import traci


class SignalManager:
    # Controller action identifiers
    GROUP_0 = 0
    GROUP_1 = 1

    # Your six verified SUMO phases
    GREEN = {0: 0, 1: 3}
    YELLOW = {0: 1, 1: 4}
    ALL_RED = {0: 2, 1: 5}

    MIN_GREEN = 10.0
    MAX_GREEN = 60.0    
    YELLOW_TIME = 3.0
    ALL_RED_TIME = 3.0  # Aligned with IRC:93-1985 clearance standards (30m intersection)

    STATES = [
        "GGGGgrrrrrGGGGgrrrrr",
        "yyyyyrrrrryyyyyrrrrr",
        "rrrrrrrrrrrrrrrrrrrr",
        "rrrrrGGGGgrrrrrGGGGg",
        "rrrrryyyyyrrrrryyyyy",
        "rrrrrrrrrrrrrrrrrrrr"
    ]

    def __init__(self, tls_id="J2", connection=None, yellow_time=3.0, all_red_time=3.0):
        self.tls_id = tls_id
        self.conn = connection if connection is not None else traci
        self.group = 0
        self.stage = "green"
        self.stage_started = self.conn.simulation.getTime()
        self.pending_group = None
        self.YELLOW_TIME = float(yellow_time)
        self.ALL_RED_TIME = float(all_red_time)

        # Verify that SUMO has the expected program
        programs = self.conn.trafficlight.getAllProgramLogics(tls_id)
        if not any(
            len(program.phases) == 6
            and [p.state for p in program.phases] == self.STATES
            for program in programs
        ):
            raise RuntimeError(
                "SUMO signal phases do not match the expected setup."
            )

        self._set_phase(self.GREEN[self.group], 10000)

    def _set_phase(self, phase, duration):
        self.conn.trafficlight.setPhase(self.tls_id, phase)
        self.conn.trafficlight.setPhaseDuration(
            self.tls_id, duration
        )
        self.stage_started = self.conn.simulation.getTime()

    def request(self, group):
        """Request green group 0 or 1."""
        if group not in (0, 1):
            raise ValueError("Action must be 0 or 1")

        if self.stage != "green":
            return False

        if group == self.group:
            return False

        elapsed = (
            self.conn.simulation.getTime() - self.stage_started
        )

        if elapsed < self.MIN_GREEN:
            return False

        self.pending_group = group
        self.stage = "yellow"
        self._set_phase(
            self.YELLOW[self.group], self.YELLOW_TIME
        )
        return True

    def update(self):
        """Call once after each simulation step."""
        now = self.conn.simulation.getTime()
        elapsed = now - self.stage_started

        if self.stage == "yellow":
            if elapsed >= self.YELLOW_TIME - 1e-6:
                self.stage = "all_red"
                self._set_phase(
                    self.ALL_RED[self.group],
                    self.ALL_RED_TIME
                )

        elif self.stage == "all_red":
            if elapsed >= self.ALL_RED_TIME - 1e-6:
                self.group = self.pending_group
                self.pending_group = None
                self.stage = "green"
                self._set_phase(
                    self.GREEN[self.group], 10000
                )

    def get_status(self):
        return {
            "group": self.group,
            "stage": self.stage,
            "phase": self.conn.trafficlight.getPhase(
                self.tls_id
            ),
            "time": self.conn.simulation.getTime()
        }
