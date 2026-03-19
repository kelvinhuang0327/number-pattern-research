#!/usr/bin/env python3
"""
高頻突斷 (High-Frequency Sudden-Stop) 監控指標
=================================================
背景: 115000053 期 #02 暴露 ACB 盲點
  freq100=14 (> expected 12.82) 但 gap=38
  ACB 的 freq_deficit(-1.18)×0.4 抵消 gap_score(0.76)×0.6 → score ≈ 0

定義: 號碼 n 滿足以下兩個條件即為「高頻突斷」:
  1. freq100(n) > expected_freq (近100期出現次數 > 期望值)
  2. gap(n) > GAP_THRESHOLD (距上次出現 > 閾值)

回測: 200 期 walk-forward
  每期找出所有高頻突斷號碼，統計下期是否命中
  命中率 vs 隨機基準 (5/39 = 12.82%)

決策: 如果命中率顯著 > 基準 → 建議調整 ACB 權重
      否則 → 記錄結論，不做調整
"""
import json
import math
import os
import sys
import warnings
from collections import Counter
from datetime import datetime

import numpy as np
from scipy import stats as scipy_stats

warnings.filterwarnings('ignore')

_base = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_base, '..', 'lottery_api'))
sys.path.insert(0, os.path.join(_base, '..'))
from database import DatabaseManager

POOL = 39
PICK = 5
RANDOM_HIT_RATE = PICK / POOL  # 12.82%
GAP_THRESHOLD = 20
TEST_PERIODS = 200
WINDOW = 100


def get_numbers(draw):
    n = draw.get('numbers', [])
    if isinstance(n, str):
        n = json.loads(n)
    return list(n)


def find_high_freq_stop(history, window=WINDOW, gap_threshold=GAP_THRESHOLD):
    """找出當前所有「高頻突斷」號碼"""
    recent = history[-window:] if len(history) >= window else history
    freq = Counter()
    for d in recent:
        for n in get_numbers(d):
            freq[n] += 1

    last_seen = {}
    for i, d in enumerate(recent):
        for n in get_numbers(d):
            last_seen[n] = i
    current = len(recent)
    gaps = {n: current - last_seen.get(n, -1) for n in range(1, POOL + 1)}

    expected_freq = len(recent) * PICK / POOL

    hfs_numbers = []
    for n in range(1, POOL + 1):
        if freq.get(n, 0) > expected_freq and gaps[n] > gap_threshold:
            hfs_numbers.append({
                'number': n,
                'freq100': freq.get(n, 0),
                'gap': gaps[n],
                'expected': round(expected_freq, 2),
                'freq_deficit': round(expected_freq - freq.get(n, 0), 2),
                'gap_score': round(gaps[n] / (len(recent) / 2), 3),
                'acb_score_approx': round(
                    ((expected_freq - freq.get(n, 0)) * 0.4 + (gaps[n] / (len(recent) / 2)) * 0.6)
                    * (1.2 if (n <= 5 or n >= 35) else 1.0)
                    * (1.1 if n % 3 == 0 else 1.0),
                    3
                ),
            })
    return hfs_numbers


def backtest(all_draws, test_periods=TEST_PERIODS, min_train=WINDOW + 10):
    """Walk-forward 回測: 高頻突斷號碼的下期命中率"""
    results = []
    hfs_counts = []
    total_hfs_numbers = 0
    total_hits = 0

    for i in range(test_periods):
        tidx = len(all_draws) - test_periods + i
        if tidx < min_train:
            continue

        history = all_draws[:tidx]
        actual = set(get_numbers(all_draws[tidx]))

        hfs = find_high_freq_stop(history)
        n_hfs = len(hfs)
        hfs_counts.append(n_hfs)

        if n_hfs == 0:
            results.append({'n_hfs': 0, 'hits': 0, 'draw': all_draws[tidx]['draw']})
            continue

        hits = sum(1 for h in hfs if h['number'] in actual)
        total_hfs_numbers += n_hfs
        total_hits += hits

        results.append({
            'n_hfs': n_hfs,
            'hits': hits,
            'draw': all_draws[tidx]['draw'],
            'hfs_numbers': [h['number'] for h in hfs],
            'actual': sorted(actual),
            'hit_numbers': [h['number'] for h in hfs if h['number'] in actual],
        })

    # Stats
    periods_with_hfs = sum(1 for r in results if r['n_hfs'] > 0)
    avg_hfs = np.mean(hfs_counts) if hfs_counts else 0
    hit_rate = total_hits / total_hfs_numbers if total_hfs_numbers > 0 else 0

    # Binomial test
    binom_p = 1.0
    z_score = 0.0
    if total_hfs_numbers > 0:
        binom_result = scipy_stats.binomtest(total_hits, total_hfs_numbers, RANDOM_HIT_RATE, alternative='greater')
        binom_p = binom_result.pvalue
        se = math.sqrt(RANDOM_HIT_RATE * (1 - RANDOM_HIT_RATE) / total_hfs_numbers)
        z_score = (hit_rate - RANDOM_HIT_RATE) / se if se > 0 else 0

    return {
        'test_periods': len(results),
        'periods_with_hfs': periods_with_hfs,
        'pct_periods_with_hfs': round(periods_with_hfs / len(results) * 100, 1) if results else 0,
        'avg_hfs_per_period': round(avg_hfs, 2),
        'total_hfs_numbers': total_hfs_numbers,
        'total_hits': total_hits,
        'hit_rate': round(hit_rate * 100, 3),
        'random_baseline': round(RANDOM_HIT_RATE * 100, 3),
        'edge': round((hit_rate - RANDOM_HIT_RATE) * 100, 3),
        'z_score': round(z_score, 3),
        'binom_p': round(binom_p, 4),
        'significant': binom_p < 0.05,
        'results': results,
    }


def main():
    db_path = os.path.join(_base, '..', 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path=db_path)
    all_draws = sorted(db.get_all_draws('DAILY_539'), key=lambda x: (x['date'], x['draw']))

    print("=" * 65)
    print("  539 高頻突斷 (High-Freq Sudden-Stop) 監控指標")
    print(f"  定義: freq100 > expected AND gap > {GAP_THRESHOLD}")
    print(f"  回測: {TEST_PERIODS}期 walk-forward")
    print("=" * 65)
    print(f"  資料: {len(all_draws)} 期")

    # Current status
    print(f"\n--- 當前高頻突斷號碼 ---")
    current_hfs = find_high_freq_stop(all_draws)
    if current_hfs:
        for h in current_hfs:
            print(f"  #{h['number']:02d}: freq100={h['freq100']}, gap={h['gap']}, "
                  f"ACB_score={h['acb_score_approx']:.3f}")
    else:
        print("  (無)")

    # Backtest
    print(f"\n--- {TEST_PERIODS}期回測 ---")
    bt = backtest(all_draws, TEST_PERIODS)
    bt_no_detail = {k: v for k, v in bt.items() if k != 'results'}

    print(f"  測試期數: {bt['test_periods']}")
    print(f"  含HFS期數: {bt['periods_with_hfs']} ({bt['pct_periods_with_hfs']}%)")
    print(f"  平均每期HFS數: {bt['avg_hfs_per_period']}")
    print(f"  總HFS號碼數: {bt['total_hfs_numbers']}")
    print(f"  命中數: {bt['total_hits']}")
    print(f"  命中率: {bt['hit_rate']}%")
    print(f"  隨機基準: {bt['random_baseline']}%")
    print(f"  Edge: {bt['edge']:+.3f}%")
    print(f"  z = {bt['z_score']:.3f}")
    print(f"  p (binomial) = {bt['binom_p']:.4f}")
    print(f"  顯著: {'YES' if bt['significant'] else 'NO'}")

    # Parameter sensitivity
    print(f"\n--- 參數敏感度 (gap threshold) ---")
    for gt in [15, 20, 25, 30]:
        orig_gt = GAP_THRESHOLD
        bt2 = backtest_with_threshold(all_draws, gt, TEST_PERIODS)
        print(f"  gap>{gt}: {bt2['total_hfs_numbers']} HFS, "
              f"hit_rate={bt2['hit_rate']}%, "
              f"edge={bt2['edge']:+.3f}%, "
              f"z={bt2['z_score']:.2f}, "
              f"p={bt2['binom_p']:.4f}")

    # Decision
    print(f"\n--- 決策 ---")
    if bt['significant'] and bt['edge'] > 0:
        decision = "ACTIONABLE — 建議調整 ACB 權重或加入 HFS 加分"
    else:
        decision = "NOT_ACTIONABLE — 高頻突斷無統計顯著信號，維持 ACB 不變"
    print(f"  {decision}")

    # Save
    def _clean(obj):
        if isinstance(obj, (np.bool_,)):
            return bool(obj)
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, dict):
            return {k: _clean(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_clean(v) for v in obj]
        return obj

    report = _clean({
        'timestamp': datetime.now().isoformat(),
        'definition': f'freq100 > expected AND gap > {GAP_THRESHOLD}',
        'test_periods': TEST_PERIODS,
        'window': WINDOW,
        'current_hfs': current_hfs,
        'backtest': bt_no_detail,
        'decision': decision,
    })
    out_path = os.path.join(_base, '..', 'data', 'high_freq_stop_monitor.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\n  [SAVED] {out_path}")
    print("=" * 65)


def backtest_with_threshold(all_draws, gap_threshold, test_periods):
    """Helper for sensitivity analysis with different gap thresholds"""
    results = []
    total_hfs = 0
    total_hits = 0

    for i in range(test_periods):
        tidx = len(all_draws) - test_periods + i
        if tidx < WINDOW + 10:
            continue
        history = all_draws[:tidx]
        actual = set(get_numbers(all_draws[tidx]))
        hfs = find_high_freq_stop(history, gap_threshold=gap_threshold)
        n_hfs = len(hfs)
        if n_hfs > 0:
            hits = sum(1 for h in hfs if h['number'] in actual)
            total_hfs += n_hfs
            total_hits += hits

    hit_rate = total_hits / total_hfs if total_hfs > 0 else 0
    z = 0
    binom_p = 1.0
    if total_hfs > 0:
        se = math.sqrt(RANDOM_HIT_RATE * (1 - RANDOM_HIT_RATE) / total_hfs)
        z = (hit_rate - RANDOM_HIT_RATE) / se if se > 0 else 0
        binom_result = scipy_stats.binomtest(total_hits, total_hfs, RANDOM_HIT_RATE, alternative='greater')
        binom_p = binom_result.pvalue

    return {
        'total_hfs_numbers': total_hfs,
        'total_hits': total_hits,
        'hit_rate': round(hit_rate * 100, 3),
        'random_baseline': round(RANDOM_HIT_RATE * 100, 3),
        'edge': round((hit_rate - RANDOM_HIT_RATE) * 100, 3),
        'z_score': round(z, 3),
        'binom_p': round(binom_p, 4),
    }


if __name__ == '__main__':
    main()
