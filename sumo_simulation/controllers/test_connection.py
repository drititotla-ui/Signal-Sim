
import traci
from pathlib import Path

# Find the SUMO configuration
BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG = BASE_DIR / "signalsim1_fixed.sumocfg"

# Start SUMO
traci.start([
    "sumo-gui",
    "-c", str(CONFIG),
    "--lateral-resolution", "0.5",
    "--delay", "100"
])

print("SUMO connected successfully!")

# Get all traffic light IDs
traffic_lights = traci.trafficlight.getIDList()

print("Traffic lights:", traffic_lights)

for tls_id in traffic_lights:
    print("Traffic light ID:", tls_id)

    # Print the signal program
    programs = traci.trafficlight.getAllProgramLogics(tls_id)

    for program in programs:
        print("Program:", program.programID)

        for i, phase in enumerate(program.phases):
            print(
                "Phase:", i,
                "Duration:", phase.duration,
                "State:", phase.state
            )

# Run a few simulation steps
for step in range(100):
    traci.simulationStep()

print("Simulation test completed!")

traci.close()
