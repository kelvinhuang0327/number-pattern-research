"""
tests/test_p89_steady_state_monitoring_snapshot.py
P89 Steady-State Monitoring Evidence Snapshot — 12 governance assertions
"""
import json
import os
import sqlite3
import pytest

SNAPSHOT_JSON = "outputs/replay/p89_steady_state_monitoring_snapshot_20260526.json"
SNAPSHOT_MD = "docs/replay/p89_steady_state_monitoring_snapshot_20260526.md"
DB_PATH = "lottery_api/data/lottery_v2.db"

EXPECTED_REPLAY_ROWS = 46962
EXPECTED_MAX_DRAW = 115000041


@pytest.fixture(scope="module")
def snapshot_json():
    assert os.path.exists(SNAPSHOT_JSON), f"JSON artifact missing: {SNAPSHOT_JSON}"
    with open(SNAPSHOT_JSON, encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="module")
def snapshot_md():
    assert os.path.exists(SNAPSHOT_MD), f"Markdown artifact missing: {SNAPSHOT_MD}"
    with open(SNAPSHOT_MD, encoding="utf-8") as fh:
        return fh.read()


@pytest.fixture(scope="module")
def db_conn():
    assert os.path.exists(DB_PATH), f"DB not found: {DB_PATH}"
    con = sqlite3.connect(DB_PATH)
    yield con
    con.close()


# 1. JSON artifact exists and is valid JSON
def test_json_artifact_exists(snapshot_json):
    assert snapshot_json is not None
    assert isinstance(snapshot_json, dict)


# 2. Markdown artifact exists
def test_markdown_artifact_exists(snapshot_md):
    assert len(snapshot_md) > 100, "Markdown artifact appears empty"


# 3. Classification is valid P89_STEADY_STATE_MONITORING_PASS
def test_classification_valid(snapshot_json):
    assert snapshot_json["classification"] == "P89_STEADY_STATE_MONITORING_PASS", (
        f"Expected P89_STEADY_STATE_MONITORING_PASS, got {snapshot_json['classification']}"
    )
    assert snapshot_json["system_status"] == "STABLE"
    assert snapshot_json["new_draw_detected"] is False
    assert snapshot_json["source_decision_required"] is False


# 4. replay_rows = 46962 (JSON artifact)
def test_replay_rows_json(snapshot_json):
    baseline = snapshot_json["production_baseline"]
    assert baseline["replay_rows"] == EXPECTED_REPLAY_ROWS, (
        f"JSON replay_rows={baseline['replay_rows']}, expected {EXPECTED_REPLAY_ROWS}"
    )
    assert baseline["replay_row_changes"] == 0


# 5. POWER_LOTTO max_draw = 115000041 (DB read)
def test_max_draw_db(db_conn):
    cur = db_conn.cursor()
    cur.execute(
        "SELECT MAX(CAST(draw AS INTEGER)) FROM draws WHERE lottery_type='POWER_LOTTO'"
    )
    max_draw = cur.fetchone()[0]
    assert max_draw == EXPECTED_MAX_DRAW, (
        f"DB max_draw={max_draw}, expected {EXPECTED_MAX_DRAW}"
    )


# 6. P79 sentinel ids 46961 / 46962 referenced in JSON and intact in DB
def test_p79_sentinels(snapshot_json, db_conn):
    sentinels = snapshot_json["production_baseline"]["p79_sentinels"]
    ids = [s["id"] for s in sentinels]
    assert 46961 in ids, "Sentinel id=46961 not in JSON"
    assert 46962 in ids, "Sentinel id=46962 not in JSON"

    cur = db_conn.cursor()
    cur.execute(
        "SELECT id, dry_run, truth_level FROM strategy_prediction_replays "
        "WHERE id IN (46961, 46962) ORDER BY id"
    )
    rows = cur.fetchall()
    assert len(rows) == 2, f"Expected 2 sentinel rows, got {len(rows)}"
    for row in rows:
        assert row[1] == 0, f"Sentinel id={row[0]} has dry_run={row[1]}, expected 0"
        assert row[2] == "POWERLOTTO_DRAW_EXT_VERIFIED", (
            f"Sentinel id={row[0]} truth_level={row[2]}"
        )


# 7. Source decision guard result present
def test_source_decision_guard_result(snapshot_json):
    checks = snapshot_json["monitoring_checks"]
    p86 = checks["p86_source_decision_guard"]
    assert "classification" in p86
    assert p86["classification"] in [
        "SOURCE_UNAVAILABLE", "FRESHNESS_PASS", "STABLE_NO_NEW_DRAW",
        "SOURCE_DECISION_REQUIRED", "SOURCE_STALE"
    ]
    assert p86["db_writes"] is False
    assert p86["db_max_draw"] == EXPECTED_MAX_DRAW


# 8. Freshness guard result present
def test_freshness_guard_result(snapshot_json):
    p82 = snapshot_json["monitoring_checks"]["p82_freshness_guard"]
    assert "classification" in p82
    assert p82["classification"] == "FRESHNESS_PASS"
    assert p82["draw_gap_detected"] is False
    assert p82["replay_gap_detected"] is False
    assert p82["batch_a_coverage_pct"] == 100.0


# 9. Browser smoke result present
def test_browser_smoke_result(snapshot_json, snapshot_md):
    smoke = snapshot_json["monitoring_checks"]["browser_smoke"]
    assert "classification" in smoke
    assert smoke["passed"] == 50
    assert smoke["failed"] == 0
    assert "browser" in snapshot_md.lower() or "smoke" in snapshot_md.lower()


# 10. No DB-write instructions present as active steps
def test_no_db_write_instructions(snapshot_json, snapshot_md):
    governance = snapshot_json["governance"]
    assert governance["no_db_writes"] is True
    assert governance["db_writes"] is False
    assert governance["no_replay_inserts"] is True
    assert governance["replay_row_changes"] == 0

    forbidden = snapshot_json["operator_actions"]["forbidden_actions"]
    assert any("insert" in f.lower() or "draws" in f.lower() for f in forbidden), (
        "INSERT into draws must be in forbidden_actions"
    )

    md_lower = snapshot_md.lower()
    assert "forbidden" in md_lower, "Forbidden actions must be documented in markdown"


# 11. replay_rows = 46962 (DB read — final guard)
def test_replay_rows_db(db_conn):
    cur = db_conn.cursor()
    cur.execute("SELECT COUNT(*) FROM strategy_prediction_replays")
    rows = cur.fetchone()[0]
    assert rows == EXPECTED_REPLAY_ROWS, (
        f"DB replay_rows={rows}, expected {EXPECTED_REPLAY_ROWS}"
    )


# 12. Operator recommendation is HOLD (stable state)
def test_operator_recommendation(snapshot_json, snapshot_md):
    assert snapshot_json["operator_recommendation"] == "HOLD"
    actions = snapshot_json["operator_actions"]
    assert actions["recommendation"] == "HOLD"
    assert "HOLD" in snapshot_md or "hold" in snapshot_md.lower()
