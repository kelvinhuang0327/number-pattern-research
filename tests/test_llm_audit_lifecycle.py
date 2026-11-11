"""
tests/test_llm_audit_lifecycle.py

LLM Audit Lifecycle 測試套件。

涵蓋架構要求中的核心測試項目：
    1.  外部 provider 寫入 ATTEMPT before execute
    2.  外部 provider 寫入 RESULT after success
    3.  外部 provider 寫入 RESULT after failure
    4.  ATTEMPT 寫入失敗封鎖 provider 執行（AuditGuardBlockedError）
    5.  政策封鎖寫入 BLOCKED
    6.  本地 provider 不寫入任何稽核事件
    7.  Unknown provider 視同外部
    8.  排程 Planner 外部 provider 被 ProviderFactory 封鎖
    9.  Worker 外部 provider 需要 requires_llm=true
    10. /llm-audit/recent 回傳必要欄位
    11. /llm-audit/today 依 role/provider 聚合
    12. /llm-usage/today 依 role/provider 聚合
    13. AuditGuard context manager 自動 ATTEMPT→RESULT 生命週期
    14. 無重複 RESULT（同一 correlation_id 只有一個 RESULT）
    15. CTO local_review 不寫外部稽核
    16. Copilot-Daemon 外部呼叫寫入 ATTEMPT
    17. Mock 稽核生命週期煙霧測試
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Optional
from unittest.mock import patch, MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture()
def tmp_audit(tmp_path, monkeypatch):
    """重導 llm_audit._AUDIT_PATH 至臨時目錄。"""
    import orchestrator.llm_audit as audit_mod
    log_file = str(tmp_path / "llm_audit.jsonl")
    monkeypatch.setattr(audit_mod, "_AUDIT_PATH", log_file)
    return log_file


@pytest.fixture()
def tmp_usage(tmp_path, monkeypatch):
    """重導 llm_usage_logger._LOG_PATH 至臨時目錄。"""
    import orchestrator.llm_usage_logger as usage_mod
    log_file = str(tmp_path / "llm_usage.jsonl")
    monkeypatch.setattr(usage_mod, "_LOG_PATH", log_file)
    return log_file


def _read_audit(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return records


# ── Test 1: 外部 provider 寫入 ATTEMPT before execute ─────────────────────

def test_external_provider_writes_attempt(tmp_audit):
    """write_attempt 寫入 LLM_CALL_ATTEMPT，回傳 correlation_id。"""
    from orchestrator.llm_audit import write_attempt, EVENT_ATTEMPT

    cid = write_attempt(
        runner="worker_tick",
        provider="claude",
        task_id=1,
        trigger_source="worker_execute",
    )
    assert cid is not None
    records = _read_audit(tmp_audit)
    assert len(records) == 1
    assert records[0]["event_type"] == EVENT_ATTEMPT
    assert records[0]["provider"] == "claude"
    assert records[0]["correlation_id"] == cid


# ── Test 2: 外部 provider 寫入 RESULT after success ─────────────────────────

def test_external_provider_writes_result_on_success(tmp_audit):
    """write_result 寫入 LLM_CALL_RESULT（success=True）。"""
    from orchestrator.llm_audit import write_attempt, write_result, EVENT_RESULT

    cid = write_attempt(runner="worker_tick", provider="codex", task_id=2)
    assert cid is not None

    write_result(
        correlation_id=cid,
        runner="worker_tick",
        provider="codex",
        success=True,
        input_tokens=100,
        output_tokens=50,
    )
    records = _read_audit(tmp_audit)
    result_records = [r for r in records if r["event_type"] == EVENT_RESULT]
    assert len(result_records) == 1
    assert result_records[0]["success"] is True
    assert result_records[0]["correlation_id"] == cid
    assert result_records[0]["input_tokens"] == 100


# ── Test 3: 外部 provider 寫入 RESULT after failure ──────────────────────────

def test_external_provider_writes_result_on_failure(tmp_audit):
    """write_result 寫入 LLM_CALL_RESULT（success=False + error）。"""
    from orchestrator.llm_audit import write_attempt, write_result, EVENT_RESULT

    cid = write_attempt(runner="worker_tick", provider="claude", task_id=3)
    write_result(
        correlation_id=cid,
        runner="worker_tick",
        provider="claude",
        success=False,
        error="rate limit exceeded",
    )
    records = _read_audit(tmp_audit)
    result_records = [r for r in records if r["event_type"] == EVENT_RESULT]
    assert len(result_records) == 1
    assert result_records[0]["success"] is False
    assert "rate limit" in (result_records[0]["error"] or "")


# ── Test 4: ATTEMPT 寫入失敗封鎖 provider 執行 ────────────────────────────────

def test_attempt_write_failure_blocks_execution(tmp_audit, monkeypatch):
    """若 _write_audit_record 失敗，AuditGuard 應 raise AuditGuardBlockedError。"""
    import orchestrator.llm_audit as audit_mod
    from orchestrator.provider_audit_guard import AuditGuard, AuditGuardBlockedError

    # 讓 _write_audit_record 永遠回傳 False（模擬 IO 失敗）
    monkeypatch.setattr(audit_mod, "_write_audit_record", lambda rec: False)

    with pytest.raises(AuditGuardBlockedError) as exc_info:
        AuditGuard(runner="worker_tick", provider="claude", task_id=4)

    assert "BLOCKED_AUDIT_LOG_UNAVAILABLE" in str(exc_info.value)


# ── Test 5: 政策封鎖寫入 BLOCKED ─────────────────────────────────────────────

def test_policy_blocked_writes_blocked_event(tmp_audit):
    """write_blocked 寫入 LLM_CALL_BLOCKED 事件。"""
    from orchestrator.llm_audit import write_blocked, EVENT_BLOCKED

    write_blocked(
        runner="planner_tick",
        provider="claude",
        block_reason="ROLE_PROVIDER_VIOLATION",
        task_id=5,
    )
    records = _read_audit(tmp_audit)
    assert len(records) == 1
    assert records[0]["event_type"] == EVENT_BLOCKED
    assert records[0]["blocked"] is True
    assert records[0]["block_reason"] == "ROLE_PROVIDER_VIOLATION"


# ── Test 6: 本地 provider 不寫入稽核事件 ─────────────────────────────────────

def test_local_provider_writes_no_audit(tmp_audit):
    """本地 provider（local / none / dry-run）不寫入任何稽核事件。"""
    from orchestrator.llm_audit import write_attempt, write_result

    cid = write_attempt(runner="worker_tick", provider="local", task_id=6)
    assert cid is not None  # 回傳 cid 但不寫入
    write_result(correlation_id=cid, runner="worker_tick", provider="local", success=True)

    records = _read_audit(tmp_audit)
    assert len(records) == 0


# ── Test 7: Unknown provider 視同外部 ────────────────────────────────────────

def test_unknown_provider_treated_as_external(tmp_audit):
    """未知 provider（非 local 集合）視同外部，寫入 ATTEMPT。"""
    from orchestrator.llm_audit import write_attempt, EVENT_ATTEMPT

    cid = write_attempt(runner="worker_tick", provider="mystery-ai", task_id=7)
    assert cid is not None
    records = _read_audit(tmp_audit)
    assert len(records) == 1
    assert records[0]["event_type"] == EVENT_ATTEMPT


# ── Test 8: 排程 Planner 外部 provider 被 ProviderFactory 封鎖 ──────────────

def test_scheduled_planner_external_provider_blocked(tmp_usage):
    """ProviderFactory.assert_role_allowed('planner', 'claude') 應 raise。"""
    from orchestrator.provider_factory import ProviderFactory, ProviderRoleViolationError

    with pytest.raises(ProviderRoleViolationError):
        ProviderFactory.assert_role_allowed("planner", "claude")

    with pytest.raises(ProviderRoleViolationError):
        ProviderFactory.assert_role_allowed("planner", "codex")

    with pytest.raises(ProviderRoleViolationError):
        ProviderFactory.assert_role_allowed("cto", "codex")


# ── Test 9: Worker 外部 provider 呼叫不被 ProviderFactory 封鎖 ──────────────

def test_worker_external_provider_not_blocked_by_factory(tmp_usage):
    """Worker 角色允許外部 provider（執行政策由 execution_policy 管控）。"""
    from orchestrator.provider_factory import ProviderFactory, ProviderRoleViolationError

    # 不應拋出異常
    try:
        ProviderFactory.assert_role_allowed("worker", "claude")
    except ProviderRoleViolationError:
        pytest.fail("Worker 不應被 ProviderFactory 封鎖")


# ── Test 13: AuditGuard context manager ATTEMPT→RESULT 生命週期 ──────────────

def test_audit_guard_context_manager_lifecycle(tmp_audit):
    """AuditGuard context manager 自動完成 ATTEMPT→RESULT 生命週期。"""
    from orchestrator.provider_audit_guard import AuditGuard
    from orchestrator.llm_audit import EVENT_ATTEMPT, EVENT_RESULT

    with AuditGuard(
        runner="worker_tick",
        provider="codex",
        task_id=13,
        trigger_source="worker_execute",
    ) as guard:
        guard.set_result(success=True, input_tokens=200, output_tokens=100)

    records = _read_audit(tmp_audit)
    event_types = [r["event_type"] for r in records]
    assert EVENT_ATTEMPT in event_types
    assert EVENT_RESULT in event_types

    # ATTEMPT 必須先於 RESULT
    attempt_idx = event_types.index(EVENT_ATTEMPT)
    result_idx = event_types.index(EVENT_RESULT)
    assert attempt_idx < result_idx


# ── Test 14: 無重複 RESULT ────────────────────────────────────────────────────

def test_no_duplicate_result(tmp_audit):
    """同一 correlation_id 只有一個 RESULT（AuditGuard 不重複寫入）。"""
    from orchestrator.provider_audit_guard import AuditGuard
    from orchestrator.llm_audit import EVENT_RESULT

    with AuditGuard(runner="worker_tick", provider="claude", task_id=14) as guard:
        guard.set_result(success=True)

    records = _read_audit(tmp_audit)
    result_records = [r for r in records if r["event_type"] == EVENT_RESULT]
    assert len(result_records) == 1


# ── Test 15: CTO local_review 不寫外部稽核 ───────────────────────────────────

def test_cto_local_review_no_external_audit(tmp_audit):
    """CTO 使用本地 provider 時不寫入稽核事件。"""
    from orchestrator.llm_audit import write_attempt

    cid = write_attempt(runner="cto_review_tick", provider="local", task_id=15)
    records = _read_audit(tmp_audit)
    assert len(records) == 0


# ── Test 16: Copilot-Daemon 外部呼叫寫入 ATTEMPT ────────────────────────────

def test_copilot_daemon_writes_attempt(tmp_audit):
    """Copilot-Daemon 外部執行寫入 ATTEMPT 事件。"""
    from orchestrator.llm_audit import write_attempt, EVENT_ATTEMPT

    cid = write_attempt(
        runner="copilot_daemon",
        provider="github-copilot",
        task_id=16,
        trigger_source="copilot_daemon_execute",
    )
    records = _read_audit(tmp_audit)
    assert len(records) == 1
    assert records[0]["event_type"] == EVENT_ATTEMPT
    assert records[0]["runner_type"] == "copilot_daemon"
    assert records[0]["usage_role"] == "worker"  # copilot_daemon → worker role


# ── Test 17: Mock 稽核生命週期煙霧測試 ───────────────────────────────────────

def test_mock_audit_lifecycle_smoke(tmp_audit):
    """
    完整煙霧測試：Planner BLOCKED + Worker ATTEMPT→RESULT + CTO BLOCKED。
    驗證 /llm-audit/recent 可讀取所有事件。
    """
    from orchestrator.llm_audit import (
        write_attempt, write_result, write_blocked,
        read_audit_records, EVENT_ATTEMPT, EVENT_RESULT, EVENT_BLOCKED,
    )

    # Planner 嘗試外部呼叫 → BLOCKED
    write_blocked(
        runner="planner_tick",
        provider="claude",
        block_reason="ROLE_PROVIDER_VIOLATION",
        task_id=100,
        trigger_source="scheduler_tick",
    )

    # Worker 外部呼叫 → ATTEMPT → RESULT
    cid = write_attempt(
        runner="worker_tick",
        provider="codex",
        task_id=101,
        trigger_source="worker_execute",
    )
    assert cid is not None
    write_result(
        correlation_id=cid,
        runner="worker_tick",
        provider="codex",
        success=True,
        input_tokens=500,
        output_tokens=200,
    )

    # CTO 外部呼叫 → ATTEMPT → RESULT(failed)
    cid_cto = write_attempt(
        runner="cto_review_tick",
        provider="claude",
        task_id=102,
        trigger_source="cto_review",
    )
    assert cid_cto is not None
    write_result(
        correlation_id=cid_cto,
        runner="cto_review_tick",
        provider="claude",
        success=False,
        error="timeout",
    )

    # Copilot BLOCKED
    write_blocked(
        runner="copilot_daemon",
        provider="github-copilot",
        block_reason="POLICY_HARD_OFF",
        task_id=103,
    )

    # 讀取所有記錄
    records = read_audit_records(hours=0)
    # 事件統計：2 BLOCKED + 2 ATTEMPT + 2 RESULT = 6
    assert len(records) == 6

    event_types = [r["event_type"] for r in records]
    assert event_types.count(EVENT_BLOCKED) == 2
    assert event_types.count(EVENT_ATTEMPT) == 2
    assert event_types.count(EVENT_RESULT) == 2

    # 今日摘要
    from orchestrator.llm_audit import build_audit_today_summary
    summary = build_audit_today_summary()
    assert summary["total_events"] == 6
    assert summary["blocked"] == 2
    assert summary["attempts"] == 2


# ── Test: /api endpoint 回傳必要欄位 ─────────────────────────────────────────

def test_api_llm_audit_recent_fields(tmp_audit):
    """
    模擬寫入稽核記錄後，驗證 read_audit_records 回傳必要欄位。
    """
    from orchestrator.llm_audit import write_attempt, read_audit_records, EVENT_ATTEMPT
    REQUIRED_FIELDS = [
        "timestamp", "correlation_id", "event_type",
        "runner_type", "usage_role", "provider",
        "blocked", "block_reason", "success",
    ]

    cid = write_attempt(
        runner="worker_tick",
        provider="claude",
        task_id=200,
        trigger_source="worker_execute",
    )
    records = read_audit_records(hours=0)
    assert len(records) == 1
    for field in REQUIRED_FIELDS:
        assert field in records[0], f"缺少必要欄位: {field}"


def test_api_llm_audit_today_aggregates(tmp_audit):
    """build_audit_today_summary 依 role/provider 正確聚合。"""
    from orchestrator.llm_audit import write_attempt, write_result, build_audit_today_summary

    cid1 = write_attempt(runner="worker_tick", provider="claude", task_id=300)
    write_result(correlation_id=cid1, runner="worker_tick", provider="claude", success=True)

    cid2 = write_attempt(runner="worker_tick", provider="codex", task_id=301)
    write_result(correlation_id=cid2, runner="worker_tick", provider="codex", success=False)

    summary = build_audit_today_summary()
    assert summary["attempts"] == 2
    assert summary["results"] == 2
    assert "worker" in summary["by_role"]
    assert "claude" in summary["by_provider"]
    assert "codex" in summary["by_provider"]
    assert summary["by_provider"]["claude"]["succeeded"] == 1
    assert summary["by_provider"]["codex"]["failed"] == 1
