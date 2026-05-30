"""Tests for P153 replay product end-to-end acceptance audit."""

import json
import subprocess
from pathlib import Path

import pytest

REPO_ROOT     = Path(__file__).parent.parent
ARTIFACT_PATH = REPO_ROOT / "outputs/replay/p153_replay_product_end_to_end_acceptance_audit_20260529.json"
INDEX_HTML    = REPO_ROOT / "index.html"

CANONICAL_REPO   = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802"
CANONICAL_BRANCH = "claude/zen-gates-ff6802"
EXPECTED_DB_ROWS = 94924

VALID_CLASSIFICATIONS = {
    "P153_REPLAY_PRODUCT_E2E_ACCEPTANCE_READY",
    "P153_REPLAY_PRODUCT_ACCEPTANCE_READY_WITH_POLISH_RECOMMENDED",
    "P153_REPLAY_PRODUCT_ACCEPTANCE_BLOCKED_BY_GAPS",
    "P153_STOP_PREFLIGHT_MISMATCH",
}


@pytest.fixture(scope="module")
def artifact():
    assert ARTIFACT_PATH.exists(), f"P153 artifact missing: {ARTIFACT_PATH}"
    return json.loads(ARTIFACT_PATH.read_text())


@pytest.fixture(scope="module")
def html():
    assert INDEX_HTML.exists()
    return INDEX_HTML.read_text(encoding="utf-8")


# ── Artifact basics ───────────────────────────────────────────────────────────

def test_artifact_exists():
    assert ARTIFACT_PATH.exists()


def test_task_id(artifact):
    assert artifact["task_id"] == "P153"


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


def test_p152_ok(artifact):
    assert artifact["p152_source_summary"]["ok"] is True


def test_p151_ok(artifact):
    assert artifact["p151_source_summary"]["ok"] is True


def test_p150_ok(artifact):
    assert artifact["p150_source_summary"]["ok"] is True


def test_p149_ok(artifact):
    assert artifact["p149_source_summary"]["ok"] is True


# ── Replay product boundary ───────────────────────────────────────────────────

def test_historical_actual_numbers_allowed(artifact):
    b = artifact["replay_product_boundary"]
    assert b["historical_actual_numbers_allowed_for_replay_display"] is True


def test_champion_block_not_block_replay(artifact):
    b = artifact["replay_product_boundary"]
    assert b["champion_block_does_not_block_replay_product"] is True


def test_live_monitoring_for_champion_only(artifact):
    b = artifact["replay_product_boundary"]
    assert b["live_monitoring_verified_required_for_champion_evaluation_only"] is True


def test_legacy_unverified_allowed_with_badge(artifact):
    b = artifact["replay_product_boundary"]
    assert b["legacy_unverified_display_allowed_with_badge"] is True


# ── Catalog acceptance ────────────────────────────────────────────────────────

def test_catalog_expected_total(artifact):
    assert artifact["catalog_acceptance_matrix"]["expected_total_strategies"] == 40


def test_catalog_total_visible(artifact):
    assert artifact["catalog_acceptance_matrix"]["total_strategies_visible"] == 40


def test_catalog_coverage_complete(artifact):
    assert artifact["catalog_acceptance_matrix"]["catalog_coverage_complete"] is True


def test_h6_gate_visible(artifact):
    assert artifact["catalog_acceptance_matrix"]["h6_gate_mk20_ew85_visible"] is True


def test_h6_gate_no_data_reason(artifact):
    assert artifact["catalog_acceptance_matrix"]["h6_gate_mk20_ew85_no_data_reason"] == "ONLINE_ZERO_REPLAY_ROWS"


def test_rejected_no_data_visible(artifact):
    assert artifact["catalog_acceptance_matrix"]["rejected_no_data_visible"] is True


def test_db_only_visible(artifact):
    assert artifact["catalog_acceptance_matrix"]["db_only_missing_lifecycle_visible"] is True


# ── Replay history API acceptance ─────────────────────────────────────────────

def test_api_bet_index_returned(artifact):
    assert artifact["replay_history_api_acceptance_matrix"]["bet_index_returned"] is True


def test_api_truth_level_returned(artifact):
    assert artifact["replay_history_api_acceptance_matrix"]["truth_level_returned"] is True


def test_api_source_returned(artifact):
    assert artifact["replay_history_api_acceptance_matrix"]["source_returned"] is True


def test_api_controlled_apply_id_returned(artifact):
    assert artifact["replay_history_api_acceptance_matrix"]["controlled_apply_id_returned"] is True


def test_api_provenance_hash_returned(artifact):
    assert artifact["replay_history_api_acceptance_matrix"]["provenance_hash_returned"] is True


def test_api_actual_numbers_returned(artifact):
    assert artifact["replay_history_api_acceptance_matrix"]["actual_numbers_returned"] is True


def test_api_hit_count_returned(artifact):
    assert artifact["replay_history_api_acceptance_matrix"]["hit_count_returned"] is True


def test_api_coverage_complete(artifact):
    assert artifact["replay_history_api_acceptance_matrix"]["api_coverage_complete"] is True


# ── All-strategy catalog API acceptance ──────────────────────────────────────

def test_all_catalog_endpoint_exists(artifact):
    assert artifact["all_strategy_catalog_api_acceptance_matrix"]["endpoint_exists"] is True


def test_all_catalog_total(artifact):
    assert artifact["all_strategy_catalog_api_acceptance_matrix"]["total_strategies_returned"] == 40


def test_all_catalog_no_data_reason(artifact):
    assert artifact["all_strategy_catalog_api_acceptance_matrix"]["no_data_reason_returned"] is True


# ── Replay UI acceptance ──────────────────────────────────────────────────────

def test_ui_bet_index_visible(artifact):
    assert artifact["replay_ui_acceptance_matrix"]["bet_index_visible"] is True


def test_ui_no_data_reason_visible(artifact):
    assert artifact["replay_ui_acceptance_matrix"]["no_data_reason_visible"] is True


def test_ui_truth_level_visible(artifact):
    assert artifact["replay_ui_acceptance_matrix"]["truth_level_visible"] is True


def test_ui_source_visible(artifact):
    assert artifact["replay_ui_acceptance_matrix"]["source_visible"] is True


def test_ui_controlled_apply_id_visible(artifact):
    assert artifact["replay_ui_acceptance_matrix"]["controlled_apply_id_visible"] is True


def test_ui_provenance_hash_visible(artifact):
    assert artifact["replay_ui_acceptance_matrix"]["provenance_hash_visible"] is True


def test_ui_h6_gate_visible(artifact):
    assert artifact["replay_ui_acceptance_matrix"]["h6_gate_mk20_ew85_visible"] is True


def test_ui_rejected_visible(artifact):
    assert artifact["replay_ui_acceptance_matrix"]["rejected_no_data_visible"] is True


def test_ui_coverage_complete(artifact):
    assert artifact["replay_ui_acceptance_matrix"]["ui_coverage_complete"] is True


# ── Multi-bet acceptance ──────────────────────────────────────────────────────

def test_multi_bet_max_index(artifact):
    assert artifact["multi_bet_acceptance"]["max_bet_index"] == 5


def test_multi_bet_distinguishable(artifact):
    assert artifact["multi_bet_acceptance"]["multi_bet_distinguishable"] is True


def test_multi_bet_api(artifact):
    assert artifact["multi_bet_acceptance"]["bet_index_returned_by_api"] is True


# ── Provenance metadata acceptance ────────────────────────────────────────────

def test_provenance_source_api(artifact):
    assert artifact["provenance_metadata_acceptance"]["source_in_api"] is True


def test_provenance_cap_api(artifact):
    assert artifact["provenance_metadata_acceptance"]["controlled_apply_id_in_api"] is True


def test_provenance_hash_api(artifact):
    assert artifact["provenance_metadata_acceptance"]["provenance_hash_in_api"] is True


def test_provenance_all_primary_covered(artifact):
    assert artifact["provenance_metadata_acceptance"]["all_primary_provenance_fields_covered"] is True


def test_legacy_unverified_badge_in_artifact(artifact):
    assert artifact["provenance_metadata_acceptance"]["legacy_unverified_badge"] is True


def test_tierb_badge_in_artifact(artifact):
    assert artifact["provenance_metadata_acceptance"]["tierb_badge"] is True


# ── Champion governance boundary ─────────────────────────────────────────────

def test_champion_blocked(artifact):
    assert artifact["champion_governance_boundary"]["champion_evaluation_blocked"] is True


def test_champion_not_affect_replay(artifact):
    assert artifact["champion_governance_boundary"]["replay_product_affected_by_champion_block"] is False


# ── Non-actions ───────────────────────────────────────────────────────────────

def test_no_db_write(artifact):
    assert artifact["non_actions"]["db_write_in_p153"] is False


def test_no_replay_rows(artifact):
    assert artifact["non_actions"]["replay_rows_inserted_in_p153"] == 0
    assert artifact["non_actions"]["replay_rows_updated_in_p153"] == 0
    assert artifact["non_actions"]["replay_rows_deleted_in_p153"] == 0


def test_no_live_api(artifact):
    assert artifact["non_actions"]["live_api_called"] is False


def test_no_controlled_apply(artifact):
    assert artifact["non_actions"]["controlled_apply_executed_in_p153"] is False


# ── Hygiene ───────────────────────────────────────────────────────────────────

def test_backups_not_staged(artifact):
    assert artifact["dirty_file_hygiene"]["backups_untracked_not_staged"] is True


def test_no_forbidden_staged(artifact):
    assert artifact["dirty_file_hygiene"]["forbidden_files_staged"] is False


# ── HTML regressions (P149-P152 preserved) ────────────────────────────────────

def test_html_p151_bet_index(html):
    assert "rp-bet-index-badge" in html


def test_html_p151_all_catalog(html):
    assert "rp-all-catalog-card" in html


def test_html_p151_no_data_reason(html):
    assert "rpNoDataReasonBadge" in html


def test_html_p152_source(html):
    assert "rp-detail-source" in html


def test_html_p152_cap_id(html):
    assert "rp-detail-controlled-apply-id" in html


def test_html_p152_provenance_hash(html):
    assert "rp-detail-provenance-hash" in html


def test_html_p152_legacy_unverified_badge(html):
    assert "rp-truth-legacy-unverified" in html


def test_html_p152_tierb_badge(html):
    assert "rp-truth-tierb" in html


def test_no_db_files_staged():
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
