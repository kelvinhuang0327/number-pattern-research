from __future__ import annotations

import json
from pathlib import Path

from wbc_backend.reporting.strategy_replay_production_enablement_boundary import (
    GO_READY_FOR_SEPARATE_ENABLEMENT_PHASE,
    NO_GO,
    evaluate_production_enablement_boundary,
)


ROOT = Path("/Users/kelvin/Kelvin-WorkSpace/Betting-pool")


def _approval_summary(**overrides: object) -> dict[str, object]:
    summary = {
        "real_approval_intake_accepted": False,
        "real_approval": False,
        "simulation_only": True,
        "production_metadata_registry_accepted": False,
        "production_enablement_allowed": False,
        "runtime_config_change_allowed": False,
        "ui_launch_allowed": False,
        "production_migration_allowed": False,
        "approval_decision": "REJECT",
        "reviewed_registry_path": "",
        "accepted_context_is_preview_only": True,
        "acceptance_context_preview": None,
        "fake_approval": False,
    }
    summary.update(overrides)
    return summary


def _lifecycle_summary(**overrides: object) -> dict[str, object]:
    summary = {
        "lifecycle_state": "NO_REAL_APPROVAL",
        "accepted_context_is_preview_only": True,
        "production_enabled": False,
        "production_enablement_allowed": False,
        "runtime_config_change_allowed": False,
        "ui_launch_allowed": False,
        "production_migration_allowed": False,
    }
    summary.update(overrides)
    return summary


def _preflight_summary(**overrides: object) -> dict[str, object]:
    summary = {
        "runtime_enablement_ready": False,
        "operator_signoff": False,
        "rollback_switch_available": False,
        "strict_mode_enabled": False,
        "fixture_validation_rerun_passed": False,
        "synthetic_future_row_dry_run_passed": False,
        "monitoring_audit_log_plan_ready": False,
        "blockers": ["accepted registry gate must pass"],
    }
    summary.update(overrides)
    return summary


def _dry_run_summary(**overrides: object) -> dict[str, object]:
    summary = {
        "dry_run_config_preview_exists": False,
        "dry_run_result_passed": False,
        "dry_run_config_preview_is_no_op": False,
        "dry_run_modified_production_config": False,
        "historical_backfill_disabled": True,
        "ui_gate_passed": False,
        "production_migration_blocked": True,
    }
    summary.update(overrides)
    return summary


def test_default_boundary_is_no_go() -> None:
    boundary = evaluate_production_enablement_boundary(None, None, None, None)
    assert boundary["boundary_state"] == NO_GO
    assert boundary["production_enablement_allowed"] is False
    assert "NO_REAL_HUMAN_APPROVAL" in boundary["no_go_reasons"]


def test_no_real_approval_keeps_no_go() -> None:
    boundary = evaluate_production_enablement_boundary(_approval_summary(), None, None, None)
    assert boundary["boundary_state"] == NO_GO
    assert "NO_REAL_HUMAN_APPROVAL" in boundary["no_go_reasons"]


def test_simulation_only_approval_keeps_no_go() -> None:
    boundary = evaluate_production_enablement_boundary(
        _approval_summary(simulation_only=True, real_approval=False, real_approval_intake_accepted=False),
        None,
        None,
        None,
    )
    assert boundary["boundary_state"] == NO_GO
    assert "ACCEPTED_CONTEXT_PREVIEW_ONLY" in boundary["no_go_reasons"]


def test_preview_only_context_keeps_no_go() -> None:
    boundary = evaluate_production_enablement_boundary(
        _approval_summary(real_approval=True, simulation_only=False, real_approval_intake_accepted=True),
        _lifecycle_summary(lifecycle_state="PREVIEW_GENERATED_NOT_ENABLED", accepted_context_is_preview_only=True),
        _preflight_summary(),
        _dry_run_summary(),
    )
    assert boundary["boundary_state"] == NO_GO
    assert "ACCEPTED_CONTEXT_PREVIEW_ONLY" in boundary["no_go_reasons"]


def test_preflight_blocked_keeps_no_go() -> None:
    boundary = evaluate_production_enablement_boundary(
        _approval_summary(real_approval=True, simulation_only=False, real_approval_intake_accepted=True),
        _lifecycle_summary(lifecycle_state="READY_FOR_OPERATOR_ENABLEMENT_REVIEW", accepted_context_is_preview_only=False),
        _preflight_summary(runtime_enablement_ready=False, operator_signoff=False),
        _dry_run_summary(dry_run_config_preview_exists=True, dry_run_result_passed=True, dry_run_config_preview_is_no_op=True),
    )
    assert boundary["boundary_state"] == NO_GO
    assert "RUNTIME_PREFLIGHT_BLOCKED" in boundary["no_go_reasons"]


def test_operator_signoff_missing_keeps_no_go() -> None:
    boundary = evaluate_production_enablement_boundary(
        _approval_summary(real_approval=True, simulation_only=False, real_approval_intake_accepted=True),
        _lifecycle_summary(lifecycle_state="READY_FOR_OPERATOR_ENABLEMENT_REVIEW", accepted_context_is_preview_only=False),
        _preflight_summary(runtime_enablement_ready=True, operator_signoff=False),
        _dry_run_summary(dry_run_config_preview_exists=True, dry_run_result_passed=True, dry_run_config_preview_is_no_op=True),
    )
    assert boundary["boundary_state"] == NO_GO
    assert "OPERATOR_SIGNOFF_MISSING" in boundary["no_go_reasons"]


def test_dry_run_preview_does_not_allow_production_config_change() -> None:
    boundary = evaluate_production_enablement_boundary(
        _approval_summary(real_approval=True, simulation_only=False, real_approval_intake_accepted=True),
        _lifecycle_summary(lifecycle_state="READY_FOR_OPERATOR_ENABLEMENT_REVIEW", accepted_context_is_preview_only=False),
        _preflight_summary(runtime_enablement_ready=True, operator_signoff=False),
        _dry_run_summary(
            dry_run_config_preview_exists=True,
            dry_run_result_passed=True,
            dry_run_config_preview_is_no_op=True,
            dry_run_modified_production_config=False,
        ),
    )
    assert boundary["production_enablement_allowed"] is False
    assert boundary["boundary_state"] == NO_GO
    assert "PRODUCTION_CONFIG_CHANGE_NOT_ALLOWED_IN_THIS_PHASE" in boundary["no_go_reasons"]


def test_all_readiness_checks_go_ready_for_separate_enablement_phase() -> None:
    boundary = evaluate_production_enablement_boundary(
        _approval_summary(
            real_approval_intake_accepted=True,
            real_approval=True,
            simulation_only=False,
            production_metadata_registry_accepted=True,
            fake_approval=False,
            approval_decision="APPROVE",
        ),
        _lifecycle_summary(
            lifecycle_state="READY_FOR_OPERATOR_ENABLEMENT_REVIEW",
            accepted_context_is_preview_only=False,
            production_enabled=False,
        ),
        _preflight_summary(
            runtime_enablement_ready=True,
            operator_signoff=True,
            rollback_switch_available=True,
            strict_mode_enabled=True,
            fixture_validation_rerun_passed=True,
            synthetic_future_row_dry_run_passed=True,
            monitoring_audit_log_plan_ready=True,
        ),
        _dry_run_summary(
            dry_run_config_preview_exists=True,
            dry_run_result_passed=True,
            dry_run_config_preview_is_no_op=True,
            dry_run_modified_production_config=False,
            historical_backfill_disabled=True,
            ui_gate_passed=False,
            production_migration_blocked=True,
        ),
    )
    assert boundary["boundary_state"] == GO_READY_FOR_SEPARATE_ENABLEMENT_PHASE
    assert boundary["production_enablement_allowed"] is False
    assert boundary["go_ready"] is True


def test_ui_remains_blocked_by_separate_gate() -> None:
    boundary = evaluate_production_enablement_boundary(
        _approval_summary(
            real_approval_intake_accepted=True,
            real_approval=True,
            simulation_only=False,
            production_metadata_registry_accepted=True,
            fake_approval=False,
            approval_decision="APPROVE",
        ),
        _lifecycle_summary(lifecycle_state="READY_FOR_OPERATOR_ENABLEMENT_REVIEW", accepted_context_is_preview_only=False),
        _preflight_summary(runtime_enablement_ready=True, operator_signoff=True, rollback_switch_available=True, strict_mode_enabled=True, fixture_validation_rerun_passed=True, synthetic_future_row_dry_run_passed=True, monitoring_audit_log_plan_ready=True),
        _dry_run_summary(dry_run_config_preview_exists=True, dry_run_result_passed=True, dry_run_config_preview_is_no_op=True, historical_backfill_disabled=True, ui_gate_passed=False, production_migration_blocked=True),
    )
    assert boundary["boundary_state"] == GO_READY_FOR_SEPARATE_ENABLEMENT_PHASE
    checklist = boundary["checklist"]
    assert any(item["check"] == "ui_gate_not_passed" and item["passed"] is True for item in checklist)


def test_production_migration_remains_blocked_by_separate_gate() -> None:
    boundary = evaluate_production_enablement_boundary(
        _approval_summary(
            real_approval_intake_accepted=True,
            real_approval=True,
            simulation_only=False,
            production_metadata_registry_accepted=True,
            fake_approval=False,
            approval_decision="APPROVE",
        ),
        _lifecycle_summary(lifecycle_state="READY_FOR_OPERATOR_ENABLEMENT_REVIEW", accepted_context_is_preview_only=False),
        _preflight_summary(runtime_enablement_ready=True, operator_signoff=True, rollback_switch_available=True, strict_mode_enabled=True, fixture_validation_rerun_passed=True, synthetic_future_row_dry_run_passed=True, monitoring_audit_log_plan_ready=True),
        _dry_run_summary(dry_run_config_preview_exists=True, dry_run_result_passed=True, dry_run_config_preview_is_no_op=True, historical_backfill_disabled=True, ui_gate_passed=False, production_migration_blocked=True),
    )
    assert boundary["boundary_state"] == GO_READY_FOR_SEPARATE_ENABLEMENT_PHASE
    assert any(item["check"] == "production_migration_blocked" and item["passed"] is True for item in boundary["checklist"])


def test_no_production_db_access() -> None:
    boundary = evaluate_production_enablement_boundary(_approval_summary(), _lifecycle_summary(), _preflight_summary(), _dry_run_summary())
    assert "db" not in json.dumps(boundary).lower()
