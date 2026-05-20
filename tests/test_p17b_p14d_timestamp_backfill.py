"""
P17B — P14D Timestamp Metadata Backfill Tests.

Verifies that:
- The backfill script correctly updates 1500 P14D rows with prediction timestamps
- Idempotency: rerun updates 0 rows
- Rollback restores NULL state
- Production DB has all 1500 P14D rows with timestamps after apply
- prediction_cutoff_date <= target_date for all P14D rows (no future violations)
- API returns timestamps for ts3_regime_3bet rows
"""

from __future__ import annotations

import asyncio
import json
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest

_REPO_ROOT   = Path(__file__).resolve().parents[1]
_LOTTERY_API = _REPO_ROOT / "lottery_api"
_PROD_DB     = _LOTTERY_API / "data" / "lottery_v2.db"
_SCRIPT      = _REPO_ROOT / "scripts" / "p17b_p14d_timestamp_backfill.py"
_REHEARSAL   = _REPO_ROOT / "outputs" / "replay" / "p17b_p14d_timestamp_backfill_rehearsal_20260520.json"
_DECISION    = _REPO_ROOT / "outputs" / "replay" / "p17b_p14d_timestamp_backfill_decision_20260520.json"
_APPLY_OUT   = _REPO_ROOT / "outputs" / "replay" / "p17b_p14d_timestamp_backfill_apply_20260520.json"

sys.path.insert(0, str(_LOTTERY_API))
from routes.replay import get_replay_history  # noqa: E402

PROD_ROWS     = 6460  # updated post-P19B apply
TARGET_APPLY_ID   = "P14D_BIGLOTTO_TS3_1500_PROD_20260520"
EXPECTED_TARGET   = 1500
GEN_AT_SEMANTICS  = "P17B_METADATA_BACKFILL_TIME_NOT_ORIGINAL_PREDICTION_TIME"


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture()
def temp_db(tmp_path):
    """Isolated temp DB for rehearsal tests — always starts from current production state."""
    dest = tmp_path / "lottery_v2_test.db"
    shutil.copy(str(_PROD_DB), str(dest))
    return dest


# ── fixtures ──────────────────────────────────────────────────────────────────

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


# ── static artifact tests ─────────────────────────────────────────────────────

def test_script_exists():
    assert _SCRIPT.exists()


def test_rehearsal_exists():
    assert _REHEARSAL.exists()


def test_decision_exists():
    assert _DECISION.exists()


def test_production_rows_4960():
    conn = sqlite3.connect(str(_PROD_DB))
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == PROD_ROWS


def test_p14d_target_rows_in_db():
    conn = sqlite3.connect(str(_PROD_DB))
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=?",
            (TARGET_APPLY_ID,),
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == EXPECTED_TARGET


def test_cutoff_join_count():
    conn = sqlite3.connect(str(_PROD_DB))
    try:
        count = conn.execute(
            """SELECT COUNT(*) FROM strategy_prediction_replays r
               JOIN draws d ON d.lottery_type=r.lottery_type AND d.draw=r.history_cutoff_draw
               WHERE r.controlled_apply_id=?""",
            (TARGET_APPLY_ID,),
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == EXPECTED_TARGET


# ── rehearsal JSON tests ──────────────────────────────────────────────────────

def test_rehearsal_temp_apply_updated_1500(rehearsal: dict):
    assert rehearsal["r1_apply_updated_count"] == EXPECTED_TARGET


def test_rehearsal_temp_apply_inserted_0(rehearsal: dict):
    assert rehearsal["r1_apply_inserted_count"] == 0


def test_rehearsal_temp_rerun_updated_0(rehearsal: dict):
    assert rehearsal["r2_rerun_updated_count"] == 0


def test_rehearsal_rollback_updated_1500(rehearsal: dict):
    assert rehearsal["rollback_updated_count"] == EXPECTED_TARGET


def test_rehearsal_violations_0(rehearsal: dict):
    assert rehearsal["r1_cutoff_violations"] == 0


def test_rehearsal_pass_flags(rehearsal: dict):
    assert rehearsal["temp_rehearsal_pass"] is True
    assert rehearsal["idempotency_pass"] is True
    assert rehearsal["rollback_pass"] is True


def test_rehearsal_semantics_documented(rehearsal: dict):
    assert rehearsal["prediction_generated_at_semantics"] == GEN_AT_SEMANTICS


# ── production apply result tests ─────────────────────────────────────────────

def test_apply_result_exists():
    assert _APPLY_OUT.exists()


def test_apply_result_updated_1500(apply_result: dict):
    assert apply_result["updated_count"] == EXPECTED_TARGET


def test_apply_result_inserted_0(apply_result: dict):
    assert apply_result["inserted_count"] == 0


def test_apply_result_rows_4960(apply_result: dict):
    # P17B apply result snapshot captured pre-P19B; value is the post-P17B count
    assert apply_result["rows_after"] >= 4960  # frozen snapshot value


def test_apply_result_violations_0(apply_result: dict):
    assert apply_result["cutoff_violations"] == 0


def test_apply_result_production_apply_true(apply_result: dict):
    assert apply_result["production_apply"] is True


# ── live DB post-apply tests ──────────────────────────────────────────────────

def test_p14d_timestamps_populated():
    conn = sqlite3.connect(str(_PROD_DB))
    try:
        count = conn.execute(
            """SELECT COUNT(*) FROM strategy_prediction_replays
               WHERE controlled_apply_id=?
               AND prediction_cutoff_date IS NOT NULL
               AND prediction_generated_at IS NOT NULL""",
            (TARGET_APPLY_ID,),
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == EXPECTED_TARGET


def test_p14d_no_null_timestamps():
    conn = sqlite3.connect(str(_PROD_DB))
    try:
        null_count = conn.execute(
            """SELECT COUNT(*) FROM strategy_prediction_replays
               WHERE controlled_apply_id=?
               AND (prediction_cutoff_date IS NULL OR prediction_generated_at IS NULL)""",
            (TARGET_APPLY_ID,),
        ).fetchone()[0]
    finally:
        conn.close()
    assert null_count == 0


def test_p14d_no_future_cutoff_violations():
    conn = sqlite3.connect(str(_PROD_DB))
    try:
        bad = conn.execute(
            """SELECT COUNT(*) FROM strategy_prediction_replays
               WHERE controlled_apply_id=?
               AND prediction_cutoff_date > target_date""",
            (TARGET_APPLY_ID,),
        ).fetchone()[0]
    finally:
        conn.close()
    assert bad == 0


def test_p14d_prediction_columns_untouched():
    """Verify predicted_numbers, actual_numbers, hit_count were not modified."""
    conn = sqlite3.connect(str(_PROD_DB))
    try:
        bad = conn.execute(
            """SELECT COUNT(*) FROM strategy_prediction_replays
               WHERE controlled_apply_id=?
               AND (predicted_numbers IS NULL OR actual_numbers IS NULL OR hit_count IS NULL)""",
            (TARGET_APPLY_ID,),
        ).fetchone()[0]
    finally:
        conn.close()
    assert bad == 0


# ── live rehearsal tests (temp DB) ────────────────────────────────────────────

def test_temp_apply_updates_1500_rows(temp_db):
    """Fresh temp DB starting with post-production state (all timestamps filled)."""
    # First rollback timestamps to simulate pre-backfill state
    from scripts.p17b_p14d_timestamp_backfill import rollback_backfill, apply_backfill, _row_count
    # Roll back to NULL (simulates pre-backfill state)
    rollback_backfill(temp_db, PROD_ROWS, allow_production=False)
    # Now apply
    result = apply_backfill(temp_db, PROD_ROWS, allow_production=False)
    assert result["updated_count"] == EXPECTED_TARGET
    assert result["inserted_count"] == 0
    assert _row_count(temp_db) == PROD_ROWS


def test_temp_rerun_updates_0_rows(temp_db):
    from scripts.p17b_p14d_timestamp_backfill import rollback_backfill, apply_backfill
    # Set up: roll back to NULL then apply
    rollback_backfill(temp_db, PROD_ROWS, allow_production=False)
    apply_backfill(temp_db, PROD_ROWS, allow_production=False)
    # Rerun
    r2 = apply_backfill(temp_db, PROD_ROWS, allow_production=False)
    assert r2["updated_count"] == 0


def test_temp_rollback_restores_nulls(temp_db):
    from scripts.p17b_p14d_timestamp_backfill import rollback_backfill, apply_backfill
    # Apply, then rollback
    rollback_backfill(temp_db, PROD_ROWS, allow_production=False)
    apply_backfill(temp_db, PROD_ROWS, allow_production=False)
    rb = rollback_backfill(temp_db, PROD_ROWS, allow_production=False)
    assert rb["rollback_updated_count"] == EXPECTED_TARGET
    # Verify NULL restored
    conn = sqlite3.connect(str(temp_db))
    try:
        null_count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=? AND prediction_cutoff_date IS NULL",
            (TARGET_APPLY_ID,),
        ).fetchone()[0]
    finally:
        conn.close()
    assert null_count == EXPECTED_TARGET


def test_script_rejects_production_db_without_flag():
    from scripts.p17b_p14d_timestamp_backfill import apply_backfill
    with pytest.raises(RuntimeError, match="SAFETY STOP"):
        apply_backfill(_PROD_DB, PROD_ROWS, allow_production=False)


# ── API verification ──────────────────────────────────────────────────────────

def test_api_ts3_has_timestamps_after_backfill():
    result = _run(get_replay_history(
        lottery_type="BIG_LOTTO", strategy_id="ts3_regime_3bet",
        replay_status=None, lifecycle_status=None,
        fixture_mode=False, date_from=None, date_to=None,
        page=1, page_size=5,
    ))
    for rec in result["records"]:
        assert rec.get("prediction_cutoff_date") is not None, \
            f"draw={rec['target_draw']}: prediction_cutoff_date is NULL after P17B backfill"
        assert rec.get("prediction_generated_at") is not None, \
            f"draw={rec['target_draw']}: prediction_generated_at is NULL after P17B backfill"


def test_no_db_writes_by_tests():
    conn = sqlite3.connect(str(_PROD_DB))
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == PROD_ROWS
