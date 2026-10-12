"""
wbc_backend/recommendation/p25_source_separation_planner.py

P25 Source Separation Planner — builds the per-date separation plan, classifies
availability, and generates recommended backfill commands for the true-date range.

Design principles:
- A date is backfill-ready only if it has a TRUE_DATE_SLICE_READY slice.
- Existing duplicated P23 materialized files cannot qualify as ready.
- If requested date range has no ready dates but true source data is found,
  the planner recommends the actual source date range instead.
- No fabrication of game outcomes, odds, predictions, or PnL.

PAPER_ONLY — no production systems, no real bets.
"""
from __future__ import annotations

import hashlib
import io
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from wbc_backend.recommendation.p25_true_date_source_contract import (
    TRUE_DATE_SLICE_BLOCKED_DATE_MISMATCH,
    TRUE_DATE_SLICE_BLOCKED_DUPLICATE_GAME_ID,
    TRUE_DATE_SLICE_BLOCKED_MISSING_REQUIRED_COLUMNS,
    TRUE_DATE_SLICE_EMPTY,
    TRUE_DATE_SLICE_PARTIAL,
    TRUE_DATE_SLICE_READY,
    P25SourceSeparationSummary,
)
from wbc_backend.recommendation.p25_true_game_date_source_slicer import (
    discover_true_date_source_files,
    identify_game_date_column,
    identify_required_columns,
    slice_source_by_game_date,
    summarize_true_date_slice,
    validate_true_date_slice,
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_true_date_separation_plan(
    date_start: str,
    date_end: str,
    source_candidates: List[Path],
) -> List[Dict[str, Any]]:
    """Return a list of per-date result dicts for the date_start..date_end range.

    For each requested date:
    - Try every source candidate in order (sorted deterministically).
    - Pick the first candidate that produces a READY slice.
    - If none produces READY, record the best non-ready status found.
    - Record all detected source game_date ranges from ALL candidates (union).

    Returns a list of dicts (one per requested date), each containing:
        run_date, status, source_path, n_rows, n_unique_game_ids,
        game_date_min, game_date_max, has_required_columns, blocker_reason.
    """
    requested_dates = _date_range(date_start, date_end)
    # Sort candidates for determinism
    sorted_candidates = sorted(source_candidates)

    # Preload source dataframes once (they may be large, avoid re-reading per date)
    loaded: Dict[str, Optional[pd.DataFrame]] = {}
    for src in sorted_candidates:
        try:
            loaded[str(src)] = pd.read_csv(src, dtype=str)
        except Exception:
            loaded[str(src)] = None

    results: List[Dict[str, Any]] = []
    for run_date in requested_dates:
        result = _plan_one_date(run_date, sorted_candidates, loaded)
        results.append(result)

    return results


def classify_date_slice_availability(date_result: Dict[str, Any]) -> str:
    """Return a human-readable availability classification for a date result dict."""
    status = date_result.get("status", "")
    if status == TRUE_DATE_SLICE_READY:
        return "READY"
    if status == TRUE_DATE_SLICE_EMPTY:
        return "EMPTY"
    if status == TRUE_DATE_SLICE_PARTIAL:
        return "PARTIAL"
    if status in (
        TRUE_DATE_SLICE_BLOCKED_DATE_MISMATCH,
        TRUE_DATE_SLICE_BLOCKED_DUPLICATE_GAME_ID,
        TRUE_DATE_SLICE_BLOCKED_MISSING_REQUIRED_COLUMNS,
    ):
        return "BLOCKED"
    return "UNKNOWN"


def summarize_true_date_separation_results(
    date_results: List[Dict[str, Any]],
    date_start: str,
    date_end: str,
    source_candidates: List[Path],
) -> P25SourceSeparationSummary:
    """Aggregate per-date results into a P25SourceSeparationSummary."""
    n_ready = sum(1 for r in date_results if r["status"] == TRUE_DATE_SLICE_READY)
    n_empty = sum(1 for r in date_results if r["status"] == TRUE_DATE_SLICE_EMPTY)
    n_partial = sum(1 for r in date_results if r["status"] == TRUE_DATE_SLICE_PARTIAL)
    n_blocked = sum(
        1
        for r in date_results
        if r["status"]
        in (
            TRUE_DATE_SLICE_BLOCKED_DATE_MISMATCH,
            TRUE_DATE_SLICE_BLOCKED_DUPLICATE_GAME_ID,
            TRUE_DATE_SLICE_BLOCKED_MISSING_REQUIRED_COLUMNS,
        )
    )

    # Detect the overall source game_date range from all candidates
    detected_min, detected_max = _detect_source_game_date_range(source_candidates)

    # Recommend backfill range = the true source range (if different from requested)
    rec_start, rec_end = _recommend_backfill_range(
        date_start, date_end, n_ready, detected_min, detected_max
    )

    return P25SourceSeparationSummary(
        date_start=date_start,
        date_end=date_end,
        n_dates_requested=len(date_results),
        n_true_date_ready=n_ready,
        n_empty_dates=n_empty,
        n_partial_dates=n_partial,
        n_blocked_dates=n_blocked,
        detected_source_game_date_min=detected_min,
        detected_source_game_date_max=detected_max,
        recommended_backfill_date_start=rec_start,
        recommended_backfill_date_end=rec_end,
        source_files_scanned=len(source_candidates),
        paper_only=True,
        production_ready=False,
    )


def validate_source_separation_summary(summary: P25SourceSeparationSummary) -> bool:
    """Return True if the summary passes internal consistency checks."""
    if summary.paper_only is not True:
        return False
    if summary.production_ready is not False:
        return False
    if summary.n_dates_requested < 0:
        return False
    total = (
        summary.n_true_date_ready
        + summary.n_empty_dates
        + summary.n_partial_dates
        + summary.n_blocked_dates
    )
    if total != summary.n_dates_requested:
        return False
    return True


def generate_next_backfill_commands(summary: P25SourceSeparationSummary) -> List[str]:
    """Return a list of CLI command strings recommended for the next phase.

    These are advisory only — they must NOT be executed automatically.
    """
    cmds: List[str] = []

    if summary.n_true_date_ready > 0:
        cmds.append(
            f"# P26: replay true-date backfill over {summary.recommended_backfill_date_start}"
            f" to {summary.recommended_backfill_date_end}"
        )
        cmds.append(
            f"./.venv/bin/python scripts/run_p26_true_date_historical_backfill.py"
            f" --date-start {summary.recommended_backfill_date_start}"
            f" --date-end {summary.recommended_backfill_date_end}"
            f" --paper-only true"
        )
    elif summary.detected_source_game_date_min and summary.detected_source_game_date_max:
        cmds.append(
            f"# P25 requested range ({summary.date_start} to {summary.date_end}) has no"
            f" true-date rows. True source range detected:"
            f" {summary.detected_source_game_date_min} to"
            f" {summary.detected_source_game_date_max}."
        )
        cmds.append(
            f"# Re-run P25 with the true source range:"
        )
        cmds.append(
            f"./.venv/bin/python scripts/run_p25_true_date_source_separation.py"
            f" --date-start {summary.detected_source_game_date_min}"
            f" --date-end {summary.detected_source_game_date_max}"
            f" --scan-base-path data"
            f" --scan-base-path outputs"
            f" --output-dir outputs/predictions/PAPER/backfill/"
            f"p25_true_date_source_separation_{summary.detected_source_game_date_min}"
            f"_{summary.detected_source_game_date_max}"
            f" --paper-only true"
        )
    else:
        cmds.append(
            "# No true source data found. Proceed to historical data acquisition."
        )
        cmds.append(
            "# Next recommended phase: historical data acquisition / fixture builder."
        )

    return cmds


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _date_range(date_start: str, date_end: str) -> List[str]:
    """Return inclusive list of YYYY-MM-DD strings."""
    start = date.fromisoformat(date_start)
    end = date.fromisoformat(date_end)
    days: List[str] = []
    current = start
    while current <= end:
        days.append(current.isoformat())
        current += timedelta(days=1)
    return days


def _plan_one_date(
    run_date: str,
    sorted_candidates: List[Path],
    loaded: Dict[str, Optional[pd.DataFrame]],
) -> Dict[str, Any]:
    """Try each candidate and return the best result for run_date."""
    best: Optional[Dict[str, Any]] = None

    for src in sorted_candidates:
        df_full = loaded.get(str(src))
        if df_full is None:
            continue

        date_col = identify_game_date_column(df_full)
        if date_col is None:
            continue

        # Slice this source by target date
        mask = df_full[date_col].astype(str).str.strip() == run_date
        slice_df = df_full[mask].copy().reset_index(drop=True)

        status, blocker = validate_true_date_slice(slice_df, run_date)

        req = identify_required_columns(slice_df) if len(slice_df) > 0 else {}
        has_req = all(req.values()) if req else False

        candidate_result: Dict[str, Any] = {
            "run_date": run_date,
            "status": status,
            "source_path": str(src),
            "n_rows": len(slice_df),
            "n_unique_game_ids": (
                int(slice_df["game_id"].nunique())
                if "game_id" in slice_df.columns and len(slice_df) > 0
                else 0
            ),
            "game_date_min": (
                str(slice_df[date_col].min()) if len(slice_df) > 0 else ""
            ),
            "game_date_max": (
                str(slice_df[date_col].max()) if len(slice_df) > 0 else ""
            ),
            "has_required_columns": has_req,
            "blocker_reason": blocker,
        }

        if status == TRUE_DATE_SLICE_READY:
            return candidate_result

        # Track best non-ready result (EMPTY < PARTIAL < BLOCKED)
        if best is None or _status_priority(status) > _status_priority(
            best["status"]
        ):
            best = candidate_result

    if best is None:
        # No candidate found at all
        return {
            "run_date": run_date,
            "status": TRUE_DATE_SLICE_EMPTY,
            "source_path": "",
            "n_rows": 0,
            "n_unique_game_ids": 0,
            "game_date_min": "",
            "game_date_max": "",
            "has_required_columns": False,
            "blocker_reason": "No source candidates found.",
        }

    return best


def _status_priority(status: str) -> int:
    """Higher = more informative / closer to READY."""
    priority_map = {
        TRUE_DATE_SLICE_EMPTY: 0,
        TRUE_DATE_SLICE_PARTIAL: 1,
        TRUE_DATE_SLICE_BLOCKED_MISSING_REQUIRED_COLUMNS: 2,
        TRUE_DATE_SLICE_BLOCKED_DATE_MISMATCH: 2,
        TRUE_DATE_SLICE_BLOCKED_DUPLICATE_GAME_ID: 2,
        TRUE_DATE_SLICE_READY: 3,
    }
    return priority_map.get(status, 0)


def _detect_source_game_date_range(
    source_candidates: List[Path],
) -> Tuple[str, str]:
    """Return (min_game_date, max_game_date) across all source candidates."""
    all_dates: List[str] = []
    for src in source_candidates:
        try:
            df = pd.read_csv(src, dtype=str, usecols=lambda c: c in ("game_date", "date"))
        except Exception:
            continue
        date_col = identify_game_date_column(df)
        if date_col is None:
            continue
        valid = df[date_col].dropna().astype(str).str.strip()
        valid = valid[valid.str.match(r"^\d{4}-\d{2}-\d{2}$")]
        all_dates.extend(valid.tolist())

    if not all_dates:
        return ("", "")
    return (min(all_dates), max(all_dates))


def _recommend_backfill_range(
    date_start: str,
    date_end: str,
    n_ready: int,
    detected_min: str,
    detected_max: str,
) -> Tuple[str, str]:
    """Return the recommended backfill date range.

    If the requested range had ready dates → use the requested range.
    Otherwise, recommend the true detected source range.
    """
    if n_ready > 0:
        return (date_start, date_end)
    if detected_min and detected_max:
        return (detected_min, detected_max)
    return ("", "")
