"""
wbc_backend/recommendation/p16_recommendation_gate.py

P16 Recommendation Gate — CEO-revised scope.

Applies per-row gate logic that integrates:
  - Paper-only invariants
  - BSS positivity check
  - Odds join status filter
  - Probability / odds validity
  - Edge threshold from sweep (NOT hardcoded)
  - Drawdown ceiling (max_drawdown_pct > 25 → block)
  - Sharpe floor (sharpe < 0.0 → block)
  - Sweep insufficient-samples guard

PAPER_ONLY: Paper simulation only. No production bets.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from wbc_backend.recommendation.p16_recommendation_input_adapter import P16InputRow
from wbc_backend.simulation.strategy_risk_metrics import StrategyRiskProfile

# ── Reason codes ──────────────────────────────────────────────────────────────

ELIGIBLE = "P16_ELIGIBLE_PAPER_RECOMMENDATION"
BLOCKED_NOT_PAPER_ONLY = "P16_BLOCKED_NOT_PAPER_ONLY"
BLOCKED_PRODUCTION = "P16_BLOCKED_PRODUCTION_NOT_ALLOWED"
BLOCKED_NEGATIVE_BSS = "P16_BLOCKED_NEGATIVE_OR_ZERO_BSS"
BLOCKED_ODDS_NOT_JOINED = "P16_BLOCKED_ODDS_NOT_JOINED"
BLOCKED_INVALID_PROB = "P16_BLOCKED_INVALID_PROBABILITY"
BLOCKED_INVALID_ODDS = "P16_BLOCKED_INVALID_ODDS"
BLOCKED_EDGE_BELOW = "P16_BLOCKED_EDGE_BELOW_THRESHOLD"
BLOCKED_INVALID_STAKE = "P16_BLOCKED_INVALID_STAKE"
BLOCKED_SWEEP_INSUFFICIENT = "P16_BLOCKED_SWEEP_INSUFFICIENT_SAMPLES"
BLOCKED_DRAWDOWN = "P16_BLOCKED_DRAWDOWN_EXCEEDS_LIMIT"
BLOCKED_SHARPE = "P16_BLOCKED_SHARPE_BELOW_FLOOR"
BLOCKED_UNKNOWN = "P16_BLOCKED_UNKNOWN"

# ── P16.6 reason codes (P18-policy gate re-run) ───────────────────────────────

P16_6_ELIGIBLE = "P16_6_ELIGIBLE_PAPER_RECOMMENDATION"
P16_6_BLOCKED_INVALID_P18_POLICY = "P16_6_BLOCKED_INVALID_P18_POLICY"
P16_6_BLOCKED_ODDS_ABOVE_POLICY_MAX = "P16_6_BLOCKED_ODDS_ABOVE_POLICY_MAX"
P16_6_BLOCKED_EDGE_BELOW_P18 = "P16_6_BLOCKED_EDGE_BELOW_P18_THRESHOLD"
P16_6_BLOCKED_POLICY_RISK_INVALID = "P16_6_BLOCKED_POLICY_RISK_PROFILE_INVALID"
P16_6_BLOCKED_PRODUCTION = "P16_6_BLOCKED_PRODUCTION_NOT_ALLOWED"
P16_6_BLOCKED_NOT_PAPER_ONLY = "P16_6_BLOCKED_NOT_PAPER_ONLY"
P16_6_BLOCKED_INVALID_STAKE = "P16_6_BLOCKED_INVALID_STAKE"
P16_6_BLOCKED_UNKNOWN = "P16_6_BLOCKED_UNKNOWN"

# ── Gate result ───────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class GateResult:
    decision: str  # ELIGIBLE | BLOCKED_*
    reason_code: str
    passed: bool


# ── Gate logic ────────────────────────────────────────────────────────────────

def _is_valid_probability(p: float | None) -> bool:
    return p is not None and math.isfinite(p) and 0.0 < p < 1.0


def _is_valid_odds(o: float | None) -> bool:
    return o is not None and math.isfinite(o) and o > 1.0


def apply_gate(
    row: P16InputRow,
    selected_edge_threshold: float,
    risk_profile: StrategyRiskProfile,
    sweep_status: str,
    max_drawdown_limit: float = 0.25,
    sharpe_floor: float = 0.0,
) -> GateResult:
    """
    Apply P16 gate to a single input row.

    Parameters
    ----------
    row : P16InputRow
        Adapted input row from P15.
    selected_edge_threshold : float
        Threshold selected by edge sweep (NOT hardcoded).
    risk_profile : StrategyRiskProfile
        Strategy risk profile from sweep.
    sweep_status : str
        "SWEEP_OK" or "SWEEP_INSUFFICIENT_SAMPLES".
    max_drawdown_limit : float
        Maximum allowed drawdown fraction (0.0-1.0). Default 0.25 (25%).
    sharpe_floor : float
        Minimum required Sharpe ratio. Default 0.0.

    Returns
    -------
    GateResult
    """
    # Guard: sweep insufficient samples — block all rows
    if sweep_status == "SWEEP_INSUFFICIENT_SAMPLES":
        return GateResult(
            decision=BLOCKED_SWEEP_INSUFFICIENT,
            reason_code=BLOCKED_SWEEP_INSUFFICIENT,
            passed=False,
        )

    # production_ready must be False
    if row.production_ready:
        return GateResult(
            decision=BLOCKED_PRODUCTION,
            reason_code=BLOCKED_PRODUCTION,
            passed=False,
        )

    # paper_only must be True
    if not row.paper_only:
        return GateResult(
            decision=BLOCKED_NOT_PAPER_ONLY,
            reason_code=BLOCKED_NOT_PAPER_ONLY,
            passed=False,
        )

    # BSS > 0
    if row.source_bss_oof <= 0.0:
        return GateResult(
            decision=BLOCKED_NEGATIVE_BSS,
            reason_code=BLOCKED_NEGATIVE_BSS,
            passed=False,
        )

    # odds_join_status == JOINED
    if row.odds_join_status != "JOINED":
        return GateResult(
            decision=BLOCKED_ODDS_NOT_JOINED,
            reason_code=BLOCKED_ODDS_NOT_JOINED,
            passed=False,
        )

    # Probability validity
    if not _is_valid_probability(row.p_model) or not _is_valid_probability(row.p_market):
        return GateResult(
            decision=BLOCKED_INVALID_PROB,
            reason_code=BLOCKED_INVALID_PROB,
            passed=False,
        )

    # Odds validity
    if not _is_valid_odds(row.odds_decimal):
        return GateResult(
            decision=BLOCKED_INVALID_ODDS,
            reason_code=BLOCKED_INVALID_ODDS,
            passed=False,
        )

    # Edge threshold (from sweep)
    edge = row.edge if row.edge is not None else (row.p_model - row.p_market)  # type: ignore[operator]
    if edge < selected_edge_threshold:
        return GateResult(
            decision=BLOCKED_EDGE_BELOW,
            reason_code=BLOCKED_EDGE_BELOW,
            passed=False,
        )

    # Drawdown ceiling
    if risk_profile.max_drawdown_pct > (max_drawdown_limit * 100.0):
        return GateResult(
            decision=BLOCKED_DRAWDOWN,
            reason_code=BLOCKED_DRAWDOWN,
            passed=False,
        )

    # Sharpe floor
    if risk_profile.sharpe_ratio < sharpe_floor:
        return GateResult(
            decision=BLOCKED_SHARPE,
            reason_code=BLOCKED_SHARPE,
            passed=False,
        )

    return GateResult(
        decision=ELIGIBLE,
        reason_code=ELIGIBLE,
        passed=True,
    )


def compute_paper_stake(
    row: P16InputRow,
    gate: GateResult,
    risk_profile: StrategyRiskProfile,
    max_stake_cap: float = 0.02,
) -> float:
    """
    Compute paper stake fraction.

    Gate fail → 0.0
    Gate pass → min(kelly_fraction, max_stake_cap)
    """
    if not gate.passed:
        return 0.0

    # Kelly fraction: (edge * (decimal_odds - 1) - (1 - edge)) / (decimal_odds - 1)
    # Simplified: f = edge / (decimal_odds - 1) where edge = p_model - p_market
    # Using full Kelly: f = (p * (odds-1) - (1-p)) / (odds-1) = p - (1-p)/(odds-1)
    edge = row.edge if row.edge is not None else (row.p_model - row.p_market)  # type: ignore[operator]
    odds = row.odds_decimal
    assert odds is not None  # validated in gate

    b = odds - 1.0  # net odds
    p = row.p_model
    assert p is not None  # validated in gate

    kelly = (p * b - (1.0 - p)) / b if b > 0.0 else 0.0
    kelly = max(0.0, kelly)

    return float(min(kelly, max_stake_cap))


# ── P16.6 gate functions (uses P18 selected policy) ───────────────────────────

def apply_gate_with_p18_policy(
    row: "P16InputRow",
    p18_policy: "P18SelectedPolicy",
) -> GateResult:
    """
    Apply P16.6 per-row gate using P18 selected policy parameters.

    Checks (in order):
      1. production_ready must be False
      2. paper_only must be True
      3. odds_join_status must be JOINED
      4. p_model and p_market must be valid probabilities
      5. odds_decimal must be valid (> 1.0)
      6. odds_decimal <= p18_policy.odds_decimal_max
      7. edge >= p18_policy.edge_threshold
      8. p18_policy risk: max_drawdown_pct <= 25.0
      9. p18_policy risk: sharpe_ratio >= 0.0
    """
    # production_ready must be False
    if row.production_ready:
        return GateResult(
            decision=P16_6_BLOCKED_PRODUCTION,
            reason_code=P16_6_BLOCKED_PRODUCTION,
            passed=False,
        )

    # paper_only must be True
    if not row.paper_only:
        return GateResult(
            decision=P16_6_BLOCKED_NOT_PAPER_ONLY,
            reason_code=P16_6_BLOCKED_NOT_PAPER_ONLY,
            passed=False,
        )

    # odds_join_status == JOINED
    if row.odds_join_status != "JOINED":
        return GateResult(
            decision=P16_6_BLOCKED_UNKNOWN,
            reason_code=P16_6_BLOCKED_UNKNOWN,
            passed=False,
        )

    # Probability validity
    if not _is_valid_probability(row.p_model) or not _is_valid_probability(row.p_market):
        return GateResult(
            decision=P16_6_BLOCKED_UNKNOWN,
            reason_code=P16_6_BLOCKED_UNKNOWN,
            passed=False,
        )

    # Odds validity
    if not _is_valid_odds(row.odds_decimal):
        return GateResult(
            decision=P16_6_BLOCKED_UNKNOWN,
            reason_code=P16_6_BLOCKED_UNKNOWN,
            passed=False,
        )

    # Odds cap from P18 policy
    assert row.odds_decimal is not None  # validated above
    if row.odds_decimal > p18_policy.odds_decimal_max:
        return GateResult(
            decision=P16_6_BLOCKED_ODDS_ABOVE_POLICY_MAX,
            reason_code=P16_6_BLOCKED_ODDS_ABOVE_POLICY_MAX,
            passed=False,
        )

    # Edge threshold from P18 policy
    edge = row.edge if row.edge is not None else (row.p_model - row.p_market)  # type: ignore[operator]
    if edge < p18_policy.edge_threshold:
        return GateResult(
            decision=P16_6_BLOCKED_EDGE_BELOW_P18,
            reason_code=P16_6_BLOCKED_EDGE_BELOW_P18,
            passed=False,
        )

    # P18 risk profile checks
    if p18_policy.max_drawdown_pct > 25.0:
        return GateResult(
            decision=P16_6_BLOCKED_POLICY_RISK_INVALID,
            reason_code=P16_6_BLOCKED_POLICY_RISK_INVALID,
            passed=False,
        )
    if p18_policy.sharpe_ratio < 0.0:
        return GateResult(
            decision=P16_6_BLOCKED_POLICY_RISK_INVALID,
            reason_code=P16_6_BLOCKED_POLICY_RISK_INVALID,
            passed=False,
        )

    return GateResult(
        decision=P16_6_ELIGIBLE,
        reason_code=P16_6_ELIGIBLE,
        passed=True,
    )


def compute_paper_stake_p18(
    row: "P16InputRow",
    gate: GateResult,
    p18_policy: "P18SelectedPolicy",
) -> float:
    """
    Compute paper stake using P18 policy parameters.

    Gate fail → 0.0
    Gate pass → min(full_kelly * kelly_fraction, max_stake_cap)
    """
    if not gate.passed:
        return 0.0

    p = row.p_model
    odds = row.odds_decimal
    assert p is not None and odds is not None  # validated in gate

    b = odds - 1.0
    full_kelly = (p * b - (1.0 - p)) / b if b > 0.0 else 0.0
    full_kelly = max(0.0, full_kelly)

    stake = full_kelly * p18_policy.kelly_fraction
    stake = min(stake, p18_policy.max_stake_cap)
    return float(stake)


# ── Type stubs (avoid circular imports) ──────────────────────────────────────
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from wbc_backend.recommendation.p16_p18_policy_loader import P18SelectedPolicy
