#!/usr/bin/env python3
"""
大樂透 P0 2注策略 (偏差互補+回聲) 正式回測工具
==========================================
策略: 偏差互補 + Lag-2 Echo (P0)
隨機基準: 3.69% (M3+)
"""
import os
import sys
import numpy as np
from tqdm import tqdm

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from lottery_api.database import DatabaseManager
from tools.quick_predict import biglotto_p0_2bet

def run_backtest(test_periods=1000):
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)
    all_draws = sorted(db.get_all_draws('BIG_LOTTO'), key=lambda x: (x['date'], x['draw']))
    
    if len(all_draws) < 100:
        print("數據不足")
        return

    total = min(len(all_draws) - 100, test_periods)
    hits_count = 0
    baseline = 3.69 # BIG LOTTO 2-bet random baseline
    
    print(f"🚀 開始驗證大樂透 P0 2注基準 {baseline}% (最近 {total} 期)...")
    
    for i in tqdm(range(len(all_draws) - total, len(all_draws))):
        history = all_draws[:i]
        actual = set(all_draws[i]['numbers'])
        
        # 使用 quick_predict.py 中的 P0 實作
        bets_dict = biglotto_p0_2bet(history)
        predict_bets = [b['numbers'] for b in bets_dict]
        
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
    print(f"📊 BigLotto P0 (2注) 回測結果 (最近 {total} 期)")
    print("-" * 65)
    print(f"  命中次數 (M3+): {hits_count}")
    print(f"  實際命中率:     {hit_rate:.2f}%")
    print(f"  隨機期望值:     {baseline:.2f}%")
    print(f"  戰勝隨機 (Edge): {edge:+.2f}%")
    print("-" * 65)
    
    if edge > 0.5:
        print("💡 結論: ✅ STABLE (具備顯著長期優勢)")
    else:
        print("💡 結論: ❓ MARGINAL/UNCERTAIN")
    print("=" * 65 + "\n")

if __name__ == "__main__":
    for p in [150, 500, 1000]:
        run_backtest(p)
