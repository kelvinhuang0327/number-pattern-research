from __future__ import annotations

from wbc_backend.reporting.strategy_replay_ui_stop_gate import (
    build_strategy_replay_ui_stop_notice,
    evaluate_strategy_replay_ui_gate,
    identify_strategy_replay_ui_blockers,
    summarize_strategy_replay_ui_gate,
)


def _readiness(level: str = "BACKFILL_REQUIRED") -> dict[str, object]:
    return {"readiness_level": level}


def _blocked_metadata_source() -> dict[str, object]:
    return {
        "has_strategy_id_source": False,
        "has_strategy_name_source": False,
        "has_lifecycle_state_at_prediction_time_source": False,
        "future_rows_write_explicit_metadata": False,
        "historical_identity_repair_stopped": True,
        "approved_mock_data_mode": False,
        "explicitly_non_production_mode": False,
    }


def _ready_metadata_source() -> dict[str, object]:
    return {
        "has_strategy_id_source": True,
        "has_strategy_name_source": True,
        "has_lifecycle_state_at_prediction_time_source": True,
        "future_rows_write_explicit_metadata": True,
        "historical_identity_repair_stopped": True,
        "approved_mock_data_mode": False,
        "explicitly_non_production_mode": False,
    }


def test_ui_blocked_when_strategy_id_source_missing() -> None:
    gate = evaluate_strategy_replay_ui_gate(_blocked_metadata_source(), _readiness())
    assert gate["ui_can_start"] is False
    assert "MISSING_STRATEGY_ID_SOURCE" in gate["blockers"]


def test_ui_blocked_when_strategy_name_source_missing() -> None:
    source = _ready_metadata_source()
    source["has_strategy_name_source"] = False
    gate = evaluate_strategy_replay_ui_gate(source, _readiness())
    assert gate["ui_can_start"] is False
    assert "MISSING_STRATEGY_NAME_SOURCE" in gate["blockers"]


def test_ui_blocked_when_lifecycle_snapshot_source_missing() -> None:
    source = _ready_metadata_source()
    source["has_lifecycle_state_at_prediction_time_source"] = False
    gate = evaluate_strategy_replay_ui_gate(source, _readiness())
    assert gate["ui_can_start"] is False
    assert "MISSING_LIFECYCLE_STATE_AT_PREDICTION_TIME_SOURCE" in gate["blockers"]


def test_ui_blocked_when_readiness_is_backfill_required() -> None:
    gate = evaluate_strategy_replay_ui_gate(_ready_metadata_source(), _readiness("BACKFILL_REQUIRED"))
    assert gate["ui_can_start"] is False
    assert "READINESS_BACKFILL_REQUIRED" in gate["blockers"]


def test_mock_data_mode_allowed_only_when_explicitly_non_production() -> None:
    source = _ready_metadata_source()
    source["approved_mock_data_mode"] = True
    source["explicitly_non_production_mode"] = True
    gate = evaluate_strategy_replay_ui_gate(source, _readiness("DATA_CONTRACT_READY"))
    assert gate["ui_can_start"] is True
    assert gate["production_can_start"] is False
    assert gate["ui_mode"] == "mock-data"


def test_production_ui_remains_blocked_without_ui_mvp_ready() -> None:
    gate = evaluate_strategy_replay_ui_gate(_ready_metadata_source(), _readiness("DATA_CONTRACT_READY"))
    assert gate["production_can_start"] is False
    assert "PRODUCTION_MIGRATION_BLOCKED" in gate["blockers"]


def test_stop_notice_and_summary_include_blockers() -> None:
    gate = evaluate_strategy_replay_ui_gate(_blocked_metadata_source(), _readiness())
    notice = build_strategy_replay_ui_stop_notice(_blocked_metadata_source(), _readiness())
    summary = summarize_strategy_replay_ui_gate(gate)
    assert notice["ui_can_start"] is False
    assert summary["blocker_count"] >= 1
    assert "HISTORICAL_IDENTITY_REPAIR_STOPPED" in summary["blockers"]


def test_no_production_db_access() -> None:
    gate = evaluate_strategy_replay_ui_gate(_blocked_metadata_source(), _readiness())
    assert gate["production_can_start"] is False
