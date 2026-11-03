"""
Configuration loader and validator for SIGNALSIM-INDIA Experiment Runner (P2-M03).

Loads and strictly validates experiment settings, simulation timing, evaluation seeds,
benchmark network paths, and scenario specifications from YAML configurations.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import yaml

from src.routes.generator import (
    CONFIRMED_FLEET_MIX,
    DEFAULT_EVALUATION_SEEDS,
    DEFAULT_TURNING_SPLIT,
    RouteValidationError,
    validate_fleet_composition,
    validate_turning_split,
)


APPROVED_BENCHMARK_NETWORK_NAME = "signalsim_lht_timed.net.xml"
REQUIRED_SCENARIO_IDS = ("S1", "S2", "S3", "S4")
EXPECTED_SCENARIO_MULTIPLIERS: Dict[str, float] = {
    "S1": 0.50,
    "S2": 0.75,
    "S3": 1.00,
    "S4": 1.25,
}


class ConfigError(ValueError):
    """Raised when an experiment or scenario configuration is invalid."""
    pass


@dataclass(frozen=True)
class SimulationTiming:
    """Rigorous temporal period definitions for the experiment benchmark."""
    warm_up_seconds: float = 600.0
    evaluation_seconds: float = 3600.0
    drain_seconds: float = 900.0
    step_length_seconds: float = 0.1
    controller_decision_interval_seconds: float = 10.0
    baseline_demand_per_approach: float = 600.0  # veh/h/approach

    @property
    def total_simulation_seconds(self) -> float:
        """Total simulation run duration: 600 + 3600 + 900 = 5100 seconds."""
        return self.warm_up_seconds + self.evaluation_seconds + self.drain_seconds

    @property
    def warmup_end_time(self) -> float:
        """Timestamp marking end of warm-up and start of evaluation cohort departures."""
        return self.warm_up_seconds

    @property
    def evaluation_end_time(self) -> float:
        """Timestamp marking end of evaluation cohort departures and start of drain period."""
        return self.warm_up_seconds + self.evaluation_seconds

    @property
    def drain_end_time(self) -> float:
        """Timestamp marking simulation completion."""
        return self.total_simulation_seconds


@dataclass(frozen=True)
class NetworkPaths:
    """Network, vehicle, and junction asset locations."""
    network_file: Path
    vehicle_types_file: Path
    traffic_light_id: str = "J2"
    signal_program: str = "0"


@dataclass(frozen=True)
class OutputDirectories:
    """Standardized output destination directories."""
    raw_tripinfo_dir: Path
    csv_metrics_dir: Path
    summaries_dir: Path
    plots_dir: Path

    def ensure_directories(self) -> None:
        """Create all output directories if they do not exist."""
        for p in (self.raw_tripinfo_dir, self.csv_metrics_dir, self.summaries_dir, self.plots_dir):
            p.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class ScenarioSpec:
    """Scenario configuration specification."""
    id: str
    name: str
    demand_multiplier: float
    turning_proportions: Dict[str, float]
    is_provisional: bool = False
    regime: str = ""


@dataclass(frozen=True)
class ExperimentConfig:
    """Master configuration container for SIGNALSIM-INDIA benchmark experiments."""
    name: str
    description: str
    version: str
    traffic_direction: str
    timing: SimulationTiming
    seeds: Tuple[int, ...]
    controller_ids: Tuple[str, ...]
    network: NetworkPaths
    output: OutputDirectories
    routes_dir: Path
    route_prefix: str
    inflow_edges: Tuple[str, ...]
    outflow_edges: Tuple[str, ...]
    scenarios: Dict[str, ScenarioSpec]
    fleet_mix: Dict[str, float] = field(default_factory=lambda: dict(CONFIRMED_FLEET_MIX))
    source_config_file: Optional[str] = None

    @classmethod
    def load(
        cls,
        config_path: Union[str, Path] = "configs/experiment.yaml",
        scenarios_dir: Union[str, Path] = "configs/scenarios",
        project_root: Optional[Union[str, Path]] = None,
    ) -> "ExperimentConfig":
        """
        Loads and validates experiment and scenario configuration files.

        Parameters
        ----------
        config_path : str or Path
            Path to the main experiment YAML file.
        scenarios_dir : str or Path
            Path to the scenario directory containing S1.yaml through S4.yaml.
        project_root : str or Path, optional
            Root directory of the project for resolving relative paths.
            Defaults to current working directory or two levels above configs.
        """
        cfg_file = Path(config_path)
        if not cfg_file.is_file():
            raise FileNotFoundError(f"Experiment config file not found: {cfg_file}")

        root = Path(project_root) if project_root else Path.cwd()

        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                raw_exp = yaml.safe_load(f)
        except Exception as err:
            raise ConfigError(f"Failed to parse experiment YAML at {cfg_file}: {err}") from err

        if not isinstance(raw_exp, dict):
            raise ConfigError(f"Expected mapping in {cfg_file}, got {type(raw_exp)}")

        # 1. Experiment metadata
        exp_sec = raw_exp.get("experiment", {})
        name = str(exp_sec.get("name", "signalsim_india_p2_benchmark"))
        description = str(exp_sec.get("description", ""))
        version = str(exp_sec.get("version", "0.1.0"))
        traffic_direction = str(exp_sec.get("traffic_direction", "left-hand"))
        if traffic_direction != "left-hand":
            raise ConfigError(f"Benchmark requires 'left-hand' traffic direction, got '{traffic_direction}'")

        # 2. Simulation timing
        sim_sec = raw_exp.get("simulation", {})
        warm_up = float(sim_sec.get("warm_up_seconds", 600.0))
        evaluation = float(sim_sec.get("evaluation_seconds", 3600.0))
        drain = float(sim_sec.get("drain_seconds", 900.0))
        step_len = float(sim_sec.get("step_length_seconds", 0.1))
        decision_interval = float(sim_sec.get("controller_decision_interval_seconds", 10.0))
        baseline_demand = float(sim_sec.get("baseline_demand_per_approach", 600.0))

        if warm_up != 600.0 or evaluation != 3600.0 or drain != 900.0:
            raise ConfigError(
                f"Non-negotiable timing mismatch: expected warm_up=600, evaluation=3600, drain=900; "
                f"got warm_up={warm_up}, evaluation={evaluation}, drain={drain}"
            )
        if abs(step_len - 0.1) > 1e-4:
            raise ConfigError(f"Non-negotiable SUMO step length mismatch: expected 0.1s, got {step_len}s")
        if abs(decision_interval - 10.0) > 1e-4:
            raise ConfigError(f"Non-negotiable decision interval mismatch: expected 10.0s, got {decision_interval}s")

        timing = SimulationTiming(
            warm_up_seconds=warm_up,
            evaluation_seconds=evaluation,
            drain_seconds=drain,
            step_length_seconds=step_len,
            controller_decision_interval_seconds=decision_interval,
            baseline_demand_per_approach=baseline_demand,
        )

        # 3. Seeds
        seeds_sec = raw_exp.get("seeds", {})
        raw_seeds = seeds_sec.get("evaluation_seeds", list(DEFAULT_EVALUATION_SEEDS))
        if not isinstance(raw_seeds, list) or len(raw_seeds) == 0:
            raise ConfigError("Invalid or empty evaluation_seeds in experiment config")
        seeds = tuple(int(s) for s in raw_seeds)
        if seeds != DEFAULT_EVALUATION_SEEDS:
            raise ConfigError(f"Non-negotiable seeds mismatch: expected {DEFAULT_EVALUATION_SEEDS}, got {seeds}")

        # 4. Controllers
        ctrl_sec = raw_exp.get("controllers", {})
        raw_candidates = ctrl_sec.get("candidates", [])
        controller_ids = tuple(str(c.get("id")) for c in raw_candidates if isinstance(c, dict) and "id" in c)
        if not controller_ids:
            controller_ids = ("fixed_time", "max_pressure", "ppo")

        # 5. Paths & Network Assets
        paths_sec = raw_exp.get("paths", {})
        raw_net = paths_sec.get("network_file", "lht_working/candidate/signalsim_lht_timed.net.xml")
        raw_vtypes = paths_sec.get("vehicle_types_file", "sumo_simulation/vTypes.add.xml")
        tl_id = str(paths_sec.get("traffic_light_id", "J2"))
        sig_prog = str(paths_sec.get("signal_program", "0"))

        net_path = (root / raw_net).resolve()
        vtypes_path = (root / raw_vtypes).resolve()

        # Enforce approved benchmark network
        if APPROVED_BENCHMARK_NETWORK_NAME not in net_path.name:
            raise ConfigError(
                f"Evaluation benchmark violation: must use '{APPROVED_BENCHMARK_NETWORK_NAME}', "
                f"got '{net_path.name}'"
            )
        if not net_path.is_file():
            raise FileNotFoundError(f"Approved benchmark network file not found at: {net_path}")
        if not vtypes_path.is_file():
            raise FileNotFoundError(f"Vehicle types definition file not found at: {vtypes_path}")

        network = NetworkPaths(
            network_file=net_path,
            vehicle_types_file=vtypes_path,
            traffic_light_id=tl_id,
            signal_program=sig_prog,
        )

        # 6. Outputs
        out_sec = paths_sec.get("output", {})
        output = OutputDirectories(
            raw_tripinfo_dir=(root / out_sec.get("raw_tripinfo_dir", "results/raw_tripinfo")).resolve(),
            csv_metrics_dir=(root / out_sec.get("csv_metrics_dir", "results/csv")).resolve(),
            summaries_dir=(root / out_sec.get("summaries_dir", "results/summaries")).resolve(),
            plots_dir=(root / out_sec.get("plots_dir", "results/plots")).resolve(),
        )

        # 7. Routes settings & Edges
        routes_sec = raw_exp.get("routes", {})
        routes_dir = (root / routes_sec.get("routes_dir", "simulation/routes")).resolve()
        route_prefix = str(routes_sec.get("route_prefix", "route_scenario"))

        edges_sec = routes_sec.get("edges", {})
        inflow_edges = (
            str(edges_sec.get("north_inflow", "-E1")),
            str(edges_sec.get("east_inflow", "-E2")),
            str(edges_sec.get("south_inflow", "-E3")),
            str(edges_sec.get("west_inflow", "-E4")),
        )
        outflow_edges = (
            str(edges_sec.get("north_outflow", "E1")),
            str(edges_sec.get("east_outflow", "E2")),
            str(edges_sec.get("south_outflow", "E3")),
            str(edges_sec.get("west_outflow", "E4")),
        )

        # 8. Scenarios (S1-S4)
        sc_dir = Path(scenarios_dir)
        if not sc_dir.is_dir():
            sc_dir = (root / scenarios_dir).resolve()
        if not sc_dir.is_dir():
            raise FileNotFoundError(f"Scenarios directory not found: {sc_dir}")

        scenarios: Dict[str, ScenarioSpec] = {}
        for sc_id in REQUIRED_SCENARIO_IDS:
            sc_file = sc_dir / f"{sc_id}.yaml"
            if not sc_file.is_file():
                raise FileNotFoundError(f"Required scenario file '{sc_id}.yaml' missing from {sc_dir}")

            with open(sc_file, "r", encoding="utf-8") as sf:
                sc_data = yaml.safe_load(sf)
            if not isinstance(sc_data, dict):
                raise ConfigError(f"Invalid content in {sc_file.name}")

            sc_info = sc_data.get("scenario", {})
            parsed_id = str(sc_info.get("id"))
            if parsed_id != sc_id:
                raise ConfigError(f"Scenario ID mismatch in {sc_file.name}: expected {sc_id}, got {parsed_id}")

            multiplier = float(sc_info.get("demand_multiplier", 0.0))
            expected_mult = EXPECTED_SCENARIO_MULTIPLIERS[sc_id]
            if abs(multiplier - expected_mult) > 1e-4:
                raise ConfigError(
                    f"Multiplier mismatch in {sc_id}: expected {expected_mult}, got {multiplier}"
                )

            tp_data = sc_data.get("turning_proportions", {})
            turns = {
                "left": float(tp_data.get("left", 0.20)),
                "straight": float(tp_data.get("straight", tp_data.get("through", 0.60))),
                "right": float(tp_data.get("right", 0.20)),
            }
            validate_turning_split(turns)

            scenarios[sc_id] = ScenarioSpec(
                id=sc_id,
                name=str(sc_info.get("name", sc_id)),
                demand_multiplier=multiplier,
                turning_proportions=turns,
                is_provisional=bool(sc_info.get("is_provisional", True)),
                regime=str(sc_info.get("regime", "")),
            )

        # 9. Confirmed 6-class fleet mix validation
        fleet_mix = dict(CONFIRMED_FLEET_MIX)
        validate_fleet_composition(fleet_mix)

        return cls(
            name=name,
            description=description,
            version=version,
            traffic_direction=traffic_direction,
            timing=timing,
            seeds=seeds,
            controller_ids=controller_ids,
            network=network,
            output=output,
            routes_dir=routes_dir,
            route_prefix=route_prefix,
            inflow_edges=inflow_edges,
            outflow_edges=outflow_edges,
            scenarios=scenarios,
            fleet_mix=fleet_mix,
            source_config_file=str(cfg_file.resolve()),
        )
