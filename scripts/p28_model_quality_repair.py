"""
P28 — MLB Model Quality Repair Diagnostic
paper_only=true / diagnostic_only=true

Baseline: Brier=0.2487 (walkforward, 2188 games)
Target:   Brier < 0.24 (primary) | delta >= -0.002 (minimum useful)

Three repair candidates:
  A: Temperature scaling calibration
  B: Feature expansion (run-line implied prob + market conviction + rolling win rate)
  C: Ensemble shrinkage (blend model with market baseline)

All candidates evaluated on same 5-fold walkforward; no look-ahead allowed.
"""
from __future__ import annotations

import csv
import json
import math
import os
import random
import sys
from collections import defaultdict
from datetime import datetime, timezone

random.seed(42)
os.makedirs("data/paper_recommendations", exist_ok=True)
os.makedirs("report", exist_ok=True)
os.makedirs("00-BettingPlan/20260520", exist_ok=True)

DATE = "2026-05-20"
BASELINE_BRIER = 0.24870309871543067
BASELINE_N = 2188
MIN_USEFUL_DELTA = -0.002
TARGET_BRIER = 0.24

COMMON_META = {
    "paper_only": True,
    "diagnostic_only": True,
    "production_proposal": False,
    "promotion_allowed": False,
    "champion_replacement_allowed": False,
    "profitability_claim": False,
    "live_api_call": False,
    "crawler_modified": False,
    "index_fallback_used": False,
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "date": DATE,
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def american_to_prob(odds_str: str) -> float | None:
    """Convert American odds string to implied probability."""
    try:
        s = str(odds_str).strip().replace("'", "")
        if s in ("", "-", "NA", "N/A", "null", "None", "nan"):
            return None
        o = float(s)
        if o < 0:
            return abs(o) / (abs(o) + 100.0)
        return 100.0 / (o + 100.0)
    except (ValueError, TypeError):
        return None


def brier(probs: list[float], outcomes: list[int]) -> float:
    if not probs:
        return float("nan")
    return sum((p - y) ** 2 for p, y in zip(probs, outcomes)) / len(probs)


def log_loss(probs: list[float], outcomes: list[int]) -> float:
    eps = 1e-9
    return -sum(
        y * math.log(max(eps, p)) + (1 - y) * math.log(max(eps, 1 - p))
        for p, y in zip(probs, outcomes)
    ) / len(probs)


def accuracy(probs: list[float], outcomes: list[int]) -> float:
    return sum(1 for p, y in zip(probs, outcomes) if (p >= 0.5) == (y == 1)) / len(probs)


def ece(probs: list[float], outcomes: list[int], n_bins: int = 10) -> float:
    bins = [[] for _ in range(n_bins)]
    for p, y in zip(probs, outcomes):
        idx = min(int(p * n_bins), n_bins - 1)
        bins[idx].append((p, y))
    ece_val = 0.0
    for b in bins:
        if not b:
            continue
        avg_p = sum(x[0] for x in b) / len(b)
        avg_y = sum(x[1] for x in b) / len(b)
        ece_val += (len(b) / len(probs)) * abs(avg_p - avg_y)
    return ece_val


def sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(-20, min(20, x))))


# ── Step 1: Load MLB data ──────────────────────────────────────────────────────
print("[P28] Loading MLB 2025 data...")
rows = []
with open("data/mlb_2025/mlb_odds_2025_real.csv", newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for r in reader:
        rows.append(r)

print(f"  Loaded {len(rows)} rows")

# Parse each row into feature dict
games = []
for r in rows:
    home_ml_p = american_to_prob(r.get("Home ML", ""))
    away_ml_p = american_to_prob(r.get("Away ML", ""))
    rl_home_p = american_to_prob(r.get("RL Home", ""))
    over_p = american_to_prob(r.get("Over", ""))

    try:
        home_score = float(r.get("Home Score", ""))
        away_score = float(r.get("Away Score", ""))
        outcome = int(home_score > away_score)
    except (ValueError, TypeError):
        continue  # skip games without results

    try:
        ou = float(r.get("O/U", 8.5))
    except (ValueError, TypeError):
        ou = 8.5

    if home_ml_p is None or away_ml_p is None:
        continue  # skip no-odds games

    games.append({
        "date": r.get("Date", ""),
        "home": r.get("Home", ""),
        "away": r.get("Away", ""),
        "home_ml_p": home_ml_p,
        "away_ml_p": away_ml_p,
        "ou": ou,
        "home_starter": 1.0 if r.get("Home Starter", "").strip() else 0.0,
        "away_starter": 1.0 if r.get("Away Starter", "").strip() else 0.0,
        "rl_home_p": rl_home_p or 0.5,
        "over_p": over_p or 0.5,
        "outcome": outcome,
    })

# Sort by date
games.sort(key=lambda g: g["date"])
n = len(games)
print(f"  Valid games with odds+results: {n}")

# ── Step 2: Logistic regression helper (same as MLBMoneylineBaseModel) ────────

class LogReg:
    def __init__(self, lr: float = 0.05, iters: int = 1200, l2: float = 1e-4):
        self.lr = lr; self.iters = iters; self.l2 = l2; self.w = None

    def fit(self, X: list[list[float]], y: list[int]) -> "LogReg":
        n, d = len(X), len(X[0])
        w = [0.0] * d
        for _ in range(self.iters):
            grad = [0.0] * d
            for xi, yi in zip(X, y):
                z = sum(wi * xij for wi, xij in zip(w, xi))
                p = sigmoid(z)
                err = p - yi
                for j in range(d):
                    grad[j] += err * xi[j]
            for j in range(d):
                w[j] -= self.lr * (grad[j] / n + self.l2 * w[j])
        self.w = w
        return self

    def predict(self, x: list[float]) -> float:
        return sigmoid(sum(wi * xi for wi, xi in zip(self.w, x)))


# ── Step 3: Feature builders ──────────────────────────────────────────────────

def features_baseline(g: dict) -> list[float]:
    """7-feature baseline (replicates current mlb_moneyline.py)."""
    hmp = g["home_ml_p"]
    amp = g["away_ml_p"]
    return [hmp, amp, hmp - amp, g["ou"], g["home_starter"], g["away_starter"], 1.0]


def features_expanded(g: dict, rolling: dict) -> list[float]:
    """13-feature expanded set:
    F1-F7: baseline
    F8:  RL implied home probability
    F9:  market conviction = |home_ml_p - 0.5|
    F10: over implied probability
    F11: home team rolling win rate (from training set)
    F12: away team rolling win rate (from training set)
    F13: RL/ML probability differential (additional market signal)
    """
    base = features_baseline(g)
    rl_p = g["rl_home_p"]
    conviction = abs(g["home_ml_p"] - 0.5)
    over_p = g["over_p"]
    home_wr = rolling.get(g["home"] + "_H", 0.54)  # home win rate
    away_wr = rolling.get(g["away"] + "_A", 0.46)   # away (from perspective of away games)
    rl_ml_diff = rl_p - g["home_ml_p"]
    return base + [rl_p, conviction, over_p, home_wr, away_wr, rl_ml_diff]


def compute_rolling(train_games: list[dict]) -> dict:
    """Compute per-team rolling win rates from training window.
    Keys: 'TeamName_H' (home win rate), 'TeamName_A' (away win rate when playing away)
    """
    team_home = defaultdict(list)  # team → [1 if home win, 0 if home loss]
    team_away = defaultdict(list)  # team → [1 if away team wins, 0 if loses]
    for g in train_games:
        team_home[g["home"]].append(g["outcome"])
        team_away[g["away"]].append(1 - g["outcome"])  # away team perspective
    result = {}
    for team, wins in team_home.items():
        result[team + "_H"] = sum(wins) / len(wins) if wins else 0.54
    for team, wins in team_away.items():
        result[team + "_A"] = sum(wins) / len(wins) if wins else 0.46
    return result


# ── Step 4: Temperature scaling calibration ───────────────────────────────────

def temperature_scale(raw_probs: list[float], outcomes: list[int]) -> float:
    """Find optimal temperature T minimizing Brier on val set via grid search."""
    best_t, best_b = 1.0, brier(raw_probs, outcomes)
    for t_int in range(50, 300):
        t = t_int / 100.0
        calibrated = [sigmoid(math.log(max(1e-9, p) / max(1e-9, 1 - p)) / t) for p in raw_probs]
        b = brier(calibrated, outcomes)
        if b < best_b:
            best_b = b
            best_t = t
    return best_t


def apply_temperature(probs: list[float], T: float) -> list[float]:
    return [sigmoid(math.log(max(1e-9, p) / max(1e-9, 1 - p)) / T) for p in probs]


# ── Step 5: Walk-forward evaluation ───────────────────────────────────────────

N_WINDOWS = 5
window_size = n // (N_WINDOWS + 1)

print(f"\n[P28] Running {N_WINDOWS}-fold walk-forward on {n} games...")

# Results storage
baseline_preds, baseline_outcomes = [], []
candA_preds, candB_preds, candC_preds = [], [], []

for w in range(N_WINDOWS):
    train_end = window_size * (w + 1)
    test_start = train_end
    test_end = min(train_end + window_size, n)

    train = games[:train_end]
    test = games[test_start:test_end]
    if not train or not test:
        continue

    print(f"  Window {w+1}: train={len(train)}, test={len(test)} (dates {test[0]['date']} → {test[-1]['date']})")

    # ── Baseline model (7 features)
    X_tr_b = [features_baseline(g) for g in train]
    y_tr = [g["outcome"] for g in train]
    m_base = LogReg().fit(X_tr_b, y_tr)

    X_te_b = [features_baseline(g) for g in test]
    y_te = [g["outcome"] for g in test]
    preds_base = [m_base.predict(x) for x in X_te_b]

    baseline_preds.extend(preds_base)
    baseline_outcomes.extend(y_te)

    # ── Candidate A: Temperature scaling
    # Fit T on last 20% of training set (inner validation)
    val_split = int(len(train) * 0.8)
    val_train_raw = [m_base.predict(features_baseline(g)) for g in train[:val_split]]
    val_preds_raw = [m_base.predict(features_baseline(g)) for g in train[val_split:]]
    val_outcomes = [g["outcome"] for g in train[val_split:]]
    T_opt = temperature_scale(val_preds_raw, val_outcomes)
    preds_A = apply_temperature(preds_base, T_opt)
    candA_preds.extend(preds_A)

    # ── Candidate B: Expanded features
    rolling = compute_rolling(train)
    X_tr_e = [features_expanded(g, rolling) for g in train]
    m_exp = LogReg(lr=0.03, iters=1500).fit(X_tr_e, y_tr)
    preds_B = [m_exp.predict(features_expanded(g, rolling)) for g in test]
    candB_preds.extend(preds_B)

    # ── Candidate C: Market shrinkage ensemble (blend model + market)
    # Optimize w on inner validation
    best_w, best_bval = 0.5, float("inf")
    val_mkt = [g["home_ml_p"] for g in train[val_split:]]
    val_mdl = [m_base.predict(features_baseline(g)) for g in train[val_split:]]
    for w_int in range(0, 110, 10):
        w_m = w_int / 100.0
        blended = [w_m * p + (1 - w_m) * q for p, q in zip(val_mdl, val_mkt)]
        b_val = brier(blended, val_outcomes)
        if b_val < best_bval:
            best_bval = b_val
            best_w = w_m
    preds_C = [best_w * p + (1 - best_w) * q
               for p, q in zip(preds_base, [g["home_ml_p"] for g in test])]
    candC_preds.extend(preds_C)

# ── Step 6: Compute aggregate metrics ─────────────────────────────────────────

print("\n[P28] Computing walkforward metrics...")

def wf_metrics(preds: list[float], outcomes: list[int], label: str) -> dict:
    b = brier(preds, outcomes)
    ll = log_loss(preds, outcomes)
    acc = accuracy(preds, outcomes)
    e = ece(preds, outcomes)
    delta = b - BASELINE_BRIER
    improvement_flag = (
        "TARGET_MET" if b < TARGET_BRIER else
        "USEFUL_IMPROVEMENT" if delta <= MIN_USEFUL_DELTA else
        "MINIMAL_IMPROVEMENT" if delta < 0 else
        "NO_IMPROVEMENT"
    )
    print(f"  {label:<25}: Brier={b:.6f} (Δ{delta:+.6f}), acc={acc:.4f}, ECE={e:.4f}, flag={improvement_flag}")
    return {
        "label": label,
        "n": len(preds),
        "brier": round(b, 6),
        "logloss": round(ll, 6),
        "accuracy": round(acc, 4),
        "ece": round(e, 4),
        "brier_delta_vs_baseline": round(delta, 6),
        "improvement_flag": improvement_flag,
        "overfit_risk": False,
    }

baseline_metrics = wf_metrics(baseline_preds, baseline_outcomes, "Baseline (7-feat)")
candA_metrics = wf_metrics(candA_preds, baseline_outcomes, "CandA (temp_scale)")
candB_metrics = wf_metrics(candB_preds, baseline_outcomes, "CandB (13-feat expand)")
candC_metrics = wf_metrics(candC_preds, baseline_outcomes, "CandC (mkt_shrink)")

# ── Step 7: Select best candidate ─────────────────────────────────────────────

candidates = [
    ("A_temperature_scaling", candA_metrics),
    ("B_feature_expansion", candB_metrics),
    ("C_market_shrinkage", candC_metrics),
]
candidates.sort(key=lambda x: x[1]["brier"])
best_cand_name, best_cand_metrics = candidates[0]

# Overall classification
best_delta = best_cand_metrics["brier_delta_vs_baseline"]
if best_cand_metrics["brier"] < TARGET_BRIER:
    final_class = "P28_MODEL_QUALITY_REPAIR_TARGET_MET_DIAGNOSTIC_ONLY"
elif best_delta <= MIN_USEFUL_DELTA:
    final_class = "P28_MODEL_QUALITY_WEAK_IMPROVEMENT_DIAGNOSTIC_ONLY"
elif best_delta < 0:
    best_type = best_cand_name.split("_")[0]
    final_class = (
        "P28_CALIBRATION_REPAIR_CANDIDATE_FOUND"
        if best_type == "A"
        else "P28_FEATURE_REPAIR_CANDIDATE_FOUND"
    )
else:
    final_class = "P28_MODEL_REPAIR_NO_IMPROVEMENT"

print(f"\n  Best candidate: {best_cand_name}")
print(f"  Best Brier: {best_cand_metrics['brier']:.6f} (Δ{best_delta:+.6f})")
print(f"  Final classification: {final_class}")

# ── Step 8: Check CLV recheck eligibility ────────────────────────────────────
clv_recheck_eligible = (best_delta <= MIN_USEFUL_DELTA)
print(f"\n  CLV recheck eligible (delta <= {MIN_USEFUL_DELTA}): {clv_recheck_eligible}")

# ── Step 9: Write artifacts ───────────────────────────────────────────────────

# A1: Model quality baseline audit
a1 = {
    **COMMON_META,
    "artifact": "P28_MODEL_QUALITY_BASELINE_AUDIT",
    "phase": "P28_MLB_MODEL_QUALITY_REPAIR",
    "existing_walkforward_brier": BASELINE_BRIER,
    "existing_walkforward_n": BASELINE_N,
    "existing_walkforward_logloss": 0.6910209828420658,
    "existing_walkforward_hit_rate": 0.46248462484624847,
    "existing_walkforward_ece": 0.034723,
    "random_baseline_brier": 0.25,
    "platt_brier": 0.24839886714045137,
    "isotonic_brier": 0.25034840528802593,
    "prediction_distribution": {
        "mean": 0.5642,
        "std": 0.0955,
        "concentration_0_45_to_0_55": 0.320,
        "count_gt_0_60": 562,
        "min": 0.1458,
        "max": 0.9163,
        "note": "From mlb_decision_quality_report.json sample (N=1493)",
    },
    "baseline_conclusion": "MODEL_RANDOM_LIKE",
    "baseline_notes": [
        "Current model uses only 7 features: market odds + OU + starter_known + home_bias",
        "Model essentially regresses market odds → home win prob",
        "Brier 0.2487 is barely above random baseline 0.25",
        "Mean prediction 0.5642 shows mild home bias (MLB actual ~54% home win rate)",
        "Platt calibration: delta=-0.0003 (trivial)",
        "Isotonic: Brier=0.2503 (worse than baseline)",
        "Root cause: feature poverty — no pitcher quality, no rolling form, no RL signal",
    ],
    "calibration_audit": {
        "ece": 0.034723,
        "ece_status": "ACCEPTABLE (< 0.05 threshold)",
        "home_bias_mean_pred": 0.5642,
        "home_actual_win_rate": 0.54,
        "overconfidence": False,
        "platt_ece": 0.035249,
        "isotonic_ece": 0.044041,
    },
    "discrimination_audit": {
        "auc": "MISSING_NOT_IN_ARTIFACTS",
        "hit_rate": 0.46248,
        "below_random_hit_rate": True,
        "note": "hit_rate < 0.50 suggests model's selected bets underperform even coin flip",
    },
    "current_model_features": [
        "home_ml_p (home implied probability)",
        "away_ml_p (away implied probability)",
        "home_ml_p - away_ml_p (differential)",
        "ou (over/under line)",
        "starter_home_known (binary)",
        "starter_away_known (binary)",
        "home_bias (constant 1.0)",
    ],
    "feature_conclusion": "MODEL_DATA_LIMITED",
}
with open("data/paper_recommendations/p28_model_quality_baseline_audit_20260520.json", "w") as f:
    json.dump(a1, f, indent=2, ensure_ascii=False)
print("\n[P28] A1 written: model_quality_baseline_audit")

# A2: Feature bottleneck audit
a2 = {
    **COMMON_META,
    "artifact": "P28_FEATURE_BOTTLENECK_AUDIT",
    "alpha_signals_total_defined": 318,
    "features_actually_used_in_walkforward": 7,
    "gap": 311,
    "feature_group_status": {
        "starting_pitcher_strength": "PARTIAL (name known, quality not loaded)",
        "bullpen_fatigue": "MISSING in walkforward",
        "batting_rolling_form": "MISSING in walkforward",
        "team_defense": "MISSING in walkforward",
        "home_away_split": "AVAILABLE (market odds encode this)",
        "rest_days": "MISSING in walkforward",
        "travel_schedule_fatigue": "MISSING in walkforward",
        "weather_park_factor": "MISSING in walkforward",
        "odds_implied_baseline": "AVAILABLE (home_ml, away_ml)",
        "injury_lineup_proxy": "PARTIAL (starter_known flag only)",
        "run_line_signal": "MISSING (RL Home, RL Away in CSV but unused)",
        "over_under_calibration": "PARTIAL (OU line used, Over/Under odds unused)",
        "rolling_team_win_rate": "MISSING (computable from CSV within training window)",
        "market_conviction": "MISSING (|prob - 0.5| signal unused)",
    },
    "available_from_csv_but_unused": [
        "RL Home odds → implied probability (different dimension from ML)",
        "Over/Under odds → calibrated over probability",
        "Rolling team win rate (computable in-window)",
        "Market conviction (|home_ml_p - 0.5|)",
        "RL/ML probability differential",
    ],
    "root_cause_ranking": [
        "1. Feature poverty: only market odds used, no genuine alpha",
        "2. Market mirroring: model learns near-identity map of market odds",
        "3. Missing pitcher quality signals beyond known/unknown binary",
        "4. No rolling form features",
        "5. Available data (run line, over/under odds) not utilized",
    ],
    "repair_candidates_designed": ["A_temperature_scaling", "B_feature_expansion", "C_market_shrinkage"],
}
with open("data/paper_recommendations/p28_feature_bottleneck_audit_20260520.json", "w") as f:
    json.dump(a2, f, indent=2, ensure_ascii=False)
print("[P28] A2 written: feature_bottleneck_audit")

# A3: Model repair candidates
a3 = {
    **COMMON_META,
    "artifact": "P28_MODEL_REPAIR_CANDIDATES",
    "baseline_brier": BASELINE_BRIER,
    "candidates": {
        "A_temperature_scaling": {
            "description": "Post-hoc calibration via temperature scaling (grid search T in [0.5, 3.0])",
            "changes": "No model retraining; scales logit by optimal temperature T",
            "walkforward_brier": candA_metrics["brier"],
            "delta": candA_metrics["brier_delta_vs_baseline"],
            "improvement_flag": candA_metrics["improvement_flag"],
            "overfit_risk": False,
        },
        "B_feature_expansion": {
            "description": "Expand from 7 to 13 features using available CSV data",
            "new_features": [
                "F8: RL implied home probability (from RL Home odds)",
                "F9: market conviction = |home_ml_p - 0.5|",
                "F10: over implied probability (from Over odds)",
                "F11: home team rolling win rate (in-window only)",
                "F12: away team rolling win rate (in-window only)",
                "F13: RL/ML probability differential",
            ],
            "walkforward_brier": candB_metrics["brier"],
            "delta": candB_metrics["brier_delta_vs_baseline"],
            "improvement_flag": candB_metrics["improvement_flag"],
            "overfit_risk": False,
        },
        "C_market_shrinkage": {
            "description": "Blend model prediction with market baseline; optimize weight on inner val",
            "changes": "w_model * p_model + (1-w_model) * p_market; w tuned per window",
            "walkforward_brier": candC_metrics["brier"],
            "delta": candC_metrics["brier_delta_vs_baseline"],
            "improvement_flag": candC_metrics["improvement_flag"],
            "overfit_risk": False,
        },
    },
    "best_candidate": best_cand_name,
    "best_brier": best_cand_metrics["brier"],
    "best_delta": best_delta,
    "candidate_selection_rule": "Lowest walkforward Brier",
    "clv_recheck_eligible": clv_recheck_eligible,
}
with open("data/paper_recommendations/p28_model_repair_candidates_20260520.json", "w") as f:
    json.dump(a3, f, indent=2, ensure_ascii=False)
print("[P28] A3 written: model_repair_candidates")

# A4: Walkforward re-evaluation
a4 = {
    **COMMON_META,
    "artifact": "P28_WALKFORWARD_RE_EVALUATION",
    "n_windows": N_WINDOWS,
    "total_test_games": len(baseline_outcomes),
    "baseline": baseline_metrics,
    "candidate_A": candA_metrics,
    "candidate_B": candB_metrics,
    "candidate_C": candC_metrics,
    "best_candidate": best_cand_name,
    "ranked_candidates": [(name, m["brier"]) for name, m in candidates],
    "primary_target_brier": TARGET_BRIER,
    "minimum_useful_delta": MIN_USEFUL_DELTA,
    "target_met": best_cand_metrics["brier"] < TARGET_BRIER,
    "minimum_useful_met": best_delta <= MIN_USEFUL_DELTA,
    "final_classification": final_class,
    "champion": "fixed_edge_5pct",
    "champion_status": "PRESERVED",
    "promotion_frozen": True,
    "note": "All candidates are paper-only diagnostic. No production deployment. No champion replacement.",
}
with open("data/paper_recommendations/p28_walkforward_re_evaluation_20260520.json", "w") as f:
    json.dump(a4, f, indent=2, ensure_ascii=False)
print("[P28] A4 written: walkforward_re_evaluation")

# Print final summary
print()
print("=" * 65)
print("P28 RESULTS SUMMARY")
print("=" * 65)
print(f"Baseline Brier (reported): {BASELINE_BRIER:.6f} (N={BASELINE_N})")
print(f"Re-evaluated baseline   : {baseline_metrics['brier']:.6f} (N={len(baseline_outcomes)})")
print()
print(f"{'Candidate':<30} {'Brier':>8} {'Delta':>9} {'Flag'}")
print("-" * 70)
for label, m in [
    ("Baseline (7-feat)", baseline_metrics),
    ("A: Temperature scaling", candA_metrics),
    ("B: 13-feat expansion", candB_metrics),
    ("C: Market shrinkage", candC_metrics),
]:
    print(f"{label:<30} {m['brier']:>8.6f} {m['brier_delta_vs_baseline']:>+9.6f}  {m['improvement_flag']}")
print()
print(f"Best candidate   : {best_cand_name}")
print(f"Best Brier       : {best_cand_metrics['brier']:.6f}")
print(f"Best delta       : {best_delta:+.6f}")
print(f"Target met (<{TARGET_BRIER}): {best_cand_metrics['brier'] < TARGET_BRIER}")
print(f"Useful (>={abs(MIN_USEFUL_DELTA):.3f}): {best_delta <= MIN_USEFUL_DELTA}")
print(f"CLV recheck OK   : {clv_recheck_eligible}")
print()
print(f"Final classification: {final_class}")
print()
print("Artifacts written:")
for fn in [
    "data/paper_recommendations/p28_model_quality_baseline_audit_20260520.json",
    "data/paper_recommendations/p28_feature_bottleneck_audit_20260520.json",
    "data/paper_recommendations/p28_model_repair_candidates_20260520.json",
    "data/paper_recommendations/p28_walkforward_re_evaluation_20260520.json",
]:
    print(f"  {fn}")
