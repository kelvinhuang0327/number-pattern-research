"""Tests for P152 replay UI source / controlled_apply_id display."""

import json
import subprocess
from pathlib import Path

import pytest

REPO_ROOT     = Path(__file__).parent.parent
ARTIFACT_PATH = REPO_ROOT / "outputs/replay/p152_replay_ui_source_controlled_apply_id_display_20260529.json"
INDEX_HTML    = REPO_ROOT / "index.html"

CANONICAL_REPO   = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802"
CANONICAL_BRANCH = "claude/zen-gates-ff6802"
EXPECTED_DB_ROWS = 94924

VALID_CLASSIFICATIONS = {
    "P152_REPLAY_UI_SOURCE_CONTROLLED_APPLY_ID_DISPLAY_READY",
    "P152_REPLAY_API_AND_UI_PROVENANCE_METADATA_READY",
    "P152_BLOCKED_PROVENANCE_FIELD_DB_SCHEMA_GAP",
    "P152_STOP_UI_ENTRYPOINT_NOT_FOUND",
    "P152_STOP_PREFLIGHT_MISMATCH",
}


@pytest.fixture(scope="module")
def artifact():
    assert ARTIFACT_PATH.exists(), f"P152 artifact missing: {ARTIFACT_PATH}"
    return json.loads(ARTIFACT_PATH.read_text())


@pytest.fixture(scope="module")
def html():
    assert INDEX_HTML.exists()
    return INDEX_HTML.read_text(encoding="utf-8")


# ── Artifact basics ───────────────────────────────────────────────────────────

def test_artifact_exists():
    assert ARTIFACT_PATH.exists()


def test_task_id(artifact):
    assert artifact["task_id"] == "P152"


def test_classification_valid(artifact):
    assert artifact["classification"] in VALID_CLASSIFICATIONS


def test_repo_ok(artifact):
    assert artifact["repo_branch_check"]["repo_ok"] is True


def test_branch_ok(artifact):
    assert artifact["repo_branch_check"]["branch_ok"] is True


def test_db_rows(artifact):
    assert artifact["db_snapshot"]["rows"] == EXPECTED_DB_ROWS


def test_db_rows_unchanged(artifact):
    assert artifact["db_snapshot"]["match"] is True


def test_drift_guard_pass(artifact):
    assert artifact["drift_guard_status"] == "PASS"


def test_p151_ok(artifact):
    assert artifact["p151_source_summary"]["ok"] is True


def test_p150_ok(artifact):
    assert artifact["p150_source_summary"]["ok"] is True


# ── API metadata field audit ──────────────────────────────────────────────────

def test_db_has_source(artifact):
    assert artifact["api_metadata_field_audit"]["db_has_source"] is True


def test_db_has_controlled_apply_id(artifact):
    assert artifact["api_metadata_field_audit"]["db_has_controlled_apply_id"] is True


def test_db_has_provenance_hash(artifact):
    assert artifact["api_metadata_field_audit"]["db_has_provenance_hash"] is True


def test_api_already_returned_fields(artifact):
    m = artifact["api_metadata_field_audit"]
    assert m["api_returns_source_before_p152"] is True
    assert m["api_returns_controlled_apply_id_before_p152"] is True
    assert m["api_returns_provenance_hash_before_p152"] is True


def test_no_api_change_required(artifact):
    assert artifact["api_changes"]["api_modified_in_p152"] is False


# ── Source display ────────────────────────────────────────────────────────────

def test_source_visible_in_detail(artifact):
    assert artifact["source_display_support"]["source_visible_in_detail"] is True


def test_source_in_history_row(artifact):
    assert artifact["source_display_support"]["source_visible_or_hooked_in_history"] is True


def test_null_source_handled(artifact):
    assert artifact["source_display_support"]["null_source_shows_legacy_unknown"] is True


def test_source_test_coverage(artifact):
    assert artifact["source_display_support"]["test_coverage_added"] is True


# ── controlled_apply_id display ───────────────────────────────────────────────

def test_controlled_apply_id_visible_in_detail(artifact):
    assert artifact["controlled_apply_id_display_support"]["controlled_apply_id_visible_in_detail"] is True


def test_null_controlled_apply_id_handled(artifact):
    assert artifact["controlled_apply_id_display_support"]["null_controlled_apply_id_handled"] is True


def test_legacy_uncontrolled_label_present(artifact):
    label = artifact["controlled_apply_id_display_support"]["legacy_uncontrolled_label"]
    assert "legacy" in label.lower() or "uncontrolled" in label.lower()


def test_controlled_apply_id_test_coverage(artifact):
    assert artifact["controlled_apply_id_display_support"]["test_coverage_added"] is True


# ── Provenance hash ───────────────────────────────────────────────────────────

def test_provenance_hash_available(artifact):
    assert artifact["provenance_hash_display_readiness"]["provenance_hash_available"] is True


def test_provenance_hash_hooked(artifact):
    assert artifact["provenance_hash_display_readiness"]["provenance_hash_visible_or_debug_hooked"] is True


# ── Legacy unverified ─────────────────────────────────────────────────────────

def test_legacy_unverified_badge_visible(artifact):
    assert artifact["legacy_unverified_display_support"]["legacy_unverified_truth_level_badge_visible"] is True


def test_legacy_unverified_source_visible(artifact):
    assert artifact["legacy_unverified_display_support"]["legacy_unverified_source_visible"] is True


def test_p138b_legacy_remark_tested(artifact):
    assert artifact["legacy_unverified_display_support"]["p138b_legacy_remark_visible_or_tested"] is True


def test_legacy_test_coverage(artifact):
    assert artifact["legacy_unverified_display_support"]["test_coverage_added"] is True


# ── Tier-B controlled apply ───────────────────────────────────────────────────

def test_tierb_truth_level_visible(artifact):
    assert artifact["tierb_controlled_apply_display_support"]["tierb_truth_level_visible"] is True


def test_tierb_metadata_visible(artifact):
    assert artifact["tierb_controlled_apply_display_support"]["controlled_apply_rows_metadata_visible_or_tested"] is True


def test_tierb_test_coverage(artifact):
    assert artifact["tierb_controlled_apply_display_support"]["test_coverage_added"] is True


# ── Non-actions ───────────────────────────────────────────────────────────────

def test_no_db_write(artifact):
    assert artifact["non_actions"]["db_write_in_p152"] is False


def test_no_replay_rows(artifact):
    assert artifact["non_actions"]["replay_rows_inserted_in_p152"] == 0
    assert artifact["non_actions"]["replay_rows_updated_in_p152"] == 0
    assert artifact["non_actions"]["replay_rows_deleted_in_p152"] == 0


def test_no_controlled_apply(artifact):
    assert artifact["non_actions"]["controlled_apply_executed_in_p152"] is False


def test_no_live_api(artifact):
    assert artifact["non_actions"]["live_api_called"] is False


def test_no_champion(artifact):
    assert artifact["non_actions"]["champion_promotion_executed_in_p152"] is False


def test_no_scheduler(artifact):
    assert artifact["non_actions"]["scheduler_installed"] is False


# ── Hygiene ───────────────────────────────────────────────────────────────────

def test_backups_not_staged(artifact):
    assert artifact["dirty_file_hygiene"]["backups_untracked_not_staged"] is True


def test_forbidden_not_staged(artifact):
    assert artifact["dirty_file_hygiene"]["forbidden_files_staged"] is False


# ── HTML content tests ────────────────────────────────────────────────────────

def test_html_source_in_detail(html):
    assert "rp-detail-source" in html


def test_html_controlled_apply_id_in_detail(html):
    assert "rp-detail-controlled-apply-id" in html


def test_html_provenance_hash_in_detail(html):
    assert "rp-detail-provenance-hash" in html


def test_html_truth_level_in_detail(html):
    assert "rp-detail-truth-level" in html


def test_html_source_label(html):
    assert "來源（source）" in html


def test_html_controlled_apply_label(html):
    assert "Controlled Apply ID" in html


def test_html_provenance_hash_label(html):
    assert "Provenance Hash" in html


def test_html_null_controlled_apply_label(html):
    assert "N/A（legacy/uncontrolled）" in html


def test_html_null_source_label(html):
    assert "legacy/unknown" in html


def test_html_source_in_history_row(html):
    assert "rp-row-source" in html


def test_html_legacy_unverified_badge(html):
    assert "LEGACY_UNVERIFIED" in html
    assert "rp-truth-legacy-unverified" in html


def test_html_tierb_badge(html):
    assert "TIERB_DRYRUN_VALIDATED" in html
    assert "rp-truth-tierb" in html


# ── P151 regression checks ────────────────────────────────────────────────────

def test_p151_bet_index_badge_preserved(html):
    assert "rp-bet-index-badge" in html


def test_p151_all_catalog_preserved(html):
    assert "rp-all-catalog-card" in html


def test_p151_no_data_reason_preserved(html):
    assert "rpNoDataReasonBadge" in html


def test_p151_bet_index_detail_preserved(html):
    assert "rp-detail-bet-index" in html


# ── No DB staging ─────────────────────────────────────────────────────────────

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
    assert forbidden == [], f"Forbidden files staged: {forbidden}"
