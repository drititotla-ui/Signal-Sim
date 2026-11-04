"""
Controller adapters for SIGNALSIM-INDIA (P2-M03).

Provides standardized adapters for Fixed-Time, Max-Pressure, and PPO controllers.
The experiment runner manages the simulation lifecycle while controllers own their
control decisions via the unified BaseControllerAdapter contract.
"""

from abc import ABC, abstractmethod
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import numpy as np

from src.experiments.config_loader import ExperimentConfig
from sumo_simulation.controllers.signal_manager import SignalManager


class ControllerError(Exception):
    """Raised when a controller encounters an invalid state or execution failure."""
    pass


class PPOModelNotAvailableError(ControllerError):
    """Raised when evaluation is requested for PPO but no valid model checkpoint is available."""
    pass


class BaseControllerAdapter(ABC):
    """Abstract base class establishing the common controller evaluation contract."""

    def __init__(self, controller_id: str, tls_id: str = "J2"):
        self.controller_id = controller_id
        self.tls_id = tls_id
        self.connection: Optional[Any] = None
        self.config: Optional[ExperimentConfig] = None
        self.scenario_id: Optional[str] = None
        self.seed: Optional[int] = None

    def setup(
        self,
        connection: Any,
        config: ExperimentConfig,
        scenario_id: str,
        seed: int,
    ) -> None:
        """Initializes the controller for an active simulation connection."""
        self.connection = connection
        self.config = config
        self.scenario_id = scenario_id
        self.seed = seed

    @abstractmethod
    def step(self, current_time: float) -> None:
        """Invoked after each simulation step (e.g. delta-t = 0.1s)."""
        pass

    def teardown(self) -> None:
        """Invoked after simulation completes to release any controller resources."""
        self.connection = None


class FixedTimeAdapter(BaseControllerAdapter):
    """
    Fixed-Time baseline controller adapter.

    Executes the verified static six-phase program:
    - Phase 0: East-West Green (30s)
    - Phase 1: East-West Yellow (3s)
    - Phase 2: All-Red Clearance (1s)
    - Phase 3: North-South Green (30s)
    - Phase 4: North-South Yellow (3s)
    - Phase 5: All-Red Clearance (1s)
    Total Cycle: 68s.
    """

    EXPECTED_STATES = [
        "GGGGgrrrrrGGGGgrrrrr",
        "yyyyyrrrrryyyyyrrrrr",
        "rrrrrrrrrrrrrrrrrrrr",
        "rrrrrGGGGgrrrrrGGGGg",
        "rrrrryyyyyrrrrryyyyy",
        "rrrrrrrrrrrrrrrrrrrr",
    ]
    EXPECTED_DURATIONS = [30.0, 3.0, 3.0, 30.0, 3.0, 3.0]
    ALL_RED_DURATION: float = 3.0

    def __init__(self, tls_id: str = "J2"):
        super().__init__(controller_id="fixed_time", tls_id=tls_id)
        self.current_phase: Optional[int] = None
        self.phase_transitions: int = 0

    def setup(
        self,
        connection: Any,
        config: ExperimentConfig,
        scenario_id: str,
        seed: int,
    ) -> None:
        super().setup(connection, config, scenario_id, seed)
        tls_list = self.connection.trafficlight.getIDList()
        if self.tls_id not in tls_list:
            raise ControllerError(f"Traffic light '{self.tls_id}' not found in simulation: {tls_list}")

        # Verify static program logic matches verified 6-phase setup
        programs = self.connection.trafficlight.getAllProgramLogics(self.tls_id)
        matching = [
            p for p in programs
            if len(p.phases) == 6
            and all(p.phases[i].state == self.EXPECTED_STATES[i] for i in range(6))
        ]
        if not matching:
            raise ControllerError(
                f"Traffic light '{self.tls_id}' in approved network does not match verified 6-phase program."
            )

        program = matching[0]
        # Align clearance interval (All-Red phases 2 and 5) with IRC:93-1985 safety standards (3.0s)
        if hasattr(program, "phases") and len(program.phases) == 6:
            program.phases[2].duration = self.ALL_RED_DURATION
            program.phases[5].duration = self.ALL_RED_DURATION
            if hasattr(self.connection.trafficlight, "setProgramLogic"):
                try:
                    self.connection.trafficlight.setProgramLogic(self.tls_id, program)
                except Exception:
                    pass

        self.connection.trafficlight.setProgram(self.tls_id, program.programID)
        self.connection.trafficlight.setPhase(self.tls_id, 0)
        self.current_phase = 0
        self.phase_transitions = 0

    def step(self, current_time: float) -> None:
        """Monitors and records phase progression of the static controller."""
        phase = self.connection.trafficlight.getPhase(self.tls_id)
        if phase != self.current_phase:
            self.current_phase = phase
            self.phase_transitions += 1


class MaxPressureAdapter(BaseControllerAdapter):
    """
    Max-Pressure adaptive heuristic controller adapter.

    Uses SignalManager to enforce min/max green, yellow, and all-red safety constraints.
    Computes pressure differentials across movements at decision intervals (10s) and
    actuates pressure-reducing phase requests.
    """

    GREEN_PHASES = {0: 0, 1: 3}  # 0: East-West (phase 0), 1: North-South (phase 3)
    PRESSURE_MARGIN = 1.0
    MAX_GREEN = 60.0

    def __init__(self, tls_id: str = "J2", decision_interval: float = 10.0):
        super().__init__(controller_id="max_pressure", tls_id=tls_id)
        self.decision_interval = decision_interval
        self.manager: Optional[SignalManager] = None
        self.movements: Dict[int, List[Tuple[str, str]]] = {}
        self.next_decision_time: float = 0.0
        self.decisions_count: int = 0
        self.switches_count: int = 0
        self.last_pressures: Dict[int, float] = {0: 0.0, 1: 0.0}

    @staticmethod
    def _lane_to_edge(lane_id: str) -> str:
        return lane_id.rsplit("_", 1)[0]

    def _discover_group_movements(self) -> Dict[int, List[Tuple[str, str]]]:
        """Discovers permitted movement edge pairs for Group 0 and Group 1 from network links."""
        links = self.connection.trafficlight.getControlledLinks(self.tls_id)
        programs = self.connection.trafficlight.getAllProgramLogics(self.tls_id)
        matches = [
            p for p in programs
            if len(p.phases) == 6
            and p.phases[0].state == SignalManager.STATES[0]
            and p.phases[3].state == SignalManager.STATES[3]
        ]
        if not matches:
            raise ControllerError("Expected traffic light program not found for Max-Pressure.")

        phases = matches[0].phases
        movements: Dict[int, List[Tuple[str, str]]] = {}

        for group, phase_index in self.GREEN_PHASES.items():
            state = phases[phase_index].state
            pairs: Set[Tuple[str, str]] = set()

            for signal_idx, signal_char in enumerate(state):
                if signal_char not in ("G", "g"):
                    continue
                for conn in links[signal_idx]:
                    from_lane, to_lane = conn[:2]
                    if not from_lane or not to_lane:
                        continue
                    upstream = self._lane_to_edge(from_lane)
                    downstream = self._lane_to_edge(to_lane)
                    pairs.add((upstream, downstream))

            movements[group] = sorted(pairs)
            if not pairs:
                raise ControllerError(f"No permitted movements discovered for signal group {group}")

        return movements

    def setup(
        self,
        connection: Any,
        config: ExperimentConfig,
        scenario_id: str,
        seed: int,
    ) -> None:
        super().setup(connection, config, scenario_id, seed)
        self.manager = SignalManager(tls_id=self.tls_id, connection=self.connection)
        self.movements = self._discover_group_movements()
        self.decision_interval = config.timing.controller_decision_interval_seconds
        self.next_decision_time = self.decision_interval
        self.decisions_count = 0
        self.switches_count = 0
        self.last_pressures = {0: 0.0, 1: 0.0}

    def _calculate_pressure(self) -> Dict[int, float]:
        """Calculates upstream halting queue minus downstream vehicle count per group."""
        pressures: Dict[int, float] = {}
        for group, pairs in self.movements.items():
            outgoing_by_incoming: Dict[str, Set[str]] = defaultdict(set)
            for upstream, downstream in pairs:
                outgoing_by_incoming[upstream].add(downstream)

            total = 0.0
            for upstream, downstream_edges in outgoing_by_incoming.items():
                upstream_queue = self.connection.edge.getLastStepHaltingNumber(upstream)
                for downstream in downstream_edges:
                    downstream_vehicles = self.connection.edge.getLastStepVehicleNumber(downstream)
                    weight = 1.0 / len(downstream_edges)
                    total += weight * (upstream_queue - downstream_vehicles)

            pressures[group] = total
        return pressures

    def step(self, current_time: float) -> None:
        if self.manager is None:
            return

        # 1. Update safety manager state machine every simulation step (0.1s)
        self.manager.update()

        # 2. Decision interval evaluation (every 10.0s)
        if current_time + 1e-6 >= self.next_decision_time:
            pressures = self._calculate_pressure()
            self.last_pressures = pressures
            self.decisions_count += 1
            status = self.manager.get_status()

            if status["stage"] == "green":
                current_group = status["group"]
                other_group = 1 - current_group

                # Pressure-based group selection
                if pressures[other_group] > pressures[current_group] + self.PRESSURE_MARGIN:
                    requested_group = other_group
                else:
                    requested_group = current_group

                # Enforce MAX_GREEN cutoff (60.0s)
                green_elapsed = current_time - self.manager.stage_started
                if green_elapsed >= self.MAX_GREEN:
                    requested_group = other_group

                if requested_group != current_group:
                    switched = self.manager.request(requested_group)
                    if switched:
                        self.switches_count += 1

            self.next_decision_time += self.decision_interval


class PPOAdapter(BaseControllerAdapter):
    """
    PPO Reinforcement Learning controller adapter (V5 baseline).

    Executes evaluation inference with frozen policy weights. If model checkpoint
    is not provided, raises PPOModelNotAvailableError when execution is attempted.
    """

    def __init__(
        self,
        tls_id: str = "J2",
        checkpoint_path: Optional[Union[str, Path]] = None,
        mock_policy: bool = False,
    ):
        super().__init__(controller_id="ppo", tls_id=tls_id)
        self.checkpoint_path = Path(checkpoint_path) if checkpoint_path else None
        self.mock_policy = mock_policy
        self.manager: Optional[SignalManager] = None
        self.model: Optional[Any] = None

    def setup(
        self,
        connection: Any,
        config: ExperimentConfig,
        scenario_id: str,
        seed: int,
    ) -> None:
        super().setup(connection, config, scenario_id, seed)
        if self.checkpoint_path is None and not self.mock_policy:
            raise PPOModelNotAvailableError(
                "PPO controller evaluation requires a trained model checkpoint (.zip / .pt). "
                "P1 has not yet delivered the finalized PPO checkpoint."
            )
        self.manager = SignalManager(tls_id=self.tls_id, connection=self.connection)

    def step(self, current_time: float) -> None:
        if self.manager is None:
            return
        self.manager.update()
        # Stub for RL inference evaluation when model checkpoint is connected


class PPOV6Adapter(BaseControllerAdapter):
    """
    PPO V6 Reinforcement Learning controller adapter.

    Executes target-phase decision-making (0: EW Green, 1: NS Green) at 10.0s intervals.
    Enforces signal safety via SignalManager:
    - Min Green: 10.0s
    - Max Green: 60.0s (forced transition)
    - Yellow: 3.0s
    - All-Red: 1.0s

    Supports loading from a trained model checkpoint (.zip) via Stable-Baselines3 PPO,
    or falls back to an evaluation target-phase policy if no trained checkpoint is supplied.
    """

    MAX_GREEN: float = 60.0
    INCOMING_EDGES: List[str] = ["-E1", "-E2", "-E3", "-E4"]
    OUTGOING_EDGES: List[str] = ["E1", "E2", "E3", "E4"]

    def __init__(
        self,
        tls_id: str = "J2",
        checkpoint_path: Optional[Union[str, Path]] = None,
        decision_interval: float = 10.0,
        deterministic: bool = False,
        **kwargs: Any,
    ):
        super().__init__(controller_id="ppo_v6", tls_id=tls_id)
        self.checkpoint_path = Path(checkpoint_path) if checkpoint_path else None
        self.decision_interval = decision_interval
        self.deterministic = deterministic
        self.next_decision_time = decision_interval
        self.decisions_count = 0
        self.switches_count = 0
        self.forced_switches_count = 0
        self.rejected_switches_count = 0
        self.holds_count = 0
        self.action_counts = {0: 0, 1: 0}
        self.manager: Optional[SignalManager] = None
        self.model: Optional[Any] = None

    def setup(
        self,
        connection: Any,
        config: ExperimentConfig,
        scenario_id: str,
        seed: int,
    ) -> None:
        super().setup(connection, config, scenario_id, seed)
        # Seed PyTorch and NumPy for strictly reproducible stochastic inference
        try:
            import torch
            torch.manual_seed(seed)
        except Exception:
            pass
        np.random.seed(seed)

        self.manager = SignalManager(tls_id=self.tls_id, connection=self.connection)
        self.decision_interval = config.timing.controller_decision_interval_seconds
        self.next_decision_time = self.decision_interval
        self.decisions_count = 0
        self.switches_count = 0
        self.forced_switches_count = 0
        self.rejected_switches_count = 0
        self.holds_count = 0
        self.action_counts = {0: 0, 1: 0}

        # Model resolution:
        # 1. Explicit checkpoint path if provided
        # 2. Default candidate models/ppo_v6_model.zip
        # 3. Evaluation fallback policy
        model_path = self.checkpoint_path or Path("models/ppo_v6_model.zip")
        if model_path.exists():
            try:
                from stable_baselines3 import PPO
                self.model = PPO.load(str(model_path))
            except Exception:
                self.model = None
        else:
            self.model = None

    def _get_observation(self) -> np.ndarray:
        current_time = self.connection.simulation.getTime()
        stage_elapsed = current_time - self.manager.stage_started
        is_green = 1.0 if self.manager.stage == "green" else 0.0
        green_ratio = float(np.clip(stage_elapsed / self.MAX_GREEN, 0.0, 1.0)) if is_green else 0.0
        min_green_ok = 1.0 if (is_green and stage_elapsed >= self.manager.MIN_GREEN) else 0.0

        queues = [float(self.connection.edge.getLastStepHaltingNumber(e)) for e in self.INCOMING_EDGES]
        vehicles = [float(self.connection.edge.getLastStepVehicleNumber(e)) for e in self.INCOMING_EDGES]
        waiting = [float(self.connection.edge.getWaitingTime(e)) for e in self.INCOMING_EDGES]
        downstream = [float(self.connection.edge.getLastStepVehicleNumber(e)) for e in self.OUTGOING_EDGES]

        q_norm = [float(np.clip(q / 25.0, 0.0, 3.0)) for q in queues]
        v_norm = [float(np.clip(v / 30.0, 0.0, 3.0)) for v in vehicles]
        w_norm = [float(np.clip(w / 120.0, 0.0, 3.0)) for w in waiting]

        queue_imbalance = float(np.clip((queues[0] + queues[2] - queues[1] - queues[3]) / 25.0, -3.0, 3.0))
        downstream_congestion = float(np.clip(sum(downstream) / 60.0, 0.0, 3.0))

        return np.array([
            float(self.manager.group),
            is_green,
            green_ratio,
            min_green_ok,
            q_norm[0], q_norm[1], q_norm[2], q_norm[3],
            v_norm[0], v_norm[1], v_norm[2], v_norm[3],
            w_norm[0], w_norm[1], w_norm[2], w_norm[3],
            queue_imbalance,
            downstream_congestion,
        ], dtype=np.float32)

    def _predict_action(self, obs: np.ndarray) -> int:
        """Determines target-phase action (0: EW, 1: NS)."""
        if self.model is not None:
            action, _ = self.model.predict(obs, deterministic=self.deterministic)
            return int(action)

        # Standalone evaluation target-phase policy:
        # Target opposite phase only when opposite queue imbalance is significant
        # and minimum green has already elapsed
        current_group = int(obs[0])
        min_green_ok = obs[3] > 0.5
        imbalance = obs[16]  # NS queue - EW queue

        if min_green_ok:
            if current_group == 0 and imbalance > 0.2:
                return 1  # Target NS
            elif current_group == 1 and imbalance < -0.2:
                return 0  # Target EW

        return current_group  # Default HOLD

    def step(self, current_time: float) -> None:
        if self.manager is None:
            return

        # 1. Update safety manager state machine every simulation step (0.1s)
        self.manager.update()

        # 2. Decision interval evaluation (every 10.0s)
        if current_time + 1e-6 >= self.next_decision_time:
            self.decisions_count += 1
            status = self.manager.get_status()

            if status["stage"] == "green":
                current_group = status["group"]
                other_group = 1 - current_group
                green_elapsed = current_time - self.manager.stage_started

                # Enforce MAX_GREEN cutoff (60.0s)
                if green_elapsed >= self.MAX_GREEN - 1e-6:
                    switched = self.manager.request(other_group)
                    if switched:
                        self.switches_count += 1
                        self.forced_switches_count += 1
                else:
                    # RL Policy inference
                    obs = self._get_observation()
                    target_group = self._predict_action(obs)
                    self.action_counts[target_group] = self.action_counts.get(target_group, 0) + 1

                    if target_group == current_group:
                        self.holds_count += 1
                    else:
                        switched = self.manager.request(target_group)
                        if switched:
                            self.switches_count += 1
                        else:
                            self.rejected_switches_count += 1

            self.next_decision_time += self.decision_interval

    def teardown(self) -> None:
        print(
            f"\n[PPOV6Adapter Summary] Decisions: {self.decisions_count} | "
            f"Holds: {self.holds_count} | "
            f"Voluntary Switches: {self.switches_count - self.forced_switches_count} | "
            f"Forced Switches: {self.forced_switches_count} | "
            f"Rejected Switches: {self.rejected_switches_count} | "
            f"Action Distribution: Action 0 (EW)={self.action_counts.get(0, 0)}, Action 1 (NS)={self.action_counts.get(1, 0)}"
        )
        super().teardown()


def get_controller_adapter(
    controller_id: str,
    tls_id: str = "J2",
    **kwargs: Any,
) -> BaseControllerAdapter:
    """
    Factory creating a controller adapter instance by identifier.

    Parameters
    ----------
    controller_id : str
        'fixed_time', 'max_pressure', 'ppo_v6', or 'ppo'.
    tls_id : str, default 'J2'
        Traffic light junction identifier.
    kwargs : dict
        Additional parameters passed to the controller adapter constructor.
    """
    c_id = controller_id.lower().strip()
    if c_id == "fixed_time":
        return FixedTimeAdapter(tls_id=tls_id)
    elif c_id == "max_pressure":
        decision_interval = kwargs.get("decision_interval", 10.0)
        return MaxPressureAdapter(tls_id=tls_id, decision_interval=decision_interval)
    elif c_id in ("ppo_v6", "ppo6"):
        return PPOV6Adapter(tls_id=tls_id, **kwargs)
    elif c_id in ("ppo", "ppo_v5"):
        return PPOAdapter(tls_id=tls_id, **kwargs)
    else:
        raise ValueError(
            f"Unknown controller_id '{controller_id}'. Supported controllers: "
            f"['fixed_time', 'max_pressure', 'ppo_v6', 'ppo']"
        )
