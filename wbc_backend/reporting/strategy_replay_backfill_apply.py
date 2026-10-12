"""Fixture-only apply helpers for Strategy Replay backfill write plans."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from wbc_backend.reporting.strategy_replay_backfill_write_plan import validate_write_plan


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _load_json_payload(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _rows_from_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key_name in ("rows", "items", "candidates"):
            rows = payload.get(key_name)
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, dict)]
    return []


def _collect_tokens(mapping: dict[str, Any] | None, key_names: tuple[str, ...]) -> list[str]:
    tokens: list[str] = []
    if not isinstance(mapping, dict):
        return tokens

    for value in mapping.values():
        text = _as_text(value)
        if text and text not in tokens:
            tokens.append(text)

    for key_name in key_names:
        text = _as_text(mapping.get(key_name))
        if text and text not in tokens:
            tokens.append(text)

    return tokens


def load_jsonl_rows(path: str | Path) -> list[dict[str, Any]]:
    source_path = Path(path)
    if not source_path.exists():
        return []

    if source_path.suffix.lower() == ".jsonl":
        rows: list[dict[str, Any]] = []
        with source_path.open("r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line:
                    continue
                row = json.loads(line)
                if isinstance(row, dict):
                    rows.append(row)
        return rows

    payload = _load_json_payload(source_path)
    return _rows_from_payload(payload)


def _row_source_tokens(row: dict[str, Any]) -> list[str]:
    tokens = _collect_tokens(row.get("source_refs") or row.get("original_source_refs"), ("prediction", "prediction_registry", "source_ref", "candidate_id"))
    for key_name in ("candidate_id", "source_ref", "recorded_at_utc"):
        text = _as_text(row.get(key_name))
        if text and text not in tokens:
            tokens.append(text)
    return tokens


def _plan_item_tokens(item: dict[str, Any]) -> list[str]:
    tokens = _collect_tokens(item.get("source_refs"), ("prediction", "prediction_registry", "source_ref"))
    candidate_id = _as_text(item.get("candidate_id"))
    if candidate_id and candidate_id not in tokens:
        tokens.append(candidate_id)
    return tokens


def _plan_item_identifier(item: dict[str, Any]) -> str:
    candidate_id = _as_text(item.get("candidate_id"))
    if candidate_id:
        return candidate_id
    source_refs = item.get("source_refs")
    if isinstance(source_refs, dict):
        return _as_text(source_refs.get("source_ref") or source_refs.get("prediction") or source_refs.get("prediction_registry"))
    return ""


def _build_plan_index(write_plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for item in write_plan.get("write_plan_items") or []:
        if not isinstance(item, dict):
            continue
        for token in _plan_item_tokens(item):
            index[token] = item
    return index


def _find_matching_plan_item(row: dict[str, Any], plan_index: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    for token in _row_source_tokens(row):
        matched_item = plan_index.get(token)
        if matched_item is not None:
            return matched_item
    return None


def _count_unapplied_plan_items(write_plan: dict[str, Any], applied_plan_items: set[str]) -> int:
    return sum(
        1
        for item in write_plan.get("write_plan_items") or []
        if isinstance(item, dict) and _plan_item_identifier(item) not in applied_plan_items
    )


def _apply_patch_to_row(row: dict[str, Any], plan_item: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    patched_row = copy.deepcopy(row)
    approved_fields = set(plan_item.get("approved_fields") or [])
    proposed_values = dict((plan_item.get("proposed_patch") or {}).get("proposed_values") or {})
    changed_fields: list[str] = []

    for field_name in approved_fields:
        if field_name not in proposed_values:
            continue
        new_value = proposed_values[field_name]
        if patched_row.get(field_name) != new_value:
            changed_fields.append(field_name)
        patched_row[field_name] = copy.deepcopy(new_value)

    return patched_row, changed_fields


def apply_write_plan_to_rows(
    rows: list[dict[str, Any]],
    write_plan: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(write_plan, dict):
        raise ValueError("write_plan must be a mapping")
    if write_plan.get("summary", {}).get("dry_run_only") is not True:
        raise ValueError("fixture-only apply requires a dry_run_only write plan")

    validation = validate_write_plan(write_plan)
    if not validation["valid"]:
        raise ValueError("invalid write plan: " + "; ".join(validation["errors"]))

    plan_index = _build_plan_index(write_plan)
    applied_plan_items: set[str] = set()
    applied_count = 0
    unchanged_count = 0
    after_rows: list[dict[str, Any]] = []

    for row in rows:
        if not isinstance(row, dict):
            after_rows.append(copy.deepcopy(row))
            unchanged_count += 1
            continue

        matched_item = _find_matching_plan_item(row, plan_index)
        if matched_item is not None:
            applied_plan_items.add(_plan_item_identifier(matched_item))

        if matched_item is None:
            after_rows.append(copy.deepcopy(row))
            unchanged_count += 1
            continue

        patched_row, changed_fields = _apply_patch_to_row(row, matched_item)
        after_rows.append(patched_row)
        if changed_fields:
            applied_count += 1
        else:
            unchanged_count += 1

    skipped_count = _count_unapplied_plan_items(write_plan, applied_plan_items)

    return {
        "rows": after_rows,
        "applied_count": applied_count,
        "skipped_count": skipped_count,
        "unchanged_count": unchanged_count,
        "dry_run_only": True,
        "mutation_allowed": False,
    }


def validate_fixture_apply_result(
    before_rows: list[dict[str, Any]],
    after_rows: list[dict[str, Any]],
    write_plan: dict[str, Any],
) -> dict[str, Any]:
    errors: list[str] = []
    if len(before_rows) != len(after_rows):
        errors.append("row count changed during fixture apply")
    if write_plan.get("summary", {}).get("dry_run_only") is not True:
        errors.append("fixture apply requires dry_run_only plan")

    summary = summarize_fixture_apply_result(before_rows, after_rows, write_plan)
    if summary["mutation_allowed"]:
        errors.append("fixture apply must not allow mutation")
    if summary["dry_run_only"] is not True:
        errors.append("fixture apply summary must be dry_run_only")

    return {
        "valid": not errors,
        "errors": errors,
        "summary": summary,
    }


def summarize_fixture_apply_result(
    before_rows: list[dict[str, Any]],
    after_rows: list[dict[str, Any]],
    write_plan: dict[str, Any],
) -> dict[str, Any]:
    before_snapshot = json.dumps(before_rows, sort_keys=True, ensure_ascii=False)
    after_snapshot = json.dumps(after_rows, sort_keys=True, ensure_ascii=False)
    applied_count = sum(1 for before, after in zip(before_rows, after_rows) if before != after)
    unchanged_count = sum(1 for before, after in zip(before_rows, after_rows) if before == after)
    skipped_count = max(len(write_plan.get("write_plan_items") or []) - applied_count, 0)

    return {
        "applied_count": applied_count,
        "skipped_count": skipped_count,
        "unchanged_count": unchanged_count,
        "dry_run_only": True,
        "mutation_allowed": False,
        "before_snapshot": before_snapshot,
        "after_snapshot": after_snapshot,
    }