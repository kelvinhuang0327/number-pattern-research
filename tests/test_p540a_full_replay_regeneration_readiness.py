"""Tests for P540A full replay/prediction regeneration readiness (dry-run only)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import analysis.p540a_full_replay_regeneration_readiness as R

REPO_ROOT = Path(__file__).resolve().parents[1]
P539B_ARTIFACT = REPO_ROOT / "outputs/research/p539b_oos_availability_ingest_gap_gate_20260709.json"


def _build_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE draws (
            id INTEGER PRIMARY KEY,
            draw TEXT NOT NULL,
            date TEXT NOT NULL,
            lottery_type TEXT NOT NULL,
            numbers TEXT NOT NULL,
            special INTEGER DEFAULT 0
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE strategy_prediction_replays (
            id INTEGER PRIMARY KEY,
            lottery_type TEXT,
            strategy_id TEXT,
            target_draw TEXT,
            target_date TEXT,
            replay_status TEXT,
            bet_index INTEGER DEFAULT 1,
            dry_run INTEGER
        )
        """
    )
    # BIG_LOTTO: replayed up to 149; official draws exist up to 155 (6 new, unreplayed).
    for draw in range(100, 150):
        conn.execute(
            "INSERT INTO draws (draw, date, lottery_type, numbers) VALUES (?,?,?,?)",
            (str(draw), f"2026/01/{1 + (draw % 28):02d}", "BIG_LOTTO", "[1,2,3,4,5,6]"),
        )
        conn.execute(
            "INSERT INTO strategy_prediction_replays "
            "(lottery_type, strategy_id, target_draw, replay_status, bet_index, dry_run) "
            "VALUES ('BIG_LOTTO','strategy_a',?, 'PREDICTED', 1, 0)",
            (str(draw),),
        )
    for draw in range(150, 156):
        conn.execute(
            "INSERT INTO draws (draw, date, lottery_type, numbers) VALUES (?,?,?,?)",
            (str(draw), f"2026/02/{1 + (draw % 28):02d}", "BIG_LOTTO", "[1,2,3,4,5,6]"),
        )
    # DAILY_539: replayed up to 249; no new official draws beyond 249.
    for draw in range(200, 250):
        conn.execute(
            "INSERT INTO draws (draw, date, lottery_type, numbers) VALUES (?,?,?,?)",
            (str(draw), f"2026/03/{1 + (draw % 28):02d}", "DAILY_539", "[1,2,3,4,5]"),
        )
        conn.execute(
            "INSERT INTO strategy_prediction_replays "
            "(lottery_type, strategy_id, target_draw, replay_status, bet_index, dry_run) "
            "VALUES ('DAILY_539','strategy_b',?, 'PREDICTED', 1, 0)",
            (str(draw),),
        )
    # POWER_LOTTO: no rows in either table -> MAX(target_draw) is NULL -> gap == all draws.
    for draw in range(300, 305):
        conn.execute(
            "INSERT INTO draws (draw, date, lottery_type, numbers) VALUES (?,?,?,?)",
            (str(draw), f"2026/04/{1 + (draw % 28):02d}", "POWER_LOTTO", "[1,2,3,4,5,6]"),
        )
    conn.commit()
    conn.close()


def _fixture_p539b() -> dict:
    return {
        "generated_at": "2026-07-09T05:49:21.717221+00:00",
        "classification": "P539B_OOS_AVAILABILITY_INGEST_GAP_GATE_READY",
        "oos_feasibility_summary": {"feasible_now": False},
        "recommended_next_single_worker_task": {"proposed_task_id": "P539C (proposed, not yet authorized)"},
    }


def _write_p539b_fixture(tmp_path: Path) -> Path:
    p = tmp_path / "p539b.json"
    p.write_text(json.dumps(_fixture_p539b()), encoding="utf-8")
    return p


def test_build_current_db_readonly_snapshot_computes_gap_per_lottery(tmp_path):
    db = tmp_path / "synthetic.db"
    _build_db(db)
    conn = R._open_ro(db)
    try:
        snapshot = R.build_current_db_readonly_snapshot(conn)
    finally:
        conn.close()

    assert snapshot["BIG_LOTTO"]["raw_draws_count"] == 56
    assert snapshot["BIG_LOTTO"]["strategy_prediction_replays_count"] == 50
    assert snapshot["BIG_LOTTO"]["strategy_prediction_replays_latest_target_draw"] == "149"
    assert snapshot["BIG_LOTTO"]["gap_count_raw_draws_newer_than_latest_replayed_target_draw"] == 6

    assert snapshot["DAILY_539"]["gap_count_raw_draws_newer_than_latest_replayed_target_draw"] == 0

    # No replay rows at all for POWER_LOTTO -> gap must equal every existing draw, not crash on NULL MAX.
    assert snapshot["POWER_LOTTO"]["strategy_prediction_replays_count"] == 0
    assert snapshot["POWER_LOTTO"]["strategy_prediction_replays_latest_target_draw"] is None
    assert snapshot["POWER_LOTTO"]["gap_count_raw_draws_newer_than_latest_replayed_target_draw"] == 5


def test_full_vs_incremental_recommendation_is_always_incremental(tmp_path):
    db = tmp_path / "synthetic.db"
    _build_db(db)
    conn = R._open_ro(db)
    try:
        snapshot = R.build_current_db_readonly_snapshot(conn)
    finally:
        conn.close()

    rec = R.build_full_vs_incremental_recommendation(snapshot)
    assert rec["recommendation"] == "incremental"
    assert rec["per_lottery_incremental_scope"]["BIG_LOTTO"]["new_draws_to_generate"] == 6


def test_choose_recommended_next_task_daily539_meets_floor(tmp_path):
    db = tmp_path / "synthetic.db"
    _build_db(db)
    conn = R._open_ro(db)
    try:
        snapshot = R.build_current_db_readonly_snapshot(conn)
    finally:
        conn.close()

    # Lower the floor so the synthetic DAILY_539 gap (0) still fails, but BIG_LOTTO (6) passes,
    # to exercise the branch logic without depending on production-sized fixtures.
    snapshot["DAILY_539"]["meets_minimum_support_draws_floor_if_gap_replayed"] = False
    task = R.choose_recommended_next_task(snapshot)
    assert task["proposed_task_id"] == "P540A_BLOCKED_REPLAY_GENERATION_ENTRYPOINT_NOT_FOUND"
    assert task["not_run_in_this_task"] is True

    snapshot["DAILY_539"]["meets_minimum_support_draws_floor_if_gap_replayed"] = True
    task = R.choose_recommended_next_task(snapshot)
    assert task["proposed_task_id"] == "P540B_DAILY539_INCREMENTAL_REPLAY_GENERATION_DB_WRITE_MANIFESTED"


def test_db_connection_is_read_only(tmp_path):
    db = tmp_path / "synthetic.db"
    _build_db(db)
    conn = R._open_ro(db)
    try:
        try:
            conn.execute("INSERT INTO draws (draw, date, lottery_type, numbers) VALUES ('999','2026/01/01','X','[]')")
            conn.commit()
            assert False, "expected write to fail on read-only connection"
        except sqlite3.OperationalError:
            pass
    finally:
        conn.close()


def test_no_db_write_side_effects(tmp_path):
    db = tmp_path / "synthetic.db"
    _build_db(db)
    before = db.read_bytes()
    p539b_path = _write_p539b_fixture(tmp_path)
    R.run_analysis(db, p539b_path)
    after = db.read_bytes()
    assert before == after


def test_db_hash_recorded_and_unchanged(tmp_path):
    db = tmp_path / "synthetic.db"
    _build_db(db)
    p539b_path = _write_p539b_fixture(tmp_path)
    artifact = R.run_analysis(db, p539b_path)
    db_access = artifact["provenance_and_limits"]["db_access"]
    assert db_access["db_unchanged"] is True
    assert db_access["db_sha256_before"] == db_access["db_sha256_after"]


def test_write_artifacts_refuses_to_overwrite_existing_file(tmp_path):
    db = tmp_path / "synthetic.db"
    _build_db(db)
    p539b_path = _write_p539b_fixture(tmp_path)
    artifact = R.run_analysis(db, p539b_path)

    out_json = tmp_path / "existing.json"
    out_md = tmp_path / "existing.md"
    out_json.write_text("{}", encoding="utf-8")

    try:
        R.write_artifacts(artifact, out_json, out_md)
        assert False, "expected FileExistsError"
    except FileExistsError:
        pass


def test_determinism_two_runs_same_fixture_identical_payload(tmp_path):
    db = tmp_path / "synthetic.db"
    _build_db(db)
    p539b_path = _write_p539b_fixture(tmp_path)

    first = R.run_analysis(db, p539b_path)
    second = R.run_analysis(db, p539b_path)

    first_copy = dict(first)
    second_copy = dict(second)
    del first_copy["generated_at"]
    del second_copy["generated_at"]
    assert json.dumps(first_copy, sort_keys=True) == json.dumps(second_copy, sort_keys=True)


def test_artifact_schema_keys_present(tmp_path):
    db = tmp_path / "synthetic.db"
    _build_db(db)
    p539b_path = _write_p539b_fixture(tmp_path)
    artifact = R.run_analysis(db, p539b_path)

    for key in (
        "schema_version", "task_id", "upstream_task_ids", "generated_at", "classification",
        "summary", "current_db_readonly_snapshot", "p539b_context", "replay_generation_entrypoints",
        "dry_run_support", "full_vs_incremental_regeneration_recommendation", "future_write_scope",
        "safety_requirements_for_p540b", "blockers_or_unknowns", "recommended_next_single_worker_task",
        "provenance_and_limits", "disclaimer_en",
    ):
        assert key in artifact, f"missing artifact key: {key}"

    assert artifact["task_id"] == "P540A"
    assert R.DISCLAIMER_EN in artifact["disclaimer_en"]
    assert artifact["provenance_and_limits"]["disclaimer_en"] == R.DISCLAIMER_EN


def test_module_source_contains_no_replay_row_insert():
    """Negative dry-run-only guarantee: this readiness module must never insert replay rows."""
    source = Path(R.__file__).read_text(encoding="utf-8")
    assert "INSERT INTO strategy_prediction_replays" not in source
    assert "INSERT INTO strategy_replay_runs" not in source
    assert "DELETE FROM" not in source
    assert 'conn.execute("UPDATE' not in source
    assert "conn.execute('UPDATE" not in source


def test_module_source_opens_db_readonly_only():
    source = Path(R.__file__).read_text(encoding="utf-8")
    assert "mode=ro" in source
    assert "sqlite3.connect(db" not in source  # must go through the shared _open_ro helper


def test_existing_committed_artifacts_untouched_by_import_or_run(tmp_path):
    """Importing/running this module must never mutate any committed artifact it reads."""
    if not P539B_ARTIFACT.exists():
        return
    before = P539B_ARTIFACT.read_bytes()

    db = tmp_path / "synthetic.db"
    _build_db(db)
    p539b_path = _write_p539b_fixture(tmp_path)
    R.run_analysis(db, p539b_path)

    assert P539B_ARTIFACT.read_bytes() == before
