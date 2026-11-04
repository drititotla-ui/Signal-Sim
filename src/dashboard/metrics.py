"""
Metrics Computation and Aggregation for SIGNALSIM-INDIA Dashboard Backend (M04.1).

Computes run-level and seed-aggregated performance statistics (mean, std, valid counts)
strictly preserving missing values and isolating controllers and scenarios.
"""

from typing import Any, Dict, List, Optional, Union
import numpy as np
import pandas as pd


# Supported core M03 evaluation and operational metrics
CORE_METRIC_COLUMNS = [
    "mean_travel_time",
    "mean_waiting_time",
    "mean_time_loss",
    "throughput_vph",
    "completed_vehicles",
    "unfinished_vehicles",
    "simulation_duration_seconds",
    "wall_clock_duration_seconds",
]


def compute_run_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """
    Extracts structured run-level metrics for all runs in the DataFrame.
    Preserves exact run identifiers, seed, status, and raw metric values.
    """
    if df.empty:
        return df.copy()

    desired_cols = [
        "run_id",
        "controller_id",
        "scenario_id",
        "seed",
        "status",
        "error_message",
    ] + [c for c in CORE_METRIC_COLUMNS if c in df.columns]

    available = [c for c in desired_cols if c in df.columns]
    return df[available].copy()


def aggregate_metrics(
    df: pd.DataFrame,
    group_by: Optional[List[str]] = None,
    metrics: Optional[List[str]] = None,
    only_successful: bool = True,
    expected_seeds_count: int = 5,
) -> pd.DataFrame:
    """
    Aggregates performance metrics across available seeds without mixing controllers or scenarios.

    Aggregation Rules:
    1. Only successful runs are included in performance calculations by default.
    2. Missing values (NaN) are strictly excluded from calculations and NEVER converted to zero.
    3. Sample standard deviation (ddof=1) is computed when observation count > 1; otherwise NaN.
    4. Reports observation counts per metric to distinguish partial results from full benchmarks.

    Parameters
    ----------
    df : pd.DataFrame
        Source results DataFrame.
    group_by : list of str, optional
        Grouping keys, defaults to ['controller_id', 'scenario_id'].
    metrics : list of str, optional
        Subset of metrics to aggregate (defaults to CORE_METRIC_COLUMNS).
    only_successful : bool, default True
        Whether to filter out non-SUCCESS runs before computing metrics.
    expected_seeds_count : int, default 5
        Target seed count to determine benchmark completeness flag.

    Returns
    -------
    pd.DataFrame
        Aggregated summary DataFrame with '<metric>_mean', '<metric>_std',
        and '<metric>_count' columns alongside completeness flags.
    """
    if df.empty:
        return pd.DataFrame()

    keys = group_by or ["controller_id", "scenario_id"]
    target_metrics = [m for m in (metrics or CORE_METRIC_COLUMNS) if m in df.columns]

    data = df[df["status"] == "SUCCESS"].copy() if only_successful else df.copy()
    if data.empty:
        return pd.DataFrame()

    rows: List[Dict[str, Any]] = []

    for group_vals, grp in data.groupby(keys, observed=True):
        if not isinstance(group_vals, tuple):
            group_vals = (group_vals,)

        row_dict: Dict[str, Any] = dict(zip(keys, group_vals))

        # Record available seeds in this cohort
        valid_seeds = sorted(int(s) for s in grp["seed"].dropna().unique())
        seed_count = len(valid_seeds)
        row_dict["seeds_available"] = valid_seeds
        row_dict["seed_count"] = seed_count
        row_dict["is_complete_cohort"] = bool(seed_count >= expected_seeds_count)

        for m in target_metrics:
            series = pd.to_numeric(grp[m], errors="coerce").dropna()
            count = len(series)

            if count > 0:
                row_dict[f"{m}_mean"] = round(float(series.mean()), 2)
                row_dict[f"{m}_std"] = round(float(series.std(ddof=1)), 2) if count > 1 else np.nan
                row_dict[f"{m}_count"] = int(count)
                row_dict[f"{m}_min"] = round(float(series.min()), 2)
                row_dict[f"{m}_max"] = round(float(series.max()), 2)
            else:
                row_dict[f"{m}_mean"] = np.nan
                row_dict[f"{m}_std"] = np.nan
                row_dict[f"{m}_count"] = 0
                row_dict[f"{m}_min"] = np.nan
                row_dict[f"{m}_max"] = np.nan

        rows.append(row_dict)

    return pd.DataFrame(rows)
