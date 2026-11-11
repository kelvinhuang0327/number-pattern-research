"""Tests for strategy replay readiness classification and diagnostics."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from wbc_backend.reporting.strategy_replay_history import build_strategy_replay_row
from wbc_backend.reporting.strategy_replay_readiness import (
    READYNESS_LEVEL_API_SKELETON_READY,
    READYNESS_LEVEL_BACKFILL_REQUIRED,
    READYNESS_LEVEL_DATA_CONTRACT_READY,
    READYNESS_LEVEL_NOT_READY,
    READYNESS_LEVEL_UI_MVP_READY,
    build_strategy_replay_gap_closure_plan,
    build_strategy_replay_readiness_summary,
    classify_strategy_replay_readiness,
    identify_strategy_replay_blockers,
)


def _complete_row(**overrides):
    record = {
        "strategy_id": "strat_001",
        "strategy_name": "Conservative Moneyline",
        "lifecycle_state_at_prediction_time": "online",
        "current_lifecycle_state": "offline",
        "prediction_timestamp": "2026-05-10T08:00:00Z",
        "game_id": "G20260510_001",
        "canonical_outcome_key": "G20260510_001",
        "market_type": "moneyline",
        "recommendation": "HOME",
        "confidence": 0.61,
        "edge": 0.03,
        "actual_result": "win",
        "source_refs": {"prediction": "fixture:prediction:1", "outcome": "fixture:outcome:1"},
    }
    record.update(overrides)
    return build_strategy_replay_row(record)


def test_zero_rows_not_ready():
    summary = build_strategy_replay_readiness_summary([], endpoint_mounted=False, endpoint_stable=False, ui_ready=False)
    assert classify_strategy_replay_readiness(summary) == READYNESS_LEVEL_NOT_READY


def test_complete_rows_ui_mvp_ready():
    rows = [_complete_row(), _complete_row(game_id="G20260510_002", canonical_outcome_key="G20260510_002")]
    summary = build_strategy_replay_readiness_summary(rows, endpoint_mounted=True, endpoint_stable=True, ui_ready=True)
    assert classify_strategy_replay_readiness(summary) == READYNESS_LEVEL_UI_MVP_READY
    assert identify_strategy_replay_blockers(summary) == []
    assert build_strategy_replay_gap_closure_plan(summary)[0].startswith("Proceed") or build_strategy_replay_gap_closure_plan(summary)[0].startswith("Hold")


def test_missing_strategy_id_backfill_required():
    row = _complete_row(strategy_id="")
    summary = build_strategy_replay_readiness_summary([row], endpoint_mounted=True, endpoint_stable=False, ui_ready=False)
    assert classify_strategy_replay_readiness(summary) == READYNESS_LEVEL_BACKFILL_REQUIRED
    assert any("strategy_id" in blocker for blocker in identify_strategy_replay_blockers(summary))


def test_missing_lifecycle_state_backfill_required():
    row = _complete_row(lifecycle_state_at_prediction_time="")
    summary = build_strategy_replay_readiness_summary([row], endpoint_mounted=True, endpoint_stable=False, ui_ready=False)
    assert classify_strategy_replay_readiness(summary) == READYNESS_LEVEL_BACKFILL_REQUIRED


def test_missing_outcome_key_backfill_required():
    row = _complete_row(canonical_outcome_key="")
    summary = build_strategy_replay_readiness_summary([row], endpoint_mounted=True, endpoint_stable=False, ui_ready=False)
    assert classify_strategy_replay_readiness(summary) == READYNESS_LEVEL_BACKFILL_REQUIRED


def test_missing_actual_result_backfill_required():
    row = _complete_row(actual_result="")
    summary = build_strategy_replay_readiness_summary([row], endpoint_mounted=True, endpoint_stable=False, ui_ready=False)
    assert classify_strategy_replay_readiness(summary) == READYNESS_LEVEL_BACKFILL_REQUIRED


def test_data_contract_ready_when_complete_but_endpoint_not_mounted():
    row = _complete_row()
    summary = build_strategy_replay_readiness_summary([row], endpoint_mounted=False, endpoint_stable=False, ui_ready=False)
    assert classify_strategy_replay_readiness(summary) == READYNESS_LEVEL_DATA_CONTRACT_READY


def test_api_skeleton_ready_when_endpoint_mounted_but_not_stable():
    row = _complete_row()
    summary = build_strategy_replay_readiness_summary([row], endpoint_mounted=True, endpoint_stable=False, ui_ready=False)
    assert classify_strategy_replay_readiness(summary) == READYNESS_LEVEL_API_SKELETON_READY


def test_diagnostics_script_prints_read_only_diagnostic():
    script_path = Path(__file__).resolve().parent.parent / "scripts" / "check_strategy_replay_readiness.py"
    completed = subprocess.run([sys.executable, str(script_path)], check=False, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    assert "READ_ONLY_DIAGNOSTIC" in completed.stdout
    assert "readiness_level:" in completed.stdout


def test_no_production_db_access():
    row = _complete_row()
    summary = build_strategy_replay_readiness_summary([row], endpoint_mounted=True, endpoint_stable=True, ui_ready=True)
    assert summary["source_mode"] == "READ_ONLY"
