#!/usr/bin/env python3
"""
Light Worker tick — runs concurrently with the research worker.
Handles quick monitoring/validation/governance tasks (worker_type='light').

Adaptive scheduling features:
- Dynamic MAX_LIGHT_WORKERS based on CPU usage + queue depth + research activity
- Priority-aware task selection (repair > governance > monitoring)
- Metrics emission to worker_metrics table every tick
- Resource isolation: reduces slots when research worker is CPU-bound
"""

import sys
import os
import time
import logging
import subprocess
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from orchestrator import db, common, llm_audit
from orchestrator.provider_audit_guard import (
    is_external_provider as _is_ext_lw_prov,
    write_worker_result_by_task_id as _write_lw_audit_result,
)
from orchestrator import outcome_extractor

logger = logging.getLogger("light_worker")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

RUNNER = "light_worker"
HEARTBEAT_INTERVAL = 30   # seconds
POLL_TIMEOUT = 300         # seconds — max wait before releasing tick

# ── Task type + quality heuristics ──────────────────────────────────────────
# Maps dedupe_key prefix → canonical task_type used in task_type_roi_state.
_DEDUPE_PREFIX_MAP = [
    ("deep_research",   "deep_research"),
    ("governance",      "governance"),
    ("data_quality",    "data_quality"),
    ("validation_repair", "repair"),
    ("format_repair",   "repair"),
    ("repair",          "repair"),
    ("audit",           "audit"),
    ("report",          "report"),
    ("health_check",    "health_check"),
    ("monitoring",      "monitoring"),
    ("ctrl_inject",     "monitoring"),
    ("fallback",        "fallback"),
]

# Heuristic quality scores by final status (no ML signal yet).
_STATUS_QUALITY = {
    "COMPLETED":        0.70,
    "REPAIR_SUCCESS":   0.80,
    "REPLAN_REQUIRED":  0.35,
    "FAILED":           0.20,
    "FAILED_WEAK_EDGE": 0.15,
    "FAILED_ACCEPTANCE":0.10,
}
_STATUS_QUALITY_DEFAULT = 0.20


def _extract_task_type(dedupe_key: str) -> str:
    """Derive canonical task_type from a dedupe_key string."""
    key = (dedupe_key or "").lower()
    for prefix, task_type in _DEDUPE_PREFIX_MAP:
        if key.startswith(prefix):
            return task_type
    # Fallback: use the first segment before ':'
    return key.split(":")[0] or "unknown"


def _heuristic_scores(status: str, task_type: str) -> tuple:
    """Return (quality_score, roi_score) heuristic floats for a completed task.

    roi_score proxies as quality_score for now; replaced once we have
    strategy-level edge signals.
    """
    q = _STATUS_QUALITY.get(status, _STATUS_QUALITY_DEFAULT)
    # Research tasks: edge_proxy = quality - 0.10 (only positive outcomes matter)
    roi = round(q * (1.1 if task_type == "deep_research" else 1.0), 3)
    roi = min(roi, 1.0)
    return q, roi


# ---------------------------------------------------------------------------
# Metrics helper
# ---------------------------------------------------------------------------

def _emit_metrics(slot_limit: int, backpressure: bool = False, slot_reason: str = ""):
    """Sample queue/utilization and write one row to worker_metrics (v2)."""
    try:
        depth = db.get_queue_depth_by_type()
        active = db.count_active_light_workers()
        light_queued = depth.get("light", 0)
        status_map = db.count_tasks_by_status()
        completed = status_map.get("COMPLETED", 0)
        failed = status_map.get("FAILED", 0)
        avg_lat = db.get_avg_task_latency("light", window_hours=6)
        tph = db.get_throughput_per_hour("light", window_hours=1)
        cpu = common.get_system_cpu_pct(interval=0.2)

        # v2 extended fields
        research_lat = db.get_research_latency_s(window_hours=6)
        research_lock = db.get_worker_lock()
        research_active = 1 if (research_lock and research_lock.get("task_id")) else 0
        total_active = active + research_active
        cpu_share = round((active / max(total_active, 1)) * cpu, 1) if active > 0 else 0.0
        # Starvation incident: queued > threshold but nothing running
        starvation = 1 if (light_queued >= common.STARVATION_QUEUE_ALERT_THRESHOLD and active == 0) else 0

        db.log_worker_metrics(
            worker_type="light",
            active_count=active,
            queued_count=light_queued,
            completed_count=completed,
            failed_count=failed,
            avg_latency_s=avg_lat,
            throughput_ph=tph,
            cpu_pct=cpu,
            slot_limit=slot_limit,
            backpressure=1 if backpressure else 0,
            cpu_share_pct=cpu_share,
            research_latency_s=research_lat,
            starvation_incidents=starvation,
            slot_decision_reason=slot_reason or None,
        )
    except Exception as _e:
        logger.debug("Metrics emit error (non-fatal): %s", _e)


# ---------------------------------------------------------------------------
# Finalize
# ---------------------------------------------------------------------------

def _finalize_light(runner_key: str, task_id: int):
    """Finalize a completed light subprocess: write output, update DB, release lock."""
    task = db.get_task(task_id)
    if not task:
        db.release_light_lock(runner_key)
        return

    slot_key = task["slot_key"]
    slug = task["slug"] or "task"
    date_folder = task["date_folder"]

    log_path = common.worker_stdout_log_path(slot_key, date_folder)
    codex_output = ""
    if os.path.exists(log_path):
        with open(log_path) as f:
            codex_output = f.read()

    has_output = bool(codex_output.strip())
    status = "COMPLETED" if has_output else "FAILED"

    started_at_str = task.get("started_at") or datetime.now(timezone.utc).isoformat()
    try:
        started_dt = datetime.fromisoformat(started_at_str)
        if started_dt.tzinfo is None:
            started_dt = started_dt.replace(tzinfo=timezone.utc)
        else:
            started_dt = started_dt.astimezone(timezone.utc)
        duration = int((datetime.now(timezone.utc) - started_dt).total_seconds())
    except Exception:
        duration = 0

    completed_text = (
        f"## 執行摘要\n\n狀態：{status}，耗時：{duration}s\n\n"
        f"## Worker 輸出\n\n```\n{codex_output[-4000:]}\n```"
    )
    c_path = common.completed_path(slot_key, slug, date_folder)
    with open(c_path, "w") as f:
        f.write(f"# Completed: {task['title']}\n\n")
        f.write(completed_text)

    db.update_task(
        task_id,
        status=status,
        completed_file_path=c_path,
        completed_text=completed_text,
        changed_files_json="[]",
        completed_at=datetime.now(timezone.utc).isoformat(),
        duration_seconds=duration,
        error_message="" if status == "COMPLETED" else "no output",
    )

    # ── Audit: close the open LLM_CALL_ATTEMPT for this task ─────────────────
    _lw_provider = task.get("worker_provider") or db.get_worker_provider() or ""
    if _is_ext_lw_prov(_lw_provider):
        _write_lw_audit_result(
            task_id=task_id,
            success=(status == "COMPLETED"),
            error=None if status == "COMPLETED" else "no output",
            duration_ms=duration * 1000,
            runner_type="light_worker",
            usage_role="worker",
            provider=_lw_provider,
            trigger_source="worker_claim",
        )
    db.release_light_lock(runner_key)

    # ── Outcome pipeline write (real extraction) ──────────────────────────────
    try:
        task_type = _extract_task_type(task.get("dedupe_key") or "")
        success   = (status == "COMPLETED")
        res = outcome_extractor.extract(
            task_id            = task_id,
            task_type          = task_type,
            completed_file_path= c_path,
            completed_text     = completed_text,
        )
        db.record_task_outcome(
            task_id           = task_id,
            task_type         = task_type,
            success           = success,
            quality_score     = res.quality_score,
            roi_score         = res.roi_score,
            edge_score        = res.edge_score,
            extraction_method = res.extraction_method,
            best_edge         = res.best_edge,
            strategies_found  = res.strategies_found,
            mc_pass_count     = res.mc_pass_count,
            confidence_score  = res.confidence_score,
        )
        db.update_task_type_roi(
            task_type     = task_type,
            quality_score = res.quality_score,
            roi_score     = res.roi_score,
            success       = success,
        )
        logger.debug(
            "Outcome recorded: task=%d type=%s method=%s q=%.2f roi=%.2f edge=%.3f conf=%.2f",
            task_id, task_type, res.extraction_method,
            res.quality_score, res.roi_score, res.edge_score, res.confidence_score,
        )
    except Exception as _oe:
        logger.debug("Outcome write error (non-fatal): %s", _oe)
    # ─────────────────────────────────────────────────────────────────────────

    # ── LLM Usage: backfill token/premium metrics from worker stdout ─────────
    try:
        db.backfill_llm_usage_metrics_for_task(
            task_id=task_id,
            output_text=codex_output,
            parse_source="light_worker_finalize_stdout",
            usage_role="worker",
            runner_type="light_worker",
        )
    except Exception as _bfe:
        logger.debug("Light worker backfill_llm_usage error (non-fatal): %s", _bfe)

    msg = f"Light task {task_id} {status} in {duration}s"
    logger.info(msg)
    db.log_tick(RUNNER, f"LIGHT_WORKER_{status}", task_id=task_id, message=msg)
    common.log_jsonl(RUNNER, f"LIGHT_WORKER_{status}", task_id=task_id, duration=duration)


def _claim_and_run(task: dict):
    """Claim a light QUEUED task, launch subprocess, heartbeat, finalize."""
    task_id = task["id"]
    slot_key = task["slot_key"]
    date_folder = task["date_folder"]
    prompt_path = task.get("prompt_file_path", "")

    if not prompt_path or not os.path.exists(prompt_path):
        # Fallback: materialise prompt_text onto disk so the subprocess can read it
        prompt_text = (task.get("prompt_text") or "").strip()
        if prompt_text:
            slug = task.get("slug") or "task"
            fallback_path = common.prompt_path(slot_key, slug, date_folder)
            with open(fallback_path, "w", encoding="utf-8") as _pf:
                _pf.write(prompt_text)
            prompt_path = fallback_path
            logger.info("Light task %s: materialised prompt_text to %s", task_id, fallback_path)
        else:
            msg = f"Light task {task_id} prompt missing: {prompt_path}"
            logger.error(msg)
            db.update_task(task_id, status="FAILED", error_message=msg)
            db.log_tick(RUNNER, "LIGHT_WORKER_FAILED", task_id=task_id, message=msg)
            return

    log_path = common.worker_stdout_log_path(slot_key, date_folder)

    with open(prompt_path) as f:
        prompt_content = f.read()

    try:
        resolution = common.worker_command(prompt_content, db.get_worker_provider())
    except FileNotFoundError as e:
        msg = f"Light task {task_id} provider unavailable: {e}"
        logger.error(msg)
        db.update_task(task_id, status="FAILED", error_message=msg)
        db.log_tick(RUNNER, "LIGHT_WORKER_FAILED", task_id=task_id, message=msg)
        return

    log_file = open(log_path, "w")

    # ── Resolve provider for audit ──
    _light_dispatch_pre = resolution.get("dispatch_provider", resolution.get("runtime", db.get_worker_provider()))
    _light_model_pre = resolution.get("model") or ""

    # ── Cap guard: check LLM caps before audit attempt ──
    if _is_ext_lw_prov(_light_dispatch_pre):
        from orchestrator.llm_caps import check_llm_cap
        _lw_cap = check_llm_cap(
            usage_role="light_worker", runner_type="light_worker",
            provider=_light_dispatch_pre, task_id=task_id,
            model=_light_model_pre, trigger_source="worker_claim",
        )
        if not _lw_cap.allowed:
            llm_audit.write_blocked(
                runner_type="light_worker", usage_role="worker",
                provider=_light_dispatch_pre, model=_light_model_pre,
                block_reason=_lw_cap.block_reason,
                task_id=task_id,
                trigger_source="worker_claim",
                extra_skip=1,
            )
            db.log_tick(RUNNER, "LIGHT_WORKER_SKIP_LLM_CAP", task_id=task_id, message=_lw_cap.block_reason)
            log_file.close()
            return

    # ── Audit: write attempt (fail-closed) ──
    if _is_ext_lw_prov(_light_dispatch_pre):
        _lw_audit_ok, _lw_audit_corr_id = llm_audit.write_attempt(
            runner_type="light_worker", usage_role="worker",
            provider=_light_dispatch_pre, model=_light_model_pre,
            task_id=task_id,
            trigger_source="worker_claim",
            extra_skip=1,
        )
        if not _lw_audit_ok:
            llm_audit.write_audit_unavailable(
                runner_type="light_worker", usage_role="worker",
                provider=_light_dispatch_pre, trigger_source="worker_claim",
            )
            db.log_tick(RUNNER, "LIGHT_WORKER_SKIP_AUDIT_UNAVAILABLE", task_id=task_id,
                        message="BLOCKED_AUDIT_LOG_UNAVAILABLE")
            log_file.close()
            return

    proc = subprocess.Popen(
        resolution["command"],
        stdout=log_file,
        stderr=subprocess.STDOUT,
        cwd=common.ROOT,
        start_new_session=True,
    )
    log_file.close()

    db.update_task(task_id, status="RUNNING", worker_pid=proc.pid,
                   started_at=datetime.now(timezone.utc).isoformat())
    runner_key = db.acquire_light_lock(pid=proc.pid, task_id=task_id)

    # Write LLM attribution for light worker
    _light_dispatch = resolution.get("dispatch_provider", resolution.get("runtime", db.get_worker_provider()))
    _light_model = resolution.get("model") or ""
    _light_label = common.normalize_llm_agent_label(_light_dispatch, _light_model)["display_label"]
    db.update_task(task_id, worker_agent_label=_light_label, llm_call_count=1)
    db.log_llm_usage_event(
        task_id=task_id,
        runner_type="light_worker",
        usage_role="worker",
        provider=_light_dispatch,
        model=_light_model,
        agent_label=_light_label,
        call_count=1,
        event_type="task_claim",
        day_label=common.local_day_label(),
    )

    prio = common.light_task_priority(task.get("dedupe_key", ""))
    msg = f"Light task {task_id} claimed (prio={prio}), PID={proc.pid}"
    logger.info(msg)
    db.log_tick(RUNNER, "LIGHT_WORKER_CLAIMED", task_id=task_id, message=msg)
    common.log_jsonl(RUNNER, "LIGHT_WORKER_CLAIMED", task_id=task_id, pid=proc.pid, priority=prio)

    deadline = time.monotonic() + POLL_TIMEOUT
    while time.monotonic() < deadline:
        ret = proc.poll()
        if ret is not None:
            break
        db.update_light_heartbeat(runner_key)
        time.sleep(HEARTBEAT_INTERVAL)

    if proc.poll() is None:
        # Timed out — let it keep running; we'll pick it up next tick if needed
        msg = f"Light task {task_id} still running after {POLL_TIMEOUT}s — releasing tick"
        logger.warning(msg)
        db.log_tick(RUNNER, "LIGHT_WORKER_TIMEOUT", task_id=task_id, message=msg)
        # Do NOT release lock — it stays until process finishes naturally
        return

    _finalize_light(runner_key, task_id)


# ---------------------------------------------------------------------------
# Stale-lock cleanup
# ---------------------------------------------------------------------------

def _cleanup_stale_locks():
    """Release light locks whose PIDs are no longer alive."""
    for lock in db.get_light_worker_locks():
        pid = lock.get("pid")
        runner_key = lock["runner"]
        task_id = lock.get("task_id")
        if pid is None:
            db.release_light_lock(runner_key)
            continue
        try:
            os.kill(pid, 0)
        except (ProcessLookupError, PermissionError):
            task = db.get_task(task_id) if task_id else None
            if task and task.get("status") == "RUNNING":
                logger.info("Light task %s PID=%s dead — finalizing", task_id, pid)
                _finalize_light(runner_key, task_id)
            else:
                db.release_light_lock(runner_key)


def run():
    """One light_worker_tick invocation: cleanup → adaptive gate → claim → emit metrics → tune."""
    db.init_db()
    _cleanup_stale_locks()

    # ── Gather scheduler inputs ───────────────────────────────────────────────
    active_light = db.count_active_light_workers()
    depth = db.get_queue_depth_by_type()
    light_queued = depth.get("light", 0)

    research_lock = db.get_worker_lock()
    research_active = 1 if (research_lock and research_lock.get("task_id")) else 0

    recent_tph = db.get_throughput_per_hour("light", window_hours=1)
    research_latency_s = db.get_research_latency_s(window_hours=6)
    light_latency_s = db.get_avg_task_latency("light", window_hours=6)

    # ── Load live tunable params (self-tuning scheduler) ─────────────────────
    try:
        from orchestrator import scheduler_tuner as _tuner
        _q_boost = _tuner.get_live_param("queue_boost_threshold")
        _cpu_floor = _tuner.get_live_param("high_cpu_floor")
        _fairness = _tuner.get_live_param("fairness_ratio")
    except Exception as _te:
        logger.debug("Tunable params unavailable (non-fatal): %s", _te)
        _q_boost = _cpu_floor = _fairness = None

    # ── Adaptive slot gate ────────────────────────────────────────────────────
    dynamic_limit, slot_reason = common.get_adaptive_max_light_workers(
        active_light=active_light,
        light_queued=light_queued,
        research_active=research_active,
        recent_light_tph=recent_tph,
        recent_research_latency_s=research_latency_s,
        recent_light_latency_s=light_latency_s,
        queue_boost_threshold=_q_boost,
        high_cpu_floor=_cpu_floor,
        tuned_fairness_ratio=_fairness,
    )

    backpressure = db.get_set_scheduling_state("backpressure_active") == "1"
    _emit_metrics(slot_limit=dynamic_limit, backpressure=backpressure, slot_reason=slot_reason)

    # hard limit=0 can no longer happen due to the max(1,...) floor, but keep
    # the guard for defensive correctness in edge cases.
    if dynamic_limit == 0:
        msg = f"Adaptive scheduler: all light slots disabled [{slot_reason}]"
        logger.info(msg)
        db.log_tick(RUNNER, "LIGHT_WORKER_SKIP_CPU_OVERLOAD", message=msg)
        _run_tuner_background()
        return

    if active_light >= dynamic_limit:
        msg = (
            f"Light worker at capacity ({active_light}/{dynamic_limit}) "
            f"[light_q={light_queued}] [{slot_reason}] — skipping"
        )
        logger.info(msg)
        db.log_tick(RUNNER, "LIGHT_WORKER_SKIP_SLOTS_FULL", message=msg)
        _run_tuner_background()
        return

    # ── Task selection ────────────────────────────────────────────────────────
    task = db.get_next_light_task()
    if not task:
        msg = "No QUEUED light tasks available"
        logger.info(msg)
        db.log_tick(RUNNER, "LIGHT_WORKER_SKIP_IDLE_NO_TASK", message=msg)
        _run_tuner_background()
        return

    _claim_and_run(task)
    _run_tuner_background()


def _run_tuner_background():
    """Run one tuning cycle (non-blocking; errors are non-fatal)."""
    try:
        from orchestrator import scheduler_tuner as _tuner
        result = _tuner.run_tuning_cycle()
        if result.get("action") not in ("skip",):
            logger.info("Tuner: %s", result)
    except Exception as _te:
        logger.debug("Tuner cycle error (non-fatal): %s", _te)


if __name__ == "__main__":
    run()
