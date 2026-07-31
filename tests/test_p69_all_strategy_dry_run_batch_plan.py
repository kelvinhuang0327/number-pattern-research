"""
P69 All-Strategy Dry-Run Batch Plan Governance Tests.

Asserts all P69 governance, classification, and candidate requirements.
No DB writes are made by any test.
"""

import json
import os
import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSON_PATH = os.path.join(
    REPO_ROOT,
    "outputs/replay/p69_all_strategy_dry_run_batch_plan_20260526.json",
)
DOC_PATH = os.path.join(
    REPO_ROOT,
    "docs/replay/p69_all_strategy_dry_run_batch_plan_20260526.md",
)


@pytest.fixture(scope="module")
def plan():
    with open(JSON_PATH) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# File existence
# ---------------------------------------------------------------------------


def test_json_file_exists():
    assert os.path.isfile(JSON_PATH), f"P69 JSON not found: {JSON_PATH}"


def test_doc_file_exists():
    assert os.path.isfile(DOC_PATH), f"P69 doc not found: {DOC_PATH}"


# ---------------------------------------------------------------------------
# Project context lock
# ---------------------------------------------------------------------------


def test_project_context_lock(plan):
    assert plan["project_context_lock"] == "LotteryNew"


def test_phase(plan):
    assert plan["phase"] == "P69"


# ---------------------------------------------------------------------------
# Production row invariant
# ---------------------------------------------------------------------------


def test_production_rows_before(plan):
    assert plan["production_rows_before"] == 46960


def test_production_rows_after(plan):
    assert plan["production_rows_after"] == 46960


# ---------------------------------------------------------------------------
# Governance flags
# ---------------------------------------------------------------------------


def test_no_db_write(plan):
    assert plan["no_db_write"] is True


def test_no_force_push(plan):
    assert plan["no_force_push"] is True


def test_no_lifecycle_promotion(plan):
    assert plan["no_lifecycle_promotion"] is True


def test_no_champion_replacement(plan):
    assert plan["no_champion_replacement"] is True


def test_no_registry_mutation(plan):
    assert plan["no_registry_mutation"] is True


def test_no_production_apply(plan):
    assert plan["no_production_apply"] is True


# ---------------------------------------------------------------------------
# Authorized candidate count
# ---------------------------------------------------------------------------


def test_authorized_candidate_count(plan):
    assert plan["authorized_candidate_count"] == 8


def test_authorized_candidates_list_length(plan):
    assert len(plan["authorized_candidates"]) == 8


# ---------------------------------------------------------------------------
# POWER_LOTTO candidates
# ---------------------------------------------------------------------------


def _get_candidate(plan, strategy_id, lottery_type):
    for c in plan["authorized_candidates"]:
        if c["strategy_id"] == strategy_id and c["lottery_type"] == lottery_type:
            return c
    return None


def test_power_lotto_fourier_rhythm_3bet_present(plan):
    c = _get_candidate(plan, "fourier_rhythm_3bet", "POWER_LOTTO")
    assert c is not None, "fourier_rhythm_3bet (POWER_LOTTO) must be in authorized candidates"


def test_power_lotto_fourier30_markov30_2bet_present(plan):
    c = _get_candidate(plan, "fourier30_markov30_2bet", "POWER_LOTTO")
    assert c is not None, "fourier30_markov30_2bet (POWER_LOTTO) must be in authorized candidates"


def test_power_lotto_candidates_are_prediction_helpful(plan):
    for strategy_id in ("fourier_rhythm_3bet", "fourier30_markov30_2bet"):
        c = _get_candidate(plan, strategy_id, "POWER_LOTTO")
        assert c["p2_label"] == "prediction-helpful", f"{strategy_id} must be prediction-helpful"


def test_power_lotto_candidates_above_baseline(plan):
    baseline = plan["p2_gate_summary"]["baselines"]["POWER_LOTTO"]
    for c in plan["authorized_candidates"]:
        if c["lottery_type"] == "POWER_LOTTO":
            assert c["m3plus_pct"] / 100.0 > baseline, (
                f"{c['strategy_id']} m3+={c['m3plus_pct']}% must exceed baseline {baseline*100:.2f}%"
            )


# ---------------------------------------------------------------------------
# DAILY_539 candidates
# ---------------------------------------------------------------------------


def test_daily539_acb_1bet_present(plan):
    c = _get_candidate(plan, "acb_1bet", "DAILY_539")
    assert c is not None, "acb_1bet (DAILY_539) must be in authorized candidates"


def test_daily539_acb_markov_midfreq_3bet_present(plan):
    c = _get_candidate(plan, "acb_markov_midfreq_3bet", "DAILY_539")
    assert c is not None, "acb_markov_midfreq_3bet (DAILY_539) must be in authorized candidates"


def test_daily539_midfreq_acb_2bet_present(plan):
    c = _get_candidate(plan, "midfreq_acb_2bet", "DAILY_539")
    assert c is not None, "midfreq_acb_2bet (DAILY_539) must be in authorized candidates"


def test_daily539_midfreq_fourier_2bet_present(plan):
    c = _get_candidate(plan, "midfreq_fourier_2bet", "DAILY_539")
    assert c is not None, "midfreq_fourier_2bet (DAILY_539) must be in authorized candidates"


def test_daily539_539_3bet_orthogonal_present(plan):
    c = _get_candidate(plan, "539_3bet_orthogonal", "DAILY_539")
    assert c is not None, "539_3bet_orthogonal (DAILY_539) must be in authorized candidates"


def test_daily539_acb_single_539_present(plan):
    c = _get_candidate(plan, "acb_single_539", "DAILY_539")
    assert c is not None, "acb_single_539 (DAILY_539) must be in authorized candidates"


def test_daily539_candidates_above_baseline(plan):
    baseline = plan["p2_gate_summary"]["baselines"]["DAILY_539"]
    for c in plan["authorized_candidates"]:
        if c["lottery_type"] == "DAILY_539":
            assert c["m3plus_pct"] / 100.0 > baseline, (
                f"{c['strategy_id']} m3+={c['m3plus_pct']}% must exceed baseline {baseline*100:.2f}%"
            )


# ---------------------------------------------------------------------------
# BIG_LOTTO excluded
# ---------------------------------------------------------------------------


def test_big_lotto_not_in_authorized_candidates(plan):
    for c in plan["authorized_candidates"]:
        assert c["lottery_type"] != "BIG_LOTTO", (
            f"BIG_LOTTO strategy {c['strategy_id']} must not be in authorized candidates"
        )


def test_big_lotto_exclusion_documented(plan):
    excluded = plan["excluded_candidates"]
    assert "BIG_LOTTO_excluded_reason" in excluded, "BIG_LOTTO exclusion must be documented"
    assert "signal_space_exhausted" in excluded["BIG_LOTTO_excluded_reason"]


# ---------------------------------------------------------------------------
# Specific exclusions
# ---------------------------------------------------------------------------


def test_cold_complement_2bet_excluded_as_sub_baseline(plan):
    excluded = plan["excluded_candidates"]
    assert "cold_complement_2bet" in excluded
    assert excluded["cold_complement_2bet"]["reason"] == "sub-baseline"


def test_zonal_entropy_2bet_excluded_as_fallback_equivalent(plan):
    excluded = plan["excluded_candidates"]
    assert "zonal_entropy_2bet" in excluded
    assert excluded["zonal_entropy_2bet"]["reason"] == "fallback-equivalent"


def test_midfreq_fourier_mk_3bet_deferred(plan):
    excluded = plan["excluded_candidates"]
    assert "midfreq_fourier_mk_3bet" in excluded
    assert "deferred" in excluded["midfreq_fourier_mk_3bet"]["reason"]
    assert "OOS" in excluded["midfreq_fourier_mk_3bet"]["reason"]


# ---------------------------------------------------------------------------
# All candidates have 1500 rows
# ---------------------------------------------------------------------------


def test_all_candidates_have_1500_rows(plan):
    for c in plan["authorized_candidates"]:
        assert c["rows"] == 1500, f"{c['strategy_id']} rows={c['rows']} must be 1500"


# ---------------------------------------------------------------------------
# Dry-run recommendation is dry-run-now for all 8
# ---------------------------------------------------------------------------


def test_all_candidates_dry_run_now(plan):
    for c in plan["authorized_candidates"]:
        assert c["dry_run_recommendation"] == "dry-run-now", (
            f"{c['strategy_id']} recommendation must be dry-run-now"
        )


# ---------------------------------------------------------------------------
# P70 gate requirements present for all candidates
# ---------------------------------------------------------------------------


def test_all_candidates_have_p70_gate_requirements(plan):
    for c in plan["authorized_candidates"]:
        gates = c.get("p70_gate_requirements", [])
        assert len(gates) >= 7, (
            f"{c['strategy_id']} must have at least 7 P70 gate requirements (got {len(gates)})"
        )


def test_p70_gate_includes_explicit_apply_authorization(plan):
    for c in plan["authorized_candidates"]:
        assert "explicit_apply_authorization" in c["p70_gate_requirements"], (
            f"{c['strategy_id']} must require explicit_apply_authorization for P70"
        )


def test_p70_gate_includes_branch_governance(plan):
    for c in plan["authorized_candidates"]:
        assert "branch_governance_guard_pass" in c["p70_gate_requirements"], (
            f"{c['strategy_id']} must require branch_governance_guard_pass for P70"
        )


def test_p70_gate_includes_drift_guard(plan):
    for c in plan["authorized_candidates"]:
        assert "drift_guard_pass" in c["p70_gate_requirements"], (
            f"{c['strategy_id']} must require drift_guard_pass for P70"
        )


# ---------------------------------------------------------------------------
# Retired lifecycle candidates require lifecycle promotion gate for P70
# ---------------------------------------------------------------------------


def test_retired_lifecycle_candidates_require_promotion_gate(plan):
    retired_strategies = {
        "acb_markov_midfreq_3bet", "midfreq_acb_2bet", "midfreq_fourier_2bet", "acb_1bet"
    }
    for c in plan["authorized_candidates"]:
        if c["strategy_id"] in retired_strategies:
            assert c["lifecycle"] == "RETIRED", (
                f"{c['strategy_id']} must have RETIRED lifecycle"
            )
            assert "lifecycle_promotion_explicit_authorization" in c["p70_gate_requirements"], (
                f"{c['strategy_id']} (RETIRED) must require lifecycle_promotion_explicit_authorization"
            )


# ---------------------------------------------------------------------------
# midfreq_fourier_2bet DAILY_539 requires lottery_type filter gate
# ---------------------------------------------------------------------------


def test_midfreq_fourier_2bet_daily539_requires_lottery_type_filter(plan):
    c = _get_candidate(plan, "midfreq_fourier_2bet", "DAILY_539")
    assert c is not None
    assert "lottery_type_filter_confirmed_DAILY_539" in c["p70_gate_requirements"], (
        "midfreq_fourier_2bet DAILY_539 must require lottery_type_filter_confirmed_DAILY_539"
    )


# ---------------------------------------------------------------------------
# Row impact estimates
# ---------------------------------------------------------------------------


def test_row_impact_production_db_not_written(plan):
    assert plan["row_impact_estimates"]["production_db_written"] is False


def test_row_impact_1500_draws_total(plan):
    ri = plan["row_impact_estimates"]["1500_draws"]
    # 2 POWER_LOTTO × 1500 + 6 DAILY_539 × 1500 = 3000 + 9000 = 12000
    assert ri["total_temp_rows"] == 12000


def test_row_impact_if_p70_applies_all_8(plan):
    ri = plan["row_impact_estimates"]["if_p70_applies_all_8"]
    assert ri["new_production_rows"] == 12000
    assert ri["production_rows_before"] == 46960
    assert ri["production_rows_after"] == 58960


# ---------------------------------------------------------------------------
# Final classification
# ---------------------------------------------------------------------------


def test_final_classification(plan):
    assert plan["final_classification"] == "P69_ALL_STRATEGY_DRY_RUN_BATCH_PLAN_READY"


# ---------------------------------------------------------------------------
# Document content checks
# ---------------------------------------------------------------------------


def test_doc_contains_project_context_lock():
    with open(DOC_PATH) as f:
        content = f.read()
    assert "PROJECT_CONTEXT_LOCK" in content
    assert "LotteryNew" in content


def test_doc_contains_all_8_candidates():
    with open(DOC_PATH) as f:
        content = f.read()
    expected = [
        "fourier_rhythm_3bet",
        "fourier30_markov30_2bet",
        "acb_1bet",
        "acb_markov_midfreq_3bet",
        "midfreq_acb_2bet",
        "midfreq_fourier_2bet",
        "539_3bet_orthogonal",
        "acb_single_539",
    ]
    for sid in expected:
        assert sid in content, f"Doc must mention {sid}"


def test_doc_contains_big_lotto_exclusion():
    with open(DOC_PATH) as f:
        content = f.read()
    assert "BIG_LOTTO" in content
    assert "Excluded" in content or "excluded" in content


def test_doc_contains_governance_confirmation():
    with open(DOC_PATH) as f:
        content = f.read()
    assert "No DB write" in content
    assert "No force push" in content
    assert "No lifecycle promotion" in content


def test_doc_contains_final_classification():
    with open(DOC_PATH) as f:
        content = f.read()
    assert "P69_ALL_STRATEGY_DRY_RUN_BATCH_PLAN_READY" in content
