"""
Deterministic Traffic Demand and Route Generator for SIGNALSIM-INDIA.

This module generates reproducible SUMO route files (.rou.xml) across scenarios
S1 to S4 and evaluation seeds using matched-seed methodology.

Key Principles:
---------------
1. YAML-Driven Configuration:
   Loads configuration dynamically from `configs/experiment.yaml` and scenario YAMLs
   (`configs/scenarios/S*.yaml`) using PyYAML, avoiding hardcoded duplication.
2. Determinism:
   Identical (scenario, seed) inputs produce byte-identical XML files across runs.
3. Fairness & Matched Seeds:
   Identical route files are used across candidate controllers (Fixed-time,
   Max-Pressure, PPO) to eliminate traffic demand stochasticity as a confounder.
4. Strict Temporal Partitions & Evaluation Cohorts:
   - Warm-Up: 0.0s to 600.0s (departures < 600s; pre-loads network, excluded from stats).
   - Evaluation: 600.0s to 4200.0s (600s <= departures < 4200s; the evaluation cohort).
   - Drain: 4200.0s to 5100.0s (NO new departures; clearance window).
   Downstream metrics can identify cohorts reliably without fragile string parsing.
5. Validation & Rigor:
   Fleet composition percentages must sum to 1.0 (100%). Incomplete proportions
   are rejected with clear errors—never silently normalized or assumed.
"""

from dataclasses import dataclass, field
from pathlib import Path
import random
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union
import xml.etree.ElementTree as ET

import yaml


# ==============================================================================
# Verified Network Topologies and Movements (LHT)
# ==============================================================================

# Verified 12 LHT movements on the 4-arm intersection
# Format: inflow_edge -> {movement_type: outflow_edge}
LHT_MOVEMENTS: Dict[str, Dict[str, str]] = {
    "-E1": {"left": "E2", "straight": "E3", "right": "E4"},  # North approach
    "-E2": {"left": "E3", "straight": "E4", "right": "E1"},  # East approach
    "-E3": {"left": "E4", "straight": "E1", "right": "E2"},  # South approach
    "-E4": {"left": "E1", "straight": "E2", "right": "E3"},  # West approach
}

# Mapping of (inflow_edge, movement_type) to canonical route ID
ROUTE_ID_MAP: Dict[Tuple[str, str], str] = {
    ("-E1", "left"): "route_N_E",
    ("-E1", "straight"): "route_N_S",
    ("-E1", "right"): "route_N_W",
    ("-E2", "left"): "route_E_S",
    ("-E2", "straight"): "route_E_W",
    ("-E2", "right"): "route_E_N",
    ("-E3", "left"): "route_S_W",
    ("-E3", "straight"): "route_S_N",
    ("-E3", "right"): "route_S_E",
    ("-E4", "left"): "route_W_N",
    ("-E4", "straight"): "route_W_E",
    ("-E4", "right"): "route_W_S",
}

# The 6 valid vehicle types defined in vTypes.add.xml
VALID_VEHICLE_TYPES: Tuple[str, ...] = (
    "car",
    "bike",
    "auto",
    "bus",
    "truck",
    "bicycle",
)

# Agreed turning split: Left 20%, Straight 60%, Right 20%
DEFAULT_TURNING_SPLIT: Dict[str, float] = {
    "left": 0.20,
    "straight": 0.60,
    "right": 0.20,
}

# Provisional fleet mix proposed by P1 (totals only 95% - will fail validation)
PROVISIONAL_UNRESOLVED_FLEET_MIX: Dict[str, float] = {
    "car": 0.30,
    "bike": 0.35,
    "auto": 0.20,
    "bus": 0.05,
    "truck": 0.05,
}

# Confirmed 6-class fleet composition (100% total, 3960 vehicles)
CONFIRMED_FLEET_COUNTS: Dict[str, int] = {
    "car": 1200,
    "bike": 900,
    "auto": 720,
    "bus": 240,
    "truck": 300,
    "bicycle": 600,
}

CONFIRMED_FLEET_MIX: Dict[str, float] = {
    "car": 1200 / 3960,
    "bike": 900 / 3960,
    "auto": 720 / 3960,
    "bus": 240 / 3960,
    "truck": 300 / 3960,
    "bicycle": 600 / 3960,
}

DEFAULT_SCENARIO_MULTIPLIERS: Dict[str, float] = {
    "S1": 0.50,
    "S2": 0.75,
    "S3": 1.00,
    "S4": 1.25,
}

DEFAULT_EVALUATION_SEEDS: Tuple[int, ...] = (42, 101, 202, 303, 404)


# ==============================================================================
# Custom Exceptions
# ==============================================================================

class RouteGeneratorError(Exception):
    """Base exception for route generation errors."""
    pass


class FleetCompositionError(RouteGeneratorError):
    """Raised when fleet mix proportions are incomplete, invalid, or do not sum to 1.0."""
    pass


class RouteValidationError(RouteGeneratorError):
    """Raised when network edge, route, or timing parameters fail validation."""
    pass


# ==============================================================================
# Cohort Classification Utilities
# ==============================================================================

def classify_vehicle_cohort(
    depart_time: float,
    warm_up_seconds: float = 600.0,
    evaluation_seconds: float = 3600.0,
) -> str:
    """
    Classifies a vehicle into its temporal evaluation cohort based on exact departure time.

    Cohorts:
    --------
    - 'warm_up': Departures strictly in [0.0, warm_up_seconds) (e.g. 0.0 <= t < 600.0).
      These vehicles preload the network to stochastic steady-state and are EXCLUDED
      from evaluation statistics.
    - 'evaluation': Departures strictly in [warm_up_seconds, warm_up_seconds + evaluation_seconds)
      (e.g. 600.0 <= t < 4200.0). This defines the formal evaluation cohort C_eval.
    - 'out_of_bounds': Departures at or after warm_up_seconds + evaluation_seconds (e.g. t >= 4200.0),
      or negative departure times.

    NOTE: The Drain period [4200.0, 5100.0] is a simulation clearance period, NOT an evaluation
    cohort. No new vehicles depart during the drain period; it exists solely to allow vehicles
    already departed during warm-up and evaluation to complete their trips and clear the network.

    Parameters
    ----------
    depart_time : float
        Departure timestamp in seconds.
    warm_up_seconds : float
        Warm-up period duration in seconds (default 600.0).
    evaluation_seconds : float
        Evaluation period duration in seconds (default 3600.0).

    Returns
    -------
    str
        'warm_up', 'evaluation', or 'out_of_bounds'.
    """
    if 0.0 <= depart_time < warm_up_seconds:
        return "warm_up"
    elif warm_up_seconds <= depart_time < (warm_up_seconds + evaluation_seconds):
        return "evaluation"
    else:
        return "out_of_bounds"


def is_evaluation_cohort(
    depart_time: float,
    warm_up_seconds: float = 600.0,
    evaluation_seconds: float = 3600.0,
) -> bool:
    """
    Returns True if and only if the vehicle belongs to the active evaluation cohort.
    """
    return classify_vehicle_cohort(depart_time, warm_up_seconds, evaluation_seconds) == "evaluation"


def add_cohort_column(
    df: Any,
    warm_up_seconds: float = 600.0,
    evaluation_seconds: float = 3600.0,
    depart_col: str = "depart",
) -> Any:
    """
    Downstream helper: Adds 'cohort' and 'is_evaluation' columns to a pandas DataFrame
    containing vehicle records with a departure time column. Avoids fragile ID parsing.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame containing vehicle records (e.g. from tripinfo_parser).
    warm_up_seconds : float
        Warm-up duration in seconds.
    evaluation_seconds : float
        Evaluation duration in seconds.
    depart_col : str
        Column name holding departure timestamps (default 'depart').

    Returns
    -------
    pd.DataFrame
        DataFrame with added 'cohort' and 'is_evaluation' columns.
    """
    df = df.copy()
    df["cohort"] = df[depart_col].apply(
        lambda t: classify_vehicle_cohort(t, warm_up_seconds, evaluation_seconds)
    )
    df["is_evaluation"] = df["cohort"] == "evaluation"
    return df


# ==============================================================================
# Configuration Data Structures & YAML Loaders
# ==============================================================================

@dataclass(frozen=True)
class VehicleDeparture:
    """Represents a single deterministic vehicle departure record."""
    veh_id: str
    depart_time: float
    veh_type: str
    from_edge: str
    to_edge: str
    route_id: str
    movement: str
    cohort: str = "evaluation"  # "warm_up" or "evaluation"

    @property
    def is_evaluation(self) -> bool:
        """True if the vehicle belongs to the formal evaluation cohort."""
        return self.cohort == "evaluation"


@dataclass(frozen=True)
class RouteGeneratorConfig:
    """Configuration container for deterministic route generation."""
    warm_up_seconds: float = 600.0
    evaluation_seconds: float = 3600.0
    drain_seconds: float = 900.0
    step_length_seconds: float = 0.1
    baseline_demand_per_approach: float = 600.0  # vehicles/hour/approach
    inflow_edges: Tuple[str, ...] = ("-E1", "-E2", "-E3", "-E4")
    outflow_edges: Tuple[str, ...] = ("E1", "E2", "E3", "E4")
    movements: Dict[str, Dict[str, str]] = field(default_factory=lambda: LHT_MOVEMENTS)
    turning_split: Dict[str, float] = field(default_factory=lambda: DEFAULT_TURNING_SPLIT)
    scenario_turning_splits: Dict[str, Dict[str, float]] = field(default_factory=dict)
    valid_vehicle_types: Tuple[str, ...] = VALID_VEHICLE_TYPES
    scenario_multipliers: Dict[str, float] = field(default_factory=lambda: dict(DEFAULT_SCENARIO_MULTIPLIERS))
    evaluation_seeds: Tuple[int, ...] = DEFAULT_EVALUATION_SEEDS
    source_config_file: Optional[str] = None

    @property
    def max_injection_time(self) -> float:
        """Maximum timestamp for vehicle departures (warm_up + evaluation)."""
        return self.warm_up_seconds + self.evaluation_seconds

    @property
    def total_simulation_time(self) -> float:
        """Total simulation duration including drain period."""
        return self.warm_up_seconds + self.evaluation_seconds + self.drain_seconds

    @classmethod
    def from_yaml(
        cls,
        experiment_path: Union[str, Path] = "configs/experiment.yaml",
        scenarios_dir: Optional[Union[str, Path]] = "configs/scenarios",
    ) -> "RouteGeneratorConfig":
        """
        Builds a RouteGeneratorConfig dynamically by loading and validating
        `configs/experiment.yaml` and scenario definitions (`configs/scenarios/S1.yaml`..`S4.yaml`).

        Parameters
        ----------
        experiment_path : str or Path
            Path to the main experiment YAML configuration.
        scenarios_dir : str or Path
            Path to the directory containing scenario YAMLs (requires S1.yaml..S4.yaml).

        Returns
        -------
        RouteGeneratorConfig
            Populated configuration object.

        Raises
        ------
        FileNotFoundError
            If configuration files are missing.
        RouteValidationError
            If required sections or fields are missing, invalid, or unexpected.
        """
        exp_file = Path(experiment_path).resolve()
        if not exp_file.is_file():
            raise FileNotFoundError(f"Experiment config file not found at: {exp_file}")

        try:
            with open(exp_file, "r", encoding="utf-8") as f:
                exp_data = yaml.safe_load(f)
        except Exception as err:
            raise RouteValidationError(f"Failed to parse YAML file at {exp_file}: {err}") from err

        if not isinstance(exp_data, dict):
            raise RouteValidationError(f"Invalid YAML structure in {exp_file}: expected dictionary.")

        # Validate top-level required sections
        required_sections = ["simulation", "seeds", "routes"]
        for sec in required_sections:
            if sec not in exp_data or not isinstance(exp_data[sec], dict):
                raise RouteValidationError(
                    f"Missing or invalid required section '{sec}' in {exp_file}."
                )

        sim_sec = exp_data["simulation"]
        for key in (
            "warm_up_seconds",
            "evaluation_seconds",
            "drain_seconds",
            "step_length_seconds",
            "baseline_demand_per_approach",
        ):
            if key not in sim_sec or not isinstance(sim_sec[key], (int, float)) or sim_sec[key] <= 0:
                raise RouteValidationError(
                    f"Section 'simulation' missing valid positive numeric field '{key}' in {exp_file}."
                )

        warm_up_seconds = float(sim_sec["warm_up_seconds"])
        evaluation_seconds = float(sim_sec["evaluation_seconds"])
        drain_seconds = float(sim_sec["drain_seconds"])
        step_length_seconds = float(sim_sec["step_length_seconds"])
        baseline_demand = float(sim_sec["baseline_demand_per_approach"])

        # Validate seeds
        seeds_sec = exp_data["seeds"]
        if "evaluation_seeds" not in seeds_sec or not isinstance(seeds_sec["evaluation_seeds"], list):
            raise RouteValidationError(f"Missing list 'evaluation_seeds' in 'seeds' section in {exp_file}.")
        if len(seeds_sec["evaluation_seeds"]) == 0:
            raise RouteValidationError(f"'evaluation_seeds' list cannot be empty in {exp_file}.")
        evaluation_seeds = tuple(int(s) for s in seeds_sec["evaluation_seeds"])

        # Validate edges
        routes_sec = exp_data["routes"]
        if "edges" not in routes_sec or not isinstance(routes_sec["edges"], dict):
            raise RouteValidationError(f"Missing 'edges' dictionary in 'routes' section in {exp_file}.")
        edges_sec = routes_sec["edges"]

        for edge_k in ("north_inflow", "east_inflow", "south_inflow", "west_inflow"):
            if edge_k not in edges_sec or not edges_sec[edge_k] or "<PENDING" in str(edges_sec[edge_k]):
                raise RouteValidationError(
                    f"Edge '{edge_k}' is missing or unconfirmed placeholder in {exp_file}."
                )
        for edge_k in ("north_outflow", "east_outflow", "south_outflow", "west_outflow"):
            if edge_k not in edges_sec or not edges_sec[edge_k] or "<PENDING" in str(edges_sec[edge_k]):
                raise RouteValidationError(
                    f"Edge '{edge_k}' is missing or unconfirmed placeholder in {exp_file}."
                )

        inflow_edges = (
            str(edges_sec["north_inflow"]),
            str(edges_sec["east_inflow"]),
            str(edges_sec["south_inflow"]),
            str(edges_sec["west_inflow"]),
        )
        outflow_edges = (
            str(edges_sec["north_outflow"]),
            str(edges_sec["east_outflow"]),
            str(edges_sec["south_outflow"]),
            str(edges_sec["west_outflow"]),
        )

        # Load and validate scenario YAMLs (strictly requiring S1, S2, S3, S4)
        if scenarios_dir is None:
            raise RouteValidationError(
                "Scenarios directory must be provided; scenarios S1 through S4 are strictly required."
            )

        sc_dir = Path(scenarios_dir).resolve()
        if not sc_dir.is_dir():
            raise RouteValidationError(
                f"Scenarios directory not found or not a directory: {sc_dir}"
            )

        REQUIRED_SCENARIOS = ("S1", "S2", "S3", "S4")
        for req_id in REQUIRED_SCENARIOS:
            expected_file = sc_dir / f"{req_id}.yaml"
            if not expected_file.is_file():
                raise RouteValidationError(
                    f"Required scenario file '{req_id}.yaml' is missing from {sc_dir}."
                )

        yaml_files = sorted(sc_dir.glob("*.yaml"))
        scenario_multipliers: Dict[str, float] = {}
        scenario_turning_splits: Dict[str, Dict[str, float]] = {}

        for sc_path in yaml_files:
            file_stem = sc_path.stem
            if file_stem not in REQUIRED_SCENARIOS:
                raise RouteValidationError(
                    f"Unexpected scenario file '{sc_path.name}' found in {sc_dir}. Exactly S1-S4 are required."
                )

            try:
                with open(sc_path, "r", encoding="utf-8") as sf:
                    sc_content = yaml.safe_load(sf)
            except Exception as err:
                raise RouteValidationError(
                    f"Error reading scenario file {sc_path.name}: {err}"
                ) from err

            if not isinstance(sc_content, dict):
                raise RouteValidationError(
                    f"Invalid YAML structure in {sc_path.name}: expected dictionary."
                )

            if "scenario" not in sc_content or not isinstance(sc_content["scenario"], dict):
                raise RouteValidationError(
                    f"Missing or invalid 'scenario' section in {sc_path.name}."
                )

            sc_sec = sc_content["scenario"]
            if "id" not in sc_sec:
                raise RouteValidationError(
                    f"Missing scenario 'id' in {sc_path.name}."
                )

            sc_id = str(sc_sec["id"])
            if sc_id != file_stem:
                raise RouteValidationError(
                    f"Scenario ID mismatch in {sc_path.name}: expected '{file_stem}', got '{sc_id}'."
                )

            if sc_id in scenario_multipliers:
                raise RouteValidationError(
                    f"Duplicate scenario ID '{sc_id}' found in {sc_path.name}."
                )

            if "demand_multiplier" not in sc_sec:
                raise RouteValidationError(
                    f"Missing 'demand_multiplier' in {sc_path.name}."
                )

            raw_mult = sc_sec["demand_multiplier"]
            if (
                not isinstance(raw_mult, (int, float))
                or isinstance(raw_mult, bool)
                or raw_mult <= 0
            ):
                raise RouteValidationError(
                    f"Invalid demand multiplier in {sc_path.name}: must be a positive number, got {raw_mult}."
                )
            scenario_multipliers[sc_id] = float(raw_mult)

            # Turning proportions
            if (
                "turning_proportions" not in sc_content
                or not isinstance(sc_content["turning_proportions"], dict)
            ):
                raise RouteValidationError(
                    f"Missing or invalid 'turning_proportions' section in {sc_path.name}."
                )

            tp_data = sc_content["turning_proportions"]
            if "left" in tp_data and ("straight" in tp_data or "through" in tp_data) and "right" in tp_data:
                try:
                    left_v = float(tp_data["left"])
                    straight_v = float(tp_data.get("straight", tp_data.get("through")))
                    right_v = float(tp_data["right"])
                except (ValueError, TypeError) as conv_err:
                    raise RouteValidationError(
                        f"Non-numeric turning proportions in {sc_path.name}: {conv_err}"
                    ) from conv_err
                turns = {"left": left_v, "straight": straight_v, "right": right_v}
            else:
                raise RouteValidationError(
                    f"'turning_proportions' in {sc_path.name} must specify 'left', 'straight' (or 'through'), and 'right'."
                )

            validate_turning_split(turns)
            scenario_turning_splits[sc_id] = turns

        if set(scenario_multipliers.keys()) != set(REQUIRED_SCENARIOS):
            raise RouteValidationError(
                f"Missing required scenarios. Expected exactly {REQUIRED_SCENARIOS}, got {tuple(scenario_multipliers.keys())}."
            )

        return cls(
            warm_up_seconds=warm_up_seconds,
            evaluation_seconds=evaluation_seconds,
            drain_seconds=drain_seconds,
            step_length_seconds=step_length_seconds,
            baseline_demand_per_approach=baseline_demand,
            inflow_edges=inflow_edges,
            outflow_edges=outflow_edges,
            evaluation_seeds=evaluation_seeds,
            scenario_multipliers=scenario_multipliers,
            scenario_turning_splits=scenario_turning_splits,
            source_config_file=str(exp_file),
        )


def load_route_generator_config(
    experiment_path: Union[str, Path] = "configs/experiment.yaml",
    scenarios_dir: Optional[Union[str, Path]] = "configs/scenarios",
) -> RouteGeneratorConfig:
    """
    Convenience loader to instantiate RouteGeneratorConfig from YAML files.
    """
    return RouteGeneratorConfig.from_yaml(experiment_path, scenarios_dir)


# ==============================================================================
# Validation Functions
# ==============================================================================

def validate_fleet_composition(
    fleet_mix: Optional[Dict[str, float]],
    valid_types: Sequence[str] = VALID_VEHICLE_TYPES,
    tolerance: float = 1e-4,
) -> None:
    """
    Validates that fleet mix proportions are complete, valid, and sum exactly to 1.0.

    Parameters
    ----------
    fleet_mix : dict of str to float
        Dictionary mapping vehicle type ID to its proportion.
    valid_types : sequence of str
        Approved vehicle type identifiers.
    tolerance : float
        Numerical tolerance for floating point summation.

    Raises
    ------
    FleetCompositionError
        If fleet_mix is None, empty, contains unknown vehicle types, has negative
        shares, or does not sum to 1.0 (100%).
    """
    if fleet_mix is None or len(fleet_mix) == 0:
        raise FleetCompositionError(
            "Fleet composition cannot be None or empty. A complete 100% vehicle "
            "mix distribution is required."
        )

    # Check for unknown vehicle types
    unknown_types = set(fleet_mix.keys()) - set(valid_types)
    if unknown_types:
        raise FleetCompositionError(
            f"Fleet composition contains unknown vehicle type IDs: {sorted(unknown_types)}. "
            f"Allowed types are: {list(valid_types)}."
        )

    # Check for non-positive or invalid shares
    for vtype, share in fleet_mix.items():
        if not isinstance(share, (int, float)):
            raise FleetCompositionError(
                f"Fleet share for '{vtype}' must be a numeric float, got {type(share)}."
            )
        if share <= 0.0:
            raise FleetCompositionError(
                f"Fleet share for '{vtype}' must be strictly positive, got {share}."
            )

    total_sum = sum(fleet_mix.values())

    # Detect if user passed values in percentage format (e.g. sum is near 100)
    # vs decimal fraction (sum is near 1.0)
    if total_sum > 1.5:
        expected_sum = 100.0
        pct_value = total_sum
    else:
        expected_sum = 1.0
        pct_value = total_sum * 100.0

    if abs(total_sum - expected_sum) > tolerance:
        raise FleetCompositionError(
            f"Incomplete fleet composition: shares sum to {total_sum:.4f} ({pct_value:.1f}%), "
            f"expected exactly {expected_sum} (100%). Incomplete fleet percentages cannot be "
            f"accepted without inventing or silently normalizing values. Awaiting P1 confirmation "
            f"of complete 100% distribution across all six vehicle types (car, bike, auto, bus, truck, bicycle)."
        )


def validate_turning_split(
    turning_split: Dict[str, float],
    tolerance: float = 1e-4,
) -> None:
    """
    Validates turning movement proportions (left, straight, right).

    Raises
    ------
    RouteValidationError
        If keys are missing, values are negative or non-numeric, or sum != 1.0.
    """
    required_movements = {"left", "straight", "right"}
    if set(turning_split.keys()) != required_movements:
        raise RouteValidationError(
            f"Turning split must specify exactly {required_movements}, got: {set(turning_split.keys())}"
        )

    for m, val in turning_split.items():
        if not isinstance(val, (int, float)) or isinstance(val, bool) or val < 0.0:
            raise RouteValidationError(
                f"Turning proportion for '{m}' must be non-negative numeric, got {val}."
            )

    total_sum = sum(turning_split.values())
    if abs(total_sum - 1.0) > tolerance:
        raise RouteValidationError(
            f"Turning split must sum to 1.0 (100%), got {total_sum:.4f}."
        )


def validate_movements(
    movements: Dict[str, Dict[str, str]],
    inflow_edges: Sequence[str],
    outflow_edges: Sequence[str],
) -> None:
    """
    Validates that every inflow approach has verified left, straight, and right connections.

    Raises
    ------
    RouteValidationError
        If any inflow edge or turn movement is missing or points to an invalid edge.
    """
    for in_edge in inflow_edges:
        if in_edge not in movements:
            raise RouteValidationError(f"Inflow edge '{in_edge}' missing from movements map.")
        edge_turns = movements[in_edge]
        for m in ("left", "straight", "right"):
            if m not in edge_turns:
                raise RouteValidationError(
                    f"Movement '{m}' missing for inflow edge '{in_edge}'."
                )
            target = edge_turns[m]
            if target not in outflow_edges:
                raise RouteValidationError(
                    f"Invalid target edge '{target}' for {in_edge} {m} turn. "
                    f"Must be one of {list(outflow_edges)}."
                )


# ==============================================================================
# Demand Generation Core Logic
# ==============================================================================

def generate_scenario_demand(
    scenario_id: str,
    seed: int,
    fleet_mix: Optional[Dict[str, float]] = None,
    config: Optional[RouteGeneratorConfig] = None,
    config_path: Optional[Union[str, Path]] = None,
    turning_split: Optional[Dict[str, float]] = None,
) -> List[VehicleDeparture]:
    """
    Generates a deterministic, chronologically ordered list of vehicle departures.

    Parameters
    ----------
    scenario_id : str
        Scenario identifier ('S1', 'S2', 'S3', 'S4').
    seed : int
        Master random seed for matched-seed evaluation (e.g., 42, 101, 202).
    fleet_mix : dict of str to float, optional
        Vehicle class proportions (must sum to 1.0). If None, uses provisional mix
        which triggers FleetCompositionError awaiting P1 clarification.
    config : RouteGeneratorConfig, optional
        Simulation and network configuration parameters. If None, loaded from YAML.
    config_path : str or Path, optional
        Path to experiment YAML file if loading dynamically.
    turning_split : dict of str to float, optional
        Custom turning movement proportions (must sum to 1.0).

    Returns
    -------
    list of VehicleDeparture
        Chronologically sorted vehicle departures with tagged cohorts.
    """
    # 1. Resolve configuration from YAML if not provided
    if config is None:
        cfg_file = Path(config_path or "configs/experiment.yaml")
        if cfg_file.is_file():
            config = RouteGeneratorConfig.from_yaml(cfg_file)
        else:
            config = RouteGeneratorConfig()

    if scenario_id not in config.scenario_multipliers:
        raise RouteValidationError(
            f"Unknown scenario '{scenario_id}'. Supported scenarios: "
            f"{list(config.scenario_multipliers.keys())}"
        )

    # 2. Comprehensive input validation
    # If no fleet mix supplied, evaluate provisional proposed mix (which fails validation)
    active_fleet_mix = fleet_mix if fleet_mix is not None else PROVISIONAL_UNRESOLVED_FLEET_MIX
    validate_fleet_composition(active_fleet_mix, config.valid_vehicle_types)

    active_turning_split = turning_split
    if active_turning_split is None:
        if config.scenario_turning_splits and scenario_id in config.scenario_turning_splits:
            active_turning_split = config.scenario_turning_splits[scenario_id]
        else:
            active_turning_split = config.turning_split

    validate_turning_split(active_turning_split)
    validate_movements(config.movements, config.inflow_edges, config.outflow_edges)

    multiplier = config.scenario_multipliers[scenario_id]
    hourly_demand_per_approach = config.baseline_demand_per_approach * multiplier
    lambda_per_approach = hourly_demand_per_approach / 3600.0  # arrivals per second

    # Normalize fleet mix to decimal fractions
    fleet_sum = sum(active_fleet_mix.values())
    vtypes = sorted(active_fleet_mix.keys())
    vtype_weights = [active_fleet_mix[vt] / fleet_sum for vt in vtypes]

    movements_list = ["left", "straight", "right"]
    turn_weights = [active_turning_split[m] for m in movements_list]

    all_departures: List[VehicleDeparture] = []

    # 3. Generate departures per approach with independent deterministic PRNG streams
    for approach_idx, approach_edge in enumerate(config.inflow_edges):
        # Derive an independent, deterministic sub-seed per approach
        approach_seed = (seed * 10007 + approach_idx * 1009) & 0xFFFFFFFF
        rng = random.Random(approach_seed)

        current_time = 0.0
        vehicle_counter = 0

        while True:
            # Poisson inter-arrival time: delta_t = -ln(1 - U) / lambda
            inter_arrival = rng.expovariate(lambda_per_approach)
            current_time += inter_arrival

            # Strict cutoff: NO vehicles generated during Drain period (4200s to 5100s)
            if current_time >= config.max_injection_time:
                break

            depart_time = round(current_time, 2)
            vehicle_counter += 1

            # Sample movement and target edge
            chosen_movement = rng.choices(movements_list, weights=turn_weights, k=1)[0]
            target_edge = config.movements[approach_edge][chosen_movement]
            route_id = ROUTE_ID_MAP[(approach_edge, chosen_movement)]

            # Sample vehicle type
            chosen_vtype = rng.choices(vtypes, weights=vtype_weights, k=1)[0]

            # Construct clean, readable vehicle ID
            clean_edge_tag = approach_edge.replace("-", "")
            veh_id = f"veh_{clean_edge_tag}_{vehicle_counter:05d}"

            # Classify cohort mathematically
            cohort = classify_vehicle_cohort(
                depart_time,
                warm_up_seconds=config.warm_up_seconds,
                evaluation_seconds=config.evaluation_seconds,
            )

            all_departures.append(
                VehicleDeparture(
                    veh_id=veh_id,
                    depart_time=depart_time,
                    veh_type=chosen_vtype,
                    from_edge=approach_edge,
                    to_edge=target_edge,
                    route_id=route_id,
                    movement=chosen_movement,
                    cohort=cohort,
                )
            )

    # 4. Sort all departures globally by timestamp ascending with tie-breaking on ID
    # SUMO requires departures in .rou.xml to be strictly non-decreasing
    all_departures.sort(key=lambda v: (v.depart_time, v.veh_id))

    return all_departures


# ==============================================================================
# XML Serialization
# ==============================================================================

def write_route_file(
    departures: List[VehicleDeparture],
    output_path: Union[str, Path],
    scenario_id: str,
    seed: int,
    config: Optional[RouteGeneratorConfig] = None,
) -> Path:
    """
    Serializes departures and all 12 LHT routes into a valid SUMO route XML file.
    Includes `<param key="cohort" value="..."/>` on each vehicle for robust identification.

    Parameters
    ----------
    departures : list of VehicleDeparture
        Sorted vehicle departure records.
    output_path : str or Path
        Destination file path.
    scenario_id : str
        Scenario ID for metadata tracking.
    seed : int
        Random seed for metadata tracking.
    config : RouteGeneratorConfig, optional
        Configuration used for generation.

    Returns
    -------
    Path
        Absolute path to the created route file.
    """
    if config is None:
        config = RouteGeneratorConfig()

    out_file = Path(output_path).resolve()
    out_file.parent.mkdir(parents=True, exist_ok=True)

    lines: List[str] = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<!-- ============================================================================== -->',
        f'<!-- SIGNALSIM-INDIA: Deterministic Route File -->',
        f'<!-- Scenario: {scenario_id} | Multiplier: {config.scenario_multipliers.get(scenario_id, 1.0):.2f} | Seed: {seed} -->',
        f'<!-- Total Vehicles: {len(departures)} | Injection Window: 0.0s to {config.max_injection_time:.1f}s -->',
        f'<!-- Drain Period: {config.max_injection_time:.1f}s to {config.total_simulation_time:.1f}s (No departures) -->',
        '<!-- ============================================================================== -->',
        '<routes xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/routes_file.xsd">',
        '',
        '    <!-- 12 Valid LHT Intersection Routes -->',
    ]

    # Pre-declare all 12 valid LHT routes
    for (in_edge, movement), route_id in sorted(ROUTE_ID_MAP.items(), key=lambda x: x[1]):
        out_edge = config.movements[in_edge][movement]
        lines.append(f'    <route id="{route_id}" edges="{in_edge} {out_edge}"/>')

    lines.append('')
    lines.append('    <!-- Chronological Deterministic Vehicle Departures -->')

    for veh in departures:
        lines.append(
            f'    <vehicle id="{veh.veh_id}" type="{veh.veh_type}" '
            f'depart="{veh.depart_time:.2f}" route="{veh.route_id}">'
        )
        lines.append(f'        <param key="cohort" value="{veh.cohort}"/>')
        lines.append('    </vehicle>')

    lines.append('</routes>')
    lines.append('')

    content = "\n".join(lines)
    out_file.write_text(content, encoding="utf-8")
    return out_file


def generate_route_file(
    scenario_id: str,
    seed: int,
    fleet_mix: Optional[Dict[str, float]] = None,
    output_path: Optional[Union[str, Path]] = None,
    config: Optional[RouteGeneratorConfig] = None,
    config_path: Optional[Union[str, Path]] = None,
    turning_split: Optional[Dict[str, float]] = None,
) -> Path:
    """
    Convenience function to generate and write a single deterministic route file.

    Parameters
    ----------
    scenario_id : str
        'S1', 'S2', 'S3', or 'S4'.
    seed : int
        Random seed integer.
    fleet_mix : dict of str to float, optional
        Vehicle proportions (must sum to 1.0). If None, provisional mix is evaluated.
    output_path : str or Path, optional
        Target file path. Defaults to simulation/routes/route_{scenario_id}_seed{seed}.rou.xml.
    config : RouteGeneratorConfig, optional
        Configuration settings.
    config_path : str or Path, optional
        Path to experiment YAML.
    turning_split : dict of str to float, optional
        Turning movement split.

    Returns
    -------
    Path
        Path to the generated route XML file.
    """
    if config is None:
        cfg_file = Path(config_path or "configs/experiment.yaml")
        if cfg_file.is_file():
            config = RouteGeneratorConfig.from_yaml(cfg_file)
        else:
            config = RouteGeneratorConfig()

    if output_path is None:
        output_path = Path("simulation/routes") / f"route_{scenario_id}_seed{seed}.rou.xml"

    departures = generate_scenario_demand(
        scenario_id=scenario_id,
        seed=seed,
        fleet_mix=fleet_mix,
        config=config,
        turning_split=turning_split,
    )

    return write_route_file(
        departures=departures,
        output_path=output_path,
        scenario_id=scenario_id,
        seed=seed,
        config=config,
    )


def generate_all_routes(
    fleet_mix: Optional[Dict[str, float]] = None,
    output_dir: Union[str, Path] = "simulation/routes",
    config: Optional[RouteGeneratorConfig] = None,
    config_path: Optional[Union[str, Path]] = None,
    scenarios: Optional[Sequence[str]] = None,
    seeds: Optional[Sequence[int]] = None,
) -> List[Path]:
    """
    Generates all scenario-seed combination route files (e.g. 4 scenarios * 5 seeds = 20 files).

    Parameters
    ----------
    fleet_mix : dict of str to float, optional
        Vehicle class proportions (must sum to 1.0).
    output_dir : str or Path
        Target folder for route files.
    config : RouteGeneratorConfig, optional
        Configuration settings.
    config_path : str or Path, optional
        Path to experiment YAML.
    scenarios : sequence of str, optional
        List of scenario IDs. Defaults to S1-S4.
    seeds : sequence of int, optional
        List of seeds. Defaults to (42, 101, 202, 303, 404).

    Returns
    -------
    list of Path
        List of generated file paths.
    """
    if config is None:
        cfg_file = Path(config_path or "configs/experiment.yaml")
        if cfg_file.is_file():
            config = RouteGeneratorConfig.from_yaml(cfg_file)
        else:
            config = RouteGeneratorConfig()

    active_scenarios = scenarios or list(config.scenario_multipliers.keys())
    active_seeds = seeds or config.evaluation_seeds
    out_dir = Path(output_dir)

    generated_paths: List[Path] = []
    for sc in active_scenarios:
        for sd in active_seeds:
            dest = out_dir / f"route_{sc}_seed{sd}.rou.xml"
            path = generate_route_file(
                scenario_id=sc,
                seed=sd,
                fleet_mix=fleet_mix,
                output_path=dest,
                config=config,
            )
            generated_paths.append(path)

    return generated_paths
