"""
P102 Special3 Draw Source Decision Audit Tests
Verifies read-only audit artifacts and governance invariants.
"""
import json
import os
import sqlite3
import pytest

# --- Artifact paths ---
JSON_PATH = "outputs/replay/special3_source_decision_audit_20260527.json"
MD_PATH = "docs/replay/special3_source_decision_audit_20260527.md"
DB_PATH = "lottery_api/data/lottery_v2.db"

# --- Governance baselines ---
EXPECTED_REPLAY_ROWS = 54462
EXPECTED_MAX_3STAR = "115000024"
EXPECTED_POWER_LOTTO_MAX = "115000041"
EXPECTED_3STAR_COUNT = 4115


@pytest.fixture(scope="module")
def audit_json():
    assert os.path.exists(JSON_PATH), f"JSON artifact not found: {JSON_PATH}"
    with open(JSON_PATH) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def db_conn():
    conn = sqlite3.connect(DB_PATH)
    yield conn
    conn.close()


# --- test_01: JSON artifact exists and is valid ---
def test_01_json_artifact_exists_and_valid():
    assert os.path.exists(JSON_PATH), f"Missing: {JSON_PATH}"
    with open(JSON_PATH) as f:
        data = json.load(f)
    assert isinstance(data, dict), "JSON must be a dict"
    assert "classification" in data


# --- test_02: Markdown artifact exists ---
def test_02_markdown_artifact_exists():
    assert os.path.exists(MD_PATH), f"Missing: {MD_PATH}"
    with open(MD_PATH) as f:
        content = f.read()
    assert "P102" in content
    assert len(content) > 100


# --- test_03: Classification is valid P102 HOLD classification ---
def test_03_classification_valid(audit_json):
    valid_classifications = [
        "P102_SPECIAL3_SOURCE_DECISION_HOLD_NO_LOCAL_SOURCE",
        "P102_SPECIAL3_SOURCE_DECISION_READY_SOURCE_FOUND",
    ]
    assert audit_json["classification"] in valid_classifications, \
        f"Invalid classification: {audit_json['classification']}"


# --- test_04: inspected_sources list is present and non-empty ---
def test_04_inspected_sources_present(audit_json):
    assert "sources_inspected" in audit_json, "sources_inspected key missing"
    sources = audit_json["sources_inspected"]
    assert isinstance(sources, list), "sources_inspected must be a list"
    assert len(sources) >= 5, f"Expected >= 5 sources inspected, got {len(sources)}"


# --- test_05: current DB max 3_STAR draw = 115000024 ---
def test_05_db_max_3star_draw_unchanged(db_conn):
    row = db_conn.execute(
        "SELECT MAX(CAST(draw AS INTEGER)) FROM draws WHERE lottery_type='3_STAR'"
    ).fetchone()
    assert row[0] is not None, "No 3_STAR draws found in DB"
    assert str(row[0]) == EXPECTED_MAX_3STAR, \
        f"Expected max 3_STAR draw={EXPECTED_MAX_3STAR}, got {row[0]}"


# --- test_06: draw_greater_than_history_end_found_locally field exists ---
def test_06_draw_availability_field_exists(audit_json):
    assert "draw_greater_than_history_end_found_locally" in audit_json, \
        "draw_greater_than_history_end_found_locally key missing"
    assert isinstance(audit_json["draw_greater_than_history_end_found_locally"], bool)


# --- test_07: no DB writes (db_writes, db_ingestion, replay_row_inserts all false) ---
def test_07_no_db_writes(audit_json):
    for key in ("db_writes", "db_ingestion", "replay_row_inserts"):
        assert key in audit_json, f"Key missing: {key}"
        assert audit_json[key] is False, \
            f"Expected {key}=false, got {audit_json[key]}"


# --- test_08: no ingestion — ingest_log has 0 3_STAR entries ---
def test_08_no_ingestion_history():
    ingest_log = "lottery_api/data/ingest_log.jsonl"
    if not os.path.exists(ingest_log):
        pytest.skip("ingest_log.jsonl not present")
    count = 0
    with open(ingest_log) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                if entry.get("lottery_type") == "3_STAR":
                    count += 1
            except json.JSONDecodeError:
                pass
    assert count == 0, f"Expected 0 3_STAR ingest log entries, found {count}"


# --- test_09: replay_rows remains 54462 ---
def test_09_replay_rows_unchanged(db_conn):
    row = db_conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()
    assert row[0] == EXPECTED_REPLAY_ROWS, \
        f"Expected {EXPECTED_REPLAY_ROWS} replay rows, got {row[0]}"


# --- test_10: 4_STAR remains DATA_GAP_BLOCKING ---
def test_10_star4_data_gap_blocking(audit_json, db_conn):
    # Check artifact
    assert audit_json.get("special4_status") == "DATA_GAP_BLOCKING", \
        f"Expected special4_status=DATA_GAP_BLOCKING, got {audit_json.get('special4_status')}"
    # Verify live DB
    row = db_conn.execute(
        "SELECT COUNT(*) FROM draws WHERE lottery_type='4_STAR'"
    ).fetchone()
    assert row[0] == 0, f"Expected 0 4_STAR draws, found {row[0]}"


# --- test_11: no Special3 promotion ---
def test_11_no_special3_promotion(audit_json):
    assert audit_json.get("special3_production_promotion") is False, \
        f"special3_production_promotion must be false, got {audit_json.get('special3_production_promotion')}"
    assert audit_json.get("strategy_promotion") is False, \
        f"strategy_promotion must be false, got {audit_json.get('strategy_promotion')}"


# --- test_12: recommended_next_action present ---
def test_12_recommended_next_action_present(audit_json):
    assert "recommended_next_action" in audit_json, \
        "recommended_next_action key missing"
    assert len(audit_json["recommended_next_action"]) > 20, \
        "recommended_next_action is too short"


# --- test_13: P101 artifact is referenced ---
def test_13_p101_artifact_referenced(audit_json):
    assert "p101_artifact" in audit_json, "p101_artifact key missing"
    p101 = audit_json["p101_artifact"]
    assert "special3_actual_draw_monitor" in p101, \
        f"p101_artifact should reference the monitor file, got: {p101}"


# --- test_14: fetcher_api_supports_3star is false ---
def test_14_fetcher_api_supports_3star_false(audit_json):
    assert "fetcher_api_supports_3star" in audit_json, \
        "fetcher_api_supports_3star key missing"
    assert audit_json["fetcher_api_supports_3star"] is False, \
        "fetcher_api_supports_3star must be false (3_STAR not in SOURCE_CONFIG)"


# --- test_15: POWER_LOTTO max draw unchanged in live DB ---
def test_15_power_lotto_max_draw_unchanged(db_conn):
    row = db_conn.execute(
        "SELECT MAX(CAST(draw AS INTEGER)) FROM draws WHERE lottery_type='POWER_LOTTO'"
    ).fetchone()
    assert row[0] is not None
    assert str(row[0]) == EXPECTED_POWER_LOTTO_MAX, \
        f"Expected POWER_LOTTO max={EXPECTED_POWER_LOTTO_MAX}, got {row[0]}"
