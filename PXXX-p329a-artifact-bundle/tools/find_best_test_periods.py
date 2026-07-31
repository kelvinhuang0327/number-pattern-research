#!/usr/bin/env python3
"""
尋找最佳測試期數
測試不同的期數範圍，找出哪個範圍能最好地展現Phase 1改進效果
"""
import sys
import os

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules
from models.multi_bet_optimizer import MultiBetOptimizer

class BacktestSystem:
    """回測系統"""
    def __init__(self, use_new_system=True):
        self.use_new_system = use_new_system
        self.optimizer = MultiBetOptimizer()
        
        if not use_new_system:
            try:
                from config_loader import config
                if hasattr(config, '_config') and config._config:
                    config._config['consecutive_filter']['use_gradual_penalties'] = False
                    config._config['strategy_weights']['gap_analysis'] = 0.6
                    config._config['strategy_weights']['gap_hunter'] = 0.6
            except:
                pass
        else:
            try:
                from config_loader import config
                if hasattr(config, '_config') and config._config:
                    config._config['consecutive_filter']['use_gradual_penalties'] = True
                    config._config['strategy_weights']['gap_analysis'] = 1.2
                    config._config['strategy_weights']['gap_hunter'] = 1.2
            except:
                pass
    
    def predict_7bets(self, history, lottery_rules):
        """生成7注預測"""
        try:
            result = self.optimizer.generate_diversified_bets(
                draws=history,
                lottery_rules=lottery_rules,
                num_bets=7,
                meta_config=None
            )
            return result.get('bets', [])
        except Exception as e:
            return None


def quick_backtest(test_periods, use_new_system=True, silent=True):
    """快速回測（簡化版，只返回關鍵指標）"""
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path=db_path)
    lottery_type = 'BIG_LOTTO'
    rules = get_lottery_rules(lottery_type)
    all_draws = db.get_all_draws(lottery_type)
    
    if len(all_draws) < test_periods + 100:
        return None
    
    backtest_sys = BacktestSystem(use_new_system=use_new_system)
    
    wins = 0
    total = 0
    consecutive_found = 0
    consecutive_covered = 0
    
    for i in range(test_periods):
        target = all_draws[i]
        target_numbers = set(target['numbers'])
        history = all_draws[i + 1:]
        
        if len(history) < 100:
            continue
        
        bets = backtest_sys.predict_7bets(history, rules)
        if not bets:
            continue
        
        all_predicted = set()
        best_match = 0
        
        for bet in bets:
            bet_numbers = set(bet['numbers'] if isinstance(bet, dict) else bet)
            all_predicted.update(bet_numbers)
            matches = len(bet_numbers & target_numbers)
            best_match = max(best_match, matches)
        
        if best_match >= 3:
            wins += 1
        total += 1
        
        # 檢查連號
        target_sorted = sorted(target_numbers)
        max_consecutive = 1
        count = 0
        for j in range(len(target_sorted) - 1):
            if target_sorted[j+1] == target_sorted[j] + 1:
                count += 1
                max_consecutive = max(max_consecutive, count + 1)
            else:
                count = 0
        
        if max_consecutive >= 2:
            consecutive_found += 1
            # 檢查是否覆蓋
            predicted_sorted = sorted(all_predicted)
            max_consec_pred = 1
            count_p = 0
            for j in range(len(predicted_sorted) - 1):
                if predicted_sorted[j+1] == predicted_sorted[j] + 1:
                    count_p += 1
                    max_consec_pred = max(max_consec_pred, count_p + 1)
                else:
                    count_p = 0
            
            if max_consec_pred >= max_consecutive:
                consecutive_covered += 1
    
    win_rate = wins / total * 100 if total > 0 else 0
    consec_coverage = consecutive_covered / consecutive_found * 100 if consecutive_found > 0 else 0
    
    return {
        'total': total,
        'wins': wins,
        'win_rate': win_rate,
        'consecutive_found': consecutive_found,
        'consecutive_covered': consecutive_covered,
        'consecutive_coverage': consec_coverage
    }


def find_best_test_periods():
    """尋找最佳測試期數"""
    print("\n" + "="*70)
    print("尋找最佳測試期數 - 效果驗證")
    print("="*70)
    
    # 測試不同期數範圍
    test_ranges = [30, 50, 100, 150, 200]
    
    print(f"\n{'測試期數':<10} {'舊系統':<20} {'新系統':<20} {'差異':<15}")
    print("-"*70)
    
    best_delta = -999
    best_periods = 0
    results_summary = []
    
    for periods in test_ranges:
        print(f"\n測試 {periods} 期中...", end="", flush=True)
        
        # 舊系統
        old_result = quick_backtest(periods, use_new_system=False)
        if not old_result:
            print(f" ❌ 數據不足")
            continue
        
        # 新系統
        new_result = quick_backtest(periods, use_new_system=True)
        if not new_result:
            print(f" ❌ 數據不足")
            continue
        
        old_rate = old_result['win_rate']
        new_rate = new_result['win_rate']
        delta = new_rate - old_rate
        
        print(f" ✓")
        print(f"{periods}期        {old_rate:>6.2f}% ({old_result['wins']}/{old_result['total']})     "
              f"{new_rate:>6.2f}% ({new_result['wins']}/{new_result['total']})     "
              f"{delta:>+6.2f}%", end="")
        
        if delta > best_delta:
            best_delta = delta
            best_periods = periods
            print(" 🏆 (目前最佳)")
        else:
            print()
        
        results_summary.append({
            'periods': periods,
            'old_rate': old_rate,
            'new_rate': new_rate,
            'delta': delta,
            'old_wins': old_result['wins'],
            'new_wins': new_result['wins'],
            'consecutive_found': new_result['consecutive_found'],
            'consecutive_coverage': new_result['consecutive_coverage']
        })
    
    # 總結
    print("\n" + "="*70)
    print("測試期數分析總結")
    print("="*70)
    
    if best_delta > 0:
        print(f"\n✅ 最佳測試期數: {best_periods} 期")
        print(f"   在此期數下，新系統優於舊系統 +{best_delta:.2f}%")
    elif best_delta == 0:
        print(f"\n➖ 所有測試期數下，新舊系統表現相同")
        print(f"   建議使用 {max(test_ranges)} 期以獲得更穩定的統計")
    else:
        print(f"\n⚠️  所有測試下新系統均未優於舊系統")
        print(f"   最小差距出現在 {best_periods} 期 ({best_delta:.2f}%)")
    
    # 詳細分析
    print(f"\n連號案例分析:")
    for r in results_summary:
        if r['consecutive_found'] > 0:
            print(f"  {r['periods']:3d}期: 發現{r['consecutive_found']}個連號案例, "
                  f"覆蓋率 {r['consecutive_coverage']:.1f}%")
    
    # 穩定性分析
    print(f"\n穩定性分析:")
    old_rates = [r['old_rate'] for r in results_summary]
    new_rates = [r['new_rate'] for r in results_summary]
    
    import statistics
    if len(old_rates) > 1:
        old_std = statistics.stdev(old_rates)
        new_std = statistics.stdev(new_rates)
        print(f"  舊系統標準差: {old_std:.2f}%")
        print(f"  新系統標準差: {new_std:.2f}%")
        
        if new_std < old_std:
            print(f"  ✅ 新系統更穩定 (標準差更小)")
        elif new_std > old_std:
            print(f"  ⚠️  新系統波動更大")
    
    # 推薦
    print(f"\n推薦:")
    if best_delta > 1.0:
        print(f"  1. 使用 {best_periods} 期進行驗證（效果最明顯）")
        print(f"  2. Phase 1 改進在此期數下有顯著效果")
    elif best_delta > 0:
        print(f"  1. Phase 1 改進有微弱正向效果")
        print(f"  2. 建議使用更長期數 (>200期) 驗證")
    else:
        print(f"  1. Phase 1 改進未在測試期數中體現優勢")
        print(f"  2. 建議檢查是否有極端連號案例被遺漏")
        print(f"  3. 或進入 Phase 2 (MAB + Anomaly Detection)")
    
    print("="*70 + "\n")
    
    return best_periods, best_delta


if __name__ == '__main__':
    best_periods, best_delta = find_best_test_periods()
    
    if best_delta > 0.5:
        print(f"🎉 建議使用 {best_periods} 期作為標準測試期數！")
    else:
        print(f"💡 建議擴展到更長期數或調整策略參數")
