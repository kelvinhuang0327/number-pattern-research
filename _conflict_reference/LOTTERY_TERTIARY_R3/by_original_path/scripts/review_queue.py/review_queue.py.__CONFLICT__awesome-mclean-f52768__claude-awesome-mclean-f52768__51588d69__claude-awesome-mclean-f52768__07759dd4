#!/usr/bin/env python3
"""
scripts/review_queue.py
========================
CLI tool for managing the Phase 24 Human Review Queue.

Usage:
    python3 scripts/review_queue.py list
    python3 scripts/review_queue.py show <review_id>
    python3 scripts/review_queue.py approve <review_id> --reviewer "Kelvin" --notes "Looks good"
    python3 scripts/review_queue.py reject  <review_id> --reviewer "Kelvin" --notes "Insufficient evidence"
    python3 scripts/review_queue.py more-data <review_id> --reviewer "Kelvin" --notes "Need 50 more samples"
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure project root is in path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from orchestrator.human_review_queue import (
    STATUS_PENDING,
    STATUS_APPROVED,
    STATUS_REJECTED,
    STATUS_MORE_DATA,
    approve_review,
    get_all_reviews,
    get_review_by_id,
    reject_review,
    request_more_data,
)

# ── ANSI colours ──────────────────────────────────────────────────────────────
_RESET  = "\033[0m"
_BOLD   = "\033[1m"
_GREEN  = "\033[32m"
_RED    = "\033[31m"
_YELLOW = "\033[33m"
_CYAN   = "\033[36m"
_GREY   = "\033[90m"

_STATUS_COLOR = {
    STATUS_PENDING:   _YELLOW,
    STATUS_APPROVED:  _GREEN,
    STATUS_REJECTED:  _RED,
    STATUS_MORE_DATA: _CYAN,
}


def _color(text: str, color: str) -> str:
    return f"{color}{text}{_RESET}"


def _status_str(status: str) -> str:
    return _color(status, _STATUS_COLOR.get(status, ""))


def _risk_str(risk: str) -> str:
    mapping = {"high": _RED, "medium": _YELLOW, "low": _GREEN}
    return _color(risk.upper(), mapping.get(risk, ""))


# ── Sub-commands ──────────────────────────────────────────────────────────────

def cmd_list(_args: argparse.Namespace) -> int:
    """List all review items, newest first."""
    items = get_all_reviews(n=50)
    if not items:
        print("(no review items in queue)")
        return 0

    print(f"\n{'─' * 80}")
    print(f"  {'REVIEW ID':<20}  {'TYPE':<26}  {'RISK':<8}  {'STATUS':<22}  {'CREATED'}")
    print(f"{'─' * 80}")
    for item in items:
        rid    = item.get("review_id", "?")
        rtype  = item.get("review_type", "?")
        risk   = item.get("risk_level", "?")
        status = item.get("status", "?")
        created = (item.get("created_at_utc") or "")[:19]
        reviewer = item.get("reviewer") or ""
        rev_sfx = f"  [{reviewer}]" if reviewer else ""
        risk_col   = _risk_str(risk)
        status_col = _status_str(status)
        print(
            f"  {rid:<20}  {rtype:<26}  {risk_col}  {status_col}  {created}{rev_sfx}"
        )
    print(f"{'─' * 80}\n")
    pending_count = sum(1 for i in items if i.get("status") == STATUS_PENDING)
    if pending_count:
        print(_color(f"  ⚠  {pending_count} review(s) PENDING — planner is blocked.", _YELLOW))
    print()
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    """Show full detail of one review item."""
    item = get_review_by_id(args.review_id)
    if item is None:
        print(f"Error: review_id '{args.review_id}' not found.", file=sys.stderr)
        return 1

    print(f"\n{'=' * 60}")
    print(f"  Review: {_color(item.get('review_id', ''), _BOLD)}")
    print(f"{'=' * 60}")
    fields = [
        ("Status",              _status_str(item.get("status", "?"))),
        ("Type",                item.get("review_type", "?")),
        ("Risk",                _risk_str(item.get("risk_level", "?"))),
        ("Title",               item.get("title", "")),
        ("Source",              item.get("source", "")),
        ("Source task ID",      item.get("source_task_id", "")),
        ("Source decision ID",  item.get("source_decision_id", "")),
        ("Created at",          item.get("created_at_utc", "")),
        ("Reviewed at",         item.get("reviewed_at_utc") or "—"),
        ("Reviewer",            item.get("reviewer") or "—"),
        ("Review notes",        item.get("review_notes") or "—"),
        ("Recommended action",  item.get("recommended_action", "")),
        ("Allowed next family", item.get("allowed_next_task_family") or "none"),
        ("Production patch?",   str(item.get("production_patch_allowed", False))),
    ]
    for label, value in fields:
        print(f"  {_BOLD}{label:<22}{_RESET} {value}")
    print()
    print(f"  Summary:\n    {item.get('summary', '(none)')}")
    print(f"{'=' * 60}\n")
    return 0


def cmd_approve(args: argparse.Namespace) -> int:
    result = approve_review(args.review_id, args.reviewer, args.notes or "")
    if result is None:
        print(f"Error: review_id '{args.review_id}' not found.", file=sys.stderr)
        return 1
    print(_color(f"✅ APPROVED: {args.review_id} by {args.reviewer}", _GREEN))
    print(f"   Allowed next task family: {result.get('allowed_next_task_family') or 'none'}")
    print(f"   production_patch_allowed = {result.get('production_patch_allowed', False)}")
    print("   (Planner will create follow-up validation/proposal task on next tick.)")
    return 0


def cmd_reject(args: argparse.Namespace) -> int:
    result = reject_review(args.review_id, args.reviewer, args.notes or "")
    if result is None:
        print(f"Error: review_id '{args.review_id}' not found.", file=sys.stderr)
        return 1
    print(_color(f"❌ REJECTED: {args.review_id} by {args.reviewer}", _RED))
    print("   No follow-up task will be created.")
    return 0


def cmd_more_data(args: argparse.Namespace) -> int:
    result = request_more_data(args.review_id, args.reviewer, args.notes or "")
    if result is None:
        print(f"Error: review_id '{args.review_id}' not found.", file=sys.stderr)
        return 1
    print(_color(f"🔄 MORE_DATA_REQUESTED: {args.review_id} by {args.reviewer}", _CYAN))
    print(f"   Allowed next task family: {result.get('allowed_next_task_family') or 'none'}")
    print("   (Planner will create data-collection task on next tick.)")
    return 0


# ── Argument parser ───────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="review_queue",
        description="Phase 24 Human Review Queue CLI",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="List all review items")

    p_show = sub.add_parser("show", help="Show detail of one review item")
    p_show.add_argument("review_id", help="Review ID (e.g. hrq_abc123)")

    for cmd_name, help_text in [
        ("approve",   "Approve a review item"),
        ("reject",    "Reject a review item"),
        ("more-data", "Request more data for a review item"),
    ]:
        p = sub.add_parser(cmd_name, help=help_text)
        p.add_argument("review_id", help="Review ID")
        p.add_argument("--reviewer", required=True, help="Reviewer name")
        p.add_argument("--notes", default="", help="Optional review notes")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "list":
        return cmd_list(args)
    elif args.command == "show":
        return cmd_show(args)
    elif args.command == "approve":
        return cmd_approve(args)
    elif args.command == "reject":
        return cmd_reject(args)
    elif args.command == "more-data":
        return cmd_more_data(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
