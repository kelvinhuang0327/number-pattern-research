#!/usr/bin/env python3
"""
2025年滾動式回測 - 8注號碼策略評估

邏輯：
1. 用2025年之前的數據訓練
2. 每個策略生成8注不同的預測號碼
3. 比對每期實際開獎號碼，計算這8注的命中情況
4. 將實際數據加入訓練集，預測下一期
5. 統計並排名最佳策略（Top 5）
"""
import sys
import os
import logging
from collections import defaultdict
from datetime import datetime
from itertools import combinations
import random

sys.path.insert(0, os.getcwd())

from database import db_manager
from models.unified_predictor import prediction_engine
from models.optimized_ensemble import OptimizedEnsemblePredictor
from models.entropy_transformer import EntropyTransformerModel
from models.anti_consensus_sampler import EntropyMaximizedSampler, AntiConsensusFilter
from common import get_lottery_rules
import numpy as np

logging.basicConfig(level=logging.WARNING, format='%(message)s')
logger = logging.getLogger(__name__)


class Fast8BetPredictor:
    """快速8注生成器 - 繞過昂貴的權重計算"""

    def __init__(self, engine):
        self.engine = engine

    def generate_8_bets(self, history, rules, strategy_name='mixed'):
        """
        根據不同策略生成8注號碼

        策略類型：
        - frequency: 頻率分析變化
        - trend: 趨勢分析變化
        - monte_carlo: 蒙地卡羅模擬
        - bayesian: 貝葉斯推斷
        - hot_cold: 冷熱號混合
        - ensemble: 集成學習
        - deviation: 偏差分析
        - statistical: 統計學習
        """
        bets = []

        try:
            if strategy_name == 'frequency':
                bets = self._frequency_8_bets(history, rules)
            elif strategy_name == 'trend':
                bets = self._trend_8_bets(history, rules)
            elif strategy_name == 'monte_carlo':
                bets = self._monte_carlo_8_bets(history, rules)
            elif strategy_name == 'bayesian':
                bets = self._bayesian_8_bets(history, rules)
            elif strategy_name == 'hot_cold':
                bets = self._hot_cold_8_bets(history, rules)
            elif strategy_name == 'ensemble':
                bets = self._ensemble_8_bets(history, rules)
            elif strategy_name == 'deviation':
                bets = self._deviation_8_bets(history, rules)
            elif strategy_name == 'statistical':
                bets = self._statistical_8_bets(history, rules)
            elif strategy_name == 'entropy_transformer':
                bets = self._entropy_8_bets(history, rules)
            else:
                # 默認混合策略
                bets = self._mixed_8_bets(history, rules)

        except Exception as e:
            logger.error(f"策略 {strategy_name} 生成失敗: {e}")
            # 失敗時生成隨機號碼
            bets = self._random_8_bets(rules)

        return bets

    def _frequency_8_bets(self, history, rules):
        """頻率分析：基於不同時間窗口的頻率"""
        bets = []
        windows = [10, 20, 30, 50, 100, 150, 200, 300]

        for window in windows[:8]:
            recent = history[:window] if len(history) >= window else history
            try:
                res = self.engine.frequency_predict(recent, rules)
                bets.append(sorted(res['numbers']))
            except:
                bets.append(self._random_bet(rules))

        return bets

    def _trend_8_bets(self, history, rules):
        """趨勢分析：不同趨勢權重組合"""
        bets = []

        # 趨勢策略變化（修改內部權重或抽樣）
        for i in range(8):
            try:
                res = self.engine.trend_predict(history[:200], rules)
                # 加入隨機變化
                nums = res['numbers']
                if i > 0:  # 第一注保持原樣
                    nums = self._vary_numbers(nums, rules, variation=i)
                bets.append(sorted(nums))
            except:
                bets.append(self._random_bet(rules))

        return bets

    def _monte_carlo_8_bets(self, history, rules):
        """蒙地卡羅：8次獨立模擬"""
        bets = []

        for _ in range(8):
            try:
                res = self.engine.monte_carlo_predict(history[:200], rules)
                bets.append(sorted(res['numbers']))
            except:
                bets.append(self._random_bet(rules))

        return bets

    def _bayesian_8_bets(self, history, rules):
        """貝葉斯：不同先驗假設"""
        bets = []

        for i in range(8):
            try:
                res = self.engine.bayesian_predict(history[:200], rules)
                nums = res['numbers']
                if i > 0:
                    nums = self._vary_numbers(nums, rules, variation=i)
                bets.append(sorted(nums))
            except:
                bets.append(self._random_bet(rules))

        return bets

    def _hot_cold_8_bets(self, history, rules):
        """冷熱號：不同冷熱比例"""
        bets = []

        for i in range(8):
            try:
                if hasattr(self.engine, 'hot_cold_mix_predict'):
                    res = self.engine.hot_cold_mix_predict(history[:200], rules)
                else:
                    res = self.engine.frequency_predict(history[:30], rules)

                nums = res['numbers']
                if i > 0:
                    nums = self._vary_numbers(nums, rules, variation=i)
                bets.append(sorted(nums))
            except:
                bets.append(self._random_bet(rules))

        return bets

    def _ensemble_8_bets(self, history, rules):
        """集成學習：不同模型組合"""
        bets = []

        # 使用不同基礎模型的組合
        base_methods = [
            self.engine.frequency_predict,
            self.engine.trend_predict,
            self.engine.monte_carlo_predict,
            self.engine.bayesian_predict,
        ]

        for i in range(8):
            try:
                # 輪流使用不同方法
                method = base_methods[i % len(base_methods)]
                res = method(history[:200], rules)
                nums = res['numbers']

                # 添加變化
                if i >= len(base_methods):
                    nums = self._vary_numbers(nums, rules, variation=i)

                bets.append(sorted(nums))
            except:
                bets.append(self._random_bet(rules))

        return bets

    def _deviation_8_bets(self, history, rules):
        """偏差分析：不同偏差閾值"""
        bets = []

        for i in range(8):
            try:
                res = self.engine.deviation_predict(history[:200], rules)
                nums = res['numbers']
                if i > 0:
                    nums = self._vary_numbers(nums, rules, variation=i)
                bets.append(sorted(nums))
            except:
                bets.append(self._random_bet(rules))

        return bets

    def _statistical_8_bets(self, history, rules):
        """統計學習：不同統計特徵"""
        bets = []

        for i in range(8):
            try:
                if hasattr(self.engine, 'statistical_predict'):
                    res = self.engine.statistical_predict(history[:200], rules)
                else:
                    res = self.engine.frequency_predict(history[:50], rules)

                nums = res['numbers']
                if i > 0:
                    nums = self._vary_numbers(nums, rules, variation=i)
                bets.append(sorted(nums))
            except:
                bets.append(self._random_bet(rules))

        return bets

    def _entropy_8_bets(self, history, rules):
        """熵驅動 Transformer：使用反共識過濾和熵最大化採樣"""
        max_num = rules.get('maxNumber', 49)
        pick_count = rules.get('pickCount', 6)
        
        # 初始化模型和採樣器
        model = EntropyTransformerModel(max_num=max_num)
        sampler = EntropyMaximizedSampler(n_bets=8, numbers_per_bet=pick_count)
        anti_filter = AntiConsensusFilter(penalty_factor=0.7)
        
        # 獲取模型概率
        probs = model.predict(history[:100])
        
        # 獲取共識號碼
        consensus_numbers = set()
        try:
            freq_result = self.engine.frequency_predict(history[:100], rules)
            consensus_numbers.update(freq_result['numbers'])
        except:
            pass
        try:
            trend_result = self.engine.trend_predict(history[:100], rules)
            consensus_numbers.update(trend_result['numbers'])
        except:
            pass
        
        # 應用反共識過濾
        filtered_probs = anti_filter.filter(probs, consensus_numbers)
        
        # 生成8注
        bets, _ = sampler.generate_diverse_8_bets(filtered_probs, strategy='balanced')
        
        return bets

    def _mixed_8_bets(self, history, rules):
        """混合策略：組合多種方法"""
        bets = []

        strategies = [
            self.engine.frequency_predict,
            self.engine.trend_predict,
            self.engine.monte_carlo_predict,
            self.engine.bayesian_predict,
        ]

        for i, method in enumerate(strategies[:4]):
            try:
                res = method(history[:200], rules)
                bets.append(sorted(res['numbers']))
            except:
                bets.append(self._random_bet(rules))

        # 添加4注變化
        for i in range(4):
            try:
                base_bet = bets[i % len(bets)]
                varied = self._vary_numbers(base_bet, rules, variation=i+1)
                bets.append(sorted(varied))
            except:
                bets.append(self._random_bet(rules))

        return bets[:8]

    def _vary_numbers(self, numbers, rules, variation=1):
        """對號碼進行變化處理"""
        nums = list(numbers)
        max_num = rules.get('maxNumber', rules.get('main_numbers', 49))

        # 隨機替換 variation 個號碼
        replace_count = min(variation, len(nums) // 2)

        for _ in range(replace_count):
            if nums:
                old_idx = random.randint(0, len(nums) - 1)
                new_num = random.randint(1, max_num)

                # 確保不重複
                attempts = 0
                while new_num in nums and attempts < 20:
                    new_num = random.randint(1, max_num)
                    attempts += 1

                if new_num not in nums:
                    nums[old_idx] = new_num

        return nums

    def _random_bet(self, rules):
        """生成隨機號碼"""
        count = rules.get('pickCount', rules.get('select_numbers', 6))
        max_num = rules.get('maxNumber', rules.get('main_numbers', 49))
        return sorted(random.sample(range(1, max_num + 1), count))

    def _random_8_bets(self, rules):
        """生成8注隨機號碼"""
        return [self._random_bet(rules) for _ in range(8)]


def calculate_prize_level(predicted, actual_main, actual_special):
    """
    計算中獎等級

    大樂透規則：
    - 頭獎：6個號碼全中
    - 貳獎：5個號碼 + 特別號
    - 參獎：5個號碼
    - 肆獎：4個號碼 + 特別號
    - 伍獎：4個號碼
    - 陸獎：3個號碼 + 特別號
    - 柒獎：2個號碼 + 特別號
    - 普獎：3個號碼
    """
    pred_set = set(predicted)
    actual_set = set(actual_main)

    match_count = len(pred_set.intersection(actual_set))
    has_special = actual_special in pred_set

    if match_count == 6:
        return "頭獎", 1, match_count, has_special
    elif match_count == 5 and has_special:
        return "貳獎", 2, match_count, has_special
    elif match_count == 5:
        return "參獎", 3, match_count, has_special
    elif match_count == 4 and has_special:
        return "肆獎", 4, match_count, has_special
    elif match_count == 4:
        return "伍獎", 5, match_count, has_special
    elif match_count == 3 and has_special:
        return "陸獎", 6, match_count, has_special
    elif match_count == 2 and has_special:
        return "柒獎", 7, match_count, has_special
    elif match_count == 3:
        return "普獎", 8, match_count, has_special
    else:
        return "未中獎", 0, match_count, has_special


class RollingBacktest8Bets:
    """8注滾動式回測系統"""

    def __init__(self, lottery_type='BIG_LOTTO'):
        self.lottery_type = lottery_type
        self.rules = get_lottery_rules(lottery_type)
        self.predictor = Fast8BetPredictor(prediction_engine)

        # 要測試的策略
        self.strategies = [
            'frequency',
            'trend',
            'monte_carlo',
            'bayesian',
            'hot_cold',
            'ensemble',
            'deviation',
            'statistical',
            'entropy_transformer',  # 熵驅動 Transformer
        ]

        # 統計數據
        self.stats = defaultdict(lambda: {
            'total_draws': 0,
            'total_bets': 0,
            'win_count': 0,
            'total_matches': 0,
            'best_prize_level': 0,
            'best_prize_name': '未中獎',
            'prize_distribution': defaultdict(int),
            'draw_records': []
        })

    def run(self):
        """執行滾動式回測"""
        print("=" * 100)
        print(f"🎲 2025年滾動式回測 - 8注號碼策略評估 ({self.lottery_type})")
        print("=" * 100)

        # 載入所有數據
        all_draws = db_manager.get_all_draws(self.lottery_type)
        all_draws.sort(key=lambda x: x['date'])

        # 分離訓練和測試數據
        train_data = [d for d in all_draws if not d['date'].startswith('2025')]
        test_data = [d for d in all_draws if d['date'].startswith('2025')]

        print(f"📚 訓練數據: {len(train_data)} 期 (2025年之前)")
        print(f"🧪 測試數據: {len(test_data)} 期 (2025年)")
        print("-" * 100)

        # 滾動式預測
        rolling_history = train_data.copy()

        for idx, target_draw in enumerate(test_data, 1):
            draw_num = target_draw['draw']
            draw_date = target_draw['date']
            actual_main = target_draw['numbers']
            actual_special = target_draw['special']

            print(f"\n🎯 第 {idx}/{len(test_data)} 期: {draw_num} ({draw_date})")
            print(f"   實際開獎: {', '.join([f'{n:02d}' for n in sorted(actual_main)])} + 特別號 {actual_special:02d}")

            # 使用最近300期數據（加速計算）
            recent_history = rolling_history[-300:] if len(rolling_history) > 300 else rolling_history

            # 對每個策略生成8注並評估
            for strategy_name in self.strategies:
                try:
                    # 生成8注號碼
                    eight_bets = self.predictor.generate_8_bets(recent_history, self.rules, strategy_name)

                    # 評估這8注的表現
                    draw_wins = 0
                    draw_best_prize = 0
                    draw_best_name = '未中獎'
                    draw_total_matches = 0

                    for bet in eight_bets:
                        prize_name, prize_level, match_count, has_special = calculate_prize_level(
                            bet, actual_main, actual_special
                        )

                        draw_total_matches += match_count

                        if prize_level > 0:
                            draw_wins += 1
                            self.stats[strategy_name]['prize_distribution'][prize_name] += 1

                            if draw_best_prize == 0 or prize_level < draw_best_prize:
                                draw_best_prize = prize_level
                                draw_best_name = prize_name

                    # 更新統計
                    self.stats[strategy_name]['total_draws'] += 1
                    self.stats[strategy_name]['total_bets'] += 8
                    self.stats[strategy_name]['win_count'] += draw_wins
                    self.stats[strategy_name]['total_matches'] += draw_total_matches

                    if draw_best_prize > 0:
                        if (self.stats[strategy_name]['best_prize_level'] == 0 or
                            draw_best_prize < self.stats[strategy_name]['best_prize_level']):
                            self.stats[strategy_name]['best_prize_level'] = draw_best_prize
                            self.stats[strategy_name]['best_prize_name'] = draw_best_name

                    # 記錄本期表現
                    self.stats[strategy_name]['draw_records'].append({
                        'draw': draw_num,
                        'date': draw_date,
                        'wins': draw_wins,
                        'best_prize': draw_best_name,
                        'total_matches': draw_total_matches,
                        'bets': eight_bets
                    })

                    # 顯示簡要結果
                    if draw_wins > 0:
                        print(f"   🎉 {strategy_name:<15} → 8注中{draw_wins}注 (最佳: {draw_best_name}, 共{draw_total_matches}個號碼)")

                except Exception as e:
                    logger.error(f"策略 {strategy_name} 失敗: {e}")

            # 將本期數據加入訓練集
            rolling_history.append(target_draw)

            if idx % 5 == 0:
                print(f"\n   ✅ 已完成 {idx}/{len(test_data)} 期測試...")

        # 輸出最終統計
        self._print_final_stats(rolling_history)

    def _print_final_stats(self, full_history):
        """輸出最終統計報告"""
        print("\n" + "=" * 100)
        print("📊 2025年滾動式回測統計報告 (8注策略)")
        print("=" * 100)

        # 計算成功率並排序
        ranked_strategies = []

        for strategy_name, stats in self.stats.items():
            if stats['total_bets'] == 0:
                continue

            win_rate = (stats['win_count'] / stats['total_bets']) * 100
            avg_matches_per_draw = stats['total_matches'] / stats['total_draws'] if stats['total_draws'] > 0 else 0

            ranked_strategies.append({
                'name': strategy_name,
                'win_count': stats['win_count'],
                'win_rate': win_rate,
                'best_prize': stats['best_prize_name'],
                'avg_matches': avg_matches_per_draw,
                'total_matches': stats['total_matches'],
                'stats': stats
            })

        # 排序：中獎次數 > 最佳獎項 > 總命中數
        ranked_strategies.sort(
            key=lambda x: (
                -x['win_count'],
                x['stats']['best_prize_level'] if x['stats']['best_prize_level'] > 0 else 999,
                -x['total_matches']
            )
        )

        # 輸出Top 5排名表
        print(f"\n{'排名':<6} {'模型':<16} {'中獎次數':<12} {'中獎率':<12} {'最佳獎項':<12} {'平均命中':<12} {'總命中'}")
        print("-" * 100)

        top5 = ranked_strategies[:5]

        for rank, strategy in enumerate(top5, 1):
            print(f"{rank:<6} {strategy['name']:<16} {strategy['win_count']:<12} "
                  f"{strategy['win_rate']:>8.2f}%    {strategy['best_prize']:<12} "
                  f"{strategy['avg_matches']:>8.2f}      {strategy['total_matches']}")

        # 輸出完整排名
        if len(ranked_strategies) > 5:
            print("\n📋 完整排名:")
            print("-" * 100)

            for rank, strategy in enumerate(ranked_strategies, 1):
                print(f"{rank:<6} {strategy['name']:<16} {strategy['win_count']:<12} "
                      f"{strategy['win_rate']:>8.2f}%    {strategy['best_prize']:<12} "
                      f"{strategy['avg_matches']:>8.2f}      {strategy['total_matches']}")

        # 輸出Top 5的最新一期8注預測
        print("\n" + "=" * 100)
        print("🔮 Top 5 策略最新一期 8注預測號碼")
        print("=" * 100)

        # 使用完整歷史數據生成最新預測
        recent_history = full_history[-300:] if len(full_history) > 300 else full_history

        for rank, strategy in enumerate(top5, 1):
            strategy_name = strategy['name']
            print(f"\n🏆 第{rank}名: {strategy_name.upper()}")
            print(f"   中獎率: {strategy['win_rate']:.2f}% | 最佳獎項: {strategy['best_prize']}")

            try:
                eight_bets = self.predictor.generate_8_bets(recent_history, self.rules, strategy_name)

                for bet_idx, bet in enumerate(eight_bets, 1):
                    bet_str = ", ".join(f"{n:02d}" for n in bet)
                    print(f"   第{bet_idx}注: [{bet_str}]")

            except Exception as e:
                print(f"   ❌ 預測失敗: {e}")

        # 輸出獎項分布（Top 3）
        print("\n" + "=" * 100)
        print("🎁 Top 3 策略獎項分布")
        print("=" * 100)

        for rank, strategy in enumerate(top5[:3], 1):
            strategy_name = strategy['name']
            prize_dist = strategy['stats']['prize_distribution']

            print(f"\n📌 第{rank}名: {strategy_name.upper()}")

            if prize_dist:
                sorted_prizes = sorted(prize_dist.items(), key=lambda x: x[1], reverse=True)
                dist_str = ", ".join([f"{name}×{count}" for name, count in sorted_prizes])
                print(f"   {dist_str}")
            else:
                print(f"   未中獎")

        print("\n" + "=" * 100)
        print("✅ 回測完成！")
        print("=" * 100)


def main():
    """主程序"""
    print("🎲 2025年大樂透滾動式回測系統")
    print("📈 每個策略生成8注號碼，評估整體成功率")
    print("=" * 100)

    backtest = RollingBacktest8Bets('BIG_LOTTO')
    backtest.run()


if __name__ == '__main__':
    main()
