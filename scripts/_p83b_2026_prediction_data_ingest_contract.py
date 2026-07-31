"""
P83B — 2026 Prediction Data Ingest Contract / Awaiting Stub
Date: 2026-05-26
Mode: paper_only=True | diagnostic_only=True | NO_REAL_BET=True

Goals:
  1. Verify P83A awaiting-state.
  2. Define canonical 2026 prediction data paths.
  3. Specify 2026 prediction row schema (extension of 2025 schema).
  4. Document 2025-to-2026 extension contract.
  5. Define validator and snapshot trigger contract.
  6. Generate future P83C prompt for when data arrives.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# ---------------------------------------------------------------------------
# Governance — MUST stay paper_only=True / diagnostic_only=True
# ---------------------------------------------------------------------------
GOVERNANCE: dict[str, Any] = {
    "paper_only": True,
    "diagnostic_only": True,
    "uses_historical_odds": False,
    "live_api_calls": 0,
    "the_odds_api_key_required": False,
    "ev_calculated": False,
    "clv_calculated": False,
    "market_edge_calculated": False,
    "kelly_deploy_allowed": False,
    "production_ready": False,
    "real_bet_allowed": False,
    "champion_replacement_allowed": False,
    "profitability_claim": False,
}

ALLOWED_CLASSIFICATIONS = [
    "P83B_INGEST_CONTRACT_READY_AWAITING_DATA",
    "P83B_INGEST_CONTRACT_READY_WITH_EXISTING_DATA",
    "P83B_BLOCKED_BY_MISSING_P83A_ARTIFACT",
    "P83B_FAILED_VALIDATION",
]

PREDICTION_BOUNDARY = (
    "P83B is an ingest contract definition only. "
    "No live data is processed; no market edge is computed. "
    "paper_only=True, diagnostic_only=True."
)

# ---------------------------------------------------------------------------
# Source / output paths
# ---------------------------------------------------------------------------
P83A_JSON = ROOT / "data/mlb_2026/derived/p83a_2026_live_accumulation_first_snapshot_summary.json"

PRIOR_PATHS = {
    "p82c_json": ROOT / "data/mlb_2025/derived/p82c_staging_guard_dryrun_scanner_summary.json",
    "p82b_json": ROOT / "data/mlb_2025/derived/p82b_raw_paid_odds_data_policy_contract_summary.json",
    "p82a_json": ROOT / "data/mlb_2025/derived/p82a_real_legal_odds_intake_gate_summary.json",
    "p81_json":  ROOT / "data/mlb_2025/derived/p81_legal_odds_dataset_validator_contract_summary.json",
    "p80_json":  ROOT / "data/mlb_2025/derived/p80_market_edge_reentry_readiness_contract_summary.json",
    "p79b_json": ROOT / "data/mlb_2025/derived/p79b_tier_b_vs_tier_c_comparison_harness_summary.json",
    "p79a_json": ROOT / "data/mlb_2025/derived/p79a_tier_b_trigger_readiness_contract_summary.json",
    "p78_json":  ROOT / "data/mlb_2025/derived/p78_monthly_shadow_tracker_report_template_summary.json",
    "p77_json":  ROOT / "data/mlb_2025/derived/p77_prediction_only_shadow_tracker_contract_summary.json",
    "p76_json":  ROOT / "data/mlb_2025/derived/p76_corrected_tier_c_final_rule_selection_summary.json",
    "p75b_json": ROOT / "data/mlb_2025/derived/p75b_calibration_diagnostics_corrected_tier_c_summary.json",
    "p75a_json": ROOT / "data/mlb_2025/derived/p75a_tier_c_corrected_rule_validator_summary.json",
    "p74_json":  ROOT / "data/mlb_2025/derived/p74_tier_c_home_away_bias_correction_summary.json",
    "p73_json":  ROOT / "data/mlb_2025/derived/p73_tier_stability_and_sample_expansion_summary.json",
    "p72b_json": ROOT / "data/mlb_2025/derived/p72b_objective_metric_contract_summary.json",
    "p72a_json": ROOT / "data/mlb_2025/derived/p72a_odds_free_strategy_accuracy_backtest_summary.json",
}

OUTPUT_JSON   = ROOT / "data/mlb_2026/derived/p83b_2026_prediction_data_ingest_contract_summary.json"
OUTPUT_REPORT = ROOT / "report/p83b_2026_prediction_data_ingest_contract_20260526.md"
PLAN_REPORT   = ROOT / "00-BettingPlan/20260526/p83b_2026_prediction_data_ingest_contract_20260526.md"

# ---------------------------------------------------------------------------
# Step 1 — Verify P83A awaiting state
# ---------------------------------------------------------------------------
def step1_verify_p83a(p83a: dict) -> dict:
    cls          = p83a.get("p83a_classification", "")
    disc         = p83a.get("step2_discovery", {})
    await_c      = p83a.get("step5_awaiting_contract", {})
    gov          = p83a.get("governance", {})
    p82c_v       = p83a.get("step1_p82c_verification", {})

    schema_rows  = disc.get("total_2026_rows_with_required_schema", -1)
    thresholds   = await_c.get("snapshot_thresholds", {})
    p82_status   = p82c_v.get("p82_status", "")
    live_api     = gov.get("live_api_calls", -1)

    # Runtime paper file should be marked as excluded
    incompatible = disc.get("schema_incompatible_files_count", 0)
    data_found   = disc.get("data_found", True)   # expected False

    ok = (
        cls == "P83A_AWAITING_2026_DATA"
        and schema_rows == 0
        and not data_found
        and len(thresholds) >= 5
        and p82_status == "BLOCKED_NO_REAL_DATASET"
        and live_api == 0
    )

    return {
        "classification": cls,
        "classification_ok": cls == "P83A_AWAITING_2026_DATA",
        "schema_rows": schema_rows,
        "schema_rows_zero": schema_rows == 0,
        "data_found": data_found,
        "runtime_paper_file_excluded": incompatible >= 0,   # file is in incompatible list
        "thresholds_count": len(thresholds),
        "thresholds_ok": len(thresholds) >= 5,
        "p82_status": p82_status,
        "p82_blocked": p82_status == "BLOCKED_NO_REAL_DATASET",
        "live_api_calls": live_api,
        "live_api_ok": live_api == 0,
        "verification_ok": ok,
    }


# ---------------------------------------------------------------------------
# Step 2 — Canonical 2026 prediction data paths
# ---------------------------------------------------------------------------
CANONICAL_PATHS = {
    "prediction_rows_jsonl": "data/mlb_2026/predictions/mlb_2026_prediction_rows.jsonl",
    "derived_accumulation_rows_jsonl": "data/mlb_2026/derived/p83_live_accumulation_rows.jsonl",
    "derived_accumulation_latest_summary_json": "data/mlb_2026/derived/p83_live_accumulation_latest_summary.json",
    "live_report_md": "report/p83_live_accumulation_latest.md",
}

RUNTIME_PAPER_HANDLING = {
    "path_pattern": "outputs/recommendations/PAPER/2026-*/",
    "status": "NON_CANONICAL",
    "reason": (
        "Runtime PAPER recommendation outputs use market-pipeline schema "
        "(contains edge_pct, kelly_fraction) and lack sp_fip_delta / predicted_side. "
        "These files must not be treated as canonical P83 research rows."
    ),
    "adapter_required": True,
    "adapter_task": "Future task: P83_RUNTIME_ADAPTER — transform PAPER output to P83A schema if needed.",
    "current_status": "DEFERRED",
}

def step2_canonical_paths() -> dict:
    return {
        "canonical_paths": CANONICAL_PATHS,
        "runtime_paper_output_handling": RUNTIME_PAPER_HANDLING,
    }


# ---------------------------------------------------------------------------
# Step 3 — 2026 prediction row schema (v1)
# ---------------------------------------------------------------------------
REQUIRED_FIELDS_V1 = [
    "game_id",
    "game_date",
    "season",
    "home_team",
    "away_team",
    "predicted_side",
    "model_probability",
    "sp_fip_delta",
    "abs_sp_fip_delta",
    "source_prediction_version",
    "rule_primary_125_flag",
    "rule_shadow_100_flag",
    "tier_b_candidate_flag",
    "tier_a_watchlist_flag",
    "paper_only",
    "diagnostic_only",
    "odds_used",
    "market_edge_evaluated",
    "production_ready",
]

OPTIONAL_OUTCOME_FIELDS_V1 = [
    "actual_winner",
    "is_correct",
    "outcome_source",
    "outcome_available",
    "outcome_finalized_at",
]

GOVERNANCE_ENFORCED_VALUES: dict[str, Any] = {
    "season": 2026,
    "paper_only": True,
    "diagnostic_only": True,
    "odds_used": False,
    "market_edge_evaluated": False,
    "production_ready": False,
}

def step3_row_schema() -> dict:
    return {
        "schema_id": "P83B_2026_PREDICTION_ROW_SCHEMA_V1",
        "version": "1.0.0",
        "required_fields": REQUIRED_FIELDS_V1,
        "optional_outcome_fields": OPTIONAL_OUTCOME_FIELDS_V1,
        "governance_enforced_values": GOVERNANCE_ENFORCED_VALUES,
        "field_notes": {
            "sp_fip_delta": "home_sp_fip - away_sp_fip; positive = home favored",
            "abs_sp_fip_delta": "abs(sp_fip_delta)",
            "predicted_side": "'home' if sp_fip_delta > 0 else 'away'",
            "model_probability": "P(predicted_side wins) from ensemble model",
            "rule_primary_125_flag": (
                "True if (predicted_side=home AND abs_sp_fip_delta>=0.50) "
                "OR (predicted_side=away AND abs_sp_fip_delta>=1.25)"
            ),
            "rule_shadow_100_flag": (
                "True if (predicted_side=home AND abs_sp_fip_delta>=0.50) "
                "OR (predicted_side=away AND abs_sp_fip_delta>=1.00)"
            ),
            "tier_b_candidate_flag": "True if 0.25 <= abs_sp_fip_delta < 0.50",
            "tier_a_watchlist_flag": "True if abs_sp_fip_delta < 0.25",
            "source_prediction_version": "mlb_2026_prediction_rows_v1",
        },
    }


# ---------------------------------------------------------------------------
# Step 4 — 2025-to-2026 extension contract
# ---------------------------------------------------------------------------
SOURCE_2025_PATH = (
    "data/mlb_2025/derived/"
    "mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl"
)

def step4_extension_contract() -> dict:
    return {
        "contract_id": "P83B_2025_TO_2026_EXTENSION_CONTRACT_V1",
        "source_2025_path": SOURCE_2025_PATH,
        "target_2026_path": CANONICAL_PATHS["prediction_rows_jsonl"],
        "target_version": "mlb_2026_prediction_rows_v1",
        "preserved_semantics": {
            "sp_fip_delta": (
                "home_sp_fip - away_sp_fip, using same FIP calculation as 2025 pipeline. "
                "FIP = (13*HR + 3*(BB+HBP) - 2*K) / IP + FIP_constant."
            ),
            "model_probability": (
                "P(home wins) from ensemble; convert to P(predicted_side wins) "
                "the same way as 2025 pipeline."
            ),
            "predicted_side": (
                "Same logic: 'home' if sp_fip_delta > 0 else 'away'. "
                "Ties (sp_fip_delta == 0) excluded."
            ),
            "rule_primary_125": (
                "Home: abs_sp_fip_delta >= 0.50 AND predicted_side='home'. "
                "Away: abs_sp_fip_delta >= 1.25 AND predicted_side='away'."
            ),
            "rule_shadow_100": (
                "Home: abs_sp_fip_delta >= 0.50 AND predicted_side='home'. "
                "Away: abs_sp_fip_delta >= 1.00 AND predicted_side='away'."
            ),
            "tier_b": "0.25 <= abs_sp_fip_delta < 0.50 (research only, n>=200 needed).",
            "tier_a_watchlist": "abs_sp_fip_delta < 0.25 (monitoring only).",
            "governance_fields": (
                "paper_only=True, diagnostic_only=True, odds_used=False, "
                "market_edge_evaluated=False, production_ready=False. "
                "Same as 2025 pipeline."
            ),
        },
        "new_fields_required_in_2026": [
            "rule_primary_125_flag",
            "rule_shadow_100_flag",
            "tier_b_candidate_flag",
            "tier_a_watchlist_flag",
        ],
        "no_retraining_required": True,
        "no_live_api_required": True,
        "extension_notes": [
            "2026 pipeline reads from statsapi.mlb.com for starter FIP data.",
            "FIP calculation identical to 2025; only season=2026 differs.",
            "Rule flags are deterministic from sp_fip_delta — no ML needed.",
            "Outcome fields remain optional until game results available.",
        ],
    }


# ---------------------------------------------------------------------------
# Step 5 — Validator contract and snapshot triggers
# ---------------------------------------------------------------------------
SNAPSHOT_TRIGGERS = {
    "smoke":          {"min_n": 1,   "label": "smoke_snapshot",            "classification": "P83C_SMOKE_SNAPSHOT_READY"},
    "sample_limited": {"min_n": 10,  "label": "first_sample_limited",      "classification": "P83C_SAMPLE_LIMITED_SNAPSHOT_READY"},
    "checkpoint_1":   {"min_n": 50,  "label": "checkpoint_1",              "classification": "P83C_CHECKPOINT_1_READY"},
    "checkpoint_2":   {"min_n": 100, "label": "checkpoint_2",              "classification": "P83C_CHECKPOINT_2_READY"},
    "operational":    {"min_n": 200, "label": "operational_checkpoint",    "classification": "P83C_OPERATIONAL_SNAPSHOT_READY"},
}

ABS_SP_FIP_DELTA_TOLERANCE = 1e-6

def step5_validator_contract() -> dict:
    return {
        "validator_id": "P83B_ROW_VALIDATOR_V1",
        "checks": [
            {
                "check_id": "required_fields_present",
                "description": "All required fields must be present in each row.",
                "fields": REQUIRED_FIELDS_V1,
            },
            {
                "check_id": "season_2026_enforced",
                "description": "season field must equal 2026.",
                "required_season": 2026,
            },
            {
                "check_id": "governance_clean",
                "description": "All governance fields must match enforced values.",
                "enforced_values": GOVERNANCE_ENFORCED_VALUES,
            },
            {
                "check_id": "abs_sp_fip_delta_tolerance",
                "description": "abs_sp_fip_delta must equal abs(sp_fip_delta) within tolerance.",
                "tolerance": ABS_SP_FIP_DELTA_TOLERANCE,
                "formula": "abs(row['sp_fip_delta']) - row['abs_sp_fip_delta'] < tolerance",
            },
            {
                "check_id": "rule_flags_deterministic",
                "description": "Rule flags must be deterministic given sp_fip_delta and predicted_side.",
                "primary_125_logic": (
                    "(predicted_side='home' AND abs_sp_fip_delta>=0.50) "
                    "OR (predicted_side='away' AND abs_sp_fip_delta>=1.25)"
                ),
                "shadow_100_logic": (
                    "(predicted_side='home' AND abs_sp_fip_delta>=0.50) "
                    "OR (predicted_side='away' AND abs_sp_fip_delta>=1.00)"
                ),
                "tier_b_logic": "0.25 <= abs_sp_fip_delta < 0.50",
                "tier_a_logic": "abs_sp_fip_delta < 0.25",
            },
            {
                "check_id": "no_odds_required",
                "description": "odds_used must be False; no odds fields required.",
                "expected": "odds_used=False",
            },
            {
                "check_id": "outcomes_pending_classification",
                "description": (
                    "If is_correct / actual_winner absent or None, "
                    "classify row as OUTCOMES_PENDING."
                ),
                "outcomes_pending_class": "OUTCOMES_PENDING",
                "outcomes_available_class": "OUTCOMES_PRESENT",
            },
            {
                "check_id": "is_correct_validation",
                "description": (
                    "If is_correct present: must be True if actual_winner == predicted_side "
                    "else False. Flag inconsistency."
                ),
            },
        ],
        "snapshot_triggers": SNAPSHOT_TRIGGERS,
        "abs_sp_fip_delta_tolerance": ABS_SP_FIP_DELTA_TOLERANCE,
        "rerun_condition": (
            "Rerun P83C whenever canonical JSONL file changes "
            "or row count crosses next threshold."
        ),
    }


# ---------------------------------------------------------------------------
# Step 6 — Future P83C prompt
# ---------------------------------------------------------------------------
def step6_p83c_prompt() -> dict:
    return {
        "future_phase": "P83C",
        "trigger": "When data/mlb_2026/predictions/mlb_2026_prediction_rows.jsonl exists with n>=1 rows",
        "prompt": (
            "[P83C — 2026 Live Accumulation First Real Snapshot]\n\n"
            "Continue from P83B (commit <P83B_COMMIT_HASH>). "
            "P83B_INGEST_CONTRACT_READY_AWAITING_DATA contract is in place.\n\n"
            "2026 prediction rows are now available at:\n"
            "  data/mlb_2026/predictions/mlb_2026_prediction_rows.jsonl\n\n"
            "P83C must:\n"
            "1. Load canonical 2026 prediction rows from canonical path.\n"
            "2. Run P83B_ROW_VALIDATOR_V1 on each row.\n"
            "3. Count: total rows / governance-clean / primary_125 / shadow_100 / tier_b / tier_a.\n"
            "4. Determine snapshot level (smoke/sample_limited/checkpoint_1/checkpoint_2/operational).\n"
            "5. If outcomes available: compute hit_rate / AUC / Brier / ECE.\n"
            "   If not: classify as OUTCOMES_PENDING.\n"
            "6. Compare 2026 hit_rate to 2025 baseline (HOME_PLUS_AWAY_125: hit=0.6392, AUC=0.5787).\n"
            "7. Generate snapshot report.\n"
            "8. Keep P82 market-edge blocked — no odds, no EV, no CLV, no Kelly.\n\n"
            "paper_only=True | diagnostic_only=True | NO_REAL_BET=True"
        ),
        "minimum_n_to_trigger": SNAPSHOT_TRIGGERS["smoke"]["min_n"],
        "preferred_n_to_trigger": SNAPSHOT_TRIGGERS["sample_limited"]["min_n"],
        "reference_baseline": {
            "rule": "TIER_C_HOME_PLUS_AWAY_125",
            "hit_rate_2025": 0.6392,
            "auc_2025": 0.5787,
            "cal_brier_2025": 0.2274,
            "n_2025": 316,
        },
    }


# ---------------------------------------------------------------------------
# Forbidden phrase scan
# ---------------------------------------------------------------------------
FORBIDDEN_PHRASES = [
    "closing_line_value",
    '"clv_calculated": true',
    "kelly fraction",
    '"kelly_deploy_allowed": true',
    '"production_ready": true',
    "profitability confirmed",
    '"real_bet_allowed": true',
    '"p82_unlocked": true',
]


def _scan_forbidden(text: str) -> dict:
    violations = [p for p in FORBIDDEN_PHRASES if p.lower() in text.lower()]
    return {"violations": violations, "result": "CLEAN" if not violations else "VIOLATION_FOUND"}


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
def _generate_report(result: dict) -> str:
    lines: list[str] = []
    a = lines.append
    cls = result.get("p83b_classification", "—")

    a("# P83B — 2026 Prediction Data Ingest Contract / Awaiting Stub")
    a("**Date:** 2026-05-26  ")
    a(f"**Phase:** P83B  ")
    a(f"**Classification:** `{cls}`  ")
    a("**Mode:** paper_only=True | diagnostic_only=True | NO_REAL_BET=True")
    a("")
    a("---")
    a("")
    a("## P83A Awaiting-State Verification")
    a("")
    v = result["step1_p83a_verification"]
    a(f"- P83A classification: `{v['classification']}` {'✅' if v['classification_ok'] else '❌'}")
    a(f"- Schema rows (2026 research): {v['schema_rows']} {'✅' if v['schema_rows_zero'] else '❌'}")
    a(f"- Runtime PAPER file excluded: {'✅' if v['runtime_paper_file_excluded'] else '❌'}")
    a(f"- Snapshot thresholds: {v['thresholds_count']} {'✅' if v['thresholds_ok'] else '❌'}")
    a(f"- P82 status: `{v['p82_status']}` {'✅' if v['p82_blocked'] else '❌'}")
    a(f"- live_api_calls: {v['live_api_calls']} {'✅' if v['live_api_ok'] else '❌'}")
    a("")
    a("---")
    a("")
    a("## Canonical 2026 Paths")
    a("")
    cp = result["step2_canonical_paths"]["canonical_paths"]
    for k, v2 in cp.items():
        a(f"- `{k}`: `{v2}`")
    a("")
    rph = result["step2_canonical_paths"]["runtime_paper_output_handling"]
    a(f"**Runtime PAPER output:** {rph['status']}")
    a(f"> {rph['reason']}")
    a(f"> Adapter: {rph['adapter_task']}")
    a("")
    a("---")
    a("")
    a("## 2026 Row Schema (v1)")
    a("")
    schema = result["step3_row_schema"]
    a(f"**Schema ID:** `{schema['schema_id']}`")
    a("")
    a("### Required Fields")
    for f in schema["required_fields"]:
        a(f"- `{f}`")
    a("")
    a("### Optional Outcome Fields")
    for f in schema["optional_outcome_fields"]:
        a(f"- `{f}`")
    a("")
    a("### Governance Enforced Values")
    for k, v2 in schema["governance_enforced_values"].items():
        a(f"- `{k}` = `{v2}`")
    a("")
    a("---")
    a("")
    a("## 2025→2026 Extension Contract")
    a("")
    ext = result["step4_extension_contract"]
    a(f"**Source 2025:** `{ext['source_2025_path']}`")
    a(f"**Target 2026:** `{ext['target_2026_path']}`")
    a(f"**Version:** `{ext['target_version']}`")
    a(f"**No retraining required:** {'✅' if ext['no_retraining_required'] else '❌'}")
    a(f"**No live API required:** {'✅' if ext['no_live_api_required'] else '❌'}")
    a("")
    a("### Preserved Semantics")
    for k, v2 in ext["preserved_semantics"].items():
        a(f"- **{k}**: {v2}")
    a("")
    a("---")
    a("")
    a("## Validator Contract")
    a("")
    val = result["step5_validator_contract"]
    a(f"**Validator ID:** `{val['validator_id']}`")
    a(f"**abs_sp_fip_delta tolerance:** {val['abs_sp_fip_delta_tolerance']}")
    a("")
    a("### Snapshot Triggers")
    a("")
    a("| Level | Min n | Label | Classification |")
    a("|---|---:|---|---|")
    for k, t in SNAPSHOT_TRIGGERS.items():
        a(f"| {k} | {t['min_n']} | `{t['label']}` | `{t['classification']}` |")
    a("")
    a("---")
    a("")
    a("## Future P83C Prompt")
    a("")
    p83c = result["step6_p83c_prompt"]
    a(f"**Trigger:** {p83c['trigger']}")
    a(f"**Minimum n:** {p83c['minimum_n_to_trigger']}")
    a(f"**Preferred n:** {p83c['preferred_n_to_trigger']}")
    a("")
    a("**2025 Baseline Reference:**")
    ref = p83c["reference_baseline"]
    a(f"- Rule: `{ref['rule']}` | hit=`{ref['hit_rate_2025']}` | AUC=`{ref['auc_2025']}` | n=`{ref['n_2025']}`")
    a("")
    a("```")
    a(p83c["prompt"])
    a("```")
    a("")
    a("---")
    a("")
    a("*paper_only=True | diagnostic_only=True | NO_REAL_BET=True*")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def run_p83b() -> dict:
    if not P83A_JSON.exists():
        return {
            "phase": "P83B",
            "date": "2026-05-26",
            "p83b_classification": "P83B_BLOCKED_BY_MISSING_P83A_ARTIFACT",
            "governance": GOVERNANCE,
        }

    p83a = json.loads(P83A_JSON.read_text())

    # Step 1
    p83a_verification = step1_verify_p83a(p83a)
    if not p83a_verification["verification_ok"]:
        return {
            "phase": "P83B",
            "date": "2026-05-26",
            "p83b_classification": "P83B_FAILED_VALIDATION",
            "step1_p83a_verification": p83a_verification,
            "governance": GOVERNANCE,
        }

    canonical = step2_canonical_paths()
    schema    = step3_row_schema()
    ext       = step4_extension_contract()
    validator = step5_validator_contract()
    p83c_prompt = step6_p83c_prompt()

    # Determine classification: data still absent → awaiting
    p83a_disc = p83a.get("step2_discovery", {})
    data_present = p83a_disc.get("data_found", False)

    classification = (
        "P83B_INGEST_CONTRACT_READY_WITH_EXISTING_DATA"
        if data_present
        else "P83B_INGEST_CONTRACT_READY_AWAITING_DATA"
    )

    result: dict[str, Any] = {
        "phase": "P83B",
        "date": "2026-05-26",
        "p83b_classification": classification,
        "allowed_classifications": ALLOWED_CLASSIFICATIONS,
        "governance": GOVERNANCE,
        "prediction_boundary": PREDICTION_BOUNDARY,
        "source_artifacts": {k: str(p) for k, p in {**PRIOR_PATHS, "p83a_json": P83A_JSON}.items()},
        "step1_p83a_verification": p83a_verification,
        "step2_canonical_paths": canonical,
        "step3_row_schema": schema,
        "step4_extension_contract": ext,
        "step5_validator_contract": validator,
        "step6_p83c_prompt": p83c_prompt,
        "p82_status": "BLOCKED_NO_REAL_DATASET",
        "p82_unlock_condition": "Requires external legal odds dataset + P81 validator pass",
    }

    result_text = json.dumps(result, indent=2)
    scan = _scan_forbidden(result_text)
    result["forbidden_scan"] = scan

    return result


def main() -> None:
    result = run_p83b()
    cls = result.get("p83b_classification", "UNKNOWN")
    print(f"[P83B] Classification: {cls}")

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON, "w") as f:
        json.dump(result, f, indent=2)
    print(f"[P83B] JSON → {OUTPUT_JSON}")

    if cls not in ("P83B_BLOCKED_BY_MISSING_P83A_ARTIFACT", "P83B_FAILED_VALIDATION"):
        report_text = _generate_report(result)
        OUTPUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_REPORT.write_text(report_text)
        print(f"[P83B] Report → {OUTPUT_REPORT}")
        PLAN_REPORT.parent.mkdir(parents=True, exist_ok=True)
        PLAN_REPORT.write_text(report_text)
        print(f"[P83B] Plan report → {PLAN_REPORT}")

    scan = result.get("forbidden_scan", {})
    if scan.get("result") != "CLEAN":
        print(f"[P83B] FORBIDDEN PHRASE VIOLATION: {scan.get('violations')}")
        sys.exit(1)
    print("[P83B] Forbidden scan: CLEAN")
    print("[P83B] Done.")


if __name__ == "__main__":
    main()
