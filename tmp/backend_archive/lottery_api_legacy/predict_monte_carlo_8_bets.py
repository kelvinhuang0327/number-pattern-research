#!/usr/bin/env python3
"""
蒙地卡羅 8注預測
基於最新歷史數據生成8組預測號碼
"""
import sys
import os

sys.path.insert(0, os.getcwd())

from database import db_manager
from models.unified_predictor import prediction_engine
from common import get_lottery_rules


def predict_monte_carlo_8_bets(lottery_type='BIG_LOTTO'):
    """使用蒙地卡羅方法生成8注預測號碼"""

    print("=" * 80)
    print(f"🎲 蒙地卡羅 8注預測 - {lottery_type}")
    print("=" * 80)

    # 載入歷史數據
    history = db_manager.get_all_draws(lottery_type)
    history.sort(key=lambda x: x['date'], reverse=True)

    rules = get_lottery_rules(lottery_type)

    print(f"\n📚 使用歷史數據: {len(history)} 期")
    print(f"📅 最新一期: {history[0]['date']} 第{history[0]['draw']}期")
    print(f"   開獎號碼: {', '.join([f'{n:02d}' for n in sorted(history[0]['numbers'])])} + 特別號 {history[0]['special']:02d}")

    # 使用最近300期數據
    recent_history = history[:300]

    print(f"\n🎯 蒙地卡羅模擬生成8注號碼...")
    print("-" * 80)

    # 生成8注號碼（每次蒙地卡羅都會有不同的隨機結果）
    bets = []

    for i in range(8):
        try:
            result = prediction_engine.monte_carlo_predict(recent_history, rules)
            numbers = sorted(result['numbers'])
            special = result.get('special')

            bets.append({
                'numbers': numbers,
                'special': special
            })

            nums_str = ", ".join(f"{n:02d}" for n in numbers)
            special_str = f" [特別號預測: {special:02d}]" if special else ""
            print(f"第{i+1}注: [{nums_str}]{special_str}")

        except Exception as e:
            print(f"第{i+1}注: 生成失敗 - {e}")

    # 號碼頻率統計
    print("\n" + "=" * 80)
    print("📊 8注號碼出現頻率分析")
    print("=" * 80)

    from collections import Counter

    all_numbers = []
    for bet in bets:
        all_numbers.extend(bet['numbers'])

    number_freq = Counter(all_numbers)

    # 按頻率排序
    sorted_freq = sorted(number_freq.items(), key=lambda x: (-x[1], x[0]))

    print(f"\n出現最多的號碼 (Top 10):")
    for num, count in sorted_freq[:10]:
        percentage = (count / 8) * 100
        bar = "█" * count + "░" * (8 - count)
        print(f"   {num:02d}: {bar} {count}/8注 ({percentage:.0f}%)")

    # 號碼區間分布
    print(f"\n號碼區間分布:")
    ranges = {
        '01-10': len([n for n in all_numbers if 1 <= n <= 10]),
        '11-20': len([n for n in all_numbers if 11 <= n <= 20]),
        '21-30': len([n for n in all_numbers if 21 <= n <= 30]),
        '31-40': len([n for n in all_numbers if 31 <= n <= 40]),
        '41-49': len([n for n in all_numbers if 41 <= n <= 49]),
    }

    for range_name, count in ranges.items():
        percentage = (count / len(all_numbers)) * 100
        print(f"   {range_name}: {count:2d}個 ({percentage:5.1f}%)")

    # 奇偶分析
    odd_count = len([n for n in all_numbers if n % 2 == 1])
    even_count = len([n for n in all_numbers if n % 2 == 0])

    print(f"\n奇偶分析:")
    print(f"   奇數: {odd_count}個 ({odd_count/len(all_numbers)*100:.1f}%)")
    print(f"   偶數: {even_count}個 ({even_count/len(all_numbers)*100:.1f}%)")

    # 建議組合
    print("\n" + "=" * 80)
    print("💡 蒙地卡羅策略建議")
    print("=" * 80)

    # 找出高頻號碼
    high_freq = [num for num, count in sorted_freq if count >= 3]
    medium_freq = [num for num, count in sorted_freq if count == 2]

    print(f"\n🔥 高頻號碼 (出現≥3次): {', '.join([f'{n:02d}' for n in high_freq])}")
    print(f"⚡ 中頻號碼 (出現2次): {', '.join([f'{n:02d}' for n in medium_freq])}")

    # 推薦組合
    if len(high_freq) >= 3:
        print(f"\n✨ 建議優先考慮包含高頻號碼的組合")
        print(f"   例如：從以上高頻號碼中選擇3-4個，搭配其他號碼")

    print("\n" + "=" * 80)
    print("📝 蒙地卡羅方法說明")
    print("=" * 80)
    print("""
蒙地卡羅模擬：
- 基於機率分布進行多次隨機模擬
- 每次預測都是獨立的隨機過程
- 適合捕捉號碼的隨機性和不確定性
- 在2025年回測中中獎率: 1.90% (排名第8)
- 最佳獎項: 柒獎 (2個主號碼 + 特別號)
    """)

    print("=" * 80)
    print("✅ 預測完成！祝您好運！")
    print("=" * 80)

    return bets


if __name__ == '__main__':
    predict_monte_carlo_8_bets('BIG_LOTTO')
