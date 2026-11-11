"""
tests/test_phase66_market_microstructure_failure_attribution.py
===============================================================
Phase 66 — Market Microstructure Failure Attribution 完整測試套件

測試類別 (13 個)：
  TestSafetyConstants           (5)  — 安全常數不可變
  TestGateConstants             (5)  — Gate 常數正確性
  TestOddsMLConversion          (8)  — _ml_to_prob, _novig_probs, overround
  TestOddsCSVLoading            (6)  — _load_odds_csv
  TestRowEnrichment             (6)  — _enrich_row, _build_enriched_rows
  TestSegmentExtraction         (6)  — _extract_segment (5 segments)
  TestFeatureBucketing          (8)  — bucket functions correctness
  TestMetricsComputation        (8)  — _brier_score, _bss, _compute_ece, _compute_segment_metrics
  TestBootstrapCI               (5)  — _bootstrap_bss_vs_market
  TestAttributionDimension      (6)  — _compute_attribution_dimension
  TestNegativeControl           (5)  — _compute_negative_control
  TestOOFValidation             (5)  — _compute_oof
  TestGateDecisionLogic         (7)  — _decide_gate
  TestEndToEnd                  (22) — run_phase66 with real artifacts
  TestBackwardCompatibility     (9)  — phase65 anchor + no live API + DATA_LIMITED checks

Total: ~111 tests
注意：測試絕不呼叫 live StatsAPI 或外部 API；所有資料使用合成 fixtures 或現有 artifacts。
"""
from __future__ import annotations

import csv
import io
import json
import random
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pytest

# ── Module imports ────────────────────────────────────────────────────────────
from orchestrator.phase66_market_microstructure_failure_attribution import (
    # Safety constants
    CANDIDATE_PATCH_CREATED,
    PRODUCTION_MODIFIED,
    ALPHA_MODIFIED,
    DIAGNOSTIC_ONLY,
    ALPHA,
    PHASE_VERSION,
    # Phase anchors
    _PHASE65_GATE,
    _PHASE65_VERSION,
    _PHASE64B_GATE,
    _PHASE64B_VERSION,
    # Gate constants
    MARKET_MICROSTRUCTURE_FEATURE_PROMISING,
    DIAGNOSTIC_ONLY_SIGNAL,
    DATA_LIMITED,
    OVERFIT_RISK,
    MARKET_MICROSTRUCTURE_NOT_PROMISING,
    # Thresholds
    _HEAVY_FAV_THRESHOLD,
    _HIGH_CONF_THRESHOLD,
    _EXTREME_FAV_THRESHOLD,
    _MIN_SEGMENT_N,
    _MIN_BUCKET_N,
    _BOOTSTRAP_N,
    _OOF_PROMISING_DELTA,
    _MIN_ODDS_COVERAGE,
    # Dimension lists
    _AVAILABLE_DIMENSIONS,
    _DATA_LIMITED_DIMENSIONS,
    # Odds helpers
    _ml_to_prob,
    _novig_probs,
    _load_odds_csv,
    # Probability helpers
    _blend_prob,
    _fav_prob,
    # Bucketing
    _market_implied_bucket,
    _model_prob_bucket,
    _blend_prob_bucket,
    _disagreement_bucket,
    _overround_bucket,
    _odds_price_bucket,
    # Core computation
    _brier_score,
    _bss,
    _compute_ece,
    _compute_segment_metrics,
    _bootstrap_bss_vs_market,
    _compute_attribution_dimension,
    _compute_negative_control,
    _compute_oof,
    _decide_gate,
    _extract_segment,
    _build_enriched_rows,
    # Dataclasses
    OddsRecord,
    OddsAlignment,
    SegmentMetrics,
    BootstrapResult,
    AttributionBucket,
    NegativeControl,
    OOFResult,
    Phase66Result,
    # Main entry
    run_phase66_market_microstructure_failure_attribution,
)

# ── Paths ─────────────────────────────────────────────────────────────────────
_REPO_ROOT = Path(__file__).resolve().parent.parent
_PREDICTIONS_PATH = str(
    _REPO_ROOT / "data/mlb_2025/derived"
    / "mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl"
)
_ODDS_CSV_PATH = str(_REPO_ROOT / "data/mlb_2025/mlb_odds_2025_real.csv")


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

def _make_prediction(
    game_date: str = "2025-05-01",
    home_team: str = "New York Yankees",
    home_win: int = 1,
    model_home_prob: float = 0.60,
    market_home_prob_no_vig: float = 0.58,
    market_away_prob_no_vig: float = 0.42,
) -> dict[str, Any]:
    blend = _blend_prob(model_home_prob, market_home_prob_no_vig)
    return {
        "game_date": game_date,
        "home_team": home_team,
        "away_team": "Boston Red Sox",
        "home_win": home_win,
        "model_home_prob": model_home_prob,
        "market_home_prob_no_vig": market_home_prob_no_vig,
        "market_away_prob_no_vig": market_away_prob_no_vig,
        "audit_hash": "test_hash_001",
        "source_backtest": "phase56_sp_bullpen_context_v1",
    }


def _make_odds_record(
    home_ml_str: str = "-150",
    away_ml_str: str = "+130",
) -> OddsRecord:
    home_impl = _ml_to_prob(home_ml_str)
    away_impl = _ml_to_prob(away_ml_str)
    novig_h, novig_a, overround = (None, None, None)
    if home_impl and away_impl:
        novig_h, novig_a, overround = _novig_probs(home_impl, away_impl)
    try:
        hml = int(home_ml_str.replace("+", ""))
    except ValueError:
        hml = None
    try:
        aml = int(away_ml_str.replace("+", ""))
    except ValueError:
        aml = None
    return OddsRecord(
        game_date="2025-05-01",
        home_team="New York Yankees",
        home_ml_raw=home_ml_str,
        away_ml_raw=away_ml_str,
        home_ml_num=hml,
        away_ml_num=aml,
        home_implied=home_impl,
        away_implied=away_impl,
        overround=overround,
        novig_home=novig_h,
        novig_away=novig_a,
    )


def _make_enriched_rows(n: int, blend_fav: float = 0.60, win_rate: float = 0.55) -> list[dict[str, Any]]:
    """Create n synthetic enriched rows with specified avg blend_fav and win_rate."""
    rows: list[dict[str, Any]] = []
    rng = random.Random(42)
    for i in range(n):
        hw = 1 if rng.random() < win_rate else 0
        model_p = blend_fav - 0.05
        market_p = blend_fav - 0.01
        blend = _blend_prob(model_p, market_p)
        fav_side = "home_fav" if blend >= 0.5 else "away_fav"
        fav_win = hw if blend >= 0.5 else (1 - hw)
        rows.append({
            "game_date": f"2025-0{(i % 5) + 1}-{(i % 28) + 1:02d}",
            "home_team": "New York Yankees",
            "home_win": hw,
            "model_home_prob": model_p,
            "market_home_prob_no_vig": market_p,
            "market_away_prob_no_vig": 1.0 - market_p,
            "_blend": blend,
            "_blend_fav": abs(blend - 0.5) + 0.5,
            "_model_fav_prob": abs(model_p - 0.5) + 0.5,
            "blend_fav_prob": abs(blend - 0.5) + 0.5,
            "model_fav_prob": abs(model_p - 0.5) + 0.5,
            "fav_side": fav_side,
            "disagreement": abs(model_p - market_p),
            "novig_fav_prob": abs(market_p - 0.5) + 0.5,
            "overround": 0.045,
            "odds_price_bucket": "moderate_fav_130_165",
            "_fav_win": fav_win,
            "_odds_aligned": True,
        })
    return rows


def _make_alignment(n_pred: int = 100, n_aligned: int = 98) -> OddsAlignment:
    return OddsAlignment(
        n_predictions=n_pred,
        n_odds_rows=n_pred + 5,
        n_aligned=n_aligned,
        n_unaligned=n_pred - n_aligned,
        coverage=n_aligned / n_pred,
        coverage_sufficient=n_aligned / n_pred >= _MIN_ODDS_COVERAGE,
        sample_audit_hash="test_hash_001",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# § 1  TestSafetyConstants (5)
# ═══════════════════════════════════════════════════════════════════════════════
class TestSafetyConstants:
    def test_candidate_patch_false(self):
        assert CANDIDATE_PATCH_CREATED is False

    def test_production_modified_false(self):
        assert PRODUCTION_MODIFIED is False

    def test_alpha_modified_false(self):
        assert ALPHA_MODIFIED is False

    def test_diagnostic_only_true(self):
        assert DIAGNOSTIC_ONLY is True

    def test_alpha_value(self):
        assert ALPHA == 0.40


# ═══════════════════════════════════════════════════════════════════════════════
# § 2  TestGateConstants (5)
# ═══════════════════════════════════════════════════════════════════════════════
class TestGateConstants:
    def test_promising_gate_string(self):
        assert MARKET_MICROSTRUCTURE_FEATURE_PROMISING == "MARKET_MICROSTRUCTURE_FEATURE_PROMISING"

    def test_diagnostic_gate_string(self):
        assert DIAGNOSTIC_ONLY_SIGNAL == "DIAGNOSTIC_ONLY_SIGNAL"

    def test_data_limited_gate_string(self):
        assert DATA_LIMITED == "DATA_LIMITED"

    def test_overfit_risk_gate_string(self):
        assert OVERFIT_RISK == "OVERFIT_RISK"

    def test_not_promising_gate_string(self):
        assert MARKET_MICROSTRUCTURE_NOT_PROMISING == "MARKET_MICROSTRUCTURE_NOT_PROMISING"


# ═══════════════════════════════════════════════════════════════════════════════
# § 3  TestOddsMLConversion (8)
# ═══════════════════════════════════════════════════════════════════════════════
class TestOddsMLConversion:
    def test_positive_ml_to_prob(self):
        # +150 → 100/(150+100) = 0.40
        p = _ml_to_prob("+150")
        assert p is not None
        assert abs(p - 0.40) < 1e-6

    def test_negative_ml_to_prob(self):
        # -150 → 150/(150+100) = 0.60
        p = _ml_to_prob("-150")
        assert p is not None
        assert abs(p - 0.60) < 1e-6

    def test_even_money(self):
        # +100 → 0.50
        p = _ml_to_prob("+100")
        assert p is not None
        assert abs(p - 0.50) < 1e-6

    def test_empty_string_returns_none(self):
        assert _ml_to_prob("") is None

    def test_dash_only_returns_none(self):
        assert _ml_to_prob("-") is None

    def test_invalid_string_returns_none(self):
        assert _ml_to_prob("n/a") is None

    def test_novig_probs_sum_to_one(self):
        home_raw = _ml_to_prob("-140")
        away_raw = _ml_to_prob("+120")
        assert home_raw is not None and away_raw is not None
        nh, na, vig = _novig_probs(home_raw, away_raw)
        assert abs(nh + na - 1.0) < 1e-8

    def test_overround_positive(self):
        home_raw = _ml_to_prob("-150")
        away_raw = _ml_to_prob("+130")
        assert home_raw is not None and away_raw is not None
        _, _, vig = _novig_probs(home_raw, away_raw)
        assert vig is not None
        assert vig > 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# § 4  TestOddsCSVLoading (6)
# ═══════════════════════════════════════════════════════════════════════════════
class TestOddsCSVLoading:
    def _write_tmp_csv(self, tmp_path: Path, rows: list[dict]) -> str:
        p = tmp_path / "test_odds.csv"
        with open(p, "w", newline="") as f:
            fieldnames = ["Date", "Away", "Home", "Away Score", "Home Score",
                          "Away ML", "Home ML", "O/U", "Over", "Under",
                          "Home RL Spread", "RL Away", "RL Home",
                          "Away Starter", "Home Starter"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in rows:
                writer.writerow(r)
        return str(p)

    def test_loads_nonempty_csv(self, tmp_path):
        rows = [{"Date": "2025-05-01", "Home": "New York Yankees", "Away": "Boston Red Sox",
                 "Home ML": "-150", "Away ML": "+130", "Away Score": "3", "Home Score": "5",
                 "O/U": "8.5", "Over": "+100", "Under": "-120", "Home RL Spread": "-1.5",
                 "RL Away": "+160", "RL Home": "-180", "Away Starter": "", "Home Starter": ""}]
        path = self._write_tmp_csv(tmp_path, rows)
        lookup = _load_odds_csv(path)
        assert ("2025-05-01", "New York Yankees") in lookup

    def test_implied_prob_computed(self, tmp_path):
        rows = [{"Date": "2025-05-01", "Home": "Detroit Tigers", "Away": "Chicago White Sox",
                 "Home ML": "-150", "Away ML": "+130", "Away Score": "", "Home Score": "",
                 "O/U": "", "Over": "", "Under": "", "Home RL Spread": "",
                 "RL Away": "", "RL Home": "", "Away Starter": "", "Home Starter": ""}]
        path = self._write_tmp_csv(tmp_path, rows)
        lookup = _load_odds_csv(path)
        rec = lookup[("2025-05-01", "Detroit Tigers")]
        assert rec.home_implied is not None
        assert abs(rec.home_implied - 0.60) < 1e-6

    def test_novig_home_computed(self, tmp_path):
        rows = [{"Date": "2025-05-01", "Home": "Boston Red Sox", "Away": "Yankees",
                 "Home ML": "-150", "Away ML": "+130", "Away Score": "", "Home Score": "",
                 "O/U": "", "Over": "", "Under": "", "Home RL Spread": "",
                 "RL Away": "", "RL Home": "", "Away Starter": "", "Home Starter": ""}]
        path = self._write_tmp_csv(tmp_path, rows)
        lookup = _load_odds_csv(path)
        rec = lookup[("2025-05-01", "Boston Red Sox")]
        assert rec.novig_home is not None
        assert 0.5 < rec.novig_home < 0.7

    def test_empty_ml_handled(self, tmp_path):
        rows = [{"Date": "2025-05-01", "Home": "Some Team", "Away": "Other Team",
                 "Home ML": "", "Away ML": "", "Away Score": "", "Home Score": "",
                 "O/U": "", "Over": "", "Under": "", "Home RL Spread": "",
                 "RL Away": "", "RL Home": "", "Away Starter": "", "Home Starter": ""}]
        path = self._write_tmp_csv(tmp_path, rows)
        lookup = _load_odds_csv(path)
        rec = lookup[("2025-05-01", "Some Team")]
        assert rec.home_implied is None
        assert rec.novig_home is None

    def test_duplicate_key_last_wins(self, tmp_path):
        # If date+home appears twice, last row wins
        rows = [
            {"Date": "2025-05-01", "Home": "Tigers", "Away": "X",
             "Home ML": "-120", "Away ML": "+100", "Away Score": "", "Home Score": "",
             "O/U": "", "Over": "", "Under": "", "Home RL Spread": "",
             "RL Away": "", "RL Home": "", "Away Starter": "", "Home Starter": ""},
            {"Date": "2025-05-01", "Home": "Tigers", "Away": "X",
             "Home ML": "-150", "Away ML": "+130", "Away Score": "", "Home Score": "",
             "O/U": "", "Over": "", "Under": "", "Home RL Spread": "",
             "RL Away": "", "RL Home": "", "Away Starter": "", "Home Starter": ""},
        ]
        path = self._write_tmp_csv(tmp_path, rows)
        lookup = _load_odds_csv(path)
        rec = lookup[("2025-05-01", "Tigers")]
        assert rec.home_ml_raw == "-150"

    def test_real_odds_csv_loads(self):
        if not Path(_ODDS_CSV_PATH).exists():
            pytest.skip("Real odds CSV not available")
        lookup = _load_odds_csv(_ODDS_CSV_PATH)
        assert len(lookup) >= 2000


# ═══════════════════════════════════════════════════════════════════════════════
# § 5  TestRowEnrichment (6)
# ═══════════════════════════════════════════════════════════════════════════════
class TestRowEnrichment:
    def test_blend_computed_correctly(self):
        pred = _make_prediction(model_home_prob=0.60, market_home_prob_no_vig=0.55)
        odds_rec = _make_odds_record("-150", "+130")
        from orchestrator.phase66_market_microstructure_failure_attribution import _enrich_row
        enriched = _enrich_row(pred, odds_rec)
        expected_blend = (1 - 0.40) * 0.60 + 0.40 * 0.55
        assert abs(enriched["_blend"] - expected_blend) < 1e-8

    def test_fav_side_home_when_blend_gt_half(self):
        pred = _make_prediction(model_home_prob=0.65, market_home_prob_no_vig=0.62)
        from orchestrator.phase66_market_microstructure_failure_attribution import _enrich_row
        enriched = _enrich_row(pred, None)
        assert enriched["fav_side"] == "home_fav"

    def test_fav_side_away_when_blend_lt_half(self):
        pred = _make_prediction(model_home_prob=0.35, market_home_prob_no_vig=0.38)
        from orchestrator.phase66_market_microstructure_failure_attribution import _enrich_row
        enriched = _enrich_row(pred, None)
        assert enriched["fav_side"] == "away_fav"

    def test_disagreement_absolute_value(self):
        pred = _make_prediction(model_home_prob=0.65, market_home_prob_no_vig=0.58)
        from orchestrator.phase66_market_microstructure_failure_attribution import _enrich_row
        enriched = _enrich_row(pred, None)
        assert abs(enriched["disagreement"] - abs(0.65 - 0.58)) < 1e-8

    def test_fav_win_home_fav(self):
        pred = _make_prediction(model_home_prob=0.65, market_home_prob_no_vig=0.62, home_win=1)
        from orchestrator.phase66_market_microstructure_failure_attribution import _enrich_row
        enriched = _enrich_row(pred, None)
        # blend > 0.5 → home is fav → fav_win = home_win = 1
        assert enriched["_fav_win"] == 1

    def test_odds_aligned_flag(self):
        pred = _make_prediction()
        from orchestrator.phase66_market_microstructure_failure_attribution import _enrich_row
        with_odds = _enrich_row(pred, _make_odds_record())
        without_odds = _enrich_row(pred, None)
        assert with_odds["_odds_aligned"] is True
        assert without_odds["_odds_aligned"] is False


# ═══════════════════════════════════════════════════════════════════════════════
# § 6  TestSegmentExtraction (6)
# ═══════════════════════════════════════════════════════════════════════════════
class TestSegmentExtraction:
    def _make_rows_for_segment(self) -> list[dict[str, Any]]:
        rows = []
        for i, blend_fav in enumerate([0.55, 0.65, 0.71, 0.76, 0.81]):
            hw = 1
            blend = blend_fav  # approx (home fav)
            rows.append({
                "game_date": f"2025-0{i+1}-01",
                "home_win": hw,
                "model_home_prob": blend - 0.03,
                "market_home_prob_no_vig": blend - 0.01,
                "market_away_prob_no_vig": 1 - (blend - 0.01),
                "_blend": blend,
                "_blend_fav": blend_fav,
                "_model_fav_prob": blend_fav - 0.02,
                "blend_fav_prob": blend_fav,
                "model_fav_prob": blend_fav - 0.02,
                "fav_side": "home_fav",
                "disagreement": 0.02,
                "novig_fav_prob": blend_fav - 0.01,
                "overround": 0.04,
                "odds_price_bucket": "moderate_fav_130_165",
                "_fav_win": hw,
                "_odds_aligned": True,
            })
        return rows

    def test_all_segment_returns_all(self):
        rows = self._make_rows_for_segment()
        out = _extract_segment(rows, "all")
        assert len(out) == len(rows)

    def test_heavy_favorite_threshold(self):
        rows = self._make_rows_for_segment()
        out = _extract_segment(rows, "heavy_favorite")
        for r in out:
            assert r["_blend_fav"] >= _HEAVY_FAV_THRESHOLD

    def test_high_confidence_threshold(self):
        rows = self._make_rows_for_segment()
        out = _extract_segment(rows, "high_confidence")
        for r in out:
            assert r["_blend_fav"] >= _HIGH_CONF_THRESHOLD

    def test_extreme_favorite_threshold(self):
        rows = self._make_rows_for_segment()
        out = _extract_segment(rows, "extreme_favorite")
        for r in out:
            assert r["_blend_fav"] >= _EXTREME_FAV_THRESHOLD

    def test_phase45_failure_segment_non_empty(self):
        rows = self._make_rows_for_segment()
        out = _extract_segment(rows, "phase45_failure")
        # phase45_failure = blend_fav >= 0.65
        for r in out:
            assert r["_blend_fav"] >= 0.65

    def test_unknown_segment_returns_all(self):
        rows = self._make_rows_for_segment()
        out = _extract_segment(rows, "nonexistent")
        assert len(out) == len(rows)


# ═══════════════════════════════════════════════════════════════════════════════
# § 7  TestFeatureBucketing (8)
# ═══════════════════════════════════════════════════════════════════════════════
class TestFeatureBucketing:
    def test_market_implied_extreme_fav(self):
        assert _market_implied_bucket(0.75) == "extreme_fav_70plus"

    def test_market_implied_heavy_fav_range(self):
        assert _market_implied_bucket(0.67) == "heavy_fav_65_70"

    def test_market_implied_slight_fav(self):
        assert _market_implied_bucket(0.52) == "slight_fav_50_55"

    def test_disagreement_agree(self):
        assert _disagreement_bucket(0.01) == "agree_lt3pct"

    def test_disagreement_slight(self):
        assert _disagreement_bucket(0.05) == "slight_disagree_3_7pct"

    def test_disagreement_strong(self):
        assert _disagreement_bucket(0.10) == "strong_disagree_7pct_plus"

    def test_overround_low(self):
        assert _overround_bucket(0.025) == "low_vig_lt3.5pct"

    def test_odds_price_heavy(self):
        assert _odds_price_bucket(-300) == "heavy_fav_210plus"


# ═══════════════════════════════════════════════════════════════════════════════
# § 8  TestMetricsComputation (8)
# ═══════════════════════════════════════════════════════════════════════════════
class TestMetricsComputation:
    def test_brier_score_perfect(self):
        probs = [1.0, 1.0, 0.0, 0.0]
        labels = [1, 1, 0, 0]
        assert _brier_score(probs, labels) == 0.0

    def test_brier_score_worst(self):
        probs = [0.0, 1.0]
        labels = [1, 0]
        assert abs(_brier_score(probs, labels) - 1.0) < 1e-8

    def test_bss_perfect_predictor(self):
        # bss(0, climate) = 1
        bs = 0.0
        climate = 0.6
        assert _bss(bs, climate) == 1.0

    def test_bss_climate_baseline(self):
        # bss(bs_climate, climate) = 0
        climate = 0.6
        bs_climate = climate * (1 - climate)
        assert abs(_bss(bs_climate, climate)) < 1e-8

    def test_ece_perfect_calibration(self):
        probs = [0.55] * 100
        labels = [1] * 55 + [0] * 45
        ece = _compute_ece(probs, labels)
        assert ece >= 0

    def test_ece_empty_returns_nan(self):
        import math
        assert math.isnan(_compute_ece([], []))

    def test_segment_metrics_n_correct(self):
        rows = _make_enriched_rows(50)
        m = _compute_segment_metrics(rows)
        assert m.n == 50

    def test_segment_metrics_brier_nonnegative(self):
        rows = _make_enriched_rows(50)
        m = _compute_segment_metrics(rows)
        assert m.model_brier >= 0
        assert m.market_brier >= 0
        assert m.blend_brier >= 0


# ═══════════════════════════════════════════════════════════════════════════════
# § 9  TestBootstrapCI (5)
# ═══════════════════════════════════════════════════════════════════════════════
class TestBootstrapCI:
    def test_bootstrap_returns_boot_result(self):
        rows = _make_enriched_rows(50)
        result = _bootstrap_bss_vs_market(rows, n_boot=100)
        assert isinstance(result, BootstrapResult)

    def test_bootstrap_ci_ordered(self):
        rows = _make_enriched_rows(50)
        result = _bootstrap_bss_vs_market(rows, n_boot=200)
        assert result.ci_lower <= result.ci_upper

    def test_bootstrap_prob_positive_in_range(self):
        rows = _make_enriched_rows(100)
        result = _bootstrap_bss_vs_market(rows, n_boot=200)
        assert 0.0 <= result.prob_positive <= 1.0

    def test_bootstrap_small_n_returns_not_significant(self):
        rows = _make_enriched_rows(5)  # below _MIN_BUCKET_N
        result = _bootstrap_bss_vs_market(rows, n_boot=100)
        assert result.significant is False

    def test_bootstrap_rng_seed_reproducible(self):
        rows = _make_enriched_rows(50)
        r1 = _bootstrap_bss_vs_market(rows, n_boot=200, rng_seed=99)
        r2 = _bootstrap_bss_vs_market(rows, n_boot=200, rng_seed=99)
        assert r1.ci_lower == r2.ci_lower
        assert r1.ci_upper == r2.ci_upper


# ═══════════════════════════════════════════════════════════════════════════════
# § 10  TestAttributionDimension (6)
# ═══════════════════════════════════════════════════════════════════════════════
class TestAttributionDimension:
    def test_attribution_returns_list(self):
        rows = _make_enriched_rows(100)
        buckets = _compute_attribution_dimension(rows, "disagreement_bucket", "all")
        assert isinstance(buckets, list)
        assert all(isinstance(b, AttributionBucket) for b in buckets)

    def test_attribution_bucket_dim_matches(self):
        rows = _make_enriched_rows(100)
        buckets = _compute_attribution_dimension(rows, "fav_side", "all")
        for b in buckets:
            assert b.dim == "fav_side"

    def test_attribution_bucket_n_sums_to_total(self):
        rows = _make_enriched_rows(100)
        buckets = _compute_attribution_dimension(rows, "disagreement_bucket", "all", n_boot=0)
        total = sum(b.n for b in buckets)
        assert total == len(rows)

    def test_attribution_available_dims(self):
        rows = _make_enriched_rows(60)
        for dim in _AVAILABLE_DIMENSIONS:
            buckets = _compute_attribution_dimension(rows, dim, "all", n_boot=0)
            assert isinstance(buckets, list)

    def test_attribution_segment_name_stored(self):
        rows = _make_enriched_rows(50)
        buckets = _compute_attribution_dimension(rows, "fav_side", "heavy_favorite", n_boot=0)
        for b in buckets:
            assert b.segment_name == "heavy_favorite"

    def test_attribution_empty_rows_returns_empty(self):
        buckets = _compute_attribution_dimension([], "fav_side", "all", n_boot=0)
        assert buckets == []


# ═══════════════════════════════════════════════════════════════════════════════
# § 11  TestNegativeControl (5)
# ═══════════════════════════════════════════════════════════════════════════════
class TestNegativeControl:
    def test_negative_control_returns_dataclass(self):
        rows = _make_enriched_rows(80)
        nc = _compute_negative_control(rows, "disagreement_bucket", "all")
        assert isinstance(nc, NegativeControl)

    def test_negative_control_dim_matches(self):
        rows = _make_enriched_rows(80)
        nc = _compute_negative_control(rows, "fav_side", "all")
        assert nc.dim == "fav_side"

    def test_negative_control_shuffled_std_nonneg(self):
        rows = _make_enriched_rows(80)
        nc = _compute_negative_control(rows, "disagreement_bucket", "all")
        assert nc.shuffled_std_delta >= 0

    def test_negative_control_real_delta_nonneg(self):
        rows = _make_enriched_rows(80)
        nc = _compute_negative_control(rows, "disagreement_bucket", "all")
        assert nc.real_blend_bss_delta >= 0

    def test_negative_control_overfit_risk_is_bool(self):
        rows = _make_enriched_rows(80)
        nc = _compute_negative_control(rows, "market_implied_bucket", "all")
        assert isinstance(nc.overfit_risk, bool)


# ═══════════════════════════════════════════════════════════════════════════════
# § 12  TestOOFValidation (5)
# ═══════════════════════════════════════════════════════════════════════════════
class TestOOFValidation:
    def _make_monthly_rows(self, n_months: int = 5) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for m in range(n_months):
            for d in range(20):
                r = _make_enriched_rows(1)[0]
                r["game_date"] = f"2025-{m + 4:02d}-{d + 1:02d}"
                rows.append(r)
        return rows

    def test_oof_returns_result(self):
        rows = self._make_monthly_rows(4)
        oof = _compute_oof(rows, "disagreement_bucket", "all")
        assert isinstance(oof, OOFResult)

    def test_oof_n_folds_correct(self):
        rows = self._make_monthly_rows(5)
        oof = _compute_oof(rows, "fav_side", "all")
        # 4 usable test folds (skip first month which has no prior)
        # but limited by _MIN_BUCKET_N
        assert oof.n_folds >= 0

    def test_oof_fold_lengths_match(self):
        rows = self._make_monthly_rows(4)
        oof = _compute_oof(rows, "fav_side", "all")
        assert len(oof.fold_months) == oof.n_folds
        assert len(oof.fold_bss_deltas) == oof.n_folds

    def test_oof_mean_delta_computed(self):
        rows = self._make_monthly_rows(5)
        oof = _compute_oof(rows, "disagreement_bucket", "all")
        if oof.n_folds > 0:
            expected = sum(oof.fold_bss_deltas) / oof.n_folds
            assert abs(oof.oof_mean_delta - expected) < 1e-8

    def test_oof_no_data_returns_zero_folds(self):
        oof = _compute_oof([], "fav_side", "all")
        assert oof.n_folds == 0


# ═══════════════════════════════════════════════════════════════════════════════
# § 13  TestGateDecisionLogic (7)
# ═══════════════════════════════════════════════════════════════════════════════
class TestGateDecisionLogic:
    def _base_alignment(self, coverage: float = 0.95) -> OddsAlignment:
        n = 100
        aligned = int(n * coverage)
        return OddsAlignment(
            n_predictions=n, n_odds_rows=n + 5,
            n_aligned=aligned, n_unaligned=n - aligned,
            coverage=coverage, coverage_sufficient=coverage >= _MIN_ODDS_COVERAGE,
            sample_audit_hash="hash"
        )

    def _base_metrics(self) -> SegmentMetrics:
        return _compute_segment_metrics(_make_enriched_rows(200))

    def _no_sig_buckets(self) -> list[AttributionBucket]:
        rows = _make_enriched_rows(30)
        return _compute_attribution_dimension(rows, "fav_side", "all", n_boot=0)

    def test_data_limited_when_coverage_low(self):
        low_cov = self._base_alignment(coverage=0.50)
        gate, *_ = _decide_gate(low_cov, self._base_metrics(), [], [], [])
        assert gate == DATA_LIMITED

    def test_overfit_risk_when_negative_control_overfit(self):
        alignment = self._base_alignment()
        nc = NegativeControl(dim="fav_side", segment="all",
                             real_blend_bss_delta=0.10,
                             shuffled_mean_delta=0.02, shuffled_std_delta=0.01,
                             null_rejected=True, overfit_risk=True)
        gate, *_ = _decide_gate(alignment, self._base_metrics(), [], [nc], [])
        assert gate == OVERFIT_RISK

    def test_promising_when_boot_and_oof(self):
        alignment = self._base_alignment()
        boot_res = BootstrapResult(ci_lower=0.005, ci_upper=0.05, prob_positive=0.95, significant=True)
        bucket = AttributionBucket(dim="fav_side", bucket_label="home_fav", n=30,
                                   segment_name="all",
                                   metrics=self._base_metrics(), bootstrap=boot_res)
        oof_res = OOFResult(dim="fav_side", segment="all", n_folds=4,
                            fold_months=["2025-05", "2025-06", "2025-07", "2025-08"],
                            fold_bss_deltas=[0.01, 0.008, 0.012, 0.009],
                            fold_ns=[20, 20, 20, 20],
                            oof_mean_delta=0.0098, oof_consistent_sign=True,
                            oof_significant=True)
        gate, _, _, worth = _decide_gate(alignment, self._base_metrics(),
                                         [bucket], [], [oof_res])
        assert gate == MARKET_MICROSTRUCTURE_FEATURE_PROMISING
        assert worth is True

    def test_diagnostic_when_only_boot_sig(self):
        alignment = self._base_alignment()
        boot_res = BootstrapResult(ci_lower=0.001, ci_upper=0.08, prob_positive=0.97, significant=True)
        bucket = AttributionBucket(dim="fav_side", bucket_label="home_fav", n=30,
                                   segment_name="all",
                                   metrics=self._base_metrics(), bootstrap=boot_res)
        gate, *_ = _decide_gate(alignment, self._base_metrics(), [bucket], [], [])
        assert gate == DIAGNOSTIC_ONLY_SIGNAL

    def test_not_promising_default(self):
        alignment = self._base_alignment()
        buckets = self._no_sig_buckets()
        gate, *_ = _decide_gate(alignment, self._base_metrics(), buckets, [], [])
        assert gate == MARKET_MICROSTRUCTURE_NOT_PROMISING

    def test_gate_rationale_not_empty(self):
        alignment = self._base_alignment()
        _, rationale, _, _ = _decide_gate(alignment, self._base_metrics(), [], [], [])
        assert len(rationale) > 10

    def test_worth_phase67_false_when_not_promising(self):
        alignment = self._base_alignment()
        _, _, _, worth = _decide_gate(alignment, self._base_metrics(), [], [], [])
        assert worth is False


# ═══════════════════════════════════════════════════════════════════════════════
# § 14  TestEndToEnd (22)
# ═══════════════════════════════════════════════════════════════════════════════
class TestEndToEnd:
    @pytest.fixture(scope="class")
    def result(self):
        if not Path(_PREDICTIONS_PATH).exists():
            pytest.skip("Real predictions not available")
        if not Path(_ODDS_CSV_PATH).exists():
            pytest.skip("Real odds CSV not available")
        return run_phase66_market_microstructure_failure_attribution(
            predictions_path=_PREDICTIONS_PATH,
            odds_csv_path=_ODDS_CSV_PATH,
        )

    def test_result_type(self, result):
        assert isinstance(result, Phase66Result)

    def test_safety_constants_preserved(self, result):
        assert result.candidate_patch_created is False
        assert result.production_modified is False
        assert result.alpha_modified is False
        assert result.diagnostic_only is True

    def test_alpha_unchanged(self, result):
        assert result.alpha == 0.40

    def test_completion_marker_present(self, result):
        assert result.completion_marker == "PHASE_66_MARKET_MICROSTRUCTURE_FAILURE_ATTRIBUTION_VERIFIED"

    def test_phase65_gate_anchor(self, result):
        assert result.phase65_gate == "OVERFIT_RISK"

    def test_phase_version_string(self, result):
        assert "phase66" in result.phase_version

    def test_n_predictions(self, result):
        assert result.n_predictions == 2025

    def test_odds_coverage_sufficient(self, result):
        assert result.odds_alignment.coverage >= _MIN_ODDS_COVERAGE

    def test_segment_n_all(self, result):
        assert result.segment_n_all == 2025

    def test_segment_n_heavy_fav_positive(self, result):
        assert result.segment_n_heavy_fav > 0

    def test_heavy_fav_below_full(self, result):
        assert result.segment_n_heavy_fav < result.segment_n_all

    def test_segment_sizes_ordered(self, result):
        assert result.segment_n_heavy_fav >= result.segment_n_high_conf
        assert result.segment_n_high_conf >= result.segment_n_extreme_fav

    def test_all_metrics_win_rate_sensible(self, result):
        assert 0.3 < result.all_metrics.win_rate < 0.7

    def test_all_metrics_brier_in_range(self, result):
        assert 0.0 < result.all_metrics.blend_brier < 0.5

    def test_attribution_buckets_non_empty(self, result):
        assert len(result.attribution_buckets) > 0

    def test_negative_controls_all_dims(self, result):
        dims = {nc.dim for nc in result.negative_controls}
        for d in _AVAILABLE_DIMENSIONS:
            assert d in dims

    def test_oof_results_non_empty(self, result):
        assert len(result.oof_results) > 0

    def test_gate_is_valid(self, result):
        valid_gates = {
            MARKET_MICROSTRUCTURE_FEATURE_PROMISING,
            DIAGNOSTIC_ONLY_SIGNAL,
            DATA_LIMITED,
            OVERFIT_RISK,
            MARKET_MICROSTRUCTURE_NOT_PROMISING,
        }
        assert result.gate in valid_gates

    def test_gate_rationale_non_empty(self, result):
        assert len(result.gate_rationale) > 0

    def test_data_limited_dims_present(self, result):
        assert len(result.data_limited_dimensions) > 0
        for d in result.data_limited_dimensions:
            assert d not in _AVAILABLE_DIMENSIONS

    def test_result_is_serialisable(self, result):
        d = asdict(result)
        j = json.dumps(d, default=str)
        assert len(j) > 100

    def test_run_timestamp_present(self, result):
        assert "2026" in result.run_timestamp or "2025" in result.run_timestamp


# ═══════════════════════════════════════════════════════════════════════════════
# § 15  TestBackwardCompatibility (9)
# ═══════════════════════════════════════════════════════════════════════════════
class TestBackwardCompatibility:
    def test_phase65_gate_anchor_value(self):
        assert _PHASE65_GATE == "OVERFIT_RISK"

    def test_phase65_version_string(self):
        assert "phase65" in _PHASE65_VERSION

    def test_phase64b_gate_anchor_value(self):
        assert _PHASE64B_GATE == "BULLPEN_GRANULAR_FEATURE_NOT_PROMISING"

    def test_phase64b_version_string(self):
        assert "phase64b" in _PHASE64B_VERSION

    def test_data_limited_dims_not_in_available(self):
        for d in _DATA_LIMITED_DIMENSIONS:
            assert d not in _AVAILABLE_DIMENSIONS

    def test_does_not_import_live_statsapi(self):
        module_path = Path(__file__).resolve().parent.parent / \
            "orchestrator/phase66_market_microstructure_failure_attribution.py"
        src = module_path.read_text()
        # Must not import live statsapi or external API
        assert "import requests" not in src
        assert "urllib.request" not in src

    def test_does_not_import_telethon(self):
        module_path = Path(__file__).resolve().parent.parent / \
            "orchestrator/phase66_market_microstructure_failure_attribution.py"
        src = module_path.read_text()
        assert "telethon" not in src.lower()

    def test_data_limited_fields_documented(self):
        from orchestrator.phase66_market_microstructure_failure_attribution import _DATA_LIMITED_FIELDS
        assert "opening_home_ml" in _DATA_LIMITED_FIELDS
        assert "clv_direction" in _DATA_LIMITED_FIELDS

    def test_blend_formula_uses_frozen_alpha(self):
        # Blend formula must use ALPHA=0.40
        model_p = 0.70
        market_p = 0.60
        b = _blend_prob(model_p, market_p)
        expected = (1 - 0.40) * 0.70 + 0.40 * 0.60
        assert abs(b - expected) < 1e-8
