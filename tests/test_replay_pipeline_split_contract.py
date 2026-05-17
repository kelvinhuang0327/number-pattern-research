"""Replay pipeline split contract tests for P3."""
from __future__ import annotations

from lottery_api.models.replay_pipeline_contract import (
    PIPELINE_STATES,
    blocks_historical_coverage,
    can_write_replay_rows,
    classify_pipeline,
    is_display_only_candidate,
    is_future_waiting_candidate,
    is_reconstruction_candidate,
    requires_future_draw,
)


def _candidate(**overrides):
    base = {
        "strategy_id": "demo_strategy",
        "source_paths": ["lottery_api/engine/demo.py"],
        "has_historical_predictions": False,
        "historical_record_source": "none",
    }
    base.update(overrides)
    return base


def test_pipeline_enum_accepts_all_states():
    assert PIPELINE_STATES == (
        "HISTORICAL_RECONSTRUCTION",
        "FUTURE_WAITING",
        "DISPLAY_ONLY",
        "UNSUPPORTED",
    )


def test_historical_reconstruction_candidate_is_classified():
    candidate = _candidate(
        has_historical_predictions=True,
        historical_record_source="prediction_runs",
    )
    assert classify_pipeline(candidate) == "HISTORICAL_RECONSTRUCTION"
    assert is_reconstruction_candidate(candidate) is True
    assert is_display_only_candidate(candidate) is False
    assert requires_future_draw(candidate) is False


def test_future_waiting_candidate_does_not_block_historical_coverage():
    candidate = _candidate(
        future_waiting=True,
        historical_record_source="prediction_runs",
        has_historical_predictions=True,
    )
    assert classify_pipeline(candidate) == "FUTURE_WAITING"
    assert is_future_waiting_candidate(candidate) is True
    assert requires_future_draw(candidate) is True
    assert blocks_historical_coverage(candidate) is False


def test_display_only_candidate_is_no_history():
    candidate = _candidate()
    assert classify_pipeline(candidate) == "DISPLAY_ONLY"
    assert is_display_only_candidate(candidate) is True
    assert is_reconstruction_candidate(candidate) is False
    assert requires_future_draw(candidate) is False


def test_unsupported_candidate_requires_identity():
    candidate = {"source_paths": []}
    assert classify_pipeline(candidate) == "UNSUPPORTED"
    assert blocks_historical_coverage(candidate) is True


def test_can_write_replay_rows_is_false_for_every_pipeline_state():
    for state in PIPELINE_STATES:
        assert can_write_replay_rows(state) is False
        assert can_write_replay_rows(_candidate(current_pipeline=state)) is False
