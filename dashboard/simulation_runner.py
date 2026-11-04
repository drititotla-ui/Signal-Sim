"""
Local SUMO Simulation Execution Engine for SIGNALSIM-INDIA Dashboard (M04.2.3).

Invokes the canonical P2-M03 experiment runner (experiments/run_experiments.py)
via secure Python subprocess, validates prerequisites, prevents duplicate launches,
preserves existing benchmark summaries, and refreshes dashboard data.
"""

from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parent.parent

VALID_CONTROLLERS = ["fixed_time", "max_pressure", "ppo_v6"]
VALID_SCENARIOS = ["S1", "S2", "S3", "S4"]
VALID_SEEDS = [42, 101, 202, 303, 404]


@dataclass
class SimulationExecutionResult:
    """Outcome and diagnostics from a local SUMO simulation execution."""
    success: bool
    run_id: str
    controller_id: str
    scenario_id: str
    seed: int
    wall_clock_seconds: float
    stdout: str
    stderr: str
    metrics: Dict[str, Any]
    error_message: Optional[str] = None


def check_prerequisites() -> Tuple[bool, str]:
    """
    Verifies that local SUMO, network definitions, configs, and Python environment
    are present and ready for execution.
    """
    # 1. Check Python executable
    if not Path(sys.executable).exists():
        return False, f"Python executable not found at: {sys.executable}"

    # 2. Check SUMO binary
    try:
        from src.experiments.sumo_manager import find_sumo_binary
        sumo_bin = find_sumo_binary(gui=False)
        if not sumo_bin or not Path(sumo_bin).exists():
            return False, "SUMO binary not found in PATH or SUMO_HOME. Please verify SUMO installation."
    except Exception as err:
        return False, f"SUMO prerequisite check failed: {err}"

    # 3. Check Network File
    net_path = ROOT_DIR / "lht_working" / "candidate" / "signalsim_lht_timed.net.xml"
    if not net_path.is_file():
        return False, f"Canonical network file missing at: {net_path}"

    # 4. Check Config File
    cfg_path = ROOT_DIR / "configs" / "experiment.yaml"
    if not cfg_path.is_file():
        return False, f"Experiment configuration missing at: {cfg_path}"

    # 5. Check Runner Script
    runner_path = ROOT_DIR / "experiments" / "run_experiments.py"
    if not runner_path.is_file():
        return False, f"Runner script missing at: {runner_path}"

    return True, "All simulation prerequisites verified successfully."


def merge_run_into_master_summary(new_record: Dict[str, Any]) -> None:
    """
    Safely merges a single run record into master_summary.csv and master_summary.json.
    Strictly preserves previously recorded benchmark rows by upserting on run_id.
    """
    summaries_dir = ROOT_DIR / "results" / "summaries"
    summaries_dir.mkdir(parents=True, exist_ok=True)
    csv_path = summaries_dir / "master_summary.csv"
    json_path = summaries_dir / "master_summary.json"

    run_id = new_record.get("run_id")
    if not run_id:
        return

    # Load existing CSV if present
    if csv_path.is_file():
        try:
            df = pd.read_csv(csv_path)
            if "run_id" in df.columns and run_id in df["run_id"].values:
                # Update existing row
                mask = (df["run_id"] == run_id)
                for col, val in new_record.items():
                    df.loc[mask, col] = val
            else:
                # Append new row
                new_row_df = pd.DataFrame([new_record])
                df = pd.concat([df, new_row_df], ignore_index=True)
        except Exception:
            df = pd.DataFrame([new_record])
    else:
        df = pd.DataFrame([new_record])

    # Persist updated master summary CSV and JSON
    df.to_csv(csv_path, index=False)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(df.to_dict(orient="records"), f, indent=2)


def run_single_simulation(
    controller_id: str,
    scenario_id: str,
    seed: int,
    timeout_seconds: int = 300,
) -> SimulationExecutionResult:
    """
    Executes a single simulation run via experiments/run_experiments.py.
    """
    run_id = f"{controller_id}_{scenario_id}_seed{seed}"
    start_time = time.perf_counter()

    # 1. Parameter Validation
    if controller_id not in VALID_CONTROLLERS:
        return SimulationExecutionResult(
            success=False,
            run_id=run_id,
            controller_id=controller_id,
            scenario_id=scenario_id,
            seed=seed,
            wall_clock_seconds=0.0,
            stdout="",
            stderr="",
            metrics={},
            error_message=f"Invalid controller '{controller_id}'. Allowed: {VALID_CONTROLLERS}.",
        )

    if scenario_id not in VALID_SCENARIOS:
        return SimulationExecutionResult(
            success=False,
            run_id=run_id,
            controller_id=controller_id,
            scenario_id=scenario_id,
            seed=seed,
            wall_clock_seconds=0.0,
            stdout="",
            stderr="",
            metrics={},
            error_message=f"Invalid scenario '{scenario_id}'. Allowed: {VALID_SCENARIOS}.",
        )

    if seed not in VALID_SEEDS:
        return SimulationExecutionResult(
            success=False,
            run_id=run_id,
            controller_id=controller_id,
            scenario_id=scenario_id,
            seed=seed,
            wall_clock_seconds=0.0,
            stdout="",
            stderr="",
            metrics={},
            error_message=f"Invalid seed '{seed}'. Allowed: {VALID_SEEDS}.",
        )

    # 2. Check Prerequisites
    prereq_ok, prereq_msg = check_prerequisites()
    if not prereq_ok:
        return SimulationExecutionResult(
            success=False,
            run_id=run_id,
            controller_id=controller_id,
            scenario_id=scenario_id,
            seed=seed,
            wall_clock_seconds=0.0,
            stdout="",
            stderr="",
            metrics={},
            error_message=f"Prerequisite failure: {prereq_msg}",
        )

    # 3. Cache existing master summary so it is not lost if the runner overwrites
    existing_records: List[Dict[str, Any]] = []
    csv_path = ROOT_DIR / "results" / "summaries" / "master_summary.csv"
    if csv_path.is_file():
        try:
            existing_records = pd.read_csv(csv_path).to_dict(orient="records")
        except Exception:
            existing_records = []

    # 4. Construct Command
    cmd = [
        sys.executable,
        str(ROOT_DIR / "experiments" / "run_experiments.py"),
        "--controllers", controller_id,
        "--scenarios", scenario_id,
        "--seeds", str(seed),
    ]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(ROOT_DIR),
            timeout=timeout_seconds,
        )
        elapsed = time.perf_counter() - start_time

        if proc.returncode != 0:
            return SimulationExecutionResult(
                success=False,
                run_id=run_id,
                controller_id=controller_id,
                scenario_id=scenario_id,
                seed=seed,
                wall_clock_seconds=elapsed,
                stdout=proc.stdout,
                stderr=proc.stderr,
                metrics={},
                error_message=f"Runner exited with non-zero exit code ({proc.returncode}). See output log.",
            )

        # 5. Locate Run Output JSON
        run_json_path = ROOT_DIR / "results" / "summaries" / f"{run_id}.json"
        if not run_json_path.is_file():
            return SimulationExecutionResult(
                success=False,
                run_id=run_id,
                controller_id=controller_id,
                scenario_id=scenario_id,
                seed=seed,
                wall_clock_seconds=elapsed,
                stdout=proc.stdout,
                stderr=proc.stderr,
                metrics={},
                error_message=f"Expected result summary file was not generated: {run_json_path}",
            )

        with open(run_json_path, "r", encoding="utf-8") as f:
            run_data = json.load(f)

        # 6. Re-merge with existing records to protect previous benchmarks
        for old_rec in existing_records:
            if old_rec.get("run_id") != run_id:
                merge_run_into_master_summary(old_rec)
        merge_run_into_master_summary(run_data)

        return SimulationExecutionResult(
            success=True,
            run_id=run_id,
            controller_id=controller_id,
            scenario_id=scenario_id,
            seed=seed,
            wall_clock_seconds=elapsed,
            stdout=proc.stdout,
            stderr=proc.stderr,
            metrics=run_data,
        )

    except subprocess.TimeoutExpired:
        elapsed = time.perf_counter() - start_time
        return SimulationExecutionResult(
            success=False,
            run_id=run_id,
            controller_id=controller_id,
            scenario_id=scenario_id,
            seed=seed,
            wall_clock_seconds=elapsed,
            stdout="",
            stderr="",
            metrics={},
            error_message=f"Simulation timed out after {timeout_seconds} seconds.",
        )
    except Exception as err:
        elapsed = time.perf_counter() - start_time
        return SimulationExecutionResult(
            success=False,
            run_id=run_id,
            controller_id=controller_id,
            scenario_id=scenario_id,
            seed=seed,
            wall_clock_seconds=elapsed,
            stdout="",
            stderr=str(err),
            metrics={},
            error_message=f"Execution failed with unexpected exception: {err}",
        )
