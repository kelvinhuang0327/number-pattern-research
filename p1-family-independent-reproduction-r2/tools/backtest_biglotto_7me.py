#!/usr/bin/env python3
"""
大樂透 7-Method Ensemble (7ME) 回測驗證
對比 Claude 提出的 7ME 與已驗證的 5ME 策略
"""
import sys
import os
import random
import numpy as np
from collections import Counter

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
# sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager
from lottery_api.common import get_lottery_rules
from lottery_api.models.unified_predictor import UnifiedPredictionEngine

# 設定隨機種子確保可復現
SEED = 42
random.seed(SEED)
np.random.seed(SEED)

# 原版 7ME 方法配置 (Claude 提出)
METHODS_7ME_ORIGINAL = [
    ('statistical_predict', '統計綜合', 'TME核心'),
    ('deviation_predict', '偏差分析', 'TME核心'),
    ('markov_predict', '馬可夫鏈', 'TME核心'),
    ('hot_cold_mix_predict', '冷熱混合', 'TME核心'),
    ('trend_predict', '趨勢分析', '5ME補充'),
    ('bayesian_predict', '貝葉斯', '額外覆蓋'),
    ('frequency_predict', '頻率統計', '額外覆蓋'),
]

# 修改版 7ME 方法配置 (改進建議)
METHODS_7ME_IMPROVED = [
    ('statistical_predict', '統計綜合', 'TME核心'),
    ('deviation_predict', '偏差分析', 'TME核心'),
    ('markov_predict', '馬可夫鏈', 'TME核心'),
    ('hot_cold_mix_predict', '冷熱混合', 'TME核心'),
    ('trend_predict', '趨勢分析', '5ME補充'),
    ('zone_balance_predict', '區域平衡', '2025最佳'),
    ('sum_range_predict', '和值範圍', '穩定補充'),
]

# 5ME 方法配置 (已驗證 11%)
METHODS_5ME = [
    ('statistical_predict', '統計綜合'),
    ('deviation_predict', '偏差分析'),
    ('markov_predict', '馬可夫鏈'),
    ('hot_cold_mix_predict', '冷熱混合'),
    ('trend_predict', '趨勢分析'),
]


def backtest_strategy(history, rules, methods, strategy_name, test_periods=200):
    """
    回測策略表現
    
    Args:
        history: 歷史數據 (從舊到新)
        rules: 彩票規則
        methods: 方法列表
        strategy_name: 策略名稱
        test_periods: 測試期數
    
    Returns:
        回測結果字典
    """
    engine = UnifiedPredictionEngine()
    
    total = 0
    match_3_plus = 0
    match_4_plus = 0
    match_dist = Counter()
    wins_by_method = Counter()
    
    print(f"\n{'='*60}")
    print(f"🔬 {strategy_name} 回測驗證 (seed={SEED}, {test_periods}期)")
    print(f"{'='*60}")
    
    for i in range(test_periods):
        target_idx = len(history) - test_periods + i
        if target_idx <= 0:
            continue
        
        target_draw = history[target_idx]
        hist = history[:target_idx]
        actual = set(target_draw['numbers'])
        
        try:
            best_match = 0
            winning_method = None
            
            # 每種方法生成一注
            for method_func, method_name, *_ in methods:
                try:
                    result = getattr(engine, method_func)(hist, rules)
                    predicted = set(result['numbers'][:6])
                    match_count = len(predicted & actual)
                    
                    if match_count > best_match:
                        best_match = match_count
                        winning_method = method_name
                except:
                    continue
            
            match_dist[best_match] += 1
            
            if best_match >= 3:
                match_3_plus += 1
                if winning_method:
                    wins_by_method[winning_method] += 1
            
            if best_match >= 4:
                match_4_plus += 1
            
            total += 1
            
            # 進度顯示
            if (i + 1) % 50 == 0:
                current_rate = match_3_plus / total * 100
                print(f"  進度: {i+1}/{test_periods} | Match-3+: {current_rate:.2f}%")
        
        except Exception as e:
            continue
    
    rate = match_3_plus / total * 100 if total > 0 else 0
    rate_4 = match_4_plus / total * 100 if total > 0 else 0
    
    return {
        'strategy': strategy_name,
        'num_bets': len(methods),
        'total': total,
        'match_3_plus': match_3_plus,
        'match_4_plus': match_4_plus,
        'rate': rate,
        'rate_4': rate_4,
        'distribution': dict(match_dist),
        'wins_by_method': dict(wins_by_method),
        'cost': len(methods) * 50
    }


def print_results(results):
    """打印回測結果"""
    print(f"\n{'='*60}")
    print(f"📊 {results['strategy']} 結果")
    print(f"{'='*60}")
    print(f"注數: {results['num_bets']} 注")
    print(f"成本: NT${results['cost']}")
    print(f"測試期數: {results['total']} 期")
    print(f"\n🎯 Match-3+ 率: {results['rate']:.2f}% ({results['match_3_plus']}/{results['total']})")
    print(f"🎯 Match-4+ 率: {results['rate_4']:.2f}% ({results['match_4_plus']}/{results['total']})")
    print(f"效益/注: {results['rate']/results['num_bets']:.2f}%")
    
    print(f"\n📈 匹配分布:")
    for m in sorted(results['distribution'].keys(), reverse=True):
        count = results['distribution'][m]
        pct = count / results['total'] * 100
        bar = '█' * int(pct / 2)
        print(f"  Match-{m}: {count:3d} 次 ({pct:5.2f}%) {bar}")
    
    if results['wins_by_method']:
        print(f"\n🏆 方法貢獻 (Match-3+中獎):")
        sorted_methods = sorted(results['wins_by_method'].items(), 
                               key=lambda x: x[1], reverse=True)
        for method, wins in sorted_methods:
            print(f"  {method}: {wins} 次")


def compare_strategies(results_list):
    """對比多個策略"""
    print(f"\n{'='*60}")
    print("📊 策略對比總表")
    print(f"{'='*60}")
    print(f"{'策略':<20} {'注數':<6} {'Match-3+':<12} {'效益/注':<10} {'成本':<8}")
    print("-" * 60)
    
    for r in sorted(results_list, key=lambda x: x['rate'], reverse=True):
        efficiency = r['rate'] / r['num_bets']
        print(f"{r['strategy']:<20} {r['num_bets']:<6} "
              f"{r['rate']:<11.2f}% {efficiency:<9.2f}% NT${r['cost']:<6}")
    
    print("\n💡 關鍵發現:")
    
    # 找出最佳勝率
    best_rate = max(results_list, key=lambda x: x['rate'])
    print(f"  🏆 最高勝率: {best_rate['strategy']} ({best_rate['rate']:.2f}%)")
    
    # 找出最佳效益
    best_efficiency = max(results_list, key=lambda x: x['rate']/x['num_bets'])
    eff = best_efficiency['rate'] / best_efficiency['num_bets']
    print(f"  💰 最高效益: {best_efficiency['strategy']} ({eff:.2f}%/注)")
    
    # 成本效益分析
    print(f"\n💵 成本效益分析:")
    for r in results_list:
        roi = r['rate'] / r['cost'] * 100
        print(f"  {r['strategy']}: {roi:.2f}% 勝率/NT$100")


def main():
    print("=" * 60)
    print("🎰 大樂透 7ME 策略回測驗證系統")
    print("=" * 60)
    print(f"隨機種子: {SEED}")
    
    # 載入數據
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = list(reversed(db.get_all_draws(lottery_type='BIG_LOTTO')))
    rules = get_lottery_rules('BIG_LOTTO')
    
    print(f"歷史數據: {len(all_draws)} 期")
    
    # 執行回測
    results_list = []
    
    # 1. 原版 7ME
    results_7me_orig = backtest_strategy(
        all_draws, rules, METHODS_7ME_ORIGINAL, 
        "7ME 原版", test_periods=200
    )
    print_results(results_7me_orig)
    results_list.append(results_7me_orig)
    
    # 2. 修改版 7ME  
    results_7me_improved = backtest_strategy(
        all_draws, rules, METHODS_7ME_IMPROVED,
        "7ME 改進版", test_periods=200
    )
    print_results(results_7me_improved)
    results_list.append(results_7me_improved)
    
    # 3. 5ME (參照組)
    results_5me = backtest_strategy(
        all_draws, rules, METHODS_5ME,
        "5ME (已驗證)", test_periods=200
    )
    print_results(results_5me)
    results_list.append(results_5me)
    
    # 對比分析
    compare_strategies(results_list)
    
    # 建議
    print(f"\n{'='*60}")
    print("🎯 最終建議")
    print(f"{'='*60}")
    
    if results_7me_orig['rate'] > results_5me['rate'] + 1.0:
        print("✅ 7ME 原版 顯著優於 5ME，建議採用")
    elif results_7me_improved['rate'] > results_5me['rate'] + 1.0:
        print("✅ 7ME 改進版 顯著優於 5ME，建議採用")
    else:
        print("⚠️ 7ME 未顯著優於 5ME，建議繼續使用 5ME")
        rate_diff = results_5me['rate'] - max(results_7me_orig['rate'], results_7me_improved['rate'])
        cost_diff = 350 - 250
        print(f"   5ME 優勢: +{rate_diff:.2f}% 勝率, 省 NT${cost_diff}")


if __name__ == '__main__':
    main()
