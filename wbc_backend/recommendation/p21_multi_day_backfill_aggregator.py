"""
wbc_backend/recommendation/p21_multi_day_backfill_aggregator.py

P21 — Aggregate per-date P20 results into a multi-day backfill summary.

PAPER_ONLY — no production systems, no real bets.
"""
from __future__ import annotations

import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Union

from wbc_backend.recommendation.p21_daily_artifact_discovery import (
    ValidationResult,
    P21MissingArtifactReport,
)
from wbc_backend.recommendation.p21_multi_day_backfill_contract import (
    P21BackfillAggregateSummary,
    P21BackfillDateResult,
    P21BackfillGateResult,
    P21_BLOCKED_CONTRACT_VIOLATION,
    P21_BLOCKED_NO_READY_DAILY_RUNS,
    P21_MULTI_DAY_PAPER_BACKFILL_READY,
)

DiscoveryItem = Union[P21BackfillDateResult, P21MissingArtifactReport]


# ---------------------------------------------------------------------------
# Weighted metric helpers
# ---------------------------------------------------------------------------


def compute_aggregate_roi(total_pnl_units: float, total_stake_units: float) -> float:
    """Stake-weighted aggregate ROI.  Returns 0.0 if stake is zero."""
    if total_stake_units == 0.0:
        return 0.0
    return total_pnl_units / total_stake_units


def compute_aggregate_hit_rate(total_wins: int, total_losses: int) -> float:
    """Settled-bet-weighted hit rate.  Returns 0.0 if no settled bets."""
    total_settled = total_wins + total_losses
    if total_settled == 0:
        return 0.0
    return total_wins / total_settled


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def aggregate_backfill_results(
    date_results: list[DiscoveryItem],
) -> P21BackfillAggregateSummary:
    """
    Aggregate per-date discovery results into a multi-day summary.

    Rules:
    - Only P21BackfillDateResult items with daily_gate == READY contribute to
      aggregate metrics.
    - Missing / blocked items are counted but never fabricated.
    - ROI is stake-weighted (not averaged by day).
    - Hit rate is settled-bet-weighted (not averaged by day).
    """
    from wbc_backend.recommendation.p21_multi_day_backfill_contract import (
        P21_MULTI_DAY_PAPER_BACKFILL_READY as READY_GATE,
    )

    ready_results: list[P21BackfillDateResult] = []
    n_missing = 0
    n_blocked = 0

    for item in date_results:
        if isinstance(item, P21MissingArtifactReport):
            n_missing += 1
        elif isinstance(item, P21BackfillDateResult):
            if item.daily_gate == READY_GATE:
                ready_results.append(item)
            else:
                n_blocked += 1

    n_dates_requested = len(date_results)
    n_dates_ready = len(ready_results)
    n_dates_missing = n_missing
    n_dates_blocked = n_blocked

    # Aggregate metrics from ready runs only
    total_active = sum(r.n_active_paper_entries for r in ready_results)
    total_win = sum(r.n_settled_win for r in ready_results)
    total_loss = sum(r.n_settled_loss for r in ready_results)
    total_unsettled = sum(r.n_unsettled for r in ready_results)
    total_stake = sum(r.total_stake_units for r in ready_results)
    total_pnl = sum(r.total_pnl_units for r in ready_results)

    agg_roi = compute_aggregate_roi(total_pnl, total_stake)
    agg_hit_rate = compute_aggregate_hit_rate(total_win, total_loss)

    min_coverage = (
        min(r.game_id_coverage for r in ready_results) if ready_results else 0.0
    )
    join_methods = tuple(
        sorted({r.settlement_join_method for r in ready_results})
    )

    # Gate decision
    if n_dates_ready == 0:
        gate = P21_BLOCKED_NO_READY_DAILY_RUNS
    else:
        # Safety checks on ready runs
        contract_ok = all(
            r.paper_only and not r.production_ready
            for r in ready_results
        )
        if not contract_ok:
            gate = P21_BLOCKED_CONTRACT_VIOLATION
        else:
            gate = P21_MULTI_DAY_PAPER_BACKFILL_READY

    # Determine date_start / date_end from requested range
    all_dates = sorted(
        item.run_date
        for item in date_results
    )
    date_start = all_dates[0] if all_dates else ""
    date_end = all_dates[-1] if all_dates else ""

    return P21BackfillAggregateSummary(
        date_start=date_start,
        date_end=date_end,
        n_dates_requested=n_dates_requested,
        n_dates_ready=n_dates_ready,
        n_dates_missing=n_dates_missing,
        n_dates_blocked=n_dates_blocked,
        total_active_entries=total_active,
        total_settled_win=total_win,
        total_settled_loss=total_loss,
        total_unsettled=total_unsettled,
        total_stake_units=total_stake,
        total_pnl_units=total_pnl,
        aggregate_roi_units=agg_roi,
        aggregate_hit_rate=agg_hit_rate,
        min_game_id_coverage=min_coverage,
        all_join_methods=join_methods,
        paper_only=True,
        production_ready=False,
        p21_gate=gate,
    )


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_backfill_summary(summary: P21BackfillAggregateSummary) -> ValidationResult:
    """
    Validate the aggregate summary against required contract rules.
    """
    if not summary.paper_only:
        return ValidationResult(
            valid=False,
            error_code=P21_BLOCKED_CONTRACT_VIOLATION,
            error_message="paper_only must be True",
        )
    if summary.production_ready:
        return ValidationResult(
            valid=False,
            error_code=P21_BLOCKED_CONTRACT_VIOLATION,
            error_message="production_ready must be False",
        )
    if summary.n_dates_ready == 0:
        return ValidationResult(
            valid=False,
            error_code=P21_BLOCKED_NO_READY_DAILY_RUNS,
            error_message="No ready daily runs found in date range",
        )
    if summary.p21_gate != P21_MULTI_DAY_PAPER_BACKFILL_READY:
        return ValidationResult(
            valid=False,
            error_code=summary.p21_gate,
            error_message=f"Gate is {summary.p21_gate}, not READY",
        )
    return ValidationResult(valid=True)


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------


def write_backfill_outputs(
    summary: P21BackfillAggregateSummary,
    date_results: list[DiscoveryItem],
    missing_reports: list[dict],
    output_dir: str | Path,
) -> list[str]:
    """
    Write all P21 output files to output_dir.

    Files written:
      - backfill_summary.json
      - backfill_summary.md
      - date_results.csv
      - missing_artifacts.json
      - p21_gate_result.json

    Returns list of written file paths.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(timezone.utc).isoformat()
    written: list[str] = []

    # 1. backfill_summary.json
    summary_dict = {
        "p21_gate": summary.p21_gate,
        "date_start": summary.date_start,
        "date_end": summary.date_end,
        "n_dates_requested": summary.n_dates_requested,
        "n_dates_ready": summary.n_dates_ready,
        "n_dates_missing": summary.n_dates_missing,
        "n_dates_blocked": summary.n_dates_blocked,
        "total_active_entries": summary.total_active_entries,
        "total_settled_win": summary.total_settled_win,
        "total_settled_loss": summary.total_settled_loss,
        "total_unsettled": summary.total_unsettled,
        "total_stake_units": summary.total_stake_units,
        "total_pnl_units": summary.total_pnl_units,
        "aggregate_roi_units": summary.aggregate_roi_units,
        "aggregate_hit_rate": summary.aggregate_hit_rate,
        "min_game_id_coverage": summary.min_game_id_coverage,
        "all_join_methods": list(summary.all_join_methods),
        "paper_only": summary.paper_only,
        "production_ready": summary.production_ready,
        "generated_at": generated_at,
    }
    p_json = out / "backfill_summary.json"
    p_json.write_text(json.dumps(summary_dict, indent=2), encoding="utf-8")
    written.append(str(p_json))

    # 2. backfill_summary.md
    roi_pct = summary.aggregate_roi_units * 100
    hit_pct = summary.aggregate_hit_rate * 100
    coverage_pct = summary.min_game_id_coverage * 100
    md_lines = [
        "# P21 Multi-Day PAPER Backfill Summary",
        "",
        f"**Gate**: `{summary.p21_gate}`  ",
        f"**Date Range**: {summary.date_start} → {summary.date_end}  ",
        f"**Generated**: {generated_at}  ",
        "",
        "## Coverage",
        f"- Dates requested: {summary.n_dates_requested}",
        f"- Dates ready: {summary.n_dates_ready}",
        f"- Dates missing: {summary.n_dates_missing}",
        f"- Dates blocked: {summary.n_dates_blocked}",
        "",
        "## Aggregate Metrics",
        f"- Total active entries: {summary.total_active_entries}",
        f"- Total settled wins: {summary.total_settled_win}",
        f"- Total settled losses: {summary.total_settled_loss}",
        f"- Total unsettled: {summary.total_unsettled}",
        f"- Total stake units: {summary.total_stake_units:.2f}",
        f"- Total PnL units: {summary.total_pnl_units:.4f}",
        f"- Aggregate ROI: {roi_pct:+.2f}%",
        f"- Aggregate hit rate: {hit_pct:.2f}%",
        f"- Min game_id coverage: {coverage_pct:.1f}%",
        f"- Join methods: {', '.join(summary.all_join_methods)}",
        "",
        "## Safety",
        f"- paper_only: {summary.paper_only}",
        f"- production_ready: {summary.production_ready}",
    ]
    p_md = out / "backfill_summary.md"
    p_md.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    written.append(str(p_md))

    # 3. date_results.csv
    ready_items = [
        item for item in date_results
        if isinstance(item, P21BackfillDateResult)
    ]
    csv_path = out / "date_results.csv"
    fieldnames = [
        "run_date", "daily_gate", "p20_gate",
        "n_recommended_rows", "n_active_paper_entries",
        "n_settled_win", "n_settled_loss", "n_unsettled",
        "total_stake_units", "total_pnl_units", "roi_units", "hit_rate",
        "game_id_coverage", "settlement_join_method",
        "artifact_manifest_sha256", "paper_only", "production_ready",
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for item in sorted(ready_items, key=lambda r: r.run_date):
            writer.writerow({fn: getattr(item, fn) for fn in fieldnames})
    written.append(str(csv_path))

    # 4. missing_artifacts.json
    p_missing = out / "missing_artifacts.json"
    p_missing.write_text(json.dumps(missing_reports, indent=2), encoding="utf-8")
    written.append(str(p_missing))

    # 5. p21_gate_result.json
    gate_dict = {
        "p21_gate": summary.p21_gate,
        "date_start": summary.date_start,
        "date_end": summary.date_end,
        "n_dates_requested": summary.n_dates_requested,
        "n_dates_ready": summary.n_dates_ready,
        "n_dates_missing": summary.n_dates_missing,
        "n_dates_blocked": summary.n_dates_blocked,
        "total_active_entries": summary.total_active_entries,
        "total_settled_win": summary.total_settled_win,
        "total_settled_loss": summary.total_settled_loss,
        "total_unsettled": summary.total_unsettled,
        "total_stake_units": summary.total_stake_units,
        "total_pnl_units": summary.total_pnl_units,
        "aggregate_roi_units": summary.aggregate_roi_units,
        "aggregate_hit_rate": summary.aggregate_hit_rate,
        "min_game_id_coverage": summary.min_game_id_coverage,
        "paper_only": summary.paper_only,
        "production_ready": summary.production_ready,
        "script_version": "P21_MULTI_DAY_PAPER_BACKFILL_V1",
        "generated_at": generated_at,
    }
    p_gate = out / "p21_gate_result.json"
    p_gate.write_text(json.dumps(gate_dict, indent=2), encoding="utf-8")
    written.append(str(p_gate))

    return written
