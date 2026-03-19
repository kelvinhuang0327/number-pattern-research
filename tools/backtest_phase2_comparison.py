#!/usr/bin/env python3
"""
Phase 2 回測比較腳本

比較升級前後的策略表現：
1. 基線策略 (Zone Balance 雙注)
2. Phase 1 策略 (熱號+共現 + Zone Balance)
3. Phase 2 策略 (投票集成 + Zone Balance)
"""
import sys
import os
from collections import Counter
from typing import List, Dict

# Add project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from models.unified_predictor import UnifiedPredictionEngine
from database import DatabaseManager
from common import get_lottery_rules
from tools.hot_cooccurrence_analyzer import HotCooccurrenceAnalyzer
from tools.auto_optimizer_v2 import IntegratedPredictor


class Phase2Comparison:
    """Phase 2 回測比較"""
    
    def __init__(self, lottery_type: str = 'BIG_LOTTO'):
        self.lottery_type = lottery_type
        self.db = DatabaseManager(
            db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
        )
        self.rules = get_lottery_rules(lottery_type)
        self.engine = UnifiedPredictionEngine()
        self.analyzer = HotCooccurrenceAnalyzer(lottery_type)
        self.predictor = IntegratedPredictor(lottery_type)
        
    def get_data(self) -> List[Dict]:
        """獲取數據 (ASC)"""
        draws_desc = self.db.get_all_draws(lottery_type=self.lottery_type)
        return list(reversed(draws_desc))
    
    def _is_win(self, main_matches: int, special_match: bool) -> bool:
        """判斷是否中獎"""
        if main_matches >= 3:
            return True
        if main_matches == 2 and special_match:
            return True
        return False
    
    def run_baseline(self, year: int = 2025) -> Dict:
        """
        基線策略: Zone Balance 500 + Zone Balance 200 雙注
        """
        all_draws = self.get_data()
        test_draws = [d for d in all_draws if d['date'].startswith(str(year))]
        
        if not test_draws:
            return {'error': f'No data for {year}'}
        
        start_idx = all_draws.index(test_draws[0])
        
        total = wins = bet1_wins = bet2_wins = 0
        
        for i, target in enumerate(test_draws):
            current_idx = start_idx + i
            history = all_draws[:current_idx]
            
            # Bet 1: Zone Balance 500
            try:
                result = self.engine.zone_balance_predict(history[-500:], self.rules)
                bet1 = sorted(result['numbers'])
            except:
                bet1 = [1, 2, 3, 4, 5, 6]
            
            # Bet 2: Zone Balance 200
            try:
                result = self.engine.zone_balance_predict(history[-200:], self.rules)
                bet2 = sorted(result['numbers'])
            except:
                bet2 = [1, 2, 3, 4, 5, 6]
            
            actual = target['numbers']
            special = target['special']
            
            m1 = len(set(bet1) & set(actual))
            s1 = special in bet1
            m2 = len(set(bet2) & set(actual))
            s2 = special in bet2
            
            w1 = self._is_win(m1, s1)
            w2 = self._is_win(m2, s2)
            
            if w1: bet1_wins += 1
            if w2: bet2_wins += 1
            if w1 or w2: wins += 1
            total += 1
        
        return {
            'strategy': '基線 (Zone Balance 500+200)',
            'total': total,
            'wins': wins,
            'bet1_wins': bet1_wins,
            'bet2_wins': bet2_wins,
            'win_rate': wins / total if total > 0 else 0
        }
    
    def run_phase1(self, year: int = 2025) -> Dict:
        """
        Phase 1 策略: 熱號+共現 + Zone Balance 500
        """
        all_draws = self.get_data()
        test_draws = [d for d in all_draws if d['date'].startswith(str(year))]
        
        if not test_draws:
            return {'error': f'No data for {year}'}
        
        start_idx = all_draws.index(test_draws[0])
        
        total = wins = bet1_wins = bet2_wins = 0
        
        for i, target in enumerate(test_draws):
            current_idx = start_idx + i
            history = all_draws[:current_idx]
            
            # Bet 1: 熱號 + 共現
            hot_freq = self.analyzer.get_hot_numbers(history, 50)
            hot_nums = [num for num, _ in hot_freq]
            co_matrix = self.analyzer.build_cooccurrence_matrix(history, 100)
            bet1 = self.analyzer.apply_cooccurrence_rules(
                hot_nums, co_matrix, self.rules['pickCount']
            )
            
            # Bet 2: Zone Balance 500
            try:
                result = self.engine.zone_balance_predict(history[-500:], self.rules)
                bet2 = sorted(result['numbers'])
            except:
                bet2 = [1, 2, 3, 4, 5, 6]
            
            actual = target['numbers']
            special = target['special']
            
            m1 = len(set(bet1) & set(actual))
            s1 = special in bet1
            m2 = len(set(bet2) & set(actual))
            s2 = special in bet2
            
            w1 = self._is_win(m1, s1)
            w2 = self._is_win(m2, s2)
            
            if w1: bet1_wins += 1
            if w2: bet2_wins += 1
            if w1 or w2: wins += 1
            total += 1
        
        return {
            'strategy': 'Phase 1 (熱號+共現 + Zone Balance)',
            'total': total,
            'wins': wins,
            'bet1_wins': bet1_wins,
            'bet2_wins': bet2_wins,
            'win_rate': wins / total if total > 0 else 0
        }
    
    def run_phase2(self, year: int = 2025) -> Dict:
        """
        Phase 2 策略: 投票集成 + Zone Balance
        """
        result = self.predictor.backtest(year)
        return {
            'strategy': 'Phase 2 (投票集成 + Zone Balance)',
            'total': result['total'],
            'wins': result['wins'],
            'bet1_wins': result['bet1_wins'],
            'bet2_wins': result['bet2_wins'],
            'win_rate': result['win_rate']
        }
    
    def run_comparison(self, year: int = 2025):
        """執行完整比較"""
        print("=" * 100)
        print(f"📊 Phase 2 策略回測比較 ({self.lottery_type}, 年份: {year})")
        print("=" * 100)
        
        print("\n⏳ 正在執行基線策略回測...")
        baseline = self.run_baseline(year)
        
        print("⏳ 正在執行 Phase 1 策略回測...")
        phase1 = self.run_phase1(year)
        
        print("⏳ 正在執行 Phase 2 策略回測...")
        phase2 = self.run_phase2(year)
        
        results = [baseline, phase1, phase2]
        
        print("\n" + "=" * 100)
        print("📈 回測結果比較")
        print("=" * 100)
        print(f"{'策略':<40} {'總期數':<10} {'第一注':<10} {'第二注':<10} {'總勝':<10} {'勝率':<10}")
        print("-" * 100)
        
        for r in results:
            print(f"{r['strategy']:<40} {r['total']:<10} {r['bet1_wins']:<10} "
                  f"{r['bet2_wins']:<10} {r['wins']:<10} {r['win_rate']*100:>6.2f}%")
        
        print("=" * 100)
        
        # 計算提升幅度
        baseline_rate = baseline['win_rate']
        phase1_rate = phase1['win_rate']
        phase2_rate = phase2['win_rate']
        
        p1_improvement = ((phase1_rate - baseline_rate) / baseline_rate * 100) if baseline_rate > 0 else 0
        p2_improvement = ((phase2_rate - baseline_rate) / baseline_rate * 100) if baseline_rate > 0 else 0
        p2_vs_p1 = ((phase2_rate - phase1_rate) / phase1_rate * 100) if phase1_rate > 0 else 0
        
        print("\n📊 提升幅度分析:")
        print(f"  Phase 1 vs 基線: {'+' if p1_improvement >= 0 else ''}{p1_improvement:.1f}%")
        print(f"  Phase 2 vs 基線: {'+' if p2_improvement >= 0 else ''}{p2_improvement:.1f}%")
        print(f"  Phase 2 vs Phase 1: {'+' if p2_vs_p1 >= 0 else ''}{p2_vs_p1:.1f}%")
        
        # 最佳策略
        best = max(results, key=lambda x: x['win_rate'])
        print(f"\n🏆 最佳策略: {best['strategy']}")
        print(f"   勝率: {best['win_rate']*100:.2f}% ({best['wins']}/{best['total']})")
        print("=" * 100)
        
        return results


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Phase 2 回測比較')
    parser.add_argument('--lottery', '-l', type=str, default='BIG_LOTTO',
                        choices=['BIG_LOTTO', 'POWER_LOTTO', 'DAILY_539'],
                        help='彩票類型')
    parser.add_argument('--year', '-y', type=int, default=2025,
                        help='回測年份')
    
    args = parser.parse_args()
    
    comparison = Phase2Comparison(args.lottery)
    comparison.run_comparison(args.year)


if __name__ == '__main__':
    main()
