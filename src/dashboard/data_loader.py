"""
Data Loader for SIGNALSIM-INDIA Dashboard Backend (M04.1).

Responsible for loading M03 master summary results from CSV or JSON formats,
validating schemas, detecting duplicate records, handling missing data gracefully,
and establishing a clear source-of-truth strategy without modifying original files.
"""

from dataclasses import dataclass
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Expected columns and types as established by M03 RunResult
EXPECTED_COLUMNS: Dict[str, Any] = {
    "run_id": "string",
    "controller_id": "string",
    "scenario_id": "string",
    "seed": "Int64",
    "status": "string",
    "error_message": "string",
    "simulation_duration_seconds": "float64",
    "wall_clock_duration_seconds": "float64",
    "tripinfo_path": "string",
    "summary_path": "string",
    "total_vehicles": "Int64",
    "completed_vehicles": "Int64",
    "unfinished_vehicles": "Int64",
    "warmup_vehicles": "Int64",
    "evaluation_vehicles": "Int64",
    "drain_vehicles": "Int64",
    "mean_travel_time": "float64",
    "mean_waiting_time": "float64",
    "mean_time_loss": "float64",
    "throughput_vph": "float64",
}

NUMERIC_METRIC_COLUMNS = [
    "mean_travel_time",
    "mean_waiting_time",
    "mean_time_loss",
    "throughput_vph",
    "simulation_duration_seconds",
    "wall_clock_duration_seconds",
]

INTEGER_COUNT_COLUMNS = [
    "total_vehicles",
    "completed_vehicles",
    "unfinished_vehicles",
    "warmup_vehicles",
    "evaluation_vehicles",
    "drain_vehicles",
    "seed",
]


class DashboardDataError(Exception):
    """Base exception for dashboard data loading and validation failures."""
    pass


class MissingDataFileError(DashboardDataError):
    """Raised when the specified data file or directory cannot be found."""
    pass


class EmptyDataFileError(DashboardDataError):
    """Raised when the data file exists but contains no records."""
    pass


class MalformedDataError(DashboardDataError):
    """Raised when data cannot be parsed or lacks required structure."""
    pass


class DuplicateRunError(DashboardDataError):
    """Raised when duplicate run_id or (controller, scenario, seed) combinations exist."""
    pass


def get_empty_summary_dataframe() -> pd.DataFrame:
    """Returns an empty DataFrame initialized with the standard M03 columns and dtypes."""
    empty_data: Dict[str, Any] = {col: pd.Series(dtype=dtype) for col, dtype in EXPECTED_COLUMNS.items()}
    return pd.DataFrame(empty_data)


def load_master_summary(
    path: Optional[Union[str, Path]] = None,
    prefer_format: str = "csv",
) -> pd.DataFrame:
    """
    Loads M03 master summary data from a file or directory.

    Source-of-truth strategy:
    1. If `path` points to a specific CSV or JSON file, loads that file directly.
    2. If `path` is a directory or None (defaults to 'results/summaries'):
       - Checks for 'master_summary.csv' first (if prefer_format == 'csv').
       - If CSV is absent, falls back to 'master_summary.json'.
       - Never silently merges CSV and JSON together to prevent duplication or discrepancy.
    3. Missing metric values remain NaN and are never silently converted to zero.
    4. Detects duplicate run records and raises DuplicateRunError.

    Parameters
    ----------
    path : str or Path, optional
        Path to file or directory. If None, resolves to 'results/summaries/master_summary.csv'.
    prefer_format : str, default "csv"
        Format priority when path is a directory ('csv' or 'json').

    Returns
    -------
    pd.DataFrame
        Validated, type-enforced DataFrame containing run records.

    Raises
    ------
    MissingDataFileError
        If target file or directory does not exist.
    EmptyDataFileError
        If file contains no data rows.
    MalformedDataError
        If file is unparseable or lacks required columns.
    DuplicateRunError
        If duplicate run records are detected.
    """
    target = Path(path) if path is not None else Path("results/summaries")

    resolved_file: Path
    if target.is_dir():
        csv_candidate = target / "master_summary.csv"
        json_candidate = target / "master_summary.json"

        if prefer_format == "csv":
            if csv_candidate.is_file():
                resolved_file = csv_candidate
            elif json_candidate.is_file():
                resolved_file = json_candidate
            else:
                raise MissingDataFileError(
                    f"No master summary file found in directory '{target}'. Looked for: "
                    f"'{csv_candidate.name}' and '{json_candidate.name}'."
                )
        else:
            if json_candidate.is_file():
                resolved_file = json_candidate
            elif csv_candidate.is_file():
                resolved_file = csv_candidate
            else:
                raise MissingDataFileError(
                    f"No master summary file found in directory '{target}'."
                )
    elif target.is_file():
        resolved_file = target
    else:
        raise MissingDataFileError(f"Data path does not exist: {target}")

    suffix = resolved_file.suffix.lower()
    if suffix == ".csv":
        df = _load_csv(resolved_file)
    elif suffix == ".json":
        df = _load_json(resolved_file)
    else:
        raise MalformedDataError(
            f"Unsupported file format '{suffix}'. Expected '.csv' or '.json'."
        )

    return _validate_and_sanitize_dataframe(df, source_file=resolved_file)


def _load_csv(file_path: Path) -> pd.DataFrame:
    """Reads a CSV file into a DataFrame with error handling."""
    if file_path.stat().st_size == 0:
        raise EmptyDataFileError(f"CSV file is empty (0 bytes): {file_path}")

    try:
        df = pd.read_csv(file_path)
    except Exception as err:
        raise MalformedDataError(f"Failed to parse CSV file '{file_path}': {err}") from err

    if df.empty:
        raise EmptyDataFileError(f"CSV file contains no data rows: {file_path}")

    return df


def _load_json(file_path: Path) -> pd.DataFrame:
    """Reads a JSON summary file into a DataFrame with error handling."""
    if file_path.stat().st_size == 0:
        raise EmptyDataFileError(f"JSON file is empty (0 bytes): {file_path}")

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as err:
        raise MalformedDataError(f"Failed to parse JSON file '{file_path}': {err}") from err

    if not isinstance(data, list):
        if isinstance(data, dict):
            # Single run record wrapped as dict
            data = [data]
        else:
            raise MalformedDataError(
                f"JSON file must contain a list of records, got {type(data).__name__}."
            )

    if len(data) == 0:
        raise EmptyDataFileError(f"JSON file contains empty list: {file_path}")

    try:
        df = pd.DataFrame(data)
    except Exception as err:
        raise MalformedDataError(f"Failed to convert JSON data to DataFrame: {err}") from err

    return df


def _validate_and_sanitize_dataframe(df: pd.DataFrame, source_file: Path) -> pd.DataFrame:
    """
    Validates required columns, checks for duplicates, and casts data types cleanly.
    Missing values are preserved as NaN, never converted to 0.
    """
    # Verify core identifying columns
    required_id_cols = ["run_id", "controller_id", "scenario_id", "seed", "status"]
    missing_cols = [c for c in required_id_cols if c not in df.columns]
    if missing_cols:
        raise MalformedDataError(
            f"Data file '{source_file}' missing required identifier columns: {missing_cols}"
        )

    # Check for duplicate run_ids
    if df["run_id"].duplicated().any():
        dupes = df[df["run_id"].duplicated(keep=False)]["run_id"].tolist()
        raise DuplicateRunError(
            f"Duplicate run_id records detected in '{source_file}': {set(dupes)}"
        )

    # Check for duplicate (controller, scenario, seed)
    dupe_keys = df.duplicated(subset=["controller_id", "scenario_id", "seed"], keep=False)
    if dupe_keys.any():
        dupe_rows = df[dupe_keys][["controller_id", "scenario_id", "seed"]].to_dict(orient="records")
        raise DuplicateRunError(
            f"Duplicate (controller_id, scenario_id, seed) combinations in '{source_file}': {dupe_rows}"
        )

    # Create a clean copy to avoid modifying original structures
    sanitized = df.copy()

    # Ensure all expected columns are present (fill missing optional columns with NaN/None)
    for col, dtype in EXPECTED_COLUMNS.items():
        if col not in sanitized.columns:
            sanitized[col] = pd.Series(np.nan, index=sanitized.index, dtype=dtype)
        else:
            # Cast numeric columns cleanly preserving NaN
            if col in NUMERIC_METRIC_COLUMNS:
                sanitized[col] = pd.to_numeric(sanitized[col], errors="coerce")
            elif col in INTEGER_COUNT_COLUMNS:
                sanitized[col] = pd.to_numeric(sanitized[col], errors="coerce").astype("Int64")
            else:
                sanitized[col] = sanitized[col].astype("string")

    return sanitized
