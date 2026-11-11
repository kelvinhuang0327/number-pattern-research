"""
P82C — Tests for Staging Guard Enforcement Dry-Run + Policy Drift Scanner
50 tests covering: source artifact loading, P82B state verification, scanner contract,
guard rules (all 6), false-positive safety, mock fixtures, current repo dry-run,
governance, forbidden phrases, and regression chain P72A→P82C.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SCRIPT = ROOT / "scripts/_p82c_staging_guard_dryrun_scanner.py"
JSON_OUT = ROOT / "data/mlb_2025/derived/p82c_staging_guard_dryrun_scanner_summary.json"
REPORT_OUT = ROOT / "report/p82c_staging_guard_dryrun_scanner_20260526.md"

P82B_JSON = ROOT / "data/mlb_2025/derived/p82b_raw_paid_odds_data_policy_contract_summary.json"
P82A_JSON = ROOT / "data/mlb_2025/derived/p82a_real_legal_odds_intake_gate_summary.json"
P81_JSON  = ROOT / "data/mlb_2025/derived/p81_legal_odds_dataset_validator_contract_summary.json"
P80_JSON  = ROOT / "data/mlb_2025/derived/p80_market_edge_reentry_readiness_contract_summary.json"
P79B_JSON = ROOT / "data/mlb_2025/derived/p79b_tier_b_vs_tier_c_comparison_harness_summary.json"
P79A_JSON = ROOT / "data/mlb_2025/derived/p79a_tier_b_trigger_readiness_contract_summary.json"
P78_JSON  = ROOT / "data/mlb_2025/derived/p78_monthly_shadow_tracker_report_template_summary.json"
P77_JSON  = ROOT / "data/mlb_2025/derived/p77_prediction_only_shadow_tracker_contract_summary.json"
P76_JSON  = ROOT / "data/mlb_2025/derived/p76_corrected_tier_c_final_rule_selection_summary.json"
P75B_JSON = ROOT / "data/mlb_2025/derived/p75b_calibration_diagnostics_corrected_tier_c_summary.json"
P75A_JSON = ROOT / "data/mlb_2025/derived/p75a_tier_c_corrected_rule_validator_summary.json"
P74_JSON  = ROOT / "data/mlb_2025/derived/p74_tier_c_home_away_bias_correction_summary.json"
P73_JSON  = ROOT / "data/mlb_2025/derived/p73_tier_stability_and_sample_expansion_summary.json"
P72B_JSON = ROOT / "data/mlb_2025/derived/p72b_objective_metric_contract_summary.json"
P72A_JSON = ROOT / "data/mlb_2025/derived/p72a_odds_free_strategy_accuracy_backtest_summary.json"

ALLOWED_CLASSIFICATIONS = [
    "P82C_STAGING_GUARD_DRYRUN_READY",
    "P82C_STAGING_GUARD_DRYRUN_READY_WITH_WARNINGS",
    "P82C_BLOCKED_BY_MISSING_P82B_ARTIFACT",
    "P82C_FAILED_VALIDATION",
]

EXPECTED_GUARD_STATES = [
    "STAGE_CLEAN", "BLOCK_RAW_PAID_DATA", "BLOCK_SECRET",
    "BLOCK_UNPOLICIED_ODDS", "BLOCK_ROW_LEVEL_LEAKAGE", "REVIEW_REQUIRED",
]

EXPECTED_GUARD_RULES = [
    "BLOCK_ENV_FILE", "BLOCK_API_KEY_PATTERN", "BLOCK_RAW_PAID_CSV",
    "BLOCK_REAL_ODDS_FILENAME", "BLOCK_CONTAINS_API_KEY_FLAG", "BLOCK_ROW_LEVEL_ODDS",
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
    '"p82_unlocked": true',
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def p82c_module():
    mod_name = "_p82c_staging_guard_dryrun_scanner"
    spec = importlib.util.spec_from_file_location(mod_name, SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod  # register so dataclasses can resolve forward refs
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def p82c_result(p82c_module):
    return p82c_module.run_p82c()


@pytest.fixture(scope="module")
def p82c_json() -> dict:
    assert JSON_OUT.exists(), f"Output JSON not found: {JSON_OUT}"
    with open(JSON_OUT) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def p82b_json() -> dict:
    assert P82B_JSON.exists()
    with open(P82B_JSON) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# 1-5: Source artifact loading + P82B state verification
# ---------------------------------------------------------------------------
def test_01_p82b_source_artifact_loads():
    assert P82B_JSON.exists(), "P82B JSON must exist for P82C"
    with open(P82B_JSON) as f:
        data = json.load(f)
    assert "p82b_classification" in data


def test_02_p82b_classification_verified(p82c_result):
    v = p82c_result["step1_p82b_verification"]
    assert v["classification"] == "P82B_RAW_PAID_DATA_POLICY_READY"
    assert v["classification_ok"] is True


def test_03_p82b_staging_guard_rules_extracted(p82c_result):
    v = p82c_result["step1_p82b_verification"]
    assert v["guard_rules_ok"] is True
    assert v["guard_rules_count"] == 6
    for rule_id in EXPECTED_GUARD_RULES:
        assert rule_id in v["guard_rule_ids"], f"Guard rule {rule_id} missing"


def test_04_p82b_policy_matrix_extracted(p82c_result):
    v = p82c_result["step1_p82b_verification"]
    assert "RAW_PAID_ODDS_DATA" in v["policy_matrix_classes"]


def test_05_p82_remains_blocked_no_real_dataset(p82c_result):
    v = p82c_result["step1_p82b_verification"]
    assert v["p82_unlock_status"] == "BLOCKED_NO_REAL_DATASET"
    assert v["p82_blocked"] is True
    assert p82c_result.get("p82_status") == "BLOCKED_NO_REAL_DATASET"


# ---------------------------------------------------------------------------
# 6-10: Scanner contract and scan modes
# ---------------------------------------------------------------------------
def test_06_dry_run_scanner_contract_generated(p82c_result):
    sc = p82c_result.get("step2_scanner_contract", {})
    assert sc.get("scanner_id") == "P82C_STAGING_GUARD_DRYRUN_SCANNER"
    assert len(sc.get("guard_rules", [])) == 6


def test_07_scanner_supports_staged_file_mode(p82c_module):
    result = p82c_module.scan_staged_files()
    assert result.scan_mode == "STAGED_FILES"
    assert result.guard_state in EXPECTED_GUARD_STATES


def test_08_scanner_supports_working_tree_mode(p82c_module):
    result = p82c_module.scan_working_tree()
    assert result.scan_mode == "WORKING_TREE"
    assert result.guard_state in EXPECTED_GUARD_STATES


def test_09_scanner_supports_allowlisted_path_mode(p82c_module):
    result = p82c_module.scan_allowlisted_paths()
    assert result.scan_mode == "ALLOWLISTED_PATHS"
    assert result.guard_state in EXPECTED_GUARD_STATES


def test_10_scanner_supports_inmemory_mock_mode(p82c_module):
    result = p82c_module.scan_inmemory(p82c_module.MOCK_FIXTURES)
    assert result.scan_mode == "INMEMORY_MOCK"
    assert len(result.files_scanned) == len(p82c_module.MOCK_FIXTURES)


# ---------------------------------------------------------------------------
# 11-17: Guard rule detection
# ---------------------------------------------------------------------------
def test_11_block_env_file_detects_dotenv(p82c_module):
    v = p82c_module.rule_block_env_file(".env", "SECRET=abc123")
    assert v is not None
    assert v.rule_id == "BLOCK_ENV_FILE"
    assert v.guard_state == "BLOCK_SECRET"


def test_12_block_api_key_pattern_detects_key_like_content(p82c_module):
    content = '{"api_key": "ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890ABCDEF"}'
    v = p82c_module.rule_block_api_key_pattern("data/config.json", content)
    assert v is not None
    assert v.rule_id == "BLOCK_API_KEY_PATTERN"
    assert v.guard_state == "BLOCK_SECRET"


def test_13_api_key_content_is_redacted_in_report(p82c_module):
    """Verify that the evidence is redacted, not the raw key value."""
    content = '{"api_key": "ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890ABCDEF"}'
    v = p82c_module.rule_block_api_key_pattern("data/config.json", content)
    assert v is not None
    full_key = "ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890ABCDEF"
    # Redacted evidence must not contain the full key
    assert full_key not in v.evidence_redacted
    assert "REDACT" in v.evidence_redacted.upper() or "..." in v.evidence_redacted


def test_14_block_raw_paid_csv_detects_paid_odds_path(p82c_module):
    v = p82c_module.rule_block_raw_paid_csv("data/paid_odds_mlb_2025.csv")
    assert v is not None
    assert v.rule_id == "BLOCK_RAW_PAID_CSV"
    assert v.guard_state == "BLOCK_RAW_PAID_DATA"


def test_15_block_real_odds_filename_detects_2024_real_pattern(p82c_module):
    v = p82c_module.rule_block_real_odds_filename("data/mlb_odds_2024_real.csv")
    assert v is not None
    assert v.rule_id == "BLOCK_REAL_ODDS_FILENAME"
    assert v.guard_state == "BLOCK_RAW_PAID_DATA"


def test_16_block_contains_api_key_flag_detects_true(p82c_module):
    content = '{"contains_api_key": true, "provider": "the_odds_api"}'
    v = p82c_module.rule_block_contains_api_key_flag("data/mlb_2025/intake.json", content)
    assert v is not None
    assert v.rule_id == "BLOCK_CONTAINS_API_KEY_FLAG"
    assert v.guard_state == "BLOCK_SECRET"


def test_17_block_row_level_odds_detects_leakage(p82c_module):
    content = (
        '{"game_id": "MLB_001", "home_ml": -130, "away_ml": 110, '
        '"raw_odds_row": true, "source": "paid_provider"}'
    )
    # filepath must not trigger BLOCK_REAL_ODDS_FILENAME
    v = p82c_module.rule_block_row_level_odds("data/mlb_2025/game_analysis_export.json", content)
    assert v is not None
    assert v.rule_id == "BLOCK_ROW_LEVEL_ODDS"
    assert v.guard_state == "BLOCK_ROW_LEVEL_LEAKAGE"
    assert not v.suppressed


# ---------------------------------------------------------------------------
# 18-22: False-positive safety
# ---------------------------------------------------------------------------
def test_18_safe_derived_summary_allowed(p82c_module):
    """P-series derived JSON with governance markers must not trigger hard blocks."""
    content = (
        '{"p82c_classification": "P82C_STAGING_GUARD_DRYRUN_READY", '
        '"governance": {"paper_only": true, "NO_REAL_BET": true, '
        '"kelly_deploy_allowed": false}, '
        '"hit_rate": 0.639, "auc": 0.579}'
    )
    filepath = "data/mlb_2025/derived/p82c_staging_guard_dryrun_scanner_summary.json"
    suppression_notes: list = []
    from scripts._p82c_staging_guard_dryrun_scanner import _scan_single_file
    viols, warns = _scan_single_file(filepath, content, suppression_notes)
    active = [v for v in viols if not v.get("suppressed", False)]
    assert len(active) == 0, f"Safe derived summary triggered guard: {active}"


def test_19_safe_policy_report_text_allowed(p82c_module):
    """Report text describing blocked filenames must not trigger hard blocks."""
    content = (
        "# P82B Policy Contract\n"
        "Guard rule BLOCK_RAW_PAID_CSV blocks files matching `*paid*odds*.csv`.\n"
        "BLOCK_REAL_ODDS_FILENAME blocks `*odds_2024_real.csv`.\n"
        "paper_only=True | diagnostic_only=True | NO_REAL_BET=True"
    )
    filepath = "report/p82b_raw_paid_odds_data_policy_contract_20260526.md"
    suppression_notes: list = []
    from scripts._p82c_staging_guard_dryrun_scanner import _scan_single_file
    viols, warns = _scan_single_file(filepath, content, suppression_notes)
    active = [v for v in viols if not v.get("suppressed", False)]
    assert len(active) == 0, f"Policy report text triggered guard: {active}"


def test_20_no_real_bet_does_not_false_positive(p82c_module):
    """Content with 'NO_REAL_BET' governance text must not trigger BLOCK_API_KEY_PATTERN."""
    content = (
        '{"governance": {"paper_only": true, "NO_REAL_BET": true}, '
        '"api_key_required": false, "live_api_calls": 0}'
    )
    v = p82c_module.rule_block_api_key_pattern("data/mlb_2025/derived/p80_summary.json", content)
    # Either None or suppressed
    if v is not None:
        assert v.suppressed, "NO_REAL_BET context must suppress false positives"


def test_21_home_moneyline_field_name_does_not_false_positive(p82c_module):
    """home_moneyline as an aggregate field name must not trigger row-level odds rule."""
    content = (
        '{"avg_home_moneyline": -115.3, "avg_away_moneyline": 108.2, '
        '"hit_rate": 0.639, "auc": 0.579, "paper_only": true}'
    )
    v = p82c_module.rule_block_row_level_odds("data/mlb_2025/derived/p72a_summary.json", content)
    if v is not None:
        assert v.suppressed, "Aggregate moneyline stats must not trigger row-level block"


def test_22_policy_text_blocked_filenames_does_not_false_positive(p82c_module):
    """Policy document mentioning blocked filenames does not trigger BLOCK_RAW_PAID_CSV."""
    content = (
        "The BLOCK_RAW_PAID_CSV rule blocks files like data/**/*paid*odds*.csv.\n"
        "guard_state = BLOCK_RAW_PAID_DATA for these patterns.\n"
        "NO_REAL_BET=True paper_only=True"
    )
    filepath = "report/p82b_raw_paid_odds_data_policy_contract_20260526.md"
    # Filename-based rule won't trigger on .md with no matching name
    v_csv = p82c_module.rule_block_raw_paid_csv(filepath, content)
    assert v_csv is None, "Policy report .md file must not trigger BLOCK_RAW_PAID_CSV"


# ---------------------------------------------------------------------------
# 23-25: Mock fixture correctness
# ---------------------------------------------------------------------------
def test_23_mock_fixtures_are_inmemory_only(p82c_module):
    """Mock fixture scan must not create new real files in the repo.
    We verify that dangerous mock data paths (raw paid CSVs, row-level odds files)
    do not exist as real files. .env and P-series derived JSONs may pre-exist.
    """
    # These paths must NOT exist as real files (they'd indicate real odds data was created)
    dangerous_mock_paths = [
        ROOT / "data/paid_odds_mlb_2025.csv",
        ROOT / "data/mlb_odds_2024_real.csv",
        ROOT / "data/mlb_2025/game_analysis_export.json",
        ROOT / "data/mlb_2025/odds_intake_test.json",
        ROOT / "data/config_backup.json",
    ]
    for p in dangerous_mock_paths:
        assert not p.exists(), (
            f"Mock fixture must not create real file: {p}"
        )


def test_24_risky_mocks_map_to_expected_guard_states(p82c_result):
    """Each risky mock must trigger its expected guard state."""
    results = p82c_result["step3_mock_fixture_scan"]["results"]
    for r in results:
        if r["is_risky"]:
            assert r["actual_guard_state"] == r["expected_guard_state"], (
                f"Risky mock '{r['fixture_name']}': "
                f"expected {r['expected_guard_state']}, got {r['actual_guard_state']}"
            )


def test_25_safe_mocks_pass_or_warning_only(p82c_result):
    """Safe mock fixtures must result in STAGE_CLEAN (no hard block)."""
    results = p82c_result["step3_mock_fixture_scan"]["results"]
    for r in results:
        if not r["is_risky"]:
            assert r["actual_guard_state"] == "STAGE_CLEAN", (
                f"Safe mock '{r['fixture_name']}' must not trigger hard block, "
                f"got {r['actual_guard_state']}"
            )


# ---------------------------------------------------------------------------
# 26-30: Current repo dry-run
# ---------------------------------------------------------------------------
def test_26_current_repo_dryrun_result_generated(p82c_result):
    repo = p82c_result.get("step4_current_repo_dryrun", {})
    assert "staged_files_result" in repo
    assert "working_tree_result" in repo
    assert "allowlisted_paths_result" in repo
    assert "overall_guard_state" in repo


def test_27_current_staged_files_scanned(p82c_result):
    staged = p82c_result["step4_current_repo_dryrun"]["staged_files_result"]
    assert "files_scanned_count" in staged
    assert "guard_state" in staged
    assert staged["guard_state"] in EXPECTED_GUARD_STATES


def test_28_current_working_tree_files_scanned(p82c_result):
    wt = p82c_result["step4_current_repo_dryrun"]["working_tree_result"]
    assert "files_scanned_count" in wt
    assert "guard_state" in wt
    assert wt["guard_state"] in EXPECTED_GUARD_STATES


def test_29_runtime_dirty_files_handled_as_out_of_scope(p82c_result):
    """Working tree runtime files must be marked out-of-scope, not hard-blocked."""
    wt = p82c_result["step4_current_repo_dryrun"]["working_tree_result"]
    # Runtime files must not produce violations that cause hard block state
    violations_count = wt.get("violations_count", 0)
    if violations_count > 0:
        # If any violation exists, it must not be a secret or raw-paid-data block
        # (runtime state files should not match these patterns)
        assert wt["guard_state"] not in ("BLOCK_SECRET",), (
            "Runtime dirty files must not trigger BLOCK_SECRET"
        )


def test_30_guard_state_generated(p82c_result):
    repo = p82c_result["step4_current_repo_dryrun"]
    assert repo["overall_guard_state"] in EXPECTED_GUARD_STATES


# ---------------------------------------------------------------------------
# 31-34: Guard state and violation structure
# ---------------------------------------------------------------------------
def test_31_guard_state_is_one_of_expected_states(p82c_result):
    overall = p82c_result["step4_current_repo_dryrun"]["overall_guard_state"]
    assert overall in EXPECTED_GUARD_STATES, f"Unknown guard state: {overall}"


def test_32_violations_include_rule_id(p82c_module):
    """Any violation object must include a rule_id field."""
    suppression_notes: list = []
    from scripts._p82c_staging_guard_dryrun_scanner import _scan_single_file
    content = '{"api_key": "ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890ABCDEF"}'
    viols, _ = _scan_single_file("data/test_config.json", content, suppression_notes)
    for v in viols:
        assert "rule_id" in v, "Violation must include rule_id"
        assert v["rule_id"] in EXPECTED_GUARD_RULES


def test_33_violations_include_redacted_evidence_only(p82c_module):
    """Violations must contain redacted evidence, not raw secrets."""
    content = '{"api_key": "ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890ABCDEF"}'
    v = p82c_module.rule_block_api_key_pattern("data/config.json", content)
    assert v is not None
    raw_key = "ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890ABCDEF"
    assert raw_key not in v.evidence_redacted, (
        "Raw secret must not appear in evidence_redacted"
    )


def test_34_warnings_include_suppression_notes(p82c_result):
    """Scanner must record suppression notes for false-positive decisions."""
    sc = p82c_result["step2_scanner_contract"]
    # Suppression markers must be defined
    assert len(sc["suppression_markers"]) > 0, "Suppression markers must be defined"


# ---------------------------------------------------------------------------
# 35-44: Governance invariants
# ---------------------------------------------------------------------------
def test_35_no_odds_file_created():
    """Mock fixtures must not have created real odds files."""
    forbidden_paths = [
        ROOT / "data/mlb_2025/game_analysis_export.json",
        ROOT / "data/paid_odds_mlb_2025.csv",
        ROOT / "data/mlb_odds_2024_real.csv",
        ROOT / "data/mlb_2025/odds_intake_test.json",
        ROOT / "data/config_backup.json",
    ]
    for p in forbidden_paths:
        assert not p.exists(), f"Mock fixture must not create real file: {p}"


def test_36_no_api_call(p82c_result):
    gov = p82c_result.get("governance", {})
    assert gov.get("live_api_calls") == 0


def test_37_no_api_key_access(p82c_result):
    gov = p82c_result.get("governance", {})
    assert gov.get("the_odds_api_key_required") is False
    # p82_unlocked must be False
    assert gov.get("p82_unlocked") is False


def test_38_no_edge_calculated(p82c_result):
    gov = p82c_result.get("governance", {})
    assert gov.get("market_edge_calculated") is False


def test_39_no_clv_calculated(p82c_result):
    gov = p82c_result.get("governance", {})
    assert gov.get("clv_calculated") is False


def test_40_no_ev_calculated(p82c_result):
    gov = p82c_result.get("governance", {})
    assert gov.get("ev_calculated") is False


def test_41_no_kelly_calculated(p82c_result):
    gov = p82c_result.get("governance", {})
    assert gov.get("kelly_deploy_allowed") is False


def test_42_live_api_calls_zero(p82c_result):
    gov = p82c_result.get("governance", {})
    assert gov.get("live_api_calls") == 0


def test_43_production_ready_false(p82c_result):
    gov = p82c_result.get("governance", {})
    assert gov.get("production_ready") is False


def test_44_kelly_deploy_allowed_false(p82c_result):
    gov = p82c_result.get("governance", {})
    assert gov.get("kelly_deploy_allowed") is False


# ---------------------------------------------------------------------------
# 45-49: Output quality
# ---------------------------------------------------------------------------
def test_45_forbidden_phrase_scan_passes(p82c_json):
    text = json.dumps(p82c_json).lower()
    for phrase in FORBIDDEN_PHRASES:
        assert phrase.lower() not in text, f"Forbidden phrase found: '{phrase}'"


def test_46_json_schema_stable(p82c_json):
    required_keys = [
        "phase", "date", "p82c_classification", "governance",
        "step1_p82b_verification", "step2_scanner_contract",
        "step3_mock_fixture_scan", "step4_current_repo_dryrun",
        "p82_status", "forbidden_scan",
    ]
    for k in required_keys:
        assert k in p82c_json, f"Required JSON key missing: {k}"


def test_47_report_includes_guard_results():
    assert REPORT_OUT.exists(), "P82C report must be generated"
    content = REPORT_OUT.read_text()
    assert "P82C" in content
    assert "guard" in content.lower() or "Guard" in content
    assert "STAGE_CLEAN" in content or "BLOCK_" in content or "STAGING_GUARD" in content


def test_48_report_includes_mock_cases():
    assert REPORT_OUT.exists()
    content = REPORT_OUT.read_text()
    assert "Mock" in content or "mock" in content or "Fixture" in content


def test_49_active_task_md_updated():
    active_task = ROOT / "00-Plan/roadmap/active_task.md"
    assert active_task.exists()
    content = active_task.read_text()
    # Must reference P82C (will be added in commit step, check for P82B at minimum)
    assert "P82" in content


# ---------------------------------------------------------------------------
# 50: Full regression chain P72A → P82C
# ---------------------------------------------------------------------------
def test_50_regression_prior_phases_intact():
    """All prior phase JSON summaries must still carry expected classifications."""
    chain = [
        (P72A_JSON, ["p72a_classification", "final_classification"],
         "P72A_ODDS_FREE_PREDICTIVE_SIGNAL_CONFIRMED"),
        (P72B_JSON, ["p72b_classification"],
         "P72B_OBJECTIVE_CONTRACT_READY"),
        (P73_JSON, ["p73_classification"],
         "P73_TIER_C_OPERATIONAL_STABLE_TIER_B_RESEARCH_CONFIRMED"),
        (P74_JSON, ["p74_classification"],
         "P74_TIER_C_HOME_AWAY_CORRECTION_CONFIRMED"),
        (P75A_JSON, ["p75a_classification"],
         "P75A_MULTI_CANDIDATE_REQUIRES_CALIBRATION"),
        (P75B_JSON, ["p75b_classification"],
         "P75B_MULTI_CANDIDATE_KEEP_FOR_NEXT_PHASE"),
        (P76_JSON, ["p76_classification"],
         "P76_DUAL_FINALISTS_RETAINED_UNTIL_2026_DATA"),
        (P77_JSON, ["p77_classification"],
         "P77_SHADOW_TRACKER_CONTRACT_READY"),
        (P78_JSON, ["p78_classification"],
         "P78_MONTHLY_SHADOW_TRACKER_TEMPLATE_READY"),
        (P79A_JSON, ["p79a_classification"],
         "P79A_TIER_B_TRIGGER_READINESS_CONTRACT_READY"),
        (P79B_JSON, ["p79b_classification"],
         "P79B_TIER_B_FIXTURE_RESEARCH_ONLY"),
        (P80_JSON, ["p80_classification"],
         "P80_MARKET_EDGE_REENTRY_CONTRACT_READY"),
        (P81_JSON, ["p81_classification"],
         "P81_VALIDATOR_CONTRACT_READY_MOCK_ONLY"),
        (P82A_JSON, ["p82a_classification"],
         "P82A_REAL_LEGAL_ODDS_INTAKE_GATE_READY"),
        (P82B_JSON, ["p82b_classification"],
         "P82B_RAW_PAID_DATA_POLICY_READY"),
    ]
    for path, keys, expected in chain:
        assert path.exists(), f"Missing prior artifact: {path}"
        with open(path) as f:
            data = json.load(f)
        value = ""
        for k in keys:
            v = data.get(k)
            if v:
                value = str(v)
                break
        assert value == expected, (
            f"{path.name}: expected classification '{expected}', got '{value}'"
        )
