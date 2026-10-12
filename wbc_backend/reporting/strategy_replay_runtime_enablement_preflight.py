"""Pure runtime enablement preflight checks for Strategy Replay."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return _as_text(value).lower() in {"1", "true", "yes", "y", "on"}


def _as_text_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [_as_text(item) for item in value if _as_text(item)]
    if isinstance(value, tuple):
        return [_as_text(item) for item in value if _as_text(item)]
    text = _as_text(value)
    return [text] if text else []


def _normalize_context(runtime_preflight_context: Mapping[str, Any] | None) -> dict[str, Any]:
    context = dict(runtime_preflight_context or {})
    return {
        "accepted_registry_path": _as_text(context.get("accepted_registry_path")),
        "accepted_acceptance_context_path": _as_text(context.get("accepted_acceptance_context_path")),
        "acceptance_gate_passed": _as_bool(context.get("acceptance_gate_passed")),
        "acceptance_gate_pass_evidence_refs": _as_text_list(context.get("acceptance_gate_pass_evidence_refs")),
        "runtime_metadata_registry_path": _as_text(context.get("runtime_metadata_registry_path")),
        "runtime_metadata_registry_path_configured_explicitly": _as_bool(
            context.get("runtime_metadata_registry_path_configured_explicitly")
        ),
        "strict_mode_enabled": _as_bool(context.get("strict_mode_enabled")),
        "non_strict_fallback_allowed": _as_bool(context.get("non_strict_fallback_allowed")),
        "rollback_switch_available": _as_bool(context.get("rollback_switch_available")),
        "fixture_validation_rerun_passed": _as_bool(context.get("fixture_validation_rerun_passed")),
        "synthetic_future_row_dry_run_passed": _as_bool(context.get("synthetic_future_row_dry_run_passed")),
        "historical_backfill_disabled": _as_bool(context.get("historical_backfill_disabled")),
        "production_ui_launch_blocked": _as_bool(context.get("production_ui_launch_blocked")),
        "production_migration_blocked": _as_bool(context.get("production_migration_blocked")),
        "monitoring_audit_log_plan_ready": _as_bool(context.get("monitoring_audit_log_plan_ready")),
        "operator_signoff": _as_bool(context.get("operator_signoff")),
    }


def _gate_blockers(gate: Mapping[str, Any]) -> list[str]:
    blockers: list[str] = []
    if not _as_bool(gate.get("production_metadata_registry_accepted") or gate.get("accepted")):
        blockers.append("accepted registry gate must pass")
    return blockers


def _context_blockers(context: Mapping[str, Any]) -> list[str]:
    blockers: list[str] = []
    for field_name, message in (
        ("accepted_registry_path", "accepted_registry_path is required"),
        ("accepted_acceptance_context_path", "accepted_acceptance_context_path is required"),
        ("acceptance_gate_pass_evidence_refs", "acceptance_gate_pass_evidence_refs must not be empty"),
        ("runtime_metadata_registry_path", "runtime_metadata_registry_path is required"),
    ):
        if not context[field_name]:
            blockers.append(message)

    for field_name, message in (
        ("acceptance_gate_passed", "acceptance_gate_passed must be true"),
        ("runtime_metadata_registry_path_configured_explicitly", "runtime_metadata_registry_path must be configured explicitly"),
        ("strict_mode_enabled", "strict_mode_enabled must be true"),
        ("rollback_switch_available", "rollback_switch_available must be true"),
        ("fixture_validation_rerun_passed", "fixture_validation_rerun_passed must be true"),
        ("synthetic_future_row_dry_run_passed", "synthetic_future_row_dry_run_passed must be true"),
        ("historical_backfill_disabled", "historical_backfill_disabled must be true"),
        ("production_ui_launch_blocked", "production_ui_launch_blocked must be true"),
        ("production_migration_blocked", "production_migration_blocked must be true"),
        ("monitoring_audit_log_plan_ready", "monitoring_audit_log_plan_ready must be true"),
        ("operator_signoff", "operator_signoff must be true"),
    ):
        if not context[field_name]:
            blockers.append(message)

    if context["non_strict_fallback_allowed"]:
        blockers.append("non_strict_fallback_allowed must be false")
    return blockers


def identify_runtime_enablement_blockers(
    registry_acceptance_gate_result: Mapping[str, Any] | None,
    runtime_preflight_context: Mapping[str, Any] | None,
) -> list[str]:
    gate = dict(registry_acceptance_gate_result or {})
    context = _normalize_context(runtime_preflight_context)

    blockers = _gate_blockers(gate)
    blockers.extend(_context_blockers(context))

    deduped: list[str] = []
    for blocker in blockers:
        if blocker and blocker not in deduped:
            deduped.append(blocker)
    return deduped


def build_runtime_enablement_checklist(
    registry_acceptance_gate_result: Mapping[str, Any] | None,
    runtime_preflight_context: Mapping[str, Any] | None,
) -> dict[str, Any]:
    context = _normalize_context(runtime_preflight_context)
    gate = dict(registry_acceptance_gate_result or {})
    blockers = identify_runtime_enablement_blockers(gate, context)

    checklist = [
        {"check": "accepted_registry_gate", "passed": _as_bool(gate.get("production_metadata_registry_accepted") or gate.get("accepted")), "required": True},
        {"check": "accepted_registry_path", "passed": bool(context["accepted_registry_path"]), "required": True},
        {"check": "accepted_acceptance_context_path", "passed": bool(context["accepted_acceptance_context_path"]), "required": True},
        {"check": "acceptance_gate_passed", "passed": context["acceptance_gate_passed"], "required": True},
        {"check": "acceptance_gate_pass_evidence_refs", "passed": bool(context["acceptance_gate_pass_evidence_refs"]), "required": True},
        {"check": "runtime_metadata_registry_path", "passed": bool(context["runtime_metadata_registry_path"]), "required": True},
        {"check": "runtime_metadata_registry_path_configured_explicitly", "passed": context["runtime_metadata_registry_path_configured_explicitly"], "required": True},
        {"check": "strict_mode_enabled", "passed": context["strict_mode_enabled"], "required": True},
        {"check": "non_strict_fallback_allowed", "passed": not context["non_strict_fallback_allowed"], "required": True},
        {"check": "rollback_switch_available", "passed": context["rollback_switch_available"], "required": True},
        {"check": "fixture_validation_rerun_passed", "passed": context["fixture_validation_rerun_passed"], "required": True},
        {"check": "synthetic_future_row_dry_run_passed", "passed": context["synthetic_future_row_dry_run_passed"], "required": True},
        {"check": "historical_backfill_disabled", "passed": context["historical_backfill_disabled"], "required": True},
        {"check": "production_ui_launch_blocked", "passed": context["production_ui_launch_blocked"], "required": True},
        {"check": "production_migration_blocked", "passed": context["production_migration_blocked"], "required": True},
        {"check": "monitoring_audit_log_plan_ready", "passed": context["monitoring_audit_log_plan_ready"], "required": True},
        {"check": "operator_signoff", "passed": context["operator_signoff"], "required": True},
    ]

    preflight_ready = not blockers and all(item["passed"] for item in checklist)
    return {
        "runtime_enablement_ready": preflight_ready,
        "blockers": blockers,
        "blocker_count": len(blockers),
        "checklist": checklist,
        "context": context,
        "registry_acceptance_gate_result": gate,
    }


def evaluate_runtime_enablement_preflight(
    registry_acceptance_gate_result: Mapping[str, Any] | None,
    runtime_preflight_context: Mapping[str, Any] | None,
) -> dict[str, Any]:
    return build_runtime_enablement_checklist(registry_acceptance_gate_result, runtime_preflight_context)


def summarize_runtime_enablement_preflight(gate_result: Mapping[str, Any] | None) -> dict[str, Any]:
    gate = dict(gate_result or {})
    context = gate.get("context") if isinstance(gate.get("context"), Mapping) else {}
    return {
        "runtime_enablement_ready": _as_bool(gate.get("runtime_enablement_ready")),
        "blocker_count": len(list(gate.get("blockers") or [])),
        "blockers": list(gate.get("blockers") or []),
        "accepted_registry_path": _as_text(context.get("accepted_registry_path")) if isinstance(context, Mapping) else "",
        "runtime_metadata_registry_path": _as_text(context.get("runtime_metadata_registry_path")) if isinstance(context, Mapping) else "",
        "strict_mode_enabled": _as_bool(context.get("strict_mode_enabled")) if isinstance(context, Mapping) else False,
        "non_strict_fallback_allowed": _as_bool(context.get("non_strict_fallback_allowed")) if isinstance(context, Mapping) else False,
        "operator_signoff": _as_bool(context.get("operator_signoff")) if isinstance(context, Mapping) else False,
    }
