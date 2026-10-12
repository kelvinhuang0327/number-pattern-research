"""
Betting-pool Orchestrator Light Worker Tick
===========================================
Phase 3: Minimal light worker for maintenance and health-check tasks.

Scope:
- Claims one QUEUED task where worker_type='light' (atomic, using BEGIN IMMEDIATE)
- Executes maintenance_health_check without LLM or external APIs
- Writes a completed markdown file
- Marks task COMPLETED in DB

Events / Logs:
- LIGHT_WORKER_CLAIMED
- LIGHT_WORKER_COMPLETED
- LIGHT_WORKER_SKIP_IDLE_NO_TASK

Forbidden:
- No LLM calls
- No external betting API calls
- No betting strategy changes
- No production betting data writes
"""

import os
import json
import logging
import sys
from datetime import datetime, timezone

from orchestrator import db
from orchestrator.common import dedupe_day_utc

logger = logging.getLogger(__name__)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNNER_NAME = "light_worker_tick"
LIGHT_WORKER_TYPE = "light"


# ── Task executors ─────────────────────────────────────────────────────────

def _execute_maintenance_health_check(task: dict) -> str:
    """Execute maintenance_health_check — no LLM, no external APIs.

    Gathers orchestrator DB queue counts, writes a completed markdown, returns the file path.
    """
    task_id = task["id"]
    slot_key = task["slot_key"]
    date_folder = task["date_folder"]

    # Gather DB stats — purely internal, no external calls
    queue_counts = db.count_tasks_by_status()
    total_tasks = sum(queue_counts.values())

    task_dir = os.path.join(REPO_ROOT, "runtime", "agent_orchestrator", "tasks", date_folder)
    os.makedirs(task_dir, exist_ok=True)
    completed_path = os.path.join(task_dir, f"{slot_key}-completed-maintenance-health-check.md")

    now_iso = datetime.now(timezone.utc).isoformat()

    queue_lines = "\n".join(f"- {status}: {count}" for status, count in sorted(queue_counts.items()))

    content = (
        f"# [MAINTENANCE] Orchestration Health Check\n\n"
        f"**Task ID:** {task_id}\n"
        f"**Task Type:** {task.get('task_type', 'maintenance_health_check')}\n"
        f"**Worker Type:** {task.get('worker_type', 'light')}\n"
        f"**Status:** COMPLETED\n"
        f"**Timestamp:** {now_iso}\n"
        f"**DB Path:** {db.DB_PATH}\n\n"
        f"## Queue Status\n\n"
        f"{queue_lines}\n"
        f"- **Total:** {total_tasks}\n\n"
        f"## Health Assessment\n\n"
        f"Orchestrator DB is reachable. Task queue enumerated successfully.\n\n"
        f"## Scope Constraints\n\n"
        f"- No external API called\n"
        f"- No betting strategy modified\n"
        f"- No production betting data written\n"
        f"- No LLM used\n"
        f"- Light worker only\n"
    )

    with open(completed_path, "w", encoding="utf-8") as f:
        f.write(content)

    return completed_path


_TASK_EXECUTORS: dict[str, callable] = {
    "maintenance_health_check": _execute_maintenance_health_check,
}


# ── Main tick ──────────────────────────────────────────────────────────────

def run_light_worker_tick() -> dict:
    """Claim and complete one QUEUED light task (worker_type='light').

    Returns a result dict with status, outcome, task_id (if claimed).
    """
    start_time = datetime.now(timezone.utc)
    logger.info("[LightWorker] Starting light_worker_tick")

    # Atomic claim — only light tasks
    task = db.claim_task_atomic(worker_type=LIGHT_WORKER_TYPE)

    if not task:
        idle_msg = "LIGHT_WORKER_SKIP_IDLE_NO_TASK: Light Worker 已執行，目前沒有待處理 light 任務。"
        logger.info("[LightWorker] %s", idle_msg)
        db.record_run(
            runner=RUNNER_NAME,
            outcome="SKIPPED",
            message=idle_msg,
            tick_at=start_time.isoformat(),
        )
        return {"status": "SKIPPED", "outcome": "LIGHT_WORKER_SKIP_IDLE_NO_TASK", "message": idle_msg}

    task_id = task["id"]
    task_type = task.get("task_type", "")
    claimed_msg = (
        f"LIGHT_WORKER_CLAIMED: task #{task_id} task_type={task_type!r} worker_type={task.get('worker_type')!r}"
    )
    logger.info("[LightWorker] %s", claimed_msg)
    db.record_run(
        runner=RUNNER_NAME,
        outcome="CLAIMED",
        task_id=task_id,
        message=claimed_msg,
        tick_at=start_time.isoformat(),
    )

    # Dispatch to executor
    executor = _TASK_EXECUTORS.get(task_type)
    if not executor:
        # Unknown light task type — mark FAILED
        err_msg = f"[LightWorker] No executor for task_type={task_type!r} (task #{task_id})"
        logger.warning(err_msg)
        db.update_task(
            task_id,
            status="FAILED",
            error_message=err_msg,
            completed_at=datetime.now(timezone.utc).isoformat(),
        )
        db.record_run(
            runner=RUNNER_NAME,
            outcome="FAILED",
            task_id=task_id,
            message=err_msg,
            tick_at=start_time.isoformat(),
        )
        return {"status": "FAILED", "task_id": task_id, "message": err_msg}

    try:
        completed_path = executor(task)
    except Exception as exc:
        err_msg = f"[LightWorker] Executor failed for task #{task_id}: {exc}"
        logger.error(err_msg)
        db.update_task(
            task_id,
            status="FAILED",
            error_message=str(exc),
            completed_at=datetime.now(timezone.utc).isoformat(),
        )
        db.record_run(
            runner=RUNNER_NAME,
            outcome="FAILED",
            task_id=task_id,
            message=err_msg,
            tick_at=start_time.isoformat(),
        )
        return {"status": "FAILED", "task_id": task_id, "message": err_msg}

    end_time = datetime.now(timezone.utc)
    duration = int((end_time - start_time).total_seconds())

    # Read completed content for DB storage
    try:
        with open(completed_path, encoding="utf-8") as f:
            completed_text = f.read()
    except Exception:
        completed_text = None

    db.update_task(
        task_id,
        status="COMPLETED",
        completed_at=end_time.isoformat(),
        duration_seconds=duration,
        completed_file_path=completed_path,
        completed_text=completed_text,
        changed_files_json=json.dumps([]),
    )

    completed_msg = (
        f"LIGHT_WORKER_COMPLETED: task #{task_id} task_type={task_type!r} "
        f"duration={duration}s file={completed_path}"
    )
    logger.info("[LightWorker] %s", completed_msg)
    db.record_run(
        runner=RUNNER_NAME,
        outcome="COMPLETED",
        task_id=task_id,
        message=completed_msg,
        tick_at=start_time.isoformat(),
        duration_seconds=duration,
    )

    return {
        "status": "COMPLETED",
        "outcome": "LIGHT_WORKER_COMPLETED",
        "task_id": task_id,
        "task_type": task_type,
        "completed_file_path": completed_path,
        "duration_seconds": duration,
        "message": completed_msg,
    }


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    db.init_db()
    result = run_light_worker_tick()
    print(json.dumps(result, indent=2, ensure_ascii=False))
