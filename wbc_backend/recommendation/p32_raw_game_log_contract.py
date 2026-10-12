"""
P32 Raw Game Log Contract — frozen dataclasses and gate constants.

PAPER_ONLY=True
production_ready=False

This module defines the data contracts and gate decisions for the P32
2024 raw game log artifact layer. It does NOT contain parser logic.

Gate decisions:
  P32_RAW_GAME_LOG_ARTIFACT_READY
  P32_BLOCKED_SOURCE_FILE_MISSING
  P32_BLOCKED_PROVENANCE_UNSAFE
  P32_BLOCKED_SCHEMA_INVALID
  P32_BLOCKED_NO_2024_GAMES
  P32_BLOCKED_CONTRACT_VIOLATION
  P32_FAIL_INPUT_MISSING
  P32_FAIL_NON_DETERMINISTIC
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# Safety constants
# ---------------------------------------------------------------------------

PAPER_ONLY: bool = True
PRODUCTION_READY: bool = False

# ---------------------------------------------------------------------------
# Gate constants
# ---------------------------------------------------------------------------

P32_RAW_GAME_LOG_ARTIFACT_READY = "P32_RAW_GAME_LOG_ARTIFACT_READY"
P32_BLOCKED_SOURCE_FILE_MISSING = "P32_BLOCKED_SOURCE_FILE_MISSING"
P32_BLOCKED_PROVENANCE_UNSAFE = "P32_BLOCKED_PROVENANCE_UNSAFE"
P32_BLOCKED_SCHEMA_INVALID = "P32_BLOCKED_SCHEMA_INVALID"
P32_BLOCKED_NO_2024_GAMES = "P32_BLOCKED_NO_2024_GAMES"
P32_BLOCKED_CONTRACT_VIOLATION = "P32_BLOCKED_CONTRACT_VIOLATION"
P32_FAIL_INPUT_MISSING = "P32_FAIL_INPUT_MISSING"
P32_FAIL_NON_DETERMINISTIC = "P32_FAIL_NON_DETERMINISTIC"

# Set of all valid gate constants for validation
VALID_P32_GATES: frozenset[str] = frozenset(
    {
        P32_RAW_GAME_LOG_ARTIFACT_READY,
        P32_BLOCKED_SOURCE_FILE_MISSING,
        P32_BLOCKED_PROVENANCE_UNSAFE,
        P32_BLOCKED_SCHEMA_INVALID,
        P32_BLOCKED_NO_2024_GAMES,
        P32_BLOCKED_CONTRACT_VIOLATION,
        P32_FAIL_INPUT_MISSING,
        P32_FAIL_NON_DETERMINISTIC,
    }
)

# ---------------------------------------------------------------------------
# Contract: source metadata
# ---------------------------------------------------------------------------


@dataclass
class P32RawGameLogSource:
    """Metadata about the raw game log source file."""

    season: int
    source_name: str
    source_path: str
    provenance_status: str  # VERIFIED | UNRESOLVED | PARTIAL
    license_status: str  # ATTRIBUTION_REQUIRED | UNKNOWN | SAFE_NON_COMMERCIAL | PAID_COMMERCIAL
    attribution_required: bool
    paper_only: bool = True
    production_ready: bool = False

    def __post_init__(self) -> None:
        if self.production_ready:
            raise ValueError(
                "CONTRACT VIOLATION: production_ready must be False. "
                "This is a PAPER_ONLY artifact."
            )
        if not self.paper_only:
            raise ValueError(
                "CONTRACT VIOLATION: paper_only must be True. "
                "This is a PAPER_ONLY artifact."
            )
        if self.season != 2024:
            raise ValueError(
                f"CONTRACT VIOLATION: P32 is scoped to season=2024, got {self.season}."
            )


# ---------------------------------------------------------------------------
# Contract: game identity record
# ---------------------------------------------------------------------------


@dataclass
class P32GameIdentityRecord:
    """
    Canonical game identity — game_id, date, team names.
    No odds, no predictions.
    """

    game_id: str
    game_date: str       # ISO format YYYY-MM-DD
    season: int
    away_team: str
    home_team: str
    source_name: str
    source_row_number: int
    paper_only: bool = True
    production_ready: bool = False

    def __post_init__(self) -> None:
        if self.production_ready:
            raise ValueError("CONTRACT VIOLATION: production_ready must be False.")
        if not self.paper_only:
            raise ValueError("CONTRACT VIOLATION: paper_only must be True.")
        if not self.game_date:
            raise ValueError("game_date must not be empty.")
        # Note: empty game_id is allowed at contract level; parser is responsible
        # for not emitting rows with empty game_ids into final artifacts.


# ---------------------------------------------------------------------------
# Contract: game outcome record
# ---------------------------------------------------------------------------


@dataclass
class P32GameOutcomeRecord:
    """
    Game outcome — scores and binary win/loss label.
    No odds, no predictions.
    """

    game_id: str
    game_date: str
    season: int
    away_team: str
    home_team: str
    away_score: Optional[int]
    home_score: Optional[int]
    y_true_home_win: Optional[int]   # 1=home win, 0=away win, None=no result
    source_name: str
    source_row_number: int
    paper_only: bool = True
    production_ready: bool = False

    def __post_init__(self) -> None:
        if self.production_ready:
            raise ValueError("CONTRACT VIOLATION: production_ready must be False.")
        if not self.paper_only:
            raise ValueError("CONTRACT VIOLATION: paper_only must be True.")
        # Scores and outcome must be consistent
        if self.away_score is not None and self.home_score is not None:
            if self.away_score == self.home_score:
                # Ties are not expected in MLB; mark as None
                pass
            expected = 1 if self.home_score > self.away_score else 0
            if self.y_true_home_win is not None and self.y_true_home_win != expected:
                raise ValueError(
                    f"CONTRACT VIOLATION: y_true_home_win={self.y_true_home_win} "
                    f"inconsistent with scores {self.home_score}:{self.away_score}"
                )


# ---------------------------------------------------------------------------
# Contract: build summary
# ---------------------------------------------------------------------------


@dataclass
class P32RawGameLogBuildSummary:
    """Aggregate statistics produced after parsing Retrosheet game logs."""

    season: int
    source_name: str
    source_path: str
    row_count_raw: int
    row_count_processed: int
    unique_game_id_count: int
    date_start: str          # YYYY-MM-DD or "" if unknown
    date_end: str            # YYYY-MM-DD or "" if unknown
    teams_detected_count: int
    outcome_coverage_pct: float   # fraction [0,1] with non-null outcome
    schema_valid: bool
    blocker: str             # gate constant if blocked, else ""
    paper_only: bool = True
    production_ready: bool = False
    # Explicit no-odds / no-predictions guard
    contains_odds: bool = False
    contains_predictions: bool = False

    def __post_init__(self) -> None:
        if self.production_ready:
            raise ValueError("CONTRACT VIOLATION: production_ready must be False.")
        if not self.paper_only:
            raise ValueError("CONTRACT VIOLATION: paper_only must be True.")
        if self.contains_odds:
            raise ValueError(
                "CONTRACT VIOLATION: P32 artifact must not contain odds data."
            )
        if self.contains_predictions:
            raise ValueError(
                "CONTRACT VIOLATION: P32 artifact must not contain predictions."
            )


# ---------------------------------------------------------------------------
# Contract: gate result
# ---------------------------------------------------------------------------


@dataclass
class P32RawGameLogGateResult:
    """Final gate decision for the P32 build run."""

    gate: str
    season: int
    source_path: str
    row_count_raw: int
    row_count_processed: int
    unique_game_id_count: int
    date_start: str
    date_end: str
    outcome_coverage_pct: float
    provenance_status: str
    license_status: str
    paper_only: bool = True
    production_ready: bool = False
    blocker_reason: str = ""
    artifacts: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.gate not in VALID_P32_GATES:
            raise ValueError(f"Invalid P32 gate: {self.gate!r}")
        if self.production_ready:
            raise ValueError("CONTRACT VIOLATION: production_ready must be False.")
        if not self.paper_only:
            raise ValueError("CONTRACT VIOLATION: paper_only must be True.")

    def to_dict(self) -> dict:
        return {
            "gate": self.gate,
            "season": self.season,
            "source_path": self.source_path,
            "row_count_raw": self.row_count_raw,
            "row_count_processed": self.row_count_processed,
            "unique_game_id_count": self.unique_game_id_count,
            "date_start": self.date_start,
            "date_end": self.date_end,
            "outcome_coverage_pct": self.outcome_coverage_pct,
            "provenance_status": self.provenance_status,
            "license_status": self.license_status,
            "paper_only": self.paper_only,
            "production_ready": self.production_ready,
            "blocker_reason": self.blocker_reason,
            "artifacts": self.artifacts,
        }
