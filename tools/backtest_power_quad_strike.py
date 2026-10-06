#!/usr/bin/env python3
"""
威力彩 Quad Strike 4注回測器
==========================
驗證窗口: 150 / 500 / 1500 期
基準位 (4注隨機): 14.60%
目標: 確認 Edge > 0% 且具備長期穩定性
"""
import os
import sys
import sqlite3
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / 'lottery_api'))

from tools.predict_power_quad_strike import generate_power_quad_strike

# 威力彩 4 注隨機基準 (1-38選6)
# P(1注中3+) = 3.87%
# P(4注中3+) = 1 - (1 - 0.0387)^4 = 1 - 0.8539 = 14.61%
# 採樣 Monte Carlo 也接近 14.60%
BASELINE_4BET = 14.60

def load_history():
    db_path = PROJECT_ROOT / 'lottery_api' / 'data' / 'lottery_v2.db'
    if not db_path.exists():
        # Fallback to older db if needed
        db_path = PROJECT_ROOT / 'lottery_api' / 'data' / 'lottery.db'
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute(
        "SELECT draw, date, numbers, special FROM draws WHERE lottery_type=? ORDER BY date ASC",
        ('POWER_LOTTO',)
    )
    draws = []
    for row in cursor.fetchall():
        nums = json.loads(row[2]) if row[2] else []
        draws.append({
            'draw': row[0], 'date': row[1],
            'numbers': nums, 'special': row[3] or 0
        })
    conn.close()
    return draws

def run_backtest(test_periods=1500):
    all_draws = load_history()
    # 確保有足夠歷史數據進行預測 (需要 500 期 FFT)
    if len(all_draws) < 500 + test_periods:
        test_periods = len(all_draws) - 500
        if test_periods <= 0:
            print("❌ 數據量不足，無法執行回測")
            return 
            
    hits_count = 0
    total = 0
    
    print(f"\n🔬 執行 Power Lotto Quad Strike (4注) 回測: 最近 {test_periods} 期")
    print(f"基準 (4注隨機): {BASELINE_4BET}%")
    
    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        if target_idx < 500:
            continue
            
        target_draw = all_draws[target_idx]
        hist = all_draws[:target_idx]
        actual = set(target_draw['numbers'])
        
        try:
            # 調用 Quad Strike 生成器
            bets = generate_power_quad_strike(hist)
            
            # 計算最佳中獎等級 (最高對幾個)
            best_match = 0
            for bet in bets:
                match = len(set(bet) & actual)
                if match > best_match:
                    best_match = match
            
            # 若最高中三碼以上，計為一次命中
            if best_match >= 3:
                hits_count += 1
            
            total += 1
            
            if total % 100 == 0:
                print(f"  已完成 {total}/{test_periods} 期...")
                
        except Exception as e:
            # print(f"Error at draw {target_draw['draw']}: {e}")
            continue
            
    if total == 0:
        return
        
    hit_rate = hits_count / total * 100
    edge = hit_rate - BASELINE_4BET
    
    print("=" * 65)
    print(f"📊 Power Lotto Quad Strike (4注) 回測結果 (最近 {total} 期)")
    print("-" * 65)
    print(f"  3+ 命中次數: {hits_count}")
    print(f"  3+ 實際勝率: {hit_rate:.2f}%")
    print(f"  隨機基準 (4注): {BASELINE_4BET:.2f}%")
    print(f"  真實 Edge:   {edge:>+7.2f}%")
    print("=" * 65)
    
    if edge > 1.0:
        print("✅ STABLE (具備顯著長期優勢)")
    elif edge > 0:
        print("➡️ MARGINAL (具備微弱優勢)")
    else:
        print("❌ FAILED (不及隨機，建議棄用)")
    print()

if __name__ == "__main__":
    # 分三階段測試，保持穩定性
    for p in [150, 500, 1500]:
        run_backtest(p)
