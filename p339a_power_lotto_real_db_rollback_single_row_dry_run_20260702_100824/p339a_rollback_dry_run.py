#!/usr/bin/env python3
"""
P339A — POWER_LOTTO single-row persistence DRY-RUN inside a ROLLED-BACK
transaction on the REAL canonical DB.

This is the last dry-run step before any durable canonical write is considered.
It proves the full parent+child insert path works against the *real* canonical
database *inside a transaction* and then ROLLS BACK, leaving the canonical DB
byte-, size- and mtime-invariant.

Flow:
    stat+sha canonical (pre-connection, read-only)  ->  open canonical RW
    ->  read (never change) journal_mode; wal_autocheckpoint=0
    ->  capture pre-state (counts, max ids, historical row hashes)
    ->  BEGIN (explicit)
    ->  INSERT exactly 1 parent (strategy_replay_runs)
    ->  build 1 forward child via the P336A builder
    ->  P335A guard BEFORE the child insert
    ->  INSERT exactly 1 child (strategy_prediction_replays) linked to the parent
    ->  verify IN-TRANSACTION (counts +1/+1, non-null predicted_special,
        JOIN association, historical rows unchanged)
    ->  ROLLBACK (explicit)
    ->  verify AFTER rollback (P339A rows gone, counts back to baseline,
        historical hashes unchanged)
    ->  close  ->  re-stat+sha canonical  ->  prove invariance.

HARD GUARDRAILS (by construction):
  - Refuses to run unless the opened DB path == the exact canonical path.
  - conn.commit is overridden to RAISE — a COMMIT can never happen.
  - All SQL is routed through _guard_sql which rejects COMMIT / END.
  - Exactly ONE parent and ONE child are inserted; inserting more raises.
  - journal_mode is READ, never assigned (assigning would rewrite the DB header
    / checkpoint the WAL == a durable canonical write). WAL mode + a tiny
    rolled-back txn writes nothing to the main DB file.
  - INSERT-only (no UPDATE/DELETE) and ROLLBACK => no historical row mutated and
    no durable row added.
  - NOT a prediction / bet / recommendation. All inputs are synthetic, fixed and
    labeled TEST_DATA_ONLY / NOT_RECOMMENDED (also stamped into the row's real
    ``source`` column and ``dry_run=1``). Prior POWER findings unchanged.

Reuse (no new algorithm): P336A ``build_power_lotto_forward_replay_row`` +
P335A ``second_zone_predict`` / ``assert_power_lotto_predicted_special``.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone

WORKTREE = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew-p335a"
EVIDENCE_ROOT = os.path.dirname(os.path.abspath(__file__))
CANONICAL = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api/data/lottery_v2.db"
SUMMARY_JSON = os.path.join(EVIDENCE_ROOT, "dry_run_output.json")

# Safety: this run targets the REAL canonical DB, but only inside a rolled-back
# transaction. Refuse to run from outside the P339A evidence root.
assert EVIDENCE_ROOT.startswith("/Users/kelvin/Kelvin-WorkSpace/p339a_"), \
    "refusing: not under P339A evidence root"
assert os.path.abspath(CANONICAL) == os.path.realpath(CANONICAL) or True  # resolved below

sys.path.insert(0, WORKTREE)
from lottery_api.models.power_lotto_forward_replay_row import (  # noqa: E402
    build_power_lotto_forward_replay_row,
)
from lottery_api.models.power_lotto_second_zone import (  # noqa: E402
    assert_power_lotto_predicted_special,
)

P339A_SCOPE = "P339A_ROLLBACK_DRYRUN"
P339A_CHILD_STRATEGY_ID = "p339a_rollback_dryrun_powerlotto"
P339A_SOURCE = "P339A_ROLLBACK_DRY_RUN_TEST_DATA_ONLY_NOT_RECOMMENDED"
P339A_NOTES = (
    "P339A real-canonical-DB single-row persistence DRY-RUN inside a ROLLED-BACK "
    "transaction. TEST_DATA_ONLY / NOT_RECOMMENDED. No commit, no durable write, "
    "no backfill, no prediction."
)

_INSERT_COUNTS = {"parent": 0, "child": 0}


class CommitForbidden(RuntimeError):
    pass


class NoCommitConnection(sqlite3.Connection):
    """HARD GUARDRAIL: a COMMIT via the Python API can never happen. The
    sqlite3.Connection.commit attribute is read-only (cannot be monkeypatched),
    so we override it on a subclass used as the connection factory."""

    def commit(self):  # noqa: D102
        raise CommitForbidden("COMMIT is forbidden in the P339A rollback dry-run")


def _guard_sql(sql: str) -> str:
    head = sql.strip().split(None, 1)[0].upper() if sql.strip() else ""
    if head in ("COMMIT", "END"):
        raise CommitForbidden(f"forbidden statement in P339A dry-run: {sql!r}")
    return sql


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def stat_triplet(path: str):
    if not os.path.exists(path):
        return {"exists": False}
    st = os.stat(path)
    return {
        "exists": True,
        "size": st.st_size,
        "mtime_epoch": int(st.st_mtime),
        "mtime": datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
    }


def sidecar_state(db_path: str):
    return {
        "wal": stat_triplet(db_path + "-wal"),
        "shm": stat_triplet(db_path + "-shm"),
        "journal": stat_triplet(db_path + "-journal"),
    }


def hash_rows_upto(conn, table, max_id):
    if max_id is None:
        return "EMPTY_TABLE"
    h = hashlib.sha256()
    for row in conn.execute(f"SELECT * FROM {table} WHERE id <= ? ORDER BY id", (max_id,)):
        h.update(repr(row).encode("utf-8"))
    return h.hexdigest()


def build_synthetic_history(n: int = 60):
    """Deterministic TEST_DATA_ONLY causal history (>= MIN_HISTORY 30). No RNG.
    Identical construction to P338A for reproducibility of predicted_special."""
    return [
        {"draw": str(114000000 + i), "date": f"2026-01-{(i % 28) + 1:02d}",
         "special": ((i * 7 + 3) % 8) + 1}
        for i in range(n)
    ]


def main() -> int:
    canon = os.path.realpath(CANONICAL)
    assert canon == os.path.realpath(CANONICAL)
    out = {
        "label": "TEST_DATA_ONLY / NOT_RECOMMENDED",
        "canonical_db": canon,
        "steps": {},
    }

    # --- Pre-connection canonical fingerprint (read-only) ----------------
    pre_sha = sha256_file(canon)
    pre_stat = stat_triplet(canon)
    pre_sidecar = sidecar_state(canon)
    out["steps"]["0_pre_connection_canonical"] = {
        "sha256": pre_sha, "stat": pre_stat, "sidecar": pre_sidecar,
    }

    # manual txn control (isolation_level=None) + commit-forbidden factory.
    conn = sqlite3.connect(canon, isolation_level=None, factory=NoCommitConnection)
    # HARD GUARDRAIL: the connection must be to the exact canonical path.
    dbs = conn.execute("PRAGMA database_list").fetchall()
    main_file = [r[2] for r in dbs if r[1] == "main"][0]
    assert os.path.realpath(main_file) == canon, \
        f"refusing: connected DB {main_file!r} != canonical {canon!r}"

    def X(sql, params=()):
        return conn.execute(_guard_sql(sql), params)

    def scalar(q):
        return X(q).fetchone()[0]

    try:
        # journal_mode is READ, NEVER assigned.
        journal_mode = X("PRAGMA journal_mode").fetchone()[0]
        X("PRAGMA wal_autocheckpoint=0")           # per-connection; not persisted
        X("PRAGMA foreign_keys=ON")                # per-connection; not persisted

        # --- Real schema confirmation ----------------------------------
        ddl = {t: X("SELECT sql FROM sqlite_master WHERE name=?", (t,)).fetchone()[0]
               for t in ("strategy_replay_runs", "strategy_prediction_replays")}
        child_info = X("PRAGMA table_info(strategy_prediction_replays)").fetchall()
        rri_type = [r[2] for r in child_info if r[1] == "replay_run_id"][0]
        child_cols = {r[1] for r in child_info}
        tables = {r[0] for r in X("SELECT name FROM sqlite_master WHERE type='table'")}
        have_parent = "strategy_replay_runs" in tables
        have_child = "strategy_prediction_replays" in tables
        out["steps"]["1_real_schema"] = {
            "journal_mode": journal_mode,
            "wal_autocheckpoint_set_to": 0,
            "strategy_replay_runs_exists": have_parent,
            "strategy_prediction_replays_exists": have_child,
            "replay_run_id_declared_type": rri_type,
            "fk_enforced_constraint_declared": "FOREIGN KEY" in ddl["strategy_prediction_replays"].upper(),
            "has_source_col": "source" in child_cols,
            "has_dry_run_col": "dry_run" in child_cols,
            "strategy_replay_runs_ddl": ddl["strategy_replay_runs"],
            "strategy_prediction_replays_ddl": ddl["strategy_prediction_replays"],
        }
        assert have_parent and have_child, "canonical tables missing"

        # --- Pre-insert baseline (autocommit; no txn open yet) ----------
        pre_parent_count = scalar("SELECT COUNT(*) FROM strategy_replay_runs")
        pre_child_count = scalar("SELECT COUNT(*) FROM strategy_prediction_replays")
        pre_parent_max = scalar("SELECT MAX(id) FROM strategy_replay_runs")
        pre_child_max = scalar("SELECT MAX(id) FROM strategy_prediction_replays")
        pre_parent_hash = hash_rows_upto(conn, "strategy_replay_runs", pre_parent_max)
        pre_child_hash = hash_rows_upto(conn, "strategy_prediction_replays", pre_child_max)
        pre_p339a_parent = scalar(
            f"SELECT COUNT(*) FROM strategy_replay_runs WHERE strategy_scope='{P339A_SCOPE}'")
        pre_p339a_child = scalar(
            f"SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='{P339A_CHILD_STRATEGY_ID}'")
        out["steps"]["2_pre_state"] = {
            "parent_count": pre_parent_count, "child_count": pre_child_count,
            "parent_max_id": pre_parent_max, "child_max_id": pre_child_max,
            "historical_parent_hash": pre_parent_hash, "historical_child_hash": pre_child_hash,
            "preexisting_p339a_parent_rows": pre_p339a_parent,
            "preexisting_p339a_child_rows": pre_p339a_child,
        }
        assert pre_p339a_parent == 0 and pre_p339a_child == 0, "P339A markers already present!"
        in_txn_before = conn.in_transaction

        now = datetime.now(timezone.utc).isoformat()

        # --- EXPLICIT BEGIN --------------------------------------------
        X("BEGIN")
        began = conn.in_transaction

        # --- Insert exactly ONE parent ---------------------------------
        parent_id = X(
            """INSERT INTO strategy_replay_runs
               (lottery_type, strategy_scope, started_at, finished_at, status,
                generator_version, data_hash, notes)
               VALUES (?,?,?,?,?,?,?,?)""",
            ("POWER_LOTTO", P339A_SCOPE, now, now, P339A_SCOPE, "p339a-dryrun", None, P339A_NOTES),
        ).lastrowid
        _INSERT_COUNTS["parent"] += 1
        assert _INSERT_COUNTS["parent"] == 1, "more than one parent inserted!"

        # --- Build ONE forward child via P336A builder -----------------
        history = build_synthetic_history(60)
        row = build_power_lotto_forward_replay_row(
            strategy_id=P339A_CHILD_STRATEGY_ID,
            strategy_name="P339A Real-DB Rollback Dry-Run (TEST_DATA_ONLY / NOT_RECOMMENDED)",
            strategy_version="p339a-dryrun",
            target_draw_id="114000061",
            target_draw_date="2026-07-04",
            history=history,
            predicted_numbers=[1, 2, 3, 4, 5, 6],  # TEST_DATA_ONLY placeholder input
            dry_run=False,  # guard ENFORCES non-null predicted_special
        )

        # --- P335A guard BEFORE the child insert -----------------------
        assert_power_lotto_predicted_special(row)
        guard_ran = True

        # --- Insert exactly ONE child linked to the parent -------------
        child_id = X(
            """INSERT INTO strategy_prediction_replays
               (lottery_type, target_draw, target_date, strategy_id, strategy_name,
                strategy_version, history_cutoff_draw, replay_status, reject_reason,
                predicted_numbers, predicted_special, actual_numbers, actual_special,
                hit_numbers, hit_count, special_hit, replay_run_id, generated_at,
                source, dry_run)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (row["lottery_type"], row["target_draw"], row["draw_date"], row["strategy_id"],
             row["strategy_name"], row["strategy_version"], row["history_cutoff_draw"],
             row["replay_status"], row["reject_reason"], json.dumps(row["predicted_numbers"]),
             row["predicted_special"], row["actual_numbers"], row["actual_special"],
             row["hit_numbers"], row["hit_count"], row["special_hit"],
             str(parent_id), row["prediction_generated_at"], P339A_SOURCE, 1),
        ).lastrowid
        _INSERT_COUNTS["child"] += 1
        assert _INSERT_COUNTS["child"] == 1, "more than one child inserted!"

        # --- IN-TRANSACTION verification -------------------------------
        fk_violations = X("PRAGMA foreign_key_check").fetchall()
        itx_parent_count = scalar("SELECT COUNT(*) FROM strategy_replay_runs")
        itx_child_count = scalar("SELECT COUNT(*) FROM strategy_prediction_replays")
        itx_parent = X(
            "SELECT id, lottery_type, strategy_scope, status, notes "
            "FROM strategy_replay_runs WHERE strategy_scope=?", (P339A_SCOPE,)).fetchall()
        itx_child = X(
            "SELECT id, lottery_type, target_draw, strategy_id, replay_status, "
            "predicted_special, actual_numbers, hit_count, replay_run_id, source, dry_run, "
            "bet_index, generated_at FROM strategy_prediction_replays WHERE strategy_id=?",
            (P339A_CHILD_STRATEGY_ID,)).fetchall()
        fk_join = X(
            "SELECT c.id, c.replay_run_id, p.id, p.strategy_scope "
            "FROM strategy_prediction_replays c "
            "JOIN strategy_replay_runs p ON CAST(c.replay_run_id AS INTEGER) = p.id "
            "WHERE c.strategy_id=?", (P339A_CHILD_STRATEGY_ID,)).fetchall()
        itx_parent_hash = hash_rows_upto(conn, "strategy_replay_runs", pre_parent_max)
        itx_child_hash = hash_rows_upto(conn, "strategy_prediction_replays", pre_child_max)

        parent = itx_parent[0] if itx_parent else None
        child = itx_child[0] if itx_child else None
        # child idx: 0 id,1 lottery_type,2 target_draw,3 strategy_id,4 replay_status,
        # 5 predicted_special,6 actual_numbers,7 hit_count,8 replay_run_id,9 source,
        # 10 dry_run,11 bet_index,12 generated_at
        assoc_ok = (
            len(fk_join) == 1
            and int(fk_join[0][1]) == parent_id
            and fk_join[0][2] == parent_id
            and child is not None and int(child[8]) == parent_id
        )
        out["steps"]["3_in_transaction"] = {
            "in_transaction_before_begin": in_txn_before,
            "in_transaction_after_begin": began,
            "explicit_begin_executed": True,
            "parent_id": parent_id, "child_id": child_id,
            "parent_row_TEST_DATA_ONLY": parent, "child_row_TEST_DATA_ONLY": child,
            "guard_ran_before_insert": guard_ran,
            "parent_count_delta": itx_parent_count - pre_parent_count,
            "child_count_delta": itx_child_count - pre_child_count,
            "p339a_parent_rows": len(itx_parent),
            "p339a_child_rows": len(itx_child),
            "foreign_key_check_violations": fk_violations,
            "fk_join_matches": len(fk_join), "fk_join": fk_join,
            "child_predicted_special": child[5] if child else None,
            "child_source_marker": child[9] if child else None,
            "child_dry_run_marker": child[10] if child else None,
            "child_actual_numbers": child[6] if child else "n/a",
            "association_valid": assoc_ok,
            "historical_parent_hash_unchanged": pre_parent_hash == itx_parent_hash,
            "historical_child_hash_unchanged": pre_child_hash == itx_child_hash,
        }

        # --- EXPLICIT ROLLBACK -----------------------------------------
        X("ROLLBACK")
        rolled_back = not conn.in_transaction

        # --- AFTER-rollback verification (autocommit) ------------------
        post_parent_count = scalar("SELECT COUNT(*) FROM strategy_replay_runs")
        post_child_count = scalar("SELECT COUNT(*) FROM strategy_prediction_replays")
        post_p339a_parent = scalar(
            f"SELECT COUNT(*) FROM strategy_replay_runs WHERE strategy_scope='{P339A_SCOPE}'")
        post_p339a_child = scalar(
            f"SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='{P339A_CHILD_STRATEGY_ID}'")
        post_parent_hash = hash_rows_upto(conn, "strategy_replay_runs", pre_parent_max)
        post_child_hash = hash_rows_upto(conn, "strategy_prediction_replays", pre_child_max)
        out["steps"]["4_after_rollback"] = {
            "explicit_rollback_executed": True,
            "in_transaction_after_rollback": conn.in_transaction,
            "rolled_back": rolled_back,
            "parent_count": post_parent_count, "child_count": post_child_count,
            "parent_count_back_to_baseline": post_parent_count == pre_parent_count,
            "child_count_back_to_baseline": post_child_count == pre_child_count,
            "p339a_parent_rows_remaining": post_p339a_parent,
            "p339a_child_rows_remaining": post_p339a_child,
            "historical_parent_hash_unchanged": pre_parent_hash == post_parent_hash,
            "historical_child_hash_unchanged": pre_child_hash == post_child_hash,
        }
    finally:
        conn.close()

    # --- Post-close canonical fingerprint (read-only) --------------------
    post_sha = sha256_file(canon)
    post_stat = stat_triplet(canon)
    post_sidecar = sidecar_state(canon)
    out["steps"]["5_post_close_canonical"] = {
        "sha256": post_sha, "stat": post_stat, "sidecar": post_sidecar,
    }
    out["steps"]["6_canonical_invariance"] = {
        "sha256_unchanged": pre_sha == post_sha,
        "size_unchanged": pre_stat.get("size") == post_stat.get("size"),
        "mtime_unchanged": pre_stat.get("mtime_epoch") == post_stat.get("mtime_epoch"),
        "pre_sha256": pre_sha, "post_sha256": post_sha,
        "pre_stat": pre_stat, "post_stat": post_stat,
    }

    s3 = out["steps"]["3_in_transaction"]
    s4 = out["steps"]["4_after_rollback"]
    s6 = out["steps"]["6_canonical_invariance"]
    validations = {
        "tables_exist": have_parent and have_child,
        "explicit_begin_executed": s3["explicit_begin_executed"] and s3["in_transaction_after_begin"],
        "exactly_one_p339a_parent_in_txn": s3["p339a_parent_rows"] == 1,
        "exactly_one_p339a_child_in_txn": s3["p339a_child_rows"] == 1,
        "parent_delta_is_1_in_txn": s3["parent_count_delta"] == 1,
        "child_delta_is_1_in_txn": s3["child_count_delta"] == 1,
        "child_predicted_special_non_null": s3["child_predicted_special"] is not None,
        "child_predicted_special_in_range": isinstance(s3["child_predicted_special"], int)
        and 1 <= s3["child_predicted_special"] <= 8,
        "guard_ran_before_insert": s3["guard_ran_before_insert"],
        "fk_check_no_violations": len(s3["foreign_key_check_violations"]) == 0,
        "parent_child_association_valid": s3["association_valid"],
        "forward_child_actual_numbers_null": s3["child_actual_numbers"] is None,
        "child_marked_test_data_only": s3["child_source_marker"] == P339A_SOURCE
        and s3["child_dry_run_marker"] == 1,
        "historical_unchanged_in_txn": s3["historical_parent_hash_unchanged"]
        and s3["historical_child_hash_unchanged"],
        "explicit_rollback_executed": s4["explicit_rollback_executed"] and s4["rolled_back"],
        "no_p339a_rows_after_rollback": s4["p339a_parent_rows_remaining"] == 0
        and s4["p339a_child_rows_remaining"] == 0,
        "counts_back_to_baseline_after_rollback": s4["parent_count_back_to_baseline"]
        and s4["child_count_back_to_baseline"],
        "historical_unchanged_after_rollback": s4["historical_parent_hash_unchanged"]
        and s4["historical_child_hash_unchanged"],
        "canonical_sha_unchanged": s6["sha256_unchanged"],
        "canonical_size_unchanged": s6["size_unchanged"],
        "canonical_mtime_unchanged": s6["mtime_unchanged"],
        "single_parent_insert_only": _INSERT_COUNTS["parent"] == 1,
        "single_child_insert_only": _INSERT_COUNTS["child"] == 1,
    }
    out["validations"] = validations
    out["all_validations_pass"] = all(validations.values())

    with open(SUMMARY_JSON, "w") as fh:
        json.dump(out, fh, indent=2)
    print(json.dumps(out, indent=2))
    print("\n=== P339A ROLLBACK DRY-RUN:",
          "PASS" if out["all_validations_pass"] else "FAIL", "===")
    return 0 if out["all_validations_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
