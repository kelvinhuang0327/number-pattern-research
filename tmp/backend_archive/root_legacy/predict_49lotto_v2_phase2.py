#!/usr/bin/env python3
import os
import sys
import json
import sqlite3
from datetime import datetime

# Setup paths
project_root = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew"
sys.path.insert(0, project_root)

from lottery_api.models.individual_rhythm_predictor import IndividualRhythmPredictor

DB_PATH = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
PROFILE_PATH_49 = os.path.join(project_root, 'lottery_api', 'data', 'irap_profile_49lotto.json')

def load_draws_49():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # BIG_LOTTO is the source for 49 Lotto
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
        # Use first 6 regular numbers for 49 Lotto
        draws.append({'draw': draw_id, 'date': date, 'numbers': sorted(nums[:6])})
    return draws

def main():
    print("=" * 80)
    print("49 樂合彩 — Phase 2 IRAP v2.3 核心預測")
    print(f"啟動時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    draws = load_draws_49()
    print(f"📊 載入 {len(draws)} 期大樂透歷史資料")
    
    # 1. Initialize and Train IRAP v2.3
    # Pool 49, Pick 6
    predictor = IndividualRhythmPredictor(pool=49, pick=6)
    
    print("🛠️ 正在訓練 49 號碼肖像庫 (含動態衰減與馬可夫矩陣)...")
    # Using 0.995 decay as optimized in 39 lotto test
    predictor.train(draws, decay_factor=0.995)
    
    # 2. Save Profile
    predictor.save_profile(PROFILE_PATH_49)
    print(f"💾 49 樂合彩肖像庫已保存: {PROFILE_PATH_49}")
    
    # 3. Generate Prediction for NEXT Draw
    last_draw = draws[-1]
    print(f"\n🔮 基於期號 {last_draw['draw']} ({last_draw['date']}) 生成下期預測:")
    
    # We generate 6 numbers as a pool (for 2, 3, or 4-bet coverage)
    prediction = predictor.predict(draws, n_to_pick=6)
    
    print(f"\n{'系統建議號碼':<15}: {prediction['numbers']}")
    print(f"{'模型信心度':<15}: {prediction['confidence']*100:.2f}%")
    print(f"{'預測方法':<15}: {prediction['method']}")
    
    print("\n💡 核心訊號分析 (Top 6 Rhythms):")
    # Sort prediction by original scores for insight
    sorted_top = sorted(prediction['details']['top_scores'].items(), key=lambda x: -x[1])[:6]
    
    for n, score in sorted_top:
        prof = predictor.profiling[n]
        print(f"  號碼 #{n:2d} | 總分: {score:6.4f} | 最佳滯後: Lag-{prof['best_lag']:<2} | 回聲優勢: {prof['lag_edge']*100:+.2f}%")

    print("\n" + "=" * 80)
    print("研究指令：您可以執行 'python3 tools/backtest_49lotto_irap.py' 進行完整驗證。")
    print("=" * 80)

if __name__ == "__main__":
    main()
