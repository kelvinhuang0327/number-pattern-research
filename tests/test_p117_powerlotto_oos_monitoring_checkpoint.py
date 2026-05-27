"""
Tests for P117: POWER_LOTTO OOS Monitoring Execution Checkpoint
"""

import json
import re
import sqlite3
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
JSON_ARTIFACT = PROJECT_ROOT / "outputs" / "replay" / "p117_powerlotto_oos_monitoring_checkpoint_20260527.json"
MD_ARTIFACT = PROJECT_ROOT / "docs" / "replay" / "p117_powerlotto_oos_monitoring_checkpoint_20260527.md"
SCRIPT = PROJECT_ROOT / "scripts" / "p117_powerlotto_oos_monitoring_checkpoint.py"
DB_PATH = PROJECT_ROOT / "lottery_api" / "data" / "lottery_v2.db"

VALID_CLASSIFICATIONS = {
    "P117_POWERLOTTO_OOS_WAIT_MORE_DRAWS",
    "P117_POWERLOTTO_OOS_PARTIAL_CHECKPOINT",
    "P117_POWERLOTTO_OOS_CHECKPOINT_READY",
    "P117_POWERLOTTO_OOS_INCONCLUSIVE",
    "P117_BLOCKED_BY_PREFLIGHT",
    "P117_BLOCKED_BY_DB_DRIFT",
    "P117_BLOCKED_BY_GUARD_FAILURE",
    "P117_BLOCKED_BY_TEST_FAILURE",
    "P117_BLOCKED_BY_FORBIDDEN_FILES_STAGED",
    "P117_BLOCKED_BY_SCOPE_VIOLATION",
    "P117_BLOCKED_BY_CONTEXT_CONTAMINATION",
}

FORBIDDEN_SQL_VERBS = [
    "INSERT", "UPDATE", "DELETE", "CREATE TABLE", "DROP", "ALTER TABLE",
    "REPLACE INTO", "VACUUM", "PRAGMA writable_schema",
]


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
    assert JSON_ARTIFACT.exists(), f"JSON artifact missing: {JSON_ARTIFACT}"


def test_md_artifact_exists():
    assert MD_ARTIFACT.exists(), f"Markdown artifact missing: {MD_ARTIFACT}"


def test_script_exists():
    assert SCRIPT.exists(), f"Script missing: {SCRIPT}"


# --- JSON parses ---

def test_json_parses(artifact):
    assert isinstance(artifact, dict)


# --- Core fields ---

def test_task_id(artifact):
    assert artifact["task_id"] == "P117_POWERLOTTO_OOS_MONITORING_CHECKPOINT"


def test_classification_valid(artifact):
    assert artifact["classification"] in VALID_CLASSIFICATIONS


def test_final_classification_valid(artifact):
    assert artifact["final_classification"] in VALID_CLASSIFICATIONS


def test_classification_matches_final(artifact):
    assert artifact["classification"] == artifact["final_classification"]


# --- References ---

def test_p116_reference_exists(artifact):
    assert "p116_reference" in artifact
    assert "classification" in artifact["p116_reference"]
    assert "artifact_path" in artifact["p116_reference"]


def test_p115_reference_exists(artifact):
    assert "p115_reference" in artifact
    assert "classification" in artifact["p115_reference"]
    assert "artifact_path" in artifact["p115_reference"]


# --- Safety guards ---

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


def test_source_unknown_caveat_preserved(artifact):
    assert artifact["source_unknown_caveat_preserved"] is True


# --- Lottery type ---

def test_monitored_lottery_type(artifact):
    assert artifact["monitored_lottery_type"] == "POWER_LOTTO"


# --- Draw baseline ---

def test_p116_baseline_draw(artifact):
    assert artifact["p116_baseline_power_lotto_max_draw"] == "115000041"


def test_current_max_draw_at_least_baseline(artifact):
    baseline = int(artifact["p116_baseline_power_lotto_max_draw"])
    current = int(artifact["current_power_lotto_max_draw"])
    assert current >= baseline


def test_new_draws_nonnegative(artifact):
    assert artifact["new_power_lotto_draws_after_p116"] >= 0


# --- Monitoring candidates ---

def test_midfreq_candidate_present(artifact):
    sids = [c["strategy_id"] for c in artifact["monitoring_candidates"]]
    assert "midfreq_fourier_mk_3bet" in sids


def test_pp3_candidate_present(artifact):
    sids = [c["strategy_id"] for c in artifact["monitoring_candidates"]]
    assert "pp3_freqort_4bet" in sids


def test_all_candidates_have_threshold_status(artifact):
    for c in artifact["monitoring_candidates"]:
        assert "threshold_status" in c, f"Missing threshold_status for {c['strategy_id']}"


def test_all_candidates_have_remaining_draws(artifact):
    for c in artifact["monitoring_candidates"]:
        assert "remaining_draws_needed_for_minimum" in c


def test_all_candidates_have_promotion_authorized_false(artifact):
    for c in artifact["monitoring_candidates"]:
        assert c["promotion_authorized"] is False, f"{c['strategy_id']} has promotion_authorized != False"


# --- Classification logic ---

def test_wait_more_draws_when_new_draws_below_30(artifact):
    new_draws = artifact["new_power_lotto_draws_after_p116"]
    if new_draws < 30:
        assert artifact["classification"] == "P117_POWERLOTTO_OOS_WAIT_MORE_DRAWS"


def test_partial_checkpoint_when_draws_30_to_39(artifact):
    new_draws = artifact["new_power_lotto_draws_after_p116"]
    if 30 <= new_draws < 40:
        assert artifact["classification"] == "P117_POWERLOTTO_OOS_PARTIAL_CHECKPOINT"


def test_checkpoint_ready_when_draws_40_plus(artifact):
    new_draws = artifact["new_power_lotto_draws_after_p116"]
    if new_draws >= 40:
        assert artifact["classification"] == "P117_POWERLOTTO_OOS_CHECKPOINT_READY"


# --- Explicit holds ---

def test_explicit_holds_contain_special3_p108(artifact):
    holds = " ".join(artifact["explicit_holds"])
    assert "P108" in holds or "Special3" in holds


def test_explicit_holds_contain_4star(artifact):
    holds = " ".join(artifact["explicit_holds"])
    assert "4_STAR" in holds


def test_explicit_holds_contain_biglotto_quarantine(artifact):
    holds = " ".join(artifact["explicit_holds"])
    assert "BIG_LOTTO" in holds or "quarantine" in holds.lower()


def test_explicit_holds_contain_no_promotion(artifact):
    holds = " ".join(artifact["explicit_holds"])
    assert "promotion" in holds.lower() or "authorized" in holds.lower()


# --- Live DB check ---

def test_live_db_replay_rows_still_54462():
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM strategy_prediction_replays")
    count = cur.fetchone()[0]
    conn.close()
    assert count == 54462, f"Replay rows changed: {count} != 54462"


# --- Script safety ---

def test_script_has_no_sql_write_verbs(script_text):
    text_upper = script_text.upper()
    for verb in FORBIDDEN_SQL_VERBS:
        # Check the verb doesn't appear outside of the FORBIDDEN_SQL_VERBS list itself
        # The list definition in the script is ok, actual execution is not
        # We check that there's no .execute() call with write verbs
        pattern = rf'\.execute\([^)]*\b{re.escape(verb)}\b'
        assert not re.search(pattern, text_upper), f"Script contains SQL write verb in execute(): {verb}"


# --- Markdown content ---

def test_md_contains_no_promotion_authorization(md_text):
    # Should not say "promotion authorized" or "promotion is authorized"
    assert "promotion authorized" not in md_text.lower() or "NOT AUTHORIZED" in md_text


def test_md_contains_p108_blocked(md_text):
    assert "P108" in md_text


def test_md_contains_4star_unauthorized(md_text):
    assert "4_STAR" in md_text
    assert "unauthorized" in md_text.lower() or "NOT authorized" in md_text or "UNAUTHORIZED" in md_text


def test_md_contains_biglotto_quarantine_gate(md_text):
    assert "BIG_LOTTO" in md_text
    assert "quarantine" in md_text.lower()


def test_md_contains_final_classification(md_text):
    assert "P117_POWERLOTTO_OOS_WAIT_MORE_DRAWS" in md_text or "PARTIAL_CHECKPOINT" in md_text or "CHECKPOINT_READY" in md_text


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
