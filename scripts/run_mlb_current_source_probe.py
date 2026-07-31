#!/usr/bin/env python3
"""MLB Current Source Probe — Adapter Validation CLI.

Probes and validates the MLB current schedule/odds source adapter.
Supports fixture mode for dry-run validation without a live API.

All outputs are paper-only / no-real-bet / no-profit-claim.

Usage:
    .venv/bin/python scripts/run_mlb_current_source_probe.py --date 2026-05-07 --source fixture
    .venv/bin/python scripts/run_mlb_current_source_probe.py --date 2026-05-07 --source current
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sys

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from orchestrator.mlb_current_sources import (
    COMPLETION_MARKER,
    DEFAULT_FIXTURE_PATH,
    MODULE_VERSION,
    NO_EDGE_CLAIM,
    NO_PROFIT_CLAIM,
    NO_REAL_BET,
    PAPER_ONLY,
    SOURCE_MODE_CURRENT,
    SOURCE_MODE_FIXTURE,
    VALID_GATES,
    build_market_coverage,
    determine_gate,
    load_fixture_schedule_odds,
    probe_current_mlb_source,
    validate_market_snapshot,
    validate_source_health,
)


# ─── Path helpers ─────────────────────────────────────────────────────────────


def build_report_paths(date_str: str) -> tuple[str, str]:
    """Derive default JSON report and markdown report paths from date string."""
    date_no_dash = date_str.replace("-", "")
    json_path = f"reports/mlb_current_source_probe_{date_no_dash}.json"
    md_path = (
        f"00-BettingPlan/20260507/mlb_current_source_probe_report_{date_no_dash}.md"
    )
    return json_path, md_path


# ─── Markdown generation ──────────────────────────────────────────────────────


def generate_markdown_report(payload: dict, md_path: str) -> None:
    """Write a human-readable markdown probe report."""
    cov = payload.get("market_coverage", {})
    health = payload.get("source_health", {})
    snapshots = payload.get("snapshots", [])

    lines: list[str] = [
        "# MLB Current Source Probe — Adapter Validation Report",
        "",
        "> **⚠️ PAPER-ONLY — DRY-RUN — NO REAL BET — NO PROFIT CLAIM**",
        ">",
        "> 本報告為 source adapter 驗證報告，所有 fixture 賠率均為測試用途，",
        "> 不代表任何真實下注、真實賠率、或真實 edge 聲明。",
        "",
        f"**Probe Date:** {payload.get('probe_date', '')}",
        f"**Source Mode:** `{payload.get('source_mode', '')}`",
        f"**Fixture Source Used:** `{payload.get('fixture_source_used', False)}`",
        f"**Current Source Reachable:** `{payload.get('current_source_reachable', False)}`",
        f"**Model Prediction Available:** `{payload.get('model_prediction_available', False)}`",
        f"**Total Snapshots:** {payload.get('total_snapshots', 0)}",
        f"**Report Generated:** {payload.get('run_timestamp_utc', '')}",
        "",
        "---",
        "",
        "## Source Health",
        "",
    ]
    for k, v in health.items():
        lines.append(f"- **{k}**: `{v}`")

    lines.extend([
        "",
        "---",
        "",
        "## Market Coverage Matrix",
        "",
        "| Field | Available |",
        "|-------|-----------|",
    ])
    for f in [
        "moneyline_available",
        "runline_available",
        "total_available",
        "result_available",
        "odds_available",
        "market_home_prob_available",
        "closing_market_available",
    ]:
        avail = cov.get(f, False)
        lines.append(f"| {f} | {'✅ YES' if avail else '❌ NO'} |")
    lines.extend([
        f"| source_name | `{cov.get('source_name', '')}` |",
        f"| source_mode | `{cov.get('source_mode', '')}` |",
        f"| fixture_source_used | `{payload.get('fixture_source_used', False)}` |",
        f"| current_source_reachable | `{payload.get('current_source_reachable', False)}` |",
        f"| model_prediction_available | `{payload.get('model_prediction_available', False)}` |",
    ])

    lines.extend([
        "",
        "---",
        "",
        "## Game Snapshots",
        "",
        f"Total: {payload.get('total_snapshots', 0)} games",
        "",
    ])

    if snapshots:
        lines.extend([
            "| # | Date | Away | Home | ML Home | ML Away | no-vig | Runline | Total | Status |",
            "|---|------|------|------|---------|---------|--------|---------|-------|--------|",
        ])
        for i, snap in enumerate(snapshots):
            ml_h = snap.get("home_moneyline_odds")
            ml_a = snap.get("away_moneyline_odds")
            prob = snap.get("market_home_prob_no_vig")
            rl = snap.get("runline_spread")
            tot = snap.get("total_line")
            lines.append(
                f"| {i + 1} | {snap.get('game_date', '')} "
                f"| {snap.get('away_team', '')} "
                f"| {snap.get('home_team', '')} "
                f"| {ml_h if ml_h is not None else 'N/A'} "
                f"| {ml_a if ml_a is not None else 'N/A'} "
                f"| {f'{prob:.3f}' if prob is not None else 'N/A'} "
                f"| {rl if rl is not None else 'N/A'} "
                f"| {tot if tot is not None else 'N/A'} "
                f"| {snap.get('result_status', '')} |"
            )

    val_errors = payload.get("validation_errors", [])
    lines.extend([
        "",
        "---",
        "",
        "## Validation Results",
        "",
        f"Snapshot validation errors: {len(val_errors)}",
        "",
    ])
    if val_errors:
        for err in val_errors:
            lines.append(f"- ⚠️ {err}")
    else:
        lines.append("✅ No validation errors found.")

    lines.extend([
        "",
        "---",
        "",
        "## Gate Conclusion",
        "",
        f"**Gate: `{payload.get('gate', '')}`**",
        "",
        f"> {payload.get('gate_rationale', '')}",
        "",
        "---",
        "",
        "## No Profit Claim",
        "",
        "本系統不聲稱已找到可盈利的投注 edge。",
        "所有 fixture 賠率均為測試用途，不代表任何真實獲利預期。",
        "",
        "**NO_PROFIT_CLAIM = True**",
        "**NO_EDGE_CLAIM = True**",
        "**PAPER_ONLY = True**",
        "**NO_REAL_BET = True**",
        "",
        "---",
        "",
        "## Completion Marker",
        "",
        f"`{COMPLETION_MARKER}`",
        "",
    ])

    dirpath = os.path.dirname(md_path)
    if dirpath:
        os.makedirs(dirpath, exist_ok=True)
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


# ─── CLI summary ──────────────────────────────────────────────────────────────


def print_summary(payload: dict, report_path: str) -> None:
    """Print CLI summary to stdout."""
    sep = "=" * 62
    cov = payload.get("market_coverage", {})
    health = payload.get("source_health", {})

    print(f"\n{sep}")
    print("MLB Current Source Probe  (PAPER-ONLY / NO REAL BET)")
    print(sep)
    print(f"probe_date               : {payload['probe_date']}")
    print(f"source_mode              : {payload['source_mode']}")
    print(f"fixture_source_used      : {payload['fixture_source_used']}")
    print(f"current_source_reachable : {payload['current_source_reachable']}")
    print(f"total_snapshots          : {payload['total_snapshots']}")
    print(f"source_health_reachable  : {health.get('reachable', False)}")
    if health.get("errors"):
        print(f"source_health_errors     : {health.get('errors', [])}")
    print(f"market_coverage:")
    print(f"  moneyline_available    : {cov.get('moneyline_available')}")
    print(f"  runline_available      : {cov.get('runline_available')}")
    print(f"  total_available        : {cov.get('total_available')}")
    print(f"  result_available       : {cov.get('result_available')}")
    print(f"  odds_available         : {cov.get('odds_available')}")
    val_errors = payload.get("validation_errors", [])
    if val_errors:
        print(f"validation_errors        : {val_errors}")
    print(f"gate                     : {payload['gate']}")
    print(f"output_report_path       : {report_path}")
    print(sep)
    print("⚠️  PAPER-ONLY — NO REAL BET — NO PROFIT CLAIM — NO EDGE CLAIM")
    print(f"completion_marker        : {COMPLETION_MARKER}")
    print(f"{sep}\n")


# ─── Main ─────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "MLB Current Source Probe — Adapter Validation (paper-only / no real bet)"
        )
    )
    parser.add_argument(
        "--date",
        required=True,
        metavar="YYYY-MM-DD",
        help="Probe target date",
    )
    parser.add_argument(
        "--source",
        choices=["fixture", "current"],
        default="fixture",
        help="Source mode: 'fixture' (default) or 'current' (live API if available)",
    )
    parser.add_argument(
        "--fixture-path",
        default=DEFAULT_FIXTURE_PATH,
        help=f"Fixture data path (default: {DEFAULT_FIXTURE_PATH})",
    )
    parser.add_argument(
        "--report-path",
        default=None,
        help="Override JSON report output path",
    )
    parser.add_argument(
        "--markdown-path",
        default=None,
        help="Override markdown report output path",
    )
    args = parser.parse_args()

    run_ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
    source_mode = args.source

    # Always probe live source for health status
    health = probe_current_mlb_source(args.date)
    current_source_reachable = health.reachable

    # Load snapshots according to mode
    fixture_source_used: bool = False
    snapshots = []

    if source_mode == SOURCE_MODE_FIXTURE:
        snapshots = load_fixture_schedule_odds(args.fixture_path)
        fixture_source_used = True
    elif source_mode == SOURCE_MODE_CURRENT:
        if health.reachable:
            # Future: load from live API
            # snapshots = fetch_live_mlb_games(args.date)
            snapshots = []
        # If not reachable, snapshots stays empty — caller can fallback to fixture

    # Build aggregate market coverage
    coverage = build_market_coverage(
        snapshots,
        source_name=source_mode,
        source_mode=source_mode,
    )

    # Run validations
    health_errors = validate_source_health(health)
    snapshot_errors: list[str] = []
    for snap in snapshots:
        errs = validate_market_snapshot(snap)
        snapshot_errors.extend(errs)
    all_validation_errors = health_errors + snapshot_errors

    # Gate determination
    gate, gate_rationale = determine_gate(health, snapshots, coverage)
    assert gate in VALID_GATES, f"Gate {gate!r} not in VALID_GATES"

    # Serialize snapshots for JSON output
    snapshots_dicts = [
        {
            "game_id": s.game_id,
            "game_date": s.game_date,
            "home_team": s.home_team,
            "away_team": s.away_team,
            "scheduled_start_time": s.scheduled_start_time,
            "home_moneyline_odds": s.home_moneyline_odds,
            "away_moneyline_odds": s.away_moneyline_odds,
            "home_implied_prob": (
                round(s.home_implied_prob, 4) if s.home_implied_prob is not None else None
            ),
            "away_implied_prob": (
                round(s.away_implied_prob, 4) if s.away_implied_prob is not None else None
            ),
            "market_home_prob_no_vig": (
                round(s.market_home_prob_no_vig, 4)
                if s.market_home_prob_no_vig is not None
                else None
            ),
            "runline_spread": s.runline_spread,
            "runline_home_odds": s.runline_home_odds,
            "runline_away_odds": s.runline_away_odds,
            "total_line": s.total_line,
            "over_odds": s.over_odds,
            "under_odds": s.under_odds,
            "result_status": s.result_status,
            "source_name": s.source_name,
            "source_timestamp": s.source_timestamp,
            "unavailable_fields": s.unavailable_fields,
        }
        for s in snapshots
    ]

    coverage_dict = {
        "moneyline_available": coverage.moneyline_available,
        "runline_available": coverage.runline_available,
        "total_available": coverage.total_available,
        "result_available": coverage.result_available,
        "odds_available": coverage.odds_available,
        "market_home_prob_available": coverage.market_home_prob_available,
        "closing_market_available": coverage.closing_market_available,
        "source_name": coverage.source_name,
        "source_mode": coverage.source_mode,
        "fixture_source_used": fixture_source_used,
        "current_source_reachable": current_source_reachable,
        "model_prediction_available": False,  # probe does not load model predictions
        "unavailable_reasons": coverage.unavailable_reasons,
    }

    health_dict = {
        "source_name": health.source_name,
        "source_mode": health.source_mode,
        "checked_at": health.checked_at,
        "reachable": health.reachable,
        "total_games": health.total_games,
        "moneyline_games": health.moneyline_games,
        "runline_games": health.runline_games,
        "total_games_with_total": health.total_games_with_total,
        "result_games": health.result_games,
        "errors": health.errors,
        "warnings": health.warnings,
    }

    payload: dict = {
        "module_version": MODULE_VERSION,
        "run_timestamp_utc": run_ts,
        "probe_date": args.date,
        "source_mode": source_mode,
        "fixture_source_used": fixture_source_used,
        "current_source_reachable": current_source_reachable,
        "model_prediction_available": False,
        "total_snapshots": len(snapshots),
        "source_health": health_dict,
        "market_coverage": coverage_dict,
        "snapshots": snapshots_dicts,
        "validation_errors": all_validation_errors,
        "gate": gate,
        "gate_rationale": gate_rationale,
        "safety": {
            "no_real_bet": NO_REAL_BET,
            "paper_only": PAPER_ONLY,
            "no_profit_claim": NO_PROFIT_CLAIM,
            "no_edge_claim": NO_EDGE_CLAIM,
            "production_modified": False,
        },
        "completion_marker": COMPLETION_MARKER,
    }

    # Resolve paths
    json_default, md_default = build_report_paths(args.date)
    report_path = args.report_path or json_default
    markdown_path = args.markdown_path or md_default

    # Write JSON report
    dirpath = os.path.dirname(report_path)
    if dirpath:
        os.makedirs(dirpath, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)

    # Write markdown report
    generate_markdown_report(payload, markdown_path)

    # CLI summary
    print_summary(payload, report_path)


if __name__ == "__main__":
    main()
