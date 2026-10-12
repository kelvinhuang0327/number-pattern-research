#!/usr/bin/env python3
"""
驗證 Gemini GUM (Grand Unified Model) 的 9.33% 聲稱
======================================================
使用標準回測邏輯，與 backtest_150_power.py 完全一致
"""
import os
import sys
import numpy as np
from collections import Counter

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules
from models.unified_predictor import UnifiedPredictionEngine
from models.special_predictor import PowerLottoSpecialPredictor

# 固定種子確保可復現
np.random.seed(42)

# 基準值
BASELINE_1BET = 3.87  # 威力彩單注 M3+ 隨機基準
BASELINE_2BET = 8.55  # 威力彩 2注 M3+ 隨機基準 (實測)

def calc_prize(match_count, special_hit):
    """威力彩獎項判定"""
    if match_count == 6 and special_hit: return '頭獎', 1
    elif match_count == 6: return '貳獎', 2
    elif match_count == 5 and special_hit: return '參獎', 3
    elif match_count == 5: return '肆獎', 4
    elif match_count == 4 and special_hit: return '伍獎', 5
    elif match_count == 4: return '陸獎', 6
    elif match_count == 3 and special_hit: return '柒獎', 7
    elif match_count == 2 and special_hit: return '捌獎', 8
    elif match_count == 3: return '玖獎', 9
    elif match_count == 1 and special_hit: return '普獎', 10
    return None, 0


def gum_predict_2bets(history, rules, window=50):
    """
    GUM (Grand Unified Model) 2注預測
    結合 Markov + Cluster + Cold 的加權評分

    這是根據 predict_consensus_ensemble.py 的邏輯重現
    """
    engine = UnifiedPredictionEngine()
    max_num = 38
    scores = np.zeros(max_num + 1)

    # Component 1: Markov (權重 3)
    try:
        recent = history[-window:]
        markov_res = engine.markov_predict(recent, rules)
        if 'numbers' in markov_res:
            for n in markov_res['numbers'][:12]:
                scores[n] += 3.0 / 6
    except:
        pass

    # Component 2: Cold Numbers (權重 2)
    recent = history[-window:]
    all_nums = [n for d in recent for n in d['numbers']]
    freq = Counter(all_nums)
    cold_nums = sorted(range(1, max_num + 1), key=lambda x: freq.get(x, 0))[:12]
    for n in cold_nums:
        scores[n] += 2.0 / 6

    # Component 3: Cluster/Zone Balance (權重 3)
    try:
        zone_res = engine.zone_balance_predict(recent, rules)
        if 'numbers' in zone_res:
            for n in zone_res['numbers'][:12]:
                scores[n] += 3.0 / 6
    except:
        pass

    # 排序選號
    all_indices = np.arange(1, max_num + 1)
    sorted_indices = all_indices[np.argsort(scores[1:])[::-1]]

    # 生成 2 注，每注 6 個號碼
    bet1 = sorted(sorted_indices[:6].tolist())
    bet2 = sorted(sorted_indices[6:12].tolist())

    return [bet1, bet2]


def cold_number_predict_2bets(history, window=50):
    """
    冷號互補策略（對照組）
    """
    recent = history[-window:]
    all_nums = [n for d in recent for n in d['numbers']]
    freq = Counter(all_nums)
    sorted_cold = sorted(range(1, 39), key=lambda x: freq.get(x, 0))

    bet1 = sorted(sorted_cold[:6])
    bet2 = sorted(sorted_cold[6:12])
    return [bet1, bet2]


def backtest_2bet_strategy(strategy_name, predict_func, test_periods=150, window=50):
    """
    標準 2 注回測邏輯
    """
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = list(reversed(db.get_all_draws(lottery_type='POWER_LOTTO')))
    rules = get_lottery_rules('POWER_LOTTO')
    sp_predictor = PowerLottoSpecialPredictor(rules)

    test_periods = min(test_periods, len(all_draws) - 50)

    m3_plus = 0
    total = 0
    match_dist = Counter()

    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        if target_idx <= window:
            continue

        # 數據切片：只能看過去
        target_draw = all_draws[target_idx]
        hist = all_draws[:target_idx]

        actual = set(target_draw['numbers'])
        actual_special = target_draw.get('special')

        # 預測
        try:
            bets = predict_func(hist, rules, window) if 'gum' in strategy_name.lower() else predict_func(hist, window)
            specials = sp_predictor.predict_top_n(hist, n=2)
        except Exception as e:
            continue

        # 評估每注
        best_match = 0
        for idx, bet in enumerate(bets):
            predicted = set(bet)
            match = len(predicted & actual)
            best_match = max(best_match, match)

        match_dist[best_match] += 1
        if best_match >= 3:
            m3_plus += 1
        total += 1

    if total == 0:
        return None

    m3_rate = m3_plus / total * 100
    return {
        'strategy': strategy_name,
        'window': window,
        'm3_rate': m3_rate,
        'm3_plus': m3_plus,
        'total': total,
        'match_dist': dict(match_dist)
    }


def main():
    print("=" * 70)
    print("🔬 驗證 Gemini GUM 9.33% 聲稱")
    print("=" * 70)
    print(f"測試條件：150 期回測，seed=42")
    print(f"基準：2注 M3+ 隨機 = {BASELINE_2BET}%")
    print("-" * 70)

    # 測試不同窗口的 GUM
    print("\n📊 GUM 策略不同窗口回測：")
    print("-" * 50)

    results = []
    rules = get_lottery_rules('POWER_LOTTO')

    for window in [20, 50, 100, 150, 200]:
        result = backtest_2bet_strategy(
            f"GUM_W{window}",
            gum_predict_2bets,
            test_periods=150,
            window=window
        )
        if result:
            edge = result['m3_rate'] - BASELINE_2BET
            results.append(result)
            status = "✅" if edge > 0 else "❌"
            print(f"Window {window:3}: M3+ = {result['m3_rate']:.2f}% | Edge = {edge:+.2f}% {status}")

    # 對照組：純冷號
    print("\n📊 對照組（冷號互補）：")
    print("-" * 50)

    for window in [50, 100]:
        result = backtest_2bet_strategy(
            f"Cold_W{window}",
            cold_number_predict_2bets,
            test_periods=150,
            window=window
        )
        if result:
            edge = result['m3_rate'] - BASELINE_2BET
            status = "✅" if edge > 0 else "❌"
            print(f"Window {window:3}: M3+ = {result['m3_rate']:.2f}% | Edge = {edge:+.2f}% {status}")

    # 總結
    print("\n" + "=" * 70)
    print("📋 結論")
    print("=" * 70)

    best = max(results, key=lambda x: x['m3_rate']) if results else None
    if best:
        best_edge = best['m3_rate'] - BASELINE_2BET
        print(f"\n最佳 GUM 配置: Window {best['window']}")
        print(f"實測 M3+: {best['m3_rate']:.2f}%")
        print(f"Edge vs Random: {best_edge:+.2f}%")
        print(f"\nGemini 聲稱: 9.33% (Window 50)")

        claimed_edge = 9.33 - BASELINE_2BET
        actual_edge = best['m3_rate'] - BASELINE_2BET

        if best['m3_rate'] >= 9.0:
            print(f"\n✅ 聲稱基本屬實")
        elif best['m3_rate'] >= 8.55:
            print(f"\n⚠️ 聲稱部分屬實（與隨機相當）")
        else:
            print(f"\n❌ 聲稱誇大（比隨機還差）")

    print("=" * 70)


if __name__ == "__main__":
    main()
