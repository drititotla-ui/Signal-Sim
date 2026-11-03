
import traci

# Actual edge IDs from your junction
INCOMING = {
    "north": "-E1",
    "south": "-E3",
    "east": "-E2",
    "west": "-E4"
}

OUTGOING = {
    "north": "E1",
    "south": "E3",
    "east": "E2",
    "west": "E4"
}


def get_edge_vehicles(edge_id):
    """Count vehicles on all lanes of an edge."""
    return traci.edge.getLastStepVehicleNumber(edge_id)


def get_edge_queue(edge_id):
    """Count vehicles moving slower than 0.1 m/s."""
    return traci.edge.getLastStepHaltingNumber(edge_id)


def get_traffic_state():
    result = {}

    for direction, edge_id in INCOMING.items():
        result[direction] = {
            "vehicles": get_edge_vehicles(edge_id),
            "queue": get_edge_queue(edge_id)
        }

    return result


def print_traffic_state():
    state = get_traffic_state()

    print("\n--- Live Traffic State ---")

    for direction, data in state.items():
        print(
            f"{direction.upper()}: "
            f"Vehicles={data['vehicles']} "
            f"Stopped={data['queue']}"
        )

