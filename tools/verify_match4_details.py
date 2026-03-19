#!/usr/bin/env python3
"""
Match-4+ 詳細驗證腳本
逐期檢查大樂透雙注組合的 Match-4 次數
"""
import sys
import os
from collections import Counter

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules
from models.unified_predictor import UnifiedPredictionEngine
from models.biglotto_3bet_optimizer import BigLotto3BetOptimizer

def verify_match4_details():
    """詳細驗證 Match-4+ 次數"""
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = list(reversed(db.get_all_draws(lottery_type='BIG_LOTTO')))
    rules = get_lottery_rules('BIG_LOTTO')
    
    test_periods = 150
    
    engine = UnifiedPredictionEngine()
    optimizer = BigLotto3BetOptimizer()
    
    import random
    
    print("=" * 80)
    print("🔍 確定性驗證（大樂透三注 BigLotto3BetOptimizer + 固定種子）")
    print("=" * 80)
    print(f"測試窗口大小: {test_periods}")
    print(f"策略: 每期使用 Draw Number 作為隨機池種子")
    print("-" * 80)
    
    match_4_details = []
    match_3_details = []
    match_distribution = Counter()
    
    print("\n開始逐期驗證...")
    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        if target_idx <= 0: continue
        
        target_draw = all_draws[target_idx]
        hist = all_draws[:target_idx]
        if len(hist) < 50: continue
        
        actual = set(target_draw['numbers'])
        
        try:
            # 💡 固定隨機種子以確保可重複性
            random.seed(int(target_draw['draw']))
            
            # 執行預測
            result = optimizer.predict_3bets_diversified(hist, rules)
            bets = [set(b['numbers']) for b in result['bets']]
            matches = [len(b & actual) for b in bets]
            best_match = max(matches)
            
            match_distribution[best_match] += 1
            
            if best_match >= 4:
                match_4_details.append({
                    'draw': target_draw['draw'],
                    'date': target_draw['date'],
                    'match': best_match,
                    'matches': sorted(matches, reverse=True),
                    'overlap': sorted(bets[matches.index(best_match)] & actual)
                })
                print(f"⭐ 發現 Match-{best_match}！期號 {target_draw['draw']}")
            elif best_match == 3:
                match_3_details.append(target_draw['draw'])
        except Exception as e:
            print(f"❌ 錯誤於 {target_draw['draw']}: {e}")
            continue

    # 顯示結果
    print("\n" + "=" * 80)
    print("📊 確定性驗證結果")
    print("=" * 80)
    
    print(f"\nMatch-4+ 總次數: {len(match_4_details)}")
    print(f"Match-4+ 率: {len(match_4_details) / test_periods * 100:.2f}%")
    
    if match_4_details:
        for idx, detail in enumerate(match_4_details, 1):
            print(f"  [{idx}] 期號 {detail['draw']}: Match-{detail['match']} (命中: {detail['overlap']})")
    
    print(f"\nMatch-3 總次數: {len(match_3_details)}")
    print(f"Match-3+ 總率: {(len(match_4_details)+len(match_3_details)) / test_periods * 100:.2f}%")

    # 命中分布
    print("\n" + "=" * 80)
    print("📊 完整命中分布")
    print("=" * 80)
    for match_count in sorted(match_distribution.keys(), reverse=True):
        count = match_distribution[match_count]
        pct = count / test_periods * 100
        print(f"  Match-{match_count}: {count:3d} 次 ({pct:5.1f}%)")
    
    # 資料庫資訊
    print("\n" + "=" * 80)
    print("💾 資料庫資訊")
    print("=" * 80)
    print(f"資料庫路徑: lottery_api/data/lottery_v2.db")
    print(f"大樂透總期數: {len(all_draws)}")
    print(f"最新期號: {all_draws[0]['draw']}")
    print(f"最新日期: {all_draws[0]['date']}")
    print(f"最舊期號: {all_draws[-1]['draw']}")
    print(f"最舊日期: {all_draws[-1]['date']}")
    
    # 測試窗口
    print("\n" + "=" * 80)
    print("🔍 測試窗口")
    print("=" * 80)
    test_start_idx = len(all_draws) - test_periods
    print(f"測試起始期號: {all_draws[test_start_idx]['draw']} ({all_draws[test_start_idx]['date']})")
    print(f"測試結束期號: {all_draws[-1]['draw']} ({all_draws[-1]['date']})")
    print(f"測試期數: {test_periods}")
    
    # 最終結論
    print("\n" + "=" * 80)
    print("✅ 驗證結論")
    print("=" * 80)
    
    if len(match_4_details) == 0:
        print("📌 本次驗證：Match-4+ 為 0 次")
        print("📝 如果之前報告顯示有 Match-4，可能原因：")
        print("   1. 資料庫數據不同（新增或修正期數）")
        print("   2. 測試窗口不同（期數範圍）")
        print("   3. 預測方法版本不同")
        print("   4. 隨機種子或權重差異")
    else:
        print(f"📌 本次驗證：Match-4+ 共 {len(match_4_details)} 次")
        print(f"   Match-4+ 率: {len(match_4_details) / test_periods * 100:.2f}%")
    
    print("\n建議後續行動：")
    print("1. 檢查資料庫是否最新（可能有新開獎數據）")
    print("2. 確認測試期數範圍（150期 從哪一期開始）")
    print("3. 對比 Gemini 報告使用的測試窗口")
    print("=" * 80)

if __name__ == '__main__':
    verify_match4_details()
