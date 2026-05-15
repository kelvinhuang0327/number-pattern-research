#!/usr/bin/env python3
"""
Single Bet Backtest 2025 - Big Lotto
Evaluates prediction methods with SINGLE BET strategy (1 bet per draw)
Tests which method is best for predicting just 6 numbers directly.
"""
import sys
import os
import logging
from collections import defaultdict
import numpy as np

# Add current directory to path
sys.path.insert(0, os.getcwd())

from database import db_manager
from models.unified_predictor import prediction_engine
from common import get_lottery_rules

# Configure logging
logging.basicConfig(level=logging.WARNING, format='%(message)s')
logger = logging.getLogger(__name__)

def calculate_match_prize(predicted, actual, actual_special):
    """Calculate match metrics for Big Lotto"""
    pred_set = set(predicted)
    actual_set = set(actual)

    match_count = len(pred_set.intersection(actual_set))
    has_special = actual_special in pred_set

    # Win if Match >= 3 or 2+special
    is_win = (match_count >= 3) or (match_count == 2 and has_special)

    prize_name = ""
    if match_count == 6:
        prize_name = "頭獎 (6)"
    elif match_count == 5 and has_special:
        prize_name = "貳獎 (5+S)"
    elif match_count == 5:
        prize_name = "參獎 (5)"
    elif match_count == 4 and has_special:
        prize_name = "肆獎 (4+S)"
    elif match_count == 4:
        prize_name = "伍獎 (4)"
    elif match_count == 3 and has_special:
        prize_name = "陸獎 (3+S)"
    elif match_count == 2 and has_special:
        prize_name = "七獎 (2+S)"
    elif match_count == 3:
        prize_name = "普獎 (3)"

    return match_count, has_special, is_win, prize_name

class SingleBetBacktester:
    def __init__(self, lottery_type='BIG_LOTTO'):
        self.lottery_type = lottery_type
        self.original_rules = get_lottery_rules(lottery_type)
        self.stats = defaultdict(lambda: {
            'draws': 0,
            'wins': 0,
            'matches_accum': 0,
            'max_match': 0,
            'best_prize': '',
            'prize_counts': defaultdict(int),
            'match_distribution': defaultdict(int)  # Track 0,1,2,3,4,5,6 matches
        })

        self.models = [
            ('Frequency', prediction_engine.frequency_predict),
            ('Trend', prediction_engine.trend_predict),
            ('Bayesian', prediction_engine.bayesian_predict),
            ('Deviation', prediction_engine.deviation_predict),
            ('Monte Carlo', prediction_engine.monte_carlo_predict),
            ('Hot-Cold', getattr(prediction_engine, 'hot_cold_mix_predict', None)),
            ('Statistical', getattr(prediction_engine, 'statistical_predict', None)),
        ]
        self.models = [m for m in self.models if m[1] is not None]

    def run_backtest(self):
        """Run single bet backtest on 2025 data"""
        print("\n" + "="*80)
        print("🎯 單注策略回測 - 2025年大樂透")
        print("="*80)

        # Get all data
        all_draws = db_manager.get_all_draws(self.lottery_type)
        all_draws = sorted(all_draws, key=lambda x: x['date'])

        # Split: before 2025 for training, 2025 for testing
        train_draws = [d for d in all_draws if d['date'] < '2025-01-01']
        test_draws = [d for d in all_draws if d['date'] >= '2025-01-01']

        print(f"\n📊 數據集:")
        print(f"   訓練數據: {len(train_draws)} 期 (2025年以前)")
        print(f"   測試數據: {len(test_draws)} 期 (2025年)")
        print(f"\n策略: 每個方法每期預測 1 注（6個號碼）")
        print(f"      直接使用方法預測的前6個號碼\n")

        # Test each model
        for model_name, model_func in self.models:
            print(f"\n{'─'*60}")
            print(f"🔮 測試方法: {model_name}")
            print(f"{'─'*60}")

            history = train_draws.copy()

            for idx, draw in enumerate(test_draws, 1):
                actual_numbers = draw['numbers']
                actual_special = draw['special']

                # Predict 6 numbers directly
                try:
                    prediction = model_func(history, self.original_rules)
                    predicted_numbers = prediction['numbers'][:6]  # Take first 6

                    if len(predicted_numbers) < 6:
                        print(f"⚠️  期{idx}: 預測號碼不足6個，跳過")
                        continue

                    # Calculate match
                    match_count, has_special, is_win, prize_name = calculate_match_prize(
                        predicted_numbers, actual_numbers, actual_special
                    )

                    # Update stats
                    stats = self.stats[model_name]
                    stats['draws'] += 1
                    stats['matches_accum'] += match_count
                    stats['match_distribution'][match_count] += 1

                    if is_win:
                        stats['wins'] += 1
                        stats['prize_counts'][prize_name] += 1

                    if match_count > stats['max_match']:
                        stats['max_match'] = match_count
                        stats['best_prize'] = prize_name

                    # Progress indicator (every 20 draws)
                    if idx % 20 == 0:
                        win_rate = (stats['wins'] / stats['draws'] * 100) if stats['draws'] > 0 else 0
                        avg_match = stats['matches_accum'] / stats['draws'] if stats['draws'] > 0 else 0
                        print(f"   進度 {idx}/{len(test_draws)}: 中獎率={win_rate:.1f}%, 平均匹配={avg_match:.2f}")

                except Exception as e:
                    print(f"⚠️  期{idx}: 預測失敗 - {e}")
                    continue

                # Rolling update: add actual result to history
                history.append(draw)
                # Keep recent 300 draws
                if len(history) > 300:
                    history = history[-300:]

            # Final stats for this model
            stats = self.stats[model_name]
            if stats['draws'] > 0:
                win_rate = stats['wins'] / stats['draws'] * 100
                avg_match = stats['matches_accum'] / stats['draws']
                print(f"\n✅ {model_name} 完成:")
                print(f"   中獎次數: {stats['wins']}/{stats['draws']} ({win_rate:.2f}%)")
                print(f"   平均匹配: {avg_match:.2f} 個號碼")
                print(f"   最佳獎項: {stats['best_prize']}")

        # Print final report
        self._print_report(len(test_draws))

    def _print_report(self, total_draws):
        """Print comprehensive report"""
        print("\n" + "="*80)
        print("📊 單注策略回測報告 - 2025年")
        print("="*80)

        # Sort by win rate
        sorted_models = sorted(
            self.stats.items(),
            key=lambda x: x[1]['wins'] / x[1]['draws'] if x[1]['draws'] > 0 else 0,
            reverse=True
        )

        print(f"\n🏆 預測方法排名（按中獎率）\n")
        print(f"{'排名':<6} {'方法':<15} {'中獎次數':<12} {'中獎率':<10} {'平均匹配':<10} {'最佳獎項'}")
        print("─" * 80)

        for rank, (model_name, stats) in enumerate(sorted_models, 1):
            if stats['draws'] == 0:
                continue

            win_rate = stats['wins'] / stats['draws'] * 100
            avg_match = stats['matches_accum'] / stats['draws']

            medal = ""
            if rank == 1: medal = "🥇"
            elif rank == 2: medal = "🥈"
            elif rank == 3: medal = "🥉"
            else: medal = f"{rank}️⃣ "

            print(f"{medal:<6} {model_name:<15} {stats['wins']}/{stats['draws']:<8} "
                  f"{win_rate:>6.2f}%    {avg_match:>5.2f}      {stats['best_prize']}")

        print("\n" + "─" * 80)

        # Detailed analysis for top 3
        print(f"\n📈 Top 3 方法詳細分析\n")

        for rank, (model_name, stats) in enumerate(sorted_models[:3], 1):
            if stats['draws'] == 0:
                continue

            win_rate = stats['wins'] / stats['draws'] * 100
            avg_match = stats['matches_accum'] / stats['draws']

            print(f"\n{'🥇' if rank==1 else '🥈' if rank==2 else '🥉'} 第{rank}名: {model_name}")
            print(f"   中獎率: {win_rate:.2f}% ({stats['wins']}/{stats['draws']})")
            print(f"   平均匹配: {avg_match:.2f} 個號碼")
            print(f"   最佳獎項: {stats['best_prize']}")

            # Match distribution
            print(f"   匹配分布:")
            for i in range(7):
                count = stats['match_distribution'][i]
                pct = (count / stats['draws'] * 100) if stats['draws'] > 0 else 0
                bar = "█" * int(pct / 2)
                print(f"     {i}個: {count:>3}次 ({pct:>5.1f}%) {bar}")

            # Prize distribution
            if stats['prize_counts']:
                print(f"   獎項分布:")
                for prize, count in sorted(stats['prize_counts'].items(),
                                          key=lambda x: -x[1]):
                    print(f"     {prize}: {count}次")

        print("\n" + "="*80)
        print("💡 建議")
        print("="*80)

        if len(sorted_models) > 0:
            best_model, best_stats = sorted_models[0]
            best_win_rate = best_stats['wins'] / best_stats['draws'] * 100 if best_stats['draws'] > 0 else 0

            print(f"\n✅ 單注策略最佳方法: {best_model}")
            print(f"   ├─ 中獎率: {best_win_rate:.2f}%")
            print(f"   ├─ 平均每 {int(100/best_win_rate if best_win_rate > 0 else 999)} 期約中獎1次")
            print(f"   └─ 建議投注: 每期投注 1 注，成本控制在 50 元/期")

            if len(sorted_models) > 1:
                second_model, second_stats = sorted_models[1]
                second_win_rate = second_stats['wins'] / second_stats['draws'] * 100 if second_stats['draws'] > 0 else 0

                print(f"\n✅ 雙注策略建議組合: {best_model} + {second_model}")
                combined_win_estimate = best_win_rate + second_win_rate * 0.7  # Rough estimate
                print(f"   ├─ 預估組合中獎率: {combined_win_estimate:.2f}%")
                print(f"   ├─ 平均每 {int(100/combined_win_estimate if combined_win_estimate > 0 else 999)} 期約中獎1次")
                print(f"   └─ 建議投注: 每期投注 2 注，成本控制在 100 元/期")

        print(f"\n⚠️  提醒:")
        print(f"   • 單注策略中獎率較低，但成本控制最佳")
        print(f"   • 建議作為長期娛樂投注方式")
        print(f"   • 理性投注，量力而為")
        print("\n" + "="*80 + "\n")

if __name__ == "__main__":
    backtester = SingleBetBacktester()
    backtester.run_backtest()
