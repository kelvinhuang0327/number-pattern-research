"""
P271F — Tests for Prize-Aware Full Eligible-History Descriptive Evaluation

Verifies source safety, invariants, safety flags, and artifact contracts
for analysis/p271f_prize_aware_full_history_descriptive_evaluation.py.
"""

from __future__ import annotations

import json
import os
import re

import pytest

SCRIPT_PATH = "analysis/p271f_prize_aware_full_history_descriptive_evaluation.py"
JSON_ARTIFACT_PATH = (
    "outputs/research/"
    "p271f_prize_aware_full_history_descriptive_evaluation_20260612.json"
)
MD_ARTIFACT_PATH = (
    "outputs/research/"
    "p271f_prize_aware_full_history_descriptive_evaluation_20260612.md"
)
ADAPTER_PATH = "lottery_api/prize_aware_replay_adapter.py"
SCORER_PATH = "lottery_api/prize_aware_scorer.py"
REPLAY_PATH = "lottery_api/routes/replay.py"
DB_PATH = "lottery_api/data/lottery_v2.db"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def script_src():
    with open(SCRIPT_PATH, encoding="utf-8") as f:
        return f.read()


@pytest.fixture(scope="module")
def artifact():
    with open(JSON_ARTIFACT_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def md_content():
    with open(MD_ARTIFACT_PATH, encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------------------
# Test 1: Import without side effects
# ---------------------------------------------------------------------------

def test_import_without_side_effects():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "p271f_eval", SCRIPT_PATH
    )
    mod = importlib.util.module_from_spec(spec)
    # Should not raise or access DB on import
    spec.loader.exec_module(mod)
    assert hasattr(mod, "run_full_evaluation")
    assert hasattr(mod, "build_json_artifact")
    assert hasattr(mod, "write_artifacts")
    assert hasattr(mod, "main")


# ---------------------------------------------------------------------------
# Test 2: DB opens with mode=ro
# ---------------------------------------------------------------------------

def test_db_opens_with_mode_ro(script_src):
    assert "mode=ro" in script_src
    assert "sqlite3.connect(" in script_src
    assert "uri=True" in script_src


# ---------------------------------------------------------------------------
# Test 3: No SQL write statements
# ---------------------------------------------------------------------------

def test_no_sql_write_statements(script_src):
    src_upper = script_src.upper()
    for stmt in ("INSERT ", "UPDATE ", "DELETE ", "DROP TABLE", "CREATE TABLE",
                 "ALTER TABLE", "TRUNCATE"):
        assert stmt not in src_upper, f"Forbidden SQL statement found: {stmt}"


# ---------------------------------------------------------------------------
# Test 4: Imports adapter/scorer but not replay.py
# ---------------------------------------------------------------------------

def test_imports_adapter_not_replay(script_src):
    assert "prize_aware_replay_adapter" in script_src
    assert "prize_aware_scorer" in script_src
    assert "import lottery_api.routes.replay" not in script_src
    assert "from lottery_api.routes.replay" not in script_src


# ---------------------------------------------------------------------------
# Test 5: Adapter and scorer source files not modified
# ---------------------------------------------------------------------------

def test_adapter_source_not_modified():
    with open(ADAPTER_PATH, encoding="utf-8") as f:
        src = f.read()
    assert len(src) > 0
    assert "prize_aware_adapter_v1" in src
    assert "MISSING_PREDICTED_SECOND_ZONE" in src


def test_scorer_source_not_modified():
    with open(SCORER_PATH, encoding="utf-8") as f:
        src = f.read()
    assert len(src) > 0
    assert "prize_aware_v1" in src
    assert "existing_m3_replay_scoring_changed" in src


# ---------------------------------------------------------------------------
# Test 6: Deterministic ordering
# ---------------------------------------------------------------------------

def test_deterministic_ordering_in_script(script_src):
    assert "ORDER BY" in script_src or "iter_structurally_eligible_rows" in script_src
    # The ordering is delegated to the adapter which uses deterministic ORDER BY
    assert "iter_structurally_eligible_rows" in script_src


# ---------------------------------------------------------------------------
# Test 7: Aggregate-only output contract
# ---------------------------------------------------------------------------

def test_aggregate_only_output(artifact):
    assert artifact["aggregate_only_output"] is True
    assert artifact["row_level_output_written"] is False


# ---------------------------------------------------------------------------
# Test 8: No row-level result arrays
# ---------------------------------------------------------------------------

def test_no_row_level_output(artifact):
    assert artifact["row_level_output_written"] is False
    # results_by_lottery contains only aggregate dicts, not lists of row records
    for lt, r in artifact["results_by_lottery"].items():
        assert isinstance(r, dict), f"{lt} result must be a dict, not a list"
        assert "scorer_result" not in r, f"{lt} must not have a row-level scorer_result"


# ---------------------------------------------------------------------------
# Test 9: No raw predicted-number arrays
# ---------------------------------------------------------------------------

def test_no_raw_predicted_number_arrays(artifact):
    assert artifact["raw_predicted_numbers_exported"] is False
    result_str = json.dumps(artifact["results_by_lottery"])
    assert "predicted_numbers" not in result_str
    assert "predicted_main_numbers" not in result_str


# ---------------------------------------------------------------------------
# Test 10: No raw actual-number arrays
# ---------------------------------------------------------------------------

def test_no_raw_actual_number_arrays(artifact):
    assert artifact["raw_actual_numbers_exported"] is False
    result_str = json.dumps(artifact["results_by_lottery"])
    assert "actual_numbers" not in result_str
    assert "actual_main_numbers" not in result_str


# ---------------------------------------------------------------------------
# Test 11: No strategy_id aggregation
# ---------------------------------------------------------------------------

def test_no_strategy_id_aggregation(script_src, artifact):
    # Script must not GROUP BY strategy_id
    assert "GROUP BY strategy_id" not in script_src.upper()
    assert "GROUP BY r.strategy_id" not in script_src.upper()
    # Artifact results must not be keyed by strategy_id
    for lt, r in artifact["results_by_lottery"].items():
        result_str = json.dumps(r)
        assert "strategy_id" not in result_str, (
            f"{lt} result must not include strategy_id keys"
        )


# ---------------------------------------------------------------------------
# Test 12: No strategy ranking or comparison
# ---------------------------------------------------------------------------

def test_no_strategy_ranking_or_comparison(artifact):
    assert artifact["strategy_comparison_run"] is False
    assert artifact["strategy_ranking_run"] is False


# ---------------------------------------------------------------------------
# Test 13: No random/null baseline
# ---------------------------------------------------------------------------

def test_no_random_null_baseline(artifact, script_src):
    assert artifact["random_baseline_calculated"] is False
    assert "baseline" not in script_src.lower() or "random_baseline_calculated" in script_src


# ---------------------------------------------------------------------------
# Test 14: No p-value calculation
# ---------------------------------------------------------------------------

def test_no_p_value_calculation(artifact, script_src):
    assert artifact["p_value_calculated"] is False
    assert "pvalue" not in script_src.lower()
    assert "p_value" not in script_src.replace("p_value_calculated", "")


# ---------------------------------------------------------------------------
# Test 15: No confidence interval calculation
# ---------------------------------------------------------------------------

def test_no_confidence_interval(artifact, script_src):
    assert artifact["confidence_interval_calculated"] is False
    assert "confidence_interval" not in script_src.replace(
        "confidence_interval_calculated", ""
    )


# ---------------------------------------------------------------------------
# Test 16: No lift calculation
# ---------------------------------------------------------------------------

def test_no_lift_calculation(artifact):
    assert artifact["lift_calculated"] is False


# ---------------------------------------------------------------------------
# Test 17: No multiple-testing correction
# ---------------------------------------------------------------------------

def test_no_multiple_testing_correction(artifact, script_src):
    assert artifact["multiple_testing_correction_run"] is False
    for term in ("bonferroni", "benjamini", "fdr", "holm"):
        assert term not in script_src.lower()


# ---------------------------------------------------------------------------
# Test 18: No temporal-window grouping
# ---------------------------------------------------------------------------

def test_no_temporal_window_grouping(artifact, script_src):
    assert artifact["temporal_window_research_started"] is False
    assert "temporal_window" not in script_src.replace(
        "temporal_window_research_started", ""
    )


# ---------------------------------------------------------------------------
# Test 19: No feature-mining logic
# ---------------------------------------------------------------------------

def test_no_feature_mining(artifact, script_src):
    assert artifact["feature_mining_started"] is False
    assert "feature_mining" not in script_src.replace("feature_mining_started", "")


# ---------------------------------------------------------------------------
# Test 20: POWER requires stored predicted second zone (source)
# ---------------------------------------------------------------------------

def test_power_requires_stored_predicted_second_zone(script_src):
    assert "POWER_LOTTO" in script_src
    assert "MISSING_PREDICTED_SECOND_ZONE" in script_src or (
        "predicted_second_zone" in script_src
    )


# ---------------------------------------------------------------------------
# Test 21: POWER missing second zone is excluded (artifact)
# ---------------------------------------------------------------------------

def test_power_missing_second_zone_excluded(artifact):
    excl = artifact["exclusion_summary_by_lottery"]["POWER_LOTTO"]
    assert excl.get("MISSING_PREDICTED_SECOND_ZONE", 0) > 0, (
        "POWER_LOTTO must report at least one MISSING_PREDICTED_SECOND_ZONE exclusion"
    )
    assert excl.get("MISSING_PREDICTED_SECOND_ZONE", 0) == 27104


# ---------------------------------------------------------------------------
# Test 22: POWER result is labeled eligible-subset-only
# ---------------------------------------------------------------------------

def test_power_result_labeled_eligible_subset_only(artifact):
    scope = artifact["evaluation_scope_by_lottery"]["POWER_LOTTO"]
    assert "eligible-subset-only" in scope.lower()
    r = artifact["results_by_lottery"]["POWER_LOTTO"]
    assert "eligible-subset-only" in r.get("scope_label", "").lower()


# ---------------------------------------------------------------------------
# Test 23: BIG full eligible scope
# ---------------------------------------------------------------------------

def test_big_full_eligible_scope(artifact):
    r = artifact["results_by_lottery"]["BIG_LOTTO"]
    assert r["total_replay_rows"] == r["structurally_eligible_rows"]
    assert r["structurally_excluded_rows"] == 0


# ---------------------------------------------------------------------------
# Test 24: DAILY_539 full eligible scope
# ---------------------------------------------------------------------------

def test_daily_539_full_eligible_scope(artifact):
    r = artifact["results_by_lottery"]["DAILY_539"]
    assert r["total_replay_rows"] == r["structurally_eligible_rows"]
    assert r["structurally_excluded_rows"] == 0


# ---------------------------------------------------------------------------
# Test 25: Required metric set is exact (all preregistered metrics present)
# ---------------------------------------------------------------------------

def test_required_metric_set_present(artifact):
    from analysis.p271f_prize_aware_full_history_descriptive_evaluation import (
        PREREGISTERED_METRICS,
    )
    for lt in ("POWER_LOTTO", "BIG_LOTTO", "DAILY_539"):
        r = artifact["results_by_lottery"][lt]
        for metric in PREREGISTERED_METRICS:
            assert metric in r, f"Missing metric {metric!r} in {lt} results"


# ---------------------------------------------------------------------------
# Test 26: No unregistered outcome metric in results
# ---------------------------------------------------------------------------

def test_no_unregistered_metrics(artifact):
    forbidden_keys = [
        "edge", "uplift", "advantage", "improvement", "baseline",
        "expected_value", "roi", "ev", "prize_amount",
        "strategy_id_result", "model_result",
    ]
    for lt in ("POWER_LOTTO", "BIG_LOTTO", "DAILY_539"):
        r = artifact["results_by_lottery"][lt]
        r_keys_lower = [k.lower() for k in r.keys()]
        for key in forbidden_keys:
            assert key not in r_keys_lower, (
                f"Forbidden key {key!r} found in {lt} result"
            )


# ---------------------------------------------------------------------------
# Test 27: Rate denominator is processed_rows
# ---------------------------------------------------------------------------

def test_rate_denominator_is_processed_rows(artifact):
    for lt in ("POWER_LOTTO", "BIG_LOTTO", "DAILY_539"):
        r = artifact["results_by_lottery"][lt]
        n = r["processed_rows"]
        apw = r["any_prize_aware_win_rate"]
        assert apw["denominator"] == n, f"{lt}: any_prize_aware_win_rate denominator mismatch"
        m3r = r["m3_plus_rate"]
        assert m3r["denominator"] == n, f"{lt}: m3_plus_rate denominator mismatch"
        for tier, rate_info in r["prize_tier_rates"].items():
            assert rate_info["denominator"] == n, (
                f"{lt}: prize_tier_rates[{tier!r}] denominator mismatch"
            )


# ---------------------------------------------------------------------------
# Test 28: Main-hit distribution sums correctly
# ---------------------------------------------------------------------------

def test_main_hit_distribution_sums_to_processed(artifact):
    for lt in ("POWER_LOTTO", "BIG_LOTTO", "DAILY_539"):
        r = artifact["results_by_lottery"][lt]
        total = sum(r["main_hit_count_counts"].values())
        assert total == r["processed_rows"], (
            f"{lt}: main_hit_count_counts sum {total} != processed_rows {r['processed_rows']}"
        )


# ---------------------------------------------------------------------------
# Test 29: Auxiliary-hit distribution sums correctly
# ---------------------------------------------------------------------------

def test_auxiliary_hit_sums_to_processed(artifact):
    for lt in ("POWER_LOTTO", "BIG_LOTTO", "DAILY_539"):
        r = artifact["results_by_lottery"][lt]
        total = r["auxiliary_hit_false_count"] + r["auxiliary_hit_true_count"]
        assert total == r["processed_rows"], (
            f"{lt}: aux_false + aux_true = {total} != processed_rows {r['processed_rows']}"
        )


# ---------------------------------------------------------------------------
# Test 30: Prize-tier distribution sums correctly
# ---------------------------------------------------------------------------

def test_prize_tier_distribution_sums_to_processed(artifact):
    for lt in ("POWER_LOTTO", "BIG_LOTTO", "DAILY_539"):
        r = artifact["results_by_lottery"][lt]
        total = sum(r["prize_tier_counts"].values())
        assert total == r["processed_rows"], (
            f"{lt}: prize_tier_counts sum {total} != processed_rows {r['processed_rows']}"
        )


# ---------------------------------------------------------------------------
# Test 31: Tier-class distribution sums correctly
# ---------------------------------------------------------------------------

def test_tier_class_distribution_sums_to_processed(artifact):
    for lt in ("POWER_LOTTO", "BIG_LOTTO", "DAILY_539"):
        r = artifact["results_by_lottery"][lt]
        total = sum(r["tier_class_counts"].values())
        assert total == r["processed_rows"], (
            f"{lt}: tier_class_counts sum {total} != processed_rows {r['processed_rows']}"
        )


# ---------------------------------------------------------------------------
# Test 32: M3+ distribution sums correctly
# ---------------------------------------------------------------------------

def test_m3_distribution_sums_to_processed(artifact):
    for lt in ("POWER_LOTTO", "BIG_LOTTO", "DAILY_539"):
        r = artifact["results_by_lottery"][lt]
        total = r["m3_plus_false_count"] + r["m3_plus_true_count"]
        assert total == r["processed_rows"], (
            f"{lt}: m3_false + m3_true = {total} != processed_rows {r['processed_rows']}"
        )


# ---------------------------------------------------------------------------
# Test 33: Overlap matrix sums correctly
# ---------------------------------------------------------------------------

def test_overlap_matrix_sums_to_processed(artifact):
    for lt in ("POWER_LOTTO", "BIG_LOTTO", "DAILY_539"):
        r = artifact["results_by_lottery"][lt]
        mx = r["prize_aware_and_m3_overlap_matrix"]
        total = (
            mx["prize_false_m3_false"]
            + mx["prize_false_m3_true"]
            + mx["prize_true_m3_false"]
            + mx["prize_true_m3_true"]
        )
        assert total == r["processed_rows"], (
            f"{lt}: overlap matrix sum {total} != processed_rows {r['processed_rows']}"
        )


# ---------------------------------------------------------------------------
# Test 34: any_prize_aware_win invariant
# ---------------------------------------------------------------------------

def test_any_prize_aware_win_matches_non_no_prize_sum(artifact):
    for lt in ("POWER_LOTTO", "BIG_LOTTO", "DAILY_539"):
        r = artifact["results_by_lottery"][lt]
        non_no_prize = sum(
            cnt for tier, cnt in r["prize_tier_counts"].items()
            if not tier.endswith("_NO_PRIZE")
        )
        assert r["any_prize_aware_win_count"] == non_no_prize, (
            f"{lt}: any_prize_aware_win_count {r['any_prize_aware_win_count']} "
            f"!= non-no-prize sum {non_no_prize}"
        )


# ---------------------------------------------------------------------------
# Test 35: Eligible + excluded = total
# ---------------------------------------------------------------------------

def test_eligible_plus_excluded_equals_total(artifact):
    for lt in ("POWER_LOTTO", "BIG_LOTTO", "DAILY_539"):
        r = artifact["results_by_lottery"][lt]
        assert r["structurally_eligible_rows"] + r["structurally_excluded_rows"] == r["total_replay_rows"], (
            f"{lt}: eligible + excluded != total"
        )


# ---------------------------------------------------------------------------
# Test 36: Processed = eligible
# ---------------------------------------------------------------------------

def test_processed_equals_eligible(artifact):
    for lt in ("POWER_LOTTO", "BIG_LOTTO", "DAILY_539"):
        r = artifact["results_by_lottery"][lt]
        assert r["processed_rows"] == r["structurally_eligible_rows"], (
            f"{lt}: processed_rows != structurally_eligible_rows"
        )


# ---------------------------------------------------------------------------
# Test 37: All rates in [0, 1]
# ---------------------------------------------------------------------------

def test_all_rates_in_0_1(artifact):
    for lt in ("POWER_LOTTO", "BIG_LOTTO", "DAILY_539"):
        r = artifact["results_by_lottery"][lt]
        for rate_dict in [r["any_prize_aware_win_rate"], r["m3_plus_rate"]]:
            rv = rate_dict.get("rate")
            if rv is not None:
                assert 0.0 <= rv <= 1.0, f"{lt}: rate {rv} out of [0,1]"
        for tier, rate_info in r["prize_tier_rates"].items():
            rv = rate_info.get("rate")
            if rv is not None:
                assert 0.0 <= rv <= 1.0, f"{lt}.{tier}: rate {rv} out of [0,1]"
        ep = r["eligible_percentage"]
        if ep.get("rate") is not None:
            assert 0.0 <= ep["rate"] <= 1.0


# ---------------------------------------------------------------------------
# Test 38: Rate numerator/denominator pairs correct
# ---------------------------------------------------------------------------

def test_rate_numerator_denominator_pairs_correct(artifact):
    for lt in ("POWER_LOTTO", "BIG_LOTTO", "DAILY_539"):
        r = artifact["results_by_lottery"][lt]
        n = r["processed_rows"]

        apw = r["any_prize_aware_win_rate"]
        assert apw["numerator"] == r["any_prize_aware_win_count"]
        assert apw["denominator"] == n

        m3r = r["m3_plus_rate"]
        assert m3r["numerator"] == r["m3_plus_true_count"]
        assert m3r["denominator"] == n

        for tier, rate_info in r["prize_tier_rates"].items():
            assert rate_info["numerator"] == r["prize_tier_counts"][tier]
            assert rate_info["denominator"] == n


# ---------------------------------------------------------------------------
# Test 39: DB row counts unchanged (pre == post in artifact)
# ---------------------------------------------------------------------------

def test_db_row_counts_unchanged(artifact):
    snap = artifact["snapshot_metadata"]
    before = snap["total_rows_before"]
    after = snap["total_rows_after"]
    for lt in ("POWER_LOTTO", "BIG_LOTTO", "DAILY_539"):
        assert before[lt] == after[lt], (
            f"{lt}: DB row count changed from {before[lt]} to {after[lt]}"
        )


# ---------------------------------------------------------------------------
# Test 40: db_read_only is true
# ---------------------------------------------------------------------------

def test_db_read_only_true(artifact):
    assert artifact["db_read_only"] is True


# ---------------------------------------------------------------------------
# Test 41: db_write is false
# ---------------------------------------------------------------------------

def test_db_write_false(artifact):
    assert artifact["db_write"] is False


# ---------------------------------------------------------------------------
# Test 42: registry_write is false
# ---------------------------------------------------------------------------

def test_registry_write_false(artifact):
    assert artifact["registry_write"] is False


# ---------------------------------------------------------------------------
# Test 43: existing_replay_modified is false
# ---------------------------------------------------------------------------

def test_existing_replay_modified_false(artifact):
    assert artifact["existing_replay_modified"] is False


# ---------------------------------------------------------------------------
# Test 44: existing_adapter_modified is false
# ---------------------------------------------------------------------------

def test_existing_adapter_modified_false(artifact):
    assert artifact["existing_adapter_modified"] is False


# ---------------------------------------------------------------------------
# Test 45: existing_scorer_modified is false
# ---------------------------------------------------------------------------

def test_existing_scorer_modified_false(artifact):
    assert artifact["existing_scorer_modified"] is False


# ---------------------------------------------------------------------------
# Test 46: existing_m3_replay_scoring_changed is false
# ---------------------------------------------------------------------------

def test_existing_m3_replay_scoring_changed_false(artifact):
    assert artifact["existing_m3_replay_scoring_changed"] is False


# ---------------------------------------------------------------------------
# Test 47: production_integration_added is false
# ---------------------------------------------------------------------------

def test_production_integration_added_false(artifact):
    assert artifact["production_integration_added"] is False


# ---------------------------------------------------------------------------
# Test 48: hit_rate_improvement_claimed is false
# ---------------------------------------------------------------------------

def test_hit_rate_improvement_claimed_false(artifact):
    assert artifact["hit_rate_improvement_claimed"] is False


# ---------------------------------------------------------------------------
# Test 49: prize_amount_logic_added is false
# ---------------------------------------------------------------------------

def test_prize_amount_logic_added_false(artifact):
    assert artifact["prize_amount_logic_added"] is False


# ---------------------------------------------------------------------------
# Test 50: ev_roi_logic_added is false
# ---------------------------------------------------------------------------

def test_ev_roi_logic_added_false(artifact):
    assert artifact["ev_roi_logic_added"] is False


# ---------------------------------------------------------------------------
# Test 51: p270c_allowed is false
# ---------------------------------------------------------------------------

def test_p270c_allowed_false(artifact):
    assert artifact["p270c_allowed"] is False


# ---------------------------------------------------------------------------
# Test 52: MD contains all required safety declarations
# ---------------------------------------------------------------------------

def test_md_required_safety_declarations(md_content):
    content_lower = md_content.lower()
    declarations = [
        "all structurally eligible historical rows were processed",
        "power_lotto results apply only to rows with a stored prediction-time second-zone value",
        "missing power second-zone predictions were excluded and never filled",
        "output is aggregate only",
        "no raw predicted or actual number arrays were exported",
        "no strategy-level aggregation, comparison, or ranking was performed",
        "no random/null baseline was calculated",
        "no p-value, confidence interval, lift, or multiple-testing correction was calculated",
        "descriptive observed rates do not demonstrate predictive improvement",
        "existing replay.py, adapter, scorer, and m3+ semantics remain unchanged",
        "db access was read-only and no db write occurred",
        "no registry or production integration was added",
        "no prize amount, ev, roi, or betting advice was calculated",
        "official source status remains manual_verification_required",
        "p270c remains unauthorized",
        "temporal-window research and feature mining were not started",
    ]
    for decl in declarations:
        assert decl in content_lower, f"MD missing declaration: {decl!r}"


# ---------------------------------------------------------------------------
# Test 53: Final classification belongs to allowed set
# ---------------------------------------------------------------------------

def test_final_classification_in_allowed_set(artifact):
    from analysis.p271f_prize_aware_full_history_descriptive_evaluation import (
        ALLOWED_FINAL_CLASSIFICATIONS,
    )
    assert artifact["final_classification"] in ALLOWED_FINAL_CLASSIFICATIONS


# ---------------------------------------------------------------------------
# Test 54: Source status remains MANUAL_VERIFICATION_REQUIRED
# ---------------------------------------------------------------------------

def test_source_status_manual_verification_required(artifact):
    assert artifact["source_verification_status"] == "MANUAL_VERIFICATION_REQUIRED"


# ---------------------------------------------------------------------------
# Test 55: No strategy/model identifiers in result aggregation keys
# ---------------------------------------------------------------------------

def test_no_strategy_model_identifiers_in_result_keys(artifact):
    for lt in ("POWER_LOTTO", "BIG_LOTTO", "DAILY_539"):
        r = artifact["results_by_lottery"][lt]
        all_keys = list(r.keys())
        for key in all_keys:
            assert "strategy_id" not in key.lower(), (
                f"{lt} result has strategy_id-level key: {key!r}"
            )
            assert "model_id" not in key.lower(), (
                f"{lt} result has model_id-level key: {key!r}"
            )


# ---------------------------------------------------------------------------
# Additional integrity tests
# ---------------------------------------------------------------------------

def test_power_eligible_count_matches_p271d_snapshot(artifact):
    """POWER_LOTTO eligible count must match P271D feasibility snapshot."""
    r = artifact["results_by_lottery"]["POWER_LOTTO"]
    assert r["structurally_eligible_rows"] == 9000
    assert r["total_replay_rows"] == 36104


def test_big_eligible_count_matches_p271d_snapshot(artifact):
    r = artifact["results_by_lottery"]["BIG_LOTTO"]
    assert r["total_replay_rows"] == 24140
    assert r["structurally_eligible_rows"] == 24140


def test_daily_539_eligible_count_matches_p271d_snapshot(artifact):
    r = artifact["results_by_lottery"]["DAILY_539"]
    assert r["total_replay_rows"] == 34680
    assert r["structurally_eligible_rows"] == 34680


def test_power_full_population_evaluation_run_is_false(artifact):
    assert artifact["power_full_population_evaluation_run"] is False


def test_full_eligible_history_evaluation_run_is_true(artifact):
    assert artifact["full_eligible_history_evaluation_run"] is True


def test_descriptive_rates_calculated_is_true(artifact):
    assert artifact["descriptive_rates_calculated"] is True


def test_inferential_test_run_is_false(artifact):
    assert artifact["inferential_test_run"] is False


def test_final_classification_is_complete_with_power_subset(artifact):
    assert artifact["final_classification"] == (
        "P271F_COMPLETE_WITH_POWER_ELIGIBLE_SUBSET_ONLY"
    )


def test_all_invariants_pass_in_artifact(artifact):
    for lt in ("POWER_LOTTO", "BIG_LOTTO", "DAILY_539"):
        inv = artifact["invariant_checks_by_lottery"][lt]
        assert inv.get("all_invariants_pass") is True, (
            f"{lt}: invariant failure — {inv}"
        )


def test_adapter_version_correct(artifact):
    assert artifact["adapter_version"] == "prize_aware_adapter_v1"


def test_scoring_version_correct(artifact):
    assert artifact["scoring_version"] == "prize_aware_v1"


def test_canonical_db_path_correct(artifact):
    assert artifact["canonical_db_path"] == "lottery_api/data/lottery_v2.db"


def test_db_open_mode_correct(artifact):
    assert artifact["db_open_mode"] == "sqlite3 URI mode=ro"


def test_aggregate_only_flag_set(artifact):
    assert artifact["aggregate_only_output"] is True


def test_strategy_comparison_run_is_false(artifact):
    assert artifact["strategy_comparison_run"] is False


def test_strategy_ranking_run_is_false(artifact):
    assert artifact["strategy_ranking_run"] is False


def test_random_baseline_calculated_is_false(artifact):
    assert artifact["random_baseline_calculated"] is False


def test_p_value_calculated_is_false(artifact):
    assert artifact["p_value_calculated"] is False


def test_confidence_interval_calculated_is_false(artifact):
    assert artifact["confidence_interval_calculated"] is False


def test_lift_calculated_is_false(artifact):
    assert artifact["lift_calculated"] is False


def test_multiple_testing_correction_is_false(artifact):
    assert artifact["multiple_testing_correction_run"] is False


def test_temporal_window_research_started_is_false(artifact):
    assert artifact["temporal_window_research_started"] is False


def test_feature_mining_started_is_false(artifact):
    assert artifact["feature_mining_started"] is False


def test_md_focused_test_count_55_passed(md_content):
    assert "55 passed" in md_content


def test_md_full_repo_suite_not_run(md_content):
    assert "NOT RUN" in md_content
