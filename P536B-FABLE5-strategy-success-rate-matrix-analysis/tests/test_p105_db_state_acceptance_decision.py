"""
P105 DB State Acceptance Decision — Test Suite
===============================================
Validates the P105 governance artifact (JSON + MD) and DB invariants.

Focused suite — does NOT modify P98-P103 stale tests (known debt, P107 scope).
"""

import json
import os
import sqlite3
import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSON_PATH = os.path.join(REPO_ROOT, "outputs", "replay",
                         "p105_db_state_acceptance_decision_20260527.json")
MD_PATH = os.path.join(REPO_ROOT, "docs", "replay",
                       "p105_db_state_acceptance_decision_20260527.md")
DB_PATH = os.path.join(REPO_ROOT, "lottery_api", "data", "lottery_v2.db")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def artifact():
    with open(JSON_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def db_conn():
    conn = sqlite3.connect(DB_PATH)
    yield conn
    conn.close()


# ---------------------------------------------------------------------------
# Artifact existence
# ---------------------------------------------------------------------------

def test_json_artifact_exists():
    assert os.path.isfile(JSON_PATH), f"JSON artifact missing: {JSON_PATH}"


def test_json_artifact_is_valid_json():
    with open(JSON_PATH, encoding="utf-8") as f:
        data = json.load(f)
    assert isinstance(data, dict)


def test_md_artifact_exists():
    assert os.path.isfile(MD_PATH), f"MD artifact missing: {MD_PATH}"


# ---------------------------------------------------------------------------
# Classification and option
# ---------------------------------------------------------------------------

def test_classification(artifact):
    assert artifact["classification"] == "P105_DB_STATE_ACCEPTED_FOR_SPECIAL3_EVALUATION_ONLY"


def test_selected_option(artifact):
    assert artifact["selected_option"] == "A"


def test_user_input_verbatim(artifact):
    assert artifact["user_input_verbatim"] == "A-"


# ---------------------------------------------------------------------------
# P104 traceability
# ---------------------------------------------------------------------------

def test_p104_pr_number(artifact):
    assert artifact["p104_input_summary"]["pr_number"] == 233


def test_p104_merge_commit_exact(artifact):
    assert artifact["p104_input_summary"]["merge_commit"] == "cf8db28710c7fb000435c005a9db7b4f3de2e4b2"


def test_p104_merge_commit_short_prefix(artifact):
    assert artifact["p104_input_summary"]["merge_commit"].startswith("cf8db28")


# ---------------------------------------------------------------------------
# Authorization table
# ---------------------------------------------------------------------------

def test_authorize_p106_special3_evaluation(artifact):
    assert artifact["authorize"]["p106_special3_evaluation"] is True


def test_authorize_four_star_backtest_false(artifact):
    assert artifact["authorize"]["four_star_backtest"] is False


def test_authorize_special3_production_promotion_false(artifact):
    assert artifact["authorize"]["special3_production_promotion"] is False


def test_authorize_db_write_false(artifact):
    assert artifact["authorize"]["db_write"] is False


def test_authorize_db_stage_false(artifact):
    assert artifact["authorize"]["db_stage"] is False


def test_authorize_lifecycle_mutation_false(artifact):
    assert artifact["authorize"]["lifecycle_mutation"] is False


# ---------------------------------------------------------------------------
# Governance clauses
# ---------------------------------------------------------------------------

def test_never_again_clause_present_and_nonempty(artifact):
    clause = artifact.get("never_again_clause", "")
    assert isinstance(clause, str) and len(clause) > 0, "never_again_clause must be a non-empty string"


def test_source_unknown_caveat_present_and_nonempty(artifact):
    caveat = artifact.get("source_unknown_caveat", "")
    assert isinstance(caveat, str) and len(caveat) > 0, "source_unknown_caveat must be a non-empty string"


# ---------------------------------------------------------------------------
# DB invariants
# ---------------------------------------------------------------------------

def test_replay_rows(db_conn):
    row = db_conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()
    assert row[0] == 54462, f"Expected 54462 replay rows, got {row[0]}"


def test_3_star_count(db_conn):
    row = db_conn.execute(
        "SELECT COUNT(*) FROM draws WHERE lottery_type='3_STAR'"
    ).fetchone()
    assert row[0] == 4179, f"Expected 4179 3_STAR rows, got {row[0]}"


def test_4_star_count(db_conn):
    row = db_conn.execute(
        "SELECT COUNT(*) FROM draws WHERE lottery_type='4_STAR'"
    ).fetchone()
    assert row[0] == 2922, f"Expected 2922 4_STAR rows, got {row[0]}"


def test_power_lotto_max_draw(db_conn):
    row = db_conn.execute(
        "SELECT MAX(CAST(draw AS INTEGER)) FROM draws WHERE lottery_type='POWER_LOTTO'"
    ).fetchone()
    assert row[0] == 115000041, f"Expected POWER_LOTTO max_draw=115000041, got {row[0]}"


def test_3_star_max_draw(db_conn):
    row = db_conn.execute(
        "SELECT MAX(CAST(draw AS INTEGER)) FROM draws WHERE lottery_type='3_STAR'"
    ).fetchone()
    assert row[0] == 115000106, f"Expected 3_STAR max_draw=115000106, got {row[0]}"


def test_4_star_max_draw(db_conn):
    row = db_conn.execute(
        "SELECT MAX(CAST(draw AS INTEGER)) FROM draws WHERE lottery_type='4_STAR'"
    ).fetchone()
    assert row[0] == 115000103, f"Expected 4_STAR max_draw=115000103, got {row[0]}"


# ---------------------------------------------------------------------------
# MD content spot-checks
# ---------------------------------------------------------------------------

def test_md_contains_project_context_lock():
    with open(MD_PATH, encoding="utf-8") as f:
        content = f.read()
    assert "PROJECT_CONTEXT_LOCK" in content


def test_md_contains_never_again_clause():
    with open(MD_PATH, encoding="utf-8") as f:
        content = f.read()
    assert "NEVER AGAIN" in content


def test_md_contains_user_input_verbatim():
    with open(MD_PATH, encoding="utf-8") as f:
        content = f.read()
    assert "A-" in content


def test_md_contains_option_a_interpretation():
    with open(MD_PATH, encoding="utf-8") as f:
        content = f.read()
    assert "Option A" in content


def test_md_contains_source_unknown_caveat():
    with open(MD_PATH, encoding="utf-8") as f:
        content = f.read()
    assert "source-unknown" in content.lower() or "SOURCE_UNKNOWN" in content


def test_md_contains_p106_next_action():
    with open(MD_PATH, encoding="utf-8") as f:
        content = f.read()
    assert "P106" in content or "P1.1" in content


def test_md_contains_p107_next_action():
    with open(MD_PATH, encoding="utf-8") as f:
        content = f.read()
    assert "P107" in content or "P0.2" in content


def test_md_contains_p1_2_next_action():
    with open(MD_PATH, encoding="utf-8") as f:
        content = f.read()
    assert "P1.2" in content


def test_md_contains_p1_4_next_action():
    with open(MD_PATH, encoding="utf-8") as f:
        content = f.read()
    assert "P1.4" in content


def test_md_contains_final_classification():
    with open(MD_PATH, encoding="utf-8") as f:
        content = f.read()
    assert "P105_DB_STATE_ACCEPTED_FOR_SPECIAL3_EVALUATION_ONLY" in content


# ---------------------------------------------------------------------------
# Preflight snapshot in JSON
# ---------------------------------------------------------------------------

def test_json_preflight_replay_rows(artifact):
    assert artifact["preflight"]["replay_rows"] == 54462


def test_json_preflight_3_star_count(artifact):
    assert artifact["preflight"]["per_lottery"]["3_STAR"]["count"] == 4179


def test_json_preflight_3_star_max_draw(artifact):
    assert artifact["preflight"]["per_lottery"]["3_STAR"]["max_draw"] == 115000106


def test_json_preflight_4_star_count(artifact):
    assert artifact["preflight"]["per_lottery"]["4_STAR"]["count"] == 2922


def test_json_preflight_4_star_max_draw(artifact):
    assert artifact["preflight"]["per_lottery"]["4_STAR"]["max_draw"] == 115000103


def test_json_preflight_power_lotto_max_draw(artifact):
    assert artifact["preflight"]["per_lottery"]["POWER_LOTTO"]["max_draw"] == 115000041
