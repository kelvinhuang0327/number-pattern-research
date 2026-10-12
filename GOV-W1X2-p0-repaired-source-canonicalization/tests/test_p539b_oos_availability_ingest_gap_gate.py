"""Tests for P539B OOS availability / ingest-gap gate."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import analysis.p539b_oos_availability_ingest_gap_gate as G

REPO_ROOT = Path(__file__).resolve().parents[1]
P539A_ARTIFACT = REPO_ROOT / "outputs/research/p539a_readonly_per_draw_replay_export_20260709.json"
P538A_ARTIFACT = REPO_ROOT / "outputs/research/p538a_strategy_candidate_evaluation_readiness_20260709.json"
P537A_ARTIFACT = REPO_ROOT / "outputs/research/p537a_shortlist_robustness_review_20260709.json"
P536K_ARTIFACT = REPO_ROOT / "outputs/research/p536k_lift_candidate_shortlist_20260708.json"
P536C_ARTIFACT = REPO_ROOT / "outputs/research/p536c_success_matrix_lift_extension_20260708.json"


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
            "INSERT INTO strategy_prediction_replays (lottery_type, strategy_id, target_draw, replay_status, dry_run) "
            "VALUES ('BIG_LOTTO','strategy_a',?, 'PREDICTED', 0)",
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
            "INSERT INTO strategy_prediction_replays (lottery_type, strategy_id, target_draw, replay_status, dry_run) "
            "VALUES ('DAILY_539','strategy_b',?, 'PREDICTED', 0)",
            (str(draw),),
        )
    conn.commit()
    conn.close()


def _fixture_p539a() -> dict:
    return {
        "task_id": "P539A",
        "generated_at": "2026-01-01T00:00:00+00:00",
        "classification": "P539A_READONLY_PER_DRAW_REPLAY_EXPORT_READY",
        "candidate_index": [
            {
                "candidate_group": "stable_review_candidate",
                "candidate_id": "stable|BIG_LOTTO|strategy_a|w750|k1",
                "lottery_type": "BIG_LOTTO",
                "strategy_id": "strategy_a",
                "recovered_earliest_target_draw": "100",
                "recovered_latest_target_draw": "149",
            },
            {
                "candidate_group": "stable_review_candidate",
                "candidate_id": "stable|DAILY_539|strategy_b|w300|k1",
                "lottery_type": "DAILY_539",
                "strategy_id": "strategy_b",
                "recovered_earliest_target_draw": "200",
                "recovered_latest_target_draw": "249",
            },
            {
                "candidate_group": "combination_review_candidate",
                "candidate_id": "combo|BIG_LOTTO|strategy_a:1",
                "lottery_type": "BIG_LOTTO",
                "combo_id": "strategy_a:1",
                "per_window_cutoffs": {
                    "750": {"recovery_status": "RECOVERED_FROM_P536C", "recovered_latest_target_draw": "148"}
                },
            },
        ],
        "readiness": {
            "new_draws_found_since_last_replay_cutoff": False,
            "p539b_rolling_oos_evaluator_feasible_from_this_export_alone": False,
            "db_max_target_draw_by_lottery": {"BIG_LOTTO": 149, "DAILY_539": 249},
            "distinct_strategy_ids_covered": 2,
            "rows_exported_by_candidate_group": {"stable_review_candidate": 2, "combination_review_candidate": 1},
        },
    }


def _fixture_p536c(minimum_support_draws: int = 30) -> dict:
    return {
        "generated_at": "2026-01-01T00:00:00+00:00",
        "window_policy": {"minimum_support_draws": minimum_support_draws},
    }


def _write_fixtures(tmp_path: Path, p536c: dict | None = None) -> tuple[Path, Path, Path, Path, Path]:
    p539a_path = tmp_path / "p539a.json"
    p538a_path = tmp_path / "p538a.json"
    p537a_path = tmp_path / "p537a.json"
    p536k_path = tmp_path / "p536k.json"
    p536c_path = tmp_path / "p536c.json"

    p539a_path.write_text(json.dumps(_fixture_p539a()), encoding="utf-8")
    p538a_path.write_text(json.dumps({"generated_at": "2026-01-01T00:00:00+00:00"}), encoding="utf-8")
    p537a_path.write_text(json.dumps({"note": "not deep-parsed by P539B"}), encoding="utf-8")
    p536k_path.write_text(json.dumps({"note": "not deep-parsed by P539B"}), encoding="utf-8")
    p536c_path.write_text(json.dumps(p536c if p536c is not None else _fixture_p536c()), encoding="utf-8")

    return p539a_path, p538a_path, p537a_path, p536k_path, p536c_path


def test_cutoffs_by_lottery_from_candidate_index_covers_stable_and_combo():
    cutoffs = G.cutoffs_by_lottery_from_candidate_index(_fixture_p539a()["candidate_index"])
    assert cutoffs["BIG_LOTTO"]["min_latest"] == 148
    assert cutoffs["BIG_LOTTO"]["max_latest"] == 149
    assert cutoffs["DAILY_539"]["min_latest"] == 249
    assert cutoffs["DAILY_539"]["max_latest"] == 249


def test_query_draws_table_availability_finds_new_draws_beyond_cutoff(tmp_path):
    db = tmp_path / "synthetic.db"
    _build_db(db)
    conn = G._open_ro(db)
    try:
        info = G.query_draws_table_availability(conn, "BIG_LOTTO", max_latest=149, min_latest=148)
    finally:
        conn.close()
    assert info["draws_table_max_draw"] == 155
    assert info["new_official_draws_beyond_all_candidates_cutoff"] == 6
    assert info["new_official_draws_beyond_any_candidate_cutoff"] == 7
    assert len(info["new_official_draws_sample"]) == 6


def test_query_draws_table_availability_zero_when_no_new_draws(tmp_path):
    db = tmp_path / "synthetic.db"
    _build_db(db)
    conn = G._open_ro(db)
    try:
        info = G.query_draws_table_availability(conn, "DAILY_539", max_latest=249, min_latest=249)
    finally:
        conn.close()
    assert info["new_official_draws_beyond_all_candidates_cutoff"] == 0


def test_run_analysis_flags_replay_generation_gap_for_big_lotto(tmp_path):
    db = tmp_path / "synthetic.db"
    _build_db(db)
    paths = _write_fixtures(tmp_path, p536c=_fixture_p536c(minimum_support_draws=30))

    artifact = G.run_analysis(db, *paths)

    big_lotto = artifact["new_draw_availability_by_lottery"]["BIG_LOTTO"]
    assert big_lotto["new_official_draws_beyond_all_candidates_cutoff"] == 6
    assert big_lotto["meets_minimum_support_draws_if_replayed_today"] is False
    assert big_lotto["additional_official_draws_needed_to_reach_minimum_support_draws"] == 24

    summary = artifact["oos_feasibility_summary"]
    assert summary["feasible_now"] is False
    assert summary["any_new_official_draws_beyond_cutoff"] is True
    assert summary["per_lottery"]["BIG_LOTTO"]["classification"] == "blocked_needs_readonly_ingest_gap_audit"
    assert summary["per_lottery"]["DAILY_539"]["classification"] == "blocked_no_new_draws"


def test_run_analysis_meets_support_floor_when_enough_new_draws(tmp_path):
    db = tmp_path / "synthetic.db"
    _build_db(db)
    paths = _write_fixtures(tmp_path, p536c=_fixture_p536c(minimum_support_draws=5))

    artifact = G.run_analysis(db, *paths)
    big_lotto = artifact["new_draw_availability_by_lottery"]["BIG_LOTTO"]
    assert big_lotto["meets_minimum_support_draws_if_replayed_today"] is True
    assert big_lotto["additional_official_draws_needed_to_reach_minimum_support_draws"] == 0


def test_missing_data_or_ingest_gaps_distinguishes_gap_types(tmp_path):
    db = tmp_path / "synthetic.db"
    _build_db(db)
    paths = _write_fixtures(tmp_path)
    artifact = G.run_analysis(db, *paths)

    gaps_by_lottery = {g["lottery_type"]: g for g in artifact["missing_data_or_ingest_gaps"]}
    assert gaps_by_lottery["BIG_LOTTO"]["gap_type"] == "replay_generation_gap"
    assert gaps_by_lottery["DAILY_539"]["gap_type"] == "no_new_draws_yet"


def test_db_connection_is_read_only(tmp_path):
    db = tmp_path / "synthetic.db"
    _build_db(db)
    conn = G._open_ro(db)
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
    paths = _write_fixtures(tmp_path)
    G.run_analysis(db, *paths)
    after = db.read_bytes()
    assert before == after


def test_db_hash_recorded_and_unchanged(tmp_path):
    db = tmp_path / "synthetic.db"
    _build_db(db)
    paths = _write_fixtures(tmp_path)
    artifact = G.run_analysis(db, *paths)
    db_access = artifact["provenance_and_limits"]["db_access"]
    assert db_access["db_unchanged"] is True
    assert db_access["db_sha256_before"] == db_access["db_sha256_after"]


def test_write_artifacts_refuses_to_overwrite_existing_file(tmp_path):
    db = tmp_path / "synthetic.db"
    _build_db(db)
    paths = _write_fixtures(tmp_path)
    artifact = G.run_analysis(db, *paths)

    out_json = tmp_path / "existing.json"
    out_md = tmp_path / "existing.md"
    out_json.write_text("{}", encoding="utf-8")

    try:
        G.write_artifacts(artifact, out_json, out_md)
        assert False, "expected FileExistsError"
    except FileExistsError:
        pass


def test_determinism_two_runs_same_fixture_identical_payload(tmp_path):
    db = tmp_path / "synthetic.db"
    _build_db(db)
    paths = _write_fixtures(tmp_path)

    first = G.run_analysis(db, *paths)
    second = G.run_analysis(db, *paths)

    first_copy = dict(first)
    second_copy = dict(second)
    del first_copy["generated_at"]
    del second_copy["generated_at"]
    assert json.dumps(first_copy, sort_keys=True) == json.dumps(second_copy, sort_keys=True)


def test_artifact_schema_keys_present(tmp_path):
    db = tmp_path / "synthetic.db"
    _build_db(db)
    paths = _write_fixtures(tmp_path)
    artifact = G.run_analysis(db, *paths)

    for key in (
        "schema_version", "task_id", "upstream_task_ids", "generated_at", "classification",
        "oos_feasibility_summary", "p539a_source_export_findings", "new_draw_availability_by_lottery",
        "missing_data_or_ingest_gaps", "minimum_data_needed_for_p539c_or_oos_evaluator",
        "recommended_next_single_worker_task", "provenance_and_limits", "disclaimer_en",
    ):
        assert key in artifact, f"missing artifact key: {key}"

    assert artifact["task_id"] == "P539B"
    assert G.DISCLAIMER_EN in artifact["disclaimer_en"]
    assert artifact["provenance_and_limits"]["disclaimer_en"] == G.DISCLAIMER_EN


def test_existing_committed_artifacts_untouched_by_import_or_run(tmp_path):
    """Importing/running this module must never mutate any committed artifact it reads."""
    paths_to_check = [P539A_ARTIFACT, P538A_ARTIFACT, P537A_ARTIFACT, P536K_ARTIFACT, P536C_ARTIFACT]
    existing = [p for p in paths_to_check if p.exists()]
    if not existing:
        return
    before = {p: p.read_bytes() for p in existing}

    db = tmp_path / "synthetic.db"
    _build_db(db)
    fixture_paths = _write_fixtures(tmp_path)
    G.run_analysis(db, *fixture_paths)

    for p in existing:
        assert p.read_bytes() == before[p], f"artifact mutated: {p}"
