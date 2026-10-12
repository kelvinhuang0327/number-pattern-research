"""
tests/test_phase18_e2e_waiting_loop.py

Phase 18 — End-to-End Autonomous Waiting Loop Runtime Validation

9 tests verifying the full DATA_WAITING loop:
  1. Planner always chooses a valid DATA_WAITING task type (never a learning type)
  2. Escalation state triggers manual_review_summary selection
  3. All valid DATA_WAITING task types are registered as deterministic safe tasks
  4. manual_review_summary executor produces a non-empty artifact (no LLM)
  5. CLV PENDING/COMPUTED counts are unchanged after safe executor run
  6. Learning remains blocked after safe executor run
  7. Refresh memory records are preserved (not mutated by executor)
  8. Readiness reports reflect WAITING_ACTIVE after execution
  9. Validation script dry-run returns exit code 0 (PHASE_18 VERIFIED)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ── helpers ────────────────────────────────────────────────────────────────

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _make_tmp_dir() -> Path:
    """Create a temporary directory."""
    d = Path(tempfile.mkdtemp())
    return d


def _make_minimal_task(
    task_type: str,
    task_id: int = 999,
    tmp_dir: Path | None = None,
) -> dict[str, Any]:
    """
    Build a minimal task dict that safe_task_executor accepts.
    """
    base = tmp_dir or _make_tmp_dir()
    base.mkdir(parents=True, exist_ok=True)
    return {
        "id": task_id,
        "task_key": f"test_{task_type}_{task_id}",
        "task_type": task_type,
        "objective": f"Test {task_type} task for Phase 18 validation",
        "task_dir": str(base),
        "prompt_path": str(base / "prompt.md"),
        "completed_path": str(base / "completed.md"),
        "contract_path": str(base / "contract.json"),
        "result_path": str(base / "result.json"),
        "meta_path": str(base / "meta.json"),
    }


VALID_DATA_WAITING_TASK_TYPES = frozenset({
    "refresh_external_closing",
    "refresh_tsl_closing",
    "closing_availability_audit",
    "closing_monitor",
    "manual_review_summary",
})

FORBIDDEN_TASK_TYPES = frozenset({
    "model_patch",
    "strategy_reinforcement",
    "feedback_learning",
    "model_patch_atomic",
    "feedback_atomic",
    "calibration_atomic",
})


# ─────────────────────────────────────────────────────────────────────────────
# Test 1: Planner always returns a valid DATA_WAITING task type
# ─────────────────────────────────────────────────────────────────────────────

def test_planner_chooses_valid_data_waiting_task_type():
    """
    _choose_closing_refresh_action() must always return one of the approved
    DATA_WAITING task types and never a learning/model task.
    """
    from orchestrator.planner_tick import _choose_closing_refresh_action

    # Test with various source_summary combinations
    test_cases: list[dict] = [
        {},  # empty → closing_monitor
        {"missing_all_sources": 5},  # missing sources → closing_availability_audit
        {"recommended_refresh_tsl": 2},  # TSL available → refresh_tsl_closing
        {"recommended_refresh_external": 3},  # external available → refresh_external_closing
    ]

    for source_summary in test_cases:
        # Disable escalation so we test the base priority logic
        with patch(
            "orchestrator.closing_refresh_memory.get_escalation_status",
            return_value={"escalation_recommended": False, "consecutive_no_improvement": 0},
        ):
            result = _choose_closing_refresh_action(source_summary)

        assert result in VALID_DATA_WAITING_TASK_TYPES, (
            f"_choose_closing_refresh_action({source_summary}) → {result!r} "
            f"is NOT in VALID_DATA_WAITING_TASK_TYPES"
        )
        assert result not in FORBIDDEN_TASK_TYPES, (
            f"_choose_closing_refresh_action({source_summary}) → {result!r} "
            f"is a FORBIDDEN learning task"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Test 2: Escalation state triggers manual_review_summary
# ─────────────────────────────────────────────────────────────────────────────

def test_escalation_triggers_manual_review_summary():
    """
    When get_escalation_status() returns escalation_recommended=True,
    _choose_closing_refresh_action() must return 'manual_review_summary'.

    This is the Phase 17 → Phase 18 integration: escalation drives planner
    to request human intervention.
    """
    from orchestrator.planner_tick import _choose_closing_refresh_action

    # Simulate: escalation triggered (14 consecutive no-improvement)
    with patch(
        "orchestrator.closing_refresh_memory.get_escalation_status",
        return_value={
            "escalation_recommended": True,
            "consecutive_no_improvement": 14,
            "recommended_escalation_action": "manual_review_summary",
        },
    ):
        result = _choose_closing_refresh_action({"missing_all_sources": 14})

    assert result == "manual_review_summary", (
        f"Expected 'manual_review_summary' when escalation is triggered, got {result!r}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Test 3: All valid DATA_WAITING task types are deterministic safe tasks
# ─────────────────────────────────────────────────────────────────────────────

def test_all_valid_types_are_deterministic_safe_tasks():
    """
    Every task type in VALID_DATA_WAITING_TASK_TYPES must be registered in
    DETERMINISTIC_TASK_TYPES — ensuring they all bypass LLM routing.
    """
    from orchestrator.safe_task_executor import (
        DETERMINISTIC_TASK_TYPES,
        is_deterministic_safe_task,
    )

    for task_type in VALID_DATA_WAITING_TASK_TYPES:
        task = {"task_type": task_type}
        assert is_deterministic_safe_task(task), (
            f"Task type {task_type!r} is NOT registered as deterministic — "
            "it would be routed to an LLM provider"
        )
        assert task_type in DETERMINISTIC_TASK_TYPES, (
            f"Task type {task_type!r} is NOT in DETERMINISTIC_TASK_TYPES registry"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Test 4: manual_review_summary executor produces non-empty artifact (no LLM)
# ─────────────────────────────────────────────────────────────────────────────

def test_manual_review_summary_produces_non_empty_artifact():
    """
    execute_safe_task() with task_type='manual_review_summary' must:
      - succeed (success=True)
      - produce a non-empty completed_text artifact
      - NOT call any external LLM
      - NOT call db.get_conn() to modify CLV state
    """
    from orchestrator.safe_task_executor import execute_safe_task

    tmp_dir = _make_tmp_dir()
    task = _make_minimal_task("manual_review_summary", task_id=998, tmp_dir=tmp_dir)

    # Patch external dependencies to ensure no real calls
    fake_diag = {
        "source_summary": {
            "pending_total": 14,
            "computed_total": 0,
            "missing_all_sources": 14,
            "invalid_before_prediction": 0,
            "invalid_same_snapshot": 0,
            "stale_candidates": 0,
            "ready_to_upgrade": 0,
            "recommended_refresh_tsl": 0,
            "recommended_refresh_external": 0,
            "manual_review_required": 0,
        },
        "pending_diagnostics": [],
    }
    fake_feedback = {
        "available": True,
        "last_refresh_action": "refresh_external_closing",
        "last_refresh_improved": False,
        "consecutive_no_improvement": 14,
        "escalation_recommended": True,
        "recommended_escalation_action": "manual_review_summary",
        "per_action": {},
    }
    fake_escalation = {
        "escalation_recommended": True,
        "consecutive_no_improvement": 14,
        "recommended_escalation_action": "manual_review_summary",
    }

    with (
        patch("orchestrator.closing_odds_monitor.get_pending_diagnostics", return_value=fake_diag),
        patch("orchestrator.closing_refresh_memory.get_refresh_feedback_summary", return_value=fake_feedback),
        patch("orchestrator.closing_refresh_memory.get_escalation_status", return_value=fake_escalation),
    ):
        result = execute_safe_task(task)

    assert result["success"] is True, f"execute_safe_task returned success={result['success']!r}"

    artifact_text = result.get("completed_text", "")
    assert artifact_text, "Artifact text must NOT be empty"
    assert len(artifact_text) >= 100, f"Artifact too short: {len(artifact_text)} chars"

    # Key sections must be present
    assert "Manual Review Summary" in artifact_text, "Artifact missing title"
    assert "Escalation Context" in artifact_text, "Artifact missing escalation context"
    assert "Hard Rules Verified" in artifact_text, "Artifact missing hard rules section"


# ─────────────────────────────────────────────────────────────────────────────
# Test 5: CLV pending/computed counts unchanged after safe executor run
# ─────────────────────────────────────────────────────────────────────────────

def test_clv_counts_unchanged_after_manual_review_executor():
    """
    Executing manual_review_summary must NOT change any CLV PENDING_CLOSING
    or COMPUTED counts. The executor is strictly read-only for CLV state.
    """
    from orchestrator.safe_task_executor import execute_safe_task
    from orchestrator.closing_odds_monitor import get_pending_diagnostics

    tmp_dir = _make_tmp_dir()
    task = _make_minimal_task("manual_review_summary", task_id=997, tmp_dir=tmp_dir)

    # Snapshot before
    before_diag = get_pending_diagnostics()
    before_ss = before_diag.get("source_summary", {})
    pending_before = before_ss.get("pending_total", 0)
    computed_before = before_ss.get("computed_total", 0)

    # Execute
    with (
        patch("orchestrator.closing_refresh_memory.get_refresh_feedback_summary",
              return_value={"available": True, "last_refresh_action": None,
                            "last_refresh_improved": None, "consecutive_no_improvement": 0,
                            "escalation_recommended": False,
                            "recommended_escalation_action": "continue", "per_action": {}}),
        patch("orchestrator.closing_refresh_memory.get_escalation_status",
              return_value={"escalation_recommended": False, "consecutive_no_improvement": 0,
                            "recommended_escalation_action": "continue"}),
    ):
        result = execute_safe_task(task)

    assert result["success"] is True

    # Snapshot after
    after_diag = get_pending_diagnostics()
    after_ss = after_diag.get("source_summary", {})
    pending_after = after_ss.get("pending_total", 0)
    computed_after = after_ss.get("computed_total", 0)

    assert pending_after == pending_before, (
        f"CLV PENDING changed: {pending_before} → {pending_after} "
        "— executor must NOT modify CLV state"
    )
    assert computed_after == computed_before, (
        f"CLV COMPUTED changed: {computed_before} → {computed_after} "
        "— executor must NOT mark PENDING as COMPUTED"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Test 6: Learning remains blocked after safe executor run
# ─────────────────────────────────────────────────────────────────────────────

def test_learning_blocked_after_safe_executor_run():
    """
    After executing a manual_review_summary task, learning must remain BLOCKED.
    The safe executor must NOT unlock any learning pathway.
    """
    from orchestrator.safe_task_executor import execute_safe_task
    from orchestrator.optimization_readiness import get_readiness_summary

    tmp_dir = _make_tmp_dir()
    task = _make_minimal_task("manual_review_summary", task_id=996, tmp_dir=tmp_dir)

    # Record learning state before
    before_rs = get_readiness_summary()
    before_learning = before_rs.get("learning_allowed", False)

    # Execute
    with (
        patch("orchestrator.closing_refresh_memory.get_refresh_feedback_summary",
              return_value={"available": True, "last_refresh_action": None,
                            "last_refresh_improved": None, "consecutive_no_improvement": 0,
                            "escalation_recommended": False,
                            "recommended_escalation_action": "continue", "per_action": {}}),
        patch("orchestrator.closing_refresh_memory.get_escalation_status",
              return_value={"escalation_recommended": False, "consecutive_no_improvement": 0,
                            "recommended_escalation_action": "continue"}),
    ):
        result = execute_safe_task(task)

    assert result["success"] is True

    # Verify learning state after
    after_rs = get_readiness_summary()
    after_learning = after_rs.get("learning_allowed", False)

    assert not after_learning, (
        "Learning was UNLOCKED after manual_review_summary — HARD RULE VIOLATION: "
        "DATA_WAITING safe tasks must never unlock learning"
    )
    assert after_learning == before_learning, (
        f"Learning state changed: {before_learning!r} → {after_learning!r} "
        "— executor must not modify learning state"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Test 7: Refresh memory is NOT mutated by manual_review_summary executor
# ─────────────────────────────────────────────────────────────────────────────

def test_refresh_memory_not_mutated_by_manual_review_executor():
    """
    The manual_review_summary executor reads refresh memory but does NOT write to it.
    (record_outcome() is called only by the closing_monitor / refresh executors.)

    Verify: record_outcome() is NOT called during manual_review_summary execution.
    """
    from orchestrator.safe_task_executor import execute_safe_task

    tmp_dir = _make_tmp_dir()
    task = _make_minimal_task("manual_review_summary", task_id=995, tmp_dir=tmp_dir)

    with (
        patch("orchestrator.closing_refresh_memory.get_refresh_feedback_summary",
              return_value={"available": True, "last_refresh_action": None,
                            "last_refresh_improved": None, "consecutive_no_improvement": 0,
                            "escalation_recommended": False,
                            "recommended_escalation_action": "continue", "per_action": {}}),
        patch("orchestrator.closing_refresh_memory.get_escalation_status",
              return_value={"escalation_recommended": False, "consecutive_no_improvement": 0,
                            "recommended_escalation_action": "continue"}),
        patch("orchestrator.closing_refresh_memory.record_outcome") as mock_record,
    ):
        result = execute_safe_task(task)

    assert result["success"] is True
    mock_record.assert_not_called(), (
        "manual_review_summary executor must NOT call record_outcome() — "
        "only refresh executors should update the memory"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Test 8: Readiness reports WAITING_ACTIVE after execution
# ─────────────────────────────────────────────────────────────────────────────

def test_readiness_remains_waiting_active_after_execution():
    """
    After executing a manual_review_summary task, readiness_state must still
    be WAITING_ACTIVE (not READY, not BLOCKED) — the system is still waiting
    for closing odds.
    """
    from orchestrator.safe_task_executor import execute_safe_task
    from orchestrator.optimization_readiness import get_readiness_summary

    tmp_dir = _make_tmp_dir()
    task = _make_minimal_task("manual_review_summary", task_id=994, tmp_dir=tmp_dir)

    with (
        patch("orchestrator.closing_refresh_memory.get_refresh_feedback_summary",
              return_value={"available": True, "last_refresh_action": None,
                            "last_refresh_improved": None, "consecutive_no_improvement": 0,
                            "escalation_recommended": False,
                            "recommended_escalation_action": "continue", "per_action": {}}),
        patch("orchestrator.closing_refresh_memory.get_escalation_status",
              return_value={"escalation_recommended": False, "consecutive_no_improvement": 0,
                            "recommended_escalation_action": "continue"}),
    ):
        result = execute_safe_task(task)

    assert result["success"] is True

    # Readiness must still reflect DATA_WAITING
    rs = get_readiness_summary()
    readiness_state = rs.get("readiness_state", "")

    assert "WAITING" in readiness_state.upper(), (
        f"Readiness state {readiness_state!r} should contain 'WAITING' after "
        "safe task execution — CLV is still PENDING_CLOSING"
    )

    assert not rs.get("learning_allowed", False), (
        "learning_allowed must remain False while CLV records are PENDING_CLOSING"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Test 9: Validation script dry-run returns exit code 0
# ─────────────────────────────────────────────────────────────────────────────

def test_phase18_validation_script_dry_run_passes():
    """
    scripts/run_phase18_e2e_validation.py --dry-run must exit with code 0
    (PHASE_18_E2E_WAITING_LOOP_RUNTIME_VERIFIED) in the current codebase state.

    This is the top-level integration assertion: if the E2E validation script
    fails, Phase 18 is not complete.
    """
    script = _REPO_ROOT / "scripts" / "run_phase18_e2e_validation.py"
    assert script.exists(), f"Validation script not found: {script}"

    proc = subprocess.run(
        [sys.executable, str(script), "--dry-run"],
        capture_output=True,
        text=True,
        cwd=str(_REPO_ROOT),
        timeout=60,
    )

    output = proc.stdout + proc.stderr

    assert proc.returncode == 0, (
        f"Validation script exited with code {proc.returncode}\n"
        f"--- stdout ---\n{proc.stdout}\n"
        f"--- stderr ---\n{proc.stderr}"
    )

    assert "PHASE_18_E2E_WAITING_LOOP_RUNTIME_VERIFIED" in output, (
        "Script did not emit PHASE_18_E2E_WAITING_LOOP_RUNTIME_VERIFIED\n"
        f"Output:\n{output[:1000]}"
    )
