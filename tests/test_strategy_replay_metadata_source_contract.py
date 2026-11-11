from __future__ import annotations

from wbc_backend.reporting.strategy_replay_metadata_source_contract import (
    NEEDS_NEW_SOURCE,
    NOT_AVAILABLE,
    SAFE_SOURCE,
    UNSAFE_HINT,
    build_required_metadata_source_contract,
    classify_strategy_replay_metadata_source,
    summarize_metadata_source_coverage,
    validate_strategy_replay_metadata_source,
)


def _safe_source() -> dict[str, object]:
    return {
        "source_id": "strategy_registry_v1",
        "source_name": "Strategy Registry",
        "source_type": "registry",
        "provided_fields": [
            "strategy_id",
            "strategy_name",
            "lifecycle_state_at_prediction_time",
            "current_lifecycle_state",
        ],
        "explicit_identity": True,
        "lifecycle_snapshot_time": "prediction_write_time",
        "owner_module": "wbc_backend.reporting.strategy_registry",
        "durability": "required",
        "auditability": "required",
        "allowed_for_future_writes": True,
        "allowed_for_historical_backfill": False,
        "failure_modes": ["missing source row"],
        "validation_rules": [
            "strategy_id must be explicit",
            "strategy_name must be explicit",
            "lifecycle_state_at_prediction_time must be explicit",
            "current_lifecycle_state cannot replace lifecycle_state_at_prediction_time",
            "SINGLE_BOOK is not strategy identity",
            "best_bet_strategy is not strategy identity",
            "query filter strategy_id is not a write source",
        ],
    }


def test_safe_source_requires_explicit_identity() -> None:
    source = _safe_source()
    assert classify_strategy_replay_metadata_source(source) == SAFE_SOURCE
    assert validate_strategy_replay_metadata_source(source) == []


def test_missing_source_is_not_available() -> None:
    assert classify_strategy_replay_metadata_source(None) == NOT_AVAILABLE
    assert validate_strategy_replay_metadata_source(None) == ["missing source"]


def test_missing_explicit_identity_needs_new_source() -> None:
    source = _safe_source()
    source["explicit_identity"] = False
    assert classify_strategy_replay_metadata_source(source) == NEEDS_NEW_SOURCE
    assert any("explicit_identity" in error for error in validate_strategy_replay_metadata_source(source))


def test_unsafe_hints_are_rejected() -> None:
    assert classify_strategy_replay_metadata_source({"source_type": "execution_strategy"}) == UNSAFE_HINT
    assert classify_strategy_replay_metadata_source({"source_type": "best_bet_strategy"}) == UNSAFE_HINT
    assert classify_strategy_replay_metadata_source({"source_type": "query_filter"}) == UNSAFE_HINT


def test_current_lifecycle_state_cannot_replace_snapshot() -> None:
    source = _safe_source()
    source["validation_rules"] = ["strategy_id must be explicit"]
    assert classify_strategy_replay_metadata_source(source) == NEEDS_NEW_SOURCE
    assert any(
        "current_lifecycle_state cannot replace lifecycle_state_at_prediction_time" in error
        for error in validate_strategy_replay_metadata_source(source)
    )


def test_query_filter_is_not_write_source() -> None:
    source = _safe_source()
    source["source_type"] = "query_filter"
    assert classify_strategy_replay_metadata_source(source) == UNSAFE_HINT


def test_summarize_metadata_source_coverage_counts_by_classification() -> None:
    summary = summarize_metadata_source_coverage([
        _safe_source(),
        {"source_type": "execution_strategy"},
        {},
    ])
    assert summary["total_sources"] == 3
    assert summary["counts"][SAFE_SOURCE] == 1
    assert summary["counts"][UNSAFE_HINT] == 1
    assert summary["counts"][NOT_AVAILABLE] == 1
    assert summary["required_contract"]["explicit_identity"] is True


def test_no_production_db_access() -> None:
    contract = build_required_metadata_source_contract()
    assert "db" not in str(contract).lower()
