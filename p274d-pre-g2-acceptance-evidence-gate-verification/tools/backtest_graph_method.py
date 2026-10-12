#!/usr/bin/env python3
"""
GNN 图中心性方法回测
测试基于图的统计方法效果（无需深度学习训练）
"""
import sys
import os
import io
from collections import Counter
import networkx as nx

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules
from models.biglotto_graph import BiglottoGraph
from models.unified_predictor import UnifiedPredictionEngine

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def graph_centrality_predict(history, lottery_rules):
    """基于图中心性的预测方法"""
    # 构建图
    graph_builder = BiglottoGraph()
    graph_builder.build_from_history(history, lookback=500)
    
    # 计算中心性指标
    graph = graph_builder.graph
    degree_cent = nx.degree_centrality(graph)
    betweenness_cent = nx.betweenness_centrality(graph, weight='weight')
    
    # 综合评分
    scores = {}
    for num in range(1, 50):
        feat = graph_builder.node_features.get(num, {})
        
        score = (
            degree_cent.get(num, 0) * 2.0 +           # 度中心性（最重要）
            betweenness_cent.get(num, 0) * 1.5 +      # 介数中心性
            feat.get('frequency_ratio', 0) * 1.5 +    # 历史频率
            (1.0 if feat.get('is_hot', False) else 0.0) * 0.8 -  # 热门加成
            (0.5 if feat.get('is_cold', False) else 0.0) * 0.3   # 冷门惩罚
        )
        scores[num] = score
    
    # 选择分数最高的号码
    pick_count = lottery_rules.get('pickCount', 6)
    top_numbers = sorted(scores.items(), key=lambda x: -x[1])[:pick_count]
    numbers = sorted([n for n, _ in top_numbers])
    
    return {
        'numbers': numbers,
        'confidence': 0.65,
        'method': 'graph_centrality'
    }

def backtest_graph_method():
    """回测图中心性方法"""
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = list(reversed(db.get_all_draws(lottery_type='BIG_LOTTO')))
    rules = get_lottery_rules('BIG_LOTTO')
    
    test_periods = min(150, len(all_draws) - 50)
    
    engine = UnifiedPredictionEngine()
    
    # 统计
    wins_graph = 0
    match_3_plus_graph = 0
    
    wins_baseline = 0
    match_3_plus_baseline = 0
    
    total = 0
    
    print("=" * 80)
    print(f"🔬 图中心性方法回测 (最近 {test_periods} 期)")
    print("=" * 80)
    print("比较方案:")
    print("  1. 图中心性方法 (GNN 降级方案)")
    print("  2. 单注偏差分析 (当前最佳)")
    print("-" * 80)
    
    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        if target_idx <= 0:
            continue
        
        target_draw = all_draws[target_idx]
        hist = all_draws[:target_idx]
        
        if len(hist) < 50:
            continue
        
        actual = set(target_draw['numbers'])
        
        # 测试图中心性
        try:
            result_graph = graph_centrality_predict(hist, rules)
            predicted_graph = set(result_graph['numbers'])
            match_graph = len(predicted_graph & actual)
            
            if match_graph >= 3:
                match_3_plus_graph += 1
                wins_graph += 1
            elif match_graph >= 1:
                wins_graph += 1
        except Exception as e:
            print(f"⚠️ 期数 {i}: {e}")
            continue
        
        # 测试基准（偏差分析）
        try:
            result_baseline = engine.deviation_predict(hist, rules)
            predicted_baseline = set(result_baseline['numbers'])
            match_baseline = len(predicted_baseline & actual)
            
            if match_baseline >= 3:
                match_3_plus_baseline += 1
                wins_baseline += 1
            elif match_baseline >= 1:
                wins_baseline += 1
        except:
            pass
        
        total += 1
        
        if (i + 1) % 50 == 0:
            print(f"进度: {i+1}/{test_periods}...")
    
    if total == 0:
        print("❌ 测试失败：无有效数据")
        return
    
    # 显示结果
    match3_rate_graph = match_3_plus_graph / total * 100
    match3_rate_baseline = match_3_plus_baseline / total * 100
    improvement = match3_rate_graph - match3_rate_baseline
    
    print("\n" + "=" * 80)
    print("📊 回测结果")
    print("=" * 80)
    print(f"{'方案':<30} {'Match-3+ 率':<15} {'提升幅度':<15}")
    print("-" * 80)
    print(f"{'单注偏差分析 (基准)':<30} {match3_rate_baseline:>13.2f}% {'-':>15}")
    print(f"{'双注优化 V1':<30} {'4.00%':>15} {'+1.33%':>15}")
    print(f"{'🌐 图中心性方法 (新)':<30} {match3_rate_graph:>13.2f}% {improvement:>13.2f}%")
    
    print("\n" + "=" * 80)
    print("🎯 目标达成度评估")
    print("=" * 80)
    print(f"目标: Match-3+ 率提升 5%")
    print(f"实际提升: {improvement:.2f}%")
    
    if improvement >= 5.0:
        print(f"✅ 目标达成！图中心性方法提升 {improvement:.2f}% >= 5%")
        print("💡 建议：可以直接使用图中心性方法作为生产方案")
    elif improvement >= 3.0:
        print(f"📈 显著改善！提升 {improvement:.2f}%")
        print("💡 建议：继续完成 GNN 深度学习训练以达到 +5% 目标")
    elif improvement >= 1.0:
        print(f"📊 有改善。提升 {improvement:.2f}%")
        print("💡 建议：必须完成 GNN 深度学习训练")
    else:
        print(f"⚠️ 效果不佳。提升 {improvement:.2f}%")
        print("💡 建议：回到统计方法或尝试其他深度学习架构")
    
    # 成本效益
    print("\n" + "=" * 80)
    print("💰 成本效益分析")
    print("=" * 80)
    print(f"图中心性 Match-3+ 率: {match3_rate_graph:.2f}% (单注成本)")
    print(f"双注优化 V1 Match-3+ 率: 4.00% (双注成本)")
    print(f"\n成本效益比 (图中心性): {match3_rate_graph:.2f}% per 单位")
    print(f"成本效益比 (双注 V1): {4.00 / 2:.2f}% per 单位")
    
    if match3_rate_graph > 4.00 / 2:
        print(f"✅ 图中心性方案性价比更高！")
    
    return improvement >= 3.0

if __name__ == '__main__':
    success = backtest_graph_method()
