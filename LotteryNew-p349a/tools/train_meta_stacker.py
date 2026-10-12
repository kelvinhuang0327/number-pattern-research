import os
import sys
import logging
import torch
from datetime import datetime

# Setup paths
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.models.unified_predictor import UnifiedPredictionEngine
from lottery_api.models.meta_stacking_predictor import MetaStackingPredictor
from lottery_api.database import DatabaseManager
from lottery_api.common import get_lottery_rules
from lottery_api.utils.backtest_safety import validate_chronological_order, get_safe_backtest_slice

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('MetaStackingTrainer')

def train_stacker(periods: int = 300):
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)
    all_draws = validate_chronological_order(db.get_all_draws('POWER_LOTTO'))
    rules = get_lottery_rules('POWER_LOTTO')
    
    engine = UnifiedPredictionEngine()
    # List of strategies to use as input features
    strategy_names = [
        'markov', 'gnn', 'fourier_main', 'sota', 'maml', 
        'anomaly', 'bayesian', 'trend', 'frequency', 'deviation'
    ]
    
    model_dir = os.path.join(project_root, 'lottery_api', 'data', 'models')
    os.makedirs(model_dir, exist_ok=True)
    model_path = os.path.join(model_dir, 'meta_stacker_power.pth')
    
    stacker = MetaStackingPredictor(strategy_names, model_path=model_path)
    
    # Collect training data
    train_samples = []
    test_data = all_draws[-periods-50:-50] # Leave last 50 for validation
    
    print(f"🎮 Generating Training Data from {len(test_data)} periods...")
    
    for i, target_draw in enumerate(test_data):
        target_idx = all_draws.index(target_draw)
        history = get_safe_backtest_slice(all_draws, target_idx)
        regime_info = engine.regime_detector.detect_regime(history)
        regime = regime_info.get('regime', 'GLOBAL')
        
        actual_main = target_draw['numbers']
        
        # 1. 策略分數特徵
        strategy_scores = {}
        for s_name in strategy_names:
            try:
                method_name = f"{s_name if 'fourier' not in s_name else 'fourier_main'}_predict"
                res = getattr(engine, method_name)(history, rules)
                score_vec = {n: 0.0 for n in range(1, 39)}
                for n in res.get('numbers', []):
                    if 1 <= n <= 38:
                        score_vec[n] = float(res.get('confidence', 0.5))
                strategy_scores[s_name] = score_vec
            except:
                continue
        
        # 2. 結構性特徵 (Phase 55)
        structural_features = {
            'entropy': {n: 0.0 for n in range(1, 39)},
            'volatility': {n: 0.0 for n in range(1, 39)}
        }
        # 計算熵值 (基於近期 20 期號碼空間)
        recent_draws = [d['numbers'] for d in history[-20:]] if len(history) >= 20 else [d['numbers'] for d in history]
        flattened_recent = [n for sublist in recent_draws for n in sublist]
        current_entropy = engine.analyzer.calculate_entropy(flattened_recent, 38)
        
        for n in range(1, 39):
            structural_features['entropy'][n] = float(current_entropy)
            n_freq = len([d for d in history[-50:] if n in d.get('numbers', [])])
            structural_features['volatility'][n] = abs(n_freq - (50 * 6 / 38)) / 10.0
            
        if strategy_scores:
            train_samples.append((strategy_scores, structural_features, regime, actual_main, 38))
            
        if (i+1) % 50 == 0:
            print(f"  Progress: {i+1}/{len(test_data)}")

    print(f"🚀 Training Meta-Stacker on {len(train_samples)} samples...")
    stacker.train_model(train_samples, epochs=150)
    print("✅ Training Complete.")

if __name__ == "__main__":
    train_stacker(1000)
