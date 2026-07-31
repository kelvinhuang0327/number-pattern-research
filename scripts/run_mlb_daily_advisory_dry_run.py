#!/usr/bin/env python3
"""CLI runner for MLB Daily Advisory Dry-run MVP.

Usage:
    .venv/bin/python scripts/run_mlb_daily_advisory_dry_run.py --date 2026-05-07 --mode today --limit 15
    .venv/bin/python scripts/run_mlb_daily_advisory_dry_run.py --date 2025-07-01 --mode replay --limit 15
    .venv/bin/python scripts/run_mlb_daily_advisory_dry_run.py --date 2026-05-07 --mode today --source fixture --allow-fixture-current-source true --limit 15

All output is paper-only / no-real-bet / no-profit-claim.
"""
from __future__ import annotations

import argparse
import os
import sys

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from orchestrator.mlb_daily_advisory import (
    run_mlb_daily_advisory,
    DEFAULT_LEDGER_PATH,
    COMPLETION_MARKER,
)
from orchestrator.mlb_current_sources import (
    load_fixture_schedule_odds,
    probe_current_mlb_source,
    merge_current_source_with_advisory_rows,
    DEFAULT_FIXTURE_PATH,
    SOURCE_MODE_FIXTURE,
    SOURCE_MODE_CURRENT,
    SOURCE_MODE_REPLAY,
)


def build_report_paths(date_str: str) -> tuple[str, str]:
    """Derive default JSON report and markdown report paths from date string."""
    date_no_dash = date_str.replace("-", "")
    json_path = f"reports/mlb_daily_advisory_dry_run_{date_no_dash}.json"
    # Markdown always goes to the 20260507 folder (today's planning folder)
    md_path = f"00-BettingPlan/20260507/mlb_daily_advisory_dry_run_report_{date_no_dash}.md"
    return json_path, md_path


def print_summary(result: dict, report_path: str, ledger_path: str) -> None:
    """Print CLI summary to stdout."""
    sep = "=" * 62
    rs = result.get("review_summary", {})
    wl = rs.get("win_loss_push_summary", {})

    print(f"\n{sep}")
    print("MLB Daily Advisory — Dry-run MVP  (PAPER-ONLY / NO REAL BET)")
    print(sep)
    print(f"requested_date           : {result['requested_date']}")
    print(f"requested_mode           : {result['requested_mode']}")
    print(f"effective_mode           : {result['effective_mode']}")
    print(f"source_mode              : {result.get('source_mode', 'replay')}")
    print(f"fixture_source_used      : {result.get('fixture_source_used', False)}")
    print(f"current_source_reachable : {result.get('current_source_reachable', False)}")
    print(f"model_prediction_available: {result.get('model_prediction_available', True)}")

    if result.get("actual_today_schedule_unavailable"):
        print(f"  ↳ today schedule unavailable — auto-fallback to replay mode")
        print(f"  ↳ actual_date_used           : {result.get('actual_date_used')}")

    print(f"total_games_loaded       : {result['total_games_loaded']}")
    print(f"total_advisories         : {result['total_advisories']}")
    print(f"total_ledger_entries_written: {result['total_ledger_entries_written']}")

    if result.get("duplicated_skipped_count"):
        print(f"duplicated_skipped_count : {result['duplicated_skipped_count']}")

    print(f"review_status_summary:")
    print(f"  pass_count             : {rs.get('pass_count', 0)}")
    print(f"  watch_only_count       : {rs.get('watch_only_count', 0)}")
    print(f"  lean_count             : {rs.get('lean_count', 0)}")
    print(f"  market_only_shadow_count: {rs.get('market_only_shadow_count', 0)}")
    print(f"  pending_result_count   : {rs.get('pending_result_count', 0)}")
    print(f"  reviewed_count         : {rs.get('reviewed_count', 0)}")

    if wl.get("won", 0) + wl.get("lost", 0) > 0:
        print(f"  paper W/L/P            : {wl.get('won',0)}W / {wl.get('lost',0)}L / {wl.get('push',0)}P")

    brier_ml = rs.get("brier_by_market_type", {}).get("moneyline")
    if brier_ml:
        print(f"brier_score (moneyline)  : {brier_ml['brier']} (n={brier_ml['n']}, bss={brier_ml['bss_vs_baseline']})")

    print(f"gate                     : {result['gate']}")
    print(f"output_report_path       : {report_path}")
    print(f"ledger_path              : {ledger_path}")
    print(sep)
    print("⚠️  PAPER-ONLY — NO REAL BET — NO PROFIT CLAIM — NO EDGE CLAIM")
    print(f"completion_marker        : {COMPLETION_MARKER}")
    print(f"{sep}\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="MLB Daily Advisory Dry-run MVP (paper-only / no real bet)"
    )
    parser.add_argument(
        "--date",
        required=True,
        metavar="YYYY-MM-DD",
        help="Target date for advisory (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--mode",
        choices=["today", "replay"],
        default="today",
        help="Advisory mode: 'today' (with auto-fallback) or 'replay'",
    )
    parser.add_argument(
        "--source",
        choices=["replay", "fixture", "current"],
        default="replay",
        help=(
            "Data source: 'replay' (historical JSONL), "
            "'fixture' (test fixture data), "
            "'current' (live API if available)"
        ),
    )
    parser.add_argument(
        "--allow-fixture-current-source",
        default="false",
        help="Allow fixture fallback when current source unavailable (true|false)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=15,
        help="Maximum number of games to process (default: 15)",
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
    parser.add_argument(
        "--ledger-path",
        default=DEFAULT_LEDGER_PATH,
        help=f"Paper betting ledger path (default: {DEFAULT_LEDGER_PATH})",
    )
    args = parser.parse_args()

    allow_fixture = args.allow_fixture_current_source.lower() == "true"
    source = args.source

    # Resolve paths
    json_default, md_default = build_report_paths(args.date)
    report_path = args.report_path or json_default
    markdown_path = args.markdown_path or md_default
    ledger_path = args.ledger_path

    # ─── Source resolution ────────────────────────────────────────────────
    override_games = None
    fixture_source_used = False
    current_source_reachable = False
    model_prediction_available = True
    effective_source_mode = SOURCE_MODE_REPLAY
    fallback_reason: str | None = None

    if args.mode == "replay" or source == "replay":
        # Pure replay: always use historical JSONL, no current source needed
        effective_source_mode = SOURCE_MODE_REPLAY

    elif source == "fixture":
        # Fixture mode: load test fixture data, merge with empty prediction rows
        snapshots = load_fixture_schedule_odds(DEFAULT_FIXTURE_PATH)
        if snapshots:
            override_games = merge_current_source_with_advisory_rows(snapshots, [])
            fixture_source_used = True
            effective_source_mode = SOURCE_MODE_FIXTURE
            model_prediction_available = False
        else:
            # Fixture file missing — fallback to replay
            fallback_reason = "fixture_file_missing: fallback to replay"
            effective_source_mode = SOURCE_MODE_REPLAY

    elif source == "current":
        # Current mode: probe live source, fallback as configured
        health = probe_current_mlb_source(args.date)
        current_source_reachable = health.reachable

        if health.reachable:
            # Future: load from live API
            # snapshots = fetch_live_schedule(args.date)
            # For now, live API not configured
            fallback_reason = "live_api_not_configured: falling back"
            current_source_reachable = False

        if not current_source_reachable:
            if allow_fixture:
                # Use fixture as fallback for current source
                snapshots = load_fixture_schedule_odds(DEFAULT_FIXTURE_PATH)
                if snapshots:
                    override_games = merge_current_source_with_advisory_rows(snapshots, [])
                    fixture_source_used = True
                    effective_source_mode = SOURCE_MODE_FIXTURE
                    model_prediction_available = False
                    fallback_reason = (
                        fallback_reason or "current_source_unavailable"
                    ) + "; fixture_source_used=true per --allow-fixture-current-source"
                else:
                    fallback_reason = (
                        (fallback_reason or "current_source_unavailable")
                        + "; fixture_file_missing; fallback to replay"
                    )
                    effective_source_mode = SOURCE_MODE_REPLAY
            else:
                # No fixture allowed — fallback to replay
                fallback_reason = (
                    (fallback_reason or "current_source_unavailable")
                    + "; replay_fallback (--allow-fixture-current-source false)"
                )
                effective_source_mode = SOURCE_MODE_REPLAY

    result = run_mlb_daily_advisory(
        date_str=args.date,
        mode=args.mode,
        limit=args.limit,
        ledger_path=ledger_path,
        report_path=report_path,
        markdown_path=markdown_path,
        write_reports=True,
        override_games=override_games,
        source_mode=effective_source_mode,
        fixture_source_used=fixture_source_used,
        current_source_reachable=current_source_reachable,
        model_prediction_available=model_prediction_available,
    )

    if fallback_reason:
        print(f"  ↳ source_fallback_reason: {fallback_reason}")

    print_summary(result, report_path, ledger_path)


if __name__ == "__main__":
    main()
