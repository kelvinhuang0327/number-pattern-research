"""CLI runner for MLB Live Source Adapter Selection and Integration Plan.

Usage:
    python scripts/run_mlb_live_source_plan.py
    python scripts/run_mlb_live_source_plan.py --date 2026-05-07
    python scripts/run_mlb_live_source_plan.py --no-write

Args:
    --date       Target date (YYYY-MM-DD). Default: today.
    --no-write   Skip disk writes (dry-run output only).
    --report-dir Directory for JSON report. Default: reports/
    --plan-dir   Directory for markdown report. Default: 00-BettingPlan/
"""
from __future__ import annotations

import argparse
import datetime
import json
import sys

# Allow running from project root
sys.path.insert(0, ".")

from orchestrator.mlb_live_source_plan import (
    COMPLETION_MARKER,
    MODULE_VERSION,
    VALID_GATES,
    build_live_source_plan_report,
    build_source_candidate_matrix,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="MLB Live Source Adapter Selection and Integration Plan CLI"
    )
    parser.add_argument(
        "--date",
        default=datetime.date.today().isoformat(),
        help="Target date YYYY-MM-DD (default: today)",
    )
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="Skip disk writes (dry-run only)",
    )
    parser.add_argument(
        "--report-dir",
        default="reports",
        help="Directory for JSON report (default: reports/)",
    )
    parser.add_argument(
        "--plan-dir",
        default="00-BettingPlan",
        help="Directory for markdown report (default: 00-BettingPlan/)",
    )
    args = parser.parse_args()

    write_reports = not args.no_write
    date_nd = args.date.replace("-", "")
    report_path = f"{args.report_dir}/mlb_live_source_plan_{date_nd}.json"
    markdown_path = f"{args.plan_dir}/{args.date}/mlb_live_source_plan_report_{date_nd}.md"

    print(f"[run_mlb_live_source_plan] date={args.date} write={write_reports}")
    print(f"  report_path   : {report_path}")
    print(f"  markdown_path : {markdown_path}")
    print()

    report = build_live_source_plan_report(
        run_date=args.date,
        write_reports=write_reports,
        report_path=report_path if write_reports else None,
        markdown_path=markdown_path if write_reports else None,
    )

    gate = report.get("gate", "UNKNOWN")
    gate_rationale = report.get("gate_rationale", "")
    summary = report.get("source_candidate_summary", {})

    # ── Summary Table ──────────────────────────────────────────────────────────

    print("=" * 68)
    print("  MLB Live Source Plan — PAPER-ONLY / PLAN DOCUMENT")
    print("=" * 68)
    print(f"  module_version        : {MODULE_VERSION}")
    print(f"  run_date              : {args.date}")
    print()
    print(f"  total_candidates      : {summary.get('total_candidates', 0)}")
    print(f"    schedule            : {summary.get('schedule_candidates', 0)}")
    print(f"    odds                : {summary.get('odds_candidates', 0)}")
    print(f"    result              : {summary.get('result_candidates', 0)}")
    print(f"  recommended           : {summary.get('recommended_count', 0)}")
    print(f"  needs_verification    : {summary.get('needs_verification_count', 0)}")
    print(f"  blocked               : {summary.get('blocked_count', 0)}")
    print()

    # Recommended candidates
    candidates = build_source_candidate_matrix()
    recommended = [c for c in candidates if c.recommended]
    if recommended:
        print("  Recommended Candidates:")
        for c in recommended:
            ver_flag = " ⚠️  requires_verification" if c.requires_verification else ""
            print(f"    [{c.source_type:8s}] {c.source_name}{ver_flag}")
    print()

    # Blocked candidates
    blocked = [c for c in candidates if c.production_readiness == "blocked"]
    if blocked:
        print("  Blocked Candidates (must not be used):")
        for c in blocked:
            print(f"    [{c.source_type:8s}] {c.source_name} — {c.rejection_reason[:60] if c.rejection_reason else ''}")
    print()

    print(f"  gate                  : {gate}")
    print(f"  gate_rationale        : {gate_rationale[:80]}")
    print()

    if write_reports:
        print(f"  report_path           : {report_path}")
        print(f"  markdown_path         : {markdown_path}")
    else:
        print("  [no-write mode — reports not written to disk]")
    print()
    print(f"  completion_marker     : {COMPLETION_MARKER}")
    print("=" * 68)
    print()
    print("  ⚠️  PAPER-ONLY  PLAN_ONLY=True  NO_LIVE_API_CONNECTED=True")
    print("  ⚠️  NO_REAL_BET=True  NO_PROFIT_CLAIM=True")
    print()

    # Exit code: 0 if gate in VALID_GATES, 1 otherwise
    if gate not in VALID_GATES:
        print(f"[ERROR] Gate {gate!r} not in VALID_GATES", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
