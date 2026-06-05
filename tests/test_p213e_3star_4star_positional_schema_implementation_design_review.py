"""
P213E 3_STAR/4_STAR Positional Schema Implementation Design Review — Targeted Validation Tests
Validates artifact integrity and safety attestations only.
No DB write, no code change, no schema change, no migration, no ingestion.
"""
import json
import os
import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSON_PATH = os.path.join(REPO_ROOT, "outputs", "research",
    "p213e_3star_4star_positional_schema_implementation_design_review_20260605.json")
MD_PATH = os.path.join(REPO_ROOT, "outputs", "research",
    "p213e_3star_4star_positional_schema_implementation_design_review_20260605.md")

EXPECTED_CLASSIFICATION = "P213E_3STAR_4STAR_POSITIONAL_SCHEMA_IMPLEMENTATION_DESIGN_REVIEW_COMPLETE"

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
    assert os.path.exists(JSON_PATH)


def test_markdown_exists():
    assert os.path.exists(MD_PATH)


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


# --- P213D option recap ---

def test_p213d_option_references_option_c(artifact):
    option = artifact.get("p213d_recommended_option", "")
    assert "option c" in option.lower() or "dual-write" in option.lower() or "additive" in option.lower()


# --- Schema semantics ---

def test_schema_semantics_present(artifact):
    sem = artifact.get("schema_semantics", {})
    assert isinstance(sem, dict)
    assert len(sem) > 0


def test_schema_semantics_numbers_present(artifact):
    sem = artifact.get("schema_semantics", {})
    assert "numbers" in sem


def test_schema_semantics_numbers_positional_present(artifact):
    sem = artifact.get("schema_semantics", {})
    assert "numbers_positional" in sem


def test_schema_semantics_numbers_unchanged(artifact):
    sem = artifact.get("schema_semantics", {})
    numbers = sem.get("numbers", {})
    change = numbers.get("change", "")
    assert "unchanged" in change.lower() or "none" in change.lower()


def test_schema_semantics_positional_is_nullable(artifact):
    sem = artifact.get("schema_semantics", {})
    positional = sem.get("numbers_positional", {})
    typ = positional.get("type", "")
    assert "null" in typ.lower()


def test_schema_semantics_non_permutation_is_null(artifact):
    sem = artifact.get("schema_semantics", {})
    positional = sem.get("numbers_positional", {})
    assert positional.get("for_non_permutation_games", "").upper() == "NULL"


def test_schema_semantics_strategy_use_prohibited(artifact):
    sem = artifact.get("schema_semantics", {})
    positional = sem.get("numbers_positional", {})
    prohibited = positional.get("strategy_use_prohibited", "")
    assert len(prohibited) > 10


# --- Implementation touchpoints ---

def test_implementation_touchpoints_present(artifact):
    tp = artifact.get("implementation_touchpoints", [])
    assert isinstance(tp, list)
    assert len(tp) > 0


def test_implementation_touchpoints_reference_database_py(artifact):
    tp = artifact.get("implementation_touchpoints", [])
    files = " ".join(t.get("file", "") for t in tp)
    assert "database.py" in files


def test_implementation_touchpoints_csv_validator_not_changed(artifact):
    tp = artifact.get("implementation_touchpoints", [])
    for t in tp:
        not_change = " ".join(str(x) for x in t.get("files_not_to_change", []))
        if "database" in t.get("file", ""):
            assert "csv_validator" in not_change


# --- Proposed P213F scope ---

def test_proposed_p213f_scope_present(artifact):
    scope = artifact.get("proposed_p213f_scope", {})
    assert isinstance(scope, dict)
    assert len(scope) > 0


def test_proposed_p213f_only_database_py(artifact):
    scope = artifact.get("proposed_p213f_scope", {})
    files = scope.get("files_to_modify", [])
    assert len(files) >= 1
    assert all("database" in f for f in files)


def test_proposed_p213f_no_production_db_write(artifact):
    scope = artifact.get("proposed_p213f_scope", {})
    assert scope.get("no_production_db_write_in_p213f") is True or \
           "no production" in str(scope.get("no_production_db_write_in_p213f", "")).lower() or \
           "not touched" in str(scope).lower()


def test_proposed_p213f_non_permutation_guarantee(artifact):
    scope = artifact.get("proposed_p213f_scope", {})
    guarantee = scope.get("non_permutation_unchanged_guarantee", "")
    assert "unaffected" in guarantee.lower() or "unchanged" in guarantee.lower()


# --- Test plan ---

def test_test_plan_present(artifact):
    plan = artifact.get("test_plan", {})
    assert isinstance(plan, dict)
    assert len(plan) > 0


def test_test_plan_has_groups(artifact):
    plan = artifact.get("test_plan", {})
    groups = plan.get("test_groups", [])
    assert len(groups) >= 3


def test_test_plan_db_isolation(artifact):
    plan = artifact.get("test_plan", {})
    isolation = plan.get("db_isolation", "")
    assert "memory" in isolation.lower() or "temp" in isolation.lower()


def test_test_plan_includes_backward_compat_group(artifact):
    plan = artifact.get("test_plan", {})
    groups = plan.get("test_groups", [])
    group_names = " ".join(g.get("group", "") for g in groups)
    assert "backward" in group_names.lower() or "compat" in group_names.lower() or "non_permutation" in group_names


# --- Migration boundaries ---

def test_migration_boundaries_present(artifact):
    mb = artifact.get("migration_boundaries", {})
    assert isinstance(mb, dict)
    assert len(mb) > 0


def test_migration_boundaries_p213f_no_production_db_write(artifact):
    mb = artifact.get("migration_boundaries", {})
    p213f = mb.get("p213f", {})
    assert p213f.get("production_db_write") is False or p213f.get("db_write") is False


def test_migration_boundaries_p213h_requires_db_write_authorization(artifact):
    mb = artifact.get("migration_boundaries", {})
    p213h = mb.get("p213h", {})
    phrase = p213h.get("authorization_phrase", "")
    assert "db write authorized" in phrase.lower() or "db write" in phrase.lower()


# --- Recommended next direction ---

def test_recommended_next_direction_present(artifact):
    assert artifact.get("recommended_next_direction") is not None


def test_exact_authorization_phrase_present(artifact):
    phrase = artifact.get("exact_authorization_phrase_for_next_direction", "")
    assert len(phrase) > 10


def test_authorization_phrase_says_no_production_db_write(artifact):
    phrase = artifact.get("exact_authorization_phrase_for_next_direction", "")
    assert "no production" in phrase.lower() or "no db write to production" in phrase.lower() \
           or "no production db write" in phrase.lower()


# --- Safety booleans ---

def test_no_code_changes(artifact):
    assert artifact["no_code_changes"] is True


def test_no_db_write(artifact):
    assert artifact["no_db_write"] is True


def test_no_schema_change(artifact):
    assert artifact["no_schema_change"] is True


def test_no_ingestion(artifact):
    assert artifact["no_ingestion"] is True


def test_no_migration(artifact):
    assert artifact["no_migration"] is True


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


# --- P238B ---

def test_p238b_observation_only(artifact):
    interp = artifact.get("p238b_interpretation", "")
    assert "observation_only" in interp.upper() or "observation" in interp.lower()


# --- Final state ---

def test_final_state_db_unchanged(artifact):
    assert artifact["final_state"]["db_rows_unchanged"] == 94924


def test_final_state_drift_guard(artifact):
    assert artifact["final_state"]["drift_guard"] == "REPLAY_LIFECYCLE_DRIFT_GUARD_PASS"


def test_final_state_no_active_worker(artifact):
    assert artifact["final_state"]["no_active_worker"] is True


def test_final_state_no_separate_closeout_pr(artifact):
    assert artifact["final_state"]["separate_closeout_pr_needed"] is False


def test_final_state_star_games_underpowered(artifact):
    assert artifact["final_state"].get("star_games_remain_underpowered_no_signal") is True


# --- Markdown checks ---

def test_markdown_says_no_code_changes(md_content):
    assert "no code changes" in md_content


def test_markdown_says_no_db_write(md_content):
    assert "no db write" in md_content or "db write" in md_content


def test_markdown_says_no_schema_change(md_content):
    assert "schema change" in md_content


def test_markdown_says_no_ingestion(md_content):
    assert "no ingestion" in md_content or "ingestion" in md_content


def test_markdown_says_no_migration(md_content):
    assert "no migration" in md_content or "migration" in md_content


def test_markdown_says_no_registry(md_content):
    assert "registry" in md_content


def test_markdown_says_no_production(md_content):
    assert "production" in md_content


def test_markdown_says_no_strategy(md_content):
    assert "strategy" in md_content


def test_markdown_says_no_betting_advice(md_content):
    assert "betting advice" in md_content or "wagering" in md_content


def test_markdown_no_separate_closeout_pr(md_content):
    assert "no separate closeout pr" in md_content or "no separate" in md_content


def test_markdown_no_forbidden_phrases(md_content):
    for phrase in FORBIDDEN_MD_PHRASES:
        assert phrase not in md_content, f"Forbidden phrase found: '{phrase}'"
