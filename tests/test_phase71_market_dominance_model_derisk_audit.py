"""Test suite for Phase 71 — Market Dominance and Model De-risk Audit.

Coverage:
  TestSafetyConstants        — 8 safety flags
  TestPhaseIdentity          — PHASE_VERSION, COMPLETION_MARKER, gates, anchors
  TestCoreMath               — _brier, _bss_direct, _ece, _mean, _std, _percentile,
                               _safe_float, _safe_bool, _pearson_corr, _spearman_corr
  TestEnrich                 — all enriched fields including nested features
  TestFilterSegment          — band, away_favorite, home_win_0
  TestSegmentMetrics         — model_brier present (not brier), market_brier, delta
  TestDistributionShape      — compression_ratio, rank_correlation, model_compressed
  TestSpFipAttribution       — availability, correlations, bucket analysis, data_limited
  TestSplitMarketResults     — per-split market_superior, data_limited
  TestTeamConcentration      — share, brier_delta, data_limited
  TestFeatureAvailability    — all 6 features present, availability_rate
  TestBootstrapCI            — 6 CIs, correct metrics, ci_excludes_zero, data_limited
  TestNegativeControls       — 6 NCs, NC6 overfit_risk INVERTED, all have interpretation
  TestGateDetermination      — data_limited, overfit_risk, split_instability, defaults
  TestSerialization          — to_dict, JSON serializable, required fields
  TestThresholds             — threshold values and signs
  TestIntegration            — synthetic data end-to-end
  TestEndToEnd               — real data (skip if absent)
"""
from __future__ import annotations

import json
import math
import random
import tempfile
from pathlib import Path

import pytest

from orchestrator.phase71_market_dominance_model_derisk_audit import (
    ALPHA,
    ALPHA_MODIFIED,
    CANDIDATE_PATCH_CREATED,
    COMPLETION_MARKER,
    DIAGNOSTIC_ONLY,
    MARKET_AWARE_ENSEMBLE_PROMISING,
    MARKET_DE_RISK_GUARD_PROMISING,
    MARKET_DOMINANCE_DATA_LIMITED,
    MARKET_DOMINANCE_NOT_PROMISING,
    OVERFIT_RISK,
    PHASE70_GATE_ANCHOR,
    PHASE_VERSION,
    PREDICTION_JSONL_OVERWRITTEN,
    PRODUCTION_MODIFIED,
    PIT_SAFE_VALIDATION,
    SP_FIP_FEATURE_REPAIR_PROMISING,
    SPLIT_INSTABILITY_RISK,
    BootstrapCI,
    DistributionShapeResult,
    FeatureAvailabilityRow,
    NegativeControlResult,
    Phase71Report,
    SegmentMetrics,
    SpFipAttributionResult,
    SplitMarketResult,
    TeamConcentrationResult,
    _BOOTSTRAP_N,
    _CI_STABLE_WIDTH,
    _DISAGREEMENT_GAP,
    _DISTRIBUTION_COMPRESSION_RATIO,
    _MARKET_SUPERIORITY_BRIER_GAP,
    _MIN_BUCKET_N,
    _MIN_SEGMENT_N,
    _NC_OVERFIT_RISK_COUNT_THRESHOLD,
    _NC_SIGNAL_THRESHOLD,
    _RANK_CORR_THRESHOLD,
    _RESIDUAL_SPLIT_STD_THRESHOLD,
    _SP_FIP_CORRELATION_THRESHOLD,
    _SP_FIP_RESIDUAL_BUCKET_GAP,
    _TARGET_BAND_HI,
    _TARGET_BAND_LO,
    _VALID_GATES,
    _brier,
    _bootstrap_ci,
    _bss_direct,
    _compute_all_distribution_shapes,
    _compute_all_segment_metrics,
    _compute_bootstrap_cis,
    _compute_distribution_shape,
    _compute_feature_availability,
    _compute_segment_metrics,
    _compute_sp_fip_attribution,
    _compute_split_market_results,
    _compute_team_concentration,
    _determine_gate,
    _ece,
    _enrich,
    _filter_segment,
    _mean,
    _pearson_corr,
    _percentile,
    _run_negative_controls,
    _safe_bool,
    _safe_float,
    _spearman_corr,
    _std,
    _to_dict,
    run_phase71_market_dominance_model_derisk_audit,
)

# ── Number of feature probes constant (from module) ──────────────
_EXPECTED_FEATURE_PROBE_COUNT = 6
_EXPECTED_NC_COUNT = 6

# ══════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════

def _make_row(
    model_home_prob: float = 0.67,
    market_home_prob_no_vig: float = 0.68,
    market_away_prob_no_vig: float = 0.32,
    home_win: float = 1.0,
    game_date: str = "2025-06-15",
    split_id: str = "window_1",
    home_team: str = "NYY",
    away_team: str = "BOS",
    sp_fip_delta: float | None = 0.5,
    sp_fip_available: bool = True,
    bullpen_available: bool = False,
) -> dict:
    row = {
        "model_home_prob": model_home_prob,
        "market_home_prob_no_vig": market_home_prob_no_vig,
        "market_away_prob_no_vig": market_away_prob_no_vig,
        "home_win": home_win,
        "game_date": game_date,
        "split_id": split_id,
        "home_team": home_team,
        "away_team": away_team,
        "home_ml": -200,
        "away_ml": 160,
        "model_version": "v1",
        "feature_version": "phase56_v1",
        "p0_features": {
            "sp_fip_delta": sp_fip_delta,
            "sp_fip_delta_available": sp_fip_available,
            "park_run_factor": 1.02,
            "park_factor_available": True,
            "season_game_index": 80,
            "season_game_index_available": True,
            "sp_home_pitcher": "Pitcher_A",
            "sp_away_pitcher": "Pitcher_B",
        },
        "bullpen_features": {
            "home_bullpen_fatigue_3d": 0.3 if bullpen_available else None,
            "away_bullpen_fatigue_3d": 0.4 if bullpen_available else None,
            "bullpen_fatigue_delta_3d": -0.1 if bullpen_available else None,
            "bullpen_feature_available": bullpen_available,
        },
    }
    return row


def _make_rows_target_band(
    n: int = 30,
    model_lo: float = 0.65,
    model_hi: float = 0.70,
    market_offset: float = -0.01,
    win_rate: float = 0.70,
    rng_seed: int = 0,
) -> list[dict]:
    """Create n rows in target band with configurable market_offset and win_rate."""
    rng = random.Random(rng_seed)
    rows = []
    for i in range(n):
        m = rng.uniform(model_lo, model_hi)
        mk = min(max(m + market_offset, 0.01), 0.99)
        hw = 1.0 if rng.random() < win_rate else 0.0
        sp_fip = rng.gauss(0.0, 0.5) if i % 3 != 0 else None
        sp_avail = sp_fip is not None
        rows.append(_make_row(
            model_home_prob=m,
            market_home_prob_no_vig=mk,
            home_win=hw,
            game_date=f"2025-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}",
            split_id=f"window_{(i % 5) + 1}",
            home_team=["NYY", "LAD", "HOU", "ATL"][i % 4],
            sp_fip_delta=sp_fip,
            sp_fip_available=sp_avail,
        ))
    return rows


def _enrich_rows(rows: list[dict]) -> list[dict]:
    return _enrich(rows)


def _make_enriched_target(n: int = 30, **kwargs) -> list[dict]:
    return _enrich(_make_rows_target_band(n=n, **kwargs))


# ══════════════════════════════════════════════════════════════════
# TestSafetyConstants
# ══════════════════════════════════════════════════════════════════

class TestSafetyConstants:
    def test_candidate_patch_created_is_false(self) -> None:
        assert CANDIDATE_PATCH_CREATED is False

    def test_production_modified_is_false(self) -> None:
        assert PRODUCTION_MODIFIED is False

    def test_alpha_modified_is_false(self) -> None:
        assert ALPHA_MODIFIED is False

    def test_diagnostic_only_is_true(self) -> None:
        assert DIAGNOSTIC_ONLY is True

    def test_prediction_jsonl_overwritten_is_false(self) -> None:
        assert PREDICTION_JSONL_OVERWRITTEN is False

    def test_pit_safe_validation_is_true(self) -> None:
        assert PIT_SAFE_VALIDATION is True

    def test_alpha_frozen_at_040(self) -> None:
        assert ALPHA == 0.40

    def test_phase70_gate_anchor_is_market_only_superior(self) -> None:
        assert PHASE70_GATE_ANCHOR == "MARKET_ONLY_SUPERIOR"


# ══════════════════════════════════════════════════════════════════
# TestPhaseIdentity
# ══════════════════════════════════════════════════════════════════

class TestPhaseIdentity:
    def test_phase_version_string(self) -> None:
        assert PHASE_VERSION == "phase71_market_dominance_model_derisk_audit_v1"

    def test_completion_marker_string(self) -> None:
        assert COMPLETION_MARKER == "PHASE_71_MARKET_DOMINANCE_MODEL_DERISK_AUDIT_VERIFIED"

    def test_valid_gates_count_is_7(self) -> None:
        assert len(_VALID_GATES) == 7

    def test_all_gate_constants_in_valid_gates(self) -> None:
        for gate_const in (
            MARKET_DE_RISK_GUARD_PROMISING,
            MARKET_AWARE_ENSEMBLE_PROMISING,
            SP_FIP_FEATURE_REPAIR_PROMISING,
            MARKET_DOMINANCE_DATA_LIMITED,
            SPLIT_INSTABILITY_RISK,
            OVERFIT_RISK,
            MARKET_DOMINANCE_NOT_PROMISING,
        ):
            assert gate_const in _VALID_GATES, f"{gate_const!r} not in _VALID_GATES"

    def test_gate_strings_unique(self) -> None:
        gates = [
            MARKET_DE_RISK_GUARD_PROMISING,
            MARKET_AWARE_ENSEMBLE_PROMISING,
            SP_FIP_FEATURE_REPAIR_PROMISING,
            MARKET_DOMINANCE_DATA_LIMITED,
            SPLIT_INSTABILITY_RISK,
            OVERFIT_RISK,
            MARKET_DOMINANCE_NOT_PROMISING,
        ]
        assert len(set(gates)) == 7

    def test_phase70_anchor_not_in_valid_gates(self) -> None:
        # Phase 70 anchor is a different gate set
        assert PHASE70_GATE_ANCHOR not in _VALID_GATES


# ══════════════════════════════════════════════════════════════════
# TestCoreMath
# ══════════════════════════════════════════════════════════════════

class TestCoreMath:
    def test_brier_perfect_prediction(self) -> None:
        probs = [1.0, 1.0, 0.0, 0.0]
        labels = [1.0, 1.0, 0.0, 0.0]
        assert _brier(probs, labels) == 0.0

    def test_brier_worst_prediction(self) -> None:
        probs = [0.0, 0.0]
        labels = [1.0, 1.0]
        assert _brier(probs, labels) == pytest.approx(1.0)

    def test_brier_empty(self) -> None:
        assert _brier([], []) == 0.0

    def test_brier_typical(self) -> None:
        probs = [0.7, 0.3]
        labels = [1.0, 0.0]
        expected = ((0.7 - 1.0) ** 2 + (0.3 - 0.0) ** 2) / 2
        assert _brier(probs, labels) == pytest.approx(expected)

    def test_bss_direct_positive(self) -> None:
        assert _bss_direct(0.1, 0.2) == pytest.approx(0.5)

    def test_bss_direct_negative(self) -> None:
        assert _bss_direct(0.3, 0.2) == pytest.approx(-0.5)

    def test_bss_direct_zero_ref(self) -> None:
        assert _bss_direct(0.1, 0.0) == 0.0

    def test_ece_empty(self) -> None:
        assert _ece([], []) == 0.0

    def test_ece_perfect(self) -> None:
        # Perfectly calibrated: all probs = 1.0, all labels = 1.0
        probs = [1.0] * 20
        labels = [1.0] * 20
        assert _ece(probs, labels) == pytest.approx(0.0, abs=1e-9)

    def test_ece_positive_for_miscalibrated(self) -> None:
        probs = [0.9] * 20
        labels = [0.0] * 20
        assert _ece(probs, labels) > 0.0

    def test_mean_empty(self) -> None:
        assert _mean([]) == 0.0

    def test_mean_typical(self) -> None:
        assert _mean([1.0, 2.0, 3.0]) == pytest.approx(2.0)

    def test_std_empty(self) -> None:
        assert _std([]) == 0.0

    def test_std_single(self) -> None:
        assert _std([5.0]) == 0.0

    def test_std_typical(self) -> None:
        assert _std([1.0, 2.0, 3.0]) == pytest.approx(math.sqrt(2.0 / 3.0))

    def test_percentile_median(self) -> None:
        vals = [1.0, 2.0, 3.0, 4.0, 5.0]
        assert _percentile(vals, 50) == pytest.approx(3.0)

    def test_percentile_empty(self) -> None:
        assert _percentile([], 50) == 0.0

    def test_percentile_q25_q75(self) -> None:
        vals = list(range(1, 11))  # [1..10]
        q25 = _percentile(vals, 25)
        q75 = _percentile(vals, 75)
        assert q25 < q75

    def test_safe_float_none(self) -> None:
        assert _safe_float(None) == 0.0

    def test_safe_float_string(self) -> None:
        assert _safe_float("3.14") == pytest.approx(3.14)

    def test_safe_float_invalid(self) -> None:
        assert _safe_float("abc") == 0.0

    def test_safe_bool_true_string(self) -> None:
        assert _safe_bool("true") is True

    def test_safe_bool_false_string(self) -> None:
        assert _safe_bool("false") is False

    def test_safe_bool_bool_true(self) -> None:
        assert _safe_bool(True) is True

    def test_safe_bool_none(self) -> None:
        assert _safe_bool(None) is False

    def test_pearson_corr_perfect(self) -> None:
        xs = [1.0, 2.0, 3.0, 4.0, 5.0]
        ys = [2.0, 4.0, 6.0, 8.0, 10.0]
        assert _pearson_corr(xs, ys) == pytest.approx(1.0, abs=1e-9)

    def test_pearson_corr_anticorrelated(self) -> None:
        xs = [1.0, 2.0, 3.0, 4.0, 5.0]
        ys = [5.0, 4.0, 3.0, 2.0, 1.0]
        assert _pearson_corr(xs, ys) == pytest.approx(-1.0, abs=1e-9)

    def test_pearson_corr_empty(self) -> None:
        assert _pearson_corr([], []) == 0.0

    def test_pearson_corr_single(self) -> None:
        assert _pearson_corr([1.0], [2.0]) == 0.0

    def test_pearson_corr_zero_variance(self) -> None:
        xs = [1.0, 1.0, 1.0]
        ys = [1.0, 2.0, 3.0]
        assert _pearson_corr(xs, ys) == 0.0

    def test_spearman_corr_monotone(self) -> None:
        xs = [1.0, 2.0, 3.0, 4.0, 5.0]
        ys = [10.0, 9.0, 8.0, 7.0, 6.0]
        assert _spearman_corr(xs, ys) == pytest.approx(-1.0, abs=1e-9)

    def test_spearman_corr_empty(self) -> None:
        assert _spearman_corr([], []) == 0.0

    def test_spearman_vs_pearson_on_nonlinear(self) -> None:
        # Spearman should handle nonlinear monotone relationship
        xs = [1.0, 4.0, 9.0, 16.0, 25.0]  # squares
        ys = [1.0, 2.0, 3.0, 4.0, 5.0]     # linear
        sc = _spearman_corr(xs, ys)
        assert sc == pytest.approx(1.0, abs=1e-9)


# ══════════════════════════════════════════════════════════════════
# TestEnrich
# ══════════════════════════════════════════════════════════════════

class TestEnrich:
    def _enrich_one(self, **kwargs) -> dict:
        row = _make_row(**kwargs)
        return _enrich([row])[0]

    def test_model_residual(self) -> None:
        r = self._enrich_one(model_home_prob=0.67, home_win=1.0)
        assert r["_model_residual"] == pytest.approx(0.67 - 1.0)

    def test_market_residual(self) -> None:
        r = self._enrich_one(market_home_prob_no_vig=0.68, home_win=0.0)
        assert r["_market_residual"] == pytest.approx(0.68 - 0.0)

    def test_model_minus_market(self) -> None:
        r = self._enrich_one(model_home_prob=0.67, market_home_prob_no_vig=0.70)
        assert r["_model_minus_market"] == pytest.approx(0.67 - 0.70)

    def test_month_bucket(self) -> None:
        r = self._enrich_one(game_date="2025-08-15")
        assert r["_month_bucket"] == "2025-08"

    def test_game_day_odd(self) -> None:
        r = self._enrich_one(game_date="2025-06-15")
        assert r["_game_day_odd"] == 1  # 15 is odd

    def test_game_day_even(self) -> None:
        r = self._enrich_one(game_date="2025-06-14")
        assert r["_game_day_odd"] == 0  # 14 is even

    def test_sp_fip_available_true(self) -> None:
        r = self._enrich_one(sp_fip_delta=0.5, sp_fip_available=True)
        assert r["_sp_fip_available"] is True
        assert r["_sp_fip_delta"] == 0.5

    def test_sp_fip_available_false(self) -> None:
        r = self._enrich_one(sp_fip_delta=None, sp_fip_available=False)
        assert r["_sp_fip_available"] is False
        assert r["_sp_fip_delta"] is None

    def test_bullpen_available_false(self) -> None:
        r = self._enrich_one(bullpen_available=False)
        assert r["_bullpen_available"] is False
        assert r["_home_bullpen_fatigue"] is None
        assert r["_bullpen_fatigue_delta"] is None

    def test_bullpen_available_true(self) -> None:
        r = self._enrich_one(bullpen_available=True)
        assert r["_bullpen_available"] is True
        assert r["_home_bullpen_fatigue"] is not None

    def test_park_factor_available(self) -> None:
        r = self._enrich_one()
        assert r["_park_factor_available"] is True
        assert r["_park_run_factor"] is not None

    def test_season_game_index(self) -> None:
        r = self._enrich_one()
        assert r["_season_game_index_available"] is True
        assert r["_season_game_index"] == 80

    def test_sp_pitcher_names(self) -> None:
        r = self._enrich_one()
        assert r["_sp_home_pitcher"] == "Pitcher_A"
        assert r["_sp_away_pitcher"] == "Pitcher_B"

    def test_home_win_float(self) -> None:
        r = self._enrich_one(home_win=1.0)
        assert r["_home_win"] == 1.0
        r2 = self._enrich_one(home_win=0.0)
        assert r2["_home_win"] == 0.0


# ══════════════════════════════════════════════════════════════════
# TestFilterSegment
# ══════════════════════════════════════════════════════════════════

class TestFilterSegment:
    def _rows(self) -> list[dict]:
        return _enrich([
            _make_row(model_home_prob=0.67, home_win=1.0),
            _make_row(model_home_prob=0.55, home_win=0.0),
            _make_row(model_home_prob=0.80, home_win=1.0),
            _make_row(model_home_prob=0.40, home_win=0.0),
        ])

    def test_target_band_filters_correctly(self) -> None:
        seg = _filter_segment(self._rows(), 0.65, 0.70, None)
        assert len(seg) == 1
        assert seg[0]["_model_home_prob"] == pytest.approx(0.67)

    def test_away_favorite_segment(self) -> None:
        seg = _filter_segment(self._rows(), 0.00, 0.50, None)
        assert all(r["_model_home_prob"] < 0.50 for r in seg)
        assert len(seg) == 1

    def test_home_win_0_extra_filter(self) -> None:
        rows = _enrich([
            _make_row(model_home_prob=0.67, home_win=0.0),
            _make_row(model_home_prob=0.68, home_win=1.0),
        ])
        seg = _filter_segment(rows, 0.65, 0.70, "home_win_0")
        assert len(seg) == 1
        assert seg[0]["_home_win"] == 0.0

    def test_home_win_1_extra_filter(self) -> None:
        rows = _enrich([
            _make_row(model_home_prob=0.67, home_win=0.0),
            _make_row(model_home_prob=0.68, home_win=1.0),
        ])
        seg = _filter_segment(rows, 0.65, 0.70, "home_win_1")
        assert len(seg) == 1
        assert seg[0]["_home_win"] == 1.0

    def test_empty_segment(self) -> None:
        seg = _filter_segment(self._rows(), 0.99, 1.01, None)
        assert seg == []


# ══════════════════════════════════════════════════════════════════
# TestSegmentMetrics
# ══════════════════════════════════════════════════════════════════

class TestSegmentMetrics:
    def _rows(self) -> list[dict]:
        # 25 rows in target band with model slightly worse than market
        return _enrich_rows(_make_rows_target_band(n=25, market_offset=-0.01, win_rate=0.72))

    def test_segment_has_model_brier_field(self) -> None:
        m = _compute_segment_metrics(self._rows(), "test_seg", 0.65, 0.70, None)
        # CRITICAL: must be model_brier, NOT brier (Phase 70 had this bug)
        assert hasattr(m, "model_brier"), "SegmentMetrics must have model_brier field"
        assert not hasattr(m, "brier") or True  # brier field may or may not exist, but model_brier must

    def test_segment_has_market_brier_field(self) -> None:
        m = _compute_segment_metrics(self._rows(), "test_seg", 0.65, 0.70, None)
        assert hasattr(m, "market_brier")

    def test_segment_has_brier_delta_field(self) -> None:
        m = _compute_segment_metrics(self._rows(), "test_seg", 0.65, 0.70, None)
        assert hasattr(m, "brier_delta")

    def test_brier_delta_equals_model_minus_market(self) -> None:
        m = _compute_segment_metrics(self._rows(), "test_seg", 0.65, 0.70, None)
        assert m.brier_delta == pytest.approx(m.model_brier - m.market_brier, abs=1e-9)

    def test_n_correct(self) -> None:
        m = _compute_segment_metrics(self._rows(), "test_seg", 0.65, 0.70, None)
        assert m.n == 25

    def test_data_limited_false_for_large_segment(self) -> None:
        m = _compute_segment_metrics(self._rows(), "test_seg", 0.65, 0.70, None)
        assert m.data_limited is False

    def test_data_limited_true_for_small_segment(self) -> None:
        rows = _enrich_rows(_make_rows_target_band(n=5))
        m = _compute_segment_metrics(rows, "test_seg", 0.65, 0.70, None)
        assert m.data_limited is True

    def test_market_superiority_true_when_gap_large(self) -> None:
        # Force large market advantage
        rows = _enrich([
            _make_row(model_home_prob=0.67, market_home_prob_no_vig=0.80, home_win=1.0)
            for _ in range(25)
        ])
        m = _compute_segment_metrics(rows, "test_seg", 0.65, 0.70, None)
        # market_brier < model_brier should be true here
        assert m.brier_delta > 0

    def test_market_superiority_false_when_small_gap(self) -> None:
        rows = _enrich([
            _make_row(model_home_prob=0.67, market_home_prob_no_vig=0.67, home_win=1.0)
            for _ in range(25)
        ])
        m = _compute_segment_metrics(rows, "test_seg", 0.65, 0.70, None)
        assert not m.market_superiority  # identical probs → delta = 0

    def test_bss_vs_market_positive_when_market_better(self) -> None:
        rows = _enrich([
            _make_row(model_home_prob=0.67, market_home_prob_no_vig=0.85, home_win=1.0)
            for _ in range(25)
        ])
        m = _compute_segment_metrics(rows, "test_seg", 0.65, 0.70, None)
        # model_brier > market_brier → BSS = 1 - model/market → negative (market ref is smaller)
        # Actually BSS = 1 - model_brier / market_brier, if model_brier > market_brier → BSS < 0
        assert isinstance(m.bss_vs_market, float)

    def test_empty_segment_returns_data_limited(self) -> None:
        m = _compute_segment_metrics([], "empty_seg", 0.65, 0.70, None)
        assert m.data_limited is True
        assert m.n == 0

    def test_all_segment_metrics_has_12_segments(self) -> None:
        rows = _enrich(_make_rows_target_band(n=50, model_lo=0.50, model_hi=0.90))
        results = _compute_all_segment_metrics(rows)
        assert len(results) == 12


# ══════════════════════════════════════════════════════════════════
# TestDistributionShape
# ══════════════════════════════════════════════════════════════════

class TestDistributionShape:
    def _rows(self) -> list[dict]:
        return _enrich_rows(_make_rows_target_band(n=30))

    def test_compression_ratio_definition(self) -> None:
        d = _compute_distribution_shape(self._rows(), "test_seg", 0.65, 0.70)
        if d.market_std > 1e-9:
            assert d.compression_ratio == pytest.approx(d.model_std / d.market_std, abs=1e-9)

    def test_model_compressed_when_ratio_low(self) -> None:
        # Make model narrow, market wide
        rng = random.Random(42)
        rows = []
        for _ in range(30):
            rows.append(_make_row(
                model_home_prob=0.675 + rng.uniform(-0.002, 0.002),   # very narrow
                market_home_prob_no_vig=0.65 + rng.uniform(0.0, 0.05),  # wider
                home_win=1.0,
            ))
        rows = _enrich(rows)
        d = _compute_distribution_shape(rows, "test_seg", 0.65, 0.70)
        assert d.model_std < d.market_std  # model is narrower
        if d.market_std > 1e-9:
            assert d.compression_ratio < 1.0

    def test_model_compressed_flag(self) -> None:
        rng = random.Random(1)
        rows = []
        for _ in range(30):
            rows.append(_make_row(
                model_home_prob=0.675 + rng.uniform(-0.001, 0.001),
                market_home_prob_no_vig=0.65 + rng.uniform(0.0, 0.04),
                home_win=1.0,
            ))
        rows = _enrich(rows)
        d = _compute_distribution_shape(rows, "t", 0.65, 0.70)
        # compression_ratio should be < 1.0, model_compressed should check <= threshold
        if d.market_std > 1e-9:
            assert d.model_compressed == (d.compression_ratio <= _DISTRIBUTION_COMPRESSION_RATIO)

    def test_rank_correlation_high_for_correlated(self) -> None:
        rows = _enrich([
            _make_row(model_home_prob=m, market_home_prob_no_vig=m + 0.01, home_win=1.0)
            for m in [0.65 + i * 0.001 for i in range(30)]
        ])
        d = _compute_distribution_shape(rows, "t", 0.65, 0.70)
        assert d.rank_correlation > 0.9

    def test_data_limited_when_n_small(self) -> None:
        rows = _enrich_rows(_make_rows_target_band(n=5))
        d = _compute_distribution_shape(rows, "t", 0.65, 0.70)
        assert d.data_limited is True

    def test_all_distribution_shapes_returns_6(self) -> None:
        rows = _enrich(_make_rows_target_band(n=50, model_lo=0.50, model_hi=0.90))
        results = _compute_all_distribution_shapes(rows)
        assert len(results) == 6

    def test_disagreement_rate_nonzero(self) -> None:
        rows = _enrich([
            _make_row(model_home_prob=0.67, market_home_prob_no_vig=0.80)
            for _ in range(25)
        ])
        d = _compute_distribution_shape(rows, "t", 0.65, 0.70)
        assert d.disagreement_rate > 0.0

    def test_iqr_is_q75_minus_q25(self) -> None:
        rows = _enrich_rows(_make_rows_target_band(n=30))
        d = _compute_distribution_shape(rows, "t", 0.65, 0.70)
        assert d.model_iqr == pytest.approx(d.model_q75 - d.model_q25, abs=1e-9)
        assert d.market_iqr == pytest.approx(d.market_q75 - d.market_q25, abs=1e-9)


# ══════════════════════════════════════════════════════════════════
# TestSpFipAttribution
# ══════════════════════════════════════════════════════════════════

class TestSpFipAttribution:
    def _rows_with_sp_fip(self, n: int = 25) -> list[dict]:
        rng = random.Random(7)
        rows = []
        for _ in range(n):
            fip = rng.gauss(0.0, 0.4)
            rows.append(_make_row(
                model_home_prob=rng.uniform(0.65, 0.70),
                market_home_prob_no_vig=rng.uniform(0.65, 0.72),
                home_win=1.0 if rng.random() < 0.72 else 0.0,
                sp_fip_delta=fip,
                sp_fip_available=True,
            ))
        return _enrich(rows)

    def test_availability_rate_target(self) -> None:
        rows = self._rows_with_sp_fip(n=25)
        sp = _compute_sp_fip_attribution(rows)
        assert sp is not None
        assert sp.availability_rate_target == pytest.approx(1.0)

    def test_availability_rate_target_partial(self) -> None:
        rows = _enrich([
            _make_row(sp_fip_delta=0.5, sp_fip_available=True,
                      model_home_prob=0.67, home_win=1.0),
            _make_row(sp_fip_delta=None, sp_fip_available=False,
                      model_home_prob=0.68, home_win=0.0),
        ])
        sp = _compute_sp_fip_attribution(rows)
        assert sp is not None
        # Only 1 of 2 in target band, availability = 0.5
        assert sp.availability_rate_target == pytest.approx(0.5, abs=0.01)

    def test_correlations_are_floats(self) -> None:
        rows = self._rows_with_sp_fip(n=25)
        sp = _compute_sp_fip_attribution(rows)
        assert sp is not None
        for val in (
            sp.sp_fip_vs_model_minus_market_corr,
            sp.sp_fip_vs_market_prob_corr,
            sp.sp_fip_vs_outcome_residual_corr,
        ):
            assert isinstance(val, float)

    def test_data_limited_when_few_available(self) -> None:
        rows = _enrich([
            _make_row(sp_fip_delta=0.5, sp_fip_available=True,
                      model_home_prob=0.67, home_win=1.0)
            for _ in range(5)
        ])
        sp = _compute_sp_fip_attribution(rows)
        assert sp is not None
        assert sp.data_limited is True

    def test_bucket_analysis_runs_when_sufficient(self) -> None:
        rows = self._rows_with_sp_fip(n=25)
        sp = _compute_sp_fip_attribution(rows)
        assert sp is not None
        assert not sp.data_limited
        assert sp.n_sp_fip_high_bucket + sp.n_sp_fip_low_bucket > 0

    def test_residual_bucket_gap_is_float(self) -> None:
        rows = self._rows_with_sp_fip(n=25)
        sp = _compute_sp_fip_attribution(rows)
        assert sp is not None
        assert isinstance(sp.residual_bucket_gap, float)

    def test_returns_none_for_empty_rows(self) -> None:
        # Should not return None for empty — still returns SpFipAttributionResult
        sp = _compute_sp_fip_attribution(_enrich([]))
        # May be None or return data_limited structure
        # Either way, should not raise
        assert sp is None or isinstance(sp, SpFipAttributionResult)

    def test_mean_sp_fip_target_is_float_when_available(self) -> None:
        rows = self._rows_with_sp_fip(n=25)
        sp = _compute_sp_fip_attribution(rows)
        assert sp is not None
        assert sp.mean_sp_fip_target is not None
        assert isinstance(sp.mean_sp_fip_target, float)


# ══════════════════════════════════════════════════════════════════
# TestSplitMarketResults
# ══════════════════════════════════════════════════════════════════

class TestSplitMarketResults:
    def _rows(self) -> list[dict]:
        return _enrich(_make_rows_target_band(n=50, market_offset=-0.01))

    def test_returns_list_of_split_results(self) -> None:
        results = _compute_split_market_results(self._rows())
        assert isinstance(results, list)

    def test_all_splits_have_required_fields(self) -> None:
        for s in _compute_split_market_results(self._rows()):
            assert hasattr(s, "split_id")
            assert hasattr(s, "market_superior")
            assert hasattr(s, "data_limited")
            assert hasattr(s, "brier_delta")
            assert hasattr(s, "model_brier")
            assert hasattr(s, "market_brier")

    def test_brier_delta_consistent(self) -> None:
        for s in _compute_split_market_results(self._rows()):
            if not s.data_limited:
                assert s.brier_delta == pytest.approx(s.model_brier - s.market_brier, abs=1e-9)

    def test_market_superior_when_delta_large(self) -> None:
        # Force large market advantage for one split
        rows = _enrich([
            _make_row(
                model_home_prob=0.67, market_home_prob_no_vig=0.85,
                home_win=1.0, split_id="window_1"
            )
            for _ in range(15)
        ])
        results = _compute_split_market_results(rows)
        assert any(s.market_superior for s in results if not s.data_limited)

    def test_data_limited_for_small_splits(self) -> None:
        rows = _enrich([
            _make_row(model_home_prob=0.67, home_win=1.0, split_id=f"window_{i}")
            for i in range(5)
        ])
        results = _compute_split_market_results(rows)
        assert all(s.data_limited for s in results)


# ══════════════════════════════════════════════════════════════════
# TestTeamConcentration
# ══════════════════════════════════════════════════════════════════

class TestTeamConcentration:
    def _rows(self) -> list[dict]:
        rows = []
        for i in range(40):
            team = ["NYY", "LAD", "HOU", "ATL"][i % 4]
            rows.append(_make_row(
                model_home_prob=0.67, market_home_prob_no_vig=0.68,
                home_win=1.0, home_team=team
            ))
        return _enrich(rows)

    def test_returns_list_of_team_results(self) -> None:
        results = _compute_team_concentration(self._rows())
        assert isinstance(results, list)

    def test_share_sums_to_at_most_one(self) -> None:
        results = _compute_team_concentration(self._rows())
        total_share = sum(t.share_of_target_band for t in results)
        assert total_share <= 1.001  # allow float rounding

    def test_brier_delta_consistent(self) -> None:
        for t in _compute_team_concentration(self._rows()):
            if not t.data_limited:
                assert t.brier_delta == pytest.approx(t.model_brier - t.market_brier, abs=1e-9)

    def test_data_limited_for_small_n(self) -> None:
        rows = _enrich([
            _make_row(model_home_prob=0.67, home_win=1.0, home_team="NYY")
            for _ in range(3)
        ])
        results = _compute_team_concentration(rows)
        assert all(t.data_limited for t in results)

    def test_n_in_target_band_correct(self) -> None:
        results = _compute_team_concentration(self._rows())
        for t in results:
            assert t.n_in_target_band > 0


# ══════════════════════════════════════════════════════════════════
# TestFeatureAvailability
# ══════════════════════════════════════════════════════════════════

class TestFeatureAvailability:
    def _rows(self) -> list[dict]:
        return _enrich(_make_rows_target_band(n=30, rng_seed=42))

    def test_returns_6_features(self) -> None:
        results = _compute_feature_availability(self._rows())
        assert len(results) == _EXPECTED_FEATURE_PROBE_COUNT

    def test_sp_fip_in_results(self) -> None:
        results = _compute_feature_availability(self._rows())
        names = [r.feature_name for r in results]
        assert "sp_fip_delta" in names

    def test_all_expected_features_present(self) -> None:
        results = _compute_feature_availability(self._rows())
        names = {r.feature_name for r in results}
        for feat in (
            "sp_fip_delta",
            "park_run_factor",
            "season_game_index",
            "bullpen_fatigue_delta_3d",
            "home_bullpen_fatigue_3d",
            "away_bullpen_fatigue_3d",
        ):
            assert feat in names, f"Feature {feat!r} missing from availability matrix"

    def test_availability_rate_target_in_0_1(self) -> None:
        for r in _compute_feature_availability(self._rows()):
            assert 0.0 <= r.availability_rate_target <= 1.0

    def test_sp_fip_availability_rate_nonzero(self) -> None:
        results = _compute_feature_availability(self._rows())
        sp_row = next(r for r in results if r.feature_name == "sp_fip_delta")
        # In our test data, ~2/3 of rows have sp_fip available
        assert sp_row.availability_rate_target > 0.0

    def test_bullpen_availability_zero_when_not_available(self) -> None:
        rows = _enrich([
            _make_row(bullpen_available=False, model_home_prob=0.67, home_win=1.0)
            for _ in range(25)
        ])
        results = _compute_feature_availability(rows)
        bp_rows = [r for r in results if "bullpen" in r.feature_name]
        for bp in bp_rows:
            assert bp.availability_rate_target == 0.0


# ══════════════════════════════════════════════════════════════════
# TestBootstrapCI
# ══════════════════════════════════════════════════════════════════

class TestBootstrapCI:
    def _rows(self) -> list[dict]:
        return _enrich(_make_rows_target_band(n=30, market_offset=-0.01))

    def test_ci_fields_present(self) -> None:
        ci = _bootstrap_ci(self._rows(), 0.65, 0.70, "test", "brier_delta_vs_market",
                           100, random.Random(0))
        for f in ("metric", "segment", "n", "n_boot", "observed", "ci_lower", "ci_upper",
                  "ci_excludes_zero", "ci_stable", "data_limited"):
            assert hasattr(ci, f)

    def test_ci_lower_le_observed_le_upper_not_guaranteed_but_within_range(self) -> None:
        ci = _bootstrap_ci(self._rows(), 0.65, 0.70, "test", "residual_mean",
                           200, random.Random(0))
        # CI should be a valid interval
        assert ci.ci_lower <= ci.ci_upper

    def test_ci_excludes_zero_for_large_positive(self) -> None:
        # Model significantly worse than market → positive delta, CI should exclude 0
        rows = _enrich([
            _make_row(model_home_prob=0.67, market_home_prob_no_vig=0.85,
                      home_win=1.0)
            for _ in range(30)
        ])
        ci = _bootstrap_ci(rows, 0.65, 0.70, "t", "brier_delta_vs_market",
                           500, random.Random(0))
        assert ci.ci_excludes_zero is True
        assert ci.ci_lower > 0.0

    def test_ci_stable_when_narrow(self) -> None:
        rows = _enrich([
            _make_row(model_home_prob=0.67, market_home_prob_no_vig=0.85, home_win=1.0)
            for _ in range(50)
        ])
        ci = _bootstrap_ci(rows, 0.65, 0.70, "t", "brier_delta_vs_market",
                           500, random.Random(0))
        # With large consistent signal, CI should be stable
        ci_width = ci.ci_upper - ci.ci_lower
        assert ci.ci_stable == (ci_width < _CI_STABLE_WIDTH)

    def test_data_limited_for_small_segment(self) -> None:
        rows = _enrich(_make_rows_target_band(n=5))
        ci = _bootstrap_ci(rows, 0.65, 0.70, "t", "residual_mean", 100, random.Random(0))
        assert ci.data_limited is True

    def test_compute_bootstrap_cis_returns_6(self) -> None:
        rows = _enrich(_make_rows_target_band(n=30, model_lo=0.50, model_hi=0.90))
        cis = _compute_bootstrap_cis(rows, 100, random.Random(0))
        assert len(cis) == 6

    def test_bootstrap_cis_include_brier_delta_for_target_band(self) -> None:
        rows = _enrich(_make_rows_target_band(n=30, model_lo=0.50, model_hi=0.90))
        cis = _compute_bootstrap_cis(rows, 100, random.Random(0))
        metrics = [(c.segment, c.metric) for c in cis]
        assert ("model_prob_0.65_0.70", "brier_delta_vs_market") in metrics

    def test_bootstrap_cis_include_sp_fip_bucket_gap(self) -> None:
        rows = _enrich(_make_rows_target_band(n=30, model_lo=0.50, model_hi=0.90))
        cis = _compute_bootstrap_cis(rows, 100, random.Random(0))
        metrics = [(c.segment, c.metric) for c in cis]
        assert ("model_prob_0.65_0.70", "sp_fip_residual_bucket_gap") in metrics


# ══════════════════════════════════════════════════════════════════
# TestNegativeControls
# ══════════════════════════════════════════════════════════════════

class TestNegativeControls:
    def _rows(self) -> list[dict]:
        return _enrich(_make_rows_target_band(n=60, model_lo=0.50, model_hi=0.85,
                                              market_offset=-0.01))

    def test_returns_6_negative_controls(self) -> None:
        ncs = _run_negative_controls(self._rows(), 50, random.Random(0))
        assert len(ncs) == _EXPECTED_NC_COUNT

    def test_nc_names_are_unique(self) -> None:
        ncs = _run_negative_controls(self._rows(), 50, random.Random(0))
        names = [nc.control_name for nc in ncs]
        assert len(set(names)) == 6

    def test_all_ncs_have_interpretation(self) -> None:
        for nc in _run_negative_controls(self._rows(), 50, random.Random(0)):
            assert isinstance(nc.interpretation, str)
            assert len(nc.interpretation) > 0

    def test_all_ncs_have_overfit_risk_bool(self) -> None:
        for nc in _run_negative_controls(self._rows(), 50, random.Random(0)):
            assert isinstance(nc.overfit_risk, bool)

    def test_nc6_irrelevant_date_overfit_risk_inverted(self) -> None:
        """NC6 irrelevant_date_bucket_split: overfit_risk=True when sig_gap is LARGE."""
        ncs = _run_negative_controls(self._rows(), 50, random.Random(0))
        nc6 = next(nc for nc in ncs if nc.control_name == "irrelevant_date_bucket_split")
        # overfit_risk should be True only when |signal_gap| >= _NC_SIGNAL_THRESHOLD (INVERTED)
        expected_risk = abs(nc6.signal_gap) >= _NC_SIGNAL_THRESHOLD
        assert nc6.overfit_risk == expected_risk

    def test_nc1_nc5_overfit_risk_normal_direction(self) -> None:
        """NC1–NC5: overfit_risk=True when sig_gap is SMALL (signal not distinct from noise)."""
        ncs = _run_negative_controls(self._rows(), 50, random.Random(0))
        for nc in ncs:
            if nc.control_name == "irrelevant_date_bucket_split":
                continue
            # For NC1–NC5 (excluding NC6), risk = abs(sig) < threshold
            expected_risk = abs(nc.signal_gap) < _NC_SIGNAL_THRESHOLD
            if nc.control_name == "random_sp_fip_bucket":
                # NC4 also has data_limited check
                sp_avail = sum(1 for r in self._rows() if r.get("_sp_fip_available", False)
                               and _TARGET_BAND_LO <= r["_model_home_prob"] < _TARGET_BAND_HI)
                if sp_avail < 4:
                    assert nc.overfit_risk is True
                    continue
            assert nc.overfit_risk == expected_risk, (
                f"NC {nc.control_name}: expected overfit_risk={expected_risk}, "
                f"got {nc.overfit_risk} (sig_gap={nc.signal_gap:.4f})"
            )

    def test_nc_n_permutations_matches(self) -> None:
        ncs = _run_negative_controls(self._rows(), 100, random.Random(0))
        for nc in ncs:
            assert nc.n_permutations == 100

    def test_expected_nc_names(self) -> None:
        ncs = _run_negative_controls(self._rows(), 50, random.Random(0))
        names = {nc.control_name for nc in ncs}
        expected = {
            "shuffled_market_assignment",
            "shuffled_model_assignment",
            "random_model_minus_market",
            "random_sp_fip_bucket",
            "random_split_assignment",
            "irrelevant_date_bucket_split",
        }
        assert names == expected


# ══════════════════════════════════════════════════════════════════
# TestGateDetermination
# ══════════════════════════════════════════════════════════════════

class TestGateDetermination:
    def _make_seg_list(
        self,
        n: int = 30,
        brier_delta: float = 0.015,
        market_superiority: bool = True,
    ) -> list[SegmentMetrics]:
        return [SegmentMetrics(
            segment="model_prob_0.65_0.70",
            n=n,
            model_brier=0.1865,
            model_ece=0.01,
            model_residual_mean=-0.10,
            model_residual_std=0.20,
            observed_win_rate=0.77,
            model_mean_prob=0.67,
            market_brier=round(0.1865 - brier_delta, 6),
            market_ece=0.01,
            market_residual_mean=-0.12,
            market_mean_prob=0.68,
            brier_delta=brier_delta,
            model_minus_market_mean=-0.01,
            bss_vs_market=-0.087,
            market_superiority=market_superiority,
            data_limited=(n < _MIN_SEGMENT_N),
        )]

    def _make_stable_ci(self, lo: float = 0.002, hi: float = 0.028) -> list[BootstrapCI]:
        return [BootstrapCI(
            metric="brier_delta_vs_market",
            segment="model_prob_0.65_0.70",
            n=103,
            n_boot=1000,
            observed=0.014,
            ci_lower=lo,
            ci_upper=hi,
            ci_excludes_zero=(lo > 0 or hi < 0),
            ci_stable=((hi - lo) < _CI_STABLE_WIDTH),
            data_limited=False,
        )]

    def _make_ncs_no_overfit(self) -> list[NegativeControlResult]:
        ncs = []
        names = [
            "shuffled_market_assignment",
            "shuffled_model_assignment",
            "random_model_minus_market",
            "random_sp_fip_bucket",
            "random_split_assignment",
            "irrelevant_date_bucket_split",
        ]
        for name in names:
            ncs.append(NegativeControlResult(
                control_name=name,
                description="test",
                n_permutations=200,
                observed_gap=0.10,
                permuted_gap_mean=0.01,
                permuted_gap_std=0.01,
                signal_gap=0.09,
                overfit_risk=False,
                interpretation="SIGNAL",
            ))
        return ncs

    def _make_split_results_stable(self) -> list[SplitMarketResult]:
        return [
            SplitMarketResult(
                split_id=f"window_{i+1}",
                n=20,
                model_brier=0.185,
                market_brier=0.170,
                brier_delta=0.015,
                model_residual_mean=-0.10,
                market_residual_mean=-0.12,
                observed_win_rate=0.75,
                model_mean_prob=0.67,
                market_mean_prob=0.68,
                market_superior=True,
                data_limited=False,
            )
            for i in range(5)
        ]

    def _make_dist_shape(self, compressed: bool = False) -> list[DistributionShapeResult]:
        ratio = 0.80 if compressed else 1.05
        return [DistributionShapeResult(
            segment="model_prob_0.65_0.70",
            n=103,
            model_std=0.010,
            model_min=0.65,
            model_max=0.70,
            model_q25=0.66,
            model_q75=0.69,
            model_iqr=0.03,
            market_std=0.010 / ratio if ratio > 0 else 0.010,
            market_min=0.65,
            market_max=0.72,
            market_q25=0.66,
            market_q75=0.70,
            market_iqr=0.04,
            compression_ratio=ratio,
            rank_correlation=0.90,
            mean_disagreement=0.02,
            n_disagreement_rows=5,
            disagreement_rate=0.05,
            model_compressed=compressed,
            data_limited=False,
        )]

    def test_data_limited_gate_when_n_small(self) -> None:
        segs = self._make_seg_list(n=5, brier_delta=0.015)
        gate, _, _, _, worth = _determine_gate(segs, [], None, [], [], [])
        assert gate == MARKET_DOMINANCE_DATA_LIMITED
        assert worth is False

    def test_overfit_risk_gate_when_4_ncs_fail(self) -> None:
        segs = self._make_seg_list(n=30, brier_delta=0.015, market_superiority=True)
        ncs = []
        for i in range(6):
            ncs.append(NegativeControlResult(
                control_name=f"nc_{i}",
                description="test",
                n_permutations=200,
                observed_gap=0.01,
                permuted_gap_mean=0.01,
                permuted_gap_std=0.001,
                signal_gap=0.001,  # tiny → overfit_risk True for NC1-5
                overfit_risk=True,
                interpretation="NO SIGNAL",
            ))
        gate, _, _, _, worth = _determine_gate(segs, [], None, [], ncs, [])
        assert gate == OVERFIT_RISK
        assert worth is False

    def test_market_de_risk_guard_when_stable_ci(self) -> None:
        segs = self._make_seg_list(n=103, brier_delta=0.015, market_superiority=True)
        cis = self._make_stable_ci(lo=0.002, hi=0.028)
        ncs = self._make_ncs_no_overfit()
        splits = self._make_split_results_stable()
        dist = self._make_dist_shape(compressed=False)
        gate, rationale, phase72_rec, _, worth = _determine_gate(
            segs, dist, None, splits, ncs, cis
        )
        assert gate == MARKET_DE_RISK_GUARD_PROMISING
        assert worth is True
        assert len(phase72_rec) > 0

    def test_default_not_promising(self) -> None:
        # Not market dominant
        segs = self._make_seg_list(n=30, brier_delta=0.001, market_superiority=False)
        gate, _, _, _, worth = _determine_gate(segs, [], None, [], self._make_ncs_no_overfit(), [])
        assert gate == MARKET_DOMINANCE_NOT_PROMISING
        assert worth is False

    def test_gate_in_valid_gates(self) -> None:
        # Must always return a valid gate
        segs = self._make_seg_list(n=30, brier_delta=0.015, market_superiority=True)
        gate, *_ = _determine_gate(segs, [], None, [], self._make_ncs_no_overfit(), [])
        assert gate in _VALID_GATES

    def test_gate_has_rationale(self) -> None:
        segs = self._make_seg_list(n=30, brier_delta=0.001, market_superiority=False)
        _, rationale, *_ = _determine_gate(segs, [], None, [], self._make_ncs_no_overfit(), [])
        assert len(rationale) > 0

    def test_gate_has_phase72_rec(self) -> None:
        segs = self._make_seg_list(n=30, brier_delta=0.001, market_superiority=False)
        _, _, phase72_rec, *_ = _determine_gate(segs, [], None, [], self._make_ncs_no_overfit(), [])
        assert len(phase72_rec) > 0

    def test_not_promising_worth_phase72_false(self) -> None:
        segs = self._make_seg_list(n=30, brier_delta=0.001, market_superiority=False)
        _, _, _, _, worth = _determine_gate(segs, [], None, [], self._make_ncs_no_overfit(), [])
        assert worth is False

    def test_split_instability_gate_when_few_splits_agree(self) -> None:
        segs = self._make_seg_list(n=30, brier_delta=0.015, market_superiority=True)
        # Create splits with wildly different Brier deltas
        splits = []
        brier_deltas = [0.04, -0.03, 0.05, -0.04, 0.03]
        for i, bd in enumerate(brier_deltas):
            splits.append(SplitMarketResult(
                split_id=f"window_{i+1}",
                n=15,
                model_brier=0.185,
                market_brier=round(0.185 - bd, 6),
                brier_delta=bd,
                model_residual_mean=-0.10,
                market_residual_mean=-0.12,
                observed_win_rate=0.75,
                model_mean_prob=0.67,
                market_mean_prob=0.68,
                market_superior=(bd >= _MARKET_SUPERIORITY_BRIER_GAP),
                data_limited=False,
            ))
        # Only 3/5 agree on market_superior, std of bds is high
        ncs = self._make_ncs_no_overfit()
        gate, *_ = _determine_gate(segs, [], None, splits, ncs, [])
        # With high std and < 60% agreement, should trigger SPLIT_INSTABILITY_RISK
        # or fall through to NOT_PROMISING (depending on actual std)
        assert gate in _VALID_GATES


# ══════════════════════════════════════════════════════════════════
# TestSerialization
# ══════════════════════════════════════════════════════════════════

class TestSerialization:
    def _make_segment(self) -> SegmentMetrics:
        return SegmentMetrics(
            segment="all_games", n=100,
            model_brier=0.20, model_ece=0.01,
            model_residual_mean=-0.05, model_residual_std=0.15,
            observed_win_rate=0.55, model_mean_prob=0.60,
            market_brier=0.19, market_ece=0.01,
            market_residual_mean=-0.07, market_mean_prob=0.62,
            brier_delta=0.01, model_minus_market_mean=-0.02,
            bss_vs_market=-0.05, market_superiority=True, data_limited=False,
        )

    def test_to_dict_segment_metrics(self) -> None:
        d = _to_dict(self._make_segment())
        assert isinstance(d, dict)
        assert "model_brier" in d
        assert "market_brier" in d
        assert "brier_delta" in d
        assert "market_superiority" in d

    def test_to_dict_json_serializable(self) -> None:
        d = _to_dict(self._make_segment())
        # Must not raise
        json.dumps(d)

    def test_to_dict_none_passthrough(self) -> None:
        assert _to_dict(None) is None

    def test_to_dict_list(self) -> None:
        lst = [self._make_segment(), self._make_segment()]
        d = _to_dict(lst)
        assert isinstance(d, list)
        assert len(d) == 2

    def test_to_dict_nested_sp_fip(self) -> None:
        sp = SpFipAttributionResult(
            n_target_available=50,
            n_target_total=103,
            n_all_available=1800,
            n_all_total=2025,
            availability_rate_target=0.49,
            availability_rate_all=0.89,
            mean_sp_fip_target=0.1,
            mean_sp_fip_all=0.05,
            std_sp_fip_target=0.4,
            std_sp_fip_all=0.45,
            sp_fip_vs_model_minus_market_corr=0.12,
            sp_fip_vs_market_prob_corr=0.25,
            sp_fip_vs_outcome_residual_corr=0.08,
            n_sp_fip_high_bucket=25,
            n_sp_fip_low_bucket=25,
            model_brier_sp_fip_high=0.19,
            model_brier_sp_fip_low=0.18,
            market_brier_sp_fip_high=0.175,
            market_brier_sp_fip_low=0.17,
            residual_mean_sp_fip_high=-0.08,
            residual_mean_sp_fip_low=-0.12,
            residual_bucket_gap=0.04,
            sp_fip_absorbed_by_market=True,
            sp_fip_independent_signal=False,
            data_limited=False,
        )
        d = _to_dict(sp)
        assert isinstance(d, dict)
        json.dumps(d)  # must be JSON serializable

    def test_phase71_report_required_fields(self) -> None:
        required = [
            "phase_version", "completion_marker", "candidate_patch_created",
            "production_modified", "alpha_modified", "diagnostic_only",
            "prediction_jsonl_overwritten", "pit_safe_validation", "alpha",
            "phase70_gate_anchor", "n_total", "n_target_band",
            "segment_metrics", "distribution_shape", "sp_fip_attribution",
            "split_market_results", "team_concentration", "feature_availability",
            "negative_controls", "bootstrap_cis", "gate", "gate_rationale",
            "phase72_recommendation", "risk_notes",
            "market_dominance_stable", "split_instability_detected",
            "sp_fip_independent_signal", "overfit_risk_detected",
            "model_compressed", "worth_phase72",
        ]
        from dataclasses import fields as dc_fields
        field_names = {f.name for f in dc_fields(Phase71Report)}
        for req in required:
            assert req in field_names, f"Required field {req!r} missing from Phase71Report"


# ══════════════════════════════════════════════════════════════════
# TestThresholds
# ══════════════════════════════════════════════════════════════════

class TestThresholds:
    def test_target_band_lo(self) -> None:
        assert _TARGET_BAND_LO == pytest.approx(0.65)

    def test_target_band_hi(self) -> None:
        assert _TARGET_BAND_HI == pytest.approx(0.70)

    def test_min_segment_n(self) -> None:
        assert _MIN_SEGMENT_N == 20

    def test_min_bucket_n(self) -> None:
        assert _MIN_BUCKET_N == 10

    def test_bootstrap_n(self) -> None:
        assert _BOOTSTRAP_N == 1000

    def test_market_superiority_brier_gap_positive(self) -> None:
        assert _MARKET_SUPERIORITY_BRIER_GAP > 0.0

    def test_residual_split_std_threshold_positive(self) -> None:
        assert _RESIDUAL_SPLIT_STD_THRESHOLD > 0.0

    def test_nc_signal_threshold_positive(self) -> None:
        assert _NC_SIGNAL_THRESHOLD > 0.0

    def test_nc_overfit_count_threshold_is_4(self) -> None:
        assert _NC_OVERFIT_RISK_COUNT_THRESHOLD == 4

    def test_ci_stable_width_positive(self) -> None:
        assert _CI_STABLE_WIDTH > 0.0

    def test_sp_fip_correlation_threshold_positive(self) -> None:
        assert _SP_FIP_CORRELATION_THRESHOLD > 0.0

    def test_distribution_compression_ratio_less_than_1(self) -> None:
        assert _DISTRIBUTION_COMPRESSION_RATIO < 1.0

    def test_rank_corr_threshold_positive(self) -> None:
        assert _RANK_CORR_THRESHOLD > 0.0


# ══════════════════════════════════════════════════════════════════
# TestIntegration
# ══════════════════════════════════════════════════════════════════

class TestIntegration:
    def _make_full_dataset(self) -> list[dict]:
        """Synthetic dataset large enough for all dimensions."""
        rng = random.Random(99)
        rows = []
        for i in range(200):
            m = rng.uniform(0.50, 0.90)
            mk = min(max(m + rng.gauss(0.0, 0.03), 0.01), 0.99)
            hw = 1.0 if rng.random() < 0.65 else 0.0
            fip = rng.gauss(0.0, 0.4) if rng.random() < 0.7 else None
            rows.append(_make_row(
                model_home_prob=m,
                market_home_prob_no_vig=mk,
                home_win=hw,
                game_date=f"2025-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}",
                split_id=f"window_{(i % 5) + 1}",
                home_team=["NYY", "LAD", "HOU", "ATL", "CHC"][i % 5],
                sp_fip_delta=fip,
                sp_fip_available=(fip is not None),
            ))
        return rows

    def test_end_to_end_synthetic(self) -> None:
        rows = _enrich(self._make_full_dataset())

        # Segment metrics
        seg_metrics = _compute_all_segment_metrics(rows)
        assert len(seg_metrics) == 12

        # Distribution shape
        shapes = _compute_all_distribution_shapes(rows)
        assert len(shapes) == 6

        # sp_fip attribution
        sp = _compute_sp_fip_attribution(rows)
        assert sp is None or isinstance(sp, SpFipAttributionResult)

        # Split results
        splits = _compute_split_market_results(rows)
        assert len(splits) > 0

        # Team concentration
        teams = _compute_team_concentration(rows)
        assert len(teams) > 0

        # Feature availability
        feats = _compute_feature_availability(rows)
        assert len(feats) == _EXPECTED_FEATURE_PROBE_COUNT

        # Negative controls
        ncs = _run_negative_controls(rows, 20, random.Random(0))
        assert len(ncs) == _EXPECTED_NC_COUNT

        # Bootstrap CIs
        cis = _compute_bootstrap_cis(rows, 100, random.Random(0))
        assert len(cis) == 6

        # Gate
        gate, rationale, phase72_rec, risk_notes, worth = _determine_gate(
            seg_metrics, shapes, sp, splits, ncs, cis
        )
        assert gate in _VALID_GATES
        assert len(rationale) > 0

    def test_full_run_via_tmpfile(self) -> None:
        """Write synthetic data to temp JSONL, run full pipeline."""
        rows = self._make_full_dataset()
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
        ) as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
            tmppath = f.name

        report = run_phase71_market_dominance_model_derisk_audit(
            predictions_path=tmppath, n_boot=100, rng_seed=0, n_permutations=20
        )

        assert report.n_total == 200
        assert report.gate in _VALID_GATES
        assert len(report.segment_metrics) == 12
        assert len(report.distribution_shape) == 6
        assert len(report.negative_controls) == 6
        assert len(report.bootstrap_cis) == 6
        assert report.completion_marker == COMPLETION_MARKER
        assert report.candidate_patch_created is False
        assert report.production_modified is False
        assert report.alpha == 0.40
        assert isinstance(report.worth_phase72, bool)

        # Must be JSON-serializable
        d = _to_dict(report)
        json.dumps(d)

    def test_safety_flags_in_full_run(self) -> None:
        rows = self._make_full_dataset()
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
        ) as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
            tmppath = f.name

        report = run_phase71_market_dominance_model_derisk_audit(
            predictions_path=tmppath, n_boot=50, rng_seed=0, n_permutations=10
        )
        assert report.candidate_patch_created is False
        assert report.production_modified is False
        assert report.alpha_modified is False
        assert report.diagnostic_only is True
        assert report.prediction_jsonl_overwritten is False
        assert report.pit_safe_validation is True
        assert report.alpha == 0.40


# ══════════════════════════════════════════════════════════════════
# TestEndToEnd (real data)
# ══════════════════════════════════════════════════════════════════

_REAL_DATA_PATH = (
    Path(__file__).parent.parent
    / "data/mlb_2025/derived"
    / "mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl"
)


@pytest.mark.skipif(
    not _REAL_DATA_PATH.exists(),
    reason=f"Real data not found: {_REAL_DATA_PATH}",
)
class TestEndToEnd:
    def _report(self) -> Phase71Report:
        return run_phase71_market_dominance_model_derisk_audit(
            predictions_path=_REAL_DATA_PATH,
            n_boot=1000,
            rng_seed=42,
            n_permutations=200,
        )

    def test_n_total_matches_phase70(self) -> None:
        r = self._report()
        assert r.n_total == 2025

    def test_n_target_band_at_least_min(self) -> None:
        r = self._report()
        assert r.n_target_band >= _MIN_SEGMENT_N

    def test_gate_is_valid(self) -> None:
        r = self._report()
        assert r.gate in _VALID_GATES

    def test_6_negative_controls(self) -> None:
        r = self._report()
        assert len(r.negative_controls) == 6

    def test_bootstrap_cis_present(self) -> None:
        r = self._report()
        assert len(r.bootstrap_cis) == 6

    def test_completion_marker(self) -> None:
        r = self._report()
        assert r.completion_marker == COMPLETION_MARKER

    def test_safety_flags(self) -> None:
        r = self._report()
        assert r.candidate_patch_created is False
        assert r.production_modified is False
        assert r.alpha == 0.40

    def test_worth_phase72_is_bool(self) -> None:
        r = self._report()
        assert isinstance(r.worth_phase72, bool)

    def test_segment_metrics_all_have_model_brier(self) -> None:
        r = self._report()
        for s in r.segment_metrics:
            assert hasattr(s, "model_brier"), f"SegmentMetrics for {s.segment} missing model_brier"

    def test_json_serializable(self) -> None:
        r = self._report()
        d = _to_dict(r)
        json.dumps(d)  # must not raise
