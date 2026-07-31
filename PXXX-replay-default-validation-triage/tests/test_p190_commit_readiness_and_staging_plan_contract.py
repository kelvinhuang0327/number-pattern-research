"""Contract test for P190 — Commit Readiness and Staging Plan."""
import json
import os
import re
import pytest

ARTIFACT_DIR = "outputs/research/power_lotto"
JSON_PATH = f"{ARTIFACT_DIR}/p190_commit_readiness_and_staging_plan_20260601.json"
MD_PATH = f"{ARTIFACT_DIR}/p190_commit_readiness_and_staging_plan_20260601.md"
DB_PATH = "lottery_api/data/lottery_v2.db"
BACKUP_PATH = "backups/p188_lottery_v2_backup_20260601_153821.db"
DRIFT_GUARD_PATH = "scripts/replay_lifecycle_drift_guard.py"
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

def test_p190_json_exists():
    assert os.path.exists(JSON_PATH), f"P190 JSON not found: {JSON_PATH}"


def test_p190_md_exists():
    assert os.path.exists(MD_PATH), f"P190 MD not found: {MD_PATH}"


# ── Classification and authorization ─────────────────────────────────────────

def test_p190_final_classification(artifact):
    assert artifact["final_classification"] == "P190_COMMIT_READINESS_AND_STAGING_PLAN_READY"


def test_p190_authorization_phrase(artifact):
    phrase = artifact.get("authorization_phrase_detected", "")
    assert "YES start P190 commit readiness and staging plan only" in phrase


# ── Phase 0 verification ──────────────────────────────────────────────────────

def test_p190_phase0_pass(artifact):
    assert artifact["phase_0_verification"]["status"] == "PASS"


def test_p190_phase0_repo(artifact):
    repo = artifact["phase_0_verification"]["repo"]
    assert "LotteryNew" in repo


def test_p190_phase0_branch(artifact):
    assert artifact["phase_0_verification"]["branch"] == "main"


def test_p190_phase0_git_dir(artifact):
    assert artifact["phase_0_verification"]["git_dir"] == ".git"


def test_p190_phase0_db_rows(artifact):
    assert artifact["phase_0_verification"]["production_db_rows"] == 94924


def test_p190_phase0_bet_index_present(artifact):
    assert artifact["phase_0_verification"]["bet_index_present"] is True


def test_p190_phase0_null_count(artifact):
    assert artifact["phase_0_verification"]["bet_index_null_count"] == 0


def test_p190_phase0_duplicate_count(artifact):
    assert artifact["phase_0_verification"]["duplicate_count"] == 0


def test_p190_phase0_integrity(artifact):
    assert artifact["phase_0_verification"]["integrity_check"] == "ok"


def test_p190_phase0_backup(artifact):
    assert artifact["phase_0_verification"]["p188_backup_exists"] is True


def test_p190_phase0_backup_rows(artifact):
    assert artifact["phase_0_verification"]["p188_backup_rows"] == 54462


def test_p190_phase0_backup_bet_index_absent(artifact):
    assert artifact["phase_0_verification"]["p188_backup_bet_index"] == "ABSENT"


def test_p190_phase0_tests_pass(artifact):
    result = artifact["phase_0_verification"]["p178a_to_p189_tests"]
    assert "644 passed" in result
    assert "0 failed" in result


def test_p190_phase0_drift_guard(artifact):
    assert "PASS" in artifact["phase_0_verification"]["drift_guard_result"]


def test_p190_phase0_staged_zero(artifact):
    assert artifact["phase_0_verification"]["staged_files"] == 0


def test_p190_phase0_no_stop_conditions(artifact):
    assert len(artifact["phase_0_verification"]["stop_conditions_triggered"]) == 0


# ── P189 classification referenced ───────────────────────────────────────────

def test_p190_p189_classification_referenced(artifact):
    ref = artifact.get("p189_classification_referenced", "")
    assert ref == "P189_POST_MIGRATION_VERIFICATION_COMMIT_READINESS_READY"


# ── Commit readiness audit ────────────────────────────────────────────────────

def test_p190_commit_readiness_overall(artifact):
    assert artifact["commit_readiness_audit"]["overall"] == "READY"


def test_p190_production_db_rows_in_audit(artifact):
    assert artifact["commit_readiness_audit"]["db_migration"]["rows_after"] == 94924


def test_p190_bet_index_in_audit(artifact):
    assert artifact["commit_readiness_audit"]["db_migration"]["bet_index_added"] is True


def test_p190_drift_guard_in_audit(artifact):
    assert artifact["commit_readiness_audit"]["drift_guard"]["result"] == "PASS"


def test_p190_tests_in_audit(artifact):
    assert artifact["commit_readiness_audit"]["test_suite"]["result"] == "PASS"
    assert artifact["commit_readiness_audit"]["test_suite"]["passed"] == 644


# ── Staging whitelist proposal ────────────────────────────────────────────────

def test_p190_staging_whitelist_exists(artifact):
    assert "staging_whitelist_proposal" in artifact
    wl = artifact["staging_whitelist_proposal"]
    assert "group_A_db_migration_payload" in wl


def test_p190_staging_whitelist_group_a_db(artifact):
    group_a = artifact["staging_whitelist_proposal"]["group_A_db_migration_payload"]
    assert "lottery_api/data/lottery_v2.db" in group_a["files"]


def test_p190_staging_whitelist_group_b_backup(artifact):
    group_b = artifact["staging_whitelist_proposal"]["group_B_backup_payload"]
    assert any("p188_lottery_v2_backup" in f for f in group_b["include"])


def test_p190_staging_whitelist_group_c_research(artifact):
    group_c = artifact["staging_whitelist_proposal"]["group_C_research_artifacts"]
    count = group_c.get("count", "")
    assert "65" in str(count) or "artifacts" in str(count)


def test_p190_staging_whitelist_group_d_tests(artifact):
    group_d = artifact["staging_whitelist_proposal"]["group_D_contract_tests"]
    assert len(group_d.get("include", [])) > 5


def test_p190_staging_whitelist_group_e_drift_guard(artifact):
    group_e = artifact["staging_whitelist_proposal"]["group_E_drift_guard_and_config"]
    assert "scripts/replay_lifecycle_drift_guard.py" in group_e["files"]


# ── Forbidden staging policy ──────────────────────────────────────────────────

def test_p190_forbidden_staging_policy_exists(artifact):
    assert "forbidden_staging_policy" in artifact


def test_p190_forbidden_pids(artifact):
    forbidden = artifact["forbidden_staging_policy"]["absolute_never_stage"]
    forbidden_str = str(forbidden)
    assert "backend.pid" in forbidden_str
    assert "frontend.pid" in forbidden_str


def test_p190_forbidden_runtime(artifact):
    forbidden = artifact["forbidden_staging_policy"]["absolute_never_stage"]
    assert any("runtime" in f for f in forbidden)


def test_p190_forbidden_fuse_hidden(artifact):
    forbidden = artifact["forbidden_staging_policy"]["absolute_never_stage"]
    assert any("fuse_hidden" in f for f in forbidden)


def test_p190_broad_staging_ban(artifact):
    ban = artifact["forbidden_staging_policy"]["broad_staging_absolute_ban"]
    assert "git add -A" in ban or "git add ." in ban
    assert "FORBIDDEN" in ban.upper() or "forbidden" in ban


# ── Commit message proposal ───────────────────────────────────────────────────

def test_p190_commit_message_exists(artifact):
    cm = artifact.get("commit_message_proposal", {})
    assert cm.get("subject") is not None


def test_p190_commit_message_subject(artifact):
    subject = artifact["commit_message_proposal"]["subject"]
    assert "P182" in subject
    assert "P190" in subject or "reconcile" in subject.lower()


def test_p190_commit_message_body_db_rows(artifact):
    body = " ".join(artifact["commit_message_proposal"]["body"])
    assert "54462" in body
    assert "94924" in body


def test_p190_commit_message_body_bet_index(artifact):
    body = " ".join(artifact["commit_message_proposal"]["body"])
    assert "bet_index" in body


def test_p190_commit_message_backup_mentioned(artifact):
    body = " ".join(artifact["commit_message_proposal"]["body"])
    assert "backup" in body.lower() or "p188_lottery_v2_backup" in body


def test_p190_commit_message_no_wagering(artifact):
    body = " ".join(artifact["commit_message_proposal"]["body"]).lower()
    assert "win" not in body or "winning" not in body.split()
    for forbidden in ["guaranteed", "wagering advice", "predict lottery"]:
        assert forbidden not in body


def test_p190_commit_message_research_closed(artifact):
    body = " ".join(artifact["commit_message_proposal"]["body"])
    assert "CLOSED" in body or "closed" in body


# ── P191 authorization options ────────────────────────────────────────────────

def test_p190_p191_options_exist(artifact):
    opts = artifact.get("p191_authorization_options", [])
    assert len(opts) >= 4


def test_p190_p191_option_a_staging_plan(artifact):
    opts = artifact["p191_authorization_options"]
    phrases = [o["phrase"] for o in opts]
    assert any("stage commit push authorization gate only" in p for p in phrases)


def test_p190_p191_option_b_local_commit(artifact):
    opts = artifact["p191_authorization_options"]
    phrases = [o["phrase"] for o in opts]
    assert any("local commit only" in p or "no push" in p for p in phrases)


def test_p190_p191_option_c_push(artifact):
    opts = artifact["p191_authorization_options"]
    phrases = [o["phrase"] for o in opts]
    assert any("push to origin main" in p for p in phrases)


def test_p190_p191_option_d_rollback(artifact):
    opts = artifact["p191_authorization_options"]
    phrases = [o["phrase"] for o in opts]
    assert any("rollback" in p for p in phrases)


# ── Governance confirmations ──────────────────────────────────────────────────

def test_p190_no_stage(artifact):
    gc = artifact["governance_confirmations"]
    assert gc["no_stage"] is True


def test_p190_no_commit(artifact):
    gc = artifact["governance_confirmations"]
    assert gc["no_commit"] is True


def test_p190_no_push(artifact):
    gc = artifact["governance_confirmations"]
    assert gc["no_push"] is True


def test_p190_no_db_write(artifact):
    gc = artifact["governance_confirmations"]
    assert gc["no_db_write_in_p190"] is True


def test_p190_no_controlled_apply(artifact):
    gc = artifact["governance_confirmations"]
    assert gc["no_controlled_apply"] is True


def test_p190_no_registry_mutation(artifact):
    gc = artifact["governance_confirmations"]
    assert gc["no_registry_mutation"] is True


def test_p190_no_research_rerun(artifact):
    gc = artifact["governance_confirmations"]
    assert gc["no_research_rerun"] is True


def test_p190_db_rows_confirmed(artifact):
    gc = artifact["governance_confirmations"]
    assert gc["production_db_rows"] == 94924


def test_p190_bet_index_confirmed(artifact):
    gc = artifact["governance_confirmations"]
    assert gc["bet_index_present"] is True


def test_p190_drift_guard_confirmed(artifact):
    gc = artifact["governance_confirmations"]
    assert gc["drift_guard_pass"] is True


def test_p190_tests_confirmed(artifact):
    gc = artifact["governance_confirmations"]
    assert gc["tests_pass"] is True


def test_p190_power_lotto_research_closed(artifact):
    gc = artifact["governance_confirmations"]
    assert gc["power_lotto_research_closed"] is True


def test_p190_reconciliation_complete(artifact):
    gc = artifact["governance_confirmations"]
    assert gc["db_level_reconciliation_complete"] is True


def test_p190_commit_not_created(artifact):
    gc = artifact["governance_confirmations"]
    assert gc["commit_not_yet_created"] is True


def test_p190_blocked_by_authorization(artifact):
    assert artifact["next_task_blocked_by_user_authorization"] is True


# ── MD content checks ─────────────────────────────────────────────────────────

def test_p190_md_classification(md_text):
    assert "P190_COMMIT_READINESS_AND_STAGING_PLAN_READY" in md_text


def test_p190_md_phase0_pass(md_text):
    assert "PASS" in md_text


def test_p190_md_db_rows(md_text):
    assert "94924" in md_text
    assert "54462" in md_text


def test_p190_md_bet_index(md_text):
    assert "bet_index" in md_text


def test_p190_md_staging_whitelist(md_text):
    assert "Staging Whitelist" in md_text or "staging_whitelist" in md_text or "Group A" in md_text


def test_p190_md_forbidden_staging(md_text):
    assert "NEVER STAGE" in md_text or "FORBIDDEN" in md_text


def test_p190_md_commit_message(md_text):
    assert "P182-P190" in md_text


def test_p190_md_p191_options(md_text):
    assert "P191" in md_text


def test_p190_md_governance(md_text):
    assert "no_stage" in md_text or "no stage" in md_text.lower()


def test_p190_md_no_wagering_recommendation(md_text):
    text_lower = md_text.lower()
    for phrase in ["wagering advice", "guaranteed win", "predict and win"]:
        assert phrase not in text_lower


# ── Roadmap doc checks ────────────────────────────────────────────────────────

def test_p190_active_task_exists():
    assert os.path.exists(ACTIVE_TASK_PATH), "active_task.md not found"


def test_p190_active_task_p190_ready():
    with open(ACTIVE_TASK_PATH) as f:
        content = f.read()
    assert "P190" in content
    assert "READY" in content or "COMPLETE" in content


def test_p190_active_task_p191_blocked():
    with open(ACTIVE_TASK_PATH) as f:
        content = f.read()
    assert "P191" in content
    assert "BLOCKED" in content


def test_p190_active_task_canonical_repo():
    with open(ACTIVE_TASK_PATH) as f:
        content = f.read()
    assert "LotteryNew" in content


def test_p190_active_task_db_rows_invariant():
    with open(ACTIVE_TASK_PATH) as f:
        content = f.read()
    assert "94924" in content


def test_p190_active_task_bet_index_present():
    with open(ACTIVE_TASK_PATH) as f:
        content = f.read()
    assert "bet_index" in content


def test_p190_active_task_p178a_preserved():
    with open(ACTIVE_TASK_PATH) as f:
        content = f.read()
    assert "P178A" in content


def test_p190_active_task_db_reconciliation_complete():
    with open(ACTIVE_TASK_PATH) as f:
        content = f.read()
    assert "RECONCILED" in content or "reconciliation" in content.lower()


def test_p190_roadmap_p190_entry():
    with open(ROADMAP_PATH) as f:
        content = f.read()
    assert "P190" in content


def test_p190_roadmap_post_migration_complete():
    with open(ROADMAP_PATH) as f:
        content = f.read()
    assert "94924" in content or "migration" in content.lower()


def test_p190_roadmap_p191_deferred():
    with open(ROADMAP_PATH) as f:
        content = f.read()
    assert "P191" in content
    assert "BLOCKED" in content or "deferred" in content.lower() or "Blocked" in content


def test_p190_roadmap_power_lotto_closed():
    with open(ROADMAP_PATH) as f:
        content = f.read()
    assert "CLOSED" in content or "closed" in content.lower()


def test_p190_cto_p190_entry():
    with open(CTO_PATH) as f:
        content = f.read()
    assert "P190" in content


def test_p190_cto_p191_recommendation():
    with open(CTO_PATH) as f:
        content = f.read()
    assert "P191" in content


def test_p190_cto_no_deployment_claim():
    with open(CTO_PATH) as f:
        content = f.read()
    text_lower = content.lower()
    for phrase in ["guaranteed win", "production deploy", "live recommendation"]:
        assert phrase not in text_lower


# ── Live DB state verification ────────────────────────────────────────────────

def test_p190_db_rows_live():
    import subprocess
    r = subprocess.run(
        ["sqlite3", DB_PATH, "SELECT COUNT(*) FROM strategy_prediction_replays;"],
        capture_output=True, text=True
    )
    assert r.returncode == 0
    assert int(r.stdout.strip()) == 94924


def test_p190_bet_index_live():
    import subprocess
    r = subprocess.run(
        ["sqlite3", DB_PATH, "PRAGMA table_info(strategy_prediction_replays);"],
        capture_output=True, text=True
    )
    assert r.returncode == 0
    assert "bet_index" in r.stdout


def test_p190_drift_guard_live():
    import subprocess
    r = subprocess.run(
        ["uv", "run", "python", DRIFT_GUARD_PATH],
        capture_output=True, text=True
    )
    assert r.returncode == 0
    assert "PASS" in r.stdout or "PASS" in r.stderr
