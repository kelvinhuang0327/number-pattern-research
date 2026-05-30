"""Tests for P151 replay UI multi-bet display artifact and index.html changes."""

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
ARTIFACT_PATH = REPO_ROOT / "outputs/replay/p151_replay_ui_multi_bet_display_20260529.json"
INDEX_HTML    = REPO_ROOT / "index.html"

CANONICAL_REPO   = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802"
CANONICAL_BRANCH = "claude/zen-gates-ff6802"
EXPECTED_DB_ROWS = 94924

VALID_CLASSIFICATIONS = {
    "P151_REPLAY_UI_MULTI_BET_DISPLAY_READY",
    "P151_STOP_UI_ENTRYPOINT_NOT_FOUND",
    "P151_BLOCKED_FRONTEND_API_CONTRACT_GAP",
    "P151_STOP_PREFLIGHT_MISMATCH",
}


@pytest.fixture(scope="module")
def artifact():
    assert ARTIFACT_PATH.exists(), f"P151 artifact missing: {ARTIFACT_PATH}"
    return json.loads(ARTIFACT_PATH.read_text())


@pytest.fixture(scope="module")
def html_content():
    assert INDEX_HTML.exists(), f"index.html missing: {INDEX_HTML}"
    return INDEX_HTML.read_text(encoding="utf-8")


# ── Artifact tests ────────────────────────────────────────────────────────────

def test_artifact_exists():
    assert ARTIFACT_PATH.exists()


def test_task_id(artifact):
    assert artifact["task_id"] == "P151"


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


def test_p151b_classification_ok(artifact):
    assert artifact["p151b_source_summary"]["ok"] is True


def test_p150_classification_ok(artifact):
    assert artifact["p150_source_summary"]["ok"] is True


def test_p149_classification_ok(artifact):
    assert artifact["p149_source_summary"]["ok"] is True


def test_non_actions_db_write(artifact):
    assert artifact["non_actions"]["db_write_in_p151"] is False


def test_non_actions_replay_rows(artifact):
    assert artifact["non_actions"]["replay_rows_inserted_in_p151"] == 0
    assert artifact["non_actions"]["replay_rows_updated_in_p151"] == 0
    assert artifact["non_actions"]["replay_rows_deleted_in_p151"] == 0


def test_non_actions_controlled_apply(artifact):
    assert artifact["non_actions"]["controlled_apply_executed_in_p151"] is False


def test_non_actions_ui_live_api(artifact):
    assert artifact["non_actions"]["live_api_called"] is False


def test_non_actions_champion(artifact):
    assert artifact["non_actions"]["champion_promotion_executed_in_p151"] is False


def test_non_actions_scheduler(artifact):
    assert artifact["non_actions"]["scheduler_installed"] is False


def test_backups_untracked_not_staged(artifact):
    assert artifact["dirty_file_hygiene"]["backups_untracked_not_staged"] is True


def test_forbidden_files_not_staged(artifact):
    assert artifact["dirty_file_hygiene"]["forbidden_files_staged"] is False


# ── Multi-bet display tests ───────────────────────────────────────────────────

def test_multi_bet_bet_index_visible(artifact):
    if artifact["classification"] == "P151_REPLAY_UI_MULTI_BET_DISPLAY_READY":
        assert artifact["multi_bet_display_support"]["bet_index_visible_in_ui"] is True


def test_multi_bet_rows_distinguishable(artifact):
    if artifact["classification"] == "P151_REPLAY_UI_MULTI_BET_DISPLAY_READY":
        assert artifact["multi_bet_display_support"]["multi_bet_rows_distinguishable"] is True


def test_multi_bet_detail_panel(artifact):
    if artifact["classification"] == "P151_REPLAY_UI_MULTI_BET_DISPLAY_READY":
        assert artifact["multi_bet_display_support"]["detail_panel_shows_bet_index"] is True


def test_multi_bet_test_coverage(artifact):
    if artifact["classification"] == "P151_REPLAY_UI_MULTI_BET_DISPLAY_READY":
        assert artifact["multi_bet_display_support"]["test_coverage_added"] is True


# ── NO_DATA display tests ─────────────────────────────────────────────────────

def test_no_data_zero_row_visible(artifact):
    if artifact["classification"] == "P151_REPLAY_UI_MULTI_BET_DISPLAY_READY":
        assert artifact["no_data_display_support"]["zero_replay_rows_strategies_visible"] is True


def test_no_data_reason_visible(artifact):
    if artifact["classification"] == "P151_REPLAY_UI_MULTI_BET_DISPLAY_READY":
        assert artifact["no_data_display_support"]["no_data_reason_visible"] is True


def test_no_data_rejected_visible(artifact):
    if artifact["classification"] == "P151_REPLAY_UI_MULTI_BET_DISPLAY_READY":
        assert artifact["no_data_display_support"]["rejected_no_data_strategies_visible"] is True


def test_no_data_db_only_visible(artifact):
    if artifact["classification"] == "P151_REPLAY_UI_MULTI_BET_DISPLAY_READY":
        assert artifact["no_data_display_support"]["db_only_missing_lifecycle_visible"] is True


def test_no_data_online_zero_visible(artifact):
    if artifact["classification"] == "P151_REPLAY_UI_MULTI_BET_DISPLAY_READY":
        assert artifact["no_data_display_support"]["online_zero_replay_rows_visible"] is True


# ── h6_gate_mk20_ew85 ─────────────────────────────────────────────────────────

def test_h6_gate_visible_in_catalog(artifact):
    if artifact["classification"] == "P151_REPLAY_UI_MULTI_BET_DISPLAY_READY":
        assert artifact["h6_gate_mk20_ew85_ui_handling"]["visible_in_catalog"] is True


def test_h6_gate_no_rows_inserted(artifact):
    assert artifact["h6_gate_mk20_ew85_ui_handling"]["replay_rows_inserted"] is False


def test_h6_gate_no_data_reason(artifact):
    assert artifact["h6_gate_mk20_ew85_ui_handling"]["no_data_reason"] == "ONLINE_ZERO_REPLAY_ROWS"


# ── Rejected no-data ──────────────────────────────────────────────────────────

def test_rejected_no_data_visible(artifact):
    if artifact["classification"] == "P151_REPLAY_UI_MULTI_BET_DISPLAY_READY":
        assert artifact["rejected_no_data_ui_handling"]["rejected_no_data_visible"] is True


def test_rejected_no_rows_inserted(artifact):
    assert artifact["rejected_no_data_ui_handling"]["replay_rows_inserted"] is False


def test_rejected_no_data_reason(artifact):
    assert artifact["rejected_no_data_ui_handling"]["no_data_reason"] == "REJECTED_NO_REPLAY_DATA"


# ── HTML content tests ────────────────────────────────────────────────────────

def test_html_bet_index_badge_present(html_content):
    assert "rp-bet-index-badge" in html_content


def test_html_bet_index_badge_css(html_content):
    assert ".rp-bet-index-badge" in html_content


def test_html_bet_index_detail_label(html_content):
    assert "注次（bet_index）" in html_content


def test_html_detail_testid_present(html_content):
    assert "rp-detail-bet-index" in html_content


def test_html_all_catalog_card(html_content):
    assert "rp-all-catalog-card" in html_content


def test_html_all_catalog_tbody(html_content):
    assert "rp-all-catalog-tbody" in html_content


def test_html_all_strategy_catalog_endpoint(html_content):
    assert "all-strategy-catalog" in html_content


def test_html_no_data_reason_badge_fn(html_content):
    assert "rpNoDataReasonBadge" in html_content


def test_html_ndr_css_zero_online(html_content):
    assert "rp-ndr-zero-online" in html_content


def test_html_ndr_css_rejected(html_content):
    assert "rp-ndr-rejected" in html_content


def test_html_ndr_css_db_only(html_content):
    assert "rp-ndr-db-only" in html_content


def test_html_online_zero_replay_rows_label(html_content):
    assert "ONLINE_ZERO_REPLAY_ROWS" in html_content


def test_html_rejected_no_replay_data_label(html_content):
    assert "REJECTED_NO_REPLAY_DATA" in html_content


def test_html_db_only_missing_lifecycle_label(html_content):
    assert "DB_ONLY_MISSING_LIFECYCLE" in html_content


def test_html_load_all_catalog_fn(html_content):
    assert "rpLoadAllStrategyCatalog" in html_content


def test_html_load_all_catalog_wired(html_content):
    # Should appear at least 3 times: definition + nav hook + DOMContentLoaded hook
    assert html_content.count("rpLoadAllStrategyCatalog") >= 3


def test_html_all_catalog_disclaimer(html_content):
    assert "rp-all-catalog-disclaimer" in html_content


def test_html_no_db_write_in_js(html_content):
    # Confirm index.html JS doesn't reference strategy_prediction_replays INSERT
    assert "INSERT INTO strategy_prediction_replays" not in html_content


def test_no_db_files_staged():
    """Confirm lottery_v2.db and other forbidden files are not staged."""
    import subprocess
    r = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True, text=True,
        cwd=CANONICAL_REPO,
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
