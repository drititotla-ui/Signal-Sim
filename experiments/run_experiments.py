#!/usr/bin/env python3
"""
CLI Execution Entry Point for SIGNALSIM-INDIA Experiment Benchmark (P2-M03).

Executes reproducible simulation experiments across Fixed-Time, Max-Pressure, and PPO
controllers on matched seeds and scenarios.
"""

import argparse
import sys
from pathlib import Path
from typing import List, Optional

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.experiments.config_loader import ExperimentConfig
from src.experiments.planner import build_experiment_plan
from src.experiments.run_manager import ExperimentRunner


def parse_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="SIGNALSIM-INDIA Benchmark Experiment Runner (P2-M03)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--config",
        type=str,
        default="configs/experiment.yaml",
        help="Path to main experiment configuration YAML",
    )
    parser.add_argument(
        "--scenarios-dir",
        type=str,
        default="configs/scenarios",
        help="Path to scenario definitions directory",
    )
    parser.add_argument(
        "--controllers",
        nargs="+",
        default=["all"],
        help="Controllers to evaluate: 'fixed_time', 'max_pressure', 'ppo', or 'all'",
    )
    parser.add_argument(
        "--scenarios",
        nargs="+",
        default=["all"],
        help="Scenarios to evaluate: 'S1', 'S2', 'S3', 'S4', or 'all'",
    )
    parser.add_argument(
        "--seeds",
        nargs="+",
        type=int,
        default=None,
        help="Evaluation seeds to run (e.g. 42 101), or omit for all configured seeds",
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        default=False,
        help="Launch SUMO graphical interface (sumo-gui) instead of headless sumo",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Plan runs and check prerequisites without executing simulation",
    )
    parser.add_argument(
        "--generate-routes",
        action="store_true",
        default=True,
        help="Generate missing route files automatically before running",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        default=False,
        help="Halt execution on the first failure",
    )
    return parser.parse_args(args)


def main(args: Optional[List[str]] = None) -> int:
    parsed = parse_args(args)

    print("=" * 70)
    print("SIGNALSIM-INDIA | P2-M03 Experiment Runner")
    print("=" * 70)

    try:
        config = ExperimentConfig.load(
            config_path=parsed.config,
            scenarios_dir=parsed.scenarios_dir,
            project_root=PROJECT_ROOT,
        )
        print(f"Loaded config: {config.name} (v{config.version})")
        print(f"Benchmark network: {config.network.network_file.name}")
        print(f"Traffic direction: {config.traffic_direction} | Decision interval: {config.timing.controller_decision_interval_seconds}s")
        print(f"Timing: Warm-up={config.timing.warm_up_seconds}s, Eval={config.timing.evaluation_seconds}s, Drain={config.timing.drain_seconds}s (Total={config.timing.total_simulation_seconds}s)")

        # Resolve controller filters
        controllers = None
        if parsed.controllers and "all" not in parsed.controllers:
            controllers = parsed.controllers
        else:
            # By default evaluate the two operational controllers
            controllers = ["fixed_time", "max_pressure"]

        # Resolve scenario filters
        scenarios = None
        if parsed.scenarios and "all" not in parsed.scenarios:
            scenarios = parsed.scenarios

        # Resolve seed filters
        seeds = parsed.seeds if parsed.seeds else None

        # Build execution plan
        plan = build_experiment_plan(
            config=config,
            controllers=controllers,
            scenarios=scenarios,
            seeds=seeds,
        )
        print(f"\nConstructed plan with {plan.total_runs} runs across:")
        print(f"  Controllers: {controllers}")
        print(f"  Scenarios:   {scenarios or list(config.scenarios.keys())}")
        print(f"  Seeds:       {seeds or list(config.seeds)}")

        if parsed.dry_run:
            print("\n[DRY-RUN] Validating routes and output paths...")
            route_map = plan.ensure_route_files(generate_missing=parsed.generate_routes)
            print(f"[DRY-RUN] Verified {len(route_map)} route files.")
            for r in plan.runs:
                print(f"  - Plan: {r.run_id} -> {r.route_file.name}")
            print("\nDry-run completed successfully. No simulations were executed.")
            return 0

        runner = ExperimentRunner(config=config)
        results = runner.run_plan(
            plan=plan,
            gui=parsed.gui,
            generate_routes=parsed.generate_routes,
            fail_fast=parsed.fail_fast,
        )

        success_count = sum(1 for r in results if r.status == "SUCCESS")
        fail_count = len(results) - success_count
        print(f"\nBenchmark completed: {success_count} succeeded, {fail_count} failed out of {len(results)} runs.")

        return 0 if fail_count == 0 else 1

    except Exception as err:
        print(f"\nERROR: Experiment runner execution failed: {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
