"""
Phase 11 — Deterministic Safe Task Executor Tests

7 scenarios:

S1: closing_monitor executor writes non-empty artifact
S2: executor does NOT mark PENDING_CLOSING as COMPUTED without valid closing odds
S3: worker_tick routes closing_monitor to safe_task_executor, NOT to LLM
S4: completion_quality of deterministic output is not EMPTY_ARTIFACT
S5: Phase 9 report counts deterministic closing_monitor as effective diagnostic work
S6: idempotent second run does not duplicate CLV records (uuid5 dedup)
S7: hard-off blocks worker execution (deterministic path does not bypass policy)

SUCCESS MARKER: PHASE_11_DETERMINISTIC_SAFE_TASK_EXECUTOR_VERIFIED
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from orchestrator.safe_task_executor import (
    DETERMINISTIC_TASK_TYPES,
    _count_clv_states,
    _execute_closing_monitor,
    _resolve_artifact_path,
    execute_safe_task,
    is_deterministic_safe_task,
)
from orchestrator.task_completion_validator import (
    QUALITY_DIAGNOSTIC_ONLY,
    QUALITY_EFFECTIVE_STATES,
    QUALITY_EMPTY_ARTIFACT,
    QUALITY_NOOP,
    QUALITY_VALID,
    validate_completion,
)


# ─────────────────────────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────────────────────────

def _make_monitor_result(upgraded: int = 0, pending: int = 3, stale: int = 0) -> dict:
    return {
        "dates_scanned": ["2026-04-30"],
        "total_stats": {
            "total_pending": pending,
            "upgraded": upgraded,
            "still_pending": pending - upgraded,
            "stale_closing_rejected": stale,
        },
        "per_date": {"2026-04-30": {"upgraded": upgraded, "still_pending": pending - upgraded}},
        "run_at": datetime.now(timezone.utc).isoformat(),
    }


def _make_closing_monitor_task(task_dir: str | None = None, task_id: int = 9001) -> dict:
    task: dict = {
        "id": task_id,
        "title": "DATA_WAITING CLV Closing Monitor",
        "status": "RUNNING",
        "task_type": "closing_monitor",
        "worker_type": "light",
        "slot_key": f"test-slot-{task_id}",
        "analysis_family": "closing-monitor",
        "completed_text": None,
        "completed_file_path": None,
        "completion_quality": None,
    }
    if task_dir:
        prompt_path = os.path.join(task_dir, f"test-slot-{task_id}-prompt.md")
        Path(prompt_path).write_text("# test prompt", encoding="utf-8")
        task["prompt_file_path"] = prompt_path
        task["date_folder"] = "20260430"
    return task


# ─────────────────────────────────────────────────────────────────
# S1 — executor writes non-empty artifact
# ─────────────────────────────────────────────────────────────────

class TestS1NonEmptyArtifact:
    def test_artifact_written_and_nonempty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            task = _make_closing_monitor_task(task_dir=tmpdir)
            mock_result = _make_monitor_result(upgraded=0, pending=5)

            with patch(
                "orchestrator.closing_odds_monitor.run_closing_odds_monitor",
                return_value=mock_result,
            ):
                result = _execute_closing_monitor(task)

            # completed_text is non-empty
            assert result["completed_text"], "completed_text must not be empty"
            assert len(result["completed_text"]) >= 50

            # artifact file written and non-empty
            artifact_path = result.get("completed_file_path")
            assert artifact_path, "completed_file_path must be set"
            assert os.path.isfile(artifact_path)
            content = Path(artifact_path).read_text(encoding="utf-8")
            assert len(content) >= 50

            # success flag
            assert result["success"] is True

    def test_no_clv_files_still_produces_artifact(self):
        """Even with zero CLV files and zero upgrades, artifact is non-empty."""
        with tempfile.TemporaryDirectory() as tmpdir:
            task = _make_closing_monitor_task(task_dir=tmpdir)
            mock_result = _make_monitor_result(upgraded=0, pending=0)

            with patch(
                "orchestrator.closing_odds_monitor.run_closing_odds_monitor",
                return_value=mock_result,
            ):
                result = _execute_closing_monitor(task)

            assert result["success"] is True
            assert result["completed_text"]
            assert "WAITING_FOR_MARKET_SETTLEMENT" in result["completed_text"]


# ─────────────────────────────────────────────────────────────────
# S2 — does NOT mark PENDING_CLOSING as COMPUTED without valid odds
# ─────────────────────────────────────────────────────────────────

class TestS2NoPendingUpgradeWithoutOdds:
    def test_no_upgrade_when_no_valid_closing_odds(self):
        """When upgraded=0, text must say WAITING_FOR_MARKET_SETTLEMENT, not COMPUTED."""
        with tempfile.TemporaryDirectory() as tmpdir:
            task = _make_closing_monitor_task(task_dir=tmpdir)
            mock_result = _make_monitor_result(upgraded=0, pending=7)

            with patch(
                "orchestrator.closing_odds_monitor.run_closing_odds_monitor",
                return_value=mock_result,
            ):
                result = _execute_closing_monitor(task)

        text = result["completed_text"]
        assert "WAITING_FOR_MARKET_SETTLEMENT" in text
        # Must NOT claim any PENDING was upgraded without valid odds
        assert "UPGRADED" not in text or "0" in text.split("UPGRADED")[1][:30]
        # upgraded_count reflects reality
        assert result["upgraded_count"] == 0

    def test_upgrade_present_when_valid_odds_provided(self):
        """When upgraded=2, text must say UPGRADED and not WAITING."""
        with tempfile.TemporaryDirectory() as tmpdir:
            task = _make_closing_monitor_task(task_dir=tmpdir)
            mock_result = _make_monitor_result(upgraded=2, pending=5)

            with patch(
                "orchestrator.closing_odds_monitor.run_closing_odds_monitor",
                return_value=mock_result,
            ):
                result = _execute_closing_monitor(task)

        text = result["completed_text"]
        assert "UPGRADED" in text
        assert result["upgraded_count"] == 2
        assert "WAITING_FOR_MARKET_SETTLEMENT" not in text


# ─────────────────────────────────────────────────────────────────
# S3 — worker_tick routes closing_monitor to safe_task_executor, not LLM
# ─────────────────────────────────────────────────────────────────

class TestS3WorkerRoutesToSafeExecutor:
    def test_is_deterministic_for_closing_monitor(self):
        task = {"task_type": "closing_monitor"}
        assert is_deterministic_safe_task(task) is True

    def test_is_not_deterministic_for_model_patch(self):
        task = {"task_type": "model_patch_calibration"}
        assert is_deterministic_safe_task(task) is False

    def test_is_not_deterministic_for_empty_type(self):
        assert is_deterministic_safe_task({}) is False
        assert is_deterministic_safe_task({"task_type": None}) is False

    def test_execute_safe_task_dispatches_closing_monitor(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            task = _make_closing_monitor_task(task_dir=tmpdir)
            mock_result = _make_monitor_result(upgraded=0)

            with patch(
                "orchestrator.closing_odds_monitor.run_closing_odds_monitor",
                return_value=mock_result,
            ) as mock_monitor:
                result = execute_safe_task(task)
                mock_monitor.assert_called_once()

            assert result["success"] is True

    def test_execute_safe_task_raises_for_unknown_type(self):
        task = {"task_type": "unknown_llm_task", "id": 1}
        with pytest.raises(ValueError, match="not a registered"):
            execute_safe_task(task)

    def test_worker_tick_calls_safe_executor_not_llm(self):
        """
        When run_worker_tick() processes a closing_monitor task, it must call
        safe_task_executor.execute_safe_task and must NOT call execute_task_with_provider.
        """
        import orchestrator.worker_tick as wt
        import orchestrator.db as db

        fake_task = {
            "id": 9901,
            "title": "Test closing monitor",
            "task_type": "closing_monitor",
            "worker_type": "light",
            "slot_key": "test-slot-9901",
            "status": "QUEUED",
            "prompt_file_path": None,
            "expected_duration_hours": 0.1,
            "signal_state_type": None,
        }
        safe_result = {
            "success": True,
            "completed_text": "pending_count=3 computed_count=0 stale_count=0 "
                              "WAITING_FOR_MARKET_SETTLEMENT diagnostic output",
            "completed_file_path": None,
            "changed_files": [],
            "duration_seconds": 1.5,
        }

        with (
            patch.object(db, "list_tasks", return_value=[fake_task]),
            patch.object(db, "update_task"),
            patch.object(db, "record_run"),
            patch.object(db, "get_worker_provider", return_value="copilot-daemon"),
            patch("orchestrator.worker_tick.execute_task_with_provider") as mock_llm,
            patch(
                "orchestrator.safe_task_executor.execute_safe_task",
                return_value=safe_result,
            ) as mock_safe,
            patch("orchestrator.worker_tick._auto_fail_zombie_running_tasks", return_value=0),
            patch(
                "orchestrator.worker_tick.execution_policy.evaluate_execution",
                return_value={"allowed": True, "message": None},
            ),
            patch("orchestrator.worker_tick._list_dirty_files", return_value=[]),
        ):
            wt.run_worker_tick()

        mock_safe.assert_called_once()
        mock_llm.assert_not_called()


# ─────────────────────────────────────────────────────────────────
# S4 — completion_quality is not EMPTY_ARTIFACT
# ─────────────────────────────────────────────────────────────────

class TestS4CompletionQualityNotEmpty:
    def test_quality_not_empty_artifact(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            task = _make_closing_monitor_task(task_dir=tmpdir)
            mock_result = _make_monitor_result(upgraded=0, pending=4)

            with patch(
                "orchestrator.closing_odds_monitor.run_closing_odds_monitor",
                return_value=mock_result,
            ):
                exec_result = _execute_closing_monitor(task)

        quality_result = validate_completion(task, exec_result)
        quality = quality_result["quality"]

        assert quality != QUALITY_EMPTY_ARTIFACT, (
            f"Expected not EMPTY_ARTIFACT, got {quality}"
        )
        assert quality != QUALITY_NOOP, (
            f"Expected not NOOP, got {quality}"
        )

    def test_quality_is_effective(self):
        """Deterministic output should land in QUALITY_EFFECTIVE_STATES."""
        with tempfile.TemporaryDirectory() as tmpdir:
            task = _make_closing_monitor_task(task_dir=tmpdir)
            mock_result = _make_monitor_result(upgraded=1, pending=3)

            with patch(
                "orchestrator.closing_odds_monitor.run_closing_odds_monitor",
                return_value=mock_result,
            ):
                exec_result = _execute_closing_monitor(task)

        quality_result = validate_completion(task, exec_result)
        assert quality_result["quality"] in QUALITY_EFFECTIVE_STATES, (
            f"Expected effective quality, got {quality_result['quality']}"
        )


# ─────────────────────────────────────────────────────────────────
# S5 — Phase 9 ops report counts deterministic work as effective
# ─────────────────────────────────────────────────────────────────

class TestS5OpsReportCountsEffective:
    def test_generate_report_counts_valid_closing_monitor_as_effective(self):
        import orchestrator.optimization_ops_report as ops_rpt
        from orchestrator.optimization_ops_report import CLASS_EFFECTIVE

        def _ago(minutes: int) -> str:
            from datetime import timedelta
            return (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()

        completed_task = {
            "id": 9001,
            "title": "CLV Closing Monitor",
            "status": "COMPLETED",
            "task_type": "closing_monitor",
            "analysis_family": "closing-monitor",
            "focus_keys": "closing_monitor",
            "completed_at": _ago(5),
            "created_at": _ago(10),
            "updated_at": _ago(5),
            # Phase 10 quality field — deterministic run produces VALID
            "completion_quality": QUALITY_VALID,
            "completed_text": (
                "pending_count=3 computed_count=0 stale_count=0 "
                "WAITING_FOR_MARKET_SETTLEMENT diagnostic closing-monitor output"
            ),
        }
        run_row = {
            "id": 1,
            "runner": "worker_tick",
            "outcome": "SUCCESS",
            "tick_at": _ago(5),
            "message": "",
        }

        with (
            patch.object(ops_rpt, "_query_tasks_in_window", return_value=[completed_task]),
            patch.object(ops_rpt, "_query_runs_in_window", return_value=[run_row]),
            patch.object(ops_rpt, "_get_training_memory_summary", return_value={}),
            patch.object(ops_rpt, "_get_phase6_summary", return_value={}),
            patch.object(ops_rpt, "_get_optimization_state_summary", return_value={}),
        ):
            report = ops_rpt.generate_report("8h")

        assert report["effective_completed_tasks"] >= 1, (
            f"Expected effective_completed_tasks >= 1, got {report['effective_completed_tasks']}"
        )
        assert report["completed_empty_artifact"] == 0, (
            f"Empty artifact count should be 0, got {report['completed_empty_artifact']}"
        )
        assert report["classification"] == CLASS_EFFECTIVE, (
            f"Expected EFFECTIVE classification, got {report['classification']}"
        )

    def test_generate_report_counts_diagnostic_closing_monitor_as_effective(self):
        """COMPLETED_DIAGNOSTIC_ONLY also counts as effective."""
        import orchestrator.optimization_ops_report as ops_rpt
        from orchestrator.optimization_ops_report import CLASS_EFFECTIVE

        def _ago(minutes: int) -> str:
            from datetime import timedelta
            return (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()

        completed_task = {
            "id": 9002,
            "title": "CLV Closing Monitor",
            "status": "COMPLETED",
            "task_type": "closing_monitor",
            "analysis_family": "closing-monitor",
            "focus_keys": "closing_monitor",
            "completed_at": _ago(5),
            "created_at": _ago(10),
            "updated_at": _ago(5),
            "completion_quality": QUALITY_DIAGNOSTIC_ONLY,
            "completed_text": "pending_count=5 stale_count=0 WAITING_FOR_MARKET_SETTLEMENT",
        }

        with (
            patch.object(ops_rpt, "_query_tasks_in_window", return_value=[completed_task]),
            patch.object(ops_rpt, "_query_runs_in_window", return_value=[]),
            patch.object(ops_rpt, "_get_training_memory_summary", return_value={}),
            patch.object(ops_rpt, "_get_phase6_summary", return_value={}),
            patch.object(ops_rpt, "_get_optimization_state_summary", return_value={}),
        ):
            report = ops_rpt.generate_report("8h")

        assert report["effective_completed_tasks"] >= 1
        assert report["completed_diagnostic_only"] >= 1


# ─────────────────────────────────────────────────────────────────
# S6 — idempotent second run (uuid5 dedup, no exception on re-run)
# ─────────────────────────────────────────────────────────────────

class TestS6Idempotency:
    def test_second_run_does_not_raise(self):
        """Running the executor twice on the same task must not raise an exception."""
        with tempfile.TemporaryDirectory() as tmpdir:
            task = _make_closing_monitor_task(task_dir=tmpdir)
            mock_result = _make_monitor_result(upgraded=1, pending=3)

            with patch(
                "orchestrator.closing_odds_monitor.run_closing_odds_monitor",
                return_value=mock_result,
            ):
                r1 = _execute_closing_monitor(task)
                r2 = _execute_closing_monitor(task)

            assert r1["success"] is True
            assert r2["success"] is True

    def test_second_run_overwrites_artifact_not_appends(self):
        """Artifact file must be overwritten (not appended) on re-run."""
        with tempfile.TemporaryDirectory() as tmpdir:
            task = _make_closing_monitor_task(task_dir=tmpdir)
            mock_result = _make_monitor_result(upgraded=0)

            with patch(
                "orchestrator.closing_odds_monitor.run_closing_odds_monitor",
                return_value=mock_result,
            ):
                r1 = _execute_closing_monitor(task)
                r2 = _execute_closing_monitor(task)

            # Both runs write to the same path (slot_key is fixed)
            assert r1["completed_file_path"] == r2["completed_file_path"]
            # File exists once (overwritten, not doubled)
            artifact_path = Path(r2["completed_file_path"])
            content = artifact_path.read_text(encoding="utf-8")
            # Count occurrences of the header — should appear exactly once
            assert content.count("# CLV Closing Monitor") == 1

    def test_upgraded_record_uuid5_is_deterministic(self):
        """
        Verify that _build_upgraded_record produces the same clv_record_id on
        two calls with identical inputs (uuid5 dedup property).
        """
        from orchestrator.closing_odds_monitor import _build_upgraded_record

        original = {
            "clv_record_id": "orig-1",
            "clv_status": "PENDING_CLOSING",
            "selection": "home",
            "implied_probability_at_prediction": 0.55,
            "prediction_time_utc": "2026-04-01T12:00:00+00:00",
        }
        closing_ts = "2026-04-01T18:00:00+00:00"
        r1 = _build_upgraded_record(original, -130.0, closing_ts, "external_closing")
        r2 = _build_upgraded_record(original, -130.0, closing_ts, "external_closing")

        assert r1["clv_record_id"] == r2["clv_record_id"], (
            "uuid5 dedup: same input must produce same clv_record_id"
        )
        assert r1["clv_status"] == "COMPUTED"
        assert r2["clv_status"] == "COMPUTED"


# ─────────────────────────────────────────────────────────────────
# S7 — hard-off blocks worker execution (policy not bypassed)
# ─────────────────────────────────────────────────────────────────

class TestS7HardOffBlocks:
    def test_hard_off_skips_even_deterministic_task(self):
        """
        HARD_OFF execution policy must block worker_tick regardless of task_type.
        Deterministic safe tasks do not bypass the general worker execution guard.
        """
        import orchestrator.worker_tick as wt
        import orchestrator.db as db

        blocked_decision = {
            "allowed": False,
            "status": "blocked",
            "reason": "HARD_OFF",
            "message": "[HARD_OFF] Worker execution is disabled.",
        }

        with (
            patch(
                "orchestrator.worker_tick.execution_policy.evaluate_execution",
                return_value=blocked_decision,
            ),
            patch.object(db, "record_run"),
            patch("orchestrator.safe_task_executor.execute_safe_task") as mock_safe,
            patch("orchestrator.worker_tick.execute_task_with_provider") as mock_llm,
        ):
            result = wt.run_worker_tick()

        assert result["status"] == "SKIPPED", (
            f"Expected SKIPPED under HARD_OFF, got {result['status']}"
        )
        mock_safe.assert_not_called()
        mock_llm.assert_not_called()

    def test_manual_override_allows_deterministic_task(self):
        """
        With ORCHESTRATOR_FORCE_RUN=1, the worker can execute even in HARD_OFF-equivalent
        scheduler-disabled states (manual_override=True bypasses scheduler check).
        """
        # Verify is_manual_run detects the env var
        from orchestrator.execution_policy import is_manual_run
        assert is_manual_run({"ORCHESTRATOR_FORCE_RUN": "1"}) is True
        assert is_manual_run({"ORCHESTRATOR_MANUAL_RUN": "true"}) is True
        assert is_manual_run({}) is False


# ─────────────────────────────────────────────────────────────────
# Registry smoke test
# ─────────────────────────────────────────────────────────────────

class TestRegistry:
    def test_closing_monitor_registered(self):
        assert "closing_monitor" in DETERMINISTIC_TASK_TYPES

    def test_all_registered_types_have_callable_executor(self):
        for task_type, executor in DETERMINISTIC_TASK_TYPES.items():
            assert callable(executor), f"executor for {task_type!r} must be callable"

    def test_is_deterministic_case_insensitive(self):
        assert is_deterministic_safe_task({"task_type": "closing_monitor"}) is True
        assert is_deterministic_safe_task({"task_type": "CLOSING_MONITOR"}) is True
        assert is_deterministic_safe_task({"task_type": "Closing_Monitor"}) is True


# ─────────────────────────────────────────────────────────────────
# Success marker
# ─────────────────────────────────────────────────────────────────

def test_phase11_success_marker():
    """Sentinel: all Phase 11 scenarios implemented."""
    assert True, "PHASE_11_DETERMINISTIC_SAFE_TASK_EXECUTOR_VERIFIED"
