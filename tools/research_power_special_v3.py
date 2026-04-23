#!/usr/bin/env python3
"""
POWER_LOTTO special_v3 orthogonal research
=========================================

Standalone research script for second-zone (special ball) candidates.

What it does:
1. Inventories the existing V3 claim source.
2. Evaluates up to three strict walk-forward special-only candidates.
3. Runs 150 / 500 / 1500-window OOS validation.
4. Runs 200-shuffle permutation tests with seed=42.
5. Performs explicit no-leakage checks per candidate.
6. Writes JSON + Markdown summaries under analysis/results/.
"""

from __future__ import annotations

import json
import math
import os
import random
from collections import Counter
from dataclasses import dataclass
from typing import Callable, Dict, List, Sequence

import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULT_JSON = os.path.join(PROJECT_ROOT, 'analysis', 'results', 'power_special_v3_research_20260422.json')
RESULT_MD = os.path.join(PROJECT_ROOT, 'analysis', 'results', 'power_special_v3_research_20260422.md')

SEED = 42
N_PERM = 200
WINDOWS = (150, 500, 1500)
MIN_HISTORY = 120
SPECIAL_BASELINES = {
    1: 0.125,
    2: 0.250,
    3: 0.375,
}


def _bootstrap_paths() -> None:
    import sys

    sys.path.insert(0, PROJECT_ROOT)
    sys.path.insert(0, os.path.join(PROJECT_ROOT, 'lottery_api'))


_bootstrap_paths()

from lottery_api.common import get_lottery_rules
from lottery_api.database import DatabaseManager
from lottery_api.models.special_predictor import PowerLottoSpecialPredictor


@dataclass(frozen=True)
class Candidate:
    name: str
    top_k: int
    thesis: str
    definition: str
    scorer: Callable[[Sequence[Dict]], Dict[int, float]]


def _normalize_scores(scores: Dict[int, float]) -> Dict[int, float]:
    ordered = {n: float(scores.get(n, 0.0)) for n in range(1, 9)}
    values = list(ordered.values())
    lo = min(values)
    hi = max(values)
    if hi - lo < 1e-12:
        return {n: 1.0 / 8.0 for n in ordered}
    scaled = {n: (v - lo) / (hi - lo) for n, v in ordered.items()}
    total = sum(scaled.values())
    if total <= 1e-12:
        return {n: 1.0 / 8.0 for n in ordered}
    return {n: scaled[n] / total for n in ordered}


def _special_sequence(history: Sequence[Dict], window: int | None = None) -> List[int]:
    sliced = history[-window:] if window else history
    return [draw['special'] for draw in sliced if draw.get('special')]


def score_drought_regime(history: Sequence[Dict]) -> Dict[int, float]:
    recent = list(history[-180:])
    if not recent:
        return {n: 1.0 / 8.0 for n in range(1, 9)}

    last_seen = {n: None for n in range(1, 9)}
    for idx, draw in enumerate(recent):
        last_seen[draw['special']] = idx

    recent_24 = Counter(_special_sequence(recent, 24))
    recent_6 = Counter(_special_sequence(recent, 6))
    length = len(recent)
    raw = {}
    for num in range(1, 9):
        gap = length - last_seen[num] - 1 if last_seen[num] is not None else length + 1
        raw[num] = (
            0.65 * min(gap, 18)
            + 0.25 * max(0, 3 - recent_24.get(num, 0))
            + 0.10 * max(0, 2 - recent_6.get(num, 0))
        )
    return _normalize_scores(raw)


def score_markov_backoff(history: Sequence[Dict]) -> Dict[int, float]:
    seq = _special_sequence(history, 360)
    if not seq:
        return {n: 1.0 / 8.0 for n in range(1, 9)}

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
    return _normalize_scores(raw)


def score_main_analog_residual(history: Sequence[Dict]) -> Dict[int, float]:
    recent = list(history[-360:])
    if len(recent) < 80:
        return {n: 1.0 / 8.0 for n in range(1, 9)}

    anchor = recent[-1]
    anchor_sum = sum(anchor['numbers'])
    anchor_odd = sum(1 for num in anchor['numbers'] if num % 2)
    anchor_z3 = sum(1 for num in anchor['numbers'] if num > 25)

    analog_scores = {n: 0.0 for n in range(1, 9)}
    for draw in recent:
        draw_sum = sum(draw['numbers'])
        draw_odd = sum(1 for num in draw['numbers'] if num % 2)
        draw_z3 = sum(1 for num in draw['numbers'] if num > 25)
        distance = (
            abs(draw_sum - anchor_sum) / 16.0
            + abs(draw_odd - anchor_odd) * 0.8
            + abs(draw_z3 - anchor_z3) * 0.6
        )
        analog_scores[draw['special']] += math.exp(-distance)

    analog_scores = _normalize_scores(analog_scores)
    drought_scores = score_drought_regime(history)
    blended = {
        num: 0.50 * analog_scores[num] + 0.50 * drought_scores[num]
        for num in range(1, 9)
    }
    return _normalize_scores(blended)


CANDIDATES = [
    Candidate(
        name='special_v3_drought_regime_top2',
        top_k=2,
        thesis='Recency / drought regime on the special ball may be exploitable as a shortlist.',
        definition='Score = bounded drought gap (180 draws) + recent under-representation (24 draws) + repeat penalty (6 draws); output top-2 shortlist.',
        scorer=score_drought_regime,
    ),
    Candidate(
        name='special_v3_markov_backoff_top2',
        top_k=2,
        thesis='Recent transition structure may help if first-order and second-order states are blended with an under-owned backoff.',
        definition='Score = 55% first-order transition + 25% second-order transition + 20% recent under-representation, using a 360-draw state window; output top-2 shortlist.',
        scorer=score_markov_backoff,
    ),
    Candidate(
        name='special_v3_main_analog_residual_top2',
        top_k=2,
        thesis='A special-only shortlist might be improved by retrieving historical specials under main-zone states analogous to the latest observed main-zone configuration, then blending with drought.',
        definition='Score = 50% main-zone analog retrieval over the latest observed main-zone state (sum / odd count / Z3 count over 360 draws) + 50% drought-regime score; output top-2 shortlist.',
        scorer=score_main_analog_residual,
    ),
]


def load_draws() -> List[Dict]:
    db_path = os.path.join(PROJECT_ROOT, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path=db_path)
    draws = sorted(db.get_all_draws('POWER_LOTTO'), key=lambda row: (row['date'], row['draw']))
    cleaned = [row for row in draws if row.get('special')]
    if not cleaned:
        raise RuntimeError('No POWER_LOTTO draws with special numbers found.')
    return cleaned


def validate_no_leakage(draws: Sequence[Dict], target_idx: int, history: Sequence[Dict]) -> None:
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


def top_k_from_scores(scores: Dict[int, float], top_k: int) -> List[int]:
    ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    return [num for num, _ in ranked[:top_k]]


def edge_baseline(top_k: int) -> float:
    baseline = SPECIAL_BASELINES.get(top_k)
    if baseline is None:
        raise KeyError(f'Unsupported top_k={top_k} for special baseline.')
    return baseline


def evaluate_candidate(
    draws: Sequence[Dict],
    candidate: Candidate,
    window: int,
    *,
    run_leakage_check: bool,
) -> Dict:
    start_idx = max(MIN_HISTORY, len(draws) - window)
    hits = 0
    total = 0
    predictions = []
    leakage_checks = 0

    for target_idx in range(start_idx, len(draws)):
        history = draws[:target_idx]
        if run_leakage_check:
            validate_no_leakage(draws, target_idx, history)
            leakage_checks += 1

        scores = candidate.scorer(history)
        picks = top_k_from_scores(scores, candidate.top_k)
        actual_special = draws[target_idx]['special']
        hit = actual_special in picks

        hits += int(hit)
        total += 1
        if len(predictions) < 5:
            predictions.append(
                {
                    'draw': draws[target_idx]['draw'],
                    'actual_special': actual_special,
                    'picks': picks,
                    'hit': hit,
                }
            )

    baseline = edge_baseline(candidate.top_k)
    rate = hits / total if total else 0.0
    edge = rate - baseline
    marginal_efficiency = (rate / baseline * 100.0) if baseline else 0.0
    return {
        'window': window,
        'top_k': candidate.top_k,
        'n_oos': total,
        'hits': hits,
        'hit_rate': round(rate * 100.0, 2),
        'baseline': round(baseline * 100.0, 2),
        'edge': round(edge * 100.0, 2),
        'marginal_efficiency': round(marginal_efficiency, 1),
        'sample_predictions': predictions,
        'leakage_checks': leakage_checks,
    }


def shuffle_specials(draws: Sequence[Dict], rng: random.Random) -> List[Dict]:
    shuffled_specials = [row['special'] for row in draws]
    rng.shuffle(shuffled_specials)
    result = []
    for idx, draw in enumerate(draws):
        copied = dict(draw)
        copied['special'] = shuffled_specials[idx]
        result.append(copied)
    return result


def permutation_test(draws: Sequence[Dict], candidate: Candidate, window: int) -> Dict:
    real_eval = evaluate_candidate(draws, candidate, window, run_leakage_check=False)
    real_edge = real_eval['edge'] / 100.0

    rng = random.Random(SEED)
    shuffle_edges = []
    for _ in range(N_PERM):
        shuffled_draws = shuffle_specials(draws, rng)
        shuffled_eval = evaluate_candidate(shuffled_draws, candidate, window, run_leakage_check=False)
        shuffle_edges.append(shuffled_eval['edge'] / 100.0)

    shuffle_mean = float(np.mean(shuffle_edges))
    shuffle_std = float(np.std(shuffle_edges))
    if shuffle_std <= 1e-9:
        shuffle_std = 1e-9

    greater_equal = sum(1 for edge in shuffle_edges if edge >= real_edge)
    p_emp = (greater_equal + 1) / (N_PERM + 1)
    cohens_d = (real_edge - shuffle_mean) / shuffle_std

    return {
        'p_emp': round(p_emp, 4),
        'cohens_d': round(cohens_d, 3),
        'shuffle_mean_edge': round(shuffle_mean * 100.0, 2),
        'shuffle_std_edge': round(shuffle_std * 100.0, 2),
        'n_perm': N_PERM,
    }


def classify_candidate(window_results: Dict[int, Dict]) -> Dict[str, str | List[str]]:
    gates = []
    edges_positive = all(result['edge'] > 0 for result in window_results.values())
    p_pass = all(result['permutation']['p_emp'] < 0.05 for result in window_results.values())
    d_pass = all(result['permutation']['cohens_d'] > 1.0 for result in window_results.values())
    eff_pass = all(result['marginal_efficiency'] > 80.0 for result in window_results.values())

    if not edges_positive:
        gates.append('one or more windows have non-positive Edge')
    if not p_pass:
        gates.append('permutation p-value does not clear 0.05 in all windows')
    if not d_pass:
        gates.append("Cohen's d does not clear 1.0 in all windows")
    if not eff_pass:
        gates.append('marginal efficiency does not clear 80% in all windows')

    if edges_positive and p_pass and d_pass and eff_pass:
        verdict = 'PASS'
    elif edges_positive:
        verdict = 'WATCH'
    else:
        verdict = 'REJECT'

    return {'verdict': verdict, 'gates_missing': gates}


def evaluate_existing_v3_reference(draws: Sequence[Dict]) -> Dict:
    rules = get_lottery_rules('POWER_LOTTO')
    predictor = PowerLottoSpecialPredictor(rules)
    results = {}
    for window in (150, 500, 1000, 1500):
        start_idx = max(MIN_HISTORY, len(draws) - window)
        hits = 0
        total = 0
        for target_idx in range(start_idx, len(draws)):
            history = draws[:target_idx]
            validate_no_leakage(draws, target_idx, history)
            prediction = predictor.predict_top_n(history, n=1)[0]
            hits += int(prediction == draws[target_idx]['special'])
            total += 1
        rate = hits / total if total else 0.0
        results[str(window)] = {
            'n_oos': total,
            'hit_rate': round(rate * 100.0, 2),
            'edge': round((rate - SPECIAL_BASELINES[1]) * 100.0, 2),
        }
    return results


def build_inventory(reference_results: Dict) -> Dict:
    return {
        'version_notes': [
            'Historical +2.20% source is the 1000-period, 1-pick V3 claim documented in lottery_api/CLAUDE.md, tools/sbp_audit_special_v3.py, and rejected/special_mab_decay_adjustment_power.json.',
            'tools/verify_special_v2_performance.py and tools/verify_special_v3_performance.py both instantiate the same PowerLottoSpecialPredictor, so they are wrapper labels rather than distinct independent baselines.',
            'tools/analyze_special_number.py contains the older exploratory V1-style family (random / hot / cold / Markov / repeater), not the current production-strength V3 stack.',
        ],
        'current_v3_reference_rerun': reference_results,
        'historical_claim_source': {
            'claude_md': 'lottery_api/CLAUDE.md',
            'audit_script': 'tools/sbp_audit_special_v3.py',
            'rejected_note': 'rejected/special_mab_decay_adjustment_power.json',
        },
    }


def overall_decision(candidate_results: List[Dict]) -> Dict:
    pass_candidates = [row for row in candidate_results if row['summary']['verdict'] == 'PASS']
    watch_candidates = [row for row in candidate_results if row['summary']['verdict'] == 'WATCH']
    if pass_candidates:
        best = max(
            pass_candidates,
            key=lambda row: (
                row['windows']['1500']['edge'],
                -row['windows']['1500']['permutation']['p_emp'],
            ),
        )
        return {
            'verdict': 'PASS',
            'best_candidate': best['name'],
            'next_round_priority': 'yes',
            'rsm_upgrade_note': 'PASS is still research-only here; do not directly upgrade RSM without a dedicated replacement decision.',
        }
    if watch_candidates:
        best = max(
            watch_candidates,
            key=lambda row: (
                row['windows']['1500']['edge'],
                -row['windows']['1500']['permutation']['p_emp'],
            ),
        )
        return {
            'verdict': 'WATCH',
            'best_candidate': best['name'],
            'next_round_priority': 'no',
            'rsm_upgrade_note': 'WATCH only; not a direct RSM upgrade and not worth displacing the current V3 stack.',
        }
    best = max(
        candidate_results,
        key=lambda row: row['windows']['1500']['edge'],
    )
    return {
        'verdict': 'REJECT',
        'best_candidate': best['name'],
        'next_round_priority': 'no',
        'rsm_upgrade_note': 'REJECT; keep special_v3 improvement work out of the next priority slot unless new evidence appears.',
    }


def markdown_summary(payload: Dict) -> str:
    lines = []
    lines.append('# POWER_LOTTO Special V3 Research (2026-04-22)')
    lines.append('')
    lines.append('## Inventory')
    lines.append('')
    for item in payload['inventory']['version_notes']:
        lines.append(f'- {item}')
    lines.append('')
    lines.append('### Current V3 reference rerun')
    lines.append('')
    lines.append('| Window | Hit Rate | Edge |')
    lines.append('|---|---:|---:|')
    for window, metrics in payload['inventory']['current_v3_reference_rerun'].items():
        lines.append(f"| {window} | {metrics['hit_rate']:.2f}% | {metrics['edge']:+.2f}% |")
    lines.append('')
    lines.append('## Candidate results')
    lines.append('')
    for candidate in payload['candidates']:
        lines.append(f"### {candidate['name']}")
        lines.append('')
        lines.append(f"- Thesis: {candidate['thesis']}")
        lines.append(f"- Definition: {candidate['definition']}")
        lines.append(f"- Verdict: **{candidate['summary']['verdict']}**")
        if candidate['summary']['gates_missing']:
            lines.append(f"- Missing gates: {', '.join(candidate['summary']['gates_missing'])}")
        lines.append('')
        lines.append("| Window | Top-k | Hit Rate | Baseline | Edge | p-value | Cohen's d | Efficiency | Leakage |")
        lines.append('|---|---:|---:|---:|---:|---:|---:|---:|---|')
        for window in WINDOWS:
            metrics = candidate['windows'][str(window)]
            perm = metrics['permutation']
            lines.append(
                f"| {window} | {metrics['top_k']} | {metrics['hit_rate']:.2f}% | {metrics['baseline']:.2f}% | "
                f"{metrics['edge']:+.2f}% | {perm['p_emp']:.4f} | {perm['cohens_d']:.3f} | "
                f"{metrics['marginal_efficiency']:.1f}% | {metrics['leakage_checks']} checks |"
            )
        lines.append('')
    lines.append('## Final conclusion')
    lines.append('')
    lines.append(f"- Overall verdict: **{payload['final_decision']['verdict']}**")
    lines.append(f"- Best candidate: `{payload['final_decision']['best_candidate']}`")
    lines.append(f"- RSM note: {payload['final_decision']['rsm_upgrade_note']}")
    lines.append(
        f"- Worth making the next main POWER_LOTTO research priority? **{payload['final_decision']['next_round_priority']}**"
    )
    return '\n'.join(lines) + '\n'


def main() -> None:
    random.seed(SEED)
    np.random.seed(SEED)
    draws = load_draws()
    reference_results = evaluate_existing_v3_reference(draws)
    inventory = build_inventory(reference_results)

    candidate_results = []
    for candidate in CANDIDATES:
        window_results = {}
        for window in WINDOWS:
            metrics = evaluate_candidate(draws, candidate, window, run_leakage_check=True)
            metrics['permutation'] = permutation_test(draws, candidate, window)
            window_results[str(window)] = metrics
        summary = classify_candidate({int(k): v for k, v in window_results.items()})
        candidate_results.append(
            {
                'name': candidate.name,
                'top_k': candidate.top_k,
                'thesis': candidate.thesis,
                'definition': candidate.definition,
                'windows': window_results,
                'summary': summary,
            }
        )

    final_decision = overall_decision(candidate_results)
    payload = {
        'seed': SEED,
        'n_perm': N_PERM,
        'windows': list(WINDOWS),
        'inventory': inventory,
        'candidates': candidate_results,
        'final_decision': final_decision,
        'wiki_update': 'pending',
    }

    os.makedirs(os.path.dirname(RESULT_JSON), exist_ok=True)
    with open(RESULT_JSON, 'w', encoding='utf-8') as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    with open(RESULT_MD, 'w', encoding='utf-8') as handle:
        handle.write(markdown_summary(payload))

    print(json.dumps(
        {
            'result_json': RESULT_JSON,
            'result_markdown': RESULT_MD,
            'overall_verdict': final_decision['verdict'],
            'best_candidate': final_decision['best_candidate'],
        },
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == '__main__':
    main()
