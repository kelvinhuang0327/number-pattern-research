#!/usr/bin/env python3
"""
Stale RUNNING lock recovery CLI.

Usage:
  python3 scripts/recover_stale_locks.py --dry-run [--json] [--db PATH] [--task-id ID]
  python3 scripts/recover_stale_locks.py --write --confirm-release [--json] [--db PATH]

Rules:
  --write requires --confirm-release (error if not both present)
  Default mode is dry-run.
  No external LLM calls. No Planner/Worker trigger. No row deletion.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict

# Allow importing orchestrator package from repo root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from orchestrator.stale_lock_recovery import (
    load_stale_lock_policy,
    inspect_running_tasks,
    release_stale_tasks,
    StaleLockResult,
)


def _print_table(result: StaleLockResult) -> None:
    decisions = result.decisions
    print(f"\n{'─'*72}")
    print(f" Stale Lock Recovery  |  dry_run={result.dry_run}  |  scanned={result.scanned}  |  would_release={result.would_release}  |  released={result.released}")
    print(f"{'─'*72}")
    if not decisions:
        print("  (no RUNNING tasks found)")
    else:
        fmt = "  {:<6}  {:<30}  {:<8}  {:<30}  {}"
        print(fmt.format("ID", "Title", "PID", "Reason", "RunMin"))
        print("  " + "─" * 68)
        for d in decisions:
            title = (d.get("title") or "")[:28]
            pid = str(d.get("pid") or "—")
            reason = d.get("reason", "")
            run_min = f"{d.get('running_minutes', 0):.1f}"
            should = "✓RELEASE" if d.get("should_release") else ""
            print(fmt.format(d.get("task_id", "?"), title, pid, reason, f"{run_min}m {should}"))
    print(f"{'─'*72}\n")

    if result.warnings:
        print(f"  WARNINGS ({len(result.warnings)} alive-but-long-running tasks):")
        for w in result.warnings:
            print(f"    task_id={w.get('task_id')} title={w.get('title')!r} running={w.get('running_minutes', 0):.1f}m")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Recover stale RUNNING task locks in the orchestrator DB."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", default=True, help="Inspect only, no DB changes (default)")
    mode.add_argument("--write", action="store_true", help="Apply changes to DB (requires --confirm-release)")
    parser.add_argument("--confirm-release", action="store_true", help="Required safety flag for --write mode")
    parser.add_argument("--json", action="store_true", dest="json_output", help="Output JSON to stdout")
    parser.add_argument("--db", dest="db_path", default=None, help="Override DB path")
    parser.add_argument("--task-id", type=int, default=None, help="Inspect a specific task only")
    args = parser.parse_args()

    # Safety check
    if args.write and not args.confirm_release:
        print("ERROR: --write requires --confirm-release flag.", file=sys.stderr)
        sys.exit(1)

    dry_run = not args.write

    if args.task_id:
        # Single-task inspection (always dry-run for filtering)
        policy = load_stale_lock_policy(args.db_path)
        decisions = inspect_running_tasks(db_path=args.db_path, policy=policy)
        decisions = [d for d in decisions if d.task_id == args.task_id]
        from dataclasses import asdict as _asdict
        result = StaleLockResult(
            dry_run=True,
            scanned=len(decisions),
            would_release=sum(1 for d in decisions if d.should_release),
            released=0,
            warnings=[_asdict(d) for d in decisions if d.reason == "WARNING_LONG_RUNNING_ALIVE"],
            decisions=[_asdict(d) for d in decisions],
        )
    else:
        result = release_stale_tasks(dry_run=dry_run, db_path=args.db_path)

    if args.json_output:
        print(json.dumps(asdict(result), indent=2))
    else:
        _print_table(result)
        if not dry_run and result.released > 0:
            print(f"  Released {result.released} stale task(s). Audit log: stale_lock_recovery.jsonl")
        elif not dry_run:
            print("  No stale tasks to release.")


if __name__ == "__main__":
    main()
