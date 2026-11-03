"""
SUMO process and TraCI simulation lifecycle manager for SIGNALSIM-INDIA (P2-M03).

Handles cross-platform SUMO binary discovery, command-line construction, process execution,
TraCI connection initialization, safe stepping, and guaranteed process cleanup.
"""

import os
from pathlib import Path
import shutil
from typing import Any, List, Optional, Union

import traci


class SumoNotFoundError(FileNotFoundError):
    """Raised when the SUMO executable cannot be discovered in PATH or standard directories."""
    pass


def find_sumo_binary(gui: bool = False) -> str:
    """
    Locates the SUMO executable across platforms and common install paths.

    Parameters
    ----------
    gui : bool, default False
        Whether to locate 'sumo-gui' instead of headless 'sumo'.

    Returns
    -------
    str
        Full path to the executable.

    Raises
    ------
    SumoNotFoundError
        If the executable cannot be located.
    """
    binary_name = "sumo-gui" if gui else "sumo"

    # 1. Search in system PATH
    found = shutil.which(binary_name)
    if found:
        return found

    # 2. Check SUMO_HOME environment variable
    sumo_home = os.environ.get("SUMO_HOME")
    if sumo_home:
        candidate = Path(sumo_home) / "bin" / (f"{binary_name}.exe" if os.name == "nt" else binary_name)
        if candidate.is_file():
            return str(candidate)

    # 3. Common Windows default installation paths
    if os.name == "nt":
        windows_defaults = [
            Path(r"C:\Program Files (x86)\Eclipse\Sumo\bin") / f"{binary_name}.exe",
            Path(r"C:\Program Files\Eclipse\Sumo\bin") / f"{binary_name}.exe",
            Path(r"C:\Program Files (x86)\SUMO\bin") / f"{binary_name}.exe",
            Path(r"C:\Program Files\SUMO\bin") / f"{binary_name}.exe",
        ]
        for p in windows_defaults:
            if p.is_file():
                return str(p)

    raise SumoNotFoundError(
        f"Could not locate '{binary_name}' in PATH or SUMO_HOME. "
        "Please ensure SUMO is installed and added to the system PATH."
    )


def build_sumo_command(
    sumo_binary: str,
    net_file: Union[str, Path],
    route_file: Union[str, Path],
    additional_file: Union[str, Path],
    end_time: float,
    step_length: float = 0.1,
    seed: int = 42,
    tripinfo_output: Optional[Union[str, Path]] = None,
    summary_output: Optional[Union[str, Path]] = None,
    log_output: Optional[Union[str, Path]] = None,
    lateral_resolution: float = 0.5,
    write_unfinished: bool = True,
    extra_args: Optional[List[str]] = None,
) -> List[str]:
    """
    Constructs standardized, reproducible SUMO command-line argument list.
    """
    cmd: List[str] = [
        str(sumo_binary),
        "-n", str(Path(net_file).resolve()),
        "-r", str(Path(route_file).resolve()),
        "-a", str(Path(additional_file).resolve()),
        "--begin", "0",
        "--end", str(end_time),
        "--step-length", str(step_length),
        "--seed", str(seed),
        "--lateral-resolution", str(lateral_resolution),
        "--collision.check-junctions", "true",
        "--collision.action", "warn",
        "--no-step-log", "true",
    ]

    if tripinfo_output:
        tripinfo_path = Path(tripinfo_output).resolve()
        tripinfo_path.parent.mkdir(parents=True, exist_ok=True)
        cmd.extend(["--tripinfo-output", str(tripinfo_path)])

    if write_unfinished:
        cmd.extend(["--tripinfo-output.write-unfinished", "true"])

    if summary_output:
        summary_path = Path(summary_output).resolve()
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        cmd.extend(["--summary-output", str(summary_path)])

    if log_output:
        log_path = Path(log_output).resolve()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        cmd.extend(["--log", str(log_path)])

    if extra_args:
        cmd.extend(extra_args)

    return cmd


class SumoSimulation:
    """
    Context manager for deterministic SUMO simulation lifecycle management.

    Ensures that TraCI is cleanly started with a label or default connection,
    provides the active connection to the caller, and guarantees that the
    connection and background SUMO process are terminated safely.
    """

    def __init__(self, command: List[str], label: Optional[str] = None):
        self.command = command
        self.label = label or "signalsim_sim"
        self.connection: Optional[Any] = None

    def __enter__(self) -> Any:
        # Start SUMO via TraCI
        # In modern traci, start() returns a Connection object or sets default connection
        traci.start(self.command, label=self.label)
        try:
            self.connection = traci.getConnection(self.label)
        except Exception:
            self.connection = traci
        return self.connection

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.connection is not None:
            try:
                self.connection.close()
            except Exception:
                try:
                    traci.close()
                except Exception:
                    pass
            self.connection = None
        return False
