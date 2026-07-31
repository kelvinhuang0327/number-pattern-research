#!/usr/bin/env python3
"""P333A read-only field-availability verification against the CURRENT canonical DB.

Strictly read-only: sqlite3 URI mode=ro. No INSERT/UPDATE/DELETE/DDL.
Reports schema + per-lottery row counts + NULL rates for the fields the
prize_aware_scorer requires. No scorer call, no hit/success computation.
"""
import hashlib
import json
import os
import sqlite3
import sys

DB = "lottery_api/data/lottery_v2.db"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    out = {}
    out["db_path"] = os.path.abspath(DB)
    out["db_size_before"] = os.path.getsize(DB)
    out["db_mtime_before"] = os.stat(DB).st_mtime_ns
    out["db_sha256_before"] = sha256(DB)

    uri = f"file:{DB}?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    cur = con.cursor()

    # sqlite data_version is a proxy for write activity
    out["data_version_start"] = cur.execute("PRAGMA data_version").fetchone()[0]

    # schema of the replay table
    cols = cur.execute("PRAGMA table_info(strategy_prediction_replays)").fetchall()
    out["strategy_prediction_replays_columns"] = [
        {"cid": c[0], "name": c[1], "type": c[2], "notnull": c[3], "pk": c[5]}
        for c in cols
    ]

    # distinct lottery types present
    out["distinct_lottery_types"] = [
        r[0] for r in cur.execute(
            "SELECT DISTINCT lottery_type FROM strategy_prediction_replays "
            "ORDER BY lottery_type"
        ).fetchall()
    ]

    # per-lottery field availability
    per = {}
    for lt in out["distinct_lottery_types"]:
        row = cur.execute(
            """
            SELECT
              COUNT(*) AS total,
              SUM(CASE WHEN predicted_numbers IS NOT NULL THEN 1 ELSE 0 END) AS pred_main_nn,
              SUM(CASE WHEN actual_numbers   IS NOT NULL THEN 1 ELSE 0 END) AS act_main_nn,
              SUM(CASE WHEN predicted_special IS NOT NULL THEN 1 ELSE 0 END) AS pred_special_nn,
              SUM(CASE WHEN actual_special    IS NOT NULL THEN 1 ELSE 0 END) AS act_special_nn
            FROM strategy_prediction_replays
            WHERE lottery_type = ?
            """,
            (lt,),
        ).fetchone()
        # distinct replay_status values
        statuses = cur.execute(
            "SELECT replay_status, COUNT(*) FROM strategy_prediction_replays "
            "WHERE lottery_type=? GROUP BY replay_status",
            (lt,),
        ).fetchall()
        total = row[0]
        per[lt] = {
            "total_rows": total,
            "predicted_main_non_null": row[1],
            "actual_main_non_null": row[2],
            "predicted_special_non_null": row[3],
            "actual_special_non_null": row[4],
            "predicted_special_null": total - row[3],
            "predicted_special_non_null_pct": round(100.0 * row[3] / total, 4) if total else None,
            "actual_special_non_null_pct": round(100.0 * row[4] / total, 4) if total else None,
            "replay_status_counts": {s[0]: s[1] for s in statuses},
        }
    out["per_lottery"] = per

    # draws table: actual number/special availability per lottery type
    draws = {}
    try:
        dcols = [c[1] for c in cur.execute("PRAGMA table_info(draws)").fetchall()]
        out["draws_columns"] = dcols
        for lt in cur.execute(
            "SELECT DISTINCT lottery_type FROM draws ORDER BY lottery_type"
        ).fetchall():
            lt = lt[0]
            r = cur.execute(
                "SELECT COUNT(*), "
                "SUM(CASE WHEN special_number IS NOT NULL THEN 1 ELSE 0 END) "
                "FROM draws WHERE lottery_type=?",
                (lt,),
            ).fetchone()
            draws[lt] = {"total": r[0], "special_number_non_null": r[1]}
    except Exception as e:  # noqa
        draws["error"] = repr(e)
    out["draws_special_availability"] = draws

    out["data_version_end"] = cur.execute("PRAGMA data_version").fetchone()[0]
    con.close()

    out["db_size_after"] = os.path.getsize(DB)
    out["db_mtime_after"] = os.stat(DB).st_mtime_ns
    out["db_sha256_after"] = sha256(DB)
    out["db_unchanged"] = (
        out["db_sha256_before"] == out["db_sha256_after"]
        and out["db_size_before"] == out["db_size_after"]
        and out["db_mtime_before"] == out["db_mtime_after"]
    )

    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(main())
