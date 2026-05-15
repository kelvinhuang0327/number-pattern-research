#!/usr/bin/env python3
"""
H6 Daily Operations Report — CLI Tool
======================================

使用方式:
  # 為特定期號生成報告
  python3 scripts/h6_daily_report.py --draw-no 115000001

  # 自動找最新期號
  python3 scripts/h6_daily_report.py --latest

  # 輸出純 JSON（機器可讀）
  python3 scripts/h6_daily_report.py --draw-no 115000001 --json

  # 指定輸出目錄
  python3 scripts/h6_daily_report.py --draw-no 115000001 --output-dir /tmp/reports

Exit codes:
  0 — success (including PENDING_OUTCOME)
  1 — invalid arguments or critical error
"""
from __future__ import annotations

import argparse
import json
import os
import sys

# ── sys.path setup ─────────────────────────────────────────────────────────────
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.normpath(os.path.join(_SCRIPT_DIR, ".."))
_LOTTERY_API = os.path.join(_ROOT, "lottery_api")
if _LOTTERY_API not in sys.path:
    sys.path.insert(0, _LOTTERY_API)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from engine.h6_report_generator import generate_report  # noqa: E402
from engine.draw_no_hygiene import is_test_draw_no, is_production_draw_no  # noqa: E402


# ── helpers ────────────────────────────────────────────────────────────────────

def _validate_draw_no(raw: str, game_type: str = "DAILY_539") -> str:
    """Validate draw_no: non-empty, not PENDING, not test prefix, and within production range."""
    v = raw.strip()
    if not v:
        raise ValueError("draw_no cannot be empty")
    if v.upper() == "PENDING":
        raise ValueError("draw_no='PENDING' is not a valid draw number")
    if is_test_draw_no(v, game_type):
        raise ValueError(
            f"draw_no='{v}' is a test/synthetic identifier. "
            "Only production draw_nos are accepted. "
            "(Numeric draw_nos must be in the valid range for the game type, "
            "e.g. 114001–999999999 for DAILY_539.)"
        )
    return v


def _print_summary(report: dict) -> None:
    """Print a human-readable summary to stdout."""
    meta = report.get("report_meta", {})
    strat = report.get("strategy", {})
    pred = report.get("this_draw_prediction", {})
    outcome = report.get("this_draw_outcome", {})
    mon = report.get("live_monitoring", {})
    risk = report.get("risk_assessment", {})
    action = report.get("action_recommendation", {})
    recent = report.get("recent_outcomes_summary", {})
    out = report.get("output", {})

    SEP = "=" * 60

    print(f"\n{SEP}")
    print(f"  H6 DAILY_539 — Daily Operations Report")
    print(f"  draw_no : {meta.get('draw_no')}")
    print(f"  status  : {meta.get('report_status')}")
    print(f"  date    : {meta.get('report_date')}")
    print(f"{SEP}")

    print(f"\n[Strategy]")
    print(f"  active_strategy : {strat.get('active_strategy')}")
    print(f"  shadow_strategy : {strat.get('shadow_strategy')}")
    print(f"  rollback_status : {strat.get('rollback_status')}")
    print(f"  planner_focus   : {strat.get('planner_focus')}")

    print(f"\n[This Draw — Prediction]")
    if pred.get("found"):
        for i, bet in enumerate(pred.get("predicted_bets", []), 1):
            print(f"  bet_{i} : {bet}")
        print(f"  generated_at : {pred.get('generated_at')}")
    else:
        print("  ⚠️  No prediction found for this draw_no")

    print(f"\n[This Draw — Outcome]")
    o_status = outcome.get("status", "PENDING_OUTCOME")
    if o_status == "RECORDED":
        print(f"  winning_numbers   : {outcome.get('winning_numbers')}")
        print(f"  hit_counts_per_bet: {outcome.get('hit_counts_per_bet')}")
        print(f"  best_hit_count    : {outcome.get('best_hit_count')}")
        print(f"  roi               : {outcome.get('roi'):.4f}" if outcome.get("roi") is not None else "  roi : N/A")
        print(f"  pnl               : {outcome.get('pnl'):.4f}" if outcome.get("pnl") is not None else "  pnl : N/A")
    else:
        print("  ⏳ PENDING_OUTCOME — outcome not yet recorded")
        print(f"  Run: python3 scripts/h6_record_outcome.py --draw_no {meta.get('draw_no')} --winning \"N1,N2,N3,N4,N5\"")

    print(f"\n[Live Monitoring]")
    edge_30 = mon.get("live_30p_edge")
    edge_50 = mon.get("live_50p_edge")
    print(f"  live_30p_edge         : {edge_30:.4f}" if edge_30 is not None else "  live_30p_edge : N/A")
    print(f"  live_50p_edge         : {edge_50:.4f}" if edge_50 is not None else "  live_50p_edge : N/A")
    print(f"  consecutive_neg_30p   : {mon.get('consecutive_negative_30p', 0)}")
    print(f"  current_regime        : {mon.get('current_regime')}")
    print(f"  bear_regime_warning   : {mon.get('bear_regime_warning')}")
    print(f"  rollback_triggered    : {mon.get('rollback_triggered')}")

    print(f"\n[Recent Outcomes (last {recent.get('count', 0)})]")
    print(f"  avg_roi         : {recent.get('avg_roi'):.4f}" if recent.get("avg_roi") is not None else "  avg_roi : N/A")
    print(f"  avg_match_count : {recent.get('avg_match_count'):.2f}" if recent.get("avg_match_count") is not None else "  avg_match_count : N/A")
    print(f"  max_hit         : {recent.get('max_hit', 0)}")
    print(f"  losing_streak   : {recent.get('losing_streak', 0)}")
    print(f"  trend (newest)  : {recent.get('best_hit_trend', [])}")

    print(f"\n[Risk Assessment]")
    risk_icon = {"LOW": "✓", "MEDIUM": "⚠", "HIGH": "✗"}.get(risk.get("risk_level", "LOW"), "?")
    print(f"  risk_level : {risk_icon}  {risk.get('risk_level')}")
    for factor in risk.get("risk_factors", []):
        print(f"    · {factor}")

    print(f"\n[Action Recommendation]")
    print(f"  → {action.get('action')}")
    print(f"    {action.get('reason')}")

    print(f"\n[Output Files]")
    print(f"  JSON     : {out.get('json_path', 'N/A')}")
    print(f"  Markdown : {out.get('markdown_path', 'N/A')}")
    print()


# ── main ───────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate H6 DAILY_539 daily operations report",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--draw-no", "--draw_no",
        dest="draw_no",
        metavar="DRAW_NO",
        help="Target draw number (e.g. 115000001)",
    )
    group.add_argument(
        "--latest",
        action="store_true",
        help="Auto-detect most recent draw_no from DB",
    )
    parser.add_argument(
        "--game-type", "--game_type",
        dest="game_type",
        default="DAILY_539",
        help="Game type (default: DAILY_539)",
    )
    parser.add_argument(
        "--output-dir", "--output_dir",
        dest="output_dir",
        default=None,
        help="Directory for output files (default: runtime/h6_daily_reports/)",
    )
    parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Print full JSON report to stdout (machine-readable mode)",
    )

    args = parser.parse_args()

    # Require one of --draw-no or --latest
    if not args.draw_no and not args.latest:
        parser.error("One of --draw-no or --latest is required")

    # Validate draw_no
    draw_no = None
    if args.draw_no:
        try:
            draw_no = _validate_draw_no(args.draw_no, args.game_type)
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1

    try:
        report = generate_report(
            game_type=args.game_type,
            draw_no=draw_no,
            latest=args.latest,
            output_dir=args.output_dir,
        )
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"ERROR: unexpected failure: {exc}", file=sys.stderr)
        return 1

    if args.json_output:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_summary(report)

    return 0


if __name__ == "__main__":
    sys.exit(main())
