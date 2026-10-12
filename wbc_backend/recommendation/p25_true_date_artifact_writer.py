"""
wbc_backend/recommendation/p25_true_date_artifact_writer.py

P25 True-Date Artifact Writer — writes per-date slice CSVs and summary JSONs
for dates that have TRUE_DATE_SLICE_READY status.

Output layout:
  <output_base_dir>/
    true_date_slices/
      <date>/
        p15_true_date_input.csv
        p15_true_date_input_summary.json

Only dates with status == TRUE_DATE_SLICE_READY are written.
This phase does NOT write canonical P15/P16/P20 directories.

PAPER_ONLY — no production systems, no real bets.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from wbc_backend.recommendation.p25_true_date_source_contract import (
    TRUE_DATE_SLICE_READY,
    P25TrueDateArtifactManifest,
)
from wbc_backend.recommendation.p25_true_game_date_source_slicer import (
    identify_game_date_column,
    slice_source_by_game_date,
    summarize_true_date_slice,
    write_true_date_slice,
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def write_true_date_artifacts(
    date_results: List[Dict[str, Any]],
    output_base_dir: Path,
) -> P25TrueDateArtifactManifest:
    """Write slice CSVs and summary JSONs for all READY dates.

    Args:
        date_results: list of per-date dicts from build_true_date_separation_plan.
        output_base_dir: root output directory.

    Returns:
        P25TrueDateArtifactManifest with metadata about written artifacts.
    """
    output_base_dir.mkdir(parents=True, exist_ok=True)

    written_dates: List[str] = []
    skipped_dates: List[str] = []
    total_rows = 0
    total_game_ids = 0

    for result in date_results:
        run_date = result["run_date"]
        status = result.get("status", "")
        source_path_str = result.get("source_path", "")

        if status != TRUE_DATE_SLICE_READY or not source_path_str:
            skipped_dates.append(run_date)
            continue

        source_path = Path(source_path_str)
        slice_df = slice_source_by_game_date(source_path, run_date)

        if slice_df is None or len(slice_df) == 0:
            skipped_dates.append(run_date)
            continue

        # Write CSV
        slice_csv_path = write_true_date_slice(slice_df, output_base_dir, run_date)

        # Build and write summary JSON
        summary = summarize_true_date_slice(slice_df, run_date, source_path_str)
        summary["paper_only"] = True
        summary["production_ready"] = False
        summary["slice_csv_path"] = str(slice_csv_path)
        summary_path = write_slice_manifest(summary, output_base_dir, run_date)

        written_dates.append(run_date)
        total_rows += len(slice_df)
        if "game_id" in slice_df.columns:
            total_game_ids += int(slice_df["game_id"].nunique())

    return P25TrueDateArtifactManifest(
        output_dir=str(output_base_dir),
        date_start=date_results[0]["run_date"] if date_results else "",
        date_end=date_results[-1]["run_date"] if date_results else "",
        written_dates=tuple(sorted(written_dates)),
        skipped_dates=tuple(sorted(skipped_dates)),
        total_rows_written=total_rows,
        total_unique_game_ids_written=total_game_ids,
        paper_only=True,
        production_ready=False,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


def write_slice_manifest(
    summary_dict: Dict[str, Any],
    output_base_dir: Path,
    target_date: str,
) -> Path:
    """Write summary JSON next to the slice CSV.

    Returns the path to the written JSON file.
    """
    date_dir = output_base_dir / "true_date_slices" / target_date
    date_dir.mkdir(parents=True, exist_ok=True)
    summary_path = date_dir / "p15_true_date_input_summary.json"
    with open(summary_path, "w", encoding="utf-8") as fh:
        json.dump(summary_dict, fh, indent=2, ensure_ascii=False)
    return summary_path


def validate_written_artifacts(output_dir: Path) -> bool:
    """Return True if every written slice has both CSV and summary JSON.

    Checks that:
    - true_date_slices/ directory exists
    - each date subdirectory has p15_true_date_input.csv
    - each date subdirectory has p15_true_date_input_summary.json
    """
    slices_dir = output_dir / "true_date_slices"
    if not slices_dir.exists():
        return True  # nothing written, trivially valid (no artifacts to validate)

    all_valid = True
    for date_dir in sorted(slices_dir.iterdir()):
        if not date_dir.is_dir():
            continue
        csv_path = date_dir / "p15_true_date_input.csv"
        summary_path = date_dir / "p15_true_date_input_summary.json"
        if not csv_path.exists() or not summary_path.exists():
            all_valid = False

    return all_valid


def build_artifact_manifest(
    date_results: List[Dict[str, Any]],
    output_base_dir: Path,
) -> P25TrueDateArtifactManifest:
    """Build a manifest from date_results without writing any files.

    Useful for validation / reporting before writing.
    """
    ready_dates = [r["run_date"] for r in date_results if r.get("status") == TRUE_DATE_SLICE_READY]
    skipped = [r["run_date"] for r in date_results if r.get("status") != TRUE_DATE_SLICE_READY]
    total_rows = sum(r.get("n_rows", 0) for r in date_results if r.get("status") == TRUE_DATE_SLICE_READY)
    total_ids = sum(
        r.get("n_unique_game_ids", 0)
        for r in date_results
        if r.get("status") == TRUE_DATE_SLICE_READY
    )

    return P25TrueDateArtifactManifest(
        output_dir=str(output_base_dir),
        date_start=date_results[0]["run_date"] if date_results else "",
        date_end=date_results[-1]["run_date"] if date_results else "",
        written_dates=tuple(sorted(ready_dates)),
        skipped_dates=tuple(sorted(skipped)),
        total_rows_written=total_rows,
        total_unique_game_ids_written=total_ids,
        paper_only=True,
        production_ready=False,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
