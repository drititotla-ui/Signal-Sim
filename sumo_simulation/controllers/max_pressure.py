
from pathlib import Path
from collections import defaultdict
import traci

from signal_manager import SignalManager

# ==================================
# SIGNALSIM-INDIA: MAX PRESSURE
# ==================================

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG = BASE_DIR / "signalsim_lht_fixed.sumocfg"

SUMO = r"C:\Program Files (x86)\SUMO\bin\sumo-gui.exe"
TLS_ID = "J2"

WARMUP_DURATION = 600
EVALUATION_DURATION = 3600
DRAIN_DURATION = 900

SIM_DURATION = (
    WARMUP_DURATION
    + EVALUATION_DURATION
    + DRAIN_DURATION

)

DECISION_INTERVAL = 10.0
PRESSURE_MARGIN = 1.0
MAX_GREEN = 60.0

# Verified group mapping:
# 0 = East-West, 1 = North-South
GREEN_PHASES = {0: 0, 1: 3}


def lane_to_edge(lane_id):
    return lane_id.rsplit("_", 1)[0]


def get_movements():
    """
    Find permitted movements for each green group
    using the actual SUMO traffic light links.
    """
    links = traci.trafficlight.getControlledLinks(TLS_ID)
    programs = traci.trafficlight.getAllProgramLogics(TLS_ID)

    matches = [
        p for p in programs
        if len(p.phases) == 6
        and p.phases[0].state == SignalManager.STATES[0]
        and p.phases[3].state == SignalManager.STATES[3]
    ]
    if not matches:
        raise RuntimeError("Expected traffic light program not found")

    phases = matches[0].phases
    movements = {}

    for group, phase_index in GREEN_PHASES.items():
        state = phases[phase_index].state
        pairs = set()

        for index, signal in enumerate(state):
            if signal not in ("G", "g"):
                continue

            for connection in links[index]:
                from_lane, to_lane = connection[:2]

                if not from_lane or not to_lane:
                    continue

                upstream = lane_to_edge(from_lane)
                downstream = lane_to_edge(to_lane)

                pairs.add((upstream, downstream))

        movements[group] = sorted(pairs)

        if not pairs:
            raise RuntimeError(
                f"No permitted movements for group {group}"
            )

    return movements


def calculate_pressure(movements):
    """
    Approximate movement pressure:
    upstream stopped vehicles - downstream vehicles.

    Movements from the same incoming edge are
    equally weighted as an initial assumption.
    """
    pressures = {}

    for group, pairs in movements.items():
        outgoing_by_incoming = defaultdict(set)

        for upstream, downstream in pairs:
            outgoing_by_incoming[upstream].add(downstream)

        total = 0.0

        for upstream, downstream_edges in outgoing_by_incoming.items():
            upstream_queue = traci.edge.getLastStepHaltingNumber(
                upstream
            )

            for downstream in downstream_edges:
                downstream_vehicles = (
                    traci.edge.getLastStepVehicleNumber(downstream)
                )

                weight = 1.0 / len(downstream_edges)

                total += weight * (
                    upstream_queue - downstream_vehicles
                )

        pressures[group] = total

    return pressures


def choose_group(pressures, current_group):
    other_group = 1 - current_group

    if (pressures[other_group] >
            pressures[current_group] + PRESSURE_MARGIN):
        return other_group

    return current_group


def main():
    traci.start([
    SUMO,
    "-c", str(CONFIG),
    "--lateral-resolution", "0.5",
    "--seed", "42",
    "--delay", "0",
    "--tripinfo-output", str(BASE_DIR / "max_pressure_tripinfo.xml"),
    "--summary-output", str(BASE_DIR / "max_pressure_summary.xml"),
    "--collision.check-junctions", "true",
    "--collision.action", "warn",
    "--log", str(BASE_DIR / "max_pressure_validation.log"),
])

    try:
        manager = SignalManager(TLS_ID)
        movements = get_movements()

        print("Max-pressure controller started!")
        print("Traffic light:", TLS_ID)
        print("Group 0 = East-West")
        print("Group 1 = North-South")
        print("Detected movements:", movements)

        next_decision = DECISION_INTERVAL

        while traci.simulation.getTime() < SIM_DURATION:
            traci.simulationStep()
            manager.update()

            
            now = traci.simulation.getTime()

            if abs(now - WARMUP_DURATION) < 0.0001:
                print("\n========== WARM-UP COMPLETE ==========")
                print("600 seconds completed.")
                print("Evaluation period has started!")
                print("======================================\n")

            if now + 1e-6 >= next_decision:

                pressures = calculate_pressure(movements)
                status = manager.get_status()

               
                
                if status["stage"] == "green":
                    requested = choose_group(
                        pressures, status["group"]
                    )

                    # Force a change after 60 seconds of green
                    green_elapsed = now - manager.stage_started

                    if green_elapsed >= MAX_GREEN:
                        requested = 1 - status["group"]

                    manager.request(requested)
                else:
                    requested = status["group"]


                actual_phase = traci.trafficlight.getPhase(TLS_ID)

                  
                print(
                    
                    f"Time={now:.1f}s | "
                    f"EW Pressure={pressures[0]:.2f} | "
                    f"NS Pressure={pressures[1]:.2f} | "
                    f"Requested={requested} | "
                    f"Stage={manager.stage} | "
                    f"Actual Phase={actual_phase}"
                )

                next_decision += DECISION_INTERVAL

        print("Max-pressure simulation completed!")

    finally:
        traci.close()


if __name__ == "__main__":
    main()
