"""Tests for Phase 67 — Context Failure Attribution.

Target: ~110 tests covering safety constants, team mappings, GL parsing,
rest day computation, context bucketing, segment extraction, metrics,
bootstrap, attribution dimension, negative control, OOF, gate logic,
end-to-end with real data, and backward compatibility.
"""
from __future__ import annotations

import json
import random
import tempfile
from datetime import date
from pathlib import Path

import pytest

# ── Module under test ────────────────────────────────────────────
from orchestrator.phase67_context_failure_attribution import (
    ALPHA,
    ALPHA_MODIFIED,
    CANDIDATE_PATCH_CREATED,
    COMPLETION_MARKER,
    CONTEXT_FEATURE_NOT_PROMISING,
    CONTEXT_FEATURE_PROMISING,
    DATA_LIMITED_GATE,
    DIAGNOSTIC_ONLY,
    DIAGNOSTIC_ONLY_SIGNAL,
    OVERFIT_RISK,
    PHASE64B_GATE_ANCHOR,
    PHASE65_GATE_ANCHOR,
    PHASE66_GATE_ANCHOR,
    PHASE_VERSION,
    PRODUCTION_MODIFIED,
    _AVAILABLE_DIMENSIONS,
    _BOOTSTRAP_N,
    _DATA_LIMITED_DIMENSIONS,
    _DATA_LIMITED_FIELDS,
    _EXTREME_FAV_THRESHOLD,
    _HEAVY_FAV_THRESHOLD,
    _HIGH_CONF_THRESHOLD,
    _MIN_BUCKET_N,
    _MIN_COVERAGE_RATE,
    _MIN_SEGMENT_N,
    _OOF_PROMISING_DELTA,
    _OVERFIT_SIGMA,
    _PHASE45_FAIL_MIN_FAV,
    _RETRO_TO_FULL,
    _TEAM_DIVISION,
    _VALID_GATES,
    _brier_score,
    _bss_direct,
    _bootstrap_bss_vs_market,
    _compute_attribution_dimension,
    _compute_ece,
    _compute_negative_control,
    _compute_oof,
    _compute_segment_metrics,
    _decide_gate,
    _enrich_rows,
    _extract_segment,
    _get_context_bucket,
    _load_gl2025,
    _rest_days,
    _blend_prob,
    _fav_prob,
    ContextAlignment,
    ContextRecord,
    Phase67Result,
    SegmentMetrics,
    AttributionBucket,
    BootstrapResult,
    NegativeControl,
    OOFResult,
    run_phase67_context_failure_attribution,
    save_result,
    _to_dict,
)

# ── Real data paths ──────────────────────────────────────────────
_REPO = Path(__file__).resolve().parent.parent
_PREDICTIONS_PATH = (
    _REPO
    / "data/mlb_2025/derived"
    / "mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl"
)
_GL2025_PATH = _REPO / "data/mlb_2025/gl2025.txt"


def _has_data() -> bool:
    return _PREDICTIONS_PATH.exists() and _GL2025_PATH.exists()


# ════════════════════════════════════════════════════════════════
# 1. Safety Constants
# ════════════════════════════════════════════════════════════════

class TestSafetyConstants:
    def test_candidate_patch_is_false(self):
        assert CANDIDATE_PATCH_CREATED is False

    def test_production_modified_is_false(self):
        assert PRODUCTION_MODIFIED is False

    def test_alpha_modified_is_false(self):
        assert ALPHA_MODIFIED is False

    def test_diagnostic_only_is_true(self):
        assert DIAGNOSTIC_ONLY is True

    def test_alpha_is_0_40(self):
        assert abs(ALPHA - 0.40) < 1e-9


# ════════════════════════════════════════════════════════════════
# 2. Gate Constants
# ════════════════════════════════════════════════════════════════

class TestGateConstants:
    def test_valid_gates_count(self):
        assert len(_VALID_GATES) == 5

    def test_context_feature_promising_in_gates(self):
        assert CONTEXT_FEATURE_PROMISING in _VALID_GATES

    def test_data_limited_in_gates(self):
        assert DATA_LIMITED_GATE in _VALID_GATES

    def test_overfit_risk_in_gates(self):
        assert OVERFIT_RISK in _VALID_GATES

    def test_not_promising_in_gates(self):
        assert CONTEXT_FEATURE_NOT_PROMISING in _VALID_GATES

    def test_diagnostic_only_signal_in_gates(self):
        assert DIAGNOSTIC_ONLY_SIGNAL in _VALID_GATES


# ════════════════════════════════════════════════════════════════
# 3. Phase Identity & Anchors
# ════════════════════════════════════════════════════════════════

class TestPhaseIdentity:
    def test_phase_version(self):
        assert "phase67" in PHASE_VERSION

    def test_completion_marker(self):
        assert COMPLETION_MARKER == "PHASE_67_CONTEXT_FAILURE_ATTRIBUTION_VERIFIED"

    def test_phase66_anchor(self):
        assert PHASE66_GATE_ANCHOR == "MARKET_MICROSTRUCTURE_NOT_PROMISING"

    def test_phase65_anchor(self):
        assert PHASE65_GATE_ANCHOR == "OVERFIT_RISK"

    def test_phase64b_anchor(self):
        assert PHASE64B_GATE_ANCHOR == "BULLPEN_GRANULAR_FEATURE_NOT_PROMISING"


# ════════════════════════════════════════════════════════════════
# 4. Analysis Thresholds
# ════════════════════════════════════════════════════════════════

class TestThresholds:
    def test_min_coverage_rate(self):
        assert _MIN_COVERAGE_RATE == 0.70

    def test_min_segment_n(self):
        assert _MIN_SEGMENT_N == 20

    def test_min_bucket_n(self):
        assert _MIN_BUCKET_N == 15

    def test_bootstrap_n(self):
        assert _BOOTSTRAP_N == 1000

    def test_heavy_fav_threshold(self):
        assert _HEAVY_FAV_THRESHOLD == 0.70

    def test_phase45_fail_min_fav(self):
        assert _PHASE45_FAIL_MIN_FAV == 0.60


# ════════════════════════════════════════════════════════════════
# 5. Team Mappings
# ════════════════════════════════════════════════════════════════

class TestTeamMappings:
    def test_retro_to_full_count(self):
        assert len(_RETRO_TO_FULL) == 30

    def test_all_retro_ids_map_to_string(self):
        for k, v in _RETRO_TO_FULL.items():
            assert isinstance(k, str) and len(k) == 3
            assert isinstance(v, str) and len(v) > 0

    def test_division_count(self):
        assert len(_TEAM_DIVISION) == 30

    def test_all_division_values_valid(self):
        valid = {"AL_East", "AL_Central", "AL_West", "NL_East", "NL_Central", "NL_West"}
        for div in _TEAM_DIVISION.values():
            assert div in valid

    def test_retro_maps_cover_all_division_teams(self):
        retro_teams = set(_RETRO_TO_FULL.values())
        division_teams = set(_TEAM_DIVISION.keys())
        assert retro_teams == division_teams

    def test_known_retrosheet_ids(self):
        assert _RETRO_TO_FULL["NYA"] == "New York Yankees"
        assert _RETRO_TO_FULL["LAN"] == "Los Angeles Dodgers"
        assert _RETRO_TO_FULL["CHN"] == "Chicago Cubs"
        assert _RETRO_TO_FULL["CHA"] == "Chicago White Sox"
        assert _RETRO_TO_FULL["SLN"] == "St. Louis Cardinals"
        assert _RETRO_TO_FULL["NYN"] == "New York Mets"

    def test_known_division_assignments(self):
        assert _TEAM_DIVISION["New York Yankees"] == "AL_East"
        assert _TEAM_DIVISION["Los Angeles Dodgers"] == "NL_West"
        assert _TEAM_DIVISION["Chicago Cubs"] == "NL_Central"
        assert _TEAM_DIVISION["Athletics"] == "AL_West"


# ════════════════════════════════════════════════════════════════
# 6. Rest Day Computation
# ════════════════════════════════════════════════════════════════

class TestRestDayComputation:
    def test_no_previous_game_returns_3(self):
        assert _rest_days(None, date(2025, 5, 1)) == 3

    def test_b2b_returns_0(self):
        prev = date(2025, 5, 1)
        curr = date(2025, 5, 2)
        assert _rest_days(prev, curr) == 0

    def test_one_day_off_returns_1(self):
        prev = date(2025, 5, 1)
        curr = date(2025, 5, 3)
        assert _rest_days(prev, curr) == 1

    def test_two_days_off_returns_2(self):
        prev = date(2025, 5, 1)
        curr = date(2025, 5, 4)
        assert _rest_days(prev, curr) == 2

    def test_all_star_break_long_rest(self):
        prev = date(2025, 7, 13)
        curr = date(2025, 7, 17)
        assert _rest_days(prev, curr) == 3

    def test_same_day_returns_0(self):
        d = date(2025, 5, 10)
        assert _rest_days(d, d) == 0


# ════════════════════════════════════════════════════════════════
# 7. Math Helpers
# ════════════════════════════════════════════════════════════════

class TestMathHelpers:
    def test_brier_score_perfect_home(self):
        probs = [1.0, 1.0]
        labels = [1, 1]
        assert _brier_score(probs, labels) == 0.0

    def test_brier_score_worst(self):
        probs = [1.0, 0.0]
        labels = [0, 1]
        assert _brier_score(probs, labels) == 1.0

    def test_brier_score_uniform(self):
        probs = [0.5] * 4
        labels = [1, 0, 1, 0]
        assert abs(_brier_score(probs, labels) - 0.25) < 1e-9

    def test_bss_direct_equal(self):
        # model same as reference → BSS = 0
        assert _bss_direct(0.25, 0.25) == 0.0

    def test_bss_direct_model_better(self):
        # model_brier < ref → BSS > 0
        assert _bss_direct(0.20, 0.25) > 0.0

    def test_bss_direct_model_worse(self):
        # model_brier > ref → BSS < 0
        assert _bss_direct(0.30, 0.25) < 0.0

    def test_bss_direct_ref_zero_returns_zero(self):
        assert _bss_direct(0.0, 0.0) == 0.0

    def test_compute_ece_empty(self):
        assert _compute_ece([], []) == 0.0

    def test_compute_ece_perfect_calibration(self):
        # perfectly calibrated: every bin has prob ≈ actual_rate
        probs = [0.5] * 100
        labels = [1 if i < 50 else 0 for i in range(100)]
        ece = _compute_ece(probs, labels)
        assert ece < 0.05


# ════════════════════════════════════════════════════════════════
# 8. Blend Formula
# ════════════════════════════════════════════════════════════════

class TestBlendFormula:
    def test_blend_uses_alpha(self):
        blend = _blend_prob(0.7, 0.6)
        expected = 0.60 * 0.7 + 0.40 * 0.6
        assert abs(blend - expected) < 1e-9

    def test_fav_prob_home_fav(self):
        assert _fav_prob(0.70) == 0.70

    def test_fav_prob_away_fav(self):
        assert _fav_prob(0.30) == 0.70

    def test_fav_prob_even(self):
        assert _fav_prob(0.50) == 0.50


# ════════════════════════════════════════════════════════════════
# 9. Context Bucketing
# ════════════════════════════════════════════════════════════════

def _make_row(**kwargs) -> dict:
    base = {
        "game_date": "2025-05-01",
        "home_team": "New York Yankees",
        "away_team": "Boston Red Sox",
        "model_home_prob": 0.60,
        "market_home_prob_no_vig": 0.58,
        "home_win": 1,
        "_blend": 0.60 * 0.60 + 0.40 * 0.58,
        "_fav_is_home": True,
        "_fav_prob": 0.60 * 0.60 + 0.40 * 0.58,
        "_fav_win": 1,
        "park_run_factor": 1.00,
        "season_game_index": 0.40,
        "home_rest_days": 2,
        "away_rest_days": 2,
        "away_consec_road_games": 3,
        "day_night": "N",
        "day_of_week": "Fri",
        "double_header": 0,
        "home_season_game_num": 30,
        "away_season_game_num": 28,
        "divisional_matchup": True,
        "same_league": True,
        "_ctx_aligned": True,
    }
    base.update(kwargs)
    if "_blend" not in kwargs:
        blend = _blend_prob(base["model_home_prob"], base["market_home_prob_no_vig"])
        base["_blend"] = blend
        base["_fav_is_home"] = blend >= 0.5
        base["_fav_prob"] = _fav_prob(blend)
        base["_fav_win"] = base["home_win"] if blend >= 0.5 else 1 - base["home_win"]
    return base


class TestContextBucketing:
    def test_home_rest_b2b(self):
        r = _make_row(home_rest_days=0)
        assert _get_context_bucket(r, "home_rest_days_bucket") == "b2b_0d"

    def test_home_rest_1d(self):
        r = _make_row(home_rest_days=1)
        assert _get_context_bucket(r, "home_rest_days_bucket") == "rest_1d"

    def test_home_rest_4plus(self):
        r = _make_row(home_rest_days=5)
        assert _get_context_bucket(r, "home_rest_days_bucket") == "rest_4plus"

    def test_away_rest_b2b(self):
        r = _make_row(away_rest_days=0)
        assert _get_context_bucket(r, "away_rest_days_bucket") == "b2b_0d"

    def test_rest_imbalance_home_2plus(self):
        r = _make_row(home_rest_days=4, away_rest_days=1)
        assert _get_context_bucket(r, "rest_imbalance_bucket") == "home_2plus_more"

    def test_rest_imbalance_equal(self):
        r = _make_row(home_rest_days=2, away_rest_days=2)
        assert _get_context_bucket(r, "rest_imbalance_bucket") == "equal_rest"

    def test_rest_imbalance_away_2plus(self):
        r = _make_row(home_rest_days=1, away_rest_days=4)
        assert _get_context_bucket(r, "rest_imbalance_bucket") == "away_2plus_more"

    def test_back_to_back_home(self):
        r = _make_row(home_rest_days=0, away_rest_days=2)
        assert _get_context_bucket(r, "back_to_back_bucket") == "home_b2b"

    def test_back_to_back_away(self):
        r = _make_row(home_rest_days=2, away_rest_days=0)
        assert _get_context_bucket(r, "back_to_back_bucket") == "away_b2b"

    def test_back_to_back_both(self):
        r = _make_row(home_rest_days=0, away_rest_days=0)
        assert _get_context_bucket(r, "back_to_back_bucket") == "both_b2b"

    def test_back_to_back_neither(self):
        r = _make_row(home_rest_days=2, away_rest_days=2)
        assert _get_context_bucket(r, "back_to_back_bucket") == "neither_b2b"

    def test_day_night_day(self):
        r = _make_row(day_night="D")
        assert _get_context_bucket(r, "day_night_bucket") == "day_game"

    def test_day_night_night(self):
        r = _make_row(day_night="N")
        assert _get_context_bucket(r, "day_night_bucket") == "night_game"

    def test_day_night_none(self):
        r = _make_row(day_night=None)
        assert _get_context_bucket(r, "day_night_bucket") is None

    def test_day_of_week_weekend(self):
        r = _make_row(day_of_week="Sat")
        assert _get_context_bucket(r, "day_of_week_bucket") == "weekend"
        r2 = _make_row(day_of_week="Sun")
        assert _get_context_bucket(r2, "day_of_week_bucket") == "weekend"

    def test_day_of_week_monday(self):
        r = _make_row(day_of_week="Mon")
        assert _get_context_bucket(r, "day_of_week_bucket") == "monday"

    def test_day_of_week_friday(self):
        r = _make_row(day_of_week="Fri")
        assert _get_context_bucket(r, "day_of_week_bucket") == "friday"

    def test_day_of_week_midweek(self):
        r = _make_row(day_of_week="Wed")
        assert _get_context_bucket(r, "day_of_week_bucket") == "midweek"

    def test_double_header_solo(self):
        r = _make_row(double_header=0)
        assert _get_context_bucket(r, "double_header_bucket") == "single_game"

    def test_double_header_game1(self):
        r = _make_row(double_header=1)
        assert _get_context_bucket(r, "double_header_bucket") == "dh_game1"

    def test_double_header_game2(self):
        r = _make_row(double_header=2)
        assert _get_context_bucket(r, "double_header_bucket") == "dh_game2"

    def test_divisional_same_div(self):
        r = _make_row(divisional_matchup=True, same_league=True)
        assert _get_context_bucket(r, "divisional_matchup_bucket") == "same_division"

    def test_divisional_same_league_diff_div(self):
        r = _make_row(divisional_matchup=False, same_league=True)
        assert _get_context_bucket(r, "divisional_matchup_bucket") == "same_league_diff_div"

    def test_divisional_interleague(self):
        r = _make_row(divisional_matchup=False, same_league=False)
        assert _get_context_bucket(r, "divisional_matchup_bucket") == "interleague"

    def test_fav_side_home(self):
        r = _make_row(model_home_prob=0.75, market_home_prob_no_vig=0.72)
        r["_fav_is_home"] = True
        assert _get_context_bucket(r, "fav_side_bucket") == "home_fav"

    def test_fav_side_away(self):
        r = _make_row(model_home_prob=0.35, market_home_prob_no_vig=0.38)
        r["_fav_is_home"] = False
        assert _get_context_bucket(r, "fav_side_bucket") == "away_fav"

    def test_park_pitcher(self):
        r = _make_row(park_run_factor=0.90)
        assert _get_context_bucket(r, "park_run_env_bucket") == "pitcher_park"

    def test_park_neutral(self):
        r = _make_row(park_run_factor=1.00)
        assert _get_context_bucket(r, "park_run_env_bucket") == "neutral_park"

    def test_park_hitter(self):
        r = _make_row(park_run_factor=1.10)
        assert _get_context_bucket(r, "park_run_env_bucket") == "hitter_park"

    def test_park_none(self):
        r = _make_row(park_run_factor=None)
        assert _get_context_bucket(r, "park_run_env_bucket") is None

    def test_season_early(self):
        r = _make_row(season_game_index=0.20)
        assert _get_context_bucket(r, "season_phase_bucket") == "early_season"

    def test_season_mid(self):
        r = _make_row(season_game_index=0.50)
        assert _get_context_bucket(r, "season_phase_bucket") == "mid_season"

    def test_season_late(self):
        r = _make_row(season_game_index=0.80)
        assert _get_context_bucket(r, "season_phase_bucket") == "late_season"

    def test_away_consec_short(self):
        r = _make_row(away_consec_road_games=2)
        assert _get_context_bucket(r, "away_consec_road_bucket") == "road_trip_1_3"

    def test_away_consec_mid(self):
        r = _make_row(away_consec_road_games=5)
        assert _get_context_bucket(r, "away_consec_road_bucket") == "road_trip_4_6"

    def test_away_consec_long(self):
        r = _make_row(away_consec_road_games=9)
        assert _get_context_bucket(r, "away_consec_road_bucket") == "road_trip_7plus"

    def test_unknown_dim_returns_none(self):
        r = _make_row()
        assert _get_context_bucket(r, "nonexistent_dim") is None


# ════════════════════════════════════════════════════════════════
# 10. Segment Extraction
# ════════════════════════════════════════════════════════════════

def _make_rows_varied(n: int = 50) -> list[dict]:
    rng = random.Random(7)
    rows = []
    for i in range(n):
        mp = rng.uniform(0.45, 0.85)
        mk = rng.uniform(0.45, 0.80)
        hw = 1 if rng.random() < mp else 0
        blend = _blend_prob(mp, mk)
        fav_is_home = blend >= 0.5
        fav_p = _fav_prob(blend)
        fav_win = hw if fav_is_home else 1 - hw
        rows.append(_make_row(
            model_home_prob=mp,
            market_home_prob_no_vig=mk,
            home_win=hw,
            _blend=blend,
            _fav_is_home=fav_is_home,
            _fav_prob=fav_p,
            _fav_win=fav_win,
        ))
    return rows


class TestSegmentExtraction:
    def test_all_returns_all(self):
        rows = _make_rows_varied(30)
        assert len(_extract_segment(rows, "all")) == 30

    def test_heavy_fav_subset(self):
        rows = _make_rows_varied(200)
        hf = _extract_segment(rows, "heavy_favorite")
        assert all(r["_fav_prob"] >= 0.70 for r in hf)

    def test_high_conf_subset_of_heavy(self):
        rows = _make_rows_varied(300)
        hf = _extract_segment(rows, "heavy_favorite")
        hc = _extract_segment(rows, "high_confidence")
        assert len(hc) <= len(hf)

    def test_extreme_fav_subset(self):
        rows = _make_rows_varied(300)
        xt = _extract_segment(rows, "extreme_favorite")
        assert all(r["_fav_prob"] >= 0.80 for r in xt)

    def test_phase45_failure_definition(self):
        rows = _make_rows_varied(300)
        p45 = _extract_segment(rows, "phase45_failure")
        assert all(r["_fav_prob"] >= 0.60 and r["_fav_win"] == 0 for r in p45)

    def test_unknown_segment_returns_all(self):
        rows = _make_rows_varied(20)
        assert len(_extract_segment(rows, "unknown")) == 20


# ════════════════════════════════════════════════════════════════
# 11. Segment Metrics
# ════════════════════════════════════════════════════════════════

class TestSegmentMetrics:
    def test_empty_returns_defaults(self):
        m = _compute_segment_metrics([])
        assert m.n == 0
        assert m.blend_bss_vs_market == 0.0

    def test_perfect_predictions(self):
        rows = [_make_row(model_home_prob=1.0, market_home_prob_no_vig=0.8, home_win=1)]
        rows[0]["_blend"] = _blend_prob(1.0, 0.8)
        m = _compute_segment_metrics(rows)
        assert m.model_brier == 0.0

    def test_n_matches_row_count(self):
        rows = _make_rows_varied(40)
        m = _compute_segment_metrics(rows)
        assert m.n == 40

    def test_bss_direct_formula(self):
        rows = _make_rows_varied(100)
        m = _compute_segment_metrics(rows)
        # Recompute from stored (rounded) brier values — allow rounding error
        expected = _bss_direct(m.blend_brier, m.market_brier)
        assert abs(m.blend_bss_vs_market - expected) < 1e-3

    def test_fav_win_rate_in_range(self):
        rows = _make_rows_varied(100)
        m = _compute_segment_metrics(rows)
        assert 0.0 <= m.fav_win_rate <= 1.0

    def test_ece_non_negative(self):
        rows = _make_rows_varied(100)
        m = _compute_segment_metrics(rows)
        assert m.ece_blend >= 0.0


# ════════════════════════════════════════════════════════════════
# 12. Bootstrap
# ════════════════════════════════════════════════════════════════

class TestBootstrap:
    def test_too_few_rows_returns_not_significant(self):
        rows = _make_rows_varied(5)
        result = _bootstrap_bss_vs_market(rows, n_boot=100)
        assert result.significant is False
        assert result.ci_lower == 0.0
        assert result.ci_upper == 0.0

    def test_n_boot_zero_returns_not_significant(self):
        rows = _make_rows_varied(50)
        result = _bootstrap_bss_vs_market(rows, n_boot=0)
        assert result.significant is False

    def test_large_sample_returns_ci(self):
        rows = _make_rows_varied(200)
        result = _bootstrap_bss_vs_market(rows, n_boot=200)
        assert result.n == 200
        assert result.ci_lower <= result.ci_upper

    def test_prob_positive_in_range(self):
        rows = _make_rows_varied(100)
        result = _bootstrap_bss_vs_market(rows, n_boot=200)
        assert 0.0 <= result.prob_positive <= 1.0

    def test_significant_requires_ci_lower_positive(self):
        rows = _make_rows_varied(100)
        result = _bootstrap_bss_vs_market(rows, n_boot=200)
        if result.significant:
            assert result.ci_lower > 0


# ════════════════════════════════════════════════════════════════
# 13. Attribution Dimension
# ════════════════════════════════════════════════════════════════

class TestAttributionDimension:
    def setup_method(self):
        self.rows = _make_rows_varied(200)

    def test_returns_list_of_buckets(self):
        buckets = _compute_attribution_dimension(self.rows, "day_night_bucket", "all", n_boot=0)
        assert isinstance(buckets, list)
        assert all(isinstance(b, AttributionBucket) for b in buckets)

    def test_bucket_labels_are_strings(self):
        buckets = _compute_attribution_dimension(self.rows, "fav_side_bucket", "all", n_boot=0)
        for b in buckets:
            assert isinstance(b.bucket_label, str)

    def test_bucket_n_positive(self):
        buckets = _compute_attribution_dimension(self.rows, "fav_side_bucket", "all", n_boot=0)
        for b in buckets:
            assert b.n > 0

    def test_dim_name_preserved(self):
        buckets = _compute_attribution_dimension(self.rows, "park_run_env_bucket", "all", n_boot=0)
        for b in buckets:
            assert b.dim == "park_run_env_bucket"

    def test_total_rows_in_buckets_le_input(self):
        buckets = _compute_attribution_dimension(self.rows, "day_of_week_bucket", "all", n_boot=0)
        total = sum(b.n for b in buckets)
        assert total <= len(self.rows)


# ════════════════════════════════════════════════════════════════
# 14. Negative Control
# ════════════════════════════════════════════════════════════════

class TestNegativeControl:
    def test_returns_negative_control_type(self):
        rows = _make_rows_varied(100)
        nc = _compute_negative_control(rows, "day_night_bucket", "all")
        assert isinstance(nc, NegativeControl)

    def test_too_few_rows_no_overfit(self):
        rows = _make_rows_varied(3)
        nc = _compute_negative_control(rows, "day_night_bucket", "all")
        assert nc.overfit_risk is False

    def test_overfit_risk_is_bool(self):
        rows = _make_rows_varied(100)
        nc = _compute_negative_control(rows, "fav_side_bucket", "all")
        assert isinstance(nc.overfit_risk, bool)

    def test_shuffled_std_non_negative(self):
        rows = _make_rows_varied(100)
        nc = _compute_negative_control(rows, "day_night_bucket", "all")
        assert nc.shuffled_std_delta >= 0

    def test_dim_preserved(self):
        rows = _make_rows_varied(50)
        nc = _compute_negative_control(rows, "season_phase_bucket", "all")
        assert nc.dim == "season_phase_bucket"


# ════════════════════════════════════════════════════════════════
# 15. OOF Validation
# ════════════════════════════════════════════════════════════════

class TestOOFValidation:
    def _make_dated_rows(self, n_per_month: int = 60) -> list[dict]:
        months = ["2025-05", "2025-06", "2025-07", "2025-08", "2025-09"]
        rows = []
        rng = random.Random(11)
        for i, month in enumerate(months):
            for j in range(n_per_month):
                r = _make_rows_varied(1)[0]
                r["game_date"] = f"{month}-{(j % 28) + 1:02d}"
                rows.append(r)
        return rows

    def test_returns_oof_result(self):
        rows = self._make_dated_rows()
        oof = _compute_oof(rows, "day_night_bucket", "all")
        assert isinstance(oof, OOFResult)

    def test_n_folds_matches_months(self):
        rows = self._make_dated_rows()
        oof = _compute_oof(rows, "day_night_bucket", "all")
        assert oof.n_folds == len(oof.fold_months)

    def test_fold_bss_deltas_length_matches(self):
        rows = self._make_dated_rows()
        oof = _compute_oof(rows, "fav_side_bucket", "all")
        assert len(oof.fold_bss_deltas) == oof.n_folds

    def test_too_few_rows_returns_empty(self):
        rows = _make_rows_varied(5)
        oof = _compute_oof(rows, "day_night_bucket", "all")
        assert oof.n_folds == 0

    def test_consistent_sign_when_all_positive(self):
        rows = self._make_dated_rows()
        oof = _compute_oof(rows, "day_night_bucket", "all")
        if oof.oof_consistent_sign:
            assert all(d > 0 for d in oof.fold_bss_deltas)


# ════════════════════════════════════════════════════════════════
# 16. Gate Decision Logic
# ════════════════════════════════════════════════════════════════

def _make_alignment(n_aligned: int = 2000, n_pred: int = 2000) -> ContextAlignment:
    cov = n_aligned / n_pred
    return ContextAlignment(
        n_predictions=n_pred,
        n_gl_records=2430,
        n_aligned=n_aligned,
        n_unaligned=n_pred - n_aligned,
        coverage=cov,
        coverage_sufficient=cov >= 0.70,
        sample_audit_hash="sha256:abc",
    )


def _make_all_metrics(bss: float = 0.001) -> SegmentMetrics:
    return SegmentMetrics(
        n=2000, model_brier=0.245, market_brier=0.244, blend_brier=0.244 - bss * 0.244,
        blend_bss_vs_market=bss, model_bss_vs_market=bss,
        fav_win_rate=0.55, win_rate=0.55, ece_blend=0.02,
    )


def _no_sig_buckets() -> list[AttributionBucket]:
    return [
        AttributionBucket(
            dim="day_night_bucket", bucket_label="night_game", n=1600,
            segment_name="all",
            metrics=_make_all_metrics(-0.002),
            bootstrap=BootstrapResult(
                n=1600, n_boot=1000, observed_delta=-0.002,
                ci_lower=-0.01, ci_upper=0.005,
                prob_positive=0.4, significant=False,
            ),
        )
    ]


def _pos_sig_bucket() -> list[AttributionBucket]:
    return [
        AttributionBucket(
            dim="day_night_bucket", bucket_label="day_game", n=400,
            segment_name="all",
            metrics=_make_all_metrics(0.020),
            bootstrap=BootstrapResult(
                n=400, n_boot=1000, observed_delta=0.020,
                ci_lower=0.005, ci_upper=0.035,
                prob_positive=0.97, significant=True,
            ),
        )
    ]


def _no_overfit_nc() -> list[NegativeControl]:
    return [NegativeControl(
        dim="day_night_bucket", segment="all",
        real_blend_bss_delta=0.01,
        shuffled_mean_delta=0.005,
        shuffled_std_delta=0.002,
        null_rejected=False,
        overfit_risk=False,
    )]


def _overfit_nc() -> list[NegativeControl]:
    return [NegativeControl(
        dim="day_night_bucket", segment="all",
        real_blend_bss_delta=0.001,
        shuffled_mean_delta=0.005,
        shuffled_std_delta=0.003,
        null_rejected=False,
        overfit_risk=True,
    )]


def _pos_oof() -> list[OOFResult]:
    return [OOFResult(
        dim="day_night_bucket", segment="all",
        n_folds=5, fold_months=["2025-05", "2025-06", "2025-07", "2025-08", "2025-09"],
        fold_bss_deltas=[0.015, 0.018, 0.012, 0.020, 0.011],
        fold_ns=[300, 350, 320, 400, 280],
        oof_mean_delta=0.0152,
        oof_consistent_sign=True,
        oof_significant=True,
    )]


def _neg_oof() -> list[OOFResult]:
    return [OOFResult(
        dim="day_night_bucket", segment="all",
        n_folds=5, fold_months=["2025-05", "2025-06", "2025-07", "2025-08", "2025-09"],
        fold_bss_deltas=[-0.001, 0.003, -0.002, 0.001, -0.003],
        fold_ns=[300, 350, 320, 400, 280],
        oof_mean_delta=-0.0004,
        oof_consistent_sign=False,
        oof_significant=False,
    )]


class TestGateDecisionLogic:
    def test_insufficient_alignment_returns_data_limited(self):
        align = _make_alignment(n_aligned=5, n_pred=2000)
        gate, *_ = _decide_gate(align, _make_all_metrics(), _no_sig_buckets(), _no_overfit_nc(), _neg_oof())
        assert gate == DATA_LIMITED_GATE

    def test_overfit_risk_gate(self):
        gate, *_ = _decide_gate(
            _make_alignment(), _make_all_metrics(),
            _no_sig_buckets(), _overfit_nc(), _neg_oof(),
        )
        assert gate == OVERFIT_RISK

    def test_promising_with_pos_boot_and_oof(self):
        gate, *_ = _decide_gate(
            _make_alignment(), _make_all_metrics(),
            _pos_sig_bucket(), _no_overfit_nc(), _pos_oof(),
        )
        assert gate == CONTEXT_FEATURE_PROMISING

    def test_diagnostic_only_signal_pos_boot_neg_oof(self):
        gate, *_ = _decide_gate(
            _make_alignment(), _make_all_metrics(),
            _pos_sig_bucket(), _no_overfit_nc(), _neg_oof(),
        )
        assert gate == DIAGNOSTIC_ONLY_SIGNAL

    def test_data_limited_no_signal_critical_dims_missing(self):
        # No positive signal + critical DATA_LIMITED dims exist
        gate, *_ = _decide_gate(
            _make_alignment(), _make_all_metrics(),
            _no_sig_buckets(), _no_overfit_nc(), _neg_oof(),
        )
        assert gate == DATA_LIMITED_GATE

    def test_gate_returns_7_tuple(self):
        result = _decide_gate(
            _make_alignment(), _make_all_metrics(),
            _no_sig_buckets(), _no_overfit_nc(), _neg_oof(),
        )
        assert len(result) == 7

    def test_gate_is_in_valid_set(self):
        gate, *_ = _decide_gate(
            _make_alignment(), _make_all_metrics(),
            _no_sig_buckets(), _no_overfit_nc(), _neg_oof(),
        )
        assert gate in _VALID_GATES

    def test_worth_phase68_true_only_when_promising(self):
        _, _, _, _, _, _, worth = _decide_gate(
            _make_alignment(), _make_all_metrics(),
            _pos_sig_bucket(), _no_overfit_nc(), _pos_oof(),
        )
        assert worth is True

    def test_worth_phase68_false_when_data_limited(self):
        _, _, _, _, _, _, worth = _decide_gate(
            _make_alignment(), _make_all_metrics(),
            _no_sig_buckets(), _no_overfit_nc(), _neg_oof(),
        )
        assert worth is False


# ════════════════════════════════════════════════════════════════
# 17. GL2025 Parsing (real file)
# ════════════════════════════════════════════════════════════════

@pytest.mark.skipif(not _GL2025_PATH.exists(), reason="gl2025.txt not available")
class TestGL2025Parsing:
    @pytest.fixture(scope="class")
    def gl_data(self):
        lookup, audit_hash, n = _load_gl2025(_GL2025_PATH)
        return lookup, audit_hash, n

    def test_n_records_correct(self, gl_data):
        _, _, n = gl_data
        assert n == 2430

    def test_lookup_has_entries(self, gl_data):
        lookup, _, _ = gl_data
        assert len(lookup) > 2000

    def test_audit_hash_starts_sha256(self, gl_data):
        _, audit_hash, _ = gl_data
        assert audit_hash.startswith("sha256:")

    def test_context_record_has_valid_day_night(self, gl_data):
        lookup, _, _ = gl_data
        for rec in list(lookup.values())[:50]:
            assert rec.day_night in ("D", "N")

    def test_rest_days_non_negative(self, gl_data):
        lookup, _, _ = gl_data
        for rec in list(lookup.values())[:200]:
            assert rec.home_rest_days >= 0
            assert rec.away_rest_days >= 0

    def test_away_consec_road_positive(self, gl_data):
        lookup, _, _ = gl_data
        for rec in list(lookup.values())[:200]:
            assert rec.away_consec_road_games >= 1

    def test_divisional_matchup_is_bool(self, gl_data):
        lookup, _, _ = gl_data
        for rec in list(lookup.values())[:50]:
            assert isinstance(rec.divisional_matchup, bool)

    def test_first_game_has_default_rest(self, gl_data):
        lookup, _, _ = gl_data
        # First game of season (2025-03-18) should have rest_days=3 (first game default)
        first_day = [rec for rec in lookup.values() if rec.game_date == "2025-03-18"]
        for rec in first_day:
            assert rec.home_rest_days == 3
            assert rec.away_rest_days == 3


# ════════════════════════════════════════════════════════════════
# 18. End-to-End with Real Data
# ════════════════════════════════════════════════════════════════

@pytest.mark.skipif(not _has_data(), reason="Real data files not available")
class TestEndToEnd:
    @pytest.fixture(scope="class")
    def result(self):
        return run_phase67_context_failure_attribution(
            predictions_path=_PREDICTIONS_PATH,
            gl2025_path=_GL2025_PATH,
            n_boot=_BOOTSTRAP_N,
        )

    def test_result_is_phase67_result(self, result):
        assert isinstance(result, Phase67Result)

    def test_safety_constants_preserved(self, result):
        assert result.candidate_patch_created is False
        assert result.production_modified is False
        assert result.diagnostic_only is True

    def test_alpha_unchanged(self, result):
        assert abs(result.alpha - 0.40) < 1e-9

    def test_alpha_modified_false(self, result):
        assert result.alpha_modified is False

    def test_completion_marker(self, result):
        assert result.completion_marker == COMPLETION_MARKER

    def test_phase_version(self, result):
        assert result.phase_version == PHASE_VERSION

    def test_phase66_gate_anchor(self, result):
        assert result.phase66_gate_anchor == "MARKET_MICROSTRUCTURE_NOT_PROMISING"

    def test_phase65_gate_anchor(self, result):
        assert result.phase65_gate_anchor == "OVERFIT_RISK"

    def test_n_predictions_correct(self, result):
        assert result.segment_n_all == 2025

    def test_context_coverage_sufficient(self, result):
        assert result.context_alignment.coverage >= _MIN_COVERAGE_RATE

    def test_alignment_is_100_pct(self, result):
        assert result.context_alignment.n_aligned == 2025

    def test_segment_n_heavy_fav(self, result):
        assert result.segment_n_heavy_fav >= 20

    def test_segment_n_high_conf(self, result):
        assert result.segment_n_high_conf >= 1

    def test_segment_n_phase45_failure(self, result):
        assert result.segment_n_phase45_failure >= 50

    def test_all_metrics_model_brier_reasonable(self, result):
        m = result.all_metrics
        assert 0.20 <= m.model_brier <= 0.30

    def test_all_metrics_market_brier_reasonable(self, result):
        assert 0.20 <= result.all_metrics.market_brier <= 0.30

    def test_attribution_buckets_non_empty(self, result):
        assert len(result.attribution_buckets) > 0

    def test_attribution_buckets_cover_available_dims(self, result):
        dims_seen = {b.dim for b in result.attribution_buckets}
        # Should have buckets for most available dimensions
        assert len(dims_seen) >= len(_AVAILABLE_DIMENSIONS) // 2

    def test_negative_controls_count(self, result):
        assert len(result.negative_controls) == len(_AVAILABLE_DIMENSIONS)

    def test_oof_results_count(self, result):
        assert len(result.oof_results) == len(_AVAILABLE_DIMENSIONS)

    def test_gate_is_valid(self, result):
        assert result.gate in _VALID_GATES

    def test_gate_rationale_non_empty(self, result):
        assert len(result.gate_rationale) > 10

    def test_next_step_non_empty(self, result):
        assert len(result.next_step) > 5

    def test_data_limited_dimensions_preserved(self, result):
        assert result.data_limited_dimensions == _DATA_LIMITED_DIMENSIONS

    def test_data_limited_fields_preserved(self, result):
        assert result.data_limited_fields == _DATA_LIMITED_FIELDS

    def test_available_dimensions_preserved(self, result):
        assert result.available_dimensions == _AVAILABLE_DIMENSIONS

    def test_result_is_json_serializable(self, result):
        d = _to_dict(result)
        s = json.dumps(d)
        assert len(s) > 100

    def test_timestamp_utc(self, result):
        assert result.run_timestamp_utc.endswith("Z")

    def test_any_boot_sig_is_bool(self, result):
        assert isinstance(result.any_bootstrap_significant, bool)

    def test_any_oof_promising_is_bool(self, result):
        assert isinstance(result.any_oof_promising, bool)

    def test_any_overfit_risk_is_bool(self, result):
        assert isinstance(result.any_overfit_risk, bool)

    def test_save_and_reload(self, result, tmp_path):
        out = tmp_path / "p67.json"
        save_result(result, out)
        with open(out) as f:
            d = json.load(f)
        assert d["gate"] == result.gate
        assert d["completion_marker"] == COMPLETION_MARKER


# ════════════════════════════════════════════════════════════════
# 19. Backward Compatibility
# ════════════════════════════════════════════════════════════════

class TestBackwardCompatibility:
    def test_phase66_report_exists(self):
        p66 = _REPO / "reports/phase66_market_microstructure_failure_attribution_20260506.json"
        assert p66.exists(), "Phase 66 report must exist"

    def test_phase66_gate_matches_anchor(self):
        p66 = _REPO / "reports/phase66_market_microstructure_failure_attribution_20260506.json"
        if not p66.exists():
            pytest.skip("Phase 66 report not found")
        with open(p66) as f:
            d = json.load(f)
        assert d["gate"] == PHASE66_GATE_ANCHOR

    def test_phase66_module_exists(self):
        p = _REPO / "orchestrator/phase66_market_microstructure_failure_attribution.py"
        assert p.exists()

    def test_phase65_module_exists(self):
        p = _REPO / "orchestrator"
        # Check any phase65 file
        files = list(p.glob("phase65*.py"))
        assert len(files) >= 1

    def test_phase64b_module_exists(self):
        files = list((_REPO / "orchestrator").glob("phase64b*.py"))
        assert len(files) >= 1

    def test_alpha_never_changed(self):
        assert ALPHA == 0.40

    def test_candidate_patch_never_set(self):
        assert CANDIDATE_PATCH_CREATED is False

    def test_production_never_modified(self):
        assert PRODUCTION_MODIFIED is False

    def test_phase67_report_completeness(self):
        """If Phase 67 report exists, verify required keys."""
        p67 = _REPO / "reports/phase67_context_failure_attribution_20260506.json"
        if not p67.exists():
            pytest.skip("Phase 67 report not yet generated")
        with open(p67) as f:
            d = json.load(f)
        required_keys = [
            "gate", "completion_marker", "phase_version",
            "context_alignment", "all_metrics", "heavy_fav_metrics",
            "attribution_buckets", "negative_controls", "oof_results",
            "data_limited_dimensions",
        ]
        for key in required_keys:
            assert key in d, f"Missing key: {key}"
        assert d["completion_marker"] == COMPLETION_MARKER
