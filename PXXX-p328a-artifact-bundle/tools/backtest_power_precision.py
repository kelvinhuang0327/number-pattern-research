#!/usr/bin/env python3
"""
威力彩 Power Precision (3注) 正式回測工具
=======================================
策略: Fourier (2注) + Echo/Cold (1注)
隨機基準: 11.17% (M3+)
"""
import os
import sys
import numpy as np
from tqdm import tqdm

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from lottery_api.database import DatabaseManager
from tools.predict_power_precision_3bet import generate_power_precision_3bet

def run_backtest(test_periods=1384):
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)
    all_draws = sorted(db.get_all_draws('POWER_LOTTO'), key=lambda x: (x['date'], x['draw']))
    
    if len(all_draws) < 500:
        print("數據不足，無法執行回測")
        return

    total = min(len(all_draws) - 500, test_periods)
    hits_count = 0
    baseline = 11.17 # Power Lotto 3-bet random baseline
    
    print(f"🚀 開始挑戰隨機基準 {baseline}% (威力彩 3注)...")
    
    # 滑動窗口回測
    for i in tqdm(range(len(all_draws) - total, len(all_draws))):
        history = all_draws[:i]
        actual = set(all_draws[i]['numbers'])
        
        # 生成預測 (3注)
        predict_bets = generate_power_precision_3bet(history)
        
        # 判定 M3+ (任一注中三號或以上)
        is_hit = False
        for bet in predict_bets:
            match_count = len(set(bet) & actual)
            if match_count >= 3:
                is_hit = True
                break
        
        if is_hit:
            hits_count += 1

    hit_rate = hits_count / total * 100
    edge = hit_rate - baseline
    
    print("\n" + "=" * 65)
    print(f"📊 Power Precision (3注) 回測結果 (最近 {total} 期)")
    print("-" * 65)
    print(f"  命中次數 (M3+): {hits_count}")
    print(f"  實際命中率:     {hit_rate:.2f}%")
    print(f"  隨機期望值:     {baseline:.2f}%")
    print(f"  戰勝隨機 (Edge): {edge:+.2f}%")
    print("-" * 65)
    
    if edge > 1.5:
        print("💡 結論: ✅ STABLE (具備顯著長期優勢)")
    elif edge > 0:
        print("💡 結論: ➡️ MARGINAL (具備微弱優勢)")
    else:
        print("💡 結論: ❌ FAILED (不及隨機)")
    print("=" * 65 + "\n")

if __name__ == "__main__":
    periods = 1384
    if len(sys.argv) > 1:
        periods = int(sys.argv[1])
    run_backtest(periods)
