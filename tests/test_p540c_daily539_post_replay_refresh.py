"""Tests for P540C DAILY_539 post-replay refresh (read-only verification)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

import analysis.p540c_daily539_post_replay_refresh as R

APPLY_ID = "TEST_APPLY_P540C"
DRAWS = ["100000111", "100000112"]
STRATEGIES = ["s_a", "s_b", "s_c"]


def _build_db(path: Path, with_unique: bool = True) -> None:
    unique = (
        ", UNIQUE(lottery_type, target_draw, strategy_id, bet_index)"
        if with_unique
        else ""
    )
    conn = sqlite3.connect(path)
    conn.execute(
        f"""
        CREATE TABLE strategy_prediction_replays (
            id INTEGER PRIMARY KEY,
            lottery_type TEXT NOT NULL,
            target_draw TEXT NOT NULL,
            target_date TEXT,
            strategy_id TEXT NOT NULL,
            strategy_name TEXT,
            strategy_version TEXT,
            history_cutoff_draw TEXT,
            replay_status TEXT NOT NULL,
            reject_reason TEXT,
            predicted_numbers TEXT,
            predicted_special INTEGER,
            actual_numbers TEXT,
            actual_special INTEGER,
            hit_numbers TEXT,
            hit_count INTEGER DEFAULT 0,
            special_hit INTEGER DEFAULT 0,
            replay_run_id TEXT,
            generated_at TEXT,
            truth_level TEXT,
            controlled_apply_id TEXT,
            source TEXT,
            provenance_hash TEXT,
            provenance_source TEXT,
            dry_run INTEGER DEFAULT 0,
            prediction_cutoff_date TEXT,
            prediction_generated_at TEXT,
            bet_index INTEGER NOT NULL DEFAULT 1
            {unique}
        )
        """
    )

    def insert(lottery, draw, sid, apply_id, hit=1, bet_index=1):
        conn.execute(
            "INSERT INTO strategy_prediction_replays "
            "(lottery_type, target_draw, strategy_id, replay_status, hit_count, "
            " special_hit, controlled_apply_id, source, truth_level, "
            " provenance_hash, dry_run, bet_index) "
            "VALUES (?,?,?,?,?,0,?,?,?,?,0,?)",
            (lottery, draw, sid, "OK", hit, apply_id, "test", "REAL", "abc", bet_index),
        )

    # The P540C-scoped rows: 2 draws x 3 strategies, bet_index 1.
    for draw in DRAWS:
        for sid in STRATEGIES:
            insert("DAILY_539", draw, sid, APPLY_ID)
    # Pre-existing rows outside the apply-id scope (NULL controlled_apply_id,
    # as in production rows pre-dating the controlled-apply convention).
    insert("DAILY_539", "100000001", "s_old", None)
    insert("DAILY_539", "100000002", "s_old", None)
    for i, draw in enumerate(["200000001", "200000002", "200000003"]):
        insert("BIG_LOTTO", draw, f"b_{i}", None)
    for i, draw in enumerate(["300000001", "300000002", "300000003", "300000004"]):
        insert("POWER_LOTTO", draw, f"p_{i}", None)
    conn.commit()
    conn.close()


def _write_manifest(path: Path, db_path: Path, expected_rows: int = 6) -> None:
    doc = {
        "task_id": "P540B",
        "classification": "TEST_FIXTURE",
        "manifest": {
            "target_lottery": "DAILY_539",
            "controlled_apply_id": APPLY_ID,
            "expected_inserted_rows": expected_rows,
            "target_draw_ids": DRAWS,
            "target_draw_count": len(DRAWS),
            "in_scope_strategy_ids": STRATEGIES,
            "in_scope_strategy_id_count": len(STRATEGIES),
            "excluded_strategy_ids": {"s_excluded": "governance reason"},
            "excluded_bet_indices": {"s_a": "bet-1-only by design"},
        },
        "inserted_rows_by_draw": {d: len(STRATEGIES) for d in DRAWS},
        "post_write_snapshot": {
            "strategy_prediction_replays_count_by_lottery": {
                "BIG_LOTTO": 3,
                "DAILY_539": 8,
                "POWER_LOTTO": 4,
            },
            "strategy_prediction_replays_total": 15,
        },
        "db_access": {"db_sha256_after": R._file_sha256(db_path)},
    }
    path.write_text(json.dumps(doc), encoding="utf-8")


@pytest.fixture()
def fixture_env(tmp_path):
    db = tmp_path / "test.db"
    _build_db(db)
    manifest = tmp_path / "p540b_fixture.json"
    _write_manifest(manifest, db)
    return db, manifest, tmp_path


def _run_main(db, manifest, tmp_path):
    out_json = tmp_path / "out.json"
    out_md = tmp_path / "out.md"
    rc = R.main(
        [
            "--db",
            str(db),
            "--p540b-json",
            str(manifest),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ]
    )
    artifact = json.loads(out_json.read_text(encoding="utf-8"))
    return rc, artifact, out_md.read_text(encoding="utf-8")


def test_exact_match_pass_end_to_end(fixture_env):
    db, manifest, tmp_path = fixture_env
    rc, artifact, md = _run_main(db, manifest, tmp_path)
    assert rc == 0
    assert artifact["classification"] == R.CLASSIFICATION_READY
    assert artifact["p540b_manifest_match"]["all_checks_pass"] is True
    assert artifact["summary"]["p540b_rows_queryable"] is True
    assert artifact["summary"]["daily539_scope_only"] is True
    assert (
        artifact["summary"]["big_lotto_power_lotto_unchanged_from_p540b_invariant"]
        is True
    )
    assert (
        artifact["recommended_next_single_worker_task"]["proposed_task_id"]
        == R.NEXT_TASK_READY
    )
    # Required sections present.
    for section in (
        "summary",
        "p540b_manifest_match",
        "readonly_db_snapshot",
        "daily539_post_replay_coverage",
        "downstream_feasibility",
        "excluded_scope",
        "recommended_next_single_worker_task",
        "provenance_and_limits",
    ):
        assert section in artifact
    # Disclaimer in both artifacts.
    assert artifact["disclaimer_en"] == R.DISCLAIMER_EN
    assert R.DISCLAIMER_EN in md
    # Coverage details reflect the fixture rows.
    cov = artifact["daily539_post_replay_coverage"]
    assert cov["target_draw_range"] == {"min": DRAWS[0], "max": DRAWS[-1]}
    assert cov["rows_by_strategy"] == {sid: len(DRAWS) for sid in STRATEGIES}
    assert cov["bet_index_counts"] == {"1": 6}
    assert cov["hit_count_distribution"] == {"1": 6}


def test_row_count_mismatch_blocks(fixture_env):
    db, manifest, tmp_path = fixture_env
    conn = sqlite3.connect(db)
    conn.execute(
        "DELETE FROM strategy_prediction_replays WHERE controlled_apply_id = ? "
        "AND strategy_id = 's_c' AND target_draw = ?",
        (APPLY_ID, DRAWS[1]),
    )
    conn.commit()
    conn.close()
    rc, artifact, _ = _run_main(db, manifest, tmp_path)
    assert rc == 1
    assert artifact["classification"] == R.CLASSIFICATION_MISMATCH
    failed = artifact["p540b_manifest_match"]["failed_checks"]
    assert "apply_id_total_rows" in failed


def test_cross_lottery_scope_leak_blocks(fixture_env):
    db, manifest, tmp_path = fixture_env
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO strategy_prediction_replays "
        "(lottery_type, target_draw, strategy_id, replay_status, "
        " controlled_apply_id, bet_index) VALUES (?,?,?,?,?,1)",
        ("BIG_LOTTO", "200000009", "s_a", "OK", APPLY_ID),
    )
    conn.commit()
    conn.close()
    rc, artifact, _ = _run_main(db, manifest, tmp_path)
    assert rc == 1
    assert artifact["classification"] == R.CLASSIFICATION_MISMATCH
    failed = artifact["p540b_manifest_match"]["failed_checks"]
    assert "apply_id_rows_in_big_lotto_or_power_lotto" in failed
    assert artifact["summary"]["daily539_scope_only"] is False


def test_duplicate_identity_detected(tmp_path):
    db = tmp_path / "dupes.db"
    _build_db(db, with_unique=False)
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO strategy_prediction_replays "
        "(lottery_type, target_draw, strategy_id, replay_status, "
        " controlled_apply_id, bet_index) VALUES (?,?,?,?,?,1)",
        ("DAILY_539", DRAWS[0], "s_a", "OK", APPLY_ID),
    )
    conn.commit()
    conn.close()
    manifest = tmp_path / "p540b_fixture.json"
    _write_manifest(manifest, db)
    rc, artifact, _ = _run_main(db, manifest, tmp_path)
    assert rc == 1
    failed = artifact["p540b_manifest_match"]["failed_checks"]
    assert "duplicate_target_draw_strategy_bet_index_groups" in failed


def test_missing_rows_not_queryable(tmp_path):
    db = tmp_path / "empty.db"
    _build_db(db)
    conn = sqlite3.connect(db)
    conn.execute(
        "DELETE FROM strategy_prediction_replays WHERE controlled_apply_id = ?",
        (APPLY_ID,),
    )
    conn.commit()
    conn.close()
    manifest = tmp_path / "p540b_fixture.json"
    _write_manifest(manifest, db)
    rc, artifact, _ = _run_main(db, manifest, tmp_path)
    assert rc == 1
    assert artifact["classification"] == R.CLASSIFICATION_NOT_QUERYABLE
    assert artifact["summary"]["p540b_rows_queryable"] is False


def test_readonly_connection_blocks_writes(fixture_env):
    db, _, _ = fixture_env
    conn = R._open_ro(db)
    with pytest.raises(sqlite3.OperationalError):
        conn.execute(
            "INSERT INTO strategy_prediction_replays "
            "(lottery_type, target_draw, strategy_id, replay_status) "
            "VALUES ('DAILY_539','1','x','OK')"
        )
    conn.close()


def test_db_hash_and_mtime_unchanged_by_run(fixture_env):
    db, manifest, tmp_path = fixture_env
    before = R._file_sha256(db)
    rc, artifact, _ = _run_main(db, manifest, tmp_path)
    assert rc == 0
    assert R._file_sha256(db) == before
    snap = artifact["readonly_db_snapshot"]
    assert snap["db_unchanged_during_task"] is True
    assert snap["before"]["sha256"] == snap["after"]["sha256"] == before
    assert artifact["summary"]["db_unchanged_during_task"] is True


def test_spec_pins_gate_real_apply_id(tmp_path):
    """A manifest claiming the REAL P540B apply id must satisfy the spec pins."""
    db = tmp_path / "real_id.db"
    _build_db(db)
    conn = sqlite3.connect(db)
    conn.execute(
        "UPDATE strategy_prediction_replays SET controlled_apply_id = ? "
        "WHERE controlled_apply_id = ?",
        (R.P540B_APPLY_ID, APPLY_ID),
    )
    conn.commit()
    conn.close()
    manifest = tmp_path / "p540b_fixture.json"
    _write_manifest(manifest, db)
    doc = json.loads(manifest.read_text(encoding="utf-8"))
    doc["manifest"]["controlled_apply_id"] = R.P540B_APPLY_ID
    manifest.write_text(json.dumps(doc), encoding="utf-8")
    rc, artifact, _ = _run_main(db, manifest, tmp_path)
    assert rc == 1
    failed = artifact["p540b_manifest_match"]["failed_checks"]
    assert "spec_pin_expected_rows_agrees_with_p540b_manifest" in failed
