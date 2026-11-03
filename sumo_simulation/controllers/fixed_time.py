
from pathlib import Path
import traci

# Project paths
BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG = BASE_DIR / "signalsim1_fixed.sumocfg"

SUMO = r"C:\Program Files (x86)\SUMO\bin\sumo-gui.exe"

# Verified six-phase fixed-time program
PHASE_DURATIONS = [30, 3, 1, 30, 3, 1]
PHASE_STATES = [
    "GGGGgrrrrrGGGGgrrrrr",
    "yyyyyrrrrryyyyyrrrrr",
    "rrrrrrrrrrrrrrrrrrrr",
    "rrrrrGGGGgrrrrrGGGGg",
    "rrrrryyyyyrrrrryyyyy",
    "rrrrrrrrrrrrrrrrrrrr"
]

SIM_DURATION = 3600

traci.start([
    SUMO,
    "-c", str(CONFIG),
    "--lateral-resolution", "0.5",
    "--seed", "42",
    "--delay", "20"
])

try:
    tls_ids = traci.trafficlight.getIDList()

    if len(tls_ids) != 1:
        raise RuntimeError(
            f"Expected one traffic light, found: {tls_ids}"
        )

    tls_id = tls_ids[0]
    logic = traci.trafficlight.getAllProgramLogics(tls_id)

    # Find the program matching our fixed-time setup
    matching = [
        p for p in logic
        if len(p.phases) == 6
        and all(
            abs(phase.duration - duration) < 0.001
            and phase.state == state
            for phase, duration, state in zip(
                p.phases, PHASE_DURATIONS, PHASE_STATES
            )
        )
    ]

    if not matching:
        raise RuntimeError(
            "Traffic-light program differs from the "
            "verified six-phase program."
        )

    program = matching[0]

    traci.trafficlight.setProgram(tls_id, program.programID)
    traci.trafficlight.setPhase(tls_id, 0)

    print("Fixed-time controller started")
    print("Traffic light:", tls_id)
    print("Cycle duration:", sum(PHASE_DURATIONS), "seconds")

    previous_phase = None

    while traci.simulation.getTime() < SIM_DURATION:
        traci.simulationStep()

        current_phase = traci.trafficlight.getPhase(tls_id)

        if current_phase != previous_phase:
            print(
                f"Time {traci.simulation.getTime():.1f}s "
                f"| Phase {current_phase} "
                f"| State: "
                f"{traci.trafficlight.getRedYellowGreenState(tls_id)}"
            )
            previous_phase = current_phase

    print("Fixed-time simulation completed")

finally:
    traci.close()
