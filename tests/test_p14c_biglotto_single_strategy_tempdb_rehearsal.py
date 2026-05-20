"""
Tests for P14C Big Lotto single-strategy temp DB rehearsal.

Verifies that the rehearsal script correctly applies 1500 rows to a temp DB,
is idempotent on rerun, and rolls back cleanly — without touching production.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest

_REPO_ROOT  = Path(__file__).resolve().parents[1]
_SCRIPT     = _REPO_ROOT / "scripts" / "p14c_biglotto_single_strategy_tempdb_rehearsal.py"
_OUTPUT     = _REPO_ROOT / "outputs" / "replay" / "p14c_biglotto_single_strategy_tempdb_rehearsal_20260520.json"
_P14B_INPUT = _REPO_ROOT / "outputs" / "replay" / "p14b_biglotto_single_strategy_replay_dry_run_20260520.json"
_PROD_DB    = _REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"

PROD_ROWS_BASELINE = 460
EXPECTED_READY     = 1500
EXPECTED_POST_APPLY = PROD_ROWS_BASELINE + EXPECTED_READY  # 1960
APPLY_ID           = "P14C_BIGLOTTO_TS3_1500_TEMP_REHEARSAL_20260520"

if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def output() -> dict:
    assert _OUTPUT.exists(), f"Output JSON not found: {_OUTPUT}"
    return json.loads(_OUTPUT.read_text())


@pytest.fixture(scope="module")
def p14b_input() -> dict:
    assert _P14B_INPUT.exists(), f"P14B input not found: {_P14B_INPUT}"
    return json.loads(_P14B_INPUT.read_text())


@pytest.fixture()
def temp_db(tmp_path):
    """Fresh copy of the production DB for each test that needs write access."""
    dest = tmp_path / "lottery_v2_test.db"
    shutil.copy(str(_PROD_DB), str(dest))
    return dest


# ── static structural tests ───────────────────────────────────────────────────

def test_script_exists():
    assert _SCRIPT.exists()


def test_p14b_input_exists():
    assert _P14B_INPUT.exists()


def test_p14b_input_has_1500_ready(p14b_input: dict):
    assert p14b_input["ready_candidates"] == EXPECTED_READY


def test_output_exists():
    assert _OUTPUT.exists()


def test_output_valid_json():
    data = json.loads(_OUTPUT.read_text())
    assert isinstance(data, dict)


# ── combined output assertions ────────────────────────────────────────────────

def test_temp_db_only(output: dict):
    assert output["temp_db_only"] is True


def test_production_apply_false(output: dict):
    assert output["production_apply"] is False


def test_rows_before_460(output: dict):
    assert output["rows_before"] == PROD_ROWS_BASELINE


def test_inserted_count_1500(output: dict):
    assert output["inserted_count"] == EXPECTED_READY


def test_rows_after_apply_1960(output: dict):
    assert output["rows_after_apply"] == EXPECTED_POST_APPLY


def test_rerun_inserted_count_zero(output: dict):
    assert output["rerun_inserted_count"] == 0


def test_rerun_duplicate_count_1500(output: dict):
    assert output["rerun_duplicate_count"] == EXPECTED_READY


def test_rows_after_rerun_unchanged(output: dict):
    assert output["rows_after_rerun"] == EXPECTED_POST_APPLY


def test_rollback_deleted_1500(output: dict):
    assert output["rollback_deleted_count"] == EXPECTED_READY


def test_rows_after_rollback_460(output: dict):
    assert output["rows_after_rollback"] == PROD_ROWS_BASELINE


def test_production_rows_after_460(output: dict):
    assert output["production_rows_after"] == PROD_ROWS_BASELINE


def test_fake_success_count_zero(output: dict):
    assert output["fake_success_count"] == 0


def test_error_count_zero(output: dict):
    assert output.get("error_count", 0) == 0


def test_final_classification_ready(output: dict):
    assert output["final_classification"] == "P14C_TEMP_DB_REHEARSAL_READY"


# ── production DB guard ───────────────────────────────────────────────────────

def test_production_db_still_460():
    conn = sqlite3.connect(str(_PROD_DB))
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == PROD_ROWS_BASELINE


# ── live apply / rollback tests ───────────────────────────────────────────────

def test_dry_run_writes_no_db(temp_db):
    from scripts.p14c_biglotto_single_strategy_tempdb_rehearsal import _row_count
    before = _row_count(temp_db)
    # dry-run: just regenerate candidates, no DB write
    from scripts.p14c_biglotto_single_strategy_tempdb_rehearsal import _regenerate_all_candidates
    candidates = _regenerate_all_candidates()
    after = _row_count(temp_db)
    assert after == before
    assert len(candidates) == EXPECTED_READY


def test_apply_inserts_1500_rows(temp_db):
    from scripts.p14c_biglotto_single_strategy_tempdb_rehearsal import (
        apply_rehearsal, _regenerate_all_candidates, _row_count,
    )
    candidates = _regenerate_all_candidates()
    result = apply_rehearsal(temp_db, candidates, APPLY_ID, expected_rows_before=PROD_ROWS_BASELINE)
    assert result["inserted_count"] == EXPECTED_READY
    assert result["duplicate_count"] == 0
    assert _row_count(temp_db) == EXPECTED_POST_APPLY


def test_temp_rows_460_to_1960(temp_db):
    from scripts.p14c_biglotto_single_strategy_tempdb_rehearsal import (
        apply_rehearsal, _regenerate_all_candidates, _row_count,
    )
    assert _row_count(temp_db) == PROD_ROWS_BASELINE
    candidates = _regenerate_all_candidates()
    apply_rehearsal(temp_db, candidates, APPLY_ID, expected_rows_before=PROD_ROWS_BASELINE)
    assert _row_count(temp_db) == EXPECTED_POST_APPLY


def test_rerun_inserts_zero_rows(temp_db):
    from scripts.p14c_biglotto_single_strategy_tempdb_rehearsal import (
        apply_rehearsal, _regenerate_all_candidates, _row_count,
    )
    candidates = _regenerate_all_candidates()
    apply_rehearsal(temp_db, candidates, APPLY_ID, expected_rows_before=PROD_ROWS_BASELINE)
    r2 = apply_rehearsal(temp_db, candidates, APPLY_ID, expected_rows_before=EXPECTED_POST_APPLY)
    assert r2["inserted_count"] == 0
    assert r2["duplicate_count"] == EXPECTED_READY
    assert _row_count(temp_db) == EXPECTED_POST_APPLY


def test_rollback_deletes_1500(temp_db):
    from scripts.p14c_biglotto_single_strategy_tempdb_rehearsal import (
        apply_rehearsal, rollback_rehearsal, _regenerate_all_candidates, _row_count,
    )
    candidates = _regenerate_all_candidates()
    apply_rehearsal(temp_db, candidates, APPLY_ID, expected_rows_before=PROD_ROWS_BASELINE)
    rb = rollback_rehearsal(temp_db, APPLY_ID, expected_rows_before=EXPECTED_POST_APPLY)
    assert rb["rollback_deleted_count"] == EXPECTED_READY
    assert _row_count(temp_db) == PROD_ROWS_BASELINE


def test_rollback_returns_rows_to_460(temp_db):
    from scripts.p14c_biglotto_single_strategy_tempdb_rehearsal import (
        apply_rehearsal, rollback_rehearsal, _regenerate_all_candidates, _row_count,
    )
    candidates = _regenerate_all_candidates()
    apply_rehearsal(temp_db, candidates, APPLY_ID, expected_rows_before=PROD_ROWS_BASELINE)
    rollback_rehearsal(temp_db, APPLY_ID, expected_rows_before=EXPECTED_POST_APPLY)
    assert _row_count(temp_db) == PROD_ROWS_BASELINE


def test_script_rejects_production_db():
    from scripts.p14c_biglotto_single_strategy_tempdb_rehearsal import (
        apply_rehearsal, _regenerate_all_candidates,
    )
    candidates = _regenerate_all_candidates()
    with pytest.raises(RuntimeError, match="SAFETY STOP"):
        apply_rehearsal(_PROD_DB, candidates, APPLY_ID, expected_rows_before=PROD_ROWS_BASELINE)


def test_script_rejects_row_count_mismatch(temp_db):
    from scripts.p14c_biglotto_single_strategy_tempdb_rehearsal import (
        apply_rehearsal, _regenerate_all_candidates,
    )
    candidates = _regenerate_all_candidates()
    with pytest.raises(RuntimeError, match="SAFETY STOP"):
        apply_rehearsal(temp_db, candidates, APPLY_ID, expected_rows_before=999)


def test_inserted_rows_have_controlled_apply_id(temp_db):
    from scripts.p14c_biglotto_single_strategy_tempdb_rehearsal import (
        apply_rehearsal, _regenerate_all_candidates,
    )
    candidates = _regenerate_all_candidates()
    apply_rehearsal(temp_db, candidates, APPLY_ID, expected_rows_before=PROD_ROWS_BASELINE)
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
    from scripts.p14c_biglotto_single_strategy_tempdb_rehearsal import (
        apply_rehearsal, _regenerate_all_candidates, TRUTH_LEVEL,
    )
    candidates = _regenerate_all_candidates()
    apply_rehearsal(temp_db, candidates, APPLY_ID, expected_rows_before=PROD_ROWS_BASELINE)
    conn = sqlite3.connect(str(temp_db))
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE truth_level=? AND controlled_apply_id=?",
            (TRUTH_LEVEL, APPLY_ID),
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == EXPECTED_READY


def test_inserted_rows_have_source(temp_db):
    from scripts.p14c_biglotto_single_strategy_tempdb_rehearsal import (
        apply_rehearsal, _regenerate_all_candidates, SOURCE,
    )
    candidates = _regenerate_all_candidates()
    apply_rehearsal(temp_db, candidates, APPLY_ID, expected_rows_before=PROD_ROWS_BASELINE)
    conn = sqlite3.connect(str(temp_db))
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE source=? AND controlled_apply_id=?",
            (SOURCE, APPLY_ID),
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == EXPECTED_READY


def test_no_artifact_only_rows(temp_db):
    """No rows with truth_level containing ARTIFACT_ONLY should be inserted."""
    from scripts.p14c_biglotto_single_strategy_tempdb_rehearsal import (
        apply_rehearsal, _regenerate_all_candidates,
    )
    candidates = _regenerate_all_candidates()
    apply_rehearsal(temp_db, candidates, APPLY_ID, expected_rows_before=PROD_ROWS_BASELINE)
    conn = sqlite3.connect(str(temp_db))
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE controlled_apply_id=? AND truth_level LIKE '%ARTIFACT%'",
            (APPLY_ID,),
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == 0


def test_no_retired_rows(temp_db):
    """No rows for RETIRED strategies should be inserted."""
    from scripts.p14c_biglotto_single_strategy_tempdb_rehearsal import (
        apply_rehearsal, _regenerate_all_candidates,
    )
    candidates = _regenerate_all_candidates()
    apply_rehearsal(temp_db, candidates, APPLY_ID, expected_rows_before=PROD_ROWS_BASELINE)
    conn = sqlite3.connect(str(temp_db))
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE controlled_apply_id=? AND strategy_id NOT IN ('ts3_regime_3bet')",
            (APPLY_ID,),
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == 0
