"""
Unit tests for the Deterministic Route Generator (src/routes/generator.py).

Verifies:
1. YAML-driven configuration loading and parameter propagation.
2. Strict rejection of incomplete fleet compositions (95% provisional mix).
3. Exact temporal evaluation cohort classification and boundary handling.
4. Departure cutoffs (no departures at or after 4200s).
5. XML schema compliance and byte-identical reproducibility.
"""

from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

import pandas as pd
import yaml

from src.routes.generator import (
    DEFAULT_TURNING_SPLIT,
    FleetCompositionError,
    LHT_MOVEMENTS,
    PROVISIONAL_UNRESOLVED_FLEET_MIX,
    RouteGeneratorConfig,
    RouteValidationError,
    VALID_VEHICLE_TYPES,
    add_cohort_column,
    classify_vehicle_cohort,
    generate_all_routes,
    generate_route_file,
    generate_scenario_demand,
    is_evaluation_cohort,
    load_route_generator_config,
    validate_fleet_composition,
    validate_movements,
    validate_turning_split,
    write_route_file,
)


# Complete 100% test fleet mix for testing generator functionality
# (Allocates 5% to bicycle to complete the 95% provisional mix for test purposes)
VALID_TEST_FLEET_MIX = {
    "car": 0.30,
    "bike": 0.35,
    "auto": 0.20,
    "bus": 0.05,
    "truck": 0.05,
    "bicycle": 0.05,
}


class TestRouteGenerator(unittest.TestCase):
    """Test suite for the deterministic route generator."""

    def setUp(self):
        """Create a temporary directory for generated test route files."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.output_dir = Path(self.temp_dir.name)
        self.config = RouteGeneratorConfig()

    def tearDown(self):
        """Clean up temporary directory."""
        self.temp_dir.cleanup()

    # ==========================================================================
    # 1. YAML-Driven Configuration Tests
    # ==========================================================================
    def test_yaml_loading_default_files(self):
        """RouteGeneratorConfig.from_yaml must correctly load experiment.yaml and scenario files."""
        cfg = RouteGeneratorConfig.from_yaml(
            experiment_path="configs/experiment.yaml",
            scenarios_dir="configs/scenarios",
        )

        self.assertEqual(cfg.warm_up_seconds, 600.0)
        self.assertEqual(cfg.evaluation_seconds, 3600.0)
        self.assertEqual(cfg.drain_seconds, 900.0)
        self.assertEqual(cfg.step_length_seconds, 0.1)
        self.assertEqual(cfg.baseline_demand_per_approach, 600.0)
        self.assertEqual(cfg.evaluation_seeds, (42, 101, 202, 303, 404))
        self.assertEqual(cfg.inflow_edges, ("-E1", "-E2", "-E3", "-E4"))
        self.assertEqual(cfg.outflow_edges, ("E1", "E2", "E3", "E4"))
        self.assertEqual(
            cfg.scenario_multipliers,
            {"S1": 0.50, "S2": 0.75, "S3": 1.00, "S4": 1.25},
        )
        self.assertIsNotNone(cfg.source_config_file)

    def test_yaml_parameter_changes_affect_config(self):
        """Modifying YAML parameters must directly change the loaded RouteGeneratorConfig."""
        custom_yaml_path = self.output_dir / "custom_experiment.yaml"
        custom_data = {
            "experiment": {"name": "custom_test"},
            "simulation": {
                "warm_up_seconds": 900.0,
                "evaluation_seconds": 1800.0,
                "drain_seconds": 450.0,
                "step_length_seconds": 0.2,
                "baseline_demand_per_approach": 750.0,
            },
            "seeds": {"evaluation_seeds": [777, 888, 999]},
            "routes": {
                "edges": {
                    "north_inflow": "-E1",
                    "east_inflow": "-E2",
                    "south_inflow": "-E3",
                    "west_inflow": "-E4",
                    "north_outflow": "E1",
                    "east_outflow": "E2",
                    "south_outflow": "E3",
                    "west_outflow": "E4",
                }
            },
        }

        with open(custom_yaml_path, "w", encoding="utf-8") as f:
            yaml.dump(custom_data, f)

        cfg = RouteGeneratorConfig.from_yaml(
            experiment_path=custom_yaml_path,
            scenarios_dir="configs/scenarios",
        )

        self.assertEqual(cfg.warm_up_seconds, 900.0)
        self.assertEqual(cfg.evaluation_seconds, 1800.0)
        self.assertEqual(cfg.drain_seconds, 450.0)
        self.assertEqual(cfg.step_length_seconds, 0.2)
        self.assertEqual(cfg.baseline_demand_per_approach, 750.0)
        self.assertEqual(cfg.evaluation_seeds, (777, 888, 999))

    def test_yaml_missing_file_raises_error(self):
        """Missing YAML file must raise FileNotFoundError."""
        with self.assertRaises(FileNotFoundError):
            RouteGeneratorConfig.from_yaml("configs/non_existent_file.yaml")

    def test_yaml_missing_section_raises_error(self):
        """YAML missing required sections must raise RouteValidationError."""
        bad_yaml_path = self.output_dir / "bad_experiment.yaml"
        bad_yaml_path.write_text("experiment: {name: 'broken'}\n", encoding="utf-8")

        with self.assertRaises(RouteValidationError):
            RouteGeneratorConfig.from_yaml(bad_yaml_path)

    def test_yaml_missing_scenarios_dir_raises_error(self):
        """Missing or None scenarios_dir must raise RouteValidationError."""
        with self.assertRaises(RouteValidationError):
            RouteGeneratorConfig.from_yaml(
                "configs/experiment.yaml",
                scenarios_dir=None,
            )
        with self.assertRaises(RouteValidationError):
            RouteGeneratorConfig.from_yaml(
                "configs/experiment.yaml",
                scenarios_dir=self.output_dir / "non_existent_scenarios_dir",
            )

    def test_yaml_missing_scenario_file_raises_error(self):
        """Missing any required scenario file (S1-S4) must raise RouteValidationError."""
        sc_dir = self.output_dir / "scenarios_missing_s4"
        sc_dir.mkdir(parents=True)
        # Create only S1, S2, S3
        for sc in ("S1", "S2", "S3"):
            sc_data = {
                "scenario": {"id": sc, "demand_multiplier": 1.0},
                "turning_proportions": {"left": 0.20, "straight": 0.60, "right": 0.20},
            }
            with open(sc_dir / f"{sc}.yaml", "w", encoding="utf-8") as f:
                yaml.dump(sc_data, f)

        with self.assertRaises(RouteValidationError) as ctx:
            RouteGeneratorConfig.from_yaml(
                "configs/experiment.yaml",
                scenarios_dir=sc_dir,
            )
        self.assertIn("S4.yaml", str(ctx.exception))

    def test_yaml_unexpected_scenario_file_raises_error(self):
        """Unexpected scenario file (e.g. S5.yaml) must raise RouteValidationError."""
        sc_dir = self.output_dir / "scenarios_unexpected"
        sc_dir.mkdir(parents=True)
        for sc in ("S1", "S2", "S3", "S4", "S5"):
            sc_data = {
                "scenario": {"id": sc, "demand_multiplier": 1.0},
                "turning_proportions": {"left": 0.20, "straight": 0.60, "right": 0.20},
            }
            with open(sc_dir / f"{sc}.yaml", "w", encoding="utf-8") as f:
                yaml.dump(sc_data, f)

        with self.assertRaises(RouteValidationError) as ctx:
            RouteGeneratorConfig.from_yaml(
                "configs/experiment.yaml",
                scenarios_dir=sc_dir,
            )
        self.assertIn("Unexpected scenario file", str(ctx.exception))

    def test_yaml_mismatched_or_duplicate_scenario_id_raises_error(self):
        """Scenario ID mismatching filename or duplicate must raise RouteValidationError."""
        sc_dir = self.output_dir / "scenarios_mismatched_id"
        sc_dir.mkdir(parents=True)
        for sc in ("S1", "S2", "S3", "S4"):
            sc_id = "S1" if sc == "S2" else sc  # S2.yaml will contain id: S1
            sc_data = {
                "scenario": {"id": sc_id, "demand_multiplier": 1.0},
                "turning_proportions": {"left": 0.20, "straight": 0.60, "right": 0.20},
            }
            with open(sc_dir / f"{sc}.yaml", "w", encoding="utf-8") as f:
                yaml.dump(sc_data, f)

        with self.assertRaises(RouteValidationError) as ctx:
            RouteGeneratorConfig.from_yaml(
                "configs/experiment.yaml",
                scenarios_dir=sc_dir,
            )
        self.assertIn("Scenario ID mismatch", str(ctx.exception))

    def test_yaml_missing_or_invalid_multiplier_raises_error(self):
        """Missing or non-positive demand multiplier must raise RouteValidationError."""
        for invalid_mult in (-0.5, 0.0, "high", True):
            sc_dir = self.output_dir / f"scenarios_bad_mult_{invalid_mult}"
            sc_dir.mkdir(parents=True)
            for sc in ("S1", "S2", "S3", "S4"):
                mult = invalid_mult if sc == "S2" else 1.0
                sc_data = {
                    "scenario": {"id": sc, "demand_multiplier": mult},
                    "turning_proportions": {"left": 0.20, "straight": 0.60, "right": 0.20},
                }
                with open(sc_dir / f"{sc}.yaml", "w", encoding="utf-8") as f:
                    yaml.dump(sc_data, f)

            with self.assertRaises(RouteValidationError):
                RouteGeneratorConfig.from_yaml(
                    "configs/experiment.yaml",
                    scenarios_dir=sc_dir,
                )

    def test_yaml_missing_or_invalid_turning_proportions_raises_error(self):
        """Missing or invalid turning proportions must raise RouteValidationError."""
        # 1. Missing turning_proportions
        sc_dir = self.output_dir / "scenarios_missing_tp"
        sc_dir.mkdir(parents=True)
        for sc in ("S1", "S2", "S3", "S4"):
            sc_data = {"scenario": {"id": sc, "demand_multiplier": 1.0}}
            with open(sc_dir / f"{sc}.yaml", "w", encoding="utf-8") as f:
                yaml.dump(sc_data, f)
        with self.assertRaises(RouteValidationError):
            RouteGeneratorConfig.from_yaml("configs/experiment.yaml", scenarios_dir=sc_dir)

        # 2. Invalid sum (0.2 + 0.5 + 0.2 = 0.9)
        sc_dir_sum = self.output_dir / "scenarios_bad_tp_sum"
        sc_dir_sum.mkdir(parents=True)
        for sc in ("S1", "S2", "S3", "S4"):
            tp = {"left": 0.20, "straight": 0.50, "right": 0.20} if sc == "S1" else {"left": 0.20, "straight": 0.60, "right": 0.20}
            sc_data = {"scenario": {"id": sc, "demand_multiplier": 1.0}, "turning_proportions": tp}
            with open(sc_dir_sum / f"{sc}.yaml", "w", encoding="utf-8") as f:
                yaml.dump(sc_data, f)
        with self.assertRaises(RouteValidationError):
            RouteGeneratorConfig.from_yaml("configs/experiment.yaml", scenarios_dir=sc_dir_sum)

        # 3. Negative turning proportion
        sc_dir_neg = self.output_dir / "scenarios_bad_tp_neg"
        sc_dir_neg.mkdir(parents=True)
        for sc in ("S1", "S2", "S3", "S4"):
            tp = {"left": -0.10, "straight": 0.90, "right": 0.20} if sc == "S1" else {"left": 0.20, "straight": 0.60, "right": 0.20}
            sc_data = {"scenario": {"id": sc, "demand_multiplier": 1.0}, "turning_proportions": tp}
            with open(sc_dir_neg / f"{sc}.yaml", "w", encoding="utf-8") as f:
                yaml.dump(sc_data, f)
        with self.assertRaises(RouteValidationError):
            RouteGeneratorConfig.from_yaml("configs/experiment.yaml", scenarios_dir=sc_dir_neg)

    def test_yaml_turning_proportions_loading_and_application(self):
        """Scenario turning proportions loaded from YAML must be applied during route generation."""
        cfg = RouteGeneratorConfig.from_yaml(
            experiment_path="configs/experiment.yaml",
            scenarios_dir="configs/scenarios",
        )

        for sc_id in ("S1", "S2", "S3", "S4"):
            self.assertIn(sc_id, cfg.scenario_turning_splits)
            split = cfg.scenario_turning_splits[sc_id]
            self.assertAlmostEqual(split["left"], 0.20)
            self.assertAlmostEqual(split["straight"], 0.60)
            self.assertAlmostEqual(split["right"], 0.20)

        # Test application: create custom scenarios with altered turning proportions
        sc_dir = self.output_dir / "scenarios_custom_turning"
        sc_dir.mkdir(parents=True)
        # S1 has 90% straight, 5% left, 5% right; S2 has 20/60/20
        custom_splits = {
            "S1": {"left": 0.05, "straight": 0.90, "right": 0.05},
            "S2": {"left": 0.20, "straight": 0.60, "right": 0.20},
            "S3": {"left": 0.20, "straight": 0.60, "right": 0.20},
            "S4": {"left": 0.20, "straight": 0.60, "right": 0.20},
        }
        for sc, split in custom_splits.items():
            sc_data = {
                "scenario": {"id": sc, "demand_multiplier": 1.0},
                "turning_proportions": split,
            }
            with open(sc_dir / f"{sc}.yaml", "w", encoding="utf-8") as f:
                yaml.dump(sc_data, f)

        custom_cfg = RouteGeneratorConfig.from_yaml(
            "configs/experiment.yaml",
            scenarios_dir=sc_dir,
        )

        # Generate demand for S1 and S2 without passing turning_split
        s1_departures = generate_scenario_demand(
            scenario_id="S1",
            seed=42,
            fleet_mix=VALID_TEST_FLEET_MIX,
            config=custom_cfg,
        )
        s2_departures = generate_scenario_demand(
            scenario_id="S2",
            seed=42,
            fleet_mix=VALID_TEST_FLEET_MIX,
            config=custom_cfg,
        )

        s1_straight_ratio = sum(1 for d in s1_departures if d.movement == "straight") / len(s1_departures)
        s2_straight_ratio = sum(1 for d in s2_departures if d.movement == "straight") / len(s2_departures)

        # S1 should have ~90% straight turns (significantly more than S2's ~60%)
        self.assertAlmostEqual(s1_straight_ratio, 0.90, delta=0.04)
        self.assertAlmostEqual(s2_straight_ratio, 0.60, delta=0.04)
        self.assertGreater(s1_straight_ratio, s2_straight_ratio)

    def test_drain_period_documented_as_simulation_clearance_not_cohort(self):
        """Drain period must be documented and treated as clearance period, not evaluation cohort."""
        doc = classify_vehicle_cohort.__doc__
        self.assertIn("clearance period", doc)
        self.assertIn("NOT an evaluation\n    cohort", doc)

        # Simulation times in drain return out_of_bounds
        self.assertEqual(classify_vehicle_cohort(4200.0), "out_of_bounds")
        self.assertEqual(classify_vehicle_cohort(4500.0), "out_of_bounds")
        self.assertEqual(classify_vehicle_cohort(5100.0), "out_of_bounds")

    # ==========================================================================
    # 2. Percentage & Fleet Composition Validation (Strict Blocker)
    # ==========================================================================
    def test_provisional_95_percent_mix_is_rejected(self):
        """The 95% provisional fleet mix must be rejected without silent normalization."""
        with self.assertRaises(FleetCompositionError) as ctx:
            validate_fleet_composition(PROVISIONAL_UNRESOLVED_FLEET_MIX)
        self.assertIn("Incomplete fleet composition", str(ctx.exception))
        self.assertIn("95.0%", str(ctx.exception))

    def test_default_generation_rejects_unresolved_fleet_mix(self):
        """Calling demand generation without providing resolved fleet mix must trigger FleetCompositionError."""
        with self.assertRaises(FleetCompositionError) as ctx:
            generate_scenario_demand(scenario_id="S1", seed=42)
        self.assertIn("Incomplete fleet composition", str(ctx.exception))

    def test_fleet_mix_none_or_empty_rejected(self):
        """None or empty fleet mix must be rejected."""
        with self.assertRaises(FleetCompositionError):
            validate_fleet_composition(None)
        with self.assertRaises(FleetCompositionError):
            validate_fleet_composition({})

    def test_fleet_mix_unknown_type_rejected(self):
        """Unknown vehicle IDs (e.g. 'suv') must be rejected."""
        invalid_mix = {"car": 0.50, "bike": 0.40, "suv": 0.10}
        with self.assertRaises(FleetCompositionError):
            validate_fleet_composition(invalid_mix)

    def test_fleet_mix_negative_share_rejected(self):
        """Negative shares must be rejected."""
        invalid_mix = {"car": 1.10, "bike": -0.10}
        with self.assertRaises(FleetCompositionError):
            validate_fleet_composition(invalid_mix)

    def test_valid_100_percent_fleet_mix_accepted(self):
        """A complete 100% fleet mix must pass validation."""
        validate_fleet_composition(VALID_TEST_FLEET_MIX)

    # ==========================================================================
    # 3. Turning Split & Movement Validation
    # ==========================================================================
    def test_turning_split_validation(self):
        """Turning split must contain left/straight/right and sum to 1.0."""
        validate_turning_split(DEFAULT_TURNING_SPLIT)

        # Invalid sum (90%)
        with self.assertRaises(RouteValidationError):
            validate_turning_split({"left": 0.20, "straight": 0.50, "right": 0.20})

        # Missing movement
        with self.assertRaises(RouteValidationError):
            validate_turning_split({"left": 0.50, "straight": 0.50})

    def test_movements_connectivity_validation(self):
        """All 4 inflow edges must map to valid outflow edges for left, straight, right."""
        validate_movements(
            LHT_MOVEMENTS,
            self.config.inflow_edges,
            self.config.outflow_edges,
        )

        # Inflow missing
        broken_movements = dict(LHT_MOVEMENTS)
        del broken_movements["-E1"]
        with self.assertRaises(RouteValidationError):
            validate_movements(broken_movements, self.config.inflow_edges, self.config.outflow_edges)

    # ==========================================================================
    # 4. Vehicle Evaluation Cohort Classification
    # ==========================================================================
    def test_cohort_classification_boundaries(self):
        """Exact classification at 0.0s, 600.0s, and 4200.0s boundaries."""
        # Warm-up: [0.0, 600.0)
        self.assertEqual(classify_vehicle_cohort(0.0), "warm_up")
        self.assertEqual(classify_vehicle_cohort(150.0), "warm_up")
        self.assertEqual(classify_vehicle_cohort(599.90), "warm_up")
        self.assertEqual(classify_vehicle_cohort(599.99), "warm_up")
        self.assertFalse(is_evaluation_cohort(0.0))
        self.assertFalse(is_evaluation_cohort(599.99))

        # Evaluation: [600.0, 4200.0)
        self.assertEqual(classify_vehicle_cohort(600.00), "evaluation")
        self.assertEqual(classify_vehicle_cohort(600.01), "evaluation")
        self.assertEqual(classify_vehicle_cohort(2400.0), "evaluation")
        self.assertEqual(classify_vehicle_cohort(4199.90), "evaluation")
        self.assertEqual(classify_vehicle_cohort(4199.99), "evaluation")
        self.assertTrue(is_evaluation_cohort(600.0))
        self.assertTrue(is_evaluation_cohort(4199.99))

        # Drain / Out of Bounds: >= 4200.0 or negative
        self.assertEqual(classify_vehicle_cohort(4200.00), "out_of_bounds")
        self.assertEqual(classify_vehicle_cohort(4200.01), "out_of_bounds")
        self.assertEqual(classify_vehicle_cohort(5000.00), "out_of_bounds")
        self.assertEqual(classify_vehicle_cohort(-1.0), "out_of_bounds")
        self.assertFalse(is_evaluation_cohort(4200.0))

    def test_vehicle_departure_records_contain_cohort(self):
        """Every generated VehicleDeparture must have a valid cohort tag ('warm_up' or 'evaluation')."""
        departures = generate_scenario_demand(
            scenario_id="S1",
            seed=42,
            fleet_mix=VALID_TEST_FLEET_MIX,
            config=self.config,
        )

        warm_up_count = sum(1 for d in departures if d.cohort == "warm_up")
        eval_count = sum(1 for d in departures if d.cohort == "evaluation")

        self.assertGreater(warm_up_count, 0, "Must contain warm-up vehicles.")
        self.assertGreater(eval_count, 0, "Must contain evaluation vehicles.")
        self.assertEqual(warm_up_count + eval_count, len(departures))

        # Verify is_evaluation property
        for d in departures:
            if d.depart_time < 600.0:
                self.assertEqual(d.cohort, "warm_up")
                self.assertFalse(d.is_evaluation)
            else:
                self.assertEqual(d.cohort, "evaluation")
                self.assertTrue(d.is_evaluation)

    def test_add_cohort_column_dataframe(self):
        """Downstream dataframe helper must add cohort and is_evaluation columns accurately."""
        df = pd.DataFrame(
            {"depart": [0.0, 599.99, 600.00, 1500.0, 4199.99, 4200.00, 4500.0]}
        )
        res = add_cohort_column(df, warm_up_seconds=600.0, evaluation_seconds=3600.0)

        expected_cohorts = [
            "warm_up",
            "warm_up",
            "evaluation",
            "evaluation",
            "evaluation",
            "out_of_bounds",
            "out_of_bounds",
        ]
        expected_eval = [False, False, True, True, True, False, False]

        self.assertEqual(res["cohort"].tolist(), expected_cohorts)
        self.assertEqual(res["is_evaluation"].tolist(), expected_eval)

    # ==========================================================================
    # 5. Departure Cutoff Rules (No Drain Departures)
    # ==========================================================================
    def test_no_departures_at_or_after_drain_cutoff(self):
        """Strict cutoff: absolutely no departures at or after 4200.0s."""
        for sc in ("S1", "S2", "S3", "S4"):
            departures = generate_scenario_demand(
                scenario_id=sc,
                seed=42,
                fleet_mix=VALID_TEST_FLEET_MIX,
                config=self.config,
            )
            for d in departures:
                self.assertLess(
                    d.depart_time,
                    4200.0,
                    f"Vehicle {d.veh_id} in {sc} departs at {d.depart_time} >= 4200.0s.",
                )
                self.assertNotEqual(d.cohort, "out_of_bounds")

    # ==========================================================================
    # 6. Reproducibility & Byte-Identical Output
    # ==========================================================================
    def test_reproducibility_byte_identical(self):
        """Identical scenario and seed inputs must produce byte-identical XML."""
        file1 = self.output_dir / "run1.rou.xml"
        file2 = self.output_dir / "run2.rou.xml"

        generate_route_file(
            scenario_id="S1",
            seed=42,
            fleet_mix=VALID_TEST_FLEET_MIX,
            output_path=file1,
            config=self.config,
        )

        generate_route_file(
            scenario_id="S1",
            seed=42,
            fleet_mix=VALID_TEST_FLEET_MIX,
            output_path=file2,
            config=self.config,
        )

        self.assertEqual(
            file1.read_bytes(),
            file2.read_bytes(),
            "Files generated with identical inputs must be byte-identical.",
        )

    def test_different_seeds_produce_different_streams(self):
        """Different seeds must yield different departure schedules and vehicle assignments."""
        file_seed42 = self.output_dir / "seed42.rou.xml"
        file_seed101 = self.output_dir / "seed101.rou.xml"

        generate_route_file(
            scenario_id="S1",
            seed=42,
            fleet_mix=VALID_TEST_FLEET_MIX,
            output_path=file_seed42,
            config=self.config,
        )

        generate_route_file(
            scenario_id="S1",
            seed=101,
            fleet_mix=VALID_TEST_FLEET_MIX,
            output_path=file_seed101,
            config=self.config,
        )

        self.assertNotEqual(
            file_seed42.read_text(encoding="utf-8"),
            file_seed101.read_text(encoding="utf-8"),
            "Different seeds must generate distinct departure streams.",
        )

    # ==========================================================================
    # 7. Scenario Demand Scaling Monotonicity
    # ==========================================================================
    def test_all_scenarios_demand_scaling(self):
        """Vehicle counts must scale monotonically with multipliers: S1 < S2 < S3 < S4."""
        counts = {}
        for sc in ("S1", "S2", "S3", "S4"):
            departures = generate_scenario_demand(
                scenario_id=sc,
                seed=42,
                fleet_mix=VALID_TEST_FLEET_MIX,
                config=self.config,
            )
            counts[sc] = len(departures)

        self.assertLess(counts["S1"], counts["S2"], "S1 count must be less than S2.")
        self.assertLess(counts["S2"], counts["S3"], "S2 count must be less than S3.")
        self.assertLess(counts["S3"], counts["S4"], "S3 count must be less than S4.")

        ratio_s1_s3 = counts["S1"] / counts["S3"]
        self.assertAlmostEqual(ratio_s1_s3, 0.50, delta=0.08)

    # ==========================================================================
    # 8. All 12 Valid Movements Represented
    # ==========================================================================
    def test_all_12_valid_movements_present(self):
        """All 12 intersection movements must be instantiated in a full scenario."""
        departures = generate_scenario_demand(
            scenario_id="S3",
            seed=42,
            fleet_mix=VALID_TEST_FLEET_MIX,
            config=self.config,
        )

        observed_movements = {(d.from_edge, d.to_edge) for d in departures}
        expected_movements = {
            ("-E1", "E2"), ("-E1", "E3"), ("-E1", "E4"),
            ("-E2", "E3"), ("-E2", "E4"), ("-E2", "E1"),
            ("-E3", "E4"), ("-E3", "E1"), ("-E3", "E2"),
            ("-E4", "E1"), ("-E4", "E2"), ("-E4", "E3"),
        }
        self.assertEqual(observed_movements, expected_movements)

    # ==========================================================================
    # 9. XML Schema, Param Tag, and Chronological Ordering
    # ==========================================================================
    def test_xml_validity_and_cohort_param(self):
        """Generated XML must parse correctly, have 12 routes, and tag cohort in <param>."""
        route_file = self.output_dir / "valid_test.rou.xml"
        generate_route_file(
            scenario_id="S2",
            seed=202,
            fleet_mix=VALID_TEST_FLEET_MIX,
            output_path=route_file,
            config=self.config,
        )

        tree = ET.parse(route_file)
        root = tree.getroot()
        self.assertEqual(root.tag, "routes")

        routes = root.findall("route")
        self.assertEqual(len(routes), 12, "Must declare exactly 12 standard routes.")

        vehicles = root.findall("vehicle")
        self.assertGreater(len(vehicles), 1000)

        # Check vehicle attributes and cohort param tag
        for veh in vehicles[:50]:  # check sample
            self.assertIn("id", veh.attrib)
            self.assertIn("type", veh.attrib)
            self.assertIn("depart", veh.attrib)
            self.assertIn("route", veh.attrib)
            self.assertIn(veh.attrib["type"], VALID_VEHICLE_TYPES)

            # Check <param key="cohort" value="..."/>
            params = {p.attrib.get("key"): p.attrib.get("value") for p in veh.findall("param")}
            self.assertIn("cohort", params)
            self.assertIn(params["cohort"], ("warm_up", "evaluation"))

    def test_chronological_ordering(self):
        """Departures must be strictly non-decreasing in departure timestamp."""
        departures = generate_scenario_demand(
            scenario_id="S1",
            seed=404,
            fleet_mix=VALID_TEST_FLEET_MIX,
            config=self.config,
        )

        for i in range(len(departures) - 1):
            t_curr = departures[i].depart_time
            t_next = departures[i + 1].depart_time
            self.assertLessEqual(
                t_curr,
                t_next,
                f"Out of order departures at index {i}: {t_curr} > {t_next}",
            )

    # ==========================================================================
    # 10. Generation of 20 Files (Test Fleet Mix in Temp Dir)
    # ==========================================================================
    def test_generate_all_routes_count(self):
        """Generating all routes must yield exactly 20 valid route files in test dir."""
        files = generate_all_routes(
            fleet_mix=VALID_TEST_FLEET_MIX,
            output_dir=self.output_dir,
            config=self.config,
        )

        self.assertEqual(len(files), 20, "Must generate exactly 20 route files.")
        for f in files:
            self.assertTrue(f.is_file(), f"Expected file {f} to exist.")
            ET.parse(f)


if __name__ == "__main__":
    unittest.main()
