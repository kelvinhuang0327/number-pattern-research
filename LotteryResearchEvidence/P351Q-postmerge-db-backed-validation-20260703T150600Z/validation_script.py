"""
P351Q read-only DB-backed validation for PR #482 (merge commit 04511801).

Does NOT touch the disposable worktree's filesystem and does NOT symlink/copy
the canonical DB. Opens its own explicit sqlite3 URI connection with
mode=ro (+ PRAGMA query_only=ON) directly against the canonical DB path,
purely for SELECT queries. Imports the *actual merged* pure functions from
the PR #482 worktree (lottery_api/routes/replay.py, replay_strategy_registry)
to reuse the real classification/shaping logic rather than reimplementing it.
"""
import sqlite3
import sys
from pathlib import Path

WORKTREE = Path("/Users/kelvin/Kelvin-WorkSpace/LotteryNew-p351q-postmerge-db-validation")
CANONICAL_DB = Path("/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api/data/lottery_v2.db")

sys.path.insert(0, str(WORKTREE / "lottery_api"))
sys.path.insert(0, str(WORKTREE))

from routes import replay as replay_mod  # noqa: E402
from models.replay_strategy_registry import (  # noqa: E402
    list_strategy_lifecycle_metadata,
    list_executable_strategy_ids,
)


def ro_conn():
    conn = sqlite3.connect(f"file:{CANONICAL_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")
    return conn


def derive_bet_count(sid):
    return replay_mod._derive_bet_count(sid)


def parse_bet_indices_csv(csv_val):
    return replay_mod._parse_bet_indices_csv(csv_val)


def build_db_index():
    conn = ro_conn()
    try:
        db_rows = conn.execute(
            """
            SELECT
                lottery_type,
                strategy_id,
                MAX(strategy_name) AS db_strategy_name,
                COUNT(*)  AS total_rows,
                COUNT(DISTINCT target_draw) AS distinct_draw_count,
                MAX(bet_index) AS max_bet_index,
                GROUP_CONCAT(DISTINCT bet_index) AS bet_indices_csv,
                MIN(CAST(target_draw AS INTEGER)) AS min_draw_int,
                MAX(CAST(target_draw AS INTEGER)) AS max_draw_int,
                SUM(CASE WHEN replay_status='PREDICTED'            THEN 1 ELSE 0 END) AS predicted_cnt,
                SUM(CASE WHEN replay_status='REJECTED'             THEN 1 ELSE 0 END) AS rejected_cnt,
                SUM(CASE WHEN replay_status='INSUFFICIENT_HISTORY' THEN 1 ELSE 0 END) AS insuf_cnt,
                SUM(CASE WHEN replay_status='REPLAY_ERROR'         THEN 1 ELSE 0 END) AS error_cnt,
                SUM(CASE WHEN replay_status='STRATEGY_UNAVAILABLE' THEN 1 ELSE 0 END) AS unavail_cnt
            FROM strategy_prediction_replays
            GROUP BY lottery_type, strategy_id
            """,
        ).fetchall()
    finally:
        conn.close()
    idx = {}
    for r in db_rows:
        key = (r["lottery_type"], r["strategy_id"])
        idx[key] = {
            "db_strategy_name": r["db_strategy_name"],
            "total_rows": r["total_rows"],
            "distinct_draw_count": r["distinct_draw_count"] or 0,
            "max_bet_index": r["max_bet_index"] or 0,
            "available_bet_indices": parse_bet_indices_csv(r["bet_indices_csv"]),
            "min_target_draw": str(r["min_draw_int"]) if r["min_draw_int"] else None,
            "max_target_draw": str(r["max_draw_int"]) if r["max_draw_int"] else None,
            "latest_target_draw": str(r["max_draw_int"]) if r["max_draw_int"] else None,
            "replay_status_summary": {
                "PREDICTED": r["predicted_cnt"] or 0,
                "REJECTED": r["rejected_cnt"] or 0,
                "INSUFFICIENT_HISTORY": r["insuf_cnt"] or 0,
                "REPLAY_ERROR": r["error_cnt"] or 0,
                "STRATEGY_UNAVAILABLE": r["unavail_cnt"] or 0,
            },
        }
    return idx


def check_1_and_check_2_and_3():
    all_meta = list_strategy_lifecycle_metadata()
    exec_ids = set(list_executable_strategy_ids())
    db_index = build_db_index()

    rows = []
    for meta in all_meta:
        sid = meta["strategy_id"]
        derived_bets = derive_bet_count(sid)
        is_exec = sid in exec_ids
        for lt in meta["supported_lottery_types"]:
            row = replay_mod._build_overview_row(
                lt=lt, sid=sid,
                strategy_name=meta["strategy_name"],
                strategy_version=meta["strategy_version"],
                derived_bets=derived_bets,
                lifecycle=meta["lifecycle_status"],
                is_exec=is_exec,
                db=db_index.get((lt, sid)),
                registry_status="registered",
            )
            rows.append(row)

    print("=== CHECK 2: RETIRED zero-row tombstone behavior ===")
    retired_zero = [r for r in rows if r["lifecycle_status"] == "RETIRED" and not r["has_replay_rows"]]
    if not retired_zero:
        print("RESULT: DATA_ABSENT (no current zero-row RETIRED strategy found)")
    else:
        ok = all(r["can_open_detail"] is False and r["missing_reason"] == "retired_no_rows" for r in retired_zero)
        print(f"count={len(retired_zero)} sample_ids={[r['strategy_id'] for r in retired_zero[:5]]}")
        print("RESULT:", "PASS" if ok else "FAIL")

    print("\n=== CHECK 3: OBSERVATION no-data behavior ===")
    obs_zero = [r for r in rows if r["lifecycle_status"] == "OBSERVATION" and not r["has_replay_rows"]]
    if not obs_zero:
        print("RESULT: DATA_ABSENT (no current zero-row OBSERVATION strategy found)")
    else:
        ok = all(r["can_open_detail"] is False and r["missing_reason"] == "observation_no_data" for r in obs_zero)
        print(f"count={len(obs_zero)} sample_ids={[r['strategy_id'] for r in obs_zero[:5]]}")
        print("RESULT:", "PASS" if ok else "FAIL")

    print("\n=== CHECK 1: REJECTED latest-300 display depth ===")
    rejected_with_rows = [r for r in rows if r["lifecycle_status"] == "REJECTED" and r["has_replay_rows"]]
    if not rejected_with_rows:
        print("RESULT: DATA_ABSENT (no REJECTED strategy with replay rows found)")
        return
    # pick the one with the most rows to make the >300 cap meaningful if possible
    rejected_with_rows.sort(key=lambda r: r["total_replay_rows"], reverse=True)
    target = rejected_with_rows[0]
    lt, sid = target["lottery_type"], target["strategy_id"]
    bet_index = derive_bet_count(sid)
    print(f"sample: lottery_type={lt} strategy_id={sid} bet_index={bet_index} total_rows_all_bets={target['total_replay_rows']}")

    clause, limit, policy = replay_mod._display_depth_clause("REJECTED")
    print(f"policy={policy} limit={limit}")

    conn = ro_conn()
    try:
        distinct_draws_total = conn.execute(
            "SELECT COUNT(DISTINCT target_draw) AS n FROM strategy_prediction_replays "
            "WHERE lottery_type=? AND strategy_id=? AND bet_index=?",
            (lt, sid, bet_index),
        ).fetchone()["n"]

        sql = f"""
            SELECT target_draw FROM strategy_prediction_replays
            WHERE lottery_type=? AND strategy_id=? AND bet_index=?
            {clause}
            ORDER BY CAST(target_draw AS INTEGER) DESC
        """
        # clause references (lottery_type, strategy_id, limit) as extra params after the base 3
        params = (lt, sid, bet_index, lt, sid, limit) if clause else (lt, sid, bet_index)
        draws = [row["target_draw"] for row in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()

    distinct_capped = len(set(draws))
    print(f"distinct_draws_total(unfiltered)={distinct_draws_total} distinct_draws_after_depth_clause={distinct_capped}")
    is_sorted_desc = [int(d) for d in draws] == sorted([int(d) for d in draws], reverse=True)
    ok = distinct_capped <= limit and is_sorted_desc and (distinct_capped == min(distinct_draws_total, limit))
    print("RESULT:", "PASS" if ok else "FAIL")


if __name__ == "__main__":
    check_1_and_check_2_and_3()
