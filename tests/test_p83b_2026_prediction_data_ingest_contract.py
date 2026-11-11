"""
tests/test_p83b_2026_prediction_data_ingest_contract.py
P83B — 2026 Prediction Data Ingest Contract / Awaiting Stub
55 required tests
paper_only=True | diagnostic_only=True | NO_REAL_BET=True
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Module loading (same pattern as P82C/P83A — register in sys.modules first)
# ---------------------------------------------------------------------------
ROOT   = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "_p83b_2026_prediction_data_ingest_contract.py"
JSON_OUT = ROOT / "data/mlb_2026/derived/p83b_2026_prediction_data_ingest_contract_summary.json"


@pytest.fixture(scope="module")
def p83b_module():
    mod_name = "_p83b_2026_prediction_data_ingest_contract"
    spec = importlib.util.spec_from_file_location(mod_name, SCRIPT)
    mod  = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def p83b_result(p83b_module):
    return p83b_module.run_p83b()


@pytest.fixture(scope="module")
def p83b_json():
    assert JSON_OUT.exists(), f"P83B JSON not found: {JSON_OUT}"
    return json.loads(JSON_OUT.read_text())


# ===========================================================================
# Group 1 — Script exists and is runnable (T01–T03)
# ===========================================================================
class TestScriptExists:
    def test_t01_script_file_exists(self):
        assert SCRIPT.exists(), f"Script not found: {SCRIPT}"

    def test_t02_json_output_exists(self):
        assert JSON_OUT.exists(), f"JSON output not found: {JSON_OUT}"

    def test_t03_report_md_exists(self):
        report = ROOT / "report/p83b_2026_prediction_data_ingest_contract_20260526.md"
        assert report.exists(), f"Report MD not found: {report}"


# ===========================================================================
# Group 2 — Classification and phase (T04–T08)
# ===========================================================================
class TestClassification:
    def test_t04_phase_is_p83b(self, p83b_result):
        assert p83b_result["phase"] == "P83B"

    def test_t05_classification_is_awaiting(self, p83b_result):
        assert p83b_result["p83b_classification"] == "P83B_INGEST_CONTRACT_READY_AWAITING_DATA"

    def test_t06_allowed_classifications_list_contains_awaiting(self, p83b_result):
        assert "P83B_INGEST_CONTRACT_READY_AWAITING_DATA" in p83b_result["allowed_classifications"]

    def test_t07_allowed_classifications_has_four_entries(self, p83b_result):
        assert len(p83b_result["allowed_classifications"]) == 4

    def test_t08_classification_matches_json(self, p83b_result, p83b_json):
        assert p83b_result["p83b_classification"] == p83b_json["p83b_classification"]


# ===========================================================================
# Group 3 — Governance (T09–T15)
# ===========================================================================
class TestGovernance:
    def test_t09_paper_only_true(self, p83b_result):
        assert p83b_result["governance"]["paper_only"] is True

    def test_t10_diagnostic_only_true(self, p83b_result):
        assert p83b_result["governance"]["diagnostic_only"] is True

    def test_t11_live_api_calls_zero(self, p83b_result):
        assert p83b_result["governance"]["live_api_calls"] == 0

    def test_t12_kelly_deploy_false(self, p83b_result):
        assert p83b_result["governance"]["kelly_deploy_allowed"] is False

    def test_t13_production_ready_false(self, p83b_result):
        assert p83b_result["governance"]["production_ready"] is False

    def test_t14_ev_calculated_false(self, p83b_result):
        assert p83b_result["governance"]["ev_calculated"] is False

    def test_t15_clv_calculated_false(self, p83b_result):
        assert p83b_result["governance"]["clv_calculated"] is False


# ===========================================================================
# Group 4 — Step 1: P83A Verification (T16–T22)
# ===========================================================================
class TestStep1P83AVerification:
    def test_t16_verification_ok(self, p83b_result):
        assert p83b_result["step1_p83a_verification"]["verification_ok"] is True

    def test_t17_p83a_classification_ok(self, p83b_result):
        v = p83b_result["step1_p83a_verification"]
        assert v["classification"] == "P83A_AWAITING_2026_DATA"
        assert v["classification_ok"] is True

    def test_t18_schema_rows_zero(self, p83b_result):
        v = p83b_result["step1_p83a_verification"]
        assert v["schema_rows"] == 0
        assert v["schema_rows_zero"] is True

    def test_t19_data_found_false(self, p83b_result):
        assert p83b_result["step1_p83a_verification"]["data_found"] is False

    def test_t20_thresholds_count_five(self, p83b_result):
        v = p83b_result["step1_p83a_verification"]
        assert v["thresholds_count"] >= 5
        assert v["thresholds_ok"] is True

    def test_t21_p82_blocked(self, p83b_result):
        v = p83b_result["step1_p83a_verification"]
        assert v["p82_status"] == "BLOCKED_NO_REAL_DATASET"
        assert v["p82_blocked"] is True

    def test_t22_live_api_ok(self, p83b_result):
        v = p83b_result["step1_p83a_verification"]
        assert v["live_api_calls"] == 0
        assert v["live_api_ok"] is True


# ===========================================================================
# Group 5 — Step 2: Canonical Paths (T23–T30)
# ===========================================================================
class TestStep2CanonicalPaths:
    def test_t23_prediction_rows_jsonl_path(self, p83b_result):
        cp = p83b_result["step2_canonical_paths"]["canonical_paths"]
        assert cp["prediction_rows_jsonl"] == "data/mlb_2026/predictions/mlb_2026_prediction_rows.jsonl"

    def test_t24_derived_accumulation_rows_path(self, p83b_result):
        cp = p83b_result["step2_canonical_paths"]["canonical_paths"]
        assert cp["derived_accumulation_rows_jsonl"] == "data/mlb_2026/derived/p83_live_accumulation_rows.jsonl"

    def test_t25_derived_accumulation_summary_path(self, p83b_result):
        cp = p83b_result["step2_canonical_paths"]["canonical_paths"]
        assert cp["derived_accumulation_latest_summary_json"] == "data/mlb_2026/derived/p83_live_accumulation_latest_summary.json"

    def test_t26_live_report_md_path(self, p83b_result):
        cp = p83b_result["step2_canonical_paths"]["canonical_paths"]
        assert cp["live_report_md"] == "report/p83_live_accumulation_latest.md"

    def test_t27_four_canonical_paths_defined(self, p83b_result):
        cp = p83b_result["step2_canonical_paths"]["canonical_paths"]
        assert len(cp) == 4

    def test_t28_runtime_paper_status_non_canonical(self, p83b_result):
        rph = p83b_result["step2_canonical_paths"]["runtime_paper_output_handling"]
        assert rph["status"] == "NON_CANONICAL"

    def test_t29_runtime_paper_adapter_deferred(self, p83b_result):
        rph = p83b_result["step2_canonical_paths"]["runtime_paper_output_handling"]
        assert rph["current_status"] == "DEFERRED"
        assert rph["adapter_required"] is True

    def test_t30_runtime_paper_reason_mentions_sp_fip_delta(self, p83b_result):
        rph = p83b_result["step2_canonical_paths"]["runtime_paper_output_handling"]
        assert "sp_fip_delta" in rph["reason"]


# ===========================================================================
# Group 6 — Step 3: Row Schema V1 (T31–T39)
# ===========================================================================
class TestStep3RowSchema:
    def test_t31_schema_id(self, p83b_result):
        s = p83b_result["step3_row_schema"]
        assert s["schema_id"] == "P83B_2026_PREDICTION_ROW_SCHEMA_V1"

    def test_t32_schema_version(self, p83b_result):
        assert p83b_result["step3_row_schema"]["version"] == "1.0.0"

    def test_t33_required_fields_count_19(self, p83b_result):
        rf = p83b_result["step3_row_schema"]["required_fields"]
        assert len(rf) == 19

    def test_t34_sp_fip_delta_in_required_fields(self, p83b_result):
        rf = p83b_result["step3_row_schema"]["required_fields"]
        assert "sp_fip_delta" in rf
        assert "abs_sp_fip_delta" in rf

    def test_t35_rule_flag_fields_present(self, p83b_result):
        rf = p83b_result["step3_row_schema"]["required_fields"]
        assert "rule_primary_125_flag" in rf
        assert "rule_shadow_100_flag" in rf
        assert "tier_b_candidate_flag" in rf
        assert "tier_a_watchlist_flag" in rf

    def test_t36_governance_fields_in_required(self, p83b_result):
        rf = p83b_result["step3_row_schema"]["required_fields"]
        for f in ["paper_only", "diagnostic_only", "odds_used", "market_edge_evaluated", "production_ready"]:
            assert f in rf, f"Missing governance field: {f}"

    def test_t37_optional_outcome_fields_count_5(self, p83b_result):
        of = p83b_result["step3_row_schema"]["optional_outcome_fields"]
        assert len(of) == 5

    def test_t38_optional_outcome_fields_content(self, p83b_result):
        of = p83b_result["step3_row_schema"]["optional_outcome_fields"]
        assert "actual_winner" in of
        assert "is_correct" in of
        assert "outcome_available" in of

    def test_t39_governance_enforced_values_season_2026(self, p83b_result):
        gev = p83b_result["step3_row_schema"]["governance_enforced_values"]
        assert gev["season"] == 2026
        assert gev["paper_only"] is True
        assert gev["odds_used"] is False
        assert gev["production_ready"] is False


# ===========================================================================
# Group 7 — Step 4: 2025→2026 Extension Contract (T40–T45)
# ===========================================================================
class TestStep4ExtensionContract:
    def test_t40_contract_id(self, p83b_result):
        ext = p83b_result["step4_extension_contract"]
        assert ext["contract_id"] == "P83B_2025_TO_2026_EXTENSION_CONTRACT_V1"

    def test_t41_no_retraining_required(self, p83b_result):
        ext = p83b_result["step4_extension_contract"]
        assert ext["no_retraining_required"] is True

    def test_t42_no_live_api_required(self, p83b_result):
        ext = p83b_result["step4_extension_contract"]
        assert ext["no_live_api_required"] is True

    def test_t43_source_2025_path_points_to_sp_bullpen_jsonl(self, p83b_result):
        ext = p83b_result["step4_extension_contract"]
        assert "mlb_2025" in ext["source_2025_path"]
        assert "sp_bullpen" in ext["source_2025_path"]

    def test_t44_target_2026_path_is_canonical(self, p83b_result):
        ext = p83b_result["step4_extension_contract"]
        cp = p83b_result["step2_canonical_paths"]["canonical_paths"]
        assert ext["target_2026_path"] == cp["prediction_rows_jsonl"]

    def test_t45_new_fields_for_2026_contains_rule_flags(self, p83b_result):
        ext = p83b_result["step4_extension_contract"]
        nf = ext["new_fields_required_in_2026"]
        assert "rule_primary_125_flag" in nf
        assert "rule_shadow_100_flag" in nf
        assert "tier_b_candidate_flag" in nf
        assert "tier_a_watchlist_flag" in nf


# ===========================================================================
# Group 8 — Step 5: Validator Contract (T46–T52)
# ===========================================================================
class TestStep5ValidatorContract:
    def test_t46_validator_id(self, p83b_result):
        v = p83b_result["step5_validator_contract"]
        assert v["validator_id"] == "P83B_ROW_VALIDATOR_V1"

    def test_t47_eight_checks_defined(self, p83b_result):
        v = p83b_result["step5_validator_contract"]
        assert len(v["checks"]) == 8

    def test_t48_check_ids_complete(self, p83b_result):
        v = p83b_result["step5_validator_contract"]
        ids = {c["check_id"] for c in v["checks"]}
        expected = {
            "required_fields_present",
            "season_2026_enforced",
            "governance_clean",
            "abs_sp_fip_delta_tolerance",
            "rule_flags_deterministic",
            "no_odds_required",
            "outcomes_pending_classification",
            "is_correct_validation",
        }
        assert expected == ids

    def test_t49_season_check_has_required_season_2026(self, p83b_result):
        v = p83b_result["step5_validator_contract"]
        season_check = next(c for c in v["checks"] if c["check_id"] == "season_2026_enforced")
        assert season_check["required_season"] == 2026

    def test_t50_abs_fip_tolerance_value(self, p83b_result):
        v = p83b_result["step5_validator_contract"]
        tol_check = next(c for c in v["checks"] if c["check_id"] == "abs_sp_fip_delta_tolerance")
        assert abs(tol_check["tolerance"] - 1e-6) < 1e-12

    def test_t51_five_snapshot_triggers_defined(self, p83b_result):
        v = p83b_result["step5_validator_contract"]
        assert len(v["snapshot_triggers"]) == 5

    def test_t52_snapshot_trigger_smoke_is_min_n_1(self, p83b_result):
        v = p83b_result["step5_validator_contract"]
        triggers = v["snapshot_triggers"]
        assert triggers["smoke"]["min_n"] == 1
        assert triggers["sample_limited"]["min_n"] == 10
        assert triggers["checkpoint_1"]["min_n"] == 50
        assert triggers["checkpoint_2"]["min_n"] == 100
        assert triggers["operational"]["min_n"] == 200


# ===========================================================================
# Group 9 — Step 6: P83C Prompt (T53–T57)
# ===========================================================================
class TestStep6P83CPrompt:
    def test_t53_future_phase_is_p83c(self, p83b_result):
        p6 = p83b_result["step6_p83c_prompt"]
        assert p6["future_phase"] == "P83C"

    def test_t54_minimum_n_to_trigger_1(self, p83b_result):
        p6 = p83b_result["step6_p83c_prompt"]
        assert p6["minimum_n_to_trigger"] == 1
        assert p6["preferred_n_to_trigger"] == 10

    def test_t55_reference_baseline_hit_rate_2025(self, p83b_result):
        ref = p83b_result["step6_p83c_prompt"]["reference_baseline"]
        assert ref["rule"] == "TIER_C_HOME_PLUS_AWAY_125"
        assert abs(ref["hit_rate_2025"] - 0.6392) < 1e-4
        assert abs(ref["auc_2025"] - 0.5787) < 1e-4
        assert ref["n_2025"] == 316


# ===========================================================================
# Group 10 — Forbidden Scan + P82 Status (T58–T61)
# ===========================================================================
class TestForbiddenScanAndP82:
    def test_t58_forbidden_scan_clean(self, p83b_result):
        assert p83b_result["forbidden_scan"]["result"] == "CLEAN"
        assert p83b_result["forbidden_scan"]["violations"] == []

    def test_t59_p82_blocked_in_result(self, p83b_result):
        assert p83b_result["p82_status"] == "BLOCKED_NO_REAL_DATASET"

    def test_t60_json_forbidden_scan_clean(self, p83b_json):
        assert p83b_json["forbidden_scan"]["result"] == "CLEAN"

    def test_t61_no_forbidden_phrases_in_report_md(self):
        report = ROOT / "report/p83b_2026_prediction_data_ingest_contract_20260526.md"
        text = report.read_text().lower()
        forbidden = ["closing_line_value", '"clv_calculated": true', "profitability confirmed"]
        for phrase in forbidden:
            assert phrase not in text, f"Forbidden phrase in report: {phrase}"


# ===========================================================================
# Group 11 — Regression chain (T62–T69)
# ===========================================================================
class TestRegressionChain:
    """Verify prior P-series JSON artifacts still exist and have correct classifications."""

    @pytest.mark.parametrize("artifact,expected_cls_key,expected_cls_val", [
        (
            "data/mlb_2025/derived/p72a_odds_free_strategy_accuracy_backtest_summary.json",
            "final_classification",
            "P72A_ODDS_FREE_PREDICTIVE_SIGNAL_CONFIRMED",
        ),
        (
            "data/mlb_2025/derived/p72b_objective_metric_contract_summary.json",
            "p72b_classification",
            "P72B_OBJECTIVE_CONTRACT_READY",
        ),
        (
            "data/mlb_2025/derived/p76_corrected_tier_c_final_rule_selection_summary.json",
            "p76_classification",
            "P76_DUAL_FINALISTS_RETAINED_UNTIL_2026_DATA",
        ),
        (
            "data/mlb_2025/derived/p82c_staging_guard_dryrun_scanner_summary.json",
            "p82c_classification",
            "P82C_STAGING_GUARD_DRYRUN_READY",
        ),
        (
            "data/mlb_2026/derived/p83a_2026_live_accumulation_first_snapshot_summary.json",
            "p83a_classification",
            "P83A_AWAITING_2026_DATA",
        ),
    ])
    def test_prior_classification(self, artifact, expected_cls_key, expected_cls_val):
        path = ROOT / artifact
        assert path.exists(), f"Missing artifact: {artifact}"
        data = json.loads(path.read_text())
        assert data[expected_cls_key] == expected_cls_val, (
            f"{artifact}: expected {expected_cls_key}={expected_cls_val!r}, "
            f"got {data.get(expected_cls_key)!r}"
        )

    def test_t67_p83b_json_phase_field(self, p83b_json):
        assert p83b_json["phase"] == "P83B"

    def test_t68_p83b_json_date_field(self, p83b_json):
        assert p83b_json["date"] == "2026-05-26"

    def test_t69_source_artifacts_includes_p83a(self, p83b_json):
        sa = p83b_json["source_artifacts"]
        assert "p83a_json" in sa
        assert "p83b" not in sa["p83a_json"].lower() or "p83a" in sa["p83a_json"].lower()
