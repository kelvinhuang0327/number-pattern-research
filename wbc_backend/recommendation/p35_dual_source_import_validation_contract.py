"""P35 Dual Source Import Validation — Frozen Contract

Defines all gate constants, status constants, and dataclasses for P35.
This module is the single source of truth for gate names, field names,
and dataclass shapes.

HARD GUARDS:
- PAPER_ONLY = True always
- PRODUCTION_READY = False always
- No odds may be downloaded without explicit approval record.
- No p_oof / p_model may be fabricated.
- No joined input may be marked ready in this phase.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

# ---------------------------------------------------------------------------
# PHASE GUARDS — immutable
# ---------------------------------------------------------------------------

PAPER_ONLY: bool = True
PRODUCTION_READY: bool = False

# ---------------------------------------------------------------------------
# GATE CONSTANTS
# ---------------------------------------------------------------------------

P35_DUAL_SOURCE_IMPORT_VALIDATION_READY: str = "P35_DUAL_SOURCE_IMPORT_VALIDATION_READY"
P35_BLOCKED_ODDS_LICENSE_NOT_APPROVED: str = "P35_BLOCKED_ODDS_LICENSE_NOT_APPROVED"
P35_BLOCKED_ODDS_SOURCE_NOT_PROVIDED: str = "P35_BLOCKED_ODDS_SOURCE_NOT_PROVIDED"
P35_BLOCKED_PREDICTION_REBUILD_NOT_FEASIBLE: str = "P35_BLOCKED_PREDICTION_REBUILD_NOT_FEASIBLE"
P35_BLOCKED_FEATURE_PIPELINE_MISSING: str = "P35_BLOCKED_FEATURE_PIPELINE_MISSING"
P35_BLOCKED_CONTRACT_VIOLATION: str = "P35_BLOCKED_CONTRACT_VIOLATION"
P35_FAIL_INPUT_MISSING: str = "P35_FAIL_INPUT_MISSING"
P35_FAIL_NON_DETERMINISTIC: str = "P35_FAIL_NON_DETERMINISTIC"

ALL_P35_GATES: Tuple[str, ...] = (
    P35_DUAL_SOURCE_IMPORT_VALIDATION_READY,
    P35_BLOCKED_ODDS_LICENSE_NOT_APPROVED,
    P35_BLOCKED_ODDS_SOURCE_NOT_PROVIDED,
    P35_BLOCKED_PREDICTION_REBUILD_NOT_FEASIBLE,
    P35_BLOCKED_FEATURE_PIPELINE_MISSING,
    P35_BLOCKED_CONTRACT_VIOLATION,
    P35_FAIL_INPUT_MISSING,
    P35_FAIL_NON_DETERMINISTIC,
)

# ---------------------------------------------------------------------------
# VALIDATION STATUS CONSTANTS
# ---------------------------------------------------------------------------

VALIDATION_READY_FOR_IMPLEMENTATION: str = "VALIDATION_READY_FOR_IMPLEMENTATION"
VALIDATION_REQUIRES_MANUAL_APPROVAL: str = "VALIDATION_REQUIRES_MANUAL_APPROVAL"
VALIDATION_BLOCKED_LICENSE: str = "VALIDATION_BLOCKED_LICENSE"
VALIDATION_BLOCKED_SOURCE_MISSING: str = "VALIDATION_BLOCKED_SOURCE_MISSING"
VALIDATION_BLOCKED_SCHEMA: str = "VALIDATION_BLOCKED_SCHEMA"
VALIDATION_BLOCKED_LEAKAGE_RISK: str = "VALIDATION_BLOCKED_LEAKAGE_RISK"

ALL_VALIDATION_STATUSES: Tuple[str, ...] = (
    VALIDATION_READY_FOR_IMPLEMENTATION,
    VALIDATION_REQUIRES_MANUAL_APPROVAL,
    VALIDATION_BLOCKED_LICENSE,
    VALIDATION_BLOCKED_SOURCE_MISSING,
    VALIDATION_BLOCKED_SCHEMA,
    VALIDATION_BLOCKED_LEAKAGE_RISK,
)

# ---------------------------------------------------------------------------
# FEASIBILITY CONSTANTS
# ---------------------------------------------------------------------------

FEASIBILITY_READY: str = "FEASIBILITY_READY"
FEASIBILITY_BLOCKED_PIPELINE_MISSING: str = "FEASIBILITY_BLOCKED_PIPELINE_MISSING"
FEASIBILITY_BLOCKED_LEAKAGE_RISK: str = "FEASIBILITY_BLOCKED_LEAKAGE_RISK"
FEASIBILITY_BLOCKED_ADAPTER_MISSING: str = "FEASIBILITY_BLOCKED_ADAPTER_MISSING"
FEASIBILITY_REQUIRES_P36_IMPLEMENTATION: str = "FEASIBILITY_REQUIRES_P36_IMPLEMENTATION"

ALL_FEASIBILITY_STATUSES: Tuple[str, ...] = (
    FEASIBILITY_READY,
    FEASIBILITY_BLOCKED_PIPELINE_MISSING,
    FEASIBILITY_BLOCKED_LEAKAGE_RISK,
    FEASIBILITY_BLOCKED_ADAPTER_MISSING,
    FEASIBILITY_REQUIRES_P36_IMPLEMENTATION,
)

# ---------------------------------------------------------------------------
# LICENSE STATUS CONSTANTS
# ---------------------------------------------------------------------------

LICENSE_APPROVED_INTERNAL_RESEARCH: str = "approved_internal_research"
LICENSE_REVIEW_REQUIRED: str = "review_required"
LICENSE_BLOCKED_NOT_APPROVED: str = "blocked_not_approved"
LICENSE_UNKNOWN: str = "unknown"

ALL_LICENSE_STATUSES: Tuple[str, ...] = (
    LICENSE_APPROVED_INTERNAL_RESEARCH,
    LICENSE_REVIEW_REQUIRED,
    LICENSE_BLOCKED_NOT_APPROVED,
    LICENSE_UNKNOWN,
)

# ---------------------------------------------------------------------------
# REQUIRED TEMPLATE COLUMNS (from P34)
# ---------------------------------------------------------------------------

ODDS_REQUIRED_COLUMNS: Tuple[str, ...] = (
    "game_id",
    "game_date",
    "home_team",
    "away_team",
    "p_market",
    "odds_decimal",
    "sportsbook",
    "market_type",
    "closing_timestamp",
    "source_odds_ref",
    "license_ref",
)

PREDICTION_REQUIRED_COLUMNS: Tuple[str, ...] = (
    "game_id",
    "game_date",
    "home_team",
    "away_team",
    "p_oof",
    "model_version",
    "fold_id",
    "source_prediction_ref",
    "generated_without_y_true",
)

# ---------------------------------------------------------------------------
# DATACLASSES
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class P35OddsLicenseValidationResult:
    """Result of validating odds source license and provenance."""

    source_type: str
    source_name: str
    source_path_or_url: str
    license_status: str
    provenance_status: str
    schema_status: str
    leakage_risk: str
    implementation_ready: bool
    blocker_reason: str
    paper_only: bool = True
    production_ready: bool = False
    season: int = 2024
    checklist_items: Tuple[str, ...] = field(default_factory=tuple)
    approval_record_found: bool = False
    notes: str = ""


@dataclass(frozen=True)
class P35OddsImportValidationPlan:
    """Structured plan for odds import validation steps."""

    source_name: str
    source_url: str
    required_columns: Tuple[str, ...]
    license_status: str
    validation_status: str
    approval_required: bool
    approved: bool
    blocker_reason: str
    paper_only: bool = True
    production_ready: bool = False
    season: int = 2024
    next_steps: Tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class P35PredictionRebuildFeasibilityResult:
    """Feasibility assessment for rebuilding 2024 OOF predictions."""

    feature_pipeline_found: bool
    model_training_found: bool
    oof_generation_found: bool
    leakage_guard_found: bool
    time_aware_split_found: bool
    adapter_for_2024_format_found: bool
    feasibility_status: str
    blocker_reason: str
    candidate_scripts: Tuple[str, ...] = field(default_factory=tuple)
    candidate_models: Tuple[str, ...] = field(default_factory=tuple)
    paper_only: bool = True
    production_ready: bool = False
    season: int = 2024
    notes: str = ""


@dataclass
class P35DualSourceValidationSummary:
    """Aggregated summary of all P35 validation findings."""

    odds_license_status: str
    odds_source_status: str
    prediction_feasibility_status: str
    feature_pipeline_status: str
    validator_specs_written: bool
    gate: str
    blocker_reasons: List[str] = field(default_factory=list)
    paper_only: bool = True
    production_ready: bool = False
    season: int = 2024
    plan_summary: str = ""
    recommended_next_action: str = ""


@dataclass
class P35GateResult:
    """Final gate result for P35."""

    gate: str
    odds_license_status: str
    odds_source_status: str
    prediction_feasibility_status: str
    feature_pipeline_status: str
    blocker_reason: str
    license_risk: str
    paper_only: bool = True
    production_ready: bool = False
    season: int = 2024
    next_phase: str = "P36_DUAL_BLOCKER_RESOLUTION_PLAN"
    artifacts: List[str] = field(default_factory=list)
