"""
wbc_backend/recommendation/p21_multi_day_backfill_contract.py

P21 Multi-Day PAPER Backfill Orchestrator — frozen contract definitions.

PAPER_ONLY — no production systems, no real bets.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# Gate decision constants
# ---------------------------------------------------------------------------

P21_MULTI_DAY_PAPER_BACKFILL_READY = "P21_MULTI_DAY_PAPER_BACKFILL_READY"
P21_BLOCKED_NO_READY_DAILY_RUNS = "P21_BLOCKED_NO_READY_DAILY_RUNS"
P21_BLOCKED_MISSING_REQUIRED_ARTIFACTS = "P21_BLOCKED_MISSING_REQUIRED_ARTIFACTS"
P21_BLOCKED_DAILY_GATE_NOT_READY = "P21_BLOCKED_DAILY_GATE_NOT_READY"
P21_BLOCKED_CONTRACT_VIOLATION = "P21_BLOCKED_CONTRACT_VIOLATION"
P21_FAIL_INPUT_MISSING = "P21_FAIL_INPUT_MISSING"
P21_FAIL_NON_DETERMINISTIC = "P21_FAIL_NON_DETERMINISTIC"

# Expected upstream P20 gate value
EXPECTED_P20_DAILY_GATE = "P20_DAILY_PAPER_ORCHESTRATOR_READY"

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class P21BackfillDateResult:
    """Result for a single date in the backfill window."""

    run_date: str
    daily_gate: str  # One of P21_* decisions for this date
    p20_gate: str    # The raw gate from p20_gate_result.json

    # Row counts
    n_recommended_rows: int
    n_active_paper_entries: int
    n_settled_win: int
    n_settled_loss: int
    n_unsettled: int

    # PnL
    total_stake_units: float
    total_pnl_units: float
    roi_units: float
    hit_rate: float

    # Identity join
    game_id_coverage: float
    settlement_join_method: str

    # Artifact integrity
    artifact_manifest_sha256: str

    # Safety invariants
    paper_only: bool
    production_ready: bool


@dataclass(frozen=True)
class P21MissingArtifactReport:
    """Report for a date with missing or invalid artifacts."""

    run_date: str
    missing_files: tuple[str, ...] = field(default_factory=tuple)
    invalid_files: tuple[str, ...] = field(default_factory=tuple)
    error_message: str = ""


@dataclass(frozen=True)
class P21BackfillAggregateSummary:
    """Aggregated summary across all dates in the backfill window."""

    date_start: str
    date_end: str

    # Date coverage
    n_dates_requested: int
    n_dates_ready: int
    n_dates_missing: int
    n_dates_blocked: int

    # Aggregate counts
    total_active_entries: int
    total_settled_win: int
    total_settled_loss: int
    total_unsettled: int

    # Aggregate PnL (stake-weighted)
    total_stake_units: float
    total_pnl_units: float
    aggregate_roi_units: float
    aggregate_hit_rate: float

    # Coverage
    min_game_id_coverage: float
    all_join_methods: tuple[str, ...] = field(default_factory=tuple)

    # Safety invariants
    paper_only: bool = True
    production_ready: bool = False

    # Gate decision for the whole backfill
    p21_gate: str = P21_MULTI_DAY_PAPER_BACKFILL_READY


@dataclass(frozen=True)
class P21BackfillGateResult:
    """Gate output for the P21 backfill run."""

    p21_gate: str
    date_start: str
    date_end: str
    n_dates_requested: int
    n_dates_ready: int
    n_dates_missing: int
    n_dates_blocked: int
    total_active_entries: int
    total_settled_win: int
    total_settled_loss: int
    total_unsettled: int
    total_stake_units: float
    total_pnl_units: float
    aggregate_roi_units: float
    aggregate_hit_rate: float
    min_game_id_coverage: float
    paper_only: bool = True
    production_ready: bool = False
    script_version: str = "P21_MULTI_DAY_PAPER_BACKFILL_V1"
    generated_at: Optional[str] = None
