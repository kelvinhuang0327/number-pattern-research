"""
wbc_backend/recommendation/p27_p25_full_range_runner.py

P27 — P25 full-range separation runner.

Invokes scripts/run_p25_true_date_source_separation.py for the full
true-date range (2025-05-08 → 2025-09-28) and validates outputs.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple


_P25_SCRIPT = "scripts/run_p25_true_date_source_separation.py"
_P25_GATE_READY = "P25_TRUE_DATE_SOURCE_SEPARATION_READY"


def run_p25_separation_for_range(
    date_start: str,
    date_end: str,
    output_dir: Path,
    scan_base_paths: Optional[List[str]] = None,
    cwd: Optional[str] = None,
) -> Tuple[int, str, str]:
    """
    Run P25 source separation CLI for the given date range.

    Returns (returncode, stdout, stderr).
    Raises FileNotFoundError if the P25 script is not found.
    """
    repo_root = Path(cwd) if cwd else Path.cwd()
    script_path = repo_root / _P25_SCRIPT
    if not script_path.exists():
        raise FileNotFoundError(f"P25 script not found: {script_path}")

    scan_paths = scan_base_paths if scan_base_paths else ["data", "outputs"]

    cmd = [
        sys.executable,
        str(script_path),
        "--date-start", date_start,
        "--date-end", date_end,
        "--output-dir", str(output_dir),
        "--paper-only", "true",
    ]
    for sp in scan_paths:
        cmd += ["--scan-base-path", sp]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(repo_root),
        env=_make_env(),
    )
    return result.returncode, result.stdout, result.stderr


def validate_p25_full_range_outputs(p25_dir: Path) -> Tuple[bool, str]:
    """
    Validate that a P25 output directory is ready for P27 replay.

    Checks:
    - Directory exists
    - p25_gate_result.json is present and gate is READY
    - true_date_slices/ subdirectory exists with at least one date
    - No 2026 relabeling: slice dirs must be dated in the expected historical range

    Returns (is_valid, reason).
    """
    if not p25_dir.exists():
        return False, f"P25 output dir does not exist: {p25_dir}"

    gate_path = p25_dir / "p25_gate_result.json"
    if not gate_path.exists():
        return False, f"P25 gate result not found: {gate_path}"

    try:
        gate_data = json.loads(gate_path.read_text())
    except Exception as e:
        return False, f"P25 gate result JSON parse error: {e}"

    p25_gate = gate_data.get("p25_gate", "")
    if p25_gate != _P25_GATE_READY:
        return False, f"P25 gate is not READY: {p25_gate}"

    slices_dir = p25_dir / "true_date_slices"
    if not slices_dir.exists():
        return False, f"P25 true_date_slices/ not found in {p25_dir}"

    slice_dates = sorted([d.name for d in slices_dir.iterdir() if d.is_dir()])
    if not slice_dates:
        return False, f"P25 true_date_slices/ is empty in {p25_dir}"

    # Check no 2026 relabeling
    for d in slice_dates:
        if d.startswith("2026"):
            return False, f"Forbidden 2026-relabeled slice detected: {d}"

    return True, ""


def summarize_p25_full_range_outputs(p25_dir: Path) -> Dict:
    """
    Summarize P25 output directory contents.

    Returns a JSON-serializable dict.
    """
    if not p25_dir.exists():
        return {"error": f"P25 dir not found: {p25_dir}", "n_slice_dates": 0}

    gate_path = p25_dir / "p25_gate_result.json"
    gate_data: Dict = {}
    if gate_path.exists():
        try:
            gate_data = json.loads(gate_path.read_text())
        except Exception:
            gate_data = {"parse_error": True}

    slices_dir = p25_dir / "true_date_slices"
    slice_dates: List[str] = []
    if slices_dir.exists():
        slice_dates = sorted([d.name for d in slices_dir.iterdir() if d.is_dir()])

    # Count total CSV rows across all slices
    total_rows = 0
    for d in slice_dates:
        csv_path = slices_dir / d / "p15_true_date_input.csv"
        if csv_path.exists():
            try:
                lines = csv_path.read_text().splitlines()
                # subtract header
                total_rows += max(0, len(lines) - 1)
            except Exception:
                pass

    return {
        "p25_output_dir": str(p25_dir),
        "p25_gate": gate_data.get("p25_gate", "UNKNOWN"),
        "n_slice_dates": len(slice_dates),
        "slice_dates_sample": slice_dates[:5],
        "slice_dates_last": slice_dates[-5:] if len(slice_dates) > 5 else [],
        "total_rows_across_slices": total_rows,
        "paper_only": gate_data.get("paper_only", True),
        "production_ready": gate_data.get("production_ready", False),
    }


def _make_env() -> Dict[str, str]:
    """Build environment dict with PYTHONPATH=. for subprocess calls."""
    import os
    env = dict(os.environ)
    env["PYTHONPATH"] = "."
    return env
