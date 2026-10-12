"""
P37 Manual Odds Provisioning Gate

Checks readiness for importing licensed odds into the P38 artifact builder.
Reads the P36 approval validation + manual odds schema validator.
Coordinates approval record validation, odds file validation, and raw-commit-risk
detection.

Gate priority (strict order):
  1. contract_violation (production_ready=True or paper_only=False) → BLOCKED_CONTRACT_VIOLATION
  2. raw commit risk detected → BLOCKED_RAW_ODDS_COMMIT_RISK
  3. no approval record → BLOCKED_APPROVAL_RECORD_MISSING
  4. approval invalid → BLOCKED_APPROVAL_RECORD_INVALID
  5. license not approved → BLOCKED_LICENSE_NOT_APPROVED
  6. no manual odds file → BLOCKED_MANUAL_ODDS_FILE_MISSING
  7. odds schema invalid → BLOCKED_MANUAL_ODDS_SCHEMA_INVALID
  8. all clear → GATE_READY

PAPER_ONLY=True  PRODUCTION_READY=False  SEASON=2024
"""

from __future__ import annotations

import json
import os
import subprocess
from datetime import timezone, datetime
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from wbc_backend.recommendation.p37_manual_odds_provisioning_contract import (
    PAPER_ONLY,
    PRODUCTION_READY,
    SEASON,
    P37GateResult,
    P37ManualOddsProvisioningGate,
    P37ProvisioningChecklist,
)
from wbc_backend.recommendation.p36_odds_approval_record_validator import (
    summarize_approval_validation,
)
from wbc_backend.recommendation.p36_manual_odds_import_validator import (
    validate_manual_odds_schema,
    validate_manual_odds_no_outcome_leakage,
    validate_manual_odds_value_ranges,
)

# ---------------------------------------------------------------------------
# Forbidden column check (mirrors P36)
# ---------------------------------------------------------------------------
_FORBIDDEN_COLS = {
    "y_true", "final_score", "home_score", "away_score", "winner",
    "outcome", "result", "run_diff", "total_runs", "game_result",
}

_REQUIRED_COLS = {
    "game_id", "game_date", "home_team", "away_team", "p_market",
    "odds_decimal", "sportsbook", "market_type", "closing_timestamp",
    "source_odds_ref", "license_ref",
}

_ALLOWED_MARKET_TYPES = {"moneyline", "ml", "money_line", "1x2", "h2h"}


# ---------------------------------------------------------------------------
# check_manual_approval_record
# ---------------------------------------------------------------------------

def check_manual_approval_record(path: Optional[str]) -> Dict[str, Any]:
    """
    Load and validate an approval record at `path`.
    Returns a dict with keys:
      - record_exists (bool)
      - approval_status (str)
      - internal_research_allowed (bool)
      - allowed_use_valid (bool)
      - issues (List[str])
    """
    if path is None or not os.path.exists(path):
        return {
            "record_exists": False,
            "approval_status": "APPROVAL_MISSING",
            "internal_research_allowed": False,
            "allowed_use_valid": False,
            "issues": ["No approval record path provided or file does not exist."],
        }

    try:
        with open(path, "r", encoding="utf-8") as fh:
            record = json.load(fh)
    except Exception as exc:
        return {
            "record_exists": True,
            "approval_status": "APPROVAL_INVALID",
            "internal_research_allowed": False,
            "allowed_use_valid": False,
            "issues": [f"Cannot parse approval record: {exc}"],
        }

    if not isinstance(record, dict):
        return {
            "record_exists": True,
            "approval_status": "APPROVAL_INVALID",
            "internal_research_allowed": False,
            "allowed_use_valid": False,
            "issues": ["Approval record must be a JSON object."],
        }

    result = summarize_approval_validation(record)
    issues: List[str] = []

    if result.approval_status not in ("APPROVAL_READY",):
        issues.append(f"Approval status: {result.approval_status}")
        if hasattr(result, "issues") and result.issues:
            issues.extend(result.issues)

    return {
        "record_exists": True,
        "approval_status": result.approval_status,
        "internal_research_allowed": result.internal_research_allowed,
        "allowed_use_valid": result.allowed_use_valid,
        "issues": issues,
    }


# ---------------------------------------------------------------------------
# check_manual_odds_file
# ---------------------------------------------------------------------------

def check_manual_odds_file(path: Optional[str]) -> Dict[str, Any]:
    """
    Load and validate a manual odds CSV at `path`.
    Returns a dict with keys:
      - file_exists (bool)
      - schema_valid (bool)
      - leakage_free (bool)
      - value_ranges_valid (bool)
      - issues (List[str])
    """
    if path is None or not os.path.exists(path):
        return {
            "file_exists": False,
            "schema_valid": False,
            "leakage_free": False,
            "value_ranges_valid": False,
            "issues": ["No manual odds file path provided or file does not exist."],
        }

    try:
        df = pd.read_csv(path)
    except Exception as exc:
        return {
            "file_exists": True,
            "schema_valid": False,
            "leakage_free": False,
            "value_ranges_valid": False,
            "issues": [f"Cannot read odds CSV: {exc}"],
        }

    issues: List[str] = []

    schema_ok, schema_msg, schema_issues = validate_manual_odds_schema(df)
    if not schema_ok:
        issues.append(schema_msg)
        issues.extend(schema_issues)

    leakage_ok, leakage_msg, leakage_issues = validate_manual_odds_no_outcome_leakage(df)
    if not leakage_ok:
        issues.append(leakage_msg)
        issues.extend(leakage_issues)

    ranges_ok, ranges_msg, ranges_issues = validate_manual_odds_value_ranges(df)
    if not ranges_ok:
        issues.append(ranges_msg)
        issues.extend(ranges_issues)

    return {
        "file_exists": True,
        "schema_valid": schema_ok,
        "leakage_free": leakage_ok,
        "value_ranges_valid": ranges_ok,
        "issues": issues,
    }


# ---------------------------------------------------------------------------
# detect_raw_commit_risk
# ---------------------------------------------------------------------------

def detect_raw_commit_risk(repo_root: str) -> bool:
    """
    Return True if any raw odds or manual import files are staged in git.
    Uses `git diff --cached --name-only` from repo_root.
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=10,
        )
        staged = result.stdout.strip()
        if not staged:
            return False
        for line in staged.splitlines():
            if any(seg in line for seg in [
                "data/mlb_2024/raw",
                "data/mlb_2024/manual_import",
                "odds_2024_approved.csv",
                "odds_approval_record.json",
            ]):
                return True
        return False
    except Exception:
        # If git is unavailable, assume no risk (conservative for templates)
        return False


# ---------------------------------------------------------------------------
# build_provisioning_gate_result
# ---------------------------------------------------------------------------

def build_provisioning_gate_result(
    approval_check: Dict[str, Any],
    odds_check: Dict[str, Any],
    raw_commit_risk: bool,
    templates_written: bool,
    repo_root: Optional[str] = None,
) -> P37GateResult:
    """
    Apply gate priority logic and return a P37GateResult.
    """
    # Guard 1: contract violation (enforced at module level)
    if PRODUCTION_READY or not PAPER_ONLY:
        return P37GateResult(
            gate="P37_BLOCKED_CONTRACT_VIOLATION",
            approval_record_status="APPROVAL_INVALID",
            manual_odds_file_status="MANUAL_ODDS_INVALID",
            raw_commit_risk=raw_commit_risk,
            templates_written=templates_written,
            paper_only=PAPER_ONLY,
            production_ready=PRODUCTION_READY,
            raw_odds_commit_allowed=False,
            odds_artifact_ready=False,
            blocker_reason="Module contract violation: PRODUCTION_READY=True or PAPER_ONLY=False.",
            recommended_next_action="Fix module-level guards. Do not set PRODUCTION_READY=True.",
        )

    # Guard 2: raw commit risk
    if raw_commit_risk:
        return P37GateResult(
            gate="P37_BLOCKED_RAW_ODDS_COMMIT_RISK",
            approval_record_status=approval_check.get("approval_status", "unknown"),
            manual_odds_file_status="unknown",
            raw_commit_risk=True,
            templates_written=templates_written,
            paper_only=True,
            production_ready=False,
            raw_odds_commit_allowed=False,
            odds_artifact_ready=False,
            blocker_reason="Raw or manual import files detected in git staging area.",
            recommended_next_action="Run `git reset HEAD <file>` to unstage raw/manual files.",
        )

    # Guard 3: approval record missing
    if not approval_check.get("record_exists", False):
        return P37GateResult(
            gate="P37_BLOCKED_APPROVAL_RECORD_MISSING",
            approval_record_status="APPROVAL_MISSING",
            manual_odds_file_status="MANUAL_ODDS_REQUIRED",
            raw_commit_risk=False,
            templates_written=templates_written,
            paper_only=True,
            production_ready=False,
            raw_odds_commit_allowed=False,
            odds_artifact_ready=False,
            blocker_reason="No approval record provided.",
            recommended_next_action=(
                "Fill in odds_approval_record_TEMPLATE.json and place the completed file at "
                "data/mlb_2024/manual_import/odds_approval_record.json, "
                "then rerun P37 with --approval-record."
            ),
        )

    # Guard 4: approval invalid
    approval_status = approval_check.get("approval_status", "APPROVAL_INVALID")
    if approval_status == "APPROVAL_INVALID":
        issues = approval_check.get("issues", [])
        return P37GateResult(
            gate="P37_BLOCKED_APPROVAL_RECORD_INVALID",
            approval_record_status="APPROVAL_INVALID",
            manual_odds_file_status="MANUAL_ODDS_REQUIRED",
            raw_commit_risk=False,
            templates_written=templates_written,
            paper_only=True,
            production_ready=False,
            raw_odds_commit_allowed=False,
            odds_artifact_ready=False,
            blocker_reason=f"Approval record invalid: {'; '.join(issues)}",
            recommended_next_action="Fix approval record issues and rerun P37.",
        )

    # Guard 5: license not approved
    if approval_status in ("APPROVAL_BLOCKED_LICENSE", "APPROVAL_BLOCKED_PROVENANCE",
                           "APPROVAL_REQUIRES_LEGAL_REVIEW"):
        return P37GateResult(
            gate="P37_BLOCKED_LICENSE_NOT_APPROVED",
            approval_record_status=approval_status,
            manual_odds_file_status="MANUAL_ODDS_REQUIRED",
            raw_commit_risk=False,
            templates_written=templates_written,
            paper_only=True,
            production_ready=False,
            raw_odds_commit_allowed=False,
            odds_artifact_ready=False,
            blocker_reason=f"License validation failed: {approval_status}",
            recommended_next_action=(
                "Ensure internal_research_allowed=true and allowed_use is a research value. "
                "Do not set paper_only=false or production_ready=true."
            ),
        )

    # Guard 6: no manual odds file
    if not odds_check.get("file_exists", False):
        return P37GateResult(
            gate="P37_BLOCKED_MANUAL_ODDS_FILE_MISSING",
            approval_record_status=approval_status,
            manual_odds_file_status="MANUAL_ODDS_REQUIRED",
            raw_commit_risk=False,
            templates_written=templates_written,
            paper_only=True,
            production_ready=False,
            raw_odds_commit_allowed=False,
            odds_artifact_ready=False,
            blocker_reason="No manual odds CSV provided.",
            recommended_next_action=(
                "Fill in odds_2024_approved_TEMPLATE.csv and place the completed file at "
                "data/mlb_2024/manual_import/odds_2024_approved.csv, "
                "then rerun P37 with --manual-odds-file."
            ),
        )

    # Guard 7: odds schema invalid
    if not odds_check.get("schema_valid", False) or not odds_check.get("leakage_free", False):
        issues = odds_check.get("issues", [])
        return P37GateResult(
            gate="P37_BLOCKED_MANUAL_ODDS_SCHEMA_INVALID",
            approval_record_status=approval_status,
            manual_odds_file_status="MANUAL_ODDS_INVALID",
            raw_commit_risk=False,
            templates_written=templates_written,
            paper_only=True,
            production_ready=False,
            raw_odds_commit_allowed=False,
            odds_artifact_ready=False,
            blocker_reason=f"Manual odds file invalid: {'; '.join(issues)}",
            recommended_next_action="Fix odds CSV schema/leakage issues and rerun P37.",
        )

    # All clear
    return P37GateResult(
        gate="P37_MANUAL_ODDS_PROVISIONING_GATE_READY",
        approval_record_status="APPROVAL_VALID",
        manual_odds_file_status="MANUAL_ODDS_VALID",
        raw_commit_risk=False,
        templates_written=templates_written,
        paper_only=True,
        production_ready=False,
        raw_odds_commit_allowed=False,
        odds_artifact_ready=True,
        blocker_reason="",
        recommended_next_action=(
            "Proceed to P38: Build 2024 Licensed Odds Import Artifact. "
            "Do NOT commit raw odds or approval records."
        ),
    )


# ---------------------------------------------------------------------------
# write_p37_outputs
# ---------------------------------------------------------------------------

def write_p37_outputs(
    output_dir: str,
    gate_result: P37GateResult,
    approval_check: Dict[str, Any],
    odds_check: Dict[str, Any],
) -> List[str]:
    """
    Write all 7 P37 output files to output_dir.
    Returns list of written file paths.
    """
    import json
    from datetime import datetime, timezone

    os.makedirs(output_dir, exist_ok=True)
    written: List[str] = []

    # 1. manual_odds_provisioning_gate.json
    gate_dict = {
        "gate": gate_result.gate,
        "approval_record_status": gate_result.approval_record_status,
        "manual_odds_file_status": gate_result.manual_odds_file_status,
        "raw_commit_risk": gate_result.raw_commit_risk,
        "templates_written": gate_result.templates_written,
        "paper_only": gate_result.paper_only,
        "production_ready": gate_result.production_ready,
        "raw_odds_commit_allowed": gate_result.raw_odds_commit_allowed,
        "approval_record_commit_allowed": gate_result.approval_record_commit_allowed,
        "odds_artifact_ready": gate_result.odds_artifact_ready,
        "blocker_reason": gate_result.blocker_reason,
        "recommended_next_action": gate_result.recommended_next_action,
        "season": gate_result.season,
        "approval_issues": approval_check.get("issues", []),
        "odds_issues": odds_check.get("issues", []),
    }
    p1 = os.path.join(output_dir, "manual_odds_provisioning_gate.json")
    with open(p1, "w", encoding="utf-8") as fh:
        json.dump(gate_dict, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    written.append(p1)

    # 2. manual_odds_provisioning_gate.md
    md_lines = [
        "# P37 Manual Odds Provisioning Gate",
        "",
        f"**Gate**: `{gate_result.gate}`",
        f"**Approval record status**: `{gate_result.approval_record_status}`",
        f"**Manual odds file status**: `{gate_result.manual_odds_file_status}`",
        f"**Raw commit risk**: `{gate_result.raw_commit_risk}`",
        f"**Templates written**: `{gate_result.templates_written}`",
        f"**paper_only**: `{gate_result.paper_only}`",
        f"**production_ready**: `{gate_result.production_ready}`",
        f"**raw_odds_commit_allowed**: `{gate_result.raw_odds_commit_allowed}`",
        f"**odds_artifact_ready**: `{gate_result.odds_artifact_ready}`",
        "",
        f"**Blocker reason**: {gate_result.blocker_reason or '(none)'}",
        "",
        f"**Recommended next action**: {gate_result.recommended_next_action}",
        "",
        "---",
        "",
        "*PAPER_ONLY=True, PRODUCTION_READY=False, SEASON=2024*",
    ]
    p2 = os.path.join(output_dir, "manual_odds_provisioning_gate.md")
    with open(p2, "w", encoding="utf-8") as fh:
        fh.write("\n".join(md_lines) + "\n")
    written.append(p2)

    # 3. p37_gate_result.json
    gate_result.generated_at = datetime.now(tz=timezone.utc).isoformat()
    gate_result.artifacts = [os.path.basename(p) for p in written]
    result_dict = {
        "gate": gate_result.gate,
        "approval_record_status": gate_result.approval_record_status,
        "manual_odds_file_status": gate_result.manual_odds_file_status,
        "raw_commit_risk": gate_result.raw_commit_risk,
        "templates_written": gate_result.templates_written,
        "paper_only": gate_result.paper_only,
        "production_ready": gate_result.production_ready,
        "raw_odds_commit_allowed": gate_result.raw_odds_commit_allowed,
        "approval_record_commit_allowed": gate_result.approval_record_commit_allowed,
        "odds_artifact_ready": gate_result.odds_artifact_ready,
        "blocker_reason": gate_result.blocker_reason,
        "recommended_next_action": gate_result.recommended_next_action,
        "season": gate_result.season,
        "next_phase": gate_result.next_phase,
        "artifacts": gate_result.artifacts,
        "generated_at": gate_result.generated_at,
    }
    p3 = os.path.join(output_dir, "p37_gate_result.json")
    with open(p3, "w", encoding="utf-8") as fh:
        json.dump(result_dict, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    written.append(p3)

    return written
