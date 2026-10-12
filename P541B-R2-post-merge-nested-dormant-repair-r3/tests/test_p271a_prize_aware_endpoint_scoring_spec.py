"""
P271A — Prize-Aware Endpoint & Scoring Specification Tests

Verifies that the P271A artifact JSON and MD exist and satisfy all governance requirements.
No backtest is run. No DB write occurs. No strategy is generated.
"""
import json
import os
import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSON_PATH = os.path.join(REPO_ROOT, "outputs", "research",
                         "p271a_prize_aware_endpoint_scoring_spec_20260611.json")
MD_PATH   = os.path.join(REPO_ROOT, "outputs", "research",
                         "p271a_prize_aware_endpoint_scoring_spec_20260611.md")

ALLOWED_CLASSIFICATIONS = {
    "P271A_PRIZE_AWARE_ENDPOINT_SPEC_COMPLETE",
    "P271A_DATA_REQUIRED_OFFICIAL_RULE_EXTRACTION",
    "P271A_BLOCKED_SCHEMA_MISMATCH",
    "P271A_BLOCKED_GOVERNANCE_CONFLICT",
}

OFFICIAL_SOURCES_REQUIRED = [
    "https://www.taiwanlottery.com/lotto/info/super_lotto638",
    "https://www.taiwanlottery.com/lotto/info/lotto649",
    "https://www.taiwanlottery.com/lotto/info/daily_cash",
]

POWER_SECOND_AREA_ENDPOINTS = [
    "POWER_M1_PLUS_SECOND",
    "POWER_M2_PLUS_SECOND",
    "POWER_M3_PLUS_SECOND",
    "POWER_M4_PLUS_SECOND",
    "POWER_M5_PLUS_SECOND",
    "POWER_M6_PLUS_SECOND",
    "POWER_M6_NO_SECOND",
    "POWER_ANY_PRIZE_AWARE_WIN",
    "POWER_TIER_CLASS",
    "POWER_MAIN_M3_PLUS_DIAGNOSTIC",
    "POWER_MAIN_M4_PLUS_DIAGNOSTIC",
]

BIG_SPECIAL_ENDPOINTS = [
    "BIG_M2_PLUS_SPECIAL",
    "BIG_M3_PLUS_SPECIAL",
    "BIG_M4_PLUS_SPECIAL",
    "BIG_M5_PLUS_SPECIAL",
    "BIG_M6_MAIN",
    "BIG_ANY_PRIZE_AWARE_WIN",
    "BIG_TIER_CLASS",
    "BIG_MAIN_M3_PLUS_DIAGNOSTIC",
    "BIG_MAIN_M4_PLUS_DIAGNOSTIC",
]

DAILY_539_MAIN_ONLY_ENDPOINTS = [
    "D539_M2_PLUS",
    "D539_M3_PLUS",
    "D539_M4_PLUS",
    "D539_M5",
    "D539_ANY_PRIZE_AWARE_WIN",
    "D539_TIER_CLASS",
]

FORBIDDEN_BETTING_PHRASES = [
    "推薦投注",
    "建議下注",
    "勝率保證",
    "guaranteed win",
    "we recommend betting",
    "buy ticket",
    "purchase ticket",
    "improves win rate",
    "增加中獎",
    "提高勝率",
]

# Phrases that indicate a POSITIVE claim of hit-rate improvement.
# The MD may contain negations like "No hit-rate improvement is claimed" — these are correct.
# We check for positive assertion patterns only.
FORBIDDEN_HIT_RATE_IMPROVEMENT_PHRASES = [
    "improved prediction accuracy",
    "improved win rate",
    "中獎率提升",
    "命中率提升",
    "accuracy improved",
    "win rate improved",
]

SPEC_ONLY_REQUIRED_PHRASES = [
    "specification only",
    "future evaluation",
    "not betting advice",
    "No backtest was run",
    "No DB write",
    "No strategy was generated",
]


@pytest.fixture(scope="module")
def artifact():
    with open(JSON_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def md_content():
    with open(MD_PATH, encoding="utf-8") as f:
        return f.read()


# ── 1 & 2: Artifact existence ────────────────────────────────────────────────

def test_json_artifact_exists():
    assert os.path.isfile(JSON_PATH), f"JSON artifact missing: {JSON_PATH}"


def test_md_artifact_exists():
    assert os.path.isfile(MD_PATH), f"MD artifact missing: {MD_PATH}"


# ── 3: Final classification is allowed ───────────────────────────────────────

def test_final_classification_is_allowed(artifact):
    fc = artifact["final_classification"]
    assert fc in ALLOWED_CLASSIFICATIONS, (
        f"final_classification '{fc}' not in allowed set: {ALLOWED_CLASSIFICATIONS}"
    )


# ── 4: Official sources include the three Taiwan Lottery URLs ─────────────────

def test_official_sources_present(artifact):
    sources = artifact["official_sources"]
    for url in OFFICIAL_SOURCES_REQUIRED:
        assert url in sources, f"official_sources missing: {url}"


# ── 5: POWER_LOTTO second-area endpoints ─────────────────────────────────────

def test_power_lotto_second_area_endpoints_present(artifact):
    ep = artifact["endpoint_definitions"]["POWER_LOTTO"]
    for name in POWER_SECOND_AREA_ENDPOINTS:
        assert name in ep, f"POWER_LOTTO endpoint missing: {name}"


def test_power_any_prize_aware_win_has_condition(artifact):
    ep = artifact["endpoint_definitions"]["POWER_LOTTO"]["POWER_ANY_PRIZE_AWARE_WIN"]
    assert "condition_sql" in ep
    cond = ep["condition_sql"]
    assert "special_hit" in cond, "POWER_ANY_PRIZE_AWARE_WIN must reference special_hit"
    assert "hit_count" in cond, "POWER_ANY_PRIZE_AWARE_WIN must reference hit_count"


def test_power_tier_class_has_values(artifact):
    tc = artifact["endpoint_definitions"]["POWER_LOTTO"]["POWER_TIER_CLASS"]
    assert "values" in tc
    values = [v["value"] for v in tc["values"]]
    assert "TIER_1_JACKPOT" in values
    assert "NO_PRIZE" in values


def test_power_main_m3_diagnostic_is_not_prize_aware(artifact):
    ep = artifact["endpoint_definitions"]["POWER_LOTTO"]["POWER_MAIN_M3_PLUS_DIAGNOSTIC"]
    assert ep.get("is_prize_aware") is False, (
        "POWER_MAIN_M3_PLUS_DIAGNOSTIC must be marked is_prize_aware=false"
    )


# ── 6: BIG_LOTTO special-number endpoints ────────────────────────────────────

def test_big_lotto_special_endpoints_present(artifact):
    ep = artifact["endpoint_definitions"]["BIG_LOTTO"]
    for name in BIG_SPECIAL_ENDPOINTS:
        assert name in ep, f"BIG_LOTTO endpoint missing: {name}"


def test_big_any_prize_aware_win_has_condition(artifact):
    ep = artifact["endpoint_definitions"]["BIG_LOTTO"]["BIG_ANY_PRIZE_AWARE_WIN"]
    assert "condition_sql" in ep
    cond = ep["condition_sql"]
    assert "special_hit" in cond
    assert "hit_count" in cond


def test_big_tier_class_has_values(artifact):
    tc = artifact["endpoint_definitions"]["BIG_LOTTO"]["BIG_TIER_CLASS"]
    assert "values" in tc
    values = [v["value"] for v in tc["values"]]
    assert "TIER_1_JACKPOT" in values
    assert "NO_PRIZE" in values


def test_big_main_m3_diagnostic_is_not_prize_aware(artifact):
    ep = artifact["endpoint_definitions"]["BIG_LOTTO"]["BIG_MAIN_M3_PLUS_DIAGNOSTIC"]
    assert ep.get("is_prize_aware") is False


# ── 7: DAILY_539 main-only endpoints ─────────────────────────────────────────

def test_daily_539_main_only_endpoints_present(artifact):
    ep = artifact["endpoint_definitions"]["DAILY_539"]
    for name in DAILY_539_MAIN_ONLY_ENDPOINTS:
        assert name in ep, f"DAILY_539 endpoint missing: {name}"


def test_daily_539_no_special_endpoint(artifact):
    """DAILY_539 endpoints must not mention second_zone or predicted_special as required."""
    ep = artifact["endpoint_definitions"]["DAILY_539"]
    # None of the DAILY_539 endpoints should have special_hit in their SQL conditions
    for name, defn in ep.items():
        if "condition_sql" in defn:
            cond = defn["condition_sql"]
            assert "special_hit" not in cond, (
                f"DAILY_539 endpoint {name} should not use special_hit in condition: {cond}"
            )


def test_daily_539_any_prize_win_covers_m2(artifact):
    ep = artifact["endpoint_definitions"]["DAILY_539"]["D539_ANY_PRIZE_AWARE_WIN"]
    cond = ep["condition_sql"]
    assert "hit_count >= 2" in cond, "D539_ANY_PRIZE_AWARE_WIN must cover hit_count>=2"


# ── 8: no_backtest_run is true ────────────────────────────────────────────────

def test_no_backtest_run(artifact):
    assert artifact["no_backtest_run"] is True


# ── 9: db_write is false ─────────────────────────────────────────────────────

def test_db_write_false(artifact):
    assert artifact["db_write"] is False


# ── 10: registry_write is false ──────────────────────────────────────────────

def test_registry_write_false(artifact):
    assert artifact["registry_write"] is False


# ── 11: strategy_generated is false ──────────────────────────────────────────

def test_strategy_generated_false(artifact):
    assert artifact["strategy_generated"] is False


# ── 12: hit_rate_improvement_claimed is false ─────────────────────────────────

def test_hit_rate_improvement_claimed_false(artifact):
    assert artifact["hit_rate_improvement_claimed"] is False


# ── 13: p270c_allowed is false ───────────────────────────────────────────────

def test_p270c_allowed_false(artifact):
    assert artifact["p270c_allowed"] is False


# ── 14: MD contains no hit-rate improvement claim ────────────────────────────

def test_md_no_hit_rate_improvement_claim(md_content):
    content_lower = md_content.lower()
    for phrase in FORBIDDEN_HIT_RATE_IMPROVEMENT_PHRASES:
        assert phrase.lower() not in content_lower, (
            f"MD contains forbidden hit-rate improvement phrase: '{phrase}'"
        )


# ── 15: MD contains no betting/actionable strategy language ──────────────────

def test_md_no_betting_language(md_content):
    content_lower = md_content.lower()
    for phrase in FORBIDDEN_BETTING_PHRASES:
        assert phrase.lower() not in content_lower, (
            f"MD contains forbidden betting/actionable phrase: '{phrase}'"
        )


# ── 16: MD states prize-aware endpoints are specification only ────────────────

def test_md_states_spec_only(md_content):
    found_any = False
    for phrase in SPEC_ONLY_REQUIRED_PHRASES:
        if phrase.lower() in md_content.lower():
            found_any = True
            break
    assert found_any, (
        f"MD must contain at least one spec-only declaration phrase. "
        f"Expected one of: {SPEC_ONLY_REQUIRED_PHRASES}"
    )


# ── Additional structural tests ───────────────────────────────────────────────

def test_artifact_has_required_top_level_fields(artifact):
    required = [
        "task_id", "generated_at", "repo_head", "branch", "mode",
        "official_sources", "source_status_by_lottery", "official_rule_summary_by_lottery",
        "lottery_type_mapping", "endpoint_definitions", "tier_class_definitions",
        "backward_compatibility_notes", "schema_inventory", "required_future_code_fields",
        "forbidden_actions", "no_backtest_run", "db_write", "registry_write",
        "strategy_generated", "hit_rate_improvement_claimed", "p270c_allowed",
        "next_recommended_task", "final_classification", "limitations",
    ]
    for field in required:
        assert field in artifact, f"Missing required top-level field: '{field}'"


def test_source_status_by_lottery_has_all_three(artifact):
    assert "POWER_LOTTO" in artifact["source_status_by_lottery"]
    assert "BIG_LOTTO" in artifact["source_status_by_lottery"]
    assert "DAILY_539" in artifact["source_status_by_lottery"]


def test_lottery_type_mapping_has_all_three(artifact):
    ltm = artifact["lottery_type_mapping"]
    assert "POWER_LOTTO" in ltm
    assert "BIG_LOTTO" in ltm
    assert "DAILY_539" in ltm


def test_endpoint_definitions_has_all_three_lotteries(artifact):
    ep = artifact["endpoint_definitions"]
    assert "POWER_LOTTO" in ep
    assert "BIG_LOTTO" in ep
    assert "DAILY_539" in ep


def test_tier_class_definitions_has_all_three(artifact):
    tc = artifact["tier_class_definitions"]
    assert "POWER_LOTTO_tier_class_ordered_by_rank" in tc
    assert "BIG_LOTTO_tier_class_ordered_by_rank" in tc
    assert "DAILY_539_tier_class_ordered_by_rank" in tc


def test_power_prize_tiers_complete(artifact):
    """POWER_LOTTO must have all 10 prize tiers defined."""
    tiers = artifact["official_rule_summary_by_lottery"]["POWER_LOTTO"]["prize_tiers"]
    assert len(tiers) == 10, f"POWER_LOTTO should have 10 prize tiers, got {len(tiers)}"


def test_big_lotto_prize_tiers_complete(artifact):
    """BIG_LOTTO must have all 8 prize tiers defined."""
    tiers = artifact["official_rule_summary_by_lottery"]["BIG_LOTTO"]["prize_tiers"]
    assert len(tiers) == 8, f"BIG_LOTTO should have 8 prize tiers, got {len(tiers)}"


def test_daily_539_prize_tiers_complete(artifact):
    """DAILY_539 must have all 4 prize tiers defined."""
    tiers = artifact["official_rule_summary_by_lottery"]["DAILY_539"]["prize_tiers"]
    assert len(tiers) == 4, f"DAILY_539 should have 4 prize tiers, got {len(tiers)}"


def test_daily_539_no_special_in_prize_tiers(artifact):
    """DAILY_539 prize tiers must not have special_hit=true."""
    tiers = artifact["official_rule_summary_by_lottery"]["DAILY_539"]["prize_tiers"]
    for t in tiers:
        assert t.get("special_hit") is False or t.get("special_hit") == False, (
            f"DAILY_539 prize tier {t} should not have special_hit=true"
        )


def test_schema_inventory_present(artifact):
    si = artifact["schema_inventory"]
    assert "table" in si
    assert si["table"] == "strategy_prediction_replays"
    assert "relevant_fields" in si
    fields = si["relevant_fields"]
    assert "hit_count" in fields
    assert "special_hit" in fields
    assert "predicted_special" in fields
    assert "actual_special" in fields


def test_power_predicted_special_gap_documented(artifact):
    """The 75% predicted_special gap for POWER_LOTTO must be documented."""
    limitations = " ".join(artifact.get("limitations", []))
    gap_mentioned = (
        "predicted_special" in limitations and "75%" in limitations
    ) or (
        "POWER_LOTTO_predicted_special_gap" in str(artifact["schema_inventory"])
    )
    assert gap_mentioned, (
        "POWER_LOTTO predicted_special gap (~75% null) must be documented in limitations or schema_inventory"
    )


def test_forbidden_actions_list_present(artifact):
    fa = artifact["forbidden_actions"]
    assert isinstance(fa, list)
    assert len(fa) >= 5
    combined = " ".join(fa).lower()
    assert "no backtest" in combined or "backtest" in combined
    assert "db write" in combined or "db_write" in combined
    assert "strategy" in combined


def test_backward_compatibility_notes_present(artifact):
    bc = artifact["backward_compatibility_notes"]
    assert "existing_m3plus_endpoint" in bc
    assert "POWER_LOTTO_M3_gap" in bc
    assert "BIG_LOTTO_M3_gap" in bc
    assert "DAILY_539_M3_gap" in bc


def test_next_recommended_task_present(artifact):
    nrt = artifact["next_recommended_task"]
    assert "task_id" in nrt
    assert nrt["task_id"] == "P271B"
    assert "authorization_required" in nrt


def test_mode_is_correct(artifact):
    assert artifact["mode"] == "prize_aware_endpoint_scoring_spec"


def test_task_id_is_correct(artifact):
    assert artifact["task_id"] == "P271A"


# ── Parallel-feature design tests ─────────────────────────────────────────────

def test_parallel_feature_design_block_present(artifact):
    """JSON must include a parallel_feature_design block."""
    assert "parallel_feature_design" in artifact, (
        "JSON must contain parallel_feature_design block (user-directed architectural principle)"
    )


def test_parallel_feature_design_states_not_replacement(artifact):
    pfd = artifact["parallel_feature_design"]
    principle = pfd.get("principle", "")
    assert "not a replacement" in principle.lower() or "NOT replace" in principle or "parallel" in principle.lower(), (
        "parallel_feature_design.principle must state that prize-aware is NOT a replacement"
    )


def test_parallel_feature_design_existing_track_preserved(artifact):
    pfd = artifact["parallel_feature_design"]
    assert "existing_track_preserved" in pfd
    preserved = pfd["existing_track_preserved"]
    assert "UNCHANGED" in str(preserved) or "unchanged" in str(preserved).lower()


def test_parallel_feature_design_no_migration_path(artifact):
    pfd = artifact["parallel_feature_design"]
    assert "no_migration_path" in pfd
    assert "migration" in pfd["no_migration_path"].lower()


def test_backward_compat_has_architectural_principle(artifact):
    bc = artifact["backward_compatibility_notes"]
    assert "architectural_principle" in bc
    principle = bc["architectural_principle"].lower()
    assert "parallel" in principle
    assert "not a replacement" in principle or "not deprecated" in principle or "not deprecated" in principle or "not replace" in principle


def test_backward_compat_has_coexistence_rule(artifact):
    bc = artifact["backward_compatibility_notes"]
    assert "coexistence_rule" in bc


def test_backward_compat_has_no_replacement_allowed(artifact):
    bc = artifact["backward_compatibility_notes"]
    assert "no_replacement_allowed" in bc


def test_md_states_parallel_feature(md_content):
    content_lower = md_content.lower()
    assert "parallel feature" in content_lower or "parallel track" in content_lower, (
        "MD must explicitly describe prize-aware scoring as a parallel feature/track"
    )


def test_md_states_not_replacement(md_content):
    content_lower = md_content.lower()
    assert "not a replacement" in content_lower or "not replace" in content_lower, (
        "MD must explicitly state that prize-aware scoring does not replace M3+"
    )


def test_md_states_m3_preserved(md_content):
    content_lower = md_content.lower()
    assert "preserved" in content_lower or "unchanged" in content_lower, (
        "MD must state that M3+ is preserved/unchanged"
    )
