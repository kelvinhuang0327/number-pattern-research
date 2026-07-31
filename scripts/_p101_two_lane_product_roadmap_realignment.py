"""
P101 Two-Lane Product Roadmap Re-alignment Script
- Lane A: Taiwan Sports Lottery Pregame Market Contract (paper-only, no odds/EV/CLV/Kelly)
- Lane B: Outcome-Only Strategy Backtest and Learning Plan (no odds, no production mutation)
Governance: paper_only=true, diagnostic_only=true, production_ready=false
"""
import json
from pathlib import Path

LANE_A = {
    "lane": "A",
    "title": "Taiwan Sports Lottery Pregame Market Contract",
    "markets": [
        {"type": "moneyline", "supported": True, "required_fields": ["game_id", "predicted_side", "source_trace", "odds"], "blocked_reason": "legal odds missing if not present"},
        {"type": "run_line", "supported": False, "required_fields": ["game_id", "predicted_side", "source_trace", "odds"], "blocked_reason": "future odds data required"},
        {"type": "total_runs", "supported": False, "required_fields": ["game_id", "predicted_side", "source_trace", "odds"], "blocked_reason": "future odds data required"},
        {"type": "first_five_innings", "supported": False, "required_fields": ["game_id", "predicted_side", "source_trace", "odds"], "blocked_reason": "future odds data required"}
    ],
    "unsupported_market_status": True,
    "required_source_trace": True,
    "required_odds_fields": True,
    "recommendation_allowed": False
}

LANE_B = {
    "lane": "B",
    "title": "Outcome-Only Strategy Backtest and Learning Plan",
    "strategies": [
        "HIGH_FIP_diagnostic_segment",
        "MID_FIP_watch_only",
        "LOW_FIP_watch_only"
    ],
    "scorecard_fields": [
        "hit_rate", "AUC", "Brier", "ECE", "monthly_stability", "side_split", "rolling_drift"
    ],
    "strategy_comparison_matrix": True,
    "learning_loop_proposal": "Based on prediction success rate, update strategy weights (paper-only)",
    "win_loss_score_simulation": "If source data supports, simulate win/loss and scores",
    "calibration_refit": False,
    "production_mutation": False
}

summary = {
    "classification": "P101_TWO_LANE_ROADMAP_READY_DIAGNOSTIC_ONLY",
    "lane_a": LANE_A,
    "lane_b": LANE_B,
    "governance": {
        "paper_only": True,
        "diagnostic_only": True,
        "production_ready": False,
        "real_bet_allowed": False,
        "recommendation_allowed": False,
        "odds_used": False,
        "ev_computed": False,
        "clv_computed": False,
        "kelly_computed": False,
        "stake_sizing": False
    }
}

out_path = Path("data/mlb_2026/derived/p101_two_lane_product_roadmap_realignment_summary.json")
out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False))

report_path = Path("report/p101_two_lane_product_roadmap_realignment_20260531.md")
report_md = f"""
# P101 Two-Lane Product Roadmap Re-alignment — 2026-05-31

## Final Classification
{summary['classification']}

## Lane A — Taiwan Sports Lottery Pregame Market Contract
- Supported markets: moneyline (winner)
- Run line, total runs, first five innings: blocked (future odds required)
- Required fields: game_id, predicted_side, source_trace, odds
- Recommendation: BLOCKED if legal odds missing
- No odds/EV/CLV/Kelly/recommendation/production

## Lane B — Outcome-Only Strategy Backtest and Learning Plan
- Strategies: HIGH_FIP (diagnostic), MID/LOW (watch-only)
- Scorecard: hit_rate, AUC, Brier, ECE, monthly_stability, side_split, rolling_drift
- Strategy comparison matrix: included
- Learning loop: based on prediction success rate (paper-only)
- Win/loss/score simulation: if data supports
- No calibration refit or production mutation

## Governance
- paper_only=true
- diagnostic_only=true
- production_ready=false
- recommendation_allowed=false
- odds_used=false
- ev_computed=false
- clv_computed=false
- kelly_computed=false
- stake_sizing=false

"""
report_path.parent.mkdir(parents=True, exist_ok=True)
report_path.write_text(report_md)

active_task_path = Path("00-Plan/roadmap/active_task.md")
active_task_md = f"""
# Active Task — P101 Two-Lane Product Roadmap Re-alignment

- Final Classification: {summary['classification']}
- Lane A: Taiwan Sports Lottery Pregame Market Contract (paper-only)
- Lane B: Outcome-Only Strategy Backtest and Learning Plan (diagnostic-only)
- Governance: paper_only=true, diagnostic_only=true, production_ready=false
- Date: 2026-05-31
"""
active_task_path.write_text(active_task_md)
