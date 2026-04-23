#!/usr/bin/env python3
"""
Promotion gate validation for DAILY_539 MicroFish+MidFreq 2-bet.

Contract summary:
  - candidate: microfish_midfreq_2bet
  - mapping:   "MicroFish+MidFreq 2-bet" in active code
  - incumbent: midfreq_acb_2bet
  - windows:   150 / 500 / 1500 OOS
  - checks:    edge, permutation (200, seed=42), Cohen's d,
               per-bet marginal efficiency, McNemar, no leakage
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Sequence

import numpy as np

try:
    from scipy.stats import binomtest
except ImportError:  # pragma: no cover
    binomtest = None


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "lottery_api"))

from lottery_api.database import DatabaseManager
from lottery_api.engine.perm_test import perm_test
from tools.quick_predict import _539_acb_bet, _539_midfreq_bet


SEED = 42
N_PERM = 200
MIN_HISTORY = 300
PERM_WARMUP = 900
WINDOWS = [150, 500, 1500]
POOL = 39
PICK = 5
GAME = "DAILY_539"
DATE_TAG = "20260423"

RESULTS_DIR = os.path.join(PROJECT_ROOT, "analysis", "results")
RESULT_JSON = os.path.join(
    RESULTS_DIR, f"daily539_microfish_midfreq_promotion_validation_{DATE_TAG}.json"
)
RESULT_MD = os.path.join(
    RESULTS_DIR, f"daily539_microfish_midfreq_promotion_validation_{DATE_TAG}.md"
)
DIAGNOSTICS_JSON = os.path.join(
    RESULTS_DIR, f"daily539_microfish_midfreq_promotion_diagnostics_{DATE_TAG}.json"
)
LEAKAGE_PATH = os.path.join(
    RESULTS_DIR, f"daily539_microfish_midfreq_promotion_no_leakage_{DATE_TAG}.txt"
)
GENOME_PATH = os.path.join(PROJECT_ROOT, "validated_strategy_set.json")
STAGE0_PATH = os.path.join(PROJECT_ROOT, "analysis", "results", "stage0_baseline.json")

BASELINES = {1: 0.1140, 2: 0.2154, 3: 0.3050}
PRIZE_TABLE = {2: 50, 3: 300, 4: 20_000, 5: 8_000_000}
ZONES = {n: 0 if n <= 13 else 1 if n <= 26 else 2 for n in range(1, POOL + 1)}


@dataclass(frozen=True)
class GenomeSpec:
    features: List[str]
    weights: List[float]
    source: str
    generated_now: bool
    summary: Dict


def ensure_results_dir() -> None:
    os.makedirs(RESULTS_DIR, exist_ok=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate DAILY_539 MicroFish+MidFreq promotion gate.")
    parser.add_argument("--leakage-audit-only", action="store_true", help="Print only the leakage audit.")
    parser.add_argument(
        "--force-regenerate-genome",
        action="store_true",
        help="Force re-running the active MicroFish engine before validation.",
    )
    return parser.parse_args()


def load_draws() -> List[Dict]:
    db_path = os.path.join(PROJECT_ROOT, "lottery_api", "data", "lottery_v2.db")
    db = DatabaseManager(db_path=db_path)
    raw = db.get_all_draws(GAME)
    draws: List[Dict] = []
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
    if draws:
        draws[-1]["next_date"] = None
    return draws


def load_stage0_reference() -> Dict:
    if not os.path.exists(STAGE0_PATH):
        return {}
    with open(STAGE0_PATH, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload.get(GAME, {}).get("strategies", {})


def validate_bet(bet: Sequence[int]) -> List[int]:
    numbers = sorted(int(n) for n in bet)
    if len(numbers) != PICK or len(set(numbers)) != PICK:
        raise ValueError(f"invalid bet: {bet}")
    if any(n < 1 or n > POOL for n in numbers):
        raise ValueError(f"bet out of range: {bet}")
    return numbers


def top5_from_scores(scores: Dict[int, float], exclude: Optional[set] = None) -> List[int]:
    exclude = exclude or set()
    ranked = sorted((n for n in scores if n not in exclude), key=lambda n: (-scores[n], n))
    return sorted(ranked[:PICK])


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


def infer_target_date(history: Sequence[Dict]):
    next_date = history[-1].get("next_date")
    if next_date is None:
        raise ValueError("next_date missing on last history draw")
    return next_date


def draw_payout(match_counts: Sequence[int]) -> float:
    return float(sum(PRIZE_TABLE.get(count, 0) for count in match_counts))


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


def max_required_history(features: Sequence[str]) -> int:
    required = 100
    for feature in features:
        numbers = [int(item) for item in re.findall(r"\d+", feature)]
        required = max(required, max(numbers) if numbers else 0)
    if any(feature.startswith("fourier_") for feature in features):
        required = max(required, 500)
    return min(max(required, 100), 500)


def _window_frequency(history: Sequence[Dict], window: int) -> Counter:
    recent = history[-window:] if len(history) >= window else history
    freq: Counter = Counter()
    for draw in recent:
        for number in draw["numbers"][:PICK]:
            freq[number] += 1
    return freq


def _gap_before_next(history: Sequence[Dict], number: int) -> int:
    gap = 0
    for draw in reversed(history):
        if number in draw["numbers"]:
            return gap
        gap += 1
    return gap


def _markov_probability(history: Sequence[Dict], number: int, lag: int, window: int) -> float:
    recent = history[-window:] if len(history) >= window else history
    if len(recent) <= lag:
        return 0.0
    hits_given = 0
    total_given = 0
    for idx in range(lag, len(recent)):
        if number in recent[idx - lag]["numbers"]:
            total_given += 1
            if number in recent[idx]["numbers"]:
                hits_given += 1
    return hits_given / total_given if total_given else 0.0


def _tail_distribution(history: Sequence[Dict], window: int) -> Dict[int, float]:
    recent = history[-window:] if len(history) >= window else history
    counts = Counter()
    total = 0
    for draw in recent:
        for number in draw["numbers"][:PICK]:
            counts[number % 10] += 1
            total += 1
    if total == 0:
        return {tail: 0.0 for tail in range(10)}
    return {tail: counts[tail] / total for tail in range(10)}


def feature_scores(history: Sequence[Dict], feature_name: str) -> Dict[int, float]:
    history = list(history)
    values = {n: 0.0 for n in range(1, POOL + 1)}

    if feature_name.startswith("ix_"):
        left_name, right_name = feature_name[3:].split("_x_", 1)
        left = feature_scores(history, left_name)
        right = feature_scores(history, right_name)
        for number in values:
            values[number] = left[number] * right[number]
        return values

    if feature_name.startswith("nl_"):
        transform, base_name = feature_name[3:].split("_", 1)
        base = feature_scores(history, base_name)
        for number in values:
            raw = base[number]
            if transform == "log":
                values[number] = math.log1p(abs(raw)) * math.copysign(1.0, raw) if raw != 0 else 0.0
            elif transform == "sqrt":
                values[number] = math.sqrt(abs(raw)) * math.copysign(1.0, raw) if raw != 0 else 0.0
            elif transform == "sq":
                values[number] = raw * abs(raw)
            elif transform == "tanh":
                values[number] = math.tanh(raw / 12.0)
            else:
                raise ValueError(f"unsupported nonlinear transform: {feature_name}")
        return values

    if feature_name.startswith("freq_"):
        window = int(feature_name.rsplit("_", 1)[1])
        recent = history[-window:] if len(history) >= window else history
        freq = _window_frequency(history, window)
        expected = len(recent) * PICK / POOL if recent else 0.0
        freq_values = np.array([freq.get(n, 0) for n in range(1, POOL + 1)], dtype=float)
        std = max(float(np.std(freq_values)), 1e-6)
        mean = float(np.mean(freq_values))
        for number in values:
            count = float(freq.get(number, 0))
            if feature_name.startswith("freq_raw_"):
                values[number] = count
            elif feature_name.startswith("freq_deficit_"):
                values[number] = expected - count
            elif feature_name.startswith("freq_zscore_"):
                values[number] = (count - mean) / std
            else:
                raise ValueError(f"unsupported frequency feature: {feature_name}")
        return values

    if feature_name.startswith("gap_"):
        window = int(feature_name.rsplit("_", 1)[1])
        freq = _window_frequency(history, window)
        for number in values:
            gap = min(_gap_before_next(history, number), window)
            if feature_name.startswith("gap_current_"):
                values[number] = float(gap)
            else:
                avg_gap = window / (freq.get(number, 0) + 1.0)
                ratio = gap / max(avg_gap, 1.0)
                if feature_name.startswith("gap_ratio_"):
                    values[number] = float(ratio)
                elif feature_name.startswith("gap_pressure_"):
                    values[number] = float(ratio * (1.0 + 0.25 * max(ratio - 1.0, 0.0)))
                else:
                    raise ValueError(f"unsupported gap feature: {feature_name}")
        return values

    if feature_name.startswith("parity_even_"):
        window = int(feature_name.rsplit("_", 1)[1])
        recent = history[-window:] if len(history) >= window else history
        total = max(len(recent) * PICK, 1)
        even_hits = sum(1 for draw in recent for number in draw["numbers"][:PICK] if number % 2 == 0)
        even_rate = even_hits / total
        for number in values:
            if feature_name.startswith("parity_even_rate_"):
                values[number] = even_rate
            elif feature_name.startswith("parity_even_boost_"):
                boost = 0.5 - even_rate
                values[number] = boost if number % 2 == 0 else -boost
            else:
                raise ValueError(f"unsupported parity feature: {feature_name}")
        return values

    if feature_name.startswith("zone_"):
        window = int(feature_name.rsplit("_", 1)[1])
        recent = history[-window:] if len(history) >= window else history
        zone_hits = Counter()
        total = 0
        for draw in recent:
            for number in draw["numbers"][:PICK]:
                zone_hits[ZONES[number]] += 1
                total += 1
        zone_pct = {zone: zone_hits[zone] / total if total else 0.0 for zone in range(3)}
        entropy = -sum(p * math.log(p + 1e-10) for p in zone_pct.values())
        concentration = max(zone_pct.values()) if zone_pct else 0.0
        for number in values:
            if feature_name.startswith("zone_deficit_"):
                values[number] = 1.0 / 3.0 - zone_pct[ZONES[number]]
            elif feature_name.startswith("zone_entropy_"):
                values[number] = entropy
            elif feature_name.startswith("zone_concentration_"):
                values[number] = concentration
            else:
                raise ValueError(f"unsupported zone feature: {feature_name}")
        return values

    if feature_name.startswith("sum_"):
        window = int(feature_name.rsplit("_", 1)[1])
        recent = history[-window:] if len(history) >= window else history
        sums = [sum(draw["numbers"][:PICK]) for draw in recent]
        mean = float(np.mean(sums)) if sums else 0.0
        std = max(float(np.std(sums)), 1e-6) if sums else 1.0
        last_sum = float(sum(history[-1]["numbers"][:PICK])) if history else 0.0
        zscore = (last_sum - mean) / std if history else 0.0
        for number in values:
            if feature_name.startswith("sum_mean_"):
                values[number] = mean
            elif feature_name.startswith("sum_zscore_"):
                values[number] = zscore
            else:
                raise ValueError(f"unsupported sum feature: {feature_name}")
        return values

    if feature_name.startswith("tail_"):
        window = int(feature_name.rsplit("_", 1)[1])
        tail_pct = _tail_distribution(history, window)
        entropy = -sum(p * math.log(p + 1e-10) for p in tail_pct.values())
        for number in values:
            if feature_name.startswith("tail_deficit_"):
                values[number] = 0.1 - tail_pct[number % 10]
            elif feature_name.startswith("tail_entropy_"):
                values[number] = entropy
            else:
                raise ValueError(f"unsupported tail feature: {feature_name}")
        return values

    if feature_name.startswith("consec_neighbor_"):
        last_numbers = set(history[-1]["numbers"][:PICK]) if history else set()
        for number in values:
            score = 0
            if number - 1 in last_numbers:
                score += 1
            if number + 1 in last_numbers:
                score += 1
            values[number] = float(score)
        return values

    if feature_name.startswith("markov_lag"):
        match = re.match(r"markov_lag(\d+)_(\d+)", feature_name)
        if not match:
            raise ValueError(f"unsupported Markov feature: {feature_name}")
        lag = int(match.group(1))
        window = int(match.group(2))
        for number in values:
            values[number] = _markov_probability(history, number, lag, window)
        return values

    if feature_name.startswith("entropy_"):
        window = int(feature_name.rsplit("_", 1)[1])
        recent = history[-window:] if len(history) >= window else history
        total_draws = max(len(recent), 1)
        freq = _window_frequency(history, window)
        for number in values:
            probability = freq.get(number, 0) / total_draws
            entropy = -(
                probability * math.log(probability + 1e-10)
                + (1.0 - probability) * math.log(1.0 - probability + 1e-10)
            )
            if feature_name.startswith("entropy_binary_"):
                values[number] = entropy
            elif feature_name.startswith("entropy_inverted_"):
                values[number] = 1.0 - entropy
            else:
                raise ValueError(f"unsupported entropy feature: {feature_name}")
        return values

    if feature_name.startswith("ac_mean_"):
        window = int(feature_name.rsplit("_", 1)[1])
        recent = history[-window:] if len(history) >= window else history
        ac_sum = 0.0
        for draw in recent:
            numbers = sorted(draw["numbers"][:PICK])
            diffs = {b - a for idx, a in enumerate(numbers) for b in numbers[idx + 1 :]}
            ac_sum += len(diffs) - len(numbers) + 1
        mean = ac_sum / max(len(recent), 1)
        for number in values:
            values[number] = mean
        return values

    if feature_name.startswith("fourier_"):
        window = 500
        if len(history) < window:
            return values
        recent = history[-window:]
        from numpy.fft import fft as np_fft, fftfreq as np_fftfreq

        for number in values:
            bh = np.array([1.0 if number in draw["numbers"][:PICK] else 0.0 for draw in recent], dtype=float)
            if bh.sum() < 2:
                continue
            yf = np_fft(bh - np.mean(bh))
            xf = np_fftfreq(window, 1)
            pos_mask = xf > 0
            if pos_mask.sum() == 0:
                continue
            pos_yf = np.abs(yf[pos_mask])
            pos_xf = xf[pos_mask]
            peak_idx = int(np.argmax(pos_yf))
            freq_value = float(pos_xf[peak_idx])
            amp_value = float(pos_yf[peak_idx])
            phase_value = 0.0
            if freq_value > 0:
                last_hit = np.where(bh == 1)[0]
                if len(last_hit) > 0:
                    expected_gap = 1.0 / freq_value
                    actual_gap = window - 1 - last_hit[-1]
                    phase_value = 1.0 / (abs(actual_gap - expected_gap) + 1.0)
            if feature_name == "fourier_freq":
                values[number] = freq_value
            elif feature_name == "fourier_amp":
                values[number] = amp_value
            elif feature_name == "fourier_phase":
                values[number] = phase_value
            else:
                raise ValueError(f"unsupported Fourier feature: {feature_name}")
        return values

    raise ValueError(f"unsupported MicroFish feature: {feature_name}")


def microfish_scores(history: Sequence[Dict], genome: GenomeSpec) -> Dict[int, float]:
    needed = max_required_history(genome.features)
    scoped_history = list(history[-needed:]) if len(history) > needed else list(history)
    scores = {n: 0.0 for n in range(1, POOL + 1)}
    for feature_name, weight in zip(genome.features, genome.weights):
        partial = feature_scores(scoped_history, feature_name)
        for number in scores:
            scores[number] += float(weight) * partial[number]
    return scores


def generate_microfish_genome() -> Dict:
    cmd = [sys.executable, os.path.join(PROJECT_ROOT, "tools", "microfish_engine.py")]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return {
        "command": "python3 tools/microfish_engine.py",
        "exit_code": proc.returncode,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
    }


def load_microfish_genome(force_regenerate: bool = False) -> GenomeSpec:
    generation_info = None
    if force_regenerate or not os.path.exists(GENOME_PATH):
        generation_info = generate_microfish_genome()
        if generation_info["exit_code"] != 0:
            raise RuntimeError("active MicroFish engine failed to generate validated_strategy_set.json")
    with open(GENOME_PATH, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    valid = payload.get("valid", [])
    if not valid:
        raise ValueError("validated_strategy_set.json contains no valid candidates")
    top = valid[0]
    return GenomeSpec(
        features=list(top["features"]),
        weights=[float(item) for item in top["weights"]],
        source=GENOME_PATH,
        generated_now=generation_info is not None,
        summary={
            "valid_count": len(valid),
            "rejected_count": len(payload.get("rejected", [])),
            "top_rank": int(top.get("rank", 1)),
            "top_status": top.get("status", "VALID"),
            "generation": generation_info,
        },
    )


def candidate_microfish_midfreq_2bet(history: List[Dict], genome: GenomeSpec) -> List[List[int]]:
    bet1 = top5_from_scores(microfish_scores(history, genome))
    bet2 = _539_midfreq_bet(history, exclude=set(bet1))
    return [validate_bet(bet1), validate_bet(bet2)]


def incumbent_midfreq_acb_2bet(history: List[Dict]) -> List[List[int]]:
    bet1 = _539_midfreq_bet(history)
    bet2 = _539_acb_bet(history, exclude=set(bet1))
    return [validate_bet(bet1), validate_bet(bet2)]


def reference_acb_markov_midfreq_3bet(history: List[Dict]) -> List[List[int]]:
    from tools.quick_predict import _539_markov_bet

    bet1 = _539_acb_bet(history)
    bet2 = _539_markov_bet(history, exclude=set(bet1))
    bet3 = _539_midfreq_bet(history, exclude=set(bet1) | set(bet2))
    return [validate_bet(bet1), validate_bet(bet2), validate_bet(bet3)]


def simulate_strategy(
    draws: Sequence[Dict],
    strategy_name: str,
    genome: Optional[GenomeSpec] = None,
) -> List[Dict]:
    records: List[Dict] = []
    for idx in range(MIN_HISTORY, len(draws)):
        history = list(draws[:idx])
        target = draws[idx]
        verify_slice_integrity(history, target)
        if strategy_name == "microfish_midfreq_2bet":
            bets = candidate_microfish_midfreq_2bet(history, genome)  # type: ignore[arg-type]
            strategy_label = "MicroFish+MidFreq 2-bet"
        elif strategy_name == "midfreq_acb_2bet":
            bets = incumbent_midfreq_acb_2bet(history)
            strategy_label = "MidFreq+ACB 2-bet"
        elif strategy_name == "acb_markov_midfreq_3bet":
            bets = reference_acb_markov_midfreq_3bet(history)
            strategy_label = "ACB+Markov+MidFreq 3-bet"
        else:
            raise ValueError(f"unknown strategy: {strategy_name}")
        actual = set(target["numbers"])
        match_counts = [len(set(bet) & actual) for bet in bets]
        record = {
            "draw": target["draw"],
            "date": target["date"],
            "strategy": strategy_label,
            "match_counts": match_counts,
        }
        for bet_idx in range(1, len(bets) + 1):
            record[f"is_m2plus_{bet_idx}"] = any(m >= 2 for m in match_counts[:bet_idx])
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
        "m2_plus_hits": int(sum(1 for item in max_matches if item >= 2)),
        "m3_plus_hits": int(sum(1 for item in max_matches if item >= 3)),
        "m4_plus_hits": int(sum(1 for item in max_matches if item >= 4)),
        "m5_hits": int(sum(1 for item in max_matches if item >= 5)),
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


def mcnemar_from_records(candidate_records: Sequence[Dict], incumbent_records: Sequence[Dict], window: int) -> Dict:
    cand_hits = [bool(r["is_m2plus_2"]) for r in candidate_records[-window:]]
    inc_hits = [bool(r["is_m2plus_2"]) for r in incumbent_records[-window:]]
    candidate_only = sum(1 for cand, inc in zip(cand_hits, inc_hits) if cand and not inc)
    incumbent_only = sum(1 for cand, inc in zip(cand_hits, inc_hits) if (not cand) and inc)
    discordant = candidate_only + incumbent_only
    if discordant == 0:
        p_value = 1.0
    elif binomtest is not None:
        p_value = float(binomtest(candidate_only, discordant, 0.5).pvalue)
    else:  # pragma: no cover
        z = abs(candidate_only - incumbent_only) / math.sqrt(discordant)
        p_value = math.erfc(z / math.sqrt(2))
    return {
        "window": window,
        "candidate_only": int(candidate_only),
        "incumbent_only": int(incumbent_only),
        "net": int(candidate_only - incumbent_only),
        "p_value": round(p_value, 4),
    }


def get_perm_slice(draws: Sequence[Dict], window: int) -> List[Dict]:
    slice_start = len(draws) - (window + PERM_WARMUP)
    if slice_start < 0:
        raise ValueError(f"insufficient draws for permutation window={window}")
    return [dict(draw) for draw in draws[slice_start:]]


def permutation_metrics(draws: Sequence[Dict], genome: GenomeSpec, strategy_name: str, window: int) -> Dict:
    if strategy_name == "microfish_midfreq_2bet":
        predict_fn = lambda history: candidate_microfish_midfreq_2bet(history, genome)
    elif strategy_name == "midfreq_acb_2bet":
        predict_fn = incumbent_midfreq_acb_2bet
    else:
        raise ValueError(f"unsupported strategy for permutation: {strategy_name}")
    perm_result = perm_test(
        history=get_perm_slice(draws, window),
        predict_fn=predict_fn,
        baseline=BASELINES[2],
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


def build_window_failures(window_result: Dict) -> List[str]:
    failures: List[str] = []
    metrics = window_result["candidate_metrics"]
    perm = window_result["candidate_permutation"]
    eff = window_result["candidate_efficiency"]
    mc = window_result["mcnemar_vs_incumbent"]
    if metrics["edge"] <= 0:
        failures.append("edge<=0")
    if perm["p_value"] >= 0.05:
        failures.append("perm>=0.05")
    if perm["cohens_d"] <= 1.0:
        failures.append("d<=1.0")
    if any(item["incremental_efficiency_pct"] < 80.0 for item in eff[1:]):
        failures.append("eff<80")
    if mc["p_value"] >= 0.05:
        failures.append("mcnemar>=0.05")
    if mc["net"] <= 0:
        failures.append("mcnemar_net<=0")
    return failures


def summarize_failed_gates(window_failures: Dict[str, List[str]], leakage: Dict) -> List[str]:
    failed = sorted({item for parts in window_failures.values() for item in parts})
    if not leakage["formal_checker_passed"] or not leakage["microfish_slice_checks_passed"]:
        failed.append("leakage")
    return failed


def determine_verdict(window_failures: Dict[str, List[str]], leakage: Dict) -> str:
    if leakage["formal_checker_passed"] and leakage["microfish_slice_checks_passed"] and all(
        not parts for parts in window_failures.values()
    ):
        return "PASS_PROMOTION"
    return "REJECT"


def run_microfish_leakage_audit(draws: Sequence[Dict], genome: GenomeSpec) -> str:
    lines = []
    lines.append("=" * 80)
    lines.append("DAILY_539 MicroFish+MidFreq promotion leakage audit")
    lines.append("=" * 80)
    sample_indices = [len(draws) - 1500, len(draws) - 500, len(draws) - 150]
    for idx in sample_indices:
        history = draws[:idx]
        target = draws[idx]
        verify_slice_integrity(history, target)
        inferred = infer_target_date(history)
        preview = candidate_microfish_midfreq_2bet(history, genome)
        lines.append(
            f"target={target['draw']} {target['date']} | train_last={history[-1]['draw']} {history[-1]['date']} | "
            f"inferred_target_date={inferred.isoformat()} | preview_bets={preview}"
        )
    lines.append("All sampled MicroFish slices passed: train draw/date < target and next_date matched target date.")
    return "\n".join(lines) + "\n"


def generate_leakage_artifact(draws: Sequence[Dict], genome: GenomeSpec) -> Dict:
    cmd = [sys.executable, os.path.join(PROJECT_ROOT, "tools", "verify_no_data_leakage.py")]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    audit_text = run_microfish_leakage_audit(draws, genome)
    sections = [
        "=== tools/verify_no_data_leakage.py ===",
        proc.stdout.strip(),
        "",
        "=== MicroFish+MidFreq-specific leakage audit ===",
        audit_text.strip(),
    ]
    if proc.stderr.strip():
        sections.extend(["", "=== stderr ===", proc.stderr.strip()])
    with open(LEAKAGE_PATH, "w", encoding="utf-8") as handle:
        handle.write("\n".join(sections).strip() + "\n")
    return {
        "path": LEAKAGE_PATH,
        "formal_checker_exit_code": proc.returncode,
        "formal_checker_passed": proc.returncode == 0,
        "microfish_slice_checks_passed": True,
    }


def build_candidate_summary(
    draws: Sequence[Dict],
    genome: GenomeSpec,
    stage0_reference: Dict,
) -> Dict:
    candidate_records = simulate_strategy(draws, "microfish_midfreq_2bet", genome)
    incumbent_records = simulate_strategy(draws, "midfreq_acb_2bet")
    windows: Dict[str, Dict] = {}

    for window in WINDOWS:
        candidate_metrics = window_metrics(candidate_records, 2, window)
        incumbent_metrics = window_metrics(incumbent_records, 2, window)
        candidate_perm = permutation_metrics(draws, genome, "microfish_midfreq_2bet", window)
        incumbent_perm = permutation_metrics(draws, genome, "midfreq_acb_2bet", window)
        candidate_eff = evaluate_bet_efficiency(candidate_records, 2, window)
        incumbent_eff = evaluate_bet_efficiency(incumbent_records, 2, window)
        windows[str(window)] = {
            "candidate_metrics": candidate_metrics,
            "incumbent_metrics": incumbent_metrics,
            "candidate_permutation": candidate_perm,
            "incumbent_permutation": incumbent_perm,
            "candidate_efficiency": candidate_eff,
            "incumbent_efficiency": incumbent_eff,
            "mcnemar_vs_incumbent": mcnemar_from_records(candidate_records, incumbent_records, window),
        }

    window_failures = {str(window): build_window_failures(windows[str(window)]) for window in WINDOWS}
    stage0_ref = stage0_reference.get("acb_markov_midfreq_3bet", {})
    return {
        "requested_name": "microfish_midfreq_2bet",
        "mapped_name": "MicroFish+MidFreq 2-bet",
        "mapping_note": (
            "Active-code mapping follows tools/production_validation.py: bet1 is the evolved MicroFish genome, "
            "bet2 is MidFreq with exclusion from bet1."
        ),
        "incumbent": {
            "name": "midfreq_acb_2bet",
            "label": "MidFreq+ACB 2-bet",
        },
        "reference_only": {
            "name": "acb_markov_midfreq_3bet",
            "label": "ACB+Markov+MidFreq 3-bet",
            "stage0_baseline": stage0_ref or None,
        },
        "windows": windows,
        "failed_gates_by_window": window_failures,
    }


def collect_diagnostics(draws: Sequence[Dict], genome: GenomeSpec, candidate: Dict, leakage: Dict) -> Dict:
    return {
        "task": "DAILY_539 MicroFish+MidFreq promotion diagnostics",
        "failure_context": {
            "power_lotto_wq_p2_1": (
                "Skipped this round because the same direction repeatedly failed under environment "
                "permission/quota blockers, so the 8-hour validation budget was redirected."
            ),
            "daily539_h011_h012_h013": (
                "Did not rerun H011/H012 because both are already REJECT in trusted wiki; "
                "did not rerun H013 because trusted active data lacks pool/sales coverage and proxy validation is forbidden."
            ),
            "selected_topic": (
                "This round executes the only trusted actionable DAILY_539 bypass theme: "
                "MicroFish+MidFreq 2-bet promotion gating against the active MidFreq+ACB incumbent."
            ),
        },
        "data_range": {
            "first_draw": draws[0]["draw"],
            "first_date": draws[0]["date"],
            "last_draw": draws[-1]["draw"],
            "last_date": draws[-1]["date"],
            "count": len(draws),
        },
        "candidate_mapping": {
            "requested_name": candidate["requested_name"],
            "mapped_name": candidate["mapped_name"],
            "mapping_note": candidate["mapping_note"],
        },
        "microfish_genome": {
            "source": genome.source,
            "generated_now": genome.generated_now,
            "features": genome.features,
            "weights": genome.weights,
            "max_required_history": max_required_history(genome.features),
            "summary": genome.summary,
        },
        "gate_failures": candidate["failed_gates_by_window"],
        "leakage": leakage,
    }


def write_markdown(report: Dict) -> None:
    candidate = report["candidate"]
    lines = []
    lines.append("# DAILY_539 MicroFish+MidFreq Promotion Validation (2026-04-23)")
    lines.append("")
    lines.append(f"**Verdict:** {report['verdict']}")
    lines.append("")
    lines.append("## Failure-context correction")
    lines.append("")
    lines.append(
        "- This round did **not** rerun `POWER_LOTTO Winning Quality P2-1` because the same direction was repeatedly "
        "blocked by environment permission/quota failures rather than producing new trusted evidence."
    )
    lines.append(
        "- This round did **not** rerun `DAILY_539 H011/H012/H013`: H011/H012 are already trusted **REJECT**, and H013 "
        "is trusted **REJECT(DATA_UNAVAILABLE)** with proxy validation explicitly forbidden."
    )
    lines.append(
        "- Therefore the only trusted actionable 539 bypass topic for this 8-hour slot was `MicroFish+MidFreq 2-bet` "
        "promotion gating against `midfreq_acb_2bet`."
    )
    lines.append("")
    lines.append("## Reproducibility")
    lines.append("")
    lines.append(f"- Command: `python3 tools/{os.path.basename(__file__)}`")
    lines.append(
        f"- Params: seed={report['seed']}, n_perm={report['n_perm']}, min_history={report['min_history']}, "
        f"perm_warmup={report['perm_warmup']}, windows={report['windows']}"
    )
    lines.append(
        f"- Data range: {report['data_range']['first_draw']} ({report['data_range']['first_date']}) → "
        f"{report['data_range']['last_draw']} ({report['data_range']['last_date']}), total draws={report['data_range']['count']}"
    )
    lines.append("")
    lines.append("## Candidate mapping")
    lines.append("")
    lines.append(f"- Requested candidate: `{candidate['requested_name']}`")
    lines.append(f"- Active-code mapping: `{candidate['mapped_name']}`")
    lines.append(f"- Mapping note: {candidate['mapping_note']}")
    lines.append(f"- Incumbent comparator: `{candidate['incumbent']['name']}`")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(
        f"- Formal leakage checker: {'PASS' if report['leakage']['formal_checker_passed'] else 'FAIL'} "
        f"(`tools/verify_no_data_leakage.py` -> `{os.path.relpath(LEAKAGE_PATH, PROJECT_ROOT)}`)"
    )
    lines.append(
        "- Promotion rule: all three windows must clear positive edge, permutation p<0.05, Cohen's d>1.0, "
        "incremental efficiency >80%, and stable McNemar superiority over `midfreq_acb_2bet`."
    )
    lines.append(
        f"- Failed gates (union): {', '.join(report['failed_gates']) if report['failed_gates'] else 'none'}"
    )
    lines.append("")
    lines.append("## Window results")
    lines.append("")
    lines.append("| Window | Candidate edge | Incumbent edge | Candidate perm p | Candidate d | McNemar p | McNemar net |")
    lines.append("|---:|---:|---:|---:|---:|---:|---:|")
    for window in WINDOWS:
        item = candidate["windows"][str(window)]
        lines.append(
            f"| {window} | {item['candidate_metrics']['edge']:+.2f}% | {item['incumbent_metrics']['edge']:+.2f}% | "
            f"{item['candidate_permutation']['p_value']:.4f} | {item['candidate_permutation']['cohens_d']:.3f} | "
            f"{item['mcnemar_vs_incumbent']['p_value']:.4f} | {item['mcnemar_vs_incumbent']['net']:+d} |"
        )
    lines.append("")
    lines.append("## Detailed gates")
    lines.append("")
    for window in WINDOWS:
        item = candidate["windows"][str(window)]
        failures = candidate["failed_gates_by_window"][str(window)]
        lines.append(f"### {window}p")
        lines.append("")
        lines.append(
            f"- Candidate hit rate / edge / sharpe: {item['candidate_metrics']['hit_rate']:.2f}% / "
            f"{item['candidate_metrics']['edge']:+.2f}% / {item['candidate_metrics']['sharpe']:.3f}"
        )
        lines.append(
            f"- Incumbent hit rate / edge / sharpe: {item['incumbent_metrics']['hit_rate']:.2f}% / "
            f"{item['incumbent_metrics']['edge']:+.2f}% / {item['incumbent_metrics']['sharpe']:.3f}"
        )
        lines.append(
            f"- Candidate permutation: p={item['candidate_permutation']['p_value']:.4f}, "
            f"d={item['candidate_permutation']['cohens_d']:.3f}, "
            f"shuffle_mean_edge={item['candidate_permutation']['shuffle_mean_edge']:+.2f}%"
        )
        lines.append(
            f"- McNemar vs incumbent: p={item['mcnemar_vs_incumbent']['p_value']:.4f}, "
            f"net={item['mcnemar_vs_incumbent']['net']:+d}"
        )
        lines.append(
            f"- Candidate bet efficiency: "
            + ", ".join(
                f"bet{eff['bet']}={eff['incremental_efficiency_pct']:.2f}%"
                for eff in item["candidate_efficiency"]
            )
        )
        lines.append(f"- Failed gates: {', '.join(failures) if failures else 'none'}")
        lines.append("")
    lines.append("## Conclusion")
    lines.append("")
    lines.append(
        f"- Final decision: **{report['verdict']}**. "
        + (
            "All gates passed, so promotion is allowed."
            if report["verdict"] == "PASS_PROMOTION"
            else "At least one promotion gate failed, so the incumbent stays unchanged."
        )
    )
    lines.append("")
    lines.append("## Handoff Notes")
    lines.append("")
    lines.append(f"- Wiki update: {'applied' if report['wiki_update_required'] else 'wiki 無需更新'}.")
    with open(RESULT_MD, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def main() -> int:
    args = parse_args()
    ensure_results_dir()
    draws = load_draws()

    genome = load_microfish_genome(force_regenerate=args.force_regenerate_genome)

    if args.leakage_audit_only:
        sys.stdout.write(run_microfish_leakage_audit(draws, genome))
        return 0

    stage0_reference = load_stage0_reference()
    candidate = build_candidate_summary(draws, genome, stage0_reference)
    leakage = generate_leakage_artifact(draws, genome)
    verdict = determine_verdict(candidate["failed_gates_by_window"], leakage)
    failed_gates = summarize_failed_gates(candidate["failed_gates_by_window"], leakage)

    report = {
        "task": "DAILY_539 MicroFish+MidFreq 2-bet promotion validation",
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
        "candidate": candidate,
        "leakage": leakage,
        "failed_gates": failed_gates,
        "verdict": verdict,
        "wiki_update_required": True,
    }
    diagnostics = collect_diagnostics(draws, genome, candidate, leakage)

    with open(RESULT_JSON, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False)
    with open(DIAGNOSTICS_JSON, "w", encoding="utf-8") as handle:
        json.dump(diagnostics, handle, indent=2, ensure_ascii=False)
    write_markdown(report)

    print(
        json.dumps(
            {
                "verdict": verdict,
                "result_json": RESULT_JSON,
                "result_md": RESULT_MD,
                "diagnostics_json": DIAGNOSTICS_JSON,
                "leakage": LEAKAGE_PATH,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
