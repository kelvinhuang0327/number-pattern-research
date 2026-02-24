import sys
import os
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from evolving_strategy_engine.data_loader import load_big_lotto_draws
from evolving_strategy_engine.strategy_base import FeatureLibrary

def test_new_features():
    draws, _ = load_big_lotto_draws()
    
    # Analyze the state before draw 115000021 (so using draws up to 115000020)
    # Actually the draws array contains all data up to 115000020.
    
    zonal_scores = FeatureLibrary.zonal_density_score(draws, window=10, zones=5)
    gap_mom_scores = FeatureLibrary.gap_momentum(draws)
    
    target_nums = [13, 15, 18, 24, 33, 49]
    
    print("=== New Features Analysis Before Draw 115000021 ===")
    print("\nZonal Density Score (Higher = colder zone expected to mean-revert):")
    for n in target_nums:
        z = min((n - 1) // 10, 4)
        print(f"Num {n:02d} (Zone {z}): Score = {zonal_scores[n-1]:+.4f}")
        
    print("\nGap Momentum (Higher = accelerating):")
    for n in target_nums:
        print(f"Num {n:02d}: Momentum = {gap_mom_scores[n-1]:+.1f}")
        
    # Combine the two into a meta-feature
    # We want mean reversion for zones (high zonal) + strong momentum (high mom)
    def norm(x):
        std = np.std(x)
        return (x - np.mean(x)) / std if std > 0 else x

    combined = norm(zonal_scores) + norm(gap_mom_scores)
    pred_indices = np.argsort(combined)[::-1]
    
    print("\nTop 12 numbers predicted by Zonal + Gap Momentum:")
    top_12 = [int(i)+1 for i in pred_indices[:12]]
    print(top_12)
    
    hits = set(top_12) & set(target_nums)
    print(f"Hits in top 12: {len(hits)} {list(hits)}")

if __name__ == "__main__":
    test_new_features()
