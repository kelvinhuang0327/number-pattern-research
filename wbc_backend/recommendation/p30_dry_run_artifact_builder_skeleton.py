"""
wbc_backend/recommendation/p30_dry_run_artifact_builder_skeleton.py

P30 Dry-Run Artifact Builder Skeleton.

Produces a PREVIEW ONLY of the joined input artifact that would be built
for a target season. Does NOT write P25/P26 outputs, does NOT fabricate
missing data, and does NOT perform actual model predictions or odds lookups.

If required sources are missing → emits an empty DataFrame with blocker reasons.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from wbc_backend.recommendation.p30_source_acquisition_contract import (
    ARTIFACT_GAME_IDENTITY,
    ARTIFACT_GAME_OUTCOMES,
    ARTIFACT_MARKET_ODDS,
    ARTIFACT_MODEL_PREDICTIONS_OR_OOF,
    ARTIFACT_TRUE_DATE_JOINED_INPUT,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PREVIEW_SCHEMA_COLUMNS = [
    "game_id",
    "game_date",
    "home_team",
    "away_team",
    "y_true",
    "p_model",
    "p_market",
    "odds_decimal",
]

DRY_RUN_STATUS_PREVIEW_READY = "PREVIEW_READY"
DRY_RUN_STATUS_BLOCKED_MISSING = "BLOCKED_MISSING_ARTIFACTS"
DRY_RUN_STATUS_EMPTY = "EMPTY"

# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _find_best_candidate(
    source_mapping: Dict[str, Any],
    artifact_type: str,
) -> Optional[str]:
    """Return the best matching source path for a given artifact type."""
    paths = source_mapping.get(artifact_type, [])
    if isinstance(paths, str):
        return paths if paths else None
    if isinstance(paths, list) and paths:
        return paths[0]
    return None


def _try_load_preview_rows(path: str, max_rows: int = 5) -> Optional[pd.DataFrame]:
    """Attempt to load a few preview rows from a file without fabricating data."""
    try:
        p = Path(path)
        if not p.exists() or not p.is_file():
            return None
        if p.suffix == ".csv":
            return pd.read_csv(p, nrows=max_rows)
        elif p.suffix == ".parquet":
            df = pd.read_parquet(p)
            return df.head(max_rows)
        elif p.suffix == ".xlsx":
            return pd.read_excel(p, nrows=max_rows)
    except Exception as exc:
        logger.debug("Cannot load preview rows from %s: %s", path, exc)
    return None


def _normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """Attempt to rename known alias columns to canonical names."""
    alias_map = {
        "Date": "game_date",
        "date": "game_date",
        "Away": "away_team",
        "Home": "home_team",
        "game_pk": "game_id",
        "Away Score": "y_true",
        "Home Score": "home_score",
    }
    rename = {col: alias_map[col] for col in df.columns if col in alias_map}
    return df.rename(columns=rename)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_dry_run_joined_input_preview(
    source_mapping: Dict[str, Any],
    output_dir: Path,
    max_preview_rows: int = 5,
) -> pd.DataFrame:
    """
    Build a PREVIEW ONLY of the joined input artifact.
    - Does NOT fabricate missing odds, predictions, or outcomes.
    - If required sources are missing → returns an empty DataFrame.
    - Does NOT write P25/P26 outputs.

    Args:
        source_mapping: dict mapping artifact type constants to source paths.
            e.g. {ARTIFACT_GAME_IDENTITY: "path/to/file.csv", ...}
        output_dir: directory to write preview artifacts (sub-dir: preview/).
        max_preview_rows: number of preview rows to show.

    Returns:
        pd.DataFrame — preview rows if any source available, else empty.
    """
    # Check which required sources are available
    identity_path = _find_best_candidate(source_mapping, ARTIFACT_GAME_IDENTITY)
    outcomes_path = _find_best_candidate(source_mapping, ARTIFACT_GAME_OUTCOMES)
    model_path = _find_best_candidate(source_mapping, ARTIFACT_MODEL_PREDICTIONS_OR_OOF)
    odds_path = _find_best_candidate(source_mapping, ARTIFACT_MARKET_ODDS)
    joined_path = _find_best_candidate(source_mapping, ARTIFACT_TRUE_DATE_JOINED_INPUT)

    # If a pre-joined input exists, use it directly (highest priority)
    if joined_path:
        df = _try_load_preview_rows(joined_path, max_preview_rows)
        if df is not None and len(df) > 0:
            df = _normalize_column_names(df)
            # Only keep preview schema columns that exist
            keep_cols = [c for c in PREVIEW_SCHEMA_COLUMNS if c in df.columns]
            if keep_cols:
                return df[keep_cols].copy()

    # Try to build a partial preview from identity source only (no fabrication)
    preview_source = identity_path or odds_path
    if preview_source:
        df = _try_load_preview_rows(preview_source, max_preview_rows)
        if df is not None and len(df) > 0:
            df = _normalize_column_names(df)
            # Only return columns we actually have; do NOT fill in missing ones
            keep_cols = [c for c in PREVIEW_SCHEMA_COLUMNS if c in df.columns]
            if keep_cols:
                return df[keep_cols].copy()

    # Nothing available → return empty DataFrame
    return pd.DataFrame(columns=PREVIEW_SCHEMA_COLUMNS)


def validate_joined_input_preview(preview_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Validate a joined input preview DataFrame.
    Returns a validation result dict.
    """
    if preview_df.empty:
        return {
            "is_valid": False,
            "n_rows": 0,
            "columns_present": [],
            "columns_missing": PREVIEW_SCHEMA_COLUMNS,
            "blocker_reasons": [
                "Preview DataFrame is empty — required source artifacts are missing.",
                "No game identity source found.",
                "No model predictions source found.",
                "No market odds source found.",
            ],
            "notes": "Cannot build joined input without all required artifacts.",
        }

    present_cols = list(preview_df.columns)
    missing_cols = [c for c in PREVIEW_SCHEMA_COLUMNS if c not in present_cols]
    blockers = []
    if "y_true" in missing_cols:
        blockers.append("Missing y_true (game outcomes).")
    if "p_model" in missing_cols:
        blockers.append("Missing p_model (model predictions).")
    if "p_market" in missing_cols:
        blockers.append("Missing p_market (market implied probability).")
    if "odds_decimal" in missing_cols:
        blockers.append("Missing odds_decimal (decimal odds).")

    is_valid = len(missing_cols) == 0 and not preview_df.empty

    return {
        "is_valid": is_valid,
        "n_rows": len(preview_df),
        "columns_present": sorted(present_cols),
        "columns_missing": sorted(missing_cols),
        "blocker_reasons": blockers,
        "notes": (
            "Preview appears complete."
            if is_valid
            else f"Partial preview: {len(missing_cols)} schema columns missing."
        ),
    }


def summarize_preview(preview_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Summarize the preview DataFrame.
    Returns dict with n_rows, blocker_reasons, schema_coverage, and status.
    """
    validation = validate_joined_input_preview(preview_df)
    n_rows = len(preview_df)
    present_cols = list(preview_df.columns) if not preview_df.empty else []
    missing_cols = [c for c in PREVIEW_SCHEMA_COLUMNS if c not in present_cols]

    if n_rows == 0:
        status = DRY_RUN_STATUS_BLOCKED_MISSING
    elif missing_cols:
        status = DRY_RUN_STATUS_PREVIEW_READY  # partial preview is still a preview
    else:
        status = DRY_RUN_STATUS_PREVIEW_READY

    return {
        "n_rows": n_rows,
        "n_columns": len(present_cols),
        "columns_present": sorted(present_cols),
        "columns_missing": sorted(missing_cols),
        "blocker_reasons": validation["blocker_reasons"],
        "dry_run_status": status,
        "schema_coverage": (
            "FULL"
            if not missing_cols and n_rows > 0
            else "PARTIAL"
            if present_cols and n_rows > 0
            else "EMPTY"
        ),
        "paper_only": True,
        "production_ready": False,
        "is_fabricated": False,
        "note": (
            "Dry-run preview only. No P25/P26 outputs written. "
            "No data was fabricated. Schema gaps indicate required artifact acquisition."
        ),
    }


def write_preview_artifacts(
    output_dir: Path,
    preview_df: pd.DataFrame,
    summary: Dict[str, Any],
    validation_result: Dict[str, Any],
) -> None:
    """Write preview artifacts to output_dir/preview/."""
    preview_dir = output_dir / "preview"
    preview_dir.mkdir(parents=True, exist_ok=True)

    # Write preview CSV (possibly empty)
    csv_path = preview_dir / "joined_input_preview.csv"
    preview_df.to_csv(csv_path, index=False)
    logger.info("Wrote preview CSV: %s (%d rows)", csv_path, len(preview_df))

    # Write summary JSON
    summary_path = preview_dir / "dry_run_preview_summary.json"
    with open(summary_path, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, ensure_ascii=False)
    logger.info("Wrote preview summary: %s", summary_path)

    # Write validation JSON
    validation_path = preview_dir / "dry_run_preview_validation.json"
    with open(validation_path, "w", encoding="utf-8") as fh:
        json.dump(validation_result, fh, indent=2, ensure_ascii=False)
    logger.info("Wrote preview validation: %s", validation_path)
