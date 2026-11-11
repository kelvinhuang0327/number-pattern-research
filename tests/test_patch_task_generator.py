"""
Tests for orchestrator/patch_task_generator.py
Coverage: safety guard, 6-category patch builders, validation builder, quality gate compat.
"""
from __future__ import annotations

import pytest
from orchestrator import patch_task_generator
from orchestrator.task_quality_gate import evaluate_task_quality


# ─── fixtures ────────────────────────────────────────────────────────────────

def _make_insight(category: str, ins_id: str = "test001") -> dict:
    """Build a minimal insight dict matching what insight_extractor produces."""
    from orchestrator.insight_extractor import AUDIT_TO_INSIGHT

    # Find the AUDIT_TO_INSIGHT entry for this category
    mapping = next(
        (v for v in AUDIT_TO_INSIGHT.values() if v["category"] == category),
        None,
    )
    assert mapping is not None, f"No AUDIT_TO_INSIGHT entry for category '{category}'"
    return {
        "id": ins_id,
        "source_task_id": 1,
        "source_signal_state_type": f"deep_research_{category}",
        "category": category,
        "weakness": mapping["weakness"],
        "evidence_files": mapping["evidence_files"],
        "target_files": mapping["target_files"],
        "expected_metric": mapping["expected_metric"],
        "priority": mapping["priority"],
        "status": "PENDING",
    }


# ─── safety guard ────────────────────────────────────────────────────────────

def test_safety_guard_blocks_live_strategy_target():
    """An insight targeting strategy/ must be silently skipped."""
    bad_insight = _make_insight("calibration")
    bad_insight["target_files"] = ["strategy/kelly.py"]

    result = patch_task_generator.generate_patch_tasks([bad_insight])
    assert result == [], "Should block insight targeting strategy/"


def test_safety_guard_blocks_telegram_bot_target():
    """An insight targeting telegram_bot/ must be silently skipped."""
    bad_insight = _make_insight("feature_quality")
    bad_insight["target_files"] = ["telegram_bot/bot.py"]

    result = patch_task_generator.generate_patch_tasks([bad_insight])
    assert result == [], "Should block insight targeting telegram_bot/"


def test_safety_guard_blocks_live_directory_target():
    """An insight targeting live/ must be silently skipped."""
    bad_insight = _make_insight("regime_detection")
    bad_insight["target_files"] = ["live/live_runner.py"]

    result = patch_task_generator.generate_patch_tasks([bad_insight])
    assert result == [], "Should block insight targeting live/"


def test_safety_guard_allows_research_target():
    """An insight targeting wbc_backend/research/ is safe and should produce a task."""
    ins = _make_insight("calibration")
    result = patch_task_generator.generate_patch_tasks([ins])
    assert len(result) == 1
    assert result[0]["safety_level"] == "paper_only"


# ─── all 6 categories produce patch tasks ────────────────────────────────────

@pytest.mark.parametrize("category", [
    "calibration",
    "feature_quality",
    "regime_detection",
    "clv_odds_quality",
    "feedback_loop",
    "backtest_validity",
])
def test_each_category_produces_patch_task(category):
    """Each of the 6 audit categories must produce exactly one patch task."""
    ins = _make_insight(category)
    result = patch_task_generator.generate_patch_tasks([ins])
    assert len(result) == 1
    task = result[0]
    assert task["analysis_family"].startswith("model-patch-"), (
        f"Expected model-patch-* family, got '{task['analysis_family']}'"
    )
    assert task["insight_id"] == ins["id"]


def test_unknown_category_skipped():
    """An insight with an unmapped category should be skipped (not raise)."""
    ins = _make_insight("calibration")
    ins["category"] = "totally_unknown_category"
    result = patch_task_generator.generate_patch_tasks([ins])
    assert result == []


# ─── validation task ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("category", [
    "calibration",
    "feature_quality",
    "regime_detection",
    "clv_odds_quality",
    "feedback_loop",
    "backtest_validity",
])
def test_validation_task_has_correct_family(category):
    """generate_validation_task() must produce model-validation-backtest family."""
    ins = _make_insight(category)
    vt = patch_task_generator.generate_validation_task(ins)
    assert vt["analysis_family"] == "model-validation-backtest"
    assert vt["focus_area"].startswith(f"mlb-validation-{category}")
    assert vt["insight_id"] == ins["id"]
    assert "[PAPER MODE ONLY]" in vt["objective"]


def test_validation_task_raises_for_live_target():
    """generate_validation_task() must raise ValueError for live-file insights."""
    ins = _make_insight("calibration")
    ins["target_files"] = ["strategy/bet_sizer.py"]
    with pytest.raises(ValueError, match="live files"):
        patch_task_generator.generate_validation_task(ins)


# ─── quality gate compatibility ───────────────────────────────────────────────

@pytest.mark.parametrize("category", [
    "calibration",
    "feature_quality",
    "regime_detection",
    "clv_odds_quality",
    "feedback_loop",
    "backtest_validity",
])
def test_patch_task_passes_quality_gate(category):
    """Every patch task blueprint must pass the task quality gate."""
    from orchestrator.planner_tick import normalize_task_draft, _build_task_from_candidate

    ins = _make_insight(category)
    candidates = patch_task_generator.generate_patch_tasks([ins])
    assert candidates, f"No patch candidate for {category}"
    task_data = normalize_task_draft(_build_task_from_candidate(candidates[0]))

    verdict = evaluate_task_quality(task_data, recent_tasks=[])
    assert verdict.passed, (
        f"Patch task for '{category}' failed quality gate:\n"
        + "\n".join(verdict.rejection_reasons)
    )


@pytest.mark.parametrize("category", [
    "calibration",
    "feature_quality",
    "regime_detection",
    "clv_odds_quality",
    "feedback_loop",
    "backtest_validity",
])
def test_validation_task_passes_quality_gate(category):
    """Every validation task blueprint must pass the task quality gate."""
    from orchestrator.planner_tick import normalize_task_draft, _build_task_from_candidate

    ins = _make_insight(category)
    vt = patch_task_generator.generate_validation_task(ins)
    task_data = normalize_task_draft(_build_task_from_candidate(vt))

    verdict = evaluate_task_quality(task_data, recent_tasks=[])
    assert verdict.passed, (
        f"Validation task for '{category}' failed quality gate:\n"
        + "\n".join(verdict.rejection_reasons)
    )
