"""
Orchestrator FastAPI routes.
Mount in your app: app.include_router(orchestrator.api.router, tags=["Orchestrator"])
"""

import os
import sys
import subprocess
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional

from orchestrator import db, common

router = APIRouter()


def _attach_task_meta_fields(task: dict) -> dict:
    slot_key = task.get("slot_key")
    date_folder = task.get("date_folder")
    if not slot_key or not date_folder:
        return task
    try:
        meta = common.read_meta(slot_key, date_folder)
    except Exception:
        meta = {}
    if not isinstance(meta, dict):
        meta = {}
    task["planner_source"] = meta.get("planner_source")
    task["planner_provider"] = meta.get("planner_provider")
    task["worker_provider"] = meta.get("worker_provider")
    task["worker_requested_provider"] = meta.get("worker_requested_provider")
    task["worker_runtime"] = meta.get("worker_runtime")
    task["worker_execution_mode"] = meta.get("worker_execution_mode")
    task["worker_fallback_reason"] = meta.get("worker_fallback_reason")
    task["task_contract_path"] = meta.get("task_contract_path")
    task["task_result_path"] = meta.get("task_result_path")
    task["gate_verdict"] = meta.get("gate_verdict")
    task["gate_reason"] = meta.get("gate_reason")
    return task


@router.get("/api/orchestrator/summary")
def get_summary():
    """Today's task stats + worker status."""
    today = datetime.now().strftime("%Y%m%d")
    tasks = db.list_tasks(date_folder=today, limit=200)
    counts = {}
    for t in tasks:
        counts[t["status"]] = counts.get(t["status"], 0) + 1

    lock = db.get_worker_lock()
    worker_busy = False
    worker_pid = None
    worker_task_id = None
    if lock and lock["pid"] and common.is_process_alive(lock["pid"]):
        worker_busy = True
        worker_pid = lock["pid"]
        worker_task_id = lock["task_id"]

    recent_runs = db.list_runs(limit=10)
    outcome_dist = {}
    for r in recent_runs:
        outcome_dist[r["outcome"]] = outcome_dist.get(r["outcome"], 0) + 1

    daemon_status = common.copilot_daemon_status()

    return {
        "today": today,
        "scheduler_enabled": db.is_scheduler_enabled(),
        "planner_provider": db.get_planner_provider(),
        "planner_provider_label": common.planner_provider_label(db.get_planner_provider()),
        "worker_provider": db.get_worker_provider(),
        "worker_provider_label": common.worker_provider_label(db.get_worker_provider()),
        "combo_label": common.planner_worker_combo_label(
            db.get_planner_provider(),
            db.get_worker_provider(),
        ),
        "task_counts": counts,
        "total_today": len(tasks),
        "worker_busy": worker_busy,
        "worker_pid": worker_pid,
        "worker_task_id": worker_task_id,
        "copilot_daemon_running": daemon_status.get("running", False),
        "copilot_daemon_pid": daemon_status.get("pid"),
        "copilot_daemon_status": daemon_status.get("status"),
        "copilot_daemon_task_id": daemon_status.get("current_task_id"),
        "recent_run_outcomes": outcome_dist,
    }


class SchedulerToggleRequest(BaseModel):
    enabled: bool


class ProviderConfigRequest(BaseModel):
    planner_provider: Optional[str] = None
    worker_provider: Optional[str] = None


class RunNowRequest(BaseModel):
    runner: str


@router.get("/api/orchestrator/scheduler")
def get_scheduler_status():
    return {"enabled": db.is_scheduler_enabled()}


@router.post("/api/orchestrator/scheduler")
def set_scheduler_status(req: SchedulerToggleRequest):
    db.set_scheduler_enabled(req.enabled)
    state = "ENABLED" if req.enabled else "DISABLED"
    db.log_tick("orchestrator", f"SCHEDULER_{state}", message=f"Scheduler set to {state}")
    return {"enabled": req.enabled}


@router.get("/api/orchestrator/providers")
def get_provider_config():
    planner_provider = db.get_planner_provider()
    worker_provider = db.get_worker_provider()
    return {
        "planner_provider": planner_provider,
        "planner_provider_label": common.planner_provider_label(planner_provider),
        "worker_provider": worker_provider,
        "worker_provider_label": common.worker_provider_label(worker_provider),
        "combo_label": common.planner_worker_combo_label(planner_provider, worker_provider),
        "planner_options": common.planner_provider_options(),
        "worker_options": common.worker_provider_options(),
    }


@router.post("/api/orchestrator/providers")
def set_provider_config(req: ProviderConfigRequest):
    planner_provider = common.normalize_planner_provider(req.planner_provider or db.get_planner_provider())
    worker_provider = common.normalize_worker_provider(req.worker_provider or db.get_worker_provider())

    planner_ok, planner_reason = common.provider_available("planner", planner_provider)
    if not planner_ok:
        raise HTTPException(status_code=400, detail=f"Planner provider unavailable: {planner_reason}")

    worker_ok, worker_reason = common.provider_available("worker", worker_provider)
    if not worker_ok:
        raise HTTPException(status_code=400, detail=f"Worker provider unavailable: {worker_reason}")

    db.set_planner_provider(planner_provider)
    db.set_worker_provider(worker_provider)

    combo_label = common.planner_worker_combo_label(planner_provider, worker_provider)
    db.log_tick(
        "orchestrator",
        "PROVIDERS_UPDATED",
        message=f"Provider combo set to {combo_label}",
    )
    return {
        "planner_provider": planner_provider,
        "planner_provider_label": common.planner_provider_label(planner_provider),
        "worker_provider": worker_provider,
        "worker_provider_label": common.worker_provider_label(worker_provider),
        "combo_label": combo_label,
    }


@router.post("/api/orchestrator/run-now")
def run_now(req: RunNowRequest):
    runner = (req.runner or "").strip().lower()
    if runner not in ("planner", "worker"):
        raise HTTPException(status_code=400, detail="runner must be planner or worker")

    if runner == "worker" and db.get_worker_provider() == "copilot-daemon":
        daemon_status = common.copilot_daemon_status()
        if daemon_status.get("running"):
            db.log_tick("orchestrator", "WORKER_MANUAL_DELEGATED", message=f"worker run-now delegated to copilot-daemon pid={daemon_status.get('pid')}")
            return {
                "ok": True,
                "runner": runner,
                "pid": daemon_status.get("pid"),
                "delegated_to": "copilot-daemon",
                "triggered_at": datetime.utcnow().isoformat(),
            }
        script_name = "copilot_daemon.py"
        extra_args = ["--once"]
    else:
        script_name = "planner_tick.py" if runner == "planner" else "worker_tick.py"
        extra_args = []

    script_path = os.path.join(common.ROOT, "orchestrator", script_name)
    if not os.path.exists(script_path):
        raise HTTPException(status_code=500, detail=f"runner script missing: {script_name}")

    env = os.environ.copy()
    env["ORCHESTRATOR_FORCE_RUN"] = "1"
    proc = subprocess.Popen(
        [sys.executable, script_path, *extra_args],
        cwd=common.ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    outcome = "PLANNER_MANUAL_TRIGGERED" if runner == "planner" else "WORKER_MANUAL_TRIGGERED"
    db.log_tick("orchestrator", outcome, message=f"{runner} run-now triggered, pid={proc.pid}")
    return {"ok": True, "runner": runner, "pid": proc.pid, "triggered_at": datetime.utcnow().isoformat()}


@router.get("/api/orchestrator/tasks")
def list_tasks(
    date: str = Query(None, description="YYYYMMDD"),
    status: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
):
    offset = (page - 1) * page_size
    total = db.count_tasks(date_folder=date, status=status)
    tasks = db.list_tasks(date_folder=date, status=status, limit=page_size, offset=offset)
    tasks = [_attach_task_meta_fields(dict(task)) for task in tasks]
    total_pages = max(1, (total + page_size - 1) // page_size)
    return {
        "tasks": tasks,
        "count": len(tasks),
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
    }


@router.get("/api/orchestrator/tasks/{task_id}")
def get_task(task_id: int):
    task = db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task = _attach_task_meta_fields(dict(task))

    # Attach codex stdout tail (last 200 lines)
    slot_key = task["slot_key"]
    date_folder = task["date_folder"]
    log_path = common.find_stdout_log_path(slot_key, date_folder)
    codex_tail = ""
    if os.path.exists(log_path):
        with open(log_path) as f:
            lines = f.readlines()
            codex_tail = "".join(lines[-200:])
    task_contract = None
    task_result = None
    contract_path = task.get("task_contract_path")
    result_path = task.get("task_result_path")
    if contract_path and os.path.exists(contract_path):
        try:
            with open(contract_path, "r", encoding="utf-8") as f:
                task_contract = f.read()
        except OSError:
            task_contract = None
    if result_path and os.path.exists(result_path):
        try:
            with open(result_path, "r", encoding="utf-8") as f:
                task_result = f.read()
        except OSError:
            task_result = None

    return {
        **task,
        "codex_stdout_tail": codex_tail,
        "task_contract": task_contract,
        "task_result": task_result,
    }


@router.get("/api/orchestrator/runs")
def list_runs(
    runner: str = Query(None, description="planner or worker"),
    since: str = Query(None, description="ISO datetime"),
    limit: int = Query(10, ge=1, le=100),
):
    runs = db.list_runs(runner=runner, since=since, limit=limit)
    return {"runs": runs, "count": len(runs)}


@router.get("/api/orchestrator/backlog")
def get_backlog():
    content = common.read_backlog()
    return {"content": content, "path": common.BACKLOG_PATH}
