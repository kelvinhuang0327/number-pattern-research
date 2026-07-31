import os
import sys
import logging
import itertools
from collections import Counter
import numpy as np

# Setup paths
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.models.advanced_strategies import AdvancedStrategies
from lottery_api.database import DatabaseManager
from lottery_api.common import get_lottery_rules
from lottery_api.utils.backtest_safety import validate_chronological_order, get_safe_backtest_slice

logging.basicConfig(level=logging.WARNING) # Reduce logs for tuning
logger = logging.getLogger('ParameterTuner')

def run_grid_search(periods: int = 100):
    db = DatabaseManager(os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = validate_chronological_order(db.get_all_draws('BIG_LOTTO'))
    rules = get_lottery_rules('BIG_LOTTO')
    adv = AdvancedStrategies()
    
    test_data = all_draws[-periods:]
    
    # Grid Search Parameters
    gap_min_options = [20, 25, 30]
    gap_max_options = [35, 40, 45]
    anomaly_window_options = [20, 30, 50]
    
    best_rate = -1
    best_params = None
    
    combinations = list(itertools.product(gap_min_options, gap_max_options, anomaly_window_options))
    print(f"🚀 Starting Grid Search over {len(combinations)} combinations ({periods} periods each)")
    
    for gap_min, gap_max, window in combinations:
        if gap_min >= gap_max: continue
        
        hits = 0
        for i, target_draw in enumerate(test_data):
            target_idx = all_draws.index(target_draw)
            history = get_safe_backtest_slice(all_draws, target_idx)
            
            # Override class methods with candidate parameters for tuning
            adv_tuned = AdvancedStrategies()
            
            # Monkeypatch the anomaly logic with specific window for this test
            # (In a real scenario we'd pass these as arguments, but here we simulate the logic)
            def tuned_predict(hist):
                v3_res = adv_tuned.structural_hybrid_v3_predict(hist, rules)
                v3_bets = v3_res['details']['bets']
                
                # Custom Anomaly logic for tuning
                max_num = rules.get('maxNumber', 49)
                all_nums = [n for d in hist for n in d['numbers']]
                recent_nums = [n for d in hist[-window:] for n in d['numbers']]
                
                long_counts = Counter(all_nums)
                recent_counts = Counter(recent_nums)
                
                anomaly_scores = {}
                history_len = max(1, len(hist))
                for n in range(1, max_num + 1):
                    expected = long_counts.get(n, 0) / history_len
                    actual = recent_counts.get(n, 0) / window
                    anomaly_scores[n] = abs(actual - expected)
                
                top_anomaly = sorted(anomaly_scores.items(), key=lambda x: x[1], reverse=True)[0][0]
                pairs, _ = adv_tuned.build_cooccurrence_matrices(hist)
                
                # Use tuned gap filters
                # (We simulate the filter call locally for tuning)
                def custom_filter(cands):
                    last_seen = {n: -1 for n in range(1, max_num + 1)}
                    for idx, d in enumerate(reversed(hist)):
                        for n in d['numbers']:
                            if last_seen[n] == -1: last_seen[n] = idx
                    res = []
                    for n in cands:
                        g = last_seen.get(n, 100)
                        if g < gap_min: res.append(n)
                        elif g > gap_max: continue
                        else: res.append(n)
                    return res

                # Expand anomaly bet
                cands = Counter()
                for (a, b), c in pairs.items():
                    if a == top_anomaly: cands[b] += c
                    elif b == top_anomaly: cands[a] += c
                sorted_cands = [n for n, _ in cands.most_common(20)]
                filtered = custom_filter(sorted_cands)
                bet_anomaly = sorted([top_anomaly] + filtered[:5])
                
                return [v3_bets[0], v3_bets[1], bet_anomaly, v3_bets[2]]

            bets = tuned_predict(history)
            actual = set(target_draw['numbers'])
            max_h = max(len(set(b) & actual) for b in bets)
            if max_h >= 3: hits += 1
            
        rate = (hits / periods) * 100
        print(f"Params: [Gap {gap_min}-{gap_max}, Window {window}] -> Match-3+ Rate: {rate:.2f}%")
        
        if rate > best_rate:
            best_rate = rate
            best_params = (gap_min, gap_max, window)
            
    print("\n" + "="*60)
    print(f"🏆 BEST RESULTS")
    print(f"Params: Gap {best_params[0]}-{best_params[1]}, Window {best_params[2]}")
    print(f"Best Match-3+ Rate: {best_rate:.2f}%")
    print("="*60)

if __name__ == "__main__":
    run_grid_search(100)
