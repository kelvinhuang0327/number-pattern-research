"""
快速測試回測框架
"""
import logging
from backtest_framework import BacktestFramework

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# 創建回測框架
framework = BacktestFramework()

# 測試單一方法（只測試10期，快速驗證）
print("\n🔍 測試頻率分析方法...")
result = framework.backtest_single_method(
    method_name='frequency',
    lottery_type='BIG_LOTTO',
    test_size=10,
    min_history=50
)

print(f"\n✅ 測試結果:")
print(f"  方法: {result.get('method')}")
print(f"  測試期數: {result.get('total_tests')}")
print(f"  勝率: {result.get('win_rate', 0):.2%}")
print(f"  平均匹配: {result.get('avg_matches', 0):.2f}")
print(f"  匹配分布: {result.get('match_distribution')}")

print("\n✅ 回測框架測試成功！")
