#!/usr/bin/env python3
"""
Elite-7 策略嚴格驗證
- 測試更長期間 (300 期)
- 計算真正的隨機 7 注基準 (模擬)
- 檢查穩定性 (前半 vs 後半)
"""
import sys
import os
import io
import random
from collections import Counter
import numpy as np

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from lottery_api.database import DatabaseManager
from lottery_api.common import get_lottery_rules
from lottery_api.models.unified_predictor import UnifiedPredictionEngine

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

SEED = 42
random.seed(SEED)
np.random.seed(SEED)

def calculate_random_baseline(all_draws, test_periods, num_bets=7, simulations=1000):
    """計算真正的隨機 7 注基準 (蒙特卡洛模擬)"""
    total_wins = 0
    total_tests = 0

    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        if target_idx <= 0:
            continue

        target_draw = all_draws[target_idx]
        actual = set(target_draw['numbers'])

        # 模擬多次隨機 7 注
        sim_wins = 0
        for _ in range(simulations):
            period_win = False
            for _ in range(num_bets):
                random_bet = set(random.sample(range(1, 50), 6))
                if len(random_bet & actual) >= 3:
                    period_win = True
                    break
            if period_win:
                sim_wins += 1

        total_wins += sim_wins
        total_tests += simulations

    return total_wins / total_tests * 100


def backtest_elite7(all_draws, rules, test_periods):
    """Elite-7 策略回測"""
    engine = UnifiedPredictionEngine()

    portfolio_config = [
        ('1. Markov (W50)', 'markov_predict', 50),
        ('2. Markov (W100)', 'markov_predict', 100),
        ('3. Deviation (W100)', 'deviation_predict', 100),
        ('4. Deviation (W200)', 'deviation_predict', 200),
        ('5. Statistical (W100)', 'statistical_predict', 100),
        ('6. Statistical (W110)', 'statistical_predict', 110),
    ]

    match3_count = 0
    total = 0

    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        if target_idx <= 0:
            continue

        target_draw = all_draws[target_idx]
        actual = set(target_draw['numbers'])

        # Generate 6 Base Bets
        bets = []
        all_predicted_numbers = []

        for name, method_name, window in portfolio_config:
            start_hist = max(0, target_idx - window)
            hist = all_draws[start_hist:target_idx]
            try:
                res = getattr(engine, method_name)(hist, rules)
                nums = res['numbers'][:6]
                bets.append(set(nums))
                all_predicted_numbers.extend(nums)
            except:
                pass

        # 7th Bet: Consensus
        if all_predicted_numbers:
            common = Counter(all_predicted_numbers).most_common(6)
            consensus_nums = [n for n, _ in common]
            bets.append(set(consensus_nums))

        # Check Match-3+
        period_match3 = False
        for nums in bets:
            if len(nums & actual) >= 3:
                period_match3 = True
                break

        if period_match3:
            match3_count += 1
        total += 1

    return match3_count, total


def main():
    print("=" * 70)
    print("🔬 Elite-7 策略嚴格驗證 (Claude 獨立審計)")
    print("=" * 70)

    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = list(reversed(db.get_all_draws(lottery_type='BIG_LOTTO')))
    rules = get_lottery_rules('BIG_LOTTO')

    print(f"數據總期數: {len(all_draws)}")

    # 測試配置
    test_configs = [
        ('150 期 (Gemini 原測)', 150),
        ('200 期', 200),
        ('300 期', 300),
    ]

    results = []

    for name, periods in test_configs:
        if periods > len(all_draws) - 50:
            print(f"⚠️ {name}: 數據不足，跳過")
            continue

        print(f"\n{'='*70}")
        print(f"📊 測試期間: {name}")
        print(f"{'='*70}")

        # Elite-7 回測
        match3, total = backtest_elite7(all_draws, rules, periods)
        elite7_rate = match3 / total * 100

        # 隨機基準 (簡化版：理論計算)
        # 大樂透 6/49，單注 Match-3+ 機率 ≈ 1.77%
        # 7 注獨立：1 - (1-0.0177)^7 ≈ 11.74%
        # 但由於有重疊，實際略低

        # 進行小規模蒙特卡洛驗證
        print("計算隨機基準 (蒙特卡洛模擬中)...")
        random_rate = calculate_random_baseline(all_draws, periods, num_bets=7, simulations=100)

        edge = elite7_rate - random_rate

        print(f"\n結果:")
        print(f"  Elite-7 勝率:  {elite7_rate:.2f}% ({match3}/{total})")
        print(f"  隨機 7注 基準: {random_rate:.2f}%")
        print(f"  Edge vs Random: {edge:+.2f}%")

        if edge > 2.0:
            verdict = "✅ 顯著優勢"
        elif edge > 0.5:
            verdict = "⚠️ 微弱優勢"
        elif edge > -0.5:
            verdict = "❌ 與隨機相當"
        else:
            verdict = "❌ 比隨機差"

        print(f"  結論: {verdict}")

        results.append({
            'name': name,
            'periods': periods,
            'elite7_rate': elite7_rate,
            'random_rate': random_rate,
            'edge': edge,
            'verdict': verdict
        })

    # 穩定性檢查 (前半 vs 後半)
    print(f"\n{'='*70}")
    print("📈 穩定性檢查 (150期: 前75期 vs 後75期)")
    print(f"{'='*70}")

    # 前 75 期
    first_half_match, first_half_total = backtest_elite7(all_draws, rules, 75)
    # 調整到使用最近 75-150 期
    all_draws_shifted = all_draws[:-75]  # 去掉最近 75 期
    second_half_match, second_half_total = backtest_elite7(all_draws_shifted, rules, 75)

    first_rate = first_half_match / first_half_total * 100 if first_half_total > 0 else 0
    second_rate = second_half_match / second_half_total * 100 if second_half_total > 0 else 0

    print(f"  後 75 期 (最近): {first_rate:.2f}%")
    print(f"  前 75 期 (較早): {second_rate:.2f}%")
    print(f"  差異: {abs(first_rate - second_rate):.2f}%")

    if abs(first_rate - second_rate) > 5:
        print("  ⚠️ 穩定性警告：前後期差異過大，可能過擬合")
    else:
        print("  ✅ 穩定性良好")

    # 最終總結
    print(f"\n{'='*70}")
    print("🎯 最終審計結論")
    print(f"{'='*70}")

    if len(results) > 0:
        avg_edge = sum(r['edge'] for r in results) / len(results)
        print(f"\n平均 Edge vs Random: {avg_edge:+.2f}%")

        if avg_edge > 2.0:
            print("\n✅ Gemini Elite-7 聲稱基本成立")
            print("   但建議繼續監控長期表現")
        elif avg_edge > 0.5:
            print("\n⚠️ Gemini Elite-7 有微弱優勢，但不如聲稱的 +3.70%")
        else:
            print("\n❌ Gemini Elite-7 聲稱無法復現")
            print("   實測與隨機相當或更差")


if __name__ == '__main__':
    main()
