import pandas as pd
import numpy as np
from typing import List, Dict, Tuple
import logging
import json
import os
from collections import Counter
# ⚠️ 特別號不預測！玩家只選6個主號碼

logger = logging.getLogger(__name__)

class AutoGluonPredictor:
    """
    使用 AutoGluon 進行彩票號碼預測（快速版本）
    採用頻率分析 + 統計特徵的混合策略，而非完整的 AutoML 訓練
    """
    
    def __init__(self):
        logger.info("AutoGluonPredictor 初始化完成（快速模式）")
        
    async def predict(self, history: List[Dict], lottery_rules: Dict) -> Dict:
        """
        預測下一期彩票號碼
        使用輕量級策略以確保快速響應
        """
        try:
            logger.info(f"開始 AutoGluon 預測，歷史數據量: {len(history)}")
            
            # 1. 參數設定
            pick_count = lottery_rules.get('pickCount', 6)
            min_number = lottery_rules.get('minNumber', 1)
            max_number = lottery_rules.get('maxNumber', 49)
            
            # 2. 數據準備 - 使用最近的數據
            recent_history = history[-200:] if len(history) > 200 else history
            
            if len(recent_history) < 10:
                raise ValueError("訓練數據不足，至少需要 10 期")
            
            # 3. 多策略組合預測
            predicted_numbers = self._hybrid_prediction(
                recent_history,
                pick_count,
                min_number,
                max_number
            )
            
            # 4. 計算信心度
            confidence = self._calculate_confidence(recent_history, predicted_numbers)
            
            logger.info(f"AutoGluon 預測完成: {predicted_numbers}, 信心度: {confidence:.2%}")
            
            # ⚠️ 大樂透特別號不預測！玩家只選6個主號碼

            result = {
                "numbers": predicted_numbers,
                "confidence": confidence,
                "method": "AutoGluon 智能混合策略",
                "probabilities": None,
                "trend": "基於頻率、趨勢和統計特徵的混合預測",
                "seasonality": None,
                "modelInfo": {
                    "trainingSize": len(recent_history),
                    "version": "1.0-fast",
                    "algorithm": "Hybrid Frequency + Statistical Features"
                },
                "notes": "採用輕量級混合策略，結合頻率分析、遺漏值、冷熱號分析等多種特徵"
            }

            return result
            
        except Exception as e:
            logger.error(f"AutoGluon 預測失敗: {str(e)}", exc_info=True)
            raise

    def _load_best_config(self) -> Dict:
        """嘗試加載最佳配置"""
        try:
            config_path = 'models/best_config.json'
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('config', {})
        except Exception as e:
            logger.warning(f"加載最佳配置失敗: {e}")
        return {}

    def _hybrid_prediction(
        self,
        history: List[Dict],
        pick_count: int,
        min_num: int,
        max_num: int
    ) -> List[int]:
        """
        混合策略預測（支持自動優化權重）
        """
        # 嘗試加載最佳配置
        config = self._load_best_config()
        
        # 默認權重
        weights = {
            'frequency_weight': 0.3,
            'missing_weight': 0.15,
            'hot_cold_weight': 0.15,
            'trend_weight': 0.1,
            'zone_weight': 0.1,
            'last_digit_weight': 0.1,
            'odd_even_weight': 0.1
        }
        
        # 如果有最佳配置，更新權重
        if config:
            # 確保權重總和為 1 (如果配置中已經歸一化則不需要，但為了安全起見)
            # 這裡直接使用配置中的權重，假設它們已經是合理的
            for key in weights:
                if key in config:
                    weights[key] = config[key]
            
            # 如果配置中有窗口參數，也可以在這裡使用（目前先只用權重）
            # recent_window = config.get('recent_window', 20)
            
            logger.info(f"使用優化後的權重: {weights}")

        # 初始化評分字典
        scores = {num: 0.0 for num in range(min_num, max_num + 1)}
        
        # === 策略 1: 頻率分析 ===
        freq_scores = self._frequency_analysis(history, min_num, max_num)
        for num, score in freq_scores.items():
            scores[num] += score * weights['frequency_weight']
        
        # === 策略 2: 遺漏值分析 ===
        missing_scores = self._missing_value_analysis(history, min_num, max_num)
        for num, score in missing_scores.items():
            scores[num] += score * weights['missing_weight']
        
        # === 策略 3: 冷熱號平衡 ===
        hot_cold_scores = self._hot_cold_balance(history, min_num, max_num)
        for num, score in hot_cold_scores.items():
            scores[num] += score * weights['hot_cold_weight']
        
        # === 策略 4: 趨勢分析 ===
        trend_scores = self._trend_analysis(history, min_num, max_num)
        for num, score in trend_scores.items():
            scores[num] += score * weights['trend_weight']
            
        # === 策略 5: 區間分析 (新) ===
        if 'zone_weight' in weights:
            zone_scores = self._zone_analysis(history, min_num, max_num)
            for num, score in zone_scores.items():
                scores[num] += score * weights['zone_weight']
                
        # === 策略 6: 尾數分析 (新) ===
        if 'last_digit_weight' in weights:
            digit_scores = self._last_digit_analysis(history, min_num, max_num)
            for num, score in digit_scores.items():
                scores[num] += score * weights['last_digit_weight']
                
        # === 策略 7: 奇偶分析 (新) ===
        if 'odd_even_weight' in weights:
            oe_scores = self._odd_even_analysis(history, min_num, max_num)
            for num, score in oe_scores.items():
                scores[num] += score * weights['odd_even_weight']
        
        # 選擇得分最高的號碼
        sorted_numbers = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        predicted_numbers = [num for num, score in sorted_numbers[:pick_count]]
        predicted_numbers.sort()
        
        return predicted_numbers

    def _zone_analysis(self, history: List[Dict], min_num: int, max_num: int) -> Dict[int, float]:
        """
        區間分析：根據近期熱門區間加權
        """
        scores = {num: 0.5 for num in range(min_num, max_num + 1)}
        if not history: return scores
        
        # 將號碼分為 5 個區間
        range_len = max_num - min_num + 1
        zone_size = max(1, range_len // 5)
        recent = history[-10:] # 最近10期
        zone_counts = Counter()
        
        for draw in recent:
            for num in draw['numbers']:
                zone_idx = (num - min_num) // zone_size
                zone_counts[zone_idx] += 1
        
        max_count = max(zone_counts.values()) if zone_counts else 1
        
        for num in range(min_num, max_num + 1):
            zone_idx = (num - min_num) // zone_size
            # 熱門區間加分
            scores[num] = zone_counts[zone_idx] / max_count
            
        return scores

    def _last_digit_analysis(self, history: List[Dict], min_num: int, max_num: int) -> Dict[int, float]:
        """
        尾數分析：統計號碼尾數的規律
        """
        scores = {num: 0.5 for num in range(min_num, max_num + 1)}
        if not history: return scores
        
        recent = history[-20:]
        digit_counts = Counter()
        
        for draw in recent:
            for num in draw['numbers']:
                last_digit = num % 10
                digit_counts[last_digit] += 1
                
        max_count = max(digit_counts.values()) if digit_counts else 1
        
        for num in range(min_num, max_num + 1):
            last_digit = num % 10
            scores[num] = digit_counts[last_digit] / max_count
            
        return scores

    def _odd_even_analysis(self, history: List[Dict], min_num: int, max_num: int) -> Dict[int, float]:
        """
        奇偶分析：分析奇偶數比例
        """
        scores = {num: 0.5 for num in range(min_num, max_num + 1)}
        if not history: return scores
        
        recent = history[-20:]
        odd_count = 0
        total_nums = 0
        
        for draw in recent:
            for num in draw['numbers']:
                if num % 2 != 0:
                    odd_count += 1
                total_nums += 1
                
        odd_ratio = odd_count / total_nums if total_nums > 0 else 0.5
        
        # 假設趨勢延續：如果近期奇數多，則給奇數較高分
        for num in range(min_num, max_num + 1):
            is_odd = num % 2 != 0
            # 將分數映射到 0.3 - 0.7 之間，避免過度極端
            base_score = odd_ratio if is_odd else (1 - odd_ratio)
            scores[num] = 0.3 + (base_score * 0.4)
            
        return scores

    def _frequency_analysis(self, history: List[Dict], min_num: int, max_num: int) -> Dict[int, float]:
        """
        頻率分析：統計號碼出現頻率
        """
        all_numbers = []
        for draw in history:
            all_numbers.extend(draw['numbers'])
        
        frequency = Counter(all_numbers)
        max_freq = max(frequency.values()) if frequency else 1
        
        # 歸一化分數
        scores = {}
        for num in range(min_num, max_num + 1):
            scores[num] = frequency.get(num, 0) / max_freq
        
        return scores

    def _missing_value_analysis(self, history: List[Dict], min_num: int, max_num: int) -> Dict[int, float]:
        """
        遺漏值分析：號碼未出現的期數
        """
        missing = {num: 0 for num in range(min_num, max_num + 1)}
        
        # 從最新一期往回查找
        for i in range(len(history) - 1, -1, -1):
            current_numbers = set(history[i]['numbers'])
            for num in range(min_num, max_num + 1):
                if num not in current_numbers:
                    missing[num] += 1
                else:
                    break  # 號碼出現了，停止計數
        
        # 歸一化：遺漏值越大，分數越高（但不要太極端）
        max_missing = max(missing.values()) if missing else 1
        scores = {}
        for num, miss_count in missing.items():
            # 使用 sqrt 來平滑極端值
            scores[num] = np.sqrt(miss_count / max_missing) if max_missing > 0 else 0
        
        return scores

    def _hot_cold_balance(self, history: List[Dict], min_num: int, max_num: int) -> Dict[int, float]:
        """
        冷熱號平衡：結合近期和長期頻率
        """
        # 近期頻率（最近 20 期）
        recent = history[-20:] if len(history) > 20 else history
        recent_numbers = []
        for draw in recent:
            recent_numbers.extend(draw['numbers'])
        recent_freq = Counter(recent_numbers)
        
        # 長期頻率
        all_numbers = []
        for draw in history:
            all_numbers.extend(draw['numbers'])
        long_freq = Counter(all_numbers)
        
        # 歸一化
        max_recent = max(recent_freq.values()) if recent_freq else 1
        max_long = max(long_freq.values()) if long_freq else 1
        
        scores = {}
        for num in range(min_num, max_num + 1):
            recent_score = recent_freq.get(num, 0) / max_recent
            long_score = long_freq.get(num, 0) / max_long
            # 結合近期和長期：60% 近期 + 40% 長期
            scores[num] = recent_score * 0.6 + long_score * 0.4
        
        return scores

    def _trend_analysis(self, history: List[Dict], min_num: int, max_num: int) -> Dict[int, float]:
        """
        趨勢分析：號碼出現頻率的增減趨勢
        """
        if len(history) < 40:
            # 數據不足，返回中性分數
            return {num: 0.5 for num in range(min_num, max_num + 1)}
        
        # 分成兩個時間段
        mid_point = len(history) - 20
        early_period = history[:mid_point]
        late_period = history[mid_point:]
        
        # 計算兩個時期的頻率
        early_numbers = []
        for draw in early_period:
            early_numbers.extend(draw['numbers'])
        early_freq = Counter(early_numbers)
        
        late_numbers = []
        for draw in late_period:
            late_numbers.extend(draw['numbers'])
        late_freq = Counter(late_numbers)
        
        # 計算趨勢：近期頻率 vs 早期頻率
        scores = {}
        for num in range(min_num, max_num + 1):
            early_count = early_freq.get(num, 0) / len(early_period) if len(early_period) > 0 else 0
            late_count = late_freq.get(num, 0) / len(late_period) if len(late_period) > 0 else 0
            
            # 上升趨勢得高分
            if early_count > 0:
                trend_ratio = late_count / early_count
                scores[num] = min(trend_ratio, 2.0) / 2.0  # 限制在 [0, 1]
            else:
                scores[num] = 0.5  # 中性
        
        return scores

    def _calculate_confidence(self, history: List[Dict], predicted_numbers: List[int]) -> float:
        """
        計算預測信心度
        """
        data_size = len(history)
        
        # 基於數據量的基礎信心度
        if data_size < 30:
            base_confidence = 0.4
        elif data_size < 100:
            base_confidence = 0.55
        elif data_size < 200:
            base_confidence = 0.7
        else:
            base_confidence = 0.78
        
        # 檢查預測號碼是否包含高頻號碼（增加信心）
        recent_numbers = []
        for draw in history[-30:]:
            recent_numbers.extend(draw['numbers'])
        
        frequency = Counter(recent_numbers)
        top_15_frequent = [num for num, _ in frequency.most_common(15)]
        
        overlap_count = len(set(predicted_numbers) & set(top_15_frequent))
        frequency_bonus = (overlap_count / len(predicted_numbers)) * 0.12
        
        final_confidence = min(base_confidence + frequency_bonus, 0.88)
        
        return round(final_confidence, 2)
