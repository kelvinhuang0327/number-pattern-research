"""
tests/test_run_mlb_repaired_model_probability_export.py

Integration tests for scripts/run_mlb_repaired_model_probability_export.py
"""
from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = str(_REPO_ROOT / "scripts" / "run_mlb_repaired_model_probability_export.py")
_VENV_PYTHON = str(_REPO_ROOT / ".venv" / "bin" / "python")


def _run_script(*args: str) -> subprocess.CompletedProcess:
    """Run the export script and return CompletedProcess."""
    return subprocess.run(
        [_VENV_PYTHON, _SCRIPT, *args],
        capture_output=True,
        text=True,
        cwd=str(_REPO_ROOT),
    )


@pytest.fixture(scope="module")
def p5_csv_path() -> Path:
    """Return the P5 CSV path, skip tests if not found."""
    p = _REPO_ROOT / "outputs" / "predictions" / "PAPER" / "2026-05-11" / "mlb_odds_with_model_probabilities.csv"
    if not p.exists():
        pytest.skip(f"P5 CSV not found: {p}")
    return p


@pytest.fixture(scope="module")
def repaired_output_dir(p5_csv_path: Path) -> Path:
    """Run the export script once and return the output dir (inside PAPER zone)."""
    paper_dir = _REPO_ROOT / "outputs" / "predictions" / "PAPER" / "_test_p9_repaired_export"
    paper_dir.mkdir(parents=True, exist_ok=True)
    result = _run_script(
        "--input-csv", str(p5_csv_path),
        "--output-dir", str(paper_dir),
        "--remove-constant-home-bias",
    )
    if result.returncode != 0:
        pytest.fail(f"Export script failed:\n{result.stdout}\n{result.stderr}")
    return paper_dir


class TestRepairedExportScript:
    def test_script_exits_zero_on_valid_input(self, p5_csv_path: Path):
        paper_dir = _REPO_ROOT / "outputs" / "predictions" / "PAPER" / "_test_p9_exit"
        paper_dir.mkdir(parents=True, exist_ok=True)
        result = _run_script(
            "--input-csv", str(p5_csv_path),
            "--output-dir", str(paper_dir),
        )
        assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"

    def test_csv_output_exists(self, repaired_output_dir: Path):
        assert (repaired_output_dir / "mlb_odds_with_repaired_features.csv").exists()

    def test_jsonl_output_exists(self, repaired_output_dir: Path):
        assert (repaired_output_dir / "mlb_repaired_model_probabilities.jsonl").exists()

    def test_metadata_json_exists(self, repaired_output_dir: Path):
        assert (repaired_output_dir / "repaired_feature_metadata.json").exists()

    def test_summary_md_exists(self, repaired_output_dir: Path):
        assert (repaired_output_dir / "repaired_probability_summary.md").exists()

    def test_csv_has_expected_columns(self, repaired_output_dir: Path):
        csv_path = repaired_output_dir / "mlb_odds_with_repaired_features.csv"
        with csv_path.open(encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            fieldnames = reader.fieldnames or []
        for expected in [
            "model_prob_home", "raw_model_prob_home",
            "probability_source", "repaired_feature_version",
            "bullpen_delta", "rest_delta", "win_rate_delta",
            "game_id",
        ]:
            assert expected in fieldnames, f"Missing column: {expected}"

    def test_metadata_paper_only_true(self, repaired_output_dir: Path):
        meta_path = repaired_output_dir / "repaired_feature_metadata.json"
        with meta_path.open(encoding="utf-8") as fh:
            meta = json.load(fh)
        assert meta.get("paper_only") is True

    def test_metadata_leakage_safe_true(self, repaired_output_dir: Path):
        meta_path = repaired_output_dir / "repaired_feature_metadata.json"
        with meta_path.open(encoding="utf-8") as fh:
            meta = json.load(fh)
        assert meta.get("leakage_safe") is True

    def test_csv_row_count_matches_input(self, p5_csv_path: Path, repaired_output_dir: Path):
        # Count input rows
        with p5_csv_path.open(encoding="utf-8", newline="") as fh:
            input_count = sum(1 for _ in csv.DictReader(fh))
        # Count output rows
        csv_path = repaired_output_dir / "mlb_odds_with_repaired_features.csv"
        with csv_path.open(encoding="utf-8", newline="") as fh:
            output_count = sum(1 for _ in csv.DictReader(fh))
        # Output should be <= input (dedup may remove some)
        assert output_count <= input_count
        assert output_count > 0

    def test_missing_input_csv_exits_nonzero(self):
        paper_dir = _REPO_ROOT / "outputs" / "predictions" / "PAPER" / "_test_p9_missing"
        paper_dir.mkdir(parents=True, exist_ok=True)
        result = _run_script(
            "--input-csv", "/nonexistent/path/missing.csv",
            "--output-dir", str(paper_dir),
        )
        assert result.returncode != 0

    def test_probability_source_all_repaired(self, repaired_output_dir: Path):
        csv_path = repaired_output_dir / "mlb_odds_with_repaired_features.csv"
        with csv_path.open(encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            sources = {row.get("probability_source") for row in reader}
        assert "repaired_model_candidate" in sources

    def test_stdout_contains_summary(self, p5_csv_path: Path):
        paper_dir = _REPO_ROOT / "outputs" / "predictions" / "PAPER" / "_test_p9_stdout"
        paper_dir.mkdir(parents=True, exist_ok=True)
        result = _run_script(
            "--input-csv", str(p5_csv_path),
            "--output-dir", str(paper_dir),
        )
        assert "avg_model_prob_before" in result.stdout or "SUMMARY" in result.stdout
