"""
Tests for orchestrator/insight_extractor.py
Coverage: extraction idempotency, priority sorting, lifecycle transitions.
"""
from __future__ import annotations

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from orchestrator import insight_extractor


# ─── helpers ────────────────────────────────────────────────────────────────

def _make_completed_task(signal_state_type: str, task_id: int = 1) -> dict:
    return {
        "id": task_id,
        "title": f"Test audit for {signal_state_type}",
        "signal_state_type": signal_state_type,
        "analysis_family": "mlb-accuracy-research",
        "status": "COMPLETED",
    }


# ─── fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def temp_insights_path(tmp_path, monkeypatch):
    """Redirect insights.json to a temp directory for test isolation."""
    fake_path = tmp_path / "insights.json"
    monkeypatch.setattr(insight_extractor, "INSIGHTS_PATH", fake_path)
    yield fake_path


# ─── tests ──────────────────────────────────────────────────────────────────

def test_extract_emits_insight_for_completed_audit():
    """Completed audit task with known signal_state_type should produce one PENDING insight."""
    task = _make_completed_task("deep_research_calibration", task_id=42)

    with patch.object(insight_extractor.db, "list_tasks", return_value=[task]):
        new = insight_extractor.extract_insights_from_completed_tasks()

    assert len(new) == 1
    ins = new[0]
    assert ins["category"] == "calibration"
    assert ins["status"] == "PENDING"
    assert ins["source_task_id"] == 42
    assert ins["priority"] == 1  # calibration is priority 1


def test_extract_is_idempotent_for_same_signal_state_type():
    """Same signal_state_type already PENDING → should not emit a second insight."""
    task = _make_completed_task("deep_research_backtest_validity", task_id=99)

    with patch.object(insight_extractor.db, "list_tasks", return_value=[task]):
        first = insight_extractor.extract_insights_from_completed_tasks()
        second = insight_extractor.extract_insights_from_completed_tasks()

    assert len(first) == 1
    assert len(second) == 0, "Duplicate insight emitted for same active signal_state_type"


def test_extract_ignores_unknown_signal_state_type():
    """A completed task with an unknown signal_state_type should be silently ignored."""
    task = _make_completed_task("mlb-some-unrelated-task", task_id=7)

    with patch.object(insight_extractor.db, "list_tasks", return_value=[task]):
        new = insight_extractor.extract_insights_from_completed_tasks()

    assert new == []


def test_get_pending_insights_sorted_by_priority():
    """get_pending_insights() should return lowest priority-number first."""
    tasks = [
        _make_completed_task("deep_research_calibration", task_id=1),   # priority 1
        _make_completed_task("deep_research_feedback", task_id=2),      # priority 3
        _make_completed_task("deep_research_backtest_validity", task_id=3),  # priority 1
    ]
    with patch.object(insight_extractor.db, "list_tasks", return_value=tasks):
        insight_extractor.extract_insights_from_completed_tasks()

    pending = insight_extractor.get_pending_insights()
    priorities = [ins["priority"] for ins in pending]
    assert priorities == sorted(priorities), "Insights not sorted by priority"
    assert priorities[0] == 1


def test_mark_insight_patch_queued_transitions_state():
    """mark_insight_patch_queued() should flip status to PATCH_QUEUED and record patch_task_id."""
    task = _make_completed_task("deep_research_regime", task_id=10)
    with patch.object(insight_extractor.db, "list_tasks", return_value=[task]):
        new = insight_extractor.extract_insights_from_completed_tasks()

    ins = new[0]
    insight_extractor.mark_insight_patch_queued(ins["id"], patch_task_id=500)

    loaded = insight_extractor._load_insights()
    updated = next(i for i in loaded if i["id"] == ins["id"])
    assert updated["status"] == "PATCH_QUEUED"
    assert updated["patch_task_id"] == 500


def test_mark_insight_validated_transitions_state():
    """mark_insight_validated() should flip status to VALIDATED and record validation_task_id."""
    task = _make_completed_task("deep_research_odds_quality", task_id=20)
    with patch.object(insight_extractor.db, "list_tasks", return_value=[task]):
        new = insight_extractor.extract_insights_from_completed_tasks()

    ins = new[0]
    insight_extractor.mark_insight_validated(ins["id"], validation_task_id=999)

    loaded = insight_extractor._load_insights()
    updated = next(i for i in loaded if i["id"] == ins["id"])
    assert updated["status"] == "VALIDATED"
    assert updated["validation_task_id"] == 999


def test_patch_queued_insight_not_in_pending():
    """PATCH_QUEUED insight must not appear in get_pending_insights()."""
    task = _make_completed_task("deep_research_feature", task_id=30)
    with patch.object(insight_extractor.db, "list_tasks", return_value=[task]):
        new = insight_extractor.extract_insights_from_completed_tasks()

    ins = new[0]
    insight_extractor.mark_insight_patch_queued(ins["id"], patch_task_id=501)

    pending = insight_extractor.get_pending_insights()
    ids = [i["id"] for i in pending]
    assert ins["id"] not in ids, "PATCH_QUEUED insight should not appear in pending list"


def test_extract_accepts_reemit_after_archived():
    """After an insight is VALIDATED, the same signal_state_type can be re-emitted."""
    task = _make_completed_task("deep_research_calibration", task_id=50)
    with patch.object(insight_extractor.db, "list_tasks", return_value=[task]):
        new = insight_extractor.extract_insights_from_completed_tasks()

    ins = new[0]
    # Manually archive it by directly mutating stored data
    all_ins = insight_extractor._load_insights()
    for i in all_ins:
        if i["id"] == ins["id"]:
            i["status"] = "VALIDATED"
    insight_extractor._save_insights(all_ins)

    # Now extract again — VALIDATED insight is no longer "active" so re-emit allowed
    with patch.object(insight_extractor.db, "list_tasks", return_value=[task]):
        second = insight_extractor.extract_insights_from_completed_tasks()

    assert len(second) == 1, "Should re-emit insight for VALIDATED signal_state_type"


def test_within_run_dedup_emits_once_per_signal_state_type():
    """Multiple completed tasks with same signal_state_type → only 1 insight in single run."""
    tasks = [
        _make_completed_task("deep_research_backtest_validity", task_id=10),
        _make_completed_task("deep_research_backtest_validity", task_id=11),
        _make_completed_task("deep_research_backtest_validity", task_id=12),
    ]
    with patch.object(insight_extractor.db, "list_tasks", return_value=tasks):
        new = insight_extractor.extract_insights_from_completed_tasks()

    sst_list = [ins["source_signal_state_type"] for ins in new]
    assert sst_list.count("deep_research_backtest_validity") == 1, (
        f"Expected 1 backtest_validity insight, got {sst_list.count('deep_research_backtest_validity')}"
    )


def test_within_run_dedup_allows_distinct_signal_state_types():
    """Different signal_state_types each emit exactly one insight in the same run."""
    tasks = [
        _make_completed_task("deep_research_calibration", task_id=20),
        _make_completed_task("deep_research_feature", task_id=21),
        _make_completed_task("deep_research_calibration", task_id=22),  # duplicate
    ]
    with patch.object(insight_extractor.db, "list_tasks", return_value=tasks):
        new = insight_extractor.extract_insights_from_completed_tasks()

    assert len(new) == 2, f"Expected 2 distinct insights, got {len(new)}"
    types_seen = {ins["source_signal_state_type"] for ins in new}
    assert types_seen == {"deep_research_calibration", "deep_research_feature"}

