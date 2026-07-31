"""
test_p6_source_promotion_policy_contract.py
=============================================
P6 Source Promotion Policy — Contract Tests.

Tests the hard policy rules in evaluate_promotion_policy():
  1. PLAN_INSERT_REPLAY_ROW is required
  2. TIER_4_CODE_SCAN_ONLY is never auto-approved
  3. TIER_5_REJECTED_JSON_ONLY without numbers is rejected
  4. TIER_5_REJECTED_JSON_ONLY with numbers → MANUAL_REVIEW_REQUIRED
  5. provenance_hash must exist
  6. predicted_numbers must exist
  7. REJECTED lifecycle is blocked
  8. RETIRED lifecycle is approved with lifecycle_warning
  9. OBSERVATION lifecycle is approved with lifecycle_warning
 10. ONLINE lifecycle is approved without lifecycle_warning
 11. p5_can_apply=True triggers MANUAL_REVIEW
 12. p6_can_apply is always False
 13. dry_run_only is always True
 14. ARTIFACT_CANDIDATE lifecycle_state (mapped to REJECTED) is blocked
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from lottery_api.models.replay_source_promotion_policy import (
    SourcePromotionDecision,
    SourcePromotionTier,
    P7CandidateStatus,
    evaluate_promotion_policy,
)

# ---------------------------------------------------------------------------
# Base valid cell — passes all gates
# ---------------------------------------------------------------------------

def _valid_cell(**overrides) -> dict:
    base = {
        "strategy_id":           "fourier_rhythm_3bet",
        "lottery_type":          "POWER_LOTTO",
        "draw_id":               "115000030",
        "draw_date":             None,
        "planned_action":        "PLAN_INSERT_REPLAY_ROW",
        "source_tier":           SourcePromotionTier.TIER_1_DB_PREDICTION_PAYLOAD,
        "p5_can_apply":          False,
        "provenance_hash":       "abc123def456abc123def456abc123de",
        "has_predicted_numbers": True,
        "run_id":                177,
        "lifecycle_state":       "ONLINE",
        "lifecycle_warning":     None,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Section 1: planned_action gate
# ---------------------------------------------------------------------------

class TestPlannedActionGate:
    def test_plan_insert_is_required(self):
        for action in ("SKIP_NO_HISTORICAL_PAYLOAD", "SKIP_SOURCE_MISSING", "", "UNKNOWN"):
            result = evaluate_promotion_policy(_valid_cell(planned_action=action))
            assert result.p7_candidate_status == P7CandidateStatus.NOT_P7_CANDIDATE, (
                f"planned_action={action!r} should be NOT_P7_CANDIDATE"
            )
            assert result.promotion_decision == SourcePromotionDecision.REJECT_NOT_PLAN_INSERT

    def test_plan_insert_passes_action_gate(self):
        result = evaluate_promotion_policy(_valid_cell())
        assert result.promotion_decision != SourcePromotionDecision.REJECT_NOT_PLAN_INSERT


# ---------------------------------------------------------------------------
# Section 2: source tier gate
# ---------------------------------------------------------------------------

class TestSourceTierGate:
    def test_tier_4_code_scan_rejected(self):
        result = evaluate_promotion_policy(
            _valid_cell(source_tier=SourcePromotionTier.TIER_4_CODE_SCAN_ONLY)
        )
        assert result.p7_candidate_status == P7CandidateStatus.NOT_P7_CANDIDATE
        assert result.promotion_decision == SourcePromotionDecision.REJECT_CODE_SCAN_REEXEC_REQUIRED

    def test_tier_5_without_numbers_rejected(self):
        result = evaluate_promotion_policy(
            _valid_cell(
                source_tier=SourcePromotionTier.TIER_5_REJECTED_JSON_ONLY,
                has_predicted_numbers=False,
            )
        )
        assert result.p7_candidate_status == P7CandidateStatus.NOT_P7_CANDIDATE
        assert result.promotion_decision == SourcePromotionDecision.REJECT_SOURCE_MISSING

    def test_tier_5_with_numbers_is_manual_review(self):
        result = evaluate_promotion_policy(
            _valid_cell(
                source_tier=SourcePromotionTier.TIER_5_REJECTED_JSON_ONLY,
                has_predicted_numbers=True,
            )
        )
        assert result.p7_candidate_status == P7CandidateStatus.MANUAL_REVIEW_REQUIRED
        assert result.promotion_decision == SourcePromotionDecision.NEEDS_MANUAL_REVIEW

    def test_tier_2_rejected(self):
        result = evaluate_promotion_policy(
            _valid_cell(source_tier=SourcePromotionTier.TIER_2_LOG_DERIVED_PAYLOAD)
        )
        assert result.p7_candidate_status == P7CandidateStatus.NOT_P7_CANDIDATE
        assert result.promotion_decision == SourcePromotionDecision.REJECT_UNSUPPORTED_TRUTH_LEVEL

    def test_tier_0_rejected(self):
        result = evaluate_promotion_policy(
            _valid_cell(source_tier=SourcePromotionTier.TIER_0_UNKNOWN)
        )
        assert result.p7_candidate_status == P7CandidateStatus.NOT_P7_CANDIDATE

    def test_tier_1_passes(self):
        result = evaluate_promotion_policy(_valid_cell())
        assert result.source_tier == SourcePromotionTier.TIER_1_DB_PREDICTION_PAYLOAD
        assert result.p7_candidate_status == P7CandidateStatus.P7_CANDIDATE


# ---------------------------------------------------------------------------
# Section 3: provenance gate
# ---------------------------------------------------------------------------

class TestProvenanceGate:
    def test_missing_provenance_hash_rejected(self):
        result = evaluate_promotion_policy(_valid_cell(provenance_hash=None))
        assert result.p7_candidate_status == P7CandidateStatus.NOT_P7_CANDIDATE
        assert result.promotion_decision == SourcePromotionDecision.REJECT_PROVENANCE_MISSING

    def test_empty_provenance_hash_rejected(self):
        result = evaluate_promotion_policy(_valid_cell(provenance_hash=""))
        assert result.p7_candidate_status == P7CandidateStatus.NOT_P7_CANDIDATE
        assert result.promotion_decision == SourcePromotionDecision.REJECT_PROVENANCE_MISSING

    def test_present_provenance_hash_passes(self):
        result = evaluate_promotion_policy(_valid_cell(provenance_hash="deadbeef1234"))
        assert result.promotion_decision != SourcePromotionDecision.REJECT_PROVENANCE_MISSING


# ---------------------------------------------------------------------------
# Section 4: predicted numbers gate
# ---------------------------------------------------------------------------

class TestPredictedNumbersGate:
    def test_missing_numbers_rejected(self):
        result = evaluate_promotion_policy(_valid_cell(has_predicted_numbers=False))
        assert result.p7_candidate_status == P7CandidateStatus.NOT_P7_CANDIDATE
        assert result.promotion_decision == SourcePromotionDecision.REJECT_SOURCE_MISSING

    def test_present_numbers_passes(self):
        result = evaluate_promotion_policy(_valid_cell(has_predicted_numbers=True))
        assert result.promotion_decision != SourcePromotionDecision.REJECT_SOURCE_MISSING


# ---------------------------------------------------------------------------
# Section 5: lifecycle gate
# ---------------------------------------------------------------------------

class TestLifecycleGate:
    def test_rejected_lifecycle_blocked(self):
        result = evaluate_promotion_policy(_valid_cell(lifecycle_state="REJECTED"))
        assert result.p7_candidate_status == P7CandidateStatus.NOT_P7_CANDIDATE
        assert result.promotion_decision == SourcePromotionDecision.REJECT_LIFECYCLE_BLOCKED

    def test_offline_lifecycle_blocked(self):
        result = evaluate_promotion_policy(_valid_cell(lifecycle_state="OFFLINE"))
        assert result.p7_candidate_status == P7CandidateStatus.NOT_P7_CANDIDATE
        assert result.promotion_decision == SourcePromotionDecision.REJECT_LIFECYCLE_BLOCKED

    def test_online_lifecycle_approved_no_warning(self):
        result = evaluate_promotion_policy(_valid_cell(lifecycle_state="ONLINE"))
        assert result.p7_candidate_status == P7CandidateStatus.P7_CANDIDATE
        assert result.promotion_decision == SourcePromotionDecision.APPROVE_FOR_P7_CANDIDATE
        assert result.lifecycle_warning is None

    def test_retired_lifecycle_approved_with_warning(self):
        result = evaluate_promotion_policy(_valid_cell(lifecycle_state="RETIRED"))
        assert result.p7_candidate_status == P7CandidateStatus.P7_CANDIDATE
        assert result.promotion_decision == SourcePromotionDecision.APPROVE_FOR_P7_CANDIDATE
        assert result.lifecycle_warning is not None
        assert "RETIRED" in result.lifecycle_warning

    def test_observation_lifecycle_approved_with_warning(self):
        result = evaluate_promotion_policy(_valid_cell(lifecycle_state="OBSERVATION"))
        assert result.p7_candidate_status == P7CandidateStatus.P7_CANDIDATE
        assert result.promotion_decision == SourcePromotionDecision.APPROVE_FOR_P7_CANDIDATE
        assert result.lifecycle_warning is not None
        assert "OBSERVATION" in result.lifecycle_warning


# ---------------------------------------------------------------------------
# Section 6: p5_can_apply invariant
# ---------------------------------------------------------------------------

class TestP5CanApplyInvariant:
    def test_p5_can_apply_true_triggers_manual_review(self):
        result = evaluate_promotion_policy(_valid_cell(p5_can_apply=True))
        assert result.p7_candidate_status == P7CandidateStatus.MANUAL_REVIEW_REQUIRED
        assert result.p5_can_apply is True  # preserved as observed

    def test_p5_can_apply_false_unchanged(self):
        result = evaluate_promotion_policy(_valid_cell(p5_can_apply=False))
        assert result.p5_can_apply is False

    def test_p6_can_apply_always_false(self):
        result = evaluate_promotion_policy(_valid_cell())
        assert result.p6_can_apply is False

    def test_p6_can_apply_always_false_on_reject(self):
        result = evaluate_promotion_policy(_valid_cell(planned_action="SKIP_NO_HISTORICAL_PAYLOAD"))
        assert result.p6_can_apply is False


# ---------------------------------------------------------------------------
# Section 7: output fields
# ---------------------------------------------------------------------------

class TestOutputFields:
    def test_dry_run_only_always_true(self):
        for cell in [
            _valid_cell(),
            _valid_cell(planned_action="SKIP_NO_HISTORICAL_PAYLOAD"),
            _valid_cell(source_tier=SourcePromotionTier.TIER_4_CODE_SCAN_ONLY),
        ]:
            result = evaluate_promotion_policy(cell)
            assert result.dry_run_only is True

    def test_created_by_phase_is_p6(self):
        result = evaluate_promotion_policy(_valid_cell())
        assert result.created_by_phase == "P6"

    def test_to_dict_contains_required_keys(self):
        result = evaluate_promotion_policy(_valid_cell())
        d = result.to_dict()
        required = {
            "strategy_id", "lottery_type", "draw_id",
            "planned_action", "source_tier", "p5_can_apply",
            "promotion_decision", "p7_candidate_status",
            "p6_can_apply", "dry_run_only", "created_by_phase",
        }
        for key in required:
            assert key in d, f"Missing key {key!r} in to_dict() output"

    def test_p6_only_adds_candidate_status(self):
        """P6 must not invent new draw_id, strategy_id, or numbers."""
        cell   = _valid_cell()
        result = evaluate_promotion_policy(cell)
        assert result.strategy_id == cell["strategy_id"]
        assert result.draw_id == cell["draw_id"]
        assert result.lottery_type == cell["lottery_type"]
