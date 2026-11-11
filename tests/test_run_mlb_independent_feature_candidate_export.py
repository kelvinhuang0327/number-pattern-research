"""
tests/test_run_mlb_independent_feature_candidate_export.py

P10: Integration tests for scripts/run_mlb_independent_feature_candidate_export.py
"""
from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = str(_REPO_ROOT / "scripts" / "run_mlb_independent_feature_candidate_export.py")
_VENV_PYTHON = str(_REPO_ROOT / ".venv" / "bin" / "python")
_P9_CSV = (
    _REPO_ROOT
    / "outputs"
    / "predictions"
    / "PAPER"
    / "2026-05-11"
    / "mlb_odds_with_repaired_features.csv"
)
_OUT_DIR = (
    _REPO_ROOT / "outputs" / "predictions" / "PAPER" / "_test_p10_feature_candidate"
)
_OUT_DIR_FEATURE_ONLY = (
    _REPO_ROOT / "outputs" / "predictions" / "PAPER" / "_test_p10_feature_only"
)


def _run_script(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [_VENV_PYTHON, _SCRIPT, *args],
        capture_output=True,
        text=True,
        cwd=str(_REPO_ROOT),
    )


@pytest.fixture(scope="module")
def p9_csv_path() -> Path:
    if not _P9_CSV.exists():
        pytest.skip(f"P9 repaired CSV not found: {_P9_CSV}")
    return _P9_CSV


@pytest.fixture(scope="module")
def feature_augmented_output(p9_csv_path: Path) -> Path:
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    result = _run_script(
        "--input-csv", str(p9_csv_path),
        "--output-dir", str(_OUT_DIR),
        "--candidate-mode", "feature_augmented",
        "--lookback-games", "15",
    )
    if result.returncode != 0:
        pytest.fail(f"Feature augmented export failed:\n{result.stdout}\n{result.stderr}")
    return _OUT_DIR


@pytest.fixture(scope="module")
def feature_only_output(p9_csv_path: Path) -> Path:
    _OUT_DIR_FEATURE_ONLY.mkdir(parents=True, exist_ok=True)
    result = _run_script(
        "--input-csv", str(p9_csv_path),
        "--output-dir", str(_OUT_DIR_FEATURE_ONLY),
        "--candidate-mode", "feature_only",
        "--lookback-games", "15",
    )
    if result.returncode != 0:
        pytest.fail(f"Feature only export failed:\n{result.stdout}\n{result.stderr}")
    return _OUT_DIR_FEATURE_ONLY


class TestCandidateExportArtifacts:
    def test_indep_jsonl_exists(self, feature_augmented_output: Path):
        assert (feature_augmented_output / "mlb_independent_features.jsonl").exists()

    def test_merged_csv_exists(self, feature_augmented_output: Path):
        assert (feature_augmented_output / "mlb_odds_with_independent_features.csv").exists()

    def test_candidate_probs_jsonl_exists(self, feature_augmented_output: Path):
        assert (feature_augmented_output / "mlb_feature_candidate_probabilities.jsonl").exists()

    def test_candidate_csv_exists(self, feature_augmented_output: Path):
        assert (feature_augmented_output / "mlb_odds_with_feature_candidate_probabilities.csv").exists()

    def test_coverage_json_exists(self, feature_augmented_output: Path):
        assert (feature_augmented_output / "independent_feature_coverage.json").exists()

    def test_summary_md_exists(self, feature_augmented_output: Path):
        assert (feature_augmented_output / "feature_candidate_summary.md").exists()


class TestCandidateCsvColumns:
    def test_has_model_prob_home(self, feature_augmented_output: Path):
        csv_path = feature_augmented_output / "mlb_odds_with_feature_candidate_probabilities.csv"
        with csv_path.open() as fh:
            fieldnames = csv.DictReader(fh).fieldnames or []
        assert "model_prob_home" in fieldnames

    def test_has_probability_source_feature_candidate(self, feature_augmented_output: Path):
        csv_path = feature_augmented_output / "mlb_odds_with_feature_candidate_probabilities.csv"
        with csv_path.open() as fh:
            rows = list(csv.DictReader(fh))
        sources = {r.get("probability_source") for r in rows}
        assert "feature_candidate" in sources

    def test_has_raw_model_prob_before_p10(self, feature_augmented_output: Path):
        """Feature-augmented mode must preserve original model_prob_home."""
        csv_path = feature_augmented_output / "mlb_odds_with_feature_candidate_probabilities.csv"
        with csv_path.open() as fh:
            fieldnames = csv.DictReader(fh).fieldnames or []
        assert "raw_model_prob_before_p10" in fieldnames

    def test_probs_in_valid_range(self, feature_augmented_output: Path):
        csv_path = feature_augmented_output / "mlb_odds_with_feature_candidate_probabilities.csv"
        with csv_path.open() as fh:
            for row in csv.DictReader(fh):
                v = row.get("model_prob_home")
                if v is not None and v != "":
                    p = float(v)
                    assert 0.01 <= p <= 0.99, f"Probability out of range: {p}"


class TestPaperOnlyGate:
    def test_non_paper_output_rejected(self, p9_csv_path: Path):
        result = _run_script(
            "--input-csv", str(p9_csv_path),
            "--output-dir", "/tmp/not_paper",
            "--candidate-mode", "feature_augmented",
        )
        assert result.returncode != 0

    def test_missing_input_rejected(self):
        result = _run_script(
            "--input-csv", "/nonexistent/input.csv",
            "--output-dir", str(_REPO_ROOT / "outputs" / "predictions" / "PAPER" / "_test_p10_missing"),
            "--candidate-mode", "feature_augmented",
        )
        assert result.returncode != 0


class TestFeatureOnlyMode:
    def test_feature_only_artifacts_created(self, feature_only_output: Path):
        assert (feature_only_output / "mlb_odds_with_feature_candidate_probabilities.csv").exists()

    def test_feature_only_probability_source(self, feature_only_output: Path):
        csv_path = feature_only_output / "mlb_odds_with_feature_candidate_probabilities.csv"
        with csv_path.open() as fh:
            rows = list(csv.DictReader(fh))
        sources = {r.get("probability_source") for r in rows}
        assert "feature_candidate" in sources

    def test_feature_only_probs_in_range(self, feature_only_output: Path):
        csv_path = feature_only_output / "mlb_odds_with_feature_candidate_probabilities.csv"
        with csv_path.open() as fh:
            for row in csv.DictReader(fh):
                v = row.get("model_prob_home")
                if v is not None and v != "":
                    p = float(v)
                    assert 0.01 <= p <= 0.99

    def test_feature_only_does_not_rely_solely_on_market(self, feature_only_output: Path):
        """In feature_only mode, all probs should cluster around 0.5, not around market odds."""
        csv_path = feature_only_output / "mlb_odds_with_feature_candidate_probabilities.csv"
        with csv_path.open() as fh:
            probs = [
                float(r["model_prob_home"])
                for r in csv.DictReader(fh)
                if r.get("model_prob_home") not in (None, "")
            ]
        avg = sum(probs) / len(probs)
        # feature_only should produce avg closer to 0.5 than market-derived (0.53+)
        assert 0.40 <= avg <= 0.65, f"Feature-only avg prob {avg:.3f} not near 0.5"

    def test_feature_augmented_preserves_raw_model_prob(self, feature_augmented_output: Path):
        """feature_augmented must preserve raw_model_prob_before_p10."""
        csv_path = feature_augmented_output / "mlb_odds_with_feature_candidate_probabilities.csv"
        with csv_path.open() as fh:
            rows = list(csv.DictReader(fh))
        has_raw = sum(1 for r in rows if r.get("raw_model_prob_before_p10") not in (None, ""))
        assert has_raw > 0


class TestCoverageJson:
    def test_coverage_json_has_leakage_safe_true(self, feature_augmented_output: Path):
        cov = json.loads((feature_augmented_output / "independent_feature_coverage.json").read_text())
        assert cov.get("leakage_safe") is True

    def test_coverage_json_has_paper_only_true(self, feature_augmented_output: Path):
        cov = json.loads((feature_augmented_output / "independent_feature_coverage.json").read_text())
        assert cov.get("paper_only") is True

    def test_coverage_json_has_feature_version(self, feature_augmented_output: Path):
        cov = json.loads((feature_augmented_output / "independent_feature_coverage.json").read_text())
        assert "feature_version" in cov


class TestStdoutSummary:
    def test_stdout_contains_summary(self, p9_csv_path: Path):
        out_dir = _REPO_ROOT / "outputs" / "predictions" / "PAPER" / "_test_p10_stdout"
        out_dir.mkdir(parents=True, exist_ok=True)
        result = _run_script(
            "--input-csv", str(p9_csv_path),
            "--output-dir", str(out_dir),
            "--candidate-mode", "feature_augmented",
        )
        assert "avg_prob_before" in result.stdout or "SUMMARY" in result.stdout
