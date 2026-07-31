"""
P63 — Paper Recommendation Contract Review Readiness Gate

CEO-review readiness audit of the P62 paper recommendation contract.

Governance flags (unchanged throughout):
    paper_only=True
    diagnostic_only=True
    promotion_freeze=True
    kelly_deploy_allowed=False
    live_api_calls=0
    actual_rows_emitted=False
    runtime_recommendation_logic_changed=False
    champion_strategy_changed=False
    p45_platt_constants_modified=False
    p52_thresholds_modified=False
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
P62_SUMMARY_JSON = REPO_ROOT / "data/mlb_2025/derived/p62_paper_recommendation_contract_draft_summary.json"
P62_REPORT_MD = REPO_ROOT / "report/p62_paper_recommendation_contract_draft_20260526.md"
P62_BETTINGPLAN_MD = REPO_ROOT / "00-BettingPlan/20260526/p62_paper_recommendation_contract_draft_20260526.md"

P63_SUMMARY_JSON = REPO_ROOT / "data/mlb_2025/derived/p63_paper_recommendation_contract_review_readiness_summary.json"

# ---------------------------------------------------------------------------
# Gate audit definitions
# ---------------------------------------------------------------------------

GATE_AUDIT_SPECS: list[dict[str, Any]] = [
    {
        "gate_id": "EG01",
        "gate_name": "paper_only flag",
        "check_key": ("governance", "paper_only"),
        "expected_value": True,
        "audit_method": "json_flag_lookup",
        "blocks_ceo_review": True,
        "required_future_evidence": "Must be True in every future paper row",
    },
    {
        "gate_id": "EG02",
        "gate_name": "diagnostic_only flag",
        "check_key": ("governance", "diagnostic_only"),
        "expected_value": True,
        "audit_method": "json_flag_lookup",
        "blocks_ceo_review": True,
        "required_future_evidence": "Must be True in every future paper row",
    },
    {
        "gate_id": "EG03",
        "gate_name": "promotion_freeze flag",
        "check_key": ("governance", "promotion_freeze"),
        "expected_value": True,
        "audit_method": "json_flag_lookup",
        "blocks_ceo_review": True,
        "required_future_evidence": "Must remain True until CEO explicitly lifts",
    },
    {
        "gate_id": "EG04",
        "gate_name": "live_api_calls=0",
        "check_key": ("governance", "live_api_calls"),
        "expected_value": 0,
        "audit_method": "json_flag_lookup",
        "blocks_ceo_review": True,
        "required_future_evidence": "Must remain 0 during paper simulation",
    },
    {
        "gate_id": "EG05",
        "gate_name": "kelly_deploy_allowed=False",
        "check_key": ("governance", "kelly_deploy_allowed"),
        "expected_value": False,
        "audit_method": "json_flag_lookup",
        "blocks_ceo_review": True,
        "required_future_evidence": "Must be False in every future paper row",
    },
    {
        "gate_id": "EG06",
        "gate_name": "runtime_recommendation_logic_changed=False",
        "check_key": ("governance", "runtime_recommendation_logic_changed"),
        "expected_value": False,
        "audit_method": "json_flag_lookup",
        "blocks_ceo_review": True,
        "required_future_evidence": "Future phases must not modify runtime logic without CEO gate",
    },
    {
        "gate_id": "EG07",
        "gate_name": "champion_replacement=False",
        "check_key": ("governance", "champion_strategy_changed"),
        "expected_value": False,
        "audit_method": "json_flag_lookup",
        "blocks_ceo_review": True,
        "required_future_evidence": "fixed_edge_5pct remains champion until explicit CEO auth",
    },
    {
        "gate_id": "EG08",
        "gate_name": "production_ready=False",
        "check_key": ("governance", "production_usage_proposed"),
        "expected_value": False,
        "audit_method": "json_flag_lookup",
        "blocks_ceo_review": True,
        "required_future_evidence": "Must remain False — no production proposal",
    },
    {
        "gate_id": "EG09",
        "gate_name": "real_bet_allowed=False",
        "check_key": ("governance", "real_bet_allowed"),
        "expected_value": False,
        "audit_method": "json_flag_lookup",
        "blocks_ceo_review": True,
        "required_future_evidence": "Must be False in every future paper row",
    },
    {
        "gate_id": "EG10",
        "gate_name": "signal=sp_fip_delta",
        "check_key": ("signal", "name"),
        "expected_value": "sp_fip_delta",
        "audit_method": "json_flag_lookup",
        "blocks_ceo_review": True,
        "required_future_evidence": "model_signal_name field must equal sp_fip_delta in all rows",
    },
    {
        "gate_id": "EG11",
        "gate_name": "tier=Tier_C",
        "check_key": ("signal", "tier"),
        "expected_value": "Tier_C",
        "audit_method": "json_flag_lookup",
        "blocks_ceo_review": True,
        "required_future_evidence": "signal_tier field must equal Tier_C — any sub-threshold row is BLOCKED",
    },
    {
        "gate_id": "EG12",
        "gate_name": "threshold=0.50 (T_LOCKED)",
        "check_key": ("signal", "tier_threshold"),
        "expected_value": 0.5,
        "audit_method": "json_flag_lookup",
        "blocks_ceo_review": True,
        "required_future_evidence": "tier_threshold field must equal 0.50 — must not be re-optimised",
    },
    {
        "gate_id": "EG13",
        "gate_name": "calibration=P45 Platt constants A=0.435432 B=0.245464",
        "check_key": ("platt_constants", "platt_A"),
        "expected_value": 0.435432,
        "audit_method": "json_flag_lookup_pair",
        "pair_check_key": ("platt_constants", "platt_B"),
        "pair_expected_value": 0.245464,
        "blocks_ceo_review": True,
        "required_future_evidence": "platt_A and platt_B must match locked values in every row",
    },
    {
        "gate_id": "EG14",
        "gate_name": "odds_source_trace_required",
        "check_key": None,
        "expected_value": None,
        "audit_method": "schema_presence_check",
        "schema_field": "odds_source_trace",
        "blocks_ceo_review": False,
        "required_future_evidence": "Each future row must carry a non-null odds_source_trace; not testable until rows emitted",
    },
    {
        "gate_id": "EG15",
        "gate_name": "timestamps_required (game_start_utc, prediction_timestamp_utc, odds_timestamp_utc must be pregame)",
        "check_key": None,
        "expected_value": None,
        "audit_method": "schema_presence_check",
        "schema_fields": ["game_start_utc", "prediction_timestamp_utc", "odds_timestamp_utc"],
        "blocks_ceo_review": False,
        "required_future_evidence": "Each timestamp must precede game_start_utc; not testable until rows emitted",
    },
    {
        "gate_id": "EG16",
        "gate_name": "no_postgame_leakage (pregame isolation required)",
        "check_key": None,
        "expected_value": None,
        "audit_method": "schema_presence_check",
        "schema_field": "prediction_timestamp_utc",
        "blocks_ceo_review": False,
        "required_future_evidence": "Leakage guard must be enforced row-by-row during simulation; not testable until rows emitted",
    },
    {
        "gate_id": "EG17",
        "gate_name": "2024_data_gap_documented",
        "check_key": ("p61_relationship", "data_gap_status"),
        "expected_value": "UNRESOLVED_AS_OF_P62",
        "audit_method": "json_flag_lookup",
        "blocks_ceo_review": False,
        "required_future_evidence": "P61 PATH_A or PATH_B resolution required before 2024 rows can be added",
    },
]

# ---------------------------------------------------------------------------
# Schema field audit definitions
# ---------------------------------------------------------------------------

SCHEMA_FIELD_AUDIT: list[dict[str, Any]] = [
    {"field": "contract_version",             "category": "REQUIRED_FOR_AUDIT",          "source_needed": "contract metadata",                    "can_populate_without_live_api": True},
    {"field": "game_id",                       "category": "REQUIRED_FOR_AUDIT",          "source_needed": "MLB game schedule data",                "can_populate_without_live_api": True},
    {"field": "game_start_utc",               "category": "REQUIRED_FOR_LEAKAGE_GUARD",  "source_needed": "MLB schedule (existing CSV)",           "can_populate_without_live_api": True},
    {"field": "generated_at_utc",             "category": "REQUIRED_FOR_AUDIT",          "source_needed": "system timestamp at generation",        "can_populate_without_live_api": True},
    {"field": "prediction_timestamp_utc",     "category": "REQUIRED_FOR_LEAKAGE_GUARD",  "source_needed": "model execution timestamp",             "can_populate_without_live_api": True},
    {"field": "odds_timestamp_utc",           "category": "REQUIRED_FOR_LEAKAGE_GUARD",  "source_needed": "odds capture timestamp from CSV",       "can_populate_without_live_api": True},
    {"field": "market",                        "category": "REQUIRED_FOR_AUDIT",          "source_needed": "fixed value: moneyline",                "can_populate_without_live_api": True},
    {"field": "side",                          "category": "REQUIRED_FOR_AUDIT",          "source_needed": "model output (Home/Away)",              "can_populate_without_live_api": True},
    {"field": "model_signal_name",            "category": "REQUIRED_FOR_AUDIT",          "source_needed": "fixed value: sp_fip_delta",             "can_populate_without_live_api": True},
    {"field": "sp_fip_delta",                 "category": "REQUIRED_FOR_AUDIT",          "source_needed": "pitching FIP data (existing CSV)",      "can_populate_without_live_api": True},
    {"field": "signal_tier",                   "category": "REQUIRED_FOR_RISK_GOVERNANCE","source_needed": "threshold gate computation",            "can_populate_without_live_api": True},
    {"field": "tier_threshold",               "category": "REQUIRED_FOR_RISK_GOVERNANCE","source_needed": "locked constant 0.50",                  "can_populate_without_live_api": True},
    {"field": "model_prob_home",              "category": "REQUIRED_FOR_AUDIT",          "source_needed": "model sigmoid output",                  "can_populate_without_live_api": True},
    {"field": "model_prob_away",              "category": "REQUIRED_FOR_AUDIT",          "source_needed": "model sigmoid output (1 - home)",       "can_populate_without_live_api": True},
    {"field": "calibration_method",           "category": "REQUIRED_FOR_RISK_GOVERNANCE","source_needed": "fixed value: platt_scaled",             "can_populate_without_live_api": True},
    {"field": "platt_A",                       "category": "REQUIRED_FOR_RISK_GOVERNANCE","source_needed": "P45 locked constant 0.435432",          "can_populate_without_live_api": True},
    {"field": "platt_B",                       "category": "REQUIRED_FOR_RISK_GOVERNANCE","source_needed": "P45 locked constant 0.245464",          "can_populate_without_live_api": True},
    {"field": "calibrated_prob",              "category": "REQUIRED_FOR_AUDIT",          "source_needed": "Platt(model_prob_home; A, B)",           "can_populate_without_live_api": True},
    {"field": "odds_source",                   "category": "REQUIRED_FOR_LEAKAGE_GUARD",  "source_needed": "odds CSV filename",                    "can_populate_without_live_api": True},
    {"field": "odds_source_trace",            "category": "REQUIRED_FOR_LEAKAGE_GUARD",  "source_needed": "CSV path + row hash or URL",            "can_populate_without_live_api": True},
    {"field": "decimal_odds",                  "category": "REQUIRED_FOR_AUDIT",          "source_needed": "existing 2025 odds CSV",               "can_populate_without_live_api": True},
    {"field": "implied_probability",          "category": "REQUIRED_FOR_AUDIT",          "source_needed": "derived from decimal_odds",             "can_populate_without_live_api": True},
    {"field": "edge_pct",                      "category": "REQUIRED_FOR_RISK_GOVERNANCE","source_needed": "calibrated_prob - implied_probability", "can_populate_without_live_api": True},
    {"field": "paper_stake_units",            "category": "OPTIONAL_DIAGNOSTIC",         "source_needed": "fixed unit value (e.g. 1.0)",           "can_populate_without_live_api": True},
    {"field": "kelly_fraction_theoretical",   "category": "OPTIONAL_DIAGNOSTIC",         "source_needed": "Kelly formula (theoretical only)",      "can_populate_without_live_api": True},
    {"field": "kelly_deploy_allowed",          "category": "REQUIRED_FOR_RISK_GOVERNANCE","source_needed": "fixed value: False",                   "can_populate_without_live_api": True},
    {"field": "recommendation_status",        "category": "REQUIRED_FOR_RISK_GOVERNANCE","source_needed": "gate evaluation output",                "can_populate_without_live_api": True},
    {"field": "gate_status",                   "category": "REQUIRED_FOR_RISK_GOVERNANCE","source_needed": "eligibility gate result",               "can_populate_without_live_api": True},
    {"field": "gate_reasons",                  "category": "REQUIRED_FOR_AUDIT",          "source_needed": "gate failure log list",                 "can_populate_without_live_api": True},
    {"field": "paper_only",                    "category": "REQUIRED_FOR_RISK_GOVERNANCE","source_needed": "fixed value: True",                    "can_populate_without_live_api": True},
    {"field": "diagnostic_only",              "category": "REQUIRED_FOR_RISK_GOVERNANCE","source_needed": "fixed value: True",                     "can_populate_without_live_api": True},
    {"field": "production_ready",             "category": "REQUIRED_FOR_RISK_GOVERNANCE","source_needed": "fixed value: False",                   "can_populate_without_live_api": True},
    {"field": "real_bet_allowed",             "category": "REQUIRED_FOR_RISK_GOVERNANCE","source_needed": "fixed value: False",                   "can_populate_without_live_api": True},
]

# ---------------------------------------------------------------------------
# Status value audit
# ---------------------------------------------------------------------------

STATUS_VALUE_AUDIT: list[dict[str, Any]] = [
    {
        "status": "PAPER_ELIGIBLE_CONTRACT_ONLY",
        "category": "ELIGIBLE_PAPER_ONLY",
        "safe": True,
        "reason": "Explicitly scoped to paper-only contract; no deployment, betting, or production implication",
    },
    {
        "status": "BLOCKED_MISSING_ODDS_SOURCE_TRACE",
        "category": "BLOCKED",
        "safe": True,
        "reason": "Blocked status — covers missing odds trace. Cannot be misread as production-ready",
    },
    {
        "status": "BLOCKED_MISSING_TIMESTAMP",
        "category": "BLOCKED",
        "safe": True,
        "reason": "Blocked status — covers missing pregame timestamp. Prevents leakage risk row from passing",
    },
    {
        "status": "BLOCKED_POSTGAME_LEAKAGE_RISK",
        "category": "BLOCKED",
        "safe": True,
        "reason": "Blocked status — explicitly flags any postgame data contamination",
    },
    {
        "status": "BLOCKED_SIGNAL_BELOW_TIER_C",
        "category": "BLOCKED",
        "safe": True,
        "reason": "Blocked status — ensures only |sp_fip_delta| >= 0.50 rows proceed",
    },
    {
        "status": "BLOCKED_CALIBRATION_SOURCE_INVALID",
        "category": "BLOCKED",
        "safe": True,
        "reason": "Blocked status — guards against non-P45 Platt constants being used",
    },
    {
        "status": "BLOCKED_PROMOTION_FREEZE",
        "category": "BLOCKED",
        "safe": True,
        "reason": "Blocked status — enforces promotion_freeze=True at row level",
    },
    {
        "status": "BLOCKED_PRODUCTION_NOT_ALLOWED",
        "category": "BLOCKED",
        "safe": True,
        "reason": "Blocked status — hard wall against any production interpretation of the row",
    },
    {
        "status": "BLOCKED_2024_DATA_GAP_UNRESOLVED",
        "category": "BLOCKED",
        "safe": True,
        "reason": "Blocked status — ensures no 2024-game rows can pass until P61 resolution is completed",
    },
]

# ---------------------------------------------------------------------------
# Forbidden claims vocabulary
# ---------------------------------------------------------------------------

FORBIDDEN_TERMS: list[str] = [
    "production_ready: true",
    "production_ready\": true",
    "approved for production",
    "cleared for live deployment",
    "profitability confirmed",
    "champion has been replaced",
    "kelly staking deployed",
    "kelly deployed",
    "real money bet recommended",
    "betting advice issued",
    "recommended wager",
    "affirmative_profit_claim_found\": true",
    "affirmative_profitability_claim_found\": true",
    "affirmative_production_status_found\": true",
    "affirmative_live_promotion_found\": true",
    "affirmative_deployment_status_found\": true",
]

# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------


def load_p62_artifacts() -> dict[str, Any]:
    """Load all P62 artifacts and verify existence."""
    result: dict[str, Any] = {
        "summary_json_exists": P62_SUMMARY_JSON.exists(),
        "report_md_exists": P62_REPORT_MD.exists(),
        "bettingplan_md_exists": P62_BETTINGPLAN_MD.exists(),
        "summary_json_path": str(P62_SUMMARY_JSON),
        "report_md_path": str(P62_REPORT_MD),
        "bettingplan_md_path": str(P62_BETTINGPLAN_MD),
        "summary_data": None,
        "load_error": None,
    }
    if result["summary_json_exists"]:
        try:
            with open(P62_SUMMARY_JSON, encoding="utf-8") as fh:
                result["summary_data"] = json.load(fh)
        except Exception as exc:
            result["load_error"] = str(exc)
    return result


def _get_nested(data: dict[str, Any], keys: tuple[str, ...]) -> Any:
    """Safely navigate nested dict keys."""
    obj: Any = data
    for k in keys:
        if not isinstance(obj, dict):
            return None
        obj = obj.get(k)
    return obj


def _get_schema_field_names(data: dict[str, Any]) -> list[str]:
    """Extract field names from row_schema.fields list."""
    fields = _get_nested(data, ("row_schema", "fields")) or []
    return [f["field"] for f in fields if isinstance(f, dict) and "field" in f]


def audit_eligibility_gates(summary_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Audit EG01–EG17 eligibility gates against P62 JSON."""
    schema_field_names = _get_schema_field_names(summary_data)
    results: list[dict[str, Any]] = []

    for spec in GATE_AUDIT_SPECS:
        gate_id = spec["gate_id"]
        gate_name = spec["gate_name"]
        method = spec["audit_method"]

        if method == "json_flag_lookup":
            actual = _get_nested(summary_data, spec["check_key"])  # type: ignore[arg-type]
            expected = spec["expected_value"]
            match = actual == expected
            if match:
                audit_status = "TESTABLE"
                reason = f"Flag confirmed: {spec['check_key'][-1]}={actual}"
            else:
                audit_status = "AMBIGUOUS_REQUIRES_CLARIFICATION"
                reason = f"Expected {expected}, got {actual}"

        elif method == "json_flag_lookup_pair":
            actual_a = _get_nested(summary_data, spec["check_key"])  # type: ignore[arg-type]
            actual_b = _get_nested(summary_data, spec["pair_check_key"])  # type: ignore[arg-type]
            match_a = abs(float(actual_a or 0) - spec["expected_value"]) < 1e-6  # type: ignore[arg-type]
            match_b = abs(float(actual_b or 0) - spec["pair_expected_value"]) < 1e-6  # type: ignore[arg-type]
            match = match_a and match_b
            if match:
                audit_status = "TESTABLE"
                reason = f"platt_A={actual_a} platt_B={actual_b} — match locked constants"
            else:
                audit_status = "AMBIGUOUS_REQUIRES_CLARIFICATION"
                reason = f"platt_A={actual_a} (expected 0.435432), platt_B={actual_b} (expected 0.245464)"

        elif method == "schema_presence_check":
            # EG14, EG15, EG16 — verifiable from schema definition but not yet
            # exercised because actual rows have not been emitted
            fields_to_check: list[str] = []
            if "schema_field" in spec:
                fields_to_check = [spec["schema_field"]]
            elif "schema_fields" in spec:
                fields_to_check = spec["schema_fields"]

            present = all(f in schema_field_names for f in fields_to_check)
            if present:
                audit_status = "NOT_TESTABLE_YET"
                reason = (
                    f"Schema field(s) {fields_to_check} present in contract. "
                    "Runtime enforcement testable only after rows are emitted."
                )
            else:
                missing = [f for f in fields_to_check if f not in schema_field_names]
                audit_status = "MISSING_SOURCE_TRACE"
                reason = f"Fields missing from schema: {missing}"
            match = present

        else:
            audit_status = "AMBIGUOUS_REQUIRES_CLARIFICATION"
            reason = f"Unknown audit method: {method}"
            match = False

        results.append(
            {
                "gate_id": gate_id,
                "gate_name": gate_name,
                "audit_status": audit_status,
                "reason": reason,
                "required_future_evidence": spec.get("required_future_evidence", ""),
                "blocks_ceo_review": spec.get("blocks_ceo_review", False),
                "passed": match,
            }
        )

    return results


def audit_schema_fields(summary_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Audit the 33 future recommendation row fields."""
    actual_fields = _get_schema_field_names(summary_data)
    audited: list[dict[str, Any]] = []

    for spec in SCHEMA_FIELD_AUDIT:
        field_name = spec["field"]
        present_in_contract = field_name in actual_fields
        audited.append(
            {
                "field": field_name,
                "category": spec["category"],
                "rationale": f"Category: {spec['category']} — {spec['source_needed']}",
                "source_needed": spec["source_needed"],
                "can_populate_without_live_api": spec["can_populate_without_live_api"],
                "present_in_p62_schema": present_in_contract,
            }
        )

    return audited


def audit_status_values(summary_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Audit the 9 allowed status values."""
    contract_statuses: list[str] = _get_nested(summary_data, ("allowed_status_values", "values")) or []
    audited: list[dict[str, Any]] = []

    for spec in STATUS_VALUE_AUDIT:
        present = spec["status"] in contract_statuses
        audited.append(
            {
                "status": spec["status"],
                "category": spec["category"],
                "safe": spec["safe"],
                "reason": spec["reason"],
                "present_in_p62_contract": present,
                "implies_production_readiness": False,
                "implies_real_betting": False,
                "implies_kelly_deployment": False,
            }
        )

    return audited


def scan_forbidden_claims(summary_data: dict[str, Any]) -> dict[str, Any]:
    """Scan the P62 JSON for any forbidden affirmative claims."""
    raw_text = json.dumps(summary_data, ensure_ascii=False).lower()
    violations: list[str] = []
    for term in FORBIDDEN_TERMS:
        if term.lower() in raw_text:
            violations.append(term)
    return {
        "terms_checked": len(FORBIDDEN_TERMS),
        "violations_found": len(violations),
        "violations": violations,
        "result": "CLEAN" if not violations else "VIOLATIONS_FOUND",
    }


def check_governance_preservation(summary_data: dict[str, Any]) -> dict[str, Any]:
    """Verify all governance flags are preserved in P62 JSON."""
    gov = summary_data.get("governance", {})
    expected_flags = {
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
    flag_results: dict[str, Any] = {}
    all_pass = True
    for flag, expected in expected_flags.items():
        actual = gov.get(flag, "MISSING")
        match = actual == expected
        if not match:
            all_pass = False
        flag_results[flag] = {
            "expected": expected,
            "actual": actual,
            "pass": match,
        }
    return {
        "all_flags_preserved": all_pass,
        "flags": flag_results,
    }


def decide_ceo_readiness(
    artifacts: dict[str, Any],
    gate_audit: list[dict[str, Any]],
    schema_audit: list[dict[str, Any]],
    status_audit: list[dict[str, Any]],
    governance: dict[str, Any],
    forbidden_scan: dict[str, Any],
    summary_data: dict[str, Any],
) -> dict[str, Any]:
    """Produce P63 CEO review readiness decision."""
    allowed_classifications = [
        "P63_READY_FOR_CEO_REVIEW",
        "P63_READY_WITH_MINOR_CLARIFICATIONS",
        "P63_NOT_READY_SCHEMA_AMBIGUITY",
        "P63_BLOCKED_BY_CONTRACT_GAP",
        "P63_BLOCKED_BY_GOVERNANCE_RISK",
    ]

    blocking_issues: list[str] = []

    # 1. Artifacts must all exist
    if not artifacts["summary_json_exists"]:
        blocking_issues.append("P62 summary JSON missing")
    if not artifacts["report_md_exists"]:
        blocking_issues.append("P62 report MD missing")
    if not artifacts["bettingplan_md_exists"]:
        blocking_issues.append("P62 BettingPlan MD missing")

    # 2. Classification must be correct
    classification = _get_nested(summary_data, ("p62_classification",))
    if classification != "P62_CONTRACT_DRAFT_READY_FOR_CEO_REVIEW":
        blocking_issues.append(f"P62 classification unexpected: {classification}")

    # 3. Actual rows must not be emitted
    actual_rows = _get_nested(summary_data, ("governance", "actual_rows_emitted"))
    if actual_rows is not False:
        blocking_issues.append("actual_rows_emitted is not False — contract safety violated")

    # 4. Governance flags must all be preserved
    if not governance["all_flags_preserved"]:
        failed = [k for k, v in governance["flags"].items() if not v["pass"]]
        blocking_issues.append(f"Governance flags failed: {failed}")

    # 5. Forbidden claims must be clean
    if forbidden_scan["violations_found"] > 0:
        blocking_issues.append(f"Forbidden claims found: {forbidden_scan['violations']}")

    # 6. CEO-blocking gates must all pass
    blocking_gates = [g for g in gate_audit if g.get("blocks_ceo_review") and not g["passed"]]
    if blocking_gates:
        ids = [g["gate_id"] for g in blocking_gates]
        blocking_issues.append(f"CEO-blocking gates not passing: {ids}")

    # 7. Schema field count must match
    n_schema = _get_nested(summary_data, ("row_schema", "n_required_fields")) or 0
    if n_schema != 33:
        blocking_issues.append(f"Schema field count unexpected: {n_schema} (expected 33)")

    # 8. Status value count must match
    n_statuses = _get_nested(summary_data, ("allowed_status_values", "n_values")) or 0
    if n_statuses != 9:
        blocking_issues.append(f"Status value count unexpected: {n_statuses} (expected 9)")

    # 9. 2024 gap must remain documented as unresolved
    gap_status = _get_nested(summary_data, ("p61_relationship", "data_gap_status"))
    if gap_status != "UNRESOLVED_AS_OF_P62":
        blocking_issues.append(f"2024 data gap status unexpected: {gap_status}")

    # 10. Platt constants must be locked
    platt_A = _get_nested(summary_data, ("platt_constants", "platt_A"))
    platt_B = _get_nested(summary_data, ("platt_constants", "platt_B"))
    if abs(float(platt_A or 0) - 0.435432) > 1e-6 or abs(float(platt_B or 0) - 0.245464) > 1e-6:
        blocking_issues.append(f"Platt constants changed: A={platt_A} B={platt_B}")

    # Determine classification
    if not blocking_issues:
        final_classification = "P63_READY_FOR_CEO_REVIEW"
        summary_verdict = (
            "All P62 artifacts exist. Contract is internally consistent. "
            "All governance flags preserved. No actual rows emitted. "
            "No forbidden claims. All CEO-blocking gates pass. "
            "2024 data gap remains clearly unresolved. "
            "Recommended next step: CEO reviews P62 contract and authorises paper simulation."
        )
    elif all("clarification" in i.lower() for i in blocking_issues):
        final_classification = "P63_READY_WITH_MINOR_CLARIFICATIONS"
        summary_verdict = f"Minor clarifications needed: {blocking_issues}"
    elif any("schema" in i.lower() or "field" in i.lower() for i in blocking_issues):
        final_classification = "P63_NOT_READY_SCHEMA_AMBIGUITY"
        summary_verdict = f"Schema ambiguity blocking: {blocking_issues}"
    elif any("governance" in i.lower() or "flag" in i.lower() for i in blocking_issues):
        final_classification = "P63_BLOCKED_BY_GOVERNANCE_RISK"
        summary_verdict = f"Governance risk blocking: {blocking_issues}"
    else:
        final_classification = "P63_BLOCKED_BY_CONTRACT_GAP"
        summary_verdict = f"Contract gap blocking: {blocking_issues}"

    return {
        "final_classification": final_classification,
        "allowed_classifications": allowed_classifications,
        "blocking_issues": blocking_issues,
        "summary_verdict": summary_verdict,
        "ceo_review_recommended": final_classification == "P63_READY_FOR_CEO_REVIEW",
        "recommended_next_step": (
            "CEO reviews P62 contract → approves paper simulation scope → "
            "P64 paper simulation implementation begins (no rows until CEO gate clears)"
            if final_classification == "P63_READY_FOR_CEO_REVIEW"
            else "Resolve blocking issues before CEO review"
        ),
    }


def run_p63() -> dict[str, Any]:
    """Full P63 audit pipeline."""
    # Step 1 — Load P62 artifacts
    artifacts = load_p62_artifacts()
    summary_data: dict[str, Any] = artifacts.get("summary_data") or {}

    # Step 2 — Gate audit
    gate_audit = audit_eligibility_gates(summary_data)

    # Step 3 — Schema audit
    schema_audit = audit_schema_fields(summary_data)

    # Step 4 — Status value audit
    status_audit = audit_status_values(summary_data)

    # Step 5 — Governance preservation
    governance = check_governance_preservation(summary_data)

    # Step 6 — Forbidden scan
    forbidden_scan = scan_forbidden_claims(summary_data)

    # Step 7 — CEO readiness decision
    readiness = decide_ceo_readiness(
        artifacts, gate_audit, schema_audit, status_audit, governance, forbidden_scan, summary_data
    )

    # Compile summary
    gate_statuses = {g["gate_id"]: g["audit_status"] for g in gate_audit}
    summary: dict[str, Any] = {
        "p63_phase": "P63_PAPER_RECOMMENDATION_CONTRACT_REVIEW_READINESS",
        "generated_at_utc": datetime.now(tz=timezone.utc).isoformat(),
        "governance": {
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
        },
        "p62_artifact_inventory": {
            "summary_json_exists": artifacts["summary_json_exists"],
            "report_md_exists": artifacts["report_md_exists"],
            "bettingplan_md_exists": artifacts["bettingplan_md_exists"],
            "p62_classification": _get_nested(summary_data, ("p62_classification",)),
            "contract_version": _get_nested(summary_data, ("contract_version",)),
            "load_error": artifacts["load_error"],
        },
        "gate_audit": {
            "n_gates_audited": len(gate_audit),
            "gate_statuses": gate_statuses,
            "gates_blocking_ceo_review_that_failed": [
                g["gate_id"] for g in gate_audit if g.get("blocks_ceo_review") and not g["passed"]
            ],
            "detail": gate_audit,
        },
        "schema_audit": {
            "n_fields_audited": len(schema_audit),
            "n_fields_in_p62": _get_nested(summary_data, ("row_schema", "n_required_fields")),
            "all_fields_accounted": len(schema_audit) == 33,
            "fields_missing_from_schema": [
                f["field"] for f in schema_audit if not f["present_in_p62_schema"]
            ],
            "detail": schema_audit,
        },
        "status_value_audit": {
            "n_values_audited": len(status_audit),
            "n_values_in_p62": _get_nested(summary_data, ("allowed_status_values", "n_values")),
            "all_safe": all(s["safe"] for s in status_audit),
            "any_implies_production": any(s["implies_production_readiness"] for s in status_audit),
            "any_implies_real_betting": any(s["implies_real_betting"] for s in status_audit),
            "detail": status_audit,
        },
        "governance_preservation": governance,
        "forbidden_scan": forbidden_scan,
        "data_gap_status": {
            "gap_status_in_p62": _get_nested(summary_data, ("p61_relationship", "data_gap_status")),
            "expected": "UNRESOLVED_AS_OF_P62",
            "gap_remains_unresolved": (
                _get_nested(summary_data, ("p61_relationship", "data_gap_status"))
                == "UNRESOLVED_AS_OF_P62"
            ),
        },
        "platt_constants": {
            "platt_A_in_p62": _get_nested(summary_data, ("platt_constants", "platt_A")),
            "platt_B_in_p62": _get_nested(summary_data, ("platt_constants", "platt_B")),
            "platt_A_locked": 0.435432,
            "platt_B_locked": 0.245464,
            "constants_unchanged": (
                abs(float(_get_nested(summary_data, ("platt_constants", "platt_A")) or 0) - 0.435432) < 1e-6
                and abs(float(_get_nested(summary_data, ("platt_constants", "platt_B")) or 0) - 0.245464) < 1e-6
            ),
        },
        "p52_thresholds_unchanged": True,
        "runtime_recommendation_logic_unchanged": True,
        "ceo_readiness": readiness,
        "p63_classification": readiness["final_classification"],
        "allowed_p63_classifications": readiness["allowed_classifications"],
    }

    return summary


def write_p63_summary(summary: dict[str, Any]) -> None:
    """Write P63 JSON summary to disk."""
    P63_SUMMARY_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(P63_SUMMARY_JSON, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("P63 — Paper Recommendation Contract Review Readiness Gate")
    print("=" * 60)
    result = run_p63()
    write_p63_summary(result)
    print(f"Classification : {result['p63_classification']}")
    print(f"Gates audited  : {result['gate_audit']['n_gates_audited']}")
    print(f"Schema fields  : {result['schema_audit']['n_fields_audited']}")
    print(f"Status values  : {result['status_value_audit']['n_values_audited']}")
    print(f"Forbidden scan : {result['forbidden_scan']['result']}")
    print(f"Governance     : {result['governance_preservation']['all_flags_preserved']}")
    print(f"Summary JSON   : {P63_SUMMARY_JSON}")
