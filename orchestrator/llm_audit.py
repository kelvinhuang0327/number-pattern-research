"""
orchestrator/llm_audit.py

LLM Audit Lifecycle — 結構化稽核事件記錄器。

每次外部 LLM 呼叫必須依序寫入三種事件：
    LLM_CALL_ATTEMPT  — 呼叫前（必須先寫入，失敗則封鎖呼叫）
    LLM_CALL_RESULT   — 呼叫後（成功或失敗）
    LLM_CALL_BLOCKED  — 政策或審計失敗阻止呼叫

寫入路徑：
    runtime/agent_orchestrator/llm_audit.jsonl

硬性規則：
- 無 ATTEMPT → 不得執行外部 LLM
- ATTEMPT 寫入失敗 → BLOCKED_AUDIT_LOG_UNAVAILABLE，fail-closed
- 本地 provider 不寫入任何稽核事件
"""
from __future__ import annotations

import json
import os
import traceback
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

_AUDIT_PATH: str = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "runtime",
    "agent_orchestrator",
    "llm_audit.jsonl",
)
_MAX_FILE_BYTES: int = 50 * 1024 * 1024  # 50 MB

# 事件類型
EVENT_ATTEMPT = "LLM_CALL_ATTEMPT"
EVENT_RESULT  = "LLM_CALL_RESULT"
EVENT_BLOCKED = "LLM_CALL_BLOCKED"

# 外部 Provider 集合
EXTERNAL_PROVIDERS: frozenset[str] = frozenset({
    "codex", "codex-cli", "openai",
    "claude", "claude-cli", "claude-code", "anthropic",
    "copilot", "copilot-daemon", "github-copilot",
    "github-cli", "github-api", "git-remote",
    "gemini", "gemini-cli",
})

# 本地 Provider 集合
LOCAL_PROVIDERS: frozenset[str] = frozenset({
    "local", "none", "dry-run", "deterministic", "rule-based",
    "adaptive_regime", "",
})

# Runner → Role 映射
_RUNNER_TO_ROLE: dict[str, str] = {
    "planner": "planner", "planner_tick": "planner",
    "worker": "worker",   "worker_tick": "worker",
    "cto": "cto",         "cto_review_tick": "cto",
    "copilot_daemon": "worker", "copilot-daemon": "worker",
    "manual": "manual",   "backfill": "backfill",
}

# Provider 標準化別名
_PROVIDER_ALIASES: dict[str, str] = {
    "claude-cli": "claude", "claude-code": "claude", "anthropic": "claude",
    "codex-cli": "codex",   "openai": "codex",
    "copilot": "github-copilot", "gh-copilot": "github-copilot",
    "copilot-daemon": "github-copilot",
    "gh-api": "github-api", "gh-cli": "github-cli", "gh": "github-cli",
    "gemini-cli": "gemini",
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_provider(provider: str) -> str:
    key = str(provider or "").strip().lower()
    return _PROVIDER_ALIASES.get(key, key)


def _normalize_role(runner: str) -> str:
    return _RUNNER_TO_ROLE.get(str(runner or "").strip().lower(), "unknown")


def _is_external(provider: str) -> bool:
    """
    回傳 True 若 provider 為外部 LLM。
    任何不在 LOCAL_PROVIDERS 集合中的 provider 都視為外部（fail-safe）。
    """
    key = str(provider or "").strip().lower()
    return key not in LOCAL_PROVIDERS


def _get_caller_info(skip_frames: int = 4) -> dict[str, str]:
    frames = traceback.extract_stack()
    cutoff = max(0, len(frames) - skip_frames)
    caller_frames = frames[:cutoff]
    caller = caller_frames[-1] if caller_frames else None
    return {
        "caller_file": caller.filename if caller else "",
        "caller_function": caller.name if caller else "",
        "caller_stack": [
            f"{f.filename}:{f.lineno} in {f.name}"
            for f in caller_frames[-6:]  # 最後 6 層
        ],
    }


def _rotate_if_needed(path: str) -> None:
    try:
        if os.path.exists(path) and os.path.getsize(path) > _MAX_FILE_BYTES:
            rotated = path + ".1"
            if os.path.exists(rotated):
                os.remove(rotated)
            os.rename(path, rotated)
    except OSError:
        pass


def _write_audit_record(record: dict) -> bool:
    """
    寫入稽核記錄至 JSONL。
    回傳 True 成功，False 失敗（fail-closed 的依據）。
    """
    try:
        os.makedirs(os.path.dirname(_AUDIT_PATH), exist_ok=True)
        _rotate_if_needed(_AUDIT_PATH)
        with open(_AUDIT_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return True
    except OSError:
        return False


def write_attempt(
    *,
    runner: str,
    provider: str,
    usage_role: Optional[str] = None,
    task_id: Optional[int] = None,
    run_id: Optional[str] = None,
    model: Optional[str] = None,
    command: Optional[str] = None,
    trigger_source: str = "unknown",
    correlation_id: Optional[str] = None,
    requires_llm: bool = True,
    policy_allowed: bool = True,
    caller_skip_frames: int = 4,
) -> Optional[str]:
    """
    寫入 LLM_CALL_ATTEMPT 事件。

    **必須在外部 LLM 呼叫之前呼叫。**

    回傳 correlation_id（用於後續 write_result / write_blocked）。
    回傳 None 表示寫入失敗 → 呼叫端必須 fail-closed，不得執行外部呼叫。
    """
    norm_provider = _normalize_provider(provider)
    if not _is_external(norm_provider):
        return str(correlation_id or uuid.uuid4())  # 本地 provider 無需稽核

    cid = str(correlation_id or uuid.uuid4())
    caller_info = _get_caller_info(skip_frames=caller_skip_frames)

    record: dict = {
        "timestamp": _utc_now_iso(),
        "correlation_id": cid,
        "event_type": EVENT_ATTEMPT,
        "runner_type": runner,
        "usage_role": usage_role or _normalize_role(runner),
        "provider": norm_provider,
        "model": model,
        "task_id": task_id,
        "run_id": run_id,
        "trigger_source": trigger_source,
        "command": command,
        "requires_llm": requires_llm,
        "policy_allowed": policy_allowed,
        "blocked": False,
        "block_reason": None,
        "success": None,
        "error": None,
        "duration_ms": None,
        "input_tokens": 0,
        "output_tokens": 0,
        "cached_tokens": 0,
        "total_tokens": 0,
        "premium_requests": 0,
        "rate_limit_type": None,
        "rate_limit_used_pct": None,
        "rate_limit_reset_raw": None,
        "raw_usage_excerpt": None,
        **caller_info,
    }
    success = _write_audit_record(record)
    return cid if success else None


def write_result(
    *,
    correlation_id: str,
    runner: str,
    provider: str,
    success: bool,
    usage_role: Optional[str] = None,
    task_id: Optional[int] = None,
    run_id: Optional[str] = None,
    model: Optional[str] = None,
    error: Optional[str] = None,
    duration_ms: Optional[float] = None,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cached_tokens: int = 0,
    premium_requests: int = 0,
    rate_limit_type: Optional[str] = None,
    rate_limit_used_pct: Optional[float] = None,
    rate_limit_reset_raw: Optional[str] = None,
    raw_usage_excerpt: Optional[str] = None,
    trigger_source: str = "unknown",
    caller_skip_frames: int = 4,
) -> None:
    """
    寫入 LLM_CALL_RESULT 事件（呼叫完成後）。
    """
    norm_provider = _normalize_provider(provider)
    if not _is_external(norm_provider):
        return

    caller_info = _get_caller_info(skip_frames=caller_skip_frames)
    total_tokens = input_tokens + output_tokens + cached_tokens

    record: dict = {
        "timestamp": _utc_now_iso(),
        "correlation_id": correlation_id,
        "event_type": EVENT_RESULT,
        "runner_type": runner,
        "usage_role": usage_role or _normalize_role(runner),
        "provider": norm_provider,
        "model": model,
        "task_id": task_id,
        "run_id": run_id,
        "trigger_source": trigger_source,
        "requires_llm": True,
        "policy_allowed": True,
        "blocked": False,
        "block_reason": None,
        "success": success,
        "error": error,
        "duration_ms": duration_ms,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cached_tokens": cached_tokens,
        "total_tokens": total_tokens,
        "premium_requests": premium_requests,
        "rate_limit_type": rate_limit_type,
        "rate_limit_used_pct": rate_limit_used_pct,
        "rate_limit_reset_raw": rate_limit_reset_raw,
        "raw_usage_excerpt": raw_usage_excerpt,
        **caller_info,
    }
    _write_audit_record(record)


def write_blocked(
    *,
    runner: str,
    provider: str,
    block_reason: str,
    usage_role: Optional[str] = None,
    task_id: Optional[int] = None,
    run_id: Optional[str] = None,
    model: Optional[str] = None,
    correlation_id: Optional[str] = None,
    trigger_source: str = "unknown",
    caller_skip_frames: int = 4,
) -> None:
    """
    寫入 LLM_CALL_BLOCKED 事件（政策阻止或稽核失敗）。
    """
    norm_provider = _normalize_provider(provider)
    caller_info = _get_caller_info(skip_frames=caller_skip_frames)
    cid = str(correlation_id or uuid.uuid4())

    record: dict = {
        "timestamp": _utc_now_iso(),
        "correlation_id": cid,
        "event_type": EVENT_BLOCKED,
        "runner_type": runner,
        "usage_role": usage_role or _normalize_role(runner),
        "provider": norm_provider,
        "model": model,
        "task_id": task_id,
        "run_id": run_id,
        "trigger_source": trigger_source,
        "requires_llm": True,
        "policy_allowed": False,
        "blocked": True,
        "block_reason": block_reason,
        "success": False,
        "error": None,
        "duration_ms": None,
        "input_tokens": 0,
        "output_tokens": 0,
        "cached_tokens": 0,
        "total_tokens": 0,
        "premium_requests": 0,
        "rate_limit_type": None,
        "rate_limit_used_pct": None,
        "rate_limit_reset_raw": None,
        "raw_usage_excerpt": None,
        **caller_info,
    }
    _write_audit_record(record)


# ── 讀取 / 聚合 API ────────────────────────────────────────────────────────

def read_audit_records(
    hours: int = 24,
    tail: int = 0,
    runner: Optional[str] = None,
    provider: Optional[str] = None,
    blocked: Optional[bool] = None,
    event_type: Optional[str] = None,
) -> list[dict]:
    """
    讀取 llm_audit.jsonl，支援時間窗口與多種篩選條件。
    """
    records: list[dict] = []
    paths = [_AUDIT_PATH]
    rotated = _AUDIT_PATH + ".1"
    if os.path.exists(rotated):
        paths = [rotated, _AUDIT_PATH]

    cutoff: Optional[datetime] = None
    if hours > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    for path in paths:
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(rec, dict):
                        continue
                    # 時間過濾
                    if cutoff:
                        ts_raw = rec.get("timestamp", "")
                        if ts_raw:
                            try:
                                ts = datetime.fromisoformat(ts_raw)
                                if ts.tzinfo is None:
                                    ts = ts.replace(tzinfo=timezone.utc)
                                if ts < cutoff:
                                    continue
                            except ValueError:
                                pass
                    # 篩選
                    if runner and rec.get("runner_type") != runner:
                        continue
                    if provider and rec.get("provider") != provider:
                        continue
                    if blocked is not None and rec.get("blocked") != blocked:
                        continue
                    if event_type and rec.get("event_type") != event_type:
                        continue
                    records.append(rec)
        except OSError:
            pass

    if tail > 0:
        return records[-tail:]
    return records


def build_audit_today_summary() -> dict:
    """
    彙整今日 LLM 稽核事件摘要，依 role / provider 分組。
    """
    cutoff_str = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    ).isoformat()
    cutoff = datetime.fromisoformat(cutoff_str)

    records = read_audit_records(hours=0)  # 讀全部
    today_records = []
    for rec in records:
        ts_raw = rec.get("timestamp", "")
        try:
            ts = datetime.fromisoformat(ts_raw)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if ts >= cutoff:
                today_records.append(rec)
        except ValueError:
            pass

    total = len(today_records)
    attempts = sum(1 for r in today_records if r.get("event_type") == EVENT_ATTEMPT)
    results  = sum(1 for r in today_records if r.get("event_type") == EVENT_RESULT)
    blocked  = sum(1 for r in today_records if r.get("event_type") == EVENT_BLOCKED)
    succeeded = sum(1 for r in today_records if r.get("event_type") == EVENT_RESULT and r.get("success"))
    failed    = sum(1 for r in today_records if r.get("event_type") == EVENT_RESULT and not r.get("success"))

    by_role: dict[str, dict] = {}
    by_provider: dict[str, dict] = {}

    for rec in today_records:
        role = rec.get("usage_role", "unknown")
        prov = rec.get("provider", "unknown")
        etype = rec.get("event_type", "")

        if role not in by_role:
            by_role[role] = {"attempts": 0, "results": 0, "blocked": 0, "succeeded": 0, "failed": 0}
        if prov not in by_provider:
            by_provider[prov] = {"attempts": 0, "results": 0, "blocked": 0, "succeeded": 0, "failed": 0}

        if etype == EVENT_ATTEMPT:
            by_role[role]["attempts"] += 1
            by_provider[prov]["attempts"] += 1
        elif etype == EVENT_RESULT:
            by_role[role]["results"] += 1
            by_provider[prov]["results"] += 1
            if rec.get("success"):
                by_role[role]["succeeded"] += 1
                by_provider[prov]["succeeded"] += 1
            else:
                by_role[role]["failed"] += 1
                by_provider[prov]["failed"] += 1
        elif etype == EVENT_BLOCKED:
            by_role[role]["blocked"] += 1
            by_provider[prov]["blocked"] += 1

    return {
        "date": datetime.now(timezone.utc).date().isoformat(),
        "total_events": total,
        "attempts": attempts,
        "results": results,
        "blocked": blocked,
        "succeeded": succeeded,
        "failed": failed,
        "by_role": by_role,
        "by_provider": by_provider,
    }
