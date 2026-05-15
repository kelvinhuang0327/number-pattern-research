"""
Orchestrator FastAPI routes.
Mount in your app: app.include_router(orchestrator.api.router, tags=["Orchestrator"])
"""

import os
import glob
import sys
import json
import uuid
import logging
import subprocess
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional

from orchestrator import db, common, execution_policy
from orchestrator.process_watchdog import watchdog as _proc_watchdog

# Max runtimes for subprocess types (seconds)
_WORKER_TIMEOUT_S  = 1800   # 30 min: planner / worker tick
_CTO_TIMEOUT_S     = 1800   # 30 min: CTO review tick

router = APIRouter()
logger = logging.getLogger(__name__)
TASK_STATUSES = (
    "QUEUED",
    "RUNNING",
    "COMPLETED",
    "FAILED",
    "FAILED_ACCEPTANCE",
    "FAILED_RATE_LIMIT",
    "FAILED_NO_EDGE",
    "FAILED_WEAK_EDGE",
    "BLOCKED_ENV",
    "REPLAN_REQUIRED",
    "CANCELLED",
)


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
    # planner_agent_label: prefer DB column (already in SELECT *), fall back to computed from meta
    if not task.get("planner_agent_label"):
        _pp = meta.get("planner_provider") or ""
        task["planner_agent_label"] = common.normalize_llm_agent_label(_pp)["display_label"] if _pp else "Local"
    task["worker_provider"] = meta.get("worker_provider")
    task["worker_requested_provider"] = meta.get("worker_requested_provider")
    task["worker_runtime"] = meta.get("worker_runtime")
    task["worker_model"] = meta.get("worker_model")
    # worker_agent_label: prefer DB column, fall back to computed from meta
    if not task.get("worker_agent_label"):
        _wp = meta.get("worker_provider") or ""
        _wm = meta.get("worker_model") or ""
        task["worker_agent_label"] = common.normalize_llm_agent_label(_wp, _wm)["display_label"] if _wp else None
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
        task["failure_reason"] = task.get("failure_reason") or result_json.get("failure_reason")
        task["failure_provider"] = task.get("failure_provider") or result_json.get("provider")
        task["reset_hint"] = task.get("reset_hint") or result_json.get("reset_hint")
        task["final_message"] = task.get("final_message") or result_json.get("final_message")
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
    llm_control = _llm_control_payload()

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

    # Compute run-state badge for the active worker task
    worker_run_state_badge = None
    worker_eta_seconds = None
    worker_subtask = None
    if worker_busy and worker_task_id:
        running_task = db.get_task(worker_task_id)
        if running_task:
            worker_run_state_badge = common.classify_task_run_state(running_task)
            worker_eta_seconds = common.estimate_task_eta_seconds(running_task)
            worker_subtask = common.read_worker_log_subtask(
                running_task.get("slot_key", ""),
                running_task.get("date_folder", ""),
            )

    # Light worker slots
    light_locks = db.get_light_worker_locks()
    light_worker_slots = []
    for lk in light_locks:
        lt_id = lk.get("task_id")
        lt_task = db.get_task(lt_id) if lt_id else None
        light_worker_slots.append({
            "runner": lk.get("runner"),
            "pid": lk.get("pid"),
            "task_id": lt_id,
            "task_title": lt_task.get("title") if lt_task else None,
            "started_at": lk.get("started_at"),
            "heartbeat_at": lk.get("heartbeat_at"),
        })

    return {
        "today": today,
        "scheduler_enabled": llm_control["scheduler_enabled"],
        "llm_mode": llm_control["mode"],
        "llm_hard_off": llm_control["hard_off_active"],
        "last_llm_call_at": llm_control["last_llm_call_at"],
        "blocked_execution_count": llm_control["blocked_execution_count"],
        "active_background_runners": llm_control["active_background_runners"],
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
        "worker_run_state_badge": worker_run_state_badge,
        "worker_eta_seconds": worker_eta_seconds,
        "worker_subtask": worker_subtask,
        "copilot_daemon_running": daemon_status.get("running", False),
        "copilot_daemon_pid": daemon_status.get("pid"),
        "copilot_daemon_status": daemon_status.get("status"),
        "copilot_daemon_task_id": daemon_status.get("current_task_id"),
        "recent_run_outcomes": outcome_dist,
        "next_planner_tick_estimate": next_planner,
        "next_worker_tick_estimate": next_worker,
        "light_worker_count": len(light_worker_slots),
        "light_worker_slots": light_worker_slots,
        "h6_live_state": _get_h6_live_state(),
        **_get_h6_report_flat_fields(),
    }


def _get_h6_live_state() -> Optional[dict]:
    """Fetch H6 monitoring state for inclusion in orchestrator summary."""
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "lottery_api"))
        from engine.h6_live_monitor import get_monitoring_state as _h6_state, H6_STRATEGY_ID
        state = _h6_state("DAILY_539")
        ass_rows = db.get_all_active_strategy_states()
        ass = next((r for r in ass_rows if r.get("game_type") == "DAILY_539"), None)
        return {
            "active_strategy": ass.get("active_strategy") if ass else H6_STRATEGY_ID,
            "shadow_strategy": ass.get("shadow_strategy") if ass else None,
            "live_30p_edge":            state.get("live_30p_edge"),
            "live_50p_edge":            state.get("live_50p_edge"),
            "consecutive_negative_30p": state.get("consecutive_negative_30p", 0),
            "current_regime":           state.get("current_regime"),
            "rollback_status":          state.get("rollback_status", "ACTIVE"),
            "rollback_triggered":       state.get("rollback_triggered", False),
            "rollback_reason":          state.get("rollback_reason"),
        }
    except Exception:
        return None


def _get_latest_h6_report_summary() -> Optional[dict]:
    """Return a brief summary of the latest H6 daily operations report."""
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "lottery_api"))
        from engine.h6_report_generator import get_latest_report_summary as _summary
        return _summary(game_type="DAILY_539")
    except Exception:
        return None


def _get_h6_report_flat_fields() -> dict:
    """Return flat H6 report fields for inclusion in summary endpoints.

    Computes the summary once and exposes both the nested dict and flat fields
    (latest_h6_risk_level, latest_h6_action_recommendation, latest_h6_daily_report_path,
    latest_h6_daily_report) so callers can query any level of granularity.
    """
    summary = _get_latest_h6_report_summary()
    return {
        "latest_h6_daily_report_summary": summary,
        "latest_h6_daily_report": summary,
        "latest_h6_daily_report_path": (summary or {}).get("json_path"),
        "latest_h6_risk_level": (summary or {}).get("risk_level"),
        "latest_h6_action_recommendation": (summary or {}).get("action"),
    }


@router.get("/api/orchestrator/metrics")
def get_worker_metrics():
    """Adaptive scheduling metrics: queue depths, latency, throughput, backpressure state."""
    try:
        queue_depth = db.get_queue_depth_by_type()
    except Exception:
        queue_depth = {}
    try:
        research_latency = db.get_avg_task_latency("research", window_hours=6)
        light_latency = db.get_avg_task_latency("light", window_hours=6)
        research_throughput = db.get_throughput_per_hour("research", window_hours=1)
        light_throughput = db.get_throughput_per_hour("light", window_hours=1)
    except Exception:
        research_latency = light_latency = research_throughput = light_throughput = None
    try:
        light_active = db.count_active_light_workers()
    except Exception:
        light_active = 0
    try:
        backpressure = db.get_set_scheduling_state("backpressure_active") == "1"
    except Exception:
        backpressure = False
    try:
        history = db.get_worker_metrics_snapshot(limit=60)
    except Exception:
        history = []
    return {
        "queue_depth": queue_depth,
        "light_active": light_active,
        "light_max": common.MAX_LIGHT_WORKERS,
        "backpressure_active": backpressure,
        "research": {
            "avg_latency_s": research_latency,
            "throughput_ph": research_throughput,
        },
        "light": {
            "avg_latency_s": light_latency,
            "throughput_ph": light_throughput,
        },
        "history": history,
    }



    enabled: bool


class ProviderConfigRequest(BaseModel):
    planner_provider: Optional[str] = None
    worker_provider: Optional[str] = None
    worker_copilot_model: Optional[str] = None


class RunNowRequest(BaseModel):
    runner: str


class LlmControlRequest(BaseModel):
    mode: str


class SchedulerToggleRequest(BaseModel):
    enabled: bool


class CtoSchedulerToggleRequest(BaseModel):
    enabled: bool


class CtoProviderConfigRequest(BaseModel):
    planner_provider: Optional[str] = None
    planner_model: Optional[str] = None


class CtoRunNowRequest(BaseModel):
    force: bool = False
    run_intent: Optional[str] = None   # retry | compare | override
    parent_run_id: Optional[str] = None

    def validated_intent(self) -> Optional[str]:
        _allowed = {"retry", "compare", "override"}
        v = (self.run_intent or "").strip().lower()
        return v if v in _allowed else None


class CtoReviewSettingsRequest(BaseModel):
    cto_review_provider: Optional[str] = None
    cto_review_model: Optional[str] = None
    cto_review_mode: Optional[str] = None
    cto_review_daily_call_cap: Optional[int] = None
    cto_review_timeout_seconds: Optional[int] = None
    cto_review_max_context_chars: Optional[int] = None
    cto_review_max_output_chars: Optional[int] = None


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


def _latest_policy_skip_reason() -> Optional[str]:
    for event in reversed(execution_policy.read_recent_events(limit=500)):
        if event.get("event") == "skip":
            return event.get("skip_reason")
    return None


def _active_background_runners() -> list[dict]:
    runners = []

    worker_lock = db.get_worker_lock()
    if worker_lock and worker_lock.get("pid") and common.is_process_alive(worker_lock.get("pid")):
        runners.append({
            "name": "worker",
            "pid": worker_lock.get("pid"),
            "task_id": worker_lock.get("task_id"),
            "status": "running",
        })

    daemon_status = common.copilot_daemon_status()
    if daemon_status.get("running"):
        runners.append({
            "name": "copilot-daemon",
            "pid": daemon_status.get("pid"),
            "task_id": daemon_status.get("current_task_id"),
            "status": daemon_status.get("status") or "running",
        })

    cto_run = db.get_latest_cto_review_run()
    if cto_run and (cto_run.get("status") or "").upper() == "RUNNING" and cto_run.get("pid") and common.is_process_alive(cto_run.get("pid")):
        runners.append({
            "name": "cto-review",
            "pid": cto_run.get("pid"),
            "task_id": None,
            "status": "running",
        })

    return runners


def _llm_control_payload() -> dict:
    state = execution_policy.current_state()
    return {
        "mode": state.get("mode"),
        "scheduler_enabled": state.get("scheduler_enabled"),
        "cto_scheduler_enabled": state.get("cto_scheduler_enabled"),
        "hard_off_active": state.get("hard_off_active"),
        "last_llm_call_at": execution_policy.last_llm_call_at(),
        "blocked_execution_count": execution_policy.blocked_execution_count(),
        "last_skip_reason": _latest_policy_skip_reason(),
        "active_background_runners": _active_background_runners(),
    }


@router.get("/api/orchestrator/scheduler")
def get_scheduler_status():
    state = execution_policy.current_state()
    return {"enabled": state.get("scheduler_enabled"), "mode": state.get("mode")}


@router.post("/api/orchestrator/scheduler")
def set_scheduler_status(req: SchedulerToggleRequest):
    execution_policy.set_scheduler_enabled(req.enabled)
    state = "ENABLED" if req.enabled else "DISABLED"
    mode = execution_policy.get_mode()
    db.log_tick("orchestrator", f"SCHEDULER_{state}", message=f"Scheduler set to {state} | mode={mode}")
    return {"enabled": req.enabled, "mode": mode}


@router.get("/api/orchestrator/llm-control")
def get_llm_control():
    return _llm_control_payload()


@router.post("/api/orchestrator/llm-control")
def set_llm_control(req: LlmControlRequest):
    mode = execution_policy.set_mode(req.mode)
    db.log_tick("orchestrator", "LLM_CONTROL_UPDATED", message=f"LLM execution mode set to {mode}")
    payload = _llm_control_payload()
    payload["ok"] = True
    return payload


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
    decision = execution_policy.evaluate("api.run-now", scope="main")
    if not decision.allowed:
        execution_policy.record_skip(decision, endpoint="/api/orchestrator/run-now", runner=runner)
        raise HTTPException(status_code=409, detail=f"{decision.skip_reason} — manual LLM execution blocked")
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
    _proc_watchdog.register(
        proc.pid,
        timeout_s=_WORKER_TIMEOUT_S,
        label=f"{runner}-tick",
        run_id=request_id,
    )
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


@router.get("/api/orchestrator/llm-usage/today")
def get_llm_usage_today():
    """Return today's LLM call counts aggregated by agent_label and by role (Asia/Taipei date).

    The summary now includes token / premium totals and rate-limit warnings.
    """
    day_label = common.local_day_label()
    items = db.get_today_llm_usage_by_agent(day_label)
    role_data = db.get_today_llm_usage_by_role(day_label)
    return {
        "date": day_label,
        "timezone": "Asia/Taipei",
        "summary": role_data["summary"],
        "roles": role_data["roles"],
        "items": items,  # legacy: kept for backward compatibility
    }


@router.get("/api/orchestrator/llm-usage/recent")
def get_llm_usage_recent(limit: int = 20):
    """Return the most recent LLM usage events with token/premium metrics.

    Query params:
        limit  (int, default=20, max=200)
    """
    events = db.get_recent_llm_usage_events(limit=limit)
    return {"events": events, "count": len(events)}


@router.get("/api/orchestrator/llm-usage/detail")
def get_llm_usage_detail(date: Optional[str] = None):
    """Return comprehensive LLM usage detail for the dashboard.

    Query params:
        date  (str, optional) — YYYY-MM-DD or 'today' (default: today Asia/Taipei)

    Response structure:
        date, timezone, roles, by_provider, by_runner, by_agent,
        copilot_focus, top_tasks, recent, warnings
    """
    if date and date.lower() != "today":
        day_label = date
    else:
        day_label = common.local_day_label()
    return db.get_llm_usage_detail(day_label)


# ── LLM Audit Endpoints ───────────────────────────────────────────────────────

@router.get("/api/orchestrator/llm-audit/recent")
def get_llm_audit_recent(
    hours: Optional[float] = 24,
    runner: Optional[str] = None,
    provider: Optional[str] = None,
    blocked: bool = False,
    limit: int = 50,
):
    """Return recent LLM audit events with optional filters.

    Query params:
        hours    (float, default=24)     — only events from last N hours
        runner   (str, optional)         — filter by runner_type
        provider (str, optional)         — filter by provider (partial match)
        blocked  (bool, default=false)   — show only blocked events
        limit    (int, default=50, max=200)
    """
    from orchestrator import llm_audit
    events = llm_audit.query_events(
        hours=hours,
        runner=runner,
        provider=provider,
        only_blocked=blocked,
        limit=min(int(limit), 200),
    )
    return {"events": events, "count": len(events)}


@router.get("/api/orchestrator/llm-audit/today")
def get_llm_audit_today():
    """Return today's LLM audit summary: totals by role, provider, and event_type."""
    from orchestrator import llm_audit
    return llm_audit.today_summary()


@router.get("/api/orchestrator/llm-caps/status")
def get_llm_caps_status():
    """Return LLM cap enforcement status: caps enabled, roles, providers, recent blocks."""
    from orchestrator.llm_caps import get_cap_status
    return get_cap_status()


@router.get("/api/orchestrator/rollback-guard/status")
async def get_rollback_guard_status(game_type: str = "DAILY_539"):
    """Return rollback guard config and current read-only decision for a game type."""
    from orchestrator.rollback_guard import load_rollback_guard_config, evaluate_rollback_guard
    config = load_rollback_guard_config(game_type)

    # Read current state from DB
    try:
        conn = db.get_conn()
        row = conn.execute(
            "SELECT active_strategy, shadow_strategy, rollback_status, live_30p_edge, "
            "       consecutive_negative_30p "
            "FROM active_strategy_state WHERE game_type=?",
            (game_type,)
        ).fetchone()
        conn.close()
        if row:
            current_state = {
                "active_strategy": row[0],
                "shadow_strategy": row[1],
                "rollback_status": row[2],
                "live_30p_edge": row[3],
                "outcome_count": 0,  # not stored in active_strategy_state; use live_strategy_outcomes
                "consecutive_negative_30p": row[4] or 0,
            }
            # Fetch outcome_count from live_strategy_outcomes
            try:
                conn2 = db.get_conn()
                cnt_row = conn2.execute(
                    "SELECT COUNT(*) FROM live_strategy_outcomes WHERE game_type=?",
                    (game_type,)
                ).fetchone()
                conn2.close()
                current_state["outcome_count"] = cnt_row[0] if cnt_row else 0
            except Exception:
                pass
        else:
            current_state = {"error": f"no state for {game_type}"}
    except Exception as e:
        current_state = {"error": str(e)}

    # Evaluate current decision (read-only)
    decision = None
    if "error" not in current_state:
        try:
            decision = evaluate_rollback_guard(
                game_type=game_type,
                live_30p_edge=current_state.get("live_30p_edge"),
                outcome_count=current_state.get("outcome_count", 0),
                consecutive_negative_30p=current_state.get("consecutive_negative_30p", 0),
                config=config,
            )
        except Exception as e:
            decision = {"error": str(e)}

    return {
        "game_type": game_type,
        "guard_enabled": config.guard_enabled,
        "config": config.to_dict(),
        "current_state": current_state,
        "current_decision": decision.to_dict() if hasattr(decision, "to_dict") else decision,
    }


@router.get("/api/orchestrator/outcome-gate/status")
async def get_outcome_gate_status():
    """Return read-only status of the unified outcome gate."""
    from orchestrator.outcome_gate import get_outcome_gate_status
    return get_outcome_gate_status()


@router.get("/api/orchestrator/stale-locks/status")
def stale_locks_status():
    """Return stale RUNNING lock scan results (dry-run, read-only)."""
    import dataclasses
    from orchestrator.stale_lock_recovery import load_stale_lock_policy, inspect_running_tasks
    policy = load_stale_lock_policy()
    decisions = inspect_running_tasks()
    would_release = sum(1 for d in decisions if d.should_release)
    warnings = sum(1 for d in decisions if d.reason == "WARNING_LONG_RUNNING_ALIVE")
    return {
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


@router.get("/api/orchestrator/evidence/status")
def evidence_status():
    """Return EvidenceCollector v0.1 dry-run status across all sources."""
    try:
        from orchestrator.evidence.collector import collect_evidence, VALID_SOURCES
        import dataclasses
        result = collect_evidence(dry_run=True)
        return {
            "sources_enabled": list(VALID_SOURCES),
            "dry_run": True,
            "item_count": result.item_count,
            "items": result.items,
            "last_jsonl_path": result.jsonl_path,
            "errors": result.errors,
        }
    except Exception as e:
        from fastapi.responses import JSONResponse
        return JSONResponse({"error": str(e)}, status_code=500)


# ── Planner Multi-Provider Settings ───────────────────────────────────────────

class PlannerLlmSettingsRequest(BaseModel):
    planner_llm_provider: Optional[str] = None
    planner_llm_model: Optional[str] = None
    planner_llm_enabled: Optional[bool] = None
    planner_llm_mode: Optional[str] = None
    planner_budget_guard_enabled: Optional[bool] = None
    planner_daily_call_cap: Optional[int] = None
    planner_timeout_seconds: Optional[int] = None
    planner_max_output_chars: Optional[int] = None


class PlannerRunOnceRequest(BaseModel):
    force: bool = False


@router.get("/api/orchestrator/planner-settings")
def get_planner_settings():
    """Return current LLM Planner multi-provider settings plus today's call stats."""
    day_label = common.local_day_label()
    cap = db.get_planner_daily_call_cap()
    today_calls = db.get_planner_today_calls(day_label)
    remaining = max(0, cap - today_calls) if cap > 0 else 0
    return {
        "planner_llm_provider": db.get_planner_llm_provider(),
        "planner_llm_model": db.get_planner_llm_model(),
        "planner_llm_enabled": db.get_planner_llm_enabled(),
        "planner_llm_mode": db.get_planner_llm_mode(),
        "planner_budget_guard_enabled": db.get_planner_budget_guard_enabled(),
        "planner_daily_call_cap": cap,
        "planner_timeout_seconds": db.get_planner_timeout_seconds(),
        "planner_max_output_chars": db.get_planner_max_output_chars(),
        "planner_today_calls": today_calls,
        "planner_remaining_cap": remaining,
        "day_label": day_label,
        "valid_providers": sorted(["local", "claude-cli", "codex-cli", "auto"]),
        "valid_modes": ["off", "suggest_only", "create_task", "create_and_route"],
    }


@router.post("/api/orchestrator/planner-settings")
def update_planner_settings(req: PlannerLlmSettingsRequest):
    """Update LLM Planner provider settings. Only provided fields are changed."""
    from orchestrator import planner_provider as pp_module

    errors = []

    if req.planner_llm_provider is not None:
        v = str(req.planner_llm_provider).strip().lower()
        if v not in pp_module.VALID_PROVIDERS:
            errors.append(f"Invalid planner_llm_provider: {v!r}. Must be one of {sorted(pp_module.VALID_PROVIDERS)}")
        else:
            db.set_planner_llm_provider(v)

    if req.planner_llm_model is not None:
        db.set_planner_llm_model(str(req.planner_llm_model).strip() or "auto")

    if req.planner_llm_enabled is not None:
        db.set_planner_llm_enabled(bool(req.planner_llm_enabled))

    if req.planner_llm_mode is not None:
        v = str(req.planner_llm_mode).strip().lower()
        if v not in pp_module.VALID_MODES:
            errors.append(f"Invalid planner_llm_mode: {v!r}. Must be one of {sorted(pp_module.VALID_MODES)}")
        else:
            db.set_planner_llm_mode(v)

    if req.planner_budget_guard_enabled is not None:
        db.set_planner_budget_guard_enabled(bool(req.planner_budget_guard_enabled))

    if req.planner_daily_call_cap is not None:
        cap = int(req.planner_daily_call_cap)
        if cap < 0:
            errors.append("planner_daily_call_cap must be >= 0")
        else:
            db.set_planner_daily_call_cap(cap)

    if req.planner_timeout_seconds is not None:
        t = int(req.planner_timeout_seconds)
        if t < 30:
            errors.append("planner_timeout_seconds must be >= 30")
        else:
            db.set_planner_timeout_seconds(t)

    if req.planner_max_output_chars is not None:
        n = int(req.planner_max_output_chars)
        if n < 1000:
            errors.append("planner_max_output_chars must be >= 1000")
        else:
            db.set_planner_max_output_chars(n)

    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))

    db.log_tick("planner-llm", "PLANNER_SETTINGS_UPDATED",
                message=f"LLM Planner settings updated via API")
    return {"ok": True, **get_planner_settings()}


@router.post("/api/orchestrator/planner/preview")
def planner_preview(_req: dict = None):
    """
    Run LLM Planner in suggest_only mode (no task creation). force=True bypasses cap.
    Always marks as manual_preview=True.
    """
    from orchestrator import planner_provider as pp_module

    provider = db.get_planner_llm_provider()
    model = db.get_planner_llm_model()
    mode = "suggest_only"
    context = pp_module.build_planner_context()

    result = pp_module.run_planner_provider(
        provider=provider,
        model=model,
        context=context,
        mode=mode,
        force=True,
        manual_preview=True,
    )

    return {
        "ok": not bool(result.error),
        "provider": result.provider,
        "model": result.model,
        "agent_label": result.agent_label,
        "mode": result.mode,
        "decision": result.decision,
        "reason": result.reason,
        "task_payload": result.task_payload,
        "safety": result.safety,
        "raw_output_excerpt": result.raw_output_excerpt,
        "usage_logged": result.usage_logged,
        "task_created": False,  # preview never creates tasks
        "skipped": result.skipped,
        "skip_reason": result.skip_reason,
        "error": result.error,
        "fallback_to_local": result.fallback_to_local,
    }


@router.post("/api/orchestrator/planner/run-once")
def planner_run_once(req: PlannerRunOnceRequest):
    """
    Run LLM Planner once, respecting mode settings.
    set force=true to bypass daily cap and scheduler guard.
    """
    from orchestrator import planner_provider as pp_module

    provider = db.get_planner_llm_provider()
    model = db.get_planner_llm_model()
    mode = db.get_planner_llm_mode()
    context = pp_module.build_planner_context()

    result = pp_module.run_planner_provider(
        provider=provider,
        model=model,
        context=context,
        mode=mode,
        force=req.force,
        manual_preview=False,
    )

    # Attempt task creation if mode allows and decision=CREATE_TASK
    task_created = False
    created_task_id = None
    safety = result.safety or {}
    risk_level = str(safety.get("risk_level") or "LOW").upper()

    if (
        not result.error
        and not result.skipped
        and result.decision == "CREATE_TASK"
        and mode in ("create_task", "create_and_route")
        and result.task_payload
        and risk_level != "HIGH"
    ):
        try:
            task = result.task_payload
            title = str(task.get("title") or "LLM Planner Task")[:200]
            prompt = str(task.get("prompt") or "")
            worker_type = str(task.get("worker_type") or "light").strip().lower()
            if worker_type not in ("research", "light"):
                worker_type = "light"
            dedupe_key = str(task.get("dedupe_key") or f"llm_planner:{common.local_day_label()}:{title[:40]}")

            slot_key = common.slot_key_now()
            date_folder = common.date_folder_now()
            slug = common.slugify(title)[:60]

            # Write prompt file
            import os
            ppath = common.prompt_path(slot_key, slug, date_folder)
            os.makedirs(os.path.dirname(ppath), exist_ok=True)
            with open(ppath, "w", encoding="utf-8") as f:
                f.write(prompt)

            created_task_id = db.create_task(
                slot_key=slot_key,
                date_folder=date_folder,
                title=title,
                slug=slug,
                prompt_text=prompt,
                prompt_file_path=ppath,
                dedupe_key=dedupe_key,
                worker_type=worker_type,
            )
            task_created = True
            if result.usage_event_id and created_task_id:
                try:
                    db.update_task(created_task_id, planner_agent_label=result.agent_label)
                except Exception:
                    pass

            db.log_tick("planner-llm", "PLANNER_LLM_TASK_CREATED",
                        task_id=created_task_id,
                        message=f"LLM Planner created task: {title[:80]}")
        except Exception as exc:
            logger.warning("planner_run_once: task creation failed: %s", exc)

    return {
        "ok": not bool(result.error),
        "provider": result.provider,
        "model": result.model,
        "agent_label": result.agent_label,
        "mode": result.mode,
        "decision": result.decision,
        "reason": result.reason,
        "task_payload": result.task_payload,
        "safety": result.safety,
        "raw_output_excerpt": result.raw_output_excerpt,
        "usage_logged": result.usage_logged,
        "task_created": task_created,
        "created_task_id": created_task_id,
        "skipped": result.skipped,
        "skip_reason": result.skip_reason,
        "error": result.error,
        "fallback_to_local": result.fallback_to_local,
    }


def get_backlog():
    content = common.read_backlog()
    return {"content": content, "path": common.BACKLOG_PATH}
@router.get("/api/orchestrator/cto/summary")
def get_cto_summary():
    latest_run = db.get_latest_cto_review_run()
    pending_count = db.count_task_git_commits(status="PENDING_REVIEW")
    latest_run_payload = latest_run or {}
    cto_planner_provider = db.get_cto_planner_provider()
    llm_control = _llm_control_payload()
    return {
        "frequency_mode": db.get_cto_review_frequency_mode(),
        "scheduler_enabled": llm_control["cto_scheduler_enabled"],
        "llm_mode": llm_control["mode"],
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
        "h6_live_state": _get_h6_live_state(),
        **_get_h6_report_flat_fields(),
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


@router.get("/api/orchestrator/cto/waiting-manual")
def list_waiting_manual_approval(limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0)):
    """List all commits waiting for manual approval before merge."""
    rows = db.list_waiting_manual_approval(limit=limit, offset=offset)
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


@router.post("/api/orchestrator/cto/tasks/{task_id}/approve-merge")
def approve_manual_merge(task_id: int):
    """
    Approve and execute merge for a task in WAITING_MANUAL_APPROVAL status.
    Triggered by the user clicking 'Approve' in the frontend.
    """
    from orchestrator import cto_review_tick  # local import to avoid circular dependency
    result = cto_review_tick.execute_manual_merge_for_task(task_id)
    if not result["success"]:
        raise HTTPException(status_code=409, detail=result["message"])
    return result


@router.get("/api/orchestrator/cto/scheduler")
def get_cto_scheduler_status():
    cto_planner_provider = db.get_cto_planner_provider()
    state = execution_policy.current_state()
    return {
        "enabled": state.get("cto_scheduler_enabled"),
        "mode": state.get("mode"),
        "planner_provider": cto_planner_provider,
        "planner_provider_label": common.planner_provider_label(cto_planner_provider),
        "planner_model": db.get_cto_planner_model(),
        "planner_options": common.planner_provider_options(),
    }


@router.post("/api/orchestrator/cto/scheduler")
def set_cto_scheduler_status(req: CtoSchedulerToggleRequest):
    execution_policy.set_cto_scheduler_enabled(req.enabled)
    state = "ENABLED" if req.enabled else "DISABLED"
    mode = execution_policy.get_mode()
    db.log_tick("cto-review", f"CTO_SCHEDULER_{state}", message=f"CTO Scheduler set to {state} | mode={mode}")
    return {"enabled": req.enabled, "mode": mode}


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
def cto_run_now(req: CtoRunNowRequest = None):
    decision = execution_policy.evaluate("api.cto-run-now", scope="cto")
    if not decision.allowed:
        execution_policy.record_skip(decision, endpoint="/api/orchestrator/cto/run-now")
        raise HTTPException(status_code=409, detail=f"{decision.skip_reason} — CTO manual execution blocked")
    request_id = uuid.uuid4().hex
    triggered_at = datetime.now(timezone.utc).isoformat()
    script_path = os.path.join(common.ROOT, "orchestrator", "cto_review_tick.py")
    if not os.path.exists(script_path):
        raise HTTPException(status_code=500, detail="cto_review_tick.py not found")
    is_force = req is not None and req.force
    # ── Force Run Rate Limit: max 3 force runs per 10 minutes ────────────────
    _FORCE_RATE_LIMIT = 3
    _FORCE_RATE_WINDOW_S = 600
    if is_force:
        recent_force_count = db.count_recent_force_runs(within_seconds=_FORCE_RATE_WINDOW_S)
        if recent_force_count >= _FORCE_RATE_LIMIT:
            raise HTTPException(
                status_code=429,
                detail=(
                    f"Force run rate limit reached: {recent_force_count}/{_FORCE_RATE_LIMIT} "
                    f"force runs in the last {_FORCE_RATE_WINDOW_S // 60} minutes. "
                    "Please wait before retrying."
                ),
            )
    intent = req.validated_intent() if req else None
    parent_run_id = (req.parent_run_id or "").strip() or None if req else None
    env = os.environ.copy()
    env["ORCHESTRATOR_FORCE_RUN"] = "1"
    env["ORCHESTRATOR_REQUEST_ID"] = request_id
    if is_force:
        env["ORCHESTRATOR_FORCE_RERUN"] = "1"
    if intent:
        env["ORCHESTRATOR_RUN_INTENT"] = intent
    if parent_run_id:
        env["ORCHESTRATOR_PARENT_RUN_ID"] = parent_run_id
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
        message=(
            f"CTO review run-now triggered, pid={proc.pid}"
            + (" [FORCE]"
               + (f" intent={intent}" if intent else "")
               + (f" parent={parent_run_id}" if parent_run_id else "")
               if is_force else "")
        ),
        request_id=request_id,
    )
    _proc_watchdog.register(
        proc.pid,
        timeout_s=_CTO_TIMEOUT_S,
        label="cto-review-tick",
        run_id=request_id,
    )
    return {
        "ok": True,
        "pid": proc.pid,
        "triggered_at": triggered_at,
        "request_id": request_id,
        "force": is_force,
        "run_intent": intent,
        "parent_run_id": parent_run_id,
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
        "CTO_REVIEW_STALE",
        "CTO_REVIEW_SKIP_DUPLICATE_RUNNING",
        "CTO_REVIEW_SKIP_DUPLICATE_RECENT",
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
            runs = [r for r in runs if (r.get("status") or "").upper() == "RUNNING"]
        elif status_upper == "COMPLETED":
            runs = [r for r in runs if (r.get("status") or "").upper() == "COMPLETED"]
        elif status_upper == "SKIPPED":
            runs = [r for r in runs if (r.get("status") or "").upper() in {"SKIPPED", "FAILED", "FAILED_STALE", "SKIPPED_STALE"}]
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


# ─── CTO Action → Backlog ─────────────────────────────────────────────────────

class CtoBacklogAddRequest(BaseModel):
    finding_id: str
    cto_run_id: str
    severity: Optional[str] = None
    impact_score: Optional[int] = None
    urgency: Optional[str] = None
    category: Optional[str] = None
    suggested_action: Optional[str] = None


class CtoBacklogBatchRequest(BaseModel):
    cto_run_id: str
    min_severity: Optional[str] = "HIGH"   # CRITICAL | HIGH | MEDIUM | LOW
    min_impact: Optional[int] = 60


def _cto_action_prompt(item: CtoBacklogAddRequest) -> tuple[str, str, str]:
    """Build a structured agent prompt from a CTO backlog item."""
    action_text = (item.suggested_action or "").strip() or f"處理 CTO 審核發現 {item.finding_id}"
    slug_raw = f"cto-{(item.category or 'task')}-{item.finding_id.replace('/', '-')}"
    slug = slug_raw[:40].rstrip("-")

    title = action_text[:60] or f"CTO Action: {item.finding_id}"

    sev = item.severity or "—"
    urg = item.urgency or "—"
    cat = item.category or "—"
    score = item.impact_score if item.impact_score is not None else "—"

    prompt = f"""## CTO Review Action — {item.finding_id}

**來源**: CTO Review Run `{item.cto_run_id}`
**Severity**: {sev} | **Impact**: {score}/100 | **Urgency**: {urg}
**Category**: {cat}

## Objective

{action_text}

## Constraints

- 本任務由 CTO Review 系統自動排入 backlog（finding_id: `{item.finding_id}`）
- 依照現有 wiki/governance.md 標準處理
- 優先採用最小必要修改
- 若為衝突修復，需確保 git cherry-pick 可以乾淨執行

## Acceptance Criteria

- 提出明確的完成摘要
- 列出異動檔案（或確認無異動）
- 說明該 finding 是否已解決

## Handoff Notes

- CTO Run ID: `{item.cto_run_id}`
- Finding ID: `{item.finding_id}`
- 若更新策略或 wiki，遵循 wiki/governance.md 流程
"""
    return title, slug, prompt


def _append_cto_item_to_backlog(item: CtoBacklogAddRequest) -> None:
    """Append a human-readable CTO action entry to backlog.md for planner visibility."""
    entry = (
        f"\n- [ ] [CTO/{item.severity or '?'}] {(item.suggested_action or item.finding_id)[:100]}"
        f" `(run={item.cto_run_id[:20]}, id={item.finding_id})`\n"
    )
    try:
        with open(common.BACKLOG_PATH, "a", encoding="utf-8") as f:
            f.write(entry)
    except OSError:
        pass  # non-fatal: task still created in DB


@router.get("/api/orchestrator/cto/intent-stats")
def get_cto_intent_stats():
    """Return per-intent aggregated outcome stats for learning dashboard."""
    stats = db.get_intent_stats()
    # Annotate with human-readable descriptions
    _DESCRIPTIONS = {
        "retry":   "重試失敗提交，包含 REPLAN/CONFLICT 候選",
        "compare": "比對分析模式，不執行合併和 backlog 寫入",
        "override": "強制覆蓋，正常行為",
    }
    return {
        "ok": True,
        "stats": {
            intent: {**data, "description": _DESCRIPTIONS.get(intent, intent)}
            for intent, data in stats.items()
        },
    }


@router.get("/api/orchestrator/cto/backlog")
def get_cto_backlog(
    cto_run_id: str = Query(None),
    status: str = Query(None),
    limit: int = Query(200, ge=1, le=500),
):
    items = db.list_cto_backlog_items(cto_run_id=cto_run_id, status=status, limit=limit)
    # Enrich with live task status
    enriched = []
    for item in items:
        live_status = db.get_cto_backlog_item_task_status(item)
        enriched.append({**item, "live_status": live_status})
    return {"items": enriched, "count": len(enriched)}


@router.get("/api/orchestrator/cto/adaptive-policy")
def get_adaptive_policy_endpoint():
    """
    Return the current Self-Optimizing adaptive policy.
    Combines the cached computed policy with live intent stats.
    """
    policy = db.get_adaptive_policy(max_age_seconds=3600)
    intent_stats = db.get_intent_stats()
    return {
        "ok":             True,
        "policy":         policy,
        "intent_stats":   intent_stats,
        "confidence_levels": {
            "high":   "≥10 runs analyzed + ≥5 intent runs",
            "medium": "≥5 runs analyzed OR ≥3 intent runs",
            "low":    "insufficient data — defaults applied",
        },
    }


@router.post("/api/orchestrator/cto/adaptive-policy/refresh")
def refresh_adaptive_policy():
    """Force-recompute the adaptive policy from the latest signal data."""
    try:
        policy = db.compute_adaptive_policy()
        return {"ok": True, "policy": policy, "message": "Adaptive policy recomputed"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Policy recompute failed: {exc}") from exc


# ─── Signal Classifier Calibration endpoints ──────────────────────────────────

class ClassifierOutcomeRequest(BaseModel):
    calibration_id: int
    outcome_state: str          # actual regime observed (COLD_REGIME / SIGNAL_SATURATED / etc.)
    draws_checked: int          # 50 / 100 / 150
    original_state: str         # state that was classified (for TP/FP logic)
    notes: Optional[str] = ""


def _compute_fp_fn(original_state: str, outcome_state: str) -> tuple[bool, str]:
    """Map original vs outcome state to TP/FP/FN/TN."""
    predicted_cold  = original_state == "COLD_REGIME"
    actual_cold     = outcome_state == "COLD_REGIME"
    if predicted_cold and actual_cold:
        return True,  "TP"
    if predicted_cold and not actual_cold:
        return False, "FP"
    if not predicted_cold and actual_cold:
        return False, "FN"
    return True, "TN"


@router.get("/api/orchestrator/classifier/calibration")
def get_classifier_calibration():
    """Return recent classifier calibration events and accuracy summary."""
    try:
        report = db.get_classifier_accuracy_report()
        return {"ok": True, **report}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/api/orchestrator/classifier/accuracy")
def get_classifier_accuracy():
    """Return full accuracy report + current dynamic thresholds."""
    try:
        report = db.get_classifier_accuracy_report()
        thresholds = db.get_classifier_thresholds()
        # Compute confidence level labels for current regime state
        confidence_levels = {
            "COLD_REGIME": {
                "strong_cold":   "≥2 games trigger + edge divergence confirmed",
                "cold":          "1–2 games trigger, evidence moderate",
                "weak_cold":     "single weak indicator, low policy support",
                "uncertain":     "insufficient evidence",
            },
            "SIGNAL_SATURATED": {
                "strong_saturated": "validated strategies + proven merge rate + ≥10 runs",
                "saturated":        "strategies exist + some activity signal",
                "uncertain":        "insufficient data to confirm saturation",
            },
        }
        return {
            "ok": True,
            "accuracy_report":   report,
            "current_thresholds": thresholds,
            "confidence_levels":  confidence_levels,
            "threshold_guidance": {
                "cold_streak_ratio":      f"Current: {thresholds['cold_streak_ratio']:.2f}. Raises if cold_fp_rate > 20%, lowers if cold_fn_rate > 20%.",
                "cold_edge_absolute_max": f"Current: {thresholds['cold_edge_absolute_max']:+.3f}. Short-term edge must be below this to trigger cold detection.",
            },
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/api/orchestrator/classifier/outcome")
def record_classifier_outcome(req: ClassifierOutcomeRequest):
    """
    Record the observed outcome for a past classifier event.
    Automatically determines TP/FP/FN/TN and adjusts accuracy counters.
    Triggers threshold recomputation if enough data is available.
    """
    try:
        is_correct, fp_fn_type = _compute_fp_fn(req.original_state, req.outcome_state)
        db.record_classifier_outcome(
            calibration_id=req.calibration_id,
            outcome_state=req.outcome_state,
            draws_checked=req.draws_checked,
            is_correct=is_correct,
            fp_fn_type=fp_fn_type,
            notes=req.notes or "",
        )
        # Recompute thresholds after any new outcome
        updated_thresholds = db.compute_classifier_thresholds()
        return {
            "ok":               True,
            "calibration_id":   req.calibration_id,
            "fp_fn_type":       fp_fn_type,
            "is_correct":       is_correct,
            "updated_thresholds": updated_thresholds,
            "message": (
                f"Outcome recorded: {fp_fn_type} "
                f"({'✓ correct' if is_correct else '✗ misclassified'}). "
                "Thresholds recomputed."
            ),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/api/orchestrator/classifier/thresholds/refresh")
def refresh_classifier_thresholds():
    """Force-recompute dynamic classifier thresholds from calibration history."""
    try:
        thresholds = db.compute_classifier_thresholds()
        return {"ok": True, "thresholds": thresholds, "message": "Thresholds recomputed"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/api/orchestrator/cto/backlog")
def add_cto_backlog_item(req: CtoBacklogAddRequest):
    """Add a single CTO finding to the agent backlog. 409 if already exists."""
    # Guard: compare runs must not pollute backlog
    if req.cto_run_id:
        _run_row = db.get_cto_review_run(req.cto_run_id)
        if _run_row and _run_row.get("run_intent") == "compare":
            return {
                "ok": False,
                "blocked": True,
                "message": "compare run 不允許寫入 backlog（比對分析模式）",
            }
    # Dedup check
    existing = db.get_cto_backlog_item_by_finding(req.finding_id)
    if existing:
        live_status = db.get_cto_backlog_item_task_status(existing)
        return {
            "ok": False,
            "conflict": True,
            "message": f"Finding {req.finding_id} already in backlog (status: {live_status})",
            "existing": {**existing, "live_status": live_status},
        }

    # Build and create QUEUED agent task
    title, slug, prompt_text = _cto_action_prompt(req)
    date_folder = common.date_folder_now()
    slot_key = common.slot_key_now()
    prompt_file = common.prompt_path(slot_key, slug, date_folder)

    os.makedirs(os.path.dirname(prompt_file), exist_ok=True)
    try:
        with open(prompt_file, "w", encoding="utf-8") as f:
            f.write(prompt_text)
    except OSError:
        prompt_file = None

    task_id = db.create_task(
        slot_key=slot_key,
        date_folder=date_folder,
        title=title,
        slug=slug,
        prompt_text=prompt_text,
        prompt_file_path=prompt_file,
    )

    # Record in cto_backlog_items
    item_id = db.insert_cto_backlog_item(
        finding_id=req.finding_id,
        cto_run_id=req.cto_run_id,
        severity=req.severity,
        impact_score=req.impact_score,
        urgency=req.urgency,
        category=req.category,
        suggested_action=req.suggested_action,
        task_id=task_id,
        task_slot_key=slot_key,
        status="queued",
    )

    _append_cto_item_to_backlog(req)

    return {
        "ok": True,
        "conflict": False,
        "item_id": item_id,
        "task_id": task_id,
        "slot_key": slot_key,
        "title": title,
        "live_status": "queued",
        "message": f"Finding {req.finding_id} added to backlog as task #{task_id}",
    }


@router.post("/api/orchestrator/cto/backlog/batch")
def batch_add_cto_backlog(req: CtoBacklogBatchRequest):
    """
    Batch-add all high-priority findings from a CTO run report.
    Filters by min_severity and min_impact. Skips duplicates.
    """
    run = db.get_cto_review_run(req.cto_run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"CTO run not found: {req.cto_run_id}")
    # Guard: compare runs must not pollute backlog
    if run.get("run_intent") == "compare":
        return {
            "ok": False,
            "blocked": True,
            "added_count": 0,
            "skipped_count": 0,
            "message": "compare run 不允許寫入 backlog（比對分析模式）",
        }

    json_path = run.get("report_json_path")
    report_json = _read_json(json_path)
    if not report_json:
        raise HTTPException(status_code=404, detail="Report JSON not found or unreadable")

    decisions = report_json.get("decisions") or []
    if not decisions:
        return {"ok": True, "added": [], "skipped": [], "message": "No decisions found in report"}

    _SEVERITY_RANK = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
    min_sev_rank = _SEVERITY_RANK.get(str(req.min_severity or "HIGH").upper(), 3)
    min_impact = int(req.min_impact) if req.min_impact is not None else 60

    added = []
    skipped = []

    for d in decisions:
        scoring = d.get("scoring") or {}
        sev = str(scoring.get("severity") or "LOW").upper()
        impact = int(scoring.get("impact_score") or 0)

        # Filter: must meet severity AND impact thresholds
        if _SEVERITY_RANK.get(sev, 1) < min_sev_rank and impact < min_impact:
            continue

        finding_id = f"{req.cto_run_id}__t{d.get('task_id')}_{sev}"
        action = (d.get("action") or {}).get("action") or d.get("reason") or d.get("decision") or finding_id
        item_req = CtoBacklogAddRequest(
            finding_id=finding_id,
            cto_run_id=req.cto_run_id,
            severity=sev,
            impact_score=impact,
            urgency=scoring.get("urgency"),
            category=d.get("category"),
            suggested_action=str(action)[:300],
        )
        existing = db.get_cto_backlog_item_by_finding(finding_id)
        if existing:
            live_status = db.get_cto_backlog_item_task_status(existing)
            skipped.append({"finding_id": finding_id, "reason": "duplicate", "live_status": live_status})
            continue

        title, slug, prompt_text = _cto_action_prompt(item_req)
        date_folder = common.date_folder_now()
        slot_key = common.slot_key_now()
        prompt_file = common.prompt_path(slot_key, slug, date_folder)
        os.makedirs(os.path.dirname(prompt_file), exist_ok=True)
        try:
            with open(prompt_file, "w", encoding="utf-8") as f:
                f.write(prompt_text)
        except OSError:
            prompt_file = None

        task_id = db.create_task(
            slot_key=slot_key,
            date_folder=date_folder,
            title=title,
            slug=slug,
            prompt_text=prompt_text,
            prompt_file_path=prompt_file,
        )

        item_id = db.insert_cto_backlog_item(
            finding_id=finding_id,
            cto_run_id=req.cto_run_id,
            severity=sev,
            impact_score=impact,
            urgency=scoring.get("urgency"),
            category=d.get("category"),
            suggested_action=str(action)[:300],
            task_id=task_id,
            task_slot_key=slot_key,
            status="queued",
        )
        _append_cto_item_to_backlog(item_req)
        added.append({
            "finding_id": finding_id,
            "item_id": item_id,
            "task_id": task_id,
            "slot_key": slot_key,
            "title": title,
        })

    # After batch insert, recompute ranks across all items
    if added:
        db.rescore_all_backlog_items()

    return {
        "ok": True,
        "added_count": len(added),
        "skipped_count": len(skipped),
        "added": added,
        "skipped": skipped,
    }


# ─── Backlog Priority Engine ──────────────────────────────────────────────────

@router.get("/api/orchestrator/cto/backlog/prioritized")
def get_cto_backlog_prioritized(
    limit: int = Query(200, ge=1, le=500),
    active_only: bool = Query(False, description="Only items with QUEUED/RUNNING tasks"),
):
    """
    Return backlog items sorted by priority: P0 → P1 → P2 → P3, then score desc.
    Enriches each item with live_status and priority metadata.
    """
    status_filter = None
    if active_only:
        status_filter = ["QUEUED", "RUNNING"]

    items = db.list_cto_backlog_items_prioritized(status_filter=status_filter, limit=limit)

    enriched = []
    for item in items:
        task_live = item.get("task_live_status") or db.get_cto_backlog_item_task_status(item)
        enriched.append({
            **{k: v for k, v in item.items() if k != "task_live_status"},
            "live_status": task_live,
        })

    # Group counts by level
    level_counts = {"P0": 0, "P1": 0, "P2": 0, "P3": 0}
    for item in enriched:
        lvl = item.get("priority_level", "P3")
        level_counts[lvl] = level_counts.get(lvl, 0) + 1

    return {
        "items": enriched,
        "count": len(enriched),
        "level_counts": level_counts,
    }


@router.post("/api/orchestrator/cto/backlog/rescore")
def rescore_backlog():
    """
    Recompute priority_score, priority_level, and rank for all backlog items.
    Call this after bulk updates or whenever scoring constants change.
    """
    sorted_items = db.rescore_all_backlog_items()
    level_counts = {"P0": 0, "P1": 0, "P2": 0, "P3": 0}
    for item in sorted_items:
        lvl = item.get("priority_level", "P3")
        level_counts[lvl] = level_counts.get(lvl, 0) + 1
    return {
        "ok": True,
        "rescored_count": len(sorted_items),
        "level_counts": level_counts,
        "top_10": [
            {
                "rank": item.get("rank"),
                "finding_id": item.get("finding_id"),
                "priority_level": item.get("priority_level"),
                "priority_score": item.get("priority_score"),
                "severity": item.get("severity"),
                "impact_score": item.get("impact_score"),
                "category": item.get("category"),
            }
            for item in sorted_items[:10]
        ],
    }


@router.get("/api/orchestrator/cto/backlog/preview-score")
def preview_priority_score(
    severity: str = Query("HIGH"),
    impact_score: int = Query(70),
    urgency: str = Query("SHORT"),
    category: str = Query("architecture"),
):
    """
    Preview computed priority score for a given set of inputs.
    Useful for understanding the formula before inserting items.
    """
    score, level = db.compute_priority_score(severity, impact_score, urgency, category)
    return {
        "severity": severity,
        "impact_score": impact_score,
        "urgency": urgency,
        "category": category,
        "priority_score": score,
        "priority_level": level,
        "formula_breakdown": {
            "severity_pts": db._SEVERITY_PTS.get(severity.upper(), 15),
            "urgency_pts": db._URGENCY_PTS.get(urgency.upper(), 30),
            "category_weight": db._CATEGORY_WEIGHT.get(category.lower(), 0.4),
            "severity_contribution": round(db._SEVERITY_PTS.get(severity.upper(), 15) * 0.35, 2),
            "impact_contribution": round(min(100, max(0, impact_score)) * 0.30, 2),
            "urgency_contribution": round(db._URGENCY_PTS.get(urgency.upper(), 30) * 0.20, 2),
            "category_contribution": round(db._CATEGORY_WEIGHT.get(category.lower(), 0.4) * 10.0, 2),
        },
    }


# ─── Execution Policy API ─────────────────────────────────────────────────────

@router.get("/api/orchestrator/cto/backlog/policy")
def get_execution_policy():
    """Return current execution policy state + queue stats."""
    return db.get_policy_stats()


class PolicyModeRequest(BaseModel):
    mode: str  # strict_priority | balanced | fairness


@router.post("/api/orchestrator/cto/backlog/policy")
def set_execution_policy(req: PolicyModeRequest):
    """Change the scheduler execution policy mode."""
    valid = {"strict_priority", "balanced", "fairness"}
    if req.mode not in valid:
        raise HTTPException(status_code=422, detail=f"Invalid mode {req.mode!r}. Choose from: {sorted(valid)}")
    db.set_policy_mode(req.mode)
    return {"ok": True, "mode": req.mode}


@router.post("/api/orchestrator/cto/backlog/aging")
def trigger_aging():
    """Manually trigger aging bonus application across all waiting backlog items."""
    count = db.apply_aging_bonus()
    return {
        "ok": True,
        "aged_count": count,
        "message": f"Applied aging bonus to {count} items",
    }


# ── CTO Review Provider settings ─────────────────────────────────────────────

@router.get("/api/orchestrator/cto-review-settings")
def get_cto_review_settings():
    """Return all CTO review provider settings and today's call count."""
    day_label = common.local_day_label()
    today_calls = db.get_cto_today_calls(day_label)
    cap = db.get_cto_review_daily_call_cap()
    provider = db.get_cto_review_provider()
    return {
        "cto_review_provider": provider,
        "cto_review_provider_label": {
            "local": "Local (no LLM)",
            "claude-cli": "Claude CLI",
            "codex-cli": "Codex CLI",
            "auto": "Auto (best available)",
        }.get(provider, provider),
        "cto_review_model": db.get_cto_review_model(),
        "cto_review_mode": db.get_cto_review_mode(),
        "cto_review_daily_call_cap": cap,
        "cto_review_timeout_seconds": db.get_cto_review_timeout_seconds(),
        "cto_review_max_context_chars": db.get_cto_review_max_context_chars(),
        "cto_review_max_output_chars": db.get_cto_review_max_output_chars(),
        "today_calls": today_calls,
        "remaining_calls": max(0, cap - today_calls) if cap > 0 else 0,
        "provider_options": [
            {"value": "local", "label": "Local (no LLM)"},
            {"value": "claude-cli", "label": "Claude CLI"},
            {"value": "codex-cli", "label": "Codex CLI"},
            {"value": "auto", "label": "Auto (best available)"},
        ],
        "mode_options": [
            {"value": "local_review", "label": "Local Review (no LLM)"},
            {"value": "review_only", "label": "Review Only (LLM advisory)"},
        ],
        "safety_note": "Claude / Codex CTO 僅提供審核建議。是否真的合併，仍由既有 CTO 合併開關與 Local Safety Gate 決定。",
    }


@router.post("/api/orchestrator/cto-review-settings")
def update_cto_review_settings(req: CtoReviewSettingsRequest):
    """Update CTO review provider settings."""
    updated = {}
    if req.cto_review_provider is not None:
        try:
            db.set_cto_review_provider(req.cto_review_provider)
            updated["cto_review_provider"] = db.get_cto_review_provider()
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
    if req.cto_review_model is not None:
        db.set_cto_review_model(req.cto_review_model)
        updated["cto_review_model"] = db.get_cto_review_model()
    if req.cto_review_mode is not None:
        try:
            db.set_cto_review_mode(req.cto_review_mode)
            updated["cto_review_mode"] = db.get_cto_review_mode()
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
    if req.cto_review_daily_call_cap is not None:
        db.set_cto_review_daily_call_cap(req.cto_review_daily_call_cap)
        updated["cto_review_daily_call_cap"] = db.get_cto_review_daily_call_cap()
    if req.cto_review_timeout_seconds is not None:
        db.set_cto_review_timeout_seconds(req.cto_review_timeout_seconds)
        updated["cto_review_timeout_seconds"] = db.get_cto_review_timeout_seconds()
    if req.cto_review_max_context_chars is not None:
        db.set_cto_review_max_context_chars(req.cto_review_max_context_chars)
        updated["cto_review_max_context_chars"] = db.get_cto_review_max_context_chars()
    if req.cto_review_max_output_chars is not None:
        db.set_cto_review_max_output_chars(req.cto_review_max_output_chars)
        updated["cto_review_max_output_chars"] = db.get_cto_review_max_output_chars()

    db.log_tick("cto-review", "CTO_REVIEW_SETTINGS_UPDATED", message=f"CTO review settings updated: {updated}")
    return {"ok": True, "updated": updated}


@router.post("/api/orchestrator/cto/preview-review")
def preview_cto_review(task_id: int = Query(None, ge=1)):
    """
    Dry-run the CTO review provider on the latest pending commit for a task.
    Does NOT modify the commit status or trigger any merge.
    Bypasses budget guard (force=True).
    """
    from orchestrator import cto_review_provider as crp

    # Find a commit to preview
    commit_row = None
    if task_id:
        rows = db.list_task_git_commits(task_id=task_id, limit=1)
        if rows:
            commit_row = dict(rows[0])
    if commit_row is None:
        # Find the latest pending commit
        conn = db.get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM task_git_commits WHERE status='PENDING_REVIEW' ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
            if row:
                commit_row = dict(row)
        finally:
            conn.close()

    if not commit_row:
        return {"ok": False, "message": "No pending commit found for preview"}

    task_ctx: dict = {}
    result = crp.run_cto_review_provider(commit_row, task_ctx, force=True)
    return {
        "ok": True,
        "task_id": commit_row.get("task_id"),
        "commit_sha": commit_row.get("commit_sha"),
        "provider": result.provider,
        "mode": result.mode,
        "skipped": result.skipped,
        "skip_reason": result.skip_reason,
        "decision": result.decision,
        "risk_level": result.risk_level,
        "merge_recommendation": result.merge_recommendation,
        "final_merge_recommendation": result.final_merge_recommendation,
        "local_gate_blocked": result.local_gate_blocked,
        "local_gate_reason": result.local_gate_reason,
        "reason": result.reason,
        "issues": result.issues,
        "required_checks": result.required_checks,
        "safety_flags": result.safety_flags,
        "usage_logged": result.usage_logged,
        "context_truncated": result.context_truncated,
        "error": result.error,
    }


@router.post("/api/orchestrator/cto/run-review-once")
def run_cto_review_once():
    """
    Manually trigger a single CTO review provider run on all pending commits.
    Returns a summary of recommendations. Does NOT merge — advisory only.
    Bypasses budget guard (force=True).
    """
    from orchestrator import cto_review_provider as crp

    conn = db.get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM task_git_commits WHERE status='PENDING_REVIEW' ORDER BY review_priority DESC, created_at ASC LIMIT 20"
        ).fetchall()
        commits = [dict(r) for r in rows]
    finally:
        conn.close()

    if not commits:
        return {"ok": True, "message": "No pending commits", "results": []}

    results_out = []
    for commit_row in commits:
        try:
            rec = crp.run_cto_review_provider(commit_row, {}, force=True)
            results_out.append({
                "task_id": commit_row.get("task_id"),
                "commit_sha": commit_row.get("commit_sha"),
                "provider": rec.provider,
                "decision": rec.decision,
                "risk_level": rec.risk_level,
                "final_merge_recommendation": rec.final_merge_recommendation,
                "local_gate_blocked": rec.local_gate_blocked,
                "local_gate_reason": rec.local_gate_reason,
                "reason": rec.reason,
                "skipped": rec.skipped,
                "skip_reason": rec.skip_reason,
                "error": rec.error,
            })
        except Exception as exc:
            results_out.append({
                "task_id": commit_row.get("task_id"),
                "commit_sha": commit_row.get("commit_sha"),
                "error": str(exc),
            })

    db.log_tick("cto-review", "CTO_REVIEW_ONCE_MANUAL", message=f"Manual CTO review-once: {len(results_out)} commits reviewed")
    return {"ok": True, "reviewed": len(results_out), "results": results_out}
