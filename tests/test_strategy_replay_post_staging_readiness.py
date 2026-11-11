from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from wbc_backend.reporting.strategy_replay_post_staging_readiness import (
    build_post_staging_readiness_summary,
    build_ui_unlock_checklist,
    evaluate_ui_unlock_gate,
    identify_ui_unlock_blockers,
)

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "check_strategy_replay_post_staging_readiness.py"


def _rows_complete() -> list[dict[str, object]]:
    return [
        {
            "candidate_id": "fixture:prediction:1",
            "source_refs": {"prediction": "fixture:prediction:1", "postgame_outcome": "G1"},
            "strategy_id": "strat_001",
            "strategy_name": "Original Strategy",
            "lifecycle_state_at_prediction_time": "online",
            "canonical_outcome_key": "G1",
            "actual_result": "win",
            "data_quality_flags": [],
        },
        {
            "candidate_id": "fixture:prediction:2",
            "source_refs": {"prediction": "fixture:prediction:2", "postgame_outcome": "G2"},
            "strategy_id": "strat_002",
            "strategy_name": "Matched",
            "lifecycle_state_at_prediction_time": "online",
            "canonical_outcome_key": "G2",
            "actual_result": "loss",
            "data_quality_flags": [],
        },
    ]


def _rows_with_p0_gap() -> list[dict[str, object]]:
    rows = _rows_complete()
    rows[0]["strategy_id"] = ""
    rows[0]["data_quality_flags"] = ["MISSING_STRATEGY_ID"]
    return rows


def _staging_result(*, staging_only: bool = True, production_write_allowed: bool = False, applied_count: int = 1, blocked_reasons: list[str] | None = None) -> dict[str, object]:
    return {
        "staging_only": staging_only,
        "production_write_allowed": production_write_allowed,
        "applied_count": applied_count,
        "skipped_count": 0,
        "unchanged_count": 1,
        "dry_run_only": True,
        "blocked_reasons": blocked_reasons or [],
        "rollback_plan_ref": "Keep the pre-apply fixture snapshot and the approved write plan artifact.",
        "target_mode": "STAGING",
    }


def test_backfill_required_keeps_ui_blocked() -> None:
    summary = build_post_staging_readiness_summary(_rows_with_p0_gap(), _staging_result())

    assert summary["readiness_level"] == "BACKFILL_REQUIRED"
    assert summary["ui_can_start"] is False
    assert summary["ui_mode"] == "BLOCKED"
    assert any("missing required field counts" in blocker for blocker in summary["blockers"])


def test_ui_mvp_ready_unlocks_frontend_spec_mock_data_mode() -> None:
    summary = build_post_staging_readiness_summary(_rows_complete(), _staging_result())

    assert summary["readiness_level"] == "UI_MVP_READY"
    assert summary["ui_can_start"] is True
    assert summary["ui_mode"] == "FRONTEND_SPEC_MOCK_DATA"
    assert summary["required_next_actions"]


def test_production_write_allowed_blocks_ui_unlock() -> None:
    readiness = build_post_staging_readiness_summary(_rows_complete(), _staging_result(production_write_allowed=True))
    gate = evaluate_ui_unlock_gate(readiness["readiness_summary"], readiness["staging_migration_result"])

    assert gate["ui_can_start"] is False
    assert any("production_write_allowed" in blocker for blocker in gate["blockers"])


def test_applied_count_zero_blocks_ui_unlock() -> None:
    readiness = build_post_staging_readiness_summary(_rows_complete(), _staging_result(applied_count=0))
    gate = build_ui_unlock_checklist(readiness["readiness_summary"], readiness["staging_migration_result"])

    assert gate["ui_can_start"] is False
    assert any("applied_count" in blocker for blocker in gate["blockers"])


def test_missing_p0_field_blocks_ui_unlock() -> None:
    readiness = build_post_staging_readiness_summary(_rows_with_p0_gap(), _staging_result())
    blockers = identify_ui_unlock_blockers(readiness["readiness_summary"], readiness["staging_migration_result"])

    assert blockers
    assert any("missing required field counts remain" in blocker for blocker in blockers)


def test_cli_prints_marker_and_does_not_write_without_output(tmp_path: Path) -> None:
    staging_output = tmp_path / "staging_output.json"
    staging_result = tmp_path / "staging_result.json"
    rows = _rows_complete()
    staging_output.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    staging_result.write_text(json.dumps(_staging_result(), ensure_ascii=False, indent=2), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--staging-output",
            str(staging_output),
            "--staging-result",
            str(staging_result),
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    assert "POST_STAGING_READINESS_RECHECK" in result.stdout
    assert "ui_mode: FRONTEND_SPEC_MOCK_DATA" in result.stdout
    assert not (tmp_path / "recheck.json").exists()


def test_no_production_db_access() -> None:
    script_source = SCRIPT_PATH.read_text(encoding="utf-8")
    helper_source = Path(__file__).resolve().parents[1] / "wbc_backend" / "reporting" / "strategy_replay_post_staging_readiness.py"
    helper_text = helper_source.read_text(encoding="utf-8")
    assert "sqlite3" not in script_source
    assert "sqlalchemy" not in script_source
    assert "psycopg" not in script_source
    assert "db.connect" not in script_source
    assert "sqlite3" not in helper_text
    assert "sqlalchemy" not in helper_text
    assert "psycopg" not in helper_text


def test_no_writes_without_explicit_output(tmp_path: Path) -> None:
    staging_output = tmp_path / "staging_output.json"
    staging_result = tmp_path / "staging_result.json"
    staging_output.write_text(json.dumps(_rows_complete(), ensure_ascii=False, indent=2), encoding="utf-8")
    staging_result.write_text(json.dumps(_staging_result(), ensure_ascii=False, indent=2), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--staging-output",
            str(staging_output),
            "--staging-result",
            str(staging_result),
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    assert "POST_STAGING_READINESS_RECHECK" in result.stdout
    assert not (tmp_path / "recheck.json").exists()
