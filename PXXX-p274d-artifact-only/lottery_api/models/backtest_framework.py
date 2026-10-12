"""
標準化滾動回測框架

設計原則：
1. 統一的回測介面 - 所有預測方法都使用相同的回測邏輯
2. 真實的滾動模擬 - 預測時只能使用該期之前的數據
3. 標準化的成功判定 - 大樂透需中3個以上號碼
4. 結果持久化 - 保存回測結果供後續分析

回測流程：
  Period 1: train=[...2024-12-31] → predict(2025-001) → compare(actual)
  Period 2: train=[...2025-001]  → predict(2025-002) → compare(actual)
  Period N: train=[...2025-N-1]  → predict(2025-N)   → compare(actual)
"""

import os
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import List, Dict, Tuple, Optional, Callable
from collections import defaultdict
import numpy as np


class DataLeakageError(Exception):
    """當回測中發現預測器接觸到未來數據（當期或之後的開獎結果）時拋出"""
    pass


@dataclass
class PredictionResult:
    """單次預測結果"""
    draw_id: str
    draw_date: str
    predicted_numbers: List[int]
    predicted_special: Optional[int]
    actual_numbers: List[int]
    actual_special: Optional[int]
    matches: int
    matched_numbers: List[int]
    is_win: bool  # >= 3 matches
    confidence: float
    method_name: str
    window_size: int
    training_periods: int


@dataclass
class BacktestSummary:
    """回測摘要統計"""
    lottery_type: str
    method_name: str
    window_size: int
    test_periods: int
    win_count: int
    win_rate: float
    avg_matches: float
    max_matches: int
    total_matches: int
    # 用戶友善指標
    periods_per_win: float  # 平均幾期中一次
    expected_cost_per_win: float  # 預期中獎成本
    # 時間資訊
    test_start_date: str
    test_end_date: str
    backtest_timestamp: str


class BaseStrategy(ABC):
    """
    預測策略基類 - 所有預測方法都需要繼承此類
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """策略名稱"""
        pass

    @property
    @abstractmethod
    def optimal_window(self) -> int:
        """最佳訓練窗口大小"""
        pass

    @property
    def supported_lottery_types(self) -> List[str]:
        """支援的彩票類型"""
        return ['BIG_LOTTO', 'DAILY_539', 'POWER_LOTTO']

    @abstractmethod
    def predict(self, history: List[Dict], lottery_rules: Dict) -> Dict:
        """
        預測下一期號碼

        Args:
            history: 歷史數據 (新→舊排序，只包含預測目標之前的數據)
            lottery_rules: 彩票規則

        Returns:
            {
                'numbers': List[int],  # 預測號碼
                'special': Optional[int],  # 特別號 (如適用)
                'confidence': float  # 信心度 0-1
            }
        """
        pass


class StrategyAdapter:
    """
    策略適配器 - 將現有的預測函數包裝成標準介面
    """

    def __init__(self, name: str, predict_func: Callable, optimal_window: int = 100):
        self._name = name
        self._predict_func = predict_func
        self._optimal_window = optimal_window

    @property
    def name(self) -> str:
        return self._name

    @property
    def optimal_window(self) -> int:
        return self._optimal_window

    def predict(self, history: List[Dict], lottery_rules: Dict) -> Dict:
        return self._predict_func(history, lottery_rules)


class RollingBacktester:
    """
    滾動回測器 - 標準化的回測執行引擎

    P0 優化：支援可配置的中獎門檻 (min_match)
    - min_match=3: 傳統標準，符合台彩官方最低獎項
    - min_match=2: 寬鬆標準，更能區分預測方法好壞
    """

    # 各彩種的預設中獎門檻
    # 今彩539 改為中2個（39選5，隨機中2個機率約9.3%，門檻較低更能區分方法好壞）
    DEFAULT_WIN_THRESHOLDS = {
        'BIG_LOTTO': 3,      # 中3個以上（49選6）
        'DAILY_539': 2,      # 中2個以上（39選5）⭐ 調整
        'POWER_LOTTO': 3,    # 中3個以上（38選6）
    }

    # 各彩種的隨機基準線（用於評估預測方法是否有效）
    RANDOM_BASELINES = {
        # min_match=2 的隨機中獎機率
        'BIG_LOTTO': {'match_2': 0.085, 'match_3': 0.012},      # 6選49
        'DAILY_539': {'match_2': 0.085, 'match_3': 0.012},      # 5選39
        'POWER_LOTTO': {'match_2': 0.095, 'match_3': 0.015},    # 6選38
    }

    # 各彩種的單注價格
    BET_PRICES = {
        'BIG_LOTTO': 50,
        'DAILY_539': 50,
        'POWER_LOTTO': 100,
    }

    def __init__(self, results_dir: str = None):
        """
        初始化回測器

        Args:
            results_dir: 結果存儲目錄
        """
        if results_dir is None:
            results_dir = os.path.join(
                os.path.dirname(__file__), '..', 'data', 'backtest_results'
            )
        self.results_dir = results_dir
        os.makedirs(results_dir, exist_ok=True)

    def run(self,
            strategy: BaseStrategy,
            draws: List[Dict],
            lottery_rules: Dict,
            lottery_type: str,
            test_year: int = 2025,
            window_override: int = None,
            min_match: int = None,
            verbose: bool = True) -> BacktestSummary:
        """
        執行滾動回測

        Args:
            strategy: 預測策略
            draws: 所有歷史數據 (新→舊排序)
            lottery_rules: 彩票規則
            lottery_type: 彩票類型
            test_year: 測試年份
            window_override: 覆蓋策略的最佳窗口
            min_match: 中獎門檻（預設使用彩種預設值，可設為2降低門檻）
            verbose: 是否顯示進度

        Returns:
            回測摘要
        """
        window = window_override or strategy.optimal_window
        win_threshold = min_match if min_match is not None else self.DEFAULT_WIN_THRESHOLDS.get(lottery_type, 3)
        bet_price = self.BET_PRICES.get(lottery_type, 50)

        # 分離測試集和訓練集
        test_draws = self._filter_by_year(draws, test_year)
        if not test_draws:
            raise ValueError(f"找不到 {test_year} 年的數據")

        if verbose:
            print(f"\n{'='*60}")
            print(f"滾動回測: {strategy.name}")
            print(f"{'='*60}")
            print(f"彩種: {lottery_type}")
            print(f"測試年份: {test_year}")
            print(f"測試期數: {len(test_draws)}")
            print(f"訓練窗口: {window}")
            print(f"中獎門檻: >= {win_threshold} 個號碼")
            print(f"-" * 60)

        results = []
        win_count = 0
        total_matches = 0
        max_matches = 0

        for i, target in enumerate(test_draws):
            # 關鍵：只使用目標期之前的數據
            # draws 是新→舊排序，target 在 draws 中的位置之後的所有數據都是之前的
            target_idx = self._find_draw_index(draws, target['draw'])
            if target_idx < 0:
                continue

            # 取得目標期之前的歷史數據 (嚴格不包含 target_idx)
            available_history = draws[target_idx + 1:]
            
            # ✨ 誠實保障：二次驗證 (Secondary Integrity Check)
            # 確保 history 中絕對不含當期期號
            for d in available_history:
                if d['draw'] == target['draw']:
                    raise DataLeakageError(f"CRITICAL: Data Leakage in {target['draw']}! history includes target draw.")

            if len(available_history) < window:
                if verbose:
                    print(f"  跳過 {target['draw']}: 歷史數據不足 ({len(available_history)} < {window})")
                continue

            # 使用指定窗口大小的歷史數據
            training_data = available_history[:window]

            try:
                # 執行預測
                prediction = strategy.predict(training_data, lottery_rules)
                predicted = set(prediction['numbers'])
                actual = set(target['numbers'])

                matches = len(predicted & actual)
                matched_nums = sorted(predicted & actual)
                is_win = matches >= win_threshold

                total_matches += matches
                max_matches = max(max_matches, matches)
                if is_win:
                    win_count += 1

                result = PredictionResult(
                    draw_id=target['draw'],
                    draw_date=target['date'],
                    predicted_numbers=sorted(predicted),
                    predicted_special=prediction.get('special'),
                    actual_numbers=sorted(actual),
                    actual_special=target.get('special_number') or target.get('special'),
                    matches=matches,
                    matched_numbers=matched_nums,
                    is_win=is_win,
                    confidence=prediction.get('confidence', 0.5),
                    method_name=strategy.name,
                    window_size=window,
                    training_periods=len(training_data)
                )
                results.append(result)

                # 進度報告
                if verbose and (i + 1) % 20 == 0:
                    current_win_rate = win_count / len(results) * 100
                    current_avg = total_matches / len(results)
                    print(f"  進度: {i+1}/{len(test_draws)}, "
                          f"中獎率: {current_win_rate:.2f}%, "
                          f"平均匹配: {current_avg:.2f}")

            except Exception as e:
                if verbose:
                    print(f"  錯誤 {target['draw']}: {e}")
                continue

        # 計算摘要統計
        test_count = len(results)
        if test_count == 0:
            raise ValueError("沒有有效的測試結果")

        win_rate = win_count / test_count
        avg_matches = total_matches / test_count
        periods_per_win = test_count / win_count if win_count > 0 else float('inf')
        expected_cost = periods_per_win * bet_price

        summary = BacktestSummary(
            lottery_type=lottery_type,
            method_name=strategy.name,
            window_size=window,
            test_periods=test_count,
            win_count=win_count,
            win_rate=win_rate,
            avg_matches=avg_matches,
            max_matches=max_matches,
            total_matches=total_matches,
            periods_per_win=periods_per_win,
            expected_cost_per_win=expected_cost,
            test_start_date=results[-1].draw_date if results else '',
            test_end_date=results[0].draw_date if results else '',
            backtest_timestamp=datetime.now().isoformat()
        )

        # 顯示結果
        if verbose:
            print(f"\n{'='*60}")
            print("回測結果")
            print(f"{'='*60}")
            print(f"  測試期數: {summary.test_periods}")
            print(f"  中獎次數: {summary.win_count}")
            print(f"  中獎率: {summary.win_rate*100:.2f}%")
            print(f"  平均匹配: {summary.avg_matches:.2f}")
            print(f"  最高匹配: {summary.max_matches}")
            print(f"\n用戶友善指標:")
            print(f"  每 {summary.periods_per_win:.1f} 期中 1 次")
            print(f"  預期每次中獎成本: ${summary.expected_cost_per_win:.0f}")

        # 保存結果
        self._save_results(strategy.name, lottery_type, test_year, summary, results)

        return summary

    def run_multi_bet(self,
                      draws: List[Dict],
                      lottery_rules: Dict,
                      lottery_type: str,
                      num_bets: int = 6,
                      test_year: int = 2025,
                      min_match: int = None,
                      verbose: bool = True) -> BacktestSummary:
        """
        執行多注覆蓋策略回測

        Args:
            min_match: 中獎門檻（預設3，可設為2降低門檻）

        判定標準：任一注中 >= min_match 個視為中獎
        """
        from .multi_bet_optimizer import MultiBetOptimizer

        optimizer = MultiBetOptimizer()
        win_threshold = min_match if min_match is not None else self.DEFAULT_WIN_THRESHOLDS.get(lottery_type, 3)
        bet_price = self.BET_PRICES.get(lottery_type, 50)

        test_draws = self._filter_by_year(draws, test_year)
        if not test_draws:
            raise ValueError(f"找不到 {test_year} 年的數據")

        if verbose:
            print(f"\n{'='*60}")
            print(f"多注覆蓋回測: {num_bets} 注")
            print(f"{'='*60}")
            print(f"彩種: {lottery_type}")
            print(f"測試年份: {test_year}")
            print(f"測試期數: {len(test_draws)}")
            print(f"-" * 60)

        results = []
        win_count = 0
        total_best_matches = 0

        for i, target in enumerate(test_draws):
            target_idx = self._find_draw_index(draws, target['draw'])
            if target_idx < 0:
                continue

            available_history = draws[target_idx + 1:]
            if len(available_history) < 100:
                continue

            try:
                prediction = optimizer.generate_diversified_bets(
                    available_history, lottery_rules, num_bets
                )

                actual = set(target['numbers'])
                best_match = 0
                best_bet_idx = -1

                for idx, bet in enumerate(prediction['bets']):
                    matches = len(set(bet['numbers']) & actual)
                    if matches > best_match:
                        best_match = matches
                        best_bet_idx = idx

                total_best_matches += best_match
                is_win = best_match >= win_threshold
                if is_win:
                    win_count += 1

                results.append({
                    'draw_id': target['draw'],
                    'best_match': best_match,
                    'is_win': is_win
                })

                if verbose and (i + 1) % 20 == 0:
                    current_win_rate = win_count / len(results) * 100
                    print(f"  進度: {i+1}/{len(test_draws)}, "
                          f"中獎率: {current_win_rate:.2f}%")

            except Exception as e:
                if verbose:
                    print(f"  錯誤 {target['draw']}: {e}")
                continue

        test_count = len(results)
        win_rate = win_count / test_count if test_count > 0 else 0
        avg_matches = total_best_matches / test_count if test_count > 0 else 0
        periods_per_win = test_count / win_count if win_count > 0 else float('inf')
        expected_cost = periods_per_win * bet_price * num_bets

        summary = BacktestSummary(
            lottery_type=lottery_type,
            method_name=f'multi_bet_{num_bets}',
            window_size=0,
            test_periods=test_count,
            win_count=win_count,
            win_rate=win_rate,
            avg_matches=avg_matches,
            max_matches=max(r['best_match'] for r in results) if results else 0,
            total_matches=total_best_matches,
            periods_per_win=periods_per_win,
            expected_cost_per_win=expected_cost,
            test_start_date=test_draws[-1]['date'] if test_draws else '',
            test_end_date=test_draws[0]['date'] if test_draws else '',
            backtest_timestamp=datetime.now().isoformat()
        )

        if verbose:
            print(f"\n{'='*60}")
            print("回測結果")
            print(f"{'='*60}")
            print(f"  測試期數: {summary.test_periods}")
            print(f"  中獎次數: {summary.win_count}")
            print(f"  中獎率: {summary.win_rate*100:.2f}%")
            print(f"  平均最佳匹配: {summary.avg_matches:.2f}")
            print(f"\n用戶友善指標:")
            print(f"  每 {summary.periods_per_win:.1f} 期中 1 次")
            print(f"  預期每次中獎成本: ${summary.expected_cost_per_win:.0f} ({num_bets}注)")

        return summary

    def compare_methods(self,
                        draws: List[Dict],
                        lottery_rules: Dict,
                        lottery_type: str,
                        test_year: int = 2025,
                        min_match: int = None,
                        verbose: bool = True) -> List[BacktestSummary]:
        """
        比較所有可用的預測方法

        Args:
            min_match: 中獎門檻（預設使用彩種預設值，可設為2降低門檻）

        Returns:
            按中獎率排序的回測摘要列表
        """
        strategies = self._get_all_strategies()
        results = []

        win_threshold = min_match if min_match is not None else self.DEFAULT_WIN_THRESHOLDS.get(lottery_type, 3)

        if verbose:
            print(f"\n{'='*60}")
            print(f"方法比較: {lottery_type} ({test_year}年)")
            print(f"中獎門檻: >= {win_threshold} 個號碼")
            print(f"{'='*60}")
            print(f"共 {len(strategies)} 個策略待測試")

        for strategy in strategies:
            try:
                summary = self.run(
                    strategy=strategy,
                    draws=draws,
                    lottery_rules=lottery_rules,
                    lottery_type=lottery_type,
                    test_year=test_year,
                    min_match=min_match,
                    verbose=False
                )
                results.append(summary)

                if verbose:
                    print(f"  {strategy.name}: {summary.win_rate*100:.2f}% "
                          f"(平均 {summary.avg_matches:.2f})")

            except Exception as e:
                if verbose:
                    print(f"  {strategy.name}: 失敗 - {e}")

        # 按中獎率排序
        results.sort(key=lambda x: -x.win_rate)

        if verbose and results:
            print(f"\n{'='*60}")
            print("排名結果")
            print(f"{'='*60}")
            for i, r in enumerate(results[:10], 1):
                print(f"  {i}. {r.method_name} (窗口={r.window_size}): "
                      f"{r.win_rate*100:.2f}%, 每{r.periods_per_win:.1f}期中1次")

        return results

    def _filter_by_year(self, draws: List[Dict], year: int) -> List[Dict]:
        """篩選指定年份的開獎記錄"""
        year_str = str(year)
        roc_year = str(year - 1911)  # 民國年

        return [
            d for d in draws
            if d['date'].startswith(year_str) or d['date'].startswith(roc_year)
        ]

    def _find_draw_index(self, draws: List[Dict], draw_id: str) -> int:
        """在 draws 列表中找到指定期號的索引"""
        for i, d in enumerate(draws):
            if d['draw'] == draw_id:
                return i
        return -1

    def _get_all_strategies(self) -> List[StrategyAdapter]:
        """獲取所有可用的預測策略"""
        from .unified_predictor import prediction_engine
        from .enhanced_predictor import EnhancedPredictor
        from .gap_predictor import GapAnalysisPredictor, ConsensusPredictor
        from .anti_consensus_predictor import AntiConsensusPredictor, HighValuePredictor
        from .daily539_predictor import daily539_predictor

        enhanced = EnhancedPredictor()
        gap_predictor = GapAnalysisPredictor()
        consensus_predictor = ConsensusPredictor()
        anti_consensus = AntiConsensusPredictor()
        high_value = HighValuePredictor()

        strategies = [
            # 統一預測引擎方法
            StrategyAdapter('zone_balance', prediction_engine.zone_balance_predict, 500),
            StrategyAdapter('zone_balance_200', prediction_engine.zone_balance_predict, 200),
            StrategyAdapter('sum_range', prediction_engine.sum_range_predict, 100),
            StrategyAdapter('sum_range_300', prediction_engine.sum_range_predict, 300),
            StrategyAdapter('hot_cold_mix', prediction_engine.hot_cold_mix_predict, 100),
            StrategyAdapter('trend_predict', prediction_engine.trend_predict, 300),
            StrategyAdapter('bayesian', prediction_engine.bayesian_predict, 300),
            StrategyAdapter('monte_carlo', prediction_engine.monte_carlo_predict, 200),
            StrategyAdapter('ensemble', prediction_engine.ensemble_predict, 200),
            StrategyAdapter('odd_even_balance', prediction_engine.odd_even_balance_predict, 200),
            # 增強型預測器方法
            StrategyAdapter('cold_comeback', enhanced.cold_number_comeback_predict, 100),
            StrategyAdapter('consecutive_friendly', enhanced.consecutive_friendly_predict, 100),
            StrategyAdapter('constrained', enhanced.constrained_predict, 100),
            StrategyAdapter('multi_window', enhanced.multi_window_fusion_predict, 100),
            StrategyAdapter('coverage_opt', enhanced.coverage_optimized_predict, 100),
            StrategyAdapter('enhanced_ensemble', enhanced.enhanced_ensemble_predict, 100),
            # P0 新增：間隔分析和共識投票
            StrategyAdapter('gap_analysis', gap_predictor.predict, 300),
            StrategyAdapter('gap_analysis_500', gap_predictor.predict, 500),
            StrategyAdapter('consensus', consensus_predictor.predict, 200),
            StrategyAdapter('consensus_300', consensus_predictor.predict, 300),
            # P1 新增：反共識策略
            StrategyAdapter('anti_consensus', anti_consensus.predict, 200),
            StrategyAdapter('contrarian', anti_consensus.predict_contrarian, 200),
            StrategyAdapter('high_value', high_value.predict, 200),
            # P2 新增：今彩539專用方法
            StrategyAdapter('539_constraint', daily539_predictor.constraint_predict, 100),
            StrategyAdapter('539_constraint_200', daily539_predictor.constraint_predict, 200),
            StrategyAdapter('539_cycle', daily539_predictor.cycle_predict, 100),
            StrategyAdapter('539_cycle_200', daily539_predictor.cycle_predict, 200),
            StrategyAdapter('539_consecutive', daily539_predictor.consecutive_predict, 100),
            StrategyAdapter('539_tail', daily539_predictor.tail_number_predict, 100),
            StrategyAdapter('539_zone_opt', daily539_predictor.zone_optimized_predict, 100),
            StrategyAdapter('539_zone_opt_200', daily539_predictor.zone_optimized_predict, 200),
            StrategyAdapter('539_hot_cold_alt', daily539_predictor.hot_cold_alternate_predict, 100),
            StrategyAdapter('539_comprehensive', daily539_predictor.comprehensive_predict, 100),
            StrategyAdapter('539_comprehensive_200', daily539_predictor.comprehensive_predict, 200),
            # P3 新增：進階組合約束方法
            StrategyAdapter('539_adv_constraint', daily539_predictor.advanced_constraint_predict, 100),
            StrategyAdapter('539_adv_constraint_200', daily539_predictor.advanced_constraint_predict, 200),
            StrategyAdapter('539_adv_constraint_300', daily539_predictor.advanced_constraint_predict, 300),
            StrategyAdapter('539_ac_optimized', daily539_predictor.ac_optimized_predict, 100),
            StrategyAdapter('539_ac_optimized_200', daily539_predictor.ac_optimized_predict, 200),
            StrategyAdapter('539_pattern_match', daily539_predictor.pattern_match_predict, 200),
            StrategyAdapter('539_pattern_match_300', daily539_predictor.pattern_match_predict, 300),
            # P4 新增：多方法組合預測器
            StrategyAdapter('539_ensemble_voting', daily539_predictor.ensemble_voting_predict, 200),
            StrategyAdapter('539_best_duo', daily539_predictor.best_duo_predict, 200),
            StrategyAdapter('539_dynamic_ensemble', daily539_predictor.dynamic_ensemble_predict, 200),
        ]

        return strategies

    def _save_results(self, method_name: str, lottery_type: str, year: int,
                     summary: BacktestSummary, details: List[PredictionResult]):
        """保存回測結果"""
        filename = f"{lottery_type}_{method_name}_{year}.json"
        filepath = os.path.join(self.results_dir, filename)

        def convert_numpy(obj):
            """轉換 numpy 類型為 Python 原生類型"""
            if isinstance(obj, np.integer):
                return int(obj)
            elif isinstance(obj, np.floating):
                return float(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, dict):
                return {k: convert_numpy(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_numpy(v) for v in obj]
            return obj

        data = {
            'summary': convert_numpy(asdict(summary)),
            'details': [convert_numpy(asdict(d)) for d in details]
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_results(self, method_name: str, lottery_type: str, year: int) -> Dict:
        """載入已保存的回測結果"""
        filename = f"{lottery_type}_{method_name}_{year}.json"
        filepath = os.path.join(self.results_dir, filename)

        if not os.path.exists(filepath):
            return None

        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)


# 便捷函數
def quick_backtest(lottery_type: str = 'BIG_LOTTO', test_year: int = 2025):
    """快速執行所有方法的比較回測"""
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

    from database import DatabaseManager
    from common import get_lottery_rules

    db = DatabaseManager(db_path=os.path.join(
        os.path.dirname(__file__), '..', 'data', 'lottery_v2.db'
    ))
    draws = db.get_all_draws(lottery_type)
    rules = get_lottery_rules(lottery_type)

    backtester = RollingBacktester()
    return backtester.compare_methods(draws, rules, lottery_type, test_year)


if __name__ == '__main__':
    quick_backtest()
