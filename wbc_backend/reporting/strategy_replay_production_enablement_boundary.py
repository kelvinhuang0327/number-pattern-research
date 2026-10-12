"""Go/No-Go boundary for Strategy Replay production enablement."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any


GO_READY_FOR_SEPARATE_ENABLEMENT_PHASE = "GO_READY_FOR_SEPARATE_ENABLEMENT_PHASE"
NO_GO = "NO_GO"


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_approval_summary(approval_summary: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = dict(approval_summary or {})
    return {
        "real_approval_intake_accepted": _as_bool(payload.get("real_approval_intake_accepted") or payload.get("accepted")),
        "real_approval": _as_bool(payload.get("real_approval")),
        "simulation_only": _as_bool(payload.get("simulation_only")),
        "production_metadata_registry_accepted": _as_bool(payload.get("production_metadata_registry_accepted")),
        "production_enablement_allowed": _as_bool(payload.get("production_enablement_allowed")),
        "runtime_config_change_allowed": _as_bool(payload.get("runtime_config_change_allowed")),
        "ui_launch_allowed": _as_bool(payload.get("ui_launch_allowed")),
        "production_migration_allowed": _as_bool(payload.get("production_migration_allowed")),
        "approval_decision": _as_text(payload.get("approval_decision")).upper(),
        "reviewed_registry_path": _as_text(payload.get("reviewed_registry_path")),
        "accepted_context_is_preview_only": _as_bool(payload.get("accepted_context_is_preview_only")),
        "preview_context_exists": payload.get("acceptance_context_preview") is not None,
        "fake_approval": _as_bool(payload.get("fake_approval")),
        "no_fake_approval": not _as_bool(payload.get("fake_approval")),
    }


def _normalize_lifecycle_summary(lifecycle_summary: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = dict(lifecycle_summary or {})
    return {
        "lifecycle_state": _as_text(payload.get("lifecycle_state")),
        "accepted_context_is_preview_only": _as_bool(payload.get("accepted_context_is_preview_only")),
        "production_enabled": _as_bool(payload.get("production_enabled")),
        "production_enablement_allowed": _as_bool(payload.get("production_enablement_allowed")),
        "runtime_config_change_allowed": _as_bool(payload.get("runtime_config_change_allowed")),
        "ui_launch_allowed": _as_bool(payload.get("ui_launch_allowed")),
        "production_migration_allowed": _as_bool(payload.get("production_migration_allowed")),
    }


def _normalize_preflight_summary(preflight_summary: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = dict(preflight_summary or {})
    return {
        "runtime_enablement_ready": _as_bool(payload.get("runtime_enablement_ready")),
        "operator_signoff": _as_bool(payload.get("operator_signoff")),
        "rollback_switch_available": _as_bool(payload.get("rollback_switch_available")),
        "strict_mode_enabled": _as_bool(payload.get("strict_mode_enabled")),
        "fixture_validation_rerun_passed": _as_bool(payload.get("fixture_validation_rerun_passed")),
        "synthetic_future_row_dry_run_passed": _as_bool(payload.get("synthetic_future_row_dry_run_passed")),
        "monitoring_audit_log_plan_ready": _as_bool(payload.get("monitoring_audit_log_plan_ready")),
        "blockers": [str(item).strip() for item in payload.get("blockers") or [] if str(item).strip()],
    }


def _normalize_dry_run_summary(dry_run_summary: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = dict(dry_run_summary or {})
    return {
        "dry_run_config_preview_exists": _as_bool(payload.get("dry_run_config_preview_exists")),
        "dry_run_result_passed": _as_bool(payload.get("dry_run_result_passed")),
        "dry_run_config_preview_is_no_op": _as_bool(payload.get("dry_run_config_preview_is_no_op")),
        "dry_run_modified_production_config": _as_bool(payload.get("dry_run_modified_production_config")),
        "historical_backfill_disabled": _as_bool(payload.get("historical_backfill_disabled")),
        "ui_gate_passed": _as_bool(payload.get("ui_gate_passed")),
        "production_migration_blocked": _as_bool(payload.get("production_migration_blocked")),
    }


def _approval_no_go_reasons(approval: Mapping[str, Any]) -> list[str]:
    reasons: list[str] = []
    if not approval["real_approval_intake_accepted"]:
        reasons.append("NO_REAL_HUMAN_APPROVAL")
    if not approval["production_metadata_registry_accepted"]:
        reasons.append("PRODUCTION_REGISTRY_NOT_ACCEPTED_FOR_REAL")
    if approval["simulation_only"]:
        reasons.append("ACCEPTED_CONTEXT_PREVIEW_ONLY")
    if not approval["no_fake_approval"]:
        reasons.append("NO_REAL_HUMAN_APPROVAL")
    if not approval["runtime_config_change_allowed"]:
        reasons.append("PRODUCTION_CONFIG_CHANGE_NOT_ALLOWED_IN_THIS_PHASE")
    return reasons


def _lifecycle_no_go_reasons(lifecycle: Mapping[str, Any]) -> list[str]:
    reasons: list[str] = []
    if lifecycle["accepted_context_is_preview_only"]:
        reasons.append("ACCEPTED_CONTEXT_PREVIEW_ONLY")
    if lifecycle["lifecycle_state"] != "READY_FOR_OPERATOR_ENABLEMENT_REVIEW":
        reasons.append("READY_FOR_OPERATOR_ENABLEMENT_REVIEW_REQUIRED")
    if lifecycle["production_enabled"]:
        reasons.append("PRODUCTION_ENABLED_NOT_ALLOWED_BY_THIS_PHASE")
    if lifecycle["production_enablement_allowed"]:
        reasons.append("PRODUCTION_CONFIG_CHANGE_NOT_ALLOWED_IN_THIS_PHASE")
    if lifecycle["ui_launch_allowed"]:
        reasons.append("UI_GATE_NOT_PASSED")
    if lifecycle["production_migration_allowed"]:
        reasons.append("PRODUCTION_MIGRATION_BLOCKED")
    return reasons


def _preflight_no_go_reasons(preflight: Mapping[str, Any]) -> list[str]:
    reasons: list[str] = []
    if not preflight["runtime_enablement_ready"]:
        reasons.append("RUNTIME_PREFLIGHT_BLOCKED")
    if not preflight["operator_signoff"]:
        reasons.append("OPERATOR_SIGNOFF_MISSING")
    if not preflight["rollback_switch_available"]:
        reasons.append("ROLLBACK_SWITCH_REQUIRED")
    if not preflight["strict_mode_enabled"]:
        reasons.append("STRICT_MODE_DECISION_REQUIRED")
    if not preflight["fixture_validation_rerun_passed"]:
        reasons.append("FIXTURE_VALIDATION_RERUN_REQUIRED")
    if not preflight["synthetic_future_row_dry_run_passed"]:
        reasons.append("SYNTHETIC_FUTURE_ROW_DRY_RUN_REQUIRED")
    if not preflight["monitoring_audit_log_plan_ready"]:
        reasons.append("MONITORING_AUDIT_LOG_PLAN_REQUIRED")
    return reasons


def _dry_run_no_go_reasons(dry_run: Mapping[str, Any]) -> list[str]:
    reasons: list[str] = []
    if not dry_run["dry_run_config_preview_exists"]:
        reasons.append("DRY_RUN_ONLY_NOT_PRODUCTION")
    if not dry_run["dry_run_result_passed"]:
        reasons.append("DRY_RUN_ONLY_NOT_PRODUCTION")
    if not dry_run["dry_run_config_preview_is_no_op"]:
        reasons.append("DRY_RUN_ONLY_NOT_PRODUCTION")
    if dry_run["dry_run_modified_production_config"]:
        reasons.append("PRODUCTION_CONFIG_CHANGE_NOT_ALLOWED_IN_THIS_PHASE")
    if not dry_run["historical_backfill_disabled"]:
        reasons.append("HISTORICAL_BACKFILL_DISABLED")
    if not dry_run["ui_gate_passed"]:
        reasons.append("UI_GATE_NOT_PASSED")
    if dry_run["production_migration_blocked"]:
        reasons.append("PRODUCTION_MIGRATION_BLOCKED")
    return reasons


def identify_production_enablement_no_go_reasons(
    approval_summary: Mapping[str, Any] | None,
    lifecycle_summary: Mapping[str, Any] | None,
    preflight_summary: Mapping[str, Any] | None,
    dry_run_summary: Mapping[str, Any] | None,
) -> list[str]:
    approval = _normalize_approval_summary(approval_summary)
    lifecycle = _normalize_lifecycle_summary(lifecycle_summary)
    preflight = _normalize_preflight_summary(preflight_summary)
    dry_run = _normalize_dry_run_summary(dry_run_summary)

    reasons: list[str] = []
    reasons.extend(_approval_no_go_reasons(approval))
    reasons.extend(_lifecycle_no_go_reasons(lifecycle))
    reasons.extend(_preflight_no_go_reasons(preflight))
    reasons.extend(_dry_run_no_go_reasons(dry_run))

    if not approval["production_metadata_registry_accepted"]:
        reasons.append("PRODUCTION_REGISTRY_NOT_ACCEPTED_FOR_REAL")
    if lifecycle["accepted_context_is_preview_only"]:
        reasons.append("ACCEPTED_CONTEXT_PREVIEW_ONLY")
    if not preflight["runtime_enablement_ready"]:
        reasons.append("RUNTIME_PREFLIGHT_BLOCKED")
    if not preflight["operator_signoff"]:
        reasons.append("OPERATOR_SIGNOFF_MISSING")
    if not dry_run["dry_run_config_preview_is_no_op"]:
        reasons.append("DRY_RUN_ONLY_NOT_PRODUCTION")
    if not dry_run["historical_backfill_disabled"]:
        reasons.append("HISTORICAL_BACKFILL_DISABLED")
    if not dry_run["ui_gate_passed"]:
        reasons.append("UI_GATE_NOT_PASSED")
    if dry_run["production_migration_blocked"]:
        reasons.append("PRODUCTION_MIGRATION_BLOCKED")

    deduped: list[str] = []
    for reason in reasons:
        if reason and reason not in deduped:
            deduped.append(reason)
    return deduped


def build_production_enablement_go_no_go_checklist(
    approval_summary: Mapping[str, Any] | None,
    lifecycle_summary: Mapping[str, Any] | None,
    preflight_summary: Mapping[str, Any] | None,
    dry_run_summary: Mapping[str, Any] | None,
) -> dict[str, Any]:
    approval = _normalize_approval_summary(approval_summary)
    lifecycle = _normalize_lifecycle_summary(lifecycle_summary)
    preflight = _normalize_preflight_summary(preflight_summary)
    dry_run = _normalize_dry_run_summary(dry_run_summary)
    no_go_reasons = identify_production_enablement_no_go_reasons(approval, lifecycle, preflight, dry_run)

    checklist = [
        {"check": "real_human_approval_exists", "passed": approval["real_approval_intake_accepted"], "required": True},
        {"check": "approval_not_simulation_only", "passed": not approval["simulation_only"], "required": True},
        {"check": "production_registry_accepted_for_real", "passed": approval["production_metadata_registry_accepted"], "required": True},
        {"check": "no_fake_approval", "passed": approval["no_fake_approval"], "required": True},
        {"check": "accepted_context_not_preview_only", "passed": not lifecycle["accepted_context_is_preview_only"], "required": True},
        {"check": "lifecycle_state_ready", "passed": lifecycle["lifecycle_state"] == "READY_FOR_OPERATOR_ENABLEMENT_REVIEW", "required": True},
        {"check": "accepted_context_separated_from_enablement", "passed": not lifecycle["production_enabled"], "required": True},
        {"check": "runtime_preflight_passes", "passed": preflight["runtime_enablement_ready"], "required": True},
        {"check": "operator_signoff", "passed": preflight["operator_signoff"], "required": True},
        {"check": "rollback_switch_available", "passed": preflight["rollback_switch_available"], "required": True},
        {"check": "strict_mode_decision_recorded", "passed": preflight["strict_mode_enabled"], "required": True},
        {"check": "fixture_validation_rerun_passed", "passed": preflight["fixture_validation_rerun_passed"], "required": True},
        {"check": "synthetic_future_row_dry_run_passed", "passed": preflight["synthetic_future_row_dry_run_passed"], "required": True},
        {"check": "monitoring_audit_log_plan_ready", "passed": preflight["monitoring_audit_log_plan_ready"], "required": True},
        {"check": "dry_run_config_preview_exists", "passed": dry_run["dry_run_config_preview_exists"], "required": True},
        {"check": "dry_run_result_passed", "passed": dry_run["dry_run_result_passed"], "required": True},
        {"check": "dry_run_config_preview_is_no_op", "passed": dry_run["dry_run_config_preview_is_no_op"], "required": True},
        {"check": "dry_run_did_not_modify_production_config", "passed": not dry_run["dry_run_modified_production_config"], "required": True},
        {"check": "historical_backfill_disabled", "passed": dry_run["historical_backfill_disabled"], "required": True},
        {"check": "ui_gate_not_passed", "passed": not dry_run["ui_gate_passed"], "required": True},
        {"check": "production_migration_blocked", "passed": dry_run["production_migration_blocked"], "required": True},
        {"check": "runtime_config_change_blocked", "passed": not approval["runtime_config_change_allowed"], "required": True},
        {"check": "production_enablement_separate_phase", "passed": True, "required": True},
    ]

    go_ready = (
        approval["real_approval_intake_accepted"]
        and approval["production_metadata_registry_accepted"]
        and not approval["simulation_only"]
        and approval["no_fake_approval"]
        and lifecycle["lifecycle_state"] == "READY_FOR_OPERATOR_ENABLEMENT_REVIEW"
        and not lifecycle["accepted_context_is_preview_only"]
        and preflight["runtime_enablement_ready"]
        and preflight["operator_signoff"]
        and preflight["rollback_switch_available"]
        and preflight["strict_mode_enabled"]
        and preflight["fixture_validation_rerun_passed"]
        and preflight["synthetic_future_row_dry_run_passed"]
        and preflight["monitoring_audit_log_plan_ready"]
        and dry_run["dry_run_config_preview_exists"]
        and dry_run["dry_run_result_passed"]
        and dry_run["dry_run_config_preview_is_no_op"]
        and not dry_run["dry_run_modified_production_config"]
        and dry_run["historical_backfill_disabled"]
        and not dry_run["ui_gate_passed"]
        and dry_run["production_migration_blocked"]
    )

    boundary_state = GO_READY_FOR_SEPARATE_ENABLEMENT_PHASE if go_ready else NO_GO
    production_enablement_allowed = False
    return {
        "boundary_state": boundary_state,
        "production_enablement_allowed": production_enablement_allowed,
        "go_ready": go_ready,
        "no_go_reasons": no_go_reasons,
        "no_go_reason_count": len(no_go_reasons),
        "checklist": checklist,
        "approval_summary": approval,
        "lifecycle_summary": lifecycle,
        "preflight_summary": preflight,
        "dry_run_summary": dry_run,
    }


def evaluate_production_enablement_boundary(
    approval_summary: Mapping[str, Any] | None,
    lifecycle_summary: Mapping[str, Any] | None,
    preflight_summary: Mapping[str, Any] | None,
    dry_run_summary: Mapping[str, Any] | None,
) -> dict[str, Any]:
    return build_production_enablement_go_no_go_checklist(
        approval_summary,
        lifecycle_summary,
        preflight_summary,
        dry_run_summary,
    )


def summarize_production_enablement_boundary(boundary_result: Mapping[str, Any] | None) -> dict[str, Any]:
    boundary = dict(boundary_result or {})
    return {
        "boundary_state": _as_text(boundary.get("boundary_state")) or NO_GO,
        "production_enablement_allowed": False,
        "go_ready": _as_bool(boundary.get("go_ready")),
        "no_go_reason_count": int(boundary.get("no_go_reason_count") or 0),
        "no_go_reasons": [str(item).strip() for item in boundary.get("no_go_reasons") or [] if str(item).strip()],
    }