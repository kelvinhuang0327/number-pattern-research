"""
P105 Outcome-Only Win/Loss and Score Simulation Runner
診斷專用，僅產生 win/loss、side accuracy、monthly accuracy、score margin 分析
明確阻擋 betting/EV/CLV/Kelly/production 相關模組
"""
import json
from pathlib import Path
from collections import defaultdict, Counter
from statistics import mean, median

# --- 輔助函數 ---
def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def load_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]

def score_margin_bucket(margin):
    if margin >= 10:
        return ">=10"
    elif margin >= 5:
        return "5-9"
    elif margin >= 3:
        return "3-4"
    elif margin >= 1:
        return "1-2"
    elif margin == 0:
        return "0"
    elif margin <= -10:
        return "<=-10"
    elif margin <= -5:
        return "-9--5"
    elif margin <= -3:
        return "-4--3"
    elif margin <= -1:
        return "-2--1"
    else:
        return "other"

# --- 主 runner ---
def main():
    # 載入 artifacts
    p104 = load_json("data/mlb_2026/derived/p104_outcome_only_score_simulation_design_summary.json")
    p103 = load_json("data/mlb_2026/derived/p103_outcome_only_strategy_learning_matrix_summary.json")
    p102 = load_json("data/mlb_2026/derived/p102_outcome_only_strategy_backtest_scorecard_summary.json")
    p84e = load_jsonl("data/mlb_2026/derived/p84e_2026_outcome_attached_prediction_rows.jsonl")

    # 取得所有策略
    strategies = {}
    for s in p103["matrix"]:
        strategies[s["strategy_id"]] = s
    # 兼容 PRIMARY_125, SHADOW_100, TIER_A, TIER_B
    extra_ids = ["PRIMARY_125", "SHADOW_100", "TIER_A", "TIER_B"]
    for eid in extra_ids:
        if eid not in strategies:
            for s in p103["matrix"]:
                if s["strategy_id"].startswith(eid):
                    strategies[eid] = s
    # 產生策略列表
    strategy_ids = [k for k in strategies.keys() if k in ["ALL_ROWS", "HIGH_FIP", "MID_FIP", "LOW_FIP", "PRIMARY_125", "SHADOW_100", "TIER_A", "TIER_B"]]
    # 若有其他策略也納入
    for k in strategies.keys():
        if k not in strategy_ids:
            strategy_ids.append(k)

    # 分群
    def eligible(row, sid):
        # 依 flag 判斷
        if sid == "ALL_ROWS":
            return True
        if sid == "HIGH_FIP":
            return row.get("sp_fip_delta", 0) > 1.0
        if sid == "MID_FIP":
            return 0.5 < abs(row.get("sp_fip_delta", 0)) <= 1.0
        if sid == "LOW_FIP":
            return abs(row.get("sp_fip_delta", 0)) <= 0.5
        if sid == "PRIMARY_125":
            return row.get("rule_primary_125_flag", False)
        if sid == "SHADOW_100":
            return row.get("rule_shadow_100_flag", False)
        if sid == "TIER_A":
            return row.get("tier_a_watchlist_flag", False)
        if sid == "TIER_B":
            return row.get("tier_b_candidate_flag", False)
        return False

    results = {}
    for sid in strategy_ids:
        rows = [r for r in p84e if eligible(r, sid)]
        if not rows:
            continue
        wins = sum(1 for r in rows if r["is_correct"])
        losses = sum(1 for r in rows if not r["is_correct"])
        hit_rate = wins / len(rows) if rows else None
        home_pred = sum(1 for r in rows if r["predicted_side"] == "home")
        away_pred = sum(1 for r in rows if r["predicted_side"] == "away")
        side_split = {
            "home": sum(1 for r in rows if r["predicted_side"] == "home" and r["is_correct"])/home_pred if home_pred else None,
            "away": sum(1 for r in rows if r["predicted_side"] == "away" and r["is_correct"])/away_pred if away_pred else None,
        }
        # 月份分組
        monthly = defaultdict(lambda: {"n":0, "wins":0})
        for r in rows:
            month = r["game_date"][:7]
            monthly[month]["n"] += 1
            if r["is_correct"]:
                monthly[month]["wins"] += 1
        monthly_acc = {m: v["wins"]/v["n"] if v["n"] else None for m,v in monthly.items()}
        # 分析分數差
        # 僅納入有分數資料的場次
        valid_rows = [r for r in rows if r.get("result_home_score") is not None and r.get("result_away_score") is not None]
        margins = [(r["result_home_score"] - r["result_away_score"]) if r["predicted_side"]=="home" else (r["result_away_score"] - r["result_home_score"]) for r in valid_rows]
        avg_margin = mean(margins) if margins else None
        med_margin = median(margins) if margins else None
        margin_buckets = dict(Counter([score_margin_bucket(m) for m in margins]))
        # 狀態
        sample_status = strategies[sid].get("sample_status", "N/A") if sid in strategies else "N/A"
        diagnostic_status = strategies[sid].get("current_decision", "N/A") if sid in strategies else "N/A"
        results[sid] = {
            "strategy_id": sid,
            "strategy_name": strategies[sid]["strategy_name"] if sid in strategies else sid,
            "eligible_rows": len(rows),
            "wins": wins,
            "losses": losses,
            "hit_rate": hit_rate,
            "home_predicted_count": home_pred,
            "away_predicted_count": away_pred,
            "side_split_accuracy": side_split,
            "monthly_accuracy": monthly_acc,
            "average_score_margin": avg_margin,
            "median_score_margin": med_margin,
            "score_margin_buckets": margin_buckets,
            "sample_status": sample_status,
            "diagnostic_status": diagnostic_status,
        }

    # --- Governance & Blocked 模組 ---
    governance = p104["governance"]
    blocked_simulations = p104["blocked_simulations"]
    supported_simulations = p104["supported_simulations"]
    final_classification = "P105_SCORE_SIMULATION_RUNNER_READY_DIAGNOSTIC_ONLY"
    summary = {
        "date": "2026-05-31",
        "final_classification": final_classification,
        "supported_simulations": supported_simulations,
        "blocked_simulations": blocked_simulations,
        "governance": governance,
        "strategies": results,
        "note": "診斷專用，未計算任何 betting/EV/CLV/Kelly/production 相關模組。",
        "next_implementation_target": "P106 Outcome-Only Simulation Review and Strategy Adjustment Plan"
    }
    out_path = Path("data/mlb_2026/derived/p105_outcome_only_score_simulation_runner_summary.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"[P105] Score simulation runner summary written: {out_path}")

if __name__ == "__main__":
    main()
