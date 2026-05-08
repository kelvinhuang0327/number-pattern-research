#!/usr/bin/env python3
"""
Run the replay governance dedicated DB validation path.

Hard requirements:
  - A readable DB fixture must exist before pytest starts.
  - DB-dependent tests must run (not silently skip).
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"

TEST_ARGS = [
    "tests/test_strategy_replay_history_cutoff_integrity.py",
    "tests/test_replay_freshness_cadence.py",
    "tests/test_replay_api_contract.py",
]


def _resolve_db_path(arg_db_path: str | None) -> Path:
    if arg_db_path:
        return Path(arg_db_path).expanduser().resolve()
    replay_env_path = os.environ.get("LOTTERY_REPLAY_DB_PATH")
    if replay_env_path:
        return Path(replay_env_path).expanduser().resolve()
    env_path = os.environ.get("LOTTERY_TEST_DB_PATH")
    if env_path:
        return Path(env_path).expanduser().resolve()
    return DEFAULT_DB_PATH


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run dedicated replay DB validation tests."
    )
    parser.add_argument(
        "--db-path",
        help=(
            "Path to replay SQLite DB fixture. "
            "If omitted, uses LOTTERY_REPLAY_DB_PATH, then LOTTERY_TEST_DB_PATH, "
            "then default project DB path."
        ),
    )
    args = parser.parse_args()

    db_path = _resolve_db_path(args.db_path)
    if not db_path.exists():
        print(
            "[replay-ci-db] ERROR: required DB fixture not found:",
            db_path,
            file=sys.stderr,
        )
        print(
            "[replay-ci-db] Refusing to run dedicated DB path without fixture.",
            file=sys.stderr,
        )
        return 2

    default_db_path = DEFAULT_DB_PATH
    created_symlink = False
    if db_path != default_db_path and not default_db_path.exists():
        default_db_path.parent.mkdir(parents=True, exist_ok=True)
        default_db_path.symlink_to(db_path)
        created_symlink = True

    env = os.environ.copy()
    env["LOTTERY_TEST_DB_PATH"] = str(db_path)
    env["LOTTERY_REPLAY_DB_PATH"] = str(db_path)
    cmd = [sys.executable, "-m", "pytest", *TEST_ARGS, "-m", "requires_db", "-q", "-rA"]
    print("[replay-ci-db] Running:")
    print(" ", " ".join(cmd))
    print("[replay-ci-db] LOTTERY_TEST_DB_PATH=", env["LOTTERY_TEST_DB_PATH"])

    try:
        completed = subprocess.run(
            cmd,
            cwd=REPO_ROOT,
            env=env,
            text=True,
            capture_output=True,
        )
    finally:
        if created_symlink and default_db_path.is_symlink():
            default_db_path.unlink()

    if completed.stdout:
        print(completed.stdout, end="")
    if completed.stderr:
        print(completed.stderr, end="", file=sys.stderr)
    if completed.returncode != 0:
        return completed.returncode

    summary = completed.stdout.splitlines()[-1] if completed.stdout else ""
    skipped_match = re.search(r"(\d+)\s+skipped", summary)
    skipped_count = int(skipped_match.group(1)) if skipped_match else 0
    if skipped_count > 0:
        print(
            "[replay-ci-db] ERROR: dedicated DB path still skipped "
            f"{skipped_count} requires_db tests.",
            file=sys.stderr,
        )
        return 3

    print("[replay-ci-db] Dedicated DB validation passed with zero skips.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
