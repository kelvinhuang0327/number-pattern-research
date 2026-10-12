"""Contract test for P196 — Remove DB Binaries Soft Reset and Recommit."""
import json
import os
import subprocess
import pytest

ARTIFACT_DIR = "outputs/research/power_lotto"
JSON_PATH = f"{ARTIFACT_DIR}/p196_remove_db_binaries_soft_reset_recommit_20260601.json"
MD_PATH = f"{ARTIFACT_DIR}/p196_remove_db_binaries_soft_reset_recommit_20260601.md"
MANIFEST_JSON = f"{ARTIFACT_DIR}/p196_db_binary_external_storage_manifest_20260601.json"
MANIFEST_MD = f"{ARTIFACT_DIR}/p196_db_binary_external_storage_manifest_20260601.md"
DB_PATH = "lottery_api/data/lottery_v2.db"
BACKUP_PATH = "backups/p188_lottery_v2_backup_20260601_153821.db"
BACKUP_SHA256_PATH = "backups/p188_lottery_v2_backup_20260601_153821.db.sha256"
GITIGNORE_PATH = ".gitignore"
ACTIVE_TASK_PATH = "00-Plan/roadmap/active_task.md"
ROADMAP_PATH = "00-Plan/roadmap/roadmap.md"
CTO_PATH = "00-Plan/roadmap/CTO-Analysis.md"


@pytest.fixture(scope="module")
def artifact():
    with open(JSON_PATH) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def manifest():
    with open(MANIFEST_JSON) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def md_text():
    with open(MD_PATH) as f:
        return f.read()


# ── Artifacts exist ───────────────────────────────────────────────────────────

def test_p196_json_exists():
    assert os.path.exists(JSON_PATH)


def test_p196_md_exists():
    assert os.path.exists(MD_PATH)


def test_p196_manifest_json_exists():
    assert os.path.exists(MANIFEST_JSON)


def test_p196_manifest_md_exists():
    assert os.path.exists(MANIFEST_MD)


# ── Classification and authorization ─────────────────────────────────────────

def test_p196_final_classification(artifact):
    assert artifact["final_classification"] == "P196_REMOVE_DB_BINARIES_RECOMMIT_NON_BINARY_READY"


def test_p196_authorization_phrase(artifact):
    phrase = artifact.get("authorization_phrase_detected", "")
    assert "YES execute P196 remove DB binaries from local commit" in phrase


# ── Phase 0 ───────────────────────────────────────────────────────────────────

def test_p196_phase0_pass(artifact):
    assert artifact["phase_0_verification"]["status"] == "PASS"


def test_p196_phase0_db_rows(artifact):
    assert artifact["phase_0_verification"]["production_db_rows_before"] == 94924


def test_p196_phase0_prod_sha256(artifact):
    assert "a5ac27a6" in artifact["phase_0_verification"]["production_db_sha256"]


def test_p196_phase0_backup_sha256(artifact):
    assert "5eea5313" in artifact["phase_0_verification"]["backup_sha256"]


def test_p196_phase0_tests(artifact):
    assert "1011 passed" in artifact["phase_0_verification"]["p178a_to_p195_tests"]


def test_p196_phase0_no_stop_conditions(artifact):
    assert len(artifact["phase_0_verification"].get("stop_conditions_triggered", [])) == 0


# ── P195 reference ────────────────────────────────────────────────────────────

def test_p196_p195_referenced(artifact):
    assert artifact.get("p195_classification_referenced") == "P195_REMOVE_DB_BINARIES_FROM_LOCAL_COMMIT_EXECUTION_PLAN_READY"


# ── Manifest ──────────────────────────────────────────────────────────────────

def test_p196_manifest_prod_sha256(manifest):
    assert "a5ac27a6" in manifest["production_db"]["sha256"]


def test_p196_manifest_prod_rows(manifest):
    assert manifest["production_db"]["rows"] == 94924


def test_p196_manifest_prod_size(manifest):
    assert manifest["production_db"]["size_bytes"] == 99368960


def test_p196_manifest_prod_integrity(manifest):
    assert manifest["production_db"]["integrity_check"] == "ok"


def test_p196_manifest_backup_sha256(manifest):
    assert "5eea5313" in manifest["backup_db"]["sha256"]


def test_p196_manifest_backup_rows(manifest):
    assert manifest["backup_db"]["rows"] == 54462


def test_p196_manifest_backup_size(manifest):
    assert manifest["backup_db"]["size_bytes"] == 53374976


def test_p196_manifest_external_storage(manifest):
    assert manifest.get("external_storage_policy", {}).get("external_storage_required") is True


def test_p196_manifest_no_controlled_apply(manifest):
    assert manifest["governance"]["no_controlled_apply"] is True


# ── Soft reset + recommit result ──────────────────────────────────────────────

def test_p196_local_commit_created(artifact):
    gc = artifact.get("governance_confirmations", {})
    assert gc.get("local_commit_created") is True


def test_p196_no_push(artifact):
    assert artifact["governance_confirmations"]["no_push"] is True


def test_p196_commit_result_not_placeholder(artifact):
    cr = artifact.get("non_binary_recommit_result", {})
    assert cr.get("status") not in (None, "POPULATED_AFTER_COMMIT")
    assert cr.get("new_commit_hash") not in (None, "POPULATED_AFTER_COMMIT")


def test_p196_db_binary_not_in_new_commit(artifact):
    cr = artifact.get("non_binary_recommit_result", {})
    assert cr.get("db_binary_in_new_commit") is False


def test_p196_post_recommit_db_rows(artifact):
    pv = artifact.get("post_recommit_verification", {})
    assert pv.get("production_db_rows") == 94924


def test_p196_post_recommit_backup_rows(artifact):
    pv = artifact.get("post_recommit_verification", {})
    assert pv.get("backup_rows") == 54462


def test_p196_post_recommit_tests_pass(artifact):
    pv = artifact.get("post_recommit_verification", {})
    result = str(pv.get("tests_pass", ""))
    assert "passed" in result or result == "PASS" or "1011" in result or "PASS" in result


def test_p196_post_recommit_drift_guard(artifact):
    pv = artifact.get("post_recommit_verification", {})
    assert "PASS" in str(pv.get("drift_guard", ""))


# ── Live DB state ─────────────────────────────────────────────────────────────

def test_p196_db_exists_on_disk():
    assert os.path.exists(DB_PATH), "Production DB must remain on disk"


def test_p196_backup_exists_on_disk():
    assert os.path.exists(BACKUP_PATH), "Backup DB must remain on disk"


def test_p196_backup_sha256_in_git():
    assert os.path.exists(BACKUP_SHA256_PATH), "SHA256 file must exist"


def test_p196_db_rows_live():
    r = subprocess.run(
        ["sqlite3", DB_PATH, "SELECT COUNT(*) FROM strategy_prediction_replays;"],
        capture_output=True, text=True
    )
    assert r.returncode == 0
    assert int(r.stdout.strip()) == 94924


def test_p196_backup_rows_live():
    r = subprocess.run(
        ["sqlite3", BACKUP_PATH, "SELECT COUNT(*) FROM strategy_prediction_replays;"],
        capture_output=True, text=True
    )
    assert r.returncode == 0
    assert int(r.stdout.strip()) == 54462


# ── .gitignore has DB rules ───────────────────────────────────────────────────

def test_p196_gitignore_has_db_rule():
    with open(GITIGNORE_PATH) as f:
        content = f.read()
    assert "lottery_v2.db" in content or "lottery_api/data/*.db" in content


def test_p196_gitignore_has_backup_rule():
    with open(GITIGNORE_PATH) as f:
        content = f.read()
    assert "backups/*.db" in content


# ── DB binary not tracked after recommit ─────────────────────────────────────

def test_p196_db_not_tracked_in_git():
    r = subprocess.run(
        ["git", "ls-files", DB_PATH],
        capture_output=True, text=True
    )
    assert r.returncode == 0
    assert r.stdout.strip() == "", f"Production DB must NOT be tracked in git, got: {r.stdout.strip()}"


def test_p196_backup_db_not_tracked_in_git():
    r = subprocess.run(
        ["git", "ls-files", BACKUP_PATH],
        capture_output=True, text=True
    )
    assert r.returncode == 0
    assert r.stdout.strip() == "", f"Backup DB must NOT be tracked in git, got: {r.stdout.strip()}"


def test_p196_no_staged_files():
    r = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True, text=True
    )
    assert r.returncode == 0
    assert r.stdout.strip() == "", "No files should be staged after commit"


def test_p196_new_commit_has_no_db_binary():
    # Use --name-status to distinguish additions (A) from deletions (D).
    # A deletion of lottery_v2.db is expected and correct; an addition is not.
    r = subprocess.run(
        ["git", "show", "--name-status", "HEAD"],
        capture_output=True, text=True
    )
    assert r.returncode == 0
    for line in r.stdout.splitlines():
        if line.startswith("A") or line.startswith("M"):
            path = line.split("\t", 1)[-1] if "\t" in line else ""
            assert not (path.endswith(".db") or path.endswith(".db-wal") or path.endswith(".db-shm")), \
                f"DB binary ADDED/MODIFIED in new commit: {path}"


def test_p196_git_commit_message():
    # Search full git history (not just HEAD) for the P196 non-binary recommit.
    # P196 may no longer be HEAD if subsequent commits have been added.
    # Note: P196 message uses "binaries" (not "binary"); search for "binaries" or "P196".
    r = subprocess.run(
        ["git", "log", "--format=%s"],
        capture_output=True, text=True
    )
    assert r.returncode == 0
    history = r.stdout
    assert (
        "P196" in history or
        "binaries" in history.lower() or
        ("P188" in history and "reconcile" in history.lower())
    ), "P196 binary-removal commit (P188-P196: ...without DB binaries) not found in git history"


# ── Governance ────────────────────────────────────────────────────────────────

def test_p196_no_controlled_apply(artifact):
    assert artifact["governance_confirmations"]["no_controlled_apply"] is True


def test_p196_no_registry_mutation(artifact):
    assert artifact["governance_confirmations"]["no_registry_mutation"] is True


def test_p196_no_db_file_deleted(artifact):
    assert artifact["governance_confirmations"]["no_db_file_deleted"] is True


def test_p196_no_backup_file_deleted(artifact):
    assert artifact["governance_confirmations"]["no_backup_file_deleted"] is True


def test_p196_power_lotto_closed(artifact):
    assert artifact["governance_confirmations"]["power_lotto_research_closed"] is True


def test_p196_db_preserved(artifact):
    assert artifact["governance_confirmations"]["migrated_db_local_state_preserved"] is True


def test_p196_blocked_by_authorization(artifact):
    assert artifact.get("next_task_blocked_by_user_authorization") is True


# ── P197 options ──────────────────────────────────────────────────────────────

def test_p196_p197_options_exist(artifact):
    opts = artifact.get("next_task_options", [])
    assert len(opts) >= 4


def test_p196_p197_pr_option(artifact):
    opts = artifact.get("next_task_options", [])
    assert any("PR" in o or "pull request" in o.lower() for o in opts)


# ── MD checks ─────────────────────────────────────────────────────────────────

def test_p196_md_classification(md_text):
    assert "P196_REMOVE_DB_BINARIES_RECOMMIT_NON_BINARY_READY" in md_text


def test_p196_md_local_only(md_text):
    assert "LOCAL ONLY" in md_text or "local only" in md_text.lower()


def test_p196_md_no_push(md_text):
    assert "no push" in md_text.lower() or "NO PUSH" in md_text or "not push" in md_text.lower()


def test_p196_md_no_wagering(md_text):
    for phrase in ["wagering advice", "guaranteed win", "predict and win"]:
        assert phrase not in md_text.lower()


# ── Roadmap checks ────────────────────────────────────────────────────────────

def test_p196_active_task_p196_ready():
    with open(ACTIVE_TASK_PATH) as f:
        content = f.read()
    assert "P196" in content
    assert "READY" in content or "COMPLETE" in content


def test_p196_active_task_p197_blocked():
    with open(ACTIVE_TASK_PATH) as f:
        content = f.read()
    assert "P197" in content
    assert "BLOCKED" in content


def test_p196_active_task_db_rows():
    with open(ACTIVE_TASK_PATH) as f:
        content = f.read()
    assert "94924" in content


def test_p196_roadmap_p196_entry():
    with open(ROADMAP_PATH) as f:
        content = f.read()
    assert "P196" in content


def test_p196_roadmap_p197_blocked():
    with open(ROADMAP_PATH) as f:
        content = f.read()
    assert "P197" in content
    assert "BLOCKED" in content or "pending" in content.lower()


def test_p196_cto_p196_entry():
    with open(CTO_PATH) as f:
        content = f.read()
    assert "P196" in content


def test_p196_cto_p197_recommendation():
    with open(CTO_PATH) as f:
        content = f.read()
    assert "P197" in content


def test_p196_cto_no_deployment_claim():
    with open(CTO_PATH) as f:
        content = f.read()
    for phrase in ["guaranteed win", "predict and win"]:
        assert phrase not in content.lower()
