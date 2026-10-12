"""
P22.5 P15 Input Dry-Run Builder.

Creates preview-only P15 input files for dates classified as P15-ready.
Reads from discovered source candidates. Never mutates canonical outputs.
Never fabricates missing fields.
PAPER_ONLY. No production DB writes. No live calls.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

from wbc_backend.recommendation.p22_5_source_artifact_contract import (
    HISTORICAL_P15_JOINED_INPUT,
    SOURCE_CANDIDATE_USABLE,
    P225HistoricalSourceCandidate,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_PREVIEW_ROWS = 20  # Only emit a sample, never full dataset
DRY_RUN_BUILD_STATUS = "DRY_RUN_PREVIEW"
DRY_RUN_BUILD_RISK_LOW = "LOW_STATIC_HISTORICAL_SOURCE"
DRY_RUN_BUILD_RISK_MEDIUM = "MEDIUM_DERIVED_IDENTITY"
DRY_RUN_BUILD_RISK_HIGH = "HIGH_UNSAFE_MAPPING"

# Required P15 input columns
_P15_REQUIRED_COLS = {
    "game_id",
    "game_date",
    "y_true",
}
_P15_EXPECTED_COLS = {
    "p_oof",
    "odds_decimal_home",
    "odds_decimal_away",
    "p_market",
    "home_team",
    "away_team",
}

PREVIEW_SUBDIR = "previews"

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_p15_input_preview_for_date(
    run_date: str,
    source_candidates: List[P225HistoricalSourceCandidate],
    output_dir: Path,
) -> Tuple[Optional[pd.DataFrame], str]:
    """Build a dry-run P15 input preview for a single run_date.

    Returns (preview_df, blocker_reason).
    If no safe source, returns (None, blocker_reason).
    Never writes canonical P15 outputs.
    Writes only to output_dir/previews/<date>/.
    """
    output_dir = Path(output_dir)

    # Find usable candidates — prefer P15 joined input as source
    usable = [c for c in source_candidates if c.candidate_status == SOURCE_CANDIDATE_USABLE]
    if not usable:
        return None, "NO_USABLE_SOURCE_CANDIDATES"

    # Prefer fully-joined P15 input (safest — no fabrication needed)
    joined_candidates = [c for c in usable if c.source_type == HISTORICAL_P15_JOINED_INPUT]
    source_candidate = joined_candidates[0] if joined_candidates else usable[0]

    # Validate source is readable
    source_path = Path(source_candidate.source_path)
    if not source_path.exists():
        return None, f"SOURCE_FILE_MISSING:{source_path}"

    # Read preview rows from source (header-safe)
    try:
        preview_df = pd.read_csv(source_path, nrows=MAX_PREVIEW_ROWS)
    except Exception as exc:
        return None, f"SOURCE_READ_ERROR:{exc}"

    if preview_df.empty:
        return None, "SOURCE_FILE_EMPTY"

    # Validate required fields exist in source
    missing_required = [c for c in _P15_REQUIRED_COLS if c not in preview_df.columns]
    if len(missing_required) == len(_P15_REQUIRED_COLS):
        # None of the required columns exist
        return None, f"SOURCE_MISSING_ALL_REQUIRED_COLS:{missing_required}"

    # Add metadata columns for dry-run identification
    preview_df = preview_df.copy()
    preview_df["run_date"] = run_date
    preview_df["source_file_refs"] = str(source_path)
    preview_df["build_status"] = DRY_RUN_BUILD_STATUS
    preview_df["build_risk"] = _infer_build_risk(source_candidate)
    preview_df["paper_only"] = True
    preview_df["production_ready"] = False

    # Validate the preview
    blocker = validate_p15_input_preview(preview_df)
    if blocker:
        return None, blocker

    # Write preview to output dir (never to canonical P15 dir)
    preview_dir = output_dir / PREVIEW_SUBDIR / run_date
    preview_dir.mkdir(parents=True, exist_ok=True)

    preview_csv = preview_dir / "p15_input_preview.csv"
    preview_df.to_csv(preview_csv, index=False)

    summary = summarize_preview(preview_df, run_date, str(source_path))
    summary_path = preview_dir / "p15_input_preview_summary.json"
    with summary_path.open("w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)

    return preview_df, ""


def validate_p15_input_preview(preview_df: pd.DataFrame) -> str:
    """Validate a preview DataFrame.

    Returns "" if valid, or an error string.
    Does NOT accept fabricated data (checks for DRY_RUN_PREVIEW tag).
    """
    if preview_df is None or preview_df.empty:
        return "PREVIEW_IS_EMPTY"

    # Must have build_status = DRY_RUN_PREVIEW (not canonical P15 output)
    if "build_status" not in preview_df.columns:
        return "MISSING_BUILD_STATUS_COLUMN"

    if (preview_df["build_status"] != DRY_RUN_BUILD_STATUS).any():
        return "INVALID_BUILD_STATUS_NOT_DRY_RUN"

    # Must not claim production readiness
    if "production_ready" in preview_df.columns:
        if preview_df["production_ready"].any():
            return "PREVIEW_CLAIMS_PRODUCTION_READY"

    # Must have at least some data rows
    if len(preview_df) == 0:
        return "PREVIEW_HAS_ZERO_ROWS"

    # Must not exceed MAX_PREVIEW_ROWS (safety guard against full dataset leakage)
    if len(preview_df) > MAX_PREVIEW_ROWS:
        return f"PREVIEW_EXCEEDS_MAX_ROWS:{len(preview_df)}"

    return ""


def summarize_preview(
    preview_df: pd.DataFrame,
    run_date: str,
    source_file: str,
) -> Dict:
    """Produce a JSON-serializable summary of a preview DataFrame."""
    n_rows = len(preview_df)
    cols = list(preview_df.columns)

    has_game_id = "game_id" in cols
    has_y_true = "y_true" in cols
    has_p_oof = "p_oof" in cols
    has_odds = any(c in cols for c in ["odds_decimal_home", "odds_decimal_away",
                                        "odds_decimal", "p_market"])

    missing_expected = [c for c in _P15_EXPECTED_COLS if c not in cols]

    return {
        "run_date": run_date,
        "build_status": DRY_RUN_BUILD_STATUS,
        "n_preview_rows": n_rows,
        "source_file": source_file,
        "has_game_id": has_game_id,
        "has_y_true": has_y_true,
        "has_p_oof": has_p_oof,
        "has_odds": has_odds,
        "missing_expected_cols": missing_expected,
        "paper_only": True,
        "production_ready": False,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _infer_build_risk(candidate: P225HistoricalSourceCandidate) -> str:
    if candidate.source_type == HISTORICAL_P15_JOINED_INPUT:
        return DRY_RUN_BUILD_RISK_LOW
    if candidate.has_game_id:
        return DRY_RUN_BUILD_RISK_LOW
    if candidate.has_p_model_or_p_oof and candidate.has_odds:
        return DRY_RUN_BUILD_RISK_MEDIUM
    return DRY_RUN_BUILD_RISK_HIGH
