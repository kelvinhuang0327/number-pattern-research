#!/usr/bin/env python3
"""
大樂透雙注預測 (Phase 2 升級版)

整合策略:
1. Auto Optimizer V2 (投票集成) - 結合熱號、頻率、貝葉斯等多模型投票
2. Zone Balance (500期) - 長期區間平衡保底

CLI 參數:
--phase: 1 或 2 (預設 2)
--optimize: 是否啟用權重優化 (預設 True)
--backtest: 執行快速回測驗證
"""
import sys
import os
import argparse
from collections import Counter

# Add project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from models.unified_predictor import UnifiedPredictionEngine
from database import DatabaseManager
from common import get_lottery_rules
from tools.hot_cooccurrence_analyzer import HotCooccurrenceAnalyzer
from tools.auto_optimizer_v2 import IntegratedPredictor


def run_phase1_prediction(args):
    """執行 Phase 1 預測 (熱號+共現)"""
    print("=" * 80)
    print("大樂透雙注預測 (Phase 1 熱號+共現)")
    print("=" * 80)
    
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path=db_path)
    lottery_type = 'BIG_LOTTO'
    draws_desc = db.get_all_draws(lottery_type=lottery_type)
    draws_asc = list(reversed(draws_desc))
    rules = get_lottery_rules(lottery_type)
    
    engine = UnifiedPredictionEngine()
    analyzer = HotCooccurrenceAnalyzer(lottery_type)
    
    # Bet 1
    hot_freq = analyzer.get_hot_numbers(draws_asc, 50)
    hot_nums = [num for num, _ in hot_freq]
    co_matrix = analyzer.build_cooccurrence_matrix(draws_asc, 100)
    nums_1 = analyzer.apply_cooccurrence_rules(hot_nums, co_matrix, rules['pickCount'])
    
    # Bet 2
    try:
        result_2 = engine.zone_balance_predict(draws_asc[-500:], rules)
        nums_2 = sorted(result_2['numbers'])
    except:
        nums_2 = []
        
    return nums_1, nums_2


def run_phase2_prediction(args):
    """執行 Phase 2 預測 (投票集成)"""
    print("=" * 80)
    print("大樂透雙注預測 (Phase 2 投票集成升級版)")
    print(f"配置: 權重優化={'啟用' if args.optimize else '使用預設'}")
    print("=" * 80)
    
    predictor = IntegratedPredictor('BIG_LOTTO')
    
    # 使用雙注預測模式
    result = predictor.predict_double_bet(optimize_weights=args.optimize)
    
    # 顯示詳細權重
    print("\n📊 策略權重分佈:")
    for name, w in sorted(result['weights'].items(), key=lambda x: x[1], reverse=True):
        print(f"   {name}: {w:.1%}")
    if result.get('consensus'):
        print(f"\n💡 共識號碼: {result['consensus']}")
        
    return result['bet1'], result['bet2']


def run_phase3_prediction(args):
    """執行 Phase 3 預測 (遺傳優化 + 負向排除)"""
    use_kill = not getattr(args, 'no_kill', False)
    mode_name = "Jackpot Mode (No Kill)" if not use_kill else "High Win Rate Mode (Kill-5)"
    
    print("=" * 80)
    print("大樂透雙注預測 (Phase 3 深度優化版)")
    print(f"配置: 遺傳算法優化 + {mode_name}")
    print("=" * 80)
    
    predictor = IntegratedPredictor('BIG_LOTTO')
    
    # 使用雙注預測模式 (Phase 3)
    result = predictor.predict_double_bet(
        optimize_weights=True,
        use_genetic=True,
        use_kill=use_kill,
        kill_count=5  # Default to conservative Kill-5
    )
    
    # 顯示詳細權重
    print("\n📊 策略權重分佈 (遺傳優化):")
    for name, w in sorted(result['weights'].items(), key=lambda x: x[1], reverse=True):
        print(f"   {name}: {w:.1%}")
    
    if result.get('kill_list'):
        print(f"\n🔪 排除號碼 (Kill-10): {result['kill_list']}")
        
    if result.get('consensus'):
        print(f"💡 共識號碼: {result['consensus']}")
        
    return result['bet1'], result['bet2']


def main():
    parser = argparse.ArgumentParser(description='大樂透雙注預測 (Phase 1/2/3)')
    parser.add_argument('--phase', type=int, default=3, choices=[1, 2, 3],
                        help='使用 Phase 1, 2 或 3 (預設 3)')
    parser.add_argument('--optimize', action='store_true', default=True,
                        help='啟用權重優化')
    parser.add_argument('--no-optimize', action='store_false', dest='optimize',
                        help='停用權重優化')
    parser.add_argument('--no-kill', action='store_true',
                        help='停用負向排除 (Jackpot Mode)')
    
    args = parser.parse_args()
    
    if args.phase == 1:
        bet1, bet2 = run_phase1_prediction(args)
        strategy_name = "Phase 1 (熱號+共現)"
    elif args.phase == 2:
        bet1, bet2 = run_phase2_prediction(args)
        strategy_name = "Phase 2 (投票集成)"
    else:
        bet1, bet2 = run_phase3_prediction(args)
        if args.no_kill:
            strategy_name = "Phase 3 (Jackpot Mode)"
        else:
            strategy_name = "Phase 3 (High Win Rate)"
    
    # 輸出結果
    print("\n" + "=" * 80)
    print(f"🎯 最終推薦 ({strategy_name}):")
    print(f"   第一注: {bet1}")
    print(f"   第二注: {bet2}")
    
    # 分析
    overlap = sorted(list(set(bet1) & set(bet2)))
    combined = sorted(list(set(bet1) | set(bet2)))
    
    print("-" * 80)
    print(f"重疊號碼 ({len(overlap)}): {overlap}")
    print(f"總覆蓋 ({len(combined)}): {combined}")
    if overlap:
        print("💡 建議: 重疊號碼可作為核心膽碼")
    print("=" * 80)


if __name__ == '__main__':
    main()
