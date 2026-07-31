#!/usr/bin/env python3
"""
Big Lotto Comprehensive Strategy Backtest
==========================================
Migrates 8 Power Lotto strategies to Big Lotto (1-49 pick 6) and runs
3-tier backtests (150/500/1500 periods) with strict anti-leakage protocol.

Usage:
    python3 tools/backtest_biglotto_comprehensive.py
    python3 tools/backtest_biglotto_comprehensive.py --strategies 1,2,3
    python3 tools/backtest_biglotto_comprehensive.py --windows 150,500

Mandatory Rules:
    1. N-bet baseline: P(N) = 1 - (1 - P_single)^N
    2. Strict temporal isolation: history = draws[:idx]
    3. Fixed seed: 42
    4. Big Lotto P_single(M3+) = 1.86%
"""
import os
import sys
import time
import json
import numpy as np
from collections import Counter
from itertools import combinations

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))
sys.path.insert(0, os.path.join(project_root, 'tools'))

from lottery_api.database import DatabaseManager

# ============================================================
# Constants
# ============================================================
MAX_NUM = 49
PICK = 6
SEED = 42

# Big Lotto baselines: P(N) = 1 - (1 - 0.0186)^N
BASELINES = {
    1: 0.0186,
    2: 0.0369,
    3: 0.0549,
    4: 0.0725,
    7: 0.1234,
}

WINDOWS = [150, 500, 1500]
MIN_HISTORY_BUFFER = 150  # Minimum prior draws before test period


# ============================================================
# Strategy #1: Fourier Rhythm 2-bet (migrated from Power Lotto)
# ============================================================
def strat_fourier_rhythm(history, num_bets=2):
    """FFT period detection + gap-to-period scoring. Deterministic."""
    from scipy.fft import fft, fftfreq

    window = min(500, len(history))
    h_slice = history[-window:]
    w = len(h_slice)

    bitstreams = {i: np.zeros(w) for i in range(1, MAX_NUM + 1)}
    for idx, d in enumerate(h_slice):
        for n in d['numbers']:
            if 1 <= n <= MAX_NUM:
                bitstreams[n][idx] = 1

    scores = np.zeros(MAX_NUM + 1)
    for n in range(1, MAX_NUM + 1):
        bh = bitstreams[n]
        if bh.sum() < 2:
            continue
        yf = fft(bh - np.mean(bh))
        xf = fftfreq(w, 1)
        idx_pos = np.where(xf > 0)
        if len(idx_pos[0]) == 0:
            continue
        pos_xf = xf[idx_pos]
        pos_yf = np.abs(yf[idx_pos])
        if len(pos_yf) == 0:
            continue
        peak_idx = np.argmax(pos_yf)
        freq_val = pos_xf[peak_idx]
        if freq_val == 0:
            continue
        period = 1 / freq_val
        if 2 < period < w / 2:
            last_hits = np.where(bh == 1)[0]
            if len(last_hits) > 0:
                gap = (w - 1) - last_hits[-1]
                dist_to_peak = abs(gap - period)
                scores[n] = 1.0 / (dist_to_peak + 1.0)

    all_idx = np.arange(1, MAX_NUM + 1)
    sorted_idx = all_idx[np.argsort(scores[1:])[::-1]]

    bets = []
    for i in range(num_bets):
        start = i * PICK
        end = (i + 1) * PICK
        bets.append(sorted(sorted_idx[start:end].tolist()))
    return bets


# ============================================================
# Strategy #2: Cold Complement 2-bet (migrated from Power Lotto)
# ============================================================
def strat_cold_complement(history, num_bets=2):
    """Top 12 coldest numbers from last 100 draws, split into 2 bets. Deterministic."""
    window = min(100, len(history))
    recent = history[-window:]
    all_nums = [n for d in recent for n in d['numbers']]
    freq = Counter(all_nums)

    sorted_nums = sorted(range(1, MAX_NUM + 1), key=lambda x: freq.get(x, 0))
    bets = []
    for i in range(num_bets):
        bets.append(sorted(sorted_nums[i * PICK:(i + 1) * PICK]))
    return bets


# ============================================================
# Strategy #3: Triple Strike 3-bet (existing Big Lotto version)
# ============================================================
def strat_triple_strike(history, num_bets=3):
    """Fourier + Cold + Tail Balance, 3 orthogonal bets. Deterministic."""
    from predict_biglotto_triple_strike import generate_triple_strike
    return generate_triple_strike(history)


# ============================================================
# Strategy #4: Markov 1-bet (generic, uses max_num=49)
# ============================================================
def strat_markov_single(history, num_bets=1):
    """1st-order Markov transition from last draw. Deterministic."""
    window = min(100, len(history))
    recent = history[-window:]

    transitions = Counter()
    for i in range(len(recent) - 1):
        curr_set = set(recent[i]['numbers'])
        next_nums = recent[i + 1]['numbers']
        for c in curr_set:
            for n in next_nums:
                transitions[(c, n)] += 1

    if not recent:
        return [sorted(list(range(1, PICK + 1)))]

    last_draw = history[-1]['numbers']
    next_scores = Counter()
    for c in last_draw:
        for n in range(1, MAX_NUM + 1):
            next_scores[n] += transitions.get((c, n), 0)

    sorted_nums = sorted(range(1, MAX_NUM + 1), key=lambda x: next_scores[x], reverse=True)
    bets = []
    for i in range(num_bets):
        bets.append(sorted(sorted_nums[i * PICK:(i + 1) * PICK]))
    return bets


# ============================================================
# Strategy #5: Deviation Complement 2-bet (existing Big Lotto)
# ============================================================
def strat_deviation_complement(history, num_bets=2):
    """Hot/Cold frequency orthogonal decomposition. Deterministic."""
    from predict_biglotto_deviation_2bet import deviation_complement_2bet
    return deviation_complement_2bet(history, window=50)


# ============================================================
# Strategy #6: Echo-Aware Mixed 3-bet (existing Big Lotto)
# ============================================================
def strat_echo_aware_mixed(history, num_bets=3):
    """Echo+Temperature 2 bets + Echo+Warm 1 bet. Deterministic."""
    from predict_biglotto_echo_3bet import echo_aware_mixed_3bet
    return echo_aware_mixed_3bet(history, window=50, echo_weight=0.25)


# ============================================================
# Strategy #7: Fourier30+Markov30 2-bet (MIGRATED from Power Lotto)
# ============================================================
def _bet1_fourier30_biglotto(history):
    """Weighted frequency with linear increasing weight over 30 periods."""
    recent = history[-30:] if len(history) >= 30 else history
    weighted_freq = Counter()
    n = len(recent)
    for i, h in enumerate(recent):
        weight = 1 + 2 * (i / max(n, 1))
        for num in h['numbers']:
            weighted_freq[num] += weight
    return sorted([num for num, _ in weighted_freq.most_common(PICK)])


def _bet2_markov30_biglotto(history):
    """Markov transition from last 30 draws."""
    recent = history[-30:] if len(history) >= 30 else history

    transitions = Counter()
    for i in range(len(recent) - 1):
        prev = set(recent[i]['numbers'])
        curr = recent[i + 1]['numbers']
        for p in prev:
            for c in curr:
                transitions[(p, c)] += 1

    if not recent:
        return sorted(list(range(1, PICK + 1)))

    last = recent[-1]['numbers']
    scores = Counter()
    for num in last:
        for (p, c), count in transitions.items():
            if p == num:
                scores[c] += count

    result = [n for n, _ in scores.most_common(PICK)]

    # Fill if fewer than 6
    if len(result) < PICK:
        all_nums = [num for h in recent for num in h['numbers']]
        freq = Counter(all_nums)
        for n, _ in freq.most_common():
            if n not in result and len(result) < PICK:
                result.append(n)

    return sorted(result[:PICK])


def _get_zone_biglotto(num):
    """5-zone division for Big Lotto (1-49)."""
    if num <= 10:
        return 1
    elif num <= 20:
        return 2
    elif num <= 30:
        return 3
    elif num <= 40:
        return 4
    else:
        return 5


def _diversify_biglotto(bet1, bet2, history, max_overlap=3):
    """Ensure overlap <= max_overlap, fill with cold numbers and zone balance."""
    overlap = set(bet1) & set(bet2)
    if len(overlap) <= max_overlap:
        return bet1, bet2

    recent = history[-50:] if len(history) >= 50 else history
    last_seen = {i: len(recent) for i in range(1, MAX_NUM + 1)}
    for idx, h in enumerate(recent):
        for num in h['numbers']:
            gap = len(recent) - 1 - idx
            if gap < last_seen[num]:
                last_seen[num] = gap

    new_bet2 = [n for n in bet2 if n not in overlap][:max_overlap]
    cold = sorted(last_seen.items(), key=lambda x: -x[1])
    zones_used = Counter(_get_zone_biglotto(n) for n in new_bet2)

    for n, gap in cold:
        if n not in bet1 and n not in new_bet2 and len(new_bet2) < PICK:
            z = _get_zone_biglotto(n)
            if zones_used[z] < 2:
                new_bet2.append(n)
                zones_used[z] += 1

    for n, gap in cold:
        if n not in bet1 and n not in new_bet2 and len(new_bet2) < PICK:
            new_bet2.append(n)

    return bet1, sorted(new_bet2[:PICK])


def strat_fourier30_markov30(history, num_bets=2):
    """Fourier30 + Markov30 hedging, migrated to Big Lotto. Deterministic."""
    bet1 = _bet1_fourier30_biglotto(history)
    bet2 = _bet2_markov30_biglotto(history)
    bet1, bet2 = _diversify_biglotto(bet1, bet2, history, max_overlap=3)
    return [bet1, bet2]


# ============================================================
# Strategy #8: Cluster Pivot 4-bet (generic, uses max_num=49)
# ============================================================
def strat_cluster_pivot(history, num_bets=4):
    """Co-occurrence anchor expansion. Deterministic."""
    window = min(150, len(history))
    recent = history[-window:]

    cooccur = Counter()
    for d in recent:
        nums = sorted(d['numbers'])
        for pair in combinations(nums, 2):
            cooccur[pair] += 1

    num_scores = Counter()
    for (a, b), count in cooccur.items():
        num_scores[a] += count
        num_scores[b] += count

    centers = [num for num, _ in num_scores.most_common(num_bets + 2)]

    bets = []
    exclude = set()
    for center in centers:
        if len(bets) >= num_bets:
            break
        candidates = Counter()
        for (a, b), count in cooccur.items():
            if a == center and b not in exclude:
                candidates[b] += count
            elif b == center and a not in exclude:
                candidates[a] += count

        bet = [center]
        for n, _ in candidates.most_common(PICK - 1):
            bet.append(n)

        if len(bet) < PICK:
            for n in range(1, MAX_NUM + 1):
                if n not in bet and n not in exclude:
                    bet.append(n)
                if len(bet) == PICK:
                    break

        bets.append(sorted(bet[:PICK]))
        exclude.update(bet[:2])

    return bets


# ============================================================
# Strategy registration
# ============================================================
STRATEGIES = [
    {
        'id': 1,
        'name': 'Fourier Rhythm',
        'origin': 'Power Lotto 2-bet (Edge +1.91%)',
        'n_bets': 2,
        'func': strat_fourier_rhythm,
        'deterministic': True,
    },
    {
        'id': 2,
        'name': 'Cold Complement',
        'origin': 'Power Lotto 2-bet (Edge +1.41%)',
        'n_bets': 2,
        'func': strat_cold_complement,
        'deterministic': True,
    },
    {
        'id': 3,
        'name': 'Triple Strike',
        'origin': 'Power Lotto 3-bet (Edge +0.43%)',
        'n_bets': 3,
        'func': strat_triple_strike,
        'deterministic': True,
    },
    {
        'id': 4,
        'name': 'Markov (Single)',
        'origin': 'Power Lotto 1-bet (Edge +0.13%)',
        'n_bets': 1,
        'func': strat_markov_single,
        'deterministic': True,
    },
    {
        'id': 5,
        'name': 'Deviation Complement',
        'origin': 'Big Lotto 2-bet (Edge +0.91%)',
        'n_bets': 2,
        'func': strat_deviation_complement,
        'deterministic': True,
    },
    {
        'id': 6,
        'name': 'Echo-Aware Mixed',
        'origin': 'Big Lotto 3-bet (Edge +1.01%)',
        'n_bets': 3,
        'func': strat_echo_aware_mixed,
        'deterministic': True,
    },
    {
        'id': 7,
        'name': 'Fourier30+Markov30',
        'origin': 'Power Lotto 2-bet (Edge +0.91%)',
        'n_bets': 2,
        'func': strat_fourier30_markov30,
        'deterministic': True,
    },
    {
        'id': 8,
        'name': 'Cluster Pivot',
        'origin': 'Big Lotto 4-bet (Edge +1.42%)',
        'n_bets': 4,
        'func': strat_cluster_pivot,
        'deterministic': True,
    },
]


# ============================================================
# Backtest engine
# ============================================================
def run_backtest(draws, strategy, n_periods):
    """
    Run backtest with strict temporal isolation.

    Returns:
        dict with hits_m3, hits_m4, hits_m5, hits_m6, total, win_rate, edge
    """
    np.random.seed(SEED)

    func = strategy['func']
    n_bets = strategy['n_bets']
    baseline = BASELINES.get(n_bets, BASELINES[1])

    start_idx = len(draws) - n_periods
    if start_idx < MIN_HISTORY_BUFFER:
        actual_periods = len(draws) - MIN_HISTORY_BUFFER
        print(f"  WARNING: Capped to {actual_periods} periods (insufficient history)")
        start_idx = MIN_HISTORY_BUFFER

    hits = {3: 0, 4: 0, 5: 0, 6: 0}
    total = 0

    for i in range(start_idx, len(draws)):
        target = set(draws[i]['numbers'])
        history = draws[:i]  # STRICT ISOLATION

        try:
            bets = func(history, num_bets=n_bets)
        except Exception as e:
            # Strategy failed for this draw, count as miss
            total += 1
            continue

        best_match = 0
        for b in bets:
            match_count = len(set(b) & target)
            if match_count > best_match:
                best_match = match_count

        if best_match >= 3:
            hits[min(best_match, 6)] += 1
        total += 1

    m3_plus = sum(hits.values())
    win_rate = m3_plus / total if total > 0 else 0
    edge = win_rate - baseline

    return {
        'total': total,
        'hits_m3': hits[3],
        'hits_m4': hits[4],
        'hits_m5': hits[5],
        'hits_m6': hits[6],
        'm3_plus': m3_plus,
        'win_rate': win_rate,
        'baseline': baseline,
        'edge': edge,
    }


# ============================================================
# Report generation
# ============================================================
def print_strategy_report(strategy, results):
    """Print per-strategy report in mandatory format."""
    print()
    print(f"策略名稱: {strategy['name']}")
    print(f"移植自: {strategy['origin']}")
    print(f"大樂透注數: {strategy['n_bets']}注")
    print(f"隨機種子: {SEED}")
    print()

    print("┌──────────┬───────────┬───────────┬─────────┬──────────┐")
    print("│ 回測窗口  │ 實測 M3+  │ 隨機基準   │  Edge   │   判定   │")
    print("├──────────┼───────────┼───────────┼─────────┼──────────┤")

    edges = {}
    for w in WINDOWS:
        r = results.get(w)
        if r is None:
            continue
        wr = r['win_rate'] * 100
        bl = r['baseline'] * 100
        ed = r['edge'] * 100
        verdict = "PASS" if ed > 0 else "FAIL"
        icon = "\u2705" if ed > 0 else "\u274c"
        print(f"│ {w:>4} 期   │  {wr:5.2f}%   │   {bl:5.2f}%   │ {ed:+5.2f}%  │ {icon:<9}│")
        edges[w] = ed

    print("└──────────┴───────────┴───────────┴─────────┴──────────┘")

    # Decay analysis
    if 150 in edges and 1500 in edges:
        decay = edges[150] - edges[1500]
        if edges[150] <= 0 and edges[1500] > 0:
            stability = "LATE_BLOOMER"
        elif edges[150] > 0 and edges[1500] <= 0:
            stability = "SHORT_MOMENTUM"
        elif edges[1500] <= 0:
            stability = "INEFFECTIVE"
        elif abs(decay) < 0.5 and edges[1500] > 0:
            stability = "ROBUST"
        else:
            stability = "MODERATE_DECAY"

        print()
        print(f"衰減分析:")
        print(f"- 150p → 1500p 衰減率: {decay:+.2f}%")
        print(f"- 穩定性分類: {stability}")

        # Match distribution for 1500p
        r1500 = results.get(1500)
        if r1500:
            print(f"- 1500p 明細: M3={r1500['hits_m3']}, M4={r1500['hits_m4']}, "
                  f"M5={r1500['hits_m5']}, M6={r1500['hits_m6']}")

    # Conclusion
    edge_1500 = edges.get(1500, 0)
    if edge_1500 > 0.5:
        conclusion = "適用"
    elif edge_1500 > 0:
        conclusion = "需進一步驗證"
    else:
        conclusion = "不適用"
    print(f"\n最終結論: {conclusion}")


def print_summary(all_results):
    """Print final summary tables."""
    print()
    print("=" * 95)
    print("  大樂透策略有效性排名 (按 1500期 Edge 排序)")
    print("=" * 95)
    print(f"{'排名':<4} {'策略':<22} {'注數':<4} {'150p Edge':<10} {'500p Edge':<10} "
          f"{'1500p Edge':<11} {'穩定性':<16} {'結論':<6}")
    print("-" * 95)

    # Collect & sort by 1500p edge (only tested strategies)
    ranking = []
    tested_ids = set(all_results.keys())
    for s in STRATEGIES:
        if s['id'] not in tested_ids:
            continue
        results = all_results.get(s['id'], {})
        e150 = results.get(150, {}).get('edge', 0) * 100
        e500 = results.get(500, {}).get('edge', 0) * 100
        e1500 = results.get(1500, {}).get('edge', 0) * 100

        # Stability
        if e150 != 0 and e1500 != 0:
            decay = e150 - e1500
            if e150 <= 0 and e1500 > 0:
                stability = "LATE_BLOOMER"
            elif e150 > 0 and e1500 <= 0:
                stability = "SHORT_MOMENTUM"
            elif e1500 <= 0:
                stability = "INEFFECTIVE"
            elif abs(decay) < 0.5 and e1500 > 0:
                stability = "ROBUST"
            else:
                stability = "MODERATE_DECAY"
        else:
            stability = "N/A"

        icon = "\u2705" if e1500 > 0 else "\u274c"
        ranking.append((s, e150, e500, e1500, stability, icon))

    ranking.sort(key=lambda x: x[3], reverse=True)

    for rank, (s, e150, e500, e1500, stability, icon) in enumerate(ranking, 1):
        print(f" {rank:<3} {s['name']:<22} {s['n_bets']:<4} {e150:>+6.2f}%    "
              f"{e500:>+6.2f}%    {e1500:>+6.2f}%     {stability:<16} {icon}")

    print("=" * 95)

    # Non-viable strategies
    print()
    print("不適用策略清單:")
    print("-" * 70)
    failed = [x for x in ranking if x[3] <= 0]
    if failed:
        for _, (s, e150, e500, e1500, stability, _) in enumerate(failed):
            reasons = []
            if stability == "SHORT_MOMENTUM":
                reasons.append("短期有效但長線衰減至負值")
            if stability == "INEFFECTIVE":
                reasons.append("全時段均無效")
            if s['n_bets'] >= 3 and e1500 < -1:
                reasons.append("多注覆蓋不足以彌補號碼空間增大")
            if not reasons:
                reasons.append("Edge 不顯著")
            print(f"  {s['name']} ({s['n_bets']}注): 1500p Edge={e1500:+.2f}%, 原因: {', '.join(reasons)}")
    else:
        print("  (無)")

    # Recommended configuration
    print()
    print("推薦配置:")
    print("-" * 70)
    best_by_bets = {}
    for _, (s, e150, e500, e1500, stability, icon) in enumerate(ranking):
        nb = s['n_bets']
        if nb not in best_by_bets and e1500 > 0:
            best_by_bets[nb] = (s, e1500, stability)

    for nb in sorted(best_by_bets.keys()):
        s, edge, stab = best_by_bets[nb]
        print(f"  {nb}注最佳: {s['name']} (1500p Edge={edge:+.2f}%, 穩定性: {stab})")

    if not best_by_bets:
        print("  (無任何策略在1500期具有正Edge)")
    print()


# ============================================================
# Main
# ============================================================
def main():
    import argparse
    parser = argparse.ArgumentParser(description='Big Lotto Comprehensive Strategy Backtest')
    parser.add_argument('--strategies', type=str, default=None,
                        help='Comma-separated strategy IDs to test (default: all)')
    parser.add_argument('--windows', type=str, default=None,
                        help='Comma-separated test windows (default: 150,500,1500)')
    args = parser.parse_args()

    # Parse strategy filter
    if args.strategies:
        selected_ids = set(int(x) for x in args.strategies.split(','))
        strategies = [s for s in STRATEGIES if s['id'] in selected_ids]
    else:
        strategies = STRATEGIES

    # Parse windows
    if args.windows:
        windows = [int(x) for x in args.windows.split(',')]
    else:
        windows = WINDOWS

    # Load data
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)
    draws = db.get_all_draws('BIG_LOTTO')
    draws = sorted(draws, key=lambda x: (x['date'], x['draw']))

    print("=" * 80)
    print("  Big Lotto Comprehensive Strategy Backtest")
    print("=" * 80)
    print(f"  Database: {len(draws)} draws")
    print(f"  Date range: {draws[0]['date']} ~ {draws[-1]['date']}")
    print(f"  Test windows: {windows}")
    print(f"  Strategies: {len(strategies)}")
    print(f"  Seed: {SEED}")
    print(f"  Total backtests: {len(strategies) * len(windows)}")
    print()

    # Baseline table
    print("  Baselines (M3+ random):")
    for nb in sorted(BASELINES.keys()):
        if nb <= 4:
            print(f"    {nb}-bet: {BASELINES[nb]*100:.2f}%")
    print("=" * 80)

    # Run all backtests
    all_results = {}
    total_tests = len(strategies) * len(windows)
    test_num = 0

    for s in strategies:
        all_results[s['id']] = {}
        for w in windows:
            test_num += 1
            print(f"\n[{test_num}/{total_tests}] #{s['id']} {s['name']} ({s['n_bets']}注) @ {w} periods...")

            t0 = time.time()
            result = run_backtest(draws, s, w)
            elapsed = time.time() - t0

            all_results[s['id']][w] = result
            wr = result['win_rate'] * 100
            bl = result['baseline'] * 100
            ed = result['edge'] * 100
            icon = "\u2705" if ed > 0 else "\u274c"

            print(f"  M3+: {result['m3_plus']}/{result['total']} = {wr:.2f}% "
                  f"(baseline {bl:.2f}%, edge {ed:+.2f}%) {icon}  [{elapsed:.1f}s]")

    # Print per-strategy reports
    print()
    print("=" * 80)
    print("  DETAILED STRATEGY REPORTS")
    print("=" * 80)

    for s in strategies:
        results = all_results.get(s['id'], {})
        print_strategy_report(s, results)
        print("-" * 60)

    # Print summary
    print_summary(all_results)


if __name__ == '__main__':
    main()
