"""
威力彩 20%+ 優化配置 - 代碼實施指南

目標: 驗證 4注推薦配置 (方案B) 是否能達成 19-21% 命中率

推薦配置:
  注1: Ensemble (窗口100)
  注2: Ensemble (窗口500)
  注3: Zone_Balance + Bayesian 混合 (窗口200)
  注4: Trend + Anti-Consensus 混合 (窗口300)
"""

# ============================================================================
# IMPLEMENTATION GUIDE - 實施指南
# ============================================================================

# 步驟 1: 檢查 unified_predictor.py 中所需方法是否存在

REQUIRED_METHODS = {
    'ensemble_predict': {
        'description': '集成多個預測器的平均值',
        'parameters': ['history', 'lottery_rules', 'window_size'],
        'expected_return': {'numbers': list, 'special': int}
    },
    
    'zone_balance_predict': {
        'description': '區域平衡預測',
        'parameters': ['history', 'lottery_rules'],
        'expected_return': {'numbers': list, 'special': int}
    },
    
    'bayesian_predict': {
        'description': '貝葉斯概率預測',
        'parameters': ['history', 'lottery_rules'],
        'expected_return': {'numbers': list, 'special': int}
    },
    
    'trend_predict': {
        'description': '趨勢預測',
        'parameters': ['history', 'lottery_rules'],
        'expected_return': {'numbers': list, 'special': int}
    },
    
    'anti_consensus_predict': {
        'description': '反向共識預測 (選擇最少人選的號碼)',
        'parameters': ['history', 'lottery_rules'],
        'expected_return': {'numbers': list, 'special': int}
    }
}

# ============================================================================
# 步驟 2: 實現回測配置
# ============================================================================

class PowerLottoOptimizedConfig:
    """威力彩 20% 優化配置"""
    
    # 推薦配置 B (窗口變異型)
    BET_CONFIG_4_OPTIMIZED = {
        'name': '4注推薦配置B (窗口變異)',
        'total_bets': 4,
        'bets': [
            {
                'id': 'bet1',
                'method': 'ensemble',
                'window_size': 100,
                'description': '靈活Ensemble - 快速反應',
                'expected_hit_rate': 0.045  # 4.5%
            },
            {
                'id': 'bet2',
                'method': 'ensemble',
                'window_size': 500,
                'description': '穩定Ensemble - 長期模式',
                'expected_hit_rate': 0.045  # 4.5%
            },
            {
                'id': 'bet3',
                'method': 'zone_balance_bayesian_hybrid',  # 自訂混合方法
                'window_size': 200,
                'description': '平衡 + 概率混合',
                'expected_hit_rate': 0.035  # 3.5%
            },
            {
                'id': 'bet4',
                'method': 'trend_anti_consensus_hybrid',  # 自訂混合方法
                'window_size': 300,
                'description': '趨勢 + 反向共識混合',
                'expected_hit_rate': 0.035  # 3.5%
            }
        ],
        'expected_total_hit_rate': 0.195,  # 19.5% 預期
        'cost': 400,  # 4注 × $100
    }
    
    # 保底配置 A (ClusterPivot 變異)
    BET_CONFIG_4_CLUSTERPIVOT = {
        'name': '4注 ClusterPivot 變異',
        'total_bets': 4,
        'bets': [
            {
                'id': 'bet1',
                'method': 'cluster_pivot',
                'anchor_count': 2,
                'window_size': 50,
                'description': '標準ClusterPivot',
            },
            {
                'id': 'bet2',
                'method': 'cluster_pivot',
                'anchor_count': 3,
                'window_size': 100,
                'description': 'ClusterPivot (3錨點)',
            },
            {
                'id': 'bet3',
                'method': 'anti_consensus_cluster_pivot',
                'window_size': 75,
                'description': 'Anti-Consensus ClusterPivot',
            },
            {
                'id': 'bet4',
                'method': 'cluster_pivot_with_kill5',
                'window_size': 50,
                'kill5_precision': 0.886,  # 已驗證 88.6%
                'description': 'ClusterPivot + Kill-5',
            }
        ],
        'expected_total_hit_rate': 0.175,  # 17.5% 預期
        'cost': 400,
    }

# ============================================================================
# 步驟 3: 回測執行代碼框架
# ============================================================================

def run_optimized_backtest(config, all_draws, lottery_rules):
    """
    執行優化後的 4注回測
    
    Parameters:
        config: 配置字典 (見上方 BET_CONFIG_4_OPTIMIZED)
        all_draws: 所有開獎紀錄
        lottery_rules: 樂透規則
    
    Returns:
        {
            'total_tests': int,
            'hit_count': int,
            'hit_rate': float,
            'match_distribution': dict,
            'special_hits': int,
            'bet_results': list
        }
    """
    
    from models.unified_predictor import UnifiedPredictionEngine
    from database import db_manager
    
    engine = UnifiedPredictionEngine()
    
    # 篩選 2025 年測試數據
    test_draws = []
    for i, draw in enumerate(all_draws):
        if '2025' in str(draw.get('date', '')):
            test_draws.append((i, draw))
    
    hit_count = 0
    match_distribution = {i: 0 for i in range(7)}  # 0-6個匹配
    special_hits = 0
    
    # 執行滾動回測
    for target_idx, target_draw in test_draws:
        
        # 獲取該期之後的全部歷史 (防止數據洩漏)
        available_history = all_draws[target_idx + 1:]
        
        # 對 4注分別進行預測
        best_matches = 0
        found_special = False
        
        for bet in config['bets']:
            
            method = bet['method']
            window = bet['window_size']
            
            # 確保有足夠的歷史數據
            if len(available_history) < window:
                continue
            
            history_window = available_history[:window]
            
            try:
                # 根據方法選擇對應的預測函數
                
                if method == 'ensemble':
                    result = engine.ensemble_predict(
                        history_window, 
                        lottery_rules, 
                        window_size=window
                    )
                
                elif method == 'zone_balance_bayesian_hybrid':
                    # 混合方法: 結合 Zone_Balance 和 Bayesian
                    zb_result = engine.zone_balance_predict(history_window, lottery_rules)
                    bay_result = engine.bayesian_predict(history_window, lottery_rules)
                    
                    # 權重混合 (50%-50%)
                    result = engine._blend_predictions(
                        [zb_result, bay_result],
                        weights=[0.5, 0.5]
                    )
                
                elif method == 'trend_anti_consensus_hybrid':
                    # 混合方法: 結合 Trend 和 Anti-Consensus
                    trend_result = engine.trend_predict(history_window, lottery_rules)
                    ac_result = engine.anti_consensus_predict(history_window, lottery_rules)
                    
                    # 權重混合 (60% 趨勢, 40% 反向)
                    result = engine._blend_predictions(
                        [trend_result, ac_result],
                        weights=[0.6, 0.4]
                    )
                
                elif method == 'cluster_pivot':
                    result = engine.cluster_pivot_predict(
                        history_window,
                        lottery_rules,
                        anchor_count=bet.get('anchor_count', 2),
                        resilience=True
                    )
                
                else:
                    continue
                
                # 計算匹配
                predicted_numbers = set(result['numbers'])
                actual_numbers = set(target_draw['numbers'])
                matches = len(predicted_numbers & actual_numbers)
                
                # 特別號
                if result.get('special') == target_draw.get('special'):
                    found_special = True
                
                # 更新最佳匹配
                if matches > best_matches:
                    best_matches = matches
                    
            except Exception as e:
                print(f"Warning: Error in prediction for bet {bet['id']}: {e}")
                continue
        
        # 統計結果
        match_distribution[best_matches] += 1
        
        # 中獎判定: 3個以上主號
        if best_matches >= 3:
            hit_count += 1
        
        if found_special:
            special_hits += 1
    
    # 計算最終統計
    total_tests = sum(match_distribution.values())
    hit_rate = hit_count / total_tests if total_tests > 0 else 0
    
    return {
        'config_name': config['name'],
        'total_tests': total_tests,
        'hit_count': hit_count,
        'hit_rate': hit_rate,
        'match_distribution': match_distribution,
        'special_hits': special_hits,
        'cost': config['cost'],
        'cost_efficiency': hit_rate / (config['cost'] / 100),  # hit_rate per $100
    }

# ============================================================================
# 步驟 4: 輔助方法 (如果 unified_predictor 中不存在)
# ============================================================================

def implement_missing_methods_in_engine():
    """
    如果以下方法在 unified_predictor.py 中不存在, 需要添加:
    """
    
    # 1. ensemble_predict 帶 window_size 參數
    # (如果已存在, 跳過)
    
    # 2. _blend_predictions 混合方法
    # @staticmethod
    # def _blend_predictions(predictions, weights):
    #     """將多個預測結果按權重混合"""
    #     blended_numbers = {}
    #     for pred, weight in zip(predictions, weights):
    #         for num in pred['numbers']:
    #             blended_numbers[num] = blended_numbers.get(num, 0) + weight
    #     
    #     # 選擇權重最高的 6 個號碼
    #     sorted_nums = sorted(blended_numbers.items(), key=lambda x: x[1], reverse=True)
    #     final_numbers = [num for num, _ in sorted_nums[:6]]
    #     
    #     # 特別號使用多數投票
    #     special_votes = {}
    #     for pred in predictions:
    #         s = pred['special']
    #         special_votes[s] = special_votes.get(s, 0) + 1
    #     final_special = max(special_votes, key=special_votes.get)
    #     
    #     return {'numbers': final_numbers, 'special': final_special}
    
    # 3. anti_consensus_predict
    # (如果已存在, 跳過)
    
    print("檢查以上方法是否在 unified_predictor.py 中實現")

# ============================================================================
# 步驟 5: 使用示例
# ============================================================================

def example_usage():
    """使用示例"""
    
    from database import db_manager
    from common import get_lottery_rules
    
    # 初始化
    lottery_type = 'POWER_LOTTO'
    all_draws = db_manager.get_all_draws(lottery_type)
    lottery_rules = get_lottery_rules(lottery_type)
    
    # 執行推薦配置的回測
    result = run_optimized_backtest(
        PowerLottoOptimizedConfig.BET_CONFIG_4_OPTIMIZED,
        all_draws,
        lottery_rules
    )
    
    # 輸出結果
    print(f"\n{'='*60}")
    print(f"配置: {result['config_name']}")
    print(f"{'='*60}")
    print(f"測試期數: {result['total_tests']}")
    print(f"命中次數: {result['hit_count']}")
    print(f"命中率: {result['hit_rate']:.2%}")
    print(f"特別號命中: {result['special_hits']}/{result['total_tests']}")
    print(f"成本效率: {result['cost_efficiency']:.2%} per $100")
    print(f"\n匹配分布:")
    for matches, count in result['match_distribution'].items():
        print(f"  {matches}個: {count}次 ({count/result['total_tests']*100:.1f}%)")
    
    # 檢查是否達成目標
    if result['hit_rate'] >= 0.20:
        print(f"\n✅ 達成目標! 命中率 {result['hit_rate']:.2%} >= 20%")
    elif result['hit_rate'] >= 0.17:
        print(f"\n⚠️  接近目標! 命中率 {result['hit_rate']:.2%}, 可考慮微調")
    else:
        print(f"\n❌ 未達成目標! 命中率 {result['hit_rate']:.2%}, 需要重新評估")

# ============================================================================
# 步驟 6: 修改建議 (如何集成到現有代碼)
# ============================================================================

"""
在 backtest_power_2025.py 中的修改:

1. 導入優化配置
   from power_lotto_optimization_config import PowerLottoOptimizedConfig

2. 選擇配置
   config = PowerLottoOptimizedConfig.BET_CONFIG_4_OPTIMIZED

3. 執行回測
   result = run_optimized_backtest(config, all_draws, lottery_rules)

4. 輸出報告
   with open('report_4bet_optimized.md', 'w') as f:
       f.write(f"# 威力彩 4注優化驗證報告\n")
       f.write(f"## 命中率: {result['hit_rate']:.2%}\n")
       f.write(f"## 成本: ${result['cost']}\n")
       f.write(f"## 期望成本/中獎: ${result['cost'] / (result['hit_rate'] if result['hit_rate'] > 0 else 1)}\n")
"""

# ============================================================================
# 核心指標檢查清單
# ============================================================================

CHECKLIST = {
    '需求驗證': {
        '✅ 4注配置存在': False,
        '✅ Ensemble 支持窗口參數': False,
        '✅ 混合方法可實現': False,
        '✅ 特別號優化已啟用': False,
    },
    '回測驗證': {
        '✅ 無數據洩漏': False,
        '✅ 使用 2025 年全數據': False,
        '✅ 命中率計算正確': False,
        '✅ 特別號統計正確': False,
    },
    '結果評估': {
        '✅ 達成 20%+': False,
        '✅ 成本合理': False,
        '✅ 方法多樣化': False,
        '✅ 相關性低': False,
    }
}

if __name__ == '__main__':
    # 執行示例
    example_usage()
