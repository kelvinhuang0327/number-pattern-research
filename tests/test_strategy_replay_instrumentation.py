"""Tests for strategy replay instrumentation helpers."""
from __future__ import annotations

from copy import deepcopy

from wbc_backend.reporting.strategy_replay_instrumentation import (
    build_backfill_candidate,
    build_canonical_outcome_key,
    enrich_prediction_for_strategy_replay,
    resolve_strategy_identity,
    snapshot_lifecycle_state,
    validate_backfill_candidate,
)


def _record(**overrides):
    record = {
        "game_id": "G20260510_001",
        "recorded_at_utc": "2026-05-10T08:00:00Z",
        "strategy_id": "strat_001",
        "strategy_name": "Conservative Moneyline",
        "current_lifecycle_state": "offline",
        "lifecycle_state_at_prediction_time": "online",
        "canonical_outcome_key": "CANON-001",
        "request": {
            "strategy_id": "strat_001",
            "strategy_name": "Conservative Moneyline",
            "market_type": "moneyline",
        },
        "actual_result": "win",
        "source_refs": {"prediction": "fixture:prediction:1"},
    }
    record.update(overrides)
    return record


def test_canonical_outcome_key_uses_explicit_field():
    payload = build_canonical_outcome_key(_record())
    assert payload["value"] == "CANON-001"
    assert payload["source"] == "explicit"
    assert payload["used_fallback"] is False


def test_canonical_outcome_key_fallback_is_flagged():
    payload = build_canonical_outcome_key(_record(canonical_outcome_key="", canonical_game_id=""))
    assert payload["value"] == "G20260510_001"
    assert payload["source"] == "game_id_fallback"
    assert payload["used_fallback"] is True


def test_strategy_identity_is_preserved_when_available():
    identity = resolve_strategy_identity(_record())
    assert identity["strategy_id"] == "strat_001"
    assert identity["strategy_name"] == "Conservative Moneyline"
    assert identity["strategy_id_missing"] is False


def test_missing_strategy_id_is_not_invented():
    identity = resolve_strategy_identity(_record(strategy_id="", request={"strategy_name": "Conservative Moneyline"}))
    assert identity["strategy_id"] == ""
    assert identity["strategy_id_missing"] is True


def test_lifecycle_state_is_snapshotted_when_provided():
    snapshot = snapshot_lifecycle_state(_record())
    assert snapshot["value"] == "online"
    assert snapshot["raw_value"] == "online"
    assert snapshot["missing"] is False


def test_missing_lifecycle_state_is_flagged():
    snapshot = snapshot_lifecycle_state(_record(lifecycle_state_at_prediction_time="", strategy_lifecycle_state=""))
    assert snapshot["missing"] is True
    assert snapshot["value"] == ""


def test_enrichment_flags_fallbacks_and_missing_values():
    record = _record(
        strategy_id="",
        lifecycle_state_at_prediction_time="",
        canonical_outcome_key="",
        actual_result="",
        request={},
    )
    source_copy = deepcopy(record)
    enriched = enrich_prediction_for_strategy_replay(record)
    assert record == source_copy
    assert enriched["strategy_id"] == ""
    assert "MISSING_STRATEGY_ID" in enriched["data_quality_flags"]
    assert "MISSING_LIFECYCLE_STATE_AT_PREDICTION_TIME" in enriched["data_quality_flags"]
    assert "CANONICAL_OUTCOME_KEY_FALLBACK_TO_GAME_ID" in enriched["data_quality_flags"]


def test_backfill_candidate_validation_keeps_missing_fields_visible():
    candidate = build_backfill_candidate(
        _record(
            strategy_id="",
            lifecycle_state_at_prediction_time="",
            canonical_outcome_key="",
            actual_result="",
            request={},
        )
    )
    errors = validate_backfill_candidate(candidate)
    assert "missing strategy_id" in errors
    assert "missing lifecycle_state_at_prediction_time" in errors
    assert "canonical_outcome_key uses game_id fallback" in errors
    assert "missing actual_result" in errors


def test_no_production_db_access():
    candidate = build_backfill_candidate(_record())
    assert isinstance(candidate["source_refs"], dict)
    assert "db" not in " ".join(candidate["source_refs"].values()).lower()
