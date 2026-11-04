"""
Standalone Gymnasium Environment for PPO V6 in SIGNALSIM-INDIA.

Key Improvements over V5:
1. Completely independent of missing ppo_env_v2.py; inherits directly from gymnasium.Env.
2. Target-Phase Action Space:
   - Action 0: EW Green (Group 0)
   - Action 1: NS Green (Group 1)
   - Target == Active Group -> Valid HOLD (no switch cost).
   - Target != Active Group -> Switch requested via SignalManager.
3. Closes the 'Free Rejected Switch' loophole:
   - Valid voluntary switch: voluntary_switch_cost = 5.0
   - Invalid early switch request (min_green < 10s): invalid_switch_penalty = 2.0
   - Transition safety: Yellow (3s) -> All-Red (1s) -> Green
   - During yellow/all-red transition:
     * If requested target matches pending_group: no penalty (transition in progress).
     * If requested target opposes pending_group: invalid_switch_penalty = 2.0 (cannot abort).
4. Observation Space:
   - 18 normalized features capturing active group, stage, elapsed green ratio, min green readiness,
     incoming halting queues, vehicle counts, waiting times, queue imbalance, and downstream congestion.
5. Signal Safety:
   - Fully enforces SignalManager constraints (Min Green 10s, Max Green 60s, Yellow 3s, All-Red 1s).
"""

import os
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Tuple, Union

import gymnasium as gym
from gymnasium import spaces
import numpy as np
import traci

from sumo_simulation.controllers.signal_manager import SignalManager


class SumoPPOEnvV6(gym.Env):
    """
    Gymnasium environment for PPO V6 traffic signal control at junction J2.
    """

    metadata = {"render_modes": ["human"], "render_fps": 10}

    INCOMING_EDGES = ["-E1", "-E2", "-E3", "-E4"]  # North, East, South, West
    OUTGOING_EDGES = ["E1", "E2", "E3", "E4"]

    def __init__(
        self,
        net_file: Optional[Union[str, Path]] = None,
        route_file: Optional[Union[str, Path]] = None,
        additional_file: Optional[Union[str, Path]] = None,
        tls_id: str = "J2",
        end_time: float = 3600.0,
        delta_t: float = 0.1,
        decision_interval: float = 10.0,
        queue_weight: float = 1.0,
        waiting_weight: float = 0.005,
        voluntary_switch_cost: float = 5.0,
        invalid_switch_penalty: float = 2.0,
        connection: Optional[Any] = None,
        use_gui: bool = False,
        sumo_binary: Optional[str] = None,
    ):
        super().__init__()

        self.net_file = Path(net_file) if net_file else None
        self.route_file = Path(route_file) if route_file else None

        if additional_file is not None:
            self.additional_file = Path(additional_file)
        else:
            default_add = Path(__file__).resolve().parent.parent / "vTypes.add.xml"
            if not default_add.is_file():
                default_add = Path("sumo_simulation/vTypes.add.xml")
            self.additional_file = default_add

        self.tls_id = tls_id
        self.end_time = float(end_time)
        self.delta_t = float(delta_t)
        self.decision_interval = float(decision_interval)

        self.queue_weight = float(queue_weight)
        self.waiting_weight = float(waiting_weight)
        self.voluntary_switch_cost = float(voluntary_switch_cost)
        self.invalid_switch_penalty = float(invalid_switch_penalty)

        if min(self.queue_weight, self.waiting_weight, self.voluntary_switch_cost, self.invalid_switch_penalty) < 0:
            raise ValueError("Reward weights and penalties must be non-negative.")

        # Target-phase action space: 0 = EW Green (Group 0), 1 = NS Green (Group 1)
        self.action_space = spaces.Discrete(2)

        # Observation space: 18 continuous features normalized around [-2.0, 2.0]
        self.observation_space = spaces.Box(
            low=-5.0,
            high=5.0,
            shape=(18,),
            dtype=np.float32,
        )

        self.use_gui = use_gui
        self.sumo_binary = sumo_binary
        self.conn = connection
        self._owns_connection = connection is None
        self._sumo_started = False
        self._label: Optional[str] = None
        self.manager: Optional[SignalManager] = None

        self._clear_counters()

    def _clear_counters(self) -> None:
        self.total_holds = 0
        self.total_switch_requests = 0
        self.total_voluntary_switches = 0
        self.total_forced_switches = 0
        self.total_rejected_requests = 0

    def _start_sumo(self, seed: Optional[int] = None) -> None:
        if self.net_file is None or not self.net_file.exists():
            raise FileNotFoundError(f"SUMO network file not found: {self.net_file}")
        if self.route_file is None or not self.route_file.exists():
            raise FileNotFoundError(f"SUMO route file not found: {self.route_file}")
        if self.additional_file is None or not self.additional_file.exists():
            raise FileNotFoundError(f"SUMO additional vehicle types file not found: {self.additional_file}")

        binary = self.sumo_binary
        if binary is None:
            try:
                from src.experiments.sumo_manager import find_sumo_binary
                binary = find_sumo_binary(gui=self.use_gui)
            except Exception:
                sumo_home = os.environ.get("SUMO_HOME", "")
                exe_name = "sumo-gui.exe" if self.use_gui else "sumo.exe"
                if sumo_home:
                    binary = str(Path(sumo_home) / "bin" / exe_name)
                else:
                    binary = exe_name

        self._label = f"ppo_v6_{id(self)}_{int(time.time() * 1000)}"

        cmd = [
            str(binary),
            "-n", str(self.net_file),
            "-r", str(self.route_file),
            "-a", str(self.additional_file),
            "--step-length", str(self.delta_t),
            "--waiting-time-memory", "1000",
            "--time-to-teleport", "-1",
            "--collision.check-junctions", "true",
            "--collision.action", "warn",
            "--no-step-log", "true",
            "--start", "true",
            "--quit-on-end", "true",
        ]
        if seed is not None:
            cmd.extend(["--seed", str(seed)])

        try:
            traci.start(cmd, label=self._label)
            self.conn = traci.getConnection(self._label)
            self._sumo_started = True
        except Exception as err:
            self._cleanup_sumo()
            raise RuntimeError(f"Failed to start SUMO TraCI instance '{self._label}': {err}") from err

    def _cleanup_sumo(self) -> None:
        if self._owns_connection and self._sumo_started:
            if self.conn is not None:
                try:
                    self.conn.close()
                except Exception:
                    pass
            elif self._label is not None:
                try:
                    traci.getConnection(self._label).close()
                except Exception:
                    pass
            self.conn = None
            self._sumo_started = False

    def _get_aggregate_traffic(self) -> Tuple[float, float]:
        """Returns total halting queue and total waiting time across all 4 incoming edges."""
        total_queue = 0.0
        total_waiting = 0.0
        for edge in self.INCOMING_EDGES:
            total_queue += float(self.conn.edge.getLastStepHaltingNumber(edge))
            total_waiting += float(self.conn.edge.getWaitingTime(edge))
        return total_queue, total_waiting

    def _get_observation(self) -> np.ndarray:
        """
        Constructs normalized 18-element state vector:
        [0]: current green group (0.0=EW, 1.0=NS)
        [1]: stage is green (1.0) or transition (0.0)
        [2]: green elapsed time ratio (0.0 to 1.0, capped at max_green=60s)
        [3]: min green satisfied (1.0 if elapsed >= 10s and stage == green, else 0.0)
        [4..7]: incoming queues [-E1 (N), -E2 (E), -E3 (S), -E4 (W)] / 25.0
        [8..11]: incoming total vehicles [-E1, -E2, -E3, -E4] / 30.0
        [12..15]: incoming waiting times [-E1, -E2, -E3, -E4] / 120.0s
        [16]: queue imbalance: (NS_queues - EW_queues) / 25.0
        [17]: downstream congestion: total vehicles on [E1, E2, E3, E4] / 60.0
        """
        current_time = self.conn.simulation.getTime()
        stage_elapsed = current_time - self.manager.stage_started
        is_green = 1.0 if self.manager.stage == "green" else 0.0
        green_ratio = float(np.clip(stage_elapsed / self.manager.MAX_GREEN, 0.0, 1.0)) if is_green else 0.0
        min_green_ok = 1.0 if (is_green and stage_elapsed >= self.manager.MIN_GREEN) else 0.0

        queues = [float(self.conn.edge.getLastStepHaltingNumber(e)) for e in self.INCOMING_EDGES]
        vehicles = [float(self.conn.edge.getLastStepVehicleNumber(e)) for e in self.INCOMING_EDGES]
        waiting = [float(self.conn.edge.getWaitingTime(e)) for e in self.INCOMING_EDGES]
        downstream = [float(self.conn.edge.getLastStepVehicleNumber(e)) for e in self.OUTGOING_EDGES]

        # Normalized features
        q_norm = [float(np.clip(q / 25.0, 0.0, 3.0)) for q in queues]
        v_norm = [float(np.clip(v / 30.0, 0.0, 3.0)) for v in vehicles]
        w_norm = [float(np.clip(w / 120.0, 0.0, 3.0)) for w in waiting]

        # NS: -E1 (index 0) + -E3 (index 2); EW: -E2 (index 1) + -E4 (index 3)
        queue_imbalance = float(np.clip((queues[0] + queues[2] - queues[1] - queues[3]) / 25.0, -3.0, 3.0))
        downstream_congestion = float(np.clip(sum(downstream) / 60.0, 0.0, 3.0))

        obs = np.array([
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

        return obs

    def reset(
        self,
        *,
        seed: Optional[int] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        super().reset(seed=seed)
        self._clear_counters()

        if self._owns_connection:
            if self._sumo_started:
                self._cleanup_sumo()
            self._start_sumo(seed=seed)

        self.manager = SignalManager(tls_id=self.tls_id, connection=self.conn)
        obs = self._get_observation()
        info = {
            "time": self.conn.simulation.getTime(),
            "green_group": self.manager.group,
            "stage": self.manager.stage,
        }
        return obs, info

    def step(self, action: Union[int, np.integer]) -> Tuple[np.ndarray, float, bool, bool, Dict[str, Any]]:
        if self.manager is None:
            raise RuntimeError("Environment must be reset() before calling step().")

        action = int(action)
        if action not in (0, 1):
            raise ValueError(f"Action must be 0 (EW) or 1 (NS), received {action}.")

        target_group = action
        current_group = self.manager.group
        current_stage = self.manager.stage
        current_time = self.conn.simulation.getTime()
        stage_elapsed = current_time - self.manager.stage_started

        voluntary_switch = 0
        forced_switch = 0
        invalid_switch = 0

        # Action evaluation
        if current_stage == "green":
            if target_group == current_group:
                # Valid HOLD command
                self.total_holds += 1
            else:
                # Switch requested to the opposite group
                self.total_switch_requests += 1
                if stage_elapsed >= self.manager.MIN_GREEN - 1e-6:
                    switched = self.manager.request(target_group)
                    if switched:
                        voluntary_switch = 1
                        self.total_voluntary_switches += 1
                    else:
                        invalid_switch = 1
                        self.total_rejected_requests += 1
                else:
                    # Min green not satisfied -> invalid early switch request penalized
                    invalid_switch = 1
                    self.total_rejected_requests += 1
        else:
            # Stage is yellow or all-red (transition already in progress)
            self.total_switch_requests += 1
            if self.manager.pending_group == target_group:
                # Action aligns with already-pending transition: no penalty
                pass
            else:
                # Attempting to reverse or abort transition mid-flight: invalid request
                invalid_switch = 1
                self.total_rejected_requests += 1

        # Step simulation across decision interval (10.0s)
        target_sim_time = min(
            self.end_time,
            current_time + self.decision_interval,
        )

        queue_samples: List[float] = []
        waiting_samples: List[float] = []

        while self.conn.simulation.getTime() < target_sim_time - 1e-6:
            # Max green enforcement (60s cutoff)
            if self.manager.stage == "green":
                elapsed = self.conn.simulation.getTime() - self.manager.stage_started
                if elapsed >= self.manager.MAX_GREEN - 1e-6:
                    if self.manager.request(1 - self.manager.group):
                        forced_switch += 1
                        self.total_forced_switches += 1

            self.conn.simulationStep()
            self.manager.update()

            # Sample traffic metrics every 1.0s (every 10 ticks at 0.1s dt)
            sim_t = self.conn.simulation.getTime()
            if int(round(sim_t * 10)) % 10 == 0:
                q, w = self._get_aggregate_traffic()
                queue_samples.append(q)
                waiting_samples.append(w)

        if not queue_samples:
            q, w = self._get_aggregate_traffic()
            queue_samples.append(q)
            waiting_samples.append(w)

        avg_queue = float(np.mean(queue_samples))
        avg_waiting = float(np.mean(waiting_samples))

        # Reward formulation
        queue_cost = self.queue_weight * avg_queue
        waiting_cost = self.waiting_weight * avg_waiting
        switch_cost = self.voluntary_switch_cost * voluntary_switch
        invalid_cost = self.invalid_switch_penalty * invalid_switch

        reward = -(queue_cost + waiting_cost + switch_cost + invalid_cost)

        truncated = self.conn.simulation.getTime() >= self.end_time - 1e-6
        terminated = False
        obs = self._get_observation()

        info = {
            "time": self.conn.simulation.getTime(),
            "green_group": self.manager.group,
            "stage": self.manager.stage,
            "avg_queue": avg_queue,
            "avg_waiting": avg_waiting,
            "voluntary_switch": voluntary_switch,
            "forced_switch": forced_switch,
            "invalid_switch": invalid_switch,
            "reward_queue_cost": queue_cost,
            "reward_waiting_cost": waiting_cost,
            "reward_switch_cost": switch_cost,
            "reward_invalid_cost": invalid_cost,
            "reward_total": reward,
            "total_holds": self.total_holds,
            "total_switch_requests": self.total_switch_requests,
            "total_voluntary_switches": self.total_voluntary_switches,
            "total_forced_switches": self.total_forced_switches,
            "total_rejected_requests": self.total_rejected_requests,
        }

        return obs, float(reward), terminated, truncated, info

    def close(self) -> None:
        self._cleanup_sumo()
