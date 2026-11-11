from __future__ import annotations

import json
from pathlib import Path

import pytest

from wbc_backend.domain.schemas import AnalyzeRequest
from wbc_backend.reporting.strategy_replay_runtime_metadata import (
    build_analyze_request_replay_metadata,
    load_runtime_strategy_metadata_registry,
    prepare_runtime_strategy_metadata_request_kwargs,
    resolve_runtime_strategy_metadata,
    validate_runtime_metadata_injection_inputs,
)


def _registry_record(**overrides: object) -> dict[str, object]:
    record = {
        "strategy_id": "wbc.pool_c.ml_v1",
        "strategy_name": "Pool C ML v1",
        "current_lifecycle_state": "online",
        "lifecycle_state_source": "explicit_registry",
        "lifecycle_state_updated_at": "2026-05-10T08:00:00Z",
        "owner_module": "wbc_backend.reporting.strategy_registry",
        "audit_source": "strategy_registry_seed",
        "allowed_for_future_writes": True,
        "allowed_for_historical_backfill": False,
        "metadata_version": "p28a-1.0",
        "notes": "Example only.",
        "source_kind": "registry",
    }
    record.update(overrides)
    return record


def _write_registry(tmp_path: Path, records: list[dict[str, object]]) -> Path:
    path = tmp_path / "strategy_registry.json"
    path.write_text(
        json.dumps({"registry_kind": "example_non_production", "records": records}, ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def test_explicit_registry_and_strategy_id_resolves_metadata(tmp_path: Path) -> None:
    path = _write_registry(tmp_path, [_registry_record()])
    records = load_runtime_strategy_metadata_registry(path)
    resolution = resolve_runtime_strategy_metadata("wbc.pool_c.ml_v1", records)

    assert resolution["matched_record"]["strategy_name"] == "Pool C ML v1"
    assert resolution["matched_record"]["allowed_for_future_writes"] is True

    kwargs = prepare_runtime_strategy_metadata_request_kwargs("wbc.pool_c.ml_v1", records)
    assert kwargs == {
        "strategy_id": "wbc.pool_c.ml_v1",
        "strategy_name": "Pool C ML v1",
        "lifecycle_state_at_prediction_time": "online",
        "current_lifecycle_state": "online",
    }


def test_missing_registry_non_strict_leaves_metadata_absent() -> None:
    kwargs = prepare_runtime_strategy_metadata_request_kwargs("wbc.pool_c.ml_v1", None)
    assert kwargs == {}


def test_missing_registry_strict_fails() -> None:
    with pytest.raises(ValueError, match="missing runtime strategy metadata registry"):
        prepare_runtime_strategy_metadata_request_kwargs("wbc.pool_c.ml_v1", None, strict=True)


def test_unknown_strategy_id_non_strict_leaves_metadata_absent(tmp_path: Path) -> None:
    path = _write_registry(tmp_path, [_registry_record()])
    records = load_runtime_strategy_metadata_registry(path)

    kwargs = prepare_runtime_strategy_metadata_request_kwargs("missing.strategy", records)
    assert kwargs == {}


def test_unknown_strategy_id_strict_fails(tmp_path: Path) -> None:
    path = _write_registry(tmp_path, [_registry_record()])
    records = load_runtime_strategy_metadata_registry(path)

    with pytest.raises(ValueError, match="unknown strategy_id"):
        prepare_runtime_strategy_metadata_request_kwargs("missing.strategy", records, strict=True)


def test_allowed_for_future_writes_false_blocks_injection(tmp_path: Path) -> None:
    path = _write_registry(tmp_path, [_registry_record(allowed_for_future_writes=False)])
    records = load_runtime_strategy_metadata_registry(path)

    assert prepare_runtime_strategy_metadata_request_kwargs("wbc.pool_c.ml_v1", records) == {}
    with pytest.raises(ValueError, match="allowed_for_future_writes must be true"):
        prepare_runtime_strategy_metadata_request_kwargs("wbc.pool_c.ml_v1", records, strict=True)


def test_allowed_for_historical_backfill_false_remains_unchanged(tmp_path: Path) -> None:
    path = _write_registry(tmp_path, [_registry_record()])
    records = load_runtime_strategy_metadata_registry(path)
    resolution = resolve_runtime_strategy_metadata("wbc.pool_c.ml_v1", records)
    record = resolution["matched_record"]

    assert record["allowed_for_historical_backfill"] is False
    assert build_analyze_request_replay_metadata(record) == {
        "strategy_id": "wbc.pool_c.ml_v1",
        "strategy_name": "Pool C ML v1",
        "lifecycle_state_at_prediction_time": "online",
        "current_lifecycle_state": "online",
    }


def test_single_book_is_not_accepted_as_registry_source(tmp_path: Path) -> None:
    path = _write_registry(tmp_path, [_registry_record(source_kind="SINGLE_BOOK")])
    records = load_runtime_strategy_metadata_registry(path)
    with pytest.raises(ValueError, match="SINGLE_BOOK"):
        prepare_runtime_strategy_metadata_request_kwargs("wbc.pool_c.ml_v1", records, strict=True)


def test_best_bet_strategy_is_not_accepted_as_registry_source(tmp_path: Path) -> None:
    path = _write_registry(tmp_path, [_registry_record(source_kind="best_bet_strategy")])
    records = load_runtime_strategy_metadata_registry(path)
    with pytest.raises(ValueError, match="best_bet_strategy"):
        prepare_runtime_strategy_metadata_request_kwargs("wbc.pool_c.ml_v1", records, strict=True)


def test_query_strategy_id_alone_is_not_enough_without_registry() -> None:
    assert validate_runtime_metadata_injection_inputs("wbc.pool_c.ml_v1", None) == [
        "missing runtime strategy metadata registry",
    ]


def test_analyze_request_receives_explicit_metadata_when_resolved(tmp_path: Path) -> None:
    path = _write_registry(tmp_path, [_registry_record()])
    records = load_runtime_strategy_metadata_registry(path)
    kwargs = prepare_runtime_strategy_metadata_request_kwargs("wbc.pool_c.ml_v1", records)

    request = AnalyzeRequest(game_id="C07", line_total=7.5, line_spread_home=-1.5, **kwargs)

    assert request.strategy_id == "wbc.pool_c.ml_v1"
    assert request.strategy_name == "Pool C ML v1"
    assert request.lifecycle_state_at_prediction_time == "online"
    assert request.current_lifecycle_state == "online"


def test_existing_analyze_request_creation_remains_backward_compatible() -> None:
    request = AnalyzeRequest(game_id="C07", line_total=7.5, line_spread_home=-1.5)
    assert request.game_id == "C07"
    assert request.strategy_id is None


def test_no_production_db_access(tmp_path: Path) -> None:
    path = _write_registry(tmp_path, [_registry_record()])
    records = load_runtime_strategy_metadata_registry(path)
    summary = resolve_runtime_strategy_metadata("wbc.pool_c.ml_v1", records)
    assert "db" not in json.dumps(summary).lower()
