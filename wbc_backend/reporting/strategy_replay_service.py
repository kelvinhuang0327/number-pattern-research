"""Read-only service/query helpers for the strategy replay API skeleton."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from math import ceil
from typing import Any

from wbc_backend.config.settings import AppConfig
from wbc_backend.reporting.strategy_replay_adapter import (
    build_strategy_replay_rows,
    load_postgame_outcome_entries,
    load_prediction_registry_entries,
    summarize_strategy_replay_rows,
)

_VALID_SORT_FIELDS = {
    "prediction_timestamp",
    "strategy_id",
    "lifecycle_state_at_prediction_time",
    "market_type",
    "settlement_status",
    "game_id",
}
_VALID_SORT_DIRECTIONS = {"asc", "desc"}


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _parse_date_text(value: object) -> date | None:
    text = _as_text(value)
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _row_date_value(row: dict[str, Any]) -> date | None:
    for key_name in ("prediction_timestamp", "recorded_at_utc"):
        text = _as_text(row.get(key_name))
        if not text:
            continue
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
        except ValueError:
            parsed = _parse_date_text(text)
            if parsed:
                return parsed
    return None


@dataclass(frozen=True)
class StrategyReplayQuery:
    strategy_id: str | None = None
    lifecycle_state: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    market_type: str | None = None
    settlement_status: str | None = None
    page: int = 1
    page_size: int = 25
    sort_by: str = "prediction_timestamp"
    sort_dir: str = "desc"
    warnings: list[str] = field(default_factory=list)


def parse_strategy_replay_query(params: dict[str, Any] | None) -> StrategyReplayQuery:
    raw = dict(params or {})
    warnings: list[str] = []

    def _clean_text(key: str) -> str | None:
        value = _as_text(raw.get(key))
        return value or None

    strategy_id = _clean_text("strategy_id")
    lifecycle_state = _clean_text("lifecycle_state")
    market_type = _clean_text("market_type")
    settlement_status = _clean_text("settlement_status")

    date_from = _parse_date_text(raw.get("date_from"))
    if raw.get("date_from") and date_from is None:
        warnings.append("invalid date_from ignored")
    date_to = _parse_date_text(raw.get("date_to"))
    if raw.get("date_to") and date_to is None:
        warnings.append("invalid date_to ignored")

    try:
        page = int(raw.get("page", 1) or 1)
    except (TypeError, ValueError):
        page = 1
        warnings.append("invalid page defaulted to 1")
    page = max(page, 1)

    try:
        page_size = int(raw.get("page_size", 25) or 25)
    except (TypeError, ValueError):
        page_size = 25
        warnings.append("invalid page_size defaulted to 25")
    page_size = min(max(page_size, 1), 100)

    sort_by = _as_text(raw.get("sort_by")) or "prediction_timestamp"
    if sort_by not in _VALID_SORT_FIELDS:
        warnings.append(f"unsupported sort_by '{sort_by}' defaulted to prediction_timestamp")
        sort_by = "prediction_timestamp"

    sort_dir = _as_text(raw.get("sort_dir")).lower() or "desc"
    if sort_dir not in _VALID_SORT_DIRECTIONS:
        warnings.append(f"unsupported sort_dir '{sort_dir}' defaulted to desc")
        sort_dir = "desc"

    return StrategyReplayQuery(
        strategy_id=strategy_id,
        lifecycle_state=lifecycle_state,
        date_from=date_from,
        date_to=date_to,
        market_type=market_type,
        settlement_status=settlement_status,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_dir=sort_dir,
        warnings=warnings,
    )


def filter_strategy_replay_rows(rows: list[dict[str, Any]], query: StrategyReplayQuery) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    for row in rows:
        if query.strategy_id and _as_text(row.get("strategy_id")) != query.strategy_id:
            continue
        if query.lifecycle_state and _as_text(row.get("lifecycle_state_at_prediction_time")) != query.lifecycle_state:
            continue
        if query.market_type and _as_text(row.get("market_type")) != query.market_type:
            continue
        if query.settlement_status and _as_text(row.get("settlement_status")) != query.settlement_status:
            continue

        row_date = _row_date_value(row)
        if query.date_from and row_date and row_date < query.date_from:
            continue
        if query.date_to and row_date and row_date > query.date_to:
            continue
        if (query.date_from or query.date_to) and row_date is None:
            continue

        filtered.append(row)

    return filtered


def sort_strategy_replay_rows(rows: list[dict[str, Any]], sort_by: str, sort_dir: str) -> list[dict[str, Any]]:
    reverse = sort_dir == "desc"

    def _sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
        if sort_by == "prediction_timestamp":
            return (
                _as_text(row.get("prediction_timestamp")),
                _as_text(row.get("strategy_id")),
                _as_text(row.get("game_id")),
            )
        return (
            _as_text(row.get(sort_by)),
            _as_text(row.get("strategy_id")),
            _as_text(row.get("game_id")),
        )

    return sorted(rows, key=_sort_key, reverse=reverse)


def paginate_strategy_replay_rows(rows: list[dict[str, Any]], page: int, page_size: int) -> tuple[list[dict[str, Any]], int, int]:
    total_rows = len(rows)
    total_pages = ceil(total_rows / page_size) if total_rows else 0
    start = (page - 1) * page_size
    end = start + page_size
    return rows[start:end], total_rows, total_pages


def build_strategy_replay_response(rows: list[dict[str, Any]], query: StrategyReplayQuery) -> dict[str, Any]:
    filtered = filter_strategy_replay_rows(rows, query)
    sorted_rows = sort_strategy_replay_rows(filtered, query.sort_by, query.sort_dir)
    page_rows, total_rows, total_pages = paginate_strategy_replay_rows(sorted_rows, query.page, query.page_size)

    data_quality_summary = summarize_strategy_replay_rows(filtered)
    warnings = list(query.warnings)
    if not rows:
        warnings.append("no replay rows available")
    if not filtered:
        warnings.append("no rows matched the applied filters")

    return {
        "rows": page_rows,
        "page": query.page,
        "page_size": query.page_size,
        "total_rows": total_rows,
        "total_pages": total_pages,
        "filters_applied": {
            "strategy_id": query.strategy_id,
            "lifecycle_state": query.lifecycle_state,
            "date_from": query.date_from.isoformat() if query.date_from else None,
            "date_to": query.date_to.isoformat() if query.date_to else None,
            "market_type": query.market_type,
            "settlement_status": query.settlement_status,
            "sort_by": query.sort_by,
            "sort_dir": query.sort_dir,
        },
        "data_quality_summary": data_quality_summary,
        "source_mode": "READ_ONLY",
        "ui_ready": False,
        "warnings": warnings,
    }


def get_strategy_replay_rows_from_paths(
    prediction_registry_path: str,
    postgame_outcomes_path: str,
    query: StrategyReplayQuery,
) -> dict[str, Any]:
    prediction_entries = load_prediction_registry_entries(prediction_registry_path)
    outcome_entries = load_postgame_outcome_entries(postgame_outcomes_path)
    rows = build_strategy_replay_rows(prediction_entries, outcome_entries)
    return build_strategy_replay_response(rows, query)


def build_strategy_replay_query_from_app_config(
    config: AppConfig,
    params: dict[str, Any] | None = None,
) -> tuple[StrategyReplayQuery, dict[str, Any]]:
    query = parse_strategy_replay_query(params)
    payload = get_strategy_replay_rows_from_paths(
        config.sources.prediction_registry_jsonl,
        config.sources.postgame_results_jsonl,
        query,
    )
    return query, payload
