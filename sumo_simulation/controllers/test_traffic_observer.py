
from pathlib import Path
import traci

from traffic_observer import print_traffic_state

# Locate SUMO configuration
BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG = BASE_DIR / "signalsim1_fixed.sumocfg"

SUMO = r"C:\Program Files (x86)\SUMO\bin\sumo-gui.exe"

# Start simulation
traci.start([
    SUMO,
    "-c", str(CONFIG),
    "--lateral-resolution", "0.5",
    "--seed", "42",
    "--delay", "20"
])

try:
    print("Traffic observer connected successfully!")

    # Run simulation for 120 seconds
    next_report = 10

    while traci.simulation.getTime() < 120:
        traci.simulationStep()

        now = traci.simulation.getTime()

        if now >= next_report:
            print(f"\nSimulation time: {now:.1f}s")
            print_traffic_state()
            next_report += 10

    print("\nTraffic observer test completed!")

finally:
    traci.close()
