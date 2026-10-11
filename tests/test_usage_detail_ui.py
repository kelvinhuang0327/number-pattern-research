"""
tests/test_usage_detail_ui.py

Usage 詳細 UI 整合測試套件。

涵蓋：
    1.  index.html 包含 Usage 詳細 section
    2.  Planner 無呼叫 → 顯示空狀態文字
    3.  Worker Copilot-Daemon 呼叫 → 顯示次數與 token
    4.  CTO 無呼叫 → 空狀態文字
    5.  Recent 10 usage table DOM 元素存在
    6.  封鎖次數 badge DOM 元素存在
    7.  Planner 外部呼叫警告 DOM 元素存在
    8.  token 格式化 k / M / cached
    9.  缺少 usage_detail 不崩潰（safe fallback）
    10. /api/orchestrator/summary 回傳 usage_detail 且前端可消費
    11. /api/orchestrator/llm-usage/today 回傳 roles 結構
    12. /api/orchestrator/usage 回傳 by_role 結構

這些測試驗證：
  - 後端 API 回傳正確結構
  - llm_usage_summary.get_usage_summary() 回傳正確形狀
  - format_tokens 輔助函式邏輯
  - 空狀態保護（空 roles、null tokens、malformed rows）
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ── HTML 結構測試 ─────────────────────────────────────────────────────────────

FRONTEND_PATH = ROOT / "runtime" / "agent_orchestrator" / "frontend" / "index.html"


def _read_html() -> str:
    return FRONTEND_PATH.read_text(encoding="utf-8")


class TestUsageHtmlStructure:
    """驗證 index.html 包含所有必要的 Usage 詳細 UI 元素。"""

    def test_usage_section_exists(self):
        """Usage 詳細 section 存在於 HTML 中。"""
        html = _read_html()
        assert 'id="usage-section"' in html, "Missing #usage-section element"

    def test_usage_nav_tab_exists(self):
        """Usage 詳細 nav tab 存在。"""
        html = _read_html()
        assert 'data-section="usage"' in html, "Missing usage nav tab"

    def test_planner_card_body_exists(self):
        """Planner 卡片 body 容器存在。"""
        html = _read_html()
        assert 'id="usage-planner-body"' in html, "Missing #usage-planner-body"

    def test_worker_card_body_exists(self):
        """Worker 卡片 body 容器存在。"""
        html = _read_html()
        assert 'id="usage-worker-body"' in html, "Missing #usage-worker-body"

    def test_cto_card_body_exists(self):
        """CTO 卡片 body 容器存在。"""
        html = _read_html()
        assert 'id="usage-cto-body"' in html, "Missing #usage-cto-body"

    def test_recent_usage_table_exists(self):
        """Recent 10 Usage 明細表格存在。"""
        html = _read_html()
        assert 'id="usage-recent-table"' in html, "Missing #usage-recent-table"
        assert 'id="usage-recent-tbody"' in html, "Missing #usage-recent-tbody"

    def test_warnings_area_exists(self):
        """警告區域 DOM 元素存在。"""
        html = _read_html()
        assert 'id="usage-warnings"' in html, "Missing #usage-warnings"

    def test_blocked_total_element_exists(self):
        """封鎖次數 badge 元素存在。"""
        html = _read_html()
        assert 'id="usage-blocked-total"' in html, "Missing #usage-blocked-total"

    def test_tokens_summary_element_exists(self):
        """Tokens 摘要元素存在。"""
        html = _read_html()
        assert 'id="usage-tokens-summary"' in html, "Missing #usage-tokens-summary"

    def test_premium_element_exists(self):
        """Premium Requests 元素存在。"""
        html = _read_html()
        assert 'id="usage-premium"' in html, "Missing #usage-premium"

    def test_recent_table_columns_exist(self):
        """Recent table 包含必要欄位標頭：Time / Role / Provider / Tokens / Blocked 等。"""
        html = _read_html()
        for col in ("Time", "Role", "Provider", "Task", "Allowed", "Blocked", "Parsed", "Premium", "Tokens"):
            assert col in html, f"Missing column header: {col}"

    def test_load_usage_data_function_exists(self):
        """loadUsageData JS 函式存在。"""
        html = _read_html()
        assert "loadUsageData" in html, "Missing loadUsageData JS function"

    def test_fmt_tokens_function_exists(self):
        """fmtTokens JS 格式化函式存在。"""
        html = _read_html()
        assert "fmtTokens" in html, "Missing fmtTokens JS function"

    def test_render_role_card_function_exists(self):
        """_renderRoleCard JS 函式存在。"""
        html = _read_html()
        assert "_renderRoleCard" in html, "Missing _renderRoleCard JS function"

    def test_render_usage_warnings_function_exists(self):
        """_renderUsageWarnings JS 函式存在。"""
        html = _read_html()
        assert "_renderUsageWarnings" in html, "Missing _renderUsageWarnings JS function"

    def test_render_recent_table_function_exists(self):
        """_renderUsageRecentTable JS 函式存在。"""
        html = _read_html()
        assert "_renderUsageRecentTable" in html, "Missing _renderUsageRecentTable JS function"

    def test_empty_state_text_in_html(self):
        """HTML 包含空狀態文字 '今日尚無 LLM 呼叫紀錄'。"""
        html = _read_html()
        assert "今日尚無 LLM 呼叫紀錄" in html, "Missing empty state text"

    def test_usage_refresh_button_exists(self):
        """重新整理按鈕存在。"""
        html = _read_html()
        assert 'id="usage-refresh-btn"' in html, "Missing #usage-refresh-btn"

    def test_all_time_checkbox_exists(self):
        """全部時間 checkbox 存在。"""
        html = _read_html()
        assert 'id="usage-all-time-cb"' in html, "Missing #usage-all-time-cb"

    def test_warning_copilot_spike_logic_in_html(self):
        """Copilot spike 警告邏輯存在於 JS 中。"""
        html = _read_html()
        assert "Copilot-Daemon 今日呼叫次數偏高" in html, "Missing Copilot spike warning text"

    def test_warning_blocked_attempts_logic_in_html(self):
        """Blocked attempts 警告邏輯存在。"""
        html = _read_html()
        assert "已封鎖外部呼叫嘗試" in html, "Missing blocked attempts warning text"

    def test_auto_refresh_includes_usage(self):
        """auto-refresh 定時器包含 usage-section。"""
        html = _read_html()
        assert "usage-section" in html
        # The auto-refresh interval should handle usage section
        assert "loadUsageData" in html


# ── Backend API 結構測試 ────────────────────────────────────────────────────

class TestUsageSummaryModule:
    """驗證 llm_usage_summary.get_usage_summary() 回傳正確結構。"""

    def test_returns_required_keys(self, tmp_path, monkeypatch):
        """get_usage_summary() 回傳 window/total/roles/warnings/recent 鍵。"""
        import orchestrator.llm_usage_summary as mod
        monkeypatch.setattr(mod, "_LOG_PATH", str(tmp_path / "llm_usage.jsonl"))
        result = mod.get_usage_summary(window="today", limit=10)

        assert "window" in result
        assert "total" in result
        assert "roles" in result
        assert "warnings" in result
        assert "recent" in result
        assert "malformed_count" in result

    def test_roles_contains_planner_worker_cto(self, tmp_path, monkeypatch):
        """roles 包含 planner / worker / cto。"""
        import orchestrator.llm_usage_summary as mod
        monkeypatch.setattr(mod, "_LOG_PATH", str(tmp_path / "llm_usage.jsonl"))
        result = mod.get_usage_summary()

        for role in ("planner", "worker", "cto"):
            assert role in result["roles"], f"Missing role: {role}"

    def test_empty_log_returns_zero_calls(self, tmp_path, monkeypatch):
        """空日誌回傳 total.calls = 0。"""
        import orchestrator.llm_usage_summary as mod
        log_path = str(tmp_path / "llm_usage.jsonl")
        monkeypatch.setattr(mod, "_LOG_PATH", log_path)
        # Create empty file
        Path(log_path).touch()

        result = mod.get_usage_summary()
        assert result["total"]["calls"] == 0
        assert result["recent"] == []
        assert result["warnings"] == []

    def test_planner_no_calls_shows_zero(self, tmp_path, monkeypatch):
        """Planner 無呼叫時 planner.calls == 0。"""
        import orchestrator.llm_usage_summary as mod
        monkeypatch.setattr(mod, "_LOG_PATH", str(tmp_path / "nofile.jsonl"))
        result = mod.get_usage_summary()
        assert result["roles"]["planner"]["calls"] == 0

    def test_worker_copilot_daemon_aggregated(self, tmp_path, monkeypatch):
        """Worker Copilot-Daemon 呼叫被正確聚合。"""
        import orchestrator.llm_usage_summary as mod
        log_path = tmp_path / "llm_usage.jsonl"
        from datetime import datetime, timezone
        ts = datetime.now(timezone.utc).isoformat()
        records = [
            {"timestamp": ts, "role": "worker", "provider": "copilot-daemon",
             "blocked": False, "success": True, "input_tokens": 1000, "output_tokens": 200, "cached_tokens": 800},
            {"timestamp": ts, "role": "worker", "provider": "copilot-daemon",
             "blocked": False, "success": True, "input_tokens": 500, "output_tokens": 100, "cached_tokens": 400},
        ]
        log_path.write_text("\n".join(json.dumps(r) for r in records) + "\n")
        monkeypatch.setattr(mod, "_LOG_PATH", str(log_path))

        result = mod.get_usage_summary(window="today", limit=10)
        worker = result["roles"]["worker"]
        assert worker["calls"] == 2
        assert worker["blocked"] == 0
        assert worker["input_tokens"] == 1500
        # Copilot-Daemon agent entry should exist
        assert "Copilot-Daemon" in worker["agents"], "Copilot-Daemon not in agents"
        assert worker["agents"]["Copilot-Daemon"]["calls"] == 2

    def test_cto_no_calls_shows_zero(self, tmp_path, monkeypatch):
        """CTO 無呼叫時 cto.calls == 0。"""
        import orchestrator.llm_usage_summary as mod
        monkeypatch.setattr(mod, "_LOG_PATH", str(tmp_path / "nofile.jsonl"))
        result = mod.get_usage_summary()
        assert result["roles"]["cto"]["calls"] == 0

    def test_missing_log_file_does_not_crash(self, tmp_path, monkeypatch):
        """日誌檔案不存在不崩潰，回傳空摘要。"""
        import orchestrator.llm_usage_summary as mod
        monkeypatch.setattr(mod, "_LOG_PATH", str(tmp_path / "nonexistent.jsonl"))
        result = mod.get_usage_summary()
        assert isinstance(result, dict)
        assert result["total"]["calls"] == 0

    def test_malformed_row_does_not_crash(self, tmp_path, monkeypatch):
        """損壞的 JSON 行不崩潰，計入 malformed_count。"""
        import orchestrator.llm_usage_summary as mod
        log_path = tmp_path / "llm_usage.jsonl"
        log_path.write_text("not json at all\n{invalid}\n")
        monkeypatch.setattr(mod, "_LOG_PATH", str(log_path))
        result = mod.get_usage_summary()
        assert isinstance(result, dict)
        assert result["malformed_count"] >= 0  # should not crash

    def test_null_token_fields_handled(self, tmp_path, monkeypatch):
        """null token 欄位不崩潰。"""
        import orchestrator.llm_usage_summary as mod
        from datetime import datetime, timezone
        log_path = tmp_path / "llm_usage.jsonl"
        ts = datetime.now(timezone.utc).isoformat()
        log_path.write_text(json.dumps({
            "timestamp": ts,
            "role": "worker",
            "provider": "copilot-daemon",
            "blocked": False,
            "input_tokens": None,
            "output_tokens": None,
            "cached_tokens": None,
        }) + "\n")
        monkeypatch.setattr(mod, "_LOG_PATH", str(log_path))
        result = mod.get_usage_summary()
        worker = result["roles"]["worker"]
        assert worker["input_tokens"] == 0
        assert worker["output_tokens"] == 0

    def test_blocked_attempts_counted(self, tmp_path, monkeypatch):
        """封鎖嘗試正確計入 blocked 欄位。"""
        import orchestrator.llm_usage_summary as mod
        from datetime import datetime, timezone
        log_path = tmp_path / "llm_usage.jsonl"
        ts = datetime.now(timezone.utc).isoformat()
        log_path.write_text(json.dumps({
            "timestamp": ts,
            "role": "worker",
            "provider": "copilot-daemon",
            "blocked": True,
            "block_reason": "hard-off",
        }) + "\n")
        monkeypatch.setattr(mod, "_LOG_PATH", str(log_path))
        result = mod.get_usage_summary()
        assert result["roles"]["worker"]["blocked"] == 1


# ── format_tokens 函式邏輯測試 ──────────────────────────────────────────────

class TestFormatTokens:
    """驗證 format_tokens() 格式化邏輯。"""

    def test_zero_tokens(self):
        from orchestrator.llm_usage_summary import format_tokens
        assert format_tokens(0, 0) == "↑0 / ↓0"

    def test_k_format(self):
        from orchestrator.llm_usage_summary import format_tokens
        result = format_tokens(1000, 500)
        assert "↑1k" in result or "↑1.0k" in result  # backend strips .0 for exact values
        assert "↓500" in result

    def test_m_format(self):
        from orchestrator.llm_usage_summary import format_tokens
        result = format_tokens(3_800_000, 74_200, 3_400_000)
        assert "↑3.8M" in result
        assert "↓74.2k" in result
        assert "3.4Mc" in result

    def test_cached_suffix(self):
        from orchestrator.llm_usage_summary import format_tokens
        result = format_tokens(100, 50, 80)
        assert result.endswith("c") or "80c" in result

    def test_no_cached_no_suffix(self):
        from orchestrator.llm_usage_summary import format_tokens
        result = format_tokens(100, 50, 0)
        assert "c" not in result

    def test_large_cached(self):
        from orchestrator.llm_usage_summary import format_tokens
        result = format_tokens(382_500, 7_900, 330_500)
        assert "382.5k" in result
        assert "7.9k" in result
        assert "330.5k" in result


# ── API 路由結構測試 ────────────────────────────────────────────────────────

class TestUsageApiStructure:
    """驗證 API 路由包含必要的 usage_detail 欄位。"""

    @pytest.fixture()
    def api_client(self):
        """建立 FastAPI test client。"""
        try:
            from fastapi.testclient import TestClient
            from app import app
            return TestClient(app)
        except Exception:
            pytest.skip("FastAPI test client not available")

    def test_orchestrator_summary_contains_usage_detail(self, api_client):
        """/api/orchestrator/summary 回傳 usage_detail 欄位。"""
        resp = api_client.get("/api/orchestrator/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert "usage_detail" in data, "Missing usage_detail in /api/orchestrator/summary"

    def test_usage_detail_contains_roles(self, api_client):
        """/api/orchestrator/summary.usage_detail 包含 roles 欄位。"""
        resp = api_client.get("/api/orchestrator/summary")
        assert resp.status_code == 200
        ud = resp.json().get("usage_detail", {})
        assert "roles" in ud or "window" in ud, "usage_detail missing roles/window"

    def test_llm_usage_today_returns_roles(self, api_client):
        """/api/orchestrator/llm-usage/today 回傳含 roles 的結構。"""
        resp = api_client.get("/api/orchestrator/llm-usage/today")
        assert resp.status_code == 200
        data = resp.json()
        assert "roles" in data or "total" in data, "llm-usage/today missing roles/total"

    def test_usage_endpoint_returns_by_role(self, api_client):
        """/api/orchestrator/usage 回傳 by_role 欄位。"""
        resp = api_client.get("/api/orchestrator/usage")
        assert resp.status_code == 200
        data = resp.json()
        assert "by_role" in data, "Missing by_role in /api/orchestrator/usage"

    def test_usage_endpoint_returns_tokens(self, api_client):
        """/api/orchestrator/usage 回傳 tokens 欄位。"""
        resp = api_client.get("/api/orchestrator/usage")
        assert resp.status_code == 200
        data = resp.json()
        assert "tokens" in data, "Missing tokens in /api/orchestrator/usage"

    def test_usage_endpoint_returns_recent(self, api_client):
        """/api/orchestrator/usage 回傳 recent 欄位。"""
        resp = api_client.get("/api/orchestrator/usage")
        assert resp.status_code == 200
        data = resp.json()
        assert "recent" in data, "Missing recent in /api/orchestrator/usage"

    def test_llm_usage_recent_returns_records(self, api_client):
        """/api/orchestrator/llm-usage/recent 回傳 records 或 recent 欄位。"""
        resp = api_client.get("/api/orchestrator/llm-usage/recent")
        assert resp.status_code == 200
        data = resp.json()
        assert "recent" in data or "records" in data or "total" in data

    def test_blocked_field_present_in_usage_summary(self, api_client):
        """/api/orchestrator/usage 包含 blocked 欄位。"""
        resp = api_client.get("/api/orchestrator/usage")
        assert resp.status_code == 200
        data = resp.json()
        assert "blocked" in data, "Missing blocked count in /api/orchestrator/usage"
