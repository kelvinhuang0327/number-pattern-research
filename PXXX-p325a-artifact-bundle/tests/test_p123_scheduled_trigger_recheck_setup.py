"""
Tests for P123: Scheduled Trigger Recheck Setup
"""

import json
import re
import sqlite3
import subprocess
import tempfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
JSON_ARTIFACT = PROJECT_ROOT / "outputs" / "replay" / "p123_scheduled_trigger_recheck_setup_20260527.json"
MD_ARTIFACT = PROJECT_ROOT / "docs" / "replay" / "p123_scheduled_trigger_recheck_setup_20260527.md"
SCRIPT = PROJECT_ROOT / "scripts" / "p123_scheduled_trigger_recheck.py"
SMOKE_ARTIFACT = PROJECT_ROOT / "outputs" / "replay" / "trigger_rechecks" / "p123_trigger_recheck_smoke_20260527.json"
DB_PATH = PROJECT_ROOT / "lottery_api" / "data" / "lottery_v2.db"

VALID_P123_CLASSIFICATIONS = {
    "P123_SCHEDULED_TRIGGER_RECHECK_SETUP_READY",
    "P123_SCHEDULED_TRIGGER_RECHECK_SETUP_PARTIAL",
    "P123_BLOCKED_BY_PREFLIGHT",
    "P123_BLOCKED_BY_DB_DRIFT",
    "P123_BLOCKED_BY_GUARD_FAILURE",
    "P123_BLOCKED_BY_TEST_FAILURE",
    "P123_BLOCKED_BY_FORBIDDEN_FILES_STAGED",
    "P123_BLOCKED_BY_SCOPE_VIOLATION",
    "P123_BLOCKED_BY_CONTEXT_CONTAMINATION",
    "P123_BLOCKED_BY_WORKTREE_BRANCH",
}

VALID_RUNTIME_CLASSIFICATIONS = {
    "P122_ALL_TRIGGERS_STILL_BLOCKED",
    "P122_P108_TRIGGER_MET",
    "P122_P117_PARTIAL_TRIGGER_MET",
    "P122_P117_FULL_TRIGGER_MET",
    "P122_P118_AUTHORIZATION_PRESENT",
    "P122_4STAR_PROVENANCE_TRIGGER_MET",
    "P122_TRIGGER_RECHECK_INCONCLUSIVE",
    "P122_BLOCKED_BY_CONTEXT_CONTAMINATION",
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


@pytest.fixture(scope="module")
def smoke_artifact():
    return json.loads(SMOKE_ARTIFACT.read_text())


# --- File existence ---

def test_json_artifact_exists():
    assert JSON_ARTIFACT.exists()


def test_md_artifact_exists():
    assert MD_ARTIFACT.exists()


def test_script_exists():
    assert SCRIPT.exists()


def test_smoke_artifact_exists():
    assert SMOKE_ARTIFACT.exists()


# --- JSON parses ---

def test_json_parses(artifact):
    assert isinstance(artifact, dict)


def test_smoke_artifact_parses(smoke_artifact):
    assert isinstance(smoke_artifact, dict)


# --- Core fields ---

def test_task_id(artifact):
    assert artifact["task_id"] == "P123_SCHEDULED_TRIGGER_RECHECK_SETUP"


def test_classification_valid(artifact):
    assert artifact["classification"] in VALID_P123_CLASSIFICATIONS


def test_final_classification_valid(artifact):
    assert artifact["final_classification"] in VALID_P123_CLASSIFICATIONS


def test_classification_matches_final(artifact):
    assert artifact["classification"] == artifact["final_classification"]


def test_classification_is_ready(artifact):
    assert artifact["classification"] == "P123_SCHEDULED_TRIGGER_RECHECK_SETUP_READY"


# --- P122 reference ---

def test_p122_reference_exists(artifact):
    assert "p122_reference" in artifact
    assert "classification" in artifact["p122_reference"]
    assert "artifact_path" in artifact["p122_reference"]
    assert "merge_commit" in artifact["p122_reference"]


def test_p122_merge_commit(artifact):
    assert artifact["p122_reference"]["merge_commit"] == "9dcef2e"


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


def test_no_crontab_installed(artifact):
    assert artifact["no_crontab_installed"] is True


def test_no_launchd_plist_created(artifact):
    assert artifact["no_launchd_plist_created"] is True


def test_source_unknown_caveat_preserved(artifact):
    assert artifact["source_unknown_caveat_preserved"] is True


# --- Cross-project contamination guard ---

def test_contamination_guard_exists(artifact):
    assert "cross_project_contamination_guard" in artifact


def test_project_lock_is_lotterynew(artifact):
    assert artifact["cross_project_contamination_guard"]["project_lock"] == "LotteryNew"


def test_canonical_repo_correct(artifact):
    assert artifact["cross_project_contamination_guard"]["canonical_repo"] == "/Users/kelvin/Kelvin-WorkSpace/LotteryNew"


def test_rejected_contexts_includes_betting_pool(artifact):
    rejected = artifact["cross_project_contamination_guard"]["rejected_project_contexts"]
    assert "Betting-pool" in rejected


def test_contamination_detected_is_false(artifact):
    assert artifact["cross_project_contamination_guard"]["contamination_detected"] is False


# --- Worktree branch guard ---

def test_worktree_branch_guard_exists(artifact):
    assert "worktree_branch_guard" in artifact


def test_git_dir_expected(artifact):
    assert artifact["worktree_branch_guard"]["git_dir_expected"] == ".git"


def test_worktree_branches_not_allowed(artifact):
    assert artifact["worktree_branch_guard"]["worktree_branches_allowed"] is False


def test_claude_codex_worktree_not_allowed(artifact):
    assert artifact["worktree_branch_guard"]["claude_codex_worktree_allowed"] is False


def test_branch_prefixes_rejected_includes_claude(artifact):
    assert "claude/" in artifact["worktree_branch_guard"]["branch_prefixes_rejected"]


def test_branch_prefixes_rejected_includes_codex(artifact):
    assert "codex/" in artifact["worktree_branch_guard"]["branch_prefixes_rejected"]


# --- Scheduled recheck design ---

def test_scheduled_recheck_design_exists(artifact):
    assert "scheduled_recheck_design" in artifact


def test_wrapper_script_path(artifact):
    assert artifact["scheduled_recheck_design"]["wrapper_script"] == "scripts/p123_scheduled_trigger_recheck.py"


def test_supports_json_out(artifact):
    assert artifact["scheduled_recheck_design"]["supports_json_out"] is True


def test_supports_output_dir(artifact):
    assert artifact["scheduled_recheck_design"]["supports_output_dir"] is True


def test_supports_operator_input(artifact):
    assert artifact["scheduled_recheck_design"]["supports_operator_input"] is True


def test_supports_timestamp(artifact):
    assert artifact["scheduled_recheck_design"]["supports_timestamp"] is True


def test_does_not_install_os_scheduler(artifact):
    assert artifact["scheduled_recheck_design"]["installs_os_scheduler"] is False


def test_does_not_mutate_crontab(artifact):
    assert artifact["scheduled_recheck_design"]["mutates_crontab"] is False


def test_does_not_create_launchd_plist(artifact):
    assert artifact["scheduled_recheck_design"]["creates_launchd_plist"] is False


# --- First smoke recheck result ---

def test_first_recheck_smoke_result_exists(artifact):
    assert "first_recheck_smoke_result" in artifact


def test_smoke_classification_valid(artifact):
    assert artifact["first_recheck_smoke_result"]["classification"] in VALID_RUNTIME_CLASSIFICATIONS


def test_smoke_p108_remaining_nonnegative(artifact):
    assert artifact["first_recheck_smoke_result"]["p108_remaining"] >= 0


def test_smoke_p117_partial_remaining_nonnegative(artifact):
    assert artifact["first_recheck_smoke_result"]["p117_partial_remaining"] >= 0


def test_smoke_p117_full_remaining_nonnegative(artifact):
    assert artifact["first_recheck_smoke_result"]["p117_full_remaining"] >= 0


def test_smoke_p118_authorization_false(artifact):
    assert artifact["first_recheck_smoke_result"]["p118_authorization_present"] is False


def test_smoke_4star_provenance_false(artifact):
    assert artifact["first_recheck_smoke_result"]["four_star_provenance_trigger_met"] is False


# --- Current DB snapshot ---

def test_current_db_snapshot_exists(artifact):
    assert "current_db_snapshot" in artifact


def test_db_snapshot_replay_rows(artifact):
    assert artifact["current_db_snapshot"]["replay_rows"] == 54462


# --- Operator commands ---

def test_operator_manual_run_command_exists(artifact):
    assert "operator_manual_run_command" in artifact
    assert len(artifact["operator_manual_run_command"]) > 10


def test_optional_cron_example_not_installed_exists(artifact):
    assert "optional_cron_example_not_installed" in artifact
    assert "NOT INSTALLED" in artifact["optional_cron_example_not_installed"]


# --- Script content checks ---

def test_script_has_no_sql_write_verbs(script_text):
    text_upper = script_text.upper()
    for verb in FORBIDDEN_SQL_VERBS:
        pattern = rf'\.execute\([^)]*\b{re.escape(verb)}\b'
        assert not re.search(pattern, text_upper), f"Script contains SQL write verb: {verb}"


def test_script_supports_json_out_flag(script_text):
    assert "--json-out" in script_text


def test_script_supports_output_dir_flag(script_text):
    assert "--output-dir" in script_text


def test_script_supports_operator_input_flag(script_text):
    assert "--operator-input" in script_text


def test_script_supports_timestamp_flag(script_text):
    assert "--timestamp" in script_text


def test_script_no_crontab_execution(script_text):
    # Script must not call crontab as a subprocess command
    assert not re.search(r'subprocess\.[a-z_]+\s*\([^)]*["\']crontab["\']', script_text), \
        "Script must not invoke crontab via subprocess"


def test_script_no_launchctl_execution(script_text):
    assert "launchctl" not in script_text


def test_script_no_systemctl_execution(script_text):
    assert "systemctl" not in script_text


def test_script_no_at_command_execution(script_text):
    assert not re.search(r'\bsubprocess\b.*\bat\b', script_text)


# --- Runtime: run script with --json-out ---

def test_script_runs_with_json_out():
    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = Path(tmpdir) / "test_run.json"
        result = subprocess.run(
            [".venv/bin/python", "scripts/p123_scheduled_trigger_recheck.py",
             "--json-out", str(out_path), "--timestamp", "test_20260527"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Script failed: {result.stderr}"
        assert out_path.exists()
        data = json.loads(out_path.read_text())
        assert isinstance(data, dict)


def test_script_runs_with_output_dir_and_timestamp():
    with tempfile.TemporaryDirectory() as tmpdir:
        result = subprocess.run(
            [".venv/bin/python", "scripts/p123_scheduled_trigger_recheck.py",
             "--output-dir", tmpdir, "--timestamp", "test_20260527_abc"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Script failed: {result.stderr}"
        files = list(Path(tmpdir).glob("*.json"))
        assert len(files) == 1
        data = json.loads(files[0].read_text())
        assert isinstance(data, dict)
        assert "test_20260527_abc" in files[0].name


# --- Runtime artifact content ---

def test_runtime_artifact_contains_trigger_recheck(smoke_artifact):
    assert "trigger_recheck" in smoke_artifact


def test_runtime_artifact_contains_worktree_branch_guard(smoke_artifact):
    assert "worktree_branch_guard" in smoke_artifact


def test_runtime_artifact_db_writes_false(smoke_artifact):
    assert smoke_artifact["db_writes"] is False


def test_runtime_artifact_no_special3_p108_rerun(smoke_artifact):
    assert smoke_artifact["no_special3_p108_rerun"] is True


def test_runtime_artifact_no_powerlotto_oos_execution(smoke_artifact):
    assert smoke_artifact["no_powerlotto_oos_execution"] is True


def test_runtime_artifact_no_actual_quarantine_applied(smoke_artifact):
    assert smoke_artifact["no_actual_quarantine_applied"] is True


def test_runtime_artifact_no_4star_backtest(smoke_artifact):
    assert smoke_artifact["no_4star_backtest"] is True


def test_runtime_artifact_classification_valid(smoke_artifact):
    assert smoke_artifact["classification"] in VALID_RUNTIME_CLASSIFICATIONS


# --- Live DB check ---

def test_live_db_replay_rows_still_54462():
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM strategy_prediction_replays")
    count = cur.fetchone()[0]
    conn.close()
    assert count == 54462


# --- Markdown content ---

def test_md_contains_optional_cron_not_installed(md_text):
    assert "NOT INSTALLED" in md_text
    assert "cron" in md_text.lower()


def test_md_contains_worktree_branch_guard(md_text):
    assert "worktree" in md_text.lower() or "Worktree" in md_text


def test_md_contains_no_promotion_authorization(md_text):
    assert "promotion" in md_text.lower()
    assert "not authorized" in md_text.lower() or "NOT authorized" in md_text


def test_md_contains_final_classification(md_text):
    assert any(c in md_text for c in VALID_P123_CLASSIFICATIONS)


def test_md_contains_p108_not_run(md_text):
    assert "P108" in md_text
    assert "NOT run" in md_text or "not run" in md_text.lower()


def test_md_contains_p117_not_run(md_text):
    assert "P117" in md_text
    assert "NOT run" in md_text or "not run" in md_text.lower()


def test_md_contains_quarantine_not_applied(md_text):
    assert "quarantine" in md_text.lower()
    assert "NOT applied" in md_text or "not applied" in md_text.lower()


def test_md_contains_4star_not_run(md_text):
    assert "4_STAR" in md_text
    assert "NOT run" in md_text or "not run" in md_text.lower()


def test_md_contains_no_crontab_installed(md_text):
    assert "crontab" in md_text.lower()
    assert "NOT" in md_text


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
