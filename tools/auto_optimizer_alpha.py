#!/usr/bin/env python3
"""
Auto Optimizer for Lottery Prediction (Alpha 20 Plan)
目標：自動尋找最佳預測策略與參數，挑戰 20% 勝率
"""
import sys
import os
import io
import itertools
import logging
from collections import defaultdict
import numpy as np

# Add project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from models.unified_predictor import UnifiedPredictionEngine
from database import DatabaseManager
from common import get_lottery_rules
from models.backtest_framework import RollingBacktester, StrategyAdapter

# Fix encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AutoOptimizer:
    def __init__(self, lottery_type='BIG_LOTTO'):
        self.lottery_type = lottery_type
        self.db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
        self.db = DatabaseManager(db_path=self.db_path)
        self.rules = get_lottery_rules(lottery_type)
        self.engine = UnifiedPredictionEngine()
        self.backtester = RollingBacktester()
        
    def get_data(self):
        # Get data ASC (Oldest -> Newest) for correct rolling backtest
        draws_desc = self.db.get_all_draws(lottery_type=self.lottery_type)
        return list(reversed(draws_desc))

    def generate_strategy_space(self):
        """生成策略搜索空間"""
        methods = [
            'zone_balance_predict',
            'bayesian_predict',
            'trend_predict',
            'frequency_predict',
            'deviation_predict'
        ]
        
        # Windows to test
        windows = [50, 100, 200, 300, 500]
        
        strategies = []
        for method in methods:
            for window in windows:
                # Create a closure to capture method and window
                def make_predict_func(m_name, w_size):
                    return lambda hist, rules: getattr(self.engine, m_name)(hist[-w_size:], rules)
                
                strategy_name = f"{method.replace('_predict', '')}_{window}"
                strategies.append(StrategyAdapter(
                    name=strategy_name,
                    predict_func=make_predict_func(method, window),
                    optimal_window=window
                ))
        return strategies

    def find_champion_strategy(self, test_year=2025):
        """尋找年度冠軍策略"""
        print(f"🚀 開始自動優化搜索 (年份: {test_year})")
        print(f"目標: 尋找 BIG_LOTTO 勝率最高的策略配置")
        print("-" * 60)

        draws = self.get_data()
        strategies = self.generate_strategy_space()
        
        results = []
        for strategy in strategies:
            try:
                # Suppress verbose output during search
                summary = self.backtester.run(
                    strategy=strategy,
                    draws=draws,
                    lottery_rules=self.rules,
                    lottery_type=self.lottery_type,
                    test_year=test_year,
                    min_match=3, # 普獎門檻
                    verbose=False
                )
                
                results.append({
                    'name': strategy.name,
                    'win_rate': summary.win_rate,
                    'avg_match': summary.avg_matches,
                    'wins': summary.win_count,
                    'total': summary.test_periods
                })
                print(f"✅ {strategy.name:<25} | Win Rate: {summary.win_rate*100:6.2f}% | Avg: {summary.avg_matches:.2f}")
                
            except Exception as e:
                logger.error(f"Strategy {strategy.name} failed: {e}")

        # Sort by Win Rate
        results.sort(key=lambda x: x['win_rate'], reverse=True)
        
        print("\n🏆 優化結果 TOP 5 策略")
        print("=" * 80)
        print(f"{'Rank':<5} | {'Strategy':<30} | {'Win Rate':<10} | {'Wins/Total'}")
        print("-" * 80)
        
        for i, res in enumerate(results[:5]):
            print(f"{i+1:<5} | {res['name']:<30} | {res['win_rate']*100:6.2f}%    | {res['wins']}/{res['total']}")
            
        return results[0]

def main():
    optimizer = AutoOptimizer()
    optimizer.find_champion_strategy()

if __name__ == '__main__':
    main()
