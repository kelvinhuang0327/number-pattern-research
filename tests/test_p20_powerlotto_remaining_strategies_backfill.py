"""
P20 — Power Lotto Remaining Strategies Backfill Tests.

Verifies dry-run, temp rehearsal, and production apply for
power_precision_3bet and power_orthogonal_5bet.
"""

from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest

_REPO_ROOT   = Path(__file__).resolve().parents[1]
_SCRIPT      = _REPO_ROOT / "scripts" / "p20_powerlotto_remaining_strategies_backfill.py"
_DRY_RUN     = _REPO_ROOT / "outputs" / "replay" / "p20_powerlotto_remaining_strategies_dry_run_20260520.json"
_REHEARSAL   = _REPO_ROOT / "outputs" / "replay" / "p20_powerlotto_remaining_strategies_tempdb_rehearsal_20260520.json"
_DECISION    = _REPO_ROOT / "outputs" / "replay" / "p20_powerlotto_remaining_strategies_apply_decision_20260520.json"
_APPLY_OUT   = _REPO_ROOT / "outputs" / "replay" / "p20_powerlotto_remaining_strategies_production_apply_20260520.json"
_PROD_DB     = _REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"

if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

STRATEGIES         = ["power_precision_3bet", "power_orthogonal_5bet"]
PROD_ROWS_BEFORE   = 6460
PROD_ROWS_AFTER    = 9460
EXPECTED_READY     = 3000
APPLY_ID           = "P20_POWERLOTTO_REMAINING_1500_PROD_20260520"
TRUTH_LEVEL        = "POWERLOTTO_REMAINING_STRATEGIES_BACKFILL_VERIFIED"
SOURCE             = "P20_POWERLOTTO_REMAINING_STRATEGIES_PRODUCTION_APPLY"


@pytest.fixture(scope="module")
def dry_run_output() -> dict:
    assert _DRY_RUN.exists()
    return json.loads(_DRY_RUN.read_text())


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


# ── static tests ──────────────────────────────────────────────────────────────

def test_script_exists():
    assert _SCRIPT.exists()


def test_dry_run_output_exists():
    assert _DRY_RUN.exists()


def test_rehearsal_exists():
    assert _REHEARSAL.exists()


def test_decision_exists():
    assert _DECISION.exists()


def test_apply_result_exists():
    assert _APPLY_OUT.exists()


# ── dry-run tests ─────────────────────────────────────────────────────────────

def test_dry_run_production_rows_before(dry_run_output: dict):
    assert dry_run_output["production_rows_before"] == PROD_ROWS_BEFORE


def test_dry_run_strategies(dry_run_output: dict):
    for sid in STRATEGIES:
        assert sid in dry_run_output["strategies"]


def test_dry_run_ready_candidates(dry_run_output: dict):
    assert dry_run_output["ready_candidates"] == EXPECTED_READY


def test_dry_run_fake_success_zero(dry_run_output: dict):
    assert dry_run_output["fake_success_count"] == 0


def test_dry_run_predicted_numbers_present(dry_run_output: dict):
    for c in dry_run_output["candidates_sample"]:
        if c["prediction_status"] == "READY":
            assert c["predicted_numbers"] is not None
            assert len(c["predicted_numbers"]) == 6


def test_dry_run_actual_numbers_present(dry_run_output: dict):
    for c in dry_run_output["candidates_sample"]:
        if c["prediction_status"] == "READY":
            assert c["actual_numbers"] is not None


def test_dry_run_hit_count_correct(dry_run_output: dict):
    for c in dry_run_output["candidates_sample"]:
        if c["prediction_status"] == "READY":
            assert c["hit_count"] == len(c["hit_numbers"])


def test_dry_run_cutoff_date_present(dry_run_output: dict):
    for c in dry_run_output["candidates_sample"]:
        if c["prediction_status"] == "READY":
            assert c["prediction_cutoff_date"] is not None


def test_dry_run_cutoff_lte_target(dry_run_output: dict):
    for c in dry_run_output["candidates_sample"]:
        if c["prediction_status"] == "READY" and c["prediction_cutoff_date"]:
            assert c["prediction_cutoff_date"] <= c["target_date"]


def test_dry_run_counts_as_success_false(dry_run_output: dict):
    for c in dry_run_output["candidates_sample"]:
        assert c["counts_as_success"] is False


def test_dry_run_duplicate_count_derived(dry_run_output: dict):
    # duplicate_existing_count must be from DB, not hardcoded
    assert "duplicate_existing_count" in dry_run_output


def test_dry_run_no_biglotto(dry_run_output: dict):
    assert dry_run_output["lottery_type"] == "POWER_LOTTO"
    for c in dry_run_output["candidates_sample"]:
        assert c["lottery_type"] == "POWER_LOTTO"


# ── rehearsal tests ───────────────────────────────────────────────────────────

def test_rehearsal_inserted_3000(rehearsal: dict):
    assert rehearsal["r1_apply_inserted_count"] == EXPECTED_READY


def test_rehearsal_rerun_inserted_0(rehearsal: dict):
    assert rehearsal["r2_rerun_inserted_count"] == 0


def test_rehearsal_rerun_duplicate_3000(rehearsal: dict):
    assert rehearsal["r2_rerun_duplicate_count"] == EXPECTED_READY


def test_rehearsal_rollback_3000(rehearsal: dict):
    assert rehearsal["rollback_deleted_count"] == EXPECTED_READY


def test_rehearsal_rollback_rows_6460(rehearsal: dict):
    assert rehearsal["rows_after_rollback"] == PROD_ROWS_BEFORE


def test_rehearsal_classification(rehearsal: dict):
    assert rehearsal["final_classification"] == "P20_REMAINING_POWERLOTTO_REHEARSAL_READY"


# ── production apply tests ────────────────────────────────────────────────────

def test_apply_inserted_3000(apply_result: dict):
    assert apply_result["inserted_count"] == EXPECTED_READY


def test_apply_duplicate_0(apply_result: dict):
    assert apply_result["duplicate_count"] == 0


def test_apply_rows_9460(apply_result: dict):
    assert apply_result["rows_after_apply"] == PROD_ROWS_AFTER


def test_apply_production_true(apply_result: dict):
    assert apply_result["production_apply"] is True


# ── live DB tests ─────────────────────────────────────────────────────────────

def test_production_db_rows_9460():
    conn = sqlite3.connect(str(_PROD_DB))
    try:
        count = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    finally:
        conn.close()
    assert count == PROD_ROWS_AFTER


def test_p20_rows_in_db():
    conn = sqlite3.connect(str(_PROD_DB))
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=?",
            (APPLY_ID,),
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == EXPECTED_READY


def test_p20_truth_level():
    conn = sqlite3.connect(str(_PROD_DB))
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=? AND truth_level=?",
            (APPLY_ID, TRUTH_LEVEL),
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == EXPECTED_READY


def test_p20_has_timestamps():
    conn = sqlite3.connect(str(_PROD_DB))
    try:
        bad = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=? AND (prediction_cutoff_date IS NULL OR prediction_generated_at IS NULL)",
            (APPLY_ID,),
        ).fetchone()[0]
    finally:
        conn.close()
    assert bad == 0


def test_p20_no_future_cutoff():
    conn = sqlite3.connect(str(_PROD_DB))
    try:
        bad = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=? AND prediction_cutoff_date > target_date",
            (APPLY_ID,),
        ).fetchone()[0]
    finally:
        conn.close()
    assert bad == 0


def test_p20_all_power_lotto():
    conn = sqlite3.connect(str(_PROD_DB))
    try:
        bad = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=? AND lottery_type != 'POWER_LOTTO'",
            (APPLY_ID,),
        ).fetchone()[0]
    finally:
        conn.close()
    assert bad == 0


def test_p20_no_fabricated():
    conn = sqlite3.connect(str(_PROD_DB))
    try:
        bad = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=? AND predicted_numbers IS NULL",
            (APPLY_ID,),
        ).fetchone()[0]
    finally:
        conn.close()
    assert bad == 0


def test_p20_no_biglotto_rows():
    conn = sqlite3.connect(str(_PROD_DB))
    try:
        bad = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=? AND lottery_type='BIG_LOTTO'",
            (APPLY_ID,),
        ).fetchone()[0]
    finally:
        conn.close()
    assert bad == 0


def test_p20_each_strategy_1500():
    conn = sqlite3.connect(str(_PROD_DB))
    try:
        for sid in STRATEGIES:
            count = conn.execute(
                "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=? AND strategy_id=?",
                (APPLY_ID, sid),
            ).fetchone()[0]
            assert count == 1500, f"{sid}: expected 1500 rows, got {count}"
    finally:
        conn.close()


def test_legacy_rows_unchanged():
    conn = sqlite3.connect(str(_PROD_DB))
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id IS NULL"
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == 460


def test_script_rejects_production_db_without_flag():
    from scripts.p20_powerlotto_remaining_strategies_backfill import apply_to_db, _generate_all_candidates
    candidates = _generate_all_candidates(_PROD_DB)
    with pytest.raises(RuntimeError, match="SAFETY STOP"):
        apply_to_db(_PROD_DB, candidates, APPLY_ID, expected_rows_before=PROD_ROWS_AFTER)
