"""
wbc_backend/recommendation/p29_source_coverage_expansion_scanner.py

Scans available data directories for potential additional sources that could
expand P25 true-date slice coverage without modifying policy thresholds.

Research only. paper_only=True. production_ready=False.
No files written by this module — scan is read-only.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from wbc_backend.recommendation.p29_density_expansion_contract import (
    P29SourceCoverageCandidate,
)

# ---------------------------------------------------------------------------
# Required columns for a valid P25-compatible source
# ---------------------------------------------------------------------------

_REQUIRED_P25_COLUMNS = frozenset({
    "edge",
    "odds_decimal",
    "y_true",
    "gate_reason",
    "paper_stake_units",
})

_OPTIONAL_P25_COLUMNS = frozenset({
    "game_id",
    "date",
    "ledger_id",
    "p_model",
    "p_market",
})

_P25_SLICE_FILENAME = "p15_true_date_input.csv"


# ---------------------------------------------------------------------------
# Detection helpers
# ---------------------------------------------------------------------------


def _probe_csv_columns(path: Path, nrows: int = 3) -> Optional[List[str]]:
    """Return column list from CSV or None on failure."""
    try:
        df = pd.read_csv(path, nrows=nrows)
        return list(df.columns)
    except Exception:
        return None


def _probe_csv_row_count(path: Path) -> int:
    """Return approximate row count from CSV (fast line count)."""
    try:
        with open(path, "r", errors="replace") as f:
            return max(0, sum(1 for _ in f) - 1)  # subtract header
    except Exception:
        return 0


def _has_required_columns(columns: List[str]) -> bool:
    return _REQUIRED_P25_COLUMNS.issubset(set(columns))


def _has_y_true(columns: List[str]) -> bool:
    return "y_true" in columns


def _has_game_id(columns: List[str]) -> bool:
    return "game_id" in columns or "Date" in columns


def _has_odds(columns: List[str]) -> bool:
    return "odds_decimal" in columns or "Away ML" in columns or "Home ML" in columns


def _infer_date_range_from_p25_dir(slices_dir: Path) -> tuple[str, str]:
    """Return (min_date, max_date) strings from P25 slices dir."""
    dates = sorted(d.name for d in slices_dir.iterdir() if d.is_dir())
    if not dates:
        return ("", "")
    return (dates[0], dates[-1])


# ---------------------------------------------------------------------------
# P25 slice directory scanner
# ---------------------------------------------------------------------------


def _scan_p25_backfill_dirs(backfill_dir: Path, current_p25_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
    """
    Scan outputs/predictions/PAPER/backfill/ for additional P25 slice directories
    other than the current primary one.
    """
    candidates: List[Dict[str, Any]] = []
    if not backfill_dir.exists():
        return candidates

    current_path_str = str(current_p25_dir.resolve()) if current_p25_dir else ""

    for d in sorted(backfill_dir.iterdir()):
        if not d.is_dir():
            continue
        if not d.name.startswith("p25_true_date_source_separation"):
            continue
        if str(d.resolve()) == current_path_str:
            continue  # skip the primary already-in-use dir

        slices_dir = d / "true_date_slices"
        if not slices_dir.exists():
            candidates.append({
                "source_path": str(d),
                "source_type": "wider_date_range",
                "n_dates": 0,
                "estimated_new_rows": 0,
                "has_required_columns": False,
                "has_y_true": False,
                "has_game_id": False,
                "has_odds": False,
                "coverage_note": "Directory exists but has no true_date_slices/ subdir",
                "is_safe_to_use": False,
                "date_range_start": "",
                "date_range_end": "",
            })
            continue

        date_dirs = [x for x in slices_dir.iterdir() if x.is_dir()]
        total_rows = 0
        has_req = False
        has_y = False
        has_gid = False
        has_odds = False
        for date_dir in date_dirs:
            csv = date_dir / _P25_SLICE_FILENAME
            if csv.exists():
                cols = _probe_csv_columns(csv)
                if cols and not has_req:
                    has_req = _has_required_columns(cols)
                    has_y = _has_y_true(cols)
                    has_gid = _has_game_id(cols)
                    has_odds = _has_odds(cols)
                total_rows += _probe_csv_row_count(csv)

        date_start, date_end = _infer_date_range_from_p25_dir(slices_dir)
        note = (
            f"Alternative P25 backfill with {len(date_dirs)} dates and ~{total_rows} rows. "
            f"Date range: {date_start} to {date_end}. "
            "Likely overlaps with primary P25 source — cannot add net-new rows without de-duplication."
        )

        candidates.append({
            "source_path": str(d),
            "source_type": "wider_date_range",
            "n_dates": len(date_dirs),
            "estimated_new_rows": 0,  # conservative: assume overlap with primary
            "has_required_columns": has_req,
            "has_y_true": has_y,
            "has_game_id": has_gid,
            "has_odds": has_odds,
            "coverage_note": note,
            "is_safe_to_use": False,  # overlap risk; would need dedup pipeline
            "date_range_start": date_start,
            "date_range_end": date_end,
        })

    return candidates


# ---------------------------------------------------------------------------
# Raw data file scanner
# ---------------------------------------------------------------------------


def _scan_raw_data_files(data_dir: Path) -> List[Dict[str, Any]]:
    """
    Scan data/ directory for CSV/Excel files that could serve as alternate sources.
    Checks column compatibility and estimates row counts.
    """
    candidates: List[Dict[str, Any]] = []
    if not data_dir.exists():
        return candidates

    scan_glob_patterns = ["**/*.csv", "**/*.xlsx"]
    seen: set = set()

    for pattern in scan_glob_patterns:
        for f in sorted(data_dir.glob(pattern)):
            if f in seen:
                continue
            seen.add(f)

            cols = _probe_csv_columns(f) if f.suffix == ".csv" else None
            if cols is None:
                # xlsx — try reading
                try:
                    df = pd.read_excel(f, nrows=3)
                    cols = list(df.columns)
                except Exception:
                    cols = []

            has_req = _has_required_columns(cols or [])
            has_y = _has_y_true(cols or [])
            has_gid = _has_game_id(cols or [])
            has_odds_flag = _has_odds(cols or [])

            estimated_rows = _probe_csv_row_count(f) if f.suffix == ".csv" else 0

            note = (
                f"Raw data file: {f.name}. Columns: {cols[:8] if cols else 'UNKNOWN'}. "
                f"Has required P25 columns: {has_req}. "
                + ("Usable after full pipeline re-run only — not directly P25-compatible."
                   if not has_req else "Schema-compatible but requires P25 pipeline integration.")
            )

            candidates.append({
                "source_path": str(f),
                "source_type": "alternate_odds" if has_odds_flag else "additional_season",
                "n_dates": 0,
                "estimated_new_rows": estimated_rows if has_req else 0,
                "has_required_columns": has_req,
                "has_y_true": has_y,
                "has_game_id": has_gid,
                "has_odds": has_odds_flag,
                "coverage_note": note,
                "is_safe_to_use": False,  # requires pipeline integration
                "date_range_start": "",
                "date_range_end": "",
            })

    return candidates


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def scan_additional_true_date_sources(
    base_paths: List[Path],
    current_p25_dir: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """
    Scan a list of base directories for any additional true-date data sources
    beyond the currently active P25 backfill directory.

    Returns a list of candidate dicts with provenance and compatibility info.
    """
    all_candidates: List[Dict[str, Any]] = []

    for base in base_paths:
        base = Path(base)
        if not base.exists():
            continue

        # If this is under outputs/predictions, look for P25 backfill dirs
        backfill_dir = base / "predictions" / "PAPER" / "backfill"
        if backfill_dir.exists():
            p25_candidates = _scan_p25_backfill_dirs(backfill_dir, current_p25_dir)
            all_candidates.extend(p25_candidates)

        # Scan raw data files (CSV/Excel)
        if base.name in ("data", "mlb_2025", "derived") or "data" in str(base):
            raw_candidates = _scan_raw_data_files(base)
            all_candidates.extend(raw_candidates)

    return all_candidates


def detect_other_seasons_or_ranges(
    candidates: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Filter candidates that represent additional seasons or date ranges
    (not just subsets of the current range).
    """
    return [
        c for c in candidates
        if c.get("source_type") in ("additional_season", "alternate_odds")
        or (c.get("source_type") == "wider_date_range" and c.get("estimated_new_rows", 0) > 0)
    ]


def summarize_source_expansion_options(
    candidates: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Summarize candidate source expansion options.
    Returns high-level counts and recommendation.
    """
    safe_candidates = [c for c in candidates if c.get("is_safe_to_use", False)]
    schema_compatible = [c for c in candidates if c.get("has_required_columns", False)]
    total_estimated_new_rows = sum(c.get("estimated_new_rows", 0) for c in safe_candidates)

    if safe_candidates:
        recommendation = (
            f"Found {len(safe_candidates)} safe source candidates with ~{total_estimated_new_rows} "
            "estimated new rows. Recommend pipeline integration."
        )
    elif schema_compatible:
        recommendation = (
            f"Found {len(schema_compatible)} schema-compatible sources but none safe to use directly. "
            "Requires full P25 pipeline re-run with new source before density can be expanded via source path."
        )
    else:
        recommendation = (
            f"Scanned {len(candidates)} candidates; none are immediately usable. "
            "All candidates either have schema mismatches or overlap with existing P25 source. "
            "Source expansion requires additional historical data acquisition or pipeline work."
        )

    return {
        "n_candidates_scanned": len(candidates),
        "n_candidates_safe": len(safe_candidates),
        "n_candidates_schema_compatible": len(schema_compatible),
        "total_estimated_new_rows_from_safe": total_estimated_new_rows,
        "source_expansion_feasible": len(safe_candidates) > 0,
        "recommendation": recommendation,
    }


def estimate_sample_gain_from_source_expansion(
    candidates: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Estimate total new active entries from source expansion
    (conservative: only count safe and schema-compatible sources).
    """
    safe_rows = sum(c.get("estimated_new_rows", 0) for c in candidates if c.get("is_safe_to_use"))
    schema_rows = sum(c.get("estimated_new_rows", 0) for c in candidates if c.get("has_required_columns"))

    # Conversion rate based on P28 diagnosis: 324/1577 = 20.5%
    _CONVERSION_RATE = 0.205
    safe_active_estimate = int(safe_rows * _CONVERSION_RATE)
    schema_active_estimate = int(schema_rows * _CONVERSION_RATE)

    return {
        "estimated_new_rows_safe": safe_rows,
        "estimated_new_rows_schema_compatible": schema_rows,
        "estimated_new_active_entries_safe": safe_active_estimate,
        "estimated_new_active_entries_schema_compatible": schema_active_estimate,
        "conversion_rate_assumed": _CONVERSION_RATE,
        "note": (
            "Estimates use the P28-observed conversion rate of 20.5% (324 active / 1577 source rows). "
            "Actual conversion depends on policy gates applied during P25 pipeline run."
        ),
    }


def build_source_coverage_candidates(
    raw_candidates: List[Dict[str, Any]],
) -> List[P29SourceCoverageCandidate]:
    """Convert raw candidate dicts to P29SourceCoverageCandidate dataclasses."""
    result: List[P29SourceCoverageCandidate] = []
    for c in raw_candidates:
        result.append(
            P29SourceCoverageCandidate(
                source_path=c.get("source_path", ""),
                source_type=c.get("source_type", "unknown"),
                date_range_start=c.get("date_range_start", ""),
                date_range_end=c.get("date_range_end", ""),
                estimated_new_rows=c.get("estimated_new_rows", 0),
                has_required_columns=c.get("has_required_columns", False),
                has_y_true=c.get("has_y_true", False),
                has_game_id=c.get("has_game_id", False),
                has_odds=c.get("has_odds", False),
                coverage_note=c.get("coverage_note", ""),
                is_safe_to_use=c.get("is_safe_to_use", False),
                paper_only=True,
                production_ready=False,
            )
        )
    return result
