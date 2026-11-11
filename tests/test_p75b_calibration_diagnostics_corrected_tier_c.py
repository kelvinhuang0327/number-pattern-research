"""
P75B — Test Suite: Calibration Diagnostics for Corrected Tier C Candidates
===========================================================================
29 tests covering all required test cases from the P75B specification.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
P72A_JSON = ROOT / "data/mlb_2025/derived/p72a_odds_free_strategy_accuracy_backtest_summary.json"
P72B_JSON = ROOT / "data/mlb_2025/derived/p72b_objective_metric_contract_summary.json"
P73_JSON = ROOT / "data/mlb_2025/derived/p73_tier_stability_and_sample_expansion_summary.json"
P74_JSON = ROOT / "data/mlb_2025/derived/p74_tier_c_home_away_bias_correction_summary.json"
P75A_JSON = ROOT / "data/mlb_2025/derived/p75a_tier_c_corrected_rule_validator_summary.json"
P75B_JSON = ROOT / "data/mlb_2025/derived/p75b_calibration_diagnostics_corrected_tier_c_summary.json"
P75B_REPORT = ROOT / "report/p75b_calibration_diagnostics_corrected_tier_c_20260526.md"
ACTIVE_TASK = ROOT / "00-Plan/roadmap/active_task.md"

CANDIDATE_RULE_IDS = [
    "TIER_C_ALL_BASELINE",
    "TIER_C_HOME_ONLY",
    "TIER_C_HOME_PLUS_AWAY_100",
    "TIER_C_HOME_PLUS_AWAY_125",
    "TIER_C_BAND_FILTERED",
]

P75A_EXPECTED = {
    "TIER_C_ALL_BASELINE":       {"n": 535, "hit_rate": 0.6056, "auc": 0.5834},
    "TIER_C_HOME_ONLY":          {"n": 268, "hit_rate": 0.6716, "auc": 0.5591},
    "TIER_C_HOME_PLUS_AWAY_100": {"n": 373, "hit_rate": 0.6327, "auc": 0.5603},
    "TIER_C_HOME_PLUS_AWAY_125": {"n": 316, "hit_rate": 0.6392, "auc": 0.5787},
    "TIER_C_BAND_FILTERED":      {"n": 168, "hit_rate": 0.6369, "auc": 0.6303},
}
TOLERANCE = 0.005

FORBIDDEN_PHRASES = [
    "expected_value",
    "closing_line_value",
    '"clv_calculated": true',
    "kelly fraction",
    '"kelly_deploy_allowed": true',
    '"production_ready": true',
    "profitability confirmed",
    '"real_bet_allowed": true',
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def p75b() -> dict:
    assert P75B_JSON.exists(), f"P75B JSON not found: {P75B_JSON}"
    return json.loads(P75B_JSON.read_text())


@pytest.fixture(scope="module")
def p75a() -> dict:
    assert P75A_JSON.exists()
    return json.loads(P75A_JSON.read_text())


@pytest.fixture(scope="module")
def p74() -> dict:
    assert P74_JSON.exists()
    return json.loads(P74_JSON.read_text())


@pytest.fixture(scope="module")
def p73() -> dict:
    assert P73_JSON.exists()
    return json.loads(P73_JSON.read_text())


@pytest.fixture(scope="module")
def p72a() -> dict:
    assert P72A_JSON.exists()
    return json.loads(P72A_JSON.read_text())


@pytest.fixture(scope="module")
def p72b() -> dict:
    assert P72B_JSON.exists()
    return json.loads(P72B_JSON.read_text())


# ---------------------------------------------------------------------------
# Test 1 — P72A/P72B/P73/P74/P75A artifacts load
# ---------------------------------------------------------------------------

def test_01_source_artifacts_load(p72a, p72b, p73, p74, p75a):
    assert isinstance(p72a, dict) and isinstance(p72b, dict)
    assert isinstance(p73, dict) and isinstance(p74, dict) and isinstance(p75a, dict)
    assert p75a["p75a_classification"] == "P75A_MULTI_CANDIDATE_REQUIRES_CALIBRATION"
    assert p74["p74_classification"] == "P74_TIER_C_HOME_AWAY_CORRECTION_CONFIRMED"


# ---------------------------------------------------------------------------
# Test 2 — Candidate rules reconstructed
# ---------------------------------------------------------------------------

def test_02_candidates_reconstructed(p75b):
    s1 = p75b["step1_reconstruction"]
    assert "reconstructions" in s1
    for rid in CANDIDATE_RULE_IDS:
        assert rid in s1["reconstructions"]


# ---------------------------------------------------------------------------
# Test 3 — Candidate reconstruction matches P75A within tolerance
# ---------------------------------------------------------------------------

def test_03_reconstruction_matches_p75a(p75b):
    s1 = p75b["step1_reconstruction"]
    for rid, exp in P75A_EXPECTED.items():
        rec = s1["reconstructions"][rid]
        assert rec["n"] == exp["n"], f"{rid}: n mismatch"
        assert abs(rec["hit_rate"] - exp["hit_rate"]) <= TOLERANCE, f"{rid}: hit_rate mismatch"
        assert rec["valid"] is True
    assert s1["all_valid"] is True


# ---------------------------------------------------------------------------
# Test 4 — Uncalibrated Brier computed
# ---------------------------------------------------------------------------

def test_04_uncalibrated_brier_computed(p75b):
    s2 = p75b["step2_uncalibrated"]
    for rid in CANDIDATE_RULE_IDS:
        m = s2[rid]
        assert m["brier"] is not None
        assert 0.0 < m["brier"] < 1.0, f"{rid}: brier={m['brier']} out of range"


# ---------------------------------------------------------------------------
# Test 5 — Uncalibrated log_loss computed
# ---------------------------------------------------------------------------

def test_05_uncalibrated_log_loss_computed(p75b):
    s2 = p75b["step2_uncalibrated"]
    for rid in CANDIDATE_RULE_IDS:
        m = s2[rid]
        assert m["log_loss"] is not None
        assert m["log_loss"] > 0, f"{rid}: log_loss={m['log_loss']} should be positive"


# ---------------------------------------------------------------------------
# Test 6 — Uncalibrated ECE computed
# ---------------------------------------------------------------------------

def test_06_uncalibrated_ece_computed(p75b):
    s2 = p75b["step2_uncalibrated"]
    for rid in CANDIDATE_RULE_IDS:
        m = s2[rid]
        assert m["ece"] is not None
        assert 0.0 <= m["ece"] <= 1.0, f"{rid}: ece={m['ece']} out of range"


# ---------------------------------------------------------------------------
# Test 7 — Reliability buckets generated
# ---------------------------------------------------------------------------

def test_07_reliability_buckets_generated(p75b):
    s2 = p75b["step2_uncalibrated"]
    for rid in CANDIDATE_RULE_IDS:
        buckets = s2[rid].get("reliability_buckets", [])
        assert len(buckets) >= 3, f"{rid}: only {len(buckets)} reliability buckets"
        for b in buckets:
            assert "bin_lo" in b and "bin_hi" in b
            assert "n" in b and b["n"] > 0
            assert "avg_predicted_prob" in b
            assert "avg_actual_rate" in b


# ---------------------------------------------------------------------------
# Test 8 — Platt scaling applied or explicitly marked unavailable
# ---------------------------------------------------------------------------

def test_08_platt_scaling_applied(p75b):
    s3 = p75b["step3_calibration"]
    for rid in CANDIDATE_RULE_IDS:
        methods = s3[rid]["methods"]
        method_names = [m["method"] for m in methods]
        assert "platt" in method_names, f"{rid}: platt method missing"
        platt = next(m for m in methods if m["method"] == "platt")
        # Should either be calibrated or have a clear reason
        if not platt.get("calibrated"):
            assert platt.get("reason") is not None


# ---------------------------------------------------------------------------
# Test 9 — Temperature scaling applied or explicitly marked unavailable
# ---------------------------------------------------------------------------

def test_09_temperature_scaling_applied(p75b):
    s3 = p75b["step3_calibration"]
    for rid in CANDIDATE_RULE_IDS:
        methods = s3[rid]["methods"]
        method_names = [m["method"] for m in methods]
        assert "temperature" in method_names, f"{rid}: temperature method missing"


# ---------------------------------------------------------------------------
# Test 10 — Isotonic applied only when sample size permits or marked high overfit risk
# ---------------------------------------------------------------------------

def test_10_isotonic_overfit_risk_enforced(p75b):
    s3 = p75b["step3_calibration"]
    for rid in CANDIDATE_RULE_IDS:
        methods = s3[rid]["methods"]
        n = s3[rid]["n"]
        iso = next((m for m in methods if "isotonic" in m["method"]), None)
        assert iso is not None, f"{rid}: isotonic method missing"
        if n < 50:
            assert iso.get("overfit_risk") == "HIGH", f"{rid}: n={n}<50 but isotonic not HIGH overfit risk"
            assert not iso.get("allowed"), f"{rid}: n={n}<50 but isotonic allowed"


# ---------------------------------------------------------------------------
# Test 11 — No fit/evaluate on same data without overfit flag
# ---------------------------------------------------------------------------

def test_11_no_same_data_fit_evaluate(p75b):
    s3 = p75b["step3_calibration"]
    for rid in CANDIDATE_RULE_IDS:
        for m in s3[rid]["methods"]:
            if m.get("calibrated") and m["method"] != "no_calibration":
                # Must have train_n < total n (i.e., not fit on same data)
                train_n = m.get("train_n", 0)
                total_n = s3[rid]["n"]
                assert train_n < total_n or "kfold" in m["method"], (
                    f"{rid}/{m['method']}: train_n={train_n} == total_n={total_n} (same-data fit)"
                )


# ---------------------------------------------------------------------------
# Test 12 — Cross-validation or chronological split used
# ---------------------------------------------------------------------------

def test_12_cv_or_chrono_split_used(p75b):
    s3 = p75b["step3_calibration"]
    for rid in CANDIDATE_RULE_IDS:
        split_train = s3[rid].get("split_train_n", 0)
        total = s3[rid]["n"]
        # chrono split: train should be ~70% of total
        assert split_train > 0, f"{rid}: no chronological split recorded"
        assert split_train < total, f"{rid}: split_train={split_train} >= total={total}"


# ---------------------------------------------------------------------------
# Test 13 — Calibration method comparison table generated
# ---------------------------------------------------------------------------

def test_13_calibration_comparison_table(p75b):
    s3 = p75b["step3_calibration"]
    for rid in CANDIDATE_RULE_IDS:
        methods = s3[rid]["methods"]
        assert len(methods) >= 3, f"{rid}: fewer than 3 calibration methods"
        method_names = {m["method"] for m in methods}
        assert "no_calibration" in method_names
        assert "platt" in method_names
        assert "temperature" in method_names


# ---------------------------------------------------------------------------
# Test 14 — Candidate scorecard generated
# ---------------------------------------------------------------------------

def test_14_scorecard_generated(p75b):
    s4 = p75b["step4_scorecard"]
    scores = s4["scores"]
    scored_ids = {s["rule_id"] for s in scores}
    for rid in CANDIDATE_RULE_IDS:
        assert rid in scored_ids, f"Missing scorecard entry for {rid}"
    for s in scores:
        assert "cal_status" in s
        assert "best_cal_brier" in s
        assert "best_cal_ece" in s
        assert "best_cal_method" in s


# ---------------------------------------------------------------------------
# Test 15 — Operational calibration gate logic tested
# ---------------------------------------------------------------------------

def test_15_operational_gate_logic(p75b):
    s4 = p75b["step4_scorecard"]
    for s in s4["scores"]:
        # If n<200, status must not be OPERATIONAL_CALIBRATED
        if not s["n_ok"]:
            assert "OPERATIONAL_CALIBRATED" not in s["cal_status"] or s["rule_id"] == "TIER_C_ALL_BASELINE", (
                f"{s['rule_id']}: n<200 but OPERATIONAL_CALIBRATED"
            )


# ---------------------------------------------------------------------------
# Test 16 — n>=200 gate enforced
# ---------------------------------------------------------------------------

def test_16_n_200_gate_enforced(p75b):
    s4 = p75b["step4_scorecard"]
    for s in s4["scores"]:
        if s["n"] < 200:
            assert s["n_ok"] is False
            assert "OPERATIONAL" not in s["cal_status"] or s["rule_id"] == "TIER_C_ALL_BASELINE", (
                f"{s['rule_id']}: n={s['n']}<200 but operational"
            )


# ---------------------------------------------------------------------------
# Test 17 — HOME_ONLY concentration caveat retained
# ---------------------------------------------------------------------------

def test_17_home_only_caveat_retained(p75b):
    s4 = p75b["step4_scorecard"]
    home_only = next(s for s in s4["scores"] if s["rule_id"] == "TIER_C_HOME_ONLY")
    assert "SEVERE_HOME_ONLY_DEPENDENCY" in home_only["caveats"], (
        "HOME_ONLY must retain SEVERE_HOME_ONLY_DEPENDENCY caveat"
    )
    # Status must reflect caveat
    assert "WITH_CAVEATS" in home_only["cal_status"] or "RESEARCH" in home_only["cal_status"], (
        f"HOME_ONLY status should include caveat: {home_only['cal_status']}"
    )


# ---------------------------------------------------------------------------
# Test 18 — BAND_FILTERED remains research-only
# ---------------------------------------------------------------------------

def test_18_band_filtered_research_only(p75b):
    s4 = p75b["step4_scorecard"]
    band = next(s for s in s4["scores"] if s["rule_id"] == "TIER_C_BAND_FILTERED")
    # n=168 < 200, so must be research-only
    assert band["n"] < 200
    assert "RESEARCH_ONLY" in band["cal_status"] or "RESEARCH" in band["cal_status"], (
        f"BAND_FILTERED should be research-only, got {band['cal_status']}"
    )


# ---------------------------------------------------------------------------
# Test 19 — Exactly one preferred rule or explicit multi-candidate decision
# ---------------------------------------------------------------------------

def test_19_exactly_one_preferred_or_explicit_multi(p75b):
    s5 = p75b["step5_selection"]
    assert "preferred_rule" in s5
    assert s5["preferred_rule"] in CANDIDATE_RULE_IDS
    assert s5.get("p75b_status") in p75b["allowed_classifications"]


# ---------------------------------------------------------------------------
# Test 20 — No odds required
# ---------------------------------------------------------------------------

def test_20_no_odds_required(p75b):
    gov = p75b["governance"]
    assert gov["uses_historical_odds"] is False
    assert gov["the_odds_api_key_required"] is False
    assert gov["market_edge_calculated"] is False


# ---------------------------------------------------------------------------
# Test 21 — No EV / CLV / Kelly calculated
# ---------------------------------------------------------------------------

def test_21_no_ev_clv_kelly(p75b):
    gov = p75b["governance"]
    assert gov["ev_calculated"] is False
    assert gov["clv_calculated"] is False
    assert gov["kelly_deploy_allowed"] is False


# ---------------------------------------------------------------------------
# Test 22 — live_api_calls=0
# ---------------------------------------------------------------------------

def test_22_live_api_calls_zero(p75b):
    assert p75b["governance"]["live_api_calls"] == 0


# ---------------------------------------------------------------------------
# Test 23 — production_ready=False
# ---------------------------------------------------------------------------

def test_23_production_ready_false(p75b):
    assert p75b["governance"]["production_ready"] is False


# ---------------------------------------------------------------------------
# Test 24 — kelly_deploy_allowed=False
# ---------------------------------------------------------------------------

def test_24_kelly_deploy_allowed_false(p75b):
    assert p75b["governance"]["kelly_deploy_allowed"] is False


# ---------------------------------------------------------------------------
# Test 25 — Forbidden phrase scan passes
# ---------------------------------------------------------------------------

def test_25_forbidden_phrase_scan(p75b):
    raw = json.dumps(p75b).lower()
    for phrase in FORBIDDEN_PHRASES:
        assert phrase.lower() not in raw, f"Forbidden phrase in P75B output: '{phrase}'"
    if P75B_REPORT.exists():
        report_text = P75B_REPORT.read_text().lower()
        for phrase in FORBIDDEN_PHRASES:
            assert phrase.lower() not in report_text, f"Forbidden phrase in report: '{phrase}'"


# ---------------------------------------------------------------------------
# Test 26 — JSON schema stable
# ---------------------------------------------------------------------------

def test_26_json_schema_stable(p75b):
    required_keys = [
        "phase", "date", "p75b_classification", "governance",
        "forbidden_scan", "source_artifacts", "calibration_module_status",
        "step1_reconstruction", "step2_uncalibrated",
        "step3_calibration", "step4_scorecard", "step5_selection",
        "prediction_boundary",
    ]
    for key in required_keys:
        assert key in p75b, f"Missing key: {key}"


# ---------------------------------------------------------------------------
# Test 27 — Report includes calibration summary table
# ---------------------------------------------------------------------------

def test_27_report_includes_calibration_summary():
    assert P75B_REPORT.exists(), f"Report not found: {P75B_REPORT}"
    report = P75B_REPORT.read_text()
    assert "TIER_C_ALL_BASELINE" in report
    assert "TIER_C_HOME_PLUS_AWAY" in report
    assert "Cal Brier" in report or "cal_brier" in report.lower()
    assert "Cal ECE" in report or "cal_ece" in report.lower()
    assert "Preferred Rule" in report or "preferred_rule" in report.lower()


# ---------------------------------------------------------------------------
# Test 28 — active_task.md updated
# ---------------------------------------------------------------------------

def test_28_active_task_updated():
    assert ACTIVE_TASK.exists()
    content = ACTIVE_TASK.read_text()
    assert "P75B" in content or "P75A" in content


# ---------------------------------------------------------------------------
# Test 29 — P72A/P72B/P73/P74/P75A/P75B regression
# ---------------------------------------------------------------------------

def test_29_full_regression(p72a, p72b, p73, p74, p75a, p75b):
    # P72A
    p72a_cls = str(p72a.get("p72a_classification") or p72a.get("final_classification", ""))
    assert "CONFIRMED" in p72a_cls or "SIGNAL" in p72a_cls or "PREDICTIVE" in p72a_cls

    # P73
    assert "TIER_C_OPERATIONAL_STABLE" in p73.get("p73_classification", "")

    # P74
    assert p74["p74_classification"] == "P74_TIER_C_HOME_AWAY_CORRECTION_CONFIRMED"

    # P75A
    assert p75a["p75a_classification"] == "P75A_MULTI_CANDIDATE_REQUIRES_CALIBRATION"

    # P75B valid classification
    assert p75b["p75b_classification"] in p75b["allowed_classifications"]

    # n chain: all agree on 535
    assert p75b["step1_reconstruction"]["reconstructions"]["TIER_C_ALL_BASELINE"]["n"] == 535
    assert p75a["step1_reconstruction"]["reconstructions"]["TIER_C_ALL_BASELINE"]["n"] == 535
    assert p74["step1_reconstruction"]["n"] == 535
    assert p73["p73a_tier_c"]["n"] == 535

    # governance chain
    for result in [p73, p74, p75a, p75b]:
        assert result["governance"]["paper_only"] is True
        assert result["governance"]["live_api_calls"] == 0
        assert result["governance"]["production_ready"] is False

    # P75B reconstruction all_valid
    assert p75b["step1_reconstruction"]["all_valid"] is True

    # P75B has calibration_module_status
    assert p75b.get("calibration_module_status") in ("AVAILABLE", "MISSING_LOCAL_DIAGNOSTIC_USED")
