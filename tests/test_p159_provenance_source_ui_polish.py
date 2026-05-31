"""Tests for P159 provenance_source UI polish."""

import json
import subprocess
from pathlib import Path

import pytest

REPO_ROOT     = Path(__file__).parent.parent
ARTIFACT_PATH = REPO_ROOT / "outputs/replay/p159_provenance_source_ui_polish_20260529.json"
INDEX_HTML    = REPO_ROOT / "index.html"

CANONICAL_REPO   = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802"
CANONICAL_BRANCH = "claude/zen-gates-ff6802"
EXPECTED_DB_ROWS = 94924

VALID_CLASSIFICATIONS = {
    "P159_PROVENANCE_SOURCE_UI_POLISH_READY",
    "P159_BLOCKED_PROVENANCE_SOURCE_SCHEMA_GAP",
    "P159_STOP_SCOPE_REALIGNMENT_REQUIRED",
}


@pytest.fixture(scope="module")
def artifact():
    assert ARTIFACT_PATH.exists()
    return json.loads(ARTIFACT_PATH.read_text())


@pytest.fixture(scope="module")
def html():
    assert INDEX_HTML.exists()
    return INDEX_HTML.read_text(encoding="utf-8")


# ── Artifact basics ───────────────────────────────────────────────────────────

def test_artifact_exists():
    assert ARTIFACT_PATH.exists()


def test_task_id(artifact):
    assert artifact["task_id"] == "P159"


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


def test_p158b_ok(artifact):
    assert artifact["p158b_source_summary"]["ok"] is True


def test_p158_ok(artifact):
    assert artifact["p158_source_summary"]["ok"] is True


# ── Provenance_source field audit ─────────────────────────────────────────────

def test_db_has_provenance_source(artifact):
    assert artifact["provenance_source_field_audit"]["db_has_provenance_source"] is True


def test_api_already_returned(artifact):
    assert artifact["provenance_source_field_audit"]["api_returns_provenance_source_before_p159"] is True


def test_no_api_change_required(artifact):
    assert artifact["provenance_source_field_audit"]["api_change_required"] is False


def test_ui_display_completed(artifact):
    if artifact["classification"] == "P159_PROVENANCE_SOURCE_UI_POLISH_READY":
        assert artifact["provenance_source_field_audit"]["ui_display_completed"] is True


# ── API changes ───────────────────────────────────────────────────────────────

def test_no_api_modified(artifact):
    assert artifact["api_changes"]["api_modified_in_p159"] is False


# ── Provenance_source display support ────────────────────────────────────────

def test_provenance_source_visible_in_detail(artifact):
    if artifact["classification"] == "P159_PROVENANCE_SOURCE_UI_POLISH_READY":
        assert artifact["provenance_source_display_support"]["provenance_source_visible_in_detail"] is True


def test_null_provenance_source_handled(artifact):
    if artifact["classification"] == "P159_PROVENANCE_SOURCE_UI_POLISH_READY":
        assert artifact["provenance_source_display_support"]["null_provenance_source_handled"] is True


def test_test_coverage_added(artifact):
    assert artifact["provenance_source_display_support"]["test_coverage_added"] is True


# ── Operator guide ────────────────────────────────────────────────────────────

def test_operator_guide_updated(artifact):
    assert artifact["operator_guide_update"]["operator_guide_updated"] is True


def test_operator_guide_has_provenance_source(artifact):
    assert artifact["operator_guide_update"]["includes_provenance_source_explanation"] is True


# ── HTML content tests ────────────────────────────────────────────────────────

def test_html_provenance_source_in_detail(html):
    assert "rp-detail-provenance-source" in html


def test_html_provenance_source_label(html):
    assert "Provenance Source" in html


def test_html_null_provenance_source_handled(html):
    assert "N/A（未提供）" in html


def test_html_p152_provenance_hash_preserved(html):
    assert "rp-detail-provenance-hash" in html


def test_html_p152_source_preserved(html):
    assert "rp-detail-source" in html


def test_html_p152_cap_id_preserved(html):
    assert "rp-detail-controlled-apply-id" in html


def test_html_p151_bet_index_preserved(html):
    assert "rp-bet-index-badge" in html


def test_html_p151_all_catalog_preserved(html):
    assert "rp-all-catalog-card" in html


# ── Non-actions ───────────────────────────────────────────────────────────────

def test_no_db_write(artifact):
    assert artifact["non_actions"]["db_write_in_p159"] is False


def test_no_lifecycle_update(artifact):
    assert artifact["non_actions"]["lifecycle_update_executed_in_p159"] is False


def test_no_controlled_apply(artifact):
    assert artifact["non_actions"]["controlled_apply_executed_in_p159"] is False


def test_no_replay_rows(artifact):
    assert artifact["non_actions"]["replay_rows_inserted_in_p159"] == 0
    assert artifact["non_actions"]["replay_rows_updated_in_p159"] == 0
    assert artifact["non_actions"]["replay_rows_deleted_in_p159"] == 0


def test_no_live_api(artifact):
    assert artifact["non_actions"]["live_api_called"] is False


# ── Forbidden staging scan ────────────────────────────────────────────────────

def test_no_forbidden_staged():
    r = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True, text=True, cwd=CANONICAL_REPO,
    )
    staged = r.stdout.strip().splitlines()
    forbidden = [
        f for f in staged
        if "lottery_v2.db" in f
        or "replay_lifecycle_drift_guard.py" in f
        or "replay_strategy_registry.py" in f
        or f.startswith("backups/")
        or f.endswith(".pyc")
    ]
    assert forbidden == [], f"Forbidden staged: {forbidden}"
