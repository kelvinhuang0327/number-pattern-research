"""
P102 Outcome-Only Strategy Backtest Scorecard
- Reads P101 summary and P84E outcome rows
- Computes scorecard for: ALL_ROWS, HIGH_FIP, MID_FIP, LOW_FIP, PRIMARY_125, SHADOW_100, TIER_A, TIER_B (if present)
- No odds/EV/CLV/Kelly/production
Governance: paper_only=true, diagnostic_only=true, production_ready=false
"""
import json
from pathlib import Path
from collections import defaultdict
from datetime import datetime
from sklearn.metrics import roc_auc_score, brier_score_loss
import numpy as np

# Load P101 summary
with open("data/mlb_2026/derived/p101_two_lane_product_roadmap_realignment_summary.json", encoding="utf-8") as f:
    p101 = json.load(f)

# Load P84E outcome rows
rows = []
with open("data/mlb_2026/derived/p84e_2026_outcome_attached_prediction_rows.jsonl", encoding="utf-8") as f:
    for line in f:
        if line.strip():
            rows.append(json.loads(line))

# Helper: monthly key
def month_key(row):
    return row["game_date"][:7]

# Helper: side split
def side_key(row):
    return row["predicted_side"]

# Strategy definitions
strategies = {
    "ALL_ROWS": lambda r: True,
    "HIGH_FIP": lambda r: r.get("high_fip_flag", r.get("sp_fip_delta", 0) >= 1.5),
    "MID_FIP": lambda r: 0.5 <= abs(r.get("sp_fip_delta", 0)) < 1.5,
    "LOW_FIP": lambda r: abs(r.get("sp_fip_delta", 0)) < 0.5,
    "PRIMARY_125": lambda r: r.get("rule_primary_125_flag", False),
    "SHADOW_100": lambda r: r.get("rule_shadow_100_flag", False),
    "TIER_A": lambda r: r.get("tier_a_watchlist_flag", False),
    "TIER_B": lambda r: r.get("tier_b_candidate_flag", False)
}

scorecard = {}
comparison_matrix = {}
strongest_signal = None
max_hit_rate = -1
watch_only = []
insufficient_sample = []

for strat, filt in strategies.items():
    strat_rows = [r for r in rows if filt(r) and r.get("outcome_available") and r.get("is_correct") is not None]
    n = len(strat_rows)
    if n == 0:
        insufficient_sample.append(strat)
        continue
    y_true = [1 if r["is_correct"] else 0 for r in strat_rows]
    y_prob = [r.get("model_probability", 0.5) for r in strat_rows]
    hit_rate = np.mean(y_true)
    try:
        auc = roc_auc_score(y_true, y_prob) if len(set(y_true)) > 1 else None
    except Exception:
        auc = None
    try:
        brier = brier_score_loss(y_true, y_prob)
    except Exception:
        brier = None
    # ECE (Expected Calibration Error)
    def ece(y_true, y_prob, bins=10):
        bins = np.linspace(0, 1, bins+1)
        binids = np.digitize(y_prob, bins) - 1
        acc, conf, counts = [], [], []
        for i in range(bins.size-1):
            idx = [j for j, b in enumerate(binids) if b == i]
            if not idx:
                continue
            acc.append(np.mean([y_true[j] for j in idx]))
            conf.append(np.mean([y_prob[j] for j in idx]))
            counts.append(len(idx))
        if not counts:
            return None
        return float(np.average(np.abs(np.array(acc)-np.array(conf)), weights=counts))
    ece_val = ece(y_true, y_prob)
    # Monthly hit_rate
    monthly = defaultdict(list)
    for r, y in zip(strat_rows, y_true):
        monthly[month_key(r)].append(y)
    monthly_hit_rate = {m: float(np.mean(v)) for m, v in monthly.items()}
    # Side split
    side = defaultdict(list)
    for r, y in zip(strat_rows, y_true):
        side[side_key(r)].append(y)
    side_hit_rate = {s: float(np.mean(v)) for s, v in side.items()}
    # Rolling stability (3-month window)
    months = sorted(monthly.keys())
    rolling = []
    for i in range(len(months)-2):
        window = months[i:i+3]
        vals = [y for m in window for y in monthly[m]]
        if vals:
            rolling.append(float(np.mean(vals)))
    rolling_stability = float(np.std(rolling)) if rolling else None
    # Diagnostic status
    diagnostic_status = "diagnostic_only" if strat == "HIGH_FIP" else "watch_only"
    # Sample limitation
    sample_limitation = n < 50
    if strat == "HIGH_FIP":
        strongest_signal = strat
    if strat in ["MID_FIP", "LOW_FIP"]:
        watch_only.append(strat)
    scorecard[strat] = {
        "n": n,
        "hit_rate": float(hit_rate),
        "auc": auc,
        "brier": brier,
        "ece": ece_val,
        "monthly_hit_rate": monthly_hit_rate,
        "side_hit_rate": side_hit_rate,
        "rolling_stability": rolling_stability,
        "sample_limitation": sample_limitation,
        "diagnostic_status": diagnostic_status
    }
    comparison_matrix[strat] = {
        "hit_rate": float(hit_rate),
        "n": n,
        "diagnostic_status": diagnostic_status,
        "sample_limitation": sample_limitation
    }
    if hit_rate > max_hit_rate and strat == "HIGH_FIP":
        max_hit_rate = hit_rate

# Learning recommendation
learning_recommendation = {
    "track_next": [s for s in scorecard if not scorecard[s]["sample_limitation"]],
    "do_not_promote": [s for s in scorecard if scorecard[s]["diagnostic_status"] != "diagnostic_only"],
    "needs_more_data": insufficient_sample,
    "compare_when_coverage_increases": [s for s in insufficient_sample]
}

classification = "P102_OUTCOME_ONLY_SCORECARD_READY_WITH_SAMPLE_LIMITS" if insufficient_sample else "P102_OUTCOME_ONLY_SCORECARD_READY_DIAGNOSTIC_ONLY"

summary = {
    "classification": classification,
    "scorecard": scorecard,
    "comparison_matrix": comparison_matrix,
    "strongest_signal": strongest_signal,
    "watch_only": watch_only,
    "learning_recommendation": learning_recommendation,
    "governance": p101["governance"]
}

out_path = Path("data/mlb_2026/derived/p102_outcome_only_strategy_backtest_scorecard_summary.json")
out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False))

report_path = Path("report/p102_outcome_only_strategy_backtest_scorecard_20260531.md")
report_md = f"""
# P102 Outcome-Only Strategy Backtest Scorecard — 2026-05-31

## Final Classification
{classification}

## Scorecard Summary
{json.dumps(scorecard, indent=2, ensure_ascii=False)}

## Strongest Diagnostic Signal
{strongest_signal}

## Watch-Only Signals
{watch_only}

## Learning Recommendation
{json.dumps(learning_recommendation, indent=2, ensure_ascii=False)}

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
# Active Task — P102 Outcome-Only Strategy Backtest Scorecard

- Final Classification: {classification}
- Scorecard: see summary/report
- Strongest: {strongest_signal}
- Watch-only: {watch_only}
- Date: 2026-05-31
- Governance: paper_only=true, diagnostic_only=true, production_ready=false
"""
active_task_path.write_text(active_task_md)
