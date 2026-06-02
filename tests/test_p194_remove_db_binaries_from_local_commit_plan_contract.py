"""Contract test for P194 — Remove DB Binaries from Local Commit Plan."""
import json
import os
import pytest

ARTIFACT_DIR = "outputs/research/power_lotto"
JSON_PATH = f"{ARTIFACT_DIR}/p194_remove_db_binaries_from_local_commit_plan_20260601.json"
MD_PATH = f"{ARTIFACT_DIR}/p194_remove_db_binaries_from_local_commit_plan_20260601.md"
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

def test_p194_json_exists():
    assert os.path.exists(JSON_PATH)


def test_p194_md_exists():
    assert os.path.exists(MD_PATH)


# ── Classification and authorization ─────────────────────────────────────────

def test_p194_final_classification(artifact):
    assert artifact["final_classification"] == "P194_REMOVE_DB_BINARIES_FROM_LOCAL_COMMIT_PLAN_READY"


def test_p194_authorization_phrase(artifact):
    assert "YES start P194 remove DB binaries from local commit plan only" in artifact.get("authorization_phrase_detected", "")


# ── Phase 0 ───────────────────────────────────────────────────────────────────

def test_p194_phase0_pass(artifact):
    assert artifact["phase_0_verification"]["status"] == "PASS"


def test_p194_phase0_db_rows(artifact):
    assert artifact["phase_0_verification"]["production_db_rows"] == 94924


def test_p194_phase0_tests(artifact):
    assert "865 passed" in artifact["phase_0_verification"]["p178a_to_p193_tests"]


def test_p194_phase0_drift_guard(artifact):
    assert "PASS" in artifact["phase_0_verification"]["drift_guard"]


def test_p194_phase0_no_stop_conditions(artifact):
    assert len(artifact["phase_0_verification"].get("stop_conditions_triggered", [])) == 0


# ── P193 reference ────────────────────────────────────────────────────────────

def test_p194_p193_classification_referenced(artifact):
    assert artifact.get("p193_classification_referenced") == "P193_PUSH_REJECTION_REMEDIATION_PLAN_READY"


# ── Large binary inventory ────────────────────────────────────────────────────

def test_p194_large_binary_inventory_exists(artifact):
    assert "large_binary_inventory" in artifact
    assert "binaries_in_p191_commit" in artifact["large_binary_inventory"]


def test_p194_production_db_in_inventory(artifact):
    files = artifact["large_binary_inventory"]["binaries_in_p191_commit"]
    paths = [f["path"] for f in files]
    assert "lottery_api/data/lottery_v2.db" in paths


def test_p194_backup_in_inventory(artifact):
    files = artifact["large_binary_inventory"]["binaries_in_p191_commit"]
    paths = [f["path"] for f in files]
    assert any("p188_lottery_v2_backup" in p for p in paths)


def test_p194_production_db_sha256(artifact):
    files = artifact["large_binary_inventory"]["binaries_in_p191_commit"]
    db = next(f for f in files if f["path"] == "lottery_api/data/lottery_v2.db")
    assert "a5ac27a6" in db["sha256"]
    assert db["size_bytes"] == 99368960


def test_p194_backup_sha256(artifact):
    files = artifact["large_binary_inventory"]["binaries_in_p191_commit"]
    bak = next(f for f in files if "p188_lottery_v2_backup" in f["path"] and f["path"].endswith(".db"))
    assert "5eea5313" in bak["sha256"]


def test_p194_sha256_file_kept(artifact):
    files = artifact["large_binary_inventory"]["binaries_in_p191_commit"]
    sha = next(f for f in files if f["path"].endswith(".sha256"))
    assert sha["remove_from_git"] is False


def test_p194_total_bytes_to_remove(artifact):
    total = artifact["large_binary_inventory"]["total_binary_bytes_to_remove"]
    assert total > 100_000_000  # > 100MB


# ── Binary removal strategy ───────────────────────────────────────────────────

def test_p194_removal_strategy_exists(artifact):
    assert "binary_removal_strategy" in artifact


def test_p194_preserve_local_db(artifact):
    strat = artifact["binary_removal_strategy"]
    assert strat["preserve_local_db"]["action"] != ""
    assert "NOT" in strat["preserve_local_db"]["action"].upper() or "MUST" in strat["preserve_local_db"]["action"].upper()


def test_p194_preserve_local_backup(artifact):
    strat = artifact["binary_removal_strategy"]
    assert "NOT" in strat["preserve_local_backup"]["action"].upper() or "MUST" in strat["preserve_local_backup"]["action"].upper()


def test_p194_manifest_plan_exists(artifact):
    strat = artifact["binary_removal_strategy"]
    manifest = strat.get("manifest_to_create_in_p195", {})
    assert manifest.get("path") is not None
    contents = manifest.get("contents", {})
    assert contents.get("production_db_rows") == 94924
    assert "a5ac27a6" in str(contents.get("production_db_sha256", ""))
    assert "5eea5313" in str(contents.get("backup_sha256", ""))


def test_p194_gitignore_entries(artifact):
    strat = artifact["binary_removal_strategy"]
    entries = strat.get("gitignore_entries_to_add", [])
    assert any("lottery_v2.db" in e for e in entries)
    assert any("backups/*.db" in e for e in entries)


# ── Candidate approaches 1-4 ─────────────────────────────────────────────────

def test_p194_approach_1_exists(artifact):
    approaches = artifact.get("candidate_execution_approaches", {})
    assert "approach_1" in approaches


def test_p194_approach_2_exists(artifact):
    approaches = artifact.get("candidate_execution_approaches", {})
    assert "approach_2" in approaches


def test_p194_approach_3_exists(artifact):
    approaches = artifact.get("candidate_execution_approaches", {})
    assert "approach_3" in approaches


def test_p194_approach_4_exists(artifact):
    approaches = artifact.get("candidate_execution_approaches", {})
    assert "approach_4" in approaches


def test_p194_approach_1_recommended(artifact):
    a1 = artifact["candidate_execution_approaches"]["approach_1"]
    assert "RECOMMENDED" in a1.get("recommendation", "").upper()


def test_p194_approach_1_steps_include_verify(artifact):
    a1 = artifact["candidate_execution_approaches"]["approach_1"]
    steps = str(a1.get("steps", []))
    assert "94924" in steps or "VERIFY" in steps


def test_p194_approach_1_preserve_db(artifact):
    a1 = artifact["candidate_execution_approaches"]["approach_1"]
    steps = str(a1.get("steps", []))
    assert "restore --staged" in steps or "unstage" in steps.lower()


# ── CTO recommendation ────────────────────────────────────────────────────────

def test_p194_cto_primary_approach_1(artifact):
    cto = artifact.get("cto_recommendation", {})
    primary = cto.get("primary_approach", "")
    assert "Approach 1" in primary or "SOFT_RESET" in primary


def test_p194_cto_do_not_push(artifact):
    cto = artifact.get("cto_recommendation", {})
    rules = str(cto.get("critical_safety_rules", []))
    assert "push" in rules.lower()


def test_p194_cto_do_not_delete_db(artifact):
    cto = artifact.get("cto_recommendation", {})
    rules = str(cto.get("critical_safety_rules", []))
    assert "rm --cached" in rules or "delete" in rules.lower() or "NOT" in rules


def test_p194_cto_gitignore_note(artifact):
    cto = artifact.get("cto_recommendation", {})
    note = cto.get("gitignore_importance", "")
    assert len(note) > 20


# ── Governance confirmations ──────────────────────────────────────────────────

def test_p194_no_db_write(artifact):
    assert artifact["governance_confirmations"]["no_db_write"] is True


def test_p194_no_db_delete(artifact):
    assert artifact["governance_confirmations"]["no_db_delete"] is True


def test_p194_no_backup_delete(artifact):
    assert artifact["governance_confirmations"]["no_backup_delete"] is True


def test_p194_no_commit_rewrite(artifact):
    assert artifact["governance_confirmations"]["no_commit_rewrite"] is True


def test_p194_no_amend(artifact):
    assert artifact["governance_confirmations"]["no_amend"] is True


def test_p194_no_reset(artifact):
    assert artifact["governance_confirmations"]["no_reset"] is True


def test_p194_no_branch_creation(artifact):
    assert artifact["governance_confirmations"]["no_branch_creation"] is True


def test_p194_no_stage(artifact):
    assert artifact["governance_confirmations"]["no_stage"] is True


def test_p194_no_commit(artifact):
    assert artifact["governance_confirmations"]["no_commit"] is True


def test_p194_no_push(artifact):
    assert artifact["governance_confirmations"]["no_push"] is True


def test_p194_no_force_push(artifact):
    assert artifact["governance_confirmations"]["no_force_push"] is True


def test_p194_power_lotto_closed(artifact):
    assert artifact["governance_confirmations"]["power_lotto_research_closed"] is True


def test_p194_db_preserved(artifact):
    assert artifact["governance_confirmations"]["migrated_db_local_state_preserved"] is True


def test_p194_db_rows_confirmed(artifact):
    assert artifact["governance_confirmations"]["production_db_rows"] == 94924


def test_p194_p191_intact(artifact):
    assert artifact["governance_confirmations"]["p191_local_commit_intact"] is True


def test_p194_blocked_by_authorization(artifact):
    assert artifact.get("next_task_blocked_by_user_authorization") is True


# ── P195 options ──────────────────────────────────────────────────────────────

def test_p194_p195_options_exist(artifact):
    opts = artifact.get("next_task_options", [])
    assert len(opts) >= 4


def test_p194_p195_option_execution(artifact):
    opts = artifact.get("next_task_options", [])
    assert any("P195" in o for o in opts)


def test_p194_p195_option_rollback(artifact):
    opts = artifact.get("next_task_options", [])
    assert any("rollback" in o.lower() for o in opts)


# ── MD checks ─────────────────────────────────────────────────────────────────

def test_p194_md_classification(md_text):
    assert "P194_REMOVE_DB_BINARIES_FROM_LOCAL_COMMIT_PLAN_READY" in md_text


def test_p194_md_approach_1(md_text):
    assert "Approach 1" in md_text


def test_p194_md_sha256(md_text):
    assert "a5ac27a6" in md_text


def test_p194_md_manifest(md_text):
    assert "manifest" in md_text.lower()


def test_p194_md_gitignore(md_text):
    assert ".gitignore" in md_text


def test_p194_md_no_wagering(md_text):
    text_lower = md_text.lower()
    for phrase in ["wagering advice", "guaranteed win", "predict and win"]:
        assert phrase not in text_lower


def test_p194_md_p195_options(md_text):
    assert "P195" in md_text


# ── Roadmap checks ────────────────────────────────────────────────────────────

def test_p194_active_task_p194_ready():
    with open(ACTIVE_TASK_PATH) as f:
        content = f.read()
    assert "P194" in content
    assert ("READY" in content or "COMPLETE" in content)


def test_p194_active_task_p195_blocked():
    with open(ACTIVE_TASK_PATH) as f:
        content = f.read()
    assert "P195" in content
    assert "BLOCKED" in content


def test_p194_active_task_db_rows():
    with open(ACTIVE_TASK_PATH) as f:
        content = f.read()
    assert "94924" in content


def test_p194_roadmap_p194_entry():
    with open(ROADMAP_PATH) as f:
        content = f.read()
    assert "P194" in content


def test_p194_roadmap_p195_blocked():
    with open(ROADMAP_PATH) as f:
        content = f.read()
    assert "P195" in content
    assert "BLOCKED" in content or "deferred" in content.lower()


def test_p194_roadmap_power_lotto_closed():
    with open(ROADMAP_PATH) as f:
        content = f.read()
    assert "CLOSED" in content or "closed" in content.lower()


def test_p194_cto_p194_entry():
    with open(CTO_PATH) as f:
        content = f.read()
    assert "P194" in content


def test_p194_cto_p195_recommendation():
    with open(CTO_PATH) as f:
        content = f.read()
    assert "P195" in content


def test_p194_cto_no_deployment_claim():
    with open(CTO_PATH) as f:
        content = f.read()
    text_lower = content.lower()
    for phrase in ["guaranteed win", "predict and win"]:
        assert phrase not in text_lower
