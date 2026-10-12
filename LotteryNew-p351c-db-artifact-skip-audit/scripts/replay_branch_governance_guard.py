#!/usr/bin/env python3
"""
replay_branch_governance_guard.py
====================================
P13.5 Branch Governance Guard — read-only audit only.

Allowed git sub-commands (read-only):
  rev-parse, status, branch --list, diff --cached --name-only, log.

This script contains NO write-capable or destructive git operations.
All subprocess calls use explicit list-form arguments to avoid any
accidental string matching for forbidden operations.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH      = PROJECT_ROOT / "lottery_api" / "data" / "lottery_v2.db"


# ── safe git helpers (read-only only) ─────────────────────────────────────────

def _git(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git"] + args,
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
    )


def _git_out(args: list[str]) -> str:
    return _git(args).stdout.strip()


def current_branch() -> str:
    """git rev-parse --abbrev-ref HEAD"""
    return _git_out(["rev-parse", "--abbrev-ref", "HEAD"])


def staged_files() -> list[str]:
    """git diff --cached --name-only — returns list of staged file paths."""
    raw = _git_out(["diff", "--cached", "--name-only"])
    if not raw:
        return []
    return [line.strip() for line in raw.splitlines() if line.strip()]


def ahead_behind(base: str) -> tuple[int, int]:
    """How many commits HEAD is ahead/behind a reference branch."""
    result = _git(["rev-list", "--count", "--left-right", f"{base}...HEAD"])
    parts = result.stdout.strip().split()
    if len(parts) == 2:
        behind, ahead = int(parts[0]), int(parts[1])
    else:
        behind, ahead = -1, -1
    return ahead, behind


def db_row_count(db_path: Path, table: str = "strategy_prediction_replays") -> int:
    conn = sqlite3.connect(str(db_path))
    count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]  # noqa: S608
    conn.close()
    return count


# ── staged-file classifiers ───────────────────────────────────────────────────

def classify_staged(staged: list[str]) -> tuple[list[str], list[str], list[str]]:
    db_files  = [f for f in staged if f.endswith(".db") or "lottery_v2" in f]
    bak_files = [f for f in staged if f.startswith("backup") or f.startswith("backups")]
    pid_rt    = [
        f for f in staged
        if f.endswith(".pid") or f.startswith("runtime/") or "/runtime/" in f
    ]
    return db_files, bak_files, pid_rt


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="P13.5 Branch Governance Guard — read-only"
    )
    parser.add_argument("--expected-branch", required=True,
                        help="Expected current branch name")
    parser.add_argument("--expected-rows", type=int, default=460,
                        help="Expected production DB row count")
    parser.add_argument("--json-out", required=True,
                        help="Output JSON file path")
    args = parser.parse_args()

    cur_branch = current_branch()
    branch_ok  = cur_branch == args.expected_branch

    prod_rows = db_row_count(DB_PATH)
    rows_ok   = prod_rows == args.expected_rows

    staged = staged_files()
    db_files, bak_files, pid_rt = classify_staged(staged)

    staged_danger = bool(db_files or bak_files)

    if branch_ok and rows_ok and not staged_danger:
        classification = "BRANCH_GOVERNANCE_PASS"
    elif not branch_ok:
        classification = "BRANCH_GOVERNANCE_FAIL_WRONG_BRANCH"
    elif not rows_ok:
        classification = "BRANCH_GOVERNANCE_FAIL_ROW_COUNT"
    elif staged_danger:
        classification = "BRANCH_GOVERNANCE_FAIL_STAGED_DANGER"
    else:
        classification = "BRANCH_GOVERNANCE_FAIL_UNKNOWN"

    output: dict = {
        "phase":                          "P13_5_BRANCH_GOVERNANCE_LOCK",
        "canonical_repo":                 str(PROJECT_ROOT),
        "active_branch_after_consolidation": "main",
        "merged_namespace":               "merged/",
        "current_branch":                 cur_branch,
        "expected_branch":                args.expected_branch,
        "branch_ok":                      branch_ok,
        "production_rows":                prod_rows,
        "expected_rows":                  args.expected_rows,
        "rows_ok":                        rows_ok,
        "new_branch_allowed":             False,
        "new_worktree_allowed":           False,
        "checkout_allowed":               False,
        "requires_explicit_authorization": "YES create new branch for <reason>",
        "staged_db_files":                db_files,
        "staged_backup_files":            bak_files,
        "staged_pid_runtime_files":       pid_rt,
        "staged_danger":                  staged_danger,
        "generated_at":                   datetime.now(timezone.utc).isoformat(),
        "classification":                 classification,
    }

    out_path = Path(args.json_out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)

    if classification == "BRANCH_GOVERNANCE_PASS":
        print(f"BRANCH_GOVERNANCE_PASS — branch={cur_branch!r} rows={prod_rows}")
        sys.exit(0)
    else:
        print(
            f"BRANCH_GOVERNANCE_FAIL — {classification}\n"
            f"  current_branch={cur_branch!r}  expected={args.expected_branch!r}\n"
            f"  production_rows={prod_rows}  expected={args.expected_rows}",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
