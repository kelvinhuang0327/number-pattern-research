#!/usr/bin/env python3
"""
熱號窗口回測腳本 (Hot Number Window Backtest)

Phase 1.4：測試不同窗口大小的勝率表現
- 測試窗口：10, 20, 30, 40, 50, 60
- 評估指標：勝率、平均命中數、收益
"""
import sys
import os
import io
import argparse
from collections import Counter
from typing import List, Dict, Tuple

# Add project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery-api'))

from models.unified_predictor import UnifiedPredictionEngine
from database import DatabaseManager
from common import get_lottery_rules
from tools.hot_cooccurrence_analyzer import HotCooccurrenceAnalyzer


class HotWindowBacktester:
    """
    熱號窗口回測器
    
    測試不同熱號窗口大小對預測準確率的影響
    """
    
    def __init__(self, lottery_type: str = 'BIG_LOTTO'):
        self.lottery_type = lottery_type
        self.db = DatabaseManager(
            db_path=os.path.join(project_root, 'lottery-api', 'data', 'lottery_v2.db')
        )
        self.rules = get_lottery_rules(lottery_type)
        self.engine = UnifiedPredictionEngine()
        self.analyzer = HotCooccurrenceAnalyzer(lottery_type)
        
    def get_data(self) -> List[Dict]:
        """獲取歷史數據 (ASC)"""
        draws_desc = self.db.get_all_draws(lottery_type=self.lottery_type)
        return list(reversed(draws_desc))
    
    def _is_win(self, main_matches: int, special_match: bool) -> bool:
        """判斷是否中獎 (≥3 中或 2中+特別號)"""
        if main_matches >= 3:
            return True
        if main_matches == 2 and special_match:
            return True
        return False
    
    def backtest_window(
        self, 
        window_size: int, 
        year: int = 2025,
        use_cooccurrence: bool = False,
        co_window: int = 100,
        verbose: bool = False
    ) -> Dict:
        """
        回測單一窗口大小
        
        Args:
            window_size: 熱號窗口大小
            year: 回測年份
            use_cooccurrence: 是否使用共現分析優化
            co_window: 共現分析窗口
            verbose: 是否輸出詳細信息
            
        Returns:
            回測結果
        """
        all_draws = self.get_data()
        test_draws = [d for d in all_draws if d['date'].startswith(str(year))]
        
        if not test_draws:
            return {'error': f'No data for {year}'}
        
        start_idx = all_draws.index(test_draws[0])
        
        total_rounds = 0
        wins = 0
        total_matches = 0
        match_distribution = Counter()
        
        for i, target_draw in enumerate(test_draws):
            current_idx = start_idx + i
            history = all_draws[:current_idx]
            
            if len(history) < window_size:
                continue
            
            # 取得熱號
            hot_freq = self.analyzer.get_hot_numbers(history, window_size)
            hot_nums = [num for num, freq in hot_freq]
            
            if use_cooccurrence:
                # 使用共現分析優化
                co_matrix = self.analyzer.build_cooccurrence_matrix(history, co_window)
                prediction = self.analyzer.apply_cooccurrence_rules(
                    hot_nums, co_matrix, self.rules['pickCount']
                )
            else:
                # 純熱號策略
                prediction = sorted(hot_nums[:self.rules['pickCount']])
            
            # 評估結果
            actual = target_draw['numbers']
            special = target_draw['special']
            
            main_matches = len(set(prediction) & set(actual))
            special_match = special in prediction
            
            if self._is_win(main_matches, special_match):
                wins += 1
            
            total_matches += main_matches
            match_distribution[main_matches] += 1
            total_rounds += 1
            
            if verbose and main_matches >= 3:
                print(f"  期數 {target_draw['draw']}: 命中 {main_matches} 個")
        
        win_rate = wins / total_rounds if total_rounds > 0 else 0
        avg_matches = total_matches / total_rounds if total_rounds > 0 else 0
        
        return {
            'window_size': window_size,
            'use_cooccurrence': use_cooccurrence,
            'total_rounds': total_rounds,
            'wins': wins,
            'win_rate': win_rate,
            'avg_matches': avg_matches,
            'match_distribution': dict(match_distribution)
        }
    
    def run_comparison(
        self, 
        windows: List[int] = [10, 20, 30, 40, 50, 60],
        year: int = 2025,
        test_cooccurrence: bool = True
    ) -> List[Dict]:
        """
        比較多個窗口大小
        
        Args:
            windows: 要測試的窗口大小列表
            year: 回測年份
            test_cooccurrence: 是否同時測試共現優化版本
            
        Returns:
            所有配置的回測結果
        """
        results = []
        
        print("=" * 100)
        print(f"🔍 熱號窗口回測比較 ({self.lottery_type}, 年份: {year})")
        print("=" * 100)
        print(f"{'窗口大小':<12} {'策略':<15} {'總期數':<10} {'中獎期數':<10} {'勝率':<12} {'平均命中':<10}")
        print("-" * 100)
        
        for window in windows:
            # 純熱號策略
            result = self.backtest_window(window, year, use_cooccurrence=False)
            results.append(result)
            
            print(f"{window:<12} {'純熱號':<15} {result['total_rounds']:<10} "
                  f"{result['wins']:<10} {result['win_rate']*100:>6.2f}%     "
                  f"{result['avg_matches']:<10.2f}")
            
            if test_cooccurrence:
                # 熱號 + 共現策略
                result_co = self.backtest_window(window, year, use_cooccurrence=True)
                results.append(result_co)
                
                print(f"{window:<12} {'熱號+共現':<15} {result_co['total_rounds']:<10} "
                      f"{result_co['wins']:<10} {result_co['win_rate']*100:>6.2f}%     "
                      f"{result_co['avg_matches']:<10.2f}")
        
        print("=" * 100)
        
        # 找出最佳配置
        best = max(results, key=lambda x: x['win_rate'])
        strategy = '熱號+共現' if best['use_cooccurrence'] else '純熱號'
        
        print(f"\n🏆 最佳配置: 窗口 {best['window_size']} + {strategy}")
        print(f"   勝率: {best['win_rate']*100:.2f}% ({best['wins']}/{best['total_rounds']})")
        print(f"   平均命中: {best['avg_matches']:.2f}")
        
        return results
    
    def run_combined_strategy(
        self,
        hot_window: int = 50,
        year: int = 2025
    ) -> Dict:
        """
        執行熱號 + Zone Balance 雙注策略回測
        
        Args:
            hot_window: 熱號窗口大小
            year: 回測年份
            
        Returns:
            回測結果
        """
        all_draws = self.get_data()
        test_draws = [d for d in all_draws if d['date'].startswith(str(year))]
        
        if not test_draws:
            return {'error': f'No data for {year}'}
        
        start_idx = all_draws.index(test_draws[0])
        
        total_rounds = 0
        wins = 0
        bet1_wins = 0
        bet2_wins = 0
        
        print("=" * 80)
        print(f"📊 熱號 + Zone Balance 雙注策略回測 (年份: {year})")
        print(f"配置: Bet1=熱號窗口{hot_window} | Bet2=zone_balance_500")
        print("=" * 80)
        
        for i, target_draw in enumerate(test_draws):
            current_idx = start_idx + i
            history = all_draws[:current_idx]
            
            if len(history) < hot_window:
                continue
            
            # Bet 1: 熱號 + 共現
            hot_freq = self.analyzer.get_hot_numbers(history, hot_window)
            hot_nums = [num for num, freq in hot_freq]
            co_matrix = self.analyzer.build_cooccurrence_matrix(history, 100)
            bet1 = self.analyzer.apply_cooccurrence_rules(
                hot_nums, co_matrix, self.rules['pickCount']
            )
            
            # Bet 2: Zone Balance
            try:
                result = self.engine.zone_balance_predict(history[-500:], self.rules)
                bet2 = sorted(result['numbers'])
            except:
                bet2 = [1, 2, 3, 4, 5, 6]
            
            # 評估
            actual = target_draw['numbers']
            special = target_draw['special']
            
            m1 = len(set(bet1) & set(actual))
            s1 = special in bet1
            m2 = len(set(bet2) & set(actual))
            s2 = special in bet2
            
            w1 = self._is_win(m1, s1)
            w2 = self._is_win(m2, s2)
            
            if w1:
                bet1_wins += 1
            if w2:
                bet2_wins += 1
            if w1 or w2:
                wins += 1
            
            total_rounds += 1
        
        win_rate = wins / total_rounds if total_rounds > 0 else 0
        
        print(f"\n回測結束: 共 {total_rounds} 期")
        print(f"第一注 (熱號+共現) 中獎: {bet1_wins} 期 ({bet1_wins/total_rounds*100:.2f}%)")
        print(f"第二注 (Zone Balance) 中獎: {bet2_wins} 期 ({bet2_wins/total_rounds*100:.2f}%)")
        print(f"總中獎期數: {wins}")
        print(f"總勝率: {win_rate*100:.2f}%")
        print("-" * 80)
        
        return {
            'hot_window': hot_window,
            'total_rounds': total_rounds,
            'bet1_wins': bet1_wins,
            'bet2_wins': bet2_wins,
            'total_wins': wins,
            'win_rate': win_rate
        }


def main():
    parser = argparse.ArgumentParser(description='熱號窗口回測')
    parser.add_argument('--lottery', '-l', type=str, default='BIG_LOTTO',
                        choices=['BIG_LOTTO', 'POWER_LOTTO', 'DAILY_539'],
                        help='彩票類型')
    parser.add_argument('--year', '-y', type=int, default=2025,
                        help='回測年份')
    parser.add_argument('--windows', '-w', type=str, default='10,20,30,40,50,60',
                        help='測試窗口大小 (逗號分隔)')
    parser.add_argument('--no-cooccurrence', action='store_true',
                        help='不測試共現優化版本')
    parser.add_argument('--combined', action='store_true',
                        help='執行熱號+Zone Balance雙注策略')
    parser.add_argument('--hot-window', type=int, default=50,
                        help='雙注策略的熱號窗口大小')
    
    args = parser.parse_args()
    
    backtester = HotWindowBacktester(args.lottery)
    
    if args.combined:
        backtester.run_combined_strategy(
            hot_window=args.hot_window,
            year=args.year
        )
    else:
        windows = [int(w.strip()) for w in args.windows.split(',')]
        backtester.run_comparison(
            windows=windows,
            year=args.year,
            test_cooccurrence=not args.no_cooccurrence
        )


if __name__ == '__main__':
    main()
