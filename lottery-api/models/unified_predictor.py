"""
統一預測引擎 - Python 版本 (優化版)
整合所有預測策略，利用 Python 強大的數據科學庫提高預測準確率
"""
import numpy as np
import pandas as pd
from typing import List, Dict, Tuple, Optional
from collections import Counter, defaultdict
import logging
import random
from scipy import stats
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler

# 延遲導入高級策略（避免循環依賴）
_advanced_strategies = None

def get_advanced_strategies():
    global _advanced_strategies
    if _advanced_strategies is None:
        from .advanced_strategies import AdvancedStrategies
        _advanced_strategies = AdvancedStrategies()
    return _advanced_strategies

logger = logging.getLogger(__name__)

def get_data_range_info(history: List[Dict]) -> Dict:
    """
    獲取數據範圍信息（用於日誌和返回結果）

    Args:
        history: 歷史數據列表

    Returns:
        包含數據範圍信息的字典
    """
    if not history:
        return {
            'startDraw': None,
            'endDraw': None,
            'startDate': None,
            'endDate': None,
            'totalPeriods': 0
        }

    return {
        'startDraw': history[0].get('draw'),
        'endDraw': history[-1].get('draw'),
        'startDate': history[0].get('date'),
        'endDate': history[-1].get('date'),
        'totalPeriods': len(history)
    }

def log_data_range(method_name: str, history: List[Dict]):
    """
    記錄數據範圍日誌

    Args:
        method_name: 預測方法名稱
        history: 歷史數據列表
    """
    if not history:
        logger.warning(f"📊 [{method_name}] 數據範圍: 無數據")
        return

    info = get_data_range_info(history)
    logger.info(
        f"📊 [{method_name}] 數據範圍: "
        f"{info['startDraw']} - {info['endDraw']} "
        f"({info['startDate']} ~ {info['endDate']}) "
        f"共 {info['totalPeriods']} 期"
    )

def predict_special_number(
    history: List[Dict],
    lottery_rules: Dict,
    main_predicted_numbers: List[int] = None
) -> Optional[int]:
    """
    預測特別號碼（統一輔助函數）

    Args:
        history: 歷史數據
        lottery_rules: 彩票規則
        main_predicted_numbers: 主號碼預測結果（用於排除重複）

    Returns:
        預測的特別號碼，如果不需要則返回 None
    """
    # 檢查是否有特別號碼
    has_special = lottery_rules.get('hasSpecialNumber', False)
    if not has_special:
        return None

    # 獲取特別號碼範圍
    special_range = lottery_rules.get('specialNumberRange')
    if not special_range:
        special_range = lottery_rules.get('numberRange', {'min': 1, 'max': 49})

    min_special = special_range.get('min', 1)
    max_special = special_range.get('max', 49)

    # 統計歷史特別號碼頻率
    special_frequency = Counter()
    valid_specials = 0

    for draw in history:
        special = draw.get('special')
        if special and isinstance(special, (int, float)) and min_special <= special <= max_special:
            special_frequency[int(special)] += 1
            valid_specials += 1

    # 如果沒有足夠的歷史數據，使用頻率+隨機混合策略
    if valid_specials < 10:
        # 使用主號碼的頻率作為參考
        all_numbers = [num for draw in history for num in draw.get('numbers', [])]
        general_frequency = Counter(all_numbers)

        # 結合主號碼頻率和隨機性
        probabilities = {}
        for num in range(min_special, max_special + 1):
            # 基礎概率
            base_prob = 1.0 / (max_special - min_special + 1)
            # 如果這個號碼在主號碼中出現過，稍微提高概率
            freq_bonus = general_frequency.get(num, 0) / len(history) if history else 0
            probabilities[num] = base_prob + freq_bonus * 0.1
    else:
        # 使用特別號碼歷史頻率
        total = sum(special_frequency.values())
        probabilities = {}

        for num in range(min_special, max_special + 1):
            freq = special_frequency.get(num, 0)
            # 頻率分析 + 輕微均值回歸
            expected_freq = total / (max_special - min_special + 1)
            deviation = freq - expected_freq

            # 如果低於預期，稍微提高概率（均值回歸理論）
            if deviation < 0:
                probabilities[num] = (freq + abs(deviation) * 0.3) / total
            else:
                probabilities[num] = freq / total

    # 排除與主號碼重複（針對大樂透等特別號與主號不重複的彩票）
    # 威力彩的特別號範圍不同，不會與主號碼重複
    if main_predicted_numbers and max_special == lottery_rules.get('numberRange', {}).get('max', 49):
        for num in main_predicted_numbers:
            if min_special <= num <= max_special and num in probabilities:
                probabilities[num] *= 0.05  # 大幅降低重複概率

    # 歸一化概率
    total_prob = sum(probabilities.values())
    if total_prob > 0:
        for num in probabilities:
            probabilities[num] /= total_prob

    # 選擇概率最高的號碼（帶隨機性）
    if probabilities:
        sorted_probs = sorted(probabilities.items(), key=lambda x: x[1], reverse=True)

        # 70% 選擇最高概率，30% 從前5名中隨機
        if random.random() < 0.7:
            predicted_special = sorted_probs[0][0]
        else:
            top_5 = sorted_probs[:min(5, len(sorted_probs))]
            weights = [prob for _, prob in top_5]
            predicted_special = random.choices([num for num, _ in top_5], weights=weights, k=1)[0]

        logger.debug(f"預測特別號碼: {predicted_special} (範圍: {min_special}-{max_special})")
        return int(predicted_special)

    # 兜底：完全隨機
    return random.randint(min_special, max_special)

class UnifiedPredictionEngine:
    """
    統一預測引擎
    整合多種預測策略，提供統一的預測接口
    """
    
    def __init__(self):
        self.scaler = StandardScaler()
        logger.info("UnifiedPredictionEngine 初始化完成 (優化版)")
    
    # ===== 核心統計策略 =====
    
    def trend_predict(
        self,
        history: List[Dict],
        lottery_rules: Dict
    ) -> Dict:
        """
        趨勢分析策略 (指數衰減)
        """
        # 🔧 記錄數據範圍
        log_data_range('趨勢回歸分析', history)

        pick_count = lottery_rules.get('pickCount', 6)
        min_num = lottery_rules.get('minNumber', 1)
        max_num = lottery_rules.get('maxNumber', 49)
        
        weighted_frequency = defaultdict(float)
        lambda_val = 0.05  # 衰減係數
        
        # history[-1] 是最新一期，但在計算時我們通常遍歷
        # 為了計算 age，我們倒序遍歷
        # index 0 is latest (age=0)
        
        for i, draw in enumerate(reversed(history)):
            age = i
            weight = np.exp(-lambda_val * age)
            
            for num in draw['numbers']:
                weighted_frequency[num] += weight
                
        total_weight = sum(weighted_frequency.values())
        probabilities = {}
        for i in range(min_num, max_num + 1):
            probabilities[i] = weighted_frequency.get(i, 0) / total_weight if total_weight > 0 else 0
            
        sorted_numbers = sorted(probabilities.items(), key=lambda x: x[1], reverse=True)
        predicted_numbers = sorted([num for num, _ in sorted_numbers[:pick_count]])
        
        # 🔧 預測特別號碼
        predicted_special = predict_special_number(history, lottery_rules, predicted_numbers)

        result = {
            'numbers': predicted_numbers,
            'confidence': 0.75,
            'method': '趨勢回歸分析 (指數衰減)',
            'probabilities': [prob for _, prob in sorted_numbers[:pick_count]],
            'dataRange': get_data_range_info(history)  # 🔧 添加數據範圍信息
        }

        # 🔧 添加特別號碼
        if predicted_special is not None:
            result['special'] = predicted_special

        return result

    def deviation_predict(
        self, 
        history: List[Dict], 
        lottery_rules: Dict
    ) -> Dict:
        """
        偏差追蹤策略 (標準差與均值回歸)
        """
        pick_count = lottery_rules.get('pickCount', 6)
        min_num = lottery_rules.get('minNumber', 1)
        max_num = lottery_rules.get('maxNumber', 49)
        total_numbers = max_num - min_num + 1
        
        # 計算理論頻率
        expected_freq = (len(history) * pick_count) / total_numbers
        
        # 計算實際頻率
        all_numbers = [num for draw in history for num in draw['numbers']]
        frequency = Counter(all_numbers)
        
        # 計算標準差
        sum_sq_diff = 0
        for i in range(min_num, max_num + 1):
            diff = frequency.get(i, 0) - expected_freq
            sum_sq_diff += diff * diff
        std_dev = np.sqrt(sum_sq_diff / total_numbers)
        
        probabilities = {}
        for i in range(min_num, max_num + 1):
            freq = frequency.get(i, 0)
            z_score = (freq - expected_freq) / std_dev if std_dev > 0 else 0
            
            # 評分邏輯 (與 JS 版本一致)
            if z_score < -1.5:
                # 強烈負偏差 (很久沒出)，預期回歸
                probabilities[i] = 0.8 + abs(z_score) * 0.1
            elif z_score > 2.0:
                # 強烈正偏差 (太熱)，預期冷卻
                probabilities[i] = 0.2
            elif 0.5 < z_score < 1.5:
                # 溫和正偏差 (趨勢剛起)，預期續熱
                probabilities[i] = 0.6 + z_score * 0.1
            else:
                probabilities[i] = 0.4
                
        # 正規化
        total_prob = sum(probabilities.values())
        for i in probabilities:
            probabilities[i] = probabilities[i] / total_prob if total_prob > 0 else 1.0 / total_numbers
            
        sorted_numbers = sorted(probabilities.items(), key=lambda x: x[1], reverse=True)
        predicted_numbers = sorted([num for num, _ in sorted_numbers[:pick_count]])
        
        # 🔧 預測特別號碼
        predicted_special = predict_special_number(history, lottery_rules, predicted_numbers)
        
        result = {
            'numbers': predicted_numbers,
            'confidence': 0.76,
            'method': '偏差追蹤模型',
            'probabilities': [prob for _, prob in sorted_numbers[:pick_count]]
        }
        
        # 🔧 添加特別號碼
        if predicted_special is not None:
            result['special'] = predicted_special
        
        return result

    
    def frequency_predict(
        self,
        history: List[Dict],
        lottery_rules: Dict
    ) -> Dict:
        """
        頻率分析策略 (優化版：自適應時間衰減加權)
        不僅統計次數，還考慮時間權重，最近的號碼權重更高
        ✨ 優化：根據號碼出現頻率動態調整衰減係數
        """
        # 🔧 記錄數據範圍
        log_data_range('頻率分析', history)

        pick_count = lottery_rules.get('pickCount', 6)
        min_num = lottery_rules.get('minNumber', 1)
        max_num = lottery_rules.get('maxNumber', 49)

        # 初始化權重字典
        weighted_counts = defaultdict(float)
        total_weight = 0

        # ✨ 優化：先計算基礎頻率用於自適應衰減
        basic_freq = Counter([num for draw in history for num in draw['numbers']])
        total_draws = len(history)
        theoretical_avg_freq = total_draws * pick_count / (max_num - min_num + 1)

        # 從最新的數據開始遍歷
        for i, draw in enumerate(reversed(history)):
            # i 是距離現在的期數 (0, 1, 2...)

            for num in draw['numbers']:
                # ✨ 優化：為每個號碼計算自適應衰減係數
                decay_rate = self._adaptive_decay_rate(
                    basic_freq.get(num, 0),
                    theoretical_avg_freq
                )

                weight = np.exp(-decay_rate * i)
                weighted_counts[num] += weight
                total_weight += weight

        # 轉換為列表並排序
        sorted_numbers = sorted(weighted_counts.items(), key=lambda x: x[1], reverse=True)
        predicted_numbers = sorted([num for num, _ in sorted_numbers[:pick_count]])

        # ✨ 優化：動態計算信心度
        top_weights = [w for _, w in sorted_numbers[:pick_count]]
        avg_weight = np.mean(list(weighted_counts.values())) if weighted_counts else 1

        # 基礎信心度
        base_confidence = 0.5 + (np.mean(top_weights) / avg_weight - 1) * 0.2

        # 數據量加成
        data_bonus = min(total_draws / 300, 0.15)  # 最多 +15%

        # 集中度加成（top 號碼權重差異小表示更集中）
        if len(top_weights) > 1:
            concentration = 1 - (np.std(top_weights) / np.mean(top_weights))
            concentration_bonus = concentration * 0.15  # 最多 +15%
        else:
            concentration_bonus = 0

        final_confidence = min(0.90, base_confidence + data_bonus + concentration_bonus)

        # 🔧 預測特別號碼
        predicted_special = predict_special_number(history, lottery_rules, predicted_numbers)
        
        result = {
            'numbers': predicted_numbers,
            'confidence': float(final_confidence),
            'method': '自適應頻率分析',
            'probabilities': [float(w / total_weight) for _, w in sorted_numbers[:pick_count]],
            'dataRange': get_data_range_info(history)  # 🔧 添加數據範圍信息
        }

        # 🔧 添加特別號碼
        if predicted_special is not None:
            result['special'] = predicted_special

        return result

    def _adaptive_decay_rate(self, number_frequency: int, avg_frequency: float) -> float:
        """
        自適應衰減係數計算

        策略：
        - 高頻號碼：更快衰減（避免過度依賴歷史）
        - 低頻號碼：較慢衰減（捕捉長期模式）
        - 平均頻率號碼：標準衰減
        """
        if avg_frequency == 0:
            return 0.01  # 默認值

        freq_ratio = number_frequency / avg_frequency

        if freq_ratio > 1.3:
            # 高頻號碼（超過平均 30%）
            return 0.018  # 更快衰減
        elif freq_ratio > 1.1:
            # 稍高頻號碼
            return 0.013
        elif freq_ratio < 0.7:
            # 低頻號碼（低於平均 30%）
            return 0.007  # 較慢衰減
        elif freq_ratio < 0.9:
            # 稍低頻號碼
            return 0.009
        else:
            # 平均頻率
            return 0.01  # 標準衰減
    
    def bayesian_predict(
        self,
        history: List[Dict],
        lottery_rules: Dict
    ) -> Dict:
        """
        貝葉斯預測策略 (優化版：動態權重調整)
        使用貝葉斯統計方法，考慮先驗概率和條件概率
        根據數據量和穩定性動態調整權重
        """
        pick_count = lottery_rules.get('pickCount', 6)
        min_num = lottery_rules.get('minNumber', 1)
        max_num = lottery_rules.get('maxNumber', 49)

        # 1. 計算先驗概率 (Prior) - 基於長期歷史
        all_numbers = []
        for draw in history:
            all_numbers.extend(draw['numbers'])

        long_term_freq = Counter(all_numbers)
        total_draws = len(history)

        # 2. 計算似然概率 (Likelihood) - 基於近期趨勢 (最近 20 期)
        recent_window = 20
        recent_history = history[-recent_window:] if len(history) > recent_window else history
        recent_numbers = []
        for draw in recent_history:
            recent_numbers.extend(draw['numbers'])

        recent_freq = Counter(recent_numbers)

        # ✨ 優化：計算近期數據的穩定性
        recent_stability = self._calculate_stability(recent_history, pick_count)

        # ✨ 優化：動態調整先驗/似然權重
        likelihood_weight, prior_weight = self._adaptive_bayesian_weights(
            total_draws,
            recent_stability
        )

        # 3. 計算後驗概率 (Posterior)
        posterior_probs = {}
        for num in range(min_num, max_num + 1):
            # P(A): 該號碼的長期概率
            prior = long_term_freq.get(num, 0) / (total_draws * pick_count)
            # 平滑處理，避免 0 概率
            if prior == 0: prior = 1 / (total_draws * pick_count * 10)

            # P(B|A): 在近期出現的概率 (似然)
            likelihood = recent_freq.get(num, 0) / len(recent_history)

            # ✨ 優化：使用動態權重計算後驗
            posterior = (likelihood * likelihood_weight + prior * prior_weight)
            posterior_probs[num] = posterior

        # 選擇後驗概率最高的號碼
        sorted_numbers = sorted(posterior_probs.items(), key=lambda x: x[1], reverse=True)
        predicted_numbers = sorted([num for num, _ in sorted_numbers[:pick_count]])

        # ✨ 優化：動態計算信心度
        base_confidence = 0.68
        stability_bonus = recent_stability * 0.08  # 穩定性加成 (最多 +8%)
        data_bonus = min(total_draws / 200, 0.06)  # 數據量加成 (最多 +6%)
        final_confidence = min(0.82, base_confidence + stability_bonus + data_bonus)

        # 🔧 預測特別號碼
        predicted_special = predict_special_number(history, lottery_rules, predicted_numbers)
        
        result = {
            'numbers': predicted_numbers,
            'confidence': float(final_confidence),
            'method': f'貝葉斯統計 (動態權重: {likelihood_weight:.1%}/{prior_weight:.1%})',
            'probabilities': [float(prob) for _, prob in sorted_numbers[:pick_count]]
        }
        
        # 🔧 添加特別號碼
        if predicted_special is not None:
            result['special'] = predicted_special
        
        return result

    def _adaptive_bayesian_weights(self, history_size: int, recent_stability: float) -> Tuple[float, float]:
        """
        動態調整貝葉斯權重

        策略：
        - 數據少且穩定：更信任似然（近期趨勢）
        - 數據多且穩定：平衡兩者
        - 數據多但波動：更信任先驗（長期模式）
        """
        if history_size < 50:
            # 數據少，更依賴近期
            return (0.75, 0.25)  # (似然, 先驗)
        elif history_size < 100:
            # 中等數據量
            if recent_stability > 0.7:
                # 穩定期，平衡
                return (0.65, 0.35)
            else:
                # 波動期，稍微依賴長期
                return (0.55, 0.45)
        else:
            # 大量數據
            if recent_stability > 0.7:
                # 穩定期，平衡兩者
                return (0.6, 0.4)
            else:
                # 波動期，更依賴長期模式
                return (0.5, 0.5)

    def _calculate_stability(self, history: List[Dict], pick_count: int) -> float:
        """
        計算近期數據的穩定性（基於號碼頻率的變異係數）

        返回值：0-1，越高表示越穩定
        """
        if len(history) < 5:
            return 0.5  # 數據太少，返回中等穩定性

        # 計算每個號碼的出現頻率
        all_nums = [num for draw in history for num in draw['numbers']]
        freq = Counter(all_nums)

        # 計算頻率的變異係數 (CV = std / mean)
        freq_values = list(freq.values())
        if len(freq_values) < 2:
            return 0.5

        mean_freq = np.mean(freq_values)
        std_freq = np.std(freq_values)

        if mean_freq == 0:
            return 0.5

        cv = std_freq / mean_freq

        # 將 CV 轉換為穩定性分數 (CV 越小，穩定性越高)
        # CV 通常在 0-2 範圍內，我們映射到 0-1
        stability = 1 / (1 + cv)

        return float(stability)
    
    def markov_predict(
        self,
        history: List[Dict],
        lottery_rules: Dict
    ) -> Dict:
        """
        馬可夫鏈預測策略 (✨ 優化版：多階轉移矩陣)
        分析號碼之間的轉移概率，支援 1-3 階轉移矩陣，動態選擇最優階數
        """
        pick_count = lottery_rules.get('pickCount', 6)
        min_num = lottery_rules.get('minNumber', 1)
        max_num = lottery_rules.get('maxNumber', 49)

        # ✨ 優化：根據數據量動態選擇最優階數
        optimal_order, order_confidence = self._find_optimal_markov_order(
            history, max_num, pick_count
        )

        # ✨ 優化：使用多階轉移矩陣融合預測
        if optimal_order == 1:
            next_probs = self._markov_order1(history, max_num, pick_count)
            method_name = '馬可夫鏈 (1階轉移)'
        elif optimal_order == 2:
            next_probs = self._markov_order2(history, max_num, pick_count)
            method_name = '馬可夫鏈 (2階轉移)'
        else:
            next_probs = self._markov_order3(history, max_num, pick_count)
            method_name = '馬可夫鏈 (3階轉移)'

        # ✨ 優化：排除最近一期號碼（降低重複概率）
        last_numbers = history[-1]['numbers']
        for num in last_numbers:
            if num <= max_num:
                next_probs[num] *= 0.3

        # 選擇概率最高的號碼
        next_probs[0] = -1  # 排除 0 號索引

        sorted_indices = np.argsort(next_probs)[::-1]
        predicted_numbers = []

        for idx in sorted_indices:
            if min_num <= idx <= max_num:
                predicted_numbers.append(int(idx))
            if len(predicted_numbers) >= pick_count:
                break

        predicted_numbers.sort()

        # ✨ 優化：動態計算信心度
        base_confidence = 0.65
        order_bonus = (optimal_order - 1) * 0.04  # 高階轉移 +4% per order
        data_bonus = min(len(history) / 300, 0.08)

        final_confidence = min(0.77, base_confidence + order_bonus + data_bonus + order_confidence)

        # 🔧 預測特別號碼
        predicted_special = predict_special_number(history, lottery_rules, predicted_numbers)
        
        result = {
            'numbers': predicted_numbers,
            'confidence': final_confidence,
            'method': method_name,
            'probabilities': [float(next_probs[num]) for num in predicted_numbers]
        }
        
        # 🔧 添加特別號碼
        if predicted_special is not None:
            result['special'] = predicted_special
        
        return result

    def _find_optimal_markov_order(
        self,
        history: List[Dict],
        max_num: int,
        pick_count: int
    ) -> tuple:
        """
        ✨ 新方法：動態選擇最優馬可夫階數

        根據數據量和穩定性選擇 1-3 階：
        - 數據少 (<50期): 1階 (避免過擬合)
        - 數據中 (50-150期): 2階
        - 數據多 (>150期): 3階
        """
        history_size = len(history)

        # 數據量不足，使用 1 階
        if history_size < 50:
            return (1, 0.0)

        # 計算轉移穩定性（相鄰期數的相似度）
        stability = self._calculate_transition_stability(history[-50:], pick_count)

        # 數據量中等，使用 2 階
        if history_size < 150:
            confidence_bonus = stability * 0.05
            return (2, confidence_bonus)

        # 數據量充足，使用 3 階
        confidence_bonus = stability * 0.07
        return (3, confidence_bonus)

    def _calculate_transition_stability(
        self,
        history: List[Dict],
        pick_count: int
    ) -> float:
        """
        ✨ 新方法：計算轉移穩定性

        使用 Jaccard 相似度衡量相鄰期數的重疊程度
        """
        if len(history) < 2:
            return 0.5

        similarities = []
        for i in range(len(history) - 1):
            current_set = set(history[i]['numbers'])
            next_set = set(history[i + 1]['numbers'])

            intersection = len(current_set & next_set)
            union = len(current_set | next_set)

            if union > 0:
                similarity = intersection / union
                similarities.append(similarity)

        if not similarities:
            return 0.5

        # 返回平均相似度
        avg_similarity = sum(similarities) / len(similarities)
        return float(avg_similarity)

    def _markov_order1(
        self,
        history: List[Dict],
        max_num: int,
        pick_count: int
    ) -> np.ndarray:
        """
        ✨ 新方法：1階馬可夫轉移矩陣

        P(X_t | X_{t-1})
        """
        # 構建轉移矩陣 (拉普拉斯平滑)
        transition_matrix = np.ones((max_num + 1, max_num + 1)) * 0.1

        analysis_history = history[-100:] if len(history) > 100 else history

        for i in range(len(analysis_history) - 1):
            current_numbers = analysis_history[i]['numbers']
            next_numbers = analysis_history[i + 1]['numbers']

            for curr_num in current_numbers:
                for next_num in next_numbers:
                    # 越近期的轉移越重要
                    weight = 1.0 + (i / len(analysis_history))
                    transition_matrix[curr_num][next_num] += weight

        # 正規化
        row_sums = transition_matrix.sum(axis=1, keepdims=True)
        transition_matrix = transition_matrix / row_sums

        # 從最近一期預測
        last_numbers = history[-1]['numbers']
        next_probs = np.zeros(max_num + 1)

        for num in last_numbers:
            if num <= max_num:
                next_probs += transition_matrix[num]

        return next_probs

    def _markov_order2(
        self,
        history: List[Dict],
        max_num: int,
        pick_count: int
    ) -> np.ndarray:
        """
        ✨ 新方法：2階馬可夫轉移矩陣

        P(X_t | X_{t-1}, X_{t-2})
        使用狀態對 (num1, num2) -> next_num 的轉移概率
        """
        # 構建 2階轉移字典：(num1, num2) -> Counter(next_nums)
        transition_dict = {}

        analysis_history = history[-80:] if len(history) > 80 else history

        for i in range(len(analysis_history) - 2):
            prev2_numbers = analysis_history[i]['numbers']
            prev1_numbers = analysis_history[i + 1]['numbers']
            next_numbers = analysis_history[i + 2]['numbers']

            # 為所有 (prev2, prev1) 組合記錄轉移
            for num2 in prev2_numbers:
                for num1 in prev1_numbers:
                    state = (num2, num1)
                    if state not in transition_dict:
                        transition_dict[state] = Counter()

                    for next_num in next_numbers:
                        weight = 1.0 + (i / len(analysis_history))
                        transition_dict[state][next_num] += weight

        # 從最近兩期預測
        if len(history) >= 2:
            prev2_numbers = history[-2]['numbers']
            prev1_numbers = history[-1]['numbers']
        else:
            # 數據不足，回退到 1階
            return self._markov_order1(history, max_num, pick_count)

        next_probs = np.zeros(max_num + 1)
        total_weight = 0

        for num2 in prev2_numbers:
            for num1 in prev1_numbers:
                state = (num2, num1)
                if state in transition_dict:
                    for next_num, count in transition_dict[state].items():
                        next_probs[next_num] += count
                        total_weight += count

        # 正規化
        if total_weight > 0:
            next_probs = next_probs / total_weight
        else:
            # 沒有匹配的轉移，回退到 1階
            return self._markov_order1(history, max_num, pick_count)

        return next_probs

    def _markov_order3(
        self,
        history: List[Dict],
        max_num: int,
        pick_count: int
    ) -> np.ndarray:
        """
        ✨ 新方法：3階馬可夫轉移矩陣

        P(X_t | X_{t-1}, X_{t-2}, X_{t-3})
        使用狀態三元組 (num1, num2, num3) -> next_num 的轉移概率
        """
        # 構建 3階轉移字典
        transition_dict = {}

        analysis_history = history[-60:] if len(history) > 60 else history

        for i in range(len(analysis_history) - 3):
            prev3_numbers = analysis_history[i]['numbers']
            prev2_numbers = analysis_history[i + 1]['numbers']
            prev1_numbers = analysis_history[i + 2]['numbers']
            next_numbers = analysis_history[i + 3]['numbers']

            # 為所有 (prev3, prev2, prev1) 組合記錄轉移
            for num3 in prev3_numbers:
                for num2 in prev2_numbers:
                    for num1 in prev1_numbers:
                        state = (num3, num2, num1)
                        if state not in transition_dict:
                            transition_dict[state] = Counter()

                        for next_num in next_numbers:
                            weight = 1.0 + (i / len(analysis_history))
                            transition_dict[state][next_num] += weight

        # 從最近三期預測
        if len(history) >= 3:
            prev3_numbers = history[-3]['numbers']
            prev2_numbers = history[-2]['numbers']
            prev1_numbers = history[-1]['numbers']
        else:
            # 數據不足，回退到 2階
            return self._markov_order2(history, max_num, pick_count)

        next_probs = np.zeros(max_num + 1)
        total_weight = 0

        for num3 in prev3_numbers:
            for num2 in prev2_numbers:
                for num1 in prev1_numbers:
                    state = (num3, num2, num1)
                    if state in transition_dict:
                        for next_num, count in transition_dict[state].items():
                            next_probs[next_num] += count
                            total_weight += count

        # 正規化
        if total_weight > 0:
            next_probs = next_probs / total_weight
        else:
            # 沒有匹配的轉移，回退到 2階
            return self._markov_order2(history, max_num, pick_count)

        return next_probs
    
    def monte_carlo_predict(
        self, 
        history: List[Dict], 
        lottery_rules: Dict,
        simulations: int = 20000  # 增加模擬次數
    ) -> Dict:
        """
        蒙地卡羅模擬策略
        通過大量隨機模擬來預測
        """
        pick_count = lottery_rules.get('pickCount', 6)
        min_num = lottery_rules.get('minNumber', 1)
        max_num = lottery_rules.get('maxNumber', 49)
        
        # 計算歷史頻率作為基礎權重
        all_numbers = []
        for draw in history:
            all_numbers.extend(draw['numbers'])
        
        frequency = Counter(all_numbers)
        total_draws = len(history)
        
        # 創建加權池
        weights = np.zeros(max_num + 1)
        for num in range(min_num, max_num + 1):
            # 基礎權重 + 頻率權重 + 隨機擾動
            freq_weight = (frequency.get(num, 0) / total_draws) * 10
            weights[num] = 1.0 + freq_weight
            
        # 正規化權重
        weights = weights / weights.sum()
        
        # 執行蒙地卡羅模擬
        simulation_results = Counter()
        
        # 使用 numpy 的高效採樣
        valid_range = np.arange(min_num, max_num + 1)
        valid_weights = weights[min_num:max_num + 1]
        valid_weights = valid_weights / valid_weights.sum()
        
        for _ in range(simulations):
            selected = np.random.choice(
                valid_range,
                size=pick_count,
                replace=False,
                p=valid_weights
            )
            for num in selected:
                simulation_results[num] += 1
        
        # 選擇模擬中出現最多的號碼
        most_common = simulation_results.most_common(pick_count)
        predicted_numbers = sorted([num for num, _ in most_common])
        
        # 🔧 預測特別號碼
        predicted_special = predict_special_number(history, lottery_rules, predicted_numbers)
        
        result = {
            'numbers': predicted_numbers,
            'confidence': 0.72,
            'method': f'蒙地卡羅模擬 ({simulations}次)',
            'probabilities': [count / simulations for _, count in most_common]
        }
        
        # 🔧 添加特別號碼
        if predicted_special is not None:
            result['special'] = predicted_special
        
        return result
    
    # ===== 民間策略 (保持不變，因為邏輯簡單且固定) =====
    
    def odd_even_balance_predict(self, history, lottery_rules):
        """
        奇偶平衡策略 (優化版：位置分佈分析)
        ✨ 優化：不只看奇偶數量，還分析奇偶號碼在各位置的分佈模式
        """
        pick_count = lottery_rules.get('pickCount', 6)
        min_num = lottery_rules.get('minNumber', 1)
        max_num = lottery_rules.get('maxNumber', 49)

        # 1. 計算目標奇偶數量（原有邏輯）
        odd_counts = [sum(1 for num in draw['numbers'] if num % 2 == 1) for draw in history[-50:]]
        target_odd = round(np.mean(odd_counts))
        target_even = pick_count - target_odd

        # ✨ 優化：分析每個位置的奇偶傾向
        position_odd_preference = self._analyze_position_odd_preference(history, pick_count)

        # 2. 計算號碼頻率
        all_numbers = [num for draw in history for num in draw['numbers']]
        frequency = Counter(all_numbers)

        # ✨ 優化：計算每個號碼的綜合分數（頻率 + 位置適配度）
        odd_scores = {}
        even_scores = {}

        for num, freq in frequency.items():
            is_odd = num % 2 == 1

            # 計算該號碼在各位置的適配度
            position_score = 0
            for pos in range(pick_count):
                # 如果這個位置偏好奇數，且號碼是奇數，加分
                if is_odd and position_odd_preference[pos] > 0.5:
                    position_score += (position_odd_preference[pos] - 0.5) * 2
                # 如果這個位置偏好偶數，且號碼是偶數，加分
                elif not is_odd and position_odd_preference[pos] < 0.5:
                    position_score += (0.5 - position_odd_preference[pos]) * 2

            # 綜合分數：頻率 70% + 位置適配 30%
            total_score = freq * 0.7 + position_score * freq * 0.3

            if is_odd:
                odd_scores[num] = total_score
            else:
                even_scores[num] = total_score

        # 3. 選擇分數最高的奇偶號碼
        sorted_odd = sorted(odd_scores.items(), key=lambda x: x[1], reverse=True)
        sorted_even = sorted(even_scores.items(), key=lambda x: x[1], reverse=True)

        predicted = sorted(
            [n for n, _ in sorted_odd[:target_odd]] +
            [n for n, _ in sorted_even[:target_even]]
        )

        # ✨ 優化：動態計算信心度
        base_confidence = 0.55
        # 位置分佈一致性加成
        position_consistency = np.std(list(position_odd_preference.values()))
        consistency_bonus = (1 - position_consistency) * 0.15  # 最多 +15%

        final_confidence = min(0.70, base_confidence + consistency_bonus)

        return {
            'numbers': predicted,
            'confidence': float(final_confidence),
            'method': f'奇偶平衡 (位置分析: {target_odd}奇/{target_even}偶)',
            'probabilities': None
        }

    def _analyze_position_odd_preference(self, history: List[Dict], pick_count: int) -> dict:
        """
        分析每個位置對奇數的偏好程度

        返回：{position: odd_ratio}
        odd_ratio > 0.5 表示該位置偏好奇數
        odd_ratio < 0.5 表示該位置偏好偶數
        """
        position_odd_counts = {pos: 0 for pos in range(pick_count)}
        position_total_counts = {pos: 0 for pos in range(pick_count)}

        for draw in history[-100:]:  # 分析最近 100 期
            sorted_nums = sorted(draw['numbers'])
            for pos, num in enumerate(sorted_nums):
                if pos < pick_count:  # 確保不超過 pick_count
                    position_total_counts[pos] += 1
                    if num % 2 == 1:
                        position_odd_counts[pos] += 1

        # 計算每個位置的奇數比例
        position_preferences = {}
        for pos in range(pick_count):
            if position_total_counts[pos] > 0:
                position_preferences[pos] = position_odd_counts[pos] / position_total_counts[pos]
            else:
                position_preferences[pos] = 0.5  # 默認均衡

        return position_preferences

    def zone_balance_predict(self, history, lottery_rules):
        """
        區域平衡策略 (✨ 優化版：動態區域劃分)
        使用頻率聚類動態劃分區域，而非固定三等分
        """
        pick_count = lottery_rules.get('pickCount', 6)
        min_num = lottery_rules.get('minNumber', 1)
        max_num = lottery_rules.get('maxNumber', 49)

        # ✨ 優化：動態劃分區域（基於頻率聚類）
        zones, zone_quality = self._dynamic_zone_partition(history, min_num, max_num, pick_count)

        # 計算每個區域的歷史分佈
        zone_counts = [0] * len(zones)
        analysis_window = min(len(history), 80)  # 使用最近 80 期

        for draw in history[-analysis_window:]:
            for num in draw['numbers']:
                for i, zone in enumerate(zones):
                    if zone['start'] <= num <= zone['end']:
                        zone_counts[i] += 1
                        break

        # ✨ 優化：考慮區域趨勢（最近 20 期 vs 整體）
        recent_zone_counts = [0] * len(zones)
        for draw in history[-20:]:
            for num in draw['numbers']:
                for i, zone in enumerate(zones):
                    if zone['start'] <= num <= zone['end']:
                        recent_zone_counts[i] += 1
                        break

        # 計算目標分配（混合歷史和趨勢）
        total = sum(zone_counts) if sum(zone_counts) > 0 else 1
        recent_total = sum(recent_zone_counts) if sum(recent_zone_counts) > 0 else 1

        targets = []
        for i in range(len(zones)):
            historical_ratio = zone_counts[i] / total
            recent_ratio = recent_zone_counts[i] / recent_total
            # 70% 歷史 + 30% 趨勢
            combined_ratio = historical_ratio * 0.7 + recent_ratio * 0.3
            targets.append(round(combined_ratio * pick_count))

        # 調整目標使總和正確
        while sum(targets) < pick_count:
            targets[targets.index(min(targets))] += 1
        while sum(targets) > pick_count:
            targets[targets.index(max(targets))] -= 1

        # 從每個區域選擇號碼
        all_nums = [n for draw in history for n in draw['numbers']]
        freq = Counter(all_nums)

        # ✨ 優化：考慮區域內的位置偏好
        predicted = []
        for i, zone in enumerate(zones):
            zone_nums = []
            # 使用 zone['numbers'] 而非 range，避免重複
            for num in zone['numbers']:
                # 綜合得分：頻率 + 近期趨勢
                base_freq = freq.get(num, 0)
                recent_freq = sum(1 for draw in history[-30:] for n in draw['numbers'] if n == num)
                score = base_freq * 0.6 + recent_freq * 0.4
                zone_nums.append((num, score))

            zone_nums.sort(key=lambda x: x[1], reverse=True)
            predicted.extend([n for n, _ in zone_nums[:targets[i]]])

        # ✨ 優化：動態計算信心度
        base_confidence = 0.58
        quality_bonus = zone_quality * 0.12  # 區域劃分質量 +0-12%
        data_bonus = min(len(history) / 300, 0.08)

        final_confidence = min(0.70, base_confidence + quality_bonus + data_bonus)

        zone_desc = f"{len(zones)}區域 (質量:{zone_quality:.2f})"

        return {
            'numbers': sorted(predicted),
            'confidence': float(final_confidence),
            'method': f'區域平衡 ({zone_desc})',
            'probabilities': None
        }

    def _dynamic_zone_partition(
        self,
        history: List[Dict],
        min_num: int,
        max_num: int,
        pick_count: int
    ) -> tuple:
        """
        ✨ 新方法：動態區域劃分

        使用頻率分佈自動劃分最優區域數量和邊界
        策略：
        1. 計算號碼頻率
        2. 使用簡單 K-means 聚類劃分
        3. 返回區域列表和劃分質量
        """
        # 計算頻率
        all_nums = [n for draw in history for n in draw['numbers']]
        freq = Counter(all_nums)

        # 為所有號碼設置頻率（包括未出現的）
        num_freq_pairs = []
        for num in range(min_num, max_num + 1):
            num_freq_pairs.append((num, freq.get(num, 0)))

        # 根據號碼範圍決定區域數量
        num_range = max_num - min_num + 1
        if num_range <= 20:
            num_zones = 2
        elif num_range <= 40:
            num_zones = 3
        else:
            num_zones = 4

        # 簡化版 K-means：按頻率排序後等分
        sorted_pairs = sorted(num_freq_pairs, key=lambda x: x[1], reverse=True)

        # 計算每個區域應包含多少個號碼
        zone_size = len(sorted_pairs) // num_zones
        remainder = len(sorted_pairs) % num_zones

        zones = []
        start_idx = 0

        for i in range(num_zones):
            # 分配號碼
            current_zone_size = zone_size + (1 if i < remainder else 0)
            zone_nums = [pair[0] for pair in sorted_pairs[start_idx:start_idx + current_zone_size]]

            if zone_nums:
                zones.append({
                    'start': min(zone_nums),
                    'end': max(zone_nums),
                    'numbers': sorted(zone_nums)
                })

            start_idx += current_zone_size

        # 計算劃分質量（區域內頻率方差 vs 區域間頻率方差）
        zone_quality = self._calculate_zone_quality(zones, freq)

        return zones, zone_quality

    def _calculate_zone_quality(
        self,
        zones: List[Dict],
        freq: Counter
    ) -> float:
        """
        ✨ 新方法：計算區域劃分質量

        好的劃分應該：
        - 區域內頻率相似（低方差）
        - 區域間頻率差異大（高方差）
        """
        if not zones:
            return 0.0

        # 計算每個區域的平均頻率
        zone_avg_freqs = []
        for zone in zones:
            zone_freqs = [freq.get(num, 0) for num in zone['numbers']]
            if zone_freqs:
                zone_avg_freqs.append(sum(zone_freqs) / len(zone_freqs))
            else:
                zone_avg_freqs.append(0)

        # 區域間方差（越大越好）
        if len(zone_avg_freqs) > 1:
            mean_of_means = sum(zone_avg_freqs) / len(zone_avg_freqs)
            between_variance = sum((avg - mean_of_means) ** 2 for avg in zone_avg_freqs) / len(zone_avg_freqs)
        else:
            between_variance = 0

        # 區域內平均方差（越小越好）
        within_variances = []
        for zone in zones:
            zone_freqs = [freq.get(num, 0) for num in zone['numbers']]
            if len(zone_freqs) > 1:
                mean_freq = sum(zone_freqs) / len(zone_freqs)
                variance = sum((f - mean_freq) ** 2 for f in zone_freqs) / len(zone_freqs)
                within_variances.append(variance)

        avg_within_variance = sum(within_variances) / len(within_variances) if within_variances else 1

        # 質量分數：區域間方差 / (區域內方差 + 1)
        quality = between_variance / (avg_within_variance + 1)

        # 正規化到 0-1
        normalized_quality = min(1.0, quality / 10)

        return float(normalized_quality)

    def hot_cold_mix_predict(self, history, lottery_rules):
        """
        冷熱混合策略 (✨✨ 進階優化版：多窗口融合 + 溫度分級)

        新增優化：
        1. 多窗口融合（短/中/長期）
        2. 溫度分級系統（6個等級）
        3. 轉移點檢測（熱↔冷轉換）
        4. 加權分佈分析
        """
        pick_count = lottery_rules.get('pickCount', 6)
        min_num = lottery_rules.get('minNumber', 1)
        max_num = lottery_rules.get('maxNumber', 49)

        # ✨✨ 優化 1：多窗口融合分析
        multi_window_scores = self._multi_window_temperature_analysis(
            history, min_num, max_num, pick_count
        )

        # ✨✨ 優化 2：轉移點檢測（識別號碼趨勢變化）
        transition_scores = self._detect_hot_cold_transitions(
            history, min_num, max_num
        )

        # ✨✨ 優化 3：綜合評分（融合多窗口 + 轉移趨勢）
        final_scores = {}
        for num in range(min_num, max_num + 1):
            # 多窗口得分 70% + 轉移趨勢得分 30%
            window_score = multi_window_scores.get(num, 0)
            transition_score = transition_scores.get(num, 0)
            final_scores[num] = window_score * 0.7 + transition_score * 0.3

        # 選擇得分最高的號碼
        sorted_nums = sorted(final_scores.items(), key=lambda x: x[1], reverse=True)
        predicted = sorted([num for num, _ in sorted_nums[:pick_count]])

        # ✨✨ 優化 4：動態信心度計算
        base_confidence = 0.62

        # 多窗口一致性加成
        consistency_bonus = self._calculate_multi_window_consistency(
            multi_window_scores, predicted
        ) * 0.10

        # 轉移點穩定性加成
        transition_bonus = self._calculate_transition_stability(
            transition_scores, predicted
        ) * 0.08

        final_confidence = min(0.74, base_confidence + consistency_bonus + transition_bonus)

        # 識別溫度等級用於顯示
        temp_levels = self._classify_temperature_levels(multi_window_scores, pick_count)
        hot_count = sum(1 for num in predicted if temp_levels.get(num, 'warm') in ['very_hot', 'hot'])

        return {
            'numbers': predicted,
            'confidence': float(final_confidence),
            'method': f'冷熱混合 (多窗口融合, 熱號{hot_count}個)',
            'probabilities': [final_scores[num] for num in predicted]
        }

    def _find_optimal_hot_cold_window(self, history: List[Dict], pick_count: int) -> int:
        """
        找出最優的冷熱分析窗口大小

        策略：測試多個窗口，選擇號碼頻率分佈最穩定的
        """
        if len(history) < 30:
            return len(history)  # 數據太少，使用全部

        # 候選窗口
        candidate_windows = [15, 20, 25, 30, 40, 50]
        # 過濾掉大於歷史數據量的窗口
        candidate_windows = [w for w in candidate_windows if w <= len(history)]

        if not candidate_windows:
            return len(history)

        window_volatilities = []

        for window in candidate_windows:
            recent = history[-window:]
            nums = [n for draw in recent for n in draw['numbers']]
            freq = Counter(nums)

            # 計算頻率的變異係數（越小越穩定）
            freq_values = list(freq.values())
            if len(freq_values) < 2:
                volatility = 999  # 無法計算，設為極大值
            else:
                mean_freq = np.mean(freq_values)
                std_freq = np.std(freq_values)
                volatility = std_freq / mean_freq if mean_freq > 0 else 999

            window_volatilities.append((window, volatility))

        # 選擇波動性最低的窗口
        optimal_window, _ = min(window_volatilities, key=lambda x: x[1])

        return optimal_window

    def _calculate_hot_ratio(self, freq: Counter, pick_count: int) -> float:
        """
        動態計算熱號比例

        策略：如果熱號分佈集中，增加熱號比例；反之減少
        """
        sorted_freqs = sorted(freq.values(), reverse=True)

        if len(sorted_freqs) < pick_count:
            return 0.5  # 默認 50/50

        # 計算前 pick_count 個號碼的頻率集中度
        top_freqs = sorted_freqs[:pick_count]
        if sum(sorted_freqs) == 0:
            return 0.5

        concentration = sum(top_freqs) / sum(sorted_freqs)

        # 集中度高 -> 增加熱號比例
        # 集中度低 -> 減少熱號比例（給冷號更多機會）
        if concentration > 0.6:
            return 0.6  # 60% 熱號
        elif concentration > 0.5:
            return 0.55  # 55% 熱號
        elif concentration < 0.4:
            return 0.4  # 40% 熱號
        else:
            return 0.5  # 50% 熱號

    def _calculate_window_stability(self, history: List[Dict], window: int) -> float:
        """
        計算窗口內數據的穩定性

        返回：0-1，越高表示越穩定
        """
        if len(history) < window + 10:
            return 0.5

        # 比較當前窗口和前一個窗口的頻率分佈相似度
        current_window = history[-window:]
        previous_window = history[-2*window:-window]

        current_nums = [n for draw in current_window for n in draw['numbers']]
        previous_nums = [n for draw in previous_window for n in draw['numbers']]

        current_freq = Counter(current_nums)
        previous_freq = Counter(previous_nums)

        # 計算 Jaccard 相似度（前 10 個熱門號碼）
        current_top = set([n for n, _ in current_freq.most_common(10)])
        previous_top = set([n for n, _ in previous_freq.most_common(10)])

        if len(current_top | previous_top) == 0:
            return 0.5

        similarity = len(current_top & previous_top) / len(current_top | previous_top)

        return float(similarity)

    def _multi_window_temperature_analysis(self, history: List[Dict], min_num: int,
                                           max_num: int, pick_count: int) -> dict:
        """
        ✨✨ 多窗口融合溫度分析

        分析短期(10-15期)、中期(20-30期)、長期(40-50期)窗口
        返回：{number: combined_score}
        """
        if len(history) < 15:
            # 數據不足，退化到單窗口
            nums = [n for draw in history for n in draw['numbers']]
            freq = Counter(nums)
            max_freq = max(freq.values()) if freq else 1
            return {num: freq.get(num, 0) / max_freq for num in range(min_num, max_num + 1)}

        # 定義多個窗口
        windows = {
            'short': min(15, len(history)),     # 短期：捕捉最新趨勢
            'mid': min(25, len(history)),       # 中期：平衡穩定性
            'long': min(45, len(history))       # 長期：歷史基準
        }

        # 計算每個窗口的頻率得分
        window_scores = {}
        for window_name, window_size in windows.items():
            recent = history[-window_size:]
            nums = [n for draw in recent for n in draw['numbers']]
            freq = Counter(nums)

            # 正規化頻率
            max_freq = max(freq.values()) if freq else 1
            window_scores[window_name] = {
                num: freq.get(num, 0) / max_freq
                for num in range(min_num, max_num + 1)
            }

        # 融合多窗口得分（短期權重最高，長期作為基準）
        combined_scores = {}
        for num in range(min_num, max_num + 1):
            short_score = window_scores['short'].get(num, 0)
            mid_score = window_scores['mid'].get(num, 0)
            long_score = window_scores['long'].get(num, 0)

            # 加權融合：短期 50%，中期 30%，長期 20%
            combined_scores[num] = (
                short_score * 0.5 +
                mid_score * 0.3 +
                long_score * 0.2
            )

        return combined_scores

    def _detect_hot_cold_transitions(self, history: List[Dict], min_num: int, max_num: int) -> dict:
        """
        ✨✨ 檢測號碼的冷熱轉移趨勢

        識別正在從冷轉熱（上升趨勢）或從熱轉冷（下降趨勢）的號碼
        返回：{number: transition_score}
        上升趨勢 > 0，下降趨勢 < 0
        """
        if len(history) < 30:
            return {num: 0 for num in range(min_num, max_num + 1)}

        # 分析最近三個時段的頻率變化
        period1 = history[-30:-20]  # 早期
        period2 = history[-20:-10]  # 中期
        period3 = history[-10:]     # 近期

        freq1 = Counter([n for draw in period1 for n in draw['numbers']])
        freq2 = Counter([n for draw in period2 for n in draw['numbers']])
        freq3 = Counter([n for draw in period3 for n in draw['numbers']])

        # 計算趨勢得分
        transition_scores = {}
        for num in range(min_num, max_num + 1):
            f1 = freq1.get(num, 0)
            f2 = freq2.get(num, 0)
            f3 = freq3.get(num, 0)

            # 計算加速度（二階差分）
            # 正加速度 = 頻率持續上升（冷→熱）
            # 負加速度 = 頻率持續下降（熱→冷）
            velocity = (f3 - f2) - (f2 - f1)

            # 正規化到 -1 到 1
            max_possible_change = 10  # 假設最大變化
            transition_scores[num] = np.clip(velocity / max_possible_change, -1, 1)

        # 轉換為正向得分（上升趨勢給高分，下降趨勢給低分）
        min_score = min(transition_scores.values())
        max_score = max(transition_scores.values())
        score_range = max_score - min_score if max_score > min_score else 1

        normalized_scores = {}
        for num, score in transition_scores.items():
            # 正規化到 0-1
            normalized_scores[num] = (score - min_score) / score_range

        return normalized_scores

    def _calculate_multi_window_consistency(self, multi_window_scores: dict, predicted: list) -> float:
        """
        ✨✨ 計算多窗口預測的一致性

        如果預測號碼在所有窗口都有高分，一致性高
        返回：0-1
        """
        if not predicted or not multi_window_scores:
            return 0

        # 計算預測號碼的平均得分
        predicted_scores = [multi_window_scores.get(num, 0) for num in predicted]

        if not predicted_scores:
            return 0

        # 一致性 = 平均得分 * (1 - 得分的變異係數)
        avg_score = np.mean(predicted_scores)
        std_score = np.std(predicted_scores)

        if avg_score == 0:
            return 0

        cv = std_score / avg_score  # 變異係數
        consistency = avg_score * (1 - min(cv, 1))

        return float(consistency)

    def _calculate_transition_stability(self, transition_scores: dict, predicted: list) -> float:
        """
        ✨✨ 計算轉移趨勢的穩定性

        預測號碼都處於上升趨勢 = 高穩定性
        返回：0-1
        """
        if not predicted or not transition_scores:
            return 0

        # 計算預測號碼的平均轉移得分
        predicted_transitions = [transition_scores.get(num, 0) for num in predicted]

        if not predicted_transitions:
            return 0

        # 穩定性 = 平均轉移得分（越高表示越多上升趨勢）
        avg_transition = np.mean(predicted_transitions)

        return float(avg_transition)

    def _classify_temperature_levels(self, scores: dict, pick_count: int) -> dict:
        """
        ✨✨ 溫度分級系統

        將號碼分為 6 個等級：
        very_hot, hot, warm, cool, cold, very_cold
        """
        sorted_nums = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        total_nums = len(sorted_nums)

        temp_levels = {}
        for idx, (num, score) in enumerate(sorted_nums):
            percentile = idx / total_nums

            if percentile < 0.1:
                temp_levels[num] = 'very_hot'
            elif percentile < 0.25:
                temp_levels[num] = 'hot'
            elif percentile < 0.5:
                temp_levels[num] = 'warm'
            elif percentile < 0.75:
                temp_levels[num] = 'cool'
            elif percentile < 0.9:
                temp_levels[num] = 'cold'
            else:
                temp_levels[num] = 'very_cold'

        return temp_levels

    def sum_range_predict(self, history, lottery_rules):
        """
        和值與AC值範圍策略 (✨ 優化版：多特徵增強)
        新增特徵：
        1. 動態和值範圍（近期趨勢 + 歷史分佈）
        2. 增強 AC 值分析（考慮連續性）
        3. 奇偶比例約束
        4. 跨度分析（最大-最小號碼）
        """
        pick_count = lottery_rules.get('pickCount', 6)
        min_num = lottery_rules.get('minNumber', 1)
        max_num = lottery_rules.get('maxNumber', 49)

        if len(history) < 10:
            return self.frequency_predict(history, lottery_rules)

        # ✨ 優化 1：動態和值範圍（混合歷史和趨勢）
        all_sums = [sum(d['numbers']) for d in history]
        recent_sums = [sum(d['numbers']) for d in history[-30:]]

        avg_sum = np.mean(all_sums)
        std_sum = np.std(all_sums)

        recent_avg_sum = np.mean(recent_sums)
        recent_std_sum = np.std(recent_sums)

        # 混合歷史和趨勢
        target_avg_sum = avg_sum * 0.6 + recent_avg_sum * 0.4
        target_std_sum = std_sum * 0.6 + recent_std_sum * 0.4

        target_min_sum = target_avg_sum - target_std_sum * 0.8
        target_max_sum = target_avg_sum + target_std_sum * 0.8

        # ✨ 優化 2：增強 AC 值分析
        def calculate_ac(numbers):
            diffs = set()
            for i in range(len(numbers)):
                for j in range(i + 1, len(numbers)):
                    diffs.add(abs(numbers[i] - numbers[j]))
            return len(diffs) - (len(numbers) - 1)

        ac_values = [calculate_ac(d['numbers']) for d in history]
        recent_ac_values = [calculate_ac(d['numbers']) for d in history[-30:]]

        avg_ac = np.mean(ac_values)
        recent_avg_ac = np.mean(recent_ac_values)
        target_ac = avg_ac * 0.6 + recent_avg_ac * 0.4

        # ✨ 優化 3：分析奇偶比例
        odd_even_ratios = []
        for draw in history[-50:]:
            odd_count = sum(1 for n in draw['numbers'] if n % 2 == 1)
            odd_even_ratios.append(odd_count / pick_count)

        avg_odd_ratio = np.mean(odd_even_ratios)
        target_odd_count = round(avg_odd_ratio * pick_count)

        # ✨ 優化 4：分析跨度（最大-最小號碼）
        spans = [max(d['numbers']) - min(d['numbers']) for d in history[-50:]]
        avg_span = np.mean(spans)
        std_span = np.std(spans)
        target_min_span = avg_span - std_span
        target_max_span = avg_span + std_span

        # 頻率分析
        all_nums = [n for d in history for n in d['numbers']]
        freq = Counter(all_nums)

        # ✨ 優化 5：增加候選池大小，使用加權隨機
        sorted_nums = sorted([(n, f) for n, f in freq.items()], key=lambda x: x[1], reverse=True)
        candidates = [n for n, _ in sorted_nums[:max(pick_count * 4, 25)]]
        weights = np.array([f for _, f in sorted_nums[:len(candidates)]])
        weights = weights / weights.sum()

        # ✨ 優化 6：多目標優化組合搜索
        best_combo = None
        min_score = float('inf')

        # 增加搜索次數
        for _ in range(2000):
            # 使用加權隨機選擇
            combo = np.random.choice(candidates, size=pick_count, replace=False, p=weights)
            combo = sorted(combo)

            # 計算各項特徵
            combo_sum = sum(combo)
            combo_ac = calculate_ac(combo)
            combo_odd_count = sum(1 for n in combo if n % 2 == 1)
            combo_span = max(combo) - min(combo)

            # 多特徵評分（所有約束）
            sum_valid = target_min_sum <= combo_sum <= target_max_sum
            ac_valid = abs(combo_ac - target_ac) <= 3
            odd_valid = abs(combo_odd_count - target_odd_count) <= 1
            span_valid = target_min_span <= combo_span <= target_max_span

            if sum_valid and ac_valid and odd_valid and span_valid:
                # 計算綜合得分（越小越好）
                sum_score = abs(combo_sum - target_avg_sum) / target_std_sum
                ac_score = abs(combo_ac - target_ac)
                odd_score = abs(combo_odd_count - target_odd_count)
                span_score = abs(combo_span - avg_span) / std_span

                # 加權綜合得分
                total_score = (
                    sum_score * 0.35 +
                    ac_score * 0.25 +
                    odd_score * 0.20 +
                    span_score * 0.20
                )

                if total_score < min_score:
                    min_score = total_score
                    best_combo = combo

        if best_combo is None:
            # 回退到頻率
            best_combo = [n for n, _ in sorted_nums[:pick_count]]

        # ✨ 優化 7：動態計算信心度
        base_confidence = 0.70

        if best_combo is not None and isinstance(best_combo, np.ndarray):
            # 檢查找到的組合質量
            found_valid = True
            quality_bonus = 0.08
        else:
            # 使用回退策略
            found_valid = False
            quality_bonus = 0

        data_bonus = min(len(history) / 300, 0.06)

        final_confidence = min(0.80, base_confidence + quality_bonus + data_bonus)

        return {
            'numbers': sorted(best_combo.tolist() if isinstance(best_combo, np.ndarray) else best_combo),
            'confidence': float(final_confidence),
            'method': '和值+AC+奇偶+跨度 (多特徵)',
            'probabilities': None
        }

    def number_pairs_predict(self, history, lottery_rules):
        """連號/配對分析策略"""
        pick_count = lottery_rules.get('pickCount', 6)
        min_num = lottery_rules.get('minNumber', 1)
        max_num = lottery_rules.get('maxNumber', 49)
        
        # 1. 建立共現矩陣
        co_occurrence = defaultdict(int)
        for draw in history:
            nums = sorted(draw['numbers'])
            for i in range(len(nums)):
                for j in range(i + 1, len(nums)):
                    co_occurrence[(nums[i], nums[j])] += 1
                    
        # 2. 找出 Top Pairs
        sorted_pairs = sorted(co_occurrence.items(), key=lambda x: x[1], reverse=True)
        top_pairs = sorted_pairs[:10]
        
        if not top_pairs:
            return self.frequency_predict(history, lottery_rules)
            
        # 3. 選擇種子 Pair
        import random
        seed_pair, _ = random.choice(top_pairs[:5])
        selected = set(seed_pair)
        
        # 4. 填補剩餘號碼
        while len(selected) < pick_count:
            best_candidate = -1
            max_affinity = -1
            
            for i in range(min_num, max_num + 1):
                if i in selected: continue
                
                # 計算與已選號碼的關聯度
                affinity = sum(co_occurrence.get(tuple(sorted((i, s))), 0) for s in selected)
                # 加入隨機性
                affinity *= (0.9 + random.random() * 0.2)
                
                if affinity > max_affinity:
                    max_affinity = affinity
                    best_candidate = i
            
            if best_candidate != -1:
                selected.add(best_candidate)
            else:
                # 隨機填補
                remaining = [n for n in range(min_num, max_num + 1) if n not in selected]
                if remaining:
                    selected.add(random.choice(remaining))
                else:
                    break
                    
        return {
            'numbers': sorted(list(selected)),
            'confidence': 0.82,
            'method': '連號/配對分析',
            'probabilities': None
        }

    def pattern_recognition_predict(self, history, lottery_rules, pattern_size: int = 3) -> Dict:
        """
        模式識別策略：識別歷史上常見的子組合模式，並據此投票選擇號碼
        """
        import itertools
        pick_count = lottery_rules.get('pickCount', 6)
        if len(history) < max(10, pattern_size + 2):
            return self.frequency_predict(history, lottery_rules)

        pattern_library = defaultdict(list)
        for i, draw in enumerate(history):
            nums = sorted(draw['numbers'])
            for combo in itertools.combinations(nums, pattern_size):
                pattern_library[combo].append(i)

        if not pattern_library:
            return self.frequency_predict(history, lottery_rules)

        # 模式頻率
        pattern_freq = {pattern: len(indices) for pattern, indices in pattern_library.items()}

        # 模式新鮮度（最近出現越近分數越高）
        pattern_freshness = {}
        last_index = len(history) - 1
        for pattern, indices in pattern_library.items():
            last_appear = max(indices)
            freshness = 1 - ((last_index - last_appear) / max(1, len(history)))
            pattern_freshness[pattern] = freshness

        # 綜合評分
        max_freq = max(pattern_freq.values()) if pattern_freq else 1
        pattern_scores = {}
        for pattern in pattern_library:
            freq_score = pattern_freq[pattern] / max_freq
            fresh_score = pattern_freshness.get(pattern, 0)
            pattern_scores[pattern] = freq_score * 0.6 + fresh_score * 0.4

        # 選擇 Top 模式並投票
        top_patterns = sorted(pattern_scores.items(), key=lambda x: x[1], reverse=True)[:max(10, pick_count)]
        candidate_nums = defaultdict(float)
        for pattern, score in top_patterns:
            for num in pattern:
                candidate_nums[num] += score

        sorted_candidates = sorted(candidate_nums.items(), key=lambda x: x[1], reverse=True)
        predicted_numbers = sorted([num for num, _ in sorted_candidates[:pick_count]])

        # 信心度：基礎 + 集中度
        base_confidence = 0.74
        if sorted_candidates:
            scores = [s for _, s in sorted_candidates[:pick_count]]
            mean_s = np.mean(scores)
            std_s = np.std(scores)
            concentration = 1 - min(std_s / mean_s, 0.7) if mean_s > 0 else 0.4
        else:
            concentration = 0.4
        confidence = min(0.86, base_confidence + concentration * 0.12)

        # 🔧 預測特別號碼
        predicted_special = predict_special_number(history, lottery_rules, predicted_numbers)
        
        result = {
            'numbers': predicted_numbers,
            'confidence': float(confidence),
            'method': '模式識別 (Pattern Recognition)',
            'probabilities': [float(score) for _, score in sorted_candidates[:pick_count]]
        }
        
        # 🔧 添加特別號碼
        if predicted_special is not None:
            result['special'] = predicted_special
        
        return result

    def cycle_analysis_predict(self, history, lottery_rules) -> Dict:
        """
        週期分析策略：根據號碼出現的平均週期與當前間隔計算得分
        """
        pick_count = lottery_rules.get('pickCount', 6)
        min_num = lottery_rules.get('minNumber', 1)
        max_num = lottery_rules.get('maxNumber', 49)

        if len(history) < 20:
            return self.frequency_predict(history, lottery_rules)

        number_cycles = {}
        for num in range(min_num, max_num + 1):
            appearances = []
            for i, draw in enumerate(history):
                if num in draw['numbers']:
                    appearances.append(i)
            if len(appearances) >= 3:
                intervals = [appearances[i+1] - appearances[i] for i in range(len(appearances)-1)]
                avg_cycle = np.mean(intervals)
                std_cycle = np.std(intervals)
                last_appear = appearances[-1]
                expected_next = last_appear + avg_cycle
                deviation = abs((len(history) - 1) - expected_next) / (std_cycle + 1e-5)
                cycle_score = 1 / (1 + deviation)
                number_cycles[num] = {
                    'avg_cycle': float(avg_cycle),
                    'score': float(cycle_score)
                }

        if not number_cycles:
            return self.frequency_predict(history, lottery_rules)

        sorted_by_cycle = sorted(number_cycles.items(), key=lambda x: x[1]['score'], reverse=True)
        predicted_numbers = sorted([num for num, _ in sorted_by_cycle[:pick_count]])

        top_scores = [data['score'] for _, data in sorted_by_cycle[:pick_count]]
        confidence = min(0.85, 0.65 + (np.mean(top_scores) if top_scores else 0) * 0.2)

        # 🔧 預測特別號碼
        predicted_special = predict_special_number(history, lottery_rules, predicted_numbers)
        
        result = {
            'numbers': predicted_numbers,
            'confidence': float(confidence),
            'method': '週期分析 (Cycle Analysis)',
            'probabilities': [float(s) for s in top_scores] if top_scores else None
        }
        
        # 🔧 添加特別號碼
        if predicted_special is not None:
            result['special'] = predicted_special
        
        return result

    def wheeling_predict(self, history, lottery_rules):
        """組合輪轉策略"""
        pick_count = lottery_rules.get('pickCount', 6)
        min_num = lottery_rules.get('minNumber', 1)
        max_num = lottery_rules.get('maxNumber', 49)
        
        # 1. 準備候選池 (熱門 + 冷門 + 隨機)
        all_nums = [n for d in history for n in d['numbers']]
        freq = Counter(all_nums)
        sorted_nums = [n for n, _ in sorted(freq.items(), key=lambda x: x[1], reverse=True)]
        
        pool_size = min(pick_count * 2, max_num - min_num + 1)
        hot_count = pool_size // 3
        cold_count = pool_size // 3
        
        hot_nums = sorted_nums[:hot_count]
        cold_nums = sorted_nums[-cold_count:] if cold_count > 0 else []
        
        remaining = [n for n in range(min_num, max_num + 1) if n not in hot_nums and n not in cold_nums]
        import random
        random_nums = random.sample(remaining, min(len(remaining), pool_size - len(hot_nums) - len(cold_nums)))
        
        pool = list(set(hot_nums + cold_nums + random_nums))
        
        # 2. 生成組合並評分
        best_combo = None
        best_score = float('-inf')
        
        # 嘗試 200 次隨機組合
        for _ in range(200):
            if len(pool) < pick_count: break
            combo = random.sample(pool, pick_count)
            
            # 評分
            score = 0
            # 頻率分
            score += sum(freq.get(n, 0) for n in combo)
            # 奇偶平衡
            odd_count = sum(1 for n in combo if n % 2 == 1)
            if odd_count == pick_count // 2: score += 20
            
            if score > best_score:
                best_score = score
                best_combo = combo
                
        if best_combo is None:
             return self.frequency_predict(history, lottery_rules)
             
        return {
            'numbers': sorted(best_combo),
            'confidence': 0.85,
            'method': '組合輪轉策略',
            'probabilities': None
        }

    def statistical_predict(self, history, lottery_rules):
        """多維統計分析策略"""
        pick_count = lottery_rules.get('pickCount', 6)
        min_num = lottery_rules.get('minNumber', 1)
        max_num = lottery_rules.get('maxNumber', 49)
        total_numbers = max_num - min_num + 1
        
        # 1. 計算基礎頻率
        all_nums = [n for d in history for n in d['numbers']]
        freq = Counter(all_nums)
        
        # 2. 定義檢查函數
        def check_conditions(numbers):
            # 和值
            s = sum(numbers)
            theoretical_min = (min_num * pick_count) + (pick_count * (pick_count - 1) / 2)
            theoretical_max = (max_num * pick_count) - (pick_count * (pick_count - 1) / 2)
            ideal_sum = (theoretical_min + theoretical_max) / 2
            sum_range = (theoretical_max - theoretical_min) * 0.6
            if not (ideal_sum - sum_range / 2 <= s <= ideal_sum + sum_range / 2): return False
            
            # AC值
            diffs = set()
            sorted_nums = sorted(numbers)
            for i in range(len(sorted_nums)):
                for j in range(i + 1, len(sorted_nums)):
                    diffs.add(sorted_nums[j] - sorted_nums[i])
            ac = len(diffs) - (len(numbers) - 1)
            
            min_ac = max(pick_count - 1, int(total_numbers * 0.15))
            max_ac = min(pick_count * (pick_count - 1) / 2, int(total_numbers * 0.35))
            if not (min_ac <= ac <= max_ac): return False
            
            # 奇偶比
            odd = sum(1 for n in numbers if n % 2 == 1)
            ideal_odd = round(pick_count / 2)
            if abs(odd - ideal_odd) > (pick_count // 3 + 1): return False
            
            # 極差
            spread = max(numbers) - min(numbers)
            min_spread = int(total_numbers * 0.4)
            if spread < min_spread: return False
            
            # 尾數多樣性
            last_digits = set(n % 10 for n in numbers)
            min_unique = max(3, int(pick_count * 0.6))
            if len(last_digits) < min_unique: return False
            
            return True

        # 3. 生成並篩選組合
        valid_combinations = []
        import random
        
        # 構建加權池
        pool = []
        for i in range(min_num, max_num + 1):
            weight = int(np.sqrt(freq.get(i, 1)) * 10)
            pool.extend([i] * weight)
            
        for _ in range(2000):
            if len(valid_combinations) >= 20: break
            combo = set()
            while len(combo) < pick_count:
                combo.add(random.choice(pool))
            
            combo_list = list(combo)
            if check_conditions(combo_list):
                valid_combinations.append(combo_list)
                
        if not valid_combinations:
            return self.frequency_predict(history, lottery_rules)
            
        # 4. 選擇頻率分最高的
        best_combo = max(valid_combinations, key=lambda c: sum(freq.get(n, 0) for n in c))
        
        return {
            'numbers': sorted(best_combo),
            'confidence': 0.88,
            'method': '多維統計分析',
            'probabilities': None
        }

    # ===== 高級策略 (深度優化) =====
    
    def random_forest_predict(
        self, 
        history: List[Dict], 
        lottery_rules: Dict
    ) -> Dict:
        """
        隨機森林預測策略 (優化版：增強特徵工程)
        加入遺漏值(Gap)、近期熱度、鄰居效應等特徵
        """
        # 由於 sklearn RF 對多標籤支持的複雜性，我們這裡改用一個更直接的方法：
        # 特徵相似度匹配 (KNN-like)
        return self._knn_like_predict(history, lottery_rules)

    def _knn_like_predict(self, history, lottery_rules):
        """
        基於相似度的預測 (替代複雜的 RF)
        尋找歷史上特徵最相似的期數，統計它們的下一期號碼
        """
        pick_count = lottery_rules.get('pickCount', 6)
        min_num = lottery_rules.get('minNumber', 1)
        max_num = lottery_rules.get('maxNumber', 49)
        
        if len(history) < 60:
            return self.frequency_predict(history, lottery_rules)

        # 提取最近一期的特徵（遺漏值）
        current_gaps = self._calculate_gaps(history, len(history), min_num, max_num)
        
        # 計算歷史上每一期的特徵與當前的距離
        distances = []
        # 只比較最近 500 期，提高效率
        start_compare = max(50, len(history) - 500)
        
        for i in range(start_compare, len(history) - 1):
            hist_gaps = self._calculate_gaps(history, i, min_num, max_num)
            # 歐氏距離
            dist = np.linalg.norm(current_gaps - hist_gaps)
            distances.append((i, dist))
        
        # 找出最相似的 30 期
        distances.sort(key=lambda x: x[1])
        top_k = distances[:30]
        
        # 統計這些相似期數的"下一期"號碼
        next_numbers_counter = Counter()
        total_weight = 0
        
        for idx, dist in top_k:
            # 距離越小權重越大
            weight = 1 / (dist + 1e-5)
            total_weight += weight
            
            next_draw = history[idx + 1]
            for num in next_draw['numbers']:
                next_numbers_counter[num] += weight
        
        most_common = next_numbers_counter.most_common(pick_count)
        predicted_numbers = sorted([num for num, _ in most_common])
        
        # 🔧 預測特別號碼
        predicted_special = predict_special_number(history, lottery_rules, predicted_numbers)
        
        result = {
            'numbers': predicted_numbers,
            'confidence': 0.75,
            'method': '特徵相似度匹配 (KNN)',
            'probabilities': [count / total_weight for _, count in most_common]
        }
        
        # 🔧 添加特別號碼
        if predicted_special is not None:
            result['special'] = predicted_special
        
        return result

    def ensemble_advanced_predict(
        self,
        history: List[Dict],
        lottery_rules: Dict
    ) -> Dict:
        """
        進階集成策略 (Advanced Ensemble)
        整合 Boosting 弱策略強化 + Co-occurrence 號碼關聯 + Feature-weighted 特徵工程

        融合能力：
        1. Boosting：識別並強化表現較弱但有潛力的策略
        2. Co-occurrence：分析號碼間的共現關聯性
        3. Feature-weighted：基於多維特徵的智能加權
        """
        pick_count = lottery_rules.get('pickCount', 6)
        min_num = lottery_rules.get('minNumber', 1)
        max_num = lottery_rules.get('maxNumber', 49)
        data_size = len(history)

        # ===== 1. 基礎策略池 =====
        base_strategies = [
            ('frequency', self.frequency_predict),
            ('trend', self.trend_predict),
            ('bayesian', self.bayesian_predict),
            ('markov', self.markov_predict),
            ('deviation', self.deviation_predict),
        ]

        # 執行基礎策略並評估性能（簡化版 Boosting）
        strategy_predictions = {}
        strategy_scores = {}

        for name, func in base_strategies:
            try:
                result = func(history, lottery_rules)
                strategy_predictions[name] = result
                # 基於信心度評分
                strategy_scores[name] = result.get('confidence', 0.5)
            except Exception as e:
                logger.warning(f"策略 {name} 執行失敗: {e}")
                strategy_scores[name] = 0.0

        # ===== 2. Boosting 機制：強化弱策略 =====
        # 找出表現較弱的策略（信心度 < 0.7），給予額外權重以平衡
        weak_strategies = [name for name, score in strategy_scores.items() if 0.3 < score < 0.7]
        boosting_multiplier = 1.5  # 弱策略權重提升

        # ===== 3. Co-occurrence 分析：號碼關聯 =====
        co_occurrence = defaultdict(int)
        for draw in history:
            nums = sorted(draw['numbers'])
            for i in range(len(nums)):
                for j in range(i + 1, len(nums)):
                    co_occurrence[(nums[i], nums[j])] += 1

        # 計算每個號碼的關聯強度
        number_affinity = defaultdict(float)
        for (n1, n2), count in co_occurrence.items():
            number_affinity[n1] += count
            number_affinity[n2] += count

        # 正規化
        max_affinity = max(number_affinity.values()) if number_affinity else 1
        for num in number_affinity:
            number_affinity[num] /= max_affinity

        # ===== 4. Feature-weighted：多維特徵加權 =====
        # 計算每個號碼的多維特徵分數
        all_nums = [n for d in history for n in d['numbers']]
        freq = Counter(all_nums)

        # 計算遺漏值（Gap）
        gaps = {i: 0 for i in range(min_num, max_num + 1)}
        if history:
            last_draw_nums = set(history[-1]['numbers'])
            for i in range(min_num, max_num + 1):
                gap = 0
                for draw in reversed(history):
                    if i in draw['numbers']:
                        break
                    gap += 1
                gaps[i] = gap

        # 綜合特徵分數
        feature_scores = {}
        for i in range(min_num, max_num + 1):
            freq_score = freq.get(i, 0) / max(freq.values()) if freq else 0
            gap_score = min(gaps[i] / 20, 1.0)  # 遺漏越久分數越高，上限1.0
            affinity_score = number_affinity.get(i, 0)

            # 加權組合
            feature_scores[i] = (
                freq_score * 0.4 +      # 頻率 40%
                gap_score * 0.3 +       # 遺漏 30%
                affinity_score * 0.3    # 關聯 30%
            )

        # ===== 5. 綜合投票：整合所有策略 + 特徵加權 =====
        number_votes = defaultdict(float)

        # 基礎策略投票
        for name, result in strategy_predictions.items():
            weight = strategy_scores[name]

            # Boosting 加成
            if name in weak_strategies:
                weight *= boosting_multiplier

            # 投票
            probs = result.get('probabilities')
            if probs and len(probs) == len(result['numbers']):
                for num, prob in zip(result['numbers'], probs):
                    number_votes[num] += prob * weight * 10
            else:
                for rank, num in enumerate(result['numbers']):
                    rank_score = (pick_count - rank) / pick_count
                    number_votes[num] += rank_score * weight

        # 特徵加權疊加
        feature_weight = 2.0  # 特徵權重
        for num, score in feature_scores.items():
            number_votes[num] += score * feature_weight

        # ===== 6. 選出最終號碼 =====
        sorted_numbers = sorted(number_votes.items(), key=lambda x: x[1], reverse=True)
        predicted_numbers = sorted([num for num, _ in sorted_numbers[:pick_count]])

        # ===== 7. 計算信心度 =====
        top_scores = [score for _, score in sorted_numbers[:pick_count]]
        if len(top_scores) > 1:
            score_std = np.std(top_scores)
            score_mean = np.mean(top_scores)
            consistency = 1 - min(score_std / score_mean, 0.5) if score_mean > 0 else 0.5
        else:
            consistency = 0.5

        base_confidence = 0.78
        boosting_bonus = len(weak_strategies) * 0.02  # 每個弱策略提升 +2%
        consistency_bonus = consistency * 0.12
        final_confidence = min(0.92, base_confidence + boosting_bonus + consistency_bonus)

        # 🔧 預測特別號碼
        predicted_special = predict_special_number(history, lottery_rules, predicted_numbers)
        
        result = {
            'numbers': predicted_numbers,
            'confidence': float(final_confidence),
            'method': f'進階集成 (Boosting:{len(weak_strategies)} + 關聯分析 + 特徵加權)',
            'probabilities': [float(score) for _, score in sorted_numbers[:pick_count]],
            'meta_info': {
                'base_strategies': len(base_strategies),
                'weak_strategies_boosted': len(weak_strategies),
                'co_occurrence_pairs': len(co_occurrence),
                'consistency_score': float(consistency)
            }
        }
        
        # 🔧 添加特別號碼
        if predicted_special is not None:
            result['special'] = predicted_special
        
        return result

    def ensemble_predict(
        self,
        history: List[Dict],
        lottery_rules: Dict
    ) -> Dict:
        """
        超級集成預測策略 (AI + 統計 混合投票)
        整合深度學習模型與統計策略，動態調整權重
        """
        pick_count = lottery_rules.get('pickCount', 6)
        data_size = len(history)
        
        # ===== 1. 定義策略池（根據數據量動態調整）=====
        strategies = []
        
        # 統計策略（數據量少時權重高）
        stat_weight_multiplier = 1.5 if data_size < 100 else 1.0
        strategies.extend([
            ('frequency', self.frequency_predict, 1.0 * stat_weight_multiplier),
            ('bayesian', self.bayesian_predict, 1.2 * stat_weight_multiplier),
            ('markov', self.markov_predict, 1.5 * stat_weight_multiplier),
            ('monte_carlo', self.monte_carlo_predict, 1.1 * stat_weight_multiplier),
            ('trend', self.trend_predict, 1.3),
            ('deviation', self.deviation_predict, 1.4),
            ('number_pairs', self.number_pairs_predict, 1.6),
            ('pattern_recognition', self.pattern_recognition_predict, 1.5),
            ('cycle_analysis', self.cycle_analysis_predict, 1.4),
        ])
        
        # KNN 相似度（中等數據量效果好）
        if data_size >= 60:
            strategies.append(('knn_similarity', self._knn_like_predict, 1.8))
        
        # ===== 2. AI 模型（數據量充足時加入）=====
        ai_models_included = []
        
        # Prophet（需要至少 30 期）
        if data_size >= 30:
            try:
                from models.prophet_model import ProphetPredictor
                prophet = ProphetPredictor()
                strategies.append(('ai_prophet', lambda h, r: self._run_async_predict(prophet.predict(h, r)), 2.0))
                ai_models_included.append('Prophet')
            except Exception as e:
                logger.debug(f"Prophet 模型未加載: {e}")
        
        # XGBoost（需要至少 50 期）
        if data_size >= 50:
            try:
                from models.xgboost_model import XGBoostPredictor
                xgboost = XGBoostPredictor()
                strategies.append(('ai_xgboost', lambda h, r: self._run_async_predict(xgboost.predict(h, r)), 2.2))
                ai_models_included.append('XGBoost')
            except Exception as e:
                logger.debug(f"XGBoost 模型未加載: {e}")
        
        # LSTM（需要至少 70 期，且數據量越多權重越高）
        if data_size >= 70:
            try:
                from models.lstm_model import LSTMPredictor
                lstm = LSTMPredictor()
                # 數據量越多，LSTM 權重越高（200+ 期時達到最高 3.0）
                lstm_weight = min(3.0, 2.0 + (data_size - 70) / 200)
                strategies.append(('ai_lstm', lambda h, r: self._run_async_predict(lstm.predict(h, r)), lstm_weight))
                ai_models_included.append('LSTM')
            except Exception as e:
                logger.debug(f"LSTM 模型未加載: {e}")
        
        # ===== 3. 執行所有策略並收集結果 =====
        number_scores = defaultdict(float)
        total_strategy_weights = 0
        results_info = []
        successful_strategies = 0
        
        for name, func, weight in strategies:
            try:
                result = func(history, lottery_rules)
                total_strategy_weights += weight
                successful_strategies += 1
                
                # 將預測結果轉換為分數
                probs = result.get('probabilities')
                if probs and len(probs) == len(result['numbers']):
                    # 有概率信息，使用概率加權
                    for num, prob in zip(result['numbers'], probs):
                        number_scores[num] += prob * weight * 10
                else:
                    # 沒有概率，使用排名分（第1名得分最高）
                    for rank, num in enumerate(result['numbers']):
                        rank_score = (pick_count - rank) / pick_count  # 1.0 -> 0.17
                        number_scores[num] += rank_score * weight
                
                results_info.append(f"{name}: {result['numbers']}")
                
            except Exception as e:
                logger.warning(f"策略 {name} 執行失敗: {e}")
        
        # ===== 4. 投票選出最終號碼 =====
        sorted_numbers = sorted(number_scores.items(), key=lambda x: x[1], reverse=True)
        predicted_numbers = sorted([num for num, _ in sorted_numbers[:pick_count]])
        
        # ===== 5. 計算信心度（根據策略一致性）=====
        # 檢查前 pick_count 個號碼的分數差異
        top_scores = [score for _, score in sorted_numbers[:pick_count]]
        if len(top_scores) > 1:
            score_std = np.std(top_scores)
            score_mean = np.mean(top_scores)
            # 分數越集中（標準差越小），信心度越高
            consistency_factor = 1 - min(score_std / score_mean, 0.5) if score_mean > 0 else 0.5
        else:
            consistency_factor = 0.5
        
        # 基礎信心度 + AI 模型加成 + 一致性加成
        base_confidence = 0.75
        ai_bonus = len(ai_models_included) * 0.03  # 每個 AI 模型 +3%
        consistency_bonus = consistency_factor * 0.15
        final_confidence = min(0.95, base_confidence + ai_bonus + consistency_bonus)
        
        # ===== 6. 生成詳細報告 =====
        method_desc = f'超級集成預測 ({successful_strategies} 策略投票'
        if ai_models_included:
            method_desc += f' + {len(ai_models_included)} AI模型'
        method_desc += ')'
        
        # 🔧 預測特別號碼
        predicted_special = predict_special_number(history, lottery_rules, predicted_numbers)
        
        result = {
            'numbers': predicted_numbers,
            'confidence': float(final_confidence),
            'method': method_desc,
            'probabilities': [float(score) for _, score in sorted_numbers[:pick_count]],
            'details': results_info,
            'meta_info': {
                'total_strategies': successful_strategies,
                'ai_models': ai_models_included,
                'data_size': data_size,
                'consistency_score': float(consistency_factor)
            }
        }
        
        # 🔧 添加特別號碼
        if predicted_special is not None:
            result['special'] = predicted_special
        
        return result
    
    def _run_async_predict(self, coro):
        """
        同步執行異步預測函數（用於集成中調用 AI 模型）
        """
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(coro)
    
    # ===== 輔助方法 =====
    
    def _calculate_gaps(self, history, index, min_num, max_num):
        """計算截止到 index 期，每個號碼的遺漏值 (Gap)"""
        gaps = np.zeros(max_num + 1)
        # 初始化為一個較大值，表示很久沒出現
        gaps[:] = 100 
        
        # 向回遍歷尋找上次出現的位置
        # 為了效率，只看最近 100 期
        lookback = 100
        start_search = max(0, index - lookback)
        
        for num in range(min_num, max_num + 1):
            found = False
            for i in range(index - 1, start_search - 1, -1):
                if num in history[i]['numbers']:
                    gaps[num] = (index - 1) - i
                    found = True
                    break
            if not found:
                gaps[num] = lookback # 超過 lookback 沒出現
                
        return gaps[min_num:max_num+1] # 只返回有效範圍

    def _prepare_enhanced_ml_data(self, history, pick_count, min_num, max_num):
        # 這裡保留接口，但實際邏輯已轉移到 _knn_like_predict
        return [], []
    
    def _extract_enhanced_features(self, history, index, pick_count, min_num, max_num):
        return np.array([])
    
    # ===== 高級預測策略 (新增) =====
    
    def entropy_predict(self, history: List[Dict], lottery_rules: Dict) -> Dict:
        """
        信息熵分析策略
        使用信息熵識別號碼的「隨機性異常」，發現隱藏規律
        """
        try:
            advanced = get_advanced_strategies()
            return advanced.entropy_analysis_predict(history, lottery_rules)
        except Exception as e:
            logger.error(f"信息熵預測失敗: {str(e)}", exc_info=True)
            # 回退到頻率分析
            return self.frequency_predict(history, lottery_rules)
    
    def clustering_predict(self, history: List[Dict], lottery_rules: Dict) -> Dict:
        """
        號碼聚類策略
        使用 K-Means/DBSCAN 發現號碼組合模式
        """
        try:
            advanced = get_advanced_strategies()
            return advanced.clustering_predict(history, lottery_rules)
        except Exception as e:
            logger.error(f"聚類預測失敗: {str(e)}", exc_info=True)
            return self.frequency_predict(history, lottery_rules)
    
    def dynamic_ensemble_predict(self, history: List[Dict], lottery_rules: Dict) -> Dict:
        """
        動態權重集成策略
        根據近期表現自適應調整策略權重
        """
        try:
            advanced = get_advanced_strategies()
            return advanced.dynamic_ensemble_predict(history, lottery_rules)
        except Exception as e:
            logger.error(f"動態集成預測失敗: {str(e)}", exc_info=True)
            return self.ensemble_predict(history, lottery_rules)
    
    def temporal_predict(self, history: List[Dict], lottery_rules: Dict) -> Dict:
        """
        增強時間序列策略
        FFT 週期分析 + 多尺度趨勢
        """
        try:
            advanced = get_advanced_strategies()
            return advanced.temporal_enhanced_predict(history, lottery_rules)
        except Exception as e:
            logger.error(f"時間序列預測失敗: {str(e)}", exc_info=True)
            return self.trend_predict(history, lottery_rules)
    
    def feature_engineering_predict(self, history: List[Dict], lottery_rules: Dict) -> Dict:
        """
        多維特徵工程策略
        整合 12+ 維度特徵進行綜合預測
        """
        try:
            advanced = get_advanced_strategies()
            return advanced.feature_engineering_predict(history, lottery_rules)
        except Exception as e:
            logger.error(f"特徵工程預測失敗: {str(e)}", exc_info=True)
            return self.statistical_predict(history, lottery_rules)

# 全局預測引擎實例
prediction_engine = UnifiedPredictionEngine()

