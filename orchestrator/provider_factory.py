"""
orchestrator/provider_factory.py

Phase 0 — 角色導向 Provider 工廠與存取控制守衛。

設計原則：
- Planner 角色絕對不可使用任何外部 LLM（ROLE_PROVIDER_VIOLATION 硬性封鎖）
- CTO 角色預設本地執行，不允許外部 LLM
- Worker 角色可使用外部 LLM（受 execution_policy 管控）
- 所有存取嘗試（允許或封鎖）均記錄至 llm_usage.jsonl

用法：
    # 在 worker_tick.py 派發任何外部 LLM 呼叫前：
    ProviderFactory.assert_role_allowed("worker", "codex", task_id=123)

    # 若 Planner 意外嘗試呼叫外部 LLM：
    ProviderFactory.assert_role_allowed("planner", "claude")
    # → 立即 raise ProviderRoleViolationError
"""
from __future__ import annotations

import logging
from typing import Optional

from orchestrator.llm_usage_logger import log_llm_event

logger = logging.getLogger(__name__)

# ── 外部 AI / GitHub Provider 集合 ──────────────────────────────────────────
# 覆蓋所有需要配額、速率限制或外部 API 的工具。
EXTERNAL_PROVIDERS: frozenset[str] = frozenset({
    # OpenAI / Codex
    "codex",
    "codex-cli",
    "openai",
    # Anthropic / Claude
    "claude",
    "claude-cli",
    "claude-code",
    "anthropic",
    # GitHub
    "copilot",
    "copilot-daemon",
    "github-copilot",
    "github-cli",
    "github-api",
    "git-remote",
    # Google Gemini
    "gemini",
    "gemini-cli",
})

LOCAL_PROVIDERS: frozenset[str] = frozenset({
    "local",
    "none",
    "dry-run",
    "",
})

# ── 角色封鎖規則 ────────────────────────────────────────────────────────────
# 值為 frozenset of blocked providers；若集合為空代表無強制封鎖。
ROLE_BLOCKED_PROVIDERS: dict[str, frozenset[str]] = {
    # Planner 必須永遠本地執行，不得呼叫任何外部 LLM
    "planner":        EXTERNAL_PROVIDERS,
    # CTO 審核邏輯為本地確定性，不允許外部 LLM
    "cto":            EXTERNAL_PROVIDERS,
    # Worker 可以使用外部 LLM（受 execution_policy 進一步管控）
    "worker":         frozenset(),
    # copilot_daemon 是 worker 的子執行緒，允許外部呼叫
    "copilot_daemon": frozenset(),
    # 未知呼叫者：不強制封鎖，但會記錄警告
    "unknown":        frozenset(),
}


class ProviderRoleViolationError(RuntimeError):
    """
    某個角色嘗試使用被明確禁止的 Provider。
    由 ProviderFactory.assert_role_allowed() 拋出。
    """
    pass


class ProviderFactory:
    """
    角色導向 Provider 存取守衛。

    在任何外部 LLM subprocess 啟動前呼叫 assert_role_allowed()。
    此方法會：
    1. 檢查 role 是否被允許使用該 provider
    2. 寫入 JSONL 使用量記錄（無論允許或封鎖）
    3. 若違規則 raise ProviderRoleViolationError
    """

    @staticmethod
    def is_external(provider_name: str) -> bool:
        """回傳 True 若 provider 屬於外部 LLM。"""
        return str(provider_name or "").strip().lower() in EXTERNAL_PROVIDERS

    @staticmethod
    def is_local(provider_name: str) -> bool:
        """回傳 True 若 provider 屬於本地執行。"""
        return str(provider_name or "").strip().lower() in LOCAL_PROVIDERS

    @staticmethod
    def assert_role_allowed(
        role: str,
        provider_name: str,
        *,
        task_id: Optional[int] = None,
        correlation_id: Optional[str] = None,
    ) -> None:
        """
        確保 role 被允許使用 provider_name。
        違規時 raise ProviderRoleViolationError 並記錄 JSONL。

        Args:
            role:           呼叫者角色，例如 "planner", "worker", "cto"
            provider_name:  嘗試使用的 provider，例如 "codex", "claude"
            task_id:        關聯任務 ID（可選）
            correlation_id: 跨系統追蹤 ID（可選）

        Raises:
            ProviderRoleViolationError: 若 role 不允許使用 provider_name
        """
        normalized_role = str(role or "unknown").strip().lower()
        normalized_provider = str(provider_name or "").strip().lower()

        blocked_set = ROLE_BLOCKED_PROVIDERS.get(normalized_role, frozenset())
        is_blocked = normalized_provider in blocked_set

        log_llm_event(
            runner=normalized_role,
            provider=normalized_provider,
            blocked=is_blocked,
            block_reason="ROLE_PROVIDER_VIOLATION" if is_blocked else None,
            task_id=task_id,
            correlation_id=correlation_id,
            entrypoint="ProviderFactory.assert_role_allowed",
            requires_llm=True,
            allowed_by_policy=not is_blocked,
            caller_skip_frames=4,
        )

        if is_blocked:
            msg = (
                f"ProviderFactory: role={role!r} 不被允許使用 provider={provider_name!r}。"
                f" 這是 ROLE_PROVIDER_VIOLATION — 請檢查呼叫端是否誤用了外部 LLM Provider。"
            )
            logger.error("[ProviderFactory] %s", msg)
            raise ProviderRoleViolationError(msg)

        if normalized_role == "unknown":
            logger.warning(
                "[ProviderFactory] role='unknown' 正在存取 provider=%r — 建議明確指定角色。",
                provider_name,
            )
        else:
            logger.debug(
                "[ProviderFactory] role=%r provider=%r — 角色許可通過。",
                role,
                provider_name,
            )
