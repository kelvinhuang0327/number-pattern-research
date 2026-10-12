"""
replay_source_promotion_policy.py
===================================
P6 Source Promotion Policy Contract — read-only.

Defines the policy that gates which P5 PLAN_INSERT_REPLAY_ROW entries can
become P7 controlled-apply candidates.

Hard constraints (enforced here and in tests):
  - No DB writes anywhere in this module
  - No replay row generation
  - No lifecycle_state mutations
  - ARTIFACT_CANDIDATE never becomes a P7 candidate
  - TIER_4_CODE_SCAN_ONLY never auto-approved
  - TIER_5_REJECTED_JSON_ONLY without per-draw payload never auto-approved
  - P6 must NOT flip p5_can_apply from False to True
  - P7 candidate status is the ONLY output added by P6
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# SourcePromotionDecision
# ---------------------------------------------------------------------------

class SourcePromotionDecision:
    """P6 gate decision for a single (strategy, draw) plan cell."""

    APPROVE_FOR_P7_CANDIDATE          = "APPROVE_FOR_P7_CANDIDATE"
    REJECT_SOURCE_MISSING             = "REJECT_SOURCE_MISSING"
    REJECT_PROVENANCE_MISSING         = "REJECT_PROVENANCE_MISSING"
    REJECT_CODE_SCAN_REEXEC_REQUIRED  = "REJECT_CODE_SCAN_REEXEC_REQUIRED"
    REJECT_ARTIFACT_CANDIDATE         = "REJECT_ARTIFACT_CANDIDATE"
    REJECT_UNSUPPORTED_TRUTH_LEVEL    = "REJECT_UNSUPPORTED_TRUTH_LEVEL"
    REJECT_LIFECYCLE_BLOCKED          = "REJECT_LIFECYCLE_BLOCKED"
    REJECT_NOT_PLAN_INSERT            = "REJECT_NOT_PLAN_INSERT"
    NEEDS_MANUAL_REVIEW               = "NEEDS_MANUAL_REVIEW"

    _APPROVE_DECISIONS = frozenset({APPROVE_FOR_P7_CANDIDATE})
    _REJECT_DECISIONS  = frozenset({
        REJECT_SOURCE_MISSING,
        REJECT_PROVENANCE_MISSING,
        REJECT_CODE_SCAN_REEXEC_REQUIRED,
        REJECT_ARTIFACT_CANDIDATE,
        REJECT_UNSUPPORTED_TRUTH_LEVEL,
        REJECT_LIFECYCLE_BLOCKED,
        REJECT_NOT_PLAN_INSERT,
    })

    _ALL = (
        APPROVE_FOR_P7_CANDIDATE,
        REJECT_SOURCE_MISSING,
        REJECT_PROVENANCE_MISSING,
        REJECT_CODE_SCAN_REEXEC_REQUIRED,
        REJECT_ARTIFACT_CANDIDATE,
        REJECT_UNSUPPORTED_TRUTH_LEVEL,
        REJECT_LIFECYCLE_BLOCKED,
        REJECT_NOT_PLAN_INSERT,
        NEEDS_MANUAL_REVIEW,
    )

    @classmethod
    def is_approve(cls, decision: str) -> bool:
        return decision in cls._APPROVE_DECISIONS

    @classmethod
    def is_reject(cls, decision: str) -> bool:
        return decision in cls._REJECT_DECISIONS


# ---------------------------------------------------------------------------
# SourcePromotionTier
# ---------------------------------------------------------------------------

class SourcePromotionTier:
    """Source quality tier for a prediction payload."""

    TIER_1_DB_PREDICTION_PAYLOAD  = "TIER_1_DB_PREDICTION_PAYLOAD"
    TIER_2_LOG_DERIVED_PAYLOAD    = "TIER_2_LOG_DERIVED_PAYLOAD"
    TIER_3_STATE_DERIVED_PAYLOAD  = "TIER_3_STATE_DERIVED_PAYLOAD"
    TIER_4_CODE_SCAN_ONLY         = "TIER_4_CODE_SCAN_ONLY"
    TIER_5_REJECTED_JSON_ONLY     = "TIER_5_REJECTED_JSON_ONLY"
    TIER_0_UNKNOWN                = "TIER_0_UNKNOWN"

    # Only TIER_1 can be auto-approved by P6 policy.
    AUTO_APPROVABLE_TIERS = frozenset({TIER_1_DB_PREDICTION_PAYLOAD})

    _ALL = (
        TIER_1_DB_PREDICTION_PAYLOAD,
        TIER_2_LOG_DERIVED_PAYLOAD,
        TIER_3_STATE_DERIVED_PAYLOAD,
        TIER_4_CODE_SCAN_ONLY,
        TIER_5_REJECTED_JSON_ONLY,
        TIER_0_UNKNOWN,
    )


# ---------------------------------------------------------------------------
# P7CandidateStatus
# ---------------------------------------------------------------------------

class P7CandidateStatus:
    """Final P7 candidate classification after P6 policy."""

    P7_CANDIDATE           = "P7_CANDIDATE"
    NOT_P7_CANDIDATE       = "NOT_P7_CANDIDATE"
    MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"

    _ALL = (P7_CANDIDATE, NOT_P7_CANDIDATE, MANUAL_REVIEW_REQUIRED)


# ---------------------------------------------------------------------------
# SourcePromotionResult
# ---------------------------------------------------------------------------

@dataclass
class SourcePromotionResult:
    """
    P6 policy evaluation result for a single (strategy, draw) plan cell.

    Produced by evaluate_promotion_policy().
    P6 does NOT modify p5_can_apply — it only adds p7_candidate_status
    and promotion_decision to the plan cell.
    """

    # Identity
    strategy_id:         str
    lottery_type:        str
    draw_id:             str
    draw_date:           Optional[str]

    # From P5 plan
    planned_action:      str       # e.g. PLAN_INSERT_REPLAY_ROW / SKIP_*
    source_tier:         str       # SourcePromotionTier constant
    p5_can_apply:        bool      # always False from P5 — P6 must not change

    # Provenance (from P5)
    provenance_hash:     Optional[str]
    has_predicted_numbers: bool
    run_id:              Optional[int]

    # Lifecycle info (from P5 / P1)
    lifecycle_state:     str       # ONLINE / RETIRED / REJECTED / OBSERVATION / OFFLINE
    lifecycle_warning:   Optional[str]  # set when lifecycle is not ONLINE

    # P6 outputs (set by evaluate_promotion_policy)
    promotion_decision:  str = SourcePromotionDecision.NEEDS_MANUAL_REVIEW
    p7_candidate_status: str = P7CandidateStatus.NOT_P7_CANDIDATE
    rejection_reason:    Optional[str] = None

    # Metadata
    dry_run_only:        bool = True   # always True
    p6_can_apply:        bool = False  # always False
    created_by_phase:    str  = "P6"

    def to_dict(self) -> dict:
        return {
            "strategy_id":           self.strategy_id,
            "lottery_type":          self.lottery_type,
            "draw_id":               self.draw_id,
            "draw_date":             self.draw_date,
            "planned_action":        self.planned_action,
            "source_tier":           self.source_tier,
            "p5_can_apply":          self.p5_can_apply,
            "provenance_hash":       self.provenance_hash,
            "has_predicted_numbers": self.has_predicted_numbers,
            "run_id":                self.run_id,
            "lifecycle_state":       self.lifecycle_state,
            "lifecycle_warning":     self.lifecycle_warning,
            "promotion_decision":    self.promotion_decision,
            "p7_candidate_status":   self.p7_candidate_status,
            "rejection_reason":      self.rejection_reason,
            "dry_run_only":          self.dry_run_only,
            "p6_can_apply":          self.p6_can_apply,
            "created_by_phase":      self.created_by_phase,
        }


# ---------------------------------------------------------------------------
# Core policy function
# ---------------------------------------------------------------------------

# Lifecycle states that are permitted as P7 candidates (with warning for non-ONLINE)
_PERMITTED_LIFECYCLE_STATES = frozenset({
    "ONLINE", "RETIRED", "OBSERVATION",
})

# REJECTED/OFFLINE/UNSUPPORTED lifecycle states are blocked
_BLOCKED_LIFECYCLE_STATES = frozenset({
    "REJECTED", "OFFLINE",
})


def evaluate_promotion_policy(cell: dict) -> SourcePromotionResult:
    """
    Apply P6 hard policy rules to a single P5 plan cell.

    Returns a SourcePromotionResult with promotion_decision and
    p7_candidate_status set. Never modifies p5_can_apply.

    Policy (in priority order):
      1. planned_action must be PLAN_INSERT_REPLAY_ROW
      2. p5_can_apply must remain False (invariant check)
      3. lifecycle_state must not be in blocked set
      4. source_tier must be TIER_1_DB_PREDICTION_PAYLOAD for auto-approve
      5. provenance_hash must exist
      6. predicted_numbers must exist
      7. RETIRED lifecycle → APPROVE with lifecycle_warning
      8. OBSERVATION lifecycle → APPROVE with lifecycle_warning
      9. ONLINE lifecycle → APPROVE (no warning)
    """
    strategy_id   = cell.get("strategy_id", "")
    lottery_type  = cell.get("lottery_type", "")
    draw_id       = cell.get("draw_id", "")
    draw_date     = cell.get("draw_date")
    planned_action = cell.get("planned_action", "")
    source_tier   = cell.get("source_tier", SourcePromotionTier.TIER_0_UNKNOWN)
    p5_can_apply  = cell.get("p5_can_apply", False)
    provenance_hash = cell.get("provenance_hash")
    has_numbers   = cell.get("has_predicted_numbers", False)
    run_id        = cell.get("run_id")
    lifecycle     = cell.get("lifecycle_state", "")
    lifecycle_warning = cell.get("lifecycle_warning")

    # Safety invariant: P6 must see p5_can_apply=False
    if p5_can_apply:
        return SourcePromotionResult(
            strategy_id=strategy_id, lottery_type=lottery_type,
            draw_id=draw_id, draw_date=draw_date,
            planned_action=planned_action, source_tier=source_tier,
            p5_can_apply=True,  # preserve as seen
            provenance_hash=provenance_hash,
            has_predicted_numbers=has_numbers,
            run_id=run_id, lifecycle_state=lifecycle,
            lifecycle_warning=lifecycle_warning,
            promotion_decision=SourcePromotionDecision.NEEDS_MANUAL_REVIEW,
            p7_candidate_status=P7CandidateStatus.MANUAL_REVIEW_REQUIRED,
            rejection_reason="p5_can_apply is True — invariant violation, requires manual review",
        )

    def _reject(decision: str, reason: str) -> SourcePromotionResult:
        return SourcePromotionResult(
            strategy_id=strategy_id, lottery_type=lottery_type,
            draw_id=draw_id, draw_date=draw_date,
            planned_action=planned_action, source_tier=source_tier,
            p5_can_apply=False,
            provenance_hash=provenance_hash,
            has_predicted_numbers=has_numbers,
            run_id=run_id, lifecycle_state=lifecycle,
            lifecycle_warning=lifecycle_warning,
            promotion_decision=decision,
            p7_candidate_status=P7CandidateStatus.NOT_P7_CANDIDATE,
            rejection_reason=reason,
        )

    # Rule 1: must be PLAN_INSERT_REPLAY_ROW
    if planned_action != "PLAN_INSERT_REPLAY_ROW":
        return _reject(
            SourcePromotionDecision.REJECT_NOT_PLAN_INSERT,
            f"planned_action={planned_action!r} is not PLAN_INSERT_REPLAY_ROW",
        )

    # Rule 3: lifecycle must not be blocked
    if lifecycle in _BLOCKED_LIFECYCLE_STATES:
        return _reject(
            SourcePromotionDecision.REJECT_LIFECYCLE_BLOCKED,
            f"lifecycle_state={lifecycle!r} is not permitted for P7 candidates",
        )

    # Rule 4: source_tier must be TIER_1 for auto-approve
    if source_tier == SourcePromotionTier.TIER_4_CODE_SCAN_ONLY:
        return _reject(
            SourcePromotionDecision.REJECT_CODE_SCAN_REEXEC_REQUIRED,
            "TIER_4_CODE_SCAN_ONLY cannot be auto-approved; "
            "requires code re-execution to produce a verifiable payload",
        )

    if source_tier == SourcePromotionTier.TIER_5_REJECTED_JSON_ONLY:
        if not has_numbers:
            return _reject(
                SourcePromotionDecision.REJECT_SOURCE_MISSING,
                "TIER_5_REJECTED_JSON_ONLY without per-draw predicted_numbers "
                "cannot be auto-approved",
            )
        # TIER_5 with numbers → manual review
        return SourcePromotionResult(
            strategy_id=strategy_id, lottery_type=lottery_type,
            draw_id=draw_id, draw_date=draw_date,
            planned_action=planned_action, source_tier=source_tier,
            p5_can_apply=False,
            provenance_hash=provenance_hash,
            has_predicted_numbers=has_numbers,
            run_id=run_id, lifecycle_state=lifecycle,
            lifecycle_warning=lifecycle_warning,
            promotion_decision=SourcePromotionDecision.NEEDS_MANUAL_REVIEW,
            p7_candidate_status=P7CandidateStatus.MANUAL_REVIEW_REQUIRED,
            rejection_reason="TIER_5 with numbers requires manual review for provenance audit",
        )

    if source_tier not in SourcePromotionTier.AUTO_APPROVABLE_TIERS:
        return _reject(
            SourcePromotionDecision.REJECT_UNSUPPORTED_TRUTH_LEVEL,
            f"source_tier={source_tier!r} is not auto-approvable; "
            "only TIER_1_DB_PREDICTION_PAYLOAD qualifies",
        )

    # Rule 5: provenance_hash must exist
    if not provenance_hash:
        return _reject(
            SourcePromotionDecision.REJECT_PROVENANCE_MISSING,
            "provenance_hash is missing or empty",
        )

    # Rule 6: predicted_numbers must exist
    if not has_numbers:
        return _reject(
            SourcePromotionDecision.REJECT_SOURCE_MISSING,
            "predicted_numbers not found in historical payload",
        )

    # Rule 7-9: lifecycle-specific approval
    lc_warning: Optional[str] = None
    if lifecycle == "RETIRED":
        lc_warning = (
            f"strategy {strategy_id!r} is RETIRED — "
            "P7 apply will create historical-only rows; "
            "no production impact, but human review required before P7"
        )
    elif lifecycle == "OBSERVATION":
        lc_warning = (
            f"strategy {strategy_id!r} is in OBSERVATION — "
            "rows will be flagged as shadow/experimental"
        )
    # ONLINE → no warning

    return SourcePromotionResult(
        strategy_id=strategy_id, lottery_type=lottery_type,
        draw_id=draw_id, draw_date=draw_date,
        planned_action=planned_action, source_tier=source_tier,
        p5_can_apply=False,
        provenance_hash=provenance_hash,
        has_predicted_numbers=has_numbers,
        run_id=run_id, lifecycle_state=lifecycle,
        lifecycle_warning=lc_warning or lifecycle_warning,
        promotion_decision=SourcePromotionDecision.APPROVE_FOR_P7_CANDIDATE,
        p7_candidate_status=P7CandidateStatus.P7_CANDIDATE,
        rejection_reason=None,
    )


# ---------------------------------------------------------------------------
# Summary helpers
# ---------------------------------------------------------------------------

def summarize_promotion_results(results: List[SourcePromotionResult]) -> Dict:
    """Produce a P6 summary dict from a list of SourcePromotionResult."""
    from collections import Counter

    total              = len(results)
    approved           = [r for r in results if r.p7_candidate_status == P7CandidateStatus.P7_CANDIDATE]
    manual_review      = [r for r in results if r.p7_candidate_status == P7CandidateStatus.MANUAL_REVIEW_REQUIRED]
    rejected           = [r for r in results if r.p7_candidate_status == P7CandidateStatus.NOT_P7_CANDIDATE]
    plan_insert_rows   = [r for r in results if r.planned_action == "PLAN_INSERT_REPLAY_ROW"]

    rejected_by_reason = Counter(
        r.rejection_reason or "unknown"
        for r in rejected
        if r.rejection_reason
    )

    by_strategy = {}
    for r in results:
        if r.strategy_id not in by_strategy:
            by_strategy[r.strategy_id] = {
                "strategy_id":              r.strategy_id,
                "lifecycle_state":          r.lifecycle_state,
                "total_plan_cells":         0,
                "approved_for_p7":          0,
                "rejected":                 0,
                "manual_review_required":   0,
            }
        by_strategy[r.strategy_id]["total_plan_cells"] += 1
        if r.p7_candidate_status == P7CandidateStatus.P7_CANDIDATE:
            by_strategy[r.strategy_id]["approved_for_p7"] += 1
        elif r.p7_candidate_status == P7CandidateStatus.MANUAL_REVIEW_REQUIRED:
            by_strategy[r.strategy_id]["manual_review_required"] += 1
        else:
            by_strategy[r.strategy_id]["rejected"] += 1

    by_lifecycle = Counter(r.lifecycle_state for r in results)
    by_tier      = Counter(r.source_tier for r in results)
    lifecycle_warnings = [
        {
            "strategy_id":       r.strategy_id,
            "draw_id":           r.draw_id,
            "lifecycle_state":   r.lifecycle_state,
            "lifecycle_warning": r.lifecycle_warning,
        }
        for r in approved
        if r.lifecycle_warning
    ]

    return {
        "total_plan_rows":           total,
        "plan_insert_rows":          len(plan_insert_rows),
        "approved_for_p7_candidate": len(approved),
        "rejected_count":            len(rejected),
        "manual_review_required":    len(manual_review),
        "rejected_by_reason":        dict(rejected_by_reason),
        "by_strategy":               by_strategy,
        "by_lifecycle_state":        dict(by_lifecycle),
        "by_source_tier":            dict(by_tier),
        "lifecycle_warnings":        lifecycle_warnings,
        "p7_candidate_rows":         [r.to_dict() for r in approved],
    }
