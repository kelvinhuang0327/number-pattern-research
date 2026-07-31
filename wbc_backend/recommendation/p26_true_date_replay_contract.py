"""
wbc_backend/recommendation/p26_true_date_replay_contract.py

P26 True-Date Historical Backfill Replay Contract.

Defines the full type system for P26:
  - Per-date gate constants
  - Aggregate gate constants
  - Frozen dataclasses for replay tasks, results, summaries, gate decisions,
    and artifact manifests.

Design invariants (enforced in __post_init__):
  - paper_only must be True
  - production_ready must be False

PAPER_ONLY — no production systems, no real bets.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Tuple

# ---------------------------------------------------------------------------
# Per-date gate constants
# ---------------------------------------------------------------------------
P26_DATE_REPLAY_READY: str = "P26_DATE_REPLAY_READY"
P26_DATE_BLOCKED_NO_TRUE_DATE_SLICE: str = "P26_DATE_BLOCKED_NO_TRUE_DATE_SLICE"
P26_DATE_BLOCKED_INVALID_TRUE_DATE_SLICE: str = (
    "P26_DATE_BLOCKED_INVALID_TRUE_DATE_SLICE"
)
P26_DATE_BLOCKED_P15_INPUT_BUILD_FAILED: str = (
    "P26_DATE_BLOCKED_P15_INPUT_BUILD_FAILED"
)
P26_DATE_BLOCKED_REPLAY_FAILED: str = "P26_DATE_BLOCKED_REPLAY_FAILED"
P26_DATE_FAIL_CONTRACT_VIOLATION: str = "P26_DATE_FAIL_CONTRACT_VIOLATION"

_VALID_DATE_GATES: frozenset = frozenset(
    {
        P26_DATE_REPLAY_READY,
        P26_DATE_BLOCKED_NO_TRUE_DATE_SLICE,
        P26_DATE_BLOCKED_INVALID_TRUE_DATE_SLICE,
        P26_DATE_BLOCKED_P15_INPUT_BUILD_FAILED,
        P26_DATE_BLOCKED_REPLAY_FAILED,
        P26_DATE_FAIL_CONTRACT_VIOLATION,
    }
)

# ---------------------------------------------------------------------------
# Aggregate gate constants
# ---------------------------------------------------------------------------
P26_TRUE_DATE_HISTORICAL_BACKFILL_READY: str = (
    "P26_TRUE_DATE_HISTORICAL_BACKFILL_READY"
)
P26_BLOCKED_NO_READY_DATES: str = "P26_BLOCKED_NO_READY_DATES"
P26_BLOCKED_ALL_DATES_FAILED: str = "P26_BLOCKED_ALL_DATES_FAILED"
P26_BLOCKED_CONTRACT_VIOLATION: str = "P26_BLOCKED_CONTRACT_VIOLATION"
P26_FAIL_INPUT_MISSING: str = "P26_FAIL_INPUT_MISSING"
P26_FAIL_NON_DETERMINISTIC: str = "P26_FAIL_NON_DETERMINISTIC"

_VALID_AGGREGATE_GATES: frozenset = frozenset(
    {
        P26_TRUE_DATE_HISTORICAL_BACKFILL_READY,
        P26_BLOCKED_NO_READY_DATES,
        P26_BLOCKED_ALL_DATES_FAILED,
        P26_BLOCKED_CONTRACT_VIOLATION,
        P26_FAIL_INPUT_MISSING,
        P26_FAIL_NON_DETERMINISTIC,
    }
)


# ---------------------------------------------------------------------------
# Frozen dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class P26TrueDateReplayTask:
    """Input task for a single run_date replay."""

    run_date: str
    p25_slice_path: str  # path to p15_true_date_input.csv for this date
    output_dir: str
    paper_only: bool
    production_ready: bool

    def __post_init__(self) -> None:
        if not self.paper_only:
            raise ValueError(
                "P26TrueDateReplayTask: paper_only must be True — "
                "P26 is PAPER_ONLY research."
            )
        if self.production_ready:
            raise ValueError(
                "P26TrueDateReplayTask: production_ready must be False — "
                "P26 is not production-ready."
            )


@dataclass(frozen=True)
class P26TrueDateReplayResult:
    """Result for a single run_date replay."""

    run_date: str
    true_game_date: str
    true_date_slice_status: str
    n_slice_rows: int
    n_unique_game_ids: int
    date_matches_slice: bool
    replay_gate: str
    n_active_paper_entries: int
    n_settled_win: int
    n_settled_loss: int
    n_unsettled: int
    total_stake_units: float
    total_pnl_units: float
    roi_units: float
    hit_rate: float
    game_id_coverage: float
    paper_only: bool
    production_ready: bool
    blocker_reason: str

    def __post_init__(self) -> None:
        if not self.paper_only:
            raise ValueError(
                "P26TrueDateReplayResult: paper_only must be True."
            )
        if self.production_ready:
            raise ValueError(
                "P26TrueDateReplayResult: production_ready must be False."
            )
        if self.replay_gate not in _VALID_DATE_GATES:
            raise ValueError(
                f"P26TrueDateReplayResult: invalid replay_gate "
                f"'{self.replay_gate}'. Must be one of {_VALID_DATE_GATES}."
            )


@dataclass(frozen=True)
class P26TrueDateReplaySummary:
    """Aggregate summary across all replayed dates."""

    date_start: str
    date_end: str
    n_dates_requested: int
    n_dates_ready: int
    n_dates_blocked: int
    n_dates_failed: int
    total_active_entries: int
    total_settled_win: int
    total_settled_loss: int
    total_unsettled: int
    total_stake_units: float
    total_pnl_units: float
    aggregate_roi_units: float
    aggregate_hit_rate: float
    blocked_date_list: Tuple[str, ...]
    source_p25_dir: str
    paper_only: bool
    production_ready: bool

    def __post_init__(self) -> None:
        if not self.paper_only:
            raise ValueError(
                "P26TrueDateReplaySummary: paper_only must be True."
            )
        if self.production_ready:
            raise ValueError(
                "P26TrueDateReplaySummary: production_ready must be False."
            )


@dataclass(frozen=True)
class P26TrueDateReplayGateResult:
    """Overall P26 gate result for the full run."""

    p26_gate: str
    date_start: str
    date_end: str
    n_dates_requested: int
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
    blocker_reason: str
    paper_only: bool
    production_ready: bool
    generated_at: str

    def __post_init__(self) -> None:
        if not self.paper_only:
            raise ValueError(
                "P26TrueDateReplayGateResult: paper_only must be True."
            )
        if self.production_ready:
            raise ValueError(
                "P26TrueDateReplayGateResult: production_ready must be False."
            )
        if self.p26_gate not in _VALID_AGGREGATE_GATES:
            raise ValueError(
                f"P26TrueDateReplayGateResult: invalid p26_gate "
                f"'{self.p26_gate}'. Must be one of {_VALID_AGGREGATE_GATES}."
            )


@dataclass(frozen=True)
class P26TrueDateReplayManifest:
    """Artifact manifest for the P26 run output directory."""

    output_dir: str
    date_start: str
    date_end: str
    written_dates: Tuple[str, ...]
    skipped_dates: Tuple[str, ...]
    total_rows_written: int
    total_active_entries_written: int
    paper_only: bool
    production_ready: bool
    generated_at: str

    def __post_init__(self) -> None:
        if not self.paper_only:
            raise ValueError(
                "P26TrueDateReplayManifest: paper_only must be True."
            )
        if self.production_ready:
            raise ValueError(
                "P26TrueDateReplayManifest: production_ready must be False."
            )
