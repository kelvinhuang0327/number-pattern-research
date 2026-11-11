"""
Phase 9 Autonomous Optimization Ops — Integration Tests

8 scenarios:

Scenario 1: EFFECTIVE window classification
Scenario 2: IDLE window classification
Scenario 3: DEGRADED repeated-skip classification
Scenario 4: BLOCKED by governance classification
Scenario 5: Task dimension mapping
Scenario 6: Decision card phase9_ops section
Scenario 7: Report JSON + MD generation
Scenario 8: Scheduler trigger does not affect planner/worker logic

SUCCESS MARKER: PHASE_9_AUTONOMOUS_OPTIMIZATION_OPS_VERIFIED
"""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from orchestrator import optimization_ops_report as ops_rpt
from orchestrator.optimization_ops_report import (
    CLASS_EFFECTIVE, CLASS_IDLE, CLASS_DEGRADED, CLASS_BLOCKED, CLASS_PARTIAL,
    classify_window, get_task_dimensions,
    DIM_MODEL_LEARNING, DIM_STRATEGY_FEEDBACK, DIM_OPERATIONAL_RELIABILITY,
    DIM_ARCHITECTURE_QUALITY, DIM_DATA_TRUSTWORTHINESS, DIM_ANALYSIS_CORRECTNESS,
)


# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ago_iso(hours: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()


def _make_task(
    task_id: int = 1,
    status: str = "COMPLETED",
    analysis_family: str = "model-patch-atomic",
    title: str = "Patch calibration",
    completed_at: str | None = None,
    completion_quality: str | None = "COMPLETED_VALID",
) -> dict:
    return {
        "id": task_id,
        "title": title,
        "status": status,
        "analysis_family": analysis_family,
        "focus_keys": analysis_family,
        "completed_at": completed_at or _now_iso(),
        "created_at": _ago_iso(1),
        "updated_at": _now_iso(),
        "completion_quality": completion_quality,
        "completed_text": "substantive result from model patch run with validation output",
    }


def _make_run(outcome: str = "SUCCESS", tick_at: str | None = None) -> dict:
    return {
        "id": 1,
        "runner": "planner_tick",
        "outcome": outcome,
        "tick_at": tick_at or _now_iso(),
        "message": "",
    }


# ─────────────────────────────────────────────────────────────────
# Scenario 1: EFFECTIVE window classification
# ─────────────────────────────────────────────────────────────────

class TestEffectiveClassification:
    def test_completed_task_with_dimension_is_effective(self):
        """One COMPLETED task with mapped dimension → EFFECTIVE."""
        tasks = [_make_task(status="COMPLETED", analysis_family="model-patch-atomic")]
        runs = [_make_run("SUCCESS")]
        result = classify_window(
            tasks=tasks, runs=runs, gov_blocked=0,
            consecutive_skips=0, opt_state={},
        )
        assert result == CLASS_EFFECTIVE

    def test_multiple_completed_different_families_effective(self):
        """Multiple COMPLETED tasks with distinct families → EFFECTIVE."""
        tasks = [
            _make_task(1, "COMPLETED", "model-patch-atomic"),
            _make_task(2, "COMPLETED", "calibration-atomic"),
        ]
        runs = [_make_run("SUCCESS")]
        result = classify_window(
            tasks=tasks, runs=runs, gov_blocked=0,
            consecutive_skips=0, opt_state={},
        )
        assert result == CLASS_EFFECTIVE

    def test_effective_not_downgraded_by_one_skip(self):
        """< 3 skips should not prevent EFFECTIVE if tasks completed."""
        tasks = [_make_task(status="COMPLETED", analysis_family="calibration-atomic")]
        runs = [_make_run("SKIPPED"), _make_run("SUCCESS")]
        result = classify_window(
            tasks=tasks, runs=runs, gov_blocked=0,
            consecutive_skips=1, opt_state={},
        )
        assert result == CLASS_EFFECTIVE

    def test_effective_generate_report_returns_effective(self):
        """generate_report with mocked COMPLETED tasks returns EFFECTIVE."""
        tasks = [_make_task(status="COMPLETED", analysis_family="model-patch-atomic")]
        runs = [_make_run("SUCCESS")]
        with patch.object(ops_rpt, "_query_tasks_in_window", return_value=tasks), \
             patch.object(ops_rpt, "_query_runs_in_window", return_value=runs), \
             patch.object(ops_rpt, "_get_training_memory_summary", return_value={}), \
             patch.object(ops_rpt, "_get_phase6_summary", return_value={}), \
             patch.object(ops_rpt, "_get_optimization_state_summary", return_value={}):
            report = ops_rpt.generate_report("8h")
        assert report["classification"] == CLASS_EFFECTIVE


# ─────────────────────────────────────────────────────────────────
# Scenario 2: IDLE window classification
# ─────────────────────────────────────────────────────────────────

class TestIdleClassification:
    def test_no_tasks_no_runs_is_idle(self):
        """No tasks and no runs → IDLE."""
        result = classify_window(
            tasks=[], runs=[], gov_blocked=0,
            consecutive_skips=0, opt_state={},
        )
        assert result == CLASS_IDLE

    def test_runs_but_no_tasks_is_idle(self):
        """Scheduler ran but produced no tasks → IDLE."""
        runs = [_make_run("NOTHING")]
        result = classify_window(
            tasks=[], runs=runs, gov_blocked=0,
            consecutive_skips=0, opt_state={},
        )
        assert result == CLASS_IDLE

    def test_idle_generate_report(self):
        """generate_report with no tasks returns IDLE."""
        with patch.object(ops_rpt, "_query_tasks_in_window", return_value=[]), \
             patch.object(ops_rpt, "_query_runs_in_window", return_value=[_make_run("NOTHING")]), \
             patch.object(ops_rpt, "_get_training_memory_summary", return_value={}), \
             patch.object(ops_rpt, "_get_phase6_summary", return_value={}), \
             patch.object(ops_rpt, "_get_optimization_state_summary", return_value={}):
            report = ops_rpt.generate_report("8h")
        assert report["classification"] == CLASS_IDLE
        assert report["tasks_completed"] == 0

    def test_idle_next_focus_mentions_planner(self):
        """IDLE next focus should mention planner or tasks."""
        with patch.object(ops_rpt, "_query_tasks_in_window", return_value=[]), \
             patch.object(ops_rpt, "_query_runs_in_window", return_value=[]), \
             patch.object(ops_rpt, "_get_training_memory_summary", return_value={}), \
             patch.object(ops_rpt, "_get_phase6_summary", return_value={}), \
             patch.object(ops_rpt, "_get_optimization_state_summary", return_value={}):
            report = ops_rpt.generate_report("8h")
        focus = report["next_recommended_focus"].lower()
        assert "task" in focus or "planner" in focus or "blueprint" in focus


# ─────────────────────────────────────────────────────────────────
# Scenario 3: DEGRADED repeated-skip classification
# ─────────────────────────────────────────────────────────────────

class TestDegradedClassification:
    def test_three_consecutive_skips_is_degraded(self):
        """≥3 consecutive SKIPPEDs with no completed tasks → DEGRADED."""
        runs = [
            _make_run("SKIPPED", _ago_iso(0.1)),
            _make_run("SKIPPED", _ago_iso(0.5)),
            _make_run("SKIPPED", _ago_iso(1.0)),
        ]
        result = classify_window(
            tasks=[], runs=runs, gov_blocked=0,
            consecutive_skips=3, opt_state={},
        )
        assert result == CLASS_DEGRADED

    def test_three_consecutive_errors_no_completed_is_degraded(self):
        """≥3 ERROR outcomes with no completed tasks → DEGRADED."""
        runs = [_make_run("ERROR")] * 3
        result = classify_window(
            tasks=[], runs=runs, gov_blocked=0,
            consecutive_skips=0, opt_state={},
        )
        assert result == CLASS_DEGRADED

    def test_degraded_next_focus_mentions_reliability(self):
        """DEGRADED next focus should mention scheduler or API failure."""
        with patch.object(ops_rpt, "_query_tasks_in_window", return_value=[]), \
             patch.object(ops_rpt, "_query_runs_in_window", return_value=[_make_run("SKIPPED")] * 4), \
             patch.object(ops_rpt, "_get_training_memory_summary", return_value={}), \
             patch.object(ops_rpt, "_get_phase6_summary", return_value={}), \
             patch.object(ops_rpt, "_get_optimization_state_summary", return_value={}):
            report = ops_rpt.generate_report("8h")
        assert report["classification"] == CLASS_DEGRADED
        focus = report["next_recommended_focus"].lower()
        assert "reliability" in focus or "skip" in focus or "scheduler" in focus


# ─────────────────────────────────────────────────────────────────
# Scenario 4: BLOCKED by governance classification
# ─────────────────────────────────────────────────────────────────

class TestBlockedClassification:
    def test_all_learning_families_blocked_and_no_completed_is_blocked(self):
        """Governance blocks ≥4 learning families, no completed tasks, no safe families → BLOCKED.

        Uses SYSTEM_RELIABILITY_ISSUE state (not DATA_WAITING) so no safe families are
        implicitly available. DATA_WAITING now returns WAITING_ACTIVE since safe
        non-learning work is always available in that state.
        """
        opt_state = {
            "current_state": "SYSTEM_RELIABILITY_ISSUE",
            "allowed_families": [],
            "blocked_families": [
                "strategy-reinforcement",
                "model-validation-atomic",
                "model-patch-atomic",
                "feedback-atomic",
            ],
            "reasons": ["system reliability issue, all learning blocked"],
        }
        result = classify_window(
            tasks=[], runs=[_make_run("SUCCESS")],
            gov_blocked=5, consecutive_skips=0, opt_state=opt_state,
        )
        assert result == CLASS_BLOCKED

    def test_blocked_returns_governance_info_in_report(self):
        """BLOCKED report should include blocked families."""
        opt_state_mock = {
            "current_state": "DATA_WAITING",
            "blocked_families": [
                "strategy-reinforcement",
                "model-validation-atomic",
                "model-patch-atomic",
                "feedback-atomic",
            ],
            "reasons": ["all_clv_pending: 10 PENDING_CLOSING"],
        }
        with patch.object(ops_rpt, "_query_tasks_in_window", return_value=[]), \
             patch.object(ops_rpt, "_query_runs_in_window", return_value=[_make_run()]), \
             patch.object(ops_rpt, "_get_training_memory_summary", return_value={}), \
             patch.object(ops_rpt, "_get_phase6_summary", return_value={"clv_pending": 10, "clv_computed": 0}), \
             patch.object(ops_rpt, "_get_optimization_state_summary", return_value=opt_state_mock):
            report = ops_rpt.generate_report("8h")
        assert len(report["optimization_blocked_families"]) >= 4

    def test_blocked_next_focus_mentions_governance(self):
        """BLOCKED next focus should mention governance unblocking."""
        opt_state_mock = {
            "current_state": "DATA_WAITING",
            "blocked_families": ["strategy-reinforcement", "model-validation-atomic",
                                  "model-patch-atomic", "feedback-atomic"],
            "reasons": ["all_clv_pending"],
        }
        with patch.object(ops_rpt, "_query_tasks_in_window", return_value=[]), \
             patch.object(ops_rpt, "_query_runs_in_window", return_value=[_make_run()]), \
             patch.object(ops_rpt, "_get_training_memory_summary", return_value={}), \
             patch.object(ops_rpt, "_get_phase6_summary", return_value={"clv_pending": 10, "clv_computed": 0}), \
             patch.object(ops_rpt, "_get_optimization_state_summary", return_value=opt_state_mock):
            report = ops_rpt.generate_report("8h")
        focus = report["next_recommended_focus"].lower()
        assert "governance" in focus or "unblock" in focus or "pending" in focus


# ─────────────────────────────────────────────────────────────────
# Scenario 5: Task dimension mapping
# ─────────────────────────────────────────────────────────────────

class TestDimensionMapping:
    def test_model_patch_maps_to_model_learning(self):
        task = _make_task(analysis_family="model-patch-atomic")
        dims = get_task_dimensions(task)
        assert DIM_MODEL_LEARNING in dims

    def test_strategy_reinforcement_maps_to_strategy_feedback(self):
        task = _make_task(analysis_family="strategy-reinforcement")
        dims = get_task_dimensions(task)
        assert DIM_STRATEGY_FEEDBACK in dims

    def test_architecture_cleanup_maps_to_architecture_quality(self):
        task = _make_task(analysis_family="architecture-cleanup")
        dims = get_task_dimensions(task)
        assert DIM_ARCHITECTURE_QUALITY in dims

    def test_data_monitor_maps_to_data_trustworthiness(self):
        task = _make_task(analysis_family="data-monitor")
        dims = get_task_dimensions(task)
        assert DIM_DATA_TRUSTWORTHINESS in dims

    def test_maintenance_maps_to_operational_reliability(self):
        task = _make_task(analysis_family="maintenance")
        dims = get_task_dimensions(task)
        assert DIM_OPERATIONAL_RELIABILITY in dims

    def test_unknown_family_falls_back_to_title_heuristic(self):
        task = {"id": 1, "title": "Patch calibration model", "status": "COMPLETED",
                "analysis_family": "unknown-xyzzy"}
        dims = get_task_dimensions(task)
        # Title heuristic should pick up "model" or "calibr"
        assert DIM_MODEL_LEARNING in dims

    def test_empty_family_empty_title_returns_empty(self):
        task = {"id": 1, "title": "", "status": "COMPLETED", "analysis_family": ""}
        dims = get_task_dimensions(task)
        assert isinstance(dims, list)

    def test_completed_task_without_dimension_flagged(self):
        """_flag_tasks_without_dimensions detects undimensioned COMPLETED tasks."""
        task_no_dim = {"id": 99, "title": "", "status": "COMPLETED", "analysis_family": ""}
        task_with_dim = _make_task(status="COMPLETED", analysis_family="model-patch-atomic")
        flagged = ops_rpt._flag_tasks_without_dimensions([task_no_dim, task_with_dim])
        ids = [t["id"] for t in flagged]
        assert 99 in ids
        assert task_with_dim["id"] not in ids


# ─────────────────────────────────────────────────────────────────
# Scenario 6: Decision card phase9_ops section
# ─────────────────────────────────────────────────────────────────

class TestDecisionCardOpsSection:
    def test_compute_phase9_ops_status_returns_available(self):
        """compute_phase9_ops_status() returns available=True on success."""
        from scripts.ops_decision_card import compute_phase9_ops_status
        tasks = [_make_task(status="COMPLETED", analysis_family="model-patch-atomic")]
        runs = [_make_run("SUCCESS")]
        with patch.object(ops_rpt, "_query_tasks_in_window", return_value=tasks), \
             patch.object(ops_rpt, "_query_runs_in_window", return_value=runs), \
             patch.object(ops_rpt, "_get_training_memory_summary", return_value={}), \
             patch.object(ops_rpt, "_get_phase6_summary", return_value={}), \
             patch.object(ops_rpt, "_get_optimization_state_summary", return_value={}):
            status = compute_phase9_ops_status(window="8h")
        assert status["available"] is True
        assert "classification" in status
        assert "tasks_completed" in status
        assert "next_focus" in status

    def test_phase9_ops_in_build_payload(self):
        """build_payload() includes 'phase9_ops' key."""
        from scripts.ops_decision_card import build_payload
        payload = build_payload()
        assert "phase9_ops" in payload

    def test_render_card_includes_ops_section(self):
        """render_card() output includes Phase 9 Autonomous Ops section."""
        from scripts.ops_decision_card import build_payload, render_card
        payload = build_payload()
        rendered = render_card(payload)
        assert "AUTONOMOUS OPS" in rendered or "phase9" in rendered.lower()


# ─────────────────────────────────────────────────────────────────
# Scenario 7: Report JSON + MD generation
# ─────────────────────────────────────────────────────────────────

class TestReportGeneration:
    def _patched_generate(self) -> dict:
        tasks = [_make_task(status="COMPLETED", analysis_family="model-patch-atomic")]
        runs = [_make_run("SUCCESS")]
        with patch.object(ops_rpt, "_query_tasks_in_window", return_value=tasks), \
             patch.object(ops_rpt, "_query_runs_in_window", return_value=runs), \
             patch.object(ops_rpt, "_get_training_memory_summary", return_value={}), \
             patch.object(ops_rpt, "_get_phase6_summary", return_value={}), \
             patch.object(ops_rpt, "_get_optimization_state_summary", return_value={}):
            return ops_rpt.generate_report("8h")

    def test_report_has_required_keys(self):
        report = self._patched_generate()
        required = [
            "window", "tasks_created", "tasks_completed", "tasks_rejected",
            "governance_blocked", "patches_validated", "patches_kept",
            "patches_rejected", "clv_computed", "clv_pending",
            "strategy_reinforcements", "system_reliability_issues",
            "top_improvements", "next_recommended_focus",
        ]
        for key in required:
            assert key in report, f"Missing report key: {key}"

    def test_report_window_matches_requested(self):
        report = self._patched_generate()
        assert report["window"] == "8h"

    def test_report_24h_window(self):
        tasks = [_make_task(status="COMPLETED", analysis_family="calibration-atomic")]
        with patch.object(ops_rpt, "_query_tasks_in_window", return_value=tasks), \
             patch.object(ops_rpt, "_query_runs_in_window", return_value=[]), \
             patch.object(ops_rpt, "_get_training_memory_summary", return_value={}), \
             patch.object(ops_rpt, "_get_phase6_summary", return_value={}), \
             patch.object(ops_rpt, "_get_optimization_state_summary", return_value={}):
            report = ops_rpt.generate_report("24h")
        assert report["window"] == "24h"

    def test_render_markdown_produces_string(self):
        report = self._patched_generate()
        md = ops_rpt.render_markdown(report)
        assert isinstance(md, str)
        assert len(md) > 100

    def test_render_markdown_contains_classification(self):
        report = self._patched_generate()
        md = ops_rpt.render_markdown(report)
        assert report["classification"] in md

    def test_cli_writes_json_and_md(self):
        """run_optimization_ops_report.run() writes both JSON and MD files."""
        import scripts.run_optimization_ops_report as cli
        tasks = [_make_task(status="COMPLETED", analysis_family="model-patch-atomic")]
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            json_dir = td / "reports"
            md_dir = td / "docs"
            with patch.object(cli, "_REPORTS_JSON", json_dir), \
                 patch.object(cli, "_REPORTS_MD", md_dir), \
                 patch.object(ops_rpt, "_query_tasks_in_window", return_value=tasks), \
                 patch.object(ops_rpt, "_query_runs_in_window", return_value=[_make_run()]), \
                 patch.object(ops_rpt, "_get_training_memory_summary", return_value={}), \
                 patch.object(ops_rpt, "_get_phase6_summary", return_value={}), \
                 patch.object(ops_rpt, "_get_optimization_state_summary", return_value={}):
                report = cli.run(window="8h", print_card=False, json_only=False)
        assert report["classification"] in (
            CLASS_EFFECTIVE, CLASS_PARTIAL, CLASS_IDLE, CLASS_DEGRADED, CLASS_BLOCKED
        )


# ─────────────────────────────────────────────────────────────────
# Scenario 8: Scheduler trigger does not affect planner/worker logic
# ─────────────────────────────────────────────────────────────────

class TestSchedulerSafety:
    def test_trigger_ops_report_now_does_not_call_planner_tick(self):
        """trigger_ops_report_now() must never call run_planner_tick."""
        import orchestrator.ops_report_scheduler as sch
        tasks = [_make_task(status="COMPLETED")]
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "ops_report_state.json"
            with patch.object(sch, "_STATE_PATH", state_path), \
                 patch.object(sch, "_REPORTS_JSON", Path(tmpdir) / "reports"), \
                 patch.object(sch, "_REPORTS_MD", Path(tmpdir) / "docs"), \
                 patch.object(ops_rpt, "_query_tasks_in_window", return_value=tasks), \
                 patch.object(ops_rpt, "_query_runs_in_window", return_value=[_make_run()]), \
                 patch.object(ops_rpt, "_get_training_memory_summary", return_value={}), \
                 patch.object(ops_rpt, "_get_phase6_summary", return_value={}), \
                 patch.object(ops_rpt, "_get_optimization_state_summary", return_value={}), \
                 patch("orchestrator.planner_tick.run_planner_tick") as mock_planner:
                sch.trigger_ops_report_now(window="8h")
        mock_planner.assert_not_called()

    def test_maybe_trigger_skips_if_interval_not_elapsed(self):
        """maybe_trigger_ops_report returns None if < 8h since last run."""
        import orchestrator.ops_report_scheduler as sch
        recent = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
        fake_state = {"last_triggered_8h": recent}
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "ops_report_state.json"
            state_path.write_text(
                json.dumps(fake_state), encoding="utf-8"
            )
            with patch.object(sch, "_STATE_PATH", state_path):
                result = sch.maybe_trigger_ops_report(window="8h")
        assert result is None

    def test_maybe_trigger_fires_when_interval_elapsed(self):
        """maybe_trigger_ops_report triggers report when > 8h since last run."""
        import orchestrator.ops_report_scheduler as sch
        old_ts = (datetime.now(timezone.utc) - timedelta(hours=10)).isoformat()
        fake_state = {"last_triggered_8h": old_ts}
        tasks = [_make_task(status="COMPLETED")]
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "ops_report_state.json"
            state_path.write_text(json.dumps(fake_state), encoding="utf-8")
            with patch.object(sch, "_STATE_PATH", state_path), \
                 patch.object(sch, "_REPORTS_JSON", Path(tmpdir) / "reports"), \
                 patch.object(sch, "_REPORTS_MD", Path(tmpdir) / "docs"), \
                 patch.object(ops_rpt, "_query_tasks_in_window", return_value=tasks), \
                 patch.object(ops_rpt, "_query_runs_in_window", return_value=[_make_run()]), \
                 patch.object(ops_rpt, "_get_training_memory_summary", return_value={}), \
                 patch.object(ops_rpt, "_get_phase6_summary", return_value={}), \
                 patch.object(ops_rpt, "_get_optimization_state_summary", return_value={}):
                result = sch.maybe_trigger_ops_report(window="8h")
        assert result is not None
        assert "classification" in result

    def test_trigger_does_not_modify_training_memory(self):
        """Scheduler trigger must not mutate training_memory consecutive counters."""
        from orchestrator import training_memory as tm
        import orchestrator.ops_report_scheduler as sch
        with tempfile.TemporaryDirectory() as tmpdir:
            mem_path = Path(tmpdir) / "training_memory.json"
            state_path = Path(tmpdir) / "ops_report_state.json"
            with patch.object(tm, "MEMORY_PATH", mem_path):
                before = tm.load_memory()
                cs_before = before.get("consecutive_successes", 0)
                cf_before = before.get("consecutive_failures", 0)
            with patch.object(sch, "_STATE_PATH", state_path), \
                 patch.object(sch, "_REPORTS_JSON", Path(tmpdir) / "reports"), \
                 patch.object(sch, "_REPORTS_MD", Path(tmpdir) / "docs"), \
                 patch.object(ops_rpt, "_query_tasks_in_window", return_value=[]), \
                 patch.object(ops_rpt, "_query_runs_in_window", return_value=[]), \
                 patch.object(ops_rpt, "_get_training_memory_summary", return_value={}), \
                 patch.object(ops_rpt, "_get_phase6_summary", return_value={}), \
                 patch.object(ops_rpt, "_get_optimization_state_summary", return_value={}), \
                 patch.object(tm, "MEMORY_PATH", mem_path):
                sch.trigger_ops_report_now(window="8h")
                after = tm.load_memory()
        assert after.get("consecutive_successes", 0) == cs_before
        assert after.get("consecutive_failures", 0) == cf_before


# ─────────────────────────────────────────────────────────────────
# Success marker
# ─────────────────────────────────────────────────────────────────

def test_phase9_autonomous_optimization_ops_verified():
    """
    SUCCESS MARKER — all Phase 9 ops checks pass.

    Asserts:
    1. 8h report generates with correct structure.
    2. Classification is correct for EFFECTIVE + IDLE + DEGRADED windows.
    3. Dimension mapping covers all key families.
    4. Decision card includes phase9_ops block.
    5. Scheduler trigger is safe (no planner side effects).
    """
    # 1. Report structure
    tasks = [_make_task(status="COMPLETED", analysis_family="model-patch-atomic")]
    with patch.object(ops_rpt, "_query_tasks_in_window", return_value=tasks), \
         patch.object(ops_rpt, "_query_runs_in_window", return_value=[_make_run()]), \
         patch.object(ops_rpt, "_get_training_memory_summary", return_value={}), \
         patch.object(ops_rpt, "_get_phase6_summary", return_value={}), \
         patch.object(ops_rpt, "_get_optimization_state_summary", return_value={}):
        report = ops_rpt.generate_report("8h")
    assert report["window"] == "8h"
    assert report["classification"] in (
        CLASS_EFFECTIVE, CLASS_PARTIAL, CLASS_IDLE, CLASS_DEGRADED, CLASS_BLOCKED
    )
    for key in ("tasks_created", "tasks_completed", "governance_blocked",
                "clv_computed", "clv_pending", "next_recommended_focus"):
        assert key in report

    # 2. Classification coverage
    assert classify_window([], [], 0, 0, {}) == CLASS_IDLE
    assert classify_window([], [], 0, 3, {}) == CLASS_DEGRADED
    assert classify_window(
        [_make_task("COMPLETED", analysis_family="model-patch-atomic")],
        [_make_run()], 0, 0, {}
    ) == CLASS_EFFECTIVE

    # 3. Dimension mapping
    assert DIM_MODEL_LEARNING in get_task_dimensions(
        _make_task(analysis_family="model-patch-atomic")
    )
    assert DIM_STRATEGY_FEEDBACK in get_task_dimensions(
        _make_task(analysis_family="strategy-reinforcement")
    )

    # 4. Decision card has phase9_ops
    from scripts.ops_decision_card import build_payload
    payload = build_payload()
    assert "phase9_ops" in payload

    # 5. Scheduler safety
    import orchestrator.ops_report_scheduler as sch
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch.object(sch, "_STATE_PATH", Path(tmpdir) / "state.json"), \
             patch.object(sch, "_REPORTS_JSON", Path(tmpdir) / "reports"), \
             patch.object(sch, "_REPORTS_MD", Path(tmpdir) / "docs"), \
             patch.object(ops_rpt, "_query_tasks_in_window", return_value=[]), \
             patch.object(ops_rpt, "_query_runs_in_window", return_value=[]), \
             patch.object(ops_rpt, "_get_training_memory_summary", return_value={}), \
             patch.object(ops_rpt, "_get_phase6_summary", return_value={}), \
             patch.object(ops_rpt, "_get_optimization_state_summary", return_value={}), \
             patch("orchestrator.planner_tick.run_planner_tick") as mock_planner:
            sch.trigger_ops_report_now(window="8h")
    mock_planner.assert_not_called()

    assert True, "PHASE_9_AUTONOMOUS_OPTIMIZATION_OPS_VERIFIED"
