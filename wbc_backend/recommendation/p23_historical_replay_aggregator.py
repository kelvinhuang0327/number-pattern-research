"""
wbc_backend/recommendation/p23_historical_replay_aggregator.py

P23 Historical Replay Aggregator — collects per-date replay results and
computes aggregate metrics: weighted ROI, weighted hit-rate, date counts.

PAPER_ONLY — no production systems, no real bets.
"""
from __future__ import annotations

import csv
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from wbc_backend.recommendation.p23_historical_replay_contract import (
    P23_BLOCKED_ALL_DATES_FAILED,
    P23_BLOCKED_CONTRACT_VIOLATION,
    P23_BLOCKED_NO_READY_DATES,
    P23_DATE_ALREADY_READY,
    P23_DATE_REPLAY_READY,
    P23_HISTORICAL_REPLAY_BACKFILL_READY,
    P23ReplayAggregateSummary,
    P23ReplayDateResult,
    P23ReplayGateResult,
)

_READY_GATES = {P23_DATE_REPLAY_READY, P23_DATE_ALREADY_READY}


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def aggregate_replay_results(
    date_results: list[P23ReplayDateResult],
    date_start: str,
    date_end: str,
    n_dates_requested: int,
) -> P23ReplayAggregateSummary:
    """Compute aggregate metrics from all per-date replay results.

    ROI is weighted by total_stake_units (not averaged).
    Hit-rate is weighted by settled bets (not averaged).

    Args:
        date_results:      List of P23ReplayDateResult (one per attempted date)
        date_start:        First date in the requested range (YYYY-MM-DD)
        date_end:          Last date in the requested range (YYYY-MM-DD)
        n_dates_requested: Total dates in the requested range

    Returns:
        P23ReplayAggregateSummary with gate decision
    """
    ready = [r for r in date_results if r.date_gate in _READY_GATES]
    blocked = [r for r in date_results if r.date_gate not in _READY_GATES]

    total_active = sum(r.n_active_paper_entries for r in ready)
    total_win = sum(r.n_settled_win for r in ready)
    total_loss = sum(r.n_settled_loss for r in ready)
    total_unsettled = sum(r.n_unsettled for r in ready)
    total_stake = sum(r.total_stake_units for r in ready)
    total_pnl = sum(r.total_pnl_units for r in ready)

    # Weighted ROI = total_pnl / total_stake
    if total_stake > 0:
        aggregate_roi = total_pnl / total_stake
    elif ready:
        # Stake = 0 but dates are ready → 0 ROI
        aggregate_roi = 0.0
    else:
        aggregate_roi = 0.0

    # Weighted hit-rate = total_win / (total_win + total_loss)
    settled = total_win + total_loss
    if settled > 0:
        aggregate_hit_rate = total_win / settled
    else:
        aggregate_hit_rate = 0.0

    # Min game_id_coverage across ready dates
    if ready:
        min_coverage = min(r.game_id_coverage for r in ready)
    else:
        min_coverage = 0.0

    # Gate decision
    if not ready and not blocked:
        gate = P23_BLOCKED_NO_READY_DATES
    elif not ready:
        gate = P23_BLOCKED_ALL_DATES_FAILED
    else:
        gate = P23_HISTORICAL_REPLAY_BACKFILL_READY

    return P23ReplayAggregateSummary(
        date_start=date_start,
        date_end=date_end,
        n_dates_requested=n_dates_requested,
        n_dates_attempted=len(date_results),
        n_dates_ready=len(ready),
        n_dates_blocked=len(blocked),
        total_active_entries=total_active,
        total_settled_win=total_win,
        total_settled_loss=total_loss,
        total_unsettled=total_unsettled,
        total_stake_units=total_stake,
        total_pnl_units=total_pnl,
        aggregate_roi_units=aggregate_roi,
        aggregate_hit_rate=aggregate_hit_rate,
        min_game_id_coverage=min_coverage,
        p23_gate=gate,
        paper_only=True,
        production_ready=False,
    )


def validate_aggregate_summary(summary: P23ReplayAggregateSummary) -> list[str]:
    """Check aggregate summary for contract compliance.

    Returns:
        List of violation messages. Empty = valid.
    """
    violations: list[str] = []

    if not summary.paper_only:
        violations.append("paper_only must be True")
    if summary.production_ready:
        violations.append("production_ready must be False")
    if summary.n_dates_ready < 0:
        violations.append("n_dates_ready cannot be negative")
    if summary.n_dates_blocked < 0:
        violations.append("n_dates_blocked cannot be negative")
    if summary.total_stake_units < 0:
        violations.append("total_stake_units cannot be negative")

    return violations


def build_gate_result(
    summary: P23ReplayAggregateSummary,
) -> P23ReplayGateResult:
    """Build the top-level gate result from the aggregate summary.

    Adds recommended_next_action based on the gate state.
    """
    gate = summary.p23_gate

    if gate == P23_HISTORICAL_REPLAY_BACKFILL_READY:
        if summary.n_dates_ready == summary.n_dates_requested:
            next_action = "Proceed to P24 Backfill Performance Stability Audit"
        elif summary.n_dates_ready >= 2:
            next_action = "Partial success: review blocked dates; consider P23.5 P15 Full Replay Input Builder"
        else:
            next_action = "Only 2026-05-12 succeeded: investigate source materializer before P24"
    elif gate == P23_BLOCKED_ALL_DATES_FAILED:
        next_action = "Investigate per-date blockers: check source materializer and P18 policy path"
    elif gate == P23_BLOCKED_NO_READY_DATES:
        next_action = "No dates attempted: verify P22.5 source artifact builder completed"
    else:
        next_action = "Review gate violations and fix blocked inputs"

    return P23ReplayGateResult(
        p23_gate=gate,
        date_start=summary.date_start,
        date_end=summary.date_end,
        n_dates_requested=summary.n_dates_requested,
        n_dates_attempted=summary.n_dates_attempted,
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
        min_game_id_coverage=summary.min_game_id_coverage,
        recommended_next_action=next_action,
        paper_only=True,
        production_ready=False,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------


def write_replay_outputs(
    summary: P23ReplayAggregateSummary,
    gate_result: P23ReplayGateResult,
    date_results: list[P23ReplayDateResult],
    output_dir: str | Path,
) -> list[str]:
    """Write all 6 required P23 output files to output_dir.

    Files:
      1. historical_replay_summary.json
      2. historical_replay_summary.md
      3. date_replay_results.csv
      4. blocked_dates.json
      5. artifact_manifest.json
      6. p23_gate_result.json

    Returns:
        List of written file paths (strings)
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    written: list[str] = []

    # 1. historical_replay_summary.json
    summary_json = out / "historical_replay_summary.json"
    with open(summary_json, "w", encoding="utf-8") as fh:
        json.dump(asdict(summary), fh, indent=2)
    written.append(str(summary_json))

    # 2. historical_replay_summary.md
    roi_pct = summary.aggregate_roi_units * 100
    hit_pct = summary.aggregate_hit_rate * 100
    cov_pct = summary.min_game_id_coverage * 100
    md_lines = [
        "# P23 Historical Replay Backfill Summary\n",
        f"\nGenerated: {gate_result.generated_at}\n",
        f"\n**Gate**: `{summary.p23_gate}`\n",
        f"\n| Metric | Value |\n|---|---|\n",
        f"| date_start | {summary.date_start} |\n",
        f"| date_end | {summary.date_end} |\n",
        f"| n_dates_requested | {summary.n_dates_requested} |\n",
        f"| n_dates_ready | {summary.n_dates_ready} |\n",
        f"| n_dates_blocked | {summary.n_dates_blocked} |\n",
        f"| total_active_entries | {summary.total_active_entries} |\n",
        f"| total_settled_win | {summary.total_settled_win} |\n",
        f"| total_settled_loss | {summary.total_settled_loss} |\n",
        f"| total_stake_units | {summary.total_stake_units:.2f} |\n",
        f"| total_pnl_units | {summary.total_pnl_units:.4f} |\n",
        f"| aggregate_roi | {roi_pct:+.2f}% |\n",
        f"| aggregate_hit_rate | {hit_pct:.2f}% |\n",
        f"| min_game_id_coverage | {cov_pct:.1f}% |\n",
        f"| paper_only | {summary.paper_only} |\n",
        f"| production_ready | {summary.production_ready} |\n",
        f"\n**Next Action**: {gate_result.recommended_next_action}\n",
    ]
    summary_md = out / "historical_replay_summary.md"
    with open(summary_md, "w", encoding="utf-8") as fh:
        fh.writelines(md_lines)
    written.append(str(summary_md))

    # 3. date_replay_results.csv
    results_csv = out / "date_replay_results.csv"
    if date_results:
        fieldnames = list(asdict(date_results[0]).keys())
        with open(results_csv, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            for dr in date_results:
                writer.writerow(asdict(dr))
    else:
        results_csv.write_text("run_date,date_gate,blocker_reason\n")
    written.append(str(results_csv))

    # 4. blocked_dates.json
    blocked = [asdict(r) for r in date_results if r.date_gate not in {P23_DATE_REPLAY_READY, P23_DATE_ALREADY_READY}]
    blocked_json = out / "blocked_dates.json"
    with open(blocked_json, "w", encoding="utf-8") as fh:
        json.dump({"n_blocked": len(blocked), "blocked_dates": blocked}, fh, indent=2)
    written.append(str(blocked_json))

    # 5. artifact_manifest.json
    manifest = {
        "date_start": summary.date_start,
        "date_end": summary.date_end,
        "n_dates_in_manifest": len(date_results),
        "output_files": [str(out / f) for f in [
            "historical_replay_summary.json",
            "historical_replay_summary.md",
            "date_replay_results.csv",
            "blocked_dates.json",
            "artifact_manifest.json",
            "p23_gate_result.json",
        ]],
        "paper_only": True,
        "production_ready": False,
        "generated_at": gate_result.generated_at,
    }
    manifest_json = out / "artifact_manifest.json"
    with open(manifest_json, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
    written.append(str(manifest_json))

    # 6. p23_gate_result.json
    gate_json = out / "p23_gate_result.json"
    with open(gate_json, "w", encoding="utf-8") as fh:
        json.dump(asdict(gate_result), fh, indent=2)
    written.append(str(gate_json))

    return written
