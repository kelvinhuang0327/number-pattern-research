#!/usr/bin/env python3
"""
Run the replay governance default validation suite.

This path is CI-safe when replay DB is absent:
requires_db tests are allowed to skip via existing guard.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

TEST_ARGS = [
    "tests/test_randomness_audit.py",
    "tests/test_randomness_audit_cadence.py",
    "tests/test_strategy_replay_history_cutoff_integrity.py",
    "tests/test_replay_browser_smoke.py",
    "tests/test_replay_api_contract.py",
    "tests/test_replay_freshness_cadence.py",
]


def main() -> int:
    cmd = [sys.executable, "-m", "pytest", *TEST_ARGS, "-q"]
    print("[replay-ci-default] Running:")
    print(" ", " ".join(cmd))
    completed = subprocess.run(cmd, cwd=REPO_ROOT)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
