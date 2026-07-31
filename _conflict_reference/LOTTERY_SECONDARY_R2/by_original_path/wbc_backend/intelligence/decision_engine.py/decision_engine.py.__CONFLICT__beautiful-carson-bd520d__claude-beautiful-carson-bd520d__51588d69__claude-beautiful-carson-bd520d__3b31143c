"""
Phase 8 — Institutional Decision Engine
==========================================
Integration layer that chains all 7 intelligence modules into a single
decision pipeline.

Pipeline flow:
  1.  Edge Validator          → Is there a real edge?
  1b. Edge Realism Filter     → Can the edge survive real-market execution?
  1c. Edge Decay Predictor    → How long will this edge last?
  1d. Line Movement Predictor → Should we bet now or delay?
  1e. Market Impact Simulator → Will our bet move the line against us?
  2.  Regime Classifier       → What type of market is this?
  3.  Sharpness Monitor       → Are we still sharp?
  4.  Bet Selector            → Does this bet pass all gates?
  5.  Position Sizing AI      → How much to bet?
  6.  Risk Engine             → Final risk approval
  7.  Meta Learning           → Feed back results

Produces a DECISION REPORT per match:
  ┌────────────────────────────────────────────┐
  │ Match:           TPE vs JPN                │
  │ Edge Score:      78.4                      │
  │ Market Regime:   PUBLIC_BIAS (84%)         │
  │ Recommended Bet: ML HOME @ 2.35           │
  │ Bet Size:        1.8% ($180)              │
  │ Confidence:      STRONG                    │
  │ Risk Level:      GREEN                     │
  │ Decision:        ✓ APPROVED                │
  └────────────────────────────────────────────┘

Absolute rules:
  × NO universal betting (every game gets an independent decision)
  × NO single-model betting (ensemble consensus required)
  × NO ignoring market structure (regime must be checked)
"""
from __future__ import annotations

import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

from wbc_backend.intelligence.edge_validator import (
    compute_edge_score,
)
from wbc_backend.intelligence.edge_realism_filter import (
    RealismInput,
    assess_edge_realism,
)
from wbc_backend.intelligence.regime_classifier import (
    RegimeSignals,
    classify_market_regime,
    build_signals_from_microstructure,
)
from wbc_backend.intelligence.bet_selector import (
    BetCandidate,
    evaluate_bet_candidate,
    select_bets,
)
from wbc_backend.intelligence.position_sizing_ai import (
    SizingInput,
    compute_position_size,
)
from wbc_backend.intelligence.sharpness_monitor import (
    SharpnessMonitor,
)
from wbc_backend.intelligence.risk_engine import (
    RiskEngine,
)
from wbc_backend.intelligence.meta_learning_loop import (
    ModelPerformanceEntry,
    initialize_meta_state,
    record_prediction,
    record_game,
    should_retrain,
    execute_retrain,
    get_model_weights,
    detect_regime_shift,
    get_meta_summary,
)
from wbc_backend.intelligence.edge_decay_predictor import (
    EdgeDecayInput,
    UrgencyLevel,
    predict_edge_decay,
)
from wbc_backend.intelligence.line_movement_predictor import (
    LineMovementPredictor,
    LineMovementInput,
    TimingAction,
)
from wbc_backend.intelligence.market_impact_simulator import (
    MarketImpactInput,
    simulate_market_impact,
)
from wbc_backend.intelligence.fake_move_detector import (
    FakeMoveInput,
    FakeAction,
    detect_fake_move,
)
from wbc_backend.intelligence.cl_bias_corrector import (
    ClosingLineBiasCorrector,
)


# ─── Decision Report ───────────────────────────────────────────────────────

@dataclass
class BetDecision:
    """Single bet decision within a match."""
    bet_type: str = ""                 # ML / RL / OU / F5
    side: str = ""                     # HOME / AWAY / OVER / UNDER
    odds: float = 1.0
    edge_pct: float = 0.0
    adjusted_edge: float = 0.0
    bet_size_pct: float = 0.0
    bet_amount: float = 0.0
    sizing_strategy: str = ""
    approved: bool = False
    confidence_tier: str = ""


@dataclass
class DecisionReport:
    """Complete decision report for one match."""
    # Match identification
    match_id: str = ""
    match_label: str = ""
    timestamp: float = 0.0

    # Phase 1: Edge
    edge_score: float = 0.0
    edge_tier: str = "FORBIDDEN"
    edge_valid: bool = False
    edge_details: str = ""

    # Phase 1b: Edge Realism
    real_edge_score: float = 0.0
    real_edge_label: str = "FAKE_EDGE"
    realism_tradeable: bool = False
    realism_details: dict[str, str] = field(default_factory=dict)

    # Phase 1c: Edge Decay
    decay_half_life: float = 0.0
    decay_urgency: str = "MONITOR"
    decay_confidence: float = 0.0
    decay_curve: list[float] = field(default_factory=list)
    decay_lower_bound: float = 0.0
    decay_upper_bound: float = 0.0

    # Phase 1d: Line Movement
    line_movement_direction: str = "STABLE"
    line_movement_confidence: float = 0.0
    expected_closing_odds: float = 0.0
    expected_clv: float = 0.0
    timing_action: str = "BET_NOW"
    timing_reasoning: str = ""
    optimal_delay_minutes: float = 0.0

    # Phase 1e: Market Impact
    expected_slippage: float = 0.0
    impact_probability: float = 0.0
    odds_after_bet: float = 0.0
    execution_risk_score: float = 0.0
    execution_strategy: str = "SINGLE_BOOK"
    max_safe_bet_size: float = 0.0
    recommended_split_count: int = 1
    slippage_exceeds_edge: bool = False

    # Phase 2: Regime
    market_regime: str = "LIQUID_MARKET"
    regime_confidence: float = 0.0
    regime_action: str = ""

    # Phase 2b: Fake Move
    fake_move_score: float = 0.0
    fake_move_type: str = "LEGITIMATE"
    fake_move_action: str = "PROCEED"
    fake_confidence_mult: float = 1.0

    # Phase 3 + 5: Selection & Sizing
    bets: list[BetDecision] = field(default_factory=list)
    total_exposure_pct: float = 0.0

    # Phase 6: Sharpness
    sharpness_level: str = "EVEN_WITH_MARKET"
    trailing_clv: float = 0.0
    sharpness_ok: bool = True

    # Phase 7: Risk
    risk_level: str = "GREEN"
    risk_approved: bool = True
    risk_warnings: list[str] = field(default_factory=list)

    # Overall decision
    decision: str = "NO_BET"           # BET / NO_BET / WATCH
    confidence: str = "LOW"            # LOW / MODERATE / STRONG / ELITE
    reasoning: list[str] = field(default_factory=list)

    # Meta
    model_weights: dict[str, float] = field(default_factory=dict)
    meta_summary: dict[str, Any] = field(default_factory=dict)


# ─── Institutional Decision Engine ─────────────────────────────────────────

class InstitutionalDecisionEngine:
    """
    The master decision engine that orchestrates all 7 intelligence phases.

    Usage:
        engine = InstitutionalDecisionEngine(bankroll=10000)
        report = engine.analyze_match(match_data)
        # report contains the full DECISION REPORT
    """

    def __init__(
        self,
        bankroll: float = 10000.0,
        model_names: list[str] | None = None,
    ):
        if model_names is None:
            model_names = ["elo", "bayesian", "poisson", "gradient_boosting", "ensemble"]

        # Initialize all sub-systems
        self.sharpness = SharpnessMonitor()
        self.risk = RiskEngine(initial_bankroll=bankroll)
        self.meta = initialize_meta_state(model_names)
        self.line_predictor = LineMovementPredictor()
        self.cl_corrector = ClosingLineBiasCorrector()

        # Trailing data for position sizing
        self._trailing_pnl: list[float] = []
        self._trailing_sizes: list[float] = []
        self._trailing_strategies: list[str] = []
        self._recent_regimes: list[str] = []

        # Band ROI lookup from backtest data
        self._band_roi_lookup = {
            "1.01-1.50": -0.05,
            "1.51-1.80": -0.03,
            "1.81-2.10": 0.0254,
            "2.11-2.60": 0.0151,
            "2.61-3.50": -0.04,
            "3.51+": -0.08,
        }
        self._executor = ThreadPoolExecutor(max_workers=4)

    def _run_phases_parallel(
        self,
        realism_fn, decay_fn, lm_fn, impact_fn,
    ) -> tuple:
        """
        Run Phases 1b/1c/1d/1e in parallel using threads.
        Returns (realism_report, decay_forecast, lm_result, impact_report).
        """
        futures = [
            self._executor.submit(realism_fn),
            self._executor.submit(decay_fn),
            self._executor.submit(lm_fn),
            self._executor.submit(impact_fn),
        ]
        return tuple(f.result() for f in futures)

    def analyze_match(  # noqa: C901
        self,
        match_id: str,
        match_label: str,
        # Model predictions
        sub_model_probs: dict[str, float],
        calibrated_prob: float,
        # Odds
        odds_home: float = 2.0,
        odds_away: float = 1.85,
        odds_over: float | None = None,
        odds_under: float | None = None,
        odds_f5_home: float | None = None,
        odds_f5_away: float | None = None,
        # Calibration info
        brier_score: float = 0.25,
        platt_a: float = 1.0,
        platt_b: float = 0.0,
        # Market signals
        regime_signals: RegimeSignals | None = None,
        micro_report: Any | None = None,
        public_pct: float = 0.5,
        hours_to_game: float = 24.0,
        # Context
        sharp_signal_count: int = 0,
        # Edge realism inputs
        market_liquidity_score: float = 0.5,
        line_movement_velocity: float = 0.0,
        opening_odds: float = 0.0,
        n_sportsbooks: int = 3,
        odds_spread_pct: float = 0.04,
        sharp_direction_agrees: bool = True,
        steam_moves: int = 0,
        reverse_line_moves: int = 0,
        closing_line_history: list[float] | None = None,
        recent_model_probs: list[float] | None = None,
        # Edge decay inputs
        odds_velocity: float = 0.0,
        odds_acceleration: float = 0.0,
        sharp_money_pct: float = 0.0,
        past_similar_edges: int = 0,
        historical_decay_times: list[float] | None = None,
        league: str = "WBC",
        # Market impact inputs
        avg_limit_usd: float = 5000.0,
        book_tier: str = "generic",
        sharp_detection_history: float = 0.0,
    ) -> DecisionReport:
        """
        Analyze a match through all 7 phases and produce a Decision Report.

        This is the main entry point. All parameters are pre-game data only.
        """
        report = DecisionReport(
            match_id=match_id,
            match_label=match_label,
            timestamp=time.time(),
        )

        probs_list = list(sub_model_probs.values())
        model_prob = sum(probs_list) / len(probs_list) if probs_list else 0.5

        # ════════════════════════════════════════════════════════
        # PHASE 1: Edge Validation
        # ════════════════════════════════════════════════════════
        # edge_validator uses a dict not a list
        sub_model_dict = sub_model_probs
        from wbc_backend.intelligence.edge_validator import get_odds_band_roi
        band_roi = get_odds_band_roi(odds_home)

        edge_report = compute_edge_score(
            sub_model_probs=sub_model_dict,
            ensemble_prob=calibrated_prob,
            market_odds=odds_home,
            model_brier=brier_score,
            calibration_a=platt_a,
            calibration_b=platt_b,
            sharp_signals=sharp_signal_count,
            line_movements=0,
            odds_band_roi=band_roi,
        )

        report.edge_score = edge_report.edge_score
        report.edge_tier = edge_report.tier
        report.edge_valid = edge_report.is_valid
        report.edge_details = (
            f"consensus={edge_report.consensus_score:.0f} "
            f"entropy={edge_report.entropy_score:.0f} "
            f"calibration={edge_report.calibration_score:.0f} "
            f"market={edge_report.market_efficiency_score:.0f}"
        )

        if not edge_report.is_valid:
            report.decision = "NO_BET"
            report.confidence = "LOW"
            report.reasoning.append(
                f"Edge score {edge_report.edge_score:.1f} below threshold — "
                f"tier={edge_report.tier}"
            )
            return report

        # ════════════════════════════════════════════════════════
        # PHASES 1b/1c/1d/1e: Run in parallel (§ P2 決策閘並行化)
        # ════════════════════════════════════════════════════════
        realism_input = RealismInput(
            model_probability=calibrated_prob,
            market_odds=odds_home,
            market_liquidity_score=market_liquidity_score,
            n_sportsbooks=n_sportsbooks,
            odds_spread_pct=odds_spread_pct,
            line_movement_velocity=line_movement_velocity,
            total_line_moves=0,
            opening_odds=opening_odds,
            hours_to_game=hours_to_game,
            sharp_money_signal=sharp_signal_count,
            sharp_direction_agrees=sharp_direction_agrees,
            steam_moves=steam_moves,
            reverse_line_moves=reverse_line_moves,
            closing_line_history=closing_line_history or [],
            recent_model_probs=recent_model_probs or [],
            intended_bet_pct=0.02,
            bankroll=self.risk.state.current_bankroll,
        )

        probs_std = statistics.stdev(probs_list) if len(probs_list) > 1 else 0.02
        drift_vals = recent_model_probs or []
        if len(drift_vals) >= 2:
            mean_drift_val = drift_vals[-1] - drift_vals[0]
            momentum_val = drift_vals[-1] - drift_vals[-2]
        else:
            mean_drift_val = 0.0
            momentum_val = 0.0

        edge_pct_raw = calibrated_prob - (1.0 / odds_home) if odds_home > 1 else 0.0

        decay_input = EdgeDecayInput(
            odds_velocity=odds_velocity,
            odds_acceleration=odds_acceleration,
            liquidity_score=market_liquidity_score,
            book_count=n_sportsbooks,
            spread_width=odds_spread_pct,
            ensemble_stddev=probs_std,
            ensemble_mean_drift=mean_drift_val,
            prediction_momentum=momentum_val,
            sharp_money_pct=sharp_money_pct,
            reverse_line_moves=reverse_line_moves,
            steam_moves=steam_moves,
            time_to_game_seconds=hours_to_game * 3600.0,
            past_similar_edges=past_similar_edges,
            historical_decay_times=historical_decay_times,
            league=league,
            edge_pct=edge_pct_raw,
            edge_score=edge_report.edge_score,
            seed=42,
        )

        our_side = "home" if calibrated_prob > 0.5 else "away"
        lm_input = LineMovementInput(
            opening_home_odds=opening_odds if opening_odds > 0 else odds_home,
            current_home_odds=odds_home,
            opening_away_odds=odds_away,
            current_away_odds=odds_away,
            minutes_to_game=hours_to_game * 60,
            liquidity_score=market_liquidity_score,
            n_sportsbooks=n_sportsbooks,
            sharp_money_pct=0.20,
            public_money_pct=0.80,
            sharp_side="home" if sharp_direction_agrees and calibrated_prob > 0.5
                       else ("away" if sharp_direction_agrees else ""),
            steam_move_count=steam_moves,
            steam_direction="home" if sharp_direction_agrees and calibrated_prob > 0.5
                            else ("away" if sharp_direction_agrees else ""),
            reverse_line_moves=reverse_line_moves,
            total_line_moves=0,
            historical_closing_lines=closing_line_history or [],
            our_side=our_side,
        )

        impact_input = MarketImpactInput(
            liquidity_score=market_liquidity_score,
            regime=report.market_regime,
            n_books=n_sportsbooks,
            avg_limit_usd=avg_limit_usd,
            current_odds=odds_home,
            intended_stake_usd=0.02 * self.risk.state.current_bankroll,
            bet_type="ML",
            bankroll=self.risk.state.current_bankroll,
            hours_to_game=hours_to_game,
            book_tier=book_tier,
            sharp_detection_history=sharp_detection_history,
            edge_pct=edge_pct_raw,
            seed=42,
            n_simulations=200,
        )

        # Execute all four phases in parallel
        realism_report, decay_forecast, lm_result, impact_report = \
            self._run_phases_parallel(
                lambda: assess_edge_realism(realism_input),
                lambda: predict_edge_decay(decay_input),
                lambda: self.line_predictor.predict(lm_input),
                lambda: simulate_market_impact(impact_input),
            )

        # ── Process Phase 1b results ─────────────────────────
        report.real_edge_score = realism_report.real_edge_score
        report.real_edge_label = realism_report.real_edge_label.value
        report.realism_tradeable = realism_report.is_tradeable
        report.realism_details = realism_report.details

        if not realism_report.is_tradeable:
            report.decision = "NO_BET"
            report.confidence = "LOW"
            report.reasoning.append(
                f"Edge Realism blocked: {realism_report.blocking_reason}"
            )
            return report

        # ── Process Phase 1c results ─────────────────────────
        report.decay_half_life = decay_forecast.half_life_seconds
        report.decay_urgency = decay_forecast.urgency_level.value
        report.decay_confidence = decay_forecast.confidence_score
        report.decay_curve = decay_forecast.decay_curve
        report.decay_lower_bound = decay_forecast.lower_bound_seconds
        report.decay_upper_bound = decay_forecast.upper_bound_seconds

        if decay_forecast.half_life_seconds < 180.0:
            report.reasoning.append(
                f"⚡ Edge Decay: half-life {decay_forecast.half_life_seconds:.0f}s "
                f"→ EXECUTE_IMMEDIATELY (conf={decay_forecast.confidence_score:.0f})"
            )
        elif decay_forecast.urgency_level == UrgencyLevel.EXPIRED:
            report.decision = "NO_BET"
            report.confidence = "LOW"
            report.reasoning.append(
                f"Edge Decay EXPIRED: half-life {decay_forecast.half_life_seconds:.0f}s "
                f"— edge already eroded"
            )
            return report

        # ── Process Phase 1d results ─────────────────────────
        report.line_movement_direction = lm_result.primary_direction.value
        report.line_movement_confidence = lm_result.primary_confidence
        report.expected_closing_odds = lm_result.expected_closing_home_odds
        report.expected_clv = lm_result.expected_clv
        report.timing_action = lm_result.timing_recommendation.value
        report.timing_reasoning = lm_result.timing_reasoning
        report.optimal_delay_minutes = lm_result.optimal_bet_window_minutes

        if lm_result.timing_recommendation in (
            TimingAction.DELAY_SHORT, TimingAction.DELAY_MEDIUM,
            TimingAction.DELAY_LONG, TimingAction.WAIT_FOR_CLOSE,
        ):
            report.reasoning.append(
                f"📈 Line Movement: {lm_result.primary_direction.value} "
                f"(conf={lm_result.primary_confidence:.0f}%) → "
                f"{lm_result.timing_recommendation.value} "
                f"({lm_result.timing_reasoning})"
            )

        if lm_result.timing_recommendation == TimingAction.AVOID:
            if decay_forecast.half_life_seconds < 180.0:
                report.reasoning.append(
                    f"⚡ Decay override: ignoring AVOID (half-life "
                    f"{decay_forecast.half_life_seconds:.0f}s)"
                )
            else:
                report.decision = "NO_BET"
                report.confidence = "LOW"
                report.reasoning.append(
                    "Line Movement AVOID: aggressive adverse movement detected"
                )
                return report

        # ── Process Phase 1e results ─────────────────────────
        report.expected_slippage = impact_report.expected_slippage
        report.impact_probability = impact_report.impact_probability
        report.odds_after_bet = impact_report.odds_after_bet
        report.execution_risk_score = impact_report.execution_risk_score
        report.execution_strategy = impact_report.execution_strategy.value
        report.max_safe_bet_size = impact_report.max_safe_bet_size
        report.recommended_split_count = impact_report.recommended_split_count

        # Decision rule: slippage > edge → NO_BET
        if impact_report.expected_slippage > edge_pct_raw and edge_pct_raw > 0:
            report.slippage_exceeds_edge = True
            report.decision = "NO_BET"
            report.confidence = "LOW"
            report.reasoning.append(
                f"Market Impact blocked: slippage ({impact_report.expected_slippage:.4f}) "
                f"> edge ({edge_pct_raw:.4f})"
            )
            return report

        # Decision rule: execution_risk > 70 → will reduce size later
        if impact_report.execution_risk_score > 70:
            report.reasoning.append(
                f"⚠ High execution risk ({impact_report.execution_risk_score:.0f}) "
                f"→ bet size will be reduced 50%"
            )

        # ════════════════════════════════════════════════════════
        # PHASE 2: Market Regime Classification
        # ════════════════════════════════════════════════════════
        if regime_signals is None:
            regime_signals = build_signals_from_microstructure(
                micro_report=micro_report,
                public_pct=public_pct,
                hours_to_game=hours_to_game,
            )
            regime_signals.sharp_signal_count = sharp_signal_count

        regime_report = classify_market_regime(regime_signals)

        report.market_regime = regime_report.regime.value
        report.regime_confidence = regime_report.confidence
        report.regime_action = regime_report.recommended_action

        self._recent_regimes.append(regime_report.regime.value)

        if not regime_report.should_bet:
            report.decision = "NO_BET"
            report.confidence = "LOW"
            report.reasoning.append(
                f"Regime {regime_report.regime.value} blocks betting: "
                f"{regime_report.recommended_action}"
            )
            return report

        # ════════════════════════════════════════════════════════
        # PHASE 2b: Fake Move Detector
        # ════════════════════════════════════════════════════════
        fake_input = FakeMoveInput(
            line_velocity=odds_velocity,
            line_acceleration=odds_acceleration,
            move_magnitude=abs(odds_home - opening_odds) / max(opening_odds, 1.01) if opening_odds > 0 else 0,
            move_duration_minutes=hours_to_game * 60 * 0.1,  # estimated
            reported_volume=market_liquidity_score,
            expected_volume=0.5,
            volume_before_move=market_liquidity_score * 0.8,
            volume_during_move=market_liquidity_score,
            reverted_pct=0.0,  # would need real snapshots
            n_books_confirming=max(1, n_sportsbooks - 1) if sharp_direction_agrees else 1,
            n_books_total=n_sportsbooks,
            pinnacle_moved=sharp_signal_count > 0,
            liquidity_score=market_liquidity_score,
            minutes_to_game=hours_to_game * 60,
            is_steam_move=steam_moves > 0,
            sharp_money_pct=sharp_money_pct,
            vpin_estimate=0.3 + 0.3 * (1.0 - market_liquidity_score),
            order_imbalance=sharp_money_pct - (1.0 - sharp_money_pct) if sharp_money_pct else 0,
        )
        fake_result = detect_fake_move(fake_input)

        report.fake_move_score = fake_result.fake_score
        report.fake_move_type = fake_result.fake_type.value
        report.fake_move_action = fake_result.action.value
        report.fake_confidence_mult = fake_result.confidence_multiplier

        if fake_result.action == FakeAction.SKIP:
            report.decision = "NO_BET"
            report.confidence = "LOW"
            report.reasoning.append(
                f"Fake Move SKIP: score={fake_result.fake_score:.0f} "
                f"({fake_result.fake_type.value}) — {fake_result.reasoning}"
            )
            return report

        if fake_result.action == FakeAction.DELAY:
            report.timing_action = "DELAY_15m"
            report.reasoning.append(
                f"⚠ Fake Move DELAY: score={fake_result.fake_score:.0f} → DELAY 15min"
            )

        # ════════════════════════════════════════════════════════
        # PHASE 6: Sharpness Check (run early to potentially abort)
        # ════════════════════════════════════════════════════════
        sharpness_report = self.sharpness.assess()

        report.sharpness_level = sharpness_report.level.value
        report.trailing_clv = sharpness_report.trailing_clv
        report.sharpness_ok = not sharpness_report.should_pause

        if sharpness_report.should_pause:
            report.decision = "NO_BET"
            report.confidence = "LOW"
            report.reasoning.append(
                f"Sharpness monitor PAUSED: {sharpness_report.alert_message}"
            )
            return report

        # ════════════════════════════════════════════════════════
        # PHASE 3: Bet Selection (evaluate all bet types)
        # ════════════════════════════════════════════════════════
        bet_candidates: list[BetCandidate] = []

        # Build bet type candidates
        bet_types = []

        # Money Line (always available)
        implied_home = 1.0 / odds_home if odds_home > 1 else 0.99
        if calibrated_prob > implied_home:
            bet_types.append(("ML", "HOME", odds_home, calibrated_prob))
        else:
            implied_away = 1.0 / odds_away if odds_away > 1 else 0.99
            away_prob = 1.0 - calibrated_prob
            if away_prob > implied_away:
                bet_types.append(("ML", "AWAY", odds_away, away_prob))

        # Over/Under (if available)
        if odds_over and odds_under:
            # Simplified: use model prob > 0.5 as over indicator
            if calibrated_prob > 0.55:
                bet_types.append(("OU", "OVER", odds_over, calibrated_prob))
            elif calibrated_prob < 0.45:
                bet_types.append(("OU", "UNDER", odds_under, 1.0 - calibrated_prob))

        # First 5 innings (if available)
        if odds_f5_home and odds_f5_away and calibrated_prob > 0.55:
            bet_types.append(("F5", "HOME", odds_f5_home, calibrated_prob * 0.95))

        for bt, side, odds, cal_prob in bet_types:
            candidate = evaluate_bet_candidate(
                match_id=match_id,
                match_label=match_label,
                bet_type=bt,
                side=side,
                odds=odds,
                model_prob=model_prob,
                calibrated_prob=cal_prob,
                sub_model_probs=probs_list,
                edge_report=edge_report,
                regime_report=regime_report,
                daily_bet_count=self.risk.state.daily_bets,
                band_roi_lookup=self._band_roi_lookup,
            )
            bet_candidates.append(candidate)

        selection = select_bets(bet_candidates, max_per_match=2)

        if not selection.selected:
            report.decision = "WATCH"
            report.confidence = "LOW"
            report.reasoning.append("No bet candidates passed all gates")
            for c in selection.rejected:
                report.reasoning.append(f"  {c.bet_type} {c.side}: {c.reasoning}")
            return report

        # ════════════════════════════════════════════════════════
        # PHASE 4 + 7: Position Sizing & Risk Check
        # ════════════════════════════════════════════════════════
        approved_bets: list[BetDecision] = []

        for candidate in selection.selected:
            # Phase 4: Position sizing
            sizing_input = SizingInput(
                odds=candidate.odds,
                calibrated_prob=candidate.calibrated_prob,
                edge_pct=candidate.edge_pct,
                adjusted_edge=candidate.adjusted_edge,
                edge_score=candidate.edge_score,
                confidence_tier=candidate.confidence_tier,
                prediction_entropy=candidate.pred_stddev * 3,  # proxy
                regime=regime_report.regime.value,
                regime_confidence=regime_report.confidence,
                bankroll=self.risk.state.current_bankroll,
                peak_bankroll=self.risk.state.peak_bankroll,
                current_drawdown=self.risk.state.drawdown_pct,
                recent_pnl=self._trailing_pnl[-20:],
            )

            sizing = compute_position_size(
                sizing_input,
                trailing_pnl=self._trailing_pnl,
                trailing_sizes=self._trailing_sizes,
                trailing_strategies=self._trailing_strategies,
            )

            # Phase 7: Risk check
            risk_check = self.risk.pre_bet_check(
                proposed_size_pct=sizing.bet_size_pct,
                match_id=match_id,
                sharpness_paused=sharpness_report.should_pause,
            )

            # Apply risk adjustments
            final_size = min(sizing.bet_size_pct, risk_check.max_allowed_size)

            # Market Impact override: high execution risk → halve size
            if impact_report.execution_risk_score > 70:
                final_size *= 0.5
            final_amount = final_size * self.risk.state.current_bankroll

            bet_decision = BetDecision(
                bet_type=candidate.bet_type,
                side=candidate.side,
                odds=candidate.odds,
                edge_pct=candidate.edge_pct,
                adjusted_edge=candidate.adjusted_edge,
                bet_size_pct=round(final_size, 6),
                bet_amount=round(final_amount, 2),
                sizing_strategy=sizing.strategy_used.value,
                approved=risk_check.approved and final_size > 0,
                confidence_tier=candidate.confidence_tier,
            )

            if risk_check.approved and final_size > 0:
                approved_bets.append(bet_decision)
                report.risk_warnings.extend(risk_check.warnings)
            else:
                report.risk_warnings.extend(risk_check.reasons)

        report.bets = approved_bets
        report.total_exposure_pct = sum(b.bet_size_pct for b in approved_bets)
        report.risk_level = self.risk.state.risk_level.value

        # ════════════════════════════════════════════════════════
        # FINAL DECISION
        # ════════════════════════════════════════════════════════
        if approved_bets:
            report.decision = "BET"
            # Confidence = best tier among approved bets
            tier_order = {"ELITE": 4, "STRONG": 3, "MODERATE": 2, "WEAK": 1}
            best_tier = max(approved_bets, key=lambda b: tier_order.get(b.confidence_tier, 0))
            report.confidence = best_tier.confidence_tier
            report.risk_approved = True

            for b in approved_bets:
                report.reasoning.append(
                    f"✓ {b.bet_type} {b.side} @ {b.odds:.2f} — "
                    f"edge={b.adjusted_edge:.2%}, size={b.bet_size_pct:.2%} "
                    f"(${b.bet_amount:.0f}), strategy={b.sizing_strategy}"
                )
        else:
            report.decision = "NO_BET"
            report.confidence = "LOW"
            report.risk_approved = False
            report.reasoning.append("Risk engine blocked all candidates")

        # Meta info
        report.model_weights = get_model_weights(self.meta)
        report.meta_summary = get_meta_summary(self.meta)

        return report

    # ─── Post-Game Feedback ─────────────────────────────────────────────

    def record_outcome(
        self,
        match_id: str,
        won: bool,
        pnl: float,
        bet_odds: float = 2.0,
        closing_odds: float = 2.0,
        opening_odds: float = 0.0,
        bet_side: str = "",
        model_probs: dict[str, float] | None = None,
        actual_outcome: int = 0,
        sizing_strategy: str = "",
        size_pct: float = 0.01,
    ) -> None:
        """
        Record game outcome for all sub-systems.
        Call this after every settled bet.
        """
        # Risk engine
        self.risk.record_result(match_id, won, pnl)

        # Sharpness monitor
        self.sharpness.record_clv(
            game_id=match_id,
            bet_odds=bet_odds,
            closing_odds=closing_odds,
            opening_odds=opening_odds,
            our_side=bet_side,
        )

        # Meta learning
        if model_probs:
            for model_name, prob in model_probs.items():
                entry = ModelPerformanceEntry(
                    game_id=match_id,
                    timestamp=time.time(),
                    model_name=model_name,
                    predicted_prob=prob,
                    actual_outcome=actual_outcome,
                    brier_contribution=(prob - actual_outcome) ** 2,
                    roi_contribution=pnl / (size_pct * self.risk.state.current_bankroll)
                    if size_pct > 0 else 0,
                    odds_at_bet=bet_odds,
                )
                record_prediction(self.meta, model_name, entry)

        record_game(self.meta)

        # Check for retrain
        do_retrain, trigger = should_retrain(self.meta)
        if do_retrain:
            execute_retrain(self.meta, trigger)

        # Check for regime shift
        detect_regime_shift(self.meta, self._recent_regimes)

        # Trailing data for position sizing
        self._trailing_pnl.append(pnl / self.risk.state.current_bankroll if self.risk.state.current_bankroll > 0 else 0)
        self._trailing_sizes.append(size_pct)
        self._trailing_strategies.append(sizing_strategy)

        # Keep trailing buffers manageable
        max_trail = 200
        if len(self._trailing_pnl) > max_trail:
            self._trailing_pnl = self._trailing_pnl[-max_trail:]
            self._trailing_sizes = self._trailing_sizes[-max_trail:]
            self._trailing_strategies = self._trailing_strategies[-max_trail:]

    def reset_daily(self) -> None:
        """Call at the start of each betting day."""
        self.risk.reset_daily()

    def get_dashboard(self) -> dict[str, Any]:
        """Get a combined status dashboard."""
        return {
            "risk": self.risk.get_status(),
            "sharpness": self.sharpness.get_quick_status(),
            "meta": get_meta_summary(self.meta),
        }


# ─── Report Formatter ──────────────────────────────────────────────────────

def format_decision_report(report: DecisionReport) -> str:
    """Format a DecisionReport as a human-readable string."""
    lines = []
    lines.append("=" * 56)
    lines.append("  INSTITUTIONAL DECISION REPORT")
    lines.append("=" * 56)
    lines.append(f"  Match:           {report.match_label}")
    lines.append(f"  Edge Score:      {report.edge_score:.1f} ({report.edge_tier})")
    lines.append(f"  Edge Realism:    {report.real_edge_score:.1f} ({report.real_edge_label})")
    lines.append(f"  Edge Decay:      {report.decay_half_life:.0f}s half-life ({report.decay_urgency}) "
                 f"conf={report.decay_confidence:.0f}")
    dir_icon = {"UP": "⬆️", "DOWN": "⬇️", "STABLE": "➡️"}
    lines.append(f"  Line Movement:   {dir_icon.get(report.line_movement_direction, '?')} "
                 f"{report.line_movement_direction} "
                 f"(conf={report.line_movement_confidence:.0f}%)")
    lines.append(f"  Timing:          {report.timing_action}")
    if report.optimal_delay_minutes > 0:
        lines.append(f"  Delay:           {report.optimal_delay_minutes:.0f} min")
    lines.append(f"  Expected CLV:    {report.expected_clv:+.2%}")
    lines.append(f"  Mkt Impact:      slip={report.expected_slippage:.4f} "
                 f"risk={report.execution_risk_score:.0f} "
                 f"strat={report.execution_strategy}")
    if report.max_safe_bet_size > 0:
        lines.append(f"  Safe Bet Max:    ${report.max_safe_bet_size:.0f} "
                     f"(split={report.recommended_split_count})")
    lines.append(f"  Market Regime:   {report.market_regime} ({report.regime_confidence:.0%})")
    if report.fake_move_score > 0:
        lines.append(f"  Fake Move:       {report.fake_move_type} "
                     f"(score={report.fake_move_score:.0f}, action={report.fake_move_action})")
    lines.append(f"  Sharpness:       {report.sharpness_level} (CLV: {report.trailing_clv:+.4f})")
    lines.append(f"  Risk Level:      {report.risk_level}")
    lines.append("-" * 56)

    if report.bets:
        for i, b in enumerate(report.bets, 1):
            lines.append(f"  Bet #{i}:")
            lines.append(f"    Type:          {b.bet_type} {b.side}")
            lines.append(f"    Odds:          {b.odds:.2f}")
            lines.append(f"    Edge:          {b.adjusted_edge:.2%}")
            lines.append(f"    Size:          {b.bet_size_pct:.2%} (${b.bet_amount:.0f})")
            lines.append(f"    Strategy:      {b.sizing_strategy}")
            lines.append(f"    Confidence:    {b.confidence_tier}")
            lines.append(f"    Approved:      {'✓' if b.approved else '✗'}")
        lines.append(f"  Total Exposure:  {report.total_exposure_pct:.2%}")
    else:
        lines.append("  No bets recommended")

    lines.append("-" * 56)
    icon = "✓" if report.decision == "BET" else ("⊘" if report.decision == "WATCH" else "✗")
    lines.append(f"  DECISION:        {icon} {report.decision}")
    lines.append(f"  CONFIDENCE:      {report.confidence}")
    lines.append("-" * 56)

    for r in report.reasoning:
        lines.append(f"  {r}")

    if report.risk_warnings:
        lines.append("")
        lines.append("  ⚠ Risk Warnings:")
        for w in report.risk_warnings:
            lines.append(f"    - {w}")

    lines.append("=" * 56)
    return "\n".join(lines)
