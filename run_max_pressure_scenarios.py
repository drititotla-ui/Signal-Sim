from pathlib import Path
import sys
import shutil
import traci

ROOT = Path(__file__).resolve().parent
CONTROLLERS = ROOT / "sumo_simulation" / "controllers"
sys.path.insert(0, str(CONTROLLERS))

import max_pressure

RESULTS = ROOT / "results" / "traffic_scenarios"
ROUTES = ROOT / "sumo_simulation" / "scenarios"
RESULTS.mkdir(parents=True, exist_ok=True)

sumo_binary = shutil.which("sumo")
if not sumo_binary:
    raise RuntimeError("SUMO executable not found in PATH")

original_start = traci.start

for scenario in ("S1", "S2", "S3", "S4"):
    print(f"\n========== MAX-PRESSURE {scenario} ==========", flush=True)

    route_file = ROUTES / f"traffic_{scenario}_seed42.rou.xml"
    if not route_file.exists():
        raise FileNotFoundError(route_file)

    def scenario_start(command, *args, **kwargs):
        command = list(command)
        command[0] = sumo_binary

        replace_options = {
            "--tripinfo-output",
            "--summary-output",
            "--log",
            "--delay",
        }

        cleaned = []
        i = 0

        while i < len(command):
            if command[i] in replace_options:
                i += 2
            else:
                cleaned.append(command[i])
                i += 1

        cleaned += [
            "--route-files", str(route_file),
            "--end", "5100",
            "--no-step-log", "true",
            "--tripinfo-output",
            str(RESULTS / f"max_{scenario}_tripinfo.xml"),
            "--summary-output",
            str(RESULTS / f"max_{scenario}_summary.xml"),
            "--log",
            str(RESULTS / f"max_{scenario}_validation.log"),
        ]

        return original_start(cleaned, *args, **kwargs)

    max_pressure.traci.start = scenario_start

    max_pressure.main()

    print(f"Completed Max-Pressure {scenario}", flush=True)

print("\nALL MAX-PRESSURE SCENARIOS COMPLETED")
