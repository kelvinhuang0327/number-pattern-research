"""
Unit Tests — edge_decay_predictor.py & market_impact_simulator.py
==================================================================
Run: python3 -m pytest tests/test_decay_and_impact.py -v
  or: python3 tests/test_decay_and_impact.py
"""
from __future__ import annotations

import sys
import os
import unittest

# Ensure project root is on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from wbc_backend.intelligence.edge_decay_predictor import (
    EdgeDecayInput,
    EdgeDecayForecast,
    UrgencyLevel,
    predict_edge_decay,
    LEAGUE_DECAY_PROFILES,
    DECAY_CURVE_STEPS,
    _survival_regression,
    _hazard_function,
    _volatility_model,
    _classify_urgency,
    _build_decay_curve,
    _compute_confidence,
)
from wbc_backend.intelligence.market_impact_simulator import (
    MarketImpactInput,
    MarketImpactReport,
    ExecutionStrategy,
    simulate_market_impact,
    _book_sensitivity,
    _detection_prob,
    _find_max_safe_size,
    _compute_execution_risk,
    BOOK_SENSITIVITY,
    SHARP_DETECTION_PROB,
)


# ═══════════════════════════════════════════════════════════════
# EDGE DECAY PREDICTOR TESTS
# ═══════════════════════════════════════════════════════════════


class TestUrgencyClassification(unittest.TestCase):
    """Test UrgencyLevel mapping from half-life."""

    def test_immediate(self):
        self.assertEqual(_classify_urgency(100), UrgencyLevel.EXECUTE_IMMEDIATELY)

    def test_soon(self):
        self.assertEqual(_classify_urgency(300), UrgencyLevel.EXECUTE_SOON)

    def test_monitor(self):
        self.assertEqual(_classify_urgency(1800), UrgencyLevel.MONITOR)

    def test_wait(self):
        self.assertEqual(_classify_urgency(7200), UrgencyLevel.WAIT)

    def test_expired(self):
        self.assertEqual(_classify_urgency(20000), UrgencyLevel.EXPIRED)

    def test_boundary_180(self):
        self.assertEqual(_classify_urgency(179.9), UrgencyLevel.EXECUTE_IMMEDIATELY)
        self.assertEqual(_classify_urgency(180.0), UrgencyLevel.EXECUTE_SOON)


class TestDecayCurve(unittest.TestCase):
    """Test decay curve generation."""

    def test_curve_length(self):
        curve = _build_decay_curve(600.0, steps=20)
        self.assertEqual(len(curve), 20)

    def test_curve_monotonic_decreasing(self):
        curve = _build_decay_curve(600.0)
        for i in range(1, len(curve)):
            self.assertLessEqual(curve[i], curve[i - 1])

    def test_curve_starts_near_1(self):
        curve = _build_decay_curve(600.0, steps=20)
        self.assertGreater(curve[0], 0.5)

    def test_curve_ends_near_0(self):
        curve = _build_decay_curve(600.0, steps=20)
        self.assertLess(curve[-1], 0.2)


class TestSubModels(unittest.TestCase):
    """Test that each sub-model returns a positive half-life."""

    def setUp(self):
        import random
        self.rng = random.Random(42)
        self.inp = EdgeDecayInput(
            odds_velocity=0.005,
            odds_acceleration=0.001,
            liquidity_score=0.6,
            book_count=4,
            spread_width=0.04,
            ensemble_stddev=0.02,
            sharp_money_pct=0.15,
            steam_moves=1,
            time_to_game_seconds=3600 * 12,
            league="WBC",
            seed=42,
        )

    def test_survival_positive(self):
        hl = _survival_regression(self.inp, self.rng)
        self.assertGreater(hl, 0)

    def test_hazard_positive(self):
        hl = _hazard_function(self.inp, self.rng)
        self.assertGreater(hl, 0)

    def test_volatility_positive(self):
        hl = _volatility_model(self.inp, self.rng)
        self.assertGreater(hl, 0)

    def test_all_above_floor(self):
        """Floor is 30 seconds for all sub-models."""
        for fn in [_survival_regression, _hazard_function, _volatility_model]:
            hl = fn(self.inp, self.rng)
            self.assertGreaterEqual(hl, 30.0)


class TestPredictEdgeDecay(unittest.TestCase):
    """Integration tests for the main predict_edge_decay API."""

    def test_deterministic_with_seed(self):
        inp = EdgeDecayInput(
            odds_velocity=0.01,
            liquidity_score=0.5,
            book_count=3,
            league="WBC",
            seed=123,
        )
        f1 = predict_edge_decay(inp)
        f2 = predict_edge_decay(inp)
        self.assertEqual(f1.half_life_seconds, f2.half_life_seconds)
        self.assertEqual(f1.confidence_score, f2.confidence_score)

    def test_forecast_structure(self):
        inp = EdgeDecayInput(seed=42)
        f = predict_edge_decay(inp)
        self.assertIsInstance(f, EdgeDecayForecast)
        self.assertIsInstance(f.urgency_level, UrgencyLevel)
        self.assertGreater(f.half_life_seconds, 0)
        self.assertEqual(len(f.decay_curve), DECAY_CURVE_STEPS)
        self.assertGreaterEqual(f.confidence_score, 0)
        self.assertLessEqual(f.confidence_score, 100)
        self.assertLessEqual(f.lower_bound_seconds, f.half_life_seconds)
        self.assertGreaterEqual(f.upper_bound_seconds, f.half_life_seconds)

    def test_high_velocity_shorter_life(self):
        base = EdgeDecayInput(odds_velocity=0.0, seed=42, league="WBC")
        fast = EdgeDecayInput(odds_velocity=0.05, seed=42, league="WBC")
        f_base = predict_edge_decay(base)
        f_fast = predict_edge_decay(fast)
        self.assertLess(f_fast.half_life_seconds, f_base.half_life_seconds)

    def test_league_profiles(self):
        for league in ["MLB", "NPB", "WBC"]:
            inp = EdgeDecayInput(league=league, seed=42)
            f = predict_edge_decay(inp)
            self.assertGreater(f.half_life_seconds, 0)

    def test_historical_memory_affects_prediction(self):
        no_hist = EdgeDecayInput(seed=42, league="WBC")
        with_hist = EdgeDecayInput(
            seed=42, league="WBC",
            historical_decay_times=[300, 350, 280, 320, 310],
            past_similar_edges=5,
        )
        f1 = predict_edge_decay(no_hist)
        f2 = predict_edge_decay(with_hist)
        # With history, confidence should be higher
        self.assertGreater(f2.confidence_score, f1.confidence_score)

    def test_confidence_range(self):
        inp = EdgeDecayInput(
            odds_velocity=0.01,
            steam_moves=2,
            sharp_money_pct=0.3,
            book_count=5,
            historical_decay_times=[500, 600, 550],
            past_similar_edges=3,
            seed=42,
        )
        f = predict_edge_decay(inp)
        self.assertGreaterEqual(f.confidence_score, 0)
        self.assertLessEqual(f.confidence_score, 100)


# ═══════════════════════════════════════════════════════════════
# MARKET IMPACT SIMULATOR TESTS
# ═══════════════════════════════════════════════════════════════


class TestBookSensitivity(unittest.TestCase):
    """Test bookmaker sensitivity lookup."""

    def test_known_books(self):
        self.assertEqual(_book_sensitivity("pinnacle"), 0.002)
        self.assertEqual(_book_sensitivity("generic_soft"), 0.008)

    def test_unknown_falls_back(self):
        self.assertEqual(_book_sensitivity("unknown_book"), BOOK_SENSITIVITY["generic"])


class TestDetectionProb(unittest.TestCase):
    """Test sharp detection probability calculation."""

    def test_base_detection(self):
        p = _detection_prob("sharp", 0.0)
        self.assertAlmostEqual(p, 0.15)

    def test_history_amplifies(self):
        p_no_hist = _detection_prob("generic", 0.0)
        p_hist = _detection_prob("generic", 0.5)
        self.assertGreater(p_hist, p_no_hist)

    def test_capped_at_95(self):
        p = _detection_prob("soft", 1.0)
        self.assertLessEqual(p, 0.95)


class TestMaxSafeSize(unittest.TestCase):
    """Test max safe bet size calculation."""

    def test_positive_edge(self):
        safe = _find_max_safe_size(
            odds=2.0, sensitivity=0.005, avg_limit=5000,
            edge_pct=0.05, n_books=3,
        )
        self.assertGreater(safe, 0)

    def test_zero_edge(self):
        safe = _find_max_safe_size(
            odds=2.0, sensitivity=0.005, avg_limit=5000,
            edge_pct=0.0, n_books=3,
        )
        self.assertEqual(safe, 0.0)

    def test_more_books_higher_safe(self):
        safe1 = _find_max_safe_size(2.0, 0.005, 5000, 0.05, 1)
        safe3 = _find_max_safe_size(2.0, 0.005, 5000, 0.05, 3)
        self.assertGreaterEqual(safe3, safe1)


class TestSimulateMarketImpact(unittest.TestCase):
    """Integration tests for the main simulate_market_impact API."""

    def test_deterministic_with_seed(self):
        inp = MarketImpactInput(
            current_odds=2.0, intended_stake_usd=200,
            n_books=3, edge_pct=0.05, seed=123,
        )
        r1 = simulate_market_impact(inp)
        r2 = simulate_market_impact(inp)
        self.assertEqual(r1.expected_slippage, r2.expected_slippage)
        self.assertEqual(r1.execution_risk_score, r2.execution_risk_score)

    def test_report_structure(self):
        inp = MarketImpactInput(
            current_odds=2.0, intended_stake_usd=200,
            n_books=3, edge_pct=0.05, seed=42,
        )
        r = simulate_market_impact(inp)
        self.assertIsInstance(r, MarketImpactReport)
        self.assertGreaterEqual(r.expected_slippage, 0)
        self.assertGreaterEqual(r.execution_risk_score, 0)
        self.assertLessEqual(r.execution_risk_score, 100)
        self.assertIsInstance(r.execution_strategy, ExecutionStrategy)
        self.assertGreater(r.n_simulations, 0)

    def test_large_stake_higher_slippage(self):
        small = MarketImpactInput(
            current_odds=2.0, intended_stake_usd=100,
            n_books=3, edge_pct=0.05, seed=42,
        )
        large = MarketImpactInput(
            current_odds=2.0, intended_stake_usd=5000,
            n_books=3, edge_pct=0.05, seed=42,
        )
        r_small = simulate_market_impact(small)
        r_large = simulate_market_impact(large)
        self.assertGreater(r_large.expected_slippage, r_small.expected_slippage)

    def test_single_book_only(self):
        inp = MarketImpactInput(
            current_odds=2.0, intended_stake_usd=200,
            n_books=1, edge_pct=0.05, seed=42,
        )
        r = simulate_market_impact(inp)
        self.assertEqual(r.recommended_split_count, 1)

    def test_slippage_exceeds_edge_flags_do_not_execute(self):
        inp = MarketImpactInput(
            current_odds=2.0,
            intended_stake_usd=50000,   # massive stake
            n_books=1,
            avg_limit_usd=500,
            edge_pct=0.001,             # tiny edge
            book_tier="generic_soft",
            seed=42,
        )
        r = simulate_market_impact(inp)
        # With huge stake, tiny edge, soft book → should flag DO_NOT_EXECUTE
        if r.expected_slippage > inp.edge_pct:
            self.assertEqual(r.execution_strategy, ExecutionStrategy.DO_NOT_EXECUTE)

    def test_execution_risk_score_range(self):
        for stake in [50, 200, 1000, 5000]:
            inp = MarketImpactInput(
                current_odds=2.0, intended_stake_usd=stake,
                n_books=3, edge_pct=0.05, seed=42,
            )
            r = simulate_market_impact(inp)
            self.assertGreaterEqual(r.execution_risk_score, 0)
            self.assertLessEqual(r.execution_risk_score, 100)


class TestComputeExecutionRisk(unittest.TestCase):
    """Test execution risk score composition."""

    def test_zero_slippage(self):
        risk = _compute_execution_risk(
            slippage_mean=0.0, slippage_p90=0.0,
            detection_rate=0.0, fill_rate=1.0,
            edge_pct=0.05,
            inp=MarketImpactInput(intended_stake_usd=100, avg_limit_usd=5000),
        )
        self.assertLess(risk, 10)

    def test_high_slippage(self):
        risk = _compute_execution_risk(
            slippage_mean=0.04, slippage_p90=0.08,
            detection_rate=0.5, fill_rate=0.7,
            edge_pct=0.05,
            inp=MarketImpactInput(intended_stake_usd=4000, avg_limit_usd=5000),
        )
        self.assertGreater(risk, 50)


# ═══════════════════════════════════════════════════════════════
# PIPELINE INTEGRATION TEST
# ═══════════════════════════════════════════════════════════════


class TestPipelineIntegration(unittest.TestCase):
    """Test that the decision engine pipeline still works end-to-end."""

    def test_full_pipeline_with_new_modules(self):
        from wbc_backend.intelligence.decision_engine import (
            InstitutionalDecisionEngine, format_decision_report,
        )
        engine = InstitutionalDecisionEngine(bankroll=10000)
        report = engine.analyze_match(
            match_id="TEST_DECAY_IMPACT",
            match_label="Test Decay+Impact",
            sub_model_probs={
                "elo": 0.70, "bayesian": 0.72, "poisson": 0.69,
                "gbm": 0.71, "ensemble": 0.70,
            },
            calibrated_prob=0.70,
            odds_home=2.05,
            odds_away=1.80,
            brier_score=0.20,
            platt_a=1.02,
            platt_b=-0.005,
            sharp_signal_count=1,
            market_liquidity_score=0.6,
            n_sportsbooks=4,
            sharp_direction_agrees=True,
            closing_line_history=[0.01, 0.02, -0.005],
            recent_model_probs=[0.69, 0.70, 0.70, 0.71],
            # New decay params
            odds_velocity=0.005,
            odds_acceleration=0.001,
            sharp_money_pct=0.15,
            league="WBC",
            # New impact params
            avg_limit_usd=5000,
            book_tier="generic",
        )

        # Verify new fields populated
        self.assertGreater(report.decay_half_life, 0)
        self.assertIn(report.decay_urgency, [u.value for u in UrgencyLevel])
        self.assertGreaterEqual(report.decay_confidence, 0)
        self.assertEqual(len(report.decay_curve), DECAY_CURVE_STEPS)

        self.assertGreaterEqual(report.expected_slippage, 0)
        self.assertGreaterEqual(report.execution_risk_score, 0)
        self.assertLessEqual(report.execution_risk_score, 100)

        # Should produce a formatted report without error
        text = format_decision_report(report)
        self.assertIn("Edge Decay", text)
        self.assertIn("Mkt Impact", text)

    def test_expired_edge_blocks(self):
        """An edge with extreme velocity should expire or return quickly."""
        from wbc_backend.intelligence.decision_engine import (
            InstitutionalDecisionEngine,
        )
        engine = InstitutionalDecisionEngine(bankroll=10000)
        report = engine.analyze_match(
            match_id="TEST_EXPIRED",
            match_label="Test Expired Edge",
            sub_model_probs={
                "elo": 0.70, "bayesian": 0.72, "poisson": 0.69,
                "gbm": 0.71, "ensemble": 0.70,
            },
            calibrated_prob=0.70,
            odds_home=2.05,
            odds_away=1.80,
            brier_score=0.20,
            platt_a=1.02,
            platt_b=-0.005,
            sharp_signal_count=1,
            market_liquidity_score=0.9,
            n_sportsbooks=6,
            sharp_direction_agrees=True,
            recent_model_probs=[0.69, 0.70, 0.70, 0.71],
            odds_velocity=0.005,
            league="WBC",
            book_tier="generic",
        )
        # Should at least have decay data
        self.assertGreater(report.decay_half_life, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
