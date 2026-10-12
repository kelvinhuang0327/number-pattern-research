"""
wbc_backend/simulation/p18_drawdown_diagnostics.py

P18 — Drawdown diagnostics for strategy risk repair.

Analyses WHY the P16 drawdown exceeded the 25% limit, providing:
  - Worst drawdown segment (start/end row, depth)
  - Consecutive loss clusters
  - Top loss outlier contribution
  - Policy exposure profile (stake & odds distribution)
  - Root cause categorisation

PnL convention (consistent with p13_strategy_simulator.py):
  - won bet: pnl = stake_fraction * (decimal_odds - 1)
  - lost bet: pnl = -stake_fraction
  - no-bet row:  pnl = 0.0

PAPER_ONLY: diagnostics only; no production bets.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import pandas as pd


# ── Data contracts ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class DrawdownSegment:
    start_row: int
    end_row: int
    peak_equity: float
    trough_equity: float
    drawdown_pct: float
    n_bets_in_segment: int


@dataclass(frozen=True)
class LossCluster:
    start_row: int
    end_row: int
    consecutive_losses: int
    total_loss: float


@dataclass(frozen=True)
class OutlierLoss:
    row_idx: int
    stake_fraction: float
    decimal_odds: float
    pnl: float
    cumulative_equity_before: float


@dataclass(frozen=True)
class PolicyExposureProfile:
    n_bets: int
    mean_stake: float
    max_stake: float
    median_stake: float
    p75_stake: float
    mean_odds: float
    max_odds: float
    median_odds: float
    p75_odds: float
    mean_edge: float
    hit_rate: float


@dataclass(frozen=True)
class DrawdownDiagnosticsReport:
    threshold: float
    n_eligible_bets: int
    max_drawdown_pct: float
    worst_segment: Optional[DrawdownSegment]
    loss_clusters: list[LossCluster]
    top_outlier_losses: list[OutlierLoss]
    exposure_profile: PolicyExposureProfile
    root_cause_flags: dict[str, bool]
    root_cause_summary: str


# ── Internal helpers ───────────────────────────────────────────────────────────

def _compute_pnl_for_filtered(df: pd.DataFrame) -> list[float]:
    """Compute PnL list for rows where should_bet is True (or all rows if column absent)."""
    pnl_list: list[float] = []
    for _, row in df.iterrows():
        if not row.get("should_bet", True):
            continue
        stake = float(row.get("stake_fraction", 0.0))
        odds = float(row.get("decimal_odds", 1.0))
        y = int(row.get("y_true", 0))
        if stake <= 0:
            pnl_list.append(0.0)
        elif y == 1:
            pnl_list.append(stake * (odds - 1.0))
        else:
            pnl_list.append(-stake)
    return pnl_list


def _filter_ledger(ledger_df: pd.DataFrame, threshold: float) -> pd.DataFrame:
    """
    Filter ledger to capped_kelly policy rows with edge >= threshold.
    Edge is computed as p_model - p_market if not present.
    Returns rows sorted by row_idx.
    """
    df = ledger_df.copy()
    if "policy" in df.columns:
        df = df[df["policy"] == "capped_kelly"].copy()
    if "edge" not in df.columns:
        if "p_model" in df.columns and "p_market" in df.columns:
            df["edge"] = df["p_model"] - df["p_market"]
        else:
            df["edge"] = 0.0
    df = df[df["edge"] >= threshold].copy()
    df["should_bet"] = True
    if "row_idx" in df.columns:
        df = df.sort_values("row_idx").reset_index(drop=True)
    return df


def _build_equity_curve(pnl_list: list[float]) -> list[float]:
    equity = 1.0
    curve = [equity]
    for p in pnl_list:
        equity += p
        curve.append(equity)
    return curve


# ── Public API ─────────────────────────────────────────────────────────────────

def summarize_drawdown_segments(
    ledger_df: pd.DataFrame,
    threshold: float,
    max_segments: int = 10,
) -> list[DrawdownSegment]:
    """
    Identify and sort drawdown segments from the equity curve.

    Returns up to max_segments segments sorted by drawdown_pct descending.
    """
    df = _filter_ledger(ledger_df, threshold)
    pnl = _compute_pnl_for_filtered(df)
    if not pnl:
        return []

    curve = _build_equity_curve(pnl)
    segments: list[DrawdownSegment] = []

    peak_val = curve[0]
    peak_idx = 0
    in_drawdown = False
    dd_start = 0

    for i in range(1, len(curve)):
        if curve[i] > peak_val:
            if in_drawdown:
                # close segment
                trough = min(curve[dd_start : i + 1])
                dd_pct = (peak_val - trough) / peak_val if peak_val > 0 else 0.0
                n_bets = i - dd_start
                segments.append(
                    DrawdownSegment(
                        start_row=dd_start,
                        end_row=i - 1,
                        peak_equity=peak_val,
                        trough_equity=trough,
                        drawdown_pct=float(dd_pct * 100),
                        n_bets_in_segment=n_bets,
                    )
                )
                in_drawdown = False
            peak_val = curve[i]
            peak_idx = i
        elif curve[i] < peak_val:
            if not in_drawdown:
                in_drawdown = True
                dd_start = peak_idx

    # Close any open segment at end
    if in_drawdown:
        trough = min(curve[dd_start:])
        dd_pct = (peak_val - trough) / peak_val if peak_val > 0 else 0.0
        segments.append(
            DrawdownSegment(
                start_row=dd_start,
                end_row=len(curve) - 1,
                peak_equity=peak_val,
                trough_equity=trough,
                drawdown_pct=float(dd_pct * 100),
                n_bets_in_segment=len(curve) - 1 - dd_start,
            )
        )

    segments.sort(key=lambda s: s.drawdown_pct, reverse=True)
    return segments[:max_segments]


def identify_loss_clusters(
    ledger_df: pd.DataFrame,
    threshold: float,
) -> list[LossCluster]:
    """
    Identify consecutive loss clusters (runs of >= 2 consecutive losses).

    Returns clusters sorted by consecutive_losses descending.
    """
    df = _filter_ledger(ledger_df, threshold)
    pnl = _compute_pnl_for_filtered(df)
    if not pnl:
        return []

    clusters: list[LossCluster] = []
    streak_start = -1
    streak_len = 0
    streak_loss = 0.0

    for i, p in enumerate(pnl):
        if p < 0:
            if streak_len == 0:
                streak_start = i
            streak_len += 1
            streak_loss += p
        else:
            if streak_len >= 2:
                clusters.append(
                    LossCluster(
                        start_row=streak_start,
                        end_row=i - 1,
                        consecutive_losses=streak_len,
                        total_loss=float(streak_loss),
                    )
                )
            streak_start = -1
            streak_len = 0
            streak_loss = 0.0

    # Close trailing streak
    if streak_len >= 2:
        clusters.append(
            LossCluster(
                start_row=streak_start,
                end_row=len(pnl) - 1,
                consecutive_losses=streak_len,
                total_loss=float(streak_loss),
            )
        )

    clusters.sort(key=lambda c: c.consecutive_losses, reverse=True)
    return clusters


def summarize_outlier_loss_contribution(
    ledger_df: pd.DataFrame,
    threshold: float,
    top_n: int = 10,
) -> list[OutlierLoss]:
    """
    Identify top loss outliers by absolute PnL magnitude.

    Returns up to top_n losing bets with largest absolute loss.
    """
    df = _filter_ledger(ledger_df, threshold)
    records: list[OutlierLoss] = []
    equity = 1.0

    for i, (_, row) in enumerate(df.iterrows()):
        stake = float(row.get("stake_fraction", 0.0))
        odds = float(row.get("decimal_odds", 1.0))
        y = int(row.get("y_true", 0))
        row_idx = int(row.get("row_idx", i))

        if stake > 0:
            if y == 1:
                pnl = stake * (odds - 1.0)
            else:
                pnl = -stake
        else:
            pnl = 0.0

        if pnl < 0:
            records.append(
                OutlierLoss(
                    row_idx=row_idx,
                    stake_fraction=float(stake),
                    decimal_odds=float(odds),
                    pnl=float(pnl),
                    cumulative_equity_before=float(equity),
                )
            )
        equity += pnl

    records.sort(key=lambda r: r.pnl)  # most negative first
    return records[:top_n]


def compute_policy_exposure_profile(
    ledger_df: pd.DataFrame,
    threshold: float,
) -> PolicyExposureProfile:
    """
    Compute distribution of stake_fraction and decimal_odds for filtered bets.
    """
    df = _filter_ledger(ledger_df, threshold)

    if df.empty:
        return PolicyExposureProfile(
            n_bets=0,
            mean_stake=0.0, max_stake=0.0, median_stake=0.0, p75_stake=0.0,
            mean_odds=0.0, max_odds=0.0, median_odds=0.0, p75_odds=0.0,
            mean_edge=0.0, hit_rate=0.0,
        )

    stakes = df["stake_fraction"].astype(float)
    odds = df["decimal_odds"].astype(float)
    edge = df["edge"].astype(float) if "edge" in df.columns else (
        df["p_model"] - df["p_market"]
    ).astype(float) if "p_model" in df.columns else pd.Series(dtype=float)
    y = df["y_true"].astype(int)

    return PolicyExposureProfile(
        n_bets=int(len(df)),
        mean_stake=float(stakes.mean()),
        max_stake=float(stakes.max()),
        median_stake=float(stakes.median()),
        p75_stake=float(stakes.quantile(0.75)),
        mean_odds=float(odds.mean()),
        max_odds=float(odds.max()),
        median_odds=float(odds.median()),
        p75_odds=float(odds.quantile(0.75)),
        mean_edge=float(edge.mean()) if not edge.empty else 0.0,
        hit_rate=float(y.mean()),
    )


# ── Master diagnostic function ─────────────────────────────────────────────────

def run_drawdown_diagnostics(
    ledger_df: pd.DataFrame,
    threshold: float,
) -> DrawdownDiagnosticsReport:
    """
    Run full drawdown diagnostic on capped_kelly rows with edge >= threshold.

    Returns DrawdownDiagnosticsReport with root cause classification.
    """
    df = _filter_ledger(ledger_df, threshold)
    pnl = _compute_pnl_for_filtered(df)

    # Compute max drawdown
    curve = _build_equity_curve(pnl)
    peak = curve[0]
    max_dd = 0.0
    for v in curve[1:]:
        if v > peak:
            peak = v
        if peak > 0:
            dd = (peak - v) / peak
            if dd > max_dd:
                max_dd = dd
    max_dd_pct = float(max_dd * 100)

    segments = summarize_drawdown_segments(ledger_df, threshold)
    clusters = identify_loss_clusters(ledger_df, threshold)
    outliers = summarize_outlier_loss_contribution(ledger_df, threshold)
    exposure = compute_policy_exposure_profile(ledger_df, threshold)

    # Root cause flags
    high_stake = exposure.mean_stake > 0.02
    high_odds = exposure.mean_odds > 2.5
    long_clusters = len(clusters) > 0 and clusters[0].consecutive_losses >= 5
    clustered_losses = len(clusters) >= 5
    broad_weakness = exposure.hit_rate < 0.50

    root_causes: list[str] = []
    if high_stake:
        root_causes.append(f"HIGH_STAKE (mean={exposure.mean_stake:.4f})")
    if high_odds:
        root_causes.append(f"HIGH_ODDS (mean={exposure.mean_odds:.2f})")
    if long_clusters:
        root_causes.append(
            f"LONG_LOSS_STREAK (max={clusters[0].consecutive_losses})"
        )
    if clustered_losses:
        root_causes.append(f"MANY_CLUSTERS ({len(clusters)})")
    if broad_weakness:
        root_causes.append(f"LOW_HIT_RATE ({exposure.hit_rate:.3f})")

    root_cause_summary = "; ".join(root_causes) if root_causes else "NO_CLEAR_CAUSE"

    return DrawdownDiagnosticsReport(
        threshold=threshold,
        n_eligible_bets=len(df),
        max_drawdown_pct=max_dd_pct,
        worst_segment=segments[0] if segments else None,
        loss_clusters=clusters,
        top_outlier_losses=outliers,
        exposure_profile=exposure,
        root_cause_flags={
            "high_stake": high_stake,
            "high_odds": high_odds,
            "long_clusters": long_clusters,
            "many_clusters": clustered_losses,
            "broad_weakness": broad_weakness,
        },
        root_cause_summary=root_cause_summary,
    )
