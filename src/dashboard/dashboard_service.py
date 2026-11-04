"""
Dashboard Service Interface for SIGNALSIM-INDIA (M04.1).

High-level application facade providing structured data, KPIs, aggregations,
and controller/scenario comparisons directly for the Streamlit dashboard layer.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import numpy as np
import pandas as pd

from src.dashboard.comparison import (
    compare_controllers_aggregate,
    compare_controllers_by_seed,
)
from src.dashboard.data_loader import (
    DashboardDataError,
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


class DashboardService:
    """
    Facade service encapsulating data loading, filtering, metrics computation,
    and comparative evaluations for the SIGNALSIM-INDIA dashboard.
    """

    def __init__(self, data_path: Optional[Union[str, Path]] = None):
        self.data_path = Path(data_path) if data_path else Path("results/summaries/master_summary.csv")
        self._cached_df: Optional[pd.DataFrame] = None

    def load_data(self, refresh: bool = False) -> pd.DataFrame:
        """
        Loads and caches results data. If refresh=True, re-reads from disk.
        """
        if self._cached_df is None or refresh:
            self._cached_df = load_master_summary(self.data_path)
        return self._cached_df.copy()

    def get_overview_kpis(self) -> Dict[str, Any]:
        """
        Calculates high-level dashboard KPIs:
        - Total runs, completed runs, failed runs.
        - Overall mean travel time and throughput across successful runs.
        - Available controller and scenario counts.
        """
        df = self.load_data()
        if df.empty:
            return {
                "total_runs": 0,
                "successful_runs": 0,
                "failed_runs": 0,
                "controllers_count": 0,
                "scenarios_count": 0,
                "mean_travel_time": np.nan,
                "mean_waiting_time": np.nan,
                "mean_time_loss": np.nan,
                "mean_throughput_vph": np.nan,
            }

        success_df = df[df["status"] == "SUCCESS"]

        def _safe_mean(series_name: str) -> float:
            if series_name in success_df.columns:
                s = pd.to_numeric(success_df[series_name], errors="coerce").dropna()
                return round(float(s.mean()), 2) if len(s) > 0 else np.nan
            return np.nan

        return {
            "total_runs": len(df),
            "successful_runs": len(success_df),
            "failed_runs": int((df["status"] != "SUCCESS").sum()),
            "controllers_count": len(self.get_available_controllers()),
            "scenarios_count": len(self.get_available_scenarios()),
            "mean_travel_time": _safe_mean("mean_travel_time"),
            "mean_waiting_time": _safe_mean("mean_waiting_time"),
            "mean_time_loss": _safe_mean("mean_time_loss"),
            "mean_throughput_vph": _safe_mean("throughput_vph"),
        }

    def get_available_controllers(self) -> List[str]:
        """Returns sorted list of controllers with data actually present."""
        df = self.load_data()
        return get_available_controllers(df)

    def get_available_scenarios(self) -> List[str]:
        """Returns sorted list of scenarios present in results."""
        df = self.load_data()
        return get_available_scenarios(df)

    def get_available_seeds(self) -> List[int]:
        """Returns sorted list of seeds present in results."""
        df = self.load_data()
        return get_available_seeds(df)

    def get_available_statuses(self) -> List[str]:
        """Returns sorted list of run statuses present in results."""
        df = self.load_data()
        return get_available_statuses(df)

    def get_run_level_results(
        self,
        controller: Optional[Union[str, List[str]]] = None,
        scenario: Optional[Union[str, List[str]]] = None,
        seed: Optional[Union[int, List[int]]] = None,
        status: Optional[Union[str, List[str]]] = "SUCCESS",
    ) -> pd.DataFrame:
        """Retrieves filtered run-level result records."""
        df = self.load_data()
        filtered = filter_results(
            df=df,
            controller_id=controller,
            scenario_id=scenario,
            seed=seed,
            status=status,
        )
        return compute_run_metrics(filtered)

    def get_aggregated_metrics(
        self,
        controller: Optional[Union[str, List[str]]] = None,
        scenario: Optional[Union[str, List[str]]] = None,
    ) -> pd.DataFrame:
        """
        Retrieves seed-aggregated metrics grouped by controller and scenario.
        Excludes failed runs and never mixes controllers or scenarios.
        """
        df = self.load_data()
        filtered = filter_results(
            df=df,
            controller_id=controller,
            scenario_id=scenario,
        )
        return aggregate_metrics(filtered, group_by=["controller_id", "scenario_id"])

    def get_controller_comparison(
        self,
        candidate_controller: str,
        baseline_controller: str = "fixed_time",
        scenario: Optional[str] = None,
        by_seed: bool = False,
    ) -> pd.DataFrame:
        """
        Compares candidate controller performance relative to baseline.

        Parameters
        ----------
        candidate_controller : str
            Name of candidate controller (e.g. 'max_pressure' or 'ppo').
        baseline_controller : str, default 'fixed_time'
            Baseline controller for relative performance.
        scenario : str, optional
            Specific scenario filter (e.g. 'S1').
        by_seed : bool, default False
            If True, returns matched seed-level deltas; if False, returns scenario aggregates.
        """
        df = self.load_data()
        if by_seed:
            return compare_controllers_by_seed(
                df=df,
                candidate_controller=candidate_controller,
                baseline_controller=baseline_controller,
                scenario_id=scenario,
            )
        else:
            return compare_controllers_aggregate(
                df=df,
                candidate_controller=candidate_controller,
                baseline_controller=baseline_controller,
                scenario_id=scenario,
            )

    def get_scenario_comparison(
        self,
        controller: Optional[Union[str, List[str]]] = None,
    ) -> pd.DataFrame:
        """
        Compares performance across traffic demand scenarios (S1 through S4).
        """
        df = self.load_data()
        filtered = filter_results(df=df, controller_id=controller)
        agg = aggregate_metrics(filtered, group_by=["scenario_id", "controller_id"])
        if not agg.empty and "scenario_id" in agg.columns:
            return agg.sort_values(by=["scenario_id", "controller_id"]).reset_index(drop=True)
        return agg

    def get_benchmark_status(
        self,
        expected_controllers: Optional[List[str]] = None,
        expected_scenarios: Optional[List[str]] = None,
        expected_seeds: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """Evaluates whether current results represent a complete or partial benchmark."""
        df = self.load_data()
        return check_benchmark_completeness(
            df=df,
            expected_controllers=expected_controllers,
            expected_scenarios=expected_scenarios,
            expected_seeds=expected_seeds,
        )
