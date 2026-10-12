"""
wbc_backend/recommendation/p17_paper_ledger_contract.py

P17 Paper Recommendation Ledger — frozen dataclass contracts.

Settlement status values:
  SETTLED_WIN                  — y_true matched the recommended side, pnl > 0
  SETTLED_LOSS                 — y_true did not match the recommended side, pnl < 0
  SETTLED_PUSH                 — push / draw (unused in this binary dataset)
  UNSETTLED_MISSING_OUTCOME    — y_true is missing (NaN) for this row
  UNSETTLED_INVALID_ODDS       — odds_decimal is invalid (<=1.0 or non-finite)
  UNSETTLED_INVALID_STAKE      — paper_stake_fraction is invalid (non-finite or <0)
  UNSETTLED_NOT_RECOMMENDED    — row was blocked at P16.6 gate (not eligible)

PAPER_ONLY — this module never touches production systems.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ── Settlement status constants ───────────────────────────────────────────────

SETTLED_WIN = "SETTLED_WIN"
SETTLED_LOSS = "SETTLED_LOSS"
SETTLED_PUSH = "SETTLED_PUSH"
UNSETTLED_MISSING_OUTCOME = "UNSETTLED_MISSING_OUTCOME"
UNSETTLED_INVALID_ODDS = "UNSETTLED_INVALID_ODDS"
UNSETTLED_INVALID_STAKE = "UNSETTLED_INVALID_STAKE"
UNSETTLED_NOT_RECOMMENDED = "UNSETTLED_NOT_RECOMMENDED"

ALL_SETTLEMENT_STATUSES = frozenset([
    SETTLED_WIN,
    SETTLED_LOSS,
    SETTLED_PUSH,
    UNSETTLED_MISSING_OUTCOME,
    UNSETTLED_INVALID_ODDS,
    UNSETTLED_INVALID_STAKE,
    UNSETTLED_NOT_RECOMMENDED,
])

# ── Gate decision constants ───────────────────────────────────────────────────

P17_PAPER_LEDGER_READY = "P17_PAPER_LEDGER_READY"
P17_BLOCKED_NO_ACTIVE_RECOMMENDATIONS = "P17_BLOCKED_NO_ACTIVE_RECOMMENDATIONS"
P17_BLOCKED_SETTLEMENT_JOIN_INCOMPLETE = "P17_BLOCKED_SETTLEMENT_JOIN_INCOMPLETE"
P17_BLOCKED_CONTRACT_VIOLATION = "P17_BLOCKED_CONTRACT_VIOLATION"
P17_FAIL_INPUT_MISSING = "P17_FAIL_INPUT_MISSING"
P17_FAIL_NON_DETERMINISTIC = "P17_FAIL_NON_DETERMINISTIC"

# ── Source / phase constants ──────────────────────────────────────────────────

SOURCE_PHASE = "P16_6"
CREATED_FROM = "P17_PAPER_RECOMMENDATION_LEDGER"
P16_6_ELIGIBLE_DECISION = "P16_6_ELIGIBLE_PAPER_RECOMMENDATION"


# ── Data contracts ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class PaperLedgerEntry:
    """One row in the P17 paper recommendation ledger."""

    # Identity
    ledger_id: str
    recommendation_id: str
    game_id: str
    date: str
    side: str

    # Prediction signals
    p_model: float
    p_market: float
    edge: float
    odds_decimal: float

    # Stake
    paper_stake_fraction: float
    paper_stake_units: float       # bankroll_units * paper_stake_fraction

    # Policy / gate provenance
    policy_id: str
    strategy_policy: str
    gate_decision: str
    gate_reason: str

    # Safety invariants
    paper_only: bool
    production_ready: bool

    # Phase provenance
    source_phase: str    # always "P16_6"
    created_from: str    # always "P17_PAPER_RECOMMENDATION_LEDGER"

    # Settlement fields — populated by settle_ledger_entries()
    y_true: Optional[float]         # 0.0, 1.0, or None
    settlement_status: str          # one of ALL_SETTLEMENT_STATUSES
    settlement_reason: str          # free-text explanation

    # P&L
    pnl_units: float                # 0.0 for unsettled
    roi: float                      # pnl_units / paper_stake_units, 0.0 if stake=0

    # Outcome flags
    is_win: bool
    is_loss: bool
    is_push: bool

    # Risk profile (from P18 policy)
    risk_profile_max_drawdown: float
    risk_profile_sharpe: float
    risk_profile_n_bets: int


@dataclass(frozen=True)
class PaperLedgerSummary:
    """Aggregate summary of the settled paper ledger."""

    p17_gate: str
    source_p16_6_gate: str

    n_recommendation_rows: int
    n_active_paper_entries: int

    n_settled_win: int
    n_settled_loss: int
    n_settled_push: int
    n_unsettled: int

    total_stake_units: float
    total_pnl_units: float
    roi_units: float        # total_pnl_units / total_stake_units (or 0.0 if stake=0)

    hit_rate: float         # n_settled_win / (n_settled_win + n_settled_loss)
    avg_edge: float
    avg_odds_decimal: float

    max_drawdown_pct: float
    sharpe_ratio: float

    settlement_join_coverage: float   # fraction of active entries that are settled
    duplicate_game_id_count: int
    unmatched_recommendation_count: int

    paper_only: bool
    production_ready: bool


@dataclass(frozen=True)
class SettlementJoinResult:
    """Result of joining recommendation rows to P15 ledger for settlement audit."""

    n_recommendations: int
    n_joined: int
    n_unmatched: int
    n_duplicate_game_ids: int
    join_coverage: float           # n_joined / n_recommendations
    join_method: str               # "game_id" or "position" or "none"
    join_quality: str              # "HIGH", "MEDIUM", "LOW", "NONE"
    risk_notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class P17LedgerGateResult:
    """Top-level gate result for the P17 ledger run."""

    gate_decision: str
    paper_only: bool
    production_ready: bool
    n_active_entries: int
    n_settled: int
    n_unsettled: int
    settlement_join_quality: str
    error_message: Optional[str] = None


@dataclass(frozen=True)
class ValidationResult:
    """Contract validation result."""

    valid: bool
    error_code: Optional[str]
    error_message: Optional[str]
