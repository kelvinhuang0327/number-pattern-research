"""Pure acceptance gate for Strategy Replay production metadata registries."""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from wbc_backend.reporting.strategy_replay_metadata_registry import (
    summarize_strategy_metadata_registry,
    validate_strategy_metadata_record,
    validate_strategy_metadata_registry,
)


UNSAFE_HINT_BLOCKERS = {
    "single_book": "SINGLE_BOOK",
    "best_bet_strategy": "best_bet_strategy",
    "strategy_id query filter": "query filter strategy_id",
}


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


def _normalize_context(acceptance_context: Mapping[str, Any] | None) -> dict[str, Any]:
    context = dict(acceptance_context or {})
    return {
        "registry_path": _as_text(context.get("registry_path")),
        "registry_owner": _as_text(context.get("registry_owner")),
        "reviewer": _as_text(context.get("reviewer")),
        "approval_timestamp": _as_text(context.get("approval_timestamp")),
        "production_candidate": _as_bool(context.get("production_candidate")),
        "non_production_example": _as_bool(context.get("non_production_example")),
        "audit_evidence_refs": _as_text_list(context.get("audit_evidence_refs")),
        "lifecycle_source_refs": _as_text_list(context.get("lifecycle_source_refs")),
        "runtime_injection_test_passed": _as_bool(context.get("runtime_injection_test_passed")),
        "e2e_fixture_validation_passed": _as_bool(context.get("e2e_fixture_validation_passed")),
        "explicit_human_approval": _as_bool(context.get("explicit_human_approval")),
        "rollback_plan_ref": _as_text(context.get("rollback_plan_ref")),
        "allowed_for_future_writes_only": _as_bool(context.get("allowed_for_future_writes_only")),
        "allowed_for_historical_backfill": _as_bool(context.get("allowed_for_historical_backfill")),
    }


def _record_has_unsafe_hint(record: Mapping[str, Any]) -> list[str]:
    blockers: list[str] = []
    source_kind = _as_text(record.get("source_kind")).lower()
    strategy_name = _as_text(record.get("strategy_name")).lower()
    audit_source = _as_text(record.get("audit_source")).lower()
    lifecycle_state_source = _as_text(record.get("lifecycle_state_source")).lower()

    for text, label in UNSAFE_HINT_BLOCKERS.items():
        if source_kind == text or strategy_name == text or audit_source == text:
            blockers.append(f"record uses unsafe hint: {label}")

    if lifecycle_state_source in {"current_lifecycle_state", "current_lifecycle_state_fallback"}:
        blockers.append("record uses unsafe hint: current_lifecycle_state fallback")

    if _as_bool(record.get("production_ready")) or _as_bool(record.get("ui_ready")) or _as_bool(
        record.get("production_migration_ready")
    ):
        blockers.append("record claims production readiness by itself")

    if _as_bool(record.get("allowed_for_historical_backfill")):
        blockers.append("record allows historical backfill")

    if not _as_bool(record.get("allowed_for_future_writes")):
        blockers.append("record must allow future writes only")

    return blockers


def _context_acceptance_blockers(context: Mapping[str, Any]) -> list[str]:
    blockers: list[str] = []
    for field_name, message in (
        ("registry_owner", "registry_owner is required"),
        ("reviewer", "reviewer is required"),
        ("approval_timestamp", "approval_timestamp is required"),
        ("audit_evidence_refs", "audit_evidence_refs must not be empty"),
        ("lifecycle_source_refs", "lifecycle_source_refs must not be empty"),
        ("rollback_plan_ref", "rollback_plan_ref is required"),
    ):
        if not context[field_name]:
            blockers.append(message)

    for field_name, message in (
        ("production_candidate", "registry must be marked production_candidate"),
        ("explicit_human_approval", "explicit_human_approval must be true"),
        ("runtime_injection_test_passed", "runtime_injection_test_passed must be true"),
        ("e2e_fixture_validation_passed", "e2e_fixture_validation_passed must be true"),
        ("allowed_for_future_writes_only", "allowed_for_future_writes_only must be true"),
    ):
        if not context[field_name]:
            blockers.append(message)

    if context["non_production_example"]:
        blockers.append("registry must not be a non-production example")
    if context["allowed_for_historical_backfill"]:
        blockers.append("allowed_for_historical_backfill must be false")
    return blockers


def _registry_record_blockers(records: list[dict[str, Any]]) -> list[str]:
    blockers: list[str] = []
    registry_summary = validate_strategy_metadata_registry(records)
    if registry_summary["duplicate_strategy_ids"]:
        blockers.append("duplicate strategy_id values are not allowed")
    if registry_summary["invalid_records"]:
        blockers.append("registry contains invalid records")

    for index, record in enumerate(records, start=1):
        record_errors = validate_strategy_metadata_record(record)
        if record_errors:
            blockers.append(f"record {index} invalid: " + "; ".join(record_errors))
        blockers.extend(f"record {index} {reason}" for reason in _record_has_unsafe_hint(record))
    return blockers


def identify_metadata_registry_acceptance_blockers(
    registry_records: Iterable[Mapping[str, Any]] | None,
    acceptance_context: Mapping[str, Any] | None,
) -> list[str]:
    context = _normalize_context(acceptance_context)
    records = [dict(record) for record in (registry_records or []) if isinstance(record, Mapping)]
    blockers: list[str] = []

    blockers.extend(_context_acceptance_blockers(context))
    if context["production_candidate"] is False:
        blockers.append("registry must be marked production_candidate")
    if context["non_production_example"] is True:
        blockers.append("registry must not be a non-production example")

    if not records:
        blockers.append("registry must contain at least one record")
        return blockers

    blockers.extend(_registry_record_blockers(records))

    deduped: list[str] = []
    for blocker in blockers:
        if blocker and blocker not in deduped:
            deduped.append(blocker)
    return deduped


def build_metadata_registry_acceptance_checklist(
    registry_records: Iterable[Mapping[str, Any]] | None,
    acceptance_context: Mapping[str, Any] | None,
) -> dict[str, Any]:
    context = _normalize_context(acceptance_context)
    records = [dict(record) for record in (registry_records or []) if isinstance(record, Mapping)]
    registry_summary = validate_strategy_metadata_registry(records)
    blockers = identify_metadata_registry_acceptance_blockers(records, context)

    checklist = [
        {"check": "production_candidate", "passed": context["production_candidate"], "required": True},
        {"check": "non_production_example", "passed": not context["non_production_example"], "required": True},
        {"check": "registry_owner", "passed": bool(context["registry_owner"]), "required": True},
        {"check": "reviewer", "passed": bool(context["reviewer"]), "required": True},
        {"check": "approval_timestamp", "passed": bool(context["approval_timestamp"]), "required": True},
        {"check": "explicit_human_approval", "passed": context["explicit_human_approval"], "required": True},
        {"check": "audit_evidence_refs", "passed": bool(context["audit_evidence_refs"]), "required": True},
        {"check": "lifecycle_source_refs", "passed": bool(context["lifecycle_source_refs"]), "required": True},
        {"check": "runtime_injection_test_passed", "passed": context["runtime_injection_test_passed"], "required": True},
        {"check": "e2e_fixture_validation_passed", "passed": context["e2e_fixture_validation_passed"], "required": True},
        {"check": "rollback_plan_ref", "passed": bool(context["rollback_plan_ref"]), "required": True},
        {
            "check": "allowed_for_future_writes_only",
            "passed": context["allowed_for_future_writes_only"],
            "required": True,
        },
        {
            "check": "allowed_for_historical_backfill",
            "passed": not context["allowed_for_historical_backfill"],
            "required": True,
        },
        {
            "check": "registry_records_valid",
            "passed": registry_summary["invalid_records"] == 0 and not registry_summary["duplicate_strategy_ids"],
            "required": True,
        },
        {
            "check": "no_unsafe_hint_records",
            "passed": not any("unsafe hint" in blocker for blocker in blockers),
            "required": True,
        },
    ]

    return {
        "checklist": checklist,
        "blockers": blockers,
        "registry_summary": registry_summary,
        "context": context,
    }


def evaluate_metadata_registry_acceptance(
    registry_records: Iterable[Mapping[str, Any]] | None,
    acceptance_context: Mapping[str, Any] | None,
) -> dict[str, Any]:
    checklist_result = build_metadata_registry_acceptance_checklist(registry_records, acceptance_context)
    blockers = checklist_result["blockers"]
    accepted = not blockers and all(item["passed"] for item in checklist_result["checklist"])

    return {
        "production_metadata_registry_accepted": accepted,
        "accepted": accepted,
        "blockers": blockers,
        "blocker_count": len(blockers),
        "checklist": checklist_result["checklist"],
        "registry_summary": checklist_result["registry_summary"],
        "acceptance_context": checklist_result["context"],
    }


def summarize_metadata_registry_acceptance(gate_result: Mapping[str, Any] | None) -> dict[str, Any]:
    gate = dict(gate_result or {})
    return {
        "production_metadata_registry_accepted": _as_bool(gate.get("production_metadata_registry_accepted") or gate.get("accepted")),
        "accepted": _as_bool(gate.get("accepted") or gate.get("production_metadata_registry_accepted")),
        "blocker_count": len(list(gate.get("blockers") or [])),
        "blockers": list(gate.get("blockers") or []),
        "registry_path": _as_text((gate.get("acceptance_context") or {}).get("registry_path")) if isinstance(gate.get("acceptance_context"), Mapping) else "",
        "registry_owner": _as_text((gate.get("acceptance_context") or {}).get("registry_owner")) if isinstance(gate.get("acceptance_context"), Mapping) else "",
        "reviewer": _as_text((gate.get("acceptance_context") or {}).get("reviewer")) if isinstance(gate.get("acceptance_context"), Mapping) else "",
        "record_count": _as_int((gate.get("registry_summary") or {}).get("total_records"), 0),
        "valid_record_count": _as_int((gate.get("registry_summary") or {}).get("valid_records"), 0),
        "invalid_record_count": _as_int((gate.get("registry_summary") or {}).get("invalid_records"), 0),
    }


def _as_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
