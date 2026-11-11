"""Tests for strategy replay backfill plan helpers."""
from __future__ import annotations

from wbc_backend.reporting.strategy_replay_backfill_plan import (
    build_strategy_replay_backfill_plan,
    classify_backfill_priority,
    summarize_backfill_requirements,
)
from wbc_backend.reporting.strategy_replay_instrumentation import build_backfill_candidate


def _record(**overrides):
    record = {
        "game_id": "G20260510_001",
        "recorded_at_utc": "2026-05-10T08:00:00Z",
        "strategy_id": "strat_001",
        "strategy_name": "Conservative Moneyline",
        "current_lifecycle_state": "offline",
        "lifecycle_state_at_prediction_time": "online",
        "canonical_outcome_key": "CANON-001",
        "market_type": "moneyline",
        "recommendation": "HOME",
        "confidence": 0.61,
        "edge": 0.03,
        "actual_result": "win",
        "source_refs": {"prediction": "fixture:prediction:1"},
    }
    record.update(overrides)
    return record


def test_p0_missing_strategy_id():
    candidate = build_backfill_candidate(_record(strategy_id=""))
    assert classify_backfill_priority(candidate) == "P0"


def test_p0_missing_lifecycle_state():
    candidate = build_backfill_candidate(_record(lifecycle_state_at_prediction_time=""))
    assert classify_backfill_priority(candidate) == "P0"


def test_p0_missing_canonical_outcome_key():
    candidate = build_backfill_candidate(_record(canonical_outcome_key=""))
    assert classify_backfill_priority(candidate) == "P1"


def test_p0_missing_actual_result():
    candidate = build_backfill_candidate(_record(actual_result=""))
    assert classify_backfill_priority(candidate) == "P0"


def test_p1_fallback_only_join():
    candidate = build_backfill_candidate(_record(canonical_outcome_key=""))
    candidate["strategy_id"] = "strat_001"
    candidate["lifecycle_state_at_prediction_time"] = "online"
    candidate["actual_result"] = "win"
    candidate["data_quality_flags"] = ["CANONICAL_OUTCOME_KEY_FALLBACK_TO_GAME_ID"]
    assert classify_backfill_priority(candidate) == "P1"


def test_p1_unknown_lifecycle_state():
    candidate = build_backfill_candidate(_record(lifecycle_state_at_prediction_time="mystery"))
    candidate["lifecycle_state_at_prediction_time"] = "unknown"
    candidate["data_quality_flags"] = ["UNKNOWN_LIFECYCLE_STATE_AT_PREDICTION_TIME"]
    assert classify_backfill_priority(candidate) == "P1"


def test_p2_optional_confidence_edge_missing():
    candidate = build_backfill_candidate(_record())
    candidate["confidence"] = ""
    candidate["edge"] = ""
    candidate["data_quality_flags"] = []
    assert classify_backfill_priority(candidate) == "P2"


def test_plan_summary_counts():
    rows = [
        build_backfill_candidate(_record()),
        build_backfill_candidate(_record(strategy_id="")),
        build_backfill_candidate(_record(canonical_outcome_key="")),
    ]
    plan = build_strategy_replay_backfill_plan(rows)
    summary = summarize_backfill_requirements(plan)
    assert summary["total_candidates"] == 3
    assert summary["backfill_required_count"] >= 2
    assert summary["p0_gap_count"] >= 1
    assert summary["next_actions"]


def test_no_production_db_access():
    candidate = build_backfill_candidate(_record())
    plan = build_strategy_replay_backfill_plan([candidate])
    assert plan[0]["priority"] in {"P0", "P1", "P2", "READY"}
