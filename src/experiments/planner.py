"""
Experiment planner for SIGNALSIM-INDIA (P2-M03).

Constructs deterministic experiment execution plans mapping scenarios, seeds, and
controllers into concrete run specifications with verified route file bindings.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple, Union

from src.experiments.config_loader import ExperimentConfig
from src.routes.generator import (
    RouteGeneratorConfig,
    generate_route_file,
)


@dataclass(frozen=True)
class ExperimentRunSpec:
    """Complete specification for a single simulation execution run."""
    run_id: str
    controller_id: str
    scenario_id: str
    seed: int
    route_file: Path
    expected_duration: float
    tripinfo_output_path: Path
    summary_output_path: Path
    log_output_path: Path


@dataclass
class ExperimentPlan:
    """Container representing a planned set of experiment runs."""
    config: ExperimentConfig
    runs: List[ExperimentRunSpec]

    @property
    def total_runs(self) -> int:
        return len(self.runs)

    def filter(
        self,
        controllers: Optional[Sequence[str]] = None,
        scenarios: Optional[Sequence[str]] = None,
        seeds: Optional[Sequence[int]] = None,
    ) -> "ExperimentPlan":
        """Returns a new ExperimentPlan filtered by the specified criteria."""
        filtered = []
        for r in self.runs:
            if controllers is not None and r.controller_id not in controllers:
                continue
            if scenarios is not None and r.scenario_id not in scenarios:
                continue
            if seeds is not None and r.seed not in seeds:
                continue
            filtered.append(r)
        return ExperimentPlan(config=self.config, runs=filtered)

    def ensure_route_files(
        self,
        generate_missing: bool = True,
        overwrite: bool = False,
    ) -> Dict[Tuple[str, int], Path]:
        """
        Verifies that all required deterministic route files exist on disk,
        optionally generating missing files upfront using the confirmed fleet mix.
        """
        route_map: Dict[Tuple[str, int], Path] = {}
        routes_dir = self.config.routes_dir
        routes_dir.mkdir(parents=True, exist_ok=True)

        # Build RouteGeneratorConfig from experiment config settings
        route_gen_cfg = RouteGeneratorConfig(
            warm_up_seconds=self.config.timing.warm_up_seconds,
            evaluation_seconds=self.config.timing.evaluation_seconds,
            drain_seconds=self.config.timing.drain_seconds,
            step_length_seconds=self.config.timing.step_length_seconds,
            baseline_demand_per_approach=self.config.timing.baseline_demand_per_approach,
            inflow_edges=self.config.inflow_edges,
            outflow_edges=self.config.outflow_edges,
            evaluation_seeds=self.config.seeds,
            scenario_multipliers={
                s_id: s_spec.demand_multiplier for s_id, s_spec in self.config.scenarios.items()
            },
            scenario_turning_splits={
                s_id: s_spec.turning_proportions for s_id, s_spec in self.config.scenarios.items()
            },
        )

        for run in self.runs:
            key = (run.scenario_id, run.seed)
            if key in route_map:
                continue

            target_path = run.route_file
            if not target_path.is_file() or overwrite:
                if not generate_missing:
                    raise FileNotFoundError(f"Missing required route file: {target_path}")
                # Generate deterministically with confirmed 6-class fleet mix
                generate_route_file(
                    scenario_id=run.scenario_id,
                    seed=run.seed,
                    fleet_mix=self.config.fleet_mix,
                    output_path=target_path,
                    config=route_gen_cfg,
                )
            route_map[key] = target_path

        return route_map


def build_experiment_plan(
    config: ExperimentConfig,
    controllers: Optional[Sequence[str]] = None,
    scenarios: Optional[Sequence[str]] = None,
    seeds: Optional[Sequence[int]] = None,
) -> ExperimentPlan:
    """
    Constructs an ExperimentPlan for the specified controllers, scenarios, and seeds.

    Parameters
    ----------
    config : ExperimentConfig
        Experiment configuration settings.
    controllers : sequence of str, optional
        Filter controllers (default: all candidates configured, e.g. fixed_time, max_pressure).
    scenarios : sequence of str, optional
        Filter scenarios (default: all configured scenarios, e.g. S1, S2, S3, S4).
    seeds : sequence of int, optional
        Filter seeds (default: all evaluation seeds, e.g. 42, 101, 202, 303, 404).

    Returns
    -------
    ExperimentPlan
        Constructed experiment plan with fully resolved output paths.
    """
    selected_controllers = (
        tuple(controllers) if controllers is not None else config.controller_ids
    )
    selected_scenarios = (
        tuple(scenarios) if scenarios is not None else tuple(config.scenarios.keys())
    )
    selected_seeds = tuple(seeds) if seeds is not None else config.seeds

    runs: List[ExperimentRunSpec] = []
    duration = config.timing.total_simulation_seconds

    for sc_id in selected_scenarios:
        if sc_id not in config.scenarios:
            raise ValueError(f"Unknown scenario ID '{sc_id}'. Configured: {list(config.scenarios.keys())}")
        for s in selected_seeds:
            route_filename = f"{config.route_prefix}_{sc_id}_seed{s}.rou.xml"
            route_path = config.routes_dir / route_filename

            for ctrl_id in selected_controllers:
                run_id = f"{ctrl_id}_{sc_id}_seed{s}"

                tripinfo_path = config.output.raw_tripinfo_dir / f"{run_id}_tripinfo.xml"
                summary_path = config.output.summaries_dir / f"{run_id}_summary.xml"
                log_path = config.output.summaries_dir / f"{run_id}.log"

                runs.append(
                    ExperimentRunSpec(
                        run_id=run_id,
                        controller_id=ctrl_id,
                        scenario_id=sc_id,
                        seed=s,
                        route_file=route_path,
                        expected_duration=duration,
                        tripinfo_output_path=tripinfo_path,
                        summary_output_path=summary_path,
                        log_output_path=log_path,
                    )
                )

    return ExperimentPlan(config=config, runs=runs)
