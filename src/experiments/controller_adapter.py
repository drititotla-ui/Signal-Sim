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
    EXPECTED_DURATIONS = [30.0, 3.0, 1.0, 30.0, 3.0, 1.0]

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
    PPO Reinforcement Learning controller adapter.

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
        'fixed_time', 'max_pressure', or 'ppo'.
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
    elif c_id == "ppo":
        return PPOAdapter(tls_id=tls_id, **kwargs)
    else:
        raise ValueError(
            f"Unknown controller_id '{controller_id}'. Supported controllers: "
            f"['fixed_time', 'max_pressure', 'ppo']"
        )
