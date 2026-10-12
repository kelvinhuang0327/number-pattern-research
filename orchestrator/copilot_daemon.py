"""
Betting-pool Copilot Daemon
============================
以 LaunchAgent 方式在使用者 GUI session 中常駐，
使 gh copilot CLI 可存取 macOS keychain。

每 10 秒 poll 一次：
  1. 確認 lock（上一個任務還在跑？）→ heartbeat / finalize
  2. worker_provider != "copilot-daemon" → 跳過
  3. scheduler disabled → 跳過
  4. 無 QUEUED 任務 → 跳過
  5. 領取任務 → 執行 → 更新任務狀態

啟動方式：
  .venv/bin/python orchestrator/copilot_daemon.py [--poll-seconds 10]

或透過 launchd LaunchAgent（推薦）：
  launchctl load ~/Library/LaunchAgents/com.bettingpool.orchestrator.copilot-daemon.plist
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ── 確保 import orchestrator package ─────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from orchestrator import db  # noqa: E402
from orchestrator import execution_policy  # noqa: E402
from orchestrator.common import (  # noqa: E402
    COPILOT_DAEMON_STATE_PATH,
    ORCH_RUNTIME_ROOT,
)
from orchestrator.provider_audit_guard import AuditGuard, AuditGuardBlockedError  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [copilot-daemon] %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Rate limit 偵測 ───────────────────────────────────────────────────────
_RATE_LIMIT_MARKERS = (
    "rate limit", "weekly rate limit", "you've hit your rate limit",
    "usage limit", "hit your usage limit", "you've hit your usage limit",
    "try again at", "purchase more credits",
    "premium request limit", "429", "quota exceeded",
)


def _detect_failure_status(error_text: str) -> str:
    """依錯誤訊息判斷應設定的任務狀態。"""
    low = error_text.lower()
    if any(m in low for m in _RATE_LIMIT_MARKERS):
        return "FAILED_RATE_LIMIT"
    return "FAILED"


# ── Copilot CLI 模式偵測 (Phase 36A) ─────────────────────────────────────────

_CLI_MODE_CACHE: Optional[str] = None
_CLI_MODE_CACHE_TIME: float = 0.0
_CLI_MODE_CACHE_TTL: float = 300.0  # 5 分鐘快取


def _detect_copilot_cli_mode_uncached() -> str:
    """實際偵測邏輯（不使用快取）。"""
    # 1. 新版 agent CLI：copilot binary 存在且支援 -p/--prompt
    copilot_bin = shutil.which("copilot")
    if copilot_bin and os.path.isfile(copilot_bin):
        try:
            r = subprocess.run(
                [copilot_bin, "--help"],
                capture_output=True, text=True, timeout=10,
            )
            if "--prompt" in (r.stdout + r.stderr):
                return "agent_cli"
        except Exception:  # noqa: BLE001
            pass

    # 2. 舊版 gh extension：gh copilot suggest --target 路徑
    gh_bin = shutil.which("gh")
    if gh_bin and os.path.isfile(gh_bin):
        try:
            r = subprocess.run(
                [gh_bin, "copilot", "suggest", "--help"],
                capture_output=True, text=True, timeout=10,
            )
            # 舊版 extension help 包含 --target (shell/git/gh)
            if "--target" in (r.stdout + r.stderr):
                return "gh_extension_legacy"
        except Exception:  # noqa: BLE001
            pass

    return "unavailable"


def detect_copilot_cli_mode() -> str:
    """
    偵測可用的 Copilot CLI 模式（含 TTL 快取）。

    Returns:
        "agent_cli"           — copilot binary (1.0+) 存在且支援 -p/--prompt
        "gh_extension_legacy" — 僅 gh copilot suggest --target 路徑可用
        "unavailable"         — 無可用 CLI
    """
    global _CLI_MODE_CACHE, _CLI_MODE_CACHE_TIME  # noqa: PLW0603
    now = time.monotonic()
    if _CLI_MODE_CACHE is not None and (now - _CLI_MODE_CACHE_TIME) < _CLI_MODE_CACHE_TTL:
        return _CLI_MODE_CACHE
    mode = _detect_copilot_cli_mode_uncached()
    _CLI_MODE_CACHE = mode
    _CLI_MODE_CACHE_TIME = now
    logger.debug("[CopilotDaemon] CLI mode detected: %s", mode)
    return mode


def build_copilot_command(
    prompt: str,
    model: Optional[str],
    cli_mode: str,
    dry_run: bool = True,
) -> list[str]:
    """
    建構 Copilot CLI 指令列表（不執行）。

    Args:
        prompt:   提示內容字串
        model:    模型名稱；None / "" 使用 CLI 預設；"auto" 亦省略 --model
        cli_mode: "agent_cli" | "gh_extension_legacy"
        dry_run:  True 時以 "[PROMPT_CONTENT]" 替代實際 prompt 內容（安全輸出）

    Returns:
        可直接傳給 subprocess.run() 的 argv list

    Raises:
        ValueError: 若 cli_mode 不受支援
    """
    safe_prompt = "[PROMPT_CONTENT]" if dry_run else prompt
    # "auto" 與空字串皆省略 --model，由 CLI 自行選擇
    effective_model = model if (model and model not in ("", "auto")) else None

    if cli_mode == "agent_cli":
        copilot_bin = shutil.which("copilot") or "copilot"
        cmd: list[str] = [copilot_bin, "-p", safe_prompt, "--allow-all-tools"]
        if effective_model:
            cmd += ["--model", effective_model]
        return cmd

    if cli_mode == "gh_extension_legacy":
        gh_bin = shutil.which("gh") or "gh"
        cmd = [gh_bin, "copilot", "suggest", "--target", "shell"]
        if effective_model:
            cmd += ["--model", effective_model]
        return cmd

    raise ValueError(f"build_copilot_command: unknown cli_mode={cli_mode!r}")


def _runtime_block_reason() -> Optional[str]:
    decision = execution_policy.evaluate_execution(
        runner="copilot_daemon",
        requires_llm=True,
        background=True,
        manual_override=execution_policy.is_manual_run(os.environ),
    )
    return decision["reason"]


def _assert_runtime_execution_allowed() -> None:
    execution_policy.assert_llm_execution_allowed(
        runner="copilot_daemon",
        provider="copilot-daemon",
        context="copilot_daemon_runtime",
        background=True,
        manual_override=execution_policy.is_manual_run(os.environ),
    )


# ── 常數 ──────────────────────────────────────────────────────────────────
LOCK_PATH = os.path.join(ORCH_RUNTIME_ROOT, "locks", "copilot_worker.lock.json")
DAEMON_PID = os.getpid()
DAEMON_START = datetime.now(timezone.utc).isoformat()


# ── 狀態寫入 ──────────────────────────────────────────────────────────────

def _write_state(
    status: str,
    current_task_id: Optional[int] = None,
    worker_pid: Optional[int] = None,
) -> None:
    """原子寫入 heartbeat 狀態檔。"""
    state = {
        "pid": DAEMON_PID,
        "status": status,
        "started_at": DAEMON_START,
        "heartbeat_at": datetime.now(timezone.utc).isoformat(),
        "current_task_id": current_task_id,
        "worker_pid": worker_pid,
        "worker_provider": "copilot-daemon",
    }
    os.makedirs(os.path.dirname(COPILOT_DAEMON_STATE_PATH), exist_ok=True)
    tmp = COPILOT_DAEMON_STATE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(state, fh, ensure_ascii=False)
    os.replace(tmp, COPILOT_DAEMON_STATE_PATH)


# ── Worker Lock ────────────────────────────────────────────────────────────

def _is_process_alive(pid: Optional[int]) -> bool:
    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, ValueError, TypeError):
        return False


def _read_lock() -> Optional[dict]:
    try:
        with open(LOCK_PATH, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None


def _write_lock(task_id: int, worker_pid: int) -> None:
    os.makedirs(os.path.dirname(LOCK_PATH), exist_ok=True)
    data = {
        "task_id": task_id,
        "worker_pid": worker_pid,
        "locked_at": datetime.now(timezone.utc).isoformat(),
    }
    tmp = LOCK_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False)
    os.replace(tmp, LOCK_PATH)


def _clear_lock() -> None:
    try:
        os.remove(LOCK_PATH)
    except OSError:
        pass


def _finalize(lock: dict) -> str:
    """Worker process 已死亡 → 將任務標為 FAILED 並清鎖。"""
    task_id = lock.get("task_id")
    if task_id:
        task = db.get_task(int(task_id))
        if task and task.get("status") == "RUNNING":
            db.update_task(
                int(task_id),
                status="FAILED",
                error_message="[COPILOT_DAEMON] Worker PID 死亡，任務強制標為 FAILED",
                completed_at=datetime.now(timezone.utc).isoformat(),
            )
            logger.warning(
                "[CopilotDaemon] Task #%s finalized as FAILED (worker PID dead)", task_id
            )
    _clear_lock()
    return "finalized"


# ── 執行邏輯 ───────────────────────────────────────────────────────────────

def _execute_with_gh_copilot(
    prompt_content: str,
    completed_path: str,
    timeout_sec: int,
    copilot_model: Optional[str] = None,
    cli_mode: Optional[str] = None,
) -> subprocess.CompletedProcess:
    """
    Copilot CLI 執行（Phase 36A：支援新版 agent_cli 與舊版 gh_extension_legacy）。

    agent_cli 模式（copilot 1.0+）：
        copilot -p <prompt> --allow-all-tools [--model <model>]
    gh_extension_legacy 模式（舊版 gh extension）：
        gh copilot suggest --target shell [--model <model>]  + stdin prompt
    """
    _assert_runtime_execution_allowed()

    if cli_mode is None:
        cli_mode = detect_copilot_cli_mode()
    if cli_mode == "unavailable":
        raise RuntimeError(
            "Copilot CLI unavailable: neither agent_cli nor gh_extension_legacy found"
        )

    cmd = build_copilot_command(prompt_content, copilot_model, cli_mode, dry_run=False)
    binary = cmd[0]
    if not (shutil.which(binary) or os.path.isfile(binary)):
        raise RuntimeError(f"Binary not found: {binary!r}")

    run_kwargs: dict = dict(
        capture_output=True,
        text=True,
        timeout=timeout_sec,
        cwd=str(PROJECT_ROOT),
    )
    # legacy 模式透過 stdin 傳遞 prompt（保留原有行為）
    if cli_mode == "gh_extension_legacy":
        run_kwargs["input"] = prompt_content

    return subprocess.run(cmd, **run_kwargs)


def _execute_with_codex(
    prompt_content: str,
    completed_path: str,
    timeout_sec: int,
) -> subprocess.CompletedProcess:
    """
    fallback：使用 codex exec --full-auto 執行。
    適用於 gh copilot 無法完成程式碼寫入的情境。
    """
    _assert_runtime_execution_allowed()
    codex_bin = shutil.which("codex") or "/opt/homebrew/bin/codex"
    if not os.path.isfile(codex_bin):
        raise RuntimeError(f"codex binary not found: {codex_bin!r}")

    cmd = [
        codex_bin, "exec",
        "-C", str(PROJECT_ROOT),
        "--full-auto",
        "--ephemeral",
        "-o", completed_path,
        "-",
    ]
    return subprocess.run(
        cmd,
        input=prompt_content,
        capture_output=True,
        text=True,
        timeout=timeout_sec,
        cwd=str(PROJECT_ROOT),
    )


def _list_dirty_files() -> list[str]:
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            capture_output=True, text=True, cwd=str(PROJECT_ROOT), timeout=10,
        )
        if result.returncode == 0:
            return [f.strip() for f in result.stdout.splitlines() if f.strip()]
        result2 = subprocess.run(
            ["git", "diff", "--name-only"],
            capture_output=True, text=True, cwd=str(PROJECT_ROOT), timeout=10,
        )
        return [f.strip() for f in result2.stdout.splitlines() if f.strip()]
    except Exception:
        return []


def _collect_changed_files(
    before: list[str],
    after: list[str],
    extra: list[str],
) -> list[str]:
    before_set = set(before)
    delta = [p for p in after if p and p not in before_set]
    combined: list[str] = []
    for p in delta + extra:
        if p and p not in combined:
            combined.append(p)
    return combined


def _log_daemon_result(
    *,
    provider: str,
    task_id: int,
    success: bool,
    error: Optional[str] = None,
    raw_text: Optional[str] = None,
) -> None:
    """CopilotDaemon 執行後補充 usage 記錄。"""
    try:
        from orchestrator.llm_usage_logger import log_usage
        log_usage(
            runner="copilot_daemon",
            role="worker",
            provider=provider,
            blocked=False,
            allowed=True,
            task_id=task_id,
            success=success,
            error=error,
            raw_usage_text=raw_text,
            source_file="orchestrator/copilot_daemon.py",
            source_function="_execute_task",
            entrypoint="post_execution",
            caller_skip_frames=4,
        )
    except Exception:  # noqa: BLE001
        pass


def _execute_task(task: dict) -> dict:
    """
    執行單一任務（Phase 36A：AuditGuard 在 subprocess 前初始化）。
    優先使用 Copilot CLI（agent_cli 或 legacy），失敗時 fallback 到 codex。
    """
    task_id = task["id"]
    prompt_path = task.get("prompt_file_path", "")
    if not prompt_path or not os.path.exists(prompt_path):
        raise RuntimeError(f"Prompt file not found: {prompt_path!r}")

    with open(prompt_path, "r", encoding="utf-8") as fh:
        prompt_content = fh.read()

    task_dir = os.path.dirname(prompt_path)
    completed_path = os.path.join(task_dir, f"{task['slot_key']}-completed.md")
    os.makedirs(task_dir, exist_ok=True)

    expected_hours = float(task.get("expected_duration_hours") or 2.0)
    timeout_sec = int(expected_hours * 3600) + 1800

    copilot_model = db.get_worker_copilot_model() or None
    cli_mode = detect_copilot_cli_mode()

    before_dirty = _list_dirty_files()

    # ── 1. 政策檢查（AuditGuard 初始化之前）────────────────────────────────
    _assert_runtime_execution_allowed()

    # ── 1b. Usage Budget Guard 檢查（HARD_CAP 時強制封鎖）─────────────────
    try:
        from orchestrator.usage_budget_guard import is_provider_allowed
        from orchestrator.llm_usage_logger import log_usage
        _budget_allowed, _budget_reason = is_provider_allowed(
            "worker", "copilot-daemon", hours=24
        )
        if not _budget_allowed:
            log_usage(
                runner="copilot_daemon",
                role="worker",
                provider="copilot-daemon",
                blocked=True,
                block_reason=_budget_reason,
                task_id=task_id,
                source_file="orchestrator/copilot_daemon.py",
                source_function="_execute_task",
                entrypoint="budget_guard_block",
            )
            from orchestrator.llm_audit import write_blocked
            write_blocked(
                runner="copilot_daemon",
                provider="github-copilot",
                block_reason=_budget_reason,
                task_id=task_id,
                trigger_source="usage_budget_guard",
            )
            raise RuntimeError(
                f"[CopilotDaemon] usage budget hard cap blocked: {_budget_reason}"
            )
    except RuntimeError:
        raise
    except Exception as _bg_exc:  # noqa: BLE001
        logger.warning(
            "[CopilotDaemon] Budget guard check failed (non-fatal, proceeding): %s", _bg_exc
        )

    # ── 2. AuditGuard 初始化（寫入 ATTEMPT，在 subprocess 之前）──────────────
    try:
        _audit = AuditGuard(
            runner="copilot_daemon",
            provider="copilot-daemon",
            usage_role="worker",
            task_id=task_id,
            model=copilot_model,
            trigger_source="copilot_daemon_execute",
        )
    except AuditGuardBlockedError as exc:
        _log_daemon_result(
            provider="copilot-daemon",
            task_id=task_id,
            success=False,
            error=f"AuditGuard blocked: {exc.block_reason}",
        )
        raise RuntimeError(
            f"[CopilotDaemon] audit guard blocked: {exc.block_reason}"
        ) from exc

    # ── 3. Subprocess 在 AuditGuard context 內執行 ───────────────────────
    proc: Optional[subprocess.CompletedProcess] = None
    used_provider = "copilot-daemon"

    with _audit:
        # 嘗試 Copilot CLI（agent_cli 或 legacy），失敗時 fallback codex
        if cli_mode != "unavailable":
            try:
                proc = _execute_with_gh_copilot(
                    prompt_content, completed_path, timeout_sec, copilot_model, cli_mode
                )
                if proc.returncode != 0:
                    logger.warning(
                        "[CopilotDaemon] Task #%d: copilot rc=%d (%s), falling back to codex",
                        task_id, proc.returncode, cli_mode,
                    )
                    proc = None
            except subprocess.TimeoutExpired:
                _audit.set_result(success=False, error="copilot subprocess timed out")
                raise
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "[CopilotDaemon] Task #%d: copilot error (%s), falling back to codex",
                    task_id, exc,
                )
                proc = None

        if proc is None:
            used_provider = "codex"
            try:
                proc = _execute_with_codex(prompt_content, completed_path, timeout_sec)
            except subprocess.TimeoutExpired:
                _audit.set_result(success=False, error="codex subprocess timed out")
                raise

        assert proc is not None, "Both copilot and codex subprocess paths returned None"
        raw_output = (proc.stdout or "") + (proc.stderr or "")

        # ── AuditGuard RESULT（在 subprocess 完成後，仍在 context 內）──────────
        if proc.returncode != 0:
            _audit.set_result(
                success=False,
                error=f"[{used_provider}] exited {proc.returncode}: {(proc.stderr or '')[:200]}",
                raw_usage_excerpt=raw_output[:300],
            )
        else:
            _audit.set_result(success=True, raw_usage_excerpt=raw_output[:300])

    after_dirty = _list_dirty_files()

    # ── 4. 失敗路徑：記錄 usage 並 raise ─────────────────────────────────
    if proc.returncode != 0:
        _log_daemon_result(
            provider=used_provider,
            task_id=task_id,
            success=False,
            error=f"[{used_provider}] exited {proc.returncode}: {(proc.stderr or '')[:500]}",
            raw_text=raw_output[:500],
        )
        raise RuntimeError(
            f"[{used_provider}] exited {proc.returncode}: {(proc.stderr or '')[:500]}"
        )

    # ── 5. 讀取 completed file（優先），fallback stdout ───────────────────
    if os.path.exists(completed_path):
        with open(completed_path, "r", encoding="utf-8") as fh:
            completed_text = fh.read()
    else:
        completed_text = proc.stdout or ""
        with open(completed_path, "w", encoding="utf-8") as fh:
            fh.write(completed_text)

    changed_files = _collect_changed_files(before_dirty, after_dirty, [completed_path])
    execution_log = f"[{used_provider}] rc={proc.returncode}\n" + (proc.stdout or "")[:2000]

    _log_daemon_result(
        provider=used_provider,
        task_id=task_id,
        success=True,
        raw_text=raw_output[:500],
    )

    return {
        "success": True,
        "completed_file_path": completed_path,
        "completed_text": completed_text,
        "changed_files": changed_files,
        "execution_log": execution_log,
    }


# ── 主迴圈 ─────────────────────────────────────────────────────────────────

def run_once() -> str:
    """
    單次 tick。回傳狀態字串：
      busy / finalized / provider-not-selected / scheduler-disabled /
      no-queued-task / claimed / error
    """
    # 1. Worker lock 檢查
    lock = _read_lock()
    if lock:
        worker_pid = lock.get("worker_pid")
        task_id = lock.get("task_id")
        if _is_process_alive(worker_pid):
            _write_state("busy", current_task_id=task_id, worker_pid=worker_pid)
            return "busy"
        return _finalize(lock)

    # 2. Provider 設定
    if db.get_worker_provider() != "copilot-daemon":
        execution_policy.set_active_background_runner("copilot-daemon", False)
        _write_state("idle")
        return "provider-not-selected"

    # 3. Scheduler 狀態
    block_reason = _runtime_block_reason()
    if block_reason:
        from orchestrator.llm_audit import write_blocked
        write_blocked(
            runner="copilot_daemon",
            provider="github-copilot",
            block_reason=block_reason,
            trigger_source="scheduler_tick",
        )
        execution_policy.set_active_background_runner("copilot-daemon", False)
        _write_state("idle")
        return block_reason

    # 4. 取最舊的 QUEUED 任務
    queued = db.list_tasks(status="QUEUED", limit=1)
    if not queued:
        execution_policy.set_active_background_runner("copilot-daemon", False)
        _write_state("idle")
        return "no-queued-task"

    task = queued[0]
    task_id: int = task["id"]

    # 5. 領取任務（QUEUED → RUNNING）
    now_iso = datetime.now(timezone.utc).isoformat()
    db.update_task(
        task_id,
        status="RUNNING",
        started_at=now_iso,
        worker_pid=DAEMON_PID,
    )
    logger.info("[CopilotDaemon] Claimed task #%d: %s", task_id, task.get("title", ""))

    # 寫鎖定與狀態
    _write_lock(task_id, DAEMON_PID)
    execution_policy.set_active_background_runner("copilot-daemon", True)
    _write_state("busy", current_task_id=task_id, worker_pid=DAEMON_PID)

    # 6. 執行任務
    start_time = datetime.now(timezone.utc)
    try:
        result = _execute_task(task)
        end_time = datetime.now(timezone.utc)
        duration = int((end_time - start_time).total_seconds())

        db.update_task(
            task_id,
            status="COMPLETED",
            completed_at=end_time.isoformat(),
            completed_file_path=result.get("completed_file_path"),
            completed_text=(result.get("completed_text") or "")[:4000],
            changed_files_json=json.dumps(result.get("changed_files", [])),
            duration_seconds=duration,
            error_message=None,
        )
        logger.info("[CopilotDaemon] Task #%d COMPLETED in %ds", task_id, duration)

    except subprocess.TimeoutExpired:
        duration = int((datetime.now(timezone.utc) - start_time).total_seconds())
        db.update_task(
            task_id,
            status="FAILED",
            error_message=f"[COPILOT_DAEMON] Task #{task_id} timed out after {duration}s",
            completed_at=datetime.now(timezone.utc).isoformat(),
            duration_seconds=duration,
        )
        logger.error("[CopilotDaemon] Task #%d TIMEOUT (%ds)", task_id, duration)

    except Exception as exc:
        duration = int((datetime.now(timezone.utc) - start_time).total_seconds())
        error_msg = str(exc)
        fail_status = _detect_failure_status(error_msg)
        db.update_task(
            task_id,
            status=fail_status,
            error_message=f"[COPILOT_DAEMON] {error_msg[:400]}",
            completed_at=datetime.now(timezone.utc).isoformat(),
            duration_seconds=duration,
        )
        logger.error("[CopilotDaemon] Task #%d %s: %s", task_id, fail_status, exc)

    finally:
        execution_policy.set_active_background_runner("copilot-daemon", False)
        _clear_lock()
        _write_state("idle")

    return "claimed"


def serve_forever(poll_seconds: int = 10) -> None:
    logger.info(
        "[CopilotDaemon] Starting PID=%d, poll=%ds, project=%s",
        DAEMON_PID, poll_seconds, PROJECT_ROOT,
    )
    db.init_db()

    while True:
        try:
            result = run_once()
            logger.debug("[CopilotDaemon] tick → %s", result)
        except Exception as exc:
            logger.error("[CopilotDaemon] Unhandled error in run_once: %s", exc)
            try:
                _write_state("error")
            except Exception:
                pass

        time.sleep(poll_seconds)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Betting-pool Copilot Daemon")
    parser.add_argument(
        "--poll-seconds",
        type=int,
        default=10,
        help="Poll interval in seconds (default: 10)",
    )
    args = parser.parse_args()
    serve_forever(args.poll_seconds)
