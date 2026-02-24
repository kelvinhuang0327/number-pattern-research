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
POOL = 49
PICK = 6

# Real-world 49 Lotto (Big Lotto Base) Payouts:
# 二合: 1/78.4 -> Payoff 1:53 (Wait, 39 lotto is 50/1150 ~= 23x, let's verify)
# Note: For 49 lotto Er-he, typical payoff is around 1,250 NTD for a 25 NTD bet -> 50x. 
# Tax might be involved for larger wins.
ERHE_PAYOFF = 50.0  # Approx payoff ratio for 49 lotto Er-he
SANHE_PAYOFF = 500.0 # Approx payoff ratio for 49 lotto San-he (typical 12500/25)
BASELINE_ERHE = (6/49) * (5/48) # 0.012755 (1.28%)
BASELINE_SANHE = (6/49) * (5/48) * (4/47) # 0.001085 (0.11%)

def load_draws_49():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT draw, date, numbers FROM draws
        WHERE lottery_type = 'BIG_LOTTO'
        ORDER BY date ASC, draw ASC
    """)
    rows = cursor.fetchall()
    conn.close()
    draws = []
    for draw_id, date, numbers_str in rows:
        nums = json.loads(numbers_str)
        draws.append({'draw': draw_id, 'date': date, 'numbers': sorted(nums[:6])})
    return draws

def run_roi_audit_49(draws, test_periods):
    """
    Backtest IRAP v2.3 for 49 Lotto Er-he and San-he
    """
    N = len(draws)
    train_data = draws[:-test_periods]
    test_data = draws[-test_periods:]
    
    predictor = IndividualRhythmPredictor(pool=POOL, pick=PICK)
    # Using 0.995 decay
    predictor.train(train_data, decay_factor=0.995)
    
    erhe_hits = 0
    sanhe_hits = 0
    
    total_bets = 0
    erhe_profit = 0
    sanhe_profit = 0
    
    print(f"Running 49 Lotto ROI Stress Test on last {test_periods} draws...")
    
    for i in range(len(test_data)):
        # Predict Top 2 and Top 3
        actual = set(test_data[i]['numbers'])
        
        # Er-he prediction (Top 2)
        res_erhe = predictor.predict(draws[:len(train_data)+i], n_to_pick=2)
        pred_erhe = set(res_erhe['numbers'])
        if len(pred_erhe & actual) == 2:
            erhe_hits += 1
            erhe_profit += ERHE_PAYOFF
        erhe_profit -= 1 # Bet cost
        
        # San-he prediction (Top 3)
        res_sanhe = predictor.predict(draws[:len(train_data)+i], n_to_pick=3)
        pred_sanhe = set(res_sanhe['numbers'])
        if len(pred_sanhe & actual) == 3:
            sanhe_hits += 1
            sanhe_profit += SANHE_PAYOFF
        sanhe_profit -= 1 # Bet cost
        
        total_bets += 1
            
    return {
        'total_bets': total_bets,
        'erhe': {
            'hits': erhe_hits,
            'rate': erhe_hits / total_bets,
            'edge': (erhe_hits / total_bets) - BASELINE_ERHE,
            'roi': (erhe_profit / total_bets) * 100,
            'profit': erhe_profit
        },
        'sanhe': {
            'hits': sanhe_hits,
            'rate': sanhe_hits / total_bets,
            'edge': (sanhe_hits / total_bets) - BASELINE_SANHE,
            'roi': (sanhe_profit / total_bets) * 100,
            'profit': sanhe_profit
        }
    }

def main():
    draws = load_draws_49()
    # Audit last 500 draws (Significant period for 49 lotto)
    res = run_roi_audit_49(draws, 500)
    
    print("\n" + "=" * 80)
    print("49 樂合彩 — IRAP v2.3 深度 ROI 回測審計 (二合/三合)")
    print("=" * 80)
    
    # 二合結果
    print(f"【二合 Er-He】 (Payoff 1:{ERHE_PAYOFF:g})")
    print(f"  實際命中率: {res['erhe']['rate']*100:.4f}% (理論: {BASELINE_ERHE*100:.2f}%)")
    print(f"  超額贏率 (Edge): {res['erhe']['edge']*100:+.4f}%")
    print(f"  最終 ROI  : {res['erhe']['roi']:+.2f}%")
    print(f"  判定      : {'🟢 PROFITABLE' if res['erhe']['roi'] > 0 else '🔴 NEGATIVE'}")
    
    print("-" * 80)
    
    # 三合結果
    print(f"【三合 San-He】 (Payoff 1:{SANHE_PAYOFF:g})")
    print(f"  實際命中率: {res['sanhe']['rate']*100:.4f}% (理論: {BASELINE_SANHE*100:.2f}%)")
    print(f"  超額贏率 (Edge): {res['sanhe']['edge']*100:+.4f}%")
    print(f"  最終 ROI  : {res['sanhe']['roi']:+.2f}%")
    print(f"  判定      : {'🟢 PROFITABLE' if res['sanhe']['roi'] > 0 else '🔴 NEGATIVE'}")
    
    print("\n" + "=" * 80)
    print("💡 肖像庫下一階段優化方向:")
    print("  1. 針對三合爆發力，引入『遺漏值過衝 (Gap Overshoot)』修正組件。")
    print("  2. 調試『馬可夫鏈門檻』，過濾低概率轉移對。")
    print("=" * 80)

if __name__ == "__main__":
    main()
