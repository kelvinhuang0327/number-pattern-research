#!/usr/bin/env python3
"""
POWER_LOTTO special V4 orthogonal reinforcement validation.

This script validates 3-5 history-only top-2 candidates derived from the
existing POWER_LOTTO special V3 feature family. It performs:

1. Strict walk-forward OOS evaluation on 150 / 500 / 1500 windows.
2. 200-shuffle permutation tests with seed=42.
3. Cohen's d and marginal-efficiency checks.
4. Internal leakage checks plus the formal external leakage verifier.
5. McNemar replacement test versus current special V3 top-2 only if a
   candidate clears every validation gate.
"""

from __future__ import annotations

import json
import math
import os
import random
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import date
from multiprocessing import Pool, cpu_count
from typing import Callable, Dict, List, Mapping, Sequence

import numpy as np


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATE_TAG = date.today().strftime('%Y%m%d')
RESULT_JSON = os.path.join(
    PROJECT_ROOT,
    'analysis',
    'results',
    f'power_special_v4_validation_{DATE_TAG}.json',
)

SEED = 42
N_PERM = 200
WINDOWS = (150, 500, 1500)
MIN_HISTORY = 120
SPECIAL_BASELINE_TOP2 = 0.25
MAX_WORKERS = min(4, max(1, cpu_count() or 1))

PERMUTATION_DRAWS: Sequence[dict] | None = None


def _bootstrap_paths() -> None:
    sys.path.insert(0, PROJECT_ROOT)
    sys.path.insert(0, os.path.join(PROJECT_ROOT, 'lottery_api'))


_bootstrap_paths()

from lottery_api.common import get_lottery_rules
from lottery_api.database import DatabaseManager
from lottery_api.models.special_predictor import PowerLottoSpecialPredictor


ScoreMap = Dict[int, float]
ComponentMap = Dict[str, ScoreMap]


@dataclass(frozen=True)
class Candidate:
    name: str
    thesis: str
    definition: str
    formula: Callable[[ComponentMap, Mapping[str, float]], ScoreMap]


def normalize_scores(scores: Mapping[int, float]) -> ScoreMap:
    ordered = {num: float(scores.get(num, 0.0)) for num in range(1, 9)}
    lo = min(ordered.values())
    hi = max(ordered.values())
    if hi - lo < 1e-12:
        return {num: 1.0 / 8.0 for num in ordered}

    scaled = {num: (value - lo) / (hi - lo) for num, value in ordered.items()}
    total = sum(scaled.values())
    if total <= 1e-12:
        return {num: 1.0 / 8.0 for num in ordered}
    return {num: scaled[num] / total for num in ordered}


def blend_components(components: ComponentMap, weights: Mapping[str, float]) -> ScoreMap:
    blended = {num: 0.0 for num in range(1, 9)}
    for component_name, weight in weights.items():
        component = components[component_name]
        for num in blended:
            blended[num] += component[num] * weight
    return normalize_scores(blended)


def special_sequence(history: Sequence[dict], window: int | None = None) -> List[int]:
    sliced = history[-window:] if window else history
    return [draw['special'] for draw in sliced if draw.get('special')]


def validate_no_leakage(draws: Sequence[dict], target_idx: int, history: Sequence[dict]) -> None:
    if len(history) != target_idx:
        raise ValueError(f'History length mismatch: expected {target_idx}, got {len(history)}')
    if not history:
        return

    latest_history = history[-1]
    target = draws[target_idx]
    if latest_history['draw'] >= target['draw']:
        raise ValueError(
            f"Draw leakage detected: latest history draw {latest_history['draw']} >= target {target['draw']}"
        )
    if latest_history['date'] >= target['date']:
        raise ValueError(
            f"Date leakage detected: latest history date {latest_history['date']} >= target {target['date']}"
        )


def top_k_from_scores(scores: Mapping[int, float], top_k: int = 2) -> List[int]:
    ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    return [num for num, _ in ranked[:top_k]]


def score_drought_regime(history: Sequence[dict]) -> ScoreMap:
    recent = list(history[-180:])
    if not recent:
        return {num: 1.0 / 8.0 for num in range(1, 9)}

    last_seen = {num: None for num in range(1, 9)}
    for idx, draw in enumerate(recent):
        last_seen[draw['special']] = idx

    recent_24 = Counter(special_sequence(recent, 24))
    recent_6 = Counter(special_sequence(recent, 6))
    length = len(recent)
    raw = {}
    for num in range(1, 9):
        gap = length - last_seen[num] - 1 if last_seen[num] is not None else length + 1
        raw[num] = (
            0.65 * min(gap, 18)
            + 0.25 * max(0, 3 - recent_24.get(num, 0))
            + 0.10 * max(0, 2 - recent_6.get(num, 0))
        )
    return normalize_scores(raw)


def score_markov_backoff(history: Sequence[dict]) -> ScoreMap:
    seq = special_sequence(history, 360)
    if not seq:
        return {num: 1.0 / 8.0 for num in range(1, 9)}

    order1 = Counter()
    order2 = Counter()
    if len(seq) >= 2:
        ctx1 = seq[-1]
        for idx in range(1, len(seq)):
            if seq[idx - 1] == ctx1:
                order1[seq[idx]] += 1

    if len(seq) >= 3:
        ctx2 = tuple(seq[-2:])
        for idx in range(2, len(seq)):
            if tuple(seq[idx - 2:idx]) == ctx2:
                order2[seq[idx]] += 1

    recent_under = Counter(seq[-24:])
    raw = {
        num: (
            0.55 * order1.get(num, 0)
            + 0.25 * order2.get(num, 0)
            + 0.20 * max(0, 3 - recent_under.get(num, 0))
            + 0.10
        )
        for num in range(1, 9)
    }
    return normalize_scores(raw)


def score_main_analog(history: Sequence[dict]) -> ScoreMap:
    recent = list(history[-360:])
    if len(recent) < 80:
        return {num: 1.0 / 8.0 for num in range(1, 9)}

    anchor = recent[-1]
    anchor_sum = sum(anchor['numbers'])
    anchor_odd = sum(1 for num in anchor['numbers'] if num % 2)
    anchor_z3 = sum(1 for num in anchor['numbers'] if num > 25)

    raw = {num: 0.0 for num in range(1, 9)}
    for draw in recent:
        draw_sum = sum(draw['numbers'])
        draw_odd = sum(1 for num in draw['numbers'] if num % 2)
        draw_z3 = sum(1 for num in draw['numbers'] if num > 25)
        distance = (
            abs(draw_sum - anchor_sum) / 16.0
            + abs(draw_odd - anchor_odd) * 0.8
            + abs(draw_z3 - anchor_z3) * 0.6
        )
        raw[draw['special']] += math.exp(-distance)
    return normalize_scores(raw)


def score_gap_pressure(history: Sequence[dict]) -> ScoreMap:
    seq = special_sequence(history)
    if len(seq) < 200:
        return {num: 1.0 / 8.0 for num in range(1, 9)}

    raw = {}
    for num in range(1, 9):
        indices = [idx for idx, value in enumerate(seq) if value == num]
        if len(indices) <= 2:
            raw[num] = 0.2
            continue

        gaps = [indices[i] - indices[i - 1] for i in range(1, len(indices))]
        avg_gap = sum(gaps) / len(gaps)
        max_gap = max(gaps)
        current_gap = len(seq) - 1 - indices[-1]
        if current_gap > avg_gap:
            raw[num] = min(1.0, (current_gap - avg_gap) / max(1.0, max_gap - avg_gap))
        else:
            raw[num] = 0.1
    return normalize_scores(raw)


def score_oscillation(history: Sequence[dict]) -> ScoreMap:
    seq = special_sequence(history, 10)
    scores = {num: 0.1 for num in range(1, 9)}
    if not seq:
        return normalize_scores(scores)

    last_special = seq[-1]
    scores[last_special] += 0.6

    if len(seq) >= 3 and seq[-1] != seq[-2] and seq[-1] == seq[-3]:
        scores[seq[-1]] += 0.3
    if len(seq) >= 4 and seq[-1] == seq[-4]:
        scores[seq[-1]] += 0.2

    return normalize_scores(scores)


def score_modulo_rebalance(history: Sequence[dict]) -> ScoreMap:
    seq = special_sequence(history, 10)
    scores = {num: 0.2 for num in range(1, 9)}
    if not seq:
        return normalize_scores(scores)

    odds = sum(1 for value in seq if value % 2)
    evens = len(seq) - odds
    if odds >= 7:
        for num in range(1, 9):
            if num % 2 == 0:
                scores[num] += 0.4
    elif evens >= 7:
        for num in range(1, 9):
            if num % 2:
                scores[num] += 0.4

    mod_counts = Counter(value % 4 for value in seq)
    for mod in range(4):
        if mod_counts[mod] == 0:
            for num in range(1, 9):
                if num % 4 == mod:
                    scores[num] += 0.2

    return normalize_scores(scores)


def score_bias(history: Sequence[dict]) -> ScoreMap:
    seq = special_sequence(history)
    if not seq:
        return {num: 1.0 / 8.0 for num in range(1, 9)}

    counts = Counter(seq)
    return normalize_scores({num: counts.get(num, 0) + 1 for num in range(1, 9)})


def score_anti_hot(history: Sequence[dict]) -> ScoreMap:
    recent = Counter(special_sequence(history, 15))
    raw = {num: max(0.0, 5.0 - recent.get(num, 0)) for num in range(1, 9)}
    return normalize_scores(raw)


def score_sectional_lift(history: Sequence[dict]) -> ScoreMap:
    if len(history) < 80:
        return {num: 1.0 / 8.0 for num in range(1, 9)}

    main_proxy = history[-1]['numbers']
    sample = history[-1000:]
    total = len(sample)
    special_counts = Counter(draw['special'] for draw in sample)
    number_totals = Counter()
    number_special_counts: Dict[int, Counter] = {num: Counter() for num in range(1, 39)}

    for draw in sample:
        special = draw['special']
        for main_num in draw['numbers']:
            number_totals[main_num] += 1
            number_special_counts[main_num][special] += 1

    lifts = {num: 0.0 for num in range(1, 9)}
    for main_num in main_proxy:
        if number_totals[main_num] == 0:
            continue
        for special in range(1, 9):
            expected = special_counts[special] / total
            observed = number_special_counts[main_num][special] / number_totals[main_num]
            if expected > 0:
                lifts[special] += max(0.0, observed / expected - 1.0)
    return normalize_scores({num: 1.0 + lifts[num] for num in range(1, 9)})


def recent_entropy(history: Sequence[dict]) -> float:
    seq = special_sequence(history, 15)
    if not seq:
        return math.log2(8)
    counts = Counter(seq)
    probs = [count / len(seq) for count in counts.values()]
    return -sum(prob * math.log2(prob) for prob in probs)


def build_components(history: Sequence[dict]) -> tuple[ComponentMap, Dict[str, float]]:
    components = {
        'drought': score_drought_regime(history),
        'markov_backoff': score_markov_backoff(history),
        'main_analog': score_main_analog(history),
        'gap_pressure': score_gap_pressure(history),
        'oscillation': score_oscillation(history),
        'modulo': score_modulo_rebalance(history),
        'bias': score_bias(history),
        'anti_hot': score_anti_hot(history),
        'sectional_lift': score_sectional_lift(history),
    }
    meta = {'entropy_15': recent_entropy(history)}
    return components, meta


def formula_regime_orthogonal(components: ComponentMap, _: Mapping[str, float]) -> ScoreMap:
    return blend_components(
        components,
        {
            'drought': 0.28,
            'markov_backoff': 0.22,
            'oscillation': 0.18,
            'modulo': 0.14,
            'gap_pressure': 0.10,
            'anti_hot': 0.08,
        },
    )


def formula_main_lift_residual(components: ComponentMap, _: Mapping[str, float]) -> ScoreMap:
    return blend_components(
        components,
        {
            'main_analog': 0.32,
            'sectional_lift': 0.24,
            'drought': 0.18,
            'gap_pressure': 0.12,
            'modulo': 0.08,
            'anti_hot': 0.06,
        },
    )


def formula_gap_markov2_balance(components: ComponentMap, _: Mapping[str, float]) -> ScoreMap:
    return blend_components(
        components,
        {
            'gap_pressure': 0.26,
            'markov_backoff': 0.24,
            'drought': 0.18,
            'modulo': 0.14,
            'bias': 0.10,
            'anti_hot': 0.08,
        },
    )


def formula_entropy_switch(components: ComponentMap, meta: Mapping[str, float]) -> ScoreMap:
    if meta['entropy_15'] < 2.35:
        weights = {
            'oscillation': 0.28,
            'markov_backoff': 0.26,
            'modulo': 0.16,
            'drought': 0.12,
            'bias': 0.10,
            'anti_hot': 0.08,
        }
    elif meta['entropy_15'] > 2.80:
        weights = {
            'gap_pressure': 0.28,
            'drought': 0.24,
            'bias': 0.16,
            'main_analog': 0.14,
            'modulo': 0.10,
            'anti_hot': 0.08,
        }
    else:
        weights = {
            'markov_backoff': 0.24,
            'drought': 0.22,
            'gap_pressure': 0.16,
            'main_analog': 0.14,
            'modulo': 0.14,
            'anti_hot': 0.10,
        }
    return blend_components(components, weights)


def formula_bias_modulo_residual(components: ComponentMap, _: Mapping[str, float]) -> ScoreMap:
    return blend_components(
        components,
        {
            'bias': 0.24,
            'modulo': 0.22,
            'main_analog': 0.18,
            'sectional_lift': 0.14,
            'drought': 0.12,
            'anti_hot': 0.10,
        },
    )


CANDIDATES = [
    Candidate(
        name='special_v4_regime_orthogonal_top2',
        thesis='Keep the V3 shortlist in the regime-only lane and rebalance toward drought/Markov/oscillation orthogonality instead of a single dominant signal.',
        definition='Score = 28% drought + 22% Markov backoff + 18% oscillation + 14% modulo rebalance + 10% gap pressure + 8% anti-hot; top-2 output.',
        formula=formula_regime_orthogonal,
    ),
    Candidate(
        name='special_v4_main_lift_residual_top2',
        thesis='Retrieve specials from main-zone analog states, then reinforce only the residual that is supported by sectional lift instead of raw main analog alone.',
        definition='Score = 32% main analog + 24% sectional lift + 18% drought + 12% gap pressure + 8% modulo + 6% anti-hot; top-2 output.',
        formula=formula_main_lift_residual,
    ),
    Candidate(
        name='special_v4_gap_markov2_balance_top2',
        thesis='Test whether the most promising V3 families are actually the gap/Markov intersection, with drought and modulo only as stabilizers.',
        definition='Score = 26% gap pressure + 24% Markov backoff + 18% drought + 14% modulo + 10% bias + 8% anti-hot; top-2 output.',
        formula=formula_gap_markov2_balance,
    ),
    Candidate(
        name='special_v4_entropy_switch_top2',
        thesis='Use V3 features only, but switch the weight stack according to recent special-ball entropy so low-entropy and high-entropy regimes are scored differently.',
        definition='Adaptive score: low-entropy favors oscillation/Markov, high-entropy favors gap/drought/bias, middle regime uses mixed Markov-drought-main analog weights; top-2 output.',
        formula=formula_entropy_switch,
    ),
    Candidate(
        name='special_v4_bias_modulo_residual_top2',
        thesis='Check whether a lighter-weight residual blend centered on long-term bias and modulo rebalance can preserve edge while avoiding the heavier main-analog overfit path.',
        definition='Score = 24% bias + 22% modulo + 18% main analog + 14% sectional lift + 12% drought + 10% anti-hot; top-2 output.',
        formula=formula_bias_modulo_residual,
    ),
]


def load_draws() -> List[dict]:
    db_path = os.path.join(PROJECT_ROOT, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path=db_path)
    draws = sorted(db.get_all_draws('POWER_LOTTO'), key=lambda row: (row['date'], row['draw']))
    cleaned = [row for row in draws if row.get('special')]
    if not cleaned:
        raise RuntimeError('No POWER_LOTTO draws with special numbers found.')
    return cleaned


def evaluate_candidates(draws: Sequence[dict], *, run_leakage_check: bool) -> dict:
    start_idx = max(MIN_HISTORY, len(draws) - max(WINDOWS))
    predictor = PowerLottoSpecialPredictor(get_lottery_rules('POWER_LOTTO'))
    candidate_hits = {candidate.name: [] for candidate in CANDIDATES}
    candidate_predictions = {candidate.name: [] for candidate in CANDIDATES}
    candidate_scores = {candidate.name: [] for candidate in CANDIDATES}
    leakage_checks = 0
    v3_hits = []

    for target_idx in range(start_idx, len(draws)):
        history = draws[:target_idx]
        if run_leakage_check:
            validate_no_leakage(draws, target_idx, history)
            leakage_checks += 1

        components, meta = build_components(history)
        actual_special = draws[target_idx]['special']

        for candidate in CANDIDATES:
            scores = candidate.formula(components, meta)
            picks = top_k_from_scores(scores, top_k=2)
            candidate_scores[candidate.name].append(scores)
            candidate_predictions[candidate.name].append(
                {
                    'draw': draws[target_idx]['draw'],
                    'actual_special': actual_special,
                    'picks': picks,
                    'hit': actual_special in picks,
                }
            )
            candidate_hits[candidate.name].append(int(actual_special in picks))

        v3_picks = predictor.predict_top_n(history, n=2)
        v3_hits.append(int(actual_special in v3_picks))

    return {
        'candidate_hits': candidate_hits,
        'candidate_predictions': candidate_predictions,
        'candidate_scores': candidate_scores,
        'v3_hits': v3_hits,
        'leakage_checks': leakage_checks,
        'start_idx': start_idx,
    }


def window_metrics(hits: Sequence[int], predictions: Sequence[dict], leakage_checks: int, window: int) -> dict:
    window_hits = list(hits[-window:])
    total = len(window_hits)
    hit_rate = sum(window_hits) / total if total else 0.0
    edge = hit_rate - SPECIAL_BASELINE_TOP2
    efficiency = hit_rate / SPECIAL_BASELINE_TOP2 * 100.0 if SPECIAL_BASELINE_TOP2 else 0.0
    edge_series = np.array(window_hits, dtype=float) - SPECIAL_BASELINE_TOP2
    sharpe = 0.0
    if edge_series.size > 1:
        std = float(np.std(edge_series, ddof=1))
        if std > 1e-12:
            sharpe = float(np.mean(edge_series) / std)

    return {
        'window': window,
        'top_k': 2,
        'n_oos': total,
        'hits': int(sum(window_hits)),
        'hit_rate': round(hit_rate * 100.0, 2),
        'baseline': round(SPECIAL_BASELINE_TOP2 * 100.0, 2),
        'edge': round(edge * 100.0, 2),
        'marginal_efficiency': round(efficiency, 1),
        'sharpe': round(sharpe, 3),
        'sample_predictions': list(predictions[-window:][:5]),
        'leakage_checks': min(window, leakage_checks),
    }


def shuffle_specials(draws: Sequence[dict], rng: random.Random) -> List[dict]:
    shuffled_specials = [row['special'] for row in draws]
    rng.shuffle(shuffled_specials)
    shuffled = []
    for idx, draw in enumerate(draws):
        copied = dict(draw)
        copied['special'] = shuffled_specials[idx]
        shuffled.append(copied)
    return shuffled


def permutation_stats(real_edges: Sequence[float]) -> tuple[float, float]:
    mean_edge = float(np.mean(real_edges))
    std_edge = float(np.std(real_edges))
    if std_edge <= 1e-12:
        std_edge = 1e-12
    return mean_edge, std_edge


def run_permutation_tests(draws: Sequence[dict], real_eval: dict) -> Dict[str, Dict[int, dict]]:
    shuffle_edges = {
        candidate.name: {window: [] for window in WINDOWS}
        for candidate in CANDIDATES
    }

    with Pool(processes=MAX_WORKERS, initializer=_init_permutation_worker, initargs=(list(draws),)) as pool:
        for shuffled_result in pool.imap_unordered(_run_single_permutation, range(N_PERM), chunksize=1):
            for candidate in CANDIDATES:
                for window in WINDOWS:
                    shuffle_edges[candidate.name][window].append(shuffled_result[candidate.name][window])

    results: Dict[str, Dict[int, dict]] = {}
    for candidate in CANDIDATES:
        results[candidate.name] = {}
        real_hits = real_eval['candidate_hits'][candidate.name]
        for window in WINDOWS:
            real_edge = sum(real_hits[-window:]) / window - SPECIAL_BASELINE_TOP2
            real_distribution = shuffle_edges[candidate.name][window]
            shuffle_mean, shuffle_std = permutation_stats(real_distribution)
            greater_equal = sum(1 for edge in real_distribution if edge >= real_edge)
            p_emp = (greater_equal + 1) / (N_PERM + 1)
            cohens_d = (real_edge - shuffle_mean) / shuffle_std
            results[candidate.name][window] = {
                'p_emp': round(p_emp, 4),
                'cohens_d': round(cohens_d, 3),
                'shuffle_mean_edge': round(shuffle_mean * 100.0, 2),
                'shuffle_std_edge': round(shuffle_std * 100.0, 2),
                'n_perm': N_PERM,
            }
    return results


def _init_permutation_worker(draws: Sequence[dict]) -> None:
    global PERMUTATION_DRAWS
    PERMUTATION_DRAWS = draws


def _run_single_permutation(perm_index: int) -> Dict[str, Dict[int, float]]:
    if PERMUTATION_DRAWS is None:
        raise RuntimeError('Permutation worker not initialized.')

    rng = random.Random(SEED + perm_index + 1)
    shuffled_draws = shuffle_specials(PERMUTATION_DRAWS, rng)
    shuffled_eval = evaluate_candidates(shuffled_draws, run_leakage_check=False)

    result: Dict[str, Dict[int, float]] = {}
    for candidate in CANDIDATES:
        hits = shuffled_eval['candidate_hits'][candidate.name]
        result[candidate.name] = {}
        for window in WINDOWS:
            result[candidate.name][window] = sum(hits[-window:]) / window - SPECIAL_BASELINE_TOP2
    return result


def candidate_gate_summary(window_results: Dict[int, dict]) -> dict:
    gates = {
        'edge_positive': all(result['edge'] > 0 for result in window_results.values()),
        'permutation_pass': all(result['permutation']['p_emp'] < 0.05 for result in window_results.values()),
        'effect_pass': all(result['permutation']['cohens_d'] > 1.0 for result in window_results.values()),
        'efficiency_pass': all(result['marginal_efficiency'] > 80.0 for result in window_results.values()),
        'sharpe_pass': all(result['sharpe'] > 0 for result in window_results.values()),
    }
    verdict = 'PASS' if all(gates.values()) else ('WATCH' if gates['edge_positive'] else 'REJECT')
    missing = []
    if not gates['edge_positive']:
        missing.append('edge_positive')
    if not gates['permutation_pass']:
        missing.append('permutation_p')
    if not gates['effect_pass']:
        missing.append('cohens_d')
    if not gates['efficiency_pass']:
        missing.append('marginal_efficiency')
    if not gates['sharpe_pass']:
        missing.append('sharpe')
    return {'verdict': verdict, 'gates': gates, 'gates_missing': missing}


def candidate_sort_key(candidate: dict) -> tuple:
    gates = candidate['summary']['gates']
    return (
        sum(1 for passed in gates.values() if passed),
        candidate['windows']['1500']['edge'],
        -candidate['windows']['1500']['permutation']['p_emp'],
        candidate['windows']['1500']['permutation']['cohens_d'],
    )


def minimal_failure_evidence(candidate: dict) -> dict:
    failures = []
    for window in WINDOWS:
        metrics = candidate['windows'][str(window)]
        if metrics['edge'] <= 0:
            failures.append(
                {
                    'gate': 'edge_positive',
                    'window': window,
                    'observed': metrics['edge'],
                    'threshold': '> 0',
                    'margin': abs(metrics['edge']),
                }
            )
        if metrics['permutation']['p_emp'] >= 0.05:
            failures.append(
                {
                    'gate': 'permutation_p',
                    'window': window,
                    'observed': metrics['permutation']['p_emp'],
                    'threshold': '< 0.05',
                    'margin': metrics['permutation']['p_emp'] - 0.05,
                }
            )
        if metrics['permutation']['cohens_d'] <= 1.0:
            failures.append(
                {
                    'gate': 'cohens_d',
                    'window': window,
                    'observed': metrics['permutation']['cohens_d'],
                    'threshold': '> 1.0',
                    'margin': 1.0 - metrics['permutation']['cohens_d'],
                }
            )
        if metrics['marginal_efficiency'] <= 80.0:
            failures.append(
                {
                    'gate': 'marginal_efficiency',
                    'window': window,
                    'observed': metrics['marginal_efficiency'],
                    'threshold': '> 80.0',
                    'margin': 80.0 - metrics['marginal_efficiency'],
                }
            )
        if metrics['sharpe'] <= 0:
            failures.append(
                {
                    'gate': 'sharpe',
                    'window': window,
                    'observed': metrics['sharpe'],
                    'threshold': '> 0',
                    'margin': abs(metrics['sharpe']),
                }
            )
    return min(failures, key=lambda item: item['margin'])


def exact_binom_two_sided(k: int, n: int) -> float:
    if n == 0:
        return 1.0
    probs = [math.comb(n, i) * (0.5 ** n) for i in range(n + 1)]
    observed = probs[k]
    p_value = sum(prob for prob in probs if prob <= observed + 1e-15)
    return min(1.0, p_value)


def run_mcnemar(candidate_hits: Sequence[int], reference_hits: Sequence[int], window: int = 1500) -> dict:
    cand = candidate_hits[-window:]
    ref = reference_hits[-window:]
    b = sum(1 for cand_hit, ref_hit in zip(cand, ref) if cand_hit == 1 and ref_hit == 0)
    c = sum(1 for cand_hit, ref_hit in zip(cand, ref) if cand_hit == 0 and ref_hit == 1)
    p_value = exact_binom_two_sided(min(b, c), b + c)
    return {
        'triggered': True,
        'window': window,
        'candidate_only_hits': b,
        'v3_only_hits': c,
        'p_value': round(p_value, 4),
        'passes_replacement_gate': p_value < 0.05,
    }


def external_leakage_check() -> dict:
    command = [sys.executable, os.path.join(PROJECT_ROOT, 'tools', 'verify_no_data_leakage.py')]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
        check=False,
    )
    combined_output = '\n'.join(
        line for line in [completed.stdout.strip(), completed.stderr.strip()] if line
    )
    success = completed.returncode == 0 and '確認回測過程無數據洩漏' in completed.stdout
    return {
        'command': ' '.join(command),
        'returncode': completed.returncode,
        'status': 'PASS' if success else 'FAIL',
        'evidence_tail': combined_output.splitlines()[-6:],
    }


def current_v3_reference(draws: Sequence[dict]) -> dict:
    predictor = PowerLottoSpecialPredictor(get_lottery_rules('POWER_LOTTO'))
    hits = []
    start_idx = max(MIN_HISTORY, len(draws) - max(WINDOWS))
    for target_idx in range(start_idx, len(draws)):
        history = draws[:target_idx]
        validate_no_leakage(draws, target_idx, history)
        hits.append(int(draws[target_idx]['special'] in predictor.predict_top_n(history, n=2)))

    results = {}
    for window in WINDOWS:
        rate = sum(hits[-window:]) / window
        results[str(window)] = {
            'hit_rate': round(rate * 100.0, 2),
            'edge': round((rate - SPECIAL_BASELINE_TOP2) * 100.0, 2),
        }
    return {'top2_windows': results}


def build_candidate_results(real_eval: dict, permutation_eval: dict) -> List[dict]:
    results = []
    for candidate in CANDIDATES:
        window_results = {}
        hits = real_eval['candidate_hits'][candidate.name]
        predictions = real_eval['candidate_predictions'][candidate.name]
        for window in WINDOWS:
            metrics = window_metrics(hits, predictions, real_eval['leakage_checks'], window)
            metrics['permutation'] = permutation_eval[candidate.name][window]
            window_results[str(window)] = metrics
        summary = candidate_gate_summary({int(key): value for key, value in window_results.items()})
        results.append(
            {
                'name': candidate.name,
                'top_k': 2,
                'thesis': candidate.thesis,
                'definition': candidate.definition,
                'windows': window_results,
                'summary': summary,
            }
        )
    return sorted(results, key=candidate_sort_key, reverse=True)


def final_decision(
    candidate_results: List[dict],
    real_eval: dict,
    leakage_result: dict,
    current_reference: dict,
) -> dict:
    pass_candidates = [candidate for candidate in candidate_results if candidate['summary']['verdict'] == 'PASS']
    best_candidate = candidate_results[0]
    if pass_candidates:
        selected = pass_candidates[0]
        mcnemar = run_mcnemar(
            real_eval['candidate_hits'][selected['name']],
            real_eval['v3_hits'],
            window=1500,
        )
        overall_verdict = 'PASS' if mcnemar['passes_replacement_gate'] else 'REJECT'
        replacement_status = 'REPLACE_V3' if overall_verdict == 'PASS' else 'DO_NOT_REPLACE'
        rejection_evidence = []
    else:
        mcnemar = {
            'triggered': False,
            'window': 1500,
            'p_value': None,
            'reason': 'No candidate cleared all edge/permutation/effect/efficiency/sharpe gates across 150/500/1500.',
        }
        overall_verdict = 'REJECT'
        replacement_status = 'DO_NOT_REPLACE'
        rejection_evidence = [
            {
                'candidate': candidate['name'],
                'minimal_failure': minimal_failure_evidence(candidate),
            }
            for candidate in candidate_results[:2]
        ]

    summary_lines = [
        f"1. Verdict: {overall_verdict}; replacement status: {replacement_status}.",
        f"2. Seed fixed at {SEED}; permutation count fixed at {N_PERM}.",
        f"3. Five history-only top-2 candidates were evaluated on 150 / 500 / 1500 OOS windows.",
        f"4. Best raw candidate: {best_candidate['name']} with 1500p Edge {best_candidate['windows']['1500']['edge']:+.2f}%.",
        f"5. Current V3 top-2 reference on 1500p: {current_reference['top2_windows']['1500']['edge']:+.2f}% Edge.",
        f"6. External leakage verifier: {leakage_result['status']} (returncode={leakage_result['returncode']}).",
        f"7. Internal walk-forward leakage checks executed: {real_eval['leakage_checks']}.",
        f"8. McNemar triggered: {mcnemar['triggered']}.",
        f"9. If triggered, McNemar p-value = {mcnemar['p_value']}.",
        f"10. No production state or engine files were modified.",
    ]

    return {
        'overall_verdict': overall_verdict,
        'replacement_status': replacement_status,
        'best_candidate': best_candidate['name'],
        'top_reject_evidence': rejection_evidence,
        'mcnemar': mcnemar,
        'readable_summary': summary_lines,
    }


def main() -> None:
    random.seed(SEED)
    np.random.seed(SEED)

    draws = load_draws()
    leakage_result = external_leakage_check()
    if leakage_result['status'] != 'PASS':
        raise RuntimeError('verify_no_data_leakage.py failed; aborting V4 validation.')

    real_eval = evaluate_candidates(draws, run_leakage_check=True)
    permutation_eval = run_permutation_tests(draws, real_eval)

    candidate_results = build_candidate_results(real_eval, permutation_eval)
    current_reference = current_v3_reference(draws)
    decision = final_decision(candidate_results, real_eval, leakage_result, current_reference)

    payload = {
        'generated_on': date.today().isoformat(),
        'seed': SEED,
        'n_perm': N_PERM,
        'windows': list(WINDOWS),
        'objective': 'POWER_LOTTO special V3 -> V4 orthogonal reinforcement validation',
        'method': {
            'bet_type': 'top2 shortlist',
            'history_only': True,
            'oos_mode': 'strict walk-forward',
            'baseline_hit_rate_pct': SPECIAL_BASELINE_TOP2 * 100.0,
        },
        'current_v3_reference': current_reference,
        'leakage_check': {
            'internal_history_only': {
                'status': 'PASS',
                'checks': real_eval['leakage_checks'],
            },
            'external_verifier': leakage_result,
        },
        'candidates': candidate_results,
        'final_decision': decision,
        'result_path': os.path.relpath(RESULT_JSON, PROJECT_ROOT),
    }

    os.makedirs(os.path.dirname(RESULT_JSON), exist_ok=True)
    with open(RESULT_JSON, 'w', encoding='utf-8') as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)

    print(json.dumps({'result_json': os.path.relpath(RESULT_JSON, PROJECT_ROOT)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
