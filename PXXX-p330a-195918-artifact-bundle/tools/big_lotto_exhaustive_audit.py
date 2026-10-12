#!/usr/bin/env python3
"""
Phase 83: Big Lotto Ultimate Strategy Audit
===========================================
Simulates 1000 periods of Big Lotto using:
- Layer 1: Selection Bias (Hot Trend / Cold Reversion / Neutral Filter)
- Layer 2: Construction Structure (Zone Split / Orthogonal)
"""

import pandas as pd
import numpy as np
import random
from collections import Counter

def get_hits(bet, draw):
    return len(set(bet).intersection(set(draw)))

def calculate_payout(hits):
    # Standard Big Lotto Payout Model (Estimates for M3+ hits)
    if hits == 3: return 400
    if hits == 4: return 2000
    if hits == 5: return 50000
    if hits == 6: return 10000000
    return 0

class BigLottoAuditor:
    def __init__(self, csv_path='data/lotto649_realistic_data.csv', window=50):
        try:
            df = pd.read_csv(csv_path)
            # Take last 1000 draws for backtest
            self.history = df[['n1','n2','n3','n4','n5','n6']].values.tolist()
            self.window = window
        except:
            # Fallback if file missing - generate synthetic
            print("Warning: Using synthetic data for Big Lotto Audit")
            self.history = [random.sample(range(1, 50), 6) for _ in range(2000)]
            self.window = window

    def run_audit(self, num_bets=3):
        total_payout = 0
        total_cost = num_bets * 50 * (len(self.history) - self.window)
        results = []
        
        for i in range(self.window, len(self.history)):
            draw = self.history[i]
            prev_data = self.history[i-self.window : i]
            flat_prev = [num for sublist in prev_data for num in sublist]
            counts = Counter(flat_prev)
            
            # Rank numbers by frequency
            ranked = sorted(range(1, 50), key=lambda x: counts.get(x, 0), reverse=True)
            
            hot_pool = ranked[:15]
            cold_pool = ranked[-15:]
            neutral_pool = ranked[15:-15]
            
            bets = []
            # Bet 1: Hot Trend
            bets.append(random.sample(hot_pool, 6))
            # Bet 2: Cold Reversion
            bets.append(random.sample(cold_pool, 6))
            # Bet 3: Structural Filter (Orthogonal to 1 & 2)
            if num_bets >= 3:
                used = set(bets[0]) | set(bets[1])
                candidate_pool = [n for n in range(1, 50) if n not in used]
                bets.append(random.sample(candidate_pool, 6))
            
            hits = [get_hits(b, draw) for b in bets]
            period_payout = sum(calculate_payout(h) for h in hits)
            total_payout += period_payout
            results.append(max(hits))

        periods = len(self.history) - self.window
        m3_plus_count = sum(1 for r in results if r >= 3)
        hit_rate = m3_plus_count / periods * 100
        roi = (total_payout / total_cost - 1) * 100
        
        return hit_rate, roi, periods

if __name__ == "__main__":
    auditor = BigLottoAuditor()
    h2, r2, p2 = auditor.run_audit(num_bets=2)
    h3, r3, p3 = auditor.run_audit(num_bets=3)
    
    print(f"--- Big Lotto Ultimate Audit ({p3} Periods) ---")
    print(f"2-Bet (Hot+Cold): Hit Rate {h2:.2f}% | ROI {r2:.2f}%")
    print(f"3-Bet (Hot+Cold+Ortho): Hit Rate {h3:.2f}% | ROI {r3:.2f}%")
    print("-" * 50)
