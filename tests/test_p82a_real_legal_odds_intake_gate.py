"""
Test suite for P82A — Real Legal Odds Dataset Intake Gate

56 tests covering:
  - P81 artifact verification (tests 1-7)
  - Intake manifest schema (tests 8-19)
  - Blocker closure checklist (tests 20-23)
  - Unlock decision scenarios (tests 24-32)
  - P82 dry-run scope (tests 33-39)
  - Governance invariants, scan, JSON schema, report (tests 40-55)
  - P72A-P82A parametrized regression (test 56, expands to 13 cases)
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parent.parent
DERIVED = REPO_ROOT / "data" / "mlb_2025" / "derived"
SCRIPT_PATH = REPO_ROOT / "scripts" / "_p82a_real_legal_odds_intake_gate.py"
SUMMARY_PATH = DERIVED / "p82a_real_legal_odds_intake_gate_summary.json"


@pytest.fixture(scope="module")
def summary() -> dict:
    assert SUMMARY_PATH.exists(), f"P82A summary not found: {SUMMARY_PATH}"
    return json.loads(SUMMARY_PATH.read_text())


@pytest.fixture(scope="module")
def module():
    spec = importlib.util.spec_from_file_location("p82a", SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Tests 1-7: P81 artifact and state verification
# ---------------------------------------------------------------------------

def test_01_p81_summary_exists():
    """P81 summary artifact must exist before P82A can run."""
    p81_path = DERIVED / "p81_legal_odds_dataset_validator_contract_summary.json"
    assert p81_path.exists()


def test_02_p81_classification_correct(summary):
    """P81 classification must be MOCK_ONLY before P82A."""
    s1 = summary["step1_p81_verification"]
    assert s1["p81_classification"] == "P81_VALIDATOR_CONTRACT_READY_MOCK_ONLY"


def test_03_p81_validator_script_exists(summary):
    """P81 validator script must exist on disk."""
    assert summary["step1_p81_verification"]["validator_script_exists"] is True


def test_04_p81_input_types_defined(summary):
    """P81 step2 must have input types defined (list)."""
    input_types = summary["step1_p81_verification"]["input_types_defined"]
    assert isinstance(input_types, list)
    assert len(input_types) >= 1


def test_05_p81_mock_cannot_unlock_p82(summary):
    """P81 must confirm mock data cannot unlock P82."""
    s1 = summary["step1_p81_verification"]
    assert s1["checks"]["mock_cannot_unlock_p82"] is True


def test_06_p81_p82_currently_blocked(summary):
    """P81 p82_unlock_status must be BLOCKED_NO_REAL_DATASET."""
    s1 = summary["step1_p81_verification"]
    assert s1["p82_unlock_status"] == "BLOCKED_NO_REAL_DATASET"


def test_07_p81_no_api_call(summary):
    """P81 live_api_calls must be 0."""
    assert summary["step1_p81_verification"]["live_api_calls"] == 0


# ---------------------------------------------------------------------------
# Tests 8-19: Intake manifest schema
# ---------------------------------------------------------------------------

def test_08_manifest_schema_generated(summary):
    """step2 must produce manifest schema."""
    assert "step2_intake_manifest" in summary
    s2 = summary["step2_intake_manifest"]
    assert "manifest_fields" in s2


def test_09_manifest_has_23_fields(summary):
    """Intake manifest must define exactly 23 fields."""
    s2 = summary["step2_intake_manifest"]
    assert s2["manifest_field_count"] == 23
    assert len(s2["manifest_fields"]) == 23


def test_10_manifest_required_fields_present(summary):
    """All 23 field names must be present in the manifest field list."""
    s2 = summary["step2_intake_manifest"]
    field_names = {f["field"] for f in s2["manifest_fields"]}
    required_fields = {
        "manifest_id", "dataset_path", "dataset_type", "season", "source_name",
        "source_license_status", "source_license_evidence_ref", "acquisition_method",
        "acquired_at_utc", "acquired_by", "raw_data_policy", "checksum_hash",
        "row_count", "expected_schema_version", "validator_script", "validator_command",
        "p81_validator_version", "storage_policy", "commit_policy", "contains_api_key",
        "contains_personal_data", "allowed_next_phase", "blocked_next_phase_reason",
    }
    assert required_fields == field_names


def test_11_manifest_dataset_path_not_nullable(summary):
    """manifest.dataset_path must not be nullable."""
    s2 = summary["step2_intake_manifest"]
    field = next(f for f in s2["manifest_fields"] if f["field"] == "dataset_path")
    assert field.get("nullable") is False


def test_12_manifest_dataset_type_required_value(summary):
    """manifest.dataset_type must require REAL_LEGAL_ODDS_DATASET."""
    s2 = summary["step2_intake_manifest"]
    field = next(f for f in s2["manifest_fields"] if f["field"] == "dataset_type")
    assert field.get("required_value") == "REAL_LEGAL_ODDS_DATASET"


def test_13_manifest_license_status_required_value(summary):
    """manifest.source_license_status must require LEGAL_OR_LICENSED."""
    s2 = summary["step2_intake_manifest"]
    field = next(f for f in s2["manifest_fields"] if f["field"] == "source_license_status")
    assert field.get("required_value") == "LEGAL_OR_LICENSED"


def test_14_manifest_license_evidence_ref_not_nullable(summary):
    """manifest.source_license_evidence_ref must not be nullable."""
    s2 = summary["step2_intake_manifest"]
    field = next(f for f in s2["manifest_fields"] if f["field"] == "source_license_evidence_ref")
    assert field.get("nullable") is False


def test_15_manifest_raw_data_policy_forbidden_unknown(summary):
    """manifest.raw_data_policy must forbid UNKNOWN."""
    s2 = summary["step2_intake_manifest"]
    field = next(f for f in s2["manifest_fields"] if f["field"] == "raw_data_policy")
    assert field.get("forbidden_value") == "UNKNOWN"


def test_16_manifest_checksum_not_nullable(summary):
    """manifest.checksum_hash must not be nullable."""
    s2 = summary["step2_intake_manifest"]
    field = next(f for f in s2["manifest_fields"] if f["field"] == "checksum_hash")
    assert field.get("nullable") is False


def test_17_manifest_validator_command_defined(summary):
    """manifest.validator_command must be defined as a non-nullable field."""
    s2 = summary["step2_intake_manifest"]
    field = next(f for f in s2["manifest_fields"] if f["field"] == "validator_command")
    assert field.get("nullable") is False


def test_18_manifest_contains_api_key_required_false(summary):
    """manifest.contains_api_key must require False."""
    s2 = summary["step2_intake_manifest"]
    field = next(f for f in s2["manifest_fields"] if f["field"] == "contains_api_key")
    assert field.get("required_value") is False


def test_19_manifest_allowed_raw_data_policies(summary):
    """Allowed raw_data_policy values must be the three approved options."""
    s2 = summary["step2_intake_manifest"]
    allowed = set(s2["allowed_raw_data_policies"])
    assert allowed == {"COMMIT_ALLOWED", "LOCAL_ONLY_HASH_COMMITTED", "DERIVED_ONLY_COMMIT"}


# ---------------------------------------------------------------------------
# Tests 20-23: Blocker closure checklist
# ---------------------------------------------------------------------------

def test_20_blocker_checklist_generated(summary):
    """step3 must produce a blocker checklist."""
    assert "step3_blocker_checklist" in summary
    s3 = summary["step3_blocker_checklist"]
    assert "checklist" in s3


def test_21_blocker_checklist_12_blockers(summary):
    """Blocker checklist must define exactly 12 blockers."""
    s3 = summary["step3_blocker_checklist"]
    assert s3["total_blockers"] == 12
    assert len(s3["checklist"]) == 12


def test_22_real_data_blockers_are_blocked(summary):
    """All 10 real-data blockers must have status BLOCKED_PENDING_REAL_DATASET."""
    s3 = summary["step3_blocker_checklist"]
    real_blocker_ids = set(s3["all_real_data_blockers"])
    for b in s3["checklist"]:
        if b["blocker_id"] in real_blocker_ids:
            assert b["current_status"] == "BLOCKED_PENDING_REAL_DATASET", (
                f"Expected BLOCKED_PENDING_REAL_DATASET for {b['blocker_id']}, "
                f"got {b['current_status']}"
            )


def test_23_governance_blockers_are_active_guardrails(summary):
    """Both governance blockers must have status ACTIVE_GUARDRAIL."""
    s3 = summary["step3_blocker_checklist"]
    gov_blocker_ids = set(s3["all_governance_blockers"])
    for b in s3["checklist"]:
        if b["blocker_id"] in gov_blocker_ids:
            assert b["current_status"] == "ACTIVE_GUARDRAIL", (
                f"Expected ACTIVE_GUARDRAIL for {b['blocker_id']}, "
                f"got {b['current_status']}"
            )


# ---------------------------------------------------------------------------
# Tests 24-32: Unlock decision scenarios
# ---------------------------------------------------------------------------

def test_24_unlock_decision_generated(summary):
    """step4 must produce unlock decision results."""
    assert "step4_unlock_decision" in summary
    s4 = summary["step4_unlock_decision"]
    assert "scenarios" in s4
    assert "only_real_legal_dataset_unlocks" in s4


def test_25_unlock_fails_for_missing_dataset(summary):
    """MISSING_DATASET scenario must NOT unlock P82."""
    s4 = summary["step4_unlock_decision"]
    assert s4["scenarios"]["MISSING_DATASET"]["can_unlock_p82"] is False


def test_26_unlock_fails_for_mock_fixture(summary):
    """MOCK_FIXTURE scenario must NOT unlock P82."""
    s4 = summary["step4_unlock_decision"]
    assert s4["scenarios"]["MOCK_FIXTURE"]["can_unlock_p82"] is False


def test_27_unlock_fails_for_unknown_source(summary):
    """UNKNOWN_SOURCE scenario must NOT unlock P82."""
    s4 = summary["step4_unlock_decision"]
    assert s4["scenarios"]["UNKNOWN_SOURCE"]["can_unlock_p82"] is False


def test_28_unlock_fails_for_scraping(summary):
    """SCRAPING_PROHIBITED scenario must NOT unlock P82."""
    s4 = summary["step4_unlock_decision"]
    assert s4["scenarios"]["SCRAPING_PROHIBITED"]["can_unlock_p82"] is False


def test_29_unlock_fails_for_bad_policy(summary):
    """BAD_RAW_DATA_POLICY scenario must NOT unlock P82."""
    s4 = summary["step4_unlock_decision"]
    assert s4["scenarios"]["BAD_RAW_DATA_POLICY"]["can_unlock_p82"] is False


def test_30_unlock_fails_for_validator_not_passed(summary):
    """VALIDATOR_NOT_PASSED scenario must NOT unlock P82."""
    s4 = summary["step4_unlock_decision"]
    assert s4["scenarios"]["VALIDATOR_NOT_PASSED"]["can_unlock_p82"] is False


def test_31_unlock_fails_for_api_key_in_data(summary):
    """API_KEY_IN_DATA scenario must NOT unlock P82."""
    s4 = summary["step4_unlock_decision"]
    assert s4["scenarios"]["API_KEY_IN_DATA"]["can_unlock_p82"] is False


def test_32_only_real_legal_unlocks_p82(summary):
    """HYPOTHETICAL_REAL_LEGAL must succeed; only_real_legal_dataset_unlocks must be True."""
    s4 = summary["step4_unlock_decision"]
    assert s4["scenarios"]["HYPOTHETICAL_REAL_LEGAL"]["can_unlock_p82"] is True
    assert s4["only_real_legal_dataset_unlocks"] is True


# ---------------------------------------------------------------------------
# Tests 33-39: P82 dry-run scope
# ---------------------------------------------------------------------------

def test_33_p82_scope_generated(summary):
    """step5 must produce P82 dry-run scope."""
    assert "step5_p82_scope" in summary
    s5 = summary["step5_p82_scope"]
    assert "allowed" in s5 and "prohibited" in s5


def test_34_p82_scope_may_compute_implied_prob(summary):
    """P82 may compute implied probabilities from moneylines."""
    s5 = summary["step5_p82_scope"]
    allowed_text = " ".join(s5["allowed"]).lower()
    assert "implied" in allowed_text or "probabilit" in allowed_text


def test_35_p82_scope_may_compute_paper_only_edge(summary):
    """P82 may compute paper-only edge diagnostics."""
    s5 = summary["step5_p82_scope"]
    allowed_text = " ".join(s5["allowed"]).lower()
    assert "edge" in allowed_text or "paper" in allowed_text


def test_36_p82_scope_may_not_kelly(summary):
    """P82 must NOT compute Kelly or position sizing."""
    s5 = summary["step5_p82_scope"]
    prohibited_text = " ".join(s5["prohibited"]).lower()
    assert "kelly" in prohibited_text


def test_37_p82_scope_may_not_recommend_bets(summary):
    """P82 must NOT recommend bets or wagering amounts."""
    s5 = summary["step5_p82_scope"]
    prohibited_text = " ".join(s5["prohibited"]).lower()
    assert "recommend" in prohibited_text or "bet" in prohibited_text


def test_38_p82_scope_may_not_promote_production(summary):
    """P82 must NOT promote production readiness."""
    s5 = summary["step5_p82_scope"]
    prohibited_text = " ".join(s5["prohibited"]).lower()
    assert "production" in prohibited_text


def test_39_p82_clv_out_of_scope(summary):
    """CLV must be blocked in P82 (reserved for P83)."""
    s5 = summary["step5_p82_scope"]
    assert "clv_status" in s5
    assert "BLOCKED" in s5["clv_status"].upper() or "P83" in s5["clv_status"].upper()


# ---------------------------------------------------------------------------
# Tests 40-55: Governance invariants, scan, JSON schema, report
# ---------------------------------------------------------------------------

def test_40_no_odds_file_present():
    """No real odds dataset file must exist in data/mlb_2025/derived/."""
    odds_patterns = [
        "legal_odds_*.jsonl",
        "real_odds_*.jsonl",
        "odds_dataset_*.jsonl",
    ]
    for pattern in odds_patterns:
        matches = list(DERIVED.glob(pattern))
        assert len(matches) == 0, f"Unexpected odds file found: {matches}"


def test_41_no_api_call_recorded(summary):
    """live_api_calls must be 0."""
    assert summary["live_api_calls"] == 0


def test_42_no_api_key_access(module):
    """GOVERNANCE['the_odds_api_key_accessed'] must be False."""
    gov = module.GOVERNANCE
    assert gov.get("the_odds_api_key_accessed") is False


def test_43_no_ev_computed(summary):
    """ev_clv_kelly_computed must be False."""
    assert summary["ev_clv_kelly_computed"] is False


def test_44_no_clv_in_p82a(summary):
    """step5 ev_kelly_clv_computed_in_p82a must be False."""
    s5 = summary["step5_p82_scope"]
    assert s5.get("ev_kelly_clv_computed_in_p82a") is False


def test_45_no_edge_calc_in_p82a(module):
    """GOVERNANCE['market_edge_evaluated'] must be False."""
    gov = module.GOVERNANCE
    assert gov.get("market_edge_evaluated") is False


def test_46_no_kelly_in_p82a(module):
    """GOVERNANCE['kelly_calculated'] must be False."""
    gov = module.GOVERNANCE
    assert gov.get("kelly_calculated") is False


def test_47_live_api_calls_zero(module):
    """GOVERNANCE['live_api_calls'] must be 0."""
    gov = module.GOVERNANCE
    assert gov.get("live_api_calls") == 0


def test_48_production_ready_false(summary):
    """GOVERNANCE production_ready must be False."""
    gov = summary["governance_snapshot"]
    assert gov["production_ready"] is False


def test_49_kelly_deploy_allowed_false(summary):
    """GOVERNANCE kelly_deploy_allowed must be False."""
    gov = summary["governance_snapshot"]
    assert gov["kelly_deploy_allowed"] is False


def test_50_forbidden_scan_passes(summary):
    """Forbidden scan must PASS with 0 violations."""
    s7 = summary["step7_forbidden_scan"]
    assert s7["scan_passed"] is True
    assert s7["violations_count"] == 0


def test_51_json_schema_stable(summary):
    """P82A JSON must have all required top-level keys."""
    required_keys = {
        "p82a_classification",
        "schema_version",
        "snapshot_id",
        "generated_at_utc",
        "governance_snapshot",
        "step1_p81_verification",
        "step2_intake_manifest",
        "step3_blocker_checklist",
        "step4_unlock_decision",
        "step5_p82_scope",
        "step6_source_artifacts",
        "step7_forbidden_scan",
        "live_api_calls",
        "ev_clv_kelly_computed",
        "p82_unlock_status",
        "p82a_current_status",
    }
    missing = required_keys - set(summary.keys())
    assert missing == set(), f"Missing top-level keys: {missing}"


def test_52_report_includes_manifest_schema():
    """Generated report must include the manifest schema table."""
    report_path = REPO_ROOT / "report" / "p82a_real_legal_odds_intake_gate_20260526.md"
    assert report_path.exists()
    content = report_path.read_text()
    assert "Intake Manifest Schema" in content
    assert "dataset_type" in content


def test_53_report_includes_blocker_table():
    """Generated report must include the blocker closure table."""
    report_path = REPO_ROOT / "report" / "p82a_real_legal_odds_intake_gate_20260526.md"
    content = report_path.read_text()
    assert "Blocker Closure Checklist" in content
    assert "REAL_DATASET_PRESENT" in content


def test_54_report_includes_unlock_decision():
    """Generated report must include the unlock decision section."""
    report_path = REPO_ROOT / "report" / "p82a_real_legal_odds_intake_gate_20260526.md"
    content = report_path.read_text()
    assert "Unlock Decision" in content
    assert "HYPOTHETICAL_REAL_LEGAL" in content


def test_55_classification_is_intake_gate_ready(summary):
    """P82A classification must be P82A_REAL_LEGAL_ODDS_INTAKE_GATE_READY."""
    assert summary["p82a_classification"] == "P82A_REAL_LEGAL_ODDS_INTAKE_GATE_READY"


# ---------------------------------------------------------------------------
# Test 56: Parametrized P72A-P82A regression (13 artifacts)
# ---------------------------------------------------------------------------

P_SERIES_ARTIFACTS = [
    ("P72A", "p72a_odds_free_strategy_accuracy_backtest_summary.json"),
    ("P72B", "p72b_objective_metric_contract_summary.json"),
    ("P73",  "p73_tier_stability_and_sample_expansion_summary.json"),
    ("P74",  "p74_tier_c_home_away_bias_correction_summary.json"),
    ("P75A", "p75a_tier_c_corrected_rule_validator_summary.json"),
    ("P75B", "p75b_calibration_diagnostics_corrected_tier_c_summary.json"),
    ("P76",  "p76_corrected_tier_c_final_rule_selection_summary.json"),
    ("P77",  "p77_prediction_only_shadow_tracker_contract_summary.json"),
    ("P78",  "p78_monthly_shadow_tracker_report_template_summary.json"),
    ("P79A", "p79a_tier_b_trigger_readiness_contract_summary.json"),
    ("P79B", "p79b_tier_b_vs_tier_c_comparison_harness_summary.json"),
    ("P80",  "p80_market_edge_reentry_readiness_contract_summary.json"),
    ("P81",  "p81_legal_odds_dataset_validator_contract_summary.json"),
    ("P82A", "p82a_real_legal_odds_intake_gate_summary.json"),
]


@pytest.mark.parametrize("phase,filename", P_SERIES_ARTIFACTS, ids=[p for p, _ in P_SERIES_ARTIFACTS])
def test_56_regression_artifact_exists_and_loads(phase: str, filename: str):
    """All P-series summary artifacts (P72A through P82A) must exist and be valid JSON."""
    path = DERIVED / filename
    assert path.exists(), f"[{phase}] Artifact missing: {path}"
    data = json.loads(path.read_text())
    assert isinstance(data, dict), f"[{phase}] Artifact is not a JSON object"
    assert len(data) > 0, f"[{phase}] Artifact is empty"
    # Governance check: live_api_calls must be 0 where present
    if "live_api_calls" in data:
        assert data["live_api_calls"] == 0, f"[{phase}] live_api_calls != 0"
    # Production readiness check where governance snapshot present
    gov = data.get("governance_snapshot", {})
    if "production_ready" in gov:
        assert gov["production_ready"] is False, f"[{phase}] production_ready=True FORBIDDEN"
    if "kelly_deploy_allowed" in gov:
        assert gov["kelly_deploy_allowed"] is False, f"[{phase}] kelly_deploy_allowed=True FORBIDDEN"
