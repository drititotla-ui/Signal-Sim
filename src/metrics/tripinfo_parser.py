"""
SUMO TripInfo XML Parser for SIGNALSIM-INDIA.

This module provides functions to parse SUMO tripinfo-output XML files into
structured pandas DataFrames. It is designed to be robust, modular, and easy
for beginners to understand and maintain.

Important Methodological Notes:
------------------------------
1. Vehicle-Level Only:
   This parser strictly extracts individual vehicle records. It DOES NOT calculate
   run-level summary metrics (such as mean travel time or completion rate). Run-level
   aggregations belong to downstream evaluation modules.

2. Unfinished Vehicle Tracking:
   By default, SUMO writes records to TripInfo ONLY when a vehicle successfully
   reaches its destination and exits the simulation network. If a vehicle is still
   in-flight (or stuck in a queue) when the simulation terminates, it will NOT appear
   in the standard TripInfo XML unless SUMO was invoked with the configuration flag:
   `--tripinfo-output.write-unfinished`.
   - This parser distinguishes explicitly recorded unfinished trips (such as
     `<unfinished-tripinfo>` tags or `<tripinfo>` tags missing an `arrival` attribute).
   - DO NOT infer that a vehicle is unfinished simply because it is absent from this
     file; total injected demand must be confirmed with P1 and verified against the
     generated route files.
   - P1 must confirm whether `--tripinfo-output.write-unfinished` is enabled.
"""

from pathlib import Path
from typing import List, Optional, Union
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd


# Expected standardized DataFrame columns and order
TRIPINFO_COLUMNS: List[str] = [
    "trip_id",
    "depart",
    "arrival",
    "duration",
    "waiting_time",
    "time_loss",
    "route_length",
    "is_completed",
]


def _create_empty_tripinfo_df() -> pd.DataFrame:
    """
    Creates an empty DataFrame with the standard TripInfo schema and dtypes.

    Returns
    -------
    pd.DataFrame
        Empty DataFrame with predetermined column names and appropriate dtypes.
    """
    return pd.DataFrame(
        {
            "trip_id": pd.Series(dtype="string"),
            "depart": pd.Series(dtype="float64"),
            "arrival": pd.Series(dtype="float64"),
            "duration": pd.Series(dtype="float64"),
            "waiting_time": pd.Series(dtype="float64"),
            "time_loss": pd.Series(dtype="float64"),
            "route_length": pd.Series(dtype="float64"),
            "is_completed": pd.Series(dtype="bool"),
        }
    )


def _safe_float(attrib_dict: dict, key: str) -> float:
    """
    Safely extracts a numeric float from an XML attribute dictionary.

    If the attribute is missing, empty, or cannot be converted to a float,
    it returns np.nan rather than inventing a default value like 0.0.

    Parameters
    ----------
    attrib_dict : dict
        Dictionary of XML element attributes.
    key : str
        The attribute key name to extract.

    Returns
    -------
    float
        The float value if valid; otherwise np.nan.
    """
    raw_val = attrib_dict.get(key)
    if raw_val is None or raw_val.strip() == "":
        return np.nan
    try:
        return float(raw_val)
    except (ValueError, TypeError):
        return np.nan


def parse_tripinfo(file_path: Union[str, Path]) -> pd.DataFrame:
    """
    Parses a SUMO TripInfo XML file and extracts vehicle-level trip records.

    Parameters
    ----------
    file_path : str or Path
        Path to the SUMO tripinfo XML output file.

    Returns
    -------
    pd.DataFrame
        A structured pandas DataFrame containing the extracted records with columns:
        - trip_id (string): Unique vehicle/trip identifier ('id').
        - depart (float): Simulation timestamp when the vehicle entered the network.
        - arrival (float): Simulation timestamp when the vehicle reached its destination
          (np.nan for unfinished vehicles).
        - duration (float): Total travel time in seconds from departure to arrival.
        - waiting_time (float): Cumulative seconds spent at speed < 0.1 m/s.
        - time_loss (float): Delay in seconds incurred relative to ideal free-flow travel.
        - route_length (float): Total distance traversed by the vehicle in metres.
        - is_completed (bool): True if the vehicle completed its trip, False if it was
          explicitly recorded as unfinished.

    Raises
    ------
    FileNotFoundError
        If the specified file does not exist.
    ET.ParseError
        If the file exists but contains invalid or malformed XML.
    TypeError
        If file_path is not a valid string or Path object.
    """
    if file_path is None:
        raise TypeError("file_path cannot be None.")

    path = Path(file_path)

    # 1. Validate file existence
    if not path.is_file():
        raise FileNotFoundError(f"SUMO TripInfo file not found at: {path.resolve()}")

    # 2. Parse XML document
    # Note: ET.parse will raise ET.ParseError if the XML syntax is invalid.
    try:
        tree = ET.parse(path)
        root = tree.getroot()
    except ET.ParseError as err:
        raise ET.ParseError(
            f"Failed to parse TripInfo XML file at '{path.resolve()}'. "
            f"The XML content is malformed or corrupted: {err}"
        ) from err

    # 3. Iterate over vehicle records
    records = []
    
    # Standard SUMO tags for vehicle trips in tripinfo XML
    # Both <tripinfo> and <unfinished-tripinfo> elements are checked
    for child in root:
        tag = child.tag.lower()
        if tag in ("tripinfo", "unfinished-tripinfo"):
            attrib = child.attrib

            trip_id = attrib.get("id")
            if trip_id is not None:
                trip_id = str(trip_id)

            depart = _safe_float(attrib, "depart")
            arrival = _safe_float(attrib, "arrival")
            duration = _safe_float(attrib, "duration")
            waiting_time = _safe_float(attrib, "waitingTime")
            time_loss = _safe_float(attrib, "timeLoss")
            route_length = _safe_float(attrib, "routeLength")

            # Determine completion status:
            # - If tag is explicitly 'unfinished-tripinfo', is_completed is False.
            # - If tag is 'tripinfo' but 'arrival' is absent/NaN, is_completed is False.
            # - If tag is 'tripinfo' and 'arrival' is a valid number, is_completed is True.
            if tag == "unfinished-tripinfo" or np.isnan(arrival):
                is_completed = False
            else:
                is_completed = True

            records.append(
                {
                    "trip_id": trip_id,
                    "depart": depart,
                    "arrival": arrival,
                    "duration": duration,
                    "waiting_time": waiting_time,
                    "time_loss": time_loss,
                    "route_length": route_length,
                    "is_completed": is_completed,
                }
            )

    # 4. Handle empty document (no records found)
    if not records:
        return _create_empty_tripinfo_df()

    # 5. Build and type-cast the resulting DataFrame
    df = pd.DataFrame(records)

    # Ensure consistent schema and column order
    df = df[TRIPINFO_COLUMNS]

    # Explicitly enforce expected data types
    df = df.astype(
        {
            "trip_id": "string",
            "depart": "float64",
            "arrival": "float64",
            "duration": "float64",
            "waiting_time": "float64",
            "time_loss": "float64",
            "route_length": "float64",
            "is_completed": "bool",
        }
    )

    return df

