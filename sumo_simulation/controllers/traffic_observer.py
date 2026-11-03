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


def get_edge_vehicles(edge_id, connection=None):
    """Count vehicles on all lanes of an edge."""
    conn = connection if connection is not None else traci
    return conn.edge.getLastStepVehicleNumber(edge_id)


def get_edge_queue(edge_id, connection=None):
    """Count vehicles moving slower than 0.1 m/s."""
    conn = connection if connection is not None else traci
    return conn.edge.getLastStepHaltingNumber(edge_id)


def get_traffic_state(connection=None):
    result = {}

    for direction, edge_id in INCOMING.items():
        result[direction] = {
            "vehicles": get_edge_vehicles(edge_id, connection=connection),
            "queue": get_edge_queue(edge_id, connection=connection)
        }

    return result


def print_traffic_state(connection=None):
    state = get_traffic_state(connection=connection)

    print("\n--- Live Traffic State ---")

    for direction, data in state.items():
        print(
            f"{direction.upper()}: "
            f"Vehicles={data['vehicles']} "
            f"Stopped={data['queue']}"
        )
