#!/usr/bin/env python3
"""
Overfitting Detector for Lottery Prediction Strategies
檢測策略是否過擬合，提供穩健性分析報告

檢測方法:
1. 時段穩定性分析 - 比較不同時期的表現
2. 走勢衰減分析 - 檢查最近期表現是否下滑
3. 複雜度懲罰 - 評估策略複雜度風險
"""
import os
import sys
import numpy as np
from collections import Counter
from typing import List, Dict, Tuple, Optional, Callable

project_root = os.getcwd()
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules
from models.unified_predictor import UnifiedPredictionEngine


class OverfittingDetector:
    """過擬合檢測器"""

    def __init__(self, lottery_type: str = 'BIG_LOTTO'):
        self.lottery_type = lottery_type
        self.db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery.db')
        self.db = DatabaseManager(db_path=self.db_path)
        self.all_draws = list(reversed(self.db.get_all_draws(lottery_type=lottery_type)))
        self.rules = get_lottery_rules(lottery_type)
        self.engine = UnifiedPredictionEngine()

        # 預設方法
        self.methods = {
            'markov': lambda h, r: self.engine.markov_predict(h, r)['numbers'][:6],
            'deviation': lambda h, r: self.engine.deviation_predict(h, r)['numbers'][:6],
            'statistical': lambda h, r: self.engine.statistical_predict(h, r)['numbers'][:6],
            'frequency': lambda h, r: self.engine.frequency_predict(h, r)['numbers'][:6],
            'trend': lambda h, r: self.engine.trend_predict(h, r)['numbers'][:6],
            'bayesian': lambda h, r: self.engine.bayesian_predict(h, r)['numbers'][:6],
            'hot_cold_mix': lambda h, r: self.engine.hot_cold_mix_predict(h, r)['numbers'][:6],
        }

    def evaluate_segment(
        self,
        strategy: List[str],
        start_idx: int,
        end_idx: int,
        window: Optional[int] = None
    ) -> Dict:
        """評估特定區段的表現"""
        wins = 0
        m4_plus = 0
        total = 0

        for target_idx in range(start_idx, end_idx):
            if target_idx >= len(self.all_draws):
                break

            target_draw = self.all_draws[target_idx]

            # 使用視窗或全部歷史
            if window:
                hist_start = max(0, target_idx - window)
                history = self.all_draws[hist_start:target_idx]
            else:
                history = self.all_draws[:target_idx]

            if len(history) < 50:
                continue

            actual = set(target_draw.get('numbers', target_draw.get('first_zone', [])))

            best_match = 0
            hit = False

            for method_name in strategy:
                try:
                    method_func = self.methods.get(method_name)
                    if not method_func:
                        continue
                    predicted = method_func(history, self.rules)
                    match = len(set(predicted) & actual)

                    if match > best_match:
                        best_match = match
                    if match >= 3:
                        hit = True
                except:
                    continue

            if hit: wins += 1
            if best_match >= 4: m4_plus += 1
            total += 1

        win_rate = wins / total * 100 if total > 0 else 0
        return {
            'win_rate': win_rate,
            'wins': wins,
            'total': total,
            'm4_plus': m4_plus
        }

    def segment_stability_analysis(
        self,
        strategy: List[str],
        num_segments: int = 4,
        window: Optional[int] = None
    ) -> Dict:
        """
        時段穩定性分析
        將數據分成多段，比較各段表現
        """
        total_periods = len(self.all_draws) - 100  # 保留 100 期最小歷史
        segment_size = total_periods // num_segments

        results = []

        for i in range(num_segments):
            start = 100 + i * segment_size
            end = start + segment_size

            segment_result = self.evaluate_segment(strategy, start, end, window)
            segment_result['segment'] = i + 1
            segment_result['period_range'] = f"{start}-{end}"
            results.append(segment_result)

        # 計算統計
        rates = [r['win_rate'] for r in results]
        mean_rate = np.mean(rates)
        std_rate = np.std(rates)
        max_diff = max(rates) - min(rates)

        # 檢查趨勢（最後一段 vs 第一段）
        trend = results[-1]['win_rate'] - results[0]['win_rate']

        # 過擬合判定
        cv = std_rate / mean_rate if mean_rate > 0 else 0  # 變異係數

        stability_score = 100 - (cv * 100) - (abs(trend) * 2)
        stability_score = max(0, min(100, stability_score))

        return {
            'segments': results,
            'mean_rate': mean_rate,
            'std_rate': std_rate,
            'max_diff': max_diff,
            'trend': trend,
            'cv': cv,
            'stability_score': stability_score,
            'is_stable': max_diff < 5 and abs(trend) < 3
        }

    def recent_vs_overall_analysis(
        self,
        strategy: List[str],
        recent_periods: int = 150,
        window: Optional[int] = None
    ) -> Dict:
        """
        走勢衰減分析
        比較最近 N 期 vs 全期表現
        """
        total_periods = len(self.all_draws) - 100

        # 全期表現
        overall = self.evaluate_segment(strategy, 100, len(self.all_draws), window)

        # 最近 N 期表現
        recent_start = len(self.all_draws) - recent_periods
        recent = self.evaluate_segment(strategy, recent_start, len(self.all_draws), window)

        # 計算衰減
        decay = overall['win_rate'] - recent['win_rate']
        decay_pct = (decay / overall['win_rate'] * 100) if overall['win_rate'] > 0 else 0

        return {
            'overall_rate': overall['win_rate'],
            'overall_periods': overall['total'],
            'recent_rate': recent['win_rate'],
            'recent_periods': recent['total'],
            'decay': decay,
            'decay_pct': decay_pct,
            'is_decaying': decay > 2,  # 衰減超過 2% 視為有問題
            'status': 'HEALTHY' if decay <= 2 else ('WARNING' if decay <= 5 else 'CRITICAL')
        }

    def complexity_penalty(self, strategy: List[str], window: Optional[int] = None) -> Dict:
        """
        複雜度懲罰評估
        策略越複雜，過擬合風險越高
        """
        # 基礎複雜度
        num_methods = len(strategy)
        has_window = window is not None

        # 計算複雜度分數 (0-100, 越高越複雜)
        complexity = 0
        complexity += num_methods * 15  # 每個方法 +15
        complexity += 20 if has_window else 0  # 特定視窗 +20
        complexity = min(100, complexity)

        # 風險等級
        if complexity <= 30:
            risk_level = 'LOW'
            risk_color = '🟢'
        elif complexity <= 60:
            risk_level = 'MEDIUM'
            risk_color = '🟡'
        else:
            risk_level = 'HIGH'
            risk_color = '🔴'

        return {
            'num_methods': num_methods,
            'has_window': has_window,
            'window': window,
            'complexity_score': complexity,
            'risk_level': risk_level,
            'risk_color': risk_color
        }

    def full_analysis(
        self,
        strategy: List[str],
        window: Optional[int] = None,
        recent_periods: int = 150
    ) -> Dict:
        """完整過擬合分析"""

        print("=" * 80)
        print(f"🔬 過擬合檢測報告 - {self.lottery_type}")
        print(f"   策略: {' + '.join(strategy)}")
        print(f"   視窗: {window if window else '全部'}")
        print("=" * 80)

        # 1. 時段穩定性分析
        print("\n📊 1. 時段穩定性分析")
        print("-" * 40)
        stability = self.segment_stability_analysis(strategy, num_segments=4, window=window)

        for seg in stability['segments']:
            print(f"   段 {seg['segment']} ({seg['period_range']}): {seg['win_rate']:.2f}% ({seg['wins']}/{seg['total']})")

        print(f"\n   平均: {stability['mean_rate']:.2f}%")
        print(f"   標準差: {stability['std_rate']:.2f}%")
        print(f"   最大差異: {stability['max_diff']:.2f}%")
        print(f"   趨勢 (末段-首段): {stability['trend']:+.2f}%")
        print(f"   穩定性分數: {stability['stability_score']:.1f}/100")
        print(f"   判定: {'✅ 穩定' if stability['is_stable'] else '⚠️ 不穩定'}")

        # 2. 走勢衰減分析
        print("\n📉 2. 走勢衰減分析")
        print("-" * 40)
        decay = self.recent_vs_overall_analysis(strategy, recent_periods, window)

        print(f"   全期表現: {decay['overall_rate']:.2f}% ({decay['overall_periods']}期)")
        print(f"   最近{recent_periods}期: {decay['recent_rate']:.2f}%")
        print(f"   衰減幅度: {decay['decay']:+.2f}% ({decay['decay_pct']:+.1f}%)")

        status_icon = {'HEALTHY': '✅', 'WARNING': '⚠️', 'CRITICAL': '🔴'}
        print(f"   狀態: {status_icon[decay['status']]} {decay['status']}")

        # 3. 複雜度評估
        print("\n🔧 3. 複雜度評估")
        print("-" * 40)
        complexity = self.complexity_penalty(strategy, window)

        print(f"   方法數量: {complexity['num_methods']}")
        print(f"   特定視窗: {'是' if complexity['has_window'] else '否'}")
        print(f"   複雜度分數: {complexity['complexity_score']}/100")
        print(f"   風險等級: {complexity['risk_color']} {complexity['risk_level']}")

        # 4. 綜合評估
        print("\n" + "=" * 80)
        print("📋 綜合過擬合風險評估")
        print("=" * 80)

        # 計算綜合分數
        overall_score = (
            stability['stability_score'] * 0.4 +
            (100 - abs(decay['decay_pct'])) * 0.4 +
            (100 - complexity['complexity_score']) * 0.2
        )
        overall_score = max(0, min(100, overall_score))

        if overall_score >= 70:
            verdict = '✅ 低過擬合風險 - 策略穩健'
            verdict_detail = '策略在不同時期表現一致，可放心使用'
        elif overall_score >= 50:
            verdict = '⚠️ 中等過擬合風險 - 需注意'
            verdict_detail = '策略有一定波動，建議持續監控'
        else:
            verdict = '🔴 高過擬合風險 - 謹慎使用'
            verdict_detail = '策略可能過度擬合歷史數據，未來表現可能下滑'

        print(f"\n   綜合分數: {overall_score:.1f}/100")
        print(f"   判定: {verdict}")
        print(f"   建議: {verdict_detail}")

        # 詳細建議
        print("\n💡 改進建議:")
        if not stability['is_stable']:
            print("   • 策略在不同時期表現差異大，考慮簡化策略或增加樣本")
        if decay['is_decaying']:
            print("   • 最近表現下滑，策略可能失效，考慮重新調整")
        if complexity['risk_level'] == 'HIGH':
            print("   • 策略複雜度高，考慮減少方法數量或移除特定視窗")
        if overall_score >= 70:
            print("   • 策略表現穩健，可繼續使用")

        print("=" * 80)

        return {
            'strategy': strategy,
            'window': window,
            'stability': stability,
            'decay': decay,
            'complexity': complexity,
            'overall_score': overall_score,
            'verdict': verdict
        }


def main():
    """測試主要策略的過擬合風險"""

    detector = OverfittingDetector('BIG_LOTTO')

    # 測試不同策略
    strategies_to_test = [
        # 大樂透策略
        (['markov'], None, "單注 Markov"),
        (['statistical', 'frequency'], None, "2-Bet (Statistical + Frequency)"),
        (['statistical', 'frequency', 'deviation', 'markov'], None, "4-Bet Top4"),
        (['statistical', 'frequency', 'deviation', 'markov'], 500, "4-Bet Top4 (W=500)"),
    ]

    results = []

    for strategy, window, name in strategies_to_test:
        print(f"\n\n{'#'*80}")
        print(f"# 測試: {name}")
        print(f"{'#'*80}")

        result = detector.full_analysis(strategy, window)
        result['name'] = name
        results.append(result)

    # 總結
    print("\n\n" + "=" * 80)
    print("📊 所有策略過擬合風險總結")
    print("=" * 80)
    print(f"{'策略':<35} {'分數':<10} {'判定':<20}")
    print("-" * 65)

    for r in results:
        score = r['overall_score']
        if score >= 70:
            status = '✅ 低風險'
        elif score >= 50:
            status = '⚠️ 中風險'
        else:
            status = '🔴 高風險'
        print(f"{r['name']:<35} {score:.1f}/100   {status}")

    print("=" * 80)


if __name__ == "__main__":
    main()
