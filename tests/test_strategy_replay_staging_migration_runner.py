from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

from wbc_backend.reporting.strategy_replay_migration_gate import build_migration_verification_checklist
from wbc_backend.reporting.strategy_replay_staging_migration_runner import (
    run_staging_migration_simulation,
    summarize_staging_migration_result,
    validate_staging_migration_inputs,
)

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_strategy_replay_staging_migration.py"


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
                    "proposed_values": {"strategy_id": "strat_001", "lifecycle_state_at_prediction_time": "online"},
                },
                "dry_run_only": True,
            }
        ],
    }


def _migration_gate_summary(*, migration_allowed: bool = True, human_approved: bool = True, rollback_plan_exists: bool = True) -> dict[str, object]:
    gate = build_migration_verification_checklist(
        {"applied_count": 1, "skipped_count": 0, "unchanged_count": 1, "dry_run_only": True, "mutation_allowed": False},
        _write_plan(),
        {"valid": True, "errors": [], "p0_unsafe_fields_unresolved": []},
        {"readiness_level": "BACKFILL_REQUIRED", "post_migration_diagnostics_passed": False},
        human_approved=human_approved,
    )
    gate["migration_allowed"] = migration_allowed
    gate["human_approved"] = human_approved
    gate["rollback_plan_exists"] = rollback_plan_exists
    if not rollback_plan_exists:
        gate["rollback_plan"] = []
    return gate


def test_gate_false_blocks_runner() -> None:
    with __import__("pytest").raises(ValueError, match="migration gate must allow migration"):
        run_staging_migration_simulation(_fixture_rows(), _write_plan(), _migration_gate_summary(migration_allowed=False), target_mode="STAGING")


def test_human_approval_false_blocks_runner() -> None:
    with __import__("pytest").raises(ValueError, match="human approval is required"):
        run_staging_migration_simulation(_fixture_rows(), _write_plan(), _migration_gate_summary(human_approved=False), target_mode="STAGING")


def test_rollback_missing_blocks_runner() -> None:
    with __import__("pytest").raises(ValueError, match="rollback plan must exist"):
        run_staging_migration_simulation(_fixture_rows(), _write_plan(), _migration_gate_summary(rollback_plan_exists=False), target_mode="STAGING")


def test_production_mode_is_refused() -> None:
    validation = validate_staging_migration_inputs(_fixture_rows(), _write_plan(), _migration_gate_summary(), target_mode="PRODUCTION")

    assert validation["valid"] is False
    assert "production target_mode is refused" in validation["errors"]


def test_cli_refuses_production_mode(tmp_path: Path) -> None:
    input_path = tmp_path / "fixture.json"
    write_plan_path = tmp_path / "write_plan.json"
    gate_path = tmp_path / "gate.json"
    output_path = tmp_path / "result.json"
    input_path.write_text(json.dumps(_fixture_rows(), ensure_ascii=False, indent=2), encoding="utf-8")
    write_plan_path.write_text(json.dumps(_write_plan(), ensure_ascii=False, indent=2), encoding="utf-8")
    gate_path.write_text(json.dumps(_migration_gate_summary(), ensure_ascii=False, indent=2), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--input",
            str(input_path),
            "--write-plan",
            str(write_plan_path),
            "--migration-gate-summary",
            str(gate_path),
            "--output",
            str(output_path),
            "--target-mode",
            "PRODUCTION",
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "PRODUCTION target mode is refused" in (result.stderr or result.stdout)


def test_staging_mode_can_run_when_gate_passes() -> None:
    rows = _fixture_rows()
    original = copy.deepcopy(rows)
    result = run_staging_migration_simulation(rows, _write_plan(), _migration_gate_summary(), target_mode="FIXTURE")

    assert result["staging_only"] is True
    assert result["production_write_allowed"] is False
    assert result["blocked_reasons"] == []
    assert result["applied_count"] == 1
    assert rows == original
    assert result["rows"][0]["strategy_id"] == "strat_001"


def test_summary_helper_reports_staging_only() -> None:
    result = run_staging_migration_simulation(_fixture_rows(), _write_plan(), _migration_gate_summary(), target_mode="STAGING")
    summary = summarize_staging_migration_result(result["rows"], result["rows"], _migration_gate_summary(), target_mode="STAGING")

    assert summary["staging_only"] is True
    assert summary["production_write_allowed"] is False


def test_cli_prints_marker_and_refuses_same_input_output_path(tmp_path: Path) -> None:
    input_path = tmp_path / "fixture.json"
    write_plan_path = tmp_path / "write_plan.json"
    gate_path = tmp_path / "gate.json"
    rows = _fixture_rows()
    input_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    write_plan_path.write_text(json.dumps(_write_plan(), ensure_ascii=False, indent=2), encoding="utf-8")
    gate_path.write_text(json.dumps(_migration_gate_summary(), ensure_ascii=False, indent=2), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--input",
            str(input_path),
            "--write-plan",
            str(write_plan_path),
            "--migration-gate-summary",
            str(gate_path),
            "--output",
            str(input_path),
            "--target-mode",
            "STAGING",
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "output path must not equal input path" in (result.stderr or result.stdout)


def test_cli_prints_marker_and_writes_output(tmp_path: Path) -> None:
    input_path = tmp_path / "fixture.json"
    write_plan_path = tmp_path / "write_plan.json"
    gate_path = tmp_path / "gate.json"
    output_path = tmp_path / "result.json"
    rows = _fixture_rows()
    input_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    write_plan_path.write_text(json.dumps(_write_plan(), ensure_ascii=False, indent=2), encoding="utf-8")
    gate_path.write_text(json.dumps(_migration_gate_summary(), ensure_ascii=False, indent=2), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--input",
            str(input_path),
            "--write-plan",
            str(write_plan_path),
            "--migration-gate-summary",
            str(gate_path),
            "--output",
            str(output_path),
            "--target-mode",
            "FIXTURE",
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    assert "STAGING_ONLY_MIGRATION_RUNNER" in result.stdout
    assert output_path.exists()
    assert "production_write_allowed: false" in result.stdout


def test_no_production_db_access() -> None:
    script_source = SCRIPT_PATH.read_text(encoding="utf-8")
    helper_source = Path(__file__).resolve().parents[1] / "wbc_backend" / "reporting" / "strategy_replay_staging_migration_runner.py"
    helper_text = helper_source.read_text(encoding="utf-8")
    assert "sqlite3" not in script_source
    assert "sqlalchemy" not in script_source
    assert "psycopg" not in script_source
    assert "db.connect" not in script_source
    assert "sqlite3" not in helper_text
    assert "sqlalchemy" not in helper_text
    assert "psycopg" not in helper_text


def test_no_production_write_allowed() -> None:
    result = run_staging_migration_simulation(_fixture_rows(), _write_plan(), _migration_gate_summary(), target_mode="STAGING")
    assert result["production_write_allowed"] is False
    assert result["staging_only"] is True
