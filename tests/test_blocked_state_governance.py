"""Tests for P12-B blocked_state_governance module."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from wbc_backend.recommendation.blocked_state_governance import (
    AllowedAction,
    BlockedReason,
    BlockedStateGovernance,
    ForbiddenAction,
    GovernanceViolationError,
    PaperOnlyViolationError,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fully_blocked() -> BlockedStateGovernance:
    """Return a governance object with all reasons active."""
    return BlockedStateGovernance(
        ceo_decision_pending=True,
        api_key_missing=True,
        post_game_proxy_only=True,
        no_closing_line=True,
        forward_accumulation_insufficient=True,
        clv_not_ready=True,
        promotion_frozen=True,
        paper_only=True,
    )


def _fully_clear() -> BlockedStateGovernance:
    """Return a governance object with no reasons active."""
    return BlockedStateGovernance(
        ceo_decision_pending=False,
        api_key_missing=False,
        post_game_proxy_only=False,
        no_closing_line=False,
        forward_accumulation_insufficient=False,
        clv_not_ready=False,
        promotion_frozen=False,
        paper_only=True,
    )


# ---------------------------------------------------------------------------
# TestCEOPendingBlocksOptimizerPromotion
# ---------------------------------------------------------------------------

class TestCEOPendingBlocksOptimizerPromotion:
    def test_ceo_pending_is_blocked(self):
        gov = BlockedStateGovernance(
            ceo_decision_pending=True,
            api_key_missing=False,
            post_game_proxy_only=False,
            no_closing_line=False,
            forward_accumulation_insufficient=False,
            clv_not_ready=False,
            promotion_frozen=False,
        )
        assert gov.is_blocked is True

    def test_ceo_pending_blocks_optimizer_promotion(self):
        gov = BlockedStateGovernance(
            ceo_decision_pending=True,
            api_key_missing=False,
            post_game_proxy_only=False,
            no_closing_line=False,
            forward_accumulation_insufficient=False,
            clv_not_ready=False,
            promotion_frozen=False,
        )
        assert gov.is_action_forbidden(ForbiddenAction.OPTIMIZER_PROMOTION) is True

    def test_ceo_pending_in_blocked_reasons(self):
        gov = BlockedStateGovernance(
            ceo_decision_pending=True,
            api_key_missing=False,
            post_game_proxy_only=False,
            no_closing_line=False,
            forward_accumulation_insufficient=False,
            clv_not_ready=False,
            promotion_frozen=False,
        )
        assert BlockedReason.CEO_DECISION_PENDING in gov.blocked_reasons

    def test_assert_forbidden_raises_governance_violation(self):
        gov = BlockedStateGovernance(
            ceo_decision_pending=True,
            api_key_missing=False,
            post_game_proxy_only=False,
            no_closing_line=False,
            forward_accumulation_insufficient=False,
            clv_not_ready=False,
            promotion_frozen=False,
        )
        with pytest.raises(GovernanceViolationError):
            gov.assert_action_not_forbidden(ForbiddenAction.OPTIMIZER_PROMOTION)


# ---------------------------------------------------------------------------
# TestNoClosingLineBlocksCLV
# ---------------------------------------------------------------------------

class TestNoClosingLineBlocksCLV:
    def test_no_closing_line_blocks_clv(self):
        gov = BlockedStateGovernance(
            ceo_decision_pending=False,
            api_key_missing=False,
            post_game_proxy_only=False,
            no_closing_line=True,
            forward_accumulation_insufficient=False,
            clv_not_ready=False,
            promotion_frozen=False,
        )
        assert gov.is_blocked is True
        assert BlockedReason.NO_CLOSING_LINE in gov.blocked_reasons

    def test_no_closing_line_forbidden_production_proposal(self):
        gov = BlockedStateGovernance(
            ceo_decision_pending=False,
            api_key_missing=False,
            post_game_proxy_only=False,
            no_closing_line=True,
            forward_accumulation_insufficient=False,
            clv_not_ready=False,
            promotion_frozen=False,
        )
        assert gov.is_action_forbidden(ForbiddenAction.PRODUCTION_PROPOSAL) is True

    def test_no_closing_line_p13_blocked(self):
        gov = BlockedStateGovernance(
            ceo_decision_pending=False,
            api_key_missing=False,
            post_game_proxy_only=False,
            no_closing_line=True,
            forward_accumulation_insufficient=False,
            clv_not_ready=False,
            promotion_frozen=False,
        )
        assert gov.p13_allowed() is False


# ---------------------------------------------------------------------------
# TestAccumulationInsufficientBlocksP13
# ---------------------------------------------------------------------------

class TestAccumulationInsufficientBlocksP13:
    def test_accumulation_insufficient_blocks_p13(self):
        gov = BlockedStateGovernance(
            ceo_decision_pending=False,
            api_key_missing=False,
            post_game_proxy_only=False,
            no_closing_line=False,
            forward_accumulation_insufficient=True,
            clv_not_ready=False,
            promotion_frozen=False,
        )
        assert gov.p13_allowed() is False

    def test_accumulation_insufficient_in_reasons(self):
        gov = BlockedStateGovernance(
            ceo_decision_pending=False,
            api_key_missing=False,
            post_game_proxy_only=False,
            no_closing_line=False,
            forward_accumulation_insufficient=True,
            clv_not_ready=False,
            promotion_frozen=False,
        )
        assert BlockedReason.FORWARD_ACCUMULATION_INSUFFICIENT in gov.blocked_reasons

    def test_clear_state_p13_allowed(self):
        gov = _fully_clear()
        assert gov.p13_allowed() is True
        assert gov.is_blocked is False


# ---------------------------------------------------------------------------
# TestPaperOnlyMonitorAllowed
# ---------------------------------------------------------------------------

class TestPaperOnlyMonitorAllowed:
    def test_paper_only_monitor_allowed_when_blocked(self):
        gov = _fully_blocked()
        assert gov.is_action_allowed(AllowedAction.PAPER_ONLY_MONITORING) is True

    def test_ceo_followup_allowed_when_blocked(self):
        gov = _fully_blocked()
        assert gov.is_action_allowed(AllowedAction.CEO_FOLLOWUP) is True

    def test_forward_coverage_check_allowed_when_blocked(self):
        gov = _fully_blocked()
        assert gov.is_action_allowed(AllowedAction.FORWARD_COVERAGE_READINESS_CHECK) is True

    def test_api_key_readiness_check_allowed_when_blocked(self):
        gov = _fully_blocked()
        assert gov.is_action_allowed(AllowedAction.API_KEY_READINESS_CHECK) is True

    def test_report_only_allowed_when_blocked(self):
        gov = _fully_blocked()
        assert gov.is_action_allowed(AllowedAction.REPORT_ONLY) is True


# ---------------------------------------------------------------------------
# TestProductionProposalForbidden
# ---------------------------------------------------------------------------

class TestProductionProposalForbidden:
    def test_production_proposal_forbidden_when_ceo_pending(self):
        gov = BlockedStateGovernance(
            ceo_decision_pending=True,
            api_key_missing=False,
            post_game_proxy_only=False,
            no_closing_line=False,
            forward_accumulation_insufficient=False,
            clv_not_ready=False,
            promotion_frozen=False,
        )
        assert gov.is_action_forbidden(ForbiddenAction.PRODUCTION_PROPOSAL) is True

    def test_production_proposal_not_forbidden_when_clear(self):
        gov = _fully_clear()
        assert gov.is_action_forbidden(ForbiddenAction.PRODUCTION_PROPOSAL) is False

    def test_production_proposal_raises_when_asserted(self):
        gov = _fully_blocked()
        with pytest.raises(GovernanceViolationError):
            gov.assert_action_not_forbidden(ForbiddenAction.PRODUCTION_PROPOSAL)


# ---------------------------------------------------------------------------
# TestHistoricalAPICallForbidden
# ---------------------------------------------------------------------------

class TestHistoricalAPICallForbidden:
    def test_historical_api_call_forbidden_without_approval(self):
        gov = BlockedStateGovernance(
            ceo_decision_pending=True,
            api_key_missing=True,
            post_game_proxy_only=False,
            no_closing_line=False,
            forward_accumulation_insufficient=False,
            clv_not_ready=False,
            promotion_frozen=False,
        )
        assert gov.is_action_forbidden(ForbiddenAction.HISTORICAL_API_CALL_WITHOUT_APPROVAL) is True

    def test_historical_api_call_not_forbidden_when_clear(self):
        gov = _fully_clear()
        assert gov.is_action_forbidden(ForbiddenAction.HISTORICAL_API_CALL_WITHOUT_APPROVAL) is False

    def test_historical_api_raises_when_asserted(self):
        gov = _fully_blocked()
        with pytest.raises(GovernanceViolationError):
            gov.assert_action_not_forbidden(ForbiddenAction.HISTORICAL_API_CALL_WITHOUT_APPROVAL)


# ---------------------------------------------------------------------------
# TestPromotionFrozenWhenCLVNotReady
# ---------------------------------------------------------------------------

class TestPromotionFrozenWhenCLVNotReady:
    def test_promotion_frozen_reason_active(self):
        gov = BlockedStateGovernance(
            ceo_decision_pending=False,
            api_key_missing=False,
            post_game_proxy_only=False,
            no_closing_line=False,
            forward_accumulation_insufficient=False,
            clv_not_ready=True,
            promotion_frozen=True,
        )
        assert BlockedReason.PROMOTION_FROZEN in gov.blocked_reasons
        assert BlockedReason.CLV_NOT_READY in gov.blocked_reasons

    def test_promotion_frozen_blocks_optimizer(self):
        gov = BlockedStateGovernance(
            ceo_decision_pending=False,
            api_key_missing=False,
            post_game_proxy_only=False,
            no_closing_line=False,
            forward_accumulation_insufficient=False,
            clv_not_ready=True,
            promotion_frozen=True,
        )
        assert gov.is_action_forbidden(ForbiddenAction.OPTIMIZER_PROMOTION) is True

    def test_promotion_frozen_blocks_profitability_claim(self):
        gov = BlockedStateGovernance(
            ceo_decision_pending=False,
            api_key_missing=False,
            post_game_proxy_only=False,
            no_closing_line=False,
            forward_accumulation_insufficient=False,
            clv_not_ready=False,
            promotion_frozen=True,
        )
        assert gov.is_action_forbidden(ForbiddenAction.PROFITABILITY_CLAIM) is True


# ---------------------------------------------------------------------------
# TestOutputPaperOnly
# ---------------------------------------------------------------------------

class TestOutputPaperOnly:
    def test_to_dict_paper_only_true(self):
        gov = _fully_blocked()
        d = gov.to_dict()
        assert d["paper_only"] is True

    def test_to_dict_network_call_false(self):
        gov = _fully_blocked()
        d = gov.to_dict()
        assert d["network_call"] is False

    def test_to_dict_crawler_modified_false(self):
        gov = _fully_blocked()
        d = gov.to_dict()
        assert d["crawler_modified"] is False

    def test_paper_only_false_raises(self):
        with pytest.raises(PaperOnlyViolationError):
            BlockedStateGovernance(
                ceo_decision_pending=True,
                api_key_missing=False,
                post_game_proxy_only=False,
                no_closing_line=False,
                forward_accumulation_insufficient=False,
                clv_not_ready=False,
                promotion_frozen=False,
                paper_only=False,
            )

    def test_p12_artifact_paper_only(self):
        """If the P12 governance JSON artifact exists, verify paper_only=true."""
        p = Path(__file__).parent.parent / "data/paper_recommendations/p12_blocked_state_governance_20260528.json"
        if not p.exists():
            pytest.skip("artifact not yet generated")
        data = json.loads(p.read_text())
        assert data.get("paper_only") is True
