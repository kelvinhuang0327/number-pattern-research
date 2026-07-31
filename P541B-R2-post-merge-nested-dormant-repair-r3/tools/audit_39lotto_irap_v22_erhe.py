#!/usr/bin/env python3
import os
import sys
import json
import sqlite3
import numpy as np
from datetime import datetime

# Setup paths
project_root = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew"
sys.path.insert(0, project_root)

from lottery_api.models.individual_rhythm_predictor import IndividualRhythmPredictor

DB_PATH = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
POOL = 39
PICK = 5
BASELINE_ERHE = 0.01349 # P(2 hits in 2 picks)
ERHE_PAYOFF = 53

def load_draws():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT draw, date, numbers FROM draws
        WHERE lottery_type = 'DAILY_539'
        ORDER BY date ASC, draw ASC
    """)
    rows = cursor.fetchall()
    conn.close()
    draws = []
    for draw_id, date, numbers_str in rows:
        nums = json.loads(numbers_str)
        draws.append({'draw': draw_id, 'date': date, 'numbers': sorted(nums)})
    return draws

def run_erhe_audit(draws, test_periods):
    """
    Backtest IRAP v2.2 for Er-he (Top-2)
    """
    train_data = draws[:-test_periods]
    test_data = draws[-test_periods:]
    
    predictor = IndividualRhythmPredictor(pool=POOL, pick=PICK)
    # Using v2.1 decay training
    predictor.train(train_data, decay_factor=0.995)
    
    erhe_hits = 0
    
    # Track daily ROI
    cumulative_profit = 0
    bets_count = 0
    
    print(f"Running Er-he ROI Stress Test on last {test_periods} draws...")
    
    for i in range(len(test_data)):
        # IRAP v2.2 ADW prediction
        res = predictor.predict(draws[:len(train_data)+i], n_to_pick=2)
        pred = set(res['numbers'])
        actual = set(test_data[i]['numbers'])
        
        bets_count += 1
        cumulative_profit -= 1 # Cost of 1 bet
        
        if len(pred & actual) == 2:
            erhe_hits += 1
            cumulative_profit += ERHE_PAYOFF # Win
            
        if (i+1) % 50 == 0:
            current_roi = (cumulative_profit / bets_count) * 100
            print(f"  Draw {i+1}/{test_periods}: Hits={erhe_hits}, ROI={current_roi:+.1f}%")
            
    hit_rate = erhe_hits / test_periods
    total_roi = (cumulative_profit / bets_count) * 100
    
    return {
        'hit_rate': hit_rate,
        'edge': hit_rate - BASELINE_ERHE,
        'roi': total_roi,
        'total_profit': cumulative_profit,
        'bets': bets_count,
        'hits': erhe_hits
    }

def main():
    draws = load_draws()
    # Test on the last 571 draws (approx 2 years)
    res = run_erhe_audit(draws, 571)
    
    print("\n" + "=" * 60)
    print("IRAP v2.2 Er-he (Top-2) 實戰 ROI 壓力測試")
    print("=" * 60)
    print(f"{'指標':<20}: {'數值'}")
    print("-" * 60)
    print(f"{'測試期數':<20}: {res['bets']}")
    print(f"{'二合命中次數':<20}: {res['hits']}")
    print(f"{'實際命中率':<20}: {res['hit_rate']*100:.4f}%")
    print(f"{'理論基準率':<20}: {BASELINE_ERHE*100:.2f}%")
    print(f"{'超額贏率 (Edge)':<20}: {res['edge']*100:+.4f}%")
    print(f"{'最終 ROI':<20}: {res['roi']:+.2f}%")
    print(f"{'總淨利 (Bet=1)':<20}: {res['total_profit']:+.1f}")
    print("-" * 60)
    
    if res['roi'] > 0:
        print("🟢 測試通過：策略具備正向盈利預期。")
    else:
        print("🔴 測試失敗：雖然有 Edge，但不足以抵銷稅率或賠率差。")
    print("=" * 60)

if __name__ == "__main__":
    main()
