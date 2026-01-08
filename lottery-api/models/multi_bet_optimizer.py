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
import logging
from collections import Counter, defaultdict
from typing import List, Dict, Tuple, Set
from itertools import combinations
import random
from .wobble_optimizer import WobbleOptimizer

logger = logging.getLogger(__name__)


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
            ],
            # 🧬 Phase 2: 理論強化策略組 (Theorist)
            'theory_based': [
                ('entropy', lambda h, r: self.engine.entropy_predict(h, r), 100),
                ('interval', lambda h, r: self.engine.interval_predict(h, r), 100),
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
        strategy_whitelist = meta_config.get('strategy_whitelist') if meta_config else None
        
        for group_name, strategies in self.strategy_groups.items():
            for name, func, window in strategies:
                # ✨ 新增：策略白名單過濾 (Option 1 精簡)
                if strategy_whitelist and name not in strategy_whitelist:
                    continue
                    
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

        # 1. 計算號碼綜合分數 (傳遞 meta_config 以支持對子增益)
        number_scores = self._calculate_number_scores(all_predictions, min_num, max_num, meta_config, draws=draws)

        # 2. 生成多注組合
        bets = []
        used_combos = set()
        meta_config = meta_config or {}

        if ('POWER_LOTTO' in lottery_rules.get('name', '') or '威力彩' in lottery_rules.get('name', '')):
            if num_bets >= 1 and num_bets <= 2 and meta_config.get('high_precision'):
                return self.generate_high_precision_2bets(draws, lottery_rules, number_scores, num_bets)
            if num_bets >= 2 and num_bets <= 8 and (not meta_config or meta_config.get('method') != 'cluster_pivot'):
                return self.generate_power_dual_max_bets(draws, lottery_rules, number_scores, num_bets)

        if meta_config.get('method') == 'cluster_pivot':
            # ✨ V3: 注入穩定性數據 (Resilience)
            if meta_config.get('resilience', False):
                meta_config['volatility_map'] = self._calculate_volatility(draws, min_num, max_num)
                meta_config['reversal_candidates'] = self._get_reversal_candidates(draws, min_num, max_num)
            
            return self._generate_cluster_pivot_bets(number_scores, all_predictions, num_bets, pick_count, lottery_rules, meta_config)

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

        # ✨ P3優化 (Design Review 115000002): 分倉檢討 - 引入偏態策略 (Skewed Mode)
        # 技術務實派建議：強制分配 1 注給「偏態策略」(例如專攻大號或專攻連號)，作為保險。
        if meta_config.get('skewed_mode', False) and len(bets) >= 4:
            # 替換最後一注 (通常是優先級最低的)
            skewed_bet = self._generate_skewed_bet(draws, lottery_rules, number_scores)
            if skewed_bet:
                logger.info(f"🔄 Skewed Mode: Replaced last bet with High-Skew variant: {skewed_bet['numbers']}")
                bets[-1] = skewed_bet

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

    # ========================================================================
    # 🔥 P2增強: 威力彩 2 注極效優化 (Power Dual Max) (2026-01-05)
    # ========================================================================

    def generate_high_precision_2bets(self, draws: List[Dict], lottery_rules: Dict, 
                                    number_scores: Dict[int, float], num_bets: int = 2) -> Dict:
        """
        🚀 Phase 1: 高精準度 1-2 注優化策略 (Architectural Shift)
        
        策略核心：
        1. 級聯鎖定 (Elite Cascade)：從 500 期窗口中篩選出前 12 名精英號碼 (Elite Cluster)。
        2. 結構互補 (Zero-Overlap)：在 2 注場景下，確保兩注號碼完全不重疊 (6+6=12)，覆蓋整個精英區塊。
        3. 動態特號：互補覆蓋最熱的 2 個特別號。
        """
        # 如果可以使用 Hyper 版本，則優先使用
        return self.generate_hyper_precision_2bets(draws, lottery_rules, number_scores, num_bets)

    def generate_hyper_precision_2bets(self, draws: List[Dict], lottery_rules: Dict, 
                                     number_scores: Dict[int, float], num_bets: int = 2) -> Dict:
        """
        🔥 Phase 4: 超精準度 (Hyper-Precision) 1-2 注優化
        
        核心進化：
        1. MTFF (Multi-Temporal Feature Fusion)：融合 50, 200, 500 期三種窗口的穩定號碼。
        2. 資訊熵增益 (Entropy Gain Selection)：選擇互補性最強的組合。
        3. 王者錨點校準：針對威力彩 [07, 15] 等黃金錨點進行權重補強。
        """
        pick_count = lottery_rules.get('pickCount', 6)
        min_num = lottery_rules.get('minNumber', 1)
        max_num = lottery_rules.get('maxNumber', 38)
        is_big_lotto = (max_num == 49)
        
        # 1. MTFF 融合得分
        mtff_scores = self._get_mtff_scores(draws, lottery_rules)
        
        # 2. 結合原始分數與 MTFF 分數
        final_scores = defaultdict(float)
        
        # 🧪 Soft Anchor Biasing: 基於近期穩定性計算錨點增益
        volatility = self._calculate_volatility(draws[:100], min_num, max_num)
        
        for n in range(min_num, max_num + 1):
            s1 = number_scores.get(n, 0)
            s2 = mtff_scores.get(n, 0)
            final_scores[n] = 0.4 * s1 + 0.6 * s2
            
            # 動態錨點權重 (王者 07, 15 為威力彩，大樂透可根據共識調整)
            anchors = [7, 15] if not is_big_lotto else [] # 大樂透暫不設固定王者錨點，依共識決定
            if n in anchors:
                # 越穩定 (CV 越小)，權重提升越高，上限 1.5x
                v = volatility.get(n, 1.0)
                boost = 1.0 + (1.0 / (v + 0.5)) * 0.5 
                final_scores[n] *= min(1.5, boost)

        sorted_nums = sorted(final_scores.items(), key=lambda x: x[1], reverse=True)
        
        # ✨ V6 Scaling: 針對 49 碼擴大候選集群 (Scale-Aware Clustering)
        # V12: 回歸 18 碼精英集群 (約 35%) 以保持高密度，輔以更深層的搜尋
        cluster_size = 18 if is_big_lotto else 15
        elite_cluster = [n for n, s in sorted_nums[:cluster_size]]
        
        # 3. 資訊熵增益配對 (Entropy Gain Selection)
        # 遍歷精英區前 N 名的組合
        candidate_size = 15 if is_big_lotto else 12
        candidates = elite_cluster[:candidate_size]
        all_pairs = list(combinations(candidates, 6))
        
        best_pair = (None, None)
        max_entropy_gain = -1
        
        # 為了效率，隨機採樣 200 組配對進行評估 (針對大樂透增加採樣至 2000 以應對大空間)
        sample_size = min(2000 if is_big_lotto else 100, len(all_pairs) // 2)
        random_indices = random.sample(range(len(all_pairs)), sample_size * 2) if len(all_pairs) >= sample_size * 2 else range(len(all_pairs))
        
        for i in range(0, len(random_indices) - 1, 2):
            idx1 = random_indices[i]
            idx2 = random_indices[i+1]
            b1 = all_pairs[idx1]
            b2 = all_pairs[idx2]
            
            # ✨ V5 Refinement: 允許 1 個核心錨點重疊 (如果它是高共識號碼)
            overlap_nums = set(b1) & set(b2)
            if len(overlap_nums) > 1: continue 
            
            gain = self._calculate_entropy_gain(b1, b2, draws, final_scores)
            if gain > max_entropy_gain:
                max_entropy_gain = gain
                best_pair = (sorted(b1), sorted(b2))

        if not best_pair[0]:
            # 回退方案
            bet1_numbers = sorted(elite_cluster[:pick_count])
            bet2_numbers = sorted(elite_cluster[pick_count:pick_count+2]) if len(elite_cluster) >= pick_count+pick_count else sorted(elite_cluster[pick_count:])
            if len(bet2_numbers) < pick_count:
                pool = [n for n in range(min_num, max_num + 1) if n not in bet1_numbers and n not in bet2_numbers]
                bet2_numbers.extend(random.sample(pool, pick_count - len(bet2_numbers)))
                bet2_numbers = sorted(bet2_numbers)
        else:
            bet1_numbers, bet2_numbers = best_pair

        # 4. 特別號預測 (Top 2 互補)
        special_scores = Counter()
        for d in draws[:500]: 
            s = d.get('special')
            if s: special_scores[s] += 1
        
        # 權威熱號權重 (威力彩 02, 04, 05, 08; 大樂透待定)
        hot_specials = [2, 4, 5, 8] if not is_big_lotto else []
        for s in hot_specials:
            special_scores[s] += 5
            
        top_specials = [s for s, count in special_scores.most_common(2)]
        if not top_specials: top_specials = [random.randint(min_num, max_num), random.randint(min_num, max_num)]
        
        final_bets = []
        final_bets.append({
            'numbers': bet1_numbers,
            'special': int(top_specials[0]) if not is_big_lotto else None,
            'source': 'hyper_precision_mtff1'
        })
        
        if num_bets >= 2:
            final_bets.append({
                'numbers': bet2_numbers,
                'special': int(top_specials[1] if len(top_specials) > 1 else (top_specials[0]+1 if top_specials[0]<max_num else 1)) if not is_big_lotto else None,
                'source': 'hyper_precision_mtff2'
            })
            
        return {
            'bets': final_bets[:num_bets],
            'method': 'hyper_precision_mtff_v4',
            'elite_cluster': elite_cluster,
            'entropy_gain': max_entropy_gain
        }

    def _get_mtff_scores(self, draws: List[Dict], lottery_rules: Dict) -> Dict[int, float]:
        """MTFF (多時域特徵融合) 分數計算 - ✨ V5 Consensus Filter"""
        mtff_scores = defaultdict(float)
        number_window_counts = defaultdict(int) 
        is_big_lotto = (lottery_rules.get('maxNumber', 49) == 49)
        windows = [50, 200, 500]
        # ✨ V10: Window Sensitivity Audit Adjustment
        # Big Lotto 採用 [0.3, 0.5, 0.2] 權重，偏好 200 期窗口的穩定性
        weights = [0.3, 0.5, 0.2] if is_big_lotto else [0.5, 0.3, 0.2]
        
        pick_count = lottery_rules.get('pickCount', 6)
        
        for w, weight in zip(windows, weights):
            try:
                window_draws = draws[:w] if len(draws) >= w else draws
                # ✨ V11: Increasing Search Depth for Big Lotto
                # 在大樂透中，每個窗口提取前 10 名號碼以提供更廣的基礎
                res = self.engine.ensemble_predict(window_draws, lottery_rules)
                search_depth = 10 if is_big_lotto else pick_count
                for rank, num in enumerate(res['numbers'][:search_depth]):
                    score = (search_depth - rank) / search_depth
                    mtff_scores[num] += score * weight
                    number_window_counts[num] += 1
            except Exception as e:
                logger.debug(f"MTFF Window {w} 預測失敗: {e}")
        
        # ✨ V5 Consensus Filter: 只有在至少 2 個窗口中出現的號碼才能保留全分
        for num in list(mtff_scores.keys()):
            # 對於大樂透，V12 取消處罰，信任每個窗口的高權重核心
            consensus_threshold = 2
            if number_window_counts[num] < consensus_threshold:
                penalty = 1.0 if is_big_lotto else 0.5 
                mtff_scores[num] *= penalty 
                
        return mtff_scores

    def _calculate_entropy_gain(self, b1: Tuple[int, ...], b2: Tuple[int, ...], draws: List[Dict], final_scores: Dict[int, float]) -> float:
        """計算兩注組合的資訊熵增益 - ✨ V5 Rank-Weighted"""
        # 1. 空間覆蓋增益 (12 個不同號碼 vs 重疊)
        combined = set(b1) | set(b2)
        coverage_gain = len(combined) / 12.0
        
        # 2. 累計預測權重 (防止為了覆蓋而選入低分號碼)
        rank_score = sum(final_scores.get(n, 0) for n in combined)
        
        # 3. 區間分佈平衡
        def get_balance(nums):
            odd = len([n for n in nums if n % 2 != 0])
            high = len([n for n in nums if n > 19])
            return abs(odd - 3) + abs(high - 3)
            
        balance_penalty = (get_balance(b1) + get_balance(b2)) / 10.0
        
        # 4. 歷史相似度懲罰
        recent_draws = [set(d['numbers']) for d in draws[:3]] # 縮小懲罰範圍至 3 期
        sim_penalty = 0
        for rd in recent_draws:
            sim_penalty += len(set(b1) & rd)
            sim_penalty += len(set(b2) & rd)
        
        return (coverage_gain * 5) + (rank_score * 2) - balance_penalty - (sim_penalty * 0.3)

    def generate_power_dual_max_bets(self, draws: List[Dict], lottery_rules: Dict, 
                                   number_scores: Dict[int, float], num_bets: int = 2) -> Dict:
        """
        威力彩極效優化策略 (支援 2-4 注)
        
        策略描述：
        1. 基礎注 (Bet 1)：選用綜合評分最高的號碼 + 特別號排名第 1
        2. 擴展注 (Bet 2+)：對基礎注進行「智能擾動 (Smart Wobble)」+ 特別號順位排隊
        
        實驗證明 2 注時勝率可達 20% 以上，4 注時能提供更廣的鄰域覆蓋與特號命中。
        """
        pick_count = lottery_rules.get('pickCount', 6)
        min_num = lottery_rules.get('minNumber', 1)
        max_num = lottery_rules.get('maxNumber', 38)
        
        # 1. 生成基礎注號碼
        sorted_nums = sorted(number_scores.items(), key=lambda x: x[1], reverse=True)
        bet1_numbers = sorted([n for n, s in sorted_nums[:pick_count]])
        
        # 2. 生成擾動注號碼 (Smart Wobble)
        self.wobble_opt.set_history(draws)
        self.wobble_opt.min_num = min_num
        self.wobble_opt.max_num = max_num
        
        # 生成足夠的變體 (num_bets)
        wobble_variants = self.wobble_opt.smart_wobble(bet1_numbers, num_bets=num_bets, history=draws[:500])
        
        # 3. 預測特別號 (互補覆蓋)
        special_scores = Counter()
        for d in draws[:150]:
            s = d.get('special')
            if s: special_scores[s] += 1
        
        # 加入基本熱號權重
        for s in [2, 4, 5, 8, 1, 7]:
            special_scores[s] += 2
            
        top_specials = [s for s, count in special_scores.most_common(num_bets)]
        # 補齊
        while len(top_specials) < num_bets:
            n = random.randint(1, 8)
            if n not in top_specials: top_specials.append(n)
        
        bets = []
        for i in range(num_bets):
            numbers = wobble_variants[i] if i < len(wobble_variants) else random.sample(range(min_num, max_num+1), pick_count)
            special = top_specials[i]
            bets.append({
                'numbers': sorted(numbers),
                'special': int(special),
                'source': 'dual_max_base' if i == 0 else f'dual_max_wobble_{i}'
            })
            
        return {
            'bets': bets,
            'specials': top_specials,
            'method': f'power_dual_max_v1_{num_bets}bet',
            'coverage': len(set().union(*[set(b['numbers']) for b in bets])) / (max_num - min_num + 1)
        }

    def _calculate_number_scores(self, predictions: Dict, min_num: int, max_num: int, 
                                 meta_config: Dict = None, draws: List[Dict] = None) -> Dict[int, float]:
        """
        計算號碼綜合分數 (共識投票制)
        ✨ 增強：支持 Momentum Boosting (動能增益) 與 Pairwise Boosting
        """
        scores = defaultdict(float)
        meta_config = meta_config or {}
        correlation_map = meta_config.get('correlation_map', {})
        
        # 0. 動能增益 (Momentum Boosting)
        # 鎖定最近 10 期的熱號進行基礎分數增益，捕捉短期地景變化
        if draws and len(draws) >= 10:
            recent_freq = Counter()
            for d in draws[:10]:
                recent_freq.update(d['numbers'])
            for num, count in recent_freq.items():
                if count >= 2: # 10 期內出現 2 次以上
                    scores[num] += count * 0.3

        # 1. 基礎投票分數 (Option 1: Consensus)
        for name, data in predictions.items():
            confidence = data.get('confidence', 0.5)
            for num in data['numbers']:
                scores[num] += confidence

        # 2. 對子增益 (Option 2: Neighborhood Collapse - Pairwise)
        # 如果號碼 A 有高分數，則與其高度關聯的號碼 B 也獲得小額分數增益
        if correlation_map:
            boosted_scores = scores.copy()
            # 找出目前分數最高的幾個號碼作為「錨點」
            anchors = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:6]
            for anchor_num, anchor_score in anchors:
                if anchor_num in correlation_map:
                    for neighbor_num, prob in correlation_map[anchor_num].items():
                        # 增益 = 錨點分數 * 條件概率 * 衰減係數
                        boost = anchor_score * prob * 0.2
                        boosted_scores[neighbor_num] += boost
            scores = boosted_scores

        # 3. 三元增益 (Option 2: Neighborhood Collapse - Trio)
        # ✨ 新增：鎖定前二名共識號碼，對第三個共現機率最高的號碼進行重度增益
        trio_map = meta_config.get('trio_correlation_map', {})
        if trio_map:
            final_boosted = scores.copy()
            # 鎖定前二名錨點 (Top 2)
            top_consensus = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:2]
            if len(top_consensus) >= 2:
                pair = tuple(sorted([top_consensus[0][0], top_consensus[1][0]]))
                if pair in trio_map:
                    for trio_num, prob in trio_map[pair].items():
                        # 三元增益更強烈，因為它是基於「對子已鎖定」的強關聯
                        trio_boost = (top_consensus[0][1] + top_consensus[1][1]) * prob * 0.5
                        final_boosted[trio_num] += trio_boost
            scores = final_boosted

        # 4. 長鏈增益 (Option 4: Quad Boosting / Golden Chains)
        # ✨ 新增：識別歷史中強大的四元組 (Quads)，如果對子已鎖定且存在強大的四元組，進行「全鏈增值」
        quad_map = meta_config.get('quad_correlation_map', {})
        if quad_map:
            chain_boosted = scores.copy()
            # 獲取前三名號碼 (Top 3)
            top_3 = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:3]
            if len(top_3) >= 3:
                # 檢查所有三元子集，看是否有對應的四元鏈路
                for trio_combo in combinations([t[0] for t in top_3], 3):
                    trio = tuple(sorted(trio_combo))
                    if trio in quad_map:
                        for quad_num, count in quad_map[trio].items():
                            # 四元增益最具侵略性，目標是直接轉化 Match 2 為 Match 4
                            boost = count * 1.5 
                            chain_boosted[quad_num] += boost
            scores = chain_boosted

        # 🧬 5. 熵值過濾 (Option 5: Sequence Adversary)
        # ✨ Phase 2: 利用熵值檢測號碼的「物理合理性」
        # 對於過於聚集或過於稀疏的號碼進行適度權重懲罰，確保整體分佈符合中等熵值規律
        for num in range(min_num, max_num + 1):
            # 簡單規則：如果該號碼與目前的高分號碼過於接近（連號 3 個以上），則降權
            top_3_anchors = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)[:3]
            for anchor in top_3_anchors:
                if abs(num - anchor) == 1:
                    scores[num] *= 0.85 # 懲罰過度稠密的連號
                elif abs(num - anchor) > 25:
                    scores[num] *= 0.95 # 適度懲罰過於孤立的號碼

        # 確保所有號碼都有分數
        for num in range(min_num, max_num + 1):
            if num not in scores:
                scores[num] = scores.get(num, 0) + 0.1

        return dict(scores)

    def _calculate_volatility(self, history: List[Dict], min_num: int, max_num: int) -> Dict[int, float]:
        """
        ✨ V3 穩定性優化：計算號碼變異係數 (CV)
        """
        windows = [20, 50, 100]
        num_volatility = {}
        for num in range(min_num, max_num + 1):
            freqs = []
            for w in windows:
                subset = history[:w]
                if not subset:
                    freqs.append(0)
                    continue
                count = sum(1 for d in subset if num in d['numbers'])
                freqs.append(count / len(subset))
            
            avg = sum(freqs) / len(freqs)
            if avg > 0:
                std = (sum((f - avg)**2 for f in freqs) / len(freqs))**0.5
                cv = std / avg
            else:
                cv = 1.0 # 高風險
            num_volatility[num] = cv
        return num_volatility

    def _get_reversal_candidates(self, history: List[Dict], min_num: int, max_num: int) -> List[int]:
        """
        ✨ V3 反轉保護：找出長期遺漏的冷號
        """
        omissions = {}
        for num in range(min_num, max_num + 1):
            last_seen = -1
            for i, draw in enumerate(history):
                if num in draw['numbers']:
                    last_seen = i
                    break
            omissions[num] = last_seen if last_seen != -1 else len(history)
            
        # 遺漏 > 20 期的列為反轉候選
        candidates = [n for n, o in omissions.items() if o >= 20]
        return sorted(candidates, key=lambda x: omissions[x], reverse=True)

    def _get_sum_biased_specials(self, predicted_sum: float) -> List[int]:
        """
        ✨ V2 跨區關聯優化：基於第一區總和回報第二區偏好號碼
        數據來源自 analyze_cross_section.py 物理特徵分析 (優化平衡版)
        """
        s = predicted_sum
        if s < 100: return [1, 2, 5, 8, 4]
        if 100 <= s < 110: return [2, 5, 8, 1, 3]
        if 110 <= s < 120: return [7, 1, 6, 2, 5]
        if 120 <= s < 130: return [2, 5, 8, 7, 4]
        if 130 <= s < 140: return [5, 3, 8, 2, 7]
        if 140 <= s < 155: return [2, 4, 3, 6, 8]
        if s >= 155: return [2, 6, 7, 3, 5]
        return [2, 5, 8, 1, 7]

    def _generate_cluster_pivot_bets(self, number_scores: Dict[int, float], 
                                     all_predictions: Dict,
                                     num_bets: int, pick_count: int, 
                                     lottery_rules: Dict,
                                     meta_config: Dict) -> Dict:
        """
        集群樞軸生成邏輯 (ClusterPivot)
        目標：鎖定最強錨點，對次要號碼進行分片採樣。
        """
        # 1. 取得排序後的號碼
        # ✨ V3: 波動率賦權 (Volatility Weighting)
        vol_map = meta_config.get('volatility_map', {})
        if vol_map:
            for num in number_scores:
                cv = vol_map.get(num, 0.5)
                # CV < 0.15 者增益 (穩定)，CV > 0.4 者減益 (雜訊)
                vol_weight = 1.0 + (0.15 - cv) * 0.5 
                vol_weight = max(0.7, min(1.3, vol_weight))
                number_scores[num] *= vol_weight

        sorted_nums = sorted(number_scores.items(), key=lambda x: x[1], reverse=True)
        top_nums = [n for n, s in sorted_nums]
        
        # 2. 鎖定錨點 (Anchors)
        #    - 預設: 取分數前 N 名
        #    - 可選: 透過 meta_config['forced_anchors'] 強制指定錨點
        anchor_count = meta_config.get('anchor_count', 2)
        forced_anchors = meta_config.get('forced_anchors')

        if forced_anchors:
            # 去重、轉型、過濾範圍
            min_num = lottery_rules.get('minNumber', lottery_rules.get('min_number', 1))
            max_num = lottery_rules.get('maxNumber', lottery_rules.get('max_number', 38))
            normalized = []
            for n in forced_anchors:
                try:
                    nn = int(n)
                except Exception:
                    continue
                if nn < min_num or nn > max_num:
                    continue
                if nn not in normalized:
                    normalized.append(nn)

            # ✨ V8: Consensus-Anchor Hybrid (混合權重)
            # 如果強制錨點的系統分數過低，自動混合 1 個最高分系統錨點以對抗風險
            forced_valid = normalized[:anchor_count]
            # 檢查強制錨點的平均排名
            avg_rank = sum([top_nums.index(n) if n in top_nums else 99 for n in forced_valid]) / len(forced_valid)

            # 🔍 V9: Consensus Alert (針對強制錨點的風險警示)
            if avg_rank > 20:
                logger.warning(f"⚠️ 高風險警告：強制錨點 {forced_valid} 的系統排名為 {avg_rank:.1f}，顯著偏離共識。")
            elif avg_rank > 10:
                logger.info(f"💡 策略提示：強制錨點 {forced_valid} 為中度風險組合 (排名 {avg_rank:.1f})。")

            if avg_rank > 15 and len(forced_valid) >= 2 and not meta_config.get('bypass_hybrid'):
                # 風險過高：混合 1 個系統 Top 1 + 1 個強制錨點
                anchors = [top_nums[0], forced_valid[0]]
            else:
                anchors = forced_valid
                
            if len(anchors) < anchor_count:
                fillers = [n for n in top_nums if n not in anchors]
                anchors.extend(fillers[: anchor_count - len(anchors)])
        else:
            anchors = top_nums[:anchor_count]
        
        # 3. 提取候選池 (Candidate Pool for the rest)
        slots_needed = pick_count - anchor_count
        
        # ✨ V7 優化：不僅依賴全局分數，還要依賴與「錨點」的強聯動
        trio_map = meta_config.get('trio_correlation_map', {})
        pair = tuple(sorted(anchors[:2])) if len(anchors) >= 2 else None
        
        # 獲取錨點的強力候選者 (基於三元組)
        anchor_companions = []
        if pair and pair in trio_map:
            # 取得與這組錨點最常出現的伴隨者
            companions = sorted(trio_map[pair].items(), key=lambda x: x[1], reverse=True)
            anchor_companions = [c[0] for c in companions if c[0] not in anchors]

        # 4. 特別號覆蓋 (Section-2 Round-Robin + Sum-Bias)
        # 如果規則有特別號且範圍獨立 (如威力彩 1-8)
        s_min = lottery_rules.get('specialMinNumber', lottery_rules.get('special_min_number', 1))
        s_max = lottery_rules.get('specialMaxNumber', lottery_rules.get('special_max_number', 8))
        
        # 簡單頻率投票選出候選人
        special_scores = defaultdict(float)
        for name, data in all_predictions.items():
            if 'special' in data:
                special_scores[data['special']] += data.get('confidence', 0.5)
        
        sorted_specials = sorted(special_scores.items(), key=lambda x: x[1], reverse=True)
        vote_specials = [s for s, _ in sorted_specials]

        # ✨ V2 優化：加入跨區總和偏差 (Sum-Bias)
        # 計算初步生成的錨點與伴隨號碼的平均總和預期值
        pred_sum = sum(anchors) + (sum(anchor_companions[:slots_needed]) if anchor_companions else 0)
        sum_biased_specials = self._get_sum_biased_specials(pred_sum)
        
        # 合併優先級：Sum-Bias > 共識投票 > 剩餘填補
        all_specials = []
        # 1. 優先加入 Sum-Bias (威力彩 1-8)
        for s in sum_biased_specials:
            if s not in all_specials: all_specials.append(s)
        # 2. 加入共識投票
        for s in vote_specials:
            if s not in all_specials: all_specials.append(s)
        # 3. 補足其餘
        for s in range(s_min, s_max + 1):
            if s not in all_specials: all_specials.append(s)

        bets = []
        for i in range(num_bets):
            current_pool_slice = []
            
            # 優先分配強聯動伴隨者給前幾注
            if i < 2 and anchor_companions:
                # 第一、二注分配最強伴隨者
                comp_start = i * slots_needed
                current_pool_slice = anchor_companions[comp_start : comp_start + slots_needed]

            # ✨ V4: Zone Balancing (區域平衡)
            # 確保補位號碼均勻分佈在不同區域 (1-13, 14-26, 27-38)
            if len(current_pool_slice) < slots_needed:
                needed = slots_needed - len(current_pool_slice)
                zones = [range(1, 14), range(14, 27), range(27, 39)]
                
                # 準備候選區 (按分數排序)
                potential_fillers = [n for n in top_nums if n not in anchors and n not in current_pool_slice]
                zone_fillers = {z: [n for n in potential_fillers if n in z] for z in zones}
                
                # 循環從各區抓取
                while len(current_pool_slice) < slots_needed:
                    found_any = False
                    for z in zones:
                        if zone_fillers[z]:
                            current_pool_slice.append(zone_fillers[z].pop(0))
                            found_any = True
                            if len(current_pool_slice) >= slots_needed: break
                    if not found_any: break
            
            bet_numbers = sorted(anchors + current_pool_slice[:slots_needed])
            
            # ✨ V3: 反轉保護 (Reversal Protection)
            # 在最後一注嘗試插入一個高機率反轉的冷號
            reversal_cands = meta_config.get('reversal_candidates', [])
            if i == num_bets - 1 and reversal_cands:
                # 如果這注還沒包含最強冷號，替換一個非錨點號碼
                rev_num = reversal_cands[0]
                if rev_num not in bet_numbers:
                    # 替換掉除錨點外的最後一個號碼
                    non_anchors = [n for n in bet_numbers if n not in anchors]
                    if non_anchors:
                        bet_numbers.remove(non_anchors[-1])
                        bet_numbers.append(rev_num)
                        bet_numbers.sort()

            # 分配特別號 (Round-Robin)
            special_num = all_specials[i % len(all_specials)]
            
            bets.append({
                'numbers': bet_numbers,
                'special': int(special_num),
                'source': f'cluster_pivot_v7_{i+1}',
                'group': 'consensus_pivot'
            })
            
        return {
            'bets': bets,
            'summary': {
                'anchors': anchors,
                'companions': anchor_companions[:12],
                'specials': all_specials[:num_bets],
                'method': 'cluster_pivot_v7'
            }
        }

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

    def _generate_skewed_bet(self, draws: List[Dict], lottery_rules: Dict, number_scores: Dict[int, float]) -> Dict:
        """
        生成偏態策略注 (Skewed Bet) - 專門捕捉尾部風險 (Tail Risks)
        例如：極端大號、極端連號、極端冷號
        """
        pick_count = lottery_rules.get('pickCount', 6)
        
        # 1. 策略選擇：這次我們專攻 "High-Value Cluster" (大數群聚)
        # 因為 115000002 期就是大數群聚，根據均值回歸，雖然下期看好小數
        # 但為了"保險" (Insurance)，我們還是生成一注大數偏態，或者一注"極端小數"
        
        sorted_nums = sorted(number_scores.items(), key=lambda x: x[1], reverse=True)
        top_30 = [n for n, s in sorted_nums[:30]]
        
        # 嘗試生成一個 "不平衡" 的組合 (Zone Focus)
        target_zone = random.randint(1, 3) # 1: Low, 2: Mid, 3: High
        zone_nums = []
        if target_zone == 1:
            zone_nums = [n for n in top_30 if n <= 17]
        elif target_zone == 2:
            zone_nums = [n for n in top_30 if 17 < n <= 34]
        else:
            zone_nums = [n for n in top_30 if n > 34]
            
        if len(zone_nums) < 4:
            zone_nums = top_30 # fallback
            
        # 從選定區間選 4-5 個，剩下的隨機補
        selected = random.sample(zone_nums, min(len(zone_nums), pick_count - 1))
        
        # 補足
        while len(selected) < pick_count:
            n = random.choice(top_30)
            if n not in selected:
                selected.append(n)
        
        return {
            'numbers': sorted(selected),
            'source': 'skewed_insurance_bet',
            'group': 'contrarian'
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
