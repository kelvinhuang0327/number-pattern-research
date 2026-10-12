"""
Edge Realism Filter
=====================
Evaluates whether a predicted edge can actually be monetised in the
real market.  A model may correctly identify a +5 % edge, but if:

  - the line moves away before execution
  - sharp money is on the OTHER side
  - the market instantly absorbs any bet size
  - the closing line already embeds the edge

…then the edge is FAKE and untradeable.

Five scoring dimensions (0-20 each, total 0-100):

  1. Edge Stability        — prediction prob variance across recent snapshots
  2. Market Absorption     — does the market absorb volume without moving?
  3. Sharp Alignment       — is sharp money going the same direction?
  4. CLV Potential          — can we still beat the closing line?
  5. Execution Feasibility — will our bet size move the line against us?

Classification:
  <50   FAKE_EDGE
  50–65 WEAK_EDGE
  65–80 TRADEABLE_EDGE
  80+   INSTITUTIONAL_EDGE

Hard rule:  REAL_EDGE_SCORE < 65  →  bet FORBIDDEN.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum


# ─── Labels ─────────────────────────────────────────────────────────────────

class RealEdgeLabel(Enum):
    FAKE_EDGE = "FAKE_EDGE"
    WEAK_EDGE = "WEAK_EDGE"
    TRADEABLE_EDGE = "TRADEABLE_EDGE"
    INSTITUTIONAL_EDGE = "INSTITUTIONAL_EDGE"


# ─── Configuration ──────────────────────────────────────────────────────────

REALISM_THRESHOLD = 65          # minimum to allow a bet
COMPONENT_MAX = 20.0            # each factor scores 0-20

WEIGHTS = {
    "edge_stability": 0.25,
    "market_absorption": 0.20,
    "sharp_alignment": 0.20,
    "clv_potential": 0.20,
    "execution_feasibility": 0.15,
}

# Ensure weights sum to 1.0
assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9


# ─── Data Structures ────────────────────────────────────────────────────────

@dataclass
class RealismInput:
    """All signals needed for the realism assessment."""
    # Core prediction
    model_probability: float = 0.55
    market_odds: float = 2.00

    # Liquidity / depth
    market_liquidity_score: float = 0.5     # 0 = bone dry, 1 = deep
    n_sportsbooks: int = 3
    odds_spread_pct: float = 0.04           # (max-min)/mid across books

    # Line movement
    line_movement_velocity: float = 0.0     # implied-prob change / hour
    total_line_moves: int = 0
    opening_odds: float = 0.0               # 0 = unknown
    hours_to_game: float = 24.0

    # Sharp money
    sharp_money_signal: int = 0             # count of sharp signals
    sharp_direction_agrees: bool = True     # does sharp money agree w/ model?
    steam_moves: int = 0
    reverse_line_moves: int = 0

    # CLV history
    closing_line_history: list[float] = field(default_factory=list)
    # list of historical CLV values from previous bets (positive = beat close)

    # Prediction stability
    recent_model_probs: list[float] = field(default_factory=list)
    # the same model's prob snapshots over the last N hours

    # Execution
    intended_bet_pct: float = 0.02          # intended bet as % of bankroll
    bankroll: float = 10000.0


@dataclass
class RealismReport:
    """Complete realism assessment output."""
    # Component scores (0-20 each, pre-weighting)
    edge_stability_raw: float = 0.0
    market_absorption_raw: float = 0.0
    sharp_alignment_raw: float = 0.0
    clv_potential_raw: float = 0.0
    execution_feasibility_raw: float = 0.0

    # Weighted composite (0-100)
    real_edge_score: float = 0.0
    real_edge_label: RealEdgeLabel = RealEdgeLabel.FAKE_EDGE
    is_tradeable: bool = False

    # Diagnostics
    details: dict[str, str] = field(default_factory=dict)
    blocking_reason: str = ""


# ─── Component 1: Edge Stability ────────────────────────────────────────────

def _score_edge_stability(inp: RealismInput) -> tuple[float, str]:
    """
    Is the model's prediction stable or oscillating wildly?

    Uses recent_model_probs snapshots.  Low stddev across snapshots = stable.
    Also checks if the probability is drifting (trend) vs jittering.
    """
    snapshots = inp.recent_model_probs
    if len(snapshots) < 2:
        # No multi-snapshot data — give neutral score but flag it
        return 12.0, "single_snapshot=neutral"

    mean_p = sum(snapshots) / len(snapshots)
    var = sum((p - mean_p) ** 2 for p in snapshots) / len(snapshots)
    stddev = math.sqrt(var)

    # Score inversely proportional to stddev
    # stddev 0.00 → 20,  stddev ≥ 0.08 → 0
    if stddev >= 0.08:
        raw = 0.0
    else:
        raw = COMPONENT_MAX * (1.0 - stddev / 0.08)

    # Trend bonus: if all snapshots trend the same direction, it's more stable
    diffs = [snapshots[i+1] - snapshots[i] for i in range(len(snapshots)-1)]
    positive_trend = all(d >= 0 for d in diffs) or all(d <= 0 for d in diffs)
    if positive_trend and len(diffs) >= 2:
        raw = min(COMPONENT_MAX, raw + 2.0)

    # Penalty: if latest snapshot diverges sharply from mean
    latest_gap = abs(snapshots[-1] - mean_p)
    if latest_gap > 0.05:
        raw = max(0, raw - 3.0)

    detail = f"stddev={stddev:.4f} trend={'mono' if positive_trend else 'jitter'}"
    return round(raw, 2), detail


# ─── Component 2: Market Absorption ─────────────────────────────────────────

def _score_market_absorption(inp: RealismInput) -> tuple[float, str]:
    """
    Can the market absorb a bet without the line moving?

    High liquidity + low movement velocity = market absorbs well.
    """
    score = 0.0

    # Liquidity contribution (0-8)
    liq = inp.market_liquidity_score
    score += min(8.0, liq * 10.0)

    # Multiple sportsbooks = better absorption (0-4)
    book_score = min(4.0, (inp.n_sportsbooks - 1) * 1.0)
    score += book_score

    # Low movement velocity = not reactive (0-4)
    vel = inp.line_movement_velocity
    if vel < 0.005:
        vel_score = 4.0
    elif vel < 0.015:
        vel_score = 4.0 * (1.0 - (vel - 0.005) / 0.010)
    else:
        vel_score = 0.0
    score += vel_score

    # Tight spread = deep market (0-4)
    spread = inp.odds_spread_pct
    if spread < 0.02:
        spread_score = 4.0
    elif spread < 0.06:
        spread_score = 4.0 * (1.0 - (spread - 0.02) / 0.04)
    else:
        spread_score = 0.0
    score += spread_score

    detail = f"liq={liq:.2f} books={inp.n_sportsbooks} vel={vel:.4f} spread={spread:.3f}"
    return round(min(COMPONENT_MAX, score), 2), detail


# ─── Component 3: Sharp Alignment ───────────────────────────────────────────

def _score_sharp_alignment(inp: RealismInput) -> tuple[float, str]:
    """
    Is smart money on the same side as our model?

    Sharp agreement = the edge is likely real.
    Sharp disagreement = the edge is likely fake (market already knows).
    """
    score = 10.0  # neutral baseline

    if inp.sharp_money_signal == 0:
        # No sharp data — neutral, slight penalty for uncertainty
        detail = "no_sharp_data=neutral"
        return 10.0, detail

    if inp.sharp_direction_agrees:
        # Agreement: more signals = more confidence
        agreement_boost = min(10.0, inp.sharp_money_signal * 3.0)
        score += agreement_boost

        # Steam moves in our direction = very strong
        if inp.steam_moves > 0:
            score = min(COMPONENT_MAX, score + 2.0)
    else:
        # Disagreement: sharps are AGAINST us
        disagreement_penalty = min(10.0, inp.sharp_money_signal * 4.0)
        score -= disagreement_penalty

        # Reverse line moves against us = very bad
        if inp.reverse_line_moves > 0:
            score = max(0, score - 3.0)

    detail = (
        f"signals={inp.sharp_money_signal} "
        f"agrees={inp.sharp_direction_agrees} "
        f"steam={inp.steam_moves} rlm={inp.reverse_line_moves}"
    )
    return round(max(0, min(COMPONENT_MAX, score)), 2), detail


# ─── Component 4: CLV Potential ──────────────────────────────────────────────

def _score_clv_potential(inp: RealismInput) -> tuple[float, str]:  # noqa: C901
    """
    Based on historical closing-line-value and current market timing,
    can we still extract CLV?

    If our past CLV is positive, future CLV is more likely.
    If the line has already moved to our price, CLV is gone.
    """
    score = 10.0  # neutral

    # Historical CLV track record
    clv_hist = inp.closing_line_history
    if clv_hist:
        mean_clv = sum(clv_hist) / len(clv_hist)
        positive_rate = sum(1 for c in clv_hist if c > 0) / len(clv_hist)

        # Mean CLV contribution (0-8)
        if mean_clv > 0.02:
            clv_boost = min(8.0, mean_clv * 200)
        elif mean_clv > 0:
            clv_boost = mean_clv * 200
        else:
            clv_boost = max(-8.0, mean_clv * 150)
        score += clv_boost

        # Consistency bonus
        if positive_rate > 0.60 and len(clv_hist) >= 10:
            score += 2.0
    else:
        # No history — slight penalty
        score -= 2.0

    # Timing: more time to close = more CLV capture opportunity
    h = inp.hours_to_game
    if h > 12:
        score += 2.0
    elif h > 3:
        score += 1.0
    elif h < 1:
        score -= 2.0  # very close to game, CLV already baked

    # Opening-to-current movement: if line already moved toward our price,
    # remaining CLV is limited
    if inp.opening_odds > 0:
        open_implied = 1.0 / inp.opening_odds if inp.opening_odds > 1 else 0.5
        curr_implied = 1.0 / inp.market_odds if inp.market_odds > 1 else 0.5
        shift = curr_implied - open_implied

        # If model says HOME and implied prob went UP → line moved toward us
        model_side_home = inp.model_probability > 0.5
        if model_side_home and shift > 0.02:
            score -= 2.0  # CLV already captured by others
        elif not model_side_home and shift < -0.02:
            score -= 2.0
        elif model_side_home and shift < -0.01:
            score += 1.0  # line moving away = edge growing
        elif not model_side_home and shift > 0.01:
            score += 1.0

    detail = (
        f"hist_n={len(clv_hist)} "
        f"hours={h:.1f} "
        f"opening={'yes' if inp.opening_odds > 0 else 'no'}"
    )
    return round(max(0, min(COMPONENT_MAX, score)), 2), detail


# ─── Component 5: Execution Feasibility ─────────────────────────────────────

def _score_execution_feasibility(inp: RealismInput) -> tuple[float, str]:
    """
    Will the intended bet size move the line against us?

    Large bets in illiquid markets = self-defeating.
    Small bets in liquid markets = full edge capture.
    """
    bet_amount = inp.intended_bet_pct * inp.bankroll
    liq = inp.market_liquidity_score

    # Normalised "market capacity" proxy
    # In a deep market (liq=1.0) we assume $10K+ can be absorbed.
    # In a thin market (liq=0.2) only ~$500 absorbed without impact.
    estimated_capacity = max(100, liq * 12000)

    fill_ratio = bet_amount / estimated_capacity  # < 1 = fine, > 1 = problem

    if fill_ratio < 0.3:
        score = COMPONENT_MAX
    elif fill_ratio < 0.6:
        score = COMPONENT_MAX * (1.0 - (fill_ratio - 0.3) / 0.3 * 0.3)
    elif fill_ratio < 1.0:
        score = COMPONENT_MAX * 0.5 * (1.0 - (fill_ratio - 0.6) / 0.4)
    else:
        # Bet exceeds estimated capacity
        overshoot = fill_ratio - 1.0
        score = max(0, COMPONENT_MAX * 0.2 * (1.0 - overshoot))

    # Bonus: many books = can split across venues
    if inp.n_sportsbooks >= 4 and fill_ratio > 0.5:
        score = min(COMPONENT_MAX, score + 3.0)

    # Penalty: close to game + big bet = harder to place
    if inp.hours_to_game < 1 and fill_ratio > 0.4:
        score = max(0, score - 3.0)

    detail = (
        f"amount=${bet_amount:.0f} "
        f"capacity=${estimated_capacity:.0f} "
        f"fill={fill_ratio:.2f}"
    )
    return round(max(0, min(COMPONENT_MAX, score)), 2), detail


# ─── Main Engine ─────────────────────────────────────────────────────────────

def assess_edge_realism(inp: RealismInput) -> RealismReport:
    """
    Compute the Real Edge Score (0-100) from 5 weighted components.

    Returns a RealismReport with score, label, and full diagnostics.
    """
    report = RealismReport()

    # Score each component
    s1, d1 = _score_edge_stability(inp)
    s2, d2 = _score_market_absorption(inp)
    s3, d3 = _score_sharp_alignment(inp)
    s4, d4 = _score_clv_potential(inp)
    s5, d5 = _score_execution_feasibility(inp)

    report.edge_stability_raw = s1
    report.market_absorption_raw = s2
    report.sharp_alignment_raw = s3
    report.clv_potential_raw = s4
    report.execution_feasibility_raw = s5

    # Weighted composite → scale to 0-100
    # Each raw component is 0-20.  Weighted sum of (raw/20) gives 0-1.
    # Multiply by 100 for final score.
    composite = (
        WEIGHTS["edge_stability"] * (s1 / COMPONENT_MAX)
        + WEIGHTS["market_absorption"] * (s2 / COMPONENT_MAX)
        + WEIGHTS["sharp_alignment"] * (s3 / COMPONENT_MAX)
        + WEIGHTS["clv_potential"] * (s4 / COMPONENT_MAX)
        + WEIGHTS["execution_feasibility"] * (s5 / COMPONENT_MAX)
    ) * 100.0

    report.real_edge_score = round(max(0, min(100, composite)), 1)

    # Classification
    if report.real_edge_score >= 80:
        report.real_edge_label = RealEdgeLabel.INSTITUTIONAL_EDGE
    elif report.real_edge_score >= 65:
        report.real_edge_label = RealEdgeLabel.TRADEABLE_EDGE
    elif report.real_edge_score >= 50:
        report.real_edge_label = RealEdgeLabel.WEAK_EDGE
    else:
        report.real_edge_label = RealEdgeLabel.FAKE_EDGE

    report.is_tradeable = report.real_edge_score >= REALISM_THRESHOLD

    if not report.is_tradeable:
        report.blocking_reason = (
            f"Real Edge Score {report.real_edge_score:.1f} < {REALISM_THRESHOLD} "
            f"({report.real_edge_label.value})"
        )

    report.details = {
        "edge_stability": f"{s1:.1f}/20 — {d1}",
        "market_absorption": f"{s2:.1f}/20 — {d2}",
        "sharp_alignment": f"{s3:.1f}/20 — {d3}",
        "clv_potential": f"{s4:.1f}/20 — {d4}",
        "execution_feasibility": f"{s5:.1f}/20 — {d5}",
    }

    return report
