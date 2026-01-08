#!/usr/bin/env python3
"""
威力彩結果驗證器 (Result Validator)
開獎後自動驗證預測結果，更新命中統計。
"""
import sys
import os
import json
from collections import Counter

# Add project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery-api'))

from database import DatabaseManager

PREDICTIONS_LOG = os.path.join(project_root, 'data', 'predictions_log.json')

def load_predictions_log():
    """載入預測記錄"""
    if os.path.exists(PREDICTIONS_LOG):
        with open(PREDICTIONS_LOG, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"predictions": []}

def save_predictions_log(log_data):
    """儲存預測記錄"""
    with open(PREDICTIONS_LOG, 'w', encoding='utf-8') as f:
        json.dump(log_data, f, ensure_ascii=False, indent=2)

def get_prize_tier(match_count, special_match):
    """判定獎項等級"""
    if match_count == 6 and special_match:
        return "頭獎 (Match-6+S)"
    elif match_count == 6:
        return "貳獎 (Match-6)"
    elif match_count == 5 and special_match:
        return "參獎 (Match-5+S)"
    elif match_count == 5:
        return "肆獎 (Match-5)"
    elif match_count == 4 and special_match:
        return "伍獎 (Match-4+S)"
    elif match_count == 4:
        return "陸獎 (Match-4)"
    elif match_count == 3 and special_match:
        return "柒獎 (Match-3+S)"
    elif match_count == 3:
        return "普獎 (Match-3)"
    elif match_count == 2 and special_match:
        return "捌獎 (Match-2+S)"
    else:
        return "未中獎"

def validate_predictions():
    """驗證所有未驗證的預測"""
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery-api', 'data', 'lottery_v2.db'))
    all_draws = {int(d['draw']): d for d in db.get_all_draws(lottery_type='POWER_LOTTO')}
    
    log_data = load_predictions_log()
    updated = False
    
    print("🔍 開始驗證預測結果...")
    print("=" * 60)
    
    for pred in log_data["predictions"]:
        if pred["validated"]:
            continue
        
        target_draw = pred["target_draw"]
        
        # 檢查是否已開獎
        if target_draw not in all_draws:
            print(f"⏳ 期數 {target_draw} 尚未開獎，跳過")
            continue
        
        actual_draw = all_draws[target_draw]
        actual_numbers = set(actual_draw['numbers'])
        actual_special = actual_draw['special']
        
        print(f"\n📍 驗證期數: {target_draw}")
        print(f"開獎號碼: {sorted(actual_numbers)} + {actual_special}")
        print("-" * 60)
        
        # 驗證每一注
        best_prize = "未中獎"
        best_match = 0
        results = []
        
        for i, bet in enumerate(pred["bets"]):
            bet_numbers = set(bet["numbers"])
            bet_special = bet["special"]
            
            match_count = len(bet_numbers & actual_numbers)
            special_match = (bet_special == actual_special)
            prize = get_prize_tier(match_count, special_match)
            
            results.append({
                "bet_index": i + 1,
                "match_count": match_count,
                "special_match": special_match,
                "prize": prize
            })
            
            if match_count > best_match or (match_count == best_match and special_match):
                best_match = match_count
                best_prize = prize
            
            status = "✅" if prize != "未中獎" else "❌"
            print(f"{status} 注 {i+1}: Match-{match_count}{'+S' if special_match else ''} → {prize}")
        
        # 更新記錄
        pred["validated"] = True
        pred["result"] = {
            "actual_numbers": sorted(actual_numbers),
            "actual_special": actual_special,
            "best_prize": best_prize,
            "best_match": best_match,
            "details": results
        }
        
        updated = True
        print("-" * 60)
        print(f"🏆 本期最佳: {best_prize}")
    
    if updated:
        save_predictions_log(log_data)
        print("\n✅ 驗證完成，記錄已更新")
    else:
        print("\n💤 無新的開獎結果需要驗證")
    
    # 統計總體表現
    print("\n" + "=" * 60)
    print("📊 總體統計")
    print("=" * 60)
    
    validated_preds = [p for p in log_data["predictions"] if p["validated"]]
    if validated_preds:
        prize_counter = Counter()
        for pred in validated_preds:
            prize_counter[pred["result"]["best_prize"]] += 1
        
        total = len(validated_preds)
        print(f"已驗證期數: {total}")
        print("\n獎項分佈:")
        for prize, count in sorted(prize_counter.items(), key=lambda x: -count):
            pct = count / total * 100
            print(f"  {prize}: {count} 次 ({pct:.1f}%)")
        
        # 計算有效中獎率（Match-3+）
        meaningful_wins = sum(count for prize, count in prize_counter.items() 
                            if "Match-3" in prize or "Match-4" in prize or 
                               "Match-5" in prize or "Match-6" in prize)
        win_rate = meaningful_wins / total * 100
        print(f"\n🎯 有效中獎率 (Match-3+): {win_rate:.2f}%")

if __name__ == '__main__':
    validate_predictions()
