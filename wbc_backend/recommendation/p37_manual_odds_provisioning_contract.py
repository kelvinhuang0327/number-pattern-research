"""
P37 Manual Odds Approval Record Provisioning / Licensed Odds Artifact Builder Gate

PAPER_ONLY=True  PRODUCTION_READY=False  SEASON=2024

This module defines contracts, constants, and dataclasses for the P37 gate.
P37 remains blocked until:
  1. A valid approval record exists AND passes P36/P37 validation.
  2. A licensed odds source CSV exists AND passes schema/leakage validation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple

# ---------------------------------------------------------------------------
# Module-level guards — enforced by all P37 modules
# ---------------------------------------------------------------------------
PAPER_ONLY: bool = True
PRODUCTION_READY: bool = False
SEASON: int = 2024

# ---------------------------------------------------------------------------
# Gate decisions
# ---------------------------------------------------------------------------
ALL_P37_GATES: Tuple[str, ...] = (
    "P37_MANUAL_ODDS_PROVISIONING_GATE_READY",
    "P37_BLOCKED_APPROVAL_RECORD_MISSING",
    "P37_BLOCKED_APPROVAL_RECORD_INVALID",
    "P37_BLOCKED_LICENSE_NOT_APPROVED",
    "P37_BLOCKED_MANUAL_ODDS_FILE_MISSING",
    "P37_BLOCKED_MANUAL_ODDS_SCHEMA_INVALID",
    "P37_BLOCKED_RAW_ODDS_COMMIT_RISK",
    "P37_BLOCKED_CONTRACT_VIOLATION",
    "P37_FAIL_INPUT_MISSING",
    "P37_FAIL_NON_DETERMINISTIC",
)

# ---------------------------------------------------------------------------
# Provisioning statuses
# ---------------------------------------------------------------------------
ALL_P37_STATUSES: Tuple[str, ...] = (
    "TEMPLATE_READY",
    "APPROVAL_REQUIRED",
    "APPROVAL_VALID",
    "APPROVAL_INVALID",
    "MANUAL_ODDS_REQUIRED",
    "MANUAL_ODDS_VALID",
    "MANUAL_ODDS_INVALID",
    "RAW_COMMIT_BLOCKED",
)

# ---------------------------------------------------------------------------
# Required fields for the approval record template
# ---------------------------------------------------------------------------
APPROVAL_RECORD_TEMPLATE_FIELDS: Tuple[str, ...] = (
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
    "checksum_sha256",
    "paper_only",
    "production_ready",
)

# ---------------------------------------------------------------------------
# Required columns for the manual odds CSV template
# ---------------------------------------------------------------------------
MANUAL_ODDS_TEMPLATE_COLUMNS: Tuple[str, ...] = (
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

# ---------------------------------------------------------------------------
# P37 output filenames
# ---------------------------------------------------------------------------
P37_OUTPUT_FILES: Tuple[str, ...] = (
    "odds_approval_record_TEMPLATE.json",
    "odds_approval_record_INSTRUCTIONS.md",
    "odds_2024_approved_TEMPLATE.csv",
    "odds_2024_approved_COLUMN_GUIDE.md",
    "manual_odds_provisioning_gate.json",
    "manual_odds_provisioning_gate.md",
    "p37_gate_result.json",
)

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class P37ApprovalRecordTemplate:
    """Template structure for a manual odds approval record."""

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
    checksum_sha256: str
    paper_only: bool
    production_ready: bool


@dataclass(frozen=True)
class P37ManualOddsTemplate:
    """Specification for the manual odds CSV template."""

    required_columns: Tuple[str, ...]
    example_row_included: bool
    example_row_is_real_data: bool
    paper_only: bool
    production_ready: bool
    notes: str


@dataclass(frozen=True)
class P37ProvisioningChecklist:
    """Readiness checklist for P37 provisioning."""

    approval_record_exists: bool
    approval_record_valid: bool
    manual_odds_file_exists: bool
    manual_odds_schema_valid: bool
    raw_commit_risk_detected: bool
    paper_only: bool
    production_ready: bool
    raw_odds_commit_allowed: bool
    approval_record_commit_allowed: bool
    odds_artifact_ready: bool
    blocker_reason: str


@dataclass(frozen=True)
class P37ManualOddsProvisioningGate:
    """Gate metadata for P37."""

    gate: str
    approval_record_status: str
    manual_odds_file_status: str
    raw_commit_risk: bool
    templates_written: bool
    paper_only: bool
    production_ready: bool
    raw_odds_commit_allowed: bool
    approval_record_commit_allowed: bool
    odds_artifact_ready: bool
    blocker_reason: str
    recommended_next_action: str
    season: int


@dataclass
class P37GateResult:
    """Mutable gate result written to p37_gate_result.json."""

    gate: str
    approval_record_status: str
    manual_odds_file_status: str
    raw_commit_risk: bool
    templates_written: bool
    paper_only: bool = True
    production_ready: bool = False
    raw_odds_commit_allowed: bool = False
    approval_record_commit_allowed: bool = False
    odds_artifact_ready: bool = False
    blocker_reason: str = ""
    recommended_next_action: str = ""
    season: int = 2024
    artifacts: List[str] = field(default_factory=list)
    next_phase: str = "P38_BUILD_2024_LICENSED_ODDS_IMPORT_ARTIFACT"
    generated_at: str = ""
