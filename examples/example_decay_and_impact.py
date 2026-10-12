#!/usr/bin/env python3
"""
Example Usage — Edge Decay Predictor & Market Impact Simulator
================================================================
Demonstrates standalone usage of both modules plus the integrated
decision engine pipeline.

Run:
    python3 examples/example_decay_and_impact.py
"""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from wbc_backend.intelligence.edge_decay_predictor import (
    EdgeDecayInput,
    predict_edge_decay,
    UrgencyLevel,
)
from wbc_backend.intelligence.market_impact_simulator import (
    MarketImpactInput,
    simulate_market_impact,
    ExecutionStrategy,
)
from wbc_backend.intelligence.decision_engine import (
    InstitutionalDecisionEngine,
    format_decision_report,
)


def demo_edge_decay() -> None:
    """Standalone edge decay prediction."""
    print("=" * 60)
    print("  EDGE DECAY PREDICTOR — Standalone Demo")
    print("=" * 60)

    inp = EdgeDecayInput(
        odds_velocity=0.008,
        odds_acceleration=0.002,
        liquidity_score=0.6,
        book_count=4,
        spread_width=0.035,
        ensemble_stddev=0.015,
        ensemble_mean_drift=0.005,
        prediction_momentum=0.003,
        sharp_money_pct=0.20,
        steam_moves=1,
        reverse_line_moves=0,
        time_to_game_seconds=3600 * 8,     # 8 hours out
        past_similar_edges=3,
        historical_decay_times=[450, 520, 380, 600],
        league="WBC",
        edge_pct=0.05,
        edge_score=78.0,
        seed=42,
    )

    forecast = predict_edge_decay(inp)

    print(f"  Half-life:      {forecast.half_life_seconds:.0f} seconds "
          f"({forecast.half_life_seconds / 60:.1f} min)")
    print(f"  Urgency:        {forecast.urgency_level.value}")
    print(f"  Confidence:     {forecast.confidence_score:.0f} / 100")
    print(f"  Bounds:         [{forecast.lower_bound_seconds:.0f}s, "
          f"{forecast.upper_bound_seconds:.0f}s]")
    print(f"  Sub-models:")
    print(f"    Survival:     {forecast.survival_half_life:.0f}s")
    print(f"    Hazard:       {forecast.hazard_half_life:.0f}s")
    print(f"    Volatility:   {forecast.volatility_half_life:.0f}s")
    print(f"  Decay curve:    {forecast.decay_curve[:5]} ... "
          f"{forecast.decay_curve[-3:]}")
    print()


def demo_market_impact() -> None:
    """Standalone market impact simulation."""
    print("=" * 60)
    print("  MARKET IMPACT SIMULATOR — Standalone Demo")
    print("=" * 60)

    inp = MarketImpactInput(
        liquidity_score=0.5,
        regime="LIQUID_MARKET",
        n_books=4,
        avg_limit_usd=5000.0,
        current_odds=2.10,
        intended_stake_usd=300.0,
        bet_type="ML",
        bankroll=10000.0,
        hours_to_game=12.0,
        book_tier="generic",
        sharp_detection_history=0.1,
        edge_pct=0.045,
        seed=42,
        n_simulations=200,
    )

    report = simulate_market_impact(inp)

    print(f"  Expected Slippage:  {report.expected_slippage:.5f} "
          f"({report.expected_slippage * 100:.3f}%)")
    print(f"  Impact Probability: {report.impact_probability:.1%}")
    print(f"  Odds After Bet:     {report.odds_after_bet:.4f}")
    print(f"  Books That Move:    {report.books_that_move}")
    print(f"  Exec Risk Score:    {report.execution_risk_score:.1f} / 100")
    print(f"  Best Strategy:      {report.execution_strategy.value}")
    print(f"  Reason:             {report.strategy_reasoning}")
    print(f"  Max Safe Bet:       ${report.max_safe_bet_size:.0f}")
    print(f"  Recommended Split:  {report.recommended_split_count} books")
    print(f"  Detection Prob:     {report.detection_probability:.1%}")
    print(f"  Slippage P10/P50/P90: {report.slippage_p10:.5f} / "
          f"{report.slippage_p50:.5f} / {report.slippage_p90:.5f}")
    print(f"  N Simulations:      {report.n_simulations}")
    print()


def demo_full_pipeline() -> None:
    """Full decision engine pipeline with both new modules."""
    print("=" * 60)
    print("  FULL PIPELINE — Decision Engine with Decay + Impact")
    print("=" * 60)

    engine = InstitutionalDecisionEngine(bankroll=10000)
    report = engine.analyze_match(
        match_id="WBC2026_TPE_JPN",
        match_label="TPE vs JPN",
        sub_model_probs={
            "elo": 0.68, "bayesian": 0.70, "poisson": 0.67,
            "gbm": 0.69, "ensemble": 0.68,
        },
        calibrated_prob=0.68,
        odds_home=2.15,
        odds_away=1.72,
        brier_score=0.21,
        platt_a=1.02,
        platt_b=-0.005,
        sharp_signal_count=1,
        market_liquidity_score=0.55,
        n_sportsbooks=4,
        sharp_direction_agrees=True,
        closing_line_history=[0.01, 0.015, -0.005, 0.02],
        recent_model_probs=[0.66, 0.67, 0.68, 0.68],
        # Decay params
        odds_velocity=0.003,
        odds_acceleration=0.001,
        sharp_money_pct=0.18,
        past_similar_edges=2,
        historical_decay_times=[600, 700, 550],
        league="WBC",
        # Impact params
        avg_limit_usd=5000,
        book_tier="generic",
        sharp_detection_history=0.05,
    )

    print(format_decision_report(report))
    print()

    # Print new fields explicitly
    print("  --- NEW MODULE OUTPUTS ---")
    print(f"  Decay Half-life: {report.decay_half_life:.0f}s "
          f"({report.decay_half_life / 60:.1f} min)")
    print(f"  Decay Urgency:   {report.decay_urgency}")
    print(f"  Decay Conf:      {report.decay_confidence:.0f}")
    print(f"  Slippage:        {report.expected_slippage:.5f}")
    print(f"  Exec Risk:       {report.execution_risk_score:.1f}")
    print(f"  Exec Strategy:   {report.execution_strategy}")
    print(f"  Max Safe:        ${report.max_safe_bet_size:.0f}")
    print(f"  Split Count:     {report.recommended_split_count}")


if __name__ == "__main__":
    demo_edge_decay()
    demo_market_impact()
    demo_full_pipeline()
