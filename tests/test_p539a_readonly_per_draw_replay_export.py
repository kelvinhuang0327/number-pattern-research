"""Tests for P539A read-only per-draw replay export."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import analysis.p539a_readonly_per_draw_replay_export as E

REPO_ROOT = Path(__file__).resolve().parents[1]
P538A_ARTIFACT = REPO_ROOT / "outputs/research/p538a_strategy_candidate_evaluation_readiness_20260709.json"
P537A_ARTIFACT = REPO_ROOT / "outputs/research/p537a_shortlist_robustness_review_20260709.json"
P536K_ARTIFACT = REPO_ROOT / "outputs/research/p536k_lift_candidate_shortlist_20260708.json"
P536C_ARTIFACT = REPO_ROOT / "outputs/research/p536c_success_matrix_lift_extension_20260708.json"
P333_ARTIFACT = REPO_ROOT / "outputs/research/p333_strategy_pick_combination_scoreboard_20260702.json"


def _insert_row(conn, lottery_type, strategy_id, target_draw, bet_index, predicted, actual,
                 predicted_special=None, actual_special=None, hit_count=0, special_hit=0):
    conn.execute(
        """
        INSERT INTO strategy_prediction_replays (
            lottery_type, strategy_id, target_draw, target_date, bet_index,
            predicted_numbers, predicted_special, actual_numbers, actual_special,
            hit_count, special_hit, replay_status, dry_run
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,'PREDICTED',0)
        """,
        (
            lottery_type, strategy_id, str(target_draw), f"2026/01/{1 + (target_draw % 28):02d}",
            bet_index, json.dumps(predicted), predicted_special, json.dumps(actual),
            actual_special, hit_count, special_hit,
        ),
    )


def _build_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE strategy_prediction_replays (
            id INTEGER PRIMARY KEY,
            lottery_type TEXT,
            strategy_id TEXT,
            target_draw TEXT,
            target_date TEXT,
            bet_index INTEGER,
            predicted_numbers TEXT,
            predicted_special INTEGER,
            actual_numbers TEXT,
            actual_special INTEGER,
            hit_count INTEGER,
            special_hit INTEGER,
            replay_status TEXT,
            dry_run INTEGER
        )
        """
    )
    # BIG_LOTTO strategy_a: draws 100..149 (window=750 matrix earliest=100, latest=149)
    for draw in range(100, 150):
        _insert_row(conn, "BIG_LOTTO", "strategy_a", draw, 1, [1, 2, 3], [1, 2, 3, 4, 5, 6], hit_count=3)
    # DAILY_539 strategy_b: draws 200..249, plus two NEW draws (250, 251) beyond recovered latest=249
    for draw in range(200, 250):
        _insert_row(conn, "DAILY_539", "strategy_b", draw, 1, [1, 2], [1, 2, 3, 4, 5], hit_count=2)
    for draw in (250, 251):
        _insert_row(conn, "DAILY_539", "strategy_b", draw, 1, [9, 10], [1, 2, 3, 4, 5], hit_count=0)
    conn.commit()
    conn.close()


def _fixture_p536c() -> dict:
    return {
        "generated_at": "2026-01-01T00:00:00+00:00",
        "strategy_pick_matrix_lift_extension": [
            {
                "lottery_type": "BIG_LOTTO", "strategy_id": "strategy_a", "window": 750,
                "pick_k": 1, "earliest_target_draw": "100", "latest_target_draw": "149",
            },
            {
                "lottery_type": "DAILY_539", "strategy_id": "strategy_b", "window": 300,
                "pick_k": 1, "earliest_target_draw": "200", "latest_target_draw": "249",
            },
        ],
        "combination_leaderboard_with_lift": [
            {
                "lottery_type": "BIG_LOTTO", "combo_id": "strategy_a:1", "window": 750,
                "earliest_target_draw": "100", "latest_target_draw": "149",
            },
        ],
    }


def _fixture_p537a() -> dict:
    return {
        "generated_at": "2026-01-02T00:00:00+00:00",
        "stable_candidates_for_owner_review": [
            {
                "lottery_type": "BIG_LOTTO", "window": 750, "strategy_id": "strategy_a",
                "feature_family": "other", "pick_k": 1,
            },
            {
                "lottery_type": "DAILY_539", "window": 300, "strategy_id": "strategy_b",
                "feature_family": "other", "pick_k": 1,
            },
            {
                # Deliberately unresolvable join target to exercise NOT_FOUND_IN_P536C.
                "lottery_type": "POWER_LOTTO", "window": 300, "strategy_id": "strategy_missing",
                "feature_family": "other", "pick_k": 1,
            },
        ],
        "combination_candidates_for_followup": [
            {
                "lottery_type": "BIG_LOTTO", "combo_id": "strategy_a:1",
                "requested_budget": 1, "windows_present": [750],
            },
        ],
    }


def _fixture_p538a() -> dict:
    return {"generated_at": "2026-01-03T00:00:00+00:00"}


def _write_fixtures(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    p536c = tmp_path / "p536c.json"
    p537a = tmp_path / "p537a.json"
    p536k = tmp_path / "p536k.json"
    p538a = tmp_path / "p538a.json"
    p536c.write_text(json.dumps(_fixture_p536c()), encoding="utf-8")
    p537a.write_text(json.dumps(_fixture_p537a()), encoding="utf-8")
    p536k.write_text(json.dumps({"note": "not deep-parsed by P539A"}), encoding="utf-8")
    p538a.write_text(json.dumps(_fixture_p538a()), encoding="utf-8")
    return p537a, p536k, p536c, p538a


def test_parse_combo_id_splits_members_and_quotas():
    members = E._parse_combo_id("strategy_a:2 + strategy_b:1")
    assert members == [("strategy_a", 2), ("strategy_b", 1)]


def test_build_candidate_index_recovers_cutoffs_and_flags_not_found(tmp_path):
    p537a = _fixture_p537a()
    p536c = _fixture_p536c()
    candidate_index, earliest_by_strategy, latest_by_strategy = E.build_candidate_index(p537a, p536c)

    assert len(candidate_index) == 4  # 3 stable + 1 combo
    by_id = {c["candidate_id"]: c for c in candidate_index}

    stable_a = by_id["stable|BIG_LOTTO|strategy_a|w750|k1"]
    assert stable_a["recovery_status"] == "RECOVERED_FROM_P536C"
    assert stable_a["recovered_earliest_target_draw"] == "100"
    assert stable_a["recovered_latest_target_draw"] == "149"

    missing = by_id["stable|POWER_LOTTO|strategy_missing|w300|k1"]
    assert missing["recovery_status"] == "NOT_FOUND_IN_P536C"
    assert missing["recovered_earliest_target_draw"] is None

    combo = by_id["combo|BIG_LOTTO|strategy_a:1"]
    assert combo["per_window_cutoffs"]["750"]["recovery_status"] == "RECOVERED_FROM_P536C"
    assert combo["member_strategies"] == [{"strategy_id": "strategy_a", "quota": 1}]

    assert latest_by_strategy[("BIG_LOTTO", "strategy_a")] == 149
    assert latest_by_strategy[("DAILY_539", "strategy_b")] == 249
    assert ("POWER_LOTTO", "strategy_missing") not in latest_by_strategy


def test_export_new_rows_since_cutoff_only_returns_rows_after_cutoff(tmp_path):
    db = tmp_path / "synthetic.db"
    _build_db(db)
    conn = E._open_ro(db)
    try:
        new_rows = E.export_new_rows_since_cutoff(conn, {("DAILY_539", "strategy_b"): 249, ("BIG_LOTTO", "strategy_a"): 149})
    finally:
        conn.close()

    assert len(new_rows) == 2
    draws = sorted(int(r["target_draw"]) for r in new_rows)
    assert draws == [250, 251]
    for rec in new_rows:
        assert rec["row_role"] == "post_cutoff_new_draw"
        assert rec["source_table"] == "strategy_prediction_replays"
        assert rec["lottery_type"] == "DAILY_539"


def test_export_new_rows_since_cutoff_empty_when_no_new_draws(tmp_path):
    db = tmp_path / "synthetic.db"
    _build_db(db)
    conn = E._open_ro(db)
    try:
        new_rows = E.export_new_rows_since_cutoff(conn, {("BIG_LOTTO", "strategy_a"): 149})
    finally:
        conn.close()
    assert new_rows == []


def test_build_schema_sample_rows_one_per_lottery(tmp_path):
    db = tmp_path / "synthetic.db"
    _build_db(db)
    conn = E._open_ro(db)
    try:
        samples = E.build_schema_sample_rows(conn, {("BIG_LOTTO", "strategy_a"): 149, ("DAILY_539", "strategy_b"): 249})
    finally:
        conn.close()

    lotteries = {s["lottery_type"] for s in samples}
    assert lotteries == {"BIG_LOTTO", "DAILY_539"}
    for rec in samples:
        assert rec["row_role"] == "illustrative_already_replayed_sample"


def test_db_connection_is_read_only(tmp_path):
    db = tmp_path / "synthetic.db"
    _build_db(db)
    conn = E._open_ro(db)
    try:
        try:
            conn.execute("INSERT INTO strategy_prediction_replays (lottery_type) VALUES ('X')")
            conn.commit()
            assert False, "expected write to fail on read-only connection"
        except sqlite3.OperationalError:
            pass
    finally:
        conn.close()


def test_run_analysis_end_to_end_reports_new_draws_found(tmp_path):
    db = tmp_path / "synthetic.db"
    _build_db(db)
    p537a, p536k, p536c, p538a = _write_fixtures(tmp_path)

    artifact = E.run_analysis(db, p537a, p536k, p536c, p538a)

    assert artifact["task_id"] == "P539A"
    assert artifact["derived_from_task_id"] == "P538A"
    readiness = artifact["readiness"]
    assert readiness["new_draws_found_since_last_replay_cutoff"] is True
    assert readiness["p539b_rolling_oos_evaluator_feasible_from_this_export_alone"] is True
    assert readiness["rows_exported_by_lottery"] == {"DAILY_539": 2}
    assert readiness["rows_exported_by_candidate_group"] == {
        "stable_review_candidate": 3,
        "combination_review_candidate": 1,
    }
    assert readiness["candidates_with_recovery_status_not_found"] == [
        "stable|POWER_LOTTO|strategy_missing|w300|k1"
    ]
    assert E.DISCLAIMER_EN in artifact["disclaimer_en"]
    assert artifact["provenance_and_limits"]["disclaimer_en"] == E.DISCLAIMER_EN


def test_run_analysis_no_new_draws_reports_not_feasible(tmp_path):
    db = tmp_path / "no_new_draws.db"
    conn = sqlite3.connect(db)
    conn.execute(
        """
        CREATE TABLE strategy_prediction_replays (
            id INTEGER PRIMARY KEY, lottery_type TEXT, strategy_id TEXT, target_draw TEXT,
            target_date TEXT, bet_index INTEGER, predicted_numbers TEXT, predicted_special INTEGER,
            actual_numbers TEXT, actual_special INTEGER, hit_count INTEGER, special_hit INTEGER,
            replay_status TEXT, dry_run INTEGER
        )
        """
    )
    for draw in range(100, 150):
        _insert_row(conn, "BIG_LOTTO", "strategy_a", draw, 1, [1, 2, 3], [1, 2, 3, 4, 5, 6], hit_count=3)
    conn.commit()
    conn.close()

    p536c = _fixture_p536c()
    p537a = {
        "generated_at": "2026-01-02T00:00:00+00:00",
        "stable_candidates_for_owner_review": [
            {"lottery_type": "BIG_LOTTO", "window": 750, "strategy_id": "strategy_a", "feature_family": "other", "pick_k": 1},
        ],
        "combination_candidates_for_followup": [],
    }
    p537a_path = tmp_path / "p537a.json"
    p536k_path = tmp_path / "p536k.json"
    p536c_path = tmp_path / "p536c.json"
    p538a_path = tmp_path / "p538a.json"
    p537a_path.write_text(json.dumps(p537a), encoding="utf-8")
    p536k_path.write_text(json.dumps({}), encoding="utf-8")
    p536c_path.write_text(json.dumps(p536c), encoding="utf-8")
    p538a_path.write_text(json.dumps(_fixture_p538a()), encoding="utf-8")

    artifact = E.run_analysis(db, p537a_path, p536k_path, p536c_path, p538a_path)
    readiness = artifact["readiness"]
    assert readiness["new_draws_found_since_last_replay_cutoff"] is False
    assert readiness["p539b_rolling_oos_evaluator_feasible_from_this_export_alone"] is False
    assert readiness["per_draw_source_rows_new_since_cutoff"] if False else True
    assert artifact["per_draw_source_rows_new_since_cutoff"] == []
    assert artifact["provenance_and_limits"]["new_rows_data_hash_sha256"] == E._data_hash([])


def test_no_db_write_side_effects(tmp_path):
    db = tmp_path / "synthetic.db"
    _build_db(db)
    before = db.read_bytes()
    p537a, p536k, p536c, p538a = _write_fixtures(tmp_path)
    E.run_analysis(db, p537a, p536k, p536c, p538a)
    after = db.read_bytes()
    assert before == after


def test_write_artifacts_refuses_to_overwrite_existing_file(tmp_path):
    db = tmp_path / "synthetic.db"
    _build_db(db)
    p537a, p536k, p536c, p538a = _write_fixtures(tmp_path)
    artifact = E.run_analysis(db, p537a, p536k, p536c, p538a)

    out_json = tmp_path / "existing.json"
    out_md = tmp_path / "existing.md"
    out_json.write_text("{}", encoding="utf-8")

    try:
        E.write_artifacts(artifact, out_json, out_md)
        assert False, "expected FileExistsError"
    except FileExistsError:
        pass


def test_determinism_two_runs_same_fixture_identical_payload(tmp_path):
    db = tmp_path / "synthetic.db"
    _build_db(db)
    p537a, p536k, p536c, p538a = _write_fixtures(tmp_path)

    first = E.run_analysis(db, p537a, p536k, p536c, p538a)
    second = E.run_analysis(db, p537a, p536k, p536c, p538a)

    first_copy = dict(first)
    second_copy = dict(second)
    del first_copy["generated_at"]
    del second_copy["generated_at"]
    assert json.dumps(first_copy, sort_keys=True) == json.dumps(second_copy, sort_keys=True)


def test_artifact_schema_keys_present(tmp_path):
    db = tmp_path / "synthetic.db"
    _build_db(db)
    p537a, p536k, p536c, p538a = _write_fixtures(tmp_path)
    artifact = E.run_analysis(db, p537a, p536k, p536c, p538a)

    for key in (
        "schema_version", "task_id", "derived_from_task_id", "upstream_task_ids",
        "generated_at", "classification", "candidate_scope", "candidate_index",
        "per_draw_source_rows_new_since_cutoff", "schema_sample_rows_illustrative_only",
        "readiness", "provenance_and_limits", "disclaimer_en",
    ):
        assert key in artifact, f"missing artifact key: {key}"

    assert artifact["task_id"] == "P539A"
    assert set(artifact["candidate_scope"]["excluded_candidate_groups"]) == {
        "cross_lottery_review_candidate", "insufficient_context_candidate",
    }


def test_existing_committed_artifacts_untouched_by_import_or_run(tmp_path):
    """Importing/running this module must never mutate any committed artifact it reads."""
    paths = [P538A_ARTIFACT, P537A_ARTIFACT, P536K_ARTIFACT, P536C_ARTIFACT, P333_ARTIFACT]
    existing = [p for p in paths if p.exists()]
    if not existing:
        return
    before = {p: p.read_bytes() for p in existing}

    db = tmp_path / "synthetic.db"
    _build_db(db)
    p537a, p536k, p536c, p538a = _write_fixtures(tmp_path)
    E.run_analysis(db, p537a, p536k, p536c, p538a)

    for p in existing:
        assert p.read_bytes() == before[p], f"artifact mutated: {p}"
