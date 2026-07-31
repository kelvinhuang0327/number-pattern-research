"""
P271B — Official Prize Rule Verification and Scoring Engine Design
Tests verify the artifact JSON and MD, not any production code.
No backtest, no DB write, no registry mutation, no strategy generation.
"""
import json
import os
import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSON_PATH = os.path.join(REPO_ROOT, "outputs", "research",
                         "p271b_official_prize_rule_scoring_engine_design_20260611.json")
MD_PATH = os.path.join(REPO_ROOT, "outputs", "research",
                       "p271b_official_prize_rule_scoring_engine_design_20260611.md")

ALLOWED_FINAL_CLASSIFICATIONS = {
    "P271B_OFFICIAL_PRIZE_RULE_SCORING_ENGINE_DESIGN_COMPLETE",
    "P271B_DATA_REQUIRED_OFFICIAL_RULE_EXTRACTION",
    "P271B_BLOCKED_P271A_MISMATCH",
    "P271B_BLOCKED_GOVERNANCE_CONFLICT",
}

OFFICIAL_SOURCES_REQUIRED = [
    "https://www.taiwanlottery.com/lotto/info/super_lotto638",
    "https://www.taiwanlottery.com/lotto/info/lotto649",
    "https://www.taiwanlottery.com/lotto/info/daily_cash",
]

FORBIDDEN_HIT_RATE_PHRASES = [
    # Only affirmative claims — negation context ("does NOT imply improved prediction accuracy") is valid safety language
    "中獎率提升",
    "命中率提升",
    "accuracy improved",
    "win rate improved",
]

FORBIDDEN_BETTING_PHRASES = [
    # Only affirmative claims — negation context ("not ... a guaranteed win") is valid safety language
    "推薦投注",
    "建議下注",
    "勝率保證",
    "we recommend betting",
    "buy ticket",
    "purchase ticket",
]


@pytest.fixture(scope="module")
def artifact():
    with open(JSON_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def md_content():
    with open(MD_PATH, encoding="utf-8") as f:
        return f.read()


# ── 1. File existence ─────────────────────────────────────────────────────────

def test_json_artifact_exists():
    assert os.path.isfile(JSON_PATH), f"JSON artifact not found: {JSON_PATH}"


def test_md_artifact_exists():
    assert os.path.isfile(MD_PATH), f"MD artifact not found: {MD_PATH}"


# ── 2. Final classification ───────────────────────────────────────────────────

def test_final_classification_allowed(artifact):
    fc = artifact.get("final_classification")
    assert fc in ALLOWED_FINAL_CLASSIFICATIONS, (
        f"final_classification '{fc}' not in allowed set"
    )


# ── 3. Official sources ───────────────────────────────────────────────────────

def test_official_sources_include_all_three(artifact):
    sources = artifact.get("official_sources", [])
    for url in OFFICIAL_SOURCES_REQUIRED:
        assert url in sources, f"Official source URL missing: {url}"


# ── 4. source_status_by_lottery ──────────────────────────────────────────────

def test_source_status_by_lottery_exists(artifact):
    assert "source_status_by_lottery" in artifact
    ssbl = artifact["source_status_by_lottery"]
    assert "POWER_LOTTO" in ssbl
    assert "BIG_LOTTO" in ssbl
    assert "DAILY_539" in ssbl


# ── 5-8. tier_mapping_by_lottery ─────────────────────────────────────────────

def test_tier_mapping_exists(artifact):
    assert "tier_mapping_by_lottery" in artifact


def test_tier_mapping_includes_power_lotto(artifact):
    assert "POWER_LOTTO" in artifact["tier_mapping_by_lottery"]


def test_tier_mapping_includes_big_lotto(artifact):
    assert "BIG_LOTTO" in artifact["tier_mapping_by_lottery"]


def test_tier_mapping_includes_daily_539(artifact):
    assert "DAILY_539" in artifact["tier_mapping_by_lottery"]


# ── 9. POWER_LOTTO first-area and second-area logic ──────────────────────────

def test_power_lotto_has_first_area_tiers(artifact):
    power = artifact["tier_mapping_by_lottery"]["POWER_LOTTO"]
    assert "first_area_tiers" in power
    assert len(power["first_area_tiers"]) > 0


def test_power_lotto_has_second_area_tiers(artifact):
    power = artifact["tier_mapping_by_lottery"]["POWER_LOTTO"]
    assert "second_area_dependent_tiers" in power
    assert len(power["second_area_dependent_tiers"]) > 0


def test_power_lotto_any_prize_endpoint_present(artifact):
    power = artifact["tier_mapping_by_lottery"]["POWER_LOTTO"]
    assert "any_prize_aware_win_endpoint" in power
    endpoint = power["any_prize_aware_win_endpoint"]
    assert "hit_count" in endpoint and "special_hit" in endpoint


# ── 10. BIG_LOTTO main-number and special-number logic ───────────────────────

def test_big_lotto_has_main_number_tiers(artifact):
    big = artifact["tier_mapping_by_lottery"]["BIG_LOTTO"]
    assert "main_number_tiers" in big
    assert len(big["main_number_tiers"]) > 0


def test_big_lotto_has_special_number_tiers(artifact):
    big = artifact["tier_mapping_by_lottery"]["BIG_LOTTO"]
    assert "special_number_dependent_tiers" in big
    assert len(big["special_number_dependent_tiers"]) > 0


def test_big_lotto_consolation_prize_present(artifact):
    big = artifact["tier_mapping_by_lottery"]["BIG_LOTTO"]
    special_tiers = big["special_number_dependent_tiers"]
    tier_classes = [t["tier_class"] for t in special_tiers]
    assert "BIG_CONSOLATION_PRIZE" in tier_classes


# ── 11. DAILY_539 is main-number only ────────────────────────────────────────

def test_daily_539_is_main_number_only(artifact):
    d539 = artifact["tier_mapping_by_lottery"]["DAILY_539"]
    assert "main_number_only_tiers" in d539
    assert "second_area_dependent_tiers" not in d539
    assert "special_number_dependent_tiers" not in d539


def test_daily_539_has_four_tiers(artifact):
    d539 = artifact["tier_mapping_by_lottery"]["DAILY_539"]
    assert len(d539["main_number_only_tiers"]) == 4


# ── 12. p271a_alignment_check ────────────────────────────────────────────────

def test_p271a_alignment_check_exists(artifact):
    assert "p271a_alignment_check" in artifact


def test_p271a_alignment_check_status_pass(artifact):
    check = artifact["p271a_alignment_check"]
    assert check.get("status") == "PASS"


def test_p271a_no_mismatches(artifact):
    mismatches = artifact.get("mismatches_with_p271a", [])
    assert isinstance(mismatches, list)
    assert len(mismatches) == 0, f"Unexpected P271A mismatches: {mismatches}"


# ── 13. scoring_engine_design ────────────────────────────────────────────────

def test_scoring_engine_design_exists(artifact):
    assert "scoring_engine_design" in artifact


def test_scoring_engine_module_name_specified(artifact):
    sed = artifact["scoring_engine_design"]
    assert "module_name" in sed
    assert "prize_aware" in sed["module_name"]


def test_scoring_engine_forbidden_imports_specified(artifact):
    sed = artifact["scoring_engine_design"]
    assert "forbidden_imports" in sed
    assert len(sed["forbidden_imports"]) > 0


# ── 14. input_contract ───────────────────────────────────────────────────────

def test_input_contract_exists(artifact):
    assert "input_contract" in artifact


def test_input_contract_has_required_fields(artifact):
    ic = artifact["input_contract"]
    assert "inputs" in ic
    inputs = ic["inputs"]
    assert "lottery_type" in inputs
    assert "hit_count" in inputs
    assert "special_hit" in inputs


# ── 15. output_contract ──────────────────────────────────────────────────────

def test_output_contract_exists(artifact):
    assert "output_contract" in artifact


def test_output_contract_has_required_fields(artifact):
    oc = artifact["output_contract"]
    assert "outputs" in oc
    outputs = oc["outputs"]
    assert "tier_class" in outputs
    assert "is_prize_aware_win" in outputs
    assert "is_m3_plus" in outputs


def test_output_contract_coexistence_guarantee(artifact):
    oc = artifact["output_contract"]
    assert "coexistence_guarantee" in oc
    cg = oc["coexistence_guarantee"].lower()
    assert "m3" in cg or "m3+" in cg


# ── 16. unit_test_fixture_matrix ─────────────────────────────────────────────

def test_unit_test_fixture_matrix_exists(artifact):
    assert "unit_test_fixture_matrix" in artifact


def test_unit_test_fixture_matrix_power_lotto(artifact):
    fixtures = artifact["unit_test_fixture_matrix"]
    assert "POWER_LOTTO" in fixtures
    assert len(fixtures["POWER_LOTTO"]) >= 10


def test_unit_test_fixture_matrix_big_lotto(artifact):
    fixtures = artifact["unit_test_fixture_matrix"]
    assert "BIG_LOTTO" in fixtures
    assert len(fixtures["BIG_LOTTO"]) >= 8


def test_unit_test_fixture_matrix_daily_539(artifact):
    fixtures = artifact["unit_test_fixture_matrix"]
    assert "DAILY_539" in fixtures
    assert len(fixtures["DAILY_539"]) >= 4


def test_fixture_matrix_power_consolation_prize_is_win(artifact):
    fixtures = artifact["unit_test_fixture_matrix"]["POWER_LOTTO"]
    consolation = [f for f in fixtures
                   if f.get("expected_tier") == "POWER_CONSOLATION_PRIZE"]
    assert len(consolation) >= 1
    assert consolation[0]["expected_win"] is True
    assert consolation[0]["expected_m3_plus"] is False


def test_fixture_matrix_big_consolation_prize_is_win(artifact):
    fixtures = artifact["unit_test_fixture_matrix"]["BIG_LOTTO"]
    consolation = [f for f in fixtures
                   if f.get("expected_tier") == "BIG_CONSOLATION_PRIZE"]
    assert len(consolation) >= 1
    assert consolation[0]["expected_win"] is True
    assert consolation[0]["expected_m3_plus"] is False


def test_fixture_matrix_d539_fourth_prize_is_win_not_m3(artifact):
    fixtures = artifact["unit_test_fixture_matrix"]["DAILY_539"]
    fourth = [f for f in fixtures
              if f.get("expected_tier") == "D539_FOURTH_PRIZE"]
    assert len(fourth) >= 1
    assert fourth[0]["expected_win"] is True
    assert fourth[0]["expected_m3_plus"] is False


# ── 17. parallel_feature_design ──────────────────────────────────────────────

def test_parallel_feature_design_exists(artifact):
    assert "parallel_feature_design" in artifact


def test_parallel_feature_design_principle_states_not_replacement(artifact):
    pfd = artifact["parallel_feature_design"]
    principle = pfd.get("principle", "").lower()
    assert "not" in principle or "parallel" in principle


def test_parallel_feature_design_existing_track_preserved(artifact):
    pfd = artifact["parallel_feature_design"]
    assert "existing_track_preserved" in pfd


def test_parallel_feature_design_no_migration_path(artifact):
    pfd = artifact["parallel_feature_design"]
    assert "no_migration_path" in pfd
    assert pfd.get("replacement_migration_authorized") is False


# ── 18–28. Governance boolean fields ─────────────────────────────────────────

def test_m3_replay_scoring_changed_is_false(artifact):
    assert artifact.get("m3_replay_scoring_changed") is False


def test_replacement_migration_authorized_is_false(artifact):
    assert artifact.get("replacement_migration_authorized") is False


def test_no_backtest_run_is_true(artifact):
    assert artifact.get("no_backtest_run") is True


def test_replay_evaluation_run_is_false(artifact):
    assert artifact.get("replay_evaluation_run") is False


def test_db_write_is_false(artifact):
    assert artifact.get("db_write") is False


def test_registry_write_is_false(artifact):
    assert artifact.get("registry_write") is False


def test_strategy_generated_is_false(artifact):
    assert artifact.get("strategy_generated") is False


def test_hit_rate_improvement_claimed_is_false(artifact):
    assert artifact.get("hit_rate_improvement_claimed") is False


def test_p270c_allowed_is_false(artifact):
    assert artifact.get("p270c_allowed") is False


def test_p271c_started_is_false(artifact):
    assert artifact.get("p271c_started") is False


def test_p271d_started_is_false(artifact):
    assert artifact.get("p271d_started") is False


# ── 29. MD: no hit-rate improvement claim ────────────────────────────────────

def test_md_no_hit_rate_improvement_claim(md_content):
    content_lower = md_content.lower()
    for phrase in FORBIDDEN_HIT_RATE_PHRASES:
        assert phrase.lower() not in content_lower, (
            f"Forbidden hit-rate improvement phrase found in MD: '{phrase}'"
        )


# ── 30. MD: no betting/actionable strategy language ──────────────────────────

def test_md_no_betting_language(md_content):
    content_lower = md_content.lower()
    for phrase in FORBIDDEN_BETTING_PHRASES:
        assert phrase.lower() not in content_lower, (
            f"Forbidden betting phrase found in MD: '{phrase}'"
        )


# ── 31. MD: states prize-aware scoring is specification/design only ───────────

def test_md_states_prize_aware_is_design_only(md_content):
    content_lower = md_content.lower()
    assert (
        "specification" in content_lower
        or "design" in content_lower
        or "spec" in content_lower
    ), "MD must state prize-aware scoring is specification/design only"


def test_md_states_parallel_feature(md_content):
    assert "parallel" in md_content.lower() or "Parallel" in md_content


def test_md_states_m3_preserved(md_content):
    assert "unchanged" in md_content.lower() or "preserved" in md_content.lower()


def test_md_states_no_backtest(md_content):
    assert "no backtest was run" in md_content.lower()


def test_md_states_no_db_write(md_content):
    assert "no db write" in md_content.lower()


def test_md_states_no_strategy_generated(md_content):
    assert "no strategy" in md_content.lower()


def test_md_states_no_replacement_authorized(md_content):
    assert "replacement" in md_content.lower() and (
        "not authorized" in md_content.lower()
        or "is not authorized" in md_content.lower()
        or "Replacement/migration is not authorized" in md_content
    )


def test_md_states_p270c_not_authorized(md_content):
    assert "P270C" in md_content and (
        "not authorized" in md_content.lower()
        or "remains not authorized" in md_content.lower()
    )
