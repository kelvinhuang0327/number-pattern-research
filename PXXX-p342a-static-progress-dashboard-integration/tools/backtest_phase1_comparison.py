#!/usr/bin/env python3
"""
Phase 1 Backtest Verification Script
嚴格回測：確保零資料洩漏 (Zero Data Leakage)

比較目標：
- 舊系統：硬性300懲罰 (consecutive_3 → +300 penalty)
- 新系統：漸進式懲罰 (consecutive_3 → score × 0.4)

驗證原則：
1. 預測第N期時，只能使用第1~N-1期的資料
2. 絕對不能看到第N期的實際開獎號碼
3. 配置在預測前設定，不能中途更改
"""
import sys
import os
import json
from collections import defaultdict, Counter

# Add project paths
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules
from models.multi_bet_optimizer import MultiBetOptimizer
from models.unified_predictor import prediction_engine
import numpy as np

class NpEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super(NpEncoder, self).default(obj)


class BacktestSystem:
    """回測系統 - 支援新舊配置切換"""
    
    def __init__(self, use_new_system=True):
        self.use_new_system = use_new_system
        self.optimizer = MultiBetOptimizer()
        
        # 臨時修改配置
        if not use_new_system:
            self._apply_old_config()
        else:
            self._apply_new_config()
    
    def _apply_old_config(self):
        """套用舊系統配置（硬懲罰）"""
        # 修改 config_loader 的返回值
        try:
            from config_loader import config
            # 強制使用舊系統
            if hasattr(config, '_config') and config._config:
                config._config['consecutive_filter']['use_gradual_penalties'] = False
                config._config['strategy_weights']['gap_analysis'] = 0.6
                config._config['strategy_weights']['gap_hunter'] = 0.6
        except:
            pass
    
    def _apply_new_config(self):
        """套用新系統配置（漸進懲罰）"""
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
            # 直接使用 optimizer 的 generate_diversified_bets 方法
            # 它會內部處理所有策略和分數計算
            result = self.optimizer.generate_diversified_bets(
                draws=history,
                lottery_rules=lottery_rules,
                num_bets=7,
                meta_config=None
            )
            
            return result.get('bets', [])
        
        except Exception as e:
            print(f"預測失敗: {e}")
            import traceback
            traceback.print_exc()
            return None


def rigorous_backtest(test_periods=50, use_new_system=True):
    """
    嚴格回測函數
    
    Args:
        test_periods: 測試期數
        use_new_system: True=新系統, False=舊系統
    
    Returns:
        回測結果字典
    """
    print(f"\n{'='*70}")
    system_name = "新系統 (漸進懲罰)" if use_new_system else "舊系統 (硬懲罰300)"
    print(f"回測系統: {system_name}")
    print(f"測試期數: {test_periods}")
    print(f"{'='*70}\n")
    
    # 載入數據
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path=db_path)
    lottery_type = 'BIG_LOTTO'
    rules = get_lottery_rules(lottery_type)
    
    # 取得所有開獎（新→舊）
    all_draws = db.get_all_draws(lottery_type)
    
    if len(all_draws) < test_periods + 100:
        print(f"⚠️  數據不足：需要至少 {test_periods + 100} 期，實際 {len(all_draws)} 期")
        return None
    
    # 初始化回測系統
    backtest_sys = BacktestSystem(use_new_system=use_new_system)
    
    # 回測結果
    results = []
    consecutive_coverage = []  # 追蹤連號覆蓋情況
    
    for i in range(test_periods):
        # 目標期數（第i期）
        target = all_draws[i]
        target_draw = target['draw']
        target_numbers = set(target['numbers'])
        
        # ⚠️ 關鍵：歷史數據只包含第i+1期之後的資料
        # 確保預測第i期時，絕對看不到第i期的數據
        history = all_draws[i + 1:]  # 從第i+1期開始往後
        
        if len(history) < 100:
            print(f"⚠️  第{target_draw}期：歷史數據不足100期，跳過")
            continue
        
        # 生成預測
        bets = backtest_sys.predict_7bets(history, rules)
        
        if not bets:
            print(f"❌ 第{target_draw}期：預測失敗")
            continue
        
        # 分析結果
        all_predicted = set()
        best_match = 0
        best_bet = None
        
        for bet in bets:
            bet_numbers = set(bet['numbers'] if isinstance(bet, dict) else bet)
            all_predicted.update(bet_numbers)
            matches = len(bet_numbers & target_numbers)
            if matches > best_match:
                best_match = matches
                best_bet = bet_numbers
        
        # 檢查是否覆蓋了連號
        target_sorted = sorted(target_numbers)
        has_consecutive = False
        max_consecutive_in_target = 1
        consecutive_count = 0
        
        for j in range(len(target_sorted) - 1):
            if target_sorted[j+1] == target_sorted[j] + 1:
                consecutive_count += 1
                max_consecutive_in_target = max(max_consecutive_in_target, consecutive_count + 1)
                has_consecutive = True
            else:
                consecutive_count = 0
        
        # 檢查預測是否包含連號
        predicted_sorted = sorted(all_predicted)
        max_consecutive_predicted = 1
        consecutive_count_p = 0
        for j in range(len(predicted_sorted) - 1):
            if predicted_sorted[j+1] == predicted_sorted[j] + 1:
                consecutive_count_p += 1
                max_consecutive_predicted = max(max_consecutive_predicted, consecutive_count_p + 1)
            else:
                consecutive_count_p = 0
        
        if has_consecutive:
            consecutive_coverage.append({
                'draw': target_draw,
                'target_consecutive': max_consecutive_in_target,
                'predicted_consecutive': max_consecutive_predicted,
                'covered': max_consecutive_in_target <= max_consecutive_predicted
            })
        
        # 記錄結果
        win = best_match >= 3
        result = {
            'draw': target_draw,
            'date': target.get('date', ''),
            'target': sorted(target_numbers),
            'total_covered': len(all_predicted),
            'best_match': best_match,
            'best_bet': sorted(best_bet) if best_bet else [],
            'win': win,
            'has_consecutive': has_consecutive,
            'max_consecutive': max_consecutive_in_target
        }
        results.append(result)
        
        # 進度報告
        if (i + 1) % 10 == 0:
            current_wins = sum(1 for r in results if r['win'])
            current_rate = current_wins / len(results) * 100 if results else 0
            print(f"進度: {i+1}/{test_periods}, Match-3+率: {current_rate:.2f}%")
    
    # 統計分析
    total_tests = len(results)
    total_wins = sum(1 for r in results if r['win'])
    win_rate = total_wins / total_tests * 100 if total_tests > 0 else 0
    
    # 匹配分佈
    match_dist = Counter(r['best_match'] for r in results)
    
    # 連號覆蓋統計
    consecutive_stats = {
        'total_with_consecutive': len(consecutive_coverage),
        'covered_count': sum(1 for c in consecutive_coverage if c['covered']),
        'coverage_rate': sum(1 for c in consecutive_coverage if c['covered']) / len(consecutive_coverage) * 100 if consecutive_coverage else 0
    }
    
    return {
        'system': system_name,
        'test_periods': test_periods,
        'total_tests': total_tests,
        'total_wins': total_wins,
        'win_rate': win_rate,
        'match_distribution': dict(match_dist),
        'consecutive_stats': consecutive_stats,
        'consecutive_details': consecutive_coverage,
        'results': results
    }


def compare_systems(test_periods=50):
    """比較新舊系統"""
    print("\n" + "="*70)
    print("Phase 1 改進效果驗證 - 新舊系統比較")
    print("="*70)
    
    # 回測舊系統
    print("\n[1/2] 回測舊系統...")
    old_results = rigorous_backtest(test_periods=test_periods, use_new_system=False)
    
    # 回測新系統
    print("\n[2/2] 回測新系統...")
    new_results = rigorous_backtest(test_periods=test_periods, use_new_system=True)
    
    if not old_results or not new_results:
        print("\n❌ 回測失敗")
        return
    
    # 比較結果
    print("\n" + "="*70)
    print("回測結果比較")
    print("="*70)
    
    print(f"\n{'指標':<30} {'舊系統':>15} {'新系統':>15} {'變化':>10}")
    print("-"*70)
    
    # Match-3+ 率
    old_rate = old_results['win_rate']
    new_rate = new_results['win_rate']
    delta = new_rate - old_rate
    delta_str = f"+{delta:.2f}%" if delta > 0 else f"{delta:.2f}%"
    print(f"{'Match-3+ 率':<30} {old_rate:>14.2f}% {new_rate:>14.2f}% {delta_str:>10}")
    
    # 連號覆蓋
    old_consec = old_results['consecutive_stats']['coverage_rate']
    new_consec = new_results['consecutive_stats']['coverage_rate']
    consec_delta = new_consec - old_consec
    consec_delta_str = f"+{consec_delta:.1f}%" if consec_delta > 0 else f"{consec_delta:.1f}%"
    print(f"{'連號覆蓋率':<30} {old_consec:>14.1f}% {new_consec:>14.1f}% {consec_delta_str:>10}")
    
    # 匹配分佈
    print(f"\n{'匹配數分佈:':<30}")
    for i in range(7):
        old_count = old_results['match_distribution'].get(i, 0)
        new_count = new_results['match_distribution'].get(i, 0)
        old_pct = old_count / old_results['total_tests'] * 100
        new_pct = new_count / new_results['total_tests'] * 100
        print(f"  Match-{i}: {old_count:>3}期({old_pct:>5.1f}%)  →  {new_count:>3}期({new_pct:>5.1f}%)")
    
    # 結論
    print("\n" + "="*70)
    print("結論")
    print("="*70)
    
    if delta > 0:
        print(f"✅ 新系統 Match-3+ 率提升 {delta:.2f}%")
    elif delta < -0.5:
        print(f"⚠️  新系統 Match-3+ 率下降 {abs(delta):.2f}%")
    else:
        print(f"➖ 新系統 Match-3+ 率變化不顯著 ({delta:.2f}%)")
    
    if consec_delta > 5:
        print(f"✅ 連號覆蓋率大幅提升 {consec_delta:.1f}% (目標達成)")
    elif consec_delta > 0:
        print(f"➕ 連號覆蓋率小幅提升 {consec_delta:.1f}%")
    
    # 儲存結果
    output_file = 'tools/phase1_backtest_results.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'old_system': old_results,
            'new_system': new_results,
            'comparison': {
                'match3_delta': delta,
                'consecutive_coverage_delta': consec_delta
            }
        }, f, indent=2, ensure_ascii=False, cls=NpEncoder)
    
    print(f"\n📊 詳細結果已儲存至: {output_file}")
    print("="*70 + "\n")


if __name__ == '__main__':
    # 執行比較
    compare_systems(test_periods=50)
