"""
tests/test_universal_usage_logging.py

Universal AI / GitHub Usage Logging — 驗證測試套件。

測試清單（10 個）：
    1. Codex 執行呼叫已記錄至 JSONL
    2. Claude 執行呼叫已記錄至 JSONL
    3. GitHub Copilot 呼叫已記錄至 JSONL
    4. GitHub CLI/API 呼叫已記錄（log_usage provider=github-api）
    5. Planner 呼叫外部 provider 被封鎖並記錄
    6. Worker 允許的呼叫已記錄（完整欄位）
    7. 被封鎖的嘗試不執行子程序
    8. Usage card 聚合各 provider 統計
    9. Recent 表格包含 Claude / Codex / GitHub 列
    10. 損壞的 JSONL 行不崩潰

設計原則：
- 使用 tmp_jsonl fixture monkeypatch _LOG_PATH，不污染生產 JSONL
- 絕不呼叫外部工具（所有 subprocess 皆 mock）
- 不消耗 Codex / Claude / GitHub 配額
"""
from __future__ import annotations

import json
import os
import pytest
from unittest.mock import patch, MagicMock
from typing import Generator


# ── Fixture: 暫存 JSONL 路徑 ──────────────────────────────────────────────
@pytest.fixture
def tmp_jsonl(tmp_path: pytest.TempPathFactory) -> Generator[str, None, None]:  # type: ignore[type-arg]
    """回傳一個臨時 JSONL 路徑，並 monkeypatch llm_usage_logger._LOG_PATH。"""
    log_file = str(tmp_path / "llm_usage.jsonl")
    import orchestrator.llm_usage_logger as logger_module
    original = logger_module._LOG_PATH
    logger_module._LOG_PATH = log_file
    yield log_file
    logger_module._LOG_PATH = original


@pytest.fixture
def tmp_reader_jsonl(tmp_path: pytest.TempPathFactory) -> Generator[str, None, None]:  # type: ignore[type-arg]
    """回傳一個臨時 JSONL 路徑，並 monkeypatch usage_reader._LOG_PATH。"""
    log_file = str(tmp_path / "usage.jsonl")
    import orchestrator.usage_reader as reader_module
    original = reader_module._LOG_PATH
    reader_module._LOG_PATH = log_file
    yield log_file
    reader_module._LOG_PATH = original


def _read_records(path: str) -> list[dict]:
    """讀取 JSONL 並回傳已解析的 dict 列表。"""
    if not os.path.exists(path):
        return []
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


# ── Test 1: Codex 呼叫已記錄 ─────────────────────────────────────────────
def test_codex_call_logged(tmp_jsonl: str) -> None:
    """log_usage 寫入 provider=codex 的記錄。"""
    from orchestrator.llm_usage_logger import log_usage

    log_usage(
        runner="worker_tick",
        provider="codex",
        blocked=False,
        task_id=42,
        success=True,
        source_file="orchestrator/worker_tick.py",
        source_function="execute_task_with_codex",
        entrypoint="post_execution",
    )

    records = _read_records(tmp_jsonl)
    assert len(records) == 1
    r = records[0]
    assert r["provider"] == "codex"
    assert r["role"] == "worker"
    assert r["success"] is True
    assert r["blocked"] is False
    assert r["task_id"] == 42
    assert r["source_function"] == "execute_task_with_codex"


# ── Test 2: Claude 呼叫已記錄 ────────────────────────────────────────────
def test_claude_call_logged(tmp_jsonl: str) -> None:
    """log_usage 寫入 provider=claude，anthropic alias 也被正規化。"""
    from orchestrator.llm_usage_logger import log_usage

    # 測試 alias：anthropic → claude
    log_usage(
        runner="worker_tick",
        provider="anthropic",
        blocked=False,
        task_id=1,
        success=True,
        raw_usage_text="Output tokens: 512",
    )

    records = _read_records(tmp_jsonl)
    assert len(records) == 1
    r = records[0]
    assert r["provider"] == "claude"  # alias 正規化
    assert r["output_tokens"] == 512   # 從 raw_usage_text 解析


# ── Test 3: GitHub Copilot 呼叫已記錄 ────────────────────────────────────
def test_github_copilot_logged(tmp_jsonl: str) -> None:
    """provider=copilot-daemon 正規化為 github-copilot，runner=copilot_daemon → worker。"""
    from orchestrator.llm_usage_logger import log_usage

    log_usage(
        runner="copilot_daemon",
        provider="copilot-daemon",
        blocked=False,
        task_id=99,
        success=True,
        source_function="_execute_task",
    )

    records = _read_records(tmp_jsonl)
    assert len(records) == 1
    r = records[0]
    assert r["provider"] == "github-copilot"
    assert r["role"] == "worker"
    assert r["source_function"] == "_execute_task"


# ── Test 4: GitHub CLI/API 呼叫已記錄 ────────────────────────────────────
def test_github_api_logged(tmp_jsonl: str) -> None:
    """log_usage with provider='github-api' 保持不變。"""
    from orchestrator.llm_usage_logger import log_usage

    log_usage(
        runner="manual",
        provider="github-api",
        blocked=False,
        success=True,
    )
    log_usage(
        runner="manual",
        provider="gh-cli",
        blocked=False,
        success=True,
    )

    records = _read_records(tmp_jsonl)
    assert len(records) == 2
    providers = {r["provider"] for r in records}
    assert "github-api" in providers
    assert "github-cli" in providers


# ── Test 5: Planner 外部呼叫被封鎖並記錄 ─────────────────────────────────
def test_planner_blocked_and_logged(tmp_jsonl: str) -> None:
    """execution_policy.record_llm_block → log_llm_event → log_usage 寫入 blocked=True。"""
    from orchestrator.llm_usage_logger import log_usage

    log_usage(
        runner="planner",
        provider="codex",
        blocked=True,
        block_reason="ROLE_PROVIDER_VIOLATION",
        task_id=10,
    )

    records = _read_records(tmp_jsonl)
    assert len(records) == 1
    r = records[0]
    assert r["blocked"] is True
    assert r["allowed"] is False
    assert r["block_reason"] == "ROLE_PROVIDER_VIOLATION"
    assert r["role"] == "planner"


# ── Test 6: Worker 允許呼叫記錄包含完整欄位 ──────────────────────────────
def test_worker_allowed_full_schema(tmp_jsonl: str) -> None:
    """log_usage 寫出符合完整 schema 的記錄。"""
    from orchestrator.llm_usage_logger import log_usage

    log_usage(
        runner="worker_tick",
        provider="codex",
        blocked=False,
        role="worker",
        agent="codex-full-auto",
        task_id=7,
        correlation_id="corr-abc-123",
        entrypoint="post_execution",
        source_file="orchestrator/worker_tick.py",
        source_function="execute_task_with_codex",
        success=True,
        input_tokens=1000,
        output_tokens=300,
        cached_tokens=50,
        premium_requests=1,
        rate_limit=False,
    )

    records = _read_records(tmp_jsonl)
    assert len(records) == 1
    r = records[0]

    # 必要欄位存在
    for key in (
        "timestamp", "correlation_id", "role", "runner", "provider",
        "blocked", "allowed", "success", "input_tokens", "output_tokens",
        "cached_tokens", "premium_requests", "rate_limit", "source_file",
        "source_function", "entrypoint",
    ):
        assert key in r, f"Missing key: {key}"

    assert r["correlation_id"] == "corr-abc-123"
    assert r["input_tokens"] == 1000
    assert r["output_tokens"] == 300
    assert r["cached_tokens"] == 50
    assert r["premium_requests"] == 1
    assert r["rate_limit"] is False


# ── Test 7: 被封鎖時不執行子程序 ─────────────────────────────────────────
def test_blocked_does_not_call_subprocess(tmp_jsonl: str) -> None:
    """
    ProviderFactory.assert_role_allowed("planner", "codex") 應拋出 ProviderRoleViolationError，
    且 subprocess.run 不被呼叫（封鎖發生在 guard 階段，還沒進入執行）。
    """
    from orchestrator.provider_factory import ProviderFactory, ProviderRoleViolationError
    from orchestrator.llm_usage_logger import _LOG_PATH as log_path

    with patch("subprocess.run") as mock_sub:
        with pytest.raises(ProviderRoleViolationError):
            ProviderFactory.assert_role_allowed("planner", "codex", task_id=1)

        # subprocess 在 guard 階段就被封鎖，不應被呼叫
        mock_sub.assert_not_called()

    # 確認 blocked=True 記錄已寫入 JSONL
    records = _read_records(tmp_jsonl)
    blocked = [r for r in records if r.get("blocked")]
    assert len(blocked) >= 1, "應有至少一筆 blocked 記錄"
    assert blocked[-1]["role"] == "planner"


# ── Test 8: Usage card 聚合各 provider 統計 ──────────────────────────────
def test_usage_card_aggregates_providers(tmp_reader_jsonl: str) -> None:
    """build_usage_summary 正確統計各 provider 數量。"""
    from orchestrator.usage_reader import build_usage_summary

    # 寫入測試記錄
    import json as _json
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()

    records_data = [
        {"timestamp": now, "role": "worker", "runner": "worker_tick", "provider": "codex",         "blocked": False, "success": True},
        {"timestamp": now, "role": "worker", "runner": "worker_tick", "provider": "codex",         "blocked": False, "success": True},
        {"timestamp": now, "role": "worker", "runner": "worker_tick", "provider": "claude",        "blocked": False, "success": True},
        {"timestamp": now, "role": "worker", "runner": "copilot_daemon", "provider": "github-copilot", "blocked": False, "success": True},
        {"timestamp": now, "role": "planner", "runner": "planner", "provider": "codex",           "blocked": True,  "block_reason": "ROLE_PROVIDER_VIOLATION"},
        {"timestamp": now, "role": "manual", "runner": "manual", "provider": "github-api",        "blocked": False, "success": True},
    ]
    with open(tmp_reader_jsonl, "w", encoding="utf-8") as f:
        for rd in records_data:
            f.write(_json.dumps(rd) + "\n")

    summary = build_usage_summary(records_data, recent_n=5)

    assert summary["total"] == 6
    assert summary["allowed"] == 5
    assert summary["blocked"] == 1
    assert summary["by_provider"]["codex"] == 3
    assert summary["by_provider"]["claude"] == 1
    assert summary["by_provider"]["github-copilot"] == 1
    assert summary["by_provider"]["github-api"] == 1
    assert summary["block_reasons"].get("ROLE_PROVIDER_VIOLATION") == 1


# ── Test 9: Recent 表格包含 Claude / Codex / GitHub 列 ───────────────────
def test_recent_table_has_all_providers(tmp_reader_jsonl: str) -> None:
    """build_usage_summary.recent 回傳最後 N 筆，包含各 provider。"""
    from orchestrator.usage_reader import build_usage_summary
    import json as _json
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()
    rows = [
        {"timestamp": now, "role": "worker", "provider": "codex", "blocked": False},
        {"timestamp": now, "role": "worker", "provider": "claude", "blocked": False},
        {"timestamp": now, "role": "worker", "provider": "github-copilot", "blocked": False},
        {"timestamp": now, "role": "worker", "provider": "github-cli", "blocked": False},
        {"timestamp": now, "role": "manual", "provider": "github-api", "blocked": False},
    ]

    summary = build_usage_summary(rows, recent_n=10)
    recent_providers = {r["provider"] for r in summary["recent"]}
    for expected in ("codex", "claude", "github-copilot", "github-cli", "github-api"):
        assert expected in recent_providers, f"Expected provider '{expected}' in recent"


# ── Test 10: 損壞的 JSONL 行不崩潰 ───────────────────────────────────────
def test_malformed_jsonl_does_not_crash(tmp_reader_jsonl: str) -> None:
    """read_usage_records 遇到損壞 JSON 行時跳過，不拋出例外。"""
    import json as _json
    from datetime import datetime, timezone
    from orchestrator.usage_reader import read_usage_records

    now = datetime.now(timezone.utc).isoformat()
    good_record = {"timestamp": now, "role": "worker", "provider": "codex", "blocked": False}

    with open(tmp_reader_jsonl, "w", encoding="utf-8") as f:
        f.write("{this is not valid json!\n")
        f.write(_json.dumps(good_record) + "\n")
        f.write("BROKEN_LINE_NO_BRACE\n")
        f.write(_json.dumps({"timestamp": now, "provider": "claude"}) + "\n")

    # 不應拋出例外
    records = read_usage_records(hours=0)
    # 有效記錄應被讀取
    valid = [r for r in records if not r.get("_malformed")]
    assert len(valid) == 2  # good_record + claude 記錄
    # 損壞行被標記
    malformed = [r for r in records if r.get("_malformed")]
    assert len(malformed) == 2  # 2 行損壞
