#!/usr/bin/env python3
"""
深入測試 OptimizedEnsemblePredictor 的表現
驗證 Gemini 的說法：是否能命中 [1, 39]
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules
from models.unified_predictor import prediction_engine
from models.optimized_ensemble import OptimizedEnsemblePredictor

def main():
    print("="*80)
    print("🔬 OptimizedEnsemblePredictor 深度測試")
    print("="*80)

    # 目標號碼
    target_numbers = [1, 3, 12, 33, 39, 41]
    target_special = 29

    print(f"\n🎯 目標號碼: {sorted(target_numbers)} + 特別號 {target_special}")
    print(f"   奇數: {[n for n in target_numbers if n % 2 == 1]} (5個)")
    print(f"   偶數: {[n for n in target_numbers if n % 2 == 0]} (1個)")

    # 載入數據
    db_path = os.path.join(os.path.dirname(__file__), 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path=db_path)
    draws = db.get_all_draws('BIG_LOTTO')
    rules = get_lottery_rules('BIG_LOTTO')

    print(f"\n📊 數據庫: {len(draws)} 期大樂透數據")

    # 初始化 OptimizedEnsemblePredictor
    print("\n🔧 初始化 OptimizedEnsemblePredictor...")
    optimizer = OptimizedEnsemblePredictor(prediction_engine)

    # 測試不同的配置
    test_configs = [
        {'window': 50, 'backtest': 20, 'name': '極短窗口'},
        {'window': 100, 'backtest': 30, 'name': '短窗口'},
        {'window': 200, 'backtest': 50, 'name': '中窗口'},
        {'window': 300, 'backtest': 50, 'name': '標準窗口'},
        {'window': 400, 'backtest': 50, 'name': '長窗口'},
        {'window': 500, 'backtest': 50, 'name': '極長窗口'},
    ]

    print("\n" + "="*80)
    print("📈 測試不同訓練窗口大小")
    print("="*80)

    best_result = None
    best_match_count = 0

    for config in test_configs:
        window = config['window']
        backtest = config['backtest']
        name = config['name']

        print(f"\n🔹 {name} (訓練: {window}期, 回測: {backtest}期)")
        print("-" * 80)

        history = draws[:window]

        try:
            # 執行預測
            result = optimizer.predict(history, rules, backtest_periods=backtest)

            # 檢查雙注結果
            bet1 = result.get('numbers', [])
            bet2 = result.get('bet2', [])
            special1 = result.get('special')
            special2 = result.get('special2')

            # 計算匹配
            matches1 = set(bet1) & set(target_numbers)
            matches2 = set(bet2) & set(target_numbers)

            # 檢查是否命中 [1, 39]
            has_1_39_bet1 = (1 in bet1 and 39 in bet1)
            has_1_39_bet2 = (1 in bet2 and 39 in bet2)

            # 檢查是否命中 [1, 41]
            has_1_41_bet1 = (1 in bet1 and 41 in bet1)
            has_1_41_bet2 = (1 in bet2 and 41 in bet2)

            print(f"   第一注: {sorted(bet1)} + 特別號 {special1}")
            print(f"     匹配 {len(matches1)}/6: {sorted(list(matches1))}")
            print(f"     [1,39]組合: {'✅' if has_1_39_bet1 else '❌'}")
            print(f"     [1,41]組合: {'✅' if has_1_41_bet1 else '❌'}")
            print(f"     置信度: {result.get('confidence', 0):.2%}")

            print(f"\n   第二注: {sorted(bet2)} + 特別號 {special2}")
            print(f"     匹配 {len(matches2)}/6: {sorted(list(matches2))}")
            print(f"     [1,39]組合: {'✅' if has_1_39_bet2 else '❌'}")
            print(f"     [1,41]組合: {'✅' if has_1_41_bet2 else '❌'}")
            print(f"     置信度: {result.get('confidence2', 0):.2%}")

            # 記錄最佳結果
            total_matches = max(len(matches1), len(matches2))
            if total_matches > best_match_count:
                best_match_count = total_matches
                best_result = {
                    'config': config,
                    'bet1': bet1,
                    'bet2': bet2,
                    'matches1': matches1,
                    'matches2': matches2,
                    'has_1_39': has_1_39_bet1 or has_1_39_bet2,
                    'has_1_41': has_1_41_bet1 or has_1_41_bet2
                }

        except Exception as e:
            print(f"   ❌ 執行失敗: {e}")
            import traceback
            traceback.print_exc()

    # 顯示最佳結果
    if best_result:
        print("\n" + "="*80)
        print("🏆 最佳表現總結")
        print("="*80)

        print(f"\n配置: {best_result['config']['name']}")
        print(f"訓練窗口: {best_result['config']['window']} 期")
        print(f"回測期數: {best_result['config']['backtest']} 期")

        print(f"\n最佳匹配數: {best_match_count}/6")
        print(f"第一注匹配: {sorted(list(best_result['matches1']))}")
        print(f"第二注匹配: {sorted(list(best_result['matches2']))}")

        print(f"\n✅ Gemini 聲稱的 [1, 39] 組合: {'是' if best_result['has_1_39'] else '否'}")
        print(f"✅ 實際出現的 [1, 41] 組合: {'是' if best_result['has_1_41'] else '否'}")

    # 測試大樂透推薦權重配置
    print("\n" + "="*80)
    print("📊 大樂透推薦權重分析")
    print("="*80)

    big_lotto_weights = OptimizedEnsemblePredictor.RECOMMENDED_WEIGHTS.get('BIG_LOTTO')
    print(f"\n大樂透專用權重配置 (前10):")
    sorted_weights = sorted(big_lotto_weights.items(), key=lambda x: x[1], reverse=True)
    for name, weight in sorted_weights[:10]:
        print(f"  {name:<25}: {weight:.1%}")

    # 結論
    print("\n" + "="*80)
    print("💡 測試結論")
    print("="*80)

    if best_result:
        if best_result['has_1_39']:
            print("\n✅ Gemini 的說法正確！")
            print("   OptimizedEnsemblePredictor 確實能命中 [1, 39] 組合")
        elif best_result['has_1_41']:
            print("\n⚠️  Gemini 的說法部分正確！")
            print("   OptimizedEnsemblePredictor 命中的是 [1, 41]，而非 [1, 39]")
        else:
            print("\n❌ Gemini 的說法不正確！")
            print(f"   OptimizedEnsemblePredictor 最多匹配 {best_match_count}/6")
            print(f"   未能命中 [1, 39] 或 [1, 41] 組合")

    print("\n" + "="*80)

if __name__ == '__main__':
    main()
