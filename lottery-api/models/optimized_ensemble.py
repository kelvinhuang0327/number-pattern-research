"""
優化集成預測策略
使用歷史回測動態計算策略權重，提高預測成功率
"""

import numpy as np
from collections import Counter, defaultdict
from typing import List, Dict, Tuple
import logging
from .genetic_optimizer import GeneticWeightOptimizer

logger = logging.getLogger(__name__)


class OptimizedEnsemblePredictor:
    """
    優化集成預測器
    
    特點：
    1. 歷史回測動態權重：根據各策略歷史表現計算權重
    2. 共識過濾：只選擇多個策略都認可的號碼
    3. 時間衰減：近期表現好的策略獲得更高權重
    """
    
    # 📊 基於 2025 年最新回測與遺傳優化的推薦權重
    RECOMMENDED_WEIGHTS = {
        'DEFAULT': {
            'zone_balance': 0.22,
            'odd_even': 0.20,
            'frequency': 0.12,
            'statistical': 0.20,
            'bayesian': 0.12,
            'monte_carlo': 0.10,
            'trend': 0.10,
            'deviation': 0.08,
            'entropy': 0.08,
            'sota': 0.15,
            'hot_cold': 0.05,
        },
        'POWER_LOTTO': {
            # === SOTA / 元學習 (Meta) ===
            'maml': 0.15,               # 🧠 MAML 元學習 - 修復後更強
            'anomaly': 0.12,            # 🔍 異常檢測 - 捕捉黑天鵝
            'sota': 0.10,               # 🚀 Transformer

            # === 回測驗證的最佳核心策略 ===
            'dynamic_ensemble': 0.15,   # 🥇 平均命中穩定
            'clustering': 0.10,         # 🥈 模式聚類 (降低)
            'bayesian': 0.10,           # 🥉 貝葉斯隨機
            'markov': 0.15,             # ⛓️ 馬可夫鏈 (提升! 0.08→0.15)
            'trend': 0.06,              # 📈 趨勢 (降低)
            'statistical': 0.04,        # 📊 統計基礎 (降低)

            # === 輔助/過濾策略 ===
            'deviation': 0.02,          # 偏差 (單期爆發力強，但長期波動大)
            'zone_balance': 0.01,
            'odd_even': 0.01,
            'entropy': 0.01,
        },
        'BIG_LOTTO': {
            # === 2026-01-03 P0優化: 提升馬可夫鏈權重 ===
            'maml': 0.15,               # 🧠 元學習 (降低 0.18→0.15)
            'anomaly': 0.10,            # 🔍 異常檢測
            'sota': 0.10,               # 🚀 Transformer (降低 0.12→0.10)

            'dynamic_ensemble': 0.12,   # (降低 0.15→0.12)
            'clustering': 0.08,         # (降低 0.10→0.08)
            'bayesian': 0.10,
            'markov': 0.18,             # ⛓️ 馬可夫鏈 (大幅提升! 0.08→0.18) 🔥
            'trend': 0.08,
            'statistical': 0.05,
            'entropy': 0.04,
        }
    }
    
    def __init__(self, unified_engine):
        """
        初始化優化集成預測器
        
        Args:
            unified_engine: UnifiedPredictionEngine 實例
        """
        self.engine = unified_engine
        # 🔧 更新策略列表：加入表現最好的策略，移除失敗的策略
        self.strategy_methods = {
            # === SOTA / Meta ===
            'maml': self.engine.maml_predict,
            'anomaly': self.engine.anomaly_detection_predict,
            'sota': self.engine.sota_predict,

            # === 核心策略 ===
            'dynamic_ensemble': self.engine.dynamic_ensemble_predict,
            'clustering': self.engine.clustering_predict,
            'bayesian': self.engine.bayesian_predict,
            'markov': self.engine.markov_predict,
            'trend': self.engine.trend_predict,
            'statistical': self.engine.statistical_predict,

            # === 輔助/實驗策略 ===
            'deviation': self.engine.deviation_predict,
            'zone_balance': self.engine.zone_balance_predict,
            'odd_even': self.engine.odd_even_balance_predict,
            'entropy': self.engine.entropy_predict,
            'monte_carlo': self.engine.monte_carlo_predict,
            'frequency': self.engine.frequency_predict,
            'hot_cold': self.engine.hot_cold_mix_predict,
        }
        # 緩存策略權重（避免重複計算）
        self._cached_weights = None
        self._cache_history_hash = None
        # 是否使用推薦權重作為基線
        self.use_recommended_baseline = True
        
    def _calculate_history_hash(self, history: List[Dict]) -> str:
        """計算歷史數據的哈希值（用於緩存判斷）"""
        if not history:
            return ""
        # 使用最新和最舊期號作為簡單哈希
        return f"{history[0].get('draw', '')}_{history[-1].get('draw', '')}_{len(history)}"
    
    def calculate_strategy_weights(
        self,
        history: List[Dict],
        lottery_rules: Dict,
        backtest_periods: int = 50,
        training_window: int = 100
    ) -> Dict[str, float]:
        """
        通過歷史回測計算各策略的動態權重
        
        Args:
            history: 完整歷史數據（按時間降序，最新在前）
            lottery_rules: 彩票規則
            backtest_periods: 回測期數
            training_window: 訓練窗口大小
            
        Returns:
            策略權重字典 {'strategy_name': weight}
        """
        # 檢查緩存
        history_hash = self._calculate_history_hash(history)
        if self._cached_weights and self._cache_history_hash == history_hash:
            logger.info("📦 使用緩存的策略權重")
            return self._cached_weights
        
        logger.info(f"🔄 開始回測計算策略權重 (回測{backtest_periods}期, 訓練窗口{training_window}期)")
        
        pick_count = lottery_rules.get('pickCount', 6)
        
        # 確保有足夠的數據
        min_required = training_window + backtest_periods + 1
        if len(history) < min_required:
            logger.warning(f"⚠️ 數據量不足 ({len(history)} < {min_required})，需要 {min_required}，使用均等權重")
            equal_weight = 1.0 / len(self.strategy_methods)
            return {name: equal_weight for name in self.strategy_methods}
        
        # 初始化策略得分
        strategy_scores = {name: [] for name in self.strategy_methods}
        
        # 滾動窗口回測
        for i in range(backtest_periods):
            # 測試期索引（從最新往回數）
            test_idx = i
            # 訓練數據（測試期之後的 training_window 期）
            train_start = test_idx + 1
            train_end = train_start + training_window
            
            if train_end > len(history):
                break
            
            # 訓練數據（按時間升序給策略使用）
            train_data = history[train_start:train_end]
            
            # 實際開獎結果（6個主號碼 + 特別號 = 7個目標）
            actual_numbers = set(history[test_idx]['numbers'])
            special = history[test_idx].get('special')
            if special is not None:
                actual_numbers.add(int(special))  # 加入特別號，變成7個目標
            
            # 對每個策略進行預測和評估
            for strategy_name, strategy_method in self.strategy_methods.items():
                try:
                    result = strategy_method(train_data, lottery_rules)
                    predicted = set(result.get('numbers', []))
                    
                    # 計算命中數
                    matches = len(predicted & actual_numbers)
                    
                    # 時間衰減：近期回測權重更高 (大幅增加衰減係數以提高短期靈敏度)
                    time_weight = np.exp(-0.15 * i)  # 從 -0.02 改為 -0.15
                    weighted_score = matches * time_weight
                    
                    strategy_scores[strategy_name].append(weighted_score)
                except Exception as e:
                    logger.debug(f"策略 {strategy_name} 回測失敗: {e}")
                    strategy_scores[strategy_name].append(0)
        
        # 計算加權平均得分
        avg_scores = {}
        for name, scores in strategy_scores.items():
            if scores:
                avg_scores[name] = sum(scores) / len(scores)
            else:
                avg_scores[name] = 0.5  # 默認得分
        
        # 轉換為權重（使用 softmax 平滑）
        total_score = sum(avg_scores.values())
        if total_score > 0:
            calculated_weights = {name: score / total_score for name, score in avg_scores.items()}
        else:
            equal_weight = 1.0 / len(self.strategy_methods)
            calculated_weights = {name: equal_weight for name in self.strategy_methods}
        
        # 🔧 混合計算權重與推薦權重 (70% 計算, 30% 推薦基線)
        if self.use_recommended_baseline:
            weights = {}
            lottery_name = lottery_rules.get('name', 'DEFAULT')
            # 獲取特定彩種的推薦權重
            if '威力彩' in lottery_name or 'POWER' in lottery_name:
                rec_profile = self.RECOMMENDED_WEIGHTS.get('POWER_LOTTO')
            elif '大樂透' in lottery_name or 'BIG' in lottery_name:
                rec_profile = self.RECOMMENDED_WEIGHTS.get('BIG_LOTTO')
            else:
                rec_profile = self.RECOMMENDED_WEIGHTS.get('DEFAULT')
            
            for name in self.strategy_methods:
                calc_w = calculated_weights.get(name, 0.1)
                rec_w = rec_profile.get(name, 0.1)
                weights[name] = 0.7 * calc_w + 0.3 * rec_w
            
            # 正規化
            total = sum(weights.values())
            if total > 0:
                weights = {k: v / total for k, v in weights.items()}
            
            logger.info("📊 策略權重計算完成 (混合推薦基線):")
        else:
            weights = calculated_weights
            logger.info("📊 策略權重計算完成:")
        
        for name, weight in sorted(weights.items(), key=lambda x: x[1], reverse=True):
            calc_w = calculated_weights.get(name, 0)
            rec_w = self.RECOMMENDED_WEIGHTS.get(name, 0)
            logger.info(f"   {name}: {weight:.1%} (計算: {calc_w:.1%}, 推薦: {rec_w:.1%})")
        
        # 更新緩存
        self._cached_weights = weights
        self._cache_history_hash = history_hash
        
        return weights

    def evolve_weights(self, history: List[Dict], lottery_rules: Dict) -> Dict[str, float]:
        """
        使用遺傳算法進化最優權重 (僅限威力彩)
        """
        lottery_name = lottery_rules.get('name', 'UNKNOWN')
        if 'POWER_LOTTO' not in lottery_name and '威力彩' not in lottery_name:
            # 對於非威力彩，直接返回基礎計算權重，不執行的遺傳優化
            return self.calculate_strategy_weights(history, lottery_rules)

        logger.info("🧬 開始遺傳算法權重進化...")
        optimizer = GeneticWeightOptimizer(list(self.strategy_methods.keys()))
        
        # 定義適應度函數：在過去 10 期中的命中表現
        def fitness_fn(weights: Dict[str, float]) -> float:
            score = 0
            test_window = 10
            for i in range(test_window):
                train_data = history[i+1 : i+1+100]
                actual = set(history[i]['numbers'])
                
                # 集成預測得分 (簡化版)
                votes = defaultdict(float)
                for name, method in self.strategy_methods.items():
                    try:
                        res = method(train_data, lottery_rules)
                        for num in res['numbers']:
                            votes[num] += weights[name]
                    except: continue
                
                top_numbers = sorted(votes.keys(), key=lambda x: votes[x], reverse=True)[:lottery_rules.get('pickCount', 6)]
                score += len(set(top_numbers) & actual)
            return score / test_window

        best_weights = optimizer.optimize(fitness_fn)
        return best_weights
    
    def predict(
        self,
        history: List[Dict],
        lottery_rules: Dict,
        min_consensus: int = 2,
        backtest_periods: int = 50
    ) -> Dict:
        """
        執行優化集成預測
        
        Args:
            history: 歷史數據
            lottery_rules: 彩票規則
            min_consensus: 最少共識數（號碼至少被N個策略推薦）
            
        Returns:
            預測結果字典
        """
        pick_count = lottery_rules.get('pickCount', 6)
        min_num = lottery_rules.get('minNumber', 1)
        max_num = lottery_rules.get('maxNumber', 49)
        
        logger.info("🎯 開始優化集成預測...")
        
        # 1. 計算策略權重
        weights = self.calculate_strategy_weights(history, lottery_rules, backtest_periods=backtest_periods)
        
        # 2. 執行所有策略
        all_predictions = {}
        for strategy_name, strategy_method in self.strategy_methods.items():
            try:
                result = strategy_method(history, lottery_rules)
                all_predictions[strategy_name] = {
                    'numbers': result.get('numbers', []),
                    'confidence': result.get('confidence', 0.5),
                    'weight': weights.get(strategy_name, 0.1)
                }
                logger.info(f"   ✓ {strategy_name}: {result.get('numbers', [])} (權重: {weights.get(strategy_name, 0):.1%})")
            except Exception as e:
                logger.warning(f"   ✗ {strategy_name} 執行失敗: {e}")
        
        if not all_predictions:
            raise ValueError("所有策略執行失敗")
        
        # 3. 加權投票計算號碼得分
        number_scores = defaultdict(float)
        number_consensus = defaultdict(int)  # 記錄每個號碼被多少策略推薦
        
        for strategy_name, pred in all_predictions.items():
            weight = pred['weight']
            confidence = pred['confidence']
            numbers = pred['numbers']
            
            for rank, num in enumerate(numbers):
                # 排名分數（第1名得6分，第6名得1分，對於6個號碼）
                rank_score = (pick_count - rank) / pick_count
                # 加權得分 = 策略權重 × 信心度 × 排名分
                weighted_score = weight * confidence * rank_score * 10
                number_scores[num] += weighted_score
                number_consensus[num] += 1
        
        # 4. 共識過濾：優先選擇多策略認可的號碼
        # 將共識度作為額外加成
        for num in number_scores:
            consensus_bonus = (number_consensus[num] / len(all_predictions)) * 5
            number_scores[num] += consensus_bonus
        
        # 5. 選出得分最高的號碼
        sorted_numbers = sorted(number_scores.items(), key=lambda x: x[1], reverse=True)
        
        # 記錄前15個號碼的得分
        logger.info("📊 號碼得分排名 (前15):")
        for num, score in sorted_numbers[:15]:
            consensus = number_consensus[num]
            logger.info(f"   {num}: {score:.2f} (共識: {consensus})")
        
        # 5. 生成注項
        # ✨ 新增：對於威力彩 2 注場景，使用 Power Dual Max 策略
        lottery_name = lottery_rules.get('name', '')
        if ('POWER_LOTTO' in lottery_name or '威力彩' in lottery_name):
            from .multi_bet_optimizer import multi_bet_optimizer
            
            # 使用多注優化器生成 2 注極效預測
            # 轉換為 generate_diversified_bets 需要的格式
            dual_max_res = multi_bet_optimizer.generate_diversified_bets(
                history, lottery_rules, num_bets=2, 
                meta_config={'method': 'dual_max'}
            )
            
            bet1_data = dual_max_res['bets'][0]
            bet2_data = dual_max_res['bets'][1]
            bet1 = bet1_data['numbers']
            bet2 = bet2_data['numbers']
            bet1_special = bet1_data['special']
            bet2_special = bet2_data['special']
            
            # 輔助變量用於下方的信心度計算
            top_numbers = bet1 + bet2
            
            logger.info(f"🔥 使用 Power Dual Max 策略生成注項")
        else:
            # 默認邏輯：選出 Top 12 號碼並對半分
            top_numbers = [num for num, _ in sorted_numbers[:pick_count * 2]]
            
            # 確保有足夠號碼
            if len(top_numbers) < pick_count * 2:
                for num in range(min_num, max_num + 1):
                    if num not in top_numbers:
                        top_numbers.append(num)
                    if len(top_numbers) >= pick_count * 2:
                        break
            
            bet1 = sorted(top_numbers[:pick_count])
            bet2 = sorted(top_numbers[pick_count:pick_count * 2])
            
            # 🔧 預測特別號碼 (使用增強版建模)
            from .unified_predictor import predict_special_number
            bet1_special = predict_special_number(history, lottery_rules, bet1, strategy_name='statistical')
            bet2_special = predict_special_number(history, lottery_rules, bet2, strategy_name='statistical')
        
        # 計算信心度
        bet1_score = sum(number_scores.get(n, 0) for n in bet1) / pick_count
        bet2_score = sum(number_scores.get(n, 0) for n in bet2) / pick_count
        max_score = max(number_scores.values()) if number_scores else 1
        
        bet1_confidence = min(0.95, bet1_score / max_score)
        bet2_confidence = min(0.90, bet2_score / max_score)
        
        # 計算整體信心度
        avg_consensus = sum(number_consensus.get(n, 0) for n in top_numbers[:pick_count]) / pick_count
        consensus_ratio = avg_consensus / len(all_predictions)
        overall_confidence = 0.7 + consensus_ratio * 0.2
        
        logger.info(f"✅ 優化集成預測完成 - 第一注: {bet1}, 第二注: {bet2}")
        
        return {
            'bet1': {
                'numbers': bet1,
                'special': bet1_special,
                'confidence': float(bet1_confidence)
            },
            'bet2': {
                'numbers': bet2,
                'special': bet2_special,
                'confidence': float(bet2_confidence)
            },
            'method': '優化集成預測',
            'overall_confidence': float(overall_confidence),
            'strategy_weights': weights,
            'consensus_stats': {
                'avg_consensus': float(avg_consensus),
                'strategies_used': len(all_predictions)
            }
        }
    
    def predict_single(
        self,
        history: List[Dict],
        lottery_rules: Dict
    ) -> Dict:
        """
        單注優化集成預測 (包含後處理優化)

        優化包含：
        1. 連號約束 (60% 開獎含連號)
        2. 特別號權重 (基於 2025 年分布)
        3. 總和過濾 (89-136 範圍)
        4. 區域平衡 (低/中/高)

        Returns:
            單注預測結果
        """
        result = self.predict(history, lottery_rules)

        numbers = result['bet1']['numbers']
        confidence = result['bet1']['confidence']

        # 應用後處理優化
        lottery_name = lottery_rules.get('name', '')

        # === 威力彩優化 ===
        if 'POWER_LOTTO' in lottery_name or '威力彩' in lottery_name:
            try:
                from .prediction_optimizer import optimize_power_lotto_prediction
                from .special_predictor import get_enhanced_special_prediction

                # 先預測特別號
                predicted_special = get_enhanced_special_prediction(
                    history, lottery_rules, numbers
                )

                # 應用優化
                optimized_numbers, optimized_special = optimize_power_lotto_prediction(
                    numbers,
                    predicted_special,
                    history,
                    lottery_rules
                )

                return {
                    'numbers': optimized_numbers,
                    'special': optimized_special,
                    'confidence': min(confidence + 0.03, 0.85),
                    'method': '優化集成預測 (含後處理)',
                    'strategy_weights': result['strategy_weights'],
                    'optimizations': ['連號約束', '特別號優化', '總和過濾', '區域平衡']
                }
            except Exception as e:
                logger.warning(f"威力彩預測優化失敗: {e}")

        # === 大樂透優化 ===
        # 注意：大樂透特別號是從同一池開出的第7球，不需要獨立預測
        # 只需優化主號預測，驗證時再比對特別號
        elif 'BIG_LOTTO' in lottery_name or '大樂透' in lottery_name:
            try:
                from .big_lotto_optimizer import optimize_big_lotto_prediction

                # 大樂透不需要預測特別號，傳入 None
                optimized_numbers, _ = optimize_big_lotto_prediction(
                    numbers,
                    None,  # 不預測特別號
                    history,
                    lottery_rules
                )

                return {
                    'numbers': optimized_numbers,
                    'special': None,  # 大樂透不預測特別號
                    'confidence': min(confidence + 0.03, 0.85),
                    'method': '優化集成預測 (含後處理)',
                    'strategy_weights': result['strategy_weights'],
                    'optimizations': ['連號約束', '總和過濾', '區域平衡']
                }
            except Exception as e:
                logger.warning(f"大樂透預測優化失敗: {e}")

        return {
            'numbers': numbers,
            'confidence': confidence,
            'method': '優化集成預測',
            'strategy_weights': result['strategy_weights']
        }


def create_optimized_ensemble_predictor(unified_engine) -> OptimizedEnsemblePredictor:
    """
    工廠函數：創建優化集成預測器
    """
    return OptimizedEnsemblePredictor(unified_engine)
