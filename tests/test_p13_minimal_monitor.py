"""Tests for P13 Minimal Blocked-State Monitor Only."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.run_stop_rule_enforcement_p13 import (
    DEFAULT_OUTPUT_PATH as P13D_OUTPUT_PATH,
    run_stop_rule_enforcement,
)
from wbc_backend.recommendation.blocked_state_governance import (
    AllowedAction,
    BlockedStateGovernance,
    ForbiddenAction,
    PaperOnlyViolationError,
)

BASE = Path(__file__).parent.parent
P13_RECHECK = BASE / "data/paper_recommendations/p13_minimal_blocked_state_recheck_20260529.json"
P13_CEO_REMINDER = BASE / "data/paper_recommendations/p13_ceo_reminder_packet_20260529.json"
P13_STOP_RULE = BASE / "data/paper_recommendations/p13_stop_rule_enforcement_20260529.json"


# ---------------------------------------------------------------------------
# TestP13BRecheckArtifact
# ---------------------------------------------------------------------------

class TestP13BRecheckArtifact:
    def test_recheck_artifact_exists(self):
        assert P13_RECHECK.exists(), "P13-B recheck artifact not found"

    def test_recheck_paper_only_true(self):
        data = json.loads(P13_RECHECK.read_text())
        assert data["paper_only"] is True

    def test_recheck_network_call_false(self):
        data = json.loads(P13_RECHECK.read_text())
        assert data["network_call"] is False

    def test_recheck_is_blocked_true(self):
        data = json.loads(P13_RECHECK.read_text())
        assert data["is_blocked"] is True

    def test_recheck_p13_classification(self):
        data = json.loads(P13_RECHECK.read_text())
        assert data["p13_classification"] == "P13_BLOCKED_MONITOR_ONLY"

    def test_recheck_p14_not_allowed(self):
        data = json.loads(P13_RECHECK.read_text())
        assert data["p14_allowed"] is False

    def test_recheck_ceo_decision_still_defer(self):
        data = json.loads(P13_RECHECK.read_text())
        assert data["ceo_decision_status"] == "DEFER_DECISION"

    def test_recheck_forward_pairs_unchanged(self):
        data = json.loads(P13_RECHECK.read_text())
        assert data["forward_pairs"] == 0
        assert data["forward_accumulation_changed"] is False


# ---------------------------------------------------------------------------
# TestP13CCEOReminderPacket
# ---------------------------------------------------------------------------

class TestP13CCEOReminderPacket:
    def test_reminder_artifact_exists(self):
        assert P13_CEO_REMINDER.exists(), "P13-C CEO reminder packet not found"

    def test_reminder_paper_only_true(self):
        data = json.loads(P13_CEO_REMINDER.read_text())
        assert data["paper_only"] is True

    def test_reminder_has_three_options(self):
        data = json.loads(P13_CEO_REMINDER.read_text())
        opts = data["options"]
        assert "OPTION_A" in opts
        assert "OPTION_B" in opts
        assert "OPTION_C" in opts

    def test_reminder_each_option_has_required_fields(self):
        data = json.loads(P13_CEO_REMINDER.read_text())
        for key, opt in data["options"].items():
            assert "impact" in opt, f"{key} missing 'impact'"
            assert "unblock_condition" in opt, f"{key} missing 'unblock_condition'"
            assert "next_owner" in opt, f"{key} missing 'next_owner'"

    def test_reminder_current_active_is_option_c(self):
        data = json.loads(P13_CEO_REMINDER.read_text())
        assert data["current_active_option"] == "OPTION_C"

    def test_reminder_p14_not_allowed(self):
        data = json.loads(P13_CEO_REMINDER.read_text())
        assert data["p14_allowed"] is False

    def test_reminder_no_profitability_claim(self):
        text = P13_CEO_REMINDER.read_text().lower()
        assert "profitable" not in text or "不宣稱" in P13_CEO_REMINDER.read_text()


# ---------------------------------------------------------------------------
# TestP13DStopRuleEnforcement
# ---------------------------------------------------------------------------

class TestP13DStopRuleArtifact:
    def test_stop_rule_artifact_exists(self):
        assert P13_STOP_RULE.exists(), "P13-D stop rule artifact not found"

    def test_stop_rule_paper_only_true(self):
        data = json.loads(P13_STOP_RULE.read_text())
        assert data["paper_only"] is True

    def test_stop_rule_enforcement_pass(self):
        data = json.loads(P13_STOP_RULE.read_text())
        assert data["enforcement_result"] == "PASS"

    def test_stop_rule_all_forbidden_blocked(self):
        data = json.loads(P13_STOP_RULE.read_text())
        assert data["all_forbidden_actions_blocked"] is True

    def test_stop_rule_all_allowed_permitted(self):
        data = json.loads(P13_STOP_RULE.read_text())
        assert data["all_allowed_actions_permitted"] is True

    def test_stop_rule_network_call_false(self):
        data = json.loads(P13_STOP_RULE.read_text())
        assert data["network_call"] is False

    def test_stop_rule_p14_not_allowed(self):
        data = json.loads(P13_STOP_RULE.read_text())
        assert data["p14_allowed"] is False


class TestP13DStopRuleLogic:
    """Unit tests for enforcement script logic."""

    def test_paper_only_false_raises(self, tmp_path):
        with pytest.raises(PaperOnlyViolationError):
            run_stop_rule_enforcement(
                output_path=tmp_path / "out.json",
                paper_only=False,
            )

    def test_all_forbidden_actions_blocked_in_blocked_state(self, tmp_path):
        result = run_stop_rule_enforcement(output_path=tmp_path / "out.json")
        for action_val, blocked in result["forbidden_actions_check"].items():
            assert blocked is True, f"Expected {action_val} to be forbidden, got False"

    def test_all_allowed_actions_permitted(self, tmp_path):
        result = run_stop_rule_enforcement(output_path=tmp_path / "out.json")
        for action_val, permitted in result["allowed_actions_check"].items():
            assert permitted is True, f"Expected {action_val} to be allowed, got False"

    def test_optimizer_promotion_is_forbidden(self, tmp_path):
        result = run_stop_rule_enforcement(output_path=tmp_path / "out.json")
        assert result["forbidden_actions_check"]["OPTIMIZER_PROMOTION"] is True

    def test_production_proposal_is_forbidden(self, tmp_path):
        result = run_stop_rule_enforcement(output_path=tmp_path / "out.json")
        assert result["forbidden_actions_check"]["PRODUCTION_PROPOSAL"] is True

    def test_live_odds_write_is_forbidden(self, tmp_path):
        result = run_stop_rule_enforcement(output_path=tmp_path / "out.json")
        assert result["forbidden_actions_check"]["LIVE_ODDS_WRITE"] is True

    def test_tsl_crawler_modification_is_forbidden(self, tmp_path):
        result = run_stop_rule_enforcement(output_path=tmp_path / "out.json")
        assert result["forbidden_actions_check"]["TSL_CRAWLER_MODIFICATION"] is True

    def test_historical_api_call_without_approval_is_forbidden(self, tmp_path):
        result = run_stop_rule_enforcement(output_path=tmp_path / "out.json")
        assert result["forbidden_actions_check"]["HISTORICAL_API_CALL_WITHOUT_APPROVAL"] is True

    def test_profitability_claim_is_forbidden(self, tmp_path):
        result = run_stop_rule_enforcement(output_path=tmp_path / "out.json")
        assert result["forbidden_actions_check"]["PROFITABILITY_CLAIM"] is True

    def test_ceo_followup_is_allowed(self, tmp_path):
        result = run_stop_rule_enforcement(output_path=tmp_path / "out.json")
        assert result["allowed_actions_check"]["CEO_FOLLOWUP"] is True

    def test_paper_only_monitoring_is_allowed(self, tmp_path):
        result = run_stop_rule_enforcement(output_path=tmp_path / "out.json")
        assert result["allowed_actions_check"]["PAPER_ONLY_MONITORING"] is True

    def test_forward_coverage_readiness_check_is_allowed(self, tmp_path):
        result = run_stop_rule_enforcement(output_path=tmp_path / "out.json")
        assert result["allowed_actions_check"]["FORWARD_COVERAGE_READINESS_CHECK"] is True

    def test_api_key_readiness_check_is_allowed(self, tmp_path):
        result = run_stop_rule_enforcement(output_path=tmp_path / "out.json")
        assert result["allowed_actions_check"]["API_KEY_READINESS_CHECK"] is True

    def test_report_only_is_allowed(self, tmp_path):
        result = run_stop_rule_enforcement(output_path=tmp_path / "out.json")
        assert result["allowed_actions_check"]["REPORT_ONLY"] is True

    def test_p13_not_allowed_when_blocked(self, tmp_path):
        result = run_stop_rule_enforcement(output_path=tmp_path / "out.json")
        assert result["p13_allowed"] is False

    def test_no_network_import_in_script(self):
        script = (BASE / "scripts/run_stop_rule_enforcement_p13.py").read_text(encoding="utf-8")
        assert "import requests" not in script
        assert "import urllib" not in script
        assert "import socket" not in script
        assert "import tsl_crawler" not in script

    def test_result_champion_preserved(self, tmp_path):
        result = run_stop_rule_enforcement(output_path=tmp_path / "out.json")
        assert result["fixed_edge_5pct_champion_preserved"] is True

    def test_result_paper_only_in_output(self, tmp_path):
        result = run_stop_rule_enforcement(output_path=tmp_path / "out.json")
        assert result["paper_only"] is True
