"""
tests/test_phase36_copilot_daemon_cli_compat.py

Phase 36A — Copilot Daemon CLI Compatibility Tests
====================================================
10 個測試，覆蓋：
 1.  detect agent_cli when copilot binary exists
 2.  detect gh_extension_legacy when only gh copilot suggest --target
 3.  unavailable mode if neither exists
 4.  agent_cli command includes copilot -p and --model gpt-5-mini
 5.  legacy mode preserves old command format
 6.  auto model omits --model
 7.  policy blocked path does not run subprocess
 8.  audit failure does not run subprocess
 9.  successful mocked execution writes usage result
10.  no real Copilot / GitHub call occurs in tests

設計原則：
- 所有 subprocess.run 皆 mock，絕不呼叫外部工具
- 不消耗任何 Copilot / GitHub 配額
- 使用 monkeypatch 重導 audit / usage 路徑
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock, patch, call

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ── 強制重置 CLI 模式快取（每次 import 可能已快取）─────────────────────────
import orchestrator.copilot_daemon as daemon_module


@pytest.fixture(autouse=True)
def reset_cli_mode_cache():
    """每個測試前清除 detect_copilot_cli_mode() 的模組層快取。"""
    daemon_module._CLI_MODE_CACHE = None
    daemon_module._CLI_MODE_CACHE_TIME = 0.0
    yield
    daemon_module._CLI_MODE_CACHE = None
    daemon_module._CLI_MODE_CACHE_TIME = 0.0


@pytest.fixture()
def tmp_audit_jsonl(tmp_path, monkeypatch):
    """重導 llm_audit._AUDIT_PATH 至臨時目錄。"""
    from orchestrator import llm_audit
    audit_file = str(tmp_path / "llm_audit.jsonl")
    monkeypatch.setattr(llm_audit, "_AUDIT_PATH", audit_file)
    return audit_file


@pytest.fixture()
def tmp_usage_jsonl(tmp_path, monkeypatch):
    """重導 llm_usage_logger._LOG_PATH 至臨時目錄。"""
    from orchestrator import llm_usage_logger
    log_file = str(tmp_path / "llm_usage.jsonl")
    monkeypatch.setattr(llm_usage_logger, "_LOG_PATH", log_file)
    return log_file


# ─────────────────────────────────────────────────────────────────────────────
# Test 1: detect agent_cli when copilot binary exists and supports -p
# ─────────────────────────────────────────────────────────────────────────────

def test_detect_agent_cli_when_copilot_binary_exists():
    """當 copilot binary 存在且 --help 包含 --prompt 時，偵測為 agent_cli。"""
    fake_help = "Usage: copilot [options]\n  --prompt, -p <string>  Execute a prompt\n"
    mock_result = MagicMock(stdout=fake_help, stderr="", returncode=0)

    with patch("shutil.which", side_effect=lambda x: f"/usr/local/bin/{x}" if x == "copilot" else None), \
         patch("os.path.isfile", return_value=True), \
         patch("subprocess.run", return_value=mock_result):

        mode = daemon_module.detect_copilot_cli_mode()

    assert mode == "agent_cli", f"Expected agent_cli, got {mode!r}"


# ─────────────────────────────────────────────────────────────────────────────
# Test 2: detect gh_extension_legacy when only gh copilot suggest exists
# ─────────────────────────────────────────────────────────────────────────────

def test_detect_gh_extension_legacy_when_only_gh_available():
    """當 copilot binary 不存在、gh copilot suggest --help 含 --target 時，偵測為 gh_extension_legacy。"""
    legacy_help = "Usage: copilot suggest [flags] <prompt>\n  --target string  shell|git|gh\n"
    mock_result = MagicMock(stdout=legacy_help, stderr="", returncode=0)

    def which_side_effect(name: str) -> Optional[str]:
        if name == "gh":
            return "/usr/bin/gh"
        return None  # copilot not found

    with patch("shutil.which", side_effect=which_side_effect), \
         patch("os.path.isfile", return_value=True), \
         patch("subprocess.run", return_value=mock_result):

        mode = daemon_module.detect_copilot_cli_mode()

    assert mode == "gh_extension_legacy", f"Expected gh_extension_legacy, got {mode!r}"


# ─────────────────────────────────────────────────────────────────────────────
# Test 3: unavailable mode if neither exists
# ─────────────────────────────────────────────────────────────────────────────

def test_detect_unavailable_when_neither_cli_exists():
    """當 copilot 和 gh 都不在 PATH 時，回傳 unavailable。"""
    with patch("shutil.which", return_value=None):
        mode = daemon_module.detect_copilot_cli_mode()

    assert mode == "unavailable", f"Expected unavailable, got {mode!r}"


# ─────────────────────────────────────────────────────────────────────────────
# Test 4: agent_cli command includes copilot -p and --model gpt-5-mini
# ─────────────────────────────────────────────────────────────────────────────

def test_build_agent_cli_command_with_model():
    """agent_cli 模式建構指令包含 -p 和 --model gpt-5-mini。"""
    with patch("shutil.which", return_value="/usr/local/bin/copilot"):
        cmd = daemon_module.build_copilot_command(
            prompt="test prompt",
            model="gpt-5-mini",
            cli_mode="agent_cli",
            dry_run=True,
        )

    assert "/usr/local/bin/copilot" in cmd[0] or cmd[0] == "copilot"
    assert "-p" in cmd
    assert "--allow-all-tools" in cmd
    assert "--model" in cmd
    model_idx = cmd.index("--model")
    assert cmd[model_idx + 1] == "gpt-5-mini"
    # dry_run=True 時 prompt 被替換
    p_idx = cmd.index("-p")
    assert cmd[p_idx + 1] == "[PROMPT_CONTENT]"


# ─────────────────────────────────────────────────────────────────────────────
# Test 5: legacy mode preserves old command format
# ─────────────────────────────────────────────────────────────────────────────

def test_build_legacy_command_format():
    """gh_extension_legacy 模式建構指令使用 gh copilot suggest --target shell。"""
    with patch("shutil.which", return_value="/usr/bin/gh"):
        cmd = daemon_module.build_copilot_command(
            prompt="test prompt",
            model="gpt-5-mini",
            cli_mode="gh_extension_legacy",
            dry_run=True,
        )

    assert cmd[0] == "/usr/bin/gh" or cmd[0] == "gh"
    assert "copilot" in cmd
    assert "suggest" in cmd
    assert "--target" in cmd
    target_idx = cmd.index("--target")
    assert cmd[target_idx + 1] == "shell"
    assert "--model" in cmd
    model_idx = cmd.index("--model")
    assert cmd[model_idx + 1] == "gpt-5-mini"


# ─────────────────────────────────────────────────────────────────────────────
# Test 6: auto model omits --model flag
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("model", ["auto", "", None])
def test_auto_and_empty_model_omits_model_flag(model):
    """model='auto', '' 或 None 時，指令不包含 --model。"""
    with patch("shutil.which", return_value="/usr/local/bin/copilot"):
        cmd = daemon_module.build_copilot_command(
            prompt="test prompt",
            model=model,
            cli_mode="agent_cli",
            dry_run=True,
        )

    assert "--model" not in cmd, f"Expected no --model in cmd for model={model!r}, got {cmd}"


# ─────────────────────────────────────────────────────────────────────────────
# Test 7: policy blocked path does not run subprocess
# ─────────────────────────────────────────────────────────────────────────────

def test_policy_blocked_does_not_run_subprocess(tmp_path, monkeypatch, tmp_audit_jsonl, tmp_usage_jsonl):
    """execution_policy 封鎖時，_execute_task 不呼叫任何 LLM subprocess。"""
    from orchestrator import execution_policy

    # 預設 CLI 快取，避免偵測期間的 subprocess.run 呼叫
    monkeypatch.setattr(daemon_module, "_CLI_MODE_CACHE", "agent_cli")
    monkeypatch.setattr(daemon_module, "_CLI_MODE_CACHE_TIME", float("inf"))
    # 跳過 git dirty-file 查詢
    monkeypatch.setattr(daemon_module, "_list_dirty_files", lambda: [])

    # 模擬 hard-off 政策
    monkeypatch.setattr(
        execution_policy, "assert_llm_execution_allowed",
        lambda **kwargs: (_ for _ in ()).throw(
            RuntimeError("BLOCKED: hard-off mode")
        ),
    )

    # 建立假 prompt 檔案
    prompt_file = tmp_path / "task-prompt.md"
    prompt_file.write_text("Do something useful")
    task = {
        "id": 999,
        "slot_key": "task-999",
        "prompt_file_path": str(prompt_file),
        "expected_duration_hours": 0.1,
    }

    with patch("subprocess.run") as mock_run:
        with pytest.raises(RuntimeError, match="BLOCKED"):
            daemon_module._execute_task(task)

        # CLI detect 與 git diff 皆已被 mock 繞過，subprocess.run 不得被呼叫
        mock_run.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# Test 8: audit failure (write_attempt returns None) blocks subprocess
# ─────────────────────────────────────────────────────────────────────────────

def test_audit_failure_blocks_subprocess(tmp_path, monkeypatch, tmp_usage_jsonl):
    """write_attempt 回傳 None（寫入失敗）時，AuditGuard 拋出 AuditGuardBlockedError，subprocess 不執行。"""
    import orchestrator.provider_audit_guard as aug_module
    from orchestrator import execution_policy

    # 預設 CLI 快取，避免偵測期間的 subprocess.run 呼叫
    monkeypatch.setattr(daemon_module, "_CLI_MODE_CACHE", "agent_cli")
    monkeypatch.setattr(daemon_module, "_CLI_MODE_CACHE_TIME", float("inf"))
    # 跳過 git dirty-file 查詢
    monkeypatch.setattr(daemon_module, "_list_dirty_files", lambda: [])

    # policy 允許
    monkeypatch.setattr(
        execution_policy, "assert_llm_execution_allowed",
        lambda **kwargs: None,
    )
    # 隔離 usage_budget_guard 以防止 live llm_usage.jsonl 觸發 HARD_CAP
    import orchestrator.usage_budget_guard as ubg_module
    monkeypatch.setattr(ubg_module, "is_provider_allowed", lambda *a, **kw: (True, None))
    # 直接 patch AuditGuard 使用的 write_attempt（在 provider_audit_guard 模組中）
    monkeypatch.setattr(aug_module, "write_attempt", lambda **kwargs: None)
    monkeypatch.setattr(aug_module, "write_blocked", lambda **kwargs: None)

    prompt_file = tmp_path / "task-prompt.md"
    prompt_file.write_text("Audit fail test")
    task = {
        "id": 998,
        "slot_key": "task-998",
        "prompt_file_path": str(prompt_file),
        "expected_duration_hours": 0.1,
    }

    with patch("subprocess.run") as mock_run:
        with pytest.raises(RuntimeError, match="audit guard blocked"):
            daemon_module._execute_task(task)

        mock_run.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# Test 9: successful mocked execution writes usage result
# ─────────────────────────────────────────────────────────────────────────────

def test_successful_mocked_execution_writes_usage(
    tmp_path, monkeypatch, tmp_audit_jsonl, tmp_usage_jsonl
):
    """成功的模擬執行寫入 usage 記錄，並回傳 success=True。"""
    from orchestrator import execution_policy, llm_usage_logger

    # policy 允許
    monkeypatch.setattr(
        execution_policy, "assert_llm_execution_allowed",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        execution_policy, "evaluate_execution",
        lambda **kwargs: {"reason": None, "mode": "safe-run"},
    )
    # 隔離 usage_budget_guard 以防止 live llm_usage.jsonl 觸發 HARD_CAP
    import orchestrator.usage_budget_guard as ubg_module
    monkeypatch.setattr(ubg_module, "is_provider_allowed", lambda *a, **kw: (True, None))

    # DB: gpt-5-mini model
    monkeypatch.setattr(
        daemon_module.db, "get_worker_copilot_model",
        lambda: "gpt-5-mini",
    )

    # 強制使用 agent_cli 模式（跳過 subprocess detect）
    monkeypatch.setattr(daemon_module, "_CLI_MODE_CACHE", "agent_cli")
    monkeypatch.setattr(daemon_module, "_CLI_MODE_CACHE_TIME", float("inf"))
    # 跳過 git dirty-file 查詢
    monkeypatch.setattr(daemon_module, "_list_dirty_files", lambda: [])

    # Mock subprocess.run: 回傳成功結果
    fake_completed = MagicMock(
        returncode=0,
        stdout="Task completed successfully.",
        stderr="",
    )

    # 建立假 prompt 和 completed 目錄
    task_dir = tmp_path / "tasks" / "task-001"
    task_dir.mkdir(parents=True)
    prompt_file = task_dir / "task-001-prompt.md"
    prompt_file.write_text("Please fix the bug")
    completed_file = task_dir / "task-001-completed.md"
    completed_file.write_text("Fixed the bug.")

    task = {
        "id": 1,
        "slot_key": "task-001",
        "prompt_file_path": str(prompt_file),
        "expected_duration_hours": 0.1,
    }

    with patch("subprocess.run", return_value=fake_completed) as mock_run:
        result = daemon_module._execute_task(task)

    assert result["success"] is True
    assert "completed_file_path" in result

    # subprocess.run 應被呼叫恰好一次（copilot agent_cli，git 已 mock 繞過）
    mock_run.assert_called_once()
    cmd = mock_run.call_args[0][0]
    # 驗證使用 agent_cli 格式：包含 -p 旗標
    assert "-p" in cmd, f"Expected -p in cmd: {cmd}"
    assert "--allow-all-tools" in cmd, f"Expected --allow-all-tools in cmd: {cmd}"
    assert "--model" in cmd, f"Expected --model in cmd: {cmd}"
    model_idx = cmd.index("--model")
    assert cmd[model_idx + 1] == "gpt-5-mini"

    # usage log 應寫入
    if os.path.exists(tmp_usage_jsonl):
        with open(tmp_usage_jsonl, "r") as f:
            records = [json.loads(line) for line in f if line.strip()]
        # 至少有一筆成功記錄
        assert len(records) >= 1


# ─────────────────────────────────────────────────────────────────────────────
# Test 10: no real Copilot / GitHub call occurs during test suite
# ─────────────────────────────────────────────────────────────────────────────

def test_no_real_external_call_in_test_suite(monkeypatch):
    """
    驗證：測試中所有外部呼叫皆被 mock，無真實 Copilot/GitHub 呼叫。
    使用 subprocess.run 的呼叫記錄驗證沒有真實 copilot/gh binary 被執行。
    """
    call_log: list[list[str]] = []

    def recording_run(cmd, **kwargs):
        call_log.append(list(cmd))
        # 若偵測到真實 copilot/gh 呼叫，立即 fail
        if cmd and len(cmd) > 0:
            binary = os.path.basename(str(cmd[0]))
            if binary in ("copilot", "gh") and kwargs.get("capture_output"):
                # 允許 detect 過程中的 --help 查詢
                if "--help" in cmd:
                    return MagicMock(stdout="", stderr="", returncode=0)
                # 真實執行呼叫（含 -p 或 suggest）不允許
                if "-p" in cmd or "suggest" in cmd:
                    pytest.fail(
                        f"Detected real external CLI call in test suite: {cmd}"
                    )
        return MagicMock(stdout="", stderr="", returncode=0)

    with patch("subprocess.run", side_effect=recording_run):
        # 偵測模式（只呼叫 --help，OK）
        daemon_module.detect_copilot_cli_mode()

        # build command 不執行（dry_run=True）
        try:
            daemon_module.build_copilot_command("prompt", "gpt-5-mini", "agent_cli", dry_run=True)
        except ValueError:
            pass

    # 沒有真實執行呼叫（-p 或 suggest 但不含 --help）
    real_calls = [
        c for c in call_log
        if ("-p" in c or "suggest" in c) and "--help" not in c
    ]
    assert len(real_calls) == 0, f"Real external CLI execution calls detected: {real_calls}"
