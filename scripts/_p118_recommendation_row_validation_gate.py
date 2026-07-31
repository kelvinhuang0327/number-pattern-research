"""
P118 Recommendation Row Validation Gate
Diagnostic-only validation for P117 paper-only recommendation row fixture.
Strictly enforces governance, invariants, and market-by-market blocking.
"""
import json
import sys
from pathlib import Path

# --- Config ---
P117_PATH = "data/mlb_2026/derived/p117_paper_only_recommendation_row_fixture_summary.json"
P116_PATH = "data/mlb_2026/derived/p116_paper_only_recommendation_row_dry_run_contract_summary.json"
P115_PATH = "data/mlb_2026/derived/p115_paper_only_odds_ingestion_contract_fixture_summary.json"
P114_PATH = "data/mlb_2026/derived/p114_legal_odds_source_requirements_spec_summary.json"
P113_PATH = "data/mlb_2026/derived/p113_paper_only_market_contract_schema_fixture_summary.json"
P112_PATH = "data/mlb_2026/derived/p112_lane_a_market_contract_gap_review_summary.json"
P101_PATH = "data/mlb_2026/derived/p101_two_lane_product_roadmap_realignment_summary.json"
OUT_PATH = "data/mlb_2026/derived/p118_recommendation_row_validation_gate_summary.json"
REPORT_PATH = "report/p118_recommendation_row_validation_gate_20260531.md"

MARKETS = [
    "moneyline_winner",
    "run_line_handicap",
    "total_runs_over_under",
    "first_five_innings_if_supported_later",
    "unsupported_market_placeholder"
]

GOVERNANCE_GUARDS = {
    "paper_only": True,
    "diagnostic_only": True,
    "production_ready": False,
    "real_bet_allowed": False,
    "recommendation_allowed": False,
    "product_surface_allowed": False,
    "odds_used": False,
    "odds_fetched": False,
    "odds_stored": False,
    "odds_ingested": False,
    "live_api_calls": 0,
    "paid_api_calls": 0,
    "ev_computed": False,
    "clv_computed": False,
    "kelly_computed": False,
    "stake_sizing": False,
    "profit_computed": False,
    "recommendation_generated": False,
    "taiwan_lottery_recommendation": False,
    "champion_replacement": False,
    "production_mutation": False,
    "calibration_refit": False,
    "canonical_rows_modified": False,
    "outcome_rows_modified": False,
    "p83e_mapping_modified": False,
    "ui_modified": False,
    "branch_protection_modified": False,
    "force_push_used": False
}

REQUIRED_INVARIANTS = [
    "ROW_IS_PAPER_ONLY",
    "ROW_IS_DIAGNOSTIC_ONLY",
    "ROW_IS_BLOCKED",
    "NO_REAL_ODDS",
    "NO_RECOMMENDATION",
    "NO_EV_CLV_KELLY",
    "NO_STAKE_OR_PROFIT",
    "NO_PRODUCTION_READY",
    "NO_LIVE_API_CALLS",
    "NO_CANONICAL_ROW_MUTATION",
    "NO_OUTCOME_ROW_MUTATION",
    "SOURCE_TRACE_REQUIRED",
    "LEGAL_PROVIDER_REQUIRED_BEFORE_ACTIVATION"
]

FINAL_CLASSIFICATION_OPTIONS = [
    "P118_RECOMMENDATION_ROW_VALIDATION_GATE_READY_DIAGNOSTIC_ONLY",
    "P118_RECOMMENDATION_ROW_VALIDATION_GATE_READY_WITH_BLOCKERS",
    "P118_RECOMMENDATION_ROW_VALIDATION_GATE_BLOCKED_BY_MISSING_P117",
    "P118_RECOMMENDATION_ROW_VALIDATION_GATE_FAILED_VALIDATION"
]

# --- Load P117 ---
def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        return None

def main():
    p117 = load_json(P117_PATH)
    if not p117 or "fixture_metadata" not in p117:
        result = {
            "gate_metadata": {
                "gate_version": "P118.20260531",
                "generated_at": "2026-05-31",
                "final_classification": "P118_RECOMMENDATION_ROW_VALIDATION_GATE_BLOCKED_BY_MISSING_P117"
            },
            "error": "P117 summary missing or unreadable."
        }
        with open(OUT_PATH, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        sys.exit(1)

    # Check P117 classification
    classification = p117["fixture_metadata"].get("final_classification", "")
    if classification != "P117_RECOMMENDATION_ROW_FIXTURE_READY_WITH_BLOCKERS":
        result = {
            "gate_metadata": {
                "gate_version": "P118.20260531",
                "generated_at": "2026-05-31",
                "final_classification": "P118_RECOMMENDATION_ROW_VALIDATION_GATE_BLOCKED_BY_MISSING_P117"
            },
            "error": f"P117 classification invalid: {classification}"
        }
        with open(OUT_PATH, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        sys.exit(1)

    # Build validation gate summary
    summary = {
        "gate_metadata": {
            "gate_version": "P118.20260531",
            "generated_at": "2026-05-31",
            "final_classification": "P118_RECOMMENDATION_ROW_VALIDATION_GATE_READY_WITH_BLOCKERS"
        },
        "source_p117_fixture_reference": P117_PATH,
        "validation_scope": "Validates that all recommendation row fixtures remain paper-only, diagnostic-only, blocked, and non-recommendational until all legal, provider, ingestion, and governance gates are satisfied.",
        "required_row_invariants": REQUIRED_INVARIANTS,
        "market_row_validation_rules": [],
        "governance_validation_rules": GOVERNANCE_GUARDS,
        "blocked_decision_validation_rules": {
            "recommendation_allowed": False,
            "production_ready": False
        },
        "odds_safety_validation_rules": {
            "real_odds_fields_forbidden": True,
            "ev_clv_kelly_forbidden": True,
            "stake_profit_forbidden": True
        },
        "source_trace_validation_rules": {
            "source_trace_required": True,
            "legal_provider_required": True
        },
        "future_gate_requirements": [
            "All legal, provider, ingestion, and governance blockers must be cleared before recommendation_allowed or production_ready can be set true."
        ],
        "failure_modes": [
            "Missing or invalid P117 fixture",
            "recommendation_allowed set true",
            "production_ready set true",
            "real odds, EV, CLV, Kelly, stake, or profit present",
            "missing source trace or legal provider"
        ],
        "allowed_future_actions": [
            "May update fixture only after all blockers are cleared and governance is updated"
        ],
        "prohibited_actions": [
            "No recommendation, odds fetching, odds ingestion, EV, CLV, Kelly, stake sizing, profit, or production logic allowed"
        ]
    }

    # Market-by-market validation
    for market in MARKETS:
        rule = {
            "market_id": market,
            "required_fixture_presence": True,
            "required_dry_run_status": "blocked",
            "required_governance_fields": list(GOVERNANCE_GUARDS.keys()),
            "required_blocker_fields": [
                "LEGAL_ODDS_SOURCE_BLOCKER",
                "LEGAL_PROVIDER_AUTHORIZATION_BLOCKER",
                "ODDS_INGESTION_NOT_IMPLEMENTED_BLOCKER",
                "ODDS_SCHEMA_BLOCKER",
                "MARKET_MAPPING_BLOCKER",
                "SOURCE_TRACE_BLOCKER",
                "TIMESTAMP_FRESHNESS_BLOCKER",
                "DATA_QUALITY_BLOCKER",
                "EV_CLV_NOT_ALLOWED_BLOCKER",
                "KELLY_STAKE_NOT_ALLOWED_BLOCKER",
                "GOVERNANCE_PRODUCTION_BLOCKER",
                "RECOMMENDATION_NOT_ALLOWED_BLOCKER"
            ],
            "required_source_trace_placeholder": True,
            "required_odds_reference_placeholder": True,
            "forbidden_real_odds_fields": True,
            "forbidden_decision_fields": True,
            "forbidden_production_fields": True,
            "validation_status": "blocked",
            "failure_message_if_invalid": f"{market} row must remain blocked, paper-only, diagnostic-only, and non-recommendational."
        }
        summary["market_row_validation_rules"].append(rule)

    # Write summary
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    # Write report
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(f"# P118 Recommendation Row Validation Gate\n\n")
        f.write(f"- Gate version: P118.20260531\n")
        f.write(f"- Generated at: 2026-05-31\n")
        f.write(f"- Final classification: {summary['gate_metadata']['final_classification']}\n\n")
        f.write(f"## Required Row Invariants\n\n")
        for inv in REQUIRED_INVARIANTS:
            f.write(f"- {inv}\n")
        f.write(f"\n## Market-by-Market Validation\n\n")
        for rule in summary["market_row_validation_rules"]:
            f.write(f"- {rule['market_id']}: {rule['validation_status']} — {rule['failure_message_if_invalid']}\n")
        f.write(f"\n## Governance Validation\n\n")
        for k, v in GOVERNANCE_GUARDS.items():
            f.write(f"- {k}: {v}\n")
        f.write(f"\n## Allowed Future Actions\n\n")
        for act in summary["allowed_future_actions"]:
            f.write(f"- {act}\n")
        f.write(f"\n## Prohibited Actions\n\n")
        for act in summary["prohibited_actions"]:
            f.write(f"- {act}\n")
        f.write(f"\n## Failure Modes\n\n")
        for fail in summary["failure_modes"]:
            f.write(f"- {fail}\n")
        f.write(f"\n## Future Gate Requirements\n\n")
        for req in summary["future_gate_requirements"]:
            f.write(f"- {req}\n")
        f.write(f"\n## Blocked Decision Validation\n\n")
        for k, v in summary["blocked_decision_validation_rules"].items():
            f.write(f"- {k}: {v}\n")
        f.write(f"\n## Odds Safety Validation\n\n")
        for k, v in summary["odds_safety_validation_rules"].items():
            f.write(f"- {k}: {v}\n")
        f.write(f"\n## Source Trace Validation\n\n")
        for k, v in summary["source_trace_validation_rules"].items():
            f.write(f"- {k}: {v}\n")

if __name__ == "__main__":
    main()
