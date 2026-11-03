from pathlib import Path
import sys
import shutil
import traci

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "sumo_simulation" / "controllers"))

import max_pressure

RESULTS = ROOT / "results" / "traffic_scenarios"
ROUTE = ROOT / "sumo_simulation" / "scenarios" / "traffic_S4_seed42.rou.xml"

if not ROUTE.exists():
    raise FileNotFoundError(ROUTE)

SUMO = shutil.which("sumo")
if not SUMO:
    raise RuntimeError("SUMO not found in PATH")

# Diagnostic change: 3-second all-red instead of 1 second
max_pressure.SignalManager.ALL_RED_TIME = 3.0

original_start = traci.start

def test_start(command, *args, **kwargs):
    command = list(command)
    command[0] = SUMO

    remove = {
        "--tripinfo-output",
        "--summary-output",
        "--log",
        "--delay",
    }

    cleaned = []
    i = 0

    while i < len(command):
        if command[i] in remove:
            i += 2
        else:
            cleaned.append(command[i])
            i += 1

    cleaned += [
        "--route-files", str(ROUTE),
        "--end", "5100",
        "--no-step-log", "true",
        "--tripinfo-output",
        str(RESULTS / "max_S4_allred3_tripinfo.xml"),
        "--summary-output",
        str(RESULTS / "max_S4_allred3_summary.xml"),
        "--log",
        str(RESULTS / "max_S4_allred3_validation.log"),
    ]

    return original_start(cleaned, *args, **kwargs)

max_pressure.traci.start = test_start

print("Testing S4 with 3-second all-red")
max_pressure.main()

print("S4 diagnostic experiment completed!")
