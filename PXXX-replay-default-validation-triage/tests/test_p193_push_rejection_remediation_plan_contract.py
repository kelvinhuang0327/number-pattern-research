"""Contract test for P193 — Push Rejection Remediation Plan."""
import json
import os
import pytest

ARTIFACT_DIR = "outputs/research/power_lotto"
JSON_PATH = f"{ARTIFACT_DIR}/p193_push_rejection_remediation_plan_20260601.json"
MD_PATH = f"{ARTIFACT_DIR}/p193_push_rejection_remediation_plan_20260601.md"
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

def test_p193_json_exists():
    assert os.path.exists(JSON_PATH)


def test_p193_md_exists():
    assert os.path.exists(MD_PATH)


# ── Classification and authorization ─────────────────────────────────────────

def test_p193_final_classification(artifact):
    assert artifact["final_classification"] == "P193_PUSH_REJECTION_REMEDIATION_PLAN_READY"


def test_p193_authorization_phrase(artifact):
    assert "YES start P193 push rejection remediation plan only" in artifact.get("authorization_phrase_detected", "")


# ── Phase 0 ───────────────────────────────────────────────────────────────────

def test_p193_phase0_pass(artifact):
    assert artifact["phase_0_verification"]["status"] == "PASS"


def test_p193_phase0_db_rows(artifact):
    assert artifact["phase_0_verification"]["production_db_rows"] == 94924


def test_p193_phase0_bet_index(artifact):
    assert artifact["phase_0_verification"]["bet_index_present"] is True


def test_p193_phase0_tests(artifact):
    assert "797 passed" in artifact["phase_0_verification"]["p178a_to_p191_tests"]


def test_p193_phase0_drift_guard(artifact):
    assert "PASS" in artifact["phase_0_verification"]["drift_guard_result"]


def test_p193_phase0_no_stop_conditions(artifact):
    assert len(artifact["phase_0_verification"].get("stop_conditions_triggered", [])) == 0


# ── P192 rejection captured ───────────────────────────────────────────────────

def test_p193_p192_rejection_captured(artifact):
    rej = artifact.get("p192_rejection_summary", {})
    assert rej.get("p192_final_classification") == "P192_PUSH_REJECTED"


def test_p193_branch_protection_captured(artifact):
    rej = artifact["p192_rejection_summary"]
    errors = rej.get("rejection_errors", [])
    codes = [e.get("code") for e in errors]
    assert "GH006" in codes


def test_p193_required_check_captured(artifact):
    rej = artifact["p192_rejection_summary"]
    errors_str = str(rej.get("rejection_errors", []))
    assert "replay-default-validation" in errors_str


def test_p193_p191_commit_intact(artifact):
    assert artifact["p192_rejection_summary"]["p191_local_commit_intact"] is True
    assert "012d4a3" in artifact["p192_rejection_summary"]["p191_commit_hash"]


def test_p193_origin_unchanged(artifact):
    assert artifact["p192_rejection_summary"]["origin_main_unchanged"] is True


# ── Large binary inventory ────────────────────────────────────────────────────

def test_p193_large_binary_inventory_exists(artifact):
    lbi = artifact.get("large_binary_inventory", {})
    assert "tracked_binary_files" in lbi


def test_p193_production_db_in_inventory(artifact):
    files = artifact["large_binary_inventory"]["tracked_binary_files"]
    paths = [f["path"] for f in files]
    assert "lottery_api/data/lottery_v2.db" in paths


def test_p193_backup_in_inventory(artifact):
    files = artifact["large_binary_inventory"]["tracked_binary_files"]
    paths = [f["path"] for f in files]
    assert any("p188_lottery_v2_backup" in p for p in paths)


def test_p193_db_size_captured(artifact):
    files = artifact["large_binary_inventory"]["tracked_binary_files"]
    db_entry = next(f for f in files if f["path"] == "lottery_api/data/lottery_v2.db")
    assert db_entry["size_mb"] >= 90


def test_p193_github_limits_captured(artifact):
    limits = artifact["large_binary_inventory"]["github_limits"]
    assert limits["hard_limit_mb"] == 100
    assert limits["recommended_max_mb"] == 50


# ── Remediation options A-E ───────────────────────────────────────────────────

def test_p193_option_a_exists(artifact):
    opts = artifact.get("remediation_options", {})
    assert "option_A" in opts


def test_p193_option_b_exists(artifact):
    opts = artifact.get("remediation_options", {})
    assert "option_B" in opts


def test_p193_option_c_exists(artifact):
    opts = artifact.get("remediation_options", {})
    assert "option_C" in opts


def test_p193_option_d_exists(artifact):
    opts = artifact.get("remediation_options", {})
    assert "option_D" in opts


def test_p193_option_e_exists(artifact):
    opts = artifact.get("remediation_options", {})
    assert "option_E" in opts


def test_p193_option_b_recommended(artifact):
    opt_b = artifact["remediation_options"]["option_B"]
    rec = opt_b.get("recommendation", "")
    assert "RECOMMENDED" in rec.upper()


def test_p193_option_d_not_recommended(artifact):
    opt_d = artifact["remediation_options"]["option_D"]
    rec = opt_d.get("recommendation", "")
    assert "NOT" in rec.upper() or "not" in rec


def test_p193_option_b_db_preservation_note(artifact):
    opt_b = artifact["remediation_options"]["option_B"]
    guarantee = opt_b.get("db_preservation_guarantee", "")
    assert len(guarantee) > 20  # must have substantive preservation note


# ── CTO recommendation ────────────────────────────────────────────────────────

def test_p193_cto_primary_is_option_b(artifact):
    cto = artifact.get("cto_recommendation", {})
    primary = cto.get("primary", "")
    assert "Option B" in primary or "REMOVE" in primary.upper()


def test_p193_cto_do_not_contains_safety_rules(artifact):
    cto = artifact.get("cto_recommendation", {})
    do_not = str(cto.get("do_not", []))
    assert "force push" in do_not.lower() or "force-push" in do_not.lower()
    assert "branch protection" in do_not.lower() or "protection" in do_not.lower()


def test_p193_cto_db_governance_note(artifact):
    cto = artifact.get("cto_recommendation", {})
    note = cto.get("db_governance_note", "")
    assert "NOT" in note.upper() and ("delete" in note.lower() or "intact" in note.lower())


# ── Governance confirmations ──────────────────────────────────────────────────

def test_p193_no_db_write(artifact):
    assert artifact["governance_confirmations"]["no_db_write"] is True


def test_p193_no_stage(artifact):
    assert artifact["governance_confirmations"]["no_stage"] is True


def test_p193_no_commit(artifact):
    assert artifact["governance_confirmations"]["no_commit"] is True


def test_p193_no_push(artifact):
    assert artifact["governance_confirmations"]["no_push"] is True


def test_p193_no_force_push(artifact):
    assert artifact["governance_confirmations"]["no_force_push"] is True


def test_p193_no_branch_protection_bypass(artifact):
    assert artifact["governance_confirmations"]["no_branch_protection_bypass"] is True


def test_p193_no_commit_rewrite(artifact):
    assert artifact["governance_confirmations"]["no_commit_rewrite"] is True


def test_p193_power_lotto_closed(artifact):
    assert artifact["governance_confirmations"]["power_lotto_research_closed"] is True


def test_p193_db_migration_preserved(artifact):
    assert artifact["governance_confirmations"]["db_migration_local_state_preserved"] is True


def test_p193_db_rows_confirmed(artifact):
    assert artifact["governance_confirmations"]["production_db_rows"] == 94924


def test_p193_p191_commit_intact_confirmed(artifact):
    assert artifact["governance_confirmations"]["p191_local_commit_intact"] is True


def test_p193_blocked_by_authorization(artifact):
    assert artifact.get("next_task_blocked_by_user_authorization") is True


# ── P194 options ──────────────────────────────────────────────────────────────

def test_p193_p194_options_exist(artifact):
    opts = artifact.get("next_task_options", [])
    assert len(opts) >= 4


def test_p193_p194_option_remove_binaries(artifact):
    opts = artifact.get("next_task_options", [])
    assert any("remove DB binaries" in o or "remove db binaries" in o.lower() for o in opts)


def test_p193_p194_option_pr(artifact):
    opts = artifact.get("next_task_options", [])
    assert any("PR" in o or "pull request" in o.lower() for o in opts)


def test_p193_p194_option_rollback(artifact):
    opts = artifact.get("next_task_options", [])
    assert any("rollback" in o.lower() for o in opts)


# ── MD checks ─────────────────────────────────────────────────────────────────

def test_p193_md_classification(md_text):
    assert "P193_PUSH_REJECTION_REMEDIATION_PLAN_READY" in md_text


def test_p193_md_phase0_pass(md_text):
    assert "PASS" in md_text


def test_p193_md_rejection_summary(md_text):
    assert "P192_PUSH_REJECTED" in md_text or "PUSH_REJECTED" in md_text


def test_p193_md_gh006(md_text):
    assert "GH006" in md_text


def test_p193_md_replay_default_validation(md_text):
    assert "replay-default-validation" in md_text


def test_p193_md_binary_size(md_text):
    assert "96" in md_text or "94" in md_text  # DB size
    assert "51" in md_text or "50" in md_text  # backup size


def test_p193_md_option_b_recommended(md_text):
    assert "RECOMMENDED" in md_text


def test_p193_md_no_force_push(md_text):
    text_lower = md_text.lower()
    assert "force push" in text_lower or "force-push" in text_lower


def test_p193_md_p194_options(md_text):
    assert "P194" in md_text


def test_p193_md_no_wagering(md_text):
    text_lower = md_text.lower()
    for phrase in ["wagering advice", "guaranteed win", "predict and win"]:
        assert phrase not in text_lower


# ── Roadmap doc checks ────────────────────────────────────────────────────────

def test_p193_active_task_p193_ready():
    with open(ACTIVE_TASK_PATH) as f:
        content = f.read()
    assert "P193" in content
    assert "READY" in content or "COMPLETE" in content


def test_p193_active_task_p194_blocked():
    with open(ACTIVE_TASK_PATH) as f:
        content = f.read()
    assert "P194" in content
    assert "BLOCKED" in content


def test_p193_active_task_push_rejected():
    with open(ACTIVE_TASK_PATH) as f:
        content = f.read()
    assert "REJECTED" in content or "rejected" in content or "P192" in content


def test_p193_active_task_db_rows():
    with open(ACTIVE_TASK_PATH) as f:
        content = f.read()
    assert "94924" in content


def test_p193_roadmap_p193_entry():
    with open(ROADMAP_PATH) as f:
        content = f.read()
    assert "P193" in content


def test_p193_roadmap_p192_rejected():
    with open(ROADMAP_PATH) as f:
        content = f.read()
    assert "P192" in content
    assert "REJECTED" in content or "rejected" in content


def test_p193_roadmap_remote_not_reconciled():
    with open(ROADMAP_PATH) as f:
        content = f.read()
    assert "P194" in content
    assert "BLOCKED" in content or "deferred" in content.lower()


def test_p193_roadmap_power_lotto_closed():
    with open(ROADMAP_PATH) as f:
        content = f.read()
    assert "CLOSED" in content or "closed" in content.lower()


def test_p193_cto_p193_entry():
    with open(CTO_PATH) as f:
        content = f.read()
    assert "P193" in content


def test_p193_cto_p194_recommendation():
    with open(CTO_PATH) as f:
        content = f.read()
    assert "P194" in content


def test_p193_cto_no_deployment_claim():
    with open(CTO_PATH) as f:
        content = f.read()
    text_lower = content.lower()
    for phrase in ["guaranteed win", "predict and win"]:
        assert phrase not in text_lower
