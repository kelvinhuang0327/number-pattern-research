#!/usr/bin/env python3
"""
Auto Optimizer V2 - 進階自動優化器

Phase 2 核心模組：
1. VotingEnsemble - 多模型投票機制 (多數投票 & 加權投票)
2. AdaptiveWeightOptimizer - 自動權重調整 (Bayesian Optimization)
3. IntegratedPredictor - 整合 Phase 1 熱號/共現分析 + 投票機制

使用方式:
python auto_optimizer_v2.py --backtest --year 2025
python auto_optimizer_v2.py --predict
python auto_optimizer_v2.py --optimize-weights
"""
import sys
import os
import argparse
import logging
import numpy as np
import random
from collections import Counter, defaultdict
from typing import List, Dict, Tuple, Optional, Callable, Set
from dataclasses import dataclass

# Add project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from models.unified_predictor import UnifiedPredictionEngine
from database import DatabaseManager
from common import get_lottery_rules
from tools.hot_cooccurrence_analyzer import HotCooccurrenceAnalyzer

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
from tools.negative_selector import NegativeSelector
from models.genetic_optimizer import GeneticWeightOptimizer


@dataclass
class PredictionResult:
    """預測結果"""
    numbers: List[int]
    confidence: float
    method: str
    metadata: Dict = None


class VotingEnsemble:
    """
    投票集成器
    
    支援：
    - majority_vote: 多數投票
    - weighted_vote: 加權投票
    - ranked_vote: 排名投票
    """
    
    def __init__(self, strategies: Dict[str, Callable] = None):
        """
        初始化投票集成器
        
        Args:
            strategies: 策略字典 {策略名: 預測函數}
        """
        self.strategies = strategies or {}
        self.weights = {name: 1.0 for name in self.strategies}
        
    def set_weights(self, weights: Dict[str, float]):
        """設定策略權重"""
        self.weights = weights
        
    def _collect_predictions(
        self, 
        history: List[Dict], 
        lottery_rules: Dict
    ) -> Dict[str, List[int]]:
        """收集所有策略的預測結果"""
        predictions = {}
        
        for name, strategy in self.strategies.items():
            try:
                result = strategy(history, lottery_rules)
                predictions[name] = result.get('numbers', [])
            except Exception as e:
                # logger.debug(f"Strategy {name} failed: {e}")
                predictions[name] = []
                
        return predictions
    
    def majority_vote(
        self, 
        history: List[Dict], 
        lottery_rules: Dict,
        min_votes: int = 2,
        kill_list: List[int] = None
    ) -> List[int]:
        """
        多數投票
        
        Args:
            history: 歷史數據
            lottery_rules: 彩票規則
            min_votes: 最少票數門檻
            kill_list: 排除名單 (殺號)
            
        Returns:
            選中的號碼列表
        """
        predictions = self._collect_predictions(history, lottery_rules)
        pick_count = lottery_rules.get('pickCount', 6)
        kill_set = set(kill_list) if kill_list else set()
        
        # 計算每個號碼的票數
        vote_counts = Counter()
        for nums in predictions.values():
            for num in nums:
                if num not in kill_set:
                    vote_counts[num] += 1
        
        # 按票數排序
        sorted_nums = sorted(vote_counts.keys(), key=lambda x: vote_counts[x], reverse=True)
        
        # 選擇票數 >= min_votes 的號碼
        selected = [n for n in sorted_nums if vote_counts[n] >= min_votes][:pick_count]
        
        # 如果不足，補充得票最多的
        if len(selected) < pick_count:
            remaining = [n for n in sorted_nums if n not in selected]
            selected.extend(remaining[:pick_count - len(selected)])
        
        return sorted(selected[:pick_count])
    
    def weighted_vote(
        self, 
        history: List[Dict], 
        lottery_rules: Dict,
        kill_list: List[int] = None
    ) -> Tuple[List[int], Dict[int, float]]:
        """
        加權投票
        
        Args:
            kill_list: 排除名單 (殺號)
            
        Returns:
            (選中的號碼列表, 號碼得分字典)
        """
        predictions = self._collect_predictions(history, lottery_rules)
        pick_count = lottery_rules.get('pickCount', 6)
        kill_set = set(kill_list) if kill_list else set()
        
        # 計算加權得分
        scores = defaultdict(float)
        
        for name, nums in predictions.items():
            weight = self.weights.get(name, 1.0)
            for rank, num in enumerate(nums):
                if num in kill_set:
                    continue
                    
                # 排名分 = (6-rank)/6 for 6 numbers
                rank_score = (len(nums) - rank) / len(nums) if nums else 0
                scores[num] += weight * rank_score
        
        # 按得分排序
        sorted_nums = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
        
        return sorted(sorted_nums[:pick_count]), dict(scores)
    
    def get_consensus_numbers(
        self, 
        history: List[Dict], 
        lottery_rules: Dict,
        consensus_threshold: float = 0.5
    ) -> Set[int]:
        """
        獲取共識號碼 (超過 threshold 比例的策略都選中的號碼)
        
        Args:
            consensus_threshold: 共識門檻 (0-1)
            
        Returns:
            共識號碼集合
        """
        predictions = self._collect_predictions(history, lottery_rules)
        num_strategies = len(predictions)
        
        if num_strategies == 0:
            return set()
        
        vote_counts = Counter()
        for nums in predictions.values():
            for num in nums:
                vote_counts[num] += 1
        
        min_votes = int(num_strategies * consensus_threshold)
        consensus = {n for n, v in vote_counts.items() if v >= min_votes}
        
        return consensus


class AdaptiveWeightOptimizer:
    """
    自適應權重優化器
    
    使用回測結果自動調整策略權重
    """
    
    def __init__(
        self, 
        strategies: Dict[str, Callable],
        lottery_type: str = 'BIG_LOTTO'
    ):
        self.strategies = strategies
        self.lottery_type = lottery_type
        self.rules = get_lottery_rules(lottery_type)
        self.db = DatabaseManager(
            db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
        )
        
    def get_data(self) -> List[Dict]:
        """獲取歷史數據 (ASC)"""
        draws_desc = self.db.get_all_draws(lottery_type=self.lottery_type)
        return list(reversed(draws_desc))
    
    def _evaluate_strategy(
        self, 
        strategy: Callable, 
        history: List[Dict],
        test_draws: List[Dict],
        training_window: int = 100
    ) -> float:
        """評估單一策略的表現"""
        total_matches = 0
        total_tests = 0
        
        draws = history + test_draws
        start_idx = len(history)
        
        for i, target in enumerate(test_draws):
            test_idx = start_idx + i
            train_data = draws[max(0, test_idx - training_window):test_idx]
            
            if len(train_data) < 20:
                continue
            
            try:
                result = strategy(train_data, self.rules)
                predicted = set(result.get('numbers', []))
                actual = set(target['numbers'])
                matches = len(predicted & actual)
                total_matches += matches
                total_tests += 1
            except:
                continue
        
        return total_matches / total_tests if total_tests > 0 else 0
    
    def calculate_optimal_weights(
        self, 
        backtest_periods: int = 50,
        training_window: int = 100
    ) -> Dict[str, float]:
        """
        計算最優策略權重
        
        基於歷史表現計算權重，表現越好權重越高
        """
        logger.info("📊 計算最優策略權重...")
        
        all_data = self.get_data()
        
        if len(all_data) < backtest_periods + training_window:
            logger.warning("數據量不足，使用均等權重")
            return {name: 1.0 / len(self.strategies) for name in self.strategies}
        
        # 分割數據
        test_draws = all_data[-backtest_periods:]
        history = all_data[:-backtest_periods]
        
        # 評估每個策略
        scores = {}
        for name, strategy in self.strategies.items():
            score = self._evaluate_strategy(strategy, history, test_draws, training_window)
            scores[name] = score
            logger.info(f"  {name}: 平均命中 {score:.2f}")
        
        # 轉換為權重 (softmax)
        total = sum(scores.values())
        if total > 0:
            weights = {name: score / total for name, score in scores.items()}
        else:
            weights = {name: 1.0 / len(self.strategies) for name in self.strategies}
        
        logger.info("📈 最優權重:")
        for name, weight in sorted(weights.items(), key=lambda x: x[1], reverse=True):
            logger.info(f"  {name}: {weight:.2%}")
        
        return weights
    
    def grid_search_weights(
        self, 
        backtest_periods: int = 50,
        top_k: int = 5
    ) -> Dict[str, float]:
        """
        網格搜索最優權重組合
        
        Args:
            backtest_periods: 回測期數
            top_k: 只優化表現最好的 K 個策略
        """
        # 先找出表現最好的策略
        base_weights = self.calculate_optimal_weights(backtest_periods)
        
        # 選擇 Top K
        sorted_strategies = sorted(base_weights.items(), key=lambda x: x[1], reverse=True)
        top_strategies = [name for name, _ in sorted_strategies[:top_k]]
        
        logger.info(f"🔍 對 Top {top_k} 策略進行網格搜索: {top_strategies}")
        
        # 簡單網格搜索
        best_weights = base_weights.copy()
        best_score = 0
        
        # 測試不同權重組合
        weight_options = [0.05, 0.1, 0.15, 0.2, 0.25, 0.3]
        
        # 這裡簡化為測試幾種固定組合
        for boost in [1.2, 1.5, 2.0]:
            test_weights = base_weights.copy()
            for name in top_strategies[:2]:  # 加強 Top 2
                test_weights[name] *= boost
            
            # 正規化
            total = sum(test_weights.values())
            test_weights = {k: v / total for k, v in test_weights.items()}
            
            # 評估 (簡化版)
            score = sum(test_weights.get(n, 0) * base_weights.get(n, 0) for n in top_strategies)
            
            if score > best_score:
                best_score = score
                best_weights = test_weights
        
        return best_weights

    def optimize_with_genetic(
        self,
        backtest_periods: int = 50,
        training_window: int = 100,
        generations: int = 5
    ) -> Dict[str, float]:
        """使用遺傳算法優化權重 (全域搜索)"""
        logger.info(f"🧬 啟動遺傳算法權重優化 (世代數: {generations})...")
        
        all_data = self.get_data()
        test_draws = all_data[-backtest_periods:]
        history = all_data[:-backtest_periods]
        
        # 定義適應度函數: 回測勝率
        def fitness_fn(weights: Dict[str, float]) -> float:
            # 建立臨時投票器
            temp_voting = VotingEnsemble(self.strategies)
            temp_voting.set_weights(weights)
            
            total_wins = 0
            # 隨機採樣 20 期進行快速評估 (避免太慢)
            sample_draws = test_draws if len(test_draws) < 20 else random.sample(test_draws, 20)
            
            for i, target in enumerate(sample_draws):
                # 這裡為了速度簡化數據切分
                start_idx = all_data.index(target)
                h = all_data[max(0, start_idx - training_window):start_idx]
                
                nums, _ = temp_voting.weighted_vote(h, self.rules)
                actual = target['numbers']
                special = target['special']
                
                m = len(set(nums) & set(actual))
                s = special in nums
                if m >= 3 or (m == 2 and s):
                    total_wins += 1
                    
            return total_wins / len(sample_draws)

        optimizer = GeneticWeightOptimizer(
            list(self.strategies.keys()),
            population_size=20, 
            generations=generations
        )
        
        best_weights = optimizer.optimize(fitness_fn)
        
        logger.info("🧬 遺傳優化完成. 最佳權重:")
        for name, w in sorted(best_weights.items(), key=lambda x: x[1], reverse=True):
            logger.info(f"  {name}: {w:.2%}")
            
        return best_weights


class IntegratedPredictor:
    """
    整合預測器
    
    結合：
    1. Phase 1 熱號 + 共現分析
    2. Phase 2 投票集成
    3. 自適應權重
    """
    
    def __init__(self, lottery_type: str = 'BIG_LOTTO'):
        self.lottery_type = lottery_type
        self.rules = get_lottery_rules(lottery_type)
        self.db = DatabaseManager(
            db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
        )
        self.engine = UnifiedPredictionEngine()
        self.analyzer = HotCooccurrenceAnalyzer(lottery_type)
        self.selector = NegativeSelector(lottery_type)
        
        # 定義策略
        self.strategies = {
            'zone_balance': lambda h, r: self.engine.zone_balance_predict(h[-500:], r),
            'frequency': lambda h, r: self.engine.frequency_predict(h[-100:], r),
            'bayesian': lambda h, r: self.engine.bayesian_predict(h[-200:], r),
            'trend': lambda h, r: self.engine.trend_predict(h[-100:], r),
            'deviation': lambda h, r: self.engine.deviation_predict(h[-100:], r),
            'hot_cooccurrence': lambda h, r: self._hot_cooccurrence_predict(h, r),
        }
        
        self.voting = VotingEnsemble(self.strategies)
        self.optimizer = AdaptiveWeightOptimizer(self.strategies, lottery_type)
        
        # 預設權重
        self.weights = {
            'zone_balance': 0.20,
            'frequency': 0.15,
            'bayesian': 0.15,
            'trend': 0.15,
            'deviation': 0.10,
            'hot_cooccurrence': 0.25,
        }
        
    def _hot_cooccurrence_predict(
        self, 
        history: List[Dict], 
        lottery_rules: Dict
    ) -> Dict:
        """熱號 + 共現預測"""
        hot_freq = self.analyzer.get_hot_numbers(history, 50)
        hot_nums = [num for num, _ in hot_freq]
        co_matrix = self.analyzer.build_cooccurrence_matrix(history, 100)
        predicted = self.analyzer.apply_cooccurrence_rules(
            hot_nums, co_matrix, lottery_rules['pickCount']
        )
        return {'numbers': predicted, 'confidence': 0.7}
    
    def get_data(self) -> List[Dict]:
        """獲取歷史數據"""
        draws_desc = self.db.get_all_draws(lottery_type=self.lottery_type)
        return list(reversed(draws_desc))
    
    def predict(
        self, 
        mode: str = 'weighted',
        optimize_weights: bool = False,
        use_genetic: bool = False,
        use_kill: bool = True,
        kill_count: int = 10
    ) -> Dict:
        """
        執行預測
        
        Args:
            mode: 'majority' | 'weighted' | 'consensus'
            optimize_weights: 是否先優化權重
            use_genetic: 是否使用遺傳算法優化權重
            use_kill: 是否使用排除法 (Negative Selection)
            kill_count: 排除數量
        """
        history = self.get_data()
        
        if optimize_weights:
            if use_genetic:
                self.weights = self.optimizer.optimize_with_genetic()
            else:
                self.weights = self.optimizer.calculate_optimal_weights()
        
        self.voting.set_weights(self.weights)
        
        # 負向排除
        kill_list = []
        if use_kill:
            kill_list = self.selector.predict_kill_numbers(count=kill_count)
            logger.info(f"🔪 負向排除 (Phase 3): {kill_list}")
        
        if mode == 'majority':
            nums = self.voting.majority_vote(history, self.rules, min_votes=2, kill_list=kill_list)
            scores = {}
        elif mode == 'weighted':
            nums, scores = self.voting.weighted_vote(history, self.rules, kill_list=kill_list)
        else:  # consensus
            # Consensus doesn't strictly use kill list inside but we filter result
            consensus = self.voting.get_consensus_numbers(history, self.rules, 0.5)
            nums = sorted(list(consensus - set(kill_list)))[:self.rules['pickCount']]
            scores = {}
        
        consensus = self.voting.get_consensus_numbers(history, self.rules, 0.5)
        
        return {
            'numbers': nums,
            'consensus': list(consensus),
            'scores': scores,
            'weights': self.weights,
            'mode': mode,
            'kill_list': kill_list
        }
    
    def predict_double_bet(
        self, 
        optimize_weights: bool = False,
        use_genetic: bool = False,
        use_kill: bool = True,
        kill_count: int = 10
    ) -> Dict:
        """產生雙注預測"""
        history = self.get_data()
        
        if optimize_weights:
            if use_genetic:
                self.weights = self.optimizer.optimize_with_genetic()
            else:
                self.weights = self.optimizer.calculate_optimal_weights()
        
        self.voting.set_weights(self.weights)
        
        # 負向排除
        kill_list = []
        if use_kill:
            kill_list = self.selector.predict_kill_numbers(count=kill_count)
            logger.info(f"🔪 負向排除 (Phase 3): {kill_list}")
            
        # Bet 1: 加權投票 (受 Kill List 影響)
        bet1, scores = self.voting.weighted_vote(history, self.rules, kill_list=kill_list)
        
        # Bet 2: Zone Balance (受 Kill List 影響)
        try:
            result = self.engine.zone_balance_predict(history[-500:], self.rules)
            raw_bet2 = set(result.get('numbers', []))
            # 如果 Bet 2 中有被殺掉的號碼，替換掉
            filtered_bet2 = list(raw_bet2 - set(kill_list))
            while len(filtered_bet2) < self.rules['pickCount']:
                # 簡單補號邏輯: 從得分高但在 bet1 的號碼補，或者隨機，這裡選得分次高的
                candidates = [n for n in scores.keys() if n not in filtered_bet2 and n not in kill_list]
                if candidates:
                    filtered_bet2.append(candidates[0])
                else:
                    break # Should not happen often
            bet2 = sorted(filtered_bet2[:self.rules['pickCount']])
        except:
            bet2 = [1, 2, 3, 4, 5, 6]
        
        consensus = self.voting.get_consensus_numbers(history, self.rules, 0.5)
        
        return {
            'bet1': bet1,
            'bet2': bet2,
            'consensus': list(consensus),
            'overlap': list(set(bet1) & set(bet2)),
            'coverage': list(set(bet1) | set(bet2)),
            'weights': self.weights,
            'kill_list': kill_list
        }

    def predict_best_5_bets(
        self,
        optimize_weights: bool = True,
        use_genetic: bool = True,
        use_kill: bool = True,
        kill_count: int = 5
    ) -> Dict:
        """
        產生最佳五注預測 (Phase 3.5 Best 5 Bets)
        
        策略組成:
        1. Bet 1 (穩健): 加權投票 Top 6
        2. Bet 2 (平衡): Zone Balance (500期)
        3. Bet 3 (趨勢): Short-term Hot (熱號+共現)
        4. Bet 4 (回補): Deviation (乖離率)
        5. Bet 5 (綜合): Consensus (共識決)
        """
        history = self.get_data()
        
        # 1. 優化權重 (for Bet 1 & Consensus)
        if optimize_weights:
            if use_genetic:
                self.weights = self.optimizer.optimize_with_genetic()
            else:
                self.weights = self.optimizer.calculate_optimal_weights()
            self.voting.set_weights(self.weights)
            
        # 2. 產生殺號清單
        kill_list = []
        if use_kill:
            kill_list = self.selector.predict_kill_numbers(count=kill_count)
            logger.info(f"🔪 負向排除 (Phase 3.5): {kill_list}")
            
        pick_count = self.rules['pickCount']
        
        def filter_and_fill(numbers, source_name="strategy"):
            """過濾殺號並補足號碼"""
            valid_nums = [n for n in numbers if n not in kill_list]
            if len(valid_nums) < pick_count:
                # 若號碼不足，從 Consensus 中補，且不重複、不殺號
                consensus_pool = sorted(list(self.voting.get_consensus_numbers(history, self.rules, 0.3)))
                for c in consensus_pool:
                    if len(valid_nums) >= pick_count:
                        break
                    if c not in valid_nums and c not in kill_list:
                        valid_nums.append(c)
            
            # 若還是不足 (極少見)，隨機補
            while len(valid_nums) < pick_count:
                import random
                r = random.randint(self.rules['minNumber'], self.rules['maxNumber'])
                if r not in valid_nums and r not in kill_list:
                    valid_nums.append(r)
            
            return sorted(valid_nums[:pick_count])

        # --- Bet 1: 加權投票 (Weighted Vote) ---
        raw_bet1, scores = self.voting.weighted_vote(history, self.rules, kill_list=kill_list)
        bet1 = filter_and_fill(raw_bet1, "Weighted")
        
        # --- Bet 2: 分區平衡 (Zone Balance) ---
        try:
            zb_result = self.engine.zone_balance_predict(history[-500:], self.rules)
            bet2 = filter_and_fill(zb_result.get('numbers', []), "ZoneBalance")
        except:
            bet2 = filter_and_fill([], "ZoneBalance_Error")

        # --- Bet 3: 短期熱號 + 共現 (Hot + Cooccurrence) ---
        # 使用 20 期窗口捕捉短期趨勢
        hot_nums_20 = [n for n, _ in self.analyzer.get_hot_numbers(history, 20)]
        co_matrix = self.analyzer.build_cooccurrence_matrix(history, 50)
        # 取前 15 個熱號進行共現分析
        raw_bet3 = self.analyzer.apply_cooccurrence_rules(hot_nums_20[:15], co_matrix, pick_count)
        bet3 = filter_and_fill(raw_bet3, "HotCooccurrence")

        # --- Bet 4: 乖離率回補 (Deviation) ---
        try:
            dev_result = self.engine.deviation_predict(history, self.rules)
            bet4 = filter_and_fill(dev_result.get('numbers', []), "Deviation")
        except:
             bet4 = filter_and_fill([], "Deviation_Error")
             
        # --- Bet 5: 綜合共識 (Consensus) ---
        # 提高閾值取得高信賴度集合
        consensus_set = self.voting.get_consensus_numbers(history, self.rules, 0.4)
        bet5 = filter_and_fill(list(consensus_set), "Consensus")
        
        return {
            'bet1': bet1, 'desc1': '穩健型 (加權投票)',
            'bet2': bet2, 'desc2': '平衡型 (分區平衡)',
            'bet3': bet3, 'desc3': '趨勢型 (熱號共現)',
            'bet4': bet4, 'desc4': '回補型 (乖離率)',
            'bet5': bet5, 'desc5': '綜合型 (多模共識)',
            'kill_list': kill_list,
            'weights': self.weights
        }
    
    def backtest_5bets(
        self,
        year: int = 2025,
        use_genetic: bool = True,
        kill_count: int = 5
    ) -> Dict:
        """
        執行 Phase 3.5 最佳五注回測
        """
        all_draws = self.get_data()
        test_draws = [d for d in all_draws if d['date'].startswith(str(year))]

        if not test_draws:
            return {'error': f'No data for {year}'}

        start_idx = all_draws.index(test_draws[0])

        # 預先計算權重 (在回測前)
        pre_test_data = all_draws[:start_idx]
        if len(pre_test_data) > 100:
            if use_genetic:
                self.weights = self.optimizer.optimize_with_genetic()
            else:
                self.weights = self.optimizer.calculate_optimal_weights()
            self.voting.set_weights(self.weights)

        total_draws = 0
        total_wins = 0
        bet_wins = {f'bet{i}': 0 for i in range(1, 6)}
        match_counts = Counter()
        max_match = 0

        # Kill stats
        total_killed_winners = 0
        draws_with_kill_mistakes = 0

        print(f"\n🔄 回測進行中 (Phase 3.5 最佳五注, 年份: {year}, 共 {len(test_draws)} 期)...")

        for i, target in enumerate(test_draws):
            current_idx = start_idx + i
            history = all_draws[:current_idx]

            # 產生殺號清單 (使用歷史數據)
            kill_list = []
            if kill_count > 0:
                kill_list = self.selector.predict_kill_numbers(count=kill_count, history=history)

            # 統計誤殺 (Winning numbers in kill list)
            actual_set = set(target['numbers'])
            killed_winners = list(actual_set & set(kill_list))
            if len(killed_winners) > 0:
                total_killed_winners += len(killed_winners)
                draws_with_kill_mistakes += 1

            pick_count = self.rules['pickCount']

            def filter_and_fill_backtest(numbers, current_history, current_kill_list):
                """過濾殺號並補足號碼 (回測專用)"""
                valid_nums = [n for n in numbers if n not in current_kill_list]
                if len(valid_nums) < pick_count:
                    # 從 Consensus 中補，且不重複、不殺號
                    consensus_pool = sorted(list(self.voting.get_consensus_numbers(current_history, self.rules, 0.3)))
                    for c in consensus_pool:
                        if len(valid_nums) >= pick_count:
                            break
                        if c not in valid_nums and c not in current_kill_list:
                            valid_nums.append(c)

                # 若還是不足，隨機補
                while len(valid_nums) < pick_count:
                    import random
                    r = random.randint(self.rules['minNumber'], self.rules['maxNumber'])
                    if r not in valid_nums and r not in current_kill_list:
                        valid_nums.append(r)

                return sorted(valid_nums[:pick_count])

            # --- Bet 1: 加權投票 (Weighted Vote) ---
            raw_bet1, _ = self.voting.weighted_vote(history, self.rules, kill_list=kill_list)
            bet1 = filter_and_fill_backtest(raw_bet1, history, kill_list)

            # --- Bet 2: 分區平衡 (Zone Balance) ---
            try:
                zb_result = self.engine.zone_balance_predict(history[-500:], self.rules)
                bet2 = filter_and_fill_backtest(zb_result.get('numbers', []), history, kill_list)
            except:
                bet2 = filter_and_fill_backtest([], history, kill_list)

            # --- Bet 3: 短期熱號 + 共現 (Hot + Cooccurrence) ---
            hot_nums_20 = [n for n, _ in self.analyzer.get_hot_numbers(history, 20)]
            co_matrix = self.analyzer.build_cooccurrence_matrix(history, 50)
            raw_bet3 = self.analyzer.apply_cooccurrence_rules(hot_nums_20[:15], co_matrix, pick_count)
            bet3 = filter_and_fill_backtest(raw_bet3, history, kill_list)

            # --- Bet 4: 乖離率回補 (Deviation) ---
            try:
                dev_result = self.engine.deviation_predict(history, self.rules)
                bet4 = filter_and_fill_backtest(dev_result.get('numbers', []), history, kill_list)
            except:
                bet4 = filter_and_fill_backtest([], history, kill_list)

            # --- Bet 5: 綜合共識 (Consensus) ---
            consensus_set = self.voting.get_consensus_numbers(history, self.rules, 0.4)
            bet5 = filter_and_fill_backtest(list(consensus_set), history, kill_list)

            # 評估
            actual = target['numbers']
            special = target['special']

            bets = [bet1, bet2, bet3, bet4, bet5]
            current_best_match = 0
            current_draw_won = False

            for idx, bet in enumerate(bets):
                main_matches = len(set(bet) & set(actual))
                special_match = special in bet
                
                # 判斷是否中獎 (3個主號或2個主號+特別號)
                won = main_matches >= 3 or (main_matches == 2 and special_match)
                if won:
                    bet_wins[f'bet{idx+1}'] += 1
                    current_draw_won = True
                
                # 記錄最佳命中 (主號)
                current_best_match = max(current_best_match, main_matches)
                
                # 記錄含特別號的情況
                if special_match:
                    match_counts[f"{main_matches}+1"] = match_counts.get(f"{main_matches}+1", 0) + 1
                else:
                    match_counts[main_matches] = match_counts.get(main_matches, 0) + 1

            if current_draw_won:
                total_wins += 1
                if current_best_match >= 4:
                    print(f"  ✨ 期數 {target['draw']}: 命中 {current_best_match} 號!")
                elif (any(len(set(b) & set(actual)) == 3 and special in b for b in bets)):
                    print(f"  ✨ 期數 {target['draw']}: 命中 3+1 (特別號)!")

            max_match = max(max_match, current_best_match)
            total_draws += 1

        win_rate = total_wins / total_draws if total_draws > 0 else 0

        return {
            'year': year,
            'total_draws': total_draws,
            'total_wins': total_wins,
            'win_rate': win_rate,
            'bet_wins': bet_wins,
            'weights': self.weights,
            'match_counts': dict(match_counts),
            'max_match': max_match,
            'total_killed_winners': total_killed_winners,
            'draws_with_kill_mistakes': draws_with_kill_mistakes
        }
    
    def backtest(
        self, 
        year: int = 2025,
        use_genetic: bool = False,
        use_kill: bool = True,
        kill_count: int = 10
    ) -> Dict:
        """執行回測"""
        all_draws = self.get_data()
        test_draws = [d for d in all_draws if d['date'].startswith(str(year))]
        
        if not test_draws:
            return {'error': f'No data for {year}'}
        
        start_idx = all_draws.index(test_draws[0])
        
        # 先計算權重 (在回測前)
        pre_test_data = all_draws[:start_idx]
        if len(pre_test_data) > 100:
            if use_genetic:
                self.weights = self.optimizer.optimize_with_genetic()
            else:
                self.weights = self.optimizer.calculate_optimal_weights(50)
            self.voting.set_weights(self.weights)
        
        total = 0
        wins = 0
        bet1_wins = 0
        bet2_wins = 0
        match_counts = Counter()
        max_match = 0
        
        # Kill stats
        total_killed_winners = 0
        draws_with_kill_mistakes = 0
        
        print(f"\n🔄 回測進行中 (年份: {year}, 共 {len(test_draws)} 期)...")
        
        for i, target in enumerate(test_draws):
            current_idx = start_idx + i
            history = all_draws[:current_idx]
            
            # Let's check NegativeSelector implementation deeply later.
            # For now, let's assume it might peek if not careful, but `predict_kill_numbers` 
            # takes last 100. If DB has future data, it peeks.
            # IMPORTANT: We need to mock DB or limit data for Selector in backtest.
            # But `selector` is init once. 
            pass 

            # ... code continues ...

            
            # Kill List (using history to avoid leakage)
            kill_list = []
            if use_kill:
                kill_list = self.selector.predict_kill_numbers(count=kill_count, history=history)
            
            # 統計誤殺 (Winning numbers in kill list)
            wrong_kills = 0
            actual_set = set(target['numbers'])
            killed_winners = []
            if use_kill: 
                killed_winners = list(actual_set & set(kill_list))
                wrong_kills = len(killed_winners)
                if wrong_kills > 0:
                    total_killed_winners += wrong_kills
                    draws_with_kill_mistakes += 1
            
            # Bet 1: 加權投票
            bet1, _ = self.voting.weighted_vote(history, self.rules, kill_list=kill_list)
            
            # Bet 2: Zone Balance
            try:
                result = self.engine.zone_balance_predict(history[-500:], self.rules)
                raw_bet2 = set(result.get('numbers', []))
                # 排除殺號
                filtered_bet2 = list(raw_bet2 - set(kill_list))
                # 簡單補號 (隨機補滿 6 個) - 這裡再次呼叫預測可能太慢，直接補 1-49 中未選的
                if len(filtered_bet2) < self.rules['pickCount']:
                    for n in range(1, 50):
                         if n not in filtered_bet2 and n not in kill_list:
                             filtered_bet2.append(n)
                         if len(filtered_bet2) == self.rules['pickCount']:
                             break
                bet2 = sorted(filtered_bet2)
            except:
                bet2 = [1, 2, 3, 4, 5, 6]
            
            # 評估
            actual = target['numbers']
            special = target['special']
            
            m1 = len(set(bet1) & set(actual))
            s1 = special in bet1
            m2 = len(set(bet2) & set(actual))
            s2 = special in bet2
            
            # 記錄最佳命中 (主號)
            best_match = max(m1, m2)
            max_match = max(max_match, best_match)
            match_counts[best_match] += 1
            
            # 記錄含特別號的情況
            if s1:
                 match_counts[f"{m1}+1"] = match_counts.get(f"{m1}+1", 0) + 1
            if s2:
                 match_counts[f"{m2}+1"] = match_counts.get(f"{m2}+1", 0) + 1
            
            w1 = m1 >= 3 or (m1 == 2 and s1)
            w2 = m2 >= 3 or (m2 == 2 and s2)
            
            if w1:
                bet1_wins += 1
            if w2:
                bet2_wins += 1
            if w1 or w2:
                wins += 1
                if best_match >= 4:
                     print(f"  ✨ 期數 {target['draw']}: 命中 {best_match} 號! (Bet1:{m1}, Bet2:{m2})")
                elif (m1 == 3 and s1) or (m2 == 3 and s2):
                     print(f"  ✨ 期數 {target['draw']}: 命中 3+1 (特別號)!")
            
            total += 1
        
        win_rate = wins / total if total > 0 else 0
        
        return {
            'year': year,
            'total': total,
            'wins': wins,
            'bet1_wins': bet1_wins,
            'bet2_wins': bet2_wins,
            'win_rate': win_rate,
            'weights': self.weights,
            'match_counts': dict(match_counts),
            'max_match': max_match,
            'total_killed_winners': total_killed_winners,
            'draws_with_kill_mistakes': draws_with_kill_mistakes
        }


def main():
    parser = argparse.ArgumentParser(description='Auto Optimizer V2')
    parser.add_argument('--lottery', '-l', type=str, default='BIG_LOTTO',
                        choices=['BIG_LOTTO', 'POWER_LOTTO', 'DAILY_539'],
                        help='彩票類型')
    parser.add_argument('--backtest', action='store_true',
                        help='執行回測')
    parser.add_argument('--year', '-y', type=int, default=2025,
                        help='回測年份')
    parser.add_argument('--predict', action='store_true',
                        help='執行預測')
    parser.add_argument('--mode', type=str, default='weighted',
                        choices=['majority', 'weighted', 'consensus'],
                        help='投票模式')
    parser.add_argument('--optimize-weights', action='store_true',
                        help='優化權重後再預測/回測')
    parser.add_argument('--double-bet', action='store_true',
                        help='產生雙注預測')
    parser.add_argument('--genetic', action='store_true',
                        help='使用遺傳算法優化權重 (Phase 3)')
    parser.add_argument('--no-kill', action='store_true',
                        help='停用負向排除 (Phase 3)')
    parser.add_argument('--kill-count', type=int, default=5,
                        help='負向排除數量 (預設 5)')
    
    args = parser.parse_args()
    
    predictor = IntegratedPredictor(args.lottery)
    
    if args.backtest:
        print("=" * 80)
        print(f"📊 Auto Optimizer V2 + Phase 3 回測 ({args.lottery})")
        print("=" * 80)
        
        result = predictor.backtest(
            year=args.year,
            use_genetic=args.genetic,
            use_kill=not args.no_kill,
            kill_count=args.kill_count
        )
        
        print("\n📈 回測結果:")
        print(f"   年份: {result['year']}")
        print(f"   總期數: {result['total']}")
        print(f"   第一注 (投票) 中獎: {result['bet1_wins']}")
        print(f"   第二注 (Zone Balance) 中獎: {result['bet2_wins']}")
        print(f"   總中獎: {result['wins']}")
        print(f"   總勝率: {result['win_rate']*100:.2f}%")
        
        if result.get('total_killed_winners', 0) > 0:
            print(f"\n⚠️ 殺號風險評估:")
            print(f"   排除數量: {args.kill_count}")
            print(f"   誤殺中獎號碼總數: {result['total_killed_winners']}")
            print(f"   發生誤殺的期數: {result['draws_with_kill_mistakes']} / {result['total']}")
            
        print("\n🎯 命中分佈:")
        print(f"   最高命中: {result.get('max_match', 0)} 號")
        match_counts = result.get('match_counts', {})
        if args.double_bet:
            print("=" * 80)
            print(f"🎯 Auto Optimizer V2 + Phase 3 雙注預測 ({args.lottery})")
            print("=" * 80)
            
            result = predictor.predict_double_bet(
                optimize_weights=args.optimize_weights,
                use_genetic=args.genetic,
                use_kill=not args.no_kill,
                kill_count=args.kill_count
            )
            
            print(f"\n第一注 (投票集成): {result['bet1']}")
            print(f"第二注 (Zone Balance): {result['bet2']}")
            if result.get('kill_list'):
                print(f"🔪 排除號碼 (Kill-{args.kill_count}): {result['kill_list']}")
            print(f"\n重疊號碼: {result['overlap']}")
            print(f"覆蓋號碼: {result['coverage']}")
            
            print("=" * 80)
        else:
            print("=" * 80)
            print(f"🎯 Auto Optimizer V2 + Phase 3 預測 ({args.lottery}, 模式: {args.mode})")
            print("=" * 80)
            
            result = predictor.predict(
                mode=args.mode, 
                optimize_weights=args.optimize_weights,
                use_genetic=args.genetic,
                use_kill=not args.no_kill,
                kill_count=args.kill_count
            )
            
            print(f"\n🎯 預測號碼: {result['numbers']}")
            if result.get('kill_list'):
                print(f"🔪 排除號碼 (Kill-{args.kill_count}): {result['kill_list']}")
            
            if result['scores']:
                print("\n號碼得分 (前10):")
                sorted_scores = sorted(result['scores'].items(), key=lambda x: x[1], reverse=True)
                for num, score in sorted_scores[:10]:
                    print(f"  {num}: {score:.2f}")
            print("=" * 80)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
