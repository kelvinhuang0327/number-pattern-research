"""
tests/test_run_p26_true_date_historical_backfill.py

Integration tests for scripts/run_p26_true_date_historical_backfill.py.
Verifies:
  - Exit 0 when gate = P26_TRUE_DATE_HISTORICAL_BACKFILL_READY
  - Exit 1 when gate = P26_BLOCKED_NO_READY_DATES (no slices)
  - Exit 2 when p25_dir does not exist
  - Exit 2 when --paper-only false
  - All 6 output files present after successful run
  - Determinism: two runs produce identical functional output files
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pandas as pd
import pytest


_SCRIPT = "scripts/run_p26_true_date_historical_backfill.py"
_PYTHON = ".venv/bin/python"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_p17_slice_csv(date: str, n_eligible: int = 2, n_blocked: int = 1) -> pd.DataFrame:
    rows = []
    for i in range(n_eligible):
        rows.append({
            "ledger_id": f"L{i:03d}", "game_id": f"G{i:03d}", "date": date,
            "side": "HOME" if i % 2 == 0 else "AWAY", "p_model": 0.60,
            "p_market": 0.52, "edge": 0.08, "odds_decimal": 1.90,
            "paper_stake_units": 0.25, "paper_stake_fraction": 0.0025,
            "gate_decision": "P16_6_ELIGIBLE_PAPER_RECOMMENDATION",
            "gate_reason": "ELIGIBLE",
            "settlement_status": "SETTLED_WIN" if i % 2 == 0 else "SETTLED_LOSS",
            "pnl_units": 0.2375 if i % 2 == 0 else -0.25,
            "is_win": i % 2 == 0, "is_loss": i % 2 != 0, "is_push": False,
            "y_true": 1 if i % 2 == 0 else 0, "paper_only": True, "production_ready": False,
        })
    for j in range(n_blocked):
        rows.append({
            "ledger_id": f"B{j:03d}", "game_id": f"BG{j:03d}", "date": date,
            "side": "HOME", "p_model": 0.52, "p_market": 0.55, "edge": -0.03,
            "odds_decimal": 1.80, "paper_stake_units": 0.0, "paper_stake_fraction": 0.0,
            "gate_decision": "P16_6_BLOCKED_NEGATIVE_EDGE", "gate_reason": "NEGATIVE_EDGE",
            "settlement_status": "UNSETTLED_NOT_RECOMMENDED",
            "pnl_units": 0.0, "is_win": False, "is_loss": False, "is_push": False,
            "y_true": 1, "paper_only": True, "production_ready": False,
        })
    return pd.DataFrame(rows)


def _setup_p25_dir(base: Path, dates: list) -> Path:
    p25_dir = base / "p25"
    for d in dates:
        slice_dir = p25_dir / "true_date_slices" / d
        slice_dir.mkdir(parents=True, exist_ok=True)
        _make_p17_slice_csv(d).to_csv(slice_dir / "p15_true_date_input.csv", index=False)
    return p25_dir


def _run_cli(
    date_start: str,
    date_end: str,
    p25_dir: Path,
    output_dir: Path,
    paper_only: str = "true",
    cwd: str = "/Users/kelvin/Kelvin-WorkSpace/Betting-pool-p13",
) -> subprocess.CompletedProcess:
    cmd = [
        _PYTHON,
        _SCRIPT,
        "--date-start", date_start,
        "--date-end", date_end,
        "--p25-dir", str(p25_dir),
        "--output-dir", str(output_dir),
        "--paper-only", paper_only,
    ]
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=cwd,
        env={"PATH": "/usr/bin:/bin:/usr/local/bin", "PYTHONPATH": "."},
    )


# ---------------------------------------------------------------------------
# Exit code tests
# ---------------------------------------------------------------------------


class TestCliExitCodes:
    def test_exit_0_when_all_dates_ready(self, tmp_path: Path):
        p25_dir = _setup_p25_dir(tmp_path, ["2025-05-08", "2025-05-09"])
        out_dir = tmp_path / "out"
        r = _run_cli("2025-05-08", "2025-05-09", p25_dir, out_dir)
        assert r.returncode == 0, f"stdout={r.stdout}\nstderr={r.stderr}"

    def test_exit_1_when_no_slices_available(self, tmp_path: Path):
        p25_dir = tmp_path / "p25"
        p25_dir.mkdir(parents=True)
        out_dir = tmp_path / "out"
        r = _run_cli("2025-05-08", "2025-05-09", p25_dir, out_dir)
        assert r.returncode == 1, f"stdout={r.stdout}\nstderr={r.stderr}"

    def test_exit_2_when_p25_dir_missing(self, tmp_path: Path):
        out_dir = tmp_path / "out"
        r = _run_cli(
            "2025-05-08", "2025-05-09",
            tmp_path / "nonexistent_p25",
            out_dir,
        )
        assert r.returncode == 2, f"stdout={r.stdout}\nstderr={r.stderr}"

    def test_exit_2_when_paper_only_false(self, tmp_path: Path):
        p25_dir = _setup_p25_dir(tmp_path, ["2025-05-08"])
        out_dir = tmp_path / "out"
        r = _run_cli("2025-05-08", "2025-05-08", p25_dir, out_dir, paper_only="false")
        assert r.returncode == 2, f"stdout={r.stdout}\nstderr={r.stderr}"


# ---------------------------------------------------------------------------
# Output file tests
# ---------------------------------------------------------------------------


class TestCliOutputFiles:
    def test_all_six_files_written(self, tmp_path: Path):
        p25_dir = _setup_p25_dir(tmp_path, ["2025-05-08", "2025-05-09"])
        out_dir = tmp_path / "out"
        r = _run_cli("2025-05-08", "2025-05-09", p25_dir, out_dir)
        assert r.returncode == 0
        for fname in [
            "p26_gate_result.json",
            "true_date_replay_summary.json",
            "true_date_replay_summary.md",
            "date_replay_results.csv",
            "blocked_dates.json",
            "artifact_manifest.json",
        ]:
            assert (out_dir / fname).exists(), f"Missing {fname}"

    def test_gate_result_has_correct_gate(self, tmp_path: Path):
        p25_dir = _setup_p25_dir(tmp_path, ["2025-05-08"])
        out_dir = tmp_path / "out"
        r = _run_cli("2025-05-08", "2025-05-08", p25_dir, out_dir)
        data = json.loads((out_dir / "p26_gate_result.json").read_text())
        assert data["p26_gate"] == "P26_TRUE_DATE_HISTORICAL_BACKFILL_READY"

    def test_summary_json_paper_only_flag(self, tmp_path: Path):
        p25_dir = _setup_p25_dir(tmp_path, ["2025-05-08"])
        out_dir = tmp_path / "out"
        r = _run_cli("2025-05-08", "2025-05-08", p25_dir, out_dir)
        data = json.loads((out_dir / "true_date_replay_summary.json").read_text())
        assert data["paper_only"] is True
        assert data["production_ready"] is False

    def test_gate_blocked_when_no_slices(self, tmp_path: Path):
        p25_dir = tmp_path / "p25"
        p25_dir.mkdir(parents=True)
        out_dir = tmp_path / "out"
        r = _run_cli("2025-05-08", "2025-05-08", p25_dir, out_dir)
        assert r.returncode == 1
        if (out_dir / "p26_gate_result.json").exists():
            data = json.loads((out_dir / "p26_gate_result.json").read_text())
            assert "BLOCKED" in data["p26_gate"]

    def test_date_replay_results_csv_has_header(self, tmp_path: Path):
        p25_dir = _setup_p25_dir(tmp_path, ["2025-05-08"])
        out_dir = tmp_path / "out"
        _run_cli("2025-05-08", "2025-05-08", p25_dir, out_dir)
        csv_path = out_dir / "date_replay_results.csv"
        assert csv_path.exists()
        first_line = csv_path.read_text().splitlines()[0]
        assert "run_date" in first_line
        assert "replay_gate" in first_line


# ---------------------------------------------------------------------------
# Determinism tests
# ---------------------------------------------------------------------------


class TestCliDeterminism:
    def _functional_fields(self, json_path: Path) -> dict:
        data = json.loads(json_path.read_text())
        data.pop("generated_at", None)
        data.pop("output_dir", None)
        return data

    def test_gate_result_deterministic(self, tmp_path: Path):
        p25_dir = _setup_p25_dir(tmp_path, ["2025-05-08", "2025-05-09"])
        out1 = tmp_path / "run1"
        out2 = tmp_path / "run2"
        _run_cli("2025-05-08", "2025-05-09", p25_dir, out1)
        _run_cli("2025-05-08", "2025-05-09", p25_dir, out2)
        d1 = self._functional_fields(out1 / "p26_gate_result.json")
        d2 = self._functional_fields(out2 / "p26_gate_result.json")
        assert d1 == d2

    def test_summary_json_deterministic(self, tmp_path: Path):
        p25_dir = _setup_p25_dir(tmp_path, ["2025-05-08", "2025-05-09"])
        out1 = tmp_path / "run1"
        out2 = tmp_path / "run2"
        _run_cli("2025-05-08", "2025-05-09", p25_dir, out1)
        _run_cli("2025-05-08", "2025-05-09", p25_dir, out2)
        d1 = self._functional_fields(out1 / "true_date_replay_summary.json")
        d2 = self._functional_fields(out2 / "true_date_replay_summary.json")
        assert d1 == d2

    def test_date_replay_csv_deterministic(self, tmp_path: Path):
        p25_dir = _setup_p25_dir(tmp_path, ["2025-05-08", "2025-05-09"])
        out1 = tmp_path / "run1"
        out2 = tmp_path / "run2"
        _run_cli("2025-05-08", "2025-05-09", p25_dir, out1)
        _run_cli("2025-05-08", "2025-05-09", p25_dir, out2)
        csv1 = (out1 / "date_replay_results.csv").read_text()
        csv2 = (out2 / "date_replay_results.csv").read_text()
        assert csv1 == csv2

    def test_artifact_manifest_deterministic(self, tmp_path: Path):
        p25_dir = _setup_p25_dir(tmp_path, ["2025-05-08", "2025-05-09"])
        out1 = tmp_path / "run1"
        out2 = tmp_path / "run2"
        _run_cli("2025-05-08", "2025-05-09", p25_dir, out1)
        _run_cli("2025-05-08", "2025-05-09", p25_dir, out2)
        d1 = self._functional_fields(out1 / "artifact_manifest.json")
        d2 = self._functional_fields(out2 / "artifact_manifest.json")
        assert d1 == d2
