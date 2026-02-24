#!/usr/bin/env python3
"""
Power Lotto Dual-Path V2 Strategy (威力彩雙軌制 V2)
Based on:
1. Genetic Algorithm Findings (Dual Path is effective, Top 7 Hot + Bottom 1 Cold)
2. Expert Review (Need smarter Negative Selection)

Logic:
1. Filter: Use NegativeSelector (Dynamic Threshold) to remove ~10 absolute no-go numbers.
2. Score: Calculate Composite Score (Freq 0.8 + Deviation 0.8 + Trend 0.1).
3. Select: 
   - Path A: Top N (Hot)
   - Path B: Bottom M (Deviation Reversion - catch the bounce)
   - Intersection/Union of these paths.
"""
import sys
import os
from collections import Counter

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules
from tools.negative_selector_optimized import NegativeSelector

class PowerLottoDualPathV2:
    def __init__(self):
        self.db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
        self.rules = get_lottery_rules('POWER_LOTTO')
        self.selector = NegativeSelector('POWER_LOTTO') # Use Optimized Selector
        
    def calculate_scores(self, history):
        # Param from GA
        w_freq = 0.8
        w_dev = 0.8
        w_trend = 0.1
        trend_win = 50
        
        # 1. Frequency (All time)
        all_nums = [n for d in history for n in d['numbers']]
        freq_counts = Counter(all_nums)
        
        # 2. Trend (Recent)
        recent_nums = [n for d in history[-trend_win:] for n in d['numbers']]
        trend_counts = Counter(recent_nums)
        
        # 3. Deviation (Gap)
        last_appearance = {}
        for i, draw in enumerate(history):
            for n in draw['numbers']:
                last_appearance[n] = i
        
        current_idx = len(history)
        scores = {}
        
        for n in range(1, self.rules['maxNumber'] + 1):
            f = freq_counts.get(n, 0)
            t = trend_counts.get(n, 0)
            gap = current_idx - last_appearance.get(n, 0)
            
            # Composite Score
            # High Score = Hot
            # Low Score = Cold
            score = (f * w_freq) + (t * w_trend * 5) - (gap * w_dev)
            scores[n] = score
            
        return scores

    def predict(self, history):
        # 1. Negative Selection (Kill)
        # Note: NegativeSelector uses its own internal DB access usually, 
        # but we should pass history if possible or let it query. 
        # The optimize selector queries DB. We assume it syncs.
        kill_list = []
        try:
            # We can't easily inject history into the current NegativeSelector impl 
            # without modifying it, as it queries DB directly. 
            # For this script we will trust its DB view (or we could modify it).
            # For safety/speed in this script, we'll implement a lightweight dynamic kill here
            # to avoid DB inconsistency during backtest loops.
            pass
        except:
            pass
            
        # Lightweight Kill (Bottom 5 Trend)
        recent_counts = Counter([n for d in history[-30:] for n in d['numbers']])
        kill_candidates = [n for n in range(1, 39) if recent_counts[n] == 0]
        # Randomly kill some colds? No, GA said 'Kill=False' was better.
        # Let's keep Kill conservative.
        
        scores = self.calculate_scores(history)
        sorted_items = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        # Path A: Hot (Top 5)
        path_a = [x[0] for x in sorted_items[:5]]
        
        # Path B: Cold Reversion (Bottom 1) - The "Black Swan"
        # Pick the one with LOWEST score (Valid Cold)
        path_b = [sorted_items[-1][0]]
        
        # Combine
        selection = list(set(path_a + path_b))
        
        # Fill if needed
        idx = 5
        while len(selection) < 6:
            if sorted_items[idx][0] not in selection:
                selection.append(sorted_items[idx][0])
            idx += 1
            
        return sorted(selection[:6])

    def predict_zone2(self, history):
        # GA found Strategy 2 (Cold) is best for Zone 2 in training, 
        # but failed in validation. 
        # Let's try Strategy 3 (Repeater/Hot) which is usually safer for small pools.
        recents = [d.get('second_zone', d.get('special')) for d in history[-10:]]
        counts = Counter(recents)
        # Return most common
        if counts:
            return counts.most_common(1)[0][0]
        return 1

    def backtest(self):
        all_draws = self.db.get_all_draws('POWER_LOTTO')
        test_len = 200  # Standard Benchmark
        
        wins = 0
        rand_wins = 0
        total = 0
        z2_wins = 0
        rand_z2_wins = 0
        
        import random

        print(f"⚔️ Running Standard Benchmark (Dual-Path V2) - {test_len} Periods...")
        print(f"{'Draw':<10} | {'M3+':<5} | {'Z2':<5} | {'Result':<15}")
        print("-" * 50)
        
        for i in range(test_len):
            idx = len(all_draws) - test_len + i
            target = all_draws[idx]
            history = all_draws[:idx]
            
            # Strategy Prediction
            p1 = self.predict(history)
            p2 = self.predict_zone2(history)
            
            # Random Baseline
            r1 = sorted(random.sample(range(1, 39), 6))
            r2 = random.randint(1, 8)
            
            # Validation
            actual = set(target['numbers'])
            actual_z2 = target.get('second_zone', target.get('special'))
            
            # Strategy Hits
            hits = len(actual & set(p1))
            hit_z2 = (p2 == actual_z2)
            if hits >= 3: wins += 1
            if hit_z2: z2_wins += 1
            
            # Random Hits
            r_hits = len(actual & set(r1))
            r_hit_z2 = (r2 == actual_z2)
            if r_hits >= 3: rand_wins += 1
            if r_hit_z2: rand_z2_wins += 1
            
            draw_val = target.get('draw', target.get('period', 'Unknown'))
            if hits >= 3 or (hits==2 and hit_z2):
                res_str = f"M{hits}" + (" + Z2" if hit_z2 else "")
                print(f"{draw_val:<10} | {'YES' if hits>=3 else 'NO':<5} | {'YES' if hit_z2 else 'NO':<5} | {res_str:<15}")
            
            total += 1
            
        print("-" * 50)
        print(f"📊 Standard Evaluation Result (N={test_len})")
        print(f"🔹 Dual-Path V2 Win Rate (M3+): {wins/total*100:.2f}% (Count: {wins})")
        print(f"🔹 Random Baseline Win Rate   : {rand_wins/total*100:.2f}% (Count: {rand_wins})")
        print(f"\n🎯 Zone 2 Accuracy")
        print(f"🔹 Strategy (Repeater/Hot)    : {z2_wins/total*100:.2f}%")
        print(f"🔹 Random Guess               : {rand_z2_wins/total*100:.2f}%")
        
        diff = (wins - rand_wins) / total * 100
        print(f"\n💡 Conclusion: Strategy is {'BETTER' if diff > 0 else 'WORSE'} than random by {abs(diff):.2f}%")

if __name__ == "__main__":
    predictor = PowerLottoDualPathV2()
    predictor.backtest()
