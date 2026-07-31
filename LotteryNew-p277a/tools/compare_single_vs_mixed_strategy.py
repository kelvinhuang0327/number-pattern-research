#!/usr/bin/env python3
"""
验证：单一策略两注 vs 多策略两注

对比:
1. 单一策略：Frequency x2 (高频 + 次高频，最大化覆盖)
2. 多策略：Frequency + 反向优化 (对冲风险)
"""
import sys
import os
import numpy as np
from collections import Counter
from scipy.stats import binomtest
from typing import List, Dict

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager


def frequency_predict(history: List[Dict], window: int = 100, exclude: List[int] = None) -> List[int]:
    """频率预测"""
    recent = history[:min(window, len(history))]
    freq = Counter()
    for d in recent:
        freq.update(d.get('numbers', []))
    
    if exclude:
        candidates = [(n, c) for n, c in freq.items() if n not in exclude]
    else:
        candidates = list(freq.items())
    
    candidates.sort(key=lambda x: x[1], reverse=True)
    return sorted([n for n, _ in candidates[:6]])


def reverse_optimize_predict(history: List[Dict]) -> List[int]:
    """反向优化预测"""
    recent = history[:min(100, len(history))]
    freq = Counter()
    for d in recent:
        freq.update(d.get('numbers', []))
    
    # 优先高区，避开生日月
    high_zone = [n for n in range(32, 39)]
    high_sorted = sorted(high_zone, key=lambda x: freq.get(x, 0), reverse=True)
    
    mid_zone = [n for n in range(13, 32) if n not in [17, 18, 27, 28]]
    mid_sorted = sorted(mid_zone, key=lambda x: freq.get(x, 0), reverse=True)
    
    # 高区3个
    nums = high_sorted[:3]
    # 中区3个
    nums.extend([n for n in mid_sorted if n not in nums][:3])
    
    return sorted(nums[:6])


def backtest_dual_strategy(history: List[Dict], test_size: int, 
                          strategy_name: str) -> Dict:
    """
    回测双注策略
    
    strategy_name:
    - 'single': Frequency x2 (单一策略)
    - 'mixed': Frequency + 反向优化 (多策略)
    """
    bet1_hits = []
    bet2_hits = []
    dual_3plus = 0
    
    print(f"回测 {strategy_name} ({test_size}期)...", end='', flush=True)
    
    for i in range(test_size):
        if (i + 1) % 200 == 0:
            print(f" {i+1}", end='', flush=True)
        
        train = history[i+1:]
        test = history[i]
        actual = set(test.get('numbers', []))
        
        try:
            if strategy_name == 'single':
                # 单一策略：Frequency高频 + Frequency次高频
                bet1 = frequency_predict(train, 100, exclude=None)
                bet2 = frequency_predict(train, 100, exclude=bet1)
            else:  # mixed
                # 多策略：Frequency + 反向优化
                bet1 = frequency_predict(train, 100, exclude=None)
                bet2 = reverse_optimize_predict(train)
            
            bet1_match = len(set(bet1) & actual)
            bet2_match = len(set(bet2) & actual)
            
            bet1_hits.append(bet1_match)
            bet2_hits.append(bet2_match)
            
            if bet1_match >= 3 or bet2_match >= 3:
                dual_3plus += 1
                
        except:
            continue
    
    print(" ✓")
    
    total = len(bet1_hits)
    dual_rate = dual_3plus / total if total > 0 else 0
    
    # 覆盖率分析
    overlap_sum = 0
    for i in range(min(100, len(bet1_hits))):
        train = history[i+1:]
        if strategy_name == 'single':
            bet1 = set(frequency_predict(train, 100, exclude=None))
            bet2 = set(frequency_predict(train, 100, exclude=list(bet1)))
        else:
            bet1 = set(frequency_predict(train, 100, exclude=None))
            bet2 = set(reverse_optimize_predict(train))
        overlap_sum += len(bet1 & bet2)
    
    avg_overlap = overlap_sum / 100
    avg_coverage = 12 - avg_overlap
    
    return {
        'strategy': strategy_name,
        'total': total,
        'bet1_mean': np.mean(bet1_hits),
        'bet2_mean': np.mean(bet2_hits),
        'dual_3plus': dual_3plus,
        'dual_rate': dual_rate,
        'avg_overlap': avg_overlap,
        'avg_coverage': avg_coverage
    }


def main():
    print("=" * 100)
    print("单一策略 vs 多策略双注对比验证")
    print("=" * 100)
    
    # 载入数据
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path=db_path)
    all_history = db.get_all_draws(lottery_type='POWER_LOTTO')
    
    print(f"\n总历史数据: {len(all_history)} 期")
    
    # 使用500期测试（平衡速度和准确性）
    test_size = min(500, len(all_history) - 50)
    history = all_history[:test_size + 50]
    
    print(f"测试规模: {test_size} 期\n")
    
    # 回测两种策略
    result_single = backtest_dual_strategy(history, test_size, 'single')
    result_mixed = backtest_dual_strategy(history, test_size, 'mixed')
    
    # 结果对比
    print("\n" + "=" * 100)
    print("回测结果对比")
    print("=" * 100)
    
    print(f"\n{'策略':<20} | {'Bet1均值':<12} | {'Bet2均值':<12} | {'双注3+率':<12} | {'平均覆盖'}")
    print("-" * 100)
    
    for result in [result_single, result_mixed]:
        strategy_name = '单一策略(Freq×2)' if result['strategy'] == 'single' else '多策略(Freq+反向)'
        print(f"{strategy_name:<20} | "
              f"{result['bet1_mean']:>6.3f}/6    | "
              f"{result['bet2_mean']:>6.3f}/6    | "
              f"{result['dual_rate']:>6.2%}      | "
              f"{result['avg_coverage']:.1f}/38")
    
    # 统计检验
    print("\n" + "=" * 100)
    print("统计显著性检验")
    print("=" * 100)
    
    theoretical = 0.0759
    
    for result in [result_single, result_mixed]:
        strategy_name = '单一策略' if result['strategy'] == 'single' else '多策略'
        binom_result = binomtest(
            result['dual_3plus'],
            result['total'],
            theoretical,
            alternative='greater'
        )
        
        print(f"\n【{strategy_name}】")
        print(f"  双注3+率: {result['dual_rate']:.2%}")
        print(f"  vs理论: {theoretical:.2%}")
        print(f"  差异: {(result['dual_rate'] - theoretical)*100:+.2f}pp")
        print(f"  p-value: {binom_result.pvalue:.4f}")
        print(f"  显著性: {'✓' if binom_result.pvalue < 0.05 else '✗'}")
    
    # 直接对比
    print("\n" + "=" * 100)
    print("策略直接对比")
    print("=" * 100)
    
    diff_rate = result_single['dual_rate'] - result_mixed['dual_rate']
    diff_coverage = result_single['avg_coverage'] - result_mixed['avg_coverage']
    
    print(f"\n单一策略 vs 多策略:")
    print(f"  3+率差异: {diff_rate*100:+.2f}pp")
    print(f"  覆盖差异: {diff_coverage:+.1f}个号码")
    
    if abs(diff_rate) < 0.01:  # 差异<1%
        print(f"\n结论: 两种策略**无实质差异**（<1pp）")
    elif diff_rate > 0:
        print(f"\n结论: **单一策略略优** (+{diff_rate*100:.2f}pp)")
        if diff_rate > 0.02:
            print(f"  需要统计检验确认是否显著")
    else:
        print(f"\n结论: **多策略略优** ({diff_rate*100:.2f}pp)")
        if diff_rate < -0.02:
            print(f"  需要统计检验确认是否显著")
    
    # 最终建议
    print("\n" + "=" * 100)
    print("最终建议")
    print("=" * 100)
    
    print(f"\n基于{test_size}期回测:")
    
    # 找出较优策略
    if result_single['dual_rate'] > result_mixed['dual_rate']:
        better = '单一策略(Frequency x2)'
        better_rate = result_single['dual_rate']
        worse_rate = result_mixed['dual_rate']
    else:
        better = '多策略(Frequency + 反向优化)'
        better_rate = result_mixed['dual_rate']
        worse_rate = result_single['dual_rate']
    
    improvement = (better_rate - worse_rate) / worse_rate * 100
    
    print(f"\n✓ 较优策略: {better}")
    print(f"  - 3+率: {better_rate:.2%}")
    print(f"  - 相对优势: {improvement:+.1f}%")
    
    # 但检查是否显著
    better_result = result_single if result_single['dual_rate'] > result_mixed['dual_rate'] else result_mixed
    binom = binomtest(better_result['dual_3plus'], better_result['total'], theoretical, alternative='greater')
    
    if binom.pvalue >= 0.05:
        print(f"\n⚠️ 但注意: 即使较优策略也未显著优于随机 (p={binom.pvalue:.4f})")
        print(f"  实际建议: 两种策略效果相当，选择更简单的")
    
    print("=" * 100)


if __name__ == '__main__':
    main()
