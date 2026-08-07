"""
tests/test_usage_detail_card.py

Usage 詳細卡片 — 8 個單元測試。

測試原則：
- 完全使用 tmp_path fixture，不依賴實際 llm_usage.jsonl
- Monkeypatch llm_usage_summary._LOG_PATH 指向臨時檔案
- 不呼叫外部 API / LLM / subprocess
"""
from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

import orchestrator.llm_usage_summary as _mod
from orchestrator.llm_usage_summary import format_tokens, get_usage_summary


# ── Fixtures ──────────────────────────────────────────────────────────────

def _write_jsonl(path: Path, records: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _now_iso(offset_minutes: int = 0) -> str:
    ts = datetime.now(timezone.utc) - timedelta(minutes=offset_minutes)
    return ts.isoformat()


# ── Test 1: 空 log → Planner/CTO 顯示「無呼叫紀錄」───────────────────────

def test_empty_log_no_calls(tmp_path, monkeypatch):
    """空的 JSONL 檔案 → 所有 role calls 皆為 0。"""
    log_file = tmp_path / "llm_usage.jsonl"
    log_file.write_text("")
    monkeypatch.setattr(_mod, "_LOG_PATH", str(log_file))

    summary = get_usage_summary(window="today")

    assert summary["total"]["calls"] == 0
    assert summary["roles"]["planner"]["calls"] == 0
    assert summary["roles"]["cto"]["calls"] == 0
    assert summary["roles"]["worker"]["calls"] == 0
    assert summary["recent"] == []
    assert summary["warnings"] == []


# ── Test 2: Worker token 累計正確 ─────────────────────────────────────────

def test_worker_token_aggregation(tmp_path, monkeypatch):
    """Worker 的多筆記錄應正確累計 token 總量。"""
    log_file = tmp_path / "llm_usage.jsonl"
    records = [
        {
            "timestamp": _now_iso(10),
            "role": "worker",
            "provider": "github-copilot",
            "blocked": False,
            "input_tokens": 100_000,
            "output_tokens": 5_000,
            "cached_tokens": 80_000,
            "premium_requests": 1,
            "success": True,
        },
        {
            "timestamp": _now_iso(5),
            "role": "worker",
            "provider": "github-copilot",
            "blocked": False,
            "input_tokens": 200_000,
            "output_tokens": 3_000,
            "cached_tokens": 150_000,
            "premium_requests": 2,
            "success": True,
        },
    ]
    _write_jsonl(log_file, records)
    monkeypatch.setattr(_mod, "_LOG_PATH", str(log_file))

    summary = get_usage_summary(window="today")
    w = summary["roles"]["worker"]

    assert w["calls"] == 2
    assert w["input_tokens"] == 300_000
    assert w["output_tokens"] == 8_000
    assert w["cached_tokens"] == 230_000
    assert w["premium_requests"] == 3


# ── Test 3: Per-agent 累計正確 ────────────────────────────────────────────

def test_per_agent_aggregation(tmp_path, monkeypatch):
    """同一 role 下不同 provider 應分別累計到 agents 子字典。"""
    log_file = tmp_path / "llm_usage.jsonl"
    records = [
        {
            "timestamp": _now_iso(10),
            "role": "worker",
            "provider": "github-copilot",
            "blocked": False,
            "input_tokens": 50_000,
            "output_tokens": 1_000,
            "cached_tokens": 0,
            "success": True,
        },
        {
            "timestamp": _now_iso(5),
            "role": "worker",
            "provider": "codex",
            "blocked": False,
            "input_tokens": 20_000,
            "output_tokens": 500,
            "cached_tokens": 0,
            "success": True,
        },
        {
            "timestamp": _now_iso(2),
            "role": "worker",
            "provider": "github-copilot",
            "blocked": False,
            "input_tokens": 10_000,
            "output_tokens": 200,
            "cached_tokens": 0,
            "success": True,
        },
    ]
    _write_jsonl(log_file, records)
    monkeypatch.setattr(_mod, "_LOG_PATH", str(log_file))

    summary = get_usage_summary(window="today")
    agents = summary["roles"]["worker"]["agents"]

    assert "Copilot-Daemon" in agents
    assert "Codex" in agents
    assert agents["Copilot-Daemon"]["calls"] == 2
    assert agents["Copilot-Daemon"]["input_tokens"] == 60_000
    assert agents["Codex"]["calls"] == 1
    assert agents["Codex"]["input_tokens"] == 20_000


# ── Test 4: Recent 最新在前，數量限制正確 ────────────────────────────────

def test_recent_sorted_newest_first(tmp_path, monkeypatch):
    """recent 列表應為最新在前，且受 limit 參數限制。"""
    log_file = tmp_path / "llm_usage.jsonl"
    records = [
        {
            "timestamp": _now_iso(offset),
            "role": "worker",
            "provider": "github-copilot",
            "blocked": False,
            "task_id": offset,
            "input_tokens": 0,
            "output_tokens": 0,
            "success": True,
        }
        for offset in range(15, 0, -1)  # 15 筆，最舊的先寫
    ]
    _write_jsonl(log_file, records)
    monkeypatch.setattr(_mod, "_LOG_PATH", str(log_file))

    summary = get_usage_summary(window="today", limit=10)
    recent = summary["recent"]

    # 只取 10 筆
    assert len(recent) == 10
    # 最新的 task_id=1（offset 最小，時間最新）
    assert recent[0]["task_id"] == 1


# ── Test 5: Token 格式化 k / M ───────────────────────────────────────────

def test_format_tokens_k_and_M():
    """format_tokens 應正確輸出 k/M 格式。"""
    # 小數字
    assert format_tokens(0, 0) == "↑0 / ↓0"
    # k 範圍
    assert format_tokens(1_000, 500) == "↑1k / ↓500"
    assert format_tokens(382_500, 7_900, 330_500) == "↑382.5k / ↓7.9k / 330.5kc"
    # M 範圍
    assert format_tokens(3_800_000, 74_200, 3_400_000) == "↑3.8M / ↓74.2k / 3.4Mc"
    # 無 cached
    result = format_tokens(1_000, 500, 0)
    assert "c" not in result


# ── Test 6: 損壞行不崩潰 ─────────────────────────────────────────────────

def test_malformed_rows_do_not_crash(tmp_path, monkeypatch):
    """JSONL 中有損壞行時，應被跳過並計入 malformed_count。"""
    log_file = tmp_path / "llm_usage.jsonl"
    log_file.write_text(
        '{"timestamp": "' + _now_iso(5) + '", "role": "worker", "provider": "codex", "blocked": false}\n'
        "THIS IS NOT JSON\n"
        "{broken json{\n"
        '{"timestamp": "' + _now_iso(1) + '", "role": "worker", "provider": "codex", "blocked": false}\n'
    )
    monkeypatch.setattr(_mod, "_LOG_PATH", str(log_file))

    summary = get_usage_summary(window="today")

    assert summary["malformed_count"] == 2
    assert summary["roles"]["worker"]["calls"] == 2  # 有效的 2 筆


# ── Test 7: Planner 有外部呼叫 → 顯示告警 ───────────────────────────────

def test_planner_external_usage_warning(tmp_path, monkeypatch):
    """Planner 有未被封鎖的外部 LLM 呼叫時，warnings 應包含 Provider Safety 告警。"""
    log_file = tmp_path / "llm_usage.jsonl"
    records = [
        {
            "timestamp": _now_iso(5),
            "role": "planner",
            "provider": "claude",
            "blocked": False,  # 未被封鎖 → 異常
            "input_tokens": 1_000,
            "output_tokens": 100,
            "success": True,
        },
    ]
    _write_jsonl(log_file, records)
    monkeypatch.setattr(_mod, "_LOG_PATH", str(log_file))

    summary = get_usage_summary(window="today")

    assert any("PLANNER" in w or "planner" in w.lower() for w in summary["warnings"])
    assert any("Provider Safety" in w or "外部" in w for w in summary["warnings"])


# ── Test 8: Decision Card 包含 Usage 詳細區塊 ────────────────────────────

def test_decision_card_contains_usage_section(tmp_path, monkeypatch):
    """render_card 應在 JSONL 有資料時輸出 'USAGE 詳細' 區塊標題。"""
    import sys
    import os
    # 確保 ROOT 在 path
    ROOT = Path(__file__).resolve().parents[1]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    log_file = tmp_path / "llm_usage.jsonl"
    records = [
        {
            "timestamp": _now_iso(5),
            "role": "worker",
            "provider": "github-copilot",
            "blocked": False,
            "input_tokens": 382_500,
            "output_tokens": 7_900,
            "cached_tokens": 330_500,
            "task_id": 380,
            "success": True,
        },
    ]
    _write_jsonl(log_file, records)
    monkeypatch.setattr(_mod, "_LOG_PATH", str(log_file))

    from scripts.ops_decision_card import build_payload, render_card

    # monkeypatch compute_llm_usage_detail 使用測試 log
    import scripts.ops_decision_card as card_mod

    def _patched_compute(*args, **kwargs):
        return get_usage_summary(window="today", limit=10)

    monkeypatch.setattr(card_mod, "compute_llm_usage_detail", _patched_compute)

    payload = build_payload()
    card_text = render_card(payload)

    assert "USAGE 詳細" in card_text or "🤖 USAGE" in card_text
    assert "WORKER" in card_text
    assert "Copilot-Daemon" in card_text
    assert "382.5k" in card_text
