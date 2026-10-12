"""
P37 Approval Record Template Writer

Writes a TEMPLATE approval record JSON and human-readable INSTRUCTIONS.md to the
output directory.  Templates contain placeholder values only — no real provider
data, no real license text.

PAPER_ONLY=True  PRODUCTION_READY=False  SEASON=2024
"""

from __future__ import annotations

import json
import os
from typing import Dict

from wbc_backend.recommendation.p37_manual_odds_provisioning_contract import (
    APPROVAL_RECORD_TEMPLATE_FIELDS,
    PAPER_ONLY,
    PRODUCTION_READY,
    SEASON,
    P37ApprovalRecordTemplate,
)

# ---------------------------------------------------------------------------
# Placeholder values (safe — no real data)
# ---------------------------------------------------------------------------
_PLACEHOLDER_RECORD: Dict[str, object] = {
    "provider_name": "PLACEHOLDER_PROVIDER",
    "source_name": "PLACEHOLDER_SOURCE",
    "source_url_or_reference": "PLACEHOLDER_URL_OR_DOI",
    "license_terms_summary": "PLACEHOLDER_LICENSE_SUMMARY",
    "allowed_use": "internal_research",
    "redistribution_allowed": False,
    "attribution_required": True,
    "internal_research_allowed": True,
    "commercial_use_allowed": False,
    "approved_by": "PLACEHOLDER_APPROVER",
    "approved_at": "YYYY-MM-DDTHH:MM:SS+00:00",
    "approval_scope": "mlb_2024_season",
    "source_file_expected_path": "data/mlb_2024/manual_import/odds_2024_approved.csv",
    "checksum_required": True,
    "checksum_sha256": "PLACEHOLDER_SHA256",
    "paper_only": PAPER_ONLY,
    "production_ready": PRODUCTION_READY,
}

_INSTRUCTIONS_CONTENT: str = """# P37 Odds Approval Record — Provisioning Instructions

## Purpose
This document guides a researcher in manually creating a valid approval record
for the 2024 MLB licensed odds import gate.

No automated scraping or download occurs at any point.
All odds data must be manually acquired from a provider whose terms permit
internal research use.

---

## Step 1 — Identify a licensed odds provider
Select a provider whose Terms of Service (ToS) explicitly allow:
- internal / personal / academic research use
- non-commercial use
- at minimum, non-redistribution (redistribution_allowed may be false)

Examples of provider categories (not endorsement):
- Publicly available historical odds archives with CC or research licenses
- Purchased academic datasets with explicit license agreements
- Self-collected manual odds entries from publicly accessible scoreboards

---

## Step 2 — Review Terms of Service
Read the full ToS.  Confirm:
- internal_research_allowed = true
- commercial_use_allowed = false (required for paper-only mode)
- redistribution_allowed = false is acceptable
- paper_only clause does not conflict

---

## Step 3 — Fill in odds_approval_record_TEMPLATE.json
Copy `odds_approval_record_TEMPLATE.json` from this directory.
Rename the copy to `odds_approval_record.json`.
Place it at: `data/mlb_2024/manual_import/odds_approval_record.json`

Fill every PLACEHOLDER field with real values.
Do NOT set production_ready = true.
Do NOT set paper_only = false.

---

## Step 4 — Compute checksum
If checksum_required = true, compute:
  sha256sum data/mlb_2024/manual_import/odds_2024_approved.csv

Place the hex string into checksum_sha256.

---

## Step 5 — Run P37 gate again
  ./.venv/bin/python scripts/run_p37_manual_odds_provisioning_gate.py \\
    --output-dir data/mlb_2024/processed/p37_manual_odds_provisioning \\
    --approval-record data/mlb_2024/manual_import/odds_approval_record.json \\
    --paper-only true

Expected: approval_record_status=APPROVAL_VALID if all fields are correct.

---

## Required Fields
| Field | Type | Notes |
|-------|------|-------|
| provider_name | string | Must not be blank |
| source_name | string | Must not be blank |
| source_url_or_reference | string | URL or DOI or reference |
| license_terms_summary | string | Must not be blank |
| allowed_use | string | Must be one of: internal_research, research, personal_research, academic_research |
| redistribution_allowed | boolean | false is acceptable |
| attribution_required | boolean | - |
| internal_research_allowed | boolean | MUST be true |
| commercial_use_allowed | boolean | MUST be false |
| approved_by | string | Must not be blank |
| approved_at | ISO 8601 datetime string | Must not be blank |
| approval_scope | string | e.g. mlb_2024_season |
| source_file_expected_path | string | Must not be blank |
| checksum_required | boolean | - |
| checksum_sha256 | string | Required if checksum_required=true |
| paper_only | boolean | MUST be true |
| production_ready | boolean | MUST be false |

---

## Invariants (enforced by gate)
- paper_only MUST be true — gate blocks if false
- production_ready MUST be false — gate blocks if true
- raw_odds_commit_allowed is ALWAYS false
- This is PAPER_ONLY manual research — not production betting

---

## What NOT to do
- Do not fabricate odds values from game outcomes
- Do not download odds unless you have confirmed license
- Do not set production_ready=true
- Do not stage the filled approval record without human review
- Do not share real provider API credentials in this file

---

*Generated by P37 Manual Odds Provisioning Gate — PAPER_ONLY=True, SEASON=2024*
"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_approval_record_template() -> Dict[str, object]:
    """Return the placeholder approval record template dict."""
    return dict(_PLACEHOLDER_RECORD)


def validate_approval_record_template(template: Dict[str, object]) -> bool:
    """
    Return True if every required field is present in the template.

    Does NOT validate placeholder vs. real content — only structural presence.
    """
    return all(field in template for field in APPROVAL_RECORD_TEMPLATE_FIELDS)


def write_approval_record_template(output_dir: str) -> str:
    """
    Write odds_approval_record_TEMPLATE.json to output_dir.
    Returns the written file path.
    """
    os.makedirs(output_dir, exist_ok=True)
    template = build_approval_record_template()
    path = os.path.join(output_dir, "odds_approval_record_TEMPLATE.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(template, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    return path


def write_approval_record_instructions(output_dir: str) -> str:
    """
    Write odds_approval_record_INSTRUCTIONS.md to output_dir.
    Returns the written file path.
    """
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, "odds_approval_record_INSTRUCTIONS.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(_INSTRUCTIONS_CONTENT)
    return path
