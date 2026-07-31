#!/usr/bin/env python3
"""
最大期数验证：Deviation + Frequency 双注策略
- 使用全部可用历史数据
- 正确的双注回测逻辑
- 统计显著性检验
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
from common import get_lottery_rules
from models.unified_predictor import UnifiedPredictionEngine


def backtest_dual_bet_correct(history: List[Dict], test_size: int) -> Dict:
    """
    正确的双注回测
    
    分别统计:
    1. Bet1命中率
    2. Bet2命中率
    3. 至少一注3+率
    """
    engine = UnifiedPredictionEngine()
    rules = get_lottery_rules('POWER_LOTTO')
    
    bet1_hits = []
    bet2_hits = []
    bet1_3plus = 0
    bet2_3plus = 0
    dual_3plus = 0  # 至少一注3+
    
    print(f"回测{test_size}期...", end='', flush=True)
    
    for i in range(test_size):
        if (i + 1) % 100 == 0:
            print(f" {i+1}", end='', flush=True)
        
        train = history[i+1:]
        test = history[i]
        
        actual_nums = set(test.get('numbers', []))
        
        try:
            # 生成双注
            bet1_pred = engine.deviation_predict(train, rules)
            bet2_pred = engine.frequency_predict(train, rules)
            
            bet1_nums = set(bet1_pred.get('numbers', [])[:6])
            bet2_nums = set(bet2_pred.get('numbers', [])[:6])
            
            # 计算命中
            bet1_match = len(bet1_nums & actual_nums)
            bet2_match = len(bet2_nums & actual_nums)
            
            bet1_hits.append(bet1_match)
            bet2_hits.append(bet2_match)
            
            if bet1_match >= 3:
                bet1_3plus += 1
            if bet2_match >= 3:
                bet2_3plus += 1
            if bet1_match >= 3 or bet2_match >= 3:
                dual_3plus += 1
                
        except Exception as e:
            continue
    
    print(" ✓")
    
    total = len(bet1_hits)
    
    return {
        'total': total,
        'bet1': {
            'mean': np.mean(bet1_hits),
            '3plus': bet1_3plus,
            '3plus_rate': bet1_3plus / total if total > 0 else 0
        },
        'bet2': {
            'mean': np.mean(bet2_hits),
            '3plus': bet2_3plus,
            '3plus_rate': bet2_3plus / total if total > 0 else 0
        },
        'dual': {
            '3plus': dual_3plus,
            '3plus_rate': dual_3plus / total if total > 0 else 0
        }
    }


def main():
    print("=" * 100)
    print("最大期数验证：Deviation + Frequency 双注")
    print("=" * 100)
    
    # 载入全部数据
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path=db_path)
    all_history = db.get_all_draws(lottery_type='POWER_LOTTO')
    
    if not all_history:
        print("❌ 无法载入历史数据")
        return
    
    print(f"\n总历史数据: {len(all_history)} 期")
    print(f"期数范围: {all_history[-1]['draw']} ~ {all_history[0]['draw']}")
    
    # 使用最大可用期数（需要留一些作为训练数据）
    max_test = min(len(all_history) - 50, 1800)
    history = all_history[:max_test + 50]
    
    print(f"\n测试规模: {max_test} 期")
    print(f"测试范围: {history[max_test-1]['draw']} ~ {history[0]['draw']}\n")
    
    # 回测
    result = backtest_dual_bet_correct(history, max_test)
    
    # 结果
    print("\n" + "=" * 100)
    print("回测结果")
    print("=" * 100)
    
    print(f"\n测试期数: {result['total']}")
    
    print(f"\n【Bet1 - Deviation】")
    print(f"  平均命中: {result['bet1']['mean']:.3f}/6")
    print(f"  3+命中: {result['bet1']['3plus']}/{result['total']} ({result['bet1']['3plus_rate']:.2%})")
    
    print(f"\n【Bet2 - Frequency】")
    print(f"  平均命中: {result['bet2']['mean']:.3f}/6")
    print(f"  3+命中: {result['bet2']['3plus']}/{result['total']} ({result['bet2']['3plus_rate']:.2%})")
    
    print(f"\n【双注组合 - 至少一注3+】")
    print(f"  命中: {result['dual']['3plus']}/{result['total']}")
    print(f"  命中率: {result['dual']['3plus_rate']:.2%}")
    
    # 统计检验
    print("\n" + "=" * 100)
    print("统计显著性检验")
    print("=" * 100)
    
    # vs 理论随机7.59%
    theoretical = 0.0759
    binom_result = binomtest(
        result['dual']['3plus'],
        result['total'],
        theoretical,
        alternative='greater'
    )
    
    print(f"\n双注至少一注3+ vs 理论随机7.59%:")
    print(f"  观察: {result['dual']['3plus_rate']:.2%}")
    print(f"  期望: {theoretical:.2%}")
    print(f"  差异: {(result['dual']['3plus_rate'] - theoretical)*100:+.2f} percentage points")
    print(f"  p-value: {binom_result.pvalue:.4f}")
    print(f"  显著性: {'✓ 显著优于随机 (p<0.05)' if binom_result.pvalue < 0.05 else '✗ 未显著优于随机 (p≥0.05)'}")
    
    # Wilson score 95% CI
    from math import sqrt
    n = result['total']
    p_hat = result['dual']['3plus_rate']
    z = 1.96
    
    denominator = 1 + z**2 / n
    center = (p_hat + z**2 / (2*n)) / denominator
    margin = z * sqrt((p_hat * (1 - p_hat) / n + z**2 / (4 * n**2))) / denominator
    
    ci_low = center - margin
    ci_high = center + margin
    
    print(f"  95% CI: [{ci_low:.2%}, {ci_high:.2%}]")
    print(f"  理论值在CI内: {'是' if ci_low <= theoretical <= ci_high else '否'}")
    
    # 最终结论
    print("\n" + "=" * 100)
    print("最终结论")
    print("=" * 100)
    
    print(f"\n测试规模: {result['total']} 期（迄今最大规模）")
    print(f"观察结果: {result['dual']['3plus_rate']:.2%} 至少一注3+")
    print(f"理论随机: 7.59%")
    print(f"p-value: {binom_result.pvalue:.4f}")
    
    if binom_result.pvalue < 0.05:
        print(f"\n✅ 结论: Deviation + Frequency双注**显著优于**随机 (p<0.05)")
        print(f"   这是真实的优势，不是统计噪音")
        improvement = (result['dual']['3plus_rate'] - theoretical) / theoretical * 100
        print(f"   相对改善: {improvement:+.1f}%")
    elif binom_result.pvalue < 0.10:
        print(f"\n⚠️ 结论: Deviation + Frequency双注**接近显著** (0.05 < p < 0.10)")
        print(f"   可能有轻微优势，但证据不足")
        print(f"   建议: 需要更多数据（2000+期）才能确认")
    else:
        print(f"\n❌ 结论: Deviation + Frequency双注**未显著优于**随机 (p≥0.10)")
        print(f"   观察到的差异可能是统计噪音")
        print(f"   建议: 当作随机对待")
    
    print("=" * 100)


if __name__ == '__main__':
    main()
