#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全面滾動回測 - 測試所有優化後的方法

測試配置：
- 使用滾動窗口方式測試
- 每次使用固定歷史期數預測下一期
- 測試100-200期以獲得統計顯著性
"""
import logging
from backtest_framework import BacktestFramework
from datetime import datetime
import json

logging.basicConfig(
    level=logging.WARNING,
    format='%(levelname)s - %(message)s'
)

print("="*80)
print("🎯 全面滾動回測 - 優化方法驗證")
print("="*80)
print()

# 創建回測框架
framework = BacktestFramework()

# 測試配置
TEST_SIZES = [100, 150, 200]  # 測試不同的樣本大小
LOTTERY_TYPE = 'BIG_LOTTO'
MIN_HISTORY = 50  # 最小歷史期數

# 測試方法
methods = [
    # Phase 1 優化方法（已驗證有效）
    ('frequency', 'Phase 1', '✨ 頻率分析+遺漏值', True),
    ('entropy_transformer', 'Phase 1', '✨ 熵驅動Transformer', True),

    # Phase 2 優化方法（需要驗證）
    ('deviation', 'Phase 2', '🚀 多維度偏差分析', True),

    # 其他方法作為對比
    ('meta_learning', '對比', '🔄 元學習集成', False),
    ('hot_cold_mix', '對比', '🌡️  冷熱混合', False),
]

print(f"📊 測試配置:")
print(f"  - 彩票類型: {LOTTERY_TYPE}")
print(f"  - 測試樣本: {TEST_SIZES}")
print(f"  - 最小歷史: {MIN_HISTORY} 期")
print(f"  - 測試方法: {len(methods)} 個")
print()

# 顯示測試方法
print("🔍 測試方法列表:")
for i, (method, phase, desc, is_optimized) in enumerate(methods, 1):
    opt_mark = "【優化】" if is_optimized else "【對比】"
    print(f"  {i}. [{phase}] {opt_mark} {desc}")
print()

# 對每個測試大小進行回測
all_results = {}

for test_size in TEST_SIZES:
    print("="*80)
    print(f"📊 測試樣本大小: {test_size} 期")
    print("="*80)
    print()

    results = []

    for i, (method, phase, desc, is_optimized) in enumerate(methods, 1):
        print(f"[{i}/{len(methods)}] 測試 {method} (共 {test_size} 期)...", end=' ', flush=True)

        try:
            result = framework.backtest_single_method(
                method_name=method,
                lottery_type=LOTTERY_TYPE,
                test_size=test_size,
                min_history=MIN_HISTORY
            )

            result['phase'] = phase
            result['description'] = desc
            result['is_optimized'] = is_optimized
            results.append(result)

            # 顯示即時結果
            win_rate = result.get('win_rate', 0)
            avg_matches = result.get('avg_matches', 0)
            print(f"✅ 勝率: {win_rate:.2%} | 平均匹配: {avg_matches:.2f}")

        except Exception as e:
            print(f"❌ 錯誤: {e}")
            continue

    all_results[test_size] = results

    # 顯示這個測試大小的摘要
    print()
    print(f"📈 {test_size}期測試摘要:")
    print("-"*80)

    # 按優化/對比分組
    optimized_results = [r for r in results if r.get('is_optimized', False)]
    comparison_results = [r for r in results if not r.get('is_optimized', False)]

    if optimized_results:
        print("\n✨ 優化方法:")
        for result in sorted(optimized_results, key=lambda x: x.get('win_rate', 0), reverse=True):
            method = result['description']
            win_rate = result.get('win_rate', 0)
            avg_matches = result.get('avg_matches', 0)
            match_dist = result.get('match_distribution', {})
            print(f"  {method}")
            print(f"    勝率: {win_rate:.2%} | 平均: {avg_matches:.2f} | 分布: 0中={match_dist.get(0,0)} 1中={match_dist.get(1,0)} 2中={match_dist.get(2,0)} 3中+={sum(match_dist.get(k,0) for k in range(3,7))}")

    if comparison_results:
        print("\n🔄 對比方法:")
        for result in sorted(comparison_results, key=lambda x: x.get('win_rate', 0), reverse=True):
            method = result['description']
            win_rate = result.get('win_rate', 0)
            avg_matches = result.get('avg_matches', 0)
            match_dist = result.get('match_distribution', {})
            print(f"  {method}")
            print(f"    勝率: {win_rate:.2%} | 平均: {avg_matches:.2f} | 分布: 0中={match_dist.get(0,0)} 1中={match_dist.get(1,0)} 2中={match_dist.get(2,0)} 3中+={sum(match_dist.get(k,0) for k in range(3,7))}")

    print()

# 生成最終對比報告
print()
print("="*80)
print("📊 全面對比分析")
print("="*80)
print()

# 找出最佳測試大小（使用最大的測試樣本）
best_test_size = max(TEST_SIZES)
best_results = all_results[best_test_size]

print(f"📈 基於 {best_test_size} 期測試的最終結果:")
print()

# Phase 1 vs Phase 2 對比
phase1_results = [r for r in best_results if r['phase'] == 'Phase 1']
phase2_results = [r for r in best_results if r['phase'] == 'Phase 2']

if phase1_results:
    print("🎯 Phase 1 優化方法:")
    phase1_avg_wr = sum(r.get('win_rate', 0) for r in phase1_results) / len(phase1_results)
    phase1_avg_matches = sum(r.get('avg_matches', 0) for r in phase1_results) / len(phase1_results)

    for result in sorted(phase1_results, key=lambda x: x.get('win_rate', 0), reverse=True):
        print(f"  {result['description']}")
        print(f"    勝率: {result.get('win_rate', 0):.2%} | 平均匹配: {result.get('avg_matches', 0):.2f}")

    print(f"  → Phase 1 平均勝率: {phase1_avg_wr:.2%}")
    print(f"  → Phase 1 平均匹配: {phase1_avg_matches:.2f}")

if phase2_results:
    print()
    print("🚀 Phase 2 優化方法:")
    phase2_avg_wr = sum(r.get('win_rate', 0) for r in phase2_results) / len(phase2_results)
    phase2_avg_matches = sum(r.get('avg_matches', 0) for r in phase2_results) / len(phase2_results)

    for result in sorted(phase2_results, key=lambda x: x.get('win_rate', 0), reverse=True):
        print(f"  {result['description']}")
        print(f"    勝率: {result.get('win_rate', 0):.2%} | 平均匹配: {result.get('avg_matches', 0):.2f}")

    print(f"  → Phase 2 平均勝率: {phase2_avg_wr:.2%}")
    print(f"  → Phase 2 平均匹配: {phase2_avg_matches:.2f}")

# 對比分析
if phase1_results and phase2_results:
    print()
    print("📊 Phase 對比:")

    if phase2_avg_wr > phase1_avg_wr:
        improvement = ((phase2_avg_wr - phase1_avg_wr) / (phase1_avg_wr + 1e-10)) * 100
        print(f"  ✅ Phase 2 勝率提升: +{improvement:.1f}%")
    elif phase2_avg_wr < phase1_avg_wr:
        decline = ((phase1_avg_wr - phase2_avg_wr) / (phase1_avg_wr + 1e-10)) * 100
        print(f"  ⚠️  Phase 2 勝率下降: -{decline:.1f}%")
    else:
        print(f"  ➡️  Phase 2 勝率持平")

    if phase2_avg_matches > phase1_avg_matches:
        improvement = ((phase2_avg_matches - phase1_avg_matches) / (phase1_avg_matches + 1e-10)) * 100
        print(f"  ✅ Phase 2 平均匹配提升: +{improvement:.1f}%")
    elif phase2_avg_matches < phase1_avg_matches:
        decline = ((phase1_avg_matches - phase2_avg_matches) / (phase1_avg_matches + 1e-10)) * 100
        print(f"  ⚠️  Phase 2 平均匹配下降: -{decline:.1f}%")
    else:
        print(f"  ➡️  Phase 2 平均匹配持平")

# 找出整體最佳方法
print()
print("🏆 最佳方法排名（基於勝率）:")
ranked_results = sorted(best_results, key=lambda x: (x.get('win_rate', 0), x.get('avg_matches', 0)), reverse=True)

for i, result in enumerate(ranked_results[:5], 1):  # 顯示前5名
    medal = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"][i-1]
    print(f"  {medal} {result['description']}")
    print(f"     勝率: {result.get('win_rate', 0):.2%} | 平均匹配: {result.get('avg_matches', 0):.2f}")

# 樣本大小影響分析
print()
print("📊 樣本大小影響分析:")
print()

for method, phase, desc, is_optimized in methods:
    print(f"{desc}:")
    for test_size in TEST_SIZES:
        results = all_results[test_size]
        method_result = next((r for r in results if r['method'] == method), None)
        if method_result:
            wr = method_result.get('win_rate', 0)
            am = method_result.get('avg_matches', 0)
            print(f"  {test_size:3d}期: 勝率={wr:.2%} 平均={am:.2f}")
    print()

# 保存結果到JSON
output_file = 'data/comprehensive_backtest_results.json'
try:
    import os
    os.makedirs('data', exist_ok=True)

    # 準備保存數據
    save_data = {
        'test_date': datetime.now().isoformat(),
        'lottery_type': LOTTERY_TYPE,
        'test_sizes': TEST_SIZES,
        'min_history': MIN_HISTORY,
        'results': {}
    }

    for test_size, results in all_results.items():
        save_data['results'][str(test_size)] = [
            {
                'method': r['method'],
                'phase': r['phase'],
                'description': r['description'],
                'win_rate': r.get('win_rate', 0),
                'avg_matches': r.get('avg_matches', 0),
                'match_distribution': r.get('match_distribution', {}),
                'total_tests': r.get('total_tests', 0),
                'wins': r.get('wins', 0)
            }
            for r in results
        ]

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(save_data, f, ensure_ascii=False, indent=2)

    print(f"✅ 結果已保存到: {output_file}")

except Exception as e:
    print(f"⚠️  保存結果失敗: {e}")

print()
print("="*80)
print("✅ 全面滾動回測完成！")
print("="*80)
