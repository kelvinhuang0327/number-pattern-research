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
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORCH_ROOT = os.path.join(ROOT, "runtime", "agent_orchestrator")
TASKS_ROOT = os.path.join(ORCH_ROOT, "tasks")
LOCKS_DIR = os.path.join(ORCH_ROOT, "locks")
LOGS_DIR = os.path.join(ORCH_ROOT, "logs")
BACKLOG_PATH = os.path.join(ORCH_ROOT, "backlog.md")

_DEFAULT_CLAUDE_BIN = os.environ.get("CLAUDE_BIN", "/Users/kelvin/.local/bin/claude")
_DEFAULT_CODEX_BIN = os.environ.get("CODEX_BIN", "/opt/homebrew/bin/codex")
_DEFAULT_GH_BIN = os.environ.get("GH_BIN", "/opt/homebrew/bin/gh")

WORKER_MAX_SECONDS = int(os.environ.get("WORKER_MAX_SECONDS", str(8 * 3600)))
WORKER_KILL_GRACE = 60  # seconds between SIGTERM and SIGKILL


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
    "claude": "Claude CLI",
}

PLANNER_ROLE_LABELS = {
    "claude": "Claude Planner",
    "codex": "Codex Planner",
}

_COPILOT_AUTH_CACHE = {
    "checked_at": 0.0,
    "ok": False,
    "reason": "Not checked yet",
}


def ensure_dirs():
    for d in [TASKS_ROOT, LOCKS_DIR, LOGS_DIR]:
        os.makedirs(d, exist_ok=True)


def normalize_planner_provider(provider: Optional[str]) -> str:
    value = str(provider or "claude").strip().lower()
    return value if value in PLANNER_PROVIDER_LABELS else "claude"


def normalize_worker_provider(provider: Optional[str]) -> str:
    value = str(provider or "codex").strip().lower()
    return value if value in WORKER_PROVIDER_LABELS else "codex"


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
    copilot_ok, copilot_reason = _copilot_auth_status()
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


def worker_command(prompt: str, provider: Optional[str] = None) -> tuple[str, list[str]]:
    runtime = normalize_worker_provider(provider)
    ok, reason = provider_available("worker", runtime)
    if not ok:
        raise FileNotFoundError(reason)

    if runtime == "codex":
        return runtime, [CODEX_BIN, "exec", "--full-auto", prompt]

    if runtime == "claude":
        return runtime, [
            CLAUDE_BIN,
            "-p",
            prompt,
            "--output-format",
            "text",
            "--dangerously-skip-permissions",
        ]

    if runtime == "copilot":
        return runtime, [GH_BIN, "copilot", "-p", prompt]

    raise FileNotFoundError(f"Unsupported worker provider: {provider}")


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
        return True
    except (ProcessLookupError, PermissionError):
        return False


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


def read_backlog() -> str:
    if not os.path.exists(BACKLOG_PATH):
        return ""
    with open(BACKLOG_PATH) as f:
        return f.read().strip()


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

# 輸出格式（只回傳 JSON，不要有其他文字）
{{
  "title": "<任務標題，中英文皆可，短於 40 字元>",
  "slug": "<kebab-case 英文識別碼，短於 40 字元，只用英數與 hyphen>",
    "prompt_markdown": "<完整的 8 小時任務 prompt，包含：## Objective / ## Scope / ## Constraints / ## Acceptance Criteria / ## Handoff Notes；Handoff Notes 必須交代 wiki 是否更新、更新哪個 game 頁、以及是否新增 lesson>"
}}
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
