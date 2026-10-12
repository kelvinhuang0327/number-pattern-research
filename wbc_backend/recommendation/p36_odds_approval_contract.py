"""P36 Odds Approval Import Gate — Contract.

PAPER_ONLY=True, PRODUCTION_READY=False throughout.
This module defines all constants, statuses, and dataclasses for P36.

P36 resolves the P35 blocker (P35_BLOCKED_ODDS_LICENSE_NOT_APPROVED) by building
a strict, auditable approval-record gate for any 2024 historical odds source.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

# ---------------------------------------------------------------------------
# Module-level guards (must not be changed)
# ---------------------------------------------------------------------------

PAPER_ONLY: bool = True
PRODUCTION_READY: bool = False
SEASON: int = 2024

# ---------------------------------------------------------------------------
# Gate decisions
# ---------------------------------------------------------------------------

P36_ODDS_APPROVAL_RECORD_READY: str = "P36_ODDS_APPROVAL_RECORD_READY"
P36_BLOCKED_APPROVAL_RECORD_MISSING: str = "P36_BLOCKED_APPROVAL_RECORD_MISSING"
P36_BLOCKED_APPROVAL_RECORD_INVALID: str = "P36_BLOCKED_APPROVAL_RECORD_INVALID"
P36_BLOCKED_LICENSE_NOT_ALLOWED_FOR_RESEARCH: str = (
    "P36_BLOCKED_LICENSE_NOT_ALLOWED_FOR_RESEARCH"
)
P36_BLOCKED_REDISTRIBUTION_RISK: str = "P36_BLOCKED_REDISTRIBUTION_RISK"
P36_BLOCKED_ODDS_SOURCE_NOT_PROVIDED: str = "P36_BLOCKED_ODDS_SOURCE_NOT_PROVIDED"
P36_BLOCKED_CONTRACT_VIOLATION: str = "P36_BLOCKED_CONTRACT_VIOLATION"
P36_FAIL_INPUT_MISSING: str = "P36_FAIL_INPUT_MISSING"
P36_FAIL_NON_DETERMINISTIC: str = "P36_FAIL_NON_DETERMINISTIC"

ALL_P36_GATES: Tuple[str, ...] = (
    P36_ODDS_APPROVAL_RECORD_READY,
    P36_BLOCKED_APPROVAL_RECORD_MISSING,
    P36_BLOCKED_APPROVAL_RECORD_INVALID,
    P36_BLOCKED_LICENSE_NOT_ALLOWED_FOR_RESEARCH,
    P36_BLOCKED_REDISTRIBUTION_RISK,
    P36_BLOCKED_ODDS_SOURCE_NOT_PROVIDED,
    P36_BLOCKED_CONTRACT_VIOLATION,
    P36_FAIL_INPUT_MISSING,
    P36_FAIL_NON_DETERMINISTIC,
)

# ---------------------------------------------------------------------------
# Approval statuses
# ---------------------------------------------------------------------------

APPROVAL_READY: str = "APPROVAL_READY"
APPROVAL_MISSING: str = "APPROVAL_MISSING"
APPROVAL_INVALID: str = "APPROVAL_INVALID"
APPROVAL_REQUIRES_LEGAL_REVIEW: str = "APPROVAL_REQUIRES_LEGAL_REVIEW"
APPROVAL_BLOCKED_LICENSE: str = "APPROVAL_BLOCKED_LICENSE"
APPROVAL_BLOCKED_PROVENANCE: str = "APPROVAL_BLOCKED_PROVENANCE"

ALL_APPROVAL_STATUSES: Tuple[str, ...] = (
    APPROVAL_READY,
    APPROVAL_MISSING,
    APPROVAL_INVALID,
    APPROVAL_REQUIRES_LEGAL_REVIEW,
    APPROVAL_BLOCKED_LICENSE,
    APPROVAL_BLOCKED_PROVENANCE,
)

# ---------------------------------------------------------------------------
# Required approval record fields
# ---------------------------------------------------------------------------

APPROVAL_RECORD_REQUIRED_FIELDS: Tuple[str, ...] = (
    "provider_name",
    "source_name",
    "source_url_or_reference",
    "license_terms_summary",
    "allowed_use",
    "redistribution_allowed",
    "attribution_required",
    "internal_research_allowed",
    "commercial_use_allowed",
    "approved_by",
    "approved_at",
    "approval_scope",
    "source_file_expected_path",
    "checksum_required",
    "paper_only",
    "production_ready",
)

# Total: 16 required fields
assert len(APPROVAL_RECORD_REQUIRED_FIELDS) == 16

# ---------------------------------------------------------------------------
# Required manual odds import columns
# ---------------------------------------------------------------------------

MANUAL_ODDS_REQUIRED_COLUMNS: Tuple[str, ...] = (
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

# Total: 11 required columns
assert len(MANUAL_ODDS_REQUIRED_COLUMNS) == 11

# Columns that indicate look-ahead leakage (must NOT appear)
FORBIDDEN_ODDS_COLUMNS: Tuple[str, ...] = (
    "y_true",
    "final_score",
    "home_score",
    "away_score",
    "winner",
    "outcome",
    "result",
    "run_diff",
    "total_runs",
    "game_result",
)

ALLOWED_MARKET_TYPES: Tuple[str, ...] = (
    "moneyline",
    "ml",
    "money_line",
    "1x2",
    "h2h",
)

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class P36OddsApprovalRecord:
    """Structured representation of a manually provided approval record."""

    provider_name: str
    source_name: str
    source_url_or_reference: str
    license_terms_summary: str
    allowed_use: str
    redistribution_allowed: bool
    attribution_required: bool
    internal_research_allowed: bool
    commercial_use_allowed: bool
    approved_by: str
    approved_at: str
    approval_scope: str
    source_file_expected_path: str
    checksum_required: bool
    paper_only: bool
    production_ready: bool


@dataclass(frozen=True)
class P36OddsApprovalValidationResult:
    """Result of validating a P36OddsApprovalRecord."""

    approval_status: str  # one of ALL_APPROVAL_STATUSES
    approval_record_found: bool
    all_required_fields_present: bool
    internal_research_allowed: bool
    allowed_use_valid: bool
    approved_by_present: bool
    approved_at_present: bool
    source_file_path_present: bool
    paper_only: bool
    production_ready: bool
    redistribution_allowed: bool
    redistribution_risk_note: str
    blocker_reason: str
    missing_fields: Tuple[str, ...]
    season: int = SEASON


@dataclass(frozen=True)
class P36ManualOddsImportSpec:
    """Specification for a manual licensed odds import."""

    required_columns: Tuple[str, ...]
    forbidden_columns: Tuple[str, ...]
    allowed_market_types: Tuple[str, ...]
    p_market_range: Tuple[float, float]
    odds_decimal_min: float
    paper_only: bool
    production_ready: bool
    notes: str
    season: int = SEASON


@dataclass(frozen=True)
class P36OddsImportGateResult:
    """Per-check gate result."""

    check_name: str
    passed: bool
    reason: str


@dataclass
class P36GateResult:
    """Overall P36 gate decision."""

    gate: str
    approval_record_status: str
    odds_source_status: str
    internal_research_allowed: bool
    raw_odds_commit_allowed: bool
    blocker_reason: str
    recommended_next_action: str
    paper_only: bool
    production_ready: bool
    season: int
    artifacts: List[str] = field(default_factory=list)
    next_phase: str = "P37_BUILD_2024_ODDS_IMPORT_ARTIFACT"
    generated_at: str = ""
