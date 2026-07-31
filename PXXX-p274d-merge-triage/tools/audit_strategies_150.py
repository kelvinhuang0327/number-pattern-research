#!/usr/bin/env python3
"""
📊 Individual Strategy Audit (Latest 200 Periods)
Goal: Find the most accurate single strategies to refine the Ensemble.
"""
import sys
import os
import io
from collections import Counter, defaultdict

# Add project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules
from models.unified_predictor import UnifiedPredictionEngine

# Fix encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def audit_strategies(test_periods=100):
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = list(reversed(db.get_all_draws(lottery_type='BIG_LOTTO')))
    rules = get_lottery_rules('BIG_LOTTO')
    engine = UnifiedPredictionEngine()
    
    strategies = {
        'frequency': engine.frequency_predict,
        'bayesian': engine.bayesian_predict,
        'markov': engine.markov_predict,
        'trend': engine.trend_predict,
        'deviation': engine.deviation_predict,
        'statistical': engine.statistical_predict,
        'zone_balance': engine.zone_balance_predict,
        'hot_cold_mix': engine.hot_cold_mix_predict,
        'monte_carlo': lambda h, r: engine.monte_carlo_predict(h, r, simulations=10000)
    }
    
    performance = defaultdict(lambda: {'match_3_plus': 0, 'total_hits': 0, 'match_counts': Counter()})
    
    print(f"🔬 Auditing {len(strategies)} strategies over {test_periods} periods...")
    
    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        if target_idx <= 0: continue
        
        target_draw = all_draws[target_idx]
        history = all_draws[:target_idx]
        actual = set(target_draw['numbers'])
        
        for name, func in strategies.items():
            try:
                # Silence prints
                import contextlib
                with contextlib.redirect_stdout(io.StringIO()):
                    res = func(history, rules)
                
                predicted = set(res['numbers'])
                hits = len(predicted & actual)
                
                performance[name]['total_hits'] += hits
                performance[name]['match_counts'][hits] += 1
                if hits >= 3:
                    performance[name]['match_3_plus'] += 1
            except Exception as e:
                continue
                
        if (i + 1) % 20 == 0:
            print(f"進度: {i+1}/{test_periods}")

    print("\n" + "=" * 80)
    print(f"📊 Strategy Performance Report (Latest {test_periods} Draws)")
    print("-" * 80)
    print(f"{'Strategy':<15} | {'M-3+ Rate':<10} | {'Avg Hits':<10} | {'Match Dist (0/1/2/3/4+)'}")
    print("-" * 80)
    
    # Sort by M-3+ rate, then Avg hits
    sorted_perf = sorted(performance.items(), key=lambda x: (x[1]['match_3_plus'], x[1]['total_hits']), reverse=True)
    
    for name, data in sorted_perf:
        m3_rate = data['match_3_plus'] / test_periods * 100
        avg_hits = data['total_hits'] / test_periods
        dist = data['match_counts']
        dist_str = f"{dist[0]}/{dist[1]}/{dist[2]}/{dist[3]}/{sum(dist[k] for k in dist if k >= 4)}"
        print(f"{name:<15} | {m3_rate:>9.2f}% | {avg_hits:>9.2f} | {dist_str}")
    print("=" * 80)

if __name__ == '__main__':
    audit_strategies(150)
