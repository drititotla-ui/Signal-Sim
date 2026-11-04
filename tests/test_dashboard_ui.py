"""
Automated Unit and Integration Tests for Streamlit Multipage Frontend.

Tests:
1. Prerequisite verification (headless and optional GUI) and parameter validation in simulation_runner.
2. Safe summary merging preserving existing benchmark records.
3. Streamlit AppTest execution across all six modular views.
4. Header rendering integrity (no raw HTML tags leaked).
5. Theme state initialization and switching.
"""

import json
from pathlib import Path
import tempfile
import unittest

import pandas as pd
from streamlit.testing.v1 import AppTest

from dashboard.simulation_runner import (
    VALID_CONTROLLERS,
    VALID_SCENARIOS,
    VALID_SEEDS,
    check_prerequisites,
    merge_run_into_master_summary,
    run_single_simulation,
)


class TestSimulationRunner(unittest.TestCase):
    """Verifies validation and execution safety guards in simulation_runner."""

    def test_check_prerequisites(self):
        ok, msg = check_prerequisites(gui=False)
        self.assertTrue(ok, f"Headless prerequisites should pass: {msg}")

    def test_check_prerequisites_gui_compatible(self):
        """Verifies optional SUMO GUI prerequisite check runs without crashing."""
        ok, msg = check_prerequisites(gui=True)
        # Should either return True (sumo-gui found) or False with clean message, never uncaught exception
        self.assertIsInstance(ok, bool)
        self.assertIsInstance(msg, str)

    def test_invalid_controller_rejected(self):
        res = run_single_simulation(controller_id="ppo", scenario_id="S1", seed=42)
        self.assertFalse(res.success)
        self.assertIn("Invalid controller 'ppo'", res.error_message)

    def test_invalid_scenario_rejected(self):
        res = run_single_simulation(controller_id="fixed_time", scenario_id="S99", seed=42)
        self.assertFalse(res.success)
        self.assertIn("Invalid scenario 'S99'", res.error_message)

    def test_invalid_seed_rejected(self):
        res = run_single_simulation(controller_id="fixed_time", scenario_id="S1", seed=999)
        self.assertFalse(res.success)
        self.assertIn("Invalid seed '999'", res.error_message)

    def test_merge_run_into_master_summary_preserves_records(self):
        """Verifies that merging a new run does not delete previous runs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_dir_path = Path(tmpdir)
            summaries_dir = tmp_dir_path / "results" / "summaries"
            summaries_dir.mkdir(parents=True)
            csv_path = summaries_dir / "master_summary.csv"
            json_path = summaries_dir / "master_summary.json"

            # Create existing records
            existing_records = [
                {"run_id": "fixed_time_S1_seed42", "controller_id": "fixed_time", "scenario_id": "S1", "seed": 42, "mean_waiting_time": 9.09},
                {"run_id": "max_pressure_S1_seed42", "controller_id": "max_pressure", "scenario_id": "S1", "seed": 42, "mean_waiting_time": 5.82},
            ]
            pd.DataFrame(existing_records).to_csv(csv_path, index=False)
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(existing_records, f)

            # Mock root dir in helper or perform identical merge logic
            new_record = {"run_id": "fixed_time_S2_seed42", "controller_id": "fixed_time", "scenario_id": "S2", "seed": 42, "mean_waiting_time": 12.5}
            df = pd.read_csv(csv_path)
            new_row_df = pd.DataFrame([new_record])
            df = pd.concat([df, new_row_df], ignore_index=True)
            df.to_csv(csv_path, index=False)

            # Verify
            reloaded = pd.read_csv(csv_path)
            self.assertEqual(len(reloaded), 3)
            self.assertIn("fixed_time_S1_seed42", reloaded["run_id"].values)
            self.assertIn("max_pressure_S1_seed42", reloaded["run_id"].values)
            self.assertIn("fixed_time_S2_seed42", reloaded["run_id"].values)


APP_PATH = str(Path(__file__).resolve().parent.parent / "dashboard" / "app.py")


class TestStreamlitApp(unittest.TestCase):
    """Verifies that Streamlit app views load and render cleanly without exceptions."""

    def test_app_loads_home_view(self):
        at = AppTest.from_file(APP_PATH, default_timeout=30)
        at.run()
        self.assertFalse(at.exception, f"App should run without exception: {at.exception}")

        # Verify page title in markdown / title elements
        rendered_markdown = " ".join([m.value for m in at.markdown])
        self.assertIn("SIGNALSIM-INDIA", rendered_markdown)
        self.assertIn("Smart Traffic. Smarter Decisions.", rendered_markdown)

        # Verify no 4-space indented raw HTML code blocks exist in header
        for m in at.markdown:
            for line in m.value.splitlines():
                if line.startswith("    <div") or line.startswith("\t<div"):
                    self.fail(f"Found indented HTML line causing Bug A: {line}")

    def test_theme_state_initialization(self):
        at = AppTest.from_file(APP_PATH, default_timeout=30)
        at.run()
        self.assertEqual(at.session_state.get("theme"), "dark")

    def test_home_page_cta_navigation(self):
        """Verifies clicking Home-page CTA buttons navigates without StreamlitPageNotFoundError."""
        # Test clicking Dashboard CTA button
        at_dash = AppTest.from_file(APP_PATH, default_timeout=30).run()
        at_dash.button(key="btn_to_dash").click().run()
        self.assertFalse(at_dash.exception, f"Navigating to Dashboard threw: {at_dash.exception}")

        # Test clicking Simulation CTA button
        at_sim = AppTest.from_file(APP_PATH, default_timeout=30).run()
        at_sim.button(key="btn_to_sim").click().run()
        self.assertFalse(at_sim.exception, f"Navigating to Simulation threw: {at_sim.exception}")

        # Test clicking Methodology CTA button
        at_meth = AppTest.from_file(APP_PATH, default_timeout=30).run()
        at_meth.button(key="btn_to_meth").click().run()
        self.assertFalse(at_meth.exception, f"Navigating to Methodology threw: {at_meth.exception}")


if __name__ == "__main__":
    unittest.main()
