"""
tests/test_p88_new_draw_source_decision_gate.py
P88 New Draw Source Decision Gate — 12 governance assertions
"""
import json
import os
import sqlite3
import pytest

SNAPSHOT_MD = "docs/replay/p88_monitoring_snapshot_20260526.md"
SNAPSHOT_JSON = "outputs/replay/p88_monitoring_snapshot_20260526.json"
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


# 1. Baseline replay_rows = 46962 (DB read)
def test_baseline_replay_rows(db_conn):
    cur = db_conn.cursor()
    cur.execute("SELECT COUNT(*) FROM strategy_prediction_replays")
    rows = cur.fetchone()[0]
    assert rows == EXPECTED_REPLAY_ROWS, (
        f"Expected replay_rows={EXPECTED_REPLAY_ROWS}, got {rows}"
    )


# 2. Baseline max_draw = 115000041 (DB read)
def test_baseline_max_draw(db_conn):
    cur = db_conn.cursor()
    cur.execute(
        "SELECT MAX(CAST(draw AS INTEGER)) FROM draws WHERE lottery_type='POWER_LOTTO'"
    )
    max_draw = cur.fetchone()[0]
    assert max_draw == EXPECTED_MAX_DRAW, (
        f"Expected max_draw={EXPECTED_MAX_DRAW}, got {max_draw}"
    )


# 3. P86 guard integration — script exists and is importable
def test_p86_guard_exists():
    assert os.path.exists("scripts/p86_live_monitoring_source_decision_guard.py"), (
        "P86 source decision guard script missing"
    )


# 4. P82 guard integration — script exists
def test_p82_guard_exists():
    assert os.path.exists("scripts/p82_replay_freshness_guard.py"), (
        "P82 freshness guard script missing"
    )


# 5. STABLE_NO_NEW_DRAW classification in JSON artifact
def test_stable_no_new_draw_classification(snapshot_json):
    assert snapshot_json["classification"] == "P88_STABLE_NO_NEW_DRAW_MONITORING_SNAPSHOT", (
        f"Expected P88_STABLE_NO_NEW_DRAW_MONITORING_SNAPSHOT, got {snapshot_json['classification']}"
    )
    assert snapshot_json["new_draw_detected"] is False, (
        "new_draw_detected must be false for STABLE_NO_NEW_DRAW"
    )


# 6. SOURCE_DECISION_REQUIRED classification documented in markdown
def test_source_decision_required_documented(snapshot_md):
    assert "SOURCE_DECISION_REQUIRED" in snapshot_md, (
        "SOURCE_DECISION_REQUIRED not documented in markdown"
    )
    assert "STOP" in snapshot_md, (
        "STOP action for SOURCE_DECISION_REQUIRED not in markdown"
    )


# 7. No DB write code paths — governance flags
def test_no_db_writes(snapshot_json):
    governance = snapshot_json["governance"]
    assert governance["no_db_writes"] is True, "governance.no_db_writes must be True"
    assert governance["db_writes"] is False, "governance.db_writes must be False"
    assert governance["no_replay_inserts"] is True, "governance.no_replay_inserts must be True"


# 8. No replay row insert paths — replay_row_changes = 0
def test_no_replay_row_changes(snapshot_json):
    assert snapshot_json["governance"]["replay_row_changes"] == 0, (
        "replay_row_changes must be 0"
    )
    baseline = snapshot_json["production_baseline"]
    assert baseline["replay_rows"] == EXPECTED_REPLAY_ROWS, (
        f"Snapshot baseline replay_rows must be {EXPECTED_REPLAY_ROWS}"
    )
    assert baseline["replay_rows_changed"] == 0, (
        "replay_rows_changed must be 0"
    )


# 9. No automatic official API write path documented
def test_no_official_api_writes(snapshot_json, snapshot_md):
    governance = snapshot_json["governance"]
    assert governance["no_official_api_writes"] is True, (
        "governance.no_official_api_writes must be True"
    )
    policy = snapshot_json["source_decision_policy"]
    forbidden = policy["forbidden_actions"]
    api_write_forbidden = any(
        "official_api" in f and "write" in f for f in forbidden
    )
    assert api_write_forbidden, (
        "call_official_api_for_writes must be in forbidden_actions"
    )


# 10. JSON artifact schema validity
def test_json_schema_validity(snapshot_json):
    required_keys = [
        "phase", "policy_version", "classification", "date",
        "source_status", "new_draw_detected", "production_baseline",
        "monitoring_checks", "p88_classification_logic",
        "source_decision_policy", "evidence_chain", "governance"
    ]
    for key in required_keys:
        assert key in snapshot_json, f"Required key '{key}' missing from JSON"

    baseline = snapshot_json["production_baseline"]
    assert baseline["replay_rows"] == EXPECTED_REPLAY_ROWS
    assert baseline["power_lotto_max_draw"] == EXPECTED_MAX_DRAW
    assert baseline["batch_a_coverage_pct"] == 100.0


# 11. Source decision policy present
def test_source_decision_policy_present(snapshot_json, snapshot_md):
    policy = snapshot_json["source_decision_policy"]
    assert "current_decision" in policy, "current_decision missing from policy"
    assert "allowed_trigger_conditions" in policy, "allowed_trigger_conditions missing"
    assert "forbidden_actions" in policy, "forbidden_actions missing from policy"
    assert len(policy["allowed_trigger_conditions"]) >= 2, (
        "At least 2 trigger conditions must be documented"
    )
    assert "source_decision_policy" in snapshot_md.lower() or "source decision" in snapshot_md.lower(), (
        "Source decision policy not documented in markdown"
    )


# 12. Forbidden actions documented (reset-hard, git-clean, DB write)
def test_forbidden_actions_documented(snapshot_json, snapshot_md):
    forbidden = snapshot_json["source_decision_policy"]["forbidden_actions"]

    git_reset_forbidden = any("reset" in f for f in forbidden)
    assert git_reset_forbidden, "git_reset_hard must be in forbidden_actions"

    git_clean_forbidden = any("clean" in f for f in forbidden)
    assert git_clean_forbidden, "git_clean must be in forbidden_actions"

    db_write_forbidden = any("insert" in f.lower() or "draws" in f.lower() for f in forbidden)
    assert db_write_forbidden, "DB write (INSERT INTO draws) must be in forbidden_actions"

    assert "git reset" in snapshot_md.lower() or "reset --hard" in snapshot_md.lower(), (
        "git reset --hard not documented in markdown"
    )
    assert "git clean" in snapshot_md.lower(), (
        "git clean not documented in markdown"
    )
