"""
orchestrator/usage_budget_guard.py

Phase 36: Usage Budget Guard — 確定性預算管制層。

決策結果：
    OK          — 全部在閾值以下
    WARN        — 接近閾值（Copilot/Claude 呼叫偏高、blocked attempts 偏多）
    CRITICAL    — 超過 critical 閾值，或 Planner/CTO 發生外部呼叫
    HARD_CAP    — 超過 hard_cap 閾值；Worker 外部 AI 呼叫強制停止

硬性規則：
- 不呼叫任何外部 AI / API
- 不修改 usage log
- 不弱化 AuditGuard
- 不封鎖確定性安全任務
- 讀取 llm_usage.jsonl + usage_budget_config.json（均為本地 runtime 檔案）

Usage:
    from orchestrator.usage_budget_guard import evaluate_usage_budget, is_provider_allowed
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone, timedelta
from typing import Optional

# ── 路徑常數 ─────────────────────────────────────────────────────────────────

_RUNTIME_DIR: str = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "runtime",
    "agent_orchestrator",
)
_BUDGET_CONFIG_PATH: str = os.path.join(_RUNTIME_DIR, "usage_budget_config.json")
_USAGE_LOG_PATH: str = os.path.join(_RUNTIME_DIR, "llm_usage.jsonl")

# ── 決策層級（嚴重性由低到高）─────────────────────────────────────────────────

_STATUS_RANK: dict[str, int] = {
    "OK": 0,
    "WARN": 1,
    "CRITICAL": 2,
    "HARD_CAP": 3,
}

# ── Provider 標準化（與 llm_usage_logger 一致）──────────────────────────────

_PROVIDER_ALIASES: dict[str, str] = {
    "claude-cli": "claude",
    "claude-code": "claude",
    "anthropic": "claude",
    "codex-cli": "codex",
    "openai": "codex",
    "copilot": "github-copilot",
    "gh-copilot": "github-copilot",
    "copilot-daemon": "github-copilot",
    "gh-api": "github-api",
    "gh-cli": "github-cli",
    "gh": "github-cli",
    "gemini-cli": "gemini",
}

# ── Runner → Role 映射 ───────────────────────────────────────────────────────

_RUNNER_TO_ROLE: dict[str, str] = {
    "planner": "planner",
    "planner_tick": "planner",
    "worker": "worker",
    "worker_tick": "worker",
    "cto": "cto",
    "cto_review_tick": "cto",
    "copilot_daemon": "worker",
    "copilot-daemon": "worker",
    "manual": "manual",
    "backfill": "backfill",
}

# ── 確定性安全任務（絕不封鎖）──────────────────────────────────────────────

DETERMINISTIC_SAFE_TASKS: frozenset[str] = frozenset({
    "clv_batch_accumulation",
    "clv_threshold_check",
    "production_clv_investigation",
    "usage_budget_check",
    "audit_guard_check",
    "frontend_health_check",
})

# ── 預設設定（config 不存在時的 fallback）───────────────────────────────────

_DEFAULT_CONFIG: dict = {
    "version": "2026-05-04-v1",
    "enabled": True,
    "window": "24h",
    "roles": {
        "planner": {
            "max_allowed_external_calls": 0,
            "severity_on_any_allowed": "CRITICAL",
            "hard_cap": True,
        },
        "cto": {
            "max_allowed_external_calls": 0,
            "severity_on_any_allowed": "CRITICAL",
            "hard_cap": True,
        },
        "worker": {
            "warn_calls": 20,
            "critical_calls": 40,
            "hard_cap_calls": 60,
        },
    },
    "providers": {
        "github-copilot": {
            "warn_calls": 20,
            "critical_calls": 40,
            "hard_cap_calls": 60,
        },
        "copilot-daemon": {
            "warn_calls": 20,
            "critical_calls": 40,
            "hard_cap_calls": 60,
        },
        "claude": {
            "warn_calls": 10,
            "critical_calls": 20,
            "hard_cap_calls": 30,
        },
        "codex": {
            "warn_calls": 5,
            "critical_calls": 10,
            "hard_cap_calls": 15,
        },
    },
    "tokens": {
        "warn_input_tokens": 3_000_000,
        "critical_input_tokens": 6_000_000,
        "hard_cap_input_tokens": 9_000_000,
    },
    "blocked_attempts": {
        "warn": 5,
        "critical": 10,
    },
}


# ── Config 載入 ──────────────────────────────────────────────────────────────

def ensure_default_budget_config() -> None:
    """若 config 不存在，寫入預設值。"""
    if os.path.exists(_BUDGET_CONFIG_PATH):
        return
    try:
        os.makedirs(os.path.dirname(_BUDGET_CONFIG_PATH), exist_ok=True)
        with open(_BUDGET_CONFIG_PATH, "w", encoding="utf-8") as fh:
            json.dump(_DEFAULT_CONFIG, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
    except OSError:
        pass


def load_budget_config() -> dict:
    """
    載入 usage_budget_config.json。

    若檔案不存在或格式損壞，回傳預設值（fail-safe，不崩潰）。
    """
    ensure_default_budget_config()
    try:
        with open(_BUDGET_CONFIG_PATH, "r", encoding="utf-8") as fh:
            cfg = json.load(fh)
        if not isinstance(cfg, dict):
            return dict(_DEFAULT_CONFIG)
        # 補足缺失頂層 key
        for k, v in _DEFAULT_CONFIG.items():
            if k not in cfg:
                cfg[k] = v
        return cfg
    except (OSError, json.JSONDecodeError):
        return dict(_DEFAULT_CONFIG)


# ── Usage Log 讀取 ───────────────────────────────────────────────────────────

def _utc_cutoff(hours: float) -> datetime:
    return datetime.now(timezone.utc) - timedelta(hours=hours)


def _normalize_provider(p: str) -> str:
    key = str(p or "").strip().lower()
    return _PROVIDER_ALIASES.get(key, key)


def _normalize_role(runner: str, role: Optional[str] = None) -> str:
    if role:
        r = str(role).strip().lower()
        if r in _RUNNER_TO_ROLE.values():
            return r
    return _RUNNER_TO_ROLE.get(str(runner or "").strip().lower(), "unknown")


def _load_usage_records(hours: float) -> list[dict]:
    """讀取 llm_usage.jsonl，篩選指定時間窗口內的記錄。"""
    cutoff = _utc_cutoff(hours)
    records: list[dict] = []
    if not os.path.exists(_USAGE_LOG_PATH):
        return records
    try:
        with open(_USAGE_LOG_PATH, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(rec, dict):
                    continue
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


# ── 統計彙整 ─────────────────────────────────────────────────────────────────

def _aggregate_records(records: list[dict]) -> dict:
    """
    回傳彙整結構：
    {
        "roles": {
            "planner": {"calls": N, "blocked": N, "allowed_external": N,
                        "input_tokens": N, "rate_limit_events": N},
            "worker": {...},
            "cto": {...},
        },
        "providers": {
            "github-copilot": {"calls": N, "blocked": N, "input_tokens": N, "rate_limit_events": N},
            "claude": {...},
            "codex": {...},
        },
        "total_input_tokens": N,
        "total_blocked": N,
    }
    """
    roles: dict[str, dict] = {}
    providers: dict[str, dict] = {}
    total_input_tokens: int = 0
    total_blocked: int = 0

    def _role_entry() -> dict:
        return {
            "calls": 0,
            "blocked": 0,
            "allowed_external": 0,
            "input_tokens": 0,
            "rate_limit_events": 0,
        }

    def _prov_entry() -> dict:
        return {
            "calls": 0,
            "blocked": 0,
            "input_tokens": 0,
            "rate_limit_events": 0,
        }

    for rec in records:
        role = _normalize_role(
            rec.get("runner", ""),
            rec.get("role"),
        )
        raw_provider = rec.get("provider", "") or rec.get("agent", "") or ""
        provider = _normalize_provider(str(raw_provider))

        is_blocked = bool(rec.get("blocked", False))
        is_allowed = bool(rec.get("allowed", not is_blocked))
        input_toks = int(rec.get("input_tokens") or 0)
        has_rate_limit = bool(rec.get("rate_limit", False))

        # role 統計
        if role not in ("unknown",):
            if role not in roles:
                roles[role] = _role_entry()
            rr = roles[role]
            if is_blocked:
                rr["blocked"] += 1
            else:
                rr["calls"] += 1
                # 計算 allowed external calls（非 blocked 的外部呼叫）
                if provider and provider not in (
                    "local", "none", "dry-run", "deterministic", "rule-based", ""
                ):
                    rr["allowed_external"] += 1
            rr["input_tokens"] += input_toks
            if has_rate_limit:
                rr["rate_limit_events"] += 1

        # provider 統計
        if provider and provider not in (
            "local", "none", "dry-run", "deterministic", "rule-based", ""
        ):
            if provider not in providers:
                providers[provider] = _prov_entry()
            pp = providers[provider]
            if is_blocked:
                pp["blocked"] += 1
            else:
                pp["calls"] += 1
            pp["input_tokens"] += input_toks
            if has_rate_limit:
                pp["rate_limit_events"] += 1

        total_input_tokens += input_toks
        if is_blocked:
            total_blocked += 1

    return {
        "roles": roles,
        "providers": providers,
        "total_input_tokens": total_input_tokens,
        "total_blocked": total_blocked,
    }


# ── 嚴重性比較工具 ────────────────────────────────────────────────────────────

def _max_status(a: str, b: str) -> str:
    return a if _STATUS_RANK.get(a, 0) >= _STATUS_RANK.get(b, 0) else b


# ── 核心評估函式 ──────────────────────────────────────────────────────────────

def evaluate_usage_budget(hours: float = 24) -> dict:
    """
    評估全域 Usage 預算狀態。

    Args:
        hours: 往回查看的時間窗口（小時）

    Returns:
        {
            "budget_status": "OK|WARN|CRITICAL|HARD_CAP",
            "roles": {...},
            "providers": {...},
            "tokens": {...},
            "warnings": [...],
            "critical_alerts": [...],
            "hard_cap_triggered": bool,
            "recommended_scheduler_mode": "NORMAL|DETERMINISTIC_ONLY|PAUSE_EXTERNAL_AI",
            "allowed_external_providers": [...],
        }
    """
    cfg = load_budget_config()

    if not cfg.get("enabled", True):
        return {
            "budget_status": "OK",
            "roles": {},
            "providers": {},
            "tokens": {"input_tokens": 0},
            "warnings": ["⚠️ Usage Budget Guard disabled in config"],
            "critical_alerts": [],
            "hard_cap_triggered": False,
            "recommended_scheduler_mode": "NORMAL",
            "allowed_external_providers": [],
            "config_version": cfg.get("version", "unknown"),
            "window_hours": hours,
            "enabled": False,
        }

    records = _load_usage_records(hours)
    agg = _aggregate_records(records)

    overall_status = "OK"
    warnings: list[str] = []
    critical_alerts: list[str] = []
    hard_cap_triggered = False

    role_results: dict[str, dict] = {}
    provider_results: dict[str, dict] = {}

    # ── Role 評估 ──────────────────────────────────────────────────────────
    role_cfg = cfg.get("roles", {})

    # Planner：任何外部 allowed call → CRITICAL（或依設定）
    for restricted_role in ("planner", "cto"):
        rcfg = role_cfg.get(restricted_role, {})
        rdata = agg["roles"].get(restricted_role, {})
        allowed_ext = rdata.get("allowed_external", 0)
        blocked_cnt = rdata.get("blocked", 0)
        severity = rcfg.get("severity_on_any_allowed", "CRITICAL")
        is_hard = rcfg.get("hard_cap", True)

        role_status = "OK"
        if allowed_ext > 0:
            role_status = _max_status(role_status, severity)
            msg = (
                f"🚨 {restricted_role.upper()} 發生 {allowed_ext} 次外部 AI 呼叫"
                f"（Policy 異常！）"
            )
            if _STATUS_RANK.get(severity, 0) >= _STATUS_RANK["CRITICAL"]:
                critical_alerts.append(msg)
                if is_hard:
                    hard_cap_triggered = True
                    role_status = _max_status(role_status, "HARD_CAP")
            else:
                warnings.append(msg)

        if blocked_cnt > 0:
            blocked_warn = cfg.get("blocked_attempts", {}).get("warn", 5)
            blocked_crit = cfg.get("blocked_attempts", {}).get("critical", 10)
            if blocked_cnt >= blocked_crit:
                role_status = _max_status(role_status, "CRITICAL")
                critical_alerts.append(
                    f"🚨 {restricted_role.upper()} blocked attempts 偏高：{blocked_cnt} 次"
                )
            elif blocked_cnt >= blocked_warn:
                role_status = _max_status(role_status, "WARN")
                warnings.append(
                    f"⚠️ {restricted_role.upper()} blocked attempts：{blocked_cnt} 次（warn 閾值 {blocked_warn}）"
                )

        overall_status = _max_status(overall_status, role_status)
        role_results[restricted_role] = {
            "status": role_status,
            "calls": rdata.get("calls", 0),
            "blocked": blocked_cnt,
            "allowed_external": allowed_ext,
            "input_tokens": rdata.get("input_tokens", 0),
            "rate_limit_events": rdata.get("rate_limit_events", 0),
        }

    # Worker：閾值三段
    worker_cfg = role_cfg.get("worker", {})
    worker_data = agg["roles"].get("worker", {})
    worker_calls = worker_data.get("calls", 0)
    worker_warn = int(worker_cfg.get("warn_calls", 20))
    worker_crit = int(worker_cfg.get("critical_calls", 40))
    worker_hard = int(worker_cfg.get("hard_cap_calls", 60))

    worker_status = "OK"
    if worker_calls >= worker_hard:
        worker_status = "HARD_CAP"
        hard_cap_triggered = True
        critical_alerts.append(
            f"🚨 Worker 呼叫達 HARD_CAP：{worker_calls}/{worker_hard} 次 — 外部 AI 強制暫停"
        )
    elif worker_calls >= worker_crit:
        worker_status = "CRITICAL"
        critical_alerts.append(
            f"🚨 Worker 呼叫超過 CRITICAL 閾值：{worker_calls}/{worker_crit} 次"
        )
    elif worker_calls >= worker_warn:
        worker_status = "WARN"
        warnings.append(
            f"⚠️ Worker 呼叫偏高：{worker_calls}/{worker_warn} 次"
        )

    worker_blocked = worker_data.get("blocked", 0)
    blocked_warn_thr = cfg.get("blocked_attempts", {}).get("warn", 5)
    blocked_crit_thr = cfg.get("blocked_attempts", {}).get("critical", 10)
    if worker_blocked >= blocked_crit_thr:
        worker_status = _max_status(worker_status, "CRITICAL")
        critical_alerts.append(f"🚨 Worker blocked attempts 達 {worker_blocked} 次")
    elif worker_blocked >= blocked_warn_thr:
        worker_status = _max_status(worker_status, "WARN")
        warnings.append(f"⚠️ Worker blocked attempts：{worker_blocked} 次")

    if worker_data.get("rate_limit_events", 0) > 0:
        worker_status = _max_status(worker_status, "WARN")
        warnings.append(
            f"⚠️ Worker rate limit 觸發：{worker_data['rate_limit_events']} 次"
        )

    overall_status = _max_status(overall_status, worker_status)
    role_results["worker"] = {
        "status": worker_status,
        "calls": worker_calls,
        "blocked": worker_blocked,
        "allowed_external": worker_data.get("allowed_external", 0),
        "input_tokens": worker_data.get("input_tokens", 0),
        "rate_limit_events": worker_data.get("rate_limit_events", 0),
        "warn_calls": worker_warn,
        "critical_calls": worker_crit,
        "hard_cap_calls": worker_hard,
    }

    # ── Provider 評估 ──────────────────────────────────────────────────────
    prov_cfg = cfg.get("providers", {})
    allowed_external_providers: list[str] = []

    for prov_name, pcfg in prov_cfg.items():
        # 標準化 provider key（config 中可能寫 "copilot-daemon" 而 log 裡是 "github-copilot"）
        norm_prov = _normalize_provider(prov_name)
        # 先嘗試 norm_prov，fallback prov_name
        pdata = agg["providers"].get(norm_prov) or agg["providers"].get(prov_name, {})
        p_calls = pdata.get("calls", 0)
        p_warn = int(pcfg.get("warn_calls", 999))
        p_crit = int(pcfg.get("critical_calls", 999))
        p_hard = int(pcfg.get("hard_cap_calls", 999))

        prov_status = "OK"
        if p_calls >= p_hard:
            prov_status = "HARD_CAP"
            hard_cap_triggered = True
            critical_alerts.append(
                f"🚨 {prov_name} 呼叫達 HARD_CAP：{p_calls}/{p_hard} 次"
            )
        elif p_calls >= p_crit:
            prov_status = "CRITICAL"
            critical_alerts.append(
                f"🚨 {prov_name} 呼叫超過 CRITICAL：{p_calls}/{p_crit} 次"
            )
        elif p_calls >= p_warn:
            prov_status = "WARN"
            warnings.append(
                f"⚠️ {prov_name} 呼叫偏高：{p_calls}/{p_warn} 次"
            )

        if pdata.get("rate_limit_events", 0) > 0:
            prov_status = _max_status(prov_status, "WARN")
            warnings.append(
                f"⚠️ {prov_name} rate limit 觸發：{pdata['rate_limit_events']} 次"
            )

        overall_status = _max_status(overall_status, prov_status)
        provider_results[prov_name] = {
            "status": prov_status,
            "calls": p_calls,
            "blocked": pdata.get("blocked", 0),
            "input_tokens": pdata.get("input_tokens", 0),
            "rate_limit_events": pdata.get("rate_limit_events", 0),
            "warn_calls": p_warn,
            "critical_calls": p_crit,
            "hard_cap_calls": p_hard,
        }
        if prov_status != "HARD_CAP":
            allowed_external_providers.append(prov_name)

    # ── Token 評估 ─────────────────────────────────────────────────────────
    tok_cfg = cfg.get("tokens", {})
    total_input = agg["total_input_tokens"]
    tok_warn = int(tok_cfg.get("warn_input_tokens", 3_000_000))
    tok_crit = int(tok_cfg.get("critical_input_tokens", 6_000_000))
    tok_hard = int(tok_cfg.get("hard_cap_input_tokens", 9_000_000))

    tok_status = "OK"
    if total_input >= tok_hard:
        tok_status = "HARD_CAP"
        hard_cap_triggered = True
        critical_alerts.append(
            f"🚨 Token 用量達 HARD_CAP：{total_input:,}/{tok_hard:,} input tokens"
        )
    elif total_input >= tok_crit:
        tok_status = "CRITICAL"
        critical_alerts.append(
            f"🚨 Token 用量超過 CRITICAL：{total_input:,}/{tok_crit:,}"
        )
    elif total_input >= tok_warn:
        tok_status = "WARN"
        warnings.append(
            f"⚠️ Token 用量偏高：{total_input:,}/{tok_warn:,}"
        )

    overall_status = _max_status(overall_status, tok_status)

    token_result = {
        "status": tok_status,
        "input_tokens": total_input,
        "warn_input_tokens": tok_warn,
        "critical_input_tokens": tok_crit,
        "hard_cap_input_tokens": tok_hard,
    }

    # ── 推薦排程模式 ───────────────────────────────────────────────────────
    if hard_cap_triggered or overall_status == "HARD_CAP":
        scheduler_mode = "PAUSE_EXTERNAL_AI"
    elif overall_status == "CRITICAL":
        scheduler_mode = "DETERMINISTIC_ONLY"
    else:
        scheduler_mode = "NORMAL"

    # HARD_CAP 時 allowed_external_providers 全清空
    if hard_cap_triggered:
        allowed_external_providers = []

    return {
        "budget_status": overall_status,
        "roles": role_results,
        "providers": provider_results,
        "tokens": token_result,
        "warnings": warnings,
        "critical_alerts": critical_alerts,
        "hard_cap_triggered": hard_cap_triggered,
        "recommended_scheduler_mode": scheduler_mode,
        "allowed_external_providers": allowed_external_providers,
        "config_version": cfg.get("version", "unknown"),
        "window_hours": hours,
        "enabled": True,
        "total_blocked": agg["total_blocked"],
    }


def is_provider_allowed(role: str, provider: str, hours: float = 24) -> tuple[bool, str]:
    """
    決定指定 role + provider 是否允許外部呼叫。

    Args:
        role:     "worker" | "planner" | "cto"
        provider: "copilot-daemon" | "claude" | "codex" | ...
        hours:    時間窗口（小時）

    Returns:
        (allowed: bool, reason: str)
        - allowed=True  → 允許呼叫
        - allowed=False → 拒絕呼叫，reason 說明原因（USAGE_BUDGET_HARD_CAP 等）
    """
    # 確定性安全任務：永不封鎖（依 task_kind 或 signal_state_type 判斷，
    # 此處以 role="deterministic" 作為明確例外，上層呼叫者可自行繞過）
    if role == "deterministic":
        return True, "DETERMINISTIC_SAFE_TASK"

    result = evaluate_usage_budget(hours=hours)
    budget_status = result["budget_status"]

    if not result.get("enabled", True):
        return True, "BUDGET_GUARD_DISABLED"

    # Planner / CTO：永遠不允許外部 AI
    if role in ("planner", "cto"):
        role_data = result["roles"].get(role, {})
        if role_data.get("status") in ("CRITICAL", "HARD_CAP"):
            return False, f"USAGE_BUDGET_HARD_CAP: {role} external AI not allowed"
        # 即使無歷史呼叫，planner/cto 的外部 AI 呼叫仍應由 ProviderFactory 管制
        return False, f"USAGE_BUDGET_ROLE_DENIED: {role} external AI policy forbidden"

    # Worker：HARD_CAP 時封鎖
    if budget_status == "HARD_CAP":
        return False, "USAGE_BUDGET_HARD_CAP: Worker external AI paused"

    # Provider 層級：若該 provider 達 HARD_CAP
    norm_prov = _normalize_provider(provider)
    prov_result = (
        result["providers"].get(provider)
        or result["providers"].get(norm_prov)
        or {}
    )
    if prov_result.get("status") == "HARD_CAP":
        return False, f"USAGE_BUDGET_HARD_CAP: provider {provider} hard cap reached"

    return True, "OK"


def get_budget_summary(hours: float = 24) -> dict:
    """
    取得適合前端 / Decision Card 顯示的精簡摘要。
    （evaluate_usage_budget 的別名，未來可在此加入快取）
    """
    return evaluate_usage_budget(hours=hours)
