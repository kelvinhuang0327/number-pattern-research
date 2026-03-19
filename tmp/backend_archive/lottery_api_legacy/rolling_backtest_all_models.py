#!/usr/bin/env python3
"""
滾動式回測 - 所有預測模型 (2025年)
使用unified_predictor中的所有預測方法進行8注預測回測
"""
import sys
import os
from collections import defaultdict, Counter
import logging

# Add current directory to path
sys.path.insert(0, os.getcwd())

from database import db_manager
from models.unified_predictor import prediction_engine
from models.optimized_ensemble import create_optimized_ensemble_predictor
from common import get_lottery_rules

# Configure logging
logging.basicConfig(level=logging.WARNING, format='%(message)s')
logger = logging.getLogger(__name__)


def calculate_match_prize(predicted, actual, actual_special):
    """
    計算大樂透中獎等級

    Args:
        predicted: 預測的6個主號碼
        actual: 實際開獎的6個主號碼
        actual_special: 實際開獎的特別號

    Returns:
        (match_count, has_special, is_win, prize_name, prize_level)
    """
    pred_set = set(predicted)
    actual_set = set(actual)

    match_count = len(pred_set.intersection(actual_set))
    has_special = actual_special in pred_set

    # 大樂透獎項規則
    prize_map = {
        (6, False): ("頭獎", 1, True),
        (5, True): ("貳獎", 2, True),
        (5, False): ("參獎", 3, True),
        (4, True): ("肆獎", 4, True),
        (4, False): ("伍獎", 5, True),
        (3, True): ("陸獎", 6, True),
        (2, True): ("柒獎", 7, True),
        (3, False): ("普獎", 8, True),
    }

    key = (match_count, has_special)
    if key in prize_map:
        prize_name, prize_level, is_win = prize_map[key]
        return match_count, has_special, is_win, prize_name, prize_level

    return match_count, has_special, False, "未中獎", 0


class RollingBacktester:
    def __init__(self, lottery_type='BIG_LOTTO'):
        self.lottery_type = lottery_type
        self.rules = get_lottery_rules(lottery_type)

        # 所有可用的預測方法
        self.models = [
            ('Frequency', prediction_engine.frequency_predict),
            ('Trend', prediction_engine.trend_predict),
            ('Bayesian', prediction_engine.bayesian_predict),
            ('Deviation', prediction_engine.deviation_predict),
            ('Monte Carlo', prediction_engine.monte_carlo_predict),
            ('Markov', prediction_engine.markov_predict),
            ('Hot-Cold Mix', prediction_engine.hot_cold_mix_predict),
            ('Statistical', prediction_engine.statistical_predict),
            ('Odd-Even Balance', prediction_engine.odd_even_balance_predict),
            ('Zone Balance', prediction_engine.zone_balance_predict),
            ('Sum Range', prediction_engine.sum_range_predict),
            ('Number Pairs', prediction_engine.number_pairs_predict),
            ('Pattern Recognition', prediction_engine.pattern_recognition_predict),
            ('Cycle Analysis', prediction_engine.cycle_analysis_predict),
            ('Wheeling', prediction_engine.wheeling_predict),
            ('Random Forest', prediction_engine.random_forest_predict),
            ('Ensemble', prediction_engine.ensemble_predict),
        ]

        # 統計結構
        self.stats = defaultdict(lambda: {
            'draws': 0,
            'wins': 0,
            'total_matches': 0,
            'max_match': 0,
            'best_prize_level': 0,
            'best_prize_name': '',
            'prize_counts': Counter(),
            'win_details': []
        })

    def run(self):
        print("=" * 100)
        print(f"🚀 滾動式回測 2025: {self.lottery_type}")
        print("=" * 100)

        # 1. 載入所有數據
        all_draws = db_manager.get_all_draws(self.lottery_type)
        all_draws.sort(key=lambda x: x['date'])

        # 2. 分割訓練集與測試集
        train_data = []
        test_data = []

        for draw in all_draws:
            d_date = draw['date']
            if d_date.startswith('2025'):
                test_data.append(draw)
            else:
                train_data.append(draw)

        print(f"📚 訓練數據: {len(train_data)} 期 (2025年之前)")
        print(f"🧪 測試數據: {len(test_data)} 期 (2025年)")
        print("-" * 100)

        if len(test_data) == 0:
            print("❌ 沒有2025年的數據可供測試")
            return None

        # 3. 滾動式回測
        print("\n🎯 開始滾動式回測...")

        for i, target_draw in enumerate(test_data):
            # 當前可用的歷史數據
            history_pool = train_data + test_data[:i]
            history_pool.sort(key=lambda x: x['date'], reverse=True)

            actual_nums = set(target_draw['numbers'])
            actual_special = int(target_draw['special']) if target_draw.get('special') else -1

            # 對每個模型進行預測並評估
            for name, method in self.models:
                try:
                    res = method(history_pool, self.rules)
                    predicted = sorted(res['numbers'])

                    m_cnt, h_sp, won, prize_name, prize_level = calculate_match_prize(
                        predicted, actual_nums, actual_special
                    )

                    self._update_stats(
                        name, m_cnt, won, prize_name, prize_level,
                        target_draw, predicted, h_sp
                    )

                except Exception as e:
                    # 預測失敗，跳過
                    logger.debug(f"{name} prediction failed: {str(e)}")
                    pass

            if (i + 1) % 10 == 0:
                print(f"   進度: {i+1}/{len(test_data)} 期...")

        print(f"✅ 回測完成！共測試 {len(test_data)} 期\n")

        # 4. 輸出結果
        self._print_results(all_draws, len(test_data))

        return self.stats, len(test_data)

    def _update_stats(self, name, match_count, is_win, prize_name, prize_level,
                      target_draw, predicted, has_special):
        """更新統計數據"""
        s = self.stats[name]
        s['draws'] += 1
        s['total_matches'] += match_count

        if is_win:
            s['wins'] += 1
            s['prize_counts'][prize_name] += 1

            # 更新最佳獎項（level越小越好）
            if s['best_prize_level'] == 0 or prize_level < s['best_prize_level']:
                s['best_prize_level'] = prize_level
                s['best_prize_name'] = prize_name

            # 記錄前10筆中獎詳情
            if len(s['win_details']) < 10:
                s['win_details'].append({
                    'draw': target_draw['draw'],
                    'date': target_draw['date'],
                    'prize_name': prize_name,
                    'match_count': match_count,
                    'has_special': has_special,
                    'predicted': predicted
                })

        if match_count > s['max_match']:
            s['max_match'] = match_count

    def _print_results(self, full_history, total_periods):
        """輸出回測結果與最新8注預測"""
        full_history.sort(key=lambda x: x['date'], reverse=True)

        # 按中獎次數、最佳獎項、平均命中排序
        ranked = sorted(
            self.stats.items(),
            key=lambda x: (
                -x[1]['wins'],  # 中獎次數越多越好
                x[1]['best_prize_level'] if x[1]['best_prize_level'] > 0 else 999,  # 獎項等級越小越好
                -x[1]['total_matches']  # 總命中數越多越好
            )
        )

        # 輸出排名表
        print("\n" + "=" * 100)
        print("🏆 2025 滾動式回測結果")
        print("=" * 100)
        print(f"{'排名':<5} {'模型':<25} {'中獎次數':<10} {'中獎率':<10} {'最佳獎項':<12} {'平均命中':<10} {'總命中'}")
        print("-" * 100)

        for i, (name, s) in enumerate(ranked, 1):
            if s['draws'] == 0:
                continue

            win_rate = s['wins'] / s['draws']
            avg_match = s['total_matches'] / s['draws']
            best_prize = s['best_prize_name'] if s['best_prize_name'] else "未中獎"

            rank_emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i} "

            print(f"{rank_emoji:<5} {name:<25} {s['wins']:<10} {win_rate:>6.1%}    {best_prize:<12} {avg_match:>6.2f}     {s['total_matches']}")

        # Top 5 詳細分析
        print("\n" + "=" * 100)
        print("🏆 前5名模型詳細分析")
        print("=" * 100)

        top_5 = ranked[:5]

        for rank, (name, s) in enumerate(top_5, 1):
            rank_emoji = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else "🏅"
            print(f"\n{rank_emoji} 第{rank}名: {name}")
            print(f"   總測試期數: {s['draws']} 期")
            print(f"   中獎次數: {s['wins']} 次")
            print(f"   中獎率: {s['wins'] / s['draws'] * 100:.2f}%")
            print(f"   最佳獎項: {s['best_prize_name']}")
            print(f"   平均命中: {s['total_matches'] / s['draws']:.2f} 個/期")
            print(f"   總命中數: {s['total_matches']}")

            if s['prize_counts']:
                prize_dist = ", ".join([f"{pname}×{count}" for pname, count in s['prize_counts'].most_common()])
                print(f"   獎項分布: {prize_dist}")

            if s['win_details']:
                print(f"   前10筆中獎記錄:")
                for detail in s['win_details']:
                    special_mark = "✅特別號" if detail['has_special'] else ""
                    pred_str = ', '.join([f'{n:02d}' for n in detail['predicted']])
                    print(f"      • {detail['date']} 第{detail['draw']}期: {detail['prize_name']} - 主{detail['match_count']}個 {special_mark}")
                    print(f"        預測號碼: [{pred_str}]")

        # 最新8注預測
        print("\n" + "=" * 100)
        print("🔮 最新8注預測（用於下一期開獎）")
        print("=" * 100)
        print("📊 使用前8名模型的最新預測...\n")

        print(f"{'排名':<5} {'模型':<25} {'預測號碼'}")
        print("-" * 100)

        for rank, (name, s) in enumerate(ranked[:8], 1):
            rank_emoji = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else f"{rank}."

            try:
                # 找到對應的預測方法
                method = next((m for n, m in self.models if n == name), None)
                if method:
                    res = method(full_history, self.rules)
                    predicted = sorted(res['numbers'])
                    nums_str = ', '.join([f'{n:02d}' for n in predicted])
                    print(f"{rank_emoji:<5} {name:<25} [{nums_str}]")
            except Exception as e:
                print(f"{rank_emoji:<5} {name:<25} 預測失敗")

        # 整體統計摘要
        print("\n" + "=" * 100)
        print("📈 整體統計摘要")
        print("=" * 100)

        total_wins = sum(s['wins'] for s in self.stats.values())
        total_tests = sum(s['draws'] for s in self.stats.values())
        overall_win_rate = (total_wins / total_tests * 100) if total_tests > 0 else 0

        print(f"   測試期數: {total_periods} 期")
        print(f"   測試模型: {len(self.models)} 個")
        print(f"   總測試次數: {total_tests} 次")
        print(f"   總中獎次數: {total_wins} 次")
        print(f"   整體中獎率: {overall_win_rate:.2f}%")

        # 所有獎項統計
        all_prizes = Counter()
        for s in self.stats.values():
            all_prizes.update(s['prize_counts'])

        if all_prizes:
            print(f"\n   所有獎項分布:")
            for prize_name, count in all_prizes.most_common():
                print(f"      • {prize_name}: {count} 次")

        print("\n" + "=" * 100)
        print("✅ 滾動式回測分析完成！")
        print("=" * 100)


if __name__ == '__main__':
    tester = RollingBacktester('BIG_LOTTO')
    tester.run()
