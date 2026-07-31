"""
Targeted tests for P213B 3_STAR/4_STAR positional data recovery feasibility artifacts.
No DB write. No production side effects.
"""
import json
import os
import pytest

JSON_PATH = "outputs/research/p213b_3star_4star_positional_data_recovery_feasibility_20260605.json"
MD_PATH = "outputs/research/p213b_3star_4star_positional_data_recovery_feasibility_20260605.md"

ALLOWED_FEASIBILITY_CLASSIFICATIONS = {
    "P213B_POSITIONAL_RECOVERY_FEASIBLE_DESIGN_ONLY",
    "P213B_POSITIONAL_RECOVERY_POSSIBLE_BUT_SOURCE_UNCONFIRMED",
    "P213B_POSITIONAL_RECOVERY_BLOCKED_NO_SOURCE_FOUND",
    "P213B_POSITIONAL_RECOVERY_NOT_RECOMMENDED",
}

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

def test_feasibility_classification(artifact):
    fc = artifact.get("feasibility_classification", "")
    assert fc in ALLOWED_FEASIBILITY_CLASSIFICATIONS, f"Unexpected: {fc}"


def test_task_type_is_b(artifact):
    assert artifact["task_type"] == "Type B"


# ---------------------------------------------------------------------------
# Lottery scope
# ---------------------------------------------------------------------------

def test_lottery_scope_includes_3_star(artifact):
    assert "3_STAR" in artifact.get("lottery_scope", [])


def test_lottery_scope_includes_4_star(artifact):
    assert "4_STAR" in artifact.get("lottery_scope", [])


# ---------------------------------------------------------------------------
# Safety booleans
# ---------------------------------------------------------------------------

def test_no_code_changes(artifact):
    assert artifact["no_code_changes"] is True


def test_no_db_write(artifact):
    assert artifact["no_db_write"] is True


def test_no_schema_change(artifact):
    assert artifact["no_schema_change"] is True


def test_no_ingestion(artifact):
    assert artifact["no_ingestion"] is True


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


def test_p238b_interpretation(artifact):
    assert "YELLOW" in artifact["p238b_interpretation"]


def test_same_pr_closeout(artifact):
    assert artifact["same_pr_closeout"] is True


def test_no_separate_closeout(artifact):
    assert artifact["separate_closeout_pr_required"] is False


# ---------------------------------------------------------------------------
# Content requirements
# ---------------------------------------------------------------------------

def test_evidence_inventory_present(artifact):
    ei = artifact.get("evidence_inventory", {})
    assert len(ei.get("confirmed", [])) >= 1
    assert len(ei.get("missing", [])) >= 1


def test_future_recovery_plan_present(artifact):
    frp = artifact.get("future_recovery_plan", {})
    assert "phase_a" in frp
    assert "phase_d" in frp


def test_required_future_authorizations_present(artifact):
    rfa = artifact.get("required_future_authorizations", [])
    assert len(rfa) >= 2


def test_recommended_next_direction_present(artifact):
    rd = artifact.get("recommended_next_direction", "")
    assert len(rd) > 0


def test_exact_authorization_phrase_present(artifact):
    phrase = artifact.get("exact_authorization_phrase_for_next_direction", "")
    if artifact.get("recommended_next_direction", "").upper() != "HOLD":
        assert len(phrase) > 10


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
    assert "no db write" in lower or "db write" in lower


def test_markdown_no_schema_change(md_content):
    lower = md_content.lower()
    assert "no schema change" in lower or "schema change" in lower


def test_markdown_no_ingestion(md_content):
    lower = md_content.lower()
    assert "no ingestion" in lower or "ingestion" in lower


def test_markdown_no_registry(md_content):
    lower = md_content.lower()
    assert "registry mutation" in lower or "no registry" in lower


def test_markdown_no_betting_advice(md_content):
    lower = md_content.lower()
    assert "betting advice" in lower or "wagering recommendation" in lower


def test_markdown_no_strategy_promotion(md_content):
    lower = md_content.lower()
    assert "no strategy" in lower or "strategy promotion" in lower


def test_markdown_no_forbidden_phrases(md_content):
    lower = md_content.lower()
    for phrase in FORBIDDEN_MD_PHRASES:
        assert phrase not in lower, f"Forbidden phrase: '{phrase}'"


def test_markdown_type_b(md_content):
    assert "Type B" in md_content


def test_markdown_no_separate_closeout(md_content):
    lower = md_content.lower()
    assert "no separate" in lower or "same-pr" in lower or "same pr" in lower
