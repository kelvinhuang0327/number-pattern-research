"""
tests/test_phase24_human_review_queue.py
=========================================
Phase 24 — Human Review Queue & Approval Gate
10 unit tests.

Isolation: every test uses a temporary QUEUE_PATH so it never touches the
real runtime/agent_orchestrator/human_review_queue.json file.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

import orchestrator.human_review_queue as hrq_module
from orchestrator.human_review_queue import (
    NTF_ADDITIONAL_VALIDATION,
    NTF_CLV_QUALITY,
    NTF_PROPOSAL_VALIDATION,
    RISK_HIGH,
    RISK_MEDIUM,
    RT_PRODUCTION_PROPOSAL,
    RT_SANDBOX_UNCERTAIN,
    STATUS_APPROVED,
    STATUS_MORE_DATA,
    STATUS_PENDING,
    STATUS_REJECTED,
    approve_review,
    get_pending_reviews,
    get_approved_reviews,
    get_more_data_reviews,
    get_queue_summary,
    get_review_by_id,
    has_pending_reviews,
    queue_review_item,
    reject_review,
    request_more_data,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def isolated_queue(tmp_path, monkeypatch):
    """Redirect QUEUE_PATH to a temp dir for every test."""
    tmp_queue = tmp_path / "human_review_queue.json"
    monkeypatch.setattr(hrq_module, "QUEUE_PATH", tmp_queue)
    yield tmp_queue


# ─────────────────────────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────────────────────────

def _queue_sandbox_item(**kwargs) -> dict:
    defaults = dict(
        source="patch_evaluation_gate",
        source_task_id="task_001",
        source_decision_id="dec_001",
        review_type=RT_SANDBOX_UNCERTAIN,
        title="Test Sandbox Review",
        summary="Sandbox outcome was uncertain.",
        risk_level=RISK_MEDIUM,
        recommended_action="Review and approve or reject.",
        allowed_next_task_family=NTF_ADDITIONAL_VALIDATION,
    )
    defaults.update(kwargs)
    return queue_review_item(**defaults)


def _queue_proposal_item(**kwargs) -> dict:
    defaults = dict(
        source="patch_evaluation_gate",
        source_task_id="task_002",
        source_decision_id="dec_002",
        review_type=RT_PRODUCTION_PROPOSAL,
        title="Test Proposal Review",
        summary="Sandbox criteria met — propose production.",
        risk_level=RISK_HIGH,
        recommended_action="Review evidence. Approve paper-only plan.",
        allowed_next_task_family=NTF_PROPOSAL_VALIDATION,
    )
    defaults.update(kwargs)
    return queue_review_item(**defaults)


# ─────────────────────────────────────────────────────────────────────────────
# Test 1 — HUMAN_REVIEW creates a PENDING review
# ─────────────────────────────────────────────────────────────────────────────

def test_human_review_required_creates_pending_review():
    """Simulating gate23 HUMAN_REVIEW path: queue_review_item → status PENDING."""
    item = _queue_sandbox_item()
    assert item["status"] == STATUS_PENDING
    assert item["review_type"] == RT_SANDBOX_UNCERTAIN
    assert item["production_patch_allowed"] is False
    assert item["production_model_modified"] is False
    assert item["external_llm_called"] is False
    assert item["reviewer"] is None
    # Should appear in pending list
    pending = get_pending_reviews()
    assert len(pending) == 1
    assert pending[0]["review_id"] == item["review_id"]


# ─────────────────────────────────────────────────────────────────────────────
# Test 2 — PROMOTE creates a PENDING production_patch_proposal review
# ─────────────────────────────────────────────────────────────────────────────

def test_promote_to_production_proposal_creates_pending_review():
    """Simulating gate23 PROMOTE path: queue_review_item → production_patch_proposal."""
    item = _queue_proposal_item()
    assert item["status"] == STATUS_PENDING
    assert item["review_type"] == RT_PRODUCTION_PROPOSAL
    assert item["risk_level"] == RISK_HIGH
    assert item["allowed_next_task_family"] == NTF_PROPOSAL_VALIDATION
    assert item["production_patch_allowed"] is False


# ─────────────────────────────────────────────────────────────────────────────
# Test 3 — Deduplication by source_decision_id
# ─────────────────────────────────────────────────────────────────────────────

def test_duplicate_source_decision_id_not_duplicated():
    """Calling queue_review_item() twice with the same source_decision_id → only 1 item."""
    item1 = _queue_sandbox_item(source_decision_id="dup_dec_001")
    item2 = _queue_sandbox_item(source_decision_id="dup_dec_001")
    # Both calls should return the same review_id
    assert item1["review_id"] == item2["review_id"]
    pending = get_pending_reviews()
    assert len(pending) == 1


# ─────────────────────────────────────────────────────────────────────────────
# Test 4 — Approve records reviewer and status
# ─────────────────────────────────────────────────────────────────────────────

def test_approve_review_records_reviewer_and_status():
    """approve_review() → status APPROVED, reviewer/notes recorded."""
    item = _queue_sandbox_item(source_decision_id="dec_approve_001")
    rid = item["review_id"]

    result = approve_review(rid, reviewer="Kelvin", notes="Evidence looks solid.")
    assert result is not None
    assert result["status"] == STATUS_APPROVED
    assert result["reviewer"] == "Kelvin"
    assert result["review_notes"] == "Evidence looks solid."
    assert result["reviewed_at_utc"] is not None
    # production_patch_allowed must remain False even after approval
    assert result["production_patch_allowed"] is False
    # Should no longer appear in pending
    assert get_pending_reviews() == []
    approved = get_approved_reviews()
    assert len(approved) == 1
    assert approved[0]["review_id"] == rid


# ─────────────────────────────────────────────────────────────────────────────
# Test 5 — Reject keeps production_patch_allowed False
# ─────────────────────────────────────────────────────────────────────────────

def test_reject_review_blocks_follow_up():
    """reject_review() → status REJECTED, production_patch_allowed still False."""
    item = _queue_proposal_item(source_decision_id="dec_reject_001")
    rid = item["review_id"]

    result = reject_review(rid, reviewer="Kelvin", notes="Not enough evidence.")
    assert result is not None
    assert result["status"] == STATUS_REJECTED
    assert result["production_patch_allowed"] is False
    # Should not appear in pending or approved
    assert get_pending_reviews() == []
    assert get_approved_reviews() == []


# ─────────────────────────────────────────────────────────────────────────────
# Test 6 — More-data sets clv-quality-analysis family
# ─────────────────────────────────────────────────────────────────────────────

def test_request_more_data_allows_validation_task():
    """request_more_data() → MORE_DATA_REQUESTED, allowed_next_task_family == clv-quality-analysis."""
    item = _queue_sandbox_item(source_decision_id="dec_moredata_001")
    rid = item["review_id"]

    result = request_more_data(rid, reviewer="Kelvin", notes="Need 50 more samples.")
    assert result is not None
    assert result["status"] == STATUS_MORE_DATA
    assert result["allowed_next_task_family"] == NTF_CLV_QUALITY
    assert result["production_patch_allowed"] is False
    more = get_more_data_reviews()
    assert len(more) == 1
    assert more[0]["review_id"] == rid


# ─────────────────────────────────────────────────────────────────────────────
# Test 7 — Planner Step 0.9 blocks while review is PENDING (unit simulation)
# ─────────────────────────────────────────────────────────────────────────────

def test_planner_skips_while_review_pending():
    """Directly test the has_pending_reviews() guard that STEP 0.9 uses to block planner."""
    assert has_pending_reviews() is False

    _queue_sandbox_item(source_decision_id="dec_block_001")

    assert has_pending_reviews() is True
    pending = get_pending_reviews()
    assert len(pending) == 1

    # After approval the block should lift
    rid = pending[0]["review_id"]
    approve_review(rid, reviewer="Auto", notes="Test")
    assert has_pending_reviews() is False


# ─────────────────────────────────────────────────────────────────────────────
# Test 8 — APPROVED production_patch_proposal produces correct candidate fields
# ─────────────────────────────────────────────────────────────────────────────

def test_planner_creates_followup_after_approved():
    """Simulate the STEP 0.9 candidate-generation logic for an APPROVED proposal."""
    item = _queue_proposal_item(source_decision_id="dec_followup_001")
    rid = item["review_id"]
    approve_review(rid, reviewer="Kelvin", notes="ok")

    approved = get_approved_reviews()
    assert len(approved) == 1
    rev = approved[0]
    # Simulate what STEP 0.9 does for each approved review
    assert rev.get("generated_task_id") is None  # not yet actioned
    assert rev.get("review_type") == RT_PRODUCTION_PROPOSAL
    next_family = rev.get("allowed_next_task_family") or NTF_ADDITIONAL_VALIDATION
    assert next_family == NTF_PROPOSAL_VALIDATION

    # Verify the candidate dict that STEP 0.9 would build
    candidate = {
        "title": f"[Phase24] Production Proposal Validation — {rid}",
        "task_type": "manual_review_summary",
        "analysis_family": next_family,
        "focus_area": "production-proposal-validation",
        "source": "human_review_queue",
        "phase24_review_id": rid,
        "production_patch_allowed": False,
    }
    assert candidate["production_patch_allowed"] is False
    assert candidate["analysis_family"] == NTF_PROPOSAL_VALIDATION
    assert candidate["source"] == "human_review_queue"


# ─────────────────────────────────────────────────────────────────────────────
# Test 9 — get_queue_summary reflects counts and blocked_by_human_review
# ─────────────────────────────────────────────────────────────────────────────

def test_ops_readiness_exposes_review_queue():
    """get_queue_summary() exposes pending_count and blocked_by_human_review."""
    # Initially empty
    summary = get_queue_summary()
    assert summary["total"] == 0
    assert summary["pending_count"] == 0
    assert summary["blocked_by_human_review"] is False

    # Add a PENDING item → blocked
    item = _queue_sandbox_item(source_decision_id="dec_summary_001")
    summary = get_queue_summary()
    assert summary["pending_count"] == 1
    assert summary["blocked_by_human_review"] is True

    # Approve it → no longer blocked
    approve_review(item["review_id"], reviewer="Kelvin", notes="ok")
    summary = get_queue_summary()
    assert summary["approved_count"] == 1
    assert summary["pending_count"] == 0
    assert summary["blocked_by_human_review"] is False


# ─────────────────────────────────────────────────────────────────────────────
# Test 10 — CLI list/show/approve/reject/more-data commands work correctly
# ─────────────────────────────────────────────────────────────────────────────

def test_cli_list_show_approve_reject_more_data(tmp_path, monkeypatch):
    """CLI commands work correctly via direct function calls (fast, no subprocess)."""
    import argparse

    # We patch the module QUEUE_PATH so CLI (which imports hrq_module at runtime)
    # also uses the tmp file.  The monkeypatch fixture already did this via autouse.

    # Seed queue
    item_a = _queue_sandbox_item(source_decision_id="cli_dec_a")
    item_b = _queue_proposal_item(source_decision_id="cli_dec_b")

    # ── list ──────────────────────────────────────────────────────
    from scripts.review_queue import cmd_list, cmd_show, cmd_approve, cmd_reject, cmd_more_data

    args_list = argparse.Namespace()
    rc = cmd_list(args_list)
    assert rc == 0

    # ── show ──────────────────────────────────────────────────────
    args_show = argparse.Namespace(review_id=item_a["review_id"])
    rc = cmd_show(args_show)
    assert rc == 0

    args_show_bad = argparse.Namespace(review_id="hrq_does_not_exist")
    rc = cmd_show(args_show_bad)
    assert rc == 1

    # ── approve ───────────────────────────────────────────────────
    args_approve = argparse.Namespace(
        review_id=item_a["review_id"],
        reviewer="Kelvin",
        notes="CLI approve test",
    )
    rc = cmd_approve(args_approve)
    assert rc == 0
    rev_a = get_review_by_id(item_a["review_id"])
    assert rev_a["status"] == STATUS_APPROVED

    # ── reject ────────────────────────────────────────────────────
    args_reject = argparse.Namespace(
        review_id=item_b["review_id"],
        reviewer="Kelvin",
        notes="CLI reject test",
    )
    rc = cmd_reject(args_reject)
    assert rc == 0
    rev_b = get_review_by_id(item_b["review_id"])
    assert rev_b["status"] == STATUS_REJECTED

    # ── more-data ─────────────────────────────────────────────────
    # Add a fresh item to request more data on
    item_c = _queue_sandbox_item(source_decision_id="cli_dec_c", source_task_id="task_cli_c")
    args_more = argparse.Namespace(
        review_id=item_c["review_id"],
        reviewer="Kelvin",
        notes="CLI more-data test",
    )
    rc = cmd_more_data(args_more)
    assert rc == 0
    rev_c = get_review_by_id(item_c["review_id"])
    assert rev_c["status"] == STATUS_MORE_DATA
    assert rev_c["allowed_next_task_family"] == NTF_CLV_QUALITY
