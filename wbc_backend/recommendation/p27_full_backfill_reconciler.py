"""
wbc_backend/recommendation/p27_full_backfill_reconciler.py

P27 — full-range aggregate reconciler.

Reads per-segment gate results and reconciles them into a single
P27FullBackfillSummary + P27FullBackfillGateResult, then writes 7 output files.
"""
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from wbc_backend.recommendation.p27_full_true_date_backfill_contract import (
    MIN_SAMPLE_SIZE_ADVISORY,
    P27_BLOCKED_P26_REPLAY_FAILED,
    P27_BLOCKED_RUNTIME_GUARD,
    P27_FAIL_INPUT_MISSING,
    P27_FULL_TRUE_DATE_BACKFILL_READY,
    P27FullBackfillGateResult,
    P27FullBackfillSummary,
    P27RuntimeGuardResult,
)


# ---------------------------------------------------------------------------
# Reconcile
# ---------------------------------------------------------------------------


def reconcile_segment_outputs(
    segment_results: List[Dict],
    date_results: Optional[List[Dict]] = None,
) -> P27FullBackfillSummary:
    """
    Build a P27FullBackfillSummary from a list of per-segment result dicts
    (as returned by p27_p26_segmented_replay_runner).

    date_results: optional per-date rows (from date_replay_results.csv per segment).
    """
    if not segment_results:
        return P27FullBackfillSummary(
            date_start="",
            date_end="",
            n_segments=0,
            n_dates_requested=0,
            n_dates_ready=0,
            n_dates_empty=0,
            n_dates_blocked=0,
            total_active_entries=0,
            total_settled_win=0,
            total_settled_loss=0,
            total_unsettled=0,
            total_stake_units=0.0,
            total_pnl_units=0.0,
            aggregate_roi_units=0.0,
            aggregate_hit_rate=0.0,
            min_game_id_coverage=0.0,
            max_runtime_seconds=0.0,
            blocked_segment_list=(),
            blocked_date_list=(),
            source_p25_base_dir="",
            paper_only=True,
            production_ready=False,
            blocker_reason="No segment results provided",
        )

    date_start = segment_results[0]["date_start"]
    date_end = segment_results[-1]["date_end"]
    n_segments = len(segment_results)

    return compute_full_range_weighted_metrics(
        date_start=date_start,
        date_end=date_end,
        n_segments=n_segments,
        segment_results=segment_results,
        date_results=date_results or [],
        source_p25_base_dir="",
    )


def compute_full_range_weighted_metrics(
    date_start: str,
    date_end: str,
    n_segments: int,
    segment_results: List[Dict],
    date_results: List[Dict],
    source_p25_base_dir: str = "",
) -> P27FullBackfillSummary:
    """
    Weighted-correctly aggregate all segment data.

    ROI = total_pnl / total_stake  (not averaged)
    Hit rate = total_wins / (total_wins + total_losses)  (not averaged)
    """
    total_active = 0
    total_win = 0
    total_loss = 0
    total_unsettled = 0
    total_stake = 0.0
    total_pnl = 0.0
    blocked_segment_labels: List[str] = []
    blocked_date_labels: List[str] = []
    n_dates_requested = 0
    n_dates_ready = 0
    n_dates_blocked = 0
    n_dates_empty = 0
    min_coverage = 1.0
    max_runtime = 0.0

    for r in segment_results:
        gd = r.get("gate_data", {})
        is_blocked = r.get("blocked", True)

        n_req = gd.get("n_dates_requested", 0)
        n_rdy = gd.get("n_dates_ready", 0)
        n_blk = gd.get("n_dates_blocked", 0)

        n_dates_requested += n_req
        n_dates_ready += n_rdy
        n_dates_blocked += n_blk
        # If the gate_data doesn't have n_dates_requested, use segment date_count
        if n_req == 0 and not is_blocked:
            pass  # no data to add

        if is_blocked:
            blocked_segment_labels.append(f"{r['date_start']}_{r['date_end']}")
        else:
            a = gd.get("total_active_entries", 0)
            w = gd.get("total_settled_win", 0)
            l = gd.get("total_settled_loss", 0)
            u = gd.get("total_unsettled", 0)
            s = gd.get("total_stake_units", 0.0)
            p = gd.get("total_pnl_units", 0.0)
            total_active += a
            total_win += w
            total_loss += l
            total_unsettled += u
            total_stake += s
            total_pnl += p

    # Compute n_dates_empty from date_results if available
    if date_results:
        for dr in date_results:
            if dr.get("n_active_paper_entries", 0) == 0 and dr.get("replay_gate") == "P26_DATE_REPLAY_READY":
                n_dates_empty += 1
            if dr.get("replay_gate", "") not in ("P26_DATE_REPLAY_READY", ""):
                blocked_date_labels.append(dr.get("run_date", ""))

    roi = total_pnl / total_stake if total_stake > 0 else 0.0
    settled = total_win + total_loss
    hit_rate = total_win / settled if settled > 0 else 0.0

    blocker_reason = ""
    if not segment_results or all(r.get("blocked", True) for r in segment_results):
        blocker_reason = "All segments blocked"

    return P27FullBackfillSummary(
        date_start=date_start,
        date_end=date_end,
        n_segments=n_segments,
        n_dates_requested=n_dates_requested,
        n_dates_ready=n_dates_ready,
        n_dates_empty=n_dates_empty,
        n_dates_blocked=n_dates_blocked,
        total_active_entries=total_active,
        total_settled_win=total_win,
        total_settled_loss=total_loss,
        total_unsettled=total_unsettled,
        total_stake_units=total_stake,
        total_pnl_units=total_pnl,
        aggregate_roi_units=roi,
        aggregate_hit_rate=hit_rate,
        min_game_id_coverage=min_coverage,
        max_runtime_seconds=max_runtime,
        blocked_segment_list=tuple(blocked_segment_labels),
        blocked_date_list=tuple(sorted(set(blocked_date_labels))),
        source_p25_base_dir=source_p25_base_dir,
        paper_only=True,
        production_ready=False,
        blocker_reason=blocker_reason,
    )


def detect_duplicate_segment_outputs(segment_results: List[Dict]) -> List[str]:
    """
    Detect if any two segments share the same output_dir.
    Returns a list of duplicate output_dir strings (empty if none).
    """
    seen: Dict[str, int] = {}
    duplicates: List[str] = []
    for r in segment_results:
        od = r.get("output_dir", "")
        if not od:
            continue
        if od in seen:
            duplicates.append(od)
        seen[od] = seen.get(od, 0) + 1
    return duplicates


def validate_full_backfill_summary(summary: P27FullBackfillSummary) -> bool:
    """
    Sanity-check the full summary.
    Returns True if valid, raises ValueError otherwise.
    """
    if summary.total_settled_win < 0:
        raise ValueError("total_settled_win must be >= 0")
    if summary.total_settled_loss < 0:
        raise ValueError("total_settled_loss must be >= 0")
    if summary.total_stake_units < 0:
        raise ValueError("total_stake_units must be >= 0")
    if not summary.paper_only:
        raise ValueError("paper_only must be True")
    if summary.production_ready:
        raise ValueError("production_ready must be False")
    return True


def build_p27_gate_result(
    summary: P27FullBackfillSummary,
    runtime_seconds: float = 0.0,
    max_runtime_seconds: float = 180.0,
    guard_triggered: bool = False,
) -> P27FullBackfillGateResult:
    """Determine the P27 gate from the summary."""
    if summary.n_dates_requested == 0:
        p27_gate = P27_FAIL_INPUT_MISSING
        blocker = "No dates requested"
    elif guard_triggered:
        p27_gate = P27_BLOCKED_RUNTIME_GUARD
        blocker = f"Runtime {runtime_seconds:.1f}s exceeded max {max_runtime_seconds:.1f}s"
    elif summary.n_dates_ready == 0:
        p27_gate = P27_BLOCKED_P26_REPLAY_FAILED
        blocker = "No dates ready — all segments blocked"
    else:
        p27_gate = P27_FULL_TRUE_DATE_BACKFILL_READY
        blocker = summary.blocker_reason

    return P27FullBackfillGateResult(
        p27_gate=p27_gate,
        date_start=summary.date_start,
        date_end=summary.date_end,
        n_segments=summary.n_segments,
        n_dates_requested=summary.n_dates_requested,
        n_dates_ready=summary.n_dates_ready,
        n_dates_empty=summary.n_dates_empty,
        n_dates_blocked=summary.n_dates_blocked,
        total_active_entries=summary.total_active_entries,
        total_settled_win=summary.total_settled_win,
        total_settled_loss=summary.total_settled_loss,
        total_unsettled=summary.total_unsettled,
        total_stake_units=summary.total_stake_units,
        total_pnl_units=summary.total_pnl_units,
        aggregate_roi_units=summary.aggregate_roi_units,
        aggregate_hit_rate=summary.aggregate_hit_rate,
        max_runtime_seconds=max(runtime_seconds, summary.max_runtime_seconds),
        paper_only=True,
        production_ready=False,
        blocker_reason=blocker,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


def write_p27_outputs(
    summary: P27FullBackfillSummary,
    gate_result: P27FullBackfillGateResult,
    segment_results: List[Dict],
    date_results: List[Dict],
    runtime_guard: P27RuntimeGuardResult,
    output_dir: Path,
) -> None:
    """
    Write 7 output files to output_dir:
    1. p27_gate_result.json
    2. p27_full_backfill_summary.json
    3. p27_full_backfill_summary.md
    4. segment_results.csv
    5. date_results.csv
    6. blocked_segments.json
    7. runtime_guard.json
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. gate result
    _write_json(output_dir / "p27_gate_result.json", _dataclass_to_dict(gate_result))

    # 2. summary json
    _write_json(output_dir / "p27_full_backfill_summary.json", _dataclass_to_dict(summary))

    # 3. summary markdown
    _write_markdown(output_dir / "p27_full_backfill_summary.md", summary, gate_result)

    # 4. segment_results.csv
    _write_segment_csv(output_dir / "segment_results.csv", segment_results)

    # 5. date_results.csv
    _write_date_csv(output_dir / "date_results.csv", date_results)

    # 6. blocked_segments.json
    _write_json(
        output_dir / "blocked_segments.json",
        {
            "n_blocked": len(summary.blocked_segment_list),
            "blocked_segments": list(summary.blocked_segment_list),
            "n_blocked_dates": len(summary.blocked_date_list),
            "blocked_dates": list(summary.blocked_date_list),
            "paper_only": True,
            "production_ready": False,
        },
    )

    # 7. runtime_guard.json
    _write_json(output_dir / "runtime_guard.json", _dataclass_to_dict(runtime_guard))


# ---------------------------------------------------------------------------
# Internal writers
# ---------------------------------------------------------------------------


def _dataclass_to_dict(obj) -> Dict:
    """Convert a frozen dataclass to a JSON-serializable dict."""
    import dataclasses
    if dataclasses.is_dataclass(obj):
        result = {}
        for f in dataclasses.fields(obj):
            v = getattr(obj, f.name)
            if isinstance(v, tuple):
                v = list(v)
            result[f.name] = v
        return result
    return dict(obj)


def _write_json(path: Path, data: Dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def _write_segment_csv(path: Path, segment_results: List[Dict]) -> None:
    fieldnames = [
        "segment_index", "date_start", "date_end", "p26_gate", "blocked",
        "returncode", "total_active_entries", "total_settled_win",
        "total_settled_loss", "total_unsettled",
        "total_stake_units", "total_pnl_units",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in segment_results:
            gd = r.get("gate_data", {})
            row = {
                "segment_index": r.get("segment_index", ""),
                "date_start": r.get("date_start", ""),
                "date_end": r.get("date_end", ""),
                "p26_gate": r.get("p26_gate", ""),
                "blocked": r.get("blocked", True),
                "returncode": r.get("returncode", ""),
                "total_active_entries": gd.get("total_active_entries", 0),
                "total_settled_win": gd.get("total_settled_win", 0),
                "total_settled_loss": gd.get("total_settled_loss", 0),
                "total_unsettled": gd.get("total_unsettled", 0),
                "total_stake_units": gd.get("total_stake_units", 0.0),
                "total_pnl_units": gd.get("total_pnl_units", 0.0),
            }
            writer.writerow(row)


def _write_date_csv(path: Path, date_results: List[Dict]) -> None:
    if not date_results:
        path.write_text("run_date,segment_index,replay_gate,n_active_paper_entries,"
                        "n_settled_win,n_settled_loss,n_unsettled,"
                        "total_stake_units,total_pnl_units\n")
        return
    fieldnames = sorted(date_results[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(date_results)


def _write_markdown(
    path: Path,
    summary: P27FullBackfillSummary,
    gate: P27FullBackfillGateResult,
) -> None:
    roi_pct = f"{summary.aggregate_roi_units * 100:.2f}%"
    hit_pct = f"{summary.aggregate_hit_rate * 100:.1f}%"
    content = f"""# P27 Full True-Date Backfill Expansion — Summary

**Gate**: `{gate.p27_gate}`  
**Date Range**: {summary.date_start} → {summary.date_end}  
**Generated**: {gate.generated_at}

## Segment Stats
- Segments: {summary.n_segments}
- Dates Requested: {summary.n_dates_requested}
- Dates Ready: {summary.n_dates_ready}
- Dates Empty: {summary.n_dates_empty}
- Dates Blocked: {summary.n_dates_blocked}

## Performance
- Active Entries: {summary.total_active_entries}
- Settled Win: {summary.total_settled_win}
- Settled Loss: {summary.total_settled_loss}
- Unsettled: {summary.total_unsettled}
- Total Stake: {summary.total_stake_units:.4f} units
- Total PnL: {summary.total_pnl_units:.4f} units
- Aggregate ROI: **{roi_pct}**
- Hit Rate: **{hit_pct}**

## Safeguards
- paper_only: {summary.paper_only}
- production_ready: {summary.production_ready}

## Blocked Segments
{', '.join(summary.blocked_segment_list) if summary.blocked_segment_list else 'None'}

## Blocker Reason
{summary.blocker_reason or 'None'}
"""
    path.write_text(content, encoding="utf-8")
