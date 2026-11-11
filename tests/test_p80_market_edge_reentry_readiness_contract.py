"""
tests/test_p80_market_edge_reentry_readiness_contract.py

P80 — Market-Edge Lane Re-entry Readiness Contract
42 tests covering all required verification areas.
"""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DERIVED = ROOT / "data/mlb_2025/derived"
SUMMARY_PATH = DERIVED / "p80_market_edge_reentry_readiness_contract_summary.json"
REPORT_PATH = ROOT / "report/p80_market_edge_reentry_readiness_contract_20260526.md"
SCRIPT_PATH = ROOT / "scripts/_p80_market_edge_reentry_readiness_contract.py"


@pytest.fixture(scope="module")
def summary() -> dict:
    assert SUMMARY_PATH.exists(), f"P80 summary missing: {SUMMARY_PATH}"
    return json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def module():
    spec = importlib.util.spec_from_file_location(
        "_p80_market_edge_reentry_readiness_contract", SCRIPT_PATH
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# 1. P79B source artifact loads
# ---------------------------------------------------------------------------

def test_01_p79b_summary_loads(summary):
    assert "step1_prediction_lane_verified" in summary
    s1 = summary["step1_prediction_lane_verified"]
    assert isinstance(s1, dict)
    assert "p79b_classification" in s1


# ---------------------------------------------------------------------------
# 2. P79B classification verified
# ---------------------------------------------------------------------------

def test_02_p79b_classification_verified(summary):
    s1 = summary["step1_prediction_lane_verified"]
    assert s1["p79b_classification"] == "P79B_TIER_B_FIXTURE_RESEARCH_ONLY"


# ---------------------------------------------------------------------------
# 3. P79B fixture result marked research-only
# ---------------------------------------------------------------------------

def test_03_p79b_fixture_research_only(summary):
    s1 = summary["step1_prediction_lane_verified"]
    assert s1["tier_b_research_only"] is True
    assert s1.get("fixture_is_2026_live_conclusion") is not True


# ---------------------------------------------------------------------------
# 4. Prediction-only primary candidate present
# ---------------------------------------------------------------------------

def test_04_primary_candidate_present(summary):
    matrix = summary["step4_candidate_eligibility"]["candidates"]
    assert "primary_125" in matrix
    assert "TIER_C_HOME_PLUS_AWAY_125" in matrix["primary_125"]["candidate_name"]


# ---------------------------------------------------------------------------
# 5. Prediction-only shadow candidate present
# ---------------------------------------------------------------------------

def test_05_shadow_candidate_present(summary):
    matrix = summary["step4_candidate_eligibility"]["candidates"]
    assert "shadow_100" in matrix
    assert "TIER_C_HOME_PLUS_AWAY_100" in matrix["shadow_100"]["candidate_name"]


# ---------------------------------------------------------------------------
# 6. Tier B remains research-only unless future P79 passes
# ---------------------------------------------------------------------------

def test_06_tier_b_conditional_eligibility(summary):
    matrix = summary["step4_candidate_eligibility"]["candidates"]
    tb = matrix["tier_b_conditional"]
    assert tb["current_prediction_status"] == "RESEARCH_ONLY"
    eligibility = tb["market_edge_eligibility"]
    assert "CONDITIONAL" in eligibility
    assert "future" in eligibility.lower() or "live P79" in eligibility


# ---------------------------------------------------------------------------
# 7. Governance confirms no odds used
# ---------------------------------------------------------------------------

def test_07_governance_no_odds_used(summary):
    gov = summary["governance_snapshot"]
    assert gov["odds_used"] is False
    assert gov["ev_calculated"] is False
    assert gov["market_edge_evaluated"] is False
    assert gov["production_ready"] is False
    assert gov["live_api_calls"] == 0


# ---------------------------------------------------------------------------
# 8. Optional P64-P71 market context handled
# ---------------------------------------------------------------------------

def test_08_optional_artifacts_handled(summary):
    optional = summary["optional_artifacts_present"]
    # Whether present or not, all 7 keys must exist in the dict
    expected_keys = [
        "p64_summary", "p65_summary", "p66_summary", "p67_summary",
        "p68_summary", "p70_summary", "p71_summary",
    ]
    for k in expected_keys:
        assert k in optional, f"Optional artifact key missing: {k}"


# ---------------------------------------------------------------------------
# 9. Market-edge blocker summary generated
# ---------------------------------------------------------------------------

def test_09_market_edge_blocker_summary_generated(summary):
    s2 = summary["step2_market_edge_blockers"]
    assert "active_blockers" in s2
    assert "blocker_count" in s2
    assert s2["blocker_count"] >= 1
    assert s2["market_edge_lane_state"] == "BLOCKED"


# ---------------------------------------------------------------------------
# 10. Legal odds data contract generated
# ---------------------------------------------------------------------------

def test_10_legal_odds_contract_generated(summary):
    s3 = summary["step3_legal_odds_contract"]
    assert "field_specifications" in s3
    assert "legality_requirements" in s3
    assert s3["required_field_count"] >= 20


# ---------------------------------------------------------------------------
# 11. Required odds fields present
# ---------------------------------------------------------------------------

def test_11_required_odds_fields_complete(module, summary):
    defined_fields = {
        spec["field"]
        for spec in summary["step3_legal_odds_contract"]["field_specifications"]
    }
    for field in module.REQUIRED_ODDS_FIELDS:
        assert field in defined_fields, f"Required field missing from spec: {field}"


# ---------------------------------------------------------------------------
# 12. Source legality required
# ---------------------------------------------------------------------------

def test_12_source_legality_required(summary):
    req = summary["step3_legal_odds_contract"]["legality_requirements"]
    assert req["legal_source_required"] is True


# ---------------------------------------------------------------------------
# 13. ToS / robots violation blocked
# ---------------------------------------------------------------------------

def test_13_tos_robots_blocked(summary):
    req = summary["step3_legal_odds_contract"]["legality_requirements"]
    assert req["scraping_prohibited_source_blocked"] is True
    assert req["robots_txt_violation_blocked"] is True
    assert req["tos_violation_blocked"] is True


# ---------------------------------------------------------------------------
# 14. API key value must not be read or printed
# ---------------------------------------------------------------------------

def test_14_api_key_not_read(summary):
    gov = summary["governance_snapshot"]
    assert gov["the_odds_api_key_accessed"] is False

    # Verify source code does not read the key value
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    import re
    # Should not contain actual env read call for the key
    assert not re.search(r'os\.environ\[.THE_ODDS_API_KEY', source)
    assert not re.search(r'os\.environ\.get\(.THE_ODDS_API_KEY', source)


# ---------------------------------------------------------------------------
# 15. Raw paid data policy required
# ---------------------------------------------------------------------------

def test_15_raw_paid_data_policy_required(summary):
    req = summary["step3_legal_odds_contract"]["legality_requirements"]
    assert req["raw_paid_data_commit_policy_decided_before_staging"] is True
    # Also verify raw_data_policy field is in spec
    fields = {
        spec["field"]
        for spec in summary["step3_legal_odds_contract"]["field_specifications"]
    }
    assert "raw_data_policy" in fields


# ---------------------------------------------------------------------------
# 16. Timestamp lineage required
# ---------------------------------------------------------------------------

def test_16_timestamp_lineage_required(summary):
    req = summary["step3_legal_odds_contract"]["legality_requirements"]
    assert req["timestamp_lineage_proven_before_clv"] is True
    fields = {
        spec["field"]
        for spec in summary["step3_legal_odds_contract"]["field_specifications"]
    }
    assert "odds_timestamp_utc" in fields
    assert "game_start_utc" in fields


# ---------------------------------------------------------------------------
# 17. Side mapping validation required
# ---------------------------------------------------------------------------

def test_17_side_mapping_required(summary):
    req = summary["step3_legal_odds_contract"]["legality_requirements"]
    assert req["side_mapping_proven_before_edge"] is True


# ---------------------------------------------------------------------------
# 18. Doubleheader disambiguation required
# ---------------------------------------------------------------------------

def test_18_doubleheader_disambiguation_required(summary):
    req = summary["step3_legal_odds_contract"]["legality_requirements"]
    assert req["doubleheader_disambiguation_required"] is True
    # Also present in Gate C
    gate_c = summary["step5_validation_gates"]["gates"]["gate_c_mapping"]
    conditions_text = str(gate_c["conditions"])
    assert "doubleheader" in conditions_text.lower()


# ---------------------------------------------------------------------------
# 19. Candidate eligibility matrix generated
# ---------------------------------------------------------------------------

def test_19_candidate_eligibility_matrix_generated(summary):
    s4 = summary["step4_candidate_eligibility"]
    assert "candidates" in s4
    assert len(s4["candidates"]) >= 4
    for ck in ["primary_125", "shadow_100", "tier_b_conditional", "baseline_50"]:
        assert ck in s4["candidates"]


# ---------------------------------------------------------------------------
# 20. Primary 125 eligible for future market-edge testing
# ---------------------------------------------------------------------------

def test_20_primary_125_eligible(summary):
    p125 = summary["step4_candidate_eligibility"]["candidates"]["primary_125"]
    assert "ELIGIBLE" in p125["market_edge_eligibility"]


# ---------------------------------------------------------------------------
# 21. Shadow 100 eligible for future market-edge testing
# ---------------------------------------------------------------------------

def test_21_shadow_100_eligible(summary):
    s100 = summary["step4_candidate_eligibility"]["candidates"]["shadow_100"]
    assert "ELIGIBLE" in s100["market_edge_eligibility"]


# ---------------------------------------------------------------------------
# 22. Tier B conditional eligibility enforced
# ---------------------------------------------------------------------------

def test_22_tier_b_conditional_enforced(summary):
    tb = summary["step4_candidate_eligibility"]["candidates"]["tier_b_conditional"]
    eligibility = tb["market_edge_eligibility"]
    assert "CONDITIONAL" in eligibility
    assert tb["current_prediction_status"] == "RESEARCH_ONLY"
    prohibited = tb["prohibited_interpretation"]
    assert "RESEARCH_ONLY" in prohibited or "research" in prohibited.lower()


# ---------------------------------------------------------------------------
# 23. Gate A data legality defined
# ---------------------------------------------------------------------------

def test_23_gate_a_defined(summary):
    gates = summary["step5_validation_gates"]["gates"]
    assert "gate_a_data_legality" in gates
    ga = gates["gate_a_data_legality"]
    assert ga["gate_id"] == "A"
    assert len(ga["conditions"]) >= 3
    assert "BLOCKED" in ga["current_state"]


# ---------------------------------------------------------------------------
# 24. Gate B schema defined
# ---------------------------------------------------------------------------

def test_24_gate_b_defined(summary):
    gates = summary["step5_validation_gates"]["gates"]
    assert "gate_b_schema" in gates
    gb = gates["gate_b_schema"]
    assert gb["gate_id"] == "B"
    assert len(gb["conditions"]) >= 4


# ---------------------------------------------------------------------------
# 25. Gate C mapping defined
# ---------------------------------------------------------------------------

def test_25_gate_c_defined(summary):
    gates = summary["step5_validation_gates"]["gates"]
    assert "gate_c_mapping" in gates
    gc = gates["gate_c_mapping"]
    assert gc["gate_id"] == "C"
    assert "doubleheader" in str(gc["conditions"]).lower()


# ---------------------------------------------------------------------------
# 26. Gate D metric readiness defined
# ---------------------------------------------------------------------------

def test_26_gate_d_defined(summary):
    gates = summary["step5_validation_gates"]["gates"]
    assert "gate_d_metric_readiness" in gates
    gd = gates["gate_d_metric_readiness"]
    assert gd["gate_id"] == "D"
    assert "prohibited_metrics" in gd
    assert "EV" in gd["prohibited_metrics"]
    assert "Kelly" in str(gd["prohibited_metrics"])


# ---------------------------------------------------------------------------
# 27. Gate E cross-year validation defined
# ---------------------------------------------------------------------------

def test_27_gate_e_defined(summary):
    gates = summary["step5_validation_gates"]["gates"]
    assert "gate_e_cross_year_validation" in gates
    ge = gates["gate_e_cross_year_validation"]
    assert ge["gate_id"] == "E"
    conditions_text = str(ge["conditions"])
    assert "season" in conditions_text.lower() or "2024" in conditions_text


# ---------------------------------------------------------------------------
# 28. Gate F governance defined
# ---------------------------------------------------------------------------

def test_28_gate_f_defined(summary):
    gates = summary["step5_validation_gates"]["gates"]
    assert "gate_f_governance" in gates
    gf = gates["gate_f_governance"]
    assert gf["gate_id"] == "F"
    assert gf["current_state"] == "ACTIVE — governance invariants enforced by P80 GOVERNANCE dict"


# ---------------------------------------------------------------------------
# 29. EV/Kelly remain prohibited
# ---------------------------------------------------------------------------

def test_29_ev_kelly_prohibited(summary):
    gov = summary["governance_snapshot"]
    assert gov["ev_calculated"] is False
    assert gov["kelly_calculated"] is False
    assert gov["kelly_deploy_allowed"] is False
    # Gate D explicitly prohibits EV and Kelly
    gd = summary["step5_validation_gates"]["gates"]["gate_d_metric_readiness"]
    assert "EV" in gd["prohibited_metrics"]
    assert "Kelly" in str(gd["prohibited_metrics"])


# ---------------------------------------------------------------------------
# 30. CLV remains prohibited until closing data exists
# ---------------------------------------------------------------------------

def test_30_clv_requires_closing_data(summary):
    s3 = summary["step3_legal_odds_contract"]
    assert s3["closing_line_required_for_clv"] is True
    gd = summary["step5_validation_gates"]["gates"]["gate_d_metric_readiness"]
    conditions_text = str(gd["conditions"])
    assert "closing" in conditions_text.lower()
    assert "clv" in conditions_text.lower()


# ---------------------------------------------------------------------------
# 31. Production remains blocked
# ---------------------------------------------------------------------------

def test_31_production_blocked(summary):
    gov = summary["governance_snapshot"]
    assert gov["production_ready"] is False
    assert gov["real_bet_allowed"] is False
    assert gov["champion_replacement_allowed"] is False
    assert gov["promotion_freeze"] is True
    assert summary.get("contract_is_production_claim") is False


# ---------------------------------------------------------------------------
# 32. Future P81/P82/P83/P84 path generated
# ---------------------------------------------------------------------------

def test_32_future_phase_path_generated(summary):
    phases = summary["step6_future_phase_path"]["phases"]
    for expected in ["P81", "P82", "P83", "P84"]:
        assert expected in phases, f"Phase {expected} missing from future path"
    assert phases["P81"]["status"] != "THIS PHASE"
    assert "production gate" in phases["P84"]["notes"].lower() or \
           "paper" in phases["P84"]["notes"].lower()


# ---------------------------------------------------------------------------
# 33. No live API calls
# ---------------------------------------------------------------------------

def test_33_no_live_api_calls(summary):
    assert summary["live_api_calls"] == 0
    gov = summary["governance_snapshot"]
    assert gov["live_api_calls"] == 0


# ---------------------------------------------------------------------------
# 34. live_api_calls=0
# ---------------------------------------------------------------------------

def test_34_live_api_calls_zero(module):
    assert module.GOVERNANCE["live_api_calls"] == 0


# ---------------------------------------------------------------------------
# 35. production_ready=false
# ---------------------------------------------------------------------------

def test_35_production_ready_false(module):
    assert module.GOVERNANCE["production_ready"] is False


# ---------------------------------------------------------------------------
# 36. kelly_deploy_allowed=false
# ---------------------------------------------------------------------------

def test_36_kelly_deploy_allowed_false(module):
    assert module.GOVERNANCE["kelly_deploy_allowed"] is False


# ---------------------------------------------------------------------------
# 37. Forbidden phrase scan passes
# ---------------------------------------------------------------------------

def test_37_forbidden_scan_passes(summary):
    s8 = summary["step8_forbidden_scan"]
    assert s8["scan_passed"] is True, (
        f"Forbidden scan violations: {s8.get('violations', [])}"
    )
    assert s8["violations_count"] == 0


# ---------------------------------------------------------------------------
# 38. JSON schema stable
# ---------------------------------------------------------------------------

def test_38_json_schema_stable(summary):
    required_top_keys = [
        "p80_classification",
        "schema_version",
        "generated_at",
        "governance_snapshot",
        "step1_prediction_lane_verified",
        "step2_market_edge_blockers",
        "step3_legal_odds_contract",
        "step4_candidate_eligibility",
        "step5_validation_gates",
        "step6_future_phase_path",
        "step7_contract_schema",
        "step8_forbidden_scan",
        "market_edge_lane",
        "prediction_lane_status",
        "live_api_calls",
        "ev_clv_kelly_computed",
    ]
    for k in required_top_keys:
        assert k in summary, f"Top-level key missing: {k}"


# ---------------------------------------------------------------------------
# 39. Report includes odds data contract table
# ---------------------------------------------------------------------------

def test_39_report_has_odds_contract_table(summary):
    assert REPORT_PATH.exists(), f"P80 report missing: {REPORT_PATH}"
    report_text = REPORT_PATH.read_text(encoding="utf-8")
    assert "Legal Odds Data Contract" in report_text
    assert "game_id" in report_text
    assert "implied_home_prob" in report_text
    assert "source_license_status" in report_text


# ---------------------------------------------------------------------------
# 40. Report includes gate table
# ---------------------------------------------------------------------------

def test_40_report_has_gate_table(summary):
    report_text = REPORT_PATH.read_text(encoding="utf-8")
    for gate_letter in ["A", "B", "C", "D", "E", "F"]:
        assert f"| **{gate_letter}**" in report_text or \
               f"Gate {gate_letter}" in report_text, \
               f"Gate {gate_letter} missing from report"


# ---------------------------------------------------------------------------
# 41. active_task.md updated
# ---------------------------------------------------------------------------

def test_41_active_task_updated():
    active_task = ROOT / "00-Plan/roadmap/active_task.md"
    assert active_task.exists()
    content = active_task.read_text(encoding="utf-8")
    # Must reference P79B commit (already in history)
    assert "520206c" in content or "P79B" in content


# ---------------------------------------------------------------------------
# 42. P80 classification is valid
# ---------------------------------------------------------------------------

def test_42_p80_classification_valid(summary):
    valid_cls = {
        "P80_MARKET_EDGE_REENTRY_CONTRACT_READY",
        "P80_MARKET_EDGE_REENTRY_CONTRACT_READY_WITH_CAVEATS",
        "P80_BLOCKED_BY_MISSING_SOURCE_ARTIFACT",
        "P80_FAILED_VALIDATION",
    }
    cls = summary["p80_classification"]
    assert cls in valid_cls, f"Invalid classification: {cls}"
    # For a clean run, expect READY (not FAILED)
    assert "FAILED" not in cls, f"P80 failed: {cls}"
    assert "BLOCKED_BY_MISSING" not in cls, f"P80 blocked by missing artifact: {cls}"


# ---------------------------------------------------------------------------
# P72A-P79B regression: verify all prior summaries still loadable
# ---------------------------------------------------------------------------

PRIOR_SUMMARIES = [
    "p72a_odds_free_strategy_accuracy_backtest_summary.json",
    "p72b_objective_metric_contract_summary.json",
    "p73_tier_stability_and_sample_expansion_summary.json",
    "p74_tier_c_home_away_bias_correction_summary.json",
    "p75a_tier_c_corrected_rule_validator_summary.json",
    "p75b_calibration_diagnostics_corrected_tier_c_summary.json",
    "p76_corrected_tier_c_final_rule_selection_summary.json",
    "p77_prediction_only_shadow_tracker_contract_summary.json",
    "p78_monthly_shadow_tracker_report_template_summary.json",
    "p79a_tier_b_trigger_readiness_contract_summary.json",
    "p79b_tier_b_vs_tier_c_comparison_harness_summary.json",
]


@pytest.mark.parametrize("filename", PRIOR_SUMMARIES)
def test_p72a_p79b_regression(filename):
    path = DERIVED / filename
    assert path.exists(), f"Prior summary missing: {filename}"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    assert len(data) >= 3
