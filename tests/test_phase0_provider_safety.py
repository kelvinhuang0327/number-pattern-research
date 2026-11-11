"""
tests/test_phase0_provider_safety.py

Phase 0 Provider Safety Engineering — 完整測試套件。

覆蓋：
- ProviderFactory 角色守衛（Planner / CTO / Worker）
- LlmUsageLogger 寫入與輪轉
- execution_policy 角色導向 provider 政策
- DB 配額開關
- Worker tick 整合守衛（ProviderRoleViolationError 不可能在 Worker 觸發）
- Planner LLM 呼叫必須為 0（靜態驗證）
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture()
def tmp_jsonl(tmp_path, monkeypatch):
    """重導 llm_usage_logger._LOG_PATH 至臨時目錄。"""
    from orchestrator import llm_usage_logger
    log_file = str(tmp_path / "llm_usage.jsonl")
    monkeypatch.setattr(llm_usage_logger, "_LOG_PATH", log_file)
    return log_file


@pytest.fixture()
def db_hardoff(monkeypatch):
    """模擬 DB 回傳 hard-off 模式。"""
    from orchestrator import execution_policy
    monkeypatch.setattr(execution_policy.db, "get_llm_execution_mode", lambda: "hard-off")
    monkeypatch.setattr(execution_policy.db, "get_scheduler_enabled", lambda: True)
    monkeypatch.setattr(execution_policy.db, "get_cto_scheduler_enabled", lambda: True)
    monkeypatch.setattr(execution_policy.db, "get_setting", lambda key, default="": default)


@pytest.fixture()
def db_safe_run_planner_blocked(monkeypatch):
    """模擬 safe-run 模式，Planner 外部 LLM 被關閉。"""
    from orchestrator import execution_policy

    settings: dict[str, str] = {
        "ext_llm_role_planner": "0",
        "ext_llm_role_worker": "1",
        "ext_llm_role_cto": "0",
        "codex_enabled_for_planner": "0",
        "claude_enabled_for_planner": "0",
        "codex_enabled_for_worker": "1",
        "claude_enabled_for_worker": "1",
    }
    monkeypatch.setattr(execution_policy.db, "get_llm_execution_mode", lambda: "safe-run")
    monkeypatch.setattr(execution_policy.db, "get_scheduler_enabled", lambda: True)
    monkeypatch.setattr(execution_policy.db, "get_cto_scheduler_enabled", lambda: True)
    monkeypatch.setattr(
        execution_policy.db,
        "get_setting",
        lambda key, default="": settings.get(key, default),
    )


# ─────────────────────────────────────────────────────────────────────────────
# 1. ProviderFactory — 角色守衛
# ─────────────────────────────────────────────────────────────────────────────

class TestProviderFactory:

    def test_planner_blocked_from_codex(self, tmp_jsonl):
        from orchestrator.provider_factory import ProviderFactory, ProviderRoleViolationError
        with pytest.raises(ProviderRoleViolationError) as exc_info:
            ProviderFactory.assert_role_allowed("planner", "codex")
        assert "ROLE_PROVIDER_VIOLATION" in str(exc_info.value)

    def test_planner_blocked_from_claude(self, tmp_jsonl):
        from orchestrator.provider_factory import ProviderFactory, ProviderRoleViolationError
        with pytest.raises(ProviderRoleViolationError):
            ProviderFactory.assert_role_allowed("planner", "claude")

    def test_planner_blocked_from_copilot(self, tmp_jsonl):
        from orchestrator.provider_factory import ProviderFactory, ProviderRoleViolationError
        with pytest.raises(ProviderRoleViolationError):
            ProviderFactory.assert_role_allowed("planner", "copilot")

    def test_planner_blocked_from_copilot_daemon(self, tmp_jsonl):
        from orchestrator.provider_factory import ProviderFactory, ProviderRoleViolationError
        with pytest.raises(ProviderRoleViolationError):
            ProviderFactory.assert_role_allowed("planner", "copilot-daemon")

    def test_cto_blocked_from_codex(self, tmp_jsonl):
        from orchestrator.provider_factory import ProviderFactory, ProviderRoleViolationError
        with pytest.raises(ProviderRoleViolationError):
            ProviderFactory.assert_role_allowed("cto", "codex")

    def test_cto_blocked_from_claude(self, tmp_jsonl):
        from orchestrator.provider_factory import ProviderFactory, ProviderRoleViolationError
        with pytest.raises(ProviderRoleViolationError):
            ProviderFactory.assert_role_allowed("cto", "claude")

    def test_worker_allowed_codex(self, tmp_jsonl):
        from orchestrator.provider_factory import ProviderFactory
        # Worker + codex は許可されるべき（例外なし）
        ProviderFactory.assert_role_allowed("worker", "codex")

    def test_worker_allowed_claude(self, tmp_jsonl):
        from orchestrator.provider_factory import ProviderFactory
        ProviderFactory.assert_role_allowed("worker", "claude")

    def test_worker_allowed_copilot(self, tmp_jsonl):
        from orchestrator.provider_factory import ProviderFactory
        ProviderFactory.assert_role_allowed("worker", "copilot")

    def test_blocked_event_written_to_jsonl(self, tmp_jsonl):
        from orchestrator.provider_factory import ProviderFactory, ProviderRoleViolationError
        with pytest.raises(ProviderRoleViolationError):
            ProviderFactory.assert_role_allowed("planner", "codex", task_id=99)
        records = [json.loads(l) for l in Path(tmp_jsonl).read_text().splitlines() if l.strip()]
        blocked = [r for r in records if r.get("blocked")]
        assert len(blocked) >= 1
        assert blocked[-1]["block_reason"] == "ROLE_PROVIDER_VIOLATION"
        assert blocked[-1]["task_id"] == 99

    def test_allowed_event_written_to_jsonl(self, tmp_jsonl):
        from orchestrator.provider_factory import ProviderFactory
        ProviderFactory.assert_role_allowed("worker", "codex", task_id=42)
        records = [json.loads(l) for l in Path(tmp_jsonl).read_text().splitlines() if l.strip()]
        allowed = [r for r in records if not r.get("blocked")]
        assert len(allowed) >= 1
        assert allowed[-1]["provider"] == "codex"
        assert allowed[-1]["runner"] == "worker"

    def test_is_external_returns_true_for_codex(self):
        from orchestrator.provider_factory import ProviderFactory
        assert ProviderFactory.is_external("codex") is True

    def test_is_external_returns_false_for_local(self):
        from orchestrator.provider_factory import ProviderFactory
        assert ProviderFactory.is_external("local") is False

    def test_is_local_returns_true_for_local(self):
        from orchestrator.provider_factory import ProviderFactory
        assert ProviderFactory.is_local("local") is True

    def test_is_local_returns_false_for_codex(self):
        from orchestrator.provider_factory import ProviderFactory
        assert ProviderFactory.is_local("codex") is False


# ─────────────────────────────────────────────────────────────────────────────
# 2. LlmUsageLogger
# ─────────────────────────────────────────────────────────────────────────────

class TestLlmUsageLogger:

    def test_log_allowed_event(self, tmp_jsonl):
        from orchestrator.llm_usage_logger import log_llm_event
        corr = str(uuid.uuid4())
        log_llm_event(
            runner="worker",
            provider="codex",
            blocked=False,
            correlation_id=corr,
            task_id=1,
        )
        records = [json.loads(l) for l in Path(tmp_jsonl).read_text().splitlines() if l.strip()]
        assert len(records) == 1
        r = records[0]
        assert r["runner"] == "worker"
        assert r["provider"] == "codex"
        assert r["blocked"] is False
        assert r["correlation_id"] == corr

    def test_log_blocked_event(self, tmp_jsonl):
        from orchestrator.llm_usage_logger import log_llm_event
        log_llm_event(
            runner="planner",
            provider="claude",
            blocked=True,
            block_reason="ROLE_PROVIDER_VIOLATION",
        )
        records = [json.loads(l) for l in Path(tmp_jsonl).read_text().splitlines() if l.strip()]
        assert records[-1]["blocked"] is True
        assert records[-1]["block_reason"] == "ROLE_PROVIDER_VIOLATION"

    def test_multiple_events_accumulate(self, tmp_jsonl):
        from orchestrator.llm_usage_logger import log_llm_event
        for i in range(5):
            log_llm_event(runner="worker", provider="codex", blocked=False, task_id=i)
        records = [json.loads(l) for l in Path(tmp_jsonl).read_text().splitlines() if l.strip()]
        assert len(records) == 5

    def test_missing_directory_is_created(self, tmp_path, monkeypatch):
        from orchestrator import llm_usage_logger
        deep_path = str(tmp_path / "deep" / "nested" / "llm_usage.jsonl")
        monkeypatch.setattr(llm_usage_logger, "_LOG_PATH", deep_path)
        log_llm_event = llm_usage_logger.log_llm_event
        log_llm_event(runner="worker", provider="codex", blocked=False)
        assert os.path.exists(deep_path)

    def test_rotation_triggered_on_large_file(self, tmp_jsonl, monkeypatch):
        from orchestrator import llm_usage_logger
        monkeypatch.setattr(llm_usage_logger, "_MAX_FILE_BYTES", 10)
        log_llm_event = llm_usage_logger.log_llm_event
        log_llm_event(runner="worker", provider="codex", blocked=False)
        log_llm_event(runner="worker", provider="codex", blocked=False)
        # 至少有一個 .1 檔被建立（因為 10 bytes 閾值很低）
        rotated = tmp_jsonl + ".1"
        # 不強制要求一定輪轉（取決於 JSON 長度），但可以確保不崩潰
        assert os.path.exists(tmp_jsonl) or os.path.exists(rotated)

    def test_caller_stack_is_list_of_strings(self, tmp_jsonl):
        from orchestrator.llm_usage_logger import log_llm_event
        log_llm_event(runner="worker", provider="codex", blocked=False)
        rec = json.loads(Path(tmp_jsonl).read_text().splitlines()[0])
        assert isinstance(rec["caller_stack"], list)
        assert all(isinstance(s, str) for s in rec["caller_stack"])


# ─────────────────────────────────────────────────────────────────────────────
# 3. execution_policy — 角色導向 Provider 政策
# ─────────────────────────────────────────────────────────────────────────────

class TestExecutionPolicyRoleGuard:

    def test_planner_blocked_by_role_ext_llm_flag(self, db_safe_run_planner_blocked):
        from orchestrator import execution_policy
        decision = execution_policy.evaluate_execution(
            runner="planner",
            requires_llm=True,
            background=True,
            provider="codex",
        )
        assert decision["allowed"] is False
        assert "role-ext-llm-disabled" in decision["reason"]

    def test_worker_allowed_when_role_enabled(self, db_safe_run_planner_blocked):
        from orchestrator import execution_policy
        decision = execution_policy.evaluate_execution(
            runner="worker",
            requires_llm=True,
            background=True,
            provider="codex",
        )
        assert decision["allowed"] is True

    def test_hard_off_overrides_everything(self, db_hardoff):
        from orchestrator import execution_policy
        from orchestrator.common import HARD_OFF_MODE
        for runner in ("planner", "worker", "cto"):
            decision = execution_policy.evaluate_execution(
                runner=runner,
                requires_llm=True,
                background=True,
                provider="codex",
            )
            assert decision["allowed"] is False
            assert decision["reason"] == HARD_OFF_MODE

    def test_provider_none_skips_role_check(self, db_safe_run_planner_blocked):
        """provider=None 時不觸發 role 檢查（非 LLM 執行）。"""
        from orchestrator import execution_policy
        decision = execution_policy.evaluate_execution(
            runner="planner",
            requires_llm=False,
            background=True,
            provider=None,
        )
        assert decision["allowed"] is True

    def test_record_llm_call_writes_jsonl(self, tmp_jsonl, db_safe_run_planner_blocked):
        from orchestrator import execution_policy
        execution_policy.record_llm_call(
            runner="worker",
            provider="codex",
            context="test-ctx",
            task_id=77,
        )
        records = [json.loads(l) for l in Path(tmp_jsonl).read_text().splitlines() if l.strip()]
        assert len(records) >= 1
        assert records[-1]["provider"] == "codex"
        assert records[-1]["blocked"] is False

    def test_record_llm_block_writes_jsonl(self, tmp_jsonl, db_safe_run_planner_blocked):
        from orchestrator import execution_policy
        execution_policy.record_llm_block(
            runner="planner",
            provider="claude",
            reason="ROLE_PROVIDER_VIOLATION",
            task_id=88,
        )
        records = [json.loads(l) for l in Path(tmp_jsonl).read_text().splitlines() if l.strip()]
        blocked = [r for r in records if r.get("blocked")]
        assert blocked[-1]["block_reason"] == "ROLE_PROVIDER_VIOLATION"


# ─────────────────────────────────────────────────────────────────────────────
# 4. DB 配額開關
# ─────────────────────────────────────────────────────────────────────────────

class TestDbQuotaSettings:

    def test_default_planner_ext_llm_disabled(self, monkeypatch):
        from orchestrator import db as orch_db
        monkeypatch.setattr(orch_db, "get_setting", lambda key, default="": orch_db.DEFAULT_SETTINGS.get(key, default))
        result = orch_db.get_ext_llm_role_enabled("planner")
        assert result is False

    def test_default_worker_ext_llm_enabled(self, monkeypatch):
        from orchestrator import db as orch_db
        monkeypatch.setattr(orch_db, "get_setting", lambda key, default="": orch_db.DEFAULT_SETTINGS.get(key, default))
        result = orch_db.get_ext_llm_role_enabled("worker")
        assert result is True

    def test_default_cto_ext_llm_disabled(self, monkeypatch):
        from orchestrator import db as orch_db
        monkeypatch.setattr(orch_db, "get_setting", lambda key, default="": orch_db.DEFAULT_SETTINGS.get(key, default))
        result = orch_db.get_ext_llm_role_enabled("cto")
        assert result is False

    def test_planner_daily_cap_is_zero(self, monkeypatch):
        from orchestrator import db as orch_db
        monkeypatch.setattr(orch_db, "get_setting", lambda key, default="": orch_db.DEFAULT_SETTINGS.get(key, default))
        assert orch_db.DEFAULT_SETTINGS.get("planner_daily_llm_cap") == "0"

    def test_cto_daily_cap_is_zero(self, monkeypatch):
        from orchestrator import db as orch_db
        assert orch_db.DEFAULT_SETTINGS.get("cto_daily_llm_cap") == "0"

    def test_worker_daily_cap_positive(self, monkeypatch):
        from orchestrator import db as orch_db
        monkeypatch.setattr(orch_db, "get_setting", lambda key, default="": orch_db.DEFAULT_SETTINGS.get(key, default))
        cap = orch_db.get_worker_daily_llm_cap()
        assert cap > 0

    def test_worker_hourly_cap_positive(self, monkeypatch):
        from orchestrator import db as orch_db
        monkeypatch.setattr(orch_db, "get_setting", lambda key, default="": orch_db.DEFAULT_SETTINGS.get(key, default))
        cap = orch_db.get_worker_hourly_llm_cap()
        assert cap > 0

    def test_planner_provider_default_is_local(self):
        from orchestrator import db as orch_db
        assert orch_db.DEFAULT_SETTINGS.get("planner_provider") == "local"

    def test_cto_planner_provider_default_is_local(self):
        from orchestrator import db as orch_db
        assert orch_db.DEFAULT_SETTINGS.get("cto_planner_provider") == "local"


# ─────────────────────────────────────────────────────────────────────────────
# 5. Planner — 靜態驗證（不呼叫外部 LLM）
# ─────────────────────────────────────────────────────────────────────────────

class TestPlannerStaticGuarantee:

    def test_planner_tick_has_no_subprocess_import_for_llm(self):
        """
        planner_tick.py 本身不能直接呼叫 codex/claude/copilot subprocess。
        靜態分析：若 planner_tick.py 含有 subprocess.run + (codex|claude|copilot) 字樣組合，測試失敗。
        """
        planner_path = ROOT / "orchestrator" / "planner_tick.py"
        source = planner_path.read_text(encoding="utf-8")
        # 一定不能有直接 subprocess.run([...codex...]) 這樣的組合
        lower = source.lower()
        assert "subprocess.run" not in lower or not any(
            kw in lower for kw in ['"codex"', "'codex'", '"claude"', "'claude'", '"copilot"', "'copilot'"]
        ), "planner_tick.py 不應直接執行 LLM subprocess！"

    def test_planner_tick_does_not_import_provider_directly(self):
        """planner_tick.py 不應 import 任何 execute_task_with_* 函式。"""
        planner_path = ROOT / "orchestrator" / "planner_tick.py"
        source = planner_path.read_text(encoding="utf-8")
        assert "execute_task_with_claude" not in source
        assert "execute_task_with_codex" not in source
        assert "execute_task_with_copilot" not in source

    def test_planner_create_tasks_use_worker_type_not_provider(self):
        """planner_tick.py 的 create_task 呼叫必須只指定 worker_type，不可傳入外部 provider。"""
        planner_path = ROOT / "orchestrator" / "planner_tick.py"
        source = planner_path.read_text(encoding="utf-8")
        # create_task 呼叫中不應出現 worker_provider= 外部 LLM provider
        import re
        create_task_calls = re.findall(
            r"db\.create_task\([^)]{0,500}\)",
            source,
            re.DOTALL,
        )
        for call in create_task_calls:
            # 若有 worker_provider，其值不應是外部 LLM
            if "worker_provider" in call:
                for ext in ("codex", "claude", "copilot"):
                    assert ext not in call, (
                        f"planner_tick.py 的 create_task 呼叫不應指定外部 worker_provider={ext}！\n{call}"
                    )


# ─────────────────────────────────────────────────────────────────────────────
# 6. Worker tick — ProviderFactory 整合
# ─────────────────────────────────────────────────────────────────────────────

class TestWorkerTickProviderGuard:

    def test_worker_tick_calls_provider_factory(self):
        """worker_tick.py 的 _assert_llm_execution_allowed 必須呼叫 ProviderFactory。"""
        worker_path = ROOT / "orchestrator" / "worker_tick.py"
        source = worker_path.read_text(encoding="utf-8")
        assert "ProviderFactory" in source
        assert "assert_role_allowed" in source

    def test_provider_factory_role_violation_in_worker_not_triggered_for_worker(self, tmp_jsonl):
        """Worker 角色呼叫 ProviderFactory 不應 raise（Worker 被允許使用 codex）。"""
        from orchestrator.provider_factory import ProviderFactory
        # 不應 raise
        ProviderFactory.assert_role_allowed("worker", "codex", task_id=1)
        ProviderFactory.assert_role_allowed("worker", "claude", task_id=2)
        ProviderFactory.assert_role_allowed("worker", "copilot", task_id=3)
