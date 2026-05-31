"""
P158B: Replay E2E Browser Smoke Expansion Tests

Static HTML/JS string inspection tests covering P151-P157 features.
No Playwright, no live API, no external browser process.
Extends the test_replay_browser_smoke.py pattern.
"""

import importlib
import json
import subprocess
from pathlib import Path

import pytest

REPO_ROOT     = Path(__file__).parent.parent
ARTIFACT_PATH = REPO_ROOT / "outputs/replay/p158b_replay_e2e_browser_smoke_expansion_20260529.json"
INDEX_HTML    = REPO_ROOT / "index.html"

CANONICAL_REPO   = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802"
CANONICAL_BRANCH = "claude/zen-gates-ff6802"
EXPECTED_DB_ROWS = 94924

VALID_CLASSIFICATIONS = {
    "P158B_REPLAY_STATIC_UI_SMOKE_READY",
    "P158B_REPLAY_E2E_BROWSER_SMOKE_READY",
    "P158B_REPLAY_E2E_BROWSER_SMOKE_BLOCKED",
}


@pytest.fixture(scope="module")
def artifact():
    assert ARTIFACT_PATH.exists()
    return json.loads(ARTIFACT_PATH.read_text())


@pytest.fixture(scope="module")
def html():
    if not INDEX_HTML.exists():
        pytest.skip("index.html not found")
    return INDEX_HTML.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def registry():
    import sys
    sys.path.insert(0, str(REPO_ROOT))
    import lottery_api.models.replay_strategy_registry as reg_mod
    importlib.reload(reg_mod)
    return {s["strategy_id"]: s["lifecycle_status"]
            for s in reg_mod.list_strategy_lifecycle_metadata()}


# ── Artifact basics ───────────────────────────────────────────────────────────

def test_artifact_exists():
    assert ARTIFACT_PATH.exists()


def test_task_id(artifact):
    assert artifact["task_id"] == "P158B"


def test_classification_valid(artifact):
    assert artifact["classification"] in VALID_CLASSIFICATIONS


def test_classification_smoke_ready(artifact):
    assert artifact["classification"] in {
        "P158B_REPLAY_STATIC_UI_SMOKE_READY",
        "P158B_REPLAY_E2E_BROWSER_SMOKE_READY",
    }


def test_repo_ok(artifact):
    assert artifact["repo_branch_check"]["repo_ok"] is True


def test_branch_ok(artifact):
    assert artifact["repo_branch_check"]["branch_ok"] is True


def test_db_rows(artifact):
    assert artifact["db_snapshot"]["rows"] == EXPECTED_DB_ROWS


def test_drift_guard_pass(artifact):
    assert artifact["drift_guard_status"] == "PASS"


def test_p158_ok(artifact):
    assert artifact["p158_source_summary"]["ok"] is True


def test_p157_ok(artifact):
    assert artifact["p157_source_summary"]["ok"] is True


def test_p154_ok(artifact):
    assert artifact["p154_source_summary"]["ok"] is True


# ── Browser smoke strategy ────────────────────────────────────────────────────

def test_smoke_strategy_no_new_dep(artifact):
    assert artifact["browser_smoke_strategy"]["no_new_large_dependency_added"] is True


def test_smoke_mode_known(artifact):
    mode = artifact["browser_smoke_strategy"]["smoke_mode"]
    assert mode in {"static_html_inspection", "browser", "artifact_audit"}


# ── Replay entrypoint smoke ───────────────────────────────────────────────────

def test_entrypoint_smoke_passed(artifact):
    assert artifact["replay_entrypoint_smoke"]["smoke_passed"] is True


def test_replay_section_exists(html):
    assert 'id="replay-section"' in html


def test_replay_api_base(html):
    assert "/api/replay" in html


def test_replay_history_endpoint(html):
    # History endpoint called as ${BASE}/history (template literal) in index.html
    assert (
        "replay/history" in html
        or "/api/replay/history" in html
        or "BASE}/history" in html
        or "{BASE}/history" in html
    )


# ── All-strategy catalog smoke ────────────────────────────────────────────────

def test_catalog_expected_40(artifact):
    assert artifact["all_strategy_catalog_smoke"]["expected_total_strategies"] == 40


def test_catalog_actual_40(artifact):
    assert artifact["all_strategy_catalog_smoke"]["actual_total_in_registry"] == 40


def test_catalog_card_present(artifact):
    assert artifact["all_strategy_catalog_smoke"]["all_catalog_card_present"] is True


def test_catalog_endpoint_called(artifact):
    assert artifact["all_strategy_catalog_smoke"]["all_catalog_endpoint_called"] is True


def test_catalog_retired_visible(artifact):
    assert artifact["all_strategy_catalog_smoke"]["retired_visible"] is True


def test_catalog_rejected_visible(artifact):
    assert artifact["all_strategy_catalog_smoke"]["rejected_visible"] is True


def test_catalog_observation_visible(artifact):
    assert artifact["all_strategy_catalog_smoke"]["observation_visible"] is True


def test_catalog_no_data_visible(artifact):
    assert artifact["all_strategy_catalog_smoke"]["no_data_visible"] is True


def test_catalog_smoke_passed(artifact):
    assert artifact["all_strategy_catalog_smoke"]["smoke_passed"] is True


def test_html_all_catalog_card(html):
    assert "rp-all-catalog-card" in html


def test_html_all_catalog_endpoint(html):
    assert "all-strategy-catalog" in html


def test_html_load_fn(html):
    assert "rpLoadAllStrategyCatalog" in html


# ── Lifecycle visibility smoke ────────────────────────────────────────────────

def test_lifecycle_invariant(artifact):
    assert artifact["lifecycle_visibility_smoke"]["lifecycle_is_label_not_gate"] is True


def test_lifecycle_retired_visible(artifact):
    assert artifact["lifecycle_visibility_smoke"]["retired_visible"] is True


def test_lifecycle_rejected_visible(artifact):
    assert artifact["lifecycle_visibility_smoke"]["rejected_visible"] is True


def test_lifecycle_observation_visible(artifact):
    assert artifact["lifecycle_visibility_smoke"]["observation_visible"] is True


def test_lifecycle_db_only_zero(artifact):
    assert artifact["lifecycle_visibility_smoke"]["db_only_remaining_zero"] is True


def test_lifecycle_visibility_confirmed(artifact):
    assert artifact["lifecycle_visibility_smoke"]["visibility_invariant_confirmed"] is True


def test_registry_no_db_only(registry):
    assert not any(v == "DB_ONLY_MISSING_LIFECYCLE" for v in registry.values())


def test_registry_total_40(registry):
    assert len(registry) == 40


# ── NO_DATA smoke ─────────────────────────────────────────────────────────────

def test_no_data_fn_present(artifact):
    assert artifact["no_data_smoke"]["no_data_reason_fn_present"] is True


def test_no_data_online_zero_label(artifact):
    assert artifact["no_data_smoke"]["online_zero_replay_rows_label"] is True


def test_no_data_rejected_label(artifact):
    assert artifact["no_data_smoke"]["rejected_no_replay_data_label"] is True


def test_no_data_db_only_label(artifact):
    assert artifact["no_data_smoke"]["db_only_missing_lifecycle_label"] is True


def test_no_data_h6_visible(artifact):
    assert artifact["no_data_smoke"]["h6_gate_visible_zero_rows"] is True


def test_no_data_smoke_passed(artifact):
    assert artifact["no_data_smoke"]["smoke_passed"] is True


def test_html_no_data_reason_fn(html):
    assert "rpNoDataReasonBadge" in html


def test_html_online_zero_replay_rows(html):
    assert "ONLINE_ZERO_REPLAY_ROWS" in html


def test_html_rejected_no_replay_data(html):
    assert "REJECTED_NO_REPLAY_DATA" in html


def test_html_db_only_label(html):
    assert "DB_ONLY_MISSING_LIFECYCLE" in html


# ── Multi-bet smoke ───────────────────────────────────────────────────────────

def test_multi_bet_bet_index_visible(artifact):
    assert artifact["multi_bet_smoke"]["bet_index_visible"] is True


def test_multi_bet_label_visible(artifact):
    assert artifact["multi_bet_smoke"]["bet_n_label_visible"] is True


def test_multi_bet_max_expected_5(artifact):
    assert artifact["multi_bet_smoke"]["max_bet_index_expected"] == 5


def test_multi_bet_detail_panel(artifact):
    assert artifact["multi_bet_smoke"]["bet_index_detail_panel"] is True


def test_multi_bet_smoke_passed(artifact):
    assert artifact["multi_bet_smoke"]["smoke_passed"] is True


def test_html_bet_index_badge(html):
    assert "rp-bet-index-badge" in html


def test_html_bet_index_css(html):
    assert ".rp-bet-index-badge" in html


def test_html_bet_index_detail(html):
    assert "rp-detail-bet-index" in html


def test_html_bet_index_label(html):
    assert "注次（bet_index）" in html


# ── Provenance metadata smoke ─────────────────────────────────────────────────

def test_provenance_truth_level(artifact):
    assert artifact["provenance_metadata_smoke"]["truth_level_visible"] is True


def test_provenance_source(artifact):
    assert artifact["provenance_metadata_smoke"]["source_visible"] is True


def test_provenance_cap_id(artifact):
    assert artifact["provenance_metadata_smoke"]["controlled_apply_id_visible"] is True


def test_provenance_hash(artifact):
    assert artifact["provenance_metadata_smoke"]["provenance_hash_visible"] is True


def test_provenance_smoke_passed(artifact):
    assert artifact["provenance_metadata_smoke"]["smoke_passed"] is True


def test_html_source_detail(html):
    assert "rp-detail-source" in html


def test_html_cap_id_detail(html):
    assert "rp-detail-controlled-apply-id" in html


def test_html_provenance_hash_detail(html):
    assert "rp-detail-provenance-hash" in html


def test_html_truth_level_detail(html):
    assert "rp-detail-truth-level" in html


def test_html_source_history_row(html):
    assert "rp-row-source" in html


def test_html_legacy_unverified_badge(html):
    assert "rp-truth-legacy-unverified" in html


def test_html_tierb_badge(html):
    assert "rp-truth-tierb" in html


# ── Champion boundary smoke ───────────────────────────────────────────────────

def test_champion_blocked(artifact):
    assert artifact["champion_boundary_smoke"]["champion_evaluation_blocked"] is True


def test_replay_not_blocked_by_champion(artifact):
    assert artifact["champion_boundary_smoke"]["replay_ui_blocked_by_champion"] is False


def test_champion_smoke_passed(artifact):
    assert artifact["champion_boundary_smoke"]["smoke_passed"] is True


# ── Non-actions ───────────────────────────────────────────────────────────────

def test_no_db_write(artifact):
    assert artifact["non_actions"]["db_write_in_p158b"] is False


def test_no_lifecycle_update(artifact):
    assert artifact["non_actions"]["lifecycle_update_executed_in_p158b"] is False


def test_no_controlled_apply(artifact):
    assert artifact["non_actions"]["controlled_apply_executed_in_p158b"] is False


def test_no_replay_rows(artifact):
    assert artifact["non_actions"]["replay_rows_inserted_in_p158b"] == 0
    assert artifact["non_actions"]["replay_rows_updated_in_p158b"] == 0
    assert artifact["non_actions"]["replay_rows_deleted_in_p158b"] == 0


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
