#!/usr/bin/env python3
"""Deep research runner for Coverage Optimization, Structure Filtering, Frequency Reversion

Produces JSON reports under tools/ and prints concise summaries.
"""
import json
import random
import numpy as np
from collections import Counter
import os
import sys
# ensure project root and lottery_api on sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))
from lottery_api.utils.benchmark_framework import StrategyBenchmark

# Helper: extract numbers from history (list of dicts with 'numbers')
def flatten_hist_numbers(history):
    nums = []
    for d in history:
        n = d.get('numbers')
        if isinstance(n, str):
            n = eval(n)
        nums.append(list(n))
    return nums

# Focus 1: Coverage Optimization - concentrated pool in cold regime
def cov_opt_concentrated(history, rules, coverage_factor=0.8, num_bets=4):
    max_num = rules.get('maxNumber', 49)
    pick = rules.get('pickCount', 6)
    window = 500
    recent = history[-window:] if len(history) >= window else history
    counts = Counter()
    for d in recent:
        nums = d.get('numbers')
        if isinstance(nums, str):
            nums = eval(nums)
        counts.update(nums)
    # select top-k pool
    k = max(6, int(max_num * coverage_factor))
    pool = [n for n,_ in counts.most_common(k)]
    # if pool too small fill
    if len(pool) < k:
        pool = list(range(1, max_num+1))
    bets = []
    for _ in range(num_bets):
        bets.append(sorted(random.sample(pool, pick)))
    return bets

# Focus 2: Structure Filtering - enforce span and consecutive limits
def struct_filter_strategy(history, rules, num_bets=4):
    max_num = rules.get('maxNumber', 49)
    pick = rules.get('pickCount', 6)
    # compute historical span/distribution
    spans = []
    consec_rates = []
    for d in history[-1000:]:
        nums = d.get('numbers')
        if isinstance(nums, str):
            nums = eval(nums)
        s = max(nums) - min(nums)
        spans.append(s)
        # consecutive count
        consec = 0
        last = None
        for x in sorted(nums):
            if last is not None and x == last + 1:
                consec += 1
            last = x
        consec_rates.append(consec)
    span_thresh = np.percentile(spans, 70) if spans else max_num
    consec_thresh = int(np.percentile(consec_rates, 70)) if consec_rates else 1
    bets = []
    attempts = 0
    while len(bets) < num_bets and attempts < 2000:
        attempts += 1
        cand = sorted(random.sample(range(1, max_num+1), pick))
        s = max(cand) - min(cand)
        consec = 0
        last = None
        for x in cand:
            if last is not None and x == last + 1:
                consec += 1
            last = x
        # simple odd-even balance filter: allow 2-4 odd
        odd = sum(1 for x in cand if x % 2 == 1)
        if s <= span_thresh and consec <= consec_thresh and 2 <= odd <= 4:
            bets.append(cand)
    # fallback
    while len(bets) < num_bets:
        bets.append(sorted(random.sample(range(1, max_num+1), pick)))
    return bets

# Focus 3: Frequency Reversion - favour low short-term freq numbers
def freq_reversion_strategy(history, rules, num_bets=4):
    max_num = rules.get('maxNumber', 49)
    pick = rules.get('pickCount', 6)
    long_window = 1000
    short_window = 50
    long_hist = history[-long_window:] if len(history) >= long_window else history
    short_hist = history[-short_window:] if len(history) >= short_window else history
    long_counts = Counter()
    short_counts = Counter()
    for d in long_hist:
        nums = d.get('numbers')
        if isinstance(nums, str):
            nums = eval(nums)
        long_counts.update(nums)
    for d in short_hist:
        nums = d.get('numbers')
        if isinstance(nums, str):
            nums = eval(nums)
        short_counts.update(nums)
    # compute ratio short/long (avoid div by zero)
    ratios = {}
    for n in range(1, max_num+1):
        l = long_counts.get(n, 0) + 0.1
        s = short_counts.get(n, 0)
        ratios[n] = s / l
    # choose numbers with smallest ratios (cold numbers)
    sorted_by_ratio = sorted(ratios.items(), key=lambda x: x[1])
    cold_pool = [n for n,_ in sorted_by_ratio[:max(12, int(max_num*0.25))]]
    bets = []
    for _ in range(num_bets):
        # ensure some cold numbers present
        bet = set(random.sample(cold_pool, min(3, len(cold_pool))))
        while len(bet) < pick:
            bet.add(random.randint(1, max_num))
        bets.append(sorted(bet))
    return bets

# Monte Carlo runner (seed=42, n=1000) - computes edge distribution using StrategyBenchmark internals
def monte_carlo_edge(strategy_fn, lottery_type, num_bets=4, test_periods=150, trials=1000, seed=42):
    bench = StrategyBenchmark(lottery_type=lottery_type, test_periods=test_periods)
    edges = []
    rng = np.random.RandomState(seed)
    for i in range(trials):
        s = seed + i
        random.seed(s)
        np.random.seed(s)
        # run single-seed backtest
        win_rate, _, score = bench._run_backtest(strategy_fn, num_bets)
        random_baseline = bench._get_random_baseline(num_bets, [s])
        edge = win_rate - random_baseline
        edges.append(edge)
    arr = np.array(edges)
    return {
        'mean': float(arr.mean()),
        'std': float(arr.std()),
        'p5': float(np.percentile(arr, 5)),
        'p95': float(np.percentile(arr, 95)),
        'trials': trials
    }

# Main runner
if __name__ == '__main__':
    out = {}
    # Target game: POWER_LOTTO (triggered by task)
    for name, fn in [
        ('cov_opt_concentrated', cov_opt_concentrated),
        ('struct_filter_strategy', struct_filter_strategy),
        ('freq_reversion_strategy', freq_reversion_strategy)
    ]:
        print(f"Running quick benchmark for {name} on POWER_LOTTO (150)")
        bench = StrategyBenchmark(lottery_type='POWER_LOTTO', test_periods=150)
        res = bench.evaluate(lambda h, r, fn=fn: fn(h, r, num_bets=3) if 'cov' in name or 'freq' in name else fn(h, r, num_bets=3), strategy_name=name, num_bets=3)
        bench.print_report(res)
        out[name] = res.to_dict()
        # run extended windows 500 and 1500 (Phase 3 requirement)
        for tp in [500, 1500]:
            try:
                bench2 = StrategyBenchmark(lottery_type='POWER_LOTTO', test_periods=tp)
                res2 = bench2.evaluate(lambda h, r, fn=fn: fn(h, r, num_bets=3), strategy_name=f"{name}_{tp}", num_bets=3)
                out[f"{name}_{tp}"] = res2.to_dict()
            except Exception as e:
                out[f"{name}_{tp}"] = {'error': str(e)}
    # Monte Carlo for each
    mc = {}
    for name, fn in [('cov_opt_concentrated', cov_opt_concentrated), ('struct_filter_strategy', struct_filter_strategy), ('freq_reversion_strategy', freq_reversion_strategy)]:
        print(f"Running Monte Carlo for {name} (n=1000, seed=42)")
        try:
            mc[name] = monte_carlo_edge(lambda h, r, fn=fn: fn(h, r, num_bets=3), lottery_type='POWER_LOTTO', num_bets=3, test_periods=150, trials=1000, seed=42)
        except Exception as e:
            mc[name] = {'error': str(e)}
    # save outputs
    # safe JSON dump: convert numpy types by serializing with default=str
    with open('tools/deep_research_results_powerlotto.json', 'w', encoding='utf-8') as f:
        f.write(json.dumps({'benchmarks': out, 'monte_carlo': mc}, indent=2, ensure_ascii=False, default=str))
    print('Saved tools/deep_research_results_powerlotto.json')
