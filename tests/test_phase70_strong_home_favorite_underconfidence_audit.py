"""Tests for Phase 70 — Strong Home Favorite Underconfidence Feature Root-Cause Audit.

All tests are paper-only; no production files modified.
Run: .venv/bin/python -m pytest tests/test_phase70_strong_home_favorite_underconfidence_audit.py -q
"""
from __future__ import annotations

import json
import math
import random
import tempfile
from pathlib import Path

import pytest

from orchestrator.phase70_strong_home_favorite_underconfidence_audit import (
    # Safety constants
    CANDIDATE_PATCH_CREATED,
    PRODUCTION_MODIFIED,
    ALPHA_MODIFIED,
    DIAGNOSTIC_ONLY,
    PREDICTION_JSONL_OVERWRITTEN,
    PIT_SAFE_VALIDATION,
    ALPHA,
    # Phase identity
    PHASE_VERSION,
    COMPLETION_MARKER,
    # Gates
    FEATURE_ROOT_CAUSE_PROMISING,
    MARKET_ONLY_SUPERIOR,
    ENSEMBLE_ATTRIBUTION_PROMISING,
    TEAM_OR_SPLIT_CONCENTRATION_PROMISING,
    DATA_LIMITED,
    OVERFIT_RISK,
    FEATURE_ROOT_CAUSE_NOT_PROMISING,
    _VALID_GATES,
    # Phase anchor
    PHASE69_GATE_ANCHOR,
    # Thresholds
    _MIN_SEGMENT_N,
    _TARGET_BAND_LO,
    _TARGET_BAND_HI,
    _FEATURE_EXTREME_DELTA,
    _MARKET_SUPERIORITY_BRIER_GAP,
    _NC_SIGNAL_THRESHOLD,
    _SEGMENT_DEFS,
    _FEATURE_PROBES,
    # Functions
    _brier,
    _bss_direct,
    _ece,
    _mean,
    _std,
    _percentile,
    _safe_float,
    _safe_bool,
    _enrich,
    _filter_segment,
    _compute_segment_metrics,
    _compute_all_segment_metrics,
    _compute_split_stability,
    _compute_team_concentration,
    _compute_feature_attribution,
    _bootstrap_residual_ci,
    _compute_bootstrap_cis,
    _run_negative_controls,
    _determine_gate,
    _to_dict,
    run_phase70_strong_home_favorite_underconfidence_audit,
    # Dataclasses
    SegmentMetrics,
    SplitStabilityResult,
    TeamConcentrationResult,
    FeatureAttributionResult,
    NegativeControlResult,
    BootstrapCI,
    Phase70Report,
)

# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────

def _make_row(
    model_home_prob: float = 0.67,
    market_home_prob_no_vig: float = 0.65,
    home_win: int = 1,
    split_id: str = "window_1",
    game_date: str = "2025-05-15",
    home_team: str = "NYY",
    away_team: str = "BOS",
    sp_fip_delta: float | None = 0.5,
    sp_fip_delta_available: bool = True,
    park_run_factor: float | None = 1.05,
    park_factor_available: bool = True,
    season_game_index: float | None = 42.0,
    season_game_index_available: bool = True,
    bullpen_fatigue_delta: float | None = -0.2,
    bullpen_available: bool = True,
) -> dict:
    return {
        "game_date": game_date,
        "game_id": f"gid_{game_date}_{home_team}",
        "home_team": home_team,
        "away_team": away_team,
        "home_win": home_win,
        "model_home_prob": model_home_prob,
        "market_home_prob_no_vig": market_home_prob_no_vig,
        "market_away_prob_no_vig": 1.0 - market_home_prob_no_vig,
        "split_id": split_id,
        "train_window_end": "2025-05-01",
        "test_window_start": "2025-05-02",
        "p0_features": {
            "sp_fip_delta": sp_fip_delta,
            "sp_fip_delta_available": sp_fip_delta_available,
            "park_run_factor": park_run_factor,
            "park_factor_available": park_factor_available,
            "season_game_index": season_game_index,
            "season_game_index_available": season_game_index_available,
            "sp_home_pitcher": "Pitcher A",
            "sp_away_pitcher": "Pitcher B",
        },
        "bullpen_features": {
            "home_bullpen_fatigue_3d": 0.3,
            "away_bullpen_fatigue_3d": 0.5,
            "bullpen_fatigue_delta_3d": bullpen_fatigue_delta,
            "bullpen_feature_available": bullpen_available,
        },
        "model_version": "test_v1",
        "feature_version": "phase56_sp_bullpen_context_v1",
        "candidate_patch_created": False,
        "production_modified": False,
        "diagnostic_only": True,
    }


def _enrich_rows(rows: list[dict]) -> list[dict]:
    """Helper: enrich in-place and return."""
    return _enrich(rows)


def _make_rows(n: int, model_prob: float = 0.67, win_rate: float = 0.5) -> list[dict]:
    """Make n rows with given model_prob and approximate win_rate."""
    rows = []
    for i in range(n):
        win = 1 if i < int(n * win_rate) else 0
        rows.append(_make_row(
            model_home_prob=model_prob,
            home_win=win,
            game_date=f"2025-06-{(i % 28) + 1:02d}",
            split_id=f"window_{(i % 5) + 1}",
        ))
    return _enrich_rows(rows)


# ─────────────────────────────────────────────────────────────────
# TestSafetyConstants
# ─────────────────────────────────────────────────────────────────

class TestSafetyConstants:
    def test_candidate_patch_created_is_false(self):
        assert CANDIDATE_PATCH_CREATED is False

    def test_production_modified_is_false(self):
        assert PRODUCTION_MODIFIED is False

    def test_alpha_modified_is_false(self):
        assert ALPHA_MODIFIED is False

    def test_diagnostic_only_is_true(self):
        assert DIAGNOSTIC_ONLY is True

    def test_prediction_jsonl_overwritten_is_false(self):
        assert PREDICTION_JSONL_OVERWRITTEN is False

    def test_pit_safe_validation_is_true(self):
        assert PIT_SAFE_VALIDATION is True

    def test_alpha_is_frozen(self):
        assert ALPHA == 0.40

    def test_alpha_is_float(self):
        assert isinstance(ALPHA, float)


# ─────────────────────────────────────────────────────────────────
# TestPhaseIdentity
# ─────────────────────────────────────────────────────────────────

class TestPhaseIdentity:
    def test_phase_version_contains_phase70(self):
        assert "phase70" in PHASE_VERSION

    def test_completion_marker_is_correct(self):
        assert COMPLETION_MARKER == "PHASE_70_STRONG_HOME_FAVORITE_UNDERCONFIDENCE_AUDIT_VERIFIED"

    def test_valid_gates_count(self):
        assert len(_VALID_GATES) == 7

    def test_all_gate_constants_in_valid_gates(self):
        for g in [
            FEATURE_ROOT_CAUSE_PROMISING,
            MARKET_ONLY_SUPERIOR,
            ENSEMBLE_ATTRIBUTION_PROMISING,
            TEAM_OR_SPLIT_CONCENTRATION_PROMISING,
            DATA_LIMITED,
            OVERFIT_RISK,
            FEATURE_ROOT_CAUSE_NOT_PROMISING,
        ]:
            assert g in _VALID_GATES

    def test_phase69_gate_anchor(self):
        assert PHASE69_GATE_ANCHOR == "CALIBRATION_OBJECTIVE_NOT_PROMISING"

    def test_segment_defs_contains_target_band(self):
        names = [s[0] for s in _SEGMENT_DEFS]
        assert "model_prob_0.65_0.70" in names

    def test_segment_defs_has_all_required(self):
        names = [s[0] for s in _SEGMENT_DEFS]
        required = [
            "all_games", "model_prob_0.65_0.70", "heavy_favorite",
            "high_confidence", "extreme_favorite", "home_favorite_only",
            "away_favorite_only", "phase45_failure",
        ]
        for r in required:
            assert r in names, f"Missing segment: {r}"

    def test_feature_probes_not_empty(self):
        assert len(_FEATURE_PROBES) >= 4


# ─────────────────────────────────────────────────────────────────
# TestCoreMath
# ─────────────────────────────────────────────────────────────────

class TestCoreMath:
    def test_brier_perfect(self):
        assert _brier([1.0, 0.0], [1.0, 0.0]) == pytest.approx(0.0)

    def test_brier_worst(self):
        assert _brier([0.0, 1.0], [1.0, 0.0]) == pytest.approx(1.0)

    def test_brier_uniform(self):
        b = _brier([0.5] * 100, [1] * 50 + [0] * 50)
        assert b == pytest.approx(0.25)

    def test_brier_empty(self):
        assert _brier([], []) == 0.0

    def test_bss_positive_when_model_better(self):
        bss = _bss_direct(0.20, 0.25)
        assert bss > 0

    def test_bss_negative_when_model_worse(self):
        bss = _bss_direct(0.25, 0.20)
        assert bss < 0

    def test_bss_zero_ref(self):
        assert _bss_direct(0.25, 0.0) == 0.0

    def test_ece_perfect_calibration(self):
        # Perfect: predict 0.7 → win rate 0.7
        probs = [0.7] * 100
        labels = [1] * 70 + [0] * 30
        ece = _ece(probs, labels)
        assert ece < 0.05

    def test_ece_empty(self):
        assert _ece([], []) == 0.0

    def test_mean_basic(self):
        assert _mean([1.0, 2.0, 3.0]) == pytest.approx(2.0)

    def test_mean_empty(self):
        assert _mean([]) == 0.0

    def test_std_basic(self):
        assert _std([0.0, 1.0]) == pytest.approx(0.5)

    def test_std_single(self):
        assert _std([1.0]) == 0.0

    def test_percentile_median(self):
        vals = list(range(101))
        assert _percentile(vals, 50) == pytest.approx(50.0)

    def test_percentile_empty(self):
        assert _percentile([], 50) == 0.0

    def test_safe_float_none(self):
        assert _safe_float(None) == 0.0

    def test_safe_float_string(self):
        assert _safe_float("0.5") == pytest.approx(0.5)

    def test_safe_bool_true(self):
        assert _safe_bool(True) is True
        assert _safe_bool("true") is True

    def test_safe_bool_false(self):
        assert _safe_bool(False) is False
        assert _safe_bool(None) is False


# ─────────────────────────────────────────────────────────────────
# TestEnrich
# ─────────────────────────────────────────────────────────────────

class TestEnrich:
    def test_enrich_adds_model_home_prob(self):
        row = _make_row(model_home_prob=0.67)
        _enrich([row])
        assert row["_model_home_prob"] == pytest.approx(0.67)

    def test_enrich_adds_market_home_prob(self):
        row = _make_row(market_home_prob_no_vig=0.63)
        _enrich([row])
        assert row["_market_home_prob"] == pytest.approx(0.63)

    def test_enrich_model_residual_correct(self):
        row = _make_row(model_home_prob=0.67, home_win=1)
        _enrich([row])
        assert row["_model_residual"] == pytest.approx(0.67 - 1.0)

    def test_enrich_market_residual_correct(self):
        row = _make_row(market_home_prob_no_vig=0.65, home_win=0)
        _enrich([row])
        assert row["_market_residual"] == pytest.approx(0.65 - 0.0)

    def test_enrich_model_minus_market(self):
        row = _make_row(model_home_prob=0.67, market_home_prob_no_vig=0.63)
        _enrich([row])
        assert row["_model_minus_market"] == pytest.approx(0.04)

    def test_enrich_month_bucket(self):
        row = _make_row(game_date="2025-07-15")
        _enrich([row])
        assert row["_month_bucket"] == "2025-07"

    def test_enrich_game_day_odd(self):
        row = _make_row(game_date="2025-07-15")
        _enrich([row])
        assert row["_game_day_odd"] == 1  # 15 is odd

    def test_enrich_game_day_even(self):
        row = _make_row(game_date="2025-07-14")
        _enrich([row])
        assert row["_game_day_odd"] == 0  # 14 is even

    def test_enrich_sp_fip_delta(self):
        row = _make_row(sp_fip_delta=0.75, sp_fip_delta_available=True)
        _enrich([row])
        assert row["_sp_fip_delta"] == 0.75
        assert row["_sp_fip_available"] is True

    def test_enrich_sp_fip_unavailable(self):
        row = _make_row(sp_fip_delta=None, sp_fip_delta_available=False)
        _enrich([row])
        assert row["_sp_fip_delta"] is None
        assert row["_sp_fip_available"] is False

    def test_enrich_bullpen_delta(self):
        row = _make_row(bullpen_fatigue_delta=-0.3, bullpen_available=True)
        _enrich([row])
        assert row["_bullpen_fatigue_delta"] == pytest.approx(-0.3)
        assert row["_bullpen_available"] is True

    def test_enrich_none_features(self):
        """Rows with no p0_features or bullpen_features should not crash."""
        row = _make_row()
        row["p0_features"] = None
        row["bullpen_features"] = None
        _enrich([row])  # should not raise
        assert row["_sp_fip_delta"] is None
        assert row["_bullpen_fatigue_delta"] is None


# ─────────────────────────────────────────────────────────────────
# TestFilterSegment
# ─────────────────────────────────────────────────────────────────

class TestFilterSegment:
    def _make_band_rows(self) -> list[dict]:
        rows = []
        for prob in [0.55, 0.62, 0.67, 0.72, 0.85]:
            rows.append(_make_row(model_home_prob=prob))
        return _enrich_rows(rows)

    def test_all_games_includes_all(self):
        rows = self._make_band_rows()
        out = _filter_segment(rows, 0.00, 1.01, None)
        assert len(out) == 5

    def test_target_band_filters_correctly(self):
        rows = self._make_band_rows()
        out = _filter_segment(rows, 0.65, 0.70, None)
        assert len(out) == 1
        assert out[0]["_model_home_prob"] == pytest.approx(0.67)

    def test_home_win_0_extra_filter(self):
        rows = [
            _make_row(model_home_prob=0.67, home_win=1),
            _make_row(model_home_prob=0.67, home_win=0),
        ]
        _enrich_rows(rows)
        out = _filter_segment(rows, 0.60, 1.01, "home_win_0")
        assert len(out) == 1
        assert out[0]["_home_win"] == 0.0

    def test_away_favorite_band(self):
        rows = [
            _make_row(model_home_prob=0.40),  # away favorite
            _make_row(model_home_prob=0.67),  # home favorite
        ]
        _enrich_rows(rows)
        out = _filter_segment(rows, 0.00, 0.50, None)
        assert len(out) == 1
        assert out[0]["_model_home_prob"] < 0.50


# ─────────────────────────────────────────────────────────────────
# TestSegmentMetrics
# ─────────────────────────────────────────────────────────────────

class TestSegmentMetrics:
    def _make_target_rows(self, n: int = 40, win_rate: float = 0.84) -> list[dict]:
        rows = []
        for i in range(n):
            win = 1 if i < int(n * win_rate) else 0
            rows.append(_make_row(
                model_home_prob=0.67,
                market_home_prob_no_vig=0.65,
                home_win=win,
                split_id=f"window_{(i % 5) + 1}",
                game_date=f"2025-07-{(i % 28) + 1:02d}",
            ))
        return _enrich_rows(rows)

    def test_segment_metrics_n_correct(self):
        rows = self._make_target_rows(40)
        sm = _compute_segment_metrics(rows, "model_prob_0.65_0.70", 0.65, 0.70, None)
        assert sm.n == 40

    def test_segment_metrics_data_limited_false(self):
        rows = self._make_target_rows(40)
        sm = _compute_segment_metrics(rows, "model_prob_0.65_0.70", 0.65, 0.70, None)
        assert not sm.data_limited

    def test_segment_metrics_data_limited_true(self):
        rows = self._make_target_rows(5)
        sm = _compute_segment_metrics(rows, "model_prob_0.65_0.70", 0.65, 0.70, None)
        assert sm.data_limited

    def test_segment_metrics_underconfidence_detected(self):
        """Model says 0.67 but actual win rate is 0.84 → underconfidence (neg residual)."""
        rows = self._make_target_rows(40, win_rate=0.84)
        sm = _compute_segment_metrics(rows, "test", 0.65, 0.70, None)
        # residual = model_prob - outcome = 0.67 - 0.84 = negative
        assert sm.residual_mean < -0.05

    def test_segment_metrics_severe_underconfidence_flag(self):
        rows = self._make_target_rows(40, win_rate=0.84)
        sm = _compute_segment_metrics(rows, "test", 0.65, 0.70, None)
        assert sm.severe_underconfidence is True

    def test_segment_metrics_market_beats_model(self):
        """When market is closer to actual, market_beats_model_brier=True."""
        rows = []
        for i in range(40):
            win = 1 if i < 34 else 0  # win_rate ≈ 0.85
            rows.append(_make_row(
                model_home_prob=0.67,         # model far from 0.85
                market_home_prob_no_vig=0.80,  # market closer
                home_win=win,
            ))
        _enrich_rows(rows)
        sm = _compute_segment_metrics(rows, "test", 0.00, 1.01, None)
        assert sm.market_beats_model_brier is True

    def test_segment_metrics_empty_segment(self):
        rows = _make_rows(20, model_prob=0.50)  # all at 0.50, none at 0.65-0.70
        sm = _compute_segment_metrics(rows, "test", 0.65, 0.70, None)
        assert sm.n == 0
        assert sm.data_limited is True

    def test_compute_all_segment_metrics_count(self):
        rows = _make_rows(200, model_prob=0.67)
        all_segs = _compute_all_segment_metrics(rows)
        assert len(all_segs) == len(_SEGMENT_DEFS)

    def test_compute_all_segment_metrics_has_target_band(self):
        rows = _make_rows(100, model_prob=0.67)
        all_segs = _compute_all_segment_metrics(rows)
        names = [s.segment for s in all_segs]
        assert "model_prob_0.65_0.70" in names

    def test_segment_metrics_has_model_minus_market(self):
        rows = self._make_target_rows(30)
        sm = _compute_segment_metrics(rows, "test", 0.00, 1.01, None)
        # model=0.67, market=0.65 → model_minus_market ≈ 0.02
        assert abs(sm.model_minus_market_mean - 0.02) < 0.01


# ─────────────────────────────────────────────────────────────────
# TestSplitStability
# ─────────────────────────────────────────────────────────────────

class TestSplitStability:
    def _make_multi_split_target_rows(self) -> list[dict]:
        rows = []
        # window_1: low win rate in target band
        for i in range(15):
            rows.append(_make_row(model_home_prob=0.67, home_win=0, split_id="window_1",
                                  game_date="2025-05-10"))
        # window_4: high win rate in target band
        for i in range(15):
            rows.append(_make_row(model_home_prob=0.67, home_win=1, split_id="window_4",
                                  game_date="2025-08-10"))
        return _enrich_rows(rows)

    def test_split_stability_returns_list(self):
        rows = self._make_multi_split_target_rows()
        results = _compute_split_stability(rows)
        assert isinstance(results, list)

    def test_split_stability_has_splits(self):
        rows = self._make_multi_split_target_rows()
        results = _compute_split_stability(rows)
        assert len(results) >= 2
        split_ids = [r.split_id for r in results]
        assert "window_1" in split_ids
        assert "window_4" in split_ids

    def test_split_stability_residuals_differ(self):
        """window_1 (all losses) vs window_4 (all wins) should have different residuals."""
        rows = self._make_multi_split_target_rows()
        results = _compute_split_stability(rows)
        by_split = {r.split_id: r for r in results}
        # window_1: residual = 0.67 - 0 = +0.67 (overconfident)
        # window_4: residual = 0.67 - 1 = -0.33 (underconfident)
        assert by_split["window_1"].residual_mean > 0
        assert by_split["window_4"].residual_mean < 0

    def test_split_stability_data_limited_small_n(self):
        rows = [_make_row(model_home_prob=0.67, split_id="window_1")]
        _enrich_rows(rows)
        results = _compute_split_stability(rows)
        if results:
            assert results[0].data_limited is True

    def test_split_stability_empty_target_band(self):
        rows = _make_rows(50, model_prob=0.50)  # no rows in 0.65-0.70
        results = _compute_split_stability(rows)
        assert results == []


# ─────────────────────────────────────────────────────────────────
# TestTeamConcentration
# ─────────────────────────────────────────────────────────────────

class TestTeamConcentration:
    def _make_concentrated_rows(self) -> list[dict]:
        rows = []
        # NYY appears 20 times in target band
        for i in range(20):
            rows.append(_make_row(model_home_prob=0.67, home_team="NYY",
                                  game_date=f"2025-07-{(i % 28) + 1:02d}"))
        # BOS appears 5 times
        for i in range(5):
            rows.append(_make_row(model_home_prob=0.67, home_team="BOS",
                                  game_date=f"2025-07-{(i % 28) + 1:02d}"))
        return _enrich_rows(rows)

    def test_team_concentration_returns_list(self):
        rows = self._make_concentrated_rows()
        results = _compute_team_concentration(rows)
        assert isinstance(results, list)

    def test_team_concentration_top_team_identified(self):
        rows = self._make_concentrated_rows()
        results = _compute_team_concentration(rows)
        assert len(results) >= 1
        top = results[0]
        assert top.team == "NYY"
        assert top.n_in_target_band == 20

    def test_team_concentration_share_correct(self):
        rows = self._make_concentrated_rows()
        results = _compute_team_concentration(rows)
        top = results[0]
        # NYY has 20 out of 25 = 0.80
        assert abs(top.share_of_target_band - 20 / 25) < 0.01

    def test_team_concentration_sorted_by_count(self):
        rows = self._make_concentrated_rows()
        results = _compute_team_concentration(rows)
        counts = [r.n_in_target_band for r in results]
        assert counts == sorted(counts, reverse=True)

    def test_team_concentration_empty_target_band(self):
        rows = _make_rows(50, model_prob=0.50)
        results = _compute_team_concentration(rows)
        assert results == []


# ─────────────────────────────────────────────────────────────────
# TestFeatureAttribution
# ─────────────────────────────────────────────────────────────────

class TestFeatureAttribution:
    def _make_feature_rows(self, n: int = 30, sp_fip: float = 0.8) -> list[dict]:
        rows = []
        for i in range(n):
            rows.append(_make_row(
                model_home_prob=0.67,
                sp_fip_delta=sp_fip,
                sp_fip_delta_available=True,
                game_date=f"2025-07-{(i % 28) + 1:02d}",
            ))
        # Also add some all_games rows with lower sp_fip
        for i in range(20):
            rows.append(_make_row(
                model_home_prob=0.55,
                sp_fip_delta=0.1,  # lower in all_games
                sp_fip_delta_available=True,
                game_date=f"2025-06-{(i % 28) + 1:02d}",
            ))
        return _enrich_rows(rows)

    def test_feature_attribution_returns_list(self):
        rows = self._make_feature_rows()
        results = _compute_feature_attribution(rows)
        assert isinstance(results, list)

    def test_feature_attribution_has_all_probes(self):
        rows = self._make_feature_rows()
        results = _compute_feature_attribution(rows)
        feat_names = [f.feature_name for f in results]
        for probe_name, _, _ in _FEATURE_PROBES:
            assert probe_name in feat_names

    def test_feature_attribution_availability_rate(self):
        rows = self._make_feature_rows(30)
        results = _compute_feature_attribution(rows)
        sp = next(f for f in results if f.feature_name == "sp_fip_delta")
        # All target rows (n=30) have sp_fip available
        assert sp.availability_rate_target == pytest.approx(1.0)

    def test_feature_attribution_extreme_delta_direction(self):
        """When sp_fip_delta is 0.8 in target vs 0.1 in all, extreme_delta should be positive."""
        rows = self._make_feature_rows(30, sp_fip=0.8)
        results = _compute_feature_attribution(rows)
        sp = next(f for f in results if f.feature_name == "sp_fip_delta")
        # target mean ≈ 0.8, all mean = mix of 0.8 and 0.1 → target > all
        assert sp.extreme_value_delta > 0.0

    def test_feature_attribution_unavailable_features(self):
        """Rows with feature unavailable should be reported without crashing."""
        rows = []
        for i in range(30):
            rows.append(_make_row(
                model_home_prob=0.67,
                sp_fip_delta=None,
                sp_fip_delta_available=False,
            ))
        _enrich_rows(rows)
        results = _compute_feature_attribution(rows)
        sp = next(f for f in results if f.feature_name == "sp_fip_delta")
        assert sp.mean_value_target is None
        assert sp.n_target_available == 0

    def test_feature_attribution_data_limited_when_few_available(self):
        rows = []
        for i in range(30):
            avail = i < 3  # only 3 available
            rows.append(_make_row(
                model_home_prob=0.67,
                sp_fip_delta=0.5 if avail else None,
                sp_fip_delta_available=avail,
            ))
        _enrich_rows(rows)
        results = _compute_feature_attribution(rows)
        sp = next(f for f in results if f.feature_name == "sp_fip_delta")
        assert sp.data_limited is True


# ─────────────────────────────────────────────────────────────────
# TestBootstrapCI
# ─────────────────────────────────────────────────────────────────

class TestBootstrapCI:
    def _make_underconf_rows(self, n: int = 50) -> list[dict]:
        rows = []
        for i in range(n):
            win = 1 if i < int(n * 0.84) else 0
            rows.append(_make_row(model_home_prob=0.67, home_win=win,
                                  game_date=f"2025-07-{(i % 28) + 1:02d}"))
        return _enrich_rows(rows)

    def test_bootstrap_ci_returns_ci(self):
        rows = self._make_underconf_rows(50)
        ci = _bootstrap_residual_ci(
            rows, 0.65, 0.70, "model_prob_0.65_0.70", "residual_mean",
            n_boot=100, rng=random.Random(42)
        )
        assert isinstance(ci, BootstrapCI)

    def test_bootstrap_ci_underconf_likely_excludes_zero(self):
        """With n=50 and residual ≈ -0.17, CI should likely exclude zero."""
        rows = self._make_underconf_rows(50)
        ci = _bootstrap_residual_ci(
            rows, 0.65, 0.70, "model_prob_0.65_0.70", "residual_mean",
            n_boot=500, rng=random.Random(42)
        )
        # Both bounds should be negative (underconfidence)
        assert ci.observed < -0.05
        assert ci.ci_upper < 0.0  # CI is fully negative

    def test_bootstrap_ci_data_limited_small_n(self):
        rows = [_make_row(model_home_prob=0.67)]
        _enrich_rows(rows)
        ci = _bootstrap_residual_ci(
            rows, 0.65, 0.70, "test", "residual_mean",
            n_boot=10, rng=random.Random(42)
        )
        assert ci.data_limited is True

    def test_bootstrap_ci_width_nonneg(self):
        rows = self._make_underconf_rows(50)
        ci = _bootstrap_residual_ci(
            rows, 0.65, 0.70, "test", "residual_mean",
            n_boot=100, rng=random.Random(42)
        )
        assert ci.ci_upper >= ci.ci_lower

    def test_compute_bootstrap_cis_count(self):
        rows = _make_rows(200, model_prob=0.67)
        cis = _compute_bootstrap_cis(rows, n_boot=50, rng=random.Random(42))
        assert len(cis) == 5

    def test_compute_bootstrap_cis_has_target_band(self):
        rows = _make_rows(100, model_prob=0.67)
        cis = _compute_bootstrap_cis(rows, n_boot=50, rng=random.Random(42))
        segs = [ci.segment for ci in cis]
        assert "model_prob_0.65_0.70" in segs


# ─────────────────────────────────────────────────────────────────
# TestNegativeControls
# ─────────────────────────────────────────────────────────────────

class TestNegativeControls:
    def _make_signal_rows(self, n: int = 200) -> list[dict]:
        rows = []
        for i in range(n):
            # Strong underconfidence in 0.65-0.70 band
            if i < 60:
                win = 1 if i < 50 else 0  # win rate 0.83 in target band
                rows.append(_make_row(model_home_prob=0.67, home_win=win,
                                      game_date=f"2025-07-{(i % 28) + 1:02d}",
                                      home_team=["NYY", "BOS", "LAD"][i % 3]))
            else:
                # Moderate signal elsewhere
                rows.append(_make_row(model_home_prob=0.55, home_win=int(i % 2),
                                      game_date=f"2025-06-{(i % 28) + 1:02d}",
                                      home_team=["CHC", "ATL", "HOU"][i % 3]))
        return _enrich_rows(rows)

    def test_negative_controls_returns_five(self):
        rows = self._make_signal_rows()
        ncs = _run_negative_controls(rows, n_permutations=50, rng=random.Random(42))
        assert len(ncs) == 5

    def test_negative_controls_names(self):
        rows = self._make_signal_rows()
        ncs = _run_negative_controls(rows, n_permutations=50, rng=random.Random(42))
        nc_names = {nc.control_name for nc in ncs}
        expected = {
            "shuffled_probability_band",
            "random_favorite_direction",
            "irrelevant_date_bucket_split",
            "random_team_bucket_split",
            "random_confidence_assignment",
        }
        assert nc_names == expected

    def test_negative_controls_have_interpretation(self):
        rows = self._make_signal_rows()
        ncs = _run_negative_controls(rows, n_permutations=50, rng=random.Random(42))
        for nc in ncs:
            assert len(nc.interpretation) > 0

    def test_negative_controls_overfit_risk_is_bool(self):
        rows = self._make_signal_rows()
        ncs = _run_negative_controls(rows, n_permutations=50, rng=random.Random(42))
        for nc in ncs:
            assert isinstance(nc.overfit_risk, bool)

    def test_nc_shuffled_band_null_gap_near_zero(self):
        """Shuffled band should produce near-zero mean null gap."""
        rows = self._make_signal_rows()
        ncs = _run_negative_controls(rows, n_permutations=100, rng=random.Random(42))
        nc1 = next(n for n in ncs if n.control_name == "shuffled_probability_band")
        # Null mean should be close to zero (random band = no structure)
        assert abs(nc1.permuted_gap_mean) < 0.10


# ─────────────────────────────────────────────────────────────────
# TestGateDetermination
# ─────────────────────────────────────────────────────────────────

class TestGateDetermination:
    def _make_empty_nc(self) -> list[NegativeControlResult]:
        """5 NCs with no overfit risk."""
        return [
            NegativeControlResult(
                control_name=f"nc_{i}", description="test",
                n_permutations=100, observed_gap=-0.10,
                permuted_gap_mean=0.0, permuted_gap_std=0.01,
                signal_gap=-0.10, overfit_risk=False,
                interpretation="SIGNAL"
            )
            for i in range(5)
        ]

    def _make_overfit_nc(self) -> list[NegativeControlResult]:
        """5 NCs all with overfit risk."""
        return [
            NegativeControlResult(
                control_name=f"nc_{i}", description="test",
                n_permutations=100, observed_gap=-0.01,
                permuted_gap_mean=0.0, permuted_gap_std=0.01,
                signal_gap=-0.01, overfit_risk=True,
                interpretation="NO SIGNAL"
            )
            for i in range(5)
        ]

    def _make_segment_metrics(self, n: int = 50, res: float = -0.17,
                               model_brier: float = 0.08,
                               market_brier: float = 0.06) -> list[SegmentMetrics]:
        return [SegmentMetrics(
            segment="model_prob_0.65_0.70", n=n,
            brier=model_brier, bss_vs_market=-0.3, ece=0.05,
            residual_mean=res, residual_std=0.07,
            observed_win_rate=0.84, predicted_mean_prob=0.67,
            market_brier=market_brier, market_residual_mean=-0.15,
            market_mean_prob=0.69,
            model_minus_market_mean=-0.02,
            market_beats_model_brier=(market_brier < model_brier),
            severe_underconfidence=True,
            data_limited=(n < _MIN_SEGMENT_N),
        ), SegmentMetrics(
            segment="all_games", n=2000,
            brier=0.24, bss_vs_market=0.0, ece=0.03,
            residual_mean=-0.02, residual_std=0.05,
            observed_win_rate=0.54, predicted_mean_prob=0.56,
            market_brier=0.24, market_residual_mean=-0.02,
            market_mean_prob=0.56,
            model_minus_market_mean=0.0,
            market_beats_model_brier=False,
            severe_underconfidence=False,
            data_limited=False,
        )]

    def test_data_limited_gate(self):
        small_segs = [SegmentMetrics(
            segment="model_prob_0.65_0.70", n=5,
            brier=0.1, bss_vs_market=0.0, ece=0.05,
            residual_mean=-0.17, residual_std=0.07,
            observed_win_rate=0.84, predicted_mean_prob=0.67,
            market_brier=0.09, market_residual_mean=-0.15,
            market_mean_prob=0.69,
            model_minus_market_mean=0.0,
            market_beats_model_brier=True,
            severe_underconfidence=False,
            data_limited=True,
        )]
        gate, *_ = _determine_gate(
            small_segs, [], [], [], self._make_empty_nc(), []
        )
        assert gate == DATA_LIMITED

    def test_overfit_risk_gate(self):
        segs = self._make_segment_metrics(50)
        gate, *_ = _determine_gate(
            segs, [], [], [], self._make_overfit_nc(), []
        )
        assert gate == OVERFIT_RISK

    def test_market_only_superior_gate(self):
        """When market Brier is much better than model in target band."""
        segs = self._make_segment_metrics(50, model_brier=0.10, market_brier=0.03)
        gate, *_ = _determine_gate(
            segs, [], [], [], self._make_empty_nc(), []
        )
        assert gate == MARKET_ONLY_SUPERIOR

    def test_default_gate_not_promising(self):
        segs = self._make_segment_metrics(50, model_brier=0.08, market_brier=0.077)
        gate, *_ = _determine_gate(
            segs, [], [], [], self._make_empty_nc(), []
        )
        assert gate == FEATURE_ROOT_CAUSE_NOT_PROMISING

    def test_gate_in_valid_gates(self):
        segs = self._make_segment_metrics(50)
        gate, *_ = _determine_gate(
            segs, [], [], [], self._make_empty_nc(), []
        )
        assert gate in _VALID_GATES

    def test_gate_has_rationale(self):
        segs = self._make_segment_metrics(50)
        gate, rationale, *_ = _determine_gate(
            segs, [], [], [], self._make_empty_nc(), []
        )
        assert len(rationale) > 0

    def test_gate_has_phase71_recommendation(self):
        segs = self._make_segment_metrics(50)
        gate, rationale, phase71_rec, *_ = _determine_gate(
            segs, [], [], [], self._make_empty_nc(), []
        )
        assert len(phase71_rec) > 0

    def test_worth_phase71_false_for_not_promising(self):
        segs = self._make_segment_metrics(50, model_brier=0.08, market_brier=0.077)
        gate, rationale, phase71_rec, risk_notes, worth = _determine_gate(
            segs, [], [], [], self._make_empty_nc(), []
        )
        assert gate == FEATURE_ROOT_CAUSE_NOT_PROMISING
        assert worth is False


# ─────────────────────────────────────────────────────────────────
# TestSerialization
# ─────────────────────────────────────────────────────────────────

class TestSerialization:
    def _make_minimal_report(self) -> Phase70Report:
        return Phase70Report(
            phase_version=PHASE_VERSION,
            completion_marker=COMPLETION_MARKER,
            generated_at="2026-05-07T00:00:00+00:00",
            data_path="/fake/path.jsonl",
            candidate_patch_created=False,
            production_modified=False,
            alpha_modified=False,
            diagnostic_only=True,
            prediction_jsonl_overwritten=False,
            pit_safe_validation=True,
            alpha=0.40,
            phase69_gate_anchor=PHASE69_GATE_ANCHOR,
            n_total=100,
            feature_version="phase56",
            n_target_band=30,
            segment_metrics=[],
            split_stability=[],
            team_concentration=[],
            feature_attribution=[],
            negative_controls=[],
            bootstrap_cis=[],
            gate=FEATURE_ROOT_CAUSE_NOT_PROMISING,
            gate_rationale="test",
            phase71_recommendation="test",
            risk_notes=[],
            market_better_in_target_band=False,
            feature_gap_detected=False,
            team_concentration_detected=False,
            split_instability_detected=False,
            negative_controls_clear=True,
            bootstrap_ci_stable=True,
            worth_phase71=False,
        )

    def test_to_dict_returns_dict(self):
        report = self._make_minimal_report()
        d = _to_dict(report)
        assert isinstance(d, dict)

    def test_to_dict_json_serializable(self):
        report = self._make_minimal_report()
        d = _to_dict(report)
        json.dumps(d)  # should not raise

    def test_report_has_completion_marker(self):
        report = self._make_minimal_report()
        d = _to_dict(report)
        assert d["completion_marker"] == COMPLETION_MARKER

    def test_report_has_safety_flags(self):
        report = self._make_minimal_report()
        d = _to_dict(report)
        assert d["candidate_patch_created"] is False
        assert d["production_modified"] is False
        assert d["alpha_modified"] is False
        assert d["diagnostic_only"] is True

    def test_report_has_gate(self):
        report = self._make_minimal_report()
        d = _to_dict(report)
        assert "gate" in d
        assert d["gate"] in _VALID_GATES

    def test_report_has_phase71_recommendation(self):
        report = self._make_minimal_report()
        d = _to_dict(report)
        assert "phase71_recommendation" in d


# ─────────────────────────────────────────────────────────────────
# TestThresholds
# ─────────────────────────────────────────────────────────────────

class TestThresholds:
    def test_min_segment_n_positive(self):
        assert _MIN_SEGMENT_N > 0

    def test_target_band_lo_hi_correct(self):
        assert _TARGET_BAND_LO == pytest.approx(0.65)
        assert _TARGET_BAND_HI == pytest.approx(0.70)

    def test_market_superiority_threshold_positive(self):
        assert _MARKET_SUPERIORITY_BRIER_GAP > 0

    def test_feature_extreme_delta_positive(self):
        assert _FEATURE_EXTREME_DELTA > 0

    def test_nc_signal_threshold_positive(self):
        assert _NC_SIGNAL_THRESHOLD > 0

    def test_segment_defs_count_at_least_11(self):
        assert len(_SEGMENT_DEFS) >= 11

    def test_target_band_lo_lt_hi(self):
        assert _TARGET_BAND_LO < _TARGET_BAND_HI

    def test_alpha_between_0_and_1(self):
        assert 0.0 < ALPHA < 1.0


# ─────────────────────────────────────────────────────────────────
# TestIntegration (synthetic data)
# ─────────────────────────────────────────────────────────────────

class TestIntegration:
    def _make_synthetic_jsonl(self, n_rows: int = 200) -> str:
        """Write synthetic JSONL to a temp file, return path."""
        rows = []
        for i in range(n_rows):
            if i < 60:
                prob = 0.67
                win = 1 if i < 50 else 0
            elif i < 120:
                prob = 0.55
                win = 1 if i % 2 == 0 else 0
            else:
                prob = 0.45
                win = 1 if i % 3 == 0 else 0

            market_prob = prob - 0.02
            row = _make_row(
                model_home_prob=prob,
                market_home_prob_no_vig=max(0.05, min(0.95, market_prob)),
                home_win=win,
                split_id=f"window_{(i % 5) + 1}",
                game_date=f"2025-{(i // 28) % 12 + 4:02d}-{(i % 28) + 1:02d}",
                home_team=["NYY", "BOS", "LAD", "CHC", "ATL"][i % 5],
            )
            rows.append(row)
        return rows

    def test_full_pipeline_synthetic(self):
        rows = self._make_synthetic_jsonl(200)
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False
        ) as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
            tmp_path = f.name

        report = run_phase70_strong_home_favorite_underconfidence_audit(
            predictions_path=tmp_path,
            n_boot=50,
            rng_seed=42,
        )
        assert isinstance(report, Phase70Report)
        assert report.gate in _VALID_GATES

    def test_full_pipeline_json_serializable(self):
        rows = self._make_synthetic_jsonl(200)
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False
        ) as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
            tmp_path = f.name

        report = run_phase70_strong_home_favorite_underconfidence_audit(
            predictions_path=tmp_path,
            n_boot=20,
            rng_seed=42,
        )
        d = _to_dict(report)
        json.dumps(d)  # should not raise

    def test_full_pipeline_required_fields(self):
        rows = self._make_synthetic_jsonl(200)
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False
        ) as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
            tmp_path = f.name

        report = run_phase70_strong_home_favorite_underconfidence_audit(
            predictions_path=tmp_path,
            n_boot=20,
            rng_seed=42,
        )
        d = _to_dict(report)
        required = [
            "phase_version", "completion_marker", "gate", "gate_rationale",
            "phase71_recommendation", "candidate_patch_created", "production_modified",
            "alpha_modified", "diagnostic_only", "prediction_jsonl_overwritten",
            "pit_safe_validation", "alpha", "segment_metrics", "split_stability",
            "team_concentration", "feature_attribution", "negative_controls",
            "bootstrap_cis", "risk_notes", "market_better_in_target_band",
            "feature_gap_detected", "team_concentration_detected",
            "split_instability_detected", "negative_controls_clear",
            "bootstrap_ci_stable", "worth_phase71",
        ]
        for fld in required:
            assert fld in d, f"Missing required field: {fld}"

    def test_full_pipeline_target_band_present_in_segments(self):
        rows = self._make_synthetic_jsonl(200)
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False
        ) as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
            tmp_path = f.name

        report = run_phase70_strong_home_favorite_underconfidence_audit(
            predictions_path=tmp_path,
            n_boot=20,
            rng_seed=42,
        )
        seg_names = [s.segment for s in report.segment_metrics]
        assert "model_prob_0.65_0.70" in seg_names

    def test_full_pipeline_five_negative_controls(self):
        rows = self._make_synthetic_jsonl(200)
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False
        ) as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
            tmp_path = f.name

        report = run_phase70_strong_home_favorite_underconfidence_audit(
            predictions_path=tmp_path,
            n_boot=20,
            rng_seed=42,
        )
        assert len(report.negative_controls) == 5

    def test_full_pipeline_safety_flags_frozen(self):
        rows = self._make_synthetic_jsonl(200)
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False
        ) as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
            tmp_path = f.name

        report = run_phase70_strong_home_favorite_underconfidence_audit(
            predictions_path=tmp_path,
            n_boot=20,
            rng_seed=42,
        )
        assert report.candidate_patch_created is False
        assert report.production_modified is False
        assert report.alpha_modified is False
        assert report.diagnostic_only is True
        assert report.prediction_jsonl_overwritten is False
        assert report.pit_safe_validation is True


# ─────────────────────────────────────────────────────────────────
# TestEndToEnd (real data — skipped if data not available)
# ─────────────────────────────────────────────────────────────────

_REAL_DATA_PATH = (
    Path(__file__).parent.parent
    / "data"
    / "mlb_2025"
    / "derived"
    / "mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl"
)

@pytest.mark.skipif(
    not _REAL_DATA_PATH.exists(),
    reason="Real predictions JSONL not available in this environment."
)
class TestEndToEnd:
    def test_real_data_n_total(self):
        report = run_phase70_strong_home_favorite_underconfidence_audit(
            predictions_path=_REAL_DATA_PATH,
            n_boot=500,
            rng_seed=42,
        )
        assert report.n_total == 2025

    def test_real_data_target_band_n_at_least_20(self):
        report = run_phase70_strong_home_favorite_underconfidence_audit(
            predictions_path=_REAL_DATA_PATH,
            n_boot=500,
            rng_seed=42,
        )
        assert report.n_target_band >= _MIN_SEGMENT_N

    def test_real_data_gate_in_valid_gates(self):
        report = run_phase70_strong_home_favorite_underconfidence_audit(
            predictions_path=_REAL_DATA_PATH,
            n_boot=500,
            rng_seed=42,
        )
        assert report.gate in _VALID_GATES

    def test_real_data_five_negative_controls(self):
        report = run_phase70_strong_home_favorite_underconfidence_audit(
            predictions_path=_REAL_DATA_PATH,
            n_boot=200,
            rng_seed=42,
        )
        assert len(report.negative_controls) == 5

    def test_real_data_target_band_underconfidence(self):
        """Confirmed from Phase 69: 0.65–0.70 band has negative residual (underconfident)."""
        report = run_phase70_strong_home_favorite_underconfidence_audit(
            predictions_path=_REAL_DATA_PATH,
            n_boot=100,
            rng_seed=42,
        )
        target = next(
            (s for s in report.segment_metrics if s.segment == "model_prob_0.65_0.70"),
            None
        )
        assert target is not None
        if not target.data_limited:
            # Phase 69 found residual ≈ -0.17 in eval set
            assert target.residual_mean < 0  # at minimum, should still be negative

    def test_real_data_bootstrap_ci_target_band(self):
        report = run_phase70_strong_home_favorite_underconfidence_audit(
            predictions_path=_REAL_DATA_PATH,
            n_boot=200,
            rng_seed=42,
        )
        target_ci = next(
            (ci for ci in report.bootstrap_cis
             if ci.segment == "model_prob_0.65_0.70" and ci.metric == "residual_mean"),
            None
        )
        assert target_ci is not None
        assert not target_ci.data_limited
