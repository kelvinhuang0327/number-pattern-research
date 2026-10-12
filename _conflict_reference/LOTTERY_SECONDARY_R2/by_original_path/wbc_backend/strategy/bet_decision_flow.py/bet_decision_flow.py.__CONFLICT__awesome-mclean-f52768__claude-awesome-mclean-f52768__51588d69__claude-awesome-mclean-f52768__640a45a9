"""
Institution-Grade Bet Decision Flow
=====================================
Five-gate sequential decision pipeline:
  Gate 1 — Model Consensus Check
  Gate 2 — Market Deviation Assessment
  Gate 3 — Risk Exposure Check
  Gate 4 — Position Sizing (Kelly/MV/RP)
  Gate 5 — Timing & Delay Strategy

A bet must pass ALL gates to be executed.
Each gate can REJECT, PASS, or MODIFY the bet.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum

from wbc_backend.domain.schemas import BetRecommendation, PredictionResult


# ─── Data Structures ─────────────────────────────────────────────────────────

class GateResult(Enum):
    PASS = "PASS"
    REJECT = "REJECT"
    MODIFY = "MODIFY"


@dataclass
class GateDecision:
    """Result from a single gate evaluation."""
    gate: str
    result: GateResult
    reason: str
    original_value: float = 0.0
    modified_value: float = 0.0
    confidence: float = 1.0


@dataclass
class BetDecision:
    """Complete decision pipeline output for a single bet."""
    bet: BetRecommendation
    approved: bool
    gates: list[GateDecision] = field(default_factory=list)
    final_stake_pct: float = 0.0
    final_stake_amount: float = 0.0
    timing: str = "IMMEDIATE"
    delay_minutes: int = 0
    summary: str = ""


@dataclass
class DecisionContext:
    """All context needed for the decision pipeline."""
    prediction: PredictionResult
    sub_model_probs: dict[str, float]    # {model_name: home_win_prob}
    market_implied_prob: float            # market's implied probability
    model_prob: float                     # ensemble model probability
    odds: float                           # current decimal odds
    bankroll: float = 100_000.0
    daily_exposure_pct: float = 0.0
    peak_bankroll: float = 100_000.0
    consecutive_losses: int = 0
    sharp_signals: list[str] = field(default_factory=list)
    steam_detected: bool = False
    market_efficiency: float = 0.5


# ─── Configuration ───────────────────────────────────────────────────────────

# Gate 1: Consensus
MIN_MODEL_AGREEMENT = 0.60          # 60% of models must agree on side
MIN_MODELS_POSITIVE_EV = 3          # at least 3 models must show +EV

# Gate 2: Market Deviation
MAX_MODEL_MARKET_DEVIATION = 0.15   # model vs market can't diverge >15%
SUSPICIOUS_EDGE_THRESHOLD = 0.20    # edge >20% is suspicious (likely model error)
MIN_EDGE_THRESHOLD = 0.02           # minimum 2% edge to proceed

# Gate 3: Risk
MAX_SINGLE_BET = 0.05               # 5% of bankroll
MAX_DAILY_EXPOSURE = 0.15           # 15% total
MAX_DRAWDOWN_BETTING = 0.20         # stop betting at 20% drawdown
CONSECUTIVE_LOSS_LIMIT = 5          # reduce after 5 losses

# Gate 4: Sizing
KELLY_FRACTION = 0.25               # quarter-Kelly
MIN_BET_SIZE = 0.005                # 0.5% minimum

# Gate 5: Timing
STEAM_DELAY_MINUTES = 15            # wait after steam move
HIGH_VOLATILITY_DELAY = 30          # wait when market is volatile


# ─── Gate 1: Model Consensus Check ──────────────────────────────────────────

def gate_consensus(ctx: DecisionContext, bet: BetRecommendation) -> GateDecision:
    """
    Check that sufficient models agree on the bet direction.

    Measures:
      1. What fraction of models favor the same side?
      2. How many models show positive EV for this bet?
      3. Standard deviation of predictions (disagreement measure)
    """
    probs = ctx.sub_model_probs
    if not probs:
        return GateDecision(
            gate="CONSENSUS",
            result=GateResult.REJECT,
            reason="No sub-model predictions available",
        )

    # Determine bet side: is this bet on the favourite or underdog?
    bet_side = getattr(bet, "side", "home").lower()
    bet_on_home = "home" in bet_side

    # Count models agreeing with bet direction
    agreeing = 0
    positive_ev = 0
    total = len(probs)

    for _name, home_p in probs.items():
        model_bet_side_prob = home_p if bet_on_home else (1.0 - home_p)

        # Agreement: model also favours this side
        if (bet_on_home and home_p > 0.5) or (not bet_on_home and home_p < 0.5):
            agreeing += 1

        # Positive EV check
        ev = model_bet_side_prob * (ctx.odds - 1) - (1 - model_bet_side_prob)
        if ev > 0:
            positive_ev += 1

    agreement_pct = agreeing / max(total, 1)
    pred_values = list(probs.values())
    std = _std(pred_values)

    if agreement_pct < MIN_MODEL_AGREEMENT:
        return GateDecision(
            gate="CONSENSUS",
            result=GateResult.REJECT,
            reason=f"Model agreement {agreement_pct:.0%} < {MIN_MODEL_AGREEMENT:.0%} "
                   f"({agreeing}/{total} agree). High disagreement (σ={std:.3f})",
            original_value=agreement_pct,
        )

    if positive_ev < MIN_MODELS_POSITIVE_EV:
        return GateDecision(
            gate="CONSENSUS",
            result=GateResult.REJECT,
            reason=f"Only {positive_ev}/{total} models show +EV (need ≥{MIN_MODELS_POSITIVE_EV})",
            original_value=positive_ev,
        )

    # Reduce confidence if disagreement is moderate
    confidence = agreement_pct
    if std > 0.08:
        confidence *= 0.8

    return GateDecision(
        gate="CONSENSUS",
        result=GateResult.PASS,
        reason=f"Agreement {agreement_pct:.0%} ({agreeing}/{total}), "
               f"+EV models: {positive_ev}, σ={std:.3f}",
        original_value=agreement_pct,
        confidence=confidence,
    )


# ─── Gate 2: Market Deviation Assessment ────────────────────────────────────

def gate_market_deviation(ctx: DecisionContext, bet: BetRecommendation) -> GateDecision:
    """
    Verify model-vs-market deviation is in plausible range.

    Too small → no edge → reject
    Too large → likely model error → reject or reduce
    """
    edge = abs(ctx.model_prob - ctx.market_implied_prob)

    if edge < MIN_EDGE_THRESHOLD:
        return GateDecision(
            gate="MARKET_DEV",
            result=GateResult.REJECT,
            reason=f"Edge {edge:.1%} < minimum {MIN_EDGE_THRESHOLD:.1%}. "
                   f"Market is efficient for this bet.",
            original_value=edge,
        )

    if edge > SUSPICIOUS_EDGE_THRESHOLD:
        # Don't reject outright, but flag and reduce confidence
        return GateDecision(
            gate="MARKET_DEV",
            result=GateResult.MODIFY,
            reason=f"Edge {edge:.1%} > {SUSPICIOUS_EDGE_THRESHOLD:.1%} "
                   f"(suspicious — possible model miscalibration). "
                   f"Reducing confidence.",
            original_value=edge,
            modified_value=edge * 0.5,  # halve the assumed edge
            confidence=0.5,
        )

    if edge > MAX_MODEL_MARKET_DEVIATION:
        return GateDecision(
            gate="MARKET_DEV",
            result=GateResult.MODIFY,
            reason=f"Large deviation {edge:.1%}: model may have superior info "
                   f"or may be miscalibrated. Proceed with caution.",
            original_value=edge,
            modified_value=edge,
            confidence=0.7,
        )

    return GateDecision(
        gate="MARKET_DEV",
        result=GateResult.PASS,
        reason=f"Edge {edge:.1%} in normal range [{MIN_EDGE_THRESHOLD:.1%}, "
               f"{MAX_MODEL_MARKET_DEVIATION:.1%}]",
        original_value=edge,
        confidence=1.0,
    )


# ─── Gate 3: Risk Exposure Check ────────────────────────────────────────────

def gate_risk_exposure(ctx: DecisionContext, bet: BetRecommendation) -> GateDecision:
    """
    Ensure the bet doesn't exceed risk limits:
      - Single bet cap
      - Daily exposure cap
      - Drawdown halt
      - Consecutive loss reduction
    """
    drawdown = (ctx.peak_bankroll - ctx.bankroll) / max(ctx.peak_bankroll, 1)

    if drawdown >= MAX_DRAWDOWN_BETTING:
        return GateDecision(
            gate="RISK",
            result=GateResult.REJECT,
            reason=f"Drawdown {drawdown:.1%} ≥ halt threshold {MAX_DRAWDOWN_BETTING:.1%}. "
                   f"Stop all betting until recovery.",
            original_value=drawdown,
        )

    remaining_exposure = MAX_DAILY_EXPOSURE - ctx.daily_exposure_pct
    if remaining_exposure <= 0.005:
        return GateDecision(
            gate="RISK",
            result=GateResult.REJECT,
            reason=f"Daily exposure {ctx.daily_exposure_pct:.1%} ≥ cap {MAX_DAILY_EXPOSURE:.1%}",
            original_value=ctx.daily_exposure_pct,
        )

    # Check consecutive losses
    confidence = 1.0
    if ctx.consecutive_losses >= CONSECUTIVE_LOSS_LIMIT:
        confidence = 0.5
        reason = (f"Consecutive losses: {ctx.consecutive_losses} ≥ {CONSECUTIVE_LOSS_LIMIT}. "
                  f"Reducing position by 50%.")
        return GateDecision(
            gate="RISK",
            result=GateResult.MODIFY,
            reason=reason,
            original_value=1.0,
            modified_value=0.5,
            confidence=confidence,
        )

    return GateDecision(
        gate="RISK",
        result=GateResult.PASS,
        reason=f"Risk OK: drawdown {drawdown:.1%}, "
               f"exposure {ctx.daily_exposure_pct:.1%}/{MAX_DAILY_EXPOSURE:.1%}, "
               f"streak {ctx.consecutive_losses}",
        confidence=confidence,
    )


# ─── Gate 4: Position Sizing ────────────────────────────────────────────────

def gate_sizing(ctx: DecisionContext, bet: BetRecommendation) -> GateDecision:
    """
    Calculate optimal position size using fractional Kelly.
    Returns the stake percentage in modified_value.
    """
    model_prob = ctx.model_prob
    bet_side = getattr(bet, "side", "home").lower()
    if "away" in bet_side:
        bet_prob = 1.0 - model_prob
    else:
        bet_prob = model_prob

    odds = ctx.odds
    if odds <= 1.0 or bet_prob <= 0.0:
        return GateDecision(
            gate="SIZING",
            result=GateResult.REJECT,
            reason=f"Invalid odds ({odds}) or probability ({bet_prob:.3f})",
        )

    # Full Kelly
    b = odds - 1.0
    q = 1.0 - bet_prob
    kelly_full = (b * bet_prob - q) / b

    if kelly_full <= 0:
        return GateDecision(
            gate="SIZING",
            result=GateResult.REJECT,
            reason=f"Negative Kelly ({kelly_full:.3f}): no +EV at these odds",
        )

    # Apply fraction
    stake_pct = kelly_full * KELLY_FRACTION
    stake_pct = max(MIN_BET_SIZE, min(MAX_SINGLE_BET, stake_pct))

    return GateDecision(
        gate="SIZING",
        result=GateResult.PASS,
        reason=f"Kelly full={kelly_full:.3f}, fractional ({KELLY_FRACTION})={stake_pct:.3f}",
        original_value=kelly_full,
        modified_value=stake_pct,
    )


# ─── Gate 5: Timing & Delay Strategy ────────────────────────────────────────

def gate_timing(ctx: DecisionContext, bet: BetRecommendation) -> GateDecision:
    """
    Determine optimal bet placement timing.

    IMMEDIATE — place now
    DELAY     — wait for line movement to settle
    """
    if ctx.steam_detected:
        return GateDecision(
            gate="TIMING",
            result=GateResult.MODIFY,
            reason=f"Steam move detected. Delay {STEAM_DELAY_MINUTES}min "
                   f"for line settlement.",
            modified_value=STEAM_DELAY_MINUTES,
        )

    if ctx.market_efficiency < 0.3:
        return GateDecision(
            gate="TIMING",
            result=GateResult.MODIFY,
            reason=f"Low market efficiency ({ctx.market_efficiency:.0%}). "
                   f"Delay {HIGH_VOLATILITY_DELAY}min.",
            modified_value=HIGH_VOLATILITY_DELAY,
        )

    # Check for sharp signals
    sharp_count = len(ctx.sharp_signals)
    if sharp_count >= 3:
        return GateDecision(
            gate="TIMING",
            result=GateResult.MODIFY,
            reason=f"{sharp_count} sharp signals active. "
                   f"Delay {STEAM_DELAY_MINUTES}min.",
            modified_value=STEAM_DELAY_MINUTES,
        )

    return GateDecision(
        gate="TIMING",
        result=GateResult.PASS,
        reason="Market stable. Place immediately.",
        modified_value=0,
    )


# ─── Full Decision Pipeline ─────────────────────────────────────────────────

def run_decision_pipeline(
    bet: BetRecommendation,
    ctx: DecisionContext,
) -> BetDecision:
    """
    Run the 5-gate sequential decision pipeline.

    A bet must survive all 5 gates. Each gate can reject, pass, or modify.
    Modifications accumulate (e.g., reduced confidence → smaller position).
    """
    gates: list[GateDecision] = []
    confidence_multiplier = 1.0
    position_multiplier = 1.0
    timing = "IMMEDIATE"
    delay = 0

    # Gate 1: Consensus
    g1 = gate_consensus(ctx, bet)
    gates.append(g1)
    if g1.result == GateResult.REJECT:
        return _build_rejected(bet, gates, "Failed consensus check")
    confidence_multiplier *= g1.confidence

    # Gate 2: Market Deviation
    g2 = gate_market_deviation(ctx, bet)
    gates.append(g2)
    if g2.result == GateResult.REJECT:
        return _build_rejected(bet, gates, "Failed market deviation check")
    confidence_multiplier *= g2.confidence

    # Gate 3: Risk
    g3 = gate_risk_exposure(ctx, bet)
    gates.append(g3)
    if g3.result == GateResult.REJECT:
        return _build_rejected(bet, gates, "Failed risk check")
    if g3.result == GateResult.MODIFY:
        position_multiplier *= g3.modified_value

    # Gate 4: Sizing
    g4 = gate_sizing(ctx, bet)
    gates.append(g4)
    if g4.result == GateResult.REJECT:
        return _build_rejected(bet, gates, "Negative EV at current odds")
    base_stake = g4.modified_value

    # Gate 5: Timing
    g5 = gate_timing(ctx, bet)
    gates.append(g5)
    if g5.result == GateResult.MODIFY:
        delay = int(g5.modified_value)
        timing = f"DELAY_{delay}MIN"
    else:
        timing = "IMMEDIATE"

    # Compute final stake
    final_stake_pct = base_stake * confidence_multiplier * position_multiplier
    final_stake_pct = max(MIN_BET_SIZE, min(MAX_SINGLE_BET, final_stake_pct))
    final_amount = final_stake_pct * ctx.bankroll

    passed_gates = sum(1 for g in gates if g.result != GateResult.REJECT)

    return BetDecision(
        bet=bet,
        approved=True,
        gates=gates,
        final_stake_pct=round(final_stake_pct, 5),
        final_stake_amount=round(final_amount, 2),
        timing=timing,
        delay_minutes=delay,
        summary=f"APPROVED ✓ | {passed_gates}/5 gates passed | "
                f"Stake: {final_stake_pct:.2%} (${final_amount:,.0f}) | "
                f"Timing: {timing}",
    )


def run_batch_decisions(
    bets: list[BetRecommendation],
    ctx: DecisionContext,
) -> list[BetDecision]:
    """
    Run decision pipeline for multiple bets.
    Tracks cumulative exposure across bets.
    """
    decisions: list[BetDecision] = []
    cumulative_exposure = ctx.daily_exposure_pct

    for bet in bets:
        ctx.daily_exposure_pct = cumulative_exposure
        decision = run_decision_pipeline(bet, ctx)
        decisions.append(decision)

        if decision.approved:
            cumulative_exposure += decision.final_stake_pct

    return decisions


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _build_rejected(
    bet: BetRecommendation,
    gates: list[GateDecision],
    reason: str,
) -> BetDecision:
    return BetDecision(
        bet=bet,
        approved=False,
        gates=gates,
        summary=f"REJECTED ✗ | {reason}",
    )


def _std(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    var = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    return math.sqrt(max(var, 0))
