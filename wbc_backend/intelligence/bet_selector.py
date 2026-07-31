"""
Phase 3 — Bet Selection Intelligence
=======================================
Four conditions must ALL be met before a bet is selected:

  1. EdgeScore ≥ 70  (from edge_validator)
  2. PredStdDev ≤ dynamic threshold  (model agreement)
  3. Regime ≠ SHARP_DOMINATED and Regime ≠ BOOKMAKER_TRAP
  4. ModelConsensus ≥ 60%  (sub-model directional agreement)

Additional filters:
  - Minimum odds band ROI > 0   (historical profitability)
  - Edge × Regime multiplier > minimum viable edge
  - No more than N bets per day

Outputs a BetCandidate with full justification.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum

from wbc_backend.intelligence.edge_validator import EdgeReport
from wbc_backend.intelligence.regime_classifier import (
    MarketRegime,
    RegimeReport,
)


# ─── Configuration ──────────────────────────────────────────────────────────

class SelectionGate(Enum):
    EDGE_SCORE = "EDGE_SCORE"
    MODEL_CONSENSUS = "MODEL_CONSENSUS"
    PREDICTION_STABILITY = "PREDICTION_STABILITY"
    REGIME_FILTER = "REGIME_FILTER"
    ODDS_BAND_ROI = "ODDS_BAND_ROI"
    VIABLE_EDGE = "VIABLE_EDGE"
    DAILY_LIMIT = "DAILY_LIMIT"


# Gate thresholds (tunable)
GATE_THRESHOLDS = {
    "edge_score_min": 70,
    "model_consensus_min": 0.60,       # 60%
    "pred_stddev_max": 0.12,           # max stddev among sub-models
    "min_viable_edge": 0.02,           # 2% minimum edge after regime adj
    "min_odds_band_roi": 0.0,          # historical band must be positive
    "max_daily_bets": 5,               # max bets per day
    "min_odds": 1.40,                  # don't bet extreme favourites
    "max_odds": 4.50,                  # don't bet extreme longshots
}

# ─── Data Structures ────────────────────────────────────────────────────────

@dataclass
class GateResult:
    """Result of a single gate check."""
    gate: SelectionGate
    passed: bool
    value: float = 0.0
    threshold: float = 0.0
    reason: str = ""


@dataclass
class BetCandidate:
    """A bet that has passed all selection gates."""
    match_id: str = ""
    match_label: str = ""
    bet_type: str = ""                  # ML / RL / OU / F5
    side: str = ""                      # HOME / AWAY / OVER / UNDER
    odds: float = 1.0
    implied_prob: float = 0.5

    # Model outputs
    model_prob: float = 0.5
    calibrated_prob: float = 0.5
    edge_pct: float = 0.0              # calibrated_prob - implied_prob
    adjusted_edge: float = 0.0          # after regime multiplier

    # Scores
    edge_score: float = 0.0
    model_consensus: float = 0.0
    pred_stddev: float = 0.0
    regime: str = "LIQUID_MARKET"
    regime_confidence: float = 0.5

    # Gate audit trail
    gates_passed: list[GateResult] = field(default_factory=list)
    all_passed: bool = False

    # Selection metadata
    confidence_tier: str = "MODERATE"
    priority_score: float = 0.0         # for ranking multiple candidates
    reasoning: str = ""


@dataclass
class SelectionResult:
    """Complete selection result for a match."""
    match_id: str = ""
    candidates_evaluated: int = 0
    candidates_selected: int = 0
    selected: list[BetCandidate] = field(default_factory=list)
    rejected: list[BetCandidate] = field(default_factory=list)
    daily_bet_count: int = 0
    summary: str = ""


# ─── Gate Checks ────────────────────────────────────────────────────────────

def _check_edge_score(edge_report: EdgeReport) -> GateResult:
    """Gate 1: Edge score must meet minimum threshold."""
    threshold = GATE_THRESHOLDS["edge_score_min"]
    return GateResult(
        gate=SelectionGate.EDGE_SCORE,
        passed=edge_report.edge_score >= threshold,
        value=edge_report.edge_score,
        threshold=threshold,
        reason=(
            f"Edge score {edge_report.edge_score:.1f} "
            f"{'≥' if edge_report.edge_score >= threshold else '<'} "
            f"threshold {threshold}"
        ),
    )


def _check_model_consensus(
    sub_model_probs: list[float],
    predicted_side_prob: float,
) -> GateResult:
    """
    Gate 2: Model consensus — at least 60% of sub-models
    must agree on the predicted direction.

    Direction = prob > 0.5 means predicted team wins.
    """
    threshold = GATE_THRESHOLDS["model_consensus_min"]

    if not sub_model_probs:
        return GateResult(
            gate=SelectionGate.MODEL_CONSENSUS,
            passed=False, value=0.0, threshold=threshold,
            reason="No sub-model probabilities provided",
        )

    direction = predicted_side_prob > 0.5
    agree = sum(1 for p in sub_model_probs if (p > 0.5) == direction)
    pct = agree / len(sub_model_probs)

    return GateResult(
        gate=SelectionGate.MODEL_CONSENSUS,
        passed=pct >= threshold,
        value=round(pct, 3),
        threshold=threshold,
        reason=(
            f"{agree}/{len(sub_model_probs)} models agree "
            f"({pct:.0%} {'≥' if pct >= threshold else '<'} {threshold:.0%})"
        ),
    )


def _check_prediction_stability(sub_model_probs: list[float]) -> GateResult:
    """
    Gate 3: Prediction stability — standard deviation of sub-model
    probabilities must be below threshold.
    """
    threshold = GATE_THRESHOLDS["pred_stddev_max"]

    if len(sub_model_probs) < 2:
        return GateResult(
            gate=SelectionGate.PREDICTION_STABILITY,
            passed=True, value=0.0, threshold=threshold,
            reason="Insufficient models for stddev — passing by default",
        )

    mean_p = sum(sub_model_probs) / len(sub_model_probs)
    var = sum((p - mean_p) ** 2 for p in sub_model_probs) / len(sub_model_probs)
    stddev = math.sqrt(var)

    return GateResult(
        gate=SelectionGate.PREDICTION_STABILITY,
        passed=stddev <= threshold,
        value=round(stddev, 4),
        threshold=threshold,
        reason=(
            f"PredStdDev {stddev:.4f} "
            f"{'≤' if stddev <= threshold else '>'} {threshold}"
        ),
    )


def _check_regime_filter(regime_report: RegimeReport) -> GateResult:
    """Gate 4: Regime must not be SHARP_DOMINATED or BOOKMAKER_TRAP."""
    blocked = {MarketRegime.SHARP_DOMINATED, MarketRegime.BOOKMAKER_TRAP}
    is_blocked = regime_report.regime in blocked

    return GateResult(
        gate=SelectionGate.REGIME_FILTER,
        passed=not is_blocked,
        value=regime_report.confidence,
        threshold=0.0,
        reason=(
            f"Regime={regime_report.regime.value} "
            f"({'BLOCKED' if is_blocked else 'OK'})"
        ),
    )


def _check_odds_band_roi(odds: float, band_roi_lookup: dict) -> GateResult:
    """Gate 5: Historical ROI for this odds band must be positive."""
    threshold = GATE_THRESHOLDS["min_odds_band_roi"]

    band_roi = _lookup_odds_band_roi(odds, band_roi_lookup)

    return GateResult(
        gate=SelectionGate.ODDS_BAND_ROI,
        passed=band_roi > threshold,
        value=round(band_roi, 4),
        threshold=threshold,
        reason=f"Odds band ROI {band_roi:.2%} for odds={odds:.2f}",
    )


def _check_viable_edge(
    edge_pct: float,
    regime_multiplier: float,
) -> GateResult:
    """Gate 6: Edge after regime adjustment must exceed minimum."""
    threshold = GATE_THRESHOLDS["min_viable_edge"]
    adjusted = edge_pct * regime_multiplier
    return GateResult(
        gate=SelectionGate.VIABLE_EDGE,
        passed=adjusted >= threshold,
        value=round(adjusted, 4),
        threshold=threshold,
        reason=(
            f"AdjEdge={adjusted:.2%} "
            f"(raw={edge_pct:.2%} × regime_mult={regime_multiplier:.1f})"
        ),
    )


def _check_daily_limit(current_daily: int) -> GateResult:
    """Gate 7: Don't exceed max daily bets."""
    limit = GATE_THRESHOLDS["max_daily_bets"]
    return GateResult(
        gate=SelectionGate.DAILY_LIMIT,
        passed=current_daily < limit,
        value=current_daily,
        threshold=limit,
        reason=f"Daily bets {current_daily} < {limit}",
    )


# ─── Helpers ────────────────────────────────────────────────────────────────

def _lookup_odds_band_roi(odds: float, lookup: dict) -> float:
    """Look up historical ROI for an odds band."""
    # Bands from backtest data
    bands = [
        (1.01, 1.50, lookup.get("1.01-1.50", -0.05)),
        (1.51, 1.80, lookup.get("1.51-1.80", -0.03)),
        (1.81, 2.10, lookup.get("1.81-2.10", 0.0254)),
        (2.11, 2.60, lookup.get("2.11-2.60", 0.0151)),
        (2.61, 3.50, lookup.get("2.61-3.50", -0.04)),
        (3.51, 10.0, lookup.get("3.51+", -0.08)),
    ]
    for lo, hi, roi in bands:
        if lo <= odds <= hi:
            return roi
    return -0.10  # unknown band → negative


def _compute_priority_score(candidate: BetCandidate) -> float:
    """
    Rank candidates by a composite priority:
      40% edge_score + 25% adjusted_edge + 20% model_consensus + 15% regime_conf
    """
    return (
        0.40 * (candidate.edge_score / 100.0)
        + 0.25 * min(1.0, candidate.adjusted_edge / 0.10)  # normalise 10% edge = 1.0
        + 0.20 * candidate.model_consensus
        + 0.15 * candidate.regime_confidence
    )


# ─── Main Selection Pipeline ───────────────────────────────────────────────

def evaluate_bet_candidate(
    match_id: str,
    match_label: str,
    bet_type: str,
    side: str,
    odds: float,
    model_prob: float,
    calibrated_prob: float,
    sub_model_probs: list[float],
    edge_report: EdgeReport,
    regime_report: RegimeReport,
    daily_bet_count: int = 0,
    band_roi_lookup: dict | None = None,
) -> BetCandidate:
    """
    Evaluate a single bet through all 7 gates.
    Returns a BetCandidate with full gate audit trail.
    """
    if band_roi_lookup is None:
        band_roi_lookup = {}

    implied_prob = 1.0 / odds if odds > 1.0 else 0.99
    edge_pct = calibrated_prob - implied_prob
    regime_mult = regime_report.edge_multiplier

    candidate = BetCandidate(
        match_id=match_id,
        match_label=match_label,
        bet_type=bet_type,
        side=side,
        odds=odds,
        implied_prob=round(implied_prob, 4),
        model_prob=model_prob,
        calibrated_prob=calibrated_prob,
        edge_pct=round(edge_pct, 4),
        adjusted_edge=round(edge_pct * regime_mult, 4),
        edge_score=edge_report.edge_score,
        model_consensus=0.0,
        pred_stddev=0.0,
        regime=regime_report.regime.value,
        regime_confidence=regime_report.confidence,
    )

    # --- Run all gates ---
    gates = []

    # Gate 1: Edge score
    gates.append(_check_edge_score(edge_report))

    # Gate 2: Model consensus
    g2 = _check_model_consensus(sub_model_probs, calibrated_prob)
    candidate.model_consensus = g2.value
    gates.append(g2)

    # Gate 3: Prediction stability
    g3 = _check_prediction_stability(sub_model_probs)
    candidate.pred_stddev = g3.value
    gates.append(g3)

    # Gate 4: Regime filter
    gates.append(_check_regime_filter(regime_report))

    # Gate 5: Odds band ROI
    gates.append(_check_odds_band_roi(odds, band_roi_lookup))

    # Gate 6: Viable edge
    gates.append(_check_viable_edge(edge_pct, regime_mult))

    # Gate 7: Daily limit
    gates.append(_check_daily_limit(daily_bet_count))

    candidate.gates_passed = gates
    candidate.all_passed = all(g.passed for g in gates)

    # Tier and priority
    if candidate.all_passed:
        candidate.priority_score = _compute_priority_score(candidate)
        if candidate.edge_score >= 90:
            candidate.confidence_tier = "ELITE"
        elif candidate.edge_score >= 80:
            candidate.confidence_tier = "STRONG"
        elif candidate.edge_score >= 70:
            candidate.confidence_tier = "MODERATE"
        else:
            candidate.confidence_tier = "WEAK"

    # Build reasoning
    failed = [g for g in gates if not g.passed]
    if failed:
        reasons = "; ".join(g.reason for g in failed)
        candidate.reasoning = f"REJECTED — failed gates: {reasons}"
    else:
        candidate.reasoning = (
            f"SELECTED — tier={candidate.confidence_tier}, "
            f"priority={candidate.priority_score:.3f}, "
            f"adjEdge={candidate.adjusted_edge:.2%}"
        )

    return candidate


def select_bets(
    candidates: list[BetCandidate],
    max_per_match: int = 2,
) -> SelectionResult:
    """
    From a list of evaluated candidates, select the best bets.
    - Filters out candidates that failed any gate
    - Ranks by priority_score
    - Limits per-match selection
    """
    passed = [c for c in candidates if c.all_passed]
    rejected = [c for c in candidates if not c.all_passed]

    # Sort by priority descending
    passed.sort(key=lambda c: -c.priority_score)

    # Limit per match
    selected_per_match: dict[str, int] = {}
    selected = []
    for c in passed:
        count = selected_per_match.get(c.match_id, 0)
        if count < max_per_match:
            selected.append(c)
            selected_per_match[c.match_id] = count + 1
        else:
            c.reasoning += f" (exceeded per-match limit {max_per_match})"
            rejected.append(c)

    return SelectionResult(
        match_id=candidates[0].match_id if candidates else "",
        candidates_evaluated=len(candidates),
        candidates_selected=len(selected),
        selected=selected,
        rejected=rejected,
        summary=(
            f"Evaluated {len(candidates)}, "
            f"selected {len(selected)}, "
            f"rejected {len(rejected)}"
        ),
    )
