"""
tests/test_run_p21_multi_day_paper_backfill.py

CLI integration tests for run_p21_multi_day_paper_backfill.py.
"""
import csv
import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "run_p21_multi_day_paper_backfill.py"
PYTHON = str(REPO_ROOT / ".venv" / "bin" / "python")


def _run_cli(args: list[str]) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    return subprocess.run(
        [PYTHON, str(SCRIPT)] + args,
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        env=env,
    )


def _write_valid_p20_dir(base: Path, run_date: str) -> Path:
    """Create a fully valid P20 date directory."""
    date_dir = base / run_date / "p20_daily_paper_orchestrator"
    date_dir.mkdir(parents=True, exist_ok=True)

    gate = {
        "run_date": run_date,
        "p20_gate": "P20_DAILY_PAPER_ORCHESTRATOR_READY",
        "paper_only": True,
        "production_ready": False,
    }
    (date_dir / "p20_gate_result.json").write_text(json.dumps(gate), encoding="utf-8")

    summary = {
        "p20_gate": "P20_DAILY_PAPER_ORCHESTRATOR_READY",
        "n_recommended_rows": 324,
        "n_active_paper_entries": 324,
        "n_settled_win": 171,
        "n_settled_loss": 153,
        "n_unsettled": 0,
        "total_stake_units": 324.0,
        "total_pnl_units": 34.921,
        "roi_units": 0.10778278086419754,
        "hit_rate": 0.5277777777777778,
        "game_id_coverage": 1.0,
        "settlement_join_method": "JOIN_BY_GAME_ID",
        "paper_only": True,
        "production_ready": False,
    }
    (date_dir / "daily_paper_summary.json").write_text(json.dumps(summary), encoding="utf-8")
    (date_dir / "artifact_manifest.json").write_text(
        json.dumps({"run_date": run_date, "artifacts": []}), encoding="utf-8"
    )
    return date_dir


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_cli_happy_path_exit_0():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / "PAPER"
        out = Path(tmp) / "out"
        _write_valid_p20_dir(base, "2026-05-12")
        result = _run_cli([
            "--date-start", "2026-05-12",
            "--date-end", "2026-05-12",
            "--paper-base-dir", str(base),
            "--output-dir", str(out),
            "--paper-only", "true",
        ])
        assert result.returncode == 0, result.stderr
        assert "P21_MULTI_DAY_PAPER_BACKFILL_READY" in result.stdout


def test_cli_creates_5_output_files():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / "PAPER"
        out = Path(tmp) / "out"
        _write_valid_p20_dir(base, "2026-05-12")
        result = _run_cli([
            "--date-start", "2026-05-12",
            "--date-end", "2026-05-12",
            "--paper-base-dir", str(base),
            "--output-dir", str(out),
            "--paper-only", "true",
        ])
        assert result.returncode == 0, result.stderr
        for fname in [
            "backfill_summary.json",
            "backfill_summary.md",
            "date_results.csv",
            "missing_artifacts.json",
            "p21_gate_result.json",
        ]:
            assert (out / fname).exists(), f"Missing: {fname}"


def test_cli_gate_result_fields():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / "PAPER"
        out = Path(tmp) / "out"
        _write_valid_p20_dir(base, "2026-05-12")
        _run_cli([
            "--date-start", "2026-05-12",
            "--date-end", "2026-05-12",
            "--paper-base-dir", str(base),
            "--output-dir", str(out),
            "--paper-only", "true",
        ])
        gate = json.loads((out / "p21_gate_result.json").read_text())
        assert gate["p21_gate"] == "P21_MULTI_DAY_PAPER_BACKFILL_READY"
        assert gate["paper_only"] is True
        assert gate["production_ready"] is False
        assert gate["n_dates_requested"] == 1
        assert gate["n_dates_ready"] == 1
        assert gate["n_dates_missing"] == 0


def test_cli_missing_date_reported_not_fabricated():
    """When date has no artifacts, it must appear in missing_artifacts.json."""
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / "PAPER"
        out = Path(tmp) / "out"
        # Only 2026-05-12 exists; 2026-05-11 is missing
        _write_valid_p20_dir(base, "2026-05-12")
        _run_cli([
            "--date-start", "2026-05-11",
            "--date-end", "2026-05-12",
            "--paper-base-dir", str(base),
            "--output-dir", str(out),
            "--paper-only", "true",
        ])
        missing = json.loads((out / "missing_artifacts.json").read_text())
        dates_in_missing = [m["run_date"] for m in missing]
        assert "2026-05-11" in dates_in_missing


def test_cli_exit_1_when_no_ready_dates():
    """When all dates are missing (no ready runs), CLI must exit 1."""
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / "PAPER"
        base.mkdir(parents=True)  # base dir exists but has no date subdirs
        out = Path(tmp) / "out"
        result = _run_cli([
            "--date-start", "2026-05-11",
            "--date-end", "2026-05-11",
            "--paper-base-dir", str(base),
            "--output-dir", str(out),
            "--paper-only", "true",
        ])
        assert result.returncode == 1, result.stdout
        assert "BLOCKED" in result.stdout


def test_cli_exit_2_on_paper_only_false():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / "PAPER"
        out = Path(tmp) / "out"
        result = _run_cli([
            "--date-start", "2026-05-12",
            "--date-end", "2026-05-12",
            "--paper-base-dir", str(base),
            "--output-dir", str(out),
            "--paper-only", "false",
        ])
        assert result.returncode == 2


def test_cli_exit_2_on_missing_base_dir():
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "out"
        result = _run_cli([
            "--date-start", "2026-05-12",
            "--date-end", "2026-05-12",
            "--paper-base-dir", "/nonexistent/path/does/not/exist",
            "--output-dir", str(out),
            "--paper-only", "true",
        ])
        assert result.returncode == 2


def test_cli_deterministic():
    """Two runs on the same input must produce identical gate/summary fields (excl. generated_at)."""
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / "PAPER"
        out1 = Path(tmp) / "out1"
        out2 = Path(tmp) / "out2"
        _write_valid_p20_dir(base, "2026-05-12")

        args = [
            "--date-start", "2026-05-12",
            "--date-end", "2026-05-12",
            "--paper-base-dir", str(base),
            "--paper-only", "true",
        ]
        _run_cli(args + ["--output-dir", str(out1)])
        _run_cli(args + ["--output-dir", str(out2)])

        # Compare gate result excluding generated_at
        def _gate_without_ts(out_dir):
            g = json.loads((out_dir / "p21_gate_result.json").read_text())
            g.pop("generated_at", None)
            return g

        g1 = _gate_without_ts(out1)
        g2 = _gate_without_ts(out2)
        assert g1 == g2, f"Gate mismatch:\nRun1: {g1}\nRun2: {g2}"

        # date_results.csv must be identical
        csv1 = (out1 / "date_results.csv").read_text()
        csv2 = (out2 / "date_results.csv").read_text()
        assert csv1 == csv2, "date_results.csv differs between runs"

        # missing_artifacts.json must be identical
        m1 = json.loads((out1 / "missing_artifacts.json").read_text())
        m2 = json.loads((out2 / "missing_artifacts.json").read_text())
        assert m1 == m2
