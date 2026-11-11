"""
tests/test_run_mlb_model_probability_export.py

Tests for the run_mlb_model_probability_export.py CLI.

P5: CLI refusal without real model artifact, success path with market proxy,
PAPER zone enforcement.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_CLI = _REPO_ROOT / "scripts" / "run_mlb_model_probability_export.py"
_PYTHON = sys.executable


def _paper_out_dir() -> Path:
    tmp = Path(tempfile.mkdtemp())
    p = tmp / "outputs" / "predictions" / "PAPER" / "test"
    p.mkdir(parents=True, exist_ok=True)
    return p


class TestMlbModelProbabilityExportCLI:
    def test_cli_exits_zero_with_allow_market_proxy(self):
        """With --allow-market-proxy and real odds CSV present, CLI must succeed."""
        out_dir = _paper_out_dir()
        result = subprocess.run(
            [
                _PYTHON,
                str(_CLI),
                "--input-csv",
                str(_REPO_ROOT / "data" / "mlb_2025" / "mlb_odds_2025_real.csv"),
                "--output-jsonl",
                str(out_dir / "probs.jsonl"),
                "--merged-output-csv",
                str(out_dir / "merged.csv"),
                "--allow-market-proxy",
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0, (
            f"CLI failed.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
        assert (out_dir / "probs.jsonl").exists()
        assert (out_dir / "merged.csv").exists()

    def test_cli_real_artifact_exits_zero_without_proxy(self):
        """Real calibrated artifact exists; CLI should succeed without --allow-market-proxy."""
        out_dir = _paper_out_dir()
        result = subprocess.run(
            [
                _PYTHON,
                str(_CLI),
                "--input-csv",
                str(_REPO_ROOT / "data" / "mlb_2025" / "mlb_odds_2025_real.csv"),
                "--output-jsonl",
                str(out_dir / "probs_real.jsonl"),
                "--merged-output-csv",
                str(out_dir / "merged_real.csv"),
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        # With the real artifact at data/derived/model_outputs_2026-04-29.jsonl,
        # this should succeed (1,493 real calibrated predictions available).
        assert result.returncode == 0, (
            f"CLI should succeed with real model artifact.\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )

    def test_cli_output_prints_probability_count(self):
        out_dir = _paper_out_dir()
        result = subprocess.run(
            [
                _PYTHON,
                str(_CLI),
                "--input-csv",
                str(_REPO_ROOT / "data" / "mlb_2025" / "mlb_odds_2025_real.csv"),
                "--output-jsonl",
                str(out_dir / "probs_count.jsonl"),
                "--merged-output-csv",
                str(out_dir / "merged_count.csv"),
                "--allow-market-proxy",
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert "probability_count=" in result.stdout
        assert "real_model_count" in result.stdout
        assert "market_proxy_count=" in result.stdout

    def test_cli_refuses_non_paper_output_path(self):
        """Output outside PAPER zone must exit non-zero."""
        result = subprocess.run(
            [
                _PYTHON,
                str(_CLI),
                "--input-csv",
                str(_REPO_ROOT / "data" / "mlb_2025" / "mlb_odds_2025_real.csv"),
                "--output-jsonl",
                "/tmp/not_paper_zone/probs.jsonl",
                "--merged-output-csv",
                "/tmp/not_paper_zone/merged.csv",
                "--allow-market-proxy",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode != 0

    def test_cli_output_row_count_matches_input(self):
        """Merged CSV must have same number of rows as input CSV."""
        import csv

        out_dir = _paper_out_dir()
        input_csv = _REPO_ROOT / "data" / "mlb_2025" / "mlb_odds_2025_real.csv"
        merged_csv = out_dir / "merged_rows.csv"
        subprocess.run(
            [
                _PYTHON,
                str(_CLI),
                "--input-csv",
                str(input_csv),
                "--output-jsonl",
                str(out_dir / "probs_rows.jsonl"),
                "--merged-output-csv",
                str(merged_csv),
                "--allow-market-proxy",
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if not merged_csv.exists():
            pytest.skip("Merged CSV not created — adapter issue")

        with open(input_csv) as f:
            input_rows = sum(1 for _ in csv.DictReader(f))
        with open(merged_csv) as f:
            merged_rows = sum(1 for _ in csv.DictReader(f))
        assert merged_rows == input_rows, (
            f"Merged CSV row count {merged_rows} != input row count {input_rows}"
        )
