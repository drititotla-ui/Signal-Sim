"""
PPO V6 Pilot Training Script for SIGNALSIM-INDIA.

Executes a 5,000-timestep pilot training run using the verified standalone SumoPPOEnvV6.
- Fresh model initialized (MlpPolicy, ent_coef=0.01).
- Training logs saved separately in results/training_logs/ppo_v6_pilot/.
- Final model saved to models/ppo_v6_model.zip.
- Existing benchmark summaries (master_summary.csv/json) remain untouched.
"""

import json
import os
from pathlib import Path
import time
from typing import Any, Dict, List

import numpy as np
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.monitor import Monitor

from sumo_simulation.controllers.ppo_env_v6 import SumoPPOEnvV6


class MetricsTrackingCallback(BaseCallback):
    """Tracks episode rewards, action counts, and switch statistics during training."""

    def __init__(self, log_dir: Path, verbose: int = 0):
        super().__init__(verbose)
        self.log_dir = log_dir
        self.episode_rewards: List[float] = []
        self.episode_lengths: List[int] = []
        self.action_counts: Dict[int, int] = {0: 0, 1: 0}
        self.total_voluntary_switches = 0
        self.total_forced_switches = 0
        self.total_rejected_requests = 0
        self.start_wall_time = time.time()
        self.episode_count = 0

    def _on_step(self) -> bool:
        # Record action taken
        actions = self.locals.get("actions")
        if actions is not None:
            for a in actions:
                act = int(a)
                self.action_counts[act] = self.action_counts.get(act, 0) + 1

        # Check for episode completion
        dones = self.locals.get("dones")
        infos = self.locals.get("infos")
        if dones is not None and infos is not None:
            for done, info in zip(dones, infos):
                if done:
                    self.episode_count += 1
                    ep_rew = info.get("episode", {}).get("r", None)
                    ep_len = info.get("episode", {}).get("l", None)
                    if ep_rew is not None:
                        self.episode_rewards.append(float(ep_rew))
                    if ep_len is not None:
                        self.episode_lengths.append(int(ep_len))

                    self.total_voluntary_switches += info.get("total_voluntary_switches", 0)
                    self.total_forced_switches += info.get("total_forced_switches", 0)
                    self.total_rejected_requests += info.get("total_rejected_requests", 0)

                    print(
                        f"[Episode {self.episode_count}] "
                        f"Timesteps: {self.num_timesteps} | "
                        f"Reward: {ep_rew:.1f} | "
                        f"Length: {ep_len} steps | "
                        f"Elapsed: {time.time() - self.start_wall_time:.1f}s"
                    )
        return True


def run_pilot_training(
    total_timesteps: int = 5000,
    model_output_path: str = "models/ppo_v6_model.zip",
    log_dir_path: str = "results/training_logs/ppo_v6_pilot",
) -> Dict[str, Any]:
    project_root = Path(__file__).resolve().parent
    net_file = project_root / "lht_working/candidate/signalsim_lht_timed.net.xml"
    route_file = project_root / "simulation/routes/route_scenario_S1_seed42.rou.xml"
    additional_file = project_root / "sumo_simulation/vTypes.add.xml"

    log_dir = project_root / log_dir_path
    log_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("SIGNALSIM-INDIA | PPO V6 Pilot Training (5,000 timesteps)")
    print("=" * 70)
    print(f"Network: {net_file.name}")
    print(f"Route:   {route_file.name}")
    print(f"Log Dir: {log_dir}")
    print(f"Target:  {model_output_path}")

    # Create and monitor standalone environment
    raw_env = SumoPPOEnvV6(
        net_file=net_file,
        route_file=route_file,
        additional_file=additional_file,
        end_time=3600.0,
        delta_t=0.1,
        decision_interval=10.0,
    )
    env = Monitor(raw_env, filename=str(log_dir / "monitor.csv"))

    # Instantiate fresh PPO model
    # Hyperparameters: non-zero entropy coefficient prevents policy collapse
    model = PPO(
        policy="MlpPolicy",
        env=env,
        learning_rate=3e-4,
        n_steps=128,
        batch_size=64,
        n_epochs=4,
        gamma=0.99,
        gae_lambda=0.95,
        clip_range=0.2,
        ent_coef=0.01,
        verbose=1,
        seed=42,
    )

    callback = MetricsTrackingCallback(log_dir=log_dir)

    start_time = time.time()
    try:
        model.learn(total_timesteps=total_timesteps, callback=callback)
    finally:
        env.close()

    total_duration = time.time() - start_time

    # Save model checkpoint
    model_path = project_root / model_output_path
    model_path.parent.mkdir(parents=True, exist_ok=True)
    model.save(str(model_path))

    checkpoint_size = model_path.stat().st_size

    # Summarize results
    total_actions = sum(callback.action_counts.values())
    act_0_pct = (callback.action_counts[0] / total_actions * 100) if total_actions > 0 else 0.0
    act_1_pct = (callback.action_counts[1] / total_actions * 100) if total_actions > 0 else 0.0

    summary = {
        "status": "COMPLETED",
        "total_timesteps": total_timesteps,
        "wall_clock_seconds": round(total_duration, 2),
        "episodes_completed": callback.episode_count,
        "episode_rewards": callback.episode_rewards,
        "mean_episode_reward": round(float(np.mean(callback.episode_rewards)), 2) if callback.episode_rewards else None,
        "action_distribution": {
            "action_0_hold_ew": callback.action_counts.get(0, 0),
            "action_1_switch_ns": callback.action_counts.get(1, 0),
            "action_0_pct": round(act_0_pct, 2),
            "action_1_pct": round(act_1_pct, 2),
        },
        "switches": {
            "total_voluntary": callback.total_voluntary_switches,
            "total_forced": callback.total_forced_switches,
            "total_rejected": callback.total_rejected_requests,
        },
        "checkpoint_path": str(model_path),
        "checkpoint_bytes": checkpoint_size,
    }

    summary_file = log_dir / "training_summary.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("\n" + "=" * 70)
    print("PILOT TRAINING COMPLETE")
    print(f"Duration:         {total_duration:.1f}s")
    print(f"Episodes:         {callback.episode_count}")
    print(f"Action 0 (EW):    {callback.action_counts.get(0, 0)} ({act_0_pct:.1f}%)")
    print(f"Action 1 (NS):    {callback.action_counts.get(1, 0)} ({act_1_pct:.1f}%)")
    print(f"Checkpoint Saved: {model_path} ({checkpoint_size / 1024:.1f} KB)")
    print(f"Summary Saved:    {summary_file}")
    print("=" * 70)

    return summary


if __name__ == "__main__":
    run_pilot_training(total_timesteps=5000)
