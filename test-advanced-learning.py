#!/usr/bin/env python3
"""
進階自動學習系統測試腳本
用於驗證多階段優化和自適應窗口優化的效果
"""
import asyncio
import sys
import os

# 添加項目路徑
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lottery-api'))

from models.advanced_auto_learning import AdvancedAutoLearningEngine
from models.database import Database

async def progress_callback(progress):
    """進度回調函數"""
    print(f"進度: {progress:.1f}%", end='\r')

async def test_multi_stage_optimization():
    """測試多階段優化"""
    print("=" * 60)
    print("🚀 測試多階段優化 (Multi-Stage Optimization)")
    print("=" * 60)

    # 初始化引擎
    engine = AdvancedAutoLearningEngine()

    # 從數據庫載入數據
    db = Database()
    await db.connect()

    # 獲取大樂透數據
    draws = await db.get_all_draws(lottery_type='BIG_LOTTO')
    print(f"\n📊 載入數據: {len(draws)} 期")

    if len(draws) < 100:
        print("❌ 數據不足（至少需要 100 期）")
        await db.close()
        return

    # 轉換數據格式
    history = [
        {
            'numbers': draw['numbers'],
            'special': draw['special'],
            'date': draw['date']
        }
        for draw in draws
    ]

    # 彩票規則
    lottery_rules = {
        'pickCount': 6,
        'minNumber': 1,
        'maxNumber': 49
    }

    print("\n開始多階段優化...")
    print("-" * 60)

    # 執行優化
    result = await engine.multi_stage_optimize(
        history=history,
        lottery_rules=lottery_rules,
        progress_callback=progress_callback
    )

    await db.close()

    # 輸出結果
    print("\n")
    print("=" * 60)
    print("✅ 優化完成！")
    print("=" * 60)

    if result['success']:
        print(f"\n📊 最終結果:")
        print(f"  最佳適應度: {result['best_fitness']:.4f} ({result['best_fitness']*100:.2f}%)")
        print(f"  優化方法: {result['method']}")

        print(f"\n📈 各階段結果:")
        for stage in result['stage_results']:
            print(f"  {stage['stage']:10s}: {stage['best_fitness']:.4f} ({stage['best_fitness']*100:.2f}%)")

        print(f"\n⚙️  最佳配置:")
        best_config = result['best_config']
        print(f"  頻率權重: {best_config.get('frequency_weight', 0):.3f}")
        print(f"  冷熱權重: {best_config.get('hot_cold_weight', 0):.3f}")
        print(f"  趨勢權重: {best_config.get('trend_weight', 0):.3f}")
        print(f"  近期窗口: {best_config.get('recent_window', 0)} 期")
        print(f"  長期窗口: {best_config.get('long_window', 0)} 期")

        # 計算提升幅度
        baseline = 0.0361  # 目前基準線
        improvement = (result['best_fitness'] - baseline) / baseline * 100
        print(f"\n🎯 相比基準線 (3.61%) 提升: {improvement:.1f}%")

    else:
        print(f"\n❌ 優化失敗: {result.get('error', 'Unknown')}")

async def test_adaptive_window_optimization():
    """測試自適應窗口優化"""
    print("\n")
    print("=" * 60)
    print("🔍 測試自適應窗口優化 (Adaptive Window)")
    print("=" * 60)

    # 初始化引擎
    engine = AdvancedAutoLearningEngine()

    # 從數據庫載入數據
    db = Database()
    await db.connect()

    draws = await db.get_all_draws(lottery_type='BIG_LOTTO')
    print(f"\n📊 載入數據: {len(draws)} 期")

    if len(draws) < 100:
        print("❌ 數據不足（至少需要 100 期）")
        await db.close()
        return

    # 轉換數據格式
    history = [
        {
            'numbers': draw['numbers'],
            'special': draw['special'],
            'date': draw['date']
        }
        for draw in draws
    ]

    lottery_rules = {
        'pickCount': 6,
        'minNumber': 1,
        'maxNumber': 49
    }

    print("\n開始自適應窗口優化...")
    print("-" * 60)

    # 執行優化
    result = await engine.adaptive_window_optimize(
        history=history,
        lottery_rules=lottery_rules,
        progress_callback=progress_callback
    )

    await db.close()

    # 輸出結果
    print("\n")
    print("=" * 60)
    print("✅ 優化完成！")
    print("=" * 60)

    if result['success']:
        print(f"\n📊 最終結果:")
        print(f"  最佳適應度: {result['best_fitness']:.4f} ({result['best_fitness']*100:.2f}%)")
        print(f"  最佳窗口大小: {result['best_window_size']} 期")
        print(f"  優化方法: {result['method']}")

        baseline = 0.0361
        improvement = (result['best_fitness'] - baseline) / baseline * 100
        print(f"\n🎯 相比基準線 (3.61%) 提升: {improvement:.1f}%")

    else:
        print(f"\n❌ 優化失敗: {result.get('error', 'Unknown')}")

async def main():
    """主函數"""
    print("\n")
    print("╔" + "═" * 58 + "╗")
    print("║" + " " * 10 + "進階自動學習系統 - 測試程序" + " " * 16 + "║")
    print("╚" + "═" * 58 + "╝")

    # 選擇測試模式
    print("\n請選擇測試模式:")
    print("  1. 多階段優化 (推薦，耗時 10-15 分鐘)")
    print("  2. 自適應窗口優化 (耗時 5-8 分鐘)")
    print("  3. 運行全部測試")

    choice = input("\n請輸入選項 (1/2/3): ").strip()

    if choice == '1':
        await test_multi_stage_optimization()
    elif choice == '2':
        await test_adaptive_window_optimization()
    elif choice == '3':
        await test_multi_stage_optimization()
        await test_adaptive_window_optimization()
    else:
        print("❌ 無效選項")
        return

    print("\n" + "=" * 60)
    print("✅ 所有測試完成！")
    print("=" * 60)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️ 用戶中斷測試")
    except Exception as e:
        print(f"\n\n❌ 測試失敗: {str(e)}")
        import traceback
        traceback.print_exc()
