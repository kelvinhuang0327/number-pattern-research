from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

from wbc_backend.reporting.strategy_replay_backfill_apply import (
    apply_write_plan_to_rows,
    summarize_fixture_apply_result,
    validate_fixture_apply_result,
)

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "apply_strategy_replay_backfill_write_plan_fixture.py"


def _write_json(path: Path, payload: list[dict[str, object]] | dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _fixture_rows() -> list[dict[str, object]]:
    return [
        {
            "candidate_id": "fixture:prediction:1",
            "source_refs": {"prediction": "fixture:prediction:1", "postgame_outcome": "G1"},
            "strategy_id": "",
            "strategy_name": "Original Strategy",
            "lifecycle_state_at_prediction_time": "",
            "canonical_outcome_key": "G1",
            "unknown_meta": {"kept": True},
        },
        {
            "candidate_id": "fixture:prediction:2",
            "source_refs": {"prediction": "fixture:prediction:2", "postgame_outcome": "G2"},
            "strategy_id": "strat_002",
            "strategy_name": "Unmatched",
            "lifecycle_state_at_prediction_time": "online",
            "canonical_outcome_key": "G2",
            "unknown_meta": {"kept": True},
        },
    ]


def _write_plan() -> dict[str, object]:
    return {
        "summary": {"dry_run_only": True, "write_ready_count": 1, "rejected_count": 0, "migration_allowed": True},
        "write_plan_items": [
            {
                "candidate_id": "fixture:prediction:1",
                "source_refs": {"prediction": "fixture:prediction:1", "postgame_outcome": "G1"},
                "approved_fields": ["strategy_id", "lifecycle_state_at_prediction_time"],
                "proposed_patch": {
                    "dry_run_only": True,
                    "proposed_values": {
                        "strategy_id": "strat_001",
                        "lifecycle_state_at_prediction_time": "online",
                        "strategy_name": "Should Not Apply",
                    },
                },
                "reviewer": "replay-ops-reviewer",
                "approval_reason": "manual approval for fixture apply",
                "timestamp": "2026-05-10T00:00:00Z",
                "dry_run_only": True,
            }
        ],
    }


def test_approved_patch_applies_to_matching_fixture_row() -> None:
    rows = _fixture_rows()
    original = copy.deepcopy(rows)
    result = apply_write_plan_to_rows(rows, _write_plan())

    assert result["applied_count"] == 1
    assert result["skipped_count"] == 0
    assert result["mutation_allowed"] is False
    assert result["dry_run_only"] is True
    assert result["rows"][0]["strategy_id"] == "strat_001"
    assert result["rows"][0]["lifecycle_state_at_prediction_time"] == "online"
    assert result["rows"][0]["strategy_name"] == "Original Strategy"
    assert result["rows"][0]["unknown_meta"] == {"kept": True}
    assert rows == original


def test_unapproved_field_is_not_patched() -> None:
    rows = _fixture_rows()
    plan = _write_plan()
    plan["write_plan_items"][0]["proposed_patch"]["proposed_values"]["strategy_name"] = "Should Not Apply"
    result = apply_write_plan_to_rows(rows, plan)

    assert result["rows"][0]["strategy_name"] == "Original Strategy"


def test_unmatched_source_ref_is_skipped() -> None:
    rows = _fixture_rows()
    plan = _write_plan()
    plan["write_plan_items"][0]["candidate_id"] = "fixture:missing"
    plan["write_plan_items"][0]["source_refs"] = {"prediction": "fixture:missing"}
    result = apply_write_plan_to_rows(rows, plan)

    assert result["applied_count"] == 0
    assert result["skipped_count"] == 1
    assert result["unchanged_count"] == 2


def test_fixture_apply_validation_reports_sane_summary() -> None:
    rows = _fixture_rows()
    plan = _write_plan()
    result = apply_write_plan_to_rows(rows, plan)
    validation = validate_fixture_apply_result(rows, result["rows"], plan)
    summary = summarize_fixture_apply_result(rows, result["rows"], plan)

    assert validation["valid"] is True
    assert summary["dry_run_only"] is True
    assert summary["mutation_allowed"] is False


def test_cli_prints_marker_and_writes_jsonl(tmp_path: Path) -> None:
    input_path = tmp_path / "input.json"
    write_plan_path = tmp_path / "write_plan.json"
    output_path = tmp_path / "output.jsonl"
    rows = _fixture_rows()
    plan = _write_plan()
    _write_json(input_path, rows)
    _write_json(write_plan_path, plan)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--input",
            str(input_path),
            "--write-plan",
            str(write_plan_path),
            "--output",
            str(output_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    assert "FIXTURE_ONLY_BACKFILL_APPLY" in result.stdout
    assert output_path.exists()
    assert input_path.read_text(encoding="utf-8") == json.dumps(rows, ensure_ascii=False, indent=2)


def test_cli_refuses_same_input_output_path(tmp_path: Path) -> None:
    input_path = tmp_path / "fixture.json"
    write_plan_path = tmp_path / "write_plan.json"
    rows = _fixture_rows()
    _write_json(input_path, rows)
    _write_json(write_plan_path, _write_plan())

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--input",
            str(input_path),
            "--write-plan",
            str(write_plan_path),
            "--output",
            str(input_path),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "output path must not equal input path" in (result.stderr or result.stdout)


def test_no_production_db_access() -> None:
    script_source = SCRIPT_PATH.read_text(encoding="utf-8")
    helper_source = Path(__file__).resolve().parents[1] / "wbc_backend" / "reporting" / "strategy_replay_backfill_apply.py"
    helper_text = helper_source.read_text(encoding="utf-8")
    assert "FIXTURE_ONLY_BACKFILL_APPLY" in script_source
    assert "sqlite3" not in script_source
    assert "sqlalchemy" not in script_source
    assert "psycopg" not in script_source
    assert "db.connect" not in script_source
    assert "sqlite3" not in helper_text
    assert "sqlalchemy" not in helper_text
    assert "psycopg" not in helper_text