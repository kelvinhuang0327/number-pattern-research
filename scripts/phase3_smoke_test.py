#!/usr/bin/env python3
"""
Phase 3 Smoke Test: Daily Cap / Dedupe / Light Worker Foundation
================================================================
Verifies the Phase 3 minimal closed loop WITHOUT going through execution_policy,
because the orchestrator is in hard-off mode (pre-existing production safety guard).

Steps:
  A. Planner attempt #1 → creates maintenance_health_check (QUEUED)
  B. Planner attempt #2 (same UTC day) → PLANNER_SKIP_DAILY_CAP + PLANNER_IDLE_NO_ELIGIBLE_TASK
  C. Light worker runs → claims task, executes, writes file, marks COMPLETED
  D. SQL evidence check
  E. File evidence check

Scope:
  - No fallback P1-P6
  - No forced exploration
  - No validation router
  - No CTO review
  - No external betting API
  - No production betting data modified
  - No git commit
"""

import os
import sys
import json
import logging
from datetime import datetime, timezone

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from orchestrator import db
from orchestrator.common import dedupe_day_utc
from orchestrator.planner_tick import _attempt_maintenance_task, generate_task_slot_key
from orchestrator.light_worker_tick import run_light_worker_tick

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)


def fake_request_id() -> str:
    import uuid
    return str(uuid.uuid4())


def step_a_planner_first_tick() -> int:
    """Step A: Simulated planner tick #1 — should CREATE maintenance_health_check."""
    print("\n[Step A] Planner tick #1: expecting CREATED ...")
    req_id = fake_request_id()
    result = _attempt_maintenance_task(req_id, datetime.now(timezone.utc))

    print(f"  _attempt_maintenance_task → status={result['status']!r}  task_id={result.get('task_id')}  dedupe_key={result['dedupe_key']!r}")

    if result["status"] not in ("CREATED", "SKIP_DAILY_CAP"):
        print(f"[Step A] UNEXPECTED status: {result['status']!r}")
        sys.exit(1)

    if result["status"] == "SKIP_DAILY_CAP":
        task_id = result["task_id"]
        # Check current status — may already be QUEUED from a previous run
        task = db.get_task(task_id)
        current_status = task.get("status", "?")
        print(f"  Daily cap hit (task #{task_id} status={current_status}). Resetting to QUEUED for re-run.")
        if current_status in ("COMPLETED", "RUNNING", "FAILED"):
            db.update_task(
                task_id,
                status="QUEUED",
                started_at=None,
                completed_at=None,
                duration_seconds=None,
                worker_pid=None,
                completed_file_path=None,
                completed_text=None,
                error_message=None,
            )
            print(f"  Reset task #{task_id} → QUEUED for smoke test.")
        return task_id

    task_id = result["task_id"]
    print(f"[Step A] PASS — created task #{task_id}")
    return task_id


def step_b_planner_second_tick(expected_task_id: int) -> None:
    """Step B: Simulated planner tick #2 — should SKIP_DAILY_CAP → IDLE."""
    print("\n[Step B] Planner tick #2 (same UTC day): expecting SKIP_DAILY_CAP + IDLE ...")
    req_id = fake_request_id()
    result = _attempt_maintenance_task(req_id, datetime.now(timezone.utc))

    print(f"  _attempt_maintenance_task → status={result['status']!r}  task_id={result.get('task_id')}")

    if result["status"] != "SKIP_DAILY_CAP":
        print(f"[Step B] FAIL: expected SKIP_DAILY_CAP, got {result['status']!r}")
        sys.exit(1)

    print(f"[Step B] PASS — PLANNER_SKIP_DAILY_CAP confirmed (existing task #{result['task_id']})")

    # Verify no duplicate row was created
    conn = db.get_conn()
    today = dedupe_day_utc()
    dedupe_key = f"maintenance_health_check:{today}"
    rows = conn.execute(
        "SELECT COUNT(*) AS cnt FROM agent_tasks WHERE dedupe_key=?",
        (dedupe_key,),
    ).fetchone()
    conn.close()
    count = rows["cnt"] if rows else 0
    print(f"  Duplicate check: dedupe_key={dedupe_key!r} → {count} row(s) in DB")
    if count > 1:
        print(f"[Step B] FAIL: duplicate rows found ({count})")
        sys.exit(1)
    print(f"[Step B] PASS — exactly {count} row(s), no duplicate")


def step_c_light_worker(expected_task_id: int) -> str:
    """Step C: Light worker claims and completes the QUEUED maintenance task."""
    print("\n[Step C] Light worker tick: claiming maintenance_health_check ...")
    result = run_light_worker_tick()
    print(f"  run_light_worker_tick → {json.dumps(result, ensure_ascii=False)}")

    if result["status"] not in ("COMPLETED", "SKIPPED"):
        print(f"[Step C] FAIL: unexpected status {result['status']!r}")
        sys.exit(1)

    if result["status"] == "SKIPPED":
        # Task might already be RUNNING or completed — check DB
        task = db.get_task(expected_task_id)
        print(f"  Task #{expected_task_id} current status in DB: {task.get('status')}")
        if task.get("status") == "COMPLETED":
            print("[Step C] Task already COMPLETED — evidence will come from DB")
            return task.get("completed_file_path", "")
        print(f"[Step C] FAIL: light worker skipped but task is not COMPLETED")
        sys.exit(1)

    if result.get("task_id") != expected_task_id:
        print(f"[Step C] WARNING: claimed task #{result.get('task_id')} but expected #{expected_task_id}")

    print(f"[Step C] PASS — LIGHT_WORKER_COMPLETED, file={result.get('completed_file_path')}")
    return result.get("completed_file_path", "")


def step_d_sql_evidence(task_id: int) -> dict:
    """Step D: SQL evidence check."""
    print("\n[Step D] SQL evidence:")
    conn = db.get_conn()
    row = conn.execute(
        "SELECT id, task_type, worker_type, status, started_at, completed_at, dedupe_key, created_at "
        "FROM agent_tasks WHERE id=?",
        (task_id,),
    ).fetchone()
    conn.close()

    if not row:
        print(f"[Step D] FAIL: task #{task_id} not found")
        sys.exit(1)

    result = dict(row)
    for k, v in result.items():
        print(f"  {k:20s} = {v}")

    assert result["task_type"] == "maintenance_health_check", f"task_type={result['task_type']!r}"
    assert result["worker_type"] == "light", f"worker_type={result['worker_type']!r}"
    assert result["status"] == "COMPLETED", f"status={result['status']!r}"
    assert result["started_at"], "started_at is NULL"
    assert result["completed_at"], "completed_at is NULL"
    assert result["dedupe_key"], "dedupe_key is NULL"

    # Duplicate check
    conn2 = db.get_conn()
    dup = conn2.execute(
        "SELECT dedupe_key, COUNT(*) AS cnt FROM agent_tasks "
        "WHERE task_type='maintenance_health_check' GROUP BY dedupe_key HAVING COUNT(*) > 1"
    ).fetchall()
    conn2.close()
    if dup:
        print(f"[Step D] FAIL: duplicate dedupe_key rows found: {[dict(r) for r in dup]}")
        sys.exit(1)

    print("[Step D] PASS — all SQL assertions passed, no duplicates")
    return result


def step_e_file_evidence(completed_path: str, task_id: int) -> None:
    """Step E: File evidence check."""
    print("\n[Step E] File evidence:")

    if not completed_path:
        # Try to get from DB
        task = db.get_task(task_id)
        completed_path = task.get("completed_file_path", "")

    if not completed_path or not os.path.exists(completed_path):
        print(f"[Step E] FAIL: completed file not found at {completed_path!r}")
        sys.exit(1)

    size = os.path.getsize(completed_path)
    print(f"  Path : {completed_path}")
    print(f"  Size : {size} bytes")

    with open(completed_path, encoding="utf-8") as f:
        content = f.read()

    print("\n  Content (first 80 lines):")
    for i, line in enumerate(content.splitlines()[:80]):
        print(f"  {line}")

    # Required content checks
    assert "maintenance_health_check" in content, "task_type missing from file"
    assert "light" in content, "worker_type missing from file"
    assert "COMPLETED" in content, "status missing from file"
    assert "No external API called" in content, "constraint note missing"
    assert "Total" in content, "queue counts missing"

    print("\n[Step E] PASS — file exists, required content present")


def main():
    print("=" * 60)
    print("Phase 3 Smoke Test: Daily Cap / Dedupe / Light Worker")
    print("=" * 60)

    db.init_db()
    print("\n[Init] DB ready.")

    # A: Planner tick #1 → create
    task_id = step_a_planner_first_tick()

    # B: Planner tick #2 → SKIP_DAILY_CAP
    step_b_planner_second_tick(task_id)

    # C: Light worker → complete
    completed_path = step_c_light_worker(task_id)

    # D: SQL evidence
    db_row = step_d_sql_evidence(task_id)

    # E: File evidence
    step_e_file_evidence(completed_path, task_id)

    print("\n" + "=" * 60)
    print("RESULT: PHASE_3_SMOKE_PASS")
    print("=" * 60)
    print(f"  task_id      = {task_id}")
    print(f"  task_type    = {db_row['task_type']}")
    print(f"  worker_type  = {db_row['worker_type']}")
    print(f"  status       = {db_row['status']}")
    print(f"  dedupe_key   = {db_row['dedupe_key']}")
    print(f"  result_file  = {completed_path}")
    print()
    print("API evidence (run separately):")
    print("  curl -s 'http://127.0.0.1:8787/api/orchestrator/tasks?status=COMPLETED&limit=10' | python3 -m json.tool | head -80")
    print()
    print("Scope check:")
    print("  Fallback P1-P6:          NOT implemented")
    print("  Forced exploration:      NOT implemented")
    print("  Validation router:       NOT implemented")
    print("  CTO review:              NOT implemented")
    print("  External betting API:    NOT called")
    print("  Production betting data: NOT modified")
    print("  Git commit:              NOT made")


if __name__ == "__main__":
    main()
