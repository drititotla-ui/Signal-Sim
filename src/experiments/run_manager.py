"""
Experiment Run Manager and Orchestrator for SIGNALSIM-INDIA (P2-M03).

Executes simulation runs under the unified controller contract, manages the simulation
stepping loop, integrates with TripInfo parser and cohort tagging, computes evaluation
metrics, and aggregates results into tabular summaries.
"""

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Union

import numpy as np
import pandas as pd

from src.experiments.config_loader import ExperimentConfig
from src.experiments.controller_adapter import (
    BaseControllerAdapter,
    get_controller_adapter,
)
from src.experiments.planner import ExperimentPlan, ExperimentRunSpec
from src.experiments.sumo_manager import (
    SumoSimulation,
    build_sumo_command,
    find_sumo_binary,
)
from src.metrics.tripinfo_parser import parse_tripinfo
from src.routes.generator import add_cohort_column


@dataclass
class RunResult:
    """Execution outcome and performance metrics for a single simulation run."""
    run_id: str
    controller_id: str
    scenario_id: str
    seed: int
    status: str  # "SUCCESS" | "FAILED"
    error_message: Optional[str]
    simulation_duration_seconds: float
    wall_clock_duration_seconds: float
    tripinfo_path: str
    summary_path: Optional[str]
    total_vehicles: int
    completed_vehicles: int
    unfinished_vehicles: int
    warmup_vehicles: int
    evaluation_vehicles: int
    drain_vehicles: int
    mean_travel_time: float
    mean_waiting_time: float
    mean_time_loss: float
    throughput_vph: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def run_one(
    run_spec: ExperimentRunSpec,
    config: ExperimentConfig,
    gui: bool = False,
    adapter: Optional[BaseControllerAdapter] = None,
    connection: Optional[Any] = None,
    sumo_binary: Optional[str] = None,
) -> RunResult:
    """
    Executes a single simulation run according to the agreed P1-P2 contract.

    Parameters
    ----------
    run_spec : ExperimentRunSpec
        Run parameters, paths, and metadata.
    config : ExperimentConfig
        Experiment global configuration.
    gui : bool, default False
        Whether to launch with sumo-gui.
    adapter : BaseControllerAdapter, optional
        Pre-configured controller adapter (if None, resolved via factory).
    connection : TraCI connection, optional
        Pre-existing TraCI connection (used for testing or mock environments).
    sumo_binary : str, optional
        Explicit path to SUMO binary.

    Returns
    -------
    RunResult
        Execution outcome with vehicle counts and evaluation metrics.
    """
    wall_start = time.perf_counter()
    controller_adapter = adapter or get_controller_adapter(
        run_spec.controller_id,
        tls_id=config.network.traffic_light_id,
        decision_interval=config.timing.controller_decision_interval_seconds,
    )

    # Ensure output directories exist
    config.output.ensure_directories()
    run_spec.tripinfo_output_path.parent.mkdir(parents=True, exist_ok=True)

    # Verify route file exists
    if not run_spec.route_file.is_file():
        raise FileNotFoundError(
            f"Route file required for {run_spec.run_id} not found: {run_spec.route_file}"
        )

    sim_duration = 0.0
    status = "SUCCESS"
    error_msg = None

    try:
        if connection is not None:
            # External or mock connection supplied
            _execute_simulation_loop(
                connection=connection,
                adapter=controller_adapter,
                config=config,
                run_spec=run_spec,
            )
            sim_duration = run_spec.expected_duration
        else:
            # Standard execution: runner launches SUMO and manages lifecycle
            bin_path = sumo_binary or find_sumo_binary(gui=gui)
            cmd = build_sumo_command(
                sumo_binary=bin_path,
                net_file=config.network.network_file,
                route_file=run_spec.route_file,
                additional_file=config.network.vehicle_types_file,
                end_time=run_spec.expected_duration,
                step_length=config.timing.step_length_seconds,
                seed=run_spec.seed,
                tripinfo_output=run_spec.tripinfo_output_path,
                summary_output=run_spec.summary_output_path,
                log_output=run_spec.log_output_path,
                lateral_resolution=0.5,
                write_unfinished=True,
            )

            with SumoSimulation(command=cmd, label=run_spec.run_id) as conn:
                _execute_simulation_loop(
                    connection=conn,
                    adapter=controller_adapter,
                    config=config,
                    run_spec=run_spec,
                )
                try:
                    sim_duration = float(conn.simulation.getTime())
                except Exception:
                    sim_duration = run_spec.expected_duration

    except Exception as err:
        status = "FAILED"
        error_msg = str(err)

    wall_duration = time.perf_counter() - wall_start

    # Process metrics from TripInfo XML if run succeeded
    metrics = _extract_run_metrics(
        tripinfo_path=run_spec.tripinfo_output_path,
        timing=config.timing,
    ) if status == "SUCCESS" else _default_error_metrics()

    result = RunResult(
        run_id=run_spec.run_id,
        controller_id=run_spec.controller_id,
        scenario_id=run_spec.scenario_id,
        seed=run_spec.seed,
        status=status,
        error_message=error_msg,
        simulation_duration_seconds=round(sim_duration, 2),
        wall_clock_duration_seconds=round(wall_duration, 2),
        tripinfo_path=str(run_spec.tripinfo_output_path),
        summary_path=str(run_spec.summary_output_path) if run_spec.summary_output_path.is_file() else None,
        total_vehicles=metrics["total_vehicles"],
        completed_vehicles=metrics["completed_vehicles"],
        unfinished_vehicles=metrics["unfinished_vehicles"],
        warmup_vehicles=metrics["warmup_vehicles"],
        evaluation_vehicles=metrics["evaluation_vehicles"],
        drain_vehicles=metrics["drain_vehicles"],
        mean_travel_time=metrics["mean_travel_time"],
        mean_waiting_time=metrics["mean_waiting_time"],
        mean_time_loss=metrics["mean_time_loss"],
        throughput_vph=metrics["throughput_vph"],
    )

    # Save per-run JSON metadata
    json_path = config.output.summaries_dir / f"{run_spec.run_id}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result.to_dict(), f, indent=2)

    return result


def _execute_simulation_loop(
    connection: Any,
    adapter: BaseControllerAdapter,
    config: ExperimentConfig,
    run_spec: ExperimentRunSpec,
) -> None:
    """Executes the stepped simulation loop."""
    adapter.setup(
        connection=connection,
        config=config,
        scenario_id=run_spec.scenario_id,
        seed=run_spec.seed,
    )

    target_time = run_spec.expected_duration
    while True:
        sim_time = connection.simulation.getTime()
        if sim_time >= target_time - 1e-6:
            break
        connection.simulationStep()
        now = connection.simulation.getTime()
        adapter.step(now)

    adapter.teardown()


def _default_error_metrics() -> Dict[str, Any]:
    return {
        "total_vehicles": 0,
        "completed_vehicles": 0,
        "unfinished_vehicles": 0,
        "warmup_vehicles": 0,
        "evaluation_vehicles": 0,
        "drain_vehicles": 0,
        "mean_travel_time": float("nan"),
        "mean_waiting_time": float("nan"),
        "mean_time_loss": float("nan"),
        "throughput_vph": 0.0,
    }


def _extract_run_metrics(tripinfo_path: Path, timing: Any) -> Dict[str, Any]:
    """Parses tripinfo XML, applies cohort classification, and computes evaluation metrics."""
    if not tripinfo_path.is_file():
        return _default_error_metrics()

    try:
        raw_df = parse_tripinfo(tripinfo_path)
    except Exception:
        return _default_error_metrics()

    if raw_df.empty:
        return _default_error_metrics()

    df = add_cohort_column(
        raw_df,
        warm_up_seconds=timing.warm_up_seconds,
        evaluation_seconds=timing.evaluation_seconds,
        depart_col="depart",
    )

    total_count = len(df)
    completed_count = int(df["is_completed"].sum())
    unfinished_count = total_count - completed_count

    warmup_count = int((df["cohort"] == "warm_up").sum())
    eval_count = int((df["cohort"] == "evaluation").sum())
    drain_count = int((df["cohort"] == "out_of_bounds").sum())

    # Evaluation cohort records: [600, 4200)
    eval_df = df[df["cohort"] == "evaluation"]
    completed_eval = eval_df[eval_df["is_completed"]]

    if not completed_eval.empty:
        mean_travel = float(completed_eval["duration"].mean())
        mean_waiting = float(completed_eval["waiting_time"].mean())
        mean_loss = float(completed_eval["time_loss"].mean())
    else:
        mean_travel = float("nan")
        mean_waiting = float("nan")
        mean_loss = float("nan")

    # Throughput: completed evaluation vehicles per hour (3600s window)
    eval_hours = timing.evaluation_seconds / 3600.0
    throughput = len(completed_eval) / eval_hours if eval_hours > 0 else 0.0

    return {
        "total_vehicles": total_count,
        "completed_vehicles": completed_count,
        "unfinished_vehicles": unfinished_count,
        "warmup_vehicles": warmup_count,
        "evaluation_vehicles": eval_count,
        "drain_vehicles": drain_count,
        "mean_travel_time": round(mean_travel, 2),
        "mean_waiting_time": round(mean_waiting, 2),
        "mean_time_loss": round(mean_loss, 2),
        "throughput_vph": round(throughput, 2),
    }


class ExperimentRunner:
    """Master orchestrator for executing experimental plans."""

    def __init__(self, config: ExperimentConfig):
        self.config = config

    def run_plan(
        self,
        plan: ExperimentPlan,
        gui: bool = False,
        generate_routes: bool = True,
        fail_fast: bool = False,
    ) -> List[RunResult]:
        """
        Executes all runs in the plan and writes master summary reports.
        """
        if generate_routes:
            plan.ensure_route_files(generate_missing=True)

        results: List[RunResult] = []
        print(f"\n============================================================")
        print(f"SIGNALSIM-INDIA: Executing {plan.total_runs} Planned Runs")
        print(f"============================================================")

        for idx, run_spec in enumerate(plan.runs, start=1):
            print(
                f"[{idx}/{plan.total_runs}] Running {run_spec.run_id} ... ",
                end="",
                flush=True,
            )
            res = run_one(run_spec, self.config, gui=gui)
            results.append(res)
            print(f"{res.status} ({res.wall_clock_duration_seconds:.1f}s)")

            if fail_fast and res.status == "FAILED":
                print(f"Execution halted due to fail_fast=True: {res.error_message}")
                break

        # Save aggregated master summary
        self.save_master_summary(results)
        return results

    def save_master_summary(self, results: List[RunResult]) -> pd.DataFrame:
        """Compiles run results into master CSV and JSON summary tables."""
        records = [r.to_dict() for r in results]
        df = pd.DataFrame(records)

        csv_path = self.config.output.summaries_dir / "master_summary.csv"
        json_path = self.config.output.summaries_dir / "master_summary.json"

        df.to_csv(csv_path, index=False)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2)

        print(f"\nMaster summary saved to: {csv_path}")
        return df
