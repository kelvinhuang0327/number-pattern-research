#!/usr/bin/env python3
"""Quick 10-Bet Big Lotto Test"""
import os, sys
from collections import Counter

project_root = os.getcwd()
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules
from models.unified_predictor import UnifiedPredictionEngine

def main():
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery.db'))
    all_draws = list(reversed(db.get_all_draws(lottery_type='BIG_LOTTO')))
    rules = get_lottery_rules('BIG_LOTTO')
    engine = UnifiedPredictionEngine()
    
    print("=" * 70)
    print("🔬 10-Bet Big Lotto Backtest (150期)")
    print("=" * 70)
    
    methods = ['markov', 'deviation', 'statistical', 'trend', 'frequency',
               'bayesian', 'hot_cold_mix']
    
    periods, wins, m4_plus = 150, 0, 0
    match_dist = Counter()
    
    for i in range(periods):
        target_idx = len(all_draws) - periods + i
        target_draw = all_draws[target_idx]
        history = all_draws[:target_idx]
        actual = set(target_draw['numbers'])
        
        bets = []
        # 7 standard methods
        for m in methods:
            try:
                func = getattr(engine, f'{m}_predict')
                bets.append(func(history, rules)['numbers'][:6])
            except: pass
        
        # 3 additional Trend variants (λ=0.03, 0.10, 0.15)
        import numpy as np
        from collections import defaultdict
        for lam in [0.03, 0.10, 0.15]:
            wf = defaultdict(float)
            for j, d in enumerate(reversed(history)):
                for n in d['numbers']:
                    wf[n] += np.exp(-lam * j)
            total = sum(wf.values())
            probs = {n: wf.get(n,0)/total for n in range(1,50)}
            s = sorted(probs.items(), key=lambda x: x[1], reverse=True)
            bets.append(sorted([n for n,_ in s[:6]]))
        
        best_match = 0
        hit = False
        for bet in bets[:10]:  # Take only 10 bets
            m = len(set(bet) & actual)
            if m > best_match: best_match = m
            if m >= 3: hit = True
        
        if hit: wins += 1
        if best_match >= 4: m4_plus += 1
        match_dist[best_match] += 1
        
        if (i+1) % 50 == 0:
            print(f"  Progress: {i+1}/{periods}... Rate: {wins/(i+1)*100:.2f}%")
    
    rate = wins / periods * 100
    print("-" * 70)
    print(f"✅ 10-Bet Big Lotto Rate: {rate:.2f}%")
    print(f"📊 Match Distribution: M3:{match_dist[3]} M4:{match_dist[4]} M5:{match_dist[5]} M6:{match_dist[6]}")
    print(f"🏆 Match-4+: {m4_plus}")
    print("=" * 70)

if __name__ == "__main__":
    main()
