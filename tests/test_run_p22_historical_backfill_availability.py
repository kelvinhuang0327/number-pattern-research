"""
Tests for P22 CLI: run_p22_historical_backfill_availability.py

Covers:
- exit 0 when at least one available date exists
- exit 1 when all dates are blocked/missing (no candidates)
- exit 2 when paper-only false
- exit 2 when base dir missing
- All 6 output files are written
- Gate fields present in p22_gate_result.json
- Determinism: two runs with same inputs produce identical outputs
- P20-ready date correctly identified
- Missing date explicitly reported in CSV
"""
from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path
from typing import List

import pytest

REPO_ROOT = Path(__file__).parent.parent
SCRIPT = REPO_ROOT / "scripts" / "run_p22_historical_backfill_availability.py"

EXPECTED_P20_GATE = "P20_DAILY_PAPER_ORCHESTRATOR_READY"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_cli(
    args: List[str],
    tmp_path: Path,
) -> subprocess.CompletedProcess[str]:
    env = {"PYTHONPATH": str(REPO_ROOT), "PATH": "/usr/bin:/bin:/usr/local/bin"}
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(REPO_ROOT),
    )


def _write_p20(date_dir: Path) -> None:
    p20_dir = date_dir / "p20_daily_paper_orchestrator"
    p20_dir.mkdir(parents=True, exist_ok=True)
    (p20_dir / "daily_paper_summary.json").write_text(json.dumps({"n_active": 1}), encoding="utf-8")
    (p20_dir / "p20_gate_result.json").write_text(
        json.dumps({"p20_gate": EXPECTED_P20_GATE}), encoding="utf-8"
    )
    (p20_dir / "artifact_manifest.json").write_text(json.dumps({}), encoding="utf-8")


# ---------------------------------------------------------------------------
# Fatal / BLOCKED exits
# ---------------------------------------------------------------------------


def test_cli_exit_2_paper_only_false(tmp_path: Path) -> None:
    base = tmp_path / "PAPER"
    base.mkdir()
    out = tmp_path / "out"
    result = _run_cli(
        [
            "--date-start", "2026-05-12",
            "--date-end", "2026-05-12",
            "--paper-base-dir", str(base),
            "--output-dir", str(out),
            "--paper-only", "false",
        ],
        tmp_path,
    )
    assert result.returncode == 2
    assert "paper-only" in result.stderr.lower() or "paper_only" in result.stderr.lower()


def test_cli_exit_2_missing_base_dir(tmp_path: Path) -> None:
    out = tmp_path / "out"
    result = _run_cli(
        [
            "--date-start", "2026-05-12",
            "--date-end", "2026-05-12",
            "--paper-base-dir", str(tmp_path / "nonexistent"),
            "--output-dir", str(out),
            "--paper-only", "true",
        ],
        tmp_path,
    )
    assert result.returncode == 2


def test_cli_exit_1_when_no_available_dates(tmp_path: Path) -> None:
    """All dates missing → BLOCKED → exit 1."""
    base = tmp_path / "PAPER"
    base.mkdir()  # exists but no date subdirs
    out = tmp_path / "out"
    result = _run_cli(
        [
            "--date-start", "2026-05-01",
            "--date-end", "2026-05-03",
            "--paper-base-dir", str(base),
            "--output-dir", str(out),
            "--paper-only", "true",
        ],
        tmp_path,
    )
    assert result.returncode == 1
    assert "BLOCKED" in result.stdout


# ---------------------------------------------------------------------------
# Successful run (exit 0)
# ---------------------------------------------------------------------------


def test_cli_exit_0_when_p20_ready(tmp_path: Path) -> None:
    base = tmp_path / "PAPER"
    _write_p20(base / "2026-05-12")
    out = tmp_path / "out"
    result = _run_cli(
        [
            "--date-start", "2026-05-12",
            "--date-end", "2026-05-12",
            "--paper-base-dir", str(base),
            "--output-dir", str(out),
            "--paper-only", "true",
        ],
        tmp_path,
    )
    assert result.returncode == 0, result.stderr
    assert "SUCCESS" in result.stdout
    assert "P22_HISTORICAL_BACKFILL_AVAILABILITY_READY" in result.stdout


def test_cli_writes_all_6_output_files(tmp_path: Path) -> None:
    base = tmp_path / "PAPER"
    _write_p20(base / "2026-05-12")
    out = tmp_path / "out"
    _run_cli(
        [
            "--date-start", "2026-05-12",
            "--date-end", "2026-05-12",
            "--paper-base-dir", str(base),
            "--output-dir", str(out),
            "--paper-only", "true",
        ],
        tmp_path,
    )
    expected_files = [
        "historical_availability_summary.json",
        "historical_availability_summary.md",
        "date_availability_results.csv",
        "backfill_execution_plan.json",
        "backfill_execution_plan.md",
        "p22_gate_result.json",
    ]
    for fname in expected_files:
        assert (out / fname).exists(), f"Missing: {fname}"


def test_cli_gate_result_fields(tmp_path: Path) -> None:
    base = tmp_path / "PAPER"
    _write_p20(base / "2026-05-12")
    out = tmp_path / "out"
    _run_cli(
        [
            "--date-start", "2026-05-12",
            "--date-end", "2026-05-12",
            "--paper-base-dir", str(base),
            "--output-dir", str(out),
            "--paper-only", "true",
        ],
        tmp_path,
    )
    gate = json.loads((out / "p22_gate_result.json").read_text(encoding="utf-8"))
    assert gate["p22_gate"] == "P22_HISTORICAL_BACKFILL_AVAILABILITY_READY"
    assert gate["paper_only"] is True
    assert gate["production_ready"] is False
    assert gate["n_dates_scanned"] == 1
    assert gate["n_dates_p20_ready"] == 1
    assert "generated_at" in gate


def test_cli_missing_date_in_csv(tmp_path: Path) -> None:
    """A missing date should appear in the CSV with DATE_MISSING_REQUIRED_SOURCE."""
    base = tmp_path / "PAPER"
    _write_p20(base / "2026-05-12")
    out = tmp_path / "out"
    _run_cli(
        [
            "--date-start", "2026-05-11",
            "--date-end", "2026-05-12",
            "--paper-base-dir", str(base),
            "--output-dir", str(out),
            "--paper-only", "true",
        ],
        tmp_path,
    )
    csv_path = out / "date_availability_results.csv"
    assert csv_path.exists()
    rows = list(csv.DictReader(csv_path.open(encoding="utf-8")))
    dates = {r["run_date"]: r for r in rows}
    assert "2026-05-11" in dates
    assert dates["2026-05-11"]["availability_status"] == "DATE_MISSING_REQUIRED_SOURCE"
    assert dates["2026-05-12"]["availability_status"] == "DATE_READY_P20_EXISTS"


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_cli_deterministic_across_two_runs(tmp_path: Path) -> None:
    base = tmp_path / "PAPER"
    _write_p20(base / "2026-05-12")
    out1 = tmp_path / "run1"
    out2 = tmp_path / "run2"

    _run_cli(
        [
            "--date-start", "2026-05-12",
            "--date-end", "2026-05-12",
            "--paper-base-dir", str(base),
            "--output-dir", str(out1),
            "--paper-only", "true",
        ],
        tmp_path,
    )
    _run_cli(
        [
            "--date-start", "2026-05-12",
            "--date-end", "2026-05-12",
            "--paper-base-dir", str(base),
            "--output-dir", str(out2),
            "--paper-only", "true",
        ],
        tmp_path,
    )

    def load_stripped(path: Path) -> dict:
        d = json.loads(path.read_text(encoding="utf-8"))
        d.pop("generated_at", None)
        return d

    g1 = load_stripped(out1 / "p22_gate_result.json")
    g2 = load_stripped(out2 / "p22_gate_result.json")
    assert g1 == g2, "p22_gate_result.json MISMATCH"

    s1 = load_stripped(out1 / "historical_availability_summary.json")
    s2 = load_stripped(out2 / "historical_availability_summary.json")
    assert s1 == s2, "historical_availability_summary.json MISMATCH"

    csv1 = (out1 / "date_availability_results.csv").read_text(encoding="utf-8")
    csv2 = (out2 / "date_availability_results.csv").read_text(encoding="utf-8")
    assert csv1 == csv2, "date_availability_results.csv MISMATCH"
