from __future__ import annotations

import json
from pathlib import Path

from wbc_backend.reporting.strategy_replay_metadata_registry import (
    build_strategy_metadata_record,
    find_strategy_metadata_by_id,
    load_strategy_metadata_registry,
    summarize_strategy_metadata_registry,
    validate_strategy_metadata_record,
    validate_strategy_metadata_registry,
)


def _valid_record(**overrides: object) -> dict[str, object]:
    record = build_strategy_metadata_record(
        strategy_id="strategy.pool_c.ml_v1",
        strategy_name="Pool C ML v1",
        current_lifecycle_state="online",
        lifecycle_state_source="explicit_registry",
        lifecycle_state_updated_at="2026-05-10T08:00:00Z",
        owner_module="wbc_backend.reporting.strategy_registry",
        audit_source="strategy_registry_seed",
        allowed_for_future_writes=True,
    )
    record.update(overrides)
    return record


def test_valid_record_passes() -> None:
    assert validate_strategy_metadata_record(_valid_record()) == []


def test_missing_required_fields_fail() -> None:
    base = _valid_record()
    for field_name in [
        "strategy_id",
        "strategy_name",
        "current_lifecycle_state",
        "lifecycle_state_source",
        "lifecycle_state_updated_at",
        "owner_module",
        "audit_source",
    ]:
        record = dict(base)
        record[field_name] = ""
        assert any(field_name in error for error in validate_strategy_metadata_record(record))


def test_missing_explicit_allowed_for_future_writes_fails() -> None:
    record = _valid_record()
    record.pop("allowed_for_future_writes")
    assert any("allowed_for_future_writes" in error for error in validate_strategy_metadata_record(record))


def test_invalid_lifecycle_sources_fail() -> None:
    record = _valid_record(lifecycle_state_source="current_lifecycle_state")
    assert any("current_lifecycle_state fallback" in error for error in validate_strategy_metadata_record(record))


def test_invalid_hint_sources_fail() -> None:
    assert any(
        "SINGLE_BOOK" in error
        for error in validate_strategy_metadata_record(_valid_record(source_kind="SINGLE_BOOK"))
    )
    assert any(
        "best_bet_strategy" in error
        for error in validate_strategy_metadata_record(_valid_record(source_kind="best_bet_strategy"))
    )
    assert any(
        "write source" in error
        for error in validate_strategy_metadata_record(_valid_record(audit_source="strategy_id query filter"))
    )


def test_duplicate_strategy_id_fails_registry_validation() -> None:
    records = [_valid_record(), _valid_record(owner_module="alt.module")]
    summary = validate_strategy_metadata_registry(records)
    assert summary["invalid_records"] == 1
    assert summary["duplicate_strategy_ids"] == ["strategy.pool_c.ml_v1"]


def test_allowed_for_historical_backfill_defaults_false() -> None:
    record = _valid_record()
    assert record["allowed_for_historical_backfill"] is False


def test_find_strategy_metadata_by_id_works() -> None:
    record = _valid_record()
    assert find_strategy_metadata_by_id([record], "strategy.pool_c.ml_v1") == record
    assert find_strategy_metadata_by_id([record], "missing") is None


def test_summary_counts_valid_invalid_and_future_write_allowed() -> None:
    valid = _valid_record()
    invalid = _valid_record(strategy_id="", allowed_for_future_writes=False)
    summary = summarize_strategy_metadata_registry([valid, invalid])
    assert summary["total_records"] == 2
    assert summary["valid_records"] == 1
    assert summary["invalid_records"] == 1
    assert summary["future_write_allowed_records"] == 1
    assert summary["backfill_defaults_false_records"] == 2


def test_load_registry_supports_example_payload(tmp_path: Path) -> None:
    path = tmp_path / "registry.example.json"
    path.write_text(
        json.dumps(
            {
                "registry_kind": "example_non_production",
                "records": [_valid_record()],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    records = load_strategy_metadata_registry(path)
    assert len(records) == 1
    assert records[0]["strategy_id"] == "strategy.pool_c.ml_v1"


def test_no_production_db_access() -> None:
    summary = summarize_strategy_metadata_registry([_valid_record()])
    assert "db" not in json.dumps(summary).lower()
