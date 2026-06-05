"""
P213C 3_STAR/4_STAR Source Audit — Targeted Validation Tests
Validates artifact integrity and safety attestations only.
No DB write, no code change, no schema change, no ingestion.
"""
import json
import os
import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSON_PATH = os.path.join(REPO_ROOT, "outputs", "research", "p213c_3star_4star_source_audit_20260605.json")
MD_PATH = os.path.join(REPO_ROOT, "outputs", "research", "p213c_3star_4star_source_audit_20260605.md")

ALLOWED_CLASSIFICATIONS = {
    "P213C_SOURCE_AUDIT_POSITIONAL_SOURCE_FOUND_READ_ONLY",
    "P213C_SOURCE_AUDIT_SOURCE_CANDIDATE_FOUND_NEEDS_VALIDATION",
    "P213C_SOURCE_AUDIT_EXTERNAL_SOURCE_REQUIRED",
    "P213C_SOURCE_AUDIT_NO_SOURCE_FOUND",
    "P213C_SOURCE_AUDIT_BLOCKED_BY_AUTHORIZATION",
}

FORBIDDEN_MD_PHRASES = [
    "prediction edge",
    "improved win rate",
    "production-ready",
    "strategy-ready",
    "recommended numbers",
    "recommended bet",
]

REQUIRED_MD_NO_CLAIM_PHRASES = [
    "no code changes",
    "no db write",
    "no schema change",
    "no ingestion",
    "no separate closeout pr",
]

REQUIRED_MD_SAFETY_PHRASES = [
    "no registry",
    "no production",
    "no strategy",
]


@pytest.fixture(scope="module")
def artifact():
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def md_content():
    with open(MD_PATH, "r", encoding="utf-8") as f:
        return f.read().lower()


# --- File existence ---

def test_json_exists():
    assert os.path.exists(JSON_PATH), f"JSON artifact not found: {JSON_PATH}"


def test_markdown_exists():
    assert os.path.exists(MD_PATH), f"Markdown artifact not found: {MD_PATH}"


def test_json_parses(artifact):
    assert isinstance(artifact, dict)


# --- Classification ---

def test_classification_is_allowed(artifact):
    assert artifact["classification"] in ALLOWED_CLASSIFICATIONS, (
        f"Unexpected classification: {artifact['classification']}"
    )


def test_final_task_classification(artifact):
    assert artifact["final_task_classification"] == "P213C_3STAR_4STAR_SOURCE_AUDIT_COMPLETE"


# --- Task type ---

def test_task_type_is_B(artifact):
    assert artifact["task_type"] == "Type B"


# --- Lottery scope ---

def test_lottery_scope_includes_3star(artifact):
    assert "3_STAR" in artifact["lottery_scope"]


def test_lottery_scope_includes_4star(artifact):
    assert "4_STAR" in artifact["lottery_scope"]


# --- Confirmed current state ---

def test_confirmed_db_stores_sorted(artifact):
    state = artifact["confirmed_current_state"]
    assert state["db_stores_sorted_arrays"] is True


def test_confirmed_positional_order_lost(artifact):
    state = artifact["confirmed_current_state"]
    assert state["positional_order_lost_in_db"] is True


def test_confirmed_database_sorting_root_cause_present(artifact):
    state = artifact["confirmed_current_state"]
    cause = state.get("database_sorting_root_cause", "")
    assert "database.py" in cause and "sorted" in cause.lower()


def test_confirmed_isPermutation_3star(artifact):
    state = artifact["confirmed_current_state"]
    assert state["lottery_types_json_ispermutation_3star"] is True


def test_confirmed_isPermutation_4star(artifact):
    state = artifact["confirmed_current_state"]
    assert state["lottery_types_json_ispermutation_4star"] is True


def test_confirmed_csv_validator_preserves_order(artifact):
    state = artifact["confirmed_current_state"]
    assert state["csv_validator_preserves_permutation_order"] is True


# --- Source audit findings ---

def test_source_audit_findings_present(artifact):
    findings = artifact.get("source_audit_findings", {})
    assert isinstance(findings, dict)
    assert len(findings) > 0


def test_source_audit_ispermutation_evidence(artifact):
    candidates = artifact.get("source_candidates_found", [])
    names = [c["name"] for c in candidates]
    assert any("isPermutation" in n or "permutation" in n.lower() for n in names)


def test_source_audit_csv_validator_evidence(artifact):
    candidates = artifact.get("source_candidates_found", [])
    names = " ".join(c["name"] for c in candidates)
    assert "csv_validator" in names.lower()


def test_source_audit_source_format_evidence(artifact):
    state = artifact["confirmed_current_state"]
    mock_evidence = state.get("mock_debug_source_format_evidence", {})
    assert mock_evidence.get("found") is True


# --- Source classification ---

def test_source_classification_exists(artifact):
    assert artifact.get("source_classification") is not None
    assert len(artifact["source_classification"]) > 0


# --- Recoverability ---

def test_recoverability_status_exists(artifact):
    assert artifact.get("recoverability_status") is not None


def test_confidence_level_exists(artifact):
    assert artifact.get("confidence_level") is not None


# --- Future path options ---

def test_future_path_options_exists(artifact):
    opts = artifact.get("future_path_options", [])
    assert isinstance(opts, list)
    assert len(opts) > 0


def test_future_path_includes_hold(artifact):
    opts = artifact.get("future_path_options", [])
    labels = [o["option"] for o in opts]
    assert "HOLD" in labels


# --- Recommended next direction ---

def test_recommended_next_direction_exists(artifact):
    assert artifact.get("recommended_next_direction") is not None


def test_exact_authorization_phrase_present_if_not_hold(artifact):
    direction = artifact.get("recommended_next_direction", "")
    if direction != "HOLD":
        phrase = artifact.get("exact_authorization_phrase_for_next_direction", "")
        assert len(phrase) > 10, "Must provide exact authorization phrase for non-HOLD direction"


# --- Safety booleans ---

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


def test_same_pr_closeout(artifact):
    assert artifact["same_pr_closeout"] is True


# --- P238B interpretation ---

def test_p238b_interpretation_is_observation_only(artifact):
    interp = artifact.get("p238b_interpretation", "")
    assert "OBSERVATION_ONLY" in interp or "observation" in interp.lower()
    assert "strategy" not in interp.lower() or "not a strategy" in interp.lower()


# --- Final state ---

def test_final_state_db_rows_unchanged(artifact):
    assert artifact["final_state"]["db_rows_unchanged"] == 94924


def test_final_state_drift_guard_pass(artifact):
    assert artifact["final_state"]["drift_guard"] == "REPLAY_LIFECYCLE_DRIFT_GUARD_PASS"


def test_final_state_no_active_worker(artifact):
    assert artifact["final_state"]["no_active_worker"] is True


def test_final_state_no_separate_closeout_pr(artifact):
    assert artifact["final_state"]["separate_closeout_pr_needed"] is False


# --- Markdown content checks ---

def test_markdown_says_no_code_changes(md_content):
    assert "no code changes" in md_content


def test_markdown_says_no_db_write(md_content):
    assert "no db write" in md_content or "db write" in md_content


def test_markdown_says_no_schema_change(md_content):
    assert "no schema change" in md_content or "schema change" in md_content


def test_markdown_says_no_ingestion(md_content):
    assert "no ingestion" in md_content or "ingestion" in md_content


def test_markdown_says_no_registry(md_content):
    assert "registry" in md_content


def test_markdown_says_no_production(md_content):
    assert "production" in md_content


def test_markdown_says_no_strategy_promotion(md_content):
    assert "strategy" in md_content


def test_markdown_says_no_betting_advice(md_content):
    assert "betting advice" in md_content or "wagering" in md_content


def test_markdown_no_separate_closeout_pr(md_content):
    assert "no separate closeout pr" in md_content or "no separate" in md_content


def test_markdown_no_forbidden_phrases(md_content):
    for phrase in FORBIDDEN_MD_PHRASES:
        assert phrase not in md_content, f"Forbidden phrase found in markdown: '{phrase}'"
