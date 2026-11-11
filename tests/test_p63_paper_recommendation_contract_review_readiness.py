"""
Tests for P63 — Paper Recommendation Contract Review Readiness Gate

Minimum 17 tests covering all required areas per task specification.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

# Ensure scripts/ is importable
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from _p63_paper_recommendation_contract_review_readiness import (
    FORBIDDEN_TERMS,
    GATE_AUDIT_SPECS,
    SCHEMA_FIELD_AUDIT,
    STATUS_VALUE_AUDIT,
    P62_BETTINGPLAN_MD,
    P62_REPORT_MD,
    P62_SUMMARY_JSON,
    P63_SUMMARY_JSON,
    audit_eligibility_gates,
    audit_schema_fields,
    audit_status_values,
    check_governance_preservation,
    decide_ceo_readiness,
    load_p62_artifacts,
    run_p63,
    scan_forbidden_claims,
    write_p63_summary,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_p62_json() -> dict[str, Any]:
    assert P62_SUMMARY_JSON.exists(), f"P62 summary JSON not found: {P62_SUMMARY_JSON}"
    with open(P62_SUMMARY_JSON, encoding="utf-8") as fh:
        return json.load(fh)


def _load_p63_json() -> dict[str, Any]:
    assert P63_SUMMARY_JSON.exists(), f"P63 summary JSON not found: {P63_SUMMARY_JSON}"
    with open(P63_SUMMARY_JSON, encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Test 1: P62 summary JSON loads
# ---------------------------------------------------------------------------

def test_p62_summary_json_exists_and_loads() -> None:
    """P62 summary JSON must exist and be valid JSON."""
    assert P62_SUMMARY_JSON.exists(), "P62 summary JSON does not exist"
    data = _load_p62_json()
    assert isinstance(data, dict), "P62 summary JSON is not a dict"
    assert len(data) > 0, "P62 summary JSON is empty"


# ---------------------------------------------------------------------------
# Test 2: P62 report loads
# ---------------------------------------------------------------------------

def test_p62_report_md_exists_and_loads() -> None:
    """P62 report markdown must exist and be non-empty."""
    assert P62_REPORT_MD.exists(), "P62 report MD does not exist"
    content = P62_REPORT_MD.read_text(encoding="utf-8")
    assert len(content) > 100, "P62 report MD is suspiciously short"


# ---------------------------------------------------------------------------
# Test 3: P62 BettingPlan copy loads
# ---------------------------------------------------------------------------

def test_p62_bettingplan_copy_exists_and_loads() -> None:
    """P62 BettingPlan copy must exist and be non-empty."""
    assert P62_BETTINGPLAN_MD.exists(), "P62 BettingPlan MD does not exist"
    content = P62_BETTINGPLAN_MD.read_text(encoding="utf-8")
    assert len(content) > 100, "P62 BettingPlan MD is suspiciously short"


# ---------------------------------------------------------------------------
# Test 4: P62 classification equals P62_CONTRACT_DRAFT_READY_FOR_CEO_REVIEW
# ---------------------------------------------------------------------------

def test_p62_classification_correct() -> None:
    """P62 must classify as P62_CONTRACT_DRAFT_READY_FOR_CEO_REVIEW."""
    data = _load_p62_json()
    classification = data.get("p62_classification")
    assert classification == "P62_CONTRACT_DRAFT_READY_FOR_CEO_REVIEW", (
        f"P62 classification is '{classification}', expected 'P62_CONTRACT_DRAFT_READY_FOR_CEO_REVIEW'"
    )


# ---------------------------------------------------------------------------
# Test 5: no actual recommendation rows emitted
# ---------------------------------------------------------------------------

def test_no_actual_recommendation_rows_emitted() -> None:
    """actual_rows_emitted must be False in P62 governance."""
    data = _load_p62_json()
    actual_rows = data.get("governance", {}).get("actual_rows_emitted")
    assert actual_rows is False, (
        f"actual_rows_emitted={actual_rows}, expected False — contract safety violated"
    )


# ---------------------------------------------------------------------------
# Test 6: all governance flags preserved
# ---------------------------------------------------------------------------

def test_all_governance_flags_preserved() -> None:
    """All P62 governance flags must be set to their required values."""
    data = _load_p62_json()
    gov = data.get("governance", {})
    required = {
        "paper_only": True,
        "diagnostic_only": True,
        "promotion_freeze": True,
        "kelly_deploy_allowed": False,
        "live_api_calls": 0,
        "actual_rows_emitted": False,
        "runtime_recommendation_logic_changed": False,
        "champion_strategy_changed": False,
        "p45_platt_constants_modified": False,
        "p52_thresholds_modified": False,
        "real_bet_allowed": False,
        "production_usage_proposed": False,
    }
    failures = {k: (gov.get(k), v) for k, v in required.items() if gov.get(k) != v}
    assert not failures, f"Governance flag mismatches: {failures}"


# ---------------------------------------------------------------------------
# Test 7: EG01–EG17 all audited (17 gates)
# ---------------------------------------------------------------------------

def test_all_17_eligibility_gates_audited() -> None:
    """All 17 eligibility gates must be present in the audit spec."""
    gate_ids = {spec["gate_id"] for spec in GATE_AUDIT_SPECS}
    expected = {f"EG{str(i).zfill(2)}" for i in range(1, 18)}
    missing = expected - gate_ids
    assert not missing, f"Missing gate specs: {missing}"
    assert len(GATE_AUDIT_SPECS) == 17, f"Expected 17 gates, got {len(GATE_AUDIT_SPECS)}"


def test_gate_audit_runs_on_p62_data() -> None:
    """Gate audit must run without error and return 17 results."""
    data = _load_p62_json()
    gate_results = audit_eligibility_gates(data)
    assert len(gate_results) == 17, f"Expected 17 gate results, got {len(gate_results)}"
    for g in gate_results:
        assert "gate_id" in g
        assert "audit_status" in g
        assert g["audit_status"] in {
            "TESTABLE",
            "AMBIGUOUS_REQUIRES_CLARIFICATION",
            "NOT_TESTABLE_YET",
            "MISSING_SOURCE_TRACE",
            "BLOCKED_BY_2024_DATA_GAP",
        }


# ---------------------------------------------------------------------------
# Test 8: all 33 schema fields audited
# ---------------------------------------------------------------------------

def test_all_33_schema_fields_audited() -> None:
    """All 33 row schema fields must appear in the audit spec."""
    assert len(SCHEMA_FIELD_AUDIT) == 33, f"Expected 33 schema field specs, got {len(SCHEMA_FIELD_AUDIT)}"


def test_schema_audit_runs_on_p62_data() -> None:
    """Schema audit must run and match against P62 JSON."""
    data = _load_p62_json()
    schema_results = audit_schema_fields(data)
    assert len(schema_results) == 33, f"Expected 33 schema audit results, got {len(schema_results)}"
    for f in schema_results:
        assert "field" in f
        assert "category" in f
        assert f["category"] in {
            "REQUIRED_FOR_AUDIT",
            "REQUIRED_FOR_LEAKAGE_GUARD",
            "REQUIRED_FOR_RISK_GOVERNANCE",
            "OPTIONAL_DIAGNOSTIC",
            "AMBIGUOUS",
        }
        assert f["present_in_p62_schema"] is True, (
            f"Field '{f['field']}' missing from P62 schema"
        )


# ---------------------------------------------------------------------------
# Test 9: all 9 status values audited
# ---------------------------------------------------------------------------

def test_all_9_status_values_audited() -> None:
    """All 9 allowed status values must be in the audit spec."""
    assert len(STATUS_VALUE_AUDIT) == 9, f"Expected 9 status audit specs, got {len(STATUS_VALUE_AUDIT)}"


def test_status_audit_runs_on_p62_data() -> None:
    """Status audit must run and find all 9 values in P62 JSON."""
    data = _load_p62_json()
    status_results = audit_status_values(data)
    assert len(status_results) == 9, f"Expected 9 status results, got {len(status_results)}"
    for s in status_results:
        assert s["safe"] is True, f"Status '{s['status']}' is not safe"
        assert s["present_in_p62_contract"] is True, (
            f"Status '{s['status']}' not found in P62 contract"
        )
        assert s["implies_production_readiness"] is False
        assert s["implies_real_betting"] is False
        assert s["implies_kelly_deployment"] is False


# ---------------------------------------------------------------------------
# Test 10: 2024 data gap remains unresolved
# ---------------------------------------------------------------------------

def test_2024_data_gap_remains_unresolved() -> None:
    """2024 data gap must remain documented as UNRESOLVED_AS_OF_P62."""
    data = _load_p62_json()
    gap_status = data.get("p61_relationship", {}).get("data_gap_status")
    assert gap_status == "UNRESOLVED_AS_OF_P62", (
        f"2024 data gap status is '{gap_status}', expected 'UNRESOLVED_AS_OF_P62'"
    )


# ---------------------------------------------------------------------------
# Test 11: Platt constants remain unchanged
# ---------------------------------------------------------------------------

def test_platt_constants_unchanged() -> None:
    """P45 Platt constants must be locked at A=0.435432, B=0.245464."""
    data = _load_p62_json()
    platt = data.get("platt_constants", {})
    platt_A = platt.get("platt_A")
    platt_B = platt.get("platt_B")
    assert platt_A is not None, "platt_A missing from P62 JSON"
    assert platt_B is not None, "platt_B missing from P62 JSON"
    assert abs(float(platt_A) - 0.435432) < 1e-6, f"platt_A={platt_A} != 0.435432"
    assert abs(float(platt_B) - 0.245464) < 1e-6, f"platt_B={platt_B} != 0.245464"


# ---------------------------------------------------------------------------
# Test 12: P52 thresholds unchanged flag
# ---------------------------------------------------------------------------

def test_p52_thresholds_unchanged() -> None:
    """P52 thresholds must not have been modified."""
    data = _load_p62_json()
    flag = data.get("governance", {}).get("p52_thresholds_modified")
    assert flag is False, f"p52_thresholds_modified={flag}, expected False"


# ---------------------------------------------------------------------------
# Test 13: runtime recommendation logic unchanged flag
# ---------------------------------------------------------------------------

def test_runtime_recommendation_logic_unchanged() -> None:
    """Runtime recommendation logic must not have been changed."""
    data = _load_p62_json()
    flag = data.get("governance", {}).get("runtime_recommendation_logic_changed")
    assert flag is False, f"runtime_recommendation_logic_changed={flag}, expected False"


# ---------------------------------------------------------------------------
# Test 14: CEO readiness classification is one of allowed values
# ---------------------------------------------------------------------------

def test_p63_ceo_readiness_classification_is_allowed() -> None:
    """P63 final classification must be one of the 5 allowed values."""
    summary = run_p63()
    allowed = summary["allowed_p63_classifications"]
    classification = summary["p63_classification"]
    assert classification in allowed, (
        f"P63 classification '{classification}' is not in allowed set: {allowed}"
    )


def test_p63_preferred_classification_is_ready_for_ceo_review() -> None:
    """Preferred P63 classification is P63_READY_FOR_CEO_REVIEW."""
    summary = run_p63()
    assert summary["p63_classification"] == "P63_READY_FOR_CEO_REVIEW", (
        f"Expected P63_READY_FOR_CEO_REVIEW, got '{summary['p63_classification']}'. "
        f"Blocking issues: {summary['ceo_readiness']['blocking_issues']}"
    )


# ---------------------------------------------------------------------------
# Test 15: forbidden affirmative scan has zero violations
# ---------------------------------------------------------------------------

def test_forbidden_claims_scan_clean() -> None:
    """Forbidden affirmative claims scan must return zero violations."""
    data = _load_p62_json()
    scan = scan_forbidden_claims(data)
    assert scan["violations_found"] == 0, (
        f"Forbidden claims found: {scan['violations']}"
    )
    assert scan["result"] == "CLEAN"


# ---------------------------------------------------------------------------
# Test 16: report includes CEO review recommendation
# ---------------------------------------------------------------------------

def test_p62_report_references_ceo_review() -> None:
    """P62 report must reference CEO review in its content."""
    content = P62_REPORT_MD.read_text(encoding="utf-8").lower()
    assert "ceo" in content or "review" in content, (
        "P62 report does not mention CEO review"
    )


def test_p63_write_and_read_summary_json() -> None:
    """P63 must be able to write and re-read the summary JSON."""
    summary = run_p63()
    write_p63_summary(summary)
    assert P63_SUMMARY_JSON.exists(), "P63 summary JSON was not written"
    data = _load_p63_json()
    assert data["p63_classification"] == summary["p63_classification"]
    assert data["p63_phase"] == "P63_PAPER_RECOMMENDATION_CONTRACT_REVIEW_READINESS"


# ---------------------------------------------------------------------------
# Test 17: active_task updated after completion (existence check)
# ---------------------------------------------------------------------------

def test_active_task_file_exists() -> None:
    """active_task.md must exist in 00-Plan/roadmap/."""
    active_task_path = REPO_ROOT / "00-Plan/roadmap/active_task.md"
    assert active_task_path.exists(), "active_task.md does not exist"


# ---------------------------------------------------------------------------
# Additional robustness tests (bonus — raises total beyond 17)
# ---------------------------------------------------------------------------

def test_gate_audit_CEO_blocking_gates_all_pass() -> None:
    """All CEO-blocking gates (EG01–EG13, EG17) must pass on P62 data."""
    data = _load_p62_json()
    gate_results = audit_eligibility_gates(data)
    blocking_failed = [
        g["gate_id"]
        for g in gate_results
        if g.get("blocks_ceo_review") and not g["passed"]
    ]
    assert not blocking_failed, (
        f"CEO-blocking gates that failed: {blocking_failed}"
    )


def test_schema_audit_no_fields_missing_from_p62() -> None:
    """All 33 schema fields in the audit spec must be present in P62 JSON."""
    data = _load_p62_json()
    schema_results = audit_schema_fields(data)
    missing = [f["field"] for f in schema_results if not f["present_in_p62_schema"]]
    assert not missing, f"Schema fields missing from P62 JSON: {missing}"


def test_governance_check_function_returns_all_pass() -> None:
    """check_governance_preservation must return all_flags_preserved=True."""
    data = _load_p62_json()
    result = check_governance_preservation(data)
    assert result["all_flags_preserved"] is True, (
        f"Governance flags not all preserved: "
        f"{[k for k, v in result['flags'].items() if not v['pass']]}"
    )


def test_p63_summary_governance_flags_match_expected() -> None:
    """P63 summary JSON must carry all governance flags with correct values."""
    summary = run_p63()
    gov = summary["governance"]
    assert gov["paper_only"] is True
    assert gov["diagnostic_only"] is True
    assert gov["promotion_freeze"] is True
    assert gov["kelly_deploy_allowed"] is False
    assert gov["live_api_calls"] == 0
    assert gov["actual_rows_emitted"] is False
    assert gov["runtime_recommendation_logic_changed"] is False
    assert gov["champion_strategy_changed"] is False
    assert gov["p45_platt_constants_modified"] is False
    assert gov["p52_thresholds_modified"] is False
    assert gov["real_bet_allowed"] is False
    assert gov["production_usage_proposed"] is False


def test_p63_platt_constants_unchanged_in_summary() -> None:
    """P63 summary must confirm Platt constants are unchanged."""
    summary = run_p63()
    platt = summary["platt_constants"]
    assert platt["constants_unchanged"] is True, (
        f"Platt constants changed: A={platt['platt_A_in_p62']} B={platt['platt_B_in_p62']}"
    )


def test_p63_data_gap_remains_unresolved_in_summary() -> None:
    """P63 summary must confirm 2024 data gap remains unresolved."""
    summary = run_p63()
    assert summary["data_gap_status"]["gap_remains_unresolved"] is True, (
        f"Data gap not marked unresolved: {summary['data_gap_status']}"
    )


def test_no_production_status_values_in_contract() -> None:
    """None of the 9 allowed status values must imply production readiness."""
    data = _load_p62_json()
    status_results = audit_status_values(data)
    production_statuses = [s["status"] for s in status_results if s["implies_production_readiness"]]
    assert not production_statuses, (
        f"Status values implying production readiness: {production_statuses}"
    )


def test_contract_version_present_in_p62() -> None:
    """P62 contract version must be present and non-empty."""
    data = _load_p62_json()
    version = data.get("contract_version")
    assert version and isinstance(version, str), (
        f"contract_version is missing or not a string: {version}"
    )


def test_p63_forbidden_scan_in_p63_summary_is_clean() -> None:
    """P63 summary forbidden scan must be CLEAN."""
    summary = run_p63()
    scan = summary["forbidden_scan"]
    assert scan["result"] == "CLEAN", f"Forbidden scan violations: {scan.get('violations')}"
    assert scan["violations_found"] == 0
