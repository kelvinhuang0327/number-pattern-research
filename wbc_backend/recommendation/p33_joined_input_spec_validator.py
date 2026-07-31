"""
P33 Joined Input Spec Validator
================================
Validates whether a candidate DataFrame or file satisfies the P33 joined
input specification. Returns a structured report of missing fields, leakage
risks, and overall readiness.

PAPER_ONLY — validation only; no data is written or mutated.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import pandas as pd

from wbc_backend.recommendation.p33_prediction_odds_gap_contract import (
    FORBIDDEN_LEAKAGE_PREFIXES,
    PAPER_ONLY,
    REQUIRED_JOINED_INPUT_FIELDS,
    P33RequiredJoinedInputSpec,
)


# ---------------------------------------------------------------------------
# Validation result dataclass
# ---------------------------------------------------------------------------


@dataclass
class P33JoinedInputValidationReport:
    """Result of validating a candidate DataFrame against the spec."""

    is_valid: bool = False
    missing_fields: List[str] = field(default_factory=list)
    leakage_risk_fields: List[str] = field(default_factory=list)
    extra_fields: List[str] = field(default_factory=list)
    row_count: int = 0
    null_counts: Dict[str, int] = field(default_factory=dict)
    schema_gap_fields: List[str] = field(default_factory=list)
    blocker_reason: str = ""
    paper_only: bool = True
    production_ready: bool = False


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


def build_required_joined_input_spec() -> P33RequiredJoinedInputSpec:
    """Return the canonical required joined input specification."""
    return P33RequiredJoinedInputSpec()


def identify_missing_joined_input_fields(df: pd.DataFrame) -> List[str]:
    """
    Return a list of required fields that are absent from the DataFrame columns.
    """
    present = {col.lower().strip() for col in df.columns}
    return [
        f for f in REQUIRED_JOINED_INPUT_FIELDS if f.lower() not in present
    ]


def identify_leakage_columns(df: pd.DataFrame) -> List[str]:
    """
    Return any column names whose prefix matches a forbidden leakage prefix.
    """
    risky: List[str] = []
    for col in df.columns:
        col_lower = col.lower()
        for prefix in FORBIDDEN_LEAKAGE_PREFIXES:
            if col_lower.startswith(prefix):
                risky.append(col)
                break
    return risky


def validate_no_leakage_columns(df: pd.DataFrame) -> bool:
    """
    Return True if the DataFrame has no columns with forbidden leakage prefixes.
    """
    return len(identify_leakage_columns(df)) == 0


def validate_candidate_joined_input(df: pd.DataFrame) -> P33JoinedInputValidationReport:
    """
    Validate a candidate joined input DataFrame against the P33 spec.
    Returns a P33JoinedInputValidationReport.
    """
    if not PAPER_ONLY:
        raise RuntimeError("Validator must run with PAPER_ONLY=True.")

    missing = identify_missing_joined_input_fields(df)
    leakage = identify_leakage_columns(df)
    present_cols = set(df.columns)
    required_set = set(REQUIRED_JOINED_INPUT_FIELDS)
    extra = sorted(present_cols - required_set)

    null_counts: Dict[str, int] = {}
    for col in df.columns:
        nc = int(df[col].isnull().sum())
        if nc > 0:
            null_counts[col] = nc

    schema_gap = list(missing)  # fields that are both required and absent

    blocker_reason = ""
    if missing:
        blocker_reason = (
            f"Missing required fields: {missing}. "
            "Cannot produce a valid 2024 joined input frame."
        )
    elif leakage:
        blocker_reason = (
            f"Leakage-risk columns detected: {leakage}. "
            "Remove future-data columns before joining."
        )

    is_valid = len(missing) == 0 and len(leakage) == 0

    return P33JoinedInputValidationReport(
        is_valid=is_valid,
        missing_fields=missing,
        leakage_risk_fields=leakage,
        extra_fields=extra,
        row_count=len(df),
        null_counts=null_counts,
        schema_gap_fields=schema_gap,
        blocker_reason=blocker_reason,
        paper_only=PAPER_ONLY,
        production_ready=False,
    )


def summarize_joined_input_readiness(df: pd.DataFrame) -> str:
    """
    Return a human-readable one-paragraph readiness summary.
    Used in report generation.
    """
    report = validate_candidate_joined_input(df)
    if report.is_valid:
        return (
            f"✅ Joined input frame is VALID: {report.row_count:,} rows, "
            f"all {len(REQUIRED_JOINED_INPUT_FIELDS)} required fields present, "
            "no leakage columns detected."
        )

    parts: List[str] = [
        f"❌ Joined input frame is INVALID ({report.row_count:,} rows)."
    ]
    if report.missing_fields:
        parts.append(f"Missing fields: {report.missing_fields}.")
    if report.leakage_risk_fields:
        parts.append(f"Leakage-risk columns: {report.leakage_risk_fields}.")
    return " ".join(parts)


def build_schema_gap_dict(df: Optional[pd.DataFrame] = None) -> Dict[str, str]:
    """
    Return a dict mapping each required field to its availability status
    for a given DataFrame. If df is None, all fields are marked MISSING.
    """
    if df is None:
        return {f: "MISSING" for f in REQUIRED_JOINED_INPUT_FIELDS}

    present = {col.lower().strip() for col in df.columns}
    result: Dict[str, str] = {}
    for f in REQUIRED_JOINED_INPUT_FIELDS:
        if f.lower() in present:
            col_series = df[f] if f in df.columns else df[
                [c for c in df.columns if c.lower() == f.lower()][0]
            ]
            null_count = int(col_series.isnull().sum())
            result[f] = "PRESENT" if null_count == 0 else f"PRESENT_NULLS={null_count}"
        else:
            result[f] = "MISSING"
    return result
