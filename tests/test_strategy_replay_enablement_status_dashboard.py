from __future__ import annotations

import json
from pathlib import Path
import subprocess

from wbc_backend.reporting.strategy_replay_enablement_status_dashboard import (
    GO_READY_FOR_SEPARATE_ENABLEMENT_PHASE,
    NO_GO,
    build_strategy_replay_enablement_status,
    classify_strategy_replay_next_action,
    identify_strategy_replay_enablement_blockers,
)


ROOT = Path("/Users/kelvin/Kelvin-WorkSpace/Betting-pool")
SCRIPT = ROOT / "scripts/check_strategy_replay_enablement_status.py"


def _approval(real_approval: bool = False, accepted: bool = False, simulation_only: bool = True, production_metadata_registry_accepted: bool = False, runtime_config_change_allowed: bool = False, ui_launch_allowed: bool = False, production_migration_allowed: bool = False, accepted_context_is_preview_only: bool = False) -> dict[str, object]:
    return {
        "real_approval_intake_accepted": accepted,
        "real_approval": real_approval,
        "simulation_only": simulation_only,
        "production_metadata_registry_accepted": production_metadata_registry_accepted,
        "production_enablement_allowed": False,
        "runtime_config_change_allowed": runtime_config_change_allowed,
        "ui_launch_allowed": ui_launch_allowed,
        "production_migration_allowed": production_migration_allowed,
        "accepted_context_is_preview_only": accepted_context_is_preview_only,
        "acceptance_context_preview": None,
        "fake_approval": False,
    }


def _lifecycle(state: str = "NO_REAL_APPROVAL", preview_only: bool = True, production_enabled: bool = False) -> dict[str, object]:
    return {
        "lifecycle_state": state,
        "accepted_context_is_preview_only": preview_only,
        "production_enabled": production_enabled,
        "production_enablement_allowed": False,
        "runtime_config_change_allowed": False,
        "ui_launch_allowed": False,
        "production_migration_allowed": False,
    }


def _preflight(runtime_enablement_ready: bool = False, operator_signoff: bool = False) -> dict[str, object]:
    return {
        "runtime_enablement_ready": runtime_enablement_ready,
        "operator_signoff": operator_signoff,
        "rollback_switch_available": False,
        "strict_mode_enabled": False,
        "fixture_validation_rerun_passed": False,
        "synthetic_future_row_dry_run_passed": False,
        "monitoring_audit_log_plan_ready": False,
        "blockers": ["accepted registry gate must pass"],
    }


def _dry_run(dry_run_config_preview_exists: bool = False, dry_run_result_passed: bool = False, dry_run_config_preview_is_no_op: bool = False, dry_run_modified_production_config: bool = False, historical_backfill_disabled: bool = True, ui_gate_passed: bool = False, production_migration_blocked: bool = True) -> dict[str, object]:
    return {
        "dry_run_config_preview_exists": dry_run_config_preview_exists,
        "dry_run_result_passed": dry_run_result_passed,
        "dry_run_config_preview_is_no_op": dry_run_config_preview_is_no_op,
        "dry_run_modified_production_config": dry_run_modified_production_config,
        "historical_backfill_disabled": historical_backfill_disabled,
        "ui_gate_passed": ui_gate_passed,
        "production_migration_blocked": production_migration_blocked,
    }


def _boundary(boundary_state: str = NO_GO) -> dict[str, object]:
    return {"boundary_state": boundary_state}


def test_default_dashboard_blocks_production_enablement() -> None:
    dashboard = build_strategy_replay_enablement_status(None, None, None, None, None)
    assert dashboard["production_actions_allowed"] is False
    assert dashboard["summary"]["runtime_production_enablement_can_start"] is False
    assert dashboard["summary"]["separate_enablement_phase_required"] is True
    assert "NO_REAL_HUMAN_APPROVAL_FORM" in dashboard["blockers"]


def test_missing_real_approval_blocks_production_enablement() -> None:
    dashboard = build_strategy_replay_enablement_status(_approval(), _lifecycle(), _preflight(), _dry_run(), _boundary())
    assert dashboard["summary"]["real_human_approval_exists"] is False
    assert dashboard["summary"]["runtime_production_enablement_can_start"] is False
    assert "NO_REAL_HUMAN_APPROVAL_FORM" in dashboard["blockers"]


def test_preview_only_accepted_context_blocks_production_enablement() -> None:
    dashboard = build_strategy_replay_enablement_status(
        _approval(real_approval=True, accepted=True, simulation_only=False, production_metadata_registry_accepted=False),
        _lifecycle(state="PREVIEW_GENERATED_NOT_ENABLED", preview_only=True),
        _preflight(runtime_enablement_ready=False, operator_signoff=False),
        _dry_run(dry_run_config_preview_exists=True, dry_run_result_passed=True, dry_run_config_preview_is_no_op=True),
        _boundary(),
    )
    assert dashboard["summary"]["accepted_context_preview_exists"] is True
    assert dashboard["summary"]["accepted_context_preview_is_production_enablement"] is False
    assert dashboard["summary"]["runtime_production_enablement_can_start"] is False


def test_dry_run_config_preview_no_op_blocks_runtime_config_change() -> None:
    dashboard = build_strategy_replay_enablement_status(
        _approval(real_approval=True, accepted=True, simulation_only=False, production_metadata_registry_accepted=True, runtime_config_change_allowed=False),
        _lifecycle(state="READY_FOR_OPERATOR_ENABLEMENT_REVIEW", preview_only=False),
        {
            "runtime_enablement_ready": True,
            "operator_signoff": True,
            "rollback_switch_available": True,
            "strict_mode_enabled": True,
            "fixture_validation_rerun_passed": True,
            "synthetic_future_row_dry_run_passed": True,
            "monitoring_audit_log_plan_ready": True,
            "blockers": [],
        },
        _dry_run(dry_run_config_preview_exists=True, dry_run_result_passed=True, dry_run_config_preview_is_no_op=True),
        _boundary(GO_READY_FOR_SEPARATE_ENABLEMENT_PHASE),
    )
    assert dashboard["summary"]["dry_run_config_preview_is_no_op"] is True
    assert dashboard["summary"]["runtime_config_change_can_start"] is False


def test_ui_remains_blocked_by_separate_gate() -> None:
    dashboard = build_strategy_replay_enablement_status(
        _approval(real_approval=True, accepted=True, simulation_only=False, production_metadata_registry_accepted=True),
        _lifecycle(state="READY_FOR_OPERATOR_ENABLEMENT_REVIEW", preview_only=False),
        _preflight(runtime_enablement_ready=True, operator_signoff=True),
        _dry_run(dry_run_config_preview_exists=True, dry_run_result_passed=True, dry_run_config_preview_is_no_op=True, ui_gate_passed=False),
        _boundary(GO_READY_FOR_SEPARATE_ENABLEMENT_PHASE),
    )
    assert dashboard["summary"]["ui_can_start"] is False
    assert "UI_GATE_NOT_PASSED" in dashboard["blockers"]


def test_production_migration_remains_blocked_by_separate_gate() -> None:
    dashboard = build_strategy_replay_enablement_status(
        _approval(real_approval=True, accepted=True, simulation_only=False, production_metadata_registry_accepted=True),
        _lifecycle(state="READY_FOR_OPERATOR_ENABLEMENT_REVIEW", preview_only=False),
        _preflight(runtime_enablement_ready=True, operator_signoff=True),
        _dry_run(dry_run_config_preview_exists=True, dry_run_result_passed=True, dry_run_config_preview_is_no_op=True, production_migration_blocked=True),
        _boundary(GO_READY_FOR_SEPARATE_ENABLEMENT_PHASE),
    )
    assert dashboard["summary"]["production_migration_can_start"] is False
    assert "PRODUCTION_MIGRATION_BLOCKED" in dashboard["blockers"]


def test_simulation_only_approval_does_not_allow_production_action() -> None:
    dashboard = build_strategy_replay_enablement_status(
        _approval(real_approval=False, accepted=False, simulation_only=True, production_metadata_registry_accepted=False),
        _lifecycle(),
        _preflight(),
        _dry_run(),
        _boundary(),
    )
    assert dashboard["summary"]["real_human_approval_exists"] is False
    assert dashboard["production_actions_allowed"] is False
    assert "SIMULATION_ONLY_APPROVAL_IS_NOT_REAL_APPROVAL" in dashboard["blockers"]


def test_next_action_reports_explicit_follow_up() -> None:
    dashboard = build_strategy_replay_enablement_status(
        _approval(real_approval=True, accepted=True, simulation_only=False, production_metadata_registry_accepted=True),
        _lifecycle(state="READY_FOR_OPERATOR_ENABLEMENT_REVIEW", preview_only=False),
        {
            "runtime_enablement_ready": True,
            "operator_signoff": True,
            "rollback_switch_available": True,
            "strict_mode_enabled": True,
            "fixture_validation_rerun_passed": True,
            "synthetic_future_row_dry_run_passed": True,
            "monitoring_audit_log_plan_ready": True,
            "blockers": [],
        },
        {
            "dry_run_config_preview_exists": True,
            "dry_run_result_passed": True,
            "dry_run_config_preview_is_no_op": True,
            "dry_run_modified_production_config": False,
            "historical_backfill_disabled": True,
            "ui_gate_passed": False,
            "production_migration_blocked": True,
        },
        _boundary(GO_READY_FOR_SEPARATE_ENABLEMENT_PHASE),
    )
    assert dashboard["phase_status"] == GO_READY_FOR_SEPARATE_ENABLEMENT_PHASE
    assert dashboard["next_action"]
    assert dashboard["production_actions_allowed"] is False


def test_script_prints_marker_and_writes_only_with_output(tmp_path: Path) -> None:
    result = subprocess.run(["./.venv/bin/python", str(SCRIPT)], cwd=ROOT, capture_output=True, text=True, check=True)
    assert "STRATEGY_REPLAY_ENABLEMENT_STATUS_CHECK" in result.stdout

    output_path = tmp_path / "dashboard.json"
    result_with_output = subprocess.run(["./.venv/bin/python", str(SCRIPT), "--output", str(output_path)], cwd=ROOT, capture_output=True, text=True, check=True)
    assert "STRATEGY_REPLAY_ENABLEMENT_STATUS_CHECK" in result_with_output.stdout
    assert output_path.exists()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["final_marker"] == "P39_STRATEGY_REPLAY_ENABLEMENT_STATUS_DASHBOARD_READY"


def test_no_production_db_access() -> None:
    dashboard = build_strategy_replay_enablement_status(_approval(), _lifecycle(), _preflight(), _dry_run(), _boundary())
    assert "db" not in json.dumps(dashboard).lower()
