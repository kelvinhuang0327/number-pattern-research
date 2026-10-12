#!/usr/bin/env python3
"""
Window Sensitivity Analysis for 3-Bet Strategy
Tests different history lookback windows to find the optimal training period.
"""
import os
import sys
from collections import Counter

project_root = os.getcwd()
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules
from models.unified_predictor import UnifiedPredictionEngine
from ai_lab.adapter import AIAdapter
from ai_lab.scripts.orthogonal_portfolio import OrthogonalPortfolio

def run_with_window(all_draws, rules, engine, ai_adapter, window_size, periods=150):
    """Run backtest with a specific history window size."""
    predictor = OrthogonalPortfolio(engine, ai_adapter)
    
    wins = 0
    total = 0
    m4_count = 0
    
    for i in range(periods):
        target_idx = len(all_draws) - periods + i
        target_draw = all_draws[target_idx]
        
        # Apply window: only use last N draws for prediction
        if window_size == 'ALL':
            history = all_draws[:target_idx]
        else:
            start_idx = max(0, target_idx - window_size)
            history = all_draws[start_idx:target_idx]
            
        if len(history) < 15:  # Need at least 15 for the AI model
            continue
            
        actual = set(target_draw['numbers'])
        
        try:
            res = predictor.predict_orthogonal_3bet(history, rules)
            bets = res['bets']
            
            round_best = 0
            for bet in bets:
                m = len(set(bet) & actual)
                if m > round_best: round_best = m
            
            if round_best >= 3: wins += 1
            if round_best >= 4: m4_count += 1
            total += 1
                
        except:
            continue
            
    rate = wins / total * 100 if total > 0 else 0
    return rate, m4_count, total

def main():
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery.db')
    db = DatabaseManager(db_path=db_path)
    all_draws = list(reversed(db.get_all_draws(lottery_type='BIG_LOTTO')))
    rules = get_lottery_rules('BIG_LOTTO')
    
    engine = UnifiedPredictionEngine()
    ai_adapter = AIAdapter()
    
    print("=" * 70)
    print("🔬 3-Bet Window Sensitivity Analysis")
    print("=" * 70)
    
    windows = [50, 100, 200, 300, 500, 1000, 'ALL']
    results = []
    
    for w in windows:
        print(f"Testing Window={w}...", end=" ", flush=True)
        rate, m4, total = run_with_window(all_draws, rules, engine, ai_adapter, w)
        results.append((w, rate, m4))
        print(f"Rate: {rate:.2f}%, M4: {m4}")
        
    print("\n" + "=" * 70)
    print("📊 RESULTS SUMMARY")
    print("=" * 70)
    print(f"{'Window':<10} | {'Success Rate':<15} | {'M4+ Hits':<10}")
    print("-" * 40)
    
    best_window = None
    best_rate = 0
    
    for w, rate, m4 in results:
        marker = ""
        if rate > best_rate:
            best_rate = rate
            best_window = w
            marker = " ⭐"
        print(f"{str(w):<10} | {rate:.2f}%{marker:<12} | {m4}")
        
    print("-" * 40)
    print(f"✅ Optimal Window: {best_window} ({best_rate:.2f}%)")
    print("=" * 70)

if __name__ == "__main__":
    main()
