#!/usr/bin/env python3
"""PR700_RUNTIME_SUPPORT_AND_SIDECAR_CONTRACT_REVIEW_R1

Deterministic, task-owned reproduction of PR #700's ColdWalReadOnlyError
guard (fixed head 9c3cf90dccc178236640d6cbc12d250df7db9ee7) under whichever
interpreter this script is invoked with.

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
from pathlib import Path

EVROOT = Path(__file__).resolve().parent
SOURCE = EVROOT / "source"
FIXTURES = EVROOT / "fixtures"

sys.path.insert(0, str(SOURCE / "lottery_api"))

from database import DatabaseManager, ColdWalReadOnlyError  # noqa: E402

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
    return {"db": file_state(db_path), "sidecars": sidecar_states(db_path)}


def build_fixture(db_path: Path, journal_mode: str, seed: int = 1234, num_rows: int = 20):
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
    return conn


def try_direct_read(db_path: Path):
    result = {"connection_uri": f"file:{db_path}?mode=ro"}
    try:
        dm = DatabaseManager(db_path=str(db_path), read_only=True)
        cur = dm._get_connection().execute("SELECT COUNT(*) FROM draws")
        count = cur.fetchone()[0]
        result["outcome"] = "SUCCESS"
        result["row_count"] = count
        result["exception_class"] = None
        result["exception_message"] = None
        result["is_cold_wal_read_only_error"] = False
    except Exception as exc:  # noqa: BLE001 - intentionally broad
        result["outcome"] = "FAILURE"
        result["row_count"] = None
        result["exception_class"] = type(exc).__name__
        result["exception_message"] = str(exc)
        result["is_cold_wal_read_only_error"] = isinstance(exc, ColdWalReadOnlyError)
    return result


def measure_case(case_id, db_path: Path, journal_mode: str, writer_state: str, before_snap):
    direct = try_direct_read(db_path)
    after_snap = snapshot(db_path)
    wal_created = (not before_snap["sidecars"]["-wal"]["exists"]) and after_snap["sidecars"]["-wal"]["exists"]
    shm_created = (not before_snap["sidecars"]["-shm"]["exists"]) and after_snap["sidecars"]["-shm"]["exists"]
    entry = {
        "case_id": case_id,
        "fixture_journal_mode": journal_mode,
        "writer_connection_state": writer_state,
        "db_path": str(db_path),
        "state_before": before_snap,
        "state_after": after_snap,
        "sqlite_created_wal_sidecar": wal_created,
        "sqlite_created_shm_sidecar": shm_created,
        "direct_database_manager_read": direct,
        "db_content_unchanged": before_snap["db"]["sha256"] == after_snap["db"]["sha256"],
    }
    return entry


def main():
    FIXTURES.mkdir(parents=True, exist_ok=True)
    matrix = {}

    # Case A: rollback-journal cold control (must always succeed)
    case_a = FIXTURES / f"case_a_{os.getpid()}.db"
    conn_a = build_fixture(case_a, "DELETE")
    conn_a.close()
    matrix["A_ROLLBACK_COLD_CONTROL"] = measure_case(
        "A_ROLLBACK_COLD_CONTROL", case_a, "DELETE", "closed", snapshot(case_a)
    )

    # Case C: WAL, checkpointed+closed, DB-only file copied to a fresh path (no sidecars)
    case_c_src = FIXTURES / f"case_c_src_{os.getpid()}.db"
    conn_c = build_fixture(case_c_src, "WAL")
    conn_c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn_c.close()
    case_c_final = FIXTURES / f"case_c_cold_{os.getpid()}.db"
    shutil.copyfile(case_c_src, case_c_final)
    matrix["C_WAL_COLD_DB_ONLY"] = measure_case(
        "C_WAL_COLD_DB_ONLY",
        case_c_final,
        "WAL (persisted in file header; no sidecars present)",
        "closed (checkpointed via TRUNCATE, connection closed, DB-only file copied to a fresh path)",
        snapshot(case_c_final),
    )

    a_ok = matrix["A_ROLLBACK_COLD_CONTROL"]["direct_database_manager_read"]["outcome"] == "SUCCESS"
    c_raised_guard = matrix["C_WAL_COLD_DB_ONLY"]["direct_database_manager_read"]["is_cold_wal_read_only_error"]
    c_outcome = matrix["C_WAL_COLD_DB_ONLY"]["direct_database_manager_read"]["outcome"]
    c_sidecar_created = (
        matrix["C_WAL_COLD_DB_ONLY"]["sqlite_created_wal_sidecar"]
        or matrix["C_WAL_COLD_DB_ONLY"]["sqlite_created_shm_sidecar"]
    )

    if a_ok and c_outcome == "FAILURE" and c_raised_guard and not c_sidecar_created:
        classification = "PR700_GUARD_FIRES_NO_SIDECAR_CREATED"
    elif a_ok and c_outcome == "SUCCESS":
        classification = "PR700_GUARD_DID_NOT_FIRE_READ_SUCCEEDED"
    elif a_ok and c_outcome == "FAILURE" and not c_raised_guard:
        classification = "PR700_GUARD_DID_NOT_FIRE_OTHER_ERROR_RAISED"
    elif a_ok and c_sidecar_created:
        classification = "SIDECAR_CREATED_UNDER_READONLY"
    else:
        classification = "GENERAL_READ_ONLY_FAILURE"

    output = {
        "task_id": "PR700_RUNTIME_SUPPORT_AND_SIDECAR_CONTRACT_REVIEW_R1",
        "executable": sys.executable,
        "python_version": sys.version,
        "sqlite3_module_version": getattr(sqlite3, "version", None),
        "sqlite_library_version": sqlite3.sqlite_version,
        "case_results": matrix,
        "a_rollback_control_succeeded": a_ok,
        "c_guard_fired": c_raised_guard,
        "c_sidecar_created": c_sidecar_created,
        "classification": classification,
    }
    out_name = f"runtime_matrix_{Path(sys.executable).name}_{os.getpid()}.json"
    (EVROOT / out_name).write_text(json.dumps(output, indent=2, default=str))
    print(json.dumps(output, indent=2, default=str))
    return output


if __name__ == "__main__":
    main()
