"""
Unit tests for SIGNALSIM-INDIA signal transition safety logic.

Validates that:
1. SignalManager enforces safe clearance intervals (Yellow=3.0s, All-Red=3.0s, Total Intergreen=6.0s)
   in accordance with IRC:93-1985 guidelines for 30m intersections.
2. SignalManager strictly transitions through Yellow -> All-Red before granting Green to conflicting movements.
3. SignalManager enforces minimum green safety (10.0s) before permitting any voluntary phase switch.
4. FixedTimeAdapter configures 3.0s All-Red clearance durations on static program phases 2 and 5.
5. MaxPressureAdapter and PPOV6Adapter instantiate SignalManager with safe clearance intervals.
"""

import unittest
from unittest.mock import MagicMock, call
from pathlib import Path

from sumo_simulation.controllers.signal_manager import SignalManager
from src.experiments.controller_adapter import (
    FixedTimeAdapter,
    MaxPressureAdapter,
    PPOV6Adapter,
    PPOAdapter,
)


class MockTraCI:
    """Lightweight mock TraCI simulation environment for deterministic testing."""

    def __init__(self, start_time: float = 0.0):
        self.current_time = start_time
        self.simulation = MagicMock()
        self.simulation.getTime.side_effect = lambda: self.current_time
        self.trafficlight = MagicMock()

        # Mock program matching verified 6 phases
        mock_phases = []
        for state in SignalManager.STATES:
            p = MagicMock()
            p.state = state
            p.duration = 1.0
            mock_phases.append(p)
        mock_prog = MagicMock()
        mock_prog.phases = mock_phases
        mock_prog.programID = "0"
        self.trafficlight.getAllProgramLogics.return_value = [mock_prog]
        self.trafficlight.getIDList.return_value = ["J2"]
        self.trafficlight.getPhase.return_value = 0

    def step(self, delta: float = 0.1) -> None:
        self.current_time += delta


class TestSignalManagerSafety(unittest.TestCase):
    """Targeted tests for SignalManager safety constraints and transition logic."""

    def setUp(self):
        self.mock_traci = MockTraCI(start_time=0.0)

    def test_default_clearance_durations_align_with_irc(self):
        """SignalManager default clearance intervals must be 3.0s Yellow and 3.0s All-Red."""
        mgr = SignalManager(tls_id="J2", connection=self.mock_traci)
        self.assertEqual(mgr.YELLOW_TIME, 3.0)
        self.assertEqual(mgr.ALL_RED_TIME, 3.0)
        self.assertEqual(mgr.MIN_GREEN, 10.0)
        self.assertEqual(mgr.MAX_GREEN, 60.0)

    def test_min_green_rejection(self):
        """Phase switches requested before MIN_GREEN (10s) must be rejected."""
        mgr = SignalManager(tls_id="J2", connection=self.mock_traci)
        self.assertEqual(mgr.stage, "green")
        self.assertEqual(mgr.group, 0)

        # Advance time by 5s (< 10s min green)
        self.mock_traci.current_time = 5.0
        switched = mgr.request(group=1)
        self.assertFalse(switched, "Request before MIN_GREEN must be rejected")
        self.assertEqual(mgr.stage, "green")
        self.assertEqual(mgr.group, 0)

        # Advance time to 10.0s (>= MIN_GREEN)
        self.mock_traci.current_time = 10.0
        switched = mgr.request(group=1)
        self.assertTrue(switched, "Request at or after MIN_GREEN must be accepted")
        self.assertEqual(mgr.stage, "yellow")

    def test_transition_progression_yellow_then_all_red_then_green(self):
        """SignalManager must progress through Yellow (3s) -> All-Red (3s) -> Green."""
        mgr = SignalManager(tls_id="J2", connection=self.mock_traci)
        self.mock_traci.current_time = 10.0
        mgr.request(group=1)

        # Initially in Yellow (phase 1)
        self.assertEqual(mgr.stage, "yellow")
        self.mock_traci.trafficlight.setPhase.assert_called_with("J2", SignalManager.YELLOW[0])

        # Step 2.9s into Yellow: still in Yellow
        self.mock_traci.current_time = 12.9
        mgr.update()
        self.assertEqual(mgr.stage, "yellow")

        # Step 3.0s into Yellow: transitions to All-Red (phase 2)
        self.mock_traci.current_time = 13.0
        mgr.update()
        self.assertEqual(mgr.stage, "all_red")
        self.mock_traci.trafficlight.setPhase.assert_called_with("J2", SignalManager.ALL_RED[0])

        # Step 2.9s into All-Red: still in All-Red
        self.mock_traci.current_time = 15.9
        mgr.update()
        self.assertEqual(mgr.stage, "all_red")

        # Step 3.0s into All-Red: transitions to Green for Group 1 (phase 3)
        self.mock_traci.current_time = 16.0
        mgr.update()
        self.assertEqual(mgr.stage, "green")
        self.assertEqual(mgr.group, 1)
        self.mock_traci.trafficlight.setPhase.assert_called_with("J2", SignalManager.GREEN[1])

    def test_total_intergreen_clearance_time(self):
        """Verifies that total intergreen clearance time is exactly 6.0s (3.0s Y + 3.0s AR)."""
        mgr = SignalManager(tls_id="J2", connection=self.mock_traci)
        self.mock_traci.current_time = 10.0
        request_time = 10.0
        mgr.request(group=1)

        # Step until green is reached
        while mgr.stage != "green":
            self.mock_traci.step(0.1)
            mgr.update()

        green_onset_time = self.mock_traci.current_time
        intergreen_duration = green_onset_time - request_time
        self.assertAlmostEqual(intergreen_duration, 6.0, places=2)


class TestControllerAdapterClearanceAlignment(unittest.TestCase):
    """Verifies all controller adapters align with the 3.0s clearance standard."""

    def test_fixed_time_adapter_configures_safe_all_red_durations(self):
        """FixedTimeAdapter setup must set phases 2 and 5 duration to 3.0s via setProgramLogic."""
        mock_conn = MockTraCI(start_time=0.0)
        ft = FixedTimeAdapter(tls_id="J2")
        mock_cfg = MagicMock()

        ft.setup(mock_conn, mock_cfg, "S1", 42)

        # Check that program logic was updated with 3.0s all-red phases
        mock_conn.trafficlight.setProgramLogic.assert_called_once()
        updated_prog = mock_conn.trafficlight.setProgramLogic.call_args[0][1]
        self.assertEqual(updated_prog.phases[2].duration, 3.0)
        self.assertEqual(updated_prog.phases[5].duration, 3.0)
        self.assertEqual(ft.ALL_RED_DURATION, 3.0)

    def test_max_pressure_uses_safe_all_red_time(self):
        """MaxPressureAdapter must initialize SignalManager with 3.0s All-Red clearance."""
        mock_conn = MockTraCI(start_time=0.0)
        mp = MaxPressureAdapter(tls_id="J2")
        mock_cfg = MagicMock()
        mock_cfg.timing.controller_decision_interval_seconds = 10.0

        # Mock controlled links for movement discovery
        mock_conn.trafficlight.getControlledLinks.return_value = [
            [("-E2_0", "E4_0", "")] for _ in range(20)
        ]
        mp.setup(mock_conn, mock_cfg, "S1", 42)

        self.assertIsNotNone(mp.manager)
        self.assertEqual(mp.manager.ALL_RED_TIME, 3.0)
        self.assertEqual(mp.manager.YELLOW_TIME, 3.0)

    def test_ppo_v6_uses_safe_all_red_time(self):
        """PPOV6Adapter must initialize SignalManager with 3.0s All-Red clearance."""
        mock_conn = MockTraCI(start_time=0.0)
        ppo = PPOV6Adapter(tls_id="J2")
        mock_cfg = MagicMock()
        mock_cfg.timing.controller_decision_interval_seconds = 10.0

        ppo.setup(mock_conn, mock_cfg, "S1", 42)

        self.assertIsNotNone(ppo.manager)
        self.assertEqual(ppo.manager.ALL_RED_TIME, 3.0)
        self.assertEqual(ppo.manager.YELLOW_TIME, 3.0)


if __name__ == "__main__":
    unittest.main()
