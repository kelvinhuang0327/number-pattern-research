"""
scripts/check_p37_manual_odds_package.py

P37.5 Manual Odds Package Checker

Checks whether the operator has placed the two required manual files:
  - data/mlb_2024/manual_import/odds_approval_record.json
  - data/mlb_2024/manual_import/odds_2024_approved.csv

If both exist, runs P37 validation logic in dry-run mode and reports results.
Writes a summary JSON to the processed output directory.

Exit codes:
  0 — Both files present and validation passed
  1 — Files missing or validation blocked
  2 — Unexpected error (import failure, IO error, etc.)

Usage:
  PYTHONPATH=. ./.venv/bin/python scripts/check_p37_manual_odds_package.py

Constraints:
  - Does NOT download, scrape, or fabricate any odds data.
  - Does NOT stage or commit any manual_import files.
  - PAPER_ONLY=True always enforced.
  - PRODUCTION_READY=False always enforced.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

# ──────────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────────

PAPER_ONLY: bool = True
PRODUCTION_READY: bool = False
SEASON: int = 2024

APPROVAL_RECORD_PATH = "data/mlb_2024/manual_import/odds_approval_record.json"
MANUAL_ODDS_PATH = "data/mlb_2024/manual_import/odds_2024_approved.csv"

OUTPUT_DIR = "data/mlb_2024/processed/p37_manual_odds_provisioning"
OUTPUT_JSON = "p37_5_manual_package_check.json"

P37_5_PACKAGE_READY = "P37_5_MANUAL_ODDS_APPROVAL_PACKAGE_READY"
P37_5_MISSING = "P37_5_MANUAL_ODDS_PACKAGE_MISSING"
P37_5_BLOCKED = "P37_5_MANUAL_ODDS_PACKAGE_BLOCKED"


# ──────────────────────────────────────────────────────────────────────────────
# Safety guard
# ──────────────────────────────────────────────────────────────────────────────

def _abort_if_contract_violated() -> None:
    """Abort if module-level guards are violated."""
    if not PAPER_ONLY or PRODUCTION_READY:
        print("FATAL: Contract violation — PAPER_ONLY must be True, PRODUCTION_READY must be False.")
        sys.exit(2)


# ──────────────────────────────────────────────────────────────────────────────
# File presence checks
# ──────────────────────────────────────────────────────────────────────────────

def check_file_presence(base_dir: str) -> Dict[str, bool]:
    """Return dict of {filename: exists_bool} for the two required manual files."""
    approval_path = os.path.join(base_dir, APPROVAL_RECORD_PATH)
    odds_path = os.path.join(base_dir, MANUAL_ODDS_PATH)
    return {
        "approval_record_exists": os.path.isfile(approval_path),
        "manual_odds_exists": os.path.isfile(odds_path),
        "approval_record_path": APPROVAL_RECORD_PATH,
        "manual_odds_path": MANUAL_ODDS_PATH,
    }


# ──────────────────────────────────────────────────────────────────────────────
# P37 validation dry-run
# ──────────────────────────────────────────────────────────────────────────────

def run_p37_validation_dry_run(base_dir: str, presence: Dict[str, Any]) -> Dict[str, Any]:
    """
    Call P37 check functions if both files are present.
    Returns a dict with validation results.
    Does NOT write gate outputs — dry-run only.
    """
    approval_path = os.path.join(base_dir, APPROVAL_RECORD_PATH)
    odds_path = os.path.join(base_dir, MANUAL_ODDS_PATH)

    try:
        from wbc_backend.recommendation.p37_manual_odds_provisioning_gate import (
            check_manual_approval_record,
            check_manual_odds_file,
        )
    except ImportError as exc:
        return {
            "dry_run_attempted": False,
            "error": f"Cannot import P37 gate module: {exc}",
        }

    approval_check = check_manual_approval_record(
        approval_path if presence["approval_record_exists"] else None
    )
    odds_check = check_manual_odds_file(
        odds_path if presence["manual_odds_exists"] else None
    )

    return {
        "dry_run_attempted": True,
        "approval_record_status": approval_check.get("approval_status", "UNKNOWN"),
        "approval_internal_research_allowed": approval_check.get("internal_research_allowed", False),
        "approval_allowed_use_valid": approval_check.get("allowed_use_valid", False),
        "approval_issues": approval_check.get("issues", []),
        "manual_odds_schema_valid": odds_check.get("schema_valid", False),
        "manual_odds_leakage_free": odds_check.get("leakage_free", False),
        "manual_odds_value_ranges_valid": odds_check.get("value_ranges_valid", False),
        "manual_odds_issues": odds_check.get("issues", []),
    }


# ──────────────────────────────────────────────────────────────────────────────
# Result building
# ──────────────────────────────────────────────────────────────────────────────

def build_result(
    presence: Dict[str, Any],
    validation: Dict[str, Any],
    status: str,
    exit_code: int,
    base_dir: str,
) -> Dict[str, Any]:
    return {
        "p37_5_status": status,
        "paper_only": PAPER_ONLY,
        "production_ready": PRODUCTION_READY,
        "raw_odds_commit_allowed": False,
        "season": SEASON,
        "approval_record_exists": presence["approval_record_exists"],
        "manual_odds_exists": presence["manual_odds_exists"],
        "approval_record_path": APPROVAL_RECORD_PATH,
        "manual_odds_path": MANUAL_ODDS_PATH,
        "validation": validation,
        "exit_code": exit_code,
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "next_action": (
            "Both files validated — run full P37 gate to confirm READY."
            if status == P37_5_PACKAGE_READY
            else "Provision both manual files at data/mlb_2024/manual_import/ "
                 "per the P37.5 Operator Checklist and Runbook."
        ),
    }


# ──────────────────────────────────────────────────────────────────────────────
# Output writing
# ──────────────────────────────────────────────────────────────────────────────

def write_output(base_dir: str, result: Dict[str, Any]) -> str:
    """Write the check result JSON to the processed output directory."""
    out_dir = Path(base_dir) / OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / OUTPUT_JSON
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, ensure_ascii=False)
    return str(out_path)


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main() -> int:
    _abort_if_contract_violated()

    base_dir = os.getcwd()

    # ── Step 1: Check file presence ──────────────────────────────────────────
    presence = check_file_presence(base_dir)

    approval_exists = presence["approval_record_exists"]
    odds_exists = presence["manual_odds_exists"]

    if approval_exists:
        print(f"APPROVAL_RECORD_EXISTS: {APPROVAL_RECORD_PATH}")
    else:
        print(f"MISSING: {APPROVAL_RECORD_PATH}")

    if odds_exists:
        print(f"MANUAL_ODDS_EXISTS: {MANUAL_ODDS_PATH}")
    else:
        print(f"MISSING: {MANUAL_ODDS_PATH}")

    # ── Step 2: If neither file exists, exit early ────────────────────────────
    if not approval_exists and not odds_exists:
        print("STATUS: Both manual files missing.")
        print("ACTION: Provision both files per docs/betting/manual_odds_approval/P37_5_OPERATOR_CHECKLIST.md")
        result = build_result(presence, {"dry_run_attempted": False}, P37_5_MISSING, 1, base_dir)
        try:
            out_path = write_output(base_dir, result)
            print(f"OUTPUT: {out_path}")
        except Exception as write_exc:
            print(f"WARNING: Could not write output JSON: {write_exc}")
        return 1

    # ── Step 3: Partial or both present — run validation ─────────────────────
    print("Running P37 validation dry-run...")
    validation = run_p37_validation_dry_run(base_dir, presence)

    if not validation.get("dry_run_attempted"):
        print(f"ERROR: {validation.get('error', 'Unknown import error')}")
        return 2

    # ── Step 4: Determine overall status ─────────────────────────────────────
    approval_ok = (
        approval_exists
        and validation.get("approval_record_status") == "APPROVAL_READY"
        and validation.get("approval_internal_research_allowed")
        and validation.get("approval_allowed_use_valid")
        and not validation.get("approval_issues")
    )
    odds_ok = (
        odds_exists
        and validation.get("manual_odds_schema_valid")
        and validation.get("manual_odds_leakage_free")
        and validation.get("manual_odds_value_ranges_valid")
        and not validation.get("manual_odds_issues")
    )

    if approval_ok and odds_ok:
        status = P37_5_PACKAGE_READY
        exit_code = 0
    else:
        status = P37_5_BLOCKED
        exit_code = 1

    # ── Step 5: Print validation summary ─────────────────────────────────────
    print(f"approval_record_status={validation.get('approval_record_status', 'N/A')}")
    print(f"approval_internal_research_allowed={validation.get('approval_internal_research_allowed', False)}")
    print(f"manual_odds_schema_valid={validation.get('manual_odds_schema_valid', False)}")
    print(f"manual_odds_leakage_free={validation.get('manual_odds_leakage_free', False)}")
    print(f"manual_odds_value_ranges_valid={validation.get('manual_odds_value_ranges_valid', False)}")

    if validation.get("approval_issues"):
        for issue in validation["approval_issues"]:
            print(f"  approval_issue: {issue}")

    if validation.get("manual_odds_issues"):
        for issue in validation["manual_odds_issues"]:
            print(f"  odds_issue: {issue}")

    print(f"p37_5_status={status}")
    print(f"EXIT_CODE={exit_code}")

    # ── Step 6: Write output JSON ─────────────────────────────────────────────
    result = build_result(presence, validation, status, exit_code, base_dir)
    try:
        out_path = write_output(base_dir, result)
        print(f"OUTPUT: {out_path}")
    except Exception as write_exc:
        print(f"WARNING: Could not write output JSON: {write_exc}")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
