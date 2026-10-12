"""
P104 Outcome-Only Score Simulation Design
Diagnostic-only contract/schema for win-loss/score simulation (no betting/EV/CLV/Kelly/production logic)
"""
import json
from typing import List, Dict, Any, Optional
from pathlib import Path

# --- Schema Definition ---
SCORE_SIMULATION_SCHEMA = {
    "strategy_id": str,
    "eligible_rows": List[Dict[str, Any]],  # Each row: prediction + outcome fields
    "predicted_side": str,
    "actual_winner": str,
    "win_loss_result": str,  # "win" | "loss"
    "home_score": int,
    "away_score": int,
    "score_margin": int,
    "score_margin_bucket": str,
    "accuracy_metrics": Dict[str, Any],
    "sample_limitations": Optional[str],
}

SUPPORTED_SIMULATIONS = [
    "win_loss_simulation_by_strategy",
    "side_accuracy_by_strategy",
    "monthly_win_loss_simulation",
    "score_margin_descriptive_analysis",
]
BLOCKED_SIMULATIONS = [
    "profit_simulation_blocked",
    "ev_simulation_blocked",
    "clv_simulation_blocked",
    "kelly_or_stake_simulation_blocked",
    "taiwan_lottery_recommendation_blocked",
]

GOVERNANCE = {
    "paper_only": True,
    "diagnostic_only": True,
    "production_ready": False,
    "real_bet_allowed": False,
    "recommendation_allowed": False,
    "product_surface_allowed": False,
    "odds_used": False,
    "ev_computed": False,
    "clv_computed": False,
    "kelly_computed": False,
    "stake_sizing": False,
    "taiwan_lottery_recommendation": False,
    "champion_replacement": False,
    "production_mutation": False,
    "calibration_refit": False,
    "live_api_calls": 0,
    "paid_api_calls": 0,
    "canonical_rows_modified": False,
    "outcome_rows_modified": False,
    "p83e_mapping_modified": False,
}

FINAL_CLASSIFICATION = "P104_SCORE_SIMULATION_DESIGN_READY_DIAGNOSTIC_ONLY"
NEXT_IMPLEMENTATION_TARGET = "P105 Outcome-Only Win/Loss and Score Simulation Runner"

# --- Evidence Generation (Design Only) ---
def main():
    summary = {
        "date": "2026-05-31",
        "final_classification": FINAL_CLASSIFICATION,
        "supported_simulations": SUPPORTED_SIMULATIONS,
        "blocked_simulations": BLOCKED_SIMULATIONS,
        "governance": GOVERNANCE,
        "next_implementation_target": NEXT_IMPLEMENTATION_TARGET,
        "schema": list(SCORE_SIMULATION_SCHEMA.keys()),
        "note": "This is a diagnostic-only contract/schema design. No betting, EV, CLV, Kelly, or production logic included."
    }
    out_path = Path("data/mlb_2026/derived/p104_outcome_only_score_simulation_design_summary.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"[P104] Score simulation design summary written: {out_path}")

if __name__ == "__main__":
    main()
