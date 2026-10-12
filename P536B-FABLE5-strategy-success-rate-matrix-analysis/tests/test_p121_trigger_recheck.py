"""
Tests for P121: Trigger Recheck / Wait-State Confirmation
"""

import json
import re
import sqlite3
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
JSON_ARTIFACT = PROJECT_ROOT / "outputs" / "replay" / "p121_trigger_recheck_20260527.json"
MD_ARTIFACT = PROJECT_ROOT / "docs" / "replay" / "p121_trigger_recheck_20260527.md"
SCRIPT = PROJECT_ROOT / "scripts" / "p121_trigger_recheck.py"
DB_PATH = PROJECT_ROOT / "lottery_api" / "data" / "lottery_v2.db"

VALID_CLASSIFICATIONS = {
    "P121_ALL_TRIGGERS_STILL_BLOCKED",
    "P121_P108_TRIGGER_MET",
    "P121_P117_PARTIAL_TRIGGER_MET",
    "P121_P117_FULL_TRIGGER_MET",
    "P121_P118_AUTHORIZATION_PRESENT",
    "P121_4STAR_PROVENANCE_TRIGGER_MET",
    "P121_TRIGGER_RECHECK_INCONCLUSIVE",
    "P121_BLOCKED_BY_PREFLIGHT",
    "P121_BLOCKED_BY_DB_DRIFT",
    "P121_BLOCKED_BY_GUARD_FAILURE",
    "P121_BLOCKED_BY_TEST_FAILURE",
    "P121_BLOCKED_BY_FORBIDDEN_FILES_STAGED",
    "P121_BLOCKED_BY_SCOPE_VIOLATION",
    "P121_BLOCKED_BY_CONTEXT_CONTAMINATION",
}

FORBIDDEN_SQL_VERBS = [
    "INSERT", "UPDATE", "DELETE", "CREATE TABLE", "DROP", "ALTER TABLE",
    "REPLACE INTO", "VACUUM", "PRAGMA writable_schema",
]

REQUIRED_TRIGGERS = {
    "P108_SPECIAL3_100DRAW_REEVALUATION",
    "P117_POWERLOTTO_OOS_RETRIGGER",
    "P118_BIGLOTTO_ACTUAL_QUARANTINE",
    "P4STAR_PROVENANCE_AND_BACKTEST",
}


@pytest.fixture(scope="module")
def artifact():
    return json.loads(JSON_ARTIFACT.read_text())


@pytest.fixture(scope="module")
def md_text():
    return MD_ARTIFACT.read_text()


@pytest.fixture(scope="module")
def script_text():
    return SCRIPT.read_text()


# --- File existence ---

def test_json_artifact_exists():
    assert JSON_ARTIFACT.exists()


def test_md_artifact_exists():
    assert MD_ARTIFACT.exists()


def test_script_exists():
    assert SCRIPT.exists()


# --- JSON parses ---

def test_json_parses(artifact):
    assert isinstance(artifact, dict)


# --- Core fields ---

def test_task_id(artifact):
    assert artifact["task_id"] == "P121_TRIGGER_RECHECK"


def test_classification_valid(artifact):
    assert artifact["classification"] in VALID_CLASSIFICATIONS


def test_final_classification_valid(artifact):
    assert artifact["final_classification"] in VALID_CLASSIFICATIONS


def test_classification_matches_final(artifact):
    assert artifact["classification"] == artifact["final_classification"]


# --- P120 reference ---

def test_p120_reference_exists(artifact):
    assert "p120_reference" in artifact
    assert "classification" in artifact["p120_reference"]
    assert "artifact_path" in artifact["p120_reference"]


# --- Safety invariants ---

def test_db_writes_false(artifact):
    assert artifact["db_writes"] is False


def test_replay_rows_before(artifact):
    assert artifact["replay_rows_before"] == 54462


def test_replay_rows_after(artifact):
    assert artifact["replay_rows_after"] == 54462


def test_replay_rows_unchanged(artifact):
    assert artifact["replay_rows_before"] == artifact["replay_rows_after"]


def test_no_strategy_promotion(artifact):
    assert artifact["no_strategy_promotion"] is True


def test_no_lifecycle_mutation(artifact):
    assert artifact["no_lifecycle_mutation"] is True


def test_no_registry_mutation(artifact):
    assert artifact["no_registry_mutation"] is True


def test_no_actual_quarantine_applied(artifact):
    assert artifact["no_actual_quarantine_applied"] is True


def test_no_replay_row_delete(artifact):
    assert artifact["no_replay_row_delete"] is True


def test_no_4star_backtest(artifact):
    assert artifact["no_4star_backtest"] is True


def test_no_special3_p108_rerun(artifact):
    assert artifact["no_special3_p108_rerun"] is True


def test_no_powerlotto_oos_execution(artifact):
    assert artifact["no_powerlotto_oos_execution"] is True


def test_source_unknown_caveat_preserved(artifact):
    assert artifact["source_unknown_caveat_preserved"] is True


# --- DB snapshot ---

def test_current_db_snapshot_exists(artifact):
    assert "current_db_snapshot" in artifact


def test_db_snapshot_replay_rows(artifact):
    assert artifact["current_db_snapshot"]["replay_rows"] == 54462


# --- Trigger recheck ---

def test_trigger_recheck_exists(artifact):
    assert "trigger_recheck" in artifact
    assert isinstance(artifact["trigger_recheck"], dict)


@pytest.mark.parametrize("trigger", sorted(REQUIRED_TRIGGERS))
def test_trigger_recheck_includes_trigger(artifact, trigger):
    assert trigger in artifact["trigger_recheck"], f"Missing trigger: {trigger}"


def test_p108_current_count_nonnegative(artifact):
    assert artifact["trigger_recheck"]["P108_SPECIAL3_100DRAW_REEVALUATION"]["current_count_after_p99_cutoff"] >= 0


def test_p108_remaining_nonnegative(artifact):
    assert artifact["trigger_recheck"]["P108_SPECIAL3_100DRAW_REEVALUATION"]["remaining_needed"] >= 0


def test_p117_current_new_draws_nonnegative(artifact):
    assert artifact["trigger_recheck"]["P117_POWERLOTTO_OOS_RETRIGGER"]["current_new_draws_after_p116"] >= 0


def test_p117_remaining_partial_nonnegative(artifact):
    assert artifact["trigger_recheck"]["P117_POWERLOTTO_OOS_RETRIGGER"]["remaining_needed_for_partial"] >= 0


def test_p117_remaining_full_nonnegative(artifact):
    assert artifact["trigger_recheck"]["P117_POWERLOTTO_OOS_RETRIGGER"]["remaining_needed_for_full"] >= 0


def test_p118_exact_phrase_recorded(artifact):
    phrase = artifact["trigger_recheck"]["P118_BIGLOTTO_ACTUAL_QUARANTINE"]["exact_authorization_phrase"]
    assert "fourier30_markov30_biglotto" in phrase
    assert "YES quarantine" in phrase


def test_p118_authorization_present_false_by_default(artifact):
    assert artifact["trigger_recheck"]["P118_BIGLOTTO_ACTUAL_QUARANTINE"]["authorization_present"] is False


def test_4star_source_unknown_caveat_active(artifact):
    assert artifact["trigger_recheck"]["P4STAR_PROVENANCE_AND_BACKTEST"]["source_unknown_caveat_active"] is True


# --- Classification logic ---

def test_all_blocked_classification(artifact):
    tr = artifact["trigger_recheck"]
    p108 = tr["P108_SPECIAL3_100DRAW_REEVALUATION"]["trigger_met"]
    p117p = tr["P117_POWERLOTTO_OOS_RETRIGGER"]["partial_trigger_met"]
    p117f = tr["P117_POWERLOTTO_OOS_RETRIGGER"]["full_trigger_met"]
    p118 = tr["P118_BIGLOTTO_ACTUAL_QUARANTINE"]["trigger_met"]
    p4star = tr["P4STAR_PROVENANCE_AND_BACKTEST"]["trigger_met"]
    if not any([p108, p117p, p117f, p118, p4star]):
        assert artifact["classification"] == "P121_ALL_TRIGGERS_STILL_BLOCKED"


# --- Priority trigger ---

def test_priority_trigger_exists(artifact):
    assert "priority_trigger" in artifact


# --- Blocked task register ---

def test_blocked_task_register_exists(artifact):
    assert "blocked_task_register" in artifact
    assert isinstance(artifact["blocked_task_register"], list)


# --- Overall recommendation ---

def test_overall_recommendation_exists(artifact):
    assert "overall_recommendation" in artifact
    assert len(artifact["overall_recommendation"]) > 10


# --- Next operator action ---

def test_next_operator_action_exists(artifact):
    assert "next_operator_action" in artifact
    assert len(artifact["next_operator_action"]) > 5


# --- Live DB check ---

def test_live_db_replay_rows_still_54462():
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM strategy_prediction_replays")
    count = cur.fetchone()[0]
    conn.close()
    assert count == 54462


# --- Script checks ---

def test_script_has_no_sql_write_verbs(script_text):
    text_upper = script_text.upper()
    for verb in FORBIDDEN_SQL_VERBS:
        pattern = rf'\.execute\([^)]*\b{re.escape(verb)}\b'
        assert not re.search(pattern, text_upper), f"Script contains SQL write verb in execute(): {verb}"


def test_script_supports_operator_input(script_text):
    assert "--operator-input" in script_text


# --- Markdown content ---

def test_md_contains_p108_not_run(md_text):
    assert "P108" in md_text
    assert "NOT run" in md_text or "not run" in md_text.lower()


def test_md_contains_p117_oos_not_run(md_text):
    assert "P117" in md_text
    assert "NOT run" in md_text or "not run" in md_text.lower()


def test_md_contains_actual_quarantine_not_applied(md_text):
    assert "quarantine" in md_text.lower()
    assert "NOT applied" in md_text or "not applied" in md_text.lower()


def test_md_contains_4star_backtest_not_run(md_text):
    assert "4_STAR" in md_text
    assert "NOT run" in md_text or "not run" in md_text.lower()


def test_md_contains_no_promotion_authorization(md_text):
    assert "promotion" in md_text.lower()
    assert "not authorized" in md_text.lower() or "NOT authorized" in md_text


def test_md_contains_final_classification(md_text):
    assert any(c in md_text for c in VALID_CLASSIFICATIONS)


# --- No DB files staged ---

def test_no_db_files_staged():
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    staged = result.stdout.strip()
    for line in staged.splitlines():
        assert not re.search(r'\.(db|wal|shm)$', line), f"DB file staged: {line}"
        assert "lottery_history" not in line, f"History file staged: {line}"
