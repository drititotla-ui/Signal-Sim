"""
Validation script for SIGNALSIM-INDIA YAML configuration files.

This script parses and validates:
- configs/experiment.yaml
- configs/scenarios/S1.yaml
- configs/scenarios/S2.yaml
- configs/scenarios/S3.yaml
- configs/scenarios/S4.yaml

It parses the YAML structure, validates syntax, verifies expected keys,
and confirms the provisional scenario multipliers (0.50, 0.75, 1.00, 1.25).
"""

from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Tuple, Union


def parse_yaml_scalar(val_str: str) -> Any:
    """Parses a YAML scalar value into a Python primitive."""
    val_str = val_str.strip()
    if not val_str:
        return None
    # Boolean
    if val_str.lower() == "true":
        return True
    if val_str.lower() == "false":
        return False
    # Quoted string
    if (val_str.startswith('"') and val_str.endswith('"')) or (
        val_str.startswith("'") and val_str.endswith("'")
    ):
        return val_str[1:-1]
    # Integer
    if re.match(r"^-?\d+$", val_str):
        return int(val_str)
    # Float
    if re.match(r"^-?\d+\.\d+$", val_str):
        return float(val_str)
    # Default unquoted string
    return val_str


def parse_simple_yaml(text: str) -> Union[Dict[str, Any], List[Any]]:
    """
    Recursive-descent line-based YAML parser for structured configuration files.
    Supports mappings, block sequences, nested objects, comments, and basic scalars.
    """
    raw_lines = text.splitlines()
    clean_tokens: List[Tuple[int, str]] = []

    for line in raw_lines:
        # Strip trailing comments unless inside quotes
        comment_idx = -1
        in_double = False
        in_single = False
        for idx, ch in enumerate(line):
            if ch == '"' and not in_single:
                in_double = not in_double
            elif ch == "'" and not in_double:
                in_single = not in_single
            elif ch == "#" and not in_double and not in_single:
                comment_idx = idx
                break

        if comment_idx != -1:
            line = line[:comment_idx]

        rstrip_line = line.rstrip()
        if not rstrip_line:
            continue

        indent = len(rstrip_line) - len(rstrip_line.lstrip(" "))
        content = rstrip_line.lstrip(" ")
        clean_tokens.append((indent, content))

    idx = 0

    def parse_block(current_indent: int) -> Any:
        nonlocal idx
        if idx >= len(clean_tokens):
            return None

        first_indent, first_content = clean_tokens[idx]
        if first_content.startswith("- "):
            # Sequence
            seq: List[Any] = []
            while idx < len(clean_tokens):
                indent, content = clean_tokens[idx]
                if indent < current_indent:
                    break
                if indent == current_indent and content.startswith("- "):
                    item_str = content[2:].strip()
                    idx += 1
                    if not item_str:
                        # Nested mapping or sequence under list item
                        if idx < len(clean_tokens) and clean_tokens[idx][0] > indent:
                            seq.append(parse_block(clean_tokens[idx][0]))
                        else:
                            seq.append(None)
                    else:
                        if ":" in item_str and not item_str.startswith('"'):
                            # Mapping inside sequence item: e.g. - id: "fixed_time"
                            k, v = item_str.split(":", 1)
                            k = k.strip()
                            v = v.strip()
                            map_item: Dict[str, Any] = {k: parse_yaml_scalar(v) if v else None}
                            # Check subsequent keys with deeper indent
                            while idx < len(clean_tokens) and clean_tokens[idx][0] > indent:
                                sub_indent, sub_content = clean_tokens[idx]
                                if ":" in sub_content:
                                    sk, sv = sub_content.split(":", 1)
                                    map_item[sk.strip()] = parse_yaml_scalar(sv.strip()) if sv.strip() else None
                                    idx += 1
                                else:
                                    break
                            seq.append(map_item)
                        else:
                            seq.append(parse_yaml_scalar(item_str))
                else:
                    break
            return seq
        else:
            # Mapping
            mapping: Dict[str, Any] = {}
            while idx < len(clean_tokens):
                indent, content = clean_tokens[idx]
                if indent < current_indent:
                    break
                if indent == current_indent:
                    if ":" not in content:
                        raise ValueError(f"Malformed YAML key-value pair: {content}")
                    key, val = content.split(":", 1)
                    key = key.strip()
                    val = val.strip()
                    idx += 1

                    if not val:
                        # Value is in subsequent nested block
                        if idx < len(clean_tokens) and clean_tokens[idx][0] > indent:
                            next_indent = clean_tokens[idx][0]
                            mapping[key] = parse_block(next_indent)
                        else:
                            mapping[key] = None
                    else:
                        mapping[key] = parse_yaml_scalar(val)
                elif indent > current_indent:
                    # Deeper indent handled recursively
                    mapping[key] = parse_block(indent)
                else:
                    break
            return mapping

    if not clean_tokens:
        return {}

    return parse_block(clean_tokens[0][0])


def validate_all_configs(project_root: Path) -> bool:
    """Validates experiment.yaml and all scenario YAML files."""
    configs_dir = project_root / "configs"
    experiment_file = configs_dir / "experiment.yaml"
    scenarios_dir = configs_dir / "scenarios"

    print("=" * 60)
    print("SIGNALSIM-INDIA YAML Configuration Validator")
    print("=" * 60)

    # 1. Validate experiment.yaml
    if not experiment_file.is_file():
        print(f"FAIL: Missing experiment config at {experiment_file}")
        return False

    exp_text = experiment_file.read_text(encoding="utf-8")
    try:
        exp_data = parse_simple_yaml(exp_text)
        print(f"PASS: Parsed {experiment_file.name} successfully.")
    except Exception as err:
        print(f"FAIL: Error parsing {experiment_file.name}: {err}")
        return False

    # Check key sections in experiment.yaml
    required_exp_sections = ["experiment", "simulation", "seeds", "controllers", "paths", "routes"]
    for sec in required_exp_sections:
        if sec not in exp_data:
            print(f"FAIL: Section '{sec}' missing from experiment.yaml")
            return False
    print("PASS: experiment.yaml contains all required top-level sections.")

    # Check seeds
    seeds = exp_data["seeds"]["evaluation_seeds"]
    expected_seeds = [42, 101, 202, 303, 404]
    if seeds != expected_seeds:
        print(f"FAIL: Expected seeds {expected_seeds}, found {seeds}")
        return False
    print(f"PASS: Evaluation seeds verified: {seeds}")

    # 2. Validate Scenarios S1 - S4
    expected_multipliers = {
        "S1": 0.50,
        "S2": 0.75,
        "S3": 1.00,
        "S4": 1.25,
    }

    for sc_id, expected_mult in expected_multipliers.items():
        sc_file = scenarios_dir / f"{sc_id}.yaml"
        if not sc_file.is_file():
            print(f"FAIL: Missing scenario file {sc_file}")
            return False

        sc_text = sc_file.read_text(encoding="utf-8")
        try:
            sc_data = parse_simple_yaml(sc_text)
            print(f"PASS: Parsed {sc_file.name} successfully.")
        except Exception as err:
            print(f"FAIL: Error parsing {sc_file.name}: {err}")
            return False

        # Check required scenario sections
        required_sc_sections = ["scenario", "vehicle_composition", "turning_proportions", "scenario_settings"]
        for sec in required_sc_sections:
            if sec not in sc_data:
                print(f"FAIL: Section '{sec}' missing in {sc_file.name}")
                return False

        # Verify scenario ID
        actual_id = sc_data["scenario"]["id"]
        if actual_id != sc_id:
            print(f"FAIL: Scenario ID mismatch in {sc_file.name}: expected {sc_id}, got {actual_id}")
            return False

        # Verify demand multiplier
        actual_mult = sc_data["scenario"]["demand_multiplier"]
        if abs(actual_mult - expected_mult) > 1e-6:
            print(f"FAIL: Multiplier mismatch in {sc_file.name}: expected {expected_mult}, got {actual_mult}")
            return False

        print(f"PASS: Scenario {sc_id} validated: demand_multiplier = {actual_mult:.2f}")

    print("=" * 60)
    print("ALL YAML CONFIGURATIONS ARE VALID AND MULTIPLIERS CONFIRMED.")
    print("=" * 60)
    return True


if __name__ == "__main__":
    project_root = Path(__file__).resolve().parent.parent
    success = validate_all_configs(project_root)
    if not success:
        sys.exit(1)

