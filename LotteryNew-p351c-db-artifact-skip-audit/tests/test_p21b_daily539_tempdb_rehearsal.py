"""
P21B — Daily 539 Temp-DB Rehearsal + Production Apply Tests.
"""

from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest

_REPO_ROOT  = Path(__file__).resolve().parents[1]
_SCRIPT     = _REPO_ROOT / "scripts" / "p21b_daily539_tempdb_rehearsal.py"
_REHEARSAL  = _REPO_ROOT / "outputs" / "replay" / "p21b_daily539_tempdb_rehearsal_20260521.json"
_APPLY_OUT  = _REPO_ROOT / "outputs" / "replay" / "p21b_daily539_production_apply_20260521.json"
_PROD_DB    = _REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"

if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

STRATEGIES         = ["daily539_f4cold", "daily539_markov_cold"]
PROD_ROWS_BEFORE   = 9460
PROD_ROWS_AFTER    = 12460
EXPECTED_READY     = 3000
APPLY_ID           = "P21B_DAILY539_BOTH_1500_PROD_20260520"
TRUTH_LEVEL        = "DAILY539_BACKFILL_VERIFIED"
SOURCE             = "P21_DAILY539_REPLAY_DRY_RUN"


@pytest.fixture(scope="module")
def rehearsal() -> dict:
    assert _REHEARSAL.exists()
    return json.loads(_REHEARSAL.read_text())


@pytest.fixture(scope="module")
def apply_result() -> dict:
    assert _APPLY_OUT.exists()
    return json.loads(_APPLY_OUT.read_text())


@pytest.fixture()
def temp_db(tmp_path):
    """Isolated temp DB with only legacy rows (460)."""
    dest = tmp_path / "db_test.db"
    prod_conn = sqlite3.connect(str(_PROD_DB))
    dest_conn = sqlite3.connect(str(dest))
    try:
        for (tbl_name, sql) in prod_conn.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='table' AND sql IS NOT NULL"
        ).fetchall():
            if not tbl_name.startswith("sqlite_"):
                dest_conn.execute(sql)
        rows = prod_conn.execute(
            "SELECT * FROM strategy_prediction_replays WHERE controlled_apply_id IS NULL"
        ).fetchall()
        if rows:
            dest_conn.executemany(
                f"INSERT INTO strategy_prediction_replays VALUES ({','.join(['?']*len(rows[0]))})",
                rows,
            )
        dest_conn.commit()
    finally:
        prod_conn.close(); dest_conn.close()
    return dest


# ── static tests ──────────────────────────────────────────────────────────────

def test_script_exists():
    assert _SCRIPT.exists()

def test_rehearsal_exists():
    assert _REHEARSAL.exists()

def test_apply_result_exists():
    assert _APPLY_OUT.exists()


# ── rehearsal JSON ────────────────────────────────────────────────────────────

def test_rehearsal_r1_inserted_3000(rehearsal: dict):
    assert rehearsal["r1_apply_inserted_count"] == EXPECTED_READY

def test_rehearsal_r2_inserted_0(rehearsal: dict):
    assert rehearsal["r2_rerun_inserted_count"] == 0

def test_rehearsal_r2_dupes_3000(rehearsal: dict):
    assert rehearsal["r2_rerun_duplicate_count"] == EXPECTED_READY

def test_rehearsal_rollback_3000(rehearsal: dict):
    assert rehearsal["rollback_deleted_count"] == EXPECTED_READY

def test_rehearsal_rollback_rows_9460(rehearsal: dict):
    assert rehearsal["rows_after_rollback"] == PROD_ROWS_BEFORE

def test_rehearsal_pass(rehearsal: dict):
    assert rehearsal["temp_rehearsal_pass"] is True
    assert rehearsal["idempotency_pass"] is True
    assert rehearsal["rollback_pass"] is True


# ── production apply result ───────────────────────────────────────────────────

def test_apply_inserted_3000(apply_result: dict):
    assert apply_result["inserted_count"] == EXPECTED_READY

def test_apply_duplicate_0(apply_result: dict):
    assert apply_result["duplicate_count"] == 0

def test_apply_rows_12460(apply_result: dict):
    assert apply_result["rows_after_apply"] == PROD_ROWS_AFTER

def test_apply_production_true(apply_result: dict):
    assert apply_result["production_apply"] is True


# ── live DB tests ─────────────────────────────────────────────────────────────

def test_production_db_rows_12460():
    conn = sqlite3.connect(str(_PROD_DB))
    try:
        count = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    finally:
        conn.close()
    assert count == PROD_ROWS_AFTER


def test_p21b_rows_in_db():
    conn = sqlite3.connect(str(_PROD_DB))
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=?",
            (APPLY_ID,),
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == EXPECTED_READY


def test_p21b_truth_level():
    conn = sqlite3.connect(str(_PROD_DB))
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=? AND truth_level=?",
            (APPLY_ID, TRUTH_LEVEL),
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == EXPECTED_READY


def test_p21b_has_timestamps():
    conn = sqlite3.connect(str(_PROD_DB))
    try:
        bad = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=? AND (prediction_cutoff_date IS NULL OR prediction_generated_at IS NULL)",
            (APPLY_ID,),
        ).fetchone()[0]
    finally:
        conn.close()
    assert bad == 0


def test_p21b_no_future_cutoff():
    conn = sqlite3.connect(str(_PROD_DB))
    try:
        bad = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=? AND prediction_cutoff_date > target_date",
            (APPLY_ID,),
        ).fetchone()[0]
    finally:
        conn.close()
    assert bad == 0


def test_p21b_all_daily539():
    conn = sqlite3.connect(str(_PROD_DB))
    try:
        bad = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=? AND lottery_type != 'DAILY_539'",
            (APPLY_ID,),
        ).fetchone()[0]
    finally:
        conn.close()
    assert bad == 0


def test_p21b_5_numbers_per_row():
    conn = sqlite3.connect(str(_PROD_DB))
    try:
        rows = conn.execute(
            "SELECT predicted_numbers FROM strategy_prediction_replays WHERE controlled_apply_id=? LIMIT 20",
            (APPLY_ID,),
        ).fetchall()
    finally:
        conn.close()
    for (nums,) in rows:
        assert len(json.loads(nums)) == 5, f"DAILY_539 must have 5 predicted numbers"


def test_p21b_special_always_null():
    conn = sqlite3.connect(str(_PROD_DB))
    try:
        bad = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=? AND predicted_special IS NOT NULL",
            (APPLY_ID,),
        ).fetchone()[0]
    finally:
        conn.close()
    assert bad == 0


def test_p21b_each_strategy_1500():
    conn = sqlite3.connect(str(_PROD_DB))
    try:
        for sid in STRATEGIES:
            count = conn.execute(
                "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=? AND strategy_id=?",
                (APPLY_ID, sid),
            ).fetchone()[0]
            assert count == 1500, f"{sid}: expected 1500, got {count}"
    finally:
        conn.close()


def test_legacy_unchanged():
    conn = sqlite3.connect(str(_PROD_DB))
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id IS NULL"
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == 460


def test_script_rejects_prod_without_flag():
    from scripts.p21b_daily539_tempdb_rehearsal import apply_to_db, _generate_candidates
    candidates = _generate_candidates(_PROD_DB)
    with pytest.raises(RuntimeError, match="SAFETY STOP"):
        apply_to_db(_PROD_DB, candidates, APPLY_ID, expected_rows_before=PROD_ROWS_AFTER)


def test_temp_apply_inserts(temp_db):
    from scripts.p21b_daily539_tempdb_rehearsal import apply_to_db, _generate_candidates, _row_count, _PROD_DB
    # draw_db=_PROD_DB: load draws from prod; db_path=temp_db: check duplicates in temp
    candidates = _generate_candidates(temp_db, draw_db=_PROD_DB)
    assert _row_count(temp_db) == 460
    r = apply_to_db(temp_db, candidates, APPLY_ID, expected_rows_before=460)
    assert r["inserted_count"] == EXPECTED_READY
    assert _row_count(temp_db) == 460 + EXPECTED_READY


def test_temp_rollback(temp_db):
    from scripts.p21b_daily539_tempdb_rehearsal import apply_to_db, rollback_from_db, _generate_candidates, _row_count, _PROD_DB
    candidates = _generate_candidates(temp_db, draw_db=_PROD_DB)
    apply_to_db(temp_db, candidates, APPLY_ID, expected_rows_before=460)
    rb = rollback_from_db(temp_db, APPLY_ID, expected_rows_before=460+EXPECTED_READY)
    assert rb["rollback_deleted_count"] == EXPECTED_READY
    assert _row_count(temp_db) == 460
