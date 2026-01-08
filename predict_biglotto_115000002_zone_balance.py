#!/usr/bin/env python3
"""
大樂透 115000002 期 - Zone Balance 預測
使用 500 期窗口的區域平衡策略
"""
import sys
import os

# 設置正確的路徑
script_dir = os.path.dirname(os.path.abspath(__file__))
lottery_api_path = os.path.join(script_dir, 'lottery-api')
sys.path.insert(0, lottery_api_path)
os.chdir(lottery_api_path)

from database import db_manager
from models.unified_predictor import UnifiedPredictionEngine
from common import get_lottery_rules

def main():
    print("=" * 70)
    print("🎱 大樂透 115000002 期預測 - Zone Balance (500期窗口)")
    print("=" * 70)
    
    lottery_type = 'BIG_LOTTO'
    rules = get_lottery_rules(lottery_type)
    
    print(f"\n📋 大樂透規則:")
    print(f"   號碼範圍: {rules['minNumber']} - {rules['maxNumber']}")
    print(f"   選號數量: {rules['pickCount']} 個")
    print(f"   特別號範圍: 1 - {rules.get('specialMax', 8)}")
    
    # 載入數據
    all_draws = db_manager.get_all_draws(lottery_type)
    all_draws.sort(key=lambda x: x.get('date', ''))  # 按日期升序排列
    
    if not all_draws:
        print("❌ 無法載入大樂透數據")
        return
    
    total_draws = len(all_draws)
    last_draw = all_draws[-1]
    
    print(f"\n📊 數據統計:")
    print(f"   總期數: {total_draws} 期")
    print(f"   最新一期: {last_draw.get('draw')} ({last_draw.get('date')})")
    print(f"   開獎號碼: {last_draw.get('numbers')} + 特別號 {last_draw.get('special')}")
    
    # 使用 500 期窗口
    window_size = 500
    history_500 = all_draws[-window_size:] if len(all_draws) >= window_size else all_draws
    actual_window = len(history_500)
    
    print(f"\n🔧 預測參數:")
    print(f"   窗口大小: {actual_window} 期 (目標 {window_size})")
    print(f"   數據範圍: {history_500[0].get('draw')} ~ {history_500[-1].get('draw')}")
    
    # 執行 Zone Balance 預測
    engine = UnifiedPredictionEngine()
    result = engine.zone_balance_predict(history_500, rules)
    
    print("\n" + "=" * 70)
    print("🎯 Zone Balance 預測結果 (500期窗口)")
    print("=" * 70)
    
    numbers = result['numbers']
    confidence = result['confidence']
    method = result['method']
    
    # 格式化輸出
    formatted_numbers = ', '.join([f"{n:02d}" for n in numbers])
    
    print(f"\n  ✅ 預測號碼: {formatted_numbers}")
    print(f"  📊 信心度: {confidence:.1%}")
    print(f"  📈 方法: {method}")
    
    # 號碼分析
    print("\n" + "-" * 70)
    print("📊 號碼分析:")
    
    # 區間分布
    low = [n for n in numbers if n <= 16]
    mid = [n for n in numbers if 17 <= n <= 33]
    high = [n for n in numbers if n >= 34]
    
    print(f"   低區 (01-16): {low} ({len(low)}個)")
    print(f"   中區 (17-33): {mid} ({len(mid)}個)")
    print(f"   高區 (34-49): {high} ({len(high)}個)")
    
    # 奇偶分析
    odd = [n for n in numbers if n % 2 == 1]
    even = [n for n in numbers if n % 2 == 0]
    print(f"   奇數: {odd} ({len(odd)}個)")
    print(f"   偶數: {even} ({len(even)}個)")
    
    # 號碼間距
    gaps = [numbers[i+1] - numbers[i] for i in range(len(numbers)-1)]
    print(f"   號碼間距: {gaps}")
    print(f"   總和: {sum(numbers)}")
    
    # 預測特別號
    print("\n" + "-" * 70)
    print("🔮 特別號預測:")
    
    # 分析最近特別號趨勢
    recent_specials = [d.get('special') for d in history_500[-50:] if d.get('special')]
    from collections import Counter
    special_freq = Counter(recent_specials)
    top_specials = special_freq.most_common(3)
    
    print(f"   最近50期特別號頻率 Top 3: {top_specials}")
    recommended_special = top_specials[0][0] if top_specials else 1
    print(f"   推薦特別號: {recommended_special}")
    
    # 最終輸出
    print("\n" + "=" * 70)
    print("🎱 大樂透 115000002 期 - 最終預測 (單注)")
    print("=" * 70)
    print(f"\n  📍 主號: {formatted_numbers}")
    print(f"  📍 特別號: {recommended_special}")
    print(f"\n  完整組合: {formatted_numbers} + 特別號 {recommended_special}")
    print("=" * 70)
    
    # 比較多種窗口
    print("\n\n📊 不同窗口大小比較:")
    print("-" * 70)
    
    for ws in [100, 200, 300, 500]:
        h = all_draws[-ws:] if len(all_draws) >= ws else all_draws
        r = engine.zone_balance_predict(h, rules)
        nums_str = ', '.join([f"{n:02d}" for n in r['numbers']])
        print(f"  窗口 {ws:3d} 期: {nums_str}  (信心度: {r['confidence']:.1%})")
    
    print("-" * 70)

if __name__ == "__main__":
    main()
