from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from wbc_backend.betting.risk_control import BankrollState
from wbc_backend.domain.schemas import (
    BetRecommendation,
    Matchup,
    PredictionResult,
    SubModelResult,
    TeamSnapshot,
)
from wbc_backend.pipeline.service import PredictionService
from wbc_backend.strategy.bet_decision_flow import (
    DecisionContext,
    GateResult,
    gate_consensus,
    gate_timing,
)


def _make_team(code: str) -> TeamSnapshot:
    return TeamSnapshot(
        team=code,
        elo=1500.0,
        batting_woba=0.320,
        batting_ops_plus=105.0,
        pitching_fip=3.90,
        pitching_whip=1.20,
        pitching_stuff_plus=102.0,
        der=0.690,
        bullpen_depth=6.0,
        pitch_limit=80,
    )


def _make_matchup() -> Matchup:
    return Matchup(
        game_id="TEST_GATED_PIPELINE",
        tournament="WBC",
        game_time_utc="2026-03-15T10:00:00Z",
        home=_make_team("JPN"),
        away=_make_team("TPE"),
    )


def _make_prediction() -> PredictionResult:
    return PredictionResult(
        game_id="TEST_GATED_PIPELINE",
        home_win_prob=0.62,
        away_win_prob=0.38,
        expected_home_runs=4.8,
        expected_away_runs=3.6,
        x_factors=[],
        diagnostics={
            "tsl_matchup": {
                "in_snapshot": True,
                "market_codes": ["MNL", "OU"],
                "is_fresh": True,
            }
        },
        sub_model_results=[
            SubModelResult("elo", 0.62, 0.38),
            SubModelResult("bayesian", 0.60, 0.40),
            SubModelResult("poisson", 0.59, 0.41),
        ],
        confidence_score=0.72,
    )


def test_gate_consensus_handles_team_code_side():
    ctx = DecisionContext(
        prediction=_make_prediction(),
        sub_model_probs={"elo": 0.62, "bayesian": 0.60, "poisson": 0.59},
        market_implied_prob=0.48,
        model_prob=0.62,
        odds=2.08,
        home_code="JPN",
        away_code="TPE",
    )
    bet = BetRecommendation(
        market="ML",
        side="JPN",
        line=None,
        sportsbook="TSL",
        source_type="tsl",
        win_probability=0.62,
        implied_probability=0.48,
        ev=0.10,
        edge=0.14,
        kelly_fraction=0.04,
        stake_fraction=0.02,
        stake_amount=2000.0,
        confidence=0.72,
    )

    decision = gate_consensus(ctx, bet)
    assert decision.result == GateResult.PASS


def test_prediction_service_applies_bet_decision_flow_delay_and_caps_stake():
    service = PredictionService.__new__(PredictionService)
    service.bankroll = BankrollState(
        initial=100_000.0,
        current=100_000.0,
        peak=100_000.0,
        daily_start=100_000.0,
    )

    gated = service._apply_bet_decision_flow(
        top_bets=[
            BetRecommendation(
                market="ML",
                side="JPN",
                line=None,
                sportsbook="TSL",
                source_type="tsl",
                win_probability=0.62,
                implied_probability=0.48,
                ev=0.10,
                edge=0.14,
                kelly_fraction=0.04,
                stake_fraction=0.02,
                stake_amount=2000.0,
                confidence=0.72,
            )
        ],
        matchup=_make_matchup(),
        pred=_make_prediction(),
        adjusted_home_prob=0.62,
        market_result={"n_steam_moves": 1, "market_weight_applied": 0.2},
    )

    assert len(gated) == 1
    assert gated[0].approved is True
    assert gated[0].decision_timing == "DELAY_15MIN"
    assert gated[0].delay_minutes == 15
    assert gated[0].stake_fraction <= 0.02
    assert "gate_summary=" in gated[0].reason


def test_gate_timing_delays_when_tsl_market_not_covered():
    ctx = DecisionContext(
        prediction=_make_prediction(),
        sub_model_probs={"elo": 0.62, "bayesian": 0.60, "poisson": 0.59},
        market_implied_prob=0.48,
        model_prob=0.62,
        odds=2.08,
        home_code="JPN",
        away_code="TPE",
        market_support_state="tsl_unlisted_market",
    )
    bet = BetRecommendation(
        market="RL",
        side="JPN",
        line=-1.5,
        sportsbook="TSL",
        source_type="tsl",
        win_probability=0.62,
        implied_probability=0.48,
        ev=0.10,
        edge=0.14,
        kelly_fraction=0.04,
        stake_fraction=0.02,
        stake_amount=2000.0,
        confidence=0.72,
    )

    decision = gate_timing(ctx, bet)
    assert decision.result == GateResult.MODIFY
    assert decision.modified_value == 30


def test_gate_timing_delays_when_tsl_snapshot_stale():
    ctx = DecisionContext(
        prediction=_make_prediction(),
        sub_model_probs={"elo": 0.62, "bayesian": 0.60, "poisson": 0.59},
        market_implied_prob=0.48,
        model_prob=0.62,
        odds=2.08,
        home_code="JPN",
        away_code="TPE",
        market_support_state="tsl_stale",
    )
    bet = BetRecommendation(
        market="ML",
        side="JPN",
        line=None,
        sportsbook="TSL",
        source_type="tsl",
        win_probability=0.62,
        implied_probability=0.48,
        ev=0.10,
        edge=0.14,
        kelly_fraction=0.04,
        stake_fraction=0.02,
        stake_amount=2000.0,
        confidence=0.72,
    )

    decision = gate_timing(ctx, bet)
    assert decision.result == GateResult.MODIFY
    assert decision.modified_value == 15
