"""Lifecycle drift guard tests for Replay Lifecycle UI."""
from __future__ import annotations

import os
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import check_replay_lifecycle_drift as drift  # noqa: E402

DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"


def _resolve_db_path() -> Path:
    override = os.environ.get("LOTTERY_TEST_DB_PATH")
    if override:
        return Path(override)
    return DB_PATH


DB_PATH = _resolve_db_path()


@pytest.mark.requires_db
@pytest.mark.skipif(not DB_PATH.exists(), reason="Replay DB not found")
class TestReplayLifecycleDriftGuard:
    def test_drift_report_is_traceable(self):
        report = drift.collect_drift_report(DB_PATH)

        assert report["status"] in {"PASS", "BLOCKED"}
        if report["status"] == "PASS":
            assert report["unknown_strategy_ids"] == []
            assert report["missing_lifecycle_status_strategy_ids"] == []
        else:
            assert report["unknown_strategy_ids"]
        assert set(report["registry_by_lifecycle"]) <= set(drift.LIFECYCLE_STATUSES)
        assert set(report["replay_rows_by_lifecycle"]) <= set(drift.LIFECYCLE_STATUSES)

    def test_drift_report_json_serializes(self):
        report = drift.collect_drift_report(DB_PATH)
        encoded = json.dumps(report, ensure_ascii=False)
        decoded = json.loads(encoded)

        assert decoded["status"] in {"PASS", "BLOCKED"}
        assert decoded["traceable_row_count"] <= decoded["replay_row_count"]
        if decoded["status"] == "BLOCKED":
            assert decoded["unknown_strategy_ids"]

    def test_registry_statuses_remain_canonical(self):
        statuses = {entry["strategy_lifecycle_status"] for entry in drift.list_strategies()}
        assert statuses <= set(drift.LIFECYCLE_STATUSES)
