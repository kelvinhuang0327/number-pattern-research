"""Tests for the read-only strategy replay service/query skeleton."""
from __future__ import annotations

import json
from pathlib import Path

from wbc_backend.reporting.strategy_replay_adapter import build_strategy_replay_rows
from wbc_backend.reporting.strategy_replay_service import (
    build_strategy_replay_response,
    filter_strategy_replay_rows,
    get_strategy_replay_rows_from_paths,
    paginate_strategy_replay_rows,
    parse_strategy_replay_query,
    sort_strategy_replay_rows,
)


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> Path:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False))
            handle.write("\n")
    return path


def _prediction_entry(game_id: str, strategy_id: str, market_type: str, timestamp: str, lifecycle_state: str = "online") -> dict[str, object]:
    return {
        "game_id": game_id,
        "recorded_at_utc": timestamp,
        "strategy_id": strategy_id,
        "strategy_name": f"Strategy {strategy_id}",
        "lifecycle_state_at_prediction_time": lifecycle_state,
        "current_lifecycle_state": "offline",
        "market_type": market_type,
        "recommendation": "HOME",
        "confidence": 0.6,
        "edge": 0.02,
    }


def _outcome_entry(game_id: str, actual_result: str | None) -> dict[str, object]:
    return {
        "game_id": game_id,
        "canonical_outcome_key": game_id,
        "actual_result": actual_result,
    }


def _sample_rows() -> list[dict[str, object]]:
    return build_strategy_replay_rows(
        [
            _prediction_entry("G1", "strat_1", "moneyline", "2026-05-10T08:00:00Z", "online"),
            _prediction_entry("G2", "strat_2", "total", "2026-05-10T09:00:00Z", "offline"),
            _prediction_entry("G3", "strat_3", "moneyline", "2026-05-11T08:00:00Z", "observation"),
        ],
        [
            _outcome_entry("G1", "win"),
            _outcome_entry("G2", "loss"),
            _outcome_entry("G3", None),
        ],
    )


def test_parse_strategy_replay_query_defaults():
    query = parse_strategy_replay_query({})
    assert query.page == 1
    assert query.page_size == 25
    assert query.sort_by == "prediction_timestamp"
    assert query.sort_dir == "desc"


def test_filter_by_strategy_id():
    rows = _sample_rows()
    query = parse_strategy_replay_query({"strategy_id": "strat_2"})
    filtered = filter_strategy_replay_rows(rows, query)
    assert len(filtered) == 1
    assert filtered[0]["strategy_id"] == "strat_2"


def test_filter_by_lifecycle_state():
    rows = _sample_rows()
    query = parse_strategy_replay_query({"lifecycle_state": "offline"})
    filtered = filter_strategy_replay_rows(rows, query)
    assert len(filtered) == 1
    assert filtered[0]["lifecycle_state_at_prediction_time"] == "offline"


def test_filter_by_market_type():
    rows = _sample_rows()
    query = parse_strategy_replay_query({"market_type": "moneyline"})
    filtered = filter_strategy_replay_rows(rows, query)
    assert len(filtered) == 2


def test_filter_by_date_range():
    rows = _sample_rows()
    query = parse_strategy_replay_query({"date_from": "2026-05-11", "date_to": "2026-05-11"})
    filtered = filter_strategy_replay_rows(rows, query)
    assert len(filtered) == 1
    assert filtered[0]["game_id"] == "G3"


def test_filter_by_settlement_status():
    rows = _sample_rows()
    query = parse_strategy_replay_query({"settlement_status": "PENDING"})
    filtered = filter_strategy_replay_rows(rows, query)
    assert len(filtered) == 1
    assert filtered[0]["game_id"] == "G3"


def test_sorting_and_pagination():
    rows = _sample_rows()
    sorted_rows = sort_strategy_replay_rows(rows, "prediction_timestamp", "asc")
    assert [row["game_id"] for row in sorted_rows] == ["G1", "G2", "G3"]
    page_rows, total_rows, total_pages = paginate_strategy_replay_rows(sorted_rows, 2, 2)
    assert total_rows == 3
    assert total_pages == 2
    assert [row["game_id"] for row in page_rows] == ["G3"]


def test_build_response_includes_required_metadata():
    rows = _sample_rows()
    query = parse_strategy_replay_query({"page": 1, "page_size": 2})
    response = build_strategy_replay_response(rows, query)
    assert response["source_mode"] == "READ_ONLY"
    assert response["ui_ready"] is False
    assert response["page"] == 1
    assert response["page_size"] == 2
    assert response["total_rows"] == 3
    assert response["total_pages"] == 2
    assert response["data_quality_summary"]["total_candidate_rows"] == 3
    assert isinstance(response["warnings"], list)


def test_invalid_params_are_handled_conservatively():
    query = parse_strategy_replay_query({"page": "bad", "page_size": 999, "sort_by": "nope", "sort_dir": "sideways"})
    assert query.page == 1
    assert query.page_size == 100
    assert query.sort_by == "prediction_timestamp"
    assert query.sort_dir == "desc"
    assert query.warnings


def test_no_production_db_access(tmp_path: Path):
    prediction_path = _write_jsonl(
        tmp_path / "predictions.jsonl",
        [_prediction_entry("G1", "strat_1", "moneyline", "2026-05-10T08:00:00Z")],
    )
    outcome_path = _write_jsonl(tmp_path / "outcomes.jsonl", [_outcome_entry("G1", "win")])
    response = get_strategy_replay_rows_from_paths(str(prediction_path), str(outcome_path), parse_strategy_replay_query({}))
    assert response["source_mode"] == "READ_ONLY"
    assert response["rows"]


def test_fastapi_endpoint_smoke(monkeypatch):
    import orchestrator.api as orchestrator_api

    monkeypatch.setattr(
        orchestrator_api,
        "build_strategy_replay_query_from_app_config",
        lambda config, params=None: (
            parse_strategy_replay_query(params),
            {
                "rows": [{"strategy_id": "strat_1"}],
                "page": 1,
                "page_size": 25,
                "total_rows": 1,
                "total_pages": 1,
                "filters_applied": {},
                "data_quality_summary": {"total_candidate_rows": 1, "rows_missing_strategy_id": 0, "rows_missing_lifecycle_state_at_prediction_time": 0, "rows_missing_canonical_outcome_key": 0, "rows_missing_actual_result": 0, "rows_mvp_ready": 1},
                "source_mode": "READ_ONLY",
                "ui_ready": False,
                "warnings": [],
            },
        ),
    )

    data = orchestrator_api.get_strategy_replay_history()
    assert data["source_mode"] == "READ_ONLY"
    assert data["ui_ready"] is False
