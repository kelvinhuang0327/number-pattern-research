from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

from wbc_backend.reporting.strategy_replay_migration_gate import (
    build_migration_rollback_plan,
    build_migration_verification_checklist,
    identify_migration_no_go_reasons,
    summarize_migration_gate,
)

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "build_strategy_replay_migration_gate_checklist.py"


def _fixture_apply_summary() -> dict[str, object]:
    return {
        "applied_count": 1,
        "skipped_count": 0,
        "unchanged_count": 1,
        "dry_run_only": True,
        "mutation_allowed": False,
    }


def _write_plan_summary() -> dict[str, object]:
    return {
        "summary": {
            "total_candidates": 1,
            "write_ready_count": 1,
            "rejected_count": 0,
            "migration_allowed": True,
            "dry_run_only": True,
        },
        "write_plan_items": [
            {
                "candidate_id": "fixture:prediction:1",
                "source_refs": {"prediction": "fixture:prediction:1"},
                "approved_fields": ["strategy_id"],
                "proposed_patch": {"dry_run_only": True, "proposed_values": {"strategy_id": "strat_001"}},
                "dry_run_only": True,
            }
        ],
    }


def _approval_manifest_summary() -> dict[str, object]:
    return {
        "valid": True,
        "errors": [],
        "human_approved": False,
        "required_human_approvals": ["human_approval"],
        "p0_unsafe_fields_unresolved": [],
    }


def _readiness_summary(level: str = "BACKFILL_REQUIRED") -> dict[str, object]:
    return {
        "readiness_level": level,
        "post_migration_diagnostics_passed": False,
    }


def test_default_migration_allowed_is_false() -> None:
    gate = build_migration_verification_checklist(None, None, None, None, human_approved=False)

    assert gate["migration_allowed"] is False
    assert gate["rollback_required"] is True
    assert gate["ui_can_start"] is False
    assert gate["no_go_reasons"]


def test_valid_inputs_still_false_without_human_approval() -> None:
    gate = build_migration_verification_checklist(
        _fixture_apply_summary(),
        _write_plan_summary(),
        _approval_manifest_summary(),
        _readiness_summary(),
        human_approved=False,
    )

    assert gate["migration_allowed"] is False
    assert "human approval flag must be explicitly true" in gate["no_go_reasons"]


def test_human_approval_allows_small_batch_gate_when_all_checks_pass() -> None:
    gate = build_migration_verification_checklist(
        _fixture_apply_summary(),
        _write_plan_summary(),
        _approval_manifest_summary(),
        _readiness_summary(),
        human_approved=True,
    )

    assert gate["migration_allowed"] is True
    assert gate["no_go_reasons"] == []
    assert gate["rollback_plan"]


def test_skipped_count_blocks_migration() -> None:
    fixture_summary = _fixture_apply_summary()
    fixture_summary["skipped_count"] = 1

    gate = build_migration_verification_checklist(
        fixture_summary,
        _write_plan_summary(),
        _approval_manifest_summary(),
        _readiness_summary(),
        human_approved=True,
    )

    assert gate["migration_allowed"] is False
    assert "planned write items must not be skipped" in gate["no_go_reasons"]


def test_unresolved_p0_unsafe_field_blocks_migration() -> None:
    manifest_summary = _approval_manifest_summary()
    manifest_summary["p0_unsafe_fields_unresolved"] = ["strategy_id"]

    gate = build_migration_verification_checklist(
        _fixture_apply_summary(),
        _write_plan_summary(),
        manifest_summary,
        _readiness_summary(),
        human_approved=True,
    )

    assert gate["migration_allowed"] is False
    assert any(reason.startswith("P0 unsafe fields remain unresolved") for reason in gate["no_go_reasons"])


def test_missing_rollback_plan_blocks_migration() -> None:
    write_plan_summary = _write_plan_summary()
    write_plan_summary["rollback_plan"] = []

    gate = build_migration_verification_checklist(
        _fixture_apply_summary(),
        write_plan_summary,
        _approval_manifest_summary(),
        _readiness_summary(),
        human_approved=True,
    )

    assert gate["migration_allowed"] is False
    assert "rollback plan must exist" in gate["no_go_reasons"]


def test_ui_remains_false_when_readiness_is_backfill_required() -> None:
    gate = build_migration_verification_checklist(
        _fixture_apply_summary(),
        _write_plan_summary(),
        _approval_manifest_summary(),
        _readiness_summary("BACKFILL_REQUIRED"),
        human_approved=True,
    )

    assert gate["ui_can_start"] is False


def test_checklist_script_prints_marker_and_does_not_write_without_output(tmp_path: Path) -> None:
    fixture_path = tmp_path / "fixture_summary.json"
    write_plan_path = tmp_path / "write_plan.json"
    manifest_path = tmp_path / "manifest_summary.json"
    readiness_path = tmp_path / "readiness_summary.json"
    fixture_path.write_text(json.dumps(_fixture_apply_summary(), ensure_ascii=False, indent=2), encoding="utf-8")
    write_plan_path.write_text(json.dumps(_write_plan_summary(), ensure_ascii=False, indent=2), encoding="utf-8")
    manifest_path.write_text(json.dumps(_approval_manifest_summary(), ensure_ascii=False, indent=2), encoding="utf-8")
    readiness_path.write_text(json.dumps(_readiness_summary(), ensure_ascii=False, indent=2), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--fixture-apply-summary",
            str(fixture_path),
            "--write-plan-summary",
            str(write_plan_path),
            "--approval-manifest-summary",
            str(manifest_path),
            "--readiness-summary",
            str(readiness_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    assert "READ_ONLY_MIGRATION_GATE_CHECKLIST" in result.stdout
    assert "migration_allowed: false" in result.stdout
    assert "ui_can_start: false" in result.stdout
    assert not (tmp_path / "checklist.json").exists()


def test_cli_writes_only_to_explicit_output(tmp_path: Path) -> None:
    fixture_path = tmp_path / "fixture_summary.json"
    write_plan_path = tmp_path / "write_plan.json"
    manifest_path = tmp_path / "manifest_summary.json"
    readiness_path = tmp_path / "readiness_summary.json"
    output_path = tmp_path / "checklist.json"
    fixture_path.write_text(json.dumps(_fixture_apply_summary(), ensure_ascii=False, indent=2), encoding="utf-8")
    write_plan_path.write_text(json.dumps(_write_plan_summary(), ensure_ascii=False, indent=2), encoding="utf-8")
    manifest_path.write_text(json.dumps(_approval_manifest_summary(), ensure_ascii=False, indent=2), encoding="utf-8")
    readiness_path.write_text(json.dumps(_readiness_summary(), ensure_ascii=False, indent=2), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--fixture-apply-summary",
            str(fixture_path),
            "--write-plan-summary",
            str(write_plan_path),
            "--approval-manifest-summary",
            str(manifest_path),
            "--readiness-summary",
            str(readiness_path),
            "--human-approved",
            "--output",
            str(output_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    assert output_path.exists()
    assert "READ_ONLY_MIGRATION_GATE_CHECKLIST" in result.stdout
    assert "output_path:" in result.stdout


def test_no_production_db_access() -> None:
    script_source = SCRIPT_PATH.read_text(encoding="utf-8")
    helper_source = Path(__file__).resolve().parents[1] / "wbc_backend" / "reporting" / "strategy_replay_migration_gate.py"
    helper_text = helper_source.read_text(encoding="utf-8")
    assert "sqlite3" not in script_source
    assert "sqlalchemy" not in script_source
    assert "psycopg" not in script_source
    assert "db.connect" not in script_source
    assert "sqlite3" not in helper_text
    assert "sqlalchemy" not in helper_text
    assert "psycopg" not in helper_text


def test_rollback_plan_is_read_only() -> None:
    plan = build_migration_rollback_plan(_write_plan_summary())
    assert plan
    assert all(isinstance(step, str) and step for step in plan)


def test_summarize_migration_gate_matches_gate_result() -> None:
    gate = build_migration_verification_checklist(
        _fixture_apply_summary(),
        _write_plan_summary(),
        _approval_manifest_summary(),
        _readiness_summary(),
        human_approved=True,
    )
    summary = summarize_migration_gate(
        _fixture_apply_summary(),
        _write_plan_summary(),
        _approval_manifest_summary(),
        _readiness_summary(),
        human_approved=True,
    )

    assert summary["migration_allowed"] == gate["migration_allowed"]
    assert summary["no_go_reasons"] == gate["no_go_reasons"]
    assert summary["ui_can_start"] == gate["ui_can_start"]
