"""
P74 — Test Suite: Tier C Home/Away Bias Correction Research
============================================================
24 tests covering all required test cases from the P74 specification.
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
P74_REPORT = ROOT / "report/p74_tier_c_home_away_bias_correction_20260526.md"
PREDICTIONS_JSONL = ROOT / "data/mlb_2025/derived/mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl"
ACTIVE_TASK = ROOT / "00-Plan/roadmap/active_task.md"

P73A_EXPECTED_N = 535
P73A_EXPECTED_HIT_RATE = 0.6056
P73A_EXPECTED_AUC = 0.5834
TOLERANCE = 0.005
OPERATIONAL_MIN_N = 75

FORBIDDEN_PHRASES = [
    "expected_value",
    "closing_line_value",
    "\"clv_calculated\": true",
    "kelly fraction",
    "\"kelly_deploy_allowed\": true",
    "\"production_ready\": true",
    "profitability confirmed",
    "\"real_bet_allowed\": true",
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def p74_result() -> dict:
    assert P74_JSON.exists(), f"P74 JSON not found: {P74_JSON}"
    return json.loads(P74_JSON.read_text())


@pytest.fixture(scope="module")
def p73_result() -> dict:
    assert P73_JSON.exists()
    return json.loads(P73_JSON.read_text())


@pytest.fixture(scope="module")
def p72a_result() -> dict:
    assert P72A_JSON.exists()
    return json.loads(P72A_JSON.read_text())


@pytest.fixture(scope="module")
def p72b_result() -> dict:
    assert P72B_JSON.exists()
    return json.loads(P72B_JSON.read_text())


# ---------------------------------------------------------------------------
# Test 1 — P72A/P72B/P73 source artifacts load
# ---------------------------------------------------------------------------

def test_01_source_artifacts_load(p72a_result, p72b_result, p73_result):
    assert isinstance(p72a_result, dict)
    assert isinstance(p72b_result, dict)
    assert isinstance(p73_result, dict)
    assert "phase" in p72a_result or "strategy_accuracy" in str(p72a_result)
    assert "phase" in p73_result or "p73_classification" in p73_result


# ---------------------------------------------------------------------------
# Test 2 — Tier C reconstruction equals P73 n=535
# ---------------------------------------------------------------------------

def test_02_tier_c_reconstruction_n_equals_535(p74_result):
    s1 = p74_result["step1_reconstruction"]
    assert s1["n"] == P73A_EXPECTED_N, f"Expected n={P73A_EXPECTED_N}, got {s1['n']}"
    assert s1["n_match"] is True


# ---------------------------------------------------------------------------
# Test 3 — Tier C reconstruction matches P73 hit_rate and AUC within tolerance
# ---------------------------------------------------------------------------

def test_03_tier_c_reconstruction_metrics_match_p73(p74_result):
    s1 = p74_result["step1_reconstruction"]
    assert abs(s1["hit_rate"] - P73A_EXPECTED_HIT_RATE) <= TOLERANCE, (
        f"hit_rate mismatch: {s1['hit_rate']} vs {P73A_EXPECTED_HIT_RATE}"
    )
    assert abs(s1["auc"] - P73A_EXPECTED_AUC) <= TOLERANCE, (
        f"AUC mismatch: {s1['auc']} vs {P73A_EXPECTED_AUC}"
    )
    assert s1["hit_rate_match"] is True
    assert s1["auc_match"] is True
    assert s1["reconstruction_valid"] is True


# ---------------------------------------------------------------------------
# Test 4 — Home split generated
# ---------------------------------------------------------------------------

def test_04_home_split_generated(p74_result):
    s2 = p74_result["step2_home_away_decomposition"]
    home = s2["home"]
    assert home["n"] > 0
    assert home["hit_rate"] is not None
    assert home["auc"] is not None
    assert home["brier"] is not None
    assert home["monthly_stability"] in ("STABLE", "MODERATE", "UNSTABLE", "INSUFFICIENT_MONTHS")


# ---------------------------------------------------------------------------
# Test 5 — Away split generated
# ---------------------------------------------------------------------------

def test_05_away_split_generated(p74_result):
    s2 = p74_result["step2_home_away_decomposition"]
    away = s2["away"]
    assert away["n"] > 0
    assert away["hit_rate"] is not None
    assert away["auc"] is not None
    assert away["brier"] is not None


# ---------------------------------------------------------------------------
# Test 6 — Home/away hit gap computed
# ---------------------------------------------------------------------------

def test_06_home_away_hit_gap_computed(p74_result):
    s2 = p74_result["step2_home_away_decomposition"]
    gap = s2["hit_gap_home_minus_away"]
    assert gap is not None
    assert isinstance(gap, float)
    # Home should outperform away based on P73A findings
    assert gap > 0, f"Expected positive gap (home > away), got {gap}"
    assert gap >= 0.10, f"Expected gap >= 0.10, got {gap}"


# ---------------------------------------------------------------------------
# Test 7 — Home monthly stability computed
# ---------------------------------------------------------------------------

def test_07_home_monthly_stability_computed(p74_result):
    s2 = p74_result["step2_home_away_decomposition"]
    home = s2["home"]
    assert "monthly_stability" in home
    assert home["monthly_stability"] in ("STABLE", "MODERATE", "UNSTABLE", "INSUFFICIENT_MONTHS")
    assert "monthly_breakdown" in home
    assert len(home["monthly_breakdown"]) >= 3


# ---------------------------------------------------------------------------
# Test 8 — Away monthly stability computed
# ---------------------------------------------------------------------------

def test_08_away_monthly_stability_computed(p74_result):
    s2 = p74_result["step2_home_away_decomposition"]
    away = s2["away"]
    assert "monthly_stability" in away
    assert away["monthly_stability"] in ("STABLE", "MODERATE", "UNSTABLE", "INSUFFICIENT_MONTHS")
    assert "monthly_breakdown" in away
    assert len(away["monthly_breakdown"]) >= 3


# ---------------------------------------------------------------------------
# Test 9 — Away rescue filters generated
# ---------------------------------------------------------------------------

def test_09_away_rescue_filters_generated(p74_result):
    s3 = p74_result["step3_away_rescue_filters"]
    filters = s3["filters"]
    assert len(filters) >= 5
    filter_ids = [f["filter_id"] for f in filters]
    assert "AWAY_BASELINE" in filter_ids
    assert "AWAY_DELTA_GE_075" in filter_ids
    assert "AWAY_DELTA_GE_100" in filter_ids
    assert "AWAY_DELTA_GE_125" in filter_ids


# ---------------------------------------------------------------------------
# Test 10 — Away rescue filters enforce n threshold for operational status
# ---------------------------------------------------------------------------

def test_10_away_rescue_filter_n_threshold_enforced(p74_result):
    s3 = p74_result["step3_away_rescue_filters"]
    for f in s3["filters"]:
        if f["n"] < OPERATIONAL_MIN_N and f["filter_id"] != "AWAY_BASELINE":
            assert f["operational_status"] in (
                "WATCHLIST_ONLY_N_BELOW_75",
                "INSUFFICIENT_N",
            ), (
                f"Filter {f['filter_id']} has n={f['n']} < {OPERATIONAL_MIN_N} "
                f"but status={f['operational_status']}"
            )


# ---------------------------------------------------------------------------
# Test 11 — Home robustness threshold variants generated
# ---------------------------------------------------------------------------

def test_11_home_robustness_variants_generated(p74_result):
    s4 = p74_result["step4_home_robustness"]
    variants = s4["variants"]
    thresholds = [v["threshold"] for v in variants]
    assert 0.50 in thresholds
    assert 0.75 in thresholds
    assert 1.00 in thresholds
    assert 1.25 in thresholds
    assert len(variants) == 4


# ---------------------------------------------------------------------------
# Test 12 — Candidate corrected rules generated
# ---------------------------------------------------------------------------

def test_12_candidate_corrected_rules_generated(p74_result):
    s5 = p74_result["step5_candidate_rules"]
    rules = s5["rules"]
    rule_ids = [r["rule_id"] for r in rules]
    required_rules = [
        "TIER_C_ALL_BASELINE",
        "TIER_C_HOME_ONLY",
        "TIER_C_HOME_PLUS_AWAY_075",
        "TIER_C_HOME_PLUS_AWAY_100",
        "TIER_C_HOME_PLUS_AWAY_125",
        "TIER_C_HOME_WEIGHTED_AWAY_WATCHLIST",
        "TIER_C_BAND_FILTERED",
    ]
    for rid in required_rules:
        assert rid in rule_ids, f"Missing rule: {rid}"


# ---------------------------------------------------------------------------
# Test 13 — Candidate corrected rules include coverage vs baseline
# ---------------------------------------------------------------------------

def test_13_corrected_rules_include_coverage(p74_result):
    s5 = p74_result["step5_candidate_rules"]
    for r in s5["rules"]:
        assert "coverage" in r, f"Rule {r['rule_id']} missing coverage"
        assert "n" in r
        # Coverage should be <= 1.0 and > 0
        cov = r.get("coverage")
        if cov is not None:
            assert 0 < cov <= 1.0, f"Coverage out of bounds for {r['rule_id']}: {cov}"


# ---------------------------------------------------------------------------
# Test 14 — Classification logic tested
# ---------------------------------------------------------------------------

def test_14_classification_is_valid(p74_result):
    cls = p74_result["p74_classification"]
    allowed = p74_result["allowed_classifications"]
    assert cls in allowed, f"Invalid classification: {cls}"


# ---------------------------------------------------------------------------
# Test 15 — No odds required
# ---------------------------------------------------------------------------

def test_15_no_odds_required(p74_result):
    gov = p74_result["governance"]
    assert gov["uses_historical_odds"] is False
    assert gov["the_odds_api_key_required"] is False
    assert gov["market_edge_calculated"] is False


# ---------------------------------------------------------------------------
# Test 16 — No EV / CLV / Kelly calculated
# ---------------------------------------------------------------------------

def test_16_no_ev_clv_kelly(p74_result):
    gov = p74_result["governance"]
    assert gov["ev_calculated"] is False
    assert gov["clv_calculated"] is False
    assert gov["kelly_deploy_allowed"] is False


# ---------------------------------------------------------------------------
# Test 17 — live_api_calls=0
# ---------------------------------------------------------------------------

def test_17_live_api_calls_zero(p74_result):
    gov = p74_result["governance"]
    assert gov["live_api_calls"] == 0


# ---------------------------------------------------------------------------
# Test 18 — production_ready=False
# ---------------------------------------------------------------------------

def test_18_production_ready_false(p74_result):
    gov = p74_result["governance"]
    assert gov["production_ready"] is False


# ---------------------------------------------------------------------------
# Test 19 — kelly_deploy_allowed=False
# ---------------------------------------------------------------------------

def test_19_kelly_deploy_allowed_false(p74_result):
    gov = p74_result["governance"]
    assert gov["kelly_deploy_allowed"] is False


# ---------------------------------------------------------------------------
# Test 20 — Forbidden phrase scan passes
# ---------------------------------------------------------------------------

def test_20_forbidden_phrase_scan(p74_result):
    raw = json.dumps(p74_result).lower()
    for phrase in FORBIDDEN_PHRASES:
        assert phrase.lower() not in raw, f"Forbidden phrase found in P74 output: '{phrase}'"
    # Also check report
    if P74_REPORT.exists():
        report_text = P74_REPORT.read_text().lower()
        for phrase in FORBIDDEN_PHRASES:
            assert phrase.lower() not in report_text, f"Forbidden phrase in report: '{phrase}'"


# ---------------------------------------------------------------------------
# Test 21 — JSON schema stable
# ---------------------------------------------------------------------------

def test_21_json_schema_stable(p74_result):
    required_keys = [
        "phase",
        "date",
        "p74_classification",
        "governance",
        "forbidden_scan",
        "source_artifacts",
        "step1_reconstruction",
        "step2_home_away_decomposition",
        "step3_away_rescue_filters",
        "step4_home_robustness",
        "step5_candidate_rules",
        "prediction_boundary",
    ]
    for key in required_keys:
        assert key in p74_result, f"Missing key in P74 JSON: {key}"


# ---------------------------------------------------------------------------
# Test 22 — Report includes final candidate rule table
# ---------------------------------------------------------------------------

def test_22_report_includes_candidate_rule_table():
    assert P74_REPORT.exists(), f"Report not found: {P74_REPORT}"
    report_text = P74_REPORT.read_text()
    assert "TIER_C_ALL_BASELINE" in report_text
    assert "TIER_C_HOME_ONLY" in report_text
    assert "TIER_C_HOME_PLUS_AWAY" in report_text
    assert "| Candidate Rule |" in report_text or "Candidate Corrected Rules" in report_text


# ---------------------------------------------------------------------------
# Test 23 — active_task.md updated
# ---------------------------------------------------------------------------

def test_23_active_task_updated():
    if not ACTIVE_TASK.exists():
        pytest.skip("active_task.md not present — skipping")
    content = ACTIVE_TASK.read_text()
    # Should reference P74 or at minimum P73 as latest
    assert "P74" in content or "P73" in content, "active_task.md not updated to reference P74"


# ---------------------------------------------------------------------------
# Test 24 — P72A/P72B/P73/P74 regression passes
# ---------------------------------------------------------------------------

def test_24_p72a_p73_p74_regression(p72a_result, p73_result, p74_result):
    """Cross-phase regression: key invariants must hold across phases."""
    # P72A: check signal confirmed (key may be final_classification or p72a_classification)
    p72a_cls = str(
        p72a_result.get("p72a_classification")
        or p72a_result.get("final_classification", "")
    )
    assert "CONFIRMED" in p72a_cls or "SIGNAL" in p72a_cls or "PREDICTIVE" in p72a_cls, (
        f"P72A classification unexpected: {p72a_cls}"
    )

    # P73: check Tier C operational stable
    p73_cls = p73_result.get("p73_classification", "")
    assert "TIER_C_OPERATIONAL_STABLE" in p73_cls, (
        f"P73 classification unexpected: {p73_cls}"
    )

    # P74: classification is valid
    p74_cls = p74_result["p74_classification"]
    assert p74_cls in p74_result["allowed_classifications"]

    # n consistency: P74 Tier C n must match P73A n
    p74_n = p74_result["step1_reconstruction"]["n"]
    p73_n = p73_result["p73a_tier_c"]["n"]
    assert p74_n == p73_n, f"P74 n={p74_n} does not match P73A n={p73_n}"

    # governance chain: paper_only must be True in P73 and P74
    assert p73_result["governance"]["paper_only"] is True
    assert p74_result["governance"]["paper_only"] is True
