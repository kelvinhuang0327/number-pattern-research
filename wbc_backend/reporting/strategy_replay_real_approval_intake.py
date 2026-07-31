"""Pure intake validation for Strategy Replay real approval forms."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from wbc_backend.reporting.strategy_replay_metadata_registry_acceptance import evaluate_metadata_registry_acceptance
from wbc_backend.reporting.strategy_replay_runtime_enablement_preflight import evaluate_runtime_enablement_preflight


REAL_TEMPLATE_PATH = (
    "/Users/kelvin/Kelvin-WorkSpace/Betting-pool/00-BettingPlan/20260510/"
    "strategy_replay_metadata_registry_acceptance_context.REAL_APPROVAL_TEMPLATE.json"
)
REVIEW_READY_CONTEXT_PATH = (
    "/Users/kelvin/Kelvin-WorkSpace/Betting-pool/00-BettingPlan/20260510/"
    "strategy_replay_metadata_registry_acceptance_context.review_ready.draft.json"
)


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


def _normalize_form(form: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = dict(form or {})
    return {
        "artifact_kind": _as_text(payload.get("artifact_kind")).upper(),
        "reviewer": _as_text(payload.get("reviewer")),
        "approval_timestamp": _as_text(payload.get("approval_timestamp")),
        "explicit_human_approval": _as_bool(payload.get("explicit_human_approval")),
        "approval_decision": _as_text(payload.get("approval_decision")).upper(),
        "approval_reason": _as_text(payload.get("approval_reason")),
        "rollback_plan_ref": _as_text(payload.get("rollback_plan_ref")),
        "reviewed_registry_path": _as_text(payload.get("reviewed_registry_path")),
        "reviewed_acceptance_context_path": _as_text(payload.get("reviewed_acceptance_context_path")),
        "reviewed_evidence_pack_path": _as_text(payload.get("reviewed_evidence_pack_path")),
        "reviewed_test_results": _as_text_list(payload.get("reviewed_test_results")),
        "reviewer_notes": _as_text(payload.get("reviewer_notes")),
        "real_approval": _as_bool(payload.get("real_approval")),
        "simulation_only": _as_bool(payload.get("simulation_only")),
        "review_status": _as_text(payload.get("review_status")),
        "production_enablement_allowed": _as_bool(payload.get("production_enablement_allowed")),
        "runtime_config_change_allowed": _as_bool(payload.get("runtime_config_change_allowed")),
        "ui_launch_allowed": _as_bool(payload.get("ui_launch_allowed")),
        "production_migration_allowed": _as_bool(payload.get("production_migration_allowed")),
        "production_metadata_registry_accepted": _as_bool(payload.get("production_metadata_registry_accepted")),
    }


def _base_context_preview(base_context: Mapping[str, Any] | None) -> dict[str, Any]:
    context = dict(base_context or {})
    preview = dict(context)
    preview.setdefault("production_enablement_allowed", False)
    preview.setdefault("runtime_config_change_allowed", False)
    preview.setdefault("ui_launch_allowed", False)
    preview.setdefault("production_migration_allowed", False)
    preview.setdefault("operator_signoff", False)
    preview.setdefault("real_approval", False)
    preview.setdefault("production_metadata_registry_accepted", False)
    return preview


def _artifact_kind_blockers(approval_form: Mapping[str, Any]) -> list[str]:
    blockers: list[str] = []

    if approval_form["artifact_kind"] == "SIMULATION_ONLY" or approval_form["simulation_only"]:
        blockers.append("simulation-only approval form is rejected by real intake")

    if not approval_form["real_approval"]:
        blockers.append("real_approval must be true")
    return blockers


def _identity_blockers(approval_form: Mapping[str, Any]) -> list[str]:
    blockers: list[str] = []
    if not approval_form["reviewer"] or approval_form["reviewer"] in {"TBD_REAL_REVIEWER", "TBD"}:
        blockers.append("reviewer is required and must not be TBD")
    if not approval_form["approval_timestamp"]:
        blockers.append("approval_timestamp is required")
    if not approval_form["explicit_human_approval"]:
        blockers.append("explicit_human_approval must be true")
    if approval_form["approval_decision"] != "APPROVE":
        blockers.append("approval_decision must be APPROVE")
    if not approval_form["approval_reason"]:
        blockers.append("approval_reason is required")
    if not approval_form["rollback_plan_ref"]:
        blockers.append("rollback_plan_ref is required")
    return blockers


def _review_target_blockers(approval_form: Mapping[str, Any]) -> list[str]:
    blockers: list[str] = []
    if not approval_form["reviewed_registry_path"]:
        blockers.append("reviewed_registry_path is required")
    if approval_form["reviewed_registry_path"] and approval_form["reviewed_registry_path"] != (
        "/Users/kelvin/Kelvin-WorkSpace/Betting-pool/00-BettingPlan/20260510/"
        "strategy_replay_metadata_registry.production_candidate.draft.json"
    ):
        blockers.append("reviewed_registry_path must match the production candidate registry")
    if approval_form["reviewed_acceptance_context_path"] not in {REAL_TEMPLATE_PATH, REVIEW_READY_CONTEXT_PATH}:
        blockers.append("reviewed_acceptance_context_path must match the real template or review-ready context")
    if not approval_form["reviewed_evidence_pack_path"]:
        blockers.append("reviewed_evidence_pack_path is required")
    if not approval_form["reviewed_test_results"]:
        blockers.append("reviewed_test_results must be present")
    return blockers


def _control_blockers(approval_form: Mapping[str, Any]) -> list[str]:
    blockers: list[str] = []
    if approval_form["production_enablement_allowed"]:
        blockers.append("production_enablement_allowed must remain false during intake")
    if approval_form["runtime_config_change_allowed"]:
        blockers.append("runtime_config_change_allowed must remain false during intake")
    if approval_form["ui_launch_allowed"]:
        blockers.append("ui_launch_allowed must remain false during intake")
    if approval_form["production_migration_allowed"]:
        blockers.append("production_migration_allowed must remain false during intake")
    if approval_form["production_metadata_registry_accepted"]:
        blockers.append("production_metadata_registry_accepted must remain false during intake")
    return blockers


def identify_real_approval_form_blockers(form: Mapping[str, Any] | None) -> list[str]:
    approval_form = _normalize_form(form)
    blockers: list[str] = []
    blockers.extend(_artifact_kind_blockers(approval_form))
    blockers.extend(_identity_blockers(approval_form))
    blockers.extend(_review_target_blockers(approval_form))
    blockers.extend(_control_blockers(approval_form))

    deduped: list[str] = []
    for blocker in blockers:
        if blocker and blocker not in deduped:
            deduped.append(blocker)
    return deduped


def validate_real_approval_form(form: Mapping[str, Any] | None) -> dict[str, Any]:
    approval_form = _normalize_form(form)
    blockers = identify_real_approval_form_blockers(approval_form)
    accepted = not blockers
    return {
        "real_approval_intake_accepted": accepted,
        "accepted": accepted,
        "blockers": blockers,
        "blocker_count": len(blockers),
        "approval_form": approval_form,
    }


def build_acceptance_context_from_real_approval(
    form: Mapping[str, Any] | None,
    base_context: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    validation = validate_real_approval_form(form)
    if not validation["accepted"]:
        return None

    approval_form = validation["approval_form"]
    context = _base_context_preview(base_context)
    context.update(
        {
            "reviewer": approval_form["reviewer"],
            "approval_timestamp": approval_form["approval_timestamp"],
            "explicit_human_approval": True,
            "approval_decision": approval_form["approval_decision"],
            "approval_reason": approval_form["approval_reason"],
            "rollback_plan_ref": approval_form["rollback_plan_ref"],
            "reviewed_registry_path": approval_form["reviewed_registry_path"],
            "reviewed_acceptance_context_path": approval_form["reviewed_acceptance_context_path"],
            "reviewed_evidence_pack_path": approval_form["reviewed_evidence_pack_path"],
            "reviewed_test_results": approval_form["reviewed_test_results"],
            "reviewer_notes": approval_form["reviewer_notes"],
            "real_approval": True,
            "review_status": approval_form["review_status"] or "real_approval_intake_preview",
            "production_enablement_allowed": False,
            "runtime_config_change_allowed": False,
            "ui_launch_allowed": False,
            "production_migration_allowed": False,
            "production_metadata_registry_accepted": False,
            "operator_signoff": False,
        }
    )
    return context


def evaluate_real_approval_intake(
    form: Mapping[str, Any] | None,
    candidate_registry: Mapping[str, Any] | None,
    base_context: Mapping[str, Any] | None,
) -> dict[str, Any]:
    validation = validate_real_approval_form(form)
    preview_context = build_acceptance_context_from_real_approval(form, base_context)
    registry = dict(candidate_registry or {})
    records = registry.get("records") if isinstance(registry.get("records"), Sequence) else []

    if preview_context is not None:
        acceptance_gate_result = evaluate_metadata_registry_acceptance(records, preview_context)
        runtime_preflight_result = evaluate_runtime_enablement_preflight(acceptance_gate_result, preview_context)
    else:
        fallback_context = _base_context_preview(base_context)
        acceptance_gate_result = evaluate_metadata_registry_acceptance(records, fallback_context)
        runtime_preflight_result = evaluate_runtime_enablement_preflight(acceptance_gate_result, fallback_context)

    return {
        **validation,
        "acceptance_context_preview": preview_context,
        "acceptance_gate_result": acceptance_gate_result,
        "runtime_enablement_preflight_result": runtime_preflight_result,
        "production_metadata_registry_accepted": bool(acceptance_gate_result.get("accepted")),
        "runtime_production_enablement_can_start": bool(runtime_preflight_result.get("runtime_enablement_ready")),
        "ui_can_start": False,
        "production_migration_can_start": False,
    }


def summarize_real_approval_intake(result: Mapping[str, Any] | None) -> dict[str, Any]:
    intake = dict(result or {})
    preview_context = intake.get("acceptance_context_preview") if isinstance(intake.get("acceptance_context_preview"), Mapping) else {}
    acceptance_gate_result = intake.get("acceptance_gate_result") if isinstance(intake.get("acceptance_gate_result"), Mapping) else {}
    runtime_preflight_result = intake.get("runtime_enablement_preflight_result") if isinstance(intake.get("runtime_enablement_preflight_result"), Mapping) else {}
    return {
        "real_approval_intake_accepted": _as_bool(intake.get("real_approval_intake_accepted") or intake.get("accepted")),
        "blocker_count": len(list(intake.get("blockers") or [])),
        "blockers": list(intake.get("blockers") or []),
        "production_metadata_registry_accepted": _as_bool(intake.get("production_metadata_registry_accepted") or acceptance_gate_result.get("accepted")),
        "runtime_production_enablement_can_start": _as_bool(intake.get("runtime_production_enablement_can_start") or runtime_preflight_result.get("runtime_enablement_ready")),
        "ui_can_start": _as_bool(intake.get("ui_can_start")),
        "production_migration_can_start": _as_bool(intake.get("production_migration_can_start")),
        "reviewer": _as_text(preview_context.get("reviewer")) if isinstance(preview_context, Mapping) else "",
        "approval_timestamp": _as_text(preview_context.get("approval_timestamp")) if isinstance(preview_context, Mapping) else "",
        "reviewed_registry_path": _as_text(preview_context.get("reviewed_registry_path")) if isinstance(preview_context, Mapping) else "",
    }