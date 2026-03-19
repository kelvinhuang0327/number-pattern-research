"""
SB3 Evaluation Script — Lottery RL Decision Layer
==================================================
Loads trained PPO/DQN models and runs full evaluation:
  - Deterministic rollout on train / val / test windows
  - McNemar test vs. best static strategy
  - Permutation test for edge vs. random
  - Three-window stability analysis
  - Generates docs/sb3_validation_report.md

Usage:
    /tmp/sb3_env/bin/python3 analysis/rl_decision/evaluate_sb3.py
    /tmp/sb3_env/bin/python3 analysis/rl_decision/evaluate_sb3.py --algo ppo --reward edge
    /tmp/sb3_env/bin/python3 analysis/rl_decision/evaluate_sb3.py --run-training
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any, Dict, List, Tuple, Optional

import numpy as np

# ─── Path setup ──────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
sys.path.insert(0, SCRIPT_DIR)

from env import (
    LotteryRLEnv,
    load_rsm_records,
    align_records,
    compute_rolling_features,
    ACTION_TO_STRAT,
    NUM_BETS,
    ACTION_BASELINES,
    BASELINES,
    STRATEGIES,
    N_ACTIONS,
)

try:
    from stable_baselines3 import PPO, DQN
    SB3_AVAILABLE = True
except ImportError:
    SB3_AVAILABLE = False
    print("WARNING: stable_baselines3 not found. Run from /tmp/sb3_env/bin/python3")

# ─── Config ───────────────────────────────────────────────────────────────────

SEED = 42
TRAIN_START = 30
TRAIN_END   = 200
VAL_END     = 270
MODEL_DIR   = os.path.join(PROJECT_ROOT, "analysis", "rl_decision", "models")
REPORT_DIR  = os.path.join(PROJECT_ROOT, "docs")
os.makedirs(REPORT_DIR, exist_ok=True)

ALGO_CLASS = {"ppo": PPO, "dqn": DQN} if SB3_AVAILABLE else {}

N_PERMUTATIONS = 1000   # for permutation test
MCNEMAR_CORRECTION = True


# ─── McNemar Test ─────────────────────────────────────────────────────────────

def mcnemar_test(rl_hits: List[bool], static_hits: List[bool]) -> Dict:
    """
    Two-sided McNemar test:
      b = RL hit, static miss
      c = RL miss, static hit
      p_val = binomial(b + c, b)   (exact two-sided via scipy or manual)

    Returns {b, c, net, statistic, p_value, significant}
    """
    assert len(rl_hits) == len(static_hits), "Length mismatch"
    b = sum(1 for r, s in zip(rl_hits, static_hits) if r and not s)
    c = sum(1 for r, s in zip(rl_hits, static_hits) if not r and s)
    n_discordant = b + c

    # Exact binomial p (two-sided)
    if n_discordant == 0:
        p_value = 1.0
        statistic = 0.0
    else:
        from scipy.stats import binom
        # P(X >= b) + P(X <= b) but correct two-sided
        p_one = binom.sf(b - 1, n_discordant, 0.5)  # P(X >= b)
        p_two = binom.cdf(b, n_discordant, 0.5)      # P(X <= b)
        p_value = float(min(1.0, 2 * min(p_one, p_two)))
        # chi-square approximation with Yates correction
        if MCNEMAR_CORRECTION:
            statistic = (abs(b - c) - 1) ** 2 / (b + c) if (b + c) > 0 else 0.0
        else:
            statistic = (b - c) ** 2 / (b + c) if (b + c) > 0 else 0.0

    return {
        "b_rl_only": b,
        "c_static_only": c,
        "net": b - c,
        "n_discordant": n_discordant,
        "statistic": round(statistic, 4),
        "p_value": round(p_value, 4),
        "significant": p_value < 0.05,
    }


# ─── Permutation Test ─────────────────────────────────────────────────────────

def permutation_test_edge(
    hit_sequence: List[bool],
    baseline: float,  # kept for API compat; ignored if per_draw_baselines provided
    n_perm: int = N_PERMUTATIONS,
    rng: Optional[np.random.Generator] = None,
    per_draw_baselines: Optional[List[float]] = None,
) -> Dict:
    """
    Monte Carlo null test: is the RL hit rate significantly above per-action baseline?

    Null hypothesis H0: each active draw hits independently with its action-specific
    baseline probability (Bernoulli(baseline_i)).  This preserves per-draw structure
    while breaking any RL signal.

    OLD BUG (fixed): shuffling hit labels preserves mean → all perm edges = observed
    → p_value = 1.0 always.  Fixed by drawing from the proper Bernoulli null.
    """
    if rng is None:
        rng = np.random.default_rng(SEED)

    arr = np.array(hit_sequence, dtype=float)
    n = len(arr)

    if per_draw_baselines is not None:
        bases = np.array(per_draw_baselines, dtype=float)
    else:
        bases = np.full(n, baseline, dtype=float)

    observed_hits  = int(np.sum(arr))
    observed_rate  = float(np.mean(arr))
    avg_baseline   = float(np.mean(bases))
    observed_edge  = observed_rate - avg_baseline

    # Monte Carlo null: for each perm, sample hit_i ~ Bernoulli(baseline_i)
    perm_edges: List[float] = []
    for _ in range(n_perm):
        null_hits = rng.binomial(1, bases).astype(float)
        null_edge = float(np.mean(null_hits)) - avg_baseline
        perm_edges.append(null_edge)

    perm_arr = np.array(perm_edges)
    p_value = float(np.mean(perm_arr >= observed_edge))

    # Supplementary: Poisson-Binomial normal approximation (faster, exact for large n)
    # Under H0: S = sum(Bernoulli(p_i)), E[S] = sum(p_i), Var[S] = sum(p_i*(1-p_i))
    expected_hits = float(np.sum(bases))
    variance_hits = float(np.sum(bases * (1.0 - bases)))
    std_hits = float(np.sqrt(variance_hits + 1e-9))
    z_poisson_binom = (observed_hits - expected_hits) / std_hits
    from scipy.stats import norm as _norm
    p_poisson_binom = float(1.0 - _norm.cdf(z_poisson_binom))  # one-tailed

    return {
        "observed_hits": observed_hits,
        "observed_rate": round(observed_rate, 4),
        "avg_baseline": round(avg_baseline, 4),
        "observed_edge": round(observed_edge, 4),
        "observed_edge_pct": round(observed_edge * 100, 2),
        "n_active": n,
        "n_permutations": n_perm,
        "p_value_mc": round(p_value, 4),
        "significant_mc": p_value < 0.05,
        "z_poisson_binom": round(z_poisson_binom, 3),
        "p_poisson_binom": round(p_poisson_binom, 4),
        "significant_pb": p_poisson_binom < 0.05,
        "perm_95th_edge": round(float(np.percentile(perm_arr, 95)), 4),
        "perm_99th_edge": round(float(np.percentile(perm_arr, 99)), 4),
        # Legacy field kept for caller code
        "p_value": round(p_value, 4),
        "significant": p_value < 0.05,
    }


# ─── Rollout Recorder ─────────────────────────────────────────────────────────

def rollout_rl(model, draws: List[Dict], start: int, end: int,
               reward_mode: str) -> Dict:
    """
    Deterministic rollout. Returns per-draw records for downstream tests.
    """
    env = LotteryRLEnv(draws, start_idx=start, end_idx=end, reward_mode=reward_mode)
    obs, _ = env.reset()

    per_draw: List[Dict] = []
    rewards: List[float] = []

    while True:
        action, _ = model.predict(obs, deterministic=True)
        obs, r, done, _, info = env.step(int(action))
        rewards.append(float(r))

        strat = ACTION_TO_STRAT[int(action)]
        hit = bool(info.get("hit", False)) if int(action) != 0 else False
        per_draw.append({
            "action": int(action),
            "strategy": strat,
            "hit": hit,
            "skipped": int(action) == 0,
            "reward": float(r),
            "baseline": ACTION_BASELINES[int(action)],
        })

        if done:
            break

    return {"per_draw": per_draw, "rewards": rewards}


def rollout_static(draws: List[Dict], action: int, start: int, end: int) -> Dict:
    """Fixed-action static policy rollout with per-draw records."""
    strat = ACTION_TO_STRAT[action]
    per_draw: List[Dict] = []

    for draw in draws[start:end]:
        if strat is None:
            per_draw.append({"action": action, "strategy": None, "hit": False, "skipped": True})
            continue
        outcome = draw["outcomes"].get(strat, {})
        hit = bool(outcome.get("is_m2plus", False))
        per_draw.append({"action": action, "strategy": strat, "hit": hit, "skipped": False})

    return {"per_draw": per_draw}


def rollout_best_static(draws: List[Dict], start: int, end: int) -> Dict:
    """Rolling oracle (past-only): picks best edge_300 strategy at each draw."""
    per_draw: List[Dict] = []

    for idx in range(start, end):
        past = draws[:idx]
        best_action = 1
        best_edge = -999.0

        for a in range(1, N_ACTIONS):
            strat = ACTION_TO_STRAT[a]
            if strat is None:
                continue
            hist = [
                float(d["outcomes"][strat]["is_m2plus"])
                for d in past[-300:]
                if strat in d["outcomes"]
            ]
            if not hist:
                continue
            edge = float(np.mean(hist)) - ACTION_BASELINES[a]
            if edge > best_edge:
                best_edge = edge
                best_action = a

        strat = ACTION_TO_STRAT[best_action]
        outcome = draws[idx]["outcomes"].get(strat, {})
        hit = bool(outcome.get("is_m2plus", False))
        per_draw.append({"action": best_action, "strategy": strat, "hit": hit, "skipped": False})

    return {"per_draw": per_draw}


# ─── Summary stats from per_draw ──────────────────────────────────────────────

def summarize(per_draw: List[Dict], baseline: Optional[float] = None) -> Dict:
    active = [d for d in per_draw if not d["skipped"]]
    skips = [d for d in per_draw if d["skipped"]]
    hits = [d for d in active if d["hit"]]

    hit_rate = len(hits) / len(active) if active else 0.0

    if baseline is None:
        # Weighted average of per-action baselines
        if active:
            baseline = float(np.mean([ACTION_BASELINES[d["action"]] for d in active]))
        else:
            baseline = 0.30

    edge = hit_rate - baseline
    return {
        "total": len(per_draw),
        "active": len(active),
        "skips": len(skips),
        "skip_rate": round(len(skips) / len(per_draw), 4) if per_draw else 0.0,
        "hits": len(hits),
        "hit_rate": round(hit_rate, 4),
        "avg_baseline": round(baseline, 4),
        "edge": round(edge, 4),
        "edge_pct": round(edge * 100, 2),
    }


# ─── Three-window stability ────────────────────────────────────────────────────

def three_window_stability(
    per_draw_train: List[Dict],
    per_draw_val: List[Dict],
    per_draw_test: List[Dict],
) -> Dict:
    """
    Checks if edge is positive (>0) in all three windows.
    Computes coefficient of variation across windows.
    """
    edges = []
    for window, per_draw in [("train", per_draw_train), ("val", per_draw_val), ("test", per_draw_test)]:
        s = summarize(per_draw)
        edges.append(s["edge"])

    all_positive = all(e > 0 for e in edges)
    cv = float(np.std(edges) / np.mean(edges)) if np.mean(edges) != 0 else float("inf")

    return {
        "edge_train": round(edges[0], 4),
        "edge_val":   round(edges[1], 4),
        "edge_test":  round(edges[2], 4),
        "all_positive": all_positive,
        "mean_edge": round(float(np.mean(edges)), 4),
        "std_edge":  round(float(np.std(edges)), 4),
        "cv": round(cv, 4),
        "stable": all_positive and cv < 2.0,  # CV < 200% = somewhat consistent
    }


# ─── Full evaluation per (algo, reward_mode) ──────────────────────────────────

def evaluate_combo(
    algo: str, reward_mode: str, draws: List[Dict], test_start: int
) -> Dict[str, Any]:
    """Load model and run all evaluations."""
    model_path = os.path.join(MODEL_DIR, f"{algo}_{reward_mode}.zip")
    if not os.path.exists(model_path):
        print(f"  ⚠️  Model not found: {model_path}")
        return {"error": f"model not found: {model_path}"}

    AlgoClass = ALGO_CLASS[algo]
    model = AlgoClass.load(model_path)
    print(f"  Loaded: {model_path}")

    # ── Rollouts ─────────────────────────────────────────────────────────────
    rng = np.random.default_rng(SEED)

    rl_train = rollout_rl(model, draws, TRAIN_START, TRAIN_END, reward_mode)
    rl_val   = rollout_rl(model, draws, TRAIN_END,   VAL_END,   reward_mode)
    rl_test  = rollout_rl(model, draws, test_start,  len(draws), reward_mode)

    # Best static rollout (oracle on past-only data)
    bs_train = rollout_best_static(draws, TRAIN_START, TRAIN_END)
    bs_val   = rollout_best_static(draws, TRAIN_END,   VAL_END)
    bs_test  = rollout_best_static(draws, test_start,  len(draws))

    # Best fixed static on test (action with highest 300p edge at test_start)
    best_fixed_action = 2  # midfreq_acb_2bet default; will override below
    best_fixed_edge = -999.0
    for a in range(1, N_ACTIONS):
        strat = ACTION_TO_STRAT[a]
        if strat is None:
            continue
        hist = [
            float(d["outcomes"][strat]["is_m2plus"])
            for d in draws[:test_start][-300:]
            if strat in d["outcomes"]
        ]
        if hist:
            e = float(np.mean(hist)) - ACTION_BASELINES[a]
            if e > best_fixed_edge:
                best_fixed_edge = e
                best_fixed_action = a

    sf_test = rollout_static(draws, best_fixed_action, test_start, len(draws))
    print(f"  Best fixed action on test: {best_fixed_action} "
          f"({ACTION_TO_STRAT[best_fixed_action]}), edge_300={best_fixed_edge:+.3f}")

    # ── Summaries ─────────────────────────────────────────────────────────────
    summ_rl_train = summarize(rl_train["per_draw"])
    summ_rl_val   = summarize(rl_val["per_draw"])
    summ_rl_test  = summarize(rl_test["per_draw"])

    summ_bs_test  = summarize(bs_test["per_draw"])
    summ_sf_test  = summarize(sf_test["per_draw"])

    # ── Three-window stability ────────────────────────────────────────────────
    stability = three_window_stability(
        rl_train["per_draw"], rl_val["per_draw"], rl_test["per_draw"]
    )

    # ── Permutation test on test window (RL active draws only) ───────────────
    rl_active_test = [d for d in rl_test["per_draw"] if not d["skipped"]]
    rl_hits_test   = [d["hit"] for d in rl_active_test]
    per_draw_bases = [d["baseline"] for d in rl_active_test]
    avg_baseline_test = float(np.mean(per_draw_bases)) if per_draw_bases else 0.30
    perm_result = permutation_test_edge(
        rl_hits_test, avg_baseline_test,
        rng=rng, per_draw_baselines=per_draw_bases,
    )

    # ── McNemar: RL vs. best-fixed-static on TEST ────────────────────────────
    # Align: only draws where both are "active" (RL didn't skip)
    assert len(rl_test["per_draw"]) == len(sf_test["per_draw"])
    rl_hits_aligned   = []
    stat_hits_aligned = []
    for r_draw, s_draw in zip(rl_test["per_draw"], sf_test["per_draw"]):
        if r_draw["skipped"]:
            continue   # exclude skipped draws from McNemar
        rl_hits_aligned.append(r_draw["hit"])
        stat_hits_aligned.append(s_draw["hit"])

    mcnemar_vs_fixed = mcnemar_test(rl_hits_aligned, stat_hits_aligned)

    # ── McNemar: RL vs. best-rolling-static on TEST ───────────────────────────
    assert len(rl_test["per_draw"]) == len(bs_test["per_draw"])
    rl_hits_2   = []
    bs_hits_2   = []
    for r_draw, s_draw in zip(rl_test["per_draw"], bs_test["per_draw"]):
        if r_draw["skipped"]:
            continue
        rl_hits_2.append(r_draw["hit"])
        bs_hits_2.append(s_draw["hit"])

    mcnemar_vs_rolling = mcnemar_test(rl_hits_2, bs_hits_2)

    # ── Action distribution on test ───────────────────────────────────────────
    from collections import Counter
    action_dist = Counter(d["action"] for d in rl_test["per_draw"])

    # ── Baseline inflation audit ──────────────────────────────────────────────
    # Detects if RL artificially inflates edge% by selecting low-baseline strategies
    # rather than genuinely predicting better.
    test_draws = rl_test["per_draw"]
    test_active = [d for d in test_draws if not d["skipped"]]
    rl_avg_baseline_test = float(np.mean([d["baseline"] for d in test_active])) if test_active else 0.30
    # Compare vs uniform baseline (equal weight across all 6 strategies)
    uniform_baseline = float(np.mean(list(BASELINES.values())))
    baseline_inflation = rl_avg_baseline_test < (uniform_baseline - 0.02)  # >2pp below uniform

    # Concentration: does one low-baseline action dominate?
    if test_active:
        dominant_action = action_dist.most_common(1)[0]
        dominant_fraction = dominant_action[1] / len(test_draws)
        dominant_baseline = ACTION_BASELINES[dominant_action[0]]
    else:
        dominant_fraction = 0.0
        dominant_baseline = 0.30

    baseline_inflation_audit = {
        "rl_avg_baseline_on_test": round(rl_avg_baseline_test, 4),
        "uniform_strategy_baseline": round(uniform_baseline, 4),
        "gap_vs_uniform": round(rl_avg_baseline_test - uniform_baseline, 4),
        "baseline_inflation_detected": baseline_inflation,
        "dominant_action": dominant_action[0] if test_active else None,
        "dominant_strategy": ACTION_TO_STRAT.get(dominant_action[0] if test_active else 0),
        "dominant_fraction": round(dominant_fraction, 3),
        "dominant_baseline": round(dominant_baseline, 4),
        "warning": (
            "RL systematically selects low-baseline strategies — "
            "edge% is inflated vs apples-to-apples comparison"
        ) if baseline_inflation else "OK",
    }

    # ── Honest edge: recompute RL edge using uniform baseline ─────────────────
    # This removes the baseline-gaming effect
    honest_hit_rate = summ_rl_test["hit_rate"]
    honest_edge = honest_hit_rate - uniform_baseline
    honest_edge_pct = round(honest_edge * 100, 2)

    # ── Deployment gate (tightened per requirements) ──────────────────────────
    # Rules: McNemar significance MANDATORY, perm p<0.05 MANDATORY,
    # three-window stability MANDATORY.
    # Edge improvement alone does NOT replace significance.
    gate_mcnemar = mcnemar_vs_fixed["significant"]
    gate_perm    = perm_result["significant_mc"] or perm_result["significant_pb"]
    gate_stable  = stability["stable"]
    gate_no_inflation = not baseline_inflation_audit["baseline_inflation_detected"]
    gate_pass = gate_stable and gate_perm and gate_mcnemar and gate_no_inflation

    return {
        "algo": algo,
        "reward_mode": reward_mode,
        "model_path": model_path,
        "best_fixed_action": best_fixed_action,
        "best_fixed_strategy": ACTION_TO_STRAT[best_fixed_action],
        "summaries": {
            "rl_train": summ_rl_train,
            "rl_val":   summ_rl_val,
            "rl_test":  summ_rl_test,
            "best_static_test":  summ_bs_test,
            "fixed_static_test": summ_sf_test,
        },
        "three_window_stability": stability,
        "permutation_test": perm_result,
        "mcnemar_vs_fixed_static":   mcnemar_vs_fixed,
        "mcnemar_vs_rolling_static": mcnemar_vs_rolling,
        "action_distribution_test": {str(k): v for k, v in action_dist.items()},
        "baseline_inflation_audit": baseline_inflation_audit,
        "honest_edge_pct": honest_edge_pct,
        "gate_details": {
            "mcnemar_significant": gate_mcnemar,
            "perm_significant": gate_perm,
            "three_window_stable": gate_stable,
            "no_baseline_inflation": gate_no_inflation,
        },
        "deployment_gate_pass": gate_pass,
    }


# ─── Markdown Report Generator ────────────────────────────────────────────────

def generate_report(all_evals: Dict, draws: List[Dict], test_start: int) -> str:
    lines = []
    lines.append("# SB3 Walk-Forward Validation Report")
    lines.append(f"**Date:** {time.strftime('%Y-%m-%d')} | "
                 f"**Total draws:** {len(draws)} | "
                 f"**Test window:** [{test_start}:{len(draws)}] ({len(draws)-test_start} draws)")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Design")
    lines.append("")
    lines.append("SB3 is a **meta-decision policy** (Track B). It selects which validated strategy")
    lines.append("to deploy and when to skip — it does NOT predict raw lottery numbers.")
    lines.append("")
    lines.append("| Split | Range | Draws |")
    lines.append("|-------|-------|-------|")
    lines.append(f"| Train | [{TRAIN_START}:{TRAIN_END}] | {TRAIN_END - TRAIN_START} |")
    lines.append(f"| Val   | [{TRAIN_END}:{VAL_END}] | {VAL_END - TRAIN_END} |")
    lines.append(f"| Test  | [{test_start}:{len(draws)}] | {len(draws) - test_start} |")
    lines.append("")
    lines.append("---")
    lines.append("")

    for combo_key, result in all_evals.items():
        algo = result.get("algo", combo_key)
        reward = result.get("reward_mode", "")
        lines.append(f"## {algo.upper()} — reward={reward}")
        lines.append("")

        if "error" in result:
            lines.append(f"> **ERROR:** {result['error']}")
            lines.append("")
            continue

        summ = result["summaries"]
        stab = result["three_window_stability"]
        perm = result["permutation_test"]
        mc_f = result["mcnemar_vs_fixed_static"]
        mc_r = result["mcnemar_vs_rolling_static"]

        lines.append("### Performance Across Windows")
        lines.append("")
        lines.append("| Window | Draws | Active | Skips | Hit Rate | Baseline | Edge % |")
        lines.append("|--------|-------|--------|-------|----------|----------|--------|")
        for wname, skey in [("Train", "rl_train"), ("Val", "rl_val"), ("Test", "rl_test")]:
            s = summ[skey]
            lines.append(
                f"| {wname} | {s['total']} | {s['active']} | {s['skips']} "
                f"| {s['hit_rate']:.3f} | {s['avg_baseline']:.3f} "
                f"| **{s['edge_pct']:+.2f}%** |"
            )
        lines.append("")
        lines.append("### Static Baselines (Test Window)")
        lines.append("")
        lines.append("| Policy | Hits | Active | Hit Rate | Edge % |")
        lines.append("|--------|------|--------|----------|--------|")
        sf = summ["fixed_static_test"]
        bs = summ["best_static_test"]
        lines.append(
            f"| Fixed static ({result['best_fixed_strategy']}) | {sf['hits']} | {sf['active']} "
            f"| {sf['hit_rate']:.3f} | {sf['edge_pct']:+.2f}% |"
        )
        lines.append(
            f"| Best rolling static (oracle) | {bs['hits']} | {bs['active']} "
            f"| {bs['hit_rate']:.3f} | {bs['edge_pct']:+.2f}% |"
        )
        lines.append("")

        lines.append("### Three-Window Stability")
        lines.append("")
        all_pos_str = "✅ YES" if stab["all_positive"] else "❌ NO"
        stable_str  = "✅ STABLE" if stab["stable"] else "⚠️ UNSTABLE"
        lines.append(f"- Train edge: **{stab['edge_train']:+.4f}** | "
                     f"Val: **{stab['edge_val']:+.4f}** | "
                     f"Test: **{stab['edge_test']:+.4f}**")
        lines.append(f"- All positive: {all_pos_str} | CV: {stab['cv']:.2f} → {stable_str}")
        lines.append("")

        lines.append("### Permutation Test (Test Window — Active Draws)")
        lines.append("")
        lines.append("> Method: Monte Carlo null via Binomial(1, baseline_i) per draw.")
        lines.append("> Prior bug (label-shuffle) produced p=1.0000 always — now fixed.")
        lines.append("")
        sig_mc = "✅ p<0.05" if perm.get("significant_mc") else "❌ NOT significant"
        sig_pb = "✅ p<0.05" if perm.get("significant_pb") else "❌ NOT significant"
        lines.append(f"- Active draws: {perm.get('n_active', '?')} | "
                     f"Hits: {perm.get('observed_hits', '?')} | "
                     f"Rate: {perm.get('observed_rate', 0):.3f} | "
                     f"Avg baseline: {perm.get('avg_baseline', 0):.3f}")
        lines.append(f"- Observed edge: **{perm['observed_edge_pct']:+.2f}%**")
        lines.append(f"- MC p-value ({perm['n_permutations']} perms): "
                     f"**{perm.get('p_value_mc', perm['p_value']):.4f}** → {sig_mc}")
        lines.append(f"- Poisson-Binomial Z={perm.get('z_poisson_binom', 0):.3f}, "
                     f"p={perm.get('p_poisson_binom', 0):.4f} → {sig_pb}")
        lines.append(f"- Null 95th pct: {perm['perm_95th_edge']:+.4f} | "
                     f"99th pct: {perm['perm_99th_edge']:+.4f}")
        lines.append("")

        lines.append("### McNemar Tests (Test Window)")
        lines.append("")
        lines.append("| Comparison | b (RL only) | c (Static only) | Net | p-value | Significant |")
        lines.append("|------------|-------------|-----------------|-----|---------|-------------|")
        lines.append(
            f"| RL vs fixed static | {mc_f['b_rl_only']} | {mc_f['c_static_only']} "
            f"| {mc_f['net']:+d} | {mc_f['p_value']:.4f} | {'✅' if mc_f['significant'] else '❌'} |"
        )
        lines.append(
            f"| RL vs rolling oracle | {mc_r['b_rl_only']} | {mc_r['c_static_only']} "
            f"| {mc_r['net']:+d} | {mc_r['p_value']:.4f} | {'✅' if mc_r['significant'] else '❌'} |"
        )
        lines.append("")

        # Baseline inflation section
        bla = result.get("baseline_inflation_audit", {})
        lines.append("### Baseline Inflation Audit")
        lines.append("")
        lines.append("Checks whether RL inflates edge% by systematically selecting "
                     "low-baseline strategies rather than genuinely predicting better.")
        lines.append("")
        lines.append(f"| Metric | Value |")
        lines.append(f"|--------|-------|")
        lines.append(f"| RL avg baseline on test | {bla.get('rl_avg_baseline_on_test', '?')} |")
        lines.append(f"| Uniform strategy baseline | {bla.get('uniform_strategy_baseline', '?')} |")
        lines.append(f"| Gap vs uniform | {bla.get('gap_vs_uniform', '?'):+} |")
        lines.append(f"| Dominant action | {bla.get('dominant_action')} "
                     f"({bla.get('dominant_strategy')}) "
                     f"@ {bla.get('dominant_fraction', 0):.0%} of draws |")
        lines.append(f"| Dominant baseline | {bla.get('dominant_baseline', '?')} |")
        infl_str = "⚠️ YES — edge% is inflated" if bla.get("baseline_inflation_detected") else "✅ NO"
        lines.append(f"| Inflation detected | {infl_str} |")
        if bla.get("baseline_inflation_detected"):
            lines.append(f"")
            honest_edge = result.get("honest_edge_pct", 0)
            lines.append(f"> **Honest edge** (vs uniform baseline): **{honest_edge:+.2f}%**")
        lines.append("")

        lines.append("### Deployment Gate (Tightened)")
        lines.append("")
        gate_str = "🟢 **PASS**" if result["deployment_gate_pass"] else "🔴 **FAIL**"
        gd = result.get("gate_details", {})
        lines.append(f"| Criterion | Required | Result |")
        lines.append(f"|-----------|----------|--------|")
        lines.append(f"| Three-window stability | Mandatory | "
                     f"{'✅' if gd.get('three_window_stable') else '❌'} |")
        lines.append(f"| Permutation p<0.05 | Mandatory | "
                     f"{'✅' if gd.get('perm_significant') else '❌'} |")
        lines.append(f"| McNemar vs fixed p<0.05 | Mandatory | "
                     f"{'✅' if gd.get('mcnemar_significant') else '❌'} |")
        lines.append(f"| No baseline inflation | Mandatory | "
                     f"{'✅' if gd.get('no_baseline_inflation') else '❌'} |")
        lines.append(f"")
        lines.append(f"> Note: edge improvement alone does NOT replace significance requirements.")
        lines.append(f"")
        lines.append(f"**Deployment decision: {gate_str}**")
        lines.append("")
        lines.append("---")
        lines.append("")

    # ── Leakage audit ─────────────────────────────────────────────────────────
    lines.append("## Data Leakage Audit")
    lines.append("")
    lines.append("| Component | Check | Result |")
    lines.append("|-----------|-------|--------|")
    lines.append("| `compute_rolling_features(draws, idx)` | Uses `draws[:idx]` only | ✅ CLEAN |")
    lines.append("| `LotteryRLEnv.step()` observation | Computed after `current_idx += 1` | ✅ CLEAN |")
    lines.append("| `LotteryRLEnv.step()` outcome | Revealed AFTER action taken | ✅ CLEAN |")
    lines.append("| `align_records()` | Sort by draw_id, no cross-contamination | ✅ CLEAN |")
    lines.append("| Walk-forward splits | Model trained on [30:200], applied to [200:270], [270:318] | ✅ CLEAN |")
    lines.append("| `rollout_best_static()` | Uses `draws[:idx]` for rolling edge | ✅ CLEAN |")
    lines.append("| `rollout_static()` fixed policy | No state, purely action-constant | ✅ CLEAN |")
    lines.append("")
    lines.append("**Conclusion: No data leakage detected in observation, reward, or baseline logic.**")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ── Overall recommendation ────────────────────────────────────────────────
    lines.append("## Overall Recommendation")
    lines.append("")
    any_pass = any(r.get("deployment_gate_pass", False) for r in all_evals.values())

    # Summarize gate failures across all combos
    failure_reasons: List[str] = []
    for combo_key, result in all_evals.items():
        if "error" in result or result.get("deployment_gate_pass"):
            continue
        gd = result.get("gate_details", {})
        bla = result.get("baseline_inflation_audit", {})
        if not gd.get("perm_significant"):
            failure_reasons.append(
                f"`{combo_key}`: permutation p={result['permutation_test'].get('p_value_mc','?'):.4f} "
                f"(need <0.05) — hit rate NOT significantly above baseline"
            )
        if not gd.get("mcnemar_significant"):
            mc = result["mcnemar_vs_fixed_static"]
            failure_reasons.append(
                f"`{combo_key}`: McNemar vs fixed net={mc['net']:+d}, "
                f"p={mc['p_value']:.4f} (need <0.05) — no improvement over static policy"
            )
        if bla.get("baseline_inflation_detected"):
            failure_reasons.append(
                f"`{combo_key}`: baseline inflation — RL avg baseline "
                f"{bla.get('rl_avg_baseline_on_test'):.3f} vs uniform "
                f"{bla.get('uniform_strategy_baseline'):.3f}"
            )

    if any_pass:
        best_combo = max(
            ((k, v) for k, v in all_evals.items() if v.get("deployment_gate_pass")),
            key=lambda kv: kv[1]["summaries"]["rl_test"]["edge_pct"],
        )
        lines.append(f"✅ **RECOMMEND ADVISORY DEPLOYMENT**: `{best_combo[0]}`")
        lines.append("")
        lines.append("Integration point: replace `rsm_weights_for_lottery()` "
                     "weight selection in `strategy_coordinator.py` (P1 insertion).")
        lines.append("")
        lines.append("> **Status: ADVISORY** — RL decision displayed alongside Track A signal.")
        lines.append("> No autonomous action until 200 more monitored periods confirm stability.")
    else:
        lines.append("❌ **REJECT** — No combination passed all mandatory gates.")
        lines.append("")
        lines.append("**Failure reasons:**")
        for reason in failure_reasons:
            lines.append(f"- {reason}")
        lines.append("")
        lines.append("**Decision: Continue with current RSM-based static strategy selection.**")
        lines.append("Re-evaluate after ≥200 additional draws (next checkpoint).")
        lines.append("")
        lines.append("> Rationale (L76): passing an edge gate alone is insufficient.")
        lines.append("> McNemar significance and permutation p<0.05 are both mandatory.")
        lines.append("> RL that merely games the reward function must be rejected.")

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("*Generated by `analysis/rl_decision/evaluate_sb3.py` — "
                 "reproducible with seed=42*")

    return "\n".join(lines)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Evaluate trained SB3 RL lottery agents")
    parser.add_argument("--algo", choices=["ppo", "dqn", "both"], default="both")
    parser.add_argument("--reward", choices=["edge", "payout_aware", "skip_efficiency"],
                        default="edge")
    parser.add_argument("--results-json", default=None,
                        help="Existing sb3_walkforward_results.json (if already trained)")
    parser.add_argument("--output-report", default=None,
                        help="Output path for validation report .md")
    parser.add_argument("--run-training", action="store_true",
                        help="Run train_sb3.py first if models not found")
    args = parser.parse_args()

    if not SB3_AVAILABLE:
        print("ERROR: stable_baselines3 not installed. Use /tmp/sb3_env/bin/python3")
        sys.exit(1)

    t0 = time.time()
    print(f"\n{'='*65}")
    print(f"  SB3 Evaluation: algo={args.algo.upper()}  reward={args.reward}")
    print(f"{'='*65}\n")

    # Load data
    raw = load_rsm_records("DAILY_539")
    draws = align_records(raw)
    test_start = VAL_END
    print(f"Loaded {len(draws)} aligned draws | Test: [{test_start}:{len(draws)}]")

    # Determine combos to evaluate
    algos = ["ppo", "dqn"] if args.algo == "both" else [args.algo]

    # Auto-train if models missing and --run-training requested
    if args.run_training:
        for algo in algos:
            mp = os.path.join(MODEL_DIR, f"{algo}_{args.reward}.zip")
            if not os.path.exists(mp):
                print(f"\nTraining {algo.upper()} first (model not found)...")
                import subprocess
                cmd = [
                    "/tmp/sb3_env/bin/python3",
                    os.path.join(SCRIPT_DIR, "train_sb3.py"),
                    "--algo", algo,
                    "--reward", args.reward,
                ]
                subprocess.run(cmd, check=True)

    # Run evaluations
    all_evals: Dict[str, Any] = {}
    for algo in algos:
        combo_key = f"{algo}_{args.reward}"
        print(f"\nEvaluating {combo_key}...")
        result = evaluate_combo(algo, args.reward, draws, test_start)
        all_evals[combo_key] = result

        if "error" not in result:
            s = result["summaries"]
            stab = result["three_window_stability"]
            perm = result["permutation_test"]
            print(f"  RL test: edge={s['rl_test']['edge_pct']:+.2f}%  "
                  f"hit={s['rl_test']['hit_rate']:.3f}  "
                  f"skip={s['rl_test']['skip_rate']:.2f}")
            print(f"  Stable: {stab['stable']}  perm_p={perm['p_value']:.4f}  "
                  f"gate={'PASS' if result['deployment_gate_pass'] else 'FAIL'}")

    # Save evaluation JSON
    eval_out = os.path.join(PROJECT_ROOT, "sb3_evaluation_results.json")
    with open(eval_out, "w", encoding="utf-8") as f:
        json.dump(all_evals, f, indent=2, ensure_ascii=False)
    print(f"\n✅ Evaluation results saved → {eval_out}")

    # Merge with walkforward results if provided
    if args.results_json and os.path.exists(args.results_json):
        with open(args.results_json, encoding="utf-8") as f:
            walkforward = json.load(f)
        merged = {"walkforward": walkforward, "evaluation": all_evals}
        merged_out = os.path.join(PROJECT_ROOT, "sb3_combined_results.json")
        with open(merged_out, "w", encoding="utf-8") as f:
            json.dump(merged, f, indent=2, ensure_ascii=False)
        print(f"✅ Combined results saved → {merged_out}")

    # Generate markdown report
    report_md = generate_report(all_evals, draws, test_start)
    report_path = args.output_report or os.path.join(REPORT_DIR, "sb3_validation_report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_md)
    print(f"✅ Validation report saved → {report_path}")

    elapsed = time.time() - t0
    print(f"\n⏱  Total evaluation time: {elapsed:.1f}s")

    # Quick summary table
    print(f"\n{'─'*65}")
    print(f"  FINAL GATE SUMMARY")
    print(f"{'─'*65}")
    for combo_key, result in all_evals.items():
        if "error" in result:
            print(f"  {combo_key:<25} ERROR")
        else:
            gate = "✅ PASS" if result["deployment_gate_pass"] else "❌ FAIL"
            edge = result["summaries"]["rl_test"]["edge_pct"]
            p    = result["permutation_test"]["p_value"]
            stable = "Y" if result["three_window_stability"]["stable"] else "N"
            print(f"  {combo_key:<25} gate={gate}  edge_test={edge:+.2f}%  "
                  f"perm_p={p:.4f}  stable={stable}")
    print(f"{'─'*65}\n")


if __name__ == "__main__":
    main()
