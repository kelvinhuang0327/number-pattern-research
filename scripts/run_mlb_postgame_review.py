"""Post-game review CLI script.

Usage:
  .venv/bin/python scripts/run_mlb_postgame_review.py --date 2026-05-07 --source fixture
  .venv/bin/python scripts/run_mlb_postgame_review.py --date 2025-07-01 --source replay

PAPER-ONLY — NO REAL BET — NO PROFIT CLAIM
"""
from __future__ import annotations

import argparse
import json
import os
import sys


def build_report_paths(date_str: str) -> tuple[str, str, str]:
    """Build default report paths for the given date."""
    date_no_dash = date_str.replace("-", "")
    json_path = f"reports/mlb_postgame_review_{date_no_dash}.json"
    snapshot_path = f"reports/mlb_paper_betting_reviewed_snapshot_{date_no_dash}.jsonl"
    md_path = f"00-BettingPlan/{date_no_dash}/mlb_postgame_review_report_{date_no_dash}.md"
    return json_path, snapshot_path, md_path


def print_summary(
    payload: dict,
    json_report_path: str,
    snapshot_path: str,
    markdown_path: str | None,
) -> None:
    """Print a concise human-readable summary of the review results."""
    rs = payload.get("review_summary", {})
    gate = payload.get("gate", "UNKNOWN")
    marker = payload.get("completion_marker", "")
    source_mode = payload.get("source_mode", "")
    review_date = payload.get("review_date", "")

    print("")
    print("=" * 66)
    print("  MLB Post-game Review — PAPER-ONLY / NO REAL BET")
    print("=" * 66)
    print(f"  review_date        : {review_date}")
    print(f"  source_mode        : {source_mode}")
    print(f"  ledger_path        : {payload.get('ledger_path', '')}")
    print(f"  reviewed_snapshot  : {snapshot_path}")
    print("")
    print(f"  total_ledger_entries  : {rs.get('total_ledger_entries', 0)}")
    print(f"  matched_results       : {rs.get('matched_results', 0)}")
    print(f"  pending_results       : {rs.get('pending_results', 0)}")
    print(f"  reviewed_count        : {rs.get('reviewed_count', 0)}")
    print(f"  won                   : {rs.get('won_count', 0)}")
    print(f"  lost                  : {rs.get('lost_count', 0)}")
    print(f"  pass                  : {rs.get('pass_count', 0)}")
    print(f"  watch_only            : {rs.get('watch_only_count', 0)}")
    print(f"  lean                  : {rs.get('lean_count', 0)}")
    print(f"  market_only_shadow    : {rs.get('market_only_shadow_count', 0)}")
    print(f"  brier_score           : {rs.get('brier_score', 'N/A')}")
    print(f"  bss_vs_baseline       : {rs.get('bss_vs_baseline', 'N/A')}")
    print(f"  recommendation_acc    : {rs.get('recommendation_accuracy', 'N/A')}")
    print(f"  human_review_required : True")
    print("")
    print(f"  gate: {gate}")
    print(f"  gate_rationale: {payload.get('gate_rationale', '')[:80]}")
    print("")
    if json_report_path and os.path.exists(json_report_path):
        print(f"  JSON report   : {json_report_path}")
    if markdown_path and os.path.exists(markdown_path):
        print(f"  Markdown      : {markdown_path}")
    print("")
    print(f"  completion_marker: {marker}")
    print("=" * 66)
    print("")
    print("  ⚠️  PAPER-ONLY  NO_REAL_BET=True  NO_PROFIT_CLAIM=True")
    print("")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="MLB Post-game Review (paper-only, no real bet)"
    )
    parser.add_argument(
        "--date",
        default="2026-05-07",
        help="Review date YYYY-MM-DD (default: 2026-05-07)",
    )
    parser.add_argument(
        "--source",
        choices=["fixture", "replay", "current"],
        default="fixture",
        help="Result source mode: fixture | replay | current (default: fixture)",
    )
    parser.add_argument(
        "--ledger-path",
        default=None,
        help="Path to paper betting ledger JSONL (default: reports/mlb_paper_betting_ledger.jsonl)",
    )
    parser.add_argument(
        "--fixture-path",
        default=None,
        help="Path to fixture JSON (default: data/fixtures/mlb_current_source_sample_20260507.json)",
    )
    parser.add_argument(
        "--reviewed-snapshot-path",
        default=None,
        help="Path for reviewed snapshot JSONL output (default: auto-generated from date)",
    )
    parser.add_argument(
        "--report-path",
        default=None,
        help="Path for JSON report output (default: auto-generated from date)",
    )
    parser.add_argument(
        "--markdown-path",
        default=None,
        help="Path for markdown report output (default: auto-generated from date)",
    )
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="Dry run: skip all disk writes",
    )

    args = parser.parse_args()

    # Import here to allow running from project root with .venv
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from orchestrator.mlb_result_review import (
        DEFAULT_FIXTURE_PATH,
        DEFAULT_LEDGER_PATH,
        run_postgame_review,
    )

    date_str = args.date
    source_mode = args.source

    # Build default paths
    default_json_path, default_snapshot_path, default_md_path = build_report_paths(date_str)

    ledger_path = args.ledger_path or DEFAULT_LEDGER_PATH
    fixture_path = args.fixture_path or DEFAULT_FIXTURE_PATH
    snapshot_path = args.reviewed_snapshot_path or default_snapshot_path
    report_path = args.report_path or default_json_path
    md_path = args.markdown_path or default_md_path
    write_reports = not args.no_write

    print(f"\n[run_mlb_postgame_review] date={date_str} source={source_mode}")
    print(f"  ledger_path    : {ledger_path}")
    print(f"  fixture_path   : {fixture_path}")
    print(f"  snapshot_path  : {snapshot_path}")
    print(f"  report_path    : {report_path}")
    print(f"  markdown_path  : {md_path}")
    print(f"  write_reports  : {write_reports}")
    print()

    payload = run_postgame_review(
        review_date=date_str,
        source_mode=source_mode,
        ledger_path=ledger_path,
        fixture_path=fixture_path,
        reviewed_snapshot_path=snapshot_path,
        report_path=report_path,
        markdown_path=md_path,
        write_reports=write_reports,
    )

    print_summary(payload, report_path, snapshot_path, md_path)


if __name__ == "__main__":
    main()
