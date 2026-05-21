"""
P19B — Power Lotto Temp-DB Rehearsal Tests.

Verifies that the rehearsal script correctly applies 1500 POWER_LOTTO rows
to a temp DB, is idempotent on rerun, and rolls back cleanly. Also verifies
that the authorized production apply completed successfully.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest

_REPO_ROOT   = Path(__file__).resolve().parents[1]
_SCRIPT      = _REPO_ROOT / "scripts" / "p19b_powerlotto_tempdb_rehearsal.py"
_REHEARSAL   = _REPO_ROOT / "outputs" / "replay" / "p19b_powerlotto_tempdb_rehearsal_20260520.json"
_DECISION    = _REPO_ROOT / "outputs" / "replay" / "p19b_powerlotto_apply_decision_20260520.json"
_APPLY_OUT   = _REPO_ROOT / "outputs" / "replay" / "p19b_powerlotto_production_apply_20260520.json"
_P19_INPUT   = _REPO_ROOT / "outputs" / "replay" / "p19_powerlotto_single_strategy_replay_dry_run_20260520.json"
_PROD_DB     = _REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"

if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

PROD_ROWS_BEFORE   = 4960
PROD_ROWS_AFTER    = 6460  # frozen in P19B apply result JSON
EXPECTED_READY     = 1500
APPLY_ID           = "P19B_POWERLOTTO_FOURIER_1500_PROD_20260520"
TRUTH_LEVEL        = "POWERLOTTO_SINGLE_STRATEGY_BACKFILL_VERIFIED"
SOURCE             = "P19_POWERLOTTO_SINGLE_STRATEGY_REPLAY_DRY_RUN"


@pytest.fixture(scope="module")
def rehearsal() -> dict:
    assert _REHEARSAL.exists()
    return json.loads(_REHEARSAL.read_text())


@pytest.fixture(scope="module")
def decision() -> dict:
    assert _DECISION.exists()
    return json.loads(_DECISION.read_text())


@pytest.fixture(scope="module")
def apply_result() -> dict:
    assert _APPLY_OUT.exists()
    return json.loads(_APPLY_OUT.read_text())


@pytest.fixture()
def temp_db(tmp_path):
    """Isolated temp DB: only legacy rows (controlled_apply_id IS NULL) = 460 rows."""
    dest = tmp_path / "lottery_v2_test.db"
    prod_conn = sqlite3.connect(str(_PROD_DB))
    dest_conn = sqlite3.connect(str(dest))
    try:
        for (tbl_name, sql) in prod_conn.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='table' AND sql IS NOT NULL"
        ).fetchall():
            if tbl_name.startswith("sqlite_"):
                continue
            dest_conn.execute(sql)
        rows = prod_conn.execute(
            "SELECT * FROM strategy_prediction_replays WHERE controlled_apply_id IS NULL"
        ).fetchall()
        if rows:
            placeholders = ",".join(["?"] * len(rows[0]))
            dest_conn.executemany(
                f"INSERT INTO strategy_prediction_replays VALUES ({placeholders})",
                rows,
            )
        dest_conn.commit()
    finally:
        prod_conn.close()
        dest_conn.close()
    return dest


# ── static tests ──────────────────────────────────────────────────────────────

def test_script_exists():
    assert _SCRIPT.exists()


def test_p19_input_exists():
    assert _P19_INPUT.exists()


def test_p19_input_has_1500_ready():
    data = json.loads(_P19_INPUT.read_text())
    assert data["ready_candidates"] == EXPECTED_READY


def test_rehearsal_exists():
    assert _REHEARSAL.exists()


def test_decision_exists():
    assert _DECISION.exists()


def test_apply_result_exists():
    assert _APPLY_OUT.exists()


# ── rehearsal JSON ────────────────────────────────────────────────────────────

def test_rehearsal_temp_apply_1500(rehearsal: dict):
    assert rehearsal["inserted_count"] == EXPECTED_READY


def test_rehearsal_temp_apply_inserted_0(rehearsal: dict):
    assert rehearsal.get("error_count", 0) == 0


def test_rehearsal_rows_4960_to_6460(rehearsal: dict):
    assert rehearsal["rows_after_apply"] == PROD_ROWS_AFTER


def test_rehearsal_rerun_inserted_0(rehearsal: dict):
    assert rehearsal["rerun_inserted_count"] == 0


def test_rehearsal_rerun_duplicate_1500(rehearsal: dict):
    assert rehearsal["rerun_duplicate_count"] == EXPECTED_READY


def test_rehearsal_rollback_1500(rehearsal: dict):
    assert rehearsal["rollback_deleted_count"] == EXPECTED_READY


def test_rehearsal_rollback_rows_4960(rehearsal: dict):
    assert rehearsal["rows_after_rollback"] == PROD_ROWS_BEFORE


def test_rehearsal_classification_ready(rehearsal: dict):
    assert rehearsal["final_classification"] == "P19B_TEMP_DB_REHEARSAL_READY"


def test_rehearsal_fake_success_0(rehearsal: dict):
    assert rehearsal["fake_success_count"] == 0


# ── production apply result ───────────────────────────────────────────────────

def test_apply_inserted_1500(apply_result: dict):
    assert apply_result["inserted_count"] == EXPECTED_READY


def test_apply_duplicate_0(apply_result: dict):
    assert apply_result["duplicate_count"] == 0


def test_apply_error_0(apply_result: dict):
    assert apply_result.get("error_count", 0) == 0


def test_apply_rows_6460(apply_result: dict):
    assert apply_result["rows_after_apply"] == PROD_ROWS_AFTER


def test_apply_production_apply_true(apply_result: dict):
    assert apply_result["production_apply"] is True


# ── live production DB tests ──────────────────────────────────────────────────

def test_production_db_rows_6460():
    conn = sqlite3.connect(str(_PROD_DB))
    try:
        count = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    finally:
        conn.close()
    assert count >= PROD_ROWS_AFTER  # post-P20: live count is higher


def test_p19b_rows_in_db():
    conn = sqlite3.connect(str(_PROD_DB))
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=?",
            (APPLY_ID,),
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == EXPECTED_READY


def test_p19b_rows_truth_level():
    conn = sqlite3.connect(str(_PROD_DB))
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=? AND truth_level=?",
            (APPLY_ID, TRUTH_LEVEL),
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == EXPECTED_READY


def test_p19b_rows_source():
    conn = sqlite3.connect(str(_PROD_DB))
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=? AND source=?",
            (APPLY_ID, SOURCE),
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == EXPECTED_READY


def test_p19b_rows_have_prediction_cutoff_date():
    conn = sqlite3.connect(str(_PROD_DB))
    try:
        null_count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=? AND prediction_cutoff_date IS NULL",
            (APPLY_ID,),
        ).fetchone()[0]
    finally:
        conn.close()
    assert null_count == 0


def test_p19b_rows_have_prediction_generated_at():
    conn = sqlite3.connect(str(_PROD_DB))
    try:
        null_count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=? AND prediction_generated_at IS NULL",
            (APPLY_ID,),
        ).fetchone()[0]
    finally:
        conn.close()
    assert null_count == 0


def test_p19b_rows_no_future_cutoff():
    conn = sqlite3.connect(str(_PROD_DB))
    try:
        bad = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=? AND prediction_cutoff_date > target_date",
            (APPLY_ID,),
        ).fetchone()[0]
    finally:
        conn.close()
    assert bad == 0


def test_p19b_rows_lottery_type():
    conn = sqlite3.connect(str(_PROD_DB))
    try:
        bad = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=? AND lottery_type != 'POWER_LOTTO'",
            (APPLY_ID,),
        ).fetchone()[0]
    finally:
        conn.close()
    assert bad == 0


def test_p19b_rows_no_fabricated():
    conn = sqlite3.connect(str(_PROD_DB))
    try:
        bad = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=? AND predicted_numbers IS NULL",
            (APPLY_ID,),
        ).fetchone()[0]
    finally:
        conn.close()
    assert bad == 0


def test_legacy_rows_unchanged():
    conn = sqlite3.connect(str(_PROD_DB))
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id IS NULL"
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == 460  # original legacy rows always 460


def test_no_biglotto_rows_applied_in_p19b():
    conn = sqlite3.connect(str(_PROD_DB))
    try:
        bad = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=? AND lottery_type='BIG_LOTTO'",
            (APPLY_ID,),
        ).fetchone()[0]
    finally:
        conn.close()
    assert bad == 0


# ── live rehearsal tests ──────────────────────────────────────────────────────

def test_script_rejects_production_db_without_flag():
    from scripts.p19b_powerlotto_tempdb_rehearsal import apply_rehearsal, _generate_candidates
    candidates = _generate_candidates(_PROD_DB)
    with pytest.raises(RuntimeError, match="SAFETY STOP"):
        apply_rehearsal(_PROD_DB, candidates, APPLY_ID, expected_rows_before=PROD_ROWS_AFTER)


def test_temp_apply_inserts_460_base(temp_db):
    from scripts.p19b_powerlotto_tempdb_rehearsal import apply_rehearsal, rollback_rehearsal, _generate_candidates, _row_count
    candidates = _generate_candidates(_PROD_DB)
    # Temp DB starts with 460 rows (legacy only)
    assert _row_count(temp_db) == 460
    result = apply_rehearsal(temp_db, candidates, APPLY_ID, expected_rows_before=460)
    assert result["inserted_count"] == EXPECTED_READY
    assert _row_count(temp_db) == 460 + EXPECTED_READY


def test_temp_rerun_inserts_0(temp_db):
    from scripts.p19b_powerlotto_tempdb_rehearsal import apply_rehearsal, _generate_candidates, _row_count
    candidates = _generate_candidates(_PROD_DB)
    apply_rehearsal(temp_db, candidates, APPLY_ID, expected_rows_before=460)
    r2 = apply_rehearsal(temp_db, candidates, APPLY_ID, expected_rows_before=460 + EXPECTED_READY)
    assert r2["inserted_count"] == 0
    assert r2["duplicate_count"] == EXPECTED_READY


def test_temp_rollback_restores(temp_db):
    from scripts.p19b_powerlotto_tempdb_rehearsal import apply_rehearsal, rollback_rehearsal, _generate_candidates, _row_count
    candidates = _generate_candidates(_PROD_DB)
    apply_rehearsal(temp_db, candidates, APPLY_ID, expected_rows_before=460)
    rb = rollback_rehearsal(temp_db, APPLY_ID, expected_rows_before=460 + EXPECTED_READY)
    assert rb["rollback_deleted_count"] == EXPECTED_READY
    assert _row_count(temp_db) == 460


def test_inserted_rows_have_controlled_apply_id(temp_db):
    from scripts.p19b_powerlotto_tempdb_rehearsal import apply_rehearsal, _generate_candidates
    candidates = _generate_candidates(_PROD_DB)
    apply_rehearsal(temp_db, candidates, APPLY_ID, expected_rows_before=460)
    conn = sqlite3.connect(str(temp_db))
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=?",
            (APPLY_ID,),
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == EXPECTED_READY


def test_inserted_rows_have_truth_level(temp_db):
    from scripts.p19b_powerlotto_tempdb_rehearsal import apply_rehearsal, _generate_candidates, TRUTH_LEVEL
    candidates = _generate_candidates(_PROD_DB)
    apply_rehearsal(temp_db, candidates, APPLY_ID, expected_rows_before=460)
    conn = sqlite3.connect(str(temp_db))
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=? AND truth_level=?",
            (APPLY_ID, TRUTH_LEVEL),
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == EXPECTED_READY


def test_inserted_rows_have_source(temp_db):
    from scripts.p19b_powerlotto_tempdb_rehearsal import apply_rehearsal, _generate_candidates, SOURCE
    candidates = _generate_candidates(_PROD_DB)
    apply_rehearsal(temp_db, candidates, APPLY_ID, expected_rows_before=460)
    conn = sqlite3.connect(str(temp_db))
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=? AND source=?",
            (APPLY_ID, SOURCE),
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == EXPECTED_READY


def test_inserted_rows_have_prediction_cutoff_date(temp_db):
    from scripts.p19b_powerlotto_tempdb_rehearsal import apply_rehearsal, _generate_candidates
    candidates = _generate_candidates(_PROD_DB)
    apply_rehearsal(temp_db, candidates, APPLY_ID, expected_rows_before=460)
    conn = sqlite3.connect(str(temp_db))
    try:
        bad = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=? AND prediction_cutoff_date IS NULL",
            (APPLY_ID,),
        ).fetchone()[0]
    finally:
        conn.close()
    assert bad == 0


def test_no_retired_rows(temp_db):
    from scripts.p19b_powerlotto_tempdb_rehearsal import apply_rehearsal, _generate_candidates
    candidates = _generate_candidates(_PROD_DB)
    apply_rehearsal(temp_db, candidates, APPLY_ID, expected_rows_before=460)
    conn = sqlite3.connect(str(temp_db))
    try:
        bad = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=? AND strategy_id NOT IN ('fourier_rhythm_3bet')",
            (APPLY_ID,),
        ).fetchone()[0]
    finally:
        conn.close()
    assert bad == 0
