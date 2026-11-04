"""Smoke tests for PPO V5; run from repository root with SUMO in PATH."""
import sys
from pathlib import Path

from stable_baselines3.common.env_checker import check_env

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "sumo_simulation" / "controllers"))
from ppo_env_v5 import SumoPPOEnvV5  # noqa: E402

ROUTES = sorted(
    (ROOT / "sumo_simulation" / "training_routes").glob("traffic_S*_seed*.rou.xml")
)
assert len(ROUTES) == 20, f"Expected 20 training routes, found {len(ROUTES)}"


def make_env(end_time):
    return SumoPPOEnvV5(route_files=[ROUTES[0]], seed=777, end_time=end_time)


def check_reward(info, reward):
    components = (
        info["reward_queue_cost"]
        + info["reward_waiting_cost"]
        + info["reward_switch_cost"]
    )
    assert abs(reward + components) < 1e-5, (reward, components)
    assert info["switches"] == (
        info["voluntary_switches"] + info["forced_switches"]
    )


# Standard Gymnasium validation (may restart SUMO several times).
env = make_env(120)
try:
    check_env(env, warn=True)
    print("Gymnasium validation PASSED")
finally:
    env.close()

# Always HOLD: one or more mandatory changes by 90 seconds.
env = make_env(90)
try:
    obs, _ = env.reset(seed=777)
    assert obs.shape == (14,)
    for _ in range(9):
        obs, reward, terminated, truncated, info = env.step(0)
        check_reward(info, reward)
    assert info["total_holds"] == 9
    assert info["total_voluntary_switches"] == 0
    assert info["total_forced_switches"] >= 1
    print("HOLD/max-green test PASSED", info["total_forced_switches"])
finally:
    env.close()

# Requesting a change at initial t=0 must be rejected (minimum green).
env = make_env(30)
try:
    obs, _ = env.reset(seed=777)
    obs, reward, _, _, info = env.step(1)
    check_reward(info, reward)
    assert info["voluntary_switches"] == 0
    assert info["rejected_switch_requests"] == 1
    assert info["reward_switch_cost"] == 0
    obs, reward, _, _, info = env.step(1)
    check_reward(info, reward)
    assert info["voluntary_switches"] == 1
    assert info["reward_switch_cost"] == 5.0
    print("Rejected/accepted switch tests PASSED")
finally:
    env.close()

print("PPO V5 AUDIT VALIDATION PASSED")
