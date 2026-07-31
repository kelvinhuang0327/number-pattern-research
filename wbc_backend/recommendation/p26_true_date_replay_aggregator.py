"""
wbc_backend/recommendation/p26_true_date_replay_aggregator.py

P26 True-Date Replay Aggregator.

Runs per-date replays across a date range and aggregates results into
a P26TrueDateReplaySummary and gate decision.

Aggregation rules:
  - ROI is weighted by total stake across all ready dates.
  - Hit rate is weighted by total settled bets (wins / (wins + losses)).
  - Blocked dates are recorded and reported.
  - Gate = P26_TRUE_DATE_HISTORICAL_BACKFILL_READY if >= 1 date is READY.
  - Gate = P26_BLOCKED_NO_READY_DATES if no date is READY.

Output files (written to output_dir):
  p26_gate_result.json
  true_date_replay_summary.json
  true_date_replay_summary.md
  date_replay_results.csv
  blocked_dates.json
  artifact_manifest.json

PAPER_ONLY — no production systems, no real bets.
"""
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone, date as dt_date
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from wbc_backend.recommendation.p26_true_date_replay_contract import (
    P26_DATE_REPLAY_READY,
    P26_TRUE_DATE_HISTORICAL_BACKFILL_READY,
    P26_BLOCKED_NO_READY_DATES,
    P26_BLOCKED_ALL_DATES_FAILED,
    P26_FAIL_INPUT_MISSING,
    P26TrueDateReplayGateResult,
    P26TrueDateReplayManifest,
    P26TrueDateReplaySummary,
    P26TrueDateReplayResult,
)
from wbc_backend.recommendation.p26_per_date_true_replay_runner import (
    run_true_date_replay_for_date,
    summarize_true_date_replay_result,
)


def run_true_date_historical_backfill(
    date_start: str,
    date_end: str,
    p25_dir: Path,
    output_dir: Path,
) -> P26TrueDateReplaySummary:
    """Run true-date replay for all dates in [date_start, date_end].

    p25_dir must contain the P25 true_date_slices subdirectory.
    Writes all output files to output_dir.
    Returns an aggregate summary.
    """
    p25_dir = Path(p25_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not p25_dir.exists():
        raise FileNotFoundError(
            f"P25 source directory does not exist: {p25_dir}"
        )

    dates = _date_range(date_start, date_end)
    date_results: List[P26TrueDateReplayResult] = []

    for run_date in dates:
        result = run_true_date_replay_for_date(
            run_date=run_date,
            p25_slice_dir=p25_dir,
            output_base_dir=output_dir,
        )
        date_results.append(result)

    summary = aggregate_true_date_results(
        date_start=date_start,
        date_end=date_end,
        source_p25_dir=str(p25_dir),
        date_results=date_results,
    )

    write_true_date_replay_outputs(
        summary=summary,
        date_results=date_results,
        output_dir=output_dir,
        p25_dir=p25_dir,
    )

    return summary


def aggregate_true_date_results(
    date_start: str,
    date_end: str,
    source_p25_dir: str,
    date_results: List[P26TrueDateReplayResult],
) -> P26TrueDateReplaySummary:
    """Aggregate per-date replay results into a summary."""
    n_dates_requested = len(date_results)
    n_dates_ready = sum(1 for r in date_results if r.replay_gate == P26_DATE_REPLAY_READY)
    n_dates_blocked = sum(1 for r in date_results if r.replay_gate != P26_DATE_REPLAY_READY)
    n_dates_failed = 0  # currently blocked, not distinguished from failed

    blocked_date_list: Tuple[str, ...] = tuple(
        r.run_date for r in date_results if r.replay_gate != P26_DATE_REPLAY_READY
    )

    total_active = sum(r.n_active_paper_entries for r in date_results)
    total_win = sum(r.n_settled_win for r in date_results)
    total_loss = sum(r.n_settled_loss for r in date_results)
    total_unsettled = sum(r.n_unsettled for r in date_results)
    total_stake = sum(r.total_stake_units for r in date_results)
    total_pnl = sum(r.total_pnl_units for r in date_results)

    # Weighted ROI
    agg_roi = total_pnl / total_stake if total_stake > 0 else 0.0

    # Weighted hit rate (wins / (wins + losses))
    total_settled = total_win + total_loss
    agg_hit_rate = total_win / total_settled if total_settled > 0 else 0.0

    return P26TrueDateReplaySummary(
        date_start=date_start,
        date_end=date_end,
        n_dates_requested=n_dates_requested,
        n_dates_ready=n_dates_ready,
        n_dates_blocked=n_dates_blocked,
        n_dates_failed=n_dates_failed,
        total_active_entries=total_active,
        total_settled_win=total_win,
        total_settled_loss=total_loss,
        total_unsettled=total_unsettled,
        total_stake_units=total_stake,
        total_pnl_units=total_pnl,
        aggregate_roi_units=agg_roi,
        aggregate_hit_rate=agg_hit_rate,
        blocked_date_list=blocked_date_list,
        source_p25_dir=source_p25_dir,
        paper_only=True,
        production_ready=False,
    )


def validate_true_date_aggregate_summary(
    summary: P26TrueDateReplaySummary,
) -> bool:
    """Sanity checks on aggregate summary. Returns True if valid."""
    if summary.paper_only is not True:
        return False
    if summary.production_ready is not False:
        return False
    if summary.n_dates_requested < 0:
        return False
    if summary.n_dates_ready + summary.n_dates_blocked > summary.n_dates_requested:
        return False
    if summary.total_settled_win < 0 or summary.total_settled_loss < 0:
        return False
    return True


def build_gate_result(
    summary: P26TrueDateReplaySummary,
) -> P26TrueDateReplayGateResult:
    """Determine the overall P26 gate from the aggregate summary."""
    if summary.n_dates_ready > 0:
        gate = P26_TRUE_DATE_HISTORICAL_BACKFILL_READY
        blocker = ""
    elif summary.n_dates_requested == 0:
        gate = P26_FAIL_INPUT_MISSING
        blocker = "No dates in requested range."
    else:
        gate = P26_BLOCKED_NO_READY_DATES
        blocker = (
            f"All {summary.n_dates_requested} dates blocked. "
            f"Blocked dates: {list(summary.blocked_date_list[:5])}"
        )

    return P26TrueDateReplayGateResult(
        p26_gate=gate,
        date_start=summary.date_start,
        date_end=summary.date_end,
        n_dates_requested=summary.n_dates_requested,
        n_dates_ready=summary.n_dates_ready,
        n_dates_blocked=summary.n_dates_blocked,
        total_active_entries=summary.total_active_entries,
        total_settled_win=summary.total_settled_win,
        total_settled_loss=summary.total_settled_loss,
        total_unsettled=summary.total_unsettled,
        total_stake_units=summary.total_stake_units,
        total_pnl_units=summary.total_pnl_units,
        aggregate_roi_units=summary.aggregate_roi_units,
        aggregate_hit_rate=summary.aggregate_hit_rate,
        blocker_reason=blocker,
        paper_only=True,
        production_ready=False,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


def write_true_date_replay_outputs(
    summary: P26TrueDateReplaySummary,
    date_results: List[P26TrueDateReplayResult],
    output_dir: Path,
    p25_dir: Path,
) -> None:
    """Write all 6 P26 output files to output_dir."""
    output_dir = Path(output_dir)
    gate_result = build_gate_result(summary)
    generated_at = datetime.now(timezone.utc).isoformat()

    # 1. p26_gate_result.json
    _write_json(
        output_dir / "p26_gate_result.json",
        {
            "p26_gate": gate_result.p26_gate,
            "date_start": gate_result.date_start,
            "date_end": gate_result.date_end,
            "n_dates_requested": gate_result.n_dates_requested,
            "n_dates_ready": gate_result.n_dates_ready,
            "n_dates_blocked": gate_result.n_dates_blocked,
            "total_active_entries": gate_result.total_active_entries,
            "total_settled_win": gate_result.total_settled_win,
            "total_settled_loss": gate_result.total_settled_loss,
            "total_unsettled": gate_result.total_unsettled,
            "total_stake_units": gate_result.total_stake_units,
            "total_pnl_units": gate_result.total_pnl_units,
            "aggregate_roi_units": gate_result.aggregate_roi_units,
            "aggregate_hit_rate": gate_result.aggregate_hit_rate,
            "blocker_reason": gate_result.blocker_reason,
            "paper_only": gate_result.paper_only,
            "production_ready": gate_result.production_ready,
            "generated_at": generated_at,
        },
    )

    # 2. true_date_replay_summary.json
    _write_json(
        output_dir / "true_date_replay_summary.json",
        {
            "date_start": summary.date_start,
            "date_end": summary.date_end,
            "n_dates_requested": summary.n_dates_requested,
            "n_dates_ready": summary.n_dates_ready,
            "n_dates_blocked": summary.n_dates_blocked,
            "n_dates_failed": summary.n_dates_failed,
            "total_active_entries": summary.total_active_entries,
            "total_settled_win": summary.total_settled_win,
            "total_settled_loss": summary.total_settled_loss,
            "total_unsettled": summary.total_unsettled,
            "total_stake_units": summary.total_stake_units,
            "total_pnl_units": summary.total_pnl_units,
            "aggregate_roi_units": summary.aggregate_roi_units,
            "aggregate_hit_rate": summary.aggregate_hit_rate,
            "blocked_date_list": list(summary.blocked_date_list),
            "source_p25_dir": summary.source_p25_dir,
            "paper_only": summary.paper_only,
            "production_ready": summary.production_ready,
            "generated_at": generated_at,
        },
    )

    # 3. true_date_replay_summary.md
    _write_markdown_summary(output_dir / "true_date_replay_summary.md", summary, gate_result)

    # 4. date_replay_results.csv
    _write_date_results_csv(output_dir / "date_replay_results.csv", date_results)

    # 5. blocked_dates.json
    _write_json(
        output_dir / "blocked_dates.json",
        {
            "blocked_dates": [
                {"run_date": r.run_date, "gate": r.replay_gate, "reason": r.blocker_reason}
                for r in date_results
                if r.replay_gate != P26_DATE_REPLAY_READY
            ],
            "n_blocked": summary.n_dates_blocked,
            "generated_at": generated_at,
        },
    )

    # 6. artifact_manifest.json
    written_dates = tuple(
        r.run_date for r in date_results if r.replay_gate == P26_DATE_REPLAY_READY
    )
    skipped_dates = tuple(
        r.run_date for r in date_results if r.replay_gate != P26_DATE_REPLAY_READY
    )
    total_rows = sum(
        r.n_slice_rows for r in date_results if r.replay_gate == P26_DATE_REPLAY_READY
    )
    total_active = sum(
        r.n_active_paper_entries for r in date_results if r.replay_gate == P26_DATE_REPLAY_READY
    )
    manifest = P26TrueDateReplayManifest(
        output_dir=str(output_dir),
        date_start=summary.date_start,
        date_end=summary.date_end,
        written_dates=written_dates,
        skipped_dates=skipped_dates,
        total_rows_written=total_rows,
        total_active_entries_written=total_active,
        paper_only=True,
        production_ready=False,
        generated_at=generated_at,
    )
    _write_json(
        output_dir / "artifact_manifest.json",
        {
            "output_dir": manifest.output_dir,
            "date_start": manifest.date_start,
            "date_end": manifest.date_end,
            "written_dates": list(manifest.written_dates),
            "skipped_dates": list(manifest.skipped_dates),
            "total_rows_written": manifest.total_rows_written,
            "total_active_entries_written": manifest.total_active_entries_written,
            "paper_only": manifest.paper_only,
            "production_ready": manifest.production_ready,
            "generated_at": generated_at,
        },
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _date_range(date_start: str, date_end: str) -> List[str]:
    """Return list of ISO date strings from date_start to date_end inclusive."""
    from datetime import date as dt_date, timedelta
    start = dt_date.fromisoformat(date_start)
    end = dt_date.fromisoformat(date_end)
    result = []
    current = start
    while current <= end:
        result.append(current.isoformat())
        current += timedelta(days=1)
    return result


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, default=str))


def _write_date_results_csv(
    path: Path,
    date_results: List[P26TrueDateReplayResult],
) -> None:
    fieldnames = [
        "run_date", "true_game_date", "replay_gate",
        "n_slice_rows", "n_unique_game_ids", "date_matches_slice",
        "n_active_paper_entries", "n_settled_win", "n_settled_loss", "n_unsettled",
        "total_stake_units", "total_pnl_units", "roi_units", "hit_rate",
        "game_id_coverage", "paper_only", "production_ready", "blocker_reason",
    ]
    rows = [summarize_true_date_replay_result(r) for r in date_results]
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_markdown_summary(
    path: Path,
    summary: P26TrueDateReplaySummary,
    gate_result: P26TrueDateReplayGateResult,
) -> None:
    roi_pct = summary.aggregate_roi_units * 100
    hit_pct = summary.aggregate_hit_rate * 100
    lines = [
        "# P26 True-Date Historical Backfill Replay Summary",
        "",
        f"**Date range**: {summary.date_start} → {summary.date_end}",
        f"**Gate**: `{gate_result.p26_gate}`",
        f"**Paper only**: {summary.paper_only} | **Production ready**: {summary.production_ready}",
        "",
        "## Date Coverage",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Dates requested | {summary.n_dates_requested} |",
        f"| Dates ready | {summary.n_dates_ready} |",
        f"| Dates blocked | {summary.n_dates_blocked} |",
        "",
        "## Aggregate Performance",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Total active entries | {summary.total_active_entries} |",
        f"| Total settled win | {summary.total_settled_win} |",
        f"| Total settled loss | {summary.total_settled_loss} |",
        f"| Total unsettled | {summary.total_unsettled} |",
        f"| Total stake (units) | {summary.total_stake_units:.4f} |",
        f"| Total PnL (units) | {summary.total_pnl_units:.4f} |",
        f"| Aggregate ROI | {roi_pct:.2f}% |",
        f"| Aggregate hit rate | {hit_pct:.1f}% |",
        "",
    ]
    if summary.blocked_date_list:
        lines.append("## Blocked Dates")
        for d in summary.blocked_date_list:
            lines.append(f"- {d}")
        lines.append("")
    path.write_text("\n".join(lines))
