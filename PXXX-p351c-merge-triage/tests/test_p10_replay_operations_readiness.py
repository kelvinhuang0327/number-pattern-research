"""
test_p10_replay_operations_readiness.py
=========================================
Tests for P10 Replay Operations Readiness.

Verifies:
  1. P10 JSON exists and is valid
  2. dry_run_only=True
  3. production_rows=460
  4. apply_authorized=False (phrase not received)
  5. required_phrase exact match
  6. launch_readiness=BLOCKED_BY_CEO_APPLY_PHRASE
  7. fake_success_count=0
  8. Runbook doc exists
  9. Monitoring doc exists
 10. Rollback checklist exists
 11. legal_next_actions are limited to exactly 2
 12. illegal_next_actions include apply-without-phrase
 13. daily_verification_commands include row_count, drift, api_contract, fake_success_guard
 14. rollback checklist mentions controlled_apply_id
 15. Production DB row count remains 460
 16. post_apply_verification_commands include row_count_488 and idempotency_rerun
 17. alerts include ALERT_ROW_COUNT_DRIFT and ALERT_FAKE_SUCCESS
 18. rollback_triggers include retired rows condition
 19. safety_flags show no unauthorized apply
 20. All referenced scripts exist
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

REPO_ROOT  = Path(__file__).resolve().parent.parent
DB_PATH    = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
P10_JSON   = REPO_ROOT / "outputs" / "replay" / "p10_replay_operations_readiness_20260520.json"
RUNBOOK    = REPO_ROOT / "docs" / "replay" / "p10_replay_operations_runbook_20260520.md"
MONITORING = REPO_ROOT / "docs" / "replay" / "p10_replay_monitoring_plan_20260520.md"
ROLLBACK   = REPO_ROOT / "docs" / "replay" / "p10_replay_rollback_checklist_20260520.md"

REQUIRED_PHRASE = "YES apply P7 controlled replay rows"
PRODUCTION_ROWS = 460

sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture(scope="module")
def p10() -> dict:
    assert P10_JSON.exists(), f"P10 JSON not found: {P10_JSON}"
    return json.loads(P10_JSON.read_text())


class TestP10Structure:
    def test_phase(self, p10):
        assert p10["phase"] == "P10_REPLAY_OPERATIONS_READINESS"

    def test_dry_run_only(self, p10):
        assert p10["dry_run_only"] is True

    def test_has_required_keys(self, p10):
        for key in ("phase", "dry_run_only", "production_rows", "apply_authorized",
                    "required_phrase", "launch_readiness", "fake_success_count",
                    "runbook_created", "monitoring_plan_created", "rollback_checklist_created",
                    "daily_verification_commands", "post_apply_verification_commands",
                    "alerts", "rollback_triggers", "legal_next_actions",
                    "illegal_next_actions", "safety_flags"):
            assert key in p10, f"Missing key: {key}"


class TestAuthorizationState:
    def test_production_rows_460(self, p10):
        assert p10["production_rows"] == PRODUCTION_ROWS

    def test_apply_not_authorized(self, p10):
        assert p10["apply_authorized"] is False

    def test_required_phrase_exact(self, p10):
        assert p10["required_phrase"] == REQUIRED_PHRASE

    def test_launch_readiness_blocked(self, p10):
        assert p10["launch_readiness"] == "BLOCKED_BY_CEO_APPLY_PHRASE"

    def test_fake_success_zero(self, p10):
        assert p10["fake_success_count"] == 0

    def test_safety_no_unauthorized_apply(self, p10):
        assert p10["safety_flags"]["unauthorized_apply_performed"] is False

    def test_safety_no_db_write(self, p10):
        assert p10["safety_flags"]["db_write_performed"] is False


class TestLegalActions:
    def test_exactly_two_legal_actions(self, p10):
        assert len(p10["legal_next_actions"]) == 2

    def test_legal_actions_content(self, p10):
        legal = set(p10["legal_next_actions"])
        assert "CEO_AUTHORIZE_P7_ONLINE_APPLY_28_ROWS" in legal
        assert "KEEP_MONITORING_DRY_RUN" in legal

    def test_illegal_apply_without_phrase(self, p10):
        assert "APPLY_WITHOUT_EXACT_PHRASE" in p10["illegal_next_actions"]

    def test_illegal_retired_without_auth(self, p10):
        assert "APPLY_RETIRED_ROWS_WITHOUT_SEPARATE_AUTH" in p10["illegal_next_actions"]

    def test_illegal_no_data_as_success(self, p10):
        assert "COUNT_NO_DATA_AS_SUCCESS" in p10["illegal_next_actions"]

    def test_illegal_fabricate_rows(self, p10):
        assert "FABRICATE_REPLAY_ROWS" in p10["illegal_next_actions"]


class TestDailyVerificationCommands:
    def test_has_daily_commands(self, p10):
        cmds = p10["daily_verification_commands"]
        assert len(cmds) >= 4

    def test_row_count_command_exists(self, p10):
        names = {c["name"] for c in p10["daily_verification_commands"]}
        assert "row_count" in names

    def test_drift_guard_command_exists(self, p10):
        names = {c["name"] for c in p10["daily_verification_commands"]}
        assert "drift_guard" in names

    def test_api_contract_command_exists(self, p10):
        names = {c["name"] for c in p10["daily_verification_commands"]}
        assert "api_contract" in names

    def test_fake_success_guard_command_exists(self, p10):
        names = {c["name"] for c in p10["daily_verification_commands"]}
        assert "fake_success_guard" in names

    def test_all_commands_have_expected_field(self, p10):
        for cmd in p10["daily_verification_commands"]:
            assert "expected" in cmd, f"Command {cmd.get('name')} missing 'expected' field"
            assert "alert_if" in cmd, f"Command {cmd.get('name')} missing 'alert_if' field"


class TestPostApplyVerification:
    def test_has_post_apply_commands(self, p10):
        cmds = p10["post_apply_verification_commands"]
        assert len(cmds) >= 4

    def test_row_count_488_command(self, p10):
        names = {c["name"] for c in p10["post_apply_verification_commands"]}
        assert "row_count_488" in names

    def test_idempotency_rerun_command(self, p10):
        names = {c["name"] for c in p10["post_apply_verification_commands"]}
        assert "idempotency_rerun" in names

    def test_api_contract_in_post_apply(self, p10):
        names = {c["name"] for c in p10["post_apply_verification_commands"]}
        assert "api_contract" in names

    def test_drift_guard_in_post_apply(self, p10):
        names = {c["name"] for c in p10["post_apply_verification_commands"]}
        assert "drift_guard" in names

    def test_steps_are_numbered(self, p10):
        for cmd in p10["post_apply_verification_commands"]:
            assert "step" in cmd, f"Post-apply command {cmd.get('name')} missing step number"


class TestAlerts:
    def test_has_alerts(self, p10):
        assert len(p10["alerts"]) >= 4

    def test_row_count_drift_alert(self, p10):
        ids = {a["id"] for a in p10["alerts"]}
        assert "ALERT_ROW_COUNT_DRIFT" in ids

    def test_drift_guard_fail_alert(self, p10):
        ids = {a["id"] for a in p10["alerts"]}
        assert "ALERT_DRIFT_GUARD_FAIL" in ids

    def test_fake_success_alert(self, p10):
        ids = {a["id"] for a in p10["alerts"]}
        assert "ALERT_FAKE_SUCCESS" in ids

    def test_unauthorized_apply_alert(self, p10):
        ids = {a["id"] for a in p10["alerts"]}
        assert "ALERT_UNAUTHORIZED_APPLY" in ids

    def test_all_alerts_have_severity(self, p10):
        for alert in p10["alerts"]:
            assert "severity" in alert
            assert alert["severity"] in ("CRITICAL", "HIGH", "MEDIUM", "LOW")


class TestRollbackTriggers:
    def test_has_rollback_triggers(self, p10):
        assert len(p10["rollback_triggers"]) >= 4

    def test_retired_rows_trigger(self, p10):
        triggers = " ".join(p10["rollback_triggers"]).lower()
        assert "retired" in triggers or "RETIRED" in " ".join(p10["rollback_triggers"])

    def test_row_count_trigger(self, p10):
        triggers = " ".join(p10["rollback_triggers"])
        assert "488" in triggers or "rows" in triggers.lower()


class TestDocumentArtifacts:
    def test_runbook_exists(self, p10):
        assert RUNBOOK.exists(), f"Runbook not found: {RUNBOOK}"
        assert p10["runbook_created"] is True

    def test_monitoring_exists(self, p10):
        assert MONITORING.exists(), f"Monitoring doc not found: {MONITORING}"
        assert p10["monitoring_plan_created"] is True

    def test_rollback_exists(self, p10):
        assert ROLLBACK.exists(), f"Rollback checklist not found: {ROLLBACK}"
        assert p10["rollback_checklist_created"] is True

    def test_rollback_mentions_controlled_apply_id(self):
        content = ROLLBACK.read_text()
        assert "controlled_apply_id" in content

    def test_rollback_mentions_backup(self):
        content = ROLLBACK.read_text()
        assert "backup" in content.lower()

    def test_runbook_has_pre_apply_checklist(self):
        content = RUNBOOK.read_text()
        assert "Pre-Apply" in content or "pre-apply" in content.lower()

    def test_runbook_has_apply_command(self):
        content = RUNBOOK.read_text()
        assert "p7_controlled_replay_row_apply.py" in content

    def test_monitoring_has_row_count_check(self):
        content = MONITORING.read_text()
        assert "strategy_prediction_replays" in content

    def test_monitoring_has_drift_guard_check(self):
        content = MONITORING.read_text()
        assert "drift_guard" in content or "replay_lifecycle_drift_guard" in content


class TestProductionDB:
    def test_production_rows_still_460(self):
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute("PRAGMA query_only = ON")
        count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
        conn.close()
        assert count == PRODUCTION_ROWS, (
            f"CRITICAL: Production rows = {count}, expected {PRODUCTION_ROWS}"
        )


class TestReferencedScripts:
    def test_drift_guard_script_exists(self):
        assert (REPO_ROOT / "scripts" / "replay_lifecycle_drift_guard.py").exists()

    def test_p7_apply_script_exists(self):
        assert (REPO_ROOT / "scripts" / "p7_controlled_replay_row_apply.py").exists()

    def test_registry_report_script_exists(self):
        assert (REPO_ROOT / "scripts" / "report_strategy_lifecycle_registry.py").exists()
