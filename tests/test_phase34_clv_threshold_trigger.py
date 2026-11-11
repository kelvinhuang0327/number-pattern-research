"""
Phase 34 Tests — CLV Threshold Crossing Trigger & Learning Recheck
===================================================================
12 tests covering:

  1.  29 → 30 produces CROSSED_APPROACHING
  2.  49 → 50 produces CROSSED_SUFFICIENT
  3.  14 → 20 produces no event
  4.  repeated 30 does not duplicate event
  5.  approaching event creates investigation task only
  6.  sufficient event creates learning recheck task only
  7.  sufficient event does NOT create production patch
  8.  event marked handled after task generation
  9.  deterministic executors produce non-empty artifacts
 10.  readiness / ops report expose threshold events
 11.  no external LLM usage
 12.  no production mutation
"""
from __future__ import annotations

import json
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

from orchestrator.clv_threshold_tracker import (
    EVENT_CROSSED_APPROACHING,
    EVENT_CROSSED_SUFFICIENT,
    TASK_FOR_APPROACHING,
    TASK_FOR_SUFFICIENT,
    THRESHOLD_APPROACHING,
    THRESHOLD_SUFFICIENT,
    detect_threshold_events,
    get_pending_threshold_events,
    get_threshold_summary,
    mark_event_handled,
    update_threshold_state,
)
from orchestrator.safe_task_executor import (
    DETERMINISTIC_TASK_TYPES,
    execute_safe_task,
)


# ── Fixture helpers ─────────────────────────────────────────────────────────

def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8"
    )


def _make_clv_file(
    reports: Path,
    date: str = "2026-04-30",
    computed: int = 0,
    pending: int = 0,
) -> Path:
    p = reports / f"clv_validation_records_6u_{date}.jsonl"
    rows: list[dict] = []
    for i in range(computed):
        rows.append({"prediction_id": f"c_{i}", "clv_status": "COMPUTED", "clv_value": 0.01 * i})
    for i in range(pending):
        rows.append({"prediction_id": f"p_{i}", "clv_status": "PENDING_CLOSING"})
    _write_jsonl(p, rows)
    return p


def _state_path(tmpdir: Path) -> Path:
    sp = tmpdir / "runtime" / "agent_orchestrator" / "clv_threshold_state.json"
    sp.parent.mkdir(parents=True, exist_ok=True)
    return sp


def _make_memory(tmpdir: Path) -> Path:
    mem_dir = tmpdir / "runtime" / "agent_orchestrator"
    mem_dir.mkdir(parents=True, exist_ok=True)
    mem_path = mem_dir / "training_memory.json"
    mem_path.write_text(json.dumps({"clv_accumulation_runs": []}), encoding="utf-8")
    return mem_path


# ── Test 1: 29 → 30 produces CROSSED_APPROACHING ────────────────────────────

def test_29_to_30_produces_crossed_approaching():
    events = detect_threshold_events(29, 30)
    assert len(events) == 1
    e = events[0]
    assert e["event_type"] == EVENT_CROSSED_APPROACHING
    assert e["threshold"] == THRESHOLD_APPROACHING
    assert e["previous_count"] == 29
    assert e["current_count"] == 30
    assert e["recommended_task_type"] == TASK_FOR_APPROACHING
    assert e["handled"] is False


# ── Test 2: 49 → 50 produces CROSSED_SUFFICIENT ─────────────────────────────

def test_49_to_50_produces_crossed_sufficient():
    events = detect_threshold_events(49, 50)
    assert len(events) == 1
    e = events[0]
    assert e["event_type"] == EVENT_CROSSED_SUFFICIENT
    assert e["threshold"] == THRESHOLD_SUFFICIENT
    assert e["previous_count"] == 49
    assert e["current_count"] == 50
    assert e["recommended_task_type"] == TASK_FOR_SUFFICIENT
    assert e["handled"] is False


# ── Test 3: 14 → 20 produces no event ──────────────────────────────────────

def test_14_to_20_produces_no_event():
    events = detect_threshold_events(14, 20)
    assert events == [], f"Expected no events but got: {events}"


# ── Test 4: repeated 30 does not duplicate event ────────────────────────────

def test_repeated_crossing_30_no_duplicate():
    with tempfile.TemporaryDirectory() as tmpdir:
        sp = _state_path(Path(tmpdir))

        # First crossing: 29 → 30
        state1 = update_threshold_state(30, state_path=sp)
        events_before = [e for e in state1["events"] if e["event_type"] == EVENT_CROSSED_APPROACHING]
        assert len(events_before) == 1

        # Second call at same count: should not add another
        state2 = update_threshold_state(30, state_path=sp)
        events_after = [e for e in state2["events"] if e["event_type"] == EVENT_CROSSED_APPROACHING]
        assert len(events_after) == 1, (
            f"Expected 1 CROSSED_APPROACHING event but found {len(events_after)}"
        )

        # Also ensure crossed_30 is True
        assert state2["crossed_30"] is True


# ── Test 5: approaching event creates investigation task only ────────────────

def test_approaching_task_type_is_investigation():
    """CROSSED_APPROACHING recommends production_clv_investigation — not recheck."""
    events = detect_threshold_events(29, 30)
    assert len(events) == 1
    assert events[0]["recommended_task_type"] == TASK_FOR_APPROACHING
    assert events[0]["recommended_task_type"] == "production_clv_investigation"
    # Must NOT recommend learning recheck at this threshold
    assert events[0]["recommended_task_type"] != TASK_FOR_SUFFICIENT


def test_production_clv_investigation_is_registered():
    """production_clv_investigation must be in DETERMINISTIC_TASK_TYPES."""
    assert "production_clv_investigation" in DETERMINISTIC_TASK_TYPES


# ── Test 6: sufficient event creates learning recheck task only ──────────────

def test_sufficient_task_type_is_learning_recheck():
    """CROSSED_SUFFICIENT recommends production_clv_learning_recheck — not investigation."""
    events = detect_threshold_events(49, 50)
    assert len(events) == 1
    assert events[0]["recommended_task_type"] == TASK_FOR_SUFFICIENT
    assert events[0]["recommended_task_type"] == "production_clv_learning_recheck"
    assert events[0]["recommended_task_type"] != TASK_FOR_APPROACHING


def test_production_clv_learning_recheck_is_registered():
    """production_clv_learning_recheck must be in DETERMINISTIC_TASK_TYPES."""
    assert "production_clv_learning_recheck" in DETERMINISTIC_TASK_TYPES


# ── Test 7: sufficient event does NOT create production patch ────────────────

def test_sufficient_event_no_production_patch():
    """
    CROSSED_SUFFICIENT only opens patch gate recheck.
    Executor must not create a patch or enable production_patch_created.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        reports = Path(tmpdir) / "reports"
        reports.mkdir()
        artifact_dir = Path(tmpdir) / "artifacts"
        artifact_dir.mkdir()
        # 50 computed records
        _make_clv_file(reports, "2026-04-30", computed=50)
        mem = _make_memory(Path(tmpdir))

        task = {
            "id": "test34_recheck",
            "task_type": "production_clv_learning_recheck",
            "_sandbox_reports_dir": str(reports),
            "_sandbox_memory_path": str(mem),
            "_sandbox_artifact_dir": str(artifact_dir),
        }
        result = execute_safe_task(task)

        assert result["success"] is True
        assert result["production_mutation"] is False
        assert result["live_bet_submitted"] is False
        assert result["patch_candidate_allowed"] is False
        # Key hard rule: no production patch
        assert result.get("production_patch_created", False) is False


# ── Test 8: event marked handled after task generation ──────────────────────

def test_event_marked_handled():
    with tempfile.TemporaryDirectory() as tmpdir:
        sp = _state_path(Path(tmpdir))

        # Produce a CROSSED_APPROACHING event
        state = update_threshold_state(30, state_path=sp)
        approaching_events = [
            e for e in state["events"]
            if e["event_type"] == EVENT_CROSSED_APPROACHING
        ]
        assert len(approaching_events) == 1
        event_id = approaching_events[0]["event_id"]
        assert approaching_events[0]["handled"] is False

        # Mark it handled
        fake_task_id = str(uuid.uuid4())
        ok = mark_event_handled(event_id, fake_task_id, state_path=sp)
        assert ok is True

        # Reload and confirm
        pending = get_pending_threshold_events(state_path=sp)
        assert all(e["event_id"] != event_id for e in pending), (
            "Handled event must not appear in pending list"
        )


# ── Test 9: deterministic executors produce non-empty artifacts ──────────────

def test_investigation_executor_artifact_non_empty():
    with tempfile.TemporaryDirectory() as tmpdir:
        reports = Path(tmpdir) / "reports"
        reports.mkdir()
        artifact_dir = Path(tmpdir) / "artifacts"
        artifact_dir.mkdir()
        _make_clv_file(reports, "2026-04-30", computed=30)

        task = {
            "id": "test34_inv",
            "task_type": "production_clv_investigation",
            "_sandbox_reports_dir": str(reports),
            "_sandbox_artifact_dir": str(artifact_dir),
        }
        result = execute_safe_task(task)
        assert result["success"] is True
        assert result["completed_text"], "completed_text must be non-empty"
        assert len(result["completed_text"]) > 100
        assert "CLV Investigation" in result["completed_text"]
        assert result["completed_file_path"] is not None
        assert Path(result["completed_file_path"]).exists()


def test_recheck_executor_artifact_non_empty():
    with tempfile.TemporaryDirectory() as tmpdir:
        reports = Path(tmpdir) / "reports"
        reports.mkdir()
        artifact_dir = Path(tmpdir) / "artifacts"
        artifact_dir.mkdir()
        mem = _make_memory(Path(tmpdir))
        _make_clv_file(reports, "2026-04-30", computed=50)

        task = {
            "id": "test34_recheck2",
            "task_type": "production_clv_learning_recheck",
            "_sandbox_reports_dir": str(reports),
            "_sandbox_memory_path": str(mem),
            "_sandbox_artifact_dir": str(artifact_dir),
        }
        result = execute_safe_task(task)
        assert result["success"] is True
        assert result["completed_text"], "completed_text must be non-empty"
        assert len(result["completed_text"]) > 100
        assert "Learning Recheck" in result["completed_text"]
        assert Path(result["completed_file_path"]).exists()


# ── Test 10: readiness / ops report expose threshold events ─────────────────

def test_readiness_exposes_clv_threshold():
    from orchestrator.optimization_readiness import get_readiness_summary
    summary = get_readiness_summary()
    assert "clv_threshold" in summary, (
        "get_readiness_summary() must contain 'clv_threshold'"
    )
    assert isinstance(summary["clv_threshold"], dict)


def test_ops_report_exposes_clv_threshold():
    from orchestrator.optimization_ops_report import generate_report
    report = generate_report(window="8h")
    assert "clv_threshold" in report, (
        "generate_report() must contain 'clv_threshold'"
    )
    assert isinstance(report["clv_threshold"], dict)


def test_decision_card_exposes_clv_threshold():
    from scripts.ops_decision_card import compute_clv_threshold_status
    status = compute_clv_threshold_status()
    assert isinstance(status, dict)
    # Even with no state file it should return a dict (available=True or available=False)
    assert "available" in status


# ── Test 11: no external LLM usage ───────────────────────────────────────────

def test_investigation_no_external_llm():
    with tempfile.TemporaryDirectory() as tmpdir:
        reports = Path(tmpdir) / "reports"
        reports.mkdir()
        artifact_dir = Path(tmpdir) / "artifacts"
        artifact_dir.mkdir()
        _make_clv_file(reports, "2026-04-30", computed=30)

        task = {
            "id": "test34_no_llm_inv",
            "task_type": "production_clv_investigation",
            "_sandbox_reports_dir": str(reports),
            "_sandbox_artifact_dir": str(artifact_dir),
        }
        result = execute_safe_task(task)
        assert "No external LLM called" in result["completed_text"]
        assert result["execution_mode"] == "PAPER_ONLY"


def test_recheck_no_external_llm():
    with tempfile.TemporaryDirectory() as tmpdir:
        reports = Path(tmpdir) / "reports"
        reports.mkdir()
        artifact_dir = Path(tmpdir) / "artifacts"
        artifact_dir.mkdir()
        mem = _make_memory(Path(tmpdir))
        _make_clv_file(reports, "2026-04-30", computed=50)

        task = {
            "id": "test34_no_llm_recheck",
            "task_type": "production_clv_learning_recheck",
            "_sandbox_reports_dir": str(reports),
            "_sandbox_memory_path": str(mem),
            "_sandbox_artifact_dir": str(artifact_dir),
        }
        result = execute_safe_task(task)
        assert "No external LLM called" in result["completed_text"]
        assert result["execution_mode"] == "PAPER_ONLY"


# ── Test 12: no production mutation ──────────────────────────────────────────

def test_investigation_no_production_mutation():
    with tempfile.TemporaryDirectory() as tmpdir:
        reports = Path(tmpdir) / "reports"
        reports.mkdir()
        artifact_dir = Path(tmpdir) / "artifacts"
        artifact_dir.mkdir()
        _make_clv_file(reports, "2026-04-30", computed=30)

        task = {
            "id": "test34_no_mut_inv",
            "task_type": "production_clv_investigation",
            "_sandbox_reports_dir": str(reports),
            "_sandbox_artifact_dir": str(artifact_dir),
        }
        result = execute_safe_task(task)
        assert result["production_mutation"] is False
        assert result["live_bet_submitted"] is False
        assert result["patch_candidate_allowed"] is False
        # patch_gate_recheck must be False for investigation (only allowed at sufficient)
        assert result["patch_gate_recheck_allowed"] is False


def test_recheck_no_production_mutation():
    with tempfile.TemporaryDirectory() as tmpdir:
        reports = Path(tmpdir) / "reports"
        reports.mkdir()
        artifact_dir = Path(tmpdir) / "artifacts"
        artifact_dir.mkdir()
        mem = _make_memory(Path(tmpdir))
        _make_clv_file(reports, "2026-04-30", computed=50)

        task = {
            "id": "test34_no_mut_recheck",
            "task_type": "production_clv_learning_recheck",
            "_sandbox_reports_dir": str(reports),
            "_sandbox_memory_path": str(mem),
            "_sandbox_artifact_dir": str(artifact_dir),
        }
        result = execute_safe_task(task)
        assert result["production_mutation"] is False
        assert result["live_bet_submitted"] is False
        assert result["patch_candidate_allowed"] is False
        assert result.get("production_patch_created", False) is False
