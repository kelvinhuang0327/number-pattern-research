"""
wbc_backend/recommendation/p30_source_acquisition_contract.py

P30 Historical Season Source Acquisition — frozen dataclasses and gate constants.

All dataclasses enforce:
  paper_only=True
  production_ready=False

This module is PAPER_ONLY source acquisition planning.
DO NOT use outputs to make real bets or enable production pipelines.
"""
from __future__ import annotations

import dataclasses
from typing import FrozenSet, Optional

# ---------------------------------------------------------------------------
# Gate decision constants
# ---------------------------------------------------------------------------

P30_SOURCE_ACQUISITION_PLAN_READY: str = "P30_SOURCE_ACQUISITION_PLAN_READY"
P30_BLOCKED_NO_VERIFIABLE_SOURCE: str = "P30_BLOCKED_NO_VERIFIABLE_SOURCE"
P30_BLOCKED_LICENSE_OR_PROVENANCE_UNSAFE: str = "P30_BLOCKED_LICENSE_OR_PROVENANCE_UNSAFE"
P30_BLOCKED_MISSING_REQUIRED_ARTIFACT_SPEC: str = "P30_BLOCKED_MISSING_REQUIRED_ARTIFACT_SPEC"
P30_BLOCKED_CONTRACT_VIOLATION: str = "P30_BLOCKED_CONTRACT_VIOLATION"
P30_FAIL_INPUT_MISSING: str = "P30_FAIL_INPUT_MISSING"
P30_FAIL_NON_DETERMINISTIC: str = "P30_FAIL_NON_DETERMINISTIC"

_VALID_P30_GATES: FrozenSet[str] = frozenset(
    {
        P30_SOURCE_ACQUISITION_PLAN_READY,
        P30_BLOCKED_NO_VERIFIABLE_SOURCE,
        P30_BLOCKED_LICENSE_OR_PROVENANCE_UNSAFE,
        P30_BLOCKED_MISSING_REQUIRED_ARTIFACT_SPEC,
        P30_BLOCKED_CONTRACT_VIOLATION,
        P30_FAIL_INPUT_MISSING,
        P30_FAIL_NON_DETERMINISTIC,
    }
)

# ---------------------------------------------------------------------------
# Source candidate status constants
# ---------------------------------------------------------------------------

SOURCE_PLAN_READY: str = "SOURCE_PLAN_READY"
SOURCE_PLAN_PARTIAL: str = "SOURCE_PLAN_PARTIAL"
SOURCE_PLAN_BLOCKED_PROVENANCE: str = "SOURCE_PLAN_BLOCKED_PROVENANCE"
SOURCE_PLAN_BLOCKED_SCHEMA_GAP: str = "SOURCE_PLAN_BLOCKED_SCHEMA_GAP"
SOURCE_PLAN_BLOCKED_NOT_AVAILABLE: str = "SOURCE_PLAN_BLOCKED_NOT_AVAILABLE"

_VALID_SOURCE_STATUSES: FrozenSet[str] = frozenset(
    {
        SOURCE_PLAN_READY,
        SOURCE_PLAN_PARTIAL,
        SOURCE_PLAN_BLOCKED_PROVENANCE,
        SOURCE_PLAN_BLOCKED_SCHEMA_GAP,
        SOURCE_PLAN_BLOCKED_NOT_AVAILABLE,
    }
)

# ---------------------------------------------------------------------------
# Required artifact spec type constants
# ---------------------------------------------------------------------------

ARTIFACT_GAME_IDENTITY: str = "GAME_IDENTITY"
ARTIFACT_GAME_OUTCOMES: str = "GAME_OUTCOMES"
ARTIFACT_MODEL_PREDICTIONS_OR_OOF: str = "MODEL_PREDICTIONS_OR_OOF"
ARTIFACT_MARKET_ODDS: str = "MARKET_ODDS"
ARTIFACT_TRUE_DATE_JOINED_INPUT: str = "TRUE_DATE_JOINED_INPUT"
ARTIFACT_TRUE_DATE_SLICE_OUTPUT: str = "TRUE_DATE_SLICE_OUTPUT"
ARTIFACT_PAPER_REPLAY_OUTPUT: str = "PAPER_REPLAY_OUTPUT"

_VALID_ARTIFACT_TYPES: FrozenSet[str] = frozenset(
    {
        ARTIFACT_GAME_IDENTITY,
        ARTIFACT_GAME_OUTCOMES,
        ARTIFACT_MODEL_PREDICTIONS_OR_OOF,
        ARTIFACT_MARKET_ODDS,
        ARTIFACT_TRUE_DATE_JOINED_INPUT,
        ARTIFACT_TRUE_DATE_SLICE_OUTPUT,
        ARTIFACT_PAPER_REPLAY_OUTPUT,
    }
)

# ---------------------------------------------------------------------------
# Default thresholds
# ---------------------------------------------------------------------------

TARGET_ACTIVE_ENTRIES_DEFAULT: int = 1500
CURRENT_ACTIVE_ENTRIES_P29: int = 324
PRIOR_GATE_MARKER: str = "P29_BLOCKED_SOURCE_COVERAGE_INSUFFICIENT"

# ---------------------------------------------------------------------------
# Frozen dataclasses
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class P30HistoricalSeasonSourceCandidate:
    """Describes a candidate historical source file or directory."""

    source_path: str
    source_type: str  # e.g. "csv", "xlsx", "directory", "api_endpoint"
    target_season: str  # e.g. "2024", "2025", "2026"
    date_start: str
    date_end: str
    estimated_games: int
    estimated_rows: int
    has_game_id: bool
    has_game_date: bool
    has_y_true: bool
    has_home_away_teams: bool
    has_p_model: bool
    has_p_market: bool
    has_odds_decimal: bool
    provenance_status: str  # e.g. "KNOWN", "UNKNOWN", "LICENSE_REQUIRED"
    license_risk: str  # e.g. "LOW", "MEDIUM", "HIGH", "UNKNOWN"
    schema_coverage: str  # e.g. "FULL", "PARTIAL", "MINIMAL"
    source_status: str
    coverage_note: str
    paper_only: bool
    production_ready: bool

    def __post_init__(self) -> None:
        if not self.paper_only:
            raise ValueError("paper_only must be True for P30HistoricalSeasonSourceCandidate")
        if self.production_ready:
            raise ValueError("production_ready must be False for P30HistoricalSeasonSourceCandidate")
        if self.source_status not in _VALID_SOURCE_STATUSES:
            raise ValueError(
                f"source_status '{self.source_status}' not in {_VALID_SOURCE_STATUSES}"
            )


@dataclasses.dataclass(frozen=True)
class P30RequiredArtifactSpec:
    """Specifies one required artifact type and its column requirements."""

    artifact_type: str
    target_season: str
    required_columns: str  # comma-separated canonical column names
    accepted_aliases: str  # comma-separated alternate column names (JSON string)
    is_present_in_existing_source: bool
    coverage_status: str  # "FULL", "PARTIAL", "MISSING"
    missing_columns: str  # comma-separated list of missing columns
    schema_gap_note: str
    paper_only: bool
    production_ready: bool

    def __post_init__(self) -> None:
        if not self.paper_only:
            raise ValueError("paper_only must be True for P30RequiredArtifactSpec")
        if self.production_ready:
            raise ValueError("production_ready must be False for P30RequiredArtifactSpec")
        if self.artifact_type not in _VALID_ARTIFACT_TYPES:
            raise ValueError(
                f"artifact_type '{self.artifact_type}' not in {_VALID_ARTIFACT_TYPES}"
            )
        if self.coverage_status not in ("FULL", "PARTIAL", "MISSING"):
            raise ValueError(f"coverage_status must be FULL/PARTIAL/MISSING, got '{self.coverage_status}'")


@dataclasses.dataclass(frozen=True)
class P30SourceAcquisitionPlan:
    """Full source acquisition plan for a target season."""

    target_season: str
    date_start: str
    date_end: str
    expected_games: int
    expected_min_active_entries: int
    source_path_or_url: str
    provenance_status: str
    license_risk: str
    schema_coverage: str
    n_source_candidates: int
    n_partial_sources: int
    n_ready_sources: int
    schema_gap_count: int
    missing_artifact_types: str  # comma-separated
    required_build_steps: str  # newline-separated step descriptions
    required_validation_steps: str  # newline-separated
    estimated_sample_gain: int
    recommended_next_action: str
    acquisition_feasibility_note: str
    p30_gate: str
    audit_status: str
    paper_only: bool
    production_ready: bool

    def __post_init__(self) -> None:
        if not self.paper_only:
            raise ValueError("paper_only must be True for P30SourceAcquisitionPlan")
        if self.production_ready:
            raise ValueError("production_ready must be False for P30SourceAcquisitionPlan")
        if self.p30_gate not in _VALID_P30_GATES:
            raise ValueError(f"p30_gate '{self.p30_gate}' not in valid gates")
        if self.audit_status not in _VALID_SOURCE_STATUSES:
            raise ValueError(f"audit_status '{self.audit_status}' not in {_VALID_SOURCE_STATUSES}")


@dataclasses.dataclass(frozen=True)
class P30ArtifactBuilderPlan:
    """Dry-run skeleton of the artifact build pipeline for a target season."""

    target_season: str
    build_phase: str  # e.g. "P31_BUILD_2024_JOINED_INPUT"
    requires_game_identity: bool
    requires_game_outcomes: bool
    requires_model_predictions: bool
    requires_market_odds: bool
    can_build_joined_input: bool
    can_build_true_date_slices: bool
    can_build_paper_replay: bool
    missing_artifacts: str  # comma-separated
    dry_run_preview_path: str
    dry_run_status: str  # "PREVIEW_READY", "BLOCKED_MISSING_ARTIFACTS", "EMPTY"
    blocker_reason: str
    build_command_plan: str  # newline-separated build steps
    paper_only: bool
    production_ready: bool

    def __post_init__(self) -> None:
        if not self.paper_only:
            raise ValueError("paper_only must be True for P30ArtifactBuilderPlan")
        if self.production_ready:
            raise ValueError("production_ready must be False for P30ArtifactBuilderPlan")


@dataclasses.dataclass(frozen=True)
class P30SourceAcquisitionGateResult:
    """Final gate result for P30 source acquisition plan."""

    p30_gate: str
    target_season: str
    n_source_candidates: int
    n_partial_sources: int
    n_ready_sources: int
    schema_gap_count: int
    expected_sample_gain: int
    recommended_next_action: str
    audit_status: str
    blocker_reason: str
    paper_only: bool
    production_ready: bool

    def __post_init__(self) -> None:
        if not self.paper_only:
            raise ValueError("paper_only must be True for P30SourceAcquisitionGateResult")
        if self.production_ready:
            raise ValueError("production_ready must be False for P30SourceAcquisitionGateResult")
        if self.p30_gate not in _VALID_P30_GATES:
            raise ValueError(f"p30_gate '{self.p30_gate}' not in valid gates")
        if self.audit_status not in _VALID_SOURCE_STATUSES:
            raise ValueError(f"audit_status '{self.audit_status}' not in {_VALID_SOURCE_STATUSES}")
