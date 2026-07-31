"""Lifecycle rules for accepted-context previews in Strategy Replay."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any


NO_REAL_APPROVAL = "NO_REAL_APPROVAL"
PREVIEW_GENERATED_NOT_ENABLED = "PREVIEW_GENERATED_NOT_ENABLED"
PREFLIGHT_BLOCKED = "PREFLIGHT_BLOCKED"
READY_FOR_OPERATOR_ENABLEMENT_REVIEW = "READY_FOR_OPERATOR_ENABLEMENT_REVIEW"
PRODUCTION_ENABLED_NOT_ALLOWED_BY_THIS_GATE = "PRODUCTION_ENABLED_NOT_ALLOWED_BY_THIS_GATE"


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


def _normalize_context(context: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = dict(context or {})
    return {
        "real_approval": _as_bool(payload.get("real_approval")),
        "approval_decision": _as_text(payload.get("approval_decision")).upper(),
        "reviewed_registry_path": _as_text(payload.get("reviewed_registry_path")),
        "reviewed_acceptance_context_path": _as_text(payload.get("reviewed_acceptance_context_path")),
        "production_enablement_allowed": _as_bool(payload.get("production_enablement_allowed")),
        "runtime_config_change_allowed": _as_bool(payload.get("runtime_config_change_allowed")),
        "ui_launch_allowed": _as_bool(payload.get("ui_launch_allowed")),
        "production_migration_allowed": _as_bool(payload.get("production_migration_allowed")),
        "operator_signoff": _as_bool(payload.get("operator_signoff")),
    }


def _normalize_preflight(preflight_summary: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = dict(preflight_summary or {})
    return {
        "runtime_enablement_ready": _as_bool(payload.get("runtime_enablement_ready")),
        "blockers": [str(item).strip() for item in payload.get("blockers") or [] if str(item).strip()],
    }


def _has_real_approval(context: Mapping[str, Any]) -> bool:
    return context["real_approval"] and context["approval_decision"] == "APPROVE" and bool(
        context["reviewed_registry_path"]
    )


def _classify_lifecycle_state(
    context: Mapping[str, Any],
    preflight_summary: Mapping[str, Any],
) -> str:
    if not _has_real_approval(context):
        return NO_REAL_APPROVAL
    if preflight_summary["runtime_enablement_ready"]:
        if context["operator_signoff"]:
            return PRODUCTION_ENABLED_NOT_ALLOWED_BY_THIS_GATE
        return READY_FOR_OPERATOR_ENABLEMENT_REVIEW
    return PREFLIGHT_BLOCKED


def classify_accepted_context_preview_state(context: Mapping[str, Any] | None) -> str:
    preview = _normalize_context(context)
    if not _has_real_approval(preview):
        return NO_REAL_APPROVAL
    if preview["production_enablement_allowed"]:
        return PRODUCTION_ENABLED_NOT_ALLOWED_BY_THIS_GATE
    return PREVIEW_GENERATED_NOT_ENABLED


def identify_accepted_context_preview_blockers(
    context: Mapping[str, Any] | None,
    preflight_summary: Mapping[str, Any] | None,
) -> list[str]:
    preview = _normalize_context(context)
    preflight = _normalize_preflight(preflight_summary)
    blockers: list[str] = []

    if not _has_real_approval(preview):
        blockers.append("NO_REAL_APPROVAL_FORM")
    else:
        blockers.append("ACCEPTED_CONTEXT_IS_PREVIEW_ONLY")

    if not preflight["runtime_enablement_ready"]:
        blockers.append("RUNTIME_PREFLIGHT_BLOCKED")
    if not preview["operator_signoff"]:
        blockers.append("OPERATOR_SIGNOFF_REQUIRED")

    blockers.extend(
        [
            "PRODUCTION_CONFIG_CHANGE_NOT_ALLOWED",
            "UI_GATE_NOT_PASSED",
            "PRODUCTION_MIGRATION_BLOCKED",
        ]
    )

    deduped: list[str] = []
    for blocker in blockers:
        if blocker not in deduped:
            deduped.append(blocker)
    return deduped


def build_accepted_context_preview_lifecycle_notice(
    context: Mapping[str, Any] | None,
    preflight_summary: Mapping[str, Any] | None,
) -> dict[str, Any]:
    preview = _normalize_context(context)
    preflight = _normalize_preflight(preflight_summary)
    state = _classify_lifecycle_state(preview, preflight)
    blockers = identify_accepted_context_preview_blockers(preview, preflight)
    production_enabled = False
    return {
        "lifecycle_state": state,
        "blockers": blockers,
        "blocker_count": len(blockers),
        "production_enabled": production_enabled,
        "preview_context": preview,
        "preflight_summary": preflight,
        "accepted_context_is_preview_only": state != NO_REAL_APPROVAL,
        "production_enablement_allowed": False,
        "runtime_config_change_allowed": False,
        "ui_launch_allowed": False,
        "production_migration_allowed": False,
    }


def summarize_accepted_context_preview_lifecycle(
    context: Mapping[str, Any] | None,
    preflight_summary: Mapping[str, Any] | None,
) -> dict[str, Any]:
    notice = build_accepted_context_preview_lifecycle_notice(context, preflight_summary)
    return {
        "lifecycle_state": notice["lifecycle_state"],
        "blocker_count": notice["blocker_count"],
        "blockers": notice["blockers"],
        "production_enabled": False,
        "accepted_context_is_preview_only": notice["accepted_context_is_preview_only"],
        "production_enablement_allowed": False,
        "runtime_config_change_allowed": False,
        "ui_launch_allowed": False,
        "production_migration_allowed": False,
    }