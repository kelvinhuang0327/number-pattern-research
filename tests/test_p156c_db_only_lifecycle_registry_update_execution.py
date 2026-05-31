"""Tests for P156C DB_ONLY lifecycle registry update execution."""

import importlib
import json
import subprocess
from pathlib import Path

import pytest

REPO_ROOT     = Path(__file__).parent.parent
ARTIFACT_PATH = REPO_ROOT / "outputs/replay/p156c_db_only_lifecycle_registry_update_execution_20260529.json"

CANONICAL_REPO   = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802"
CANONICAL_BRANCH = "claude/zen-gates-ff6802"
EXPECTED_DB_ROWS = 94924

VALID_CLASSIFICATIONS = {
    "P156C_DB_ONLY_LIFECYCLE_REGISTRY_UPDATE_APPLIED",
    "P156C_PARTIAL_DB_ONLY_LIFECYCLE_REGISTRY_UPDATE_APPLIED",
    "P156C_STOP_AUTHORIZATION_PHRASE_MISSING",
    "P156C_STOP_PREFLIGHT_MISMATCH",
}

EXPECTED_ONLINE_AFTER = {
    "biglotto_echo_aware_3bet", "biglotto_ts3_markov_4bet_w30",
    "daily539_f4cold_3bet", "daily539_f4cold_5bet",
    "power_fourier_rhythm_2bet", "midfreq_fourier_mk_3bet", "pp3_freqort_4bet",
    "cold_complement_2bet", "zonal_entropy_2bet", "fourier30_markov30_2bet",
}

EXPECTED_RETIRED_FROM_DB_ONLY = {
    "539_3bet_orthogonal", "acb_single_539", "markov_1bet_539",
    "p0b_539_3bet_f_cold_fmid", "p0c_539_3bet_f_cold_x2", "zone_gap_3bet_539",
    "bet2_fourier_expansion_biglotto", "cold_complement_biglotto", "coldpool15_biglotto",
    "markov_2bet_biglotto", "markov_single_biglotto", "fourier30_markov30_biglotto",
}


@pytest.fixture(scope="module")
def artifact():
    assert ARTIFACT_PATH.exists()
    return json.loads(ARTIFACT_PATH.read_text())


@pytest.fixture(scope="module")
def registry():
    import sys
    sys.path.insert(0, str(REPO_ROOT))
    import lottery_api.models.replay_strategy_registry as reg_mod
    importlib.reload(reg_mod)
    return {s["strategy_id"]: s["lifecycle_status"]
            for s in reg_mod.list_strategy_lifecycle_metadata()}


@pytest.fixture(scope="module")
def ba_matrix(artifact):
    return {m["strategy_id"]: m for m in artifact["lifecycle_before_after_matrix"]}


# ── Artifact basics ───────────────────────────────────────────────────────────

def test_artifact_exists():
    assert ARTIFACT_PATH.exists()


def test_task_id(artifact):
    assert artifact["task_id"] == "P156C"


def test_classification_valid(artifact):
    assert artifact["classification"] in VALID_CLASSIFICATIONS


def test_repo_ok(artifact):
    assert artifact["repo_branch_check"]["repo_ok"] is True


def test_branch_ok(artifact):
    assert artifact["repo_branch_check"]["branch_ok"] is True


def test_db_rows(artifact):
    assert artifact["db_snapshot"]["rows"] == EXPECTED_DB_ROWS


def test_db_match(artifact):
    assert artifact["db_snapshot"]["match"] is True


def test_drift_guard_pass(artifact):
    assert artifact["drift_guard_status"] == "PASS"


def test_p156b_ok(artifact):
    assert artifact["p156b_source_summary"]["ok"] is True


def test_p156_ok(artifact):
    assert artifact["p156_source_summary"]["ok"] is True


# ── Authorization parse ───────────────────────────────────────────────────────

def test_authorization_present(artifact):
    assert artifact["authorization_parse_result"]["authorization_present"] is True


def test_valid_auth_count_7(artifact):
    assert artifact["authorization_parse_result"]["valid_authorization_count"] == 7


def test_invalid_auth_count_zero(artifact):
    assert artifact["authorization_parse_result"]["invalid_authorization_count"] == 0


def test_authorized_22_strategies(artifact):
    assert len(artifact["authorization_parse_result"]["authorized_strategy_ids"]) == 22


# ── Registry update result ────────────────────────────────────────────────────

def test_registry_file_modified(artifact):
    cls = artifact["classification"]
    if cls == "P156C_DB_ONLY_LIFECYCLE_REGISTRY_UPDATE_APPLIED":
        assert artifact["registry_update_execution_result"]["registry_file_modified"] is True


def test_update_count_22(artifact):
    assert artifact["registry_update_execution_result"]["update_count"] == 22


def test_no_db_write_performed(artifact):
    assert artifact["registry_update_execution_result"]["db_write_performed"] is False


def test_online_count_18(artifact):
    counts = artifact["registry_update_execution_result"]["post_update_lifecycle_counts"]
    assert counts.get("ONLINE") == 18


def test_retired_count_17(artifact):
    counts = artifact["registry_update_execution_result"]["post_update_lifecycle_counts"]
    assert counts.get("RETIRED") == 17


def test_db_only_count_zero(artifact):
    counts = artifact["registry_update_execution_result"]["post_update_lifecycle_counts"]
    assert counts.get("DB_ONLY_MISSING_LIFECYCLE", 0) == 0


# ── Before/after matrix ───────────────────────────────────────────────────────

def test_ba_matrix_has_22(artifact):
    assert len(artifact["lifecycle_before_after_matrix"]) == 22


def test_all_before_was_db_only(ba_matrix):
    for sid, m in ba_matrix.items():
        assert m["lifecycle_before"] == "DB_ONLY_MISSING_LIFECYCLE"


def test_group_a_after_online(ba_matrix):
    for sid in EXPECTED_ONLINE_AFTER:
        if sid in ba_matrix:
            assert ba_matrix[sid]["lifecycle_after"] == "ONLINE", f"{sid} not ONLINE"


def test_retired_after_correct(ba_matrix):
    for sid in EXPECTED_RETIRED_FROM_DB_ONLY:
        if sid in ba_matrix:
            assert ba_matrix[sid]["lifecycle_after"] == "RETIRED", f"{sid} not RETIRED"


def test_all_authorized_changed(ba_matrix):
    for sid, m in ba_matrix.items():
        assert m["authorized"] is True
        assert m["changed"] is True, f"{sid}: expected changed=True"


# ── Actual registry state ─────────────────────────────────────────────────────

def test_registry_no_db_only_remaining(registry):
    db_only = [sid for sid, lc in registry.items() if lc == "DB_ONLY_MISSING_LIFECYCLE"]
    assert db_only == [], f"DB_ONLY_MISSING_LIFECYCLE still present: {db_only}"


def test_registry_new_online_strategies(registry):
    for sid in EXPECTED_ONLINE_AFTER:
        assert registry.get(sid) == "ONLINE", f"{sid}: expected ONLINE, got {registry.get(sid)}"


def test_registry_retired_strategies(registry):
    for sid in EXPECTED_RETIRED_FROM_DB_ONLY:
        assert registry.get(sid) == "RETIRED", f"{sid}: expected RETIRED, got {registry.get(sid)}"


def test_registry_total_40(registry):
    assert len(registry) == 40


def test_registry_observation_unchanged(registry):
    assert registry.get("h6_gate_mk20_ew85") == "OBSERVATION"


def test_registry_online_count_18(registry):
    online = [sid for sid, lc in registry.items() if lc == "ONLINE"]
    assert len(online) == 18


def test_registry_retired_count_17(registry):
    retired = [sid for sid, lc in registry.items() if lc == "RETIRED"]
    assert len(retired) == 17


# ── Catalog validation ────────────────────────────────────────────────────────

def test_catalog_total_40(artifact):
    assert artifact["all_strategy_catalog_validation"]["total_strategies_visible"] == 40


def test_catalog_db_only_zero(artifact):
    assert artifact["all_strategy_catalog_validation"]["db_only_missing_lifecycle_count_after"] == 0


def test_catalog_h6_gate_observation(artifact):
    assert artifact["all_strategy_catalog_validation"]["h6_gate_mk20_ew85_unchanged_unless_authorized"] is True


# ── Non-actions ───────────────────────────────────────────────────────────────

def test_no_db_write(artifact):
    assert artifact["non_actions"]["db_write_in_p156c"] is False


def test_no_replay_rows(artifact):
    assert artifact["non_actions"]["replay_rows_inserted_in_p156c"] == 0
    assert artifact["non_actions"]["replay_rows_updated_in_p156c"] == 0
    assert artifact["non_actions"]["replay_rows_deleted_in_p156c"] == 0


def test_no_live_api(artifact):
    assert artifact["non_actions"]["live_api_called"] is False


def test_no_controlled_apply(artifact):
    assert artifact["non_actions"]["controlled_apply_executed_in_p156c"] is False


# ── Forbidden staging scan ────────────────────────────────────────────────────

def test_no_forbidden_db_staged():
    r = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True, text=True, cwd=CANONICAL_REPO,
    )
    staged = r.stdout.strip().splitlines()
    forbidden = [
        f for f in staged
        if "lottery_v2.db" in f
        or "replay_lifecycle_drift_guard.py" in f
        or f.startswith("backups/")
        or f.endswith(".pyc")
    ]
    assert forbidden == [], f"Forbidden staged: {forbidden}"
