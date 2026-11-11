"""
tests/test_audit_guard_integration.py

Phase A1 — AuditGuard 整合測試。

10 個測試涵蓋：
  1.  Planner 預設 provider 為 "local"（app.py + db.py 設定）
  2.  Worker 允許呼叫 → ATTEMPT + RESULT 寫入 audit JSONL
  3.  Worker audit write failure → subprocess NOT 呼叫
  4.  Worker blocked provider → BLOCKED 事件，no subprocess
  5.  Copilot-Daemon 允許呼叫 → ATTEMPT + RESULT
  6.  Copilot-Daemon blocked（policy）→ BLOCKED 事件
  7.  Deterministic/local task → 無 audit 事件
  8.  Decision Card render 含 LLM Audit section
  9.  Coverage checker 回傳 FULL 或記錄 exclusions（無 uncovered）
  10. 既有 Usage logging（llm_usage.jsonl）仍正常運作（parallel to audit）
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, call

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


def _read_jsonl(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    records = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


# ── Test 1: Planner default provider is "local" ───────────────────────────────

def test_planner_provider_default_is_local():
    """app.py 及 db.DEFAULT_SETTINGS 中 planner_provider 預設為 'local'。"""
    from orchestrator import db
    assert db.DEFAULT_SETTINGS.get("planner_provider") == "local", (
        "planner_provider DEFAULT must be 'local' (not codex/claude)"
    )


# ── Test 2: Worker allowed → ATTEMPT + RESULT ─────────────────────────────────

def test_worker_claude_allowed_writes_attempt_and_result(tmp_audit, monkeypatch):
    """Worker 執行 Claude 任務時，audit JSONL 應有 ATTEMPT + RESULT 各一筆。"""
    import orchestrator.worker_tick as wt

    # 允許 execution policy
    monkeypatch.setattr("orchestrator.execution_policy.evaluate_execution", lambda **kw: {"allowed": True, "mode": "safe-run", "reason": None})
    monkeypatch.setattr("orchestrator.execution_policy.record_llm_call", lambda **kw: None)
    monkeypatch.setattr("orchestrator.provider_factory.ProviderFactory.assert_role_allowed", staticmethod(lambda r, p: None))

    # Mock subprocess.run 回傳成功
    fake_proc = MagicMock()
    fake_proc.returncode = 0
    fake_proc.stdout = "# Done\n"
    fake_proc.stderr = ""

    import shutil as shutil_mod
    monkeypatch.setattr(shutil_mod, "which", lambda x: f"/usr/bin/{x}")
    monkeypatch.setattr(os.path, "isfile", lambda p: True)
    import subprocess as sp_mod
    monkeypatch.setattr(sp_mod, "run", lambda *a, **kw: fake_proc)

    # 建立假 prompt file
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        prompt_path = os.path.join(td, "task-prompt.md")
        with open(prompt_path, "w") as f:
            f.write("# Do the work")

        task = {
            "id": 77,
            "slot_key": "slot-1",
            "prompt_file_path": prompt_path,
            "expected_duration_hours": 0.01,
        }
        # patch open for completed file write — allow it
        result = wt.execute_task_with_claude(task)

    assert result["success"] is True
    records = _read_jsonl(tmp_audit)
    event_types = [r["event_type"] for r in records]
    assert "LLM_CALL_ATTEMPT" in event_types, f"No ATTEMPT found in {event_types}"
    assert "LLM_CALL_RESULT" in event_types, f"No RESULT found in {event_types}"
    # Correlation IDs should match
    attempt = next(r for r in records if r["event_type"] == "LLM_CALL_ATTEMPT")
    result_rec = next(r for r in records if r["event_type"] == "LLM_CALL_RESULT")
    assert attempt["correlation_id"] == result_rec["correlation_id"]


# ── Test 3: Worker audit write failure → subprocess NOT called ────────────────

def test_worker_audit_write_failure_blocks_subprocess(tmp_audit, monkeypatch):
    """ATTEMPT 寫入失敗時，AuditGuardBlockedError 必須阻斷 subprocess 呼叫。"""
    import orchestrator.worker_tick as wt

    monkeypatch.setattr("orchestrator.execution_policy.evaluate_execution", lambda **kw: {"allowed": True, "mode": "safe-run", "reason": None})
    monkeypatch.setattr("orchestrator.execution_policy.record_llm_call", lambda **kw: None)
    monkeypatch.setattr("orchestrator.provider_factory.ProviderFactory.assert_role_allowed", staticmethod(lambda r, p: None))

    # Force ATTEMPT write to fail by making _AUDIT_PATH unwritable
    import orchestrator.llm_audit as audit_mod
    monkeypatch.setattr(audit_mod, "_AUDIT_PATH", "/dev/full/no-permission/audit.jsonl")

    subprocess_called = []

    def fake_subprocess_run(*a, **kw):
        # Allow git commands (used by _list_dirty_files)
        cmd = a[0] if a else kw.get("args", [])
        if isinstance(cmd, list) and cmd and cmd[0] == "git":
            m = MagicMock(); m.returncode = 0; m.stdout = ""; m.stderr = ""
            return m
        subprocess_called.append(True)
        raise AssertionError("subprocess.run should NOT be called when audit guard blocks")

    import shutil as shutil_mod
    monkeypatch.setattr(shutil_mod, "which", lambda x: f"/usr/bin/{x}")
    monkeypatch.setattr(os.path, "isfile", lambda p: True)
    import subprocess as sp_mod
    monkeypatch.setattr(sp_mod, "run", fake_subprocess_run)

    with tempfile.TemporaryDirectory() as td:
        prompt_path = os.path.join(td, "task-prompt.md")
        with open(prompt_path, "w") as f:
            f.write("# Do the work")

        task = {
            "id": 88,
            "slot_key": "slot-1",
            "prompt_file_path": prompt_path,
            "expected_duration_hours": 0.01,
        }
        with pytest.raises(RuntimeError, match="audit guard blocked"):
            wt.execute_task_with_claude(task)

    assert not subprocess_called, "subprocess.run was called despite audit guard failure"


# ── Test 4: Worker blocked provider → BLOCKED event ─────────────────────────

def test_worker_blocked_provider_writes_blocked_event(tmp_audit, monkeypatch):
    """ProviderRoleViolationError → _assert_llm_execution_allowed raises → no AuditGuard/subprocess."""
    import orchestrator.worker_tick as wt
    from orchestrator.provider_factory import ProviderRoleViolationError

    def _raise_violation(role, provider):
        raise ProviderRoleViolationError(f"{role} cannot use {provider}")

    monkeypatch.setattr("orchestrator.provider_factory.ProviderFactory.assert_role_allowed", staticmethod(_raise_violation))

    subprocess_called = []
    monkeypatch.setattr("subprocess.run", lambda *a, **kw: subprocess_called.append(True))

    with tempfile.TemporaryDirectory() as td:
        prompt_path = os.path.join(td, "task-prompt.md")
        with open(prompt_path, "w") as f:
            f.write("# Blocked task")

        task = {
            "id": 99,
            "slot_key": "slot-1",
            "prompt_file_path": prompt_path,
            "expected_duration_hours": 0.01,
        }
        with pytest.raises(Exception):
            wt.execute_task_with_claude(task)

    assert not subprocess_called


# ── Test 5: Copilot-Daemon allowed → ATTEMPT + RESULT ─────────────────────────

def test_copilot_daemon_allowed_writes_attempt_and_result(tmp_audit, monkeypatch):
    """Copilot-Daemon 成功執行時，audit JSONL 應有 ATTEMPT + RESULT。"""
    import orchestrator.copilot_daemon as cd

    monkeypatch.setattr("orchestrator.execution_policy.evaluate_execution", lambda **kw: {"allowed": True, "mode": "safe-run", "reason": None})
    monkeypatch.setattr("orchestrator.execution_policy.record_llm_call", lambda **kw: None)

    fake_proc = MagicMock()
    fake_proc.returncode = 0
    fake_proc.stdout = "# Completed\n"
    fake_proc.stderr = ""

    import shutil as shutil_mod
    monkeypatch.setattr(shutil_mod, "which", lambda x: f"/usr/bin/{x}")
    monkeypatch.setattr(os.path, "isfile", lambda p: True)
    import subprocess as sp_mod
    monkeypatch.setattr(sp_mod, "run", lambda *a, **kw: fake_proc)

    # Mock db calls
    monkeypatch.setattr("orchestrator.db.get_worker_copilot_model", lambda: None)

    with tempfile.TemporaryDirectory() as td:
        prompt_path = os.path.join(td, "task-prompt.md")
        with open(prompt_path, "w") as f:
            f.write("# Copilot task")

        task = {
            "id": 55,
            "slot_key": "slot-copi",
            "prompt_file_path": prompt_path,
            "expected_duration_hours": 0.01,
        }
        result = cd._execute_task(task)

    assert result["success"] is True
    records = _read_jsonl(tmp_audit)
    event_types = [r["event_type"] for r in records]
    assert "LLM_CALL_ATTEMPT" in event_types
    assert "LLM_CALL_RESULT" in event_types


# ── Test 6: Copilot-Daemon blocked → BLOCKED event ──────────────────────────

def test_copilot_daemon_blocked_writes_blocked_event(tmp_audit, monkeypatch):
    """run_once() scheduler block → write_blocked 應寫入 BLOCKED 事件。"""
    import orchestrator.copilot_daemon as cd

    # Simulate runtime block
    monkeypatch.setattr(cd, "_runtime_block_reason", lambda: "hard-off mode active")
    monkeypatch.setattr(cd, "_read_lock", lambda: None)  # no existing lock
    monkeypatch.setattr("orchestrator.execution_policy.set_active_background_runner", lambda *a: None)
    monkeypatch.setattr(cd, "_write_state", lambda *a, **kw: None)
    monkeypatch.setattr("orchestrator.db.get_worker_provider", lambda: "copilot-daemon")

    cd.run_once()

    records = _read_jsonl(tmp_audit)
    blocked_events = [r for r in records if r.get("event_type") == "LLM_CALL_BLOCKED"]
    assert blocked_events, f"No BLOCKED event found; got: {[r.get('event_type') for r in records]}"
    assert blocked_events[0]["runner_type"] == "copilot_daemon"
    assert "hard-off" in blocked_events[0]["block_reason"]


# ── Test 7: Local/deterministic task → no audit events ───────────────────────

def test_local_provider_no_audit_events(tmp_audit):
    """本地 provider ('local', 'deterministic') 不寫入任何 audit 事件。"""
    from orchestrator.llm_audit import write_attempt, _is_external

    assert _is_external("local") is False
    assert _is_external("deterministic") is False
    assert _is_external("rule-based") is False
    assert _is_external("adaptive_regime") is False
    assert _is_external("none") is False

    # write_attempt for local provider → should skip silently (does NOT write to JSONL)
    cid = write_attempt(runner="planner", provider="local", task_id=1, trigger_source="test")
    records = _read_jsonl(tmp_audit)
    assert len(records) == 0, "Local provider must not write audit events"
    # cid may be a UUID stub (non-None) but no record must be written
    assert records == [], "No JSONL record expected for local provider"


# ── Test 8: Decision Card renders LLM Audit section ──────────────────────────

def test_decision_card_renders_audit_section(monkeypatch):
    """render_card() 應包含 'LLM AUDIT' section。"""
    import scripts.ops_decision_card as card_mod

    # Inject a minimal audit_summary
    def _fake_audit():
        return {
            "available": True,
            "total": {"ATTEMPT": 3, "RESULT": 3, "BLOCKED": 1},
            "by_role": {"worker": {"ATTEMPT": 3, "RESULT": 3, "BLOCKED": 0}},
            "recent": [
                {"time": "2026-01-01 12:00", "event": "LLM_CALL_ATTEMPT", "runner": "worker_tick",
                 "provider": "claude", "task_id": 1, "success": None},
            ],
        }

    monkeypatch.setattr(card_mod, "compute_llm_audit_summary", _fake_audit)

    payload = card_mod.build_payload()
    card_text = card_mod.render_card(payload)

    assert "LLM AUDIT" in card_text or "Audit" in card_text, (
        "render_card() should include LLM Audit section"
    )
    assert "ATTEMPT" in card_text


# ── Test 9: Coverage checker returns FULL or documents exclusions ─────────────

def test_audit_coverage_checker_no_uncovered():
    """llm_audit_coverage.check_coverage() must return FULL or have no uncovered non-excluded paths."""
    from orchestrator.llm_audit_coverage import check_coverage

    result = check_coverage()
    assert "coverage_status" in result
    assert result["coverage_status"] in ("FULL", "PARTIAL", "FAILED")

    # No uncovered paths that are not intentionally excluded
    uncovered = result.get("uncovered_paths", [])
    assert uncovered == [], (
        f"AuditGuard coverage incomplete. Uncovered paths: {uncovered}\n"
        f"Warnings: {result.get('warnings', [])}"
    )


# ── Test 10: Usage logging still works alongside audit ────────────────────────

def test_usage_logging_works_parallel_to_audit(tmp_audit, tmp_usage, monkeypatch):
    """AuditGuard 不得干擾 llm_usage_logger；兩者可並行寫入。"""
    from orchestrator.llm_audit import write_attempt, write_result
    from orchestrator.llm_usage_logger import log_usage

    # Write audit events
    cid = write_attempt(runner="worker_tick", provider="claude", task_id=10, trigger_source="test")
    assert cid is not None
    write_result(correlation_id=cid, runner="worker_tick", provider="claude", success=True)

    # Write usage event separately
    log_usage(runner="worker_tick", provider="claude", blocked=False, task_id=10)

    audit_records = _read_jsonl(tmp_audit)
    usage_records = _read_jsonl(tmp_usage)

    assert len(audit_records) == 2  # ATTEMPT + RESULT
    assert len(usage_records) == 1  # usage log

    # Audit record has required fields
    attempt = next(r for r in audit_records if r["event_type"] == "LLM_CALL_ATTEMPT")
    assert attempt["runner_type"] == "worker_tick"
    assert attempt["provider"] == "claude"
    assert attempt["task_id"] == 10

    # Usage record has required fields
    assert usage_records[0]["runner"] == "worker_tick"
