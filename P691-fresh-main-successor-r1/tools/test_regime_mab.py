import os
import sys
import logging
import numpy as np

# Setup paths
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from lottery_api.models.mab_ensemble import ThompsonSamplingEnsemble

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('MABVerify')

def test_regime_aware_mab():
    strategies = ['gnn', 'markov', 'frequency']
    mab = ThompsonSamplingEnsemble(strategies, window=10)
    
    print("\n🚀 Testing Regime-Aware MAB Logic")
    
    # 1. Simulate CHAOS regime: GNN performs well
    print("\n--- Phase 1: CHAOS Regime (GNN Dominates) ---")
    for _ in range(20):
        # Mock predictions where GNN hits 3+
        preds = {
            'gnn': [1, 2, 3, 4, 5, 6],
            'markov': [10, 11, 12, 13, 14, 15],
            'frequency': [20, 21, 22, 23, 24, 25]
        }
        actual = [1, 2, 3, 10, 20, 30] # GNN hits 3, markov hits 1, freq hits 1
        mab.update(preds, actual, regime='CHAOS')
        
    stats = mab.get_statistics()
    chaos_gnn_weight = stats['regimes']['CHAOS']['gnn']['expected_weight']
    global_gnn_weight = stats['regimes']['GLOBAL']['gnn']['expected_weight']
    
    print(f"CHAOS GNN Weight: {chaos_gnn_weight:.4f}")
    print(f"GLOBAL GNN Weight: {global_gnn_weight:.4f}")
    
    # 2. Simulate ORDER regime: Markov performs well
    print("\n--- Phase 2: ORDER Regime (Markov Dominates) ---")
    for _ in range(20):
        preds = {
            'gnn': [20, 21, 22, 23, 24, 25],
            'markov': [1, 2, 3, 4, 5, 6],
            'frequency': [10, 11, 12, 13, 14, 15]
        }
        actual = [1, 2, 3, 10, 20, 30] # Markov hits 3
        mab.update(preds, actual, regime='ORDER')

    stats = mab.get_statistics()
    order_markov_weight = stats['regimes']['ORDER']['markov']['expected_weight']
    chaos_markov_weight = stats['regimes']['CHAOS']['markov']['expected_weight']
    
    print(f"ORDER Markov Weight: {order_markov_weight:.4f}")
    print(f"CHAOS Markov Weight: {chaos_markov_weight:.4f}")

    # Validation
    assert chaos_gnn_weight > 0.5, "GNN should dominate in CHAOS"
    assert order_markov_weight > 0.5, "Markov should dominate in ORDER"
    assert chaos_gnn_weight > order_markov_weight, "Just checking different values"
    
    print("\n✅ SUCCESS: MAB correctly isolates performance by regime!")

if __name__ == "__main__":
    test_regime_aware_mab()
