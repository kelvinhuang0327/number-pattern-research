"""
tests/test_phase55_sp_vs_bullpen_diagnosis.py
=============================================
Phase 55 — SP Functional Form Redesign vs Bullpen Feature Investigation Tests

覆蓋：
  T-001  Hard rule constants
  T-002  Functional form implementations (6 forms)
  T-003  Segment helpers
  T-004  Metrics helpers (BSS / ECE)
  T-005  Form evaluation (FunctionalFormResult)
  T-006  Bullpen missing-feature diagnosis
  T-007  Decision framework (3 conclusions)
  T-008  Phase55DiagnosisResult hard rules + post_init
  T-009  JSON serialization
  T-010  Markdown report (all required sections)
  T-011  Integration smoke test (requires real JSONL)
"""
from __future__ import annotations

import json
import math
import tempfile
from dataclasses import asdict
from pathlib import Path

import pytest

from orchestrator.phase55_sp_vs_bullpen_diagnosis import (
    # Constants
    CANDIDATE_PATCH_CREATED,
    PRODUCTION_MODIFIED,
    DIAGNOSTIC_ONLY,
    PHASE55_VERSION,
    SP_FUNCTIONAL_FORM_REDESIGN,
    BULLPEN_FEATURE_INVESTIGATION,
    COLLECT_MORE_DATA,
    _VALID_CONCLUSIONS,
    FORM_TANH_CURRENT,
    FORM_TANH_STRONGER,
    FORM_LINEAR_CAPPED,
    FORM_SIGN_ONLY,
    FORM_BUCKETED_DELTA,
    FORM_SHRINK_TO_MARKET,
    ALL_FORM_NAMES,
    RECOMMENDED_BULLPEN_FEATURES,
    _PHASE54_FAILURE_COUNT,
    _BULLPEN_SCORE_THRESHOLD,
    # Dataclasses
    SegmentMetrics55,
    FunctionalFormResult,
    BullpenDiagnosis,
    Phase55DiagnosisResult,
    # Functions
    _apply_tanh_current,
    _apply_tanh_stronger,
    _apply_linear_capped,
    _apply_sign_only,
    _apply_bucketed_delta,
    _apply_shrink_to_market,
    _FORM_FNS,
    _odds_bucket,
    _confidence_bucket,
    _disagree_bucket,
    _month_key,
    _compute_segment_metrics,
    _is_failure,
    _evaluate_form,
    _score_bullpen_missing,
    _decide_conclusion,
    _load_raw_rows,
    run_phase55_diagnosis,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

_REAL_CONTEXT = (
    Path(__file__).resolve().parent.parent
    / "data/mlb_2025/derived/mlb_2025_per_game_predictions_phase52_sp_context_v1.jsonl"
)
_REAL_PHASE54_REPORT = (
    Path(__file__).resolve().parent.parent
    / "reports/phase54_safe_sp_stability_audit_2026-05-05.json"
)
_REAL_FILES_EXIST = _REAL_CONTEXT.exists()


def _make_row(
    idx: int = 0,
    model_home_prob: float = 0.55,
    home_win: int = 1,
    market_home_prob: float = 0.58,
    game_date: str = "2025-06-15",
    sp_fip_delta: float = 1.5,
    sp_fip_available: bool = True,
) -> dict:
    """Synthetic context row with p0_features."""
    return {
        "schema_version": "phase39-v1",
        "season": 2025,
        "game_date": game_date,
        "game_id": f"MLB2025_{idx:04d}",
        "dedupe_key": f"{game_date}|T1|T2|{idx}",
        "home_team": "TeamB",
        "away_team": "TeamA",
        "home_win": home_win,
        "model_home_prob": model_home_prob,
        "market_home_prob_no_vig": market_home_prob,
        "market_away_prob_no_vig": round(1.0 - market_home_prob, 6),
        "home_ml": "-110",
        "away_ml": "+100",
        "model_version": "xgb_v1",
        "feature_version": "v1",
        "source_backtest": True,
        "audit_hash": f"abc{idx:04d}",
        "p0_features": {
            "sp_fip_delta": sp_fip_delta,
            "sp_fip_delta_available": sp_fip_available,
            "park_factor_available": False,
            "park_run_factor": 1.0,
            "season_game_index_available": False,
            "season_game_index": 0.5,
        },
    }


def _make_synthetic_rows(n: int = 200) -> list[dict]:
    """Diverse synthetic rows for form evaluation."""
    rows = []
    months = ["2025-04", "2025-05", "2025-06", "2025-07"]
    for i in range(n):
        month = months[i % 4]
        day = (i % 28) + 1
        gd = f"{month}-{day:02d}"
        model_p = 0.42 + (i % 40) * 0.004
        if i % 6 == 0:
            mkt_p = 0.68 + (i % 8) * 0.01   # heavy_favorite
        elif i % 6 == 1:
            mkt_p = 0.32 - (i % 5) * 0.01   # underdog
        else:
            mkt_p = 0.50 + (i % 12) * 0.01
        mkt_p = min(0.99, max(0.01, mkt_p))
        if i % 5 == 0:
            model_p = 0.72 + (i % 10) * 0.01   # high confidence
        model_p = min(0.99, max(0.01, model_p))
        fip_delta = -2.5 + (i % 50) * 0.1
        hw = 1 if i % 2 == 0 else 0
        rows.append(_make_row(
            idx=i, model_home_prob=model_p, home_win=hw,
            market_home_prob=mkt_p, game_date=gd,
            sp_fip_delta=fip_delta, sp_fip_available=True,
        ))
    return rows


def _write_jsonl(rows: list[dict], path: Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _make_form_result(
    form_name: str = FORM_TANH_CURRENT,
    failure_count: int = 6,
    overall_bss: float = 0.002,
    heavy_fav_ece: float = 0.095,
    high_conf_bss: float = -0.005,
) -> FunctionalFormResult:
    return FunctionalFormResult(
        form_name=form_name,
        adjusted_rows=300,
        adjusted_rate=0.25,
        mean_abs_adjustment=0.00005,
        max_abs_adjustment=0.00075,
        overall_bss=overall_bss,
        overall_ece=0.028,
        heavy_fav_ece=heavy_fav_ece,
        high_conf_bss=high_conf_bss,
        month_2025_04_bss=0.001,
        failure_segment_count=failure_count,
        segment_details=[],
        diagnostic_only=True,
        candidate_patch_created=False,
        production_modified=False,
    )


def _make_bullpen_diag(
    score: float = 0.65,
    likely_missing: bool = True,
    pattern: str = "MIXED",
) -> BullpenDiagnosis:
    return BullpenDiagnosis(
        bullpen_missing_score=score,
        evidence=["heavy_favorite failing", "high_confidence failing"],
        recommended_features=list(RECOMMENDED_BULLPEN_FEATURES),
        failure_pattern=pattern,
        bullpen_feature_likely_missing=likely_missing,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# § T-001  Hard rule constants
# ═══════════════════════════════════════════════════════════════════════════════

class TestHardRuleConstants:
    def test_candidate_patch_created_false(self):
        assert CANDIDATE_PATCH_CREATED is False

    def test_production_modified_false(self):
        assert PRODUCTION_MODIFIED is False

    def test_diagnostic_only_true(self):
        assert DIAGNOSTIC_ONLY is True

    def test_valid_conclusions_set(self):
        expected = {SP_FUNCTIONAL_FORM_REDESIGN, BULLPEN_FEATURE_INVESTIGATION, COLLECT_MORE_DATA}
        assert _VALID_CONCLUSIONS == expected

    def test_no_patch_in_conclusion_names(self):
        for c in _VALID_CONCLUSIONS:
            assert "PATCH" not in c, f"Conclusion {c!r} must not contain 'PATCH'"

    def test_all_form_names_has_six_forms(self):
        assert len(ALL_FORM_NAMES) == 6

    def test_form_fn_registry_matches_all_form_names(self):
        for name in ALL_FORM_NAMES:
            assert name in _FORM_FNS, f"Form '{name}' not in _FORM_FNS"

    def test_recommended_bullpen_features_correct(self):
        expected = {
            "bullpen_fatigue_3d",
            "bullpen_fatigue_7d",
            "reliever_back_to_back_count",
            "bullpen_recent_era_proxy",
            "late_game_leverage_usage_proxy",
        }
        assert set(RECOMMENDED_BULLPEN_FEATURES) == expected

    def test_phase54_failure_count_is_six(self):
        assert _PHASE54_FAILURE_COUNT == 6

    def test_bullpen_score_threshold(self):
        assert _BULLPEN_SCORE_THRESHOLD == 0.60


# ═══════════════════════════════════════════════════════════════════════════════
# § T-002  Functional form implementations
# ═══════════════════════════════════════════════════════════════════════════════

class TestFunctionalForms:
    """Each form produces valid probabilities in [0.01, 0.99]."""

    _P0_AVAIL = {"sp_fip_delta_available": True, "sp_fip_delta": 2.0}
    _P0_UNAVAIL = {"sp_fip_delta_available": False, "sp_fip_delta": 2.0}
    _BASE = 0.55
    _MKT = 0.58

    def test_tanh_current_adjusts_when_available(self):
        adj = _apply_tanh_current(self._BASE, self._P0_AVAIL, self._MKT)
        assert adj != self._BASE
        assert 0.01 <= adj <= 0.99

    def test_tanh_current_no_adjust_when_unavailable(self):
        adj = _apply_tanh_current(self._BASE, self._P0_UNAVAIL, self._MKT)
        assert abs(adj - self._BASE) < 1e-9

    def test_tanh_stronger_larger_than_tanh_current(self):
        """Stronger form produces larger adjustments for same delta."""
        p0 = {"sp_fip_delta_available": True, "sp_fip_delta": 1.5}
        adj_curr = _apply_tanh_current(0.5, p0, 0.5)
        adj_strong = _apply_tanh_stronger(0.5, p0, 0.5)
        # Stronger should have larger abs adjustment from baseline
        assert abs(adj_strong - 0.5) > abs(adj_curr - 0.5)

    def test_linear_capped_bounded(self):
        """Linear form never exceeds ±0.008 adjustment."""
        p0 = {"sp_fip_delta_available": True, "sp_fip_delta": 100.0}  # extreme
        adj = _apply_linear_capped(0.5, p0, 0.5)
        assert abs(adj - 0.5) <= 0.008 + 1e-9

    def test_sign_only_applies_small_fixed_adjustment(self):
        """sign_only produces ±0.001 for |delta| > 1.0."""
        p0 = {"sp_fip_delta_available": True, "sp_fip_delta": 2.0}
        adj = _apply_sign_only(0.5, p0, 0.5)
        assert abs(adj - 0.5) == pytest.approx(0.001, abs=1e-9)

    def test_sign_only_no_adjustment_for_small_delta(self):
        """sign_only produces no adjustment for |delta| <= 1.0."""
        p0 = {"sp_fip_delta_available": True, "sp_fip_delta": 0.5}
        adj = _apply_sign_only(0.5, p0, 0.5)
        assert abs(adj - 0.5) < 1e-9

    def test_bucketed_delta_positive_for_large_away_edge(self):
        """delta >= 1.5: away SP worse → home advantage → +0.003."""
        p0 = {"sp_fip_delta_available": True, "sp_fip_delta": 2.0}
        adj = _apply_bucketed_delta(0.5, p0, 0.5)
        assert adj > 0.5

    def test_bucketed_delta_negative_for_large_home_edge(self):
        """delta <= -1.5: home SP worse → away advantage → -0.003."""
        p0 = {"sp_fip_delta_available": True, "sp_fip_delta": -2.0}
        adj = _apply_bucketed_delta(0.5, p0, 0.5)
        assert adj < 0.5

    def test_bucketed_delta_neutral(self):
        """-0.5 < delta < 0.5 → no adjustment."""
        p0 = {"sp_fip_delta_available": True, "sp_fip_delta": 0.2}
        adj = _apply_bucketed_delta(0.5, p0, 0.5)
        assert abs(adj - 0.5) < 1e-9

    def test_shrink_to_market_smaller_adjustment_high_conf(self):
        """High-confidence prediction gets 50% reduction in adjustment."""
        p0 = {"sp_fip_delta_available": True, "sp_fip_delta": 2.0}
        # High confidence: base_prob = 0.70, |0.70 - 0.5| = 0.20 >= 0.15
        adj_hc = _apply_shrink_to_market(0.70, p0, 0.60)
        # Low confidence: base_prob = 0.52, |0.52 - 0.5| = 0.02 < 0.15
        adj_lc = _apply_shrink_to_market(0.52, p0, 0.52)
        # High confidence should have smaller absolute adjustment
        assert abs(adj_hc - 0.70) < abs(adj_lc - 0.52) or abs(adj_hc - 0.70) < 0.001

    def test_all_forms_produce_valid_probs(self):
        """All forms clamp output to [0.01, 0.99]."""
        test_deltas = [-5.0, -1.0, 0.0, 1.0, 5.0]
        for delta in test_deltas:
            p0 = {"sp_fip_delta_available": True, "sp_fip_delta": delta}
            for base_p in [0.01, 0.2, 0.5, 0.8, 0.99]:
                for form_fn in _FORM_FNS.values():
                    adj = form_fn(base_p, p0, 0.5)
                    assert 0.01 <= adj <= 0.99, (
                        f"Form {form_fn.__name__} produced {adj} for base={base_p}, delta={delta}"
                    )

    def test_forms_no_adjust_when_feature_unavailable(self):
        """All forms produce base_prob when sp_fip_delta_available=False."""
        p0 = {"sp_fip_delta_available": False, "sp_fip_delta": 5.0}
        for form_name, form_fn in _FORM_FNS.items():
            adj = form_fn(0.55, p0, 0.58)
            assert abs(adj - 0.55) < 1e-9, (
                f"Form {form_name!r} adjusted prob when feature unavailable"
            )


# ═══════════════════════════════════════════════════════════════════════════════
# § T-003  Segment helpers
# ═══════════════════════════════════════════════════════════════════════════════

class TestSegmentHelpers:
    def test_odds_bucket_heavy_favorite(self):
        assert _odds_bucket(0.66) == "heavy_favorite"
        assert _odds_bucket(0.65) == "heavy_favorite"

    def test_odds_bucket_mid(self):
        assert _odds_bucket(0.50) == "mid"
        assert _odds_bucket(0.45) == "mid"

    def test_odds_bucket_underdog(self):
        assert _odds_bucket(0.44) == "underdog"
        assert _odds_bucket(0.30) == "underdog"

    def test_confidence_bucket_high(self):
        assert _confidence_bucket(0.65) == "high_confidence"   # 0.15 from 0.5
        assert _confidence_bucket(0.35) == "high_confidence"

    def test_confidence_bucket_mid(self):
        assert _confidence_bucket(0.58) == "mid_confidence"    # 0.08
        assert _confidence_bucket(0.43) == "mid_confidence"

    def test_confidence_bucket_low(self):
        assert _confidence_bucket(0.52) == "low_confidence"    # 0.02

    def test_disagree_bucket_high(self):
        assert _disagree_bucket(0.60, 0.45) == "high"          # 0.15 gap

    def test_disagree_bucket_medium(self):
        assert _disagree_bucket(0.58, 0.51) == "medium"        # 0.07

    def test_disagree_bucket_low(self):
        assert _disagree_bucket(0.55, 0.53) == "low"           # 0.02

    def test_month_key_format(self):
        assert _month_key("2025-04-15") == "month:2025-04"
        assert _month_key("2025-07-01") == "month:2025-07"

    def test_month_key_short_date(self):
        assert _month_key("202") == "month:unknown"


# ═══════════════════════════════════════════════════════════════════════════════
# § T-004  Metrics helpers
# ═══════════════════════════════════════════════════════════════════════════════

class TestMetricsHelpers:
    def test_compute_segment_metrics_sufficient_data(self):
        probs = [0.6] * 50
        labels = [1] * 30 + [0] * 20
        mkt = [0.58] * 50
        m = _compute_segment_metrics(probs, labels, mkt)
        assert m["n"] == 50
        assert m["model_bss"] is not None
        assert m["model_ece"] is not None

    def test_compute_segment_metrics_insufficient_data(self):
        probs = [0.6] * 10
        labels = [1] * 10
        mkt = [0.58] * 10
        m = _compute_segment_metrics(probs, labels, mkt)
        assert m["n"] == 10
        assert m["model_bss"] is None
        assert m["model_ece"] is None

    def test_is_failure_bss_below_threshold(self):
        m = {"model_bss": -0.02, "model_ece": 0.025, "market_ece": 0.025}
        assert _is_failure(m) is True

    def test_is_failure_ece_deterioration(self):
        m = {"model_bss": 0.001, "model_ece": 0.040, "market_ece": 0.025}
        assert _is_failure(m) is True  # ece diff = 0.015 > 0.01

    def test_is_failure_good_segment(self):
        m = {"model_bss": 0.003, "model_ece": 0.026, "market_ece": 0.025}
        assert _is_failure(m) is False

    def test_is_failure_none_bss_not_failure(self):
        """None BSS = insufficient data, not counted as failure."""
        m = {"model_bss": None, "model_ece": None, "market_ece": None}
        assert _is_failure(m) is False


# ═══════════════════════════════════════════════════════════════════════════════
# § T-005  Form evaluation (FunctionalFormResult)
# ═══════════════════════════════════════════════════════════════════════════════

class TestFormEvaluation:
    def test_evaluate_form_returns_result_object(self):
        rows = _make_synthetic_rows(100)
        fr = _evaluate_form(FORM_TANH_CURRENT, _apply_tanh_current, rows)
        assert isinstance(fr, FunctionalFormResult)
        assert fr.form_name == FORM_TANH_CURRENT

    def test_evaluate_form_hard_rules(self):
        rows = _make_synthetic_rows(100)
        for form_name in ALL_FORM_NAMES:
            fn = _FORM_FNS[form_name]
            fr = _evaluate_form(form_name, fn, rows)
            assert fr.diagnostic_only is True
            assert fr.candidate_patch_created is False
            assert fr.production_modified is False

    def test_evaluate_form_adjusted_rows_count(self):
        """All rows should be adjusted since all have sp_fip_delta_available=True."""
        rows = _make_synthetic_rows(50)
        fr = _evaluate_form(FORM_TANH_STRONGER, _apply_tanh_stronger, rows)
        # All rows have sp_fip_delta_available=True with non-zero delta
        assert fr.adjusted_rows > 0
        assert 0.0 <= fr.adjusted_rate <= 1.0

    def test_evaluate_form_adjustment_stats(self):
        rows = _make_synthetic_rows(80)
        fr = _evaluate_form(FORM_LINEAR_CAPPED, _apply_linear_capped, rows)
        assert fr.mean_abs_adjustment >= 0.0
        assert fr.max_abs_adjustment >= fr.mean_abs_adjustment

    def test_evaluate_form_overall_metrics(self):
        rows = _make_synthetic_rows(200)
        fr = _evaluate_form(FORM_TANH_CURRENT, _apply_tanh_current, rows)
        # With 200 rows, overall segment should have valid metrics
        assert fr.overall_bss is not None
        assert fr.overall_ece is not None

    def test_evaluate_form_segment_details_populated(self):
        rows = _make_synthetic_rows(150)
        fr = _evaluate_form(FORM_BUCKETED_DELTA, _apply_bucketed_delta, rows)
        assert len(fr.segment_details) > 0
        keys = {s.segment_key for s in fr.segment_details}
        assert "overall" in keys

    def test_evaluate_form_failure_count_non_negative(self):
        rows = _make_synthetic_rows(100)
        for form_name in ALL_FORM_NAMES:
            fn = _FORM_FNS[form_name]
            fr = _evaluate_form(form_name, fn, rows)
            assert fr.failure_segment_count >= 0

    def test_evaluate_form_no_unavailable_features(self):
        """When no features available, all forms should produce 0 adjusted rows."""
        rows = [_make_row(idx=i, sp_fip_available=False) for i in range(50)]
        for form_name in ALL_FORM_NAMES:
            fn = _FORM_FNS[form_name]
            fr = _evaluate_form(form_name, fn, rows)
            assert fr.adjusted_rows == 0


# ═══════════════════════════════════════════════════════════════════════════════
# § T-006  Bullpen missing-feature diagnosis
# ═══════════════════════════════════════════════════════════════════════════════

class TestBullpenDiagnosis:
    def test_bullpen_score_range_0_to_1(self):
        """bullpen_missing_score is always in [0, 1]."""
        # All possible failure segment combinations
        scenarios = [
            [],
            ["odds_bucket:heavy_favorite"],
            ["confidence:high_confidence"],
            ["month:2025-04"],
            ["disagreement:high"],
            ["odds_bucket:heavy_favorite", "confidence:high_confidence",
             "month:2025-04", "disagreement:high"],
        ]
        form_results = [_make_form_result(failure_count=6)]
        for segs in scenarios:
            bd = _score_bullpen_missing(segs, form_results)
            assert 0.0 <= bd.bullpen_missing_score <= 1.0

    def test_high_score_when_all_critical_segments_fail(self):
        """All 4 critical indicators → high score (>= 0.60)."""
        segs = [
            "odds_bucket:heavy_favorite",
            "confidence:high_confidence",
            "month:2025-04",
            "disagreement:high",
        ]
        form_results = [_make_form_result(failure_count=6)]
        bd = _score_bullpen_missing(segs, form_results)
        assert bd.bullpen_missing_score >= 0.60

    def test_likely_missing_flag_when_score_high(self):
        segs = [
            "odds_bucket:heavy_favorite",
            "confidence:high_confidence",
            "month:2025-04",
            "disagreement:high",
        ]
        form_results = [_make_form_result(failure_count=6)]
        bd = _score_bullpen_missing(segs, form_results)
        assert bd.bullpen_feature_likely_missing is True

    def test_low_score_when_no_critical_segments(self):
        """No critical failure indicators → low score (< 0.60)."""
        segs = ["odds_bucket:mid"]
        form_results = [_make_form_result(failure_count=4)]  # can fix heavy_fav
        bd = _score_bullpen_missing(segs, form_results)
        assert bd.bullpen_missing_score < 0.60

    def test_failure_pattern_mixed(self):
        segs = ["odds_bucket:heavy_favorite", "confidence:high_confidence"]
        form_results = [_make_form_result(failure_count=6)]
        bd = _score_bullpen_missing(segs, form_results)
        assert bd.failure_pattern == "MIXED"

    def test_failure_pattern_heavy_favorite_concentrated(self):
        segs = ["odds_bucket:heavy_favorite"]
        form_results = [_make_form_result(failure_count=6)]
        bd = _score_bullpen_missing(segs, form_results)
        assert bd.failure_pattern == "HEAVY_FAVORITE_CONCENTRATED"

    def test_failure_pattern_high_confidence_concentrated(self):
        segs = ["confidence:high_confidence"]
        form_results = [_make_form_result(failure_count=6)]
        bd = _score_bullpen_missing(segs, form_results)
        assert bd.failure_pattern == "HIGH_CONFIDENCE_CONCENTRATED"

    def test_failure_pattern_diffuse(self):
        segs = []
        form_results = [_make_form_result(failure_count=6)]
        bd = _score_bullpen_missing(segs, form_results)
        assert bd.failure_pattern == "DIFFUSE"

    def test_recommended_features_match_spec(self):
        segs = ["odds_bucket:heavy_favorite"]
        form_results = [_make_form_result()]
        bd = _score_bullpen_missing(segs, form_results)
        for feat in RECOMMENDED_BULLPEN_FEATURES:
            assert feat in bd.recommended_features

    def test_evidence_non_empty_when_heavy_fav_fails(self):
        segs = ["odds_bucket:heavy_favorite"]
        form_results = [_make_form_result(failure_count=6)]
        bd = _score_bullpen_missing(segs, form_results)
        assert len(bd.evidence) > 0


# ═══════════════════════════════════════════════════════════════════════════════
# § T-007  Decision framework
# ═══════════════════════════════════════════════════════════════════════════════

class TestDecisionFramework:
    def test_sp_functional_form_redesign_when_form_clearly_better(self):
        """If a form reduces failure_count by >= 2, conclusion = SP_FUNCTIONAL_FORM_REDESIGN."""
        tanh_curr = _make_form_result(
            FORM_TANH_CURRENT, failure_count=6, overall_bss=0.002
        )
        better_form = _make_form_result(
            FORM_BUCKETED_DELTA, failure_count=3, overall_bss=0.002
        )  # failure 6 → 3 = reduction of 3 >= 2
        form_results = [tanh_curr, better_form]
        bd = _make_bullpen_diag(score=0.30, likely_missing=False)
        conclusion, rationale, tasks = _decide_conclusion(form_results, bd, 6, tanh_curr)
        assert conclusion == SP_FUNCTIONAL_FORM_REDESIGN

    def test_bullpen_feature_investigation_when_score_high(self):
        """bullpen_score >= 0.60 and all forms can't reduce failures → BULLPEN_FEATURE_INVESTIGATION."""
        tanh_curr = _make_form_result(FORM_TANH_CURRENT, failure_count=6, overall_bss=0.002)
        better_bss = _make_form_result(FORM_LINEAR_CAPPED, failure_count=5, overall_bss=0.003)
        form_results = [tanh_curr, better_bss]
        bd = _make_bullpen_diag(score=0.65, likely_missing=True)
        conclusion, rationale, tasks = _decide_conclusion(form_results, bd, 6, tanh_curr)
        assert conclusion == BULLPEN_FEATURE_INVESTIGATION

    def test_collect_more_data_fallback(self):
        """No clear improvement, low bullpen score → COLLECT_MORE_DATA."""
        tanh_curr = _make_form_result(FORM_TANH_CURRENT, failure_count=6, overall_bss=0.002)
        similar_form = _make_form_result(FORM_SIGN_ONLY, failure_count=6, overall_bss=0.0015)
        form_results = [tanh_curr, similar_form]
        bd = _make_bullpen_diag(score=0.30, likely_missing=False)
        conclusion, rationale, tasks = _decide_conclusion(form_results, bd, 6, tanh_curr)
        assert conclusion == COLLECT_MORE_DATA

    def test_conclusion_always_in_valid_set(self):
        """All decision paths produce valid conclusions."""
        tanh_curr = _make_form_result(FORM_TANH_CURRENT, failure_count=6)
        scenarios = [
            # (form_results, bd)
            (
                [tanh_curr, _make_form_result(FORM_BUCKETED_DELTA, failure_count=2)],
                _make_bullpen_diag(0.20, False),
            ),
            (
                [tanh_curr, _make_form_result(FORM_SIGN_ONLY, failure_count=5, overall_bss=0.003)],
                _make_bullpen_diag(0.70, True),
            ),
            (
                [tanh_curr, _make_form_result(FORM_SIGN_ONLY, failure_count=6)],
                _make_bullpen_diag(0.20, False),
            ),
        ]
        for form_results, bd in scenarios:
            conclusion, _, _ = _decide_conclusion(form_results, bd, 6, tanh_curr)
            assert conclusion in _VALID_CONCLUSIONS, f"conclusion {conclusion!r} not in _VALID_CONCLUSIONS"

    def test_no_patch_in_conclusion(self):
        """Conclusion never contains 'PATCH'."""
        tanh_curr = _make_form_result(FORM_TANH_CURRENT, failure_count=6)
        bd = _make_bullpen_diag(0.30, False)
        conclusion, _, _ = _decide_conclusion([tanh_curr], bd, 6, tanh_curr)
        assert "PATCH" not in conclusion

    def test_rationale_is_non_empty_string(self):
        tanh_curr = _make_form_result(FORM_TANH_CURRENT, failure_count=6)
        bd = _make_bullpen_diag(0.30, False)
        _, rationale, _ = _decide_conclusion([tanh_curr], bd, 6, tanh_curr)
        assert isinstance(rationale, str)
        assert len(rationale) > 0

    def test_phase56_tasks_non_empty(self):
        tanh_curr = _make_form_result(FORM_TANH_CURRENT, failure_count=6)
        bd = _make_bullpen_diag(0.30, False)
        _, _, tasks = _decide_conclusion([tanh_curr], bd, 6, tanh_curr)
        assert isinstance(tasks, list)
        assert len(tasks) > 0


# ═══════════════════════════════════════════════════════════════════════════════
# § T-008  Phase55DiagnosisResult hard rules + __post_init__
# ═══════════════════════════════════════════════════════════════════════════════

class TestPhase55DiagnosisResultHardRules:
    def _make_result(self, conclusion: str = COLLECT_MORE_DATA) -> Phase55DiagnosisResult:
        return Phase55DiagnosisResult(
            functional_form_results=[_make_form_result()],
            bullpen_diagnosis=_make_bullpen_diag(0.30, False),
            conclusion=conclusion,
            conclusion_rationale="test",
            candidate_patch_created=False,
            production_modified=False,
            diagnostic_only=True,
        )

    def test_candidate_patch_created_false(self):
        r = self._make_result()
        assert r.candidate_patch_created is False

    def test_production_modified_false(self):
        r = self._make_result()
        assert r.production_modified is False

    def test_diagnostic_only_true(self):
        r = self._make_result()
        assert r.diagnostic_only is True

    def test_conclusion_in_valid_set(self):
        for c in _VALID_CONCLUSIONS:
            r = self._make_result(conclusion=c)
            assert r.conclusion in _VALID_CONCLUSIONS

    def test_post_init_raises_on_patch_created_true(self):
        with pytest.raises(AssertionError, match="candidate_patch_created"):
            Phase55DiagnosisResult(
                candidate_patch_created=True,
                production_modified=False,
                diagnostic_only=True,
                conclusion=COLLECT_MORE_DATA,
                bullpen_diagnosis=BullpenDiagnosis(),
            )

    def test_post_init_raises_on_production_modified_true(self):
        with pytest.raises(AssertionError, match="production_modified"):
            Phase55DiagnosisResult(
                candidate_patch_created=False,
                production_modified=True,
                diagnostic_only=True,
                conclusion=COLLECT_MORE_DATA,
                bullpen_diagnosis=BullpenDiagnosis(),
            )

    def test_post_init_raises_on_diagnostic_only_false(self):
        with pytest.raises(AssertionError, match="diagnostic_only"):
            Phase55DiagnosisResult(
                candidate_patch_created=False,
                production_modified=False,
                diagnostic_only=False,
                conclusion=COLLECT_MORE_DATA,
                bullpen_diagnosis=BullpenDiagnosis(),
            )

    def test_post_init_raises_on_invalid_conclusion(self):
        with pytest.raises(AssertionError, match="invalid conclusion"):
            Phase55DiagnosisResult(
                candidate_patch_created=False,
                production_modified=False,
                diagnostic_only=True,
                conclusion="PATCH_GATE_RECHECK",
                bullpen_diagnosis=BullpenDiagnosis(),
            )

    def test_post_init_raises_on_bullpen_score_out_of_range(self):
        with pytest.raises(AssertionError, match="bullpen_missing_score"):
            Phase55DiagnosisResult(
                candidate_patch_created=False,
                production_modified=False,
                diagnostic_only=True,
                conclusion=COLLECT_MORE_DATA,
                bullpen_diagnosis=BullpenDiagnosis(bullpen_missing_score=1.5),  # invalid
            )

    def test_phase55_version_set(self):
        r = self._make_result()
        assert r.phase55_version == PHASE55_VERSION


# ═══════════════════════════════════════════════════════════════════════════════
# § T-009  JSON serialization
# ═══════════════════════════════════════════════════════════════════════════════

class TestJsonSerialization:
    def _make_result(self) -> Phase55DiagnosisResult:
        return Phase55DiagnosisResult(
            run_timestamp="2026-05-05T09:00:00+00:00",
            audit_hash="abcd1234ef567890",
            phase54_failure_segments=["odds_bucket:heavy_favorite"],
            functional_form_results=[
                _make_form_result(FORM_TANH_CURRENT),
                _make_form_result(FORM_BUCKETED_DELTA, failure_count=4),
            ],
            best_form_name=FORM_BUCKETED_DELTA,
            best_form_failure_count=4,
            bullpen_diagnosis=_make_bullpen_diag(0.45, False, "HEAVY_FAVORITE_CONCENTRATED"),
            conclusion=COLLECT_MORE_DATA,
            conclusion_rationale="test rationale",
            recommended_phase56_tasks=["Task A", "Task B"],
            candidate_patch_created=False,
            production_modified=False,
            diagnostic_only=True,
        )

    def test_asdict_and_json_dumps(self):
        r = self._make_result()
        d = asdict(r)
        json_str = json.dumps(d, ensure_ascii=False, default=str)
        parsed = json.loads(json_str)
        assert parsed["candidate_patch_created"] is False
        assert parsed["production_modified"] is False
        assert parsed["diagnostic_only"] is True
        assert parsed["conclusion"] == COLLECT_MORE_DATA

    def test_json_has_all_top_level_keys(self):
        r = self._make_result()
        d = asdict(r)
        required_keys = [
            "phase55_version", "run_timestamp", "audit_hash",
            "phase54_failure_count", "phase54_failure_segments",
            "functional_form_results", "best_form_name", "best_form_failure_count",
            "bullpen_diagnosis", "conclusion", "conclusion_rationale",
            "recommended_phase56_tasks",
            "candidate_patch_created", "production_modified", "diagnostic_only",
        ]
        for k in required_keys:
            assert k in d, f"Missing key: {k}"

    def test_json_written_to_disk(self):
        r = self._make_result()
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "phase55.json"
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(asdict(r), f, ensure_ascii=False, default=str)
            assert json_path.exists()
            with open(json_path) as f:
                data = json.load(f)
            assert data["candidate_patch_created"] is False
            assert data["conclusion"] in list(_VALID_CONCLUSIONS)

    def test_functional_form_results_serializable(self):
        fr = _make_form_result()
        d = asdict(fr)
        json_str = json.dumps(d, default=str)
        parsed = json.loads(json_str)
        assert parsed["diagnostic_only"] is True
        assert parsed["candidate_patch_created"] is False

    def test_bullpen_diagnosis_serializable(self):
        bd = _make_bullpen_diag()
        d = asdict(bd)
        json_str = json.dumps(d, default=str)
        parsed = json.loads(json_str)
        assert "bullpen_missing_score" in parsed
        assert "recommended_features" in parsed
        assert "failure_pattern" in parsed


# ═══════════════════════════════════════════════════════════════════════════════
# § T-010  Markdown report
# ═══════════════════════════════════════════════════════════════════════════════

class TestMarkdownReport:
    def _make_result(self, conclusion: str = COLLECT_MORE_DATA) -> Phase55DiagnosisResult:
        return Phase55DiagnosisResult(
            run_timestamp="2026-05-05T09:00:00+00:00",
            audit_hash="deadbeef12345678",
            phase54_failure_count=6,
            phase54_failure_segments=[
                "odds_bucket:heavy_favorite",
                "confidence:high_confidence",
            ],
            functional_form_results=[
                _make_form_result(FORM_TANH_CURRENT, failure_count=6),
                _make_form_result(FORM_TANH_STRONGER, failure_count=5),
                _make_form_result(FORM_LINEAR_CAPPED, failure_count=5),
                _make_form_result(FORM_SIGN_ONLY, failure_count=6),
                _make_form_result(FORM_BUCKETED_DELTA, failure_count=4),
                _make_form_result(FORM_SHRINK_TO_MARKET, failure_count=6),
            ],
            best_form_name=FORM_BUCKETED_DELTA,
            best_form_failure_count=4,
            bullpen_diagnosis=_make_bullpen_diag(0.70, True, "MIXED"),
            conclusion=conclusion,
            conclusion_rationale="test rationale",
            recommended_phase56_tasks=["Phase 56A: Task A", "Phase 56B: Task B"],
            candidate_patch_created=False,
            production_modified=False,
            diagnostic_only=True,
        )

    def test_required_sections_present(self):
        from scripts.run_phase55_sp_vs_bullpen_diagnosis import _build_markdown
        r = self._make_result()
        md = _build_markdown(r, "2026-05-05")

        required_sections = [
            "Executive Summary",
            "Why Phase54 Failed",
            "SP Functional Form Comparison",
            "Bullpen Missing-Feature Evidence",
            "Decision Conclusion",
            "Recommended Phase56 Tasks",
            "Limitations",
            "Hard-Rule Confirmation",
            "Completion Marker",
        ]
        for section in required_sections:
            assert section in md, f"Section '{section}' missing from Markdown"

    def test_completion_marker_present(self):
        from scripts.run_phase55_sp_vs_bullpen_diagnosis import _build_markdown
        r = self._make_result()
        md = _build_markdown(r, "2026-05-05")
        assert "PHASE_55_SP_VS_BULLPEN_DIAGNOSIS_VERIFIED" in md

    def test_hard_rules_in_markdown(self):
        from scripts.run_phase55_sp_vs_bullpen_diagnosis import _build_markdown
        r = self._make_result()
        md = _build_markdown(r, "2026-05-05")
        assert "candidate_patch_created = False" in md
        assert "production_modified     = False" in md
        assert "diagnostic_only         = True" in md

    def test_conclusion_in_markdown(self):
        from scripts.run_phase55_sp_vs_bullpen_diagnosis import _build_markdown
        for c in [COLLECT_MORE_DATA, BULLPEN_FEATURE_INVESTIGATION, SP_FUNCTIONAL_FORM_REDESIGN]:
            r = self._make_result(conclusion=c)
            md = _build_markdown(r, "2026-05-05")
            assert c in md, f"Conclusion {c!r} not found in markdown"

    def test_all_form_names_in_table(self):
        """All 6 form names appear in the functional form comparison table."""
        from scripts.run_phase55_sp_vs_bullpen_diagnosis import _build_markdown
        r = self._make_result()
        md = _build_markdown(r, "2026-05-05")
        for form_name in ALL_FORM_NAMES:
            assert form_name in md, f"Form '{form_name}' not in markdown"

    def test_no_patch_gate_recheck_in_markdown(self):
        from scripts.run_phase55_sp_vs_bullpen_diagnosis import _build_markdown
        r = self._make_result()
        md = _build_markdown(r, "2026-05-05")
        assert "PATCH_GATE_RECHECK" not in md

    def test_bullpen_features_in_markdown(self):
        from scripts.run_phase55_sp_vs_bullpen_diagnosis import _build_markdown
        r = self._make_result()
        md = _build_markdown(r, "2026-05-05")
        for feat in RECOMMENDED_BULLPEN_FEATURES:
            assert feat in md, f"Bullpen feature '{feat}' not in markdown"

    def test_phase56_tasks_in_markdown(self):
        from scripts.run_phase55_sp_vs_bullpen_diagnosis import _build_markdown
        r = self._make_result()
        md = _build_markdown(r, "2026-05-05")
        assert "Phase 56" in md

    def test_markdown_written_to_disk(self):
        from scripts.run_phase55_sp_vs_bullpen_diagnosis import _build_markdown
        r = self._make_result()
        md = _build_markdown(r, "2026-05-05")
        with tempfile.TemporaryDirectory() as tmpdir:
            md_path = Path(tmpdir) / "phase55_report.md"
            md_path.write_text(md, encoding="utf-8")
            assert md_path.exists()
            content = md_path.read_text(encoding="utf-8")
            assert "PHASE_55_SP_VS_BULLPEN_DIAGNOSIS_VERIFIED" in content


# ═══════════════════════════════════════════════════════════════════════════════
# § T-011  Integration smoke test (requires real JSONL)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.skipif(
    not _REAL_FILES_EXIST,
    reason="Real Phase52 context JSONL not found; skip integration test",
)
class TestRunPhase55DiagnosisIntegration:
    """Integration test: run_phase55_diagnosis with real data."""

    def test_runs_end_to_end(self):
        result = run_phase55_diagnosis(
            context_path=_REAL_CONTEXT,
            phase54_report_path=_REAL_PHASE54_REPORT if _REAL_PHASE54_REPORT.exists() else None,
        )
        assert result.candidate_patch_created is False
        assert result.production_modified is False
        assert result.diagnostic_only is True
        assert result.conclusion in _VALID_CONCLUSIONS

    def test_six_forms_evaluated(self):
        result = run_phase55_diagnosis(context_path=_REAL_CONTEXT)
        assert len(result.functional_form_results) == 6

    def test_all_form_names_present(self):
        result = run_phase55_diagnosis(context_path=_REAL_CONTEXT)
        evaluated = {fr.form_name for fr in result.functional_form_results}
        for name in ALL_FORM_NAMES:
            assert name in evaluated

    def test_bullpen_score_in_range(self):
        result = run_phase55_diagnosis(context_path=_REAL_CONTEXT)
        assert 0.0 <= result.bullpen_diagnosis.bullpen_missing_score <= 1.0

    def test_no_production_files_written(self):
        """run_phase55_diagnosis must not create production JSONL files."""
        root = Path(__file__).resolve().parent.parent
        before_files = set(root.glob("data/mlb_2025/derived/*.jsonl"))
        run_phase55_diagnosis(context_path=_REAL_CONTEXT)
        after_files = set(root.glob("data/mlb_2025/derived/*.jsonl"))
        # Should not have added any new production JSONL files
        new_files = after_files - before_files
        # phase55 diagnosis files are OK if named with phase55; but no production names
        for f in new_files:
            assert "phase55" in f.name.lower(), (
                f"Unexpected production JSONL created: {f}"
            )
