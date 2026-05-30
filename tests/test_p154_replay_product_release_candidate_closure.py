"""Tests for P154 replay product release candidate closure."""

import json
import subprocess
from pathlib import Path

import pytest

REPO_ROOT        = Path(__file__).parent.parent
ARTIFACT_PATH    = REPO_ROOT / "outputs/replay/p154_replay_product_release_candidate_closure_20260529.json"
OPERATOR_GUIDE   = REPO_ROOT / "docs/replay/REPLAY_PRODUCT_OPERATOR_GUIDE_20260529.md"
INDEX_HTML       = REPO_ROOT / "index.html"

CANONICAL_REPO   = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802"
CANONICAL_BRANCH = "claude/zen-gates-ff6802"
EXPECTED_DB_ROWS = 94924

VALID_CLASSIFICATIONS = {
    "P154_REPLAY_PRODUCT_RELEASE_CANDIDATE_CLOSED",
    "P154_REPLAY_PRODUCT_RC_BLOCKED_BY_ACCEPTANCE_GAPS",
    "P154_STOP_SCOPE_REALIGNMENT_REQUIRED",
}


@pytest.fixture(scope="module")
def artifact():
    assert ARTIFACT_PATH.exists(), f"P154 artifact missing: {ARTIFACT_PATH}"
    return json.loads(ARTIFACT_PATH.read_text())


@pytest.fixture(scope="module")
def guide():
    assert OPERATOR_GUIDE.exists(), f"Operator Guide missing: {OPERATOR_GUIDE}"
    return OPERATOR_GUIDE.read_text(encoding="utf-8")


# ── Artifact basics ───────────────────────────────────────────────────────────

def test_artifact_exists():
    assert ARTIFACT_PATH.exists()


def test_task_id(artifact):
    assert artifact["task_id"] == "P154"


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


def test_p153_ok(artifact):
    assert artifact["p153_source_summary"]["ok"] is True


# ── Release candidate status ──────────────────────────────────────────────────

def test_rc_ready(artifact):
    assert artifact["release_candidate_status"]["replay_product_rc_ready"] is True


def test_blocking_gaps_zero(artifact):
    assert artifact["release_candidate_status"]["blocking_gaps_count"] == 0


def test_artifacts_chain_valid(artifact):
    assert artifact["release_candidate_status"]["artifacts_chain_valid"] is True


def test_p153_classification_from_rc(artifact):
    assert artifact["release_candidate_status"]["acceptance_classification_from_p153"] == \
        "P153_REPLAY_PRODUCT_ACCEPTANCE_READY_WITH_POLISH_RECOMMENDED"


# ── Acceptance summary ────────────────────────────────────────────────────────

def test_total_strategies_40(artifact):
    assert artifact["replay_product_acceptance_summary"]["total_strategies_visible"] == 40


def test_expected_strategies_40(artifact):
    assert artifact["replay_product_acceptance_summary"]["expected_total_strategies"] == 40


def test_total_replay_rows(artifact):
    assert artifact["replay_product_acceptance_summary"]["total_replay_rows"] == EXPECTED_DB_ROWS


def test_multi_bet_max_index(artifact):
    assert artifact["replay_product_acceptance_summary"]["multi_bet_max_bet_index"] == 5


def test_multi_bet_rows(artifact):
    assert artifact["replay_product_acceptance_summary"]["multi_bet_rows"] == 40622


def test_api_acceptance_passed(artifact):
    assert artifact["replay_product_acceptance_summary"]["api_acceptance_passed"] is True


def test_ui_acceptance_passed(artifact):
    assert artifact["replay_product_acceptance_summary"]["ui_acceptance_passed"] is True


def test_no_data_acceptance_passed(artifact):
    assert artifact["replay_product_acceptance_summary"]["no_data_acceptance_passed"] is True


def test_provenance_metadata_acceptance_passed(artifact):
    assert artifact["replay_product_acceptance_summary"]["provenance_metadata_acceptance_passed"] is True


# ── Operator guide ────────────────────────────────────────────────────────────

def test_operator_guide_exists():
    assert OPERATOR_GUIDE.exists()


def test_operator_guide_created(artifact):
    assert artifact["operator_guide_summary"]["operator_guide_created"] is True


def test_guide_bet_index_explanation(artifact):
    assert artifact["operator_guide_summary"]["includes_bet_index_explanation"] is True


def test_guide_no_data_reason_explanation(artifact):
    assert artifact["operator_guide_summary"]["includes_no_data_reason_explanation"] is True


def test_guide_truth_level_explanation(artifact):
    assert artifact["operator_guide_summary"]["includes_truth_level_explanation"] is True


def test_guide_source_cap_id_explanation(artifact):
    assert artifact["operator_guide_summary"]["includes_source_controlled_apply_id_explanation"] is True


def test_guide_known_limitations(artifact):
    assert artifact["operator_guide_summary"]["includes_known_limitations"] is True


def test_guide_content_bet_index(guide):
    assert "bet_index" in guide or "Bet N" in guide


def test_guide_content_no_data_reason(guide):
    assert "no_data_reason" in guide or "ONLINE_ZERO_REPLAY_ROWS" in guide


def test_guide_content_truth_level(guide):
    assert "truth_level" in guide


def test_guide_content_source(guide):
    assert "source" in guide


def test_guide_content_controlled_apply_id(guide):
    assert "controlled_apply_id" in guide or "Controlled Apply ID" in guide


def test_guide_content_legacy_unverified(guide):
    assert "LEGACY_UNVERIFIED" in guide


def test_guide_content_db_only(guide):
    assert "DB_ONLY_MISSING_LIFECYCLE" in guide


def test_guide_content_historical_vs_live(guide):
    assert "LIVE_MONITORING_VERIFIED" in guide


def test_guide_content_known_limitations(guide):
    assert "已知限制" in guide or "Known" in guide


# ── RC checklist ──────────────────────────────────────────────────────────────

def test_rc_checklist_preflight(artifact):
    assert artifact["release_candidate_checklist"]["phase0_preflight_passed"] is True


def test_rc_checklist_artifacts_valid(artifact):
    assert artifact["release_candidate_checklist"]["p149_p150_p151_p152_p153_artifacts_valid"] is True


def test_rc_checklist_db_verified(artifact):
    assert artifact["release_candidate_checklist"]["db_row_count_verified"] is True


def test_rc_checklist_drift_guard(artifact):
    assert artifact["release_candidate_checklist"]["drift_guard_passed"] is True


def test_rc_checklist_no_db_write(artifact):
    assert artifact["release_candidate_checklist"]["no_db_write"] is True


def test_rc_checklist_no_row_mutation(artifact):
    assert artifact["release_candidate_checklist"]["no_replay_row_mutation"] is True


def test_rc_checklist_no_champion(artifact):
    assert artifact["release_candidate_checklist"]["no_champion_promotion"] is True


def test_rc_checklist_40_strategies(artifact):
    assert artifact["release_candidate_checklist"]["40_40_strategies_visible"] is True


def test_rc_checklist_bet_index_5(artifact):
    assert artifact["release_candidate_checklist"]["bet_index_5_max_verified"] is True


# ── Non-blocking risk register ────────────────────────────────────────────────

def test_risk_register_has_4_items(artifact):
    assert len(artifact["non_blocking_risk_register"]) == 4


def test_risk_register_none_blocking(artifact):
    for risk in artifact["non_blocking_risk_register"]:
        assert risk["blocking_release_candidate"] is False


def test_risk_r001_db_only(artifact):
    r001 = next((r for r in artifact["non_blocking_risk_register"] if r["risk_id"] == "R001"), None)
    assert r001 is not None
    assert "DB_ONLY" in r001["title"] or "lifecycle" in r001["title"].lower()


def test_risk_r002_h6_gate(artifact):
    r002 = next((r for r in artifact["non_blocking_risk_register"] if r["risk_id"] == "R002"), None)
    assert r002 is not None
    assert "h6_gate" in r002["title"]


# ── Post-RC backlog ───────────────────────────────────────────────────────────

def test_post_rc_backlog_has_p155(artifact):
    assert "P155_REPLAY_UI_POLISH_OPERATOR_REVIEW" in artifact["post_rc_backlog"]


def test_post_rc_backlog_has_p156(artifact):
    assert "P156_DB_ONLY_LIFECYCLE_GOVERNANCE_AUDIT" in artifact["post_rc_backlog"]


def test_post_rc_backlog_has_p157(artifact):
    assert "P157_H6_GATE_ZERO_REPLAY_ROWS_DECISION_GATE" in artifact["post_rc_backlog"]


def test_post_rc_backlog_has_p158(artifact):
    assert "P158_REPLAY_E2E_BROWSER_SMOKE_EXPANSION" in artifact["post_rc_backlog"]


def test_post_rc_backlog_champion_separate(artifact):
    assert "champion_live_monitoring_backlog_separate_from_replay_rc" in artifact["post_rc_backlog"]


def test_post_rc_all_non_blocking(artifact):
    for k, v in artifact["post_rc_backlog"].items():
        assert v["blocking_rc"] is False, f"{k} marked as blocking"


# ── Champion governance ───────────────────────────────────────────────────────

def test_champion_blocked(artifact):
    assert artifact["champion_governance_boundary"]["champion_evaluation_blocked"] is True


def test_champion_not_block_replay(artifact):
    assert artifact["champion_governance_boundary"]["replay_product_blocked_by_champion"] is False


def test_live_monitoring_champion_only(artifact):
    assert artifact["champion_governance_boundary"]["live_monitoring_verified_required_only_for_champion"] is True


# ── Non-actions ───────────────────────────────────────────────────────────────

def test_no_db_write(artifact):
    assert artifact["non_actions"]["db_write_in_p154"] is False


def test_no_replay_rows(artifact):
    assert artifact["non_actions"]["replay_rows_inserted_in_p154"] == 0


def test_no_live_api(artifact):
    assert artifact["non_actions"]["live_api_called"] is False


def test_no_controlled_apply(artifact):
    assert artifact["non_actions"]["controlled_apply_executed_in_p154"] is False


def test_no_champion_promo(artifact):
    assert artifact["non_actions"]["champion_promotion_executed_in_p154"] is False


# ── Hygiene ───────────────────────────────────────────────────────────────────

def test_backups_not_staged(artifact):
    assert artifact["dirty_file_hygiene"]["backups_untracked_not_staged"] is True


def test_no_forbidden_staged(artifact):
    assert artifact["dirty_file_hygiene"]["forbidden_files_staged"] is False


def test_no_db_files_in_staged():
    r = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True, text=True, cwd=CANONICAL_REPO,
    )
    staged = r.stdout.strip().splitlines()
    forbidden = [
        f for f in staged
        if "lottery_v2.db" in f or "replay_lifecycle_drift_guard.py" in f
        or f.startswith("backups/") or f.endswith(".pyc")
    ]
    assert forbidden == [], f"Forbidden staged: {forbidden}"


# ── HTML regressions (P149-P153 preserved) ────────────────────────────────────

def test_html_all_acceptance_features():
    html = INDEX_HTML.read_text(encoding="utf-8")
    required = [
        "rp-bet-index-badge", "rp-all-catalog-card", "rpNoDataReasonBadge",
        "rp-detail-source", "rp-detail-controlled-apply-id",
        "rp-detail-provenance-hash", "rp-detail-truth-level",
        "rp-truth-legacy-unverified", "rp-truth-tierb",
        "ONLINE_ZERO_REPLAY_ROWS", "REJECTED_NO_REPLAY_DATA", "DB_ONLY_MISSING_LIFECYCLE",
    ]
    missing = [r for r in required if r not in html]
    assert missing == [], f"Missing from HTML: {missing}"
