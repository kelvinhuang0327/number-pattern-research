#!/usr/bin/env python3
"""
True Random Baseline Validator
==============================
Calculates the probability of getting Match-3+ when placing N random bets.
This accounts for the combinatorial complexity and is more accurate than 
simply multiplying single-bet probabilities.
"""
import numpy as np
import argparse
from tqdm import tqdm

def simulate_baseline(num_balls, n_picks, n_bets, iterations=1000000):
    print(f"🔬 Simulating {n_bets}-bet random strategy for {n_picks}/{num_balls} lottery...")
    print(f"📊 Iterations: {iterations:,}")
    
    match_3plus_count = 0
    
    # Pre-generate random pool for safety if needed, but per-iteration is fine
    pool = np.arange(1, num_balls + 1)
    
    for _ in tqdm(range(iterations)):
        actual = set(np.random.choice(pool, size=n_picks, replace=False))
        
        win = False
        for _ in range(n_bets):
            pred = set(np.random.choice(pool, size=n_picks, replace=False))
            if len(pred & actual) >= 3:
                win = True
                break
        
        if win:
            match_3plus_count += 1
            
    final_prob = match_3plus_count / iterations * 100
    print(f"\n✅ Result: {n_bets}-bet Match-3+ Baseline = {final_prob:.4f}%")
    return final_prob

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--lottery', default='BIG_LOTTO', choices=['BIG_LOTTO', 'POWER_LOTTO', 'CUSTOM'])
    parser.add_argument('--balls', type=int, default=49)
    parser.add_argument('--picks', type=int, default=6)
    parser.add_argument('--bets', type=int, default=1)
    parser.add_argument('--n', type=int, default=1000000)
    args = parser.parse_args()
    
    if args.lottery == 'BIG_LOTTO':
        balls, picks = 49, 6
    elif args.lottery == 'POWER_LOTTO':
        balls, picks = 38, 6
    else:
        balls, picks = args.balls, args.picks
        
    simulate_baseline(balls, picks, args.bets, iterations=args.n)
