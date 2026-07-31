"""Dry-run write plan builder for approved Strategy Replay backfill candidates."""
from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from wbc_backend.reporting.strategy_replay_backfill_review import (
    REVIEW_DECISION_REVIEW_REQUIRED,
    REVIEW_DECISION_WRITE_READY,
    build_safe_migration_proposal,
    load_backfill_candidates,
    validate_approval_manifest,
)


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _approval_key(entry: dict[str, Any]) -> str:
    return _as_text(entry.get("candidate_id") or entry.get("source_ref"))


def _validate_write_plan_item(index: int, item: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(item, dict):
        return [f"write plan item {index} must be an object"]

    if not _as_text(item.get("candidate_id")):
        errors.append(f"write plan item {index} missing candidate_id")
    if not isinstance(item.get("source_refs"), dict) or not item.get("source_refs"):
        errors.append(f"write plan item {index} missing source_refs")
    if not isinstance(item.get("approved_fields"), list):
        errors.append(f"write plan item {index} approved_fields must be a list")
    if not isinstance(item.get("proposed_patch"), dict):
        errors.append(f"write plan item {index} proposed_patch must be an object")
    if item.get("dry_run_only") is not True:
        errors.append(f"write plan item {index} must be dry_run_only")
    return errors


def _validate_write_plan_summary(summary: Any) -> list[str]:
    if not isinstance(summary, dict):
        return ["plan summary must be a mapping"]
    if summary.get("dry_run_only") is not True:
        return ["plan summary must be dry_run_only"]
    return []


def _build_proposed_patch(candidate: dict[str, Any], approval_entry: dict[str, Any] | None) -> dict[str, Any]:
    approved_fields = list((approval_entry or {}).get("approved_fields") or [])
    patch = {
        "write_action": "append_historical_backfill_candidate",
        "candidate_id": _approval_key(candidate),
        "source_refs": dict(candidate.get("original_source_refs") or {}),
        "approved_fields": approved_fields,
        "proposed_values": {},
        "dry_run_only": True,
    }

    proposed_values = patch["proposed_values"]
    for field_name in approved_fields:
        if field_name == "strategy_id":
            proposed_values[field_name] = candidate.get("proposed_strategy_id", "")
        elif field_name == "strategy_name":
            proposed_values[field_name] = candidate.get("strategy_name", candidate.get("proposed_strategy_name", ""))
        elif field_name == "lifecycle_state_at_prediction_time":
            proposed_values[field_name] = candidate.get("proposed_lifecycle_state_at_prediction_time", "")
        elif field_name == "canonical_outcome_key_fallback":
            proposed_values[field_name] = True
        elif field_name == "actual_result":
            proposed_values[field_name] = candidate.get("proposed_actual_result", "")
        elif field_name in {"confidence", "edge"}:
            proposed_values[field_name] = candidate.get(field_name, "")

    return patch


def reject_unapproved_candidates(
    candidates: list[dict[str, Any]],
    approval_manifest: dict[str, Any] | None,
) -> dict[str, Any]:
    proposal = build_safe_migration_proposal(candidates, approval_manifest)
    approved_items = [item for item in proposal["proposal_items"] if item["status"] == REVIEW_DECISION_WRITE_READY]
    rejected_items = [item for item in proposal["proposal_items"] if item["status"] != REVIEW_DECISION_WRITE_READY]
    return {
        "approved_items": approved_items,
        "rejected_items": rejected_items,
        "manifest_valid": proposal["manifest_valid"],
        "manifest_errors": list(proposal["manifest_errors"]),
        "migration_allowed": proposal["migration_allowed"],
    }


def build_approved_backfill_write_plan(
    candidates: list[dict[str, Any]],
    approval_manifest: dict[str, Any] | None,
) -> dict[str, Any]:
    review_proposal = build_safe_migration_proposal(candidates, approval_manifest)
    manifest_result = validate_approval_manifest(approval_manifest, candidates)
    approved_lookup = {}
    if manifest_result["valid"]:
        approved_lookup = manifest_result["approved_entries"]

    write_plan_items: list[dict[str, Any]] = []
    rejected_count = 0
    for item in review_proposal["proposal_items"]:
        if item["status"] != REVIEW_DECISION_WRITE_READY:
            rejected_count += 1
            continue

        approval_key = _approval_key(item)
        approval_entry = approved_lookup.get(approval_key)
        write_plan_items.append(
            {
                "candidate_id": approval_key,
                "source_refs": dict(item.get("original_source_refs") or {}),
                "approved_fields": list((approval_entry or {}).get("approved_fields") or []),
                "proposed_patch": _build_proposed_patch(item, approval_entry),
                "reviewer": _as_text((approval_entry or {}).get("reviewer")),
                "approval_reason": _as_text((approval_entry or {}).get("approval_reason")),
                "timestamp": _as_text((approval_entry or {}).get("timestamp")),
                "dry_run_only": True,
            }
        )

    return {
        "summary": {
            "total_candidates": len(candidates),
            "write_ready_count": len(write_plan_items),
            "rejected_count": rejected_count + len(review_proposal["manifest_errors"]),
            "migration_allowed": bool(write_plan_items) and not review_proposal["manifest_errors"],
            "dry_run_only": True,
        },
        "write_plan_items": write_plan_items,
        "review_proposal": review_proposal,
        "manifest_valid": manifest_result["valid"],
        "manifest_errors": list(manifest_result["errors"]),
    }


def validate_write_plan(plan: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    write_plan_items = plan.get("write_plan_items")
    if not isinstance(write_plan_items, list):
        errors.append("write_plan_items must be a list")
        write_plan_items = []

    for index, item in enumerate(write_plan_items, start=1):
        errors.extend(_validate_write_plan_item(index, item))

    summary = plan.get("summary") if isinstance(plan.get("summary"), dict) else {}
    errors.extend(_validate_write_plan_summary(summary))

    return {
        "valid": not errors,
        "errors": errors,
    }


def summarize_write_plan(plan: dict[str, Any]) -> dict[str, Any]:
    write_plan_items = list(plan.get("write_plan_items") or [])
    approved_fields_counter: Counter[str] = Counter()
    for item in write_plan_items:
        for field_name in item.get("approved_fields") or []:
            approved_fields_counter[_as_text(field_name)] += 1

    summary = dict(plan.get("summary") or {})
    summary["approved_fields_summary"] = dict(sorted(approved_fields_counter.items()))
    summary.setdefault("total_candidates", len(write_plan_items))
    summary.setdefault("write_ready_count", len(write_plan_items))
    summary.setdefault("rejected_count", 0)
    summary.setdefault("migration_allowed", False)
    summary.setdefault("dry_run_only", True)
    return summary
