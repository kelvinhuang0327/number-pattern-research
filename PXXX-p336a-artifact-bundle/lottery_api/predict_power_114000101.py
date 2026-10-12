#!/usr/bin/env python3
import sys
import os

# Add current directory to path
sys.path.insert(0, os.getcwd())

from database import db_manager
from models.unified_predictor import prediction_engine
from common import get_lottery_rules

def main():
    lottery_type = 'POWER_LOTTO'
    lottery_rules = get_lottery_rules(lottery_type)
    all_draws = db_manager.get_all_draws(lottery_type)
    
    print("-" * 65)
    print(f"🔮 PREDICTING POWER_LOTTO DRAW 114000101 (Latest in DB: {all_draws[0]['draw']})")
    print("-" * 65)
    
    # Selection 1: Entropy Analysis (Best at W=100)
    history_100 = all_draws[:100]
    ent_res = prediction_engine.entropy_predict(history_100, lottery_rules)
    print(f"➜ [Entropy Analysis (W=100)]:")
    print(f"   Numbers: {', '.join(map(lambda x: f'{x:02d}', ent_res['numbers']))}")
    special_val = ent_res.get('special')
    print(f"   Special: {f'{special_val:02d}' if isinstance(special_val, int) else 'N/A'}")
    
    # Selection 2: Trend Analysis (Best at W=500)
    history_500 = all_draws[:500]
    trend_res = prediction_engine.trend_predict(history_500, lottery_rules)
    print(f"\n➜ [Trend Analysis (W=500)]:")
    print(f"   Numbers: {', '.join(map(lambda x: f'{x:02d}', trend_res['numbers']))}")
    special_val = trend_res.get('special')
    print(f"   Special: {f'{special_val:02d}' if isinstance(special_val, int) else 'N/A'}")
    
    # Selection 3: Hot-Cold Mixed (Best at W=500)
    hc_res = prediction_engine.hot_cold_mix_predict(history_500, lottery_rules)
    print(f"\n➜ [Hot-Cold Mixed (W=500)]:")
    print(f"   Numbers: {', '.join(map(lambda x: f'{x:02d}', hc_res['numbers']))}")
    special_val = hc_res.get('special')
    print(f"   Special: {f'{special_val:02d}' if isinstance(special_val, int) else 'N/A'}")
    
    print("-" * 65)

if __name__ == '__main__':
    main()
