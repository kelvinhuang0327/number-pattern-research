"""
對比 Phase 1 和 Phase 2 的優化效果
"""
import logging
from backtest_framework import BacktestFramework
from datetime import datetime

logging.basicConfig(
    level=logging.WARNING,
    format='%(levelname)s - %(message)s'
)

print("="*80)
print("📊 Phase 1 vs Phase 2 優化效果對比")
print("="*80)
print()

# 創建回測框架
framework = BacktestFramework()

# 測試期數
TEST_SIZE = 50  # 先用50期快速驗證

print(f"📊 測試配置:")
print(f"  - 彩票類型: 大樂透 (BIG_LOTTO)")
print(f"  - 測試期數: {TEST_SIZE}")
print()

# Phase 1 vs Phase 2 對比
methods = [
    # Phase 1 優化方法
    ('frequency', 'Phase 1', '✨ 頻率分析+遺漏值'),
    ('entropy_transformer', 'Phase 1', '✨ 熵驅動Transformer'),

    # Phase 2 優化方法
    ('deviation', 'Phase 2', '🚀 多維度偏差分析'),
]

print("🔍 測試方法:")
for i, (method, phase, desc) in enumerate(methods, 1):
    print(f"  {i}. [{phase}] {desc}")
print()

# 執行回測
results = []

for i, (method, phase, desc) in enumerate(methods, 1):
    print(f"[{i}/{len(methods)}] 測試 {method}...", end=' ', flush=True)

    try:
        result = framework.backtest_single_method(
            method_name=method,
            lottery_type='BIG_LOTTO',
            test_size=TEST_SIZE,
            min_history=50
        )

        result['phase'] = phase
        result['description'] = desc
        results.append(result)

        # 顯示即時結果
        print(f"✅ 勝率: {result.get('win_rate', 0):.2%} | 平均匹配: {result.get('avg_matches', 0):.2f}")

    except Exception as e:
        print(f"❌ 錯誤: {e}")
        continue

# 顯示對比結果
if results:
    print()
    print("="*80)
    print("📊 優化效果對比")
    print("="*80)

    # 按 Phase 分組
    phase1_results = [r for r in results if r['phase'] == 'Phase 1']
    phase2_results = [r for r in results if r['phase'] == 'Phase 2']

    print("\n🎯 Phase 1 優化方法（已驗證）:")
    for result in phase1_results:
        method = result['description']
        win_rate = result.get('win_rate', 0)
        avg_matches = result.get('avg_matches', 0)
        print(f"  {method}")
        print(f"    勝率: {win_rate:.2%} | 平均匹配: {avg_matches:.2f}")

    if phase2_results:
        print("\n🚀 Phase 2 優化方法（新增）:")
        for result in phase2_results:
            method = result['description']
            win_rate = result.get('win_rate', 0)
            avg_matches = result.get('avg_matches', 0)
            match_dist = result.get('match_distribution', {})
            print(f"  {method}")
            print(f"    勝率: {win_rate:.2%} | 平均匹配: {avg_matches:.2f}")
            print(f"    匹配分布: 0中={match_dist.get(0,0)} 1中={match_dist.get(1,0)} 2中={match_dist.get(2,0)} 3中+={match_dist.get(3,0)}")

    # 對比總結
    print("\n"+"="*80)
    print("📈 總結")
    print("="*80)

    if phase1_results and phase2_results:
        phase1_avg_wr = sum(r.get('win_rate', 0) for r in phase1_results) / len(phase1_results)
        phase2_avg_wr = sum(r.get('win_rate', 0) for r in phase2_results) / len(phase2_results)

        phase1_avg_matches = sum(r.get('avg_matches', 0) for r in phase1_results) / len(phase1_results)
        phase2_avg_matches = sum(r.get('avg_matches', 0) for r in phase2_results) / len(phase2_results)

        print(f"Phase 1 平均勝率: {phase1_avg_wr:.2%}")
        print(f"Phase 2 平均勝率: {phase2_avg_wr:.2%}")
        print(f"Phase 1 平均匹配: {phase1_avg_matches:.2f}")
        print(f"Phase 2 平均匹配: {phase2_avg_matches:.2f}")

        if phase2_avg_wr > phase1_avg_wr:
            improvement = (phase2_avg_wr - phase1_avg_wr) / phase1_avg_wr * 100
            print(f"\n✅ Phase 2 勝率提升: +{improvement:.1f}%")
        elif phase2_avg_matches > phase1_avg_matches:
            improvement = (phase2_avg_matches - phase1_avg_matches) / phase1_avg_matches * 100
            print(f"\n✅ Phase 2 匹配數提升: +{improvement:.1f}%")

    print("\n"+"="*80)
    print("✅ 對比測試完成！")
    print("="*80)
else:
    print("❌ 沒有成功的回測結果")
