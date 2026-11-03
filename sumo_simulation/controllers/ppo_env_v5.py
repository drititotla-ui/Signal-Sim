"""Auditable SUMO PPO V5 environment for the verified J2 LHT junction.

Place alongside ppo_env_v2.py and signal_manager.py.

Action: 0 HOLD, 1 REQUEST SWITCH. Uses the existing SignalManager without edits.
Reward defaults preserve V4 economics: -(mean_queue + .005*mean_waiting +
5*accepted_voluntary_switches). Mandatory max-green changes are unpenalized.
"""

import numpy as np
import traci
from gymnasium import spaces

from ppo_env_v2 import SumoPPOEnvV2


class SumoPPOEnvV5(SumoPPOEnvV2):
    def __init__(
        self,
        *,
        queue_weight=1.0,
        waiting_weight=0.005,
        voluntary_switch_cost=5.0,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.queue_weight = float(queue_weight)
        self.waiting_weight = float(waiting_weight)
        self.voluntary_switch_cost = float(voluntary_switch_cost)
        if min(self.queue_weight, self.waiting_weight, self.voluntary_switch_cost) < 0:
            raise ValueError("Reward weights must be nonnegative")
        self.observation_space = spaces.Box(
            low=-np.inf, high=np.inf, shape=(14,), dtype=np.float32
        )
        self._clear_counters()

    def _clear_counters(self):
        self.total_holds = 0
        self.total_switch_requests = 0
        self.total_voluntary_switches = 0
        self.total_forced_switches = 0
        self.total_rejected_requests = 0

    def _observe(self):
        base = super()._observe()
        # base[:4] is -E1,-E2,-E3,-E4 halting count divided by 20.
        # GROUP_1 is NS: -E1,-E3; GROUP_0 is EW: -E2,-E4.
        imbalance = (base[0] + base[2]) - (base[1] + base[3])
        return np.append(base, imbalance).astype(np.float32)

    def reset(self, *, seed=None, options=None):
        self._clear_counters()
        return super().reset(seed=seed, options=options)

    def step(self, action):
        if not self.running:
            raise RuntimeError("Call reset() first")
        if not self.action_space.contains(action):
            raise ValueError(f"Invalid action: {action}")

        action = int(action)
        voluntary = 0
        forced = 0
        rejected = 0
        self.total_holds += int(action == 0)

        if action == 1:
            self.total_switch_requests += 1
            # Only accepted requests incur a switching penalty.
            # Calling request even during transition is unnecessary: it
            # returns False in signal_manager.py and is counted as rejected.
            if self.manager.stage == "green" and self.manager.request(
                1 - self.manager.group
            ):
                voluntary = 1
            else:
                rejected = 1

        target_time = min(
            self.end_time,
            traci.simulation.getTime() + self.decision_interval,
        )
        queue_sum = 0.0
        waiting_sum = 0.0
        samples = 0
        ticks = 0

        while traci.simulation.getTime() < target_time - 1e-6:
            if self.manager.stage == "green":
                elapsed = traci.simulation.getTime() - self.manager.stage_started
                if elapsed >= self.manager.MAX_GREEN - 1e-6:
                    if self.manager.request(1 - self.manager.group):
                        forced += 1

            traci.simulationStep()
            self.manager.update()
            ticks += 1
            if ticks % 10 == 0:
                queues, waiting = self._traffic()
                queue_sum += float(queues.sum())
                waiting_sum += float(waiting.sum())
                samples += 1

        if samples == 0:
            queues, waiting = self._traffic()
            queue_sum = float(queues.sum())
            waiting_sum = float(waiting.sum())
            samples = 1

        avg_queue = queue_sum / samples
        avg_waiting = waiting_sum / samples
        queue_cost = self.queue_weight * avg_queue
        waiting_cost = self.waiting_weight * avg_waiting
        switching_cost = self.voluntary_switch_cost * voluntary
        reward = -(queue_cost + waiting_cost + switching_cost)

        self.total_voluntary_switches += voluntary
        self.total_forced_switches += forced
        self.total_rejected_requests += rejected

        truncated = traci.simulation.getTime() >= self.end_time - 1e-6
        observation = self._observe()
        info = {
            "time": traci.simulation.getTime(),
            "route_file": self.current_route.name,
            "green_group": self.manager.group,
            "stage": self.manager.stage,
            "queue": avg_queue,
            "waiting": avg_waiting,
            "reward_queue_cost": queue_cost,
            "reward_waiting_cost": waiting_cost,
            "reward_switch_cost": switching_cost,
            "reward_total": reward,
            "ppo_action": action,
            "switch_requested": int(action == 1),
            "voluntary_switches": voluntary,
            "forced_switches": forced,
            "rejected_switch_requests": rejected,
            "switches": voluntary + forced,
            "total_holds": self.total_holds,
            "total_switch_requests": self.total_switch_requests,
            "total_voluntary_switches": self.total_voluntary_switches,
            "total_forced_switches": self.total_forced_switches,
            "total_rejected_switch_requests": self.total_rejected_requests,
            "queue_imbalance": float(observation[13]),
        }
        return observation, float(reward), False, truncated, info
