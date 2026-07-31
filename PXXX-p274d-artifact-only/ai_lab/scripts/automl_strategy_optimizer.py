#!/usr/bin/env python3
"""
AutoML Strategy Optimizer for Lottery Prediction
Automatically searches for the optimal prediction strategy configuration.

Features:
- Tests all method combinations (1-bet, 2-bet, 3-bet, 4-bet)
- Tests parameter grids (lambda values, window sizes)
- Ranks by Match-3+ rate and Match-4+ count
- Supports BIG_LOTTO and POWER_LOTTO
"""
import os
import sys
import json
import numpy as np
from collections import defaultdict, Counter
from itertools import combinations, product
from datetime import datetime
from typing import List, Dict, Tuple, Optional

project_root = os.getcwd()
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules
from models.unified_predictor import UnifiedPredictionEngine


class TrendPredictor:
    """Configurable Trend predictor with adjustable lambda."""
    def __init__(self, lambda_val: float = 0.05):
        self.lambda_val = lambda_val
        
    def predict(self, history: List[Dict], rules: Dict) -> List[int]:
        pick_count = rules.get('pickCount', 6)
        max_num = rules.get('maxNumber', 49)
        min_num = rules.get('minNumber', 1)
        
        weighted_freq = defaultdict(float)
        for i, draw in enumerate(reversed(history)):
            weight = np.exp(-self.lambda_val * i)
            nums = draw.get('numbers', draw.get('first_zone', []))
            for num in nums:
                weighted_freq[num] += weight
        
        total = sum(weighted_freq.values())
        if total == 0:
            return list(range(min_num, min_num + pick_count))
            
        probs = {n: weighted_freq.get(n, 0) / total for n in range(min_num, max_num + 1)}
        sorted_nums = sorted(probs.items(), key=lambda x: x[1], reverse=True)
        return sorted([n for n, _ in sorted_nums[:pick_count]])


class AutoMLStrategyOptimizer:
    """
    AutoML optimizer for lottery prediction strategies.
    """
    
    def __init__(self, lottery_type: str = 'BIG_LOTTO'):
        self.lottery_type = lottery_type
        self.db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery.db')
        self.db = DatabaseManager(db_path=self.db_path)
        self.all_draws = list(reversed(self.db.get_all_draws(lottery_type=lottery_type)))
        self.rules = get_lottery_rules(lottery_type)
        self.engine = UnifiedPredictionEngine()
        
        # Method registry
        self.base_methods = {
            'markov': lambda h, r: self.engine.markov_predict(h, r)['numbers'][:6],
            'deviation': lambda h, r: self.engine.deviation_predict(h, r)['numbers'][:6],
            'statistical': lambda h, r: self.engine.statistical_predict(h, r)['numbers'][:6],
            'trend': lambda h, r: self.engine.trend_predict(h, r)['numbers'][:6],
            'frequency': lambda h, r: self.engine.frequency_predict(h, r)['numbers'][:6],
            'bayesian': lambda h, r: self.engine.bayesian_predict(h, r)['numbers'][:6],
            'hot_cold_mix': lambda h, r: self.engine.hot_cold_mix_predict(h, r)['numbers'][:6],
        }
        
        # Add Trend variants
        for lam in [0.03, 0.07, 0.10, 0.15]:
            name = f'trend_l{int(lam*100):02d}'
            predictor = TrendPredictor(lambda_val=lam)
            self.base_methods[name] = lambda h, r, p=predictor: p.predict(h, r)
            
    def evaluate_combination(
        self, 
        methods: Tuple[str, ...], 
        periods: int = None,
        window: Optional[int] = None
    ) -> Dict:
        """Evaluate a specific method combination."""
        
        # Use all data if periods not specified
        if periods is None:
            periods = len(self.all_draws) - 50 # Start from 50 to have history
            
        wins = 0
        m4_plus = 0
        total = 0
        method_wins = {m: 0 for m in methods}
        
        for i in range(periods):
            target_idx = len(self.all_draws) - periods + i
            target_draw = self.all_draws[target_idx]
            
            # Apply window if specified
            if window:
                start_idx = max(0, target_idx - window)
                history = self.all_draws[start_idx:target_idx]
            else:
                history = self.all_draws[:target_idx]
                
            if len(history) < 50:  # Need minimum history
                continue
                
            actual = set(target_draw.get('numbers', target_draw.get('first_zone', [])))
            
            best_match = 0
            hit = False
            
            for method_name in methods:
                try:
                    method_func = self.base_methods.get(method_name)
                    if not method_func:
                        continue
                    predicted = method_func(history, self.rules)
                    match = len(set(predicted) & actual)
                    
                    if match > best_match:
                        best_match = match
                    if match >= 3:
                        hit = True
                        method_wins[method_name] += 1
                except:
                    continue
                    
            if hit: wins += 1
            if best_match >= 4: m4_plus += 1
            total += 1
            
        win_rate = wins / total * 100 if total > 0 else 0
        m4_rate = m4_plus / total * 100 if total > 0 else 0
        
        return {
            'methods': methods,
            'num_bets': len(methods),
            'window': window,
            'win_rate': win_rate,
            'm4_count': m4_plus,
            'm4_rate': m4_rate,
            'method_wins': method_wins,
            'periods': total
        }
    
    def search(
        self,
        max_bets: int = 2,
        periods: int = None,  # None = use all available data
        windows: List[Optional[int]] = [None, 200, 500],
        top_k: int = 10,
        verbose: bool = True
    ) -> List[Dict]:
        """
        Perform AutoML search for optimal strategy.
        
        Args:
            max_bets: Maximum number of bets to test (1, 2, 3, or 4)
            periods: Number of periods to test (None = all available data)
            windows: List of window sizes to test (None = all history)
            top_k: Number of top results to return
            verbose: Print progress
        """
        all_methods = list(self.base_methods.keys())
        results = []
        
        # Use all data if periods not specified
        if periods is None:
            periods = len(self.all_draws) - 100  # Reserve 100 for minimum history
        
        if verbose:
            print("=" * 80)
            print(f"🤖 AutoML Strategy Search for {self.lottery_type}")
            print(f"   Methods: {len(all_methods)}")
            print(f"   Max Bets: {max_bets}")
            print(f"   Windows: {windows}")
            print(f"   Periods: {periods} (Total draws: {len(self.all_draws)})")
            print("=" * 80)
        
        total_combos = 0
        tested = 0
        
        # Calculate total combinations
        for num_bets in range(1, max_bets + 1):
            combos = len(list(combinations(all_methods, num_bets)))
            total_combos += combos * len(windows)
            
        if verbose:
            print(f"   Total combinations to test: {total_combos}")
            print("-" * 80)
        
        for num_bets in range(1, max_bets + 1):
            for window in windows:
                for combo in combinations(all_methods, num_bets):
                    tested += 1
                    
                    if verbose and tested % 50 == 0:
                        print(f"   Progress: {tested}/{total_combos} ({tested/total_combos*100:.0f}%)")
                    
                    result = self.evaluate_combination(combo, periods, window)
                    results.append(result)
        
        # Sort by win rate, then by M4+ count
        results.sort(key=lambda x: (x['win_rate'], x['m4_count']), reverse=True)
        
        if verbose:
            print("\n" + "=" * 80)
            print(f"📊 TOP {top_k} RESULTS")
            print("=" * 80)
            print(f"{'Rank':<5} {'Methods':<40} {'Win%':<8} {'M4+':<5} {'Bets':<5} {'Window':<8}")
            print("-" * 75)
            
            for i, r in enumerate(results[:top_k], 1):
                methods_str = ' + '.join(r['methods'])[:38]
                window_str = str(r['window']) if r['window'] else 'All'
                marker = "⭐" if i == 1 else ""
                print(f"{i:<5} {methods_str:<40} {r['win_rate']:.2f}%{marker:<3} {r['m4_count']:<5} {r['num_bets']:<5} {window_str:<8}")
            
            print("=" * 80)
            best = results[0]
            print(f"\n🏆 BEST STRATEGY: {' + '.join(best['methods'])}")
            print(f"   Win Rate: {best['win_rate']:.2f}%")
            print(f"   Match-4+: {best['m4_count']}")
            print(f"   Bets: {best['num_bets']}")
            print(f"   Window: {best['window'] if best['window'] else 'All'}")
            
        return results[:top_k]
    
    def save_results(self, results: List[Dict], filename: str = None):
        """Save search results to JSON."""
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'automl_results_{self.lottery_type}_{timestamp}.json'
            
        output_path = os.path.join(project_root, 'ai_lab', 'results', filename)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
            
        print(f"💾 Results saved to: {output_path}")
        return output_path


def main():
    """Run AutoML search for both lottery types using ALL data."""
    
    # Power Lotto optimization
    print("\n" + "="*80)
    print("POWER LOTTO AUTOML SEARCH (全部數據)")
    print("="*80 + "\n")
    
    optimizer_pl = AutoMLStrategyOptimizer('POWER_LOTTO')
    results_pl = optimizer_pl.search(
        max_bets=2,
        periods=None,  # Use all data
        windows=[None, 300, 500],
        top_k=10
    )
    
    # Big Lotto optimization
    print("\n" + "="*80)
    print("BIG LOTTO AUTOML SEARCH (全部數據)")
    print("="*80 + "\n")
    
    optimizer_bl = AutoMLStrategyOptimizer('BIG_LOTTO')
    results_bl = optimizer_bl.search(
        max_bets=2,
        periods=None,  # Use all data
        windows=[None, 300, 500],
        top_k=10
    )


if __name__ == "__main__":
    main()

