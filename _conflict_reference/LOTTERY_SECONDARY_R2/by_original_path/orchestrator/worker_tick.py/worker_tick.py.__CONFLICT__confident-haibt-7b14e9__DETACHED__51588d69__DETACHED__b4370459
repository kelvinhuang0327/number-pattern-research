"""
Betting-pool Orchestrator Worker Tick
Betting-pool 任務執行管線 — claim、執行、失敗分類、結果寫入
"""

import os
import shutil
import uuid
import json
import subprocess
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from orchestrator import db
from orchestrator import execution_policy

logger = logging.getLogger(__name__)

_LLM_EXECUTION_PROVIDERS = {"claude", "codex", "copilot", "copilot-daemon"}

# ── Worker 錯誤分類常數 ────────────────────────────────────────────────
# Rate limit 關鍵字：從輸出文字判斷是否需要 FAILED_RATE_LIMIT 狀態
_RATE_LIMIT_MARKERS = (
    "rate limit", "weekly rate limit", "you've hit your rate limit",
    "usage limit", "hit your usage limit", "you've hit your usage limit",  # codex quota
    "try again at", "purchase more credits",                              # codex quota msg
    "premium request limit", "429", "quota exceeded",
)
# 環境封鎖關鍵字：provider 驗證/權限失敗 → BLOCKED_ENV（非 worker 程式問題）
_ENV_BLOCK_MARKERS = (
    "permission denied", "auth failed", "not logged in",
    "403 forbidden", "http 403", "status: 403",
    "mcp servers are disabled", "third-party mcp",
)


def _detect_failure_status(output: str, error_message: str) -> str:
    """
    依輸出文字分析 Worker 失敗後應設定的狀態。

    優先序：
    1. Rate limit / quota → FAILED_RATE_LIMIT（provider 冷卻，等待解除）
    2. 環境封鎖 / 驗證失敗 → BLOCKED_ENV（基礎設施問題，非程式碼錯誤）
    3. 其他 → FAILED
    """
    combined = (output + " " + error_message).lower()
    if any(m in combined for m in _RATE_LIMIT_MARKERS):
        return "FAILED_RATE_LIMIT"
    if any(m in combined for m in _ENV_BLOCK_MARKERS):
        return "BLOCKED_ENV"
    return "FAILED"


def _provider_requires_llm(provider: str) -> bool:
    return str(provider or "").strip().lower() in _LLM_EXECUTION_PROVIDERS


def _llm_block_reason(provider: str) -> Optional[str]:
    if not _provider_requires_llm(provider):
        return None
    decision = execution_policy.evaluate_execution(
        runner="worker_tick",
        requires_llm=True,
        background=True,
        manual_override=execution_policy.is_manual_run(os.environ),
    )
    return decision["reason"]


def _assert_llm_execution_allowed(provider: str, runner: str) -> None:
    # Phase 0: ProviderFactory 角色守衛——Worker 呼叫外部 LLM 前先確認
    from orchestrator.provider_factory import ProviderFactory
    ProviderFactory.assert_role_allowed("worker", provider)

    reason = _llm_block_reason(provider)
    if reason:
        execution_policy.record_llm_block(runner=runner, provider=provider, reason=reason)
        raise RuntimeError(execution_policy.evaluate_execution(
            runner=runner,
            requires_llm=True,
            background=True,
            manual_override=execution_policy.is_manual_run(os.environ),
        )["message"])
    execution_policy.record_llm_call(runner=runner, provider=provider, context="worker_provider_boundary")


def _log_exec_result(
    *,
    provider: str,
    task_id: int,
    success: bool,
    source_function: str,
    error: Optional[str] = None,
    raw_text: Optional[str] = None,
) -> None:
    """執行後補充 usage 記錄（post-execution: 含 success / tokens / rate_limit）。"""
    try:
        from orchestrator.llm_usage_logger import log_usage
        log_usage(
            runner="worker",
            role="worker",
            provider=provider,
            blocked=False,
            allowed=True,
            task_id=task_id,
            success=success,
            error=error,
            raw_usage_text=raw_text,
            source_file="orchestrator/worker_tick.py",
            source_function=source_function,
            entrypoint="post_execution",
            caller_skip_frames=4,
        )
    except Exception:  # noqa: BLE001
        pass


def _list_dirty_files(project_root: str) -> list[str]:
    """取得目前工作樹的 dirty files。"""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            capture_output=True,
            text=True,
            cwd=project_root,
            timeout=10,
        )
        if result.returncode == 0:
            files = [f.strip() for f in result.stdout.splitlines() if f.strip()]
            return files
        # fallback: uncommitted changes relative to index
        result2 = subprocess.run(
            ["git", "diff", "--name-only"],
            capture_output=True,
            text=True,
            cwd=project_root,
            timeout=10,
        )
        return [f.strip() for f in result2.stdout.splitlines() if f.strip()]
    except Exception:
        return []


def _collect_task_changed_files(
    before_dirty_files: list[str],
    after_dirty_files: list[str],
    reported_files: Optional[list[str]] = None,
) -> list[str]:
    """只保留本次 task 新增的 repo 變更，外加 task 自己回報的產物檔案。"""
    before_set = {path for path in before_dirty_files if path}
    task_delta = [path for path in after_dirty_files if path and path not in before_set]

    combined: list[str] = []
    for path in task_delta + list(reported_files or []):
        if path and path not in combined:
            combined.append(path)
    return combined


def execute_task_with_provider(task: dict, provider: str) -> dict:
    """使用指定 Provider 執行任務。model_patch_* 任務走真實研究路徑。"""
    sst = task.get("signal_state_type") or ""
    if sst.startswith("model_patch_"):
        return execute_model_patch_task(task)

    if provider == "claude":
        return execute_task_with_claude(task)
    elif provider == "codex":
        return execute_task_with_codex(task)
    elif provider in ["copilot", "copilot-daemon"]:
        return execute_task_with_copilot(task, provider)
    else:
        raise ValueError(f"Unsupported provider: {provider}")


def execute_model_patch_task(task: dict) -> dict:
    """
    執行 model_patch_* 任務的真實研究路徑。
    目前支援: model_patch_calibration → calibration_patch_runner

    完成門檻（Completion Gate）：
    - 必須成功產出 before/after snapshot artifacts
    - 必須記錄真實指標（brier_delta、method）
    - 缺失任一 → status = FAILED_STUB（強制重試）
    """
    sst = task.get("signal_state_type", "")
    task_id = task["id"]
    logger.info("[Worker] model_patch task #%d (%s) → real research executor", task_id, sst)

    if sst == "model_patch_calibration":
        return _run_calibration_patch(task)

    # 其他 model_patch_* 類別：尚未實作真實執行器，誠實記錄
    return {
        "success": False,
        "completed_text": f"FAILED_STUB: no real executor implemented for {sst}",
        "changed_files": [],
        "execution_log": f"Patch type '{sst}' has no research executor yet",
        "stub": True,
    }


def _run_calibration_patch(task: dict) -> dict:
    """呼叫 calibration_patch_runner 並強制驗證 artifacts 存在。"""
    task_id = task["id"]
    try:
        from wbc_backend.research.calibration_patch_runner import (
            artifacts_exist,
            build_completion_text,
            run_calibration_patch,
        )
        manifest = run_calibration_patch(task_id)
    except Exception as exc:
        logger.exception("[Worker] calibration_patch_runner 執行失敗 task #%d", task_id)
        return {
            "success": False,
            "completed_text": f"FAILED_ERROR: {exc}",
            "changed_files": [],
            "execution_log": str(exc),
            "stub": False,
        }

    # Completion Gate: 若 artifacts 不存在或狀態非 SUCCESS → FAILED_STUB
    if manifest.status != "SUCCESS" or not artifacts_exist(task_id):
        failure_text = (
            f"FAILED_STUB: calibration patch did not produce valid artifacts.\n"
            f"Status: {manifest.status}\n"
            f"Reason: {manifest.failure_reason}"
        )
        logger.warning("[Worker] Completion gate FAILED for task #%d: %s", task_id, manifest.failure_reason)
        return {
            "success": False,
            "completed_text": failure_text,
            "changed_files": [],
            "execution_log": failure_text,
            "stub": False,
        }

    completed_text = build_completion_text(manifest)
    changed_files = [
        manifest.before_snapshot_path,
        manifest.after_snapshot_path,
    ]

    logger.info(
        "[Worker] Calibration patch task #%d COMPLETED — %s — Brier Δ%+.4f",
        task_id, manifest.calibration_method, manifest.brier_delta,
    )
    return {
        "success": True,
        "completed_text": completed_text,
        "changed_files": changed_files,
        "execution_log": f"Calibration patch SUCCESS: {manifest.calibration_method}",
        "stub": False,
        "manifest": {
            "status": manifest.status,
            "calibration_method": manifest.calibration_method,
            "brier_delta": manifest.brier_delta,
            "before_snapshot_path": manifest.before_snapshot_path,
            "after_snapshot_path":  manifest.after_snapshot_path,
        },
    }


def execute_task_with_claude(task: dict) -> dict:
    """
    使用 Claude CLI 真實執行任務。

    流程:
    1. 讀取 prompt_file_path 的內容
    2. 記錄執行前 git dirty files
    3. 透過 `claude -p - --output-format text --dangerously-skip-permissions` (stdin) 執行
    4. 記錄執行後 git dirty files，計算差異作為 changed_files
    5. 寫入 completed_path 並回傳結果
    """
    task_id = task["id"]
    _assert_llm_execution_allowed("claude", "worker_tick")
    logger.info("[Worker] Executing task #%d with Claude (real)", task_id)

    project_root = str(Path(__file__).resolve().parents[1])

    # ── 讀取 prompt ─────────────────────────────────────────────────────────
    prompt_path = task.get("prompt_file_path", "")
    if not prompt_path or not os.path.exists(prompt_path):
        raise RuntimeError(f"Prompt file not found: {prompt_path!r}")

    with open(prompt_path, "r", encoding="utf-8") as fh:
        prompt_content = fh.read()

    task_dir = os.path.dirname(prompt_path)
    completed_path = os.path.join(task_dir, f"{task['slot_key']}-completed.md")

    # ── 執行前 dirty files ──────────────────────────────────────────────────
    before_dirty = _list_dirty_files(project_root)

    # ── 計算 timeout ────────────────────────────────────────────────────────
    expected_hours = float(task.get("expected_duration_hours") or 2.0)
    timeout_sec = int(expected_hours * 3600) + 1800  # +30min buffer

    # ── 找 claude binary ─────────────────────────────────────────────────────
    claude_bin = shutil.which("claude") or os.path.expanduser("~/.local/bin/claude")
    if not os.path.isfile(claude_bin):
        raise RuntimeError(f"claude binary not found at {claude_bin!r}")

    cmd = [
        claude_bin,
        "-p", "-",                          # read prompt from stdin (-p -)
        "--output-format", "text",
        "--dangerously-skip-permissions",   # non-interactive
    ]
    logger.debug("[Worker] claude cmd: %s", " ".join(cmd))

    # ── 執行 Claude ──────────────────────────────────────────────────────────
    try:
        proc = subprocess.run(
            cmd,
            input=prompt_content,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            cwd=project_root,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"[Claude] task #{task_id} timed out after {timeout_sec}s"
        ) from exc

    # ── 讀取輸出 ────────────────────────────────────────────────────────────
    completed_text = proc.stdout or ""

    # ── 執行後 dirty files ──────────────────────────────────────────────────
    after_dirty = _list_dirty_files(project_root)
    changed_files = _collect_task_changed_files(before_dirty, after_dirty, [completed_path])

    # ── 判斷成功/失敗 ───────────────────────────────────────────────────────
    raw_output = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0:
        stderr_snippet = (proc.stderr or "")[:800]
        _log_exec_result(
            provider="claude",
            task_id=task_id,
            success=False,
            source_function="execute_task_with_claude",
            error=f"[Claude] exited with code {proc.returncode}: {stderr_snippet}",
            raw_text=raw_output[:500],
        )
        raise RuntimeError(
            f"[Claude] exited with code {proc.returncode}: {stderr_snippet}"
        )

    # ── 寫入 completed file ──────────────────────────────────────────────────
    with open(completed_path, "w", encoding="utf-8") as fh:
        fh.write(completed_text)

    _log_exec_result(
        provider="claude",
        task_id=task_id,
        success=True,
        source_function="execute_task_with_claude",
        raw_text=raw_output[:500],
    )
    logger.info(
        "[Worker] task #%d completed with Claude: %d changed files",
        task_id, len(changed_files),
    )
    return {
        "success": True,
        "completed_file_path": completed_path,
        "completed_text": completed_text,
        "changed_files": changed_files,
        "execution_log": completed_text[:2000],
    }


def execute_task_with_codex(task: dict) -> dict:
    """
    使用 Codex CLI 真實執行任務。

    流程:
    1. 讀取 prompt_file_path 的內容
    2. 記錄執行前 git dirty files
    3. 透過 `codex exec -C <root> --ephemeral -o <completed> -` (stdin) 執行
    4. 記錄執行後 git dirty files，計算差異作為 changed_files
    5. 寫入 completed_path 並回傳結果
    """
    task_id = task["id"]
    _assert_llm_execution_allowed("codex", "worker_tick")
    logger.info("[Worker] Executing task #%d with Codex (real)", task_id)

    project_root = str(Path(__file__).resolve().parents[1])

    # ── 讀取 prompt ─────────────────────────────────────────────────────────
    prompt_path = task.get("prompt_file_path", "")
    if not prompt_path or not os.path.exists(prompt_path):
        raise RuntimeError(f"Prompt file not found: {prompt_path!r}")

    with open(prompt_path, "r", encoding="utf-8") as fh:
        prompt_content = fh.read()

    task_dir = os.path.dirname(prompt_path)
    completed_path = os.path.join(task_dir, f"{task['slot_key']}-completed.md")

    # ── 執行前 dirty files ──────────────────────────────────────────────────
    before_dirty = _list_dirty_files(project_root)

    # ── 計算 timeout ────────────────────────────────────────────────────────
    expected_hours = float(task.get("expected_duration_hours") or 2.0)
    timeout_sec = int(expected_hours * 3600) + 1800  # +30min buffer

    # ── 找 codex binary ─────────────────────────────────────────────────────
    codex_bin = shutil.which("codex") or "/opt/homebrew/bin/codex"
    if not os.path.isfile(codex_bin):
        raise RuntimeError(f"codex binary not found at {codex_bin!r}")

    cmd = [
        codex_bin, "exec",
        "-C", project_root,
        "--full-auto",   # non-interactive: approval=never
        "--ephemeral",
        "-o", completed_path,
        "-",  # read prompt from stdin
    ]
    logger.debug("[Worker] codex cmd: %s", " ".join(cmd))

    # ── 執行 Codex ──────────────────────────────────────────────────────────
    try:
        proc = subprocess.run(
            cmd,
            input=prompt_content,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            cwd=project_root,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"[Codex] task #{task_id} timed out after {timeout_sec}s"
        ) from exc

    # ── 讀取輸出 ────────────────────────────────────────────────────────────
    completed_text = ""
    if os.path.exists(completed_path):
        with open(completed_path, "r", encoding="utf-8") as fh:
            completed_text = fh.read()
    else:
        # -o file not written (error path) — fall back to stdout
        completed_text = proc.stdout or "(no codex output)"
        with open(completed_path, "w", encoding="utf-8") as fh:
            fh.write(completed_text)

    # ── 執行後 dirty files ──────────────────────────────────────────────────
    after_dirty = _list_dirty_files(project_root)
    changed_files = _collect_task_changed_files(before_dirty, after_dirty, [completed_path])

    # ── 判斷成功/失敗 ───────────────────────────────────────────────────────
    raw_output = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0:
        stderr_snippet = (proc.stderr or "")[:800]
        _log_exec_result(
            provider="codex",
            task_id=task_id,
            success=False,
            source_function="execute_task_with_codex",
            error=f"[Codex] exited with code {proc.returncode}: {stderr_snippet}",
            raw_text=raw_output[:500],
        )
        raise RuntimeError(
            f"[Codex] exited with code {proc.returncode}: {stderr_snippet}"
        )

    _log_exec_result(
        provider="codex",
        task_id=task_id,
        success=True,
        source_function="execute_task_with_codex",
        raw_text=raw_output[:500],
    )
    logger.info(
        "[Worker] task #%d completed with Codex: %d changed files",
        task_id, len(changed_files),
    )
    return {
        "success": True,
        "completed_file_path": completed_path,
        "completed_text": completed_text,
        "changed_files": changed_files,
        "execution_log": (proc.stdout or "")[:2000],
    }


def execute_task_with_copilot(task: dict, provider: str) -> dict:
    """
    copilot / copilot-daemon provider 路徑。

    - provider="copilot-daemon"：任務由 orchestrator/copilot_daemon.py 常駐進程管理，
      此函式通常不會被呼叫（daemon 自己處理 claim + execute）。
      若意外在此呼叫，fallback 到 codex exec。
    - provider="copilot"：每次 spawn `gh copilot suggest`，需要使用者 session keychain。
      若 gh 不可用，fallback 到 codex exec。
    """
    task_id = task["id"]
    _assert_llm_execution_allowed(provider, "worker_tick")

    if shutil.which("gh"):
        try:
            from orchestrator.copilot_daemon import _execute_task as _copilot_execute
            logger.info("[Worker] task #%d provider=%s → gh copilot", task_id, provider)
            return _copilot_execute(task)
        except Exception as exc:
            logger.warning(
                "[Worker] task #%d gh copilot failed (%s), fallback → codex", task_id, exc
            )

    logger.info("[Worker] task #%d provider=%s → codex exec (fallback)", task_id, provider)
    return execute_task_with_codex(task)


def _auto_fail_zombie_running_tasks() -> int:
    """
    掃描並自動修復殭屍 RUNNING 任務（超時未完成）。

    殭屍定義：status=RUNNING 但 age ≥ max(expected_duration × 3600 + 3600, 7200)。
    原因：Worker 行程崩潰或異常退出，任務永久卡住、阻斷 Planner。
    回傳已修復的任務數量。
    """
    running_tasks = db.list_tasks(status="RUNNING", limit=20)
    resolved = 0
    now = datetime.now(timezone.utc)

    for task in running_tasks:
        ts_str = (
            task.get("started_at")
            or task.get("updated_at")
            or task.get("created_at")
            or ""
        )
        age_seconds = 0.0
        if ts_str:
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                age_seconds = (now - ts).total_seconds()
            except ValueError:
                pass

        expected_hours = float(task.get("expected_duration_hours") or 2.0)
        zombie_timeout = max(expected_hours * 3600 + 3600, 7200)

        if age_seconds >= zombie_timeout:
            db.update_task(
                task["id"],
                status="FAILED",
                error_message=(
                    f"[WORKER_AUTO_RESOLVE] RUNNING → FAILED (zombie): "
                    f"no completion after {int(age_seconds)}s "
                    f"(timeout={int(zombie_timeout)}s, expected={expected_hours}h). "
                    + (task.get("error_message") or "")
                )[:500],
            )
            logger.warning(
                "[WorkerTick] WORKER_RESOLVED_ZOMBIE_RUNNING: task #%s → FAILED "
                "(age=%ds, timeout=%ds)",
                task["id"], int(age_seconds), int(zombie_timeout),
            )
            resolved += 1

    return resolved


def run_worker_tick() -> dict:
    """執行 Worker Tick"""
    start_time = datetime.now(timezone.utc)
    request_id = os.environ.get("ORCHESTRATOR_REQUEST_ID") or str(uuid.uuid4())
    task_id: Optional[int] = None  # sentinel: 讓 outer except 能安全更新 FAILED

    logger.info("[WorkerTick] Starting worker tick, request_id=%s", request_id)

    try:
        decision = execution_policy.evaluate_execution(
            runner="worker_tick",
            background=True,
            manual_override=execution_policy.is_manual_run(os.environ),
        )
        if not decision["allowed"]:
            message = decision["message"]
            db.record_run(
                runner="worker_tick",
                outcome="SKIPPED",
                request_id=request_id,
                message=message,
                tick_at=start_time.isoformat()
            )
            logger.info("[WorkerTick] %s", message)
            return {"status": "SKIPPED", "message": message}

        # ── 殭屍任務清理：先於 QUEUED 掃描之前執行 ────────────────────────
        zombie_resolved = _auto_fail_zombie_running_tasks()
        if zombie_resolved > 0:
            logger.info("[WorkerTick] Auto-resolved %d zombie RUNNING task(s)", zombie_resolved)
        # ────────────────────────────────────────────────────────────────────

        # 找到最舊的 QUEUED 任務
        queued_tasks = db.list_tasks(status="QUEUED", limit=1)
        if not queued_tasks:
            status_counts = db.count_tasks_by_status()
            replan_count = status_counts.get("REPLAN_REQUIRED", 0)
            total_tasks = sum(status_counts.values())
            message = (
                f"Worker skipped: no queued tasks available"
                f" ({replan_count} REPLAN_REQUIRED, total_tasks={total_tasks})"
            )
            db.record_run(
                runner="worker_tick",
                outcome="SKIPPED",
                request_id=request_id,
                message=message,
                tick_at=start_time.isoformat()
            )
            logger.info(f"[WorkerTick] {message}")
            return {
                "status": "SKIPPED",
                "message": message,
                "mining_needed": True,
                "replan_required_count": replan_count,
            }
        
        task = queued_tasks[0]
        task_id = task["id"]
        
        # 更新任務狀態為 RUNNING
        db.update_task(task_id, 
                      status="RUNNING", 
                      started_at=start_time.isoformat())
        
        logger.info(f"[WorkerTick] Starting execution of task #{task_id}: {task['title']}")
        
        # 取得 Worker Provider 設定
        worker_provider = db.get_worker_provider()
        
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        before_dirty_files = _list_dirty_files(project_root)

        # ── Phase 11: deterministic safe task bypass ───────────────────
        # closing_monitor (and future registered types) execute Python logic
        # directly — no LLM provider is invoked.
        from orchestrator.safe_task_executor import (
            is_deterministic_safe_task,
            execute_safe_task,
        )
        if is_deterministic_safe_task(task):
            logger.info(
                "[WorkerTick] Task #%d (type=%s) → deterministic safe executor (no LLM)",
                task_id, task.get("task_type"),
            )
            execution_result = execute_safe_task(task)
        else:
            # 執行任務（LLM provider path）
            execution_result = execute_task_with_provider(task, worker_provider)
        after_dirty_files = _list_dirty_files(project_root)
        changed_files = _collect_task_changed_files(
            before_dirty_files,
            after_dirty_files,
            execution_result.get("changed_files", []),
        )
        execution_result["changed_files"] = changed_files
        
        if execution_result["success"]:
            # 任務成功完成
            end_time = datetime.now(timezone.utc)
            duration = int((end_time - start_time).total_seconds())

            # ── Phase 10: 完成品質驗證 ────────────────────────────────
            from orchestrator.task_completion_validator import (
                validate_completion,
                QUALITY_INVALID_STATES,
            )
            quality_result = validate_completion(
                task,
                {**execution_result, "duration_seconds": duration},
            )
            completion_quality = quality_result["quality"]
            is_empty_completion = completion_quality in QUALITY_INVALID_STATES

            # 更新任務狀態
            update_data: dict = {
                "status": "COMPLETED",
                "completed_at": end_time.isoformat(),
                "duration_seconds": duration,
                "completed_file_path": execution_result.get("completed_file_path"),
                "completed_text": execution_result.get("completed_text"),
                "changed_files_json": json.dumps(execution_result.get("changed_files", [])),
                "completion_quality": completion_quality,
            }
            if is_empty_completion:
                update_data["error_message"] = (
                    f"[COMPLETION_QUALITY:{completion_quality}] {quality_result['reason']}"
                )
                logger.warning(
                    f"[WorkerTick] Task #{task_id} COMPLETED but quality={completion_quality}: "
                    f"{quality_result['reason']}"
                )
            db.update_task(task_id, **update_data)

            message = f"Worker completed task #{task_id}: {task['title']}"
            if is_empty_completion:
                message += f" [quality={completion_quality}]"
            db.record_run(
                runner="worker_tick",
                outcome="SUCCESS",
                request_id=request_id,
                task_id=task_id,
                message=message,
                tick_at=start_time.isoformat(),
                duration_seconds=duration,
                log_snippet=execution_result.get("execution_log", "")
            )

            logger.info(
                f"[WorkerTick] Completed task #{task_id} in {duration}s "
                f"quality={completion_quality}"
            )

            return {
                "status": "SUCCESS",
                "message": message,
                "task_id": task_id,
                "duration_seconds": duration,
                "changed_files": execution_result.get("changed_files", []),
                "completion_quality": completion_quality,
            }
        else:
            # 任務執行失敗
            end_time = datetime.now(timezone.utc)
            duration = int((end_time - start_time).total_seconds())

            error_message = execution_result.get("error_message", "Unknown execution error")
            output_text = (
                execution_result.get("completed_text", "")
                + " "
                + execution_result.get("execution_log", "")
            )

            # ── 失敗狀態分類 ────────────────────────────────────────────
            # FAILED_RATE_LIMIT → provider 冷卻中，Planner 下次可自動解除
            # BLOCKED_ENV       → 環境/驗證問題，等待 600s 後 Planner 自動解除
            # FAILED            → 其他執行失敗
            final_status = _detect_failure_status(output_text, error_message)

            # 更新任務狀態
            db.update_task(
                task_id,
                status=final_status,
                completed_at=end_time.isoformat(),
                duration_seconds=duration,
                error_message=error_message,
            )

            outcome_code = {
                "FAILED_RATE_LIMIT": "WORKER_FAILED_RATE_LIMIT",
                "BLOCKED_ENV": "WORKER_BLOCKED_ENV",
            }.get(final_status, "WORKER_FAILED")

            message = f"Worker failed task #{task_id} [{final_status}]: {error_message}"
            db.record_run(
                runner="worker_tick",
                outcome=outcome_code,
                request_id=request_id,
                task_id=task_id,
                message=message,
                tick_at=start_time.isoformat(),
                duration_seconds=duration,
            )

            logger.error("[WorkerTick] %s", message)

            return {
                "status": final_status,
                "outcome": outcome_code,
                "message": message,
                "task_id": task_id,
                "duration_seconds": duration,
                "error": error_message,
            }
            
    except Exception as e:
        end_time = datetime.now(timezone.utc)
        duration = int((end_time - start_time).total_seconds())

        error_message = f"Worker tick failed: {str(e)}"

        # ── 確保任務不會永久卡在 RUNNING ─────────────────────────────────
        # 若此時 task_id 已知且任務仍是 RUNNING，強制轉為 FAILED
        try:
            if task_id is not None:
                current = db.get_task(task_id) if hasattr(db, 'get_task') else None
                if current is None or current.get("status") == "RUNNING":
                    db.update_task(
                        task_id,
                        status="FAILED",
                        error_message=error_message[:500],
                        completed_at=end_time.isoformat(),
                        duration_seconds=duration,
                    )
        except Exception as db_err:
            logger.error("[WorkerTick] Failed to update task status in outer except: %s", db_err)
        # ─────────────────────────────────────────────────────────────────

        db.record_run(
            runner="worker_tick",
            outcome="FAILED",
            request_id=request_id,
            message=error_message,
            tick_at=start_time.isoformat(),
            duration_seconds=duration
        )

        logger.error("[WorkerTick] Critical failure: %s", e)

        return {
            "status": "FAILED",
            "message": error_message,
            "duration_seconds": duration
        }


if __name__ == "__main__":
    # 直接測試執行
    logging.basicConfig(level=logging.INFO)
    db.init_db()
    result = run_worker_tick()
    print(f"Worker tick result: {result}")
