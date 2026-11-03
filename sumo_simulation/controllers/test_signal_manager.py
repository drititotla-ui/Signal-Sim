
from pathlib import Path
import traci
from signal_manager import SignalManager

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG = BASE_DIR / "signalsim_lht_fixed.sumocfg"

SUMO = r"C:\Program Files (x86)\SUMO\bin\sumo-gui.exe"

traci.start([
    SUMO,
    "-c", str(CONFIG),
    "--lateral-resolution", "0.5",
    "--delay", "50"
])

try:
    manager = SignalManager("J2")

    print("Safety manager connected!")
    print("Initial status:", manager.get_status())

    last_stage = None
    last_group = None

    while traci.simulation.getTime() < 90:
        traci.simulationStep()
        manager.update()

        now = traci.simulation.getTime()

        # Request group 1 after 15 seconds
        if 15 <= now < 16:
            manager.request(1)

        # Request group 0 after 50 seconds
        if 50 <= now < 51:
            manager.request(0)

        status = manager.get_status()

        if (status["stage"] != last_stage or
                status["group"] != last_group):
            print(
                f"Time: {now:.1f}s | "
                f"Group: {status['group']} | "
                f"Stage: {status['stage']} | "
                f"Phase: {status['phase']}"
            )
            last_stage = status["stage"]
            last_group = status["group"]

    print("Safety manager test completed!")

finally:
    traci.close()
