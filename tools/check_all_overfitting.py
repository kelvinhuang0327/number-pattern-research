#!/usr/bin/env python3
"""
全面過擬合檢測 - 檢查所有已驗證策略
"""
import os
import sys

project_root = os.getcwd()
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from tools.overfitting_detector import OverfittingDetector


def main():
    print("=" * 80)
    print("🔬 全面過擬合檢測報告")
    print("=" * 80)

    results_all = []

    # ========== 大樂透策略 ==========
    print("\n" + "=" * 80)
    print("📘 大樂透 (BIG_LOTTO) 策略檢測")
    print("=" * 80)

    detector_bl = OverfittingDetector('BIG_LOTTO')

    biglotto_strategies = [
        # 單注策略
        (['markov'], None, "1注 Markov"),
        (['statistical'], None, "1注 Statistical"),
        (['deviation'], None, "1注 Deviation"),
        (['frequency'], None, "1注 Frequency"),
        (['trend'], None, "1注 Trend"),
        (['bayesian'], None, "1注 Bayesian"),
        (['hot_cold_mix'], None, "1注 HotCold"),

        # 2注策略
        (['statistical', 'frequency'], None, "2注 Stat+Freq"),
        (['deviation', 'frequency'], None, "2注 Dev+Freq"),
        (['markov', 'statistical'], None, "2注 Markov+Stat"),
        (['deviation', 'markov'], None, "2注 Dev+Markov"),

        # 3注策略 (TME)
        (['statistical', 'deviation', 'markov'], None, "3注 TME"),

        # 4注策略
        (['statistical', 'frequency', 'deviation', 'markov'], None, "4注 Top4"),
        (['statistical', 'frequency', 'deviation', 'markov'], 500, "4注 Top4 (W=500)"),

        # 5注策略 (5ME)
        (['statistical', 'deviation', 'markov', 'hot_cold_mix', 'trend'], None, "5注 5ME"),
    ]

    bl_results = []
    for strategy, window, name in biglotto_strategies:
        try:
            stability = detector_bl.segment_stability_analysis(strategy, num_segments=4, window=window)
            decay = detector_bl.recent_vs_overall_analysis(strategy, 150, window)
            complexity = detector_bl.complexity_penalty(strategy, window)

            overall_score = (
                stability['stability_score'] * 0.4 +
                (100 - abs(decay['decay_pct'])) * 0.4 +
                (100 - complexity['complexity_score']) * 0.2
            )
            overall_score = max(0, min(100, overall_score))

            bl_results.append({
                'name': name,
                'score': overall_score,
                'stability': stability['stability_score'],
                'decay': decay['decay'],
                'decay_pct': decay['decay_pct'],
                'overall_rate': decay['overall_rate'],
                'recent_rate': decay['recent_rate'],
                'complexity': complexity['complexity_score'],
                'max_diff': stability['max_diff'],
                'trend': stability['trend']
            })
        except Exception as e:
            print(f"Error testing {name}: {e}")
            continue

    # 排序並顯示
    bl_results.sort(key=lambda x: x['score'], reverse=True)

    print(f"\n{'策略':<25} {'分數':<8} {'風險':<8} {'全期':<8} {'近150期':<8} {'衰減':<10} {'穩定性':<8}")
    print("-" * 85)

    for r in bl_results:
        if r['score'] >= 70:
            risk = '✅ 低'
        elif r['score'] >= 50:
            risk = '⚠️ 中'
        else:
            risk = '🔴 高'

        decay_str = f"{r['decay']:+.2f}%"
        print(f"{r['name']:<25} {r['score']:.1f}    {risk:<8} {r['overall_rate']:.2f}%   {r['recent_rate']:.2f}%   {decay_str:<10} {r['stability']:.1f}")

    results_all.extend([(r, 'BIG_LOTTO') for r in bl_results])

    # ========== 威力彩策略 ==========
    print("\n" + "=" * 80)
    print("⭐ 威力彩 (POWER_LOTTO) 策略檢測")
    print("=" * 80)

    detector_pl = OverfittingDetector('POWER_LOTTO')

    powerlotto_strategies = [
        # 單注策略
        (['markov'], None, "1注 Markov"),
        (['statistical'], None, "1注 Statistical"),
        (['deviation'], None, "1注 Deviation"),
        (['frequency'], None, "1注 Frequency"),

        # 2注策略
        (['statistical', 'frequency'], None, "2注 Stat+Freq"),
        (['deviation', 'frequency'], None, "2注 Dev+Freq"),
        (['markov', 'statistical'], None, "2注 Markov+Stat"),

        # 4注策略
        (['statistical', 'frequency', 'deviation', 'markov'], None, "4注 Top4"),
    ]

    pl_results = []
    for strategy, window, name in powerlotto_strategies:
        try:
            stability = detector_pl.segment_stability_analysis(strategy, num_segments=4, window=window)
            decay = detector_pl.recent_vs_overall_analysis(strategy, 150, window)
            complexity = detector_pl.complexity_penalty(strategy, window)

            overall_score = (
                stability['stability_score'] * 0.4 +
                (100 - abs(decay['decay_pct'])) * 0.4 +
                (100 - complexity['complexity_score']) * 0.2
            )
            overall_score = max(0, min(100, overall_score))

            pl_results.append({
                'name': name,
                'score': overall_score,
                'stability': stability['stability_score'],
                'decay': decay['decay'],
                'decay_pct': decay['decay_pct'],
                'overall_rate': decay['overall_rate'],
                'recent_rate': decay['recent_rate'],
                'complexity': complexity['complexity_score'],
                'max_diff': stability['max_diff'],
                'trend': stability['trend']
            })
        except Exception as e:
            print(f"Error testing {name}: {e}")
            continue

    # 排序並顯示
    pl_results.sort(key=lambda x: x['score'], reverse=True)

    print(f"\n{'策略':<25} {'分數':<8} {'風險':<8} {'全期':<8} {'近150期':<8} {'衰減':<10} {'穩定性':<8}")
    print("-" * 85)

    for r in pl_results:
        if r['score'] >= 70:
            risk = '✅ 低'
        elif r['score'] >= 50:
            risk = '⚠️ 中'
        else:
            risk = '🔴 高'

        decay_str = f"{r['decay']:+.2f}%"
        print(f"{r['name']:<25} {r['score']:.1f}    {risk:<8} {r['overall_rate']:.2f}%   {r['recent_rate']:.2f}%   {decay_str:<10} {r['stability']:.1f}")

    results_all.extend([(r, 'POWER_LOTTO') for r in pl_results])

    # ========== 總結 ==========
    print("\n" + "=" * 80)
    print("📊 過擬合風險總結")
    print("=" * 80)

    # 統計各風險等級
    low_risk = [r for r, t in results_all if r['score'] >= 70]
    med_risk = [r for r, t in results_all if 50 <= r['score'] < 70]
    high_risk = [r for r, t in results_all if r['score'] < 50]

    print(f"\n✅ 低風險策略 ({len(low_risk)}個):")
    for r in sorted(low_risk, key=lambda x: x['score'], reverse=True)[:10]:
        print(f"   {r['name']:<25} {r['score']:.1f}/100")

    if med_risk:
        print(f"\n⚠️ 中風險策略 ({len(med_risk)}個):")
        for r in sorted(med_risk, key=lambda x: x['score'], reverse=True):
            print(f"   {r['name']:<25} {r['score']:.1f}/100")

    if high_risk:
        print(f"\n🔴 高風險策略 ({len(high_risk)}個):")
        for r in sorted(high_risk, key=lambda x: x['score'], reverse=True):
            print(f"   {r['name']:<25} {r['score']:.1f}/100 - 可能過擬合!")

    # 最佳推薦
    print("\n" + "=" * 80)
    print("🏆 穩健策略推薦 (分數 ≥ 80)")
    print("=" * 80)

    top_strategies = [(r, t) for r, t in results_all if r['score'] >= 80]
    top_strategies.sort(key=lambda x: (x[0]['overall_rate'], x[0]['score']), reverse=True)

    print(f"\n{'排名':<5} {'彩種':<12} {'策略':<25} {'分數':<8} {'全期勝率':<10}")
    print("-" * 65)
    for i, (r, lottery_type) in enumerate(top_strategies[:10], 1):
        lt_short = '大樂透' if lottery_type == 'BIG_LOTTO' else '威力彩'
        print(f"{i:<5} {lt_short:<12} {r['name']:<25} {r['score']:.1f}    {r['overall_rate']:.2f}%")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
