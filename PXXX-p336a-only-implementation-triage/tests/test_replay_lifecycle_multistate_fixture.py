"""Multi-state synthetic catalog fixture coverage for Replay Lifecycle UI."""
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
EXPECTED_LIFECYCLE_STATUSES = {
    "ONLINE",
    "OFFLINE",
    "REJECTED",
    "OBSERVATION",
    "RETIRED",
}


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


def test_multistate_fixture_passes_drift_guard(tmp_path):
    db_path = tmp_path / "multistate_fixture.db"

    _run_script(
        str(BUILD_SCRIPT),
        "--fixture-mode",
        "multistate",
        "--output",
        str(db_path),
    )
    _run_script(str(VALIDATE_SCRIPT), "--db", str(db_path))

    report = _drift_report(db_path)

    assert report["status"] == "PASS"
    assert report["unknown_strategy_ids"] == []
    assert report["missing_lifecycle_status_strategy_ids"] == []
    assert set(report["replay_rows_by_lifecycle"]) == EXPECTED_LIFECYCLE_STATUSES
    assert all(report["replay_rows_by_lifecycle"][status] >= 1 for status in EXPECTED_LIFECYCLE_STATUSES)
    assert report["traceable_row_count"] == report["replay_row_count"] == 5
    assert len(report["traceable_strategy_ids"]) == 5
    assert set(report["fixture_catalog_strategy_ids"]) == {
        "catalog_online_biglotto_triple_strike",
        "catalog_offline_power_precision_3bet",
        "catalog_rejected_biglotto_deviation_2bet",
        "catalog_observation_daily539_f4cold",
        "catalog_retired_power_orthogonal_5bet",
    }
    assert set(report["fixture_catalog_by_lifecycle"]) == EXPECTED_LIFECYCLE_STATUSES


def test_mismatch_fixture_stays_blocked(tmp_path):
    db_path = tmp_path / "mismatch_fixture.db"

    _run_script(str(BUILD_SCRIPT), "--output", str(db_path))
    _run_script(str(VALIDATE_SCRIPT), "--db", str(db_path))

    report = _drift_report(db_path)

    assert report["status"] == "BLOCKED"
    assert report["unknown_strategy_ids"]
    assert report["traceable_row_count"] == 0
    assert report["replay_rows_by_lifecycle"] == {}
