#!/usr/bin/env python3
"""
POWER_LOTTO midfreq_fourier_2bet regime-gated validation (2026-04-23)
======================================================================

Goal:
1. Diagnose why `midfreq_fourier_2bet` failed 150p / McNemar / efficiency gates.
2. Build a history-only fixed-rule candidate:
   `midfreq_fourier_2bet_regime_gate_v1`
3. Run 150 / 500 / 1500 window validation with permutation, effect size,
   leakage verification, and conditional 500p OOS McNemar vs baseline.
"""

from __future__ import annotations

import ast
import json
import math
import os
import sqlite3
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, List, Sequence, Tuple

import numpy as np
from scipy.stats import chi2

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "lottery_api"))

from lottery_api.engine.perm_test import perm_test
from lottery_api.utils.benchmark_framework import StrategyBenchmark
from tools.power_midfreq_fourier import midfreq_fourier_2bet

SEED = 42
N_PERM = 200
MAX_NUM = 38
PICK = 6
MATCH_TH = 3
MIN_HISTORY = 100
DB_PATH = os.path.join(PROJECT_ROOT, "lottery_api", "data", "lottery_v2.db")
RESULT_PATH = os.path.join(
    PROJECT_ROOT,
    "analysis",
    "results",
    "power_midfreq2bet_regime_gate_v1_20260423.json",
)
DIAG_PATH = os.path.join(
    PROJECT_ROOT,
    "analysis",
    "results",
    "power_midfreq2bet_regime_gate_v1_diagnostics_20260423.json",
)
LEAKAGE_TOOL = os.path.join(PROJECT_ROOT, "tools", "verify_no_data_leakage.py")
STAGE0_PATH = os.path.join(PROJECT_ROOT, "analysis", "results", "stage0_baseline.json")
DB_QUERY = (
    "SELECT draw, date, numbers, special, lottery_type "
    "FROM draws WHERE lottery_type = ? ORDER BY CAST(draw AS INTEGER) DESC"
)

P_SINGLE = sum(
    math.comb(PICK, m) * math.comb(MAX_NUM - PICK, PICK - m)
    for m in range(MATCH_TH, PICK + 1)
) / math.comb(MAX_NUM, PICK)
BASELINE_1BET = P_SINGLE
BASELINE_2BET = 1 - (1 - P_SINGLE) ** 2


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


def recent_frequency_map(history: Sequence[Dict], window: int) -> Dict[int, float]:
    recent = history[-window:] if len(history) >= window else history
    freq = Counter(n for d in recent for n in d["numbers"][:PICK])
    return {n: float(freq.get(n, 0)) for n in range(1, MAX_NUM + 1)}


def validate_no_leakage(target_draw: Dict, history: Sequence[Dict]) -> None:
    if not history:
        return
    last = history[-1]
    if (last["date"], last["draw"]) >= (target_draw["date"], target_draw["draw"]):
        raise ValueError(
            f"Data leakage: history tail {last['draw']} >= target {target_draw['draw']}"
        )


def baseline_predictor(history: Sequence[Dict]) -> List[List[int]]:
    return midfreq_fourier_2bet(list(history))


def cold_residual_bet(history: Sequence[Dict], exclude: Sequence[int], window: int = 60) -> List[int]:
    cold_scores = normalize_map(recent_frequency_map(history, window), reverse=True)
    candidates = [n for n in range(1, MAX_NUM + 1) if n not in set(exclude)]
    ranked = sorted(candidates, key=lambda n: (-cold_scores[n], n))
    return sorted(ranked[:PICK])


def hot_residual_bet(history: Sequence[Dict], exclude: Sequence[int], window: int = 60) -> List[int]:
    hot_scores = normalize_map(recent_frequency_map(history, window))
    candidates = [n for n in range(1, MAX_NUM + 1) if n not in set(exclude)]
    ranked = sorted(candidates, key=lambda n: (-hot_scores[n], n))
    return sorted(ranked[:PICK])


def regime_snapshot(history: Sequence[Dict]) -> Dict:
    prev_draw = history[-1]
    prev_nums = prev_draw["numbers"][:PICK]
    prev_sum = int(sum(prev_nums))
    prev_odd = int(sum(n % 2 for n in prev_nums))
    last10 = history[-10:] if len(history) >= 10 else history
    mean10_sum = float(np.mean([sum(d["numbers"][:PICK]) for d in last10])) if last10 else prev_sum
    last30 = history[-30:] if len(history) >= 30 else history
    recent30_freq = Counter(n for d in last30 for n in d["numbers"][:PICK])
    hot12 = {n for n, _ in recent30_freq.most_common(12)}
    hot_overlap = int(sum(1 for n in prev_nums if n in hot12))

    if prev_sum < 109:
        prev_sum_bucket = "low"
    elif prev_sum > 139:
        prev_sum_bucket = "high"
    else:
        prev_sum_bucket = "mid"

    if prev_odd == 3:
        prev_parity_bucket = "balanced"
    elif prev_odd in (0, 1, 5, 6):
        prev_parity_bucket = "extreme"
    else:
        prev_parity_bucket = "tilted"

    if hot_overlap <= 1:
        density_bucket = "cold"
    elif hot_overlap >= 4:
        density_bucket = "hot"
    else:
        density_bucket = "mixed"

    mean10_sum_low = mean10_sum < 114.0

    return {
        "prev_draw": prev_draw["draw"],
        "prev_sum": prev_sum,
        "prev_odd_count": prev_odd,
        "prev_sum_bucket": prev_sum_bucket,
        "prev_parity_bucket": prev_parity_bucket,
        "hot_overlap_12of30": hot_overlap,
        "density_bucket": density_bucket,
        "mean10_sum": round(mean10_sum, 3),
        "mean10_sum_low": mean10_sum_low,
    }


def candidate_predictor(history: Sequence[Dict]) -> Tuple[List[List[int]], Dict]:
    bet1, base_bet2 = baseline_predictor(history)
    exclude = set(bet1)
    snapshot = regime_snapshot(history)

    if snapshot["mean10_sum_low"]:
        bet2 = cold_residual_bet(history, exclude, window=60)
        gate = "mean10_sum_low -> cold_residual_60"
    elif snapshot["density_bucket"] == "hot":
        bet2 = hot_residual_bet(history, exclude, window=60)
        gate = "prev_hot_overlap>=4 -> hot_residual_60"
    else:
        bet2 = base_bet2
        gate = "default -> baseline_fourier_residual"

    meta = {
        "gate_applied": gate,
        "regime_snapshot": snapshot,
    }
    return [bet1, bet2], meta


def candidate_predictor_bets(history: Sequence[Dict]) -> List[List[int]]:
    return candidate_predictor(history)[0]


def evaluate_targets(
    draws: Sequence[Dict],
    target_indices: Sequence[int],
    predictor: Callable[[Sequence[Dict]], List[List[int]] | Tuple[List[List[int]], Dict]],
) -> Dict:
    records = []
    for target_idx in target_indices:
        target = draws[target_idx]
        history = draws[:target_idx]
        validate_no_leakage(target, history)
        result = predictor(history)
        if isinstance(result, tuple):
            bets, meta = result
        else:
            bets, meta = result, {"gate_applied": "baseline"}

        actual = set(target["numbers"])
        per_bet_hits = [len(set(bet) & actual) >= MATCH_TH for bet in bets]
        records.append(
            {
                "target_idx": target_idx,
                "draw": target["draw"],
                "date": target["date"],
                "actual": target["numbers"],
                "bets": bets,
                "per_bet_hits": per_bet_hits,
                "hit": any(per_bet_hits),
                "gate_applied": meta.get("gate_applied", "baseline"),
                "regime_snapshot": meta.get("regime_snapshot"),
            }
        )
    return {
        "records": records,
        "hits": sum(1 for row in records if row["hit"]),
        "periods": len(records),
    }


def summarize_window(evaluation: Dict) -> Dict:
    periods = evaluation["periods"]
    hits = evaluation["hits"]
    hit_rate = hits / periods if periods else 0.0
    edge = hit_rate - BASELINE_2BET
    per_bet_hit_rates = []
    per_bet_edges = []
    if periods:
        n_bets = len(evaluation["records"][0]["per_bet_hits"])
        for bet_idx in range(n_bets):
            rate = sum(row["per_bet_hits"][bet_idx] for row in evaluation["records"]) / periods
            per_bet_hit_rates.append(rate)
            per_bet_edges.append(rate - BASELINE_1BET)
    efficiency_pct = (
        (per_bet_hit_rates[1] / per_bet_hit_rates[0] * 100.0)
        if len(per_bet_hit_rates) >= 2 and per_bet_hit_rates[0] > 0
        else 0.0
    )
    return {
        "periods": periods,
        "hits": hits,
        "hit_rate": round(hit_rate, 6),
        "hit_rate_pct": round(hit_rate * 100.0, 2),
        "edge": round(edge, 6),
        "edge_pct": round(edge * 100.0, 2),
        "sharpe_bernoulli": round(bernoulli_sharpe(hit_rate, edge), 4),
        "per_bet_hit_rates": [round(rate, 6) for rate in per_bet_hit_rates],
        "per_bet_hit_rate_pct": [round(rate * 100.0, 2) for rate in per_bet_hit_rates],
        "per_bet_edges": [round(edge_i, 6) for edge_i in per_bet_edges],
        "per_bet_edge_pct": [round(edge_i * 100.0, 2) for edge_i in per_bet_edges],
        "per_bet_efficiency_pct": round(efficiency_pct, 2),
        "per_bet_efficiency_pass": efficiency_pct > 80.0,
        "start_draw": evaluation["records"][0]["draw"],
        "end_draw": evaluation["records"][-1]["draw"],
    }


def compare_windows(candidate: Dict, baseline: Dict) -> Dict:
    return {
        "candidate_edge_pct": candidate["edge_pct"],
        "baseline_edge_pct": baseline["edge_pct"],
        "delta_edge_pct": round(candidate["edge_pct"] - baseline["edge_pct"], 2),
        "candidate_sharpe": candidate["sharpe_bernoulli"],
        "baseline_sharpe": baseline["sharpe_bernoulli"],
        "delta_sharpe": round(candidate["sharpe_bernoulli"] - baseline["sharpe_bernoulli"], 4),
        "candidate_efficiency_pct": candidate["per_bet_efficiency_pct"],
        "baseline_efficiency_pct": baseline["per_bet_efficiency_pct"],
    }


def run_perm_window(
    draws: Sequence[Dict],
    target_indices: Sequence[int],
    predict_fn: Callable[[Sequence[Dict]], List[List[int]]],
) -> Dict:
    subset = list(draws[: target_indices[-1] + 1])
    min_history = target_indices[0]
    result = perm_test(
        history=subset,
        predict_fn=predict_fn,
        baseline=BASELINE_2BET,
        min_history=min_history,
        n_perm=N_PERM,
        seed=SEED,
        verbose=False,
    )
    if result["n_oos"] != len(target_indices):
        raise ValueError(
            f"Permutation OOS mismatch: expected {len(target_indices)}, got {result['n_oos']}"
        )
    result["real_rate_pct"] = round(result["real_rate"] * 100.0, 2)
    result["real_edge_pct"] = round(result["real_edge"] * 100.0, 2)
    result["shuffle_mean_pct"] = round(result["shuffle_mean"] * 100.0, 2)
    result["shuffle_std_pct"] = round(result["shuffle_std"] * 100.0, 2)
    return result


def mcnemar_against_baseline(
    draws: Sequence[Dict],
    target_indices: Sequence[int],
) -> Dict:
    candidate_hits = []
    baseline_hits = []
    for target_idx in target_indices:
        target = draws[target_idx]
        history = draws[:target_idx]
        validate_no_leakage(target, history)
        actual = set(target["numbers"])
        candidate_bets = candidate_predictor_bets(history)
        baseline_bets = baseline_predictor(history)
        candidate_hits.append(any(len(set(bet) & actual) >= MATCH_TH for bet in candidate_bets))
        baseline_hits.append(any(len(set(bet) & actual) >= MATCH_TH for bet in baseline_bets))

    a = sum(1 for c, b in zip(candidate_hits, baseline_hits) if c and b)
    b = sum(1 for c, bl in zip(candidate_hits, baseline_hits) if c and not bl)
    c = sum(1 for c, bl in zip(candidate_hits, baseline_hits) if not c and bl)
    d = sum(1 for c, bl in zip(candidate_hits, baseline_hits) if not c and not bl)
    discordant = b + c
    if discordant == 0:
        return {
            "status": "IDENTICAL",
            "a": a,
            "b": b,
            "c": c,
            "d": d,
            "discordant": discordant,
            "chi2": 0.0,
            "p_value": 1.0,
            "net": 0,
            "pass": False,
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


def run_leakage_check() -> Dict:
    proc = subprocess.run(
        [sys.executable, LEAKAGE_TOOL],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    status = "PASS" if proc.returncode == 0 and "✅ 所有測試案例通過" in proc.stdout else "FAIL"
    return {
        "status": status,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout.strip().splitlines()[-12:],
        "stderr_tail": proc.stderr.strip().splitlines()[-12:],
    }


def benchmark_reference(
    predictor: Callable[[Sequence[Dict]], List[List[int]]],
    strategy_name: str,
    test_periods: int,
) -> Dict:
    def wrapper(history, rules):
        del rules
        return predictor(history)

    benchmark = StrategyBenchmark(lottery_type="POWER_LOTTO", test_periods=test_periods)
    result = benchmark.evaluate(
        strategy_fn=wrapper,
        strategy_name=strategy_name,
        num_bets=2,
        use_multi_seed=False,
    )
    return {
        "strategy_name": result.strategy_name,
        "test_periods": result.test_periods,
        "random_baseline_pct": round(result.random_baseline, 2),
        "win_rate_pct": round(result.win_rate, 2),
        "edge_vs_random_pct": round(result.edge_vs_random, 2),
        "roi_pct": round(result.roi, 2),
        "z_score": round(result.z_score, 3),
        "p_value": round(result.p_value, 4),
    }


def build_bucket_diagnostics(
    window_name: str,
    baseline_eval: Dict,
    candidate_eval: Dict,
) -> Dict:
    buckets = defaultdict(lambda: {"count": 0, "baseline_hits": 0, "candidate_hits": 0})
    gate_counts = Counter()
    for base_row, cand_row in zip(baseline_eval["records"], candidate_eval["records"]):
        regime = cand_row["regime_snapshot"] or {}
        key = (
            regime.get("prev_sum_bucket", "na"),
            regime.get("prev_parity_bucket", "na"),
            regime.get("density_bucket", "na"),
        )
        buckets[key]["count"] += 1
        buckets[key]["baseline_hits"] += int(base_row["hit"])
        buckets[key]["candidate_hits"] += int(cand_row["hit"])
        gate_counts[cand_row["gate_applied"]] += 1

    bucket_rows = []
    for key, row in buckets.items():
        count = row["count"]
        if count < 8:
            continue
        baseline_rate = row["baseline_hits"] / count
        candidate_rate = row["candidate_hits"] / count
        bucket_rows.append(
            {
                "bucket": {
                    "prev_sum_bucket": key[0],
                    "prev_parity_bucket": key[1],
                    "density_bucket": key[2],
                },
                "count": count,
                "baseline_hit_rate_pct": round(baseline_rate * 100.0, 2),
                "baseline_edge_pct": round((baseline_rate - BASELINE_2BET) * 100.0, 2),
                "candidate_hit_rate_pct": round(candidate_rate * 100.0, 2),
                "candidate_edge_pct": round((candidate_rate - BASELINE_2BET) * 100.0, 2),
                "candidate_minus_baseline_edge_pct": round((candidate_rate - baseline_rate) * 100.0, 2),
            }
        )

    bucket_rows.sort(key=lambda row: (row["baseline_edge_pct"], -row["count"]))
    top_negative = bucket_rows[:3]
    top_improvement = sorted(
        bucket_rows,
        key=lambda row: (row["candidate_minus_baseline_edge_pct"], row["count"]),
        reverse=True,
    )[:5]

    return {
        "window": window_name,
        "gate_counts": dict(gate_counts),
        "top_negative_baseline_buckets": top_negative,
        "top_candidate_improvement_buckets": top_improvement,
    }


def build_top_blockers(payload: Dict) -> List[str]:
    blockers = []
    for window_name in ("recent_150", "recent_500", "recent_1500"):
        win = payload["candidate_windows"][window_name]
        base_win = payload["baseline_windows"][window_name]
        perm = payload["permutation_tests"][window_name]
        if win["edge"] <= 0:
            blockers.append(f"{window_name}: edge={win['edge_pct']:+.2f}% <= 0")
        if perm["p_emp"] >= 0.05:
            blockers.append(f"{window_name}: permutation p={perm['p_emp']:.4f} >= 0.05")
        if perm["cohens_d"] <= 1.0:
            blockers.append(f"{window_name}: Cohen's d={perm['cohens_d']:.3f} <= 1.0")
        if not win["per_bet_efficiency_pass"]:
            blockers.append(
                f"{window_name}: per-bet efficiency={win['per_bet_efficiency_pct']:.1f}% <= 80%"
            )
        if any(edge_pct <= 0 for edge_pct in win["per_bet_edge_pct"]):
            blockers.append(
                f"{window_name}: single-bet edge contains non-positive leg "
                f"{win['per_bet_edge_pct']}"
            )
        if win["edge_pct"] < base_win["edge_pct"]:
            blockers.append(
                f"{window_name}: candidate edge {win['edge_pct']:+.2f}% trails baseline "
                f"{base_win['edge_pct']:+.2f}%"
            )

    leakage = payload["leakage_check"]["status"]
    if leakage != "PASS":
        blockers.append("leakage_check: FAIL")

    if payload["mcnemar_500"]["status"] == "COMPUTED" and not payload["mcnemar_500"]["pass"]:
        blockers.append(
            f"mcnemar_500: p={payload['mcnemar_500']['p_value']:.4f} >= 0.05 "
            f"(net={payload['mcnemar_500']['net']:+d})"
        )
    elif payload["mcnemar_500"]["status"] == "SKIPPED":
        blockers.append(f"mcnemar_500: skipped ({payload['mcnemar_500']['reason']})")

    seen = []
    for blocker in blockers:
        if blocker not in seen:
            seen.append(blocker)
    return seen[:3]


def build_completed_markdown(payload: Dict) -> str:
    lines = [
        "# POWER_LOTTO midfreq_fourier_2bet_regime_gate_v1 validation (2026-04-23)",
        "",
        f"- Verdict: **{payload['verdict']}**",
        (
            "- Candidate rule: "
            "`mean10_sum_low -> cold_residual_60`, else "
            "`prev_hot_overlap>=4 -> hot_residual_60`, else baseline Fourier residual"
        ),
        (
            f"- 150/500/1500 Edge: "
            f"{payload['candidate_windows']['recent_150']['edge_pct']:+.2f}% / "
            f"{payload['candidate_windows']['recent_500']['edge_pct']:+.2f}% / "
            f"{payload['candidate_windows']['recent_1500']['edge_pct']:+.2f}%"
        ),
        (
            f"- 150/500/1500 perm p: "
            f"{payload['permutation_tests']['recent_150']['p_emp']:.4f} / "
            f"{payload['permutation_tests']['recent_500']['p_emp']:.4f} / "
            f"{payload['permutation_tests']['recent_1500']['p_emp']:.4f}"
        ),
        (
            f"- 150/500/1500 Cohen's d: "
            f"{payload['permutation_tests']['recent_150']['cohens_d']:.3f} / "
            f"{payload['permutation_tests']['recent_500']['cohens_d']:.3f} / "
            f"{payload['permutation_tests']['recent_1500']['cohens_d']:.3f}"
        ),
        (
            f"- Per-bet efficiency: "
            f"{payload['candidate_windows']['recent_150']['per_bet_efficiency_pct']:.1f}% / "
            f"{payload['candidate_windows']['recent_500']['per_bet_efficiency_pct']:.1f}% / "
            f"{payload['candidate_windows']['recent_1500']['per_bet_efficiency_pct']:.1f}%"
        ),
        f"- Leakage check: {payload['leakage_check']['status']}",
    ]
    if payload["mcnemar_500"]["status"] == "COMPUTED":
        lines.append(
            f"- McNemar 500p vs baseline: p={payload['mcnemar_500']['p_value']:.4f}, "
            f"net={payload['mcnemar_500']['net']:+d}"
        )
    else:
        lines.append(f"- McNemar 500p vs baseline: skipped ({payload['mcnemar_500']['reason']})")

    blockers = payload["top_3_blockers"]
    if blockers:
        lines.append("- Top blockers:")
        for blocker in blockers:
            lines.append(f"  - {blocker}")
    return "\n".join(lines)


def main() -> None:
    draws = load_draws()
    stage0 = load_stage0_metrics()
    total_draws = len(draws)

    windows = {
        "recent_150": list(range(max(MIN_HISTORY, total_draws - 150), total_draws)),
        "recent_500": list(range(max(MIN_HISTORY, total_draws - 500), total_draws)),
        "recent_1500": list(range(max(MIN_HISTORY, total_draws - 1500), total_draws)),
    }

    leakage_check = run_leakage_check()

    baseline_eval = {
        name: evaluate_targets(draws, indices, baseline_predictor)
        for name, indices in windows.items()
    }
    candidate_eval = {
        name: evaluate_targets(draws, indices, candidate_predictor)
        for name, indices in windows.items()
    }

    baseline_windows = {name: summarize_window(value) for name, value in baseline_eval.items()}
    candidate_windows = {name: summarize_window(value) for name, value in candidate_eval.items()}
    window_comparison = {
        name: compare_windows(candidate_windows[name], baseline_windows[name])
        for name in windows
    }

    permutation_tests = {
        name: run_perm_window(draws, indices, candidate_predictor_bets)
        for name, indices in windows.items()
    }

    edge_pass = all(candidate_windows[name]["edge"] > 0 for name in windows)
    perm_pass = all(permutation_tests[name]["p_emp"] < 0.05 for name in windows)
    d_pass = all(permutation_tests[name]["cohens_d"] > 1.0 for name in windows)
    efficiency_pass = all(candidate_windows[name]["per_bet_efficiency_pass"] for name in windows)
    leakage_pass = leakage_check["status"] == "PASS"

    if edge_pass and perm_pass and d_pass:
        mcnemar_500 = mcnemar_against_baseline(draws, windows["recent_500"])
    else:
        reasons = []
        if not edge_pass:
            reasons.append("edge gate not fully passed")
        if not perm_pass:
            reasons.append("permutation p gate not fully passed")
        if not d_pass:
            reasons.append("Cohen's d gate not fully passed")
        mcnemar_500 = {
            "status": "SKIPPED",
            "reason": ", ".join(reasons),
            "pass": False,
        }

    verdict = (
        "PASS"
        if edge_pass and perm_pass and d_pass and efficiency_pass and leakage_pass and mcnemar_500["pass"]
        else "REJECT"
    )

    benchmark_refs = {
        "baseline": {
            name: benchmark_reference(baseline_predictor, "midfreq_fourier_2bet", len(indices))
            for name, indices in windows.items()
        },
        "candidate": {
            name: benchmark_reference(candidate_predictor_bets, "midfreq_fourier_2bet_regime_gate_v1", len(indices))
            for name, indices in windows.items()
        },
    }

    diagnostics = {
        "generated_at": now_iso_taipei(),
        "strategy": "midfreq_fourier_2bet_regime_gate_v1",
        "diagnostic_method": [
            "Baseline/candidate evaluated on identical contiguous windows",
            "Regime buckets: previous draw sum bucket, parity bucket, hot-density bucket",
            "Gate precedence: mean10_sum_low first, then prev_hot_overlap>=4, else baseline residual",
        ],
        "windows": {
            name: build_bucket_diagnostics(name, baseline_eval[name], candidate_eval[name])
            for name in windows
        },
        "gate_definition": {
            "rule_1": "If rolling mean of previous 10 draw sums < 114, replace bet2 with 60-draw cold residual bet.",
            "rule_2": "Else if previous draw overlaps with 30-draw hot-12 set on >=4 numbers, replace bet2 with 60-draw hot residual bet.",
            "rule_3": "Else keep baseline Fourier residual bet2.",
        },
    }

    payload = {
        "generated_at": now_iso_taipei(),
        "lottery_type": "POWER_LOTTO",
        "strategy": "midfreq_fourier_2bet_regime_gate_v1",
        "baseline_strategy": "midfreq_fourier_2bet",
        "seed": SEED,
        "n_perm": N_PERM,
        "source_files": {
            "db": "lottery_api/data/lottery_v2.db",
            "baseline_predictor": "tools/power_midfreq_fourier.py",
            "benchmark_framework": "lottery_api/utils/benchmark_framework.py",
            "permutation_test": "lottery_api/engine/perm_test.py",
            "leakage_check": "tools/verify_no_data_leakage.py",
            "baseline_reference": "analysis/results/stage0_baseline.json",
            "diagnostics": os.path.relpath(DIAG_PATH, PROJECT_ROOT),
        },
        "db_query": DB_QUERY,
        "draw_count_total": total_draws,
        "baselines": {
            "single_bet_hit_rate_pct": round(BASELINE_1BET * 100.0, 4),
            "two_bet_hit_rate_pct": round(BASELINE_2BET * 100.0, 4),
        },
        "candidate_design": {
            "name": "midfreq_fourier_2bet_regime_gate_v1",
            "thesis": (
                "Repair the 150p drawdown by switching bet2 away from Fourier only when a "
                "low-sum regime or hot-cluster continuation regime is detected from history-only signals."
            ),
            "gate_priority": [
                "mean10_sum_low -> cold_residual_60",
                "prev_hot_overlap>=4 -> hot_residual_60",
                "default -> baseline Fourier residual",
            ],
        },
        "baseline_windows": baseline_windows,
        "candidate_windows": candidate_windows,
        "window_comparison": window_comparison,
        "permutation_tests": permutation_tests,
        "mcnemar_500": mcnemar_500,
        "leakage_check": leakage_check,
        "benchmark_framework_reference": benchmark_refs,
        "monitoring_references": {
            "fourier_rhythm_3bet_stage0_edge_pct": stage0["fourier_rhythm_3bet"]["edge_pct"],
            "fourier_rhythm_3bet_stage0_sharpe": stage0["fourier_rhythm_3bet"]["sharpe_bernoulli"],
            "pp3_freqort_4bet_stage0_edge_pct": stage0["pp3_freqort_4bet"]["edge_pct"],
            "pp3_freqort_4bet_stage0_sharpe": stage0["pp3_freqort_4bet"]["sharpe_bernoulli"],
        },
        "diagnostics_file": os.path.relpath(DIAG_PATH, PROJECT_ROOT),
        "verdict": verdict,
        "summary": {
            "edge_pass": edge_pass,
            "permutation_pass": perm_pass,
            "cohens_d_pass": d_pass,
            "efficiency_pass": efficiency_pass,
            "leakage_pass": leakage_pass,
            "mcnemar_pass": bool(mcnemar_500.get("pass")),
        },
        "changed_files_list": [
            "tools/validate_power_midfreq2bet_regime_gate_v1.py",
            "analysis/results/power_midfreq2bet_regime_gate_v1_20260423.json",
            "analysis/results/power_midfreq2bet_regime_gate_v1_diagnostics_20260423.json",
        ],
    }
    payload["top_3_blockers"] = build_top_blockers(payload)
    payload["completed_markdown"] = build_completed_markdown(payload)
    payload["task_result_json"] = {
        "strategy": payload["strategy"],
        "verdict": verdict,
        "edge_pct": {name: payload["candidate_windows"][name]["edge_pct"] for name in windows},
        "perm_p": {name: payload["permutation_tests"][name]["p_emp"] for name in windows},
        "cohens_d": {name: payload["permutation_tests"][name]["cohens_d"] for name in windows},
        "per_bet_efficiency_pct": {
            name: payload["candidate_windows"][name]["per_bet_efficiency_pct"] for name in windows
        },
        "mcnemar_500": payload["mcnemar_500"],
        "leakage_check": payload["leakage_check"]["status"],
        "top_3_blockers": payload["top_3_blockers"],
    }

    os.makedirs(os.path.dirname(DIAG_PATH), exist_ok=True)
    with open(DIAG_PATH, "w", encoding="utf-8") as f:
        json.dump(diagnostics, f, ensure_ascii=False, indent=2)
        f.write("\n")

    with open(RESULT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(payload["completed_markdown"])
    print(f"\nSaved: {os.path.relpath(RESULT_PATH, PROJECT_ROOT)}")
    print(f"Saved: {os.path.relpath(DIAG_PATH, PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
