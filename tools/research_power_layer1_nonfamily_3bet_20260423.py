#!/usr/bin/env python3
"""
POWER_LOTTO Layer-1 nonfamily 3bet validation (2026-04-23)
===========================================================

Goal:
1. Validate at least four non-PP3 / non-Fourier / non-MidFreq / non-Special /
   non-WQ Layer-1 history-only 3-bet candidates.
2. Use strict 150 / 500 / 1500 OOS windows with seed=42 and 200-shuffle
   fixed-prediction permutation tests.
3. Compare per-bet marginal efficiency against `pp3_freqort_4bet`, and only
   trigger McNemar vs `fourier_rhythm_3bet` when every pre-promotion gate passes.
4. Emit orchestrator-ready JSON / Markdown / diagnostics artifacts plus a saved
   leakage-check transcript under analysis/results/.
"""

from __future__ import annotations

import ast
import json
import math
import os
import sqlite3
import subprocess
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, List, Sequence, Tuple

import numpy as np
from scipy.stats import chi2

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "lottery_api"))

from tools.power_fourier_rhythm import fourier_rhythm_predict
from tools.predict_power_orthogonal_5bet import generate_orthogonal_5bet

SEED = 42
N_PERM = 200
MIN_HISTORY = 200
MAX_NUM = 38
PICK = 6
MATCH_TH = 3
DATE_TAG = "20260423"

WINDOW_SPECS = {
    "recent_150": 150,
    "recent_500": 500,
    "recent_1500": 1500,
}

DB_PATH = os.path.join(PROJECT_ROOT, "lottery_api", "data", "lottery_v2.db")
LEAKAGE_TOOL = os.path.join(PROJECT_ROOT, "tools", "verify_no_data_leakage.py")
STAGE0_PATH = os.path.join(PROJECT_ROOT, "analysis", "results", "stage0_baseline.json")
RESULT_PATH = os.path.join(
    PROJECT_ROOT,
    "analysis",
    "results",
    f"power_layer1_nonfamily_3bet_validation_{DATE_TAG}.json",
)
MARKDOWN_PATH = os.path.join(
    PROJECT_ROOT,
    "analysis",
    "results",
    f"power_layer1_nonfamily_3bet_validation_{DATE_TAG}.md",
)
DIAG_PATH = os.path.join(
    PROJECT_ROOT,
    "analysis",
    "results",
    f"power_layer1_nonfamily_3bet_diagnostics_{DATE_TAG}.json",
)
LEAKAGE_OUTPUT_PATH = os.path.join(
    PROJECT_ROOT,
    "analysis",
    "results",
    f"power_layer1_nonfamily_3bet_leakage_check_{DATE_TAG}.txt",
)
DB_QUERY = (
    "SELECT draw, date, numbers, special, lottery_type "
    "FROM draws WHERE lottery_type = ? ORDER BY CAST(draw AS INTEGER) DESC"
)

P_SINGLE = sum(
    math.comb(PICK, m) * math.comb(MAX_NUM - PICK, PICK - m)
    for m in range(MATCH_TH, PICK + 1)
) / math.comb(MAX_NUM, PICK)
BASELINE_1BET = P_SINGLE
BASELINE_3BET = 1 - (1 - P_SINGLE) ** 3
BASELINE_4BET = 1 - (1 - P_SINGLE) ** 4

ZONE_BOUNDS = [(1, 9), (10, 19), (20, 29), (30, 38)]
ZONE_OF = {n: idx for idx, (lo, hi) in enumerate(ZONE_BOUNDS) for n in range(lo, hi + 1)}
ZONE_SIZES = {idx: hi - lo + 1 for idx, (lo, hi) in enumerate(ZONE_BOUNDS)}
TAIL_SIZES = Counter(n % 10 for n in range(1, MAX_NUM + 1))
MOD3_SIZES = Counter(n % 3 for n in range(1, MAX_NUM + 1))
MOD5_SIZES = Counter(n % 5 for n in range(1, MAX_NUM + 1))

RESULT_SCHEMA_KEYS = {
    "generated_at",
    "lottery_type",
    "strategy_family",
    "seed",
    "n_perm",
    "source_files",
    "draw_count_total",
    "baselines",
    "reference_windows",
    "leakage_check",
    "candidate_count",
    "candidates",
    "best_candidate",
    "final_decision",
    "completed_markdown",
    "task_result_json",
    "changed_files_list",
}

CANDIDATE_SPECS = [
    {
        "name": "dispersion_state_transition_3bet",
        "family": "dispersion_state",
        "formula": "0.65*similar-dispersion transition + 0.35*spread mean-reversion boost",
        "thesis": (
            "Match historical next draws that followed similar spread / clustering states, "
            "then re-expand or contract around the latest draw centroid depending on whether "
            "the current spread is tighter or wider than its recent median."
        ),
        "transition_window": 540,
        "similarity_scale": 0.5,
        "transition_weight": 0.65,
    },
    {
        "name": "odd_tail_imbalance_3bet",
        "family": "odd_tail_imbalance",
        "formula": "0.55*4-draw odd-tail transition + 0.45*parity/tail deficit reversion",
        "thesis": (
            "Track the last four draws' odd-even and tail-digit balance, then reweight numbers "
            "whose parity / tail buckets are locally under-represented."
        ),
        "transition_window": 480,
        "similarity_scale": 0.8,
        "transition_weight": 0.55,
    },
    {
        "name": "zone_transition_tensor_3bet",
        "family": "zone_transition_tensor",
        "formula": "0.65*two-step zone tensor transition + 0.35*zone deficit boost",
        "thesis": (
            "Use the latest zone-count tensor (current counts plus prior delta) as the state, "
            "and predict numbers from historical next draws that followed the most similar "
            "zone transition pattern."
        ),
        "transition_window": 900,
        "similarity_scale": 0.8,
        "transition_weight": 0.65,
    },
    {
        "name": "residue_structure_stability_3bet",
        "family": "residue_structure_stability",
        "formula": "0.50*12-draw residue transition + 0.50*mod3/mod5 deficit+stability boost",
        "thesis": (
            "Condition on recent residue-class structure (mod3 / mod5 mix and overlap stability), "
            "then boost numbers from residue buckets that are both under-represented and "
            "historically stable."
        ),
        "transition_window": 540,
        "similarity_scale": 0.8,
        "transition_weight": 0.50,
    },
]


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
    return sorted(desc_draws, key=lambda row: (row["date"], row["draw"]))


def load_stage0_metrics() -> Dict:
    with open(STAGE0_PATH, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload["POWER_LOTTO"]["strategies"]


def build_window_indices(total_draws: int, min_history: int = MIN_HISTORY) -> Dict[str, List[int]]:
    return {
        name: list(range(max(min_history, total_draws - periods), total_draws))
        for name, periods in WINDOW_SPECS.items()
    }


def normalize_map(values: Dict[int, float]) -> Dict[int, float]:
    arr = np.array(list(values.values()), dtype=float)
    lo = float(np.min(arr))
    hi = float(np.max(arr))
    if hi - lo <= 1e-12:
        return {key: 0.5 for key in values}
    return {key: (val - lo) / (hi - lo) for key, val in values.items()}


def normalized_entropy(counts: Sequence[float]) -> float:
    arr = np.array(counts, dtype=float)
    total = float(np.sum(arr))
    if total <= 0:
        return 0.0
    probs = arr[arr > 0] / total
    base = math.log(len(arr)) if len(arr) > 1 else 1.0
    return float(-(probs * np.log(probs)).sum() / base)


def similarity_weight(current_vec: np.ndarray, hist_vec: np.ndarray, scale: float) -> float:
    dist = float(np.linalg.norm(current_vec - hist_vec))
    return math.exp(-(dist * dist) / max(scale, 1e-9))


def bernoulli_sharpe(hit_rate: float, edge: float) -> float:
    variance = max(hit_rate * (1.0 - hit_rate), 1e-9)
    return edge / math.sqrt(variance)


def validate_no_leakage(target_draw: Dict, history: Sequence[Dict]) -> None:
    if not history:
        return
    last = history[-1]
    if (last["date"], last["draw"]) >= (target_draw["date"], target_draw["draw"]):
        raise ValueError(
            f"Data leakage: history tail {last['draw']} >= target {target_draw['draw']}"
        )


def top6(score_map: Dict[int, float], exclude: Sequence[int]) -> List[int]:
    excluded = set(exclude)
    ranked = sorted(
        (n for n in range(1, MAX_NUM + 1) if n not in excluded),
        key=lambda n: (-score_map[n], n),
    )
    return sorted(ranked[:PICK])


def make_orthogonal_3bet(score_map: Dict[int, float]) -> List[List[int]]:
    used: set[int] = set()
    bets: List[List[int]] = []
    for _ in range(3):
        bet = top6(score_map, used)
        bets.append(bet)
        used.update(bet)
    return bets


def transition_score_from_context(
    history: Sequence[Dict],
    current_vec: np.ndarray | None,
    context_func: Callable[[Sequence[Dict], int], np.ndarray | None],
    transition_window: int,
    similarity_scale: float,
    start_min: int,
) -> Dict[int, float]:
    raw = {n: 0.0 for n in range(1, MAX_NUM + 1)}
    if current_vec is None:
        return normalize_map(raw)

    start_idx = max(start_min, len(history) - 1 - transition_window)
    total_weight = 0.0
    for idx in range(start_idx, len(history) - 1):
        hist_vec = context_func(history, idx)
        if hist_vec is None:
            continue
        weight = similarity_weight(current_vec, hist_vec, similarity_scale)
        total_weight += weight
        for number in history[idx + 1]["numbers"][:PICK]:
            raw[number] += weight

    if total_weight > 0:
        raw = {n: raw[n] / total_weight for n in raw}
    return normalize_map(raw)


def zone_count(numbers: Sequence[int]) -> List[int]:
    counts = [0, 0, 0, 0]
    for number in numbers:
        counts[ZONE_OF[number]] += 1
    return counts


def dispersion_context(history: Sequence[Dict], idx: int) -> np.ndarray:
    numbers = sorted(history[idx]["numbers"][:PICK])
    gaps = [b - a for a, b in zip(numbers, numbers[1:])]
    return np.array(
        [
            (numbers[-1] - numbers[0]) / 37.0,
            float(np.std(numbers)) / 12.0,
            (sum(gaps) / len(gaps)) / 8.0,
            sum(1 for gap in gaps if gap <= 2) / 5.0,
            sum(1 for gap in gaps if gap >= 8) / 5.0,
        ],
        dtype=float,
    )


def dispersion_boost(history: Sequence[Dict]) -> Dict[int, float]:
    recent = history[-30:] if len(history) >= 30 else history
    ranges = [max(draw["numbers"]) - min(draw["numbers"]) for draw in recent]
    current_range = ranges[-1]
    median_range = float(np.median(ranges)) if ranges else current_range
    last_mean = float(np.mean(history[-1]["numbers"]))
    tight_weight = 0.7

    raw = {}
    for number in range(1, MAX_NUM + 1):
        outer = abs(number - last_mean) / 19.0
        inner = 1.0 - outer
        if current_range < median_range:
            raw[number] = tight_weight * outer + (1.0 - tight_weight) * inner
        else:
            raw[number] = tight_weight * inner + (1.0 - tight_weight) * outer
    return normalize_map(raw)


def odd_tail_context(history: Sequence[Dict], idx: int) -> np.ndarray | None:
    if idx < 3:
        return None
    window = history[idx - 3 : idx + 1]
    numbers = [n for draw in window for n in draw["numbers"][:PICK]]
    odd_ratio = sum(n % 2 for n in numbers) / len(numbers)
    tails = [n % 10 for n in numbers]
    tail_counts = [tails.count(tail) for tail in range(10)]
    high_tail_share = sum(1 for n in history[idx]["numbers"][:PICK] if n % 10 >= 5) / PICK
    return np.array(
        [
            odd_ratio,
            normalized_entropy(tail_counts),
            sum(count for tail, count in enumerate(tail_counts) if tail <= 4) / len(numbers),
            high_tail_share,
        ],
        dtype=float,
    )


def odd_tail_boost(history: Sequence[Dict]) -> Dict[int, float]:
    window = history[-4:] if len(history) >= 4 else history
    numbers = [n for draw in window for n in draw["numbers"][:PICK]]
    odd_ratio = sum(n % 2 for n in numbers) / len(numbers)
    target_parity = 1 if odd_ratio < 0.5 else 0
    tail_freq = Counter(n % 10 for n in numbers)
    total = len(numbers)

    raw = {}
    for number in range(1, MAX_NUM + 1):
        parity_match = 1.0 if (number % 2) == target_parity else 0.0
        expected = TAIL_SIZES[number % 10] / MAX_NUM
        observed = tail_freq[number % 10] / total if total else expected
        tail_deficit = max(expected - observed, 0.0)
        raw[number] = 0.5 * parity_match + 0.5 * tail_deficit * 10.0
    return normalize_map(raw)


def zone_transition_context(history: Sequence[Dict], idx: int) -> np.ndarray | None:
    if idx < 1:
        return None
    current = np.array(zone_count(history[idx]["numbers"][:PICK]), dtype=float) / PICK
    previous = np.array(zone_count(history[idx - 1]["numbers"][:PICK]), dtype=float) / PICK
    return np.concatenate([current, current - previous])


def zone_deficit_boost(history: Sequence[Dict]) -> Dict[int, float]:
    window = history[-12:] if len(history) >= 12 else history
    numbers = [n for draw in window for n in draw["numbers"][:PICK]]
    zone_freq = Counter(ZONE_OF[n] for n in numbers)
    total = len(numbers)

    raw = {}
    for number in range(1, MAX_NUM + 1):
        zone = ZONE_OF[number]
        expected = ZONE_SIZES[zone] / MAX_NUM
        observed = zone_freq[zone] / total if total else expected
        raw[number] = max(expected - observed, 0.0)
    return normalize_map(raw)


def residue_structure_context(history: Sequence[Dict], idx: int) -> np.ndarray | None:
    if idx < 11:
        return None
    window = history[idx - 11 : idx + 1]
    numbers = [n for draw in window for n in draw["numbers"][:PICK]]
    mod3_counts = [0, 0, 0]
    mod5_counts = [0, 0, 0, 0, 0]
    for number in numbers:
        mod3_counts[number % 3] += 1
        mod5_counts[number % 5] += 1
    overlap = float(
        np.mean(
            [
                len(set(window[i]["numbers"]) & set(window[i - 1]["numbers"])) / PICK
                for i in range(1, len(window))
            ]
        )
    )
    return np.array(
        [
            *(np.array(mod3_counts, dtype=float) / len(numbers)),
            normalized_entropy(mod5_counts),
            overlap,
        ],
        dtype=float,
    )


def residue_structure_boost(history: Sequence[Dict]) -> Dict[int, float]:
    window = history[-12:] if len(history) >= 12 else history
    numbers = [n for draw in window for n in draw["numbers"][:PICK]]
    mod3_freq = Counter(n % 3 for n in numbers)
    mod5_freq = Counter(n % 5 for n in numbers)
    per_draw_m3 = {bucket: [] for bucket in range(3)}
    per_draw_m5 = {bucket: [] for bucket in range(5)}
    for draw in window:
        draw_mod3 = Counter(n % 3 for n in draw["numbers"][:PICK])
        draw_mod5 = Counter(n % 5 for n in draw["numbers"][:PICK])
        for bucket in range(3):
            per_draw_m3[bucket].append(draw_mod3.get(bucket, 0) / PICK)
        for bucket in range(5):
            per_draw_m5[bucket].append(draw_mod5.get(bucket, 0) / PICK)

    mod3_stability = {bucket: 1.0 - float(np.std(per_draw_m3[bucket])) for bucket in range(3)}
    mod5_stability = {bucket: 1.0 - float(np.std(per_draw_m5[bucket])) for bucket in range(5)}
    total = len(numbers)

    raw = {}
    for number in range(1, MAX_NUM + 1):
        mod3_bucket = number % 3
        mod5_bucket = number % 5
        expected_mod3 = MOD3_SIZES[mod3_bucket] / MAX_NUM
        expected_mod5 = MOD5_SIZES[mod5_bucket] / MAX_NUM
        observed_mod3 = mod3_freq[mod3_bucket] / total if total else expected_mod3
        observed_mod5 = mod5_freq[mod5_bucket] / total if total else expected_mod5
        deficit = 0.55 * max(expected_mod3 - observed_mod3, 0.0) + 0.45 * max(
            expected_mod5 - observed_mod5, 0.0
        )
        stability = 0.5 * mod3_stability[mod3_bucket] + 0.5 * mod5_stability[mod5_bucket]
        raw[number] = 0.7 * deficit * 10.0 + 0.3 * stability
    return normalize_map(raw)


def build_score_components(history: Sequence[Dict], spec: Dict) -> Dict[str, Dict[int, float]]:
    family = spec["family"]
    if family == "dispersion_state":
        current_vec = dispersion_context(history, len(history) - 1)
        transition = transition_score_from_context(
            history,
            current_vec,
            dispersion_context,
            spec["transition_window"],
            spec["similarity_scale"],
            0,
        )
        boost = dispersion_boost(history)
        return {
            "transition_component": transition,
            "reversion_component": boost,
        }

    if family == "odd_tail_imbalance":
        current_vec = odd_tail_context(history, len(history) - 1)
        transition = transition_score_from_context(
            history,
            current_vec,
            odd_tail_context,
            spec["transition_window"],
            spec["similarity_scale"],
            3,
        )
        boost = odd_tail_boost(history)
        return {
            "transition_component": transition,
            "bucket_reversion_component": boost,
        }

    if family == "zone_transition_tensor":
        current_vec = zone_transition_context(history, len(history) - 1)
        transition = transition_score_from_context(
            history,
            current_vec,
            zone_transition_context,
            spec["transition_window"],
            spec["similarity_scale"],
            1,
        )
        boost = zone_deficit_boost(history)
        return {
            "transition_component": transition,
            "zone_deficit_component": boost,
        }

    if family == "residue_structure_stability":
        current_vec = residue_structure_context(history, len(history) - 1)
        transition = transition_score_from_context(
            history,
            current_vec,
            residue_structure_context,
            spec["transition_window"],
            spec["similarity_scale"],
            11,
        )
        boost = residue_structure_boost(history)
        return {
            "transition_component": transition,
            "stability_component": boost,
        }

    raise ValueError(f"Unknown candidate family: {family}")


def build_score_map(history: Sequence[Dict], spec: Dict) -> Tuple[Dict[int, float], Dict[str, Dict[int, float]]]:
    components = build_score_components(history, spec)
    transition_component = components["transition_component"]
    boost_component_name = next(name for name in components if name != "transition_component")
    boost_component = components[boost_component_name]

    raw = {
        number: spec["transition_weight"] * transition_component[number]
        + (1.0 - spec["transition_weight"]) * boost_component[number]
        for number in range(1, MAX_NUM + 1)
    }
    return normalize_map(raw), components


def predictor_factory(spec: Dict) -> Callable[[Sequence[Dict]], List[List[int]]]:
    def predictor(history: Sequence[Dict]) -> List[List[int]]:
        score_map, _ = build_score_map(history, spec)
        return make_orthogonal_3bet(score_map)

    return predictor


def fourier_3bet_predictor(history: Sequence[Dict]) -> List[List[int]]:
    return fourier_rhythm_predict(list(history), n_bets=3, window=500)


def pp3_freqort_4bet_predictor(history: Sequence[Dict]) -> List[List[int]]:
    return generate_orthogonal_5bet(list(history))[:4]


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
        actual = set(target["numbers"][:PICK])
        per_bet_hits = [len(set(bet) & actual) >= MATCH_TH for bet in bets]
        records.append(
            {
                "target_idx": target_idx,
                "draw": target["draw"],
                "date": target["date"],
                "bets": bets,
                "actual": target["numbers"][:PICK],
                "per_bet_hits": per_bet_hits,
                "hit": any(per_bet_hits),
            }
        )
    return {
        "records": records,
        "hits": sum(1 for row in records if row["hit"]),
        "periods": len(records),
    }


def summarize_window(evaluation: Dict, baseline: float) -> Dict:
    periods = evaluation["periods"]
    hits = evaluation["hits"]
    hit_rate = hits / periods if periods else 0.0
    edge = hit_rate - baseline
    per_bet_hit_rates = []
    per_bet_edges = []
    if periods:
        for bet_idx in range(3):
            rate = sum(row["per_bet_hits"][bet_idx] for row in evaluation["records"]) / periods
            per_bet_hit_rates.append(rate)
            per_bet_edges.append(rate - BASELINE_1BET)
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
        "start_draw": evaluation["records"][0]["draw"],
        "end_draw": evaluation["records"][-1]["draw"],
    }


def marginal_efficiency(edge_3bet: float, edge_4bet: float) -> Dict:
    edge_retention_pct = (edge_3bet / edge_4bet * 100.0) if edge_4bet > 0 else 0.0
    per_bet_efficiency_pct = (
        ((edge_3bet / 3.0) / (edge_4bet / 4.0) * 100.0) if edge_4bet > 0 else 0.0
    )
    return {
        "edge_retention_pct": round(edge_retention_pct, 2),
        "per_bet_efficiency_pct": round(per_bet_efficiency_pct, 2),
        "pass": per_bet_efficiency_pct > 80.0,
    }


def fixed_prediction_permutation(
    records: Sequence[Dict],
    baseline: float,
    n_perm: int = N_PERM,
    seed: int = SEED,
) -> Dict:
    actuals = np.zeros((len(records), MAX_NUM), dtype=bool)
    for row_idx, rec in enumerate(records):
        for number in rec["actual"]:
            actuals[row_idx, number - 1] = True

    def eval_edge(actual_matrix: np.ndarray) -> Tuple[int, float, float]:
        hits = 0
        for i, rec in enumerate(records):
            is_hit = any(
                sum(actual_matrix[i, number - 1] for number in bet) >= MATCH_TH
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
        _, _, shuffled_edge = eval_edge(shuffled)
        shuffle_edges.append(shuffled_edge)
        if shuffled_edge >= real_edge:
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
    candidate_hits = []
    fourier_hits = []
    for target_idx in target_indices:
        target = draws[target_idx]
        history = draws[:target_idx]
        validate_no_leakage(target, history)
        actual = set(target["numbers"][:PICK])
        cand_bets = predictor(history)
        ref_bets = fourier_rhythm_predict(list(history), n_bets=3, window=500)
        candidate_hits.append(any(len(set(bet) & actual) >= MATCH_TH for bet in cand_bets))
        fourier_hits.append(any(len(set(bet) & actual) >= MATCH_TH for bet in ref_bets))

    b = sum(1 for cand, ref in zip(candidate_hits, fourier_hits) if cand and not ref)
    c = sum(1 for cand, ref in zip(candidate_hits, fourier_hits) if not cand and ref)
    a = sum(1 for cand, ref in zip(candidate_hits, fourier_hits) if cand and ref)
    d = sum(1 for cand, ref in zip(candidate_hits, fourier_hits) if not cand and not ref)
    discordant = b + c
    if discordant == 0:
        return {
            "status": "IDENTICAL",
            "a": a,
            "b": b,
            "c": c,
            "d": d,
            "discordant": 0,
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
        "pass": p_value < 0.05 and b > c,
    }


def run_leakage_check() -> Dict:
    proc = subprocess.run(
        [sys.executable, LEAKAGE_TOOL],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    os.makedirs(os.path.dirname(LEAKAGE_OUTPUT_PATH), exist_ok=True)
    transcript = [
        f"command: {sys.executable} tools/verify_no_data_leakage.py",
        f"returncode: {proc.returncode}",
        "",
        "=== STDOUT ===",
        proc.stdout.rstrip(),
        "",
        "=== STDERR ===",
        proc.stderr.rstrip(),
        "",
    ]
    with open(LEAKAGE_OUTPUT_PATH, "w", encoding="utf-8") as handle:
        handle.write("\n".join(transcript))

    status = "PASS" if proc.returncode == 0 and "✅ 所有測試案例通過" in proc.stdout else "FAIL"
    return {
        "status": status,
        "returncode": proc.returncode,
        "output_file": os.path.relpath(LEAKAGE_OUTPUT_PATH, PROJECT_ROOT),
        "stdout_tail": proc.stdout.strip().splitlines()[-12:],
        "stderr_tail": proc.stderr.strip().splitlines()[-12:],
    }


def candidate_passes_pre_mcnemar(candidate: Dict) -> bool:
    for window_name in WINDOW_SPECS:
        if candidate["windows"][window_name]["edge"] <= 0:
            return False
        if candidate["permutation_tests"][window_name]["p_emp"] >= 0.05:
            return False
        if candidate["permutation_tests"][window_name]["cohens_d"] <= 1.0:
            return False
        if not candidate["efficiency_vs_pp3_freqort_4bet"][window_name]["pass"]:
            return False
    return candidate["leakage_check"] == "PASS"


def candidate_failure_gates(candidate: Dict) -> List[str]:
    failures = []
    for window_name in WINDOW_SPECS:
        if candidate["windows"][window_name]["edge"] <= 0:
            failures.append(f"{window_name}: edge<=0")
        if candidate["permutation_tests"][window_name]["p_emp"] >= 0.05:
            failures.append(f"{window_name}: permutation_p>=0.05")
        if candidate["permutation_tests"][window_name]["cohens_d"] <= 1.0:
            failures.append(f"{window_name}: cohens_d<=1.0")
        if not candidate["efficiency_vs_pp3_freqort_4bet"][window_name]["pass"]:
            failures.append(f"{window_name}: per_bet_efficiency<=80%")
    if candidate["leakage_check"] != "PASS":
        failures.append("all_windows: leakage_check_fail")
    if candidate.get("mcnemar_triggered") and not candidate["mcnemar"]["pass"]:
        failures.append("recent_1500: mcnemar_vs_fourier_rhythm_3bet>=0.05_or_net<=0")
    return failures


def determine_candidate_decision(candidate: Dict) -> Tuple[str, List[str], bool]:
    pre_mcnemar_pass = candidate_passes_pre_mcnemar(candidate)
    failures = candidate_failure_gates(candidate)
    if pre_mcnemar_pass and candidate["mcnemar"]["pass"]:
        return "PROMOTE", failures, True
    if pre_mcnemar_pass:
        return "WATCH", failures, True

    positive_edges = all(candidate["windows"][name]["edge"] > 0 for name in WINDOW_SPECS)
    signal_trace = any(
        candidate["permutation_tests"][name]["p_emp"] < 0.10
        or candidate["permutation_tests"][name]["cohens_d"] > 0.8
        for name in WINDOW_SPECS
    )
    if positive_edges and signal_trace:
        return "WATCH", failures, False
    return "REJECT", failures, False


def latest_family_snapshot(draws: Sequence[Dict], spec: Dict) -> Dict:
    history = draws[:-1]
    score_map, components = build_score_map(history, spec)
    bets = make_orthogonal_3bet(score_map)
    ranked = sorted(range(1, MAX_NUM + 1), key=lambda n: (-score_map[n], n))[:12]
    rows = []
    for number in ranked:
        row = {
            "number": number,
            "final_score": round(score_map[number], 6),
        }
        for component_name, component_map in components.items():
            row[component_name] = round(component_map[number], 6)
        rows.append(row)
    return {
        "latest_bets": bets,
        "latest_top_numbers": rows,
    }


def build_completed_markdown(payload: Dict) -> str:
    lines = [
        "# POWER_LOTTO Layer-1 nonfamily 3bet validation (2026-04-23)",
        "",
        f"- Final decision: **{payload['final_decision']}**",
        f"- Leakage check: **{payload['leakage_check']['status']}**",
        f"- Best candidate: `{payload['best_candidate']['name']}` ({payload['best_candidate']['decision']})",
        (
            f"- Best 150/500/1500 raw edge: "
            f"{payload['best_candidate']['windows']['recent_150']['edge_pct']:+.2f}% / "
            f"{payload['best_candidate']['windows']['recent_500']['edge_pct']:+.2f}% / "
            f"{payload['best_candidate']['windows']['recent_1500']['edge_pct']:+.2f}%"
        ),
        "",
        "| Candidate | Decision | 150 Edge | 500 Edge | 1500 Edge | 150 p | 500 p | 1500 p | 150 d | 500 d | 1500 d | 150 Eff | 500 Eff | 1500 Eff | McNemar |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for candidate in payload["candidates"]:
        mcnemar_note = (
            f"p={candidate['mcnemar']['p_value']:.4f}"
            if candidate["mcnemar_triggered"]
            else "not triggered"
        )
        lines.append(
            "| "
            + " | ".join(
                [
                    candidate["name"],
                    candidate["decision"],
                    f"{candidate['windows']['recent_150']['edge_pct']:+.2f}%",
                    f"{candidate['windows']['recent_500']['edge_pct']:+.2f}%",
                    f"{candidate['windows']['recent_1500']['edge_pct']:+.2f}%",
                    f"{candidate['permutation_tests']['recent_150']['p_emp']:.4f}",
                    f"{candidate['permutation_tests']['recent_500']['p_emp']:.4f}",
                    f"{candidate['permutation_tests']['recent_1500']['p_emp']:.4f}",
                    f"{candidate['permutation_tests']['recent_150']['cohens_d']:.3f}",
                    f"{candidate['permutation_tests']['recent_500']['cohens_d']:.3f}",
                    f"{candidate['permutation_tests']['recent_1500']['cohens_d']:.3f}",
                    f"{candidate['efficiency_vs_pp3_freqort_4bet']['recent_150']['per_bet_efficiency_pct']:.1f}%",
                    f"{candidate['efficiency_vs_pp3_freqort_4bet']['recent_500']['per_bet_efficiency_pct']:.1f}%",
                    f"{candidate['efficiency_vs_pp3_freqort_4bet']['recent_1500']['per_bet_efficiency_pct']:.1f}%",
                    mcnemar_note,
                ]
            )
            + " |"
        )

    lines.extend(["", "## Failure gates by candidate", ""])
    for candidate in payload["candidates"]:
        failure_text = ", ".join(candidate["failed_gates"]) if candidate["failed_gates"] else "none"
        lines.append(f"- `{candidate['name']}` → **{candidate['decision']}**: {failure_text}")
    return "\n".join(lines)


def main() -> None:
    draws = load_draws()
    total_draws = len(draws)
    stage0 = load_stage0_metrics()
    windows = build_window_indices(total_draws)
    leakage_check = run_leakage_check()

    reference_windows = {
        "fourier_rhythm_3bet": {
            window_name: summarize_window(
                evaluate_targets(draws, indices, fourier_3bet_predictor),
                BASELINE_3BET,
            )
            for window_name, indices in windows.items()
        },
        "pp3_freqort_4bet": {
            window_name: summarize_window(
                evaluate_targets(draws, indices, pp3_freqort_4bet_predictor),
                BASELINE_4BET,
            )
            for window_name, indices in windows.items()
        },
    }

    diagnostics = {
        "generated_at": now_iso_taipei(),
        "strategy_family": "power_layer1_nonfamily_3bet",
        "seed": SEED,
        "n_perm": N_PERM,
        "latest_snapshots": {},
    }

    candidates = []
    for spec in CANDIDATE_SPECS:
        predictor = predictor_factory(spec)
        evaluations = {
            window_name: evaluate_targets(draws, indices, predictor)
            for window_name, indices in windows.items()
        }
        summaries = {
            window_name: summarize_window(evaluations[window_name], BASELINE_3BET)
            for window_name in windows
        }
        permutation_tests = {
            window_name: fixed_prediction_permutation(
                evaluations[window_name]["records"],
                BASELINE_3BET,
                N_PERM,
                SEED,
            )
            for window_name in windows
        }
        efficiency_vs_pp3 = {
            window_name: marginal_efficiency(
                summaries[window_name]["edge"],
                reference_windows["pp3_freqort_4bet"][window_name]["edge"],
            )
            for window_name in windows
        }
        comparison_vs_fourier = {
            window_name: {
                "candidate_edge_pct": summaries[window_name]["edge_pct"],
                "fourier_edge_pct": reference_windows["fourier_rhythm_3bet"][window_name]["edge_pct"],
                "delta_edge_pct": round(
                    summaries[window_name]["edge_pct"]
                    - reference_windows["fourier_rhythm_3bet"][window_name]["edge_pct"],
                    2,
                ),
            }
            for window_name in windows
        }

        candidate = {
            "name": spec["name"],
            "family": spec["family"],
            "formula": spec["formula"],
            "thesis": spec["thesis"],
            "windows": summaries,
            "permutation_tests": permutation_tests,
            "efficiency_vs_pp3_freqort_4bet": efficiency_vs_pp3,
            "comparison_vs_fourier_rhythm_3bet": comparison_vs_fourier,
            "leakage_check": leakage_check["status"],
        }

        pre_mcnemar_pass = candidate_passes_pre_mcnemar(candidate)
        if pre_mcnemar_pass:
            candidate["mcnemar"] = mcnemar_against_fourier(draws, windows["recent_1500"], predictor)
        else:
            candidate["mcnemar"] = {
                "status": "SKIPPED",
                "reason": "pre-promotion gates not fully passed",
                "pass": False,
            }
        decision, failed_gates, triggered = determine_candidate_decision(candidate)
        candidate["mcnemar_triggered"] = triggered
        candidate["decision"] = decision
        candidate["failed_gates"] = failed_gates
        candidates.append(candidate)
        diagnostics["latest_snapshots"][spec["name"]] = latest_family_snapshot(draws, spec)

    promote_candidates = [candidate for candidate in candidates if candidate["decision"] == "PROMOTE"]
    final_decision = (
        "PROMOTE_NONFAMILY_LAYER1_3BET"
        if promote_candidates
        else "REJECT_ALL_NONFAMILY_LAYER1_3BET"
    )
    best_candidate = sorted(
        candidates,
        key=lambda candidate: (
            candidate["decision"] == "PROMOTE",
            candidate["decision"] == "WATCH",
            candidate["windows"]["recent_500"]["edge"],
            candidate["permutation_tests"]["recent_500"]["cohens_d"],
        ),
        reverse=True,
    )[0]

    payload = {
        "generated_at": now_iso_taipei(),
        "lottery_type": "POWER_LOTTO",
        "strategy_family": "power_layer1_nonfamily_3bet",
        "seed": SEED,
        "n_perm": N_PERM,
        "source_files": {
            "db": "lottery_api/data/lottery_v2.db",
            "baseline": "analysis/results/stage0_baseline.json",
            "fourier_reference": "tools/power_fourier_rhythm.py",
            "pp3_freqort_reference": "tools/predict_power_orthogonal_5bet.py",
            "leakage_check": "tools/verify_no_data_leakage.py",
            "leakage_output": os.path.relpath(LEAKAGE_OUTPUT_PATH, PROJECT_ROOT),
            "diagnostics": os.path.relpath(DIAG_PATH, PROJECT_ROOT),
        },
        "draw_count_total": total_draws,
        "db_query": DB_QUERY,
        "baselines": {
            "one_bet_pct": round(BASELINE_1BET * 100.0, 4),
            "three_bet_pct": round(BASELINE_3BET * 100.0, 4),
            "four_bet_pct": round(BASELINE_4BET * 100.0, 4),
        },
        "stage0_reference": {
            "fourier_rhythm_3bet_edge_pct": stage0["fourier_rhythm_3bet"]["edge_pct"],
            "pp3_freqort_4bet_edge_pct": stage0["pp3_freqort_4bet"]["edge_pct"],
        },
        "reference_windows": reference_windows,
        "leakage_check": leakage_check,
        "candidate_count": len(candidates),
        "candidates": candidates,
        "best_candidate": best_candidate,
        "final_decision": final_decision,
        "summary": {
            "promote_count": len(promote_candidates),
            "watch_count": sum(1 for candidate in candidates if candidate["decision"] == "WATCH"),
            "reject_count": sum(1 for candidate in candidates if candidate["decision"] == "REJECT"),
            "mcnemar_triggered_count": sum(
                1 for candidate in candidates if candidate["mcnemar_triggered"]
            ),
        },
        "changed_files_list": [
            "tools/research_power_layer1_nonfamily_3bet_20260423.py",
            f"analysis/results/power_layer1_nonfamily_3bet_validation_{DATE_TAG}.json",
            f"analysis/results/power_layer1_nonfamily_3bet_validation_{DATE_TAG}.md",
            f"analysis/results/power_layer1_nonfamily_3bet_diagnostics_{DATE_TAG}.json",
            f"analysis/results/power_layer1_nonfamily_3bet_leakage_check_{DATE_TAG}.txt",
            "tests/test_power_layer1_nonfamily_3bet_20260423.py",
            "wiki/games/power_lotto.md",
            "wiki/lessons/key_lessons.md",
            "memory/lessons.md",
        ],
    }
    payload["completed_markdown"] = build_completed_markdown(payload)
    payload["task_result_json"] = {
        "final_decision": payload["final_decision"],
        "candidate_decisions": {candidate["name"]: candidate["decision"] for candidate in candidates},
        "mcnemar_triggered": {
            candidate["name"]: candidate["mcnemar_triggered"] for candidate in candidates
        },
        "top_failures": {
            candidate["name"]: candidate["failed_gates"][:5] for candidate in candidates
        },
        "leakage_check": leakage_check["status"],
    }

    missing_keys = RESULT_SCHEMA_KEYS.difference(payload.keys())
    if missing_keys:
        raise KeyError(f"Result payload missing keys: {sorted(missing_keys)}")

    os.makedirs(os.path.dirname(RESULT_PATH), exist_ok=True)
    with open(DIAG_PATH, "w", encoding="utf-8") as handle:
        json.dump(diagnostics, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    with open(RESULT_PATH, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    with open(MARKDOWN_PATH, "w", encoding="utf-8") as handle:
        handle.write(payload["completed_markdown"])
        handle.write("\n")

    print(payload["completed_markdown"])
    print(f"\nSaved: {os.path.relpath(RESULT_PATH, PROJECT_ROOT)}")
    print(f"Saved: {os.path.relpath(MARKDOWN_PATH, PROJECT_ROOT)}")
    print(f"Saved: {os.path.relpath(DIAG_PATH, PROJECT_ROOT)}")
    print(f"Saved: {os.path.relpath(LEAKAGE_OUTPUT_PATH, PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
