"""
wbc_backend/recommendation/p24_backfill_stability_auditor.py

P24 — Backfill Performance Stability Auditor.

Orchestrates:
1. Source integrity audit (p24_source_integrity_auditor)
2. Performance stability analysis (p24_performance_stability_analyzer)
3. Gate determination
4. Writing 6 output files

PAPER_ONLY — no production systems, no real bets.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from wbc_backend.recommendation.p24_backfill_stability_contract import (
    MIN_INDEPENDENT_SOURCE_DATES,
    P24_BACKFILL_STABILITY_AUDIT_READY,
    P24_BLOCKED_CONTRACT_VIOLATION,
    P24_BLOCKED_DUPLICATE_SOURCE_REPLAY,
    P24_BLOCKED_INSUFFICIENT_INDEPENDENT_DATES,
    P24_FAIL_INPUT_MISSING,
    STABILITY_ACCEPTABLE,
    STABILITY_INSUFFICIENT_INDEPENDENT_DATES,
    STABILITY_SOURCE_INTEGRITY_BLOCKED,
    P24StabilityAuditSummary,
    P24StabilityGateResult,
)
from wbc_backend.recommendation.p24_source_integrity_auditor import (
    audit_materialized_source_hashes,
    detect_duplicate_source_groups,
    summarize_source_integrity,
)
from wbc_backend.recommendation.p24_performance_stability_analyzer import (
    compute_per_date_performance_profiles,
    compute_variance_metrics,
    compute_weighted_aggregate_metrics,
    detect_too_uniform_performance,
    load_p23_date_results,
)


def _date_range(date_start: str, date_end: str) -> List[str]:
    """Generate list of dates from date_start to date_end inclusive (YYYY-MM-DD)."""
    start = date.fromisoformat(date_start)
    end = date.fromisoformat(date_end)
    result = []
    current = start
    while current <= end:
        result.append(current.isoformat())
        current = date.fromordinal(current.toordinal() + 1)
    return result


def run_backfill_stability_audit(
    date_start: str,
    date_end: str,
    p23_dir: str,
    paper_base_dir: str,
) -> tuple:
    """Run full P24 stability audit.

    Returns (P24StabilityAuditSummary, P24StabilityGateResult, raw_audit_data).
    """
    date_range = _date_range(date_start, date_end)
    n_dates = len(date_range)

    # --- Load P23 date results ---
    date_results_csv = Path(p23_dir) / "date_replay_results.csv"
    if not date_results_csv.exists():
        gate = P24StabilityGateResult(
            p24_gate=P24_FAIL_INPUT_MISSING,
            audit_status=P24_FAIL_INPUT_MISSING,
            date_start=date_start,
            date_end=date_end,
            n_dates_audited=n_dates,
            n_independent_source_dates=0,
            n_duplicate_source_groups=0,
            source_hash_unique_count=0,
            source_hash_duplicate_count=0,
            roi_std_by_date=0.0,
            hit_rate_std_by_date=0.0,
            blocker_reason=f"P23 date results CSV not found: {date_results_csv}",
            recommended_next_action="Verify P23 outputs exist before running P24.",
        )
        raise FileNotFoundError(
            f"P23 date results CSV not found: {date_results_csv}"
        )

    df_dates = load_p23_date_results(str(date_results_csv))

    # --- Source integrity audit ---
    raw_source_results = audit_materialized_source_hashes(date_range, paper_base_dir)
    duplicate_findings = detect_duplicate_source_groups(raw_source_results)
    source_profile = summarize_source_integrity(
        raw_source_results, duplicate_findings, n_dates
    )

    # Build per-date source hash maps for performance profiles
    source_hash_map = {
        r["run_date"]: r["content_hash"] for r in raw_source_results if r["file_found"]
    }
    game_id_hash_map = {
        r["run_date"]: r["game_id_set_hash"]
        for r in raw_source_results
        if r["file_found"]
    }
    game_date_range_map = {
        r["run_date"]: r["game_date_range_str"]
        for r in raw_source_results
        if r["file_found"]
    }
    run_date_match_map = {
        r["run_date"]: r["run_date_matches_game_date"]
        for r in raw_source_results
        if r["file_found"]
    }

    # --- Performance stability ---
    profiles = compute_per_date_performance_profiles(
        df_dates,
        source_hash_map=source_hash_map,
        game_id_set_hash_map=game_id_hash_map,
        game_date_range_map=game_date_range_map,
        run_date_matches_game_date_map=run_date_match_map,
    )
    aggregate = compute_weighted_aggregate_metrics(profiles)
    variance = compute_variance_metrics(profiles)
    is_perf_suspicious, perf_reason = detect_too_uniform_performance(profiles)

    # --- Gate determination ---
    gate_result, summary = determine_p24_gate(
        date_start=date_start,
        date_end=date_end,
        n_dates=n_dates,
        source_profile=source_profile,
        aggregate=aggregate,
        variance=variance,
        is_perf_suspicious=is_perf_suspicious,
        perf_reason=perf_reason,
    )

    raw_audit_data = {
        "raw_source_results": raw_source_results,
        "duplicate_findings": duplicate_findings,
        "profiles": profiles,
        "source_profile": source_profile,
    }

    return summary, gate_result, raw_audit_data


def determine_p24_gate(
    date_start: str,
    date_end: str,
    n_dates: int,
    source_profile,
    aggregate: Dict,
    variance: Dict,
    is_perf_suspicious: bool,
    perf_reason: str,
) -> tuple:
    """Determine P24 gate and build summary/gate dataclasses."""

    # Priority 1: Contract violation (shouldn't happen but guard)
    # Priority 2: Duplicate source replay — majority of dates duplicated
    # Priority 3: Insufficient independent dates
    # Priority 4: Ready

    n_independent = source_profile.n_independent_source_dates
    n_dup_groups = source_profile.n_duplicate_source_groups

    if source_profile.audit_status == STABILITY_SOURCE_INTEGRITY_BLOCKED:
        p24_gate = P24_BLOCKED_DUPLICATE_SOURCE_REPLAY
        audit_status = STABILITY_SOURCE_INTEGRITY_BLOCKED
        blocker = source_profile.blocker_reason
        recommended = (
            "Proceed to P25 Full Historical Source Separation / "
            "True Multi-Date Artifact Builder."
        )
    elif n_independent < MIN_INDEPENDENT_SOURCE_DATES:
        p24_gate = P24_BLOCKED_INSUFFICIENT_INDEPENDENT_DATES
        audit_status = STABILITY_INSUFFICIENT_INDEPENDENT_DATES
        blocker = (
            f"Only {n_independent} independent source date(s) found "
            f"(minimum required: {MIN_INDEPENDENT_SOURCE_DATES}). "
            "Backfill does not constitute independent multi-date evidence."
        )
        recommended = (
            "Proceed to P25 Full Historical Source Separation / "
            "True Multi-Date Artifact Builder."
        )
    else:
        p24_gate = P24_BACKFILL_STABILITY_AUDIT_READY
        audit_status = STABILITY_ACCEPTABLE
        blocker = ""
        recommended = "Proceed to P25 Backfill Strategy Variance Audit."

    summary = P24StabilityAuditSummary(
        date_start=date_start,
        date_end=date_end,
        n_dates_audited=n_dates,
        n_independent_source_dates=n_independent,
        n_duplicate_source_groups=n_dup_groups,
        aggregate_roi_units=aggregate["aggregate_roi_units"],
        aggregate_hit_rate=aggregate["aggregate_hit_rate"],
        total_stake_units=aggregate["total_stake_units"],
        total_pnl_units=aggregate["total_pnl_units"],
        roi_std_by_date=variance["roi_std_by_date"],
        roi_min_by_date=variance["roi_min_by_date"],
        roi_max_by_date=variance["roi_max_by_date"],
        hit_rate_std_by_date=variance["hit_rate_std_by_date"],
        hit_rate_min_by_date=variance["hit_rate_min_by_date"],
        hit_rate_max_by_date=variance["hit_rate_max_by_date"],
        active_entry_std_by_date=variance["active_entry_std_by_date"],
        active_entry_min_by_date=variance["active_entry_min_by_date"],
        active_entry_max_by_date=variance["active_entry_max_by_date"],
        source_hash_unique_count=source_profile.source_hash_unique_count,
        source_hash_duplicate_count=source_profile.source_hash_duplicate_count,
        all_dates_date_mismatch=source_profile.all_dates_date_mismatch,
        audit_status=audit_status,
        blocker_reason=blocker,
    )

    gate_result = P24StabilityGateResult(
        p24_gate=p24_gate,
        audit_status=audit_status,
        date_start=date_start,
        date_end=date_end,
        n_dates_audited=n_dates,
        n_independent_source_dates=n_independent,
        n_duplicate_source_groups=n_dup_groups,
        source_hash_unique_count=source_profile.source_hash_unique_count,
        source_hash_duplicate_count=source_profile.source_hash_duplicate_count,
        roi_std_by_date=variance["roi_std_by_date"],
        hit_rate_std_by_date=variance["hit_rate_std_by_date"],
        blocker_reason=blocker,
        recommended_next_action=recommended,
    )

    return gate_result, summary


def write_p24_outputs(
    output_dir: str,
    summary: P24StabilityAuditSummary,
    gate_result: P24StabilityGateResult,
    raw_audit_data: Dict,
) -> Dict[str, str]:
    """Write all 6 P24 output files. Returns dict of {name: path}."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    now_iso = datetime.now(timezone.utc).isoformat()

    # 1. stability_audit_summary.json
    summary_dict = {k: v for k, v in summary.__dict__.items()}
    summary_dict["generated_at"] = now_iso
    summary_path = out / "stability_audit_summary.json"
    summary_path.write_text(json.dumps(summary_dict, indent=2, default=str))

    # 2. stability_audit_summary.md
    md_path = out / "stability_audit_summary.md"
    _write_summary_md(md_path, summary, gate_result, now_iso)

    # 3. source_integrity_audit.json
    source_profile = raw_audit_data["source_profile"]
    dup_findings_serializable = [
        {
            "group_id": f.group_id,
            "content_hash": f.content_hash[:16] + "...",
            "game_id_set_hash": f.game_id_set_hash[:16] + "...",
            "dates_in_group": list(f.dates_in_group),
            "n_dates": f.n_dates,
            "representative_game_date_range": f.representative_game_date_range,
            "is_date_mismatch": f.is_date_mismatch,
        }
        for f in raw_audit_data["duplicate_findings"]
    ]
    src_audit = {
        "n_dates_audited": source_profile.n_dates_audited,
        "n_independent_source_dates": source_profile.n_independent_source_dates,
        "n_duplicate_source_groups": source_profile.n_duplicate_source_groups,
        "source_hash_unique_count": source_profile.source_hash_unique_count,
        "source_hash_duplicate_count": source_profile.source_hash_duplicate_count,
        "game_id_set_unique_count": source_profile.game_id_set_unique_count,
        "all_dates_date_mismatch": source_profile.all_dates_date_mismatch,
        "any_date_date_mismatch": source_profile.any_date_date_mismatch,
        "audit_status": source_profile.audit_status,
        "blocker_reason": source_profile.blocker_reason,
        "per_date_details": [
            {k: v for k, v in r.items() if k not in ("file_hash",)}
            for r in raw_audit_data["raw_source_results"]
        ],
        "generated_at": now_iso,
    }
    src_audit_path = out / "source_integrity_audit.json"
    src_audit_path.write_text(json.dumps(src_audit, indent=2, default=str))

    # 4. performance_stability_audit.json
    profiles = raw_audit_data["profiles"]
    perf_audit = {
        "n_profiles": len(profiles),
        "per_date": [
            {
                "run_date": p.run_date,
                "n_active_entries": p.n_active_entries,
                "n_settled_win": p.n_settled_win,
                "n_settled_loss": p.n_settled_loss,
                "n_unsettled": p.n_unsettled,
                "total_stake_units": p.total_stake_units,
                "total_pnl_units": p.total_pnl_units,
                "roi_units": p.roi_units,
                "hit_rate": p.hit_rate,
                "game_id_coverage": p.game_id_coverage,
                "source_hash_content_prefix": p.source_hash_content[:16] + "..."
                if p.source_hash_content
                else "",
                "game_date_range_str": p.game_date_range_str,
                "run_date_matches_game_date": p.run_date_matches_game_date,
            }
            for p in profiles
        ],
        "aggregate_roi_units": summary.aggregate_roi_units,
        "aggregate_hit_rate": summary.aggregate_hit_rate,
        "total_stake_units": summary.total_stake_units,
        "total_pnl_units": summary.total_pnl_units,
        "roi_std_by_date": summary.roi_std_by_date,
        "roi_min_by_date": summary.roi_min_by_date,
        "roi_max_by_date": summary.roi_max_by_date,
        "hit_rate_std_by_date": summary.hit_rate_std_by_date,
        "hit_rate_min_by_date": summary.hit_rate_min_by_date,
        "hit_rate_max_by_date": summary.hit_rate_max_by_date,
        "generated_at": now_iso,
    }
    perf_path = out / "performance_stability_audit.json"
    perf_path.write_text(json.dumps(perf_audit, indent=2, default=str))

    # 5. duplicate_source_findings.json
    dup_path = out / "duplicate_source_findings.json"
    dup_path.write_text(
        json.dumps(
            {
                "n_duplicate_source_groups": len(dup_findings_serializable),
                "findings": dup_findings_serializable,
                "generated_at": now_iso,
            },
            indent=2,
        )
    )

    # 6. p24_gate_result.json
    gate_dict = {k: v for k, v in gate_result.__dict__.items()}
    gate_dict["generated_at"] = now_iso
    gate_path = out / "p24_gate_result.json"
    gate_path.write_text(json.dumps(gate_dict, indent=2, default=str))

    return {
        "stability_audit_summary.json": str(summary_path),
        "stability_audit_summary.md": str(md_path),
        "source_integrity_audit.json": str(src_audit_path),
        "performance_stability_audit.json": str(perf_path),
        "duplicate_source_findings.json": str(dup_path),
        "p24_gate_result.json": str(gate_path),
    }


def _write_summary_md(
    path: Path,
    summary: P24StabilityAuditSummary,
    gate_result: P24StabilityGateResult,
    generated_at: str,
) -> None:
    """Write human-readable stability audit summary."""
    lines = [
        "# P24 Backfill Performance Stability Audit Summary",
        "",
        f"**Gate**: `{gate_result.p24_gate}`",
        f"**Audit Status**: `{summary.audit_status}`",
        f"**Generated**: {generated_at}",
        "",
        "## Date Range",
        f"- date_start: {summary.date_start}",
        f"- date_end: {summary.date_end}",
        f"- n_dates_audited: {summary.n_dates_audited}",
        f"- n_independent_source_dates: {summary.n_independent_source_dates}",
        f"- n_duplicate_source_groups: {summary.n_duplicate_source_groups}",
        "",
        "## Source Integrity",
        f"- source_hash_unique_count: {summary.source_hash_unique_count}",
        f"- source_hash_duplicate_count: {summary.source_hash_duplicate_count}",
        f"- all_dates_date_mismatch: {summary.all_dates_date_mismatch}",
        "",
        "## Aggregate Performance (PAPER ONLY — NOT independent evidence)",
        f"- aggregate_roi_units: {summary.aggregate_roi_units:.6f}",
        f"- aggregate_hit_rate: {summary.aggregate_hit_rate:.6f}",
        f"- total_stake_units: {summary.total_stake_units:.4f}",
        f"- total_pnl_units: {summary.total_pnl_units:.6f}",
        "",
        "## Per-Date Variance",
        f"- roi_std_by_date: {summary.roi_std_by_date:.8f}",
        f"- roi_min_by_date: {summary.roi_min_by_date:.6f}",
        f"- roi_max_by_date: {summary.roi_max_by_date:.6f}",
        f"- hit_rate_std_by_date: {summary.hit_rate_std_by_date:.8f}",
        f"- hit_rate_min_by_date: {summary.hit_rate_min_by_date:.6f}",
        f"- hit_rate_max_by_date: {summary.hit_rate_max_by_date:.6f}",
        f"- active_entry_min_by_date: {summary.active_entry_min_by_date}",
        f"- active_entry_max_by_date: {summary.active_entry_max_by_date}",
        "",
        "## Gate Details",
        f"- paper_only: {summary.paper_only}",
        f"- production_ready: {summary.production_ready}",
    ]
    if summary.blocker_reason:
        lines += [
            "",
            "## Blocker Reason",
            summary.blocker_reason,
        ]
    lines += [
        "",
        "## Next Action",
        gate_result.recommended_next_action,
    ]
    path.write_text("\n".join(lines) + "\n")
