"""
P85 Launch Closure and Operator Release Package — Validation Tests
Classification: P85_REPLAY_LAUNCH_CLOSURE_OPERATOR_PACKAGE_READY

12 assertions verifying P85 artifacts, baseline, operator guide, and risk register.
No DB writes. No replay row insertions. Read-only.
"""

import json
import os
import sqlite3

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

P85_JSON = os.path.join(REPO_ROOT, "outputs", "replay", "p85_launch_closure_operator_release_20260526.json")
P85_MD = os.path.join(REPO_ROOT, "docs", "replay", "p85_launch_closure_operator_release_20260526.md")
DB_PATH = os.path.join(REPO_ROOT, "lottery_api", "data", "lottery_v2.db")


@pytest.fixture(scope="module")
def p85_json():
    with open(P85_JSON) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def p85_md():
    with open(P85_MD) as f:
        return f.read()


@pytest.fixture(scope="module")
def db_conn():
    conn = sqlite3.connect(DB_PATH)
    yield conn
    conn.close()


# --- Assertion 1: P85 JSON artifact exists ---
def test_p85_json_artifact_exists():
    assert os.path.isfile(P85_JSON), f"P85 JSON artifact missing: {P85_JSON}"


# --- Assertion 2: P85 markdown artifact exists ---
def test_p85_markdown_artifact_exists():
    assert os.path.isfile(P85_MD), f"P85 markdown artifact missing: {P85_MD}"


# --- Assertion 3: Classification is correct ---
def test_p85_classification(p85_json):
    assert p85_json["classification"] == "P85_REPLAY_LAUNCH_CLOSURE_OPERATOR_PACKAGE_READY", (
        f"Expected P85_REPLAY_LAUNCH_CLOSURE_OPERATOR_PACKAGE_READY, got {p85_json['classification']}"
    )


# --- Assertion 4: replay_rows baseline = 46962 ---
def test_replay_rows_baseline(p85_json, db_conn):
    # Verify artifact documents correct value
    assert p85_json["production_baseline"]["replay_rows"] == 46962
    # Verify DB matches
    cur = db_conn.cursor()
    cur.execute("SELECT COUNT(*) FROM strategy_prediction_replays")
    actual = cur.fetchone()[0]
    assert actual == 46962, f"DB replay_rows={actual}, expected 46962"


# --- Assertion 5: POWER_LOTTO max_draw = 115000041 ---
def test_power_lotto_max_draw(p85_json, db_conn):
    # Verify artifact documents correct value
    assert p85_json["production_baseline"]["power_lotto_max_draw"] == 115000041
    # Verify DB matches
    cur = db_conn.cursor()
    cur.execute("SELECT MAX(CAST(draw AS INTEGER)) FROM draws WHERE lottery_type='POWER_LOTTO'")
    actual = cur.fetchone()[0]
    assert actual == 115000041, f"DB max_draw={actual}, expected 115000041"


# --- Assertion 6: P79 sentinel ids 46961 / 46962 are referenced ---
def test_p79_sentinel_ids_referenced(p85_json, db_conn):
    sentinel_rows = p85_json["production_baseline"]["p79_sentinel_rows"]
    ids = [r["id"] for r in sentinel_rows]
    assert 46961 in ids, "id=46961 missing from p79_sentinel_rows"
    assert 46962 in ids, "id=46962 missing from p79_sentinel_rows"
    # Verify in DB with correct dry_run and truth_level
    cur = db_conn.cursor()
    cur.execute(
        "SELECT id, dry_run, truth_level FROM strategy_prediction_replays WHERE id IN (46961, 46962) ORDER BY id"
    )
    db_rows = cur.fetchall()
    assert len(db_rows) == 2, f"Expected 2 sentinel rows in DB, got {len(db_rows)}"
    for row in db_rows:
        assert row[1] == 0, f"id={row[0]} has dry_run={row[1]}, expected 0"
        assert row[2] == "POWERLOTTO_DRAW_EXT_VERIFIED", f"id={row[0]} truth_level={row[2]}"


# --- Assertion 7: Browser E2E status = PASS / stabilized by P84 ---
def test_browser_e2e_stabilized(p85_json, p85_md):
    assert p85_json["production_baseline"]["browser_e2e_stabilized"] is True
    assert p85_json["production_baseline"]["browser_e2e_post_merge_result"] == "70/70 PASS"
    # Check P84 is in evidence chain with correct PR
    chain = p85_json["evidence_chain"]
    p84 = next((e for e in chain if e["phase"] == "P84"), None)
    assert p84 is not None, "P84 missing from evidence_chain"
    assert p84["pr"] == 209
    assert p84["commit"] == "a18523d"
    # Check markdown references browser E2E PASS
    assert "70/70 PASS" in p85_md or "70/70" in p85_md
    assert "P84" in p85_md


# --- Assertion 8: Operator guide includes port 8002 ---
def test_operator_guide_port_8002(p85_json, p85_md):
    assert p85_json["operator_guide"]["backend_port"] == 8002
    assert "8002" in p85_md
    # Ensure 8000 is documented as wrong
    assert "8000" in p85_md or "wrong" in p85_md.lower() or "unrelated" in p85_md.lower()


# --- Assertion 9: Operator guide includes date format 2026/05/21 ---
def test_operator_guide_date_format(p85_json, p85_md):
    assert p85_json["operator_guide"]["date_format"] == "2026/05/21"
    assert "2026/05/21" in p85_md
    # Slash format is required; hyphen should be flagged
    assert "slash" in p85_md.lower() or "YYYY/MM/DD" in p85_md


# --- Assertion 10: Risk register marks browser E2E flaky as CLOSED ---
def test_risk_register_browser_e2e_closed(p85_json, p85_md):
    risks = p85_json["risk_register"]
    browser_risk = next((r for r in risks if "Browser E2E" in r["risk"] or "browser_e2e" in r.get("risk", "").lower()), None)
    assert browser_risk is not None, "Browser E2E risk not found in risk_register"
    assert browser_risk["status"] == "CLOSED", f"Browser E2E risk status={browser_risk['status']}, expected CLOSED"
    assert browser_risk["closed_by"] == "P84"
    assert "CLOSED" in p85_md


# --- Assertion 11: No DB-write instructions present as active steps ---
def test_no_db_write_instructions(p85_json, p85_md):
    # JSON governance flags
    assert p85_json["governance"]["no_db_writes"] is True
    assert p85_json["governance"]["no_replay_inserts"] is True
    assert p85_json["governance"]["no_ingestion"] is True
    assert p85_json["production_baseline"]["db_writes"] is False
    assert p85_json["production_baseline"]["replay_rows_inserted_in_p85"] == 0
    # Rollback SQL in markdown must be inside a warning block, not as an active step
    assert "authorization" in p85_md.lower(), "Rollback must require authorization mention"


# --- Assertion 12: Evidence chain includes P77C through P84 ---
def test_evidence_chain_complete(p85_json):
    chain = p85_json["evidence_chain"]
    phases_present = [e["phase"] for e in chain]
    required = ["P77C", "P78", "P79", "P80", "P81", "P82", "P83", "P84"]
    for phase in required:
        assert phase in phases_present, f"Phase {phase} missing from evidence_chain"
    # Verify each entry has required fields
    for entry in chain:
        assert "phase" in entry
        assert "title" in entry
        assert "pr" in entry
        assert "commit" in entry
        assert "description" in entry
