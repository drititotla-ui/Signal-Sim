"""
Controller Comparison Engine for SIGNALSIM-INDIA Dashboard Backend (M04.1).

Computes matched-seed relative performance improvements across identical scenarios,
handles edge-case baselines safely, and assesses sample size validity.
"""

from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd


# Metric orientation definitions
LOWER_IS_BETTER_METRICS = [
    "mean_travel_time",
    "mean_waiting_time",
    "mean_time_loss",
]

HIGHER_IS_BETTER_METRICS = [
    "throughput_vph",
    "completed_vehicles",
]


def calculate_percentage_improvement(
    metric_name: str,
    baseline_value: float,
    candidate_value: float,
) -> float:
    """
    Computes percentage improvement of candidate relative to baseline.

    Formulas:
    - Lower is better (travel time, waiting time, time loss):
      ((baseline - candidate) / baseline) * 100
    - Higher is better (throughput, completed vehicles):
      ((candidate - baseline) / baseline) * 100

    A positive value represents a performance improvement in both cases.
    Returns np.nan if baseline is zero, negative, or missing.
    """
    if pd.isna(baseline_value) or pd.isna(candidate_value):
        return np.nan

    b = float(baseline_value)
    c = float(candidate_value)

    if b <= 0.0:
        # Cannot compute meaningful relative percentage over zero or negative baseline
        return np.nan

    if metric_name in LOWER_IS_BETTER_METRICS:
        return ((b - c) / b) * 100.0
    elif metric_name in HIGHER_IS_BETTER_METRICS:
        return ((c - b) / b) * 100.0
    else:
        # Default fallback to lower-is-better
        return ((b - c) / b) * 100.0


def compare_controllers_by_seed(
    df: pd.DataFrame,
    candidate_controller: str,
    baseline_controller: str = "fixed_time",
    scenario_id: Optional[str] = None,
    metrics: Optional[List[str]] = None,
) -> pd.DataFrame:
    """
    Computes seed-by-seed paired comparisons between candidate and baseline controllers.

    Strictly matches runs by scenario_id and random seed.
    """
    if df.empty:
        return pd.DataFrame()

    target_metrics = metrics or ["mean_travel_time", "mean_waiting_time", "mean_time_loss", "throughput_vph"]

    # Filter to successful runs
    success_df = df[df["status"] == "SUCCESS"].copy()
    if scenario_id is not None:
        success_df = success_df[success_df["scenario_id"] == scenario_id]

    base_df = success_df[success_df["controller_id"] == baseline_controller]
    cand_df = success_df[success_df["controller_id"] == candidate_controller]

    if base_df.empty or cand_df.empty:
        return pd.DataFrame()

    # Merge on (scenario_id, seed) to guarantee matched conditions
    merge_cols = ["scenario_id", "seed"]
    merged = pd.merge(
        base_df,
        cand_df,
        on=merge_cols,
        suffixes=("_baseline", "_candidate"),
    )

    if merged.empty:
        return pd.DataFrame()

    rows: List[Dict[str, Any]] = []
    for _, row in merged.iterrows():
        entry: Dict[str, Any] = {
            "scenario_id": row["scenario_id"],
            "seed": int(row["seed"]),
            "baseline_controller": baseline_controller,
            "candidate_controller": candidate_controller,
        }

        for m in target_metrics:
            b_val = row.get(f"{m}_baseline")
            c_val = row.get(f"{m}_candidate")
            entry[f"{m}_baseline"] = round(float(b_val), 2) if pd.notna(b_val) else np.nan
            entry[f"{m}_candidate"] = round(float(c_val), 2) if pd.notna(c_val) else np.nan

            if pd.notna(b_val) and pd.notna(c_val):
                diff = float(b_val) - float(c_val) if m in LOWER_IS_BETTER_METRICS else float(c_val) - float(b_val)
                pct = calculate_percentage_improvement(m, float(b_val), float(c_val))
                entry[f"{m}_diff"] = round(diff, 2)
                entry[f"{m}_pct_improvement"] = round(pct, 2)
            else:
                entry[f"{m}_diff"] = np.nan
                entry[f"{m}_pct_improvement"] = np.nan

        rows.append(entry)

    return pd.DataFrame(rows)


def compare_controllers_aggregate(
    df: pd.DataFrame,
    candidate_controller: str,
    baseline_controller: str = "fixed_time",
    scenario_id: Optional[str] = None,
    metrics: Optional[List[str]] = None,
) -> pd.DataFrame:
    """
    Computes aggregated relative performance across matched seeds per scenario.

    Includes:
    - Mean and standard deviation of percentage improvement.
    - Number of matched observations used.
    - Paired t-statistic and sample size validity assessment.
    """
    paired_df = compare_controllers_by_seed(
        df=df,
        candidate_controller=candidate_controller,
        baseline_controller=baseline_controller,
        scenario_id=scenario_id,
        metrics=metrics,
    )

    if paired_df.empty:
        return pd.DataFrame()

    target_metrics = metrics or ["mean_travel_time", "mean_waiting_time", "mean_time_loss", "throughput_vph"]
    scenarios = sorted(paired_df["scenario_id"].unique())

    agg_rows: List[Dict[str, Any]] = []

    for sc in scenarios:
        sc_data = paired_df[paired_df["scenario_id"] == sc]
        matched_n = len(sc_data)

        entry: Dict[str, Any] = {
            "scenario_id": sc,
            "baseline_controller": baseline_controller,
            "candidate_controller": candidate_controller,
            "matched_seeds_count": matched_n,
            "is_complete_benchmark": bool(matched_n >= 5),
            "statistical_significance_evaluable": bool(matched_n >= 5),
        }

        for m in target_metrics:
            pct_col = f"{m}_pct_improvement"
            diff_col = f"{m}_diff"

            pct_series = sc_data[pct_col].dropna()
            diff_series = sc_data[diff_col].dropna()

            obs_count = len(pct_series)
            entry[f"{m}_matched_obs"] = obs_count

            if obs_count > 0:
                mean_pct = float(pct_series.mean())
                std_pct = float(pct_series.std(ddof=1)) if obs_count > 1 else np.nan
                entry[f"{m}_mean_pct_improvement"] = round(mean_pct, 2)
                entry[f"{m}_std_pct_improvement"] = round(std_pct, 2) if pd.notna(std_pct) else np.nan

                # Paired t-statistic on differences if obs_count >= 2
                if obs_count >= 2:
                    mean_diff = float(diff_series.mean())
                    std_diff = float(diff_series.std(ddof=1))
                    if std_diff > 1e-9:
                        se_diff = std_diff / np.sqrt(obs_count)
                        t_stat = mean_diff / se_diff
                        entry[f"{m}_paired_t_stat"] = round(float(t_stat), 3)
                    else:
                        entry[f"{m}_paired_t_stat"] = np.nan
                else:
                    entry[f"{m}_paired_t_stat"] = np.nan
            else:
                entry[f"{m}_mean_pct_improvement"] = np.nan
                entry[f"{m}_std_pct_improvement"] = np.nan
                entry[f"{m}_paired_t_stat"] = np.nan

        agg_rows.append(entry)

    return pd.DataFrame(agg_rows)
