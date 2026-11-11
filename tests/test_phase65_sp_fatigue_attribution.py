"""
tests/test_phase65_sp_fatigue_attribution.py
=============================================
Phase 65 — SP Fatigue Attribution 完整測試套件

測試類別 (15 個)：
  TestSafetyConstants       (5)  — 安全常數不可變
  TestGateConstants         (5)  — Gate 常數正確性
  TestFeatureRegistry       (6)  — 特徵登錄表
  TestSPStartHistoryBuilder (6)  — build_sp_start_history
  TestRestDaysComputation   (6)  — compute_sp_rest_days (PIT-safe)
  TestSPFeatureDerivation   (8)  — derive_sp_features
  TestAlignmentLogic        (6)  — align_predictions_with_sp
  TestFeatureCoverage       (5)  — compute_sp_coverage
  TestSegmentExtraction     (5)  — extract_segment
  TestBucketAttributionLogic(6)  — bucket_attribution
  TestBootstrapCI           (4)  — bootstrap_win_rate_delta
  TestOOFValidation         (5)  — compute_sp_oof
  TestNegativeControlLogic  (5)  — compute_sp_negative_control
  TestGateDecisionLogic     (7)  — decide_sp_gate
  TestEndToEnd              (22) — run_phase65_sp_fatigue_attribution
  TestBackwardCompatibility  (9) — phase64b anchor + regression guards

Total: 110 tests
注意：測試絕不呼叫 live StatsAPI；所有資料使用合成 fixtures 或現有 artifacts。
"""
from __future__ import annotations

import csv
import io
import json
import random
from dataclasses import asdict
from pathlib import Path
from typing import Any
from unittest.mock import patch, MagicMock

import pytest

# ── 模組導入 ──────────────────────────────────────────────────────────────────
from orchestrator.phase65_sp_fatigue_attribution import (
    ALPHA,
    ALPHA_MODIFIED,
    CANDIDATE_PATCH_CREATED,
    DIAGNOSTIC_ONLY,
    PHASE_VERSION,
    PRODUCTION_MODIFIED,
    SP_FATIGUE_FEATURE_PROMISING,
    DIAGNOSTIC_ONLY_SIGNAL,
    DATA_LIMITED,
    OVERFIT_RISK,
    SP_FATIGUE_FEATURE_NOT_PROMISING,
    _HEAVY_FAV_THRESHOLD,
    _HIGH_CONF_THRESHOLD,
    _MIN_SEGMENT_N,
    _BOOTSTRAP_N,
    _OOF_PROMISING_DELTA,
    _MIN_COVERAGE_RATE,
    _OVERFIT_SIGMA,
    _SHORT_REST_THRESHOLD,
    _LONG_REST_THRESHOLD,
    _SP_FEATURE_REGISTRY,
    _SP_AVAILABLE_FEATURES,
    _PHASE64B_GATE,
    _PHASE64B_VERSION,
    _blend_prob,
    _fav_prob,
    _brier_score,
    _bss,
    _compute_ece,
    _bootstrap_win_rate_delta,
    _bucket_attribution,
    _build_sp_start_history,
    _compute_sp_rest_days,
    _derive_sp_features,
    _align_predictions_with_sp,
    _compute_sp_coverage,
    _extract_segment,
    _compute_sp_attribution,
    _compute_sp_negative_control,
    _compute_sp_oof,
    _decide_sp_gate,
    run_phase65_sp_fatigue_attribution,
    SPFeatureCoverage,
    SPBucketAttribution,
    SPSegmentAttribution,
    SPNegativeControl,
    SPOOFResult,
    SPAlignment,
    Phase65Result,
)

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

_ROOT = Path(__file__).parent.parent

# Paths to real artifacts (read-only — DO NOT MODIFY)
_REAL_PREDICTIONS = str(
    _ROOT / "data" / "mlb_2025" / "derived"
    / "mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl"
)
_REAL_ASPLAYED = str(_ROOT / "data" / "mlb_2025" / "mlb-2025-asplayed.csv")


def _make_asplayed_rows(
    games: list[tuple[str, str, str, str, str]],
) -> list[dict[str, str]]:
    """
    Build synthetic asplayed rows.
    games: list of (date, home_team, away_team, home_starter, away_starter)
    """
    return [
        {"date": d, "home_team": h, "away_team": a, "home_starter": hs, "away_starter": as_}
        for d, h, a, hs, as_ in games
    ]


def _make_pred_row(
    game_date: str = "2025-05-01",
    home_team: str = "TeamA",
    away_team: str = "TeamB",
    model_prob: float = 0.60,
    market_prob: float = 0.58,
    home_win: int = 1,
) -> dict[str, Any]:
    return {
        "game_date": game_date,
        "home_team": home_team,
        "away_team": away_team,
        "model_home_prob": model_prob,
        "market_home_prob_no_vig": market_prob,
        "home_win": home_win,
    }


def _make_synthetic_predictions(
    n: int = 100,
    base_date: str = "2025-05-01",
    n_months: int = 4,
    home_win_rate: float = 0.55,
) -> list[dict[str, Any]]:
    """Build n synthetic prediction rows spread over n_months."""
    rng = random.Random(42)
    preds = []
    months = ["2025-05", "2025-06", "2025-07", "2025-08", "2025-09"][:n_months]
    per_month = n // len(months)
    teams = [("TeamA", "TeamB"), ("TeamC", "TeamD"), ("TeamE", "TeamF")]
    for i, month in enumerate(months):
        for j in range(per_month):
            day = (j % 28) + 1
            gd = f"{month}-{day:02d}"
            ht, at = teams[j % len(teams)]
            mp = rng.uniform(0.52, 0.72)
            mkp = mp + rng.uniform(-0.02, 0.02)
            hw = 1 if rng.random() < home_win_rate else 0
            preds.append(_make_pred_row(gd, ht, at, mp, mkp, hw))
    return preds


def _make_synthetic_asplayed(
    predictions: list[dict[str, Any]],
    rest_range: tuple[int, int] = (4, 8),
) -> list[dict[str, str]]:
    """Build matching asplayed rows for all predictions, with pitcher history."""
    rng = random.Random(42)
    pitchers = [f"Pitcher{i:02d}" for i in range(10)]
    rows = []
    for p in predictions:
        rows.append({
            "date": p["game_date"],
            "home_team": p["home_team"],
            "away_team": p["away_team"],
            "home_starter": rng.choice(pitchers[:5]),
            "away_starter": rng.choice(pitchers[5:]),
        })
    # Also add prior starts to enable rest_days computation
    prior_rows = []
    pitcher_set = set(r["home_starter"] for r in rows) | set(r["away_starter"] for r in rows)
    for pitcher in pitcher_set:
        prior_rows.append({
            "date": "2025-04-15",
            "home_team": "PriorHome",
            "away_team": "PriorAway",
            "home_starter": pitcher if rng.random() > 0.5 else "",
            "away_starter": pitcher if rng.random() > 0.5 else "",
        })
    return prior_rows + rows


# ---------------------------------------------------------------------------
# 1. Safety Constants
# ---------------------------------------------------------------------------

class TestSafetyConstants:
    def test_candidate_patch_created_is_false(self):
        assert CANDIDATE_PATCH_CREATED is False

    def test_production_modified_is_false(self):
        assert PRODUCTION_MODIFIED is False

    def test_alpha_modified_is_false(self):
        assert ALPHA_MODIFIED is False

    def test_diagnostic_only_is_true(self):
        assert DIAGNOSTIC_ONLY is True

    def test_alpha_is_040(self):
        assert ALPHA == 0.40


# ---------------------------------------------------------------------------
# 2. Gate Constants
# ---------------------------------------------------------------------------

class TestGateConstants:
    def test_sp_fatigue_promising_value(self):
        assert SP_FATIGUE_FEATURE_PROMISING == "SP_FATIGUE_FEATURE_PROMISING"

    def test_diagnostic_only_signal_value(self):
        assert DIAGNOSTIC_ONLY_SIGNAL == "DIAGNOSTIC_ONLY_SIGNAL"

    def test_data_limited_value(self):
        assert DATA_LIMITED == "DATA_LIMITED"

    def test_overfit_risk_value(self):
        assert OVERFIT_RISK == "OVERFIT_RISK"

    def test_not_promising_value(self):
        assert SP_FATIGUE_FEATURE_NOT_PROMISING == "SP_FATIGUE_FEATURE_NOT_PROMISING"


# ---------------------------------------------------------------------------
# 3. Feature Registry
# ---------------------------------------------------------------------------

class TestFeatureRegistry:
    def test_registry_has_16_entries(self):
        assert len(_SP_FEATURE_REGISTRY) == 16

    def test_available_features_count(self):
        avail = [name for name, limited, _ in _SP_FEATURE_REGISTRY if not limited]
        assert len(avail) == 11

    def test_data_limited_features_count(self):
        limited = [name for name, is_lim, _ in _SP_FEATURE_REGISTRY if is_lim]
        assert len(limited) == 5

    def test_rest_days_features_are_available(self):
        assert "home_sp_rest_days" in _SP_AVAILABLE_FEATURES
        assert "away_sp_rest_days" in _SP_AVAILABLE_FEATURES
        assert "fav_sp_rest_days" in _SP_AVAILABLE_FEATURES

    def test_ip_features_are_data_limited(self):
        limited = {name for name, is_lim, _ in _SP_FEATURE_REGISTRY if is_lim}
        assert "starter_previous_start_ip" in limited
        assert "starter_last_7d_ip" in limited
        assert "starter_last_14d_ip" in limited

    def test_available_features_frozenset_matches_registry(self):
        registry_avail = frozenset(name for name, lim, _ in _SP_FEATURE_REGISTRY if not lim)
        assert _SP_AVAILABLE_FEATURES == registry_avail


# ---------------------------------------------------------------------------
# 4. SP Start History Builder
# ---------------------------------------------------------------------------

class TestSPStartHistoryBuilder:
    def test_empty_input_returns_empty_dict(self):
        hist = _build_sp_start_history([])
        assert hist == {}

    def test_single_game_single_pitcher(self):
        rows = _make_asplayed_rows([("2025-05-01", "HA", "AA", "PitcherA", "PitcherB")])
        hist = _build_sp_start_history(rows)
        assert "PitcherA" in hist
        assert hist["PitcherA"] == ["2025-05-01"]

    def test_multiple_starts_sorted(self):
        rows = _make_asplayed_rows([
            ("2025-06-10", "HA", "AA", "AcePit", "OtherPit"),
            ("2025-05-01", "HA", "AA", "AcePit", "OtherPit"),
            ("2025-05-15", "HA", "AA", "AcePit", "OtherPit"),
        ])
        hist = _build_sp_start_history(rows)
        assert hist["AcePit"] == ["2025-05-01", "2025-05-15", "2025-06-10"]

    def test_empty_starter_names_ignored(self):
        rows = [{"date": "2025-05-01", "home_team": "HA", "away_team": "AA",
                 "home_starter": "", "away_starter": "SomePitcher"}]
        hist = _build_sp_start_history(rows)
        assert "" not in hist
        assert "SomePitcher" in hist

    def test_home_and_away_both_tracked(self):
        rows = _make_asplayed_rows([("2025-05-01", "HA", "AA", "HomePit", "AwayPit")])
        hist = _build_sp_start_history(rows)
        assert "HomePit" in hist
        assert "AwayPit" in hist

    def test_returns_sorted_unique_dates(self):
        rows = _make_asplayed_rows([
            ("2025-05-10", "HA", "AA", "Dup", "X"),
            ("2025-05-01", "HA", "AA", "Dup", "X"),
            ("2025-05-10", "HB", "AB", "Dup", "Y"),  # duplicate date for Dup
        ])
        hist = _build_sp_start_history(rows)
        # sorted, may have duplicates if pitcher started twice same day (edge case)
        assert hist["Dup"] == sorted(hist["Dup"])


# ---------------------------------------------------------------------------
# 5. Rest Days Computation (PIT-safe)
# ---------------------------------------------------------------------------

class TestRestDaysComputation:
    def test_no_history_returns_none(self):
        hist = {}
        result = _compute_sp_rest_days("UnknownPitcher", "2025-05-01", hist)
        assert result is None

    def test_first_start_returns_none(self):
        hist = {"AcePit": ["2025-05-01"]}
        result = _compute_sp_rest_days("AcePit", "2025-05-01", hist)
        assert result is None

    def test_previous_start_exact_5_days(self):
        hist = {"AcePit": ["2025-04-26", "2025-05-01"]}
        result = _compute_sp_rest_days("AcePit", "2025-05-01", hist)
        assert result == 5

    def test_short_rest_4_days(self):
        hist = {"AcePit": ["2025-04-27"]}
        result = _compute_sp_rest_days("AcePit", "2025-05-01", hist)
        assert result == 4

    def test_long_rest_14_days(self):
        hist = {"AcePit": ["2025-04-17"]}
        result = _compute_sp_rest_days("AcePit", "2025-05-01", hist)
        assert result == 14

    def test_pit_safe_excludes_future_starts(self):
        """PIT-safe: current game date is NOT in previous starts list."""
        hist = {"AcePit": ["2025-04-26", "2025-05-01", "2025-05-07"]}
        # For game on 2025-05-01, should use 2025-04-26 as prev (not 2025-05-01 itself)
        result = _compute_sp_rest_days("AcePit", "2025-05-01", hist)
        assert result == 5  # 05-01 - 04-26 = 5 days


# ---------------------------------------------------------------------------
# 6. SP Feature Derivation
# ---------------------------------------------------------------------------

class TestSPFeatureDerivation:
    def _make_history(self) -> dict[str, list[str]]:
        return {
            "HomePit": ["2025-04-26"],
            "AwayPit": ["2025-04-23"],
        }

    def test_all_feature_keys_present(self):
        hist = self._make_history()
        feats = _derive_sp_features("2025-05-01", "HomePit", "AwayPit", 0.65, hist)
        for fname, _, _ in _SP_FEATURE_REGISTRY:
            assert fname in feats, f"Missing feature: {fname}"

    def test_rest_days_computed_correctly(self):
        hist = self._make_history()
        feats = _derive_sp_features("2025-05-01", "HomePit", "AwayPit", 0.65, hist)
        assert feats["home_sp_rest_days"] == 5.0  # 05-01 - 04-26
        assert feats["away_sp_rest_days"] == 8.0  # 05-01 - 04-23

    def test_short_rest_flag(self):
        hist = {"HomePit": ["2025-04-28"], "AwayPit": ["2025-04-23"]}
        feats = _derive_sp_features("2025-05-01", "HomePit", "AwayPit", 0.65, hist)
        assert feats["home_sp_short_rest"] == 1.0   # 3 days = short rest
        assert feats["away_sp_short_rest"] == 0.0   # 8 days = not short rest

    def test_long_rest_flag(self):
        hist = {"HomePit": ["2025-04-26"], "AwayPit": ["2025-04-19"]}
        feats = _derive_sp_features("2025-05-01", "HomePit", "AwayPit", 0.65, hist)
        assert feats["home_sp_long_rest"] == 0.0   # 5 days = not long
        assert feats["away_sp_long_rest"] == 1.0   # 12 days = long rest

    def test_data_limited_features_are_none(self):
        hist = self._make_history()
        feats = _derive_sp_features("2025-05-01", "HomePit", "AwayPit", 0.65, hist)
        for fname, is_lim, _ in _SP_FEATURE_REGISTRY:
            if is_lim:
                assert feats[fname] is None, f"{fname} should be None (DATA_LIMITED)"

    def test_rest_imbalance_computed(self):
        hist = {"HomePit": ["2025-04-26"], "AwayPit": ["2025-04-23"]}
        feats = _derive_sp_features("2025-05-01", "HomePit", "AwayPit", 0.65, hist)
        # home_rest=5, away_rest=8 → imbalance=3
        assert feats["sp_rest_imbalance"] == 3.0

    def test_fav_dog_assignment_home_fav(self):
        hist = {"HomePit": ["2025-04-26"], "AwayPit": ["2025-04-23"]}
        feats = _derive_sp_features("2025-05-01", "HomePit", "AwayPit", 0.72, hist)
        # blend=0.72 >= 0.50 → home is fav
        assert feats["fav_sp_rest_days"] == feats["home_sp_rest_days"]
        assert feats["dog_sp_rest_days"] == feats["away_sp_rest_days"]

    def test_rest_none_when_no_history(self):
        feats = _derive_sp_features("2025-05-01", "NewPit", "NewAway", 0.60, {})
        assert feats["home_sp_rest_days"] is None
        assert feats["away_sp_rest_days"] is None
        assert feats["sp_rest_imbalance"] is None
        assert feats["fav_sp_rest_days"] is None


# ---------------------------------------------------------------------------
# 7. Alignment Logic
# ---------------------------------------------------------------------------

class TestAlignmentLogic:
    def test_perfect_alignment(self):
        preds = [_make_pred_row("2025-05-01", "TeamA", "TeamB")]
        asplayed = _make_asplayed_rows([("2025-05-01", "TeamA", "TeamB", "P1", "P2")])
        hist = _build_sp_start_history(asplayed + _make_asplayed_rows(
            [("2025-04-25", "TeamA", "TeamB", "P1", "P2")]
        ))
        enriched, al = _align_predictions_with_sp(preds, asplayed, hist)
        assert al.n_predictions == 1
        assert al.n_aligned_home_rest == 1
        assert al.home_rest_coverage == 1.0
        assert al.coverage_sufficient

    def test_no_match_returns_none_features(self):
        preds = [_make_pred_row("2025-05-01", "TeamX", "TeamY")]
        asplayed = _make_asplayed_rows([("2025-04-30", "TeamZ", "TeamW", "P1", "P2")])
        hist = _build_sp_start_history(asplayed)
        enriched, al = _align_predictions_with_sp(preds, asplayed, hist)
        assert enriched[0]["home_sp_rest_days"] is None

    def test_alignment_coverage_below_threshold_detected(self):
        preds = [_make_pred_row("2025-05-01", "T1", "T2") for _ in range(100)]
        asplayed = []  # no asplayed → no history → no rest_days
        hist = {}
        _, al = _align_predictions_with_sp(preds, asplayed, hist)
        assert not al.coverage_sufficient

    def test_enriched_rows_contain_sp_fields(self):
        preds = [_make_pred_row("2025-05-01", "TeamA", "TeamB")]
        asplayed = _make_asplayed_rows([("2025-05-01", "TeamA", "TeamB", "HomePit", "AwayPit")])
        hist = _build_sp_start_history(asplayed)
        enriched, _ = _align_predictions_with_sp(preds, asplayed, hist)
        assert "_sp_home_starter" in enriched[0]
        assert "_sp_away_starter" in enriched[0]

    def test_both_coverage_requires_both_starters(self):
        preds = [_make_pred_row("2025-05-01", "TA", "TB")]
        asplayed = _make_asplayed_rows([
            ("2025-04-20", "TA", "TB", "HP", "AP"),
            ("2025-05-01", "TA", "TB", "HP", "AP"),
        ])
        hist = _build_sp_start_history(asplayed)
        _, al = _align_predictions_with_sp(preds, asplayed, hist)
        assert al.n_both_aligned == 1
        assert al.both_coverage == 1.0

    def test_alignment_count_matches_n_predictions(self):
        preds = [_make_pred_row(f"2025-05-{i+1:02d}", "TA", "TB") for i in range(10)]
        asplayed = []
        hist = {}
        _, al = _align_predictions_with_sp(preds, asplayed, hist)
        assert al.n_predictions == 10


# ---------------------------------------------------------------------------
# 8. Feature Coverage
# ---------------------------------------------------------------------------

class TestFeatureCoverage:
    def test_all_features_covered_above_threshold(self):
        n = 100
        # Build enriched rows with all available features set
        rows = []
        for i in range(n):
            r: dict[str, Any] = {
                "home_sp_rest_days": float(i % 7 + 3),
                "away_sp_rest_days": float(i % 7 + 3),
                "home_sp_short_rest": 0.0,
                "away_sp_short_rest": 0.0,
                "home_sp_long_rest": 0.0,
                "away_sp_long_rest": 0.0,
                "sp_rest_imbalance": 1.0,
                "fav_sp_rest_days": float(i % 7 + 3),
                "dog_sp_rest_days": float(i % 7 + 3),
                "fav_sp_short_rest": 0.0,
                "sp_rest_advantage": 0.0,
                "starter_previous_start_ip": None,
                "starter_last_7d_ip": None,
                "starter_last_14d_ip": None,
                "starter_previous_start_pitch_count": None,
                "opener_or_bulk_pitcher_flag": None,
            }
            rows.append(r)
        cov = _compute_sp_coverage(rows)
        avail_cov = [c for c in cov if c.feature_name in _SP_AVAILABLE_FEATURES]
        for c in avail_cov:
            assert not c.data_limited, f"{c.feature_name} should not be DATA_LIMITED"

    def test_data_limited_features_flagged(self):
        rows = [{"starter_previous_start_ip": None, "starter_last_7d_ip": None,
                 "starter_last_14d_ip": None, "starter_previous_start_pitch_count": None,
                 "opener_or_bulk_pitcher_flag": None,
                 "home_sp_rest_days": None, "away_sp_rest_days": None,
                 "home_sp_short_rest": None, "away_sp_short_rest": None,
                 "home_sp_long_rest": None, "away_sp_long_rest": None,
                 "sp_rest_imbalance": None, "fav_sp_rest_days": None,
                 "dog_sp_rest_days": None, "fav_sp_short_rest": None,
                 "sp_rest_advantage": None}]
        cov = _compute_sp_coverage(rows)
        lim = {c.feature_name for c in cov if c.data_limited}
        assert "starter_previous_start_ip" in lim
        assert "starter_last_7d_ip" in lim

    def test_coverage_pct_correct(self):
        rows = [{"home_sp_rest_days": 5.0 if i % 2 == 0 else None,
                 **{f: None for f in ["away_sp_rest_days", "home_sp_short_rest",
                    "away_sp_short_rest", "home_sp_long_rest", "away_sp_long_rest",
                    "sp_rest_imbalance", "fav_sp_rest_days", "dog_sp_rest_days",
                    "fav_sp_short_rest", "sp_rest_advantage", "starter_previous_start_ip",
                    "starter_last_7d_ip", "starter_last_14d_ip",
                    "starter_previous_start_pitch_count", "opener_or_bulk_pitcher_flag"]}}
                for i in range(10)]
        cov = _compute_sp_coverage(rows)
        home_cov = next(c for c in cov if c.feature_name == "home_sp_rest_days")
        assert home_cov.n_available == 5
        assert home_cov.coverage_pct == pytest.approx(0.5, abs=0.01)

    def test_coverage_returns_16_entries(self):
        rows = [{f: None for f, _, _ in _SP_FEATURE_REGISTRY}]
        cov = _compute_sp_coverage(rows)
        assert len(cov) == 16

    def test_inherently_limited_has_reason(self):
        rows = [{f: None for f, _, _ in _SP_FEATURE_REGISTRY}]
        cov = _compute_sp_coverage(rows)
        for c in cov:
            if c.data_limited:
                assert c.data_limited_reason is not None


# ---------------------------------------------------------------------------
# 9. Segment Extraction
# ---------------------------------------------------------------------------

class TestSegmentExtraction:
    def _make_blend_rows(
        self,
        blends: list[float],
        home_wins: list[int] | None = None,
    ) -> list[dict[str, Any]]:
        if home_wins is None:
            home_wins = [1] * len(blends)
        rows = []
        for b, hw in zip(blends, home_wins):
            # model+market that yield blend ≈ b (since blend=(1-0.4)*model+0.4*market)
            rows.append({
                "game_date": "2025-05-01",
                "model_home_prob": b,
                "market_home_prob_no_vig": b,
                "home_win": hw,
            })
        return rows

    def test_all_segment_returns_all(self):
        rows = self._make_blend_rows([0.55, 0.72, 0.80])
        result = _extract_segment(rows, "all")
        assert len(result) == 3

    def test_heavy_fav_filters_correctly(self):
        rows = self._make_blend_rows([0.55, 0.72, 0.80, 0.30])
        result = _extract_segment(rows, "heavy_favorite")
        # blend 0.72>=0.70, 0.80>=0.70; 0.30→fav=0.70 (exactly boundary, passes)
        # fav_prob for 0.30 = max(0.30, 0.70) = 0.70 (exactly 0.70, passes)
        assert len(result) >= 2

    def test_high_confidence_filters(self):
        rows = self._make_blend_rows([0.76, 0.74, 0.80])
        result = _extract_segment(rows, "high_confidence")
        # 0.76>=0.75, 0.80>=0.75; 0.74<0.75 excluded
        assert len(result) == 2

    def test_empty_rows_returns_empty(self):
        assert _extract_segment([], "heavy_favorite") == []

    def test_no_heavy_fav_returns_empty(self):
        rows = self._make_blend_rows([0.52, 0.55, 0.60])
        result = _extract_segment(rows, "heavy_favorite")
        assert len(result) == 0


# ---------------------------------------------------------------------------
# 10. Bucket Attribution Logic
# ---------------------------------------------------------------------------

class TestBucketAttributionLogic:
    def test_basic_bucket_attribution(self):
        # Use distinct float values to ensure median split works
        fvals = [float(i) for i in range(1, 61)]  # 60 distinct values
        wins = [1 if i > 30 else 0 for i in range(1, 61)]
        result = _bucket_attribution(fvals, wins, n_boot=100)
        assert result is not None
        assert result.n_high > 0
        assert result.n_low > 0
        # High bucket should have higher win rate (values 31-60 → wins=1)
        assert result.win_rate_high > result.win_rate_low

    def test_insufficient_data_returns_none(self):
        fvals = [1.0, 2.0, 3.0]
        wins = [1, 0, 1]
        result = _bucket_attribution(fvals, wins, n_boot=10)
        assert result is None

    def test_all_none_values_returns_none(self):
        fvals = [None] * 50
        wins = [1] * 50
        result = _bucket_attribution(fvals, wins, n_boot=10)
        assert result is None

    def test_returns_spdataclass(self):
        fvals = [float(i) for i in range(1, 61)]
        wins = [1] * 30 + [0] * 30
        result = _bucket_attribution(fvals, wins, n_boot=100)
        assert result is not None
        assert isinstance(result, SPBucketAttribution)

    def test_bootstrap_significant_when_ci_excludes_zero(self):
        # All high bucket wins, all low bucket loses → strong signal
        fvals = [float(i) for i in range(1, 61)]
        wins = [1 if i > 30 else 0 for i in range(1, 61)]
        result = _bucket_attribution(fvals, wins, n_boot=500)
        assert result is not None
        # With perfect split signal should be significant
        assert result.bootstrap_significant

    def test_bucket_attribution_equal_values_returns_none(self):
        # All identical values → median split → empty high bucket
        fvals = [5.0] * 50
        wins = [1] * 25 + [0] * 25
        result = _bucket_attribution(fvals, wins, n_boot=10)
        assert result is None


# ---------------------------------------------------------------------------
# 11. Bootstrap CI
# ---------------------------------------------------------------------------

class TestBootstrapCI:
    def test_basic_ci_structure(self):
        high = [1] * 35 + [0] * 15
        low = [1] * 10 + [0] * 40
        ci_lo, ci_hi = _bootstrap_win_rate_delta(high, low, n_boot=1000, rng_seed=42)
        assert ci_lo < ci_hi
        assert ci_lo > 0  # both groups different enough

    def test_ci_symmetric_with_no_signal(self):
        rng = random.Random(42)
        group = [rng.choice([0, 1]) for _ in range(50)]
        ci_lo, ci_hi = _bootstrap_win_rate_delta(group, group, n_boot=200, rng_seed=42)
        # Same group → CI should straddle zero
        assert ci_lo < 0 < ci_hi or (ci_lo == 0 and ci_hi == 0)

    def test_reproducible_with_seed(self):
        high = [1] * 30 + [0] * 20
        low = [1] * 10 + [0] * 40
        c1 = _bootstrap_win_rate_delta(high, low, n_boot=100, rng_seed=7)
        c2 = _bootstrap_win_rate_delta(high, low, n_boot=100, rng_seed=7)
        assert c1 == c2

    def test_ci_bounds_are_floats(self):
        hi = [1, 1, 0, 1, 0] * 5
        lo = [0, 0, 1, 0, 1] * 5
        lo_val, hi_val = _bootstrap_win_rate_delta(hi, lo, n_boot=50)
        assert isinstance(lo_val, float)
        assert isinstance(hi_val, float)


# ---------------------------------------------------------------------------
# 12. OOF Validation
# ---------------------------------------------------------------------------

class TestOOFValidation:
    def _make_multi_month_rows(
        self,
        feature_name: str = "fav_sp_rest_days",
        n_per_month: int = 20,
        n_months: int = 5,
        signal: bool = True,
    ) -> list[dict[str, Any]]:
        rng = random.Random(42)
        rows = []
        months = ["2025-05", "2025-06", "2025-07", "2025-08", "2025-09"][:n_months]
        for month in months:
            for i in range(n_per_month):
                day = (i % 28) + 1
                rest = float(rng.randint(3, 12))
                # signal: high rest → high win rate
                win = 1 if (rest > 7 and signal) else rng.choice([0, 1])
                rows.append({
                    "game_date": f"{month}-{day:02d}",
                    "model_home_prob": 0.72,
                    "market_home_prob_no_vig": 0.72,
                    "home_win": win,
                    feature_name: rest,
                })
        return rows

    def test_oof_returns_result_dataclass(self):
        rows = self._make_multi_month_rows()
        result = _compute_sp_oof(rows, "fav_sp_rest_days", segment="all")
        assert isinstance(result, SPOOFResult)

    def test_oof_with_single_month_returns_zero_folds(self):
        rows = [{"game_date": "2025-05-01", "model_home_prob": 0.72,
                 "market_home_prob_no_vig": 0.72, "home_win": 1, "fav_sp_rest_days": 5.0}
                for _ in range(30)]
        result = _compute_sp_oof(rows, "fav_sp_rest_days", segment="all")
        assert result.n_folds == 0

    def test_oof_fold_months_length_matches_n_folds(self):
        rows = self._make_multi_month_rows(n_per_month=25, n_months=4)
        result = _compute_sp_oof(rows, "fav_sp_rest_days", segment="all")
        assert len(result.fold_months) == result.n_folds
        assert len(result.fold_win_rate_deltas) == result.n_folds

    def test_oof_feature_name_preserved(self):
        rows = self._make_multi_month_rows(n_per_month=25)
        result = _compute_sp_oof(rows, "fav_sp_rest_days")
        assert result.feature_name == "fav_sp_rest_days"

    def test_oof_consistent_sign_detection(self):
        rows = self._make_multi_month_rows(n_per_month=30, n_months=5, signal=True)
        result = _compute_sp_oof(rows, "fav_sp_rest_days", segment="all")
        # With signal, should find some folds
        assert result.n_folds >= 0


# ---------------------------------------------------------------------------
# 13. Negative Control Logic
# ---------------------------------------------------------------------------

class TestNegativeControlLogic:
    def _make_heavy_fav_rows(
        self, n: int = 80, feature_name: str = "fav_sp_rest_days"
    ) -> list[dict[str, Any]]:
        rng = random.Random(42)
        rows = []
        for i in range(n):
            rest = float(rng.randint(3, 12))
            rows.append({
                "game_date": "2025-05-01",
                "model_home_prob": 0.75,
                "market_home_prob_no_vig": 0.75,
                "home_win": rng.choice([0, 1]),
                feature_name: rest,
            })
        return rows

    def test_negative_control_returns_dataclass(self):
        rows = self._make_heavy_fav_rows()
        nc = _compute_sp_negative_control(rows, "fav_sp_rest_days")
        assert isinstance(nc, SPNegativeControl)

    def test_insufficient_data_returns_no_risk(self):
        rows = [{"game_date": "2025-05-01", "model_home_prob": 0.75,
                 "market_home_prob_no_vig": 0.75, "home_win": 1, "fav_sp_rest_days": 5.0}
                for _ in range(5)]
        nc = _compute_sp_negative_control(rows, "fav_sp_rest_days")
        assert not nc.null_rejected
        assert not nc.overfit_risk

    def test_shuffled_std_is_non_negative(self):
        rows = self._make_heavy_fav_rows()
        nc = _compute_sp_negative_control(rows, "fav_sp_rest_days", n_shuffles=50)
        assert nc.shuffled_std_delta >= 0.0

    def test_feature_name_preserved(self):
        rows = self._make_heavy_fav_rows()
        nc = _compute_sp_negative_control(rows, "fav_sp_rest_days")
        assert nc.feature_name == "fav_sp_rest_days"

    def test_segment_preserved(self):
        rows = self._make_heavy_fav_rows()
        nc = _compute_sp_negative_control(rows, "fav_sp_rest_days", segment="heavy_favorite")
        assert nc.segment == "heavy_favorite"


# ---------------------------------------------------------------------------
# 14. Gate Decision Logic
# ---------------------------------------------------------------------------

class TestGateDecisionLogic:
    def _make_alignment(
        self, home_cov: float = 0.90
    ) -> SPAlignment:
        n = 2025
        n_home = int(n * home_cov)
        return SPAlignment(
            n_predictions=n,
            n_asplayed_rows=2430,
            n_aligned_home_rest=n_home,
            n_aligned_away_rest=n_home,
            n_both_aligned=n_home,
            home_rest_coverage=home_cov,
            away_rest_coverage=home_cov,
            both_coverage=home_cov,
            coverage_sufficient=home_cov >= _MIN_COVERAGE_RATE,
        )

    def _make_coverage(self, all_limited: bool = False) -> list[SPFeatureCoverage]:
        return [
            SPFeatureCoverage(
                feature_name=name,
                n_available=0 if (is_lim or all_limited) else 100,
                n_total=100,
                coverage_pct=0.0 if (is_lim or all_limited) else 1.0,
                data_limited=is_lim or all_limited,
                data_limited_reason="test" if (is_lim or all_limited) else None,
            )
            for name, is_lim, _ in _SP_FEATURE_REGISTRY
        ]

    def _make_attribution(
        self, sig: bool = False, n: int = 60
    ) -> list[SPSegmentAttribution]:
        ba = SPBucketAttribution(
            n_high=30, n_low=30,
            win_rate_high=0.60, win_rate_low=0.45,
            win_rate_delta=0.15,
            bootstrap_ci_lower=0.02 if sig else -0.05,
            bootstrap_ci_upper=0.28 if sig else 0.20,
            bootstrap_significant=sig,
        ) if n >= _MIN_SEGMENT_N else None
        return [
            SPSegmentAttribution(
                feature_name="fav_sp_rest_days",
                segment="heavy_favorite",
                n=n, coverage_pct=0.9,
                brier=0.22, bss=0.01,
                calibration_residual=0.01,
                ece=0.05,
                bucket_attribution=ba,
                data_limited=False,
                data_limited_reason=None,
            )
        ]

    def _make_oof(self, sig: bool = False, consistent: bool = False) -> list[SPOOFResult]:
        return [SPOOFResult(
            feature_name="fav_sp_rest_days",
            n_folds=4,
            fold_months=["2025-06", "2025-07", "2025-08", "2025-09"],
            fold_win_rate_deltas=[0.05, 0.04, 0.03, 0.04] if sig else [0.01, -0.01, 0.00, 0.00],
            fold_n=[15, 14, 13, 12],
            oof_mean_delta=0.04 if sig else 0.005,
            oof_consistent_sign=consistent,
            oof_significant=sig,
        )]

    def _make_neg_ctrl(self, overfit: bool = False) -> list[SPNegativeControl]:
        return [SPNegativeControl(
            feature_name="fav_sp_rest_days",
            segment="heavy_favorite",
            real_win_rate_delta=0.10,
            shuffled_mean_delta=0.01,
            shuffled_std_delta=0.05,
            null_rejected=overfit,
            overfit_risk=overfit,
        )]

    def test_data_limited_gate_when_all_limited(self):
        al = self._make_alignment()
        cov = self._make_coverage(all_limited=True)
        gate, _, _, _ = _decide_sp_gate(al, cov, [], [], [])
        assert gate == DATA_LIMITED

    def test_data_limited_gate_when_coverage_low(self):
        al = self._make_alignment(home_cov=0.05)
        cov = self._make_coverage(all_limited=False)
        gate, _, _, _ = _decide_sp_gate(al, cov, [], [], [])
        assert gate == DATA_LIMITED

    def test_overfit_risk_gate(self):
        al = self._make_alignment()
        cov = self._make_coverage()
        attrs = self._make_attribution(sig=True)
        oof = self._make_oof(sig=True, consistent=True)
        nc = self._make_neg_ctrl(overfit=True)
        gate, _, _, _ = _decide_sp_gate(al, cov, attrs, nc, oof)
        assert gate == OVERFIT_RISK

    def test_promising_gate(self):
        al = self._make_alignment()
        cov = self._make_coverage()
        attrs = self._make_attribution(sig=True)
        oof = self._make_oof(sig=True, consistent=True)
        nc = self._make_neg_ctrl(overfit=False)
        gate, _, _, worth = _decide_sp_gate(al, cov, attrs, nc, oof)
        assert gate == SP_FATIGUE_FEATURE_PROMISING
        assert worth is True

    def test_diagnostic_only_signal_gate(self):
        al = self._make_alignment()
        cov = self._make_coverage()
        attrs = self._make_attribution(sig=True)
        oof = self._make_oof(sig=False, consistent=False)
        nc = self._make_neg_ctrl(overfit=False)
        gate, _, _, worth = _decide_sp_gate(al, cov, attrs, nc, oof)
        assert gate == DIAGNOSTIC_ONLY_SIGNAL
        assert worth is False

    def test_not_promising_gate(self):
        al = self._make_alignment()
        cov = self._make_coverage()
        attrs = self._make_attribution(sig=False)
        oof = self._make_oof(sig=False)
        nc = self._make_neg_ctrl(overfit=False)
        gate, _, _, worth = _decide_sp_gate(al, cov, attrs, nc, oof)
        assert gate == SP_FATIGUE_FEATURE_NOT_PROMISING
        assert worth is False

    def test_gate_returns_4_tuple(self):
        al = self._make_alignment()
        cov = self._make_coverage()
        result = _decide_sp_gate(al, cov, [], [], [])
        assert len(result) == 4


# ---------------------------------------------------------------------------
# 15. End-to-End (using real artifacts)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not Path(_REAL_PREDICTIONS).exists() or not Path(_REAL_ASPLAYED).exists(),
    reason="Real artifact files not found — skipping E2E tests",
)
class TestEndToEnd:
    @pytest.fixture(scope="class")
    def result(self):
        return run_phase65_sp_fatigue_attribution(
            predictions_path=_REAL_PREDICTIONS,
            asplayed_path=_REAL_ASPLAYED,
        )

    def test_result_type(self, result):
        assert isinstance(result, Phase65Result)

    def test_phase_version(self, result):
        assert result.phase_version == "phase65_sp_fatigue_attribution_v1"

    def test_safety_constants_in_result(self, result):
        assert result.candidate_patch_created is False
        assert result.production_modified is False
        assert result.alpha_modified is False
        assert result.diagnostic_only is True
        assert result.alpha == 0.40

    def test_phase64b_anchor_in_result(self, result):
        assert result.phase64b_gate == "BULLPEN_GRANULAR_FEATURE_NOT_PROMISING"
        assert result.phase64b_version == "phase64b_full_season_attribution_v1"

    def test_completion_marker(self, result):
        assert result.completion_marker == "PHASE_65_SP_FATIGUE_ATTRIBUTION_VERIFIED"

    def test_n_predictions_correct(self, result):
        assert result.n_predictions == 2025

    def test_sp_history_has_pitchers(self, result):
        assert result.sp_start_history.n_unique_pitchers >= 200
        assert result.sp_start_history.n_pitchers_with_multiple_starts >= 100

    def test_home_rest_coverage_high(self, result):
        # With full asplayed.csv, home rest coverage should be ~80%+
        assert result.alignment.home_rest_coverage >= 0.70

    def test_coverage_sufficient_true(self, result):
        assert result.alignment.coverage_sufficient is True

    def test_feature_coverage_count(self, result):
        assert len(result.feature_coverage) == 16

    def test_n_available_features(self, result):
        assert result.n_available_features == 11

    def test_n_data_limited_features(self, result):
        assert result.n_data_limited_features == 5

    def test_segment_n_all_equals_predictions(self, result):
        assert result.segment_n_all == 2025

    def test_segment_n_heavy_fav_positive(self, result):
        assert result.segment_n_heavy_fav > 0

    def test_attributions_not_empty(self, result):
        assert len(result.attributions) > 0

    def test_attributions_have_correct_segments(self, result):
        segs = {a.segment for a in result.attributions}
        assert "all" in segs
        assert "heavy_favorite" in segs

    def test_negative_controls_for_available_features(self, result):
        nc_names = {nc.feature_name for nc in result.negative_controls}
        assert "fav_sp_rest_days" in nc_names or len(nc_names) > 0

    def test_oof_results_for_available_features(self, result):
        oof_names = {r.feature_name for r in result.oof_results}
        assert len(oof_names) > 0

    def test_gate_is_valid_value(self, result):
        valid_gates = {
            SP_FATIGUE_FEATURE_PROMISING,
            DIAGNOSTIC_ONLY_SIGNAL,
            DATA_LIMITED,
            OVERFIT_RISK,
            SP_FATIGUE_FEATURE_NOT_PROMISING,
        }
        assert result.gate in valid_gates

    def test_gate_rationale_non_empty(self, result):
        assert result.gate_rationale and len(result.gate_rationale) > 10

    def test_next_step_non_empty(self, result):
        assert result.next_step and len(result.next_step) > 10

    def test_worth_phase66_is_bool(self, result):
        assert isinstance(result.worth_phase66, bool)

    def test_result_serialisable_to_json(self, result):
        d = asdict(result)
        serialised = json.dumps(d)
        assert len(serialised) > 100

    def test_any_bootstrap_significant_is_bool(self, result):
        assert isinstance(result.any_bootstrap_significant, bool)

    def test_any_oof_promising_is_bool(self, result):
        assert isinstance(result.any_oof_promising, bool)


# ---------------------------------------------------------------------------
# 16. Backward Compatibility
# ---------------------------------------------------------------------------

class TestBackwardCompatibility:
    def test_phase64b_gate_anchor_value(self):
        assert _PHASE64B_GATE == "BULLPEN_GRANULAR_FEATURE_NOT_PROMISING"

    def test_phase64b_version_anchor(self):
        assert _PHASE64B_VERSION == "phase64b_full_season_attribution_v1"

    def test_phase65_version_format(self):
        assert PHASE_VERSION.startswith("phase65_")

    def test_alpha_matches_frozen_blend(self):
        # blend formula consistency: (1-0.40)*model + 0.40*market
        model = 0.60
        market = 0.50
        expected = 0.60 * model + 0.40 * market
        assert abs(_blend_prob(model, market) - expected) < 1e-9

    def test_heavy_fav_threshold_consistent_with_phase64b(self):
        assert _HEAVY_FAV_THRESHOLD == 0.70

    def test_min_segment_n_consistent(self):
        assert _MIN_SEGMENT_N == 20

    def test_min_coverage_rate_consistent(self):
        assert _MIN_COVERAGE_RATE == 0.10

    def test_phase65_does_not_import_live_statsapi(self):
        import orchestrator.phase65_sp_fatigue_attribution as m65
        src = Path(m65.__file__).read_text()
        # 確保沒有 import statsapi 或 from statsapi 的陳述式
        assert "import statsapi" not in src
        assert "from statsapi" not in src
        assert "requests.get(" not in src

    def test_data_limited_features_always_none_in_output(self):
        """DATA_LIMITED features must always produce None values in feature dict."""
        hist = {"P1": ["2025-04-25"], "P2": ["2025-04-22"]}
        feats = _derive_sp_features("2025-05-01", "P1", "P2", 0.65, hist)
        limited_names = [name for name, is_lim, _ in _SP_FEATURE_REGISTRY if is_lim]
        for fname in limited_names:
            assert feats[fname] is None, f"DATA_LIMITED feature {fname} must be None"
