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



def compare_safety_benchmarks(
    original_df: pd.DataFrame,
    safety_df: pd.DataFrame,
) -> Dict[str, Any]:
    """
    Computes rigorous side-by-side comparative analysis between the Original Benchmark
    (1s All-Red, 68s Fixed-Time cycle) and the Retimed Safety Benchmark
    (3s All-Red, 72s Fixed-Time cycle, IRC:93-1985 standard).

    Parameters
    ----------
    original_df : pd.DataFrame
        Run records from the original benchmark dataset (results/summaries/).
    safety_df : pd.DataFrame
        Run records from the retimed safety benchmark dataset (results/safety/summaries/).

    Returns
    -------
    dict
        Structured comparison containing controller_summary, scenario_summary,
        overall_kpis, and safety_metadata.
    """
    if original_df.empty or safety_df.empty:
        return {
            "controller_summary": pd.DataFrame(),
            "scenario_summary": pd.DataFrame(),
            "overall_kpis": {},
            "safety_metadata": {},
        }

    # Success filter
    orig_succ = original_df[original_df["status"] == "SUCCESS"].copy()
    safe_succ = safety_df[safety_df["status"] == "SUCCESS"].copy()

    ctrl_order = ["fixed_time", "max_pressure", "ppo_v6"]
    ctrl_labels = {
        "fixed_time": "Fixed-Time",
        "max_pressure": "Max-Pressure",
        "ppo_v6": "PPO V6",
    }

    controller_rows = []
    for c in ctrl_order:
        o = orig_succ[orig_succ["controller_id"] == c]
        s = safe_succ[safe_succ["controller_id"] == c]
        if o.empty or s.empty:
            continue

        col_orig = int(o["collisions"].sum()) if "collisions" in o.columns else 0
        col_safe = int(s["collisions"].sum()) if "collisions" in s.columns else 0
        col_diff = col_safe - col_orig
        col_red_pct = round(((col_orig - col_safe) / col_orig * 100.0), 2) if col_orig > 0 else 0.0

        tt_orig = round(float(o["mean_travel_time"].mean()), 2)
        tt_safe = round(float(s["mean_travel_time"].mean()), 2)
        tt_pct = round(((tt_safe - tt_orig) / tt_orig * 100.0), 2) if tt_orig > 0 else 0.0

        wt_orig = round(float(o["mean_waiting_time"].mean()), 2)
        wt_safe = round(float(s["mean_waiting_time"].mean()), 2)
        wt_pct = round(((wt_safe - wt_orig) / wt_orig * 100.0), 2) if wt_orig > 0 else 0.0

        tl_orig = round(float(o["mean_time_loss"].mean()), 2)
        tl_safe = round(float(s["mean_time_loss"].mean()), 2)
        tl_pct = round(((tl_safe - tl_orig) / tl_orig * 100.0), 2) if tl_orig > 0 else 0.0

        tp_orig = round(float(o["throughput_vph"].mean()), 2)
        tp_safe = round(float(s["throughput_vph"].mean()), 2)
        tp_pct = round(((tp_safe - tp_orig) / tp_orig * 100.0), 2) if tp_orig > 0 else 0.0

        controller_rows.append({
            "controller_id": c,
            "controller_name": ctrl_labels.get(c, c),
            "travel_time_orig": tt_orig,
            "travel_time_safe": tt_safe,
            "travel_time_pct_change": tt_pct,
            "waiting_time_orig": wt_orig,
            "waiting_time_safe": wt_safe,
            "waiting_time_pct_change": wt_pct,
            "time_loss_orig": tl_orig,
            "time_loss_safe": tl_safe,
            "time_loss_pct_change": tl_pct,
            "throughput_orig": tp_orig,
            "throughput_safe": tp_safe,
            "throughput_pct_change": tp_pct,
            "collisions_orig": col_orig,
            "collisions_safe": col_safe,
            "collisions_diff": col_diff,
            "collision_reduction_pct": col_red_pct,
        })

    controller_summary = pd.DataFrame(controller_rows)

    # Scenario breakdown
    scenarios = ["S1", "S2", "S3", "S4"]
    scenario_rows = []
    for sc in scenarios:
        for c in ctrl_order:
            o_sc = orig_succ[(orig_succ["scenario_id"] == sc) & (orig_succ["controller_id"] == c)]
            s_sc = safe_succ[(safe_succ["scenario_id"] == sc) & (safe_succ["controller_id"] == c)]
            if o_sc.empty or s_sc.empty:
                continue

            c_o = int(o_sc["collisions"].sum()) if "collisions" in o_sc.columns else 0
            c_s = int(s_sc["collisions"].sum()) if "collisions" in s_sc.columns else 0
            c_red = round(((c_o - c_s) / c_o * 100.0), 2) if c_o > 0 else 0.0

            scenario_rows.append({
                "scenario_id": sc,
                "controller_id": c,
                "controller_name": ctrl_labels.get(c, c),
                "travel_time_orig": round(float(o_sc["mean_travel_time"].mean()), 2),
                "travel_time_safe": round(float(s_sc["mean_travel_time"].mean()), 2),
                "throughput_orig": round(float(o_sc["throughput_vph"].mean()), 2),
                "throughput_safe": round(float(s_sc["throughput_vph"].mean()), 2),
                "collisions_orig": c_o,
                "collisions_safe": c_s,
                "collisions_diff": c_s - c_o,
                "collision_reduction_pct": c_red,
            })

    scenario_summary = pd.DataFrame(scenario_rows)

    tot_orig_col = int(controller_summary["collisions_orig"].sum()) if not controller_summary.empty else 0
    tot_safe_col = int(controller_summary["collisions_safe"].sum()) if not controller_summary.empty else 0
    tot_avoided = tot_orig_col - tot_safe_col
    tot_reduction_pct = round((tot_avoided / tot_orig_col * 100.0), 2) if tot_orig_col > 0 else 0.0

    overall_kpis = {
        "total_collisions_orig": tot_orig_col,
        "total_collisions_safe": tot_safe_col,
        "total_collisions_avoided": tot_avoided,
        "overall_collision_reduction_pct": tot_reduction_pct,
        "mean_travel_time_orig": round(float(orig_succ["mean_travel_time"].mean()), 2),
        "mean_travel_time_safe": round(float(safe_succ["mean_travel_time"].mean()), 2),
        "mean_throughput_orig": round(float(orig_succ["throughput_vph"].mean()), 2),
        "mean_throughput_safe": round(float(safe_succ["throughput_vph"].mean()), 2),
    }

    safety_metadata = {
        "all_red_original": "1.0s",
        "all_red_safety": "3.0s",
        "cycle_original": "68s",
        "cycle_safety": "72s",
        "standard": "IRC:93-1985 Section 5",
        "disclosure": (
            "Safety-Retimed Configuration: The intergreen All-Red clearance interval "
            "was increased from 1.0s to 3.0s to provide adequate clearance time for slow heavy "
            "vehicles (buses and trucks) traversing the 30m intersection, altering the Fixed-Time "
            "cycle length from 68s to 72s. Vehicle routes, demand multipliers, and RL policy "
            "weights remain identical."
        ),
    }

    return {
        "controller_summary": controller_summary,
        "scenario_summary": scenario_summary,
        "overall_kpis": overall_kpis,
        "safety_metadata": safety_metadata,
    }
