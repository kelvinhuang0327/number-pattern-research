"""
Tests for run_p33_2024_prediction_odds_gap_builder CLI
"""

import json
import os
import sys
import tempfile

import pytest

# ---------------------------------------------------------------------------
# Ensure repo root is on path
# ---------------------------------------------------------------------------
_REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from scripts.run_p33_2024_prediction_odds_gap_builder import (
    _check_paper_only_guard,
    _determine_final_gate,
    _write_gate_result,
    _write_gap_summary_json,
    _write_gap_summary_md,
    _write_candidates_csv,
    _write_recommendations_json,
    main,
    DEFAULT_OUTPUT_DIR,
    P32_GATE_JSON,
    P32_OUTCOMES_CSV,
)
from wbc_backend.recommendation.p33_prediction_odds_gap_contract import (
    PAPER_ONLY,
    P33_BLOCKED_NO_VERIFIED_ODDS_SOURCE,
    P33_BLOCKED_NO_VERIFIED_PREDICTION_SOURCE,
    P33_PREDICTION_ODDS_GAP_PLAN_READY,
    P33GateResult,
    P33SourceGapSummary,
)
from wbc_backend.recommendation.p33_safe_source_recommendation_builder import (
    P33SourceRecommendationSet,
    build_recommendation_set,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_gap_summary(pred_missing: bool = True, odds_missing: bool = True) -> P33SourceGapSummary:
    return P33SourceGapSummary(
        prediction_missing=pred_missing,
        odds_missing=odds_missing,
        prediction_gap_reason="No prediction files." if pred_missing else "",
        odds_gap_reason="No odds files." if odds_missing else "",
    )


def _setup_repo_with_p32_gate(tmp_path, gate_value: str = "P32_RAW_GAME_LOG_ARTIFACT_READY") -> str:
    """Create a minimal repo structure with a valid P32 gate result."""
    processed_dir = tmp_path / "data" / "mlb_2024" / "processed"
    processed_dir.mkdir(parents=True)
    gate = {
        "gate": gate_value,
        "season": 2024,
        "paper_only": True,
        "production_ready": False,
    }
    (processed_dir / "p32_gate_result.json").write_text(
        json.dumps(gate), encoding="utf-8"
    )
    return str(tmp_path)


# ---------------------------------------------------------------------------
# Guard checks
# ---------------------------------------------------------------------------


class TestCheckPaperOnlyGuard:
    def test_paper_only_is_true(self):
        """Should not raise when PAPER_ONLY=True."""
        _check_paper_only_guard()  # No exception expected
        assert PAPER_ONLY is True


# ---------------------------------------------------------------------------
# _determine_final_gate
# ---------------------------------------------------------------------------


class TestDetermineFinalGate:
    def test_both_missing_returns_prediction_blocked(self):
        gap = _make_gap_summary(pred_missing=True, odds_missing=True)
        gate = _determine_final_gate(gap)
        assert gate.gate == P33_BLOCKED_NO_VERIFIED_PREDICTION_SOURCE
        assert gate.prediction_gap_blocked is True
        assert gate.odds_gap_blocked is True

    def test_only_pred_missing(self):
        gap = _make_gap_summary(pred_missing=True, odds_missing=False)
        gate = _determine_final_gate(gap)
        assert gate.gate == P33_BLOCKED_NO_VERIFIED_PREDICTION_SOURCE
        assert gate.prediction_gap_blocked is True
        assert gate.odds_gap_blocked is False

    def test_only_odds_missing(self):
        gap = _make_gap_summary(pred_missing=False, odds_missing=True)
        gate = _determine_final_gate(gap)
        assert gate.gate == P33_BLOCKED_NO_VERIFIED_ODDS_SOURCE
        assert gate.odds_gap_blocked is True
        assert gate.prediction_gap_blocked is False

    def test_both_ready_returns_plan_ready(self):
        gap = _make_gap_summary(pred_missing=False, odds_missing=False)
        gate = _determine_final_gate(gap)
        assert gate.gate == P33_PREDICTION_ODDS_GAP_PLAN_READY
        assert gate.prediction_gap_blocked is False
        assert gate.odds_gap_blocked is False

    def test_gate_result_paper_only(self):
        gap = _make_gap_summary()
        gate = _determine_final_gate(gap)
        assert gate.paper_only is True
        assert gate.production_ready is False

    def test_gate_result_next_phase(self):
        gap = _make_gap_summary()
        gate = _determine_final_gate(gap)
        assert gate.next_phase == "P34_DUAL_SOURCE_ACQUISITION_PLAN"

    def test_blocker_reason_populated_when_blocked(self):
        gap = _make_gap_summary(pred_missing=True, odds_missing=True)
        gate = _determine_final_gate(gap)
        assert len(gate.blocker_reason) > 0

    def test_blocker_reason_empty_when_ready(self):
        gap = _make_gap_summary(pred_missing=False, odds_missing=False)
        gate = _determine_final_gate(gap)
        assert gate.blocker_reason == ""


# ---------------------------------------------------------------------------
# _write_gate_result
# ---------------------------------------------------------------------------


class TestWriteGateResult:
    def test_creates_file(self, tmp_path):
        gate = P33GateResult(gate=P33_BLOCKED_NO_VERIFIED_PREDICTION_SOURCE)
        path = _write_gate_result(str(tmp_path), gate, ["a.csv"])
        assert os.path.isfile(path)

    def test_valid_json(self, tmp_path):
        gate = P33GateResult(gate=P33_BLOCKED_NO_VERIFIED_PREDICTION_SOURCE)
        path = _write_gate_result(str(tmp_path), gate, [])
        with open(path) as fh:
            data = json.load(fh)
        assert data["gate"] == P33_BLOCKED_NO_VERIFIED_PREDICTION_SOURCE
        assert data["paper_only"] is True
        assert data["production_ready"] is False

    def test_artifacts_written(self, tmp_path):
        gate = P33GateResult(gate=P33_PREDICTION_ODDS_GAP_PLAN_READY)
        artifacts = ["file1.csv", "file2.json"]
        path = _write_gate_result(str(tmp_path), gate, artifacts)
        with open(path) as fh:
            data = json.load(fh)
        assert data["artifacts"] == artifacts

    def test_next_phase_in_output(self, tmp_path):
        gate = P33GateResult(gate=P33_BLOCKED_NO_VERIFIED_PREDICTION_SOURCE)
        path = _write_gate_result(str(tmp_path), gate, [])
        with open(path) as fh:
            data = json.load(fh)
        assert data["next_phase"] == "P34_DUAL_SOURCE_ACQUISITION_PLAN"


# ---------------------------------------------------------------------------
# _write_gap_summary_json
# ---------------------------------------------------------------------------


class TestWriteGapSummaryJson:
    def test_creates_file(self, tmp_path):
        gap = _make_gap_summary()
        path = _write_gap_summary_json(str(tmp_path), gap)
        assert os.path.isfile(path)

    def test_valid_json(self, tmp_path):
        gap = _make_gap_summary()
        path = _write_gap_summary_json(str(tmp_path), gap)
        with open(path) as fh:
            data = json.load(fh)
        assert data["season"] == 2024
        assert data["paper_only"] is True
        assert data["prediction_missing"] is True
        assert data["odds_missing"] is True


# ---------------------------------------------------------------------------
# _write_gap_summary_md
# ---------------------------------------------------------------------------


class TestWriteGapSummaryMd:
    def test_creates_file(self, tmp_path):
        gap = _make_gap_summary()
        gate = _determine_final_gate(gap)
        path = _write_gap_summary_md(str(tmp_path), gap, gate)
        assert os.path.isfile(path)

    def test_contains_gate(self, tmp_path):
        gap = _make_gap_summary()
        gate = _determine_final_gate(gap)
        path = _write_gap_summary_md(str(tmp_path), gap, gate)
        content = open(path).read()
        assert gate.gate in content

    def test_contains_next_phase(self, tmp_path):
        gap = _make_gap_summary()
        gate = _determine_final_gate(gap)
        path = _write_gap_summary_md(str(tmp_path), gap, gate)
        content = open(path).read()
        assert "P34" in content


# ---------------------------------------------------------------------------
# _write_candidates_csv
# ---------------------------------------------------------------------------


class TestWriteCandidatesCsv:
    def test_creates_file_empty_list(self, tmp_path):
        path = _write_candidates_csv(str(tmp_path), [], "pred_candidates.csv")
        assert os.path.isfile(path)

    def test_header_in_empty_csv(self, tmp_path):
        path = _write_candidates_csv(str(tmp_path), [], "pred.csv")
        with open(path) as fh:
            content = fh.read()
        assert "candidate_id" in content

    def test_file_name_preserved(self, tmp_path):
        path = _write_candidates_csv(str(tmp_path), [], "my_candidates.csv")
        assert os.path.basename(path) == "my_candidates.csv"


# ---------------------------------------------------------------------------
# _write_recommendations_json
# ---------------------------------------------------------------------------


class TestWriteRecommendationsJson:
    def test_creates_file(self, tmp_path):
        gap = _make_gap_summary()
        rec_set = build_recommendation_set(gap)
        path = _write_recommendations_json(str(tmp_path), rec_set)
        assert os.path.isfile(path)

    def test_valid_json(self, tmp_path):
        gap = _make_gap_summary()
        rec_set = build_recommendation_set(gap)
        path = _write_recommendations_json(str(tmp_path), rec_set)
        with open(path) as fh:
            data = json.load(fh)
        assert data["paper_only"] is True
        assert "prediction_recommendations" in data
        assert "odds_recommendations" in data
        assert isinstance(data["prediction_recommendations"], list)
        assert isinstance(data["odds_recommendations"], list)


# ---------------------------------------------------------------------------
# main() integration tests
# ---------------------------------------------------------------------------


class TestMainIntegration:
    def test_exits_1_when_blocked(self, tmp_path):
        """Without any valid 2024 sources, should exit 1 (BLOCKED)."""
        repo_root = _setup_repo_with_p32_gate(tmp_path)
        out_dir = str(tmp_path / "p33_output")
        exit_code = main([
            "--repo-root", repo_root,
            "--output-dir", out_dir,
            "--skip-determinism-check",
        ])
        assert exit_code == 1

    def test_gate_result_written(self, tmp_path):
        """Gate result JSON must be written."""
        repo_root = _setup_repo_with_p32_gate(tmp_path)
        out_dir = str(tmp_path / "p33_output")
        main([
            "--repo-root", repo_root,
            "--output-dir", out_dir,
            "--skip-determinism-check",
        ])
        gate_path = os.path.join(out_dir, "p33_gate_result.json")
        assert os.path.isfile(gate_path)

    def test_gate_result_is_blocked(self, tmp_path):
        """With no 2024 data, gate must be a blocked value."""
        repo_root = _setup_repo_with_p32_gate(tmp_path)
        out_dir = str(tmp_path / "p33_output")
        main([
            "--repo-root", repo_root,
            "--output-dir", out_dir,
            "--skip-determinism-check",
        ])
        with open(os.path.join(out_dir, "p33_gate_result.json")) as fh:
            data = json.load(fh)
        assert data["gate"] in (
            P33_BLOCKED_NO_VERIFIED_PREDICTION_SOURCE,
            P33_BLOCKED_NO_VERIFIED_ODDS_SOURCE,
        )

    def test_source_gap_summary_written(self, tmp_path):
        repo_root = _setup_repo_with_p32_gate(tmp_path)
        out_dir = str(tmp_path / "p33_output")
        main([
            "--repo-root", repo_root,
            "--output-dir", out_dir,
            "--skip-determinism-check",
        ])
        assert os.path.isfile(os.path.join(out_dir, "p33_source_gap_summary.json"))

    def test_recommendations_written(self, tmp_path):
        repo_root = _setup_repo_with_p32_gate(tmp_path)
        out_dir = str(tmp_path / "p33_output")
        main([
            "--repo-root", repo_root,
            "--output-dir", out_dir,
            "--skip-determinism-check",
        ])
        recs_path = os.path.join(out_dir, "source_recommendations.json")
        assert os.path.isfile(recs_path)
        with open(recs_path) as fh:
            data = json.load(fh)
        assert len(data["prediction_recommendations"]) > 0
        assert len(data["odds_recommendations"]) > 0

    def test_fails_if_no_p32_gate(self, tmp_path):
        """Should exit 2 if P32 gate file is missing."""
        out_dir = str(tmp_path / "p33_output")
        with pytest.raises(SystemExit) as exc_info:
            main([
                "--repo-root", str(tmp_path),
                "--output-dir", out_dir,
                "--skip-determinism-check",
            ])
        assert exc_info.value.code == 2

    def test_fails_if_p32_gate_not_ready(self, tmp_path):
        """Should exit 2 if P32 gate is not READY."""
        repo_root = _setup_repo_with_p32_gate(tmp_path, gate_value="P32_BLOCKED_SOURCE_FILE_MISSING")
        out_dir = str(tmp_path / "p33_output")
        with pytest.raises(SystemExit) as exc_info:
            main([
                "--repo-root", repo_root,
                "--output-dir", out_dir,
                "--skip-determinism-check",
            ])
        assert exc_info.value.code == 2

    def test_gate_paper_only_in_output(self, tmp_path):
        repo_root = _setup_repo_with_p32_gate(tmp_path)
        out_dir = str(tmp_path / "p33_output")
        main([
            "--repo-root", repo_root,
            "--output-dir", out_dir,
            "--skip-determinism-check",
        ])
        with open(os.path.join(out_dir, "p33_gate_result.json")) as fh:
            data = json.load(fh)
        assert data["paper_only"] is True
        assert data["production_ready"] is False

    def test_skeleton_artifacts_written(self, tmp_path):
        repo_root = _setup_repo_with_p32_gate(tmp_path)
        out_dir = str(tmp_path / "p33_output")
        main([
            "--repo-root", repo_root,
            "--output-dir", out_dir,
            "--skip-determinism-check",
        ])
        # At least the schema CSV should be present
        assert os.path.isfile(os.path.join(out_dir, "mlb_2024_joined_input_schema.csv"))

    def test_default_output_dir_constant(self):
        assert "mlb_2024" in DEFAULT_OUTPUT_DIR
        assert "p33" in DEFAULT_OUTPUT_DIR
