"""
P54 test suite — Sep 2025 SP FIP Delta Feature Drift Audit
18 tests covering all governance, data, and output requirements.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent

P53_JSON = REPO_ROOT / "data/mlb_2025/derived/p53_sep_calibration_critical_audit_summary.json"
P54_JSON = REPO_ROOT / "data/mlb_2025/derived/p54_sep_sp_fip_delta_feature_drift_audit_summary.json"
P52_JSON = REPO_ROOT / "data/mlb_2025/derived/p52_monitoring_contract_v2_summary.json"
P54_REPORT = REPO_ROOT / "report/p54_sep_sp_fip_delta_feature_drift_audit_20260526.md"
P54_BPLAN = REPO_ROOT / "00-BettingPlan/20260526/p54_sep_sp_fip_delta_feature_drift_audit_20260526.md"
ACTIVE_TASK = REPO_ROOT / "00-Plan/roadmap/active_task.md"
JSONL_PATH = REPO_ROOT / "data/mlb_2025/derived/mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl"

PLATT_A_EXPECTED = 0.435432
PLATT_B_EXPECTED = 0.245464

VALID_CLASSIFICATIONS = {
    "P54_SEP_FEATURE_DRIFT_CONFIRMED_DIAGNOSTIC",
    "P54_SEP_EXTREME_DELTA_CONCENTRATION_DIAGNOSTIC",
    "P54_SEP_SIDE_COMPOSITION_SHIFT_DIAGNOSTIC",
    "P54_NO_FEATURE_DRIFT_FOUND_DIAGNOSTIC",
    "P54_INCONCLUSIVE_SAMPLE_LIMITED",
}

EXPECTED_BANDS = {"0.50_0.75", "0.75_1.00", "1.00_1.25", "1.25_1.50", "1.50_plus"}
DEPLOYMENT_FORBIDDEN = [
    "DEPLOYMENT_READY",
    "PRODUCTION_READY",
    "approved for production deployment",
    "ready for production deployment",
    "deploy to production",
    "production deployment approved",
]


@pytest.fixture(scope="module")
def p54_data() -> dict:
    assert P54_JSON.exists(), f"P54 JSON not found: {P54_JSON}"
    return json.loads(P54_JSON.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def p53_data() -> dict:
    assert P53_JSON.exists(), f"P53 JSON not found: {P53_JSON}"
    return json.loads(P53_JSON.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# T01 — P53 source artifact exists and is loaded
# ---------------------------------------------------------------------------
def test_t01_p53_source_artifact_exists_and_loaded(p53_data, p54_data):
    """T01: P53 artifact exists and P54 recap references it."""
    assert P53_JSON.exists(), "P53 JSON must exist"
    p53_recap = p54_data.get("p53_recap", {})
    assert p53_recap.get("classification") == "SEP_CALIBRATION_SAMPLE_SENSITIVE_DIAGNOSTIC", (
        "P54 must reference P53 classification"
    )
    assert p53_recap.get("sep_n") == 98
    assert p53_recap.get("sep_platt_ece") == pytest.approx(0.122929, abs=1e-4)


# ---------------------------------------------------------------------------
# T02 — Tier C row count == 535
# ---------------------------------------------------------------------------
def test_t02_tier_c_row_count(p54_data):
    """T02: Tier C n=535."""
    assert p54_data["tier_c_verification"]["n"] == 535


# ---------------------------------------------------------------------------
# T03 — Sep subset exists and n is recorded
# ---------------------------------------------------------------------------
def test_t03_sep_subset_recorded(p54_data):
    """T03: Sep 2025 subset exists and n > 0."""
    sep_metrics = p54_data.get("sep_2025_metrics", {})
    assert "n" in sep_metrics
    sep_n = sep_metrics["n"]
    assert sep_n > 0, "Sep subset must not be empty"
    assert sep_n == 98, f"Expected Sep n=98, got {sep_n}"


# ---------------------------------------------------------------------------
# T04 — Platt constants match P45 and are not modified
# ---------------------------------------------------------------------------
def test_t04_platt_constants_not_modified(p54_data):
    """T04: Platt constants match P45 locked values."""
    consts = p54_data.get("platt_constants", {})
    assert consts.get("PLATT_A") == pytest.approx(PLATT_A_EXPECTED, abs=1e-6)
    assert consts.get("PLATT_B") == pytest.approx(PLATT_B_EXPECTED, abs=1e-6)
    assert consts.get("modified") is False
    assert p54_data["governance_flags"]["platt_constants_modified"] is False


# ---------------------------------------------------------------------------
# T05 — Monthly distribution includes Sep and at least May/Jun/Aug
# ---------------------------------------------------------------------------
def test_t05_monthly_distribution_completeness(p54_data):
    """T05: Monthly FIP distribution contains Sep, May, Jun, Aug."""
    monthly = p54_data.get("monthly_fip_distribution", {})
    required = {"Sep", "May", "Jun", "Aug"}
    missing = required - set(monthly.keys())
    assert not missing, f"Missing monthly periods: {missing}"
    # each period has n > 0
    for period in required:
        assert monthly[period]["n"] > 0, f"{period} n must be > 0"


# ---------------------------------------------------------------------------
# T06 — FIP delta band audit contains all five bands
# ---------------------------------------------------------------------------
def test_t06_fip_band_audit_five_bands(p54_data):
    """T06: calibration_by_fip_band contains all 5 expected bands for full_tier_c."""
    bands = p54_data.get("calibration_by_fip_band", {})
    assert "full_tier_c" in bands, "full_tier_c period must be in band audit"
    full_bands = set(bands["full_tier_c"].keys())
    missing = EXPECTED_BANDS - full_bands
    assert not missing, f"Missing FIP bands in full_tier_c: {missing}"
    assert "Sep" in bands, "Sep period must be in band audit"
    sep_bands = set(bands["Sep"].keys())
    missing_sep = EXPECTED_BANDS - sep_bands
    assert not missing_sep, f"Missing FIP bands in Sep: {missing_sep}"


# ---------------------------------------------------------------------------
# T07 — Calibration by band includes raw_ece and platt_ece
# ---------------------------------------------------------------------------
def test_t07_calibration_by_band_has_ece_fields(p54_data):
    """T07: Each non-empty band has raw_ece and platt_ece."""
    bands = p54_data.get("calibration_by_fip_band", {})
    for period in ["full_tier_c", "Sep"]:
        for band_key, band_data in bands[period].items():
            if band_data.get("n", 0) > 0:
                assert "raw_ece" in band_data, f"{period}/{band_key} missing raw_ece"
                assert "platt_ece" in band_data, f"{period}/{band_key} missing platt_ece"
                assert isinstance(band_data["platt_ece"], float), "platt_ece must be float"


# ---------------------------------------------------------------------------
# T08 — Statistical comparison contains KS statistics
# ---------------------------------------------------------------------------
def test_t08_statistical_comparison_ks_statistics(p54_data):
    """T08: statistical_comparison contains KS stats for Sep vs May/Jun/Jul/Aug/Full."""
    sc = p54_data.get("statistical_comparison", {})
    required_keys = {"sep_vs_may", "sep_vs_jun", "sep_vs_aug", "sep_vs_full_tier_c"}
    missing = required_keys - set(sc.keys())
    assert not missing, f"Missing comparison keys: {missing}"
    for key in required_keys:
        ks = sc[key].get("ks_statistic")
        assert ks is not None, f"{key} missing ks_statistic"
        assert isinstance(ks, float), f"{key} ks_statistic must be float"
        assert 0.0 <= ks <= 1.0, f"{key} KS out of [0,1]: {ks}"


# ---------------------------------------------------------------------------
# T09 — Side/outcome composition section exists
# ---------------------------------------------------------------------------
def test_t09_side_composition_section_exists(p54_data):
    """T09: side_outcome_composition section exists with Sep and full_tier_c."""
    side = p54_data.get("side_outcome_composition", {})
    assert "Sep" in side, "Sep must be in side composition"
    assert "full_tier_c" in side, "full_tier_c must be in side composition"
    sep_side = side["Sep"]
    assert "n" in sep_side
    assert sep_side["n"] > 0
    # at least some expected fields
    for field in ["home_selected_rate", "home_win_rate", "selected_side_win_rate"]:
        assert field in sep_side, f"Sep side missing field: {field}"


# ---------------------------------------------------------------------------
# T10 — Governance flags exist and match required values
# ---------------------------------------------------------------------------
def test_t10_governance_flags_correct(p54_data):
    """T10: All governance flags match required values."""
    gf = p54_data.get("governance_flags", {})
    assert gf.get("paper_only") is True
    assert gf.get("diagnostic_only") is True
    assert gf.get("promotion_freeze") is True
    assert gf.get("kelly_deploy_allowed") is False
    assert gf.get("tsl_crawler_modified") is False
    assert gf.get("champion_strategy_changed") is False
    assert gf.get("production_usage_proposed") is False
    assert gf.get("runtime_recommendation_logic_changed") is False
    assert gf.get("platt_constants_modified") is False
    assert gf.get("p52_contract_overwritten") is False
    assert gf.get("p53_artifact_overwritten") is False


# ---------------------------------------------------------------------------
# T11 — live_api_calls == 0
# ---------------------------------------------------------------------------
def test_t11_live_api_calls_zero(p54_data):
    """T11: live_api_calls must be exactly 0."""
    assert p54_data["governance_flags"]["live_api_calls"] == 0


# ---------------------------------------------------------------------------
# T12 — runtime_recommendation_logic_changed == False
# ---------------------------------------------------------------------------
def test_t12_runtime_logic_unchanged(p54_data):
    """T12: runtime_recommendation_logic_changed is False."""
    assert p54_data["governance_flags"]["runtime_recommendation_logic_changed"] is False


# ---------------------------------------------------------------------------
# T13 — platt_constants_modified == False
# ---------------------------------------------------------------------------
def test_t13_platt_constants_not_modified_flag(p54_data):
    """T13: platt_constants_modified governance flag is False."""
    assert p54_data["governance_flags"]["platt_constants_modified"] is False


# ---------------------------------------------------------------------------
# T14 — p52_contract_overwritten == False
# ---------------------------------------------------------------------------
def test_t14_p52_contract_not_overwritten(p54_data):
    """T14: p52_contract_overwritten is False; P52 JSON still exists."""
    assert p54_data["governance_flags"]["p52_contract_overwritten"] is False
    assert P52_JSON.exists(), "P52 JSON artifact must still exist"


# ---------------------------------------------------------------------------
# T15 — p53_artifact_overwritten == False
# ---------------------------------------------------------------------------
def test_t15_p53_artifact_not_overwritten(p54_data):
    """T15: p53_artifact_overwritten is False; P53 JSON still exists with original classification."""
    assert p54_data["governance_flags"]["p53_artifact_overwritten"] is False
    assert P53_JSON.exists(), "P53 JSON artifact must still exist"
    p53 = json.loads(P53_JSON.read_text(encoding="utf-8"))
    assert p53.get("final_p53_classification") == "SEP_CALIBRATION_SAMPLE_SENSITIVE_DIAGNOSTIC", (
        "P53 classification must be unchanged"
    )


# ---------------------------------------------------------------------------
# T16 — JSON output contains no deployment-readiness classification
# ---------------------------------------------------------------------------
def test_t16_no_deployment_classification(p54_data):
    """T16: final_p54_classification must be one of the allowed diagnostic values."""
    cls = p54_data.get("final_p54_classification", "")
    assert cls in VALID_CLASSIFICATIONS, (
        f"Invalid classification: {cls}. Must be one of {VALID_CLASSIFICATIONS}"
    )
    # must not contain deployment-readiness language
    for forbidden in ["DEPLOYMENT_READY", "PRODUCTION_READY", "CHAMPION_PROMOTED"]:
        assert forbidden not in cls, f"Forbidden string in classification: {forbidden}"


# ---------------------------------------------------------------------------
# T17 — Reports contain no affirmative production or profit claims
# ---------------------------------------------------------------------------
def test_t17_reports_no_affirmative_production_profit_claims():
    """T17: Reports must not contain affirmative deployment/profit claims."""
    assert P54_REPORT.exists(), "P54 report must exist"
    report_text = P54_REPORT.read_text(encoding="utf-8")
    for forbidden in DEPLOYMENT_FORBIDDEN:
        assert forbidden not in report_text, (
            f"Forbidden phrase '{forbidden}' found in P54 report"
        )
    # also check no profit claims
    profit_forbidden = ["guaranteed profit", "expected profit confirmed", "profit-guaranteed"]
    for phrase in profit_forbidden:
        assert phrase.lower() not in report_text.lower(), (
            f"Forbidden profit claim '{phrase}' found in report"
        )


# ---------------------------------------------------------------------------
# T18 — active_task.md references final P54 classification
# ---------------------------------------------------------------------------
def test_t18_active_task_references_p54_classification(p54_data):
    """T18: active_task.md must reference the P54 classification."""
    assert ACTIVE_TASK.exists(), "active_task.md must exist"
    content = ACTIVE_TASK.read_text(encoding="utf-8")
    cls = p54_data.get("final_p54_classification", "")
    assert cls in content, (
        f"active_task.md must reference classification '{cls}'"
    )
    assert "P54" in content, "active_task.md must reference P54"
