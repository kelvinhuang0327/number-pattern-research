"""
P82B — Raw Paid Odds Data Storage / Commit Policy Contract
===========================================================
Policy and contract definition only.
No real odds files. No API calls. No data pull. No market-edge computation.

Classification target: P82B_RAW_PAID_DATA_POLICY_READY
"""

from __future__ import annotations

import json
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
    "p82b_storage_policy_defined": True,
}

SCHEMA_VERSION = "p82b-v1"
SNAPSHOT_ID = "raw_paid_odds_data_policy_contract_20260526"

REPO_ROOT = Path(__file__).parent.parent
DERIVED = REPO_ROOT / "data" / "mlb_2025" / "derived"

# ---------------------------------------------------------------------------
# Required source artifacts (P72A → P82A)
# ---------------------------------------------------------------------------
SOURCE_ARTIFACTS: list[str] = [
    "p82a_real_legal_odds_intake_gate_summary.json",
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
# Artifact classes (9 classes)
# ---------------------------------------------------------------------------
ARTIFACT_CLASSES: list[dict] = [
    {
        "class_id": "RAW_PAID_ODDS_DATA",
        "description": "Original paid CSV/JSON/API export from a licensed data provider",
        "examples": ["odds_2025_raw.csv", "paid_feed_export.json"],
        "default_policy": "LOCAL_ONLY_DO_NOT_COMMIT",
        "can_commit": False,
        "can_stage": False,
        "storage_location": "local_external_only — not inside repo directory",
        "allowed_file_patterns": ["*_raw_*.csv", "*_raw_*.json"],
        "forbidden_file_patterns": ["data/**/*_raw_*.csv", "data/**/*_raw_*.json"],
        "required_metadata": ["checksum_hash", "row_count", "source_name", "acquisition_date"],
        "required_redactions": ["api_key_value", "personal_data", "proprietary_row_values"],
        "review_gate": "COMMIT_ONLY_CHECKSUM_AND_DERIVED_SUMMARY",
        "stop_condition": "STOP if raw paid odds rows appear in any staged file",
        "allowed_downstream_use": ["P81 validator local only", "P82 dry-run local only"],
    },
    {
        "class_id": "RAW_FREE_LEGAL_ODDS_DATA",
        "description": "Legally redistributable raw odds data (open license or explicit permission)",
        "examples": ["free_odds_feed_2025.csv", "open_odds_export.json"],
        "default_policy": "COMMIT_ALLOWED_ONLY_IF_LICENSE_ALLOWS",
        "can_commit": None,
        "can_stage": None,
        "storage_location": "data/mlb_2025/derived/ (if license confirmed) or local",
        "allowed_file_patterns": ["*_free_odds_*.csv", "*_open_odds_*.json"],
        "forbidden_file_patterns": [],
        "required_metadata": ["license_type", "license_url", "source_name", "checksum_hash"],
        "required_redactions": [],
        "review_gate": "LICENSE_EVIDENCE_MUST_BE_DOCUMENTED_BEFORE_COMMIT",
        "stop_condition": "STOP if license evidence is missing or unverified before staging",
        "allowed_downstream_use": ["P81 validator", "P82 dry-run", "backtest"],
    },
    {
        "class_id": "VALIDATION_MANIFEST",
        "description": "Metadata manifest only; no raw data rows; no proprietary values",
        "examples": ["intake_manifest_2025.json"],
        "default_policy": "COMMIT_ALLOWED",
        "can_commit": True,
        "can_stage": True,
        "storage_location": "data/mlb_2025/derived/",
        "allowed_file_patterns": ["*_manifest_*.json", "*_intake_*.json"],
        "forbidden_file_patterns": [],
        "required_metadata": ["manifest_id", "checksum_hash", "row_count", "schema_version"],
        "required_redactions": ["api_key_value", "raw_data_rows"],
        "review_gate": "REVIEW_NO_API_KEY_NO_RAW_ROWS_BEFORE_COMMIT",
        "stop_condition": "STOP if contains_api_key flag is True or raw data rows are present",
        "allowed_downstream_use": ["P82A gate", "P81 validator", "P82 dry-run"],
    },
    {
        "class_id": "CHECKSUM_ONLY_RECORD",
        "description": "Hash, row count, and schema version only; no data rows",
        "examples": ["p82_odds_checksum_2025.json"],
        "default_policy": "COMMIT_ALLOWED",
        "can_commit": True,
        "can_stage": True,
        "storage_location": "data/mlb_2025/derived/",
        "allowed_file_patterns": ["*_checksum_*.json", "*_hash_record_*.json"],
        "forbidden_file_patterns": [],
        "required_metadata": ["checksum_hash", "row_count", "schema_version", "dataset_alias"],
        "required_redactions": [],
        "review_gate": "CONFIRM_NO_ROW_LEVEL_ODDS_VALUES_BEFORE_COMMIT",
        "stop_condition": "STOP if any raw odds row value appears in the committed file",
        "allowed_downstream_use": ["integrity check", "lineage audit"],
    },
    {
        "class_id": "DERIVED_VALIDATION_SUMMARY",
        "description": "Pass/fail validation summary with counts and schema stats; no raw proprietary rows",
        "examples": ["p81_legal_odds_validator_summary.json"],
        "default_policy": "COMMIT_ALLOWED",
        "can_commit": True,
        "can_stage": True,
        "storage_location": "data/mlb_2025/derived/",
        "allowed_file_patterns": ["*_summary.json", "*_validation_*.json"],
        "forbidden_file_patterns": [],
        "required_metadata": ["validation_status", "row_count", "schema_version", "gates_passed"],
        "required_redactions": ["raw_odds_rows", "proprietary_values"],
        "review_gate": "CONFIRM_AGGREGATE_COUNTS_ONLY_NO_ROW_LEVEL",
        "stop_condition": "STOP if row-level paid odds values appear in the summary file",
        "allowed_downstream_use": ["P82 gate check", "pipeline audit"],
    },
    {
        "class_id": "DERIVED_MARKET_EDGE_SUMMARY",
        "description": "Future P82 aggregate edge diagnostics only; no row-level paid odds leakage",
        "examples": ["p82_market_edge_dry_run_summary.json"],
        "default_policy": "COMMIT_ALLOWED_AGGREGATE_ONLY",
        "can_commit": True,
        "can_stage": True,
        "storage_location": "data/mlb_2025/derived/",
        "allowed_file_patterns": ["*_edge_dry_run_*.json", "*_market_edge_summary_*.json"],
        "forbidden_file_patterns": [],
        "required_metadata": ["model_version", "dataset_alias", "aggregate_edge_stats"],
        "required_redactions": ["raw_odds_rows", "row_level_moneylines"],
        "review_gate": "CONFIRM_AGGREGATE_STATS_ONLY_NO_ROW_LEVEL_PAID_ODDS",
        "stop_condition": "STOP if row-level paid odds appear in any committed file",
        "allowed_downstream_use": ["P82 diagnostic audit", "model comparison"],
    },
    {
        "class_id": "LOCAL_REPRODUCIBILITY_NOTE",
        "description": "Path placeholders and run commands; no secrets; reproducibility instructions only",
        "examples": ["p82_local_run_notes.md", "p82_reproducibility_guide.md"],
        "default_policy": "COMMIT_ALLOWED",
        "can_commit": True,
        "can_stage": True,
        "storage_location": "docs/ or report/",
        "allowed_file_patterns": ["*_local_run_*.md", "*_reproducibility_*.md"],
        "forbidden_file_patterns": [],
        "required_metadata": [],
        "required_redactions": ["api_key_value", "secret_value", "paid_data_local_path"],
        "review_gate": "CONFIRM_NO_SECRETS_NO_RAW_DATA_PATH_BEFORE_COMMIT",
        "stop_condition": "STOP if API key value or secret appears in any committed file",
        "allowed_downstream_use": ["onboarding", "audit trail"],
    },
    {
        "class_id": "SECRET_OR_API_KEY",
        "description": "API key, database password, or any secret value — never committed",
        "examples": [".env", "secrets.json", "credentials.json"],
        "default_policy": "HARD_FORBIDDEN",
        "can_commit": False,
        "can_stage": False,
        "storage_location": "NEVER — must not exist anywhere in git history",
        "allowed_file_patterns": [],
        "forbidden_file_patterns": [".env", ".env.*", "*secret*", "*credential*", "*.pem", "*.key"],
        "required_metadata": [],
        "required_redactions": ["ALL_CONTENT"],
        "review_gate": "HARD_BLOCK_NO_OVERRIDE_ALLOWED",
        "stop_condition": "STOP immediately — rotate key, purge file, do not commit under any circumstance",
        "allowed_downstream_use": [],
    },
    {
        "class_id": "MOCK_FIXTURE",
        "description": "Mock or fixture odds data; explicitly labeled as mock; not valid market evidence",
        "examples": ["fixture_odds_2025.json", "mock_odds_test.json"],
        "default_policy": "COMMIT_ALLOWED_IF_EXPLICITLY_LABELED_MOCK",
        "can_commit": True,
        "can_stage": True,
        "storage_location": "data/fixtures/ or tests/fixtures/",
        "allowed_file_patterns": ["*fixture*", "*mock*"],
        "forbidden_file_patterns": [],
        "required_metadata": ["mock_flag", "dataset_type"],
        "required_redactions": [],
        "review_gate": "CONFIRM_LABELED_MOCK_NOT_TREATED_AS_REAL_MARKET_EVIDENCE",
        "stop_condition": "STOP if mock data is treated as real market evidence in any pipeline step",
        "allowed_downstream_use": ["unit tests", "contract validation dry-run only"],
    },
]

ARTIFACT_CLASS_IDS: list[str] = [c["class_id"] for c in ARTIFACT_CLASSES]

# ---------------------------------------------------------------------------
# Commit policy matrix — keyed by class_id
# ---------------------------------------------------------------------------
COMMIT_POLICY_MATRIX: dict[str, dict] = {
    c["class_id"]: {
        "can_commit": c["can_commit"],
        "can_stage": c["can_stage"],
        "storage_location": c["storage_location"],
        "allowed_file_patterns": c["allowed_file_patterns"],
        "forbidden_file_patterns": c.get("forbidden_file_patterns", []),
        "required_metadata": c["required_metadata"],
        "required_redactions": c["required_redactions"],
        "review_gate": c["review_gate"],
        "stop_condition": c["stop_condition"],
        "allowed_downstream_use": c["allowed_downstream_use"],
    }
    for c in ARTIFACT_CLASSES
}

# ---------------------------------------------------------------------------
# Staging guard contract
# ---------------------------------------------------------------------------
STAGING_GUARD_CONTRACT: dict = {
    "guard_id": "p82b_staging_guard_v1",
    "description": "Prevents raw paid data, secrets, and unpolicied odds from reaching git",
    "blocks": [
        {
            "rule_id": "BLOCK_ENV_FILE",
            "description": "Block .env files and environment config files from being staged",
            "file_patterns": [".env", ".env.*", ".env.local", ".env.production"],
            "reason": "Environment files may contain secret values and provider credentials",
            "guard_state": "BLOCK_SECRET",
        },
        {
            "rule_id": "BLOCK_API_KEY_PATTERN",
            "description": "Block files whose content contains API key-like string patterns",
            "detect_patterns": ["[A-Za-z0-9]{32,}", "[A-Za-z0-9_-]{40,}"],
            "note": "Covers paid data provider key formats; human review required before override",
            "guard_state": "BLOCK_SECRET",
        },
        {
            "rule_id": "BLOCK_RAW_PAID_CSV",
            "description": "Block raw paid odds CSV/JSON files under data/ from being staged",
            "file_patterns": [
                "data/**/*paid*odds*.csv",
                "data/**/*raw*odds*.json",
                "data/**/*paid*odds*.json",
            ],
            "guard_state": "BLOCK_RAW_PAID_DATA",
        },
        {
            "rule_id": "BLOCK_REAL_ODDS_FILENAME",
            "description": "Block specific filename patterns associated with raw real odds exports",
            "file_patterns": [
                "*odds_2024_real.csv",
                "*paid*odds*.csv",
                "*raw*odds*.json",
                "*the_odds_api*raw*",
            ],
            "guard_state": "BLOCK_UNPOLICIED_ODDS",
        },
        {
            "rule_id": "BLOCK_CONTAINS_API_KEY_FLAG",
            "description": "Block any manifest/JSON where the contains_api_key field is not False",
            "detect_json_key": "contains_api_key",
            "detect_forbidden_json_value": True,
            "note": "contains_api_key must be False in all committed manifests",
            "guard_state": "BLOCK_SECRET",
        },
        {
            "rule_id": "BLOCK_ROW_LEVEL_ODDS",
            "description": "Block committed markdown/JSON containing row-level odds values unless explicitly aggregate/derived",
            "detect_patterns": ["moneyline_home.*[0-9]+", "raw_odds_row", "row_level_odds"],
            "exemptions": ["files in data/fixtures/", "files with mock_flag explicitly set True"],
            "guard_state": "BLOCK_ROW_LEVEL_LEAKAGE",
        },
    ],
    "guard_states": [
        "STAGE_CLEAN",
        "BLOCK_RAW_PAID_DATA",
        "BLOCK_SECRET",
        "BLOCK_UNPOLICIED_ODDS",
        "BLOCK_ROW_LEVEL_LEAKAGE",
        "REVIEW_REQUIRED",
    ],
    "default_state": "STAGE_CLEAN",
    "hard_block_classes": ["SECRET_OR_API_KEY", "RAW_PAID_ODDS_DATA"],
    "review_required_classes": ["RAW_FREE_LEGAL_ODDS_DATA"],
    "auto_pass_classes": [
        "VALIDATION_MANIFEST",
        "CHECKSUM_ONLY_RECORD",
        "DERIVED_VALIDATION_SUMMARY",
        "DERIVED_MARKET_EDGE_SUMMARY",
        "LOCAL_REPRODUCIBILITY_NOTE",
        "MOCK_FIXTURE",
    ],
}

# ---------------------------------------------------------------------------
# Manifest integration policy (extends P82A intake manifest)
# ---------------------------------------------------------------------------
MANIFEST_INTEGRATION_POLICY: dict = {
    "source": "P82A INTAKE_MANIFEST_FIELDS (23 fields)",
    "raw_data_policy": {
        "field": "raw_data_policy",
        "allowed_values": [
            "LOCAL_ONLY_HASH_COMMITTED",
            "DERIVED_ONLY_COMMIT",
            "COMMIT_ALLOWED_LICENSE_VERIFIED",
            "MOCK_ONLY",
        ],
        "forbidden_values": [
            "UNKNOWN",
            "COMMIT_RAW_PAID_DATA",
            "EMBED_SECRET",
            "UNLICENSED_SOURCE",
        ],
        "default": "LOCAL_ONLY_HASH_COMMITTED",
        "note": "Must be explicitly decided before manifest is committed",
    },
    "storage_policy": {
        "field": "storage_policy",
        "allowed_values": [
            "LOCAL_ONLY",
            "LOCAL_EXTERNAL_PATH",
            "CLOUD_PRIVATE",
            "DERIVED_ONLY_IN_REPO",
        ],
        "forbidden_values": ["PUBLIC_REPO", "COMMIT_RAW"],
        "note": "Raw paid data must never be in PUBLIC_REPO storage",
    },
    "commit_policy": {
        "field": "commit_policy",
        "allowed_values": [
            "HASH_ONLY_NO_RAW_DATA",
            "MANIFEST_AND_DERIVED_ONLY",
            "COMMIT_ALLOWED_LICENSE_VERIFIED",
            "NO_COMMIT",
        ],
        "forbidden_values": ["COMMIT_RAW_DATA", "COMMIT_WITH_SECRET"],
        "note": "Raw paid rows must never be committed even if license allows redistribution",
    },
    "dataset_path_policy": (
        "manifest.dataset_path must be a local placeholder only; "
        "must not reveal the real raw data path in any committed file"
    ),
    "checksum_requirement": (
        "SHA-256 checksum must be computed from the raw file before staging the manifest; "
        "checksum_hash is a mandatory non-nullable field"
    ),
    "license_evidence_requirement": (
        "source_license_evidence_ref must point to a stored license document; "
        "cannot be empty or a placeholder like TBD"
    ),
    "secret_in_manifest_policy": (
        "HARD_FORBIDDEN — manifest.contains_api_key must be False; "
        "any manifest with contains_api_key not False is blocked by the staging guard"
    ),
    "local_path_policy": (
        "manifest may reference a local external path for the raw file, "
        "but that path must not appear in any committed manifest or summary file"
    ),
    "p81_output_storage": (
        "P81 validator output (DERIVED_VALIDATION_SUMMARY) is committed to "
        "data/mlb_2025/derived/ without any raw odds rows — aggregate counts only"
    ),
    "future_p82_storage": (
        "P82 edge dry-run summary (DERIVED_MARKET_EDGE_SUMMARY) is committed "
        "as aggregate statistics only — no row-level paid odds in committed file"
    ),
}

# ---------------------------------------------------------------------------
# Future workflow — 7 steps to safely introduce a real legal odds dataset
# ---------------------------------------------------------------------------
FUTURE_WORKFLOW: list[dict] = [
    {
        "step": 1,
        "action": "Acquire legal odds data outside git",
        "detail": (
            "Obtain dataset from a licensed provider via paid subscription or licensed feed; "
            "verify source_license_status will be LEGAL_OR_LICENSED before download"
        ),
        "where": "External acquisition — never inside repo directory",
        "gate": "Source must have a verifiable legal license; LEGAL_OR_LICENSED required",
    },
    {
        "step": 2,
        "action": "Store raw paid data in local external path",
        "detail": (
            "Keep raw file in a local filesystem path not tracked by git; "
            "never run git add on the raw file; "
            "record path in local-only config that is also git-ignored"
        ),
        "where": "Local filesystem path outside repo (e.g. ~/odds-data/2025/raw/)",
        "gate": "Raw data path must not appear in any committed file",
    },
    {
        "step": 3,
        "action": "Generate manifest with checksum, row count, and schema version",
        "detail": (
            "Compute SHA-256 on raw file; fill all 23 P82A manifest fields; "
            "set contains_api_key=False; set raw_data_policy to one of the allowed values; "
            "pass manifest through _validate_manifest() before staging"
        ),
        "where": "data/mlb_2025/derived/intake_manifest_<season>.json",
        "gate": "_validate_manifest() from P82A script must return valid=True with zero errors",
    },
    {
        "step": 4,
        "action": "Run P81 validator locally against raw file",
        "detail": (
            "Execute P81 validator script against the raw file locally; "
            "do not commit the raw file; "
            "commit only the DERIVED_VALIDATION_SUMMARY output"
        ),
        "where": "Local execution; validation summary written to data/mlb_2025/derived/",
        "gate": "Validator must return LEGAL_ODDS_DATASET_VALIDATED_FOR_P82 before advancing",
    },
    {
        "step": 5,
        "action": "Commit only manifest, checksum record, and derived validation summary",
        "detail": (
            "Stage and commit: intake manifest JSON, checksum-only record, P81 validation summary; "
            "do not stage raw paid odds rows; "
            "staging guard must return STAGE_CLEAN"
        ),
        "where": "data/mlb_2025/derived/ — no raw data rows in diff",
        "gate": "Staging guard STAGE_CLEAN required; diff must contain zero raw paid odds values",
    },
    {
        "step": 6,
        "action": "Run P82 dry-run edge diagnostics only after P82A unlock criteria pass",
        "detail": (
            "Load validated dataset locally; compute paper-only edge diagnostics; "
            "commit only DERIVED_MARKET_EDGE_SUMMARY with aggregate statistics; "
            "no row-level paid odds in committed file"
        ),
        "where": "Local execution; aggregate summary to data/mlb_2025/derived/",
        "gate": "_run_unlock_decision(manifest) must return can_unlock_p82=True",
    },
    {
        "step": 7,
        "action": "Never commit API key values, raw paid odds rows, or proprietary row-level values",
        "detail": (
            "Permanent rule for all future phases. "
            "Even if license permits redistribution, row-level paid odds must receive "
            "explicit project governance authorization before any commit is attempted"
        ),
        "where": "Entire repo lifetime — no time limit, no exception path without authorization",
        "gate": "HARD_FORBIDDEN — no override without explicit governance authorization record",
    },
]

# ---------------------------------------------------------------------------
# Policy constants
# ---------------------------------------------------------------------------
ALLOWED_RAW_DATA_POLICIES: list[str] = [
    "LOCAL_ONLY_HASH_COMMITTED",
    "DERIVED_ONLY_COMMIT",
    "COMMIT_ALLOWED_LICENSE_VERIFIED",
    "MOCK_ONLY",
]

FORBIDDEN_RAW_DATA_POLICIES: list[str] = [
    "UNKNOWN",
    "COMMIT_RAW_PAID_DATA",
    "EMBED_SECRET",
    "UNLICENSED_SOURCE",
]

# ---------------------------------------------------------------------------
# Step functions
# ---------------------------------------------------------------------------

def step1_verify_p82a_state() -> dict:
    """Load and verify P82A summary matches required pre-conditions."""
    p82a_path = DERIVED / "p82a_real_legal_odds_intake_gate_summary.json"
    if not p82a_path.exists():
        return {"status": "FAIL", "error": "P82A summary missing — STOP"}

    d = json.loads(p82a_path.read_text())

    # Check manifest fields for raw_data_policy and contains_api_key
    manifest_fields = d.get("step2_intake_manifest", {}).get("manifest_fields", [])
    raw_data_policy_present = any(
        f.get("field") == "raw_data_policy" for f in manifest_fields
    )
    contains_api_key_must_be_false = any(
        f.get("field") == "contains_api_key" and f.get("required_value") is False
        for f in manifest_fields
    )

    gov = d.get("governance_snapshot", {})
    checks = {
        "classification_correct": (
            d.get("p82a_classification") == "P82A_REAL_LEGAL_ODDS_INTAKE_GATE_READY"
        ),
        "p82_unlock_status_blocked": (
            d.get("p82_unlock_status") == "BLOCKED_NO_REAL_DATASET"
        ),
        "p82_unlocked_false": gov.get("p82_unlocked") is False,
        "live_api_calls_zero": d.get("live_api_calls") == 0,
        "raw_data_policy_field_present": raw_data_policy_present,
        "contains_api_key_must_be_false": contains_api_key_must_be_false,
        "forbidden_scan_passed": (
            d.get("step7_forbidden_scan", {}).get("scan_passed") is True
        ),
        "production_ready_false": gov.get("production_ready") is False,
        "intake_gate_defined": (
            "INTAKE_GATE_DEFINED" in str(d.get("p82a_current_status", ""))
        ),
    }

    all_pass = all(checks.values())
    s3 = d.get("step3_blocker_checklist", {})
    s4 = d.get("step4_unlock_decision", {})
    allowed_policies = d.get("step2_intake_manifest", {}).get(
        "allowed_raw_data_policies", []
    )

    return {
        "status": "PASS" if all_pass else "FAIL",
        "p82a_classification": d.get("p82a_classification"),
        "p82_unlock_status": d.get("p82_unlock_status"),
        "p82_unlocked": gov.get("p82_unlocked"),
        "live_api_calls": d.get("live_api_calls"),
        "raw_data_policy_field_present": raw_data_policy_present,
        "contains_api_key_must_be_false": contains_api_key_must_be_false,
        "manifest_field_count": len(manifest_fields),
        "allowed_raw_data_policies_in_p82a": allowed_policies,
        "total_blockers": s3.get("total_blockers", 0),
        "only_real_legal_dataset_unlocks": s4.get("only_real_legal_dataset_unlocks"),
        "p82a_script_exists": (
            (REPO_ROOT / "scripts" / "_p82a_real_legal_odds_intake_gate.py").exists()
        ),
        "checks": checks,
    }


def step2_define_artifact_classes() -> dict:
    """Define the 9 artifact classes for raw/paid odds data governance."""
    classes_by_id = {c["class_id"]: c for c in ARTIFACT_CLASSES}
    can_commit_true = [c["class_id"] for c in ARTIFACT_CLASSES if c.get("can_commit") is True]
    can_commit_false = [c["class_id"] for c in ARTIFACT_CLASSES if c.get("can_commit") is False]
    can_commit_conditional = [
        c["class_id"] for c in ARTIFACT_CLASSES if c.get("can_commit") is None
    ]
    return {
        "class_count": len(ARTIFACT_CLASSES),
        "class_ids": ARTIFACT_CLASS_IDS,
        "classes": ARTIFACT_CLASSES,
        "classes_by_id": classes_by_id,
        "can_commit_true": can_commit_true,
        "can_commit_false": can_commit_false,
        "can_commit_conditional": can_commit_conditional,
        "hard_forbidden_classes": [
            c["class_id"] for c in ARTIFACT_CLASSES
            if c.get("default_policy") == "HARD_FORBIDDEN"
        ],
        "local_only_classes": [
            c["class_id"] for c in ARTIFACT_CLASSES
            if "LOCAL_ONLY" in c.get("default_policy", "")
            or "DO_NOT_COMMIT" in c.get("default_policy", "")
        ],
    }


def step3_define_commit_policy_matrix() -> dict:
    """Return the commit policy matrix; one entry per artifact class."""
    # Validate all 9 classes have required fields
    required_fields = ["can_commit", "can_stage", "storage_location", "stop_condition"]
    validation_errors = []
    for cls_id, policy in COMMIT_POLICY_MATRIX.items():
        for field in required_fields:
            if field not in policy:
                validation_errors.append(f"MISSING:{cls_id}.{field}")

    return {
        **COMMIT_POLICY_MATRIX,
        "_meta": {
            "class_count": len(COMMIT_POLICY_MATRIX),
            "validation_errors": validation_errors,
            "matrix_valid": len(validation_errors) == 0,
        },
    }


def step4_define_staging_guard() -> dict:
    """Return the staging guard contract with validation."""
    guard = dict(STAGING_GUARD_CONTRACT)
    # Validate guard structure
    rule_ids = [b["rule_id"] for b in guard["blocks"]]
    required_states = ["STAGE_CLEAN", "BLOCK_SECRET", "BLOCK_RAW_PAID_DATA"]
    missing_states = [s for s in required_states if s not in guard["guard_states"]]

    guard["_validation"] = {
        "rule_count": len(guard["blocks"]),
        "rule_ids": rule_ids,
        "guard_state_count": len(guard["guard_states"]),
        "missing_required_states": missing_states,
        "guard_valid": len(missing_states) == 0,
    }
    return guard


def step5_define_manifest_integration() -> dict:
    """Return the manifest integration policy for P82A manifest fields."""
    return {
        **MANIFEST_INTEGRATION_POLICY,
        "allowed_raw_data_policies": ALLOWED_RAW_DATA_POLICIES,
        "forbidden_raw_data_policies": FORBIDDEN_RAW_DATA_POLICIES,
        "policy_count": (
            len(ALLOWED_RAW_DATA_POLICIES) + len(FORBIDDEN_RAW_DATA_POLICIES)
        ),
        "validation_summary": {
            "raw_data_policy_allowed_count": len(ALLOWED_RAW_DATA_POLICIES),
            "raw_data_policy_forbidden_count": len(FORBIDDEN_RAW_DATA_POLICIES),
            "storage_policy_allowed_count": len(
                MANIFEST_INTEGRATION_POLICY["storage_policy"]["allowed_values"]
            ),
            "commit_policy_allowed_count": len(
                MANIFEST_INTEGRATION_POLICY["commit_policy"]["allowed_values"]
            ),
        },
    }


def step6_define_future_workflow() -> dict:
    """Return the 7-step future real data workflow."""
    # Validate workflow completeness
    step_numbers = [s["step"] for s in FUTURE_WORKFLOW]
    expected_steps = list(range(1, 8))
    missing_steps = [s for s in expected_steps if s not in step_numbers]

    p81_step = next((s for s in FUTURE_WORKFLOW if s["step"] == 4), None)
    raw_outside_git_step = next((s for s in FUTURE_WORKFLOW if s["step"] == 2), None)
    commit_only_derived_step = next((s for s in FUTURE_WORKFLOW if s["step"] == 5), None)

    return {
        "workflow_steps": FUTURE_WORKFLOW,
        "step_count": len(FUTURE_WORKFLOW),
        "step_numbers": step_numbers,
        "missing_steps": missing_steps,
        "workflow_complete": len(missing_steps) == 0,
        "p81_required_before_p82": (
            p81_step is not None
            and "validator" in p81_step.get("action", "").lower()
        ),
        "raw_stored_outside_git": (
            raw_outside_git_step is not None
            and "local" in raw_outside_git_step.get("where", "").lower()
        ),
        "commits_only_derived": (
            commit_only_derived_step is not None
            and (
                "manifest" in commit_only_derived_step.get("action", "").lower()
                or "checksum" in commit_only_derived_step.get("action", "").lower()
            )
        ),
        "p82_remains_blocked": True,
        "p82_block_reason": "BLOCKED_NO_REAL_DATASET — workflow steps 1-4 must complete before P82 unlock",
    }


def step7_verify_source_artifacts() -> dict:
    """Verify all required source artifacts (P72A → P82A) exist."""
    results: dict[str, bool] = {}
    for fname in SOURCE_ARTIFACTS:
        path = DERIVED / fname
        results[fname] = path.exists()
    all_present = all(results.values())
    missing = [k for k, v in results.items() if not v]
    return {
        "all_present": all_present,
        "artifact_count": len(SOURCE_ARTIFACTS),
        "artifacts": results,
        "missing": missing,
        "status": "PASS" if all_present else "FAIL",
    }


def step8_forbidden_scan() -> dict:
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

    # Locate self function body start/end (guard: only first occurrence)
    self_func_start = None
    self_func_end = len(lines)
    for i, line in enumerate(lines):
        if self_func_start is None and "def step8_forbidden_scan" in line:
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
    s1 = summary["step1_p82a_verification"]
    s2 = summary["step2_artifact_classes"]
    s3 = summary["step3_commit_policy_matrix"]
    s4 = summary["step4_staging_guard"]
    s5 = summary["step5_manifest_integration"]
    s6 = summary["step6_future_workflow"]
    s7 = summary["step7_source_artifacts"]
    s8 = summary["step8_forbidden_scan"]

    lines = [
        f"# P82B — Raw Paid Odds Data Storage / Commit Policy Contract",
        f"",
        f"**Snapshot**: {summary['snapshot_id']}  ",
        f"**Schema version**: {summary['schema_version']}  ",
        f"**Classification**: `{summary['p82b_classification']}`  ",
        f"**Generated**: {summary['generated_at_utc']}",
        f"",
        f"---",
        f"",
        f"## Step 1 — P82A State Verification",
        f"",
        f"| Check | Result |",
        f"|---|---|",
    ]
    for k, v in s1.get("checks", {}).items():
        lines.append(f"| {k} | {'✅ PASS' if v else '❌ FAIL'} |")
    lines += [
        f"",
        f"- **P82A classification**: `{s1.get('p82a_classification')}`",
        f"- **P82 unlock status**: `{s1.get('p82_unlock_status')}`",
        f"- **Manifest fields**: {s1.get('manifest_field_count')}",
        f"- **raw_data_policy field present**: {s1.get('raw_data_policy_field_present')}",
        f"- **contains_api_key must be False**: {s1.get('contains_api_key_must_be_false')}",
        f"- **Total blockers**: {s1.get('total_blockers')}",
        f"- **Only real legal dataset unlocks P82**: {s1.get('only_real_legal_dataset_unlocks')}",
        f"",
        f"---",
        f"",
        f"## Step 2 — Artifact Classes",
        f"",
        f"**{s2.get('class_count')} artifact classes defined**",
        f"",
        f"| Class ID | can_commit | Default Policy |",
        f"|---|---|---|",
    ]
    for c in ARTIFACT_CLASSES:
        can = c["can_commit"]
        can_str = "✅ Yes" if can is True else ("❌ No" if can is False else "⚠️ Conditional")
        lines.append(f"| `{c['class_id']}` | {can_str} | {c['default_policy']} |")
    lines += [
        f"",
        f"- **Hard-forbidden classes**: {', '.join(s2.get('hard_forbidden_classes', []))}",
        f"- **Local-only classes**: {', '.join(s2.get('local_only_classes', []))}",
        f"- **Conditional commit**: {', '.join(s2.get('can_commit_conditional', []))}",
        f"",
        f"---",
        f"",
        f"## Step 3 — Commit Policy Matrix",
        f"",
        f"| Class ID | can_commit | can_stage | storage_location |",
        f"|---|---|---|---|",
    ]
    meta = s3.get("_meta", {})
    for cls_id in ARTIFACT_CLASS_IDS:
        p = s3.get(cls_id, {})
        cc = p.get("can_commit")
        cs = p.get("can_stage")
        sl = p.get("storage_location", "")[:40]
        cc_str = "✅" if cc is True else ("❌" if cc is False else "⚠️")
        cs_str = "✅" if cs is True else ("❌" if cs is False else "⚠️")
        lines.append(f"| `{cls_id}` | {cc_str} | {cs_str} | {sl}... |")
    lines += [
        f"",
        f"- **Matrix valid**: {meta.get('matrix_valid')}",
        f"- **Validation errors**: {meta.get('validation_errors', [])}",
        f"",
        f"---",
        f"",
        f"## Step 4 — Staging Guard Contract",
        f"",
        f"**Guard ID**: `{s4.get('guard_id')}`",
        f"",
        f"| Rule ID | Guard State |",
        f"|---|---|",
    ]
    for block in s4.get("blocks", []):
        lines.append(f"| `{block['rule_id']}` | `{block['guard_state']}` |")
    lines += [
        f"",
        f"**Guard states**: {', '.join(s4.get('guard_states', []))}",
        f"",
        f"**Hard-blocked classes**: {', '.join(s4.get('hard_block_classes', []))}",
        f"",
        f"---",
        f"",
        f"## Step 5 — Manifest Integration Policy",
        f"",
        f"### raw_data_policy allowed values",
        f"",
    ]
    rdp = s5.get("raw_data_policy", {})
    for v in rdp.get("allowed_values", []):
        lines.append(f"- ✅ `{v}`")
    lines += [f"", f"### raw_data_policy forbidden values", f""]
    for v in rdp.get("forbidden_values", []):
        lines.append(f"- ❌ `{v}`")
    lines += [
        f"",
        f"- **Default**: `{rdp.get('default')}`",
        f"- **Checksum requirement**: {s5.get('checksum_requirement', '')}",
        f"- **License evidence requirement**: {s5.get('license_evidence_requirement', '')}",
        f"",
        f"---",
        f"",
        f"## Step 6 — Future Real Data Workflow",
        f"",
    ]
    for wf_step in s6.get("workflow_steps", []):
        lines += [
            f"### Step {wf_step['step']}: {wf_step['action']}",
            f"",
            f"- **Where**: {wf_step['where']}",
            f"- **Gate**: {wf_step['gate']}",
            f"",
        ]
    lines += [
        f"- **P82 remains blocked**: {s6.get('p82_remains_blocked')}",
        f"- **Block reason**: {s6.get('p82_block_reason')}",
        f"",
        f"---",
        f"",
        f"## Step 7 — Source Artifacts",
        f"",
        f"- **Total**: {s7.get('artifact_count')} | **All present**: {s7.get('all_present')}",
        f"- **Missing**: {s7.get('missing', [])}",
        f"",
        f"---",
        f"",
        f"## Step 8 — Forbidden Scan",
        f"",
        f"- **Scan passed**: {s8.get('scan_passed')}",
        f"- **Violations**: {s8.get('violations_count')}",
        f"- **Patterns checked**: {s8.get('patterns_checked')}",
        f"- **Lines scanned**: {s8.get('lines_scanned')}",
        f"",
        f"---",
        f"",
        f"## Governance Invariants",
        f"",
        f"| Key | Value |",
        f"|---|---|",
    ]
    gov = summary.get("governance_snapshot", {})
    for k, v in gov.items():
        lines.append(f"| `{k}` | `{v}` |")
    lines += [
        f"",
        f"---",
        f"",
        f"## Current P82 Status",
        f"",
        f"- **P82 unlock status**: `{summary.get('p82_unlock_status')}`",
        f"- **P82B current status**: {summary.get('p82b_current_status')}",
        f"- **live_api_calls**: {summary.get('live_api_calls')}",
        f"- **ev_clv_kelly_computed**: {summary.get('ev_clv_kelly_computed')}",
        f"",
        f"---",
        f"*Generated by P82B — paper_only=True | diagnostic_only=True | no_real_bet_enforced*",
    ]
    path.write_text("\n".join(lines))


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def main() -> dict:
    step1 = step1_verify_p82a_state()
    step2 = step2_define_artifact_classes()
    step3 = step3_define_commit_policy_matrix()
    step4 = step4_define_staging_guard()
    step5 = step5_define_manifest_integration()
    step6 = step6_define_future_workflow()
    step7 = step7_verify_source_artifacts()
    step8 = step8_forbidden_scan()

    all_pass = (
        step1.get("status") == "PASS"
        and step7.get("status") == "PASS"
        and step8.get("scan_passed") is True
        and step2.get("class_count") == 9
        and step3.get("_meta", {}).get("matrix_valid") is True
        and step4.get("_validation", {}).get("guard_valid") is True
        and step5.get("raw_data_policy") is not None
        and step6.get("workflow_complete") is True
    )

    classification = (
        "P82B_RAW_PAID_DATA_POLICY_READY"
        if all_pass
        else "P82B_FAILED_VALIDATION"
    )

    summary: dict = {
        "p82b_classification": classification,
        "schema_version": SCHEMA_VERSION,
        "snapshot_id": SNAPSHOT_ID,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "governance_snapshot": GOVERNANCE,
        "step1_p82a_verification": step1,
        "step2_artifact_classes": step2,
        "step3_commit_policy_matrix": step3,
        "step4_staging_guard": step4,
        "step5_manifest_integration": step5,
        "step6_future_workflow": step6,
        "step7_source_artifacts": step7,
        "step8_forbidden_scan": step8,
        "live_api_calls": 0,
        "ev_clv_kelly_computed": False,
        "p82_unlock_status": "BLOCKED_NO_REAL_DATASET",
        "p82b_current_status": (
            "RAW_PAID_DATA_POLICY_DEFINED — awaiting real legal odds dataset"
        ),
    }

    # Write JSON summary
    out_path = DERIVED / "p82b_raw_paid_odds_data_policy_contract_summary.json"
    out_path.write_text(json.dumps(summary, indent=2, default=str))

    # Write report
    report_path = (
        REPO_ROOT / "report" / "p82b_raw_paid_odds_data_policy_contract_20260526.md"
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    _write_report(summary, report_path)

    # Write betting-plan copy
    bet_path = (
        REPO_ROOT
        / "00-BettingPlan"
        / "20260526"
        / "p82b_raw_paid_odds_data_policy_contract_20260526.md"
    )
    bet_path.parent.mkdir(parents=True, exist_ok=True)
    _write_report(summary, bet_path)

    print(f"Classification : {classification}")
    print(f"Artifact classes : {step2.get('class_count')}")
    print(f"Scan passed    : {step8.get('scan_passed')}")
    print(f"Violations     : {step8.get('violations_count')}")
    print(f"Written        : {out_path}")
    return summary


if __name__ == "__main__":
    main()
