"""
tests/test_phase25_human_review_ui.py
======================================
Phase 25 — Human Review Queue Actionability in Decision Card / Operator UI

Tests verify:
1. Decision card shows pending review action commands
2. Decision card shows blocked_by_human_review flag
3. Readiness report includes review queue section with action guidance
4. Ops report includes review queue counts + pending review commands
5. CLI list renders pending review table with action commands hint
6. CLI approve prints next-scheduler-behaviour message (validation task, no deploy)
7. CLI reject prints no-follow-up-task message
8. CLI more-data prints validation follow-up message
9. Approval does NOT apply any production patch (invariant)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# ── helpers ───────────────────────────────────────────────────────────────────

def _make_minimal_clv() -> dict:
    """Minimal CLV dict accepted by render_card."""
    return {
        "coverage_pct": 0.0,
        "external_closing_rows": 0,
        "total_live_rows": 0,
        "clv_samples": 0,
        "clv_std": 0.0,
    }


def _make_minimal_sched() -> dict:
    """Minimal scheduler dict accepted by render_card."""
    return {
        "last_run_ts": "2026-05-01T10:00:00Z",
        "next_trigger_minutes": None,
        "api_calls_today": 0,
        "api_cap": 100,
        "state_date": "20260501",
        "fetched_today": False,
        "heartbeat_present": True,
    }


def _make_pending_item(review_id: str = "hrq_test000001") -> dict:
    return {
        "review_id": review_id,
        "review_type": "production_patch_proposal",
        "risk_level": "high",
        "status": "PENDING",
        "title": "Test patch proposal v1",
        "summary": "Sandbox kept patch with 1200 samples CLV 0.032",
        "recommended_action": "review and approve if CLV > 0.03",
        "created_at_utc": "2026-05-01T10:00:00+00:00",
        "reviewed_at_utc": None,
        "reviewer": None,
        "review_notes": None,
        "allowed_next_task_family": "production-proposal-validation",
        "source": "sandbox_evaluator",
        "source_task_id": "task_001",
        "source_decision_id": "dec_001",
        "production_patch_allowed": False,
        "production_model_modified": False,
        "external_llm_called": False,
    }


def _make_queue_summary(pending_items: list[dict] | None = None) -> dict:
    items = pending_items or [_make_pending_item()]
    return {
        "total": len(items),
        "pending_count": len(items),
        "approved_count": 0,
        "rejected_count": 0,
        "more_data_count": 0,
        "blocked_by_human_review": bool(items),
        "latest_review": items[-1] if items else None,
        "pending_reviews": items,
        "approved_reviews": [],
        "rejected_reviews": [],
        "more_data_requested": [],
    }


# ── Test 1: Decision card shows pending review action commands ────────────────

def test_decision_card_shows_pending_review_commands(tmp_path):
    """Decision card render_card() must include action commands for each pending review."""
    from scripts.ops_decision_card import render_card

    item = _make_pending_item("hrq_abc123")
    human_review = {
        "available": True,
        "total": 1,
        "pending_count": 1,
        "approved_count": 0,
        "rejected_count": 0,
        "more_data_count": 0,
        "blocked_by_human_review": True,
        "latest_review": {
            "review_id": "hrq_abc123",
            "review_type": "production_patch_proposal",
            "risk_level": "high",
            "status": "PENDING",
            "recommended_action": "review",
            "created_at_utc": "2026-05-01T10:00:00+00:00",
            "reviewed_at_utc": None,
            "reviewer": None,
            "production_patch_allowed": False,
        },
        "pending_reviews": [item],
    }

    # Minimal payload - only the human_review key matters for this section
    payload: dict[str, Any] = {
        "generated_at": "2026-05-01T10:00:00Z",
        "status": "OK",
        "reasons": [],
        "clv": _make_minimal_clv(),
        "scheduler": _make_minimal_sched(),
        "flags": [],
        "action": "",
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
        "closing_refresh_feedback": {},
        "usage_detail": {},
        "audit_summary": {"available": False},
        "human_review": human_review,
    }

    card = render_card(payload)
    assert "hrq_abc123" in card, "Review ID must appear in card"
    assert "review_queue.py approve" in card, "approve command must appear"
    assert "review_queue.py reject" in card, "reject command must appear"
    assert "review_queue.py more-data" in card, "more-data command must appear"
    assert "review_queue.py show" in card, "show command must appear"


# ── Test 2: Decision card shows blocked_by_human_review prominently ───────────

def test_decision_card_shows_blocked_flag(tmp_path):
    """Decision card must prominently display 🚫 BLOCKED when pending reviews exist."""
    from scripts.ops_decision_card import render_card

    human_review = {
        "available": True,
        "total": 1,
        "pending_count": 1,
        "approved_count": 0,
        "rejected_count": 0,
        "more_data_count": 0,
        "blocked_by_human_review": True,
        "latest_review": None,
        "pending_reviews": [_make_pending_item()],
    }
    payload: dict[str, Any] = {
        "generated_at": "2026-05-01T10:00:00Z",
        "status": "OK", "reasons": [], "clv": _make_minimal_clv(),
        "scheduler": _make_minimal_sched(), "flags": [],
        "action": "", "system_health": {}, "today_wbc": {}, "recent_performance": {},
        "last_postmortem": {}, "phase6": {}, "phase7": {}, "phase8": {}, "phase9_ops": {},
        "readiness": {}, "closing_availability": {}, "closing_refresh_feedback": {},
        "usage_detail": {}, "audit_summary": {"available": False},
        "human_review": human_review,
    }
    card = render_card(payload)
    assert "BLOCKED" in card, "Card must show BLOCKED when pending reviews exist"
    assert "HUMAN REVIEW QUEUE" in card, "Card must show section header"


# ── Test 3: Readiness report includes review queue section ────────────────────

def test_readiness_report_includes_review_section():
    """render_readiness_markdown() must include Phase 24 human review queue section."""
    from orchestrator.optimization_readiness import render_readiness_markdown

    summary = {
        "generated_at": "2026-05-01T10:00:00+00:00",
        "readiness_state": "SAFE_WORK_ACTIVE",
        "severity": "YELLOW",
        "reason": "waiting for CLV",
        "learning_allowed": False,
        "next_required_event": "closing_odds",
        "recommended_next_action": "run closing monitor",
        "phase6": {}, "phase7": {}, "governance": {}, "ops": {},
        "completion_quality": {}, "safe_work": {}, "skip_health": {},
        "closing_availability": {}, "latest_learning_cycle": None,
        "latest_gate_decision": None, "latest_patch_evaluation": None,
        "latest_eval_gate_decision": None,
        "human_review_queue": _make_queue_summary(),
        "blocked_by_human_review": True,
    }
    md = render_readiness_markdown(summary)
    assert "PHASE 24" in md, "Must include Phase 24 section header"
    assert "BLOCKED" in md, "Must indicate planner is blocked"
    assert "review_queue.py" in md, "Must include CLI reference"
    assert "hrq_test000001" in md, "Must show the pending review ID"


# ── Test 4: Ops report includes review queue counts ───────────────────────────

def test_ops_report_includes_review_queue_counts():
    """Ops report markdown must include Phase 24 table with counts + pending review commands."""
    from orchestrator.optimization_ops_report import render_markdown, generate_report

    pending = _make_pending_item("hrq_ops001")
    hrq = {
        "total": 1,
        "pending_count": 1,
        "approved_count": 0,
        "rejected_count": 0,
        "more_data_count": 0,
        "blocked_by_human_review": True,
        "latest_review": {
            "review_id": "hrq_ops001",
            "review_type": "production_patch_proposal",
            "status": "PENDING",
            "risk_level": "high",
        },
        "pending_reviews": [pending],
    }

    # Build a minimal report dict that render_markdown accepts
    report = {
        "window": "8h",
        "since": "2026-05-01T02:00:00+00:00",
        "generated_at": "2026-05-01T10:00:00+00:00",
        "classification": "IDLE",
        "tasks_created": 0,
        "tasks_completed": 0,
        "tasks_queued": 0,
        "tasks_running": 0,
        "tasks_failed": 0,
        "tasks_archived": 0,
        "tasks_cancelled": 0,
        "tasks_rejected": 0,
        "completed_valid_tasks": 0,
        "completed_diagnostic_only": 0,
        "completed_empty_artifact": 0,
        "completed_noop": 0,
        "effective_completed_tasks": 0,
        "governance_blocked": 0,
        "consecutive_skips": 0,
        "hard_off_skip_count": 0,
        "patches_validated": 0,
        "patches_kept": 0,
        "patches_rejected": 0,
        "clv_computed": 0,
        "clv_pending": 0,
        "strategy_reinforcements": 0,
        "top_improvements": [],
        "tasks_without_dimension": [],
        "system_reliability_issues": [],
        "optimization_state": "DATA_WAITING",
        "optimization_blocked_families": [],
        "next_recommended_focus": "",
        "difficulty_level": 1,
        "consecutive_failures": 0,
        "consecutive_successes": 0,
        "scheduler_runs": 0,
        "skip_reasons": {},
        "closing_availability": {},
        "closing_sub_classification": None,
        "human_review_queue": hrq,
    }

    md = render_markdown(report)
    assert "Phase 24" in md, "Must include Phase 24 section"
    assert "hrq_ops001" in md, "Must show review ID"
    assert "review_queue.py approve" in md, "Must include approve command"
    assert "review_queue.py reject" in md, "Must include reject command"
    assert "BLOCKING PLANNER" in md, "Must show BLOCKING PLANNER flag"


# ── Test 5: CLI list renders pending review with action commands hint ──────────

def test_cli_list_shows_action_hint(capsys):
    """CLI list command must show action command hint when reviews are PENDING."""
    from scripts.review_queue import cmd_list

    items = [_make_pending_item("hrq_list001")]

    with patch("scripts.review_queue.get_all_reviews", return_value=items):
        args = argparse.Namespace()
        rc = cmd_list(args)

    captured = capsys.readouterr()
    assert rc == 0
    assert "hrq_list001" in captured.out
    assert "PENDING" in captured.out
    assert "review_queue.py approve" in captured.out, "List must include approve hint when PENDING"
    assert "review_queue.py reject" in captured.out, "List must include reject hint when PENDING"


# ── Test 6: CLI approve prints validation task + no-deploy message ─────────────

def test_cli_approve_prints_no_deploy_message(capsys):
    """CLI approve must say planner creates validation task and NOT a production patch."""
    from scripts.review_queue import cmd_approve

    approved_item = _make_pending_item("hrq_appr001")
    approved_item["status"] = "APPROVED"
    approved_item["reviewer"] = "Kelvin"
    approved_item["allowed_next_task_family"] = "production-proposal-validation"
    approved_item["production_patch_allowed"] = False

    with patch("scripts.review_queue.approve_review", return_value=approved_item):
        args = argparse.Namespace(review_id="hrq_appr001", reviewer="Kelvin", notes="")
        rc = cmd_approve(args)

    captured = capsys.readouterr()
    assert rc == 0
    assert "APPROVED" in captured.out
    assert "production-proposal-validation" in captured.out or "validation" in captured.out.lower()
    assert "does NOT deploy" in captured.out or "not deploy" in captured.out.lower() or "does not" in captured.out.lower()
    # Crucially: approval message must NOT claim patch was deployed
    assert "patch applied" not in captured.out.lower()
    assert "production model modified" not in captured.out.lower()


# ── Test 7: CLI reject prints no-follow-up message ────────────────────────────

def test_cli_reject_prints_no_followup_message(capsys):
    """CLI reject must indicate no follow-up task will be created."""
    from scripts.review_queue import cmd_reject

    rejected_item = _make_pending_item("hrq_rej001")
    rejected_item["status"] = "REJECTED"
    rejected_item["reviewer"] = "Kelvin"

    with patch("scripts.review_queue.reject_review", return_value=rejected_item):
        args = argparse.Namespace(review_id="hrq_rej001", reviewer="Kelvin", notes="")
        rc = cmd_reject(args)

    captured = capsys.readouterr()
    assert rc == 0
    assert "REJECTED" in captured.out
    assert "follow-up" in captured.out.lower() or "no follow" in captured.out.lower()
    assert "not be created" in captured.out.lower() or "will not" in captured.out.lower()


# ── Test 8: CLI more-data prints data-collection follow-up message ────────────

def test_cli_more_data_prints_validation_followup(capsys):
    """CLI more-data must indicate a data-collection task will be created."""
    from scripts.review_queue import cmd_more_data

    more_data_item = _make_pending_item("hrq_md001")
    more_data_item["status"] = "MORE_DATA_REQUESTED"
    more_data_item["reviewer"] = "Kelvin"
    more_data_item["allowed_next_task_family"] = "clv-quality-analysis"

    with patch("scripts.review_queue.request_more_data", return_value=more_data_item):
        args = argparse.Namespace(review_id="hrq_md001", reviewer="Kelvin", notes="")
        rc = cmd_more_data(args)

    captured = capsys.readouterr()
    assert rc == 0
    assert "MORE_DATA_REQUESTED" in captured.out
    # Must mention data-collection or analysis task
    out_lower = captured.out.lower()
    assert "clv" in out_lower or "validation" in out_lower or "data" in out_lower
    assert "no production patch" in out_lower or "not applied" in out_lower or "not apply" in out_lower


# ── Test 9: Approval does NOT apply production patch (invariant) ──────────────

def test_approval_does_not_apply_production_patch(tmp_path):
    """
    approve_review() must return production_patch_allowed=False always.
    Approval only changes status to APPROVED; it must never apply a patch.
    """
    from orchestrator.human_review_queue import (
        approve_review,
        queue_review_item,
        QUEUE_PATH,
        RT_PRODUCTION_PROPOSAL,
        RISK_HIGH,
        NTF_PROPOSAL_VALIDATION,
    )
    import orchestrator.human_review_queue as hrq_mod

    # Redirect queue to tmp dir
    tmp_queue = tmp_path / "human_review_queue.json"
    original_path = hrq_mod.QUEUE_PATH
    hrq_mod.QUEUE_PATH = tmp_queue

    try:
        item = queue_review_item(
            source="test",
            source_task_id="task_test",
            source_decision_id="dec_test_unique_9",
            review_type=RT_PRODUCTION_PROPOSAL,
            title="Test patch proposal",
            summary="Should not be auto-applied",
            risk_level=RISK_HIGH,
            recommended_action="manual review required",
            allowed_next_task_family=NTF_PROPOSAL_VALIDATION,
        )
        review_id = item["review_id"]

        # Approve it
        result = approve_review(review_id, "TestReviewer", "looks good")

        assert result is not None, "approve_review must return the updated item"
        assert result["status"] == "APPROVED"
        assert result["production_patch_allowed"] is False, \
            "production_patch_allowed MUST remain False even after approval"
        assert result.get("production_model_modified", False) is False, \
            "production_model_modified MUST remain False after approval"
        assert result.get("external_llm_called", False) is False, \
            "external_llm_called MUST remain False after approval"
    finally:
        hrq_mod.QUEUE_PATH = original_path
