"""
P22.5 Historical Source Artifact Builder — Contract

All frozen dataclasses and string constants.
PAPER_ONLY. PRODUCTION_READY=False enforced at construction.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

# ---------------------------------------------------------------------------
# Gate constants
# ---------------------------------------------------------------------------

P22_5_SOURCE_ARTIFACT_BUILDER_READY = "P22_5_SOURCE_ARTIFACT_BUILDER_READY"
P22_5_BLOCKED_NO_SOURCE_CANDIDATES = "P22_5_BLOCKED_NO_SOURCE_CANDIDATES"
P22_5_BLOCKED_UNSAFE_SOURCE_MAPPING = "P22_5_BLOCKED_UNSAFE_SOURCE_MAPPING"
P22_5_BLOCKED_CONTRACT_VIOLATION = "P22_5_BLOCKED_CONTRACT_VIOLATION"
P22_5_FAIL_INPUT_MISSING = "P22_5_FAIL_INPUT_MISSING"
P22_5_FAIL_NON_DETERMINISTIC = "P22_5_FAIL_NON_DETERMINISTIC"

# ---------------------------------------------------------------------------
# Source candidate statuses
# ---------------------------------------------------------------------------

SOURCE_CANDIDATE_USABLE = "SOURCE_CANDIDATE_USABLE"
SOURCE_CANDIDATE_PARTIAL = "SOURCE_CANDIDATE_PARTIAL"
SOURCE_CANDIDATE_MISSING = "SOURCE_CANDIDATE_MISSING"
SOURCE_CANDIDATE_UNSAFE_MAPPING = "SOURCE_CANDIDATE_UNSAFE_MAPPING"
SOURCE_CANDIDATE_UNKNOWN = "SOURCE_CANDIDATE_UNKNOWN"

# ---------------------------------------------------------------------------
# Source artifact types
# ---------------------------------------------------------------------------

HISTORICAL_OOF_PREDICTIONS = "HISTORICAL_OOF_PREDICTIONS"
HISTORICAL_MARKET_ODDS = "HISTORICAL_MARKET_ODDS"
HISTORICAL_GAME_OUTCOMES = "HISTORICAL_GAME_OUTCOMES"
HISTORICAL_GAME_IDENTITY = "HISTORICAL_GAME_IDENTITY"
HISTORICAL_P15_JOINED_INPUT = "HISTORICAL_P15_JOINED_INPUT"
HISTORICAL_P15_SIMULATION_INPUT = "HISTORICAL_P15_SIMULATION_INPUT"

# ---------------------------------------------------------------------------
# Mapping risk levels
# ---------------------------------------------------------------------------

MAPPING_RISK_LOW = "LOW"
MAPPING_RISK_MEDIUM = "MEDIUM"
MAPPING_RISK_HIGH = "HIGH"
MAPPING_RISK_UNKNOWN = "UNKNOWN"

# ---------------------------------------------------------------------------
# Frozen dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class P225SourceArtifactSpec:
    """Specification for a type of source artifact."""

    source_type: str
    required_columns: Tuple[str, ...] = ()
    optional_columns: Tuple[str, ...] = ()
    min_rows: int = 1


@dataclass(frozen=True)
class P225HistoricalSourceCandidate:
    """A discovered file that may be a historical source artifact."""

    source_path: str
    source_type: str
    source_date: str  # YYYY-MM-DD or empty if unknown
    coverage_pct: float  # 0.0–1.0 ratio of non-null key columns
    row_count: int
    has_game_id: bool
    has_y_true: bool
    has_odds: bool
    has_p_model_or_p_oof: bool
    mapping_risk: str
    candidate_status: str
    paper_only: bool = True
    production_ready: bool = False
    error_message: str = ""

    def __post_init__(self) -> None:
        if self.production_ready:
            raise ValueError(
                "P225HistoricalSourceCandidate: production_ready must be False"
            )
        if not self.paper_only:
            raise ValueError(
                "P225HistoricalSourceCandidate: paper_only must be True"
            )


@dataclass(frozen=True)
class P225DateSourceAvailability:
    """Source data availability assessment for a single run_date."""

    run_date: str
    candidate_status: str
    has_predictions: bool
    has_odds: bool
    has_outcomes: bool
    has_identity: bool
    is_p15_ready: bool
    blocked_reason: str = ""
    candidates: Tuple[str, ...] = ()  # source_paths of contributing candidates
    paper_only: bool = True
    production_ready: bool = False

    def __post_init__(self) -> None:
        if self.production_ready:
            raise ValueError(
                "P225DateSourceAvailability: production_ready must be False"
            )
        if not self.paper_only:
            raise ValueError(
                "P225DateSourceAvailability: paper_only must be True"
            )


@dataclass(frozen=True)
class P225ArtifactBuildPlan:
    """Plan for building P15 source inputs from discovered historical data."""

    date_start: str
    date_end: str
    dates_ready_to_build_p15_inputs: Tuple[str, ...] = ()
    dates_partial_missing_odds: Tuple[str, ...] = ()
    dates_partial_missing_predictions: Tuple[str, ...] = ()
    dates_partial_missing_outcomes: Tuple[str, ...] = ()
    dates_unsafe_identity_mapping: Tuple[str, ...] = ()
    dates_missing_all_sources: Tuple[str, ...] = ()
    recommended_safe_commands: Tuple[str, ...] = ()
    blocked_reason_by_date: Tuple[str, ...] = ()  # "DATE:REASON" strings
    paper_only: bool = True
    production_ready: bool = False

    def __post_init__(self) -> None:
        if self.production_ready:
            raise ValueError(
                "P225ArtifactBuildPlan: production_ready must be False"
            )
        if not self.paper_only:
            raise ValueError(
                "P225ArtifactBuildPlan: paper_only must be True"
            )


@dataclass(frozen=True)
class P225ArtifactBuilderGateResult:
    """Final gate result for P22.5 source artifact builder."""

    p22_5_gate: str
    date_start: str
    date_end: str
    n_source_candidates: int
    n_usable_candidates: int
    n_dates_ready_to_build: int
    n_dates_partial: int
    n_dates_unsafe: int
    n_dates_missing: int
    dry_run_preview_count: int
    recommended_next_action: str
    paper_only: bool = True
    production_ready: bool = False
    generated_at: str = ""

    def __post_init__(self) -> None:
        if self.production_ready:
            raise ValueError(
                "P225ArtifactBuilderGateResult: production_ready must be False"
            )
        if not self.paper_only:
            raise ValueError(
                "P225ArtifactBuilderGateResult: paper_only must be True"
            )
