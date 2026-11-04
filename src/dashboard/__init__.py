"""
SIGNALSIM-INDIA Dashboard Package (M04.1).

Exports the DashboardService facade and underlying data processing modules.
"""

from src.dashboard.comparison import (
    calculate_percentage_improvement,
    compare_controllers_aggregate,
    compare_controllers_by_seed,
)
from src.dashboard.dashboard_service import DashboardService
from src.dashboard.data_loader import (
    DashboardDataError,
    DuplicateRunError,
    EmptyDataFileError,
    MalformedDataError,
    MissingDataFileError,
    get_empty_summary_dataframe,
    load_master_summary,
)
from src.dashboard.data_processor import (
    check_benchmark_completeness,
    filter_results,
    get_available_controllers,
    get_available_scenarios,
    get_available_seeds,
    get_available_statuses,
)
from src.dashboard.metrics import (
    aggregate_metrics,
    compute_run_metrics,
)

__all__ = [
    "DashboardService",
    "load_master_summary",
    "filter_results",
    "get_available_controllers",
    "get_available_scenarios",
    "get_available_seeds",
    "get_available_statuses",
    "check_benchmark_completeness",
    "aggregate_metrics",
    "compute_run_metrics",
    "compare_controllers_by_seed",
    "compare_controllers_aggregate",
    "calculate_percentage_improvement",
    "get_empty_summary_dataframe",
    "DashboardDataError",
    "MissingDataFileError",
    "EmptyDataFileError",
    "MalformedDataError",
    "DuplicateRunError",
]
