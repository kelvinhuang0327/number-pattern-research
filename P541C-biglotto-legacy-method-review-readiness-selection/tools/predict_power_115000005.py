#!/usr/bin/env python3
"""
威力彩 115000005 雙注預測 (最佳組合: Statistical + Frequency)
"""
import sys
import os

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery-api'))

from lottery_api.database import DatabaseManager
from lottery_api.common import get_lottery_rules
from lottery_api.models.unified_predictor import UnifiedPredictionEngine

def main():
    print("=" * 80)
    print("威力彩 115000005 期雙注預測")
    print("策略: Statistical + Frequency (10.00% 驗證勝率)")
    print("=" * 80)
    
    # 初始化
    db = DatabaseManager()
    history = db.get_all_draws(lottery_type='POWER_LOTTO')
    rules = get_lottery_rules('POWER_LOTTO')
    engine = UnifiedPredictionEngine()
    
    if not history:
        print("❌ 無法獲取歷史數據")
        return
    
    # 上期開獎
    last_draw = history[0]
    print(f"\n📅 上期開獎 ({last_draw.get('draw', 'N/A')}):")
    last_nums = sorted(last_draw.get('numbers', []))
    last_special = last_draw.get('special', last_draw.get('special_number'))
    print(f"   一區: {', '.join([f'{n:02d}' for n in last_nums])}")
    print(f"   二區: {last_special:02d}" if last_special else "   二區: N/A")
    
    print("\n" + "-" * 80)
    print("📊 雙注預測號碼:")
    print("-" * 80)
    
    # Bet 1: Statistical
    try:
        result1 = engine.statistical_predict(history, rules)
        bet1_nums = sorted(result1.get('numbers', [])[:6])
        bet1_special = result1.get('special_number', result1.get('special', 6))
        
        print(f"\n注1 (Statistical - 統計綜合):")
        print(f"   一區: {', '.join([f'{n:02d}' for n in bet1_nums])}")
        print(f"   二區: {bet1_special:02d}")
    except Exception as e:
        print(f"\n注1 預測失敗: {e}")
        bet1_nums = []
    
    # Bet 2: Frequency
    try:
        result2 = engine.frequency_predict(history, rules)
        bet2_nums = sorted(result2.get('numbers', [])[:6])
        bet2_special = result2.get('special_number', result2.get('special', 6))
        
        print(f"\n注2 (Frequency - 頻率分析):")
        print(f"   一區: {', '.join([f'{n:02d}' for n in bet2_nums])}")
        print(f"   二區: {bet2_special:02d}")
    except Exception as e:
        print(f"\n注2 預測失敗: {e}")
        bet2_nums = []
    
    # 分析
    if bet1_nums and bet2_nums:
        overlap = set(bet1_nums) & set(bet2_nums)
        coverage = set(bet1_nums) | set(bet2_nums)
        
        print("\n" + "-" * 80)
        print("📈 預測分析:")
        print("-" * 80)
        print(f"   重疊號碼 ({len(overlap)}): {sorted(list(overlap)) if overlap else '無'}")
        print(f"   總覆蓋數: {len(coverage)} 個號碼")
        print(f"   覆蓋率: {len(coverage)/38*100:.1f}% (38個號碼)")
        
    print("\n" + "-" * 80)
    print("📚 策略說明:")
    print("-" * 80)
    print("   ✅ 經 150 期回測驗證，勝率 10.00%")
    print("   ✅ 效益 5.00%/注 (所有組合中最高)")
    print("   ✅ Statistical: 綜合統計指標，穩健型")
    print("   ✅ Frequency: 頻率趨勢分析，捕捉熱號")
    print("=" * 80)

if __name__ == '__main__':
    main()
