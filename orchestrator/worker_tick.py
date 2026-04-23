#!/usr/bin/env python3
"""
Codex Worker tick — triggered every 10 min by launchd.
Heartbeats active tasks, finalizes completed ones, claims and starts new QUEUED tasks.
"""

import sys
import os
import time
import logging
import subprocess
import json
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from orchestrator import db, common

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [worker] %(levelname)s %(message)s"
)
logger = logging.getLogger(__name__)

RUNNER = "worker"
FINALIZED = False  # track if we finalized this tick (to decide whether to try claiming)
COPILOT_STALE_LOG_TIMEOUT_SECONDS = 600


def _worker_runtime_error_markers_to_check() -> list[str]:
    """Return list of markers to check for in worker output."""
    return [
        # Runtime/execution errors
        "error:",
        "traceback",
        "command not found",
        "panicked",
        "failed to connect",
        "stream disconnected before completion",
        "could not create otel exporter",
        
        # Quota/rate-limit errors (critical for governance)
        "you have no quota",
        "no quota",
        "you've reached your weekly rate limit",
        "reached your weekly rate limit",
        "weekly rate limit",
        "please wait for your limit to reset",
        "switch to auto model to continue",
        "docs.github.com/en/copilot/concepts/rate-limits",
        
        # Environment/permission errors
        "third-party mcp servers are disabled",
        "auth failed",
        "not logged in",
        "permission denied",
        "unable to complete this task due to environment execution restrictions",
        
        # Additional environment blocking messages
        "403",
        "429",  # HTTP 429 Too Many Requests
    ]


def _check_worker_runtime_errors(output_lower: str) -> list[str]:
    """Check output against error markers and return matched markers."""
    markers_to_check = _worker_runtime_error_markers_to_check()
    found_markers = []
    for marker in markers_to_check:
        if marker in output_lower:
            found_markers.append(marker)
    return found_markers


def _as_list(value):
    if isinstance(value, list):
        return value
    if value:
        return [value]
    return []


def _load_task_commit_context(task: dict, meta: dict, task_result: dict, changed_files: list[str]) -> dict:
    contract = {}
    contract_path = meta.get("task_contract_path") or common.contract_path(task["slot_key"], task.get("slug") or "task", task["date_folder"])
    if os.path.exists(contract_path):
        try:
            with open(contract_path, "r", encoding="utf-8") as handle:
                contract = json.load(handle)
        except Exception:
            contract = {}

    integration_group = (
        meta.get("integration_group")
        or contract.get("integration_group")
        or contract.get("group")
        or task.get("slug")
        or task.get("title")
        or ""
    )
    depends_on_tasks = (
        meta.get("depends_on_tasks")
        or contract.get("depends_on_tasks")
        or contract.get("depends_on_task_ids")
        or []
    )
    depends_on_commits = (
        meta.get("depends_on_commits")
        or contract.get("depends_on_commits")
        or []
    )
    committable_paths = common.filter_committable_paths(changed_files)
    high_conflict_paths = [path for path in committable_paths if common.is_high_conflict_path(path)]
    review_priority = "high" if high_conflict_paths else "normal"
    safe_to_autocommit = bool(
        task.get("status") == "COMPLETED"
        and task_result.get("gate_verdict") == "PASS"
        and committable_paths
    )
    return {
        "contract": contract,
        "integration_group": str(integration_group or "").strip(),
        "depends_on_tasks": _as_list(depends_on_tasks),
        "depends_on_commits": _as_list(depends_on_commits),
        "committable_paths": committable_paths,
        "high_conflict_paths": high_conflict_paths,
        "review_priority": review_priority,
        "safe_to_autocommit": safe_to_autocommit,
    }


def _record_git_commit_state(task: dict, task_result: dict, changed_files: list[str], commit_info: dict):
    db.upsert_task_git_commit(
        task_id=task["id"],
        slot_key=task["slot_key"],
        task_title=task.get("title"),
        source_branch=commit_info.get("source_branch"),
        commit_sha=commit_info.get("commit_sha"),
        commit_message=commit_info.get("commit_message"),
        integration_group=commit_info.get("integration_group"),
        review_priority=commit_info.get("review_priority", "normal"),
        safe_to_autocommit=commit_info.get("safe_to_autocommit", False),
        status=commit_info.get("status", "SKIPPED_GIT_COMMIT"),
        reviewer_role=commit_info.get("reviewer_role"),
        reviewed_at=commit_info.get("reviewed_at"),
        merge_branch=commit_info.get("merge_branch"),
        merge_commit_sha=commit_info.get("merge_commit_sha"),
        reject_reason=commit_info.get("reject_reason"),
        superseded_by_task_id=commit_info.get("superseded_by_task_id"),
        superseded_by_commit_sha=commit_info.get("superseded_by_commit_sha"),
        changed_files=changed_files,
        depends_on_tasks=commit_info.get("depends_on_tasks"),
        depends_on_commits=commit_info.get("depends_on_commits"),
        high_conflict_paths=commit_info.get("high_conflict_paths"),
        task_status=task.get("status"),
        gate_verdict=task_result.get("gate_verdict"),
        gate_reason=task_result.get("gate_reason"),
    )


def _attempt_auto_commit(task: dict, meta: dict, task_result: dict, changed_files: list[str]) -> dict:
    context = _load_task_commit_context(task, meta, task_result, changed_files)
    current_branch = common.git_current_branch()
    commit_paths = context["committable_paths"]
    inbox_branch = common.git_branch_name_for_inbox(task["date_folder"], scope=common.derive_scope_from_paths(commit_paths))

    commit_info = {
        "status": "SKIPPED_GIT_COMMIT",
        "source_branch": current_branch,
        "merge_branch": None,
        "merge_commit_sha": None,
        "commit_sha": None,
        "commit_message": None,
        "reject_reason": "",
        "safe_to_autocommit": context["safe_to_autocommit"],
        "integration_group": context["integration_group"],
        "review_priority": context["review_priority"],
        "depends_on_tasks": context["depends_on_tasks"],
        "depends_on_commits": context["depends_on_commits"],
        "high_conflict_paths": context["high_conflict_paths"],
        "reviewer_role": "worker-auto",
    }

    if task.get("status") != "COMPLETED":
        commit_info["reject_reason"] = f"task status {task.get('status')} is not COMPLETED"
        return commit_info
    if task_result.get("gate_verdict") != "PASS":
        commit_info["reject_reason"] = f"gate verdict {task_result.get('gate_verdict')} is not PASS"
        return commit_info
    if not commit_paths:
        commit_info["reject_reason"] = "no committable files after filtering runtime artifacts"
        return commit_info

    title = str(task.get("title") or "Task").strip()
    subject = f"auto(task-{task['id']}): {title[:80]}"
    body_lines = [
        f"Task-ID: {task['id']}",
        f"Slot-Key: {task['slot_key']}",
        f"Planner-Provider: {meta.get('planner_provider') or meta.get('planner_requested_provider') or meta.get('planner_source') or 'unknown'}",
        f"Worker-Provider: {meta.get('worker_provider') or meta.get('worker_requested_provider') or meta.get('worker_runtime') or 'unknown'}",
        f"Gate-Verdict: {task_result.get('gate_verdict')}",
        f"Review-Priority: {context['review_priority']}",
    ]
    if context["integration_group"]:
        body_lines.append(f"Integration-Group: {context['integration_group']}")
    if context["depends_on_tasks"]:
        body_lines.append(f"Depends-On-Tasks: {json.dumps(context['depends_on_tasks'], ensure_ascii=False)}")
    if context["depends_on_commits"]:
        body_lines.append(f"Depends-On-Commits: {json.dumps(context['depends_on_commits'], ensure_ascii=False)}")
    if context["high_conflict_paths"]:
        body_lines.append(f"High-Conflict-Paths: {json.dumps(context['high_conflict_paths'], ensure_ascii=False)}")
    commit_body = "\n".join(body_lines)

    with common.git_ops_lock():
        if current_branch != inbox_branch:
            ok, output = common.git_checkout_branch(inbox_branch)
            if not ok:
                commit_info["reject_reason"] = f"failed to checkout inbox branch {inbox_branch}: {output}"
                return commit_info

        ok, commit_sha, output = common.git_commit_selected_files(
            commit_paths,
            subject=subject,
            body=commit_body,
        )
        if not ok:
            commit_info["reject_reason"] = output
            return commit_info

    commit_info.update({
        "status": "PENDING_REVIEW",
        "commit_sha": commit_sha,
        "commit_message": f"{subject}\n\n{commit_body}",
        "merge_branch": inbox_branch,
        "reject_reason": "",
        "safe_to_autocommit": True,
        "reviewer_role": "worker-auto",
    })
    return commit_info


def _violates_forbidden_changes(changed_files: list[str], forbidden_rules: list[str]) -> list[str]:
    violations = []
    for path in changed_files:
        for rule in forbidden_rules:
            r = str(rule or "").strip()
            if not r:
                continue
            # Prefix-like rule for strategy state files.
            if r.endswith("_"):
                if path.startswith(r):
                    violations.append(path)
            elif path == r or path.startswith(r.rstrip("/") + "/"):
                violations.append(path)
    return sorted(set(violations))


def _is_environment_blocking_error(error_markers_hit: list[str]) -> bool:
    """Check if error markers indicate environment/quota blocking (not worker code failure)."""
    blocking_markers = {
        "no quota",
        "you have no quota",
        "weekly rate limit",
        "reached your weekly rate limit",
        "you've reached your weekly rate limit",
        "please wait for your limit to reset",
        "switch to auto model to continue",
        "third-party mcp servers are disabled",
        "429",
        "403",
    }
    return any(marker in blocking_markers for marker in error_markers_hit)


def _build_and_gate_task_result(
    task: dict,
    status: str,
    duration: int,
    changed_files: list[str],
    codex_output: str,
    error_markers_hit: list[str],
    contract: dict,
    contract_valid: bool,
    contract_reason: str,
    completed_file_path: str,
) -> tuple[dict, str, str]:
    """
    Returns: (task_result_json, final_status, gate_verdict)
    """
    acceptance_tests = contract.get("acceptance_tests", []) if isinstance(contract, dict) else []
    required_outputs = contract.get("required_outputs", []) if isinstance(contract, dict) else []
    forbidden_changes = contract.get("forbidden_changes", []) if isinstance(contract, dict) else []

    output_present = bool(codex_output.strip())
    required_output_map = {
        "completed_markdown": bool(completed_file_path),
        "task_result_json": True,  # will be written right after build
        "changed_files_list": True,
    }
    missing_required = [name for name in required_outputs if not required_output_map.get(name, False)]
    violations = _violates_forbidden_changes(changed_files, forbidden_changes if isinstance(forbidden_changes, list) else [])
    no_effective_delivery = (not changed_files) and (bool(error_markers_hit) or not output_present)
    is_env_blocked = _is_environment_blocking_error(error_markers_hit)

    acceptance_results = []
    for item in acceptance_tests:
        acceptance_results.append({
            "name": str(item),
            "passed": output_present and not bool(error_markers_hit) and not no_effective_delivery,
            "evidence": (
                "worker_stdout_tail_present"
                if output_present and not no_effective_delivery
                else "no_effective_delivery"
            ),
        })

    gate_verdict = "PASS"
    final_status = status
    gate_reason = ""
    if not contract_valid:
        gate_verdict = "INVALID_DELIVERY"
        final_status = "REPLAN_REQUIRED"
        gate_reason = contract_reason
    elif missing_required:
        gate_verdict = "FAILED_ACCEPTANCE"
        final_status = "REPLAN_REQUIRED"
        gate_reason = f"missing required outputs: {', '.join(missing_required)}"
    elif no_effective_delivery:
        gate_verdict = "FAILED_ACCEPTANCE"
        final_status = "REPLAN_REQUIRED"
        gate_reason = "no effective delivery: no changed files and no valid runtime output"
    elif violations:
        gate_verdict = "POLICY_VIOLATION"
        final_status = "REPLAN_REQUIRED"
        gate_reason = f"forbidden changes detected: {', '.join(violations[:5])}"
    elif status == "FAILED":
        if is_env_blocked:
            gate_verdict = "BLOCKED_ENV"
            final_status = "BLOCKED_ENV"
            gate_reason = f"environment execution blocked: {error_markers_hit[0] if error_markers_hit else 'unknown'}"
        else:
            gate_verdict = "WORKER_RUNTIME_FAILED"
            final_status = "FAILED"
            gate_reason = "worker runtime failure markers detected"

    task_result = {
        "version": "1.0",
        "task_id": task.get("id"),
        "slot_key": task.get("slot_key"),
        "title": task.get("title"),
        "status": final_status,
        "gate_verdict": gate_verdict,
        "gate_reason": gate_reason,
        "duration_seconds": duration,
        "changed_files": changed_files,
        "error_markers_hit": error_markers_hit,
        "required_outputs": required_outputs,
        "missing_required_outputs": missing_required,
        "forbidden_change_violations": violations,
        "acceptance_results": acceptance_results,
        "next_action": (
            "Planner must replan from task_result gate_reason and handoff_questions."
            if final_status == "REPLAN_REQUIRED"
            else "Continue to next planned task."
        ),
    }
    return task_result, final_status, gate_verdict


def _finalize(lock: dict):
    """Codex process is dead — write completed file, update DB."""
    task_id = lock["task_id"]
    task = db.get_task(task_id)
    if not task:
        db.clear_worker_lock()
        return

    slot_key = task["slot_key"]
    slug = task["slug"] or "task"
    date_folder = task["date_folder"]

    log_path = common.find_stdout_log_path(slot_key, date_folder)
    codex_output = ""
    if os.path.exists(log_path):
        with open(log_path) as f:
            codex_output = f.read()

    changed_files_now = common.git_changed_files()
    meta = common.read_meta(slot_key, date_folder)
    worker_runtime = meta.get("worker_runtime", "codex")
    requested_provider = meta.get("worker_requested_provider", meta.get("worker_provider", worker_runtime))
    fallback_reason = meta.get("worker_fallback_reason")
    execution_mode = meta.get("worker_execution_mode", "direct")
    baseline_changed_files = set(meta.get("baseline_changed_files") or [])
    changed_files = sorted(set(changed_files_now) - baseline_changed_files)

    # Determine runtime status heuristically from worker output because we do not
    # retain the original process handle / exit code across launchd ticks.
    output_lower = codex_output.lower()
    error_markers_hit = _check_worker_runtime_errors(output_lower)
    # 若輸出包含明確失敗訊號（例如 quota/policy/auth），必定標 FAILED。
    # 否則再看是否有產出與異動。
    has_output = bool(codex_output.strip())
    has_changes = bool(changed_files)
    fatal_error = bool(error_markers_hit)
    if fatal_error:
        status = "FAILED"
    elif not has_output and not has_changes:
        status = "FAILED"
    elif has_output and not has_changes and len(codex_output.strip()) < 120:
        # Avoid treating a tiny one-line runtime message as a successful delivery.
        status = "FAILED"
    else:
        status = "COMPLETED"

    started_at = task.get("started_at") or lock.get("started_at") or datetime.now(timezone.utc).isoformat()
    try:
        started_dt = datetime.fromisoformat(started_at)
        if started_dt.tzinfo is None:
            started_dt = started_dt.replace(tzinfo=timezone.utc)
        else:
            started_dt = started_dt.astimezone(timezone.utc)
        duration = int((datetime.now(timezone.utc) - started_dt).total_seconds())
    except Exception:
        duration = 0

    completed_text_parts = [
        f"## 執行摘要\n\n狀態：{status}，耗時：{duration}s\n",
        (
            "執行器資訊：\n"
            f"- 請求：{requested_provider}\n"
            f"- 實際：{worker_runtime}\n"
            f"- 模式：{execution_mode}\n"
            + (f"- Fallback：{fallback_reason}\n" if fallback_reason else "")
        ),
        "## 異動檔案清單\n\n" + ("\n".join(f"- {f}" for f in changed_files) if changed_files else "（無異動）"),
        f"## Worker 輸出（後 200 行）\n\n```\n{codex_output[-4000:]}\n```",
        "## 驗證結果\n\n（請人工確認）",
        "## 阻塞 / 風險\n\n（請人工填寫）",
    ]
    completed_text = "\n\n".join(completed_text_parts)

    c_path = common.completed_path(slot_key, slug, date_folder)
    with open(c_path, "w") as f:
        f.write(f"# Completed: {task['title']}\n\n")
        f.write(completed_text)

    contract_path = common.contract_path(slot_key, slug, date_folder)
    contract = {}
    contract_valid = False
    contract_reason = "task contract missing"
    if os.path.exists(contract_path):
        try:
            with open(contract_path, "r", encoding="utf-8") as f:
                contract = json.load(f)
            contract_valid, contract_reason = common.validate_task_contract(contract)
        except Exception as exc:
            contract_valid = False
            contract_reason = f"failed to parse contract: {exc}"

    task_result, final_status, gate_verdict = _build_and_gate_task_result(
        task=task,
        status=status,
        duration=duration,
        changed_files=changed_files,
        codex_output=codex_output,
        error_markers_hit=error_markers_hit,
        contract=contract,
        contract_valid=contract_valid,
        contract_reason=contract_reason,
        completed_file_path=c_path,
    )
    result_path = common.result_path(slot_key, slug, date_folder)
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(task_result, f, ensure_ascii=False, indent=2)

    error_message = ""
    if final_status in ("FAILED", "REPLAN_REQUIRED"):
        error_message = task_result.get("gate_reason", "") or (", ".join(error_markers_hit[:3]) if error_markers_hit else "")

    db.update_task(
        task_id,
        status=final_status,
        completed_file_path=c_path,
        completed_text=completed_text,
        changed_files_json=json.dumps(changed_files, ensure_ascii=False),
        completed_at=datetime.now(timezone.utc).isoformat(),
        duration_seconds=duration,
        error_message=error_message,
    )
    # read_meta includes slot_key/date_folder keys; avoid passing them twice.
    safe_meta = {
        k: v for k, v in (meta or {}).items()
        if k not in ("slot_key", "date_folder")
    }

    git_commit_info = _attempt_auto_commit(task, safe_meta, task_result, changed_files)
    _record_git_commit_state(task, task_result, changed_files, git_commit_info)
    common.write_meta(
        slot_key,
        date_folder,
        **{
            **safe_meta,
            "task_id": task_id,
            "title": task["title"],
            "slug": slug,
            "status": final_status,
            "duration_seconds": duration,
            "changed_files": changed_files,
            "task_contract_path": contract_path,
            "task_result_path": result_path,
            "gate_verdict": gate_verdict,
            "gate_reason": task_result.get("gate_reason", ""),
            "git_commit_status": git_commit_info.get("status"),
            "git_commit_sha": git_commit_info.get("commit_sha"),
            "git_source_branch": git_commit_info.get("source_branch"),
            "git_inbox_branch": git_commit_info.get("merge_branch"),
            "git_commit_reason": git_commit_info.get("reject_reason"),
        },
    )
    db.clear_worker_lock()

    msg = (
        f"Task {task_id} finalized as {final_status} "
        f"({duration}s, {len(changed_files)} files changed, gate={gate_verdict})"
    )
    logger.info(msg)
    db.log_tick(RUNNER, "WORKER_FINALIZED", task_id=task_id, message=msg)
    common.log_jsonl(
        RUNNER,
        "WORKER_FINALIZED",
        task_id=task_id,
        status=final_status,
        gate_verdict=gate_verdict,
    )
    # Keep backlog status snapshot in sync after every finalized task.
    common.refresh_backlog_auto_status()


def _log_idle_seconds(path: str):
    try:
        mtime = os.path.getmtime(path)
        return max(0, int(time.time() - mtime))
    except OSError:
        return None


def _read_log_tail(path: str, max_chars: int = 6000) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()[-max_chars:]
    except OSError:
        return ""


def _copilot_permission_blocked(log_tail: str) -> bool:
    s = (log_tail or "").lower()
    markers = [
        "permission denied and could not request permission from user",
        "could not request permission from user",
        "cannot request permission from user",
        "tool permission",
    ]
    return any(marker in s for marker in markers)


def _claim(task: dict):
    """Claim a QUEUED task and launch the resolved worker runtime."""
    task_id = task["id"]
    slot_key = task["slot_key"]
    slug = task["slug"] or "task"
    date_folder = task["date_folder"]
    prompt_path = task.get("prompt_file_path", "")
    worker_provider = db.get_worker_provider()

    if not prompt_path or not os.path.exists(prompt_path):
        msg = f"Task {task_id} prompt file missing: {prompt_path}"
        logger.error(msg)
        db.update_task(task_id, status="FAILED", error_message=msg)
        db.log_tick(RUNNER, "WORKER_FAILED", task_id=task_id, message=msg)
        return

    log_path = common.worker_stdout_log_path(slot_key, date_folder)

    with open(prompt_path) as f:
        prompt_content = f.read()

    log_file = open(log_path, "w")
    try:
        resolution = common.worker_command(prompt_content, worker_provider)
    except FileNotFoundError as e:
        log_file.write(f"{e}\n")
        log_file.close()
        msg = f"Task {task_id} worker provider '{worker_provider}' unavailable: {e}"
        logger.error(msg)
        db.update_task(task_id, status="FAILED", error_message=msg)
        common.write_meta(
            slot_key,
            date_folder,
            task_id=task_id,
            title=task["title"],
            slug=slug,
            status="FAILED",
            error_message=msg,
            worker_provider=worker_provider,
        )
        db.log_tick(RUNNER, "WORKER_FAILED", task_id=task_id, message=msg)
        common.log_jsonl(RUNNER, "WORKER_FAILED", task_id=task_id, error=msg)
        return

    worker_runtime = resolution["runtime"]
    dispatch_provider = resolution.get("dispatch_provider", worker_runtime)
    requested_provider = resolution["requested_provider"]
    fallback_reason = resolution.get("fallback_reason")
    worker_model = resolution.get("model") or ""
    command = resolution["command"]
    execution_mode = "daemon" if requested_provider == "copilot-daemon" else "direct"
    baseline_changed_files = common.git_changed_files()

    proc = subprocess.Popen(
        command,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        cwd=common.ROOT,
        start_new_session=True,
    )
    log_file.close()

    db.update_task(task_id, status="RUNNING", worker_pid=proc.pid,
                   started_at=datetime.now(timezone.utc).isoformat())
    db.set_worker_lock(pid=proc.pid, task_id=task_id)
    common.write_meta(slot_key, date_folder,
                      task_id=task_id, title=task["title"], slug=slug,
                      status="RUNNING", worker_pid=proc.pid,
                      worker_runtime=worker_runtime,
                      worker_dispatch_provider=dispatch_provider,
                      worker_provider=worker_provider,
                      worker_requested_provider=requested_provider,
                      worker_model=worker_model,
                      worker_execution_mode=execution_mode,
                      worker_fallback_reason=fallback_reason,
                      baseline_changed_files=baseline_changed_files)

    msg = f"Task {task_id} claimed, {worker_runtime} PID={proc.pid}"
    logger.info(msg)
    db.log_tick(RUNNER, "WORKER_CLAIMED", task_id=task_id, message=msg)
    common.log_jsonl(RUNNER, "WORKER_CLAIMED", task_id=task_id, pid=proc.pid, worker_runtime=worker_runtime)

    if fallback_reason:
        fallback_msg = (
            f"Task {task_id} requested {requested_provider} but launched {worker_runtime}: "
            f"{fallback_reason}"
        )
        logger.warning(fallback_msg)
        db.log_tick(RUNNER, "WORKER_RUNTIME_FALLBACK", task_id=task_id, message=fallback_msg)
        common.log_jsonl(
            RUNNER,
            "WORKER_RUNTIME_FALLBACK",
            task_id=task_id,
            requested_provider=requested_provider,
            worker_runtime=worker_runtime,
            reason=fallback_reason,
        )


def run(force: bool = False):
    common.ensure_dirs()
    lock = db.get_worker_lock()
    scheduler_enabled = db.is_scheduler_enabled()
    worker_provider = db.get_worker_provider()

    if lock and lock["pid"]:
        pid = lock["pid"]
        task_id = lock["task_id"]
        task = db.get_task(task_id) if task_id else None
        meta = common.read_meta(task["slot_key"], task["date_folder"]) if task else {}
        worker_runtime = meta.get("worker_runtime", "codex")

        # Check 8-hour timeout
        if task and task.get("started_at"):
            try:
                started = datetime.fromisoformat(task["started_at"])
                if started.tzinfo is None:
                    started = started.replace(tzinfo=timezone.utc)
                else:
                    started = started.astimezone(timezone.utc)
                elapsed = (datetime.now(timezone.utc) - started).total_seconds()
                if elapsed > common.WORKER_MAX_SECONDS and common.is_process_alive(pid):
                    logger.warning(f"Task {task_id} exceeded {common.WORKER_MAX_SECONDS}s — killing")
                    common.kill_process_tree(pid)
            except Exception:
                pass

        if common.is_process_alive(pid):
            # Copilot special guard: process alive but log stalled for too long => likely hung.
            if task and worker_runtime == "copilot":
                log_path = common.find_stdout_log_path(task["slot_key"], task["date_folder"])
                tail = _read_log_tail(log_path)
                if _copilot_permission_blocked(tail):
                    msg = f"Task {task_id} blocked by Copilot permission gate; force finalize"
                    logger.warning(msg)
                    db.log_tick(RUNNER, "WORKER_PERMISSION_BLOCKED", task_id=task_id, message=msg)
                    common.log_jsonl(RUNNER, "WORKER_PERMISSION_BLOCKED", task_id=task_id, pid=pid)
                    common.kill_process_tree(pid)
                    _finalize(lock)
                    return
                idle_seconds = _log_idle_seconds(log_path)
                if idle_seconds is not None and idle_seconds > COPILOT_STALE_LOG_TIMEOUT_SECONDS:
                    msg = (
                        f"Task {task_id} appears stuck: copilot process alive but log idle "
                        f"{idle_seconds}s (> {COPILOT_STALE_LOG_TIMEOUT_SECONDS}s)"
                    )
                    logger.warning(msg)
                    db.log_tick(RUNNER, "WORKER_STUCK_TIMEOUT", task_id=task_id, message=msg)
                    common.log_jsonl(RUNNER, "WORKER_STUCK_TIMEOUT", task_id=task_id, pid=pid, idle_seconds=idle_seconds)
                    common.kill_process_tree(pid)
                    _finalize(lock)
                    return

            if not scheduler_enabled:
                msg = f"Scheduler disabled; task {task_id} still running (PID={pid}), no new claim"
                logger.info(msg)
                db.log_tick(RUNNER, "WORKER_SKIP_DISABLED_RUNNING", task_id=task_id, message=msg)
                common.log_jsonl(RUNNER, "WORKER_SKIP_DISABLED_RUNNING", task_id=task_id, pid=pid)
                return
            db.update_worker_heartbeat()
            msg = f"Task {task_id} still running (PID={pid})"
            logger.info(msg)
            db.log_tick(RUNNER, "WORKER_HEARTBEAT", task_id=task_id, message=msg)
            common.log_jsonl(RUNNER, "WORKER_HEARTBEAT", task_id=task_id, pid=pid)
            return
        else:
            logger.info(f"Task {task_id} PID={pid} is dead — finalizing")
            _finalize(lock)

    if not scheduler_enabled and not force:
        msg = "Scheduler is disabled — worker skip claiming new task"
        logger.info(msg)
        db.log_tick(RUNNER, "WORKER_SKIP_DISABLED", message=msg)
        common.log_jsonl(RUNNER, "WORKER_SKIP_DISABLED")
        return

    if worker_provider == "copilot-daemon":
        msg = "Worker provider is copilot-daemon — resident daemon will claim queued tasks"
        logger.info(msg)
        db.log_tick(RUNNER, "WORKER_SKIP_DAEMON_PROVIDER", message=msg)
        common.log_jsonl(RUNNER, "WORKER_SKIP_DAEMON_PROVIDER")
        return

    # Try to claim a new QUEUED task
    queued = db.list_tasks(status="QUEUED", limit=1)
    if not queued:
        msg = "No QUEUED tasks available"
        logger.info(msg)
        db.log_tick(RUNNER, "WORKER_SKIP_IDLE_NO_TASK", message=msg)
        common.log_jsonl(RUNNER, "WORKER_SKIP_IDLE_NO_TASK")
        return

    _claim(queued[0])


if __name__ == "__main__":
    db.init_db()
    force_run = str(os.environ.get("ORCHESTRATOR_FORCE_RUN", "")).strip().lower() in ("1", "true", "yes", "on")
    run(force=force_run)
