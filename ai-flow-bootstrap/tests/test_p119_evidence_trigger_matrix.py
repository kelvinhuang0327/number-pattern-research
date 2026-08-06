"""
Tests for P119: Evidence Consolidation and Trigger Matrix
"""

import json
import re
import sqlite3
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
JSON_ARTIFACT = PROJECT_ROOT / "outputs" / "replay" / "p119_evidence_trigger_matrix_20260527.json"
MD_ARTIFACT = PROJECT_ROOT / "docs" / "replay" / "p119_evidence_trigger_matrix_20260527.md"
SCRIPT = PROJECT_ROOT / "scripts" / "p119_evidence_trigger_matrix.py"
DB_PATH = PROJECT_ROOT / "lottery_api" / "data" / "lottery_v2.db"

VALID_CLASSIFICATIONS = {
    "P119_EVIDENCE_TRIGGER_MATRIX_READY",
    "P119_EVIDENCE_TRIGGER_MATRIX_PARTIAL",
    "P119_EVIDENCE_TRIGGER_MATRIX_INCONCLUSIVE",
    "P119_BLOCKED_BY_PREFLIGHT",
    "P119_BLOCKED_BY_DB_DRIFT",
    "P119_BLOCKED_BY_GUARD_FAILURE",
    "P119_BLOCKED_BY_TEST_FAILURE",
    "P119_BLOCKED_BY_FORBIDDEN_FILES_STAGED",
    "P119_BLOCKED_BY_SCOPE_VIOLATION",
    "P119_BLOCKED_BY_CONTEXT_CONTAMINATION",
}

FORBIDDEN_SQL_VERBS = [
    "INSERT", "UPDATE", "DELETE", "CREATE TABLE", "DROP", "ALTER TABLE",
    "REPLACE INTO", "VACUUM", "PRAGMA writable_schema",
]

REQUIRED_EVIDENCE_PHASES = {"P105", "P106", "P107A", "P107B", "P112", "P113", "P114", "P116", "P115", "P117"}
REQUIRED_TRIGGER_ENTRIES = {
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
    assert artifact["task_id"] == "P119_EVIDENCE_TRIGGER_MATRIX"


def test_classification_valid(artifact):
    assert artifact["classification"] in VALID_CLASSIFICATIONS


def test_final_classification_valid(artifact):
    assert artifact["final_classification"] in VALID_CLASSIFICATIONS


def test_classification_matches_final(artifact):
    assert artifact["classification"] == artifact["final_classification"]


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

def test_db_snapshot_exists(artifact):
    assert "current_db_snapshot" in artifact


def test_db_snapshot_replay_rows(artifact):
    assert artifact["current_db_snapshot"]["replay_rows"] == 54462


def test_db_snapshot_three_star_count(artifact):
    assert artifact["current_db_snapshot"]["three_star_count"] == 4179


def test_db_snapshot_three_star_max_draw(artifact):
    assert artifact["current_db_snapshot"]["three_star_max_draw"] == "115000106"


def test_db_snapshot_four_star_count(artifact):
    assert artifact["current_db_snapshot"]["four_star_count"] == 2922


def test_db_snapshot_four_star_max_draw(artifact):
    assert artifact["current_db_snapshot"]["four_star_max_draw"] == "115000103"


def test_db_snapshot_power_lotto_count(artifact):
    assert artifact["current_db_snapshot"]["power_lotto_count"] == 1913


def test_db_snapshot_power_lotto_max_draw(artifact):
    assert artifact["current_db_snapshot"]["power_lotto_max_draw"] == "115000041"


# --- Evidence index ---

def test_evidence_index_exists(artifact):
    assert "evidence_index" in artifact
    assert isinstance(artifact["evidence_index"], list)


def test_evidence_index_phase_count(artifact):
    phases = {e["phase_id"] for e in artifact["evidence_index"]}
    assert phases >= REQUIRED_EVIDENCE_PHASES


@pytest.mark.parametrize("phase", sorted(REQUIRED_EVIDENCE_PHASES))
def test_evidence_index_contains_phase(artifact, phase):
    phases = {e["phase_id"] for e in artifact["evidence_index"]}
    assert phase in phases, f"Evidence index missing phase {phase}"


# --- Trigger matrix ---

def test_trigger_matrix_exists(artifact):
    assert "trigger_matrix" in artifact
    assert isinstance(artifact["trigger_matrix"], dict)


@pytest.mark.parametrize("entry", sorted(REQUIRED_TRIGGER_ENTRIES))
def test_trigger_matrix_contains_entry(artifact, entry):
    assert entry in artifact["trigger_matrix"], f"Trigger matrix missing {entry}"


def test_trigger_p108_has_status(artifact):
    assert "status" in artifact["trigger_matrix"]["P108_SPECIAL3_100DRAW_REEVALUATION"]


def test_trigger_p117_has_status(artifact):
    assert "status" in artifact["trigger_matrix"]["P117_POWERLOTTO_OOS_RETRIGGER"]


def test_trigger_p118_has_status(artifact):
    assert "status" in artifact["trigger_matrix"]["P118_BIGLOTTO_ACTUAL_QUARANTINE"]


def test_trigger_p4star_has_status(artifact):
    assert "status" in artifact["trigger_matrix"]["P4STAR_PROVENANCE_AND_BACKTEST"]


# --- Blocked task register ---

def test_blocked_task_register_exists(artifact):
    assert "blocked_task_register" in artifact
    assert isinstance(artifact["blocked_task_register"], list)


def test_blocked_register_includes_p108(artifact):
    names = [b["task"] for b in artifact["blocked_task_register"]]
    assert any("P108" in n or "SPECIAL3" in n for n in names)


def test_blocked_register_includes_p117_retrigger_if_no_new_draws(artifact):
    new_pl_draws = artifact["trigger_matrix"]["P117_POWERLOTTO_OOS_RETRIGGER"]["current_value"]
    if new_pl_draws < 30:
        names = [b["task"] for b in artifact["blocked_task_register"]]
        assert any("P117" in n or "POWERLOTTO" in n for n in names)


def test_blocked_register_includes_p118(artifact):
    names = [b["task"] for b in artifact["blocked_task_register"]]
    assert any("P118" in n or "QUARANTINE" in n for n in names)


def test_blocked_register_includes_4star(artifact):
    names = [b["task"] for b in artifact["blocked_task_register"]]
    assert any("4STAR" in n or "4_STAR" in n or "PROVENANCE" in n for n in names)


# --- Next action selector ---

def test_next_action_selector_exists(artifact):
    assert "next_action_selector" in artifact


def test_next_action_selector_has_recommendation(artifact):
    assert "recommended_next_action" in artifact["next_action_selector"]


# --- Explicit authorization phrases ---

def test_explicit_authorization_phrases_exists(artifact):
    assert "explicit_authorization_phrases" in artifact


def test_explicit_authorization_contains_biglotto_phrase(artifact):
    phrases = artifact["explicit_authorization_phrases"]
    combined = " ".join(str(p) for p in phrases)
    assert "fourier30_markov30_biglotto" in combined
    assert "YES quarantine" in combined


# --- Live DB check ---

def test_live_db_replay_rows_still_54462():
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM strategy_prediction_replays")
    count = cur.fetchone()[0]
    conn.close()
    assert count == 54462


# --- Script safety ---

def test_script_has_no_sql_write_verbs(script_text):
    text_upper = script_text.upper()
    for verb in FORBIDDEN_SQL_VERBS:
        pattern = rf'\.execute\([^)]*\b{re.escape(verb)}\b'
        assert not re.search(pattern, text_upper), f"Script contains SQL write verb in execute(): {verb}"


# --- Markdown content ---

def test_md_contains_p108_blocked(md_text):
    assert "P108" in md_text


def test_md_contains_p117_retrigger_condition(md_text):
    assert "P117" in md_text
    assert ("30" in md_text or "WAIT" in md_text or "BLOCKED" in md_text)


def test_md_contains_p118_authorization_phrase(md_text):
    assert "YES quarantine strategy fourier30_markov30_biglotto" in md_text


def test_md_contains_4star_blocked(md_text):
    assert "4_STAR" in md_text
    assert "unauthorized" in md_text.lower() or "BLOCKED" in md_text or "NOT_AUTHORIZED" in md_text


def test_md_contains_no_promotion_authorization(md_text):
    assert "promotion" in md_text.lower()
    # Must state it is NOT authorized
    assert "not authorize" in md_text.lower() or "NOT authorize" in md_text or "no promotion" in md_text.lower() or "NOT authorized" in md_text


def test_md_contains_final_classification(md_text):
    assert "P119_EVIDENCE_TRIGGER_MATRIX_READY" in md_text


# --- No DB files staged ---

def test_no_db_files_staged():
    import subprocess
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
