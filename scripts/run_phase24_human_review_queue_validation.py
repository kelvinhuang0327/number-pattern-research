#!/usr/bin/env python3
"""
scripts/run_phase24_human_review_queue_validation.py
=====================================================
Phase 24 — End-to-end validation script.
Runs 7 deterministic steps that exercise the full Human Review Queue lifecycle.

Verdict on success: PHASE_24_HUMAN_REVIEW_QUEUE_VERIFIED
"""
from __future__ import annotations

import sys
import tempfile
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
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
    get_pending_reviews,
    get_approved_reviews,
    get_more_data_reviews,
    get_queue_summary,
    has_pending_reviews,
    queue_review_item,
    reject_review,
    request_more_data,
)

# ── ANSI ─────────────────────────────────────────────────────────────────────
_G = "\033[32m"
_R = "\033[31m"
_Y = "\033[33m"
_B = "\033[1m"
_Z = "\033[0m"

STEPS_TOTAL = 7
steps_passed = 0
_sub_ok_count = 0  # sub-steps inside a single numbered step


def ok(msg: str, sub: bool = False) -> None:
    global steps_passed, _sub_ok_count
    if not sub:
        steps_passed += 1
    print(f"  {_G}✓{_Z} {msg}")


def fail(msg: str, exc: Exception | None = None) -> None:
    print(f"  {_R}✗ FAIL: {msg}{_Z}")
    if exc:
        print(f"    {exc}")
    sys.exit(1)


def step(n: int, title: str) -> None:
    print(f"\n{_B}Step {n}/{STEPS_TOTAL}: {title}{_Z}")


# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    print(f"\n{_B}Phase 24 — Human Review Queue Validation{_Z}")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp) / "human_review_queue.json"
        # Redirect module to temp file
        hrq_module.QUEUE_PATH = tmp_path

        # ── Step 1: queue item → PENDING ─────────────────────────────────
        step(1, "Queue review item → PENDING")
        try:
            item = queue_review_item(
                source="patch_evaluation_gate",
                source_task_id="val_task_001",
                source_decision_id=f"val_dec_{uuid.uuid4().hex[:8]}",
                review_type=RT_SANDBOX_UNCERTAIN,
                title="[Validation] Sandbox Uncertain",
                summary="Sandbox evaluation returned uncertain outcome.",
                risk_level=RISK_MEDIUM,
                recommended_action="Review and decide.",
                allowed_next_task_family=NTF_ADDITIONAL_VALIDATION,
            )
            assert item["status"] == STATUS_PENDING, f"Expected PENDING, got {item['status']}"
            assert item["production_patch_allowed"] is False
            assert item["external_llm_called"] is False
            assert has_pending_reviews() is True
            ok(f"queued {item['review_id']} → status={item['status']}")
        except Exception as exc:
            fail("queue_review_item() failed", exc)

        # ── Step 2: duplicate source_decision_id → no duplicate ──────────
        step(2, "Duplicate source_decision_id → no additional item created")
        try:
            dec_id = f"val_dec_{uuid.uuid4().hex[:8]}"
            item_a = queue_review_item(
                source="patch_evaluation_gate",
                source_task_id="val_task_002a",
                source_decision_id=dec_id,
                review_type=RT_SANDBOX_UNCERTAIN,
                title="Dup A",
                summary="First call",
                risk_level=RISK_MEDIUM,
                recommended_action="Review",
                allowed_next_task_family=NTF_ADDITIONAL_VALIDATION,
            )
            item_b = queue_review_item(
                source="patch_evaluation_gate",
                source_task_id="val_task_002b",
                source_decision_id=dec_id,
                review_type=RT_SANDBOX_UNCERTAIN,
                title="Dup B",
                summary="Second call — should be deduplicated",
                risk_level=RISK_MEDIUM,
                recommended_action="Review",
                allowed_next_task_family=NTF_ADDITIONAL_VALIDATION,
            )
            assert item_a["review_id"] == item_b["review_id"], "Deduplication failed"
            ok(f"same review_id returned on duplicate: {item_a['review_id']}")
        except Exception as exc:
            fail("Deduplication check failed", exc)

        # ── Step 3: approve_review → APPROVED, production_patch_allowed still False ──
        step(3, "approve_review() → APPROVED, production_patch_allowed remains False")
        try:
            # pick item from step 2 (item_a = PENDING)
            result = approve_review(item_a["review_id"], reviewer="Validator", notes="Step 3 ok")
            assert result is not None
            assert result["status"] == STATUS_APPROVED, f"Expected APPROVED, got {result['status']}"
            assert result["production_patch_allowed"] is False, "production_patch_allowed must stay False"
            assert result["reviewer"] == "Validator"
            ok(f"{item_a['review_id']} → APPROVED (production_patch_allowed=False)")
        except Exception as exc:
            fail("approve_review() failed", exc)

        # ── Step 4: reject_review → REJECTED, blocks follow-up ──────────
        step(4, "reject_review() → REJECTED, blocks follow-up")
        try:
            item_r = queue_review_item(
                source="patch_evaluation_gate",
                source_task_id="val_task_004",
                source_decision_id=f"val_dec_{uuid.uuid4().hex[:8]}",
                review_type=RT_PRODUCTION_PROPOSAL,
                title="[Validation] Production Proposal",
                summary="Promote criteria met.",
                risk_level=RISK_HIGH,
                recommended_action="Review evidence.",
                allowed_next_task_family=NTF_PROPOSAL_VALIDATION,
            )
            r_result = reject_review(item_r["review_id"], reviewer="Validator", notes="Insufficient evidence")
            assert r_result is not None
            assert r_result["status"] == STATUS_REJECTED
            assert r_result["production_patch_allowed"] is False
            # the rejected item must not appear in approved list
            approved_ids = {i["review_id"] for i in get_approved_reviews()}
            assert item_r["review_id"] not in approved_ids, "Rejected item must not appear in approved list"
            ok(f"{item_r['review_id']} → REJECTED (production_patch_allowed=False)")
        except Exception as exc:
            fail("reject_review() failed", exc)

        # ── Step 5: request_more_data → MORE_DATA_REQUESTED, clv-quality-analysis ──
        step(5, "request_more_data() → MORE_DATA_REQUESTED, allowed_next_task_family=clv-quality-analysis")
        try:
            item_md = queue_review_item(
                source="patch_evaluation_gate",
                source_task_id="val_task_005",
                source_decision_id=f"val_dec_{uuid.uuid4().hex[:8]}",
                review_type=RT_SANDBOX_UNCERTAIN,
                title="[Validation] More Data",
                summary="Outcome uncertain — need more data.",
                risk_level=RISK_MEDIUM,
                recommended_action="Request additional CLV data.",
                allowed_next_task_family=NTF_ADDITIONAL_VALIDATION,
            )
            md_result = request_more_data(item_md["review_id"], reviewer="Validator", notes="Need 50+ samples")
            assert md_result is not None
            assert md_result["status"] == STATUS_MORE_DATA
            assert md_result["allowed_next_task_family"] == NTF_CLV_QUALITY, (
                f"Expected {NTF_CLV_QUALITY}, got {md_result['allowed_next_task_family']}"
            )
            ok(f"{item_md['review_id']} → MORE_DATA_REQUESTED (family={NTF_CLV_QUALITY})")
        except Exception as exc:
            fail("request_more_data() failed", exc)

        # ── Step 6: get_queue_summary reflects counts + blocked_by_human_review ──
        step(6, "get_queue_summary() reflects correct counts and blocked_by_human_review flag")
        try:
            # Add a fresh PENDING item to block the planner
            item_block = queue_review_item(
                source="manual",
                source_task_id="val_task_006",
                source_decision_id=f"val_dec_{uuid.uuid4().hex[:8]}",
                review_type=RT_SANDBOX_UNCERTAIN,
                title="[Validation] Block Test",
                summary="Pending review that blocks planner.",
                risk_level=RISK_MEDIUM,
                recommended_action="Review.",
                allowed_next_task_family=NTF_ADDITIONAL_VALIDATION,
            )
            summary = get_queue_summary()
            assert summary["blocked_by_human_review"] is True, "Expected blocked=True with a PENDING item"
            assert summary["pending_count"] >= 1
            assert "approved_count" in summary
            assert "rejected_count" in summary
            assert "more_data_count" in summary
            ok(
                f"summary: total={summary['total']}, pending={summary['pending_count']}, "
                f"approved={summary['approved_count']}, rejected={summary['rejected_count']}, "
                f"more_data={summary['more_data_count']}, blocked={summary['blocked_by_human_review']}"
            )
            # Approve all remaining pending items to unblock
            for pending_item in get_pending_reviews():
                approve_review(pending_item["review_id"], reviewer="Validator", notes="Step 6 cleanup")
            summary2 = get_queue_summary()
            assert summary2["blocked_by_human_review"] is False, "Expected unblocked after approval"
            ok("unblocked after approval ✓", sub=True)
        except Exception as exc:
            fail("get_queue_summary() failed", exc)

        # ── Step 7: No external LLM called end-to-end ────────────────────
        step(7, "Verify no external LLM was called (all items have external_llm_called=False)")
        try:
            from orchestrator.human_review_queue import load_queue
            all_items = load_queue()
            for it in all_items:
                if it.get("external_llm_called") is not False:
                    fail(
                        f"review_id={it.get('review_id')} has external_llm_called="
                        f"{it.get('external_llm_called')} — must be False"
                    )
            ok(f"All {len(all_items)} queue items have external_llm_called=False")
        except SystemExit:
            raise
        except Exception as exc:
            fail("LLM-free check failed", exc)

    # ── Final verdict ─────────────────────────────────────────────────────────
    print(f"\n{'=' * 60}")
    if steps_passed == STEPS_TOTAL:
        print(f"{_G}{_B}✅ ALL {STEPS_TOTAL}/{STEPS_TOTAL} STEPS PASSED{_Z}")
        print(f"{_G}{_B}VERDICT: PHASE_24_HUMAN_REVIEW_QUEUE_VERIFIED{_Z}")
    else:
        print(f"{_R}{_B}❌ {steps_passed}/{STEPS_TOTAL} STEPS PASSED — VALIDATION FAILED{_Z}")
        sys.exit(1)


if __name__ == "__main__":
    main()
