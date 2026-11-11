"""
Tests for Phase 49: Feature Repair Evaluation
==============================================
Covers:
  - candidate_patch_created always False
  - production_modified always False
  - feature_effect_mode detection (REPORT_ONLY / MODEL_AFFECTING)
  - REPORT_ONLY → gate = FEATURE_INJECTION_REQUIRED (forced)
  - REPORT_ONLY → metric deltas must be zero
  - segment comparison schema completeness
  - feature availability summary correctness
  - leakage guard summary correctness
  - JSON and Markdown report generation
  - critical required segment keys present
"""
from __future__ import annotations

import json
import math
import tempfile
from pathlib import Path

import pytest

from orchestrator.phase49_feature_repair_evaluation import (
    CANDIDATE_PATCH_CREATED,
    PRODUCTION_MODIFIED,
    REPORT_ONLY,
    MODEL_AFFECTING,
    FEATURE_INJECTION_REQUIRED,
    FEATURE_READY_FOR_INJECTION,
    FEATURE_REPORT_ONLY_AVAIL,
    _REQUIRED_SEGMENT_KEYS,
    _compute_audit_hash,
    build_feature_availability_summary,
    build_leakage_guard_summary,
    build_segment_comparisons,
    detect_feature_effect_mode,
    run_phase49_evaluation,
)
from wbc_backend.evaluation.prediction_persistence import PredictionRow


# ─── Shared helpers ──────────────────────────────────────────────────────────

def _make_row(
    game_id: str = "G001",
    game_date: str = "2025-06-15",
    model_home_prob: float = 0.60,
    market_home_prob_no_vig: float = 0.55,
    home_win: int = 1,
    home_team: str = "New York Yankees",
) -> PredictionRow:
    return PredictionRow(
        schema_version="phase39-v1",
        season=2025,
        game_date=game_date,
        game_id=game_id,
        dedupe_key=game_id,
        home_team=home_team,
        away_team="Boston Red Sox",
        home_win=home_win,
        model_home_prob=model_home_prob,
        market_home_prob_no_vig=market_home_prob_no_vig,
        market_away_prob_no_vig=1.0 - market_home_prob_no_vig,
        home_ml=-150,
        away_ml=130,
    )


def _minimal_jsonl_row(
    game_id: str = "G001",
    game_date: str = "2025-06-15",
    model_home_prob: float = 0.60,
    home_win: int = 1,
    home_team: str = "Colorado Rockies",
    include_p0_features: bool = True,
    park_factor_available: bool = True,
    season_idx_available: bool = True,
    sp_fip_available: bool = False,
    forbidden_fields: list[str] | None = None,
) -> dict:
    row: dict = {
        "schema_version": "phase39-v1",
        "season": 2025,
        "game_date": game_date,
        "game_id": game_id,
        "dedupe_key": game_id,
        "home_team": home_team,
        "away_team": "Los Angeles Dodgers",
        "home_win": home_win,
        "model_home_prob": model_home_prob,
        "market_home_prob_no_vig": 0.55,
        "market_away_prob_no_vig": 0.45,
        "home_ml": "",
        "away_ml": "",
    }
    if include_p0_features:
        row["p0_features"] = {
            "feature_version": "phase48_p0_v1",
            "candidate_patch_created": False,
            "production_modified": False,
            "sp_fip_delta": 0.0,
            "sp_fip_delta_available": sp_fip_available,
            "park_run_factor": 1.15 if park_factor_available else 1.00,
            "park_factor_available": park_factor_available,
            "season_game_index": 0.25,
            "season_game_index_available": season_idx_available,
            "feature_audit_hash": "a" * 64,
            "audit_notes": {
                "ignored_forbidden_fields": forbidden_fields if forbidden_fields is not None else ["home_win"],
                "sp_fip_source": "neutral_fallback",
                "park_factor_source": "lookup_table",
                "season_index_source": "computed",
            },
        }
        row["feature_version"] = "phase48_p0_v1"
        row["feature_audit_hash"] = "a" * 64
    return row


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


def _make_baseline_rows(n: int = 50) -> list[dict]:
    """Minimal baseline JSONL rows (no p0_features)."""
    rows = []
    for i in range(n):
        rows.append({
            "schema_version": "phase39-v1",
            "season": 2025,
            "game_date": f"2025-06-{(i % 28) + 1:02d}",
            "game_id": f"G{i:04d}",
            "dedupe_key": f"G{i:04d}",
            "home_team": "New York Yankees",
            "away_team": "Boston Red Sox",
            "home_win": i % 2,
            "model_home_prob": 0.55 + (i % 10) * 0.01,
            "market_home_prob_no_vig": 0.52 + (i % 8) * 0.01,
            "market_away_prob_no_vig": 0.48 - (i % 8) * 0.01,
            "home_ml": "",
            "away_ml": "",
        })
    return rows


def _make_phase48_rows(baseline: list[dict], same_probs: bool = True) -> list[dict]:
    """Produce phase48 rows from baseline, optionally altering model_home_prob."""
    rows = []
    for i, b in enumerate(baseline):
        p = b["model_home_prob"]
        if not same_probs:
            p = min(0.99, p + 0.05)  # simulate model was affected
        r = {**b, "model_home_prob": p}
        r["p0_features"] = {
            "feature_version": "phase48_p0_v1",
            "candidate_patch_created": False,
            "production_modified": False,
            "sp_fip_delta": 0.0,
            "sp_fip_delta_available": False,
            "park_run_factor": 1.15,
            "park_factor_available": True,
            "season_game_index": 0.25,
            "season_game_index_available": True,
            "feature_audit_hash": "b" * 64,
            "audit_notes": {
                "ignored_forbidden_fields": ["home_win"],
                "sp_fip_source": "neutral_fallback",
                "park_factor_source": "lookup_table",
                "season_index_source": "computed",
            },
        }
        r["feature_version"] = "phase48_p0_v1"
        r["feature_audit_hash"] = "b" * 64
        rows.append(r)
    return rows


# ═══════════════════════════════════════════════════════════════════════════════
# § A  Hard-Rule Invariants
# ═══════════════════════════════════════════════════════════════════════════════

class TestHardRuleInvariants:
    def test_candidate_patch_created_is_false(self):
        assert CANDIDATE_PATCH_CREATED is False

    def test_production_modified_is_false(self):
        assert PRODUCTION_MODIFIED is False

    def test_result_candidate_patch_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            bp = Path(tmp) / "baseline.jsonl"
            pp = Path(tmp) / "phase48.jsonl"
            rows = _make_baseline_rows(50)
            _write_jsonl(bp, rows)
            _write_jsonl(pp, _make_phase48_rows(rows))
            result = run_phase49_evaluation(bp, pp)
            assert result.candidate_patch_created is False

    def test_result_production_modified_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            bp = Path(tmp) / "baseline.jsonl"
            pp = Path(tmp) / "phase48.jsonl"
            rows = _make_baseline_rows(50)
            _write_jsonl(bp, rows)
            _write_jsonl(pp, _make_phase48_rows(rows))
            result = run_phase49_evaluation(bp, pp)
            assert result.production_modified is False

    def test_to_dict_preserves_false_flags(self):
        with tempfile.TemporaryDirectory() as tmp:
            bp = Path(tmp) / "baseline.jsonl"
            pp = Path(tmp) / "phase48.jsonl"
            rows = _make_baseline_rows(50)
            _write_jsonl(bp, rows)
            _write_jsonl(pp, _make_phase48_rows(rows))
            result = run_phase49_evaluation(bp, pp)
            d = result.to_dict()
            assert d["candidate_patch_created"] is False
            assert d["production_modified"] is False

    def test_gate_never_patch(self):
        with tempfile.TemporaryDirectory() as tmp:
            bp = Path(tmp) / "baseline.jsonl"
            pp = Path(tmp) / "phase48.jsonl"
            rows = _make_baseline_rows(50)
            _write_jsonl(bp, rows)
            _write_jsonl(pp, _make_phase48_rows(rows))
            result = run_phase49_evaluation(bp, pp)
            assert result.gate_recommendation != "PATCH"


# ═══════════════════════════════════════════════════════════════════════════════
# § B  Feature Effect Mode Detection
# ═══════════════════════════════════════════════════════════════════════════════

class TestFeatureEffectMode:
    def _base_rows(self, n: int = 5) -> list[PredictionRow]:
        return [_make_row(game_id=f"G{i:04d}", model_home_prob=0.60) for i in range(n)]

    def test_identical_probs_is_report_only(self):
        baseline = self._base_rows()
        phase48  = self._base_rows()  # same probs
        mode, mismatch = detect_feature_effect_mode(baseline, phase48)
        assert mode == REPORT_ONLY
        assert mismatch == 0

    def test_different_probs_is_model_affecting(self):
        baseline = self._base_rows()
        phase48  = [_make_row(game_id=f"G{i:04d}", model_home_prob=0.65) for i in range(5)]
        mode, mismatch = detect_feature_effect_mode(baseline, phase48)
        assert mode == MODEL_AFFECTING
        assert mismatch == 5

    def test_partial_mismatch_is_model_affecting(self):
        baseline = [_make_row(game_id=f"G{i:04d}", model_home_prob=0.60) for i in range(4)]
        phase48  = [
            _make_row(game_id="G0000", model_home_prob=0.65),  # different
            _make_row(game_id="G0001", model_home_prob=0.60),  # same
            _make_row(game_id="G0002", model_home_prob=0.60),  # same
            _make_row(game_id="G0003", model_home_prob=0.60),  # same
        ]
        mode, mismatch = detect_feature_effect_mode(baseline, phase48)
        assert mode == MODEL_AFFECTING
        assert mismatch == 1

    def test_no_matching_ids_defaults_report_only(self):
        baseline = [_make_row(game_id="A001")]
        phase48  = [_make_row(game_id="B999")]
        mode, _ = detect_feature_effect_mode(baseline, phase48)
        assert mode == REPORT_ONLY

    def test_tolerance_below_threshold_is_report_only(self):
        baseline = [_make_row(game_id="G001", model_home_prob=0.60)]
        phase48  = [_make_row(game_id="G001", model_home_prob=0.60 + 1e-11)]  # within tolerance
        mode, mismatch = detect_feature_effect_mode(baseline, phase48)
        assert mode == REPORT_ONLY
        assert mismatch == 0


# ═══════════════════════════════════════════════════════════════════════════════
# § C  JSONL I/O — Baseline & Phase48 Readable
# ═══════════════════════════════════════════════════════════════════════════════

class TestJSONLLoading:
    def test_baseline_jsonl_readable(self):
        with tempfile.TemporaryDirectory() as tmp:
            bp = Path(tmp) / "b.jsonl"
            pp = Path(tmp) / "p.jsonl"
            rows = _make_baseline_rows(30)
            _write_jsonl(bp, rows)
            _write_jsonl(pp, _make_phase48_rows(rows))
            result = run_phase49_evaluation(bp, pp)
            assert result.baseline_metrics.n == 30

    def test_phase48_jsonl_readable(self):
        with tempfile.TemporaryDirectory() as tmp:
            bp = Path(tmp) / "b.jsonl"
            pp = Path(tmp) / "p.jsonl"
            rows = _make_baseline_rows(30)
            _write_jsonl(bp, rows)
            _write_jsonl(pp, _make_phase48_rows(rows))
            result = run_phase49_evaluation(bp, pp)
            assert result.phase48_metrics.n == 30

    def test_empty_ml_fields_tolerated(self):
        """home_ml='' and away_ml='' (real JSONL schema) must not raise."""
        with tempfile.TemporaryDirectory() as tmp:
            bp = Path(tmp) / "b.jsonl"
            pp = Path(tmp) / "p.jsonl"
            rows = _make_baseline_rows(30)
            # Baseline rows already have home_ml='' from _make_baseline_rows
            _write_jsonl(bp, rows)
            _write_jsonl(pp, _make_phase48_rows(rows))
            result = run_phase49_evaluation(bp, pp)
            assert result.baseline_metrics.n > 0

    def test_report_only_when_probs_identical(self):
        with tempfile.TemporaryDirectory() as tmp:
            bp = Path(tmp) / "b.jsonl"
            pp = Path(tmp) / "p.jsonl"
            rows = _make_baseline_rows(30)
            _write_jsonl(bp, rows)
            _write_jsonl(pp, _make_phase48_rows(rows, same_probs=True))
            result = run_phase49_evaluation(bp, pp)
            assert result.feature_effect_mode == REPORT_ONLY


# ═══════════════════════════════════════════════════════════════════════════════
# § D  REPORT_ONLY Gate Enforcement
# ═══════════════════════════════════════════════════════════════════════════════

class TestReportOnlyGate:
    def _run_report_only(self, n: int = 50) -> "Phase49EvaluationResult":
        with tempfile.TemporaryDirectory() as tmp:
            bp = Path(tmp) / "b.jsonl"
            pp = Path(tmp) / "p.jsonl"
            rows = _make_baseline_rows(n)
            _write_jsonl(bp, rows)
            _write_jsonl(pp, _make_phase48_rows(rows, same_probs=True))
            return run_phase49_evaluation(bp, pp)

    def test_report_only_forces_injection_required_gate(self):
        result = self._run_report_only()
        assert result.gate_recommendation == FEATURE_INJECTION_REQUIRED

    def test_report_only_delta_brier_is_zero(self):
        result = self._run_report_only()
        assert result.delta_metrics.delta_brier == 0.0

    def test_report_only_delta_bss_is_zero(self):
        result = self._run_report_only()
        assert result.delta_metrics.delta_bss == 0.0

    def test_report_only_delta_ece_is_zero(self):
        result = self._run_report_only()
        assert result.delta_metrics.delta_ece == 0.0

    def test_report_only_delta_log_loss_is_zero(self):
        result = self._run_report_only()
        assert result.delta_metrics.delta_log_loss == 0.0

    def test_report_only_gate_rationale_mentions_injection(self):
        result = self._run_report_only()
        assert "injection" in result.gate_rationale.lower() or "INJECTION" in result.gate_rationale


# ═══════════════════════════════════════════════════════════════════════════════
# § E  Segment Comparison Schema
# ═══════════════════════════════════════════════════════════════════════════════

class TestSegmentComparisonSchema:
    def _run(self) -> "Phase49EvaluationResult":
        with tempfile.TemporaryDirectory() as tmp:
            bp = Path(tmp) / "b.jsonl"
            pp = Path(tmp) / "p.jsonl"
            rows = _make_baseline_rows(60)
            _write_jsonl(bp, rows)
            _write_jsonl(pp, _make_phase48_rows(rows))
            return run_phase49_evaluation(bp, pp)

    def test_segment_comparisons_is_list(self):
        result = self._run()
        assert isinstance(result.segment_comparisons, list)

    def test_required_segments_all_present(self):
        result = self._run()
        keys = {s.segment_key for s in result.segment_comparisons}
        for k in _REQUIRED_SEGMENT_KEYS:
            assert k in keys, f"Required segment missing: {k}"

    def test_segment_has_correct_fields(self):
        result = self._run()
        s = result.segment_comparisons[0]
        assert hasattr(s, "segment_key")
        assert hasattr(s, "segment_type")
        assert hasattr(s, "segment_label")
        assert hasattr(s, "sample_size")
        assert hasattr(s, "baseline_bss")
        assert hasattr(s, "phase48_bss")
        assert hasattr(s, "delta_bss")
        assert hasattr(s, "baseline_ece")
        assert hasattr(s, "phase48_ece")
        assert hasattr(s, "delta_ece")
        assert hasattr(s, "improvement_label")

    def test_improvement_labels_valid(self):
        result = self._run()
        valid_labels = {"IMPROVED", "DEGRADED", "UNCHANGED", "NOT_EVALUABLE"}
        for s in result.segment_comparisons:
            assert s.improvement_label in valid_labels, f"{s.segment_key}: {s.improvement_label}"

    def test_report_only_all_segments_unchanged_or_not_evaluable(self):
        """When feature_effect_mode=REPORT_ONLY, delta_bss must be 0 for all evaluable segments."""
        result = self._run()
        assert result.feature_effect_mode == REPORT_ONLY
        for s in result.segment_comparisons:
            if s.improvement_label in ("IMPROVED", "DEGRADED"):
                # Should not happen in REPORT_ONLY
                pytest.fail(f"Unexpected label {s.improvement_label} for {s.segment_key} in REPORT_ONLY mode")

    def test_build_segment_comparisons_empty_inputs(self):
        comps = build_segment_comparisons({}, {})
        # Required segments must still be present (as NOT_EVALUABLE)
        keys = {s.segment_key for s in comps}
        for k in _REQUIRED_SEGMENT_KEYS:
            assert k in keys
        for s in comps:
            assert s.improvement_label == "NOT_EVALUABLE"


# ═══════════════════════════════════════════════════════════════════════════════
# § F  Feature Availability Summary
# ═══════════════════════════════════════════════════════════════════════════════

class TestFeatureAvailabilitySummary:
    def test_all_available_park_and_season(self):
        rows = [_minimal_jsonl_row(game_id=f"G{i}", park_factor_available=True, season_idx_available=True, sp_fip_available=False) for i in range(10)]
        fa = build_feature_availability_summary(rows)
        assert fa.park_availability_rate == 1.0
        assert fa.season_idx_availability_rate == 1.0
        assert fa.sp_fip_availability_rate == 0.0
        assert fa.neutral_fallback_rate == 1.0

    def test_feature_ready_label_when_park_season_full(self):
        rows = [_minimal_jsonl_row(game_id=f"G{i}", park_factor_available=True, season_idx_available=True) for i in range(10)]
        fa = build_feature_availability_summary(rows)
        assert fa.feature_availability_label == FEATURE_READY_FOR_INJECTION

    def test_report_only_label_when_sp_fip_zero(self):
        # park=1.0, season=1.0, sp_fip=0.0 → FEATURE_READY_FOR_INJECTION (park+season are the ones checked)
        # If park or season < 0.99:
        rows = [_minimal_jsonl_row(game_id=f"G{i}", park_factor_available=False, season_idx_available=True, sp_fip_available=False) for i in range(10)]
        fa = build_feature_availability_summary(rows)
        # park_rate = 0 → not FEATURE_READY → check label
        assert fa.feature_availability_label in (FEATURE_REPORT_ONLY_AVAIL, "FEATURE_DATA_GAP")

    def test_audit_hash_present_rate_correct(self):
        rows = [_minimal_jsonl_row(game_id=f"G{i}") for i in range(5)]
        # All rows have feature_audit_hash = "a"*64 → should be 100%
        fa = build_feature_availability_summary(rows)
        assert fa.feature_audit_hash_present_rate == 1.0

    def test_sp_fip_partial_availability(self):
        rows = (
            [_minimal_jsonl_row(game_id=f"G{i}", sp_fip_available=True) for i in range(3)]
            + [_minimal_jsonl_row(game_id=f"G{i+3}", sp_fip_available=False) for i in range(7)]
        )
        fa = build_feature_availability_summary(rows)
        assert abs(fa.sp_fip_availability_rate - 0.3) < 1e-5
        assert abs(fa.neutral_fallback_rate - 0.7) < 1e-5

    def test_empty_rows_does_not_raise(self):
        fa = build_feature_availability_summary([])
        assert fa.total_rows == 0
        assert fa.park_availability_rate == 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# § G  Leakage Guard Summary
# ═══════════════════════════════════════════════════════════════════════════════

class TestLeakageGuardSummary:
    def test_triggered_count_correct(self):
        rows = [_minimal_jsonl_row(game_id=f"G{i}", forbidden_fields=["home_win"]) for i in range(5)]
        lg = build_leakage_guard_summary(rows)
        assert lg.rows_with_forbidden_triggered == 5

    def test_most_common_forbidden_field(self):
        rows = [_minimal_jsonl_row(game_id=f"G{i}", forbidden_fields=["home_win"]) for i in range(10)]
        lg = build_leakage_guard_summary(rows)
        assert lg.most_common_forbidden_field == "home_win"

    def test_hash_stable_true_when_all_64_char(self):
        rows = [_minimal_jsonl_row(game_id=f"G{i}") for i in range(5)]
        lg = build_leakage_guard_summary(rows)
        assert lg.feature_hash_stable is True

    def test_hash_stable_false_when_short_hash(self):
        rows = [_minimal_jsonl_row(game_id="G0")]
        # Overwrite with short hash
        rows[0]["p0_features"]["feature_audit_hash"] = "abc"
        lg = build_leakage_guard_summary(rows)
        assert lg.feature_hash_stable is False

    def test_no_forbidden_trigger_rate_zero(self):
        rows = [_minimal_jsonl_row(game_id=f"G{i}", forbidden_fields=[]) for i in range(5)]
        lg = build_leakage_guard_summary(rows)
        assert lg.forbidden_trigger_rate == 0.0
        assert lg.rows_with_forbidden_triggered == 0

    def test_trigger_rate_correct(self):
        triggered = [_minimal_jsonl_row(game_id=f"G{i}", forbidden_fields=["home_win"]) for i in range(3)]
        not_triggered = [_minimal_jsonl_row(game_id=f"G{i+3}", forbidden_fields=[]) for i in range(7)]
        lg = build_leakage_guard_summary(triggered + not_triggered)
        assert abs(lg.forbidden_trigger_rate - 0.3) < 1e-5

    def test_empty_rows_does_not_raise(self):
        lg = build_leakage_guard_summary([])
        assert lg.total_rows == 0
        assert lg.forbidden_trigger_rate == 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# § H  JSON Report Generation
# ═══════════════════════════════════════════════════════════════════════════════

class TestJSONReportGeneration:
    def test_json_report_written(self):
        from scripts.run_phase49_feature_repair_evaluation import write_json_report
        import unittest.mock as mock

        with tempfile.TemporaryDirectory() as tmp:
            bp = Path(tmp) / "b.jsonl"
            pp = Path(tmp) / "p.jsonl"
            rows = _make_baseline_rows(30)
            _write_jsonl(bp, rows)
            _write_jsonl(pp, _make_phase48_rows(rows))
            result = run_phase49_evaluation(bp, pp)

            # Patch output dir to tmp
            with mock.patch("scripts.run_phase49_feature_repair_evaluation._REPORTS_DIR", Path(tmp)):
                out = write_json_report(result)
                assert out.exists()

    def test_json_report_valid_json(self):
        from scripts.run_phase49_feature_repair_evaluation import write_json_report
        import unittest.mock as mock

        with tempfile.TemporaryDirectory() as tmp:
            bp = Path(tmp) / "b.jsonl"
            pp = Path(tmp) / "p.jsonl"
            rows = _make_baseline_rows(30)
            _write_jsonl(bp, rows)
            _write_jsonl(pp, _make_phase48_rows(rows))
            result = run_phase49_evaluation(bp, pp)

            with mock.patch("scripts.run_phase49_feature_repair_evaluation._REPORTS_DIR", Path(tmp)):
                out = write_json_report(result)
                data = json.loads(out.read_text())
                assert data["candidate_patch_created"] is False
                assert data["production_modified"] is False
                assert "gate_recommendation" in data

    def test_json_report_feature_effect_mode_present(self):
        from scripts.run_phase49_feature_repair_evaluation import write_json_report
        import unittest.mock as mock

        with tempfile.TemporaryDirectory() as tmp:
            bp = Path(tmp) / "b.jsonl"
            pp = Path(tmp) / "p.jsonl"
            rows = _make_baseline_rows(30)
            _write_jsonl(bp, rows)
            _write_jsonl(pp, _make_phase48_rows(rows))
            result = run_phase49_evaluation(bp, pp)

            with mock.patch("scripts.run_phase49_feature_repair_evaluation._REPORTS_DIR", Path(tmp)):
                out = write_json_report(result)
                data = json.loads(out.read_text())
                assert "feature_effect_mode" in data


# ═══════════════════════════════════════════════════════════════════════════════
# § I  Markdown Report Generation
# ═══════════════════════════════════════════════════════════════════════════════

class TestMarkdownReportGeneration:
    def test_markdown_report_written(self):
        from scripts.run_phase49_feature_repair_evaluation import write_markdown_report
        import unittest.mock as mock

        with tempfile.TemporaryDirectory() as tmp:
            bp = Path(tmp) / "b.jsonl"
            pp = Path(tmp) / "p.jsonl"
            rows = _make_baseline_rows(30)
            _write_jsonl(bp, rows)
            _write_jsonl(pp, _make_phase48_rows(rows))
            result = run_phase49_evaluation(bp, pp)

            with mock.patch("scripts.run_phase49_feature_repair_evaluation._DOCS_DIR", Path(tmp)):
                out = write_markdown_report(result)
                assert out.exists()

    def test_markdown_contains_feature_effect_mode(self):
        from scripts.run_phase49_feature_repair_evaluation import write_markdown_report
        import unittest.mock as mock

        with tempfile.TemporaryDirectory() as tmp:
            bp = Path(tmp) / "b.jsonl"
            pp = Path(tmp) / "p.jsonl"
            rows = _make_baseline_rows(30)
            _write_jsonl(bp, rows)
            _write_jsonl(pp, _make_phase48_rows(rows))
            result = run_phase49_evaluation(bp, pp)

            with mock.patch("scripts.run_phase49_feature_repair_evaluation._DOCS_DIR", Path(tmp)):
                out = write_markdown_report(result)
                content = out.read_text()
                assert "REPORT_ONLY" in content

    def test_markdown_contains_report_only_notice(self):
        from scripts.run_phase49_feature_repair_evaluation import write_markdown_report
        import unittest.mock as mock

        with tempfile.TemporaryDirectory() as tmp:
            bp = Path(tmp) / "b.jsonl"
            pp = Path(tmp) / "p.jsonl"
            rows = _make_baseline_rows(30)
            _write_jsonl(bp, rows)
            _write_jsonl(pp, _make_phase48_rows(rows))
            result = run_phase49_evaluation(bp, pp)

            with mock.patch("scripts.run_phase49_feature_repair_evaluation._DOCS_DIR", Path(tmp)):
                out = write_markdown_report(result)
                content = out.read_text()
                # Must include the required REPORT_ONLY notice text
                assert "not yet injected" in content.lower() or "Phase 50" in content

    def test_markdown_contains_verification_marker(self):
        from scripts.run_phase49_feature_repair_evaluation import write_markdown_report
        import unittest.mock as mock

        with tempfile.TemporaryDirectory() as tmp:
            bp = Path(tmp) / "b.jsonl"
            pp = Path(tmp) / "p.jsonl"
            rows = _make_baseline_rows(30)
            _write_jsonl(bp, rows)
            _write_jsonl(pp, _make_phase48_rows(rows))
            result = run_phase49_evaluation(bp, pp)

            with mock.patch("scripts.run_phase49_feature_repair_evaluation._DOCS_DIR", Path(tmp)):
                out = write_markdown_report(result)
                content = out.read_text()
                assert "PHASE_49_FEATURE_REPAIR_EVALUATION_VERIFIED" in content


# ═══════════════════════════════════════════════════════════════════════════════
# § J  Audit Hash
# ═══════════════════════════════════════════════════════════════════════════════

class TestAuditHash:
    def test_result_has_audit_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            bp = Path(tmp) / "b.jsonl"
            pp = Path(tmp) / "p.jsonl"
            rows = _make_baseline_rows(30)
            _write_jsonl(bp, rows)
            _write_jsonl(pp, _make_phase48_rows(rows))
            result = run_phase49_evaluation(bp, pp)
            assert len(result.audit_hash) == 64

    def test_compute_audit_hash_direct(self):
        h = _compute_audit_hash("REPORT_ONLY", "FEATURE_INJECTION_REQUIRED", 2025, 2025, "test-run-id")
        assert len(h) == 64
        int(h, 16)  # must be valid hex

    def test_hash_differs_for_different_mode(self):
        h1 = _compute_audit_hash("REPORT_ONLY", "FEATURE_INJECTION_REQUIRED", 2025, 2025, "run1")
        h2 = _compute_audit_hash("MODEL_AFFECTING", "FEATURE_REPAIR_NOT_EFFECTIVE", 2025, 2025, "run1")
        assert h1 != h2

    def test_hash_stable_across_calls(self):
        h1 = _compute_audit_hash("REPORT_ONLY", "FEATURE_INJECTION_REQUIRED", 100, 100, "abc")
        h2 = _compute_audit_hash("REPORT_ONLY", "FEATURE_INJECTION_REQUIRED", 100, 100, "abc")
        assert h1 == h2
