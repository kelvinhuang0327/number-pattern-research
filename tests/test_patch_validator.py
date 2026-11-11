"""
Tests for orchestrator/patch_validator.py

Coverage:
- _compute_metrics(): Brier, LogLoss, Accuracy, ROI, CLV
- _regime_breakdown(): per-regime grouping
- _decide(): KEEP / REJECT / PARTIAL decision logic
- _detect_stub_completion(): stub worker detection
- run_patch_validation(): end-to-end flow (mocked DB + FS)
- insight state transitions
"""
from __future__ import annotations

import json
import math
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from orchestrator import patch_validator


# ─── fixtures ────────────────────────────────────────────────────────────────

def _settlement(
    game_id: str,
    predicted_prob: float,
    result: str,
    regime: str = "Pool A",
    pnl: float = 0.0,
    clv: float | None = None,
) -> dict:
    return {
        "event_type": "settlement",
        "game_id": game_id,
        "predicted_prob": predicted_prob,
        "market_prob": 0.5,
        "result": result,
        "regime": regime,
        "pnl": pnl,
        "roi": pnl,
        "clv": clv,
    }


def _make_records(n: int, predicted_prob: float = 0.6, win_rate: float = 0.6) -> list[dict]:
    """Generate n synthetic settlement records."""
    records = []
    for i in range(n):
        result = "win" if (i / n) < win_rate else "loss"
        records.append(_settlement(f"G{i:03d}", predicted_prob, result))
    return records


def _make_patch_task(stub: bool = True, task_id: int = 880) -> dict:
    return {
        "id": task_id,
        "title": "MLB Calibration Patch: Test",
        "signal_state_type": "model_patch_calibration",
        "status": "COMPLETED",
        "completed_text": "程式碼自動生成\n智能建議整合\n- 測試案例產生" if stub else "# Real patch completed",
    }


def _make_insight(ins_id: str = "abc12345") -> dict:
    return {
        "id": ins_id,
        "source_signal_state_type": "deep_research_calibration",
        "category": "calibration",
        "weakness": "Brier score baseline not quantified",
        "evidence_files": ["data/wbc_backend/reports/mlb_decision_quality_report.json"],
        "target_files": [
            "wbc_backend/research/mlb_model_rebuild.py",
            "wbc_backend/evaluation/mlb_decision_quality.py",
        ],
        "expected_metric": "小 regime Brier score 改善 >= 2%",
        "priority": 1,
        "status": "PATCH_QUEUED",
        "patch_task_id": 880,
    }


# ─── unit: _compute_metrics ──────────────────────────────────────────────────

def test_compute_metrics_brier_perfect():
    """Perfect prediction (prob=1, win) → Brier = 0."""
    records = [_settlement("G1", 1.0, "win")]
    m = patch_validator._compute_metrics(records)
    assert m["brier_score"] == 0.0
    assert m["accuracy"] == 1.0


def test_compute_metrics_brier_worst():
    """Worst prediction (prob=1, loss) → Brier = 1."""
    records = [_settlement("G1", 1.0, "loss")]
    m = patch_validator._compute_metrics(records)
    assert m["brier_score"] == pytest.approx(1.0)
    assert m["accuracy"] == 0.0


def test_compute_metrics_brier_formula():
    """Brier score manual check: (0.7-1)^2 = 0.09"""
    records = [_settlement("G1", 0.7, "win")]
    m = patch_validator._compute_metrics(records)
    assert m["brier_score"] == pytest.approx(0.09, abs=1e-5)


def test_compute_metrics_logloss_bounded():
    """LogLoss should be positive and finite for valid probs."""
    records = _make_records(50, 0.6, 0.6)
    m = patch_validator._compute_metrics(records)
    assert m["log_loss"] > 0
    assert math.isfinite(m["log_loss"])


def test_compute_metrics_roi():
    """Avg ROI computed as mean of pnl fields."""
    records = [
        _settlement("G1", 0.6, "win", pnl=0.10),
        _settlement("G2", 0.6, "loss", pnl=-0.05),
    ]
    m = patch_validator._compute_metrics(records)
    assert m["avg_roi"] == pytest.approx(0.025)


def test_compute_metrics_clv_aggregation():
    """CLV average computed only over records with non-null CLV."""
    records = [
        _settlement("G1", 0.6, "win", clv=0.04),
        _settlement("G2", 0.6, "loss", clv=0.02),
        _settlement("G3", 0.6, "win"),           # clv=None
    ]
    m = patch_validator._compute_metrics(records)
    assert m["avg_clv"] == pytest.approx(0.03)
    assert m["clv_available"] == 2


def test_compute_metrics_empty_returns_nulls():
    m = patch_validator._compute_metrics([])
    assert m["brier_score"] is None
    assert m["n"] == 0


# ─── unit: _regime_breakdown ─────────────────────────────────────────────────

def test_regime_breakdown_groups_correctly():
    records = [
        _settlement("G1", 0.7, "win",  regime="Pool A"),
        _settlement("G2", 0.6, "loss", regime="Pool B"),
        _settlement("G3", 0.8, "win",  regime="Pool A"),
    ]
    breakdown = patch_validator._regime_breakdown(records)
    assert "Pool A" in breakdown
    assert "Pool B" in breakdown
    assert breakdown["Pool A"]["n"] == 2
    assert breakdown["Pool B"]["n"] == 1


def test_regime_breakdown_empty_input():
    assert patch_validator._regime_breakdown([]) == {}


# ─── unit: _decide ───────────────────────────────────────────────────────────

def test_decide_keep_when_brier_improves():
    before = {"brier_score": 0.25, "log_loss": 0.6}
    after  = {"brier_score": 0.24, "log_loss": 0.58}  # >0.5% relative improve
    d = patch_validator._decide(before, after, n=200, risk_notes=[])
    assert d == "KEEP_PATCH"


def test_decide_reject_when_no_improvement():
    before = {"brier_score": 0.25, "log_loss": 0.6}
    after  = {"brier_score": 0.2499, "log_loss": 0.5999}  # <0.5% improve → noise
    d = patch_validator._decide(before, after, n=200, risk_notes=[])
    assert d == "REJECT_PATCH"


def test_decide_reject_when_regression():
    before = {"brier_score": 0.25, "log_loss": 0.6}
    after  = {"brier_score": 0.27, "log_loss": 0.65}   # worse
    d = patch_validator._decide(before, after, n=200, risk_notes=[])
    assert d == "REJECT_PATCH"


def test_decide_partial_when_small_sample():
    before = {"brier_score": 0.25, "log_loss": 0.6}
    after  = {"brier_score": 0.23, "log_loss": 0.58}
    d = patch_validator._decide(before, after, n=50, risk_notes=[])
    assert d == "PARTIAL_KEEP"


def test_decide_insufficient_when_no_metrics():
    d = patch_validator._decide({}, {}, n=0, risk_notes=[])
    assert d == "INSUFFICIENT_DATA"


# ─── unit: _detect_stub_completion ───────────────────────────────────────────

def test_detect_stub_returns_true_for_copilot_daemon():
    task = {"completed_text": "程式碼自動生成\ncopilot-daemon\n智能建議整合\n- 測試案例產生"}
    assert patch_validator._detect_stub_completion(task) is True


def test_detect_stub_returns_false_for_real_output():
    task = {"completed_text": "# Calibration patch\nActually updated wbc_backend/research/mlb_model_rebuild.py"}
    assert patch_validator._detect_stub_completion(task) is False


def test_detect_stub_handles_missing_text():
    assert patch_validator._detect_stub_completion({}) is False


# ─── unit: find_insight_for_patch ────────────────────────────────────────────

def test_find_insight_for_patch_matches_category(tmp_path, monkeypatch):
    insights = [
        {"id": "aa1", "source_signal_state_type": "deep_research_calibration", "status": "PATCH_QUEUED"},
        {"id": "bb2", "source_signal_state_type": "deep_research_feature", "status": "PENDING"},
    ]
    fake_path = tmp_path / "insights.json"
    fake_path.write_text(json.dumps(insights))
    monkeypatch.setattr(patch_validator, "INSIGHTS_PATH", fake_path)

    patch_task = {"signal_state_type": "model_patch_calibration"}
    result = patch_validator.find_insight_for_patch(patch_task)
    assert result is not None
    assert result["id"] == "aa1"


def test_find_insight_returns_none_when_no_match(tmp_path, monkeypatch):
    insights = [{"id": "aa1", "source_signal_state_type": "deep_research_feature", "status": "PENDING"}]
    fake_path = tmp_path / "insights.json"
    fake_path.write_text(json.dumps(insights))
    monkeypatch.setattr(patch_validator, "INSIGHTS_PATH", fake_path)

    patch_task = {"signal_state_type": "model_patch_calibration"}
    result = patch_validator.find_insight_for_patch(patch_task)
    assert result is None


# ─── integration: run_patch_validation ───────────────────────────────────────

def test_run_patch_validation_stub_worker_returns_insufficient(tmp_path, monkeypatch):
    """Stub worker → INSUFFICIENT_DATA, no fake improvement reported."""
    fake_insights = tmp_path / "insights.json"
    fake_insights.write_text(json.dumps([_make_insight()]))
    monkeypatch.setattr(patch_validator, "INSIGHTS_PATH", fake_insights)
    monkeypatch.setattr(patch_validator, "REPORT_OUTPUT_PATH", tmp_path / "report.md")
    # No real snapshots on disk for this test — isolate from production artifacts
    monkeypatch.setattr(patch_validator, "SNAPSHOTS_DIR", tmp_path / "empty_snapshots")

    # Patch trade_ledger with 35 real-ish records
    fake_ledger = tmp_path / "trade_ledger.jsonl"
    fake_ledger.write_text(
        "\n".join(json.dumps(_settlement(f"G{i}", 0.6, "win" if i % 2 == 0 else "loss")) for i in range(35))
    )
    monkeypatch.setattr(patch_validator, "TRADE_LEDGER_PATH", fake_ledger)

    result = patch_validator.run_patch_validation(_make_patch_task(stub=True), _make_insight())
    assert result["decision"] == "INSUFFICIENT_DATA"
    assert result["before_metrics"]["brier_score"] is not None
    assert result["after_metrics"].get("note") == "stub_worker_no_real_change"
    assert (tmp_path / "report.md").exists()


def test_run_patch_validation_insufficient_when_no_data(tmp_path, monkeypatch):
    """No trade ledger → INSUFFICIENT_DATA."""
    fake_insights = tmp_path / "insights.json"
    fake_insights.write_text(json.dumps([_make_insight()]))
    monkeypatch.setattr(patch_validator, "INSIGHTS_PATH", fake_insights)
    monkeypatch.setattr(patch_validator, "REPORT_OUTPUT_PATH", tmp_path / "report.md")
    monkeypatch.setattr(patch_validator, "TRADE_LEDGER_PATH", tmp_path / "nonexistent.jsonl")
    # No real snapshots on disk for this test — isolate from production artifacts
    monkeypatch.setattr(patch_validator, "SNAPSHOTS_DIR", tmp_path / "empty_snapshots")

    result = patch_validator.run_patch_validation(
        _make_patch_task(stub=False), _make_insight()
    )
    assert result["decision"] == "INSUFFICIENT_DATA"
    assert result["sample_size"] == 0


def test_run_patch_validation_insight_marked_partial(tmp_path, monkeypatch):
    """INSUFFICIENT_DATA → insight status → PARTIAL."""
    ins = _make_insight("xyz99")
    fake_insights = tmp_path / "insights.json"
    fake_insights.write_text(json.dumps([ins]))
    monkeypatch.setattr(patch_validator, "INSIGHTS_PATH", fake_insights)
    monkeypatch.setattr(patch_validator, "REPORT_OUTPUT_PATH", tmp_path / "report.md")
    monkeypatch.setattr(patch_validator, "TRADE_LEDGER_PATH", tmp_path / "nonexistent.jsonl")

    patch_validator.run_patch_validation(_make_patch_task(stub=False), ins)

    updated = json.loads(fake_insights.read_text())
    assert updated[0]["status"] == "PARTIAL"


def test_run_patch_validation_blocks_live_target(tmp_path, monkeypatch):
    """Insight targeting strategy/ must produce risk_note."""
    bad_insight = _make_insight()
    bad_insight["target_files"] = ["strategy/kelly.py"]
    fake_insights = tmp_path / "insights.json"
    fake_insights.write_text(json.dumps([bad_insight]))
    monkeypatch.setattr(patch_validator, "INSIGHTS_PATH", fake_insights)
    monkeypatch.setattr(patch_validator, "REPORT_OUTPUT_PATH", tmp_path / "report.md")
    monkeypatch.setattr(patch_validator, "TRADE_LEDGER_PATH", tmp_path / "nonexistent.jsonl")

    result = patch_validator.run_patch_validation(_make_patch_task(), bad_insight)
    assert any("BLOCKED" in note for note in result["risk_notes"])


def test_report_file_contains_decision(tmp_path, monkeypatch):
    """Generated report markdown must mention the decision."""
    fake_insights = tmp_path / "insights.json"
    fake_insights.write_text(json.dumps([_make_insight()]))
    monkeypatch.setattr(patch_validator, "INSIGHTS_PATH", fake_insights)
    report_path = tmp_path / "report.md"
    monkeypatch.setattr(patch_validator, "REPORT_OUTPUT_PATH", report_path)
    monkeypatch.setattr(patch_validator, "TRADE_LEDGER_PATH", tmp_path / "nonexistent.jsonl")

    result = patch_validator.run_patch_validation(_make_patch_task(), _make_insight())
    content = report_path.read_text()
    assert result["decision"] in content
    assert "BEFORE vs AFTER" in content
    assert "Regime" in content
