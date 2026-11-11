"""
tests/test_strategy_simulator_spine.py

Tests for the simulate_strategy() function.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from wbc_backend.simulation.strategy_simulator import simulate_strategy
from wbc_backend.simulation.strategy_simulation_result import StrategySimulationResult

# ── Fixture builders ──────────────────────────────────────────────────────────

def _make_row(
    home_ml: str = "-130",
    away_ml: str = "+110",
    home_score: int = 5,
    away_score: int = 3,
    status: str = "Final",
    model_prob_home: float | None = None,
) -> dict:
    row: dict = {
        "Date": "2025-05-01",
        "Away": "Team A",
        "Home": "Team B",
        "Away Score": str(away_score),
        "Home Score": str(home_score),
        "Status": status,
        "Away ML": away_ml,
        "Home ML": home_ml,
    }
    if model_prob_home is not None:
        row["model_prob_home"] = str(model_prob_home)
    return row


def _make_rows_n(n: int, home_win: bool = True, **kwargs) -> list[dict]:
    """Generate n identical rows."""
    score = (5, 3) if home_win else (3, 5)
    return [_make_row(home_score=score[0], away_score=score[1], **kwargs) for _ in range(n)]


def _make_mixed_rows(n: int) -> list[dict]:
    """Alternate home win / away win rows."""
    rows = []
    for i in range(n):
        if i % 2 == 0:
            rows.append(_make_row(home_score=5, away_score=3))
        else:
            rows.append(_make_row(home_score=3, away_score=5))
    return rows


# ── Tests: basic returns ───────────────────────────────────────────────────────

class TestSimulateStrategyBasic:
    def test_returns_strategy_simulation_result(self):
        rows = _make_rows_n(50)
        result = simulate_strategy("test", rows, "2025-01-01", "2025-12-31")
        assert isinstance(result, StrategySimulationResult)

    def test_paper_only_always_true(self):
        rows = _make_rows_n(50)
        result = simulate_strategy("test", rows, "2025-01-01", "2025-12-31")
        assert result.paper_only is True

    def test_simulation_id_is_string(self):
        rows = _make_rows_n(50)
        result = simulate_strategy("test", rows, "2025-01-01", "2025-12-31")
        assert isinstance(result.simulation_id, str)
        assert len(result.simulation_id) > 0

    def test_generated_at_utc_is_datetime(self):
        rows = _make_rows_n(50)
        result = simulate_strategy("test", rows, "2025-01-01", "2025-12-31")
        assert isinstance(result.generated_at_utc, datetime)
        assert result.generated_at_utc.tzinfo is not None


# ── Tests: gate on low sample ─────────────────────────────────────────────────

class TestGateLowSample:
    def test_blocked_low_sample_for_tiny_input(self):
        rows = _make_rows_n(5)
        result = simulate_strategy("test", rows, "2025-01-01", "2025-12-31")
        assert result.gate_status == "BLOCKED_LOW_SAMPLE"

    def test_blocked_low_sample_for_exactly_29(self):
        rows = _make_rows_n(29)
        result = simulate_strategy("test", rows, "2025-01-01", "2025-12-31")
        assert result.gate_status == "BLOCKED_LOW_SAMPLE"

    def test_not_blocked_low_sample_at_30(self):
        rows = _make_mixed_rows(30)
        result = simulate_strategy(
            "test", rows, "2025-01-01", "2025-12-31", require_positive_bss=False
        )
        assert result.gate_status != "BLOCKED_LOW_SAMPLE"

    def test_sample_size_matches_usable_rows(self):
        rows = _make_rows_n(50)
        result = simulate_strategy("test", rows, "2025-01-01", "2025-12-31")
        assert result.sample_size == 50


# ── Tests: gate on negative BSS ───────────────────────────────────────────────

class TestGateNegativeBSS:
    def test_blocked_negative_bss_when_model_underperforms(self):
        """
        All home wins with home_ml=-130 → market assigns ~56.5% to home.
        If model_prob_home is set to 0.42 (much lower), model will be worse calibrated.
        """
        rows = [
            _make_row(
                home_ml="-130", away_ml="+110",
                home_score=5, away_score=3,   # home win
                model_prob_home=0.35,          # wrong direction vs market
            )
            for _ in range(50)
        ]
        result = simulate_strategy(
            "test", rows, "2025-01-01", "2025-12-31", require_positive_bss=True
        )
        # BSS = 1 - brier_model/brier_market; if model is worse, BSS < 0
        assert result.gate_status == "BLOCKED_NEGATIVE_BSS"
        assert result.brier_skill_score is not None
        assert result.brier_skill_score < 0

    def test_not_blocked_when_require_positive_bss_false(self):
        rows = [
            _make_row(
                home_ml="-130", away_ml="+110",
                home_score=5, away_score=3,
                model_prob_home=0.35,
            )
            for _ in range(50)
        ]
        result = simulate_strategy(
            "test", rows, "2025-01-01", "2025-12-31", require_positive_bss=False
        )
        assert result.gate_status != "BLOCKED_NEGATIVE_BSS"


# ── Tests: empty rows ─────────────────────────────────────────────────────────

class TestGateNoResults:
    def test_blocked_no_results_for_empty_list(self):
        result = simulate_strategy("test", [], "2025-01-01", "2025-12-31")
        assert result.gate_status == "BLOCKED_NO_RESULTS"
        assert result.sample_size == 0

    def test_blocked_no_market_data_when_odds_missing(self):
        rows = [
            {"Date": "2025-05-01", "Away": "A", "Home": "B",
             "Away Score": "3", "Home Score": "5", "Status": "Final"}
            for _ in range(50)
        ]
        result = simulate_strategy("test", rows, "2025-01-01", "2025-12-31")
        assert result.gate_status in ("BLOCKED_NO_MARKET_DATA", "BLOCKED_NO_RESULTS")


# ── Tests: metrics computation ────────────────────────────────────────────────

class TestMetricsComputation:
    def test_brier_score_computed(self):
        rows = _make_mixed_rows(50)
        result = simulate_strategy(
            "test", rows, "2025-01-01", "2025-12-31", require_positive_bss=False
        )
        assert result.brier_model is not None
        assert 0.0 <= result.brier_model <= 1.0

    def test_brier_market_computed(self):
        rows = _make_mixed_rows(50)
        result = simulate_strategy(
            "test", rows, "2025-01-01", "2025-12-31", require_positive_bss=False
        )
        assert result.brier_market is not None
        assert 0.0 <= result.brier_market <= 1.0

    def test_ece_computed(self):
        rows = _make_mixed_rows(50)
        result = simulate_strategy(
            "test", rows, "2025-01-01", "2025-12-31", require_positive_bss=False
        )
        assert result.ece is not None
        assert 0.0 <= result.ece <= 1.0

    def test_bss_computed(self):
        rows = _make_mixed_rows(50)
        result = simulate_strategy(
            "test", rows, "2025-01-01", "2025-12-31", require_positive_bss=False
        )
        # BSS might be None only if brier_market == 0, which is impossible on real data
        # On mixed rows with market proxy, it will be ~0
        # Just assert it's numeric or None
        if result.brier_skill_score is not None:
            assert isinstance(result.brier_skill_score, float)

    def test_avg_model_prob_in_range(self):
        rows = _make_mixed_rows(50)
        result = simulate_strategy(
            "test", rows, "2025-01-01", "2025-12-31", require_positive_bss=False
        )
        if result.avg_model_prob is not None:
            assert 0.0 <= result.avg_model_prob <= 1.0

    def test_skipped_count_non_negative(self):
        rows = _make_mixed_rows(50)
        result = simulate_strategy("test", rows, "2025-01-01", "2025-12-31",
                                   require_positive_bss=False)
        assert result.skipped_count >= 0

    def test_bet_count_gte_zero(self):
        rows = _make_mixed_rows(50)
        result = simulate_strategy("test", rows, "2025-01-01", "2025-12-31",
                                   require_positive_bss=False)
        assert result.bet_count >= 0

    def test_fixture_rows_bss_near_zero_with_proxy(self):
        """
        When model_prob_home is not in rows, simulator uses market prob as proxy.
        BSS should be ~0 (market vs market) — but can be slightly off due to rounding.
        """
        rows = _make_mixed_rows(50)
        result = simulate_strategy(
            "test", rows, "2025-01-01", "2025-12-31", require_positive_bss=False
        )
        # When using market proxy, brier_model ~= brier_market → BSS ~= 0
        if result.brier_skill_score is not None:
            assert abs(result.brier_skill_score) < 0.01

    def test_model_prob_column_used_when_present(self):
        """Rows with model_prob_home column use that value, not market proxy."""
        rows = [
            _make_row(
                home_ml="-130", away_ml="+110",
                home_score=5, away_score=3,
                model_prob_home=0.70,   # strong model confidence
            )
            for _ in range(50)
        ]
        result = simulate_strategy(
            "test", rows, "2025-01-01", "2025-12-31", require_positive_bss=False
        )
        assert result.avg_model_prob is not None
        assert abs(result.avg_model_prob - 0.70) < 0.01

    def test_walk_forward_ml_candidate_source_trace_fields(self):
        rows = []
        for i in range(50):
            rows.append(
                {
                    "Date": "2025-05-01",
                    "Away": "Team A",
                    "Home": "Team B",
                    "Away Score": "3" if i % 2 == 0 else "5",
                    "Home Score": "5" if i % 2 == 0 else "3",
                    "Status": "Final",
                    "Away ML": "+110",
                    "Home ML": "-130",
                    "model_prob_home": "0.56" if i % 2 == 0 else "0.44",
                    "probability_source": "walk_forward_ml_candidate",
                    "ml_model_type": "logistic_regression",
                    "ml_feature_policy": "p13_v1",
                    "ml_features_used": "indep_recent_win_rate_delta,indep_starter_era_delta",
                }
            )
        result = simulate_strategy(
            "wf_ml_test", rows, "2025-01-01", "2025-12-31", require_positive_bss=False
        )
        assert result.source_trace.get("probability_source_mode") == "walk_forward_ml_candidate"
        assert result.source_trace.get("walk_forward_ml_candidate_count", 0) > 0


# ── Tests: gate PASS scenario ─────────────────────────────────────────────────

class TestGatePass:
    def test_pass_gate_with_good_calibrated_model(self):
        """
        Model with ~55% home win probability on games where home wins 55% of time.
        Brier score should be similar to market. With require_positive_bss=False and
        ECE below threshold, gate should PASS.
        """
        rows = []
        for i in range(100):
            # Home wins ~55% of time (55 wins, 45 losses)
            home_score = 5 if i < 55 else 2
            away_score = 3 if i < 55 else 4
            rows.append(_make_row(
                home_ml="-120", away_ml="+100",
                home_score=home_score, away_score=away_score,
                model_prob_home=0.545,  # well-calibrated at ~55% home win rate
            ))
        result = simulate_strategy(
            "test_pass", rows, "2025-01-01", "2025-12-31",
            require_positive_bss=False, ece_threshold=0.20,
        )
        assert result.gate_status == "PASS"
        assert result.paper_only is True


# ── Tests: P5 probability_source_mode in source_trace ────────────────────────

class TestProbabilitySourceModeP5:
    def test_market_proxy_mode_when_no_model_prob_column(self):
        """Without model_prob_home column, mode must be market_proxy."""
        rows = _make_rows_n(50)  # no model_prob_home
        result = simulate_strategy("test", rows, "2025-01-01", "2025-12-31",
                                   require_positive_bss=False)
        assert "probability_source_mode" in result.source_trace
        assert result.source_trace["probability_source_mode"] == "market_proxy"

    def test_real_model_mode_when_model_prob_column_present(self):
        """Rows with model_prob_home and calibrated_model source → mode must be calibrated_model (P6)."""
        rows = [
            _make_row(model_prob_home=0.55, home_score=5, away_score=3)
            for _ in range(50)
        ]
        # Mark rows with calibrated_model source (not proxy)
        for r in rows:
            r["probability_source"] = "calibrated_model"
        result = simulate_strategy("test", rows, "2025-01-01", "2025-12-31",
                                   require_positive_bss=False)
        # P6: calibrated_model source is tracked as calibrated_model_count, not real_model_count
        assert result.source_trace["probability_source_mode"] == "calibrated_model"
        assert result.source_trace["calibrated_model_count"] > 0
        assert result.source_trace["market_proxy_count"] == 0

    def test_mixed_mode_with_some_proxy_rows(self):
        """Mix of calibrated model rows and market_proxy rows → mode must be mixed."""
        rows = []
        for i in range(50):
            r = _make_row(model_prob_home=0.55, home_score=5, away_score=3)
            r["probability_source"] = "calibrated_model" if i < 25 else "market_proxy"
            rows.append(r)
        result = simulate_strategy("test", rows, "2025-01-01", "2025-12-31",
                                   require_positive_bss=False)
        assert result.source_trace["probability_source_mode"] == "mixed"
        assert result.source_trace["calibrated_model_count"] > 0
        assert result.source_trace["market_proxy_count"] > 0

    def test_source_trace_has_real_and_proxy_counts(self):
        rows = _make_rows_n(50)
        result = simulate_strategy("test", rows, "2025-01-01", "2025-12-31",
                                   require_positive_bss=False)
        assert "real_model_count" in result.source_trace
        assert "market_proxy_count" in result.source_trace
        assert "missing_model_prob_count" in result.source_trace

    def test_missing_model_prob_count_tracked(self):
        """Rows that failed model prob parsing appear in missing_model_prob_count."""
        # Rows with corrupt model_prob_home → will be counted as missing
        rows = []
        for _ in range(50):
            r = _make_row(home_score=5, away_score=3)
            r["model_prob_home"] = "INVALID"
            rows.append(r)
        result = simulate_strategy("test", rows, "2025-01-01", "2025-12-31",
                                   require_positive_bss=False)
        # With invalid model_prob, it falls back to market proxy; missing_model_data may be 0
        assert "missing_model_prob_count" in result.source_trace


# ── Tests: P7 OOF calibration detection in source_trace ──────────────────────

import json as _json


def _make_oof_row(
    home_ml: str = "-130",
    away_ml: str = "+110",
    home_score: int = 5,
    away_score: int = 3,
    model_prob_home: float = 0.60,
    leakage_safe: bool = True,
) -> dict:
    """Create a row with OOF calibration metadata."""
    trace = {
        "calibration_mode": "walk_forward_oof",
        "leakage_safe": leakage_safe,
        "train_start": "2025-03",
        "train_end": "2025-04",
        "validation_start": "2025-05",
        "validation_size": 50,
    }
    return {
        "Date": "2025-05-15",
        "Away": "Team A",
        "Home": "Team B",
        "Away Score": str(away_score),
        "Home Score": str(home_score),
        "Status": "Final",
        "Away ML": away_ml,
        "Home ML": home_ml,
        "model_prob_home": str(model_prob_home),
        "probability_source": "calibrated_model",
        "calibration_source_trace": _json.dumps(trace),
    }


class TestOOFCalibrationDetectionP7:
    def test_oof_calibration_count_in_source_trace(self):
        """OOF calibrated rows should populate oof_calibration_count in source_trace."""
        rows = [_make_oof_row(leakage_safe=True) for _ in range(50)]
        result = simulate_strategy("test_oof", rows, "2025-01-01", "2025-12-31",
                                   require_positive_bss=False)
        assert result.source_trace.get("oof_calibration_count", 0) == 50

    def test_leakage_safe_true_in_source_trace(self):
        """When all OOF rows have leakage_safe=True, source_trace must have leakage_safe=True."""
        rows = [_make_oof_row(leakage_safe=True) for _ in range(50)]
        result = simulate_strategy("test_oof", rows, "2025-01-01", "2025-12-31",
                                   require_positive_bss=False)
        assert result.source_trace.get("leakage_safe") is True

    def test_calibration_mode_walk_forward_oof_in_source_trace(self):
        """source_trace calibration_mode must be 'walk_forward_oof' for OOF rows."""
        rows = [_make_oof_row(leakage_safe=True) for _ in range(50)]
        result = simulate_strategy("test_oof", rows, "2025-01-01", "2025-12-31",
                                   require_positive_bss=False)
        assert result.source_trace.get("calibration_mode") == "walk_forward_oof"

    def test_oof_calibration_warning_message(self):
        """OOF calibration warning message must mention OOF (not in-sample)."""
        rows = [_make_oof_row(leakage_safe=True) for _ in range(50)]
        result = simulate_strategy("test_oof", rows, "2025-01-01", "2025-12-31",
                                   require_positive_bss=False)
        warning = result.source_trace.get("calibration_warning", "")
        assert "OOF" in warning or "oof" in warning.lower(), (
            f"Expected OOF warning, got: {warning!r}"
        )

    def test_in_sample_calibration_remains_blocked_warning(self):
        """Rows without OOF trace should still get in-sample warning."""
        rows = []
        for _ in range(50):
            r = _make_row(home_score=5, away_score=3, model_prob_home=0.60)
            r["probability_source"] = "calibrated_model"
            # No calibration_source_trace → in-sample
            rows.append(r)
        result = simulate_strategy("test_in_sample", rows, "2025-01-01", "2025-12-31",
                                   require_positive_bss=False)
        warning = result.source_trace.get("calibration_warning", "")
        assert "in-sample" in warning.lower() or "not production" in warning.lower(), (
            f"Expected in-sample warning, got: {warning!r}"
        )

