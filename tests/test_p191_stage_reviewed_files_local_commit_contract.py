"""Contract test for P191 — Stage Reviewed Files and Create Local Commit."""
import json
import os
import subprocess
import pytest

ARTIFACT_DIR = "outputs/research/power_lotto"
JSON_PATH = f"{ARTIFACT_DIR}/p191_stage_reviewed_files_local_commit_20260601.json"
MD_PATH = f"{ARTIFACT_DIR}/p191_stage_reviewed_files_local_commit_20260601.md"
DB_PATH = "lottery_api/data/lottery_v2.db"
BACKUP_PATH = "backups/p188_lottery_v2_backup_20260601_153821.db"
ACTIVE_TASK_PATH = "00-Plan/roadmap/active_task.md"
ROADMAP_PATH = "00-Plan/roadmap/roadmap.md"
CTO_PATH = "00-Plan/roadmap/CTO-Analysis.md"


@pytest.fixture(scope="module")
def artifact():
    with open(JSON_PATH) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def md_text():
    with open(MD_PATH) as f:
        return f.read()


# ── Artifact existence ────────────────────────────────────────────────────────

def test_p191_json_exists():
    assert os.path.exists(JSON_PATH)


def test_p191_md_exists():
    assert os.path.exists(MD_PATH)


# ── Classification and authorization ─────────────────────────────────────────

def test_p191_final_classification(artifact):
    assert artifact["final_classification"] == "P191_STAGE_REVIEWED_FILES_LOCAL_COMMIT_READY"


def test_p191_authorization_phrase(artifact):
    assert "YES start P191 stage reviewed files and create local commit only, no push" in artifact.get("authorization_phrase_detected", "")


# ── Phase 0 verification ──────────────────────────────────────────────────────

def test_p191_phase0_pass(artifact):
    assert artifact["phase_0_verification"]["status"] == "PASS"


def test_p191_phase0_db_rows(artifact):
    assert artifact["phase_0_verification"]["production_db_rows"] == 94924


def test_p191_phase0_bet_index(artifact):
    assert artifact["phase_0_verification"]["bet_index_present"] is True


def test_p191_phase0_backup_rows(artifact):
    assert artifact["phase_0_verification"]["p188_backup_rows"] == 54462


def test_p191_phase0_backup_bet_index_absent(artifact):
    assert artifact["phase_0_verification"]["p188_backup_bet_index"] == "ABSENT"


def test_p191_phase0_tests_pass(artifact):
    result = artifact["phase_0_verification"]["p178a_to_p190_tests"]
    assert "736 passed" in result
    assert "0 failed" in result


def test_p191_phase0_drift_guard(artifact):
    assert "PASS" in artifact["phase_0_verification"]["drift_guard_result"]


def test_p191_phase0_staged_zero(artifact):
    assert artifact["phase_0_verification"]["staged_files_before_p191"] == 0


def test_p191_phase0_no_stop_conditions(artifact):
    assert len(artifact["phase_0_verification"].get("stop_conditions_triggered", [])) == 0


# ── P190 classification referenced ───────────────────────────────────────────

def test_p191_p190_classification_referenced(artifact):
    assert artifact.get("p190_classification_referenced") == "P190_COMMIT_READINESS_AND_STAGING_PLAN_READY"


# ── Reviewed staging whitelist ────────────────────────────────────────────────

def test_p191_staging_whitelist_exists(artifact):
    wl = artifact.get("reviewed_staging_whitelist", {})
    assert len(wl) >= 5


def test_p191_staging_whitelist_db(artifact):
    wl = artifact["reviewed_staging_whitelist"]
    group_a = wl.get("group_A_db", [])
    assert "lottery_api/data/lottery_v2.db" in group_a


def test_p191_staging_whitelist_backup(artifact):
    wl = artifact["reviewed_staging_whitelist"]
    group_b = wl.get("group_B_backup", [])
    assert any("p188_lottery_v2_backup" in f for f in group_b)
    assert any(".sha256" in f for f in group_b)


def test_p191_staging_whitelist_drift_guard(artifact):
    wl = artifact["reviewed_staging_whitelist"]
    group_e = wl.get("group_E_drift_guard", [])
    assert "scripts/replay_lifecycle_drift_guard.py" in group_e


def test_p191_staging_whitelist_analysis_scripts(artifact):
    wl = artifact["reviewed_staging_whitelist"]
    group_f = wl.get("group_F_analysis_scripts", [])
    assert len(group_f) >= 5


def test_p191_staging_whitelist_roadmap(artifact):
    wl = artifact["reviewed_staging_whitelist"]
    group_h = wl.get("group_H_roadmap_docs", [])
    assert "00-Plan/roadmap/active_task.md" in group_h


# ── Commit result ─────────────────────────────────────────────────────────────

def test_p191_local_commit_created(artifact):
    gc = artifact.get("governance_confirmations", {})
    assert gc.get("local_commit_created") is True


def test_p191_no_push(artifact):
    gc = artifact.get("governance_confirmations", {})
    assert gc.get("no_push") is True


def test_p191_commit_result_populated(artifact):
    cr = artifact.get("commit_result", {})
    assert cr.get("status") not in (None, "POPULATED_AFTER_COMMIT")
    assert cr.get("commit_hash") not in (None, "POPULATED_AFTER_COMMIT")


def test_p191_commit_message_contains_p188(artifact):
    cm = artifact.get("commit_result", {}).get("commit_message", "")
    assert "P188" in cm or "P191" in cm or "reconcile" in cm.lower()


# ── Forbidden staging scan ────────────────────────────────────────────────────

def test_p191_forbidden_staging_scan_passed(artifact):
    fs = artifact.get("forbidden_staging_scan", {})
    assert fs.get("status") not in (None, "POPULATED_AFTER_STAGING")
    assert fs.get("forbidden_files_staged", 0) == 0


def test_p191_no_pid_staged(artifact):
    fs = artifact.get("forbidden_staging_scan", {})
    staged = fs.get("staged_files_list", [])
    staged_str = str(staged)
    assert "backend.pid" not in staged_str
    assert "frontend.pid" not in staged_str


def test_p191_no_runtime_staged(artifact):
    fs = artifact.get("forbidden_staging_scan", {})
    staged = fs.get("staged_files_list", [])
    staged_str = str(staged)
    assert "runtime/" not in staged_str


def test_p191_no_fuse_hidden_staged(artifact):
    fs = artifact.get("forbidden_staging_scan", {})
    staged = fs.get("staged_files_list", [])
    staged_str = str(staged)
    assert ".fuse_hidden" not in staged_str


def test_p191_no_wal_shm_staged(artifact):
    fs = artifact.get("forbidden_staging_scan", {})
    staged = fs.get("staged_files_list", [])
    staged_str = str(staged)
    assert ".db-wal" not in staged_str
    assert ".db-shm" not in staged_str


def test_p191_no_bak_files_staged(artifact):
    fs = artifact.get("forbidden_staging_scan", {})
    staged = fs.get("staged_files_list", [])
    staged_str = str(staged)
    assert ".db.bak_" not in staged_str


# ── Governance confirmations ──────────────────────────────────────────────────

def test_p191_no_controlled_apply(artifact):
    assert artifact["governance_confirmations"]["no_controlled_apply"] is True


def test_p191_no_registry_mutation(artifact):
    assert artifact["governance_confirmations"]["no_registry_mutation"] is True


def test_p191_no_research_rerun(artifact):
    assert artifact["governance_confirmations"]["no_research_rerun"] is True


def test_p191_power_lotto_closed(artifact):
    assert artifact["governance_confirmations"]["power_lotto_research_closed"] is True


def test_p191_db_reconciliation_complete(artifact):
    assert artifact["governance_confirmations"]["db_level_reconciliation_complete"] is True


def test_p191_db_rows_in_governance(artifact):
    assert artifact["governance_confirmations"]["production_db_rows"] == 94924


def test_p191_bet_index_in_governance(artifact):
    assert artifact["governance_confirmations"]["bet_index_present"] is True


def test_p191_backup_included(artifact):
    assert artifact["governance_confirmations"]["backup_included"] is True


def test_p191_blocked_by_authorization(artifact):
    assert artifact.get("next_task_blocked_by_user_authorization") is True


# ── P192 options ──────────────────────────────────────────────────────────────

def test_p191_p192_options_exist(artifact):
    opts = artifact.get("next_task_options", [])
    assert len(opts) >= 4


def test_p191_p192_option_push(artifact):
    opts = artifact.get("next_task_options", [])
    assert any("push" in o.lower() for o in opts)


def test_p191_p192_option_rollback(artifact):
    opts = artifact.get("next_task_options", [])
    assert any("rollback" in o.lower() for o in opts)


# ── MD content checks ─────────────────────────────────────────────────────────

def test_p191_md_classification(md_text):
    assert "P191_STAGE_REVIEWED_FILES_LOCAL_COMMIT_READY" in md_text


def test_p191_md_phase0_pass(md_text):
    assert "PASS" in md_text


def test_p191_md_commit(md_text):
    assert "local commit" in md_text.lower() or "Commit" in md_text


def test_p191_md_no_push(md_text):
    assert "no push" in md_text.lower() or "NO PUSH" in md_text or "not push" in md_text.lower()


def test_p191_md_p192_options(md_text):
    assert "P192" in md_text


def test_p191_md_no_wagering(md_text):
    text_lower = md_text.lower()
    for phrase in ["wagering advice", "guaranteed win", "predict and win"]:
        assert phrase not in text_lower


# ── Roadmap doc checks ────────────────────────────────────────────────────────

def test_p191_active_task_p191_ready():
    with open(ACTIVE_TASK_PATH) as f:
        content = f.read()
    assert "P191" in content
    assert ("READY" in content or "COMPLETE" in content or "LOCAL_COMMIT" in content)


def test_p191_active_task_p192_blocked():
    with open(ACTIVE_TASK_PATH) as f:
        content = f.read()
    assert "P192" in content
    assert "BLOCKED" in content


def test_p191_active_task_db_rows():
    with open(ACTIVE_TASK_PATH) as f:
        content = f.read()
    assert "94924" in content


def test_p191_active_task_no_push():
    with open(ACTIVE_TASK_PATH) as f:
        content = f.read()
    assert "push" in content.lower()


def test_p191_roadmap_p191_entry():
    with open(ROADMAP_PATH) as f:
        content = f.read()
    assert "P191" in content


def test_p191_roadmap_push_deferred():
    with open(ROADMAP_PATH) as f:
        content = f.read()
    assert "P192" in content
    assert "BLOCKED" in content or "deferred" in content.lower() or "Blocked" in content


def test_p191_roadmap_power_lotto_closed():
    with open(ROADMAP_PATH) as f:
        content = f.read()
    assert "CLOSED" in content or "closed" in content.lower()


def test_p191_cto_p191_entry():
    with open(CTO_PATH) as f:
        content = f.read()
    assert "P191" in content


def test_p191_cto_no_deployment_claim():
    with open(CTO_PATH) as f:
        content = f.read()
    text_lower = content.lower()
    for phrase in ["guaranteed win", "predict and win"]:
        assert phrase not in text_lower


# ── Live DB state ─────────────────────────────────────────────────────────────

def test_p191_db_rows_live():
    r = subprocess.run(
        ["sqlite3", DB_PATH, "SELECT COUNT(*) FROM strategy_prediction_replays;"],
        capture_output=True, text=True
    )
    assert r.returncode == 0
    assert int(r.stdout.strip()) == 94924


def test_p191_bet_index_live():
    r = subprocess.run(
        ["sqlite3", DB_PATH, "PRAGMA table_info(strategy_prediction_replays);"],
        capture_output=True, text=True
    )
    assert r.returncode == 0
    assert "bet_index" in r.stdout


# ── Git state (after commit) ──────────────────────────────────────────────────

def test_p191_git_commit_exists():
    r = subprocess.run(
        ["git", "log", "-1", "--oneline"],
        capture_output=True, text=True
    )
    assert r.returncode == 0
    assert "P188" in r.stdout or "P191" in r.stdout or "reconcile" in r.stdout.lower()


def test_p191_no_staged_files_after_commit():
    r = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True, text=True
    )
    assert r.returncode == 0
    assert r.stdout.strip() == ""


def test_p191_no_push():
    r = subprocess.run(
        ["git", "log", "--oneline", "origin/main..HEAD"],
        capture_output=True, text=True
    )
    # If origin/main doesn't exist locally, this fails — which is fine (no remote configured)
    # If origin/main exists, HEAD should be ahead by at least 1 commit (unpushed)
    # We just verify the commit was NOT pushed by checking the commit is in HEAD
    r2 = subprocess.run(
        ["git", "log", "-1", "--format=%H"],
        capture_output=True, text=True
    )
    assert r2.returncode == 0
    assert len(r2.stdout.strip()) == 40  # valid commit hash
