"""
tests/test_p101_special3_actual_draw_monitor.py

P101 Special3 Actual Draw Availability Monitor — governance tests.

Verifies:
  1.  JSON artifact exists and is valid
  2.  MD artifact exists
  3.  Classification is a valid P101 value
  4.  P100 artifact is referenced
  5.  actual_draw_available field exists
  6.  No DB writes
  7.  No ingestion
  8.  replay_rows remains 54462 (live DB check)
  9.  4_STAR remains DATA_GAP_BLOCKING
  10. No Special3 promotion
  11. next / recommended action is present
  12. HOLD vs READY consistency
  13. P101 gate status is valid
"""

import json
import os
import sqlite3

import pytest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
JSON_PATH = "outputs/replay/special3_actual_draw_monitor_20260527.json"
MD_PATH   = "docs/replay/special3_actual_draw_monitor_20260527.md"
DB_PATH   = "lottery_api/data/lottery_v2.db"

P100_JSON_PATH = "outputs/replay/special3_prospective_evaluation_20260527.json"

EXPECTED_REPLAY_ROWS        = 54462
EXPECTED_POWER_LOTTO_MAX    = 115000041
HISTORY_END_DRAW            = "115000024"

VALID_CLASSIFICATIONS = {
    "P101_SPECIAL3_ACTUAL_DRAW_MONITOR_HOLD",
    "P101_SPECIAL3_ACTUAL_DRAW_MONITOR_READY_FOR_EVALUATION",
}

VALID_GATE_STATUSES = {
    "NOT_YET_ELIGIBLE",
    "ELIGIBLE",
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def artifact():
    with open(JSON_PATH) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def db():
    conn = sqlite3.connect(DB_PATH)
    yield conn
    conn.close()


# ---------------------------------------------------------------------------
# Test 01 — JSON artifact exists and is valid JSON
# ---------------------------------------------------------------------------
def test_01_json_artifact_exists_and_valid():
    assert os.path.exists(JSON_PATH), f"Missing: {JSON_PATH}"
    with open(JSON_PATH) as f:
        data = json.load(f)
    assert isinstance(data, dict), "JSON root must be a dict"
    assert "classification" in data
    assert "actual_draw_available" in data


# ---------------------------------------------------------------------------
# Test 02 — MD artifact exists
# ---------------------------------------------------------------------------
def test_02_md_artifact_exists():
    assert os.path.exists(MD_PATH), f"Missing: {MD_PATH}"
    with open(MD_PATH) as f:
        text = f.read()
    assert len(text) > 100, "MD artifact too short"
    assert "P101" in text


# ---------------------------------------------------------------------------
# Test 03 — classification is a valid P101 value
# ---------------------------------------------------------------------------
def test_03_classification_is_valid(artifact):
    assert artifact["classification"] in VALID_CLASSIFICATIONS, (
        f"Unexpected classification: {artifact['classification']}"
    )


# ---------------------------------------------------------------------------
# Test 04 — P100 artifact is referenced
# ---------------------------------------------------------------------------
def test_04_p100_artifact_referenced(artifact):
    p100_ref = artifact.get("p100_artifact", "")
    assert P100_JSON_PATH in p100_ref, (
        f"p100_artifact must reference '{P100_JSON_PATH}', got '{p100_ref}'"
    )
    p100_cls = artifact.get("p100_classification", "")
    assert "P100_SPECIAL3_PROSPECTIVE_EVALUATION" in p100_cls, (
        f"p100_classification unexpected: {p100_cls}"
    )


# ---------------------------------------------------------------------------
# Test 05 — actual_draw_available field exists and is boolean
# ---------------------------------------------------------------------------
def test_05_actual_draw_available_field_exists(artifact):
    assert "actual_draw_available" in artifact
    assert isinstance(artifact["actual_draw_available"], bool), (
        "actual_draw_available must be a bool"
    )


# ---------------------------------------------------------------------------
# Test 06 — no DB writes
# ---------------------------------------------------------------------------
def test_06_no_db_writes(artifact):
    assert artifact.get("db_writes") is False, "db_writes must be false"
    assert artifact.get("db_ingestion") is False, "db_ingestion must be false"
    assert artifact.get("replay_row_inserts") is False, "replay_row_inserts must be false"


# ---------------------------------------------------------------------------
# Test 07 — no ingestion statement
# ---------------------------------------------------------------------------
def test_07_no_ingestion(artifact):
    assert artifact.get("db_ingestion") is False, "db_ingestion must be false"
    # MD must not claim ingestion was performed
    with open(MD_PATH) as f:
        text = f.read()
    assert "ingested successfully" not in text.lower()
    assert "ingestion complete" not in text.lower()


# ---------------------------------------------------------------------------
# Test 08 — replay_rows remains 54462 (live DB check)
# ---------------------------------------------------------------------------
def test_08_replay_rows_unchanged(db, artifact):
    live_rows = db.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays"
    ).fetchone()[0]
    assert live_rows == EXPECTED_REPLAY_ROWS, (
        f"Live replay_rows={live_rows}, expected {EXPECTED_REPLAY_ROWS}"
    )
    # artifact must also record correct baseline
    assert artifact.get("replay_rows_checked") == EXPECTED_REPLAY_ROWS, (
        f"artifact replay_rows_checked={artifact.get('replay_rows_checked')}"
    )


# ---------------------------------------------------------------------------
# Test 09 — 4_STAR remains DATA_GAP_BLOCKING
# ---------------------------------------------------------------------------
def test_09_4star_data_gap_blocking(db, artifact):
    count_4star = db.execute(
        "SELECT COUNT(*) FROM draws WHERE lottery_type='4_STAR'"
    ).fetchone()[0]
    assert count_4star == 0, f"4_STAR draws count={count_4star}, expected 0"
    assert artifact.get("star4_draws_count") == 0
    assert artifact.get("special4_status") == "DATA_GAP_BLOCKING"
    assert artifact.get("star4_backtest") is False


# ---------------------------------------------------------------------------
# Test 10 — no Special3 production promotion
# ---------------------------------------------------------------------------
def test_10_no_special3_production_promotion(artifact):
    assert artifact.get("special3_production_promotion") is False
    assert artifact.get("no_production_promotion") is True


# ---------------------------------------------------------------------------
# Test 11 — next action / recommended action is present
# ---------------------------------------------------------------------------
def test_11_recommended_next_action_present(artifact):
    action = artifact.get("recommended_next_action", "")
    assert isinstance(action, str) and len(action) > 10, (
        "recommended_next_action must be a non-empty string"
    )
    # SOP checklist must be present
    sop = artifact.get("sop_checklist")
    assert isinstance(sop, list) and len(sop) >= 1, (
        "sop_checklist must be a non-empty list"
    )


# ---------------------------------------------------------------------------
# Test 12 — HOLD vs READY consistency
# ---------------------------------------------------------------------------
def test_12_hold_ready_consistency(artifact):
    cls = artifact["classification"]
    available = artifact["actual_draw_available"]

    if cls == "P101_SPECIAL3_ACTUAL_DRAW_MONITOR_HOLD":
        assert available is False, (
            "HOLD classification requires actual_draw_available=false"
        )
        assert "HOLD" in artifact.get("monitor_status", "")
        hold_reason = artifact.get("hold_reason", "")
        assert len(hold_reason) > 10, "HOLD artifact must include hold_reason"

    elif cls == "P101_SPECIAL3_ACTUAL_DRAW_MONITOR_READY_FOR_EVALUATION":
        assert available is True, (
            "READY classification requires actual_draw_available=true"
        )
        assert "READY" in artifact.get("monitor_status", ""), (
            "monitor_status must include READY"
        )


# ---------------------------------------------------------------------------
# Test 13 — P101 gate status is valid
# ---------------------------------------------------------------------------
def test_13_p101_gate_status_valid(artifact):
    gate_status = artifact.get("p101_gate_status", "")
    assert gate_status in VALID_GATE_STATUSES, (
        f"p101_gate_status '{gate_status}' not in {VALID_GATE_STATUSES}"
    )
    gate_reason = artifact.get("p101_gate_reason", "")
    assert isinstance(gate_reason, str) and len(gate_reason) > 10, (
        "p101_gate_reason must be present"
    )


# ---------------------------------------------------------------------------
# Test 14 — history_end_draw matches P99/P100 baseline
# ---------------------------------------------------------------------------
def test_14_history_end_draw_matches_baseline(artifact):
    assert artifact.get("history_end_draw") == HISTORY_END_DRAW, (
        f"history_end_draw must be '{HISTORY_END_DRAW}'"
    )


# ---------------------------------------------------------------------------
# Test 15 — POWER_LOTTO max draw unchanged in live DB
# ---------------------------------------------------------------------------
def test_15_power_lotto_max_draw_unchanged(db):
    pl_max = db.execute(
        "SELECT MAX(CAST(draw AS INTEGER)) FROM draws WHERE lottery_type='POWER_LOTTO'"
    ).fetchone()[0]
    assert pl_max == EXPECTED_POWER_LOTTO_MAX, (
        f"POWER_LOTTO max_draw={pl_max}, expected {EXPECTED_POWER_LOTTO_MAX}"
    )
