"""Stale RUNNING task lock detection and safe auto-release."""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional, List

# Ensure orchestrator package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from orchestrator import db as _db

STALE_LOCK_RECOVERY_LOG = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "runtime", "agent_orchestrator", "stale_lock_recovery.jsonl",
)

_SETTING_DEFAULTS = {
    "stale_lock_recovery_enabled": "1",
    "stale_lock_max_running_minutes": "120",
    "stale_lock_light_worker_minutes": "30",
    "stale_lock_planner_minutes": "30",
    "stale_lock_release_without_pid_minutes": "240",
    "stale_lock_dry_run_default": "1",
}


@dataclass
class StaleLockPolicy:
    enabled: bool = True
    max_running_minutes: int = 120
    max_light_worker_minutes: int = 30
    max_planner_minutes: int = 30
    require_dead_pid_for_release: bool = True
    release_without_pid_after_minutes: int = 240
    dry_run_default: bool = True
    do_not_requeue: bool = True


@dataclass
class StaleLockDecision:
    task_id: int
    title: str
    status: str
    should_release: bool
    reason: str  # PROCESS_DEAD | LOCK_TIMEOUT_NO_PID | WARNING_LONG_RUNNING_ALIVE | NOT_STALE
    pid: Optional[int]
    pid_alive: Optional[bool]
    running_minutes: float
    started_at: Optional[str]
    policy_max_minutes: int


@dataclass
class StaleLockResult:
    dry_run: bool
    scanned: int
    would_release: int
    released: int
    warnings: List[dict] = field(default_factory=list)
    decisions: List[dict] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _open_db(db_path: Optional[str] = None) -> sqlite3.Connection:
    path = db_path or _db.DB_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _get_setting(settings: dict, key: str, default: str) -> str:
    return settings.get(key, _SETTING_DEFAULTS.get(key, default))


def _role_max_minutes(title: str, policy: StaleLockPolicy) -> int:
    t = (title or "").lower()
    if any(k in t for k in ("planner", "plan")):
        return policy.max_planner_minutes
    if any(k in t for k in ("light", "quick", "small")):
        return policy.max_light_worker_minutes
    return policy.max_running_minutes


def _write_audit(event: str, **extra) -> None:
    record = {"event": event, "timestamp": datetime.now(timezone.utc).isoformat(), **extra}
    try:
        os.makedirs(os.path.dirname(STALE_LOCK_RECOVERY_LOG), exist_ok=True)
        with open(STALE_LOCK_RECOVERY_LOG, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def is_pid_alive(pid: Optional[int]) -> bool:
    return _db._is_pid_alive(pid)


def load_stale_lock_policy(db_path: Optional[str] = None) -> StaleLockPolicy:
    """Load stale lock policy from orchestrator_settings, with defaults."""
    settings: dict = {}
    try:
        conn = _open_db(db_path)
        try:
            rows = conn.execute(
                "SELECT key, value FROM orchestrator_settings WHERE key LIKE 'stale_lock_%'"
            ).fetchall()
            settings = {r["key"]: r["value"] for r in rows}
        finally:
            conn.close()
    except Exception:
        pass

    def _bool(key: str, default: bool) -> bool:
        raw = settings.get(key, _SETTING_DEFAULTS.get(key, "1" if default else "0"))
        return str(raw).strip() not in ("0", "false", "False", "")

    def _int(key: str, default: int) -> int:
        raw = settings.get(key, _SETTING_DEFAULTS.get(key, str(default)))
        try:
            return int(raw)
        except (TypeError, ValueError):
            return default

    return StaleLockPolicy(
        enabled=_bool("stale_lock_recovery_enabled", True),
        max_running_minutes=_int("stale_lock_max_running_minutes", 120),
        max_light_worker_minutes=_int("stale_lock_light_worker_minutes", 30),
        max_planner_minutes=_int("stale_lock_planner_minutes", 30),
        release_without_pid_after_minutes=_int("stale_lock_release_without_pid_minutes", 240),
        dry_run_default=_bool("stale_lock_dry_run_default", True),
        require_dead_pid_for_release=True,
        do_not_requeue=True,
    )


def inspect_running_tasks(
    db_path: Optional[str] = None,
    now: Optional[datetime] = None,
    policy: Optional[StaleLockPolicy] = None,
) -> List[StaleLockDecision]:
    """Inspect all RUNNING agent_tasks and classify each one."""
    if policy is None:
        policy = load_stale_lock_policy(db_path)
    if now is None:
        now = datetime.now(timezone.utc)

    decisions: List[StaleLockDecision] = []

    if not policy.enabled:
        return decisions

    try:
        conn = _open_db(db_path)
        try:
            rows = conn.execute(
                "SELECT id, title, status, worker_pid, started_at FROM agent_tasks WHERE status = 'RUNNING'"
            ).fetchall()
            tasks = [dict(r) for r in rows]
        finally:
            conn.close()
    except Exception:
        return decisions

    for task in tasks:
        task_id = task["id"]
        title = task.get("title") or ""
        pid = task.get("worker_pid")
        started_at_str = task.get("started_at")

        # Calculate running_minutes
        running_minutes = 0.0
        if started_at_str:
            try:
                started_dt = datetime.fromisoformat(str(started_at_str).replace("Z", "+00:00"))
                if started_dt.tzinfo is None:
                    started_dt = started_dt.replace(tzinfo=timezone.utc)
                running_minutes = (now - started_dt).total_seconds() / 60.0
            except Exception:
                pass

        policy_max = _role_max_minutes(title, policy)
        pid_alive: Optional[bool] = None

        if pid:
            pid_alive = is_pid_alive(pid)
            if pid_alive:
                # Process is alive — check for long-running warning
                if running_minutes > policy_max:
                    decisions.append(StaleLockDecision(
                        task_id=task_id,
                        title=title,
                        status="RUNNING",
                        should_release=False,
                        reason="WARNING_LONG_RUNNING_ALIVE",
                        pid=pid,
                        pid_alive=True,
                        running_minutes=running_minutes,
                        started_at=started_at_str,
                        policy_max_minutes=policy_max,
                    ))
                else:
                    decisions.append(StaleLockDecision(
                        task_id=task_id,
                        title=title,
                        status="RUNNING",
                        should_release=False,
                        reason="NOT_STALE",
                        pid=pid,
                        pid_alive=True,
                        running_minutes=running_minutes,
                        started_at=started_at_str,
                        policy_max_minutes=policy_max,
                    ))
            else:
                # Dead process — always release
                decisions.append(StaleLockDecision(
                    task_id=task_id,
                    title=title,
                    status="RUNNING",
                    should_release=True,
                    reason="PROCESS_DEAD",
                    pid=pid,
                    pid_alive=False,
                    running_minutes=running_minutes,
                    started_at=started_at_str,
                    policy_max_minutes=policy_max,
                ))
        else:
            # No PID — release only after threshold
            threshold = policy.release_without_pid_after_minutes
            if running_minutes >= threshold:
                decisions.append(StaleLockDecision(
                    task_id=task_id,
                    title=title,
                    status="RUNNING",
                    should_release=True,
                    reason="LOCK_TIMEOUT_NO_PID",
                    pid=None,
                    pid_alive=None,
                    running_minutes=running_minutes,
                    started_at=started_at_str,
                    policy_max_minutes=policy_max,
                ))
            else:
                decisions.append(StaleLockDecision(
                    task_id=task_id,
                    title=title,
                    status="RUNNING",
                    should_release=False,
                    reason="NOT_STALE",
                    pid=None,
                    pid_alive=None,
                    running_minutes=running_minutes,
                    started_at=started_at_str,
                    policy_max_minutes=policy_max,
                ))

    return decisions


def release_stale_tasks(
    dry_run: bool = True,
    db_path: Optional[str] = None,
    now: Optional[datetime] = None,
) -> StaleLockResult:
    """Inspect RUNNING tasks and optionally release stale ones.

    When dry_run=True no DB changes are made.
    When dry_run=False:
      - Sets status='FAILED', failure_category=reason, completed_at=now
      - Deletes matching agent_locks rows
      - Appends audit JSONL events
    """
    policy = load_stale_lock_policy(db_path)
    if now is None:
        now = datetime.now(timezone.utc)

    decisions = inspect_running_tasks(db_path=db_path, now=now, policy=policy)

    to_release = [d for d in decisions if d.should_release]
    warnings = [asdict(d) for d in decisions if d.reason == "WARNING_LONG_RUNNING_ALIVE"]

    result = StaleLockResult(
        dry_run=dry_run,
        scanned=len(decisions),
        would_release=len(to_release),
        released=0,
        warnings=warnings,
        decisions=[asdict(d) for d in decisions],
    )

    _write_audit(
        "STALE_LOCK_SCAN",
        dry_run=dry_run,
        scanned=len(decisions),
        would_release=len(to_release),
    )

    if dry_run:
        return result

    # --- Write mode ---
    completed_at = now.isoformat()
    updated_at = completed_at
    for decision in to_release:
        try:
            conn = _open_db(db_path)
            try:
                conn.execute(
                    "UPDATE agent_tasks SET status=?, failure_category=?, completed_at=?, updated_at=? WHERE id=?",
                    ("FAILED", decision.reason, completed_at, updated_at, decision.task_id),
                )
                conn.execute(
                    "DELETE FROM agent_locks WHERE task_id = ?",
                    (decision.task_id,),
                )
                conn.commit()
            finally:
                conn.close()

            result.released += 1
            _write_audit(
                "STALE_LOCK_RELEASED",
                task_id=decision.task_id,
                title=decision.title,
                reason=decision.reason,
                pid=decision.pid,
                running_minutes=decision.running_minutes,
                dry_run=False,
            )
        except Exception as exc:
            _write_audit(
                "STALE_LOCK_RELEASE_ERROR",
                task_id=decision.task_id,
                reason=decision.reason,
                error=str(exc),
                dry_run=False,
            )

    return result


def run_startup_stale_lock_check(
    dry_run: Optional[bool] = None,
    db_path: Optional[str] = None,
) -> StaleLockResult:
    """Hook called at orchestrator startup.

    Reads stale_lock_startup_check_enabled (default 1) and
    stale_lock_startup_write_enabled (default 0).
    Always defaults to dry_run unless startup_write_enabled=1.
    """
    # Load raw settings
    raw_settings: dict = {}
    try:
        conn = _open_db(db_path)
        try:
            rows = conn.execute(
                "SELECT key, value FROM orchestrator_settings WHERE key LIKE 'stale_lock_%'"
            ).fetchall()
            raw_settings = {r["key"]: r["value"] for r in rows}
        finally:
            conn.close()
    except Exception:
        pass

    check_enabled = str(raw_settings.get("stale_lock_startup_check_enabled", "1")).strip() not in ("0", "false", "False")
    if not check_enabled:
        return StaleLockResult(dry_run=True, scanned=0, would_release=0, released=0)

    if dry_run is None:
        write_enabled = str(raw_settings.get("stale_lock_startup_write_enabled", "0")).strip() not in ("0", "false", "False")
        dry_run = not write_enabled

    return release_stale_tasks(dry_run=dry_run, db_path=db_path)
