"""
運行完整回測並生成報告
測試所有改進後的預測方法
"""
import logging
import json
from backtest_framework import BacktestFramework
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

print("="*80)
print("🚀 Phase 1 優化效果驗證 - 完整回測")
print("="*80)
print()

# 創建回測框架
framework = BacktestFramework()

# 測試期數
TEST_SIZE = 100

print(f"📊 測試配置:")
print(f"  - 彩票類型: 大樂透 (BIG_LOTTO)")
print(f"  - 測試期數: {TEST_SIZE}")
print(f"  - 最小歷史: 50期")
print()

# 重點測試的方法（包含已優化的）
priority_methods = [
    'frequency',      # ✨ 已優化：加入遺漏值權重
    'deviation',      # 基準方法
    'entropy_transformer',  # ✨ 已優化：信心度修復
    'anomaly_detection',    # ✨ 已優化：馬氏距離
    'meta_learning'   # 集成方法
]

print("🔍 測試方法:")
for i, method in enumerate(priority_methods, 1):
    marker = "✨" if method in ['frequency', 'entropy_transformer', 'anomaly_detection'] else "📌"
    print(f"  {i}. {marker} {method}")
print()

# 執行回測
comparison = []

for i, method in enumerate(priority_methods, 1):
    print(f"{'='*80}")
    print(f"[{i}/{len(priority_methods)}] 測試 {method}...")
    print(f"{'='*80}")

    try:
        result = framework.backtest_single_method(
            method_name=method,
            lottery_type='BIG_LOTTO',
            test_size=TEST_SIZE,
            min_history=50
        )

        comparison.append(result)

        # 顯示即時結果
        print(f"✅ 完成!")
        print(f"  勝率: {result.get('win_rate', 0):.2%}")
        print(f"  平均匹配: {result.get('avg_matches', 0):.2f}")
        print(f"  期望值: ${result.get('expected_value', 0):.0f}")
        print()

    except Exception as e:
        print(f"❌ 錯誤: {e}")
        print()
        continue

# 生成報告
if comparison:
    print("="*80)
    print("📝 生成報告...")
    print("="*80)

    output_file = f'backtest_report_phase1_{datetime.now().strftime("%Y%m%d_%H%M%S")}.md'
    framework.generate_report(comparison, output_file=output_file)

    print(f"✅ 報告已生成: {output_file}")
    print()

    # 保存 JSON 格式的原始數據
    json_file = output_file.replace('.md', '.json')
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(comparison, f, ensure_ascii=False, indent=2)
    print(f"✅ 原始數據已保存: {json_file}")
    print()

    # 顯示排名
    print("="*80)
    print("🏆 方法排名（按勝率）")
    print("="*80)

    # 按勝率排序
    sorted_comparison = sorted(comparison, key=lambda x: x.get('win_rate', 0), reverse=True)

    for rank, result in enumerate(sorted_comparison, 1):
        method = result.get('method', 'Unknown')
        win_rate = result.get('win_rate', 0)
        avg_matches = result.get('avg_matches', 0)

        # 標記已優化的方法
        marker = "✨" if any(m in method.lower() for m in ['frequency', 'entropy', 'anomaly']) else "  "

        print(f"{rank}. {marker} {method}")
        print(f"     勝率: {win_rate:.2%} | 平均匹配: {avg_matches:.2f}")

    print()
    print("="*80)
    print("✅ 回測完成！")
    print("="*80)
else:
    print("❌ 沒有成功的回測結果")
