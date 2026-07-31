"""P36 Odds Approval Record Validator.

Validates a manually provided approval record for 2024 historical odds import.
PAPER_ONLY=True, PRODUCTION_READY=False.

Rules:
- If no approval record path provided → APPROVAL_MISSING
- internal_research_allowed must be True
- allowed_use must include "internal_research"
- approved_by must be non-empty
- approved_at must be non-empty
- source_file_expected_path must be non-empty
- production_ready must be False
- paper_only must be True
- Redistribution risk surfaced if redistribution_allowed=False
  (does not block internal use, but raw odds must not be committed)
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from wbc_backend.recommendation.p36_odds_approval_contract import (
    APPROVAL_BLOCKED_LICENSE,
    APPROVAL_BLOCKED_PROVENANCE,
    APPROVAL_INVALID,
    APPROVAL_MISSING,
    APPROVAL_READY,
    APPROVAL_RECORD_REQUIRED_FIELDS,
    APPROVAL_REQUIRES_LEGAL_REVIEW,
    PAPER_ONLY,
    PRODUCTION_READY,
    SEASON,
    P36OddsApprovalRecord,
    P36OddsApprovalValidationResult,
)

logger = logging.getLogger(__name__)

# Allowed values for `allowed_use` that permit internal research
_ALLOWED_USE_RESEARCH_VALUES: Tuple[str, ...] = (
    "internal_research",
    "research",
    "personal_research",
    "academic_research",
)


def load_approval_record(path: Optional[str]) -> Optional[Dict[str, Any]]:
    """Load approval record JSON from *path*.

    Returns None if path is None or file does not exist / is malformed.
    """
    if path is None:
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            logger.warning("Approval record at %s is not a JSON object", path)
            return None
        return data
    except FileNotFoundError:
        logger.warning("Approval record file not found: %s", path)
        return None
    except json.JSONDecodeError as exc:
        logger.warning("Approval record JSON malformed at %s: %s", path, exc)
        return None


def _find_missing_fields(record: Dict[str, Any]) -> List[str]:
    return [f for f in APPROVAL_RECORD_REQUIRED_FIELDS if f not in record]


def validate_approval_record(
    record: Optional[Dict[str, Any]],
) -> Tuple[bool, str, List[str]]:
    """Check that all required fields are present.

    Returns (valid, reason, missing_fields).
    """
    if record is None:
        return False, "No approval record provided.", list(APPROVAL_RECORD_REQUIRED_FIELDS)

    missing = _find_missing_fields(record)
    if missing:
        return (
            False,
            f"Approval record missing required fields: {missing}",
            missing,
        )
    return True, "All required fields present.", []


def validate_allowed_use(record: Dict[str, Any]) -> Tuple[bool, str]:
    """Check allowed_use permits internal research.

    Returns (valid, reason).
    """
    allowed_use = str(record.get("allowed_use", "")).lower().strip()
    for permitted in _ALLOWED_USE_RESEARCH_VALUES:
        if permitted in allowed_use:
            return True, f"allowed_use '{allowed_use}' permits internal research."
    return (
        False,
        f"allowed_use '{allowed_use}' does not permit internal research. "
        f"Must include one of: {_ALLOWED_USE_RESEARCH_VALUES}",
    )


def validate_redistribution_policy(record: Dict[str, Any]) -> Tuple[bool, str]:
    """Surface redistribution risk.

    Redistribution disallowed does NOT block internal research use, but
    MUST prevent committing raw odds files to the repo.

    Returns (redistribution_allowed, note).
    """
    redistribution_allowed = bool(record.get("redistribution_allowed", False))
    if not redistribution_allowed:
        note = (
            "Redistribution is NOT allowed. Raw odds files must NEVER be "
            "committed to the repository. Internal research use is still permitted."
        )
    else:
        note = "Redistribution is allowed per approval record."
    return redistribution_allowed, note


def validate_required_approver(record: Dict[str, Any]) -> Tuple[bool, str]:
    """Check approved_by, approved_at, and source_file_expected_path are non-empty.

    Returns (valid, reason).
    """
    issues: List[str] = []
    if not str(record.get("approved_by", "")).strip():
        issues.append("approved_by is empty")
    if not str(record.get("approved_at", "")).strip():
        issues.append("approved_at is empty")
    if not str(record.get("source_file_expected_path", "")).strip():
        issues.append("source_file_expected_path is empty")
    if issues:
        return False, f"Approver validation failed: {'; '.join(issues)}"
    return True, "Approver, approval date, and source file path all present."


def _determine_approval_status(
    record_present: bool,
    fields_valid: bool,
    allowed_use_valid: bool,
    internal_research_allowed: bool,
    approver_valid: bool,
    paper_only_in_record: bool,
    production_ready_in_record: bool,
) -> Tuple[str, str]:
    """Return (status, reason) based on validation results."""
    if not record_present:
        return APPROVAL_MISSING, "No approval record was provided."
    if not fields_valid:
        return APPROVAL_INVALID, "Approval record is missing required fields."
    if not approver_valid:
        return APPROVAL_INVALID, "Approval record has missing approver/date/path."
    if not paper_only_in_record:
        return APPROVAL_BLOCKED_PROVENANCE, "Approval record has paper_only=False — not permitted."
    if production_ready_in_record:
        return APPROVAL_BLOCKED_PROVENANCE, "Approval record has production_ready=True — not permitted."
    if not internal_research_allowed:
        return APPROVAL_BLOCKED_LICENSE, "internal_research_allowed=False in approval record."
    if not allowed_use_valid:
        return (
            APPROVAL_BLOCKED_LICENSE,
            "allowed_use does not permit internal research.",
        )
    return APPROVAL_READY, "Approval record is valid and permits internal research."


def summarize_approval_validation(
    record: Optional[Dict[str, Any]],
) -> P36OddsApprovalValidationResult:
    """Run all approval validations and return a consolidated result.

    This function always enforces PAPER_ONLY=True and PRODUCTION_READY=False
    regardless of the contents of the approval record.
    """
    record_present = record is not None

    # Field completeness
    fields_valid, fields_reason, missing_fields = validate_approval_record(record)

    # Per-field checks (only meaningful when record present)
    if record_present and fields_valid:
        allowed_use_valid, _au_reason = validate_allowed_use(record)
        redistribution_allowed, redistrib_note = validate_redistribution_policy(record)
        approver_valid, _approver_reason = validate_required_approver(record)
        internal_research_allowed = bool(record.get("internal_research_allowed", False))
        paper_only_in_record = bool(record.get("paper_only", False))
        production_ready_in_record = bool(record.get("production_ready", False))
        approved_by_present = bool(str(record.get("approved_by", "")).strip())
        approved_at_present = bool(str(record.get("approved_at", "")).strip())
        source_file_present = bool(str(record.get("source_file_expected_path", "")).strip())
    else:
        allowed_use_valid = False
        redistribution_allowed = False
        redistrib_note = "No approval record — redistribution status unknown."
        approver_valid = False
        internal_research_allowed = False
        paper_only_in_record = True  # default safe
        production_ready_in_record = False  # default safe
        approved_by_present = False
        approved_at_present = False
        source_file_present = False

    status, blocker_reason = _determine_approval_status(
        record_present=record_present,
        fields_valid=fields_valid,
        allowed_use_valid=allowed_use_valid,
        internal_research_allowed=internal_research_allowed,
        approver_valid=approver_valid,
        paper_only_in_record=paper_only_in_record,
        production_ready_in_record=production_ready_in_record,
    )

    return P36OddsApprovalValidationResult(
        approval_status=status,
        approval_record_found=record_present,
        all_required_fields_present=fields_valid,
        internal_research_allowed=internal_research_allowed,
        allowed_use_valid=allowed_use_valid,
        approved_by_present=approved_by_present,
        approved_at_present=approved_at_present,
        source_file_path_present=source_file_present,
        paper_only=PAPER_ONLY,
        production_ready=PRODUCTION_READY,
        redistribution_allowed=redistribution_allowed,
        redistribution_risk_note=redistrib_note,
        blocker_reason=blocker_reason,
        missing_fields=tuple(missing_fields),
        season=SEASON,
    )
