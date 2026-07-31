import json
from pathlib import Path
from typing import Any, Dict

def load_json(path: str) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def main():
    # Load required inputs
    p107 = load_json("data/mlb_2026/derived/p107_outcome_only_strategy_adjustment_backlog_summary.json")
    p106 = load_json("data/mlb_2026/derived/p106_outcome_only_simulation_review_strategy_adjustment_summary.json")
    p105 = load_json("data/mlb_2026/derived/p105_outcome_only_score_simulation_runner_summary.json")
    p104 = load_json("data/mlb_2026/derived/p104_outcome_only_score_simulation_design_summary.json")
    p103 = load_json("data/mlb_2026/derived/p103_outcome_only_strategy_learning_matrix_summary.json")
    p102 = load_json("data/mlb_2026/derived/p102_outcome_only_strategy_backtest_scorecard_summary.json")
    # p84e is not loaded for summary, only for test coverage

    # Governance lock
    governance = {
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
        "p83e_mapping_modified": False
    }

    # Classification
    final_classification = "P108_DIAGNOSTIC_TRACKING_REPORT_READY"
    date = p107.get("date")

    # Backlog extraction
    backlog = p107["backlog"]
    def extract_items(cat):
        return backlog.get(cat, [])
    active_diag = extract_items("IMMEDIATE_DIAGNOSTIC_TRACKING")
    watch_only = extract_items("WATCH_ONLY_CONTINUE")
    sample_limited = extract_items("SAMPLE_LIMITED_WAIT_FOR_DATA")
    paused = extract_items("PAUSE_OPTIMIZATION") + extract_items("REJECT_FOR_NOW")
    blocked = extract_items("BLOCKED_PRODUCTION")

    # Next data thresholds
    next_data_thresholds = {}
    for cat in [active_diag, watch_only, sample_limited]:
        for item in cat:
            next_data_thresholds[item["strategy_id"]] = item.get("data_threshold", None)

    # Compose summary
    summary = {
        "date": date,
        "final_classification": final_classification,
        "active_diagnostic_tracking": active_diag,
        "watch_only_tracking": watch_only,
        "sample_limited_tracking": sample_limited,
        "paused_or_rejected_tracking": paused,
        "blocked_production_items": blocked,
        "next_data_thresholds": next_data_thresholds,
        "governance": governance,
        "source_backlog_classification": p107["final_classification"],
        "source_backlog_date": p107.get("date"),
        "source_backlog_file": "p107_outcome_only_strategy_adjustment_backlog_summary.json",
        "source_simulation_review": "p106_outcome_only_simulation_review_strategy_adjustment_summary.json",
        "source_score_simulation": "p105_outcome_only_score_simulation_runner_summary.json",
        "source_score_design": "p104_outcome_only_score_simulation_design_summary.json",
        "source_learning_matrix": "p103_outcome_only_strategy_learning_matrix_summary.json",
        "source_backtest_scorecard": "p102_outcome_only_strategy_backtest_scorecard_summary.json",
        "next_implementation_target": "P109 Outcome-Only Tracking Drift Snapshot"
    }
    Path("data/mlb_2026/derived/p108_outcome_only_diagnostic_tracking_report_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

if __name__ == "__main__":
    main()
