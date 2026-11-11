"""
tests/test_run_mlb_model_probability_audit_repair.py

P6 tests for scripts/run_mlb_model_probability_audit_repair.py CLI.
"""
from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = _REPO_ROOT / "scripts" / "run_mlb_model_probability_audit_repair.py"
_REAL_INPUT_CSV = (
    _REPO_ROOT / "outputs" / "predictions" / "PAPER" / "2026-05-11"
    / "mlb_odds_with_model_probabilities.csv"
)


def _run_script(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(_SCRIPT), *args],
        capture_output=True,
        text=True,
    )


def _build_minimal_csv(tmp_path: Path, n: int = 50) -> Path:
    """Build a small synthetic odds CSV with model_prob_home."""
    rows = []
    for i in range(n):
        hs, as_ = ("5", "2") if i % 2 == 0 else ("1", "3")
        prob = round(0.40 + (i % 5) * 0.04, 2)
        rows.append({
            "Date": f"2025-{(i // 28) + 4:02d}-{(i % 28) + 1:02d}",
            "Home": "KC",
            "Away": "HOU",
            "Home Score": hs,
            "Away Score": as_,
            "Status": "Final",
            "Home ML": "+100",
            "Away ML": "-120",
            "model_prob_home": str(prob),
            "model_prob_away": str(round(1 - prob, 2)),
            "probability_source": "calibrated_model",
        })

    path = tmp_path / "test_input.csv"
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return path


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestAuditRepairCLI:
    def test_writes_audit_json(self, tmp_path):
        csv_path = _build_minimal_csv(tmp_path)
        output_dir = tmp_path / "outputs" / "predictions" / "PAPER" / "test-run"
        result = _run_script(
            "--input-csv", str(csv_path),
            "--output-dir", str(output_dir),
            "--n-bins", "5",
            "--min-bin-size", "5",
        )
        assert result.returncode == 0, result.stderr
        audit_file = output_dir / "model_probability_audit.json"
        assert audit_file.exists(), f"audit JSON not found at {audit_file}"
        data = json.loads(audit_file.read_text())
        assert "row_count" in data
        assert data["row_count"] == 50

    def test_writes_calibrated_csv(self, tmp_path):
        csv_path = _build_minimal_csv(tmp_path)
        output_dir = tmp_path / "outputs" / "predictions" / "PAPER" / "test-run2"
        result = _run_script(
            "--input-csv", str(csv_path),
            "--output-dir", str(output_dir),
            "--n-bins", "5",
            "--min-bin-size", "5",
        )
        assert result.returncode == 0, result.stderr
        cal_csv = output_dir / "mlb_odds_with_calibrated_probabilities.csv"
        assert cal_csv.exists(), f"Calibrated CSV not found at {cal_csv}"
        with cal_csv.open() as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 50

    def test_refuses_non_paper_output_dir(self, tmp_path):
        csv_path = _build_minimal_csv(tmp_path)
        bad_dir = tmp_path / "not_paper" / "output"
        result = _run_script(
            "--input-csv", str(csv_path),
            "--output-dir", str(bad_dir),
        )
        assert result.returncode != 0, "Should refuse non-PAPER output dir"
        assert "REFUSED" in result.stderr

    def test_refuses_nonexistent_input(self, tmp_path):
        output_dir = tmp_path / "outputs" / "predictions" / "PAPER" / "test-noinput"
        result = _run_script(
            "--input-csv", str(tmp_path / "does_not_exist.csv"),
            "--output-dir", str(output_dir),
        )
        assert result.returncode != 0, "Should refuse missing input"
        assert "REFUSED" in result.stderr

    def test_calibrated_csv_row_count_matches_input(self, tmp_path):
        csv_path = _build_minimal_csv(tmp_path, n=30)
        output_dir = tmp_path / "outputs" / "predictions" / "PAPER" / "test-run3"
        result = _run_script(
            "--input-csv", str(csv_path),
            "--output-dir", str(output_dir),
            "--n-bins", "5",
            "--min-bin-size", "3",
        )
        assert result.returncode == 0, result.stderr
        cal_csv = output_dir / "mlb_odds_with_calibrated_probabilities.csv"
        with cal_csv.open() as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 30

    def test_stdout_contains_original_bss(self, tmp_path):
        csv_path = _build_minimal_csv(tmp_path)
        output_dir = tmp_path / "outputs" / "predictions" / "PAPER" / "test-stdout"
        result = _run_script(
            "--input-csv", str(csv_path),
            "--output-dir", str(output_dir),
            "--n-bins", "5",
            "--min-bin-size", "5",
        )
        assert result.returncode == 0, result.stderr
        assert "original_bss=" in result.stdout


class TestAuditRepairCLIWithRealData:
    """Tests that use the real P5 artifact CSV (skip if not available)."""

    @pytest.mark.skipif(
        not _REAL_INPUT_CSV.exists(),
        reason="Real P5 artifact CSV not available.",
    )
    def test_real_input_exits_zero(self, tmp_path):
        output_dir = tmp_path / "outputs" / "predictions" / "PAPER" / "real-test"
        result = _run_script(
            "--input-csv", str(_REAL_INPUT_CSV),
            "--output-dir", str(output_dir),
            "--n-bins", "10",
            "--min-bin-size", "30",
        )
        assert result.returncode == 0, result.stderr

    @pytest.mark.skipif(
        not _REAL_INPUT_CSV.exists(),
        reason="Real P5 artifact CSV not available.",
    )
    def test_real_input_audit_has_bss(self, tmp_path):
        output_dir = tmp_path / "outputs" / "predictions" / "PAPER" / "real-bss-test"
        result = _run_script(
            "--input-csv", str(_REAL_INPUT_CSV),
            "--output-dir", str(output_dir),
        )
        assert result.returncode == 0, result.stderr
        audit_file = output_dir / "model_probability_audit.json"
        data = json.loads(audit_file.read_text())
        assert data["brier_skill_score"] is not None
