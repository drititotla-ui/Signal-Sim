"""
Deterministic route and traffic demand generator package for SIGNALSIM-INDIA.
"""

from src.routes.generator import (
    FleetCompositionError,
    RouteValidationError,
    RouteGeneratorConfig,
    VehicleDeparture,
    LHT_MOVEMENTS,
    DEFAULT_TURNING_SPLIT,
    VALID_VEHICLE_TYPES,
    PROVISIONAL_UNRESOLVED_FLEET_MIX,
    classify_vehicle_cohort,
    is_evaluation_cohort,
    add_cohort_column,
    load_route_generator_config,
    generate_scenario_demand,
    write_route_file,
    generate_route_file,
    generate_all_routes,
    validate_fleet_composition,
    validate_turning_split,
    validate_movements,
)

__all__ = [
    "FleetCompositionError",
    "RouteValidationError",
    "RouteGeneratorConfig",
    "VehicleDeparture",
    "LHT_MOVEMENTS",
    "DEFAULT_TURNING_SPLIT",
    "VALID_VEHICLE_TYPES",
    "PROVISIONAL_UNRESOLVED_FLEET_MIX",
    "classify_vehicle_cohort",
    "is_evaluation_cohort",
    "add_cohort_column",
    "load_route_generator_config",
    "generate_scenario_demand",
    "write_route_file",
    "generate_route_file",
    "generate_all_routes",
    "validate_fleet_composition",
    "validate_turning_split",
    "validate_movements",
]
