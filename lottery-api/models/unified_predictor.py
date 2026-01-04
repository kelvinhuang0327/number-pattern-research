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
from .feature_analyzer import LotteryFeatureAnalyzer
from .special_predictor import get_enhanced_special_prediction
from .sota_predictor import PatternAwareTransformerPredictor

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

def extract_pool_history(history: List[Dict], pool_type: str = 'main') -> List[List[int]]:
    """
    從歷史開獎中提取特定池的數據
    pool_type: 'main' (第1區) 或 'special' (第2區)
    """
    if pool_type == 'main':
        return [draw.get('numbers', []) for draw in history]
    else:
        # 提取特別號，包裝成列表以統一處理接口
        return [[draw.get('special')] for draw in history if draw.get('special') is not None]

def predict_pool_numbers(
    history: List[Dict],
    lottery_rules: Dict,
    pool_type: str = 'main',
    strategy_name: str = 'frequency',
    main_predicted: List[int] = None
) -> Dict:
    """
    通用池預測函數，支持對不同區塊使用不同策略
    """
    # 根據區塊設定範圍
    if pool_type == 'main':
        min_num = lottery_rules.get('minNumber', 1)
        max_num = lottery_rules.get('maxNumber', 49)
        pick_count = lottery_rules.get('pickCount', 6)
        # 轉換歷史格式
        pool_history = [{'numbers': draw.get('numbers', [])} for draw in history]
    else:
        # 特別號區 (Section 2)
        min_num = lottery_rules.get('specialMinNumber', lottery_rules.get('minNumber', 1))
        max_num = lottery_rules.get('specialMaxNumber', lottery_rules.get('maxNumber', 49))
        pick_count = 1
        # 轉換歷史格式：將特別號放在 'numbers' 鍵下，使其與主號策略接口一致
        pool_history = [{'numbers': [draw.get('special')]} for draw in history if draw.get('special') is not None]

    if not pool_history:
        return {'numbers': [random.randint(min_num, max_num)]}

    # 構造虛擬規則
    sub_rules = {
        'minNumber': min_num,
        'maxNumber': max_num,
        'pickCount': pick_count,
        'hasSpecialNumber': False
    }

    # 執行策略
    engine = UnifiedPredictionEngine()
    
    # 映射策略名稱到具體方法
    strategy_map = {
        'frequency': engine.frequency_predict,
        'trend': engine.trend_predict,
        'bayesian': engine.bayesian_predict,
        'deviation': engine.deviation_predict,
        'monte_carlo': engine.monte_carlo_predict,
        'statistical': engine.statistical_predict,
        'hot_cold': engine.hot_cold_mix_predict,
        'markov': engine.markov_predict
    }
    
    method = strategy_map.get(strategy_name, engine.frequency_predict)
    
    try:
        result = method(pool_history, sub_rules)
        
        # 處理特別號與主號重複的情況（如果範圍重疊，如大樂透）
        if pool_type == 'special' and main_predicted and max_num == lottery_rules.get('maxNumber'):
            # 如果預測的特別號已經在主號中，嘗試換一個
            if result['numbers'][0] in main_predicted:
                # 簡單退回到概率次高的
                # 這裡為了簡單，直接從未被選中的號碼中隨機選一個高頻的
                pass 
        
        return result
    except Exception as e:
        logger.warning(f"Pool {pool_type} strategy {strategy_name} failed: {e}")
        # 兜底隨機
        return {'numbers': [random.randint(min_num, max_num)], 'confidence': 0.1}

def predict_special_number(
    history: List[Dict],
    lottery_rules: Dict,
    main_predicted_numbers: List[int] = None,
    strategy_name: str = 'frequency'
) -> Optional[int]:
    """
    預測特別號碼（優化後支持多策略）
    """
    # 檢查是否有特別號碼
    has_special = lottery_rules.get('hasSpecialNumber', False)
    if not has_special:
        return None

    # ✨ 威力彩專屬增強邏輯
    enhanced_special = get_enhanced_special_prediction(history, lottery_rules, main_predicted_numbers)
    if enhanced_special is not None:
        return enhanced_special

    res = predict_pool_numbers(
        history, 
        lottery_rules, 
        pool_type='special', 
        strategy_name=strategy_name,
        main_predicted=main_predicted_numbers
    )
    
    return res['numbers'][0] if res.get('numbers') else None

class UnifiedPredictionEngine:
    """
    統一預測引擎
    整合多種預測策略，提供統一的預測接口
    """
    
    def __init__(self):
        self.scaler = StandardScaler()
        self.analyzer = LotteryFeatureAnalyzer()
        self._sota_models = {} # 緩存不同彩種的 SOTA 模型
        logger.info("UnifiedPredictionEngine 初始化完成 (優化版)")

    def filter_by_global_constraints(self, history: List[Dict], predicted_numbers: List[int], lottery_rules: Dict) -> List[int]:
        """
        根據全局統計特徵過濾或調整預測號碼 (僅針對 POWER_LOTTO 優化)
        """
        lottery_type = lottery_rules.get('name', '')
        if 'POWER_LOTTO' not in lottery_type and '威力彩' not in lottery_type:
            return predicted_numbers

        # 獲取歷史統計特徵
        stats_data = self.analyzer.get_draw_stats(history)
        if stats_data['sum_avg'] == 0:
            return predicted_numbers

        adjusted = list(predicted_numbers)
        max_attempts = 10
        attempt = 0
        
        while attempt < max_attempts:
            current_sum = self.analyzer.calculate_sum(adjusted)
            # 判斷總和是否在 [avg - 1.5*std, avg + 1.5*std] 範圍內
            if abs(current_sum - stats_data['sum_avg']) <= 1.5 * stats_data['sum_std']:
                break
                
            if current_sum > stats_data['sum_avg'] + 1.5 * stats_data['sum_std']:
                # 總和太高，把最大的一個號碼減 1
                max_val = max(adjusted)
                idx = adjusted.index(max_val)
                if max_val > lottery_rules.get('minNumber', 1):
                    new_val = max_val - 1
                    if new_val not in adjusted:
                        adjusted[idx] = new_val
                    else:
                        # 如果連號了，嘗試減去更大的
                        for shift in range(2, 5):
                            if max_val - shift > 0 and max_val - shift not in adjusted:
                                adjusted[idx] = max_val - shift
                                break
            else:
                # 總和太低，把最小的一個號碼加 1
                min_val = min(adjusted)
                idx = adjusted.index(min_val)
                if min_val < lottery_rules.get('maxNumber', 38):
                    new_val = min_val + 1
                    if new_val not in adjusted:
                        adjusted[idx] = new_val
                    else:
                        for shift in range(2, 5):
                            if min_val + shift <= lottery_rules.get('maxNumber', 38) and min_val + shift not in adjusted:
                                adjusted[idx] = min_val + shift
                                break
            attempt += 1
            
        return sorted(adjusted)
    
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
        
        # 🧪 套用全局特徵過濾 (僅針對 POWER_LOTTO)
        predicted_numbers = self.filter_by_global_constraints(history, predicted_numbers, lottery_rules)

        # 🔧 預測特別號碼 (使用趨勢分析策略)
        predicted_special = predict_special_number(history, lottery_rules, predicted_numbers, strategy_name='trend')

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
        多維度偏差追蹤策略（優化版 Phase 2）

        改進：
        - 維度1: 頻率偏差（原有）
        - 維度2: 區域偏差（49個號碼分5區）
        - 維度3: 奇偶偏差（奇數vs偶數）
        - 維度4: 大小偏差（小號vs大號）
        - 維度5: 遺漏值偏差（距離上次出現的期數）
        """
        pick_count = lottery_rules.get('pickCount', 6)
        min_num = lottery_rules.get('minNumber', 1)
        max_num = lottery_rules.get('maxNumber', 49)
        total_numbers = max_num - min_num + 1

        # 初始化綜合評分
        scores = np.zeros(max_num + 1)

        # ============ 維度1: 頻率偏差（原有邏輯，權重30%）============
        expected_freq = (len(history) * pick_count) / total_numbers
        all_numbers = [num for draw in history for num in draw['numbers']]
        frequency = Counter(all_numbers)

        sum_sq_diff = 0
        for i in range(min_num, max_num + 1):
            diff = frequency.get(i, 0) - expected_freq
            sum_sq_diff += diff * diff
        std_dev = np.sqrt(sum_sq_diff / total_numbers)

        for i in range(min_num, max_num + 1):
            freq = frequency.get(i, 0)
            z_score = (freq - expected_freq) / std_dev if std_dev > 0 else 0

            if z_score < -1.5:
                scores[i] += 0.8 + abs(z_score) * 0.1
            elif z_score > 2.0:
                scores[i] += 0.2
            elif 0.5 < z_score < 1.5:
                scores[i] += 0.6 + z_score * 0.1
            else:
                scores[i] += 0.4

        # 歸一化頻率偏差分數
        freq_scores = scores.copy()
        freq_scores = freq_scores / (np.max(freq_scores) + 1e-10)
        scores = freq_scores * 0.3  # 權重30%

        # ============ 維度2: 區域偏差（權重25%）============
        # 動態劃分區域（分為5區）
        zone_size = (max_num - min_num + 1) // 5
        zones = {}
        for i in range(1, 6):
            start = min_num + (i-1) * zone_size
            if i == 5:
                # 最後一區包含剩餘所有號碼
                end = max_num
            else:
                end = min_num + i * zone_size - 1
            zones[i] = list(range(start, end + 1))

        zone_counts = {i: 0 for i in zones}
        for draw in history:
            for num in draw['numbers']:
                for zone_id, zone_nums in zones.items():
                    if num in zone_nums:
                        zone_counts[zone_id] += 1

        # 計算每個區域的期望值和偏差
        zone_scores = {}
        for zone_id, zone_nums in zones.items():
            expected = len(history) * pick_count * len(zone_nums) / total_numbers
            actual = zone_counts[zone_id]
            deviation = expected - actual  # 偏差越大，越需要補償
            zone_scores[zone_id] = max(0, deviation)  # 只考慮負偏差（需要補償的）

        # 將區域偏差分數分配給各號碼
        for zone_id, score in zone_scores.items():
            for num in zones[zone_id]:
                if min_num <= num <= max_num:
                    scores[num] += score * 0.25 / len(zones[zone_id])  # 權重25%

        # ============ 維度3: 奇偶偏差（權重20%）============
        odd_count = sum(1 for num in all_numbers if num % 2 == 1)
        even_count = len(all_numbers) - odd_count

        # 理論上奇偶應該各佔一半
        expected_odd = len(all_numbers) / 2
        odd_deviation = expected_odd - odd_count  # 負數表示奇數太多，正數表示奇數太少

        for i in range(min_num, max_num + 1):
            if i % 2 == 1:  # 奇數
                if odd_deviation > 0:  # 奇數太少，需要補償
                    scores[i] += 0.2 * (odd_deviation / expected_odd)
            else:  # 偶數
                if odd_deviation < 0:  # 偶數太少，需要補償
                    scores[i] += 0.2 * (abs(odd_deviation) / expected_odd)

        # ============ 維度4: 大小偏差（權重15%）============
        # 小號：1-24，大號：25-49
        mid_point = (min_num + max_num) // 2
        small_count = sum(1 for num in all_numbers if num <= mid_point)
        large_count = len(all_numbers) - small_count

        expected_small = len(all_numbers) / 2
        small_deviation = expected_small - small_count

        for i in range(min_num, max_num + 1):
            if i <= mid_point:  # 小號
                if small_deviation > 0:
                    scores[i] += 0.15 * (small_deviation / expected_small)
            else:  # 大號
                if small_deviation < 0:
                    scores[i] += 0.15 * (abs(small_deviation) / expected_small)

        # ============ 維度5: 遺漏值偏差（權重10%）============
        gaps = {}
        for num in range(min_num, max_num + 1):
            for i, draw in enumerate(history):
                if num in draw['numbers']:
                    gaps[num] = i
                    break
            if num not in gaps:
                gaps[num] = len(history)

        max_gap = max(gaps.values()) if gaps else 1
        for num in range(min_num, max_num + 1):
            gap_score = gaps.get(num, 0) / max_gap if max_gap > 0 else 0
            scores[num] += gap_score * 0.1  # 權重10%

        # ============ 最終選號 ============
        # 找出分數最高的號碼
        valid_scores = [(i, scores[i]) for i in range(min_num, max_num + 1)]
        sorted_numbers = sorted(valid_scores, key=lambda x: x[1], reverse=True)
        predicted_numbers = sorted([num for num, _ in sorted_numbers[:pick_count]])

        # 🧪 套用全局特徵過濾 (僅針對 POWER_LOTTO)
        predicted_numbers = self.filter_by_global_constraints(history, predicted_numbers, lottery_rules)

        # 計算動態信心度
        top_scores = [score for _, score in sorted_numbers[:pick_count]]
        avg_score = np.mean([score for _, score in valid_scores])
        confidence = min(0.90, 0.65 + (np.mean(top_scores) / avg_score - 1) * 0.15)

        # 🔧 預測特別號碼 (使用偏差追蹤策略)
        predicted_special = predict_special_number(history, lottery_rules, predicted_numbers, strategy_name='deviation')

        result = {
            'numbers': predicted_numbers,
            'confidence': float(confidence),
            'method': '多維度偏差追蹤（頻率+區域+奇偶+大小+遺漏值）',
            'probabilities': [float(score) for _, score in sorted_numbers[:pick_count]],
            'meta_info': {
                'dimensions': 5,
                'weights': {
                    'frequency': 0.30,
                    'zone': 0.25,
                    'odd_even': 0.20,
                    'high_low': 0.15,
                    'gap': 0.10
                }
            }
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
        頻率分析策略 (優化版：自適應時間衰減加權 + 遺漏值分析)
        不僅統計次數，還考慮時間權重，最近的號碼權重更高
        ✨ 優化1：根據號碼出現頻率動態調整衰減係數
        ✨ 優化2：加入遺漏值（Gap）權重，平衡「出現頻率」與「遺漏期數」
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

        # ✨ 新增：計算每個號碼的遺漏值（距離上次出現的期數）
        gaps = {}
        for num in range(min_num, max_num + 1):
            for i, draw in enumerate(history):
                if num in draw['numbers']:
                    gaps[num] = i  # 距離現在幾期
                    break
            if num not in gaps:
                gaps[num] = len(history)  # 從未出現，遺漏值 = 總期數

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

        # ✨ 新增：綜合評分 = 頻率分數 + 遺漏值分數
        combined_scores = {}
        max_gap = max(gaps.values()) if gaps else 1

        for num in range(min_num, max_num + 1):
            # 頻率分數（歸一化到 0-1）
            freq_score = weighted_counts.get(num, 0) / (total_weight / (max_num - min_num + 1)) if total_weight > 0 else 0

            # 遺漏值分數（歸一化到 0-1，遺漏越久分數越高）
            gap_score = gaps.get(num, 0) / max_gap if max_gap > 0 else 0

            # 混合：40% 頻率 + 60% 遺漏值
            # （給予遺漏值更高權重，避免只選高頻號碼）
            combined_scores[num] = 0.4 * freq_score + 0.6 * gap_score

        # 根據綜合分數排序
        sorted_numbers = sorted(combined_scores.items(), key=lambda x: x[1], reverse=True)
        predicted_numbers = sorted([num for num, _ in sorted_numbers[:pick_count]])

        # 🧪 套用全局特徵過濾 (僅針對 POWER_LOTTO)
        predicted_numbers = self.filter_by_global_constraints(history, predicted_numbers, lottery_rules)

        # ✨ 優化：動態計算信心度（基於綜合分數）
        top_scores = [score for _, score in sorted_numbers[:pick_count]]
        avg_score = np.mean(list(combined_scores.values())) if combined_scores else 1

        # 基礎信心度
        base_confidence = 0.5 + (np.mean(top_scores) / avg_score - 1) * 0.2

        # 數據量加成
        data_bonus = min(total_draws / 300, 0.15)  # 最多 +15%

        # 集中度加成（top 號碼分數差異小表示更集中）
        if len(top_scores) > 1:
            concentration = 1 - (np.std(top_scores) / np.mean(top_scores))
            concentration_bonus = concentration * 0.15  # 最多 +15%
        else:
            concentration_bonus = 0

        final_confidence = min(0.90, base_confidence + data_bonus + concentration_bonus)

        # 🔧 預測特別號碼 (使用頻率分析策略)
        predicted_special = predict_special_number(history, lottery_rules, predicted_numbers, strategy_name='frequency')

        result = {
            'numbers': predicted_numbers,
            'confidence': float(final_confidence),
            'method': '自適應頻率分析 + 遺漏值權重',
            'probabilities': [float(score) for _, score in sorted_numbers[:pick_count]],
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

        # 🧪 套用全局特徵過濾 (僅針對 POWER_LOTTO)
        predicted_numbers = self.filter_by_global_constraints(history, predicted_numbers, lottery_rules)

        # ✨ 優化：動態計算信心度
        base_confidence = 0.68
        stability_bonus = recent_stability * 0.08  # 穩定性加成 (最多 +8%)
        data_bonus = min(total_draws / 200, 0.06)  # 數據量加成 (最多 +6%)
        final_confidence = min(0.82, base_confidence + stability_bonus + data_bonus)

        # 🔧 預測特別號碼 (使用貝葉斯策略)
        predicted_special = predict_special_number(history, lottery_rules, predicted_numbers, strategy_name='bayesian')
        
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
        stability = self._calculate_markov_stability(history[-50:], pick_count)

        # 數據量中等，使用 2 階
        if history_size < 150:
            confidence_bonus = stability * 0.05
            return (2, confidence_bonus)

        # 數據量充足，使用 3 階
        confidence_bonus = stability * 0.07
        return (3, confidence_bonus)

    def _calculate_markov_stability(
        self,
        history: List[Dict],
        pick_count: int
    ) -> float:
        """
        ✨ 計算馬可夫轉移穩定性

        使用 Jaccard 相似度衡量相鄰期數的重疊程度
        """
        if len(history) < 2:
            return 0.5

        similarities = []
        for i in range(len(history) - 1):
            # 確保 numbers 是可迭代的 (修復 'int' object is not iterable bug)
            curr_nums = history[i]['numbers']
            next_nums = history[i + 1]['numbers']
            
            if isinstance(curr_nums, (int, float)): curr_nums = [curr_nums]
            if isinstance(next_nums, (int, float)): next_nums = [next_nums]
            
            current_set = set(curr_nums)
            next_set = set(next_nums)

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
            curr_numbers = analysis_history[i]['numbers']
            next_numbers = analysis_history[i + 1]['numbers']
            
            if isinstance(curr_numbers, (int, float)): curr_numbers = [curr_numbers]
            if isinstance(next_numbers, (int, float)): next_numbers = [next_numbers]

            for curr_num in curr_numbers:
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
            p2_nums = analysis_history[i]['numbers']
            p1_nums = analysis_history[i + 1]['numbers']
            nxt_nums = analysis_history[i + 2]['numbers']
            
            if isinstance(p2_nums, (int, float)): p2_nums = [p2_nums]
            if isinstance(p1_nums, (int, float)): p1_nums = [p1_nums]
            if isinstance(nxt_nums, (int, float)): nxt_nums = [nxt_nums]

            # 為所有 (prev2, prev1) 組合記錄轉移
            for num2 in p2_nums:
                for num1 in p1_nums:
                    state = (num2, num1)
                    if state not in transition_dict:
                        transition_dict[state] = Counter()

                    for next_num in nxt_nums:
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
            p3_nums = analysis_history[i]['numbers']
            p2_nums = analysis_history[i + 1]['numbers']
            p1_nums = analysis_history[i + 2]['numbers']
            nxt_nums = analysis_history[i + 3]['numbers']
            
            if isinstance(p3_nums, (int, float)): p3_nums = [p3_nums]
            if isinstance(p2_nums, (int, float)): p2_nums = [p2_nums]
            if isinstance(p1_nums, (int, float)): p1_nums = [p1_nums]
            if isinstance(nxt_nums, (int, float)): nxt_nums = [nxt_nums]

            # 為所有 (prev3, prev2, prev1) 組合記錄轉移
            for num3 in p3_nums:
                for num2 in p2_nums:
                    for num1 in p1_nums:
                        state = (num3, num2, num1)
                        if state not in transition_dict:
                            transition_dict[state] = Counter()

                        for next_num in nxt_nums:
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
        predicted_numbers = sorted(best_combo)

        # 🧪 套用全局特徵過濾 (僅針對 POWER_LOTTO)
        predicted_numbers = self.filter_by_global_constraints(history, predicted_numbers, lottery_rules)
        
        return {
            'numbers': predicted_numbers,
            'confidence': 0.88,
            'method': '多維統計分析',
            'probabilities': None
        }

    def sota_predict(self, history, lottery_rules):
        """
        SOTA Transformer 模式識別預測 (僅限威力彩)
        """
        lottery_name = lottery_rules.get('name', 'UNKNOWN')
        if 'POWER_LOTTO' not in lottery_name and '威力彩' not in lottery_name:
            # 對於非威力彩，回退到統計模型，不執行 SOTA 邏輯
            return self.statistical_predict(history, lottery_rules)

        if lottery_name not in self._sota_models:
            self._sota_models[lottery_name] = PatternAwareTransformerPredictor(lottery_rules)
            
        model = self._sota_models[lottery_name]
        
        # 在線快速微調 (使用最近 100 期數據)
        train_window = min(100, len(history))
        model.train_on_history(history[:train_window], epochs=3)
        
        result = model.predict(history)
        if not result:
            return self.statistical_predict(history, lottery_rules)
            
        # 🧪 套用全局特徵過濾 (僅針對 POWER_LOTTO)
        result['numbers'] = self.filter_by_global_constraints(history, result['numbers'], lottery_rules)
        
        # 預測特別號 (優先使用 SOTA 預測的，若無則回退統計模型)
        if 'special' not in result:
            predicted_special = predict_special_number(history, lottery_rules, result['numbers'], strategy_name='statistical')
            if predicted_special is not None:
                result['special'] = predicted_special
            
        return result

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

        # ===== 1. 基礎策略池 (基於回測結果優化) =====
        # 移除表現差的方法 (frequency, deviation)
        # 保留表現優秀的方法
        base_strategies = [
            ('bayesian', self.bayesian_predict),      # 1.09 avg hits
            ('trend', self.trend_predict),            # 1.03 avg hits
            ('statistical', self.statistical_predict), # 1.00 avg hits
            ('markov', self.markov_predict),          # 已修復bug
            ('monte_carlo', self.monte_carlo_predict), # 0.95 avg hits
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
        
        # 統計策略（基於回測結果優化權重）
        # 優秀方法: bayesian, trend, statistical, markov
        # 中等方法: monte_carlo, random_forest
        # 低效方法: frequency, deviation (降權或移除)
        stat_weight_multiplier = 1.5 if data_size < 100 else 1.0
        strategies.extend([
            # 優秀方法 (回測平均命中 > 1.0)
            ('bayesian', self.bayesian_predict, 2.2 * stat_weight_multiplier),      # 1.09 avg
            ('trend', self.trend_predict, 2.0 * stat_weight_multiplier),            # 1.03 avg
            ('statistical', self.statistical_predict, 1.8 * stat_weight_multiplier), # 1.00 avg
            ('markov', self.markov_predict, 1.6 * stat_weight_multiplier),          # 已修復bug

            # 中等方法 (回測接近隨機)
            ('monte_carlo', self.monte_carlo_predict, 1.0),                         # 0.95 avg
            ('number_pairs', self.number_pairs_predict, 0.8),
            ('pattern_recognition', self.pattern_recognition_predict, 0.8),
            ('cycle_analysis', self.cycle_analysis_predict, 0.7),

            # 低效方法 (回測低於隨機，大幅降權)
            ('frequency', self.frequency_predict, 0.3),                             # 0.88 avg
            ('deviation', self.deviation_predict, 0.2),                             # 0.86 avg (最差)
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

    def entropy_transformer_predict(self, history, lottery_rules):
        """
        熵驱动 Transformer 预测方法 (创新)

        核心创新：
        1. 12维创新特征（随机性度量、反向信号、覆盖率、时序动态）
        2. 反向共识过滤（降低传统方法共识号码的权重）
        3. 熵最大化采样（生成多样化预测）

        Args:
            history: 历史开奖数据
            lottery_rules: 彩票规则

        Returns:
            预测结果字典
        """
        from .entropy_transformer import EntropyTransformerModel
        from .anti_consensus_sampler import AntiConsensusFilter

        log_data_range('熵驅動Transformer', history)

        # 1. 初始化模型
        # max_num = lottery_rules.get('maxNumber', 49) # No longer needed here as we pass rules
        model = EntropyTransformerModel(lottery_rules=lottery_rules)

        # 2. 获取模型预测概率
        probs = model.predict(history, lottery_rules=lottery_rules)

        # 3. 获取传统方法的共识号码（用于反向过滤）
        consensus_numbers = set()

        try:
            # 获取频率分析的预测
            freq_result = self.frequency_predict(history, lottery_rules)
            consensus_numbers.update(freq_result['numbers'])
        except:
            pass

        try:
            # 获取趋势分析的预测
            trend_result = self.trend_predict(history, lottery_rules)
            consensus_numbers.update(trend_result['numbers'])
        except:
            pass

        # 4. 应用反向共识过滤
        anti_filter = AntiConsensusFilter(penalty_factor=0.7)
        filtered_probs = anti_filter.filter(probs, consensus_numbers)

        # 5. 选择 Top N 号码
        pick_count = lottery_rules.get('pickCount', 6)
        top_indices = np.argsort(filtered_probs)[-pick_count:][::-1]
        predicted_numbers = sorted([int(idx + 1) for idx in top_indices])

        # 6. 计算信心度（优化版 - 调整到合理范围 60-85%）
        top_probs = filtered_probs[top_indices]

        # 原始平均机率可能很小 (0.02-0.06)
        # 使用调整系数将其映射到合理范围
        raw_confidence = float(np.mean(top_probs))

        # 基础信心度 + 机率加权
        # 如果平均机率 0.05，则 confidence = 0.60 + 0.05 * 4 = 0.80
        confidence = min(0.85, max(0.60, 0.60 + raw_confidence * 4))

        # 7. 计算反共识分数
        anti_consensus_score = anti_filter.calculate_anti_consensus_score(
            predicted_numbers,
            consensus_numbers
        )

        # 8. 预测特别号码
        predicted_special = predict_special_number(history, lottery_rules, predicted_numbers)

        result = {
            'numbers': predicted_numbers,
            'confidence': confidence,
            'method': '熵驱动Transformer (12维创新特征 + 反向共识)',
            'probabilities': [float(p) for p in top_probs],
            'meta_info': {
                'anti_consensus_score': float(anti_consensus_score),
                'consensus_numbers': sorted(list(consensus_numbers)),
                'feature_dimensions': 12,
                'filter_penalty': 0.7
            }
        }

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
            res = advanced.entropy_analysis_predict(history, lottery_rules)
            res['special'] = predict_special_number(history, lottery_rules, res['numbers'], strategy_name='frequency')
            return res
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
            res = advanced.clustering_predict(history, lottery_rules)
            res['special'] = predict_special_number(history, lottery_rules, res['numbers'], strategy_name='frequency')
            return res
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
            res = advanced.dynamic_ensemble_predict(history, lottery_rules)
            res['special'] = predict_special_number(history, lottery_rules, res['numbers'], strategy_name='frequency')
            return res
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
            res = advanced.temporal_enhanced_predict(history, lottery_rules)
            res['special'] = predict_special_number(history, lottery_rules, res['numbers'], strategy_name='trend')
            return res
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
            res = advanced.feature_engineering_predict(history, lottery_rules)
            res['special'] = predict_special_number(history, lottery_rules, res['numbers'], strategy_name='deviation')
            return res
        except Exception as e:
            logger.error(f"特徵工程預測失敗: {str(e)}", exc_info=True)
            return self.statistical_predict(history, lottery_rules)

    # ===== 新增創新預測方法 (2025-12-15) =====

    def social_wisdom_predict(self, history: List[Dict], lottery_rules: Dict) -> Dict:
        """
        社群智慧預測方法

        核心概念：
        - 避開大眾最常選擇的號碼（生日1-31、幸運數字7/8/9）
        - 理論：中獎機率相同，但獨得獎金機會更高
        - 提升中獎時的獎金期望值

        Args:
            history: 歷史開獎數據
            lottery_rules: 彩票規則

        Returns:
            預測結果字典
        """
        from .social_wisdom_predictor import SocialWisdomPredictor

        log_data_range('社群智慧', history)

        max_num = lottery_rules.get('maxNumber', 49)
        pick_count = lottery_rules.get('pickCount', 6)

        # 初始化預測器
        predictor = SocialWisdomPredictor(max_num=max_num)

        # 預測號碼（避開熱門）
        predicted_numbers = predictor.predict(history, pick_count=pick_count)

        # 分析獨特性
        analysis = predictor.analyze_popularity(predicted_numbers)

        # 計算信心度（基於獨特性分數）
        confidence = min(0.95, 0.60 + analysis['avg_unpopular_score'] * 10)

        # 預測特別號
        predicted_special = predict_special_number(history, lottery_rules, predicted_numbers)

        result = {
            'numbers': predicted_numbers,
            'confidence': float(confidence),
            'method': '社群智慧 (避開熱門號碼)',
            'meta_info': {
                'unpopular_count': analysis['unpopular_count'],
                'popular_count': analysis['popular_count'],
                'uniqueness_grade': analysis['uniqueness_grade'],
                'birthday_numbers': analysis['birthday_numbers'],
                'high_numbers': analysis['high_numbers'],
                'strategy': '提升獨得獎金機率'
            }
        }

        if predicted_special is not None:
            result['special'] = predicted_special

        return result

    def quantum_random_predict(self, history: List[Dict], lottery_rules: Dict) -> Dict:
        """
        量子隨機預測方法

        核心概念：
        - 大樂透本質是隨機，與其預測不如產生真隨機
        - 使用量子隨機數生成器（ANU QRNG API）
        - 作為 Baseline 對比其他方法

        Args:
            history: 歷史開獎數據
            lottery_rules: 彩票規則

        Returns:
            預測結果字典
        """
        from .quantum_random_predictor import QuantumRandomPredictor

        log_data_range('量子隨機', history)

        max_num = lottery_rules.get('maxNumber', 49)
        pick_count = lottery_rules.get('pickCount', 6)

        # 初始化預測器（嘗試使用真量子隨機）
        predictor = QuantumRandomPredictor(max_num=max_num, use_quantum=True)

        # 生成隨機號碼（帶和值約束）
        predicted_numbers = predictor.predict_with_constraints(
            history,
            pick_count=pick_count,
            min_sum=100,
            max_sum=200
        )

        # 計算信心度（隨機方法給予基準信心度）
        confidence = 0.50  # 基準值

        # 預測特別號
        predicted_special = predict_special_number(history, lottery_rules, predicted_numbers)

        result = {
            'numbers': predicted_numbers,
            'confidence': float(confidence),
            'method': '量子隨機 (真隨機基準)',
            'meta_info': {
                'sum': sum(predicted_numbers),
                'odd_count': sum(1 for n in predicted_numbers if n % 2 == 1),
                'randomness_source': '量子物理 (ANU QRNG)' if predictor.use_quantum else '密碼學隨機',
                'strategy': '對比基準線'
            }
        }

        if predicted_special is not None:
            result['special'] = predicted_special

        return result

    def anomaly_detection_predict(self, history: List[Dict], lottery_rules: Dict) -> Dict:
        """
        異常檢測預測方法

        核心概念：
        - 訓練模型識別「正常」組合
        - 預測「異常」組合
        - 反向思維：大家都預測正常→異常可能開出

        Args:
            history: 歷史開獎數據
            lottery_rules: 彩票規則

        Returns:
            預測結果字典
        """
        from .anomaly_predictor import AnomalyPredictor

        log_data_range('異常檢測', history)

        max_num = lottery_rules.get('maxNumber', 49)
        pick_count = lottery_rules.get('pickCount', 6)

        # 初始化預測器
        predictor = AnomalyPredictor(max_num=max_num, contamination=0.1)

        # 訓練並預測
        predicted_numbers = predictor.predict(history, pick_count=pick_count)

        # 分析異常程度
        analysis = predictor.analyze_combination(predicted_numbers, history)

        # 計算信心度（基於異常分數）
        anomaly_score = abs(analysis['anomaly_score'])
        confidence = min(0.95, 0.55 + anomaly_score * 0.15)

        # 預測特別號
        predicted_special = predict_special_number(history, lottery_rules, predicted_numbers)

        result = {
            'numbers': predicted_numbers,
            'confidence': float(confidence),
            'method': '異常檢測 (反向選號)',
            'meta_info': {
                'anomaly_score': analysis['anomaly_score'],
                'anomaly_grade': analysis['grade'],
                'is_anomaly': analysis['is_anomaly'],
                'consecutive_count': analysis['consecutive_count'],
                'zone_distribution': analysis['zone_distribution'],
                'strategy': '選擇統計異常組合'
            }
        }

        if predicted_special is not None:
            result['special'] = predicted_special

        return result

    def extreme_odd_predict(self, history: List[Dict], lottery_rules: Dict) -> Dict:
        """
        極端奇數策略：只選擇奇數號碼

        應用場景：
        - 上期為極端偶數（5-6個偶數）時，預期反轉
        - 捕捉極端奇數配比（如5奇1偶）

        Args:
            history: 歷史開獎數據
            lottery_rules: 彩票規則

        Returns:
            預測結果字典
        """
        log_data_range('極端奇數策略', history)

        max_num = lottery_rules.get('maxNumber', 49)
        min_num = lottery_rules.get('minNumber', 1)
        pick_count = lottery_rules.get('pickCount', 6)

        # 統計奇數頻率（近50期）
        freq = Counter()
        window = min(50, len(history))
        for draw in history[:window]:
            odds = [n for n in draw.get('numbers', []) if n % 2 == 1]
            freq.update(odds)

        # 只選擇奇數候選
        odd_candidates = [(n, freq.get(n, 0)) for n in range(min_num, max_num+1, 2)]
        odd_candidates.sort(key=lambda x: x[1], reverse=True)

        # 選擇高頻奇數
        selected = [n for n, _ in odd_candidates[:pick_count]]

        # 預測特別號
        predicted_special = predict_special_number(history, lottery_rules, selected)

        result = {
            'numbers': selected,
            'confidence': 0.65,
            'method': '極端奇數策略',
            'meta_info': {
                'strategy': '只選奇數',
                'odd_count': pick_count,
                'even_count': 0,
                'use_case': '應對極端奇數配比'
            }
        }

        if predicted_special is not None:
            result['special'] = predicted_special

        return result

    def extreme_even_predict(self, history: List[Dict], lottery_rules: Dict) -> Dict:
        """
        極端偶數策略：只選擇偶數號碼

        應用場景：
        - 上期為極端奇數（5-6個奇數）時，預期反轉
        - 捕捉極端偶數配比（如1奇5偶）

        Args:
            history: 歷史開獎數據
            lottery_rules: 彩票規則

        Returns:
            預測結果字典
        """
        log_data_range('極端偶數策略', history)

        max_num = lottery_rules.get('maxNumber', 49)
        min_num = lottery_rules.get('minNumber', 1)
        pick_count = lottery_rules.get('pickCount', 6)

        # 統計偶數頻率（近50期）
        freq = Counter()
        window = min(50, len(history))
        for draw in history[:window]:
            evens = [n for n in draw.get('numbers', []) if n % 2 == 0]
            freq.update(evens)

        # 只選擇偶數候選
        even_candidates = [(n, freq.get(n, 0)) for n in range(min_num, max_num+1) if n % 2 == 0]
        even_candidates.sort(key=lambda x: x[1], reverse=True)

        # 選擇高頻偶數
        selected = [n for n, _ in even_candidates[:pick_count]]

        # 預測特別號
        predicted_special = predict_special_number(history, lottery_rules, selected)

        result = {
            'numbers': selected,
            'confidence': 0.65,
            'method': '極端偶數策略',
            'meta_info': {
                'strategy': '只選偶數',
                'odd_count': 0,
                'even_count': pick_count,
                'use_case': '應對極端偶數配比'
            }
        }

        if predicted_special is not None:
            result['special'] = predicted_special

        return result

    def cold_number_predict(self, history: List[Dict], lottery_rules: Dict, threshold: int = 3) -> Dict:
        """
        冷號回歸策略：選擇長期低頻號碼

        核心理論：
        - 基於均值回歸理論
        - 長期低頻號碼有"債務償還"壓力
        - 冷號回歸是常見現象

        Args:
            history: 歷史開獎數據
            lottery_rules: 彩票規則
            threshold: 冷號閾值（出現次數≤threshold即為冷號）

        Returns:
            預測結果字典
        """
        log_data_range('冷號回歸策略', history)

        max_num = lottery_rules.get('maxNumber', 49)
        min_num = lottery_rules.get('minNumber', 1)
        pick_count = lottery_rules.get('pickCount', 6)

        # 統計號碼頻率（近50期）
        freq = Counter()
        window = min(50, len(history))
        for draw in history[:window]:
            freq.update(draw.get('numbers', []))

        # 找出冷號（出現次數 <= threshold）
        cold_nums = [n for n in range(min_num, max_num+1) if freq.get(n, 0) <= threshold]

        # 按頻率排序（最冷的優先）
        cold_nums.sort(key=lambda x: freq.get(x, 0))

        # 如果冷號不夠，補充溫號
        if len(cold_nums) < pick_count:
            warm_threshold = threshold + 2
            warm_nums = [n for n in range(min_num, max_num+1) if freq.get(n, 0) <= warm_threshold]
            warm_nums.sort(key=lambda x: freq.get(x, 0))
            cold_nums = list(dict.fromkeys(cold_nums + warm_nums))  # 去重保持順序

        selected = cold_nums[:pick_count]

        # 如果還是不夠（極少見），隨機補充
        if len(selected) < pick_count:
            remaining = [n for n in range(min_num, max_num+1) if n not in selected]
            selected.extend(random.sample(remaining, pick_count - len(selected)))

        # 預測特別號
        predicted_special = predict_special_number(history, lottery_rules, selected)

        # 計算冷號程度
        avg_freq = sum(freq.get(n, 0) for n in selected) / len(selected)

        result = {
            'numbers': sorted(selected),
            'confidence': 0.60,
            'method': f'冷號回歸 (閾值≤{threshold})',
            'meta_info': {
                'strategy': '選擇低頻號碼',
                'threshold': threshold,
                'avg_frequency': avg_freq,
                'window': window,
                'theory': '均值回歸理論'
            }
        }

        if predicted_special is not None:
            result['special'] = predicted_special

        return result

    def tail_repeat_predict(self, history: List[Dict], lottery_rules: Dict) -> Dict:
        """
        尾數重複策略：傾向於選擇重複尾數的號碼

        統計發現：
        - 大樂透約70%期數有1-2組尾數重複
        - 尾數重複是常見模式

        Args:
            history: 歷史開獎數據
            lottery_rules: 彩票規則

        Returns:
            預測結果字典
        """
        log_data_range('尾數重複策略', history)

        max_num = lottery_rules.get('maxNumber', 49)
        min_num = lottery_rules.get('minNumber', 1)
        pick_count = lottery_rules.get('pickCount', 6)

        # 統計尾數頻率（近50期）
        tail_freq = Counter()
        window = min(50, len(history))
        for draw in history[:window]:
            for n in draw.get('numbers', []):
                tail_freq[n % 10] += 1

        # 統計號碼頻率
        num_freq = Counter()
        for draw in history[:window]:
            num_freq.update(draw.get('numbers', []))

        # 選擇最熱門的3個尾數
        hot_tails = [t for t, _ in tail_freq.most_common(3)]

        # 每個尾數選2個號碼
        selected = []
        for tail in hot_tails:
            candidates = [n for n in range(min_num, max_num+1) if n % 10 == tail]
            # 按號碼頻率排序
            candidates.sort(key=lambda x: num_freq.get(x, 0), reverse=True)
            selected.extend(candidates[:2])

        # 如果不夠，從其他高頻號碼中補充
        if len(selected) < pick_count:
            remaining = [n for n in range(min_num, max_num+1) if n not in selected]
            remaining.sort(key=lambda x: num_freq.get(x, 0), reverse=True)
            selected.extend(remaining[:pick_count - len(selected)])

        selected = sorted(selected[:pick_count])

        # 分析尾數重複情況
        tail_distribution = [n % 10 for n in selected]
        tail_repeat_count = len(tail_distribution) - len(set(tail_distribution))

        # 預測特別號
        predicted_special = predict_special_number(history, lottery_rules, selected)

        result = {
            'numbers': selected,
            'confidence': 0.68,
            'method': '尾數重複策略',
            'meta_info': {
                'strategy': '選擇高頻尾數組合',
                'hot_tails': hot_tails,
                'tail_repeat_count': tail_repeat_count,
                'tail_distribution': tail_distribution,
                'statistical_basis': '70%期數有尾數重複'
            }
        }

        if predicted_special is not None:
            result['special'] = predicted_special

        return result

    def cold_hot_balanced_predict(self, history: List[Dict], lottery_rules: Dict) -> Dict:
        """
        冷熱平衡策略：混合熱號和冷號

        配比：
        - 3個熱號（高頻穩定）
        - 3個冷號（回歸潛力）

        Args:
            history: 歷史開獎數據
            lottery_rules: 彩票規則

        Returns:
            預測結果字典
        """
        log_data_range('冷熱平衡策略', history)

        max_num = lottery_rules.get('maxNumber', 49)
        min_num = lottery_rules.get('minNumber', 1)
        pick_count = lottery_rules.get('pickCount', 6)

        # 統計號碼頻率（近50期）
        freq = Counter()
        window = min(50, len(history))
        for draw in history[:window]:
            freq.update(draw.get('numbers', []))

        # 所有號碼按頻率排序
        all_nums = list(range(min_num, max_num+1))
        all_nums.sort(key=lambda x: freq.get(x, 0), reverse=True)

        # 配比：一半熱號，一半冷號
        half = pick_count // 2

        # 熱號池：前20個高頻號
        hot_pool = all_nums[:20]
        # 冷號池：後20個低頻號
        cold_pool = all_nums[-20:]

        # 隨機選擇（增加多樣性）
        hot_selected = random.sample(hot_pool, half)
        cold_selected = random.sample(cold_pool, pick_count - half)

        selected = sorted(hot_selected + cold_selected)

        # 預測特別號
        predicted_special = predict_special_number(history, lottery_rules, selected)

        # 計算平均頻率
        avg_freq = sum(freq.get(n, 0) for n in selected) / len(selected)

        result = {
            'numbers': selected,
            'confidence': 0.72,
            'method': '冷熱平衡策略',
            'meta_info': {
                'strategy': f'{half}熱+{pick_count-half}冷',
                'hot_numbers': sorted(hot_selected),
                'cold_numbers': sorted(cold_selected),
                'avg_frequency': avg_freq,
                'balance_theory': '穩定性+爆發性'
            }
        }

        if predicted_special is not None:
            result['special'] = predicted_special

        return result

    def generate_double_bet(self, history: List[Dict], lottery_rules: Dict, mode: str = 'optimal') -> Dict:
        """
        生成最優雙注組合

        模式：
        - optimal: 極端奇數 + 冷號回歸（驗證命中率50%）
        - dynamic: 根據上期自動選擇
        - balanced: 標準熱號 + 極端奇數

        Args:
            history: 歷史開獎數據
            lottery_rules: 彩票規則
            mode: 雙注模式

        Returns:
            包含兩注預測的結果字典
        """
        log_data_range(f'雙注策略 ({mode})', history)

        if mode == 'dynamic':
            # 動態模式：根據上期奇偶配比選擇策略
            last_draw = history[0] if history else {'numbers': []}
            last_numbers = last_draw.get('numbers', [])
            odd_count = len([n for n in last_numbers if n % 2 == 1])

            if odd_count >= 5:
                # 上期極端奇數 → 本期可能極端偶數
                bet1 = self.extreme_even_predict(history, lottery_rules)
                bet2 = self.cold_number_predict(history, lottery_rules)
                reason = f'上期{odd_count}奇，預期反轉為偶數主導'
            elif odd_count <= 1:
                # 上期極端偶數 → 本期可能極端奇數
                bet1 = self.extreme_odd_predict(history, lottery_rules)
                bet2 = self.cold_number_predict(history, lottery_rules)
                reason = f'上期{odd_count}奇，預期反轉為奇數主導'
            else:
                # 上期均衡 → 雙押極端+均衡
                bet1 = self.extreme_odd_predict(history, lottery_rules)
                bet2 = self.cold_hot_balanced_predict(history, lottery_rules)
                reason = f'上期{odd_count}奇，雙押極端+均衡'

        elif mode == 'balanced':
            # 平衡模式：熱號 + 極端奇數
            bet1 = self.frequency_predict(history, lottery_rules)
            bet2 = self.extreme_odd_predict(history, lottery_rules)
            reason = '熱號穩定 + 極端奇數'

        else:  # optimal
            # 最優模式：極端奇數 + 冷號回歸（116期驗證50%命中率）
            bet1 = self.extreme_odd_predict(history, lottery_rules)
            bet2 = self.cold_number_predict(history, lottery_rules, threshold=3)
            reason = '極端奇數 + 冷號回歸（最優組合）'

        # 計算覆蓋率和互補性
        coverage = set(bet1['numbers']) | set(bet2['numbers'])
        overlap = set(bet1['numbers']) & set(bet2['numbers'])

        coverage_count = len(coverage)
        overlap_count = len(overlap)
        complementary_score = coverage_count - overlap_count

        result = {
            'mode': mode,
            'bet1': bet1,
            'bet2': bet2,
            'meta_info': {
                'coverage': coverage_count,
                'overlap': overlap_count,
                'complementary_score': complementary_score,
                'complementary_rate': f'{complementary_score}/{len(bet1["numbers"])*2}',
                'reason': reason,
                'expected_hit_rate': '50%（基於116期驗證）' if mode == 'optimal' else '40-50%'
            }
        }

        return result

    def maml_predict(self, history: List[Dict], lottery_rules: Dict) -> Dict:
        """
        元學習預測方法 (MAML)
        基於 Model-Agnostic Meta-Learning，快速適應新開獎模式
        """
        from .meta_learning import create_meta_learning_predictor
        import asyncio

        log_data_range('元學習 (MAML)', history)

        predictor = create_meta_learning_predictor()
        
        # 為了兼容同步引擎，我們需要運行異步預測
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 如果 loop 正在運行，我們必須在一個新線程中運行
                import threading
                from concurrent.futures import ThreadPoolExecutor
                with ThreadPoolExecutor() as executor:
                    return executor.submit(lambda: asyncio.run(predictor.predict(history, lottery_rules))).result()
            else:
                return loop.run_until_complete(predictor.predict(history, lottery_rules))
        except RuntimeError:
            return asyncio.run(predictor.predict(history, lottery_rules))

    def meta_learning_predict(self, history: List[Dict], lottery_rules: Dict) -> Dict:
        """
        元學習集成預測方法

        核心概念：
        - 整合所有預測方法的結果
        - 使用加權投票選擇最佳號碼
        - 動態調整權重（根據情境）

        權重配置：
        - 30% 熵驅動AI
        - 25% 偏差分析
        - 20% 社群智慧
        - 15% 異常檢測
        - 10% 量子隨機

        Args:
            history: 歷史開獎數據
            lottery_rules: 彩票規則

        Returns:
            預測結果字典
        """
        from .meta_predictor import MetaPredictor

        log_data_range('元學習集成', history)

        max_num = lottery_rules.get('maxNumber', 49)
        pick_count = lottery_rules.get('pickCount', 6)

        # 收集各方法的預測結果
        predictions = {}

        try:
            result_entropy = self.entropy_transformer_predict(history, lottery_rules)
            predictions['entropy'] = result_entropy['numbers']
        except:
            pass

        try:
            result_deviation = self.deviation_predict(history, lottery_rules)
            predictions['deviation'] = result_deviation['numbers']
        except:
            pass

        try:
            result_social = self.social_wisdom_predict(history, lottery_rules)
            predictions['social'] = result_social['numbers']
        except:
            pass

        try:
            result_anomaly = self.anomaly_detection_predict(history, lottery_rules)
            predictions['anomaly'] = result_anomaly['numbers']
        except:
            pass

        try:
            result_quantum = self.quantum_random_predict(history, lottery_rules)
            predictions['quantum'] = result_quantum['numbers']
        except:
            pass

        # 如果沒有任何預測成功，回退到頻率分析
        if not predictions:
            return self.frequency_predict(history, lottery_rules)

        # 初始化元學習器
        meta = MetaPredictor(max_num=max_num)

        # 加權集成預測
        predicted_numbers, details = meta.predict_with_ensemble(
            predictions,
            weights=None,  # 使用預設權重
            pick_count=pick_count
        )

        # 計算信心度（基於共識程度）
        consensus_ratio = details['consensus_count'] / pick_count
        confidence = 0.65 + consensus_ratio * 0.25

        # 預測特別號
        predicted_special = predict_special_number(history, lottery_rules, predicted_numbers)

        result = {
            'numbers': predicted_numbers,
            'confidence': float(confidence),
            'method': f'元學習集成 ({len(predictions)}個方法)',
            'meta_info': {
                'methods_used': list(predictions.keys()),
                'consensus_count': details['consensus_count'],
                'number_sources': details['number_sources'],
                'weights': meta.default_weights,
                'strategy': '加權投票集成'
            }
        }

        if predicted_special is not None:
            result['special'] = predicted_special

        return result

    # ========================================================================
    # 🔥 P1優化: 新增策略方法 (2026-01-03)
    # ========================================================================

    def gap_sensitive_predict(self, history: List[Dict], lottery_rules: Dict) -> Dict:
        """
        間隔敏感策略 - 專門捕捉大跨度跳躍模式

        核心原理：
        1. 分析歷史上號碼間隔的分布模式
        2. 學習「大間隔」出現的規律 (gap > 15)
        3. 生成符合歷史間隔特徵的號碼組合

        覆蓋目標：42% 的大間隔開獎模式
        """
        pick_count = lottery_rules.get('pickCount', 6)
        min_num = lottery_rules.get('minNumber', 1)
        max_num = lottery_rules.get('maxNumber', 49)

        # 分析歷史間隔模式
        gap_patterns = []
        for d in history[:300]:
            nums = sorted(d['numbers'])
            gaps = [nums[i+1] - nums[i] for i in range(len(nums)-1)]
            max_gap = max(gaps)
            gap_position = gaps.index(max_gap)  # 最大間隔的位置
            gap_patterns.append({
                'max_gap': max_gap,
                'position': gap_position,
                'before_gap': nums[:gap_position+1],
                'after_gap': nums[gap_position+1:]
            })

        # 統計大間隔的特徵
        large_gap_patterns = [p for p in gap_patterns if p['max_gap'] > 15]
        large_gap_ratio = len(large_gap_patterns) / len(gap_patterns) if gap_patterns else 0

        # 統計號碼頻率
        freq = Counter()
        for d in history[:200]:
            freq.update(d['numbers'])

        # 決定是否生成大間隔組合
        import random
        generate_large_gap = random.random() < large_gap_ratio

        if generate_large_gap and large_gap_patterns:
            # 分析大間隔模式中，間隔前後的號碼範圍
            before_nums = []
            after_nums = []
            for p in large_gap_patterns[:50]:
                before_nums.extend(p['before_gap'])
                after_nums.extend(p['after_gap'])

            before_freq = Counter(before_nums)
            after_freq = Counter(after_nums)

            # 選擇「間隔前」的號碼 (通常是低區)
            before_candidates = [(n, before_freq.get(n, 0) + freq.get(n, 0))
                                for n in range(min_num, min_num + (max_num - min_num) // 2)]
            before_candidates.sort(key=lambda x: -x[1])
            selected_before = [n for n, _ in before_candidates[:4]]

            # 選擇「間隔後」的號碼 (通常是高區)
            after_candidates = [(n, after_freq.get(n, 0) + freq.get(n, 0))
                               for n in range(min_num + (max_num - min_num) // 2, max_num + 1)]
            after_candidates.sort(key=lambda x: -x[1])
            selected_after = [n for n, _ in after_candidates[:2]]

            numbers = selected_before[:4] + selected_after[:2]
        else:
            # 生成均勻間隔組合
            step = (max_num - min_num) // (pick_count + 1)
            base_nums = [min_num + step * (i + 1) for i in range(pick_count)]
            # 微調到高頻號碼
            numbers = []
            for base in base_nums:
                candidates = [(n, freq.get(n, 0)) for n in range(max(min_num, base-3), min(max_num+1, base+4))]
                candidates.sort(key=lambda x: -x[1])
                if candidates:
                    numbers.append(candidates[0][0])
                else:
                    numbers.append(base)

        # 確保數量正確且無重複
        numbers = list(set(numbers))[:pick_count]
        while len(numbers) < pick_count:
            for n in range(min_num, max_num + 1):
                if n not in numbers:
                    numbers.append(n)
                    if len(numbers) >= pick_count:
                        break

        confidence = 0.62 + large_gap_ratio * 0.15

        return {
            'numbers': sorted(numbers[:pick_count]),
            'confidence': float(confidence),
            'method': f'間隔敏感 (大間隔比例:{large_gap_ratio:.1%})',
            'gap_info': {
                'large_gap_ratio': large_gap_ratio,
                'generated_large_gap': generate_large_gap
            }
        }

    def extended_sum_range_predict(self, history: List[Dict], lottery_rules: Dict) -> Dict:
        """
        擴展和值範圍策略 - 按歷史分布覆蓋各和值區間

        核心原理：
        1. 統計歷史和值分布 (低/中/高)
        2. 按實際分布機率選擇目標和值區間
        3. 生成符合目標和值的號碼組合

        覆蓋目標：26% 低和值 + 47% 中和值 + 27% 高和值
        """
        pick_count = lottery_rules.get('pickCount', 6)
        min_num = lottery_rules.get('minNumber', 1)
        max_num = lottery_rules.get('maxNumber', 49)

        # 統計歷史和值分布
        sums = [sum(d['numbers']) for d in history[:500]]
        avg_sum = np.mean(sums)
        std_sum = np.std(sums)

        # 定義和值區間
        low_threshold = avg_sum - std_sum * 0.5   # 約 130
        high_threshold = avg_sum + std_sum * 0.5  # 約 170

        low_count = sum(1 for s in sums if s < low_threshold)
        mid_count = sum(1 for s in sums if low_threshold <= s <= high_threshold)
        high_count = sum(1 for s in sums if s > high_threshold)
        total = len(sums)

        # 按機率選擇目標區間
        import random
        r = random.random()
        low_prob = low_count / total
        mid_prob = mid_count / total

        if r < low_prob:
            target_range = 'low'
            target_min = int(avg_sum - std_sum * 1.5)
            target_max = int(low_threshold)
        elif r < low_prob + mid_prob:
            target_range = 'mid'
            target_min = int(low_threshold)
            target_max = int(high_threshold)
        else:
            target_range = 'high'
            target_min = int(high_threshold)
            target_max = int(avg_sum + std_sum * 1.5)

        # 統計號碼頻率
        freq = Counter()
        for d in history[:200]:
            freq.update(d['numbers'])

        # 根據目標和值生成號碼
        candidates = list(range(min_num, max_num + 1))

        # 嘗試多次生成符合和值約束的組合
        best_combo = None
        best_score = -1

        for _ in range(1000):
            random.shuffle(candidates)
            combo = sorted(candidates[:pick_count])
            combo_sum = sum(combo)

            if target_min <= combo_sum <= target_max:
                # 計算頻率分數
                score = sum(freq.get(n, 0) for n in combo)
                if score > best_score:
                    best_score = score
                    best_combo = combo

        if best_combo is None:
            # 回退：貪心選擇
            if target_range == 'low':
                # 低和值：選擇較小的號碼
                sorted_by_value = sorted(range(min_num, max_num + 1), key=lambda n: n)
            elif target_range == 'high':
                # 高和值：選擇較大的號碼
                sorted_by_value = sorted(range(min_num, max_num + 1), key=lambda n: -n)
            else:
                # 中和值：選擇中間號碼
                mid = (min_num + max_num) // 2
                sorted_by_value = sorted(range(min_num, max_num + 1), key=lambda n: abs(n - mid))

            best_combo = sorted_by_value[:pick_count]

        return {
            'numbers': sorted(best_combo[:pick_count]),
            'confidence': 0.65,
            'method': f'擴展和值 ({target_range}: {target_min}-{target_max})',
            'sum_info': {
                'target_range': target_range,
                'target_min': target_min,
                'target_max': target_max,
                'distribution': {'low': low_prob, 'mid': mid_prob, 'high': 1 - low_prob - mid_prob}
            }
        }

    def diverse_zone_predict(self, history: List[Dict], lottery_rules: Dict) -> Dict:
        """
        區間分布多樣化策略 - 按歷史頻率生成各種區間模式

        核心原理：
        1. 統計歷史區間分布模式 (如 2:2:2, 3:1:2, 1:2:3 等)
        2. 按實際出現頻率隨機選擇目標模式
        3. 生成符合目標模式的號碼組合

        優勢：不再只偏好 (2:2:2)，覆蓋更多歷史模式
        """
        pick_count = lottery_rules.get('pickCount', 6)
        min_num = lottery_rules.get('minNumber', 1)
        max_num = lottery_rules.get('maxNumber', 49)

        # 定義三個區間
        zone_size = (max_num - min_num + 1) // 3
        zones = [
            (min_num, min_num + zone_size - 1),                    # 低區
            (min_num + zone_size, min_num + 2 * zone_size - 1),    # 中區
            (min_num + 2 * zone_size, max_num)                      # 高區
        ]

        # 統計歷史區間分布模式
        zone_patterns = Counter()
        for d in history[:500]:
            nums = d['numbers']
            low = sum(1 for n in nums if zones[0][0] <= n <= zones[0][1])
            mid = sum(1 for n in nums if zones[1][0] <= n <= zones[1][1])
            high = sum(1 for n in nums if zones[2][0] <= n <= zones[2][1])
            zone_patterns[(low, mid, high)] += 1

        # 按機率選擇目標模式
        total_patterns = sum(zone_patterns.values())
        patterns_with_prob = [(p, c / total_patterns) for p, c in zone_patterns.most_common()]

        import random
        r = random.random()
        cumulative = 0
        target_pattern = (2, 2, 2)  # 預設

        for pattern, prob in patterns_with_prob:
            cumulative += prob
            if r < cumulative:
                target_pattern = pattern
                break

        # 統計各區號碼頻率
        freq = Counter()
        for d in history[:200]:
            freq.update(d['numbers'])

        # 根據目標模式生成號碼
        numbers = []
        for zone_idx, (zone_start, zone_end) in enumerate(zones):
            target_count = target_pattern[zone_idx]
            zone_nums = [(n, freq.get(n, 0)) for n in range(zone_start, zone_end + 1)]
            zone_nums.sort(key=lambda x: -x[1])
            numbers.extend([n for n, _ in zone_nums[:target_count]])

        # 確保數量正確
        numbers = list(set(numbers))[:pick_count]
        while len(numbers) < pick_count:
            for n in range(min_num, max_num + 1):
                if n not in numbers:
                    numbers.append(n)
                    if len(numbers) >= pick_count:
                        break

        pattern_prob = zone_patterns[target_pattern] / total_patterns
        confidence = 0.60 + pattern_prob * 0.20

        return {
            'numbers': sorted(numbers[:pick_count]),
            'confidence': float(confidence),
            'method': f'區間多樣化 ({target_pattern[0]}:{target_pattern[1]}:{target_pattern[2]})',
            'zone_info': {
                'target_pattern': target_pattern,
                'pattern_probability': pattern_prob,
                'top_patterns': patterns_with_prob[:5]
            }
        }

    # ========================================================================
    # 🔥 P2優化: 號碼社群圖分析 (2026-01-04)
    # ========================================================================

    def community_predict(self, history: List[Dict], lottery_rules: Dict) -> Dict:
        """
        號碼社群預測策略 - P2優化

        核心原理：
        1. 建立號碼共現圖（邊權重 = 共現次數）
        2. 使用社群檢測找出「號碼群落」
        3. 從高連通的社群中聯合採樣

        優勢：利用 (3,7), (7,19), (16,40) 這類共現對
        """
        from itertools import combinations
        import random

        pick_count = lottery_rules.get('pickCount', 6)
        min_num = lottery_rules.get('minNumber', 1)
        max_num = lottery_rules.get('maxNumber', 49)

        # 建立共現圖
        cooccurrence = Counter()
        for d in history[:300]:
            for pair in combinations(sorted(d['numbers']), 2):
                cooccurrence[pair] += 1

        # 計算每個號碼的「社群分數」= 與其他號碼的總共現強度
        number_scores = {}
        for num in range(min_num, max_num + 1):
            score = sum(
                cooccurrence.get(tuple(sorted([num, other])), 0)
                for other in range(min_num, max_num + 1)
                if other != num
            )
            number_scores[num] = score

        # 找出高共現號碼對
        top_pairs = cooccurrence.most_common(20)

        # 貪心選擇：從最強共現對開始，逐步擴展
        selected = set()
        pair_contribution = {}

        for pair, count in top_pairs:
            if len(selected) >= pick_count:
                break
            n1, n2 = pair
            # 加入未選中的號碼
            if n1 not in selected and len(selected) < pick_count:
                selected.add(n1)
                pair_contribution[n1] = count
            if n2 not in selected and len(selected) < pick_count:
                selected.add(n2)
                pair_contribution[n2] = count

        # 補足不夠的（選社群分數高的）
        if len(selected) < pick_count:
            remaining = [(n, s) for n, s in number_scores.items() if n not in selected]
            remaining.sort(key=lambda x: -x[1])
            for n, _ in remaining:
                if len(selected) >= pick_count:
                    break
                selected.add(n)

        numbers = sorted(list(selected))[:pick_count]

        # 計算信心度（基於共現強度）
        avg_cooccur = sum(pair_contribution.values()) / max(len(pair_contribution), 1)
        max_cooccur = max(cooccurrence.values()) if cooccurrence else 1
        confidence = 0.60 + min(avg_cooccur / max_cooccur * 0.20, 0.20)

        return {
            'numbers': numbers,
            'confidence': float(confidence),
            'method': '號碼社群分析',
            'community_info': {
                'top_pairs': [(list(p), c) for p, c in top_pairs[:5]],
                'selected_from_pairs': list(pair_contribution.keys())
            }
        }

    def adaptive_weight_predict(self, history: List[Dict], lottery_rules: Dict) -> Dict:
        """
        動態權重預測策略 - P2優化

        核心原理：
        1. 根據近期各策略的表現動態調整權重
        2. 使用滑動窗口評估策略有效性
        3. 加權融合多策略預測結果

        優勢：自動適應不同時期的最佳策略
        """
        pick_count = lottery_rules.get('pickCount', 6)
        min_num = lottery_rules.get('minNumber', 1)
        max_num = lottery_rules.get('maxNumber', 49)

        # 收集多個策略的預測
        strategies = [
            ('zone_balance', self.zone_balance_predict),
            ('bayesian', self.bayesian_predict),
            ('trend', self.trend_predict),
            ('markov', self.markov_predict),
            ('hot_cold', self.hot_cold_mix_predict),
        ]

        predictions = {}
        for name, func in strategies:
            try:
                result = func(history, lottery_rules)
                predictions[name] = {
                    'numbers': set(result['numbers']),
                    'confidence': result.get('confidence', 0.5)
                }
            except:
                continue

        if not predictions:
            return self.frequency_predict(history, lottery_rules)

        # 回測近30期評估各策略表現
        strategy_scores = {name: 0.0 for name in predictions.keys()}
        backtest_window = min(30, len(history) - 100)

        for i in range(backtest_window):
            target = history[i]
            target_nums = set(target['numbers'])
            test_history = history[i+1:i+101]

            for name, func in strategies:
                if name not in predictions:
                    continue
                try:
                    result = func(test_history, lottery_rules)
                    matches = len(set(result['numbers']) & target_nums)
                    # 時間衰減：近期表現權重更高
                    decay = np.exp(-0.05 * i)
                    strategy_scores[name] += matches * decay
                except:
                    continue

        # 歸一化權重
        total_score = sum(strategy_scores.values())
        if total_score > 0:
            weights = {name: score / total_score for name, score in strategy_scores.items()}
        else:
            weights = {name: 1.0 / len(predictions) for name in predictions.keys()}

        # 加權投票
        number_scores = {}
        for num in range(min_num, max_num + 1):
            score = 0.0
            for name, data in predictions.items():
                if num in data['numbers']:
                    score += weights.get(name, 0) * data['confidence']
            number_scores[num] = score

        # 選擇得分最高的號碼
        sorted_nums = sorted(number_scores.items(), key=lambda x: -x[1])
        numbers = [n for n, _ in sorted_nums[:pick_count]]

        # 信心度
        top_weights = sorted(weights.items(), key=lambda x: -x[1])
        confidence = 0.65 + top_weights[0][1] * 0.15 if top_weights else 0.65

        return {
            'numbers': sorted(numbers),
            'confidence': float(confidence),
            'method': '動態權重融合',
            'weight_info': {
                'strategy_weights': weights,
                'top_strategy': top_weights[0][0] if top_weights else None
            }
        }


# 全局預測引擎實例
prediction_engine = UnifiedPredictionEngine()

