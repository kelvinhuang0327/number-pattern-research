#!/usr/bin/env python3
"""
快速回測腳本 - 供 /backtest 命令使用
用法:
    python3 tools/quick_backtest.py 大樂透           # 默認3注 Triple Strike, 1000期
    python3 tools/quick_backtest.py 大樂透 2          # 2注 P0 回聲
    python3 tools/quick_backtest.py 威力彩            # 默認2注 Fourier Rhythm
    python3 tools/quick_backtest.py 威力彩 3          # 3注 Power Precision
    python3 tools/quick_backtest.py 大樂透 3 --three-tier   # 150/500/1500 三階驗證
    python3 tools/quick_backtest.py 威力彩 2 --periods 500  # 自訂期數
    python3 tools/quick_backtest.py all               # 全部彩票默認注數

策略對照 (2026-02-11):
  大樂透 2注: 偏差互補+回聲 P0 (Edge +1.21%)
  大樂透 3注: Triple Strike (Edge +0.98%, 1500期 STABLE)
  威力彩 2注: Fourier Rhythm (Edge +1.91%)
  威力彩 3注: Power Precision (Edge +2.49%, 1384期 STABLE)
"""
import sys
import os
import time
import random
import argparse
from collections import Counter

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))
sys.path.insert(0, os.path.join(project_root, 'tools'))

from database import DatabaseManager

# ============================================================
# Constants
# ============================================================
LOTTERY_MAP = {
    '大樂透': 'BIG_LOTTO', 'biglotto': 'BIG_LOTTO', 'big': 'BIG_LOTTO',
    '威力彩': 'POWER_LOTTO', 'power': 'POWER_LOTTO',
}

LOTTERY_NAMES = {
    'BIG_LOTTO': '大樂透',
    'POWER_LOTTO': '威力彩',
}

DEFAULT_BETS = {
    'BIG_LOTTO': 3,
    'POWER_LOTTO': 2,
}

# N注隨機基準: P(N) = 1 - (1 - P_single)^N
BASELINES = {
    'BIG_LOTTO':   {1: 1.86, 2: 3.69, 3: 5.49, 4: 7.25},
    'POWER_LOTTO': {1: 3.87, 2: 7.59, 3: 11.17, 4: 14.60},
}

STRATEGY_NAMES = {
    'BIG_LOTTO':   {2: '偏差互補+回聲 P0', 3: 'Triple Strike'},
    'POWER_LOTTO': {2: 'Fourier Rhythm', 3: 'Power Precision'},
}

SEED = 42
MIN_HISTORY = 50  # 最少訓練期數


# ============================================================
# Strategy functions (same as quick_predict.py)
# ============================================================

def _biglotto_p0_2bet(history, window=50, echo_boost=1.5):
    """大樂透 2注: 偏差互補+回聲 P0"""
    MAX_NUM, PICK = 49, 6
    recent = history[-window:] if len(history) > window else history
    expected = len(recent) * PICK / MAX_NUM

    freq = Counter()
    for d in recent:
        for n in d['numbers']:
            freq[n] += 1

    scores = {}
    for n in range(1, MAX_NUM + 1):
        scores[n] = freq.get(n, 0) - expected

    if len(history) >= 3:
        for n in history[-2]['numbers']:
            if n <= MAX_NUM:
                scores[n] += echo_boost

    hot = sorted([(n, s) for n, s in scores.items() if s > 1],
                 key=lambda x: x[1], reverse=True)
    cold = sorted([(n, abs(s)) for n, s in scores.items() if s < -1],
                  key=lambda x: x[1], reverse=True)

    bet1 = [n for n, _ in hot[:PICK]]
    used = set(bet1)
    if len(bet1) < PICK:
        mid = sorted(range(1, MAX_NUM + 1), key=lambda n: abs(scores[n]))
        for n in mid:
            if n not in used and len(bet1) < PICK:
                bet1.append(n); used.add(n)

    bet2 = []
    for n, _ in cold:
        if n not in used and len(bet2) < PICK:
            bet2.append(n); used.add(n)
    if len(bet2) < PICK:
        for n in range(1, MAX_NUM + 1):
            if n not in used and len(bet2) < PICK:
                bet2.append(n); used.add(n)

    return [sorted(bet1[:PICK]), sorted(bet2[:PICK])]


def _biglotto_triple_strike(history):
    """大樂透 3注: Triple Strike"""
    from predict_biglotto_triple_strike import generate_triple_strike
    return generate_triple_strike(history)


def _power_fourier_rhythm_2bet(history):
    """威力彩 2注: Fourier Rhythm"""
    from power_fourier_rhythm import fourier_rhythm_predict
    return fourier_rhythm_predict(history, n_bets=2, window=500)


def _power_precision_3bet(history):
    """威力彩 3注: Power Precision (Edge +2.49%, 1384期 STABLE)"""
    from predict_power_precision_3bet import generate_power_precision_3bet
    return generate_power_precision_3bet(history)


# ============================================================
# Strategy dispatch
# ============================================================

def get_predict_func(lottery_type, num_bets):
    """返回 (predict_func, strategy_name)，predict_func(history) → list of lists"""
    if lottery_type == 'BIG_LOTTO':
        if num_bets <= 2:
            return _biglotto_p0_2bet, '偏差互補+回聲 P0'
        else:
            return _biglotto_triple_strike, 'Triple Strike'
    elif lottery_type == 'POWER_LOTTO':
        if num_bets <= 2:
            return _power_fourier_rhythm_2bet, 'Fourier Rhythm'
        else:
            return _power_precision_3bet, 'Power Precision'
    else:
        raise ValueError(f'不支援回測: {lottery_type}')


# ============================================================
# Core backtest engine
# ============================================================

def run_backtest(lottery_type, num_bets, test_periods, seed=SEED):
    """執行滾動回測，返回結果 dict"""
    random.seed(seed)

    db = DatabaseManager(db_path=os.path.join(
        project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = db.get_all_draws(lottery_type=lottery_type)
    # DESC → ASC
    all_draws = sorted(all_draws, key=lambda x: (x['date'], x['draw']))

    predict_func, strategy_name = get_predict_func(lottery_type, num_bets)
    baseline = BASELINES[lottery_type][num_bets]

    available = len(all_draws)
    if test_periods > available - MIN_HISTORY:
        test_periods = available - MIN_HISTORY

    m3_plus = 0
    match_dist = Counter()
    total = 0
    errors = 0

    for i in range(test_periods):
        target_idx = available - test_periods + i
        if target_idx < MIN_HISTORY:
            continue

        target = all_draws[target_idx]
        hist = all_draws[:target_idx]
        actual = set(target['numbers'])

        try:
            random.seed(seed)  # reset per-iteration for reproducibility
            bets = predict_func(hist)
            bets = bets[:num_bets]

            # 確保 bets 是 list of lists
            if bets and isinstance(bets[0], dict):
                bets = [b['numbers'] for b in bets]

            best_match = 0
            for bet in bets:
                mc = len(set(bet) & actual)
                if mc > best_match:
                    best_match = mc

            match_dist[best_match] += 1
            if best_match >= 3:
                m3_plus += 1
            total += 1

        except Exception as e:
            errors += 1
            if errors <= 3:
                print(f'  [ERROR] idx={target_idx}: {e}')
            continue

    rate = m3_plus / total * 100 if total > 0 else 0
    edge = rate - baseline

    return {
        'lottery_type': lottery_type,
        'strategy': strategy_name,
        'num_bets': num_bets,
        'test_periods': total,
        'requested_periods': test_periods,
        'm3_plus': m3_plus,
        'rate': rate,
        'baseline': baseline,
        'edge': edge,
        'match_dist': dict(sorted(match_dist.items(), reverse=True)),
        'errors': errors,
        'seed': seed,
    }


# ============================================================
# Three-tier validation
# ============================================================

def run_three_tier(lottery_type, num_bets, seed=SEED):
    """150/500/1500 期三階驗證"""
    results = {}
    for periods in [150, 500, 1500]:
        results[periods] = run_backtest(lottery_type, num_bets, periods, seed)
    return results


# ============================================================
# Report printing
# ============================================================

def print_report(result):
    """印出單次回測結果"""
    lt = LOTTERY_NAMES.get(result['lottery_type'], result['lottery_type'])
    print(f"  策略: {result['strategy']} ({result['num_bets']}注)")
    print(f"  期數: {result['test_periods']} 期 (seed={result['seed']})")
    print()

    # 命中分布
    print('  命中分布:')
    for mc in sorted(result['match_dist'].keys(), reverse=True):
        cnt = result['match_dist'][mc]
        pct = cnt / result['test_periods'] * 100
        bar = '#' * min(cnt, 50)
        label = ' <-- M3+ 門檻' if mc == 3 else ''
        print(f'    Match-{mc}: {cnt:4d} ({pct:5.1f}%) {bar}{label}')

    print()
    print(f"  M3+ 命中: {result['m3_plus']}/{result['test_periods']} "
          f"({result['rate']:.2f}%)")
    print(f"  隨機基準: {result['baseline']:.2f}% ({result['num_bets']}注)")
    edge_symbol = '+' if result['edge'] >= 0 else ''
    verdict = 'PASS' if result['edge'] > 0 else 'FAIL'
    print(f"  Edge: {edge_symbol}{result['edge']:.2f}% [{verdict}]")

    if result['errors'] > 0:
        print(f"  錯誤: {result['errors']} 期跳過")


def print_three_tier_report(results, lottery_type, num_bets):
    """印出三階驗證報告"""
    lt = LOTTERY_NAMES.get(lottery_type, lottery_type)
    strategy = results[150]['strategy']

    print()
    print('=' * 65)
    print(f'  {lt} {num_bets}注 {strategy} — 三階驗證報告')
    print('=' * 65)
    print()
    print(f'  {"窗口":<8} {"M3+":<8} {"期數":<8} {"M3+率":<10} {"基準":<10} {"Edge":<10} {"判定":<12}')
    print('  ' + '-' * 60)

    edges = []
    for periods in [150, 500, 1500]:
        r = results[periods]
        edge_str = f"{r['edge']:+.2f}%"
        verdict = 'PASS' if r['edge'] > 0 else 'FAIL'
        print(f"  {periods:<8} {r['m3_plus']:<8} {r['test_periods']:<8} "
              f"{r['rate']:.2f}%{'':<5} {r['baseline']:.2f}%{'':<5} "
              f"{edge_str:<10} {verdict}")
        edges.append(r['edge'])

    # 趨勢分析
    e150, e500, e1500 = edges
    print()
    print('  趨勢分析:')
    if e1500 < 0:
        if e150 > 0 or e500 > 0:
            print('  [SHORT_MOMENTUM] 短期正 Edge 但長期失效 — 不應採納')
        else:
            print('  [INEFFECTIVE] 全段無效 — 不應採納')
    elif e150 < 0 and e1500 > 0:
        print('  [LATE_BLOOMER] 近期差但長期穩定 — 可備用')
    elif all(e > 0 for e in edges):
        print('  [STABLE] 三窗口全正 — 推薦採納')
    elif e1500 > 0:
        print('  [MODERATE_DECAY] 1500期仍正但有衰減 — 可用，持續監控')
    else:
        print(f'  [MIXED] 趨勢不明確 — 需進一步分析')

    print()
    print('=' * 65)


def print_single_report(result):
    """印出單次回測報告（含標題）"""
    lt = LOTTERY_NAMES.get(result['lottery_type'], result['lottery_type'])
    print()
    print('=' * 65)
    print(f'  {lt} {result["num_bets"]}注 — 回測報告')
    print('=' * 65)
    print()
    print_report(result)
    print()
    print('=' * 65)


# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description='彩票回測工具 (2026-02-11 Edge 方法論)')
    parser.add_argument('lottery', nargs='?', default='all',
                        help='彩票類型 (大樂透/威力彩/all)')
    parser.add_argument('bets', nargs='?', type=int, default=None,
                        help='回測注數')
    parser.add_argument('--periods', '-p', type=int, default=1000,
                        help='回測期數 (默認 1000)')
    parser.add_argument('--three-tier', '-t', action='store_true',
                        help='執行 150/500/1500 三階驗證')
    parser.add_argument('--seed', '-s', type=int, default=SEED,
                        help='隨機種子 (默認 42)')
    args = parser.parse_args()

    # 確定彩票類型
    if args.lottery.lower() == 'all':
        tasks = [
            ('BIG_LOTTO', DEFAULT_BETS['BIG_LOTTO']),
            ('POWER_LOTTO', DEFAULT_BETS['POWER_LOTTO']),
        ]
    else:
        lt = LOTTERY_MAP.get(args.lottery.lower(), args.lottery.upper())
        if lt not in BASELINES:
            print(f'不支援: {args.lottery} (可用: 大樂透, 威力彩)')
            sys.exit(1)
        num_bets = args.bets or DEFAULT_BETS.get(lt, 2)
        tasks = [(lt, num_bets)]

    print()
    print('  Lottery Backtest Engine (Edge vs Random)')
    print('  ' + '=' * 45)

    start = time.time()

    for lottery_type, num_bets in tasks:
        if args.three_tier:
            results = run_three_tier(lottery_type, num_bets, args.seed)
            print_three_tier_report(results, lottery_type, num_bets)
        else:
            result = run_backtest(lottery_type, num_bets, args.periods, args.seed)
            print_single_report(result)

    elapsed = time.time() - start
    print(f'\n  耗時: {elapsed:.1f}s')


if __name__ == '__main__':
    main()
