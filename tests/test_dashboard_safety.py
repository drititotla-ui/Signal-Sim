"""
Automated unit tests for SIGNALSIM-INDIA Safety Benchmark & Dashboard Integration (M07).

Validates:
1. Independent loading of Original vs Safety Retimed benchmark datasets.
2. Direct SUMO summary XML collision parsing (never inferred from TripInfo).
3. Collision reduction percentages across all three controllers (Fixed-Time, Max-Pressure, PPO V6).
4. Preservation of throughput and empirical travel-time trade-off metrics.
5. Accurate disclosure of the IRC:93-1985 clearance configuration (1s -> 3s all-red, 68s -> 72s cycle).
"""

from pathlib import Path
import tempfile
import unittest

import pandas as pd

from src.dashboard.comparison import compare_safety_benchmarks
from src.dashboard.dashboard_service import DashboardService
from src.dashboard.data_loader import (
    extract_collisions_from_summary,
    load_master_summary,
)


class TestDashboardSafetyIntegration(unittest.TestCase):
    """Test suite for M07 Safety Benchmark Dashboard Integration."""

    @classmethod
    def setUpClass(cls):
        cls.root_dir = Path(__file__).resolve().parent.parent
        cls.orig_csv = cls.root_dir / "results" / "summaries" / "master_summary.csv"
        cls.safety_csv = cls.root_dir / "results" / "safety" / "summaries" / "master_summary.csv"

    def test_extract_collisions_from_summary_edge_cases(self):
        """Verifies edge cases of extract_collisions_from_summary function."""
        # None or empty path
        self.assertEqual(extract_collisions_from_summary(None), 0)
        self.assertEqual(extract_collisions_from_summary(""), 0)

        # Non-existent file
        self.assertEqual(extract_collisions_from_summary("non_existent_file.xml"), 0)

        # Empty file
        with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as f:
            temp_path = Path(f.name)
        try:
            self.assertEqual(extract_collisions_from_summary(temp_path), 0)
        finally:
            if temp_path.exists():
                temp_path.unlink()

        # Synthetic valid XML snippet with multiple step tags
        with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False, encoding="utf-8") as f:
            f.write(
                '<summary>\n'
                '    <step time="10.00" collisions="0" />\n'
                '    <step time="20.00" collisions="2" />\n'
                '    <step time="30.00" collisions="5" />\n'
                '</summary>\n'
            )
            temp_path = Path(f.name)
        try:
            self.assertEqual(extract_collisions_from_summary(temp_path), 5)
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_extract_collisions_from_real_summary_xml(self):
        """Verifies collision parser on actual evaluation XML files."""
        # Test a run verified to have 0 collisions (fixed_time_S1_seed101)
        s1_zero_xml = self.root_dir / "results" / "summaries" / "fixed_time_S1_seed101_summary.xml"
        if s1_zero_xml.is_file():
            self.assertEqual(extract_collisions_from_summary(s1_zero_xml), 0)

        # Test a run verified to have exactly 1 collision (fixed_time_S1_seed42)
        s1_one_xml = self.root_dir / "results" / "summaries" / "fixed_time_S1_seed42_summary.xml"
        if s1_one_xml.is_file():
            self.assertEqual(extract_collisions_from_summary(s1_one_xml), 1)

        # Test a high-congestion run known to have multiple collisions (e.g. ppo_v6_S3_seed42)
        s3_xml = self.root_dir / "results" / "summaries" / "ppo_v6_S3_seed42_summary.xml"
        if s3_xml.is_file():
            collisions = extract_collisions_from_summary(s3_xml)
            self.assertGreater(collisions, 5)

    def test_independent_datasets_integrity(self):
        """Verifies original and safety benchmarks load separately without mixing."""
        self.assertTrue(self.orig_csv.is_file(), f"Missing original benchmark: {self.orig_csv}")
        self.assertTrue(self.safety_csv.is_file(), f"Missing safety benchmark: {self.safety_csv}")

        orig_df = load_master_summary(self.orig_csv)
        safety_df = load_master_summary(self.safety_csv)

        # Verify exact record counts
        self.assertEqual(len(orig_df), 60)
        self.assertEqual(len(safety_df), 60)

        # Verify all successful
        self.assertEqual((orig_df["status"] == "SUCCESS").sum(), 60)
        self.assertEqual((safety_df["status"] == "SUCCESS").sum(), 60)

        # Verify collisions column exists and is populated
        self.assertIn("collisions", orig_df.columns)
        self.assertIn("collisions", safety_df.columns)

        # Verify total collision counts match SUMO verified numbers
        self.assertEqual(int(orig_df["collisions"].sum()), 398)
        self.assertEqual(int(safety_df["collisions"].sum()), 273)

        # Verify datasets have different memory references and independent summaries
        self.assertIsNot(orig_df, safety_df)

    def test_dashboard_service_safety_comparison(self):
        """Verifies DashboardService loads and performs safety comparison cleanly."""
        service = DashboardService(self.orig_csv)
        comparison = service.get_safety_comparison(self.safety_csv)

        # Check top-level keys
        self.assertIn("controller_summary", comparison)
        self.assertIn("scenario_summary", comparison)
        self.assertIn("overall_kpis", comparison)
        self.assertIn("safety_metadata", comparison)

        # Verify Overall KPIs
        kpis = comparison["overall_kpis"]
        self.assertEqual(kpis["total_collisions_orig"], 398)
        self.assertEqual(kpis["total_collisions_safe"], 273)
        self.assertEqual(kpis["total_collisions_avoided"], 125)
        self.assertAlmostEqual(kpis["overall_collision_reduction_pct"], 31.41, places=1)

        # Verify travel time delta (mean increase of ~1.54s)
        travel_delta = round(kpis["mean_travel_time_safe"] - kpis["mean_travel_time_orig"], 2)
        self.assertAlmostEqual(travel_delta, 1.54, places=1)

        # Verify throughput preservation (virtually identical: 2108.65 vs 2108.32 vph, delta <= 0.1%)
        throughput_pct_change = (kpis["mean_throughput_safe"] - kpis["mean_throughput_orig"]) / kpis["mean_throughput_orig"] * 100.0
        self.assertLess(abs(throughput_pct_change), 0.1)

    def test_controller_level_collision_reductions(self):
        """Verifies collision metrics and reductions for each controller."""
        service = DashboardService(self.orig_csv)
        comparison = service.get_safety_comparison(self.safety_csv)
        ctrl_summary = comparison["controller_summary"]

        self.assertEqual(len(ctrl_summary), 3)
        controllers = set(ctrl_summary["controller_id"])
        self.assertEqual(controllers, {"fixed_time", "max_pressure", "ppo_v6"})

        # Map by controller_id
        c_map = ctrl_summary.set_index("controller_id").to_dict(orient="index")

        # Fixed-Time: 93 -> 53 (-43.01%)
        ft = c_map["fixed_time"]
        self.assertEqual(ft["collisions_orig"], 93)
        self.assertEqual(ft["collisions_safe"], 53)
        self.assertAlmostEqual(ft["collision_reduction_pct"], 43.01, places=1)
        self.assertEqual(ft["travel_time_orig"], 21.17)
        self.assertEqual(ft["travel_time_safe"], 22.60)

        # Max-Pressure: 133 -> 119 (-10.53%)
        mp = c_map["max_pressure"]
        self.assertEqual(mp["collisions_orig"], 133)
        self.assertEqual(mp["collisions_safe"], 119)
        self.assertAlmostEqual(mp["collision_reduction_pct"], 10.53, places=1)
        self.assertEqual(mp["travel_time_orig"], 17.69)
        self.assertEqual(mp["travel_time_safe"], 19.50)

        # PPO V6: 172 -> 101 (-41.28%)
        ppo = c_map["ppo_v6"]
        self.assertEqual(ppo["collisions_orig"], 172)
        self.assertEqual(ppo["collisions_safe"], 101)
        self.assertAlmostEqual(ppo["collision_reduction_pct"], 41.28, places=1)
        self.assertEqual(ppo["travel_time_orig"], 22.26)
        self.assertEqual(ppo["travel_time_safe"], 23.64)

    def test_safety_metadata_disclosure_content(self):
        """Verifies disclosure metadata documents IRC:93-1985 and timing adjustments."""
        service = DashboardService(self.orig_csv)
        comparison = service.get_safety_comparison(self.safety_csv)
        meta = comparison["safety_metadata"]

        self.assertEqual(meta["all_red_original"], "1.0s")
        self.assertEqual(meta["all_red_safety"], "3.0s")
        self.assertEqual(meta["cycle_original"], "68s")
        self.assertEqual(meta["cycle_safety"], "72s")
        self.assertIn("IRC:93-1985", meta["standard"])
        self.assertIn("1.0s to 3.0s", meta["disclosure"])
        self.assertIn("68s to 72s", meta["disclosure"])
        self.assertIn("30m", meta["disclosure"])

    def test_compare_safety_benchmarks_empty_dataframes(self):
        """Verifies compare_safety_benchmarks safely handles empty DataFrames."""
        res = compare_safety_benchmarks(pd.DataFrame(), pd.DataFrame())
        self.assertTrue(res["controller_summary"].empty)
        self.assertTrue(res["scenario_summary"].empty)
        self.assertEqual(res["overall_kpis"], {})


if __name__ == "__main__":
    unittest.main()
