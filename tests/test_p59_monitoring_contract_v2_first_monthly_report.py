"""
P59 test suite — Monitoring Contract V2 First Monthly Report.
22 tests (T01–T22).
"""

from __future__ import annotations

import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

P59_SCRIPT = ROOT / "scripts/_p59_monitoring_contract_v2_first_monthly_report.py"
P59_JSON = ROOT / "data/mlb_2025/derived/p59_monitoring_contract_v2_first_monthly_report_summary.json"
P58_JSON = ROOT / "data/mlb_2025/derived/p58_monitoring_contract_v2_monthly_report_template_summary.json"
P57_JSON = ROOT / "data/mlb_2025/derived/p57_monitoring_contract_v2_annotation_integration_summary.json"
P52_JSON = ROOT / "data/mlb_2025/derived/p52_monitoring_contract_v2_summary.json"
REPORT_MD = ROOT / "report/p59_monitoring_contract_v2_first_monthly_report_20260526.md"
BETTING_PLAN_MD = ROOT / "00-BettingPlan/20260526/p59_monitoring_contract_v2_first_monthly_report_20260526.md"


@pytest.fixture(scope="module")
def p59() -> dict:
    assert P59_JSON.exists(), f"P59 output JSON not found: {P59_JSON}"
    return json.loads(P59_JSON.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def p57() -> dict:
    assert P57_JSON.exists(), f"P57 artifact not found: {P57_JSON}"
    return json.loads(P57_JSON.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def p58() -> dict:
    assert P58_JSON.exists(), f"P58 artifact not found: {P58_JSON}"
    return json.loads(P58_JSON.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def p52() -> dict:
    assert P52_JSON.exists(), f"P52 artifact not found: {P52_JSON}"
    return json.loads(P52_JSON.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# T01 — P59 script file exists
# ---------------------------------------------------------------------------

def test_T01_p59_script_exists() -> None:
    assert P59_SCRIPT.exists(), f"P59 script not found: {P59_SCRIPT}"


# ---------------------------------------------------------------------------
# T02 — P59 output JSON exists and is valid
# ---------------------------------------------------------------------------

def test_T02_output_json_exists_and_valid(p59: dict) -> None:
    assert isinstance(p59, dict), "P59 output is not a dict"
    assert "final_p59_classification" in p59


# ---------------------------------------------------------------------------
# T03 — P59 references P58 template as source
# ---------------------------------------------------------------------------

def test_T03_references_p58_template(p59: dict) -> None:
    assert "template_source" in p59
    assert "P58" in p59["template_source"]


# ---------------------------------------------------------------------------
# T04 — Source artifacts are listed and expected files referenced
# ---------------------------------------------------------------------------

def test_T04_source_artifacts_listed(p59: dict) -> None:
    arts = p59.get("source_artifacts", {})
    for key in ["jsonl", "p44t", "p52", "p53", "p55", "p56", "p57", "p58"]:
        assert key in arts, f"source_artifacts missing key: {key!r}"


# ---------------------------------------------------------------------------
# T05 — Report month is 2025-09 (Sep 2025 HISTORICAL_DIAGNOSTIC_FIRST_REPORT)
# ---------------------------------------------------------------------------

def test_T05_report_month_is_sep_2025(p59: dict) -> None:
    assert p59.get("report_month") == "2025-09"


# ---------------------------------------------------------------------------
# T06 — Report type indicates HISTORICAL_DIAGNOSTIC_FIRST_REPORT (Sep fallback)
# ---------------------------------------------------------------------------

def test_T06_report_type_historical_diagnostic(p59: dict) -> None:
    assert "HISTORICAL_DIAGNOSTIC" in p59.get("report_type", "").upper()


# ---------------------------------------------------------------------------
# T07 — global_status section has all 16 required fields
# ---------------------------------------------------------------------------

REQUIRED_GLOBAL_STATUS_FIELDS = [
    "report_month",
    "batch_n",
    "global_status",
    "global_alert_level",
    "global_alert_reasons",
    "edge_status",
    "calibration_status",
    "sample_status",
    "data_gap_status",
    "raw_edge_mean",
    "raw_edge_ci_low",
    "raw_edge_ci_high",
    "platt_ece",
    "platt_brier",
    "p52_thresholds_used",
    "source_trace",
]


def test_T07_global_status_has_all_required_fields(p59: dict) -> None:
    gs = p59.get("global_status", {})
    missing = [f for f in REQUIRED_GLOBAL_STATUS_FIELDS if f not in gs]
    assert not missing, f"global_status missing fields: {missing}"


# ---------------------------------------------------------------------------
# T08 — batch_n is 98 (Sep 2025 Tier C count from P44T)
# ---------------------------------------------------------------------------

def test_T08_batch_n_is_98(p59: dict) -> None:
    assert p59["global_status"]["batch_n"] == 98


# ---------------------------------------------------------------------------
# T09 — global_alert_level is RED (CALIBRATION_CRITICAL: platt_ece > 0.12)
# ---------------------------------------------------------------------------

def test_T09_global_alert_level_is_red(p59: dict) -> None:
    assert p59["global_status"]["global_alert_level"] == "RED"


# ---------------------------------------------------------------------------
# T10 — global_status is MONITORING_ALERT_DIAGNOSTIC
# ---------------------------------------------------------------------------

def test_T10_global_status_is_alert_diagnostic(p59: dict) -> None:
    assert p59["global_status"]["global_status"] == "MONITORING_ALERT_DIAGNOSTIC"


# ---------------------------------------------------------------------------
# T11 — calibration_status is CALIBRATION_ALERT
# ---------------------------------------------------------------------------

def test_T11_calibration_status_is_alert(p59: dict) -> None:
    assert p59["global_status"]["calibration_status"] == "CALIBRATION_ALERT"


# ---------------------------------------------------------------------------
# T12 — sample_status is SAMPLE_INSUFFICIENT (n=98 < 100)
# ---------------------------------------------------------------------------

def test_T12_sample_status_is_insufficient(p59: dict) -> None:
    assert p59["global_status"]["sample_status"] == "SAMPLE_INSUFFICIENT"


# ---------------------------------------------------------------------------
# T13 — edge_status is EDGE_WITHIN_THRESHOLD (ci_low > 0 and mean > 0.07)
# ---------------------------------------------------------------------------

def test_T13_edge_status_within_threshold(p59: dict) -> None:
    assert p59["global_status"]["edge_status"] == "EDGE_WITHIN_THRESHOLD"


# ---------------------------------------------------------------------------
# T14 — platt_ece equals Sep 2025 P53 drilldown value (0.122929)
# ---------------------------------------------------------------------------

def test_T14_platt_ece_matches_p53(p59: dict) -> None:
    platt_ece = p59["global_status"]["platt_ece"]
    assert abs(platt_ece - 0.122929) < 1e-5, f"platt_ece={platt_ece} expected ~0.122929"


# ---------------------------------------------------------------------------
# T15 — raw_edge_mean matches P44T Sep 2025 value (0.108441)
# ---------------------------------------------------------------------------

def test_T15_raw_edge_mean_matches_p44t(p59: dict) -> None:
    edge = p59["global_status"]["raw_edge_mean"]
    assert abs(edge - 0.108441) < 1e-5, f"raw_edge_mean={edge} expected ~0.108441"


# ---------------------------------------------------------------------------
# T16 — band_annotations section carries forward Sep 2025 mid-band record
# ---------------------------------------------------------------------------

def test_T16_band_annotations_carry_forward_present(p59: dict) -> None:
    ba = p59.get("band_annotations", {})
    records = ba.get("records", [])
    assert len(records) >= 1
    rec = records[0]
    assert rec.get("band_label") == "1.00 <= |sp_fip_delta| < 1.25"
    assert rec.get("band_n") == 27


# ---------------------------------------------------------------------------
# T17 — repeated_month_count is incremented to 2 (was 1 in P57)
# ---------------------------------------------------------------------------

def test_T17_repeated_month_count_incremented_to_2(p59: dict, p57: dict) -> None:
    rec = p59["band_annotations"]["records"][0]
    prior_count = p57["sep_2025_mid_band_annotation_carry_forward"]["repeated_month_count"]
    assert rec["repeated_month_count"] == prior_count + 1
    assert rec["repeated_month_count"] == 2


# ---------------------------------------------------------------------------
# T18 — Band annotation action is TRACK_ONLY_NO_REFIT
# ---------------------------------------------------------------------------

def test_T18_band_action_is_track_only(p59: dict) -> None:
    rec = p59["band_annotations"]["records"][0]
    assert rec["action"] == "TRACK_ONLY_NO_REFIT"


# ---------------------------------------------------------------------------
# T19 — Band annotation safety flags are all False
# ---------------------------------------------------------------------------

def test_T19_band_annotation_safety_flags_false(p59: dict) -> None:
    for rec in p59["band_annotations"]["records"]:
        assert rec["should_change_global_status"] is False
        assert rec["should_trigger_refit"] is False
        assert rec["should_change_thresholds"] is False


# ---------------------------------------------------------------------------
# T20 — VAL01–VAL10 all passed
# ---------------------------------------------------------------------------

def test_T20_all_val_rules_passed(p59: dict) -> None:
    val = p59.get("validation_results", {})
    assert val.get("passed") == val.get("rules_run") == 10
    failed = [r for r in val.get("results", []) if not r["passed"]]
    assert not failed, f"Failed validation rules: {[f['rule_id'] for f in failed]}"


# ---------------------------------------------------------------------------
# T21 — Final classification is P59_FIRST_MONTHLY_REPORT_SAMPLE_LIMITED
# ---------------------------------------------------------------------------

def test_T21_final_classification_sample_limited(p59: dict) -> None:
    clf = p59.get("final_p59_classification", "")
    assert clf == "P59_FIRST_MONTHLY_REPORT_SAMPLE_LIMITED", f"Unexpected classification: {clf!r}"


# ---------------------------------------------------------------------------
# T22 — Governance flags: no deployment, no production claims, locked Platt
# ---------------------------------------------------------------------------

def test_T22_governance_flags_compliant(p59: dict) -> None:
    gov = p59.get("governance_summary", {})
    assert gov.get("paper_only") is True, "paper_only must be True"
    assert gov.get("live_api_calls") == 0, "live_api_calls must be 0"
    assert gov.get("promotion_freeze") is True, "promotion_freeze must be True"
    assert gov.get("kelly_deploy_allowed") is False, "kelly_deploy_allowed must be False"
    assert gov.get("p52_thresholds_changed") is False
    assert gov.get("p57_artifact_overwritten") is False
    assert gov.get("p58_artifact_overwritten") is False

    # Platt constants must appear in the report
    platt_str = gov.get("platt_constants", "")
    assert "0.435432" in platt_str, "Platt A=0.435432 must appear in governance_summary"
    assert "0.245464" in platt_str, "Platt B=0.245464 must appear in governance_summary"

    # Forbidden deployment strings must not appear in non-governance areas
    forbidden = ["kelly_deploy_allowed=true", "deploy_to_production=true", "production_usage_proposed=true"]
    non_gov_text = json.dumps({k: v for k, v in p59.items() if k != "governance_summary"}).lower()
    for term in forbidden:
        assert term.lower() not in non_gov_text, f"Forbidden string found outside governance block: {term!r}"
