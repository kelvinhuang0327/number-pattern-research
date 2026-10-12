#!/usr/bin/env python3
"""
大乐透双注组合详细回测
Deviation + Markov 组合 - 最近150期详细分析
"""
import sys
import os
import io
from collections import Counter

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules
from models.unified_predictor import UnifiedPredictionEngine

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def detailed_backtest_deviation_markov():
    """详细回测 Deviation + Markov 双注组合"""
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = list(reversed(db.get_all_draws(lottery_type='BIG_LOTTO')))
    rules = get_lottery_rules('BIG_LOTTO')
    
    test_periods = min(150, len(all_draws) - 50)
    
    engine = UnifiedPredictionEngine()
    
    print("=" * 80)
    print(f"🔬 大乐透双注详细回测 (Deviation + Markov)")
    print("=" * 80)
    print(f"测试期数: {test_periods} 期")
    print(f"组合: 偏差分析 (Deviation) + 马可夫链 (Markov)")
    print("-" * 80)
    
    # 统计数据
    wins = 0
    match_3_plus = 0
    match_4_plus = 0
    match_5_plus = 0
    match_6 = 0
    total = 0
    
    match_distribution = Counter()
    hit_details = []
    
    # 逐期测试
    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        if target_idx <= 0:
            continue
        
        target_draw = all_draws[target_idx]
        hist = all_draws[:target_idx]
        
        if len(hist) < 10:
            continue
        
        actual = set(target_draw['numbers'])
        draw_num = target_draw['draw']
        draw_date = target_draw['date']
        
        # 生成两注预测
        try:
            result_dev = engine.deviation_predict(hist, rules)
            result_mar = engine.markov_predict(hist, rules)
            
            if not result_dev or not result_mar:
                continue
            
            pred_dev = set(result_dev['numbers'])
            pred_mar = set(result_mar['numbers'])
            
            # 计算命中数
            match_dev = len(pred_dev & actual)
            match_mar = len(pred_mar & actual)
            best_match = max(match_dev, match_mar)
            
            # 记录
            match_distribution[best_match] += 1
            
            # 判断中奖
            period_win = False
            period_match3 = False
            
            if best_match >= 6:
                match_6 += 1
                match_5_plus += 1
                match_4_plus += 1
                match_3_plus += 1
                period_match3 = True
                period_win = True
            elif best_match >= 5:
                match_5_plus += 1
                match_4_plus += 1
                match_3_plus += 1
                period_match3 = True
                period_win = True
            elif best_match >= 4:
                match_4_plus += 1
                match_3_plus += 1
                period_match3 = True
                period_win = True
            elif best_match >= 3:
                match_3_plus += 1
                period_match3 = True
                period_win = True
            elif best_match >= 1:
                period_win = True
            
            if period_match3:
                wins += 1
            elif period_win:
                wins += 1
            
            # 记录命中详情
            if best_match >= 3:
                hit_details.append({
                    'draw': draw_num,
                    'date': draw_date,
                    'actual': sorted(actual),
                    'pred_dev': sorted(pred_dev),
                    'pred_mar': sorted(pred_mar),
                    'match_dev': match_dev,
                    'match_mar': match_mar,
                    'best_match': best_match
                })
            
            total += 1
            
        except Exception as e:
            continue
    
    if total == 0:
        print("❌ 回测失败：无有效数据")
        return
    
    # 显示统计结果
    print("\n" + "=" * 80)
    print("📊 回测统计结果")
    print("=" * 80)
    
    print(f"\n总期数: {total}")
    print(f"总胜率: {wins / total * 100:.2f}%")
    print(f"\n命中统计:")
    print(f"  Match-6 (头奖):  {match_6:3d} 次 ({match_6 / total * 100:5.2f}%)")
    print(f"  Match-5+ (贰奖):  {match_5_plus:3d} 次 ({match_5_plus / total * 100:5.2f}%)")
    print(f"  Match-4+ (参奖):  {match_4_plus:3d} 次 ({match_4_plus / total * 100:5.2f}%)")
    print(f"  Match-3+ (肆奖):  {match_3_plus:3d} 次 ({match_3_plus / total * 100:5.2f}%)")
    
    print(f"\n命中分布:")
    for match_count in sorted(match_distribution.keys(), reverse=True):
        count = match_distribution[match_count]
        pct = count / total * 100
        bar = "█" * int(pct / 2)
        print(f"  Match-{match_count}: {count:3d} 次 ({pct:5.1f}%) {bar}")
    
    # 显示 Match-3+ 详情
    if hit_details:
        print("\n" + "=" * 80)
        print(f"🎯 Match-3+ 命中详情 (共 {len(hit_details)} 次)")
        print("=" * 80)
        
        print(f"\n{'期号':<12} {'日期':<12} {'实际号码':<25} {'最佳命中':<10}")
        print("-" * 80)
        
        for detail in hit_details[:20]:  # 只显示前20次
            actual_str = ','.join([f"{n:02d}" for n in detail['actual']])
            best_source = 'Deviation' if detail['match_dev'] >= detail['match_mar'] else 'Markov'
            print(f"{detail['draw']:<12} {detail['date']:<12} {actual_str:<25} {detail['best_match']}号({best_source})")
        
        if len(hit_details) > 20:
            print(f"\n... 还有 {len(hit_details) - 20} 次命中未显示")
    
    # 方法贡献度分析
    print("\n" + "=" * 80)
    print("📈 双注方法贡献度分析")
    print("=" * 80)
    
    dev_better = sum(1 for d in hit_details if d['match_dev'] > d['match_mar'])
    mar_better = sum(1 for d in hit_details if d['match_mar'] > d['match_dev'])
    equal = sum(1 for d in hit_details if d['match_dev'] == d['match_mar'])
    
    if hit_details:
        print(f"Deviation 表现更好: {dev_better} 次 ({dev_better / len(hit_details) * 100:.1f}%)")
        print(f"Markov 表现更好:    {mar_better} 次 ({mar_better / len(hit_details) * 100:.1f}%)")
        print(f"两者相同:           {equal} 次 ({equal / len(hit_details) * 100:.1f}%)")
    
    # 最终总结
    print("\n" + "=" * 80)
    print("🎯 最终总结")
    print("=" * 80)
    
    match_3_rate = match_3_plus / total * 100
    baseline = 2.67
    improvement = match_3_rate - baseline
    
    print(f"✅ Match-3+ 率: {match_3_rate:.2f}%")
    print(f"📈 提升幅度: +{improvement:.2f}% (vs 单注基准 {baseline}%)")
    print(f"💰 性价比: {match_3_rate / 2:.2f}% per 注")
    print(f"🎰 成本: 2 注")
    
    if improvement >= 5.0:
        print(f"\n🎉 达成目标！实际提升 {improvement:.2f}% >= 5%")
    elif improvement >= 3.0:
        print(f"\n📊 显著改善！实际提升 {improvement:.2f}%，接近目标")
    else:
        print(f"\n⚠️ 未达 +5% 目标，实际提升 {improvement:.2f}%")
    
    # 建议
    print("\n💡 使用建议:")
    if match_3_rate >= 5.0:
        print("  ✅ 双注组合表现良好，建议作为大乐透主要策略")
    else:
        print("  ⚠️ 如需更高成功率，可考虑 3-4 注组合")

if __name__ == '__main__':
    detailed_backtest_deviation_markov()
