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
PROFILE_PATH = os.path.join(project_root, 'lottery_api', 'data', 'irap_profile_39lotto.json')

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

def main():
    print("=" * 80)
    print("39樂合彩 v2 — Phase 2 IRAP 核心預測 (Individual Rhythm Adaptive Predictor)")
    print(f"啟動時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    draws = load_draws()
    print(f"📊 載入 {len(draws)} 期歷史資料")
    
    # 1. Initialize and Train IRAP
    predictor = IndividualRhythmPredictor(pool=39, pick=5)
    print("🛠️ 開始號碼個體節律畫像 (Individual Rhythm Profiling)...")
    predictor.train(draws)
    
    # 2. Save Profile
    predictor.save_profile(PROFILE_PATH)
    print(f"💾 肖像庫已保存至: {PROFILE_PATH}")
    
    # 3. Generate Prediction for NEXT Draw
    # Assuming the next draw follows the last one in DB
    last_draw_id = draws[-1]['draw']
    next_draw_date = "2026-02-xx" # Approximation
    
    print(f"\n🔮 為下一期 ({last_draw_id}+) 生成 1-bet 正交預測:")
    prediction = predictor.predict(draws)
    
    print(f"\n{'系統建議號碼':<15}: {prediction['numbers']}")
    print(f"{'模型信心度':<15}: {prediction['confidence']*100:.2f}%")
    print(f"{'預測方法':<15}: {prediction['method']}")
    
    print("\n💡 核心訊號分析 (IRAP Components):")
    for n in prediction['numbers']:
        comp = prediction['details']['rhythm_components'][n]
        print(f"  號碼 #{n:2d} | 最佳滯後: Lag-{comp['best_lag']:<2} (Edge: {comp['lag_edge']*100:+.2f}%) | 週期振幅: {comp['fourier_amp']:.4f}")

    print("\n" + "=" * 80)
    print("Phase 2 決議：IRAP 模型已取代 Phase 1 的全局假說模型。")
    print("=" * 80)

if __name__ == "__main__":
    main()
