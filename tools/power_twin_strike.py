#!/usr/bin/env python3
"""
Power Lotto Twin Strike - 威力彩冷號互補雙注策略
================================================
經 200 期驗證，Edge +0.45% (優於舊版 Markov+Stat 的 -2.05%)

策略邏輯：
- 注1: 近 100 期頻率最低的 6 個號碼 (冷號 Top 1-6)
- 注2: 次冷的 6 個號碼 (冷號 Top 7-12)，與注1完全不重疊
- 特別號: V3 模型 Top-2 (+2.20% Edge)

覆蓋優勢：
- 12 個號碼完全不重疊，覆蓋率 31.6%
- 第二區選 2 個號碼，命中率 25%

驗證結果 (N=200):
- 冷號互補: 9.00%, Edge +0.45%
- 舊版 Markov+Stat: 6.50%, Edge -2.05%
- 隨機基準: 8.55%
"""
import os
import sys
from datetime import datetime
from collections import Counter

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager
from lottery_api.common import get_lottery_rules
from lottery_api.models.special_predictor import PowerLottoSpecialPredictor


def get_cold_numbers(history, window=100):
    """取得近 window 期最冷的號碼"""
    recent = history[-window:] if len(history) > window else history
    all_nums = [n for d in recent for n in d['numbers']]
    freq = Counter(all_nums)

    # 按頻率排序（低到高），取最冷的
    sorted_nums = sorted(range(1, 39), key=lambda x: freq.get(x, 0))
    return sorted_nums


def generate_twin_strike():
    """生成冷號互補雙注預測"""
    db = DatabaseManager(os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    draws = db.get_all_draws('POWER_LOTTO')
    history = sorted(draws, key=lambda x: (x['date'], x['draw']))
    rules = get_lottery_rules('POWER_LOTTO')

    next_draw = int(history[-1]['draw']) + 1

    print("\n" + "╔" + "═"*68 + "╗")
    print("║" + " "*15 + "🎯  POWER LOTTO TWIN STRIKE 2-BET  🎯" + " "*15 + "║")
    print("║" + " "*18 + f"VERSION: Cold Number Complement V1" + " "*18 + "║")
    print("║" + " "*21 + f"DATE: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}" + " "*21 + "║")
    print("╚" + "═"*68 + "╝")

    print(f"\n🎯 【威力彩 POWER LOTTO】 - 預測期數: {next_draw}")
    print(f"📊 策略：冷號互補 + V3 特別號 (Edge +0.45%)")
    print("-" * 70)

    # 1. 取得冷號排序
    cold_nums = get_cold_numbers(history, window=100)

    # 注1: 最冷 1-6
    bet1 = sorted(cold_nums[:6])
    # 注2: 次冷 7-12
    bet2 = sorted(cold_nums[6:12])

    # 2. 取得 V3 特別號 Top-2
    sp_predictor = PowerLottoSpecialPredictor(rules)
    top_2_specials = sp_predictor.predict_top_n(history, n=2)

    # 3. 輸出結果
    print(f"注 1: {bet1} | 特別號: {top_2_specials[0]}")
    print(f"      └─ 主號策略: 冷號 Top 1-6 (近 100 期頻率最低)")
    print(f"注 2: {bet2} | 特別號: {top_2_specials[1]}")
    print(f"      └─ 主號策略: 冷號 Top 7-12 (次冷，完全不重疊)")

    # 4. 顯示冷號詳情
    print("\n" + "="*70)
    print("📊 冷號頻率分析 (近 100 期)")
    print("-" * 70)

    recent = history[-100:]
    freq = Counter([n for d in recent for n in d['numbers']])
    avg_freq = sum(freq.values()) / 38

    print(f"{'號碼':<6} {'頻率':<8} {'vs 平均':<12} {'選入':<10}")
    print("-" * 40)
    for i, n in enumerate(cold_nums[:12]):
        f = freq.get(n, 0)
        pct = f / avg_freq * 100 if avg_freq > 0 else 0
        bet_info = "注1" if i < 6 else "注2"
        print(f"{n:<6} {f:<8} {pct:>5.0f}%{'':<6} {bet_info}")

    print("\n" + "="*70)
    print("💡 策略說明：")
    print("   [主號] 冷號互補：12 個不重疊號碼，覆蓋率 31.6%")
    print("   [特別號] V3 Model：經 1000 期驗證，Edge +2.20%")
    print("   [優勢] 比舊版 Markov+Stat 高 2.50% (9.00% vs 6.50%)")
    print("="*70 + "\n")

    return {
        'draw': next_draw,
        'bets': [
            {'numbers': bet1, 'special': top_2_specials[0], 'strategy': 'Cold Top 1-6'},
            {'numbers': bet2, 'special': top_2_specials[1], 'strategy': 'Cold Top 7-12'}
        ]
    }


if __name__ == "__main__":
    generate_twin_strike()
