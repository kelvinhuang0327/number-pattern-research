from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from orchestrator import db
from orchestrator.insight_extractor import AUDIT_TO_INSIGHT
from orchestrator.planner_tick import TASK_BLUEPRINTS, create_sample_task, run_planner_tick
from orchestrator.task_quality_gate import build_task_dedupe_key, evaluate_task_quality


def _reset_runtime_db() -> None:
    db.init_db()
    conn = db.get_conn()
    try:
        conn.execute("DELETE FROM agent_task_runs")
        conn.execute("DELETE FROM agent_tasks")
        conn.commit()
    finally:
        conn.close()


@pytest.fixture(autouse=True)
def isolate_db(monkeypatch):
    """Ensure each test starts and ends with a clean DB so test tasks don't pollute production."""
    _reset_runtime_db()
    orig_sched = db.get_setting("scheduler_enabled", "1")
    orig_llm_mode = db.get_setting("llm_execution_mode", "safe-run")
    db.set_setting("scheduler_enabled", "1")
    db.set_setting("llm_execution_mode", "safe-run")
    # Neutralize usage budget guard so quality gate tests reach REJECTED/SUCCESS paths
    monkeypatch.setattr(
        "orchestrator.usage_budget_guard.evaluate_usage_budget",
        lambda **_kw: {"budget_status": "OK", "scheduler_mode": "NORMAL"},
        raising=False,
    )
    # Isolate candidate generators from production state (patch/hrq/clv candidates)
    monkeypatch.setattr("orchestrator.patch_task_generator.generate_patch_tasks", lambda *_a, **_k: [], raising=False)
    monkeypatch.setattr("orchestrator.human_review_queue.get_approved_reviews", lambda *_a, **_k: [], raising=False)
    monkeypatch.setattr("orchestrator.human_review_queue.get_more_data_reviews", lambda *_a, **_k: [], raising=False)
    monkeypatch.setattr("orchestrator.human_review_queue.get_pending_reviews", lambda *_a, **_k: [], raising=False)
    monkeypatch.setattr("orchestrator.clv_accumulation_policy.get_clv_accumulation_summary", lambda *_a, **_k: {"evidence_state": "SUFFICIENT", "computed_count": 100, "threshold": 50}, raising=False)
    monkeypatch.setattr("orchestrator.clv_batch_scheduler.get_batch_scheduler_summary", lambda *_a, **_k: {"scheduler_due": False, "needs_clv_generation": 0, "pending_total": 0}, raising=False)
    monkeypatch.setattr("orchestrator.clv_threshold_tracker.get_pending_threshold_events", lambda *_a, **_k: [], raising=False)
    monkeypatch.setattr("orchestrator.training_memory.get_latest_gate_decision", lambda *_a, **_k: None, raising=False)
    # Block forced_exploration from pre-empting quality gate test candidates
    monkeypatch.setattr("orchestrator.planner_tick._attempt_forced_exploration", lambda *_a, **_k: {"status": "SKIP_ALL_LANES_CAPPED", "capped_lanes": []}, raising=False)
    monkeypatch.setattr("orchestrator.planner_tick._attempt_maintenance_task", lambda *_a, **_k: {"status": "SKIP_DAILY_CAP", "task_id": None}, raising=False)
    monkeypatch.setattr("orchestrator.planner_tick.process_completed_exploration_tasks", lambda *_a, **_k: {"validation_created": 0, "validation_task_ids": []}, raising=False)
    yield
    _reset_runtime_db()
    db.set_setting("scheduler_enabled", orig_sched)
    db.set_setting("llm_execution_mode", orig_llm_mode)


def _build_valid_task_draft() -> dict:
    prompt_text = """# 任務：Walk-forward split boundary validation

## 單一目標
驗證 walk-forward split 邊界是否正確隔離訓練與測試集。

## 執行步驟
1. 檢查 split 定義與時間序是否一致。
2. 統計 overlap / lookahead 違規樣本數。
3. 輸出 machine-readable JSON。

## 必要輸出
```json
{
  "violations": [],
  "metrics": {
    "baseline": {},
    "candidate": {},
    "delta": {}
  },
  "regime_counts": {},
  "leakage_detected": false,
  "candidate_fix": []
}
```
"""
    contract_json = json.dumps(
        {
            "max_compute_hours": 2,
            "max_major_objectives": 2,
            "max_dataset_count": 2,
            "task_kind": "audit",
            "deliverable_kind": "violation_count",
            "required_output_fields": [
                "violations",
                "metrics",
                "regime_counts",
                "leakage_detected",
                "candidate_fix",
            ],
            "signal_state_type": "deep_research_backtest_validity",
            "dataset_paths": [
                "wbc_backend/evaluation/real_backtest.py",
                "data/wbc_backend/reports/mlb_regime_paper_report.json",
            ],
            "major_objectives": ["驗證 walk-forward split 邊界"],
        },
        ensure_ascii=False,
    )
    return {
        "slot_key": "20260423-pass-task",
        "date_folder": "20260423",
        "title": "MLB Walk-Forward Split Boundary Validation",
        "slug": "20260423-pass-task",
        "prompt_text": prompt_text,
        "prompt_file_path": "",
        "focus_area": "mlb-walkforward-split-boundary",
        "market_scope": "MLB paper-only backtest",
        "analysis_family": "backtest-validity-atomic",
        "signal_state_type": "deep_research_backtest_validity",
        "task_kind": "audit",
        "deliverable_kind": "violation_count",
        "expected_duration_hours": 2,
        "dataset_paths": [
            "wbc_backend/evaluation/real_backtest.py",
            "data/wbc_backend/reports/mlb_regime_paper_report.json",
        ],
        "major_objectives": ["驗證 walk-forward split 邊界"],
        "contract_json": contract_json,
    }


def test_quality_gate_rejects_short_task_without_creating_task(monkeypatch) -> None:
    short_task = {
        "slot_key": "20260423-short-task",
        "date_folder": "20260423",
        "title": "更新 MLB 2025 歷史數據回測報告",
        "slug": "20260423-short-task",
        "prompt_text": "# 任務\n\n更新 MLB 2025 歷史數據回測報告。",
        "prompt_file_path": "",
        "focus_area": "test-short",
        "market_scope": "test",
        "analysis_family": "test",
    }
    # Patch all candidate sources to only return the short task
    monkeypatch.setattr("orchestrator.planner_tick.TASK_BLUEPRINTS", (short_task,))
    monkeypatch.setattr("orchestrator.planner_tick._mine_tasks_from_wiki", lambda: [])

    result = run_planner_tick()

    assert result["status"] == "REJECTED"
    assert result["quality_status"] == "REJECT"
    assert db.get_latest_task() == {}


def test_quality_gate_allows_valid_atomic_task(monkeypatch) -> None:
    valid_task = _build_valid_task_draft()
    valid_task["focus_area"] = "wbc-strategy-test"
    valid_task["market_scope"] = "WBC test"
    valid_task["analysis_family"] = "multi-strategy-test"
    # Patch all candidate sources to only return the valid task
    monkeypatch.setattr("orchestrator.planner_tick.TASK_BLUEPRINTS", (valid_task,))
    monkeypatch.setattr("orchestrator.planner_tick._mine_tasks_from_wiki", lambda: [])

    result = run_planner_tick()

    assert result["status"] == "SUCCESS"
    assert result["quality_status"] == "PASS"

    latest_task = db.get_latest_task()
    assert latest_task["title"] == valid_task["title"]
    assert latest_task["prompt_file_path"]


def test_quality_gate_rejects_duplicate_focus() -> None:
    existing_task = _build_valid_task_draft()
    existing_task["dedupe_key"] = build_task_dedupe_key(existing_task)
    verdict = evaluate_task_quality(existing_task, recent_tasks=[existing_task])

    assert verdict.quality_status == "REJECT"
    assert any("重複性檢查" in reason for reason in verdict.rejection_reasons)


def test_planner_sample_task_is_atomic_ready() -> None:
    task_draft = create_sample_task()
    verdict = evaluate_task_quality(task_draft, recent_tasks=[])

    assert verdict.quality_status == "PASS"
    assert task_draft["dedupe_key"].startswith("quality-gate:")
    assert task_draft["expected_duration_hours"] <= 2


def test_quality_gate_rejects_mixed_audit_simulation_and_recommendation() -> None:
    invalid_task = _build_valid_task_draft()
    invalid_task["task_kind"] = "audit"
    invalid_task["deliverable_kind"] = "metric_delta"
    invalid_task["prompt_text"] += "\n\n請執行 Monte Carlo 模擬，並在同一任務給最終推薦方案。"
    invalid_task["contract_json"] = json.dumps(
        {
            **json.loads(invalid_task["contract_json"]),
            "task_kind": "audit",
            "deliverable_kind": "metric_delta",
        },
        ensure_ascii=False,
    )

    verdict = evaluate_task_quality(invalid_task, recent_tasks=[])

    assert verdict.quality_status == "REJECT"
    assert any("Monte Carlo 隔離" in reason or "最終推薦" in reason for reason in verdict.rejection_reasons)


def test_backtest_family_is_decomposed_into_five_atomic_tasks() -> None:
    titles = [task["title"] for task in TASK_BLUEPRINTS if task["analysis_family"] == "backtest-validity-atomic"]

    assert len(titles) == 5
    assert "MLB Walk-Forward Split Boundary Validation" in titles
    assert "MLB Feature Window Leakage Audit" in titles
    assert "MLB Regime Sample Sufficiency Analysis" in titles
    assert "Monte Carlo Leakage Sensitivity" in titles
    assert "Leakage Fix Proposal" in titles


def test_all_blueprints_remain_loop_compatible() -> None:
    for task in TASK_BLUEPRINTS:
        assert task["signal_state_type"] in AUDIT_TO_INSIGHT
        assert task["deliverable_kind"] in {"insight", "metric_delta", "violation_count", "candidate_patch"}


def test_quality_gate_rejects_generic_task_titles(monkeypatch) -> None:
    """Task 5 rule: generic tasks without measurable metrics must be rejected."""
    base = _build_valid_task_draft()
    # Inject a generic forbidden phrase into the prompt so the gate catches it.
    generic_task = {
        **base,
        "slot_key": "20260424-generic-task",
        "title": "Improve MLB model performance",
        "prompt_text": base["prompt_text"] + "\n\nObjective: improve mlb model accuracy generally.",
        "focus_area": "mlb-generic",
        "market_scope": "MLB",
        "analysis_family": "generic-research",
    }
    monkeypatch.setattr("orchestrator.planner_tick.TASK_BLUEPRINTS", (generic_task,))
    monkeypatch.setattr("orchestrator.planner_tick._mine_tasks_from_wiki", lambda: [])

    result = run_planner_tick()

    assert result["status"] == "REJECTED"
    assert result["quality_status"] == "REJECT"
    assert db.get_latest_task() == {}


def test_planner_skips_when_all_candidates_blocked_by_recent_duplicate(monkeypatch) -> None:
    valid_task = _build_valid_task_draft()
    valid_task["focus_area"] = "wbc-strategy-test"
    valid_task["market_scope"] = "WBC test"
    valid_task["analysis_family"] = "multi-strategy-test"

    recent_duplicate = {
        "title": valid_task["title"],
        "prompt_text": valid_task["prompt_text"],
        "focus_area": valid_task["focus_area"],
        "analysis_family": valid_task["analysis_family"],
        "status": "QUEUED",
    }

    monkeypatch.setattr("orchestrator.planner_tick.TASK_BLUEPRINTS", (valid_task,))
    monkeypatch.setattr("orchestrator.planner_tick._mine_tasks_from_wiki", lambda: [])
    monkeypatch.setattr("orchestrator.db.list_tasks", lambda *args, **kwargs: [recent_duplicate])

    result = run_planner_tick()

    assert result["status"] == "SKIPPED"
    assert result["quality_status"] == "SKIP"
    assert "duplicate gate" in result["message"]
    assert result["blocked_by_recent"] == 1
    assert result["blocked_by_duplicate"] == 0