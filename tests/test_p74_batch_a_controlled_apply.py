"""
tests/test_p74_batch_a_controlled_apply.py
==========================================
P74 Batch A Controlled Apply — governance test suite.

Asserts:
- JSON and doc artifacts exist
- project_context_lock = LotteryNew
- backup_verified = true, backup_rows = 46960
- production_rows_before = 46960, production_rows_after = 46960
- Batch A candidates = exactly [fourier_rhythm_3bet, fourier30_markov30_2bet]
- No DAILY_539 or BIG_LOTTO candidates
- No DB write occurred (apply_results.executed = false)
- duplicate_check: 0 P74 rows, no collision
- apply_script_available = false, source_data_available = false
- All boolean governance flags = True
- final_classification = P74_BATCH_A_READY_WAITING_FOR_APPLY_AUTHORIZATION
"""

from __future__ import annotations

import json
import pathlib

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
JSON_PATH = REPO_ROOT / "outputs" / "replay" / "p74_batch_a_controlled_apply_20260526.json"
DOC_PATH  = REPO_ROOT / "docs"    / "replay" / "p74_batch_a_controlled_apply_20260526.md"


@pytest.fixture(scope="module")
def data() -> dict:
    with JSON_PATH.open() as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Artifact existence
# ---------------------------------------------------------------------------

def test_json_artifact_exists():
    assert JSON_PATH.exists(), f"JSON artifact missing: {JSON_PATH}"


def test_doc_artifact_exists():
    assert DOC_PATH.exists(), f"Doc artifact missing: {DOC_PATH}"


# ---------------------------------------------------------------------------
# Project context lock
# ---------------------------------------------------------------------------

def test_project_context_lock(data):
    assert data["project_context_lock"] == "LotteryNew"


# ---------------------------------------------------------------------------
# Backup gate
# ---------------------------------------------------------------------------

def test_backup_verified(data):
    assert data["backup_verified"] is True


def test_backup_rows(data):
    assert data["backup_rows"] == 46960, f"backup_rows={data['backup_rows']}"


def test_backup_path_present(data):
    assert data["backup_path"], "backup_path must be non-empty"
    assert "p74_pre_batch_a" in data["backup_path"]


# ---------------------------------------------------------------------------
# DB state (no write)
# ---------------------------------------------------------------------------

def test_production_rows_before(data):
    assert data["production_rows_before"] == 46960


def test_production_rows_after_unchanged(data):
    assert data["production_rows_after"] == 46960, (
        f"rows_after={data['production_rows_after']} — DB must be unchanged for READINESS_ONLY"
    )


def test_expected_rows_after_if_applied(data):
    assert data["expected_rows_after_if_applied"] == 49960


# ---------------------------------------------------------------------------
# Candidates: exactly Batch A, POWER_LOTTO only
# ---------------------------------------------------------------------------

def test_exactly_two_candidates(data):
    assert len(data["candidates"]) == 2


def test_candidate_ids_are_batch_a(data):
    ids = {c["strategy_id"] for c in data["candidates"]}
    assert ids == {"fourier_rhythm_3bet", "fourier30_markov30_2bet"}


def test_no_daily_539_candidates(data):
    for c in data["candidates"]:
        assert c.get("lottery_type") != "DAILY_539", f"DAILY_539 candidate found: {c}"


def test_no_big_lotto_candidates(data):
    for c in data["candidates"]:
        assert c.get("lottery_type") != "BIG_LOTTO", f"BIG_LOTTO candidate found: {c}"


def test_all_candidates_power_lotto(data):
    for c in data["candidates"]:
        assert c["lottery_type"] == "POWER_LOTTO"


# ---------------------------------------------------------------------------
# Duplicate check
# ---------------------------------------------------------------------------

def test_no_p74_existing_rows(data):
    assert data["duplicate_check_results"]["p74_existing_rows"] == 0


def test_no_controlled_apply_id_collision(data):
    assert data["duplicate_check_results"]["p74_controlled_apply_id_collision"] is False


def test_apply_script_not_available(data):
    assert data["duplicate_check_results"]["apply_script_available"] is False


def test_source_data_not_available(data):
    assert data["duplicate_check_results"]["source_data_available"] is False


def test_apply_blocked(data):
    assert data["duplicate_check_results"]["apply_blocked"] is True


# ---------------------------------------------------------------------------
# Apply results (no DB write)
# ---------------------------------------------------------------------------

def test_apply_not_executed(data):
    assert data["apply_results"]["executed"] is False


def test_no_db_write(data):
    assert data["apply_results"]["db_write_occurred"] is False


def test_rows_inserted_zero(data):
    assert data["apply_results"]["rows_inserted"] == 0


# ---------------------------------------------------------------------------
# Authorization mode
# ---------------------------------------------------------------------------

def test_authorization_mode(data):
    assert data["authorization_mode"] == "APPLY_AUTHORIZED_BUT_BLOCKED"


# ---------------------------------------------------------------------------
# Boolean governance flags
# ---------------------------------------------------------------------------

BOOL_FLAGS = [
    "no_force_push",
    "no_reset_hard",
    "no_git_clean",
    "no_lifecycle_promotion",
    "no_champion_replacement",
    "no_registry_mutation",
    "no_unscoped_strategy_apply",
]


@pytest.mark.parametrize("flag", BOOL_FLAGS)
def test_governance_flag(data, flag):
    assert data.get(flag) is True, f"governance flag {flag} must be True"


def test_scope_no_daily_539(data):
    assert data["scope_enforcement"]["no_daily_539"] is True


def test_scope_no_big_lotto(data):
    assert data["scope_enforcement"]["no_big_lotto"] is True


def test_scope_no_retired(data):
    assert data["scope_enforcement"]["no_retired_strategies"] is True


# ---------------------------------------------------------------------------
# Guard results
# ---------------------------------------------------------------------------

def test_drift_guard_pass(data):
    assert data["guard_results"]["drift_guard"] == "PASS"


def test_branch_governance_pass(data):
    assert "BRANCH_GOVERNANCE_PASS" in data["guard_results"]["branch_governance"]


# ---------------------------------------------------------------------------
# Final classification
# ---------------------------------------------------------------------------

def test_final_classification(data):
    assert data["final_classification"] == "P74_BATCH_A_READY_WAITING_FOR_APPLY_AUTHORIZATION"


# ---------------------------------------------------------------------------
# Required next steps documented
# ---------------------------------------------------------------------------

def test_required_next_steps_present(data):
    steps = data.get("required_next_steps_for_apply", [])
    assert len(steps) >= 3, "Must document at least 3 required next steps for apply"
