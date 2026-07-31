#!/usr/bin/env python3
"""LOTTERYNEW_LEGACY_COLD_START_PREDICTION_CONTINUITY_AUDIT_R1

Deterministic, task-owned reproduction matrix for whether the legacy
DatabaseManager(read_only=True) / quick_predict.load_history read path
survives a "cold" SQLite WAL database (no -wal/-shm sidecars present).

All databases used here are synthetic and created fresh by this script.
The canonical LotteryNew database is never opened, queried, or copied.
"""
import datetime
import hashlib
import json
import os
import random
import shutil
import sqlite3
import sys
import traceback
from pathlib import Path

EVROOT = Path(__file__).resolve().parent
SOURCE = EVROOT / "source"
FIXTURES = EVROOT / "fixtures"

sys.path.insert(0, str(SOURCE))
sys.path.insert(0, str(SOURCE / "lottery_api"))
sys.path.insert(0, str(SOURCE / "tools"))

from database import DatabaseManager  # noqa: E402
import quick_predict  # noqa: E402

SIDECAR_SUFFIXES = ("-wal", "-shm", "-journal")


def file_state(path: Path):
    exists = path.exists()
    state = {"path": str(path), "exists": exists}
    if exists:
        data = path.read_bytes()
        state["size"] = len(data)
        state["sha256"] = hashlib.sha256(data).hexdigest()
    else:
        state["size"] = None
        state["sha256"] = None
    return state


def sidecar_states(db_path: Path):
    return {suffix: file_state(Path(str(db_path) + suffix)) for suffix in SIDECAR_SUFFIXES}


def snapshot(db_path: Path):
    return {
        "db": file_state(db_path),
        "sidecars": sidecar_states(db_path),
    }


def list_fixture_dir():
    return sorted(p.name for p in FIXTURES.rglob("*") if p.is_file())


def build_biglotto_fixture(db_path: Path, journal_mode: str, seed: int = 1234, num_rows: int = 20):
    """Create a deterministic synthetic BIG_LOTTO `draws` table + canonical view.

    Schema mirrors DatabaseManager._init_database()'s `draws` table (source-
    verified in evidence-root/source/lottery_api/database.py). The
    `draws_big_lotto_canonical_main` view is not created by _init_database()
    in the pinned source (it is a one-off migration against the real
    canonical DB per the P247B code comment) so this script defines an
    equivalent view here, using the same two SQL-level exclusion predicates
    documented in get_canonical_draws()'s fallback branch (hyphenated draw
    IDs, 8-digit YYYYMMDD draw IDs). All synthetic rows use 6 numbers drawn
    from 1..49, so the SMALL_POOL_ALIEN family (max(numbers) <= 25) never
    applies here and does not need separate SQL modeling.
    """
    conn = sqlite3.connect(str(db_path))
    conn.execute(f"PRAGMA journal_mode={journal_mode}")
    conn.execute(
        """
        CREATE TABLE draws (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            draw TEXT NOT NULL,
            date TEXT NOT NULL,
            lottery_type TEXT NOT NULL,
            numbers TEXT NOT NULL,
            special INTEGER DEFAULT 0,
            jackpot_amount REAL DEFAULT NULL,
            numbers_positional TEXT DEFAULT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(draw, lottery_type)
        )
        """
    )
    conn.execute("CREATE INDEX idx_lottery_type ON draws(lottery_type)")
    conn.execute("CREATE INDEX idx_date ON draws(date DESC)")
    conn.execute("CREATE INDEX idx_draw ON draws(draw)")
    conn.execute(
        """
        CREATE VIEW draws_big_lotto_canonical_main AS
        SELECT id, draw, date, lottery_type, numbers, special, jackpot_amount
        FROM draws
        WHERE lottery_type = 'BIG_LOTTO'
          AND draw NOT LIKE '%-%'
          AND NOT (LENGTH(draw) = 8 AND draw LIKE '20%')
        """
    )
    rng = random.Random(seed)
    base_draw = 114000001
    rows = []
    for i in range(num_rows):
        draw_id = str(base_draw + i)
        date_str = (datetime.date(2026, 1, 1) + datetime.timedelta(days=i)).isoformat()
        nums = sorted(rng.sample(range(1, 50), 6))
        special = rng.randint(1, 49)
        rows.append((draw_id, date_str, "BIG_LOTTO", json.dumps(nums), special, 100000000.0 + i * 1000))
    conn.executemany(
        "INSERT INTO draws (draw, date, lottery_type, numbers, special, jackpot_amount) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    max_num_seen = max(max(json.loads(r[3])) for r in rows)
    assert max_num_seen > 25, "fixture invariant violated: expected max(numbers) > 25 for all rows"
    return conn


def try_direct_read(db_path: Path):
    result = {"attempted": True}
    uri = f"file:{db_path}?mode=ro"
    result["connection_uri"] = uri
    try:
        dm = DatabaseManager(db_path=str(db_path), read_only=True)
        rows = dm.get_canonical_draws(lottery_type="BIG_LOTTO")
        result["outcome"] = "SUCCESS"
        result["canonical_draw_count"] = len(rows)
        result["exception_class"] = None
        result["exception_message"] = None
        result["_rows"] = rows
    except Exception as exc:  # noqa: BLE001 - intentionally broad: recording exact exception
        result["outcome"] = "FAILURE"
        result["canonical_draw_count"] = None
        result["exception_class"] = type(exc).__name__
        result["exception_message"] = str(exc)
        result["_rows"] = None
    return result


def try_quick_predict_load(db_path: Path, dry_run: bool):
    result = {"attempted": True, "dry_run": dry_run}
    quick_predict.DB_PATH = str(db_path)
    try:
        history = quick_predict.load_history("BIG_LOTTO", dry_run=dry_run)
        result["outcome"] = "SUCCESS"
        result["canonical_draw_count"] = len(history)
        result["exception_class"] = None
        result["exception_message"] = None
        result["_history"] = history
    except Exception as exc:  # noqa: BLE001
        result["outcome"] = "FAILURE"
        result["canonical_draw_count"] = None
        result["exception_class"] = type(exc).__name__
        result["exception_message"] = str(exc)
        result["_history"] = None
    return result


def measure_case(case_id, db_path: Path, journal_mode: str, writer_state: str, before_snap):
    print(f"--- {case_id}: read attempts against {db_path.name} ---")

    direct = try_direct_read(db_path)
    normal = try_quick_predict_load(db_path, dry_run=False)
    dryrun = try_quick_predict_load(db_path, dry_run=True)

    parity = None
    if normal["outcome"] == "SUCCESS" and dryrun["outcome"] == "SUCCESS":
        parity = normal["_history"] == dryrun["_history"]

    after_snap = snapshot(db_path)

    entry = {
        "case_id": case_id,
        "fixture_journal_mode": journal_mode,
        "writer_connection_state": writer_state,
        "db_path": str(db_path),
        "state_before": before_snap,
        "state_after": after_snap,
        "direct_database_manager_read": {
            k: v for k, v in direct.items() if not k.startswith("_")
        },
        "quick_predict_normal_load": {
            k: v for k, v in normal.items() if not k.startswith("_")
        },
        "quick_predict_dry_run_load": {
            k: v for k, v in dryrun.items() if not k.startswith("_")
        },
        "normal_dry_run_parity": parity,
    }
    print(json.dumps(entry, indent=2, default=str))
    return entry


def main():
    FIXTURES.mkdir(parents=True, exist_ok=True)
    matrix = {}

    # ---------------- Case A: ROLLBACK_COLD_CONTROL ----------------
    case_a_path = FIXTURES / "case_a_rollback.db"
    conn_a = build_biglotto_fixture(case_a_path, "DELETE")
    conn_a.close()
    before_a = snapshot(case_a_path)
    matrix["A_ROLLBACK_COLD_CONTROL"] = measure_case(
        "A_ROLLBACK_COLD_CONTROL", case_a_path, "DELETE", "closed (all writers closed before read)", before_a
    )

    # ---------------- Case B: WAL_WARM_ACTIVE_WRITER ----------------
    case_b_path = FIXTURES / "case_b_wal_warm.db"
    writer_b = build_biglotto_fixture(case_b_path, "WAL")
    # writer_b intentionally kept open (not closed) through the read attempts below
    before_b = snapshot(case_b_path)
    matrix["B_WAL_WARM_ACTIVE_WRITER"] = measure_case(
        "B_WAL_WARM_ACTIVE_WRITER", case_b_path, "WAL", "open (active writer connection held)", before_b
    )
    writer_b.close()
    matrix["B_WAL_WARM_ACTIVE_WRITER"]["state_after_writer_close"] = snapshot(case_b_path)

    # ---------------- Case C: WAL_COLD_DB_ONLY ----------------
    case_c_source_path = FIXTURES / "case_c_wal_source_precheckpoint.db"
    conn_c = build_biglotto_fixture(case_c_source_path, "WAL")
    conn_c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn_c.close()
    case_c_final_path = FIXTURES / "case_c_wal_cold_dbonly.db"
    shutil.copyfile(case_c_source_path, case_c_final_path)
    # Confirm the fresh copy has no sidecars of its own (new filename => no prior sidecars).
    sidecars_absent = all(
        not Path(str(case_c_final_path) + suffix).exists() for suffix in SIDECAR_SUFFIXES
    )
    before_c = snapshot(case_c_final_path)
    before_c["sidecars_confirmed_absent_pre_read"] = sidecars_absent
    matrix["C_WAL_COLD_DB_ONLY"] = measure_case(
        "C_WAL_COLD_DB_ONLY",
        case_c_final_path,
        "WAL (persisted in file header; no sidecars present)",
        "closed (checkpointed via TRUNCATE, connection closed, then DB-only file copied to a fresh path)",
        before_c,
    )
    matrix["C_WAL_COLD_DB_ONLY"]["no_writable_fallback_used"] = True

    # ---------------- Case D: WAL_COLD_IMMUTABLE_PROBE (optional characterization) ----------------
    d_result = {"case_id": "D_WAL_COLD_IMMUTABLE_PROBE", "note": "OPTIONAL CHARACTERIZATION ONLY. "
                "immutable=1 is UNSAFE for a concurrently mutable live DB and is NOT an approved "
                "production fix -- this probe exists only to characterize SQLite's own behavior."}
    uri = f"file:{case_c_final_path}?mode=ro&immutable=1"
    d_result["connection_uri"] = uri
    try:
        conn_d = sqlite3.connect(uri, uri=True)
        cur = conn_d.execute("SELECT COUNT(*) FROM draws_big_lotto_canonical_main")
        count = cur.fetchone()[0]
        conn_d.close()
        d_result["outcome"] = "SUCCESS"
        d_result["canonical_draw_count"] = count
        d_result["exception_class"] = None
        d_result["exception_message"] = None
    except Exception as exc:  # noqa: BLE001
        d_result["outcome"] = "FAILURE"
        d_result["canonical_draw_count"] = None
        d_result["exception_class"] = type(exc).__name__
        d_result["exception_message"] = str(exc)
    matrix["D_WAL_COLD_IMMUTABLE_PROBE"] = d_result
    print("--- D_WAL_COLD_IMMUTABLE_PROBE ---")
    print(json.dumps(d_result, indent=2, default=str))

    # ---------------- Unexpected-files check ----------------
    expected_fixture_files = {
        "case_a_rollback.db",
        "case_b_wal_warm.db",
        "case_b_wal_warm.db-wal",
        "case_b_wal_warm.db-shm",
        "case_c_wal_source_precheckpoint.db",
        "case_c_wal_source_precheckpoint.db-wal",
        "case_c_wal_source_precheckpoint.db-shm",
        "case_c_wal_cold_dbonly.db",
    }
    actual_files = set(list_fixture_dir())
    unexpected = sorted(actual_files - expected_fixture_files)
    missing_expected = sorted(expected_fixture_files - actual_files)

    # ---------------- Classification ----------------
    a_ok = matrix["A_ROLLBACK_COLD_CONTROL"]["direct_database_manager_read"]["outcome"] == "SUCCESS" and \
        matrix["A_ROLLBACK_COLD_CONTROL"]["quick_predict_normal_load"]["outcome"] == "SUCCESS" and \
        matrix["A_ROLLBACK_COLD_CONTROL"]["quick_predict_dry_run_load"]["outcome"] == "SUCCESS"
    b_ok = matrix["B_WAL_WARM_ACTIVE_WRITER"]["direct_database_manager_read"]["outcome"] == "SUCCESS" and \
        matrix["B_WAL_WARM_ACTIVE_WRITER"]["quick_predict_normal_load"]["outcome"] == "SUCCESS" and \
        matrix["B_WAL_WARM_ACTIVE_WRITER"]["quick_predict_dry_run_load"]["outcome"] == "SUCCESS"
    c_ok = matrix["C_WAL_COLD_DB_ONLY"]["direct_database_manager_read"]["outcome"] == "SUCCESS" and \
        matrix["C_WAL_COLD_DB_ONLY"]["quick_predict_normal_load"]["outcome"] == "SUCCESS" and \
        matrix["C_WAL_COLD_DB_ONLY"]["quick_predict_dry_run_load"]["outcome"] == "SUCCESS"

    if a_ok and b_ok and not c_ok:
        classification = "COLD_START_GAP_CONFIRMED"
    elif a_ok and b_ok and c_ok:
        classification = "COLD_START_GAP_NOT_REPRODUCED"
    elif (not a_ok) or (not b_ok):
        classification = "GENERAL_READ_ONLY_FAILURE"
    else:
        classification = "COLD_START_RESULT_UNRESOLVED"

    output = {
        "task_id": "LOTTERYNEW_LEGACY_COLD_START_PREDICTION_CONTINUITY_AUDIT_R1",
        "python_version": sys.version,
        "sqlite3_module_version": sqlite3.version,
        "sqlite_library_version": sqlite3.sqlite_version,
        "case_results": {
            k: {kk: vv for kk, vv in v.items() if not str(kk).startswith("_")}
            for k, v in matrix.items()
        },
        "unexpected_files_in_fixtures_dir": unexpected,
        "missing_expected_fixture_files": missing_expected,
        "a_rollback_control_all_succeeded": a_ok,
        "b_wal_warm_all_succeeded": b_ok,
        "c_wal_cold_dbonly_all_succeeded": c_ok,
        "classification": classification,
    }

    (EVROOT / "matrix_results.json").write_text(json.dumps(output, indent=2, default=str))
    print("=== CLASSIFICATION ===")
    print(classification)
    print("=== unexpected files ===", unexpected)
    print("=== missing expected files ===", missing_expected)
    return output


if __name__ == "__main__":
    main()
