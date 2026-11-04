"""
Automated unit tests for SIGNALSIM-INDIA Dashboard Backend (M04.1).

Validates data loading, schema enforcement, duplicate detection, filtering,
metric aggregations, matched-seed controller comparisons, and the DashboardService facade.
"""

import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd

from src.dashboard.comparison import (
    calculate_percentage_improvement,
    compare_controllers_aggregate,
    compare_controllers_by_seed,
)
from src.dashboard.dashboard_service import DashboardService
from src.dashboard.data_loader import (
    DuplicateRunError,
    EmptyDataFileError,
    MalformedDataError,
    MissingDataFileError,
    load_master_summary,
)
from src.dashboard.data_processor import (
    check_benchmark_completeness,
    filter_results,
    get_available_controllers,
    get_available_scenarios,
    get_available_seeds,
)
from src.dashboard.metrics import (
    aggregate_metrics,
    compute_run_metrics,
)


class TestDataLoader(unittest.TestCase):
    """Tests loading, schema enforcement, and validation in data_loader."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dir_path = Path(self.temp_dir.name)

        # Minimal valid record template
        self.sample_record = {
            "run_id": "fixed_time_S1_seed42",
            "controller_id": "fixed_time",
            "scenario_id": "S1",
            "seed": 42,
            "status": "SUCCESS",
            "error_message": None,
            "simulation_duration_seconds": 5100.0,
            "wall_clock_duration_seconds": 22.38,
            "tripinfo_path": "path/to/tripinfo.xml",
            "summary_path": "path/to/summary.xml",
            "total_vehicles": 1443,
            "completed_vehicles": 1443,
            "unfinished_vehicles": 0,
            "warmup_vehicles": 210,
            "evaluation_vehicles": 1233,
            "drain_vehicles": 0,
            "mean_travel_time": 20.16,
            "mean_waiting_time": 9.09,
            "mean_time_loss": 13.48,
            "throughput_vph": 1233.0,
        }

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_load_real_m03_csv(self):
        """Verifies loading the actual M03 master_summary.csv in the repository."""
        csv_path = Path("results/summaries/master_summary.csv")
        if not csv_path.is_file():
            self.skipTest("master_summary.csv not present in repo")

        df = load_master_summary(csv_path)
        self.assertFalse(df.empty)
        self.assertIn("run_id", df.columns)
        self.assertIn("mean_travel_time", df.columns)
        self.assertEqual(len(df), 2)
        self.assertListEqual(sorted(df["controller_id"].tolist()), ["fixed_time", "max_pressure"])

    def test_load_real_m03_json(self):
        """Verifies loading the actual M03 master_summary.json in the repository."""
        json_path = Path("results/summaries/master_summary.json")
        if not json_path.is_file():
            self.skipTest("master_summary.json not present in repo")

        df = load_master_summary(json_path)
        self.assertFalse(df.empty)
        self.assertEqual(len(df), 2)

    def test_directory_loading_strategy(self):
        """Verifies loading from a directory containing both CSV and JSON."""
        csv_file = self.dir_path / "master_summary.csv"
        json_file = self.dir_path / "master_summary.json"

        pd.DataFrame([self.sample_record]).to_csv(csv_file, index=False)
        with open(json_file, "w") as f:
            json.dump([self.sample_record], f)

        # By default prefer_format='csv'
        df_csv = load_master_summary(self.dir_path, prefer_format="csv")
        self.assertEqual(len(df_csv), 1)

        df_json = load_master_summary(self.dir_path, prefer_format="json")
        self.assertEqual(len(df_json), 1)

    def test_missing_file_raises(self):
        """Verifies MissingDataFileError when path does not exist."""
        non_existent = self.dir_path / "does_not_exist.csv"
        with self.assertRaises(MissingDataFileError):
            load_master_summary(non_existent)

    def test_empty_csv_raises(self):
        """Verifies EmptyDataFileError on a 0-byte or header-only CSV."""
        empty_csv = self.dir_path / "empty.csv"
        empty_csv.write_text("")
        with self.assertRaises(EmptyDataFileError):
            load_master_summary(empty_csv)

    def test_empty_json_raises(self):
        """Verifies EmptyDataFileError on empty JSON file or empty list."""
        empty_json = self.dir_path / "empty.json"
        empty_json.write_text("[]")
        with self.assertRaises(EmptyDataFileError):
            load_master_summary(empty_json)

    def test_malformed_csv_missing_identifiers_raises(self):
        """Verifies MalformedDataError when required columns are absent."""
        bad_csv = self.dir_path / "bad.csv"
        pd.DataFrame([{"foo": "bar", "val": 123}]).to_csv(bad_csv, index=False)
        with self.assertRaises(MalformedDataError):
            load_master_summary(bad_csv)

    def test_duplicate_run_id_raises(self):
        """Verifies DuplicateRunError when duplicate run_ids exist."""
        rec1 = dict(self.sample_record)
        rec2 = dict(self.sample_record)  # same run_id
        dup_csv = self.dir_path / "dup.csv"
        pd.DataFrame([rec1, rec2]).to_csv(dup_csv, index=False)

        with self.assertRaises(DuplicateRunError):
            load_master_summary(dup_csv)

    def test_missing_metrics_remain_nan(self):
        """Verifies that missing or NaN metric values are preserved as NaN, never zeroed."""
        rec = dict(self.sample_record)
        rec["mean_travel_time"] = np.nan
        rec["mean_waiting_time"] = None
        nan_csv = self.dir_path / "nan.csv"
        pd.DataFrame([rec]).to_csv(nan_csv, index=False)

        df = load_master_summary(nan_csv)
        self.assertTrue(pd.isna(df.loc[0, "mean_travel_time"]))
        self.assertTrue(pd.isna(df.loc[0, "mean_waiting_time"]))
        self.assertNotEqual(df.loc[0, "mean_travel_time"], 0.0)


class TestDataProcessor(unittest.TestCase):
    """Tests filtering, dynamic entity detection, and completeness tracking."""

    def setUp(self):
        self.data = pd.DataFrame([
            {
                "run_id": "fixed_time_S1_seed42",
                "controller_id": "fixed_time",
                "scenario_id": "S1",
                "seed": 42,
                "status": "SUCCESS",
                "mean_travel_time": 20.0,
            },
            {
                "run_id": "max_pressure_S1_seed42",
                "controller_id": "max_pressure",
                "scenario_id": "S1",
                "seed": 42,
                "status": "SUCCESS",
                "mean_travel_time": 16.0,
            },
            {
                "run_id": "fixed_time_S2_seed101",
                "controller_id": "fixed_time",
                "scenario_id": "S2",
                "seed": 101,
                "status": "FAILED",
                "mean_travel_time": np.nan,
            },
        ])

    def test_filter_results(self):
        res_ctrl = filter_results(self.data, controller_id="fixed_time")
        self.assertEqual(len(res_ctrl), 2)

        res_scen = filter_results(self.data, scenario_id="S2")
        self.assertEqual(len(res_scen), 1)

        res_seed = filter_results(self.data, seed=42)
        self.assertEqual(len(res_seed), 2)

        res_status = filter_results(self.data, status="SUCCESS")
        self.assertEqual(len(res_status), 2)

    def test_get_available_controllers_excludes_ppo_when_absent(self):
        controllers = get_available_controllers(self.data)
        self.assertListEqual(controllers, ["fixed_time", "max_pressure"])
        self.assertNotIn("ppo", controllers)

    def test_check_benchmark_completeness_partial(self):
        # 2 controllers, 4 scenarios, 5 seeds = 40 expected
        comp = check_benchmark_completeness(
            self.data,
            expected_controllers=["fixed_time", "max_pressure"],
            expected_scenarios=["S1", "S2", "S3", "S4"],
            expected_seeds=[42, 101, 202, 303, 404],
        )
        self.assertEqual(comp["total_expected_runs"], 40)
        self.assertEqual(comp["successful_runs"], 2)
        self.assertTrue(comp["is_partial"])
        self.assertFalse(comp["is_complete"])
        self.assertEqual(len(comp["missing_runs"]), 38)


class TestMetrics(unittest.TestCase):
    """Tests metric aggregation, sample std, and NaN exclusion."""

    def setUp(self):
        self.df = pd.DataFrame([
            {
                "run_id": "ft_1",
                "controller_id": "fixed_time",
                "scenario_id": "S1",
                "seed": 42,
                "status": "SUCCESS",
                "mean_travel_time": 20.0,
                "throughput_vph": 1200.0,
            },
            {
                "run_id": "ft_2",
                "controller_id": "fixed_time",
                "scenario_id": "S1",
                "seed": 101,
                "status": "SUCCESS",
                "mean_travel_time": 22.0,
                "throughput_vph": 1250.0,
            },
            {
                "run_id": "ft_failed",
                "controller_id": "fixed_time",
                "scenario_id": "S1",
                "seed": 202,
                "status": "FAILED",
                "mean_travel_time": 10.0,  # Must be excluded!
                "throughput_vph": 9999.0,
            },
            {
                "run_id": "mp_1",
                "controller_id": "max_pressure",
                "scenario_id": "S1",
                "seed": 42,
                "status": "SUCCESS",
                "mean_travel_time": 16.0,
                "throughput_vph": 1200.0,
            },
        ])

    def test_aggregate_metrics_excludes_failed_runs(self):
        agg = aggregate_metrics(self.df, group_by=["controller_id", "scenario_id"])
        ft_agg = agg[(agg["controller_id"] == "fixed_time") & (agg["scenario_id"] == "S1")].iloc[0]

        # Only 2 successful runs (20.0 and 22.0), mean must be 21.0
        self.assertEqual(ft_agg["mean_travel_time_mean"], 21.0)
        self.assertEqual(ft_agg["mean_travel_time_count"], 2)
        # Sample standard deviation of [20.0, 22.0] is sqrt(2) ≈ 1.41
        self.assertAlmostEqual(ft_agg["mean_travel_time_std"], 1.41, places=2)

    def test_aggregate_never_mixes_controllers(self):
        agg = aggregate_metrics(self.df, group_by=["controller_id", "scenario_id"])
        self.assertEqual(len(agg), 2)
        controllers = set(agg["controller_id"])
        self.assertSetEqual(controllers, {"fixed_time", "max_pressure"})


class TestComparison(unittest.TestCase):
    """Tests relative percentage improvement, matched seeds, and edge-cases."""

    def test_calculate_percentage_improvement(self):
        # Lower-is-better: travel time reduced from 20 to 15 -> +25%
        imp_lower = calculate_percentage_improvement("mean_travel_time", 20.0, 15.0)
        self.assertEqual(imp_lower, 25.0)

        # Lower-is-better: travel time increased from 20 to 25 -> -25%
        worse_lower = calculate_percentage_improvement("mean_travel_time", 20.0, 25.0)
        self.assertEqual(worse_lower, -25.0)

        # Higher-is-better: throughput increased from 1000 to 1200 -> +20%
        imp_higher = calculate_percentage_improvement("throughput_vph", 1000.0, 1200.0)
        self.assertEqual(imp_higher, 20.0)

    def test_zero_or_missing_baseline(self):
        # Baseline is 0 or NaN -> return np.nan
        self.assertTrue(pd.isna(calculate_percentage_improvement("mean_travel_time", 0.0, 10.0)))
        self.assertTrue(pd.isna(calculate_percentage_improvement("mean_travel_time", np.nan, 10.0)))
        self.assertTrue(pd.isna(calculate_percentage_improvement("mean_travel_time", 10.0, np.nan)))

    def test_matched_seed_comparisons(self):
        df = pd.DataFrame([
            {"run_id": "ft_1", "controller_id": "fixed_time", "scenario_id": "S1", "seed": 42, "status": "SUCCESS", "mean_travel_time": 20.0, "throughput_vph": 1200.0},
            {"run_id": "ft_2", "controller_id": "fixed_time", "scenario_id": "S1", "seed": 101, "status": "SUCCESS", "mean_travel_time": 22.0, "throughput_vph": 1200.0},
            {"run_id": "mp_1", "controller_id": "max_pressure", "scenario_id": "S1", "seed": 42, "status": "SUCCESS", "mean_travel_time": 16.0, "throughput_vph": 1200.0},
            # Note: seed 101 is missing for max_pressure!
        ])

        paired = compare_controllers_by_seed(df, candidate_controller="max_pressure", baseline_controller="fixed_time")
        # Only seed 42 is matched
        self.assertEqual(len(paired), 1)
        self.assertEqual(paired.iloc[0]["seed"], 42)
        self.assertEqual(paired.iloc[0]["mean_travel_time_pct_improvement"], 20.0)

        agg = compare_controllers_aggregate(df, candidate_controller="max_pressure", baseline_controller="fixed_time")
        self.assertEqual(len(agg), 1)
        self.assertEqual(agg.iloc[0]["matched_seeds_count"], 1)
        self.assertFalse(agg.iloc[0]["statistical_significance_evaluable"])

    def test_ppo_unavailable(self):
        df = pd.DataFrame([
            {"run_id": "ft_1", "controller_id": "fixed_time", "scenario_id": "S1", "seed": 42, "status": "SUCCESS", "mean_travel_time": 20.0, "throughput_vph": 1200.0},
        ])
        paired = compare_controllers_by_seed(df, candidate_controller="ppo", baseline_controller="fixed_time")
        self.assertTrue(paired.empty)


class TestDashboardService(unittest.TestCase):
    """Tests DashboardService interface layer."""

    def test_service_with_real_results(self):
        csv_path = Path("results/summaries/master_summary.csv")
        if not csv_path.is_file():
            self.skipTest("master_summary.csv not present in repo")

        service = DashboardService(csv_path)
        kpis = service.get_overview_kpis()
        self.assertEqual(kpis["total_runs"], 2)
        self.assertEqual(kpis["successful_runs"], 2)

        controllers = service.get_available_controllers()
        self.assertListEqual(controllers, ["fixed_time", "max_pressure"])

        runs = service.get_run_level_results()
        self.assertEqual(len(runs), 2)

        comparison = service.get_controller_comparison("max_pressure", baseline_controller="fixed_time")
        self.assertEqual(len(comparison), 1)
        self.assertEqual(comparison.iloc[0]["scenario_id"], "S1")
        self.assertGreater(comparison.iloc[0]["mean_travel_time_mean_pct_improvement"], 0.0)

        status = service.get_benchmark_status()
        self.assertTrue(status["is_partial"])


if __name__ == "__main__":
    unittest.main()
