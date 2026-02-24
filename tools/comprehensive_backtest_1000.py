import os
import sys
import logging
import numpy as np
from datetime import datetime

# Setup paths
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.models.unified_predictor import UnifiedPredictionEngine
from lottery_api.models.multi_bet_optimizer import MultiBetOptimizer
from lottery_api.database import DatabaseManager
from lottery_api.common import get_lottery_rules
from lottery_api.utils.backtest_safety import (
    validate_chronological_order, 
    get_safe_backtest_slice
)

logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger('ComprehensiveBacktest')

# Power Lotto Prize Table (TWD)
PRIZE_TABLE = {
    (6, 1): 200000000, # Mock Grand
    (6, 0): 20000000,
    (5, 1): 150000,
    (5, 0): 20000,
    (4, 1): 4000,
    (4, 0): 800,
    (3, 1): 400,
    (2, 1): 200,
    (3, 0): 100,
    (1, 1): 100
}

def calculate_prize(main_hits, special_hit):
    return PRIZE_TABLE.get((main_hits, special_hit), 0)

def run_comprehensive_backtest(periods: int = 1000, num_bets: int = 5, meta_config: dict = None):
    if meta_config is None:
        meta_config = {'high_precision': True}
    db = DatabaseManager(os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = validate_chronological_order(db.get_all_draws('POWER_LOTTO'))
    
    rules = get_lottery_rules('POWER_LOTTO')
    engine = UnifiedPredictionEngine()
    optimizer = MultiBetOptimizer()
    
    total_cost = 0
    total_prize = 0
    total_m3_hits = 0
    regime_results = {'ORDER': {'hits': 0, 'count': 0}, 'CHAOS': {'hits': 0, 'count': 0}, 'TRANSITION': {'hits': 0, 'count': 0}, 'GLOBAL': {'hits': 0, 'count': 0}}
    backtest_details = [] # Phase 58
    
    test_data = all_draws[-periods:]
    start_time = datetime.now()
    
    print(f"🚀 Starting Comprehensive Regime-Aware Backtest: {periods} periods, {num_bets}-bet")
    print(f"Targeting: POWER_LOTTO | Engine: Unified (Regime-Aware MAB)")
    print("-" * 60)
    
    for i, target_draw in enumerate(test_data):
        target_idx = all_draws.index(target_draw)
        history = get_safe_backtest_slice(all_draws, target_idx)
        actual_main = sorted(list(target_draw['numbers']))
        actual_special = target_draw.get('special_number', target_draw.get('special', 0))
        
        # 1. Detect Regime (to be used for logging and verification)
        regime_info = engine.regime_detector.detect_regime(history)
        regime = regime_info.get('regime', 'GLOBAL')
        
        # 2. Prediction (implicitly uses MAB and Regime context)
        # We call generate_diversified_bets as it's the high-level multi-bet entry point
        result = optimizer.generate_diversified_bets(
            history, rules, num_bets=num_bets,
            meta_config=meta_config
        )
        
        # Strategy predictions (for MAB update)
        # Note: In a real simulation, we'd need the predictions from MABEnsemblePredictor
        # But UnifiedPredictionEngine's ensemble_predict already does MAB.
        # To update MAB, we need to know what each strategy predicted.
        # generate_diversified_bets returns source-tagged bets.
        
        # Collect hits for this draw
        draw_prize = 0
        draw_m3_hit = False
        
        # Each bet is 100 TWD
        total_cost += num_bets * 100
        
        # Mocking special number for each bet (if not provided by optimizer)
        bet_specials = result.get('specials', [1] * num_bets)
        
        for b_idx, bet in enumerate(result['bets']):
            nums = set(bet['numbers'])
            main_hits = len(nums & set(actual_main))
            spec_matched = 1 if (bet_specials[b_idx] == actual_special) else 0
            
            prize = calculate_prize(main_hits, spec_matched)
            draw_prize += prize
            
            if main_hits >= 3:
                draw_m3_hit = True
                
        total_prize += draw_prize
        if draw_m3_hit:
            total_m3_hits += 1
            regime_results[regime]['hits'] += 1
            
        regime_results[regime]['count'] += 1
        
        # Save details
        backtest_details.append({
            'draw': target_draw['draw'],
            'actual_numbers': list(actual_main),
            'actual_special': actual_special,
            'bets': [{'numbers': list(b['numbers']), 'special': bet_specials[idx]} for idx, b in enumerate(result['bets'])],
            'prize': draw_prize
        })

        # Update MAB (Simulating training/feedback loop)
        # For simplicity in backtest, we assume the engine updates its internal state
        # But in a real backtest, we need to explicitly trigger the update
        # We need the individual strategy predictions for this.
        # This part is complex because UnifiedPredictionEngine.ensemble_predict 
        # is normally called once. Optimizer calls it too.
        
        # To avoid double-running, we trust the Optimizer's use of number_scores.
        # The MAB is updated via engine.update_mab.
        # We need to simulate the prediction set.
        strategy_preds = {}
        for s_name, s_data in result.get('metadata', {}).get('strategy_predictions', {}).items():
            strategy_preds[s_name] = s_data
        
        if strategy_preds:
            engine.update_mab(history, strategy_preds, list(actual_main), lottery_type='POWER_LOTTO')
        
        if (i+1) % 100 == 0:
            elapsed = (datetime.now() - start_time).total_seconds()
            m3_rate = (total_m3_hits / (i+1)) * 100
            roi = (total_prize / total_cost) * 100
            print(f"Progress: {i+1}/{periods} | M3+: {m3_rate:.2f}% | ROI: {roi:.2f}% | Elapsed: {elapsed:.1f}s", flush=True)

    # Final Report
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    final_m3_rate = (total_m3_hits / periods) * 100
    final_roi = (total_prize / total_cost) * 100
    
    print("\n" + "="*70)
    print(f"📊 FINAL COMPREHENSIVE BACKTEST REPORT")
    print(f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"⏱️ Duration: {duration:.1f} seconds")
    print("-" * 70)
    print(f"🎯 M3+ Hit Rate: {final_m3_rate:.2f}%  (Baseline Goal: 18.20% for 5-bet)")
    print(f"💰 Total Cost:  {total_cost:,} TWD")
    print(f"🏆 Total Prize: {total_prize:,} TWD")
    print(f"📈 Overall ROI: {final_roi:.2f}%")
    print("-" * 70)
    print("📈 REGIME PERFORMANCE:")
    for r, data in regime_results.items():
        if data['count'] > 0:
            rate = (data['hits'] / data['count']) * 100
            print(f"  - {r:10}: {rate:.2f}% ({data['hits']}/{data['count']})")
    
    print("=" * 70)
    
    # Phase 58: Save results for PnL analysis
    if meta_config.get('save_path'):
        import json
        
        # Convert numpy types to native python for JSON serialization
        def native_convert(obj):
            if isinstance(obj, (np.int64, np.int32)):
                return int(obj)
            if isinstance(obj, (np.float64, np.float32)):
                return float(obj)
            if hasattr(obj, 'tolist'):
                return obj.tolist()
            return obj

        clean_details = []
        for d in backtest_details:
            clean_d = {
                'draw': native_convert(d['draw']),
                'actual_numbers': [native_convert(n) for n in d['actual_numbers']],
                'actual_special': native_convert(d['actual_special']),
                'bets': [{'numbers': [native_convert(n) for n in b['numbers']], 'special': native_convert(b['special'])} for b in d['bets']],
                'prize': native_convert(d['prize'])
            }
            clean_details.append(clean_d)

        with open(meta_config['save_path'], 'w') as f:
            json.dump(clean_details, f)
        print(f"\n📂 Raw results saved to: {meta_config['save_path']}")

if __name__ == "__main__":
    import sys
    periods = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
    num_bets = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    method = sys.argv[3] if len(sys.argv) > 3 else 'high_precision'
    
    save_path = sys.argv[4] if len(sys.argv) > 4 else None
    
    meta_config = {}
    if method == 'high_precision':
        meta_config['high_precision'] = True
    elif method == 'roi_stacking':
        meta_config['method'] = 'roi_stacking'
    elif method == 'meta_stacking':
        meta_config['method'] = 'meta_stacking'
    elif method == 'diffusion':
        meta_config['method'] = 'diffusion'
    
    if save_path:
        meta_config['save_path'] = save_path
    
    run_comprehensive_backtest(periods, num_bets, meta_config)
