"""
Automated Unit and Integration Test Suite for SIGNALSIM-INDIA Experiment Runner (P2-M03).

Tests:
1. Configuration Loader & Non-Negotiable Rules
2. Experiment Planner & Filtering
3. SUMO Lifecycle Manager & Command Construction
4. Controller Adapters (Fixed-Time, Max-Pressure, PPO)
5. Run Manager & TripInfo Metric Extraction
6. Live SUMO Integration Run on Approved LHT Network
"""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd

from src.experiments.config_loader import (
    APPROVED_BENCHMARK_NETWORK_NAME,
    ConfigError,
    ExperimentConfig,
    NetworkPaths,
    OutputDirectories,
    ScenarioSpec,
    SimulationTiming,
)
from src.experiments.controller_adapter import (
    BaseControllerAdapter,
    ControllerError,
    FixedTimeAdapter,
    MaxPressureAdapter,
    PPOAdapter,
    PPOModelNotAvailableError,
    get_controller_adapter,
)
from src.experiments.planner import (
    ExperimentPlan,
    ExperimentRunSpec,
    build_experiment_plan,
)
from src.experiments.run_manager import (
    ExperimentRunner,
    RunResult,
    _extract_run_metrics,
    run_one,
)
from src.experiments.sumo_manager import (
    build_sumo_command,
    find_sumo_binary,
)
from src.routes.generator import CONFIRMED_FLEET_MIX


class TestConfigLoader(unittest.TestCase):
    """Test suite for experiment configuration loading and validation."""

    def test_load_default_experiment_config(self):
        """Must correctly load and validate default experiment.yaml and S1-S4 configs."""
        cfg = ExperimentConfig.load(
            config_path="configs/experiment.yaml",
            scenarios_dir="configs/scenarios",
        )

        # Non-negotiable timing: 600 + 3600 + 900 = 5100s
        self.assertEqual(cfg.timing.warm_up_seconds, 600.0)
        self.assertEqual(cfg.timing.evaluation_seconds, 3600.0)
        self.assertEqual(cfg.timing.drain_seconds, 900.0)
        self.assertEqual(cfg.timing.total_simulation_seconds, 5100.0)
        self.assertEqual(cfg.timing.warmup_end_time, 600.0)
        self.assertEqual(cfg.timing.evaluation_end_time, 4200.0)
        self.assertEqual(cfg.timing.drain_end_time, 5100.0)

        # Operational parameters
        self.assertEqual(cfg.timing.step_length_seconds, 0.1)
        self.assertEqual(cfg.timing.controller_decision_interval_seconds, 10.0)
        self.assertEqual(cfg.timing.baseline_demand_per_approach, 600.0)
        self.assertEqual(cfg.traffic_direction, "left-hand")

        # Seeds
        self.assertEqual(cfg.seeds, (42, 101, 202, 303, 404))

        # Benchmark network
        self.assertIn(APPROVED_BENCHMARK_NETWORK_NAME, str(cfg.network.network_file))
        self.assertTrue(cfg.network.network_file.is_file())
        self.assertTrue(cfg.network.vehicle_types_file.is_file())
        self.assertEqual(cfg.network.traffic_light_id, "J2")
        self.assertEqual(cfg.network.signal_program, "0")

        # Scenarios S1-S4
        self.assertEqual(set(cfg.scenarios.keys()), {"S1", "S2", "S3", "S4"})
        self.assertEqual(cfg.scenarios["S1"].demand_multiplier, 0.50)
        self.assertEqual(cfg.scenarios["S2"].demand_multiplier, 0.75)
        self.assertEqual(cfg.scenarios["S3"].demand_multiplier, 1.00)
        self.assertEqual(cfg.scenarios["S4"].demand_multiplier, 1.25)

        # Fleet mix: 6 confirmed classes summing to 1.0
        self.assertEqual(len(cfg.fleet_mix), 6)
        self.assertAlmostEqual(sum(cfg.fleet_mix.values()), 1.0, places=5)
        self.assertAlmostEqual(cfg.fleet_mix["car"], 1200 / 3960, places=5)
        self.assertAlmostEqual(cfg.fleet_mix["bike"], 900 / 3960, places=5)
        self.assertAlmostEqual(cfg.fleet_mix["auto"], 720 / 3960, places=5)
        self.assertAlmostEqual(cfg.fleet_mix["bus"], 240 / 3960, places=5)
        self.assertAlmostEqual(cfg.fleet_mix["truck"], 300 / 3960, places=5)
        self.assertAlmostEqual(cfg.fleet_mix["bicycle"], 600 / 3960, places=5)

    def test_rejection_of_unapproved_network(self):
        """Must raise ConfigError if network file is not the approved benchmark network."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            bad_yaml = Path(tmp_dir) / "bad_network.yaml"
            bad_yaml.write_text(
                """
experiment:
  name: "test"
  traffic_direction: "left-hand"
simulation:
  warm_up_seconds: 600
  evaluation_seconds: 3600
  drain_seconds: 900
  step_length_seconds: 0.1
  controller_decision_interval_seconds: 10.0
  baseline_demand_per_approach: 600
seeds:
  evaluation_seeds: [42, 101, 202, 303, 404]
paths:
  network_file: "sumo_simulation/signalsim.net.xml"
  vehicle_types_file: "sumo_simulation/vTypes.add.xml"
routes:
  edges: {north_inflow: "-E1", east_inflow: "-E2", south_inflow: "-E3", west_inflow: "-E4"}
""",
                encoding="utf-8",
            )
            with self.assertRaises(ConfigError) as ctx:
                ExperimentConfig.load(config_path=bad_yaml, scenarios_dir="configs/scenarios")
            self.assertIn("benchmark", str(ctx.exception).lower())

    def test_rejection_of_non_lht_direction(self):
        """Must raise ConfigError if traffic_direction is not left-hand."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            bad_yaml = Path(tmp_dir) / "bad_dir.yaml"
            bad_yaml.write_text(
                """
experiment:
  name: "test"
  traffic_direction: "right-hand"
simulation:
  warm_up_seconds: 600
  evaluation_seconds: 3600
  drain_seconds: 900
  step_length_seconds: 0.1
  controller_decision_interval_seconds: 10.0
  baseline_demand_per_approach: 600
seeds:
  evaluation_seeds: [42, 101, 202, 303, 404]
paths:
  network_file: "lht_working/candidate/signalsim_lht_timed.net.xml"
  vehicle_types_file: "sumo_simulation/vTypes.add.xml"
""",
                encoding="utf-8",
            )
            with self.assertRaises(ConfigError) as ctx:
                ExperimentConfig.load(config_path=bad_yaml, scenarios_dir="configs/scenarios")
            self.assertIn("left-hand", str(ctx.exception))


class TestExperimentPlanner(unittest.TestCase):
    """Test suite for deterministic experiment run planning."""

    @classmethod
    def setUpClass(cls):
        cls.config = ExperimentConfig.load(
            config_path="configs/experiment.yaml",
            scenarios_dir="configs/scenarios",
        )

    def test_full_plan_runs_count(self):
        """Planning fixed_time and max_pressure across 4 scenarios and 5 seeds must yield 40 runs."""
        plan = build_experiment_plan(
            config=self.config,
            controllers=["fixed_time", "max_pressure"],
            scenarios=["S1", "S2", "S3", "S4"],
            seeds=[42, 101, 202, 303, 404],
        )
        self.assertEqual(plan.total_runs, 40)

        # Check unique run IDs
        run_ids = [r.run_id for r in plan.runs]
        self.assertEqual(len(run_ids), len(set(run_ids)))
        self.assertIn("fixed_time_S1_seed42", run_ids)
        self.assertIn("max_pressure_S4_seed404", run_ids)

    def test_plan_filtering(self):
        """Filtering plan by controller, scenario, or seed must return exact subset."""
        plan = build_experiment_plan(
            config=self.config,
            controllers=["fixed_time", "max_pressure"],
            scenarios=["S1", "S2", "S3", "S4"],
            seeds=[42, 101, 202, 303, 404],
        )

        filtered = plan.filter(controllers=["fixed_time"], scenarios=["S1"])
        self.assertEqual(filtered.total_runs, 5)  # 5 seeds for fixed_time on S1
        for r in filtered.runs:
            self.assertEqual(r.controller_id, "fixed_time")
            self.assertEqual(r.scenario_id, "S1")

    def test_run_spec_paths_and_durations(self):
        """RunSpec must contain duration 5100s and appropriate output XML file paths."""
        plan = build_experiment_plan(
            config=self.config,
            controllers=["fixed_time"],
            scenarios=["S2"],
            seeds=[101],
        )
        spec = plan.runs[0]
        self.assertEqual(spec.expected_duration, 5100.0)
        self.assertEqual(spec.run_id, "fixed_time_S2_seed101")
        self.assertTrue(str(spec.tripinfo_output_path).endswith("fixed_time_S2_seed101_tripinfo.xml"))


class TestSumoManager(unittest.TestCase):
    """Test suite for SUMO process lifecycle manager."""

    def test_find_sumo_binary(self):
        """find_sumo_binary must locate installed sumo executable without error."""
        sumo_bin = find_sumo_binary(gui=False)
        self.assertTrue(Path(sumo_bin).is_file())
        self.assertIn("sumo", Path(sumo_bin).name.lower())

    def test_build_sumo_command(self):
        """build_sumo_command must generate complete, valid SUMO argument sequence."""
        cmd = build_sumo_command(
            sumo_binary="sumo",
            net_file="test.net.xml",
            route_file="test.rou.xml",
            additional_file="test.add.xml",
            end_time=5100.0,
            step_length=0.1,
            seed=42,
            tripinfo_output="output/tripinfo.xml",
            summary_output="output/summary.xml",
            log_output="output/sim.log",
            lateral_resolution=0.5,
            write_unfinished=True,
        )

        self.assertIn("-n", cmd)
        self.assertIn("-r", cmd)
        self.assertIn("-a", cmd)
        self.assertIn("--begin", cmd)
        self.assertIn("0", cmd)
        self.assertIn("--end", cmd)
        self.assertIn("5100.0", cmd)
        self.assertIn("--step-length", cmd)
        self.assertIn("0.1", cmd)
        self.assertIn("--seed", cmd)
        self.assertIn("42", cmd)
        self.assertIn("--lateral-resolution", cmd)
        self.assertIn("0.5", cmd)
        self.assertIn("--tripinfo-output.write-unfinished", cmd)
        self.assertIn("true", cmd)

    def test_fixed_time_sumocfg_validity(self):
        """sumo_simulation/signalsim1_fixed.sumocfg must be valid, accessible, and point to approved LHT network."""
        cfg_path = Path("sumo_simulation/signalsim1_fixed.sumocfg")
        self.assertTrue(cfg_path.is_file(), "signalsim1_fixed.sumocfg must exist")

        tree = ET.parse(cfg_path)
        root = tree.getroot()
        net_node = root.find("input/net-file")
        self.assertIsNotNone(net_node, "input/net-file element must exist")
        net_val = net_node.attrib["value"]

        resolved_net = (cfg_path.parent / net_val).resolve()
        self.assertTrue(resolved_net.is_file(), f"Network file '{resolved_net}' must be accessible")
        self.assertEqual(resolved_net.name, APPROVED_BENCHMARK_NETWORK_NAME)


class TestControllerAdapters(unittest.TestCase):
    """Test suite for controller adapters."""

    def test_factory_creation(self):
        """Factory must create instances of FixedTime, MaxPressure, and PPO adapters."""
        ft = get_controller_adapter("fixed_time")
        self.assertIsInstance(ft, FixedTimeAdapter)
        self.assertEqual(ft.controller_id, "fixed_time")

        mp = get_controller_adapter("max_pressure")
        self.assertIsInstance(mp, MaxPressureAdapter)
        self.assertEqual(mp.controller_id, "max_pressure")

        ppo = get_controller_adapter("ppo")
        self.assertIsInstance(ppo, PPOAdapter)
        self.assertEqual(ppo.controller_id, "ppo")

        with self.assertRaises(ValueError):
            get_controller_adapter("unknown_controller")

    def test_ppo_raises_without_checkpoint(self):
        """PPO adapter must raise PPOModelNotAvailableError when model checkpoint is missing."""
        ppo = PPOAdapter(tls_id="J2", checkpoint_path=None, mock_policy=False)
        mock_conn = MagicMock()
        mock_cfg = MagicMock()
        with self.assertRaises(PPOModelNotAvailableError):
            ppo.setup(mock_conn, mock_cfg, "S1", 42)

    def test_fixed_time_adapter_mock_setup(self):
        """FixedTimeAdapter must verify static program phases and set program 0."""
        mock_conn = MagicMock()
        mock_conn.trafficlight.getIDList.return_value = ["J2"]

        # Mock program matching verified 6 phases
        mock_phase = MagicMock()
        mock_phases = []
        for state in FixedTimeAdapter.EXPECTED_STATES:
            p = MagicMock()
            p.state = state
            mock_phases.append(p)
        mock_prog = MagicMock()
        mock_prog.phases = mock_phases
        mock_prog.programID = "0"
        mock_conn.trafficlight.getAllProgramLogics.return_value = [mock_prog]

        ft = FixedTimeAdapter(tls_id="J2")
        mock_cfg = MagicMock()
        ft.setup(mock_conn, mock_cfg, "S1", 42)

        mock_conn.trafficlight.setProgram.assert_called_with("J2", "0")
        mock_conn.trafficlight.setPhase.assert_called_with("J2", 0)


class TestRunManagerAndMetrics(unittest.TestCase):
    """Test suite for run manager execution and metric calculations."""

    @classmethod
    def setUpClass(cls):
        cls.config = ExperimentConfig.load(
            config_path="configs/experiment.yaml",
            scenarios_dir="configs/scenarios",
        )

    def test_extract_run_metrics_cohort_filtering(self):
        """Metrics extractor must correctly exclude warm-up [0, 600) and drain [4200, 5100] from evaluation."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tripinfo_xml = Path(tmp_dir) / "test_tripinfo.xml"
            tripinfo_xml.write_text(
                """<?xml version="1.0" encoding="UTF-8"?>
<tripinfos>
    <!-- Warm-up vehicles (< 600s) -->
    <tripinfo id="veh_warm_1" depart="100.0" arrival="150.0" duration="50.0" waitingTime="10.0" timeLoss="12.0" routeLength="250.0"/>
    <tripinfo id="veh_warm_2" depart="599.9" arrival="640.0" duration="40.1" waitingTime="5.0" timeLoss="6.0" routeLength="250.0"/>

    <!-- Evaluation vehicles (600s <= depart < 4200s) -->
    <tripinfo id="veh_eval_1" depart="600.0" arrival="700.0" duration="100.0" waitingTime="20.0" timeLoss="25.0" routeLength="250.0"/>
    <tripinfo id="veh_eval_2" depart="1500.0" arrival="1620.0" duration="120.0" waitingTime="30.0" timeLoss="35.0" routeLength="250.0"/>
    <tripinfo id="veh_eval_3" depart="4199.9" arrival="4300.0" duration="100.1" waitingTime="10.0" timeLoss="15.0" routeLength="250.0"/>
    <!-- Unfinished evaluation vehicle -->
    <unfinished-tripinfo id="veh_eval_unf" depart="3000.0" waitingTime="80.0" timeLoss="90.0" routeLength="100.0"/>
</tripinfos>
""",
                encoding="utf-8",
            )

            metrics = _extract_run_metrics(tripinfo_xml, self.config.timing)

            self.assertEqual(metrics["total_vehicles"], 6)
            self.assertEqual(metrics["completed_vehicles"], 5)
            self.assertEqual(metrics["unfinished_vehicles"], 1)
            self.assertEqual(metrics["warmup_vehicles"], 2)
            self.assertEqual(metrics["evaluation_vehicles"], 4)  # 3 completed + 1 unfinished

            # Evaluation completed metrics: average of [100.0, 120.0, 100.1]
            expected_mean_travel = (100.0 + 120.0 + 100.1) / 3.0
            expected_mean_waiting = (20.0 + 30.0 + 10.0) / 3.0
            expected_mean_loss = (25.0 + 35.0 + 15.0) / 3.0

            self.assertAlmostEqual(metrics["mean_travel_time"], round(expected_mean_travel, 2))
            self.assertAlmostEqual(metrics["mean_waiting_time"], round(expected_mean_waiting, 2))
            self.assertAlmostEqual(metrics["mean_time_loss"], round(expected_mean_loss, 2))

            # Throughput: 3 completed evaluation vehicles / 1 hour = 3.0 vph
            self.assertEqual(metrics["throughput_vph"], 3.0)

    def test_run_one_with_mock_connection(self):
        """run_one must execute stepping loop and return RunResult."""
        mock_conn = MagicMock()
        mock_conn.simulation.getTime.side_effect = [0.0, 5.0, 10.0, 10.0]

        mock_adapter = MagicMock()
        run_spec = ExperimentRunSpec(
            run_id="mock_run",
            controller_id="fixed_time",
            scenario_id="S1",
            seed=42,
            route_file=Path("simulation/routes/test.rou.xml"),
            expected_duration=10.0,
            tripinfo_output_path=Path("results/mock_tripinfo.xml"),
            summary_output_path=Path("results/mock_summary.xml"),
            log_output_path=Path("results/mock.log"),
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            route_file = Path(tmp_dir) / "test.rou.xml"
            route_file.write_text("<routes/>", encoding="utf-8")
            tripinfo_file = Path(tmp_dir) / "test_tripinfo.xml"
            tripinfo_file.write_text("<tripinfos/>", encoding="utf-8")

            spec = ExperimentRunSpec(
                run_id="mock_run",
                controller_id="fixed_time",
                scenario_id="S1",
                seed=42,
                route_file=route_file,
                expected_duration=10.0,
                tripinfo_output_path=tripinfo_file,
                summary_output_path=Path(tmp_dir) / "summary.xml",
                log_output_path=Path(tmp_dir) / "run.log",
            )

            res = run_one(
                run_spec=spec,
                config=self.config,
                adapter=mock_adapter,
                connection=mock_conn,
            )

            self.assertEqual(res.status, "SUCCESS")
            self.assertEqual(res.run_id, "mock_run")
            mock_adapter.setup.assert_called_once()
            mock_adapter.teardown.assert_called_once()


class TestLiveSumoIntegration(unittest.TestCase):
    """End-to-end integration test with live SUMO simulation on approved LHT network."""

    @classmethod
    def setUpClass(cls):
        cls.config = ExperimentConfig.load(
            config_path="configs/experiment.yaml",
            scenarios_dir="configs/scenarios",
        )

    def test_live_fixed_time_and_max_pressure_execution(self):
        """Must successfully start SUMO, execute 10 steps, control signals, and produce valid TripInfo XML."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_output = Path(tmp_dir)

            # Generate a minimal valid route file with 1 vehicle
            route_file = temp_output / "mini_test.rou.xml"
            route_file.write_text(
                """<?xml version="1.0" encoding="UTF-8"?>
<routes>
    <route id="r1" edges="-E1 E3"/>
    <vehicle id="veh_001" type="car" depart="0.0" route="r1"/>
</routes>
""",
                encoding="utf-8",
            )

            # Test Fixed-Time
            ft_spec = ExperimentRunSpec(
                run_id="test_live_ft",
                controller_id="fixed_time",
                scenario_id="S1",
                seed=42,
                route_file=route_file,
                expected_duration=2.0,  # 2 seconds = 20 steps at 0.1s
                tripinfo_output_path=temp_output / "ft_tripinfo.xml",
                summary_output_path=temp_output / "ft_summary.xml",
                log_output_path=temp_output / "ft.log",
            )

            ft_res = run_one(run_spec=ft_spec, config=self.config, gui=False)
            self.assertEqual(ft_res.status, "SUCCESS")
            self.assertTrue(ft_spec.tripinfo_output_path.is_file())

            # Test Max-Pressure
            mp_spec = ExperimentRunSpec(
                run_id="test_live_mp",
                controller_id="max_pressure",
                scenario_id="S1",
                seed=42,
                route_file=route_file,
                expected_duration=2.0,  # 2 seconds = 20 steps at 0.1s
                tripinfo_output_path=temp_output / "mp_tripinfo.xml",
                summary_output_path=temp_output / "mp_summary.xml",
                log_output_path=temp_output / "mp.log",
            )

            mp_res = run_one(run_spec=mp_spec, config=self.config, gui=False)
            self.assertEqual(mp_res.status, "SUCCESS")
            self.assertTrue(mp_spec.tripinfo_output_path.is_file())


if __name__ == "__main__":
    unittest.main()
