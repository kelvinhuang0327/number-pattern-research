"""
tests/test_p83c_2026_prediction_schema_producer_contract.py
P83C — 2026 Prediction Pipeline Stub Generator / Schema Producer Contract
38 required tests
paper_only=True | diagnostic_only=True | NO_REAL_BET=True
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Module loading
# ---------------------------------------------------------------------------
ROOT   = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "_p83c_2026_prediction_schema_producer_contract.py"
JSON_OUT = ROOT / "data/mlb_2026/derived/p83c_2026_prediction_schema_producer_contract_summary.json"
P83B_JSON = ROOT / "data/mlb_2026/derived/p83b_2026_prediction_data_ingest_contract_summary.json"
ACTIVE_TASK_MD = ROOT / "00-Plan/roadmap/active_task.md"
REPORT_MD = ROOT / "report/p83c_2026_prediction_schema_producer_contract_20260526.md"
CANONICAL_PRED_PATH = ROOT / "data/mlb_2026/predictions/mlb_2026_prediction_rows.jsonl"


@pytest.fixture(scope="module")
def p83c_module():
    mod_name = "_p83c_2026_prediction_schema_producer_contract"
    spec = importlib.util.spec_from_file_location(mod_name, SCRIPT)
    mod  = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def p83c_result(p83c_module):
    return p83c_module.run_p83c()


@pytest.fixture(scope="module")
def p83c_json():
    assert JSON_OUT.exists(), f"P83C JSON not found: {JSON_OUT}"
    return json.loads(JSON_OUT.read_text())


# ===========================================================================
# T01 — P83B source artifact loads
# ===========================================================================
class TestT01_P83BArtifactLoads:
    def test_t01_p83b_source_artifact_loads(self):
        """T01: P83B source artifact file exists and is valid JSON."""
        assert P83B_JSON.exists(), f"P83B artifact not found: {P83B_JSON}"
        data = json.loads(P83B_JSON.read_text())
        assert "p83b_classification" in data


# ===========================================================================
# T02 — P83B classification verified
# ===========================================================================
class TestT02_P83BClassification:
    def test_t02_p83b_classification_verified(self, p83c_result):
        """T02: P83B classification = P83B_INGEST_CONTRACT_READY_AWAITING_DATA."""
        s1 = p83c_result["step1_p83b_verification"]
        assert s1["classification_ok"] is True
        assert s1["p83b_classification"] == "P83B_INGEST_CONTRACT_READY_AWAITING_DATA"
        assert s1["verification_ok"] is True


# ===========================================================================
# T03 — Canonical prediction path verified
# ===========================================================================
class TestT03_CanonicalPath:
    def test_t03_canonical_prediction_path_verified(self, p83c_result):
        """T03: Canonical prediction path documented in P83B contract."""
        s1 = p83c_result["step1_p83b_verification"]
        assert s1["prediction_path"] == "data/mlb_2026/predictions/mlb_2026_prediction_rows.jsonl"
        assert s1["canonical_paths_ok"] is True


# ===========================================================================
# T04 — Row schema fields verified (19)
# ===========================================================================
class TestT04_RowSchemaFields:
    def test_t04_row_schema_fields_verified(self, p83c_result):
        """T04: Producer output schema has 19 required fields."""
        s3 = p83c_result["step3_producer_output_schema"]
        assert s3["required_fields_count"] == 19
        assert len(s3["required_fields"]) == 19
        expected_fields = [
            "game_id", "game_date", "season", "home_team", "away_team",
            "predicted_side", "model_probability", "sp_fip_delta", "abs_sp_fip_delta",
            "source_prediction_version", "rule_primary_125_flag", "rule_shadow_100_flag",
            "tier_b_candidate_flag", "tier_a_watchlist_flag", "paper_only",
            "diagnostic_only", "odds_used", "market_edge_evaluated", "production_ready",
        ]
        for f in expected_fields:
            assert f in s3["required_fields"], f"Missing field: {f}"


# ===========================================================================
# T05 — Governance fields verified
# ===========================================================================
class TestT05_GovernanceFields:
    def test_t05_governance_fields_verified(self, p83c_result):
        """T05: Governance enforced values present and correct in producer schema."""
        s3 = p83c_result["step3_producer_output_schema"]
        gov = s3["governance_enforced_values"]
        assert gov["season"] == 2026
        assert gov["paper_only"] is True
        assert gov["diagnostic_only"] is True
        assert gov["odds_used"] is False
        assert gov["market_edge_evaluated"] is False
        assert gov["production_ready"] is False


# ===========================================================================
# T06 — Runtime PAPER remains noncanonical
# ===========================================================================
class TestT06_RuntimePaperNoncanonical:
    def test_t06_runtime_paper_remains_noncanonical(self, p83c_result):
        """T06: P83B contract confirms runtime PAPER output remains NON_CANONICAL."""
        s1 = p83c_result["step1_p83b_verification"]
        assert s1["runtime_paper_noncanonical"] is True


# ===========================================================================
# T07 — Upstream input contract generated
# ===========================================================================
class TestT07_UpstreamInputContractGenerated:
    def test_t07_upstream_input_contract_generated(self, p83c_result):
        """T07: step2 upstream input contract exists and has correct ID."""
        s2 = p83c_result["step2_upstream_input_contract"]
        assert s2["contract_id"] == "P83C_UPSTREAM_INPUT_CONTRACT_V1"
        assert s2["live_api_calls"] == 0
        assert s2["status"] == "AWAITING"


# ===========================================================================
# T08 — Required upstream input fields present
# ===========================================================================
class TestT08_UpstreamInputFields:
    def test_t08_required_upstream_input_fields_present(self, p83c_result):
        """T08: Upstream contract documents all required input fields."""
        s2 = p83c_result["step2_upstream_input_contract"]
        req_fields = s2.get("required_input_fields", [])
        for expected in ["game_id", "game_date", "home_team", "away_team",
                         "home_sp_fip", "away_sp_fip", "model_probability",
                         "predicted_side", "source_prediction_version"]:
            assert expected in req_fields, f"Missing required input field: {expected}"
        groups = s2.get("required_input_groups", {})
        assert "game_schedule" in groups
        assert "team_identifiers" in groups
        assert "starting_pitcher_features" in groups
        assert "model_output" in groups
        assert "governance_flags" in groups


# ===========================================================================
# T09 — Producer output path generated
# ===========================================================================
class TestT09_ProducerOutputPath:
    def test_t09_producer_output_path_generated(self, p83c_result):
        """T09: step3 defines canonical output path."""
        s3 = p83c_result["step3_producer_output_schema"]
        assert s3["output_path"] == "data/mlb_2026/predictions/mlb_2026_prediction_rows.jsonl"
        assert s3["output_format"] == "jsonl"


# ===========================================================================
# T10 — Rule flag computation contract generated
# ===========================================================================
class TestT10_RuleFlagComputationContract:
    def test_t10_rule_flag_computation_contract_generated(self, p83c_result):
        """T10: step4 rule flag computation contract exists with correct ID."""
        s4 = p83c_result["step4_rule_flag_computation"]
        assert s4["contract_id"] == "P83C_RULE_FLAG_COMPUTATION_CONTRACT_V1"
        assert s4["deterministic"] is True
        assert s4["verification_all_pass"] is True


# ===========================================================================
# T11 — abs_sp_fip_delta formula present
# ===========================================================================
class TestT11_AbsFipDeltaFormula:
    def test_t11_abs_sp_fip_delta_formula_present(self, p83c_result):
        """T11: abs_sp_fip_delta formula documented in step4."""
        formulas = p83c_result["step4_rule_flag_computation"]["formulas"]
        assert "abs_sp_fip_delta" in formulas
        assert "abs(sp_fip_delta)" in formulas["abs_sp_fip_delta"]

    def test_t11b_abs_fip_function_correct(self, p83c_module):
        """T11b: compute_abs_sp_fip_delta function returns correct value."""
        assert p83c_module.compute_abs_sp_fip_delta(1.30) == pytest.approx(1.30)
        assert p83c_module.compute_abs_sp_fip_delta(-1.40) == pytest.approx(1.40)
        assert p83c_module.compute_abs_sp_fip_delta(0.0) == pytest.approx(0.0)


# ===========================================================================
# T12 — primary 125 rule formula present
# ===========================================================================
class TestT12_Primary125Formula:
    def test_t12_primary_125_rule_formula_present(self, p83c_result):
        """T12: rule_primary_125_flag formula documented in step4."""
        formulas = p83c_result["step4_rule_flag_computation"]["formulas"]
        assert "rule_primary_125_flag" in formulas
        formula = formulas["rule_primary_125_flag"]
        assert "0.50" in formula or "0.5" in formula
        assert "1.25" in formula

    def test_t12b_primary_125_function_correct(self, p83c_module):
        """T12b: compute_rule_primary_125_flag returns correct values."""
        # home pick: abs >= 0.50 → True
        assert p83c_module.compute_rule_primary_125_flag("home", 1.30) is True
        assert p83c_module.compute_rule_primary_125_flag("home", 0.50) is True
        assert p83c_module.compute_rule_primary_125_flag("home", 0.49) is False
        # away pick: abs >= 1.25 → True
        assert p83c_module.compute_rule_primary_125_flag("away", 1.25) is True
        assert p83c_module.compute_rule_primary_125_flag("away", 1.40) is True
        assert p83c_module.compute_rule_primary_125_flag("away", 1.10) is False


# ===========================================================================
# T13 — shadow 100 rule formula present
# ===========================================================================
class TestT13_Shadow100Formula:
    def test_t13_shadow_100_rule_formula_present(self, p83c_result):
        """T13: rule_shadow_100_flag formula documented in step4."""
        formulas = p83c_result["step4_rule_flag_computation"]["formulas"]
        assert "rule_shadow_100_flag" in formulas
        formula = formulas["rule_shadow_100_flag"]
        assert "1.00" in formula or "1.0" in formula

    def test_t13b_shadow_100_function_correct(self, p83c_module):
        """T13b: compute_rule_shadow_100_flag returns correct values."""
        # home: abs >= 0.50
        assert p83c_module.compute_rule_shadow_100_flag("home", 0.50) is True
        assert p83c_module.compute_rule_shadow_100_flag("home", 0.49) is False
        # away: abs >= 1.00
        assert p83c_module.compute_rule_shadow_100_flag("away", 1.00) is True
        assert p83c_module.compute_rule_shadow_100_flag("away", 1.10) is True
        assert p83c_module.compute_rule_shadow_100_flag("away", 0.99) is False


# ===========================================================================
# T14 — Tier B formula present
# ===========================================================================
class TestT14_TierBFormula:
    def test_t14_tier_b_formula_present(self, p83c_result):
        """T14: tier_b_candidate_flag formula documented in step4."""
        formulas = p83c_result["step4_rule_flag_computation"]["formulas"]
        assert "tier_b_candidate_flag" in formulas
        formula = formulas["tier_b_candidate_flag"]
        assert "0.25" in formula
        assert "0.50" in formula or "0.5" in formula

    def test_t14b_tier_b_function_correct(self, p83c_module):
        """T14b: compute_tier_b_candidate_flag returns correct values."""
        assert p83c_module.compute_tier_b_candidate_flag(0.25) is True
        assert p83c_module.compute_tier_b_candidate_flag(0.35) is True
        assert p83c_module.compute_tier_b_candidate_flag(0.49) is True
        assert p83c_module.compute_tier_b_candidate_flag(0.50) is False
        assert p83c_module.compute_tier_b_candidate_flag(0.24) is False
        assert p83c_module.compute_tier_b_candidate_flag(1.30) is False


# ===========================================================================
# T15 — Tier A formula present
# ===========================================================================
class TestT15_TierAFormula:
    def test_t15_tier_a_formula_present(self, p83c_result):
        """T15: tier_a_watchlist_flag formula documented in step4."""
        formulas = p83c_result["step4_rule_flag_computation"]["formulas"]
        assert "tier_a_watchlist_flag" in formulas
        formula = formulas["tier_a_watchlist_flag"]
        assert "0.25" in formula

    def test_t15b_tier_a_function_correct(self, p83c_module):
        """T15b: compute_tier_a_watchlist_flag returns correct values."""
        assert p83c_module.compute_tier_a_watchlist_flag(0.10) is True
        assert p83c_module.compute_tier_a_watchlist_flag(0.24) is True
        assert p83c_module.compute_tier_a_watchlist_flag(0.25) is False
        assert p83c_module.compute_tier_a_watchlist_flag(1.30) is False


# ===========================================================================
# T16 — Mock schema-only row generated in-memory
# ===========================================================================
class TestT16_MockRowInMemory:
    def test_t16_mock_schema_only_row_generated_in_memory(self, p83c_result):
        """T16: step5 dry-run generates mock rows in-memory."""
        s5 = p83c_result["step5_schema_only_dry_run"]
        assert s5["mock_row_count"] >= 1
        assert s5["mock_rows_in_memory_only"] is True
        assert s5["mock_tag"] == "MOCK_SCHEMA_ONLY"
        assert len(s5["row_results"]) >= 1
        for rr in s5["row_results"]:
            assert rr["mock_tag"] == "MOCK_SCHEMA_ONLY"


# ===========================================================================
# T17 — Mock row not written to canonical path
# ===========================================================================
class TestT17_MockRowNotWritten:
    def test_t17_mock_row_not_written_to_canonical_path(self, p83c_result):
        """T17: mock row is NOT written to canonical prediction file."""
        s5 = p83c_result["step5_schema_only_dry_run"]
        assert s5["mock_row_written_to_canonical"] is False

    def test_t17b_canonical_file_not_contains_mock_game_id(self):
        """T17b: canonical prediction file (if exists) does not contain mock game IDs."""
        if not CANONICAL_PRED_PATH.exists():
            return  # path doesn't exist → no mock rows possible
        content = CANONICAL_PRED_PATH.read_text()
        assert "P83C_MOCK_SCHEMA_ONLY" not in content


# ===========================================================================
# T18 — Mock row cannot trigger snapshot
# ===========================================================================
class TestT18_MockRowNoSnapshot:
    def test_t18_mock_row_cannot_trigger_snapshot(self, p83c_result):
        """T18: snapshot_unlock_blocked reflects real row count in canonical path."""
        s5 = p83c_result["step5_schema_only_dry_run"]
        # snapshot_unlock_blocked is True when no real rows exist in canonical path;
        # False when canonical rows exist (e.g. after P83E runs successfully)
        assert isinstance(s5["snapshot_unlock_blocked"], bool)
        if s5["snapshot_unlock_blocked"] is True:
            assert s5["real_row_count_in_canonical"] == 0


# ===========================================================================
# T19 — Schema validator passes mock row
# ===========================================================================
class TestT19_SchemaValidatorPassesMock:
    def test_t19_schema_validator_passes_mock_row(self, p83c_result):
        """T19: schema_pass=True for all mock rows in dry-run."""
        s5 = p83c_result["step5_schema_only_dry_run"]
        assert s5["schema_pass"] is True
        for rr in s5["row_results"]:
            assert rr["schema_pass"] is True, f"Schema failed for {rr['mock_label']}: {rr['schema_violations']}"

    def test_t19b_schema_validator_function(self, p83c_module):
        """T19b: validate_row_schema function works correctly."""
        good_row = {
            "game_id": "TEST_001",
            "game_date": "2026-04-01",
            "season": 2026,
            "home_team": "NYY",
            "away_team": "BOS",
            "predicted_side": "home",
            "model_probability": 0.60,
            "sp_fip_delta": 0.80,
            "abs_sp_fip_delta": 0.80,
            "source_prediction_version": "mlb_2026_prediction_rows_v1",
            "rule_primary_125_flag": True,
            "rule_shadow_100_flag": True,
            "tier_b_candidate_flag": False,
            "tier_a_watchlist_flag": False,
            "paper_only": True,
            "diagnostic_only": True,
            "odds_used": False,
            "market_edge_evaluated": False,
            "production_ready": False,
        }
        result = p83c_module.validate_row_schema(good_row)
        assert result["schema_pass"] is True
        assert len(result["violations"]) == 0


# ===========================================================================
# T20 — Governance validator passes mock row
# ===========================================================================
class TestT20_GovernanceValidatorPassesMock:
    def test_t20_governance_validator_passes_mock_row(self, p83c_result):
        """T20: governance_pass=True for all mock rows in dry-run."""
        s5 = p83c_result["step5_schema_only_dry_run"]
        assert s5["governance_pass"] is True
        for rr in s5["row_results"]:
            assert rr["governance_pass"] is True, f"Gov failed for {rr['mock_label']}: {rr['governance_violations']}"

    def test_t20b_governance_validator_rejects_bad_row(self, p83c_module):
        """T20b: validate_row_governance rejects row with production_ready=True."""
        bad_row = {
            "season": 2026,
            "paper_only": True,
            "diagnostic_only": True,
            "odds_used": False,
            "market_edge_evaluated": False,
            "production_ready": True,  # VIOLATION
        }
        result = p83c_module.validate_row_governance(bad_row)
        assert result["governance_pass"] is False
        assert len(result["violations"]) > 0


# ===========================================================================
# T21 — Awaiting upstream data classification generated
# ===========================================================================
class TestT21_AwaitingClassification:
    def test_t21_awaiting_upstream_data_classification_generated(self, p83c_result):
        """T21: classification must be a valid P83C state."""
        cls = p83c_result["p83c_classification"]
        VALID_P83C = {
            "P83C_SCHEMA_PRODUCER_READY_AWAITING_UPSTREAM_DATA",
            "P83C_SCHEMA_PRODUCER_READY_WITH_EXISTING_UPSTREAM_DATA",
        }
        assert cls in VALID_P83C, f"Expected a valid P83C classification, got {cls}"
        assert "P83C_SCHEMA_PRODUCER_READY_AWAITING_UPSTREAM_DATA" in p83c_result["allowed_classifications"]


# ===========================================================================
# T22 — Future P83D prompt generated
# ===========================================================================
class TestT22_P83DPromptGenerated:
    def test_t22_future_p83d_prompt_generated(self, p83c_result):
        """T22: step6 P83D prompt exists with required structure."""
        s6 = p83c_result["step6_p83d_prompt"]
        assert s6["future_phase"] == "P83D"
        assert s6["minimum_rows_to_trigger"] == 1
        assert s6["schema_ref"] == "P83C_PRODUCER_OUTPUT_SCHEMA_V1"
        assert s6["upstream_contract_ref"] == "P83C_UPSTREAM_INPUT_CONTRACT_V1"
        assert len(s6["p83d_tasks"]) >= 7
        prompt_text = s6["prompt_template"]
        assert "P83D" in prompt_text
        assert "paper_only=True" in prompt_text

    def test_t22b_p83d_prompt_baseline_reference(self, p83c_result):
        """T22b: P83D prompt references 2025 baseline correctly."""
        s6 = p83c_result["step6_p83d_prompt"]
        baseline = s6["reference_baseline"]
        assert baseline["rule"] == "TIER_C_HOME_PLUS_AWAY_125"
        assert abs(baseline["hit_rate_2025"] - 0.6392) < 1e-4
        assert abs(baseline["auc_2025"] - 0.5787) < 1e-4


# ===========================================================================
# T23 — No odds required
# ===========================================================================
class TestT23_NoOddsRequired:
    def test_t23_no_odds_required(self, p83c_result):
        """T23: odds_required=False and odds_used=False in producer schema."""
        s3 = p83c_result["step3_producer_output_schema"]
        assert s3["odds_required"] is False
        assert s3["no_odds_fields"] is True
        assert s3["governance_enforced_values"]["odds_used"] is False


# ===========================================================================
# T24 — No API call
# ===========================================================================
class TestT24_NoAPICall:
    def test_t24_no_api_call(self, p83c_result):
        """T24: live_api_calls=0 in upstream contract."""
        s2 = p83c_result["step2_upstream_input_contract"]
        assert s2["live_api_calls"] == 0


# ===========================================================================
# T25 — No API key access
# ===========================================================================
class TestT25_NoAPIKeyAccess:
    def test_t25_no_api_key_access(self, p83c_result):
        """T25: api_key_accessed=False in governance."""
        gov = p83c_result["governance"]
        assert gov["api_key_accessed"] is False
        assert gov["the_odds_api_key_required"] is False

    def test_t25b_api_key_not_in_json(self, p83c_json):
        """T25b: THE_ODDS_API_KEY string not present in JSON output."""
        json_text = json.dumps(p83c_json)
        assert "THE_ODDS_API_KEY" not in json_text


# ===========================================================================
# T26 — No edge calculated
# ===========================================================================
class TestT26_NoEdge:
    def test_t26_no_edge_calculated(self, p83c_result):
        """T26: market_edge_calculated=False in governance."""
        gov = p83c_result["governance"]
        assert gov["market_edge_calculated"] is False
        assert gov["market_edge_evaluated"] is False


# ===========================================================================
# T27 — No CLV calculated
# ===========================================================================
class TestT27_NoCLV:
    def test_t27_no_clv_calculated(self, p83c_result):
        """T27: clv_calculated=False in governance."""
        gov = p83c_result["governance"]
        assert gov["clv_calculated"] is False


# ===========================================================================
# T28 — No EV calculated
# ===========================================================================
class TestT28_NoEV:
    def test_t28_no_ev_calculated(self, p83c_result):
        """T28: ev_calculated=False in governance."""
        gov = p83c_result["governance"]
        assert gov["ev_calculated"] is False


# ===========================================================================
# T29 — No Kelly calculated
# ===========================================================================
class TestT29_NoKelly:
    def test_t29_no_kelly_calculated(self, p83c_result):
        """T29: kelly_calculated=False and kelly_deploy_allowed=False."""
        gov = p83c_result["governance"]
        assert gov["kelly_calculated"] is False
        assert gov["kelly_deploy_allowed"] is False


# ===========================================================================
# T30 — live_api_calls=0
# ===========================================================================
class TestT30_LiveApiCallsZero:
    def test_t30_live_api_calls_zero(self, p83c_result):
        """T30: governance live_api_calls == 0."""
        gov = p83c_result["governance"]
        assert gov["live_api_calls"] == 0


# ===========================================================================
# T31 — production_ready=false
# ===========================================================================
class TestT31_ProductionReadyFalse:
    def test_t31_production_ready_false(self, p83c_result):
        """T31: governance production_ready=False."""
        gov = p83c_result["governance"]
        assert gov["production_ready"] is False


# ===========================================================================
# T32 — kelly_deploy_allowed=false
# ===========================================================================
class TestT32_KellyDeployFalse:
    def test_t32_kelly_deploy_allowed_false(self, p83c_result):
        """T32: governance kelly_deploy_allowed=False."""
        gov = p83c_result["governance"]
        assert gov["kelly_deploy_allowed"] is False


# ===========================================================================
# T33 — forbidden scan passes
# ===========================================================================
class TestT33_ForbiddenScan:
    def test_t33_forbidden_scan_passes(self, p83c_result):
        """T33: forbidden scan result = CLEAN with 0 violations."""
        fs = p83c_result["forbidden_scan"]
        assert fs["result"] == "CLEAN"
        assert fs["violation_count"] == 0
        assert len(fs["violations"]) == 0

    def test_t33b_forbidden_scan_on_json_file(self, p83c_json):
        """T33b: forbidden exact-phrases absent from written JSON output."""
        text_lower = json.dumps(p83c_json).lower()
        # Use same exact phrases as _FORBIDDEN_PHRASES in the script
        forbidden_exact = [
            "closing_line_value",
            '"clv_calculated": true',
            "kelly fraction",
            '"kelly_deploy_allowed": true',
            '"production_ready": true',
            '"real_bet_allowed": true',
            '"ev_calculated": true',
            '"odds_used": true',
            "the_odds_api_key =",
        ]
        for phrase in forbidden_exact:
            assert phrase.lower() not in text_lower, f"Forbidden phrase found: {phrase}"


# ===========================================================================
# T34 — JSON schema stable
# ===========================================================================
class TestT34_JSONSchemaStable:
    def test_t34_json_schema_stable(self):
        """T34: JSON output file exists and is parseable."""
        assert JSON_OUT.exists(), f"P83C JSON not found: {JSON_OUT}"
        data = json.loads(JSON_OUT.read_text())
        assert data["phase"] == "P83C"

    def test_t34b_json_has_all_required_top_level_keys(self, p83c_json):
        """T34b: JSON output has all required top-level keys."""
        required_keys = [
            "phase", "date", "p83c_classification", "allowed_classifications",
            "governance", "prediction_boundary",
            "step1_p83b_verification", "step2_upstream_input_contract",
            "step3_producer_output_schema", "step4_rule_flag_computation",
            "step5_schema_only_dry_run", "step6_p83d_prompt",
            "p82_status", "forbidden_scan",
        ]
        for k in required_keys:
            assert k in p83c_json, f"Missing key: {k}"


# ===========================================================================
# T35 — report includes upstream contract
# ===========================================================================
class TestT35_ReportUpstreamContract:
    def test_t35_report_includes_upstream_contract(self):
        """T35: Report markdown includes upstream contract section."""
        assert REPORT_MD.exists(), f"Report not found: {REPORT_MD}"
        text = REPORT_MD.read_text()
        assert "Upstream Input Contract" in text
        assert "P83C_UPSTREAM_INPUT_CONTRACT_V1" in text
        assert "starting_pitcher_features" in text


# ===========================================================================
# T36 — report includes producer schema
# ===========================================================================
class TestT36_ReportProducerSchema:
    def test_t36_report_includes_producer_schema(self):
        """T36: Report markdown includes producer schema section."""
        assert REPORT_MD.exists()
        text = REPORT_MD.read_text()
        assert "Producer Output Schema" in text
        assert "P83C_PRODUCER_OUTPUT_SCHEMA_V1" in text
        assert "sp_fip_delta" in text


# ===========================================================================
# T37 — active_task.md updated
# ===========================================================================
class TestT37_ActiveTaskUpdated:
    def test_t37_active_task_md_updated(self):
        """T37: active_task.md contains P83C section."""
        assert ACTIVE_TASK_MD.exists(), f"active_task.md not found: {ACTIVE_TASK_MD}"
        text = ACTIVE_TASK_MD.read_text()
        assert "P83C" in text
        assert "P83C_SCHEMA_PRODUCER_READY_AWAITING_UPSTREAM_DATA" in text


# ===========================================================================
# T38 — P72A-P83C regression invariant
# ===========================================================================
class TestT38_RegressionInvariant:
    def test_t38_p72a_p83c_regression_invariant(self):
        """T38: All prior phase summary JSON files still present (regression guard)."""
        required_artifacts = [
            ROOT / "data/mlb_2025/derived/p72a_odds_free_strategy_accuracy_backtest_summary.json",
            ROOT / "data/mlb_2025/derived/p72b_objective_metric_contract_summary.json",
            ROOT / "data/mlb_2025/derived/p76_corrected_tier_c_final_rule_selection_summary.json",
            ROOT / "data/mlb_2025/derived/p77_prediction_only_shadow_tracker_contract_summary.json",
            ROOT / "data/mlb_2025/derived/p82b_raw_paid_odds_data_policy_contract_summary.json",
            ROOT / "data/mlb_2025/derived/p82c_staging_guard_dryrun_scanner_summary.json",
            ROOT / "data/mlb_2026/derived/p83a_2026_live_accumulation_first_snapshot_summary.json",
            ROOT / "data/mlb_2026/derived/p83b_2026_prediction_data_ingest_contract_summary.json",
            ROOT / "data/mlb_2026/derived/p83c_2026_prediction_schema_producer_contract_summary.json",
        ]
        for artifact in required_artifacts:
            assert artifact.exists(), f"Regression fail — artifact missing: {artifact}"

    def test_t38b_p83c_phase_identifier(self, p83c_result, p83c_json):
        """T38b: phase=P83C in both result dict and written JSON."""
        assert p83c_result["phase"] == "P83C"
        assert p83c_json["phase"] == "P83C"

    def test_t38c_classification_matches_json(self, p83c_result, p83c_json):
        """T38c: classification consistent between result and written JSON."""
        assert p83c_result["p83c_classification"] == p83c_json["p83c_classification"]
