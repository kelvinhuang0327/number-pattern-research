"""
tests/test_p90_operations_hold_baseline_archive.py
P90 Operations Hold Baseline Archive — 12 governance assertions
"""
import json
import os
import sqlite3
import pytest

ARCHIVE_JSON = "outputs/replay/p90_operations_hold_baseline_archive_20260526.json"
ARCHIVE_MD = "docs/replay/p90_operations_hold_baseline_archive_20260526.md"
DB_PATH = "lottery_api/data/lottery_v2.db"

EXPECTED_REPLAY_ROWS = 46962
EXPECTED_MAX_DRAW = 115000041
EXPECTED_PHASES = ["P83", "P84", "P85", "P86", "P87", "P88", "P89"]


@pytest.fixture(scope="module")
def archive_json():
    assert os.path.exists(ARCHIVE_JSON), f"JSON artifact missing: {ARCHIVE_JSON}"
    with open(ARCHIVE_JSON, encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="module")
def archive_md():
    assert os.path.exists(ARCHIVE_MD), f"Markdown artifact missing: {ARCHIVE_MD}"
    with open(ARCHIVE_MD, encoding="utf-8") as fh:
        return fh.read()


@pytest.fixture(scope="module")
def db_conn():
    assert os.path.exists(DB_PATH), f"DB not found: {DB_PATH}"
    con = sqlite3.connect(DB_PATH)
    yield con
    con.close()


# 1. JSON artifact exists and is valid
def test_json_artifact_exists(archive_json):
    assert archive_json is not None
    assert isinstance(archive_json, dict)
    assert archive_json["phase"] == "P90"


# 2. Markdown artifact exists and is non-trivial
def test_markdown_artifact_exists(archive_md):
    assert len(archive_md) > 200


# 3. Classification is P90_OPERATIONS_HOLD_BASELINE_ARCHIVED
def test_classification(archive_json, archive_md):
    assert archive_json["classification"] == "P90_OPERATIONS_HOLD_BASELINE_ARCHIVED"
    assert archive_json["system_status"] == "STABLE"
    assert archive_json["launch_readiness"] == "READY"
    assert archive_json["immediate_development_action_required"] is False
    assert "P90_OPERATIONS_HOLD_BASELINE_ARCHIVED" in archive_md


# 4. replay_rows = 46962 (JSON)
def test_replay_rows_json(archive_json):
    baseline = archive_json["production_baseline"]
    assert baseline["replay_rows"] == EXPECTED_REPLAY_ROWS
    assert baseline["replay_rows_changed"] == 0


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


# 6. Phase ledger includes P83 through P89
def test_phase_ledger_complete(archive_json, archive_md):
    ledger = archive_json["phase_ledger"]
    for phase in EXPECTED_PHASES:
        assert phase in ledger, f"Phase {phase} missing from ledger"
        assert "classification" in ledger[phase]
        assert "pr" in ledger[phase]
        assert "commit" in ledger[phase]

    for phase in EXPECTED_PHASES:
        assert phase in archive_md, f"Phase {phase} missing from markdown"

    assert ledger["P89"]["pr"] == 214
    assert ledger["P89"]["commit"] == "c387c24"
    assert ledger["P88"]["pr"] == 213
    assert ledger["P88"]["commit"] == "d7a707f"


# 7. Operator recommendation = HOLD
def test_operator_recommendation(archive_json, archive_md):
    assert archive_json["operator_recommendation"] == "HOLD"
    assert archive_json["new_draw_detected"] is False
    assert archive_json["source_decision_required"] is False
    assert archive_json["operator_actions"]["recommendation"] == "HOLD"
    assert "HOLD" in archive_md


# 8. Future trigger policy exists with at least 6 triggers
def test_future_trigger_policy(archive_json, archive_md):
    policy = archive_json["future_trigger_policy"]
    assert "triggers" in policy
    assert len(policy["triggers"]) >= 6

    trigger_ids = [t["id"] for t in policy["triggers"]]
    for expected in ["T1", "T2", "T3", "T4", "T5", "T6"]:
        assert expected in trigger_ids, f"Trigger {expected} missing"

    classifications = policy["recommended_future_classifications"]
    assert "P91_SOURCE_DECISION_REQUIRED" in classifications
    assert "P91_CONTROLLED_DRAW_REFRESH_READY" in classifications
    assert "P91_BROWSER_REGRESSION_INVESTIGATION" in classifications

    assert "trigger" in archive_md.lower() or "p91" in archive_md.lower()


# 9. Forbidden DB writes documented in JSON and markdown
def test_forbidden_db_writes(archive_json, archive_md):
    governance = archive_json["governance"]
    assert governance["no_db_writes"] is True
    assert governance["db_writes"] is False
    assert governance["no_replay_inserts"] is True
    assert governance["replay_row_changes"] == 0
    assert governance["read_only"] is True

    forbidden = archive_json["operator_actions"]["forbidden_actions"]
    assert any("insert" in f.lower() or "draws" in f.lower() for f in forbidden)
    assert "forbidden" in archive_md.lower()


# 10. Future source decision risk documented
def test_source_decision_risk_documented(archive_json, archive_md):
    risks = archive_json["known_open_risks"]
    assert len(risks) >= 1
    risk_texts = [r["risk"].lower() for r in risks]
    assert any("draw" in r and "115000041" in r for r in risk_texts)

    md_lower = archive_md.lower()
    assert "risk" in md_lower or "source decision" in md_lower


# 11. replay_rows = 46962 (DB read — final guard)
def test_replay_rows_db(db_conn):
    cur = db_conn.cursor()
    cur.execute("SELECT COUNT(*) FROM strategy_prediction_replays")
    rows = cur.fetchone()[0]
    assert rows == EXPECTED_REPLAY_ROWS, (
        f"DB replay_rows={rows}, expected {EXPECTED_REPLAY_ROWS}"
    )


# 12. P79 sentinels intact in JSON and DB
def test_p79_sentinels_intact(archive_json, db_conn):
    sentinels = archive_json["production_baseline"]["p79_sentinels"]
    ids = [s["id"] for s in sentinels]
    assert 46961 in ids
    assert 46962 in ids

    cur = db_conn.cursor()
    cur.execute(
        "SELECT id, dry_run, truth_level FROM strategy_prediction_replays "
        "WHERE id IN (46961, 46962) ORDER BY id"
    )
    rows = cur.fetchall()
    assert len(rows) == 2
    for row in rows:
        assert row[1] == 0, f"Sentinel id={row[0]} dry_run={row[1]} expected 0"
        assert row[2] == "POWERLOTTO_DRAW_EXT_VERIFIED"
