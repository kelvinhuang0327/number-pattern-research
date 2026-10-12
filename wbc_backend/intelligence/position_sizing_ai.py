"""
Phase 4 — Position Sizing AI
================================
Dynamically selects the optimal position-sizing strategy based on:

  - Current drawdown state
  - Edge strength & confidence tier
  - Bankroll volatility
  - Prediction entropy
  - Market regime

Five sizing strategies compete:
  1. Fractional Kelly     — standard f* = (bp - q) / b scaled by fraction
  2. Drawdown Kelly       — reduces size as drawdown deepens
  3. Volatility Scaled    — scales inversely with recent P&L volatility
  4. Confidence Weighted  — scales with edge_score / confidence_tier
  5. Entropy Adjusted     — reduces size when prediction entropy is high

The AI selects the strategy that would have produced the best
risk-adjusted returns over the trailing window, then applies it.

NO FIXED KELLY ALLOWED.  Every bet gets a dynamically chosen sizing.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum


# ─── Sizing Strategies ─────────────────────────────────────────────────────

class SizingStrategy(Enum):
    FRACTIONAL_KELLY = "FRACTIONAL_KELLY"
    DRAWDOWN_KELLY = "DRAWDOWN_KELLY"
    VOLATILITY_SCALED = "VOLATILITY_SCALED"
    CONFIDENCE_WEIGHTED = "CONFIDENCE_WEIGHTED"
    ENTROPY_ADJUSTED = "ENTROPY_ADJUSTED"


# ─── Configuration ──────────────────────────────────────────────────────────

SIZING_CONFIG = {
    "kelly_fraction": 0.25,           # quarter Kelly as base
    "max_bet_pct": 0.025,             # absolute max 2.5% of bankroll
    "min_bet_pct": 0.005,             # minimum 0.5%
    "drawdown_decay_rate": 3.0,       # how fast sizing shrinks with drawdown
    "volatility_lookback": 20,        # recent bets for vol calc
    "volatility_target": 0.03,        # target daily P&L vol
    "entropy_penalty_rate": 2.0,      # how aggressively to penalise entropy
    "confidence_scale": {             # multipliers by confidence tier
        "ELITE": 1.0,
        "STRONG": 0.75,
        "MODERATE": 0.50,
        "WEAK": 0.25,
    },
    "regime_scale": {                 # additional regime adjustments
        "PUBLIC_BIAS": 1.1,
        "LIQUID_MARKET": 1.0,
        "ILLIQUID_MARKET": 0.6,
        "SHARP_DOMINATED": 0.0,       # should never reach here
        "BOOKMAKER_TRAP": 0.0,        # should never reach here
    },
    "trailing_window": 50,            # bets to evaluate strategy performance
}


# ─── Data Structures ────────────────────────────────────────────────────────

@dataclass
class SizingInput:
    """All inputs needed for position sizing."""
    # Bet specifics
    odds: float = 2.0
    calibrated_prob: float = 0.55
    edge_pct: float = 0.05
    adjusted_edge: float = 0.05

    # Scores
    edge_score: float = 75.0
    confidence_tier: str = "MODERATE"
    prediction_entropy: float = 0.30   # bits

    # Regime
    regime: str = "LIQUID_MARKET"
    regime_confidence: float = 0.5

    # Bankroll state
    bankroll: float = 10000.0
    peak_bankroll: float = 10000.0
    current_drawdown: float = 0.0      # 0 = no drawdown, 0.1 = 10% dd

    # Recent performance
    recent_pnl: list[float] = field(default_factory=list)  # last N P&L as %


@dataclass
class SizingResult:
    """Position sizing decision."""
    strategy_used: SizingStrategy = SizingStrategy.FRACTIONAL_KELLY
    bet_size_pct: float = 0.01         # % of bankroll
    bet_amount: float = 100.0          # absolute amount
    raw_kelly: float = 0.0
    all_strategies: dict[str, float] = field(default_factory=dict)
    strategy_scores: dict[str, float] = field(default_factory=dict)
    reasoning: str = ""
    capped: bool = False
    cap_reason: str = ""


# ─── Individual Strategy Functions ──────────────────────────────────────────

def _fractional_kelly(inp: SizingInput) -> float:
    """Standard fractional Kelly criterion."""
    b = inp.odds - 1.0  # net payout
    if b <= 0:
        return 0.0
    p = inp.calibrated_prob
    q = 1.0 - p
    kelly = (b * p - q) / b
    if kelly <= 0:
        return 0.0
    return kelly * SIZING_CONFIG["kelly_fraction"]


def _drawdown_kelly(inp: SizingInput) -> float:
    """Kelly adjusted by current drawdown depth."""
    base = _fractional_kelly(inp)
    if base <= 0:
        return 0.0

    dd = inp.current_drawdown
    decay = SIZING_CONFIG["drawdown_decay_rate"]

    # Exponential decay: at 10% dd → ~74% of base, at 20% dd → ~55%
    multiplier = math.exp(-decay * dd)
    return base * multiplier


def _volatility_scaled(inp: SizingInput) -> float:
    """Scale sizing inversely with recent P&L volatility."""
    base = _fractional_kelly(inp)
    if base <= 0:
        return 0.0

    recent = inp.recent_pnl
    if len(recent) < 5:
        return base  # not enough data, use base

    # Compute volatility of recent P&L
    mean_pnl = sum(recent) / len(recent)
    var = sum((x - mean_pnl) ** 2 for x in recent) / len(recent)
    vol = math.sqrt(var) if var > 0 else 0.001

    target_vol = SIZING_CONFIG["volatility_target"]
    scaling = target_vol / max(vol, 0.001)
    scaling = max(0.3, min(2.0, scaling))  # clamp

    return base * scaling


def _confidence_weighted(inp: SizingInput) -> float:
    """Scale sizing by confidence tier and edge score."""
    base = _fractional_kelly(inp)
    if base <= 0:
        return 0.0

    tier_mult = SIZING_CONFIG["confidence_scale"].get(inp.confidence_tier, 0.5)
    edge_mult = min(1.0, inp.edge_score / 90.0)  # normalise to 90

    return base * tier_mult * edge_mult


def _entropy_adjusted(inp: SizingInput) -> float:
    """Reduce sizing when prediction entropy is high (uncertain)."""
    base = _fractional_kelly(inp)
    if base <= 0:
        return 0.0

    entropy = inp.prediction_entropy
    rate = SIZING_CONFIG["entropy_penalty_rate"]

    # Ideal entropy ~0.1-0.2. Penalise above 0.3
    if entropy < 0.15:
        mult = 1.0
    elif entropy < 0.40:
        mult = 1.0 - rate * (entropy - 0.15) / 0.85
        mult = max(0.2, mult)
    else:
        mult = 0.2  # very uncertain

    return base * mult


# Strategy function mapping
_STRATEGY_FUNCS = {
    SizingStrategy.FRACTIONAL_KELLY: _fractional_kelly,
    SizingStrategy.DRAWDOWN_KELLY: _drawdown_kelly,
    SizingStrategy.VOLATILITY_SCALED: _volatility_scaled,
    SizingStrategy.CONFIDENCE_WEIGHTED: _confidence_weighted,
    SizingStrategy.ENTROPY_ADJUSTED: _entropy_adjusted,
}


# ─── Strategy Selection ────────────────────────────────────────────────────

def _evaluate_strategies_trailing(
    recent_pnl: list[float],
    recent_sizes: list[float],
    recent_strategies: list[str],
) -> dict[str, float]:
    """
    Evaluate each strategy's trailing risk-adjusted performance.
    Returns a score for each strategy (higher = better).
    """
    scores = {}
    for strat in SizingStrategy:
        # If we haven't used this strategy, give it a neutral score
        matching = [
            (pnl, size)
            for pnl, size, s in zip(recent_pnl, recent_sizes, recent_strategies)
            if s == strat.value
        ]
        if len(matching) < 3:
            scores[strat.value] = 0.5  # neutral
            continue

        # Risk-adjusted return: mean / (vol + epsilon)
        pnls = [m[0] for m in matching]
        mean_r = sum(pnls) / len(pnls)
        var = sum((x - mean_r) ** 2 for x in pnls) / len(pnls)
        vol = math.sqrt(var) if var > 0 else 0.01
        sharpe = mean_r / vol

        # Normalise to [0, 1]
        scores[strat.value] = max(0.0, min(1.0, 0.5 + sharpe * 0.2))

    return scores


def _select_best_strategy(
    inp: SizingInput,
    trailing_scores: dict[str, float] | None = None,
) -> SizingStrategy:
    """
    Select the best sizing strategy based on current conditions and
    trailing performance.
    """
    if trailing_scores is None:
        trailing_scores = {s.value: 0.5 for s in SizingStrategy}

    # Condition-based priors
    priors: dict[SizingStrategy, float] = {}

    # High drawdown → prefer drawdown Kelly
    if inp.current_drawdown > 0.10:
        priors[SizingStrategy.DRAWDOWN_KELLY] = 0.8
    elif inp.current_drawdown > 0.05:
        priors[SizingStrategy.DRAWDOWN_KELLY] = 0.6
    else:
        priors[SizingStrategy.DRAWDOWN_KELLY] = 0.3

    # High entropy → prefer entropy adjusted
    if inp.prediction_entropy > 0.35:
        priors[SizingStrategy.ENTROPY_ADJUSTED] = 0.7
    else:
        priors[SizingStrategy.ENTROPY_ADJUSTED] = 0.3

    # High volatility → prefer volatility scaled
    if inp.recent_pnl and len(inp.recent_pnl) >= 5:
        mean_pnl = sum(inp.recent_pnl) / len(inp.recent_pnl)
        var = sum((x - mean_pnl) ** 2 for x in inp.recent_pnl) / len(inp.recent_pnl)
        vol = math.sqrt(var)
        if vol > 0.05:
            priors[SizingStrategy.VOLATILITY_SCALED] = 0.7
        else:
            priors[SizingStrategy.VOLATILITY_SCALED] = 0.3
    else:
        priors[SizingStrategy.VOLATILITY_SCALED] = 0.4

    # Strong confidence → confidence weighted
    if inp.confidence_tier in ("ELITE", "STRONG"):
        priors[SizingStrategy.CONFIDENCE_WEIGHTED] = 0.6
    else:
        priors[SizingStrategy.CONFIDENCE_WEIGHTED] = 0.4

    # Fractional Kelly is the safe default
    priors[SizingStrategy.FRACTIONAL_KELLY] = 0.5

    # Combine priors (40%) with trailing performance (60%)
    combined = {}
    for strat in SizingStrategy:
        prior = priors.get(strat, 0.5)
        trailing = trailing_scores.get(strat.value, 0.5)
        combined[strat] = 0.40 * prior + 0.60 * trailing

    return max(combined, key=combined.get)


# ─── Main Entry Point ──────────────────────────────────────────────────────

def compute_position_size(
    inp: SizingInput,
    trailing_pnl: list[float] | None = None,
    trailing_sizes: list[float] | None = None,
    trailing_strategies: list[str] | None = None,
) -> SizingResult:
    """
    Compute the optimal position size for a bet.

    Dynamically selects the best sizing strategy, then applies
    regime scaling and hard caps.
    """
    # Evaluate trailing performance
    trailing_scores = None
    if trailing_pnl and trailing_sizes and trailing_strategies:
        trailing_scores = _evaluate_strategies_trailing(
            trailing_pnl, trailing_sizes, trailing_strategies,
        )

    # Select best strategy
    best_strategy = _select_best_strategy(inp, trailing_scores)

    # Compute all strategy sizes
    all_sizes = {}
    for strat in SizingStrategy:
        fn = _STRATEGY_FUNCS[strat]
        all_sizes[strat.value] = round(fn(inp), 6)

    # Use the selected strategy's size
    raw_size = all_sizes[best_strategy.value]

    # Raw Kelly for reference
    b = inp.odds - 1.0
    if b > 0:
        raw_kelly = max(0, (b * inp.calibrated_prob - (1 - inp.calibrated_prob)) / b)
    else:
        raw_kelly = 0.0

    # Apply regime scaling
    regime_scale = SIZING_CONFIG["regime_scale"].get(inp.regime, 1.0)
    adjusted_size = raw_size * regime_scale

    # Hard caps
    max_pct = SIZING_CONFIG["max_bet_pct"]
    min_pct = SIZING_CONFIG["min_bet_pct"]

    capped = False
    cap_reason = ""
    if adjusted_size > max_pct:
        capped = True
        cap_reason = f"Capped at max {max_pct:.1%}"
        adjusted_size = max_pct
    elif 0 < adjusted_size < min_pct:
        capped = True
        cap_reason = f"Floored at min {min_pct:.1%}"
        adjusted_size = min_pct

    if adjusted_size <= 0:
        adjusted_size = 0.0

    bet_amount = round(adjusted_size * inp.bankroll, 2)

    return SizingResult(
        strategy_used=best_strategy,
        bet_size_pct=round(adjusted_size, 6),
        bet_amount=bet_amount,
        raw_kelly=round(raw_kelly, 6),
        all_strategies=all_sizes,
        strategy_scores=trailing_scores or {},
        reasoning=(
            f"Strategy={best_strategy.value}, "
            f"raw_size={raw_size:.4f}, "
            f"regime_scale={regime_scale}, "
            f"final={adjusted_size:.4f} "
            f"({bet_amount:.0f} on {inp.bankroll:.0f} bankroll)"
        ),
        capped=capped,
        cap_reason=cap_reason,
    )
