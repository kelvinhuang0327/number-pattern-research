"""
wbc_backend/recommendation/p26_per_date_true_replay_runner.py

P26 Per-Date True-Date Replay Runner.

For each true-date slice (from P25 output), runs an isolated replay:
  1. Load the P25 true-date slice CSV.
  2. Validate it (required columns, date match, non-empty).
  3. Apply the conservative P18/P16.6 policy filter to identify active entries.
  4. Settle using y_true.
  5. Emit a P26TrueDateReplayResult.

Policy constants (matching P18 / P16.6):
  edge_threshold    = 0.05
  max_stake_cap     = 0.0025  (25 units at 1000-unit bankroll → 0.25 units per bet)
  kelly_fraction    = 0.10
  odds_decimal_max  = 2.50

Does NOT:
  - Reuse P23 duplicated materialized inputs
  - Relabel 2025 rows as 2026 rows
  - Fabricate outcomes / odds / PnL

PAPER_ONLY — no production systems, no real bets.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

from wbc_backend.recommendation.p26_true_date_replay_contract import (
    P26_DATE_BLOCKED_NO_TRUE_DATE_SLICE,
    P26_DATE_BLOCKED_INVALID_TRUE_DATE_SLICE,
    P26_DATE_BLOCKED_P15_INPUT_BUILD_FAILED,
    P26_DATE_REPLAY_READY,
    P26TrueDateReplayResult,
)
from wbc_backend.recommendation.p26_true_date_replay_input_adapter import (
    convert_true_date_slice_to_replay_input,
    load_true_date_slice,
    validate_true_date_slice_for_replay,
    write_replay_input_for_date,
)

# ---------------------------------------------------------------------------
# Policy constants (P18 / P16.6 conservative policy)
# ---------------------------------------------------------------------------
EDGE_THRESHOLD: float = 0.05
MAX_STAKE_CAP: float = 0.0025          # fraction of bankroll per bet
KELLY_FRACTION: float = 0.10
ODDS_DECIMAL_MAX: float = 2.50

# ---------------------------------------------------------------------------
# Gate/column constants from P17 ledger schema
# ---------------------------------------------------------------------------
_GATE_COLUMN = "gate_decision"
_ELIGIBLE_GATE_VALUE = "P16_6_ELIGIBLE_PAPER_RECOMMENDATION"
_STAKE_COLUMN = "paper_stake_units"
_PNL_COLUMN = "pnl_units"
_WIN_COLUMN = "is_win"
_LOSS_COLUMN = "is_loss"
_PUSH_COLUMN = "is_push"
_SETTLEMENT_COLUMN = "settlement_status"
_ODDS_COLUMN = "odds_decimal"
_EDGE_COLUMN = "edge"


def run_true_date_replay_for_date(
    run_date: str,
    p25_slice_dir: Path,
    output_base_dir: Path,
) -> P26TrueDateReplayResult:
    """Run true-date replay for a single run_date.

    p25_slice_dir is the directory containing true_date_slices/<date>/
    output_base_dir is the base directory where per-date outputs will be written.
    """
    slice_csv = (
        Path(p25_slice_dir)
        / "true_date_slices"
        / run_date
        / "p15_true_date_input.csv"
    )

    # Load
    slice_df = load_true_date_slice(slice_csv)

    # Validate
    gate, reason = validate_true_date_slice_for_replay(slice_df, run_date)
    if gate != P26_DATE_REPLAY_READY:
        return _blocked_result(run_date, gate, reason, slice_df)

    # Convert to replay input (normalise columns)
    try:
        replay_df = convert_true_date_slice_to_replay_input(slice_df)
    except Exception as exc:
        return _blocked_result(
            run_date,
            P26_DATE_BLOCKED_P15_INPUT_BUILD_FAILED,
            f"Input conversion failed: {exc}",
            slice_df,
        )

    # Write replay input artifacts
    try:
        write_replay_input_for_date(run_date, replay_df, output_base_dir)
    except Exception:
        pass  # Non-fatal — the replay can continue without writing inputs

    # Compute replay statistics
    result = build_recommendation_rows_from_true_date_input(run_date, replay_df)
    return result


def build_recommendation_rows_from_true_date_input(
    run_date: str,
    replay_df: pd.DataFrame,
) -> P26TrueDateReplayResult:
    """Extract active entries and compute per-date replay statistics.

    Active entries are rows where gate_decision == P16_6_ELIGIBLE_PAPER_RECOMMENDATION.
    Settlement is derived from existing y_true / settlement columns in the P17 ledger.
    """
    n_slice_rows = len(replay_df)
    n_unique_game_ids = replay_df["game_id"].nunique() if "game_id" in replay_df.columns else 0

    # Identify active entries
    if _GATE_COLUMN in replay_df.columns:
        active = replay_df[replay_df[_GATE_COLUMN] == _ELIGIBLE_GATE_VALUE].copy()
    else:
        # Fall back: apply policy manually if no gate column
        active = _apply_policy_filter(replay_df).copy()

    n_active = len(active)

    if n_active == 0:
        # No active entries — still READY (the date is processed; policy blocked all)
        return P26TrueDateReplayResult(
            run_date=run_date,
            true_game_date=run_date,
            true_date_slice_status=P26_DATE_REPLAY_READY,
            n_slice_rows=n_slice_rows,
            n_unique_game_ids=n_unique_game_ids,
            date_matches_slice=True,
            replay_gate=P26_DATE_REPLAY_READY,
            n_active_paper_entries=0,
            n_settled_win=0,
            n_settled_loss=0,
            n_unsettled=0,
            total_stake_units=0.0,
            total_pnl_units=0.0,
            roi_units=0.0,
            hit_rate=0.0,
            game_id_coverage=0.0,
            paper_only=True,
            production_ready=False,
            blocker_reason="",
        )

    # Compute settlement from existing columns
    settled_win, settled_loss, unsettled = settle_true_date_replay(active)
    total_stake = float(active[_STAKE_COLUMN].sum()) if _STAKE_COLUMN in active.columns else 0.0
    total_pnl = float(active[_PNL_COLUMN].sum()) if _PNL_COLUMN in active.columns else 0.0
    roi = total_pnl / total_stake if total_stake > 0 else 0.0
    total_settled = settled_win + settled_loss
    hit_rate = settled_win / total_settled if total_settled > 0 else 0.0
    game_id_coverage = (
        active["game_id"].nunique() / n_unique_game_ids
        if n_unique_game_ids > 0 and "game_id" in active.columns
        else 0.0
    )

    return P26TrueDateReplayResult(
        run_date=run_date,
        true_game_date=run_date,
        true_date_slice_status=P26_DATE_REPLAY_READY,
        n_slice_rows=n_slice_rows,
        n_unique_game_ids=n_unique_game_ids,
        date_matches_slice=True,
        replay_gate=P26_DATE_REPLAY_READY,
        n_active_paper_entries=n_active,
        n_settled_win=settled_win,
        n_settled_loss=settled_loss,
        n_unsettled=unsettled,
        total_stake_units=total_stake,
        total_pnl_units=total_pnl,
        roi_units=roi,
        hit_rate=hit_rate,
        game_id_coverage=game_id_coverage,
        paper_only=True,
        production_ready=False,
        blocker_reason="",
    )


def settle_true_date_replay(
    active_df: pd.DataFrame,
) -> Tuple[int, int, int]:
    """Compute (n_settled_win, n_settled_loss, n_unsettled) from active entries.

    Uses existing settlement_status column if present; otherwise derives from y_true.
    Returns (settled_win, settled_loss, unsettled).
    """
    if _SETTLEMENT_COLUMN in active_df.columns:
        status = active_df[_SETTLEMENT_COLUMN].astype(str)
        settled_win = int((status == "SETTLED_WIN").sum())
        settled_loss = int((status == "SETTLED_LOSS").sum())
        unsettled = int(
            (~status.isin({"SETTLED_WIN", "SETTLED_LOSS"})).sum()
        )
        return settled_win, settled_loss, unsettled

    # Fall back to y_true + is_win / is_loss columns
    if _WIN_COLUMN in active_df.columns and _LOSS_COLUMN in active_df.columns:
        settled_win = int(active_df[_WIN_COLUMN].sum())
        settled_loss = int(active_df[_LOSS_COLUMN].sum())
        unsettled = len(active_df) - settled_win - settled_loss
        return settled_win, settled_loss, max(0, unsettled)

    # Last resort: derive from y_true + stake > 0
    if "y_true" in active_df.columns and "side" in active_df.columns:
        # side HOME: win if y_true == 1, else loss
        # side AWAY: win if y_true == 0, else loss
        wins = ((active_df["side"] == "HOME") & (active_df["y_true"] == 1)) | (
            (active_df["side"] == "AWAY") & (active_df["y_true"] == 0)
        )
        settled_win = int(wins.sum())
        settled_loss = len(active_df) - settled_win
        return settled_win, settled_loss, 0

    return 0, 0, len(active_df)


def summarize_true_date_replay_result(result: P26TrueDateReplayResult) -> Dict:
    """Return a JSON-serialisable dict for the replay result."""
    return {
        "run_date": result.run_date,
        "true_game_date": result.true_game_date,
        "true_date_slice_status": result.true_date_slice_status,
        "n_slice_rows": result.n_slice_rows,
        "n_unique_game_ids": result.n_unique_game_ids,
        "date_matches_slice": result.date_matches_slice,
        "replay_gate": result.replay_gate,
        "n_active_paper_entries": result.n_active_paper_entries,
        "n_settled_win": result.n_settled_win,
        "n_settled_loss": result.n_settled_loss,
        "n_unsettled": result.n_unsettled,
        "total_stake_units": result.total_stake_units,
        "total_pnl_units": result.total_pnl_units,
        "roi_units": result.roi_units,
        "hit_rate": result.hit_rate,
        "game_id_coverage": result.game_id_coverage,
        "paper_only": result.paper_only,
        "production_ready": result.production_ready,
        "blocker_reason": result.blocker_reason,
    }


def validate_true_date_replay_result(result: P26TrueDateReplayResult) -> bool:
    """Basic sanity checks on a replay result. Returns True if valid."""
    if result.paper_only is not True:
        return False
    if result.production_ready is not False:
        return False
    if result.replay_gate not in {
        P26_DATE_REPLAY_READY,
        P26_DATE_BLOCKED_NO_TRUE_DATE_SLICE,
        P26_DATE_BLOCKED_INVALID_TRUE_DATE_SLICE,
        P26_DATE_BLOCKED_P15_INPUT_BUILD_FAILED,
    }:
        return False
    if result.n_active_paper_entries < 0:
        return False
    if result.n_settled_win < 0 or result.n_settled_loss < 0:
        return False
    return True


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _blocked_result(
    run_date: str,
    gate: str,
    reason: str,
    slice_df: Optional[pd.DataFrame],
) -> P26TrueDateReplayResult:
    n_rows = len(slice_df) if slice_df is not None else 0
    n_ids = slice_df["game_id"].nunique() if (slice_df is not None and "game_id" in (slice_df.columns if slice_df is not None else [])) else 0
    return P26TrueDateReplayResult(
        run_date=run_date,
        true_game_date=run_date,
        true_date_slice_status=gate,
        n_slice_rows=n_rows,
        n_unique_game_ids=n_ids,
        date_matches_slice=False,
        replay_gate=gate,
        n_active_paper_entries=0,
        n_settled_win=0,
        n_settled_loss=0,
        n_unsettled=0,
        total_stake_units=0.0,
        total_pnl_units=0.0,
        roi_units=0.0,
        hit_rate=0.0,
        game_id_coverage=0.0,
        paper_only=True,
        production_ready=False,
        blocker_reason=reason,
    )


def _apply_policy_filter(df: pd.DataFrame) -> pd.DataFrame:
    """Apply P18/P16.6 policy filter if gate_decision column is missing.

    Uses: edge >= EDGE_THRESHOLD and odds_decimal <= ODDS_DECIMAL_MAX
    and stake_cap is already embedded as paper_stake_units <= MAX_STAKE_CAP * bankroll.
    """
    mask = pd.Series([True] * len(df), index=df.index)
    if _EDGE_COLUMN in df.columns:
        mask &= df[_EDGE_COLUMN] >= EDGE_THRESHOLD
    if _ODDS_COLUMN in df.columns:
        mask &= df[_ODDS_COLUMN] <= ODDS_DECIMAL_MAX
    return df[mask]
