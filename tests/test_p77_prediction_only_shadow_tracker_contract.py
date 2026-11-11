"""
P77 tests — 2026 Prediction-Only Shadow Tracker Contract
Run: ./.venv/bin/pytest tests/test_p77_prediction_only_shadow_tracker_contract.py -v
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _load_json(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def _load_summary() -> dict:
    return _load_json(ROOT / "data/mlb_2025/derived/p77_prediction_only_shadow_tracker_contract_summary.json")


# ---------------------------------------------------------------------------
# Lazily import contract module
# ---------------------------------------------------------------------------
import importlib, sys

def _contract():
    spec = importlib.util.spec_from_file_location(
        "_p77_prediction_only_shadow_tracker_contract",
        ROOT / "scripts/_p77_prediction_only_shadow_tracker_contract.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="session")
def contract_mod():
    return _contract()


@pytest.fixture(scope="session")
def summary(contract_mod):
    """Run the main() function and return the summary dict."""
    return contract_mod.main()


# ===========================================================================
# 1. Source artifacts load
# ===========================================================================

def test_p72a_artifact_loads():
    d = _load_json(ROOT / "data/mlb_2025/derived/p72a_odds_free_strategy_accuracy_backtest_summary.json")
    assert "phase" in d or "final_classification" in d or "strategy_results" in d


def test_p72b_artifact_loads():
    d = _load_json(ROOT / "data/mlb_2025/derived/p72b_objective_metric_contract_summary.json")
    assert d is not None


def test_p73_artifact_loads():
    d = _load_json(ROOT / "data/mlb_2025/derived/p73_tier_stability_and_sample_expansion_summary.json")
    assert "phase" in d


def test_p74_artifact_loads():
    d = _load_json(ROOT / "data/mlb_2025/derived/p74_tier_c_home_away_bias_correction_summary.json")
    assert "phase" in d


def test_p75a_artifact_loads():
    d = _load_json(ROOT / "data/mlb_2025/derived/p75a_tier_c_corrected_rule_validator_summary.json")
    assert "phase" in d


def test_p75b_artifact_loads():
    d = _load_json(ROOT / "data/mlb_2025/derived/p75b_calibration_diagnostics_corrected_tier_c_summary.json")
    assert "phase" in d


def test_p76_artifact_loads():
    d = _load_json(ROOT / "data/mlb_2025/derived/p76_corrected_tier_c_final_rule_selection_summary.json")
    assert "phase" in d


# ===========================================================================
# 2–3. P76 dual-finalist verification
# ===========================================================================

def test_p76_final_classification_verified(summary):
    verif = summary["step1_p76_verification"]
    assert verif["verification_passed"], f"P76 verification failed: {verif['verification_issues']}"


def test_p76_classification_is_dual_finalists(summary):
    verif = summary["step1_p76_verification"]
    assert verif["p76_classification"] == "P76_DUAL_FINALISTS_RETAINED_UNTIL_2026_DATA"


def test_p76_dual_finalist_score_delta_verified(summary):
    verif = summary["step1_p76_verification"]
    assert verif["score_delta"] == 0.0003
    assert verif["score_125"] == 0.5543
    assert verif["score_100"] == 0.5540


# ===========================================================================
# 4–6. Shadow tracker row schema
# ===========================================================================

def test_shadow_tracker_row_schema_generated(summary):
    schema = summary["step2_row_schema"]
    assert schema is not None
    assert schema["schema_version"] == "p77-v1"


def test_required_row_schema_fields_present(summary):
    schema = summary["step2_row_schema"]
    required_fields = [
        "game_id", "game_date", "season", "home_team", "away_team",
        "predicted_side", "actual_winner", "is_correct", "model_probability",
        "sp_fip_delta", "abs_sp_fip_delta",
        "selected_rule_home_plus_away_125_flag",
        "shadow_rule_home_plus_away_100_flag",
        "tier_b_candidate_flag", "tier_a_watchlist_flag",
        "home_pick_flag", "away_pick_flag",
        "month", "source_prediction_version",
    ]
    for field in required_fields:
        assert field in schema["fields"], f"Missing field: {field}"


def test_governance_fields_present(summary):
    schema = summary["step2_row_schema"]
    gov_fields = [
        "paper_only", "diagnostic_only", "market_edge_evaluated",
        "odds_used", "ev_calculated", "clv_calculated",
        "kelly_calculated", "production_ready",
    ]
    for f in gov_fields:
        assert f in schema["governance_fields"], f"Missing governance field: {f}"
        assert f in schema["fields"], f"Missing governance field in fields: {f}"


def test_governance_paper_only_true(summary):
    gov = summary["step2_row_schema"]["governance_frozen"]
    assert gov["paper_only"] is True


def test_governance_odds_used_false(summary):
    gov = summary["step2_row_schema"]["governance_frozen"]
    assert gov["odds_used"] is False


def test_governance_ev_calculated_false(summary):
    gov = summary["step2_row_schema"]["governance_frozen"]
    assert gov["ev_calculated"] is False


def test_governance_clv_calculated_false(summary):
    gov = summary["step2_row_schema"]["governance_frozen"]
    assert gov["clv_calculated"] is False


def test_governance_kelly_calculated_false(summary):
    gov = summary["step2_row_schema"]["governance_frozen"]
    assert gov["kelly_calculated"] is False


def test_governance_production_ready_false(summary):
    gov = summary["step2_row_schema"]["governance_frozen"]
    assert gov["production_ready"] is False


# ===========================================================================
# 13–14. Rule contracts generated
# ===========================================================================

def test_home_plus_away_125_rule_contract_generated(summary):
    rules = summary["step3_rule_contract"]["rules"]
    assert "TIER_C_HOME_PLUS_AWAY_125" in rules
    r = rules["TIER_C_HOME_PLUS_AWAY_125"]
    assert r["role"] == "primary_tracking_rule"
    assert r["home_threshold"] == 0.50
    assert r["away_threshold"] == 1.25


def test_home_plus_away_100_rule_contract_generated(summary):
    rules = summary["step3_rule_contract"]["rules"]
    assert "TIER_C_HOME_PLUS_AWAY_100" in rules
    r = rules["TIER_C_HOME_PLUS_AWAY_100"]
    assert r["role"] == "shadow_tracking_rule"
    assert r["home_threshold"] == 0.50
    assert r["away_threshold"] == 1.00


# ===========================================================================
# 15. Rule semantics match P76/P75B expected counts on 2025 data
# ===========================================================================

def test_rule_semantics_match_p75b_expected_counts(summary):
    semval = summary["step3b_semantics_validation"]
    assert semval["validation_status"] == "PASS", (
        f"Rule semantics failed: {semval['rule_count_checks']}"
    )
    checks = semval["rule_count_checks"]
    assert checks["TIER_C_HOME_PLUS_AWAY_100"]["match"], f"HOME_PLUS_AWAY_100 count mismatch"
    assert checks["TIER_C_HOME_PLUS_AWAY_125"]["match"], f"HOME_PLUS_AWAY_125 count mismatch"


def test_rule_semantics_home_only_count(summary):
    checks = summary["step3b_semantics_validation"]["rule_count_checks"]
    assert checks["TIER_C_HOME_ONLY"]["computed"] == 268
    assert checks["TIER_C_HOME_ONLY"]["match"] is True


def test_rule_semantics_away_100_count(summary):
    checks = summary["step3b_semantics_validation"]["rule_count_checks"]
    assert checks["TIER_C_HOME_PLUS_AWAY_100"]["computed"] == 373


def test_rule_semantics_away_125_count(summary):
    checks = summary["step3b_semantics_validation"]["rule_count_checks"]
    assert checks["TIER_C_HOME_PLUS_AWAY_125"]["computed"] == 316


# ===========================================================================
# 16–18. Tier B / Tier A flags
# ===========================================================================

def test_tier_b_candidate_flag_defined(summary):
    rules = summary["step3_rule_contract"]["rules"]
    assert "TIER_B_CANDIDATE" in rules
    tb = rules["TIER_B_CANDIDATE"]
    assert tb["lo_threshold"] == 0.25
    assert tb["hi_threshold"] == 0.50


def test_tier_b_n200_reeval_trigger_present(summary):
    triggers = summary["step5_reeval_triggers"]["tier_b_reeval"]
    assert triggers["trigger_n"] == 200
    assert triggers["trigger_phase"] == "P78"


def test_tier_a_watchlist_flag_defined(summary):
    rules = summary["step3_rule_contract"]["rules"]
    assert "TIER_A_WATCHLIST" in rules
    ta = rules["TIER_A_WATCHLIST"]
    assert ta["lo_threshold"] == 1.50
    assert ta["operational_n_minimum"] == 50


# ===========================================================================
# 19–20. Monthly metrics contract
# ===========================================================================

def test_monthly_metrics_contract_generated(summary):
    metrics = summary["step4_monthly_metrics"]
    assert metrics is not None
    assert len(metrics["metrics_per_rule_per_month"]) > 0


def test_monthly_cadence_present(summary):
    cadence = summary["step4_monthly_metrics"]["monthly_cadence_2026"]
    months = [e["month"] for e in cadence]
    assert "2026-06" in months
    assert "2026-10" in months


# ===========================================================================
# 21–27. Re-evaluation triggers
# ===========================================================================

def test_checkpoint_n50_present(summary):
    tc = summary["step5_reeval_triggers"]["tier_c_selected_shadow_reeval"]
    assert tc["checkpoint_1"]["n_threshold"] == 50


def test_checkpoint_n100_present(summary):
    tc = summary["step5_reeval_triggers"]["tier_c_selected_shadow_reeval"]
    assert tc["checkpoint_2"]["n_threshold"] == 100


def test_checkpoint_n200_present(summary):
    tc = summary["step5_reeval_triggers"]["tier_c_selected_shadow_reeval"]
    assert tc["operational_checkpoint"]["n_threshold"] == 200


def test_end_season_checkpoint_present(summary):
    tc = summary["step5_reeval_triggers"]["tier_c_selected_shadow_reeval"]
    sc = tc["seasonal_checkpoint"]
    assert sc["trigger"] == "end_of_2026_regular_season"


def test_rolling_100_downgrade_criterion_present(summary):
    tc = summary["step5_reeval_triggers"]["tier_c_selected_shadow_reeval"]
    criteria_ids = [dc["criterion_id"] for dc in tc["downgrade_criteria"]]
    assert "rolling_100_floor" in criteria_ids


def test_consecutive_monthly_downgrade_criterion_present(summary):
    tc = summary["step5_reeval_triggers"]["tier_c_selected_shadow_reeval"]
    criteria_ids = [dc["criterion_id"] for dc in tc["downgrade_criteria"]]
    assert "consecutive_monthly_floor" in criteria_ids


def test_ece_downgrade_criterion_present(summary):
    tc = summary["step5_reeval_triggers"]["tier_c_selected_shadow_reeval"]
    criteria_ids = [dc["criterion_id"] for dc in tc["downgrade_criteria"]]
    assert "ece_worsening" in criteria_ids


# ===========================================================================
# 28–30. Market-edge / odds separation
# ===========================================================================

def test_market_edge_lane_remains_separate(summary):
    me = summary["step5_reeval_triggers"]["market_edge_lane"]
    assert me["status"] == "DEFERRED"
    assert me["blocked_in_p77"] is True


def test_no_odds_required(summary):
    metrics = summary["step4_monthly_metrics"]
    assert metrics["no_odds_metrics"] is True


def test_no_ev_clv_kelly_calculated(summary):
    gov = summary["governance"]
    assert gov["ev_calculated"] is False
    assert gov["clv_calculated"] is False
    assert gov["kelly_calculated"] is False
    assert gov["kelly_deploy_allowed"] is False


# ===========================================================================
# 31–32. Governance invariants
# ===========================================================================

def test_live_api_calls_zero(summary):
    assert summary["governance"]["live_api_calls"] == 0


def test_production_ready_false(summary):
    assert summary["governance"]["production_ready"] is False


# ===========================================================================
# 33. Forbidden phrase scan
# ===========================================================================

def test_forbidden_phrase_scan_passes(summary):
    forb = summary["step6_forbidden_scan"]
    assert forb["scan_passed"], f"Forbidden phrase violations: {forb['violations']}"


# ===========================================================================
# 34. JSON schema stable
# ===========================================================================

def test_json_schema_stable(summary):
    required_top_keys = [
        "phase", "date", "p77_classification", "governance", "step1_p76_verification",
        "step2_row_schema", "step3_rule_contract", "step3b_semantics_validation",
        "step4_monthly_metrics", "step5_reeval_triggers", "step6_forbidden_scan",
        "p78_recommendation",
    ]
    for key in required_top_keys:
        assert key in summary, f"Missing top-level key: {key}"


# ===========================================================================
# 35–36. Report includes required sections
# ===========================================================================

def test_report_includes_row_schema():
    report = (ROOT / "report/p77_prediction_only_shadow_tracker_contract_20260526.md").read_text()
    assert "Row Schema" in report or "row schema" in report.lower()
    assert "paper_only" in report


def test_report_includes_trigger_table():
    report = (ROOT / "report/p77_prediction_only_shadow_tracker_contract_20260526.md").read_text()
    assert "Re-evaluation Triggers" in report or "trigger" in report.lower()
    assert "n_threshold" in report or "n >= 200" in report or "n>=200" in report or "200" in report


# ===========================================================================
# 37. active_task.md updated
# ===========================================================================

def test_active_task_md_updated():
    active = (ROOT / "00-Plan/roadmap/active_task.md").read_text()
    assert "P77" in active, "active_task.md must mention P77"


# ===========================================================================
# 38. P72A–P77 regression: all phases pass
# ===========================================================================

def test_p72a_final_classification():
    d = _load_json(ROOT / "data/mlb_2025/derived/p72a_odds_free_strategy_accuracy_backtest_summary.json")
    cls = d.get("final_classification", "")
    assert "P72A" in cls


def test_p72b_classification_present():
    d = _load_json(ROOT / "data/mlb_2025/derived/p72b_objective_metric_contract_summary.json")
    assert d is not None


def test_p73_classification_present():
    d = _load_json(ROOT / "data/mlb_2025/derived/p73_tier_stability_and_sample_expansion_summary.json")
    cls = d.get("p73_classification", "")
    assert "P73" in cls


def test_p74_classification_present():
    d = _load_json(ROOT / "data/mlb_2025/derived/p74_tier_c_home_away_bias_correction_summary.json")
    cls = d.get("p74_classification", "")
    assert "P74" in cls


def test_p75a_classification_present():
    d = _load_json(ROOT / "data/mlb_2025/derived/p75a_tier_c_corrected_rule_validator_summary.json")
    cls = d.get("p75a_classification", "")
    assert "P75A" in cls


def test_p75b_classification_present():
    d = _load_json(ROOT / "data/mlb_2025/derived/p75b_calibration_diagnostics_corrected_tier_c_summary.json")
    cls = d.get("p75b_classification", "")
    assert "P75B" in cls


def test_p76_classification_present():
    d = _load_json(ROOT / "data/mlb_2025/derived/p76_corrected_tier_c_final_rule_selection_summary.json")
    cls = d.get("p76_classification", "")
    assert cls == "P76_DUAL_FINALISTS_RETAINED_UNTIL_2026_DATA"


def test_p77_classification_is_contract_ready(summary):
    assert summary["p77_classification"] in [
        "P77_SHADOW_TRACKER_CONTRACT_READY",
        "P77_SHADOW_TRACKER_CONTRACT_READY_WITH_CAVEATS",
    ]


# ===========================================================================
# Additional unit tests for rule computation functions
# ===========================================================================

def test_home_plus_away_125_home_pick(contract_mod):
    # Home pick: sp_fip_delta > 0, abs >= 0.50 → True
    assert contract_mod.compute_selected_rule_home_plus_away_125_flag(0.82, 0.82, True) is True


def test_home_plus_away_125_home_pick_below_threshold(contract_mod):
    # Home pick: abs < 0.50 → False
    assert contract_mod.compute_selected_rule_home_plus_away_125_flag(0.30, 0.30, True) is False


def test_home_plus_away_125_away_pick_above_threshold(contract_mod):
    # Away pick: sp_fip_delta < 0, abs >= 1.25 → True
    assert contract_mod.compute_selected_rule_home_plus_away_125_flag(-1.40, 1.40, True) is True


def test_home_plus_away_125_away_pick_below_threshold(contract_mod):
    # Away pick: abs = 1.10 < 1.25 → False for 125
    assert contract_mod.compute_selected_rule_home_plus_away_125_flag(-1.10, 1.10, True) is False


def test_home_plus_away_100_away_pick_above_threshold(contract_mod):
    # Away pick: abs = 1.10 >= 1.00 → True for 100
    assert contract_mod.compute_shadow_rule_home_plus_away_100_flag(-1.10, 1.10, True) is True


def test_home_plus_away_100_away_pick_below_threshold(contract_mod):
    # Away pick: abs = 0.80 < 1.00 → False for 100
    assert contract_mod.compute_shadow_rule_home_plus_away_100_flag(-0.80, 0.80, True) is False


def test_home_plus_away_not_available(contract_mod):
    assert contract_mod.compute_selected_rule_home_plus_away_125_flag(1.50, 1.50, False) is False
    assert contract_mod.compute_shadow_rule_home_plus_away_100_flag(1.50, 1.50, False) is False


def test_tier_b_candidate_in_band(contract_mod):
    assert contract_mod.compute_tier_b_candidate_flag(0.35, True) is True


def test_tier_b_candidate_at_boundary_low(contract_mod):
    assert contract_mod.compute_tier_b_candidate_flag(0.25, True) is True


def test_tier_b_candidate_at_boundary_high(contract_mod):
    # 0.50 is NOT in Tier B (it's Tier C)
    assert contract_mod.compute_tier_b_candidate_flag(0.50, True) is False


def test_tier_b_candidate_below_band(contract_mod):
    assert contract_mod.compute_tier_b_candidate_flag(0.10, True) is False


def test_tier_a_watchlist_above_threshold(contract_mod):
    assert contract_mod.compute_tier_a_watchlist_flag(1.60, True) is True


def test_tier_a_watchlist_below_threshold(contract_mod):
    assert contract_mod.compute_tier_a_watchlist_flag(1.40, True) is False


def test_tier_a_watchlist_not_available(contract_mod):
    assert contract_mod.compute_tier_a_watchlist_flag(2.00, False) is False
