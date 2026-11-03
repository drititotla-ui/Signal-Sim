from pathlib import Path
from src.routes.generator import (
    RouteGeneratorConfig,
    generate_route_file
)

config = RouteGeneratorConfig.from_yaml(
    "configs/experiment.yaml",
    "configs/scenarios"
)

# Vehicle distribution from existing SUMO flows
fleet_mix = {
    "car": 1200 / 3960,
    "bike": 900 / 3960,
    "auto": 720 / 3960,
    "bus": 240 / 3960,
    "truck": 300 / 3960,
    "bicycle": 600 / 3960
}

output_dir = Path("sumo_simulation/scenarios")
output_dir.mkdir(parents=True, exist_ok=True)

for scenario in ["S1", "S2", "S3", "S4"]:
    output = output_dir / f"traffic_{scenario}_seed42.rou.xml"

    result = generate_route_file(
        scenario_id=scenario,
        seed=42,
        fleet_mix=fleet_mix,
        config=config,
        output_path=output
    )

    print(f"Generated: {result}")

print("\nAll four traffic scenarios generated!")
