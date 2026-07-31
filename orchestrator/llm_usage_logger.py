"""
orchestrator/llm_usage_logger.py

Universal AI / GitHub Usage Logger — 結構化 JSONL 使用量記錄器。

每次外部 AI / GitHub 呼叫（允許或封鎖）都寫入一行 JSON 到：
    runtime/agent_orchestrator/llm_usage.jsonl

覆蓋的外部工具：
- Claude / Claude Code / Anthropic API
- Codex / Codex CLI / OpenAI
- GitHub Copilot / copilot-daemon
- GitHub CLI (gh) / GitHub API
- Gemini CLI / Gemini API

設計原則：
- 非同步安全（append-mode 寫入，不鎖檔）
- 不引入外部套件
- 所有例外皆為非致命（寫入失敗不中斷執行流程）
- 超過 _MAX_FILE_BYTES（50 MB）時自動輪轉為 .1
"""
from __future__ import annotations

import json
import os
import re
import traceback
import uuid
from datetime import datetime, timezone
from typing import Optional

_LOG_PATH: str = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "runtime",
    "agent_orchestrator",
    "llm_usage.jsonl",
)
_MAX_FILE_BYTES: int = 50 * 1024 * 1024  # 50 MB

# Runner 名稱 → 標準化 role 對照表
_RUNNER_TO_ROLE: dict[str, str] = {
    "planner":          "planner",
    "planner_tick":     "planner",
    "worker":           "worker",
    "worker_tick":      "worker",
    "cto":              "cto",
    "cto_review_tick":  "cto",
    "copilot_daemon":   "worker",
    "copilot-daemon":   "worker",
    "manual":           "manual",
    "backfill":         "backfill",
}

# Provider 標準化別名
_PROVIDER_ALIASES: dict[str, str] = {
    "claude-cli":     "claude",
    "claude-code":    "claude",
    "anthropic":      "claude",
    "codex-cli":      "codex",
    "openai":         "codex",
    "copilot":        "github-copilot",
    "gh-copilot":     "github-copilot",
    "github-copilot": "github-copilot",
    "copilot-daemon": "github-copilot",
    "gh-api":         "github-api",
    "gh-cli":         "github-cli",
    "gh":             "github-cli",
    "gemini-cli":     "gemini",
}

# Rate limit 偵測關鍵字
_RATE_LIMIT_MARKERS = (
    "rate limit", "weekly rate limit", "you've hit your rate limit",
    "usage limit", "hit your usage limit",
    "try again at", "purchase more credits",
    "premium request limit", "429", "quota exceeded",
)

# Token 解析正規式：嘗試從輸出文字中提取 tokens
_INPUT_TOKEN_RE = re.compile(r"input[_ ]tokens?[:\s]+(\d+)", re.IGNORECASE)
_OUTPUT_TOKEN_RE = re.compile(r"output[_ ]tokens?[:\s]+(\d+)", re.IGNORECASE)
_CACHED_TOKEN_RE = re.compile(r"cache(?:d|_read)[_ ]tokens?[:\s]+(\d+)", re.IGNORECASE)
_PREMIUM_RE = re.compile(r"premium[_ ]requests?[:\s]+(\d+)", re.IGNORECASE)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_role(runner: str) -> str:
    """Runner 名稱 → 標準化 role 字串。"""
    return _RUNNER_TO_ROLE.get(str(runner or "").strip().lower(), "unknown")


def _normalize_provider(provider: str) -> str:
    """Provider 名稱 → 標準化字串（保留 codex / claude / github-* 等）。"""
    key = str(provider or "").strip().lower()
    return _PROVIDER_ALIASES.get(key, key)


def _get_caller_stack(skip_frames: int = 3) -> list[str]:
    """取得精簡的呼叫堆疊（略去此函式本身及 skip_frames 個框架）。"""
    frames = traceback.extract_stack()
    cutoff = max(0, len(frames) - skip_frames)
    return [
        f"{f.filename}:{f.lineno} in {f.name}"
        for f in frames[:cutoff]
    ]


def _rotate_if_needed(path: str) -> None:
    """若 JSONL 超過 _MAX_FILE_BYTES 則輪轉（舊檔改名為 .1）。"""
    try:
        if os.path.exists(path) and os.path.getsize(path) > _MAX_FILE_BYTES:
            rotated = path + ".1"
            if os.path.exists(rotated):
                os.remove(rotated)
            os.rename(path, rotated)
    except OSError:
        pass


def parse_token_usage(text: str) -> dict[str, int]:
    """
    嘗試從 LLM 輸出文字解析 token 使用量。
    回傳 {"input_tokens": N, "output_tokens": N, "cached_tokens": N, "premium_requests": N}
    """
    result: dict[str, int] = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cached_tokens": 0,
        "premium_requests": 0,
    }
    if not text:
        return result
    m = _INPUT_TOKEN_RE.search(text)
    if m:
        result["input_tokens"] = int(m.group(1))
    m = _OUTPUT_TOKEN_RE.search(text)
    if m:
        result["output_tokens"] = int(m.group(1))
    m = _CACHED_TOKEN_RE.search(text)
    if m:
        result["cached_tokens"] = int(m.group(1))
    m = _PREMIUM_RE.search(text)
    if m:
        result["premium_requests"] = int(m.group(1))
    return result


def detect_rate_limit(text: str) -> bool:
    """回傳 True 若文字包含 rate limit / quota 相關關鍵字。"""
    low = str(text or "").lower()
    return any(m in low for m in _RATE_LIMIT_MARKERS)


def log_usage(
    *,
    runner: str,
    provider: str,
    blocked: bool,
    # 標準化欄位
    role: Optional[str] = None,
    agent: Optional[str] = None,
    task_id: Optional[int] = None,
    correlation_id: Optional[str] = None,
    entrypoint: Optional[str] = None,
    command: Optional[str] = None,
    # 政策欄位
    allowed: bool = True,
    block_reason: Optional[str] = None,
    # 執行結果
    success: Optional[bool] = None,
    parsed: Optional[bool] = None,
    error: Optional[str] = None,
    # 使用量計量
    premium_requests: int = 0,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cached_tokens: int = 0,
    rate_limit: Optional[bool] = None,
    rate_limit_reset: Optional[str] = None,
    raw_usage_text: Optional[str] = None,
    # 來源追蹤
    source_file: Optional[str] = None,
    source_function: Optional[str] = None,
    # 內部
    model: Optional[str] = None,
    requires_llm: bool = True,
    allowed_by_policy: bool = True,
    caller_skip_frames: int = 3,
) -> None:
    """
    寫入一筆完整的外部 AI / GitHub 使用量記錄至 llm_usage.jsonl。

    這是主要入口點，覆蓋所有外部呼叫（Claude/Codex/Copilot/GitHub）。

    必填欄位：
        runner    — 呼叫者 ID，例如 "worker_tick", "planner", "copilot_daemon"
        provider  — 提供者，例如 "codex", "claude", "github-copilot", "github-cli"
        blocked   — True = 此次呼叫被封鎖（未執行）

    使用量欄位（可選）：
        premium_requests, input_tokens, output_tokens, cached_tokens,
        rate_limit, raw_usage_text
    """
    norm_provider = _normalize_provider(provider)
    norm_role = role or _normalize_role(runner)

    # 若有 raw_usage_text，嘗試補充 token 資訊
    if raw_usage_text and not input_tokens and not output_tokens:
        parsed_tokens = parse_token_usage(raw_usage_text)
        if not input_tokens:
            input_tokens = parsed_tokens["input_tokens"]
        if not output_tokens:
            output_tokens = parsed_tokens["output_tokens"]
        if not cached_tokens:
            cached_tokens = parsed_tokens["cached_tokens"]
        if not premium_requests:
            premium_requests = parsed_tokens["premium_requests"]

    # 若有 raw_usage_text，嘗試偵測 rate limit
    if raw_usage_text and rate_limit is None:
        rate_limit = detect_rate_limit(raw_usage_text)

    record: dict = {
        "timestamp": _utc_now_iso(),
        "correlation_id": correlation_id or str(uuid.uuid4()),
        "role": norm_role,
        "runner": runner,
        "agent": agent,
        "task_id": task_id,
        "provider": norm_provider,
        "model": model,
        "agent_command": command,  # renamed to avoid confusion
        "entrypoint": entrypoint,
        "source_file": source_file,
        "source_function": source_function,
        # 政策欄位
        "allowed": allowed and not blocked,
        "blocked": blocked,
        "block_reason": block_reason,
        "requires_llm": requires_llm,
        "allowed_by_policy": allowed_by_policy,
        # 執行結果
        "success": success,
        "parsed": parsed,
        "error": error,
        # 使用量計量
        "premium_requests": premium_requests,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cached_tokens": cached_tokens,
        "rate_limit": rate_limit,
        "rate_limit_reset": rate_limit_reset,
        "raw_usage_text": raw_usage_text,
        # 堆疊追蹤
        "caller_stack": _get_caller_stack(skip_frames=caller_skip_frames),
    }
    try:
        os.makedirs(os.path.dirname(_LOG_PATH), exist_ok=True)
        _rotate_if_needed(_LOG_PATH)
        with open(_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass  # 寫入失敗為非致命錯誤，不中斷執行流程


def log_llm_event(
    *,
    runner: str,
    provider: str,
    blocked: bool,
    block_reason: Optional[str] = None,
    task_id: Optional[int] = None,
    correlation_id: Optional[str] = None,
    entrypoint: Optional[str] = None,
    model: Optional[str] = None,
    command: Optional[str] = None,
    requires_llm: bool = True,
    allowed_by_policy: bool = True,
    success: Optional[bool] = None,
    error: Optional[str] = None,
    input_tokens: Optional[int] = None,
    output_tokens: Optional[int] = None,
    caller_skip_frames: int = 3,
) -> None:
    """
    向後相容入口點 — 委派至 log_usage()。

    新程式碼應直接呼叫 log_usage()。
    """
    log_usage(
        runner=runner,
        provider=provider,
        blocked=blocked,
        block_reason=block_reason,
        task_id=task_id,
        correlation_id=correlation_id,
        entrypoint=entrypoint,
        model=model,
        command=command,
        requires_llm=requires_llm,
        allowed_by_policy=allowed_by_policy,
        allowed=not blocked,
        success=success,
        error=error,
        input_tokens=input_tokens or 0,
        output_tokens=output_tokens or 0,
        caller_skip_frames=caller_skip_frames + 1,
    )
