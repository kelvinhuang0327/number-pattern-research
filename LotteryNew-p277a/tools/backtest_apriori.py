#!/usr/bin/env python3
"""
Backtest script for Apriori Association Rule Strategy
"""
import sys
import os
import logging
from collections import Counter
import random

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules
from tools.predict_biglotto_apriori import BigLottoAprioriPredictor

# Suppress logging during backtest
logging.getLogger().setLevel(logging.ERROR)

class BacktestApriori(BigLottoAprioriPredictor):
    def predict_for_backtest(self, history, num_bets=6, window=150):
        # Optimized version of predict_next_draw that takes history argument
        recent_history = history[-window:] # Recent N draws from the history slice
        
        # 1. Mine Frequent Itemsets
        frequent = self.mine_frequent_itemsets(recent_history, min_support=3)
        
        # 2. Generate Rules
        rules = self.generate_rules(frequent, min_confidence=0.4)
        
        bets = []
        used_rules = set() # Avoid picking same antecedent
        
        for i in range(num_bets):
            target_rule = None
            for r in rules:
                r_key = r['antecedent']
                if r_key not in used_rules:
                    target_rule = r
                    used_rules.add(r_key)
                    break
            
            if not target_rule:
                # Fallback if no rules found: Random with recent hot numbers?
                # For consistency with script, we break or use fallback.
                # Let's use simple random fallback to ensure we have bets
                remaining = list(range(1, 50))
                bets.append(sorted(random.sample(remaining, 6)))
                continue

            core = list(target_rule['antecedent']) + [target_rule['consequent']]
            current_nums = sorted(list(set(core)))
            
            while len(current_nums) < 6:
                best_next = None
                last_num = current_nums[-1]
                
                candidates = []
                for r in rules:
                    if r['consequent'] not in current_nums:
                        if r['antecedent'] == (last_num,) or (len(r['antecedent'])==1 and r['antecedent'][0] in current_nums):
                             candidates.append(r)
                
                if candidates:
                    candidates.sort(key=lambda x: x['confidence'], reverse=True)
                    best_next = candidates[0]['consequent']
                else:
                    remaining = [n for n in range(1, 50) if n not in current_nums]
                    if not remaining: break
                    best_next = remaining[i % len(remaining)]
                
                current_nums.append(best_next)
                current_nums = sorted(list(set(current_nums)))
                
            bets.append(sorted(current_nums[:6]))
            
        return bets

def run_backtest():
    predictor = BacktestApriori()
    all_draws = list(reversed(predictor.get_draws())) # Old -> New
    
    test_periods = 150
    start_idx = len(all_draws) - test_periods
    
    print(f"🚀 Apriori 策略多注數回測 (近 {test_periods} 期)...")
    print("=" * 60)
    
    for num_bets in [1, 2, 3, 7]:
        wins = Counter()
        
        for i in range(test_periods):
            curr_idx = start_idx + i
            target_draw = all_draws[curr_idx]
            history = all_draws[:curr_idx]
            actual = set(target_draw['numbers'])
            
            try:
                bets = predictor.predict_for_backtest(history, num_bets=num_bets, window=150)
            except Exception:
                continue
                
            period_best = 0
            for bet in bets:
                match = len(set(bet) & actual)
                period_best = max(period_best, match)
                
            wins[period_best] += 1
            
        total_match3_plus = sum(wins[k] for k in wins if k >= 3)
        match3_rate = total_match3_plus / test_periods * 100
        
        print(f"[{num_bets}注] Match 3+ 率: {match3_rate:.2f}% ({total_match3_plus}/{test_periods})")
    
if __name__ == '__main__':
    run_backtest()
