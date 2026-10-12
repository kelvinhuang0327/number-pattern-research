#!/usr/bin/env python3
"""
大樂透 115000012 檢討優化 - 多窗口回測 (150/500/1500 期)

Phase A: Baseline (Orthogonal 3-Bet 原始版)
Phase D: Full Optimization (Median + Zone Absence + Repeat/Consecutive)

Rolling Backtest: 無資料洩漏
"""
import sys
import os
import logging
import numpy as np
from typing import List, Dict, Tuple
from collections import Counter
from datetime import datetime

# Setup path
lottery_api_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, lottery_api_dir)
os.chdir(lottery_api_dir)

logging.getLogger().setLevel(logging.ERROR)

from database import db_manager
db_manager.db_path = os.path.join(lottery_api_dir, "data", "lottery_v2.db")

from models.unified_predictor import UnifiedPredictionEngine
from models.multi_bet_optimizer import MultiBetOptimizer
from common import get_lottery_rules

# Import optimization modules from the other script
from backtest_115000012_optimizations import (
    MedianZoneSampler, ZoneAbsencePredictor, RepeatConsecutiveForcer,
    EnhancedOrthogonal3Bet
)


def run_rolling_backtest(test_draws, all_draws, predict_func, rules, label):
    """Rolling backtest with no data leakage"""
    max_num = rules.get('maxNumber', 49)
    pick_count = rules.get('pickCount', 6)
    
    stats = {
        'label': label, 'total': 0,
        'bet_hits': [[], [], []],
        'best_hit_per_draw': [], 'union_hits': [],
        'any_3plus': 0, 'any_2plus': 0, 'union_3plus': 0,
        'hit_dist': Counter(),
    }
    
    for target in test_draws:
        target_id = target['draw']
        target_idx = -1
        for i, d in enumerate(all_draws):
            if d['draw'] == target_id:
                target_idx = i
                break
        
        if target_idx == -1 or target_idx < 200:
            continue
        
        history_desc = list(reversed(all_draws[:target_idx]))
        if len(history_desc) < 100:
            continue
        
        recent_nums = [n for d in history_desc[:200] for n in d['numbers']]
        freq_counter = Counter(recent_nums)
        number_scores = {n: freq_counter.get(n, 0) for n in range(1, max_num + 1)}
        
        actual = set(target['numbers'])
        
        try:
            result = predict_func(history_desc, rules, number_scores)
            bets = result.get('bets', [])
            if len(bets) < 3:
                continue
            
            bet_hits_this = []
            all_predicted = set()
            for bi, bet in enumerate(bets[:3]):
                nums = set(bet['numbers'])
                all_predicted |= nums
                hits = len(nums & actual)
                bet_hits_this.append(hits)
                stats['bet_hits'][bi].append(hits)
            
            best_hit = max(bet_hits_this)
            union_hit = len(all_predicted & actual)
            
            stats['best_hit_per_draw'].append(best_hit)
            stats['union_hits'].append(union_hit)
            stats['hit_dist'][best_hit] += 1
            
            if best_hit >= 3: stats['any_3plus'] += 1
            if best_hit >= 2: stats['any_2plus'] += 1
            if union_hit >= 3: stats['union_3plus'] += 1
            stats['total'] += 1
            
        except Exception:
            pass
    
    return stats


def print_compact_stats(stats):
    n = stats['total']
    if n == 0:
        print(f"   ❌ {stats['label']}: 無有效測試")
        return
    
    avg_best = np.mean(stats['best_hit_per_draw'])
    avg_union = np.mean(stats['union_hits'])
    rate_3 = stats['any_3plus'] / n * 100
    rate_2 = stats['any_2plus'] / n * 100
    u3 = stats['union_3plus'] / n * 100
    avg_bets = [np.mean(h) if h else 0 for h in stats['bet_hits']]
    
    print(f"   測試期數: {n} | B1={avg_bets[0]:.2f} B2={avg_bets[1]:.2f} B3={avg_bets[2]:.2f}")
    print(f"   最佳注Avg: {avg_best:.3f} | 聯合Avg: {avg_union:.3f}")
    print(f"   3+率: {rate_3:.1f}% ({stats['any_3plus']}/{n}) | 2+率: {rate_2:.1f}% | U3+率: {u3:.1f}%")
    dist = stats['hit_dist']
    print(f"   命中分佈: ", end="")
    for h in sorted(dist.keys(), reverse=True):
        print(f"{h}hit={dist[h]}({dist[h]/n*100:.1f}%) ", end="")
    print()


def main():
    print("=" * 90)
    print("🎰 大樂透 優化回測 - 多窗口比較 (150 / 500 / 1500 期)")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 90)
    
    rules = get_lottery_rules('BIG_LOTTO')
    all_draws = db_manager.get_all_draws('BIG_LOTTO')
    all_draws.sort(key=lambda x: x['date'])  # ASC
    
    total = len(all_draws)
    print(f"\n📦 總數據: {total} 期")
    
    engine = UnifiedPredictionEngine()
    optimizer = MultiBetOptimizer()
    enhanced = EnhancedOrthogonal3Bet(engine, optimizer)
    
    windows = [150, 500, 1500]
    
    # 收集所有結果用於最終對比表
    all_results = []
    
    for window in windows:
        if window > total - 200:
            actual_window = total - 200
            print(f"\n⚠️ {window} 期超出可用範圍，縮減至 {actual_window} 期")
            window = actual_window
        
        # 取最近 N 期作為測試集
        test_draws = all_draws[-window:]
        
        print(f"\n{'=' * 90}")
        print(f"📐 窗口: 最近 {window} 期")
        print(f"   範圍: {test_draws[0]['draw']} ~ {test_draws[-1]['draw']}")
        print(f"{'=' * 90}")
        
        # Phase A: Baseline
        print(f"\n   🅰️ Baseline Orthogonal 3-Bet")
        stats_a = run_rolling_backtest(
            test_draws, all_draws,
            enhanced.predict_baseline,
            rules, f"Baseline ({window}期)"
        )
        print_compact_stats(stats_a)
        all_results.append(stats_a)
        
        # Phase D: Full Optimization
        print(f"\n   🅳 Full Optimization (Median+Zone+Repeat)")
        stats_d = run_rolling_backtest(
            test_draws, all_draws,
            enhanced.predict_full_optimization,
            rules, f"Full Optim ({window}期)"
        )
        print_compact_stats(stats_d)
        all_results.append(stats_d)
        
        # Delta
        if stats_a['total'] > 0 and stats_d['total'] > 0:
            a3 = stats_a['any_3plus'] / stats_a['total'] * 100
            d3 = stats_d['any_3plus'] / stats_d['total'] * 100
            delta = d3 - a3
            print(f"\n   📈 Δ3+率: {delta:+.1f} 百分點 ({a3:.1f}% → {d3:.1f}%)")
    
    # Final comparison table
    print(f"\n{'=' * 90}")
    print("📊 最終對比表")
    print("=" * 90)
    print(f"{'策略':<30} | {'期數':>5} | {'BestAvg':>8} | {'UnionAvg':>9} | {'3+%':>7} | {'2+%':>7} | {'U3+%':>7}")
    print("-" * 90)
    
    for s in all_results:
        n = s['total']
        if n == 0: continue
        avg_b = np.mean(s['best_hit_per_draw'])
        avg_u = np.mean(s['union_hits'])
        r3 = s['any_3plus'] / n * 100
        r2 = s['any_2plus'] / n * 100
        u3 = s['union_3plus'] / n * 100
        print(f"{s['label']:<30} | {n:>5} | {avg_b:>8.3f} | {avg_u:>9.3f} | {r3:>6.1f}% | {r2:>6.1f}% | {u3:>6.1f}%")
    
    # Summary
    print(f"\n{'=' * 90}")
    print("🏁 總結")
    print("=" * 90)
    
    for i in range(0, len(all_results), 2):
        if i + 1 >= len(all_results): break
        sa = all_results[i]
        sd = all_results[i + 1]
        if sa['total'] == 0 or sd['total'] == 0: continue
        a3 = sa['any_3plus'] / sa['total'] * 100
        d3 = sd['any_3plus'] / sd['total'] * 100
        label = sa['label'].split('(')[1].rstrip(')')
        mult = d3 / a3 if a3 > 0 else float('inf')
        print(f"   {label}: Baseline {a3:.1f}% → Optimized {d3:.1f}% (Δ={d3-a3:+.1f}%, x{mult:.1f})")


if __name__ == '__main__':
    main()
