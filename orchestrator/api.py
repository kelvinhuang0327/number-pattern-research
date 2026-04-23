"""
Orchestrator FastAPI routes.
Mount in your app: app.include_router(orchestrator.api.router, tags=["Orchestrator"])
"""

import os
import glob
import sys
import json
import uuid
import subprocess
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional

from orchestrator import db, common

router = APIRouter()
TASK_STATUSES = ("QUEUED", "RUNNING", "COMPLETED", "FAILED", "REPLAN_REQUIRED", "CANCELLED")


def _parse_iso(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(str(ts))
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _tail_lines(path: str, lines: int = 200) -> str:
    if not path or not os.path.exists(path):
        return ""
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return "".join(f.readlines()[-lines:])
    except OSError:
        return ""


def _read_text(path: Optional[str]) -> Optional[str]:
    if not path or not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except OSError:
        return None


def _read_json(path: Optional[str]) -> Optional[dict]:
    text = _read_text(path)
    if not text:
        return None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _estimate_next_tick_at(runs: list[dict], runner: str, interval_minutes: int = 10) -> Optional[str]:
    latest = None
    for row in runs:
        if row.get("runner") == runner:
            latest = row
            break
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
        next_dt = next_dt + (interval * missed)
    return next_dt.isoformat()


def _normalize_date_filter(value: Optional[str]) -> Optional[str]:
    if value is None or not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw:
        return None
    if len(raw) == 10 and raw[4] == "-" and raw[7] == "-":
        return raw.replace("-", "")
    if len(raw) == 8 and raw.isdigit():
        return raw
    return None


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
    task["worker_model"] = meta.get("worker_model")
    task["worker_execution_mode"] = meta.get("worker_execution_mode")
    task["worker_fallback_reason"] = meta.get("worker_fallback_reason")
    task["task_contract_path"] = meta.get("task_contract_path")
    task["task_result_path"] = meta.get("task_result_path")
    task["gate_verdict"] = meta.get("gate_verdict")
    task["gate_reason"] = meta.get("gate_reason")
    progress = common.read_worker_progress(slot_key, date_folder)
    task["worker_log_path"] = progress.get("worker_log_path")
    task["last_output_at"] = progress.get("last_output_at")
    task["last_progress_summary"] = progress.get("last_progress_summary")

    # Derive contract/result paths when meta keys are absent.
    slug = task.get("slug") or "task"
    if not task.get("task_contract_path"):
        task["task_contract_path"] = common.contract_path(slot_key, slug, date_folder)
    if not task.get("task_result_path"):
        task["task_result_path"] = common.result_path(slot_key, slug, date_folder)

    result_json = _read_json(task.get("task_result_path"))
    if result_json:
        task["gate_verdict"] = task.get("gate_verdict") or result_json.get("gate_verdict")
        task["gate_reason"] = task.get("gate_reason") or result_json.get("gate_reason")
        worker_runtime = result_json.get("worker_runtime")
        if isinstance(worker_runtime, dict):
            runtime_error = str(worker_runtime.get("runtime_error") or "").strip()
            if runtime_error and not task.get("error_message"):
                task["error_message"] = runtime_error
        if not task.get("changed_files_json"):
            changed = result_json.get("changed_files", [])
            task["changed_files_json"] = json.dumps(changed, ensure_ascii=False)

    progress_view = common.classify_worker_progress(
        status=task.get("status"),
        last_output_at=task.get("last_output_at"),
        worker_runtime=task.get("worker_runtime"),
    )
    progress_state = str(progress_view.get("progress_state") or "").lower()
    progress_state_code = {
        "active": "RUNNING_ACTIVE",
        "stale": "STUCK_SUSPECTED",
        "no_output": "RUNNING_NO_OUTPUT",
        "not_running": "NOT_RUNNING",
    }.get(progress_state)
    task["progress_state"] = progress_state
    task["progress_state_code"] = progress_state_code
    task["progress_note"] = progress_view.get("progress_note")
    task["last_output_age_seconds"] = progress_view.get("progress_idle_seconds")
    task["progress_stale"] = progress_view.get("progress_stale")

    task["planner_published_at"] = task.get("created_at")
    task["worker_completed_at"] = task.get("completed_at")
    return _attach_git_review_fields(task)


def _attach_git_review_fields(task: dict) -> dict:
    git_commit = db.get_task_git_commit_for_task(task.get("id"))
    if not git_commit:
        return task

    task["commit_sha"] = git_commit.get("commit_sha")
    task["source_branch"] = git_commit.get("source_branch")
    task["review_status"] = git_commit.get("status")
    task["reviewed_at"] = git_commit.get("reviewed_at")
    task["merge_branch"] = git_commit.get("merge_branch")
    task["merge_commit_sha"] = git_commit.get("merge_commit_sha")
    task["reject_reason"] = git_commit.get("reject_reason")
    task["integration_group"] = git_commit.get("integration_group")
    task["review_priority"] = git_commit.get("review_priority")
    task["safe_to_autocommit"] = bool(git_commit.get("safe_to_autocommit"))
    task["git_commit"] = git_commit

    commit_sha = git_commit.get("commit_sha")
    if commit_sha:
        git_review = db.get_task_git_review_for_commit(commit_sha)
        if git_review:
            task["review_decision"] = git_review.get("decision")
            task["review_run_id"] = git_review.get("review_run_id")
            task["review_summary"] = git_review.get("review_summary")
    return task


@router.get("/api/orchestrator/summary")
def get_summary():
    """Today's task stats + worker status."""
    today = datetime.now().strftime("%Y%m%d")
    counts = {status: 0 for status in TASK_STATUSES}
    counts.update(db.count_tasks_by_status(date_folder=today))

    lock = db.get_worker_lock()
    worker_busy = False
    worker_pid = None
    worker_task_id = None
    if lock and lock["pid"] and common.is_process_alive(lock["pid"]):
        worker_busy = True
        worker_pid = lock["pid"]
        worker_task_id = lock["task_id"]

    recent_runs = db.list_runs(limit=500)
    outcome_dist = {}
    for r in recent_runs:
        outcome_dist[r["outcome"]] = outcome_dist.get(r["outcome"], 0) + 1

    daemon_status = common.copilot_daemon_status()
    worker_provider = db.get_worker_provider()

    if worker_provider == "copilot-daemon":
        daemon_mode = str(daemon_status.get("status") or "").lower()
        if worker_busy or daemon_mode in ("busy", "claiming", "finalizing"):
            worker_state = "執行中"
        elif daemon_status.get("running"):
            worker_state = "待命中"
        else:
            worker_state = "未啟動"
    else:
        worker_state = f"忙碌 (PID {worker_pid})" if worker_busy else "閒置"

    next_planner = _estimate_next_tick_at(db.list_runs(runner="planner", limit=1), "planner", 10)
    next_worker = _estimate_next_tick_at(db.list_runs(runner="worker", limit=1), "worker", 10)

    return {
        "today": today,
        "scheduler_enabled": db.is_scheduler_enabled(),
        "planner_provider": db.get_planner_provider(),
        "planner_provider_label": common.planner_provider_label(db.get_planner_provider()),
        "worker_provider": worker_provider,
        "worker_provider_label": common.worker_provider_label(worker_provider),
        "combo_label": common.planner_worker_combo_label(
            db.get_planner_provider(),
            worker_provider,
        ),
        "task_counts": counts,
        "total_today": db.count_tasks(date_folder=today),
        "worker_busy": worker_busy,
        "worker_pid": worker_pid,
        "worker_task_id": worker_task_id,
        "worker_state": worker_state,
        "copilot_daemon_running": daemon_status.get("running", False),
        "copilot_daemon_pid": daemon_status.get("pid"),
        "copilot_daemon_status": daemon_status.get("status"),
        "copilot_daemon_task_id": daemon_status.get("current_task_id"),
        "recent_run_outcomes": outcome_dist,
        "next_planner_tick_estimate": next_planner,
        "next_worker_tick_estimate": next_worker,
    }


class SchedulerToggleRequest(BaseModel):
    enabled: bool


class ProviderConfigRequest(BaseModel):
    planner_provider: Optional[str] = None
    worker_provider: Optional[str] = None
    worker_copilot_model: Optional[str] = None


class RunNowRequest(BaseModel):
    runner: str


class CtoSchedulerToggleRequest(BaseModel):
    enabled: bool


class CtoProviderConfigRequest(BaseModel):
    planner_provider: Optional[str] = None
    planner_model: Optional[str] = None


def _estimate_cto_next_run_at(latest_run: Optional[dict]) -> Optional[str]:
    if not latest_run:
        return None
    dt = _parse_iso(latest_run.get("completed_at") or latest_run.get("started_at"))
    if not dt:
        return None
    frequency_mode = str(latest_run.get("frequency_mode") or db.get_cto_review_frequency_mode()).strip().lower()
    interval = timedelta(hours=12 if frequency_mode == "twice_daily" else 24)
    next_dt = dt + interval
    now = datetime.now(timezone.utc)
    if next_dt <= now:
        elapsed = now - next_dt
        missed = int(elapsed.total_seconds() // interval.total_seconds()) + 1
        next_dt = next_dt + (interval * missed)
    return next_dt.isoformat()


def _matches_local_date(ts: Optional[str], date_folder: Optional[str]) -> bool:
    normalized_date = _normalize_date_filter(date_folder)
    if not normalized_date:
        return True
    dt = _parse_iso(ts)
    if not dt:
        return False
    local_date = dt.astimezone(timezone(timedelta(hours=8))).strftime("%Y%m%d")
    return local_date == normalized_date


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
    worker_copilot_model = db.get_worker_copilot_model()
    return {
        "planner_provider": planner_provider,
        "planner_provider_label": common.planner_provider_label(planner_provider),
        "worker_provider": worker_provider,
        "worker_provider_label": common.worker_provider_label(worker_provider),
        "combo_label": common.planner_worker_combo_label(planner_provider, worker_provider),
        "planner_options": common.planner_provider_options(),
        "worker_options": common.worker_provider_options(),
        "worker_copilot_model": worker_copilot_model,
        "worker_copilot_model_presets": common.COPILOT_MODEL_PRESETS,
    }


@router.post("/api/orchestrator/providers")
def set_provider_config(req: ProviderConfigRequest):
    planner_provider = common.normalize_planner_provider(req.planner_provider or db.get_planner_provider())
    worker_provider = common.normalize_worker_provider(req.worker_provider or db.get_worker_provider())
    worker_copilot_model_raw = str(req.worker_copilot_model or "").strip()
    model_ok, worker_copilot_model, model_reason = common.validate_copilot_model(worker_copilot_model_raw)
    if not model_ok:
        raise HTTPException(status_code=400, detail=model_reason)

    planner_ok, planner_reason = common.provider_available("planner", planner_provider)
    if not planner_ok:
        raise HTTPException(status_code=400, detail=f"Planner provider unavailable: {planner_reason}")

    worker_ok, worker_reason = common.provider_available("worker", worker_provider)
    if not worker_ok:
        raise HTTPException(status_code=400, detail=f"Worker provider unavailable: {worker_reason}")

    db.set_planner_provider(planner_provider)
    db.set_worker_provider(worker_provider)
    db.set_worker_copilot_model(worker_copilot_model)

    combo_label = common.planner_worker_combo_label(planner_provider, worker_provider)
    db.log_tick(
        "orchestrator",
        "PROVIDERS_UPDATED",
        message=(
            f"Provider combo set to {combo_label}"
            + (f" | Copilot model={worker_copilot_model}" if worker_copilot_model else "")
        ),
    )
    return {
        "planner_provider": planner_provider,
        "planner_provider_label": common.planner_provider_label(planner_provider),
        "worker_provider": worker_provider,
        "worker_provider_label": common.worker_provider_label(worker_provider),
        "combo_label": combo_label,
        "worker_copilot_model": worker_copilot_model,
        "worker_copilot_model_presets": common.COPILOT_MODEL_PRESETS,
    }


@router.post("/api/orchestrator/run-now")
def run_now(req: RunNowRequest):
    runner = (req.runner or "").strip().lower()
    if runner not in ("planner", "worker"):
        raise HTTPException(status_code=400, detail="runner must be planner or worker")
    triggered_at = datetime.now(timezone.utc).isoformat()
    request_id = uuid.uuid4().hex

    if runner == "worker" and db.get_worker_provider() == "copilot-daemon":
        daemon_status = common.copilot_daemon_status()
        if daemon_status.get("running"):
            db.log_tick("worker", "WORKER_MANUAL_DELEGATED", message=f"worker run-now delegated to copilot-daemon pid={daemon_status.get('pid')}", request_id=request_id)
            return {
                "ok": True,
                "runner": runner,
                "pid": daemon_status.get("pid"),
                "mode": "delegated",
                "delegated_to": "copilot-daemon",
                "message": "Worker run-now delegated to resident copilot daemon",
                "triggered_at": triggered_at,
                "request_id": request_id,
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
    env["ORCHESTRATOR_REQUEST_ID"] = request_id
    proc = subprocess.Popen(
        [sys.executable, script_path, *extra_args],
        cwd=common.ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    outcome = "PLANNER_MANUAL_TRIGGERED" if runner == "planner" else "WORKER_MANUAL_TRIGGERED"
    db.log_tick(runner, outcome, message=f"{runner} run-now triggered, pid={proc.pid}", request_id=request_id)
    return {
        "ok": True,
        "runner": runner,
        "pid": proc.pid,
        "mode": "spawned",
        "triggered_at": triggered_at,
        "request_id": request_id,
    }


@router.get("/api/orchestrator/tasks")
def list_tasks(
    date: str = Query(None, description="YYYYMMDD"),
    status: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
):
    try:
        safe_page = int(page)
    except (TypeError, ValueError):
        safe_page = 1
    if safe_page < 1:
        safe_page = 1

    try:
        safe_page_size = int(page_size)
    except (TypeError, ValueError):
        safe_page_size = 10
    if safe_page_size < 1:
        safe_page_size = 10
    safe_page_size = min(safe_page_size, 50)

    normalized_date = _normalize_date_filter(date)
    status_raw = status if isinstance(status, str) else ""
    normalized_status = status_raw.strip().upper()
    if normalized_status in ("", "ALL"):
        effective_status = None
    else:
        if normalized_status not in TASK_STATUSES:
            raise HTTPException(status_code=400, detail=f"invalid status: {status}")
        effective_status = normalized_status

    offset = (safe_page - 1) * safe_page_size
    total = db.count_tasks(date_folder=normalized_date, status=effective_status)
    tasks = db.list_tasks(date_folder=normalized_date, status=effective_status, limit=safe_page_size, offset=offset)
    tasks = [_attach_task_meta_fields(dict(task)) for task in tasks]
    total_pages = max(1, (total + safe_page_size - 1) // safe_page_size)
    return {
        "tasks": tasks,
        "count": len(tasks),
        "page": safe_page,
        "page_size": safe_page_size,
        "total": total,
        "total_pages": total_pages,
    }


@router.get("/api/orchestrator/run-status")
def get_run_status(
    runner: str = Query(..., description="planner or worker"),
    request_id: str = Query(..., min_length=4),
):
    safe_runner = str(runner or "").strip().lower()
    if safe_runner not in ("planner", "worker"):
        raise HTTPException(status_code=400, detail="runner must be planner or worker")

    runs = db.list_runs(runner=safe_runner, request_id=request_id, limit=50)
    if not runs:
        return {"runner": safe_runner, "request_id": request_id, "status": "PENDING", "final": False, "run": None}

    terminal_outcomes = {
        "planner": {
            "PLANNER_PRODUCED",
            "PLANNER_SKIP_PROVIDER_FAILURE",
            "PLANNER_SKIP_PREV_RUNNING",
            "PLANNER_SKIP_DISABLED",
            "PLANNER_SKIP_NO_BACKLOG",
            "PLANNER_INVALID_CONTRACT",
        },
        "worker": {
            "WORKER_FINALIZED",
            "WORKER_SKIP_DISABLED",
            "WORKER_SKIP_IDLE_NO_TASK",
            "WORKER_SKIP_DAEMON_PROVIDER",
        },
    }
    final_run = next((run for run in runs if run.get("outcome") in terminal_outcomes[safe_runner]), None)
    if final_run:
        return {"runner": safe_runner, "request_id": request_id, "status": "FINAL", "final": True, "run": final_run}
    return {"runner": safe_runner, "request_id": request_id, "status": "RUNNING", "final": False, "run": runs[0]}




def _resolve_artifact_path(task: dict, artifact: str, explicit_path: Optional[str]) -> Optional[str]:
    if explicit_path and os.path.exists(explicit_path):
        return explicit_path

    slot_key = task.get("slot_key")
    date_folder = task.get("date_folder")
    slug = str(task.get("slug") or "").strip()
    if not slot_key or not date_folder:
        return explicit_path

    candidates = []
    if slug:
        if artifact == "contract":
            candidates.append(common.contract_path(slot_key, slug, date_folder))
        elif artifact == "result":
            candidates.append(common.result_path(slot_key, slug, date_folder))

    pattern = os.path.join(common.TASKS_ROOT, date_folder, f"{slot_key}-{artifact}-*.json")
    candidates.extend(sorted(glob.glob(pattern)))

    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return candidate
    return explicit_path


@router.get("/api/orchestrator/tasks/{task_id}")
def get_task(task_id: int):
    task = db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task = _attach_task_meta_fields(dict(task))

    # Attach worker stdout tail (last 200 lines)
    slot_key = task["slot_key"]
    date_folder = task["date_folder"]
    log_path = common.find_stdout_log_path(slot_key, date_folder)
    worker_tail = _tail_lines(log_path, lines=200)
    contract_path = _resolve_artifact_path(task, "contract", task.get("task_contract_path"))
    result_path = _resolve_artifact_path(task, "result", task.get("task_result_path"))
    task_contract = _read_text(contract_path)
    task_result = _read_text(result_path)

    prompt_path = task.get("prompt_file_path")
    completed_path = task.get("completed_file_path")
    if not (prompt_path and os.path.exists(prompt_path)):
        prompt_candidates = sorted(glob.glob(os.path.join(common.TASKS_ROOT, date_folder, f"{slot_key}-prompt-*.md")))
        prompt_path = prompt_candidates[0] if prompt_candidates else prompt_path
    if not (completed_path and os.path.exists(completed_path)):
        completed_candidates = sorted(glob.glob(os.path.join(common.TASKS_ROOT, date_folder, f"{slot_key}-completed-*.md")))
        completed_path = completed_candidates[0] if completed_candidates else completed_path

    prompt_text = task.get("prompt_text") or _read_text(prompt_path) or ""
    completed_text = task.get("completed_text") or _read_text(completed_path) or ""

    return {
        **task,
        "prompt_text": prompt_text,
        "completed_text": completed_text,
        "codex_stdout_tail": worker_tail,
        "worker_stdout_tail": worker_tail,
        "task_contract": task_contract,
        "task_result": task_result,
        "task_contract_path": contract_path,
        "task_result_path": result_path,
        "prompt_file_path": prompt_path,
        "completed_file_path": completed_path,
    }


@router.get("/api/orchestrator/runs")
def list_runs(
    runner: str = Query(None, description="planner or worker"),
    since: str = Query(None, description="ISO datetime"),
    limit: int = Query(200, ge=1, le=1000),
    request_id: str = Query(None, description="manual run request id"),
):
    safe_runner = runner if isinstance(runner, str) else None
    safe_since = since if isinstance(since, str) else None
    safe_request_id = request_id if isinstance(request_id, str) and request_id.strip() else None
    try:
        safe_limit = int(limit)
    except (TypeError, ValueError):
        safe_limit = 200
    safe_limit = min(max(safe_limit, 1), 1000)
    runs = db.list_runs(runner=safe_runner, since=safe_since, limit=safe_limit, request_id=safe_request_id)
    return {"runs": runs, "count": len(runs)}


@router.get("/api/orchestrator/backlog")
def get_backlog():
    content = common.read_backlog()
    return {"content": content, "path": common.BACKLOG_PATH}


@router.get("/api/orchestrator/cto/summary")
def get_cto_summary():
    latest_run = db.get_latest_cto_review_run()
    pending_count = db.count_task_git_commits(status="PENDING_REVIEW")
    latest_run_payload = latest_run or {}
    cto_planner_provider = db.get_cto_planner_provider()
    return {
        "frequency_mode": db.get_cto_review_frequency_mode(),
        "scheduler_enabled": db.is_cto_scheduler_enabled(),
        "planner_provider": cto_planner_provider,
        "planner_provider_label": common.planner_provider_label(cto_planner_provider),
        "planner_model": db.get_cto_planner_model(),
        "pending_count": pending_count,
        "latest_run": latest_run_payload,
        "next_run_estimate": _estimate_cto_next_run_at(latest_run_payload) if latest_run_payload else None,
        "approved_count": latest_run_payload.get("approved_count", 0) if latest_run_payload else 0,
        "merged_count": latest_run_payload.get("merged_count", 0) if latest_run_payload else 0,
        "rejected_count": latest_run_payload.get("rejected_count", 0) if latest_run_payload else 0,
        "deferred_count": latest_run_payload.get("deferred_count", 0) if latest_run_payload else 0,
        "superseded_count": latest_run_payload.get("superseded_count", 0) if latest_run_payload else 0,
        "duplicate_count": latest_run_payload.get("duplicate_count", 0) if latest_run_payload else 0,
    }


@router.get("/api/orchestrator/cto/pending")
def list_cto_pending_commits(limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0)):
    rows = db.list_task_git_commits(status="PENDING_REVIEW", limit=limit, offset=offset)
    rows = [
        {
            **row,
            "changed_files": json.loads(row["changed_files_json"]) if row.get("changed_files_json") else [],
            "depends_on_tasks": json.loads(row["depends_on_tasks_json"]) if row.get("depends_on_tasks_json") else [],
            "depends_on_commits": json.loads(row["depends_on_commits_json"]) if row.get("depends_on_commits_json") else [],
            "high_conflict_paths": json.loads(row["high_conflict_paths_json"]) if row.get("high_conflict_paths_json") else [],
        }
        for row in rows
    ]
    return {"commits": rows, "count": len(rows)}


@router.get("/api/orchestrator/cto/reviews")
def list_cto_git_reviews(limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0)):
    reviews = db.list_task_git_reviews(limit=limit, offset=offset)
    return {"reviews": reviews, "count": len(reviews)}


@router.get("/api/orchestrator/cto/scheduler")
def get_cto_scheduler_status():
    cto_planner_provider = db.get_cto_planner_provider()
    return {
        "enabled": db.is_cto_scheduler_enabled(),
        "planner_provider": cto_planner_provider,
        "planner_provider_label": common.planner_provider_label(cto_planner_provider),
        "planner_model": db.get_cto_planner_model(),
        "planner_options": common.planner_provider_options(),
    }


@router.post("/api/orchestrator/cto/scheduler")
def set_cto_scheduler_status(req: CtoSchedulerToggleRequest):
    db.set_cto_scheduler_enabled(req.enabled)
    state = "ENABLED" if req.enabled else "DISABLED"
    db.log_tick("cto-review", f"CTO_SCHEDULER_{state}", message=f"CTO Scheduler set to {state}")
    return {"enabled": req.enabled}


@router.get("/api/orchestrator/cto/providers")
def get_cto_provider_config():
    cto_planner_provider = db.get_cto_planner_provider()
    return {
        "planner_provider": cto_planner_provider,
        "planner_provider_label": common.planner_provider_label(cto_planner_provider),
        "planner_options": common.planner_provider_options(),
        "planner_model": db.get_cto_planner_model(),
        "planner_model_presets": common.COPILOT_MODEL_PRESETS,
    }


@router.post("/api/orchestrator/cto/providers")
def set_cto_provider_config(req: CtoProviderConfigRequest):
    planner_provider = common.normalize_planner_provider(req.planner_provider or db.get_cto_planner_provider())
    planner_model_raw = str(req.planner_model or "").strip()
    model_ok, planner_model, model_reason = common.validate_copilot_model(planner_model_raw)
    if not model_ok:
        raise HTTPException(status_code=400, detail=model_reason)
    planner_ok, planner_reason = common.provider_available("planner", planner_provider)
    if not planner_ok:
        raise HTTPException(status_code=400, detail=f"CTO Planner provider unavailable: {planner_reason}")
    db.set_cto_planner_provider(planner_provider)
    db.set_cto_planner_model(planner_model)
    db.log_tick(
        "cto-review",
        "CTO_PROVIDERS_UPDATED",
        message=(
            f"CTO Planner provider set to {planner_provider}"
            + (f" | model={planner_model}" if planner_model else "")
        ),
    )
    return {
        "planner_provider": planner_provider,
        "planner_provider_label": common.planner_provider_label(planner_provider),
        "planner_model": planner_model,
        "planner_model_presets": common.COPILOT_MODEL_PRESETS,
    }


@router.post("/api/orchestrator/cto/run-now")
def cto_run_now():
    request_id = uuid.uuid4().hex
    triggered_at = datetime.now(timezone.utc).isoformat()
    script_path = os.path.join(common.ROOT, "orchestrator", "cto_review_tick.py")
    if not os.path.exists(script_path):
        raise HTTPException(status_code=500, detail="cto_review_tick.py not found")
    env = os.environ.copy()
    env["ORCHESTRATOR_FORCE_RUN"] = "1"
    env["ORCHESTRATOR_REQUEST_ID"] = request_id
    proc = subprocess.Popen(
        [sys.executable, script_path],
        cwd=common.ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    db.log_tick(
        "cto-review",
        "CTO_REVIEW_MANUAL_TRIGGERED",
        message=f"CTO review run-now triggered, pid={proc.pid}",
        request_id=request_id,
    )
    return {
        "ok": True,
        "pid": proc.pid,
        "triggered_at": triggered_at,
        "request_id": request_id,
    }


@router.get("/api/orchestrator/cto/run-status")
def get_cto_run_status(request_id: str = Query(..., min_length=4)):
    runs = db.list_runs(runner="cto-review", request_id=request_id, limit=50)
    terminal_outcomes = {
        "CTO_REVIEW_COMPLETED",
        "CTO_REVIEW_SKIP_DISABLED",
        "CTO_REVIEW_SKIP_FREQUENCY",
        "CTO_REVIEW_NO_CANDIDATES",
        "CTO_REVIEW_ERROR",
    }
    if not runs:
        return {"request_id": request_id, "status": "PENDING", "final": False, "run": None}
    final_run = next((run for run in runs if run.get("outcome") in terminal_outcomes), None)
    if final_run:
        return {"request_id": request_id, "status": "FINAL", "final": True, "run": final_run}
    return {"request_id": request_id, "status": "RUNNING", "final": False, "run": runs[0]}


@router.get("/api/orchestrator/cto/runs")
def list_cto_review_runs(limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0), date: str = Query(None, description="YYYYMMDD"), status: str = Query(None, description="RUNNING|COMPLETED|SKIPPED")):
    runs = db.list_cto_review_runs(limit=500, offset=0)
    if date:
        runs = [row for row in runs if _matches_local_date(row.get("started_at"), date) or _matches_local_date(row.get("completed_at"), date)]
    if status:
        status_upper = status.strip().upper()
        if status_upper == "RUNNING":
            runs = [r for r in runs if not r.get("completed_at")]
        elif status_upper == "COMPLETED":
            runs = [r for r in runs if r.get("completed_at") and (r.get("candidate_count") or 0) > 0]
        elif status_upper == "SKIPPED":
            runs = [r for r in runs if r.get("completed_at") and (r.get("candidate_count") or 0) == 0]
    runs = runs[offset: offset + limit]
    return {"runs": runs, "count": len(runs)}


@router.get("/api/orchestrator/cto/runs/{run_id}")
def get_cto_review_run_detail(run_id: str):
    run = db.get_cto_review_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="CTO review run not found")
    reviews = db.list_task_git_reviews(review_run_id=run_id, limit=500, offset=0)
    return {"run": run, "reviews": reviews, "count": len(reviews)}


@router.get("/api/orchestrator/cto/reports/{run_id}")
def get_cto_review_report(run_id: str):
    run = db.get_cto_review_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="CTO review run not found")
    md_path = run.get("report_md_path")
    json_path = run.get("report_json_path")
    report_md = _read_text(md_path)
    report_json = _read_json(json_path)
    return {
        "run_id": run_id,
        "report_md_path": md_path,
        "report_json_path": json_path,
        "report_md": report_md,
        "report_json": report_json,
    }
