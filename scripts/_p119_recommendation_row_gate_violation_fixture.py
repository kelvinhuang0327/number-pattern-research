# P119 Recommendation Row Gate Violation Fixture
# Diagnostic-only, negative-test fixture for recommendation row gate validation
# Do not generate valid recommendations, odds, or production logic
# Only outputs violation fixture summary JSON for gate testing

import json
from pathlib import Path

# Upstream artifact references
P118_PATH = "data/mlb_2026/derived/p118_recommendation_row_validation_gate_summary.json"
P117_PATH = "data/mlb_2026/derived/p117_paper_only_recommendation_row_fixture_summary.json"
P116_PATH = "data/mlb_2026/derived/p116_paper_only_recommendation_row_dry_run_contract_summary.json"
P115_PATH = "data/mlb_2026/derived/p115_paper_only_odds_ingestion_contract_fixture_summary.json"
P114_PATH = "data/mlb_2026/derived/p114_legal_odds_source_requirements_spec_summary.json"
P113_PATH = "data/mlb_2026/derived/p113_paper_only_market_contract_schema_fixture_summary.json"

OUT_PATH = "data/mlb_2026/derived/p119_recommendation_row_gate_violation_fixture_summary.json"

MARKETS = [
    "moneyline_winner",
    "run_line_handicap",
    "total_runs_over_under",
    "first_five_innings_if_supported_later",
    "unsupported_market_placeholder"
]

VIOLATION_CASES = [
    ("recommendation_allowed_true_violation", {"recommendation_allowed": True}, ["NO_RECOMMENDATION"]),
    ("production_ready_true_violation", {"production_ready": True}, ["NO_PRODUCTION_READY"]),
    ("real_odds_present_violation", {"odds": 1.95, "real_odds": 1.95}, ["NO_REAL_ODDS"]),
    ("ev_field_present_violation", {"ev": 0.12}, ["NO_EV_CLV_KELLY"]),
    ("clv_field_present_violation", {"clv": 0.08}, ["NO_EV_CLV_KELLY"]),
    ("kelly_field_present_violation", {"kelly": 0.05}, ["NO_EV_CLV_KELLY"]),
    ("stake_field_present_violation", {"stake": 100}, ["NO_STAKE_OR_PROFIT"]),
    ("profit_field_present_violation", {"profit": 50}, ["NO_STAKE_OR_PROFIT"]),
    ("missing_source_trace_violation", {"provider_id": None, "fetch_time": None}, ["SOURCE_TRACE_REQUIRED"]),
    ("missing_legal_provider_violation", {"legal_provider_authorized": False}, ["LEGAL_PROVIDER_REQUIRED_BEFORE_ACTIVATION"]),
    ("canonical_row_mutation_violation", {"canonical_rows_modified": True}, ["NO_CANONICAL_ROW_MUTATION"]),
    ("outcome_row_mutation_violation", {"outcome_rows_modified": True}, ["NO_OUTCOME_ROW_MUTATION"]),
    ("taiwan_lottery_recommendation_true_violation", {"taiwan_lottery_recommendation": True}, ["NO_RECOMMENDATION"])
]

INVARIANTS = [
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

def build_violation_cases():
    cases = []
    for market_id in MARKETS:
        for v_id, patch, violated in VIOLATION_CASES:
            case = {
                "violation_id": v_id,
                "market_id": market_id,
                "invalid_row_patch": patch,
                "violated_invariants": violated,
                "expected_gate_status": "BLOCKED",
                "expected_failure_message": f"Gate blocks {v_id} for {market_id}",
                "blocked_fields": list(patch.keys()),
                "governance_expected_result": "BLOCKED",
                "allowed_future_action": "None",
                "prohibited_action": "Production/Recommendation/Real Odds"
            }
            cases.append(case)
    return cases

def main():
    summary = {
        "violation_fixture_metadata": {
            "fixture_version": "P119.20260531",
            "generated_at": "2026-05-31",
            "final_classification": "P119_GATE_VIOLATION_FIXTURE_READY_WITH_BLOCKERS"
        },
        "source_p118_gate_reference": P118_PATH,
        "negative_fixture_scope": "Synthetic negative-test fixture for recommendation row gate validation. All cases are expected to be blocked by the P118 gate.",
        "invalid_recommendation_rows": len(VIOLATION_CASES) * len(MARKETS),
        "violation_cases": build_violation_cases(),
        "expected_gate_failures": len(VIOLATION_CASES) * len(MARKETS),
        "market_violation_matrix": MARKETS,
        "governance_violation_matrix": [v[0] for v in VIOLATION_CASES],
        "odds_safety_violation_matrix": [v[0] for v in VIOLATION_CASES if "odds" in v[1] or "real_odds" in v[1]],
        "source_trace_violation_matrix": [v[0] for v in VIOLATION_CASES if "provider_id" in v[1] or "fetch_time" in v[1]],
        "failure_messages": [f"Gate blocks {v[0]}" for v in VIOLATION_CASES],
        "allowed_future_actions": ["None"],
        "prohibited_actions": ["Production", "Recommendation", "Real Odds"],
        "invariant_coverage": INVARIANTS
    }
    Path(OUT_PATH).parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"P119 violation fixture summary written to {OUT_PATH}")

if __name__ == "__main__":
    main()
