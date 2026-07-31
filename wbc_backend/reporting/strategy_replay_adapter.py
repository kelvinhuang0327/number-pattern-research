"""Read-only adapters for strategy replay historical rows.

These helpers bridge existing registry/outcome JSONL data into the strategy replay
row contract without writing to production storage.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from wbc_backend.reporting.strategy_replay_history import build_strategy_replay_row


def load_jsonl_entries(path: str | Path) -> list[dict[str, Any]]:
    """Load JSONL rows from *path* without mutation."""
    source_path = Path(path)
    if not source_path.exists():
        return []

    rows: list[dict[str, Any]] = []
    with source_path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def load_prediction_registry_entries(path: str | Path) -> list[dict[str, Any]]:
    return load_jsonl_entries(path)


def load_postgame_outcome_entries(path: str | Path) -> list[dict[str, Any]]:
    return load_jsonl_entries(path)


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _extract_canonical_outcome_key(entry: dict[str, Any]) -> str:
    for key_name in (
        "canonical_outcome_key",
        "canonical_game_id",
        "game_id",
    ):
        candidate = _as_text(entry.get(key_name))
        if candidate:
            return candidate
    return ""


def _extract_actual_result(entry: dict[str, Any]) -> object:
    if "actual_result" in entry:
        return entry.get("actual_result")

    evaluation = entry.get("evaluation")
    if isinstance(evaluation, dict):
        for key_name in (
            "actual_result",
            "result_status",
            "realized_outcome",
        ):
            if key_name in evaluation:
                return evaluation.get(key_name)

    for key_name in ("result_status", "realized_outcome", "home_win"):
        if key_name in entry:
            return entry.get(key_name)

    return None


def build_outcome_lookup(entries: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Build a conservative lookup map keyed by explicit canonical key and game_id."""
    lookup: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue

        canonical_key = _extract_canonical_outcome_key(entry)
        if canonical_key:
            lookup[canonical_key] = entry

        game_id = _as_text(entry.get("game_id"))
        if game_id and game_id not in lookup:
            lookup[game_id] = entry

    return lookup


def adapt_prediction_to_replay_candidate(
    prediction_entry: dict[str, Any],
    outcome_lookup: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Adapt a raw prediction registry row into the replay row contract."""
    source_entry = dict(prediction_entry or {})
    canonical_outcome_key = _extract_canonical_outcome_key(source_entry)
    outcome_entry = None
    used_fallback = False

    if outcome_lookup is not None:
        if canonical_outcome_key and canonical_outcome_key in outcome_lookup:
            outcome_entry = outcome_lookup[canonical_outcome_key]
        else:
            game_id = _as_text(source_entry.get("game_id"))
            if game_id and game_id in outcome_lookup:
                outcome_entry = outcome_lookup[game_id]
                used_fallback = True

    actual_result = _extract_actual_result(outcome_entry or {})
    replay_row = build_strategy_replay_row(
        {
            "strategy_id": source_entry.get("strategy_id"),
            "strategy_name": source_entry.get("strategy_name"),
            "lifecycle_state_at_prediction_time": source_entry.get("lifecycle_state_at_prediction_time"),
            "current_lifecycle_state": source_entry.get("current_lifecycle_state"),
            "prediction_timestamp": source_entry.get("prediction_timestamp") or source_entry.get("recorded_at_utc"),
            "game_id": source_entry.get("game_id"),
            "canonical_outcome_key": canonical_outcome_key,
            "market_type": source_entry.get("market_type") or source_entry.get("request", {}).get("market_type"),
            "recommendation": source_entry.get("recommendation") or source_entry.get("decision_report", {}).get("decision"),
            "confidence": source_entry.get("confidence") or source_entry.get("game_output", {}).get("confidence_index"),
            "edge": source_entry.get("edge") or source_entry.get("portfolio_metrics", {}).get("edge"),
            "actual_result": actual_result,
            "source_refs": {
                "prediction_registry": _as_text(source_entry.get("game_id") or source_entry.get("recorded_at_utc") or "prediction_registry_row"),
                "postgame_outcome": _as_text((outcome_entry or {}).get("game_id") or canonical_outcome_key or "postgame_outcome_row"),
            },
        }
    )

    if used_fallback:
        flags = list(replay_row.get("data_quality_flags") or [])
        if "CANONICAL_OUTCOME_KEY_FALLBACK_TO_GAME_ID" not in flags:
            flags.append("CANONICAL_OUTCOME_KEY_FALLBACK_TO_GAME_ID")
        replay_row["data_quality_flags"] = flags

    return replay_row


def build_strategy_replay_rows(
    prediction_entries: list[dict[str, Any]],
    outcome_entries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    outcome_lookup = build_outcome_lookup(outcome_entries)
    return [
        adapt_prediction_to_replay_candidate(entry, outcome_lookup=outcome_lookup)
        for entry in prediction_entries
        if isinstance(entry, dict)
    ]


def summarize_strategy_replay_rows(rows: list[dict[str, Any]]) -> dict[str, int]:
    summary = {
        "total_candidate_rows": len(rows),
        "rows_missing_strategy_id": 0,
        "rows_missing_lifecycle_state_at_prediction_time": 0,
        "rows_missing_canonical_outcome_key": 0,
        "rows_missing_actual_result": 0,
        "rows_mvp_ready": 0,
    }

    for row in rows:
        flags = set(row.get("data_quality_flags") or [])
        if "MISSING_STRATEGY_ID" in flags:
            summary["rows_missing_strategy_id"] += 1
        if "MISSING_LIFECYCLE_STATE_AT_PREDICTION_TIME" in flags:
            summary["rows_missing_lifecycle_state_at_prediction_time"] += 1
        if "MISSING_CANONICAL_OUTCOME_KEY" in flags:
            summary["rows_missing_canonical_outcome_key"] += 1
        if "MISSING_ACTUAL_RESULT" in flags:
            summary["rows_missing_actual_result"] += 1

        if not flags.intersection(
            {
                "MISSING_STRATEGY_ID",
                "MISSING_LIFECYCLE_STATE_AT_PREDICTION_TIME",
                "MISSING_CANONICAL_OUTCOME_KEY",
                "MISSING_ACTUAL_RESULT",
            }
        ):
            summary["rows_mvp_ready"] += 1

    return summary
