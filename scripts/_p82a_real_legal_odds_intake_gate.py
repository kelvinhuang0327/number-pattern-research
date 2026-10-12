"""
P82A — Real Legal Odds Dataset Intake Gate + P82 Blocker Closure Plan
=======================================================================
Intake-gate and blocker-plan only. No odds pull, no real odds staging,
no edge/CLV/EV/Kelly computation.

Classification target: P82A_REAL_LEGAL_ODDS_INTAKE_GATE_READY
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# GOVERNANCE — immutable constant, paper_only mode
# ---------------------------------------------------------------------------
GOVERNANCE: dict = {
    "paper_only": True,
    "live_api_calls": 0,
    "ev_calculated": False,
    "clv_calculated": False,
    "market_edge_evaluated": False,
    "kelly_calculated": False,
    "kelly_deploy_allowed": False,
    "production_ready": False,
    "real_bet_allowed": False,
    "champion_replacement_allowed": False,
    "profitability_claim": False,
    "promotion_freeze": True,
    "tsl_crawler_modified": False,
    "runtime_recommendation_modified": False,
    "the_odds_api_key_required": False,
    "the_odds_api_key_accessed": False,
    "uses_historical_odds": False,
    "odds_used": False,
    "diagnostic_only": True,
    "real_odds_dataset_present": False,
    "p82_unlocked": False,
}

SCHEMA_VERSION = "p82a-v1"
SNAPSHOT_ID = "real_legal_odds_intake_gate_20260526"

REPO_ROOT = Path(__file__).parent.parent
DERIVED = REPO_ROOT / "data" / "mlb_2025" / "derived"

# ---------------------------------------------------------------------------
# Required source artifacts (P72A → P81)
# ---------------------------------------------------------------------------
SOURCE_ARTIFACTS: list[str] = [
    "p81_legal_odds_dataset_validator_contract_summary.json",
    "p80_market_edge_reentry_readiness_contract_summary.json",
    "p79b_tier_b_vs_tier_c_comparison_harness_summary.json",
    "p79a_tier_b_trigger_readiness_contract_summary.json",
    "p78_monthly_shadow_tracker_report_template_summary.json",
    "p77_prediction_only_shadow_tracker_contract_summary.json",
    "p76_corrected_tier_c_final_rule_selection_summary.json",
    "p75b_calibration_diagnostics_corrected_tier_c_summary.json",
    "p75a_tier_c_corrected_rule_validator_summary.json",
    "p74_tier_c_home_away_bias_correction_summary.json",
    "p73_tier_stability_and_sample_expansion_summary.json",
    "p72b_objective_metric_contract_summary.json",
    "p72a_odds_free_strategy_accuracy_backtest_summary.json",
]

# ---------------------------------------------------------------------------
# Intake manifest field spec
# ---------------------------------------------------------------------------
INTAKE_MANIFEST_FIELDS: list[dict] = [
    {"field": "manifest_id", "type": "str", "nullable": False, "description": "Unique ID for this intake manifest"},
    {"field": "dataset_path", "type": "str", "nullable": False, "description": "Relative path to the dataset file"},
    {"field": "dataset_type", "type": "str", "nullable": False, "required_value": "REAL_LEGAL_ODDS_DATASET", "description": "Must be REAL_LEGAL_ODDS_DATASET"},
    {"field": "season", "type": "int", "nullable": False, "description": "Season year (e.g. 2025)"},
    {"field": "source_name", "type": "str", "nullable": False, "description": "Name of originating sportsbook or data provider"},
    {"field": "source_license_status", "type": "str", "nullable": False, "required_value": "LEGAL_OR_LICENSED", "description": "Must be LEGAL_OR_LICENSED"},
    {"field": "source_license_evidence_ref", "type": "str", "nullable": False, "description": "Path or URL to license evidence document"},
    {"field": "acquisition_method", "type": "str", "nullable": False, "description": "How data was acquired (e.g. PAID_API, LICENSED_FEED)"},
    {"field": "acquired_at_utc", "type": "str", "nullable": False, "description": "ISO-8601 UTC timestamp of acquisition"},
    {"field": "acquired_by", "type": "str", "nullable": False, "description": "Person or system that acquired the data"},
    {"field": "raw_data_policy", "type": "str", "nullable": False, "forbidden_value": "UNKNOWN", "allowed_values": ["COMMIT_ALLOWED", "LOCAL_ONLY_HASH_COMMITTED", "DERIVED_ONLY_COMMIT"], "description": "Storage/commit policy; must not be UNKNOWN"},
    {"field": "checksum_hash", "type": "str", "nullable": False, "description": "SHA-256 checksum of dataset file"},
    {"field": "row_count", "type": "int", "nullable": False, "min": 1, "description": "Number of rows in the dataset"},
    {"field": "expected_schema_version", "type": "str", "nullable": False, "required_value": "p81-v1", "description": "Must match P81 schema version"},
    {"field": "validator_script", "type": "str", "nullable": False, "description": "Path to P81 validator script"},
    {"field": "validator_command", "type": "str", "nullable": False, "description": "Command to invoke the validator"},
    {"field": "p81_validator_version", "type": "str", "nullable": False, "description": "Version string of the validator"},
    {"field": "storage_policy", "type": "str", "nullable": False, "description": "Where dataset is stored (LOCAL_ONLY, CLOUD_PRIVATE, etc.)"},
    {"field": "commit_policy", "type": "str", "nullable": False, "description": "Whether dataset is committed to git"},
    {"field": "contains_api_key", "type": "bool", "nullable": False, "required_value": False, "description": "Must be False — API key must never be stored in dataset"},
    {"field": "contains_personal_data", "type": "bool", "nullable": False, "description": "Whether dataset contains PII"},
    {"field": "allowed_next_phase", "type": "str", "nullable": True, "description": "P82 only after validator passes; null if blocked"},
    {"field": "blocked_next_phase_reason", "type": "str", "nullable": True, "description": "Reason P82 is blocked if allowed_next_phase is null"},
]

ALLOWED_RAW_DATA_POLICIES = ["COMMIT_ALLOWED", "LOCAL_ONLY_HASH_COMMITTED", "DERIVED_ONLY_COMMIT"]

# ---------------------------------------------------------------------------
# Blocker closure checklist
# ---------------------------------------------------------------------------
BLOCKER_CHECKLIST: list[dict] = [
    {
        "blocker_id": "REAL_DATASET_PRESENT",
        "description": "A real legal odds dataset file exists at the declared manifest path",
        "current_status": "BLOCKED_PENDING_REAL_DATASET",
        "evidence_required": "File exists; checksum matches manifest.checksum_hash",
        "validation_method": "os.path.exists(manifest.dataset_path) + sha256 check",
        "owner": "Data Engineer",
        "unlock_effect": "Permits validator invocation",
        "stop_condition_if_failed": "STOP — do not invoke validator or unlock P82",
    },
    {
        "blocker_id": "SOURCE_LEGALITY_PROVEN",
        "description": "source_license_status == LEGAL_OR_LICENSED in manifest",
        "current_status": "BLOCKED_PENDING_REAL_DATASET",
        "evidence_required": "manifest.source_license_status == LEGAL_OR_LICENSED",
        "validation_method": "_run_unlock_decision(manifest) LEGALITY check",
        "owner": "Legal / Compliance",
        "unlock_effect": "Permits LEGALITY_GATE pass",
        "stop_condition_if_failed": "STOP — SCRAPING_TOS_VIOLATION or UNKNOWN blocks pipeline permanently",
    },
    {
        "blocker_id": "LICENSE_EVIDENCE_RECORDED",
        "description": "A license evidence document is referenced in manifest.source_license_evidence_ref",
        "current_status": "BLOCKED_PENDING_REAL_DATASET",
        "evidence_required": "Non-empty source_license_evidence_ref pointing to a document",
        "validation_method": "Non-empty string check on manifest field",
        "owner": "Legal / Compliance",
        "unlock_effect": "Required for audit trail",
        "stop_condition_if_failed": "STOP — undocumented license blocks P82",
    },
    {
        "blocker_id": "RAW_DATA_POLICY_DECIDED",
        "description": "manifest.raw_data_policy is in allowed values, not UNKNOWN",
        "current_status": "BLOCKED_PENDING_REAL_DATASET",
        "evidence_required": "manifest.raw_data_policy in [COMMIT_ALLOWED, LOCAL_ONLY_HASH_COMMITTED, DERIVED_ONLY_COMMIT]",
        "validation_method": "_run_unlock_decision(manifest) RAW_DATA_POLICY check",
        "owner": "Data Engineer",
        "unlock_effect": "Permits RAW_DATA_POLICY_GATE pass",
        "stop_condition_if_failed": "STOP — UNKNOWN policy blocks P82",
    },
    {
        "blocker_id": "CHECKSUM_RECORDED",
        "description": "manifest.checksum_hash is a non-empty SHA-256 hash",
        "current_status": "BLOCKED_PENDING_REAL_DATASET",
        "evidence_required": "Non-empty hex string in manifest.checksum_hash",
        "validation_method": "Non-empty string check; length == 64 for SHA-256",
        "owner": "Data Engineer",
        "unlock_effect": "Enables integrity verification before validator run",
        "stop_condition_if_failed": "STOP — missing checksum blocks P82",
    },
    {
        "blocker_id": "SCHEMA_VALIDATED",
        "description": "P81 validator _validate_schema returns valid=True for all rows",
        "current_status": "BLOCKED_PENDING_REAL_DATASET",
        "evidence_required": "P81 validator run output: all rows valid=True, 0 missing/null/type errors",
        "validation_method": "Invoke scripts/_p81_legal_odds_dataset_validator_contract.py on dataset",
        "owner": "Data Engineer",
        "unlock_effect": "Permits full 5-gate validation",
        "stop_condition_if_failed": "STOP — any schema violation blocks P82",
    },
    {
        "blocker_id": "TIMESTAMP_LINEAGE_VALIDATED",
        "description": "All rows pass TIMESTAMP_GATE: pregame odds_ts < game_start_ts",
        "current_status": "BLOCKED_PENDING_REAL_DATASET",
        "evidence_required": "P81 TIMESTAMP_GATE returns PASS for all rows",
        "validation_method": "_run_timestamp_gate per-row validation",
        "owner": "Data Engineer",
        "unlock_effect": "Enables pregame edge diagnostics; closing pairs required for CLV",
        "stop_condition_if_failed": "STOP — timestamp violation blocks P82; CLV remains blocked until P83",
    },
    {
        "blocker_id": "MONEYLINE_VALIDATED",
        "description": "All rows pass MONEYLINE_GATE: home + away moneylines are numeric",
        "current_status": "BLOCKED_PENDING_REAL_DATASET",
        "evidence_required": "P81 MONEYLINE_GATE returns PASS for all rows",
        "validation_method": "_run_moneyline_gate per-row validation",
        "owner": "Data Engineer",
        "unlock_effect": "Enables implied probability computation",
        "stop_condition_if_failed": "STOP — non-numeric moneyline blocks P82",
    },
    {
        "blocker_id": "IDENTITY_MAPPING_VALIDATED",
        "description": "All rows pass IDENTITY_GATE: home_team != away_team, game_id non-empty",
        "current_status": "BLOCKED_PENDING_REAL_DATASET",
        "evidence_required": "P81 IDENTITY_GATE returns PASS for all rows",
        "validation_method": "_run_identity_gate per-row validation",
        "owner": "Data Engineer",
        "unlock_effect": "Enables join to prediction candidates",
        "stop_condition_if_failed": "STOP — identity failure blocks P82",
    },
    {
        "blocker_id": "MOCK_DATA_EXCLUDED",
        "description": "No rows with source_license_status=MOCK_VALIDATOR_ONLY in real dataset",
        "current_status": "BLOCKED_PENDING_REAL_DATASET",
        "evidence_required": "Zero rows where source_license_status == MOCK_VALIDATOR_ONLY",
        "validation_method": "Row-level filter scan after load",
        "owner": "Data Engineer",
        "unlock_effect": "Ensures real-data integrity; mock rows would invalidate edge diagnostics",
        "stop_condition_if_failed": "STOP — any mock row in real dataset blocks P82",
    },
    {
        "blocker_id": "API_KEY_NOT_STORED",
        "description": "manifest.contains_api_key == False; no API key embedded in dataset",
        "current_status": "ACTIVE_GUARDRAIL",
        "evidence_required": "manifest.contains_api_key == False",
        "validation_method": "_run_unlock_decision(manifest) API key check",
        "owner": "Security",
        "unlock_effect": "Permanent guardrail — must be False at all times",
        "stop_condition_if_failed": "STOP — API key in data is a hard block; purge dataset",
    },
    {
        "blocker_id": "PRODUCTION_REMAINS_BLOCKED",
        "description": "production_ready=False and kelly_deploy_allowed=False throughout P82",
        "current_status": "ACTIVE_GUARDRAIL",
        "evidence_required": "GOVERNANCE['production_ready'] == False; GOVERNANCE['kelly_deploy_allowed'] == False",
        "validation_method": "Governance constant check",
        "owner": "CTO",
        "unlock_effect": "Permanent guardrail — P82 is dry-run only",
        "stop_condition_if_failed": "STOP — governance production_ready and kelly_deploy_allowed must remain False; see GOVERNANCE constant",
    },
]

REAL_DATA_BLOCKER_IDS = [
    "REAL_DATASET_PRESENT",
    "SOURCE_LEGALITY_PROVEN",
    "LICENSE_EVIDENCE_RECORDED",
    "RAW_DATA_POLICY_DECIDED",
    "CHECKSUM_RECORDED",
    "SCHEMA_VALIDATED",
    "TIMESTAMP_LINEAGE_VALIDATED",
    "MONEYLINE_VALIDATED",
    "IDENTITY_MAPPING_VALIDATED",
    "MOCK_DATA_EXCLUDED",
]

GOVERNANCE_BLOCKER_IDS = [
    "API_KEY_NOT_STORED",
    "PRODUCTION_REMAINS_BLOCKED",
]

# ---------------------------------------------------------------------------
# P82 allowed / prohibited dry-run scope
# ---------------------------------------------------------------------------
P82_DRY_RUN_SCOPE: dict = {
    "allowed": [
        "load validated odds dataset",
        "join prediction candidates to odds rows via game_id",
        "compute market implied probabilities from home/away moneylines",
        "compute paper-only edge diagnostics (model prob vs implied prob)",
        "compare primary 125 vs shadow 100 vs baseline Tier C",
        "generate dry-run diagnostic report",
    ],
    "prohibited": [
        "calculate Kelly criterion or position sizing",
        "recommend bets or wagering amounts",
        "change champion strategy or Tier C thresholds",
        "promote production readiness",
        "claim profitability from historical edge",
        "use unvalidated or partially-validated odds rows",
        "use mock odds or fixture data as real market evidence",
        "access the live odds api key env var",
        "compute CLV (reserved for P83 pending closing data and timestamp lineage)",
    ],
    "clv_status": "BLOCKED_UNTIL_P83 — closing-line pairs not yet confirmed in dataset; timestamp lineage must pass before CLV scope activates",
    "production_status": "BLOCKED — P82 is diagnostic dry-run only; paper_only=True remains",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _validate_manifest(manifest: dict) -> dict:
    """
    Validate a candidate intake manifest against the intake manifest schema.
    Returns dict with valid:bool, errors:list.
    """
    errors: list[str] = []
    for spec in INTAKE_MANIFEST_FIELDS:
        field = spec["field"]
        nullable = spec.get("nullable", False)

        if field not in manifest:
            errors.append(f"MISSING_FIELD:{field}")
            continue

        val = manifest[field]

        if not nullable and val is None:
            errors.append(f"NULL_FIELD:{field}")
            continue

        required_value = spec.get("required_value")
        if required_value is not None and val != required_value:
            errors.append(f"WRONG_VALUE:{field}={val!r} (required {required_value!r})")

        forbidden_value = spec.get("forbidden_value")
        if forbidden_value is not None and val == forbidden_value:
            errors.append(f"FORBIDDEN_VALUE:{field}={val!r}")

        allowed_values = spec.get("allowed_values")
        if allowed_values is not None and val not in allowed_values and val is not None:
            errors.append(f"NOT_ALLOWED:{field}={val!r} (allowed: {allowed_values})")

    return {"valid": len(errors) == 0, "errors": errors}


def _run_unlock_decision(manifest: dict) -> dict:
    """
    P82 unlock decision function.
    Returns dict with can_unlock_p82:bool, blocks:list, passed_checks:list.
    """
    blocks: list[str] = []
    passed: list[str] = []

    # 1. Dataset type
    if manifest.get("dataset_type") != "REAL_LEGAL_ODDS_DATASET":
        blocks.append(f"WRONG_DATASET_TYPE:{manifest.get('dataset_type')}")
    else:
        passed.append("DATASET_TYPE_OK")

    # 2. Source license status
    if manifest.get("source_license_status") != "LEGAL_OR_LICENSED":
        blocks.append(f"BAD_LICENSE_STATUS:{manifest.get('source_license_status')}")
    else:
        passed.append("LICENSE_STATUS_OK")

    # 3. API key check
    if manifest.get("contains_api_key") is not False:
        blocks.append("API_KEY_PRESENT_IN_DATA")
    else:
        passed.append("NO_API_KEY_IN_DATA")

    # 4. Raw data policy
    policy = manifest.get("raw_data_policy")
    if policy not in ALLOWED_RAW_DATA_POLICIES:
        blocks.append(f"BAD_RAW_DATA_POLICY:{policy}")
    else:
        passed.append("RAW_DATA_POLICY_OK")

    # 5. Validator output required
    validator_output = manifest.get("_validator_output_state")
    if validator_output != "LEGAL_ODDS_DATASET_VALIDATED_FOR_P82":
        blocks.append(f"VALIDATOR_NOT_PASSED:{validator_output}")
    else:
        passed.append("VALIDATOR_OUTPUT_OK")

    # 6. Governance guardrails
    if GOVERNANCE.get("production_ready") is not False:
        blocks.append("GOVERNANCE_PRODUCTION_READY_MUST_BE_FALSE")
    else:
        passed.append("GOVERNANCE_PRODUCTION_BLOCKED")

    if GOVERNANCE.get("kelly_deploy_allowed") is not False:
        blocks.append("GOVERNANCE_KELLY_DEPLOY_MUST_BE_FALSE")
    else:
        passed.append("GOVERNANCE_KELLY_BLOCKED")

    return {
        "can_unlock_p82": len(blocks) == 0,
        "blocks": blocks,
        "passed_checks": passed,
    }


# ---------------------------------------------------------------------------
# Step functions
# ---------------------------------------------------------------------------

def step1_verify_p81_state() -> dict:
    """Load and verify P81 summary matches required pre-conditions."""
    p81_path = DERIVED / "p81_legal_odds_dataset_validator_contract_summary.json"
    if not p81_path.exists():
        return {"status": "FAIL", "error": "P81 summary missing — STOP"}

    d = json.loads(p81_path.read_text())

    checks = {
        "classification": d.get("p81_classification") == "P81_VALIDATOR_CONTRACT_READY_MOCK_ONLY",
        "p82_unlock_status": d.get("p82_unlock_status") == "BLOCKED_NO_REAL_DATASET",
        "live_api_calls": d.get("live_api_calls") == 0,
        "ev_clv_kelly": d.get("ev_clv_kelly_computed") is False,
        "forbidden_scan_passed": d.get("step8_forbidden_scan", {}).get("scan_passed") is True,
        "production_ready": d.get("governance_snapshot", {}).get("production_ready") is False,
        "real_legal_dataset_available": d.get("step2_input_contract", {}).get("real_legal_dataset_available") is False,
        "mock_cannot_unlock_p82": d.get("step5_mock_fixture_validation", {}).get("mock_cannot_unlock_p82") is True,
    }

    all_pass = all(checks.values())
    return {
        "status": "PASS" if all_pass else "FAIL",
        "p81_classification": d.get("p81_classification"),
        "p82_unlock_status": d.get("p82_unlock_status"),
        "live_api_calls": d.get("live_api_calls"),
        "checks": checks,
        "input_types_defined": d.get("step2_input_contract", {}).get("input_types_defined", []),
        "gates_defined": [g["gate"] for g in d.get("step4_validator_gates", {}).get("gates_defined", [])],
        "validator_script_exists": (REPO_ROOT / "scripts" / "_p81_legal_odds_dataset_validator_contract.py").exists(),
    }


def step2_define_intake_manifest() -> dict:
    """Define the intake manifest schema for a future real legal odds dataset."""
    return {
        "manifest_field_count": len(INTAKE_MANIFEST_FIELDS),
        "manifest_fields": INTAKE_MANIFEST_FIELDS,
        "required_dataset_type": "REAL_LEGAL_ODDS_DATASET",
        "required_license_status": "LEGAL_OR_LICENSED",
        "allowed_raw_data_policies": ALLOWED_RAW_DATA_POLICIES,
        "contains_api_key_must_be": False,
        "expected_schema_version": "p81-v1",
        "validator_script": "scripts/_p81_legal_odds_dataset_validator_contract.py",
        "notes": [
            "manifest must be committed before dataset is loaded for P82",
            "checksum_hash must be computed before validator is invoked",
            "allowed_next_phase is P82 only after validator returns LEGAL_ODDS_DATASET_VALIDATED_FOR_P82",
        ],
    }


def step3_define_blocker_checklist() -> dict:
    """Define and return the blocker closure checklist."""
    real_data_blockers = [b for b in BLOCKER_CHECKLIST if b["blocker_id"] in REAL_DATA_BLOCKER_IDS]
    governance_blockers = [b for b in BLOCKER_CHECKLIST if b["blocker_id"] in GOVERNANCE_BLOCKER_IDS]

    all_real_blocked = all(b["current_status"] == "BLOCKED_PENDING_REAL_DATASET" for b in real_data_blockers)
    all_gov_active = all(b["current_status"] == "ACTIVE_GUARDRAIL" for b in governance_blockers)

    return {
        "total_blockers": len(BLOCKER_CHECKLIST),
        "real_data_blockers_count": len(real_data_blockers),
        "governance_blockers_count": len(governance_blockers),
        "all_real_data_blockers": [b["blocker_id"] for b in real_data_blockers],
        "all_governance_blockers": [b["blocker_id"] for b in governance_blockers],
        "all_real_data_currently_blocked": all_real_blocked,
        "all_governance_currently_active": all_gov_active,
        "checklist": BLOCKER_CHECKLIST,
        "p82_can_open": False,
        "p82_open_requires": "All 10 real-data blockers CLOSED + 2 governance guardrails ACTIVE",
    }


def step4_define_unlock_decision() -> dict:
    """Define P82 unlock decision function semantics and run test scenarios."""

    # Scenario A — real legal dataset with validator pass (hypothetical)
    mock_real_manifest = {
        "manifest_id": "HYPOTHETICAL-REAL-001",
        "dataset_path": "data/mlb_2025/derived/legal_odds_2025.jsonl",
        "dataset_type": "REAL_LEGAL_ODDS_DATASET",
        "season": 2025,
        "source_name": "HypotheticalLegalProvider",
        "source_license_status": "LEGAL_OR_LICENSED",
        "source_license_evidence_ref": "docs/legal/provider_license_2025.pdf",
        "acquisition_method": "PAID_API",
        "acquired_at_utc": "2026-05-26T00:00:00+00:00",
        "acquired_by": "data_engineer",
        "raw_data_policy": "LOCAL_ONLY_HASH_COMMITTED",
        "checksum_hash": "a" * 64,
        "row_count": 5000,
        "expected_schema_version": "p81-v1",
        "validator_script": "scripts/_p81_legal_odds_dataset_validator_contract.py",
        "validator_command": "python scripts/_p81_legal_odds_dataset_validator_contract.py",
        "p81_validator_version": "p81-v1",
        "storage_policy": "LOCAL_ONLY",
        "commit_policy": "HASH_ONLY_NO_RAW_DATA",
        "contains_api_key": False,
        "contains_personal_data": False,
        "allowed_next_phase": "P82",
        "blocked_next_phase_reason": None,
        "_validator_output_state": "LEGAL_ODDS_DATASET_VALIDATED_FOR_P82",
    }

    # Scenario B — mock fixture (must fail)
    mock_fixture_manifest = dict(mock_real_manifest)
    mock_fixture_manifest["dataset_type"] = "MOCK_ODDS_FIXTURE"
    mock_fixture_manifest["_validator_output_state"] = "MOCK_FIXTURE_VALIDATOR_PASS_NOT_MARKET_READY"

    # Scenario C — unknown source (must fail)
    unknown_source_manifest = dict(mock_real_manifest)
    unknown_source_manifest["source_license_status"] = "UNKNOWN"
    unknown_source_manifest["_validator_output_state"] = None

    # Scenario D — scraping prohibited (must fail)
    scraping_manifest = dict(mock_real_manifest)
    scraping_manifest["source_license_status"] = "SCRAPING_TOS_VIOLATION"

    # Scenario E — missing dataset (must fail)
    missing_manifest = dict(mock_real_manifest)
    missing_manifest["dataset_type"] = None
    missing_manifest["_validator_output_state"] = None

    # Scenario F — API key in data (must fail)
    api_key_manifest = dict(mock_real_manifest)
    api_key_manifest["contains_api_key"] = True

    # Scenario G — unknown raw data policy (must fail)
    bad_policy_manifest = dict(mock_real_manifest)
    bad_policy_manifest["raw_data_policy"] = "UNKNOWN"

    # Scenario H — validator did not pass (must fail)
    no_validator_pass_manifest = dict(mock_real_manifest)
    no_validator_pass_manifest["_validator_output_state"] = "BLOCKED_SOURCE_LEGALITY"

    scenarios = {
        "HYPOTHETICAL_REAL_LEGAL": _run_unlock_decision(mock_real_manifest),
        "MOCK_FIXTURE": _run_unlock_decision(mock_fixture_manifest),
        "UNKNOWN_SOURCE": _run_unlock_decision(unknown_source_manifest),
        "SCRAPING_PROHIBITED": _run_unlock_decision(scraping_manifest),
        "MISSING_DATASET": _run_unlock_decision(missing_manifest),
        "API_KEY_IN_DATA": _run_unlock_decision(api_key_manifest),
        "BAD_RAW_DATA_POLICY": _run_unlock_decision(bad_policy_manifest),
        "VALIDATOR_NOT_PASSED": _run_unlock_decision(no_validator_pass_manifest),
    }

    # Verify expected: only HYPOTHETICAL_REAL_LEGAL should unlock
    only_real_unlocks = (
        scenarios["HYPOTHETICAL_REAL_LEGAL"]["can_unlock_p82"] is True
        and all(
            not scenarios[k]["can_unlock_p82"]
            for k in scenarios
            if k != "HYPOTHETICAL_REAL_LEGAL"
        )
    )

    return {
        "decision_function": "_run_unlock_decision(manifest)",
        "required_conditions": [
            "manifest.dataset_type == REAL_LEGAL_ODDS_DATASET",
            "manifest.source_license_status == LEGAL_OR_LICENSED",
            "manifest.contains_api_key == False",
            "manifest.raw_data_policy in allowed policies",
            "manifest._validator_output_state == LEGAL_ODDS_DATASET_VALIDATED_FOR_P82",
            "GOVERNANCE.production_ready == False",
            "GOVERNANCE.kelly_deploy_allowed == False",
        ],
        "scenarios": scenarios,
        "only_real_legal_dataset_unlocks": only_real_unlocks,
        "current_p82_status": "BLOCKED_NO_REAL_DATASET",
    }


def step5_define_p82_scope() -> dict:
    """Define the future P82 dry-run scope."""
    return {
        "phase": "P82",
        "phase_name": "Legal Odds Market Edge Dry-Run",
        "prerequisite": "P82A_REAL_LEGAL_ODDS_INTAKE_GATE_READY + real legal dataset validated",
        "allowed": P82_DRY_RUN_SCOPE["allowed"],
        "prohibited": P82_DRY_RUN_SCOPE["prohibited"],
        "clv_status": P82_DRY_RUN_SCOPE["clv_status"],
        "production_status": P82_DRY_RUN_SCOPE["production_status"],
        "kelly_status": "PERMANENTLY_BLOCKED_IN_P82",
        "ev_kelly_clv_computed_in_p82a": False,
    }


def step6_verify_source_artifacts() -> dict:
    """Verify all required source artifacts exist."""
    results = {}
    for fname in SOURCE_ARTIFACTS:
        path = DERIVED / fname
        results[fname] = path.exists()
    all_present = all(results.values())
    return {
        "all_present": all_present,
        "artifact_count": len(SOURCE_ARTIFACTS),
        "artifacts": results,
        "status": "PASS" if all_present else "FAIL",
    }


def step7_forbidden_scan() -> dict:
    """
    Scan the script file for forbidden phrases.
    Excludes this function body and the GOVERNANCE dict block.
    """
    script_path = Path(__file__)
    lines = script_path.read_text().splitlines()

    forbidden_checks = [
        ("tsl_crawler", "TSL crawler modification"),
        ("runtime_recommendation", "runtime recommendation modification"),
        ("THE_ODDS_API_KEY", "API key access"),
        ("kelly_bet", "Kelly bet deployment"),
        ("deploy_kelly", "deploy Kelly"),
        ("production_ready.*True", "production_ready set True"),
        ("kelly_deploy_allowed.*True", "kelly_deploy_allowed set True"),
        ("real_bet.*True", "real bet enabled"),
        ("champion_replacement.*True", "champion replacement enabled"),
        ("profitability_claim.*True", "profitability claim enabled"),
    ]

    # Locate self function body start/end
    self_func_start = None
    self_func_end = len(lines)
    for i, line in enumerate(lines):
        if self_func_start is None and "def step7_forbidden_scan" in line:
            self_func_start = i
        if self_func_start is not None and i > self_func_start:
            stripped = line.rstrip()
            if stripped and not stripped[0].isspace() and not stripped.startswith("#"):
                self_func_end = i
                break

    # Locate GOVERNANCE dict block
    gov_block_start = None
    gov_block_end = None
    for i, line in enumerate(lines):
        if "GOVERNANCE: dict = {" in line:
            gov_block_start = i
        if gov_block_start is not None and gov_block_end is None and i > gov_block_start:
            if line.strip() == "}":
                gov_block_end = i + 1
                break

    def _in_excluded_zone(idx: int) -> bool:
        if self_func_start is not None and self_func_start <= idx < self_func_end:
            return True
        if gov_block_start is not None and gov_block_end is not None:
            if gov_block_start <= idx < gov_block_end:
                return True
        return False

    import re
    violations = []
    for i, line in enumerate(lines):
        if _in_excluded_zone(i):
            continue
        for pattern, label in forbidden_checks:
            if re.search(pattern, line, re.IGNORECASE):
                violations.append({"line": i + 1, "label": label, "content": line.strip()})
                break

    return {
        "scan_passed": len(violations) == 0,
        "violations_count": len(violations),
        "violations": violations,
        "patterns_checked": len(forbidden_checks),
        "lines_scanned": len(lines),
        "self_exclusion_range": [self_func_start, self_func_end],
        "governance_exclusion_range": [gov_block_start, gov_block_end],
    }


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def _write_report(summary: dict, path: Path) -> None:
    s1 = summary["step1_p81_verification"]
    s2 = summary["step2_intake_manifest"]
    s3 = summary["step3_blocker_checklist"]
    s4 = summary["step4_unlock_decision"]
    s5 = summary["step5_p82_scope"]
    s6 = summary["step6_source_artifacts"]
    s7 = summary["step7_forbidden_scan"]

    lines = [
        f"# P82A — Real Legal Odds Dataset Intake Gate + P82 Blocker Closure Plan",
        f"",
        f"**Snapshot**: {summary['snapshot_id']}  ",
        f"**Schema version**: {summary['schema_version']}  ",
        f"**Classification**: `{summary['p82a_classification']}`  ",
        f"**Generated**: {summary['generated_at_utc']}",
        f"",
        f"---",
        f"",
        f"## Step 1 — P81 State Verification",
        f"",
        f"| Check | Result |",
        f"|---|---|",
    ]
    for k, v in s1["checks"].items():
        lines.append(f"| {k} | {'✅ PASS' if v else '❌ FAIL'} |")
    lines += [
        f"",
        f"- **P81 classification**: `{s1['p81_classification']}`",
        f"- **P82 unlock status**: `{s1['p82_unlock_status']}`",
        f"- **live_api_calls**: {s1['live_api_calls']}",
        f"- **Validator script exists**: {s1['validator_script_exists']}",
        f"- **Input types**: {', '.join(s1['input_types_defined'])}",
        f"- **Validator gates**: {', '.join(s1['gates_defined'])}",
        f"",
        f"---",
        f"",
        f"## Step 2 — Intake Manifest Schema",
        f"",
        f"**{s2['manifest_field_count']} required fields**",
        f"",
        f"| Field | Type | Required Value / Rule |",
        f"|---|---|---|",
    ]
    for spec in s2["manifest_fields"]:
        rule = ""
        if "required_value" in spec:
            rule = f"Must be `{spec['required_value']}`"
        elif "forbidden_value" in spec:
            rule = f"Forbidden: `{spec['forbidden_value']}`; allowed: {spec.get('allowed_values', '')}"
        elif "allowed_values" in spec:
            rule = f"Allowed: {spec['allowed_values']}"
        lines.append(f"| `{spec['field']}` | {spec['type']} | {rule or spec.get('description', '')} |")

    lines += [
        f"",
        f"**Allowed raw_data_policy values**: {', '.join(s2['allowed_raw_data_policies'])}",
        f"",
        f"---",
        f"",
        f"## Step 3 — Blocker Closure Checklist",
        f"",
        f"**{s3['total_blockers']} blockers** ({s3['real_data_blockers_count']} real-data, {s3['governance_blockers_count']} governance)",
        f"",
        f"| Blocker ID | Current Status | Unlock Effect |",
        f"|---|---|---|",
    ]
    for b in s3["checklist"]:
        lines.append(f"| `{b['blocker_id']}` | `{b['current_status']}` | {b['unlock_effect']} |")

    lines += [
        f"",
        f"**P82 can open**: {s3['p82_can_open']}  ",
        f"**Requires**: {s3['p82_open_requires']}",
        f"",
        f"---",
        f"",
        f"## Step 4 — P82 Unlock Decision Function",
        f"",
        f"**Function**: `_run_unlock_decision(manifest)`",
        f"",
        f"**Required conditions to unlock P82**:",
        f"",
    ]
    for c in s4["required_conditions"]:
        lines.append(f"- {c}")

    lines += [
        f"",
        f"**Scenario test results**:",
        f"",
        f"| Scenario | can_unlock_p82 | Blocks |",
        f"|---|---|---|",
    ]
    for sc_name, sc in s4["scenarios"].items():
        lines.append(f"| {sc_name} | `{sc['can_unlock_p82']}` | {'; '.join(sc['blocks'][:2]) or '—'} |")

    lines += [
        f"",
        f"**Only REAL_LEGAL_ODDS_DATASET unlocks P82**: {s4['only_real_legal_dataset_unlocks']}",
        f"**Current P82 status**: `{s4['current_p82_status']}`",
        f"",
        f"---",
        f"",
        f"## Step 5 — Future P82 Dry-Run Scope",
        f"",
        f"**Allowed in P82**:",
        f"",
    ]
    for item in s5["allowed"]:
        lines.append(f"- {item}")

    lines += [f"", f"**Prohibited in P82**:", f""]
    for item in s5["prohibited"]:
        lines.append(f"- {item}")

    lines += [
        f"",
        f"**CLV status**: {s5['clv_status']}",
        f"**Production status**: {s5['production_status']}",
        f"",
        f"---",
        f"",
        f"## Step 6 — Source Artifacts",
        f"",
        f"| Artifact | Present |",
        f"|---|---|",
    ]
    for fname, present in s6["artifacts"].items():
        lines.append(f"| {fname} | {'✅' if present else '❌'} |")

    lines += [
        f"",
        f"---",
        f"",
        f"## Step 7 — Forbidden Phrase Scan",
        f"",
        f"- **Scan passed**: {s7['scan_passed']}",
        f"- **Violations**: {s7['violations_count']}",
        f"- **Patterns checked**: {s7['patterns_checked']}",
        f"- **Lines scanned**: {s7['lines_scanned']}",
        f"",
        f"---",
        f"",
        f"## Governance Invariants",
        f"",
        f"| Key | Value |",
        f"|---|---|",
    ]
    for k, v in summary["governance_snapshot"].items():
        lines.append(f"| `{k}` | `{v}` |")

    lines += [
        f"",
        f"---",
        f"",
        f"## STOP Conditions",
        f"",
        f"P82 **remains blocked** until all of the following are satisfied:",
        f"",
        f"1. A real legal odds dataset file is present at manifest.dataset_path",
        f"2. source_license_status == LEGAL_OR_LICENSED (evidence documented)",
        f"3. raw_data_policy in allowed values",
        f"4. P81 validator returns LEGAL_ODDS_DATASET_VALIDATED_FOR_P82",
        f"5. All 10 real-data blockers are CLOSED",
        f"6. contains_api_key == False",
        f"7. GOVERNANCE.production_ready == False",
        f"8. GOVERNANCE.kelly_deploy_allowed == False",
        f"",
        f"Mock data, fixture data, scraping-sourced data, or unknown-source data can **never** unlock P82.",
        f"",
        f"---",
        f"",
        f"*paper_only=True | diagnostic_only=True | live_api_calls=0 | ev_calculated=False | kelly_deploy_allowed=False*",
    ]

    path.write_text("\n".join(lines))


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def main() -> dict:
    print("[P82A] Starting: Real Legal Odds Dataset Intake Gate")

    s1 = step1_verify_p81_state()
    print(f"[P82A] Step 1: P81 verification = {s1['status']}")
    if s1["status"] != "PASS":
        raise RuntimeError(f"STOP — P81 verification failed: {s1}")

    s2 = step2_define_intake_manifest()
    print(f"[P82A] Step 2: Intake manifest schema — {s2['manifest_field_count']} fields")

    s3 = step3_define_blocker_checklist()
    print(f"[P82A] Step 3: Blockers — {s3['total_blockers']} defined, p82_can_open={s3['p82_can_open']}")

    s4 = step4_define_unlock_decision()
    print(f"[P82A] Step 4: Unlock decision — only_real_unlocks={s4['only_real_legal_dataset_unlocks']}")

    s5 = step5_define_p82_scope()
    print(f"[P82A] Step 5: P82 scope — {len(s5['allowed'])} allowed, {len(s5['prohibited'])} prohibited")

    s6 = step6_verify_source_artifacts()
    print(f"[P82A] Step 6: Source artifacts — all_present={s6['all_present']}")

    s7 = step7_forbidden_scan()
    print(f"[P82A] Step 7: Scan passed = {s7['scan_passed']} (violations: {s7['violations_count']})")

    # Classification
    if (
        s1["status"] == "PASS"
        and s6["all_present"]
        and s7["scan_passed"]
        and s4["only_real_legal_dataset_unlocks"]
    ):
        classification = "P82A_REAL_LEGAL_ODDS_INTAKE_GATE_READY"
    elif not s6["all_present"]:
        classification = "P82A_BLOCKED_BY_MISSING_P81_ARTIFACT"
    else:
        classification = "P82A_FAILED_VALIDATION"

    summary = {
        "p82a_classification": classification,
        "schema_version": SCHEMA_VERSION,
        "snapshot_id": SNAPSHOT_ID,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "governance_snapshot": {k: v for k, v in GOVERNANCE.items()},
        "step1_p81_verification": s1,
        "step2_intake_manifest": s2,
        "step3_blocker_checklist": s3,
        "step4_unlock_decision": s4,
        "step5_p82_scope": s5,
        "step6_source_artifacts": s6,
        "step7_forbidden_scan": s7,
        "live_api_calls": GOVERNANCE["live_api_calls"],
        "ev_clv_kelly_computed": False,
        "p82_unlock_status": "BLOCKED_NO_REAL_DATASET",
        "p82a_current_status": "INTAKE_GATE_DEFINED — awaiting real legal odds dataset",
    }

    # Write JSON
    out_json = DERIVED / "p82a_real_legal_odds_intake_gate_summary.json"
    out_json.write_text(json.dumps(summary, indent=2))
    print(f"[P82A] Summary written: {out_json.relative_to(REPO_ROOT)}")

    # Write reports
    report_dir = REPO_ROOT / "report"
    report_dir.mkdir(exist_ok=True)
    report_path = report_dir / "p82a_real_legal_odds_intake_gate_20260526.md"
    _write_report(summary, report_path)
    print(f"[P82A] Report written: {report_path.relative_to(REPO_ROOT)}")

    betting_plan_dir = REPO_ROOT / "00-BettingPlan" / "20260526"
    betting_plan_dir.mkdir(exist_ok=True)
    bp_path = betting_plan_dir / "p82a_real_legal_odds_intake_gate_20260526.md"
    _write_report(summary, bp_path)
    print(f"[P82A] BettingPlan copy: {bp_path.relative_to(REPO_ROOT)}")

    print(f"[P82A] Classification: {classification}")
    print(f"[P82A] P82 unlock status: BLOCKED_NO_REAL_DATASET")
    print(f"[P82A] Forbidden scan: PASS={s7['scan_passed']} violations={s7['violations_count']}")

    return summary


if __name__ == "__main__":
    main()
