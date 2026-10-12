"""
wbc_backend/recommendation/p17_paper_ledger_writer.py

P17 Paper Recommendation Ledger — core ledger construction and settlement logic.

Functions:
  build_paper_ledger(recommendation_rows_df, bankroll_units) -> pd.DataFrame
  settle_ledger_entries(ledger_df) -> pd.DataFrame
  summarize_paper_ledger(settled_df, source_p16_6_gate) -> PaperLedgerSummary
  validate_paper_ledger_contract(settled_df) -> ValidationResult

Settlement rules:
  - Only P16_6_ELIGIBLE_PAPER_RECOMMENDATION rows become active paper entries.
  - Blocked rows are included as audit rows with paper_stake_units=0 and
    settlement_status=UNSETTLED_NOT_RECOMMENDED.
  - y_true=1 and is_home_win_side → pnl_units = stake * (odds_decimal - 1)
  - y_true=0 and is_home_win_side → pnl_units = -stake
  - Side mapping: side column value determines which y_true direction means win.
    'HOME' side: y_true=1 → win (home team won), y_true=0 → loss.
    'AWAY' side: y_true=0 → win (home team lost = away win), y_true=1 → loss.
  - Missing y_true → UNSETTLED_MISSING_OUTCOME, pnl_units=0.
  - Invalid odds (<=1.0 or NaN) → UNSETTLED_INVALID_ODDS, pnl_units=0.
  - Invalid stake (<0 or NaN) → UNSETTLED_INVALID_STAKE, pnl_units=0.

PAPER_ONLY — no production DB, no live TSL, no real bets.
"""
from __future__ import annotations

import hashlib
import math
from typing import Optional

import pandas as pd

from wbc_backend.recommendation.p17_paper_ledger_contract import (
    CREATED_FROM,
    P16_6_ELIGIBLE_DECISION,
    P17_BLOCKED_CONTRACT_VIOLATION,
    P17_BLOCKED_NO_ACTIVE_RECOMMENDATIONS,
    P17_BLOCKED_SETTLEMENT_JOIN_INCOMPLETE,
    P17_PAPER_LEDGER_READY,
    SETTLED_LOSS,
    SETTLED_PUSH,
    SETTLED_WIN,
    SOURCE_PHASE,
    UNSETTLED_INVALID_ODDS,
    UNSETTLED_INVALID_STAKE,
    UNSETTLED_MISSING_OUTCOME,
    UNSETTLED_NOT_RECOMMENDED,
    ALL_SETTLEMENT_STATUSES,
    PaperLedgerSummary,
    ValidationResult,
)


def _make_ledger_id(recommendation_id: str, date: str, side: str) -> str:
    """Deterministic ledger row ID from recommendation_id + date + side."""
    raw = f"{recommendation_id}|{date}|{side}"
    return "L17-" + hashlib.md5(raw.encode()).hexdigest().upper()[:12]


def _is_finite(value: object) -> bool:
    """Return True if value is a finite real number."""
    try:
        return math.isfinite(float(value))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False


def _side_win_for_y_true(side: str, y_true: float) -> bool:
    """
    Determine if the recommended side won given y_true.

    Convention (from P15/P16 dataset):
      y_true=1 → home team won
      y_true=0 → home team lost (away team won)

      side='HOME' → recommended home team → win if y_true=1
      side='AWAY' → recommended away team → win if y_true=0
      Any other side string is treated as HOME.
    """
    if side.upper() == "AWAY":
        return y_true == 0.0
    return y_true == 1.0


def build_paper_ledger(
    recommendation_rows_df: pd.DataFrame,
    bankroll_units: float = 100.0,
) -> pd.DataFrame:
    """
    Convert P16.6 recommendation rows into a P17 paper ledger DataFrame.

    Active entries (gate_decision == P16_6_ELIGIBLE_PAPER_RECOMMENDATION):
      - paper_stake_units = bankroll_units * paper_stake_fraction
      - Settlement fields initialised to UNSETTLED_MISSING_OUTCOME (no y_true yet)

    Audit entries (all other gate_decisions):
      - paper_stake_units = 0.0
      - settlement_status = UNSETTLED_NOT_RECOMMENDED

    Parameters
    ----------
    recommendation_rows_df : DataFrame
        Output of run_p16_6_recommendation_gate_with_p18_policy.py
        (recommendation_rows.csv).
    bankroll_units : float
        Hypothetical starting bankroll (default 100.0 units).

    Returns
    -------
    DataFrame
        All input rows converted to ledger rows (active + audit).
    """
    df = recommendation_rows_df.copy()
    rows = []

    required_cols = [
        "recommendation_id", "game_id", "date", "side",
        "p_model", "p_market", "edge", "odds_decimal",
        "paper_stake_fraction", "gate_decision", "gate_reason",
        "source_model", "paper_only", "production_ready",
    ]
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Missing required column in recommendation rows: {col}")

    # Optional risk profile columns (may or may not be present)
    def _get_float(row: pd.Series, col: str, default: float = 0.0) -> float:
        val = row.get(col, default)
        try:
            f = float(val)
            return f if math.isfinite(f) else default
        except (TypeError, ValueError):
            return default

    def _get_int(row: pd.Series, col: str, default: int = 0) -> int:
        val = row.get(col, default)
        try:
            return int(val)
        except (TypeError, ValueError):
            return default

    for _, row in df.iterrows():
        gate_decision = str(row.get("gate_decision", ""))
        is_active = (gate_decision == P16_6_ELIGIBLE_DECISION)

        stake_frac = _get_float(row, "paper_stake_fraction", 0.0)
        if not _is_finite(stake_frac) or stake_frac < 0:
            stake_frac = 0.0

        stake_units = bankroll_units * stake_frac if is_active else 0.0

        rec_id = str(row.get("recommendation_id", ""))
        date = str(row.get("date", ""))
        side = str(row.get("side", "HOME"))
        ledger_id = _make_ledger_id(rec_id, date, side)

        # y_true from recommendation rows (may be present if joined)
        y_true_raw = row.get("y_true", None)
        try:
            y_true: Optional[float] = float(y_true_raw)
            if not math.isfinite(y_true):
                y_true = None
        except (TypeError, ValueError):
            y_true = None

        rows.append({
            "ledger_id": ledger_id,
            "recommendation_id": rec_id,
            "game_id": str(row.get("game_id", "")),
            "date": date,
            "side": side,
            "p_model": _get_float(row, "p_model"),
            "p_market": _get_float(row, "p_market"),
            "edge": _get_float(row, "edge"),
            "odds_decimal": _get_float(row, "odds_decimal", 0.0),
            "paper_stake_fraction": stake_frac,
            "paper_stake_units": stake_units,
            "policy_id": str(row.get("p18_policy_id", "")),
            "strategy_policy": str(row.get("strategy_policy", "")),
            "gate_decision": gate_decision,
            "gate_reason": str(row.get("gate_reason", "")),
            "paper_only": bool(row.get("paper_only", True)),
            "production_ready": bool(row.get("production_ready", False)),
            "source_phase": SOURCE_PHASE,
            "created_from": CREATED_FROM,
            "y_true": y_true,
            # Settlement — computed by settle_ledger_entries()
            "settlement_status": UNSETTLED_NOT_RECOMMENDED if not is_active else UNSETTLED_MISSING_OUTCOME,
            "settlement_reason": "blocked at P16.6 gate" if not is_active else "pending settlement",
            "pnl_units": 0.0,
            "roi": 0.0,
            "is_win": False,
            "is_loss": False,
            "is_push": False,
            "risk_profile_max_drawdown": _get_float(row, "p18_policy_max_drawdown_pct"),
            "risk_profile_sharpe": _get_float(row, "p18_policy_sharpe_ratio"),
            "risk_profile_n_bets": _get_int(row, "p18_policy_n_bets"),
        })

    return pd.DataFrame(rows)


def settle_ledger_entries(ledger_df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute settlement fields for all ledger rows.

    Only active paper entries (gate_decision == P16_6_ELIGIBLE_PAPER_RECOMMENDATION)
    are eligible for SETTLED_WIN / SETTLED_LOSS. All other rows remain
    UNSETTLED_NOT_RECOMMENDED.

    Modifies and returns a copy of ledger_df with updated settlement columns.
    """
    df = ledger_df.copy()

    settled_rows = []
    for idx, row in df.iterrows():
        gate_decision = str(row.get("gate_decision", ""))
        is_active = (gate_decision == P16_6_ELIGIBLE_DECISION)

        # Audit rows — not eligible for settlement
        if not is_active:
            settled_rows.append({
                "settlement_status": UNSETTLED_NOT_RECOMMENDED,
                "settlement_reason": "blocked at P16.6 gate",
                "pnl_units": 0.0,
                "roi": 0.0,
                "is_win": False,
                "is_loss": False,
                "is_push": False,
            })
            continue

        stake_units = float(row.get("paper_stake_units", 0.0))
        odds = float(row.get("odds_decimal", 0.0))
        side = str(row.get("side", "HOME"))
        y_true = row.get("y_true", None)

        # Validate stake
        if not _is_finite(stake_units) or stake_units < 0:
            settled_rows.append({
                "settlement_status": UNSETTLED_INVALID_STAKE,
                "settlement_reason": f"invalid stake_units={stake_units}",
                "pnl_units": 0.0,
                "roi": 0.0,
                "is_win": False,
                "is_loss": False,
                "is_push": False,
            })
            continue

        # Validate odds
        if not _is_finite(odds) or odds <= 1.0:
            settled_rows.append({
                "settlement_status": UNSETTLED_INVALID_ODDS,
                "settlement_reason": f"invalid odds_decimal={odds}",
                "pnl_units": 0.0,
                "roi": 0.0,
                "is_win": False,
                "is_loss": False,
                "is_push": False,
            })
            continue

        # Check y_true availability
        if y_true is None:
            settled_rows.append({
                "settlement_status": UNSETTLED_MISSING_OUTCOME,
                "settlement_reason": "y_true is missing",
                "pnl_units": 0.0,
                "roi": 0.0,
                "is_win": False,
                "is_loss": False,
                "is_push": False,
            })
            continue

        # Compute P&L
        won = _side_win_for_y_true(side, float(y_true))
        pnl = stake_units * (odds - 1.0) if won else -stake_units
        roi = pnl / stake_units if stake_units > 0 else 0.0

        settled_rows.append({
            "settlement_status": SETTLED_WIN if won else SETTLED_LOSS,
            "settlement_reason": f"y_true={y_true}, side={side}, odds={odds:.4f}",
            "pnl_units": pnl,
            "roi": roi,
            "is_win": won,
            "is_loss": not won,
            "is_push": False,
        })

    settled_df = pd.DataFrame(settled_rows, index=df.index)
    for col in ["settlement_status", "settlement_reason", "pnl_units", "roi",
                "is_win", "is_loss", "is_push"]:
        df[col] = settled_df[col]

    return df


def summarize_paper_ledger(
    settled_df: pd.DataFrame,
    source_p16_6_gate: str = "P16_6_PAPER_RECOMMENDATION_GATE_READY",
    duplicate_game_id_count: int = 0,
    unmatched_recommendation_count: int = 0,
) -> PaperLedgerSummary:
    """Aggregate the settled ledger into a PaperLedgerSummary."""
    active = settled_df[settled_df["gate_decision"] == P16_6_ELIGIBLE_DECISION]

    n_rec = len(settled_df)
    n_active = len(active)

    n_win = int((active["settlement_status"] == SETTLED_WIN).sum())
    n_loss = int((active["settlement_status"] == SETTLED_LOSS).sum())
    n_push = int((active["settlement_status"] == SETTLED_PUSH).sum())
    n_unsettled = n_active - n_win - n_loss - n_push

    total_stake = float(active["paper_stake_units"].sum())
    total_pnl = float(active["pnl_units"].sum())
    roi = total_pnl / total_stake if total_stake > 0 else 0.0

    resolved = n_win + n_loss
    hit_rate = n_win / resolved if resolved > 0 else 0.0

    avg_edge = float(active["edge"].mean()) if n_active > 0 else 0.0
    avg_odds = float(active["odds_decimal"].mean()) if n_active > 0 else 0.0

    # Risk profile from active rows (all same, from P18 policy)
    max_dd = float(active["risk_profile_max_drawdown"].iloc[0]) if n_active > 0 else 0.0
    sharpe = float(active["risk_profile_sharpe"].iloc[0]) if n_active > 0 else 0.0

    # Settlement coverage = fraction of active entries that are settled (win or loss)
    coverage = resolved / n_active if n_active > 0 else 0.0

    # Gate decision
    if n_active == 0:
        gate = P17_BLOCKED_NO_ACTIVE_RECOMMENDATIONS
    elif n_unsettled == n_active:
        gate = P17_BLOCKED_SETTLEMENT_JOIN_INCOMPLETE
    else:
        gate = P17_PAPER_LEDGER_READY

    return PaperLedgerSummary(
        p17_gate=gate,
        source_p16_6_gate=source_p16_6_gate,
        n_recommendation_rows=n_rec,
        n_active_paper_entries=n_active,
        n_settled_win=n_win,
        n_settled_loss=n_loss,
        n_settled_push=n_push,
        n_unsettled=n_unsettled,
        total_stake_units=total_stake,
        total_pnl_units=total_pnl,
        roi_units=roi,
        hit_rate=hit_rate,
        avg_edge=avg_edge,
        avg_odds_decimal=avg_odds,
        max_drawdown_pct=max_dd,
        sharpe_ratio=sharpe,
        settlement_join_coverage=coverage,
        duplicate_game_id_count=duplicate_game_id_count,
        unmatched_recommendation_count=unmatched_recommendation_count,
        paper_only=True,
        production_ready=False,
    )


def validate_paper_ledger_contract(settled_df: pd.DataFrame) -> ValidationResult:
    """
    Enforce hard safety invariants on the settled ledger.

    Returns ValidationResult(valid=False, ...) on first violation found.
    """
    # 1. production_ready must always be False
    if "production_ready" in settled_df.columns:
        bad = settled_df["production_ready"].astype(bool)
        if bad.any():
            return ValidationResult(
                valid=False,
                error_code=P17_BLOCKED_CONTRACT_VIOLATION,
                error_message="production_ready=True found in ledger rows — safety violation",
            )

    # 2. paper_only must always be True
    if "paper_only" in settled_df.columns:
        bad2 = ~settled_df["paper_only"].astype(bool)
        if bad2.any():
            return ValidationResult(
                valid=False,
                error_code=P17_BLOCKED_CONTRACT_VIOLATION,
                error_message="paper_only=False found in ledger rows — safety violation",
            )

    # 3. settlement_status must be in known set
    if "settlement_status" in settled_df.columns:
        unknown = ~settled_df["settlement_status"].isin(ALL_SETTLEMENT_STATUSES)
        if unknown.any():
            bad_vals = settled_df.loc[unknown, "settlement_status"].unique().tolist()
            return ValidationResult(
                valid=False,
                error_code=P17_BLOCKED_CONTRACT_VIOLATION,
                error_message=f"Unknown settlement_status values: {bad_vals}",
            )

    # 4. Blocked rows must have paper_stake_units == 0
    if "gate_decision" in settled_df.columns and "paper_stake_units" in settled_df.columns:
        blocked = settled_df["gate_decision"] != P16_6_ELIGIBLE_DECISION
        bad_stake = settled_df.loc[blocked, "paper_stake_units"] != 0.0
        if bad_stake.any():
            return ValidationResult(
                valid=False,
                error_code=P17_BLOCKED_CONTRACT_VIOLATION,
                error_message="Blocked rows have non-zero paper_stake_units — invariant violated",
            )

    # 5. pnl_units for UNSETTLED rows must be 0.0
    if "settlement_status" in settled_df.columns and "pnl_units" in settled_df.columns:
        unsettled_mask = settled_df["settlement_status"].str.startswith("UNSETTLED")
        bad_pnl = settled_df.loc[unsettled_mask, "pnl_units"] != 0.0
        if bad_pnl.any():
            return ValidationResult(
                valid=False,
                error_code=P17_BLOCKED_CONTRACT_VIOLATION,
                error_message="UNSETTLED rows have non-zero pnl_units — invariant violated",
            )

    return ValidationResult(valid=True, error_code=None, error_message=None)
