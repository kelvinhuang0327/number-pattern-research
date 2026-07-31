"""
P32 Raw Game Artifact Writer.

Writes canonical game identity / outcome CSV artifacts and manifest/summary JSON.
Does NOT write odds or prediction artifacts.

PAPER_ONLY=True
production_ready=False
"""
from __future__ import annotations

import csv
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from wbc_backend.recommendation.p32_raw_game_log_contract import (
    PAPER_ONLY,
    PRODUCTION_READY,
    P32RawGameLogBuildSummary,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Filenames
# ---------------------------------------------------------------------------

IDENTITY_FILENAME = "mlb_2024_game_identity.csv"
OUTCOMES_FILENAME = "mlb_2024_game_outcomes.csv"
JOINED_FILENAME = "mlb_2024_game_identity_outcomes_joined.csv"
SUMMARY_FILENAME = "mlb_2024_game_log_summary.json"
MANIFEST_FILENAME = "mlb_2024_game_log_manifest.json"

IDENTITY_COLUMNS = [
    "game_id",
    "game_date",
    "season",
    "away_team",
    "home_team",
    "source_name",
    "source_row_number",
]

OUTCOME_COLUMNS = [
    "game_id",
    "game_date",
    "season",
    "away_team",
    "home_team",
    "away_score",
    "home_score",
    "y_true_home_win",
    "source_name",
    "source_row_number",
]

# Columns explicitly blocked from artifacts
BLOCKED_COLUMNS = frozenset(
    {
        "odds",
        "closing_odds",
        "moneyline",
        "spread",
        "over_under",
        "predicted_probability",
        "edge",
        "kelly_fraction",
        "recommendation",
        "bet_size",
        "pnl",
        "ev",
    }
)


# ---------------------------------------------------------------------------
# Public writer functions
# ---------------------------------------------------------------------------


def write_raw_game_identity_artifact(processed_df: pd.DataFrame, output_dir: Path) -> Path:
    """
    Write game identity CSV (game_id, date, teams).
    No scores, no odds, no predictions.
    """
    _assert_no_blocked_columns(processed_df, "identity")
    output_dir.mkdir(parents=True, exist_ok=True)
    out = output_dir / IDENTITY_FILENAME
    available = [c for c in IDENTITY_COLUMNS if c in processed_df.columns]
    processed_df[available].to_csv(out, index=False, quoting=csv.QUOTE_NONNUMERIC)
    logger.info("Wrote identity artifact: %s (%d rows)", out, len(processed_df))
    return out


def write_raw_game_outcome_artifact(processed_df: pd.DataFrame, output_dir: Path) -> Path:
    """
    Write game outcome CSV (game_id, scores, y_true_home_win).
    No odds, no predictions.
    """
    _assert_no_blocked_columns(processed_df, "outcomes")
    output_dir.mkdir(parents=True, exist_ok=True)
    out = output_dir / OUTCOMES_FILENAME
    available = [c for c in OUTCOME_COLUMNS if c in processed_df.columns]
    processed_df[available].to_csv(out, index=False, quoting=csv.QUOTE_NONNUMERIC)
    logger.info("Wrote outcomes artifact: %s (%d rows)", out, len(processed_df))
    return out


def write_raw_game_joined_artifact(processed_df: pd.DataFrame, output_dir: Path) -> Path:
    """
    Write joined identity+outcome CSV (all required canonical columns).
    No odds, no predictions.
    """
    _assert_no_blocked_columns(processed_df, "joined")
    output_dir.mkdir(parents=True, exist_ok=True)
    out = output_dir / JOINED_FILENAME
    all_cols = list(dict.fromkeys(IDENTITY_COLUMNS + OUTCOME_COLUMNS))
    available = [c for c in all_cols if c in processed_df.columns]
    processed_df[available].to_csv(out, index=False, quoting=csv.QUOTE_NONNUMERIC)
    logger.info("Wrote joined artifact: %s (%d rows)", out, len(processed_df))
    return out


def write_p32_summary(summary: P32RawGameLogBuildSummary, output_dir: Path) -> Path:
    """
    Write JSON summary of the P32 build run.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    out = output_dir / SUMMARY_FILENAME
    data: dict[str, Any] = {
        "season": summary.season,
        "source_name": summary.source_name,
        "source_path": summary.source_path,
        "row_count_raw": summary.row_count_raw,
        "row_count_processed": summary.row_count_processed,
        "unique_game_id_count": summary.unique_game_id_count,
        "date_start": summary.date_start,
        "date_end": summary.date_end,
        "teams_detected_count": summary.teams_detected_count,
        "outcome_coverage_pct": round(summary.outcome_coverage_pct, 6),
        "schema_valid": summary.schema_valid,
        "blocker": summary.blocker,
        "paper_only": summary.paper_only,
        "production_ready": summary.production_ready,
        "contains_odds": summary.contains_odds,
        "contains_predictions": summary.contains_predictions,
    }
    out.write_text(json.dumps(data, indent=2), encoding="utf-8")
    logger.info("Wrote build summary: %s", out)
    return out


def build_artifact_manifest(output_dir: Path) -> Path:
    """
    Scan output_dir for artifact files and write a manifest JSON listing them.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_files: list[dict[str, Any]] = []
    for f in sorted(output_dir.iterdir()):
        if f.is_file() and f.name != MANIFEST_FILENAME:
            artifact_files.append(
                {
                    "filename": f.name,
                    "size_bytes": f.stat().st_size,
                    "paper_only": True,
                    "production_ready": False,
                    "contains_odds": False,
                    "contains_predictions": False,
                }
            )

    manifest: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "paper_only": PAPER_ONLY,
        "production_ready": PRODUCTION_READY,
        "contains_odds": False,
        "contains_predictions": False,
        "artifact_count": len(artifact_files),
        "artifacts": artifact_files,
    }
    out = output_dir / MANIFEST_FILENAME
    out.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    logger.info("Wrote artifact manifest: %s (%d files)", out, len(artifact_files))
    return out


# ---------------------------------------------------------------------------
# Safety helpers
# ---------------------------------------------------------------------------


def _assert_no_blocked_columns(df: pd.DataFrame, artifact_name: str) -> None:
    """Raise if the DataFrame contains any blocked columns (odds, predictions)."""
    found = BLOCKED_COLUMNS & set(df.columns)
    if found:
        raise ValueError(
            f"CONTRACT VIOLATION: {artifact_name} artifact contains blocked "
            f"columns: {sorted(found)}. P32 must not write odds or prediction data."
        )
