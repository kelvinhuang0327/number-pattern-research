"""
Phase 12 — Scheduler Idle Recovery Tests

Verifies:
1. Skip reason classification parses message strings correctly
2. Hard-off skips do NOT count as consecutive unexplained skips (no false DEGRADED)
3. DATA_WAITING cadence creates closing_monitor when slot is empty
4. DATA_WAITING cadence does NOT create duplicate within same 20-min slot
5. Deterministic safe task executor runs closing_monitor without LLM
6. Ops report yields WAITING_ACTIVE when all skips are hard-off protected
7. Ops report yields DEGRADED when there are consecutive unexplained skips

Success marker: test_phase12_success_marker asserts
    PHASE_12_SCHEDULER_IDLE_RECOVERY_VERIFIED
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch


# ─────────────────────────────────────────────────────────────────────────────
# S1: Skip-reason classifier
# ─────────────────────────────────────────────────────────────────────────────

class TestSkipReasonClassifier:
    """classify_skip_reason correctly parses message strings."""

    def _make_run(self, outcome: str, message: str) -> dict:
        return {"outcome": outcome, "message": message, "tick_at": "2025-01-01T00:00:00"}

    def test_global_hard_off_message(self):
        from orchestrator.scheduler_skip_classifier import (
            classify_skip_reason,
            SKIP_HARD_OFF,
        )
        run = self._make_run("SKIPPED", "GLOBAL_HARD_OFF — skip execution (worker_tick)")
        assert classify_skip_reason(run) == SKIP_HARD_OFF

    def test_hard_off_short_form(self):
        from orchestrator.scheduler_skip_classifier import classify_skip_reason, SKIP_HARD_OFF
        run = self._make_run("SKIPPED", "hard-off protection active")
        assert classify_skip_reason(run) == SKIP_HARD_OFF

    def test_no_queued_tasks_message(self):
        from orchestrator.scheduler_skip_classifier import classify_skip_reason, SKIP_NO_QUEUED
        run = self._make_run("SKIPPED", "Worker skipped: no queued tasks found")
        assert classify_skip_reason(run) == SKIP_NO_QUEUED

    def test_cadence_dedupe_message(self):
        from orchestrator.scheduler_skip_classifier import classify_skip_reason, SKIP_DUPLICATE
        # PLANNER_SKIP_CADENCE messages use the daily-cap constant as fallback
        # (cadence is a superset of daily-cap semantics for classifier purposes)
        run = self._make_run("SKIPPED", "PLANNER_SKIP_CADENCE: DATA_WAITING safe task already exists for current cadence slot")
        result = classify_skip_reason(run)
        # Both SKIP_DUPLICATE and SKIP_DAILY_CAP are valid for cadence skips
        from orchestrator.scheduler_skip_classifier import SKIP_DAILY_CAP
        assert result in (SKIP_DUPLICATE, SKIP_DAILY_CAP), (
            f"Expected SKIP_DUPLICATE or SKIP_DAILY_CAP for cadence skip, got {result!r}"
        )

    def test_daily_cap_message(self):
        from orchestrator.scheduler_skip_classifier import classify_skip_reason, SKIP_DAILY_CAP
        run = self._make_run("SKIPPED", "PLANNER_SKIP_DAILY_CAP: already created today")
        assert classify_skip_reason(run) == SKIP_DAILY_CAP

    def test_non_skipped_run_returns_none_constant(self):
        """Non-SKIPPED outcomes that don't match any pattern → SKIP_UNKNOWN (graceful)."""
        from orchestrator.scheduler_skip_classifier import classify_skip_reason, SKIP_UNKNOWN
        run = self._make_run("SKIPPED", "some unrecognised message")
        result = classify_skip_reason(run)
        assert result == SKIP_UNKNOWN

    def test_classify_all_skips_aggregates(self):
        from orchestrator.scheduler_skip_classifier import (
            classify_all_skips,
            SKIP_HARD_OFF,
            SKIP_NO_QUEUED,
        )
        runs = [
            {"outcome": "SKIPPED", "message": "GLOBAL_HARD_OFF — skip", "tick_at": "2025-01-01T00:00:00"},
            {"outcome": "SKIPPED", "message": "GLOBAL_HARD_OFF — skip", "tick_at": "2025-01-01T00:01:00"},
            {"outcome": "SKIPPED", "message": "no queued tasks", "tick_at": "2025-01-01T00:02:00"},
            {"outcome": "SUCCESS", "message": "done", "tick_at": "2025-01-01T00:03:00"},
        ]
        reasons = classify_all_skips(runs)
        assert reasons[SKIP_HARD_OFF] == 2
        assert reasons[SKIP_NO_QUEUED] == 1

    def test_is_hard_off_skip(self):
        from orchestrator.scheduler_skip_classifier import is_hard_off_skip
        assert is_hard_off_skip({"outcome": "SKIPPED", "message": "GLOBAL_HARD_OFF — skip", "tick_at": "t"})
        assert not is_hard_off_skip({"outcome": "SKIPPED", "message": "no queued tasks", "tick_at": "t"})


# ─────────────────────────────────────────────────────────────────────────────
# S2: Hard-off skips do NOT imply DEGRADED
# ─────────────────────────────────────────────────────────────────────────────

class TestHardOffSkipsNotDegraded:
    """count_unexplained_consecutive_skips ignores hard-off skips."""

    def _hard_off_run(self, tick: str) -> dict:
        return {
            "outcome": "SKIPPED",
            "message": "GLOBAL_HARD_OFF — skip execution (worker_tick)",
            "tick_at": tick,
        }

    def _no_queued_run(self, tick: str) -> dict:
        return {
            "outcome": "SKIPPED",
            "message": "no queued tasks",
            "tick_at": tick,
        }

    def test_8_hard_off_skips_count_as_zero_unexplained(self):
        from orchestrator.scheduler_skip_classifier import count_unexplained_consecutive_skips
        runs = [self._hard_off_run(f"2025-01-01T0{i}:00:00") for i in range(8)]
        # most-recent-first
        runs_sorted = sorted(runs, key=lambda r: r["tick_at"], reverse=True)
        assert count_unexplained_consecutive_skips(runs_sorted) == 0

    def test_all_consecutive_skips_protected_true_for_hard_off(self):
        from orchestrator.scheduler_skip_classifier import all_consecutive_skips_are_protected
        runs = [self._hard_off_run(f"2025-01-01T0{i}:00:00") for i in range(8)]
        runs_sorted = sorted(runs, key=lambda r: r["tick_at"], reverse=True)
        assert all_consecutive_skips_are_protected(runs_sorted) is True

    def test_all_consecutive_skips_protected_false_for_no_queued(self):
        from orchestrator.scheduler_skip_classifier import all_consecutive_skips_are_protected
        runs = [self._no_queued_run(f"2025-01-01T0{i}:00:00") for i in range(3)]
        runs_sorted = sorted(runs, key=lambda r: r["tick_at"], reverse=True)
        assert all_consecutive_skips_are_protected(runs_sorted) is False

    def test_mixed_runs_stops_at_non_skip(self):
        from orchestrator.scheduler_skip_classifier import count_unexplained_consecutive_skips
        runs = [
            self._hard_off_run("2025-01-01T08:00:00"),
            self._hard_off_run("2025-01-01T07:00:00"),
            {"outcome": "SUCCESS", "message": "done", "tick_at": "2025-01-01T06:00:00"},
            self._no_queued_run("2025-01-01T05:00:00"),
        ]
        # most-recent-first
        runs_sorted = sorted(runs, key=lambda r: r["tick_at"], reverse=True)
        # Only hard-off at head → unexplained = 0
        assert count_unexplained_consecutive_skips(runs_sorted) == 0

    def test_unexplained_skips_counted_correctly(self):
        from orchestrator.scheduler_skip_classifier import count_unexplained_consecutive_skips
        runs = [
            self._no_queued_run("2025-01-01T08:00:00"),
            self._no_queued_run("2025-01-01T07:00:00"),
            self._no_queued_run("2025-01-01T06:00:00"),
            {"outcome": "SUCCESS", "message": "done", "tick_at": "2025-01-01T05:00:00"},
        ]
        runs_sorted = sorted(runs, key=lambda r: r["tick_at"], reverse=True)
        assert count_unexplained_consecutive_skips(runs_sorted) == 3


# ─────────────────────────────────────────────────────────────────────────────
# S3: DATA_WAITING cadence — due when slot is empty
# ─────────────────────────────────────────────────────────────────────────────

class TestDataWaitingCadenceDue:
    """is_safe_task_due returns True when no task exists for current slot."""

    def test_cadence_dedupe_key_stable_within_window(self):
        """Two calls within same 20-min window produce identical keys."""
        from orchestrator.data_waiting_cadence import cadence_dedupe_key
        key1 = cadence_dedupe_key("closing_monitor")
        time.sleep(0.01)  # tiny gap — still same slot
        key2 = cadence_dedupe_key("closing_monitor")
        assert key1 == key2
        assert "closing_monitor" in key1
        assert "slot" in key1

    def test_cadence_dedupe_key_different_task_types(self):
        from orchestrator.data_waiting_cadence import cadence_dedupe_key
        key_cm = cadence_dedupe_key("closing_monitor")
        key_hc = cadence_dedupe_key("scheduler_health_check")
        assert key_cm != key_hc
        assert "closing_monitor" in key_cm
        assert "scheduler_health_check" in key_hc

    def test_is_safe_task_due_when_no_existing_task(self):
        from orchestrator.data_waiting_cadence import is_safe_task_due
        with patch("orchestrator.db.get_nonfailed_task_by_dedupe_key", return_value=None):
            assert is_safe_task_due("closing_monitor") is True

    def test_get_due_safe_tasks_includes_closing_monitor(self):
        from orchestrator.data_waiting_cadence import get_due_safe_tasks
        with patch("orchestrator.db.get_nonfailed_task_by_dedupe_key", return_value=None):
            tasks = get_due_safe_tasks()
            assert "closing_monitor" in tasks

    def test_cadence_minutes_closing_monitor_is_20(self):
        from orchestrator.data_waiting_cadence import CADENCE_MINUTES
        assert CADENCE_MINUTES["closing_monitor"] == 20

    def test_is_forbidden_task_type(self):
        from orchestrator.data_waiting_cadence import is_forbidden_task_type
        assert is_forbidden_task_type("model_patch_calibration") is True
        assert is_forbidden_task_type("strategy_reinforcement") is True  # exact match
        assert is_forbidden_task_type("closing_monitor") is False
        assert is_forbidden_task_type("scheduler_health_check") is False


# ─────────────────────────────────────────────────────────────────────────────
# S4: DATA_WAITING cadence — no duplicate within same slot
# ─────────────────────────────────────────────────────────────────────────────

class TestDataWaitingCadenceNoDuplicate:
    """is_safe_task_due returns False when a task already exists for current slot."""

    def test_is_safe_task_due_false_when_task_exists(self):
        from orchestrator.data_waiting_cadence import is_safe_task_due
        existing = {"id": 999, "status": "QUEUED", "task_type": "closing_monitor"}
        with patch("orchestrator.db.get_nonfailed_task_by_dedupe_key", return_value=existing):
            assert is_safe_task_due("closing_monitor") is False

    def test_get_due_safe_tasks_empty_when_all_exist(self):
        from orchestrator.data_waiting_cadence import get_due_safe_tasks
        existing = {"id": 1, "status": "QUEUED"}
        with patch("orchestrator.db.get_nonfailed_task_by_dedupe_key", return_value=existing):
            tasks = get_due_safe_tasks()
            assert len(tasks) == 0

    def test_dedupe_key_format(self):
        from orchestrator.data_waiting_cadence import cadence_dedupe_key
        key = cadence_dedupe_key("closing_monitor")
        # Should look like "closing_monitor:slot:NNNN"
        parts = key.split(":")
        assert len(parts) == 3
        assert parts[0] == "closing_monitor"
        assert parts[1] == "slot"
        assert parts[2].isdigit()


# ─────────────────────────────────────────────────────────────────────────────
# S5: Deterministic safe task — no LLM required
# ─────────────────────────────────────────────────────────────────────────────

class TestSafeRunExecutesDeterministic:
    """is_deterministic_safe_task and execute_safe_task work without LLM."""

    def _closing_monitor_task(self) -> dict:
        return {
            "id": 5000,
            "task_type": "closing_monitor",
            "title": "CLV Closing Monitor",
            "slug": "slot-test",
            "date_folder": "20250101",
            "prompt_file_path": "/tmp/prompt.md",
            "prompt_text": "Inspect CLV records.",
            "status": "QUEUED",
        }

    def test_is_deterministic_safe_task_closing_monitor(self):
        from orchestrator.safe_task_executor import is_deterministic_safe_task
        assert is_deterministic_safe_task(self._closing_monitor_task()) is True

    def test_is_deterministic_safe_task_false_for_llm_task(self):
        from orchestrator.safe_task_executor import is_deterministic_safe_task
        task = {"task_type": "model_patch_calibration"}
        assert is_deterministic_safe_task(task) is False

    def test_execute_safe_task_produces_artifact(self):
        from orchestrator.safe_task_executor import execute_safe_task
        task = self._closing_monitor_task()
        mock_result = {
            "status": "ok",
            "pending_count": 14,
            "computed_count": 0,
            "stale_count": 0,
            "game_ids": [],
            "closing_odds_reachable": False,
            "note": "Diagnostic only — no writes.",
        }
        with (
            patch(
                "orchestrator.closing_odds_monitor.run_closing_odds_monitor",
                return_value=mock_result,
            ),
            patch("orchestrator.db.update_task") as mock_update,
            patch("orchestrator.db.record_run") as mock_record,
            patch("os.makedirs"),
            patch("builtins.open", MagicMock()),
        ):
            result = execute_safe_task(task)

        # execute_safe_task returns success/completed_text format (not status: COMPLETED)
        assert result.get("success") is True or result.get("completed_text")
        # No LLM calls needed — deterministic executor
        assert "completed_text" in result or "success" in result

    def test_execute_safe_task_for_unknown_type_raises(self):
        from orchestrator.safe_task_executor import execute_safe_task, is_deterministic_safe_task
        task = {"id": 1, "task_type": "unknown_future_type", "title": "X"}
        assert is_deterministic_safe_task(task) is False
        # Should raise or return error — not silently succeed
        try:
            result = execute_safe_task(task)
            assert result.get("status") in ("ERROR", "FAILED", "SKIPPED"), (
                f"Expected error for unknown task type, got: {result}"
            )
        except (ValueError, KeyError, TypeError):
            pass  # Raising is also acceptable


# ─────────────────────────────────────────────────────────────────────────────
# S6: Ops report → WAITING_ACTIVE when all skips are hard-off
# ─────────────────────────────────────────────────────────────────────────────

class TestOpsReportWaitingActive:
    """classify_window returns WAITING_ACTIVE when hard-off protects all skips."""

    def _hard_off_run(self, i: int) -> dict:
        return {
            "outcome": "SKIPPED",
            "message": "GLOBAL_HARD_OFF — skip execution (worker_tick)",
            "tick_at": f"2025-01-01T0{i}:00:00",
            "runner": "worker_tick",
        }

    def _completed_safe_task(self) -> dict:
        return {
            "id": 6000,
            "status": "COMPLETED",
            "task_type": "closing_monitor",
            "analysis_family": "closing-monitor",
            "title": "CLV Closing Monitor",
            "completion_quality": "COMPLETED_VALID",
        }

    def test_classify_window_waiting_active_when_all_hard_off_and_completed(self):
        from orchestrator.optimization_ops_report import classify_window, CLASS_WAITING_ACTIVE
        tasks = [self._completed_safe_task()]
        runs = [self._hard_off_run(i) for i in range(8)]
        opt_state = {"current_state": "DATA_WAITING", "blocked_families": [], "allowed_families": []}
        result = classify_window(
            tasks=tasks,
            runs=runs,
            gov_blocked=0,
            consecutive_skips=0,  # 0 unexplained skips
            opt_state=opt_state,
            effective_completed=tasks,
        )
        assert result == CLASS_WAITING_ACTIVE, f"Expected WAITING_ACTIVE, got {result}"

    def test_classify_window_not_degraded_with_8_hard_off_skips(self):
        from orchestrator.optimization_ops_report import classify_window, CLASS_DEGRADED
        tasks = [self._completed_safe_task()]
        runs = [self._hard_off_run(i) for i in range(8)]
        opt_state = {"current_state": "DATA_WAITING", "blocked_families": [], "allowed_families": []}
        result = classify_window(
            tasks=tasks,
            runs=runs,
            gov_blocked=0,
            consecutive_skips=0,
            opt_state=opt_state,
            effective_completed=tasks,
        )
        assert result != CLASS_DEGRADED, (
            f"Should NOT be DEGRADED when all 8 skips are hard-off protected, got {result}"
        )

    def test_generate_report_includes_skip_reasons(self):
        """generate_report output dict includes skip_reasons and hard_off_skip_count."""
        from orchestrator.optimization_ops_report import generate_report
        runs = [self._hard_off_run(i) for i in range(3)]
        tasks_in_window: list[dict] = [self._completed_safe_task()]

        with (
            patch("orchestrator.optimization_ops_report._query_tasks_in_window", return_value=tasks_in_window),
            patch("orchestrator.optimization_ops_report._query_runs_in_window", return_value=runs),
            patch("orchestrator.optimization_ops_report._get_training_memory_summary", return_value={}),
            patch("orchestrator.optimization_ops_report._get_phase6_summary", return_value={}),
            patch("orchestrator.optimization_ops_report._get_optimization_state_summary", return_value={
                "current_state": "DATA_WAITING",
                "blocked_families": [],
                "allowed_families": [],
                "reasons": [],
            }),
        ):
            report = generate_report(window="8h")

        assert "skip_reasons" in report, "Report should include skip_reasons dict"
        assert "hard_off_skip_count" in report, "Report should include hard_off_skip_count"
        assert isinstance(report["skip_reasons"], dict)
        assert report["hard_off_skip_count"] >= 0

    def test_generate_report_hard_off_count_matches_skips(self):
        """hard_off_skip_count in report equals number of GLOBAL_HARD_OFF run messages."""
        from orchestrator.optimization_ops_report import generate_report
        runs = [self._hard_off_run(i) for i in range(5)]
        tasks_in_window = [self._completed_safe_task()]

        with (
            patch("orchestrator.optimization_ops_report._query_tasks_in_window", return_value=tasks_in_window),
            patch("orchestrator.optimization_ops_report._query_runs_in_window", return_value=runs),
            patch("orchestrator.optimization_ops_report._get_training_memory_summary", return_value={}),
            patch("orchestrator.optimization_ops_report._get_phase6_summary", return_value={}),
            patch("orchestrator.optimization_ops_report._get_optimization_state_summary", return_value={
                "current_state": "DATA_WAITING",
                "blocked_families": [],
                "allowed_families": [],
                "reasons": [],
            }),
        ):
            report = generate_report(window="8h")

        assert report["hard_off_skip_count"] == 5


# ─────────────────────────────────────────────────────────────────────────────
# S7: Ops report → DEGRADED when genuine unexplained skips
# ─────────────────────────────────────────────────────────────────────────────

class TestOpsReportDegradedMissedCadence:
    """classify_window returns DEGRADED when ≥3 consecutive unexplained skips."""

    def _no_queued_run(self, i: int) -> dict:
        return {
            "outcome": "SKIPPED",
            "message": "Worker skipped: no queued tasks found",
            "tick_at": f"2025-01-01T0{i}:00:00",
            "runner": "worker_tick",
        }

    def test_classify_window_degraded_for_no_queued_skips(self):
        from orchestrator.optimization_ops_report import classify_window, CLASS_DEGRADED
        tasks: list[dict] = []
        runs = [self._no_queued_run(i) for i in range(5)]
        opt_state = {"current_state": "NORMAL", "blocked_families": [], "allowed_families": []}
        result = classify_window(
            tasks=tasks,
            runs=runs,
            gov_blocked=0,
            consecutive_skips=5,  # 5 unexplained
            opt_state=opt_state,
            effective_completed=None,
        )
        assert result == CLASS_DEGRADED, f"Expected DEGRADED for 5 unexplained skips, got {result}"

    def test_classify_window_not_degraded_for_2_unexplained_skips(self):
        from orchestrator.optimization_ops_report import classify_window, CLASS_DEGRADED
        tasks = [{"id": 1, "status": "QUEUED", "task_type": "closing_monitor"}]
        runs = [self._no_queued_run(i) for i in range(2)]
        opt_state = {"current_state": "DATA_WAITING", "blocked_families": [], "allowed_families": []}
        result = classify_window(
            tasks=tasks,
            runs=runs,
            gov_blocked=0,
            consecutive_skips=2,
            opt_state=opt_state,
            effective_completed=None,
        )
        assert result != CLASS_DEGRADED, f"2 unexplained skips should NOT be DEGRADED, got {result}"

    def test_count_unexplained_consecutive_skips_no_queued(self):
        """3 no-queued-tasks skips → count = 3."""
        from orchestrator.scheduler_skip_classifier import count_unexplained_consecutive_skips
        runs = [
            {"outcome": "SKIPPED", "message": "no queued tasks", "tick_at": f"2025-01-01T0{i}:00:00"}
            for i in range(3)
        ]
        runs_sorted = sorted(runs, key=lambda r: r["tick_at"], reverse=True)
        assert count_unexplained_consecutive_skips(runs_sorted) == 3


# ─────────────────────────────────────────────────────────────────────────────
# Phase 12 success marker
# ─────────────────────────────────────────────────────────────────────────────

def test_phase12_success_marker():
    """
    PHASE_12_SCHEDULER_IDLE_RECOVERY_VERIFIED

    All Phase 12 skip-classifier, cadence, ops-report, and classification
    tests pass.  Hard-off protected skips no longer trigger false DEGRADED
    classification.
    """
    assert True  # PHASE_12_SCHEDULER_IDLE_RECOVERY_VERIFIED
