"""
tests/test_run_mlb_oof_calibration_validation.py

P7: Tests for the OOF calibration CLI script.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# CLI module import
_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from scripts.run_mlb_oof_calibration_validation import (
    _assert_paper_output_dir,
    _detect_date_col,
    _detect_proxy_rows,
)


# ── Fixture helpers ──────────────────────────────────────────────────────────

def _make_enriched_csv(tmp_path: Path, rows: list[dict] | None = None) -> Path:
    """Write a minimal enriched CSV to tmp_path and return its path."""
    if rows is None:
        rows = [
            {
                "Date": f"2025-{(3 + i // 80):02d}-{(i % 28 + 1):02d}",
                "model_prob_home": "0.55",
                "home_win": "1" if i % 2 == 0 else "0",
                "probability_source": "real_model",
                "Away ML": "+110",
                "Home ML": "-130",
                "Status": "Final",
            }
            for i in range(400)
        ]
    p = tmp_path / "mlb_odds_with_model_probabilities.csv"
    with p.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return p


# ── Tests: _assert_paper_output_dir ─────────────────────────────────────────

class TestAssertPaperOutputDir:
    def test_accepts_paper_path(self, tmp_path):
        """Path containing PAPER/predictions zone should not raise."""
        paper_path = tmp_path / "outputs" / "predictions" / "PAPER" / "2026-05-11"
        paper_path.mkdir(parents=True)
        # Should not call sys.exit
        with patch("scripts.run_mlb_oof_calibration_validation._PAPER_PREDICTIONS_ZONE",
                   "outputs/predictions/PAPER"):
            _assert_paper_output_dir(paper_path)

    def test_rejects_non_paper_path(self, tmp_path):
        """Path NOT containing PAPER zone should exit with code 2."""
        non_paper = tmp_path / "some_other_dir"
        non_paper.mkdir()
        with pytest.raises(SystemExit) as exc_info:
            _assert_paper_output_dir(non_paper)
        assert exc_info.value.code == 2


# ── Tests: _detect_date_col ──────────────────────────────────────────────────

class TestDetectDateCol:
    def test_detects_date_col_capital(self):
        rows = [{"Date": "2025-03-01", "x": "y"}]
        col = _detect_date_col(rows, "date")
        assert col == "Date"

    def test_detects_date_col_lowercase(self):
        rows = [{"date": "2025-03-01", "x": "y"}]
        col = _detect_date_col(rows, "date")
        assert col == "date"

    def test_returns_none_when_no_date_col(self):
        rows = [{"x": "y", "foo": "bar"}]
        col = _detect_date_col(rows, "date")
        assert col is None


# ── Tests: _detect_proxy_rows ────────────────────────────────────────────────

class TestDetectProxyRows:
    def test_no_proxy_rows(self):
        rows = [
            {"model_prob_home": "0.55", "probability_source": "real_model"}
            for _ in range(50)
        ]
        proxy, enriched = _detect_proxy_rows(rows)
        assert enriched == 50
        assert proxy == 0

    def test_all_proxy_rows(self):
        rows = [
            {"model_prob_home": "0.55", "probability_source": "market_proxy"}
            for _ in range(50)
        ]
        proxy, enriched = _detect_proxy_rows(rows)
        assert enriched == 50
        assert proxy == 50

    def test_no_enriched_rows(self):
        rows = [{"x": "y"} for _ in range(50)]
        proxy, enriched = _detect_proxy_rows(rows)
        assert enriched == 0
        assert proxy == 0


# ── Tests: CLI via subprocess ────────────────────────────────────────────────

class TestCLIIntegration:
    def _run_cli(self, args: list[str]) -> tuple[int, str, str]:
        """Run the CLI script and return (returncode, stdout, stderr)."""
        import subprocess
        result = subprocess.run(
            [sys.executable, str(_REPO_ROOT / "scripts" / "run_mlb_oof_calibration_validation.py")]
            + args,
            capture_output=True,
            text=True,
            cwd=str(_REPO_ROOT),
        )
        return result.returncode, result.stdout, result.stderr

    def test_cli_refuses_missing_input(self, tmp_path):
        """CLI must exit 1 when --input-csv does not exist."""
        returncode, stdout, stderr = self._run_cli([
            "--input-csv", str(tmp_path / "nonexistent.csv"),
        ])
        assert returncode == 1
        assert "REFUSED" in stderr

    def test_cli_refuses_non_paper_output_dir(self, tmp_path):
        """CLI must exit 2 when --output-dir is outside PAPER zone."""
        input_csv = _make_enriched_csv(tmp_path)
        non_paper_dir = tmp_path / "some_other_output"
        non_paper_dir.mkdir()
        returncode, stdout, stderr = self._run_cli([
            "--input-csv", str(input_csv),
            "--output-dir", str(non_paper_dir),
        ])
        assert returncode == 2
        assert "REFUSED" in stderr

    def test_cli_writes_oof_csv(self, tmp_path):
        """CLI must write mlb_odds_with_oof_calibrated_probabilities.csv under output dir."""
        input_csv = _make_enriched_csv(tmp_path)
        output_dir = tmp_path / "outputs" / "predictions" / "PAPER" / "test-run"
        output_dir.mkdir(parents=True)
        returncode, stdout, stderr = self._run_cli([
            "--input-csv", str(input_csv),
            "--output-dir", str(output_dir),
            "--min-train-size", "200",
            "--initial-train-months", "2",
        ])
        assert returncode == 0, f"CLI failed with stderr: {stderr}"
        assert (output_dir / "mlb_odds_with_oof_calibrated_probabilities.csv").exists()

    def test_cli_writes_evaluation_json(self, tmp_path):
        """CLI must write oof_calibration_evaluation.json."""
        input_csv = _make_enriched_csv(tmp_path)
        output_dir = tmp_path / "outputs" / "predictions" / "PAPER" / "test-run"
        output_dir.mkdir(parents=True)
        returncode, stdout, stderr = self._run_cli([
            "--input-csv", str(input_csv),
            "--output-dir", str(output_dir),
            "--min-train-size", "200",
            "--initial-train-months", "2",
        ])
        assert returncode == 0, f"CLI failed with stderr: {stderr}"
        eval_path = output_dir / "oof_calibration_evaluation.json"
        assert eval_path.exists()
        data = json.loads(eval_path.read_text())
        assert "recommendation" in data
        assert "deployability_status" in data

    def test_cli_prints_oneline_summary(self, tmp_path):
        """CLI stdout must include key metric fields."""
        input_csv = _make_enriched_csv(tmp_path)
        output_dir = tmp_path / "outputs" / "predictions" / "PAPER" / "test-run"
        output_dir.mkdir(parents=True)
        returncode, stdout, stderr = self._run_cli([
            "--input-csv", str(input_csv),
            "--output-dir", str(output_dir),
            "--min-train-size", "200",
            "--initial-train-months", "2",
        ])
        assert returncode == 0, f"CLI failed with stderr: {stderr}"
        assert "original_bss=" in stdout
        assert "oof_bss=" in stdout
        assert "recommendation=" in stdout
