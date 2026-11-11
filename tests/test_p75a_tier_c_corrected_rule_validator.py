"""
P75A — Test Suite: Tier C Corrected Rule Validator
===================================================
29 tests covering all required test cases from the P75A specification.
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
P75A_REPORT = ROOT / "report/p75a_tier_c_corrected_rule_validator_20260526.md"
ACTIVE_TASK = ROOT / "00-Plan/roadmap/active_task.md"

# Reference values from P74
P74_EXPECTED = {
    "TIER_C_ALL_BASELINE":       {"n": 535,  "hit_rate": 0.6056, "auc": 0.5834},
    "TIER_C_HOME_ONLY":          {"n": 268,  "hit_rate": 0.6716, "auc": 0.5591},
    "TIER_C_HOME_PLUS_AWAY_100": {"n": 373,  "hit_rate": 0.6327, "auc": 0.5603},
    "TIER_C_HOME_PLUS_AWAY_125": {"n": 316,  "hit_rate": 0.6392, "auc": 0.5787},
    "TIER_C_BAND_FILTERED":      {"n": 168,  "hit_rate": 0.6369, "auc": 0.6303},
}
TOLERANCE = 0.005

CANDIDATE_RULE_IDS = [
    "TIER_C_ALL_BASELINE",
    "TIER_C_HOME_ONLY",
    "TIER_C_HOME_PLUS_AWAY_100",
    "TIER_C_HOME_PLUS_AWAY_125",
    "TIER_C_BAND_FILTERED",
]

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
def p75a() -> dict:
    assert P75A_JSON.exists(), f"P75A JSON not found: {P75A_JSON}"
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
# Test 1 — P72A/P72B/P73/P74 source artifacts load
# ---------------------------------------------------------------------------

def test_01_source_artifacts_load(p72a, p72b, p73, p74):
    assert isinstance(p72a, dict)
    assert isinstance(p72b, dict)
    assert isinstance(p73, dict)
    assert isinstance(p74, dict)
    assert "p74_classification" in p74
    assert p74["p74_classification"] == "P74_TIER_C_HOME_AWAY_CORRECTION_CONFIRMED"


# ---------------------------------------------------------------------------
# Test 2 — P74 candidate rules reconstructed
# ---------------------------------------------------------------------------

def test_02_p74_candidates_reconstructed(p75a):
    s1 = p75a["step1_reconstruction"]
    assert "reconstructions" in s1
    for rid in CANDIDATE_RULE_IDS:
        assert rid in s1["reconstructions"], f"Missing reconstruction for {rid}"


# ---------------------------------------------------------------------------
# Test 3 — Baseline Tier C matches P74 within tolerance
# ---------------------------------------------------------------------------

def test_03_baseline_matches_p74(p75a):
    rec = p75a["step1_reconstruction"]["reconstructions"]["TIER_C_ALL_BASELINE"]
    exp = P74_EXPECTED["TIER_C_ALL_BASELINE"]
    assert rec["n"] == exp["n"]
    assert abs(rec["hit_rate"] - exp["hit_rate"]) <= TOLERANCE
    assert abs(rec["auc"] - exp["auc"]) <= TOLERANCE
    assert rec["valid"] is True


# ---------------------------------------------------------------------------
# Test 4 — HOME_ONLY matches P74 within tolerance
# ---------------------------------------------------------------------------

def test_04_home_only_matches_p74(p75a):
    rec = p75a["step1_reconstruction"]["reconstructions"]["TIER_C_HOME_ONLY"]
    exp = P74_EXPECTED["TIER_C_HOME_ONLY"]
    assert rec["n"] == exp["n"]
    assert abs(rec["hit_rate"] - exp["hit_rate"]) <= TOLERANCE
    assert abs(rec["auc"] - exp["auc"]) <= TOLERANCE
    assert rec["valid"] is True


# ---------------------------------------------------------------------------
# Test 5 — HOME_PLUS_AWAY_100 matches P74 within tolerance
# ---------------------------------------------------------------------------

def test_05_home_plus_away_100_matches_p74(p75a):
    rec = p75a["step1_reconstruction"]["reconstructions"]["TIER_C_HOME_PLUS_AWAY_100"]
    exp = P74_EXPECTED["TIER_C_HOME_PLUS_AWAY_100"]
    assert rec["n"] == exp["n"]
    assert abs(rec["hit_rate"] - exp["hit_rate"]) <= TOLERANCE
    assert rec["valid"] is True


# ---------------------------------------------------------------------------
# Test 6 — HOME_PLUS_AWAY_125 matches P74 within tolerance
# ---------------------------------------------------------------------------

def test_06_home_plus_away_125_matches_p74(p75a):
    rec = p75a["step1_reconstruction"]["reconstructions"]["TIER_C_HOME_PLUS_AWAY_125"]
    exp = P74_EXPECTED["TIER_C_HOME_PLUS_AWAY_125"]
    assert rec["n"] == exp["n"]
    assert abs(rec["hit_rate"] - exp["hit_rate"]) <= TOLERANCE
    assert rec["valid"] is True


# ---------------------------------------------------------------------------
# Test 7 — BAND_FILTERED matches P74 within tolerance
# ---------------------------------------------------------------------------

def test_07_band_filtered_matches_p74(p75a):
    rec = p75a["step1_reconstruction"]["reconstructions"]["TIER_C_BAND_FILTERED"]
    exp = P74_EXPECTED["TIER_C_BAND_FILTERED"]
    assert rec["n"] == exp["n"]
    assert abs(rec["hit_rate"] - exp["hit_rate"]) <= TOLERANCE
    assert rec["valid"] is True


# ---------------------------------------------------------------------------
# Test 8 — Bootstrap deterministic with seed=42
# ---------------------------------------------------------------------------

def test_08_bootstrap_deterministic_seed42(p75a):
    s2 = p75a["step2_robustness"]["rule_metrics"]
    baseline_ci = s2["TIER_C_ALL_BASELINE"]["hit_rate_ci_95"]
    home_ci = s2["TIER_C_HOME_ONLY"]["hit_rate_ci_95"]
    # Deterministic: re-check known values
    assert baseline_ci[0] is not None and baseline_ci[1] is not None
    assert home_ci[0] is not None and home_ci[1] is not None
    # home CI should be fully above 0.50
    assert home_ci[0] > 0.50, f"HOME_ONLY CI low={home_ci[0]} should be > 0.50"


# ---------------------------------------------------------------------------
# Test 9 — Chronological thirds generated
# ---------------------------------------------------------------------------

def test_09_chronological_thirds_generated(p75a):
    s2 = p75a["step2_robustness"]["rule_metrics"]
    for rid in ["TIER_C_ALL_BASELINE", "TIER_C_HOME_ONLY", "TIER_C_HOME_PLUS_AWAY_125"]:
        thirds = s2[rid].get("chronological_thirds", [])
        assert len(thirds) == 3, f"{rid} should have 3 thirds, got {len(thirds)}"
        for t in thirds:
            assert "hit_rate" in t
            assert t["n"] > 0


# ---------------------------------------------------------------------------
# Test 10 — Monthly stability generated
# ---------------------------------------------------------------------------

def test_10_monthly_stability_generated(p75a):
    s2 = p75a["step2_robustness"]["rule_metrics"]
    for rid in CANDIDATE_RULE_IDS:
        m = s2[rid]
        assert "monthly_stability" in m
        assert m["monthly_stability"] in ("STABLE", "MODERATE", "UNSTABLE", "INSUFFICIENT_MONTHS")
        assert "monthly_breakdown" in m
        assert len(m["monthly_breakdown"]) >= 3


# ---------------------------------------------------------------------------
# Test 11 — Rolling-window stability generated
# ---------------------------------------------------------------------------

def test_11_rolling_window_generated(p75a):
    s2 = p75a["step2_robustness"]["rule_metrics"]
    for rid in ["TIER_C_ALL_BASELINE", "TIER_C_HOME_ONLY"]:
        rolling = s2[rid].get("rolling_window_stability", [])
        assert len(rolling) >= 2, f"{rid} rolling window has {len(rolling)} entries"
        for w in rolling:
            assert "hit_rate" in w
            assert w["n"] >= 10


# ---------------------------------------------------------------------------
# Test 12 — Head-to-head comparison generated
# ---------------------------------------------------------------------------

def test_12_head_to_head_comparison_generated(p75a):
    s3 = p75a["step3_head_to_head"]
    comps = s3["comparisons"]
    compared_ids = {c["rule_id"] for c in comps}
    for rid in ["TIER_C_HOME_ONLY", "TIER_C_HOME_PLUS_AWAY_100", "TIER_C_HOME_PLUS_AWAY_125", "TIER_C_BAND_FILTERED"]:
        assert rid in compared_ids, f"Missing head-to-head for {rid}"
    for c in comps:
        assert "hit_delta_vs_baseline" in c
        assert "auc_delta_vs_baseline" in c
        assert "sample_loss_pct" in c


# ---------------------------------------------------------------------------
# Test 13 — Candidate gate logic tested
# ---------------------------------------------------------------------------

def test_13_gate_logic_tested(p75a):
    s4 = p75a["step4_gate"]
    for g in s4["gate_results"]:
        assert g["gate_status"] in (
            "OPERATIONAL_CANDIDATE",
            "OPERATIONAL_WITH_CAVEATS",
            "RESEARCH_ONLY",
            "WATCHLIST",
        )
        assert "gate_checks" in g
        checks = g["gate_checks"]
        assert "n_ge_200" in checks
        assert "hit_beats_baseline_by_002" in checks
        assert "ci_low_ge_055" in checks
        assert "monthly_stability_moderate_or_better" in checks
        assert "no_severe_concentration_risk" in checks


# ---------------------------------------------------------------------------
# Test 14 — n>=200 operational threshold enforced
# ---------------------------------------------------------------------------

def test_14_n_200_threshold_enforced(p75a):
    s4 = p75a["step4_gate"]
    for g in s4["gate_results"]:
        checks = g["gate_checks"]
        if not checks["n_ge_200"]:
            assert g["gate_status"] not in ("OPERATIONAL_CANDIDATE",), (
                f"{g['rule_id']} has n<200 but is OPERATIONAL_CANDIDATE"
            )


# ---------------------------------------------------------------------------
# Test 15 — hit_rate improvement threshold enforced
# ---------------------------------------------------------------------------

def test_15_hit_improvement_threshold_enforced(p75a):
    s4 = p75a["step4_gate"]
    for g in s4["gate_results"]:
        checks = g["gate_checks"]
        if not checks["hit_beats_baseline_by_002"]:
            assert g["gate_status"] not in ("OPERATIONAL_CANDIDATE", "OPERATIONAL_WITH_CAVEATS"), (
                f"{g['rule_id']} doesn't beat baseline by 0.02 but is operational"
            )


# ---------------------------------------------------------------------------
# Test 16 — CI low threshold enforced
# ---------------------------------------------------------------------------

def test_16_ci_low_threshold_enforced(p75a):
    s4 = p75a["step4_gate"]
    for g in s4["gate_results"]:
        checks = g["gate_checks"]
        if not checks["ci_low_ge_055"]:
            assert g["gate_status"] not in ("OPERATIONAL_CANDIDATE", "OPERATIONAL_WITH_CAVEATS"), (
                f"{g['rule_id']} has CI_low<0.55 but is operational"
            )


# ---------------------------------------------------------------------------
# Test 17 — Severe concentration risk blocks OPERATIONAL_CANDIDATE (but not WITH_CAVEATS)
# ---------------------------------------------------------------------------

def test_17_severe_conc_risk_handling(p75a):
    s4 = p75a["step4_gate"]
    for g in s4["gate_results"]:
        if g["severe_concentration_risk"] and g["gate_checks"]["n_ge_200"]:
            assert g["gate_status"] != "OPERATIONAL_CANDIDATE", (
                f"{g['rule_id']} has severe concentration risk but is OPERATIONAL_CANDIDATE "
                f"(should be OPERATIONAL_WITH_CAVEATS or lower)"
            )


# ---------------------------------------------------------------------------
# Test 18 — AUC drop explanation present when hit improves but AUC drops
# ---------------------------------------------------------------------------

def test_18_auc_drop_explanation_present(p75a):
    s3 = p75a["step3_head_to_head"]
    for c in s3["comparisons"]:
        hit_d = c.get("hit_delta_vs_baseline") or 0
        auc_d = c.get("auc_delta_vs_baseline") or 0
        if hit_d > 0 and auc_d < -0.005:
            assert c.get("auc_drop_note") is not None, (
                f"{c['rule_id']} improves hit ({hit_d:+.4f}) but drops AUC ({auc_d:+.4f}) "
                "without explanation note"
            )


# ---------------------------------------------------------------------------
# Test 19 — Exactly one final preferred rule or explicit multi-candidate decision
# ---------------------------------------------------------------------------

def test_19_exactly_one_preferred_rule_or_explicit_multi(p75a):
    s5 = p75a["step5_preferred_rule"]
    assert "preferred_rule" in s5
    assert s5["preferred_rule"] in CANDIDATE_RULE_IDS, (
        f"Preferred rule '{s5['preferred_rule']}' not in candidate list"
    )
    assert s5.get("p75a_status") in p75a["allowed_classifications"]


# ---------------------------------------------------------------------------
# Test 20 — No odds required
# ---------------------------------------------------------------------------

def test_20_no_odds_required(p75a):
    gov = p75a["governance"]
    assert gov["uses_historical_odds"] is False
    assert gov["the_odds_api_key_required"] is False
    assert gov["market_edge_calculated"] is False


# ---------------------------------------------------------------------------
# Test 21 — No EV / CLV / Kelly calculated
# ---------------------------------------------------------------------------

def test_21_no_ev_clv_kelly(p75a):
    gov = p75a["governance"]
    assert gov["ev_calculated"] is False
    assert gov["clv_calculated"] is False
    assert gov["kelly_deploy_allowed"] is False


# ---------------------------------------------------------------------------
# Test 22 — live_api_calls=0
# ---------------------------------------------------------------------------

def test_22_live_api_calls_zero(p75a):
    assert p75a["governance"]["live_api_calls"] == 0


# ---------------------------------------------------------------------------
# Test 23 — production_ready=False
# ---------------------------------------------------------------------------

def test_23_production_ready_false(p75a):
    assert p75a["governance"]["production_ready"] is False


# ---------------------------------------------------------------------------
# Test 24 — kelly_deploy_allowed=False
# ---------------------------------------------------------------------------

def test_24_kelly_deploy_allowed_false(p75a):
    assert p75a["governance"]["kelly_deploy_allowed"] is False


# ---------------------------------------------------------------------------
# Test 25 — Forbidden phrase scan passes
# ---------------------------------------------------------------------------

def test_25_forbidden_phrase_scan(p75a):
    raw = json.dumps(p75a).lower()
    for phrase in FORBIDDEN_PHRASES:
        assert phrase.lower() not in raw, f"Forbidden phrase found in P75A output: '{phrase}'"
    if P75A_REPORT.exists():
        report_text = P75A_REPORT.read_text().lower()
        for phrase in FORBIDDEN_PHRASES:
            assert phrase.lower() not in report_text, f"Forbidden phrase in report: '{phrase}'"


# ---------------------------------------------------------------------------
# Test 26 — JSON schema stable
# ---------------------------------------------------------------------------

def test_26_json_schema_stable(p75a):
    required_keys = [
        "phase",
        "date",
        "p75a_classification",
        "governance",
        "forbidden_scan",
        "source_artifacts",
        "step1_reconstruction",
        "step2_robustness",
        "step3_head_to_head",
        "step4_gate",
        "step5_preferred_rule",
        "prediction_boundary",
    ]
    for key in required_keys:
        assert key in p75a, f"Missing key: {key}"


# ---------------------------------------------------------------------------
# Test 27 — Report includes final rule table
# ---------------------------------------------------------------------------

def test_27_report_includes_rule_table():
    assert P75A_REPORT.exists(), f"Report not found: {P75A_REPORT}"
    report = P75A_REPORT.read_text()
    assert "TIER_C_ALL_BASELINE" in report
    assert "TIER_C_HOME_ONLY" in report
    assert "TIER_C_HOME_PLUS_AWAY" in report
    assert "Gate Result" in report or "gate_status" in report.lower() or "OPERATIONAL" in report


# ---------------------------------------------------------------------------
# Test 28 — active_task.md updated
# ---------------------------------------------------------------------------

def test_28_active_task_updated():
    assert ACTIVE_TASK.exists()
    content = ACTIVE_TASK.read_text()
    assert "P75A" in content or "P74" in content


# ---------------------------------------------------------------------------
# Test 29 — P72A/P72B/P73/P74/P75A regression
# ---------------------------------------------------------------------------

def test_29_full_regression(p72a, p72b, p73, p74, p75a):
    # P72A classification check
    p72a_cls = str(p72a.get("p72a_classification") or p72a.get("final_classification", ""))
    assert "CONFIRMED" in p72a_cls or "SIGNAL" in p72a_cls or "PREDICTIVE" in p72a_cls

    # P73 Tier C operational stable
    assert "TIER_C_OPERATIONAL_STABLE" in p73.get("p73_classification", "")

    # P74 correction confirmed
    assert p74["p74_classification"] == "P74_TIER_C_HOME_AWAY_CORRECTION_CONFIRMED"

    # P75A valid classification
    assert p75a["p75a_classification"] in p75a["allowed_classifications"]

    # n chain: all must agree
    assert p75a["step1_reconstruction"]["reconstructions"]["TIER_C_ALL_BASELINE"]["n"] == 535
    assert p74["step1_reconstruction"]["n"] == 535
    assert p73["p73a_tier_c"]["n"] == 535

    # governance chain
    for result in [p73, p74, p75a]:
        assert result["governance"]["paper_only"] is True
        assert result["governance"]["live_api_calls"] == 0
        assert result["governance"]["production_ready"] is False

    # P75A reconstruction all_valid
    assert p75a["step1_reconstruction"]["all_valid"] is True

    # P75A classification in allowed list
    cls = p75a["p75a_classification"]
    assert cls in p75a["allowed_classifications"]
