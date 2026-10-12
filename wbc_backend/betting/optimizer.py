"""
Bet Optimizer — § 五 投注策略引擎

Combines Kelly criterion, risk control, and market calibration
to find the TOP 3 highest-EV bets.

Output format:
  TOP 3 BETS
  1. 類型 + EV + 信心
  2. 類型 + EV + 信心
  3. 類型 + EV + 信心
"""
from __future__ import annotations

import logging

from wbc_backend.betting.kelly import (
    calculate_kelly_bet,
    expected_value,
    bayesian_kelly,
    implied_probability,
)
from wbc_backend.betting.risk_control import BankrollState, check_risk_limits
from wbc_backend.config.settings import AppConfig
from wbc_backend.domain.schemas import (
    BetRecommendation,
    OddsLine,
    SimulationSummary,
)
from wbc_backend.models.closing_line_model import ClosingLineModel

logger = logging.getLogger(__name__)

_SUSPICIOUS_MODEL_MARKET_GAP = 0.18
_BORDERLINE_EDGE_BUFFER = 0.01
_HIGH_BRIER_REJECT = 0.285
_HIGH_BRIER_WARN = 0.255
_HIGH_ECE_REJECT = 0.12
_HIGH_ECE_WARN = 0.08
_HIGH_EFFICIENCY_REJECT = 0.88
_TSL_MARKET_CODE_MAP = {
    "ML": "MNL",
    "RL": "HDC",
    "OU": "OU",
    "OE": "OE",
    "F5": "FMNL",
    "TT": "TTO",
}
_MARKET_SUPPORT_CONFIDENCE = {
    "direct": 1.03,
    "stale": 0.94,
    "unlisted_market": 0.92,
    "unlisted_matchup": 0.90,
    "blocked": 0.88,
    "degraded": 0.92,
    "migrating": 0.93,
    "unknown": 1.0,
}


def _apply_reject_option(
    *,
    win_prob: float,
    implied_prob_value: float,
    edge_val: float,
    local_confidence: float,
    clv_edge: float,
    efficiency: float,
    strat,
    model_brier: float | None = None,
    calibration_ece: float | None = None,
) -> tuple[bool, float, list[str]]:
    """Reject or downweight fragile bets before Kelly sizing."""
    reasons: list[str] = []
    confidence_multiplier = 1.0
    prob_gap = abs(win_prob - implied_prob_value)

    if local_confidence < strat.confidence_min:
        return True, 0.0, [f"reject_low_conf={local_confidence:.3f}<{strat.confidence_min:.3f}"]

    if prob_gap > _SUSPICIOUS_MODEL_MARKET_GAP:
        return True, 0.0, [f"reject_prob_gap={prob_gap:.3f}"]

    if efficiency > _HIGH_EFFICIENCY_REJECT and edge_val < (strat.edge_threshold + _BORDERLINE_EDGE_BUFFER):
        return True, 0.0, [f"reject_high_efficiency={efficiency:.2f}"]

    if clv_edge < 0.02 and local_confidence < max(0.65, strat.confidence_min + 0.04):
        return True, 0.0, [f"reject_borderline_clv={clv_edge:.3f}"]

    if model_brier is not None:
        if model_brier > _HIGH_BRIER_REJECT and edge_val < (strat.edge_threshold + 0.02):
            return True, 0.0, [f"reject_brier={model_brier:.3f}"]
        if model_brier > _HIGH_BRIER_WARN:
            confidence_multiplier *= 0.85
            reasons.append(f"brier_penalty={model_brier:.3f}")

    if calibration_ece is not None:
        if calibration_ece > _HIGH_ECE_REJECT and edge_val < (strat.edge_threshold + 0.02):
            return True, 0.0, [f"reject_ece={calibration_ece:.3f}"]
        if calibration_ece > _HIGH_ECE_WARN:
            confidence_multiplier *= 0.90
            reasons.append(f"ece_penalty={calibration_ece:.3f}")

    return False, confidence_multiplier, reasons


def _map_market_key(odds: OddsLine, home_code: str, away_code: str) -> str:
    """Map an OddsLine to a probability key."""
    if odds.market == "ML":
        return f"ML_{odds.side}"
    if odds.market == "RL":
        return f"RL_{odds.side}"
    if odds.market == "OU":
        return f"OU_{odds.side}"
    if odds.market == "OE":
        return f"OE_{odds.side}"
    if odds.market == "F5":
        return f"F5_{odds.side}"
    if odds.market == "TT":
        return f"TT_{odds.side}"
    return f"{odds.market}_{odds.side}"


def classify_market_support_state(odds: OddsLine, tsl_matchup_status: dict | None) -> str:
    if odds.sportsbook != "TSL":
        return "intl_only"
    if not tsl_matchup_status or not tsl_matchup_status.get("in_snapshot", False):
        return "tsl_unlisted_matchup"
    if not tsl_matchup_status.get("is_fresh", True):
        return "tsl_stale"
    expected_code = _TSL_MARKET_CODE_MAP.get(str(odds.market or "").upper(), str(odds.market or "").upper())
    market_codes = {str(code).strip().upper() for code in (tsl_matchup_status.get("market_codes") or [])}
    if expected_code.upper() not in market_codes:
        return "tsl_unlisted_market"
    return "tsl_direct"


def _tsl_market_is_covered(odds: OddsLine, tsl_matchup_status: dict | None) -> bool:
    return classify_market_support_state(odds, tsl_matchup_status) == "tsl_direct"


def _market_environment_state(
    odds: OddsLine,
    market_support_by_market: dict[str, str] | None,
) -> str:
    if not market_support_by_market:
        return "unknown"
    return str(market_support_by_market.get(str(odds.market or "").upper(), "unknown"))


def _market_environment_multiplier(state: str) -> float:
    return _MARKET_SUPPORT_CONFIDENCE.get(str(state or "").lower(), 1.0)


def apply_execution_slippage(odds: float, latency_seconds: float = 30.0) -> float:
    """
    P1.2: Institutional Execution Realism.
    Simulates odds deterioration (slippage) between signal and execution.
    Average market slippage in high-liquidity baseball markets is ~0.5-1.5 ticks.
    """
    # Deteriorate odds by a factor scaled by latency
    # 0.0005 per second decay (1.5% slippage after 30s)
    decay = 1.0 - (latency_seconds * 0.0005)
    deteriorated_odds = 1.0 + (odds - 1.0) * max(0.95, decay)
    return round(deteriorated_odds, 3)


def build_true_probs(
    home_code: str,
    away_code: str,
    home_win_prob: float,
    sim: SimulationSummary,
) -> dict[str, float]:
    """Build true probability map from model + simulation."""
    return {
        f"ML_{home_code}": home_win_prob,
        f"ML_{away_code}": 1.0 - home_win_prob,
        f"RL_{home_code}": sim.home_cover_prob,
        f"RL_{away_code}": sim.away_cover_prob,
        "OU_Over": sim.over_prob,
        "OU_Under": sim.under_prob,
        "OE_Odd": sim.odd_prob,
        "OE_Even": sim.even_prob,
        f"F5_{home_code}": sim.home_f5_win_prob,
        f"F5_{away_code}": sim.away_f5_win_prob,
    }


def find_top_bets(
    odds_lines: list[OddsLine],
    true_probs: dict[str, float],
    home_code: str,
    away_code: str,
    confidence_score: float = 0.5,
    config: AppConfig | None = None,
    bankroll_state: BankrollState | None = None,
    time_to_start_hours: float = 12.0,      # Default: 12h before start
    steam_signals: int = 0,                 # Recent steam moves
    market_consensus: dict[str, float] = None, # Average odds from other books
    model_brier: float | None = None,
    calibration_ece: float | None = None,
    tsl_feed_status: dict | None = None,
    tsl_matchup_status: dict | None = None,
    market_support_by_market: dict[str, str] | None = None,
    blowout_propensity: float = 0.0,        # N.02 mismatch_blowout_propensity
) -> list[BetRecommendation]:
    """
    Evaluate all available odds lines, compute EV, Kelly stakes,
    apply risk controls, and return TOP 3 best bets.
    """
    config = config or AppConfig()
    strat = config.strategy
    bank_config = config.bankroll
    state = bankroll_state or BankrollState(
        initial=bank_config.initial_bankroll,
        current=bank_config.initial_bankroll,
        peak=bank_config.initial_bankroll,
        daily_start=bank_config.initial_bankroll,
    )
    base_confidence = confidence_score

    candidates: list[BetRecommendation] = []

    for odds in odds_lines:
        # OE（單雙號）市場：vig 最高且近乎純隨機，永久跳過
        if str(odds.market or "").upper() == "OE":
            logger.debug("Bet OE %s skipped: OE market excluded (high vig, near-random)")
            continue

        # OU Under 崩盤壓制：Elo 差距極大時大比分崩盤風險使 Under 失效
        # blowout_propensity > 0.65 ≈ Elo gap > 140（B06 典型值約 0.85）
        if (
            str(odds.market or "").upper() == "OU"
            and str(odds.side or "").lower() == "under"
            and blowout_propensity > 0.65
        ):
            logger.debug(
                "OU Under skipped: blowout_propensity=%.2f > 0.65 (high mismatch)",
                blowout_propensity,
            )
            continue

        market_support_state = classify_market_support_state(odds, tsl_matchup_status)
        market_env_state = _market_environment_state(odds, market_support_by_market)
        if odds.sportsbook == "TSL" and market_support_state != "tsl_direct":
            logger.debug(
                "Bet %s %s skipped: support_state=%s",
                odds.market,
                odds.side,
                market_support_state,
            )
            continue
        if odds.sportsbook == "TSL" and tsl_feed_status and not tsl_feed_status.get("success"):
            note = str(tsl_feed_status.get("note") or tsl_feed_status.get("error") or "")
            if "modern_pre_" in note and "403" in note:
                logger.debug(
                    "Bet %s %s skipped: TSL pre-match feed currently blocked",
                    odds.market,
                    odds.side,
                )
                continue

        key = _map_market_key(odds, home_code, away_code)
        if key not in true_probs:
            continue

        # ── P1.2: Execution Slippage Adjustment ──────────
        # Assume 45s latency for manual execution (Institutional buffer)
        real_odds = apply_execution_slippage(odds.decimal_odds, latency_seconds=45.0)

        win_prob = true_probs[key]
        impl_prob = implied_probability(real_odds)
        ev = expected_value(win_prob, real_odds)
        edge_val = win_prob - impl_prob

        # ── P1.4: CLV Alpha Gate ─────────────────────────
        clv_model = ClosingLineModel(config.model)

        # Estimate predicted closing odds
        consensus = (market_consensus or {}).get(key, odds.decimal_odds)
        predicted_closing = clv_model.predict_closing_odds(
            odds.decimal_odds, time_to_start_hours, steam_signals, consensus
        )

        # Only bet if we have an advantage over the predicted closing line
        clv_edge = (odds.decimal_odds / predicted_closing) - 1.0
        if clv_edge < 0.015:  # Require 1.5% CLV margin
            logger.debug("Bet %s %s skipped: Insufficient CLV (%.3f)", odds.market, odds.side, clv_edge)
            continue

        # ── P1.5: Market Efficiency Check ────────────────
        efficiency = clv_model.get_market_efficiency_score(bookie_variance=0.01)
        local_confidence = base_confidence
        if efficiency > 0.85: # High efficiency -> lower confidence
            local_confidence *= 0.9
        if odds.sportsbook == "TSL" and tsl_feed_status and not tsl_feed_status.get("success"):
            local_confidence *= 0.8
        if odds.sportsbook == "TSL" and market_support_state != "tsl_direct":
            local_confidence *= 0.7
        local_confidence *= _market_environment_multiplier(market_env_state)

        # Filter: must have positive edge and meet minimum EV
        if edge_val < strat.edge_threshold:
            continue
        if ev < strat.min_ev:
            continue

        reject_bet, confidence_mult, gate_reasons = _apply_reject_option(
            win_prob=win_prob,
            implied_prob_value=impl_prob,
            edge_val=edge_val,
            local_confidence=local_confidence,
            clv_edge=clv_edge,
            efficiency=efficiency,
            strat=strat,
            model_brier=model_brier,
            calibration_ece=calibration_ece,
        )
        if reject_bet:
            logger.debug(
                "Bet %s %s skipped by reject gate: %s",
                odds.market,
                odds.side,
                ", ".join(gate_reasons),
            )
            continue
        local_confidence *= confidence_mult

        # Bayesian Kelly calculation (P2.6) - Use real_odds for calculation
        full_kelly = calculate_kelly_bet(win_prob, real_odds)
        frac_kelly = bayesian_kelly(win_prob, real_odds, local_confidence, strat.fractional_kelly)
        stake_frac = min(strat.max_stake_fraction, frac_kelly)

        if stake_frac <= 0:
            continue

        # Calculate actual stake amount
        proposed_stake = state.current * stake_frac
        adjusted_stake, warnings = check_risk_limits(state, proposed_stake, bank_config)

        if adjusted_stake <= 0:
            continue

        # Confidence: blend model confidence with edge magnitude
        bet_confidence = min(1.0, local_confidence * 0.6 + min(edge_val / 0.15, 1.0) * 0.4)
        if bet_confidence < strat.confidence_min:
            logger.debug(
                "Bet %s %s skipped: final confidence %.3f below %.3f",
                odds.market,
                odds.side,
                bet_confidence,
                strat.confidence_min,
            )
            continue

        # Build reason
        reason_parts = [
            f"edge={edge_val:.3f}",
            f"EV={ev:.3f}",
            f"kelly={full_kelly:.3f}",
            f"frac_kelly={frac_kelly:.3f}",
            f"book={odds.sportsbook}",
        ]
        reason_parts.append(f"market_support={market_support_state}")
        reason_parts.append(f"market_env={market_env_state}")
        if gate_reasons:
            reason_parts.extend(gate_reasons)
        if warnings:
            reason_parts.append(f"risk_warnings={len(warnings)}")
        reason = "; ".join(reason_parts)

        candidates.append(BetRecommendation(
            market=odds.market,
            side=odds.side,
            line=odds.line,
            sportsbook=odds.sportsbook,
            source_type=odds.source_type,
            win_probability=round(win_prob, 4),
            implied_probability=round(impl_prob, 4),
            ev=round(ev, 4),
            edge=round(edge_val, 4),
            kelly_fraction=round(full_kelly, 4),
            stake_fraction=round(stake_frac, 4),
            stake_amount=round(adjusted_stake, 0),
            confidence=round(bet_confidence, 4),
            market_support_state=market_support_state,
            reason=reason + f"; CLV={clv_edge:+.3f}; Efficiency={efficiency:.2f}",
        ))

    # Sort by EV (primary), then confidence (secondary)
    candidates.sort(key=lambda b: (b.ev, b.confidence), reverse=True)

    # Return top 3
    top = candidates[:strat.max_recommendations]

    if top:
        logger.info("=" * 50)
        logger.info("TOP %d BETS", len(top))
        logger.info("=" * 50)
        for i, bet in enumerate(top, 1):
            logger.info(
                "%d. %s %s (line=%s) @ %s — EV=%.3f, edge=%.3f, confidence=%.2f, stake=$%.0f",
                i, bet.market, bet.side, bet.line, bet.sportsbook,
                bet.ev, bet.edge, bet.confidence, bet.stake_amount,
            )
    else:
        logger.info("No positive EV bets found above threshold.")

    return top


def format_top_bets(bets: list[BetRecommendation]) -> str:
    """Format TOP 3 bets for display output."""
    lines = ["", "=" * 60, "🏆 TOP 3 BETS", "=" * 60]

    if not bets:
        lines.append("  No positive-EV bets found above threshold.")
        lines.append("=" * 60)
        return "\n".join(lines)

    for i, bet in enumerate(bets, 1):
        market_desc = f"{bet.market} {bet.side}"
        if bet.line is not None:
            market_desc += f" ({bet.line:+.1f})"

        lines.append(
            f"  {i}. {market_desc} @ {bet.sportsbook}"
        )
        lines.append(
            f"     EV = {bet.ev:+.3f}  |  Edge = {bet.edge:.3f}  |  "
            f"Confidence = {bet.confidence:.0%}"
        )
        lines.append(
            f"     Kelly = {bet.kelly_fraction:.3f}  |  "
            f"Stake = ${bet.stake_amount:,.0f} ({bet.stake_fraction:.1%} of bankroll)"
        )
        lines.append(
            f"     Win Prob = {bet.win_probability:.1%}  |  "
            f"Implied = {bet.implied_probability:.1%}"
        )
        if i < len(bets):
            lines.append("")

    lines.append("=" * 60)
    return "\n".join(lines)
