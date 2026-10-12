"""
wbc_backend/recommendation/p26_true_date_replay_input_adapter.py

P26 True-Date Replay Input Adapter.

Loads and validates P25 true-date slices for use in P26 replay.

Rules:
  - Only rows where true game_date (date column) == run_date are accepted.
  - Required columns must be present.
  - Empty slices block the date.
  - Missing required columns block the date.
  - Do not relabel dates.
  - Do not fabricate missing odds / predictions / outcomes.

Output per date:
  outputs/predictions/PAPER/<date>/p26_true_date_replay_input/replay_input.csv
  outputs/predictions/PAPER/<date>/p26_true_date_replay_input/replay_input_summary.json

PAPER_ONLY — no production systems, no real bets.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Tuple

import pandas as pd

from wbc_backend.recommendation.p26_true_date_replay_contract import (
    P26_DATE_BLOCKED_INVALID_TRUE_DATE_SLICE,
    P26_DATE_BLOCKED_NO_TRUE_DATE_SLICE,
    P26_DATE_REPLAY_READY,
)

# ---------------------------------------------------------------------------
# Column requirements
# ---------------------------------------------------------------------------
_REQUIRED_EXACT = frozenset({"game_id", "y_true", "p_market", "odds_decimal"})
_DATE_COLUMN_CANDIDATES = frozenset({"game_date", "date"})
_PRED_COLUMN_CANDIDATES = frozenset({"p_model", "p_oof"})

# Columns that are already computed in P17 ledger slices
_GATE_COLUMN = "gate_decision"
_ELIGIBLE_GATE_VALUE = "P16_6_ELIGIBLE_PAPER_RECOMMENDATION"
_STAKE_COLUMN = "paper_stake_units"
_PNL_COLUMN = "pnl_units"
_WIN_COLUMN = "is_win"
_LOSS_COLUMN = "is_loss"
_SETTLEMENT_COLUMN = "settlement_status"


def load_true_date_slice(slice_path: Path) -> Optional[pd.DataFrame]:
    """Load a P25 true-date slice CSV. Returns None if the file is missing."""
    try:
        path = Path(slice_path)
        if not path.exists():
            return None
        return pd.read_csv(path)
    except Exception:
        return None


def validate_true_date_slice_for_replay(
    slice_df: Optional[pd.DataFrame],
    run_date: str,
) -> Tuple[str, str]:
    """Validate a true-date slice DataFrame for P26 replay.

    Returns (gate, blocker_reason).
    gate is one of P26_DATE_REPLAY_READY, P26_DATE_BLOCKED_NO_TRUE_DATE_SLICE,
    P26_DATE_BLOCKED_INVALID_TRUE_DATE_SLICE.
    """
    if slice_df is None or len(slice_df) == 0:
        return (
            P26_DATE_BLOCKED_NO_TRUE_DATE_SLICE,
            f"No true-date slice rows for {run_date}.",
        )

    cols = set(slice_df.columns)

    # Check required exact columns
    missing_exact = _REQUIRED_EXACT - cols
    if missing_exact:
        return (
            P26_DATE_BLOCKED_INVALID_TRUE_DATE_SLICE,
            f"Missing required columns: {sorted(missing_exact)}",
        )

    # Check date column
    date_col = _get_date_column(slice_df)
    if date_col is None:
        return (
            P26_DATE_BLOCKED_INVALID_TRUE_DATE_SLICE,
            "No date column (game_date or date) found.",
        )

    # Check pred column
    if not (cols & _PRED_COLUMN_CANDIDATES):
        return (
            P26_DATE_BLOCKED_INVALID_TRUE_DATE_SLICE,
            "Missing prediction column (p_model or p_oof).",
        )

    # Validate that all rows have the correct date
    dates_in_slice = slice_df[date_col].astype(str).unique().tolist()
    if any(d != run_date for d in dates_in_slice):
        wrong = [d for d in dates_in_slice if d != run_date]
        return (
            P26_DATE_BLOCKED_INVALID_TRUE_DATE_SLICE,
            f"Slice contains rows with wrong date: {wrong[:3]}. Expected {run_date}.",
        )

    return P26_DATE_REPLAY_READY, ""


def convert_true_date_slice_to_replay_input(
    slice_df: pd.DataFrame,
) -> pd.DataFrame:
    """Return the slice DataFrame ready for replay (pass-through of valid slice).

    The P25 slices are already processed P17 ledger rows. This function
    ensures date column normalisation and returns the slice as-is.
    No fabrication — only column renaming for consistent access.
    """
    df = slice_df.copy()
    # Normalise: if 'date' column exists but 'game_date' does not, alias it
    if "date" in df.columns and "game_date" not in df.columns:
        df = df.rename(columns={"date": "game_date"})
    return df


def write_replay_input_for_date(
    run_date: str,
    slice_df: pd.DataFrame,
    output_base_dir: Path,
) -> Tuple[Path, Path]:
    """Write replay_input.csv and replay_input_summary.json for run_date.

    Returns (csv_path, summary_path).
    """
    out_dir = Path(output_base_dir) / run_date / "p26_true_date_replay_input"
    out_dir.mkdir(parents=True, exist_ok=True)

    csv_path = out_dir / "replay_input.csv"
    slice_df.to_csv(csv_path, index=False)

    summary = summarize_replay_input(slice_df, run_date, str(csv_path))
    summary_path = out_dir / "replay_input_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, default=str))

    return csv_path, summary_path


def summarize_replay_input(
    input_df: Optional[pd.DataFrame],
    run_date: str = "",
    source_path: str = "",
) -> Dict:
    """Return a JSON-serialisable summary dict for the replay input."""
    if input_df is None or len(input_df) == 0:
        return {
            "run_date": run_date,
            "source_path": source_path,
            "n_rows": 0,
            "n_unique_game_ids": 0,
            "n_active_entries": 0,
            "n_blocked_entries": 0,
            "total_stake_units": 0.0,
            "total_pnl_units": 0.0,
            "content_hash": "",
            "paper_only": True,
            "production_ready": False,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    n_rows = len(input_df)
    n_unique_game_ids = input_df["game_id"].nunique() if "game_id" in input_df.columns else 0

    # Active entries have the eligible gate decision
    if _GATE_COLUMN in input_df.columns:
        active = input_df[input_df[_GATE_COLUMN] == _ELIGIBLE_GATE_VALUE]
    else:
        active = input_df  # treat all as active if no gate column

    n_active = len(active)
    n_blocked = n_rows - n_active
    stake = float(active[_STAKE_COLUMN].sum()) if _STAKE_COLUMN in active.columns else 0.0
    pnl = float(active[_PNL_COLUMN].sum()) if _PNL_COLUMN in active.columns else 0.0

    # Content hash for determinism check
    try:
        buf = input_df.sort_values("game_id").to_csv(index=False) if "game_id" in input_df.columns else input_df.to_csv(index=False)
        content_hash = hashlib.sha256(buf.encode()).hexdigest()
    except Exception:
        content_hash = ""

    return {
        "run_date": run_date,
        "source_path": source_path,
        "n_rows": n_rows,
        "n_unique_game_ids": n_unique_game_ids,
        "n_active_entries": n_active,
        "n_blocked_entries": n_blocked,
        "total_stake_units": stake,
        "total_pnl_units": pnl,
        "content_hash": content_hash,
        "paper_only": True,
        "production_ready": False,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_date_column(df: pd.DataFrame) -> Optional[str]:
    """Return 'game_date' if present, else 'date', else None."""
    for col in ("game_date", "date"):
        if col in df.columns:
            return col
    return None
