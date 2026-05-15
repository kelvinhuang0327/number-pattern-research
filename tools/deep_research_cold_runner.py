#!/usr/bin/env python3
import json
import os
import random
import numpy as np
import sys
from collections import Counter

# ensure project root is importable
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from lottery_api.utils.benchmark_framework import StrategyBenchmark
from lottery_api.engine.perm_test import perm_test

OUT_DIR = os.path.join(PROJECT_ROOT, 'outputs')
os.makedirs(OUT_DIR, exist_ok=True)

# --- Strategy implementations (simple, reproducible heuristics) ---

def cold_lowfreq_2bet(history, rules):
    window = history[-300:]
    freq = Counter()
    for d in window:
        freq.update(d['numbers'])
    all_nums = list(range(1, rules.get('maxNumber', 49) + 1))
    freq_list = sorted(all_nums, key=lambda n: (freq.get(n, 0), n))
    b1 = sorted(freq_list[:6])
    b2 = sorted(freq_list[6:12])
    return [b1, b2]


def shadow_gap_daily_3bet(history, rules):
    last_seen = {n: -1 for n in range(1, rules.get('maxNumber', 49) + 1)}
    for idx, d in enumerate(history):
        for n in d['numbers']:
            last_seen[n] = idx
    gap_sorted = sorted(last_seen.keys(), key=lambda n: ( (len(history)-last_seen[n]) if last_seen[n]>=0 else len(history)+1000), reverse=True)
    bets = []
    for i in range(3):
        start = i*6
        bets.append(sorted(gap_sorted[start:start+6]))
    return bets


def anti_corr_reverse_freq_4bet(history, rules):
    window = history[-300:]
    freq = Counter()
    for d in window:
        freq.update(d['numbers'])
    all_nums = list(range(1, rules.get('maxNumber', 49) + 1))
    freq_sorted = sorted(all_nums, key=lambda n: (-freq.get(n,0), n))
    top12 = set(freq_sorted[:12])
    complement = [n for n in all_nums if n not in top12]
    bets = []
    for i in range(4):
        bets.append(sorted(complement[i*6:(i+1)*6]))
    while len(bets) < 4:
        bets.append(sorted(random.sample(all_nums, 6)))
    return bets


CANDIDATES = [
    {
        'strategy_name': 'cold_lowfreq_2bet',
        'game': 'POWER_LOTTO',
        'fn': cold_lowfreq_2bet,
        'num_bets': 2
    },
    {
        'strategy_name': 'shadow_gap_daily_3bet',
        'game': 'DAILY_539',
        'fn': shadow_gap_daily_3bet,
        'num_bets': 3
    },
    {
        'strategy_name': 'anti_reverse_freq_4bet',
        'game': 'BIG_LOTTO',
        'fn': anti_corr_reverse_freq_4bet,
        'num_bets': 4
    }
]

SUMMARY = []
MC_SUMMARIES = {}

for cand in CANDIDATES:
    name = cand['strategy_name']
    game = cand['game']
    fn = cand['fn']
    bets = cand['num_bets']

    print(f"Running quick benchmark: {name} on {game} (150p)")
    bench = StrategyBenchmark(lottery_type=game, test_periods=150)
    result = bench.evaluate(fn, strategy_name=name, num_bets=bets, use_multi_seed=False)
    bench.print_report(result)

    rdict = result.to_dict()
    out_file = os.path.join(OUT_DIR, f"benchmark_{name}_{game}_150.json")
    # serialize numpy types safely
    import json as _json
    safe = _json.loads(_json.dumps(rdict, default=str))
    with open(out_file, 'w', encoding='utf-8') as f:
        _json.dump(safe, f, indent=2, ensure_ascii=False)

    SUMMARY.append(rdict)

    print(f"Running Monte Carlo bootstrap for {name}: seed=42, n=1000")
    n_mc = 1000
    base_seed = 42
    edges = []
    orig_draws = bench.all_draws
    for i in range(n_mc):
        rng = np.random.RandomState(base_seed + i)
        idxs = rng.randint(0, len(orig_draws), size=len(orig_draws))
        boot_draws = [orig_draws[j] for j in idxs]
        bench_mc = StrategyBenchmark(lottery_type=game, test_periods=150)
        bench_mc.all_draws = boot_draws
        win_rate, _, _score = bench_mc._run_backtest(fn, bets)
        baseline = bench_mc._get_random_baseline(bets, [base_seed])
        edge = win_rate - baseline
        edges.append(edge)
        if (i+1) % 200 == 0:
            print(f"  Monte Carlo {i+1}/{n_mc}")

    edges = np.array(edges)
    mc_summary = {
        'strategy_name': name,
        'game': game,
        'n': n_mc,
        'seed_start': base_seed,
        'edge_mean': float(np.mean(edges)),
        'edge_std': float(np.std(edges)),
        'edge_p5': float(np.percentile(edges, 5)),
        'edge_p95': float(np.percentile(edges, 95)),
        'edges_sample': edges[:50].tolist()
    }
    MC_SUMMARIES[name] = mc_summary
    with open(os.path.join(OUT_DIR, f"mc_{name}_{game}_n{n_mc}_seed{base_seed}.json"), 'w', encoding='utf-8') as f:
        json.dump(mc_summary, f, indent=2, ensure_ascii=False)

TASK_RESULT = {
    'candidates_quick': SUMMARY,
    'monte_carlo': MC_SUMMARIES,
    'mc_params': {'seed': 42, 'n': 1000}
}
import json as _json
with open(os.path.join(OUT_DIR, 'task_result_deep_research.json'), 'w', encoding='utf-8') as f:
    _json.dump(_json.loads(_json.dumps(TASK_RESULT, default=str)), f, indent=2, ensure_ascii=False)

md_lines = [
    '# Deep Research — Cold-phase + Shadow + Anti-correlation (Automated run)\n',
    f"MC params: seed=42, n=1000\n",
    '## Candidates and quick 150p edges\n'
]
for r in SUMMARY:
    md_lines.append(f"- {r['strategy_name']} | game={r['lottery_type']} | edge_150={r['edge_vs_random']:+.4f}\n")

md_lines.append('\n## Monte Carlo summaries (mean ± std)\n')
for k, v in MC_SUMMARIES.items():
    md_lines.append(f"- {k}: mean={v['edge_mean']:+.4f}, std={v['edge_std']:.4f}, p5={v['edge_p5']:+.4f}, p95={v['edge_p95']:+.4f}\n")

with open(os.path.join(OUT_DIR, 'completed_markdown.md'), 'w', encoding='utf-8') as f:
    f.writelines(md_lines)

print('Done. Outputs written to outputs/*.')
