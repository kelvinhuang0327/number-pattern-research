"""
P73 Local DB Recovery Guard + Apply Authorization Hardening
Governance test suite — READINESS_ONLY, no production DB writes.
"""

import json
import os

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSON_PATH = os.path.join(
    REPO_ROOT,
    "outputs",
    "replay",
    "p73_local_db_recovery_guard_apply_auth_hardening_20260526.json",
)
DOC_PATH = os.path.join(
    REPO_ROOT,
    "docs",
    "replay",
    "p73_local_db_recovery_guard_apply_auth_hardening_20260526.md",
)


@pytest.fixture(scope="module")
def artifact():
    with open(JSON_PATH, "r") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# File existence
# ---------------------------------------------------------------------------


def test_json_artifact_exists():
    assert os.path.exists(JSON_PATH), f"JSON artifact not found: {JSON_PATH}"


def test_doc_artifact_exists():
    assert os.path.exists(DOC_PATH), f"Doc artifact not found: {DOC_PATH}"


# ---------------------------------------------------------------------------
# Project context lock
# ---------------------------------------------------------------------------


def test_project_context_lock(artifact):
    assert artifact["project_context_lock"] == "LotteryNew"


def test_task_name(artifact):
    assert artifact["task"] == "P73_LOCAL_DB_RECOVERY_GUARD_APPLY_AUTH_HARDENING"


def test_authorization_mode_readiness_only(artifact):
    assert artifact["authorization_mode"] == "READINESS_ONLY"


# ---------------------------------------------------------------------------
# Production rows invariant
# ---------------------------------------------------------------------------


def test_production_rows_before(artifact):
    assert artifact["production_rows_before"] == 46960


def test_production_rows_after(artifact):
    assert artifact["production_rows_after"] == 46960


def test_rows_unchanged(artifact):
    assert artifact["production_rows_before"] == artifact["production_rows_after"]


# ---------------------------------------------------------------------------
# P72 incident
# ---------------------------------------------------------------------------


def test_p72_incident_exists(artifact):
    assert "p72_incident" in artifact
    assert isinstance(artifact["p72_incident"], dict)


def test_p72_incident_classification(artifact):
    assert artifact["p72_incident"]["classification"] == "46960_to_37960_then_recovered"


def test_p72_incident_rows_before(artifact):
    assert artifact["p72_incident"]["rows_before_incident"] == 46960


def test_p72_incident_rows_after(artifact):
    assert artifact["p72_incident"]["rows_after_incident"] == 37960


def test_p72_incident_row_delta(artifact):
    assert artifact["p72_incident"]["row_delta"] == -9000


def test_p72_incident_trigger(artifact):
    assert "git reset --hard" in artifact["p72_incident"]["trigger"]


def test_p72_incident_recovery_result(artifact):
    result = artifact["p72_incident"]["recovery_result"]
    assert "46960" in result
    assert "PASS" in result


def test_p72_incident_recovery_steps(artifact):
    steps = artifact["p72_incident"]["recovery_steps"]
    assert isinstance(steps, list)
    assert len(steps) >= 3
    assert any("bak_p59" in s for s in steps)
    assert any("p59_powerlotto" in s for s in steps)
    assert any("p66_wave6" in s for s in steps)


# ---------------------------------------------------------------------------
# Root cause
# ---------------------------------------------------------------------------


def test_root_cause_present(artifact):
    assert "root_cause" in artifact
    assert "lottery_api/data/lottery_v2.db" in artifact["root_cause"]
    assert "git reset --hard" in artifact["root_cause"]


# ---------------------------------------------------------------------------
# Prohibited commands
# ---------------------------------------------------------------------------


def test_prohibited_commands_exists(artifact):
    assert "prohibited_commands" in artifact
    assert isinstance(artifact["prohibited_commands"], list)
    assert len(artifact["prohibited_commands"]) >= 2


def test_prohibited_commands_includes_reset_hard(artifact):
    cmds = artifact["prohibited_commands"]
    assert any("git reset --hard" in c for c in cmds)


def test_prohibited_commands_includes_git_clean(artifact):
    cmds = artifact["prohibited_commands"]
    assert any("git clean" in c for c in cmds)


# ---------------------------------------------------------------------------
# Pre-apply backup gate
# ---------------------------------------------------------------------------


def test_required_pre_apply_backup_gate_exists(artifact):
    assert "required_pre_apply_backup_gate" in artifact
    gate = artifact["required_pre_apply_backup_gate"]
    assert isinstance(gate, dict)


def test_pre_apply_backup_gate_steps(artifact):
    steps = artifact["required_pre_apply_backup_gate"]["steps"]
    assert isinstance(steps, list)
    assert len(steps) >= 5


def test_pre_apply_backup_gate_abort_conditions(artifact):
    abort = artifact["required_pre_apply_backup_gate"]["abort_conditions"]
    assert isinstance(abort, list)
    assert any("46960" in c for c in abort)


def test_pre_apply_backup_gate_mentions_row_count(artifact):
    gate_str = json.dumps(artifact["required_pre_apply_backup_gate"])
    assert "46960" in gate_str


# ---------------------------------------------------------------------------
# Safe post-merge verification
# ---------------------------------------------------------------------------


def test_safe_post_merge_verification_exists(artifact):
    assert "safe_post_merge_verification" in artifact
    assert isinstance(artifact["safe_post_merge_verification"], dict)


def test_safe_post_merge_verification_forbids_reset_hard(artifact):
    section = artifact["safe_post_merge_verification"]
    forbidden = section.get("forbidden_commands", [])
    assert any("git reset --hard" in c for c in forbidden)


def test_safe_post_merge_verification_has_preferred_commands(artifact):
    section = artifact["safe_post_merge_verification"]
    preferred = section.get("preferred_commands", [])
    assert isinstance(preferred, list)
    assert len(preferred) >= 2
    assert any("git fetch" in c for c in preferred)


# ---------------------------------------------------------------------------
# Apply authorization gate
# ---------------------------------------------------------------------------


def test_apply_authorization_gate_exists(artifact):
    assert "apply_authorization_gate" in artifact
    gate = artifact["apply_authorization_gate"]
    assert isinstance(gate, dict)


def test_apply_authorization_gate_includes_required_phrase(artifact):
    phrase = artifact["apply_authorization_gate"]["required_phrase"]
    assert phrase == "YES apply P71 controlled replay rows"


def test_apply_authorization_gate_has_additional_requirements(artifact):
    reqs = artifact["apply_authorization_gate"]["additional_requirements"]
    assert isinstance(reqs, list)
    assert len(reqs) >= 3


# ---------------------------------------------------------------------------
# Recommended next apply scope
# ---------------------------------------------------------------------------


def test_recommended_next_apply_scope_exists(artifact):
    assert "recommended_next_apply_scope" in artifact
    scope = artifact["recommended_next_apply_scope"]
    assert isinstance(scope, dict)


def test_recommended_next_apply_scope_phase(artifact):
    assert artifact["recommended_next_apply_scope"]["phase"] == "P74"


def test_recommended_next_apply_scope_b2_b3_blocked(artifact):
    b2_b3_gate = artifact["recommended_next_apply_scope"]["b2_b3_gate"]
    assert "BLOCKED" in b2_b3_gate


def test_recommended_next_apply_scope_midfreq_fourier_gate(artifact):
    mf_gate = artifact["recommended_next_apply_scope"]["midfreq_fourier_2bet_gate"]
    assert "BLOCKED" in mf_gate
    assert "DAILY_539" in mf_gate


# ---------------------------------------------------------------------------
# Batch risk table
# ---------------------------------------------------------------------------


def test_batch_risk_table_exists(artifact):
    assert "batch_risk_table" in artifact
    table = artifact["batch_risk_table"]
    assert isinstance(table, list)
    assert len(table) == 4


def test_batch_a_not_blocked(artifact):
    batch_a = next(b for b in artifact["batch_risk_table"] if b["batch"] == "A")
    assert batch_a["blocked"] is False


def test_batch_b1_not_blocked(artifact):
    batch_b1 = next(b for b in artifact["batch_risk_table"] if b["batch"] == "B1")
    assert batch_b1["blocked"] is False


def test_batch_b2_blocked(artifact):
    batch_b2 = next(b for b in artifact["batch_risk_table"] if b["batch"] == "B2")
    assert batch_b2["blocked"] is True


def test_batch_b3_blocked(artifact):
    batch_b3 = next(b for b in artifact["batch_risk_table"] if b["batch"] == "B3")
    assert batch_b3["blocked"] is True


def test_batch_b2_midfreq_fourier_risk(artifact):
    batch_b2 = next(b for b in artifact["batch_risk_table"] if b["batch"] == "B2")
    assert "midfreq_fourier_2bet" in batch_b2.get("midfreq_fourier_2bet_extra_risk", "")
    assert "DAILY_539" in batch_b2.get("midfreq_fourier_2bet_extra_risk", "")


# ---------------------------------------------------------------------------
# Governance boolean flags
# ---------------------------------------------------------------------------


def test_no_db_write(artifact):
    assert artifact["no_db_write"] is True


def test_no_force_push(artifact):
    assert artifact["no_force_push"] is True


def test_no_reset_hard(artifact):
    assert artifact["no_reset_hard"] is True


def test_no_git_clean(artifact):
    assert artifact["no_git_clean"] is True


def test_no_lifecycle_promotion(artifact):
    assert artifact["no_lifecycle_promotion"] is True


def test_no_champion_replacement(artifact):
    assert artifact["no_champion_replacement"] is True


def test_no_registry_mutation(artifact):
    assert artifact["no_registry_mutation"] is True


def test_no_production_apply(artifact):
    assert artifact["no_production_apply"] is True


def test_requires_future_explicit_apply_authorization(artifact):
    assert artifact["requires_future_explicit_apply_authorization"] is True


# ---------------------------------------------------------------------------
# Final classification
# ---------------------------------------------------------------------------


def test_final_classification(artifact):
    assert (
        artifact["final_classification"]
        == "P73_LOCAL_DB_RECOVERY_GUARD_APPLY_AUTH_HARDENING_MERGED_TO_MAIN"
    )


# ---------------------------------------------------------------------------
# Doc content spot checks
# ---------------------------------------------------------------------------


def test_doc_contains_project_context_lock():
    with open(DOC_PATH, "r") as f:
        content = f.read()
    assert "PROJECT_CONTEXT_LOCK" in content
    assert "LotteryNew" in content


def test_doc_contains_p72_incident():
    with open(DOC_PATH, "r") as f:
        content = f.read()
    assert "P72 Incident" in content
    assert "git reset --hard" in content


def test_doc_contains_46960():
    with open(DOC_PATH, "r") as f:
        content = f.read()
    assert "46960" in content


def test_doc_contains_recovery_path():
    with open(DOC_PATH, "r") as f:
        content = f.read()
    assert "Recovery Path" in content or "recovery" in content.lower()


def test_doc_contains_no_db_write_confirmation():
    with open(DOC_PATH, "r") as f:
        content = f.read()
    assert "No DB write" in content or "no_db_write" in content


def test_doc_contains_final_classification():
    with open(DOC_PATH, "r") as f:
        content = f.read()
    assert "P73_LOCAL_DB_RECOVERY_GUARD_APPLY_AUTH_HARDENING_MERGED_TO_MAIN" in content


def test_doc_contains_yes_apply_phrase():
    with open(DOC_PATH, "r") as f:
        content = f.read()
    assert "YES apply P71 controlled replay rows" in content


def test_doc_contains_safe_post_merge_section():
    with open(DOC_PATH, "r") as f:
        content = f.read()
    assert "Safe Post-Merge" in content or "safe post-merge" in content.lower()
