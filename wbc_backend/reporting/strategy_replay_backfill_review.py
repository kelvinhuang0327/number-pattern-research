"""Read-only review workflow for Strategy Replay backfill candidates."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from wbc_backend.reporting.strategy_replay_adapter import load_jsonl_entries

REVIEW_DECISION_REVIEW_REQUIRED = "REVIEW_REQUIRED"
REVIEW_DECISION_AUTO_APPROVABLE = "AUTO_APPROVABLE"
REVIEW_DECISION_WRITE_READY = "WRITE_READY"
REVIEW_DECISION_REJECTED = "REJECTED"

_MANIFEST_REQUIRED_FIELDS = ("reviewer", "approval_reason", "timestamp")
_ALLOWED_APPROVED_FIELDS = {
    "canonical_outcome_key_fallback",
    "confidence",
    "edge",
    "lifecycle_state_at_prediction_time",
    "strategy_id",
    "strategy_name",
    "actual_result",
}


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _load_json_payload(path: Path) -> Any:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload


def load_backfill_candidates(path: str | Path) -> list[dict[str, Any]]:
    source_path = Path(path)
    if not source_path.exists():
        return []

    if source_path.suffix.lower() == ".jsonl":
        return load_jsonl_entries(source_path)

    payload = _load_json_payload(source_path)
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key_name in ("candidates", "rows", "items"):
            rows = payload.get(key_name)
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, dict)]
    return []


def _candidate_source_tokens(candidate: dict[str, Any]) -> list[str]:
    tokens: list[str] = []
    original_source_refs = candidate.get("original_source_refs")
    if isinstance(original_source_refs, dict):
        for value in original_source_refs.values():
            text = _as_text(value)
            if text and text not in tokens:
                tokens.append(text)

    candidate_id = _as_text(candidate.get("candidate_id"))
    if candidate_id and candidate_id not in tokens:
        tokens.append(candidate_id)
    return tokens


def _candidate_primary_source_ref(candidate: dict[str, Any]) -> str:
    original_source_refs = candidate.get("original_source_refs")
    if isinstance(original_source_refs, dict):
        for key_name in ("prediction", "prediction_registry", "source_ref"):
            text = _as_text(original_source_refs.get(key_name))
            if text:
                return text
        for value in original_source_refs.values():
            text = _as_text(value)
            if text:
                return text
    return _as_text(candidate.get("candidate_id"))


def _candidate_has_required_source_refs(candidate: dict[str, Any]) -> bool:
    original_source_refs = candidate.get("original_source_refs")
    if not isinstance(original_source_refs, dict) or not original_source_refs:
        return False
    return any(_as_text(value) for value in original_source_refs.values())


def _manifest_required_field_errors(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field_name in _MANIFEST_REQUIRED_FIELDS:
        if not _as_text(manifest.get(field_name)):
            errors.append(f"missing required manifest field: {field_name}")
    return errors


def _normalize_manifest_approval_entry(
    index: int,
    entry: Any,
    candidate_tokens: dict[str, dict[str, Any]],
    manifest: dict[str, Any],
) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    if not isinstance(entry, dict):
        return None, [f"manifest entry {index} must be an object"]

    candidate_id = _as_text(entry.get("candidate_id"))
    source_ref = _as_text(entry.get("source_ref"))
    token = candidate_id or source_ref
    if not token:
        return None, [f"manifest entry {index} must include candidate_id or source_ref"]

    if token not in candidate_tokens:
        return None, [f"unknown candidate reference: {token}"]

    approved_fields = entry.get("approved_fields")
    if not isinstance(approved_fields, list) or not approved_fields:
        return None, [f"manifest entry {index} must include a non-empty approved_fields list"]

    approved_fields_text = [_as_text(field) for field in approved_fields if _as_text(field)]
    if not approved_fields_text:
        return None, [f"manifest entry {index} must include at least one approved field"]

    unknown_fields = [field_name for field_name in approved_fields_text if field_name not in _ALLOWED_APPROVED_FIELDS]
    if unknown_fields:
        return None, [
            f"manifest entry {index} contains unsupported approved_fields: {', '.join(sorted(unknown_fields))}"
        ]

    normalized_entry = {
        "candidate_id": candidate_id,
        "source_ref": source_ref,
        "approved_fields": approved_fields_text,
        "reviewer": _as_text(manifest.get("reviewer")),
        "approval_reason": _as_text(manifest.get("approval_reason")),
        "timestamp": _as_text(manifest.get("timestamp")),
    }
    return normalized_entry, errors


def summarize_backfill_candidates(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    summary = {
        "total_candidates": len(candidates),
        "review_required_count": 0,
        "auto_approvable_count": 0,
        "write_ready_count": 0,
        "rejected_count": 0,
        "unsafe_to_infer_field_counts": {},
        "decision_counts": {},
    }

    unsafe_counter: Counter[str] = Counter()
    decision_counter: Counter[str] = Counter()
    for candidate in candidates:
        decision = classify_review_decision(candidate)
        decision_counter[decision] += 1
        if decision == REVIEW_DECISION_REVIEW_REQUIRED:
            summary["review_required_count"] += 1
        elif decision == REVIEW_DECISION_AUTO_APPROVABLE:
            summary["auto_approvable_count"] += 1
        elif decision == REVIEW_DECISION_WRITE_READY:
            summary["write_ready_count"] += 1
        elif decision == REVIEW_DECISION_REJECTED:
            summary["rejected_count"] += 1

        for field_name in candidate.get("unsafe_to_infer_fields") or []:
            unsafe_counter[_as_text(field_name)] += 1

    summary["unsafe_to_infer_field_counts"] = dict(sorted(unsafe_counter.items()))
    summary["decision_counts"] = dict(sorted(decision_counter.items()))
    return summary


def classify_review_decision(candidate: dict[str, Any]) -> str:
    if not _candidate_has_required_source_refs(candidate):
        return REVIEW_DECISION_REVIEW_REQUIRED

    unsafe_fields = list(candidate.get("unsafe_to_infer_fields") or [])
    if unsafe_fields:
        return REVIEW_DECISION_REVIEW_REQUIRED

    priority = _as_text(candidate.get("backfill_priority"))
    if priority in {"P1", "P2", "READY"}:
        return REVIEW_DECISION_AUTO_APPROVABLE

    return REVIEW_DECISION_REVIEW_REQUIRED


def validate_approval_manifest(
    manifest: dict[str, Any] | None,
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    candidate_tokens: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        for token in _candidate_source_tokens(candidate):
            candidate_tokens[token] = candidate

    errors: list[str] = []
    if not isinstance(manifest, dict):
        errors.append("approval manifest must be a JSON object")
        return {
            "valid": False,
            "errors": errors,
            "approved_entries": {},
            "approval_entries": [],
        }

    errors.extend(_manifest_required_field_errors(manifest))

    entries = manifest.get("entries")
    if not isinstance(entries, list) or not entries:
        errors.append("approval manifest must include a non-empty entries list")
        entries = []

    approved_entries: dict[str, dict[str, Any]] = {}
    normalized_entries: list[dict[str, Any]] = []
    for index, entry in enumerate(entries, start=1):
        normalized_entry, entry_errors = _normalize_manifest_approval_entry(index, entry, candidate_tokens, manifest)
        if entry_errors:
            errors.extend(entry_errors)
            continue

        normalized_entries.append(normalized_entry)
        token = normalized_entry["candidate_id"] or normalized_entry["source_ref"]
        approved_entries[token] = normalized_entry

    return {
        "valid": not errors,
        "errors": errors,
        "approved_entries": approved_entries,
        "approval_entries": normalized_entries,
    }


def _approval_allows_write_ready(candidate: dict[str, Any], approval_entry: dict[str, Any] | None) -> bool:
    if not approval_entry:
        return False

    approved_fields = set(approval_entry.get("approved_fields") or [])
    inferred_fields = set(candidate.get("inferred_fields") or [])
    unsafe_fields = set(candidate.get("unsafe_to_infer_fields") or [])

    if unsafe_fields:
        return False
    return inferred_fields.issubset(approved_fields)


def build_safe_migration_proposal(
    candidates: list[dict[str, Any]],
    approval_manifest: dict[str, Any] | None,
) -> dict[str, Any]:
    manifest_result = validate_approval_manifest(approval_manifest, candidates)
    approved_entries = manifest_result["approved_entries"] if manifest_result["valid"] else {}

    proposal_items: list[dict[str, Any]] = []
    rejected_count = 0
    for candidate in candidates:
        review_decision = classify_review_decision(candidate)
        token = _candidate_primary_source_ref(candidate)
        approval_entry = approved_entries.get(token)
        write_ready = review_decision == REVIEW_DECISION_AUTO_APPROVABLE and _approval_allows_write_ready(candidate, approval_entry)
        if review_decision == REVIEW_DECISION_REVIEW_REQUIRED:
            status = REVIEW_DECISION_REVIEW_REQUIRED
        elif write_ready:
            status = REVIEW_DECISION_WRITE_READY
        else:
            status = REVIEW_DECISION_AUTO_APPROVABLE

        if status == REVIEW_DECISION_REJECTED:
            rejected_count += 1

        proposal_items.append(
            {
                "candidate_id": token,
                "status": status,
                "review_decision": review_decision,
                "write_ready": write_ready,
                "approved_fields": list((approval_entry or {}).get("approved_fields") or []),
                "backfill_priority": candidate.get("backfill_priority", ""),
                "unsafe_to_infer_fields": list(candidate.get("unsafe_to_infer_fields") or []),
                "inferred_fields": list(candidate.get("inferred_fields") or []),
                "original_source_refs": dict(candidate.get("original_source_refs") or {}),
            }
        )

    summary = summarize_backfill_candidates(candidates)
    summary["rejected_count"] = rejected_count + len(manifest_result["errors"])
    write_ready_count = sum(1 for item in proposal_items if item["write_ready"])
    summary["write_ready_count"] = write_ready_count
    summary["auto_approvable_count"] = sum(1 for item in proposal_items if item["status"] == REVIEW_DECISION_AUTO_APPROVABLE)
    summary["review_required_count"] = sum(1 for item in proposal_items if item["status"] == REVIEW_DECISION_REVIEW_REQUIRED)
    migration_allowed = bool(manifest_result["valid"]) and write_ready_count == len(candidates)

    return {
        "summary": summary,
        "proposal_items": proposal_items,
        "manifest_valid": manifest_result["valid"],
        "manifest_errors": list(manifest_result["errors"]),
        "migration_allowed": migration_allowed,
    }