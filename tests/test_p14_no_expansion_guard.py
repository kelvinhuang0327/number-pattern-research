"""Tests for P14 No-Expansion Guard."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from wbc_backend.recommendation.blocked_state_governance import (
    AllowedAction,
    BlockedStateGovernance,
    ForbiddenAction,
    GovernanceViolationError,
    PaperOnlyViolationError,
)
from scripts.run_no_expansion_guard_p14 import run_no_expansion_guard

BASE = Path(__file__).parent.parent

# ---------------------------------------------------------------------------
# Artifact paths
# ---------------------------------------------------------------------------

P14B_ARTIFACT = BASE / "data/paper_recommendations/p14_ceo_decision_watch_20260530.json"
P14C_ARTIFACT = BASE / "data/paper_recommendations/p14_forward_coverage_readonly_check_20260530.json"
P14D_ARTIFACT = BASE / "data/paper_recommendations/p14_no_expansion_guard_20260530.json"
P14E_ARTIFACT = BASE / "data/paper_recommendations/p14_cto_minimal_action_recommendation_20260530.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _fully_blocked() -> BlockedStateGovernance:
    return BlockedStateGovernance(
        ceo_decision_pending=True,
        api_key_missing=True,
        post_game_proxy_only=False,
        no_closing_line=True,
        forward_accumulation_insufficient=True,
        clv_not_ready=True,
        promotion_frozen=True,
        paper_only=True,
    )


# ---------------------------------------------------------------------------
# TestP14BCEODecisionWatch
# ---------------------------------------------------------------------------

class TestP14BCEODecisionWatch:
    @pytest.fixture(autouse=True)
    def load_artifact(self):
        assert P14B_ARTIFACT.exists(), f"Missing: {P14B_ARTIFACT}"
        self.data = _load(P14B_ARTIFACT)

    def test_artifact_exists(self):
        assert P14B_ARTIFACT.exists()

    def test_paper_only(self):
        assert self.data["paper_only"] is True

    def test_network_call_false(self):
        assert self.data["network_call"] is False

    def test_ceo_decision_is_defer(self):
        assert self.data["ceo_decision"] == "DEFER_DECISION"

    def test_path_a_blocked(self):
        assert self.data["path_a_status"] == "BLOCKED_NEEDS_CEO_APPROVAL_AND_API_KEY"

    def test_path_b_insufficient(self):
        assert self.data["path_b_status"] == "ACCUMULATION_INSUFFICIENT"

    def test_p15_not_allowed(self):
        assert self.data["p15_allowed"] is False

    def test_next_owner_is_ceo(self):
        assert self.data["next_owner"] == "CEO"

    def test_supported_decisions_contains_four_options(self):
        decisions = self.data["supported_decisions"]
        assert "APPROVE_PATH_A_WITH_API_KEY" in decisions
        assert "APPROVE_PATH_A_BUT_KEY_PENDING" in decisions
        assert "REJECT_PATH_A_USE_FORWARD_ONLY" in decisions
        assert "DEFER_DECISION" in decisions


# ---------------------------------------------------------------------------
# TestP14CForwardCoverageCheck
# ---------------------------------------------------------------------------

class TestP14CForwardCoverageCheck:
    @pytest.fixture(autouse=True)
    def load_artifact(self):
        assert P14C_ARTIFACT.exists(), f"Missing: {P14C_ARTIFACT}"
        self.data = _load(P14C_ARTIFACT)

    def test_artifact_exists(self):
        assert P14C_ARTIFACT.exists()

    def test_paper_only(self):
        assert self.data["paper_only"] is True

    def test_network_call_false(self):
        assert self.data["network_call"] is False

    def test_pair_count_is_zero(self):
        assert self.data["pregame_closing_pair_count"] == 0

    def test_pair_target_is_200(self):
        assert self.data["pair_target"] == 200

    def test_status_insufficient(self):
        assert self.data["status"] == "ACCUMULATION_INSUFFICIENT"

    def test_p15_clv_not_allowed(self):
        assert self.data["p15_clv_allowed"] is False

    def test_tsl_history_not_exists(self):
        assert self.data["tsl_odds_history_exists"] is False


# ---------------------------------------------------------------------------
# TestP14DNoExpansionGuardArtifact
# ---------------------------------------------------------------------------

class TestP14DNoExpansionGuardArtifact:
    @pytest.fixture(autouse=True)
    def load_artifact(self):
        assert P14D_ARTIFACT.exists(), f"Missing: {P14D_ARTIFACT}"
        self.data = _load(P14D_ARTIFACT)

    def test_artifact_exists(self):
        assert P14D_ARTIFACT.exists()

    def test_paper_only(self):
        assert self.data["paper_only"] is True

    def test_network_call_false(self):
        assert self.data["network_call"] is False

    def test_enforcement_pass(self):
        assert self.data["enforcement_result"] == "PASS"

    def test_all_forbidden_blocked(self):
        assert self.data["all_forbidden_actions_blocked"] is True

    def test_all_allowed_permitted(self):
        assert self.data["all_allowed_actions_permitted"] is True

    def test_p14_not_allowed_in_artifact(self):
        assert self.data["p14_allowed"] is False

    def test_p15_not_allowed(self):
        assert self.data["p15_allowed"] is False

    def test_new_roadmap_expansion_blocked(self):
        assert self.data["forbidden_actions_check"]["NEW_ROADMAP_EXPANSION"] is True

    def test_new_backfill_without_decision_blocked(self):
        assert self.data["forbidden_actions_check"]["NEW_BACKFILL_WITHOUT_DECISION"] is True


# ---------------------------------------------------------------------------
# TestP14DNoExpansionGuardLogic
# ---------------------------------------------------------------------------

class TestP14DNoExpansionGuardLogic:
    def test_paper_only_false_raises(self, tmp_path):
        with pytest.raises(PaperOnlyViolationError):
            run_no_expansion_guard(
                output_path=tmp_path / "out.json",
                paper_only=False,
            )

    def test_ceo_pending_blocks_new_roadmap_expansion(self):
        gov = _fully_blocked()
        assert gov.is_action_forbidden(ForbiddenAction.NEW_ROADMAP_EXPANSION) is True

    def test_ceo_pending_blocks_optimizer_promotion(self):
        gov = _fully_blocked()
        assert gov.is_action_forbidden(ForbiddenAction.OPTIMIZER_PROMOTION) is True

    def test_no_api_key_blocks_historical_api_call(self):
        gov = BlockedStateGovernance(
            ceo_decision_pending=False,
            api_key_missing=True,
            post_game_proxy_only=False,
            no_closing_line=False,
            forward_accumulation_insufficient=False,
            clv_not_ready=False,
            promotion_frozen=False,
            paper_only=True,
        )
        assert gov.is_action_forbidden(ForbiddenAction.HISTORICAL_API_CALL_WITHOUT_APPROVAL) is True

    def test_no_clv_blocks_promotion(self):
        gov = BlockedStateGovernance(
            ceo_decision_pending=False,
            api_key_missing=False,
            post_game_proxy_only=False,
            no_closing_line=False,
            forward_accumulation_insufficient=False,
            clv_not_ready=True,
            promotion_frozen=True,
            paper_only=True,
        )
        assert gov.is_action_forbidden(ForbiddenAction.OPTIMIZER_PROMOTION) is True

    def test_report_only_remains_allowed(self):
        gov = _fully_blocked()
        assert gov.is_action_allowed(AllowedAction.REPORT_ONLY) is True

    def test_paper_only_enforced_in_output(self, tmp_path):
        result = run_no_expansion_guard(output_path=tmp_path / "out.json")
        assert result["paper_only"] is True

    def test_new_roadmap_expansion_is_forbidden_action(self):
        assert hasattr(ForbiddenAction, "NEW_ROADMAP_EXPANSION")
        assert ForbiddenAction.NEW_ROADMAP_EXPANSION.value == "NEW_ROADMAP_EXPANSION"

    def test_new_backfill_without_decision_is_forbidden_action(self):
        assert hasattr(ForbiddenAction, "NEW_BACKFILL_WITHOUT_DECISION")
        assert ForbiddenAction.NEW_BACKFILL_WITHOUT_DECISION.value == "NEW_BACKFILL_WITHOUT_DECISION"

    def test_p14_allowed_false_when_blocked(self, tmp_path):
        result = run_no_expansion_guard(output_path=tmp_path / "out.json")
        assert result["p14_allowed"] is False

    def test_p14_allowed_method_false_when_blocked(self):
        gov = _fully_blocked()
        assert gov.p14_allowed() is False

    def test_p14_allowed_method_true_when_clear(self):
        gov = BlockedStateGovernance(
            ceo_decision_pending=False,
            api_key_missing=False,
            post_game_proxy_only=False,
            no_closing_line=False,
            forward_accumulation_insufficient=False,
            clv_not_ready=False,
            promotion_frozen=False,
            paper_only=True,
        )
        assert gov.p14_allowed() is True

    def test_all_forbidden_actions_blocked(self, tmp_path):
        result = run_no_expansion_guard(output_path=tmp_path / "out.json")
        for action_val, blocked in result["forbidden_actions_check"].items():
            assert blocked is True, f"Expected {action_val} to be forbidden"

    def test_all_allowed_actions_permitted(self, tmp_path):
        result = run_no_expansion_guard(output_path=tmp_path / "out.json")
        for action_val, permitted in result["allowed_actions_check"].items():
            assert permitted is True, f"Expected {action_val} to be allowed"

    def test_champion_preserved(self, tmp_path):
        result = run_no_expansion_guard(output_path=tmp_path / "out.json")
        assert result["fixed_edge_5pct_champion_preserved"] is True

    def test_no_network_import_in_script(self):
        script = (BASE / "scripts/run_no_expansion_guard_p14.py").read_text(encoding="utf-8")
        assert "import requests" not in script
        assert "import urllib" not in script
        assert "import socket" not in script
        assert "import tsl_crawler" not in script


# ---------------------------------------------------------------------------
# TestP14ECTORecommendation
# ---------------------------------------------------------------------------

class TestP14ECTORecommendation:
    @pytest.fixture(autouse=True)
    def load_artifact(self):
        assert P14E_ARTIFACT.exists(), f"Missing: {P14E_ARTIFACT}"
        self.data = _load(P14E_ARTIFACT)

    def test_artifact_exists(self):
        assert P14E_ARTIFACT.exists()

    def test_paper_only(self):
        assert self.data["paper_only"] is True

    def test_recommendation_daily_monitor_only(self):
        assert self.data["recommendation"] == "DAILY_MONITOR_ONLY"

    def test_engineering_expansion_not_allowed(self):
        assert self.data["engineering_expansion_allowed"] is False

    def test_p15_not_allowed(self):
        assert self.data["p15_allowed"] is False

    def test_next_owner_is_ceo(self):
        assert self.data["next_owner"] == "CEO"

    def test_champion_preserved(self):
        assert self.data["fixed_edge_5pct_champion_preserved"] is True

    def test_promotion_frozen(self):
        assert self.data["promotion_frozen"] is True

    def test_no_profitability_claim(self):
        text = json.dumps(self.data).lower()
        assert "profitable" not in text
