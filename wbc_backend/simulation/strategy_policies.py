"""
wbc_backend/simulation/strategy_policies.py

P14: Deterministic staking policy functions for strategy simulation.

Each policy takes a row dict with (at minimum):
    p_model   : float   – model probability for home win
    p_market  : float | None – no-vig market probability (may be absent)
    odds_decimal: float | None – decimal odds (may be absent)

Returns a PolicyDecision with:
    should_bet     : bool
    stake_fraction : float (0.0 if no bet)
    reason         : str (see REASON_CODES below)
    policy_name    : str

Reason codes
------------
POLICY_SELECTED          – bet accepted, stake_fraction > 0
BELOW_EDGE_THRESHOLD     – model edge < configured threshold
MARKET_ODDS_ABSENT       – decimal odds required but absent
PAPER_ONLY_REQUIRED      – reserved (paper_only block)
INVALID_PROBABILITY      – p_model is not in (0, 1)
CONTROL_NO_BET           – no_bet policy, always skip

Hard invariants
---------------
- paper_only=True must be passed for all policies (except no_bet_policy).
- Negative stake_fraction is never returned.
- Non-finite probabilities are rejected before any bet decision.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

# ── Reason codes ──────────────────────────────────────────────────────────────

REASON_CODES: frozenset[str] = frozenset({
    "POLICY_SELECTED",
    "BELOW_EDGE_THRESHOLD",
    "MARKET_ODDS_ABSENT",
    "PAPER_ONLY_REQUIRED",
    "INVALID_PROBABILITY",
    "CONTROL_NO_BET",
})

_DEFAULT_FLAT_STAKE = 0.02          # 2 % of bankroll per bet
_DEFAULT_CONFIDENCE_THRESHOLD = 0.55
_DEFAULT_EDGE_THRESHOLD = 0.0
_KELLY_CAP = 0.05                   # 5 % max fraction


@dataclass(frozen=True)
class PolicyDecision:
    """Typed result of a single staking policy evaluation."""

    should_bet: bool
    stake_fraction: float
    reason: str
    policy_name: str

    def __post_init__(self) -> None:
        if self.reason not in REASON_CODES:
            raise ValueError(
                f"PolicyDecision.reason '{self.reason}' not in REASON_CODES: "
                f"{sorted(REASON_CODES)}"
            )
        if self.stake_fraction < 0.0:
            raise ValueError(
                f"stake_fraction must be >= 0.0, got {self.stake_fraction}"
            )
        if self.should_bet and self.stake_fraction == 0.0:
            raise ValueError(
                "should_bet=True requires stake_fraction > 0.0"
            )


# ── Internal helpers ──────────────────────────────────────────────────────────

def _validate_p_model(p_model: Any) -> float | None:
    """Return float if valid probability, else None."""
    try:
        v = float(p_model)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(v) or v <= 0.0 or v >= 1.0:
        return None
    return v


# ── Public policy functions ───────────────────────────────────────────────────

def flat_stake_policy(
    row: dict[str, Any],
    *,
    threshold: float = _DEFAULT_CONFIDENCE_THRESHOLD,
    stake_fraction: float = _DEFAULT_FLAT_STAKE,
    paper_only: bool = True,
) -> PolicyDecision:
    """
    Bet a fixed stake fraction whenever p_model > threshold.

    Does NOT require market odds — works on model probability alone.
    ROI computation in the ledger will be None if decimal odds are absent.

    Parameters
    ----------
    row : dict
        Must contain ``p_model``.
    threshold : float
        Minimum model probability to place a bet.
    stake_fraction : float
        Fixed fraction of bankroll per bet.
    paper_only : bool
        Must remain True.
    """
    if not paper_only:
        return PolicyDecision(
            should_bet=False,
            stake_fraction=0.0,
            reason="PAPER_ONLY_REQUIRED",
            policy_name="flat_stake",
        )

    p = _validate_p_model(row.get("p_model"))
    if p is None:
        return PolicyDecision(
            should_bet=False,
            stake_fraction=0.0,
            reason="INVALID_PROBABILITY",
            policy_name="flat_stake",
        )

    if p > threshold:
        return PolicyDecision(
            should_bet=True,
            stake_fraction=stake_fraction,
            reason="POLICY_SELECTED",
            policy_name="flat_stake",
        )

    return PolicyDecision(
        should_bet=False,
        stake_fraction=0.0,
        reason="BELOW_EDGE_THRESHOLD",
        policy_name="flat_stake",
    )


def capped_kelly_policy(
    row: dict[str, Any],
    *,
    edge_threshold: float = _DEFAULT_EDGE_THRESHOLD,
    kelly_cap: float = _KELLY_CAP,
    paper_only: bool = True,
) -> PolicyDecision:
    """
    Kelly criterion staking, capped at ``kelly_cap``.

    Requires decimal_odds and p_market to compute edge.
    Returns MARKET_ODDS_ABSENT if odds are not available.

    Parameters
    ----------
    row : dict
        Must contain ``p_model``, ``decimal_odds``, ``p_market``.
    edge_threshold : float
        Minimum edge (p_model - p_market) to place a bet.
    kelly_cap : float
        Maximum Kelly fraction (default 0.05).
    paper_only : bool
        Must remain True.
    """
    if not paper_only:
        return PolicyDecision(
            should_bet=False,
            stake_fraction=0.0,
            reason="PAPER_ONLY_REQUIRED",
            policy_name="capped_kelly",
        )

    p = _validate_p_model(row.get("p_model"))
    if p is None:
        return PolicyDecision(
            should_bet=False,
            stake_fraction=0.0,
            reason="INVALID_PROBABILITY",
            policy_name="capped_kelly",
        )

    # Requires market odds
    decimal_odds_raw = row.get("decimal_odds")
    p_market_raw = row.get("p_market")
    if decimal_odds_raw is None or p_market_raw is None:
        return PolicyDecision(
            should_bet=False,
            stake_fraction=0.0,
            reason="MARKET_ODDS_ABSENT",
            policy_name="capped_kelly",
        )

    try:
        decimal_odds = float(decimal_odds_raw)
        p_market = float(p_market_raw)
    except (TypeError, ValueError):
        return PolicyDecision(
            should_bet=False,
            stake_fraction=0.0,
            reason="MARKET_ODDS_ABSENT",
            policy_name="capped_kelly",
        )

    if not math.isfinite(decimal_odds) or decimal_odds <= 1.0:
        return PolicyDecision(
            should_bet=False,
            stake_fraction=0.0,
            reason="MARKET_ODDS_ABSENT",
            policy_name="capped_kelly",
        )

    edge = p - p_market
    if edge <= edge_threshold:
        return PolicyDecision(
            should_bet=False,
            stake_fraction=0.0,
            reason="BELOW_EDGE_THRESHOLD",
            policy_name="capped_kelly",
        )

    b = decimal_odds - 1.0
    kelly = edge / b if b > 0 else 0.0
    fraction = max(0.0, min(kelly_cap, kelly))

    if fraction <= 0.0:
        return PolicyDecision(
            should_bet=False,
            stake_fraction=0.0,
            reason="BELOW_EDGE_THRESHOLD",
            policy_name="capped_kelly",
        )

    return PolicyDecision(
        should_bet=True,
        stake_fraction=fraction,
        reason="POLICY_SELECTED",
        policy_name="capped_kelly",
    )


def confidence_rank_policy(
    row: dict[str, Any],
    *,
    top_n_pct: float = 0.30,
    stake_fraction: float = _DEFAULT_FLAT_STAKE,
    rank: int | None = None,
    n_total: int | None = None,
    paper_only: bool = True,
) -> PolicyDecision:
    """
    Bet the top ``top_n_pct`` of rows sorted by p_model descending.

    Requires pre-computed ``rank`` (1-based) and ``n_total`` to be injected
    into the row dict OR passed as explicit arguments.
    Falls back to flat_stake_policy if rank is unavailable.

    Parameters
    ----------
    row : dict
        Must contain ``p_model`` and optionally ``confidence_rank`` (1-based).
    top_n_pct : float
        Fraction of highest-confidence rows to bet (default 0.30 = top 30 %).
    stake_fraction : float
        Fixed fraction of bankroll per selected bet.
    rank : int | None
        Pre-computed rank override (1-based, lowest = highest confidence).
    n_total : int | None
        Total sample size override.
    paper_only : bool
        Must remain True.
    """
    if not paper_only:
        return PolicyDecision(
            should_bet=False,
            stake_fraction=0.0,
            reason="PAPER_ONLY_REQUIRED",
            policy_name="confidence_rank",
        )

    p = _validate_p_model(row.get("p_model"))
    if p is None:
        return PolicyDecision(
            should_bet=False,
            stake_fraction=0.0,
            reason="INVALID_PROBABILITY",
            policy_name="confidence_rank",
        )

    _rank = rank if rank is not None else row.get("confidence_rank")
    _n = n_total if n_total is not None else row.get("n_total")

    # If rank metadata is missing, fall back to threshold 0.55
    if _rank is None or _n is None:
        cutoff = 0.55
        if p > cutoff:
            return PolicyDecision(
                should_bet=True,
                stake_fraction=stake_fraction,
                reason="POLICY_SELECTED",
                policy_name="confidence_rank",
            )
        return PolicyDecision(
            should_bet=False,
            stake_fraction=0.0,
            reason="BELOW_EDGE_THRESHOLD",
            policy_name="confidence_rank",
        )

    top_cutoff = int(math.ceil(float(_n) * top_n_pct))
    if int(_rank) <= top_cutoff:
        return PolicyDecision(
            should_bet=True,
            stake_fraction=stake_fraction,
            reason="POLICY_SELECTED",
            policy_name="confidence_rank",
        )

    return PolicyDecision(
        should_bet=False,
        stake_fraction=0.0,
        reason="BELOW_EDGE_THRESHOLD",
        policy_name="confidence_rank",
    )


def no_bet_policy(
    row: dict[str, Any],
    **_kwargs: Any,
) -> PolicyDecision:
    """
    Control policy: never bet.

    Used as a zero-activity baseline. Always returns CONTROL_NO_BET.
    Does NOT enforce paper_only because it never acts.
    """
    _ = row  # unused, intentional
    return PolicyDecision(
        should_bet=False,
        stake_fraction=0.0,
        reason="CONTROL_NO_BET",
        policy_name="no_bet",
    )
