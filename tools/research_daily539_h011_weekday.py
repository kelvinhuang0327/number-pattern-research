#!/usr/bin/env python3
"""
H011 - DAILY_539 weekday / calendar regime research.

Research contract:
  - seed=42
  - n_perm=200
  - calendar-only pre-draw signals
  - strict walk-forward with no future leakage

Outputs:
  - analysis/results/daily539_h011_weekday_research_20260422.json
  - analysis/results/daily539_h011_weekday_research_20260422.md
  - analysis/results/daily539_h011_weekday_no_leakage_20260422.txt
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
from datetime import date, datetime
from typing import Callable, Dict, List, Optional, Sequence

import numpy as np

try:
    from scipy.stats import binomtest, chi2_contingency
except ImportError:  # pragma: no cover - repo environment normally has scipy
    binomtest = None
    chi2_contingency = None


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "lottery_api"))

from lottery_api.database import DatabaseManager
from lottery_api.engine.perm_test import perm_test


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
JSON_PATH = os.path.join(RESULTS_DIR, f"daily539_h011_weekday_research_{DATE_TAG}.json")
MD_PATH = os.path.join(RESULTS_DIR, f"daily539_h011_weekday_research_{DATE_TAG}.md")
LEAKAGE_PATH = os.path.join(RESULTS_DIR, f"daily539_h011_weekday_no_leakage_{DATE_TAG}.txt")

BASELINES = {1: 0.1140, 2: 0.2154, 3: 0.3050}
PRIZE_TABLE = {2: 50, 3: 300, 4: 20_000, 5: 4_000_000}
WEEKDAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


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
    parser = argparse.ArgumentParser(description="Research DAILY_539 H011 weekday/calendar hypothesis.")
    parser.add_argument("--leakage-audit-only", action="store_true", help="Print only H011 leakage audit.")
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


def month_bucket(day: int) -> int:
    if day <= 10:
        return 0
    if day <= 20:
        return 1
    return 2


def is_month_edge(day: int) -> bool:
    return day <= 5 or day >= 26


def infer_target_date(history: Sequence[Dict]) -> date:
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


def acb_bet(history: Sequence[Dict], exclude: Optional[set] = None, window: int = 100) -> List[int]:
    exclude = exclude or set()
    recent = history[-window:]
    counter = Counter(n for draw in recent for n in draw["numbers"])
    last_seen = {n: idx for idx, draw in enumerate(recent) for n in draw["numbers"]}
    expected = len(recent) * PICK / POOL
    scores = {}
    for number in range(1, POOL + 1):
        if number in exclude:
            continue
        freq_deficit = expected - counter.get(number, 0)
        gap_score = (len(recent) - last_seen.get(number, -1)) / max(len(recent) / 2, 1)
        boundary_bonus = 1.2 if number <= 5 or number >= 35 else 1.0
        mod3_bonus = 1.1 if number % 3 == 0 else 1.0
        scores[number] = (freq_deficit * 0.4 + gap_score * 0.6) * boundary_bonus * mod3_bonus
    ranked = sorted(scores, key=lambda n: (-scores[n], n))
    return sorted(ranked[:PICK])


def midfreq_bet(history: Sequence[Dict], exclude: Optional[set] = None, window: int = 100) -> List[int]:
    exclude = exclude or set()
    recent = history[-window:]
    expected = len(recent) * PICK / POOL
    freq = Counter(n for draw in recent for n in draw["numbers"])
    ranked = sorted(
        [n for n in range(1, POOL + 1) if n not in exclude],
        key=lambda n: (abs(freq.get(n, 0) - expected), n),
    )
    return sorted(ranked[:PICK])


def markov_bet(history: Sequence[Dict], exclude: Optional[set] = None, window: int = 30) -> List[int]:
    exclude = exclude or set()
    recent = history[-window:]
    transitions: Dict[int, Counter] = defaultdict(Counter)
    for idx in range(len(recent) - 1):
        for prev_num in recent[idx]["numbers"]:
            for next_num in recent[idx + 1]["numbers"]:
                transitions[prev_num][next_num] += 1
    scores: Counter = Counter()
    for prev_num in history[-1]["numbers"]:
        total = sum(transitions[prev_num].values())
        if total <= 0:
            continue
        for next_num, count in transitions[prev_num].items():
            scores[next_num] += count / total
    for number in range(1, POOL + 1):
        scores.setdefault(number, 0.0)
    ranked = [n for n in sorted(scores, key=lambda x: (-scores[x], x)) if n not in exclude]
    return sorted(ranked[:PICK])


def subgroup_post_break_flags(draws: Sequence[Dict]) -> List[int]:
    flags: List[int] = []
    for idx, draw in enumerate(draws):
        if idx == 0:
            flags.append(0)
            continue
        gap_days = (draw["dt"] - draws[idx - 1]["dt"]).days
        flags.append(1 if gap_days > 1 else 0)
    return flags


def _subset_component(
    subset: Sequence[Dict],
    recent: Sequence[Dict],
    global_freq: Counter,
    number: int,
) -> float:
    subset_size = len(subset)
    if subset_size < 30:
        return 0.0
    observed = sum(1 for draw in subset if number in draw["numbers"])
    expected = subset_size * (global_freq.get(number, 0) / max(len(recent), 1))
    lift_z = (observed - expected) / math.sqrt(expected + 1.0)
    last_idx = None
    for idx in range(subset_size - 1, -1, -1):
        if number in subset[idx]["numbers"]:
            last_idx = idx
            break
    gap_bonus = 1.0 if last_idx is None else (subset_size - last_idx) / max(subset_size / 2, 1)
    return 0.75 * lift_z + 0.25 * gap_bonus


def calendar_scores(
    history: Sequence[Dict],
    *,
    target_dt: date,
    exclude: Optional[set] = None,
    window: int = 900,
    weights: Optional[Dict[str, float]] = None,
) -> Dict[int, float]:
    exclude = exclude or set()
    weights = weights or {"weekday": 0.55, "month_bucket": 0.25, "post_break": 0.20}
    recent = history[-window:]
    if len(recent) < 30:
        return {n: 0.0 for n in range(1, POOL + 1) if n not in exclude}

    target_weekday = target_dt.weekday()
    target_bucket = month_bucket(target_dt.day)
    target_post_break = 1 if (target_dt - history[-1]["dt"]).days > 1 else 0
    post_break_flags = subgroup_post_break_flags(recent)
    global_freq = Counter(n for draw in recent for n in draw["numbers"])

    subsets = {
        "weekday": [draw for draw in recent if draw["dt"].weekday() == target_weekday],
        "month_bucket": [draw for draw in recent if month_bucket(draw["dt"].day) == target_bucket],
        "post_break": [draw for draw, flag in zip(recent, post_break_flags) if flag == target_post_break],
        "month_edge": [draw for draw in recent if is_month_edge(draw["dt"].day) == is_month_edge(target_dt.day)],
    }

    scores: Dict[int, float] = {}
    expected_global = len(recent) * PICK / POOL
    for number in range(1, POOL + 1):
        if number in exclude:
            continue
        score = 0.0
        for key, weight in weights.items():
            score += weight * _subset_component(subsets[key], recent, global_freq, number)
        if len(subsets["month_edge"]) >= 40:
            score += 0.10 * _subset_component(subsets["month_edge"], recent, global_freq, number)
        freq_deficit = (expected_global - global_freq.get(number, 0)) / max(expected_global, 1.0)
        score += 0.15 * freq_deficit
        if number <= 5 or number >= 35:
            score *= 1.03
        scores[number] = score
    return scores


def top5_from_scores(scores: Dict[int, float]) -> List[int]:
    ranked = sorted(scores, key=lambda n: (-scores[n], n))
    return sorted(ranked[:PICK])


def weekday_residual_1bet(history: List[Dict]) -> List[List[int]]:
    target_dt = infer_target_date(history)
    scores = calendar_scores(
        history,
        target_dt=target_dt,
        window=450,
        weights={"weekday": 1.0, "month_bucket": 0.0, "post_break": 0.0},
    )
    return [top5_from_scores(scores)]


def acb_weekday_overlay_2bet(history: List[Dict]) -> List[List[int]]:
    target_dt = infer_target_date(history)
    bet1 = acb_bet(history)
    bet2 = top5_from_scores(
        calendar_scores(
            history,
            target_dt=target_dt,
            exclude=set(bet1),
            window=450,
            weights={"weekday": 1.0, "month_bucket": 0.0, "post_break": 0.0},
        )
    )
    return [bet1, bet2]


def acb_calendar_overlay_2bet(history: List[Dict]) -> List[List[int]]:
    target_dt = infer_target_date(history)
    bet1 = acb_bet(history)
    bet2 = top5_from_scores(calendar_scores(history, target_dt=target_dt, exclude=set(bet1), window=900))
    return [bet1, bet2]


def acb_markov_calendar_3bet(history: List[Dict]) -> List[List[int]]:
    target_dt = infer_target_date(history)
    bet1 = acb_bet(history)
    bet2 = markov_bet(history, exclude=set(bet1))
    bet3 = top5_from_scores(
        calendar_scores(history, target_dt=target_dt, exclude=set(bet1) | set(bet2), window=900)
    )
    return [bet1, bet2, bet3]


def incumbent_acb_1bet(history: List[Dict]) -> List[List[int]]:
    return [acb_bet(history)]


def incumbent_midfreq_acb_2bet(history: List[Dict]) -> List[List[int]]:
    bet1 = acb_bet(history)
    bet2 = midfreq_bet(history, exclude=set(bet1))
    return [bet1, bet2]


def incumbent_acb_markov_midfreq_3bet(history: List[Dict]) -> List[List[int]]:
    bet1 = acb_bet(history)
    bet2 = markov_bet(history, exclude=set(bet1))
    bet3 = midfreq_bet(history, exclude=set(bet1) | set(bet2))
    return [bet1, bet2, bet3]


CANDIDATES = [
    Candidate(
        name="weekday_residual_1bet",
        label="Weekday residual 1-bet",
        num_bets=1,
        strategy_fn=weekday_residual_1bet,
        incumbent_name="acb_1bet",
        incumbent_label="ACB 1-bet",
        incumbent_fn=incumbent_acb_1bet,
    ),
    Candidate(
        name="acb_calendar_overlay_2bet",
        label="ACB + calendar regime overlay 2-bet",
        num_bets=2,
        strategy_fn=acb_calendar_overlay_2bet,
        incumbent_name="midfreq_acb_2bet",
        incumbent_label="MidFreq + ACB 2-bet",
        incumbent_fn=incumbent_midfreq_acb_2bet,
    ),
    Candidate(
        name="acb_markov_calendar_3bet",
        label="ACB + Markov + calendar regime 3-bet",
        num_bets=3,
        strategy_fn=acb_markov_calendar_3bet,
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
            "weekday": WEEKDAY_LABELS[target["dt"].weekday()],
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
    b = sum(1 for c, i in zip(cand_hits, inc_hits) if c and not i)
    c = sum(1 for c_hit, i in zip(cand_hits, inc_hits) if (not c_hit) and i)
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


def exploratory_weekday_stats(draws: Sequence[Dict]) -> Dict:
    weekday_counts = Counter(draw["dt"].weekday() for draw in draws)
    matrix = np.zeros((7, POOL), dtype=int)
    for draw in draws:
        wd = draw["dt"].weekday()
        for number in draw["numbers"]:
            matrix[wd, number - 1] += 1
    average_rate_range = float(np.mean(np.ptp(matrix, axis=0)))

    per_number_p = []
    bonferroni = 0
    nominal = 0
    if chi2_contingency is not None:
        global_p = float(chi2_contingency(matrix)[1])
        weekday_totals = np.array([weekday_counts.get(i, 0) for i in range(7)], dtype=int)
        for idx in range(POOL):
            present = matrix[:, idx]
            absent = weekday_totals - present
            table = np.vstack([present, absent]).T
            p_val = float(chi2_contingency(table)[1])
            per_number_p.append(p_val)
        nominal = sum(1 for p in per_number_p if p < 0.05)
        threshold = 0.05 / POOL
        bonferroni = sum(1 for p in per_number_p if p < threshold)
    else:
        global_p = 1.0

    return {
        "weekday_counts": {WEEKDAY_LABELS[k]: int(v) for k, v in sorted(weekday_counts.items())},
        "global_chi2_p_value": round(global_p, 4),
        "nominal_p_lt_0_05": int(nominal),
        "bonferroni_survivors": int(bonferroni),
        "avg_weekday_count_range": round(average_rate_range, 2),
    }


def run_h011_leakage_audit(draws: Sequence[Dict]) -> str:
    lines = []
    lines.append("=" * 80)
    lines.append("H011 DAILY_539 leakage audit")
    lines.append("=" * 80)
    sample_indices = [len(draws) - 1500, len(draws) - 500, len(draws) - 150]
    for idx in sample_indices:
        history = draws[:idx]
        target = draws[idx]
        verify_slice_integrity(history, target)
        inferred = infer_target_date(history)
        lines.append(
            f"target={target['draw']} {target['date']} | train_last={history[-1]['draw']} {history[-1]['date']} | "
            f"inferred_target_date={inferred.isoformat()}"
        )
    lines.append("All sampled H011 slices passed: train draw/date < target and next_date matched target date.")
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
    mcnemar_ready = True

    for window in WINDOWS:
        print(f"  [window] {candidate.name} -> {window}", flush=True)
        wm = window_metrics(candidate_records, candidate.num_bets, window)
        pm = permutation_metrics(draws, candidate.strategy_fn, candidate.num_bets, window)
        eff = evaluate_bet_efficiency(candidate_records, candidate.num_bets, window)
        mc = mcnemar_from_records(candidate_records, incumbent_records, candidate.num_bets, window)
        windows[str(window)] = {
            "metrics": wm,
            "permutation": pm,
            "marginal_efficiency": eff,
            "mcnemar_vs_incumbent": mc,
        }
        edge_positive_all &= wm["edge"] > 0
        perm_pass_all &= pm["p_value"] < 0.05
        d_pass_all &= pm["cohens_d"] > 1.0
        eff_pass_all &= all(item["incremental_efficiency_pct"] >= 80.0 for item in eff[1:])
        mcnemar_ready &= mc["p_value"] < 0.05 and mc["net"] > 0

    if edge_positive_all and perm_pass_all and d_pass_all and eff_pass_all and mcnemar_ready:
        status = "PASS"
        rationale = "All three windows cleared edge/perm/d/efficiency and beat the incumbent by McNemar."
    elif edge_positive_all and perm_pass_all and d_pass_all and eff_pass_all:
        status = "WATCH"
        rationale = "Raw signal exists, but McNemar did not prove a ranking change over the incumbent."
    else:
        status = "REJECT"
        reasons = []
        if not edge_positive_all:
            reasons.append("at least one window edge <= 0")
        if not perm_pass_all:
            reasons.append("permutation p-value failed in at least one window")
        if not d_pass_all:
            reasons.append("Cohen's d <= 1.0 in at least one window")
        if not eff_pass_all:
            reasons.append("multi-bet marginal efficiency < 80%")
        rationale = "; ".join(reasons)

    return {
        "name": candidate.name,
        "label": candidate.label,
        "num_bets": candidate.num_bets,
        "incumbent": {"name": candidate.incumbent_name, "label": candidate.incumbent_label},
        "status": status,
        "rationale": rationale,
        "windows": windows,
    }


def generate_leakage_artifact(draws: Sequence[Dict]) -> Dict:
    cmd = [sys.executable, os.path.join(PROJECT_ROOT, "tools", "verify_no_data_leakage.py")]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    h011_audit = run_h011_leakage_audit(draws)
    sections = [
        "=== tools/verify_no_data_leakage.py ===",
        proc.stdout.strip(),
        "",
        "=== H011-specific leakage audit ===",
        h011_audit.strip(),
    ]
    if proc.stderr.strip():
        sections.extend(["", "=== stderr ===", proc.stderr.strip()])
    with open(LEAKAGE_PATH, "w", encoding="utf-8") as handle:
        handle.write("\n".join(sections).strip() + "\n")
    return {
        "path": LEAKAGE_PATH,
        "formal_checker_exit_code": proc.returncode,
        "formal_checker_passed": proc.returncode == 0,
        "h011_slice_checks_passed": True,
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
            "Calendar/weekday H011 produced a promotion candidate. Run a dedicated 500-draw OOS handoff "
            "and incumbent McNemar follow-up before any RSM change."
        )
    if verdict == "WATCH":
        return (
            "Do not promote into RSM yet. Revisit only if a broader exogenous calendar source is added; "
            "otherwise switch to H011 cross-draw clusters or pool-size regime research."
        )
    return (
        "REJECT weekday/calendar overlays for DAILY_539 under current data. Next H011 branch should move to "
        "cross-draw cluster structure or pool-size regime effects, not another weekday retry. With H001-H008 "
        "already exhausted and calendar family also failing, DAILY_539 is closer to a near-exhausted signal space."
    )


def write_markdown(report: Dict) -> None:
    lines = []
    lines.append("# DAILY_539 H011 Weekday / Calendar Regime Research (2026-04-22)")
    lines.append("")
    lines.append(f"**Verdict:** {report['verdict']}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(
        f"- Formal leakage checker: {'PASS' if report['leakage']['formal_checker_passed'] else 'FAIL'} "
        f"(`tools/verify_no_data_leakage.py` -> `{os.path.relpath(LEAKAGE_PATH, PROJECT_ROOT)}`)"
    )
    lines.append(
        f"- Exploratory weekday screen: global chi-square p={report['exploratory_checks']['global_chi2_p_value']}, "
        f"Bonferroni survivors={report['exploratory_checks']['bonferroni_survivors']}."
    )
    lines.append(
        "- Decision rule applied: any window edge <= 0, permutation p >= 0.05, Cohen's d <= 1.0, or "
        "marginal efficiency < 80% blocks promotion."
    )
    lines.append("")
    lines.append("## Candidate Results")
    lines.append("")
    for candidate in report["candidates"]:
        lines.append(f"### {candidate['label']} — {candidate['status']}")
        lines.append("")
        lines.append(f"- Incumbent comparator: `{candidate['incumbent']['name']}`")
        lines.append(f"- Why not RSM: {candidate['rationale']}")
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
        lines.append("| Window | McNemar p vs incumbent | Net discordant wins |")
        lines.append("|---:|---:|---:|")
        for window in WINDOWS:
            mc = candidate["windows"][str(window)]["mcnemar_vs_incumbent"]
            lines.append(f"| {window} | {mc['p_value']:.4f} | {mc['net']:+d} |")
        lines.append("")
    lines.append("## Next Planner Recommendation")
    lines.append("")
    lines.append(report["next_planner_recommendation"])
    lines.append("")
    lines.append("## Handoff Notes")
    lines.append("")
    lines.append(
        "- This round switched away from blocked/repeated POWER_LOTTO work. Do not send "
        "`fourier_rhythm_3bet` 500p OOS or `Winning Quality P2-1` back unchanged next round."
    )
    lines.append(
        f"- Wiki update: {'applied' if report['wiki_update_required'] else 'wiki 無需更新'}."
    )
    with open(MD_PATH, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def main() -> int:
    args = parse_args()
    ensure_results_dir()
    draws = load_draws()

    if args.leakage_audit_only:
        sys.stdout.write(run_h011_leakage_audit(draws))
        return 0

    candidate_summaries = [build_candidate_summary(draws, candidate) for candidate in CANDIDATES]
    top_verdict = choose_top_verdict(candidate_summaries)
    leakage = generate_leakage_artifact(draws)
    report = {
        "task": "DAILY_539 H011 weekday/calendar regime validation",
        "game": GAME,
        "seed": SEED,
        "n_perm": N_PERM,
        "min_history": MIN_HISTORY,
        "perm_warmup": PERM_WARMUP,
        "windows": WINDOWS,
        "verdict": top_verdict,
        "exploratory_checks": exploratory_weekday_stats(draws),
        "leakage": leakage,
        "candidates": candidate_summaries,
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
