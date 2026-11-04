import sys
from pathlib import Path
from collections import Counter

from stable_baselines3 import PPO
from stable_baselines3.common.monitor import Monitor

ROOT = Path(__file__).resolve().parent

sys.path.insert(
    0,
    str(ROOT / "sumo_simulation" / "controllers")
)

from ppo_env_v5 import SumoPPOEnvV5

SEED = 777
CHECKPOINTS = [8192, 16384, 32768]
SWITCH_COST = 8.0

MODEL_DIR = ROOT / "models"
MODEL_DIR.mkdir(exist_ok=True)

ROUTES = sorted(
    (ROOT / "sumo_simulation" / "training_routes")
    .glob("traffic_S*_seed*.rou.xml")
)


class TrackingEnv(SumoPPOEnvV5):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.route_history = []

    def reset(self, *, seed=None, options=None):
        obs, info = super().reset(
            seed=seed,
            options=options
        )

        route = info["route_file"]
        self.route_history.append(route)

        print(
            f"Episode {len(self.route_history)}: {route}",
            flush=True
        )

        return obs, info


def main():

    if len(ROUTES) != 20:
        raise RuntimeError(
            f"Expected 20 training routes, found {len(ROUTES)}"
        )

    # Never overwrite checkpoints from an earlier run.
    for checkpoint in CHECKPOINTS:
        path = MODEL_DIR / f"ppo_v5_c_{checkpoint}.zip"

        if path.exists():
            raise FileExistsError(
                f"Checkpoint already exists: {path}"
            )

    base_env = TrackingEnv(
        route_files=ROUTES,
        seed=SEED,
        end_time=4200,
        decision_interval=10.0,
        queue_weight=1.0,
        waiting_weight=0.005,
        voluntary_switch_cost=SWITCH_COST
    )

    env = Monitor(base_env)

    print()
    print("PPO V5-C LONGER TRAINING")
    print("=" * 60)
    print("Training routes:", len(ROUTES))
    print("Seed:", SEED)
    print("Switch cost:", SWITCH_COST)
    print("Final timesteps:", CHECKPOINTS[-1])
    print("Checkpoints:", CHECKPOINTS)
    print("=" * 60)

    try:

        model = PPO(
            "MlpPolicy",
            env,
            learning_rate=3e-4,
            n_steps=256,
            batch_size=64,
            n_epochs=10,
            gamma=0.99,
            seed=SEED,
            device="cpu",
            verbose=1
        )

        completed = 0

        for checkpoint in CHECKPOINTS:

            additional_steps = checkpoint - completed

            print()
            print(
                f"Training from {completed} "
                f"to {checkpoint} timesteps...",
                flush=True
            )

            model.learn(
                total_timesteps=additional_steps,
                reset_num_timesteps=(completed == 0)
            )

            path = MODEL_DIR / f"ppo_v5_c_{checkpoint}"
            model.save(str(path))

            completed = checkpoint

            print()
            print(f"CHECKPOINT SAVED: {path}.zip")
            print("Actual model timesteps:", model.num_timesteps)

            if model.num_timesteps != checkpoint:
                raise RuntimeError(
                    "Unexpected timestep count: "
                    f"{model.num_timesteps}"
                )

        counts = Counter(
            route.split("_")[1]
            for route in base_env.route_history
        )

        print()
        print("=" * 60)
        print("PPO V5-C TRAINING SUMMARY")
        print("=" * 60)
        print("Total timesteps:", model.num_timesteps)
        print(
            "Episodes started:",
            len(base_env.route_history)
        )
        print(
            "Unique routes:",
            len(set(base_env.route_history))
        )
        print(
            "Scenario coverage:",
            dict(sorted(counts.items()))
        )

        for checkpoint in CHECKPOINTS:
            path = MODEL_DIR / f"ppo_v5_c_{checkpoint}.zip"
            print(
                f"Checkpoint {checkpoint}:",
                path.exists()
            )

    finally:
        env.close()


if __name__ == "__main__":
    main()
