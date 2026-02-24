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
from .regime_detector import RegimeDetector
from .zone_cluster import ZoneClusterRefiner
from .gap_manager import AdaptiveGapManager
from scipy.fft import fft, fftfreq
import random



# Phase 1: Import configuration loader for consecutive filter settings
try:
    from ..config_loader import get_consecutive_penalty, get_strategy_weight, get_diversity_lambda
    CONFIG_AVAILABLE = True
except ImportError:
    CONFIG_AVAILABLE = False
    # Fallback: use default values if config not available
    def get_consecutive_penalty(count):
        # Old hard penalty system
        return 300 if count >= 3 else 0
    def get_strategy_weight(name):
        return 1.0
    def get_diversity_lambda():
        return 0.5

logger = logging.getLogger(__name__)


class MultiBetOptimizer:
    """多注覆蓋優化器"""

    def __init__(self):
        self.name = "MultiBetOptimizer"
        self._load_strategies()
        self.wobble_opt = WobbleOptimizer()
        self.regime_detector = RegimeDetector()
        self.gap_manager = AdaptiveGapManager()
        self.roi_predictor = None # Lazy init for Phase 51
        self.zone_refiner = ZoneClusterRefiner({'maxNumber': 38}) # Default for PowerLotto

    def _load_strategies(self):
        """載入策略"""
        from .unified_predictor import prediction_engine
        from .enhanced_predictor import EnhancedPredictor
        from .gap_predictor import GapAnalysisPredictor, ConsensusPredictor
        from .anti_consensus_predictor import AntiConsensusPredictor, HighValuePredictor
        from .anomaly_predictor import AnomalyPredictor, EnhancedAnomalyPredictor

        self.enhanced = EnhancedPredictor()
        self.engine = prediction_engine
        self.gap_predictor = GapAnalysisPredictor()
        self.consensus_predictor = ConsensusPredictor()
        self.anti_consensus = AntiConsensusPredictor()
        self.high_value = HighValuePredictor()
        
        # Phase 2: Anomaly Predictor
        self.anomaly_predictor = AnomalyPredictor()
        self.enhanced_anomaly = EnhancedAnomalyPredictor(n_models=3)

        # 定義策略池，按多樣性分組 (P0+P1 優化)
        # 2026-01-03 P0優化: 加入馬可夫鏈、大間隔策略、低和值策略
        self.strategy_groups = {
            'frequency_based': [
                ('hot_cold_mix', lambda h, r: self.engine.hot_cold_mix_predict(h, r), 100),
                ('trend_predict', lambda h, r: self.engine.trend_predict(h, r), 300),
            ],
            'statistical': [
                ('statistical', lambda h, r: self.engine.statistical_predict(h, r), 400),
                ('deviation', lambda h, r: self.engine.deviation_predict(h, r), 500),
                ('zone_balance', lambda h, r: self.engine.zone_balance_predict(h, r), 500),
                ('sum_range', lambda h, r: self.engine.sum_range_predict(h, r), 100),
                ('odd_even', lambda h, r: self.engine.odd_even_balance_predict(h, r), 200),
            ],
            'probabilistic': [
                ('bayesian', lambda h, r: self.engine.bayesian_predict(h, r), 400),
                ('monte_carlo', lambda h, r: self.engine.monte_carlo_predict(h, r), 100),
                ('markov', lambda h, r: self.engine.markov_predict(h, r), 200),
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
            # Phase 2: Experimental / Anomaly
            'experimental': [
                ('anomaly_detection', lambda h, r: self.anomaly_predictor.predict(h, r), 150),
                ('enhanced_anomaly', lambda h, r: self.enhanced_anomaly.predict(h, r), 200),
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
                ('gnn', lambda h, r: self.engine.gnn_predict(h, r), 500), # Phase 48
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
            ],
            # 🔄 Phase Failure Analysis 115000010: Lag & Clusters
            'reversion': [
                ('lag_reversion', lambda h, r: self.engine.lag_reversion_predict(h, r), 600), # 高權重抓回補
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

        # ✨ 數據標準化：確保進入的模型數據是從舊到新 (ASC)
        if draws and len(draws) > 1:
            # 獲取日期或序號進行比較 (使用 int 或 date 字串比較)
            first_val = str(draws[0].get('draw', '0'))
            last_val = str(draws[-1].get('draw', '0'))
            
            # 如果第一條比最後一條大 (且長度相同，或是年份較大)，則是 DESC
            # 更穩健的做法：比較日期字串 '2026-01-01' vs '2007-01-01'
            first_date = str(draws[0].get('date', '0'))
            last_date = str(draws[-1].get('date', '0'))
            
            if first_date > last_date:
                # 是 DESC (Newest -> Oldest)，翻轉為 ASC
                draws = list(reversed(draws))
                logger.debug(f"🔄 MultiBetOptimizer: History reversed from DESC to ASC.")

        # 收集所有策略的預測結果
        all_predictions = {}
        strategy_whitelist = meta_config.get('strategy_whitelist') if meta_config else None
        
        for group_name, strategies in self.strategy_groups.items():
            for name, func, window in strategies:
                # ✨ 新增：策略白名單過濾 (Option 1 精簡)
                if strategy_whitelist and name not in strategy_whitelist:
                    continue
                    
                try:
                    history = draws[-window:] if len(draws) >= window else draws
                    result = func(history, lottery_rules)
                    all_predictions[name] = {
                        'numbers': set(result['numbers']),
                        'group': group_name,
                        'confidence': result.get('confidence', 0.5),
                        'probabilities': result.get('probabilities', []) # Phase 48
                    }
                except Exception as e:
                    continue

        # 0. 偵測當前環境機制 (Order/Chaos) - Phase 48
        regime = 'GLOBAL'
        if self.regime_detector:
            regime_info = self.regime_detector.detect_regime(draws)
            regime = regime_info.get('regime', 'GLOBAL')
            meta_config = meta_config or {}
            meta_config['regime'] = regime
            meta_config['regime_info'] = regime_info

        # 1. 計算號碼綜合分數 (傳遞 meta_config 以支持對子增益與 GNN 加權)
        number_scores = self._calculate_number_scores(all_predictions, min_num, max_num, meta_config, draws=draws)

        # 2. 生成多注組合
        bets = []
        used_combos = set()
        meta_config = meta_config or {}

        if ('POWER_LOTTO' in lottery_rules.get('name', '') or '威力彩' in lottery_rules.get('name', '')):
            # ROI Stacking 2-bet (Phase 51: Focus on Momentum + Entropy + Lag)
            if num_bets <= 2 and meta_config.get('method') == 'roi_stacking':
                from .optimized_ensemble import OptimizedEnsemblePredictor
                if self.roi_predictor is None:
                    self.roi_predictor = OptimizedEnsemblePredictor(lottery_rules)
                
                roi_result = self.roi_predictor.predict(draws, n_bets=num_bets)
                bets = []
                for b_nums in roi_result['all_bets']:
                    bets.append({'numbers': b_nums, 'source': 'roi_stacked_mel'})
                
                # Phase 58: ROI-Optimized Special Number Selection
                main_nums = bets[0]['numbers'] if bets else None
                specials = self._predict_multiple_specials(draws, lottery_rules, num_bets, main_numbers=main_nums)
                return {
                    'bets': bets,
                    'specials': specials,
                    'coverage': len(set(n for b in bets for n in b['numbers'])) / max_num,
                    'method': 'ROI_Stacked_Ensemble'
                }

            if num_bets >= 1 and num_bets <= 2 and meta_config.get('high_precision'):
                return self.generate_high_precision_2bets(draws, lottery_rules, number_scores, num_bets)
            
            # Meta-Stacking 2.0 (Phase 54: MLP Fusion)
            if num_bets <= 2 and meta_config.get('method') == 'meta_stacking':
                stacker_res = self.engine.meta_stacking_predict(draws, lottery_rules)
                bets = [{'numbers': stacker_res['numbers'], 'source': 'meta_stacking_deep'}]
                # If 2nd bet needed, use smart wobble on the stacker result
                if num_bets == 2:
                    self.wobble_opt.set_history(draws)
                    wobble_bets = self.wobble_opt.smart_wobble(stacker_res['numbers'], num_bets=1)
                    bets.append({'numbers': wobble_bets[0], 'source': 'meta_stacking_wobble'})
                
                # Phase 58: ROI-Optimized Special Number Selection
                main_nums = bets[0]['numbers'] if bets else None
                specials = self._predict_multiple_specials(draws, lottery_rules, num_bets, main_numbers=main_nums)
                return {
                    'bets': bets,
                    'specials': specials,
                    'method': 'Meta_Stacking_2.0'
                }

            # Diffusion Generative (Phase 56: DDPM Sampling)
            if num_bets <= 2 and meta_config.get('method') == 'diffusion':
                # Generate 2 independent tickets via diffusion
                bets = []
                for i in range(num_bets):
                    d_res = self.engine.diffusion_predict(draws, lottery_rules)
                    bets.append({'numbers': d_res['numbers'], 'source': f'diffusion_sample_{i+1}'})
                
                # Phase 58: ROI-Optimized Special Number Selection
                main_nums = bets[0]['numbers'] if bets else None
                specials = self._predict_multiple_specials(draws, lottery_rules, num_bets, main_numbers=main_nums)
                return {
                    'bets': bets,
                    'specials': specials,
                    'method': 'Diffusion_Generative'
                }

            # Default to Orthogonal Ensemble for Power Lotto 2-bet
            if num_bets == 3:
                 return self.generate_orthogonal_strategy_3bets(draws, lottery_rules, number_scores)
            
            # Phase 48: 允許多注 (5注以上) 使用主體多樣化邏輯
            if num_bets >= 2 and num_bets <= 4 and (not meta_config or meta_config.get('method') != 'cluster_pivot'):
                return self.generate_power_dual_max_bets(draws, lottery_rules, number_scores, num_bets)

        if meta_config.get('method') == 'cluster_pivot':
            # ✨ V3: 注入穩定性數據 (Resilience)
            if meta_config.get('resilience', False):
                meta_config['volatility_map'] = self._calculate_volatility(draws, min_num, max_num)
                meta_config['reversal_candidates'] = self._get_reversal_candidates(draws, min_num, max_num)
            
            return self._generate_cluster_pivot_bets(number_scores, all_predictions, num_bets, pick_count, lottery_rules, meta_config)
            
        # ✨ Phase 8/Optim: Orthogonal 3-bet (Now supporting Power & Big Lotto)
        if num_bets == 3:
             return self.generate_orthogonal_strategy_3bets(draws, lottery_rules, number_scores)

        is_big_lotto = lottery_rules.get('name', '') == 'BIG_LOTTO' or lottery_rules.get('maxNumber', 49) == 49
        
        # ✨ Phase 3: Set default diversity parameters for Big Lotto
        default_wobble = 0.0 if is_big_lotto else 0.2
        wobble_ratio = meta_config.get('wobble_ratio', default_wobble) 
        num_wobble = int(num_bets * wobble_ratio)
        num_base = num_bets - num_wobble
        
        if meta_config.get('skewed_mode') is None and is_big_lotto:
            meta_config['skewed_mode'] = True
            
        if meta_config.get('diversity_lambda') is None:
            # For Big Lotto, use a stronger default. For Power Lotto, allow more overlap for clustering.
            meta_config['diversity_lambda'] = 0.9 if is_big_lotto else 0.4
            lambda_val = meta_config['diversity_lambda']

        # 策略1: 基礎策略 (選分組中第一名或指定的策略)
        base_strategy_name = meta_config.get('base_strategy', 'top_score')
        
        # 排序策略 (依據信心度或指定名稱)
        # Phase 2/3 Step: 使用 MAB 權重調整信心度 (如果 MAB 已開啟)
        mab_stats = None
        if hasattr(self.engine, 'mab_predictor') and self.engine.mab_predictor:
            mab_stats = self.engine.mab_predictor.mab.get_statistics()
            
        # 準備基礎注
        available_strategies = []
        for group_name, strategies in self.strategy_groups.items():
            for name, _, _ in strategies:
                if name in all_predictions:
                    conf = all_predictions[name]['confidence']
                    
                    # 🚀 Phase 3/48 優化：如果 MAB 有該策略的統計，乘以特定 Regime 的 MAB 權重
                    if mab_stats and regime in mab_stats['regimes'] and name in mab_stats['regimes'][regime]:
                        mab_weight = mab_stats['regimes'][regime][name]['expected_weight']
                        conf = 0.7 * (mab_weight * 2.0) + 0.3 * conf
                    
                    # ✨ Phase 48: 強制提升 GNN 的重要性
                    if name == 'gnn':
                        conf = 9.9 
                    
                    available_strategies.append((name, group_name, conf))

        # 降序排列，GNN 因為 conf=9.9 會排第一
        available_strategies.sort(key=lambda x: -x[2])

        # 填注 1: 基礎多樣性注 (Iterative Diversity Selection)
        kill_set = set(meta_config.get('kill_list', []))
        top_nums = [n for n, s in sorted(number_scores.items(), key=lambda x: x[1], reverse=True)]
        
        # Phase 3: Iterative Selection with Overlap Penalty
        lambda_val = meta_config.get('diversity_lambda')
        if lambda_val is None:
            lambda_val = get_diversity_lambda()
        
        while len(bets) < num_base and available_strategies:
            # 1. Sort available strategies by current adjusted confidence
            available_strategies.sort(key=lambda x: -x[2])
            
            # 2. Pick the best remaining strategy
            name, group_name, current_conf = available_strategies.pop(0)
            
            raw_numbers = all_predictions[name]['numbers']
            safe_numbers = [n for n in raw_numbers if n not in kill_set]
            
            # Fill if needed
            if len(safe_numbers) < pick_count:
                fillers = [n for n in top_nums if n not in safe_numbers and n not in kill_set]
                safe_numbers.extend(fillers[:pick_count - len(safe_numbers)])
            
            bet = sorted(safe_numbers[:pick_count])
            
            if tuple(bet) not in used_combos:
                bets.append({
                    'numbers': bet,
                    'source': name,
                    'group': group_name
                })
                used_combos.add(tuple(bet))
                
                # 3. Apply Multi-Armed Penalty for Overlap to REMAINING strategies
                new_available = []
                for s_name, s_group, s_conf in available_strategies:
                    s_numbers = all_predictions[s_name]['numbers']
                    overlap_size = len(set(bet) & s_numbers)
                    overlap_ratio = overlap_size / pick_count
                    
                    # Penalty increases with overlap
                    # New_Conf = Old_Conf * (1 - Lambda * Ratio)
                    penalty_mult = 1.0 - (lambda_val * overlap_ratio)
                    new_conf = s_conf * penalty_mult
                    
                    new_available.append((s_name, s_group, new_conf))
                
                available_strategies = new_available

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
                
                # ✨ P3 整合: 確保擾動變體也避開殺號
                safe_variant = [n for n in variant if n not in kill_set]
                if len(safe_variant) < pick_count:
                    fillers = [n for n in top_nums if n not in safe_variant and n not in kill_set]
                    safe_variant.extend(fillers[:pick_count - len(safe_variant)])
                    
                variant = sorted(safe_variant[:pick_count])

                if tuple(variant) not in used_combos:
                    bets.append({
                        'numbers': variant,
                        'source': f'wobble_{wobble_method}({bets[0]["source"]})'
                    })
                    used_combos.add(tuple(variant))

        # 應用區間斷層修正 (Zone Gap Correction)
        bets = self._apply_zone_gap_correction(bets, draws, lottery_rules, meta_config)

        # 🕸️ Phase 48: 應用 GNN 協同優化 (GNN Synergy)
        # 對於 5 注以上的組合，強制加入一注 GNN 補位注以確保覆蓋邊緣高機率區
        force_synergy = (num_bets >= 5)
        bets = self._apply_gnn_synergy(bets, all_predictions, num_bets, lottery_rules, force=force_synergy)

        # ✨ P3優化 (Design Review 115000002) -> P0 (2026-01-12): 
        # 檢討會議目標：將「前區密集」與「後區密集」列為固定必選的保險注項。
        if meta_config.get('skewed_mode', False) and len(bets) >= 2:
            # 1. 前區密集保險 (Front Dense)
            skewed_front = self._generate_skewed_bet(draws, lottery_rules, number_scores, target_zone=1)
            # 2. 後區密集保險 (Back Dense)
            skewed_back = self._generate_skewed_bet(draws, lottery_rules, number_scores, target_zone=3)
            
            if len(bets) >= 4:
                # 替換最後兩注
                bets[-2] = skewed_front
                bets[-1] = skewed_back
                logger.info(f"🔄 Skewed Mode (P0): Added Front-Dense and Back-Dense insurance bets.")
            else:
                # 如果注數不足 4 注，則替換最後一注 (隨機選一個偏態)
                bets[-1] = random.choice([skewed_front, skewed_back])
                logger.info(f"🔄 Skewed Mode: Added single insurance bet due to low bet count.")

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

    def _apply_zone_gap_correction(self, bets: List[Dict], draws: List[Dict], lottery_rules: Dict, meta_config: Dict = None) -> List[Dict]:
        """
        區間斷層修正：識別長期未開出的區塊並在多注中進行補強
        """
        if not draws or not bets:
            return bets
            
        pick_count = lottery_rules.get('pickCount', 6)
        min_num = lottery_rules.get('minNumber', 1)
        max_num = lottery_rules.get('maxNumber', 49)
        kill_set = set(meta_config.get('kill_list', [])) if meta_config else set()
        
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
            # 修正最後一注
            target_bet = bets[-1]
            # 找到冷門區塊中歷史頻率較高的號碼，且不在殺號清單中
            all_nums_in_zone = [n for n in range(z_min, z_max + 1) if n not in kill_set]
            if all_nums_in_zone:
                new_num = random.choice(all_nums_in_zone)
                if new_num not in target_bet['numbers']:
                    # 替換最後一個號碼 (假設最後一個是非核心號)
                    target_bet['numbers'][-1] = new_num 
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
                                     number_scores: Dict[int, float], num_bets: int = 2, 
                                     cluster_override: int = None) -> Dict:
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
        
        # ✨ V6 Scaled: 針對 49 碼的最優集群大小 (Benchmark Phase 10 Result: 15 > 18)
        # 15碼的密度最高，在 50 期測試中達到 10% 勝率 (vs 18碼的 8%)
        cluster_size = 15 # Universal optimized size for both lotteries (approx 30-40% coverage)
             
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
    def _get_lukewarm_candidates(self, draws: List[Dict], min_num: int, max_num: int) -> List[int]:
        """
        獲取「溫號」(Lukewarm Numbers) 候選清單
        定義：遺漏期數在 8-18 期之間的號碼，歷史證明這類號碼最容易被熱號/冷號模型同時忽略。
        """
        if len(draws) < 20: return []
        
        last_seen = {}
        for i, d in enumerate(draws):
            for n in d['numbers']:
                if n not in last_seen:
                    last_seen[n] = i
        
        lukewarm = []
        for n in range(min_num, max_num + 1):
            gap = last_seen.get(n, 999)
            if 8 <= gap <= 18:
                lukewarm.append(n)
        
        return lukewarm

    def generate_orthogonal_strategy_3bets(self, draws: List[Dict], lottery_rules: Dict, number_scores: Dict[int, float]) -> Dict:
        """
        🚀 Phase Fail-Analysis Optim: Orthogonal Strategy 3-Bet
        針對 115000011 期檢討提出的「正交多樣化」策略：
        Bet 1: Balanced (均衡流) - 基於 Entropy，確保全域覆蓋
        Bet 2: Cluster (集群流) - 基於 Momentum，抓取連號/重號慣性
        Bet 3: Recovery (回補流) - 基於 Gap，抓取長遺漏回歸 + 溫號補強
        """
        pick_count = lottery_rules.get('pickCount', 6)
        min_num = lottery_rules.get('minNumber', 1)
        max_num = lottery_rules.get('maxNumber', 38 if 'POWER' in lottery_rules.get('name', '') else 49)
        
        # 0. 偵測是否處於極端切換期 (Extreme Transition)
        regime_info = self.regime_detector.detect_regime(draws)
        is_extreme = regime_info['regime'] == 'TRANSITION' or regime_info.get('symmetry_score', 0) > 0.6
        
        # 1. Bet 1: Balanced (Entropy-based)
        balanced_res = self.engine.entropy_predict(draws, lottery_rules, boost_z4=is_extreme)
        bet1 = sorted(balanced_res['numbers'])
        
        # 2. Bet 2: Cluster (Momentum-based)
        momentum_res = self.engine.trend_predict(draws, lottery_rules)
        bet2_pool = momentum_res['numbers']
        bet2 = self._select_orthogonal_set(bet2_pool, bet1, pick_count)
        
        # 3. Bet 3: Recovery (Gap-based) + Lukewarm Detector
        gap_res = self.engine.lag_reversion_predict(draws, lottery_rules, boost_cold=is_extreme)
        recovery_pool = gap_res['numbers']
        
        # ✨ 優化：強制注入溫號 (Lukewarm) 清單
        lukewarm_nums = self._get_lukewarm_candidates(draws, min_num, max_num)
        if lukewarm_nums:
            # 排除已出現在 Bet 1, Bet 2 的號碼
            extra_lukewarm = [n for n in lukewarm_nums if n not in bet1 and n not in bet2]
            if extra_lukewarm:
                # 根據 number_scores 排序溫號
                extra_lukewarm.sort(key=lambda x: number_scores.get(x, 0), reverse=True)
                # 注入前 3 名最有潛力的溫號
                recovery_pool = extra_lukewarm[:3] + [n for n in recovery_pool if n not in extra_lukewarm]
        
        # 確保與 Bet 1, Bet 2 的正交性
        bet3 = self._select_orthogonal_set(recovery_pool, bet1 + bet2, pick_count)
        
        # 🛡️ 安全補足：確保一定有 6 個號碼
        if len(bet3) < pick_count:
            fill_pool = [n for n in range(min_num, max_num + 1) if n not in bet1 and n not in bet2 and n not in bet3]
            bet3.extend(random.sample(fill_pool, pick_count - len(bet3)))
            bet3.sort()
        
        # 特別號 (如果有)
        specials = self._predict_multiple_specials(draws, lottery_rules, 3) if lottery_rules.get('hasSpecialNumber', False) else None
        
        bets = [
            {'numbers': bet1, 'source': 'orthogonal_balanced_entropy' + ('_extreme' if is_extreme else ''), 'special': specials[0] if specials else None},
            {'numbers': bet2, 'source': 'orthogonal_cluster_momentum', 'special': specials[1] if specials else None},
            {'numbers': bet3, 'source': 'orthogonal_recovery_gap_lukewarm', 'special': specials[2] if specials else None}
        ]
        
        # ✨ Phase Stability Audit: Add Zone Gap Correction
        bets = self._apply_zone_gap_correction(bets, draws, lottery_rules)
        
        result = {
            'bets': bets,
            'method': 'orthogonal_strategy_3bet_v3',
            'is_extreme_alert': is_extreme,
            'regime': regime_info['regime'],
            'symmetry_score': regime_info.get('symmetry_score', 0),
            'coverage': len(set(n for b in bets for n in b['numbers'])) / (max_num - min_num + 1)
        }
        
        return self.engine.auto_identify_stability(lottery_rules.get('name', ''), 'Orthogonal_3Bet', result)

    def generate_verified_ts3_plus_5bets(self, history: List[Dict], lottery_rules: Dict) -> Dict:
        """
        ★ Verified Production Strategy: TS3+ (Triple Strike Plus)
        Validated Results (1500p): +1.77% Edge (Deterministic)
        
        Exact Order (Critical for Orthogonality):
        1. Fourier Rhythm (TS3-B1) - Window: 500
        2. Cold Numbers (TS3-B2) - Window: 100
        3. Tail Balance (TS3-B3) - Window: 100
        4. Markov Order-1 (Orthogonal-B4) - Window: 30
        5. Frequency Orthogonal (Orthogonal-B5) - Window: 200
        """
        max_num = lottery_rules.get('maxNumber', 49)
        pick_count = lottery_rules.get('pickCount', 6)
        
        # Ensure chronological ascending order
        h_asc = sorted(history, key=lambda x: (x.get('date', ''), x.get('draw', 0)))
        
        # 1. Fourier Rhythm (注1)
        bet1 = self._ts3_fourier_bet(h_asc, max_num)
        
        # 2. Cold Numbers (注2)
        bet2 = self._ts3_cold_bet(h_asc, max_num, exclude=set(bet1))
        
        # 3. Tail Balance (注3)
        bet3 = self._ts3_tail_bet(h_asc, max_num, exclude=set(bet1) | set(bet2))
        
        # 4. Markov Order-1 (注4, w=30)
        used = set(bet1) | set(bet2) | set(bet3)
        bet4 = self._ts3_markov_order1_bet(h_asc, max_num, pick_count, window=30, exclude=used)
        
        # 5. Frequency Orthogonal (注5, w=200)
        used |= set(bet4)
        bet5 = self._ts3_freq_ortho_bet(h_asc, max_num, pick_count, window=200, exclude=used)
        
        all_bets = [bet1, bet2, bet3, bet4, bet5]
        sources = ['Fourier_Rhythm', 'Cold_Numbers', 'Tail_Balance', 'Markov_Order1', 'Freq_Orthogonal']
        
        all_covered = set()
        for b in all_bets:
            all_covered.update(b)
            
        return {
            'bets': [{'numbers': b, 'source': sources[i]} for i, b in enumerate(all_bets)],
            'method': 'verified_ts3_plus_5bet',
            'edge_expected': '+1.77%',
            'coverage': len(all_covered) / max_num,
            'unique_numbers': sorted(list(all_covered))
        }

    def _ts3_fourier_bet(self, history: List[Dict], max_num: int, window: int = 500) -> List[int]:
        """Strict TS3 Fourier Logic"""
        h_slice = history[-window:]
        w = len(h_slice)
        if w < 20: return sorted(random.sample(range(1, max_num + 1), 6))
        
        bitstreams = {i: np.zeros(w) for i in range(1, max_num + 1)}
        for idx, d in enumerate(h_slice):
            for n in d['numbers']:
                if n <= max_num: bitstreams[n][idx] = 1
        
        scores = np.zeros(max_num + 1)
        for n in range(1, max_num + 1):
            bh = bitstreams[n]
            if sum(bh) < 2: continue
            yf = fft(bh - np.mean(bh))
            xf = fftfreq(w, 1)
            idx_pos = np.where(xf > 0)
            pos_xf, pos_yf = xf[idx_pos], np.abs(yf[idx_pos])
            peak_idx = np.argmax(pos_yf)
            freq_val = pos_xf[peak_idx]
            if freq_val == 0: continue
            period = 1 / freq_val
            if 2 < period < w / 2:
                last_hit = np.where(bh == 1)[0][-1]
                gap = (w - 1) - last_hit
                scores[n] = 1.0 / (abs(gap - period) + 1.0)
        
        sorted_idx = np.argsort(scores[1:])[::-1] + 1
        return sorted(sorted_idx[:6].tolist())

    def _ts3_cold_bet(self, history: List[Dict], max_num: int, exclude: Set[int] = None) -> List[int]:
        """Strict TS3 Cold Numbers Logic (w=100)"""
        exclude = exclude or set()
        recent = history[-100:]
        all_nums = [n for d in recent for n in d['numbers']]
        freq = Counter(all_nums)
        candidates = [n for n in range(1, max_num + 1) if n not in exclude]
        sorted_cold = sorted(candidates, key=lambda x: freq.get(x, 0))
        return sorted(sorted_cold[:6])

    def _ts3_tail_bet(self, history: List[Dict], max_num: int, exclude: Set[int] = None) -> List[int]:
        """Strict TS3 Tail Balance Logic (w=100)"""
        exclude = exclude or set()
        recent = history[-100:]
        all_nums = [n for d in recent for n in d['numbers']]
        freq = Counter(all_nums)
        tail_groups = {i: [] for i in range(10)}
        for n in range(1, max_num + 1):
            if n not in exclude:
                tail_groups[n % 10].append((n, freq.get(n, 0)))
        for t in tail_groups:
            tail_groups[t].sort(key=lambda x: x[1], reverse=True)
        
        selected = []
        available_tails = sorted([t for t in range(10) if tail_groups[t]], 
                                key=lambda t: tail_groups[t][0][1] if tail_groups[t] else 0, reverse=True)
        idx_in_group = {t: 0 for t in range(10)}
        while len(selected) < 6:
            added = False
            for tail in available_tails:
                if len(selected) >= 6: break
                if idx_in_group[tail] < len(tail_groups[tail]):
                    num = tail_groups[tail][idx_in_group[tail]][0]
                    if num not in selected:
                        selected.append(num)
                        added = True
                    idx_in_group[tail] += 1
            if not added: break
        return sorted(selected[:6])

    def _ts3_markov_order1_bet(self, history: List[Dict], max_num: int, pick_count: int, window: int = 30, exclude: Set[int] = None) -> List[int]:
        """Strict Order-1 Markov Logic (w=30)"""
        exclude = exclude or set()
        recent = history[-window:]
        if len(history) < 2: return sorted([n for n in range(1, max_num + 1) if n not in exclude][:pick_count])
        
        transitions = Counter()
        for i in range(len(recent) - 1):
            prev_nums, next_nums = recent[i]['numbers'], recent[i+1]['numbers']
            for p in prev_nums:
                for n in next_nums: transitions[(p, n)] += 1
        
        last_nums = history[-1]['numbers']
        scores = Counter()
        for p in last_nums:
            for n in range(1, max_num + 1):
                if n not in exclude:
                    scores[n] += transitions.get((p, n), 0)
            
        candidates = sorted(scores.items(), key=lambda x: -x[1])
        res = [n for n, _ in candidates[:pick_count]]
        if len(res) < pick_count:
            remaining = [n for n in range(1, max_num + 1) if n not in exclude and n not in res]
            res.extend(remaining[:pick_count - len(res)])
        return sorted(res[:pick_count])

    def _ts3_freq_ortho_bet(self, history: List[Dict], max_num: int, pick_count: int, window: int = 200, exclude: Set[int] = None) -> List[int]:
        """Frequency Orthogonal Logic (w=200)"""
        exclude = exclude or set()
        all_nums = [n for d in history[-window:] for n in d['numbers']]
        freq = Counter(all_nums)
        candidates = [(n, freq.get(n, 0)) for n in range(1, max_num + 1) if n not in exclude]
        candidates.sort(key=lambda x: -x[1])
        res = [n for n, _ in candidates[:pick_count]]
        return sorted(res)

    def _detect_extreme_transition(self, draws: List[Dict]) -> bool:
        """
        偵測數據是否即將發生「極端相位切換」(Regime Shift)
        判斷指標：
        1. 最近 5 期總和持續低於均值 (累積壓力)
        2. 最近 5 期區域分佈嚴重失衡 (如 Z4 完全未出)
        """
        if len(draws) < 10: return False
        
        # 確保數據從舊到新排列以便切片
        ordered_draws = sorted(draws, key=lambda x: x.get('date', ''))
        recent_window = ordered_draws[-5:]
        
        # 1. 總和累積壓力 (Accumulated Sum Pressure)
        # Power Lotto 均值約 117
        recent_sums = [sum(d['numbers']) for d in recent_window]
        avg_sum = np.mean(recent_sums)
        if avg_sum < 100: # 如果連續多期偏小，預警大號爆發
            return True
            
        # 2. 區域壓縮 (Zonal Compression)
        # 如果 Z4 (31-38) 在最近 5 期幾乎沒出號
        z4_count = sum(1 for d in recent_window for n in d['numbers'] if n >= 31)
        if z4_count <= 1: # 壓力點
            return True
            
        return False

    def _select_orthogonal_set(self, pool: List[int], existing_numbers: List[int], count: int) -> List[int]:
        """從 pool 中選取與 existing_numbers 重合度最低的號碼組合"""
        existing_set = set(existing_numbers)
        # 優先選擇不在 existing_set 中的號碼
        orthogonal = [n for n in pool if n not in existing_set]
        if len(orthogonal) < count:
            # 補足以符合 pick_count
            fillers = [n for n in pool if n in existing_set]
            orthogonal.extend(fillers)
            
        return sorted(orthogonal[:count])


    def generate_tri_core_3bets(self, draws: List[Dict], lottery_rules: Dict, 
                              number_scores: Dict[int, float], num_bets: int = 3) -> Dict:
        """
        🚀 Phase 8: Tri-Core Orthogonal 3-bet Strategy
        
        Design Philosophy (Orthogonal Expansion):
        1. Bet 1 (Core): High-Precision Anchor (Consensus & Stability).
        2. Bet 2 (Shadow): Orthogonal Complement (Covering the Elite Shadow).
        3. Bet 3 (Gap/Risk): Reversal & Interval (Capturing high-volatility gaps).
        
        Target: 9-10% Success Rate (Match-3+) for Big Lotto.
        """
        pick_count = lottery_rules.get('pickCount', 6)
        min_num = lottery_rules.get('minNumber', 1)
        max_num = lottery_rules.get('maxNumber', 49)
        
        # 1. Get Scores (MTFF & Base)
        mtff_scores = self._get_mtff_scores(draws, lottery_rules)
        final_scores = defaultdict(float)
        volatility = self._calculate_volatility(draws[:100], min_num, max_num)
        
        for n in range(min_num, max_num + 1):
            s1 = number_scores.get(n, 0)
            s2 = mtff_scores.get(n, 0)
            # Slightly higher weighting on MTFF for stability
            final_scores[n] = 0.35 * s1 + 0.65 * s2
            
            # Dynamic Anchor Boosting (Big Lotto Context)
            # If low volatility (stable), boost score
            v = volatility.get(n, 1.0)
            if v < 0.2: # Very stable
                final_scores[n] *= 1.2
        
        sorted_nums = sorted(final_scores.items(), key=lambda x: x[1], reverse=True)
        
        # --- Bet 1: The Core (Top Tier Elite) ---
        # Cluster size expanded to 18 (proven in v6 for Big Lotto)
        core_cluster = [n for n, s in sorted_nums[:18]]
        
        # Use Entropy to pick best 6 from Top 18
        bet1 = self._select_best_entropy_set(core_cluster, 6, draws, final_scores)
        
        # --- Bet 2: The Shadow (Orthogonal Complement) ---
        # Pick from Rank 19-30 (The "Shadow" Elite)
        shadow_cluster = [n for n, s in sorted_nums[18:30]]
        
        # Ensure orthogonality: Strictly NO overlap with Bet 1
        shadow_candidates = [n for n in shadow_cluster if n not in bet1]
        
        # If we need filler 
        if len(shadow_candidates) < 6:
            remaining = [n for n, s in sorted_nums[30:40] if n not in bet1]
            shadow_candidates.extend(remaining)
            
        bet2 = self._select_best_entropy_set(shadow_candidates, 6, draws, final_scores)
        
        # --- Bet 3: The Gap/Risk (Reversal) ---
        reversal_candidates = self._get_reversal_candidates(draws, min_num, max_num)
        
        exclusion_set = set(bet1) | set(bet2)
        valid_reversals = [n for n in reversal_candidates if n not in exclusion_set]
        
        bet3 = []
        if len(valid_reversals) >= 3:
            bet3.extend(valid_reversals[:3])
        else:
            bet3.extend(valid_reversals)
            
        recent_hot = set()
        for d in draws[:10]:
            recent_hot.update(d['numbers'])
            
        high_energy = []
        for n in recent_hot:
            if n not in exclusion_set and n not in bet3:
                cv = volatility.get(n, 1.0)
                if cv > 0.5: 
                    high_energy.append(n)
        
        needed = 6 - len(bet3)
        if len(high_energy) >= needed:
            bet3.extend(random.sample(high_energy, needed))
        else:
            bet3.extend(high_energy)
            pool = [n for n in range(min_num, max_num + 1) if n not in exclusion_set and n not in bet3]
            if len(pool) >= 6 - len(bet3):
                bet3.extend(random.sample(pool, 6 - len(bet3)))
                
        bet3 = sorted(bet3)

        # Specials (Top 3)
        special_scores = Counter()
        for d in draws[:200]: 
            s = d.get('special')
            if s: special_scores[s] += 1
            
        top_specials = [s for s, c in special_scores.most_common(5)]
        # Random fallback if empty
        while len(top_specials) < 3:
            r = random.randint(1, 8 if not (max_num == 49) else 49) 
            if r not in top_specials: top_specials.append(r)

        final_bets = [
            {'numbers': sorted(bet1), 'special': top_specials[0] if not (max_num==49) else None, 'source': 'tri_core_1_core'},
            {'numbers': sorted(bet2), 'special': top_specials[1] if not (max_num==49) else None, 'source': 'tri_core_2_shadow'},
            {'numbers': sorted(bet3), 'special': top_specials[2] if not (max_num==49) else None, 'source': 'tri_core_3_gap'}
        ]

        return {
            'bets': final_bets[:num_bets],
            'method': 'tri_core_orthogonal',
            'elite_cluster': core_cluster,
            'shadow_cluster': shadow_cluster
        }

    def generate_coverage_max_3bets(self, draws: List[Dict], lottery_rules: Dict, 
                                 number_scores: Dict[int, float]) -> Dict:
        """
        🚀 Phase 9: Coverage-Maximizing Union Strategy (Expert Jury Revision)
        
        針對 115000014 期提出的「窮盡特徵與最高覆蓋」需求：
        1. 整合 AdaptiveGapManager 提供精確的冷號回補權重。
        2. 採用「梯度覆蓋」：Bet 1 攻勢(熱), Bet 2 守勢(溫), Bet 3 奇襲(冷/斷層)。
        3. 確保三注聯合覆蓋率達到理論最優。
        """
        pick_count = lottery_rules.get('pickCount', 6)
        min_num = lottery_rules.get('minNumber', 1)
        max_num = lottery_rules.get('maxNumber', 49)
        
        # 1. 取得環境機制與遺漏分析
        regime_info = self.regime_detector.detect_regime(draws)
        gap_analysis = self.gap_manager.analyze_gaps(draws, lottery_rules)
        
        # 2. 融合分數 (MTFF + Regime Weights + Gap Saturation)
        mtff_scores = self._get_mtff_scores(draws, lottery_rules)
        regime_weights = self.regime_detector.get_weight_adjustments(regime_info, lottery_rules.get('name', 'BIG_LOTTO'))
        
        final_scores = defaultdict(float)
        for n in range(min_num, max_num + 1):
            s_base = number_scores.get(n, 0)
            s_mtff = mtff_scores.get(n, 0)
            s_gap = gap_analysis[n]['rebound_score']
            
            # 動態權重分配 (規律期看 MTFF, 紊亂期看 Gap)
            if regime_info['regime'] == 'ORDER':
                final_scores[n] = 0.3 * s_base + 0.6 * s_mtff + 0.1 * s_gap
            elif regime_info['regime'] == 'CHAOS':
                final_scores[n] = 0.2 * s_base + 0.3 * s_mtff + 0.5 * s_gap
            else: # TRANSITION
                final_scores[n] = 0.35 * s_base + 0.35 * s_mtff + 0.3 * s_gap

        # --- Bet 1: The Vanguard (High-Confidence Momentum) ---
        # 專注於近期最熱與共識最高的集群
        vanguard_pool = sorted(final_scores.keys(), key=lambda x: final_scores[x], reverse=True)[:15]
        bet1 = self._select_best_entropy_set(vanguard_pool, pick_count, draws, final_scores)
        
        # --- Bet 2: The Sentinel (Structural Support & Coverage) ---
        # 選取不在 Bet 1 中的次優號碼，並優先考慮區間平衡
        sentinel_pool = [n for n in sorted(final_scores.keys(), key=lambda x: final_scores[x], reverse=True) 
                        if n not in bet1][:18]
        bet2 = self._select_best_entropy_set(sentinel_pool, pick_count, draws, final_scores)
        
        # --- Bet 3: The Ghost (Adaptive Gap Rebound & Anomaly) ---
        # 強制加入遺漏飽和度最高的號碼，並補足其他正交號碼
        ghost_pool = [n for n, s in sorted(gap_analysis.items(), key=lambda x: x[1]['rebound_score'], reverse=True) 
                     if n not in set(bet1) | set(bet2)][:12]
        
        # 確保覆蓋到至少 3 個最高飽和度的號碼
        bet3 = ghost_pool[:3]
        # 剩餘位置使用正交選取或其他高分號碼
        remaining_pool = [n for n in sorted(final_scores.keys(), key=lambda x: final_scores[x], reverse=True)
                         if n not in set(bet1) | set(bet2) | set(bet3)]
        bet3.extend(remaining_pool[:pick_count - len(bet3)])
        bet3 = sorted(bet3[:pick_count])
        
        # 3. 特別號優化
        specials = self._predict_multiple_specials(draws, lottery_rules, 3) if lottery_rules.get('hasSpecialNumber', False) else None
        
        bets = [
            {'numbers': bet1, 'source': 'coverage_max_vanguard', 'special': specials[0] if specials else None},
            {'numbers': bet2, 'source': 'coverage_max_sentinel', 'special': specials[1] if specials else None},
            {'numbers': bet3, 'source': 'coverage_max_ghost', 'special': specials[2] if specials else None}
        ]
        
        # 4. 進行最後的空間斷層修正
        bets = self._apply_zone_gap_correction(bets, draws, lottery_rules)
        
        all_covered = set().union(*[set(b['numbers']) for b in bets])
        
        return {
            'bets': bets,
            'method': 'coverage_max_union_v9',
            'regime': regime_info['regime'],
            'coverage': len(all_covered) / (max_num - min_num + 1),
            'unique_numbers': sorted(list(all_covered))
        }

    def generate_orthogonal_5bets(self, draws: List[Dict], lottery_rules: Dict, 
                                 number_scores: Dict[int, float]) -> Dict:
        """
        🚀 Phase 10: Orthogonal 5-Bet Expansion (Penta-Stream Strategy)
        
        與 3-bet 相比，5-bet 版本增加了「反共識」與「節奏分析」串流。
        1. Bet 1: Balanced (Entropy)
        2. Bet 2: Cluster (Momentum)
        3. Bet 3: Recovery (Adaptive Gap Rebound)
        4. Bet 4: Anomaly (Anti-Consensus/Experimental)
        5. Bet 5: Rhythm (Fourier/Pattern-Aware)
        """
        pick_count = lottery_rules.get('pickCount', 6)
        min_num = lottery_rules.get('minNumber', 1)
        max_num = lottery_rules.get('maxNumber', 49)
        
        regime_info = self.regime_detector.detect_regime(draws)
        gap_analysis = self.gap_manager.analyze_gaps(draws, lottery_rules)
        
        # Stream 1: Balanced
        b1_res = self.engine.entropy_predict(draws, lottery_rules)
        bet1 = sorted(b1_res['numbers'])
        
        # Stream 2: Cluster
        b2_res = self.engine.trend_predict(draws, lottery_rules)
        bet2 = self._select_orthogonal_set(b2_res['numbers'], bet1, pick_count)
        
        # Stream 3: Recovery (Using Gap Manager)
        b3_pool = self.gap_manager.get_top_gaps(gap_analysis, count=12)
        bet3 = self._select_orthogonal_set(b3_pool, bet1 + bet2, pick_count)
        
        # Stream 4: Anomaly
        b4_res = self.anomaly_predictor.predict(draws, lottery_rules)
        bet4 = self._select_orthogonal_set(b4_res['numbers'], bet1 + bet2 + bet3, pick_count)
        
        # Stream 5: Rhythm
        try:
            from .fourier_rhythm import FourierRhythmPredictor
            fr = FourierRhythmPredictor(min_val=min_num, max_val=max_num)
            fr_scores = fr.predict_main_numbers(draws, max_num=max_num)
            b5_pool = sorted(fr_scores.keys(), key=lambda x: fr_scores[x], reverse=True)[:12]
        except:
            # Fallback to ensemble
            b5_res = self.engine.ensemble_predict(draws, lottery_rules)
            b5_pool = b5_res['numbers']
            
        bet5 = self._select_orthogonal_set(b5_pool, bet1 + bet2 + bet3 + bet4, pick_count)
        
        specials = self._predict_multiple_specials(draws, lottery_rules, 5) if lottery_rules.get('hasSpecialNumber', False) else None
        
        raw_bets = [bet1, bet2, bet3, bet4, bet5]
        sources = ['ortho_balanced', 'ortho_cluster', 'ortho_recovery', 'ortho_anomaly', 'ortho_rhythm']
        
        bets = []
        for i in range(5):
            bets.append({
                'numbers': raw_bets[i],
                'source': sources[i],
                'special': specials[i] if specials else None
            })
            
        # Apply correction
        bets = self._apply_zone_gap_correction(bets, draws, lottery_rules)
        
        all_covered = set().union(*[set(b['numbers']) for b in bets])
        
        return {
            'bets': bets,
            'method': 'orthogonal_5bet_v10',
            'coverage': len(all_covered) / (max_num - min_num + 1),
            'unique_numbers': sorted(list(all_covered))
        }

    def generate_optimized_5bets_v11(self, draws: List[Dict], lottery_rules: Dict, 
                                   number_scores: Dict[int, float]) -> Dict:
        """
        🚀 Phase 11: Optimized 5-Bet (Concentrated Orthogonal)
        
        策略升級：
        1. Bet 1 (Alpha): 超精準 MTFF 核心注，集中最高共識。
        2. Bet 2 (Beta): 次高共識 + 區域補強。
        3. Bet 3 (Gamma): 正交回補 (Gap Rebound)。
        4. Bet 4 (Delta): 正交極端 (Anomaly/Cold)。
        5. Bet 5 (Omega): 正交節奏 (Rhythm/Fourier)。
        
        目標：在不顯著大幅降低覆蓋率的情況下，將單注 3+ 命中率提升至 15%-20%。
        """
        pick_count = lottery_rules.get('pickCount', 6)
        min_num = lottery_rules.get('minNumber', 1)
        max_num = lottery_rules.get('maxNumber', 49)
        
        regime_info = self.regime_detector.detect_regime(draws)
        gap_analysis = self.gap_manager.analyze_gaps(draws, lottery_rules)
        mtff_scores = self._get_mtff_scores(draws, lottery_rules)
        
        # 融合權重 (依據 Regime)
        final_scores = defaultdict(float)
        for n in range(min_num, max_num + 1):
            s_mtff = mtff_scores.get(n, 0)
            s_gap = gap_analysis[n]['rebound_score']
            if regime_info['regime'] == 'ORDER':
                final_scores[n] = 0.7 * s_mtff + 0.3 * s_gap
            else:
                final_scores[n] = 0.4 * s_mtff + 0.6 * s_gap
        
        # --- Bet 1: Alpha Core (Concentrated) ---
        alpha_pool = sorted(final_scores.keys(), key=lambda x: final_scores[x], reverse=True)[:15]
        bet1 = self._select_best_entropy_set(alpha_pool, pick_count, draws, final_scores)
        
        # --- Bet 2: Beta Core (Slightly Overlap Allowed) ---
        # 允許與 Bet 1 有 1-2 個號碼重疊，以增加對核心高產區的打擊力
        beta_pool = sorted(final_scores.keys(), key=lambda x: final_scores[x], reverse=True)[:20]
        # 這裡不強求完全正交，但確保整體分佈平衡
        bet2 = self._select_best_entropy_set(beta_pool, pick_count, draws, final_scores)
        
        # --- Bet 3-5: Orthogonal Streams (Strict No Overlap with Bet 1/2) ---
        excluded = set(bet1) | set(bet2)
        
        # Bet 3: Gap Recovery
        b3_pool = [n for n, s in sorted(gap_analysis.items(), key=lambda x: x[1]['rebound_score'], reverse=True)
                  if n not in excluded][:15]
        bet3 = self._select_best_entropy_set(b3_pool, pick_count, draws, final_scores)
        
        # Bet 4: Anomaly/Cold
        excluded.update(bet3)
        b4_res = self.anomaly_predictor.predict(draws, lottery_rules)
        bet4 = self._select_orthogonal_set(b4_res['numbers'], list(excluded), pick_count)
        
        # Bet 5: Rhythm/Fourier
        excluded.update(bet4)
        try:
            from .fourier_rhythm import FourierRhythmPredictor
            fr = FourierRhythmPredictor(min_val=min_num, max_val=max_num)
            fr_scores = fr.predict_main_numbers(draws, max_num=max_num)
            b5_pool = [n for n in sorted(fr_scores.keys(), key=lambda x: fr_scores[x], reverse=True) if n not in excluded][:12]
        except:
            b5_pool = [n for n in range(min_num, max_num + 1) if n not in excluded]
            
        bet5 = self._select_orthogonal_set(b5_pool, list(excluded), pick_count)
        
        specials = self._predict_multiple_specials(draws, lottery_rules, 5) if lottery_rules.get('hasSpecialNumber', False) else None
        
        bets = [
            {'numbers': bet1, 'source': 'optimized_alpha', 'special': specials[0] if specials else None},
            {'numbers': bet2, 'source': 'optimized_beta', 'special': specials[1] if specials else None},
            {'numbers': bet3, 'source': 'optimized_gamma_gap', 'special': specials[2] if specials else None},
            {'numbers': bet4, 'source': 'optimized_delta_anomaly', 'special': specials[3] if specials else None},
            {'numbers': bet5, 'source': 'optimized_omega_rhythm', 'special': specials[4] if specials else None}
        ]
        
        all_covered = set().union(*[set(b['numbers']) for b in bets])
        
        return {
            'bets': bets,
            'method': 'concentrated_orthogonal_5bet_v11',
            'coverage': len(all_covered) / (max_num - min_num + 1),
            'unique_numbers': sorted(list(all_covered))
        }

    def _select_best_entropy_set(self, candidates: List[int], k: int, draws: List[Dict], scores: Dict[int, float], lock_pair: bool = False) -> List[int]:
        """
        Helper to pick best k numbers with Smart Filtering (v7)
        - lock_pair: If True, forces inclusion of the strongest historical pair within candidates.
        """
        if len(candidates) <= k:
            return sorted(candidates)
            
        # 1. Identify Lock Pair (if enabled)
        forced_pair = []
        if lock_pair and len(candidates) >= 2:
            pair_counts = Counter()
            c_set = set(candidates)
            for d in draws[:50]: # Look at recent 50 draws for pair trends
                nums = [n for n in d['numbers'] if n in c_set]
                if len(nums) >= 2:
                    for p in combinations(nums, 2):
                        pair_counts[p] += 1
            
            if pair_counts:
                best_pair = pair_counts.most_common(1)[0][0]
                forced_pair = list(best_pair)
        
        all_combs = list(combinations(candidates, k))
        
        # Soft Lock: Do NOT filter list. Just identify the pair for scoring.
        # if forced_pair:
        #      all_combs = [c for c in all_combs if all(p in c for p in forced_pair)]
        
        # Logically sample if still too many (but prioritized)
        if len(all_combs) > 200:
            all_combs = random.sample(all_combs, 200)
            
        best_comb = None
        max_score = -9999
        
        for comb in all_combs:
            # --- Smart Filters (Phase 9) ---
            # 1. Odd/Even Balance (Reject 6:0 / 0:6)
            odd_count = len([n for n in comb if n % 2 != 0])
            if odd_count == 0 or odd_count == k:
                # Soft reject: heavy penalty instead of continue, to allow recovery if signal is massive
                balance_penalty_override = 500
            else:
                balance_penalty_override = 0
                
            # 2. Sequential Limit - ✨ Phase 1 Improvement: Gradual Penalties
            # Instead of harsh 300 penalty for all 3+ consecutive, use configurable gradual system
            sorted_c = sorted(comb)
            consecutive_count = 0
            max_consecutive = 1
            
            # Count maximum consecutive sequence
            for i in range(len(sorted_c) - 1):
                if sorted_c[i+1] == sorted_c[i] + 1:
                    consecutive_count += 1
                    max_consecutive = max(max_consecutive, consecutive_count + 1)
                else:
                    consecutive_count = 0
            
            # --- Scoring ---
            # Base Score from Ranks
            rank_score = sum(scores.get(n, 0) for n in comb)
            
            # Balance Penalty (Ideal: 3:3 or 4:2)
            balance_penalty = abs(odd_count - k/2) * 0.2 + balance_penalty_override
            
            # ✨ Phase 1: Use gradual consecutive penalty from config
            if CONFIG_AVAILABLE and max_consecutive >= 2:
                # Get penalty multiplier from config (e.g., 0.7 for 2-consecutive, 0.4 for 3-consecutive)
                penalty_multiplier = get_consecutive_penalty(max_consecutive)
                if penalty_multiplier < 1.0:
                    # Apply as score multiplier (e.g., score * 0.4 for 3-consecutive)
                    rank_score *= penalty_multiplier
                elif penalty_multiplier > 1.0:
                    # Old-style hard penalty (backwards compatibility)
                    balance_penalty += penalty_multiplier
            else:
                # Fallback: old hard penalty system
                if max_consecutive >= 3:
                    balance_penalty += 300  # Heavy penalty for 3-consecutive
            
            # History penalty (exact match previous)
            hist_penalty = 0
            for d in draws[:10]:
                if set(d['numbers']) == set(comb):
                    hist_penalty = 100
                    break
            
            total = rank_score - balance_penalty - hist_penalty
            
            # Bonus for pair strength (The "Soft Lock")
            if forced_pair and all(p in comb for p in forced_pair):
                 total += 50.0  # Significant bonus to encourage inclusion effectively
                 
            if total > max_score:
                max_score = total
                best_comb = comb
        
        # Fallback if filters killed everything
        if best_comb is None:
             return sorted(list(random.choice(all_combs) if all_combs else candidates[:k]))
             
        return sorted(list(best_comb))

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
        
        # 1. 生成基礎注號碼 (回歸加權評分制，確保全域公平性)
        sorted_nums = sorted(number_scores.items(), key=lambda x: x[1], reverse=True)
        bet1_numbers = sorted([n for n, s in sorted_nums[:pick_count]])
        
        # 2. 生成擾動注號碼 (Smart Wobble)
        self.wobble_opt.set_history(draws)
        self.wobble_opt.min_num = min_num
        self.wobble_opt.max_num = max_num
        
        # 生成足夠的變體 (num_bets)
        wobble_variants = self.wobble_opt.smart_wobble(bet1_numbers, num_bets=num_bets, history=draws[:500])
        
        # 3. 預測特別號 (使用增強版動態預測)
        from .unified_predictor import predict_special_number
        
        top_specials = []
        # 第 1 注使用最強特殊號預測
        s1 = predict_special_number(draws, lottery_rules, bet1_numbers, strategy_name='lag')
        top_specials.append(s1)
        
        # 後續注項使用多樣化覆蓋
        all_s = list(range(1, 9))
        random.shuffle(all_s)
        for s in all_s:
            if len(top_specials) >= num_bets: break
            if s not in top_specials: top_specials.append(s)
        
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

        # 0.1 負向過濾 (Kill List Penalty) - P1 整合
        kill_list = meta_config.get('kill_list', [])
        if kill_list:
            for n in kill_list:
                scores[n] = -999.0 # 極大負權重，確保不被選中

        # 1. 基礎投票分數 (Option 1: Consensus)
        regime_info = meta_config.get('regime_info', {})
        regime_weights = {}
        if regime_info:
            regime_weights = self.regime_detector.get_weight_adjustments(regime_info)
            
        for name, data in predictions.items():
            confidence = data.get('confidence', 0.5)
            
            # 🚀 Apply Regime weights
            r_weight = regime_weights.get(name, 1.0)
            confidence *= r_weight
            
            # ✨ Phase 48: 獲取 GNN 原始機率
            if name == 'gnn' and 'probabilities' in data:
                probs = data['probabilities']
                regime = regime_info.get('regime', 'GLOBAL') if regime_info else 'GLOBAL'
                # 在 CHAOS 環境下，給予 GNN 更高的加權
                gnn_boost = 1.8 if regime == 'CHAOS' else 1.2
                for i, p in enumerate(probs):
                    num = i + min_num
                    scores[num] += p * confidence * gnn_boost
            
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
        kill_set = set(meta_config.get('kill_list', []))
        if pair and pair in trio_map:
            # 取得與這組錨點最常出現的伴隨者
            companions = sorted(trio_map[pair].items(), key=lambda x: x[1], reverse=True)
            anchor_companions = [c[0] for c in companions if c[0] not in anchors and c[0] not in kill_set]

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
            reversal_cands = [n for n in meta_config.get('reversal_candidates', []) if n not in kill_set]
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
                                   num_bets: int, main_numbers: List[int] = None) -> List[int]:
        """
        🚀 Phase 58: ROI-Optimized Special Number Prediction
        Uses PowerLottoSpecialPredictor (MAB/Regime/Fourier) instead of simple frequency.
        """
        lottery_name = lottery_rules.get('name', '')
        if 'POWER_LOTTO' in lottery_name or '威力彩' in lottery_name:
            from .special_predictor import PowerLottoSpecialPredictor
            predictor = PowerLottoSpecialPredictor(lottery_rules)
            # Use top_n which covers more probability space
            return predictor.predict_top_n(draws, n=num_bets, main_numbers=main_numbers)
        
        # Fallback for Big Lotto or others
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

    def generate_orthogonal_bets(self, draws: List[Dict], lottery_rules: Dict, 
                                 number_scores: Dict[int, float], num_bets: int = 2) -> Dict:
        """
        正交化集成預測 (Orthogonal Ensemble)
        目標：在 2 注場景下，最大化號碼覆蓋的正交性 (Orthogonality)。
        
        策略描述：
        1. 偵測環境機制 (Order/Chaos)。
        2. 獲取區域剪枝名單 (Zonal Pruning) 排除噪聲。
        3. Bet 1: 選擇當前機制下的最優共識號碼。
        4. Bet 2: 採用「貪婪正交選擇」，在保證評分前 15 名的前提下，選取與 Bet 1 重疊最少的組合。
        """
        pick_count = lottery_rules.get('pickCount', 6)
        min_num = lottery_rules.get('minNumber', 1)
        max_num = lottery_rules.get('maxNumber', 38)
        
        # 預防性檢查：如果 number_scores 為空，則先計算基礎分數
        if not number_scores:
            from .unified_predictor import UnifiedPredictionEngine
            engine = UnifiedPredictionEngine()
            ensemble_result = engine.ensemble_predict(draws, lottery_rules)
            # 將 ensemble_predict 輸出轉換為 _calculate_number_scores 需要的格式
            predictions = {
                'ensemble': {
                    'numbers': ensemble_result.get('numbers', []),
                    'confidence': ensemble_result.get('confidence', 0.5)
                }
            }
            number_scores = self._calculate_number_scores(predictions, min_num, max_num, {}, draws)

        # 1. 偵測環境
        regime_info = self.regime_detector.detect_regime(draws)
        regime = regime_info['regime']
        
        # 2. 獲取剪枝與加成名單
        self.zone_refiner.max_num = max_num
        self.zone_refiner.zone_size = max_num // 5
        number_scores = self.zone_refiner.refine(draws, number_scores)
        
        # 3. Bet 1: 共識王者 (精英池)
        sorted_nums = sorted(number_scores.items(), key=lambda x: x[1], reverse=True)
        # 精英候選池 (Top 12)
        elite_pool = [n for n, s in sorted_nums[:15]]
        
        # 使用熵值選擇第一注
        bet1 = self._select_best_entropy_set(elite_pool[:12], pick_count, draws, number_scores)
        
        # 4. Bet 2: 正交補償 (Orthogonal Complement)
        # 目標：在 Elite Pool 餘下的號碼中，選取與 Bet 1 重疊最少的 6 個號碼
        # 如果 Elite Pool 不夠，擴展到 Top 18
        extended_pool = [n for n, s in sorted_nums[:18]]
        
        # 貪婪尋找最佳正交注
        best_bet2 = None
        min_overlap = 7
        max_score = -1
        
        # 遍歷組合尋找
        candidates = [n for n in extended_pool if n not in bet1]
        # 如果非重疊號碼足夠 (>=6)
        if len(candidates) >= pick_count:
            # 在非重疊號碼中選最優
            best_bet2 = self._select_best_entropy_set(candidates, pick_count, draws, number_scores)
            min_overlap = 0
        else:
            # 如果不夠，允許少量重疊 (1-2個)
            all_cands = [n for n in extended_pool]
            # 隨機採樣評估
            for _ in range(100):
                comb = sorted(random.sample(all_cands, pick_count))
                overlap = len(set(comb) & set(bet1))
                score = sum(number_scores.get(n, 0) for n in comb)
                
                # 正交優先級：Overlap < 2 > Score
                if overlap < min_overlap:
                    min_overlap = overlap
                    max_score = score
                    best_bet2 = comb
                elif overlap == min_overlap and score > max_score:
                    max_score = score
                    best_bet2 = comb
        
        # 5. 特別號預測 (Regime-Aware)
        from .special_predictor import PowerLottoSpecialPredictor
        predictor = PowerLottoSpecialPredictor(lottery_rules)
        # 傳送主號碼以供關聯性分析
        s1 = predictor.predict(draws, main_numbers=bet1)
        
        # Bet 2 特別號採用互補性
        s2_pool = [2, 5, 4, 8, 1, 3, 7, 6]
        s2 = s1
        for s in s2_pool:
            if s != s1:
                s2 = s
                break
                
        bets = [
            {'numbers': sorted(bet1), 'special': int(s1), 'source': f'orthogonal_v1_bet1_{regime}'},
            {'numbers': sorted(best_bet2), 'special': int(s2), 'source': f'orthogonal_v1_bet2_{regime}'}
        ]
        
        covered = set(bet1) | set(best_bet2)
        
        return {
            'bets': bets,
            'regime': regime_info,
            'coverage': len(covered) / (max_num - min_num + 1),
            'method': 'orthogonal_ensemble_v1',
            'overlap_count': min_overlap
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

    def _generate_skewed_bet(self, draws: List[Dict], lottery_rules: Dict, number_scores: Dict[int, float], target_zone: int = None) -> Dict:
        """
        生成偏態策略注 (Skewed Bet) - 專門捕捉尾部風險 (Tail Risks)
        例如：極端小號 (Front Dense)、極端大號 (Back Dense)
        """
        pick_count = lottery_rules.get('pickCount', 6)
        max_num = lottery_rules.get('maxNumber', 49)
        
        # 1. 策略選擇
        # 2026-01-12 P0: 強制支持 "前區密集" 與 "後區密集" 作為保險
        if target_zone is None:
            target_zone = random.randint(1, 3) # 1: Low, 2: Mid, 3: High
        
        sorted_nums = sorted(number_scores.items(), key=lambda x: x[1], reverse=True)
        # 精英池擴大到 35 個，增加波動性覆蓋
        top_pool = [n for n, s in sorted_nums[:35]]
        
        # 定義邊界 (以 49 碼為基準)
        low_bound = max_num // 3
        high_bound = (max_num // 3) * 2
        
        zone_nums = []
        source_tag = "skewed_insurance"
        
        if target_zone == 1: # Low Focus (Front Dense)
            zone_nums = [n for n in top_pool if n <= low_bound]
            source_tag = "skewed_front_dense"
        elif target_zone == 2: # Mid Focus
            zone_nums = [n for n in top_pool if low_bound < n <= high_bound]
            source_tag = "skewed_mid_focus"
        else: # High Focus (Back Dense)
            zone_nums = [n for n in top_pool if n > high_bound]
            source_tag = "skewed_back_dense"
            
        # 如果候選號太少，則從全精英池中按比例補充
        if len(zone_nums) < 4:
            zone_nums = top_pool
            
        # 從選定區間選 4-5 個 (強化聚集性)
        num_from_zone = min(len(zone_nums), random.randint(4, 5))
        selected = random.sample(zone_nums, num_from_zone)
        
        # 補足剩餘位數 (從前 20 名中補，確保品質)
        top_20 = [n for n, s in sorted_nums[:20]]
        while len(selected) < pick_count:
            n = random.choice(top_20)
            if n not in selected:
                selected.append(n)
        
        return {
            'numbers': sorted(selected),
            'source': source_tag,
            'group': 'contrarian'
        }

    def _apply_gnn_synergy(self, bets: List[Dict], all_predictions: Dict, num_bets: int, lottery_rules: Dict, force: bool = False) -> List[Dict]:
        """
        GNN 協同優化：
        利用 GNN 的全量機率熱點，補全現有多注組合中未覆蓋的高機率區域。
        """
        if 'gnn' not in all_predictions or 'probabilities' not in all_predictions['gnn']:
            return bets
            
        probs = np.array(all_predictions['gnn']['probabilities'])
        min_num = lottery_rules.get('minNumber', 1)
        pick_count = lottery_rules.get('pickCount', 6)
        
        # 1. 找出目前已覆蓋的號碼
        covered = set()
        for b in bets:
            covered.update(b['numbers'])
            
        # 2. 找出未覆蓋號碼中的 GNN 高機率點
        uncovered_probs = []
        for i, p in enumerate(probs):
            num = i + min_num
            if num not in covered:
                uncovered_probs.append((num, p))
        
        if not uncovered_probs:
            return bets
            
        # 3. 如果還有空間或是強制執行
        if len(bets) < num_bets or force:
            top_uncovered = sorted(uncovered_probs, key=lambda x: x[1], reverse=True)
            pool = [n for n, p in top_uncovered[:15]]
            
            if len(pool) >= 6:
                new_numbers = sorted(random.sample(pool, 6))
                new_bet = {
                    'numbers': new_numbers,
                    'source': 'gnn_synergy_gap_filler',
                    'group': 'p1_advanced'
                }
                
                if len(bets) < num_bets:
                    bets.append(new_bet)
                elif force and len(bets) >= 2:
                    # 替換掉最後一注 (通常是信心度最低的策略注)
                    bets[-1] = new_bet
                    
                logger.debug(f"🕸️ GNN Synergy: Integrated gap-filling bet.")
            
        return bets


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
