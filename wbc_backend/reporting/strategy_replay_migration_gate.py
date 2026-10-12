"""Read-only small-batch migration gate for Strategy Replay backfill."""
from __future__ import annotations

from typing import Any

from wbc_backend.reporting.strategy_replay_backfill_write_plan import validate_write_plan

READYNESS_LEVEL_BACKFILL_REQUIRED = "BACKFILL_REQUIRED"
READYNESS_LEVEL_UI_MVP_READY = "UI_MVP_READY"


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def _as_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _list_of_text(values: object) -> list[str]:
    if not isinstance(values, list):
        return []
    tokens: list[str] = []
    for value in values:
        text = _as_text(value)
        if text and text not in tokens:
            tokens.append(text)
    return tokens


def _plan_payload(write_plan_summary: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(write_plan_summary, dict):
        return {"summary": {}, "write_plan_items": []}

    summary = write_plan_summary.get("summary")
    if not isinstance(summary, dict):
        summary = {}

    write_plan_items = write_plan_summary.get("write_plan_items")
    if not isinstance(write_plan_items, list):
        write_plan_items = []

    return {
        "summary": summary,
        "write_plan_items": [item for item in write_plan_items if isinstance(item, dict)],
        "rollback_plan": write_plan_summary.get("rollback_plan") if isinstance(write_plan_summary.get("rollback_plan"), list) else None,
    }


def _readiness_level(readiness_summary: dict[str, Any] | None) -> str:
    if not isinstance(readiness_summary, dict):
        return READYNESS_LEVEL_BACKFILL_REQUIRED
    readiness_level = _as_text(readiness_summary.get("readiness_level"))
    return readiness_level or READYNESS_LEVEL_BACKFILL_REQUIRED


def _human_approval_required(_: dict[str, Any] | None) -> list[str]:
    return ["human_approval"]


def _manifest_valid(approval_manifest_summary: dict[str, Any] | None) -> bool:
    if not isinstance(approval_manifest_summary, dict):
        return False
    if "valid" in approval_manifest_summary:
        return _as_bool(approval_manifest_summary.get("valid"))
    if "manifest_valid" in approval_manifest_summary:
        return _as_bool(approval_manifest_summary.get("manifest_valid"))
    return False


def _manifest_errors(approval_manifest_summary: dict[str, Any] | None) -> list[str]:
    if not isinstance(approval_manifest_summary, dict):
        return ["approval manifest must be valid"]

    errors = _list_of_text(approval_manifest_summary.get("errors"))
    if errors:
        return errors
    return _list_of_text(approval_manifest_summary.get("manifest_errors"))


def _p0_unsafe_fields_unresolved(approval_manifest_summary: dict[str, Any] | None) -> list[str]:
    if not isinstance(approval_manifest_summary, dict):
        return []

    explicit_fields = _list_of_text(approval_manifest_summary.get("p0_unsafe_fields_unresolved"))
    if explicit_fields:
        return explicit_fields

    if isinstance(approval_manifest_summary.get("unsafe_to_infer_fields"), list):
        return _list_of_text(approval_manifest_summary.get("unsafe_to_infer_fields"))

    proposal_items = approval_manifest_summary.get("proposal_items")
    if not isinstance(proposal_items, list):
        return []

    unresolved: list[str] = []
    for item in proposal_items:
        if not isinstance(item, dict):
            continue
        status = _as_text(item.get("status") or item.get("review_decision"))
        if status not in {"REVIEW_REQUIRED", "REJECTED"}:
            continue
        for field_name in _list_of_text(item.get("unsafe_to_infer_fields")):
            if field_name not in unresolved:
                unresolved.append(field_name)
    return unresolved


def _append_manifest_gate_reasons(reasons: list[str], approval_manifest_summary: dict[str, Any] | None) -> None:
    if not _manifest_valid(approval_manifest_summary):
        reasons.append("approval manifest must be valid")

    manifest_errors = _manifest_errors(approval_manifest_summary)
    if manifest_errors:
        reasons.append("approval manifest contains validation errors")

    unresolved_fields = _p0_unsafe_fields_unresolved(approval_manifest_summary)
    if unresolved_fields:
        reasons.append("P0 unsafe fields remain unresolved: " + ", ".join(unresolved_fields))


def _append_write_plan_gate_reasons(reasons: list[str], write_plan_summary: dict[str, Any] | None) -> list[dict[str, Any]]:
    plan_payload = _plan_payload(write_plan_summary)
    plan_summary = plan_payload["summary"]
    plan_items = plan_payload["write_plan_items"]

    if not plan_items:
        reasons.append("write plan must contain at least one planned item")

    if _as_bool(plan_summary.get("dry_run_only")) is not True:
        reasons.append("write plan must be dry_run_only")

    if plan_items and _as_int(plan_summary.get("write_ready_count"), len(plan_items)) != len(plan_items):
        reasons.append("all write-plan items must be WRITE_READY")

    if _as_int(plan_summary.get("rejected_count"), 0) > 0:
        reasons.append("write plan contains rejected items")

    return plan_items


def _append_fixture_gate_reasons(reasons: list[str], fixture_apply_summary: dict[str, Any] | None, planned_item_count: int) -> None:
    fixture_summary = fixture_apply_summary if isinstance(fixture_apply_summary, dict) else {}
    if _as_bool(fixture_summary.get("dry_run_only")) is not True:
        reasons.append("fixture apply must be dry_run_only")
    if _as_bool(fixture_summary.get("mutation_allowed")):
        reasons.append("fixture apply must not allow mutation")
    if _as_int(fixture_summary.get("skipped_count"), 0) > 0:
        reasons.append("planned write items must not be skipped")

    applied_count = _as_int(fixture_summary.get("applied_count"), 0)
    if planned_item_count > 0 and applied_count != planned_item_count:
        reasons.append("fixture apply must apply every planned write item")


def _append_run_gate_reasons(
    reasons: list[str],
    fixture_apply_summary: dict[str, Any] | None,
    write_plan_summary: dict[str, Any] | None,
    approval_manifest_summary: dict[str, Any] | None,
    *,
    human_approved: bool,
) -> tuple[list[dict[str, Any]], list[str]]:
    _append_manifest_gate_reasons(reasons, approval_manifest_summary)
    plan_items = _append_write_plan_gate_reasons(reasons, write_plan_summary)
    _append_fixture_gate_reasons(reasons, fixture_apply_summary, len(plan_items))

    rollback_plan = build_migration_rollback_plan(write_plan_summary)
    if not rollback_plan:
        reasons.append("rollback plan must exist")

    if not human_approved:
        reasons.append("human approval flag must be explicitly true")

    return plan_items, rollback_plan


def _all_write_plan_items_ready(write_plan_summary: dict[str, Any] | None) -> bool:
    payload = _plan_payload(write_plan_summary)
    items = payload["write_plan_items"]
    summary = payload["summary"]

    if not items:
        return False
    if _as_int(summary.get("write_ready_count"), 0) != len(items):
        return False
    if _as_int(summary.get("rejected_count"), 0) != 0:
        return False
    if _as_bool(summary.get("dry_run_only")) is not True:
        return False

    validation = validate_write_plan({"summary": summary, "write_plan_items": items})
    return bool(validation["valid"])


def build_migration_rollback_plan(write_plan_summary: dict[str, Any] | None) -> list[str]:
    payload = _plan_payload(write_plan_summary)
    explicit_plan = payload.get("rollback_plan")
    if isinstance(explicit_plan, list):
        return _list_of_text(explicit_plan)

    items = payload["write_plan_items"]
    if not items:
        return []

    candidate_ids = [
        _as_text(item.get("candidate_id"))
        for item in items
        if isinstance(item, dict) and _as_text(item.get("candidate_id"))
    ]

    plan = [
        "Keep the pre-apply fixture snapshot and the approved write plan artifact.",
        "Discard the staged output file if the batch must be rolled back.",
        "Re-run the read-only fixture apply comparison from the before snapshot.",
    ]
    if candidate_ids:
        plan.append("Revert the staged batch for: " + ", ".join(candidate_ids))
    return plan


def identify_migration_no_go_reasons(
    fixture_apply_summary: dict[str, Any] | None,
    write_plan_summary: dict[str, Any] | None,
    approval_manifest_summary: dict[str, Any] | None,
    *,
    human_approved: bool = False,
) -> list[str]:
    reasons: list[str] = []

    _append_run_gate_reasons(
        reasons,
        fixture_apply_summary,
        write_plan_summary,
        approval_manifest_summary,
        human_approved=human_approved,
    )

    return reasons


def build_migration_verification_checklist(
    fixture_apply_summary: dict[str, Any] | None,
    write_plan_summary: dict[str, Any] | None,
    approval_manifest_summary: dict[str, Any] | None,
    readiness_summary: dict[str, Any] | None = None,
    *,
    human_approved: bool = False,
) -> dict[str, Any]:
    plan_payload = _plan_payload(write_plan_summary)
    plan_summary = plan_payload["summary"]
    plan_items = plan_payload["write_plan_items"]
    rollback_plan = build_migration_rollback_plan(write_plan_summary)
    readiness_level = _readiness_level(readiness_summary)
    ui_can_start = readiness_level == READYNESS_LEVEL_UI_MVP_READY and _as_bool((readiness_summary or {}).get("post_migration_diagnostics_passed"))

    manifest_valid = _manifest_valid(approval_manifest_summary)
    manifest_errors = _manifest_errors(approval_manifest_summary)
    unresolved_fields = _p0_unsafe_fields_unresolved(approval_manifest_summary)
    fixture_summary = fixture_apply_summary if isinstance(fixture_apply_summary, dict) else {}

    checklist = [
        {
            "check": "approval_manifest_valid",
            "required": True,
            "passed": manifest_valid and not manifest_errors,
            "details": manifest_errors,
        },
        {
            "check": "all_write_plan_items_write_ready",
            "required": True,
            "passed": bool(plan_items)
            and _as_int(plan_summary.get("write_ready_count"), len(plan_items)) == len(plan_items)
            and _as_int(plan_summary.get("rejected_count"), 0) == 0,
            "details": {
                "write_ready_count": _as_int(plan_summary.get("write_ready_count"), 0),
                "rejected_count": _as_int(plan_summary.get("rejected_count"), 0),
                "planned_items": len(plan_items),
            },
        },
        {
            "check": "fixture_apply_passed",
            "required": True,
            "passed": _as_bool(fixture_summary.get("dry_run_only"))
            and _as_bool(fixture_summary.get("mutation_allowed")) is False
            and _as_int(fixture_summary.get("applied_count"), 0) == len(plan_items),
            "details": {
                "applied_count": _as_int(fixture_summary.get("applied_count"), 0),
                "skipped_count": _as_int(fixture_summary.get("skipped_count"), 0),
                "dry_run_only": _as_bool(fixture_summary.get("dry_run_only")),
                "mutation_allowed": _as_bool(fixture_summary.get("mutation_allowed")),
            },
        },
        {
            "check": "rollback_plan_exists",
            "required": True,
            "passed": bool(rollback_plan),
            "details": rollback_plan,
        },
        {
            "check": "human_approval_present",
            "required": True,
            "passed": _as_bool(human_approved),
            "details": ["human_approval"],
        },
        {
            "check": "p0_unsafe_fields_resolved",
            "required": True,
            "passed": not unresolved_fields,
            "details": unresolved_fields,
        },
        {
            "check": "ui_gate_remains_blocked",
            "required": True,
            "passed": ui_can_start is False,
            "details": {
                "readiness_level": readiness_level,
                "ui_can_start": ui_can_start,
            },
        },
    ]

    no_go_reasons = identify_migration_no_go_reasons(
        fixture_apply_summary,
        write_plan_summary,
        approval_manifest_summary,
        human_approved=human_approved,
    )

    migration_allowed = not no_go_reasons
    return {
        "migration_allowed": migration_allowed,
        "no_go_reasons": no_go_reasons,
        "human_approved": _as_bool(human_approved),
        "required_human_approvals": _human_approval_required(approval_manifest_summary),
        "rollback_required": True,
        "rollback_plan_exists": bool(rollback_plan),
        "rollback_plan": rollback_plan,
        "ui_can_start": ui_can_start,
        "readiness_level": readiness_level,
        "checks": checklist,
        "fixture_apply_summary": fixture_apply_summary if isinstance(fixture_apply_summary, dict) else {},
        "write_plan_summary": write_plan_summary if isinstance(write_plan_summary, dict) else {},
        "approval_manifest_summary": approval_manifest_summary if isinstance(approval_manifest_summary, dict) else {},
    }


def summarize_migration_gate(
    fixture_apply_summary: dict[str, Any] | None,
    write_plan_summary: dict[str, Any] | None,
    approval_manifest_summary: dict[str, Any] | None,
    readiness_summary: dict[str, Any] | None = None,
    *,
    human_approved: bool = False,
) -> dict[str, Any]:
    gate = build_migration_verification_checklist(
        fixture_apply_summary,
        write_plan_summary,
        approval_manifest_summary,
        readiness_summary,
        human_approved=human_approved,
    )
    return {
        "migration_allowed": gate["migration_allowed"],
        "no_go_reasons": list(gate["no_go_reasons"]),
        "human_approved": gate["human_approved"],
        "required_human_approvals": list(gate["required_human_approvals"]),
        "rollback_required": gate["rollback_required"],
        "rollback_plan_exists": gate["rollback_plan_exists"],
        "ui_can_start": gate["ui_can_start"],
        "readiness_level": gate["readiness_level"],
        "rollback_plan": list(gate["rollback_plan"]),
    }
