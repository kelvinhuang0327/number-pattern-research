"""
P86 Live Monitoring / Source Decision Guard — Validation Tests
Classification: P86_LIVE_MONITORING_SOURCE_DECISION_GUARD_READY

10 assertions verifying monitoring logic, DB safety, and governance.
No DB writes. No replay row insertions. Read-only.
"""

import json
import os
import sqlite3
import tempfile

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(REPO_ROOT, "lottery_api", "data", "lottery_v2.db")
P86_JSON = os.path.join(
    REPO_ROOT, "outputs", "replay", "p86_live_monitoring_source_decision_guard_20260526.json"
)
P86_MD = os.path.join(
    REPO_ROOT, "docs", "replay", "p86_live_monitoring_source_decision_guard_20260526.md"
)
P86_SCRIPT = os.path.join(REPO_ROOT, "scripts", "p86_live_monitoring_source_decision_guard.py")

# Import the guard module directly for unit testing
import importlib.util

spec = importlib.util.spec_from_file_location("p86_guard", P86_SCRIPT)
_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(_mod)


@pytest.fixture(scope="module")
def p86_json():
    with open(P86_JSON) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def p86_md():
    with open(P86_MD) as f:
        return f.read()


# --- Assertion 1: DB max draw = 115000041 ---
def test_baseline_db_max_draw():
    con = sqlite3.connect(DB_PATH)
    try:
        cur = con.cursor()
        cur.execute(
            "SELECT MAX(CAST(draw AS INTEGER)) FROM draws WHERE lottery_type='POWER_LOTTO'"
        )
        actual = cur.fetchone()[0]
    finally:
        con.close()
    assert actual == 115000041, f"DB max_draw={actual}, expected 115000041"


# --- Assertion 2: STABLE_NO_NEW_DRAW when source == DB ---
def test_classify_stable_no_new_draw():
    result = _mod.classify(db_max=115000041, source_max=115000041)
    assert result == _mod.CLASSIFICATION_STABLE, f"Expected STABLE_NO_NEW_DRAW, got {result}"


# --- Assertion 3: SOURCE_DECISION_REQUIRED when source > DB ---
def test_classify_source_decision_required():
    result = _mod.classify(db_max=115000041, source_max=115000042)
    assert result == _mod.CLASSIFICATION_DECISION_REQUIRED, (
        f"Expected SOURCE_DECISION_REQUIRED, got {result}"
    )


# --- Assertion 4: SOURCE_STALE when source < DB ---
def test_classify_source_stale():
    result = _mod.classify(db_max=115000041, source_max=115000040)
    assert result == _mod.CLASSIFICATION_STALE, f"Expected SOURCE_STALE, got {result}"


# --- Assertion 5: SOURCE_UNAVAILABLE when no source provided ---
def test_classify_source_unavailable():
    result = _mod.classify(db_max=115000041, source_max=None)
    assert result == _mod.CLASSIFICATION_UNAVAILABLE, (
        f"Expected SOURCE_UNAVAILABLE, got {result}"
    )


# --- Assertion 6: run() produces no DB writes ---
def test_run_no_db_writes():
    """run() must not write to DB: replay_rows must remain 46962."""
    # Count before
    con = sqlite3.connect(DB_PATH)
    try:
        cur = con.cursor()
        cur.execute("SELECT COUNT(*) FROM strategy_prediction_replays")
        before = cur.fetchone()[0]
    finally:
        con.close()

    _mod.run()

    # Count after
    con = sqlite3.connect(DB_PATH)
    try:
        cur = con.cursor()
        cur.execute("SELECT COUNT(*) FROM strategy_prediction_replays")
        after = cur.fetchone()[0]
    finally:
        con.close()

    assert after == before == 46962, f"replay_rows changed: before={before}, after={after}"


# --- Assertion 7: run() reports no replay inserts ---
def test_run_reports_zero_replay_inserts():
    result = _mod.run()
    assert result["db"]["replay_rows_inserted"] == 0
    assert result["db"]["db_writes"] is False


# --- Assertion 8: governance block is correct ---
def test_governance_flags(p86_json):
    gov = p86_json["governance"]
    assert gov["no_db_writes"] is True
    assert gov["no_replay_inserts"] is True
    assert gov["no_official_api_writes"] is True
    assert gov["no_new_tables"] is True
    assert gov["no_ingestion"] is True
    assert gov["read_only"] is True


# --- Assertion 9: JSON schema validity ---
def test_p86_json_schema(p86_json):
    required_top = {"phase", "policy_version", "classification", "as_of", "db", "source", "policy", "governance"}
    assert required_top.issubset(p86_json.keys()), f"Missing keys: {required_top - p86_json.keys()}"
    assert p86_json["phase"] == "P86"
    assert p86_json["policy_version"] == "p86-v1"
    assert p86_json["db"]["max_draw"] == 115000041
    assert p86_json["db"]["replay_rows"] == 46962
    assert p86_json["classification"] in {
        "STABLE_NO_NEW_DRAW",
        "SOURCE_DECISION_REQUIRED",
        "SOURCE_STALE",
        "SOURCE_UNAVAILABLE",
    }
    # forbidden_automatic_behavior must list all 4 forbidden items
    forbidden = p86_json["policy"]["forbidden_automatic_behavior"]
    assert "auto_db_insert" in forbidden
    assert "auto_replay_apply" in forbidden
    assert "fallback_to_official_api_without_explicit_decision" in forbidden
    assert "new_staging_table_creation" in forbidden


# --- Assertion 10: P82 guard compatibility — freshness guard still passes ---
def test_p82_guard_compatibility():
    """
    P86 must not break P82 freshness guard.
    We verify by importing and calling the P82 guard read path.
    """
    p82_script = os.path.join(REPO_ROOT, "scripts", "p82_replay_freshness_guard.py")
    assert os.path.isfile(p82_script), "P82 freshness guard script missing"

    spec = importlib.util.spec_from_file_location("p82_guard", p82_script)
    p82 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(p82)

    # P82 should report FRESHNESS_PASS for POWER_LOTTO
    # We verify it doesn't raise and returns a meaningful result
    # (calling via subprocess to avoid global state collisions)
    import subprocess
    result = subprocess.run(
        [os.path.join(REPO_ROOT, ".venv", "bin", "python"),
         p82_script, "--lottery", "POWER_LOTTO"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert "FRESHNESS_PASS" in result.stdout, (
        f"P82 did not return FRESHNESS_PASS. stdout={result.stdout!r}"
    )


# --- Assertion 11: source snapshot round-trip (STABLE) ---
def test_source_snapshot_stable():
    """Write a temp snapshot with source_max == DB max, expect STABLE_NO_NEW_DRAW."""
    snapshot = {
        "lottery_type": "POWER_LOTTO",
        "max_draw": 115000041,
        "source": "operator_upload",
        "as_of": "2026-05-26",
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(snapshot, f)
        tmp_path = f.name
    try:
        result = _mod.run(source_snapshot_path=tmp_path)
        assert result["classification"] == _mod.CLASSIFICATION_STABLE
    finally:
        os.unlink(tmp_path)


# --- Assertion 12: source snapshot round-trip (SOURCE_DECISION_REQUIRED) ---
def test_source_snapshot_decision_required():
    """Write a temp snapshot with source_max > DB max, expect SOURCE_DECISION_REQUIRED."""
    snapshot = {
        "lottery_type": "POWER_LOTTO",
        "max_draw": 115000042,
        "source": "operator_upload",
        "as_of": "2026-05-27",
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(snapshot, f)
        tmp_path = f.name
    try:
        result = _mod.run(source_snapshot_path=tmp_path)
        assert result["classification"] == _mod.CLASSIFICATION_DECISION_REQUIRED
        # Verify allowed source decisions are enumerated
        assert "allowed_source_decisions" in result["policy"]
        decisions = result["policy"]["allowed_source_decisions"]
        assert "uploaded_source_provided_by_operator" in decisions
        assert "official_api_explicitly_authorized" in decisions
        assert "hold_no_action" in decisions
        assert "manual_verification_required" in decisions
    finally:
        os.unlink(tmp_path)
