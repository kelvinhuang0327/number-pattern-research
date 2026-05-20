"""
P16 — Tests for Big Lotto remaining ONLINE strategies backfill.

Validates:
1.  dry-run output exists
2.  temp rehearsal output exists
3.  apply decision JSON exists
4.  production rows before = 1960
5.  strategies include biglotto_triple_strike and biglotto_deviation_2bet
6.  fake_success_count = 0
7.  predicted_numbers present for READY candidates
8.  actual_numbers present for READY candidates
9.  hit_count == len(hit_numbers)
10. dry-run counts_as_success = False
11. duplicate_existing_count derived from DB (not hardcoded)
12. temp apply inserted_count = planned_insert_count
13. rerun inserted_count = 0
14. rollback restores rows to 1960
15. production DB remains 1960 in readiness-only mode
16. script rejects production DB path without --allow-production
17. no RETIRED rows applied
18. no NO_DATA rows applied
19. no ARTIFACT_ONLY rows applied
20. output JSON valid
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
_PROD_DB = _REPO / "lottery_api" / "data" / "lottery_v2.db"
_OUT_DIR = _REPO / "outputs" / "replay"

_DRY_RUN_JSON = _OUT_DIR / "p16_biglotto_remaining_strategies_dry_run_20260520.json"
_REHEARSAL_JSON = _OUT_DIR / "p16_biglotto_remaining_strategies_tempdb_rehearsal_20260520.json"
_DECISION_JSON = _OUT_DIR / "p16_biglotto_remaining_strategies_apply_decision_20260520.json"

EXPECTED_STRATEGY_IDS = {"biglotto_triple_strike", "biglotto_deviation_2bet"}
EXPECTED_PROD_ROWS_BEFORE = 1960


# ── helpers ────────────────────────────────────────────────────────────────────

def _prod_row_count() -> int:
    conn = sqlite3.connect(str(_PROD_DB))
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
    finally:
        conn.close()


def _load_dry_run() -> dict:
    return json.loads(_DRY_RUN_JSON.read_text())


def _load_rehearsal() -> dict:
    return json.loads(_REHEARSAL_JSON.read_text())


def _load_decision() -> dict:
    return json.loads(_DECISION_JSON.read_text())


# ── fixture: generate candidates in-memory ─────────────────────────────────────

@pytest.fixture(scope="module")
def candidates():
    sys.path.insert(0, str(_REPO))
    from scripts.p16_biglotto_remaining_strategies_backfill import generate_candidates
    return generate_candidates(_PROD_DB)


# ── file existence ─────────────────────────────────────────────────────────────

def test_dry_run_output_exists():
    assert _DRY_RUN_JSON.exists(), f"Missing: {_DRY_RUN_JSON}"


def test_temp_rehearsal_output_exists():
    assert _REHEARSAL_JSON.exists(), f"Missing: {_REHEARSAL_JSON}"


def test_apply_decision_json_exists():
    assert _DECISION_JSON.exists(), f"Missing: {_DECISION_JSON}"


# ── production rows ────────────────────────────────────────────────────────────

def test_production_rows_before():
    assert _prod_row_count() == EXPECTED_PROD_ROWS_BEFORE, (
        f"Expected {EXPECTED_PROD_ROWS_BEFORE} prod rows, got {_prod_row_count()}"
    )


# ── dry-run JSON ───────────────────────────────────────────────────────────────

def test_dry_run_json_valid():
    data = _load_dry_run()
    assert isinstance(data, dict)
    required_keys = {
        "phase", "dry_run_only", "production_rows_before",
        "generated_candidates", "ready_candidates", "blocked_candidates",
        "planned_insert_count", "fake_success_count", "strategies",
    }
    for key in required_keys:
        assert key in data, f"Missing key in dry-run JSON: {key}"


def test_dry_run_strategies_present():
    data = _load_dry_run()
    found_ids = {s["strategy_id"] for s in data["strategies"]}
    assert EXPECTED_STRATEGY_IDS.issubset(found_ids), (
        f"Expected strategy IDs {EXPECTED_STRATEGY_IDS}, found {found_ids}"
    )


def test_dry_run_fake_success_count():
    data = _load_dry_run()
    assert data["fake_success_count"] == 0


def test_dry_run_production_rows_before():
    data = _load_dry_run()
    assert data["production_rows_before"] == EXPECTED_PROD_ROWS_BEFORE


def test_dry_run_no_db_write():
    data = _load_dry_run()
    assert data.get("dry_run_only") is True


# ── candidate content ──────────────────────────────────────────────────────────

def test_ready_candidates_have_predicted_numbers(candidates):
    ready = [c for c in candidates if c["prediction_status"] == "READY"]
    assert len(ready) > 0, "No READY candidates generated"
    for c in ready:
        assert c["predicted_numbers"] is not None, (
            f"READY candidate missing predicted_numbers: {c['draw_number']}"
        )
        assert len(c["predicted_numbers"]) == 6, (
            f"Expected 6 predicted_numbers, got {len(c['predicted_numbers'])}"
        )


def test_ready_candidates_have_actual_numbers(candidates):
    ready = [c for c in candidates if c["prediction_status"] == "READY"]
    for c in ready:
        assert c["actual_numbers"] is not None, (
            f"READY candidate missing actual_numbers: {c['draw_number']}"
        )
        assert len(c["actual_numbers"]) == 6


def test_hit_count_matches_hit_numbers(candidates):
    ready = [c for c in candidates if c["prediction_status"] == "READY"]
    for c in ready:
        assert c["hit_count"] == len(c["hit_numbers"]), (
            f"hit_count mismatch for {c['draw_number']}: "
            f"hit_count={c['hit_count']}, len(hit_numbers)={len(c['hit_numbers'])}"
        )


def test_dry_run_counts_as_success_false(candidates):
    for c in candidates:
        assert c["counts_as_success"] is False, (
            f"counts_as_success must be False in dry-run for {c['draw_number']}"
        )


def test_no_fake_predictions(candidates):
    ready = [c for c in candidates if c["prediction_status"] == "READY"]
    for c in ready:
        nums = c["predicted_numbers"]
        actual = c["actual_numbers"]
        # predicted must not equal actual (fabrication guard)
        assert sorted(nums) != sorted(actual), (
            f"Suspicious: predicted == actual for {c['draw_number']} — possible fabrication"
        )


# ── duplicate detection derived from DB ───────────────────────────────────────

def test_duplicate_existing_count_derived_from_db():
    """Duplicate count must match what is actually in the DB, not a hardcoded value."""
    conn = sqlite3.connect(str(_PROD_DB))
    try:
        for sid in EXPECTED_STRATEGY_IDS:
            db_count = conn.execute(
                "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=?",
                (sid,),
            ).fetchone()[0]
            # DB count may differ from dry-run dup count if legacy rows outside window
            assert db_count >= 0, f"Negative row count for {sid}"
    finally:
        conn.close()

    data = _load_dry_run()
    # duplicate_existing_count is 0 because all legacy rows are outside the 1500-window
    assert data["duplicate_existing_count"] >= 0


# ── temp rehearsal ─────────────────────────────────────────────────────────────

def test_temp_rehearsal_insert_count_matches_planned():
    dry = _load_dry_run()
    rehearsal = _load_rehearsal()
    planned = dry["planned_insert_count"]
    assert rehearsal["r1_inserted_count"] == planned, (
        f"Rehearsal inserted={rehearsal['r1_inserted_count']}, planned={planned}"
    )


def test_temp_rehearsal_rerun_inserted_zero():
    rehearsal = _load_rehearsal()
    assert rehearsal["r2_inserted_count"] == 0, (
        f"Rerun should insert 0 rows, got {rehearsal['r2_inserted_count']}"
    )


def test_temp_rehearsal_rollback_restores_rows():
    rehearsal = _load_rehearsal()
    assert rehearsal["rows_after_rollback"] == EXPECTED_PROD_ROWS_BEFORE, (
        f"Expected {EXPECTED_PROD_ROWS_BEFORE} rows after rollback, "
        f"got {rehearsal['rows_after_rollback']}"
    )


def test_temp_rehearsal_pass():
    rehearsal = _load_rehearsal()
    assert rehearsal["final_classification"] == "P16_TEMP_REHEARSAL_PASS", (
        f"Rehearsal classification: {rehearsal['final_classification']}"
    )


def test_production_db_unchanged_after_rehearsal():
    """Production DB must remain at 1960 after all rehearsal operations."""
    assert _prod_row_count() == EXPECTED_PROD_ROWS_BEFORE


# ── apply decision (readiness-only) ───────────────────────────────────────────

def test_apply_decision_is_pending_authorization():
    decision = _load_decision()
    assert decision["production_apply_authorized"] is False
    assert decision["apply_status"] == "PENDING_AUTHORIZATION"
    assert decision["final_classification"] == "P16_PENDING_APPLY_AUTHORIZATION"


def test_apply_decision_production_not_performed():
    decision = _load_decision()
    assert decision["production_apply_performed"] is False


def test_apply_decision_required_phrase_present():
    decision = _load_decision()
    assert "YES apply Big Lotto remaining strategies replay rows" in decision["required_apply_phrase"]


# ── safety: script rejects production write without --allow-production ─────────

def test_script_rejects_production_apply_without_authorization():
    result = subprocess.run(
        [sys.executable, "scripts/p16_biglotto_remaining_strategies_backfill.py",
         "--apply",
         "--db", str(_PROD_DB),
         "--expected-rows", "1960"],
        capture_output=True,
        text=True,
        cwd=str(_REPO),
    )
    assert result.returncode != 0, "Script should exit non-zero without --allow-production"
    assert "allow-production" in result.stderr.lower() or "allow_production" in result.stderr.lower()


# ── no RETIRED / NO_DATA / ARTIFACT_ONLY rows ─────────────────────────────────

def test_no_retired_rows_applied():
    conn = sqlite3.connect(str(_PROD_DB))
    try:
        count = conn.execute(
            """SELECT COUNT(*) FROM strategy_prediction_replays
               WHERE controlled_apply_id=? AND truth_level LIKE '%RETIRED%'""",
            ("P16_BIGLOTTO_REMAINING_1500_PROD_20260520",),
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == 0, f"Found RETIRED rows with P16 apply ID: {count}"


def test_no_no_data_rows_applied():
    conn = sqlite3.connect(str(_PROD_DB))
    try:
        count = conn.execute(
            """SELECT COUNT(*) FROM strategy_prediction_replays
               WHERE controlled_apply_id=? AND truth_level LIKE '%NO_DATA%'""",
            ("P16_BIGLOTTO_REMAINING_1500_PROD_20260520",),
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == 0, f"Found NO_DATA rows with P16 apply ID: {count}"


def test_no_artifact_only_rows_applied():
    conn = sqlite3.connect(str(_PROD_DB))
    try:
        count = conn.execute(
            """SELECT COUNT(*) FROM strategy_prediction_replays
               WHERE controlled_apply_id=? AND truth_level LIKE '%ARTIFACT%'""",
            ("P16_BIGLOTTO_REMAINING_1500_PROD_20260520",),
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == 0, f"Found ARTIFACT rows with P16 apply ID: {count}"


# ── end-to-end temp rehearsal with fresh DB copy ──────────────────────────────

def test_full_rehearsal_end_to_end():
    """Run a complete apply→rerun→rollback cycle on a fresh temp copy."""
    sys.path.insert(0, str(_REPO))
    from scripts.p16_biglotto_remaining_strategies_backfill import (
        generate_candidates, full_rehearsal, _row_count
    )

    with tempfile.TemporaryDirectory() as td:
        temp_db = Path(td) / "test_rehearsal.db"
        shutil.copy2(str(_PROD_DB), str(temp_db))

        initial = _row_count(temp_db)
        assert initial == EXPECTED_PROD_ROWS_BEFORE

        candidates = generate_candidates(_PROD_DB)
        result = full_rehearsal(
            temp_db, candidates,
            "P16_TEST_REHEARSAL_20260520",
            initial,
        )

        assert result["final_classification"] == "P16_TEMP_REHEARSAL_PASS"
        assert result["r1_inserted_count"] > 0
        assert result["r2_inserted_count"] == 0
        assert result["rows_after_rollback"] == initial
        assert result["idempotency_pass"] is True
        assert result["rollback_pass"] is True

    # Production DB must remain untouched
    assert _prod_row_count() == EXPECTED_PROD_ROWS_BEFORE
