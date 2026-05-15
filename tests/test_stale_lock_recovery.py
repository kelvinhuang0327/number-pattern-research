"""
Tests for stale RUNNING task lock detection and safe auto-release.

Covers 20 core cases from the spec.
"""
from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
from dataclasses import asdict
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from orchestrator.stale_lock_recovery import (
    StaleLockDecision,
    StaleLockPolicy,
    StaleLockResult,
    inspect_running_tasks,
    load_stale_lock_policy,
    release_stale_tasks,
    run_startup_stale_lock_check,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_db(tmp_path_str: str) -> str:
    """Create a minimal orchestrator DB with required tables."""
    db_path = os.path.join(tmp_path_str, "test_orchestrator.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS agent_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            status TEXT DEFAULT 'QUEUED',
            worker_pid INTEGER,
            started_at TEXT,
            completed_at TEXT,
            failure_category TEXT,
            updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS agent_locks (
            runner TEXT PRIMARY KEY,
            pid INTEGER,
            task_id INTEGER,
            started_at TEXT,
            heartbeat_at TEXT,
            lock_type TEXT DEFAULT 'research'
        );
        CREATE TABLE IF NOT EXISTS orchestrator_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
    """)
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def tmp_db(tmp_path):
    return _make_db(str(tmp_path))


def _insert_task(db_path: str, title: str = "test task", status: str = "RUNNING",
                 worker_pid=None, started_offset_minutes: float = 10.0) -> int:
    """Insert a task and return its id."""
    now = datetime.now(timezone.utc)
    started_at = (now - timedelta(minutes=started_offset_minutes)).isoformat()
    conn = sqlite3.connect(db_path)
    cur = conn.execute(
        "INSERT INTO agent_tasks (title, status, worker_pid, started_at) VALUES (?, ?, ?, ?)",
        (title, status, worker_pid, started_at),
    )
    task_id = cur.lastrowid
    conn.commit()
    conn.close()
    return task_id


def _insert_lock(db_path: str, task_id: int, pid: int, runner: str = "worker") -> None:
    conn = sqlite3.connect(db_path)
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT OR REPLACE INTO agent_locks (runner, pid, task_id, started_at, heartbeat_at) VALUES (?, ?, ?, ?, ?)",
        (runner, pid, task_id, now, now),
    )
    conn.commit()
    conn.close()


def _get_task(db_path: str, task_id: int) -> dict:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM agent_tasks WHERE id = ?", (task_id,)).fetchone()
    conn.close()
    return dict(row) if row else {}


def _insert_setting(db_path: str, key: str, value: str) -> None:
    conn = sqlite3.connect(db_path)
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT OR REPLACE INTO orchestrator_settings (key, value, updated_at) VALUES (?, ?, ?)",
        (key, value, now),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Case 1: No RUNNING tasks → scanned=0, released=0
# ---------------------------------------------------------------------------

class TestNoRunningTasks:
    def test_no_running_tasks(self, tmp_db):
        _insert_task(tmp_db, status="COMPLETED")
        _insert_task(tmp_db, status="QUEUED")
        result = release_stale_tasks(dry_run=True, db_path=tmp_db)
        assert result.scanned == 0
        assert result.released == 0
        assert result.would_release == 0
        assert result.decisions == []


# ---------------------------------------------------------------------------
# Case 2: RUNNING task with alive PID → NOT_STALE, not released
# ---------------------------------------------------------------------------

class TestAliveProcess:
    def test_alive_pid_not_released(self, tmp_db):
        task_id = _insert_task(tmp_db, worker_pid=99999, started_offset_minutes=5)
        with patch("orchestrator.stale_lock_recovery.is_pid_alive", return_value=True):
            result = release_stale_tasks(dry_run=True, db_path=tmp_db)
        assert result.scanned == 1
        assert result.would_release == 0
        d = result.decisions[0]
        assert d["reason"] == "NOT_STALE"
        assert d["should_release"] is False
        assert d["pid_alive"] is True

    def test_alive_pid_not_modified_in_db(self, tmp_db):
        task_id = _insert_task(tmp_db, worker_pid=99999, started_offset_minutes=5)
        with patch("orchestrator.stale_lock_recovery.is_pid_alive", return_value=True):
            release_stale_tasks(dry_run=False, db_path=tmp_db)
        task = _get_task(tmp_db, task_id)
        assert task["status"] == "RUNNING"


# ---------------------------------------------------------------------------
# Case 3: RUNNING task with dead PID → PROCESS_DEAD, would release in dry-run
# ---------------------------------------------------------------------------

class TestDeadProcess:
    def test_dead_pid_flagged_for_release(self, tmp_db):
        _insert_task(tmp_db, worker_pid=99999, started_offset_minutes=5)
        with patch("orchestrator.stale_lock_recovery.is_pid_alive", return_value=False):
            result = release_stale_tasks(dry_run=True, db_path=tmp_db)
        assert result.scanned == 1
        assert result.would_release == 1
        d = result.decisions[0]
        assert d["reason"] == "PROCESS_DEAD"
        assert d["should_release"] is True
        assert d["pid_alive"] is False


# ---------------------------------------------------------------------------
# Case 4: dry-run does NOT modify DB
# ---------------------------------------------------------------------------

class TestDryRunNoModification:
    def test_dry_run_no_db_change(self, tmp_db):
        task_id = _insert_task(tmp_db, worker_pid=99999, started_offset_minutes=5)
        with patch("orchestrator.stale_lock_recovery.is_pid_alive", return_value=False):
            result = release_stale_tasks(dry_run=True, db_path=tmp_db)
        assert result.dry_run is True
        assert result.released == 0
        task = _get_task(tmp_db, task_id)
        assert task["status"] == "RUNNING"
        assert task["failure_category"] is None
        assert task["completed_at"] is None


# ---------------------------------------------------------------------------
# Case 5: write mode with dead PID → releases task correctly
# ---------------------------------------------------------------------------

class TestWriteModeDead:
    def test_write_releases_task(self, tmp_db):
        task_id = _insert_task(tmp_db, worker_pid=99999, started_offset_minutes=10)
        _insert_lock(tmp_db, task_id, 99999)
        with patch("orchestrator.stale_lock_recovery.is_pid_alive", return_value=False):
            result = release_stale_tasks(dry_run=False, db_path=tmp_db)
        assert result.released == 1
        task = _get_task(tmp_db, task_id)
        assert task["status"] == "FAILED"

    def test_write_sets_failure_category(self, tmp_db):
        task_id = _insert_task(tmp_db, worker_pid=99999, started_offset_minutes=10)
        with patch("orchestrator.stale_lock_recovery.is_pid_alive", return_value=False):
            release_stale_tasks(dry_run=False, db_path=tmp_db)
        task = _get_task(tmp_db, task_id)
        assert task["failure_category"] == "PROCESS_DEAD"

    def test_write_sets_completed_at(self, tmp_db):
        task_id = _insert_task(tmp_db, worker_pid=99999, started_offset_minutes=10)
        with patch("orchestrator.stale_lock_recovery.is_pid_alive", return_value=False):
            release_stale_tasks(dry_run=False, db_path=tmp_db)
        task = _get_task(tmp_db, task_id)
        assert task["completed_at"] is not None


# ---------------------------------------------------------------------------
# Case 6: No PID, below threshold → NOT_STALE
# ---------------------------------------------------------------------------

class TestNoPidBelowThreshold:
    def test_no_pid_below_threshold_not_released(self, tmp_db):
        _insert_task(tmp_db, worker_pid=None, started_offset_minutes=10)
        # threshold defaults to 240 minutes
        result = release_stale_tasks(dry_run=True, db_path=tmp_db)
        assert result.would_release == 0
        d = result.decisions[0]
        assert d["reason"] == "NOT_STALE"
        assert d["should_release"] is False
        assert d["pid"] is None


# ---------------------------------------------------------------------------
# Case 7: No PID, beyond threshold → LOCK_TIMEOUT_NO_PID
# ---------------------------------------------------------------------------

class TestNoPidBeyondThreshold:
    def test_no_pid_beyond_threshold_released(self, tmp_db):
        _insert_task(tmp_db, worker_pid=None, started_offset_minutes=241)
        result = release_stale_tasks(dry_run=True, db_path=tmp_db)
        assert result.would_release == 1
        d = result.decisions[0]
        assert d["reason"] == "LOCK_TIMEOUT_NO_PID"
        assert d["should_release"] is True


# ---------------------------------------------------------------------------
# Case 8: COMPLETED task never modified
# ---------------------------------------------------------------------------

class TestCompletedTaskUntouched:
    def test_completed_task_not_scanned(self, tmp_db):
        task_id = _insert_task(tmp_db, status="COMPLETED", worker_pid=99999)
        result = release_stale_tasks(dry_run=False, db_path=tmp_db)
        assert result.scanned == 0
        task = _get_task(tmp_db, task_id)
        assert task["status"] == "COMPLETED"


# ---------------------------------------------------------------------------
# Case 9: QUEUED task never modified
# ---------------------------------------------------------------------------

class TestQueuedTaskUntouched:
    def test_queued_task_not_scanned(self, tmp_db):
        task_id = _insert_task(tmp_db, status="QUEUED", worker_pid=None)
        result = release_stale_tasks(dry_run=False, db_path=tmp_db)
        assert result.scanned == 0
        task = _get_task(tmp_db, task_id)
        assert task["status"] == "QUEUED"


# ---------------------------------------------------------------------------
# Case 10: release does not requeue
# ---------------------------------------------------------------------------

class TestNoRequeue:
    def test_released_task_not_requeued(self, tmp_db):
        task_id = _insert_task(tmp_db, worker_pid=99999, started_offset_minutes=10)
        with patch("orchestrator.stale_lock_recovery.is_pid_alive", return_value=False):
            release_stale_tasks(dry_run=False, db_path=tmp_db)
        task = _get_task(tmp_db, task_id)
        assert task["status"] != "QUEUED"
        assert task["status"] == "FAILED"

    def test_policy_do_not_requeue(self):
        policy = StaleLockPolicy()
        assert policy.do_not_requeue is True


# ---------------------------------------------------------------------------
# Case 11: failure_category set correctly
# ---------------------------------------------------------------------------

class TestFailureCategoryValues:
    def test_process_dead_category(self, tmp_db):
        task_id = _insert_task(tmp_db, worker_pid=99999)
        with patch("orchestrator.stale_lock_recovery.is_pid_alive", return_value=False):
            release_stale_tasks(dry_run=False, db_path=tmp_db)
        assert _get_task(tmp_db, task_id)["failure_category"] == "PROCESS_DEAD"

    def test_timeout_no_pid_category(self, tmp_db):
        task_id = _insert_task(tmp_db, worker_pid=None, started_offset_minutes=241)
        release_stale_tasks(dry_run=False, db_path=tmp_db)
        assert _get_task(tmp_db, task_id)["failure_category"] == "LOCK_TIMEOUT_NO_PID"


# ---------------------------------------------------------------------------
# Case 12: completed_at set on release
# ---------------------------------------------------------------------------

class TestCompletedAtOnRelease:
    def test_completed_at_set_process_dead(self, tmp_db):
        task_id = _insert_task(tmp_db, worker_pid=99999)
        with patch("orchestrator.stale_lock_recovery.is_pid_alive", return_value=False):
            release_stale_tasks(dry_run=False, db_path=tmp_db)
        task = _get_task(tmp_db, task_id)
        assert task["completed_at"] is not None

    def test_completed_at_set_no_pid_timeout(self, tmp_db):
        task_id = _insert_task(tmp_db, worker_pid=None, started_offset_minutes=241)
        release_stale_tasks(dry_run=False, db_path=tmp_db)
        task = _get_task(tmp_db, task_id)
        assert task["completed_at"] is not None


# ---------------------------------------------------------------------------
# Case 13: policy loads from DB settings
# ---------------------------------------------------------------------------

class TestPolicyLoading:
    def test_loads_from_db(self, tmp_db):
        _insert_setting(tmp_db, "stale_lock_max_running_minutes", "60")
        _insert_setting(tmp_db, "stale_lock_planner_minutes", "15")
        _insert_setting(tmp_db, "stale_lock_recovery_enabled", "1")
        policy = load_stale_lock_policy(tmp_db)
        assert policy.max_running_minutes == 60
        assert policy.max_planner_minutes == 15
        assert policy.enabled is True

    def test_defaults_when_no_settings(self, tmp_db):
        policy = load_stale_lock_policy(tmp_db)
        assert policy.max_running_minutes == 120
        assert policy.max_light_worker_minutes == 30
        assert policy.release_without_pid_after_minutes == 240

    def test_disabled_setting(self, tmp_db):
        _insert_setting(tmp_db, "stale_lock_recovery_enabled", "0")
        policy = load_stale_lock_policy(tmp_db)
        assert policy.enabled is False

    def test_disabled_returns_empty(self, tmp_db):
        _insert_setting(tmp_db, "stale_lock_recovery_enabled", "0")
        _insert_task(tmp_db, worker_pid=None, started_offset_minutes=300)
        result = release_stale_tasks(dry_run=True, db_path=tmp_db)
        assert result.scanned == 0


# ---------------------------------------------------------------------------
# Case 14: startup check defaults to dry_run=True
# ---------------------------------------------------------------------------

class TestStartupCheck:
    def test_startup_dry_run_default(self, tmp_db):
        _insert_task(tmp_db, worker_pid=99999)
        with patch("orchestrator.stale_lock_recovery.is_pid_alive", return_value=False):
            result = run_startup_stale_lock_check(db_path=tmp_db)
        assert result.dry_run is True
        assert result.released == 0

    def test_startup_disabled_when_setting_zero(self, tmp_db):
        _insert_setting(tmp_db, "stale_lock_startup_check_enabled", "0")
        _insert_task(tmp_db, worker_pid=99999)
        with patch("orchestrator.stale_lock_recovery.is_pid_alive", return_value=False):
            result = run_startup_stale_lock_check(db_path=tmp_db)
        assert result.scanned == 0

    def test_startup_write_when_enabled(self, tmp_db):
        _insert_setting(tmp_db, "stale_lock_startup_check_enabled", "1")
        _insert_setting(tmp_db, "stale_lock_startup_write_enabled", "1")
        task_id = _insert_task(tmp_db, worker_pid=99999)
        with patch("orchestrator.stale_lock_recovery.is_pid_alive", return_value=False):
            result = run_startup_stale_lock_check(db_path=tmp_db)
        assert result.dry_run is False
        assert result.released == 1
        assert _get_task(tmp_db, task_id)["status"] == "FAILED"


# ---------------------------------------------------------------------------
# Case 15: API endpoint returns correct summary
# ---------------------------------------------------------------------------

class TestApiEndpoint:
    def test_stale_locks_status_structure(self, tmp_db):
        """Simulate the endpoint logic without HTTP."""
        import dataclasses
        from orchestrator.stale_lock_recovery import load_stale_lock_policy, inspect_running_tasks

        _insert_task(tmp_db, worker_pid=99999, started_offset_minutes=5)
        with patch("orchestrator.stale_lock_recovery.is_pid_alive", return_value=True):
            policy = load_stale_lock_policy(tmp_db)
            decisions = inspect_running_tasks(db_path=tmp_db)

        would_release = sum(1 for d in decisions if d.should_release)
        warnings = sum(1 for d in decisions if d.reason == "WARNING_LONG_RUNNING_ALIVE")

        response = {
            "enabled": policy.enabled,
            "dry_run_default": policy.dry_run_default,
            "policy": dataclasses.asdict(policy),
            "summary": {
                "running_count": len(decisions),
                "would_release": would_release,
                "warnings": warnings,
            },
            "decisions": [dataclasses.asdict(d) for d in decisions],
        }

        assert "enabled" in response
        assert "policy" in response
        assert "summary" in response
        assert "decisions" in response
        assert isinstance(response["summary"]["running_count"], int)
        assert isinstance(response["summary"]["would_release"], int)
        assert isinstance(response["decisions"], list)

    def test_api_summary_would_release(self, tmp_db):
        import dataclasses
        from orchestrator.stale_lock_recovery import load_stale_lock_policy, inspect_running_tasks

        _insert_task(tmp_db, worker_pid=99999)
        with patch("orchestrator.stale_lock_recovery.is_pid_alive", return_value=False):
            decisions = inspect_running_tasks(db_path=tmp_db)

        would_release = sum(1 for d in decisions if d.should_release)
        assert would_release == 1


# ---------------------------------------------------------------------------
# Case 16: UI DOM IDs referenced
# ---------------------------------------------------------------------------

class TestUiDomIds:
    """Verify that the expected DOM element IDs exist in OrchestrationManager.js."""

    def _read_ui_file(self) -> str:
        path = os.path.join(REPO_ROOT, "src", "ui", "OrchestrationManager.js")
        with open(path, encoding="utf-8") as f:
            return f.read()

    def test_stale_lock_status_id_present(self):
        content = self._read_ui_file()
        assert "orc-stale-lock-status" in content

    def test_stale_lock_summary_id_present(self):
        content = self._read_ui_file()
        assert "orc-stale-lock-summary" in content

    def test_stale_lock_decisions_id_present(self):
        content = self._read_ui_file()
        assert "orc-stale-lock-decisions" in content

    def test_load_stale_lock_method_present(self):
        content = self._read_ui_file()
        assert "_loadStaleLockStatus" in content


# ---------------------------------------------------------------------------
# Extra coverage: role-based max minutes
# ---------------------------------------------------------------------------

class TestRoleBasedMaxMinutes:
    def test_planner_title_uses_planner_minutes(self, tmp_db):
        _insert_setting(tmp_db, "stale_lock_planner_minutes", "15")
        _insert_task(tmp_db, title="run planner task", worker_pid=None, started_offset_minutes=5)
        policy = load_stale_lock_policy(tmp_db)
        decisions = inspect_running_tasks(db_path=tmp_db, policy=policy)
        assert decisions[0].policy_max_minutes == 15

    def test_light_title_uses_light_minutes(self, tmp_db):
        _insert_setting(tmp_db, "stale_lock_light_worker_minutes", "20")
        _insert_task(tmp_db, title="light worker process", worker_pid=None, started_offset_minutes=5)
        policy = load_stale_lock_policy(tmp_db)
        decisions = inspect_running_tasks(db_path=tmp_db, policy=policy)
        assert decisions[0].policy_max_minutes == 20

    def test_generic_title_uses_default(self, tmp_db):
        _insert_task(tmp_db, title="research new strategy", worker_pid=None, started_offset_minutes=5)
        policy = load_stale_lock_policy(tmp_db)
        decisions = inspect_running_tasks(db_path=tmp_db, policy=policy)
        assert decisions[0].policy_max_minutes == policy.max_running_minutes


# ---------------------------------------------------------------------------
# Warning: alive but long-running
# ---------------------------------------------------------------------------

class TestWarningLongRunningAlive:
    def test_alive_over_max_produces_warning(self, tmp_db):
        _insert_setting(tmp_db, "stale_lock_max_running_minutes", "5")
        _insert_task(tmp_db, worker_pid=99999, started_offset_minutes=10)
        with patch("orchestrator.stale_lock_recovery.is_pid_alive", return_value=True):
            result = release_stale_tasks(dry_run=True, db_path=tmp_db)
        assert len(result.warnings) == 1
        assert result.warnings[0]["reason"] == "WARNING_LONG_RUNNING_ALIVE"
        assert result.would_release == 0  # alive, do not release

    def test_warning_not_released_in_write_mode(self, tmp_db):
        _insert_setting(tmp_db, "stale_lock_max_running_minutes", "5")
        task_id = _insert_task(tmp_db, worker_pid=99999, started_offset_minutes=10)
        with patch("orchestrator.stale_lock_recovery.is_pid_alive", return_value=True):
            result = release_stale_tasks(dry_run=False, db_path=tmp_db)
        assert result.released == 0
        assert _get_task(tmp_db, task_id)["status"] == "RUNNING"


# ---------------------------------------------------------------------------
# Lock row deleted on release
# ---------------------------------------------------------------------------

class TestLockDeleted:
    def test_lock_row_removed_after_release(self, tmp_db):
        task_id = _insert_task(tmp_db, worker_pid=99999)
        _insert_lock(tmp_db, task_id, 99999, runner="worker")
        with patch("orchestrator.stale_lock_recovery.is_pid_alive", return_value=False):
            release_stale_tasks(dry_run=False, db_path=tmp_db)
        conn = sqlite3.connect(tmp_db)
        lock = conn.execute("SELECT * FROM agent_locks WHERE task_id = ?", (task_id,)).fetchone()
        conn.close()
        assert lock is None


# ---------------------------------------------------------------------------
# StaleLockResult structure
# ---------------------------------------------------------------------------

class TestResultStructure:
    def test_result_is_dataclass(self):
        r = StaleLockResult(dry_run=True, scanned=0, would_release=0, released=0)
        d = asdict(r)
        assert "dry_run" in d
        assert "scanned" in d
        assert "would_release" in d
        assert "released" in d
        assert "warnings" in d
        assert "decisions" in d
