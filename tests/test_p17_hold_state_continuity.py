"""P17 — Hold-State Continuity Check tests.

All tests are paper_only, no network calls, no crawler modification.
Tests verify governance contract, CEO response watch v2, forward coverage v4,
hold-state continuity, and CTO hold recommendation v2 for P17.
"""
from __future__ import annotations

import json
import pathlib

import pytest

BASE = pathlib.Path(__file__).parent.parent


def _load(rel: str) -> dict:
    return json.loads((BASE / rel).read_text())


# ---------------------------------------------------------------------------
# P17-A: Governance p17_allowed() method
# ---------------------------------------------------------------------------

class TestP17AGovernanceP17Allowed:
    """Verify BlockedStateGovernance.p17_allowed() exists and behaves correctly."""

    def test_p17_allowed_method_exists(self) -> None:
        from wbc_backend.recommendation.blocked_state_governance import BlockedStateGovernance
        g = BlockedStateGovernance(
            ceo_decision_pending=True,
            api_key_missing=True,
            post_game_proxy_only=True,
            no_closing_line=True,
            forward_accumulation_insufficient=True,
            clv_not_ready=True,
            promotion_frozen=True,
        )
        assert hasattr(g, "p17_allowed")
        assert callable(g.p17_allowed)

    def test_p17_allowed_false_when_blocked(self) -> None:
        from wbc_backend.recommendation.blocked_state_governance import BlockedStateGovernance
        g = BlockedStateGovernance(
            ceo_decision_pending=True,
            api_key_missing=False,
            post_game_proxy_only=False,
            no_closing_line=True,
            forward_accumulation_insufficient=True,
            clv_not_ready=True,
            promotion_frozen=True,
        )
        assert g.p17_allowed() is False

    def test_p17_allowed_true_when_clear(self) -> None:
        from wbc_backend.recommendation.blocked_state_governance import BlockedStateGovernance
        g = BlockedStateGovernance(
            ceo_decision_pending=False,
            api_key_missing=False,
            post_game_proxy_only=False,
            no_closing_line=False,
            forward_accumulation_insufficient=False,
            clv_not_ready=False,
            promotion_frozen=False,
        )
        assert g.p17_allowed() is True

    def test_p17_allowed_in_to_dict(self) -> None:
        from wbc_backend.recommendation.blocked_state_governance import BlockedStateGovernance
        g = BlockedStateGovernance(
            ceo_decision_pending=True,
            api_key_missing=True,
            post_game_proxy_only=True,
            no_closing_line=True,
            forward_accumulation_insufficient=True,
            clv_not_ready=True,
            promotion_frozen=True,
        )
        d = g.to_dict()
        assert "p17_allowed" in d

    def test_p17_allowed_false_in_to_dict_when_blocked(self) -> None:
        from wbc_backend.recommendation.blocked_state_governance import BlockedStateGovernance
        g = BlockedStateGovernance(
            ceo_decision_pending=True,
            api_key_missing=True,
            post_game_proxy_only=True,
            no_closing_line=True,
            forward_accumulation_insufficient=True,
            clv_not_ready=True,
            promotion_frozen=True,
        )
        d = g.to_dict()
        assert d["p17_allowed"] is False

    def test_p17_consistent_with_p16(self) -> None:
        from wbc_backend.recommendation.blocked_state_governance import BlockedStateGovernance
        g = BlockedStateGovernance(
            ceo_decision_pending=True,
            api_key_missing=True,
            post_game_proxy_only=True,
            no_closing_line=True,
            forward_accumulation_insufficient=True,
            clv_not_ready=True,
            promotion_frozen=True,
        )
        assert g.p16_allowed() == g.p17_allowed()

    def test_p17_ceo_pending_alone_blocks(self) -> None:
        from wbc_backend.recommendation.blocked_state_governance import BlockedStateGovernance
        g = BlockedStateGovernance(
            ceo_decision_pending=True,
            api_key_missing=False,
            post_game_proxy_only=False,
            no_closing_line=False,
            forward_accumulation_insufficient=False,
            clv_not_ready=False,
            promotion_frozen=False,
        )
        assert g.p17_allowed() is False

    def test_p17_paper_only_enforced(self) -> None:
        from wbc_backend.recommendation.blocked_state_governance import (
            BlockedStateGovernance,
            PaperOnlyViolationError,
        )
        with pytest.raises(PaperOnlyViolationError):
            BlockedStateGovernance(
                ceo_decision_pending=True,
                api_key_missing=True,
                post_game_proxy_only=True,
                no_closing_line=True,
                forward_accumulation_insufficient=True,
                clv_not_ready=True,
                promotion_frozen=True,
                paper_only=False,
            )


# ---------------------------------------------------------------------------
# P17-B: CEO Response Watch v2
# ---------------------------------------------------------------------------

class TestP17BCEOResponseWatch:
    """Verify p17_ceo_response_watch_20260602.json schema and decision logic."""

    @pytest.fixture(scope="class")
    def artifact(self) -> dict:
        return _load("data/paper_recommendations/p17_ceo_response_watch_20260602.json")

    def test_artifact_exists(self, artifact: dict) -> None:
        assert artifact is not None

    def test_paper_only(self, artifact: dict) -> None:
        assert artifact["paper_only"] is True

    def test_network_call_false(self, artifact: dict) -> None:
        assert artifact["network_call"] is False

    def test_decision_status_defer(self, artifact: dict) -> None:
        assert artifact["decision_status"] == "DEFER_DECISION"

    def test_p18_allowed_false(self, artifact: dict) -> None:
        assert artifact["p18_allowed"] is False

    def test_next_owner_ceo(self, artifact: dict) -> None:
        assert artifact["next_owner"] == "CEO"

    def test_final_branch_hold(self, artifact: dict) -> None:
        assert artifact["final_branch"] == "HOLD"

    def test_four_supported_decisions(self, artifact: dict) -> None:
        assert len(artifact["supported_decisions"]) == 4

    def test_approve_path_a_impact(self, artifact: dict) -> None:
        impact = artifact["decision_impacts"]["APPROVE_PATH_A_WITH_API_KEY"]
        assert impact["p18_allowed"] is True
        assert impact["status"] == "READY_FOR_API_KEY_GATE_ONLY"

    def test_defer_impact_hold(self, artifact: dict) -> None:
        impact = artifact["decision_impacts"]["DEFER_DECISION"]
        assert impact["p18_allowed"] is False
        assert impact["status"] == "HOLD"

    def test_key_pending_blocked(self, artifact: dict) -> None:
        impact = artifact["decision_impacts"]["APPROVE_PATH_A_BUT_KEY_PENDING"]
        assert impact["p18_allowed"] is False

    def test_reject_forward_only(self, artifact: dict) -> None:
        impact = artifact["decision_impacts"]["REJECT_PATH_A_USE_FORWARD_ONLY"]
        assert impact["p18_allowed"] is False
        assert impact["status"] == "FORWARD_ONLY_MONITOR_CONTINUES"


# ---------------------------------------------------------------------------
# P17-C: Forward Coverage Read-only v4
# ---------------------------------------------------------------------------

class TestP17CForwardCoverage:
    """Verify p17_forward_coverage_readonly_check_20260602.json."""

    @pytest.fixture(scope="class")
    def artifact(self) -> dict:
        return _load("data/paper_recommendations/p17_forward_coverage_readonly_check_20260602.json")

    def test_artifact_exists(self, artifact: dict) -> None:
        assert artifact is not None

    def test_paper_only(self, artifact: dict) -> None:
        assert artifact["paper_only"] is True

    def test_network_call_false(self, artifact: dict) -> None:
        assert artifact["network_call"] is False

    def test_pair_count_zero(self, artifact: dict) -> None:
        assert artifact["pair_count"] == 0

    def test_pair_target_200(self, artifact: dict) -> None:
        assert artifact["pair_target"] == 200

    def test_status_accumulation_insufficient(self, artifact: dict) -> None:
        assert artifact["status"] == "ACCUMULATION_INSUFFICIENT"

    def test_p18_clv_allowed_false(self, artifact: dict) -> None:
        assert artifact["p18_clv_allowed"] is False

    def test_tsl_history_false(self, artifact: dict) -> None:
        assert artifact["tsl_odds_history_exists"] is False

    def test_delta_vs_p16_zero(self, artifact: dict) -> None:
        assert artifact["delta_vs_p16"] == 0


# ---------------------------------------------------------------------------
# P17-D: Hold-State Continuity Verification
# ---------------------------------------------------------------------------

class TestP17DHoldStateContinuity:
    """Verify p17_hold_state_continuity_20260602.json and governance enforcement."""

    @pytest.fixture(scope="class")
    def artifact(self) -> dict:
        return _load("data/paper_recommendations/p17_hold_state_continuity_20260602.json")

    def test_artifact_exists(self, artifact: dict) -> None:
        assert artifact is not None

    def test_paper_only(self, artifact: dict) -> None:
        assert artifact["paper_only"] is True

    def test_network_call_false(self, artifact: dict) -> None:
        assert artifact["network_call"] is False

    def test_enforcement_pass(self, artifact: dict) -> None:
        assert artifact["enforcement"] == "PASS"

    def test_forbidden_count_8(self, artifact: dict) -> None:
        assert artifact["forbidden_count"] == 8

    def test_all_forbidden_blocked(self, artifact: dict) -> None:
        for action, blocked in artifact["forbidden_actions_blocked"].items():
            assert blocked is True, f"{action} should be blocked"

    def test_all_allowed_permitted(self, artifact: dict) -> None:
        for action, permitted in artifact["allowed_actions_permitted"].items():
            assert permitted is True, f"{action} should be permitted"

    def test_p16_allowed_false(self, artifact: dict) -> None:
        assert artifact["p16_allowed"] is False

    def test_p17_allowed_false(self, artifact: dict) -> None:
        assert artifact["p17_allowed"] is False

    def test_p18_allowed_false(self, artifact: dict) -> None:
        assert artifact["p18_allowed"] is False

    def test_regression_vs_p16_no_change(self, artifact: dict) -> None:
        assert artifact["regression_vs_p16"] == "NO_CHANGE"

    def test_champion_preserved(self, artifact: dict) -> None:
        assert artifact["champion"] == "fixed_edge_5pct"
        assert artifact["champion_status"] == "PRESERVED"

    def test_promotion_frozen(self, artifact: dict) -> None:
        assert artifact["promotion_status"] == "FROZEN"

    def test_no_network_imports_in_governance(self) -> None:
        gov_path = BASE / "wbc_backend" / "recommendation" / "blocked_state_governance.py"
        source = gov_path.read_text()
        for bad in ("import requests", "import httpx", "import urllib.request", "import aiohttp"):
            assert bad not in source, f"Network import found: {bad}"

    # Governance runtime checks
    def test_ceo_pending_keeps_p18_blocked(self) -> None:
        from wbc_backend.recommendation.blocked_state_governance import BlockedStateGovernance
        g = BlockedStateGovernance(
            ceo_decision_pending=True,
            api_key_missing=False,
            post_game_proxy_only=False,
            no_closing_line=False,
            forward_accumulation_insufficient=False,
            clv_not_ready=False,
            promotion_frozen=False,
        )
        assert g.p17_allowed() is False

    def test_forward_insufficient_keeps_clv_blocked(self) -> None:
        from wbc_backend.recommendation.blocked_state_governance import (
            BlockedStateGovernance,
            ForbiddenAction,
        )
        g = BlockedStateGovernance(
            ceo_decision_pending=False,
            api_key_missing=False,
            post_game_proxy_only=False,
            no_closing_line=True,
            forward_accumulation_insufficient=True,
            clv_not_ready=True,
            promotion_frozen=False,
        )
        assert g.is_action_forbidden(ForbiddenAction.OPTIMIZER_PROMOTION) is True

    def test_api_key_missing_blocks_path_a(self) -> None:
        from wbc_backend.recommendation.blocked_state_governance import (
            BlockedStateGovernance,
            BlockedReason,
        )
        g = BlockedStateGovernance(
            ceo_decision_pending=False,
            api_key_missing=True,
            post_game_proxy_only=False,
            no_closing_line=False,
            forward_accumulation_insufficient=False,
            clv_not_ready=False,
            promotion_frozen=False,
        )
        assert BlockedReason.API_KEY_MISSING in g.blocked_reasons

    def test_report_only_remains_allowed(self) -> None:
        from wbc_backend.recommendation.blocked_state_governance import (
            BlockedStateGovernance,
            AllowedAction,
        )
        g = BlockedStateGovernance(
            ceo_decision_pending=True,
            api_key_missing=True,
            post_game_proxy_only=True,
            no_closing_line=True,
            forward_accumulation_insufficient=True,
            clv_not_ready=True,
            promotion_frozen=True,
        )
        assert g.is_action_allowed(AllowedAction.REPORT_ONLY) is True

    def test_p16_p17_behavior_consistent(self) -> None:
        from wbc_backend.recommendation.blocked_state_governance import BlockedStateGovernance
        g = BlockedStateGovernance(
            ceo_decision_pending=True,
            api_key_missing=True,
            post_game_proxy_only=True,
            no_closing_line=True,
            forward_accumulation_insufficient=True,
            clv_not_ready=True,
            promotion_frozen=True,
        )
        assert g.p16_allowed() == g.p17_allowed()

    def test_paper_only_true_enforced(self) -> None:
        from wbc_backend.recommendation.blocked_state_governance import (
            BlockedStateGovernance,
            PaperOnlyViolationError,
        )
        with pytest.raises(PaperOnlyViolationError):
            BlockedStateGovernance(
                ceo_decision_pending=True,
                api_key_missing=True,
                post_game_proxy_only=True,
                no_closing_line=True,
                forward_accumulation_insufficient=True,
                clv_not_ready=True,
                promotion_frozen=True,
                paper_only=False,
            )


# ---------------------------------------------------------------------------
# P17-E: CTO Hold Recommendation v2
# ---------------------------------------------------------------------------

class TestP17ECTOHoldRecommendation:
    """Verify p17_cto_hold_recommendation_20260602.json."""

    @pytest.fixture(scope="class")
    def artifact(self) -> dict:
        return _load("data/paper_recommendations/p17_cto_hold_recommendation_20260602.json")

    def test_artifact_exists(self, artifact: dict) -> None:
        assert artifact is not None

    def test_paper_only(self, artifact: dict) -> None:
        assert artifact["paper_only"] is True

    def test_network_call_false(self, artifact: dict) -> None:
        assert artifact["network_call"] is False

    def test_recommendation_hold(self, artifact: dict) -> None:
        assert artifact["recommendation"] == "HOLD_ENGINEERING_EXPANSION"

    def test_p18_allowed_false(self, artifact: dict) -> None:
        assert artifact["p18_allowed"] is False

    def test_next_owner_ceo(self, artifact: dict) -> None:
        assert artifact["next_owner"] == "CEO"

    def test_worker_next_action_daily_monitor(self, artifact: dict) -> None:
        assert artifact["worker_next_action"] == "DAILY_MONITOR_ONLY"

    def test_engineering_expansion_not_allowed(self, artifact: dict) -> None:
        assert artifact["engineering_expansion_allowed"] is False

    def test_champion_preserved(self, artifact: dict) -> None:
        assert artifact["champion"] == "fixed_edge_5pct"

    def test_promotion_frozen(self, artifact: dict) -> None:
        assert artifact["promotion_freeze"] is True

    def test_classification(self, artifact: dict) -> None:
        assert artifact["classification"] == "P17_HOLD_ENGINEERING_EXPANSION_NO_DECISION"

    def test_profitability_claim_false(self, artifact: dict) -> None:
        assert artifact["profitability_claim"] is False

    def test_path_a_status(self, artifact: dict) -> None:
        assert artifact["path_a_status"] == "BLOCKED_NEEDS_CEO_APPROVAL_AND_API_KEY"

    def test_path_b_status(self, artifact: dict) -> None:
        assert artifact["path_b_status"] == "ACCUMULATION_INSUFFICIENT"

    def test_clv_status(self, artifact: dict) -> None:
        assert artifact["clv_status"] == "BLOCKED_NO_CLOSING_LINE"
