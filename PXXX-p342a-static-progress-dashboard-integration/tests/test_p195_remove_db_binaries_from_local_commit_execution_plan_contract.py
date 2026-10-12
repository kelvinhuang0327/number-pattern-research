"""Contract test for P195 — Remove DB Binaries Execution Plan."""
import json
import os
import pytest

ARTIFACT_DIR = "outputs/research/power_lotto"
JSON_PATH = f"{ARTIFACT_DIR}/p195_remove_db_binaries_from_local_commit_execution_plan_20260601.json"
MD_PATH = f"{ARTIFACT_DIR}/p195_remove_db_binaries_from_local_commit_execution_plan_20260601.md"
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


# ── Artifacts exist ───────────────────────────────────────────────────────────

def test_p195_json_exists():
    assert os.path.exists(JSON_PATH)


def test_p195_md_exists():
    assert os.path.exists(MD_PATH)


# ── Classification and authorization ─────────────────────────────────────────

def test_p195_final_classification(artifact):
    assert artifact["final_classification"] == "P195_REMOVE_DB_BINARIES_FROM_LOCAL_COMMIT_EXECUTION_PLAN_READY"


def test_p195_authorization_phrase(artifact):
    assert "YES start P195 remove DB binaries from local commit execution plan only" in artifact.get("authorization_phrase_detected", "")


# ── Phase 0 ───────────────────────────────────────────────────────────────────

def test_p195_phase0_pass(artifact):
    assert artifact["phase_0_verification"]["status"] == "PASS"


def test_p195_phase0_db_rows(artifact):
    assert artifact["phase_0_verification"]["production_db_rows"] == 94924


def test_p195_phase0_bet_index(artifact):
    assert artifact["phase_0_verification"]["bet_index_null_count"] == 0


def test_p195_phase0_backup(artifact):
    assert artifact["phase_0_verification"]["backup_exists"] is True


def test_p195_phase0_prod_sha256(artifact):
    assert "a5ac27a6" in artifact["phase_0_verification"]["production_db_sha256"]


def test_p195_phase0_backup_sha256(artifact):
    assert "5eea5313" in artifact["phase_0_verification"]["backup_sha256"]


def test_p195_phase0_prod_bytes(artifact):
    assert artifact["phase_0_verification"]["production_db_size_bytes"] == 99368960


def test_p195_phase0_backup_bytes(artifact):
    assert artifact["phase_0_verification"]["backup_size_bytes"] == 53374976


def test_p195_phase0_tests(artifact):
    assert "933 passed" in artifact["phase_0_verification"]["p178a_to_p194_tests"]


def test_p195_phase0_drift_guard(artifact):
    assert "PASS" in artifact["phase_0_verification"]["drift_guard"]


def test_p195_phase0_no_stop_conditions(artifact):
    assert len(artifact["phase_0_verification"].get("stop_conditions_triggered", [])) == 0


# ── P194 reference ────────────────────────────────────────────────────────────

def test_p195_p194_classification_referenced(artifact):
    assert artifact.get("p194_classification_referenced") == "P194_REMOVE_DB_BINARIES_FROM_LOCAL_COMMIT_PLAN_READY"


# ── Current state ─────────────────────────────────────────────────────────────

def test_p195_current_state_p191_unpushed(artifact):
    cs = artifact.get("current_state_summary", {})
    assert "012d4a3" in cs.get("p191_local_commit", "")
    assert cs.get("p191_commit_contains_db_binaries") is True


# ── P196 execution plan ───────────────────────────────────────────────────────

def test_p195_p196_plan_exists(artifact):
    assert "p196_execution_plan" in artifact


def test_p195_p196_has_soft_reset(artifact):
    plan = artifact["p196_execution_plan"]
    reset = plan.get("step_2_soft_reset", {})
    assert "reset --soft" in str(reset.get("command", ""))


def test_p195_p196_no_hard_reset(artifact):
    # --hard is allowed only in a safety-warning context ("Never use --hard")
    plan = str(artifact["p196_execution_plan"])
    if "--hard" in plan:
        # Must only appear in a prohibition/warning context
        assert "never" in plan.lower() or "must not" in plan.lower()


def test_p195_p196_has_unstage_step(artifact):
    plan = artifact["p196_execution_plan"]
    unstage = plan.get("step_3_unstage_db_binaries", {})
    commands = str(unstage.get("commands", []))
    assert "restore --staged" in commands
    assert "lottery_v2.db" in commands


def test_p195_p196_preserve_db_on_disk(artifact):
    plan = artifact["p196_execution_plan"]
    unstage = plan.get("step_3_unstage_db_binaries", {})
    what_it_does = str(unstage.get("what_it_does", []))
    assert "NOT" in what_it_does.upper() or "intact" in what_it_does.lower() or "disk" in what_it_does.lower()


def test_p195_p196_has_recommit_step(artifact):
    plan = artifact["p196_execution_plan"]
    recommit = plan.get("step_7_recommit", {})
    assert recommit.get("command") is not None


def test_p195_p196_no_push(artifact):
    plan = artifact["p196_execution_plan"]
    no_push = plan.get("step_9_no_push", {})
    assert no_push.get("action") is not None


def test_p195_p196_has_manifest_step(artifact):
    plan = artifact["p196_execution_plan"]
    manifest_step = plan.get("step_1_preserve_evidence", {})
    assert "manifest" in str(manifest_step).lower()


def test_p195_p196_has_gitignore_step(artifact):
    plan = artifact["p196_execution_plan"]
    gitignore_step = plan.get("step_4_update_gitignore", {})
    entries = str(gitignore_step.get("lines_to_append", []))
    assert "lottery_v2.db" in entries
    assert "backups/*.db" in entries


# ── Safety checks ─────────────────────────────────────────────────────────────

def test_p195_safety_checks_exist(artifact):
    sc = artifact.get("p196_safety_checks", {})
    assert "before_reset" in sc
    assert "after_unstage" in sc
    assert "after_commit" in sc


def test_p195_safety_check_preserve_local_db(artifact):
    sc = artifact["p196_safety_checks"]
    after_unstage = str(sc.get("after_unstage", []))
    assert "96M" in after_unstage or "exist" in after_unstage.lower() or "disk" in after_unstage.lower()


def test_p195_safety_check_preserve_backup(artifact):
    sc = artifact["p196_safety_checks"]
    after_unstage = str(sc.get("after_unstage", []))
    assert "51M" in after_unstage or "backup" in after_unstage.lower()


def test_p195_safety_check_no_db_binary_staged(artifact):
    sc = artifact["p196_safety_checks"]
    after_unstage = str(sc.get("after_unstage", []))
    assert "NOT" in after_unstage or "staged" in after_unstage.lower()


def test_p195_safety_check_no_db_binary_in_commit(artifact):
    sc = artifact["p196_safety_checks"]
    after_commit = str(sc.get("after_commit", []))
    assert "ABSENT" in after_commit or "empty" in after_commit.lower() or "no DB binary" in after_commit.lower()


def test_p195_safety_check_db_rows_after_commit(artifact):
    sc = artifact["p196_safety_checks"]
    after_commit = str(sc.get("after_commit", []))
    assert "94924" in after_commit


def test_p195_safety_check_no_push_after_commit(artifact):
    sc = artifact["p196_safety_checks"]
    after_commit = str(sc.get("after_commit", []))
    assert "push" in after_commit.lower()


# ── Manifest design ───────────────────────────────────────────────────────────

def test_p195_manifest_design_exists(artifact):
    assert "manifest_design" in artifact


def test_p195_manifest_path(artifact):
    md = artifact["manifest_design"]
    assert "db_migration_manifest" in md.get("path", "")


def test_p195_manifest_prod_sha256(artifact):
    md = artifact["manifest_design"]
    content = md.get("content", {})
    prod = content.get("production_db", {})
    assert "a5ac27a6" in str(prod.get("sha256", ""))


def test_p195_manifest_prod_rows(artifact):
    md = artifact["manifest_design"]
    content = md.get("content", {})
    prod = content.get("production_db", {})
    assert prod.get("rows") == 94924


def test_p195_manifest_prod_bytes(artifact):
    md = artifact["manifest_design"]
    content = md.get("content", {})
    prod = content.get("production_db", {})
    assert prod.get("size_bytes") == 99368960


def test_p195_manifest_backup_sha256(artifact):
    md = artifact["manifest_design"]
    content = md.get("content", {})
    bak = content.get("backup_db", {})
    assert "5eea5313" in str(bak.get("sha256", ""))


def test_p195_manifest_backup_rows(artifact):
    md = artifact["manifest_design"]
    content = md.get("content", {})
    bak = content.get("backup_db", {})
    assert bak.get("rows") == 54462


def test_p195_manifest_integrity(artifact):
    md = artifact["manifest_design"]
    content = md.get("content", {})
    prod = content.get("production_db", {})
    assert prod.get("integrity_check") == "ok"


def test_p195_manifest_external_storage_required(artifact):
    md = artifact["manifest_design"]
    content = md.get("content", {})
    assert content.get("external_storage_required") is True


# ── CTO recommendation ────────────────────────────────────────────────────────

def test_p195_cto_recommends_p196_soft_reset(artifact):
    cto = artifact.get("cto_recommendation", {})
    primary = cto.get("primary", "")
    assert "soft" in primary.lower() or "reset" in primary.lower()


def test_p195_cto_no_push(artifact):
    cto = artifact.get("cto_recommendation", {})
    do_not = str(cto.get("critical_do_not", []))
    assert "push" in do_not.lower()


def test_p195_cto_no_delete_db(artifact):
    cto = artifact.get("cto_recommendation", {})
    do_not = str(cto.get("critical_do_not", []))
    assert "delete" in do_not.lower() or "rm" in do_not.lower()


# ── Governance confirmations ──────────────────────────────────────────────────

def test_p195_no_db_write(artifact):
    assert artifact["governance_confirmations"]["no_db_write"] is True


def test_p195_no_db_delete(artifact):
    assert artifact["governance_confirmations"]["no_db_delete"] is True


def test_p195_no_backup_delete(artifact):
    assert artifact["governance_confirmations"]["no_backup_delete"] is True


def test_p195_no_commit_rewrite(artifact):
    assert artifact["governance_confirmations"]["no_commit_rewrite"] is True


def test_p195_no_stage(artifact):
    assert artifact["governance_confirmations"]["no_stage"] is True


def test_p195_no_commit(artifact):
    assert artifact["governance_confirmations"]["no_commit"] is True


def test_p195_no_push(artifact):
    assert artifact["governance_confirmations"]["no_push"] is True


def test_p195_no_force_push(artifact):
    assert artifact["governance_confirmations"]["no_force_push"] is True


def test_p195_power_lotto_closed(artifact):
    assert artifact["governance_confirmations"]["power_lotto_research_closed"] is True


def test_p195_db_preserved(artifact):
    assert artifact["governance_confirmations"]["migrated_db_local_state_preserved"] is True


def test_p195_blocked_by_authorization(artifact):
    assert artifact.get("next_task_blocked_by_user_authorization") is True


# ── P196 options ──────────────────────────────────────────────────────────────

def test_p195_p196_options_exist(artifact):
    opts = artifact.get("next_task_options", [])
    assert len(opts) >= 4


def test_p195_p196_execute_option(artifact):
    opts = artifact.get("next_task_options", [])
    assert any("YES execute P196" in o for o in opts)


def test_p195_p196_rollback_option(artifact):
    opts = artifact.get("next_task_options", [])
    assert any("rollback" in o.lower() for o in opts)


# ── MD checks ─────────────────────────────────────────────────────────────────

def test_p195_md_classification(md_text):
    assert "P195_REMOVE_DB_BINARIES_FROM_LOCAL_COMMIT_EXECUTION_PLAN_READY" in md_text


def test_p195_md_soft_reset(md_text):
    assert "reset --soft" in md_text


def test_p195_md_restore_staged(md_text):
    assert "restore --staged" in md_text


def test_p195_md_sha256_prod(md_text):
    assert "a5ac27a6" in md_text


def test_p195_md_sha256_backup(md_text):
    assert "5eea5313" in md_text


def test_p195_md_manifest(md_text):
    assert "manifest" in md_text.lower()


def test_p195_md_gitignore(md_text):
    assert ".gitignore" in md_text


def test_p195_md_no_hard_reset(md_text):
    assert "--hard" not in md_text or "NEVER" in md_text or "never" in md_text


def test_p195_md_p196_options(md_text):
    assert "P196" in md_text


def test_p195_md_no_wagering(md_text):
    text_lower = md_text.lower()
    for phrase in ["wagering advice", "guaranteed win", "predict and win"]:
        assert phrase not in text_lower


# ── Roadmap checks ────────────────────────────────────────────────────────────

def test_p195_active_task_p195_ready():
    with open(ACTIVE_TASK_PATH) as f:
        content = f.read()
    assert "P195" in content
    assert "READY" in content or "COMPLETE" in content


def test_p195_active_task_p196_blocked():
    with open(ACTIVE_TASK_PATH) as f:
        content = f.read()
    assert "P196" in content
    assert "BLOCKED" in content


def test_p195_active_task_db_rows():
    with open(ACTIVE_TASK_PATH) as f:
        content = f.read()
    assert "94924" in content


def test_p195_roadmap_p195_entry():
    with open(ROADMAP_PATH) as f:
        content = f.read()
    assert "P195" in content


def test_p195_roadmap_p196_blocked():
    with open(ROADMAP_PATH) as f:
        content = f.read()
    assert "P196" in content
    assert "BLOCKED" in content or "pending" in content.lower()


def test_p195_roadmap_power_lotto_closed():
    with open(ROADMAP_PATH) as f:
        content = f.read()
    assert "CLOSED" in content or "closed" in content.lower()


def test_p195_cto_p195_entry():
    with open(CTO_PATH) as f:
        content = f.read()
    assert "P195" in content


def test_p195_cto_p196_recommendation():
    with open(CTO_PATH) as f:
        content = f.read()
    assert "P196" in content


def test_p195_cto_no_deployment_claim():
    with open(CTO_PATH) as f:
        content = f.read()
    for phrase in ["guaranteed win", "predict and win"]:
        assert phrase not in content.lower()
