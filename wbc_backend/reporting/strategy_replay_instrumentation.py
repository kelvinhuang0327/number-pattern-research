"""Read-only instrumentation helpers for strategy replay backfill preparation."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from wbc_backend.reporting.strategy_replay_history import build_data_quality_flags, normalize_lifecycle_state


WRITE_PATH_REPLAY_METADATA_VERSION = "p7-1.0"
WRITE_PATH_REPLAY_INSTRUMENTATION_SOURCE = "wbc_backend.reporting.prediction_registry"


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _first_text(record: Mapping[str, Any], paths: tuple[tuple[str, ...], ...]) -> str:
    for path in paths:
        current: Any = record
        for key in path:
            if not isinstance(current, Mapping) or key not in current:
                current = None
                break
            current = current.get(key)
        text = _as_text(current)
        if text:
            return text
    return ""


def build_canonical_outcome_key(record: Mapping[str, Any]) -> dict[str, Any]:
    """Resolve a canonical outcome key without mutating the source record."""
    explicit_key = _first_text(
        record,
        (
            ("canonical_outcome_key",),
            ("canonical_game_id",),
            ("request", "canonical_outcome_key"),
            ("verification", "canonical_game_id"),
        ),
    )
    source = "explicit"
    used_fallback = False

    if not explicit_key:
        explicit_key = _first_text(record, (("game_id",),))
        source = "game_id_fallback" if explicit_key else "missing"
        used_fallback = bool(explicit_key)

    return {
        "value": explicit_key,
        "source": source,
        "used_fallback": used_fallback,
    }


def resolve_strategy_identity(record: Mapping[str, Any]) -> dict[str, Any]:
    """Resolve strategy identity without inventing missing values."""
    strategy_id = _first_text(
        record,
        (
            ("strategy_id",),
            ("request", "strategy_id"),
            ("prediction", "strategy_id"),
            ("decision_report", "strategy_id"),
        ),
    )
    strategy_name = _first_text(
        record,
        (
            ("strategy_name",),
            ("request", "strategy_name"),
            ("request", "strategy"),
            ("decision_report", "strategy_name"),
        ),
    )
    return {
        "strategy_id": strategy_id,
        "strategy_name": strategy_name,
        "strategy_id_missing": not bool(strategy_id),
        "strategy_name_missing": not bool(strategy_name),
    }


def snapshot_lifecycle_state(record: Mapping[str, Any]) -> dict[str, Any]:
    """Snapshot lifecycle state at prediction time only from explicit history."""
    raw_state = _first_text(
        record,
        (
            ("lifecycle_state_at_prediction_time",),
            ("strategy_lifecycle_state",),
            ("request", "lifecycle_state_at_prediction_time"),
            ("request", "strategy_lifecycle_state"),
            ("request", "lifecycle_state"),
        ),
    )
    normalized_state = normalize_lifecycle_state(raw_state)
    source = "explicit" if raw_state else "missing"
    return {
        "value": normalized_state if raw_state else "",
        "raw_value": raw_state,
        "source": source,
        "inferred": False,
        "missing": not bool(raw_state),
    }


def enrich_prediction_for_strategy_replay(record: Mapping[str, Any]) -> dict[str, Any]:
    """Build a non-mutating enrichment payload for strategy replay prep."""
    source_record = dict(record or {})
    identity = resolve_strategy_identity(source_record)
    canonical = build_canonical_outcome_key(source_record)
    lifecycle = snapshot_lifecycle_state(source_record)

    result: dict[str, Any] = {
        "strategy_id": identity["strategy_id"],
        "strategy_name": identity["strategy_name"],
        "canonical_outcome_key": canonical["value"],
        "canonical_outcome_key_source": canonical["source"],
        "canonical_outcome_key_used_fallback": canonical["used_fallback"],
        "lifecycle_state_at_prediction_time": lifecycle["value"],
        "lifecycle_state_at_prediction_time_raw": lifecycle["raw_value"],
        "lifecycle_state_source": lifecycle["source"],
        "lifecycle_state_inferred": lifecycle["inferred"],
        "actual_result": _first_text(record, (("actual_result",), ("evaluation", "actual_result"), ("evaluation", "realized_outcome"))),
        "data_quality_flags": [],
        "source_refs": {
            "prediction_record": _as_text(source_record.get("game_id") or source_record.get("recorded_at_utc") or "prediction_record"),
        },
    }

    result["data_quality_flags"] = build_data_quality_flags(result)
    if canonical["used_fallback"]:
        result["data_quality_flags"] = list(result["data_quality_flags"]) + ["CANONICAL_OUTCOME_KEY_FALLBACK_TO_GAME_ID"]
    return result


def build_backfill_candidate(record: Mapping[str, Any]) -> dict[str, Any]:
    """Return a backfill candidate row with explicit readiness flags."""
    source_record = dict(record or {})
    enrichment = enrich_prediction_for_strategy_replay(source_record)
    candidate = {
        "strategy_id": enrichment["strategy_id"],
        "strategy_name": enrichment["strategy_name"],
        "lifecycle_state_at_prediction_time": enrichment["lifecycle_state_at_prediction_time"],
        "current_lifecycle_state": _first_text(source_record, (("current_lifecycle_state",), ("request", "current_lifecycle_state"))),
        "prediction_timestamp": _first_text(source_record, (("prediction_timestamp",), ("recorded_at_utc",))),
        "game_id": _as_text(source_record.get("game_id")),
        "canonical_outcome_key": enrichment["canonical_outcome_key"],
        "canonical_outcome_key_source": enrichment["canonical_outcome_key_source"],
        "canonical_outcome_key_used_fallback": enrichment["canonical_outcome_key_used_fallback"],
        "market_type": _first_text(source_record, (("market_type",), ("request", "market_type"))),
        "recommendation": _first_text(source_record, (("recommendation",), ("decision_report", "decision"))),
        "confidence": source_record.get("confidence", source_record.get("game_output", {}).get("confidence_index")),
        "edge": source_record.get("edge", source_record.get("portfolio_metrics", {}).get("edge")),
        "actual_result": enrichment["actual_result"],
        "hit_miss_push": _first_text(source_record, (("hit_miss_push",),)),
        "settlement_status": _first_text(source_record, (("settlement_status",),)),
        "data_quality_flags": list(enrichment["data_quality_flags"]),
        "source_refs": dict(enrichment["source_refs"]),
    }
    return candidate


def validate_backfill_candidate(candidate: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if not _as_text(candidate.get("strategy_id")):
        errors.append("missing strategy_id")
    if not _as_text(candidate.get("lifecycle_state_at_prediction_time")):
        errors.append("missing lifecycle_state_at_prediction_time")
    if not _as_text(candidate.get("canonical_outcome_key")):
        errors.append("missing canonical_outcome_key")
    elif candidate.get("canonical_outcome_key_used_fallback"):
        errors.append("canonical_outcome_key uses game_id fallback")
    if not _as_text(candidate.get("actual_result")):
        errors.append("missing actual_result")
    return errors


def build_prediction_write_path_replay_metadata(record: Mapping[str, Any]) -> dict[str, Any]:
    """Build replay metadata for prediction registry writes without inventing values."""
    source_record = dict(record or {})
    identity = resolve_strategy_identity(source_record)
    canonical = build_canonical_outcome_key(source_record)
    lifecycle = snapshot_lifecycle_state(source_record)

    current_lifecycle_state = _first_text(
        source_record,
        (
            ("current_lifecycle_state",),
            ("request", "current_lifecycle_state"),
        ),
    )

    flags: list[str] = []
    if identity["strategy_id_missing"]:
        flags.append("MISSING_STRATEGY_ID")
    if identity["strategy_name_missing"]:
        flags.append("MISSING_STRATEGY_NAME")
    if not current_lifecycle_state:
        flags.append("MISSING_CURRENT_LIFECYCLE_STATE")
    if lifecycle["missing"]:
        flags.append("MISSING_LIFECYCLE_STATE_AT_PREDICTION_TIME")
    if not canonical["value"]:
        flags.append("MISSING_CANONICAL_OUTCOME_KEY")
    elif canonical["used_fallback"]:
        flags.append("CANONICAL_OUTCOME_KEY_FALLBACK_TO_GAME_ID")
    if canonical["value"] and canonical["value"].lower() in {"tmp", "temp", "unknown", "pending", "n/a", "na", "none"}:
        flags.append("UNSTABLE_CANONICAL_OUTCOME_KEY")

    return {
        "strategy_id": identity["strategy_id"],
        "strategy_name": identity["strategy_name"],
        "lifecycle_state_at_prediction_time": lifecycle["value"],
        "current_lifecycle_state": current_lifecycle_state,
        "canonical_outcome_key": canonical["value"],
        "canonical_outcome_key_source": canonical["source"],
        "canonical_outcome_key_used_fallback": canonical["used_fallback"],
        "replay_metadata_version": WRITE_PATH_REPLAY_METADATA_VERSION,
        "replay_instrumentation_source": WRITE_PATH_REPLAY_INSTRUMENTATION_SOURCE,
        "replay_data_quality_flags": flags,
        "replay_data_quality_flag_count": len(flags),
    }


def _build_outcome_lookup(entries: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue

        for key_name in ("canonical_outcome_key", "canonical_game_id", "game_id"):
            candidate = _as_text(entry.get(key_name))
            if candidate and candidate not in lookup:
                lookup[candidate] = entry
    return lookup


def _extract_actual_result(entry: Mapping[str, Any] | None) -> str:
    if not isinstance(entry, Mapping):
        return ""

    for key_name in ("actual_result", "result_status", "realized_outcome"):
        text = _as_text(entry.get(key_name))
        if text:
            return text

    evaluation = entry.get("evaluation")
    if isinstance(evaluation, Mapping):
        for key_name in ("actual_result", "result_status", "realized_outcome"):
            text = _as_text(evaluation.get(key_name))
            if text:
                return text

    for key_name in ("home_win",):
        text = _as_text(entry.get(key_name))
        if text:
            return text

    return ""


def _resolve_export_outcome_entry(
    candidate: Mapping[str, Any],
    outcome_lookup: Mapping[str, Mapping[str, Any]] | None,
) -> tuple[Mapping[str, Any] | None, str]:
    outcome_map = dict(outcome_lookup or {})
    canonical_key = _as_text(candidate.get("canonical_outcome_key"))
    if canonical_key and canonical_key in outcome_map:
        outcome_entry = outcome_map[canonical_key]
        return outcome_entry, _extract_actual_result(outcome_entry)

    game_id = _as_text(candidate.get("game_id"))
    if game_id and game_id in outcome_map:
        outcome_entry = outcome_map[game_id]
        return outcome_entry, _extract_actual_result(outcome_entry)

    return None, ""


def _build_original_source_refs(
    source_record: Mapping[str, Any],
    candidate: Mapping[str, Any],
    outcome_entry: Mapping[str, Any] | None,
) -> dict[str, Any]:
    original_source_refs: dict[str, Any] = {}
    if isinstance(source_record.get("source_refs"), Mapping):
        original_source_refs = dict(source_record.get("source_refs") or {})
    if not original_source_refs:
        original_source_refs = {
            "prediction_registry": _as_text(candidate.get("source_refs", {}).get("prediction_record")),
        }

    original_source_refs["postgame_outcome"] = _as_text(
        (outcome_entry or {}).get("game_id") or (outcome_entry or {}).get("canonical_outcome_key") or candidate.get("game_id")
    )
    return original_source_refs


def _build_export_field_notes(
    candidate: Mapping[str, Any],
    joined_actual_result: str,
) -> dict[str, list[str]]:
    backfill_reasons: list[str] = []
    inferred_fields: list[str] = []
    unsafe_to_infer_fields: list[str] = []

    if not _as_text(candidate.get("strategy_id")):
        unsafe_to_infer_fields.append("strategy_id")
        backfill_reasons.append("strategy_id is missing and cannot be safely inferred")
    if not _as_text(candidate.get("lifecycle_state_at_prediction_time")):
        unsafe_to_infer_fields.append("lifecycle_state_at_prediction_time")
        backfill_reasons.append("lifecycle_state_at_prediction_time is missing and cannot be safely inferred")
    if candidate.get("canonical_outcome_key_used_fallback"):
        inferred_fields.append("canonical_outcome_key_fallback")
        backfill_reasons.append("canonical_outcome_key was derived from game_id fallback")
    if not _as_text(candidate.get("actual_result")):
        unsafe_to_infer_fields.append("actual_result")
        backfill_reasons.append("actual_result is missing and cannot be safely inferred")
    elif joined_actual_result:
        backfill_reasons.append("actual_result joined from postgame outcome")

    if not backfill_reasons:
        backfill_reasons.append("row is ready for historical backfill automation")

    return {
        "backfill_reasons": backfill_reasons,
        "inferred_fields": inferred_fields,
        "unsafe_to_infer_fields": unsafe_to_infer_fields,
    }


def build_backfill_candidate_export_row(
    prediction_entry: Mapping[str, Any],
    outcome_lookup: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    source_record = dict(prediction_entry or {})
    candidate = build_backfill_candidate(source_record)
    outcome_entry, joined_actual_result = _resolve_export_outcome_entry(candidate, outcome_lookup)
    if joined_actual_result:
        candidate["actual_result"] = joined_actual_result
        candidate_flags = [flag for flag in candidate.get("data_quality_flags", []) if flag != "MISSING_ACTUAL_RESULT"]
        candidate["data_quality_flags"] = candidate_flags
    elif "MISSING_ACTUAL_RESULT" not in set(candidate.get("data_quality_flags") or []):
        candidate["data_quality_flags"] = list(candidate.get("data_quality_flags") or []) + ["MISSING_ACTUAL_RESULT"]

    notes = _build_export_field_notes(candidate, joined_actual_result)

    export_row = {
        "original_source_refs": _build_original_source_refs(source_record, candidate, outcome_entry),
        "proposed_strategy_id": candidate.get("strategy_id", ""),
        "proposed_lifecycle_state_at_prediction_time": candidate.get("lifecycle_state_at_prediction_time", ""),
        "proposed_canonical_outcome_key": candidate.get("canonical_outcome_key", ""),
        "proposed_actual_result": candidate.get("actual_result", ""),
        "backfill_priority": "P1" if candidate.get("canonical_outcome_key_used_fallback") else "P0",
        **notes,
        "data_quality_flags": list(candidate.get("data_quality_flags") or []),
    }
    from wbc_backend.reporting.strategy_replay_backfill_plan import classify_backfill_priority

    export_row["backfill_priority"] = classify_backfill_priority(
        {
            "strategy_id": export_row["proposed_strategy_id"],
            "lifecycle_state_at_prediction_time": export_row["proposed_lifecycle_state_at_prediction_time"],
            "canonical_outcome_key": export_row["proposed_canonical_outcome_key"],
            "actual_result": export_row["proposed_actual_result"],
            "confidence": candidate.get("confidence"),
            "edge": candidate.get("edge"),
            "data_quality_flags": export_row["data_quality_flags"],
        }
    )

    if not export_row["backfill_reasons"]:
        export_row["backfill_reasons"].append("row is ready for historical backfill automation")

    return export_row


def build_backfill_candidate_export_rows(
    prediction_entries: list[dict[str, Any]],
    outcome_entries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    outcome_lookup = _build_outcome_lookup(outcome_entries)
    return [
        build_backfill_candidate_export_row(entry, outcome_lookup)
        for entry in prediction_entries
        if isinstance(entry, dict)
    ]
