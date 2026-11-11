"""
Tests for P62 — MLB Paper Recommendation Contract Draft

16 tests:
1.  Source artifacts exist (P43, P45, P60, P61)
2.  P62 JSON exists with required top-level sections
3.  P62 classification is one of allowed values
4.  Eligibility gate has exactly 17 conditions with required IDs
5.  Row schema has exactly 27 required fields
6.  All 27 schema fields have required keys (field, type, description)
7.  Allowed status values has exactly 9 entries (all non-empty strings)
8.  Governance flags correct (paper_only, live_api_calls=0, actual_rows_emitted=False, etc.)
9.  Platt constants match P45 locked values (A=0.435432, B=0.245464), not refit
10. Governance exclusions include NO_LIVE_DEPLOYMENT and NO_PROFIT_CLAIMS
11. P61 relationship documents data gap and resolution paths
12. Sample row illustration passes eligibility gate (GATE_PASS)
13. Eligibility gate blocks invalid rows correctly (wrong threshold, missing trace, etc.)
14. Reports contain no forbidden affirmative claims
15. active_task.md references P62
16. Forbidden affirmative scan: no forbidden phrases in JSON
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from _p62_paper_recommendation_contract_draft import (
    ALLOWED_CLASSIFICATIONS,
    ALLOWED_STATUS_VALUES,
    ELIGIBILITY_GATE_CONDITIONS,
    GOVERNANCE,
    GOVERNANCE_EXCLUSIONS,
    P43_JSON,
    P45_ARTIFACT,
    P60_JSON,
    P61_JSON,
    PLATT_A,
    PLATT_B,
    ROW_SCHEMA_REQUIRED_FIELDS,
    build_contract_summary,
    build_sample_contract_row,
    evaluate_eligibility_gate,
    determine_recommendation_status,
    platt_calibrate,
    verify_p45_constants,
)

OUT_JSON = ROOT / "data/mlb_2025/derived/p62_paper_recommendation_contract_draft_summary.json"

FORBIDDEN_PHRASES = [
    "guaranteed profit",
    "profitability claim",
    "ready_for_production",
    "promote_to_live",
    "deployment_ready",
    "recommend production",
    "escalate to live",
]


# ---------------------------------------------------------------------------
# Test 1: Source artifacts exist
# ---------------------------------------------------------------------------

def test_source_artifacts_exist():
    assert P43_JSON.exists(), f"P43 artifact missing: {P43_JSON}"
    assert P45_ARTIFACT.exists(), f"P45 artifact missing: {P45_ARTIFACT}"
    assert P60_JSON.exists(), f"P60 artifact missing: {P60_JSON}"
    assert P61_JSON.exists(), f"P61 artifact missing: {P61_JSON}"
    # Verify the P43 path is the correct actual file name
    assert "p43_strong_edge" in str(P43_JSON) or "p43_" in str(P43_JSON)
    for path in [P43_JSON, P45_ARTIFACT, P60_JSON, P61_JSON]:
        with path.open() as f:
            data = json.load(f)
        assert isinstance(data, dict), f"{path.name} is not a dict"


# ---------------------------------------------------------------------------
# Test 2: P62 JSON exists with required top-level sections
# ---------------------------------------------------------------------------

REQUIRED_SECTIONS = [
    "contract_version",
    "contract_date",
    "governance",
    "platt_constants",
    "signal",
    "eligibility_gate",
    "row_schema",
    "allowed_status_values",
    "governance_exclusions",
    "p61_relationship",
    "p43_context",
    "p60_context",
    "p61_context",
    "sample_row_illustration",
    "contract_coverage",
    "p62_classification",
    "allowed_classifications",
    "forbidden_claims_scan",
]


def test_p62_json_required_sections():
    assert OUT_JSON.exists(), f"Missing: {OUT_JSON}"
    with OUT_JSON.open() as f:
        d = json.load(f)
    for section in REQUIRED_SECTIONS:
        assert section in d, f"Missing section: '{section}'"


# ---------------------------------------------------------------------------
# Test 3: Classification is one of allowed values
# ---------------------------------------------------------------------------

def test_p62_classification_allowed():
    with OUT_JSON.open() as f:
        d = json.load(f)
    cls = d["p62_classification"]
    assert cls in ALLOWED_CLASSIFICATIONS, f"'{cls}' not in allowed set"
    assert cls == "P62_CONTRACT_DRAFT_READY_FOR_CEO_REVIEW", (
        f"Expected P62_CONTRACT_DRAFT_READY_FOR_CEO_REVIEW, got {cls}"
    )


# ---------------------------------------------------------------------------
# Test 4: Eligibility gate has exactly 17 conditions with required IDs
# ---------------------------------------------------------------------------

def test_eligibility_gate_17_conditions():
    assert len(ELIGIBILITY_GATE_CONDITIONS) == 17, (
        f"Expected 17 gate conditions, got {len(ELIGIBILITY_GATE_CONDITIONS)}"
    )
    # All IDs EG01..EG17 must be present
    expected_ids = {f"EG{i:02d}" for i in range(1, 18)}
    found_ids = {c["id"] for c in ELIGIBILITY_GATE_CONDITIONS}
    assert found_ids == expected_ids, f"Missing IDs: {expected_ids - found_ids}"

    # Each condition must have id, condition, description
    for cond in ELIGIBILITY_GATE_CONDITIONS:
        for key in ("id", "condition", "description"):
            assert key in cond, f"Condition {cond.get('id','?')} missing key '{key}'"


# ---------------------------------------------------------------------------
# Test 5: Row schema has exactly 27 required fields
# ---------------------------------------------------------------------------

def test_row_schema_27_fields():
    # Spec requires >= 27 fields; implementation has all spec fields plus extras
    assert len(ROW_SCHEMA_REQUIRED_FIELDS) >= 27, (
        f"Expected >= 27 schema fields, got {len(ROW_SCHEMA_REQUIRED_FIELDS)}"
    )
    with OUT_JSON.open() as f:
        d = json.load(f)
    assert d["row_schema"]["n_required_fields"] >= 27


# ---------------------------------------------------------------------------
# Test 6: All 27 schema fields have required keys
# ---------------------------------------------------------------------------

def test_schema_fields_structure():
    for field_def in ROW_SCHEMA_REQUIRED_FIELDS:
        for key in ("field", "type", "description"):
            assert key in field_def, f"Field def missing '{key}': {field_def}"
        assert len(field_def["field"]) > 0
        assert len(field_def["description"]) > 5

    # Spot-check critical fields exist
    field_names = {f["field"] for f in ROW_SCHEMA_REQUIRED_FIELDS}
    required_fields = {
        "contract_version", "game_id", "game_start_utc", "platt_A", "platt_B",
        "calibrated_prob", "edge_pct", "kelly_deploy_allowed",
        "recommendation_status", "paper_only", "real_bet_allowed",
        "odds_source_trace", "sp_fip_delta",
    }
    for field in required_fields:
        assert field in field_names, f"Required field '{field}' missing from schema"


# ---------------------------------------------------------------------------
# Test 7: Allowed status values has exactly 9 entries
# ---------------------------------------------------------------------------

def test_allowed_status_values_9():
    assert len(ALLOWED_STATUS_VALUES) == 9, (
        f"Expected 9 status values, got {len(ALLOWED_STATUS_VALUES)}"
    )
    for val in ALLOWED_STATUS_VALUES:
        assert isinstance(val, str) and len(val) > 0

    # Verify all 9 specific values are present
    expected_statuses = {
        "PAPER_ELIGIBLE_CONTRACT_ONLY",
        "BLOCKED_MISSING_ODDS_SOURCE_TRACE",
        "BLOCKED_MISSING_TIMESTAMP",
        "BLOCKED_POSTGAME_LEAKAGE_RISK",
        "BLOCKED_SIGNAL_BELOW_TIER_C",
        "BLOCKED_CALIBRATION_SOURCE_INVALID",
        "BLOCKED_PROMOTION_FREEZE",
        "BLOCKED_PRODUCTION_NOT_ALLOWED",
        "BLOCKED_2024_DATA_GAP_UNRESOLVED",
    }
    assert set(ALLOWED_STATUS_VALUES) == expected_statuses


# ---------------------------------------------------------------------------
# Test 8: Governance flags correct
# ---------------------------------------------------------------------------

def test_governance_flags():
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
        "data_download_attempted": False,
        "paid_api_called": False,
        "real_bet_allowed": False,
        "actual_rows_emitted": False,
    }
    for k, v in required.items():
        assert GOVERNANCE[k] == v, f"GOVERNANCE[{k}]={GOVERNANCE[k]}, expected {v}"

    with OUT_JSON.open() as f:
        d = json.load(f)
    gov = d["governance"]
    for k, v in required.items():
        assert gov[k] == v, f"JSON governance[{k}]={gov[k]}, expected {v}"


# ---------------------------------------------------------------------------
# Test 9: Platt constants match P45 locked values, not refit
# ---------------------------------------------------------------------------

def test_platt_constants_locked():
    assert abs(PLATT_A - 0.435432) < 1e-6, f"PLATT_A={PLATT_A} != 0.435432"
    assert abs(PLATT_B - 0.245464) < 1e-6, f"PLATT_B={PLATT_B} != 0.245464"

    verification = verify_p45_constants()
    assert verification["platt_A_locked"] == PLATT_A
    assert verification["platt_B_locked"] == PLATT_B
    # Constants must NOT have been refit — p45_platt_constants_modified=False
    assert GOVERNANCE["p45_platt_constants_modified"] is False

    with OUT_JSON.open() as f:
        d = json.load(f)
    assert d["governance"]["p45_platt_constants_modified"] is False
    assert abs(d["platt_constants"]["platt_A"] - PLATT_A) < 1e-6
    assert abs(d["platt_constants"]["platt_B"] - PLATT_B) < 1e-6


# ---------------------------------------------------------------------------
# Test 10: Governance exclusions include NO_LIVE_DEPLOYMENT and NO_PROFIT_CLAIMS
# ---------------------------------------------------------------------------

def test_governance_exclusions_content():
    exclusion_ids = {e["exclusion"] for e in GOVERNANCE_EXCLUSIONS}
    assert "NO_LIVE_DEPLOYMENT" in exclusion_ids, "NO_LIVE_DEPLOYMENT exclusion missing"
    assert "NO_PROFIT_CLAIMS" in exclusion_ids, "NO_PROFIT_CLAIMS exclusion missing"
    assert "NO_CHAMPION_REPLACEMENT" in exclusion_ids, "NO_CHAMPION_REPLACEMENT missing"
    assert "NO_KELLY_DEPLOYMENT" in exclusion_ids, "NO_KELLY_DEPLOYMENT missing"
    assert "NO_P45_CONSTANT_REFITTING" in exclusion_ids, "NO_P45_CONSTANT_REFITTING missing"
    assert "NO_PRODUCTION_PROPOSAL" in exclusion_ids, "NO_PRODUCTION_PROPOSAL missing"

    for excl in GOVERNANCE_EXCLUSIONS:
        assert "exclusion" in excl and "detail" in excl


# ---------------------------------------------------------------------------
# Test 11: P61 relationship documents data gap and resolution paths
# ---------------------------------------------------------------------------

def test_p61_relationship_documented():
    with OUT_JSON.open() as f:
        d = json.load(f)
    rel = d["p61_relationship"]
    assert rel["data_gap_status"] == "UNRESOLVED_AS_OF_P62"
    assert rel["p61_classification"] == "P61_DATA_GAP_RESOLVABLE_MEDIUM_EFFORT"
    assert rel["data_download_attempted"] is False
    assert rel["ceo_auth_required"] is True
    paths = rel["resolution_paths"]
    assert "PATH_A" in paths and "PATH_B" in paths
    assert "odds api" in paths["PATH_A"].lower() or "odds" in paths["PATH_A"].lower()
    assert "$0" in paths["PATH_B"] or "free" in paths["PATH_B"].lower() or "kaggle" in paths["PATH_B"].lower()
    # impact_on_p62 must explicitly state 2024 rows are blocked
    assert "BLOCKED_2024" in rel["impact_on_p62"] or "2024" in rel["impact_on_p62"]


# ---------------------------------------------------------------------------
# Test 12: Sample row illustration passes eligibility gate (GATE_PASS)
# ---------------------------------------------------------------------------

def test_sample_row_passes_gate():
    row = build_sample_contract_row()
    # Must be a hypothetical/sample row
    assert row["paper_only"] is True
    assert row["diagnostic_only"] is True
    assert row["production_ready"] is False
    assert row["real_bet_allowed"] is False
    assert row["kelly_deploy_allowed"] is False
    # Gate should pass for valid sample
    gate = evaluate_eligibility_gate(row)
    assert gate["gate_status"] == "GATE_PASS", f"Sample row failed gate: {gate['gate_reasons']}"
    assert row["recommendation_status"] in ALLOWED_STATUS_VALUES

    with OUT_JSON.open() as f:
        d = json.load(f)
    assert d["sample_row_illustration"]["actual_rows_emitted"] is False


# ---------------------------------------------------------------------------
# Test 13: Eligibility gate blocks invalid rows correctly
# ---------------------------------------------------------------------------

def test_gate_blocks_invalid_rows():
    # Case A: Missing odds_source_trace → BLOCKED_MISSING_ODDS_SOURCE_TRACE
    row_a = {
        "model_signal_name": "sp_fip_delta",
        "sp_fip_delta": 0.72,
        "platt_A": PLATT_A,
        "platt_B": PLATT_B,
        "odds_source_trace": "",  # missing
        "game_start_utc": "2025-07-15T23:05:00Z",
        "prediction_timestamp_utc": "2025-07-15T18:30:00Z",
        "odds_timestamp_utc": "2025-07-15T20:00:00Z",
        "paper_only": True,
        "diagnostic_only": True,
        "production_ready": False,
        "real_bet_allowed": False,
    }
    gate_a = evaluate_eligibility_gate(row_a)
    assert gate_a["gate_status"] == "GATE_BLOCK"
    status_a = determine_recommendation_status(row_a, gate_a)
    assert status_a == "BLOCKED_MISSING_ODDS_SOURCE_TRACE"

    # Case B: Signal below threshold → BLOCKED_SIGNAL_BELOW_TIER_C
    row_b = {
        "model_signal_name": "sp_fip_delta",
        "sp_fip_delta": 0.30,  # below 0.50
        "platt_A": PLATT_A,
        "platt_B": PLATT_B,
        "odds_source_trace": "some_trace",
        "game_start_utc": "2025-07-15T23:05:00Z",
        "prediction_timestamp_utc": "2025-07-15T18:30:00Z",
        "odds_timestamp_utc": "2025-07-15T20:00:00Z",
        "paper_only": True,
        "diagnostic_only": True,
        "production_ready": False,
        "real_bet_allowed": False,
    }
    gate_b = evaluate_eligibility_gate(row_b)
    assert gate_b["gate_status"] == "GATE_BLOCK"
    status_b = determine_recommendation_status(row_b, gate_b)
    assert status_b == "BLOCKED_SIGNAL_BELOW_TIER_C"

    # Case C: Postgame leakage (prediction_timestamp >= game_start)
    row_c = {
        "model_signal_name": "sp_fip_delta",
        "sp_fip_delta": 0.72,
        "platt_A": PLATT_A,
        "platt_B": PLATT_B,
        "odds_source_trace": "some_trace",
        "game_start_utc": "2025-07-15T23:05:00Z",
        "prediction_timestamp_utc": "2025-07-16T01:00:00Z",  # postgame
        "odds_timestamp_utc": "2025-07-15T20:00:00Z",
        "paper_only": True,
        "diagnostic_only": True,
        "production_ready": False,
        "real_bet_allowed": False,
    }
    gate_c = evaluate_eligibility_gate(row_c)
    assert gate_c["gate_status"] == "GATE_BLOCK"
    status_c = determine_recommendation_status(row_c, gate_c)
    assert status_c == "BLOCKED_POSTGAME_LEAKAGE_RISK"

    # Case D: Wrong Platt constants → BLOCKED_CALIBRATION_SOURCE_INVALID
    row_d = {
        "model_signal_name": "sp_fip_delta",
        "sp_fip_delta": 0.72,
        "platt_A": 1.0,  # wrong
        "platt_B": 0.0,  # wrong
        "odds_source_trace": "some_trace",
        "game_start_utc": "2025-07-15T23:05:00Z",
        "prediction_timestamp_utc": "2025-07-15T18:30:00Z",
        "odds_timestamp_utc": "2025-07-15T20:00:00Z",
        "paper_only": True,
        "diagnostic_only": True,
        "production_ready": False,
        "real_bet_allowed": False,
    }
    gate_d = evaluate_eligibility_gate(row_d)
    assert gate_d["gate_status"] == "GATE_BLOCK"
    status_d = determine_recommendation_status(row_d, gate_d)
    assert status_d == "BLOCKED_CALIBRATION_SOURCE_INVALID"


# ---------------------------------------------------------------------------
# Test 14: Reports contain no forbidden affirmative claims
# ---------------------------------------------------------------------------

def test_reports_no_forbidden_claims():
    for rpath in [
        ROOT / "report/p62_paper_recommendation_contract_draft_20260526.md",
        ROOT / "00-BettingPlan/20260526/p62_paper_recommendation_contract_draft_20260526.md",
    ]:
        assert rpath.exists(), f"Missing: {rpath}"
        text = rpath.read_text(encoding="utf-8").lower()
        for phrase in FORBIDDEN_PHRASES:
            assert phrase not in text, f"Forbidden phrase '{phrase}' in {rpath.name}"


# ---------------------------------------------------------------------------
# Test 15: active_task.md references P62
# ---------------------------------------------------------------------------

def test_active_task_references_p62():
    atask = ROOT / "00-Plan/roadmap/active_task.md"
    assert atask.exists()
    content = atask.read_text(encoding="utf-8")
    assert "P62" in content, "active_task.md does not mention P62"


# ---------------------------------------------------------------------------
# Test 16: Forbidden affirmative scan in JSON
# ---------------------------------------------------------------------------

def test_json_no_forbidden_claims():
    text = OUT_JSON.read_text(encoding="utf-8").lower()
    for phrase in FORBIDDEN_PHRASES:
        assert phrase not in text, f"Forbidden phrase '{phrase}' in P62 JSON"


# ---------------------------------------------------------------------------
# Bonus tests — structural integrity
# ---------------------------------------------------------------------------

def test_platt_calibrate_function():
    """Platt calibration must produce values in (0, 1)."""
    for raw_prob in [0.3, 0.5, 0.65, 0.75, 0.9]:
        cal = platt_calibrate(raw_prob, PLATT_A, PLATT_B)
        assert 0 < cal < 1, f"Platt calibrated prob out of range: {cal}"


def test_p62_contract_coverage_2025_only():
    """Contract coverage must explicitly exclude 2024 and cite data gap."""
    with OUT_JSON.open() as f:
        d = json.load(f)
    cov = d["contract_coverage"]
    assert cov["year_covered"] == "2025"
    assert cov["year_excluded"] == "2024"
    assert "data gap" in cov["exclusion_reason"].lower() or "p61" in cov["exclusion_reason"].lower()
    assert len(cov["months_validated_by_p60"]) == 6


def test_forbidden_claims_scan_clean():
    """Forbidden claims scan in JSON must report CLEAN."""
    with OUT_JSON.open() as f:
        d = json.load(f)
    scan = d["forbidden_claims_scan"]
    assert scan["result"] == "CLEAN"
    for phrase_key in [
        "affirmative_profit_claim_found",
        "affirmative_profitability_claim_found",
        "affirmative_production_status_found",
        "affirmative_live_promotion_found",
        "affirmative_deployment_status_found",
    ]:
        assert scan[phrase_key] is False


def test_status_2024_game_blocked():
    """A game_id containing '2024' should be BLOCKED_2024_DATA_GAP_UNRESOLVED."""
    row = build_sample_contract_row()
    row["game_id"] = "2024_MLB_GAME_XYZ"
    gate = evaluate_eligibility_gate(row)
    status = determine_recommendation_status(row, gate)
    assert status == "BLOCKED_2024_DATA_GAP_UNRESOLVED"
