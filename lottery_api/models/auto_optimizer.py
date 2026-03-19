"""
自動優化器 - 自動找出最佳預測配置

功能：
1. 自動測試所有方法 × 所有窗口組合
2. 找出當前最佳配置
3. 定期更新最佳配置
4. 提供 API 接口查詢
"""

import os
import json
from typing import List, Dict, Tuple, Optional
from datetime import datetime
from dataclasses import dataclass, asdict
import numpy as np


@dataclass
class OptimalConfig:
    """最佳配置"""
    lottery_type: str
    method_name: str
    window_size: int
    win_rate: float
    avg_matches: float
    periods_per_win: float
    expected_cost: float
    test_periods: int
    last_updated: str


class AutoOptimizer:
    """自動優化器"""

    # 測試的窗口大小
    WINDOW_SIZES = [50, 100, 150, 200, 300, 500]

    # 各彩種的單注價格
    BET_PRICES = {
        'BIG_LOTTO': 50,
        'DAILY_539': 50,
        'POWER_LOTTO': 100,
    }

    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(__file__), '..', 'data', 'auto_optimal_configs.json'
            )
        self.config_path = config_path
        self._load_configs()

    def _load_configs(self):
        """載入已保存的配置"""
        self.configs = {}
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for lottery_type, config_data in data.items():
                        self.configs[lottery_type] = OptimalConfig(**config_data)
            except:
                pass

    def _save_configs(self):
        """保存配置"""
        data = {
            lottery_type: asdict(config)
            for lottery_type, config in self.configs.items()
        }
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def find_optimal(self,
                     draws: List[Dict],
                     lottery_rules: Dict,
                     lottery_type: str,
                     test_year: int = 2025,
                     verbose: bool = True) -> OptimalConfig:
        """
        找出最佳預測配置

        Args:
            draws: 歷史數據
            lottery_rules: 彩票規則
            lottery_type: 彩票類型
            test_year: 測試年份
            verbose: 是否顯示進度

        Returns:
            最佳配置
        """
        from .unified_predictor import prediction_engine
        from .enhanced_predictor import EnhancedPredictor

        enhanced = EnhancedPredictor()

        # 定義所有方法
        methods = {
            'zone_balance': prediction_engine.zone_balance_predict,
            'sum_range': prediction_engine.sum_range_predict,
            'hot_cold_mix': prediction_engine.hot_cold_mix_predict,
            'trend_predict': prediction_engine.trend_predict,
            'bayesian': prediction_engine.bayesian_predict,
            'monte_carlo': prediction_engine.monte_carlo_predict,
            'ensemble': prediction_engine.ensemble_predict,
            'odd_even_balance': prediction_engine.odd_even_balance_predict,
            'cold_comeback': enhanced.cold_number_comeback_predict,
            'constrained': enhanced.constrained_predict,
            'multi_window': enhanced.multi_window_fusion_predict,
            'coverage_opt': enhanced.coverage_optimized_predict,
        }

        bet_price = self.BET_PRICES.get(lottery_type, 50)

        # 篩選測試數據
        test_draws = self._filter_by_year(draws, test_year)
        if not test_draws:
            raise ValueError(f"找不到 {test_year} 年的數據")

        if verbose:
            print(f"\n{'='*60}")
            print(f"自動優化器 - 尋找最佳配置")
            print(f"{'='*60}")
            print(f"彩種: {lottery_type}")
            print(f"測試年份: {test_year}")
            print(f"測試期數: {len(test_draws)}")
            print(f"方法數: {len(methods)}")
            print(f"窗口選項: {self.WINDOW_SIZES}")
            total_tests = len(methods) * len(self.WINDOW_SIZES)
            print(f"總測試組合: {total_tests}")
            print(f"-" * 60)

        results = []
        tested = 0

        for method_name, method_func in methods.items():
            for window in self.WINDOW_SIZES:
                tested += 1
                try:
                    # 執行快速回測
                    win_count, total_matches, test_count = self._quick_backtest(
                        method_func, draws, test_draws, lottery_rules, window
                    )

                    if test_count > 0:
                        win_rate = win_count / test_count
                        avg_matches = total_matches / test_count
                        periods_per_win = test_count / win_count if win_count > 0 else float('inf')

                        results.append({
                            'method': method_name,
                            'window': window,
                            'win_rate': win_rate,
                            'avg_matches': avg_matches,
                            'periods_per_win': periods_per_win,
                            'test_count': test_count,
                            'win_count': win_count
                        })

                        if verbose and win_rate > 0.03:
                            print(f"  {method_name}({window}): {win_rate*100:.2f}%")

                except Exception as e:
                    if verbose:
                        print(f"  {method_name}({window}): 失敗")

                if verbose and tested % 20 == 0:
                    print(f"  進度: {tested}/{total_tests}")

        if not results:
            raise ValueError("沒有有效的測試結果")

        # 找出最佳
        best = max(results, key=lambda x: (x['win_rate'], x['avg_matches']))

        optimal = OptimalConfig(
            lottery_type=lottery_type,
            method_name=best['method'],
            window_size=best['window'],
            win_rate=best['win_rate'],
            avg_matches=best['avg_matches'],
            periods_per_win=best['periods_per_win'],
            expected_cost=best['periods_per_win'] * bet_price,
            test_periods=best['test_count'],
            last_updated=datetime.now().isoformat()
        )

        # 保存配置
        self.configs[lottery_type] = optimal
        self._save_configs()

        if verbose:
            print(f"\n{'='*60}")
            print("最佳配置")
            print(f"{'='*60}")
            print(f"  方法: {optimal.method_name}")
            print(f"  窗口: {optimal.window_size}")
            print(f"  中獎率: {optimal.win_rate*100:.2f}%")
            print(f"  平均匹配: {optimal.avg_matches:.2f}")
            print(f"  每 {optimal.periods_per_win:.1f} 期中 1 次")
            print(f"  預期成本: ${optimal.expected_cost:.0f}")

            # 顯示 Top 5
            print(f"\nTop 5 配置:")
            sorted_results = sorted(results, key=lambda x: -x['win_rate'])
            for i, r in enumerate(sorted_results[:5], 1):
                print(f"  {i}. {r['method']}({r['window']}): "
                      f"{r['win_rate']*100:.2f}%, 平均{r['avg_matches']:.2f}")

        return optimal

    def _quick_backtest(self, method_func, all_draws: List[Dict],
                       test_draws: List[Dict], lottery_rules: Dict,
                       window: int) -> Tuple[int, int, int]:
        """快速回測"""
        win_count = 0
        total_matches = 0
        test_count = 0

        for target in test_draws:
            target_idx = self._find_draw_index(all_draws, target['draw'])
            if target_idx < 0:
                continue

            available_history = all_draws[target_idx + 1:]
            if len(available_history) < window:
                continue

            try:
                history = available_history[:window]
                result = method_func(history, lottery_rules)
                predicted = set(result['numbers'])
                actual = set(target['numbers'])
                matches = len(predicted & actual)

                total_matches += matches
                if matches >= 3:
                    win_count += 1
                test_count += 1
            except:
                continue

        return win_count, total_matches, test_count

    def _filter_by_year(self, draws: List[Dict], year: int) -> List[Dict]:
        """篩選指定年份"""
        year_str = str(year)
        roc_year = str(year - 1911)
        return [
            d for d in draws
            if d['date'].startswith(year_str) or d['date'].startswith(roc_year)
        ]

    def _find_draw_index(self, draws: List[Dict], draw_id: str) -> int:
        """找到期號索引"""
        for i, d in enumerate(draws):
            if d['draw'] == draw_id:
                return i
        return -1

    def get_optimal(self, lottery_type: str) -> Optional[OptimalConfig]:
        """獲取已保存的最佳配置"""
        return self.configs.get(lottery_type)

    def get_all_configs(self) -> Dict[str, OptimalConfig]:
        """獲取所有配置"""
        return dict(self.configs)

    def predict_with_optimal(self, draws: List[Dict], lottery_rules: Dict,
                            lottery_type: str) -> Dict:
        """使用最佳配置進行預測"""
        config = self.get_optimal(lottery_type)
        if config is None:
            # 使用默認配置
            from .unified_predictor import prediction_engine
            history = draws[:100]
            return prediction_engine.ensemble_predict(history, lottery_rules)

        # 載入對應方法
        from .unified_predictor import prediction_engine
        from .enhanced_predictor import EnhancedPredictor

        enhanced = EnhancedPredictor()

        methods = {
            'zone_balance': prediction_engine.zone_balance_predict,
            'sum_range': prediction_engine.sum_range_predict,
            'hot_cold_mix': prediction_engine.hot_cold_mix_predict,
            'trend_predict': prediction_engine.trend_predict,
            'bayesian': prediction_engine.bayesian_predict,
            'monte_carlo': prediction_engine.monte_carlo_predict,
            'ensemble': prediction_engine.ensemble_predict,
            'odd_even_balance': prediction_engine.odd_even_balance_predict,
            'cold_comeback': enhanced.cold_number_comeback_predict,
            'constrained': enhanced.constrained_predict,
            'multi_window': enhanced.multi_window_fusion_predict,
            'coverage_opt': enhanced.coverage_optimized_predict,
        }

        method_func = methods.get(config.method_name)
        if method_func is None:
            method_func = prediction_engine.ensemble_predict

        history = draws[:config.window_size]
        result = method_func(history, lottery_rules)

        return {
            'numbers': result['numbers'],
            'special': result.get('special'),
            'confidence': result.get('confidence', 0.5),
            'method': config.method_name,
            'window': config.window_size,
            'expected_win_rate': config.win_rate,
            'periods_per_win': config.periods_per_win
        }


# 單例
auto_optimizer = AutoOptimizer()


def run_optimization(lottery_type: str = 'BIG_LOTTO'):
    """執行優化"""
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

    from database import DatabaseManager
    from common import get_lottery_rules

    db = DatabaseManager(db_path=os.path.join(
        os.path.dirname(__file__), '..', 'data', 'lottery_v2.db'
    ))
    draws = db.get_all_draws(lottery_type)
    rules = get_lottery_rules(lottery_type)

    optimizer = AutoOptimizer()
    return optimizer.find_optimal(draws, rules, lottery_type)


if __name__ == '__main__':
    for lottery_type in ['BIG_LOTTO', 'DAILY_539']:
        print(f"\n\n{'#'*70}")
        print(f"# {lottery_type}")
        print(f"{'#'*70}")
        run_optimization(lottery_type)
