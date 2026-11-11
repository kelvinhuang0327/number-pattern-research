"""Contract tests for strategy replay row normalization.

Tests remain fixture-based and avoid any production DB access.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from wbc_backend.reporting.strategy_replay_history import (
    build_data_quality_flags,
    build_strategy_replay_row,
    derive_settlement_status,
    normalize_lifecycle_state,
    validate_strategy_replay_row,
)


def _base_record(**overrides):
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
        "source_refs": {
            "prediction": "prediction_registry.jsonl#1",
            "outcome": "postgame_results.jsonl#1",
            "lifecycle": "strategy_lifecycle_snapshot.jsonl#1",
        },
    }
    record.update(overrides)
    return record


class TestLifecycleNormalization:
    @pytest.mark.parametrize(
        ("raw_state", "expected"),
        [
            ("online", "online"),
            ("OFFLINE", "offline"),
            ("Rejected", "rejected"),
            ("observation", "observation"),
            ("observed", "observation"),
            ("unknown-value", "unknown"),
            (None, "unknown"),
        ],
    )
    def test_normalize_lifecycle_state(self, raw_state, expected):
        assert normalize_lifecycle_state(raw_state) == expected


class TestSettlementDerivation:
    @pytest.mark.parametrize(
        ("actual_result", "expected"),
        [
            ("win", "WON"),
            ("loss", "LOST"),
            ("push", "PUSH"),
            ("void", "VOID"),
            (None, "PENDING"),
            ("", "PENDING"),
        ],
    )
    def test_derive_settlement_status(self, actual_result, expected):
        assert derive_settlement_status(actual_result) == expected


class TestStrategyReplayRowContract:
    def test_build_strategy_replay_row_win(self):
        row = build_strategy_replay_row(_base_record(actual_result="win"))
        assert row["settlement_status"] == "WON"
        assert row["hit_miss_push"] == "HIT"
        assert row["data_quality_flags"] == []

    def test_build_strategy_replay_row_loss(self):
        row = build_strategy_replay_row(_base_record(actual_result="loss"))
        assert row["settlement_status"] == "LOST"
        assert row["hit_miss_push"] == "MISS"

    def test_build_strategy_replay_row_push(self):
        row = build_strategy_replay_row(_base_record(actual_result="push"))
        assert row["settlement_status"] == "PUSH"
        assert row["hit_miss_push"] == "PUSH"

    def test_missing_strategy_id_is_flagged(self):
        row = build_strategy_replay_row(_base_record(strategy_id=""))
        assert "MISSING_STRATEGY_ID" in row["data_quality_flags"]
        assert any("strategy_id" in err for err in validate_strategy_replay_row(row))

    def test_missing_lifecycle_state_at_prediction_time_is_flagged(self):
        row = build_strategy_replay_row(_base_record(lifecycle_state_at_prediction_time=""))
        assert "MISSING_LIFECYCLE_STATE_AT_PREDICTION_TIME" in row["data_quality_flags"]
        assert any("lifecycle_state_at_prediction_time" in err for err in validate_strategy_replay_row(row))

    def test_missing_actual_result_is_flagged(self):
        row = build_strategy_replay_row(_base_record(actual_result=None))
        assert row["settlement_status"] == "PENDING"
        assert row["hit_miss_push"] == "PENDING"
        assert "MISSING_ACTUAL_RESULT" in row["data_quality_flags"]

    def test_missing_canonical_outcome_key_falls_back_to_game_id(self):
        row = build_strategy_replay_row(
            _base_record(canonical_outcome_key="", game_id="G20260510_002")
        )
        assert row["canonical_outcome_key"] == "G20260510_002"
        assert "CANONICAL_OUTCOME_KEY_FALLBACK_TO_GAME_ID" in row["data_quality_flags"]

    def test_unstable_outcome_join_key_is_flagged(self):
        row = build_strategy_replay_row(
            _base_record(canonical_outcome_key="tmp", game_id="G20260510_003")
        )
        assert "UNSTABLE_CANONICAL_OUTCOME_KEY" in row["data_quality_flags"]

    @pytest.mark.parametrize(
        ("state", "expected"),
        [
            ("rejected", "rejected"),
            ("observation", "observation"),
            ("offline", "offline"),
            ("online", "online"),
        ],
    )
    def test_replay_row_preserves_known_lifecycle_states(self, state, expected):
        row = build_strategy_replay_row(_base_record(lifecycle_state_at_prediction_time=state))
        assert row["lifecycle_state_at_prediction_time"] == expected

    def test_unknown_lifecycle_state_normalizes_to_unknown(self):
        row = build_strategy_replay_row(_base_record(lifecycle_state_at_prediction_time="mystery"))
        assert row["lifecycle_state_at_prediction_time"] == "unknown"
        assert "UNKNOWN_LIFECYCLE_STATE_AT_PREDICTION_TIME" in row["data_quality_flags"]

    def test_no_production_db_access(self):
        row = build_strategy_replay_row(_base_record())
        assert isinstance(row["source_refs"], dict)
        assert "db" not in " ".join(sorted(row["source_refs"].values())).lower()


class TestPreviewBackfillScript:
    def test_preview_script_prints_dry_run_only(self):
        script_path = Path(__file__).resolve().parent.parent / "scripts" / "preview_strategy_replay_backfill.py"
        completed = subprocess.run(
            [sys.executable, str(script_path)],
            check=False,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 0, completed.stderr
        assert "DRY_RUN_ONLY" in completed.stdout
        assert "total candidate rows" in completed.stdout

    def test_build_data_quality_flags(self):
        row = build_strategy_replay_row(_base_record(strategy_id="", actual_result=None, canonical_outcome_key=""))
        flags = build_data_quality_flags(row)
        assert "MISSING_STRATEGY_ID" in flags
        assert "MISSING_ACTUAL_RESULT" in flags
