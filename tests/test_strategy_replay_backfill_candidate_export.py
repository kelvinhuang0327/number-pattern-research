from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "export_strategy_replay_backfill_candidates.py"


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> str:
    content = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n"
    path.write_text(content, encoding="utf-8")
    return content


def _run_export(
    *,
    prediction_registry: Path,
    postgame_outcomes: Path,
    output: Path,
    export_format: str,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--prediction-registry",
            str(prediction_registry),
            "--postgame-outcomes",
            str(postgame_outcomes),
            "--output",
            str(output),
            "--format",
            export_format,
        ],
        capture_output=True,
        text=True,
        check=True,
    )


def test_export_script_prints_marker_and_writes_jsonl(tmp_path: Path) -> None:
    prediction_registry = tmp_path / "prediction_registry.jsonl"
    postgame_outcomes = tmp_path / "postgame_outcomes.jsonl"
    output = tmp_path / "exported_candidates.jsonl"

    prediction_content = _write_jsonl(
        prediction_registry,
        [
            {
                "recorded_at_utc": "2026-05-10T08:00:00Z",
                "game_id": "G20260510_001",
                "strategy_id": "strat_001",
                "strategy_name": "Conservative Moneyline",
                "lifecycle_state_at_prediction_time": "online",
                "current_lifecycle_state": "online",
                "canonical_outcome_key": "G20260510_001",
                "market_type": "moneyline",
                "recommendation": "HOME",
                "source_refs": {"prediction": "fixture:prediction:1"},
            },
            {
                "recorded_at_utc": "2026-05-10T09:00:00Z",
                "game_id": "G20260510_002",
                    "strategy_id": "strat_002",
                    "strategy_name": "Fallback Join",
                    "lifecycle_state_at_prediction_time": "observation",
                    "current_lifecycle_state": "observation",
                "market_type": "total",
                "recommendation": "OVER",
                "source_refs": {"prediction": "fixture:prediction:2"},
            },
        ],
    )
    outcome_content = _write_jsonl(
        postgame_outcomes,
        [
            {"game_id": "G20260510_001", "canonical_outcome_key": "G20260510_001", "actual_result": "win"},
            {"game_id": "G20260510_002", "canonical_outcome_key": "G20260510_002", "actual_result": "loss"},
        ],
    )

    result = _run_export(
        prediction_registry=prediction_registry,
        postgame_outcomes=postgame_outcomes,
        output=output,
        export_format="jsonl",
    )

    assert "READ_ONLY_BACKFILL_EXPORT" in result.stdout
    assert output.exists()
    lines = output.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2

    first_row = json.loads(lines[0])
    second_row = json.loads(lines[1])

    assert first_row["original_source_refs"]["prediction"] == "fixture:prediction:1"
    assert first_row["original_source_refs"]["postgame_outcome"] == "G20260510_001"
    assert first_row["proposed_strategy_id"] == "strat_001"
    assert first_row["proposed_actual_result"] == "win"
    assert "actual_result" not in first_row["unsafe_to_infer_fields"]

    assert second_row["proposed_canonical_outcome_key"] == "G20260510_002"
    assert second_row["backfill_priority"] == "P1"
    assert "canonical_outcome_key_fallback" in second_row["inferred_fields"]
    assert second_row["proposed_actual_result"] == "loss"

    assert prediction_registry.read_text(encoding="utf-8") == prediction_content
    assert postgame_outcomes.read_text(encoding="utf-8") == outcome_content


def test_export_script_marks_missing_fields_unsafe_and_supports_json(tmp_path: Path) -> None:
    prediction_registry = tmp_path / "prediction_registry.jsonl"
    postgame_outcomes = tmp_path / "postgame_outcomes.jsonl"
    output = tmp_path / "exported_candidates.json"

    _write_jsonl(
        prediction_registry,
        [
            {
                "recorded_at_utc": "2026-05-10T10:00:00Z",
                "game_id": "G20260510_003",
                "market_type": "run_line",
                "recommendation": "AWAY",
                "source_refs": {"prediction": "fixture:prediction:3"},
            }
        ],
    )
    _write_jsonl(
        postgame_outcomes,
        [
            {"game_id": "G20260510_004", "canonical_outcome_key": "G20260510_004", "actual_result": "push"}
        ],
    )

    result = _run_export(
        prediction_registry=prediction_registry,
        postgame_outcomes=postgame_outcomes,
        output=output,
        export_format="json",
    )

    assert "READ_ONLY_BACKFILL_EXPORT" in result.stdout
    assert output.exists()
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert isinstance(payload, list)
    assert len(payload) == 1

    row = payload[0]
    assert row["proposed_strategy_id"] == ""
    assert row["proposed_lifecycle_state_at_prediction_time"] == ""
    assert row["proposed_actual_result"] == ""
    assert "strategy_id" in row["unsafe_to_infer_fields"]
    assert "lifecycle_state_at_prediction_time" in row["unsafe_to_infer_fields"]
    assert "actual_result" in row["unsafe_to_infer_fields"]
    assert row["backfill_priority"] == "P0"


def test_export_script_is_read_only_and_has_no_db_dependencies() -> None:
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    assert "READ_ONLY_BACKFILL_EXPORT" in source
    assert "sqlite3" not in source
    assert "sqlalchemy" not in source
    assert "psycopg" not in source
    assert "db.connect" not in source