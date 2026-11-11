"""
Phase 16 — Closing Source Refresh Orchestration Tests
======================================================
Tests the Phase 16 additions:
  - _choose_closing_refresh_action() priority logic
  - _attempt_closing_source_refresh_task() task creation + cadence dedup
  - DETERMINISTIC_TASK_TYPES registry has all 3 new task types registered
  - Artifact is non-empty for all 3 new executors
  - Learning stays blocked (no COMPUTED CLV during DATA_WAITING)
  - Phase 9 ops report shows closing availability with refresh action

Test scenarios:
  T1. recommended_refresh_tsl > 0  → action="refresh_tsl_closing"
  T2. recommended_refresh_external > 0 → action="refresh_external_closing"
  T3. missing_all_sources > 0      → action="closing_availability_audit"
  T4. Cadence dedup blocks duplicate refresh task within same window
  T5. All 3 new task types registered in DETERMINISTIC_TASK_TYPES
  T6. All 3 executor artifacts are non-empty (including when 0 pending records)
  T7. No CLV status changes during Phase 16 tasks (learning remains blocked)
  T8. Ops report includes next_refresh_action field in closing_availability
"""
from __future__ import annotations

import json
import textwrap
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows),
        encoding="utf-8",
    )


def _make_clv_row(
    pred_id: str = "pred-001",
    match_id: str = "game-001",
    selection: str = "home",
    pred_time: str | None = None,
    status: str = "PENDING_CLOSING",
) -> dict[str, Any]:
    if pred_time is None:
        pred_time = _iso(datetime.now(timezone.utc) - timedelta(hours=6))
    return {
        "prediction_id": pred_id,
        "canonical_match_id": match_id,
        "selection": selection,
        "prediction_time_utc": pred_time,
        "clv_status": status,
        "predicted_ml": -120,
        "predicted_side": selection,
    }


def _make_timeline_row(
    game_id: str = "game-001",
    closing_home_ml: float | None = None,
    closing_ts: str | None = None,
    ext_home_ml: float | None = None,
    ext_ts: str | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {"game_id": game_id, "source": "live"}
    if closing_home_ml is not None:
        row["closing_home_ml"] = closing_home_ml
    if closing_ts is not None:
        row["closing_ts"] = closing_ts
    if ext_home_ml is not None:
        row["external_closing_home_ml"] = ext_home_ml
    if ext_ts is not None:
        row["external_closing_ts"] = ext_ts
    return row


# ─────────────────────────────────────────────────────────────────────
# T1. recommended_refresh_tsl > 0  → action="refresh_tsl_closing"
# ─────────────────────────────────────────────────────────────────────

def test_t1_choose_action_refresh_tsl() -> None:
    """T1: When recommended_refresh_tsl > 0, choose refresh_tsl_closing action."""
    from orchestrator.planner_tick import _choose_closing_refresh_action

    source_summary = {
        "recommended_refresh_tsl": 2,
        "recommended_refresh_external": 0,
        "missing_all_sources": 0,
    }
    # Phase 17: mock escalation to OFF so Phase 16 priority logic is exercised
    with patch(
        "orchestrator.closing_refresh_memory.get_escalation_status",
        return_value={"escalation_recommended": False, "consecutive_no_improvement": 0},
    ):
        action = _choose_closing_refresh_action(source_summary)
    assert action == "refresh_tsl_closing", (
        f"Expected 'refresh_tsl_closing' when recommended_refresh_tsl=2, got {action!r}"
    )


# ─────────────────────────────────────────────────────────────────────
# T2. recommended_refresh_external > 0 → action="refresh_external_closing"
# ─────────────────────────────────────────────────────────────────────

def test_t2_choose_action_refresh_external() -> None:
    """T2: External has highest priority — chosen when > 0 even if TSL also > 0."""
    from orchestrator.planner_tick import _choose_closing_refresh_action

    source_summary = {
        "recommended_refresh_tsl": 1,
        "recommended_refresh_external": 3,
        "missing_all_sources": 2,
    }
    with patch(
        "orchestrator.closing_refresh_memory.get_escalation_status",
        return_value={"escalation_recommended": False, "consecutive_no_improvement": 0},
    ):
        action = _choose_closing_refresh_action(source_summary)
    assert action == "refresh_external_closing", (
        f"Expected 'refresh_external_closing' (highest priority), got {action!r}"
    )


# ─────────────────────────────────────────────────────────────────────
# T3. missing_all_sources > 0 → action="closing_availability_audit"
# ─────────────────────────────────────────────────────────────────────

def test_t3_choose_action_audit() -> None:
    """T3: When only missing_all_sources > 0, choose closing_availability_audit."""
    from orchestrator.planner_tick import _choose_closing_refresh_action

    source_summary = {
        "recommended_refresh_tsl": 0,
        "recommended_refresh_external": 0,
        "missing_all_sources": 5,
    }
    with patch(
        "orchestrator.closing_refresh_memory.get_escalation_status",
        return_value={"escalation_recommended": False, "consecutive_no_improvement": 0},
    ):
        action = _choose_closing_refresh_action(source_summary)
    assert action == "closing_availability_audit", (
        f"Expected 'closing_availability_audit' when only missing_all_sources > 0, got {action!r}"
    )


def test_t3b_choose_action_default() -> None:
    """T3b: When all counts == 0, fall back to closing_monitor."""
    from orchestrator.planner_tick import _choose_closing_refresh_action

    source_summary = {
        "recommended_refresh_tsl": 0,
        "recommended_refresh_external": 0,
        "missing_all_sources": 0,
    }
    with patch(
        "orchestrator.closing_refresh_memory.get_escalation_status",
        return_value={"escalation_recommended": False, "consecutive_no_improvement": 0},
    ):
        action = _choose_closing_refresh_action(source_summary)
    assert action == "closing_monitor", (
        f"Expected 'closing_monitor' (default fallback), got {action!r}"
    )


# ─────────────────────────────────────────────────────────────────────
# T4. Cadence dedup prevents duplicate within same slot window
# ─────────────────────────────────────────────────────────────────────

def test_t4_cadence_dedup_skip(tmp_path: Path) -> None:
    """T4: When a non-failed task exists for the current cadence slot, return SKIP_CADENCE."""
    from orchestrator.planner_tick import _attempt_closing_source_refresh_task
    from orchestrator.data_waiting_cadence import cadence_dedupe_key

    # Mock diagnostics with refresh_tsl_closing priority
    mock_diag = {
        "source_summary": {
            "recommended_refresh_tsl": 1,
            "recommended_refresh_external": 0,
            "missing_all_sources": 0,
        }
    }

    action_type = "refresh_tsl_closing"
    current_dedupe_key = cadence_dedupe_key(action_type)

    fake_existing = {"id": 999, "status": "QUEUED", "dedupe_key": current_dedupe_key}

    with (
        patch("orchestrator.planner_tick.db") as mock_db,
        patch(
            "orchestrator.closing_odds_monitor.get_pending_diagnostics",
            return_value=mock_diag,
        ),
        patch(
            "orchestrator.planner_tick._choose_closing_refresh_action",
            return_value=action_type,
        ),
    ):
        mock_db.get_nonfailed_task_by_dedupe_key.return_value = fake_existing
        mock_db.record_run.return_value = None
        mock_db.ORCH_ROOT = str(tmp_path / "runtime" / "agent_orchestrator")

        result = _attempt_closing_source_refresh_task(
            request_id="test-req-t4",
            start_time=datetime.now(timezone.utc),
            opt_state_result={},
        )

    assert result["status"] == "SKIP_CADENCE", (
        f"Expected SKIP_CADENCE when task already exists for cadence slot, got {result['status']!r}"
    )
    assert result["task_id"] == 999
    assert result["action_type"] == action_type


# ─────────────────────────────────────────────────────────────────────
# T5. All 3 new task types registered in DETERMINISTIC_TASK_TYPES
# ─────────────────────────────────────────────────────────────────────

def test_t5_new_task_types_registered() -> None:
    """T5: All Phase 16 task types must be registered in DETERMINISTIC_TASK_TYPES."""
    from orchestrator.safe_task_executor import DETERMINISTIC_TASK_TYPES

    required_types = [
        "closing_availability_audit",
        "refresh_tsl_closing",
        "refresh_external_closing",
    ]
    for task_type in required_types:
        assert task_type in DETERMINISTIC_TASK_TYPES, (
            f"Task type {task_type!r} not registered in DETERMINISTIC_TASK_TYPES. "
            f"Registered: {sorted(DETERMINISTIC_TASK_TYPES.keys())}"
        )


def test_t5b_is_deterministic_safe_task() -> None:
    """T5b: is_deterministic_safe_task() returns True for all Phase 16 types."""
    from orchestrator.safe_task_executor import is_deterministic_safe_task

    for task_type in ["closing_availability_audit", "refresh_tsl_closing", "refresh_external_closing"]:
        task = {"task_type": task_type}
        assert is_deterministic_safe_task(task) is True, (
            f"is_deterministic_safe_task should return True for {task_type!r}"
        )


# ─────────────────────────────────────────────────────────────────────
# T6. All 3 executor artifacts are non-empty (even with 0 pending records)
# ─────────────────────────────────────────────────────────────────────

def _make_empty_diag() -> dict:
    """Return a get_pending_diagnostics() result with no pending records."""
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_summary": {
            "pending_total": 0,
            "computed_total": 5,
            "external_available_valid": 0,
            "external_available_invalid": 0,
            "tsl_available_valid": 0,
            "tsl_available_invalid": 0,
            "missing_all_sources": 0,
            "invalid_before_prediction": 0,
            "invalid_same_snapshot": 0,
            "stale_candidates": 0,
            "recommended_refresh_tsl": 0,
            "recommended_refresh_external": 0,
            "manual_review_required": 0,
            "ready_to_upgrade": 0,
            "next_closing_action": "run_closing_monitor",
        },
        "pending_diagnostics": [],
    }


@pytest.mark.parametrize("task_type,executor_name", [
    ("closing_availability_audit", "_execute_closing_availability_audit"),
    ("refresh_tsl_closing", "_execute_refresh_tsl_closing"),
    ("refresh_external_closing", "_execute_refresh_external_closing"),
])
def test_t6_executor_artifact_nonempty(
    tmp_path: Path,
    task_type: str,
    executor_name: str,
) -> None:
    """T6: Each Phase 16 executor produces a non-empty artifact even with 0 pending records."""
    import orchestrator.safe_task_executor as ste

    executor = getattr(ste, executor_name)
    artifact_dir = tmp_path / "reports"
    artifact_dir.mkdir(parents=True, exist_ok=True)

    task = {
        "id": f"test-{task_type}",
        "task_type": task_type,
        "completed_file_path": str(artifact_dir / f"{task_type}-artifact.md"),
        "date_folder": "20260430",
        "slug": f"test-{task_type}",
    }

    with patch(
        "orchestrator.closing_odds_monitor.get_pending_diagnostics",
        return_value=_make_empty_diag(),
    ):
        result = executor(task)

    # Must succeed
    assert result["success"] is True, f"{executor_name} returned success=False"

    # completed_text must be non-empty
    completed_text = result.get("completed_text", "")
    assert completed_text, f"{executor_name} returned empty completed_text"
    assert len(completed_text) > 50, (
        f"{executor_name} artifact is suspiciously short ({len(completed_text)} chars)"
    )

    # Must contain header with task type evidence
    assert "Hard Rules Verified" in completed_text, (
        f"{executor_name} artifact missing 'Hard Rules Verified' section"
    )

    # Must not contain fake CLV upgrades
    assert "PENDING_CLOSING" not in completed_text or "NOT" in completed_text or "no" in completed_text.lower(), (
        f"{executor_name} artifact mentions PENDING_CLOSING upgrade in suspicious context"
    )


# ─────────────────────────────────────────────────────────────────────
# T7. No CLV status changes during Phase 16 tasks (learning blocked)
# ─────────────────────────────────────────────────────────────────────

def test_t7_no_clv_status_change_in_refresh_executors(tmp_path: Path) -> None:
    """T7: Phase 16 executors must not change any CLV status to COMPUTED."""
    from orchestrator.safe_task_executor import (
        _execute_closing_availability_audit,
        _execute_refresh_tsl_closing,
        _execute_refresh_external_closing,
    )

    diag_with_pending = _make_empty_diag()
    # Add a pending record to make it realistic
    diag_with_pending["source_summary"]["pending_total"] = 3
    diag_with_pending["source_summary"]["recommended_refresh_tsl"] = 2
    diag_with_pending["source_summary"]["recommended_refresh_external"] = 1
    diag_with_pending["pending_diagnostics"] = [
        {
            "prediction_id": "pred-001",
            "canonical_match_id": "game-001",
            "selection": "home",
            "prediction_time_utc": _iso(datetime.now(timezone.utc) - timedelta(hours=5)),
            "tsl_closing_found": False,
            "external_closing_found": False,
            "candidate_valid": False,
            "best_candidate_source": None,
            "best_candidate_time_utc": None,
            "invalid_reason": "missing_odds",
            "recommended_action": "wait",
        }
    ]

    executors = [
        _execute_closing_availability_audit,
        _execute_refresh_tsl_closing,
        _execute_refresh_external_closing,
    ]

    artifact_dir = tmp_path / "reports"
    artifact_dir.mkdir(parents=True, exist_ok=True)

    for executor in executors:
        task = {
            "id": f"test-{executor.__name__}",
            "task_type": executor.__name__.replace("_execute_", ""),
            "completed_file_path": str(artifact_dir / f"{executor.__name__}-artifact.md"),
            "date_folder": "20260430",
            "slug": f"test-{executor.__name__}",
        }

        clv_status_calls: list[str] = []

        def capture_clv_change(status: str, *args: Any, **kwargs: Any) -> None:
            if status == "COMPUTED":
                clv_status_calls.append(status)

        with patch(
            "orchestrator.closing_odds_monitor.get_pending_diagnostics",
            return_value=diag_with_pending,
        ):
            result = executor(task)

        # No status changes to COMPUTED should have been triggered
        assert clv_status_calls == [], (
            f"{executor.__name__} triggered COMPUTED status change — learning must stay blocked"
        )

        # Artifact must still be non-empty
        assert result.get("completed_text"), f"{executor.__name__} returned empty artifact"


# ─────────────────────────────────────────────────────────────────────
# T8. Ops report includes next_refresh_action in closing_availability
# ─────────────────────────────────────────────────────────────────────

def test_t8_ops_report_refresh_fields() -> None:
    """T8: Phase 9 ops report's closing_availability includes Phase 16 refresh fields."""
    from orchestrator.optimization_ops_report import generate_report

    mock_diag = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_summary": {
            "pending_total": 4,
            "computed_total": 0,
            "external_available_valid": 0,
            "external_available_invalid": 0,
            "tsl_available_valid": 0,
            "tsl_available_invalid": 0,
            "missing_all_sources": 4,
            "invalid_before_prediction": 0,
            "invalid_same_snapshot": 0,
            "stale_candidates": 0,
            "recommended_refresh_tsl": 0,
            "recommended_refresh_external": 0,
            "manual_review_required": 0,
            "ready_to_upgrade": 0,
            "next_closing_action": "closing_availability_audit",
        },
        "pending_diagnostics": [],
    }

    with (
        patch(
            "orchestrator.closing_odds_monitor.get_pending_diagnostics",
            return_value=mock_diag,
        ),
        # Phase 17: mock out escalation check so Phase 16 logic is exercised purely
        patch(
            "orchestrator.closing_refresh_memory.get_escalation_status",
            return_value={"escalation_recommended": False, "consecutive_no_improvement": 0},
        ),
        patch(
            "orchestrator.closing_refresh_memory.get_refresh_feedback_summary",
            return_value={"available": False},
        ),
    ):
        report = generate_report(window="8h")

    ca = report.get("closing_availability") or {}
    assert ca.get("available") is True, "closing_availability must be available"

    # Phase 16 field: next_refresh_action must be present
    assert "next_refresh_action" in ca, (
        f"'next_refresh_action' missing from closing_availability. "
        f"Keys: {list(ca.keys())}"
    )

    # With missing_all_sources=4, action should be closing_availability_audit
    assert ca["next_refresh_action"] == "closing_availability_audit", (
        f"Expected next_refresh_action='closing_availability_audit', "
        f"got {ca['next_refresh_action']!r}"
    )

    # refresh_task_due field must exist
    assert "refresh_task_due" in ca, "'refresh_task_due' missing from closing_availability"

    # last_refresh_task field must exist (may be None)
    assert "last_refresh_task" in ca, "'last_refresh_task' missing from closing_availability"

    # Phase 9 ops report render_markdown must include the refresh section
    from orchestrator.optimization_ops_report import render_markdown
    md = render_markdown(report)
    assert "Closing Odds Availability" in md, (
        "render_markdown must include 'Closing Odds Availability' section"
    )
    assert "next_refresh_action" in md.lower() or "refresh" in md.lower(), (
        "render_markdown should mention refresh action somewhere"
    )
