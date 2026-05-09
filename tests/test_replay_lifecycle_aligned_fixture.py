"""Registry-aligned and mismatch fixture coverage for Replay Lifecycle UI."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import check_replay_lifecycle_drift as drift  # noqa: E402

PYTHON = sys.executable
BUILD_SCRIPT = SCRIPTS_DIR / "build_replay_test_fixture.py"
VALIDATE_SCRIPT = SCRIPTS_DIR / "validate_replay_test_fixture.py"
DRIFT_SCRIPT = SCRIPTS_DIR / "check_replay_lifecycle_drift.py"


def _run_script(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [PYTHON, *args],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )


def _drift_report(db_path: Path) -> dict:
    result = subprocess.run(
        [PYTHON, str(DRIFT_SCRIPT), "--db-path", str(db_path)],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_aligned_fixture_passes_drift_guard(tmp_path):
    db_path = tmp_path / "aligned_fixture.db"

    _run_script(str(BUILD_SCRIPT), "--fixture-mode", "aligned", "--output", str(db_path))
    _run_script(str(VALIDATE_SCRIPT), "--db", str(db_path))

    report = _drift_report(db_path)

    assert report["status"] == "PASS"
    assert report["unknown_strategy_ids"] == []
    assert report["missing_lifecycle_status_strategy_ids"] == []
    assert report["traceable_row_count"] == report["replay_row_count"] == 3
    assert report["replay_rows_by_lifecycle"] == {"ONLINE": 3}
    assert report["traceable_strategy_ids"]
    assert set(report["traceable_strategy_ids"]) <= {entry["strategy_id"] for entry in drift.list_strategies()}


def test_mismatch_fixture_remains_blocked(tmp_path):
    db_path = tmp_path / "mismatch_fixture.db"

    _run_script(str(BUILD_SCRIPT), "--output", str(db_path))
    _run_script(str(VALIDATE_SCRIPT), "--db", str(db_path))

    report = _drift_report(db_path)

    assert report["status"] == "BLOCKED"
    assert report["unknown_strategy_ids"]
    assert report["traceable_row_count"] == 0
    assert report["replay_rows_by_lifecycle"] == {}
