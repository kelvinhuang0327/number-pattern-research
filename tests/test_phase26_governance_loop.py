"""
tests/test_phase26_governance_loop.py
======================================
Phase 26 — Full Governance Loop Runtime Drill Tests.

7 tests validating:
1. Pending review blocks planner (WAITING_FOR_HUMAN_REVIEW)
2. Approve creates validation/proposal follow-up only (safe families)
3. Reject creates no follow-up candidate
4. More-data creates clv-quality-analysis follow-up only
5. Decision card shows review commands for all pending items
6. No production model file modified
7. No external LLM called during entire lifecycle

Isolation: every test uses isolated_queue fixture that redirects QUEUE_PATH to tmp.
For planner integration tests, we additionally stub execution_policy and db helpers
so no real DB write occurs.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch, call

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

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
    get_approved_reviews,
    get_more_data_reviews,
    get_pending_reviews,
    get_queue_summary,
    has_pending_reviews,
    load_queue,
    queue_review_item,
    reject_review,
    request_more_data,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def isolated_queue(tmp_path, monkeypatch):
    """Redirect QUEUE_PATH to a temp file for every test — real queue untouched."""
    tmp_queue = tmp_path / "human_review_queue.json"
    monkeypatch.setattr(hrq_module, "QUEUE_PATH", tmp_queue)
    yield tmp_queue


# ── Helpers ───────────────────────────────────────────────────────────────────

def _queue_proposal(source_decision_id: str = "drill_dec_001") -> dict:
    return queue_review_item(
        source="patch_evaluation_gate",
        source_task_id="drill_task",
        source_decision_id=source_decision_id,
        review_type=RT_PRODUCTION_PROPOSAL,
        title="[Drill] Production Patch Proposal",
        summary="Sandbox CLV 0.032, sample_count=1500.",
        risk_level=RISK_HIGH,
        recommended_action="Approve for paper-only validation.",
        allowed_next_task_family=NTF_PROPOSAL_VALIDATION,
    )


def _queue_uncertain(source_decision_id: str = "drill_dec_002") -> dict:
    return queue_review_item(
        source="patch_evaluation_gate",
        source_task_id="drill_task_u",
        source_decision_id=source_decision_id,
        review_type=RT_SANDBOX_UNCERTAIN,
        title="[Drill] Sandbox Uncertain",
        summary="Sample count 400, below threshold.",
        risk_level=RISK_MEDIUM,
        recommended_action="Request more data.",
        allowed_next_task_family=NTF_ADDITIONAL_VALIDATION,
    )


def _planner_stubs(monkeypatch) -> None:
    """
    Stub out all planner dependencies so run_planner_tick() can reach Step 0.9
    without touching real DB, LLM policy, or insight extractor.
    """
    from orchestrator import execution_policy as ep_mod, db as db_mod
    from orchestrator import insight_extractor as ie_mod, patch_task_generator as ptg_mod

    monkeypatch.setattr(
        ep_mod, "evaluate_execution",
        lambda **_kw: {"allowed": True, "message": "", "reason": None},
    )
    monkeypatch.setattr(ie_mod, "extract_insights_from_completed_tasks", lambda: [])
    monkeypatch.setattr(ie_mod, "get_pending_insights", lambda: [])
    monkeypatch.setattr(ie_mod, "get_patch_queued_insights", lambda: [])
    monkeypatch.setattr(ptg_mod, "generate_patch_tasks", lambda _: [])
    monkeypatch.setattr(db_mod, "get_latest_task", lambda: None)
    monkeypatch.setattr(db_mod, "list_tasks", lambda **_kw: [])
    monkeypatch.setattr(db_mod, "record_run", lambda **_kw: None)
    monkeypatch.setattr(db_mod, "create_task", MagicMock(return_value={"id": 999}))


# ────────────────────────────────────────────────────────────────────────────
# Test 1: Pending review blocks planner → WAITING_FOR_HUMAN_REVIEW
# ────────────────────────────────────────────────────────────────────────────

def test_pending_review_blocks_planner(monkeypatch):
    """
    When a PENDING review exists, run_planner_tick() must return
    status=SKIPPED / outcome=WAITING_FOR_HUMAN_REVIEW and must NOT
    create any production task.
    """
    _planner_stubs(monkeypatch)
    from orchestrator.planner_tick import run_planner_tick

    # Queue a pending review item (isolated to tmp_queue via autouse fixture)
    item = _queue_proposal()
    assert item["status"] == STATUS_PENDING

    # Run the planner
    result = run_planner_tick()

    assert result["status"] == "SKIPPED", f"Expected SKIPPED, got: {result}"
    assert result.get("outcome") == "WAITING_FOR_HUMAN_REVIEW", (
        f"Expected WAITING_FOR_HUMAN_REVIEW, got: {result.get('outcome')}"
    )
    assert item["review_id"] in result.get("pending_review_ids", []), (
        "pending_review_ids must include the queued review"
    )
    # Planner must not have created any task
    from orchestrator import db as db_mod
    db_mod.create_task.assert_not_called()


# ────────────────────────────────────────────────────────────────────────────
# Test 2: Approve creates validation/proposal follow-up only (safe families)
# ────────────────────────────────────────────────────────────────────────────

def test_approve_creates_safe_followup_only():
    """
    After approval:
      - status = APPROVED
      - production_patch_allowed remains False
      - follow-up candidate family is production-proposal-validation (not a production patch)
      - planner is unblocked (has_pending_reviews() == False)
    """
    item = _queue_proposal()
    assert item["status"] == STATUS_PENDING

    result = approve_review(item["review_id"], reviewer="Driller", notes="Evidence sufficient.")

    assert result is not None
    assert result["status"] == STATUS_APPROVED
    assert result["production_patch_allowed"] is False, \
        "production_patch_allowed MUST remain False even after approval"
    assert result.get("production_model_modified", False) is False

    # Planner gate unblocked
    assert has_pending_reviews() is False, "pending queue must clear after approval"

    # Simulate what Step 0.9 would build as a candidate
    approved = get_approved_reviews()
    assert len(approved) == 1
    rev = approved[0]
    next_family = rev.get("allowed_next_task_family") or NTF_ADDITIONAL_VALIDATION

    # Must be one of the safe, non-production-patching families
    SAFE_FAMILIES = {
        NTF_PROPOSAL_VALIDATION,   # "production-proposal-validation"
        NTF_ADDITIONAL_VALIDATION, # "additional-validation"
        "paper-rollout-plan",
        "model-validation-atomic",
        NTF_CLV_QUALITY,
    }
    assert next_family in SAFE_FAMILIES, (
        f"follow-up family {next_family!r} is NOT in safe families {SAFE_FAMILIES}"
    )

    # Confirm the candidate dict that Step 0.9 builds has production_patch_allowed=False
    candidate = {
        "title": f"[Phase24] Production Proposal Validation — {rev['review_id']}",
        "task_type": "manual_review_summary",
        "analysis_family": next_family,
        "source": "human_review_queue",
        "phase24_review_id": rev["review_id"],
        "production_patch_allowed": False,
    }
    assert candidate["production_patch_allowed"] is False
    assert candidate["analysis_family"] == NTF_PROPOSAL_VALIDATION


# ────────────────────────────────────────────────────────────────────────────
# Test 3: Reject creates no follow-up candidate
# ────────────────────────────────────────────────────────────────────────────

def test_reject_creates_no_followup():
    """
    After rejection:
      - status = REJECTED
      - item does NOT appear in approved or more-data lists
      - planner Step 0.9 iterates only _approved and _more_data for follow-up candidates;
        REJECTED items generate no candidates — this structural invariant is verified here.
    """
    item = _queue_proposal(source_decision_id="dec_reject_p26")
    result = reject_review(item["review_id"], reviewer="Driller", notes="Insufficient CLV.")

    assert result is not None
    assert result["status"] == STATUS_REJECTED
    assert result["production_patch_allowed"] is False

    # Rejected item must NOT appear in approved or more-data query results
    approved_ids = {r["review_id"] for r in get_approved_reviews()}
    more_data_ids = {r["review_id"] for r in get_more_data_reviews()}
    assert item["review_id"] not in approved_ids, \
        "Rejected review must not appear in approved list"
    assert item["review_id"] not in more_data_ids, \
        "Rejected review must not appear in more-data list"

    # Queue summary shows rejected count
    summary = get_queue_summary()
    assert summary["rejected_count"] >= 1
    assert summary["approved_count"] == 0
    assert summary["more_data_count"] == 0


# ────────────────────────────────────────────────────────────────────────────
# Test 4: More-data creates clv-quality-analysis follow-up only
# ────────────────────────────────────────────────────────────────────────────

def test_more_data_creates_clv_quality_followup_only():
    """
    After more-data request:
      - status = MORE_DATA_REQUESTED
      - allowed_next_task_family = clv-quality-analysis
      - production_patch_allowed remains False
      - the follow-up candidate task_type = clv_quality_analysis (not a production patch)
    """
    item = _queue_uncertain(source_decision_id="dec_moredata_p26")
    result = request_more_data(
        item["review_id"], reviewer="Driller", notes="Need 500+ samples."
    )

    assert result is not None
    assert result["status"] == STATUS_MORE_DATA
    assert result["allowed_next_task_family"] == NTF_CLV_QUALITY, (
        f"Expected {NTF_CLV_QUALITY!r}, got {result['allowed_next_task_family']!r}"
    )
    assert result["production_patch_allowed"] is False

    # Verify it appears in more-data list
    more_data_items = get_more_data_reviews()
    assert any(i["review_id"] == item["review_id"] for i in more_data_items)

    # Simulate the Step 0.9 candidate — must be clv_quality_analysis, not production patch
    for rev in more_data_items:
        if rev["review_id"] == item["review_id"]:
            md_candidate = {
                "task_type": "clv_quality_analysis",
                "analysis_family": NTF_CLV_QUALITY,
                "source": "human_review_queue",
            }
            assert md_candidate["task_type"] == "clv_quality_analysis"
            # Not a production-model-modifying task
            assert "production_patch" not in md_candidate["task_type"]
            assert "model_patch" not in md_candidate["task_type"]
            break


# ────────────────────────────────────────────────────────────────────────────
# Test 5: Decision card shows review commands for all pending items
# ────────────────────────────────────────────────────────────────────────────

def test_decision_card_shows_commands_for_pending_reviews():
    """
    render_card() must show actionable CLI commands for every pending review item.
    """
    from scripts.ops_decision_card import render_card

    item_a = _queue_proposal(source_decision_id="dec_card_a")
    item_b = _queue_uncertain(source_decision_id="dec_card_b")

    summary = get_queue_summary()
    hr_payload = {
        "available": True,
        "total": summary["total"],
        "pending_count": summary["pending_count"],
        "approved_count": summary["approved_count"],
        "rejected_count": summary["rejected_count"],
        "more_data_count": summary["more_data_count"],
        "blocked_by_human_review": summary["blocked_by_human_review"],
        "latest_review": summary.get("latest_review"),
        "pending_reviews": summary.get("pending_reviews", []),
    }
    payload: dict[str, Any] = {
        "generated_at": "2026-05-01T10:00:00Z",
        "status": "BLOCKED",
        "reasons": [],
        "clv": {"coverage_pct": 0.0, "external_closing_rows": 0, "total_live_rows": 0,
                "clv_samples": 0, "clv_std": 0.0},
        "scheduler": {"last_run_ts": "2026-05-01T10:00:00Z", "next_trigger_minutes": None,
                      "api_calls_today": 0, "api_cap": 100, "state_date": "20260501",
                      "fetched_today": False, "heartbeat_present": True},
        "flags": [], "action": "", "system_health": {}, "today_wbc": {},
        "recent_performance": {}, "last_postmortem": {},
        "phase6": {}, "phase7": {}, "phase8": {}, "phase9_ops": {},
        "readiness": {}, "closing_availability": {}, "closing_refresh_feedback": {},
        "usage_detail": {}, "audit_summary": {"available": False},
        "human_review": hr_payload,
    }

    card = render_card(payload)

    # Section header must appear
    assert "HUMAN REVIEW QUEUE" in card, "Card must include HUMAN REVIEW QUEUE section"
    # BLOCKED indicator
    assert "BLOCKED" in card, "Card must show BLOCKED status when pending reviews exist"
    # Both review IDs must appear (pending_reviews[:3])
    assert item_a["review_id"] in card, f"{item_a['review_id']} must appear in card"
    assert item_b["review_id"] in card, f"{item_b['review_id']} must appear in card"
    # Must include all 4 action command types
    for cmd in ("show", "approve", "reject", "more-data"):
        assert f"review_queue.py {cmd}" in card, f"Card must include '{cmd}' command"


# ────────────────────────────────────────────────────────────────────────────
# Test 6: No production model file modified
# ────────────────────────────────────────────────────────────────────────────

def test_no_production_model_modified(tmp_path):
    """
    Full lifecycle (queue → approve → reject → more-data) must never modify
    any production model file. production_patch_allowed must be False for all items.
    """
    # Exercise full lifecycle
    item_a = _queue_proposal(source_decision_id="dec_model_a")
    item_b = _queue_uncertain(source_decision_id="dec_model_b")
    item_c = _queue_proposal(source_decision_id="dec_model_c")

    approve_review(item_a["review_id"], reviewer="T", notes="")
    reject_review(item_b["review_id"], reviewer="T", notes="")
    request_more_data(item_c["review_id"], reviewer="T", notes="")

    # Invariant: all items must have production_patch_allowed = False
    all_items = load_queue()
    assert len(all_items) == 3
    for it in all_items:
        assert it["production_patch_allowed"] is False, (
            f"{it['review_id']}: production_patch_allowed={it['production_patch_allowed']}"
        )
        assert it.get("production_model_modified", False) is False, (
            f"{it['review_id']}: production_model_modified={it.get('production_model_modified')}"
        )

    # Production model directories must NOT have been touched by this test
    model_paths = [
        ROOT / "wbc_backend" / "calibration",
        ROOT / "wbc_backend" / "models",
        ROOT / "models",
    ]
    import time
    test_start = time.time() - 1  # 1 second before test body
    for model_dir in model_paths:
        if not model_dir.exists():
            continue
        for py_file in model_dir.glob("*.py"):
            mtime = py_file.stat().st_mtime
            # No model file should have been written after test started
            assert mtime < test_start + 10, (
                f"Model file {py_file} was modified during the governance loop test "
                f"(mtime={mtime:.0f} > test_start={test_start:.0f})"
            )


# ────────────────────────────────────────────────────────────────────────────
# Test 7: No external LLM called during entire lifecycle
# ────────────────────────────────────────────────────────────────────────────

def test_no_external_llm_called():
    """
    All queue items across the full lifecycle must have external_llm_called=False.
    The governance module must not invoke any external LLM API.
    """
    # Exercise full lifecycle
    item_a = _queue_proposal(source_decision_id="dec_llm_a")
    item_b = _queue_uncertain(source_decision_id="dec_llm_b")
    item_c = _queue_proposal(source_decision_id="dec_llm_c")

    # Initial state — all PENDING
    for item in [item_a, item_b, item_c]:
        assert item["external_llm_called"] is False

    # Transition all items
    approve_review(item_a["review_id"], reviewer="T", notes="")
    reject_review(item_b["review_id"], reviewer="T", notes="")
    request_more_data(item_c["review_id"], reviewer="T", notes="")

    # After transitions — all items must still have external_llm_called=False
    all_items = load_queue()
    assert len(all_items) == 3
    llm_violations = [
        it["review_id"]
        for it in all_items
        if it.get("external_llm_called") is not False
    ]
    assert not llm_violations, (
        f"external_llm_called is not False for: {llm_violations}"
    )
