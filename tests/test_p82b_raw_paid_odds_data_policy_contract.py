"""
Tests for P82B — Raw Paid Odds Data Storage / Commit Policy Contract
=====================================================================
54 named tests + 1 parametrized regression (15 artifacts = P72A→P82B) = 69 total
All tests operate in paper_only=True, diagnostic_only=True mode.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).parent.parent
DERIVED = REPO_ROOT / "data" / "mlb_2025" / "derived"
SCRIPT_PATH = REPO_ROOT / "scripts" / "_p82b_raw_paid_odds_data_policy_contract.py"

# Regression: P72A → P82B (15 artifacts)
P_SERIES_ARTIFACTS: list[str] = [
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
    "p80_market_edge_reentry_readiness_contract_summary.json",
    "p81_legal_odds_dataset_validator_contract_summary.json",
    "p82a_real_legal_odds_intake_gate_summary.json",
    "p82b_raw_paid_odds_data_policy_contract_summary.json",
]


# ---------------------------------------------------------------------------
# Module-scoped fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def module():
    """Import P82B script module via importlib."""
    spec = importlib.util.spec_from_file_location("p82b", SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def summary(module):
    """Run P82B main() and return the summary dict."""
    return module.main()


# ---------------------------------------------------------------------------
# Tests 1-7: P82A source artifact + P82A state verification
# ---------------------------------------------------------------------------

def test_01_p82a_artifact_loads(summary):
    assert summary["step1_p82a_verification"]["status"] == "PASS"


def test_02_p82a_classification_verified(summary):
    assert (
        summary["step1_p82a_verification"]["p82a_classification"]
        == "P82A_REAL_LEGAL_ODDS_INTAKE_GATE_READY"
    )


def test_03_p82_remains_blocked_no_real_dataset(summary):
    assert summary["p82_unlock_status"] == "BLOCKED_NO_REAL_DATASET"


def test_04_p82_unlocked_false(summary):
    assert summary["governance_snapshot"]["p82_unlocked"] is False


def test_05_raw_data_policy_requirement_verified(summary):
    assert summary["step1_p82a_verification"]["raw_data_policy_field_present"] is True


def test_06_contains_api_key_false_requirement(summary):
    assert summary["step1_p82a_verification"]["contains_api_key_must_be_false"] is True


def test_07_only_real_legal_dataset_unlocks_p82(summary):
    assert (
        summary["step1_p82a_verification"]["only_real_legal_dataset_unlocks"] is True
    )


# ---------------------------------------------------------------------------
# Tests 8-17: Artifact classes
# ---------------------------------------------------------------------------

def test_08_artifact_classes_generated(summary):
    assert summary["step2_artifact_classes"]["class_count"] == 9


def test_09_raw_paid_odds_data_class_exists(summary):
    assert "RAW_PAID_ODDS_DATA" in summary["step2_artifact_classes"]["class_ids"]


def test_10_raw_paid_odds_data_cannot_commit(summary):
    assert summary["step3_commit_policy_matrix"]["RAW_PAID_ODDS_DATA"]["can_commit"] is False


def test_11_raw_paid_odds_data_is_local_only(summary):
    storage = summary["step3_commit_policy_matrix"]["RAW_PAID_ODDS_DATA"]["storage_location"]
    assert "local" in storage.lower()


def test_12_raw_free_legal_conditional_commit_policy(summary):
    c = summary["step2_artifact_classes"]["classes_by_id"]["RAW_FREE_LEGAL_ODDS_DATA"]
    assert c["default_policy"] == "COMMIT_ALLOWED_ONLY_IF_LICENSE_ALLOWS"


def test_13_validation_manifest_commit_allowed(summary):
    assert summary["step3_commit_policy_matrix"]["VALIDATION_MANIFEST"]["can_commit"] is True


def test_14_checksum_only_record_commit_allowed(summary):
    assert summary["step3_commit_policy_matrix"]["CHECKSUM_ONLY_RECORD"]["can_commit"] is True


def test_15_derived_validation_summary_commit_allowed(summary):
    assert summary["step3_commit_policy_matrix"]["DERIVED_VALIDATION_SUMMARY"]["can_commit"] is True


def test_16_derived_market_edge_summary_commit_allowed_aggregate(summary):
    c = summary["step3_commit_policy_matrix"]["DERIVED_MARKET_EDGE_SUMMARY"]
    assert c["can_commit"] is True
    review_gate = c.get("review_gate", "")
    stop_cond = c.get("stop_condition", "")
    assert "aggregate" in review_gate.lower() or "aggregate" in stop_cond.lower()


def test_17_secret_or_api_key_hard_forbidden(summary):
    c = summary["step3_commit_policy_matrix"]["SECRET_OR_API_KEY"]
    assert c["can_commit"] is False
    assert c["can_stage"] is False


def test_18_mock_fixture_not_market_evidence(summary):
    c = summary["step2_artifact_classes"]["classes_by_id"]["MOCK_FIXTURE"]
    stop_cond = c.get("stop_condition", "")
    review_gate = c.get("review_gate", "")
    assert "mock" in stop_cond.lower() or "mock" in review_gate.lower()


# ---------------------------------------------------------------------------
# Tests 19-21: Commit policy matrix completeness
# ---------------------------------------------------------------------------

def test_19_commit_policy_matrix_generated(summary):
    matrix = {k: v for k, v in summary["step3_commit_policy_matrix"].items() if k != "_meta"}
    assert len(matrix) == 9


def test_20_each_class_has_can_commit(summary):
    matrix = {k: v for k, v in summary["step3_commit_policy_matrix"].items() if k != "_meta"}
    for cls_id, policy in matrix.items():
        assert "can_commit" in policy, f"Missing can_commit for {cls_id}"


def test_21_each_class_has_storage_location(summary):
    matrix = {k: v for k, v in summary["step3_commit_policy_matrix"].items() if k != "_meta"}
    for cls_id, policy in matrix.items():
        assert "storage_location" in policy, f"Missing storage_location for {cls_id}"


def test_22_each_class_has_stop_condition(summary):
    matrix = {k: v for k, v in summary["step3_commit_policy_matrix"].items() if k != "_meta"}
    for cls_id, policy in matrix.items():
        assert "stop_condition" in policy, f"Missing stop_condition for {cls_id}"


# ---------------------------------------------------------------------------
# Tests 23-30: Staging guard contract
# ---------------------------------------------------------------------------

def test_23_staging_guard_contract_generated(summary):
    assert summary["step4_staging_guard"]["guard_id"] == "p82b_staging_guard_v1"


def test_24_guard_blocks_env_file(summary):
    blocks = summary["step4_staging_guard"]["blocks"]
    env_rule = next((b for b in blocks if b["rule_id"] == "BLOCK_ENV_FILE"), None)
    assert env_rule is not None
    assert ".env" in env_rule["file_patterns"]


def test_25_guard_blocks_api_key_patterns(summary):
    blocks = summary["step4_staging_guard"]["blocks"]
    api_rule = next((b for b in blocks if b["rule_id"] == "BLOCK_API_KEY_PATTERN"), None)
    assert api_rule is not None
    assert api_rule["guard_state"] == "BLOCK_SECRET"


def test_26_guard_blocks_raw_paid_csv(summary):
    blocks = summary["step4_staging_guard"]["blocks"]
    raw_rule = next((b for b in blocks if b["rule_id"] == "BLOCK_RAW_PAID_CSV"), None)
    assert raw_rule is not None
    assert raw_rule["guard_state"] == "BLOCK_RAW_PAID_DATA"


def test_27_guard_blocks_odds_2024_real_csv(summary):
    blocks = summary["step4_staging_guard"]["blocks"]
    real_rule = next((b for b in blocks if b["rule_id"] == "BLOCK_REAL_ODDS_FILENAME"), None)
    assert real_rule is not None
    patterns_str = " ".join(real_rule.get("file_patterns", []))
    assert "odds_2024_real" in patterns_str or "real" in patterns_str


def test_28_guard_blocks_contains_api_key_flag(summary):
    blocks = summary["step4_staging_guard"]["blocks"]
    flag_rule = next((b for b in blocks if b["rule_id"] == "BLOCK_CONTAINS_API_KEY_FLAG"), None)
    assert flag_rule is not None
    assert flag_rule["guard_state"] == "BLOCK_SECRET"


def test_29_guard_blocks_row_level_leakage(summary):
    blocks = summary["step4_staging_guard"]["blocks"]
    row_rule = next((b for b in blocks if b["rule_id"] == "BLOCK_ROW_LEVEL_ODDS"), None)
    assert row_rule is not None
    assert row_rule["guard_state"] == "BLOCK_ROW_LEVEL_LEAKAGE"


def test_30_guard_states_generated(summary):
    states = summary["step4_staging_guard"]["guard_states"]
    required = ["STAGE_CLEAN", "BLOCK_RAW_PAID_DATA", "BLOCK_SECRET",
                "BLOCK_UNPOLICIED_ODDS", "BLOCK_ROW_LEVEL_LEAKAGE", "REVIEW_REQUIRED"]
    for state in required:
        assert state in states, f"Missing guard state: {state}"


# ---------------------------------------------------------------------------
# Tests 31-35: Manifest integration
# ---------------------------------------------------------------------------

def test_31_manifest_integration_generated(summary):
    assert "raw_data_policy" in summary["step5_manifest_integration"]


def test_32_raw_data_policy_allowed_values_defined(summary):
    allowed = summary["step5_manifest_integration"]["raw_data_policy"]["allowed_values"]
    assert "LOCAL_ONLY_HASH_COMMITTED" in allowed
    assert "DERIVED_ONLY_COMMIT" in allowed
    assert "COMMIT_ALLOWED_LICENSE_VERIFIED" in allowed
    assert "MOCK_ONLY" in allowed


def test_33_raw_data_policy_forbidden_values_defined(summary):
    forbidden = summary["step5_manifest_integration"]["raw_data_policy"]["forbidden_values"]
    assert "UNKNOWN" in forbidden
    assert "COMMIT_RAW_PAID_DATA" in forbidden
    assert "EMBED_SECRET" in forbidden
    assert "UNLICENSED_SOURCE" in forbidden


def test_34_storage_policy_allowed_values_defined(summary):
    allowed = summary["step5_manifest_integration"]["storage_policy"]["allowed_values"]
    assert "LOCAL_ONLY" in allowed
    assert "DERIVED_ONLY_IN_REPO" in allowed


def test_35_commit_policy_allowed_values_defined(summary):
    allowed = summary["step5_manifest_integration"]["commit_policy"]["allowed_values"]
    assert "HASH_ONLY_NO_RAW_DATA" in allowed
    assert "MANIFEST_AND_DERIVED_ONLY" in allowed


# ---------------------------------------------------------------------------
# Tests 36-40: Future workflow
# ---------------------------------------------------------------------------

def test_36_future_workflow_generated(summary):
    wf = summary["step6_future_workflow"]["workflow_steps"]
    assert len(wf) == 7


def test_37_workflow_stores_raw_paid_outside_git(summary):
    wf = summary["step6_future_workflow"]["workflow_steps"]
    step2 = next((s for s in wf if s["step"] == 2), None)
    assert step2 is not None
    assert "local" in step2["where"].lower()


def test_38_workflow_commits_only_manifest_hash_derived(summary):
    wf = summary["step6_future_workflow"]["workflow_steps"]
    step5 = next((s for s in wf if s["step"] == 5), None)
    assert step5 is not None
    action = step5["action"].lower()
    assert "manifest" in action or "checksum" in action


def test_39_workflow_requires_p81_validation_before_p82(summary):
    wf = summary["step6_future_workflow"]["workflow_steps"]
    step4 = next((s for s in wf if s["step"] == 4), None)
    assert step4 is not None
    action = step4["action"].lower()
    assert "p81" in action or "validator" in action


def test_40_p82_remains_blocked_until_real_dataset(summary):
    assert summary["step6_future_workflow"]["p82_remains_blocked"] is True


# ---------------------------------------------------------------------------
# Tests 41-47: No prohibited operations
# ---------------------------------------------------------------------------

def test_41_no_odds_file_created(summary):
    # Check no raw odds DATA files (csv / jsonl) were created — pipeline _summary.json artifacts are OK
    raw_csv = list(DERIVED.glob("*odds*.csv"))
    raw_jsonl = list(DERIVED.glob("*raw_odds*.jsonl"))
    # Exclude policy/contract/summary files that mention "odds" in their name
    raw_json = [
        f for f in DERIVED.glob("*odds*.json")
        if "_summary.json" not in f.name and "_contract" not in f.name and "_gate" not in f.name
    ]
    assert len(raw_csv) == 0, f"Unexpected odds CSV files: {raw_csv}"
    assert len(raw_jsonl) == 0, f"Unexpected odds JSONL files: {raw_jsonl}"
    assert len(raw_json) == 0, f"Unexpected raw odds JSON files: {raw_json}"


def test_42_no_api_call(summary):
    assert summary["live_api_calls"] == 0


def test_43_no_api_key_access(summary):
    assert summary["governance_snapshot"]["the_odds_api_key_accessed"] is False


def test_44_no_edge_calculated(summary):
    assert summary["governance_snapshot"]["market_edge_evaluated"] is False


def test_45_no_clv_calculated(summary):
    assert summary["governance_snapshot"]["clv_calculated"] is False


def test_46_no_ev_calculated(summary):
    assert summary["ev_clv_kelly_computed"] is False


def test_47_no_kelly_calculated(summary):
    assert summary["governance_snapshot"]["kelly_calculated"] is False


# ---------------------------------------------------------------------------
# Tests 48-49: Governance invariants
# ---------------------------------------------------------------------------

def test_48_live_api_calls_zero(summary):
    assert summary["live_api_calls"] == 0


def test_49_production_ready_false(summary):
    assert summary["governance_snapshot"]["production_ready"] is False


def test_50_kelly_deploy_allowed_false(summary):
    assert summary["governance_snapshot"]["kelly_deploy_allowed"] is False


# ---------------------------------------------------------------------------
# Tests 51-54: Scan, schema, reports, active_task
# ---------------------------------------------------------------------------

def test_51_forbidden_phrase_scan_passes(summary):
    assert summary["step8_forbidden_scan"]["scan_passed"] is True
    assert summary["step8_forbidden_scan"]["violations_count"] == 0


def test_52_json_schema_stable(summary):
    required_keys = [
        "p82b_classification",
        "schema_version",
        "snapshot_id",
        "generated_at_utc",
        "governance_snapshot",
        "step1_p82a_verification",
        "step2_artifact_classes",
        "step3_commit_policy_matrix",
        "step4_staging_guard",
        "step5_manifest_integration",
        "step6_future_workflow",
        "step7_source_artifacts",
        "step8_forbidden_scan",
        "live_api_calls",
        "ev_clv_kelly_computed",
        "p82_unlock_status",
        "p82b_current_status",
    ]
    for key in required_keys:
        assert key in summary, f"Missing key: {key}"


def test_53_report_includes_policy_matrix(summary):
    report_path = (
        REPO_ROOT / "report" / "p82b_raw_paid_odds_data_policy_contract_20260526.md"
    )
    assert report_path.exists(), "P82B report file not found"
    text = report_path.read_text()
    assert "Commit Policy Matrix" in text or "policy matrix" in text.lower()


def test_54_report_includes_staging_guard(summary):
    report_path = (
        REPO_ROOT / "report" / "p82b_raw_paid_odds_data_policy_contract_20260526.md"
    )
    text = report_path.read_text()
    assert "Staging Guard" in text or "STAGE_CLEAN" in text


def test_55_active_task_md_updated(summary):
    active_task_path = REPO_ROOT / "00-Plan" / "roadmap" / "active_task.md"
    assert active_task_path.exists()
    text = active_task_path.read_text()
    assert "P82B" in text


# ---------------------------------------------------------------------------
# Test 56 (collected as 15): P72A→P82B regression
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("artifact_name", P_SERIES_ARTIFACTS)
def test_56_p72a_through_p82b_regression(artifact_name):
    path = DERIVED / artifact_name
    assert path.exists(), f"Missing artifact: {artifact_name}"
    data = json.loads(path.read_text())
    assert isinstance(data, dict), f"Not a dict: {artifact_name}"
    assert len(data) >= 3, f"Suspiciously small dict: {artifact_name}"
