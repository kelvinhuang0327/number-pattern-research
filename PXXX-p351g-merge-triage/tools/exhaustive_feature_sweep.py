#!/usr/bin/env python3
"""
Exhaustive Feature Sweep (Phase 20)
==================================
Brute-forces ALL combinations of features to find the absolute maximum Edge.
"""
import os
import sys
import numpy as np

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from tools.strategy_leaderboard import StrategyLeaderboard
from tools.verify_strategy_longterm import UnifiedAuditor
from tools.predict_sequence_transformer import transformer_predict

def run_sweep(lottery_type='BIG_LOTTO'):
    auditor = UnifiedAuditor(lottery_type=lottery_type)
    results = []
    
    # 1. Sweep Window Sizes
    windows = [50, 150, 300, 500]
    
    print(f"🔬 STARTING EXHAUSTIVE SWEEP FOR {lottery_type}")
    print("="*60)
    
    for w in windows:
        # Strategy A: Zonal Pruning (Spatial Focus)
        from tools.biglotto_zonal_pruning import zonal_pruned_predict
        def bridge_zonal(h, num_bets=2): return zonal_pruned_predict(h, n_bets=num_bets, window=w)
        wr, edge = auditor.audit(bridge_zonal, n=300, num_bets=2)
        results.append({'strat': f'Zonal_W{w}', 'edge': edge})
        
        # Strategy B: Transformer (Attention Focus)
        def bridge_trans(h, num_bets=2): return transformer_predict(h, lottery_type=lottery_type, n_bets=num_bets, window=w)
        wr, edge = auditor.audit(bridge_trans, n=300, num_bets=2)
        results.append({'strat': f'Trans_W{w}', 'edge': edge})
        
        # Strategy C: Fourier (Global Frequency Focus)
        from tools.power_fourier_rhythm import fourier_rhythm_predict
        def bridge_four(h, num_bets=2): return fourier_rhythm_predict(h, n_bets=num_bets, window=w)
        wr, edge = auditor.audit(bridge_four, n=300, num_bets=2)
        results.append({'strat': f'Fourier_W{w}', 'edge': edge})

    # Find Winner
    results.sort(key=lambda x: x['edge'], reverse=True)
    winner = results[0]
    
    print("\n" + "🏆" + "="*58 + "🏆")
    print(f"   GOLDEN FEATURE DISCOVERY: {winner['strat']}")
    print(f"   MAX VERIFIED EDGE: {winner['edge']*100:+.2f}%")
    print("🏆" + "="*58 + "🏆")
    
    return winner

if __name__ == "__main__":
    run_sweep(lottery_type='BIG_LOTTO')
