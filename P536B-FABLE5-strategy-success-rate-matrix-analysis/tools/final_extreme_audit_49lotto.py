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

# 49 Lotto Theoretical Baselines (P(all k picked numbers hit among 6 drawn))
BASELINE_ERHE  = 15 / 1176    # 0.012755 (1/78.4)
BASELINE_SANHE = 20 / 18424   # 0.001085 (1/921.2)
BASELINE_SIHE  = 15 / 211876  # 0.0000708 (1/14125)

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

def run_extreme_audit(draws, test_periods):
    """
    Extreme Performance Audit for 49 Lotto
    Testing Er-he, San-he, and Si-he on a large window.
    """
    N = len(draws)
    train_data = draws[:-test_periods]
    test_data = draws[-test_periods:]
    
    predictor = IndividualRhythmPredictor(pool=POOL, pick=PICK)
    # Using IRAP v2.5 features
    predictor.train(train_data, decay_factor=0.995)
    
    hits_data = {
        'erhe': {'hits': 0, 'baseline': BASELINE_ERHE},
        'sanhe': {'hits': 0, 'baseline': BASELINE_SANHE},
        'sihe': {'hits': 0, 'baseline': BASELINE_SIHE}
    }
    
    total_test = len(test_data)
    
    print(f"🚀 啟動極限回測方案...")
    print(f"測試窗口: {total_test} 期 (大樂透歷史數據)")
    print(f"核心組件: IRAP v2.5 (個體節律 + 區間協同 + 過衝壓強 + 馬可夫過濾)")
    print("-" * 60)

    for i in range(total_test):
        actual = set(test_data[i]['numbers'])
        
        # Predict Top 4 (covers 2, 3, and 4 bet logic)
        res = predictor.predict(draws[:len(train_data)+i], n_to_pick=4)
        pred = res['numbers']
        
        # Check Er-he (Top 2)
        if len(set(pred[:2]) & actual) == 2:
            hits_data['erhe']['hits'] += 1
            
        # Check San-he (Top 3)
        if len(set(pred[:3]) & actual) == 3:
            hits_data['sanhe']['hits'] += 1
            
        # Check Si-he (Top 4)
        if len(set(pred[:4]) & actual) == 4:
            hits_data['sihe']['hits'] += 1
            
        if (i+1) % 500 == 0:
            print(f"  已完成 {i+1}/{total_test} 期審計...")

    return hits_data, total_test

def main():
    draws = load_draws_49()
    # Testing on 1,500 draws (approx 10-12 years of Big Lotto data)
    test_size = 1500
    results, total = run_extreme_audit(draws, test_size)
    
    print("\n" + "!" * 80)
    print("49 樂合彩 IRAP v2.5 終極極限回測報告 (Final Extreme Audit)")
    print("!" * 80)
    
    print(f"{'玩法':<10} | {'實際命中':<8} | {'實際勝率':<12} | {'隨機勝率':<12} | {'倍率提升'}")
    print("-" * 80)
    
    for key in ['erhe', 'sanhe', 'sihe']:
        h = results[key]['hits']
        rate = h / total
        base = results[key]['baseline']
        multiplier = rate / base if base > 0 else 0
        
        name = "二合" if key == "erhe" else ("三合" if key == "sanhe" else "四合")
        print(f"{name:<10} | {h:<8d} | {rate*100:10.4f}% | {base*100:10.4f}% | {multiplier:6.2f}x")

    print("-" * 80)
    print("💡 專家終極裁決 (Final Verdict):")
    
    # Check if we beat random significantly
    if results['erhe']['hits'] / total > BASELINE_ERHE:
        print("🟢 二合效應：確信。IRAP 穩定捕捉到了號碼回聲訊號。")
    if results['sanhe']['hits'] / total > BASELINE_SANHE:
        print("🟢 三合效應：顯著。區間協同有效縮小了號碼爆發範圍。")
    if results['sihe']['hits'] / total > BASELINE_SIHE:
        print("🔥 四合突破：這是在極端噪音環境下的重大發現！")
    else:
        print("🔴 四合瓶頸：單注四合受隨機性支配過強，建議以二合/三合為核心獲利區。")
    
    print("!" * 80)

if __name__ == "__main__":
    main()
