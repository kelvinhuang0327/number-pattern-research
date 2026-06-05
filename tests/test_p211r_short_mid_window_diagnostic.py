"""
Targeted tests for P211R short/mid-window diagnostic.
No DB write. No production side effects.
"""
import inspect
import json
import os
import subprocess
import sys
import pytest

import scripts.p211r_short_mid_window_diagnostic as script_mod

JSON_PATH = "outputs/research/p211r_short_mid_window_diagnostic_20260605.json"
MD_PATH = "outputs/research/p211r_short_mid_window_diagnostic_20260605.md"

APPROVED_CLASSIFICATIONS = {
    "P211R_SHORT_MID_WINDOW_NULL_NO_DEPLOYABLE_EDGE",
    "P211R_CANDIDATE_NEEDS_OOS_CONFIRMATION",
    "P211R_IS_CANDIDATES_PRIOR_OOS_REJECTED_HISTORICAL_ARTIFACT",
}


@pytest.fixture(scope="module")
def artifact():
    assert os.path.exists(JSON_PATH), f"Run the script first: {JSON_PATH}"
    with open(JSON_PATH) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def md_content():
    assert os.path.exists(MD_PATH), f"Run the script first: {MD_PATH}"
    with open(MD_PATH) as f:
        return f.read()


# ---------------------------------------------------------------------------
# Script purity
# ---------------------------------------------------------------------------

def test_script_no_db_write_sql():
    src = inspect.getsource(script_mod)
    for kw in ("INSERT ", "UPDATE ", "DELETE ", "CREATE TABLE", "DROP TABLE", "ALTER TABLE"):
        assert kw not in src.upper(), f"Script contains forbidden SQL keyword: {kw}"


def test_script_no_production_import():
    src = inspect.getsource(script_mod)
    assert "controlled_apply" not in src
    assert "replay_strategy_registry" not in src


def test_script_db_readonly_uri():
    src = inspect.getsource(script_mod)
    assert "mode=ro" in src


# ---------------------------------------------------------------------------
# JSON artifact
# ---------------------------------------------------------------------------

def test_json_exists():
    assert os.path.exists(JSON_PATH)


def test_json_parses(artifact):
    assert isinstance(artifact, dict)


def test_classification_approved(artifact):
    assert artifact["classification"] in APPROVED_CLASSIFICATIONS, (
        f"Unexpected classification: {artifact['classification']}"
    )


def test_p211_restarted(artifact):
    assert artifact["p211_restarted"] is True


def test_db_write_not_authorized(artifact):
    assert artifact["db_write_authorized"] is False


def test_registry_write_not_authorized(artifact):
    assert artifact["registry_write_authorized"] is False


def test_production_not_authorized(artifact):
    assert artifact["production_authorized"] is False


def test_monitoring_not_authorized(artifact):
    assert artifact["monitoring_authorized"] is False


def test_strategy_not_authorized(artifact):
    assert artifact["strategy_authorized"] is False


def test_no_betting_advice(artifact):
    assert artifact["betting_advice"] is False


def test_p238b_interpretation(artifact):
    assert "YELLOW" in artifact["p238b_interpretation"]


def test_feature_bottlenecks_present(artifact):
    ft = artifact.get("feature_bottlenecks", [])
    assert len(ft) >= 1


def test_allowed_next_actions_present(artifact):
    aa = artifact.get("allowed_next_actions", [])
    assert len(aa) >= 1
    assert not any("strategy_promotion" in a for a in aa)
    assert not any("betting" in a for a in aa)


def test_forbidden_next_actions_present(artifact):
    fa = artifact.get("forbidden_next_actions", [])
    assert "strategy_promotion" in fa
    assert "betting_advice" in fa


def test_no_claim_attestation_present(artifact):
    att = artifact.get("no_claim_attestation", "")
    assert len(att) > 20
    bad_phrases = ("prediction edge", "improved win rate", "betting advice", "production-ready")
    for p in bad_phrases:
        assert p.lower() not in att.lower(), f"Attestation contains forbidden phrase: {p}"


def test_lotteries_analyzed(artifact):
    assert "POWER_LOTTO" in artifact.get("lotteries_analyzed", [])
    assert "DAILY_539" in artifact.get("lotteries_analyzed", [])


def test_windows_analyzed(artifact):
    ws = artifact.get("windows_analyzed", [])
    assert 150 in ws
    assert 500 in ws


def test_final_state_db_rows(artifact):
    assert artifact["final_state"]["db_rows"] == 94924


def test_final_state_drift_guard(artifact):
    assert artifact["final_state"]["drift_guard"] == "REPLAY_LIFECYCLE_DRIFT_GUARD_PASS"


def test_final_state_no_deployable_candidate(artifact):
    assert artifact["final_state"]["deployable_candidate_exists"] is False


def test_per_lottery_results_safety(artifact):
    for lottery in ["POWER_LOTTO", "DAILY_539"]:
        for r in artifact["per_lottery_results"][lottery]["results"]:
            assert r["db_write_authorized"] is False
            assert r["registry_write_authorized"] is False
            assert r["production_authorized"] is False
            assert r["betting_advice"] is False


def test_per_lottery_no_prediction_edge_language(artifact):
    bad = ("prediction edge", "improved win rate", "betting advice",
           "recommended numbers", "production-ready")
    for lottery in ["POWER_LOTTO", "DAILY_539"]:
        for r in artifact["per_lottery_results"][lottery]["results"]:
            lang = r.get("confidence_language", "").lower()
            for phrase in bad:
                assert phrase not in lang, (
                    f"confidence_language contains forbidden phrase '{phrase}': {lang!r}"
                )


# ---------------------------------------------------------------------------
# Markdown artifact
# ---------------------------------------------------------------------------

def test_markdown_exists():
    assert os.path.exists(MD_PATH)


def test_markdown_no_db_write(md_content):
    lower = md_content.lower()
    assert "no db write" in lower or "db_write_authorized" in lower


def test_markdown_no_betting_advice(md_content):
    assert "betting advice" in md_content.lower() or "wagering recommendation" in md_content.lower()


def test_markdown_type_c(md_content):
    assert "Type C" in md_content


def test_markdown_no_separate_closeout(md_content):
    lower = md_content.lower()
    assert "no separate" in lower or "same-pr" in lower or "same pr" in lower


def test_markdown_p211_restart_authorized(md_content):
    assert "P211" in md_content
    assert "Start P211" in md_content or "restart" in md_content.lower()


def test_markdown_no_prediction_edge_claim(md_content):
    bad = ("prediction edge", "improved win rate", "production-ready", "recommended numbers")
    lower = md_content.lower()
    for phrase in bad:
        assert phrase not in lower, f"Markdown contains forbidden phrase: {phrase!r}"


def test_markdown_has_no_claim_attestation(md_content):
    assert "No-Claim Attestation" in md_content or "no-claim attestation" in md_content.lower()


# ---------------------------------------------------------------------------
# Script runs in read-only mode (integration)
# ---------------------------------------------------------------------------

def test_db_unchanged_after_script():
    """Verify replay row count is 94924 after script execution."""
    import sqlite3
    conn = sqlite3.connect("lottery_api/data/lottery_v2.db")
    count = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    conn.close()
    assert count == 94924
