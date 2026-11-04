"""
Data Processor for SIGNALSIM-INDIA Dashboard Backend (M04.1).

Provides filtering, slicing, dynamic entity discovery, and benchmark completeness
tracking over M03 simulation results.
"""

from typing import Any, Dict, List, Optional, Set, Tuple, Union
import numpy as np
import pandas as pd


# Standard benchmark dimensions agreed in P1-P2 contract
DEFAULT_EXPECTED_CONTROLLERS = ["fixed_time", "max_pressure"]
DEFAULT_EXPECTED_SCENARIOS = ["S1", "S2", "S3", "S4"]
DEFAULT_EXPECTED_SEEDS = [42, 101, 202, 303, 404]


def filter_results(
    df: pd.DataFrame,
    controller_id: Optional[Union[str, List[str]]] = None,
    scenario_id: Optional[Union[str, List[str]]] = None,
    seed: Optional[Union[int, List[int]]] = None,
    status: Optional[Union[str, List[str]]] = None,
) -> pd.DataFrame:
    """
    Filters summary DataFrame by controller, scenario, seed, and/or status.

    Parameters
    ----------
    df : pd.DataFrame
        Source simulation results DataFrame.
    controller_id : str or list of str, optional
        Filter to specific controller(s).
    scenario_id : str or list of str, optional
        Filter to specific scenario(s) (e.g. 'S1').
    seed : int or list of int, optional
        Filter to specific seed(s) (e.g. 42).
    status : str or list of str, optional
        Filter by run status (e.g. 'SUCCESS').

    Returns
    -------
    pd.DataFrame
        Filtered subset of the DataFrame.
    """
    if df.empty:
        return df.copy()

    mask = pd.Series(True, index=df.index)

    if controller_id is not None:
        c_list = [controller_id] if isinstance(controller_id, str) else list(controller_id)
        mask &= df["controller_id"].isin(c_list)

    if scenario_id is not None:
        s_list = [scenario_id] if isinstance(scenario_id, str) else list(scenario_id)
        mask &= df["scenario_id"].isin(s_list)

    if seed is not None:
        seed_list = [seed] if isinstance(seed, (int, np.integer)) else list(seed)
        mask &= df["seed"].isin(seed_list)

    if status is not None:
        st_list = [status] if isinstance(status, str) else list(status)
        mask &= df["status"].isin(st_list)

    return df[mask].copy()


def get_available_controllers(df: pd.DataFrame) -> List[str]:
    """
    Dynamically discovers unique controller IDs present in the data.
    Never hardcodes controllers (e.g. PPO appears only when actual results exist).
    """
    if df.empty or "controller_id" not in df.columns:
        return []
    valid = df["controller_id"].dropna().unique().tolist()
    return sorted(str(c) for c in valid)


def get_available_scenarios(df: pd.DataFrame) -> List[str]:
    """Dynamically discovers unique scenario IDs present in the data."""
    if df.empty or "scenario_id" not in df.columns:
        return []
    valid = df["scenario_id"].dropna().unique().tolist()
    return sorted(str(s) for s in valid)


def get_available_seeds(df: pd.DataFrame) -> List[int]:
    """Dynamically discovers unique seeds present in the data."""
    if df.empty or "seed" not in df.columns:
        return []
    valid = df["seed"].dropna().unique().tolist()
    return sorted(int(s) for s in valid)


def get_available_statuses(df: pd.DataFrame) -> List[str]:
    """Dynamically discovers unique run statuses present in the data."""
    if df.empty or "status" not in df.columns:
        return []
    valid = df["status"].dropna().unique().tolist()
    return sorted(str(st) for st in valid)


def check_benchmark_completeness(
    df: pd.DataFrame,
    expected_controllers: Optional[List[str]] = None,
    expected_scenarios: Optional[List[str]] = None,
    expected_seeds: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """
    Assesses benchmark completeness against standard or custom design dimensions.

    Parameters
    ----------
    df : pd.DataFrame
        Loaded results DataFrame.
    expected_controllers : list of str, optional
        Target controllers (defaults to ['fixed_time', 'max_pressure']).
    expected_scenarios : list of str, optional
        Target scenarios (defaults to ['S1', 'S2', 'S3', 'S4']).
    expected_seeds : list of int, optional
        Target evaluation seeds (defaults to [42, 101, 202, 303, 404]).

    Returns
    -------
    dict
        Detailed completeness diagnostics including counts, missing runs, and flags.
    """
    controllers = expected_controllers or DEFAULT_EXPECTED_CONTROLLERS
    scenarios = expected_scenarios or DEFAULT_EXPECTED_SCENARIOS
    seeds = expected_seeds or DEFAULT_EXPECTED_SEEDS

    total_expected = len(controllers) * len(scenarios) * len(seeds)

    if df.empty:
        return {
            "total_expected_runs": total_expected,
            "total_present_runs": 0,
            "successful_runs": 0,
            "failed_runs": 0,
            "completion_rate_pct": 0.0,
            "is_complete": False,
            "is_partial": True,
            "missing_runs": [
                {"controller_id": c, "scenario_id": sc, "seed": s}
                for c in controllers for sc in scenarios for s in seeds
            ],
            "runs_by_controller": {c: 0 for c in controllers},
            "runs_by_scenario": {sc: 0 for sc in scenarios},
            "present_controllers": [],
        }

    # Build set of present successful (and total) run tuples
    present_set: Set[Tuple[str, str, int]] = set()
    successful_set: Set[Tuple[str, str, int]] = set()
    failed_count = 0

    for _, row in df.iterrows():
        c_val = str(row.get("controller_id"))
        sc_val = str(row.get("scenario_id"))
        s_val = row.get("seed")
        if pd.isna(s_val):
            continue
        key = (c_val, sc_val, int(s_val))
        present_set.add(key)
        if str(row.get("status")) == "SUCCESS":
            successful_set.add(key)
        else:
            failed_count += 1

    missing: List[Dict[str, Any]] = []
    for c in controllers:
        for sc in scenarios:
            for s in seeds:
                if (c, sc, s) not in successful_set:
                    missing.append({"controller_id": c, "scenario_id": sc, "seed": s})

    total_present = len(present_set)
    successful_runs = len(successful_set)
    completion_rate = (successful_runs / total_expected) * 100.0 if total_expected > 0 else 0.0
    is_complete = (len(missing) == 0) and (total_expected > 0)

    # Controller breakdown
    runs_by_controller = {
        c: int((df["controller_id"] == c).sum()) if "controller_id" in df.columns else 0
        for c in controllers
    }

    # Scenario breakdown
    runs_by_scenario = {
        sc: int((df["scenario_id"] == sc).sum()) if "scenario_id" in df.columns else 0
        for sc in scenarios
    }

    return {
        "total_expected_runs": total_expected,
        "total_present_runs": total_present,
        "successful_runs": successful_runs,
        "failed_runs": failed_count,
        "completion_rate_pct": round(completion_rate, 2),
        "is_complete": is_complete,
        "is_partial": not is_complete,
        "missing_runs": missing,
        "runs_by_controller": runs_by_controller,
        "runs_by_scenario": runs_by_scenario,
        "present_controllers": get_available_controllers(df),
    }
