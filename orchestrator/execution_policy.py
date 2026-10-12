from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Optional

from orchestrator import db
from orchestrator.common import HARD_OFF_MODE, SAFE_RUN_MODE, build_runtime_guard_message

POLICY_ALLOWED = "allowed"
POLICY_BLOCKED = "blocked"

_TRUE_VALUES = {"1", "true", "yes", "on"}
_LLM_BLOCKED_COUNT_KEY = "llm_blocked_count"
_LAST_LLM_CALL_AT_KEY = "llm_last_call_at"
_LAST_LLM_CALL_RUNNER_KEY = "llm_last_call_runner"
_LAST_LLM_CALL_PROVIDER_KEY = "llm_last_call_provider"
_LAST_LLM_CALL_CONTEXT_KEY = "llm_last_call_context"
_LAST_LLM_BLOCKED_AT_KEY = "llm_last_blocked_at"
_LAST_LLM_BLOCKED_REASON_KEY = "llm_last_blocked_reason"
_LAST_LLM_BLOCKED_RUNNER_KEY = "llm_last_blocked_runner"
_LAST_LLM_BLOCKED_PROVIDER_KEY = "llm_last_blocked_provider"
_ACTIVE_BACKGROUND_RUNNER_KEY = "llm_active_background_runner"

# ── Phase 0: 角色對應 DB 設定 key ─────────────────────────────────────────
_ROLE_EXT_LLM_KEY: dict[str, str] = {
    "planner":        "ext_llm_role_planner",
    "worker":         "ext_llm_role_worker",
    "cto":            "ext_llm_role_cto",
    "copilot_daemon": "ext_llm_role_worker",  # daemon 視同 worker
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _as_bool(value: Any) -> bool:
    return str(value or "").strip().lower() in _TRUE_VALUES


def _get_int_setting(key: str, default: int = 0) -> int:
    raw = db.get_setting(key, str(default)).strip()
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def is_manual_run(env: Optional[Mapping[str, str]] = None) -> bool:
    payload = env or {}
    return _as_bool(payload.get("ORCHESTRATOR_FORCE_RUN")) or _as_bool(payload.get("ORCHESTRATOR_MANUAL_RUN"))


def get_state() -> dict[str, Any]:
    mode = db.get_llm_execution_mode()
    return {
        "scheduler_enabled": db.get_scheduler_enabled(),
        "cto_scheduler_enabled": db.get_cto_scheduler_enabled(),
        "llm_execution_mode": mode,
        "hard_off": mode == HARD_OFF_MODE,
        "llm_blocked_count": _get_int_setting(_LLM_BLOCKED_COUNT_KEY, 0),
        "last_llm_call_at": db.get_setting(_LAST_LLM_CALL_AT_KEY, "") or None,
        "last_llm_call_runner": db.get_setting(_LAST_LLM_CALL_RUNNER_KEY, "") or None,
        "last_llm_call_provider": db.get_setting(_LAST_LLM_CALL_PROVIDER_KEY, "") or None,
        "last_llm_call_context": db.get_setting(_LAST_LLM_CALL_CONTEXT_KEY, "") or None,
        "last_llm_blocked_at": db.get_setting(_LAST_LLM_BLOCKED_AT_KEY, "") or None,
        "last_llm_blocked_reason": db.get_setting(_LAST_LLM_BLOCKED_REASON_KEY, "") or None,
        "last_llm_blocked_runner": db.get_setting(_LAST_LLM_BLOCKED_RUNNER_KEY, "") or None,
        "last_llm_blocked_provider": db.get_setting(_LAST_LLM_BLOCKED_PROVIDER_KEY, "") or None,
        "active_background_runner": db.get_setting(_ACTIVE_BACKGROUND_RUNNER_KEY, "") or None,
    }


def set_llm_execution_mode(mode: str) -> dict[str, Any]:
    db.set_llm_execution_mode(mode)
    return get_state()


def set_scheduler_enabled(enabled: bool) -> dict[str, Any]:
    db.set_scheduler_enabled(enabled)
    return get_state()


def set_cto_scheduler_enabled(enabled: bool) -> dict[str, Any]:
    db.set_cto_scheduler_enabled(enabled)
    return get_state()


def set_active_background_runner(runner: str, active: bool) -> None:
    db.set_setting(_ACTIVE_BACKGROUND_RUNNER_KEY, runner if active else "")


def _check_role_provider_policy(
    runner: str,
    provider: Optional[str],
) -> Optional[str]:
    """
    Phase 0: 角色導向 provider 政策檢查。
    回傳封鎖原因字串，若允許則回傳 None。

    此函式僅在 requires_llm=True 且需要外部 LLM 時有意義。
    provider=None 時略過角色層級檢查。
    """
    if not provider:
        return None

    normalized_role = str(runner or "").strip().lower()
    role_key = _ROLE_EXT_LLM_KEY.get(normalized_role)

    if role_key is not None:
        # 角色層級開關（0=封鎖）
        role_enabled = db.get_setting(role_key, "0") == "1"
        if not role_enabled:
            return f"role-ext-llm-disabled:{normalized_role}"

    # Provider × 角色細粒度開關
    norm_provider = str(provider).lower().replace("-", "_")
    norm_role = normalized_role.replace("-", "_")
    provider_key = f"{norm_provider}_enabled_for_{norm_role}"
    # 若設定不存在，對已知外部 provider 預設封鎖
    from orchestrator.provider_factory import EXTERNAL_PROVIDERS
    raw_val = db.get_setting(provider_key, None)
    if raw_val is None:
        # key 不在 DB 中：若為外部 provider 且 role 是 planner/cto → 封鎖
        if str(provider).lower() in EXTERNAL_PROVIDERS and normalized_role in ("planner", "cto"):
            return f"provider-role-not-configured:{provider}:{normalized_role}"
    elif raw_val != "1":
        return f"provider-disabled-for-role:{provider}:{normalized_role}"

    return None


def evaluate_execution(
    *,
    runner: str,
    requires_llm: bool = False,
    background: bool = True,
    manual_override: bool = False,
    scheduler_scope: str = "global",
    provider: Optional[str] = None,
) -> dict[str, Any]:
    """
    評估是否允許執行（含 Phase 0 角色導向 Provider 政策）。

    Args:
        runner:           執行者名稱（"planner_tick", "worker_tick", 等）
        requires_llm:     此次執行是否需要外部 LLM 呼叫
        background:       是否為排程背景執行
        manual_override:  是否為人工強制執行
        scheduler_scope:  排程範圍（"global" 或 "cto"）
        provider:         欲使用的 provider（requires_llm=True 時才有意義）
    """
    state = get_state()
    reason: Optional[str] = None

    # ── 全域 Hard-Off 開關 ───────────────────────────────────────────────
    if state["hard_off"]:
        reason = HARD_OFF_MODE
    # ── 排程停用 ────────────────────────────────────────────────────────
    elif background and not manual_override and not state["scheduler_enabled"]:
        reason = "scheduler-disabled"
    elif (
        scheduler_scope == "cto"
        and background
        and not manual_override
        and not state["cto_scheduler_enabled"]
    ):
        reason = "cto-scheduler-disabled"
    # ── Phase 0: 角色導向 Provider 政策（僅在 requires_llm=True 時檢查）──
    elif requires_llm and provider:
        reason = _check_role_provider_policy(runner, provider)

    allowed = reason is None
    return {
        "status": POLICY_ALLOWED if allowed else POLICY_BLOCKED,
        "allowed": allowed,
        "reason": reason,
        "message": None if allowed else build_runtime_guard_message(reason, runner),
        "runner": runner,
        "requires_llm": requires_llm,
        "background": background,
        "manual_override": manual_override,
        "scheduler_scope": scheduler_scope,
        "provider": provider,
        "state": state,
    }


def record_llm_call(
    *,
    runner: str,
    provider: str,
    context: str,
    task_id: Optional[int] = None,
    correlation_id: Optional[str] = None,
) -> None:
    now = _utc_now_iso()
    db.set_setting(_LAST_LLM_CALL_AT_KEY, now)
    db.set_setting(_LAST_LLM_CALL_RUNNER_KEY, runner)
    db.set_setting(_LAST_LLM_CALL_PROVIDER_KEY, provider)
    db.set_setting(_LAST_LLM_CALL_CONTEXT_KEY, context)
    # Phase 0: JSONL 使用量記錄
    try:
        from orchestrator.llm_usage_logger import log_llm_event
        log_llm_event(
            runner=runner,
            provider=provider,
            blocked=False,
            task_id=task_id,
            correlation_id=correlation_id,
            entrypoint=context,
            requires_llm=True,
            allowed_by_policy=True,
            caller_skip_frames=4,
        )
    except Exception:  # noqa: BLE001
        pass  # 記錄失敗不中斷執行


def record_llm_block(
    *,
    runner: str,
    provider: str,
    reason: str,
    task_id: Optional[int] = None,
    correlation_id: Optional[str] = None,
) -> None:
    now = _utc_now_iso()
    db.set_setting(_LAST_LLM_BLOCKED_AT_KEY, now)
    db.set_setting(_LAST_LLM_BLOCKED_REASON_KEY, reason)
    db.set_setting(_LAST_LLM_BLOCKED_RUNNER_KEY, runner)
    db.set_setting(_LAST_LLM_BLOCKED_PROVIDER_KEY, provider)
    db.set_setting(_LLM_BLOCKED_COUNT_KEY, str(_get_int_setting(_LLM_BLOCKED_COUNT_KEY, 0) + 1))
    # Phase 0: JSONL 使用量記錄
    try:
        from orchestrator.llm_usage_logger import log_llm_event
        log_llm_event(
            runner=runner,
            provider=provider,
            blocked=True,
            block_reason=reason,
            task_id=task_id,
            correlation_id=correlation_id,
            entrypoint="execution_policy.record_llm_block",
            requires_llm=True,
            allowed_by_policy=False,
            caller_skip_frames=4,
        )
    except Exception:  # noqa: BLE001
        pass  # 記錄失敗不中斷執行


def assert_llm_execution_allowed(
    *,
    runner: str,
    provider: str,
    context: str,
    background: bool,
    manual_override: bool = False,
    scheduler_scope: str = "global",
    task_id: Optional[int] = None,
    correlation_id: Optional[str] = None,
) -> None:
    decision = evaluate_execution(
        runner=runner,
        requires_llm=True,
        background=background,
        manual_override=manual_override,
        scheduler_scope=scheduler_scope,
        provider=provider,
    )
    if decision["allowed"]:
        record_llm_call(
            runner=runner,
            provider=provider,
            context=context,
            task_id=task_id,
            correlation_id=correlation_id,
        )
        return

    record_llm_block(
        runner=runner,
        provider=provider,
        reason=str(decision["reason"] or "blocked"),
        task_id=task_id,
        correlation_id=correlation_id,
    )
    raise RuntimeError(decision["message"])