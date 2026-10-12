"""P35 Odds License / Provenance Validator

Validates whether the odds acquisition path identified in P34 has:
1. An approved license record
2. A valid provenance statement
3. A schema compatible with the P34 odds import template

HARD GUARDS:
- Do NOT access or scrape any sportsbook website.
- Do NOT mark any odds source as ready without an approval record.
- Do NOT use unclear-license odds data in any computation.
- PAPER_ONLY = True always.
- PRODUCTION_READY = False always.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from wbc_backend.recommendation.p35_dual_source_import_validation_contract import (
    LICENSE_APPROVED_INTERNAL_RESEARCH,
    LICENSE_BLOCKED_NOT_APPROVED,
    LICENSE_REVIEW_REQUIRED,
    LICENSE_UNKNOWN,
    ODDS_REQUIRED_COLUMNS,
    PAPER_ONLY,
    PRODUCTION_READY,
    VALIDATION_BLOCKED_LICENSE,
    VALIDATION_BLOCKED_SOURCE_MISSING,
    VALIDATION_BLOCKED_SCHEMA,
    VALIDATION_READY_FOR_IMPLEMENTATION,
    VALIDATION_REQUIRES_MANUAL_APPROVAL,
    P35_BLOCKED_ODDS_LICENSE_NOT_APPROVED,
    P35_BLOCKED_ODDS_SOURCE_NOT_PROVIDED,
    P35OddsLicenseValidationResult,
    P35OddsImportValidationPlan,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Required approval record fields
# ---------------------------------------------------------------------------

REQUIRED_APPROVAL_FIELDS: Tuple[str, ...] = (
    "provider_name",
    "license_terms_summary",
    "allowed_use",
    "redistribution_allowed",
    "attribution_required",
    "approved_by",
    "approved_at",
)

APPROVED_USE_VALUES: Tuple[str, ...] = (
    "internal_research",
    "research",
    "personal_research",
)

# Known odds sources referenced in P34
KNOWN_ODDS_SOURCES: Tuple[Dict[str, str], ...] = (
    {
        "option_id": "odds_r01",
        "source_name": "sportsbookreviewsonline.com",
        "source_url": "https://www.sportsbookreviewsonline.com/scoresoddsarchives/mlb/",
        "license_note": "Freely downloadable historical archives; ToS requires verification before use.",
    },
    {
        "option_id": "odds_r02",
        "source_name": "The Odds API",
        "source_url": "https://the-odds-api.com/",
        "license_note": "Paid subscription; internal research use permitted under paid tier.",
    },
)


# ---------------------------------------------------------------------------
# Loader functions
# ---------------------------------------------------------------------------


def load_p34_odds_options(path: str) -> List[Dict[str, Any]]:
    """Load odds acquisition options from P34 output JSON.

    Returns empty list if file is missing or malformed.
    """
    if not path or not os.path.isfile(path):
        logger.warning("P34 odds options file not found: %s", path)
        return []
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        opts = data.get("options", [])
        if not isinstance(opts, list):
            logger.warning("P34 odds options 'options' key is not a list")
            return []
        return opts
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to load P34 odds options: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Checklist builder
# ---------------------------------------------------------------------------


def build_odds_license_checklist(odds_options: List[Dict[str, Any]]) -> List[str]:
    """Build a license validation checklist from P34 odds options.

    Returns a list of checklist item strings describing what must be done
    before each odds source can be used.
    """
    checklist: List[str] = [
        "Confirm ToS permits internal research use without redistribution.",
        "Confirm data may be downloaded manually (no automated scraping).",
        "Confirm attribution is required and format is understood.",
        "Confirm redistribution policy (paper_only, no public sharing).",
        "Confirm data covers 2024 MLB season (April–October).",
        "Confirm American moneyline → decimal odds conversion is correct.",
        "Confirm game_id alignment with P32 Retrosheet spine.",
        "Confirm closing moneyline timestamp is pre-game.",
        "Confirm no outcome information is embedded in odds record.",
        "Record all approvals in a machine-readable approval_record.json.",
    ]
    # Add source-specific items from P34 options
    for opt in odds_options:
        option_id = opt.get("option_id", "unknown")
        source_name = opt.get("source_name", "")
        if "sportsbookreviewsonline" in source_name.lower():
            checklist.append(
                f"[{option_id}] Manually download Excel archives for each month of 2024 MLB season."
            )
        elif "odds api" in source_name.lower() or "odds_api" in source_name.lower():
            checklist.append(
                f"[{option_id}] Confirm paid API subscription is active and covers 2024 historical data."
            )
    return checklist


# ---------------------------------------------------------------------------
# Approval record validator
# ---------------------------------------------------------------------------


def validate_manual_odds_source_approval(
    approval_record_path: Optional[str] = None,
) -> Tuple[bool, str, Dict[str, Any]]:
    """Validate the manual odds source approval record.

    Parameters
    ----------
    approval_record_path:
        Optional path to a JSON approval record file. If None or file does
        not exist, validation fails with BLOCKED_LICENSE.

    Returns
    -------
    (approved: bool, reason: str, record: dict)
        approved — True only if all required fields are present and valid.
        reason   — Human-readable explanation.
        record   — Loaded record dict (empty if not found/invalid).
    """
    if not approval_record_path or not os.path.isfile(approval_record_path):
        return (
            False,
            "No approval record provided. Odds import blocked until "
            "explicit license approval is recorded in approval_record.json.",
            {},
        )

    try:
        with open(approval_record_path, encoding="utf-8") as fh:
            record = json.load(fh)
    except (json.JSONDecodeError, OSError) as exc:
        return (False, f"Approval record could not be parsed: {exc}", {})

    missing_fields: List[str] = [
        f for f in REQUIRED_APPROVAL_FIELDS if f not in record
    ]
    if missing_fields:
        return (
            False,
            f"Approval record is missing required fields: {missing_fields}",
            record,
        )

    allowed_use = str(record.get("allowed_use", "")).lower().strip()
    if allowed_use not in APPROVED_USE_VALUES:
        return (
            False,
            f"Approval record 'allowed_use' value '{allowed_use}' is not in "
            f"approved values: {APPROVED_USE_VALUES}",
            record,
        )

    return (True, "Approval record is valid.", record)


# ---------------------------------------------------------------------------
# Schema template validator
# ---------------------------------------------------------------------------


def validate_odds_import_schema_template(template_path: str) -> Tuple[bool, str, List[str]]:
    """Validate that the P34 odds import template CSV has the required columns.

    Parameters
    ----------
    template_path:
        Path to odds_import_template.csv from P34.

    Returns
    -------
    (valid: bool, reason: str, missing_columns: list)
    """
    if not template_path or not os.path.isfile(template_path):
        return (False, f"Template file not found: {template_path}", list(ODDS_REQUIRED_COLUMNS))

    try:
        df = pd.read_csv(template_path, nrows=0)
    except Exception as exc:
        return (False, f"Could not read template: {exc}", list(ODDS_REQUIRED_COLUMNS))

    actual_cols = set(df.columns.tolist())
    required_cols = set(ODDS_REQUIRED_COLUMNS)
    missing = sorted(required_cols - actual_cols)

    if missing:
        return (False, f"Missing required columns: {missing}", missing)
    return (True, "Schema template has all required columns.", [])


# ---------------------------------------------------------------------------
# Summarizer
# ---------------------------------------------------------------------------


def summarize_odds_license_validation(
    approval_approved: bool,
    approval_reason: str,
    schema_valid: bool,
    schema_reason: str,
    schema_missing_cols: List[str],
    checklist_items: List[str],
    odds_options: List[Dict[str, Any]],
) -> P35OddsLicenseValidationResult:
    """Build a P35OddsLicenseValidationResult from validation findings.

    This function NEVER returns implementation_ready=True unless approval
    is explicitly granted AND schema is valid.
    """
    # Hard guard
    assert PAPER_ONLY is True, "PAPER_ONLY must be True"
    assert PRODUCTION_READY is False, "PRODUCTION_READY must be False"

    if not approval_approved:
        license_status = LICENSE_BLOCKED_NOT_APPROVED
        validation_status = VALIDATION_BLOCKED_LICENSE
        implementation_ready = False
        blocker_reason = approval_reason
        approval_record_found = False
    else:
        approval_record_found = True
        if not schema_valid:
            license_status = LICENSE_REVIEW_REQUIRED
            validation_status = VALIDATION_BLOCKED_SCHEMA
            implementation_ready = False
            blocker_reason = schema_reason
        else:
            license_status = LICENSE_APPROVED_INTERNAL_RESEARCH
            validation_status = VALIDATION_READY_FOR_IMPLEMENTATION
            implementation_ready = True
            blocker_reason = ""

    # Best known source from P34
    best_opt = odds_options[0] if odds_options else {}
    source_name = best_opt.get("source_name", "sportsbookreviewsonline.com")
    source_url = KNOWN_ODDS_SOURCES[0]["source_url"]

    return P35OddsLicenseValidationResult(
        source_type="licensed_export",
        source_name=source_name,
        source_path_or_url=source_url,
        license_status=license_status,
        provenance_status="external_public_archive",
        schema_status="valid" if schema_valid else f"missing: {schema_missing_cols}",
        leakage_risk="none" if schema_valid else "schema_gap",
        implementation_ready=implementation_ready,
        blocker_reason=blocker_reason,
        paper_only=True,
        production_ready=False,
        season=2024,
        checklist_items=tuple(checklist_items),
        approval_record_found=approval_record_found,
        notes=(
            "Do NOT scrape odds. Download manually after ToS approval. "
            "Do NOT infer odds from game outcomes."
        ),
    )


# ---------------------------------------------------------------------------
# Import validation plan builder
# ---------------------------------------------------------------------------


def build_odds_import_validation_plan(
    odds_options: List[Dict[str, Any]],
    approval_result: P35OddsLicenseValidationResult,
) -> P35OddsImportValidationPlan:
    """Build the import validation plan for odds.

    Always reflects the current blocked/approved state.
    """
    if approval_result.implementation_ready:
        validation_status = VALIDATION_READY_FOR_IMPLEMENTATION
        approved = True
        blocker = ""
        next_steps = (
            "Proceed to P36: build odds import adapter.",
            "Parse Excel archives → CSV with required columns.",
            "Convert American moneylines → decimal odds.",
            "Align game_id to P32 spine.",
        )
    else:
        validation_status = VALIDATION_BLOCKED_LICENSE
        approved = False
        blocker = approval_result.blocker_reason
        next_steps = (
            "Review sportsbookreviewsonline.com Terms of Service.",
            "Obtain explicit approval from project lead.",
            "Create approval_record.json with all required fields.",
            "Re-run P35 with --odds-approval-record flag.",
        )

    return P35OddsImportValidationPlan(
        source_name=approval_result.source_name,
        source_url=approval_result.source_path_or_url,
        required_columns=ODDS_REQUIRED_COLUMNS,
        license_status=approval_result.license_status,
        validation_status=validation_status,
        approval_required=True,
        approved=approved,
        blocker_reason=blocker,
        paper_only=True,
        production_ready=False,
        season=2024,
        next_steps=next_steps,
    )
