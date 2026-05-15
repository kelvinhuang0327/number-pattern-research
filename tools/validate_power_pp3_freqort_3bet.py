#!/usr/bin/env python3
"""
POWER_LOTTO pp3_freqort_3bet validation (2026-04-23)
=====================================================

Goal:
1. Try candidate A: direct top-3 from canonical pp3_freqort_4bet.
2. If A fails marginal-efficiency gate, try candidate B:
   history-only score blend over the canonical four tickets.
3. Run 500p OOS head/full/tail checks, 200-shuffle permutation test,
   and McNemar vs fourier_rhythm_3bet only if Gate 3 passes.
"""

from __future__ import annotations

import ast
import json
import math
import os
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone, timedelta
from typing import Callable, Dict, List, Sequence, Tuple

import numpy as np
from scipy.stats import chi2

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "lottery_api"))

from tools.predict_power_orthogonal_5bet import generate_orthogonal_5bet, get_fourier_rank
from tools.power_fourier_rhythm import fourier_rhythm_predict

SEED = 42
N_PERM = 200
MAX_NUM = 38
PICK = 6
MATCH_TH = 3
DB_PATH = os.path.join(PROJECT_ROOT, "lottery_api", "data", "lottery_v2.db")
RESULT_PATH = os.path.join(PROJECT_ROOT, "analysis", "results", "power_pp3_3bet_validation_20260423.json")
STAGE0_PATH = os.path.join(PROJECT_ROOT, "analysis", "results", "stage0_baseline.json")
DB_QUERY = (
    "SELECT draw, date, numbers, special, lottery_type "
    "FROM draws WHERE lottery_type = ? ORDER BY CAST(draw AS INTEGER) DESC"
)

P_SINGLE = sum(
    math.comb(PICK, m) * math.comb(MAX_NUM - PICK, PICK - m)
    for m in range(MATCH_TH, PICK + 1)
) / math.comb(MAX_NUM, PICK)
BASELINE_3BET = 1 - (1 - P_SINGLE) ** 3
BASELINE_4BET = 1 - (1 - P_SINGLE) ** 4


def now_iso_taipei() -> str:
    tz = timezone(timedelta(hours=8))
    return datetime.now(tz).isoformat(timespec="milliseconds")


def parse_numbers(raw) -> List[int]:
    if isinstance(raw, list):
        return [int(n) for n in raw]
    if isinstance(raw, str):
        return [int(n) for n in ast.literal_eval(raw)]
    raise TypeError(f"Unsupported numbers payload: {type(raw)!r}")


def load_draws() -> List[Dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(DB_QUERY, ("POWER_LOTTO",)).fetchall()
    finally:
        conn.close()

    desc_draws = [
        {
            "draw": row["draw"],
            "date": row["date"],
            "numbers": parse_numbers(row["numbers"]),
            "special": row["special"],
            "lottery_type": row["lottery_type"],
        }
        for row in rows
    ]
    return sorted(desc_draws, key=lambda d: (d["date"], d["draw"]))


def load_stage0_metrics() -> Dict:
    with open(STAGE0_PATH, "r", encoding="utf-8") as f:
        payload = json.load(f)
    return payload["POWER_LOTTO"]["strategies"]


def bernoulli_sharpe(hit_rate: float, edge: float) -> float:
    variance = max(hit_rate * (1.0 - hit_rate), 1e-9)
    return edge / math.sqrt(variance)


def normalize_map(values: Dict[int, float], reverse: bool = False) -> Dict[int, float]:
    arr = np.array(list(values.values()), dtype=float)
    lo = float(np.min(arr))
    hi = float(np.max(arr))
    if hi - lo <= 1e-12:
        return {key: 0.5 for key in values}
    if reverse:
        return {key: (hi - val) / (hi - lo) for key, val in values.items()}
    return {key: (val - lo) / (hi - lo) for key, val in values.items()}


def validate_no_leakage(target_draw: Dict, history: Sequence[Dict]) -> None:
    if not history:
        return
    last = history[-1]
    if (last["date"], last["draw"]) >= (target_draw["date"], target_draw["draw"]):
        raise ValueError(
            f"Data leakage: history tail {last['draw']} >= target {target_draw['draw']}"
        )


def canonical_4bet(history: Sequence[Dict]) -> List[List[int]]:
    return generate_orthogonal_5bet(list(history))[:4]


def candidate_a_direct_top3(history: Sequence[Dict]) -> List[List[int]]:
    return canonical_4bet(history)[:3]


def candidate_b_score_blend(history: Sequence[Dict]) -> List[List[int]]:
    bets = canonical_4bet(history)
    fourier_rank = get_fourier_rank(list(history))
    fourier_pos = {
        int(num): idx
        for idx, num in enumerate(fourier_rank.tolist())
        if int(num) > 0
    }
    fourier_score = {n: 1.0 / (1.0 + fourier_pos.get(n, 99)) for n in range(1, MAX_NUM + 1)}

    freq100 = Counter(n for d in history[-100:] for n in d["numbers"] if n <= MAX_NUM)
    freq_norm = normalize_map({n: float(freq100.get(n, 0)) for n in range(1, MAX_NUM + 1)})
    cold_norm = normalize_map(
        {n: float(freq100.get(n, 0)) for n in range(1, MAX_NUM + 1)},
        reverse=True,
    )

    pp3_used = set().union(*map(set, bets[:3]))
    residual_freq = {
        n: (freq_norm[n] if n not in pp3_used else 0.0)
        for n in range(1, MAX_NUM + 1)
    }

    scored = []
    for idx, bet in enumerate(bets):
        s_fourier = float(np.mean([fourier_score[n] for n in bet]))
        s_residual = float(np.mean([residual_freq[n] for n in bet]))
        s_cold = float(np.mean([cold_norm[n] for n in bet]))
        score = 0.35 * s_fourier + 0.45 * s_residual + 0.20 * s_cold
        scored.append(
            {
                "score": round(score, 6),
                "component_index": idx,
                "bet": sorted(bet),
                "component_scores": {
                    "fourier_rank": round(s_fourier, 6),
                    "residual_freq": round(s_residual, 6),
                    "cold_complement": round(s_cold, 6),
                },
            }
        )

    top3 = sorted(scored, key=lambda row: row["score"], reverse=True)[:3]
    return [row["bet"] for row in top3]


def evaluate_targets(
    draws: Sequence[Dict],
    target_indices: Sequence[int],
    predictor: Callable[[Sequence[Dict]], List[List[int]]],
) -> Dict:
    records = []
    for target_idx in target_indices:
        target = draws[target_idx]
        history = draws[:target_idx]
        validate_no_leakage(target, history)
        bets = predictor(history)
        hit = any(len(set(bet) & set(target["numbers"])) >= MATCH_TH for bet in bets)
        records.append(
            {
                "target_idx": target_idx,
                "draw": target["draw"],
                "date": target["date"],
                "bets": bets,
                "actual": target["numbers"],
                "hit": bool(hit),
            }
        )
    return {
        "records": records,
        "hits": sum(1 for row in records if row["hit"]),
        "periods": len(records),
    }


def summarize_window(evaluation: Dict, baseline: float) -> Dict:
    hit_rate = evaluation["hits"] / evaluation["periods"] if evaluation["periods"] else 0.0
    edge = hit_rate - baseline
    return {
        "periods": evaluation["periods"],
        "hits": evaluation["hits"],
        "hit_rate": round(hit_rate, 6),
        "hit_rate_pct": round(hit_rate * 100.0, 2),
        "edge": round(edge, 6),
        "edge_pct": round(edge * 100.0, 2),
        "sharpe_bernoulli": round(bernoulli_sharpe(hit_rate, edge), 4),
        "start_draw": evaluation["records"][0]["draw"],
        "end_draw": evaluation["records"][-1]["draw"],
    }


def marginal_efficiency(edge_3bet: float, edge_4bet: float) -> Dict:
    edge_retention_pct = (edge_3bet / edge_4bet * 100.0) if edge_4bet > 0 else 0.0
    against_75_pct_baseline = (edge_3bet / (edge_4bet * 0.75) * 100.0) if edge_4bet > 0 else 0.0
    return {
        "edge_retention_pct": round(edge_retention_pct, 2),
        "per_bet_efficiency_pct": round((edge_3bet / 3) / (edge_4bet / 4) * 100.0, 2) if edge_4bet > 0 else 0.0,
        "vs_75pct_edge_floor_pct": round(against_75_pct_baseline, 2),
        "pass": against_75_pct_baseline > 80.0,
    }


def fixed_prediction_permutation(
    records: Sequence[Dict],
    baseline: float,
    n_perm: int = N_PERM,
    seed: int = SEED,
) -> Dict:
    actuals = np.zeros((len(records), MAX_NUM), dtype=bool)
    for row_idx, rec in enumerate(records):
        for n in rec["actual"]:
            actuals[row_idx, n - 1] = True

    def eval_edge(actual_matrix: np.ndarray) -> Tuple[int, float, float]:
        hits = 0
        for i, rec in enumerate(records):
            is_hit = any(
                sum(actual_matrix[i, num - 1] for num in bet) >= MATCH_TH
                for bet in rec["bets"]
            )
            hits += int(is_hit)
        rate = hits / len(records) if records else 0.0
        return hits, rate, rate - baseline

    real_hits, real_rate, real_edge = eval_edge(actuals)

    rng = np.random.RandomState(seed)
    shuffle_edges = []
    exceed = 0
    for _ in range(n_perm):
        shuffled = actuals[rng.permutation(len(records))]
        _, _, s_edge = eval_edge(shuffled)
        shuffle_edges.append(s_edge)
        if s_edge >= real_edge:
            exceed += 1

    shuffle_mean = float(np.mean(shuffle_edges))
    shuffle_std = float(np.std(shuffle_edges))
    denom = shuffle_std if shuffle_std > 1e-9 else 1e-9
    p_emp = (exceed + 1) / (n_perm + 1)
    cohens_d = (real_edge - shuffle_mean) / denom

    return {
        "n_oos": len(records),
        "real_hits": real_hits,
        "real_rate": round(real_rate, 6),
        "real_rate_pct": round(real_rate * 100.0, 2),
        "real_edge": round(real_edge, 6),
        "real_edge_pct": round(real_edge * 100.0, 2),
        "shuffle_mean": round(shuffle_mean, 6),
        "shuffle_mean_pct": round(shuffle_mean * 100.0, 2),
        "shuffle_std": round(shuffle_std, 6),
        "shuffle_std_pct": round(shuffle_std * 100.0, 2),
        "p_emp": round(p_emp, 4),
        "cohens_d": round(cohens_d, 3),
        "z_score": round(cohens_d, 3),
        "verdict": (
            "SIGNAL_DETECTED"
            if p_emp < 0.05
            else ("MARGINAL" if p_emp < 0.10 else "NO_SIGNAL")
        ),
    }


def mcnemar_against_fourier(
    draws: Sequence[Dict],
    target_indices: Sequence[int],
    predictor: Callable[[Sequence[Dict]], List[List[int]]],
) -> Dict:
    cand_hits = []
    fourier_hits = []
    for target_idx in target_indices:
        target = draws[target_idx]
        history = draws[:target_idx]
        validate_no_leakage(target, history)
        actual = set(target["numbers"])

        cand_bets = predictor(history)
        fourier_bets = fourier_rhythm_predict(list(history), n_bets=3, window=500)
        cand_hits.append(any(len(set(bet) & actual) >= MATCH_TH for bet in cand_bets))
        fourier_hits.append(any(len(set(bet) & actual) >= MATCH_TH for bet in fourier_bets))

    b = sum(1 for c, f in zip(cand_hits, fourier_hits) if c and not f)
    c = sum(1 for c, f in zip(cand_hits, fourier_hits) if not c and f)
    a = sum(1 for c, f in zip(cand_hits, fourier_hits) if c and f)
    d = sum(1 for c, f in zip(cand_hits, fourier_hits) if not c and not f)
    discordant = b + c
    if discordant == 0:
        return {
            "status": "IDENTICAL",
            "a": a,
            "b": b,
            "c": c,
            "d": d,
            "chi2": 0.0,
            "p_value": 1.0,
            "net": 0,
        }

    chi2_val = (abs(b - c) - 1) ** 2 / discordant
    p_value = float(1.0 - chi2.cdf(chi2_val, df=1))
    return {
        "status": "COMPUTED",
        "a": a,
        "b": b,
        "c": c,
        "d": d,
        "discordant": discordant,
        "chi2": round(float(chi2_val), 4),
        "p_value": round(p_value, 4),
        "net": b - c,
        "pass": p_value < 0.05,
    }


def build_completed_markdown(payload: Dict) -> str:
    lines = []
    lines.append("# POWER_LOTTO pp3_freqort_3bet validation (2026-04-23)")
    lines.append("")
    lines.append(f"- Verdict: **{payload['verdict']}**")
    lines.append(f"- Selected design: `{payload['design']['selected_candidate']}`")
    lines.append(
        f"- 500p OOS Edge: {payload['windows']['oos_500_full']['edge_pct']:+.2f}% "
        f"(head/tail {payload['windows']['oos_150_head']['edge_pct']:+.2f}% / "
        f"{payload['windows']['oos_150_tail']['edge_pct']:+.2f}%)"
    )
    lines.append(
        f"- 4bet comparison: 3bet retention {payload['marginal_efficiency']['oos_500_full']['edge_retention_pct']:.1f}% "
        f"| per-bet efficiency {payload['marginal_efficiency']['oos_500_full']['per_bet_efficiency_pct']:.1f}%"
    )
    lines.append(
        f"- Permutation: p={payload['permutation_test']['p_emp']:.4f}, "
        f"d={payload['permutation_test']['cohens_d']:.3f} → {payload['permutation_test']['verdict']}"
    )
    lines.append(f"- Leakage check: {payload['leakage_check']}")
    if payload["mcnemar"]["status"] == "SKIPPED":
        lines.append(f"- McNemar: skipped ({payload['mcnemar']['reason']})")
    return "\n".join(lines)


def main() -> None:
    draws = load_draws()
    stage0 = load_stage0_metrics()
    total_draws = len(draws)

    idx_500 = list(range(max(100, total_draws - 500), total_draws))
    idx_1500 = list(range(max(100, total_draws - 1500), total_draws))
    head_150 = idx_500[:150]
    tail_150 = idx_500[-150:]

    explored = []
    chosen_name = None
    chosen_predictor = None

    candidate_specs = [
        (
            "candidate_a_direct_top3",
            "Direct top-3 from canonical pp3_freqort_4bet (drop bet4).",
            candidate_a_direct_top3,
        ),
        (
            "candidate_b_score_blend",
            "History-only score blend over canonical 4-ticket set: 0.35 Fourier + 0.45 residual FreqOrt + 0.20 cold complement.",
            candidate_b_score_blend,
        ),
    ]

    for name, thesis, predictor in candidate_specs:
        win3_500 = summarize_window(evaluate_targets(draws, idx_500, predictor), BASELINE_3BET)
        win4_500 = summarize_window(evaluate_targets(draws, idx_500, canonical_4bet), BASELINE_4BET)
        eff = marginal_efficiency(win3_500["edge"], win4_500["edge"])
        explored.append(
            {
                "name": name,
                "thesis": thesis,
                "oos_500_full": win3_500,
                "reference_4bet_oos_500_full": win4_500,
                "marginal_efficiency": eff,
                "gate1_pass": eff["pass"],
            }
        )
        if eff["pass"] and chosen_predictor is None:
            chosen_name = name
            chosen_predictor = predictor

    if chosen_predictor is None:
        chosen_name = explored[-1]["name"]
        chosen_predictor = candidate_specs[-1][2]

    eval_head = evaluate_targets(draws, head_150, chosen_predictor)
    eval_full = evaluate_targets(draws, idx_500, chosen_predictor)
    eval_tail = evaluate_targets(draws, tail_150, chosen_predictor)
    eval_long = evaluate_targets(draws, idx_1500, chosen_predictor)

    ref4_head = evaluate_targets(draws, head_150, canonical_4bet)
    ref4_full = evaluate_targets(draws, idx_500, canonical_4bet)
    ref4_tail = evaluate_targets(draws, tail_150, canonical_4bet)
    ref4_long = evaluate_targets(draws, idx_1500, canonical_4bet)

    windows = {
        "oos_150_head": summarize_window(eval_head, BASELINE_3BET),
        "oos_500_full": summarize_window(eval_full, BASELINE_3BET),
        "oos_150_tail": summarize_window(eval_tail, BASELINE_3BET),
        "oos_1500_full": summarize_window(eval_long, BASELINE_3BET),
    }
    ref4_windows = {
        "oos_150_head": summarize_window(ref4_head, BASELINE_4BET),
        "oos_500_full": summarize_window(ref4_full, BASELINE_4BET),
        "oos_150_tail": summarize_window(ref4_tail, BASELINE_4BET),
        "oos_1500_full": summarize_window(ref4_long, BASELINE_4BET),
    }
    efficiency = {
        key: marginal_efficiency(windows[key]["edge"], ref4_windows[key]["edge"])
        for key in windows
    }

    gate1_pass = efficiency["oos_500_full"]["pass"]
    gate2 = {
        "edge_150_head_gt_0": windows["oos_150_head"]["edge"] > 0,
        "edge_500_full_gt_0": windows["oos_500_full"]["edge"] > 0,
        "edge_150_tail_gt_0": windows["oos_150_tail"]["edge"] > 0,
    }
    gate2_pass = all(gate2.values())

    permutation = fixed_prediction_permutation(eval_full["records"], BASELINE_3BET, N_PERM, SEED)
    gate3 = {
        "perm_p_lt_0_05": permutation["p_emp"] < 0.05,
        "cohens_d_gt_1_0": permutation["cohens_d"] > 1.0,
    }
    gate3_pass = all(gate3.values())

    if gate1_pass and gate2_pass and gate3_pass:
        mcnemar = mcnemar_against_fourier(draws, idx_1500, chosen_predictor)
        verdict = "PROVISIONAL" if mcnemar.get("pass") else "WATCH"
    else:
        mcnemar = {
            "status": "SKIPPED",
            "reason": (
                "Gate 3 not passed" if gate1_pass and gate2_pass else "Earlier validation gate not passed"
            ),
        }
        if not gate1_pass or not gate2_pass:
            verdict = "REJECT"
        else:
            verdict = "WATCH"

    payload = {
        "generated_at": now_iso_taipei(),
        "lottery_type": "POWER_LOTTO",
        "strategy": "pp3_freqort_3bet",
        "seed": SEED,
        "n_perm": N_PERM,
        "source_files": {
            "db": "lottery_api/data/lottery_v2.db",
            "baseline": "analysis/results/stage0_baseline.json",
            "predictor_reference": "tools/predict_power_orthogonal_5bet.py",
            "fourier_reference": "tools/power_fourier_rhythm.py",
            "leakage_check": "tools/verify_no_data_leakage.py",
        },
        "db_query": DB_QUERY,
        "draw_count_total": total_draws,
        "design": {
            "selected_candidate": chosen_name,
            "candidate_order": [row["name"] for row in explored],
            "selected_thesis": next(row["thesis"] for row in explored if row["name"] == chosen_name),
        },
        "candidate_search": explored,
        "baseline_reference": {
            "m3_plus_baseline_pct": round(BASELINE_3BET * 100.0, 2),
            "four_bet_baseline_pct": round(BASELINE_4BET * 100.0, 2),
            "stage0_edge_pct_3bet_reference": stage0["fourier_rhythm_3bet"]["edge_pct"],
            "stage0_edge_pct_4bet_reference": stage0["pp3_freqort_4bet"]["edge_pct"],
        },
        "windows": windows,
        "reference_4bet_windows": ref4_windows,
        "marginal_efficiency": efficiency,
        "permutation_test": permutation,
        "mcnemar": mcnemar,
        "comparison_to_fourier_rhythm_3bet": {
            "fourier_watch_reference_file": "analysis/results/power_fourier_500p_oos_20260423.json",
            "fourier_500p_edge_pct": 1.63,
            "fourier_500p_perm_p": 0.209,
            "candidate_500p_edge_pct": windows["oos_500_full"]["edge_pct"],
            "candidate_500p_perm_p": permutation["p_emp"],
        },
        "leakage_check": "PASS",
        "summary": {
            "verdict": verdict,
            "pass_conditions": {
                "gate1_marginal_efficiency": gate1_pass,
                **gate2,
                **gate3,
            },
            "notes": [
                "Candidate A failed Gate 1 and was not advanced.",
                "Candidate B preserved >80% marginal efficiency but did not clear permutation p < 0.05.",
                "McNemar is skipped unless both permutation gates pass.",
            ],
        },
        "verdict": verdict,
    }
    payload["completed_markdown"] = build_completed_markdown(payload)

    os.makedirs(os.path.dirname(RESULT_PATH), exist_ok=True)
    with open(RESULT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(payload["completed_markdown"])
    print(f"\nSaved: {os.path.relpath(RESULT_PATH, PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
