"""P36 Odds Import Gate Planner.

Determines the P36 gate decision given approval and import validation results.
Writes all P36 output artifacts.

Gate priority (strict):
  1. contract violation (production_ready=True or paper_only=False)
  2. approval record missing → P36_BLOCKED_APPROVAL_RECORD_MISSING
  3. approval record invalid → P36_BLOCKED_APPROVAL_RECORD_INVALID
  4. internal research not allowed → P36_BLOCKED_LICENSE_NOT_ALLOWED_FOR_RESEARCH
  5. approval valid but odds source file missing → P36_BLOCKED_ODDS_SOURCE_NOT_PROVIDED
  6. all clear → P36_ODDS_APPROVAL_RECORD_READY

PAPER_ONLY=True, PRODUCTION_READY=False.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from wbc_backend.recommendation.p36_odds_approval_contract import (
    APPROVAL_BLOCKED_LICENSE,
    APPROVAL_BLOCKED_PROVENANCE,
    APPROVAL_INVALID,
    APPROVAL_MISSING,
    APPROVAL_READY,
    PAPER_ONLY,
    PRODUCTION_READY,
    SEASON,
    P36GateResult,
    P36OddsApprovalValidationResult,
)
from wbc_backend.recommendation.p36_odds_approval_contract import (
    P36_BLOCKED_APPROVAL_RECORD_INVALID,
    P36_BLOCKED_APPROVAL_RECORD_MISSING,
    P36_BLOCKED_CONTRACT_VIOLATION,
    P36_BLOCKED_LICENSE_NOT_ALLOWED_FOR_RESEARCH,
    P36_BLOCKED_ODDS_SOURCE_NOT_PROVIDED,
    P36_ODDS_APPROVAL_RECORD_READY,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Recommended next actions
# ---------------------------------------------------------------------------

_NEXT_ACTION_MISSING = (
    "Create an approval record JSON at data/mlb_2024/manual_import/odds_approval_record.json "
    "with all required fields filled in after reviewing the ToS of the chosen odds provider."
)
_NEXT_ACTION_INVALID = (
    "Fix the approval record: ensure all required fields are present and valid."
)
_NEXT_ACTION_LICENSE = (
    "Choose an odds provider that permits internal research use and update the approval record."
)
_NEXT_ACTION_NO_SOURCE = (
    "Provide the manually downloaded odds CSV at the path specified in source_file_expected_path "
    "in the approval record, then re-run P36."
)
_NEXT_ACTION_READY = (
    "Approval record is valid. Proceed to P37 to build the 2024 odds import artifact."
)
_NEXT_ACTION_CONTRACT = (
    "Correct the contract violation: paper_only must be True and production_ready must be False."
)


def build_odds_import_gate_plan(
    approval_validation: P36OddsApprovalValidationResult,
    manual_import_validation: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a gate plan dict summarising the P36 validation state."""
    return {
        "approval_status": approval_validation.approval_status,
        "approval_record_found": approval_validation.approval_record_found,
        "all_fields_present": approval_validation.all_required_fields_present,
        "internal_research_allowed": approval_validation.internal_research_allowed,
        "allowed_use_valid": approval_validation.allowed_use_valid,
        "approved_by_present": approval_validation.approved_by_present,
        "approved_at_present": approval_validation.approved_at_present,
        "source_file_path_present": approval_validation.source_file_path_present,
        "redistribution_allowed": approval_validation.redistribution_allowed,
        "redistribution_risk_note": approval_validation.redistribution_risk_note,
        "approval_blocker_reason": approval_validation.blocker_reason,
        "manual_import_file_provided": (
            manual_import_validation.get("file_provided", False)
            if manual_import_validation
            else False
        ),
        "manual_import_schema_valid": (
            manual_import_validation.get("schema_valid", False)
            if manual_import_validation
            else False
        ),
        "manual_import_overall_valid": (
            manual_import_validation.get("overall_valid", False)
            if manual_import_validation
            else False
        ),
        "paper_only": PAPER_ONLY,
        "production_ready": PRODUCTION_READY,
        "season": SEASON,
    }


def determine_p36_gate(plan: Dict[str, Any]) -> P36GateResult:
    """Apply gate priority rules and return a P36GateResult."""
    paper_only = plan.get("paper_only", True)
    prod_ready = plan.get("production_ready", False)

    # Priority 1: contract violation
    if prod_ready or not paper_only:
        return P36GateResult(
            gate=P36_BLOCKED_CONTRACT_VIOLATION,
            approval_record_status=plan.get("approval_status", ""),
            odds_source_status="unknown",
            internal_research_allowed=False,
            raw_odds_commit_allowed=False,
            blocker_reason="Contract violation: production_ready=True or paper_only=False.",
            recommended_next_action=_NEXT_ACTION_CONTRACT,
            paper_only=PAPER_ONLY,
            production_ready=PRODUCTION_READY,
            season=SEASON,
        )

    approval_status = plan.get("approval_status", APPROVAL_MISSING)

    # Priority 2: approval missing
    if approval_status == APPROVAL_MISSING:
        return P36GateResult(
            gate=P36_BLOCKED_APPROVAL_RECORD_MISSING,
            approval_record_status=APPROVAL_MISSING,
            odds_source_status="unknown",
            internal_research_allowed=False,
            raw_odds_commit_allowed=False,
            blocker_reason="No approval record provided.",
            recommended_next_action=_NEXT_ACTION_MISSING,
            paper_only=PAPER_ONLY,
            production_ready=PRODUCTION_READY,
            season=SEASON,
        )

    # Priority 3: approval invalid
    if approval_status == APPROVAL_INVALID:
        return P36GateResult(
            gate=P36_BLOCKED_APPROVAL_RECORD_INVALID,
            approval_record_status=APPROVAL_INVALID,
            odds_source_status="unknown",
            internal_research_allowed=False,
            raw_odds_commit_allowed=False,
            blocker_reason=plan.get("approval_blocker_reason", "Approval record is invalid."),
            recommended_next_action=_NEXT_ACTION_INVALID,
            paper_only=PAPER_ONLY,
            production_ready=PRODUCTION_READY,
            season=SEASON,
        )

    # Priority 4: license doesn't allow internal research
    if (
        approval_status in (APPROVAL_BLOCKED_LICENSE, APPROVAL_BLOCKED_PROVENANCE)
        or not plan.get("internal_research_allowed", False)
        or not plan.get("allowed_use_valid", False)
    ):
        return P36GateResult(
            gate=P36_BLOCKED_LICENSE_NOT_ALLOWED_FOR_RESEARCH,
            approval_record_status=approval_status,
            odds_source_status="blocked_license",
            internal_research_allowed=False,
            raw_odds_commit_allowed=False,
            blocker_reason=plan.get(
                "approval_blocker_reason",
                "License does not permit internal research.",
            ),
            recommended_next_action=_NEXT_ACTION_LICENSE,
            paper_only=PAPER_ONLY,
            production_ready=PRODUCTION_READY,
            season=SEASON,
        )

    # Priority 5: approval valid but no odds source file
    if not plan.get("manual_import_file_provided", False):
        return P36GateResult(
            gate=P36_BLOCKED_ODDS_SOURCE_NOT_PROVIDED,
            approval_record_status=approval_status,
            odds_source_status="source_not_provided",
            internal_research_allowed=True,
            raw_odds_commit_allowed=False,
            blocker_reason=(
                "Approval record is valid but no manual odds source file was provided."
            ),
            recommended_next_action=_NEXT_ACTION_NO_SOURCE,
            paper_only=PAPER_ONLY,
            production_ready=PRODUCTION_READY,
            season=SEASON,
        )

    # Priority 6: all clear
    return P36GateResult(
        gate=P36_ODDS_APPROVAL_RECORD_READY,
        approval_record_status=approval_status,
        odds_source_status="provided",
        internal_research_allowed=True,
        raw_odds_commit_allowed=False,  # redistribution risk — never commit raw odds
        blocker_reason="",
        recommended_next_action=_NEXT_ACTION_READY,
        paper_only=PAPER_ONLY,
        production_ready=PRODUCTION_READY,
        season=SEASON,
    )


def validate_p36_gate_plan(plan: Dict[str, Any]) -> bool:
    """Return True only if the plan passes all sanity guards."""
    if plan.get("production_ready", True):
        return False
    if not plan.get("paper_only", False):
        return False
    if plan.get("season") != SEASON:
        return False
    return True


def write_p36_outputs(
    output_dir: str,
    gate: P36GateResult,
    approval_validation: P36OddsApprovalValidationResult,
    odds_import_schema_dict: Dict[str, Any],
    manual_import_summary: Optional[Dict[str, Any]],
    gate_plan: Dict[str, Any],
) -> List[str]:
    """Write all P36 output files and return list of written file paths."""
    os.makedirs(output_dir, exist_ok=True)
    now_str = datetime.now(tz=timezone.utc).isoformat()
    gate.generated_at = now_str

    written: List[str] = []

    # 1. odds_approval_validation.json
    approval_dict: Dict[str, Any] = {
        "approval_status": approval_validation.approval_status,
        "approval_record_found": approval_validation.approval_record_found,
        "all_required_fields_present": approval_validation.all_required_fields_present,
        "internal_research_allowed": approval_validation.internal_research_allowed,
        "allowed_use_valid": approval_validation.allowed_use_valid,
        "approved_by_present": approval_validation.approved_by_present,
        "approved_at_present": approval_validation.approved_at_present,
        "source_file_path_present": approval_validation.source_file_path_present,
        "redistribution_allowed": approval_validation.redistribution_allowed,
        "redistribution_risk_note": approval_validation.redistribution_risk_note,
        "blocker_reason": approval_validation.blocker_reason,
        "missing_fields": list(approval_validation.missing_fields),
        "paper_only": approval_validation.paper_only,
        "production_ready": approval_validation.production_ready,
        "season": approval_validation.season,
        "generated_at": now_str,
    }
    p1 = _write_json(output_dir, "odds_approval_validation.json", approval_dict)
    written.append(p1)

    # 2. manual_odds_import_schema.json
    p2 = _write_json(output_dir, "manual_odds_import_schema.json", odds_import_schema_dict)
    written.append(p2)

    # 3. manual_odds_import_validation.json
    if manual_import_summary is None:
        manual_import_summary = {
            "file_provided": False,
            "status": "NO_FILE",
            "paper_only": PAPER_ONLY,
            "production_ready": PRODUCTION_READY,
            "season": SEASON,
        }
    manual_import_summary["generated_at"] = now_str
    p3 = _write_json(output_dir, "manual_odds_import_validation.json", manual_import_summary)
    written.append(p3)

    # 4. odds_import_gate_plan.json
    gate_plan["generated_at"] = now_str
    p4 = _write_json(output_dir, "odds_import_gate_plan.json", gate_plan)
    written.append(p4)

    # 5. odds_import_gate_plan.md
    p5 = _write_gate_plan_md(output_dir, gate, gate_plan, now_str)
    written.append(p5)

    # 6. p36_gate_result.json
    gate_dict: Dict[str, Any] = {
        "gate": gate.gate,
        "approval_record_status": gate.approval_record_status,
        "odds_source_status": gate.odds_source_status,
        "internal_research_allowed": gate.internal_research_allowed,
        "raw_odds_commit_allowed": gate.raw_odds_commit_allowed,
        "blocker_reason": gate.blocker_reason,
        "recommended_next_action": gate.recommended_next_action,
        "paper_only": gate.paper_only,
        "production_ready": gate.production_ready,
        "season": gate.season,
        "next_phase": gate.next_phase,
        "artifacts": [os.path.basename(p) for p in written],
        "generated_at": now_str,
    }
    p6 = _write_json(output_dir, "p36_gate_result.json", gate_dict)
    written.append(p6)

    return written


def _write_json(output_dir: str, filename: str, data: Dict[str, Any]) -> str:
    path = os.path.join(output_dir, filename)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
    return path


def _write_gate_plan_md(
    output_dir: str,
    gate: P36GateResult,
    plan: Dict[str, Any],
    now_str: str,
) -> str:
    path = os.path.join(output_dir, "odds_import_gate_plan.md")
    lines = [
        "# P36 Odds Import Gate Plan",
        "",
        f"**Generated**: {now_str}",
        f"**Gate**: `{gate.gate}`",
        f"**Approval Status**: `{gate.approval_record_status}`",
        f"**Odds Source**: `{gate.odds_source_status}`",
        f"**Internal Research Allowed**: {gate.internal_research_allowed}",
        f"**Raw Odds Commit Allowed**: {gate.raw_odds_commit_allowed} (always False)",
        f"**paper_only**: {gate.paper_only}",
        f"**production_ready**: {gate.production_ready}",
        "",
        "## Blocker Reason",
        "",
        gate.blocker_reason or "None",
        "",
        "## Recommended Next Action",
        "",
        gate.recommended_next_action,
        "",
        "## Redistribution Risk",
        "",
        plan.get("redistribution_risk_note", "N/A"),
        "",
        "## Next Phase",
        "",
        f"`{gate.next_phase}`",
    ]
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return path
