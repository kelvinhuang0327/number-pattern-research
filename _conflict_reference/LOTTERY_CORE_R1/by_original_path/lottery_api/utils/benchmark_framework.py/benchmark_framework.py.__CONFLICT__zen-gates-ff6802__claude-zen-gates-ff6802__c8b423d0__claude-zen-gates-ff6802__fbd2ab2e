#!/usr/bin/env python3
"""
標準化 Benchmark 框架
====================
確保所有策略回測結果可復現、可驗證。

使用方式：
    from lottery_api.utils.benchmark_framework import StrategyBenchmark

    benchmark = StrategyBenchmark(lottery_type='BIG_LOTTO')
    result = benchmark.evaluate(my_strategy_fn, num_bets=4)
    benchmark.print_report(result)

規範：
    1. 固定種子 (SEED=42) 作為官方基準
    2. 多種子驗證 (42-51) 計算 mean ± std
    3. 統計顯著性檢驗 (p < 0.05)
    4. 標準化輸出格式
"""

import sys
import os
import json
import random
import numpy as np
from collections import Counter
from datetime import datetime
from typing import List, Dict, Callable, Optional, Any
from dataclasses import dataclass, asdict

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager
from lottery_api.common import get_lottery_rules


@dataclass
class BenchmarkResult:
    """回測結果數據結構"""
    strategy_name: str
    lottery_type: str
    num_bets: int
    test_periods: int

    # 核心指標
    win_rate: float          # Match 3+ 勝率
    win_rate_std: float      # 勝率標準差 (多種子)
    random_baseline: float   # 隨機基準
    edge_vs_random: float    # Edge = win_rate - random_baseline

    # 詳細數據
    match_distribution: Dict[int, int]  # {3: 次數, 4: 次數, ...}
    roi: float               # 投資報酬率

    # 統計檢驗
    z_score: float           # Z 分數
    p_value: float           # P 值
    is_significant: bool     # 是否顯著 (p < 0.05)

    # 元數據
    seeds_used: List[int]
    timestamp: str

    def to_dict(self):
        return asdict(self)


class StrategyBenchmark:
    """策略回測框架"""

    # 官方種子
    OFFICIAL_SEED = 42
    MULTI_SEEDS = list(range(42, 52))  # 42-51, 共 10 個

    # 獎金結構 (簡化)
    PRIZE_TABLE = {
        6: 100_000_000,
        5: 50_000,
        4: 2_000,
        3: 400,
    }
    BET_COST = 100  # 每注成本

    def __init__(self, lottery_type: str = 'BIG_LOTTO', test_periods: int = 150):
        self.lottery_type = lottery_type
        self.test_periods = test_periods

        db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
        self.db = DatabaseManager(db_path=db_path)

        # 獲取數據並確保從舊到新排序
        raw_draws = self.db.get_all_draws(lottery_type=lottery_type)
        # DatabaseManager 返回新→舊，需要反轉
        self.all_draws = list(reversed(raw_draws))

        self.rules = get_lottery_rules(lottery_type)

        # 預計算隨機基準
        self._random_baselines = {}

        print(f"📊 Benchmark 框架初始化完成")
        print(f"   彩種: {lottery_type}")
        print(f"   總期數: {len(self.all_draws)}")
        print(f"   測試期數: {test_periods}")

    def evaluate(
        self,
        strategy_fn: Callable[[List[Dict], Dict], List[List[int]]],
        strategy_name: str = "Unknown",
        num_bets: int = 4,
        use_multi_seed: bool = True
    ) -> BenchmarkResult:
        """
        評估策略表現

        Args:
            strategy_fn: 策略函數，接收 (history, rules) 返回 List[List[int]] (多注預測)
            strategy_name: 策略名稱
            num_bets: 注數
            use_multi_seed: 是否使用多種子驗證

        Returns:
            BenchmarkResult: 回測結果
        """
        seeds = self.MULTI_SEEDS if use_multi_seed else [self.OFFICIAL_SEED]

        all_win_rates = []
        all_match_dists = []
        all_scores = []

        for seed in seeds:
            np.random.seed(seed)
            random.seed(seed)

            win_rate, match_dist, score = self._run_backtest(strategy_fn, num_bets)
            all_win_rates.append(win_rate)
            all_match_dists.append(match_dist)
            all_scores.append(score)

        # 計算統計值
        mean_win_rate = np.mean(all_win_rates)
        std_win_rate = np.std(all_win_rates) if len(all_win_rates) > 1 else 0

        # 合併 match distribution
        combined_dist = Counter()
        for dist in all_match_dists:
            combined_dist.update(dist)
        # 取平均
        avg_dist = {k: v / len(seeds) for k, v in combined_dist.items()}

        # 計算隨機基準
        random_baseline = self._get_random_baseline(num_bets, seeds)

        # Edge
        edge = mean_win_rate - random_baseline

        # ROI
        avg_score = np.mean(all_scores)
        total_cost = self.test_periods * num_bets * self.BET_COST
        roi = (avg_score - total_cost) / total_cost * 100

        # 統計檢驗
        z_score, p_value, is_significant = self._statistical_test(
            mean_win_rate, random_baseline, self.test_periods
        )

        return BenchmarkResult(
            strategy_name=strategy_name,
            lottery_type=self.lottery_type,
            num_bets=num_bets,
            test_periods=self.test_periods,
            win_rate=mean_win_rate,
            win_rate_std=std_win_rate,
            random_baseline=random_baseline,
            edge_vs_random=edge,
            match_distribution=dict(avg_dist),
            roi=roi,
            z_score=z_score,
            p_value=p_value,
            is_significant=is_significant,
            seeds_used=seeds,
            timestamp=datetime.now().isoformat()
        )

    def _run_backtest(
        self,
        strategy_fn: Callable,
        num_bets: int
    ) -> tuple:
        """執行單次回測"""
        start_idx = len(self.all_draws) - self.test_periods

        wins = 0
        match_dist = Counter()
        total_score = 0

        for i in range(start_idx, len(self.all_draws)):
            target = self.all_draws[i]
            history = self.all_draws[:i]

            if len(history) < 100:
                continue

            actual = set(target['numbers'])
            if isinstance(target['numbers'], str):
                actual = set(eval(target['numbers']))

            # 獲取預測
            try:
                predictions = strategy_fn(history, self.rules)
                if not predictions:
                    predictions = [sorted(random.sample(range(1, 50), 6)) for _ in range(num_bets)]
                predictions = predictions[:num_bets]
            except Exception as e:
                # 策略失敗時使用隨機
                predictions = [sorted(random.sample(range(1, 50), 6)) for _ in range(num_bets)]

            # 評估
            max_match = 0
            for pred in predictions:
                match = len(set(pred) & actual)
                max_match = max(max_match, match)

            if max_match >= 3:
                wins += 1
                match_dist[max_match] += 1

            # 計算獎金
            prize = self.PRIZE_TABLE.get(max_match, 0)
            total_score += prize

        win_rate = wins / self.test_periods * 100
        return win_rate, match_dist, total_score

    def _get_random_baseline(self, num_bets: int, seeds: List[int]) -> float:
        """計算隨機基準"""
        cache_key = (num_bets, tuple(seeds))
        if cache_key in self._random_baselines:
            return self._random_baselines[cache_key]

        all_rates = []
        max_num = self.rules.get('maxNumber', 49)

        for seed in seeds:
            random.seed(seed)
            wins = 0
            start_idx = len(self.all_draws) - self.test_periods

            for i in range(start_idx, len(self.all_draws)):
                target = self.all_draws[i]
                actual = set(target['numbers'])
                if isinstance(target['numbers'], str):
                    actual = set(eval(target['numbers']))

                # 隨機預測
                max_match = 0
                for _ in range(num_bets):
                    pred = set(random.sample(range(1, max_num + 1), 6))
                    match = len(pred & actual)
                    max_match = max(max_match, match)

                if max_match >= 3:
                    wins += 1

            all_rates.append(wins / self.test_periods * 100)

        baseline = np.mean(all_rates)
        self._random_baselines[cache_key] = baseline
        return baseline

    def _statistical_test(
        self,
        observed_rate: float,
        expected_rate: float,
        n: int
    ) -> tuple:
        """統計顯著性檢驗"""
        # 使用 Z-test
        p = expected_rate / 100
        se = np.sqrt(p * (1 - p) / n) * 100  # 標準誤差

        if se == 0:
            return 0, 1, False

        z = (observed_rate - expected_rate) / se

        # 計算 p-value (單尾)
        from scipy import stats
        try:
            p_value = 1 - stats.norm.cdf(z)
        except:
            # 如果沒有 scipy，使用近似
            p_value = 0.5 if z < 0 else 0.05 if z > 1.65 else 0.1

        is_significant = p_value < 0.05

        return z, p_value, is_significant

    def print_report(self, result: BenchmarkResult):
        """打印標準化報告"""
        print("\n" + "=" * 70)
        print(f"📊 Benchmark 報告: {result.strategy_name}")
        print("=" * 70)

        print(f"\n【基本信息】")
        print(f"  彩種: {result.lottery_type}")
        print(f"  注數: {result.num_bets}")
        print(f"  測試期數: {result.test_periods}")
        print(f"  種子: {result.seeds_used[0]}-{result.seeds_used[-1]} ({len(result.seeds_used)}個)")

        print(f"\n【核心指標】")
        print(f"  勝率 (Match 3+): {result.win_rate:.2f}% ± {result.win_rate_std:.2f}%")
        print(f"  隨機基準:        {result.random_baseline:.2f}%")
        print(f"  Edge vs Random:  {result.edge_vs_random:+.2f}%")
        print(f"  ROI:             {result.roi:+.1f}%")

        print(f"\n【統計檢驗】")
        print(f"  Z-Score: {result.z_score:.2f}")
        print(f"  P-Value: {result.p_value:.4f}")
        sig_mark = "✅ 顯著" if result.is_significant else "❌ 不顯著"
        print(f"  結論:    {sig_mark} (p < 0.05)")

        print(f"\n【命中分布】")
        for match, count in sorted(result.match_distribution.items(), reverse=True):
            print(f"  Match {match}: {count:.1f} 次")

        # 結論
        print(f"\n【結論】")
        if result.edge_vs_random > 1.0 and result.is_significant:
            print(f"  ✅ 策略有效 (Edge > 1%, p < 0.05)")
        elif result.edge_vs_random > 0.5:
            print(f"  ⚠️ 微弱優勢 (0.5% < Edge < 1%)")
        elif result.edge_vs_random > -0.5:
            print(f"  ❌ 與隨機相當 (|Edge| < 0.5%)")
        else:
            print(f"  ❌ 劣於隨機 (Edge < -0.5%)")

        print(f"\n  時間戳: {result.timestamp}")
        print("=" * 70)

    def save_result(self, result: BenchmarkResult, filename: str = None):
        """保存結果到 JSON"""
        if filename is None:
            filename = f"benchmark_{result.strategy_name}_{result.lottery_type}.json"

        filepath = os.path.join(project_root, 'tools', filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)

        print(f"💾 結果已保存至: {filepath}")
        return filepath


# ============================================================
# 便捷函數
# ============================================================

def quick_benchmark(
    strategy_fn: Callable,
    strategy_name: str,
    lottery_type: str = 'BIG_LOTTO',
    num_bets: int = 4,
    test_periods: int = 150
) -> BenchmarkResult:
    """快速回測"""
    benchmark = StrategyBenchmark(lottery_type=lottery_type, test_periods=test_periods)
    result = benchmark.evaluate(strategy_fn, strategy_name, num_bets)
    benchmark.print_report(result)
    return result


# ============================================================
# 測試
# ============================================================

if __name__ == '__main__':
    # 測試：隨機策略
    def random_strategy(history, rules):
        max_num = rules.get('maxNumber', 49)
        return [sorted(random.sample(range(1, max_num + 1), 6)) for _ in range(4)]

    result = quick_benchmark(
        strategy_fn=random_strategy,
        strategy_name="Random_Baseline",
        lottery_type='BIG_LOTTO',
        num_bets=4
    )
