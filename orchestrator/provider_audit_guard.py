"""
orchestrator/provider_audit_guard.py

Provider Audit Guard — fail-closed 外部 LLM 呼叫守衛。

核心規則：
    無 ATTEMPT 寫入成功 → 不得執行外部 LLM 呼叫。
    ATTEMPT 寫入失敗 → 回傳 BLOCKED_AUDIT_LOG_UNAVAILABLE，fail-closed。

用法：
    from orchestrator.provider_audit_guard import AuditGuard

    guard = AuditGuard(
        runner="worker_tick",
        provider="claude",
        task_id=42,
        trigger_source="worker_execute",
    )
    with guard:
        # 此區塊內執行外部 LLM 呼叫
        result = run_claude(...)
    # guard 自動寫入 RESULT（成功或失敗）

    # 若 guard 初始化失敗（ATTEMPT 寫入失敗），會 raise AuditGuardBlockedError
"""
from __future__ import annotations

import time
from typing import Optional

from orchestrator.llm_audit import (
    write_attempt,
    write_result,
    write_blocked,
    _is_external,
    _normalize_provider,
)


class AuditGuardBlockedError(RuntimeError):
    """
    外部 LLM 呼叫被稽核守衛阻止。
    原因：ATTEMPT 寫入失敗（BLOCKED_AUDIT_LOG_UNAVAILABLE）
    或政策封鎖（block_reason 說明）。
    """
    def __init__(self, block_reason: str, correlation_id: Optional[str] = None):
        super().__init__(f"AuditGuard blocked: {block_reason}")
        self.block_reason = block_reason
        self.correlation_id = correlation_id


class AuditGuard:
    """
    Context manager：包裝外部 LLM 呼叫，確保 ATTEMPT → RESULT 稽核生命週期。

    使用方式：
        guard = AuditGuard(runner="worker_tick", provider="claude", task_id=42)
        with guard:
            output = subprocess.check_output([...])
        guard.finalize(success=True, input_tokens=123, output_tokens=456)

    或使用 context manager 自動 finalize（需在 __exit__ 前呼叫 set_result）：
        with AuditGuard(...) as guard:
            result = run_llm()
            guard.set_result(success=True, output=result)
    """

    def __init__(
        self,
        *,
        runner: str,
        provider: str,
        usage_role: Optional[str] = None,
        task_id: Optional[int] = None,
        run_id: Optional[str] = None,
        model: Optional[str] = None,
        command: Optional[str] = None,
        trigger_source: str = "unknown",
        policy_allowed: bool = True,
        caller_skip_frames: int = 5,
    ):
        self.runner = runner
        self.provider = _normalize_provider(provider)
        self.usage_role = usage_role
        self.task_id = task_id
        self.run_id = run_id
        self.model = model
        self.command = command
        self.trigger_source = trigger_source
        self._start_time: Optional[float] = None
        self._correlation_id: Optional[str] = None
        self._result_set = False
        self._success: Optional[bool] = None
        self._error: Optional[str] = None
        self._input_tokens: int = 0
        self._output_tokens: int = 0
        self._cached_tokens: int = 0
        self._premium_requests: int = 0
        self._rate_limit_type: Optional[str] = None
        self._rate_limit_used_pct: Optional[float] = None
        self._rate_limit_reset_raw: Optional[str] = None
        self._raw_usage_excerpt: Optional[str] = None
        self._is_local = not _is_external(self.provider)

        # 非外部 provider 跳過稽核
        if self._is_local:
            self._correlation_id = "local-no-audit"
            return

        # 寫入 ATTEMPT — 若失敗則 fail-closed
        cid = write_attempt(
            runner=runner,
            provider=provider,
            usage_role=usage_role,
            task_id=task_id,
            run_id=run_id,
            model=model,
            command=command,
            trigger_source=trigger_source,
            policy_allowed=policy_allowed,
            caller_skip_frames=caller_skip_frames,
        )
        if cid is None:
            # ATTEMPT 寫入失敗 → fail-closed
            write_blocked(
                runner=runner,
                provider=provider,
                block_reason="BLOCKED_AUDIT_LOG_UNAVAILABLE",
                usage_role=usage_role,
                task_id=task_id,
                run_id=run_id,
                model=model,
                trigger_source=trigger_source,
                caller_skip_frames=caller_skip_frames,
            )
            raise AuditGuardBlockedError("BLOCKED_AUDIT_LOG_UNAVAILABLE")

        self._correlation_id = cid
        self._start_time = time.monotonic()

    def __enter__(self) -> "AuditGuard":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        if self._is_local:
            return False
        if not self._result_set:
            # context manager 退出時若未呼叫 set_result，自動判斷
            if exc_type is not None:
                self.set_result(success=False, error=str(exc_val))
            else:
                self.set_result(success=True)
        self._flush_result()
        return False  # 不吞例外

    def set_result(
        self,
        *,
        success: bool,
        error: Optional[str] = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cached_tokens: int = 0,
        premium_requests: int = 0,
        rate_limit_type: Optional[str] = None,
        rate_limit_used_pct: Optional[float] = None,
        rate_limit_reset_raw: Optional[str] = None,
        raw_usage_excerpt: Optional[str] = None,
    ) -> None:
        """設定執行結果（在 __exit__ 前呼叫）。"""
        self._result_set = True
        self._success = success
        self._error = error
        self._input_tokens = input_tokens
        self._output_tokens = output_tokens
        self._cached_tokens = cached_tokens
        self._premium_requests = premium_requests
        self._rate_limit_type = rate_limit_type
        self._rate_limit_used_pct = rate_limit_used_pct
        self._rate_limit_reset_raw = rate_limit_reset_raw
        self._raw_usage_excerpt = raw_usage_excerpt

    def _flush_result(self) -> None:
        """寫入 RESULT 事件。"""
        if self._is_local or self._correlation_id is None:
            return
        duration_ms: Optional[float] = None
        if self._start_time is not None:
            duration_ms = (time.monotonic() - self._start_time) * 1000

        write_result(
            correlation_id=self._correlation_id,
            runner=self.runner,
            provider=self.provider,
            success=bool(self._success),
            usage_role=self.usage_role,
            task_id=self.task_id,
            run_id=self.run_id,
            model=self.model,
            error=self._error,
            duration_ms=duration_ms,
            input_tokens=self._input_tokens,
            output_tokens=self._output_tokens,
            cached_tokens=self._cached_tokens,
            premium_requests=self._premium_requests,
            rate_limit_type=self._rate_limit_type,
            rate_limit_used_pct=self._rate_limit_used_pct,
            rate_limit_reset_raw=self._rate_limit_reset_raw,
            raw_usage_excerpt=self._raw_usage_excerpt,
            trigger_source=self.trigger_source,
        )

    @property
    def correlation_id(self) -> Optional[str]:
        return self._correlation_id


def guard_external_call(
    *,
    runner: str,
    provider: str,
    usage_role: Optional[str] = None,
    task_id: Optional[int] = None,
    run_id: Optional[str] = None,
    model: Optional[str] = None,
    command: Optional[str] = None,
    trigger_source: str = "unknown",
    policy_allowed: bool = True,
) -> "AuditGuard":
    """
    建立並回傳 AuditGuard context manager 的捷徑函式。

    用法：
        with guard_external_call(runner="worker_tick", provider="claude", task_id=42) as g:
            output = run_process(...)
            g.set_result(success=True, input_tokens=100, output_tokens=50)
    """
    return AuditGuard(
        runner=runner,
        provider=provider,
        usage_role=usage_role,
        task_id=task_id,
        run_id=run_id,
        model=model,
        command=command,
        trigger_source=trigger_source,
        policy_allowed=policy_allowed,
        caller_skip_frames=6,
    )
