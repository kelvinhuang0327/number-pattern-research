"""
P271G — Prize-Aware Null Baseline & Prospective Holdout Preregistration Tests

Verifies that the P271G design artifact (JSON + MD) exists under the corrected
canonical `outputs/research/` convention and satisfies every governance
requirement of the preregistration.

P271G is DESIGN-ONLY with disclosed prior outcome exposure. These tests assert that:
  * no baseline / scorer / adapter / DB access / simulation occurred,
  * no p-value / CI / lift / effect value was calculated,
  * the retrospective (exploratory) and prospective (confirmatory) populations
    are kept separate,
  * the draw-cluster statistical unit and frozen null/endpoint/multiplicity
    contracts are present and correct,
  * no P271F result schema, result-artifact ingestion, strategy identifier, or
    DB path leaks into the final P271G files.

No backtest is run. No DB write occurs. No strategy is generated.
"""
import json
import os
import re

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

JSON_PATH = os.path.join(
    REPO_ROOT, "outputs", "research",
    "p271g_prize_aware_null_prospective_preregistration_20260612.json",
)
MD_PATH = os.path.join(
    REPO_ROOT, "outputs", "research",
    "p271g_prize_aware_null_prospective_preregistration_20260612.md",
)

# Incorrect, explicitly-forbidden legacy convention paths (must NOT exist).
REPORTS_JSON_PATH = os.path.join(
    REPO_ROOT, "reports", "research",
    "p271g_prize_aware_null_prospective_preregistration_20260612.json",
)
REPORTS_MD_PATH = os.path.join(
    REPO_ROOT, "reports", "research",
    "p271g_prize_aware_null_prospective_preregistration_20260612.md",
)

ALLOWED_CLASSIFICATIONS = {
    "P271G_NULL_AND_PROSPECTIVE_PREREGISTRATION_DESIGN_COMPLETE_WITH_PRIOR_OUTCOME_EXPOSURE",
    "P271G_BLOCKED_OUTCOME_VALUES_COPIED_INTO_FINAL_FILES",
    "P271G_BLOCKED_OUTCOME_DEPENDENT_DESIGN",
    "P271G_BLOCKED_STATISTICAL_UNIT_AMBIGUITY",
    "P271G_BLOCKED_NULL_GENERATOR_AMBIGUITY",
    "P271G_BLOCKED_GOVERNANCE_CONFLICT",
    "P271G_TEST_FAILURE",
}

FORBIDDEN_RESULT_SCHEMA_KEYS = {
    "main_hit_count_counts",
    "auxiliary_hit_false_count",
    "auxiliary_hit_true_count",
    "any_prize_aware_win_count",
    "any_prize_aware_win_rate",
    "prize_tier_counts",
    "prize_tier_rates",
    "tier_class_counts",
    "tier_class_rates",
    "m3_plus_false_count",
    "m3_plus_true_count",
    "m3_plus_rate",
    "prize_aware_and_m3_overlap_matrix",
    "results_by_lottery",
    "invariant_checks_by_lottery",
}

# Strategy identifier fragments that must not appear anywhere.
FORBIDDEN_STRATEGY_ID_FRAGMENTS = [
    "acb_", "midfreq", "fourier", "regime_", "f4cold", "markov", "ts3_",
    "orthogonal", "pp3_", "echo_aware", "neighbor_cold", "shlc",
    "1bet", "2bet", "3bet", "4bet", "5bet", "strategy_id=",
]

# DB path tokens that must not appear (no DB path is required or accessed).
FORBIDDEN_DB_PATH_TOKENS = ["lottery_v2.db", "/data/lottery", ".sqlite", ".db\""]

# Required declarations that must appear verbatim in the MD.
REQUIRED_MD_DECLARATIONS = [
    "design-only",
    "Strict outcome blindness was not achieved",
    "Mandatory governance exposed prior P271F outcomes",
    "numerical values are not reproduced",
    "Design choices are frozen by the externally supplied task contract",
    "Prior outcomes were not used to select endpoints",
    "blacklist fixtures were removed",
    "semantic/schema guards",
    "No baseline was executed",
    "No scorer or adapter execution occurred",
    "No database was accessed",
    "P271F is retrospective and exploratory",
    "Confirmatory claims require new prospective post-activation data",
    "Replay rows within one target draw are not independent",
    "Strategy-level comparison/ranking is excluded",
    "No p-value, CI, lift, effect value, ranking, or improvement claim was calculated",
    "No production or strategy promotion is authorized",
    "MANUAL_VERIFICATION_REQUIRED",
    "P270C remains unauthorized",
    "Temporal-window research and feature mining were not started",
]

REQUIRED_MD_SECTION_TITLES = [
    "Executive Summary",
    "Why P271F Cannot Be Treated As Untouched Confirmation",
    "Prior Outcome Exposure and Design Independence",
    "Retrospective Exploratory Population",
    "Prospective Confirmatory Population",
    "Draw-Cluster Statistical Unit",
    "Random/Null Ticket Generator",
    "Frozen Endpoints",
    "Effect Statistic",
    "Multiple-Testing Correction",
    "Minimum Evidence Gate",
    "Prospective Cutoff and Sample Gate",
    "Leakage and Integrity Gates",
    "Versioning and Amendment Policy",
    "Explicit Non-Actions",
    "Activation Requirements",
    "Final Classification",
]


@pytest.fixture(scope="module")
def artifact():
    with open(JSON_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def raw_json_text():
    with open(JSON_PATH, encoding="utf-8") as f:
        return f.read()


@pytest.fixture(scope="module")
def md_content():
    with open(MD_PATH, encoding="utf-8") as f:
        return f.read()


def _iter_float_leaves(obj):
    """Yield every float leaf value in a nested JSON structure (bools excluded)."""
    if isinstance(obj, dict):
        for v in obj.values():
            yield from _iter_float_leaves(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _iter_float_leaves(v)
    elif isinstance(obj, bool):
        return
    elif isinstance(obj, float):
        yield obj


def _iter_keys(obj):
    if isinstance(obj, dict):
        for key, value in obj.items():
            yield key
            yield from _iter_keys(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from _iter_keys(value)


# ── 1: Corrected JSON/MD paths are under outputs/research ─────────────────────

def test_01_paths_under_outputs_research():
    assert os.path.normpath(JSON_PATH).split(os.sep)[-3:-1] == ["outputs", "research"]
    assert os.path.normpath(MD_PATH).split(os.sep)[-3:-1] == ["outputs", "research"]
    assert os.path.isfile(JSON_PATH)
    assert os.path.isfile(MD_PATH)


# ── 2: No reports/research artifact is created ───────────────────────────────

def test_02_no_reports_research_artifact():
    assert not os.path.exists(REPORTS_JSON_PATH), "Forbidden reports/research JSON exists"
    assert not os.path.exists(REPORTS_MD_PATH), "Forbidden reports/research MD exists"
    # The whole reports/research/p271g_* family must be absent.
    reports_research = os.path.join(REPO_ROOT, "reports", "research")
    if os.path.isdir(reports_research):
        offenders = [n for n in os.listdir(reports_research) if n.startswith("p271g_")]
        assert not offenders, f"Forbidden reports/research p271g artifacts: {offenders}"


# ── 3: JSON and MD exist ─────────────────────────────────────────────────────

def test_03_json_and_md_exist():
    assert os.path.isfile(JSON_PATH)
    assert os.path.isfile(MD_PATH)


# ── 4: Design-only is true ───────────────────────────────────────────────────

def test_04_design_only_true(artifact):
    assert artifact["design_only"] is True


# ── 5: Prior exposure is disclosed truthfully ────────────────────────────────

def test_05_prior_exposure_disclosed(artifact):
    assert artifact["strict_outcome_blindness"] is False
    assert artifact["prior_outcome_exposure"] is True
    assert "mandatory_governance_files" in artifact["exposure_source"]
    assert artifact["historical_results_inspected"] is True


# ── 6: P271F outcome exposure is acknowledged ────────────────────────────────

def test_06_p271f_outcome_metrics_read_true(artifact):
    assert artifact["p271f_outcome_metrics_read"] is True


# ── 7: Outcome values read is true but not copied or used ────────────────────

def test_07_outcome_values_exposure_and_non_use(artifact):
    assert artifact["outcome_values_read"] is True
    assert artifact["outcome_values_copied_into_final_p271g_files"] is False
    assert artifact["outcome_values_used_for_endpoint_selection"] is False
    assert artifact["outcome_values_used_for_null_design"] is False
    assert artifact["outcome_values_used_for_threshold_selection"] is False
    assert artifact["outcome_values_used_for_multiple_testing_design"] is False
    assert artifact["outcome_values_used_for_sample_gate_selection"] is False
    assert artifact["design_contract_fixed_externally_by_task_prompt"] is True


# ── 8: DB access/write are false ─────────────────────────────────────────────

def test_08_db_access_and_write_false(artifact):
    assert artifact["db_access"] is False
    assert artifact["db_write"] is False


# ── 9: Scorer/adapter execution are false ────────────────────────────────────

def test_09_scorer_and_adapter_executed_false(artifact):
    assert artifact["scorer_executed"] is False
    assert artifact["adapter_executed"] is False


# ── 10: Baseline execution is false ──────────────────────────────────────────

def test_10_baseline_executed_false(artifact):
    assert artifact["baseline_executed"] is False


# ── 11: Evaluation rerun is false ────────────────────────────────────────────

def test_11_evaluation_rerun_false(artifact):
    assert artifact["evaluation_rerun"] is False


# ── 12: Retrospective and prospective populations are separate ───────────────

def test_12_populations_are_separate(artifact):
    retro = artifact["retrospective_population_contract"]
    pros = artifact["prospective_population_contract"]
    assert retro["population_id"] == "retrospective_exploratory"
    assert pros["population_id"] == "prospective_confirmatory"
    assert retro["population_id"] != pros["population_id"]
    assert retro["evidence_label"] == "exploratory"
    assert pros["evidence_label"] == "confirmatory"


# ── 13: P271F is not confirmatory ────────────────────────────────────────────

def test_13_p271f_not_confirmatory(artifact):
    retro = artifact["retrospective_population_contract"]
    assert retro["is_confirmatory"] is False
    assert retro["cannot_support_untouched_confirmatory_claims"] is True


# ── 14: Prospective cutoff is pending merge timestamp ────────────────────────

def test_14_prospective_cutoff_pending_merge_timestamp(artifact):
    cutoff = artifact["prospective_cutoff_contract"]
    assert cutoff["prospective_prediction_start_at"] == "PENDING_P271G_MERGE_TIMESTAMP"


# ── 15: No pre-merge cutoff is used ──────────────────────────────────────────

def test_15_no_pre_merge_cutoff(artifact):
    cutoff = artifact["prospective_cutoff_contract"]
    assert cutoff["historical_or_pre_merge_start_timestamp_prohibited"] is True
    start = cutoff["prospective_prediction_start_at"]
    # The start must be the pending marker, not a real (parseable) timestamp/date.
    assert start == "PENDING_P271G_MERGE_TIMESTAMP"
    assert not re.match(r"^\d{4}-\d{2}-\d{2}", start), "start_at must not be a real date"


# ── 16: Minimum 100 draws per lottery ────────────────────────────────────────

def test_16_minimum_100_draws_per_lottery(artifact):
    assert artifact["prospective_cutoff_contract"]["minimum_draws_per_lottery"] == 100
    gate = artifact["minimum_evidence_gate"]["requires_all"]
    assert gate["min_completed_target_draws"] == 100


# ── 17: Minimum 500 tickets per lottery ──────────────────────────────────────

def test_17_minimum_500_tickets_per_lottery(artifact):
    assert artifact["prospective_cutoff_contract"]["minimum_tickets_per_lottery"] == 500
    gate = artifact["minimum_evidence_gate"]["requires_all"]
    assert gate["min_eligible_prediction_tickets"] == 500


# ── 18: One final confirmatory test only ─────────────────────────────────────

def test_18_one_final_confirmatory_test_only(artifact):
    cutoff = artifact["prospective_cutoff_contract"]
    assert cutoff["final_confirmatory_analysis_runs_once"] is True
    assert cutoff["final_confirmatory_analysis_run_count"] == 1


# ── 19: No repeated-peeking GO decision ──────────────────────────────────────

def test_19_no_repeated_peeking_go_decision(artifact):
    cutoff = artifact["prospective_cutoff_contract"]
    assert cutoff["no_repeated_peeking_go_decision"] is True
    assert cutoff["interim_descriptive_monitoring_may_contain_no_p_values_or_go_decision"] is True


# ── 20: Primary cluster unit is target_draw ──────────────────────────────────

def test_20_primary_cluster_unit_is_target_draw(artifact):
    su = artifact["statistical_unit_contract"]
    assert su["primary_cluster_unit"] == "target_draw"


# ── 21: Rows within a draw are dependent ─────────────────────────────────────

def test_21_rows_within_draw_dependent(artifact):
    su = artifact["statistical_unit_contract"]
    assert su["rows_within_draw_independent"] is False
    assert su["reject_replay_row_independence"] is True
    assert su["naive_row_level_binomial_p_value_prohibited"] is True


# ── 22: Primary endpoint is exactly any-prize-aware-win draw-cluster mean ─────

def test_22_primary_endpoint_exact(artifact):
    ep = artifact["primary_endpoint_contract"]
    assert ep["indicator"] == "any_prize_aware_win"
    assert ep["aggregation"] == "draw_cluster_mean"
    assert ep["family_size"] == 3


# ── 23: Secondary endpoint is exactly M3+ draw-cluster mean ───────────────────

def test_23_secondary_endpoint_exact(artifact):
    ep = artifact["secondary_endpoint_contract"]
    assert ep["indicator"] == "m3_plus"
    assert ep["aggregation"] == "draw_cluster_mean"
    assert ep["family_size"] == 3


# ── 24: Tier distributions are descriptive only ──────────────────────────────

def test_24_tier_distributions_descriptive_only(artifact):
    d = artifact["descriptive_only_endpoint_contract"]
    assert "prize_tier_distribution" in d["endpoints"]
    assert "tier_class_distribution" in d["endpoints"]
    assert d["receive_no_confirmatory_p_value"] is True
    assert d["cannot_independently_trigger_go"] is True
    assert d["cannot_be_promoted_after_results_viewed"] is True


# ── 25: Null preserves ticket count by draw ──────────────────────────────────

def test_25_null_preserves_ticket_count_by_draw(artifact):
    n = artifact["null_ticket_generator_contract"]
    assert n["preserve_ticket_count_per_target_draw"] is True
    assert n["preserve_total_row_ticket_count"] is True


# ── 26: Null is uniform over valid ticket space ──────────────────────────────

def test_26_null_uniform_over_valid_space(artifact):
    n = artifact["null_ticket_generator_contract"]
    assert n["uniform_over_valid_ticket_space"] is True
    assert n["do_not_preserve_model_selected_numbers"] is True
    assert n["do_not_use_outcomes"] is True


# ── 27: Seeds exclude outcomes and strategy IDs ──────────────────────────────

def test_27_seeds_exclude_outcomes_and_strategy_ids(artifact):
    s = artifact["deterministic_seed_contract"]
    assert s["seeds_exclude_outcomes"] is True
    assert s["seeds_exclude_strategy_ids"] is True
    excluded = s["excluded_seed_inputs"]
    assert "strategy_id" in excluded
    assert "winning_numbers" in excluded
    assert "p271f_outcomes" in excluded
    assert s["seed_derivation_inputs_ordered"] == [
        "preregistration_version", "lottery_type", "replication_index"
    ]


# ── 28: Repetitions equal 100,000 ────────────────────────────────────────────

def test_28_repetitions_100000(artifact):
    assert artifact["simulation_contract"]["primary_repetitions"] == 100000


# ── 29: Minimum valid repetitions equal 99,900 ───────────────────────────────

def test_29_minimum_valid_repetitions_99900(artifact):
    assert artifact["simulation_contract"]["minimum_valid_repetitions"] == 99900


# ── 30: No adaptive repetition count ─────────────────────────────────────────

def test_30_no_adaptive_repetitions(artifact):
    sim = artifact["simulation_contract"]
    assert sim["adaptive_repetitions"] is False
    assert sim["early_stopping_prohibited"] is True
    assert sim["failed_repetitions_selective_replacement_prohibited"] is True


# ── 31: POWER null includes second-zone sampling ─────────────────────────────

def test_31_power_null_includes_second_zone(artifact):
    p = artifact["lottery_rule_contracts"]["POWER_LOTTO"]
    assert p["has_second_zone"] is True
    assert p["null_samples_second_zone"] is True
    assert p["second_zone_range"] == [1, 8]


# ── 32: BIG has no predicted special field ───────────────────────────────────

def test_32_big_no_predicted_special_field(artifact):
    b = artifact["lottery_rule_contracts"]["BIG_LOTTO"]
    assert b["has_predicted_special_field"] is False
    assert b["main_number_range"] == [1, 49]


# ── 33: DAILY_539 has no auxiliary field ─────────────────────────────────────

def test_33_daily_539_no_auxiliary_field(artifact):
    d = artifact["lottery_rule_contracts"]["DAILY_539"]
    assert d["has_auxiliary_field"] is False
    assert d["main_number_range"] == [1, 39]


# ── 34: Primary family has exactly three tests ───────────────────────────────

def test_34_primary_family_three_tests(artifact):
    pf = artifact["multiple_testing_contract"]["primary_family"]
    assert pf["n_tests"] == 3
    assert len(pf["lotteries"]) == 3


# ── 35: Primary correction is Holm at alpha 0.05 ─────────────────────────────

def test_35_primary_correction_holm_alpha_005(artifact):
    pf = artifact["multiple_testing_contract"]["primary_family"]
    assert pf["correction"] == "Holm"
    assert pf["alpha"] == 0.05


# ── 36: Secondary family is separate ─────────────────────────────────────────

def test_36_secondary_family_separate(artifact):
    sf = artifact["multiple_testing_contract"]["secondary_family"]
    assert sf["separate_from_primary"] is True
    assert sf["n_tests"] == 3
    assert sf["correction"] == "Holm"
    assert sf["alpha"] == 0.05


# ── 37: Secondary cannot override primary failure ────────────────────────────

def test_37_secondary_cannot_override_primary(artifact):
    sf = artifact["multiple_testing_contract"]["secondary_family"]
    assert sf["cannot_override_primary_failure"] is True
    assert artifact["secondary_endpoint_contract"]["cannot_override_primary_failure"] is True


# ── 38: Evidence gate requires adjusted p-value ──────────────────────────────

def test_38_gate_requires_adjusted_p_value(artifact):
    gate = artifact["minimum_evidence_gate"]["requires_all"]
    assert gate["primary_holm_adjusted_p_value_lt_0_05"] is True


# ── 39: Evidence gate requires positive effect ───────────────────────────────

def test_39_gate_requires_positive_effect(artifact):
    gate = artifact["minimum_evidence_gate"]["requires_all"]
    assert gate["observed_minus_null_effect_gt_0"] is True


# ── 40: Evidence gate requires CI lower bound > 0 ────────────────────────────

def test_40_gate_requires_ci_lower_bound_gt_0(artifact):
    gate = artifact["minimum_evidence_gate"]["requires_all"]
    assert gate["draw_cluster_bootstrap_95_ci_lower_bound_gt_0"] is True


# ── 41: Evidence gate requires minimum sample ────────────────────────────────

def test_41_gate_requires_minimum_sample(artifact):
    gate = artifact["minimum_evidence_gate"]["requires_all"]
    assert gate["min_completed_target_draws"] == 100
    assert gate["min_eligible_prediction_tickets"] == 500


# ── 42: Evidence gate requires zero causality violations ─────────────────────

def test_42_gate_requires_zero_causality_violations(artifact):
    gate = artifact["minimum_evidence_gate"]["requires_all"]
    assert gate["zero_causality_or_timestamp_violations"] is True


# ── 43: No strategy promotion is authorized ──────────────────────────────────

def test_43_no_strategy_promotion_authorized(artifact):
    assert artifact["no_strategy_promotion_authorized"] is True
    g = artifact["minimum_evidence_gate"]
    assert g["does_not_authorize_production_deployment_or_strategy_promotion"] is True


# ── 44: Leakage gates fail closed ────────────────────────────────────────────

def test_44_leakage_gates_fail_closed(artifact):
    assert artifact["leakage_integrity_gates"]["fail_closed"] is True


# ── 45: Missing timestamps are rejected ──────────────────────────────────────

def test_45_missing_timestamps_rejected(artifact):
    lg = artifact["leakage_integrity_gates"]
    assert lg["missing_timestamps_rejected"] is True
    assert "timestamps_missing_or_ambiguous" in lg["fail_closed_conditions"]


# ── 46: Post-draw amendment is rejected ──────────────────────────────────────

def test_46_post_draw_amendment_rejected(artifact):
    lg = artifact["leakage_integrity_gates"]
    assert lg["post_draw_amendment_rejected"] is True
    assert "prediction_amended_after_cutoff" in lg["fail_closed_conditions"]
    assert "source_prediction_changes_after_draw_close" in lg["fail_closed_conditions"]


# ── 47: POWER missing second zone is rejected ────────────────────────────────

def test_47_power_missing_second_zone_rejected(artifact):
    lg = artifact["leakage_integrity_gates"]
    assert lg["power_missing_second_zone_rejected"] is True
    assert "power_predicted_second_zone_missing" in lg["fail_closed_conditions"]


# ── 48: Amendment requires a new version ─────────────────────────────────────

def test_48_amendment_requires_new_version(artifact):
    assert artifact["amendment_policy"]["amendment_requires_new_version"] is True


# ── 49: Prior evidence cannot be silently reinterpreted ──────────────────────

def test_49_prior_evidence_not_silently_reinterpreted(artifact):
    ap = artifact["amendment_policy"]
    assert ap["cannot_silently_reinterpret_prior_evidence"] is True
    assert ap["cannot_modify_treatment_of_prior_confirmatory_data_without_explicit_invalidation_or_versioning"] is True


# ── 50: No calculated p-value/CI/lift/effect value exists ────────────────────

def test_50_no_calculated_values_exist(artifact):
    assert artifact["p_value_calculated"] is False
    assert artifact["confidence_interval_calculated"] is False
    assert artifact["lift_calculated"] is False
    assert artifact["effect_value_calculated"] is False
    assert artifact["effect_statistic_contract"]["values_calculated"] is False
    assert artifact["simulation_contract"]["simulations_executed"] is False
    assert artifact["null_ticket_generator_contract"]["generator_executed"] is False
    # The ONLY non-integer numeric in the entire artifact is the design alpha (0.05).
    # No computed statistic value (p-value, CI bound, lift, effect) is embedded.
    floats = set(_iter_float_leaves(artifact))
    assert floats == {0.05}, f"Unexpected float values present (possible computed result): {floats}"


# ── 51: No P271F result-schema keys are embedded ─────────────────────────────

def test_51_no_result_schema_keys_embedded(artifact, md_content):
    embedded_keys = set(_iter_keys(artifact))
    assert embedded_keys.isdisjoint(FORBIDDEN_RESULT_SCHEMA_KEYS)
    md_lower = md_content.lower()
    for key in FORBIDDEN_RESULT_SCHEMA_KEYS:
        assert key.lower() not in md_lower


def test_51b_contamination_recovery_disclosed(artifact):
    recovery = artifact["contamination_recovery"]
    assert recovery["preexisting_test_source_contained_outcome_value_blacklist"] is True
    assert recovery["outcome_value_blacklist_removed"] is True
    assert recovery["copied_outcome_values_present_in_final_test_source"] is False
    assert recovery["copied_outcome_values_present_in_final_json"] is False
    assert recovery["copied_outcome_values_present_in_final_md"] is False
    assert recovery["final_p271g_files_contain_p271f_outcome_values"] is False
    assert recovery["design_rule_changed_due_to_contamination"] is False


def test_51c_no_p271f_result_artifact_ingestion_or_execution(artifact):
    with open(__file__, encoding="utf-8") as f:
        test_source = f.read().lower()
    forbidden_source_patterns = [
        r"from\s+\S*p271f\S*\s+import",
        r"import\s+\S*p271f",
        r"open\s*\([^)]*p271f",
        r"json\.load\s*\([^)]*p271f",
        r"subprocess\.[a-z_]+\s*\([^)]*p271f",
    ]
    for pattern in forbidden_source_patterns:
        assert not re.search(pattern, test_source)
    integrity = artifact["prior_outcome_exposure_integrity"]
    assert integrity["p271f_result_artifacts_ingested_by_p271g"] is False
    assert integrity["outcome_result_fields_ingested"] == []


def test_51d_no_numerical_retrospective_result_reporting(md_content):
    forbidden_report_labels = [
        "p271f result table",
        "observed historical rate table",
        "prize-tier result table",
        "m3+ result table",
        "overlap result table",
    ]
    md_lower = md_content.lower()
    for label in forbidden_report_labels:
        assert label not in md_lower


# ── 52: No strategy identifiers are present ──────────────────────────────────

def test_52_no_strategy_identifiers(raw_json_text, md_content):
    blob = (raw_json_text + "\n" + md_content).lower()
    for frag in FORBIDDEN_STRATEGY_ID_FRAGMENTS:
        assert frag.lower() not in blob, f"Forbidden strategy identifier fragment present: '{frag}'"


# ── 53: No DB path is required or accessed ───────────────────────────────────

def test_53_no_db_path(artifact, raw_json_text, md_content):
    blob = raw_json_text + "\n" + md_content
    for tok in FORBIDDEN_DB_PATH_TOKENS:
        assert tok not in blob, f"Forbidden DB path token present: '{tok}'"
    assert artifact["db_access"] is False
    assert artifact["db_write"] is False


# ── 54: MD contains all required declarations ────────────────────────────────

def test_54_md_required_declarations(md_content):
    for decl in REQUIRED_MD_DECLARATIONS:
        assert decl.lower() in md_content.lower(), f"MD missing required declaration: '{decl}'"


# ── 55: Final classification is allowed ──────────────────────────────────────

def test_55_final_classification_allowed(artifact):
    assert artifact["final_classification"] in ALLOWED_CLASSIFICATIONS


# ── 56: P270C is false ───────────────────────────────────────────────────────

def test_56_p270c_allowed_false(artifact):
    assert artifact["p270c_allowed"] is False


# ── 57: Temporal-window and feature-mining flags are false ───────────────────

def test_57_temporal_and_feature_flags_false(artifact):
    assert artifact["temporal_window_research_started"] is False
    assert artifact["feature_mining_started"] is False


# ── 58: Production integration and improvement claims are false ──────────────

def test_58_production_and_improvement_false(artifact):
    assert artifact["production_integration_added"] is False
    assert artifact["hit_rate_improvement_claimed"] is False


# ── Additional structural / governance tests ─────────────────────────────────

def test_top_level_required_fields_present(artifact):
    required = [
        "task_id", "generated_at", "repo_head_before_task", "branch", "mode",
        "design_only", "preregistration_version",
        "strict_outcome_blindness", "prior_outcome_exposure", "exposure_source",
        "historical_results_inspected", "p271f_outcome_metrics_read",
        "outcome_values_copied_into_final_p271g_files",
        "outcome_values_used_for_endpoint_selection",
        "outcome_values_used_for_null_design",
        "outcome_values_used_for_threshold_selection",
        "outcome_values_used_for_multiple_testing_design",
        "outcome_values_used_for_sample_gate_selection",
        "design_contract_fixed_externally_by_task_prompt",
        "retrospective_confirmatory_claim_allowed",
        "prospective_confirmatory_claim_requires_post_merge_data",
        "contamination_recovery",
        "retrospective_population_contract", "prospective_population_contract",
        "statistical_unit_contract", "null_ticket_generator_contract",
        "deterministic_seed_contract", "simulation_contract",
        "primary_endpoint_contract", "secondary_endpoint_contract",
        "descriptive_only_endpoint_contract", "effect_statistic_contract",
        "multiple_testing_contract", "minimum_evidence_gate",
        "prospective_cutoff_contract", "leakage_integrity_gates",
        "amendment_policy", "lottery_rule_contracts",
        "power_eligible_subset_limitation", "source_verification_status",
        "baseline_executed", "scorer_executed", "adapter_executed",
        "evaluation_rerun", "db_access", "db_write", "outcome_values_read",
        "p_value_calculated", "confidence_interval_calculated", "lift_calculated",
        "effect_value_calculated",
        "strategy_comparison_run", "strategy_ranking_run",
        "temporal_window_research_started", "feature_mining_started",
        "production_integration_added", "hit_rate_improvement_claimed",
        "p270c_allowed", "next_activation_requirement", "tests_result",
        "modified_files", "final_classification", "limitations",
    ]
    for field in required:
        assert field in artifact, f"Missing required top-level field: '{field}'"


def test_task_id_and_mode(artifact):
    assert artifact["task_id"] == "P271G"
    assert artifact["mode"] == "prize_aware_null_and_prospective_preregistration"


def test_preregistration_version_frozen(artifact):
    assert artifact["preregistration_version"] == "p271g_v1"
    vc = artifact["versioning_contract"]
    assert vc["preregistration_version"] == "p271g_v1"
    assert vc["metric_contract_version"] == "p271g_metrics_v1"
    assert vc["null_generator_version"] == "p271g_null_v1"
    assert vc["clustering_contract_version"] == "p271g_cluster_v1"
    assert vc["prospective_protocol_version"] == "p271g_prospective_v1"


def test_source_verification_status(artifact):
    assert artifact["source_verification_status"] == "MANUAL_VERIFICATION_REQUIRED"


def test_strategy_comparison_and_ranking_false(artifact):
    assert artifact["strategy_comparison_run"] is False
    assert artifact["strategy_ranking_run"] is False


def test_repo_head_before_task_recorded(artifact):
    assert artifact["repo_head_before_task"] == "6ce381e73fadb828cf0d4a367922eb400f6ea4a9"


def test_modified_files_are_exactly_whitelist(artifact):
    expected = {
        "outputs/research/p271g_prize_aware_null_prospective_preregistration_20260612.json",
        "outputs/research/p271g_prize_aware_null_prospective_preregistration_20260612.md",
        "tests/test_p271g_prize_aware_null_prospective_preregistration.py",
        "00-Plan/roadmap/active_task.md",
        "00-Plan/roadmap/agent_bootstrap/CURRENT_STATE.md",
    }
    assert set(artifact["modified_files"]) == expected


def test_power_eligible_subset_limitation_documented(artifact):
    lim = artifact["power_eligible_subset_limitation"]
    assert lim["retrospective_eligibility_is_structural_scope_not_outcome"] is True
    counts = lim["structural_scope_counts"]
    # Structural scope counts are allowed; outcome rates are not.
    assert counts["exclusion_reason"] == "MISSING_PREDICTED_SECOND_ZONE"


def test_md_section_titles_present(md_content):
    for title in REQUIRED_MD_SECTION_TITLES:
        assert title.lower() in md_content.lower(), f"MD missing required section: '{title}'"


def test_next_activation_requires_separate_authorization(artifact):
    nar = artifact["next_activation_requirement"]
    assert "prospective_activation" in nar
    assert "after p271g merges" in nar["prospective_activation"].lower()
    assert nar["p270c"] == "remains unauthorized"


def test_prospective_population_is_only_confirmatory(artifact):
    pros = artifact["prospective_population_contract"]
    assert pros["is_confirmatory"] is True
    assert pros["is_only_confirmatory_population"] is True
    assert pros["no_retrospective_row_may_migrate_into_prospective_population"] is True


def test_retrospective_confirmation_forbidden_and_prospective_required(artifact):
    assert artifact["retrospective_confirmatory_claim_allowed"] is False
    assert artifact["prospective_confirmatory_claim_requires_post_merge_data"] is True


def test_no_executable_baseline_or_statistical_logic(artifact):
    assert artifact["baseline_executed"] is False
    assert artifact["simulation_contract"]["simulations_executed"] is False
    assert artifact["null_ticket_generator_contract"]["generator_executed"] is False
    assert artifact["statistical_unit_contract"]["primary_method_executed"] is False
    assert artifact["statistical_unit_contract"]["sensitivity_method_executed"] is False
    assert artifact["strategy_comparison_run"] is False
    assert artifact["strategy_ranking_run"] is False
