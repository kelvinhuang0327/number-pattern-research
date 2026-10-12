"""Machine-readable status dashboard for Strategy Replay enablement."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any


NO_GO = "NO_GO"
GO_READY_FOR_SEPARATE_ENABLEMENT_PHASE = "GO_READY_FOR_SEPARATE_ENABLEMENT_PHASE"


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


def _normalize_mapping(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    return dict(payload or {})


def _derive_phase_status(boundary_result: Mapping[str, Any] | None, lifecycle_result: Mapping[str, Any] | None) -> str:
    boundary = _normalize_mapping(boundary_result)
    lifecycle = _normalize_mapping(lifecycle_result)
    if _as_text(boundary.get("boundary_state")) == GO_READY_FOR_SEPARATE_ENABLEMENT_PHASE:
        return GO_READY_FOR_SEPARATE_ENABLEMENT_PHASE
    if _as_text(lifecycle.get("lifecycle_state")) == "READY_FOR_OPERATOR_ENABLEMENT_REVIEW":
        return "READY_FOR_OPERATOR_ENABLEMENT_REVIEW"
    if _as_text(lifecycle.get("lifecycle_state")) == "PREFLIGHT_BLOCKED":
        return "PREFLIGHT_BLOCKED"
    if _as_text(lifecycle.get("lifecycle_state")) == "PREVIEW_GENERATED_NOT_ENABLED":
        return "PREVIEW_GENERATED_NOT_ENABLED"
    return "NO_REAL_APPROVAL"


def _approval_blockers(approval: Mapping[str, Any]) -> list[str]:
    blockers: list[str] = []
    if not _as_bool(approval.get("real_approval_intake_accepted") or approval.get("accepted")):
        blockers.append("NO_REAL_HUMAN_APPROVAL_FORM")
    if not _as_bool(approval.get("production_metadata_registry_accepted")):
        blockers.append("PRODUCTION_REGISTRY_NOT_ACCEPTED_FOR_REAL")
    if _as_bool(approval.get("simulation_only")):
        blockers.append("SIMULATION_ONLY_APPROVAL_IS_NOT_REAL_APPROVAL")
    if _as_bool(approval.get("accepted_context_is_preview_only")):
        blockers.append("ACCEPTED_CONTEXT_PREVIEW_ONLY")
    if not _as_bool(approval.get("real_approval")):
        blockers.append("NO_REAL_HUMAN_APPROVAL_FORM")
    return blockers


def _lifecycle_blockers(lifecycle: Mapping[str, Any]) -> list[str]:
    blockers: list[str] = []
    state = _as_text(lifecycle.get("lifecycle_state"))
    if state in {"NO_REAL_APPROVAL", "PREVIEW_GENERATED_NOT_ENABLED", "PREFLIGHT_BLOCKED"}:
        blockers.append("PREVIEW_PREFLIGHT_NOT_ENABLEMENT")
    if state != "READY_FOR_OPERATOR_ENABLEMENT_REVIEW":
        blockers.append("SEPARATE_ENABLEMENT_PHASE_REQUIRED")
    return blockers


def _preflight_blockers(preflight: Mapping[str, Any]) -> list[str]:
    blockers: list[str] = []
    if not _as_bool(preflight.get("runtime_enablement_ready")):
        blockers.append("RUNTIME_PREFLIGHT_BLOCKED")
    if not _as_bool(preflight.get("operator_signoff")):
        blockers.append("OPERATOR_SIGNOFF_MISSING")
    return blockers


def _dry_run_blockers(dry_run: Mapping[str, Any]) -> list[str]:
    blockers: list[str] = []
    if not _as_bool(dry_run.get("dry_run_config_preview_is_no_op")):
        blockers.append("DRY_RUN_ONLY_NOT_PRODUCTION")
    if _as_bool(dry_run.get("dry_run_modified_production_config")):
        blockers.append("PRODUCTION_CONFIG_CHANGE_NOT_ALLOWED_IN_THIS_PHASE")
    if not _as_bool(dry_run.get("historical_backfill_disabled")):
        blockers.append("HISTORICAL_BACKFILL_DISABLED")
    if not _as_bool(dry_run.get("ui_gate_passed")):
        blockers.append("UI_GATE_NOT_PASSED")
    if _as_bool(dry_run.get("production_migration_blocked")):
        blockers.append("PRODUCTION_MIGRATION_BLOCKED")
    return blockers


def identify_strategy_replay_enablement_blockers(
    approval_summary: Mapping[str, Any] | None,
    lifecycle_summary: Mapping[str, Any] | None,
    preflight_summary: Mapping[str, Any] | None,
    dry_run_summary: Mapping[str, Any] | None,
    boundary_summary: Mapping[str, Any] | None,
) -> list[str]:
    approval = _normalize_mapping(approval_summary)
    lifecycle = _normalize_mapping(lifecycle_summary)
    preflight = _normalize_mapping(preflight_summary)
    dry_run = _normalize_mapping(dry_run_summary)
    boundary = _normalize_mapping(boundary_summary)

    blockers: list[str] = []
    blockers.extend(_approval_blockers(approval))
    blockers.extend(_lifecycle_blockers(lifecycle))
    blockers.extend(_preflight_blockers(preflight))
    blockers.extend(_dry_run_blockers(dry_run))
    if _as_text(boundary.get("boundary_state")) != GO_READY_FOR_SEPARATE_ENABLEMENT_PHASE:
        blockers.append("SEPARATE_ENABLEMENT_PHASE_REQUIRED")

    deduped: list[str] = []
    for blocker in blockers:
        if blocker and blocker not in deduped:
            deduped.append(blocker)
    return deduped


def build_strategy_replay_phase_status_table(
    approval_summary: Mapping[str, Any] | None,
    lifecycle_summary: Mapping[str, Any] | None,
    preflight_summary: Mapping[str, Any] | None,
    dry_run_summary: Mapping[str, Any] | None,
    boundary_summary: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    approval = _normalize_mapping(approval_summary)
    lifecycle = _normalize_mapping(lifecycle_summary)
    preflight = _normalize_mapping(preflight_summary)
    dry_run = _normalize_mapping(dry_run_summary)
    boundary = _normalize_mapping(boundary_summary)

    return [
        {
            "phase": "approval",
            "state": "REAL_APPROVAL_ACCEPTED" if _as_bool(approval.get("production_metadata_registry_accepted")) else "NO_REAL_APPROVAL",
            "status": "pass" if _as_bool(approval.get("production_metadata_registry_accepted")) else "blocked",
        },
        {
            "phase": "preview_lifecycle",
            "state": _as_text(lifecycle.get("lifecycle_state")) or "NO_REAL_APPROVAL",
            "status": "pass" if _as_text(lifecycle.get("lifecycle_state")) == "READY_FOR_OPERATOR_ENABLEMENT_REVIEW" else "blocked",
        },
        {
            "phase": "runtime_preflight",
            "state": "READY" if _as_bool(preflight.get("runtime_enablement_ready")) else "BLOCKED",
            "status": "pass" if _as_bool(preflight.get("runtime_enablement_ready")) else "blocked",
        },
        {
            "phase": "dry_run",
            "state": "NO_OP" if _as_bool(dry_run.get("dry_run_config_preview_is_no_op")) else "NOT_NO_OP",
            "status": "pass" if _as_bool(dry_run.get("dry_run_config_preview_is_no_op")) else "blocked",
        },
        {
            "phase": "boundary",
            "state": _as_text(boundary.get("boundary_state")) or NO_GO,
            "status": "pass" if _as_text(boundary.get("boundary_state")) == GO_READY_FOR_SEPARATE_ENABLEMENT_PHASE else "blocked",
        },
    ]


def classify_strategy_replay_next_action(
    approval_summary: Mapping[str, Any] | None,
    lifecycle_summary: Mapping[str, Any] | None,
    preflight_summary: Mapping[str, Any] | None,
    dry_run_summary: Mapping[str, Any] | None,
    boundary_summary: Mapping[str, Any] | None,
) -> str:
    boundary = _normalize_mapping(boundary_summary)
    lifecycle = _normalize_mapping(lifecycle_summary)
    preflight = _normalize_mapping(preflight_summary)
    approval = _normalize_mapping(approval_summary)
    dry_run = _normalize_mapping(dry_run_summary)

    if not _as_bool(approval.get("real_approval_intake_accepted") or approval.get("accepted")):
        return "Collect a real human approval form before any enablement review."
    if _as_bool(approval.get("simulation_only")):
        return "Replace simulation-only artifacts with a real approval form."
    if _as_text(lifecycle.get("lifecycle_state")) == "NO_REAL_APPROVAL":
        return "Collect a real human approval form before any enablement review."
    if not _as_bool(dry_run.get("dry_run_config_preview_is_no_op")):
        return "Keep the dry-run preview no-op and separate it from production config changes."
    if _as_text(boundary.get("boundary_state")) == GO_READY_FOR_SEPARATE_ENABLEMENT_PHASE:
        return "Move to a separate explicit enablement phase; do not change production config in this dashboard phase."
    if not _as_bool(preflight.get("runtime_enablement_ready")):
        return "Resolve runtime preflight blockers and keep operator sign-off separate."
    return "Keep preview, dry-run, and enablement separated; production actions remain blocked."


def build_strategy_replay_enablement_status(
    approval_summary: Mapping[str, Any] | None,
    lifecycle_summary: Mapping[str, Any] | None,
    preflight_summary: Mapping[str, Any] | None,
    dry_run_summary: Mapping[str, Any] | None,
    boundary_summary: Mapping[str, Any] | None,
) -> dict[str, Any]:
    approval = _normalize_mapping(approval_summary)
    lifecycle = _normalize_mapping(lifecycle_summary)
    preflight = _normalize_mapping(preflight_summary)
    dry_run = _normalize_mapping(dry_run_summary)
    boundary = _normalize_mapping(boundary_summary)

    production_metadata_registry_accepted_for_real = _as_bool(approval.get("production_metadata_registry_accepted"))
    real_human_approval_exists = _as_bool(approval.get("real_approval_intake_accepted") or approval.get("accepted"))
    accepted_context_preview_exists = approval.get("acceptance_context_preview") is not None or _as_bool(lifecycle.get("accepted_context_is_preview_only"))
    accepted_context_preview_is_production_enablement = False
    runtime_preflight_passed = _as_bool(preflight.get("runtime_enablement_ready"))
    runtime_dry_run_passed = _as_bool(dry_run.get("dry_run_result_passed"))
    dry_run_config_preview_is_no_op = _as_bool(dry_run.get("dry_run_config_preview_is_no_op"))

    blockers = identify_strategy_replay_enablement_blockers(approval, lifecycle, preflight, dry_run, boundary)
    phase_status = _derive_phase_status(boundary, lifecycle)
    next_action = classify_strategy_replay_next_action(approval, lifecycle, preflight, dry_run, boundary)

    return {
        "phase_status": phase_status,
        "blockers": blockers,
        "next_action": next_action,
        "production_actions_allowed": False,
        "human_action_required": True,
        "source_reports": [
            "00-BettingPlan/20260510/strategy_replay_production_enablement_phase_boundary_report.md",
            "00-BettingPlan/20260510/strategy_replay_runtime_enablement_operator_handoff_binder.md",
            "00-BettingPlan/20260510/strategy_replay_real_approval_intake_report.md",
            "00-BettingPlan/20260510/strategy_replay_accepted_context_preview_lifecycle_report.md",
            "00-BettingPlan/20260510/strategy_replay_runtime_enablement_dry_run_report.md",
            "00-BettingPlan/20260510/strategy_replay_metadata_registry_acceptance_gate_report.md",
        ],
        "final_marker": "P39_STRATEGY_REPLAY_ENABLEMENT_STATUS_DASHBOARD_READY",
        "phase_status_table": build_strategy_replay_phase_status_table(approval, lifecycle, preflight, dry_run, boundary),
        "summary": {
            "production_metadata_registry_accepted_for_real": production_metadata_registry_accepted_for_real,
            "real_human_approval_exists": real_human_approval_exists,
            "accepted_context_preview_exists": accepted_context_preview_exists,
            "accepted_context_preview_is_production_enablement": accepted_context_preview_is_production_enablement,
            "runtime_preflight_passed": runtime_preflight_passed,
            "runtime_dry_run_passed": runtime_dry_run_passed,
            "dry_run_config_preview_is_no_op": dry_run_config_preview_is_no_op,
            "runtime_production_enablement_can_start": False,
            "runtime_config_change_can_start": False,
            "ui_can_start": False,
            "production_migration_can_start": False,
            "separate_enablement_phase_required": True,
        },
    }


def summarize_strategy_replay_enablement_dashboard(dashboard: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = dict(dashboard or {})
    summary = dict(payload.get("summary") or {})
    return {
        "phase_status": _as_text(payload.get("phase_status")) or NO_GO,
        "blocker_count": len(list(payload.get("blockers") or [])),
        "blockers": _as_text_list(payload.get("blockers")),
        "next_action": _as_text(payload.get("next_action")),
        "production_actions_allowed": _as_bool(payload.get("production_actions_allowed")),
        "human_action_required": _as_bool(payload.get("human_action_required")),
        "production_metadata_registry_accepted_for_real": _as_bool(summary.get("production_metadata_registry_accepted_for_real")),
        "real_human_approval_exists": _as_bool(summary.get("real_human_approval_exists")),
        "accepted_context_preview_exists": _as_bool(summary.get("accepted_context_preview_exists")),
        "accepted_context_preview_is_production_enablement": _as_bool(summary.get("accepted_context_preview_is_production_enablement")),
        "runtime_preflight_passed": _as_bool(summary.get("runtime_preflight_passed")),
        "runtime_dry_run_passed": _as_bool(summary.get("runtime_dry_run_passed")),
        "dry_run_config_preview_is_no_op": _as_bool(summary.get("dry_run_config_preview_is_no_op")),
        "runtime_production_enablement_can_start": _as_bool(summary.get("runtime_production_enablement_can_start")),
        "runtime_config_change_can_start": _as_bool(summary.get("runtime_config_change_can_start")),
        "ui_can_start": _as_bool(summary.get("ui_can_start")),
        "production_migration_can_start": _as_bool(summary.get("production_migration_can_start")),
        "separate_enablement_phase_required": _as_bool(summary.get("separate_enablement_phase_required")),
        "final_marker": _as_text(payload.get("final_marker")),
    }