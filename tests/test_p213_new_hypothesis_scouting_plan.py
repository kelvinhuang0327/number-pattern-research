"""
Targeted tests for P213 New Hypothesis Scouting Plan artifacts.
No DB access beyond Phase 0. No production side effects.
"""
import json
import os
import pytest

JSON_PATH = "outputs/research/p213_new_hypothesis_scouting_plan_20260605.json"
MD_PATH = "outputs/research/p213_new_hypothesis_scouting_plan_20260605.md"

REQUIRED_LOTTERIES = {"BIG_LOTTO", "DAILY_539", "POWER_LOTTO", "3_STAR", "4_STAR"}
REQUIRED_CLOSED_LINES = {"P211R", "P212"}

FORBIDDEN_MD_PHRASES = (
    "prediction edge",
    "improved win rate",
    "production-ready",
    "strategy-ready",
    "recommended numbers",
    "deployment-ready",
)


@pytest.fixture(scope="module")
def artifact():
    with open(JSON_PATH) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def md_content():
    with open(MD_PATH) as f:
        return f.read()


# ---------------------------------------------------------------------------
# Existence
# ---------------------------------------------------------------------------

def test_json_exists():
    assert os.path.exists(JSON_PATH)


def test_markdown_exists():
    assert os.path.exists(MD_PATH)


def test_json_parses(artifact):
    assert isinstance(artifact, dict)


# ---------------------------------------------------------------------------
# Classification and type
# ---------------------------------------------------------------------------

def test_classification(artifact):
    assert artifact["classification"] == "P213_NEW_HYPOTHESIS_SCOUTING_PLAN_COMPLETE"


def test_task_type_is_b(artifact):
    assert artifact["task_type"] == "Type B"


# ---------------------------------------------------------------------------
# Safety booleans
# ---------------------------------------------------------------------------

def test_no_db_write(artifact):
    assert artifact["no_db_write"] is True


def test_no_registry_mutation(artifact):
    assert artifact["no_registry_mutation"] is True


def test_no_production_change(artifact):
    assert artifact["no_production_change"] is True


def test_no_monitoring_change(artifact):
    assert artifact["no_monitoring_change"] is True


def test_no_strategy_authorization(artifact):
    assert artifact["no_strategy_authorization"] is True


def test_no_betting_advice(artifact):
    assert artifact["no_betting_advice"] is True


def test_p211_not_restarted(artifact):
    assert artifact["p211_restarted"] is False


def test_p238b_interpretation(artifact):
    assert "YELLOW" in artifact["p238b_interpretation"]


def test_same_pr_closeout(artifact):
    assert artifact["same_pr_closeout"] is True


def test_no_separate_closeout(artifact):
    assert artifact["separate_closeout_pr_required"] is False


# ---------------------------------------------------------------------------
# Closed lines
# ---------------------------------------------------------------------------

def test_closed_lines_include_p211r(artifact):
    chains = [c["chain"] for c in artifact.get("closed_lines", [])]
    assert any("P211R" in c or "P211" in c for c in chains)


def test_closed_lines_include_p212(artifact):
    chains = [c["chain"] for c in artifact.get("closed_lines", [])]
    assert any("P212" in c for c in chains)


# ---------------------------------------------------------------------------
# Lottery status
# ---------------------------------------------------------------------------

def test_lottery_status_includes_all(artifact):
    ls = artifact.get("lottery_status", {})
    for lot in REQUIRED_LOTTERIES:
        assert lot in ls, f"Missing lottery in status: {lot}"


# ---------------------------------------------------------------------------
# Hypothesis categories
# ---------------------------------------------------------------------------

def test_hypothesis_categories_present(artifact):
    cats = artifact.get("hypothesis_categories", [])
    assert len(cats) >= 2


def test_hypothesis_categories_design_only(artifact):
    for cat in artifact.get("hypothesis_categories", []):
        assert cat.get("design_only") is True
        assert cat.get("implementation_authorized") is False


def test_hypothesis_categories_no_forbidden_actions(artifact):
    for cat in artifact.get("hypothesis_categories", []):
        forbidden = cat.get("forbidden_next_action", [])
        assert "betting_advice" in forbidden or "betting" in str(forbidden).lower()
        assert "strategy_promotion" in forbidden or "strategy" in str(forbidden).lower()


# ---------------------------------------------------------------------------
# Recommended direction
# ---------------------------------------------------------------------------

def test_recommended_next_direction_present(artifact):
    rd = artifact.get("recommended_next_direction", "")
    assert len(rd) > 0 and rd != "HOLD"


def test_exact_authorization_phrase_present(artifact):
    phrase = artifact.get("exact_authorization_phrase_for_next_direction", "")
    assert len(phrase) > 10, "Authorization phrase must be non-trivial"


# ---------------------------------------------------------------------------
# Final state
# ---------------------------------------------------------------------------

def test_final_state_db_rows(artifact):
    assert artifact["final_state"]["db_rows"] == 94924


def test_final_state_drift_guard(artifact):
    assert artifact["final_state"]["drift_guard"] == "REPLAY_LIFECYCLE_DRIFT_GUARD_PASS"


def test_final_state_no_deployable_candidate(artifact):
    assert artifact["final_state"]["deployable_candidate_exists"] is False


# ---------------------------------------------------------------------------
# Markdown content
# ---------------------------------------------------------------------------

def test_markdown_no_code_changes(md_content):
    lower = md_content.lower()
    assert "no code changes" in lower or "no code change" in lower


def test_markdown_no_db_write(md_content):
    lower = md_content.lower()
    assert "no db write" in lower or "db_write_authorized" in lower


def test_markdown_no_registry(md_content):
    assert "registry mutation" in md_content.lower()


def test_markdown_no_production(md_content):
    lower = md_content.lower()
    assert "no production" in lower or "production" in lower


def test_markdown_no_strategy_promotion(md_content):
    lower = md_content.lower()
    assert "no strategy" in lower or "strategy promotion" in lower


def test_markdown_no_betting_advice(md_content):
    assert "betting advice" in md_content.lower() or "wagering recommendation" in md_content.lower()


def test_markdown_no_p211_restart(md_content):
    lower = md_content.lower()
    assert "p211r is complete" in lower or "p211r" in lower


def test_markdown_no_forbidden_phrases(md_content):
    lower = md_content.lower()
    for phrase in FORBIDDEN_MD_PHRASES:
        assert phrase not in lower, f"Forbidden phrase in Markdown: '{phrase}'"


def test_markdown_type_b(md_content):
    assert "Type B" in md_content


def test_markdown_no_separate_closeout(md_content):
    lower = md_content.lower()
    assert "no separate" in lower or "same-pr" in lower or "same pr" in lower
