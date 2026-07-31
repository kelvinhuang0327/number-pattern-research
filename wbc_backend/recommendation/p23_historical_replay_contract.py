"""
wbc_backend/recommendation/p23_historical_replay_contract.py

P23 Execute Replayable Historical Backfill — frozen dataclass contracts.

All dataclasses enforce paper_only=True and production_ready=False via
__post_init__ safety guards.

PAPER_ONLY — no production systems, no real bets.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Per-date gate decisions
# ---------------------------------------------------------------------------

P23_DATE_REPLAY_READY = "P23_DATE_REPLAY_READY"
P23_DATE_ALREADY_READY = "P23_DATE_ALREADY_READY"
P23_DATE_BLOCKED_SOURCE_NOT_READY = "P23_DATE_BLOCKED_SOURCE_NOT_READY"
P23_DATE_BLOCKED_P15_BUILD_FAILED = "P23_DATE_BLOCKED_P15_BUILD_FAILED"
P23_DATE_BLOCKED_P16_6_FAILED = "P23_DATE_BLOCKED_P16_6_FAILED"
P23_DATE_BLOCKED_P19_FAILED = "P23_DATE_BLOCKED_P19_FAILED"
P23_DATE_BLOCKED_P17_REPLAY_FAILED = "P23_DATE_BLOCKED_P17_REPLAY_FAILED"
P23_DATE_BLOCKED_P20_FAILED = "P23_DATE_BLOCKED_P20_FAILED"
P23_DATE_FAIL_CONTRACT_VIOLATION = "P23_DATE_FAIL_CONTRACT_VIOLATION"

# ---------------------------------------------------------------------------
# Aggregate gate decisions
# ---------------------------------------------------------------------------

P23_HISTORICAL_REPLAY_BACKFILL_READY = "P23_HISTORICAL_REPLAY_BACKFILL_READY"
P23_BLOCKED_NO_READY_DATES = "P23_BLOCKED_NO_READY_DATES"
P23_BLOCKED_ALL_DATES_FAILED = "P23_BLOCKED_ALL_DATES_FAILED"
P23_BLOCKED_CONTRACT_VIOLATION = "P23_BLOCKED_CONTRACT_VIOLATION"
P23_FAIL_INPUT_MISSING = "P23_FAIL_INPUT_MISSING"
P23_FAIL_NON_DETERMINISTIC = "P23_FAIL_NON_DETERMINISTIC"

# ---------------------------------------------------------------------------
# Replay source types
# ---------------------------------------------------------------------------

P23_SOURCE_TYPE_ALREADY_READY = "ALREADY_READY"
P23_SOURCE_TYPE_MATERIALIZED = "MATERIALIZED_FROM_P22_5"
P23_SOURCE_TYPE_PREVIEW_ONLY = "PREVIEW_ONLY"
P23_SOURCE_TYPE_BLOCKED = "BLOCKED"


# ---------------------------------------------------------------------------
# Frozen dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class P23ReplayDateTask:
    """Specification for a single date replay task."""

    run_date: str
    p22_5_source_ready: bool
    p22_5_preview_path: str = ""
    p22_5_full_source_path: str = ""
    source_type: str = P23_SOURCE_TYPE_BLOCKED
    paper_only: bool = True
    production_ready: bool = False

    def __post_init__(self) -> None:
        if not self.paper_only:
            raise ValueError("P23ReplayDateTask: paper_only must be True")
        if self.production_ready:
            raise ValueError("P23ReplayDateTask: production_ready must be False")


@dataclass(frozen=True)
class P23ReplayDateResult:
    """Result of a single date replay attempt."""

    run_date: str
    source_ready: bool
    p15_preview_ready: bool
    p16_6_gate: str
    p19_gate: str
    p17_replay_gate: str
    p20_gate: str
    date_gate: str
    n_recommended_rows: int
    n_active_paper_entries: int
    n_settled_win: int
    n_settled_loss: int
    n_unsettled: int
    total_stake_units: float
    total_pnl_units: float
    roi_units: float
    hit_rate: float
    game_id_coverage: float
    settlement_join_method: str
    blocker_reason: str = ""
    paper_only: bool = True
    production_ready: bool = False

    def __post_init__(self) -> None:
        if not self.paper_only:
            raise ValueError("P23ReplayDateResult: paper_only must be True")
        if self.production_ready:
            raise ValueError("P23ReplayDateResult: production_ready must be False")


@dataclass(frozen=True)
class P23ReplayAggregateSummary:
    """Aggregate summary across all replayed dates."""

    date_start: str
    date_end: str
    n_dates_requested: int
    n_dates_attempted: int
    n_dates_ready: int
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
    p23_gate: str
    paper_only: bool = True
    production_ready: bool = False

    def __post_init__(self) -> None:
        if not self.paper_only:
            raise ValueError("P23ReplayAggregateSummary: paper_only must be True")
        if self.production_ready:
            raise ValueError("P23ReplayAggregateSummary: production_ready must be False")


@dataclass(frozen=True)
class P23ReplayGateResult:
    """Top-level gate result for the P23 CLI."""

    p23_gate: str
    date_start: str
    date_end: str
    n_dates_requested: int
    n_dates_attempted: int
    n_dates_ready: int
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
    recommended_next_action: str
    paper_only: bool = True
    production_ready: bool = False
    generated_at: str = ""

    def __post_init__(self) -> None:
        if not self.paper_only:
            raise ValueError("P23ReplayGateResult: paper_only must be True")
        if self.production_ready:
            raise ValueError("P23ReplayGateResult: production_ready must be False")


@dataclass(frozen=True)
class P23ReplayArtifactManifest:
    """Manifest of all output artifacts generated by P23."""

    date_start: str
    date_end: str
    n_dates_in_manifest: int
    artifact_paths: tuple = field(default_factory=tuple)
    paper_only: bool = True
    production_ready: bool = False
    generated_at: str = ""

    def __post_init__(self) -> None:
        if not self.paper_only:
            raise ValueError("P23ReplayArtifactManifest: paper_only must be True")
        if self.production_ready:
            raise ValueError("P23ReplayArtifactManifest: production_ready must be False")
