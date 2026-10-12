"""
orchestrator/llm_usage_summary.py

Usage 詳細卡片 — LLM / AI / GitHub 呼叫量摘要。

提供：
    format_tokens(input, output, cached) → "↑382.5k / ↓7.9k / 330.5kc"
    get_usage_summary(window, limit)     → 結構化摘要 dict

此模組只讀取本地 llm_usage.jsonl，絕不呼叫外部 API 或消耗配額。
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone, timedelta
from typing import Optional

_LOG_PATH: str = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "runtime",
    "agent_orchestrator",
    "llm_usage.jsonl",
)

# 外部 provider 集合：出現在 planner/cto 代表 Policy 異常
_EXTERNAL_PROVIDERS: frozenset[str] = frozenset({
    "codex", "codex-cli", "openai",
    "claude", "claude-cli", "claude-code", "anthropic",
    "copilot", "copilot-daemon", "github-copilot",
    "github-cli", "github-api", "git-remote",
    "gemini", "gemini-cli",
})

# Agent 顯示名稱映射（provider → 人類可讀名稱）
_PROVIDER_DISPLAY: dict[str, str] = {
    "github-copilot": "Copilot-Daemon",
    "copilot":        "Copilot-Daemon",
    "copilot-daemon": "Copilot-Daemon",
    "codex":          "Codex",
    "codex-cli":      "Codex CLI",
    "claude":         "Claude",
    "claude-cli":     "Claude CLI",
    "openai":         "OpenAI",
    "anthropic":      "Anthropic",
    "github-cli":     "GitHub CLI",
    "github-api":     "GitHub API",
    "git-remote":     "Git Remote",
    "gemini":         "Gemini",
    "gemini-cli":     "Gemini CLI",
}


# ── Token 格式化 ──────────────────────────────────────────────────────────

def _fmt_num(n: int) -> str:
    """
    將整數格式化為人類易讀格式：
        0        → "0"
        999      → "999"
        1_000    → "1.0k"
        382_500  → "382.5k"
        3_800_000 → "3.8M"
    """
    if n >= 1_000_000:
        v = n / 1_000_000
        return f"{v:.1f}M" if v != int(v) else f"{int(v)}M"
    if n >= 1_000:
        v = n / 1_000
        return f"{v:.1f}k" if v != int(v) else f"{int(v)}k"
    return str(n)


def format_tokens(
    input_tokens: int,
    output_tokens: int,
    cached_tokens: int = 0,
) -> str:
    """
    回傳格式化的 token 使用量字串。

    範例：
        format_tokens(382500, 7900, 330500) → "↑382.5k / ↓7.9k / 330.5kc"
        format_tokens(0, 0, 0)              → "↑0 / ↓0"
        format_tokens(1000, 500)            → "↑1.0k / ↓500"
    """
    parts = [f"↑{_fmt_num(input_tokens)}", f"↓{_fmt_num(output_tokens)}"]
    if cached_tokens:
        parts.append(f"{_fmt_num(cached_tokens)}c")
    return " / ".join(parts)


# ── 時間窗口解析 ──────────────────────────────────────────────────────────

def _window_cutoff(window: str) -> Optional[datetime]:
    """
    將窗口字串轉換為 UTC cutoff datetime。
    支援：
        "today"  → 今日 00:00 UTC
        "24h"    → 24 小時前
        "48h"    → 48 小時前
        "7d"     → 7 天前
        "all"    → None（無限制）
    """
    now = datetime.now(timezone.utc)
    if window == "today":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if window == "all":
        return None
    if window.endswith("h"):
        return now - timedelta(hours=int(window[:-1]))
    if window.endswith("d"):
        return now - timedelta(days=int(window[:-1]))
    # 預設 today
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


# ── 空白 role 骨架 ────────────────────────────────────────────────────────

def _empty_role() -> dict:
    return {
        "calls": 0,
        "blocked": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cached_tokens": 0,
        "premium_requests": 0,
        "agents": {},
    }


def _empty_agent() -> dict:
    return {
        "calls": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cached_tokens": 0,
    }


# ── 核心讀取函式 ──────────────────────────────────────────────────────────

def _load_records(cutoff: Optional[datetime]) -> list[dict]:
    """讀取 JSONL，跳過損壞行，回傳有效記錄。"""
    records: list[dict] = []
    if not os.path.exists(_LOG_PATH):
        return records
    try:
        with open(_LOG_PATH, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    records.append({"_malformed": True})
                    continue
                if not isinstance(rec, dict):
                    continue
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
                records.append(rec)
    except OSError:
        pass
    return records


# ── 主要摘要函式 ──────────────────────────────────────────────────────────

def get_usage_summary(window: str = "today", limit: int = 10) -> dict:
    """
    讀取 llm_usage.jsonl 並回傳結構化摘要。

    Args:
        window: 時間窗口 ("today" | "24h" | "48h" | "7d" | "all")
        limit:  最近記錄筆數（recent 列表長度）

    回傳結構：
    {
        "window": "today",
        "total": {
            "calls": N, "input_tokens": N, "output_tokens": N,
            "cached_tokens": N, "premium_requests": N
        },
        "roles": {
            "planner": {"calls": 0, "blocked": 0, "input_tokens": 0, ..., "agents": {}},
            "worker":  {...},
            "cto":     {...},
        },
        "warnings": ["⚠️ Planner 有外部 LLM 呼叫紀錄，請檢查 Provider Safety"],
        "recent": [
            {
                "time": "18:49:46",
                "role": "worker",
                "agent": "Copilot-Daemon",
                "task_id": 380,
                "parsed": true,
                "premium_requests": 0,
                "tokens_text": "↑382.5k / ↓7.9k / 330.5kc",
                "rate_limit": "—",
                "blocked": false,
            },
            ...
        ],
        "malformed_count": 0,
    }
    """
    cutoff = _window_cutoff(window)
    all_records = _load_records(cutoff)

    total: dict = {
        "calls": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cached_tokens": 0,
        "premium_requests": 0,
    }

    roles: dict[str, dict] = {
        "planner": _empty_role(),
        "worker":  _empty_role(),
        "cto":     _empty_role(),
    }

    malformed_count = 0
    valid_records: list[dict] = []

    for rec in all_records:
        if rec.get("_malformed"):
            malformed_count += 1
            continue

        # role 解析：優先用 role 欄位，fallback runner
        role = str(rec.get("role") or rec.get("runner") or "unknown").lower()

        # runner→role 映射（舊格式相容）
        _runner_map = {
            "planner_tick": "planner",
            "worker_tick":  "worker",
            "cto_review_tick": "cto",
            "copilot_daemon": "worker",
        }
        role = _runner_map.get(role, role)

        provider = str(rec.get("provider") or "").lower()
        agent_display = _PROVIDER_DISPLAY.get(provider, provider or "unknown")

        in_tok  = int(rec.get("input_tokens") or 0)
        out_tok = int(rec.get("output_tokens") or 0)
        cac_tok = int(rec.get("cached_tokens") or 0)
        prem    = int(rec.get("premium_requests") or 0)
        blocked = bool(rec.get("blocked"))

        # 全域累計（封鎖的也計）
        total["calls"] += 1
        total["input_tokens"]  += in_tok
        total["output_tokens"] += out_tok
        total["cached_tokens"] += cac_tok
        total["premium_requests"] += prem

        # 按 role 累計
        if role not in roles:
            roles[role] = _empty_role()
        r = roles[role]
        r["calls"] += 1
        if blocked:
            r["blocked"] += 1
        r["input_tokens"]  += in_tok
        r["output_tokens"] += out_tok
        r["cached_tokens"] += cac_tok
        r["premium_requests"] += prem

        # 按 agent 累計（role 內）
        if not blocked and provider:
            agents = r["agents"]
            if agent_display not in agents:
                agents[agent_display] = _empty_agent()
            a = agents[agent_display]
            a["calls"] += 1
            a["input_tokens"]  += in_tok
            a["output_tokens"] += out_tok
            a["cached_tokens"] += cac_tok

        valid_records.append(rec)

    # ── Provider Safety 告警 ──────────────────────────────────────────────
    warnings: list[str] = []
    for role_name in ("planner", "cto"):
        rdata = roles.get(role_name, {})
        ext_calls = rdata.get("calls", 0) - rdata.get("blocked", 0)
        # 允許的外部呼叫：有 input/output tokens 或 success=True 且非 blocked
        if ext_calls > 0:
            # 確認是否有真正的外部 provider（非 local/none）
            has_external = any(
                str(rec.get("role") or rec.get("runner") or "").lower() in (role_name, f"{role_name}_tick")
                and str(rec.get("provider") or "").lower() in _EXTERNAL_PROVIDERS
                and not rec.get("blocked")
                for rec in valid_records
            )
            if has_external:
                warnings.append(
                    f"⚠️ {role_name.upper()} 有外部 LLM 呼叫紀錄，請檢查 Provider Safety"
                )

    # ── Recent 明細（最新在前）───────────────────────────────────────────
    recent: list[dict] = []
    for rec in reversed(valid_records):
        if len(recent) >= limit:
            break

        ts_raw = rec.get("timestamp", "")
        try:
            ts = datetime.fromisoformat(ts_raw)
            time_str = ts.strftime("%H:%M:%S")
        except (ValueError, AttributeError):
            time_str = "—"

        role = str(rec.get("role") or rec.get("runner") or "unknown").lower()
        _runner_map2 = {
            "planner_tick": "planner",
            "worker_tick":  "worker",
            "cto_review_tick": "cto",
            "copilot_daemon": "worker",
        }
        role = _runner_map2.get(role, role)

        provider = str(rec.get("provider") or "").lower()
        agent_display = _PROVIDER_DISPLAY.get(provider, provider or "—")

        in_tok  = int(rec.get("input_tokens") or 0)
        out_tok = int(rec.get("output_tokens") or 0)
        cac_tok = int(rec.get("cached_tokens") or 0)
        has_tokens = bool(in_tok or out_tok or cac_tok)
        tokens_text = format_tokens(in_tok, out_tok, cac_tok) if has_tokens else "—"

        rate_limit = rec.get("rate_limit")
        if rate_limit is True:
            rate_limit_str = "⚠️ RL"
        elif rate_limit is False:
            rate_limit_str = "—"
        else:
            rate_limit_str = "—"

        # parsed: success=True 且 output 不為空
        success = rec.get("success")
        parsed_flag = success is True

        recent.append({
            "time":             time_str,
            "role":             role,
            "agent":            agent_display,
            "task_id":          rec.get("task_id"),
            "parsed":           parsed_flag,
            "premium_requests": int(rec.get("premium_requests") or 0),
            "tokens_text":      tokens_text,
            "rate_limit":       rate_limit_str,
            "blocked":          bool(rec.get("blocked")),
            "block_reason":     rec.get("block_reason"),
            "source_function":  rec.get("source_function"),
        })

    return {
        "window":         window,
        "total":          total,
        "roles":          roles,
        "warnings":       warnings,
        "recent":         recent,
        "malformed_count": malformed_count,
    }
