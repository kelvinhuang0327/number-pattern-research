"""
多注覆蓋優化器 - 策略7

核心理念：
1. 單注預測準確率受限於彩票隨機性 (~4-5%)
2. 多注組合可以通過覆蓋更多號碼空間提高整體中獎率
3. 關鍵是生成足夠多樣化且互補的注組

設計原則：
1. 最大化號碼覆蓋率 - 多注組合應覆蓋更多不同號碼
2. 最小化重疊 - 減少注與注之間的重複號碼
3. 平衡策略多樣性 - 每注來自不同預測方法
4. 約束條件平衡 - 確保每注都符合統計規律

目標：6注組合達到 15%+ 中獎率 (至少1注中3個以上)
"""

import numpy as np
from collections import Counter, defaultdict
from typing import List, Dict, Tuple, Set
from itertools import combinations
import random
from .wobble_optimizer import WobbleOptimizer


class MultiBetOptimizer:
    """多注覆蓋優化器"""

    def __init__(self):
        self.name = "MultiBetOptimizer"
        self._load_strategies()
        self.wobble_opt = WobbleOptimizer()

    def _load_strategies(self):
        """載入策略"""
        from .unified_predictor import prediction_engine
        from .enhanced_predictor import EnhancedPredictor
        from .gap_predictor import GapAnalysisPredictor, ConsensusPredictor
        from .anti_consensus_predictor import AntiConsensusPredictor, HighValuePredictor

        self.enhanced = EnhancedPredictor()
        self.engine = prediction_engine
        self.gap_predictor = GapAnalysisPredictor()
        self.consensus_predictor = ConsensusPredictor()
        self.anti_consensus = AntiConsensusPredictor()
        self.high_value = HighValuePredictor()

        # 定義策略池，按多樣性分組 (P0+P1 優化)
        # 2026-01-03 P0優化: 加入馬可夫鏈、大間隔策略、低和值策略
        self.strategy_groups = {
            'frequency_based': [
                ('hot_cold_mix', lambda h, r: self.engine.hot_cold_mix_predict(h, r), 100),
                ('trend_predict', lambda h, r: self.engine.trend_predict(h, r), 300),
            ],
            'statistical': [
                ('zone_balance', lambda h, r: self.engine.zone_balance_predict(h, r), 500),
                ('sum_range', lambda h, r: self.engine.sum_range_predict(h, r), 100),
                ('odd_even', lambda h, r: self.engine.odd_even_balance_predict(h, r), 200),
            ],
            'probabilistic': [
                ('bayesian', lambda h, r: self.engine.bayesian_predict(h, r), 300),
                ('monte_carlo', lambda h, r: self.engine.monte_carlo_predict(h, r), 200),
                # 🔥 P0優化: 馬可夫鏈 - 捕捉轉移模式 (表現最佳)
                ('markov', lambda h, r: self.engine.markov_predict(h, r), 300),
            ],
            'pattern_based': [
                ('cold_comeback', lambda h, r: self.enhanced.cold_number_comeback_predict(h, r), 100),
                ('consecutive', lambda h, r: self.enhanced.consecutive_friendly_predict(h, r), 100),
                # P0 新增：間隔分析
                ('gap_analysis', lambda h, r: self.gap_predictor.predict(h, r), 300),
            ],
            'ensemble': [
                ('ensemble', lambda h, r: self.engine.ensemble_predict(h, r), 200),
                ('constrained', lambda h, r: self.enhanced.constrained_predict(h, r), 100),
                # P0 新增：共識投票
                ('consensus', lambda h, r: self.consensus_predictor.predict(h, r), 200),
            ],
            # P1 新增：反共識策略組
            'contrarian': [
                ('anti_consensus', lambda h, r: self.anti_consensus.predict(h, r), 200),
                ('contrarian', lambda h, r: self.anti_consensus.predict_contrarian(h, r), 200),
                ('high_value', lambda h, r: self.high_value.predict(h, r), 200),
            ],
            # 🔥 P0優化: 大間隔/雙峰策略組 - 覆蓋42%的大間隔開獎
            'bimodal': [
                ('bimodal_gap', lambda h, r: self._bimodal_gap_predict(h, r), 500),
                ('low_sum', lambda h, r: self._low_sum_predict(h, r), 500),
            ],
            # 🔥 P1優化: 間隔/和值/區間多樣化策略組
            'p1_advanced': [
                ('gap_sensitive', lambda h, r: self.engine.gap_sensitive_predict(h, r), 300),
                ('extended_sum', lambda h, r: self.engine.extended_sum_range_predict(h, r), 500),
                ('diverse_zone', lambda h, r: self.engine.diverse_zone_predict(h, r), 500),
            ],
            # 🔥 P2優化: 共現社群 + 動態權重策略組 (2026-01-04)
            'p2_advanced': [
                ('community', lambda h, r: self.engine.community_predict(h, r), 200),
                ('adaptive_weight', lambda h, r: self.engine.adaptive_weight_predict(h, r), 300),
            ]
        }

    def generate_diversified_bets(self, draws: List[Dict], lottery_rules: Dict,
                                  num_bets: int = 6,
                                  meta_config: Dict = None) -> Dict:
        """
        生成多樣化的多注組合

        Args:
            draws: 歷史數據
            lottery_rules: 彩票規則
            num_bets: 生成注數
            meta_config: 元配置（用於優化測試）
                - 'wobble_ratio': 鄰域擾動注數比例 (0.0 - 1.0)
                - 'base_strategy': 基於哪個策略進行擾動，預設為 'top_score'
        """
        pick_count = lottery_rules.get('pickCount', lottery_rules.get('pick_count', 6))
        min_num = lottery_rules.get('minNumber', lottery_rules.get('min_number', 1))
        max_num = lottery_rules.get('maxNumber', lottery_rules.get('max_number', 49))

        # 收集所有策略的預測結果
        all_predictions = {}
        for group_name, strategies in self.strategy_groups.items():
            for name, func, window in strategies:
                try:
                    history = draws[:window]
                    result = func(history, lottery_rules)
                    all_predictions[name] = {
                        'numbers': set(result['numbers']),
                        'group': group_name,
                        'confidence': result.get('confidence', 0.5)
                    }
                except Exception as e:
                    continue

        # 計算號碼綜合分數
        number_scores = self._calculate_number_scores(all_predictions, min_num, max_num)

        # 生成多注組合
        bets = []
        used_combos = set()
        meta_config = meta_config or {}
        wobble_ratio = meta_config.get('wobble_ratio', 0.2) 
        num_wobble = int(num_bets * wobble_ratio)
        num_base = num_bets - num_wobble

        # 策略1: 基礎策略 (選分組中第一名或指定的策略)
        base_strategy_name = meta_config.get('base_strategy', 'top_score')
        
        # 準備基礎注
        available_strategies = []
        for group_name, strategies in self.strategy_groups.items():
            for name, _, _ in strategies:
                if name in all_predictions:
                    available_strategies.append((name, group_name, all_predictions[name]['confidence']))

        # 排序策略 (依據信心度或指定名稱)
        if base_strategy_name != 'top_score':
            # 優先將指定策略排在前面
            available_strategies.sort(key=lambda x: (x[0] != base_strategy_name, -x[2]))
        else:
            available_strategies.sort(key=lambda x: -x[2])

        # 填注 1: 基礎多樣性注
        for name, group_name, _ in available_strategies:
            if len(bets) >= num_base:
                break
            bet = sorted(all_predictions[name]['numbers'])
            if tuple(bet) not in used_combos:
                bets.append({
                    'numbers': bet,
                    'source': name,
                    'group': group_name
                })
                used_combos.add(tuple(bet))

        # 填注 2: 鄰域擾動 (Wobble) - P2優化：使用智能擾動
        if num_wobble > 0 and bets:
            # 基於第一注（通常是信心度最高）進行擾動
            base_bet = bets[0]['numbers']

            # P2優化：選擇擾動策略
            wobble_method = meta_config.get('wobble_method', 'smart')  # smart | cooccurrence | systematic

            if wobble_method == 'smart':
                # 智能擾動：根據頻率和共現選擇最佳擾動方向
                wobble_variants = self.wobble_opt.smart_wobble(
                    base_bet, num_bets=num_wobble + 1, history=draws[:200]
                )
            elif wobble_method == 'cooccurrence':
                # 共現感知擾動：優先擾動到共現頻繁的號碼
                wobble_variants = self.wobble_opt.cooccurrence_aware_wobble(
                    base_bet, num_bets=num_wobble + 1, history=draws[:200]
                )
            else:
                # 原始系統化擾動
                wobble_variants = self.wobble_opt.systematic_wobble(base_bet, num_bets=num_wobble + 1)

            for variant in wobble_variants[1:]: # 跳過原始注
                if len(bets) >= num_bets:
                    break
                if tuple(variant) not in used_combos:
                    bets.append({
                        'numbers': variant,
                        'source': f'wobble_{wobble_method}({bets[0]["source"]})'
                    })
                    used_combos.add(tuple(variant))

        # 應用區間斷層修正 (Zone Gap Correction)
        # 如果某個區塊很久沒開，強制在一注中補強該區塊
        bets = self._apply_zone_gap_correction(bets, draws, lottery_rules)

        # 計算覆蓋統計

        # 計算覆蓋統計
        all_covered = set()
        for bet in bets:
            all_covered.update(bet['numbers'])

        coverage = len(all_covered) / (max_num - min_num + 1)

        # 特別號預測
        specials = None
        if lottery_rules.get('hasSpecialNumber', False):
            specials = self._predict_multiple_specials(draws, lottery_rules, num_bets)

        return {
            'bets': bets[:num_bets],
            'specials': specials,
            'coverage': coverage,
            'covered_numbers': sorted(all_covered),
            'total_unique_numbers': len(all_covered),
            'strategies_used': list(set(b.get('source', 'unknown') for b in bets))
        }

    def _apply_zone_gap_correction(self, bets: List[Dict], draws: List[Dict], lottery_rules: Dict) -> List[Dict]:
        """
        區間斷層修正：識別長期未開出的區塊並在多注中進行補強
        """
        if not draws or not bets:
            return bets
            
        pick_count = lottery_rules.get('pickCount', 6)
        min_num = lottery_rules.get('minNumber', 1)
        max_num = lottery_rules.get('maxNumber', 49)
        
        # 定義 5 個區塊
        zone_size = (max_num - min_num + 1) // 5
        zones = []
        for i in range(5):
            z_min = min_num + i * zone_size
            z_max = min_num + (i+1) * zone_size - 1 if i < 4 else max_num
            zones.append((z_min, z_max))
            
        # 統計各區塊最近 20 期的開出頻率
        recent_draws = draws[:20]
        zone_counts = [0] * 5
        for d in recent_draws:
            for n in d['numbers']:
                for i, (z_min, z_max) in enumerate(zones):
                    if z_min <= n <= z_max:
                        zone_counts[i] += 1
                        break
                        
        # 找出最冷門的區塊 (可能出現斷層回補)
        coldest_zone_idx = np.argmin(zone_counts)
        z_min, z_max = zones[coldest_zone_idx]
        
        # 檢查現有注項是否覆蓋了冷門區塊
        covered = any(any(z_min <= n <= z_max for n in b['numbers']) for b in bets)
        
        if not covered and len(bets) > 1:
            # 修正最後一注，強制加入一個來自冷門區塊的號碼
            target_bet = bets[-1]
            # 找到冷門區塊中歷史頻率較高的號碼
            all_nums_in_zone = list(range(z_min, z_max + 1))
            # 簡單隨機選一個或補償
            new_num = random.choice(all_nums_in_zone)
            if new_num not in target_bet['numbers']:
                target_bet['numbers'][-1] = new_num # 替換最後一個號碼
                target_bet['numbers'].sort()
                target_bet['source'] += " + zone_gap_corrected"
                
        return bets

    def _calculate_number_scores(self, predictions: Dict, min_num: int, max_num: int) -> Dict[int, float]:
        """計算號碼綜合分數"""
        scores = defaultdict(float)

        for name, data in predictions.items():
            confidence = data.get('confidence', 0.5)
            for num in data['numbers']:
                scores[num] += confidence

        # 確保所有號碼都有分數
        for num in range(min_num, max_num + 1):
            if num not in scores:
                scores[num] = 0.1

        return dict(scores)

    def _calculate_diversity(self, candidate: Tuple[int, ...], existing_bets: List[List[int]]) -> float:
        """計算候選組合與現有注的差異度"""
        if not existing_bets:
            return 1.0

        total_overlap = 0
        for existing in existing_bets:
            overlap = len(set(candidate) & set(existing))
            total_overlap += overlap

        avg_overlap = total_overlap / len(existing_bets)
        max_overlap = len(candidate)

        return 1 - (avg_overlap / max_overlap)

    def _predict_multiple_specials(self, draws: List[Dict], lottery_rules: Dict,
                                   num_bets: int) -> List[int]:
        """預測多個特別號"""
        special_min = lottery_rules.get('specialMinNumber', lottery_rules.get('specialMin', 1))
        special_max = lottery_rules.get('specialMaxNumber', lottery_rules.get('specialMax', 8))

        # 統計特別號頻率
        special_freq = Counter()
        for h in draws[:100]:
            special = h.get('special_number') or h.get('special')
            if special is not None:
                special_freq[special] += 1

        if not special_freq:
            return list(range(special_min, min(special_min + num_bets, special_max + 1)))

        # 選擇不同的特別號
        specials = []
        for num, _ in special_freq.most_common():
            if len(specials) >= num_bets:
                break
            specials.append(num)

        # 補足不夠的
        while len(specials) < num_bets:
            for num in range(special_min, special_max + 1):
                if num not in specials:
                    specials.append(num)
                    if len(specials) >= num_bets:
                        break

        return specials[:num_bets]

    def backtest_multi_bet(self, draws: List[Dict], lottery_rules: Dict,
                           num_bets: int = 6, test_periods: int = 100,
                           meta_config: Dict = None) -> Dict:
        """
        多注策略回測

        判定標準：任意一注中3個及以上視為中獎
        """
        results = []
        win_count = 0
        total_best_matches = 0

        print(f"\n多注覆蓋策略回測 ({num_bets} 注 × {test_periods} 期)")
        print("-" * 60)

        for i in range(test_periods):
            target = draws[i]
            target_numbers = set(target['numbers'])
            history = draws[i + 1:]

            if len(history) < 100:
                continue

            try:
                prediction = self.generate_diversified_bets(history, lottery_rules, num_bets, meta_config)

                # 檢查每一注
                bet_matches = []
                best_match = 0
                best_bet_idx = -1

                for idx, bet in enumerate(prediction['bets']):
                    matches = len(set(bet['numbers']) & target_numbers)
                    bet_matches.append(matches)
                    if matches > best_match:
                        best_match = matches
                        best_bet_idx = idx

                total_best_matches += best_match

                # 任一注中3個及以上視為中獎
                if best_match >= 3:
                    win_count += 1
                    status = f"WIN (第{best_bet_idx+1}注, {best_match}個)"
                else:
                    status = ""

                results.append({
                    'draw': target['draw'],
                    'bet_matches': bet_matches,
                    'best_match': best_match,
                    'best_bet_idx': best_bet_idx,
                    'coverage': prediction['coverage'],
                    'won': best_match >= 3
                })

                if (i + 1) % 20 == 0:
                    current_win_rate = win_count / (i + 1) * 100
                    current_avg = total_best_matches / (i + 1)
                    print(f"進度: {i+1}/{test_periods}, "
                          f"中獎率: {current_win_rate:.2f}%, "
                          f"最佳匹配平均: {current_avg:.2f}")

            except Exception as e:
                print(f"錯誤 ({target['draw']}): {e}")

        test_count = len(results)

        # 分析每注位置的表現
        bet_position_stats = defaultdict(lambda: {'count': 0, 'wins': 0, 'total_matches': 0})
        for r in results:
            for idx, matches in enumerate(r['bet_matches']):
                bet_position_stats[idx]['count'] += 1
                bet_position_stats[idx]['total_matches'] += matches
                if matches >= 3:
                    bet_position_stats[idx]['wins'] += 1

        return {
            'num_bets': num_bets,
            'test_count': test_count,
            'win_count': win_count,
            'win_rate': win_count / test_count if test_count > 0 else 0,
            'avg_best_match': total_best_matches / test_count if test_count > 0 else 0,
            'bet_position_stats': dict(bet_position_stats),
            'details': results
        }

    # ========================================================================
    # 🔥 P0優化: 新增策略方法 (2026-01-03)
    # ========================================================================

    def _bimodal_gap_predict(self, draws: List[Dict], lottery_rules: Dict) -> Dict:
        """
        雙峰/大間隔預測策略

        專門生成「低區群聚 + 高區群聚」的號碼組合
        覆蓋歷史上 42% 的大間隔開獎模式
        """
        pick_count = lottery_rules.get('pickCount', 6)
        min_num = lottery_rules.get('minNumber', 1)
        max_num = lottery_rules.get('maxNumber', 49)

        # 統計各區號碼頻率
        freq = Counter()
        for d in draws[:200]:
            freq.update(d['numbers'])

        # 定義低區和高區
        low_range = range(min_num, min_num + (max_num - min_num) // 3)  # 1-16 for 49
        high_range = range(max_num - (max_num - min_num) // 3, max_num + 1)  # 33-49 for 49

        # 從低區選 3-4 個高頻號碼
        low_nums = [(n, freq.get(n, 0)) for n in low_range]
        low_nums.sort(key=lambda x: -x[1])
        low_selected = [n for n, _ in low_nums[:4]]

        # 從高區選 2-3 個高頻號碼
        high_nums = [(n, freq.get(n, 0)) for n in high_range]
        high_nums.sort(key=lambda x: -x[1])
        high_selected = [n for n, _ in high_nums[:3]]

        # 組合：低區 4 個 + 高區 2 個 = 6 個
        # 製造大間隔 (類似 19→40)
        numbers = low_selected[:4] + high_selected[:2]
        numbers = sorted(set(numbers))[:pick_count]

        # 補足不夠的
        if len(numbers) < pick_count:
            all_nums = list(range(min_num, max_num + 1))
            random.shuffle(all_nums)
            for n in all_nums:
                if n not in numbers:
                    numbers.append(n)
                    if len(numbers) >= pick_count:
                        break

        return {
            'numbers': sorted(numbers[:pick_count]),
            'confidence': 0.65,
            'method': 'bimodal_gap',
            'description': '雙峰分布策略 - 低區群聚 + 高區群聚'
        }

    def _low_sum_predict(self, draws: List[Dict], lottery_rules: Dict) -> Dict:
        """
        低和值預測策略

        專門生成和值 < 130 的號碼組合
        覆蓋歷史上 26% 的低和值開獎
        """
        pick_count = lottery_rules.get('pickCount', 6)
        min_num = lottery_rules.get('minNumber', 1)
        max_num = lottery_rules.get('maxNumber', 49)

        # 目標和值範圍
        target_sum_min = 90
        target_sum_max = 130

        # 統計號碼頻率
        freq = Counter()
        for d in draws[:200]:
            freq.update(d['numbers'])

        # 偏好較小的號碼，但要考慮頻率
        candidates = []
        for n in range(min_num, max_num + 1):
            # 分數 = 頻率加成 - 號碼大小懲罰
            score = freq.get(n, 0) * 0.5 - n * 0.3
            candidates.append((n, score))

        candidates.sort(key=lambda x: -x[1])

        # 貪心選擇：在和值約束下選擇高分號碼
        numbers = []
        current_sum = 0

        for n, _ in candidates:
            if len(numbers) >= pick_count:
                break
            # 預估加入後的和值
            if current_sum + n <= target_sum_max:
                numbers.append(n)
                current_sum += n

        # 如果和值太低，補充一些中等號碼
        if current_sum < target_sum_min and len(numbers) < pick_count:
            mid_nums = [n for n in range(20, 35) if n not in numbers]
            random.shuffle(mid_nums)
            for n in mid_nums:
                if len(numbers) >= pick_count:
                    break
                if current_sum + n <= target_sum_max + 10:
                    numbers.append(n)
                    current_sum += n

        # 補足不夠的
        if len(numbers) < pick_count:
            small_nums = [n for n in range(min_num, 25) if n not in numbers]
            random.shuffle(small_nums)
            for n in small_nums:
                if n not in numbers:
                    numbers.append(n)
                    if len(numbers) >= pick_count:
                        break

        return {
            'numbers': sorted(numbers[:pick_count]),
            'confidence': 0.60,
            'method': 'low_sum',
            'description': f'低和值策略 - 目標和值 {target_sum_min}-{target_sum_max}'
        }


# 單例
multi_bet_optimizer = MultiBetOptimizer()


def test_multi_bet():
    """測試多注覆蓋策略"""
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

    from database import DatabaseManager
    from common import get_lottery_rules

    print("=" * 80)
    print("多注覆蓋優化器測試 - 2025年大樂透")
    print("=" * 80)

    db = DatabaseManager(db_path=os.path.join(os.path.dirname(__file__), '..', 'data', 'lottery_v2.db'))
    draws = db.get_all_draws('BIG_LOTTO')
    rules = get_lottery_rules('BIG_LOTTO')

    print(f"\n數據: {len(draws)} 期")

    # 篩選2025年
    draws_2025 = [d for d in draws if d['date'].startswith('2025') or d['date'].startswith('114')]
    print(f"2025年: {len(draws_2025)} 期")

    optimizer = MultiBetOptimizer()

    # 測試不同注數
    for num_bets in [3, 6, 8]:
        print(f"\n{'='*60}")
        print(f"測試 {num_bets} 注策略")
        print(f"{'='*60}")

        results = optimizer.backtest_multi_bet(draws, rules, num_bets, len(draws_2025))

        print(f"\n結果:")
        print(f"  中獎次數: {results['win_count']}/{results['test_count']}")
        print(f"  中獎率: {results['win_rate']*100:.2f}%")
        print(f"  最佳匹配平均: {results['avg_best_match']:.2f}")

        print(f"\n  各注位置表現:")
        for idx, stats in sorted(results['bet_position_stats'].items()):
            if stats['count'] > 0:
                avg_match = stats['total_matches'] / stats['count']
                win_rate = stats['wins'] / stats['count'] * 100
                print(f"    第{idx+1}注: 平均匹配 {avg_match:.2f}, 中獎率 {win_rate:.1f}%")

    return results


if __name__ == '__main__':
    test_multi_bet()
