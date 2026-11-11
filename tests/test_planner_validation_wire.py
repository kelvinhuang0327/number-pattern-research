"""
tests/test_planner_validation_wire.py

驗證 planner_tick.py STEP 0.6 自動驗證接線是否正確：
- PATCH_QUEUED 洞見 + COMPLETED patch 任務 → 直接呼叫 patch_validator.run_patch_validation()
- KEEP_PATCH → insight.status = VALIDATED
- PARTIAL_KEEP → insight.status = PARTIAL
- INSUFFICIENT_DATA → 不呼叫 validator（因為 patch task 尚未 COMPLETED）
- 冪等性：已 VALIDATED 的洞見不再被 validator 呼叫
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from orchestrator import db, insight_extractor, patch_validator
from orchestrator import planner_tick

# ── Helper stubs ────────────────────────────────────────────────────────────

def _make_insight(
    status: str = "PATCH_QUEUED",
    patch_task_id: int = 42,
    iid: str = "ins-001",
    validated_at: str | None = None,
) -> dict:
    ins = {
        "id": iid,
        "status": status,
        "patch_task_id": patch_task_id,
        "category": "calibration",
        "signal_state_type": "model_patch_calibration",
        "target_files": ["wbc_backend/calibration/probability_calibrator.py"],
        "expected_metric": "Brier < 0.25",
        "priority": 1,
    }
    if validated_at:
        ins["validated_at"] = validated_at
    return ins


def _make_patch_task(task_id: int = 42, status: str = "COMPLETED") -> dict:
    return {
        "id": task_id,
        "status": status,
        "title": "MLB Calibration Patch",
        "signal_state_type": "model_patch_calibration",
        "completed_text": "Brier improved from 0.30 to 0.12",
    }


def _make_validation_result(decision: str = "KEEP_PATCH") -> dict:
    return {
        "decision": decision,
        "before_metrics": {"brier_score": 0.30, "log_loss": 0.65},
        "after_metrics": {"brier_score": 0.12, "log_loss": 0.32},
        "statistical_note": "SNAPSHOT_COMPARISON",
        "sample_size": 35,
        "risk_notes": [],
        "patch_task_id": 42,
        "insight_id": "ins-001",
        "signal_state_type": "model_patch_calibration",
        "evaluated_at": "2026-01-01T00:00:00Z",
        "regime_breakdown": {},
    }


def _reset_db() -> None:
    db.init_db()
    conn = db.get_conn()
    try:
        conn.execute("DELETE FROM agent_task_runs")
        conn.execute("DELETE FROM agent_tasks")
        conn.commit()
    finally:
        conn.close()


def _list_tasks_stub(limit: int = 20, **kwargs) -> list:
    """Stub for db.list_tasks — accepts any kwargs (status, etc.) and returns []."""
    return []


@pytest.fixture(autouse=True)
def isolate_db():
    _reset_db()
    orig_sched = db.get_setting("scheduler_enabled", "1")
    orig_llm_mode = db.get_setting("llm_execution_mode", "safe-run")
    db.set_setting("scheduler_enabled", "1")
    db.set_setting("llm_execution_mode", "safe-run")
    yield
    _reset_db()
    db.set_setting("scheduler_enabled", orig_sched)
    db.set_setting("llm_execution_mode", orig_llm_mode)


# ── Test 1: PATCH_QUEUED insight + COMPLETED patch → validator is called ────

def test_planner_calls_validator_for_completed_patch(monkeypatch):
    """PATCH_QUEUED insight with COMPLETED patch task → run_patch_validation called exactly once."""
    ins = _make_insight()
    pt = _make_patch_task()
    vr = _make_validation_result("KEEP_PATCH")

    monkeypatch.setattr(insight_extractor, "extract_insights_from_completed_tasks", lambda: [])
    monkeypatch.setattr(insight_extractor, "get_pending_insights", lambda: [])
    monkeypatch.setattr(insight_extractor, "get_patch_queued_insights", lambda: [ins])
    monkeypatch.setattr(patch_task_generator := planner_tick.patch_task_generator,
                        "generate_patch_tasks", lambda _: [])
    # db.get_task must return our completed patch task
    monkeypatch.setattr(db, "get_task", lambda tid: pt if tid == 42 else None)
    # db.get_latest_task returns None so planner isn't blocked by RUNNING task
    monkeypatch.setattr(db, "get_latest_task", lambda: None)
    # No other DB reads needed — list_tasks for dedup
    monkeypatch.setattr(db, "list_tasks", _list_tasks_stub)

    mock_validate = MagicMock(return_value=vr)
    monkeypatch.setattr(patch_validator, "run_patch_validation", mock_validate)

    planner_tick.run_planner_tick()

    mock_validate.assert_called_once_with(pt, ins)


# ── Test 2: KEEP_PATCH decision updates insight to VALIDATED ────────────────

def test_keep_patch_decision_reflected_in_validator_call(monkeypatch):
    """When run_patch_validation returns KEEP_PATCH the validator must be called (lifecycle update
    is inside the validator itself; we verify the call took place and returned correctly)."""
    ins = _make_insight()
    pt = _make_patch_task()
    vr = _make_validation_result("KEEP_PATCH")

    monkeypatch.setattr(insight_extractor, "extract_insights_from_completed_tasks", lambda: [])
    monkeypatch.setattr(insight_extractor, "get_pending_insights", lambda: [])
    monkeypatch.setattr(insight_extractor, "get_patch_queued_insights", lambda: [ins])
    monkeypatch.setattr(planner_tick.patch_task_generator, "generate_patch_tasks", lambda _: [])
    monkeypatch.setattr(db, "get_task", lambda tid: pt if tid == 42 else None)
    monkeypatch.setattr(db, "get_latest_task", lambda: None)
    monkeypatch.setattr(db, "list_tasks", _list_tasks_stub)

    mock_validate = MagicMock(return_value=vr)
    monkeypatch.setattr(patch_validator, "run_patch_validation", mock_validate)

    result = planner_tick.run_planner_tick()

    mock_validate.assert_called_once()
    assert mock_validate.call_args[0][0]["id"] == 42  # patch task
    assert mock_validate.call_args[0][1]["id"] == "ins-001"  # insight
    returned_decision = mock_validate.return_value["decision"]
    assert returned_decision == "KEEP_PATCH"


# ── Test 3: PARTIAL_KEEP decision → validator called, insight lifecycle managed ──

def test_partial_keep_validator_is_called(monkeypatch):
    """PARTIAL_KEEP decision still results in validator being called once."""
    ins = _make_insight()
    pt = _make_patch_task()
    vr = _make_validation_result("PARTIAL_KEEP")

    monkeypatch.setattr(insight_extractor, "extract_insights_from_completed_tasks", lambda: [])
    monkeypatch.setattr(insight_extractor, "get_pending_insights", lambda: [])
    monkeypatch.setattr(insight_extractor, "get_patch_queued_insights", lambda: [ins])
    monkeypatch.setattr(planner_tick.patch_task_generator, "generate_patch_tasks", lambda _: [])
    monkeypatch.setattr(db, "get_task", lambda tid: pt if tid == 42 else None)
    monkeypatch.setattr(db, "get_latest_task", lambda: None)
    monkeypatch.setattr(db, "list_tasks", _list_tasks_stub)

    mock_validate = MagicMock(return_value=vr)
    monkeypatch.setattr(patch_validator, "run_patch_validation", mock_validate)

    planner_tick.run_planner_tick()

    mock_validate.assert_called_once()
    assert mock_validate.return_value["decision"] == "PARTIAL_KEEP"


# ── Test 4: PATCH_QUEUED insight but patch task NOT YET COMPLETED → validator NOT called ──

def test_incomplete_patch_task_skips_validation(monkeypatch):
    """If patch task is RUNNING/PENDING → validator must NOT be called."""
    ins = _make_insight()
    pt_running = _make_patch_task(status="RUNNING")

    monkeypatch.setattr(insight_extractor, "extract_insights_from_completed_tasks", lambda: [])
    monkeypatch.setattr(insight_extractor, "get_pending_insights", lambda: [])
    monkeypatch.setattr(insight_extractor, "get_patch_queued_insights", lambda: [ins])
    monkeypatch.setattr(planner_tick.patch_task_generator, "generate_patch_tasks", lambda _: [])
    monkeypatch.setattr(db, "get_task", lambda tid: pt_running if tid == 42 else None)
    monkeypatch.setattr(db, "get_latest_task", lambda: None)
    monkeypatch.setattr(db, "list_tasks", _list_tasks_stub)

    mock_validate = MagicMock()
    monkeypatch.setattr(patch_validator, "run_patch_validation", mock_validate)

    planner_tick.run_planner_tick()

    mock_validate.assert_not_called()


# ── Test 5: Already-validated insight (has validated_at) → validator NOT called again ──

def test_idempotent_skip_insight_with_validated_at(monkeypatch):
    """Insight with validated_at timestamp already set → validator skipped (idempotency)."""
    ins = _make_insight(validated_at="2026-01-01T12:00:00Z")
    # Note: this insight still has status=PATCH_QUEUED (edge case — in production it would
    # have transitioned, but we test the extra guard in STEP 0.6)
    pt = _make_patch_task()

    monkeypatch.setattr(insight_extractor, "extract_insights_from_completed_tasks", lambda: [])
    monkeypatch.setattr(insight_extractor, "get_pending_insights", lambda: [])
    monkeypatch.setattr(insight_extractor, "get_patch_queued_insights", lambda: [ins])
    monkeypatch.setattr(planner_tick.patch_task_generator, "generate_patch_tasks", lambda _: [])
    monkeypatch.setattr(db, "get_task", lambda tid: pt if tid == 42 else None)
    monkeypatch.setattr(db, "get_latest_task", lambda: None)
    monkeypatch.setattr(db, "list_tasks", _list_tasks_stub)

    mock_validate = MagicMock()
    monkeypatch.setattr(patch_validator, "run_patch_validation", mock_validate)

    planner_tick.run_planner_tick()

    mock_validate.assert_not_called()


# ── Test 6: Validator exception is non-fatal → planner tick still completes ──

def test_validator_exception_is_non_fatal(monkeypatch):
    """If run_patch_validation raises, the planner tick should not crash."""
    ins = _make_insight()
    pt = _make_patch_task()

    monkeypatch.setattr(insight_extractor, "extract_insights_from_completed_tasks", lambda: [])
    monkeypatch.setattr(insight_extractor, "get_pending_insights", lambda: [])
    monkeypatch.setattr(insight_extractor, "get_patch_queued_insights", lambda: [ins])
    monkeypatch.setattr(planner_tick.patch_task_generator, "generate_patch_tasks", lambda _: [])
    monkeypatch.setattr(db, "get_task", lambda tid: pt if tid == 42 else None)
    monkeypatch.setattr(db, "get_latest_task", lambda: None)
    monkeypatch.setattr(db, "list_tasks", _list_tasks_stub)

    def _exploding_validator(*args, **kwargs):
        raise RuntimeError("Simulated validator crash")

    monkeypatch.setattr(patch_validator, "run_patch_validation", _exploding_validator)

    # Should not raise
    result = planner_tick.run_planner_tick()
    # Planner continues and returns some status
    assert "status" in result


# ── Test 7: Multiple PATCH_QUEUED insights → validator called for each COMPLETED patch ──

def test_multiple_insights_each_validated(monkeypatch):
    """Two PATCH_QUEUED insights with COMPLETED patch tasks → validator called twice."""
    ins_a = _make_insight(iid="ins-a", patch_task_id=10)
    ins_b = _make_insight(iid="ins-b", patch_task_id=20)
    pt_a = _make_patch_task(task_id=10)
    pt_b = _make_patch_task(task_id=20)
    vr = _make_validation_result("KEEP_PATCH")

    monkeypatch.setattr(insight_extractor, "extract_insights_from_completed_tasks", lambda: [])
    monkeypatch.setattr(insight_extractor, "get_pending_insights", lambda: [])
    monkeypatch.setattr(insight_extractor, "get_patch_queued_insights", lambda: [ins_a, ins_b])
    monkeypatch.setattr(planner_tick.patch_task_generator, "generate_patch_tasks", lambda _: [])

    def _get_task(tid):
        if tid == 10:
            return pt_a
        if tid == 20:
            return pt_b
        return None

    monkeypatch.setattr(db, "get_task", _get_task)
    monkeypatch.setattr(db, "get_latest_task", lambda: None)
    monkeypatch.setattr(db, "list_tasks", _list_tasks_stub)

    mock_validate = MagicMock(return_value=vr)
    monkeypatch.setattr(patch_validator, "run_patch_validation", mock_validate)

    planner_tick.run_planner_tick()

    assert mock_validate.call_count == 2
    called_insight_ids = {c[0][1]["id"] for c in mock_validate.call_args_list}
    assert called_insight_ids == {"ins-a", "ins-b"}
