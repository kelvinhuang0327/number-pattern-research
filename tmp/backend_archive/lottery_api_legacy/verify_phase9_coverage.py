
import numpy as np
import sys
import os
import json
from collections import Counter

# Setup path
lottery_api_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, lottery_api_dir)
os.chdir(lottery_api_dir)

# Fix DB path
from database import db_manager
db_manager.db_path = os.path.join(lottery_api_dir, "data", "lottery_v2.db")

from models.multi_bet_optimizer import MultiBetOptimizer
from common import load_backend_history

def validate():
    # ==================== 目標號碼 ====================
    target_numbers = [9, 20, 25, 35, 39, 48]
    draw_id = 115000014
    lottery_type = 'BIG_LOTTO'
    
    # ==================== 載入歷史與環境 ====================
    history, rules = load_backend_history(lottery_type)
    h_pred = [d for d in history if int(d['draw']) < draw_id]
    
    print(f"🔬 正在驗證 Phase 9: Coverage-Max Union Strategy (三注聯合覆蓋優化)")
    print(f"🎯 目標期號: {draw_id} | 號碼: {target_numbers}")
    
    # 取得基礎分數 (使用內部 logic 模擬)
    # 這裡我們模擬一個 standard scores 傳入
    all_nums = [n for d in h_pred[:200] for n in d['numbers']]
    freq_counter = Counter(all_nums)
    number_scores = {n: freq_counter.get(n, 0) for n in range(1, 49 + 1)}
    
    # ==================== 執行優化器 ====================
    optimizer = MultiBetOptimizer()
    result = optimizer.generate_coverage_max_3bets(h_pred, rules, number_scores)
    
    # ==================== 結果分析 ====================
    print("\n" + "=" * 80)
    print(f"📋 優化方法: {result['method']} | 環境機制: {result['regime']}")
    print("=" * 80)
    
    total_hits = set()
    for i, bet in enumerate(result['bets']):
        nums = bet['numbers']
        hits = sorted(list(set(nums) & set(target_numbers)))
        print(f"注項 {i+1} ({bet['source']}): {nums} | 命中: {hits} ({len(hits)} 支)")
        total_hits.update(hits)
        
    print("-" * 80)
    print(f"🔥 三注聯合總命中: {sorted(list(total_hits))} ({len(total_hits)} 支)")
    print(f"📈 聯合覆蓋率: {result['coverage'] * 100:.1f}%")
    
    if len(total_hits) >= 4:
        print("\n✅ 驗證成功：聯合覆蓋達到 4 支或以上，成功捕捉冷冷回補與動能號碼。")
    else:
        print("\n⚠️ 驗證提醒：聯合覆蓋未達預期，需檢視特定權重分配。")

if __name__ == '__main__':
    validate()
