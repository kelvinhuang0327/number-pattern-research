"""
P103 Outcome-Only Strategy Learning Matrix

- 依據 P102 outcome-only scorecard，產生策略學習矩陣。
- 僅允許 diagnostic/tracking，禁止 production/recommendation。
- 所有治理旗標皆需合規。
"""
import json
from pathlib import Path

P102_SCORECARD_PATH = Path("data/mlb_2026/derived/p102_outcome_only_strategy_backtest_scorecard_summary.json")
P103_MATRIX_PATH = Path("data/mlb_2026/derived/p103_outcome_only_strategy_learning_matrix_summary.json")
REPORT_PATH = Path("report/p103_outcome_only_strategy_learning_matrix_20260531.md")

# 載入 P102 scorecard
with P102_SCORECARD_PATH.open() as f:
    p102 = json.load(f)

scorecard = p102["scorecard"]
comparison_matrix = p102.get("comparison_matrix", {})
strongest_signal = p102.get("strongest_signal", "HIGH_FIP")
watch_only = set(p102.get("watch_only", []))
governance = p102.get("governance", {})

# 定義學習矩陣
matrix = []
for strat, stats in scorecard.items():
    entry = {
        "strategy_id": strat,
        "strategy_name": strat,
        "segment_type": strat,
        "n": stats["n"],
        "hit_rate": stats["hit_rate"],
        "auc": stats.get("auc"),
        "brier": stats.get("brier"),
        "ece": stats.get("ece"),
        "monthly_stability": stats.get("monthly_hit_rate"),
        "side_split_status": stats.get("side_hit_rate"),
        "rolling_stability": stats.get("rolling_stability"),
        "sample_status": "SAMPLE_LIMITED" if stats.get("sample_limitation") else "OK",
        "current_decision": None,
        "next_learning_action": None
    }
    # 決策分配
    if strat == "HIGH_FIP":
        entry["current_decision"] = "TRACK_DIAGNOSTIC"
        entry["next_learning_action"] = "Continue diagnostic tracking; do not promote"
    elif strat in ("MID_FIP", "LOW_FIP"):
        entry["current_decision"] = "WATCH_ONLY"
        entry["next_learning_action"] = "Monitor for stability; do not promote"
    else:
        entry["current_decision"] = "WATCH_ONLY"
        entry["next_learning_action"] = "Monitor; do not promote"
    matrix.append(entry)

# 學習循環定義
learning_loop = {
    "metric": "hit_rate, auc, brier, ece, monthly_stability",
    "re_evaluation_trigger": "+100 new samples or monthly",
    "data_threshold": 200,
    "allowed_next_action": "TRACK_DIAGNOSTIC or WATCH_ONLY",
    "prohibited_action": "No production, recommendation, or odds/EV/CLV/Kelly logic"
}

final_classification = "P103_STRATEGY_LEARNING_MATRIX_READY_DIAGNOSTIC_ONLY"

# 輸出 summary JSON
summary = {
    "date": "2026-05-31",
    "final_classification": final_classification,
    "matrix": matrix,
    "strongest_signal": strongest_signal,
    "watch_only": list(watch_only),
    "learning_loop": learning_loop,
    "governance": governance
}
with P103_MATRIX_PATH.open("w") as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)

# 產生報告 markdown
with REPORT_PATH.open("w") as f:
    f.write(f"# P103 Outcome-Only Strategy Learning Matrix — 2026-05-31\n\n")
    f.write(f"## Final Classification\n{final_classification}\n\n")
    f.write(f"## Strongest Diagnostic Signal\n{strongest_signal}\n\n")
    f.write(f"## Watch-Only or Sample-Limited Signals\n{', '.join(watch_only)}\n\n")
    f.write(f"## Learning Matrix\n\n")
    for entry in matrix:
        f.write(f"- {entry['strategy_id']}: {entry['current_decision']} | n={entry['n']} | hit_rate={entry['hit_rate']:.3f}\n")
    f.write(f"\n## Learning Loop\n{json.dumps(learning_loop, ensure_ascii=False, indent=2)}\n\n")
    f.write(f"## Governance\n{json.dumps(governance, ensure_ascii=False, indent=2)}\n")
