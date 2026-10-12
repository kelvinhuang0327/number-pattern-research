"""
P22 Historical Backfill Data Availability Expansion — Contract Module.

Frozen dataclasses and constants for the P22 historical artifact scanner,
backfill execution plan generator, and CLI orchestrator.

PAPER_ONLY: True
PRODUCTION_READY: False
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Tuple

# ---------------------------------------------------------------------------
# Gate / status constants
# ---------------------------------------------------------------------------

# P22 gate decisions
P22_HISTORICAL_BACKFILL_AVAILABILITY_READY: str = (
    "P22_HISTORICAL_BACKFILL_AVAILABILITY_READY"
)
P22_BLOCKED_NO_AVAILABLE_DATES: str = "P22_BLOCKED_NO_AVAILABLE_DATES"
P22_BLOCKED_CONTRACT_VIOLATION: str = "P22_BLOCKED_CONTRACT_VIOLATION"
P22_FAIL_INPUT_MISSING: str = "P22_FAIL_INPUT_MISSING"
P22_FAIL_NON_DETERMINISTIC: str = "P22_FAIL_NON_DETERMINISTIC"

# Date availability status values
DATE_READY_P20_EXISTS: str = "DATE_READY_P20_EXISTS"
DATE_READY_REPLAYABLE_FROM_P15_P16_P19: str = (
    "DATE_READY_REPLAYABLE_FROM_P15_P16_P19"
)
DATE_PARTIAL_SOURCE_AVAILABLE: str = "DATE_PARTIAL_SOURCE_AVAILABLE"
DATE_MISSING_REQUIRED_SOURCE: str = "DATE_MISSING_REQUIRED_SOURCE"
DATE_BLOCKED_INVALID_ARTIFACTS: str = "DATE_BLOCKED_INVALID_ARTIFACTS"
DATE_BLOCKED_UNSAFE_IDENTITY: str = "DATE_BLOCKED_UNSAFE_IDENTITY"
DATE_UNKNOWN: str = "DATE_UNKNOWN"

# Phase artifact keys
P15_JOINED_OOF_WITH_ODDS: str = "P15_JOINED_OOF_WITH_ODDS"
P15_SIMULATION_LEDGER: str = "P15_SIMULATION_LEDGER"
P16_6_RECOMMENDATION_ROWS: str = "P16_6_RECOMMENDATION_ROWS"
P16_6_RECOMMENDATION_SUMMARY: str = "P16_6_RECOMMENDATION_SUMMARY"
P19_ENRICHED_LEDGER: str = "P19_ENRICHED_LEDGER"
P19_GATE_RESULT: str = "P19_GATE_RESULT"
P17_REPLAY_LEDGER: str = "P17_REPLAY_LEDGER"
P17_REPLAY_SUMMARY: str = "P17_REPLAY_SUMMARY"
P20_DAILY_SUMMARY: str = "P20_DAILY_SUMMARY"
P20_GATE_RESULT: str = "P20_GATE_RESULT"

# Known P20 gate value required by P21/P22
EXPECTED_P20_GATE: str = "P20_DAILY_PAPER_ORCHESTRATOR_READY"

# Directories under each date
P15_DIR: str = "p15_market_odds_simulation"
P16_6_DIR: str = "p16_6_recommendation_gate_p18_policy"
P19_DIR: str = "p19_odds_identity_join_repair"
P17_DIR: str = "p17_replay_with_p19_identity"
P20_DIR: str = "p20_daily_paper_orchestrator"


# ---------------------------------------------------------------------------
# Frozen dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class P22PhaseArtifactStatus:
    """Status of a single phase artifact for a given run_date."""

    artifact_key: str  # e.g. P15_JOINED_OOF_WITH_ODDS
    expected_path: str  # relative to date_dir
    exists: bool
    readable: bool = False
    size_bytes: int = 0
    error_message: str = ""


@dataclass(frozen=True)
class P22DateAvailabilityResult:
    """
    Availability classification for a single run_date.

    availability_status is one of the DATE_* constants.
    phase_statuses is a tuple of P22PhaseArtifactStatus (one per known artifact).
    """

    run_date: str  # ISO 8601: "2026-05-12"
    availability_status: str  # DATE_* constant
    phase_statuses: Tuple[P22PhaseArtifactStatus, ...] = field(
        default_factory=tuple
    )
    p20_gate: str = ""
    n_artifacts_found: int = 0
    n_artifacts_required: int = 0
    error_message: str = ""
    paper_only: bool = True
    production_ready: bool = False

    def __post_init__(self) -> None:
        if self.production_ready:
            raise ValueError(
                "P22DateAvailabilityResult: production_ready must be False"
            )
        if not self.paper_only:
            raise ValueError(
                "P22DateAvailabilityResult: paper_only must be True"
            )


@dataclass(frozen=True)
class P22HistoricalAvailabilitySummary:
    """
    Aggregate summary of a date-range scan.

    paper_only=True, production_ready=False enforced.
    """

    date_start: str
    date_end: str
    n_dates_scanned: int
    n_dates_p20_ready: int
    n_dates_replayable: int
    n_dates_partial: int
    n_dates_missing: int
    n_dates_blocked: int
    n_backfill_candidate_dates: int
    backfill_candidate_dates: Tuple[str, ...] = field(default_factory=tuple)
    missing_dates: Tuple[str, ...] = field(default_factory=tuple)
    blocked_dates: Tuple[str, ...] = field(default_factory=tuple)
    partial_dates: Tuple[str, ...] = field(default_factory=tuple)
    recommended_next_action: str = ""
    paper_only: bool = True
    production_ready: bool = False
    p22_gate: str = ""

    def __post_init__(self) -> None:
        if self.production_ready:
            raise ValueError(
                "P22HistoricalAvailabilitySummary: production_ready must be False"
            )
        if not self.paper_only:
            raise ValueError(
                "P22HistoricalAvailabilitySummary: paper_only must be True"
            )


@dataclass(frozen=True)
class P22BackfillExecutionPlan:
    """
    Execution plan generated from the historical availability scan.

    Emits recommended CLI commands per date status.
    Does NOT execute anything.

    paper_only=True, production_ready=False enforced.
    """

    date_start: str
    date_end: str
    dates_to_skip_already_ready: Tuple[str, ...] = field(default_factory=tuple)
    dates_to_replay_from_existing_sources: Tuple[str, ...] = field(
        default_factory=tuple
    )
    dates_missing_required_sources: Tuple[str, ...] = field(default_factory=tuple)
    dates_blocked: Tuple[str, ...] = field(default_factory=tuple)
    recommended_commands: Tuple[str, ...] = field(default_factory=tuple)
    execution_order: Tuple[str, ...] = field(default_factory=tuple)
    risk_notes: Tuple[str, ...] = field(default_factory=tuple)
    paper_only: bool = True
    production_ready: bool = False

    def __post_init__(self) -> None:
        if self.production_ready:
            raise ValueError(
                "P22BackfillExecutionPlan: production_ready must be False"
            )
        if not self.paper_only:
            raise ValueError(
                "P22BackfillExecutionPlan: paper_only must be True"
            )


@dataclass(frozen=True)
class P22GateResult:
    """
    Final gate result for a P22 scan run.

    Written to p22_gate_result.json.
    paper_only=True, production_ready=False enforced.
    """

    p22_gate: str
    date_start: str
    date_end: str
    n_dates_scanned: int
    n_dates_p20_ready: int
    n_dates_replayable: int
    n_dates_partial: int
    n_dates_missing: int
    n_dates_blocked: int
    n_backfill_candidate_dates: int
    recommended_next_action: str
    paper_only: bool = True
    production_ready: bool = False
    generated_at: str = ""

    def __post_init__(self) -> None:
        if self.production_ready:
            raise ValueError(
                "P22GateResult: production_ready must be False"
            )
        if not self.paper_only:
            raise ValueError(
                "P22GateResult: paper_only must be True"
            )
