"""
Targeted tests for P212 POWER_LOTTO backward-OOS gap check.
No DB write. No production side effects.
"""
import inspect
import json
import os
import sqlite3
import pytest

import scripts.p212_power_lotto_backward_oos_gap_check as script_mod

JSON_PATH = "outputs/research/p212_power_lotto_backward_oos_gap_check_20260605.json"
MD_PATH = "outputs/research/p212_power_lotto_backward_oos_gap_check_20260605.md"

TARGET_STRATEGIES = {"fourier30_markov30_2bet", "zonal_entropy_2bet"}

APPROVED_CLASSIFICATIONS = {
    "P212_POWER_LOTTO_BACKWARD_OOS_GAP_CHECK_HISTORICAL_ARTIFACT",
    "P212_POWER_LOTTO_BACKWARD_OOS_GAP_CHECK_NULL",
    "P212_POWER_LOTTO_BACKWARD_OOS_GAP_CHECK_WAIT_FOR_OOS",
    "P212_POWER_LOTTO_BACKWARD_OOS_GAP_CHECK_UNDERPOWERED",
    "P212_POWER_LOTTO_BACKWARD_OOS_GAP_CHECK_INSUFFICIENT_DATA_WAIT_FOR_OOS",
}


@pytest.fixture(scope="module")
def artifact():
    with open(JSON_PATH) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def md_content():
    with open(MD_PATH) as f:
        return f.read()


# ---------------------------------------------------------------------------
# Script purity
# ---------------------------------------------------------------------------

def test_script_no_db_write_sql():
    src = inspect.getsource(script_mod)
    # Check for SQL write statements outside of comments/docstrings
    # Look for these only in execute() calls, not in docstrings or comments
    import re
    # Remove docstrings and comments before checking
    no_comments = re.sub(r'""".*?"""', '', src, flags=re.DOTALL)
    no_comments = re.sub(r"'''.*?'''", '', no_comments, flags=re.DOTALL)
    no_comments = re.sub(r'#.*', '', no_comments)
    for kw in ("conn.execute(\"INSERT", "conn.execute(\"UPDATE", "conn.execute(\"DELETE",
               "conn.execute(\"CREATE", "conn.execute(\"DROP", "conn.execute(\"ALTER"):
        assert kw not in no_comments, f"Forbidden SQL in execute call: {kw}"


def test_script_no_production_import():
    src = inspect.getsource(script_mod)
    assert "replay_strategy_registry" not in src
    assert "import controlled_apply" not in src


def test_script_readonly_uri():
    src = inspect.getsource(script_mod)
    assert "mode=ro" in src


# ---------------------------------------------------------------------------
# JSON artifact
# ---------------------------------------------------------------------------

def test_json_exists():
    assert os.path.exists(JSON_PATH)


def test_markdown_exists():
    assert os.path.exists(MD_PATH)


def test_json_parses(artifact):
    assert isinstance(artifact, dict)


def test_only_power_lotto(artifact):
    assert artifact["lottery_type"] == "POWER_LOTTO"


def test_only_two_target_strategies(artifact):
    analyzed = set(artifact.get("strategies_analyzed", []))
    assert analyzed == TARGET_STRATEGIES, f"Expected {TARGET_STRATEGIES}, got {analyzed}"


def test_classification_approved(artifact):
    assert artifact["classification"] in APPROVED_CLASSIFICATIONS


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
    fb = artifact.get("feature_bottlenecks", [])
    assert len(fb) >= 2


def test_allowed_next_actions(artifact):
    aa = artifact.get("allowed_next_actions", [])
    assert len(aa) >= 1
    assert not any("strategy_promotion" in a for a in aa)
    assert not any("betting" in a for a in aa)


def test_forbidden_next_actions(artifact):
    fa = artifact.get("forbidden_next_actions", [])
    assert "strategy_promotion" in fa
    assert "betting_advice" in fa


def test_no_claim_attestation(artifact):
    att = artifact.get("no_claim_attestation", "")
    assert len(att) > 20
    bad = ("prediction edge", "improved win rate", "betting advice",
           "production-ready", "deployment-ready", "strategy-ready", "recommended numbers")
    for p in bad:
        assert p.lower() not in att.lower(), f"Attestation: forbidden phrase '{p}'"


def test_per_strategy_safety(artifact):
    for r in artifact.get("per_strategy_results", []):
        assert r["db_write_authorized"] is False
        assert r["registry_write_authorized"] is False
        assert r["production_authorized"] is False
        assert r["betting_advice"] is False


def test_per_strategy_no_forbidden_language(artifact):
    bad = ("prediction edge", "improved win rate", "betting advice",
           "recommended numbers", "production-ready", "deployment-ready", "strategy-ready")
    for r in artifact.get("per_strategy_results", []):
        lang = r.get("confidence_language", "").lower()
        for phrase in bad:
            assert phrase not in lang, f"Forbidden phrase '{phrase}' in confidence_language"


def test_final_state_db_rows(artifact):
    assert artifact["final_state"]["db_rows"] == 94924


def test_final_state_drift_guard(artifact):
    assert artifact["final_state"]["drift_guard"] == "REPLAY_LIFECYCLE_DRIFT_GUARD_PASS"


def test_final_state_no_deployable_candidate(artifact):
    assert artifact["final_state"]["deployable_candidate_exists"] is False


# ---------------------------------------------------------------------------
# Markdown content
# ---------------------------------------------------------------------------

def test_markdown_type_c(md_content):
    assert "Type C" in md_content


def test_markdown_no_separate_closeout(md_content):
    lower = md_content.lower()
    assert "no separate" in lower or "same-pr" in lower or "same pr" in lower


def test_markdown_no_betting_advice(md_content):
    assert "betting advice" in md_content.lower() or "wagering recommendation" in md_content.lower()


def test_markdown_no_forbidden_claim(md_content):
    bad = ("prediction edge", "improved win rate", "production-ready",
           "recommended numbers", "deployment-ready", "strategy-ready")
    lower = md_content.lower()
    for phrase in bad:
        assert phrase not in lower, f"Markdown: forbidden phrase '{phrase}'"


def test_markdown_has_no_claim_attestation(md_content):
    assert "No-Claim Attestation" in md_content or "no-claim attestation" in md_content.lower()


# ---------------------------------------------------------------------------
# DB unchanged after script
# ---------------------------------------------------------------------------

def test_db_unchanged():
    conn = sqlite3.connect("lottery_api/data/lottery_v2.db")
    count = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    conn.close()
    assert count == 94924
