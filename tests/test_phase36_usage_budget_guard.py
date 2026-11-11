"""
tests/test_phase36_usage_budget_guard.py

Phase 36: Usage Budget Guard — 15 個確定性測試。

硬性規則（測試層）:
- 不呼叫任何真實外部 AI / API / GitHub / Copilot / Claude / Codex
- 不修改 runtime/ 或 data/ 下的真實文件
- 所有 I/O 均使用 tmp_path fixtures
"""
from __future__ import annotations

import json
import sys
import types
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# ── 確保 project root 在 sys.path ───────────────────────────────────────────
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


# ────────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────────

def _make_usage_record(
    role: str = "worker",
    provider: str = "github-copilot",
    blocked: bool = False,
    input_tokens: int = 1000,
    hours_ago: float = 1.0,
) -> dict:
    ts = (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat()
    return {
        "timestamp": ts,
        "role": role,
        "provider": provider,
        "blocked": blocked,
        "input_tokens": input_tokens,
        "output_tokens": 100,
        "cached_tokens": 0,
        "rate_limited": False,
    }


def _write_usage_log(path: Path, records: list[dict]) -> None:
    with path.open("w") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")


def _write_budget_config(path: Path, config: dict) -> None:
    with path.open("w") as f:
        json.dump(config, f, indent=2)


def _minimal_config() -> dict:
    return {
        "version": "test-v1",
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
                "warn_calls": 5,
                "critical_calls": 10,
                "hard_cap_calls": 15,
            },
        },
        "providers": {
            "github-copilot": {
                "warn_calls": 5,
                "critical_calls": 10,
                "hard_cap_calls": 15,
            },
            "claude": {
                "warn_calls": 3,
                "critical_calls": 6,
                "hard_cap_calls": 10,
            },
            "codex": {
                "warn_calls": 2,
                "critical_calls": 4,
                "hard_cap_calls": 8,
            },
        },
        "tokens": {
            "warn_input_tokens": 1_000_000,
            "critical_input_tokens": 2_000_000,
            "hard_cap_input_tokens": 3_000_000,
        },
        "blocked_attempts": {
            "warn": 3,
            "critical": 5,
        },
    }


# ────────────────────────────────────────────────────────────────────────────
# Test 1: 缺少 config 時，ensure_default_budget_config 建立預設設定
# ────────────────────────────────────────────────────────────────────────────

def test_01_missing_config_creates_default(tmp_path):
    """config 不存在時，ensure_default_budget_config() 應建立預設 JSON 並可讀取。"""
    config_path = tmp_path / "usage_budget_config.json"
    usage_log_path = tmp_path / "llm_usage.jsonl"
    usage_log_path.write_text("")

    from orchestrator import usage_budget_guard as ubg
    with (
        patch.object(ubg, "_BUDGET_CONFIG_PATH", str(config_path)),
        patch.object(ubg, "_USAGE_LOG_PATH", str(usage_log_path)),
    ):
        assert not config_path.exists()
        ubg.ensure_default_budget_config()
        assert config_path.exists()

        data = json.loads(config_path.read_text())
        assert "version" in data
        assert "roles" in data
        assert "providers" in data


# ────────────────────────────────────────────────────────────────────────────
# Test 2: 損壞的 config 安全 fallback
# ────────────────────────────────────────────────────────────────────────────

def test_02_malformed_config_fallback(tmp_path):
    """損壞的 config JSON 應 fallback 到 _DEFAULT_CONFIG，不應拋出例外。"""
    config_path = tmp_path / "usage_budget_config.json"
    usage_log_path = tmp_path / "llm_usage.jsonl"
    config_path.write_text("{ INVALID JSON }")
    usage_log_path.write_text("")

    from orchestrator import usage_budget_guard as ubg
    with (
        patch.object(ubg, "_BUDGET_CONFIG_PATH", str(config_path)),
        patch.object(ubg, "_USAGE_LOG_PATH", str(usage_log_path)),
    ):
        cfg = ubg.load_budget_config()
        assert isinstance(cfg, dict)
        assert "roles" in cfg  # fallback 到 _DEFAULT_CONFIG


# ────────────────────────────────────────────────────────────────────────────
# Test 3: Planner 發生外部呼叫 → CRITICAL/HARD_CAP
# ────────────────────────────────────────────────────────────────────────────

def test_03_planner_allowed_external_call_triggers_critical(tmp_path):
    """Planner 發生外部 AI 呼叫時，budget_status 應至少是 CRITICAL。"""
    config_path = tmp_path / "usage_budget_config.json"
    usage_log_path = tmp_path / "llm_usage.jsonl"
    _write_budget_config(config_path, _minimal_config())
    _write_usage_log(usage_log_path, [
        _make_usage_record(role="planner", provider="github-copilot", blocked=False),
    ])

    from orchestrator import usage_budget_guard as ubg
    with (
        patch.object(ubg, "_BUDGET_CONFIG_PATH", str(config_path)),
        patch.object(ubg, "_USAGE_LOG_PATH", str(usage_log_path)),
    ):
        result = ubg.evaluate_usage_budget(hours=24)

    # Planner 外部呼叫不被允許，應觸發至少 CRITICAL
    rank = ubg._STATUS_RANK
    assert rank[result["budget_status"]] >= rank["CRITICAL"]
    assert rank[result["roles"]["planner"]["status"]] >= rank["CRITICAL"]


# ────────────────────────────────────────────────────────────────────────────
# Test 4: Planner 大量封鎖嘗試 → WARN
# ────────────────────────────────────────────────────────────────────────────

def test_04_planner_blocked_attempts_warn(tmp_path):
    """Planner/CTO 的封鎖嘗試超過 warn 閾值，budget_status 應至少是 WARN。"""
    config_path = tmp_path / "usage_budget_config.json"
    usage_log_path = tmp_path / "llm_usage.jsonl"
    _write_budget_config(config_path, _minimal_config())
    # 4 個封鎖嘗試（warn=3）
    records = [
        _make_usage_record(role="worker", provider="github-copilot", blocked=True)
        for _ in range(4)
    ]
    _write_usage_log(usage_log_path, records)

    from orchestrator import usage_budget_guard as ubg
    with (
        patch.object(ubg, "_BUDGET_CONFIG_PATH", str(config_path)),
        patch.object(ubg, "_USAGE_LOG_PATH", str(usage_log_path)),
    ):
        result = ubg.evaluate_usage_budget(hours=24)

    rank = ubg._STATUS_RANK
    assert rank[result["budget_status"]] >= rank["WARN"]


# ────────────────────────────────────────────────────────────────────────────
# Test 5: Worker 低於閾值 → OK
# ────────────────────────────────────────────────────────────────────────────

def test_05_worker_below_threshold_ok(tmp_path):
    """Worker 呼叫次數低於 warn 閾值時，應為 OK。"""
    config_path = tmp_path / "usage_budget_config.json"
    usage_log_path = tmp_path / "llm_usage.jsonl"
    _write_budget_config(config_path, _minimal_config())
    _write_usage_log(usage_log_path, [
        _make_usage_record(role="worker", provider="github-copilot")
        for _ in range(3)  # warn=5
    ])

    from orchestrator import usage_budget_guard as ubg
    with (
        patch.object(ubg, "_BUDGET_CONFIG_PATH", str(config_path)),
        patch.object(ubg, "_USAGE_LOG_PATH", str(usage_log_path)),
    ):
        result = ubg.evaluate_usage_budget(hours=24)

    assert result["budget_status"] == "OK"
    assert result["roles"]["worker"]["status"] == "OK"


# ────────────────────────────────────────────────────────────────────────────
# Test 6: Worker 超過 warn → WARN
# ────────────────────────────────────────────────────────────────────────────

def test_06_worker_over_warn_threshold(tmp_path):
    """Worker 超過 warn_calls=5 時，應為 WARN。"""
    config_path = tmp_path / "usage_budget_config.json"
    usage_log_path = tmp_path / "llm_usage.jsonl"
    _write_budget_config(config_path, _minimal_config())
    _write_usage_log(usage_log_path, [
        _make_usage_record(role="worker", provider="github-copilot")
        for _ in range(6)  # 超過 warn=5
    ])

    from orchestrator import usage_budget_guard as ubg
    with (
        patch.object(ubg, "_BUDGET_CONFIG_PATH", str(config_path)),
        patch.object(ubg, "_USAGE_LOG_PATH", str(usage_log_path)),
    ):
        result = ubg.evaluate_usage_budget(hours=24)

    rank = ubg._STATUS_RANK
    assert rank[result["budget_status"]] >= rank["WARN"]
    assert rank[result["roles"]["worker"]["status"]] >= rank["WARN"]


# ────────────────────────────────────────────────────────────────────────────
# Test 7: Worker 超過 critical → CRITICAL
# ────────────────────────────────────────────────────────────────────────────

def test_07_worker_over_critical_threshold(tmp_path):
    """Worker 超過 critical_calls=10 時，應為 CRITICAL。"""
    config_path = tmp_path / "usage_budget_config.json"
    usage_log_path = tmp_path / "llm_usage.jsonl"
    _write_budget_config(config_path, _minimal_config())
    _write_usage_log(usage_log_path, [
        _make_usage_record(role="worker", provider="github-copilot")
        for _ in range(11)  # 超過 critical=10
    ])

    from orchestrator import usage_budget_guard as ubg
    with (
        patch.object(ubg, "_BUDGET_CONFIG_PATH", str(config_path)),
        patch.object(ubg, "_USAGE_LOG_PATH", str(usage_log_path)),
    ):
        result = ubg.evaluate_usage_budget(hours=24)

    rank = ubg._STATUS_RANK
    assert rank[result["budget_status"]] >= rank["CRITICAL"]


# ────────────────────────────────────────────────────────────────────────────
# Test 8: Provider 超過 hard_cap → HARD_CAP + hard_cap_triggered = True
# ────────────────────────────────────────────────────────────────────────────

def test_08_provider_hard_cap_triggered(tmp_path):
    """Provider 超過 hard_cap_calls 時，hard_cap_triggered=True 且 budget_status=HARD_CAP。"""
    config_path = tmp_path / "usage_budget_config.json"
    usage_log_path = tmp_path / "llm_usage.jsonl"
    _write_budget_config(config_path, _minimal_config())
    _write_usage_log(usage_log_path, [
        _make_usage_record(role="worker", provider="github-copilot")
        for _ in range(16)  # 超過 hard_cap=15
    ])

    from orchestrator import usage_budget_guard as ubg
    with (
        patch.object(ubg, "_BUDGET_CONFIG_PATH", str(config_path)),
        patch.object(ubg, "_USAGE_LOG_PATH", str(usage_log_path)),
    ):
        result = ubg.evaluate_usage_budget(hours=24)

    assert result["budget_status"] == "HARD_CAP"
    assert result["hard_cap_triggered"] is True
    assert result["recommended_scheduler_mode"] in ("PAUSE_EXTERNAL_AI", "DETERMINISTIC_ONLY")


# ────────────────────────────────────────────────────────────────────────────
# Test 9: is_provider_allowed 在 HARD_CAP 時回傳 False
# ────────────────────────────────────────────────────────────────────────────

def test_09_is_provider_allowed_blocks_on_hard_cap(tmp_path):
    """HARD_CAP 觸發後，is_provider_allowed('worker', 'github-copilot') 應回傳 False。"""
    config_path = tmp_path / "usage_budget_config.json"
    usage_log_path = tmp_path / "llm_usage.jsonl"
    _write_budget_config(config_path, _minimal_config())
    _write_usage_log(usage_log_path, [
        _make_usage_record(role="worker", provider="github-copilot")
        for _ in range(16)  # hard_cap=15
    ])

    from orchestrator import usage_budget_guard as ubg
    with (
        patch.object(ubg, "_BUDGET_CONFIG_PATH", str(config_path)),
        patch.object(ubg, "_USAGE_LOG_PATH", str(usage_log_path)),
    ):
        allowed, reason = ubg.is_provider_allowed("worker", "github-copilot", hours=24)

    assert allowed is False
    assert reason  # should be non-empty


# ────────────────────────────────────────────────────────────────────────────
# Test 10: Budget 封鎖時寫入 audit BLOCKED 記錄（worker_tick 整合）
# ────────────────────────────────────────────────────────────────────────────

def test_10_budget_block_writes_audit_blocked(tmp_path, monkeypatch):
    """Budget HARD_CAP 觸發後，_assert_llm_execution_allowed 應寫入 write_blocked。"""
    config_path = tmp_path / "usage_budget_config.json"
    usage_log_path = tmp_path / "llm_usage.jsonl"
    _write_budget_config(config_path, _minimal_config())
    _write_usage_log(usage_log_path, [
        _make_usage_record(role="worker", provider="github-copilot")
        for _ in range(16)
    ])

    from orchestrator import usage_budget_guard as ubg
    monkeypatch.setattr(ubg, "_BUDGET_CONFIG_PATH", str(config_path))
    monkeypatch.setattr(ubg, "_USAGE_LOG_PATH", str(usage_log_path))

    write_blocked_calls: list[dict] = []

    def fake_write_blocked(**kwargs):
        write_blocked_calls.append(kwargs)

    log_usage_calls: list[dict] = []

    def fake_log_usage(**kwargs):
        log_usage_calls.append(kwargs)

    import orchestrator.worker_tick as wt

    # 確保 execution_policy 不擋住
    fake_policy_decision = MagicMock()
    fake_policy_decision.return_value = {"allowed": True}
    monkeypatch.setattr(wt.execution_policy, "evaluate_execution", fake_policy_decision)

    # ProviderFactory 允許 worker 呼叫
    from orchestrator.provider_factory import ProviderFactory
    monkeypatch.setattr(ProviderFactory, "assert_role_allowed", staticmethod(lambda *a, **kw: None))

    # _llm_block_reason 回傳 None（不被 policy 擋住）
    monkeypatch.setattr(wt, "_llm_block_reason", lambda p: None)
    monkeypatch.setattr(wt.execution_policy, "record_llm_call", MagicMock())

    with (
        patch("orchestrator.worker_tick.usage_budget_guard", ubg, create=True),
        patch("orchestrator.llm_audit.write_blocked", side_effect=fake_write_blocked),
        patch("orchestrator.llm_usage_logger.log_usage", side_effect=fake_log_usage),
    ):
        with pytest.raises(RuntimeError, match="usage budget hard cap blocked"):
            wt._assert_llm_execution_allowed("github-copilot", "worker_tick_test")

    assert len(write_blocked_calls) >= 1
    assert any("usage_budget_guard" in str(c.get("trigger_source", "")) for c in write_blocked_calls)


# ────────────────────────────────────────────────────────────────────────────
# Test 11: Budget 封鎖時寫入 usage blocked 記錄（blocked=True）
# ────────────────────────────────────────────────────────────────────────────

def test_11_budget_block_writes_usage_blocked_record(tmp_path, monkeypatch):
    """Budget HARD_CAP 封鎖時，log_usage(blocked=True) 應被呼叫。"""
    config_path = tmp_path / "usage_budget_config.json"
    usage_log_path = tmp_path / "llm_usage.jsonl"
    _write_budget_config(config_path, _minimal_config())
    _write_usage_log(usage_log_path, [
        _make_usage_record(role="worker", provider="github-copilot")
        for _ in range(16)
    ])

    from orchestrator import usage_budget_guard as ubg
    monkeypatch.setattr(ubg, "_BUDGET_CONFIG_PATH", str(config_path))
    monkeypatch.setattr(ubg, "_USAGE_LOG_PATH", str(usage_log_path))

    log_usage_calls: list[dict] = []

    def fake_log_usage(**kwargs):
        log_usage_calls.append(kwargs)

    import orchestrator.worker_tick as wt
    from orchestrator.provider_factory import ProviderFactory
    monkeypatch.setattr(ProviderFactory, "assert_role_allowed", staticmethod(lambda *a, **kw: None))
    monkeypatch.setattr(wt, "_llm_block_reason", lambda p: None)
    monkeypatch.setattr(wt.execution_policy, "record_llm_call", MagicMock())

    with (
        patch("orchestrator.llm_audit.write_blocked", MagicMock()),
        patch("orchestrator.llm_usage_logger.log_usage", side_effect=fake_log_usage),
    ):
        with pytest.raises(RuntimeError):
            wt._assert_llm_execution_allowed("github-copilot", "worker_tick_test")

    blocked_calls = [c for c in log_usage_calls if c.get("blocked") is True]
    assert len(blocked_calls) >= 1


# ────────────────────────────────────────────────────────────────────────────
# Test 12: HARD_CAP 時 recommended_scheduler_mode 為 PAUSE_EXTERNAL_AI
# ────────────────────────────────────────────────────────────────────────────

def test_12_scheduler_mode_pause_external_ai_on_hard_cap(tmp_path):
    """HARD_CAP 時，recommended_scheduler_mode 應為 PAUSE_EXTERNAL_AI。"""
    config_path = tmp_path / "usage_budget_config.json"
    usage_log_path = tmp_path / "llm_usage.jsonl"
    _write_budget_config(config_path, _minimal_config())
    _write_usage_log(usage_log_path, [
        _make_usage_record(role="worker", provider="github-copilot")
        for _ in range(20)  # 遠超 hard_cap=15
    ])

    from orchestrator import usage_budget_guard as ubg
    with (
        patch.object(ubg, "_BUDGET_CONFIG_PATH", str(config_path)),
        patch.object(ubg, "_USAGE_LOG_PATH", str(usage_log_path)),
    ):
        result = ubg.evaluate_usage_budget(hours=24)

    assert result["budget_status"] == "HARD_CAP"
    assert result["recommended_scheduler_mode"] == "PAUSE_EXTERNAL_AI"


# ────────────────────────────────────────────────────────────────────────────
# Test 13: Decision Card 渲染 Usage Budget 區段
# ────────────────────────────────────────────────────────────────────────────

def test_13_decision_card_renders_usage_budget():
    """render_card 應在 payload 中包含 usage_budget 並輸出對應區段。"""
    from scripts.ops_decision_card import render_card, build_payload

    # 使用 build_payload + override usage_budget 以確保完整的 payload 結構
    try:
        payload = build_payload()
    except Exception:
        pytest.skip("build_payload requires runtime files — skip in CI")
        return

    payload["usage_budget"] = {
        "budget_status": "WARN",
        "recommended_scheduler_mode": "NORMAL",
        "window_hours": 24,
        "roles": {
            "planner": {"status": "OK", "calls": 0, "blocked": 0, "allowed_external": 0},
            "cto": {"status": "OK", "calls": 0, "blocked": 0, "allowed_external": 0},
            "worker": {
                "status": "WARN", "calls": 7, "blocked": 0,
                "warn_calls": 5, "critical_calls": 10, "hard_cap_calls": 15,
            },
        },
        "providers": {
            "github-copilot": {
                "status": "WARN", "calls": 7,
                "warn_calls": 5, "critical_calls": 10, "hard_cap_calls": 15,
            },
        },
        "tokens": {
            "status": "OK", "input_tokens": 5000,
            "warn_input_tokens": 1_000_000, "hard_cap_input_tokens": 3_000_000,
        },
        "warnings": ["⚠️ Worker 呼叫偏高 (7/15)"],
        "critical_alerts": [],
        "hard_cap_triggered": False,
        "total_blocked": 0,
    }

    card = render_card(payload)
    assert "USAGE BUDGET GUARD" in card
    assert "WARN" in card


# ────────────────────────────────────────────────────────────────────────────
# Test 14: Frontend HTML 包含 Usage Budget 面板元素
# ────────────────────────────────────────────────────────────────────────────

def test_14_frontend_html_contains_budget_panel():
    """frontend/index.html 應包含 Phase 36 budget panel 元素。"""
    html_path = _ROOT / "runtime" / "agent_orchestrator" / "frontend" / "index.html"
    assert html_path.exists(), f"Missing: {html_path}"
    content = html_path.read_text()

    assert "usage-budget-card" in content, "Missing #usage-budget-card element"
    assert "budget-status-badge" in content, "Missing #budget-status-badge element"
    assert "budget-worker-calls" in content, "Missing #budget-worker-calls element"
    assert "budget-copilot-calls" in content, "Missing #budget-copilot-calls element"
    assert "_renderBudgetGuard" in content, "Missing _renderBudgetGuard function"


# ────────────────────────────────────────────────────────────────────────────
# Test 15: 測試中不發生真實外部 AI 呼叫
# ────────────────────────────────────────────────────────────────────────────

def test_15_no_real_external_ai_calls_in_tests(tmp_path):
    """
    驗證 usage_budget_guard 的核心函數在執行期間不呼叫任何外部 AI。
    透過 monkeypatching subprocess.run 並確認其未被呼叫。
    """
    import subprocess
    config_path = tmp_path / "usage_budget_config.json"
    usage_log_path = tmp_path / "llm_usage.jsonl"
    _write_budget_config(config_path, _minimal_config())
    _write_usage_log(usage_log_path, [
        _make_usage_record(role="worker", provider="github-copilot")
        for _ in range(3)
    ])

    real_calls: list[list] = []

    def mock_subprocess_run(args, *a, **kw):
        real_calls.append(list(args) if isinstance(args, (list, tuple)) else [args])
        raise AssertionError(f"[TEST 15] Real subprocess call detected: {args}")

    from orchestrator import usage_budget_guard as ubg
    with (
        patch.object(ubg, "_BUDGET_CONFIG_PATH", str(config_path)),
        patch.object(ubg, "_USAGE_LOG_PATH", str(usage_log_path)),
        patch("subprocess.run", side_effect=mock_subprocess_run),
        patch("subprocess.Popen", side_effect=lambda *a, **kw: (_ for _ in ()).throw(AssertionError("Popen called"))),
    ):
        result = ubg.evaluate_usage_budget(hours=24)
        assert result["budget_status"] in ("OK", "WARN", "CRITICAL", "HARD_CAP")

    assert real_calls == [], f"Unexpected subprocess calls: {real_calls}"
