"""
wbc_backend/recommendation/p25_true_date_source_contract.py

P25 True-Date Source Separation Contract — defines the type system for the
true multi-date artifact builder that resolves the P24 duplicate-source blocker.

Design principles:
- Frozen dataclasses prevent mutation after construction.
- paper_only=True, production_ready=False are enforced by __post_init__.
- All gate and status constants are plain module-level strings.
- No external dependencies beyond Python stdlib dataclasses / typing.

PAPER_ONLY — no production systems, no real bets.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

# ---------------------------------------------------------------------------
# Gate decisions
# ---------------------------------------------------------------------------
P25_TRUE_DATE_SOURCE_SEPARATION_READY = "P25_TRUE_DATE_SOURCE_SEPARATION_READY"
P25_BLOCKED_NO_TRUE_DATE_SOURCE = "P25_BLOCKED_NO_TRUE_DATE_SOURCE"
P25_BLOCKED_DATE_MISMATCH = "P25_BLOCKED_DATE_MISMATCH"
P25_BLOCKED_INSUFFICIENT_ROWS = "P25_BLOCKED_INSUFFICIENT_ROWS"
P25_BLOCKED_CONTRACT_VIOLATION = "P25_BLOCKED_CONTRACT_VIOLATION"
P25_FAIL_INPUT_MISSING = "P25_FAIL_INPUT_MISSING"
P25_FAIL_NON_DETERMINISTIC = "P25_FAIL_NON_DETERMINISTIC"

# ---------------------------------------------------------------------------
# Per-date slice status codes
# ---------------------------------------------------------------------------
TRUE_DATE_SLICE_READY = "TRUE_DATE_SLICE_READY"
TRUE_DATE_SLICE_EMPTY = "TRUE_DATE_SLICE_EMPTY"
TRUE_DATE_SLICE_PARTIAL = "TRUE_DATE_SLICE_PARTIAL"
TRUE_DATE_SLICE_BLOCKED_DATE_MISMATCH = "TRUE_DATE_SLICE_BLOCKED_DATE_MISMATCH"
TRUE_DATE_SLICE_BLOCKED_MISSING_REQUIRED_COLUMNS = (
    "TRUE_DATE_SLICE_BLOCKED_MISSING_REQUIRED_COLUMNS"
)
TRUE_DATE_SLICE_BLOCKED_DUPLICATE_GAME_ID = "TRUE_DATE_SLICE_BLOCKED_DUPLICATE_GAME_ID"

# ---------------------------------------------------------------------------
# Minimum row threshold for a date to be considered non-trivially ready
# ---------------------------------------------------------------------------
MIN_ROWS_FOR_READY_SLICE = 1


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class P25TrueDateSourceSlice:
    """Immutable description of one true-date source slice for a single run_date."""

    run_date: str
    source_game_date: str          # the game_date column value found in the slice
    source_path: str               # absolute or repo-relative path to the source CSV
    source_hash: str               # sha256 of the slice content (excluding run_date)
    n_rows: int
    n_unique_game_ids: int
    game_date_min: str
    game_date_max: str
    has_required_columns: bool
    date_matches_requested: bool   # all game_date values == run_date
    paper_only: bool
    production_ready: bool
    blocker_reason: str = ""       # empty string means no blocker

    def __post_init__(self) -> None:
        if self.production_ready is not False:
            raise ValueError(
                "P25TrueDateSourceSlice: production_ready must be False (paper only)."
            )
        if self.paper_only is not True:
            raise ValueError(
                "P25TrueDateSourceSlice: paper_only must be True."
            )


@dataclass(frozen=True)
class P25DateSeparationResult:
    """Result of attempting true-date source separation for one requested date."""

    run_date: str
    status: str                          # one of TRUE_DATE_SLICE_* constants
    source_path: str                     # path to the best source candidate (may be empty)
    n_rows: int
    n_unique_game_ids: int
    game_date_min: str
    game_date_max: str
    has_required_columns: bool
    blocker_reason: str
    paper_only: bool
    production_ready: bool
    slice_path: str = ""                 # path to written slice CSV (empty if not written)
    source_hash: str = ""

    def __post_init__(self) -> None:
        if self.production_ready is not False:
            raise ValueError(
                "P25DateSeparationResult: production_ready must be False."
            )
        if self.paper_only is not True:
            raise ValueError(
                "P25DateSeparationResult: paper_only must be True."
            )
        valid_statuses = {
            TRUE_DATE_SLICE_READY,
            TRUE_DATE_SLICE_EMPTY,
            TRUE_DATE_SLICE_PARTIAL,
            TRUE_DATE_SLICE_BLOCKED_DATE_MISMATCH,
            TRUE_DATE_SLICE_BLOCKED_MISSING_REQUIRED_COLUMNS,
            TRUE_DATE_SLICE_BLOCKED_DUPLICATE_GAME_ID,
        }
        if self.status not in valid_statuses:
            raise ValueError(
                f"P25DateSeparationResult: invalid status '{self.status}'."
            )


@dataclass(frozen=True)
class P25SourceSeparationSummary:
    """Aggregate summary of the true-date source separation run."""

    date_start: str
    date_end: str
    n_dates_requested: int
    n_true_date_ready: int
    n_empty_dates: int
    n_partial_dates: int
    n_blocked_dates: int
    detected_source_game_date_min: str   # "" if no source found
    detected_source_game_date_max: str   # "" if no source found
    recommended_backfill_date_start: str # "" if none
    recommended_backfill_date_end: str   # "" if none
    source_files_scanned: int
    paper_only: bool
    production_ready: bool

    def __post_init__(self) -> None:
        if self.production_ready is not False:
            raise ValueError(
                "P25SourceSeparationSummary: production_ready must be False."
            )
        if self.paper_only is not True:
            raise ValueError(
                "P25SourceSeparationSummary: paper_only must be True."
            )
        if self.n_dates_requested < 0:
            raise ValueError("n_dates_requested must be >= 0.")


@dataclass(frozen=True)
class P25SourceSeparationGateResult:
    """Final gate result for the P25 source separation run."""

    p25_gate: str
    date_start: str
    date_end: str
    n_dates_requested: int
    n_true_date_ready: int
    n_empty_dates: int
    n_partial_dates: int
    n_blocked_dates: int
    detected_source_game_date_min: str
    detected_source_game_date_max: str
    recommended_backfill_date_start: str
    recommended_backfill_date_end: str
    blocker_reason: str
    paper_only: bool
    production_ready: bool
    generated_at: str

    def __post_init__(self) -> None:
        if self.production_ready is not False:
            raise ValueError(
                "P25SourceSeparationGateResult: production_ready must be False."
            )
        if self.paper_only is not True:
            raise ValueError(
                "P25SourceSeparationGateResult: paper_only must be True."
            )
        valid_gates = {
            P25_TRUE_DATE_SOURCE_SEPARATION_READY,
            P25_BLOCKED_NO_TRUE_DATE_SOURCE,
            P25_BLOCKED_DATE_MISMATCH,
            P25_BLOCKED_INSUFFICIENT_ROWS,
            P25_BLOCKED_CONTRACT_VIOLATION,
            P25_FAIL_INPUT_MISSING,
            P25_FAIL_NON_DETERMINISTIC,
        }
        if self.p25_gate not in valid_gates:
            raise ValueError(
                f"P25SourceSeparationGateResult: invalid p25_gate '{self.p25_gate}'."
            )


@dataclass(frozen=True)
class P25TrueDateArtifactManifest:
    """Manifest of all written true-date source slice artifacts."""

    output_dir: str
    date_start: str
    date_end: str
    written_dates: tuple                 # tuple of date strings that were written
    skipped_dates: tuple                 # dates skipped (empty, blocked, etc.)
    total_rows_written: int
    total_unique_game_ids_written: int
    paper_only: bool
    production_ready: bool
    generated_at: str

    def __post_init__(self) -> None:
        if self.production_ready is not False:
            raise ValueError(
                "P25TrueDateArtifactManifest: production_ready must be False."
            )
        if self.paper_only is not True:
            raise ValueError(
                "P25TrueDateArtifactManifest: paper_only must be True."
            )
