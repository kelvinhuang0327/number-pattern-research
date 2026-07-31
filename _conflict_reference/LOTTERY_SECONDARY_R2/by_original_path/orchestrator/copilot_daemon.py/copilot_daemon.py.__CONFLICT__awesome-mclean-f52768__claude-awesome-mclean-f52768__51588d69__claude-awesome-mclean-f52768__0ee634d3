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
) -> subprocess.CompletedProcess:
    """
    使用 gh copilot suggest 執行提示。
    gh copilot 需要在使用者 session（有 keychain 存取）中執行。
    """
    _assert_runtime_execution_allowed()
    gh_bin = shutil.which("gh") or "/opt/homebrew/bin/gh"
    if not os.path.isfile(gh_bin):
        raise RuntimeError(f"gh binary not found: {gh_bin!r}")

    cmd = [gh_bin, "copilot", "suggest", "--target", "shell"]
    if copilot_model:
        cmd += ["--model", copilot_model]

    return subprocess.run(
        cmd,
        input=prompt_content,
        capture_output=True,
        text=True,
        timeout=timeout_sec,
        cwd=str(PROJECT_ROOT),
    )


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
    執行單一任務。
    優先使用 gh copilot（keychain session 中），失敗時 fallback 到 codex。
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

    before_dirty = _list_dirty_files()

    # ── 嘗試 gh copilot，失敗時 fallback codex ──────────────────────────
    proc: Optional[subprocess.CompletedProcess] = None
    used_provider = "copilot"

    if shutil.which("gh"):
        try:
            proc = _execute_with_gh_copilot(
                prompt_content, completed_path, timeout_sec, copilot_model
            )
            if proc.returncode != 0:
                logger.warning(
                    "[CopilotDaemon] Task #%d: gh copilot rc=%d, falling back to codex",
                    task_id, proc.returncode,
                )
                proc = None
        except subprocess.TimeoutExpired:
            raise
        except Exception as exc:
            logger.warning(
                "[CopilotDaemon] Task #%d: gh copilot error (%s), falling back to codex",
                task_id, exc,
            )
            proc = None

    if proc is None:
        used_provider = "codex"
        proc = _execute_with_codex(prompt_content, completed_path, timeout_sec)

    after_dirty = _list_dirty_files()

    raw_output = (proc.stdout or "") + (proc.stderr or "")
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

    # ── 讀取 completed file（優先），fallback stdout ──────────────────────
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
