"""
P83 Stable-Baseline Closure Test Suite
Tests: 20 tests — artifact existence, DB baseline, phase evidence, guard references,
       risk register, launch-readiness checklist, browser E2E flag, no-DB-write guard.
"""

import json
import os
import sqlite3
import subprocess
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSON_ARTIFACT = os.path.join(REPO_ROOT, "outputs", "replay", "p83_stable_baseline_closure_20260526.json")
MD_ARTIFACT = os.path.join(REPO_ROOT, "docs", "replay", "p83_stable_baseline_closure_20260526.md")
DB_PATH = os.path.join(REPO_ROOT, "lottery_api", "data", "lottery_v2.db")


@pytest.fixture(scope="session")
def artifact():
    with open(JSON_ARTIFACT) as f:
        return json.load(f)


@pytest.fixture(scope="session")
def md_content():
    with open(MD_ARTIFACT) as f:
        return f.read()


@pytest.fixture(scope="session")
def db():
    conn = sqlite3.connect(DB_PATH)
    yield conn
    conn.close()


# ── 1. Artifact existence ────────────────────────────────────────────────────

def test_01_json_artifact_exists():
    assert os.path.exists(JSON_ARTIFACT), f"Missing: {JSON_ARTIFACT}"


def test_02_md_artifact_exists():
    assert os.path.exists(MD_ARTIFACT), f"Missing: {MD_ARTIFACT}"


# ── 2. JSON top-level classification ────────────────────────────────────────

def test_03_json_classification(artifact):
    assert artifact["classification"] == "P83_STABLE_BASELINE_CLOSURE_VERIFIED"


def test_04_no_db_writes_flag(artifact):
    assert artifact["db_writes"] is False
    assert artifact["replay_rows_inserted"] == 0
    assert artifact["ingestion_performed"] is False


# ── 3. Baseline metrics ──────────────────────────────────────────────────────

def test_05_replay_rows_46962(artifact):
    assert artifact["baseline_metrics"]["replay_rows"] == 46962


def test_06_max_draw_115000041(artifact):
    assert artifact["baseline_metrics"]["power_lotto_max_draw"] == 115000041


def test_07_batch_a_coverage_100pct(artifact):
    assert artifact["baseline_metrics"]["batch_a_coverage_pct"] == 100.0


def test_08_p79_sentinel_ids(artifact):
    sentinels = {r["id"]: r for r in artifact["baseline_metrics"]["p79_sentinel_rows"]}
    assert 46961 in sentinels
    assert 46962 in sentinels
    assert sentinels[46961]["dry_run"] == 0
    assert sentinels[46962]["dry_run"] == 0
    assert sentinels[46961]["truth_level"] == "POWERLOTTO_DRAW_EXT_VERIFIED"
    assert sentinels[46962]["truth_level"] == "POWERLOTTO_DRAW_EXT_VERIFIED"


# ── 4. DB live verification ──────────────────────────────────────────────────

def test_09_db_replay_rows_match(db):
    cur = db.cursor()
    cur.execute("SELECT COUNT(*) FROM strategy_prediction_replays")
    assert cur.fetchone()[0] == 46962


def test_10_db_max_draw_match(db):
    cur = db.cursor()
    cur.execute("SELECT MAX(CAST(draw AS INTEGER)) FROM draws WHERE lottery_type='POWER_LOTTO'")
    assert cur.fetchone()[0] == 115000041


def test_11_db_p79_rows_exist(db):
    cur = db.cursor()
    for rid in (46961, 46962):
        cur.execute(
            "SELECT dry_run, truth_level FROM strategy_prediction_replays WHERE id=?", (rid,)
        )
        row = cur.fetchone()
        assert row is not None, f"Row id={rid} missing"
        assert row[0] == 0, f"Row id={rid} dry_run != 0"
        assert row[1] == "POWERLOTTO_DRAW_EXT_VERIFIED"


# ── 5. Phase evidence completeness ──────────────────────────────────────────

def test_12_phase_evidence_includes_p77c_to_p82(artifact):
    phases = {e["phase"] for e in artifact["phase_evidence"]}
    for expected in ("P77C", "P78", "P79", "P80", "P81", "P82"):
        assert expected in phases, f"Phase {expected} missing from evidence"


def test_13_p82_freshness_pass_referenced(artifact):
    p82 = next(e for e in artifact["phase_evidence"] if e["phase"] == "P82")
    assert p82["key_metrics"]["guard_classification"] == "FRESHNESS_PASS"


# ── 6. Launch-readiness checklist ───────────────────────────────────────────

def test_14_launch_readiness_checklist_exists(artifact):
    checklist = artifact["launch_readiness_checklist"]
    assert isinstance(checklist, list)
    assert len(checklist) >= 6


def test_15_launch_readiness_core_items_pass(artifact):
    checklist = {item["item"]: item for item in artifact["launch_readiness_checklist"]}
    required_pass = [
        "source_recovery_complete",
        "draw_freshness_verified",
        "replay_rows_applied",
        "api_visibility_verified",
        "monitoring_scoring_path_verified",
        "freshness_guard_added",
    ]
    for item in required_pass:
        assert item in checklist, f"Checklist item '{item}' missing"
        assert checklist[item]["status"] == "PASS", f"'{item}' not PASS: {checklist[item]['status']}"


# ── 7. Browser E2E — must be FLAKY, never PASS ──────────────────────────────

def test_16_browser_e2e_not_marked_pass(artifact):
    assert artifact["browser_e2e_status"] != "PASS"
    # Must be FLAKY or FAILURE
    assert artifact["browser_e2e_status"] in ("FLAKY", "FAILURE", "NOT_RUN")


def test_17_browser_e2e_checklist_not_pass(artifact):
    checklist = {item["item"]: item for item in artifact["launch_readiness_checklist"]}
    if "browser_e2e" in checklist:
        assert checklist["browser_e2e"]["status"] != "PASS"


# ── 8. Risk register ────────────────────────────────────────────────────────

def test_18_risk_register_exists(artifact):
    assert "risk_register" in artifact
    assert len(artifact["risk_register"]) >= 3


# ── 9. No forbidden DB-write instructions in MD ────────────────────────────

def test_19_no_db_write_instructions_in_md(md_content):
    forbidden_patterns = [
        "INSERT INTO strategy_prediction_replays",
        "DROP TABLE",
        "DELETE FROM strategy_prediction_replays",
        "git reset --hard",
    ]
    for pattern in forbidden_patterns:
        assert pattern not in md_content, f"Forbidden pattern found in MD: '{pattern}'"


# ── 10. Guard results in JSON ───────────────────────────────────────────────

def test_20_guard_results_all_pass(artifact):
    guards = artifact["guard_results"]
    assert guards["p82_freshness_guard"] == "FRESHNESS_PASS"
    assert guards["drift_guard"] == "REPLAY_LIFECYCLE_DRIFT_GUARD_PASS"
    assert guards["branch_governance"] == "BRANCH_GOVERNANCE_PASS"
    assert guards["forbidden_staging_scan"] == "CLEAN"
