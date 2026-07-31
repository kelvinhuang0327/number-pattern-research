#!/usr/bin/env python3
"""
大樂透 Triple Strike (3注) 正式回測工具
=====================================
策略: Fourier (注1) + Cold (注2) + Tail Balance (注3)
隨機基準: 5.49% (M3+)
"""
import os
import sys
import numpy as np
from tqdm import tqdm

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from lottery_api.database import DatabaseManager
from tools.predict_biglotto_triple_strike import generate_triple_strike

def run_backtest(test_periods=1500):
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)
    all_draws = sorted(db.get_all_draws('BIG_LOTTO'), key=lambda x: (x['date'], x['draw']))
    
    if len(all_draws) < 500:
        print("數據不足，無法執行回測")
        return

    total = min(len(all_draws) - 500, test_periods)
    hits_count = 0
    baseline = 5.49 # BIG LOTTO 3-bet random baseline
    
    print(f"🚀 開始驗證大樂透 Triple Strike 基準 {baseline}% (最近 {total} 期)...")
    
    for i in tqdm(range(len(all_draws) - total, len(all_draws))):
        history = all_draws[:i]
        actual = set(all_draws[i]['numbers'])
        
        # 生成預測 (3注)
        predict_bets = generate_triple_strike(history)
        
        is_hit = False
        for bet in predict_bets:
            if len(set(bet) & actual) >= 3:
                is_hit = True
                break
        if is_hit:
            hits_count += 1

    hit_rate = hits_count / total * 100
    edge = hit_rate - baseline
    
    print("\n" + "=" * 65)
    print(f"📊 Triple Strike (3注) 回測結果 (最近 {total} 期)")
    print("-" * 65)
    print(f"  命中次數 (M3+): {hits_count}")
    print(f"  實際命中率:     {hit_rate:.2f}%")
    print(f"  隨機期望值:     {baseline:.2f}%")
    print(f"  戰勝隨機 (Edge): {edge:+.2f}%")
    print("-" * 65)
    
    if edge > 0.5:
        print("💡 結論: ✅ STABLE (具備顯著長期優勢)")
    elif edge > 0:
        print("💡 結論: ➡️ MARGINAL (具備微弱優勢)")
    else:
        print("💡 結論: ❌ FAILED (不及隨機)")
    print("=" * 65 + "\n")

if __name__ == "__main__":
    for p in [150, 500, 1500]:
        run_backtest(p)
