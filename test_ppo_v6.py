"""
Comprehensive Unit Tests for PPO V6 Environment & Control Mechanics.

Tests requirements:
1. Environment initialization and reset.
2. Both target-phase actions (0: EW, 1: NS).
3. HOLD behavior when requested target is already active (Group 0 -> Action 0).
4. Minimum-green enforcement (Action 1 rejected when elapsed < 10.0s).
5. Transition safety (Yellow 3.0s -> All-Red 1.0s -> Next Green).
6. Reward accounting:
   - Valid voluntary switch: 5.0 cost.
   - Invalid early switch request: 2.0 penalty.
   - Unpenalized target continuation during transition.
   - Penalty for reversing transition mid-flight.
   - Forced max-green (60s) switch unpenalized.
7. Observation space shape, values, and normalization.
"""

from typing import Any, Dict, List
import numpy as np
import pytest

from sumo_simulation.controllers.ppo_env_v6 import SumoPPOEnvV6
from sumo_simulation.controllers.signal_manager import SignalManager


class MockPhase:
    def __init__(self, state: str, duration: float):
        self.state = state
        self.duration = duration


class MockProgramLogic:
    def __init__(self, programID: str, phases: List[MockPhase]):
        self.programID = programID
        self.phases = phases


class MockTraCIConnection:
    """Simulates SUMO TraCI interface for unit testing SignalManager and SumoPPOEnvV6."""

    EXPECTED_STATES = [
        "GGGGgrrrrrGGGGgrrrrr",
        "yyyyyrrrrryyyyyrrrrr",
        "rrrrrrrrrrrrrrrrrrrr",
        "rrrrrGGGGgrrrrrGGGGg",
        "rrrrryyyyyrrrrryyyyy",
        "rrrrrrrrrrrrrrrrrrrr",
    ]

    def __init__(self, delta_t: float = 0.1):
        self.time: float = 0.0
        self.delta_t: float = delta_t
        self.current_phase: int = 0
        self.phase_duration: float = 10000.0

        # Sub-modules
        self.simulation = self
        self.trafficlight = self
        self.edge = self

        self.queues: Dict[str, int] = {"-E1": 5, "-E2": 3, "-E3": 4, "-E4": 2}
        self.vehicles: Dict[str, int] = {"-E1": 8, "-E2": 6, "-E3": 7, "-E4": 5, "E1": 2, "E2": 3, "E3": 1, "E4": 2}
        self.waiting: Dict[str, float] = {"-E1": 45.0, "-E2": 20.0, "-E3": 35.0, "-E4": 15.0}

    def getTime(self) -> float:
        return self.time

    def simulationStep(self) -> None:
        self.time = round(self.time + self.delta_t, 4)

    def getAllProgramLogics(self, tls_id: str) -> List[MockProgramLogic]:
        phases = [MockPhase(state, 30.0) for state in self.EXPECTED_STATES]
        return [MockProgramLogic("0", phases)]

    def getPhase(self, tls_id: str) -> int:
        return self.current_phase

    def setPhase(self, tls_id: str, phase: int) -> None:
        self.current_phase = phase

    def setPhaseDuration(self, tls_id: str, duration: float) -> None:
        self.phase_duration = duration

    def getLastStepHaltingNumber(self, edge_id: str) -> int:
        return self.queues.get(edge_id, 0)

    def getLastStepVehicleNumber(self, edge_id: str) -> int:
        return self.vehicles.get(edge_id, 0)

    def getWaitingTime(self, edge_id: str) -> float:
        return self.waiting.get(edge_id, 0.0)


def test_ppo_v6_specifications():
    """Verify action space, observation space and default parameters."""
    env = SumoPPOEnvV6(connection=MockTraCIConnection())
    assert env.action_space.n == 2
    assert env.observation_space.shape == (18,)
    assert env.observation_space.dtype == np.float32
    assert env.voluntary_switch_cost == 5.0
    assert env.invalid_switch_penalty == 2.0
    assert env.queue_weight == 1.0
    assert env.waiting_weight == 0.005


def test_env_reset_and_initial_state():
    """Test environment reset returns valid initial observation and metadata."""
    mock_conn = MockTraCIConnection()
    env = SumoPPOEnvV6(connection=mock_conn)

    obs, info = env.reset()
    assert obs.shape == (18,)
    assert obs.dtype == np.float32
    assert info["green_group"] == 0  # Initial green is EW (0)
    assert info["stage"] == "green"
    assert obs[0] == 0.0  # group
    assert obs[1] == 1.0  # is_green
    assert obs[2] == 0.0  # green_ratio at time 0
    assert obs[3] == 0.0  # min_green_ok (elapsed 0 < 10s)


def test_hold_action_group_0():
    """Test Action 0 (Target EW) while EW Green is active: valid HOLD, no switch cost."""
    mock_conn = MockTraCIConnection()
    env = SumoPPOEnvV6(connection=mock_conn)
    env.reset()

    # Step with target 0 (matches active group 0)
    obs, reward, terminated, truncated, info = env.step(action=0)

    assert info["green_group"] == 0
    assert info["stage"] == "green"
    assert info["voluntary_switch"] == 0
    assert info["invalid_switch"] == 0
    assert info["reward_switch_cost"] == 0.0
    assert info["reward_invalid_cost"] == 0.0
    assert info["total_holds"] == 1
    assert pytest.approx(mock_conn.time, 1e-4) == 10.0  # Stepped 10.0s


def test_invalid_early_switch_request():
    """
    Test Action 1 (Target NS) when green elapsed < 10.0s:
    Min green constraint is not met, so switch is rejected and penalized with 2.0.
    """
    mock_conn = MockTraCIConnection()
    env = SumoPPOEnvV6(connection=mock_conn)
    env.reset()

    # At time 0, elapsed is 0 < 10s. Action 1 requests switch to NS.
    obs, reward, terminated, truncated, info = env.step(action=1)

    assert info["invalid_switch"] == 1
    assert info["voluntary_switch"] == 0
    assert info["reward_invalid_cost"] == 2.0
    assert info["reward_switch_cost"] == 0.0
    assert info["total_rejected_requests"] == 1
    # Check that invalid penalty is deducted in total reward
    expected_penalty = -(info["reward_queue_cost"] + info["reward_waiting_cost"] + 2.0)
    assert pytest.approx(reward, 1e-4) == expected_penalty


def test_valid_switch_request_after_min_green():
    """
    Test Action 1 (Target NS) after min green (10.0s) is satisfied:
    Switch is accepted, transitions to yellow, and incurs voluntary switch cost of 5.0.
    """
    mock_conn = MockTraCIConnection()
    env = SumoPPOEnvV6(connection=mock_conn)
    env.reset()

    # Step 1: HOLD for 10.0s to satisfy min-green
    env.step(action=0)
    assert pytest.approx(mock_conn.time, 1e-4) == 10.0
    assert env.manager.stage == "green"
    assert (mock_conn.time - env.manager.stage_started) >= 10.0

    # Step 2: Request switch to group 1 (NS)
    obs, reward, terminated, truncated, info = env.step(action=1)

    assert info["voluntary_switch"] == 1
    assert info["invalid_switch"] == 0
    assert info["reward_switch_cost"] == 5.0
    assert info["reward_invalid_cost"] == 0.0
    assert info["total_voluntary_switches"] == 1

    # Check signal transition safety progression:
    # Yellow runs 3.0s, All-Red runs 1.0s, then Green(1) begins.
    # At the end of the 10s interval, signal has completed yellow + all-red and is green for NS!
    assert info["green_group"] == 1
    assert info["stage"] == "green"
    assert mock_conn.current_phase == 3  # Phase 3 is NS Green


def test_transition_continuity_no_penalty():
    """
    Test that targeting the pending group during transition incurs NO penalty.
    """
    mock_conn = MockTraCIConnection()
    env = SumoPPOEnvV6(connection=mock_conn)
    env.reset()

    # Fast forward to 10s
    mock_conn.time = 10.0
    env.manager.stage_started = 0.0

    # Trigger switch to group 1 manually to enter yellow
    env.manager.request(1)
    assert env.manager.stage == "yellow"
    assert env.manager.pending_group == 1

    # In yellow stage, action 1 (targeting pending group) should NOT incur invalid penalty
    obs, reward, terminated, truncated, info = env.step(action=1)
    assert info["invalid_switch"] == 0
    assert info["reward_invalid_cost"] == 0.0


def test_transition_reversal_attempt_penalized():
    """
    Test that attempting to reverse or abort transition mid-flight incurs invalid penalty.
    """
    mock_conn = MockTraCIConnection()
    env = SumoPPOEnvV6(connection=mock_conn)
    env.reset()

    # Fast forward to 10s
    mock_conn.time = 10.0
    env.manager.stage_started = 0.0

    # Trigger switch to group 1 to enter yellow
    env.manager.request(1)
    assert env.manager.stage == "yellow"
    assert env.manager.pending_group == 1

    # In yellow stage towards 1, targeting group 0 is an illegal reversal attempt
    obs, reward, terminated, truncated, info = env.step(action=0)
    assert info["invalid_switch"] == 1
    assert info["reward_invalid_cost"] == 2.0


def test_max_green_forced_switch_unpenalized():
    """
    Test that exceeding MAX_GREEN (60.0s) forces a transition without voluntary switch cost.
    """
    mock_conn = MockTraCIConnection()
    env = SumoPPOEnvV6(connection=mock_conn)
    env.reset()

    # Repeatedly HOLD for 6 intervals (60s total)
    for _ in range(6):
        obs, reward, terminated, truncated, info = env.step(action=0)

    # Next step: green has elapsed 60s, so forced switch must occur during interval
    obs, reward, terminated, truncated, info = env.step(action=0)
    assert info["forced_switch"] >= 1
    assert info["voluntary_switch"] == 0
    assert info["reward_switch_cost"] == 0.0


def test_reward_weights_validation():
    """Verify negative weights raise ValueError."""
    with pytest.raises(ValueError):
        SumoPPOEnvV6(voluntary_switch_cost=-1.0)
    with pytest.raises(ValueError):
        SumoPPOEnvV6(invalid_switch_penalty=-0.5)


def test_sb3_ppo_model_inference():
    """
    Test 7: Verify Stable-Baselines3 PPO model initialization, observation compatibility,
    and target-phase action prediction (0 or 1).
    """
    from stable_baselines3 import PPO

    mock_conn = MockTraCIConnection()
    env = SumoPPOEnvV6(connection=mock_conn)
    obs, info = env.reset()

    # Initialize a lightweight PPO agent with MlpPolicy
    model = PPO("MlpPolicy", env, n_steps=64, n_epochs=1, batch_size=32, verbose=0)
    action, _states = model.predict(obs, deterministic=True)

    assert int(action) in (0, 1)

    # Step the environment with model's predicted action
    next_obs, reward, terminated, truncated, step_info = env.step(action)
    assert next_obs.shape == (18,)
    assert isinstance(reward, float)
    assert step_info["stage"] in ("green", "yellow", "all_red")


def test_standalone_env_lifecycle_and_vehicle_loading():
    """
    Verifies that SumoPPOEnvV6 in standalone mode:
    1. Successfully starts SUMO with vehicle type definitions (-a vTypes.add.xml).
    2. Runs through vehicle departures without 'vehicle type unknown' error.
    3. Successfully resets across multiple consecutive episodes (cleaning up TraCI connection and process).
    4. Cleanly closes resources on close().
    """
    net_file = "lht_working/candidate/signalsim_lht_timed.net.xml"
    route_file = "simulation/routes/route_scenario_S1_seed42.rou.xml"

    env = SumoPPOEnvV6(
        net_file=net_file,
        route_file=route_file,
        end_time=100.0,
        decision_interval=10.0,
    )

    try:
        # Episode 1
        obs1, info1 = env.reset(seed=42)
        assert obs1.shape == (18,)
        assert info1["green_group"] == 0

        # Step past vehicle injection timesteps (truck departs at 2.99s, bike at 3.21s)
        # Stepping 2 decision intervals = 20.0s simulation time
        for _ in range(2):
            obs, reward, terminated, truncated, step_info = env.step(action=0)
            assert step_info["stage"] in ("green", "yellow", "all_red")

        # Episode 2 (Repeated reset with clean TraCI reconnection)
        obs2, info2 = env.reset(seed=101)
        assert obs2.shape == (18,)
        assert info2["green_group"] == 0

        for _ in range(2):
            obs, reward, terminated, truncated, step_info = env.step(action=0)
            assert step_info["stage"] in ("green", "yellow", "all_red")

    finally:
        env.close()


if __name__ == "__main__":
    pytest.main(["-v", __file__])
