"""
P33 Joined Input Skeleton Writer
==================================
Writes a set of gap-documenting skeleton artifacts to disk:

  - joined_input_required_spec.json      — canonical required field list
  - joined_input_schema_gap.json         — per-field availability status
  - mlb_2024_joined_input_schema.csv     — empty header-only template
  - mlb_2024_joined_input_gap_rows.csv   — per-game gap rows (all fields null)
  - mlb_2024_joined_input_schema_manifest.json

Artifacts are PAPER_ONLY placeholders. They document the gap, not fill it.
No odds, predictions, or scores are fabricated.
"""

from __future__ import annotations

import csv
import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from wbc_backend.recommendation.p33_prediction_odds_gap_contract import (
    PAPER_ONLY,
    PRODUCTION_READY,
    REQUIRED_JOINED_INPUT_FIELDS,
    P33GateResult,
    P33SourceGapSummary,
)
from wbc_backend.recommendation.p33_joined_input_spec_validator import (
    P33RequiredJoinedInputSpec,
    build_required_joined_input_spec,
    build_schema_gap_dict,
)

# ---------------------------------------------------------------------------
# Output file names
# ---------------------------------------------------------------------------
OUT_REQUIRED_SPEC = "joined_input_required_spec.json"
OUT_SCHEMA_GAP = "joined_input_schema_gap.json"
OUT_SCHEMA_CSV = "mlb_2024_joined_input_schema.csv"
OUT_GAP_ROWS_CSV = "mlb_2024_joined_input_gap_rows.csv"
OUT_MANIFEST = "mlb_2024_joined_input_schema_manifest.json"


# ---------------------------------------------------------------------------
# Writer helpers
# ---------------------------------------------------------------------------


def _ensure_output_dir(output_dir: str) -> None:
    Path(output_dir).mkdir(parents=True, exist_ok=True)


def write_required_spec_json(output_dir: str) -> str:
    """Write joined_input_required_spec.json. Returns file path."""
    spec = build_required_joined_input_spec()
    out_path = os.path.join(output_dir, OUT_REQUIRED_SPEC)
    payload = {
        "season": spec.season,
        "paper_only": spec.paper_only,
        "production_ready": spec.production_ready,
        "description": spec.description,
        "required_fields": list(spec.required_fields),
        "field_count": len(spec.required_fields),
    }
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
    return out_path


def write_schema_gap_json(
    output_dir: str,
    df: Optional[pd.DataFrame] = None,
) -> str:
    """
    Write joined_input_schema_gap.json showing per-field availability.
    If df is None (no data available), all fields are MISSING.
    """
    gap_dict = build_schema_gap_dict(df)
    missing_fields = [f for f, v in gap_dict.items() if v == "MISSING"]
    out_path = os.path.join(output_dir, OUT_SCHEMA_GAP)
    payload = {
        "season": 2024,
        "paper_only": PAPER_ONLY,
        "production_ready": PRODUCTION_READY,
        "field_availability": gap_dict,
        "missing_count": len(missing_fields),
        "missing_fields": missing_fields,
        "total_required": len(REQUIRED_JOINED_INPUT_FIELDS),
    }
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
    return out_path


def write_empty_joined_input_schema_csv(output_dir: str) -> str:
    """
    Write an empty CSV with only the header row (required field names).
    This is a schema template, not data.
    """
    out_path = os.path.join(output_dir, OUT_SCHEMA_CSV)
    with open(out_path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(REQUIRED_JOINED_INPUT_FIELDS)
    return out_path


def write_gap_rows_csv(
    output_dir: str,
    game_identity_csv: Optional[str] = None,
) -> str:
    """
    Write gap rows CSV: one row per 2024 game, with game identity fields
    populated from P32 outcomes and all prediction/odds fields set to null.

    If game_identity_csv is None or unreadable, writes an empty schema-only file.
    """
    out_path = os.path.join(output_dir, OUT_GAP_ROWS_CSV)

    gap_row_template: Dict[str, Optional[str]] = {f: None for f in REQUIRED_JOINED_INPUT_FIELDS}

    rows: List[Dict] = []
    if game_identity_csv and os.path.isfile(game_identity_csv):
        try:
            identity_df = pd.read_csv(game_identity_csv, dtype=str)
            for _, row in identity_df.iterrows():
                gap_row = dict(gap_row_template)
                # Populate known game identity columns
                for col in ["game_id", "game_date", "home_team", "away_team"]:
                    if col in identity_df.columns:
                        gap_row[col] = str(row[col]) if pd.notna(row[col]) else None
                # y_true_home_win comes from outcomes; leave null if missing
                if "y_true_home_win" in identity_df.columns:
                    gap_row["y_true_home_win"] = str(row["y_true_home_win"]) if pd.notna(row.get("y_true_home_win")) else None
                # Safety flags
                gap_row["paper_only"] = "True"
                gap_row["production_ready"] = "False"
                rows.append(gap_row)
        except Exception:
            rows = []

    if not rows:
        rows = [gap_row_template]  # schema-only placeholder

    with open(out_path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=REQUIRED_JOINED_INPUT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    return out_path


def write_schema_manifest(
    output_dir: str,
    written_files: List[str],
    gap_summary: P33SourceGapSummary,
) -> str:
    """Write mlb_2024_joined_input_schema_manifest.json."""
    out_path = os.path.join(output_dir, OUT_MANIFEST)
    payload = {
        "season": 2024,
        "paper_only": PAPER_ONLY,
        "production_ready": PRODUCTION_READY,
        "gap_status": {
            "prediction_missing": gap_summary.prediction_missing,
            "odds_missing": gap_summary.odds_missing,
            "prediction_gap_reason": gap_summary.prediction_gap_reason,
            "odds_gap_reason": gap_summary.odds_gap_reason,
        },
        "artifacts": written_files,
        "artifact_count": len(written_files),
    }
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
    return out_path


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def write_all_skeleton_artifacts(
    output_dir: str,
    gap_summary: P33SourceGapSummary,
    p32_outcomes_csv: Optional[str] = None,
) -> List[str]:
    """
    Write all P33 skeleton artifacts to output_dir.
    Returns list of absolute paths written.

    Parameters
    ----------
    output_dir    : Destination directory (created if absent).
    gap_summary   : Result from p33_2024_source_gap_auditor.
    p32_outcomes_csv : Optional path to P32 outcomes CSV for game identity rows.
    """
    if not PAPER_ONLY:
        raise RuntimeError("Skeleton writer must run with PAPER_ONLY=True.")

    _ensure_output_dir(output_dir)

    written: List[str] = []
    written.append(write_required_spec_json(output_dir))
    written.append(write_schema_gap_json(output_dir, df=None))  # all MISSING
    written.append(write_empty_joined_input_schema_csv(output_dir))
    written.append(write_gap_rows_csv(output_dir, game_identity_csv=p32_outcomes_csv))
    written.append(write_schema_manifest(output_dir, written, gap_summary))

    return written


def validate_skeleton_outputs(output_dir: str) -> bool:
    """
    Verify that all expected skeleton output files exist.
    Returns True if all present.
    """
    expected = [
        OUT_REQUIRED_SPEC,
        OUT_SCHEMA_GAP,
        OUT_SCHEMA_CSV,
        OUT_GAP_ROWS_CSV,
        OUT_MANIFEST,
    ]
    for fname in expected:
        if not os.path.isfile(os.path.join(output_dir, fname)):
            return False
    return True
