"""P15-D — No-Expansion Watch Tests.

Validates:
- P14 no-expansion guard regression (8 forbidden actions still blocked)
- P15 governance module extension (p15_allowed)
- CEO escalation packet artifact
- Forward coverage read-only check v2 artifact
- CTO minimal action recommendation v2 artifact
- All paper_only=true, no network calls, no crawler modification
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from wbc_backend.recommendation.blocked_state_governance import (
    AllowedAction,
    BlockedStateGovernance,
    ForbiddenAction,
    GovernanceViolationError,
    PaperOnlyViolationError,
)

BASE = Path(__file__).parent.parent
DATA = BASE / "data" / "paper_recommendations"


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _fully_blocked() -> BlockedStateGovernance:
    return BlockedStateGovernance(
        ceo_decision_pending=True,
        api_key_missing=True,
        post_game_proxy_only=False,
        no_closing_line=True,
        forward_accumulation_insufficient=True,
        clv_not_ready=True,
        promotion_frozen=True,
    )


def _load(filename: str) -> dict:
    return json.loads((DATA / filename).read_text())


# ===========================================================================
# TestP15AGovernanceP15Allowed — p15_allowed() method
# ===========================================================================

class TestP15AGovernanceP15Allowed:
    """Governance module now exposes p15_allowed()."""

    def test_p15_allowed_method_exists(self) -> None:
        gov = _fully_blocked()
        assert hasattr(gov, "p15_allowed")

    def test_p15_allowed_false_when_blocked(self) -> None:
        gov = _fully_blocked()
        assert gov.p15_allowed() is False

    def test_p15_allowed_true_when_clear(self) -> None:
        gov = BlockedStateGovernance(
            ceo_decision_pending=False,
            api_key_missing=False,
            post_game_proxy_only=False,
            no_closing_line=False,
            forward_accumulation_insufficient=False,
            clv_not_ready=False,
            promotion_frozen=False,
        )
        assert gov.p15_allowed() is True

    def test_p15_allowed_in_to_dict(self) -> None:
        gov = _fully_blocked()
        d = gov.to_dict()
        assert "p15_allowed" in d

    def test_to_dict_p15_allowed_false_when_blocked(self) -> None:
        gov = _fully_blocked()
        assert gov.to_dict()["p15_allowed"] is False

    def test_to_dict_p15_allowed_true_when_clear(self) -> None:
        gov = BlockedStateGovernance(
            ceo_decision_pending=False,
            api_key_missing=False,
            post_game_proxy_only=False,
            no_closing_line=False,
            forward_accumulation_insufficient=False,
            clv_not_ready=False,
            promotion_frozen=False,
        )
        assert gov.to_dict()["p15_allowed"] is True

    def test_p13_p14_p15_consistent_when_blocked(self) -> None:
        gov = _fully_blocked()
        assert gov.p13_allowed() is False
        assert gov.p14_allowed() is False
        assert gov.p15_allowed() is False

    def test_p13_p14_p15_consistent_when_clear(self) -> None:
        gov = BlockedStateGovernance(
            ceo_decision_pending=False,
            api_key_missing=False,
            post_game_proxy_only=False,
            no_closing_line=False,
            forward_accumulation_insufficient=False,
            clv_not_ready=False,
            promotion_frozen=False,
        )
        assert gov.p13_allowed() is True
        assert gov.p14_allowed() is True
        assert gov.p15_allowed() is True


# ===========================================================================
# TestP15BNoExpansionRegressionLogic — guard logic
# ===========================================================================

class TestP15BNoExpansionRegressionLogic:
    """No-expansion guard: 8/8 forbidden still blocked, 5/5 allowed still permitted."""

    def test_forbidden_count_is_8(self) -> None:
        assert len(ForbiddenAction) == 8

    def test_new_roadmap_expansion_in_enum(self) -> None:
        assert ForbiddenAction.NEW_ROADMAP_EXPANSION in ForbiddenAction

    def test_new_backfill_without_decision_in_enum(self) -> None:
        assert ForbiddenAction.NEW_BACKFILL_WITHOUT_DECISION in ForbiddenAction

    def test_all_forbidden_blocked_in_blocked_state(self) -> None:
        gov = _fully_blocked()
        for action in ForbiddenAction:
            assert gov.is_action_forbidden(action), f"{action} should be forbidden"

    def test_all_allowed_permitted_in_blocked_state(self) -> None:
        gov = _fully_blocked()
        for action in AllowedAction:
            assert gov.is_action_allowed(action), f"{action} should be allowed"

    def test_allowed_count_is_5(self) -> None:
        assert len(AllowedAction) == 5

    def test_report_only_always_allowed(self) -> None:
        gov = _fully_blocked()
        assert gov.is_action_allowed(AllowedAction.REPORT_ONLY) is True

    def test_paper_only_monitoring_always_allowed(self) -> None:
        gov = _fully_blocked()
        assert gov.is_action_allowed(AllowedAction.PAPER_ONLY_MONITORING) is True

    def test_ceo_pending_blocks_new_roadmap_expansion(self) -> None:
        gov = BlockedStateGovernance(
            ceo_decision_pending=True,
            api_key_missing=False,
            post_game_proxy_only=False,
            no_closing_line=False,
            forward_accumulation_insufficient=False,
            clv_not_ready=False,
            promotion_frozen=False,
        )
        assert gov.is_action_forbidden(ForbiddenAction.NEW_ROADMAP_EXPANSION) is True

    def test_ceo_pending_blocks_new_backfill(self) -> None:
        gov = BlockedStateGovernance(
            ceo_decision_pending=True,
            api_key_missing=False,
            post_game_proxy_only=False,
            no_closing_line=False,
            forward_accumulation_insufficient=False,
            clv_not_ready=False,
            promotion_frozen=False,
        )
        assert gov.is_action_forbidden(ForbiddenAction.NEW_BACKFILL_WITHOUT_DECISION) is True

    def test_ceo_pending_blocks_optimizer_promotion(self) -> None:
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

    def test_no_api_key_blocks_historical_call(self) -> None:
        gov = BlockedStateGovernance(
            ceo_decision_pending=False,
            api_key_missing=True,
            post_game_proxy_only=False,
            no_closing_line=False,
            forward_accumulation_insufficient=False,
            clv_not_ready=False,
            promotion_frozen=False,
        )
        assert gov.is_action_forbidden(ForbiddenAction.HISTORICAL_API_CALL_WITHOUT_APPROVAL) is True

    def test_paper_only_false_raises(self) -> None:
        with pytest.raises(PaperOnlyViolationError):
            BlockedStateGovernance(
                ceo_decision_pending=True,
                api_key_missing=True,
                post_game_proxy_only=False,
                no_closing_line=True,
                forward_accumulation_insufficient=True,
                clv_not_ready=True,
                promotion_frozen=True,
                paper_only=False,
            )

    def test_assert_forbidden_raises_governance_error(self) -> None:
        gov = _fully_blocked()
        with pytest.raises(GovernanceViolationError):
            gov.assert_action_not_forbidden(ForbiddenAction.NEW_ROADMAP_EXPANSION)

    def test_no_network_imports_in_governance_module(self) -> None:
        import importlib
        import importlib.util
        source_path = BASE / "wbc_backend" / "recommendation" / "blocked_state_governance.py"
        source = source_path.read_text()
        for bad in ("import requests", "import urllib", "import socket", "import httpx"):
            assert bad not in source, f"Governance module must not import {bad}"

    def test_paper_only_enforced_in_to_dict(self) -> None:
        gov = _fully_blocked()
        assert gov.to_dict()["paper_only"] is True


# ===========================================================================
# TestP15BNoExpansionRegressionArtifact — JSON artifact
# ===========================================================================

class TestP15BNoExpansionRegressionArtifact:
    """P15-D JSON artifact validation."""

    def test_artifact_exists(self) -> None:
        assert (DATA / "p15_no_expansion_guard_regression_20260531.json").exists()

    def test_paper_only_true(self) -> None:
        d = _load("p15_no_expansion_guard_regression_20260531.json")
        assert d["paper_only"] is True

    def test_network_call_false(self) -> None:
        d = _load("p15_no_expansion_guard_regression_20260531.json")
        assert d["network_call"] is False

    def test_enforcement_pass(self) -> None:
        d = _load("p15_no_expansion_guard_regression_20260531.json")
        assert d["enforcement_result"] == "PASS"

    def test_all_forbidden_blocked(self) -> None:
        d = _load("p15_no_expansion_guard_regression_20260531.json")
        assert d["all_forbidden_actions_blocked"] is True

    def test_all_allowed_permitted(self) -> None:
        d = _load("p15_no_expansion_guard_regression_20260531.json")
        assert d["all_allowed_actions_permitted"] is True

    def test_p15_allowed_false(self) -> None:
        d = _load("p15_no_expansion_guard_regression_20260531.json")
        assert d["p15_allowed"] is False

    def test_p16_allowed_false(self) -> None:
        d = _load("p15_no_expansion_guard_regression_20260531.json")
        assert d["p16_allowed"] is False

    def test_forbidden_count_8(self) -> None:
        d = _load("p15_no_expansion_guard_regression_20260531.json")
        assert d["forbidden_count"] == 8

    def test_new_roadmap_expansion_blocked(self) -> None:
        d = _load("p15_no_expansion_guard_regression_20260531.json")
        assert d["forbidden_actions_check"]["NEW_ROADMAP_EXPANSION"] is True

    def test_new_backfill_blocked(self) -> None:
        d = _load("p15_no_expansion_guard_regression_20260531.json")
        assert d["forbidden_actions_check"]["NEW_BACKFILL_WITHOUT_DECISION"] is True

    def test_champion_preserved(self) -> None:
        d = _load("p15_no_expansion_guard_regression_20260531.json")
        assert d["fixed_edge_5pct_champion_preserved"] is True

    def test_regression_vs_p14_no_change(self) -> None:
        d = _load("p15_no_expansion_guard_regression_20260531.json")
        assert d["regression_vs_p14"] == "NO_CHANGE"


# ===========================================================================
# TestP15CCEODecisionWatch — B watch artifact
# ===========================================================================

class TestP15CCEODecisionWatch:
    """P15-B CEO Decision Watch v2 artifact."""

    def test_artifact_exists(self) -> None:
        assert (DATA / "p15_ceo_decision_watch_20260531.json").exists()

    def test_paper_only_true(self) -> None:
        d = _load("p15_ceo_decision_watch_20260531.json")
        assert d["paper_only"] is True

    def test_network_call_false(self) -> None:
        d = _load("p15_ceo_decision_watch_20260531.json")
        assert d["network_call"] is False

    def test_ceo_decision_defer(self) -> None:
        d = _load("p15_ceo_decision_watch_20260531.json")
        assert d["ceo_decision"] == "DEFER_DECISION"

    def test_p16_allowed_false(self) -> None:
        d = _load("p15_ceo_decision_watch_20260531.json")
        assert d["p16_allowed"] is False

    def test_next_owner_ceo(self) -> None:
        d = _load("p15_ceo_decision_watch_20260531.json")
        assert d["next_owner"] == "CEO"

    def test_4_supported_decisions(self) -> None:
        d = _load("p15_ceo_decision_watch_20260531.json")
        assert len(d["supported_decisions"]) == 4

    def test_approve_path_a_with_key_unblocks_p16(self) -> None:
        d = _load("p15_ceo_decision_watch_20260531.json")
        assert d["decision_impacts"]["APPROVE_PATH_A_WITH_API_KEY"]["p16_allowed"] is True

    def test_defer_keeps_p16_blocked(self) -> None:
        d = _load("p15_ceo_decision_watch_20260531.json")
        assert d["decision_impacts"]["DEFER_DECISION"]["p16_allowed"] is False

    def test_path_a_blocked(self) -> None:
        d = _load("p15_ceo_decision_watch_20260531.json")
        assert d["path_a_status"] == "BLOCKED_NEEDS_CEO_APPROVAL_AND_API_KEY"

    def test_path_b_insufficient(self) -> None:
        d = _load("p15_ceo_decision_watch_20260531.json")
        assert d["path_b_status"] == "ACCUMULATION_INSUFFICIENT"


# ===========================================================================
# TestP15DForwardCoverage — C forward coverage artifact
# ===========================================================================

class TestP15DForwardCoverage:
    """P15-C Forward Coverage Read-only Check v2 artifact."""

    def test_artifact_exists(self) -> None:
        assert (DATA / "p15_forward_coverage_readonly_check_20260531.json").exists()

    def test_paper_only_true(self) -> None:
        d = _load("p15_forward_coverage_readonly_check_20260531.json")
        assert d["paper_only"] is True

    def test_network_call_false(self) -> None:
        d = _load("p15_forward_coverage_readonly_check_20260531.json")
        assert d["network_call"] is False

    def test_pair_count_zero(self) -> None:
        d = _load("p15_forward_coverage_readonly_check_20260531.json")
        assert d["pregame_closing_pair_count"] == 0

    def test_pair_target_200(self) -> None:
        d = _load("p15_forward_coverage_readonly_check_20260531.json")
        assert d["pair_target"] == 200

    def test_status_accumulation_insufficient(self) -> None:
        d = _load("p15_forward_coverage_readonly_check_20260531.json")
        assert d["status"] == "ACCUMULATION_INSUFFICIENT"

    def test_p16_clv_allowed_false(self) -> None:
        d = _load("p15_forward_coverage_readonly_check_20260531.json")
        assert d["p16_clv_allowed"] is False

    def test_tsl_history_not_exist(self) -> None:
        d = _load("p15_forward_coverage_readonly_check_20260531.json")
        assert d["tsl_odds_history_exists"] is False

    def test_delta_from_p14_zero(self) -> None:
        d = _load("p15_forward_coverage_readonly_check_20260531.json")
        assert d["delta_from_p14"] == 0


# ===========================================================================
# TestP15ECEOEscalationPacket — E escalation artifact
# ===========================================================================

class TestP15ECEOEscalationPacket:
    """P15-E CEO Escalation Packet artifact."""

    def test_artifact_exists(self) -> None:
        assert (DATA / "p15_ceo_escalation_packet_20260531.json").exists()

    def test_paper_only_true(self) -> None:
        d = _load("p15_ceo_escalation_packet_20260531.json")
        assert d["paper_only"] is True

    def test_network_call_false(self) -> None:
        d = _load("p15_ceo_escalation_packet_20260531.json")
        assert d["network_call"] is False

    def test_three_decision_options(self) -> None:
        d = _load("p15_ceo_escalation_packet_20260531.json")
        assert set(d["decision_options"].keys()) == {"A", "B", "C"}

    def test_option_a_has_required_fields(self) -> None:
        d = _load("p15_ceo_escalation_packet_20260531.json")
        opt_a = d["decision_options"]["A"]
        for field in ("impact", "unblock_condition", "next_owner", "worker_next_action"):
            assert field in opt_a, f"Option A missing field: {field}"

    def test_p16_blocked_in_current_state(self) -> None:
        d = _load("p15_ceo_escalation_packet_20260531.json")
        assert d["current_state_summary"]["p16_allowed"] is False

    def test_promotion_frozen(self) -> None:
        d = _load("p15_ceo_escalation_packet_20260531.json")
        assert d["current_state_summary"]["promotion_status"] == "FROZEN"

    def test_champion_preserved(self) -> None:
        d = _load("p15_ceo_escalation_packet_20260531.json")
        assert d["current_state_summary"]["champion"] == "fixed_edge_5pct"

    def test_no_profitability_claim(self) -> None:
        d = _load("p15_ceo_escalation_packet_20260531.json")
        text = json.dumps(d).lower()
        assert "profitable" not in text
        assert "可獲利" not in text


# ===========================================================================
# TestP15FCTORecommendation — F CTO recommendation artifact
# ===========================================================================

class TestP15FCTORecommendation:
    """P15-F CTO Minimal Action Recommendation v2 artifact."""

    def test_artifact_exists(self) -> None:
        assert (DATA / "p15_cto_minimal_action_recommendation_20260531.json").exists()

    def test_paper_only_true(self) -> None:
        d = _load("p15_cto_minimal_action_recommendation_20260531.json")
        assert d["paper_only"] is True

    def test_recommendation_daily_monitor_only(self) -> None:
        d = _load("p15_cto_minimal_action_recommendation_20260531.json")
        assert d["recommendation"] == "DAILY_MONITOR_ONLY"

    def test_engineering_expansion_not_allowed(self) -> None:
        d = _load("p15_cto_minimal_action_recommendation_20260531.json")
        assert d["engineering_expansion_allowed"] is False

    def test_p16_allowed_false(self) -> None:
        d = _load("p15_cto_minimal_action_recommendation_20260531.json")
        assert d["p16_allowed"] is False

    def test_next_owner_ceo(self) -> None:
        d = _load("p15_cto_minimal_action_recommendation_20260531.json")
        assert d["next_owner"] == "CEO"

    def test_champion_preserved(self) -> None:
        d = _load("p15_cto_minimal_action_recommendation_20260531.json")
        assert d["fixed_edge_5pct_champion_preserved"] is True

    def test_promotion_frozen(self) -> None:
        d = _load("p15_cto_minimal_action_recommendation_20260531.json")
        assert d["promotion_frozen"] is True

    def test_classification(self) -> None:
        d = _load("p15_cto_minimal_action_recommendation_20260531.json")
        assert d["classification"] == "P15_DAILY_MONITOR_ONLY_NO_EXPANSION"

    def test_no_profitability_claim(self) -> None:
        d = _load("p15_cto_minimal_action_recommendation_20260531.json")
        text = json.dumps(d).lower()
        assert "profitable" not in text
        assert "可獲利" not in text
