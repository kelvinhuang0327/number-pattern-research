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
BASELINE_GE2 = 0.113973

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

def run_block_test(all_draws, start_idx, end_idx):
    """
    Train on draws[:start_idx]
    Test on draws[start_idx:end_idx]
    """
    train_data = all_draws[:start_idx]
    test_data = all_draws[start_idx:end_idx]
    
    predictor = IndividualRhythmPredictor(pool=POOL, pick=PICK)
    predictor.train(train_data)
    
    ge2_count = 0
    total_test = len(test_data)
    if total_test == 0: return None
    
    for i in range(total_test):
        # Using the static profile trained at the start of the block
        res = predictor.predict(all_draws[:start_idx + i])
        pred = set(res['numbers'])
        actual = set(test_data[i]['numbers'])
        if len(pred & actual) >= 2:
            ge2_count += 1
            
    rate = ge2_count / total_test
    return {
        'rate': rate,
        'edge': rate - BASELINE_GE2,
        'count': total_test,
        'start_draw': test_data[0]['draw'],
        'end_draw': test_data[-1]['draw']
    }

def main():
    draws = load_draws()
    N = len(draws)
    
    # We begin testing from draw 3500 to get more blocks
    # Historically: N is around 5771. 3500 to 5771 is 2271 draws.
    # We divide these into blocks of 300 draws each.
    
    TEST_START = 3500
    BLOCK_SIZE = 300
    
    print("=" * 100)
    print("IRAP 時期分解深度分析 (Period Decomposition Audit)")
    print(f"目的: 驗證 +1.53% Edge 的跨時期穩定性，排除「單一幸運窗口」假說")
    print(f"基準 >=2 機率: {BASELINE_GE2*100:.4f}%")
    print("=" * 100)
    print(f"{'時段 (Index)':<15} {'起始期號':<12} {'結束期號':<12} {'>=2 Rate':<12} {'Edge':<12} {'判定'}")
    print("-" * 100)
    
    block_edges = []
    
    for start in range(TEST_START, N, BLOCK_SIZE):
        end = min(start + BLOCK_SIZE, N)
        res = run_block_test(draws, start, end)
        if not res: continue
        
        edge = res['edge']
        block_edges.append(edge)
        
        verdict = "✅ STABLE" if edge > 0 else "❌ FAILED"
        if edge > 0.02: verdict = "🔥 STRONG"
        
        print(f"{start:4d}-{end:<10d} {res['start_draw']:<12} {res['end_draw']:<12} {res['rate']*100:10.2f}% {edge*100:+11.3f}% {verdict}")

    print("-" * 100)
    avg_edge = np.mean(block_edges)
    std_edge = np.std(block_edges)
    consistency = (sum(1 for e in block_edges if e > 0) / len(block_edges)) * 100
    
    print(f"平均 Edge: {avg_edge*100:+.3f}%")
    print(f"Edge 標準差 (Volatility): {std_edge*100:.3f}%")
    print(f"正向勝率 (Period Win-Rate): {consistency:.1f}%")
    
    print("\n💡 最終判斷:")
    if consistency >= 75:
        print(">>> 結論：IRAP 展現了高度的【跨時期穩定性】，Edge 並非由單一幸運窗口撐起，具備進入 Phase 2 的實力。")
    elif consistency >= 50:
        print(">>> 結論：IRAP 具備【週期性優勢】，但存在明顯的失效時期，Phase 2 需強化 Regime Detection。")
    else:
        print(">>> 結論：IRAP 表現接近隨機漂移，+1.53% 極可能是幸運偏差，建議重新審視個體節律假說。")
    print("=" * 100)

if __name__ == "__main__":
    main()
