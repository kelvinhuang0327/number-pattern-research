"""
Orchestrator shared helpers — no lottery_api dependencies.

This module centralizes provider selection so planner/worker runtimes can be
switched from the UI without editing launchd jobs or runner scripts.
"""

import os
import re
import signal
import logging
import json
import subprocess
import shutil
import time
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from typing import Optional

try:
    import fcntl
except ImportError:  # pragma: no cover - non-POSIX fallback
    fcntl = None

logger = logging.getLogger(__name__)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORCH_ROOT = os.path.join(ROOT, "runtime", "agent_orchestrator")
TASKS_ROOT = os.path.join(ORCH_ROOT, "tasks")
LOCKS_DIR = os.path.join(ORCH_ROOT, "locks")
LOGS_DIR = os.path.join(ORCH_ROOT, "logs")
BACKLOG_PATH = os.path.join(ORCH_ROOT, "backlog.md")
BACKLOG_AUTO_STATUS_START = "<!-- AUTO_STATUS_START -->"
BACKLOG_AUTO_STATUS_END = "<!-- AUTO_STATUS_END -->"

_DEFAULT_CLAUDE_BIN = os.environ.get("CLAUDE_BIN", "/Users/kelvin/.local/bin/claude")
_DEFAULT_CODEX_BIN = os.environ.get("CODEX_BIN", "/opt/homebrew/bin/codex")
_DEFAULT_GH_BIN = os.environ.get("GH_BIN", "/opt/homebrew/bin/gh")

WORKER_MAX_SECONDS = int(os.environ.get("WORKER_MAX_SECONDS", str(8 * 3600)))
WORKER_KILL_GRACE = 60  # seconds between SIGTERM and SIGKILL
WORKER_PROGRESS_STALE_SECONDS = int(os.environ.get("WORKER_PROGRESS_STALE_SECONDS", "600"))
COPILOT_PROGRESS_STALE_SECONDS = int(os.environ.get("COPILOT_PROGRESS_STALE_SECONDS", "600"))


def _resolve_bin(preferred: str, cli_name: str) -> Optional[str]:
    """Resolve a CLI path from configured absolute path or PATH lookup."""
    if preferred:
        expanded = os.path.expanduser(preferred)
        if os.path.isabs(expanded):
            if os.path.exists(expanded) and os.access(expanded, os.X_OK):
                return expanded
        else:
            found = shutil.which(expanded)
            if found:
                return found

    found = shutil.which(cli_name)
    if found:
        return found

    if preferred and os.path.isabs(os.path.expanduser(preferred)):
        return os.path.expanduser(preferred)
    return None


CLAUDE_BIN = _resolve_bin(_DEFAULT_CLAUDE_BIN, "claude")
CODEX_BIN = _resolve_bin(_DEFAULT_CODEX_BIN, "codex")
GH_BIN = _resolve_bin(_DEFAULT_GH_BIN, "gh")

PLANNER_PROVIDER_LABELS = {
    "claude": "Claude CLI",
    "codex": "Codex CLI",
}

WORKER_PROVIDER_LABELS = {
    "codex": "Codex CLI",
    "copilot": "GitHub Copilot CLI",
    "copilot-daemon": "GitHub Copilot Daemon",
    "claude": "Claude CLI",
}

COPILOT_MODEL_PRESETS = [
    {"value": "", "label": "預設"},
    {"value": "auto", "label": "auto（建議）"},
    {"value": "gpt-5-mini", "label": "gpt-5-mini"},
]

PLANNER_ROLE_LABELS = {
    "claude": "Claude Planner",
    "codex": "Codex Planner",
}

_COPILOT_AUTH_CACHE = {
    "checked_at": 0.0,
    "ok": False,
    "reason": "Not checked yet",
}

_COPILOT_RUNTIME_CACHE = {
    "checked_at": 0.0,
    "ok": False,
    "reason": "Not checked yet",
}

COPILOT_DAEMON_STATE_PATH = os.path.join(LOCKS_DIR, "copilot_daemon_state.json")
COPILOT_DAEMON_HEARTBEAT_TTL = int(os.environ.get("COPILOT_DAEMON_HEARTBEAT_TTL", "45"))
GIT_OPS_LOCK_PATH = os.path.join(LOCKS_DIR, "git_ops.lock")

HIGH_CONFLICT_PATHS = [
    "CLAUDE.md",
    "AGENT_RULES.md",
    "SYSTEM_MAP.md",
    "index.html",
    "src/main.js",
    "src/ui/OrchestrationManager.js",
    "orchestrator/",
    "runtime/agent_orchestrator/backlog.md",
    "runtime/agent_orchestrator/launchd/",
    "wiki/",
    "memory/",
]


def ensure_dirs():
    for d in [TASKS_ROOT, LOCKS_DIR, LOGS_DIR]:
        os.makedirs(d, exist_ok=True)


def read_copilot_daemon_state() -> dict:
    if not os.path.exists(COPILOT_DAEMON_STATE_PATH):
        return {}
    try:
        with open(COPILOT_DAEMON_STATE_PATH) as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def write_copilot_daemon_state(**kwargs):
    ensure_dirs()
    current = read_copilot_daemon_state()
    with open(COPILOT_DAEMON_STATE_PATH, "w") as f:
        json.dump({**current, **kwargs}, f, indent=2)


def clear_copilot_daemon_state(pid: Optional[int] = None):
    current = read_copilot_daemon_state()
    if pid is not None and current.get("pid") not in (None, pid):
        return
    try:
        os.remove(COPILOT_DAEMON_STATE_PATH)
    except FileNotFoundError:
        return


def copilot_daemon_status() -> dict:
    state = read_copilot_daemon_state()
    pid = state.get("pid")
    heartbeat_at = state.get("heartbeat_at")
    running = False
    stale = True

    if pid and heartbeat_at and is_process_alive(pid):
        try:
            last = datetime.fromisoformat(heartbeat_at)
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            stale = (datetime.now(timezone.utc) - last).total_seconds() > COPILOT_DAEMON_HEARTBEAT_TTL
            running = not stale
        except ValueError:
            running = False
            stale = True

    return {
        **state,
        "pid": pid,
        "heartbeat_at": heartbeat_at,
        "running": running,
        "stale": stale if heartbeat_at else True,
    }


def normalize_planner_provider(provider: Optional[str]) -> str:
    value = str(provider or "claude").strip().lower()
    return value if value in PLANNER_PROVIDER_LABELS else "claude"


def normalize_worker_provider(provider: Optional[str]) -> str:
    value = str(provider or "codex").strip().lower()
    return value if value in WORKER_PROVIDER_LABELS else "codex"


def normalize_copilot_model(model: Optional[str]) -> str:
    raw = str(model or "").strip()
    if not raw:
        return ""

    lowered = raw.lower().strip()
    if lowered in ("default", "預設", "system", "builtin"):
        return ""
    if lowered == "auto":
        return "auto"

    aliases = {
        "gpt-5 mini": "gpt-5-mini",
        "gpt5 mini": "gpt-5-mini",
        "gpt 5 mini": "gpt-5-mini",
        "gpt_5_mini": "gpt-5-mini",
        "gpt5-mini": "gpt-5-mini",
    }
    if lowered in aliases:
        return aliases[lowered]

    normalized = re.sub(r"\s+", "-", lowered)
    normalized = re.sub(r"[^a-z0-9._-]", "", normalized)
    normalized = re.sub(r"-{2,}", "-", normalized).strip("-")
    return normalized


def validate_copilot_model(model: Optional[str]) -> tuple[bool, str, str]:
    normalized = normalize_copilot_model(model)
    if not normalized:
        return True, "", ""
    if normalized in ("auto", "gpt-5-mini"):
        return True, normalized, ""
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{1,63}", normalized):
        return False, normalized, "Copilot model 格式無效；請使用 auto、gpt-5-mini 或合法 model id"
    return True, normalized, ""


def planner_provider_label(provider: Optional[str]) -> str:
    return PLANNER_PROVIDER_LABELS.get(normalize_planner_provider(provider), "Planner")


def worker_provider_label(provider: Optional[str]) -> str:
    return WORKER_PROVIDER_LABELS.get(normalize_worker_provider(provider), "Worker")


def planner_role_label(provider: Optional[str]) -> str:
    return PLANNER_ROLE_LABELS.get(normalize_planner_provider(provider), "Planner")


def planner_worker_combo_label(planner_provider: Optional[str], worker_provider: Optional[str]) -> str:
    return f"{planner_provider_label(planner_provider)} Planner + {worker_provider_label(worker_provider)} Worker"


def _binary_ready(path: Optional[str]) -> tuple[bool, str]:
    if path and os.path.exists(path) and os.access(path, os.X_OK):
        return True, ""
    return False, f"Binary missing: {path or 'not found in PATH'}"


def _copilot_auth_status(force_refresh: bool = False) -> tuple[bool, str]:
    now = time.time()
    if not force_refresh and now - _COPILOT_AUTH_CACHE["checked_at"] < 30:
        return _COPILOT_AUTH_CACHE["ok"], _COPILOT_AUTH_CACHE["reason"]

    gh_ready, gh_reason = _binary_ready(GH_BIN)
    if not gh_ready:
        _COPILOT_AUTH_CACHE.update({
            "checked_at": now,
            "ok": False,
            "reason": gh_reason,
        })
        return False, gh_reason

    try:
        result = subprocess.run(
            [GH_BIN, "auth", "status"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            reason = "GitHub auth OK"
            ok = True
        else:
            output = (result.stdout or "") + (result.stderr or "")
            lowered = output.lower()
            if "token in default is invalid" in lowered:
                reason = "GitHub CLI token invalid; run gh auth login"
            elif "failed to log in" in lowered:
                reason = "GitHub CLI auth failed; run gh auth login"
            else:
                reason = output.strip().splitlines()[0] if output.strip() else "GitHub CLI auth is invalid"
            ok = False
    except Exception as exc:
        ok = False
        reason = f"GitHub auth check failed: {exc}"

    _COPILOT_AUTH_CACHE.update({
        "checked_at": now,
        "ok": ok,
        "reason": reason,
    })
    return ok, reason


def _copilot_runtime_status(force_refresh: bool = False) -> tuple[bool, str]:
    now = time.time()
    if not force_refresh and now - _COPILOT_RUNTIME_CACHE["checked_at"] < 60:
        return _COPILOT_RUNTIME_CACHE["ok"], _COPILOT_RUNTIME_CACHE["reason"]

    auth_ok, auth_reason = _copilot_auth_status(force_refresh=force_refresh)
    if not auth_ok:
        _COPILOT_RUNTIME_CACHE.update({
            "checked_at": now,
            "ok": False,
            "reason": auth_reason,
        })
        return False, auth_reason

    try:
        # Runtime smoke check: avoids "auth OK but copilot process unusable" cases.
        result = subprocess.run(
            [GH_BIN, "copilot", "--", "--help"],
            capture_output=True,
            text=True,
            timeout=12,
        )
        output = ((result.stdout or "") + "\n" + (result.stderr or "")).strip()
        if result.returncode == 0:
            ok = True
            reason = "GitHub Copilot CLI runtime OK"
        else:
            lowered = output.lower()
            if "secitemcopymatching failed -50" in lowered:
                reason = "Copilot keychain access failed in non-interactive shell (SecItemCopyMatching -50)"
            else:
                reason = output.splitlines()[0] if output else f"Copilot runtime failed (exit {result.returncode})"
            ok = False
    except subprocess.TimeoutExpired:
        ok = False
        reason = "Copilot runtime check timeout"
    except Exception as exc:
        ok = False
        reason = f"Copilot runtime check failed: {exc}"

    _COPILOT_RUNTIME_CACHE.update({
        "checked_at": now,
        "ok": ok,
        "reason": reason,
    })
    return ok, reason


def planner_provider_options() -> list[dict]:
    claude_ok, claude_reason = _binary_ready(CLAUDE_BIN)
    codex_ok, codex_reason = _binary_ready(CODEX_BIN)
    return [
        {
            "value": "claude",
            "label": planner_provider_label("claude"),
            "available": claude_ok,
            "reason": claude_reason or "Ready",
        },
        {
            "value": "codex",
            "label": planner_provider_label("codex"),
            "available": codex_ok,
            "reason": codex_reason or "Ready",
        },
    ]


def worker_provider_options() -> list[dict]:
    codex_ok, codex_reason = _binary_ready(CODEX_BIN)
    claude_ok, claude_reason = _binary_ready(CLAUDE_BIN)
    copilot_ok, copilot_reason = _copilot_runtime_status()
    gh_ok, gh_reason = _binary_ready(GH_BIN)
    daemon_status = copilot_daemon_status()
    if not gh_ok:
        daemon_ok = False
        daemon_reason = gh_reason
    elif daemon_status.get("running"):
        daemon_ok = True
        daemon_reason = f"Daemon running (PID {daemon_status.get('pid')})"
    else:
        daemon_ok = True
        daemon_reason = "Ready; start resident LaunchAgent to run Copilot in user session"
    return [
        {
            "value": "codex",
            "label": worker_provider_label("codex"),
            "available": codex_ok,
            "reason": codex_reason or "Ready",
        },
        {
            "value": "copilot",
            "label": worker_provider_label("copilot"),
            "available": copilot_ok,
            "reason": copilot_reason,
        },
        {
            "value": "copilot-daemon",
            "label": worker_provider_label("copilot-daemon"),
            "available": daemon_ok,
            "reason": daemon_reason,
        },
        {
            "value": "claude",
            "label": worker_provider_label("claude"),
            "available": claude_ok,
            "reason": claude_reason or "Ready",
        },
    ]


def provider_available(kind: str, provider: Optional[str]) -> tuple[bool, str]:
    if kind == "planner":
        normalized = normalize_planner_provider(provider)
        options = {item["value"]: item for item in planner_provider_options()}
    else:
        normalized = normalize_worker_provider(provider)
        options = {item["value"]: item for item in worker_provider_options()}
    item = options.get(normalized)
    if not item:
        return False, f"Unknown {kind} provider: {provider}"
    return bool(item["available"]), item["reason"]


def _worker_fallback_candidates(provider: Optional[str]) -> list[str]:
    requested = normalize_worker_provider(provider)
    ordered = [requested]

    if requested in ("copilot", "copilot-daemon"):
        ordered.extend(["codex", "claude"])
    elif requested == "codex":
        ordered.append("claude")
    elif requested == "claude":
        ordered.append("codex")

    deduped = []
    for item in ordered:
        if item not in deduped:
            deduped.append(item)
    return deduped


def resolve_worker_runtime(provider: Optional[str] = None) -> dict:
    requested = normalize_worker_provider(provider)
    attempts = []

    for candidate in _worker_fallback_candidates(requested):
        ok, reason = provider_available("worker", candidate)
        attempts.append({
            "provider": candidate,
            "available": ok,
            "reason": reason,
        })
        if ok:
            fallback_reason = None
            if candidate != requested:
                requested_reason = attempts[0]["reason"] if attempts else "Unavailable"
                fallback_reason = (
                    f"{worker_provider_label(requested)} unavailable: {requested_reason}; "
                    f"fell back to {worker_provider_label(candidate)}"
                )
            runtime = "copilot" if candidate == "copilot-daemon" else candidate
            return {
                "requested_provider": requested,
                "dispatch_provider": candidate,
                "runtime": runtime,
                "availability_reason": reason,
                "fallback_reason": fallback_reason,
                "attempts": attempts,
            }

    details = "; ".join(
        f"{worker_provider_label(item['provider'])}: {item['reason']}"
        for item in attempts
    ) or "No worker providers available"
    raise FileNotFoundError(details)


def planner_command(prompt: str, provider: Optional[str] = None) -> tuple[str, list[str]]:
    runtime = normalize_planner_provider(provider)

    if runtime == "claude":
        ok, reason = provider_available("planner", runtime)
        if not ok:
            raise FileNotFoundError(reason)
        return runtime, [
            CLAUDE_BIN,
            "-p",
            prompt,
            "--output-format",
            "text",
            "--dangerously-skip-permissions",
        ]

    if runtime == "codex":
        ok, reason = provider_available("planner", runtime)
        if not ok:
            raise FileNotFoundError(reason)
        return runtime, [
            CODEX_BIN,
            "exec",
            "--sandbox",
            "read-only",
            prompt,
        ]

    raise FileNotFoundError(f"Unsupported planner provider: {provider}")


def worker_command(prompt: str, provider: Optional[str] = None) -> dict:
    resolution = resolve_worker_runtime(provider)
    runtime = resolution["runtime"]
    configured_model = ""

    if runtime == "codex":
        command = [CODEX_BIN, "exec", "--full-auto", prompt]
    elif runtime == "claude":
        command = [
            CLAUDE_BIN,
            "-p",
            prompt,
            "--output-format",
            "text",
            "--dangerously-skip-permissions",
        ]
    elif runtime == "copilot":
        from orchestrator import db

        configured_model = db.get_worker_copilot_model()
        permission_mode = str(os.environ.get("COPILOT_PERMISSION_MODE", "all")).strip().lower()
        command = [GH_BIN, "copilot", "-p", prompt]
        if configured_model:
            command.extend(["--model", configured_model])
        if permission_mode in ("all", "wide"):
            command.extend(["--allow-all", "--no-ask-user"])
        else:
            command.extend([
                "--allow-all-tools",
                "--add-dir",
                ROOT,
                "--no-ask-user",
            ])
            # Optional broader path scope for workflows that touch paths outside ROOT.
            if str(os.environ.get("COPILOT_ALLOW_ALL_PATHS", "")).strip().lower() in ("1", "true", "yes", "on"):
                command.append("--allow-all-paths")
    else:
        raise FileNotFoundError(f"Unsupported worker provider: {provider}")

    return {
        **resolution,
        "model": configured_model,
        "command": command,
    }


def slugify(text: str) -> str:
    text = re.sub(r"[^\w\s-]", "", text.lower())
    text = re.sub(r"[\s_]+", "-", text)
    return text[:40].strip("-")


def slot_key_now() -> str:
    return datetime.now().strftime("%Y%m%d%H%M")


def date_folder_now() -> str:
    return datetime.now().strftime("%Y%m%d")


def task_dir(date_folder: str) -> str:
    path = os.path.join(TASKS_ROOT, date_folder)
    os.makedirs(path, exist_ok=True)
    return path


def prompt_path(slot_key: str, slug: str, date_folder: str) -> str:
    return os.path.join(task_dir(date_folder), f"{slot_key}-prompt-{slug}.md")


def completed_path(slot_key: str, slug: str, date_folder: str) -> str:
    return os.path.join(task_dir(date_folder), f"{slot_key}-completed-{slug}.md")


def contract_path(slot_key: str, slug: str, date_folder: str) -> str:
    return os.path.join(task_dir(date_folder), f"{slot_key}-contract-{slug}.json")


def result_path(slot_key: str, slug: str, date_folder: str) -> str:
    return os.path.join(task_dir(date_folder), f"{slot_key}-result-{slug}.json")


def worker_stdout_log_path(slot_key: str, date_folder: str) -> str:
    return os.path.join(task_dir(date_folder), f"{slot_key}-worker-stdout.log")


def legacy_stdout_log_path(slot_key: str, date_folder: str) -> str:
    return os.path.join(task_dir(date_folder), f"{slot_key}-codex-stdout.log")


def stdout_log_path(slot_key: str, date_folder: str) -> str:
    return worker_stdout_log_path(slot_key, date_folder)


def find_stdout_log_path(slot_key: str, date_folder: str) -> str:
    for path in [worker_stdout_log_path(slot_key, date_folder), legacy_stdout_log_path(slot_key, date_folder)]:
        if os.path.exists(path):
            return path
    return worker_stdout_log_path(slot_key, date_folder)


def read_worker_progress(slot_key: str, date_folder: str, max_chars: int = 6000) -> dict:
    """
    Return lightweight progress metadata from the worker stdout log so the UI can
    distinguish active long-running work from a stuck task.
    """
    path = find_stdout_log_path(slot_key, date_folder)
    if not os.path.exists(path):
        return {
            "worker_log_path": path,
            "last_output_at": None,
            "last_progress_summary": "",
            "idle_seconds": None,
            "stuck_suspected": False,
            "stuck_timeout_seconds": WORKER_PROGRESS_STALE_SECONDS,
            "progress_state": "no_output",
        }

    summary = ""
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            tail = f.read()[-max_chars:]
        lines = [line.strip() for line in tail.splitlines() if line.strip()]
        for line in reversed(lines):
            if line.startswith(("│", "└", "```")):
                continue
            summary = line[:300]
            break
    except OSError:
        summary = ""

    idle_seconds = None
    try:
        mtime = os.path.getmtime(path)
        last_output_at = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
        idle_seconds = max(0, int(time.time() - mtime))
    except OSError:
        last_output_at = None

    stuck_suspected = bool(idle_seconds is not None and idle_seconds > WORKER_PROGRESS_STALE_SECONDS)
    if stuck_suspected:
        progress_state = "stuck_suspected"
    elif idle_seconds is not None:
        progress_state = "active"
    else:
        progress_state = "unknown"

    return {
        "worker_log_path": path,
        "last_output_at": last_output_at,
        "last_progress_summary": summary,
        "idle_seconds": idle_seconds,
        "stuck_suspected": stuck_suspected,
        "stuck_timeout_seconds": WORKER_PROGRESS_STALE_SECONDS,
        "progress_state": progress_state,
    }


def _parse_utc_iso(raw: Optional[str]) -> Optional[datetime]:
    value = str(raw or "").strip()
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc)
    return dt.replace(tzinfo=timezone.utc)


def classify_worker_progress(status: Optional[str], last_output_at: Optional[str], worker_runtime: Optional[str] = None) -> dict:
    normalized_status = str(status or "").upper()
    runtime = str(worker_runtime or "").strip().lower()
    if normalized_status != "RUNNING":
        return {
            "progress_state": "not_running",
            "progress_note": "",
            "progress_idle_seconds": None,
            "progress_stale": False,
        }

    if not last_output_at:
        return {
            "progress_state": "no_output",
            "progress_note": "執行中但尚無輸出",
            "progress_idle_seconds": None,
            "progress_stale": False,
        }

    output_at = _parse_utc_iso(last_output_at)
    if not output_at:
        return {
            "progress_state": "no_output",
            "progress_note": "執行中，最後輸出時間格式無法解析",
            "progress_idle_seconds": None,
            "progress_stale": False,
        }

    idle_seconds = max(0, int((datetime.now(timezone.utc) - output_at).total_seconds()))
    stale_threshold = COPILOT_PROGRESS_STALE_SECONDS if runtime == "copilot" else WORKER_PROGRESS_STALE_SECONDS
    stale = idle_seconds > stale_threshold
    return {
        "progress_state": "stale" if stale else "active",
        "progress_note": (
            f"已 {idle_seconds}s 無新輸出，疑似卡住"
            if stale
            else f"{idle_seconds}s 前有新輸出，持續執行中"
        ),
        "progress_idle_seconds": idle_seconds,
        "progress_stale": stale,
    }


def meta_path(slot_key: str, date_folder: str) -> str:
    return os.path.join(task_dir(date_folder), f"{slot_key}-meta.json")


def write_meta(slot_key: str, date_folder: str, **kwargs):
    path = meta_path(slot_key, date_folder)
    with open(path, "w") as f:
        json.dump({"slot_key": slot_key, "date_folder": date_folder, **kwargs}, f, indent=2)


def read_meta(slot_key: str, date_folder: str) -> dict:
    path = meta_path(slot_key, date_folder)
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)


def append_jsonl(path: str, data: dict):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(data, ensure_ascii=False) + "\n")


def log_jsonl(runner: str, outcome: str, **kwargs):
    path = os.path.join(LOGS_DIR, f"{runner}.jsonl")
    append_jsonl(path, {
        "ts": datetime.now().astimezone().isoformat(),
        "runner": runner,
        "outcome": outcome,
        **kwargs
    })


def is_process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, PermissionError):
        return False

    # os.kill(pid, 0) treats zombie as "alive". Filter zombies explicitly.
    try:
        proc = subprocess.run(
            ["ps", "-o", "stat=", "-p", str(pid)],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if proc.returncode == 0:
            stat = (proc.stdout or "").strip().upper()
            # macOS/Linux: zombie state contains "Z" (e.g., "Z", "Z+", "SZ").
            if "Z" in stat:
                return False
    except Exception:
        # Fall back to the kill(0) probe result on any ps failure.
        pass
    return True


def kill_process_tree(pid: int):
    """SIGTERM the process group, then SIGKILL after grace period."""
    try:
        os.killpg(os.getpgid(pid), signal.SIGTERM)
    except Exception:
        pass
    import time
    time.sleep(min(WORKER_KILL_GRACE, 5))
    if is_process_alive(pid):
        try:
            os.killpg(os.getpgid(pid), signal.SIGKILL)
        except Exception:
            pass


def git_changed_files() -> list:
    """Return list of files changed since last commit (staged + unstaged + untracked)."""
    try:
        result = subprocess.run(
            ["git", "-C", ROOT, "status", "--porcelain"],
            capture_output=True, text=True, timeout=15
        )
        files = []
        for line in result.stdout.splitlines():
            if len(line) > 3:
                files.append(line[3:].strip())
        return sorted(set(files))
    except Exception as e:
        logger.warning(f"git status failed: {e}")
        return []


def git_status_porcelain(paths: Optional[list[str]] = None) -> list[str]:
    try:
        command = ["git", "-C", ROOT, "status", "--porcelain"]
        if paths:
            command.extend(["--", *paths])
        result = subprocess.run(command, capture_output=True, text=True, timeout=20)
        return [line.rstrip() for line in result.stdout.splitlines() if line.strip()]
    except Exception as exc:
        logger.warning(f"git status porcelain failed: {exc}")
        return []


def git_current_branch() -> str:
    try:
        result = subprocess.run(
            ["git", "-C", ROOT, "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        return (result.stdout or "").strip()
    except Exception:
        return "HEAD"


def git_head_sha() -> str:
    try:
        result = subprocess.run(
            ["git", "-C", ROOT, "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        return (result.stdout or "").strip()
    except Exception:
        return ""


def git_branch_exists(branch_name: str) -> bool:
    try:
        result = subprocess.run(
            ["git", "-C", ROOT, "rev-parse", "--verify", branch_name],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except Exception:
        return False


def git_checkout_branch(branch_name: str) -> tuple[bool, str]:
    try:
        if git_branch_exists(branch_name):
            command = ["git", "-C", ROOT, "checkout", branch_name]
        else:
            command = ["git", "-C", ROOT, "checkout", "-b", branch_name]
        result = subprocess.run(command, capture_output=True, text=True, timeout=30)
        output = ((result.stdout or "") + "\n" + (result.stderr or "")).strip()
        return result.returncode == 0, output
    except Exception as exc:
        return False, str(exc)


def git_branch_name_for_inbox(date_folder: str, scope: Optional[str] = None) -> str:
    base = f"auto/inbox/{date_folder}"
    scope_value = slugify(scope or "") if scope else ""
    return f"{base}/{scope_value}" if scope_value else base


def git_branch_name_for_cto_merge(date_folder: str, frequency_mode: str = "once_daily", started_at: Optional[str] = None) -> str:
    mode = str(frequency_mode or "once_daily").strip().lower()
    if mode != "twice_daily":
        return f"cto/merge/{date_folder}"

    dt = None
    if started_at:
        try:
            dt = datetime.fromisoformat(started_at)
        except ValueError:
            dt = None
    if dt is None:
        dt = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    local_hour = dt.astimezone(timezone(timedelta(hours=8))).hour
    suffix = "A" if local_hour < 12 else "B"
    return f"cto/merge/{date_folder}-{suffix}"


def derive_scope_from_paths(paths: list[str]) -> str:
    cleaned = [str(path or "").strip().strip("/") for path in paths if str(path or "").strip()]
    if not cleaned:
        return ""

    groups: dict[str, int] = {}
    for path in cleaned:
        first = path.split("/", 1)[0]
        groups[first] = groups.get(first, 0) + 1

    if len(groups) == 1:
        return next(iter(groups))

    if all(path.startswith("orchestrator/") for path in cleaned):
        return "orchestrator"
    if all(path.startswith("src/ui/") for path in cleaned):
        return "src-ui"
    if all(path.startswith("wiki/") for path in cleaned):
        return "wiki"
    if all(path.startswith("runtime/agent_orchestrator/") for path in cleaned):
        return "orchestrator-runtime"
    if all(path.startswith("tests/") for path in cleaned):
        return "tests"

    return ""


def is_high_conflict_path(path: str) -> bool:
    normalized = str(path or "").strip().replace("\\", "/")
    if not normalized:
        return False
    for pattern in HIGH_CONFLICT_PATHS:
        if pattern.endswith("/"):
            if normalized.startswith(pattern):
                return True
        elif normalized == pattern or normalized.startswith(pattern + "/"):
            return True
    return False


def filter_committable_paths(paths: list[str]) -> list[str]:
    allowed = []
    for raw in paths or []:
        path = str(raw or "").strip().replace("\\", "/")
        if not path:
            continue
        if path.endswith(".pid"):
            continue
        if path.startswith((
            "runtime/agent_orchestrator/logs/",
            "runtime/agent_orchestrator/tasks/",
            "runtime/agent_orchestrator/locks/",
            "tmp/",
            "logs/",
            ".pytest_cache/",
            "__pycache__/",
        )):
            continue
        if path.startswith("analysis/results/"):
            continue
        allowed.append(path)
    return sorted(set(allowed))


def git_staged_paths() -> list[str]:
    staged = []
    for line in git_status_porcelain():
        if line.startswith("??"):
            continue
        if len(line) > 3 and line[:2].strip():
            staged.append(line[3:].strip())
    return sorted(set(staged))


@contextmanager
def git_ops_lock(timeout_seconds: int = 300):
    ensure_dirs()
    os.makedirs(os.path.dirname(GIT_OPS_LOCK_PATH), exist_ok=True)
    handle = open(GIT_OPS_LOCK_PATH, "a+")
    start = time.time()
    try:
        if fcntl is None:
            yield handle
            return
        while True:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.time() - start > timeout_seconds:
                    raise TimeoutError(f"timed out waiting for git ops lock: {GIT_OPS_LOCK_PATH}")
                time.sleep(0.25)
        yield handle
    finally:
        try:
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


def git_commit_selected_files(paths: list[str], subject: str, body: str, branch_name: Optional[str] = None) -> tuple[bool, str, str]:
    committable_paths = filter_committable_paths(paths)
    if not committable_paths:
        return False, "", "no committable paths"

    if branch_name:
        ok, output = git_checkout_branch(branch_name)
        if not ok:
            return False, "", f"branch checkout failed: {output}"

    if git_staged_paths():
        return False, "", "repository already has staged changes"

    add_result = subprocess.run(
        ["git", "-C", ROOT, "add", "--", *committable_paths],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if add_result.returncode != 0:
        output = ((add_result.stdout or "") + "\n" + (add_result.stderr or "")).strip()
        return False, "", f"git add failed: {output}"

    staged_paths = git_staged_paths()
    staged_set = set(staged_paths)
    allowed_set = set(committable_paths)
    if not staged_set:
        return False, "", "nothing staged after git add"
    if not staged_set.issubset(allowed_set):
        extra = sorted(staged_set - allowed_set)
        subprocess.run(["git", "-C", ROOT, "reset", "HEAD", "--", *staged_paths], capture_output=True, text=True, timeout=60)
        return False, "", f"staged files exceed task scope: {', '.join(extra[:10])}"

    commit_result = subprocess.run(
        ["git", "-C", ROOT, "commit", "-m", subject, "-m", body],
        capture_output=True,
        text=True,
        timeout=120,
    )
    output = ((commit_result.stdout or "") + "\n" + (commit_result.stderr or "")).strip()
    if commit_result.returncode != 0:
        return False, "", f"git commit failed: {output}"

    sha = git_head_sha()
    return True, sha, output


def read_backlog() -> str:
    if not os.path.exists(BACKLOG_PATH):
        return ""
    with open(BACKLOG_PATH) as f:
        return f.read().strip()


REQUIRED_CONTRACT_FIELDS = [
    "version",
    "objective",
    "scope",
    "constraints",
    "acceptance_tests",
    "required_outputs",
    "forbidden_changes",
    "handoff_questions",
]


def validate_task_contract(contract: dict) -> tuple[bool, str]:
    if not isinstance(contract, dict):
        return False, "contract must be a JSON object"
    for field in REQUIRED_CONTRACT_FIELDS:
        if field not in contract:
            return False, f"missing contract field: {field}"
    if not str(contract.get("objective", "")).strip():
        return False, "objective is empty"
    list_fields = [
        "scope",
        "constraints",
        "acceptance_tests",
        "required_outputs",
        "forbidden_changes",
        "handoff_questions",
    ]
    for field in list_fields:
        value = contract.get(field)
        if not isinstance(value, list) or not value:
            return False, f"{field} must be a non-empty array"
    return True, ""


def _fmt_slot_to_taipei(slot_key: str) -> str:
    s = str(slot_key or "").strip()
    if len(s) != 12 or not s.isdigit():
        return s or "—"
    return f"{s[:4]}/{s[4:6]}/{s[6:8]} {s[8:10]}:{s[10:12]}"


def _fmt_seconds(sec) -> str:
    if sec is None:
        return "—"
    try:
        total = int(sec)
    except (TypeError, ValueError):
        return "—"
    if total < 60:
        return f"{total}s"
    if total < 3600:
        return f"{total // 60}m{total % 60}s"
    return f"{total // 3600}h{(total % 3600) // 60}m"


def _fmt_iso_to_taipei(iso_ts: str) -> str:
    s = str(iso_ts or "").strip()
    if not s:
        return "—"
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt_tw = dt.astimezone(timezone(timedelta(hours=8)))
        return dt_tw.strftime("%Y/%m/%d %H:%M:%S")
    except ValueError:
        return s


def _summarize_latest_task(tasks: list, keywords: list[str], label: str) -> str:
    for task in tasks:
        title = str(task.get("title") or "")
        if all(k.lower() in title.lower() for k in keywords):
            return (
                f"- {label}：`{task.get('status', '—')}` "
                f"(Task #{task.get('id')}, {_fmt_slot_to_taipei(task.get('slot_key'))})"
            )
    return f"- {label}：`NO_RECORD`"


def build_backlog_auto_status(tasks: list) -> str:
    now_tw = datetime.now(timezone(timedelta(hours=8))).strftime("%Y/%m/%d %H:%M:%S")
    recent = tasks[:8]
    lines = [
        "## 自動狀態快照（Auto-generated）",
        "",
        f"- 更新時間（Asia/Taipei）：`{now_tw}`",
        f"- 最近任務總數（查詢範圍）：`{len(tasks)}`",
        "",
        "### 研究任務摘要",
        _summarize_latest_task(tasks, ["midfreq_fourier_2bet", "mcnemar"], "midfreq_fourier_2bet McNemar 驗證"),
        _summarize_latest_task(tasks, ["fourier", "500期", "oos"], "fourier_rhythm_3bet 500期 OOS 驗證"),
        _summarize_latest_task(tasks, ["winning quality", "p2-1"], "Winning Quality P2-1 驗證"),
        "",
        "### 最近 8 筆任務",
    ]
    if not recent:
        lines.append("- （無任務資料）")
    else:
        for t in recent:
            lines.append(
                "- "
                f"#{t.get('id')} | {_fmt_slot_to_taipei(t.get('slot_key'))} | "
                f"{t.get('status', '—')} | 耗時 {_fmt_seconds(t.get('duration_seconds'))} | "
                f"完成 {_fmt_iso_to_taipei(t.get('completed_at'))} | "
                f"{str(t.get('title') or '—')[:60]}"
            )
    return "\n".join(lines).strip()


def refresh_backlog_auto_status(max_tasks: int = 50):
    """
    Update the AUTO status block in backlog.md using latest task records.
    Keeps all manually-written backlog content untouched.
    """
    if not os.path.exists(BACKLOG_PATH):
        return

    try:
        # Local import to avoid module-level circular dependency.
        from orchestrator import db
        tasks = db.list_tasks(limit=max_tasks, offset=0)
    except Exception as exc:
        logger.warning(f"[backlog] skip auto status refresh: failed to query tasks: {exc}")
        return

    auto_block = (
        f"{BACKLOG_AUTO_STATUS_START}\n\n"
        f"{build_backlog_auto_status(tasks)}\n\n"
        f"{BACKLOG_AUTO_STATUS_END}\n"
    )

    try:
        with open(BACKLOG_PATH, "r", encoding="utf-8") as f:
            original = f.read()
    except OSError as exc:
        logger.warning(f"[backlog] read failed: {exc}")
        return

    if BACKLOG_AUTO_STATUS_START in original and BACKLOG_AUTO_STATUS_END in original:
        start_idx = original.find(BACKLOG_AUTO_STATUS_START)
        end_idx = original.find(BACKLOG_AUTO_STATUS_END, start_idx)
        if end_idx == -1:
            updated = original.rstrip() + "\n\n" + auto_block
        else:
            end_idx += len(BACKLOG_AUTO_STATUS_END)
            updated = original[:start_idx].rstrip() + "\n\n" + auto_block + original[end_idx:].lstrip()
    else:
        updated = original.rstrip() + "\n\n---\n\n" + auto_block

    if updated != original:
        try:
            with open(BACKLOG_PATH, "w", encoding="utf-8") as f:
                f.write(updated)
        except OSError as exc:
            logger.warning(f"[backlog] write failed: {exc}")


PLANNER_META_PROMPT_TEMPLATE = """\
你是 {planner_role_label}，負責規劃軟體開發任務。
請根據「北極星目標」和「最近任務歷史（含 FAILED）」，產出下一個 8 小時任務的詳細 prompt。

重要規則：
- 若歷史中有 [FAILED] 任務，必須分析失敗原因，不得直接重複相同計畫，應調整方向或提供更具體的執行步驟
- 若同一方向已連續失敗 2 次以上，切換至 backlog 中的其他優先任務
- 若所有方向均已窮盡，在 prompt_markdown 中加入 [SIGNAL_EXHAUSTED_ALL] 標記並說明原因
- `prompt_markdown` 的 `## Handoff Notes` 必須包含：
    - 若有新策略驗證結果（PASS/REJECT），更新 wiki/games/<game>.md 的現役策略表
    - 若為新教訓，在 wiki/lessons/key_lessons.md 末尾新增（格式：**L<N>** 說明）
    - 若無新發現，Handoff Notes 填「wiki 無需更新」

# 相關知識（wiki 摘要，自動注入）
{wiki_context}

# 北極星目標（backlog.md）
{backlog}

# 最近任務歷史（最新 5 筆，含 FAILED/COMPLETED 狀態）
{recent_completed}

# 輸出格式（重要：只回傳純 JSON，第一個字元必須是 {{，最後一個字元必須是 }}，不要有任何其他文字、說明、markdown）
{{
  "title": "實際任務標題（中英文皆可，<= 40 字）",
  "slug": "actual-kebab-case-id",
  "prompt_markdown": "完整且可執行的 8 小時任務 prompt，必須含 ## Objective / ## Scope / ## Constraints / ## Acceptance Criteria / ## Handoff Notes"
}}

禁止輸出模板字串或佔位符，例如：
- 任務標題
- kebab-case
- 完整的 8 小時任務 prompt
- <...> 或 {{...}} 類型模板符號
若你輸出任何模板值，該結果會被判定為無效。
"""


def build_planner_meta_prompt(
        backlog: str,
        recent_completed: str,
        wiki_context: str = "",
        planner_provider: Optional[str] = None,
) -> str:
    return PLANNER_META_PROMPT_TEMPLATE.format(
        planner_role_label=planner_role_label(planner_provider),
                wiki_context=wiki_context.strip() or "（無可用 wiki 摘要）",
        backlog=backlog,
        recent_completed=recent_completed,
    )
