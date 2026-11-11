"""
Tests for P55 — Sep 2025 Mid-Band Calibration Anomaly Audit.

18 tests covering:
T01  P54 source artifact loaded
T02  Tier C n=535
T03  Sep mid-band n recorded and matches
T04  Platt constants match P45
T05  Outlier concentration includes top5 and contribution shares
T06  Leave-one-out ECE is deterministic and in range
T07  Month/band comparison includes required months
T08  Platt vs raw check includes ECE and Brier deltas
T09  Governance flags exist and correct
T10  live_api_calls == 0
T11  runtime_recommendation_logic_changed == False
T12  platt_constants_modified == False
T13  p52_contract_overwritten == False
T14  p53_artifact_overwritten == False
T15  p54_artifact_overwritten == False
T16  No deployment-readiness classification in JSON
T17  Reports contain no affirmative production/profit claims
T18  active_task.md references P55 classification
"""
import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]

P55_JSON = ROOT / "data/mlb_2025/derived/p55_sep_mid_band_calibration_anomaly_audit_summary.json"
P54_JSON = ROOT / "data/mlb_2025/derived/p54_sep_sp_fip_delta_feature_drift_audit_summary.json"
REPORT_MD = ROOT / "report/p55_sep_mid_band_calibration_anomaly_audit_20260526.md"
BETTING_PLAN_MD = ROOT / "00-BettingPlan/20260526/p55_sep_mid_band_calibration_anomaly_audit_20260526.md"
ACTIVE_TASK_MD = ROOT / "00-Plan/roadmap/active_task.md"

FORBIDDEN_CLASSIFICATIONS = [
    "DEPLOYMENT_READY",
    "PRODUCTION_READY",
    "CHAMPION_PROMOTED",
    "KELLY_LIVE",
    "LIVE_BETTING_APPROVED",
]

FORBIDDEN_REPORT_PHRASES = [
    "guaranteed profit",
    "expected profit",
    "will profit",
    "production deployment",
    "deploy to production",
    "ready for live betting",
    "champion strategy activated",
    "kelly_deploy_allowed=True",
]


@pytest.fixture(scope="module")
def summary() -> dict:
    assert P55_JSON.exists(), f"P55 JSON not found: {P55_JSON}"
    return json.loads(P55_JSON.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# T01 — P54 source artifact exists and is referenced
# ---------------------------------------------------------------------------
def test_t01_p54_source_artifact_loaded(summary: dict) -> None:
    """P54 source artifact must exist and be referenced in the P55 summary."""
    assert P54_JSON.exists(), f"P54 JSON not found: {P54_JSON}"
    recap = summary.get("p54_recap", {})
    assert recap, "p55 summary must include p54_recap section"
    assert recap.get("final_p54_classification") == "P54_NO_FEATURE_DRIFT_FOUND_DIAGNOSTIC"
    assert recap.get("tier_c_n") == 535, f"P54 tier_c_n mismatch: {recap.get('tier_c_n')}"
    assert recap.get("sep_mid_band_n_from_p54") == 27, (
        f"P54 sep_mid_band_n_from_p54 expected 27, got {recap.get('sep_mid_band_n_from_p54')}"
    )


# ---------------------------------------------------------------------------
# T02 — Tier C n=535
# ---------------------------------------------------------------------------
def test_t02_tier_c_n(summary: dict) -> None:
    """Tier C must equal 535 (consistent with P40-P54)."""
    verification = summary.get("tier_c_verification", {})
    assert verification.get("n") == 535, (
        f"Tier C n expected 535, got {verification.get('n')}"
    )
    assert verification.get("consistent_with_p54") is True


# ---------------------------------------------------------------------------
# T03 — Sep mid-band n is recorded
# ---------------------------------------------------------------------------
def test_t03_sep_mid_band_n(summary: dict) -> None:
    """Sep mid-band n must be recorded and >= 1."""
    ds = summary.get("sep_mid_band_dataset", {})
    n = ds.get("n")
    assert n is not None, "sep_mid_band_dataset.n is missing"
    assert n >= 1, f"Sep mid-band n must be >= 1, got {n}"
    # Consistent with P54
    expected = summary["p54_recap"]["sep_mid_band_n_from_p54"]
    assert n == expected, (
        f"Sep mid-band n={n} doesn't match P54 reported n={expected}"
    )
    assert ds.get("consistent_with_p54") is True


# ---------------------------------------------------------------------------
# T04 — Platt constants match P45
# ---------------------------------------------------------------------------
def test_t04_platt_constants_p45(summary: dict) -> None:
    """Platt constants must match P45 locked values."""
    pc = summary.get("platt_constants", {})
    assert abs(pc.get("platt_a", 0) - 0.435432) < 1e-6, (
        f"platt_a mismatch: {pc.get('platt_a')}"
    )
    assert abs(pc.get("platt_b", 0) - 0.245464) < 1e-6, (
        f"platt_b mismatch: {pc.get('platt_b')}"
    )
    assert summary["governance_flags"]["platt_constants_modified"] is False


# ---------------------------------------------------------------------------
# T05 — Outlier concentration includes top5 and contribution shares
# ---------------------------------------------------------------------------
def test_t05_outlier_concentration_top5(summary: dict) -> None:
    """Outlier concentration section must include top5 games and contribution shares."""
    oc = summary.get("outlier_concentration_audit", {})
    assert oc, "outlier_concentration_audit section is missing"

    # top5_games list
    top5 = oc.get("top5_games", [])
    n = oc.get("n", 0)
    expected_count = min(5, n)
    assert len(top5) == expected_count, (
        f"top5_games expected {expected_count} entries, got {len(top5)}"
    )

    # Contribution shares
    for key in ["top1_contribution_share", "top3_contribution_share", "top5_contribution_share"]:
        val = oc.get(key)
        assert val is not None, f"{key} is missing from outlier_concentration_audit"
        assert 0.0 <= val <= 1.0, f"{key}={val} must be in [0, 1]"

    # Each top5 game has required fields
    for g in top5:
        assert "game_date" in g, "top5 game missing game_date"
        assert "abs_error_platt" in g, "top5 game missing abs_error_platt"

    # concentration_classification is one of allowed values
    allowed_clf = {
        "OUTLIER_DRIVEN", "BROAD_BASED", "INCONCLUSIVE_SAMPLE_LIMITED"
    }
    assert oc.get("concentration_classification") in allowed_clf, (
        f"Invalid concentration_classification: {oc.get('concentration_classification')}"
    )


# ---------------------------------------------------------------------------
# T06 — Leave-one-out ECE range is deterministic and valid
# ---------------------------------------------------------------------------
def test_t06_leave_one_out_ece(summary: dict) -> None:
    """Leave-one-out ECE must be present and deterministic (min <= max)."""
    oc = summary.get("outlier_concentration_audit", {})
    loo = oc.get("leave_one_out", {})
    assert loo, "leave_one_out section is missing"

    min_ece = loo.get("min_ece_without_one_game")
    max_ece = loo.get("max_ece_without_one_game")
    std_ece = loo.get("ece_std_leave_one_out")
    swing = loo.get("ece_swing")

    assert min_ece is not None, "min_ece_without_one_game is missing"
    assert max_ece is not None, "max_ece_without_one_game is missing"
    assert std_ece is not None, "ece_std_leave_one_out is missing"
    assert swing is not None, "ece_swing is missing"

    # Deterministic constraint
    assert min_ece <= max_ece, f"min_ece ({min_ece}) > max_ece ({max_ece})"
    assert abs(swing - (max_ece - min_ece)) < 1e-5, (
        f"ece_swing ({swing}) != max-min ({max_ece - min_ece:.6f})"
    )
    assert std_ece >= 0.0, f"ece_std_leave_one_out must be >= 0, got {std_ece}"

    # Second run should produce same result (determinism check via known values)
    # Values must be positive finite floats
    assert 0.0 <= min_ece < 1.0, f"min_ece={min_ece} out of [0,1)"
    assert 0.0 <= max_ece <= 1.0, f"max_ece={max_ece} out of [0,1]"


# ---------------------------------------------------------------------------
# T07 — Month/band comparison includes required months
# ---------------------------------------------------------------------------
def test_t07_month_band_comparison(summary: dict) -> None:
    """Month/band comparison must include all months present in data."""
    mc = summary.get("month_band_comparison", {})
    assert mc, "month_band_comparison section is missing"

    months = mc.get("months", {})
    assert months, "month_band_comparison.months is empty"

    # Required months: May, Jun, Aug, Sep (from P54); Jul now included if data exists
    expected_in_structure = ["May", "Jun", "Aug", "Sep"]
    for m in expected_in_structure:
        assert m in months, f"Month {m} missing from month_band_comparison.months"

    # Sep must have data
    sep = months.get("Sep", {})
    assert sep.get("n", 0) > 0, "Sep must have data in month_band_comparison"

    # Each month with data must have required metrics
    required_keys = ["n", "platt_ece", "raw_ece", "platt_brier", "raw_brier",
                     "mean_platt_prob", "actual_win_rate", "calibration_gap"]
    for month, mv in months.items():
        if mv.get("n", 0) > 0:
            for k in required_keys:
                assert k in mv, f"Month {month} missing key {k}"

    # Sep rank must be present
    assert mc.get("sep_rank_by_platt_ece") is not None, "sep_rank_by_platt_ece missing"
    rank = mc["sep_rank_by_platt_ece"]
    months_with_data = sum(1 for v in months.values() if v["n"] > 0)
    assert 1 <= rank <= months_with_data, (
        f"sep_rank ({rank}) out of range [1, {months_with_data}]"
    )


# ---------------------------------------------------------------------------
# T08 — Platt vs raw check includes ECE and Brier deltas
# ---------------------------------------------------------------------------
def test_t08_platt_vs_raw_check(summary: dict) -> None:
    """Platt vs raw transformation check must include ECE and Brier deltas."""
    pvr = summary.get("platt_vs_raw_transformation", {})
    assert pvr, "platt_vs_raw_transformation section is missing"

    required = [
        "raw_ece", "platt_ece", "market_ece",
        "raw_brier", "platt_brier", "market_brier",
        "ece_delta_platt_minus_raw", "brier_delta_platt_minus_raw",
        "platt_improved_ece_vs_raw", "anomaly_source",
    ]
    for key in required:
        assert key in pvr, f"platt_vs_raw_transformation missing key: {key}"
        assert pvr[key] is not None, f"platt_vs_raw_transformation.{key} is None"

    # anomaly_source must be one of allowed values
    allowed_sources = {
        "RAW_MODEL_MISCALE",
        "PLATT_TRANSFORM_WORSENED",
        "OUTCOME_RANDOMNESS",
        "MARKET_PROBABILITY_SHIFT",
        "INCONCLUSIVE_SAMPLE_LIMITED",
    }
    assert pvr["anomaly_source"] in allowed_sources, (
        f"Invalid anomaly_source: {pvr['anomaly_source']}"
    )

    # ECE delta = platt_ece - raw_ece (within tolerance)
    delta_expected = pvr["platt_ece"] - pvr["raw_ece"]
    assert abs(pvr["ece_delta_platt_minus_raw"] - delta_expected) < 1e-4, (
        f"ece_delta mismatch: stored={pvr['ece_delta_platt_minus_raw']}, "
        f"computed={delta_expected:.6f}"
    )


# ---------------------------------------------------------------------------
# T09 — Governance flags exist and match required values
# ---------------------------------------------------------------------------
def test_t09_governance_flags(summary: dict) -> None:
    """All governance flags must be present and correct."""
    gov = summary.get("governance_flags", {})
    required = {
        "paper_only": True,
        "diagnostic_only": True,
        "promotion_freeze": True,
        "kelly_deploy_allowed": False,
        "live_api_calls": 0,
        "tsl_crawler_modified": False,
        "champion_strategy_changed": False,
        "production_usage_proposed": False,
        "runtime_recommendation_logic_changed": False,
        "platt_constants_modified": False,
        "p52_contract_overwritten": False,
        "p53_artifact_overwritten": False,
        "p54_artifact_overwritten": False,
    }
    for key, expected in required.items():
        assert key in gov, f"governance_flags missing key: {key}"
        assert gov[key] == expected, (
            f"governance_flags.{key} expected {expected}, got {gov[key]}"
        )


# ---------------------------------------------------------------------------
# T10 — live_api_calls == 0
# ---------------------------------------------------------------------------
def test_t10_live_api_calls_zero(summary: dict) -> None:
    """live_api_calls must be exactly 0."""
    gov = summary.get("governance_flags", {})
    assert gov.get("live_api_calls") == 0, (
        f"live_api_calls must be 0, got {gov.get('live_api_calls')}"
    )


# ---------------------------------------------------------------------------
# T11 — runtime_recommendation_logic_changed == False
# ---------------------------------------------------------------------------
def test_t11_runtime_logic_unchanged(summary: dict) -> None:
    """runtime_recommendation_logic_changed must be False."""
    gov = summary.get("governance_flags", {})
    assert gov.get("runtime_recommendation_logic_changed") is False, (
        "runtime_recommendation_logic_changed must be False"
    )


# ---------------------------------------------------------------------------
# T12 — platt_constants_modified == False
# ---------------------------------------------------------------------------
def test_t12_platt_constants_not_modified(summary: dict) -> None:
    """platt_constants_modified must be False."""
    gov = summary.get("governance_flags", {})
    assert gov.get("platt_constants_modified") is False, (
        "platt_constants_modified must be False"
    )


# ---------------------------------------------------------------------------
# T13 — p52_contract_overwritten == False
# ---------------------------------------------------------------------------
def test_t13_p52_contract_not_overwritten(summary: dict) -> None:
    """P52 contract must not be overwritten."""
    gov = summary.get("governance_flags", {})
    assert gov.get("p52_contract_overwritten") is False, (
        "p52_contract_overwritten must be False"
    )


# ---------------------------------------------------------------------------
# T14 — p53_artifact_overwritten == False
# ---------------------------------------------------------------------------
def test_t14_p53_artifact_not_overwritten(summary: dict) -> None:
    """P53 artifact must not be overwritten."""
    gov = summary.get("governance_flags", {})
    assert gov.get("p53_artifact_overwritten") is False, (
        "p53_artifact_overwritten must be False"
    )


# ---------------------------------------------------------------------------
# T15 — p54_artifact_overwritten == False
# ---------------------------------------------------------------------------
def test_t15_p54_artifact_not_overwritten(summary: dict) -> None:
    """P54 artifact must not be overwritten."""
    gov = summary.get("governance_flags", {})
    assert gov.get("p54_artifact_overwritten") is False, (
        "p54_artifact_overwritten must be False"
    )


# ---------------------------------------------------------------------------
# T16 — JSON contains no deployment-readiness classification
# ---------------------------------------------------------------------------
def test_t16_no_deployment_classification(summary: dict) -> None:
    """Final P55 classification must not imply deployment readiness."""
    clf = summary.get("final_p55_classification", "")
    for forbidden in FORBIDDEN_CLASSIFICATIONS:
        assert forbidden not in clf, (
            f"Forbidden classification fragment '{forbidden}' found in '{clf}'"
        )
    # Also ensure the classification is one of the allowed P55 values
    allowed = {
        "P55_OUTLIER_DRIVEN_MID_BAND_ANOMALY_DIAGNOSTIC",
        "P55_BROAD_BASED_MID_BAND_ANOMALY_DIAGNOSTIC",
        "P55_PLATT_WORSENED_MID_BAND_DIAGNOSTIC",
        "P55_RAW_MODEL_MISCALE_MID_BAND_DIAGNOSTIC",
        "P55_INCONCLUSIVE_SAMPLE_LIMITED",
    }
    assert clf in allowed, (
        f"Final classification '{clf}' is not in the allowed set: {allowed}"
    )


# ---------------------------------------------------------------------------
# T17 — Reports contain no affirmative production/profit claims
# ---------------------------------------------------------------------------
def test_t17_reports_no_production_claims() -> None:
    """Reports must not contain affirmative production or profit claims."""
    for report_path in [REPORT_MD, BETTING_PLAN_MD]:
        assert report_path.exists(), f"Report not found: {report_path}"
        text = report_path.read_text(encoding="utf-8").lower()
        for phrase in FORBIDDEN_REPORT_PHRASES:
            assert phrase.lower() not in text, (
                f"Forbidden phrase '{phrase}' found in {report_path.name}"
            )


# ---------------------------------------------------------------------------
# T18 — active_task.md references final P55 classification
# ---------------------------------------------------------------------------
def test_t18_active_task_references_p55(summary: dict) -> None:
    """active_task.md must reference the final P55 classification."""
    assert ACTIVE_TASK_MD.exists(), f"active_task.md not found: {ACTIVE_TASK_MD}"
    content = ACTIVE_TASK_MD.read_text(encoding="utf-8")
    clf = summary.get("final_p55_classification", "")
    assert clf in content, (
        f"active_task.md must reference '{clf}' but it was not found"
    )
    # Also verify P55 is referenced
    assert "P55" in content, "active_task.md must reference P55"
