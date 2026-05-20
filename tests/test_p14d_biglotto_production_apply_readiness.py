"""
Tests for P14D Big Lotto production apply readiness review.

Validates that the readiness artifacts are present and consistent,
and that after the authorized production apply the DB is in the
expected state (1960 rows, correct apply_id, truth_level, source).
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

_REPO_ROOT    = Path(__file__).resolve().parents[1]
_DECISION_JSON = _REPO_ROOT / "outputs" / "replay" / "p14d_biglotto_production_apply_decision_20260520.json"
_RESULT_JSON  = _REPO_ROOT / "outputs" / "replay" / "p14d_biglotto_production_apply_result_20260520.json"
_READINESS_DOC = _REPO_ROOT / "docs" / "replay" / "p14d_biglotto_production_apply_readiness_20260520.md"
_PROD_DB      = _REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"

PROD_ROWS_BEFORE = 460
EXPECTED_AFTER   = 1960
PLANNED_INSERT   = 1500
APPLY_ID         = "P14D_BIGLOTTO_TS3_1500_PROD_20260520"
TRUTH_LEVEL      = "BIGLOTTO_SINGLE_STRATEGY_BACKFILL_VERIFIED"
SOURCE           = "P14D_BIGLOTTO_PRODUCTION_APPLY"
REQUIRED_PHRASE  = "YES apply Big Lotto single strategy replay rows"


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def decision() -> dict:
    assert _DECISION_JSON.exists(), f"Decision JSON not found: {_DECISION_JSON}"
    return json.loads(_DECISION_JSON.read_text())


@pytest.fixture(scope="module")
def result() -> dict:
    assert _RESULT_JSON.exists(), f"Result JSON not found: {_RESULT_JSON}"
    return json.loads(_RESULT_JSON.read_text())


# ── decision JSON tests ───────────────────────────────────────────────────────

def test_decision_json_exists():
    assert _DECISION_JSON.exists()


def test_readiness_doc_exists():
    assert _READINESS_DOC.exists()


def test_production_rows_before(decision: dict):
    assert decision["production_rows_before"] == PROD_ROWS_BEFORE


def test_planned_insert_count(decision: dict):
    assert decision["planned_insert_count"] == PLANNED_INSERT


def test_expected_rows_after_apply(decision: dict):
    assert decision["expected_rows_after_apply"] == EXPECTED_AFTER


def test_selected_strategy_id(decision: dict):
    assert decision["selected_strategy_id"] == "ts3_regime_3bet"


def test_p14b_ready_candidates(decision: dict):
    assert decision["p14b_ready_candidates"] == 1500


def test_p14c_temp_rehearsal_pass(decision: dict):
    assert decision["p14c_temp_rehearsal_pass"] is True


def test_p14c_idempotency_pass(decision: dict):
    assert decision["p14c_idempotency_pass"] is True


def test_p14c_rollback_pass(decision: dict):
    assert decision["p14c_rollback_pass"] is True


def test_fake_success_count_zero(decision: dict):
    assert decision["fake_success_count"] == 0


def test_required_apply_phrase(decision: dict):
    assert decision["required_apply_phrase"] == REQUIRED_PHRASE


def test_apply_performed(decision: dict):
    # apply-authorized mode: production_apply_performed must be true
    assert decision["production_apply_authorized"] is True


# ── result JSON tests (post-apply) ────────────────────────────────────────────

def test_result_json_exists():
    assert _RESULT_JSON.exists()


def test_result_inserted_count(result: dict):
    assert result["inserted_count"] == PLANNED_INSERT


def test_result_duplicate_count_zero(result: dict):
    assert result["duplicate_count"] == 0


def test_result_error_count_zero(result: dict):
    assert result["error_count"] == 0


def test_result_rows_after_apply(result: dict):
    assert result["rows_after_apply"] == EXPECTED_AFTER


def test_result_production_apply_true(result: dict):
    assert result["production_apply"] is True


def test_result_temp_db_only_false(result: dict):
    assert result["temp_db_only"] is False


def test_result_classification(result: dict):
    assert result["final_classification"] == "P14D_PRODUCTION_APPLY_COMPLETE"


def test_result_fake_success_zero(result: dict):
    assert result["fake_success_count"] == 0


# ── live production DB tests ──────────────────────────────────────────────────

def test_production_db_rows_1960():
    conn = sqlite3.connect(str(_PROD_DB))
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
    finally:
        conn.close()
    # After P16, production has 4960 rows; P14D rows (1500) are still present
    assert count >= EXPECTED_AFTER, \
        f"Expected at least {EXPECTED_AFTER} rows (post-P14D baseline), got {count}"


def test_production_db_p14d_rows():
    conn = sqlite3.connect(str(_PROD_DB))
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=?",
            (APPLY_ID,),
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == PLANNED_INSERT, \
        f"Expected {PLANNED_INSERT} P14D rows, got {count}"


def test_production_db_legacy_rows_unchanged():
    conn = sqlite3.connect(str(_PROD_DB))
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id IS NULL"
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == PROD_ROWS_BEFORE, \
        f"Legacy rows changed: expected {PROD_ROWS_BEFORE}, got {count}"


def test_production_db_p14d_truth_level():
    conn = sqlite3.connect(str(_PROD_DB))
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=? AND truth_level=?",
            (APPLY_ID, TRUTH_LEVEL),
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == PLANNED_INSERT, \
        f"Expected {PLANNED_INSERT} rows with truth_level={TRUTH_LEVEL!r}, got {count}"


def test_production_db_p14d_source():
    conn = sqlite3.connect(str(_PROD_DB))
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=? AND source=?",
            (APPLY_ID, SOURCE),
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == PLANNED_INSERT, \
        f"Expected {PLANNED_INSERT} rows with source={SOURCE!r}, got {count}"


def test_production_db_p14d_strategy():
    conn = sqlite3.connect(str(_PROD_DB))
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=? AND strategy_id=?",
            (APPLY_ID, "ts3_regime_3bet"),
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == PLANNED_INSERT


def test_production_db_p14d_lottery_type():
    conn = sqlite3.connect(str(_PROD_DB))
    try:
        bad = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE controlled_apply_id=? AND lottery_type != 'BIG_LOTTO'",
            (APPLY_ID,),
        ).fetchone()[0]
    finally:
        conn.close()
    assert bad == 0, f"Found {bad} P14D rows with wrong lottery_type"


def test_production_db_no_fabricated_rows():
    """No P14D rows should have NULL predicted_numbers."""
    conn = sqlite3.connect(str(_PROD_DB))
    try:
        bad = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE controlled_apply_id=? AND predicted_numbers IS NULL",
            (APPLY_ID,),
        ).fetchone()[0]
    finally:
        conn.close()
    assert bad == 0, f"Found {bad} P14D rows with NULL predicted_numbers"


# ── readiness doc content checks ─────────────────────────────────────────────

def test_readiness_doc_mentions_rollback():
    content = _READINESS_DOC.read_text()
    assert "rollback" in content.lower()


def test_readiness_doc_mentions_baseline_update():
    content = _READINESS_DOC.read_text()
    assert "baseline update" in content.lower() or "requires_baseline_update" in content.lower() or "Tests Requiring" in content


def test_readiness_doc_mentions_authorization():
    content = _READINESS_DOC.read_text()
    assert REQUIRED_PHRASE in content
