"""
tests/test_phase17_refresh_feedback_escalation.py

Phase 17 — Refresh Feedback & Escalation

9 tests verifying:
  1. record_outcome(improved=True)  → streak resets to 0
  2. record_outcome(no improvement) → consecutive_no_improvement increments
  3. Three no-improvement runs (same action_type) → escalation_recommended=True
  4. Escalation causes _choose_closing_refresh_action() to return "manual_review_summary"
  5. Improved run after escalation resets streak (consecutive → 0, escalation → False)
  6. get_readiness_summary() includes refresh feedback keys in closing_availability
  7. generate_report() (ops) includes refresh feedback in closing_availability
  8. Escalation does NOT change any CLV COMPUTED status
  9. Decision card render includes CLOSING REFRESH FEEDBACK section
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _now_minus(hours: float) -> datetime:
    """Return a UTC datetime that is `hours` hours ago (recent, within 30-day window)."""
    return datetime.now(timezone.utc) - timedelta(hours=hours)


def _make_tmp_path() -> Path:
    """Create a temporary file path that does not yet exist."""
    tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
    tmp.close()
    os.unlink(tmp.name)
    return Path(tmp.name)


# ─────────────────────────────────────────────────────────────────────────────
# Test 1: record_outcome improved=True resets streak to 0
# ─────────────────────────────────────────────────────────────────────────────

def test_record_outcome_improved_resets_streak():
    """record_outcome with an improving run must reset consecutive_no_improvement to 0."""
    from orchestrator.closing_refresh_memory import record_outcome, get_escalation_status

    path = _make_tmp_path()
    try:
        # Seed a no-improvement streak of 2
        now = _now_minus(3)
        record_outcome(
            action_type="refresh_tsl_closing",
            pending_before=5, pending_after=5,
            computed_before=10, computed_after=10,
            missing_before=0, missing_after=0,
            memory_path=path, now_utc=now,
        )
        record_outcome(
            action_type="refresh_tsl_closing",
            pending_before=5, pending_after=5,
            computed_before=10, computed_after=10,
            missing_before=0, missing_after=0,
            memory_path=path, now_utc=now + timedelta(hours=1),
        )

        # Now record an improving run
        entry = record_outcome(
            action_type="refresh_tsl_closing",
            pending_before=5, pending_after=3,   # pending decreased → improvement
            computed_before=10, computed_after=12,
            missing_before=0, missing_after=0,
            memory_path=path, now_utc=now + timedelta(hours=2),
        )

        assert entry["improved"] is True
        assert entry["consecutive_no_improvement"] == 0
        assert entry["escalation_recommended"] is False

        # Check persistent state
        esc = get_escalation_status("refresh_tsl_closing", memory_path=path)
        assert esc["consecutive_no_improvement"] == 0
        assert esc["escalation_recommended"] is False
    finally:
        Path(path).unlink(missing_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# Test 2: record_outcome no improvement increments consecutive counter
# ─────────────────────────────────────────────────────────────────────────────

def test_record_outcome_no_improvement_increments():
    """record_outcome with no improvement increments consecutive_no_improvement."""
    from orchestrator.closing_refresh_memory import record_outcome

    path = _make_tmp_path()
    try:
        now = _now_minus(5)
        for i in range(3):
            entry = record_outcome(
                action_type="closing_availability_audit",
                pending_before=4, pending_after=4,
                computed_before=8, computed_after=8,
                missing_before=1, missing_after=1,
                memory_path=path, now_utc=now + timedelta(minutes=i * 30),
            )
        assert entry["consecutive_no_improvement"] == 3
        assert entry["improved"] is False
    finally:
        Path(path).unlink(missing_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# Test 3: Three no-improvement runs triggers escalation
# ─────────────────────────────────────────────────────────────────────────────

def test_three_no_improvement_triggers_escalation():
    """
    After 3 consecutive no-improvement runs for the same action_type,
    escalation_recommended must be True.
    """
    from orchestrator.closing_refresh_memory import record_outcome, get_escalation_status

    path = _make_tmp_path()
    try:
        now = _now_minus(5)
        for i in range(3):
            entry = record_outcome(
                action_type="refresh_tsl_closing",
                pending_before=5, pending_after=5,
                computed_before=10, computed_after=10,
                missing_before=2, missing_after=2,
                memory_path=path, now_utc=now + timedelta(minutes=i * 30),
            )

        # Third run should trigger escalation
        assert entry["consecutive_no_improvement"] == 3
        assert entry["escalation_recommended"] is True
        assert entry["failure_reason"] is not None

        esc = get_escalation_status("refresh_tsl_closing", memory_path=path)
        assert esc["escalation_recommended"] is True
        assert esc["recommended_escalation_action"] == "manual_review_summary"
    finally:
        Path(path).unlink(missing_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# Test 4: Escalation causes _choose_closing_refresh_action() to return manual_review_summary
# ─────────────────────────────────────────────────────────────────────────────

def test_escalation_returns_manual_review_summary():
    """
    When get_escalation_status() returns escalation_recommended=True,
    _choose_closing_refresh_action() must return "manual_review_summary".
    """
    from orchestrator.planner_tick import _choose_closing_refresh_action

    escalation_status = {
        "escalation_recommended": True,
        "consecutive_no_improvement": 3,
        "last_run_at_utc": None,
        "last_improved": False,
        "recommended_escalation_action": "manual_review_summary",
    }

    with patch(
        "orchestrator.closing_refresh_memory.get_escalation_status",
        return_value=escalation_status,
    ):
        # closing_availability with a high-priority refresh signal — escalation wins
        closing_availability = {
            "recommended_refresh_external": 5,
            "recommended_refresh_tsl": 3,
            "missing_all_sources": 2,
        }
        result = _choose_closing_refresh_action(closing_availability)
        assert result == "manual_review_summary", (
            f"Expected 'manual_review_summary', got {result!r}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Test 5: Improved run resets streak and clears escalation
# ─────────────────────────────────────────────────────────────────────────────

def test_improved_run_resets_escalation():
    """
    An improving run after escalation must reset consecutive counter to 0
    and set escalation_recommended=False.
    """
    from orchestrator.closing_refresh_memory import record_outcome, get_escalation_status

    path = _make_tmp_path()
    try:
        now = _now_minus(4)
        # Build up escalation (3 no-improvement runs)
        for i in range(3):
            record_outcome(
                action_type="refresh_external_closing",
                pending_before=3, pending_after=3,
                computed_before=7, computed_after=7,
                missing_before=0, missing_after=0,
                memory_path=path, now_utc=now + timedelta(hours=i),
            )
        esc_before = get_escalation_status("refresh_external_closing", memory_path=path)
        # refresh_external_closing threshold is 2 → should already be escalated
        assert esc_before["escalation_recommended"] is True

        # Now record improvement
        reset_entry = record_outcome(
            action_type="refresh_external_closing",
            pending_before=3, pending_after=1,   # pending dropped → improved
            computed_before=7, computed_after=9,
            missing_before=0, missing_after=0,
            memory_path=path, now_utc=now + timedelta(hours=4),
        )
        assert reset_entry["improved"] is True
        assert reset_entry["consecutive_no_improvement"] == 0
        assert reset_entry["escalation_recommended"] is False

        esc_after = get_escalation_status("refresh_external_closing", memory_path=path)
        assert esc_after["consecutive_no_improvement"] == 0
        assert esc_after["escalation_recommended"] is False
    finally:
        Path(path).unlink(missing_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# Test 6: get_readiness_summary() includes refresh feedback keys
# ─────────────────────────────────────────────────────────────────────────────

def test_readiness_summary_includes_refresh_feedback():
    """
    get_readiness_summary()["closing_availability"] must include the Phase 17
    refresh feedback keys: consecutive_no_improvement, escalation_recommended,
    recommended_escalation_action, last_refresh_action, last_refresh_improved.
    """
    from orchestrator.optimization_readiness import get_readiness_summary

    # Stub get_pending_diagnostics so no DB required
    stub_diag = {
        "source_summary": {
            "pending_total": 0,
            "computed_total": 5,
            "missing_all_sources": 0,
            "invalid_before_prediction": 0,
            "invalid_same_snapshot": 0,
            "stale_candidates": 0,
            "recommended_refresh_tsl": 0,
            "recommended_refresh_external": 0,
            "manual_review_required": 0,
            "ready_to_upgrade": 0,
            "next_closing_action": "none",
        },
        "pending_diagnostics": [],
    }
    stub_rfb = {
        "available": True,
        "last_refresh_action": "refresh_tsl_closing",
        "last_refresh_improved": True,
        "last_refresh_at_utc": datetime.now(timezone.utc).isoformat(),
        "consecutive_no_improvement": 1,
        "escalation_recommended": False,
        "recommended_escalation_action": "continue",
        "per_action": {},
    }
    stub_esc_status = {
        "escalation_recommended": False,
        "consecutive_no_improvement": 1,
        "last_run_at_utc": None,
        "last_improved": True,
        "recommended_escalation_action": "continue",
    }

    with (
        patch("orchestrator.closing_odds_monitor.get_pending_diagnostics", return_value=stub_diag),
        patch("orchestrator.closing_refresh_memory.get_escalation_status", return_value=stub_esc_status),
        patch("orchestrator.closing_refresh_memory.get_refresh_feedback_summary", return_value=stub_rfb),
        patch("orchestrator.data_waiting_cadence.is_safe_task_due", return_value=False),
        patch("orchestrator.db.get_conn", side_effect=Exception("no db")),
    ):
        summary = get_readiness_summary()

    ca = summary.get("closing_availability", {})
    assert ca.get("available") is True, f"closing_availability not available: {ca}"

    # Phase 17 keys must be present
    for key in (
        "consecutive_no_improvement",
        "escalation_recommended",
        "recommended_escalation_action",
        "last_refresh_action",
        "last_refresh_improved",
    ):
        assert key in ca, f"Missing key {key!r} in closing_availability: {ca}"


# ─────────────────────────────────────────────────────────────────────────────
# Test 7: generate_report() (ops) includes refresh feedback in closing_availability
# ─────────────────────────────────────────────────────────────────────────────

def test_ops_report_includes_refresh_feedback():
    """
    generate_report()["closing_availability"] must include Phase 17 refresh feedback keys.
    """
    from orchestrator.optimization_ops_report import generate_report

    stub_diag = {
        "source_summary": {
            "pending_total": 1,
            "computed_total": 4,
            "missing_all_sources": 0,
            "invalid_before_prediction": 0,
            "invalid_same_snapshot": 0,
            "stale_candidates": 0,
            "recommended_refresh_tsl": 1,
            "recommended_refresh_external": 0,
            "manual_review_required": 0,
            "ready_to_upgrade": 0,
            "next_closing_action": "refresh_tsl_closing",
        },
        "pending_diagnostics": [],
    }
    stub_rfb = {
        "available": True,
        "last_refresh_action": "refresh_tsl_closing",
        "last_refresh_improved": False,
        "last_refresh_at_utc": datetime.now(timezone.utc).isoformat(),
        "consecutive_no_improvement": 2,
        "escalation_recommended": False,
        "recommended_escalation_action": "continue",
        "per_action": {},
    }
    stub_esc_status = {
        "escalation_recommended": False,
        "consecutive_no_improvement": 2,
        "last_run_at_utc": None,
        "last_improved": False,
        "recommended_escalation_action": "continue",
    }

    with (
        patch("orchestrator.closing_odds_monitor.get_pending_diagnostics", return_value=stub_diag),
        patch("orchestrator.closing_refresh_memory.get_escalation_status", return_value=stub_esc_status),
        patch("orchestrator.closing_refresh_memory.get_refresh_feedback_summary", return_value=stub_rfb),
        patch("orchestrator.data_waiting_cadence.is_safe_task_due", return_value=False),
        patch("orchestrator.db.get_conn", side_effect=Exception("no db")),
    ):
        report = generate_report(window="8h")

    ca = report.get("closing_availability", {})
    assert ca.get("available") is True, f"closing_availability not available: {ca}"

    for key in (
        "consecutive_no_improvement",
        "escalation_recommended",
        "recommended_escalation_action",
        "last_refresh_action",
        "last_refresh_improved",
    ):
        assert key in ca, f"Missing key {key!r} in closing_availability: {ca}"

    assert ca["consecutive_no_improvement"] == 2
    assert ca["last_refresh_action"] == "refresh_tsl_closing"


# ─────────────────────────────────────────────────────────────────────────────
# Test 8: Escalation does NOT change CLV COMPUTED status
# ─────────────────────────────────────────────────────────────────────────────

def test_escalation_does_not_change_clv_status():
    """
    Running multiple no-improvement record_outcome() calls must NOT touch
    any CLV JSONL / DB state. The closing_refresh_memory module writes only
    to its own JSON file — verified by ensuring only the memory JSON is written.
    No db.get_conn() call is ever made by record_outcome().
    """
    from orchestrator.closing_refresh_memory import record_outcome

    path = _make_tmp_path()
    try:
        # Patch db.get_conn to assert it is NEVER called from record_outcome
        with patch("orchestrator.db.get_conn") as mock_get_conn:
            now = _now_minus(3)
            for i in range(5):
                record_outcome(
                    action_type="refresh_tsl_closing",
                    pending_before=5, pending_after=5,
                    computed_before=10, computed_after=10,
                    missing_before=3, missing_after=3,
                    memory_path=path, now_utc=now + timedelta(minutes=i * 30),
                )

        # db.get_conn must never be called from record_outcome
        mock_get_conn.assert_not_called(), (
            "record_outcome() must NOT call db.get_conn() — CLV state must not be touched"
        )

        # The memory file was written — verify it only contains refresh history
        data = json.loads(path.read_text())
        assert "history" in data
        assert "per_action" in data

        # Verify no CLV-status mutation keys exist in the memory file
        for entry in data["history"]:
            assert "clv_status" not in entry, "memory should NOT contain CLV status"
            assert "COMPUTED" not in str(entry), "memory should NOT reference COMPUTED"

    finally:
        Path(path).unlink(missing_ok=True)


# ───────────────────────────────────────────────────────────────────────────────
# Test 9: Decision card render includes CLOSING REFRESH FEEDBACK section
# ───────────────────────────────────────────────────────────────────────────────

def test_decision_card_includes_refresh_feedback():
    """
    render_card() must include the 'CLOSING REFRESH FEEDBACK' section when
    closing_refresh_feedback data is available and has escalation context.

    Test strategy:
    - Inject a minimal payload with closing_refresh_feedback populated
    - Call render_card(payload) directly (no file I/O, no external calls)
    - Assert section header and key fields appear in the rendered output
    """
    import sys
    from pathlib import Path as _P
    ROOT = _P(__file__).resolve().parents[1]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    from scripts.ops_decision_card import render_card

    # Minimal payload: only fill keys accessed by render_card
    # All other sections are skipped with empty/falsy defaults
    payload: dict = {
        "status": "WAITING",
        "reasons": ["DATA_WAITING"],
        "clv": {
            "coverage_pct": 0.0,
            "external_closing_rows": 0,
            "total_live_rows": 0,
            "clv_samples": 0,
            "clv_std": 0.0,
        },
        "scheduler": {
            "last_run_ts": "never",
            "next_trigger_minutes": None,
            "api_calls_today": 0,
            "api_cap": 100,
            "state_date": "2026-01-01",
            "fetched_today": False,
            "heartbeat_present": True,
        },
        "flags": [],
        "action": "Wait for settlement.",
        "system_health": {},
        "today_wbc": {},
        "recent_performance": {},
        "last_postmortem": {},
        "phase6": {},
        "phase7": {},
        "phase8": {},
        "phase9_ops": {},
        "readiness": {},
        "closing_availability": {},
        "usage_detail": {},
        # Phase 17 payload — must trigger CLOSING REFRESH FEEDBACK section
        "closing_refresh_feedback": {
            "available": True,
            "last_refresh_action": "refresh_tsl_closing",
            "last_refresh_improved": False,
            "consecutive_no_improvement": 3,
            "escalation_recommended": True,
            "recommended_escalation_action": "manual_review_summary",
        },
    }

    card = render_card(payload)

    # Section header must appear
    assert "CLOSING REFRESH FEEDBACK" in card, (
        "Decision card must include CLOSING REFRESH FEEDBACK section"
    )
    # Key fields from the Phase 17 spec must appear
    assert "refresh_tsl_closing" in card, "last_refresh_action must appear in card"
    assert "manual_review_summary" in card, "recommended_escalation_action must appear in card"
