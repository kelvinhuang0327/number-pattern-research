"""Tests for read-only strategy replay adapter helpers."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from wbc_backend.reporting.strategy_replay_adapter import (
    adapt_prediction_to_replay_candidate,
    build_outcome_lookup,
    build_strategy_replay_rows,
    load_jsonl_entries,
    load_postgame_outcome_entries,
    load_prediction_registry_entries,
    summarize_strategy_replay_rows,
)


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> Path:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False))
            handle.write("\n")
    return path


def _prediction_entry(**overrides: object) -> dict[str, object]:
    record: dict[str, object] = {
        "game_id": "G20260510_001",
        "recorded_at_utc": "2026-05-10T08:00:00Z",
        "strategy_id": "strat_001",
        "strategy_name": "Conservative Moneyline",
        "lifecycle_state_at_prediction_time": "online",
        "current_lifecycle_state": "online",
        "market_type": "moneyline",
        "recommendation": "HOME",
        "confidence": 0.61,
        "edge": 0.03,
    }
    record.update(overrides)
    return record


def _outcome_entry(**overrides: object) -> dict[str, object]:
    record: dict[str, object] = {
        "game_id": "G20260510_001",
        "canonical_outcome_key": "G20260510_001",
        "actual_result": "win",
    }
    record.update(overrides)
    return record


def test_load_jsonl_entries_reads_rows(tmp_path: Path):
    path = _write_jsonl(tmp_path / "prediction.jsonl", [
        {"game_id": "A"},
        {"game_id": "B"},
    ])
    assert load_jsonl_entries(path) == [{"game_id": "A"}, {"game_id": "B"}]


def test_load_prediction_and_outcome_entries(tmp_path: Path):
    prediction_path = _write_jsonl(tmp_path / "prediction.jsonl", [{"game_id": "A"}])
    outcome_path = _write_jsonl(tmp_path / "outcome.jsonl", [{"game_id": "A", "actual_result": "win"}])
    assert load_prediction_registry_entries(prediction_path) == [{"game_id": "A"}]
    assert load_postgame_outcome_entries(outcome_path) == [{"game_id": "A", "actual_result": "win"}]


def test_join_prediction_to_actual_by_canonical_outcome_key():
    predictions = [_prediction_entry()]
    outcomes = [_outcome_entry(actual_result="win")]
    rows = build_strategy_replay_rows(predictions, outcomes)
    assert rows[0]["canonical_outcome_key"] == "G20260510_001"
    assert rows[0]["actual_result"] == "win"
    assert rows[0]["settlement_status"] == "WON"
    assert rows[0]["hit_miss_push"] == "HIT"


def test_missing_outcome_produces_data_quality_flags():
    rows = build_strategy_replay_rows([_prediction_entry()], [])
    assert "MISSING_ACTUAL_RESULT" in rows[0]["data_quality_flags"]


def test_missing_strategy_id_is_preserved_not_invented():
    row = adapt_prediction_to_replay_candidate(_prediction_entry(strategy_id=""), outcome_lookup={})
    assert row["strategy_id"] == ""
    assert "MISSING_STRATEGY_ID" in row["data_quality_flags"]


def test_missing_lifecycle_state_at_prediction_time_is_flagged():
    row = adapt_prediction_to_replay_candidate(
        _prediction_entry(lifecycle_state_at_prediction_time=""),
        outcome_lookup={},
    )
    assert "MISSING_LIFECYCLE_STATE_AT_PREDICTION_TIME" in row["data_quality_flags"]


def test_no_production_db_access():
    row = adapt_prediction_to_replay_candidate(_prediction_entry(), outcome_lookup={})
    assert isinstance(row["source_refs"], dict)
    assert "db" not in " ".join(row["source_refs"].values()).lower()


def test_preview_script_with_fixture_inputs_prints_dry_run_only(tmp_path: Path):
    prediction_path = _write_jsonl(tmp_path / "predictions.jsonl", [_prediction_entry()])
    outcome_path = _write_jsonl(tmp_path / "outcomes.jsonl", [_outcome_entry(actual_result="win")])
    script_path = Path(__file__).resolve().parent.parent / "scripts" / "preview_strategy_replay_backfill.py"

    completed = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--prediction-registry",
            str(prediction_path),
            "--postgame-outcomes",
            str(outcome_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "DRY_RUN_ONLY" in completed.stdout
    assert "total candidate rows" in completed.stdout


def test_summarize_rows_counts_ready_and_missing():
    rows = build_strategy_replay_rows(
        [
            _prediction_entry(),
            _prediction_entry(strategy_id=""),
        ],
        [_outcome_entry(actual_result="win")],
    )
    summary = summarize_strategy_replay_rows(rows)
    assert summary["total_candidate_rows"] == 2
    assert summary["rows_missing_strategy_id"] == 1
    assert summary["rows_mvp_ready"] == 1
