from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from wbc_backend.reporting.strategy_replay_backfill_review import (
    REVIEW_DECISION_AUTO_APPROVABLE,
    REVIEW_DECISION_REJECTED,
    REVIEW_DECISION_REVIEW_REQUIRED,
    REVIEW_DECISION_WRITE_READY,
    build_safe_migration_proposal,
    classify_review_decision,
    load_backfill_candidates,
    summarize_backfill_candidates,
    validate_approval_manifest,
)

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "review_strategy_replay_backfill_candidates.py"


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


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
        {
            "original_source_refs": {"prediction": "fixture:prediction:3", "postgame_outcome": "G3"},
            "proposed_strategy_id": "strat_003",
            "proposed_lifecycle_state_at_prediction_time": "online",
            "proposed_canonical_outcome_key": "G3",
            "proposed_actual_result": "win",
            "backfill_priority": "P2",
            "backfill_reasons": ["row is ready for historical backfill automation"],
            "inferred_fields": [],
            "unsafe_to_infer_fields": [],
            "data_quality_flags": [],
        },
    ]


def test_p0_unsafe_candidate_requires_review() -> None:
    candidate = _build_candidates()[0]
    assert classify_review_decision(candidate) == REVIEW_DECISION_REVIEW_REQUIRED
    summary = summarize_backfill_candidates([candidate])
    assert summary["review_required_count"] == 1
    assert summary["auto_approvable_count"] == 0


def test_p1_fallback_candidate_needs_manifest_for_write_ready() -> None:
    candidate = _build_candidates()[1]
    proposal = build_safe_migration_proposal([candidate], None)
    assert classify_review_decision(candidate) == REVIEW_DECISION_AUTO_APPROVABLE
    assert proposal["migration_allowed"] is False
    assert proposal["summary"]["auto_approvable_count"] == 1
    assert proposal["proposal_items"][0]["write_ready"] is False
    assert proposal["proposal_items"][0]["status"] == REVIEW_DECISION_AUTO_APPROVABLE


def test_p1_fallback_candidate_can_be_write_ready_with_manifest() -> None:
    candidate = _build_candidates()[1]
    manifest = {
        "manifest_version": "p9-1.0",
        "reviewer": "replay-ops-reviewer",
        "approval_reason": "manual review approved fallback-only join",
        "timestamp": "2026-05-10T00:00:00Z",
        "entries": [
            {"source_ref": "fixture:prediction:2", "approved_fields": ["canonical_outcome_key_fallback"]}
        ],
    }
    proposal = build_safe_migration_proposal([candidate], manifest)
    assert proposal["migration_allowed"] is True
    assert proposal["proposal_items"][0]["write_ready"] is True
    assert proposal["proposal_items"][0]["status"] == REVIEW_DECISION_WRITE_READY


def test_p2_optional_candidate_can_be_auto_approvable_but_not_write_ready_without_manifest() -> None:
    candidate = _build_candidates()[2]
    proposal = build_safe_migration_proposal([candidate], None)
    assert classify_review_decision(candidate) == REVIEW_DECISION_AUTO_APPROVABLE
    assert proposal["migration_allowed"] is False
    assert proposal["proposal_items"][0]["write_ready"] is False
    assert proposal["proposal_items"][0]["status"] == REVIEW_DECISION_AUTO_APPROVABLE


def test_unknown_candidate_id_in_manifest_is_rejected() -> None:
    candidates = _build_candidates()
    manifest = {
        "manifest_version": "p9-1.0",
        "reviewer": "replay-ops-reviewer",
        "approval_reason": "manual review approved fallback-only join",
        "timestamp": "2026-05-10T00:00:00Z",
        "entries": [
            {"candidate_id": "unknown-candidate", "approved_fields": ["canonical_outcome_key_fallback"]}
        ],
    }
    validation = validate_approval_manifest(manifest, candidates)
    assert validation["valid"] is False
    assert any("unknown candidate reference" in error for error in validation["errors"])


def test_missing_manifest_fields_invalidate_manifest() -> None:
    candidates = _build_candidates()
    manifest = {
        "manifest_version": "p9-1.0",
        "entries": [{"source_ref": "fixture:prediction:2", "approved_fields": ["canonical_outcome_key_fallback"]}],
    }
    validation = validate_approval_manifest(manifest, candidates)
    assert validation["valid"] is False
    assert any("reviewer" in error for error in validation["errors"])
    assert any("approval_reason" in error for error in validation["errors"])
    assert any("timestamp" in error for error in validation["errors"])


def test_review_script_prints_marker_and_summary(tmp_path: Path) -> None:
    candidates_path = tmp_path / "candidates.jsonl"
    manifest_path = tmp_path / "manifest.json"
    _write_jsonl(candidates_path, _build_candidates())
    _write_json(
        manifest_path,
        {
            "manifest_version": "p9-1.0",
            "reviewer": "replay-ops-reviewer",
            "approval_reason": "manual review approved fallback-only join",
            "timestamp": "2026-05-10T00:00:00Z",
            "entries": [
                {"source_ref": "fixture:prediction:2", "approved_fields": ["canonical_outcome_key_fallback"]}
            ],
        },
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--candidates",
            str(candidates_path),
            "--approval-manifest",
            str(manifest_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    assert "READ_ONLY_BACKFILL_REVIEW" in result.stdout
    assert "migration_allowed: false" in result.stdout
    assert "total_candidates: 3" in result.stdout
    assert candidates_path.exists()
    assert manifest_path.exists()


def test_no_production_db_access_and_no_writes() -> None:
    script_source = SCRIPT_PATH.read_text(encoding="utf-8")
    helper_source = Path(__file__).resolve().parents[1] / "wbc_backend" / "reporting" / "strategy_replay_backfill_review.py"
    helper_text = helper_source.read_text(encoding="utf-8")
    assert "READ_ONLY_BACKFILL_REVIEW" in script_source
    assert "sqlite3" not in script_source
    assert "sqlalchemy" not in script_source
    assert "psycopg" not in script_source
    assert "db.connect" not in script_source
    assert "sqlite3" not in helper_text
    assert "sqlalchemy" not in helper_text
    assert "psycopg" not in helper_text