#!/usr/bin/env python3
"""
Phase 2 Minimal Closed-Loop Smoke Test
=======================================
Executes exactly: Planner build → Worker claim (atomic) → Completed → visible via API/UI

SCOPE:
  - Creates one orchestration_smoke task (QUEUED)
  - Atomically claims it (RUNNING)
  - Writes a completed result file
  - Marks it COMPLETED in DB

FORBIDDEN:
  - No fallback P1-P6
  - No forced exploration
  - No validation router
  - No CTO review
  - No external API calls
  - No production betting data writes

Usage:
  cd /Users/kelvin/Kelvin-WorkSpace/Betting-pool
  .venv/bin/python3 scripts/phase2_smoke_test.py
"""

import os
import sys
import json

# ── Path setup ──────────────────────────────────────────────────────────────
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from datetime import datetime, timezone
from orchestrator import db, common

# ── Constants ────────────────────────────────────────────────────────────────
TASK_TYPE = "orchestration_smoke"
WORKER_TYPE = "light"
TASK_TITLE = "[ORCH-TEST] Minimal closed-loop smoke task"


def _slot_key() -> str:
    now = datetime.now(timezone.utc)
    return f"{now.strftime('%Y%m%d%H%M%S%f')}-task"


def step_a_planner_create() -> int:
    """Step A: Planner creates one QUEUED orchestration_smoke task."""
    today = common.dedupe_day_utc()
    dedupe_key = f"{TASK_TYPE}:{today}"

    # Dedupe check — skip if already QUEUED/RUNNING/COMPLETED today
    conn = db.get_conn()
    try:
        row = conn.execute(
            "SELECT id, status FROM agent_tasks WHERE dedupe_key=?",
            (dedupe_key,),
        ).fetchone()
    finally:
        conn.close()

    if row:
        existing_id = row["id"]
        existing_status = row["status"]
        print(f"[Step A] Dedupe hit: task #{existing_id} already exists with status={existing_status}")
        print(f"         dedupe_key={dedupe_key!r}")
        if existing_status == "QUEUED":
            print(f"[Step A] Will proceed with existing QUEUED task #{existing_id}")
            return existing_id
        elif existing_status == "RUNNING":
            print(f"[Step A] Task #{existing_id} is already RUNNING — aborting smoke test")
            sys.exit(1)
        elif existing_status == "COMPLETED":
            # Reset to QUEUED so we can re-run the closed-loop demo
            print(f"[Step A] Task #{existing_id} was COMPLETED — resetting to QUEUED for re-run")
            db.update_task(
                existing_id,
                status="QUEUED",
                started_at=None,
                completed_at=None,
                duration_seconds=None,
                worker_pid=None,
                completed_file_path=None,
                completed_text=None,
                error_message=None,
            )
            return existing_id
        else:
            print(f"[Step A] Task #{existing_id} has status={existing_status} — resetting to QUEUED")
            db.update_task(existing_id, status="QUEUED")
            return existing_id

    slot_key = _slot_key()
    date_folder = common.dedupe_day_utc()
    task_dir = os.path.join(REPO_ROOT, "runtime", "agent_orchestrator", "tasks", date_folder)
    os.makedirs(task_dir, exist_ok=True)
    prompt_path = os.path.join(task_dir, f"{slot_key}-prompt.md")

    prompt_content = (
        f"# {TASK_TITLE}\n\n"
        "## Objective\n"
        "Verify Betting-pool orchestration minimal closed loop.\n\n"
        "## Constraints\n"
        "- No betting strategy changes\n"
        "- No external API calls\n"
        "- No production DB writes except orchestrator task state\n"
        "- Complete by writing a small completed markdown result\n\n"
        f"## Task Type\n{TASK_TYPE}\n\n"
        f"## Created At\n{datetime.now(timezone.utc).isoformat()}\n"
    )
    with open(prompt_path, "w", encoding="utf-8") as f:
        f.write(prompt_content)

    task_id = db.create_task(
        slot_key=slot_key,
        date_folder=date_folder,
        title=TASK_TITLE,
        slug=slot_key,
        status="QUEUED",
        prompt_file_path=prompt_path,
        prompt_text=prompt_content,
        dedupe_key=dedupe_key,
        task_type=TASK_TYPE,
        worker_type=WORKER_TYPE,
        regime_state="phase2_minimal_loop",
        epoch_id=0,
    )
    print(f"[Step A] Created task #{task_id}  slot_key={slot_key}  dedupe_key={dedupe_key!r}")
    return task_id


def step_b_worker_claim(expected_task_id: int) -> dict:
    """Step B: Worker atomically claims the QUEUED task."""
    print(f"[Step B] Attempting atomic claim for task_type={TASK_TYPE!r} ...")
    task = db.claim_task_atomic(task_type=TASK_TYPE)
    if not task:
        print("[Step B] FAIL: claim_task_atomic returned None — no QUEUED orchestration_smoke task found")
        sys.exit(1)

    claimed_id = task["id"]
    if claimed_id != expected_task_id:
        print(f"[Step B] WARNING: claimed task #{claimed_id} but expected #{expected_task_id}")

    print(f"[Step B] Claimed task #{claimed_id}  status={task['status']}  started_at={task['started_at']}  worker_pid={task['worker_pid']}")

    if task["status"] != "RUNNING":
        print(f"[Step B] FAIL: expected status=RUNNING, got {task['status']!r}")
        sys.exit(1)
    if not task["started_at"]:
        print("[Step B] FAIL: started_at is NULL after claim")
        sys.exit(1)

    return task


def step_c_worker_complete(task: dict) -> str:
    """Step C: Worker completes the task and writes a result file."""
    task_id = task["id"]
    slot_key = task["slot_key"]
    date_folder = task["date_folder"]

    start_dt = datetime.fromisoformat(task["started_at"])
    end_dt = datetime.now(timezone.utc)
    duration = int((end_dt - start_dt).total_seconds())

    task_dir = os.path.join(REPO_ROOT, "runtime", "agent_orchestrator", "tasks", date_folder)
    os.makedirs(task_dir, exist_ok=True)
    completed_path = os.path.join(task_dir, f"{slot_key}-completed.md")

    result_content = (
        f"# Completed: {TASK_TITLE}\n\n"
        f"**Task ID:** {task_id}\n"
        f"**Status:** COMPLETED\n"
        f"**Task Type:** {TASK_TYPE}\n"
        f"**Worker Type:** {WORKER_TYPE}\n"
        f"**Started:** {task['started_at']}\n"
        f"**Completed:** {end_dt.isoformat()}\n"
        f"**Duration:** {duration}s\n"
        f"**Worker PID:** {task['worker_pid']}\n\n"
        "## Result\n\n"
        "Minimal closed-loop smoke test completed successfully.\n\n"
        "### Evidence\n"
        "- Task created via planner-equivalent with `task_type=orchestration_smoke`\n"
        "- Task claimed atomically via `BEGIN IMMEDIATE` transaction\n"
        "- Task marked COMPLETED with timestamp and result file\n"
        "- DB migration added `task_type` and `worker_type` columns to `agent_tasks`\n"
        "- `dedupe_day_utc()` helper added to `orchestrator/common.py`\n\n"
        "### Scope Confirmation\n"
        "- Fallback P1-P6: NOT implemented\n"
        "- Forced exploration: NOT implemented\n"
        "- Validation router: NOT implemented\n"
        "- CTO review: NOT implemented\n"
        "- External betting API: NOT called\n"
        "- Production betting data: NOT modified\n"
    )

    with open(completed_path, "w", encoding="utf-8") as f:
        f.write(result_content)

    db.update_task(
        task_id,
        status="COMPLETED",
        completed_at=end_dt.isoformat(),
        duration_seconds=duration,
        completed_file_path=completed_path,
        completed_text=result_content,
        changed_files_json=json.dumps([]),
    )

    print(f"[Step C] Task #{task_id} marked COMPLETED  duration={duration}s")
    print(f"[Step C] Result file: {completed_path}")
    return completed_path


def step_d_verify_db(task_id: int) -> dict:
    """Step D: SQL evidence — verify the completed task row."""
    conn = db.get_conn()
    try:
        row = conn.execute(
            "SELECT id, task_type, status, created_at, started_at, completed_at "
            "FROM agent_tasks WHERE id=?",
            (task_id,),
        ).fetchone()
    finally:
        conn.close()

    if not row:
        print(f"[Step D] FAIL: task #{task_id} not found in DB")
        sys.exit(1)

    result = dict(row)
    print("\n[Step D] SQL Evidence:")
    print(f"  id          = {result['id']}")
    print(f"  task_type   = {result['task_type']}")
    print(f"  status      = {result['status']}")
    print(f"  created_at  = {result['created_at']}")
    print(f"  started_at  = {result['started_at']}")
    print(f"  completed_at= {result['completed_at']}")

    assert result["task_type"] == TASK_TYPE, f"task_type mismatch: {result['task_type']!r}"
    assert result["status"] == "COMPLETED", f"status mismatch: {result['status']!r}"
    assert result["created_at"], "created_at is NULL"
    assert result["started_at"], "started_at is NULL"
    assert result["completed_at"], "completed_at is NULL"

    return result


def main():
    print("=" * 60)
    print("Phase 2 Minimal Closed-Loop Smoke Test")
    print("=" * 60)

    # Run DB migrations first
    print("\n[Init] Running DB migrations ...")
    db.init_db()
    print("[Init] DB ready.")

    # Step A: Planner creates task
    print()
    task_id = step_a_planner_create()

    # Step B: Worker claims atomically
    print()
    claimed_task = step_b_worker_claim(task_id)

    # Step C: Worker completes task
    print()
    completed_path = step_c_worker_complete(claimed_task)

    # Step D: SQL verification
    print()
    db_row = step_d_verify_db(task_id)

    print("\n" + "=" * 60)
    print("RESULT: PHASE_2_SMOKE_PASS")
    print("=" * 60)
    print(f"  task_id      = {task_id}")
    print(f"  task_type    = {db_row['task_type']}")
    print(f"  status       = {db_row['status']}")
    print(f"  result_file  = {completed_path}")
    print()
    print("API evidence (run separately):")
    print("  curl -s http://127.0.0.1:8787/api/orchestrator/tasks | python3 -m json.tool | head -60")
    print()


if __name__ == "__main__":
    main()
