#!/usr/bin/env python3
"""
H012 - DAILY_539 cross-draw cluster / transition residual research.

Research contract:
  - seed=42
  - n_perm=200
  - strict walk-forward with no future leakage
  - evaluate 150 / 500 / 1500 windows
  - only trigger McNemar when a candidate clears the first three gates

Outputs:
  - analysis/results/daily539_h012_cluster_research_20260422.json
  - analysis/results/daily539_h012_cluster_research_20260422.md
  - analysis/results/daily539_h012_cluster_no_leakage_20260422.txt
"""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Dict, List, Optional, Sequence

import numpy as np

try:
    from scipy.stats import binomtest
except ImportError:  # pragma: no cover - repo environment normally has scipy
    binomtest = None


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "lottery_api"))

from lottery_api.database import DatabaseManager
from lottery_api.engine.perm_test import perm_test
from tools.quick_predict import _539_acb_bet, _539_markov_bet, _539_midfreq_bet


SEED = 42
N_PERM = 200
MIN_HISTORY = 300
PERM_WARMUP = 900
WINDOWS = [150, 500, 1500]
POOL = 39
PICK = 5
GAME = "DAILY_539"
DATE_TAG = "20260422"

RESULTS_DIR = os.path.join(PROJECT_ROOT, "analysis", "results")
JSON_PATH = os.path.join(RESULTS_DIR, f"daily539_h012_cluster_research_{DATE_TAG}.json")
MD_PATH = os.path.join(RESULTS_DIR, f"daily539_h012_cluster_research_{DATE_TAG}.md")
LEAKAGE_PATH = os.path.join(RESULTS_DIR, f"daily539_h012_cluster_no_leakage_{DATE_TAG}.txt")

BASELINES = {1: 0.1140, 2: 0.2154, 3: 0.3050}
PRIZE_TABLE = {2: 50, 3: 300, 4: 20_000, 5: 4_000_000}
TRANSITION_LAG_WEIGHTS = {1: 1.00, 2: 0.55, 3: 0.30}
ACTIVE_SEED_WEIGHTS = {1: 1.00, 2: 0.70, 3: 0.45}


@dataclass(frozen=True)
class Candidate:
    name: str
    label: str
    num_bets: int
    strategy_fn: Callable[[List[Dict]], List[List[int]]]
    incumbent_name: str
    incumbent_label: str
    incumbent_fn: Callable[[List[Dict]], List[List[int]]]


def ensure_results_dir() -> None:
    os.makedirs(RESULTS_DIR, exist_ok=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Research DAILY_539 H012 temporal-cluster hypothesis.")
    parser.add_argument("--leakage-audit-only", action="store_true", help="Print only H012 leakage audit.")
    return parser.parse_args()


def load_draws() -> List[Dict]:
    db_path = os.path.join(PROJECT_ROOT, "lottery_api", "data", "lottery_v2.db")
    db = DatabaseManager(db_path=db_path)
    raw = db.get_all_draws(GAME)
    draws = []
    for item in raw:
        numbers = item["numbers"]
        if isinstance(numbers, str):
            numbers = json.loads(numbers)
        dt = datetime.strptime(item["date"], "%Y/%m/%d").date()
        draws.append(
            {
                "draw": str(item["draw"]),
                "date": item["date"],
                "dt": dt,
                "numbers": sorted(int(n) for n in numbers),
            }
        )
    draws.sort(key=lambda d: (d["dt"], int(d["draw"])))
    for idx, draw in enumerate(draws[:-1]):
        draw["next_date"] = draws[idx + 1]["dt"]
    draws[-1]["next_date"] = None
    return draws


def infer_target_date(history: Sequence[Dict]):
    next_date = history[-1].get("next_date")
    if next_date is None:
        raise ValueError("next_date missing on last history draw")
    return next_date


def validate_bet(bet: Sequence[int]) -> List[int]:
    numbers = sorted(int(n) for n in bet)
    if len(numbers) != PICK or len(set(numbers)) != PICK:
        raise ValueError(f"invalid bet length or duplicates: {bet}")
    if any(n < 1 or n > POOL for n in numbers):
        raise ValueError(f"bet out of range: {bet}")
    return numbers


def draw_payout(match_counts: Sequence[int]) -> float:
    return float(sum(PRIZE_TABLE.get(mc, 0) for mc in match_counts))


def draw_profit(match_counts: Sequence[int]) -> float:
    return draw_payout(match_counts) - 50 * len(match_counts)


def hit_rate(records: Sequence[Dict], key: str) -> float:
    if not records:
        return 0.0
    return float(np.mean([1.0 if r[key] else 0.0 for r in records]))


def bernoulli_sharpe(rate: float, baseline: float) -> float:
    if rate <= 0 or rate >= 1:
        return 0.0
    return (rate - baseline) / math.sqrt(rate * (1 - rate))


def top5_from_scores(scores: Dict[int, float]) -> List[int]:
    ranked = sorted(scores, key=lambda n: (-scores[n], n))
    return sorted(ranked[:PICK])


def temporal_cluster_scores(
    history: Sequence[Dict],
    *,
    exclude: Optional[set] = None,
    transition_window: int = 420,
    cluster_window: int = 210,
) -> Dict[int, float]:
    exclude = exclude or set()
    scores = {n: 0.0 for n in range(1, POOL + 1) if n not in exclude}

    recent_transition = history[-transition_window:]
    recent_cluster = history[-cluster_window:]

    active_seed_weights: Counter = Counter()
    for lag, weight in ACTIVE_SEED_WEIGHTS.items():
        if len(history) >= lag:
            for number in history[-lag]["numbers"]:
                active_seed_weights[number] += weight

    transition_positions = defaultdict(list)
    for idx, draw in enumerate(recent_transition):
        for number in draw["numbers"]:
            transition_positions[number].append(idx)

    cluster_positions = defaultdict(list)
    for idx, draw in enumerate(recent_cluster):
        for number in draw["numbers"]:
            cluster_positions[number].append(idx)

    recent = history[-100:]
    freq = Counter(n for draw in recent for n in draw["numbers"])
    expected = len(recent) * PICK / POOL if recent else 0.0
    last_seen = {n: idx for idx, draw in enumerate(recent) for n in draw["numbers"]}

    for seed, seed_weight in active_seed_weights.items():
        transition_counts: Counter = Counter()
        transition_total = 0.0
        for pos in transition_positions.get(seed, []):
            for lag, weight in TRANSITION_LAG_WEIGHTS.items():
                future_idx = pos + lag
                if future_idx >= len(recent_transition):
                    continue
                for number in recent_transition[future_idx]["numbers"]:
                    if number in scores:
                        transition_counts[number] += weight
                        transition_total += weight

        cluster_counts: Counter = Counter()
        cluster_total = 0.0
        for pos in cluster_positions.get(seed, []):
            block = set()
            for future_idx in range(pos, min(pos + 3, len(recent_cluster))):
                block.update(recent_cluster[future_idx]["numbers"])
            for number in block:
                if number in scores and number != seed:
                    cluster_counts[number] += 1.0
                    cluster_total += 1.0

        for number in scores:
            if transition_total > 0:
                scores[number] += seed_weight * 1.10 * transition_counts.get(number, 0) / transition_total
            if cluster_total > 0:
                scores[number] += seed_weight * 0.60 * cluster_counts.get(number, 0) / cluster_total

    for number in list(scores):
        gap_bonus = 0.0
        deficit_bonus = 0.0
        if recent:
            gap_bonus = (len(recent) - last_seen.get(number, -1)) / max(len(recent) / 2, 1)
            deficit_bonus = (expected - freq.get(number, 0)) / max(expected, 1.0)
        scores[number] += 0.18 * gap_bonus + 0.08 * deficit_bonus
        if number <= 5 or number >= 35:
            scores[number] *= 1.02

    return scores


def cluster_residual_1bet(history: List[Dict]) -> List[List[int]]:
    return [top5_from_scores(temporal_cluster_scores(history))]


def acb_cluster_overlay_2bet(history: List[Dict]) -> List[List[int]]:
    bet1 = _539_acb_bet(history)
    bet2 = top5_from_scores(temporal_cluster_scores(history, exclude=set(bet1)))
    return [bet1, bet2]


def acb_markov_cluster_3bet(history: List[Dict]) -> List[List[int]]:
    bet1 = _539_acb_bet(history)
    bet2 = _539_markov_bet(history, exclude=set(bet1))
    bet3 = top5_from_scores(temporal_cluster_scores(history, exclude=set(bet1) | set(bet2)))
    return [bet1, bet2, bet3]


def incumbent_acb_1bet(history: List[Dict]) -> List[List[int]]:
    return [_539_acb_bet(history)]


def incumbent_midfreq_acb_2bet(history: List[Dict]) -> List[List[int]]:
    bet1 = _539_midfreq_bet(history)
    bet2 = _539_acb_bet(history, exclude=set(bet1))
    return [bet1, bet2]


def incumbent_acb_markov_midfreq_3bet(history: List[Dict]) -> List[List[int]]:
    bet1 = _539_acb_bet(history)
    bet2 = _539_markov_bet(history, exclude=set(bet1))
    bet3 = _539_midfreq_bet(history, exclude=set(bet1) | set(bet2))
    return [bet1, bet2, bet3]


CANDIDATES = [
    Candidate(
        name="cluster_residual_1bet",
        label="Temporal-cluster residual 1-bet",
        num_bets=1,
        strategy_fn=cluster_residual_1bet,
        incumbent_name="acb_1bet",
        incumbent_label="ACB 1-bet",
        incumbent_fn=incumbent_acb_1bet,
    ),
    Candidate(
        name="acb_cluster_overlay_2bet",
        label="ACB + temporal-cluster overlay 2-bet",
        num_bets=2,
        strategy_fn=acb_cluster_overlay_2bet,
        incumbent_name="midfreq_acb_2bet",
        incumbent_label="MidFreq + ACB 2-bet",
        incumbent_fn=incumbent_midfreq_acb_2bet,
    ),
    Candidate(
        name="acb_markov_cluster_3bet",
        label="ACB + Markov + temporal-cluster 3-bet",
        num_bets=3,
        strategy_fn=acb_markov_cluster_3bet,
        incumbent_name="acb_markov_midfreq_3bet",
        incumbent_label="ACB + Markov + MidFreq 3-bet",
        incumbent_fn=incumbent_acb_markov_midfreq_3bet,
    ),
]


def verify_slice_integrity(history: Sequence[Dict], target: Dict) -> None:
    if not history:
        raise ValueError("history is empty")
    latest = history[-1]
    if int(latest["draw"]) >= int(target["draw"]):
        raise ValueError(f"draw leakage detected: train={latest['draw']} target={target['draw']}")
    if latest["dt"] >= target["dt"]:
        raise ValueError(f"date leakage detected: train={latest['date']} target={target['date']}")
    expected_target = latest.get("next_date")
    if expected_target and expected_target != target["dt"]:
        raise ValueError(f"next_date mismatch: expected={expected_target} actual={target['dt']}")


def simulate_strategy(draws: Sequence[Dict], strategy_fn: Callable[[List[Dict]], List[List[int]]], num_bets: int) -> List[Dict]:
    records: List[Dict] = []
    for idx in range(MIN_HISTORY, len(draws)):
        history = list(draws[:idx])
        target = draws[idx]
        verify_slice_integrity(history, target)
        bets = strategy_fn(history)
        if len(bets) != num_bets:
            raise ValueError(f"strategy returned {len(bets)} bets, expected {num_bets}")
        bets = [validate_bet(bet) for bet in bets]
        actual = set(target["numbers"])
        match_counts = [len(set(bet) & actual) for bet in bets]
        record = {
            "draw": target["draw"],
            "date": target["date"],
            "match_counts": match_counts,
        }
        for bet_idx in range(1, num_bets + 1):
            partial = match_counts[:bet_idx]
            record[f"is_m2plus_{bet_idx}"] = any(m >= 2 for m in partial)
        records.append(record)
    return records


def window_metrics(records: Sequence[Dict], num_bets: int, window: int) -> Dict:
    subset = list(records[-window:])
    rate = hit_rate(subset, f"is_m2plus_{num_bets}")
    edge = rate - BASELINES[num_bets]
    max_matches = [max(r["match_counts"][:num_bets]) for r in subset]
    payouts = [draw_payout(r["match_counts"][:num_bets]) for r in subset]
    profits = [draw_profit(r["match_counts"][:num_bets]) for r in subset]
    roi = (sum(payouts) - len(subset) * num_bets * 50) / max(len(subset) * num_bets * 50, 1)
    match_summary = {
        "m2_plus_hits": int(sum(1 for m in max_matches if m >= 2)),
        "m3_plus_hits": int(sum(1 for m in max_matches if m >= 3)),
        "m4_plus_hits": int(sum(1 for m in max_matches if m >= 4)),
        "m5_hits": int(sum(1 for m in max_matches if m >= 5)),
    }
    return {
        "window": window,
        "baseline": round(BASELINES[num_bets] * 100, 2),
        "hit_rate": round(rate * 100, 2),
        "edge": round(edge * 100, 2),
        "sharpe": round(bernoulli_sharpe(rate, BASELINES[num_bets]), 3),
        "monetary_roi_pct": round(roi * 100, 2),
        "avg_profit_per_draw": round(float(np.mean(profits)), 2),
        "match_summary": match_summary,
    }


def evaluate_bet_efficiency(records: Sequence[Dict], num_bets: int, window: int) -> List[Dict]:
    subset = list(records[-window:])
    efficiencies = []
    prev_rate = 0.0
    prev_baseline = 0.0
    for bet_idx in range(1, num_bets + 1):
        rate = hit_rate(subset, f"is_m2plus_{bet_idx}")
        baseline = BASELINES[bet_idx]
        if bet_idx == 1:
            efficiency = 100.0
        else:
            numerator = rate - prev_rate
            denominator = baseline - prev_baseline
            efficiency = 100.0 * numerator / denominator if denominator > 0 else 0.0
        efficiencies.append(
            {
                "bet": bet_idx,
                "cumulative_hit_rate": round(rate * 100, 2),
                "incremental_efficiency_pct": round(efficiency, 2),
            }
        )
        prev_rate = rate
        prev_baseline = baseline
    return efficiencies


def mcnemar_from_records(
    candidate_records: Sequence[Dict],
    incumbent_records: Sequence[Dict],
    num_bets: int,
    window: int,
) -> Dict:
    cand_hits = [bool(r[f"is_m2plus_{num_bets}"]) for r in candidate_records[-window:]]
    inc_hits = [bool(r[f"is_m2plus_{num_bets}"]) for r in incumbent_records[-window:]]
    b = sum(1 for cand_hit, inc_hit in zip(cand_hits, inc_hits) if cand_hit and not inc_hit)
    c = sum(1 for cand_hit, inc_hit in zip(cand_hits, inc_hits) if (not cand_hit) and inc_hit)
    total = b + c
    if total == 0:
        p_value = 1.0
    elif binomtest is not None:
        p_value = float(binomtest(b, total, 0.5).pvalue)
    else:
        z = abs(b - c) / math.sqrt(total)
        p_value = math.erfc(z / math.sqrt(2))
    return {
        "window": window,
        "triggered": True,
        "candidate_only": int(b),
        "incumbent_only": int(c),
        "net": int(b - c),
        "p_value": round(p_value, 4),
    }


def get_perm_slice(draws: Sequence[Dict], window: int) -> List[Dict]:
    slice_start = len(draws) - (window + PERM_WARMUP)
    if slice_start < 0:
        raise ValueError(f"insufficient draws for window={window}")
    return [dict(draw) for draw in draws[slice_start:]]


def permutation_metrics(draws: Sequence[Dict], strategy_fn: Callable[[List[Dict]], List[List[int]]], num_bets: int, window: int) -> Dict:
    perm_result = perm_test(
        history=get_perm_slice(draws, window),
        predict_fn=strategy_fn,
        baseline=BASELINES[num_bets],
        hit_fn=lambda bet, actual: len(set(bet) & actual) >= 2,
        min_history=PERM_WARMUP,
        n_perm=N_PERM,
        seed=SEED,
        verbose=False,
    )
    return {
        "window": window,
        "real_rate": round(perm_result["real_rate"] * 100, 2),
        "edge": round(perm_result["real_edge"] * 100, 2),
        "p_value": round(float(perm_result["p_emp"]), 4),
        "cohens_d": round(float(perm_result["cohens_d"]), 3),
        "shuffle_mean_edge": round(float(perm_result["shuffle_mean"]) * 100, 2),
        "shuffle_std_edge": round(float(perm_result["shuffle_std"]) * 100, 2),
        "n_oos": int(perm_result["n_oos"]),
        "n_perm": int(perm_result["n_perm"]),
    }


def random_overlap_ge2_rate() -> float:
    total = math.comb(POOL, PICK)
    probability = 0.0
    for overlap in range(2, PICK + 1):
        probability += math.comb(PICK, overlap) * math.comb(POOL - PICK, PICK - overlap) / total
    return probability


def exploratory_cluster_stats(draws: Sequence[Dict]) -> Dict:
    expected_mean_overlap = PICK * PICK / POOL
    expected_ge2_rate = random_overlap_ge2_rate()
    lag_stats = {}
    for lag in [1, 2, 3]:
        overlaps = [len(set(draws[idx]["numbers"]) & set(draws[idx + lag]["numbers"])) for idx in range(len(draws) - lag)]
        lag_stats[str(lag)] = {
            "mean_overlap": round(float(np.mean(overlaps)), 3),
            "overlap_ge2_rate": round(float(np.mean([1.0 if item >= 2 else 0.0 for item in overlaps])), 4),
        }
    return {
        "expected_mean_overlap_random": round(expected_mean_overlap, 3),
        "expected_overlap_ge2_rate_random": round(expected_ge2_rate, 4),
        "lag_stats": lag_stats,
    }


def build_window_failures(candidate: Dict) -> Dict[str, List[str]]:
    failures: Dict[str, List[str]] = {}
    for window in WINDOWS:
        key = str(window)
        item = candidate["windows"][key]
        metrics = item["metrics"]
        perm = item["permutation"]
        eff = item["marginal_efficiency"]
        mc = item["mcnemar_vs_incumbent"]
        window_failures: List[str] = []
        if metrics["edge"] <= 0:
            window_failures.append("edge<=0")
        if perm["p_value"] >= 0.05:
            window_failures.append("perm>=0.05")
        if perm["cohens_d"] <= 1.0:
            window_failures.append("d<=1.0")
        if any(part["incremental_efficiency_pct"] < 80.0 for part in eff[1:]):
            window_failures.append("eff<80")
        if mc.get("triggered"):
            if mc["p_value"] >= 0.05:
                window_failures.append("mcnemar>=0.05")
            if mc["net"] <= 0:
                window_failures.append("mcnemar_net<=0")
        failures[key] = window_failures
    return failures


def run_h012_leakage_audit(draws: Sequence[Dict]) -> str:
    lines = []
    lines.append("=" * 80)
    lines.append("H012 DAILY_539 leakage audit")
    lines.append("=" * 80)
    sample_indices = [len(draws) - 1500, len(draws) - 500, len(draws) - 150]
    for idx in sample_indices:
        history = draws[:idx]
        target = draws[idx]
        verify_slice_integrity(history, target)
        inferred = infer_target_date(history)
        preview = cluster_residual_1bet(list(history))[0]
        lines.append(
            f"target={target['draw']} {target['date']} | train_last={history[-1]['draw']} {history[-1]['date']} | "
            f"inferred_target_date={inferred.isoformat()} | preview_cluster_bet={preview}"
        )
    lines.append("All sampled H012 slices passed: train draw/date < target and next_date matched target date.")
    return "\n".join(lines) + "\n"


def build_candidate_summary(draws: Sequence[Dict], candidate: Candidate) -> Dict:
    print(f"[candidate] {candidate.name}", flush=True)
    candidate_records = simulate_strategy(draws, candidate.strategy_fn, candidate.num_bets)
    incumbent_records = simulate_strategy(draws, candidate.incumbent_fn, candidate.num_bets)
    windows = {}
    edge_positive_all = True
    perm_pass_all = True
    d_pass_all = True
    eff_pass_all = True

    for window in WINDOWS:
        print(f"  [window] {candidate.name} -> {window}", flush=True)
        wm = window_metrics(candidate_records, candidate.num_bets, window)
        pm = permutation_metrics(draws, candidate.strategy_fn, candidate.num_bets, window)
        eff = evaluate_bet_efficiency(candidate_records, candidate.num_bets, window)
        windows[str(window)] = {
            "metrics": wm,
            "permutation": pm,
            "marginal_efficiency": eff,
        }
        edge_positive_all &= wm["edge"] > 0
        perm_pass_all &= pm["p_value"] < 0.05
        d_pass_all &= pm["cohens_d"] > 1.0
        eff_pass_all &= all(item["incremental_efficiency_pct"] >= 80.0 for item in eff[1:])

    mcnemar_triggered = edge_positive_all and perm_pass_all and d_pass_all
    mcnemar_ready = False
    if mcnemar_triggered:
        mcnemar_ready = True
        for window in WINDOWS:
            mc = mcnemar_from_records(candidate_records, incumbent_records, candidate.num_bets, window)
            windows[str(window)]["mcnemar_vs_incumbent"] = mc
            mcnemar_ready &= mc["p_value"] < 0.05 and mc["net"] > 0
    else:
        for window in WINDOWS:
            windows[str(window)]["mcnemar_vs_incumbent"] = {
                "window": window,
                "triggered": False,
                "reason": "前三閘門未過，不執行替換檢定",
            }

    if edge_positive_all and perm_pass_all and d_pass_all and eff_pass_all and mcnemar_ready:
        status = "PASS"
        rationale = "三窗口全正、perm 全過、Cohen's d 全過、邊際效率全過，且 McNemar 證明可替換現役。"
    elif edge_positive_all and perm_pass_all and d_pass_all and eff_pass_all:
        status = "WATCH"
        rationale = "候選有穩定 raw signal，但 McNemar 未證明能替換現役。"
    else:
        status = "REJECT"
        reasons = []
        if not edge_positive_all:
            reasons.append("三窗口 Edge 未全正")
        if not perm_pass_all:
            reasons.append("permutation p 未全窗口 < 0.05")
        if not d_pass_all:
            reasons.append("Cohen's d 未全窗口 > 1.0")
        if not eff_pass_all:
            reasons.append("多注邊際效率未全窗口 > 80%")
        if mcnemar_triggered and not mcnemar_ready:
            reasons.append("McNemar 未證明可替換現役")
        elif not mcnemar_triggered:
            reasons.append("未進入 McNemar 替換閘")
        rationale = "；".join(reasons)

    summary = {
        "name": candidate.name,
        "label": candidate.label,
        "num_bets": candidate.num_bets,
        "incumbent": {"name": candidate.incumbent_name, "label": candidate.incumbent_label},
        "status": status,
        "rationale": rationale,
        "mcnemar_triggered": mcnemar_triggered,
        "windows": windows,
    }
    summary["failed_gates_by_window"] = build_window_failures(summary)
    return summary


def generate_leakage_artifact(draws: Sequence[Dict]) -> Dict:
    cmd = [sys.executable, os.path.join(PROJECT_ROOT, "tools", "verify_no_data_leakage.py")]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    h012_audit = run_h012_leakage_audit(draws)
    sections = [
        "=== tools/verify_no_data_leakage.py ===",
        proc.stdout.strip(),
        "",
        "=== H012-specific leakage audit ===",
        h012_audit.strip(),
    ]
    if proc.stderr.strip():
        sections.extend(["", "=== stderr ===", proc.stderr.strip()])
    with open(LEAKAGE_PATH, "w", encoding="utf-8") as handle:
        handle.write("\n".join(sections).strip() + "\n")
    return {
        "path": LEAKAGE_PATH,
        "formal_checker_exit_code": proc.returncode,
        "formal_checker_passed": proc.returncode == 0,
        "h012_slice_checks_passed": True,
    }


def choose_top_verdict(candidate_summaries: Sequence[Dict]) -> str:
    if any(item["status"] == "PASS" for item in candidate_summaries):
        return "PASS"
    if any(item["status"] == "WATCH" for item in candidate_summaries):
        return "WATCH"
    return "REJECT"


def build_next_planner_recommendation(verdict: str) -> str:
    if verdict == "PASS":
        return (
            "H012 cluster/transition produced a promotion-grade candidate. Keep the research script as the canonical "
            "artifact, then prepare the minimum RSM change set with a narrow incumbent replacement note."
        )
    if verdict == "WATCH":
        return (
            "Do not promote into RSM yet. Keep the candidate in shadow only if a future 200-period monitor preserves "
            "the same three-window profile; otherwise move 539 closer to signal-exhaustion handling."
        )
    return (
        "REJECT H012 cluster/transition overlays for DAILY_539 under current data. The family can generate some "
        "medium/long-window raw edge, but not a stable three-window, permutation-confirmed, incumbent-beating "
        "signal. DAILY_539 should be treated as even closer to signal exhaustion; only exogenous data or materially "
        "different pool-size / market-behavior signals are still worth testing."
    )


def write_markdown(report: Dict) -> None:
    lines = []
    lines.append("# DAILY_539 H012 Cross-Draw Cluster / Transition Research (2026-04-22)")
    lines.append("")
    lines.append(f"**Verdict:** {report['verdict']}")
    lines.append("")
    lines.append("## Reproducibility")
    lines.append("")
    lines.append(f"- Command: `{report['reproducibility']['command']}`")
    lines.append(
        f"- Params: seed={report['seed']}, n_perm={report['n_perm']}, min_history={report['min_history']}, "
        f"perm_warmup={report['perm_warmup']}, windows={report['windows']}"
    )
    lines.append(
        f"- Data range: {report['data_range']['first_draw']} ({report['data_range']['first_date']}) → "
        f"{report['data_range']['last_draw']} ({report['data_range']['last_date']}), total draws={report['data_range']['count']}"
    )
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(
        f"- Formal leakage checker: {'PASS' if report['leakage']['formal_checker_passed'] else 'FAIL'} "
        f"(`tools/verify_no_data_leakage.py` -> `{os.path.relpath(LEAKAGE_PATH, PROJECT_ROOT)}`)"
    )
    cluster_stats = report["exploratory_checks"]
    lag1 = cluster_stats["lag_stats"]["1"]
    lag2 = cluster_stats["lag_stats"]["2"]
    lag3 = cluster_stats["lag_stats"]["3"]
    lines.append(
        f"- Cross-draw overlap diagnostics: random baseline mean overlap={cluster_stats['expected_mean_overlap_random']}, "
        f"lag1={lag1['mean_overlap']}, lag2={lag2['mean_overlap']}, lag3={lag3['mean_overlap']}."
    )
    lines.append(
        f"- Random baseline P(overlap>=2)={cluster_stats['expected_overlap_ge2_rate_random']:.4f}; "
        f"observed lag1/2/3={lag1['overlap_ge2_rate']:.4f}/{lag2['overlap_ge2_rate']:.4f}/{lag3['overlap_ge2_rate']:.4f}."
    )
    lines.append(
        "- Decision rule applied: any window edge <= 0, permutation p >= 0.05, Cohen's d <= 1.0, or "
        "marginal efficiency < 80% blocks promotion; McNemar runs only after the first three gates clear."
    )
    lines.append("")
    lines.append("## Candidate Results")
    lines.append("")
    for candidate in report["candidates"]:
        lines.append(f"### {candidate['label']} — {candidate['status']}")
        lines.append("")
        lines.append(f"- Incumbent comparator: `{candidate['incumbent']['name']}`")
        lines.append(f"- Gate summary: {candidate['rationale']}")
        failures = []
        for window in WINDOWS:
            parts = candidate["failed_gates_by_window"][str(window)]
            failures.append(f"{window}: {', '.join(parts) if parts else 'none'}")
        lines.append(f"- Failed gates by window: {' | '.join(failures)}")
        lines.append("")
        lines.append("| Window | Edge | Sharpe | Perm p | Cohen's d | Hit rate | ROI | M2+/M3+/M4+/M5 |")
        lines.append("|---:|---:|---:|---:|---:|---:|---:|---|")
        for window in WINDOWS:
            item = candidate["windows"][str(window)]
            metrics = item["metrics"]
            perm = item["permutation"]
            ms = metrics["match_summary"]
            lines.append(
                f"| {window} | {metrics['edge']:+.2f}% | {metrics['sharpe']:.3f} | "
                f"{perm['p_value']:.4f} | {perm['cohens_d']:.3f} | {metrics['hit_rate']:.2f}% | "
                f"{metrics['monetary_roi_pct']:+.2f}% | {ms['m2_plus_hits']}/{ms['m3_plus_hits']}/"
                f"{ms['m4_plus_hits']}/{ms['m5_hits']} |"
            )
        lines.append("")
        if candidate["num_bets"] > 1:
            lines.append("| Window | Bet | Cum hit rate | Incremental efficiency |")
            lines.append("|---:|---:|---:|---:|")
            for window in WINDOWS:
                for eff in candidate["windows"][str(window)]["marginal_efficiency"]:
                    lines.append(
                        f"| {window} | {eff['bet']} | {eff['cumulative_hit_rate']:.2f}% | "
                        f"{eff['incremental_efficiency_pct']:.2f}% |"
                    )
            lines.append("")
        mc_any = candidate["windows"][str(WINDOWS[0])]["mcnemar_vs_incumbent"].get("triggered", False)
        if mc_any:
            lines.append("| Window | McNemar p vs incumbent | Net discordant wins |")
            lines.append("|---:|---:|---:|")
            for window in WINDOWS:
                mc = candidate["windows"][str(window)]["mcnemar_vs_incumbent"]
                lines.append(f"| {window} | {mc['p_value']:.4f} | {mc['net']:+d} |")
            lines.append("")
        else:
            reason = candidate["windows"][str(WINDOWS[0])]["mcnemar_vs_incumbent"]["reason"]
            lines.append(f"- McNemar: not triggered ({reason})")
            lines.append("")
    lines.append("## Conclusion")
    lines.append("")
    lines.append(
        f"- Signal exhaustion read: {'closer_to_exhaustion' if report['closer_to_signal_exhaustion'] else 'not_yet'}."
    )
    lines.append(report["next_planner_recommendation"])
    lines.append("")
    lines.append("## Handoff Notes")
    lines.append("")
    lines.append(f"- Wiki update: {'applied' if report['wiki_update_required'] else 'wiki 無需更新'}.")
    with open(MD_PATH, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def main() -> int:
    args = parse_args()
    ensure_results_dir()
    draws = load_draws()

    if args.leakage_audit_only:
        sys.stdout.write(run_h012_leakage_audit(draws))
        return 0

    candidate_summaries = [build_candidate_summary(draws, candidate) for candidate in CANDIDATES]
    top_verdict = choose_top_verdict(candidate_summaries)
    leakage = generate_leakage_artifact(draws)
    report = {
        "task": "DAILY_539 H012 cross-draw cluster orthogonal validation",
        "hypothesis": "cross-draw cluster / transition residual",
        "game": GAME,
        "seed": SEED,
        "n_perm": N_PERM,
        "min_history": MIN_HISTORY,
        "perm_warmup": PERM_WARMUP,
        "windows": WINDOWS,
        "data_range": {
            "first_draw": draws[0]["draw"],
            "first_date": draws[0]["date"],
            "last_draw": draws[-1]["draw"],
            "last_date": draws[-1]["date"],
            "count": len(draws),
        },
        "reproducibility": {
            "command": "python3 tools/research_daily539_h012_cluster.py",
        },
        "verdict": top_verdict,
        "exploratory_checks": exploratory_cluster_stats(draws),
        "leakage": leakage,
        "candidates": candidate_summaries,
        "closer_to_signal_exhaustion": top_verdict == "REJECT",
        "next_planner_recommendation": build_next_planner_recommendation(top_verdict),
        "wiki_update_required": True,
    }
    with open(JSON_PATH, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False)
    write_markdown(report)

    print(json.dumps({"verdict": top_verdict, "json": JSON_PATH, "markdown": MD_PATH, "leakage": LEAKAGE_PATH}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
