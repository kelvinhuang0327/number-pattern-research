from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from wbc_backend.reporting.strategy_replay_backfill_write_plan import (
    build_approved_backfill_write_plan,
    reject_unapproved_candidates,
    summarize_write_plan,
    validate_write_plan,
)

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "build_strategy_replay_backfill_write_plan.py"


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")


def _build_candidates() -> list[dict[str, object]]:
    return [
        {
            "original_source_refs": {"prediction": "fixture:prediction:1", "postgame_outcome": "G1"},
            "proposed_strategy_id": "",
            "proposed_lifecycle_state_at_prediction_time": "",
            "proposed_canonical_outcome_key": "G1",
            "proposed_actual_result": "",
            "backfill_priority": "P0",
            "backfill_reasons": ["strategy_id is missing and cannot be safely inferred"],
            "inferred_fields": [],
            "unsafe_to_infer_fields": ["strategy_id", "lifecycle_state_at_prediction_time", "actual_result"],
            "data_quality_flags": ["MISSING_STRATEGY_ID", "MISSING_LIFECYCLE_STATE_AT_PREDICTION_TIME", "MISSING_ACTUAL_RESULT"],
        },
        {
            "original_source_refs": {"prediction": "fixture:prediction:2", "postgame_outcome": "G2"},
            "proposed_strategy_id": "strat_002",
            "proposed_lifecycle_state_at_prediction_time": "online",
            "proposed_canonical_outcome_key": "G2",
            "proposed_actual_result": "win",
            "backfill_priority": "P1",
            "backfill_reasons": ["canonical_outcome_key was derived from game_id fallback"],
            "inferred_fields": ["canonical_outcome_key_fallback"],
            "unsafe_to_infer_fields": [],
            "data_quality_flags": ["CANONICAL_OUTCOME_KEY_FALLBACK_TO_GAME_ID"],
        },
    ]


def _approval_manifest(source_ref: str, approved_fields: list[str]) -> dict[str, object]:
    return {
        "manifest_version": "p10-1.0",
        "reviewer": "replay-ops-reviewer",
        "approval_reason": "manual review approved for dry-run write plan",
        "timestamp": "2026-05-10T00:00:00Z",
        "entries": [{"source_ref": source_ref, "approved_fields": approved_fields}],
    }


def test_unapproved_candidates_are_rejected() -> None:
    candidates = _build_candidates()
    proposal = build_approved_backfill_write_plan(candidates, None)
    assert proposal["summary"]["write_ready_count"] == 0
    assert proposal["write_plan_items"] == []
    rejection = reject_unapproved_candidates(candidates, None)
    assert len(rejection["rejected_items"]) == 2


def test_approved_p1_fallback_candidate_enters_write_plan() -> None:
    candidates = _build_candidates()
    original_snapshot = json.loads(json.dumps(candidates))
    manifest = _approval_manifest("fixture:prediction:2", ["canonical_outcome_key_fallback"])
    plan = build_approved_backfill_write_plan(candidates, manifest)
    assert plan["summary"]["write_ready_count"] == 1
    assert plan["summary"]["migration_allowed"] is True
    item = plan["write_plan_items"][0]
    assert item["dry_run_only"] is True
    assert item["approved_fields"] == ["canonical_outcome_key_fallback"]
    assert item["proposed_patch"]["dry_run_only"] is True
    assert item["proposed_patch"]["proposed_values"]["canonical_outcome_key_fallback"] is True
    assert candidates == original_snapshot


def test_p0_unsafe_candidate_without_approved_values_is_rejected() -> None:
    candidates = _build_candidates()
    manifest = _approval_manifest("fixture:prediction:1", ["canonical_outcome_key_fallback"])
    plan = build_approved_backfill_write_plan(candidates, manifest)
    assert plan["summary"]["write_ready_count"] == 0
    assert plan["write_plan_items"] == []


def test_unknown_candidate_id_in_manifest_is_rejected() -> None:
    candidates = _build_candidates()
    manifest = {
        "manifest_version": "p10-1.0",
        "reviewer": "replay-ops-reviewer",
        "approval_reason": "manual review approved for dry-run write plan",
        "timestamp": "2026-05-10T00:00:00Z",
        "entries": [{"candidate_id": "unknown", "approved_fields": ["canonical_outcome_key_fallback"]}],
    }
    plan = build_approved_backfill_write_plan(candidates, manifest)
    assert plan["manifest_valid"] is False
    assert plan["write_plan_items"] == []
    assert any("unknown candidate reference" in error for error in plan["manifest_errors"])


def test_write_plan_contains_dry_run_only() -> None:
    candidates = _build_candidates()
    manifest = _approval_manifest("fixture:prediction:2", ["canonical_outcome_key_fallback"])
    plan = build_approved_backfill_write_plan(candidates, manifest)
    summary = summarize_write_plan(plan)
    validation = validate_write_plan(plan)
    assert summary["dry_run_only"] is True
    assert validation["valid"] is True


def test_cli_prints_marker_and_writes_jsonl(tmp_path: Path) -> None:
    candidates_path = tmp_path / "candidates.jsonl"
    manifest_path = tmp_path / "manifest.json"
    output_path = tmp_path / "write_plan.jsonl"
    candidates_content = _build_candidates()
    _write_jsonl(candidates_path, candidates_content)
    manifest_path.write_text(json.dumps(_approval_manifest("fixture:prediction:2", ["canonical_outcome_key_fallback"]), ensure_ascii=False), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--candidates",
            str(candidates_path),
            "--approval-manifest",
            str(manifest_path),
            "--output",
            str(output_path),
            "--format",
            "jsonl",
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    assert "DRY_RUN_BACKFILL_WRITE_PLAN" in result.stdout
    assert output_path.exists()
    assert candidates_path.read_text(encoding="utf-8") == "\n".join(json.dumps(row, ensure_ascii=False) for row in candidates_content) + "\n"
    rows = output_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(rows) == 1
    payload = json.loads(rows[0])
    assert payload["dry_run_only"] is True
    assert payload["proposed_patch"]["dry_run_only"] is True


def test_no_production_db_access(tmp_path: Path) -> None:
    script_source = SCRIPT_PATH.read_text(encoding="utf-8")
    helper_source = Path(__file__).resolve().parents[1] / "wbc_backend" / "reporting" / "strategy_replay_backfill_write_plan.py"
    helper_text = helper_source.read_text(encoding="utf-8")
    assert "DRY_RUN_BACKFILL_WRITE_PLAN" in script_source
    assert "sqlite3" not in script_source
    assert "sqlalchemy" not in script_source
    assert "psycopg" not in script_source
    assert "db.connect" not in script_source
    assert "sqlite3" not in helper_text
    assert "sqlalchemy" not in helper_text
    assert "psycopg" not in helper_text