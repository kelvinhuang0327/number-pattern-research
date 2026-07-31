"""
Betting-pool Orchestrator FastAPI Routes
完整實作 Task Orchestration 與 CTO Review API 規格
"""

import os
import json
import subprocess
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated, Optional

from fastapi import APIRouter, FastAPI, HTTPException, Query
from pydantic import BaseModel
import uvicorn

from orchestrator import db
from orchestrator import execution_policy
from orchestrator.common import (
    COPILOT_MODEL_PRESETS,
    copilot_daemon_status,
    planner_provider_label,
    planner_provider_options,
    provider_available,
    provider_combo_label,
    validate_copilot_model,
    worker_provider_label,
    worker_provider_options,
)
from orchestrator.cto_review_tick import run_cto_review_tick
from orchestrator.planner_tick import run_planner_tick
from orchestrator.worker_tick import run_worker_tick

router = APIRouter()

PROJECT_ROOT = Path(__file__).parent.parent

TASK_STATUSES = (
    "QUEUED", "RUNNING", "COMPLETED", "FAILED",
    "FAILED_RATE_LIMIT", "BLOCKED_ENV", "REPLAN_REQUIRED", "CANCELLED",
)

# In-memory tracking for spawned processes (request_id -> pid)
_spawned_pids: dict[str, int] = {}
# CTO force-run timestamps for rate limiting
_cto_force_run_times: list[datetime] = []

ERROR_404_RESPONSE = {404: {"description": "Resource not found"}}
ERROR_500_RESPONSE = {500: {"description": "Internal server error"}}
ERROR_400_RESPONSE = {400: {"description": "Bad request"}}
ERROR_429_RESPONSE = {429: {"description": "Too many requests"}}


# Pydantic Models

class SchedulerToggleRequest(BaseModel):
    enabled: bool


class ProviderConfigRequest(BaseModel):
    planner_provider: Optional[str] = None
    worker_provider: Optional[str] = None
    worker_copilot_model: Optional[str] = None


class RuntimeModeRequest(BaseModel):
    mode: str


class RunNowRequest(BaseModel):
    runner: str  # "planner" | "worker"


class CTOSchedulerToggleRequest(BaseModel):
    enabled: bool


class CTOProviderConfigRequest(BaseModel):
    planner_provider: Optional[str] = None
    planner_model: Optional[str] = None


class CTORunNowRequest(BaseModel):
    force: Optional[bool] = False
    run_intent: Optional[str] = None   # retry | compare | override
    parent_run_id: Optional[str] = None


class BacklogCreateRequest(BaseModel):
    finding_id: str
    cto_run_id: str
    severity: str
    urgency: str
    category: str
    title: str
    description: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None


class BacklogBatchRequest(BaseModel):
    cto_run_id: str
    min_severity: str = "HIGH"
    min_impact: int = 60


# Internal Helpers

def _enrich_task(task: dict) -> dict:
    enriched = dict(task)
    enriched["objective"] = task.get("title") or task.get("objective")
    enriched["task_key"] = task.get("slug") or task.get("slot_key")
    enriched["finished_at"] = task.get("completed_at")
    enriched["quality_status"] = "PASS"
    enriched["rejection_reasons"] = []
    return enriched


def _parse_changed_files(raw: Optional[str]) -> list:
    if not raw:
        return []
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return []


def _parse_iso(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(str(ts))
    except ValueError:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _estimate_next_tick_at(
    runs: list[dict], runner: str, interval_minutes: int = 10
) -> Optional[str]:
    latest = next((r for r in runs if r.get("runner") == runner), None)
    if not latest:
        return None
    dt = _parse_iso(latest.get("tick_at"))
    if not dt:
        return None
    interval = timedelta(minutes=interval_minutes)
    next_dt = dt + interval
    now = datetime.now(timezone.utc)
    if next_dt <= now:
        elapsed = now - next_dt
        missed = int(elapsed.total_seconds() // interval.total_seconds()) + 1
        next_dt += interval * missed
    return next_dt.isoformat()


def _build_provider_config_payload() -> dict:
    planner_prov = db.get_planner_provider()
    worker_prov = db.get_worker_provider()
    worker_copilot_model = db.get_worker_copilot_model()
    runtime_state = execution_policy.get_state()
    return {
        "planner_provider": planner_prov,
        "planner_provider_label": planner_provider_label(planner_prov),
        "worker_provider": worker_prov,
        "worker_provider_label": worker_provider_label(worker_prov),
        "combo_label": provider_combo_label(planner_prov, worker_prov),
        "planner_options": planner_provider_options(),
        "worker_options": worker_provider_options(),
        "worker_copilot_model": worker_copilot_model,
        "worker_copilot_model_presets": COPILOT_MODEL_PRESETS,
        "llm_execution_mode": runtime_state["llm_execution_mode"],
        "hard_off": runtime_state["hard_off"],
    }


def _build_cto_provider_payload() -> dict:
    planner_prov = db.get_setting("cto_planner_provider", "claude")
    planner_model = db.get_setting("cto_planner_model", "")
    return {
        "planner_provider": planner_prov,
        "planner_provider_label": planner_provider_label(planner_prov),
        "planner_options": planner_provider_options(),
        "planner_model": planner_model,
        "planner_model_presets": COPILOT_MODEL_PRESETS,
    }


def _spawn_runner(runner: str, request_id: str, extra_env: Optional[dict] = None) -> int:
    subcmd = "planner-tick" if runner == "planner" else "worker-tick"
    if runner == "cto":
        subcmd = "cto-review-tick"
    script = PROJECT_ROOT / "scripts" / "agent_orchestrator.py"
    env = {**os.environ, "ORCHESTRATOR_FORCE_RUN": "1", "ORCHESTRATOR_REQUEST_ID": request_id}
    if extra_env:
        env.update(extra_env)
    proc = subprocess.Popen(
        [sys.executable, str(script), subcmd],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
    )
    return proc.pid


def _is_pid_running(pid: Optional[int]) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def _check_cto_force_rate_limit() -> None:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=10)
    _cto_force_run_times[:] = [t for t in _cto_force_run_times if t > cutoff]
    if len(_cto_force_run_times) >= 3:
        raise HTTPException(status_code=429, detail="Force run rate limit: max 3 per 10 minutes")
    _cto_force_run_times.append(now)


def _worker_state_label(scheduler_enabled: bool, worker_busy: bool) -> str:
    if not scheduler_enabled:
        return "未啟動"
    if worker_busy:
        return "執行中"
    return "閒置"


# Core Orchestrator Summary

@router.get("/api/summary", responses=ERROR_500_RESPONSE)
def get_summary():
    try:
        counts = db.count_tasks_by_status()
        latest_task = db.get_latest_task()
        scheduler_enabled = execution_policy.get_state()["scheduler_enabled"]
        runtime_state = execution_policy.get_state()
        runs = db.list_runs(limit=10)
        next_planner_at = _estimate_next_tick_at(runs, "planner_tick", 10)
        next_worker_at = _estimate_next_tick_at(runs, "worker_tick", 10)
        latest_planner_run = db.get_latest_run_by_runner("planner_tick")
        planner_prov = db.get_planner_provider()
        worker_prov = db.get_worker_provider()
        latest_task_payload = _enrich_task(latest_task) if latest_task else None
        latest_planner_run_payload = dict(latest_planner_run) if latest_planner_run else None
        if latest_planner_run_payload:
            latest_planner_run_payload["rejection_reasons"] = [
                line for line in str(latest_planner_run_payload.get("log_snippet") or "").splitlines()
                if line.strip()
            ]
        return {
            "project": {"name": "Betting Pool", "slug": "betting-pool",
                        "planner_provider": planner_prov, "worker_provider": worker_prov},
            "scheduler": {"enabled": scheduler_enabled, "interval_minutes": 10,
                          "next_planner_run_at": next_planner_at, "next_worker_run_at": next_worker_at,
                          "updated_at": datetime.now(timezone.utc).isoformat()},
            "runtime_control": runtime_state,
            "counts": counts,
            "latest_task": latest_task_payload,
            "latest_planner_run": latest_planner_run_payload,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _get_usage_detail_safe(window: str = "today", limit: int = 10) -> dict:
    """Usage 摘要 helper — 例外不對外曝露，回傳空摘要。"""
    try:
        from orchestrator.llm_usage_summary import get_usage_summary
        return get_usage_summary(window=window, limit=limit)
    except Exception:
        return {"available": False, "roles": {}, "recent": [], "warnings": []}


@router.get("/api/orchestrator/summary", responses=ERROR_500_RESPONSE)
def get_orchestrator_summary():
    try:
        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        runtime_state = execution_policy.get_state()
        scheduler_enabled = runtime_state["scheduler_enabled"]
        planner_prov = db.get_planner_provider()
        worker_prov = db.get_worker_provider()
        combo_label = provider_combo_label(planner_prov, worker_prov)

        runs = db.list_runs(limit=20)
        next_planner_at = _estimate_next_tick_at(runs, "planner_tick", 10)
        next_worker_at = _estimate_next_tick_at(runs, "worker_tick", 10)

        all_counts = db.count_tasks_by_status()
        task_counts = {s: all_counts.get(s, 0) for s in TASK_STATUSES}
        total_today = db.count_tasks(date_folder=today)

        running_tasks = db.list_tasks(limit=5, status="RUNNING")
        worker_busy = len(running_tasks) > 0
        worker_task_id = running_tasks[0].get("id") if running_tasks else None
        worker_state = _worker_state_label(scheduler_enabled, worker_busy)

        daemon = copilot_daemon_status()

        return {
            "today": today,
            "scheduler_enabled": scheduler_enabled,
            "llm_execution_mode": runtime_state["llm_execution_mode"],
            "hard_off": runtime_state["hard_off"],
            "llm_blocked_count": runtime_state["llm_blocked_count"],
            "last_llm_call_at": runtime_state["last_llm_call_at"],
            "last_llm_call_runner": runtime_state["last_llm_call_runner"],
            "last_llm_call_provider": runtime_state["last_llm_call_provider"],
            "last_llm_blocked_at": runtime_state["last_llm_blocked_at"],
            "last_llm_blocked_reason": runtime_state["last_llm_blocked_reason"],
            "active_background_runner": runtime_state["active_background_runner"],
            "planner_provider": planner_prov,
            "worker_provider": worker_prov,
            "combo_label": combo_label,
            "task_counts": task_counts,
            "total_today": total_today,
            "worker_busy": worker_busy,
            "worker_pid": None,
            "worker_task_id": worker_task_id,
            "worker_state": worker_state,
            "copilot_daemon_running": daemon.get("running", False),
            "copilot_daemon_pid": daemon.get("pid"),
            "copilot_daemon_status": daemon.get("reason", ""),
            "copilot_daemon_task_id": None,
            "next_planner_tick_estimate": next_planner_at,
            "next_worker_tick_estimate": next_worker_at,
            "usage_detail": _get_usage_detail_safe(),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# Scheduler

@router.get("/api/scheduler")
@router.get("/api/orchestrator/scheduler")
def get_scheduler_status():
    return {"enabled": execution_policy.get_state()["scheduler_enabled"]}


@router.post("/api/scheduler/enable")
@router.post("/api/orchestrator/scheduler")
def set_scheduler_status(req: SchedulerToggleRequest):
    state = execution_policy.set_scheduler_enabled(req.enabled)
    return {"enabled": state["scheduler_enabled"]}


# Providers

@router.get("/api/providers")
@router.get("/api/orchestrator/providers")
def get_provider_config():
    return _build_provider_config_payload()


@router.post("/api/providers", responses=ERROR_400_RESPONSE)
@router.post("/api/orchestrator/providers", responses=ERROR_400_RESPONSE)
def set_provider_config(req: ProviderConfigRequest):
    if req.planner_provider:
        if req.planner_provider not in {"claude", "codex"}:
            raise HTTPException(400, "Planner provider 僅支援 claude / codex")
        ok, reason = provider_available(req.planner_provider)
        if not ok:
            raise HTTPException(400, f"Planner provider unavailable: {reason}")
        db.set_planner_provider(req.planner_provider)
    if req.worker_provider:
        if req.worker_provider not in {"codex", "copilot", "copilot-daemon", "claude"}:
            raise HTTPException(400, "Worker provider 不支援")
        ok, reason = provider_available(req.worker_provider)
        if not ok:
            raise HTTPException(400, f"Worker provider unavailable: {reason}")
        db.set_worker_provider(req.worker_provider)
    if req.worker_copilot_model is not None:
        if not validate_copilot_model(req.worker_copilot_model):
            raise HTTPException(400, "worker_copilot_model 格式不合法")
        db.set_worker_copilot_model(req.worker_copilot_model)
    return _build_provider_config_payload()


@router.get("/api/runtime-mode")
@router.get("/api/orchestrator/runtime-mode")
def get_runtime_mode():
    return execution_policy.get_state()


@router.post("/api/runtime-mode", responses=ERROR_400_RESPONSE)
@router.post("/api/orchestrator/runtime-mode", responses=ERROR_400_RESPONSE)
def set_runtime_mode(req: RuntimeModeRequest):
    try:
        return execution_policy.set_llm_execution_mode(req.mode)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/api/llm-control")
@router.get("/api/orchestrator/llm-control")
def get_llm_control():
    return execution_policy.get_state()


@router.post("/api/llm-control", responses=ERROR_400_RESPONSE)
@router.post("/api/orchestrator/llm-control", responses=ERROR_400_RESPONSE)
def set_llm_control(req: RuntimeModeRequest):
    try:
        return execution_policy.set_llm_execution_mode(req.mode)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


# Run Now / Run Status

@router.post("/api/orchestrator/run-now")
def run_now(req: RunNowRequest):
    if req.runner not in ("planner", "worker"):
        raise HTTPException(400, "runner must be 'planner' or 'worker'")

    request_id = str(uuid.uuid4())
    triggered_at = datetime.now(timezone.utc).isoformat()
    worker_prov = db.get_worker_provider()

    if req.runner == "worker" and worker_prov == "copilot-daemon":
        daemon = copilot_daemon_status()
        if daemon.get("running"):
            return {
                "ok": True,
                "runner": req.runner,
                "pid": daemon.get("pid"),
                "mode": "delegated",
                "triggered_at": triggered_at,
                "request_id": request_id,
                "delegated_to": "copilot-daemon",
            }

    try:
        pid = _spawn_runner(req.runner, request_id)
        _spawned_pids[request_id] = pid
        return {
            "ok": True,
            "runner": req.runner,
            "pid": pid,
            "mode": "spawned",
            "triggered_at": triggered_at,
            "request_id": request_id,
        }
    except Exception as exc:
        raise HTTPException(500, f"Failed to spawn {req.runner}: {exc}") from exc


@router.get("/api/orchestrator/run-status")
def get_run_status(
    runner: Annotated[str, Query()],
    request_id: Annotated[str, Query()],
):
    run = db.get_run_by_request_id(request_id)
    if run:
        return {"status": "FINAL", "final": True, "run": dict(run)}

    pid = _spawned_pids.get(request_id)
    if _is_pid_running(pid):
        return {"status": "RUNNING", "final": False, "run": None}

    return {"status": "PENDING", "final": False, "run": None}


# Tasks

@router.get("/api/tasks")
def get_tasks(
    limit: Annotated[int, Query(le=100)] = 30,
    offset: Annotated[int, Query(ge=0)] = 0,
    status: Annotated[Optional[str], Query()] = None,
    date_folder: Annotated[Optional[str], Query()] = None,
):
    tasks = db.list_tasks(limit=limit, offset=offset, status=status, date_folder=date_folder)
    for task in tasks:
        task.update(_enrich_task(task))
        if task.get("started_at") and task.get("completed_at"):
            s = _parse_iso(task["started_at"])
            e = _parse_iso(task["completed_at"])
            if s and e:
                task["execution_time_seconds"] = int((e - s).total_seconds())
        task["changed_files_list"] = _parse_changed_files(task.get("changed_files_json"))
    return {"tasks": tasks}


@router.get("/api/orchestrator/tasks")
def get_orchestrator_tasks(
    date: Annotated[Optional[str], Query()] = None,
    status: Annotated[Optional[str], Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=50)] = 10,
):
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    date_folder = date or today
    status_filter = None if (not status or status == "ALL") else status

    total = db.count_tasks(status=status_filter, date_folder=date_folder)
    offset = (page - 1) * page_size
    tasks = db.list_tasks(limit=page_size, offset=offset, status=status_filter, date_folder=date_folder)

    for task in tasks:
        task.update(_enrich_task(task))
        if task.get("started_at") and task.get("completed_at"):
            s = _parse_iso(task["started_at"])
            e = _parse_iso(task["completed_at"])
            if s and e:
                task["duration_seconds"] = int((e - s).total_seconds())
        task["changed_files_list"] = _parse_changed_files(task.get("changed_files_json"))
        task.setdefault("planner_published_at", task.get("created_at"))
        task.setdefault("worker_completed_at", task.get("completed_at"))

    total_pages = max(1, (total + page_size - 1) // page_size)
    return {
        "tasks": tasks,
        "count": len(tasks),
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
    }


@router.get("/api/tasks/{task_id}", responses=ERROR_404_RESPONSE)
def get_task_detail(task_id: int):
    task = db.get_task(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    task = _enrich_task(task)
    result: dict = {"task": task}

    if task.get("prompt_file_path") and os.path.exists(task["prompt_file_path"]):
        with open(task["prompt_file_path"], "r", encoding="utf-8") as f:
            result["contract_text"] = f.read()

    if task.get("completed_file_path") and os.path.exists(task["completed_file_path"]):
        with open(task["completed_file_path"], "r", encoding="utf-8") as f:
            result["completed_text"] = f.read()

    task["changed_files_list"] = _parse_changed_files(task.get("changed_files_json"))
    return result


@router.get("/api/orchestrator/tasks/{task_id}", responses=ERROR_404_RESPONSE)
def get_orchestrator_task_detail(task_id: int):
    task = db.get_task(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    task = _enrich_task(task)
    result: dict = {
        "task": task,
        "prompt_text": None,
        "completed_text": None,
        "worker_stdout_tail": None,
        "task_contract": None,
        "task_result": None,
    }

    if task.get("prompt_file_path") and os.path.exists(task["prompt_file_path"]):
        with open(task["prompt_file_path"], "r", encoding="utf-8") as f:
            content = f.read()
            result["prompt_text"] = content
            result["task_contract"] = content

    if task.get("completed_file_path") and os.path.exists(task["completed_file_path"]):
        with open(task["completed_file_path"], "r", encoding="utf-8") as f:
            content = f.read()
            result["completed_text"] = content
            result["task_result"] = content

    log_dir = PROJECT_ROOT / "logs"
    stdout_log = log_dir / f"worker_task_{task_id}.log"
    if stdout_log.exists():
        lines = stdout_log.read_text(encoding="utf-8", errors="ignore").splitlines()
        result["worker_stdout_tail"] = "\n".join(lines[-200:])

    task["changed_files_list"] = _parse_changed_files(task.get("changed_files_json"))
    return result


# Runs

@router.get("/api/runs")
def get_runs(
    limit: Annotated[int, Query(le=1000)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    runs = db.list_runs(limit=limit, offset=offset)
    for run in runs:
        run["tick_type"] = run["runner"]
        run["started_at"] = run["tick_at"]
        run["finished_at"] = run.get("created_at")
        run["status"] = run["outcome"]
    return {"runs": runs}


@router.get("/api/orchestrator/runs")
def get_orchestrator_runs(
    runner: Annotated[Optional[str], Query()] = None,
    since: Annotated[Optional[str], Query()] = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 500,
    request_id: Annotated[Optional[str], Query()] = None,
):
    runs = db.list_runs_filtered(runner=runner, since=since, limit=limit, request_id=request_id)
    for run in runs:
        run["tick_type"] = run.get("runner", "")
        run["started_at"] = run.get("tick_at")
    return {"runs": runs, "count": len(runs)}


# Backlog (markdown)

@router.get("/api/orchestrator/backlog")
def get_orchestrator_backlog():
    backlog_paths = [
        PROJECT_ROOT / "backlog.md",
        PROJECT_ROOT / "docs" / "backlog.md",
        PROJECT_ROOT / "data" / "backlog.md",
    ]
    for p in backlog_paths:
        if p.exists():
            return {"content": p.read_text(encoding="utf-8"), "path": str(p)}
    return {"content": "", "path": ""}


# Legacy Run-Now (direct function call, kept for compatibility)

@router.post("/api/planner/run-now")
def run_planner_now():
    result = run_planner_tick()
    return {"ok": result.get("status") != "FAILED", "result": result}


@router.post("/api/worker/run-now")
def run_worker_now():
    result = run_worker_tick()
    return {"ok": result.get("status") != "FAILED", "result": result}


# CTO Scheduler

@router.get("/api/cto/scheduler")
@router.get("/api/orchestrator/cto/scheduler")
def get_cto_scheduler_status():
    planner_prov = db.get_setting("cto_planner_provider", "claude")
    return {
        "enabled": db.get_cto_scheduler_enabled(),
        "planner_provider": planner_prov,
        "planner_provider_label": planner_provider_label(planner_prov),
        "planner_model": db.get_setting("cto_planner_model", ""),
        "planner_options": planner_provider_options(),
    }


@router.post("/api/cto/scheduler")
@router.post("/api/orchestrator/cto/scheduler")
def set_cto_scheduler_status(req: CTOSchedulerToggleRequest):
    db.set_cto_scheduler_enabled(req.enabled)
    return {"ok": True, "enabled": req.enabled}


# CTO Providers

@router.get("/api/cto/settings")
@router.get("/api/orchestrator/cto/providers")
def get_cto_provider_config():
    return _build_cto_provider_payload()


@router.post("/api/cto/settings")
@router.post("/api/orchestrator/cto/providers", responses=ERROR_400_RESPONSE)
def set_cto_provider_config(req: CTOProviderConfigRequest):
    if req.planner_provider:
        if req.planner_provider not in {"claude", "codex"}:
            raise HTTPException(400, "CTO Planner provider 僅支援 claude / codex")
        db.set_setting("cto_planner_provider", req.planner_provider)
    if req.planner_model is not None:
        if req.planner_model and not validate_copilot_model(req.planner_model):
            raise HTTPException(400, "planner_model 格式不合法")
        db.set_setting("cto_planner_model", req.planner_model)
    return _build_cto_provider_payload()


# CTO Summary

@router.get("/api/orchestrator/cto/summary")
def get_cto_summary():
    runs = db.list_cto_review_runs(limit=1, offset=0)
    latest_run = runs[0] if runs else None
    freq_mode = db.get_setting("cto_review_frequency_mode", "once_daily")
    planner_prov = db.get_setting("cto_planner_provider", "claude")
    planner_model = db.get_setting("cto_planner_model", "")

    pending_count = db.count_tasks(status="QUEUED")
    approved_count = latest_run.get("approved_count", 0) if latest_run else 0
    merged_count = latest_run.get("merged_count", 0) if latest_run else 0
    rejected_count = latest_run.get("rejected_count", 0) if latest_run else 0

    next_run = None
    if latest_run:
        started = _parse_iso(latest_run.get("started_at") or latest_run.get("created_at"))
        if started:
            hours = 24 if freq_mode == "once_daily" else 12
            next_run = (started + timedelta(hours=hours)).isoformat()

    return {
        "frequency_mode": freq_mode,
        "scheduler_enabled": db.get_cto_scheduler_enabled(),
        "planner_provider": planner_prov,
        "planner_model": planner_model,
        "pending_count": pending_count,
        "latest_run": latest_run,
        "next_run_estimate": next_run,
        "approved_count": approved_count,
        "merged_count": merged_count,
        "rejected_count": rejected_count,
        "deferred_count": 0,
        "superseded_count": 0,
        "duplicate_count": 0,
    }


# CTO Run Now / Run Status

@router.post("/api/cto/run-now")
@router.post("/api/orchestrator/cto/run-now", responses=ERROR_429_RESPONSE)
def run_cto_now(req: CTORunNowRequest):
    if req.force:
        _check_cto_force_rate_limit()

    request_id = str(uuid.uuid4())
    triggered_at = datetime.now(timezone.utc).isoformat()

    extra_env: dict[str, str] = {}
    if req.force:
        extra_env["ORCHESTRATOR_FORCE_RERUN"] = "1"
    if req.run_intent:
        extra_env["ORCHESTRATOR_RUN_INTENT"] = req.run_intent
    if req.parent_run_id:
        extra_env["ORCHESTRATOR_PARENT_RUN_ID"] = req.parent_run_id

    try:
        pid = _spawn_runner("cto", request_id, extra_env=extra_env)
        _spawned_pids[request_id] = pid
        return {
            "ok": True,
            "runner": "cto",
            "pid": pid,
            "mode": "spawned",
            "triggered_at": triggered_at,
            "request_id": request_id,
        }
    except Exception as exc:
        raise HTTPException(500, f"Failed to spawn CTO review: {exc}") from exc


@router.get("/api/orchestrator/cto/run-status")
def get_cto_run_status(request_id: Annotated[str, Query()]):
    run = db.get_run_by_request_id(request_id)
    if run:
        return {"status": "FINAL", "final": True, "run": dict(run)}
    pid = _spawned_pids.get(request_id)
    if _is_pid_running(pid):
        return {"status": "RUNNING", "final": False, "run": None}
    return {"status": "PENDING", "final": False, "run": None}


# CTO Runs

@router.get("/api/cto/runs")
@router.get("/api/orchestrator/cto/runs")
def get_cto_runs(
    limit: Annotated[int, Query(ge=1, le=200)] = 15,
    offset: Annotated[int, Query(ge=0)] = 0,
    date: Annotated[Optional[str], Query()] = None,
    status: Annotated[Optional[str], Query()] = None,
):
    runs = db.list_cto_review_runs(limit=limit, offset=offset)
    if date:
        runs = [r for r in runs if (r.get("started_at") or "").startswith(date)]
    if status:
        runs = [r for r in runs if r.get("status") == status]

    settings = {
        "enabled": db.get_cto_scheduler_enabled(),
        "frequency_mode": db.get_setting("cto_review_frequency_mode", "once_daily"),
        "planner_provider": db.get_setting("cto_planner_provider", "claude"),
        "planner_model": db.get_setting("cto_planner_model", ""),
    }
    return {"runs": runs, "count": len(runs), "settings": settings}


@router.get("/api/cto/runs/{run_id}", responses=ERROR_404_RESPONSE)
@router.get("/api/orchestrator/cto/runs/{run_id}", responses=ERROR_404_RESPONSE)
def get_cto_run_detail(run_id: str):
    run = db.get_cto_review_run(run_id)
    if not run:
        raise HTTPException(404, "CTO run not found")
    result: dict = {"run": run, "reviews": [], "count": 0}

    if run.get("report_md_path") and os.path.exists(run["report_md_path"]):
        with open(run["report_md_path"], "r", encoding="utf-8") as f:
            result["report_md"] = f.read()

    if run.get("report_json_path") and os.path.exists(run["report_json_path"]):
        try:
            with open(run["report_json_path"], "r", encoding="utf-8") as f:
                result["report_json"] = json.load(f)
        except (json.JSONDecodeError, OSError):
            result["report_json"] = {}

    return result


# CTO Reports

@router.get("/api/orchestrator/cto/reports/{run_id}", responses=ERROR_404_RESPONSE)
def get_cto_report(run_id: str):
    run = db.get_cto_review_run(run_id)
    if not run:
        raise HTTPException(404, "CTO run not found")

    report_md = ""
    report_json: dict = {}

    if run.get("report_md_path") and os.path.exists(run["report_md_path"]):
        with open(run["report_md_path"], "r", encoding="utf-8") as f:
            report_md = f.read()

    if run.get("report_json_path") and os.path.exists(run["report_json_path"]):
        try:
            with open(run["report_json_path"], "r", encoding="utf-8") as f:
                report_json = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass

    return {"run_id": run_id, "report_md": report_md, "report_json": report_json}


# CTO Pending

@router.get("/api/orchestrator/cto/pending")
def get_cto_pending(
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    tasks = db.list_tasks(limit=limit, offset=offset, status="PENDING_REVIEW")
    items = []
    for t in tasks:
        items.append({
            "task_id": t.get("id"),
            "task_title": t.get("title") or t.get("objective"),
            "integration_group": t.get("date_folder"),
            "review_priority": "NORMAL",
            "source_branch": None,
            "commit_sha": None,
            "changed_files": _parse_changed_files(t.get("changed_files_json")),
            "depends_on_tasks": [],
            "high_conflict_paths": [],
        })
    return {"items": items, "count": len(items)}


# CTO Backlog

@router.get("/api/cto/backlog")
@router.get("/api/orchestrator/cto/backlog")
def get_cto_backlog(
    limit: Annotated[int, Query(le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    status: Annotated[Optional[str], Query()] = None,
    cto_run_id: Annotated[Optional[str], Query()] = None,
):
    items = db.list_backlog_items(limit=limit, offset=offset, status=status)
    if cto_run_id:
        items = [i for i in items if i.get("cto_run_id") == cto_run_id]

    for item in items:
        linked_task_id = item.get("agent_task_id")
        if linked_task_id:
            task = db.get_task(int(linked_task_id))
            if task:
                status_map = {
                    "QUEUED": "queued", "RUNNING": "running",
                    "COMPLETED": "completed", "FAILED": "failed",
                }
                item["live_status"] = status_map.get(task.get("status", ""), "queued")
            else:
                item["live_status"] = "queued"
        else:
            item["live_status"] = None

    return {"items": items, "count": len(items)}


@router.get("/api/orchestrator/cto/backlog/prioritized")
def get_cto_backlog_prioritized(
    limit: Annotated[int, Query(le=200)] = 200,
    cto_run_id: Annotated[Optional[str], Query()] = None,
):
    items = db.list_backlog_items(limit=limit, offset=0)
    if cto_run_id:
        items = [i for i in items if i.get("cto_run_id") == cto_run_id]

    level_counts = {"P0": 0, "P1": 0, "P2": 0, "P3": 0}
    for item in items:
        score = item.get("priority_score", 0)
        sev = item.get("severity", "LOW")
        if sev == "CRITICAL" or score >= 90:
            item["priority_level"] = "P0"
        elif sev == "HIGH" or score >= 60:
            item["priority_level"] = "P1"
        elif sev == "MEDIUM" or score >= 30:
            item["priority_level"] = "P2"
        else:
            item["priority_level"] = "P3"
        level_counts[item["priority_level"]] += 1

    items.sort(key=lambda x: x.get("priority_score", 0), reverse=True)
    return {"items": items, "count": len(items), "level_counts": level_counts}


@router.post("/api/cto/backlog")
@router.post("/api/orchestrator/cto/backlog")
def create_cto_backlog_item(req: BacklogCreateRequest):
    severity_scores = {"CRITICAL": 100, "HIGH": 70, "MEDIUM": 40, "LOW": 15}
    urgency_scores = {"IMMEDIATE": 100, "HIGH": 80, "MEDIUM": 50, "LOW": 20}
    priority_score = int(
        severity_scores.get(req.severity, 15) * 0.6
        + urgency_scores.get(req.urgency, 20) * 0.4
    )
    item_id = db.create_backlog_item(
        finding_id=req.finding_id,
        cto_run_id=req.cto_run_id,
        severity=req.severity,
        urgency=req.urgency,
        category=req.category,
        title=req.title,
        description=req.description,
        file_path=req.file_path,
        line_number=req.line_number,
        priority_score=priority_score,
    )
    return {"ok": True, "item_id": item_id}


@router.post("/api/orchestrator/cto/backlog/batch")
def create_cto_backlog_batch(req: BacklogBatchRequest):
    severity_order = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
    min_sev_rank = severity_order.get(req.min_severity, 3)

    run = db.get_cto_review_run(req.cto_run_id)
    if not run:
        raise HTTPException(404, "CTO run not found")

    report_json: dict = {}
    if run.get("report_json_path") and os.path.exists(run["report_json_path"]):
        try:
            with open(run["report_json_path"], "r", encoding="utf-8") as f:
                report_json = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass

    decisions = report_json.get("decisions", [])
    created_ids = []

    for dec in decisions:
        sev = (dec.get("scoring") or {}).get("severity", "LOW")
        impact = (dec.get("scoring") or {}).get("impact_score", 0)
        if severity_order.get(sev, 1) < min_sev_rank:
            continue
        if impact < req.min_impact:
            continue

        task_id = dec.get("task_id", "unknown")
        finding_id = f"{req.cto_run_id}__t{task_id}_{sev}"

        try:
            item_id = db.create_backlog_item(
                finding_id=finding_id,
                cto_run_id=req.cto_run_id,
                severity=sev,
                urgency=(dec.get("scoring") or {}).get("urgency", "MEDIUM"),
                category=dec.get("category", "general"),
                title=dec.get("reason", "Finding")[:200],
                description=json.dumps(dec, ensure_ascii=False),
                file_path=None,
                line_number=None,
                priority_score=int(impact),
            )
            created_ids.append(item_id)
        except Exception:
            pass

    return {"ok": True, "created_count": len(created_ids), "item_ids": created_ids}


# CTO Adaptive Policy

@router.get("/api/orchestrator/cto/adaptive-policy")
def get_adaptive_policy():
    policy_raw = db.get_setting("cto_adaptive_policy", "")
    policy: dict = {}
    if policy_raw:
        try:
            policy = json.loads(policy_raw)
        except json.JSONDecodeError:
            pass

    intent_stats = {
        "retry": {"runs": 0, "success_rate": 0.0, "description": "重試失敗提交，包含 REPLAN/CONFLICT 候選"},
        "compare": {"runs": 0, "success_rate": 0.0, "description": "比對分析模式，不執行合併和 backlog 寫入"},
        "override": {"runs": 0, "success_rate": 0.0, "description": "強制覆蓋，正常行為"},
    }

    return {
        "policy": policy,
        "intent_stats": intent_stats,
        "confidence_levels": {
            "high": ">=10 runs analyzed + >=5 intent runs",
            "medium": ">=5 runs analyzed",
            "low": "<5 runs analyzed",
        },
    }


@router.post("/api/orchestrator/cto/adaptive-policy/refresh")
def refresh_adaptive_policy():
    runs = db.list_cto_review_runs(limit=100, offset=0)
    policy = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "total_runs_analyzed": len(runs),
        "recommendation": "once_daily" if len(runs) < 10 else "twice_daily",
    }
    db.set_setting("cto_adaptive_policy", json.dumps(policy))
    return {"ok": True, "policy": policy}


# ── Usage Card ───────────────────────────────────────────────────────────────


@router.get("/api/orchestrator/usage")
def get_usage_summary(hours: int = 24, tail: int = 10):
    """
    Usage Card — 全 AI / GitHub 外部呼叫統計。

    Query params:
        hours: 時間窗口（預設 24 小時；0 = 無限制）
        tail:  recent 表格筆數（預設 10）

    回傳欄位：
        total, allowed, blocked, malformed, rate_limited,
        by_role, by_provider, block_reasons, tokens, recent
    """
    from orchestrator.usage_reader import read_usage_records, build_usage_summary
    records = read_usage_records(hours=hours)
    summary = build_usage_summary(records, recent_n=tail)
    summary["hours"] = hours
    return summary


# App Factory

def create_api_app() -> FastAPI:
    app = FastAPI(
        title="Betting-pool Orchestrator API",
        description="Task Orchestration + CTO Review API",
        version="2.0.0",
    )
    app.include_router(router, tags=["Orchestrator"])
    return app


def run_api_server(
    profile_path: Optional[str] = None,
    host: str = "127.0.0.1",
    port: int = 8787,
) -> None:
    _ = profile_path
    db.init_db()
    uvicorn.run(create_api_app(), host=host, port=port, log_level="info")
