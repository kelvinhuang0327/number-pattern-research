"""
wbc_backend/recommendation/p25_true_game_date_source_slicer.py

P25 True Game Date Source Slicer — discovers source CSV files and slices
them by actual game_date column values, never by run_date relabeling.

Design principles:
- game_date values come directly from the source CSV; no relabeling.
- P23 materialized directories are excluded from discovery (known duplicates).
- A date is EMPTY if the source has no rows where game_date == target_date.
- Missing required columns → BLOCKED_MISSING_REQUIRED_COLUMNS.
- Duplicate game_id within a date → BLOCKED_DUPLICATE_GAME_ID.
- All outputs are deterministic for a fixed source CSV.

PAPER_ONLY — no production systems, no real bets.
"""
from __future__ import annotations

import hashlib
import io
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from wbc_backend.recommendation.p25_true_date_source_contract import (
    TRUE_DATE_SLICE_BLOCKED_DATE_MISMATCH,
    TRUE_DATE_SLICE_BLOCKED_DUPLICATE_GAME_ID,
    TRUE_DATE_SLICE_BLOCKED_MISSING_REQUIRED_COLUMNS,
    TRUE_DATE_SLICE_EMPTY,
    TRUE_DATE_SLICE_READY,
)

# ---------------------------------------------------------------------------
# Column requirements
# ---------------------------------------------------------------------------
_REQUIRED_EXACT: frozenset = frozenset({"game_id", "y_true", "p_market"})
_DATE_COLUMN_CANDIDATES: frozenset = frozenset({"game_date", "date"})
_PRED_COLUMN_CANDIDATES: frozenset = frozenset({"p_model", "p_oof"})
_ODDS_COLUMN_CANDIDATES: frozenset = frozenset(
    {"odds_decimal", "decimal_odds", "odds_decimal_home", "odds_decimal_away"}
)

# ---------------------------------------------------------------------------
# Exclusion rules — paths containing these segments are P23 duplicated files
# and must not be used as true-date sources.
# ---------------------------------------------------------------------------
_EXCLUDED_PATH_SEGMENTS: Tuple[str, ...] = (
    "p23_historical_replay/p15_materialized",
    "p23_historical_replay\\p15_materialized",  # Windows compat
)

# Minimum file size to consider (bytes) — avoids scanning truly empty stub CSVs
_MIN_FILE_SIZE_BYTES = 50


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def discover_true_date_source_files(base_paths: List[str]) -> List[Path]:
    """Return a deduplicated, sorted list of CSV candidates.

    Candidates must:
    - end with .csv
    - be larger than _MIN_FILE_SIZE_BYTES
    - not live under a known P23-materialised directory
    - contain all required columns when read

    Files are deduped by resolved absolute path so symlinks don't produce
    duplicate entries.
    """
    seen: set = set()
    candidates: List[Path] = []

    for base in base_paths:
        for csv_path in sorted(Path(base).rglob("*.csv")):
            # Skip excluded P23 materialized paths
            if _is_excluded_path(csv_path):
                continue
            # Skip tiny files
            try:
                if csv_path.stat().st_size < _MIN_FILE_SIZE_BYTES:
                    continue
            except OSError:
                continue

            resolved = csv_path.resolve()
            if resolved in seen:
                continue

            # Quick column check without reading whole file
            if _has_required_columns_quick(csv_path):
                seen.add(resolved)
                candidates.append(csv_path)

    return sorted(candidates)


def identify_game_date_column(df: pd.DataFrame) -> Optional[str]:
    """Return the first matching date column name, or None."""
    for col in ("game_date", "date"):
        if col in df.columns:
            return col
    return None


def identify_required_columns(df: pd.DataFrame) -> Dict[str, bool]:
    """Return a dict mapping each requirement to whether it is satisfied."""
    cols = set(df.columns)
    return {
        "game_id": "game_id" in cols,
        "game_date_or_date": bool(cols & _DATE_COLUMN_CANDIDATES),
        "y_true": "y_true" in cols,
        "p_model_or_p_oof": bool(cols & _PRED_COLUMN_CANDIDATES),
        "p_market": "p_market" in cols,
        "odds_column": bool(cols & _ODDS_COLUMN_CANDIDATES),
    }


def slice_source_by_game_date(
    source_path: Path,
    target_date: str,
) -> Optional[pd.DataFrame]:
    """Return rows from source_path where game_date == target_date.

    Returns None if the file cannot be read or has no date column.
    Returns an empty DataFrame if no rows match.
    Does NOT relabel run_date as game_date.
    """
    try:
        df = pd.read_csv(source_path, dtype=str)
    except Exception:
        return None

    date_col = identify_game_date_column(df)
    if date_col is None:
        return None

    mask = df[date_col].astype(str).str.strip() == target_date
    sliced = df[mask].copy().reset_index(drop=True)
    return sliced


def validate_true_date_slice(
    slice_df: Optional[pd.DataFrame],
    target_date: str,
) -> Tuple[str, str]:
    """Return (status, blocker_reason) for the given slice.

    Status is one of the TRUE_DATE_SLICE_* constants.
    blocker_reason is empty string when status is READY or EMPTY.
    """
    if slice_df is None or len(slice_df) == 0:
        return (TRUE_DATE_SLICE_EMPTY, "")

    req = identify_required_columns(slice_df)
    if not all(req.values()):
        missing = [k for k, v in req.items() if not v]
        return (
            TRUE_DATE_SLICE_BLOCKED_MISSING_REQUIRED_COLUMNS,
            f"Missing required columns: {missing}",
        )

    # All rows must have the exact target_date as their game_date value
    date_col = identify_game_date_column(slice_df)
    if date_col is not None:
        mismatched = (~(slice_df[date_col].astype(str).str.strip() == target_date)).sum()
        if mismatched > 0:
            return (
                TRUE_DATE_SLICE_BLOCKED_DATE_MISMATCH,
                f"{mismatched} row(s) have game_date != '{target_date}'",
            )

    # Duplicate game_id check
    if "game_id" in slice_df.columns and slice_df["game_id"].duplicated().any():
        n_dup = slice_df["game_id"].duplicated().sum()
        return (
            TRUE_DATE_SLICE_BLOCKED_DUPLICATE_GAME_ID,
            f"{n_dup} duplicate game_id value(s) in date '{target_date}'",
        )

    return (TRUE_DATE_SLICE_READY, "")


def write_true_date_slice(
    slice_df: pd.DataFrame,
    output_dir: Path,
    target_date: str,
) -> Path:
    """Write slice_df as a CSV under output_dir/<target_date>/p15_true_date_input.csv.

    Returns the path to the written file.
    """
    date_dir = output_dir / "true_date_slices" / target_date
    date_dir.mkdir(parents=True, exist_ok=True)
    out_path = date_dir / "p15_true_date_input.csv"
    slice_df.to_csv(out_path, index=False)
    return out_path


def summarize_true_date_slice(
    slice_df: Optional[pd.DataFrame],
    target_date: str,
    source_path: str = "",
) -> Dict[str, Any]:
    """Return a JSON-serialisable summary dict for one date's slice."""
    if slice_df is None or len(slice_df) == 0:
        return {
            "target_date": target_date,
            "source_path": source_path,
            "n_rows": 0,
            "n_unique_game_ids": 0,
            "game_date_min": "",
            "game_date_max": "",
            "content_hash": "",
        }

    date_col = identify_game_date_column(slice_df)
    game_date_min = str(slice_df[date_col].min()) if date_col else ""
    game_date_max = str(slice_df[date_col].max()) if date_col else ""

    n_unique_game_ids = (
        slice_df["game_id"].nunique() if "game_id" in slice_df.columns else 0
    )

    content_hash = _compute_slice_content_hash(slice_df)

    return {
        "target_date": target_date,
        "source_path": source_path,
        "n_rows": len(slice_df),
        "n_unique_game_ids": n_unique_game_ids,
        "game_date_min": game_date_min,
        "game_date_max": game_date_max,
        "content_hash": content_hash,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _is_excluded_path(path: Path) -> bool:
    """Return True if path contains a known P23-materialized path segment."""
    path_str = str(path).replace("\\", "/")
    for segment in _EXCLUDED_PATH_SEGMENTS:
        if segment.replace("\\", "/") in path_str:
            return True
    return False


def _has_required_columns_quick(csv_path: Path) -> bool:
    """Read only the header row to check required columns cheaply."""
    try:
        with open(csv_path, encoding="utf-8", errors="replace") as fh:
            header_line = fh.readline()
        cols = {c.strip().lower() for c in header_line.split(",")}
        # Must have game_id and y_true at minimum
        if "game_id" not in cols or "y_true" not in cols:
            return False
        # Must have a date column
        if not ({"game_date", "date"} & cols):
            return False
        return True
    except Exception:
        return False


def _compute_slice_content_hash(df: pd.DataFrame) -> str:
    """Return sha256 hex-digest of slice CSV bytes (sorted by game_id for determinism)."""
    sort_col = "game_id" if "game_id" in df.columns else df.columns[0]
    sorted_df = df.sort_values(sort_col).reset_index(drop=True)
    buf = io.StringIO()
    sorted_df.to_csv(buf, index=False)
    return hashlib.sha256(buf.getvalue().encode()).hexdigest()
