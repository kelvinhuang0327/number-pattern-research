import os, sys, json, random
from collections import Counter
import numpy as np
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.utils.benchmark_framework import StrategyBenchmark

# Helpers

def freq_ratios(history, rules, long_w=1000, short_w=50):
    pick = rules.get('pickCount', 6)
    maxN = rules.get('maxNumber', 49)
    long_hist = history[-long_w:] if len(history) >= long_w else history
    short_hist = history[-short_w:] if len(history) >= short_w else history
    cnt_long = Counter()
    cnt_short = Counter()
    for d in long_hist:
        for n in d['numbers']:
            cnt_long[n] += 1
    for d in short_hist:
        for n in d['numbers']:
            cnt_short[n] += 1
    ratios = {}
    for n in range(1, maxN+1):
        ratios[n] = (cnt_short.get(n,0) + 1) / (cnt_long.get(n,0) + 1)
    return ratios

# Strategy implementations

def freq_rev_strategy_factory(core_size=3, long_w=1000, short_w=50):
    def strategy(history, rules):
        pick = rules.get('pickCount', 6)
        maxN = rules.get('maxNumber', 49)
        if len(history) < max(short_w, 100):
            # fallback random
            return [sorted(random.sample(range(1, maxN+1), pick)) for _ in range(3)]
        ratios = freq_ratios(history, rules, long_w, short_w)
        cold_sorted = sorted(ratios.items(), key=lambda x: x[1])
        core = [n for n,_ in cold_sorted[:core_size]]
        fillers = [n for n in range(1, maxN+1) if n not in core]
        bets = []
        for i in range(3):
            need = pick - len(core)
            start = (i * need) % len(fillers)
            sel = fillers[start:start+need]
            if len(sel) < need:
                sel += fillers[:(need - len(sel))]
            bet = sorted(core + sel)
            bets.append(bet)
        return bets
    return strategy


def cov_opt_strategy_factory(core_size=2, num_bets=2, long_w=1000, short_w=50):
    def strategy(history, rules):
        pick = rules.get('pickCount', 6)
        maxN = rules.get('maxNumber', 49)
        if len(history) < max(short_w, 100):
            return [sorted(random.sample(range(1, maxN+1), pick)) for _ in range(num_bets)]
        ratios = freq_ratios(history, rules, long_w, short_w)
        # choose two cold numbers and produce few concentrated bets
        cold_sorted = sorted(ratios.items(), key=lambda x: x[1])
        core = [n for n,_ in cold_sorted[:core_size]]
        fillers = [n for n in range(1, maxN+1) if n not in core]
        bets = []
        for i in range(num_bets):
            need = pick - len(core)
            # choose top fillers by long frequency (to diversify coverage)
            fillers_sorted = sorted(fillers, key=lambda x: -sum(1 for d in history[-1000:] if x in d['numbers']))
            sel = fillers_sorted[i: i+need]
            if len(sel) < need:
                sel += fillers_sorted[:(need - len(sel))]
            bets.append(sorted(core + sel))
        return bets
    return strategy


def hybrid_big_strategy_factory(core_size=3, num_bets=4, long_w=1000, short_w=50):
    def strategy(history, rules):
        pick = rules.get('pickCount', 6)
        maxN = rules.get('maxNumber', 49)
        if len(history) < max(short_w, 100):
            return [sorted(random.sample(range(1, maxN+1), pick)) for _ in range(num_bets)]
        ratios = freq_ratios(history, rules, long_w, short_w)
        # mix cold core + some high-frequency fillers to balance
        cold_sorted = sorted(ratios.items(), key=lambda x: x[1])
        core = [n for n,_ in cold_sorted[:core_size]]
        high_sorted = sorted(ratios.items(), key=lambda x: -x[1])
        high_fillers = [n for n,_ in high_sorted if n not in core]
        bets = []
        for i in range(num_bets):
            need = pick - len(core)
            sel = high_fillers[i: i+need]
            if len(sel) < need:
                sel += high_fillers[:(need - len(sel))]
            bets.append(sorted(core + sel))
        return bets
    return strategy

# Candidate definitions
candidates = [
    {
        'strategy_name': 'freq_rev_daily_cold_3bet',
        'game': 'DAILY_539',
        'factory': lambda: freq_rev_strategy_factory(core_size=3),
        'num_bets': 3
    },
    {
        'strategy_name': 'cov_opt_power_partial_2bet',
        'game': 'POWER_LOTTO',
        'factory': lambda: cov_opt_strategy_factory(core_size=2, num_bets=2),
        'num_bets': 2
    },
    {
        'strategy_name': 'hybrid_big_freq_cov_4bet',
        'game': 'BIG_LOTTO',
        'factory': lambda: hybrid_big_strategy_factory(core_size=3, num_bets=4),
        'num_bets': 4
    }
]

results_summary = []

for c in candidates:
    name = c['strategy_name']
    game = c['game']
    num_bets = c['num_bets']
    strategy_fn = c['factory']()
    print('\n' + '='*60)
    print(f"Running quick benchmark for {name} on {game} (150p, {num_bets} bets)")
    benchmark = StrategyBenchmark(lottery_type=game, test_periods=150)
    result = benchmark.evaluate(strategy_fn, strategy_name=name, num_bets=num_bets, use_multi_seed=False)
    benchmark.print_report(result)
    out = result.to_dict()
    out_path = os.path.join(project_root, 'outputs', f"benchmark_{name}_{game}_150.json")
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=2, default=lambda o: o.item() if hasattr(o, 'item') else (o.tolist() if hasattr(o, 'tolist') else str(o)))
    # Monte Carlo n=1000 seed=42
    mc_n = 1000
    mc_seed_start = 42
    mc_win_rates = []
    random_baseline = out['random_baseline']
    print(f"Starting Monte Carlo (n={mc_n}, seed=42..): this may take a bit...")
    for i in range(mc_n):
        s = mc_seed_start + i
        np.random.seed(s)
        random.seed(s)
        win_rate, match_dist, score = benchmark._run_backtest(strategy_fn, num_bets)
        mc_win_rates.append(win_rate)
    mc_mean = float(np.mean(mc_win_rates))
    mc_std = float(np.std(mc_win_rates))
    p5 = float(np.percentile(mc_win_rates, 5))
    p95 = float(np.percentile(mc_win_rates, 95))
    # Edge vs random baseline
    mc_edge = mc_mean - random_baseline
    # Statistical test using benchmark helper
    z, p_value, is_significant = benchmark._statistical_test(mc_mean, random_baseline, benchmark.test_periods)
    mc_status = 'PASS' if (is_significant and mc_edge > 0.01) else 'FAIL'
    mc_out = {
        'strategy_name': name,
        'game': game,
        'edge_150': out['edge_vs_random'],
        'mc_mean_win_rate': mc_mean,
        'mc_std_win_rate': mc_std,
        'mc_edge_vs_random': mc_edge,
        'mc_p_value': p_value,
        'mc_is_significant': is_significant,
        'mc_status': mc_status,
        'p5': p5,
        'p95': p95
    }
    with open(os.path.join(project_root, 'outputs', f"mc_{name}_{game}.json"), 'w', encoding='utf-8') as f:
        json.dump(mc_out, f, indent=2, default=lambda o: o.item() if hasattr(o, 'item') else (o.tolist() if hasattr(o, 'tolist') else str(o)))
    print(f"MC done for {name}: mean_edge={mc_edge:+.4f}, p={p_value:.4f}, status={mc_status}")
    results_summary.append((name, game, out, mc_out))

# Summarize for Strategy Output Table requirements
table_lines = []
for name, game, out, mc in results_summary:
    edge_150 = f"{out['edge_vs_random']:+.3f}"
    line = {
        'strategy_name': name,
        'game': game,
        'edge_150': edge_150,
        'edge_500': '—',
        'edge_1000': '—',
        'mc_status': mc['mc_status'],
        'vs_incumbent': None,
        'incumbent_name': None,
        'validation_tier': 'T1_MC_PASS' if mc['mc_status']=='PASS' else 'T0_IDEA',
        'promotion_blocker': 'NONE' if mc['mc_status']=='PASS' else 'negative or non-significant mc',
        'next_action': 'run_500w' if mc['mc_status']=='PASS' else 'reject'
    }
    table_lines.append(line)

# Save task outputs
task_result = {
    'results_summary_count': len(results_summary),
    'entries': [dict(name=n, game=g, edge150=e["edge_vs_random"] if isinstance(e, dict) else e) for n,g,e,_ in results_summary]
}
with open(os.path.join(project_root, 'outputs', 'task_result.json'), 'w', encoding='utf-8') as f:
    json.dump(task_result, f, indent=2)

print('\nAll candidates processed. Outputs saved to outputs/')
