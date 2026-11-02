"""
Unit tests for SUMO TripInfo XML Parser.

All fixtures in this module are SYNTHETIC TEST DATA used exclusively for
verifying parsing logic, schema consistency, and error handling. They do not
represent empirical or simulation results.
"""

from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd

from src.metrics.tripinfo_parser import TRIPINFO_COLUMNS, parse_tripinfo


# ==============================================================================
# Synthetic Test XML Fixtures
# ==============================================================================

VALID_TRIPINFO_XML = """<?xml version="1.0" encoding="UTF-8"?>
<!-- SYNTHETIC TEST DATA - DO NOT USE AS SIMULATION RESULTS -->
<tripinfos xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
    <tripinfo id="synth_veh_01" depart="610.50" departLane="north_in_0" departPos="5.10"
              departSpeed="0.00" departDelay="0.00" arrival="655.20" arrivalLane="south_out_0"
              arrivalPos="150.00" arrivalSpeed="13.80" duration="44.70" routeLength="300.00"
              waitingTime="12.30" waitingCount="1" stopTime="0.00" timeLoss="18.90"
              rerouteNo="0" devices="tripinfo_synth_veh_01" vType="car" speedFactor="1.00"/>
    <tripinfo id="synth_veh_02" depart="615.00" departLane="east_in_1" departPos="5.10"
              departSpeed="0.00" departDelay="0.00" arrival="685.50" arrivalLane="west_out_1"
              arrivalPos="150.00" arrivalSpeed="11.20" duration="70.50" routeLength="310.50"
              waitingTime="35.00" waitingCount="2" stopTime="0.00" timeLoss="42.10"
              rerouteNo="0" devices="tripinfo_synth_veh_02" vType="two_wheeler" speedFactor="1.00"/>
</tripinfos>
"""

MISSING_OPTIONAL_ATTRIBS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<!-- SYNTHETIC TEST DATA: Missing waitingTime, routeLength, and timeLoss -->
<tripinfos>
    <tripinfo id="synth_incomplete_01" depart="700.00" arrival="750.00" duration="50.00"/>
</tripinfos>
"""

EMPTY_TRIPINFO_XML = """<?xml version="1.0" encoding="UTF-8"?>
<!-- SYNTHETIC TEST DATA: Root element present but zero vehicle records -->
<tripinfos>
</tripinfos>
"""

UNFINISHED_TRIPINFO_XML = """<?xml version="1.0" encoding="UTF-8"?>
<!-- SYNTHETIC TEST DATA: Explicit unfinished trip records -->
<tripinfos>
    <tripinfo id="synth_finished" depart="800.00" arrival="860.00" duration="60.00"
              waitingTime="10.00" timeLoss="15.00" routeLength="200.00"/>
    <unfinished-tripinfo id="synth_unfinished_tag" depart="850.00" duration="50.00"
                         waitingTime="45.00" timeLoss="48.00" routeLength="120.00"/>
    <tripinfo id="synth_no_arrival" depart="890.00" duration="10.00"
              waitingTime="8.00" timeLoss="9.00" routeLength="50.00"/>
</tripinfos>
"""

MALFORMED_XML = """<?xml version="1.0" encoding="UTF-8"?>
<!-- SYNTHETIC TEST DATA: Malformed XML (unclosed tag) -->
<tripinfos>
    <tripinfo id="bad_record" depart="100.00" arrival="150.00"
"""


class TestTripInfoParser(unittest.TestCase):
    """Test suite for validating the TripInfo parser module."""

    def setUp(self):
        """Create a temporary directory for test XML fixture files."""
        self.test_dir = tempfile.TemporaryDirectory()
        self.test_path = Path(self.test_dir.name)

    def tearDown(self):
        """Clean up the temporary directory after tests."""
        self.test_dir.cleanup()

    def _write_temp_xml(self, content: str) -> Path:
        """Helper to write synthetic XML content to a temporary file."""
        file_path = self.test_path / f"temp_{Path(tempfile.mktemp()).name}.xml"
        file_path.write_text(content, encoding="utf-8")
        return file_path

    # --------------------------------------------------------------------------
    # 1. Valid TripInfo XML Parsing
    # --------------------------------------------------------------------------
    def test_valid_tripinfo_parsing(self):
        """Test that a valid TripInfo XML is parsed and returns expected row count."""
        xml_file = self._write_temp_xml(VALID_TRIPINFO_XML)
        df = parse_tripinfo(xml_file)

        self.assertIsInstance(df, pd.DataFrame)
        self.assertEqual(len(df), 2, "Expected exactly 2 parsed vehicle records.")
        self.assertEqual(list(df["trip_id"]), ["synth_veh_01", "synth_veh_02"])

    # --------------------------------------------------------------------------
    # 2. Extraction of All Required Attributes
    # --------------------------------------------------------------------------
    def test_extraction_of_all_required_attributes(self):
        """Test accurate extraction and types for all required vehicle attributes."""
        xml_file = self._write_temp_xml(VALID_TRIPINFO_XML)
        df = parse_tripinfo(xml_file)

        row1 = df.iloc[0]
        self.assertEqual(row1["trip_id"], "synth_veh_01")
        self.assertAlmostEqual(row1["depart"], 610.50)
        self.assertAlmostEqual(row1["arrival"], 655.20)
        self.assertAlmostEqual(row1["duration"], 44.70)
        self.assertAlmostEqual(row1["waiting_time"], 12.30)
        self.assertAlmostEqual(row1["time_loss"], 18.90)
        self.assertAlmostEqual(row1["route_length"], 300.00)
        self.assertTrue(row1["is_completed"])

    # --------------------------------------------------------------------------
    # 3. Missing Optional Attributes Handling
    # --------------------------------------------------------------------------
    def test_missing_optional_attributes(self):
        """Test that missing optional attributes produce NaN and are NOT invented."""
        xml_file = self._write_temp_xml(MISSING_OPTIONAL_ATTRIBS_XML)
        df = parse_tripinfo(xml_file)

        self.assertEqual(len(df), 1)
        row = df.iloc[0]
        self.assertEqual(row["trip_id"], "synth_incomplete_01")
        self.assertAlmostEqual(row["depart"], 700.00)
        self.assertAlmostEqual(row["arrival"], 750.00)
        self.assertAlmostEqual(row["duration"], 50.00)

        # Missing attributes must be NaN, NOT 0.0 or default values
        self.assertTrue(
            np.isnan(row["waiting_time"]),
            "Missing waitingTime must evaluate to NaN, not an invented number.",
        )
        self.assertTrue(
            np.isnan(row["time_loss"]),
            "Missing timeLoss must evaluate to NaN, not an invented number.",
        )
        self.assertTrue(
            np.isnan(row["route_length"]),
            "Missing routeLength must evaluate to NaN, not an invented number.",
        )

    # --------------------------------------------------------------------------
    # 4. Empty XML Document with No Vehicle Records
    # --------------------------------------------------------------------------
    def test_empty_xml_document(self):
        """Test that an empty XML document returns an empty DataFrame with valid schema."""
        xml_file = self._write_temp_xml(EMPTY_TRIPINFO_XML)
        df = parse_tripinfo(xml_file)

        self.assertIsInstance(df, pd.DataFrame)
        self.assertEqual(len(df), 0, "DataFrame should contain 0 rows.")
        self.assertEqual(
            list(df.columns),
            TRIPINFO_COLUMNS,
            "Empty DataFrame must retain standard column schema.",
        )

    # --------------------------------------------------------------------------
    # 5. Malformed XML Handling
    # --------------------------------------------------------------------------
    def test_malformed_xml(self):
        """Test that malformed XML syntax raises an ET.ParseError with clear message."""
        xml_file = self._write_temp_xml(MALFORMED_XML)
        with self.assertRaises(ET.ParseError):
            parse_tripinfo(xml_file)

    # --------------------------------------------------------------------------
    # 6. Missing File Handling
    # --------------------------------------------------------------------------
    def test_missing_file_handling(self):
        """Test that a non-existent file path raises FileNotFoundError."""
        non_existent = self.test_path / "does_not_exist_file.xml"
        with self.assertRaises(FileNotFoundError):
            parse_tripinfo(non_existent)

    # --------------------------------------------------------------------------
    # 7. Consistent DataFrame Columns and Numeric Values
    # --------------------------------------------------------------------------
    def test_consistent_dataframe_columns_and_numeric_values(self):
        """Test that DataFrame columns, order, and datatypes are consistent."""
        xml_file = self._write_temp_xml(VALID_TRIPINFO_XML)
        df = parse_tripinfo(xml_file)

        # Check column names and order
        self.assertEqual(list(df.columns), TRIPINFO_COLUMNS)

        # Check data types
        self.assertEqual(df["trip_id"].dtype, "string")
        self.assertEqual(df["depart"].dtype, "float64")
        self.assertEqual(df["arrival"].dtype, "float64")
        self.assertEqual(df["duration"].dtype, "float64")
        self.assertEqual(df["waiting_time"].dtype, "float64")
        self.assertEqual(df["time_loss"].dtype, "float64")
        self.assertEqual(df["route_length"].dtype, "float64")
        self.assertEqual(df["is_completed"].dtype, "bool")

    # --------------------------------------------------------------------------
    # 8. Unfinished Vehicle Records Handling
    # --------------------------------------------------------------------------
    def test_unfinished_vehicle_record_handling(self):
        """Test that explicitly unfinished trip records are flagged as is_completed=False."""
        xml_file = self._write_temp_xml(UNFINISHED_TRIPINFO_XML)
        df = parse_tripinfo(xml_file)

        self.assertEqual(len(df), 3)

        # Record 1: Completed trip
        self.assertTrue(df.loc[df["trip_id"] == "synth_finished", "is_completed"].iloc[0])
        self.assertFalse(np.isnan(df.loc[df["trip_id"] == "synth_finished", "arrival"].iloc[0]))

        # Record 2: <unfinished-tripinfo> tag
        row_unfinished_tag = df[df["trip_id"] == "synth_unfinished_tag"].iloc[0]
        self.assertFalse(row_unfinished_tag["is_completed"])
        self.assertTrue(np.isnan(row_unfinished_tag["arrival"]))

        # Record 3: <tripinfo> tag missing arrival attribute
        row_no_arrival = df[df["trip_id"] == "synth_no_arrival"].iloc[0]
        self.assertFalse(row_no_arrival["is_completed"])
        self.assertTrue(np.isnan(row_no_arrival["arrival"]))

    # --------------------------------------------------------------------------
    # 9. Invalid Type Argument Handling
    # --------------------------------------------------------------------------
    def test_invalid_type_argument(self):
        """Test that passing None raises TypeError."""
        with self.assertRaises(TypeError):
            parse_tripinfo(None)


if __name__ == "__main__":
    unittest.main()

