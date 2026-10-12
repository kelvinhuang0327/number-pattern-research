"""
wbc_backend/recommendation/p27_full_true_date_backfill_contract.py

P27 Full 2025 True-Date Backfill Expansion — type definitions and gate constants.

All dataclasses are frozen and enforce paper_only=True, production_ready=False
in __post_init__. Any violation raises ValueError immediately.

Gate constants follow the naming pattern P27_<OUTCOME>_<REASON>.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Tuple

# ---------------------------------------------------------------------------
# Aggregate gate constants
# ---------------------------------------------------------------------------
P27_FULL_TRUE_DATE_BACKFILL_READY = "P27_FULL_TRUE_DATE_BACKFILL_READY"
P27_BLOCKED_P25_FULL_RANGE_NOT_READY = "P27_BLOCKED_P25_FULL_RANGE_NOT_READY"
P27_BLOCKED_P26_REPLAY_FAILED = "P27_BLOCKED_P26_REPLAY_FAILED"
P27_BLOCKED_INSUFFICIENT_SAMPLE_SIZE = "P27_BLOCKED_INSUFFICIENT_SAMPLE_SIZE"
P27_BLOCKED_RUNTIME_GUARD = "P27_BLOCKED_RUNTIME_GUARD"
P27_BLOCKED_CONTRACT_VIOLATION = "P27_BLOCKED_CONTRACT_VIOLATION"
P27_FAIL_INPUT_MISSING = "P27_FAIL_INPUT_MISSING"
P27_FAIL_NON_DETERMINISTIC = "P27_FAIL_NON_DETERMINISTIC"

_VALID_AGGREGATE_GATES: frozenset = frozenset({
    P27_FULL_TRUE_DATE_BACKFILL_READY,
    P27_BLOCKED_P25_FULL_RANGE_NOT_READY,
    P27_BLOCKED_P26_REPLAY_FAILED,
    P27_BLOCKED_INSUFFICIENT_SAMPLE_SIZE,
    P27_BLOCKED_RUNTIME_GUARD,
    P27_BLOCKED_CONTRACT_VIOLATION,
    P27_FAIL_INPUT_MISSING,
    P27_FAIL_NON_DETERMINISTIC,
})

# Minimum sample size required for P27 to report READY (not a hard gate blocker)
MIN_SAMPLE_SIZE_ADVISORY: int = 1500


# ---------------------------------------------------------------------------
# Frozen dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class P27ExpansionSegment:
    """A 14-day (or shorter final) segment of the full backfill range."""
    segment_index: int
    date_start: str        # ISO YYYY-MM-DD
    date_end: str          # ISO YYYY-MM-DD
    date_count: int        # inclusive count
    p25_output_dir: str    # expected P25 output path for this segment's range
    p26_output_dir: str    # expected P26 output path for this segment's range

    def __post_init__(self) -> None:
        if self.date_count < 1:
            raise ValueError(f"P27ExpansionSegment: date_count must be >= 1, got {self.date_count}")
        if self.date_start > self.date_end:
            raise ValueError(
                f"P27ExpansionSegment: date_start {self.date_start} > date_end {self.date_end}"
            )


@dataclass(frozen=True)
class P27ExpansionDateResult:
    """Per-date result from the full-range expansion."""
    run_date: str
    segment_index: int
    replay_gate: str         # P26 per-date gate
    n_active_paper_entries: int
    n_settled_win: int
    n_settled_loss: int
    n_unsettled: int
    total_stake_units: float
    total_pnl_units: float
    hit_rate: float
    paper_only: bool
    production_ready: bool
    blocker_reason: str

    def __post_init__(self) -> None:
        if not self.paper_only:
            raise ValueError("P27ExpansionDateResult: paper_only must be True")
        if self.production_ready:
            raise ValueError("P27ExpansionDateResult: production_ready must be False")


@dataclass(frozen=True)
class P27FullBackfillSummary:
    """Full-range aggregate summary after all segments are complete."""
    date_start: str
    date_end: str
    n_segments: int
    n_dates_requested: int
    n_dates_ready: int
    n_dates_empty: int
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
    max_runtime_seconds: float
    blocked_segment_list: Tuple[str, ...]  # e.g. ("2025-06-01_2025-06-14", ...)
    blocked_date_list: Tuple[str, ...]
    source_p25_base_dir: str
    paper_only: bool
    production_ready: bool
    blocker_reason: str

    def __post_init__(self) -> None:
        if not self.paper_only:
            raise ValueError("P27FullBackfillSummary: paper_only must be True")
        if self.production_ready:
            raise ValueError("P27FullBackfillSummary: production_ready must be False")


@dataclass(frozen=True)
class P27FullBackfillGateResult:
    """Top-level gate result — all summary fields plus p27_gate."""
    p27_gate: str
    date_start: str
    date_end: str
    n_segments: int
    n_dates_requested: int
    n_dates_ready: int
    n_dates_empty: int
    n_dates_blocked: int
    total_active_entries: int
    total_settled_win: int
    total_settled_loss: int
    total_unsettled: int
    total_stake_units: float
    total_pnl_units: float
    aggregate_roi_units: float
    aggregate_hit_rate: float
    max_runtime_seconds: float
    paper_only: bool
    production_ready: bool
    blocker_reason: str
    generated_at: str

    def __post_init__(self) -> None:
        if not self.paper_only:
            raise ValueError("P27FullBackfillGateResult: paper_only must be True")
        if self.production_ready:
            raise ValueError("P27FullBackfillGateResult: production_ready must be False")
        if self.p27_gate not in _VALID_AGGREGATE_GATES:
            raise ValueError(
                f"P27FullBackfillGateResult: invalid p27_gate '{self.p27_gate}'. "
                f"Must be one of {sorted(_VALID_AGGREGATE_GATES)}"
            )


@dataclass(frozen=True)
class P27RuntimeGuardResult:
    """Runtime guard check — ensures max_runtime_seconds is not exceeded."""
    max_runtime_seconds: float
    actual_runtime_seconds: float
    guard_triggered: bool
    guard_reason: str
    paper_only: bool
    production_ready: bool

    def __post_init__(self) -> None:
        if not self.paper_only:
            raise ValueError("P27RuntimeGuardResult: paper_only must be True")
        if self.production_ready:
            raise ValueError("P27RuntimeGuardResult: production_ready must be False")
