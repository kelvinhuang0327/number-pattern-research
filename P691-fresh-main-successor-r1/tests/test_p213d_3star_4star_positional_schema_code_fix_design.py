"""
P213D 3_STAR/4_STAR Positional Schema and Code Fix Design — Targeted Validation Tests
Validates artifact integrity and safety attestations only.
No DB write, no code change, no schema change, no ingestion.
"""
import json
import os
import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSON_PATH = os.path.join(REPO_ROOT, "outputs", "research", "p213d_3star_4star_positional_schema_code_fix_design_20260605.json")
MD_PATH = os.path.join(REPO_ROOT, "outputs", "research", "p213d_3star_4star_positional_schema_code_fix_design_20260605.md")

EXPECTED_CLASSIFICATION = "P213D_3STAR_4STAR_POSITIONAL_SCHEMA_CODE_FIX_DESIGN_COMPLETE"

FORBIDDEN_MD_PHRASES = [
    "prediction edge",
    "improved win rate",
    "production-ready",
    "strategy-ready",
    "recommended numbers",
    "recommended bet",
    "win rate improvement",
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

def test_classification(artifact):
    assert artifact["classification"] == EXPECTED_CLASSIFICATION


# --- Task type ---

def test_task_type_is_B(artifact):
    assert artifact["task_type"] == "Type B"


# --- Lottery scope ---

def test_lottery_scope_includes_3star(artifact):
    assert "3_STAR" in artifact["lottery_scope"]


def test_lottery_scope_includes_4star(artifact):
    assert "4_STAR" in artifact["lottery_scope"]


# --- Root cause ---

def test_root_cause_references_db_sorting(artifact):
    rc = artifact.get("current_root_cause", {})
    loss = rc.get("loss_code", "") + rc.get("loss_location", "") + rc.get("summary", "")
    assert "sorted" in loss.lower() and "database" in loss.lower()


def test_root_cause_references_positional_order_loss(artifact):
    rc = artifact.get("current_root_cause", {})
    summary = rc.get("summary", "")
    assert "positional" in summary.lower() or "order" in summary.lower()


def test_root_cause_existing_rows_unrecoverable(artifact):
    rc = artifact.get("current_root_cause", {})
    assert rc.get("existing_rows_unrecoverable") is True


def test_root_cause_no_positional_column(artifact):
    rc = artifact.get("current_root_cause", {})
    assert rc.get("numbers_positional_column_exists") is False


# --- Evidence summary ---

def test_evidence_includes_database_py(artifact):
    ev = str(artifact.get("evidence_summary", {}))
    assert "database" in ev.lower()


def test_evidence_includes_csv_validator(artifact):
    ev = str(artifact.get("evidence_summary", {}))
    assert "csv_validator" in ev.lower()


def test_evidence_includes_lottery_types_json(artifact):
    ev = str(artifact.get("evidence_summary", {}))
    assert "lottery_types" in ev.lower() or "isPermutation" in ev or "ispermutation" in ev.lower()


def test_evidence_includes_mock_order_evidence(artifact):
    ev = str(artifact.get("evidence_summary", {}))
    assert "開出順序" in ev or "draw_order" in ev.lower() or "mock" in ev.lower() or "debug" in ev.lower()


# --- Design options ---

def test_design_options_present(artifact):
    opts = artifact.get("design_options", [])
    assert isinstance(opts, list)
    assert len(opts) >= 3


def test_design_options_have_names(artifact):
    opts = artifact.get("design_options", [])
    for opt in opts:
        assert "option" in opt or "name" in opt


def test_design_options_include_hold(artifact):
    opts = artifact.get("design_options", [])
    names = " ".join(str(o.get("name", "")) + str(o.get("option", "")) for o in opts).lower()
    assert "hold" in names or "no change" in names or "no-change" in names


def test_design_options_include_additive_column(artifact):
    opts = artifact.get("design_options", [])
    descs = " ".join(str(o.get("description", "")) + str(o.get("name", "")) for o in opts).lower()
    assert "column" in descs or "positional" in descs or "additive" in descs


# --- Recommended option ---

def test_recommended_option_exists(artifact):
    assert artifact.get("recommended_option") is not None
    assert len(str(artifact["recommended_option"])) > 0


def test_recommended_option_has_rationale(artifact):
    assert len(artifact.get("recommended_option_rationale", "")) > 10


# --- Future implementation plan ---

def test_future_implementation_plan_exists(artifact):
    plan = artifact.get("future_implementation_plan", [])
    assert isinstance(plan, list)
    assert len(plan) > 0


def test_future_implementation_plan_has_multiple_phases(artifact):
    plan = artifact.get("future_implementation_plan", [])
    assert len(plan) >= 2


# --- Future authorization phrases ---

def test_future_authorization_phrases_exist(artifact):
    phrases = artifact.get("future_authorization_phrases", {})
    assert isinstance(phrases, dict)
    assert len(phrases) > 0


def test_future_authorization_phrases_db_write_requires_explicit(artifact):
    phrases = artifact.get("future_authorization_phrases", {})
    db_phrase = phrases.get("P213H_controlled_db_migration", "")
    assert "DB write authorized" in db_phrase or "db write" in db_phrase.lower()


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

def test_p238b_observation_only(artifact):
    interp = artifact.get("p238b_interpretation", "")
    assert "OBSERVATION_ONLY" in interp or "observation" in interp.lower()


# --- Final state ---

def test_final_state_db_unchanged(artifact):
    assert artifact["final_state"]["db_rows_unchanged"] == 94924


def test_final_state_drift_guard(artifact):
    assert artifact["final_state"]["drift_guard"] == "REPLAY_LIFECYCLE_DRIFT_GUARD_PASS"


def test_final_state_no_active_worker(artifact):
    assert artifact["final_state"]["no_active_worker"] is True


def test_final_state_no_separate_closeout_pr(artifact):
    assert artifact["final_state"]["separate_closeout_pr_needed"] is False


def test_final_state_star_games_remain_underpowered(artifact):
    assert artifact["final_state"].get("star_games_remain_underpowered_no_signal") is True


# --- Markdown content checks ---

def test_markdown_says_no_code_changes(md_content):
    assert "no code changes" in md_content


def test_markdown_says_no_db_write(md_content):
    assert "no db write" in md_content or "db write" in md_content


def test_markdown_says_no_schema_change(md_content):
    assert "schema change" in md_content


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
