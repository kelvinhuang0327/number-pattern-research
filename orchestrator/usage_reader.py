"""
orchestrator/usage_reader.py

llm_usage.jsonl 讀取與聚合模組。

提供兩個函式：
    read_usage_records(hours, tail) → list[dict]
    build_usage_summary(records, recent_n) → dict

供 api.py 的 GET /api/orchestrator/usage 使用。
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone, timedelta
from typing import Optional

# 與 llm_usage_logger 保持相同路徑
_LOG_PATH: str = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "runtime",
    "agent_orchestrator",
    "llm_usage.jsonl",
)

_KNOWN_ROLES: list[str] = ["planner", "worker", "cto", "manual", "backfill", "unknown"]

_KNOWN_PROVIDERS: list[str] = [
    "codex",
    "claude",
    "github-copilot",
    "github-cli",
    "github-api",
    "git-remote",
    "openai",
    "anthropic",
    "gemini",
    "other",
]


def read_usage_records(hours: int = 24, tail: int = 0) -> list[dict]:
    """
    讀取 llm_usage.jsonl，回傳最近 `hours` 小時的記錄。

    Args:
        hours: 時間窗口（0 = 無限制）
        tail:  若 > 0，只回傳最後 `tail` 筆（不受 hours 限制）

    回傳值：已解析的 dict 列表（跳過損壞的 JSON 行）
    """
    records: list[dict] = []
    if not os.path.exists(_LOG_PATH):
        return records

    cutoff: Optional[datetime] = None
    if hours > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    try:
        with open(_LOG_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    # 損壞的行跳過（不崩潰）
                    records.append({"_malformed": True, "raw": line[:120]})
                    continue
                if cutoff and isinstance(rec, dict):
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
                records.append(rec)
    except OSError:
        pass

    if tail > 0:
        return records[-tail:]
    return records


def build_usage_summary(records: list[dict], recent_n: int = 10) -> dict:
    """
    從記錄列表建構摘要統計。

    回傳結構：
    {
        "total": N,
        "allowed": N,
        "blocked": N,
        "malformed": N,
        "by_role": {"planner": {...}, "worker": {...}, ...},
        "by_provider": {"codex": N, "claude": N, ...},
        "block_reasons": {"ROLE_PROVIDER_VIOLATION": N, ...},
        "rate_limited": N,
        "tokens": {"input": N, "output": N, "cached": N, "premium_requests": N},
        "recent": [last N records (not malformed)],
    }
    """
    total = 0
    allowed_cnt = 0
    blocked_cnt = 0
    malformed_cnt = 0
    rate_limited_cnt = 0

    by_role: dict[str, dict] = {}
    by_provider: dict[str, int] = {}
    block_reasons: dict[str, int] = {}
    tokens: dict[str, int] = {"input": 0, "output": 0, "cached": 0, "premium_requests": 0}

    valid_records: list[dict] = []

    for rec in records:
        if not isinstance(rec, dict):
            malformed_cnt += 1
            continue
        if rec.get("_malformed"):
            malformed_cnt += 1
            continue

        total += 1
        valid_records.append(rec)

        if rec.get("blocked"):
            blocked_cnt += 1
        else:
            allowed_cnt += 1

        if rec.get("rate_limit"):
            rate_limited_cnt += 1

        # 角色聚合
        role = str(rec.get("role") or "unknown")
        if role not in by_role:
            by_role[role] = {"total": 0, "allowed": 0, "blocked": 0, "rate_limited": 0}
        by_role[role]["total"] += 1
        if rec.get("blocked"):
            by_role[role]["blocked"] += 1
        else:
            by_role[role]["allowed"] += 1
        if rec.get("rate_limit"):
            by_role[role]["rate_limited"] += 1

        # Provider 聚合
        provider = str(rec.get("provider") or "other")
        by_provider[provider] = by_provider.get(provider, 0) + 1

        # 封鎖原因
        if rec.get("blocked") and rec.get("block_reason"):
            reason = str(rec["block_reason"])
            block_reasons[reason] = block_reasons.get(reason, 0) + 1

        # Token 累計
        tokens["input"] += int(rec.get("input_tokens") or 0)
        tokens["output"] += int(rec.get("output_tokens") or 0)
        tokens["cached"] += int(rec.get("cached_tokens") or 0)
        tokens["premium_requests"] += int(rec.get("premium_requests") or 0)

    # 近期記錄（排除內部欄位 raw_usage_text 節省大小）
    recent = []
    for r in valid_records[-recent_n:] if recent_n else []:
        slim = {k: v for k, v in r.items() if k not in ("raw_usage_text", "caller_stack")}
        recent.append(slim)

    return {
        "total": total,
        "allowed": allowed_cnt,
        "blocked": blocked_cnt,
        "malformed": malformed_cnt,
        "rate_limited": rate_limited_cnt,
        "by_role": by_role,
        "by_provider": by_provider,
        "block_reasons": block_reasons,
        "tokens": tokens,
        "recent": recent,
    }
