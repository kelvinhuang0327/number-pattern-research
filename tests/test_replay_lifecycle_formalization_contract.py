"""Contract tests for the formal replay lifecycle surface used by P1/P3."""
from __future__ import annotations

from lottery_api.models.replay_pipeline_contract import (
    FORMAL_LIFECYCLE_STATES,
    can_production_apply_lifecycle,
    canonicalize_lifecycle_state,
    normalize_pipeline_sequence,
)


def test_formal_lifecycle_states_cover_all_7_values():
    assert FORMAL_LIFECYCLE_STATES == (
        "PRODUCTION",
        "WATCHING",
        "PROVISIONAL",
        "REJECTED",
        "OFFLINE",
        "EXPERIMENTAL",
        "UNKNOWN",
    )


def test_can_production_apply_only_accepts_production():
    assert can_production_apply_lifecycle("PRODUCTION") is True
    for state in FORMAL_LIFECYCLE_STATES:
        if state != "PRODUCTION":
            assert can_production_apply_lifecycle(state) is False


def test_unknown_is_classification_only():
    assert canonicalize_lifecycle_state("mystery") == "UNKNOWN"
    assert can_production_apply_lifecycle("UNKNOWN") is False


def test_pipeline_sequence_normalization_is_safe():
    assert normalize_pipeline_sequence(["historical_reconstruction", None, "bad"]) == [
        "HISTORICAL_RECONSTRUCTION",
        "UNSUPPORTED",
        "UNSUPPORTED",
    ]
