
from pathlib import Path
import traci

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG = BASE_DIR / "signalsim1_fixed.sumocfg"

SUMO = r"C:\Program Files (x86)\SUMO\bin\sumo.exe"

traci.start([
    SUMO,
    "-c", str(CONFIG),
    "--lateral-resolution", "0.5",
    "--seed", "42"
])

try:
    tls_id = "J2"

    programs = traci.trafficlight.getAllProgramLogics(tls_id)
    phases = programs[0].phases

    links = traci.trafficlight.getControlledLinks(tls_id)

    incoming_edges = {
        "-E1": "NORTH",
        "-E3": "SOUTH",
        "-E2": "EAST",
        "-E4": "WEST"
    }

    for group, phase_id in [(0, 0), (1, 3)]:
        state = phases[phase_id].state
        active_directions = set()

        for index, signal in enumerate(state):
            if signal not in "Gg":
                continue

            for connection in links[index]:
                from_lane = connection[0]

                for edge, direction in incoming_edges.items():
                    if from_lane.startswith(edge + "_"):
                        active_directions.add(direction)

        print(
            f"Group {group}:",
            sorted(active_directions)
        )

finally:
    traci.close()
