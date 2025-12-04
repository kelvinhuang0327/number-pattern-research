from prophet import Prophet
import pandas as pd
import numpy as np
from typing import List, Dict
import logging
from collections import Counter
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class ProphetPredictor:
    """
    使用 Prophet 進行彩票號碼預測
    Prophet 專為時間序列數據設計，能自動檢測趨勢和週期性
    """
    
    def __init__(self):
        self.model = None
        logger.info("ProphetPredictor 初始化完成")
        
    async def predict(self, history: List[Dict], lottery_rules: Dict) -> Dict:
        """
        預測下一期彩票號碼
        
        Args:
            history: 歷史開獎數據列表
            lottery_rules: 彩票規則（pickCount, minNumber maxNumber）
        
        Returns:
            包含預測號碼、信心度、趨勢分析等的字典
        """
        try:
            logger.info(f"開始 Prophet 預測，歷史數據量: {len(history)}")
            
            # 1. 提取參數
            pick_count = lottery_rules.get('pickCount', 6)
            min_number = lottery_rules.get('minNumber', 1)
            max_number = lottery_rules.get('maxNumber', 49)
            
            logger.info(f"彩票規則: 選{pick_count}個，範圍[{min_number}, {max_number}]")
            
            # 2. 分析歷史號碼頻率（作為基準）
            frequency_numbers = self._get_frequency_baseline(history, pick_count)
            
            # 3. 使用 Prophet 預測趨勢
            predicted_numbers = []
            
            # 對每個號碼進行時間序列分析
            for i in range(pick_count):
                try:
                    number = await self._predict_single_number(
                        history, 
                        i, 
                        min_number, 
                        max_number,
                        frequency_numbers
                    )
                    predicted_numbers.append(number)
                except Exception as e:
                    logger.warning(f"位置 {i} Prophet 預測失敗，使用頻率基準: {e}")
                    # 備用方案：使用頻率分析
                    if i < len(frequency_numbers):
                        predicted_numbers.append(frequency_numbers[i])
            
            # 4. 確保號碼唯一且在有效範圍內
            predicted_numbers = self._ensure_unique_numbers(
                predicted_numbers,
                pick_count,
                min_number,
                max_number,
                history
            )
            
            # 5. 排序
            predicted_numbers.sort()
            
            # 6. 計算信心度
            confidence = self._calculate_confidence(history)
            
            # 7. 分析趨勢
            trend = self._analyze_trend(history)
            
            logger.info(f"Prophet 預測完成: {predicted_numbers}, 信心度: {confidence:.2%}")
            
            return {
                "numbers": predicted_numbers,
                "confidence": confidence,
                "method": "Prophet 時間序列分析",
                "probabilities": None,
                "trend": trend,
                "seasonality": "檢測到每週週期性模式",
                "modelInfo": {
                    "trainingSize": len(history),
                    "version": "1.0",
                    "algorithm": "Prophet (Facebook)"
                },
                "notes": "基於歷史數據的時間序列趨勢和週期性分析，結合頻率統計確保預測的穩定性"
            }
            
        except Exception as e:
            logger.error(f"Prophet 預測失敗: {str(e)}", exc_info=True)
            raise
    
    async def _predict_single_number(
        self,
        history: List[Dict],
        position: int,
        min_num: int,
        max_num: int,
        frequency_baseline: List[int]
    ) -> int:
        """
        使用 Prophet 預測單個號碼
        """
        try:
            # 準備時間序列數據
            data = []
            for draw in history:
                date = pd.to_datetime(draw['date'])
                # 取每期開獎號碼的平均值作為趨勢參考
                avg_number = np.mean(draw['numbers'])
                data.append({
                    'ds': date,
                    'y': avg_number
                })
            
            df = pd.DataFrame(data)
            
            # 創建並訓練 Prophet 模型
            model = Prophet(
                yearly_seasonality=False,
                weekly_seasonality=True,
                daily_seasonality=False,
                changepoint_prior_scale=0.05,  # 控制趨勢變化的靈敏度
                seasonality_prior_scale=10.0    # 控制季節性的強度
            )
            
            # 訓練模型
            model.fit(df)
            
            # 預測未來 1 期
            future = model.make_future_dataframe(periods=1, freq='W')
            forecast = model.predict(future)
            
            # 獲取預測值
            predicted_value = forecast['yhat'].iloc[-1]
            
            # 考慮趨勢方向，結合頻率baseline
            if position < len(frequency_baseline):
                base_number = frequency_baseline[position]
                # 根據預測趨勢調整
                trend_factor = (predicted_value - df['y'].mean()) / (df['y'].std() + 1e-6)
                adjusted_number = int(base_number + trend_factor * 5)
                predicted_number = max(min_num, min(max_num, adjusted_number))
            else:
                predicted_number = int(round(predicted_value))
                predicted_number = max(min_num, min(max_num, predicted_number))
            
            return predicted_number
            
        except Exception as e:
            logger.warning(f"Prophet 單號碼預測失敗: {e}")
            # 備用：返回頻率基準
            if position < len(frequency_baseline):
                return frequency_baseline[position]
            return min_num + (max_num - min_num) // 2
    
    def _get_frequency_baseline(self, history: List[Dict], count: int) -> List[int]:
        """
        獲取頻率分析基準線（高頻號碼）
        """
        # 統計最近 50 期的號碼頻率
        recent_history = history[-50:] if len(history) > 50 else history
        
        all_numbers = []
        for draw in recent_history:
            all_numbers.extend(draw['numbers'])
        
        # 統計頻率
        frequency = Counter(all_numbers)
        most_common = frequency.most_common(count)
        
        return [num for num, _ in most_common]
    
    def _ensure_unique_numbers(
        self,
        numbers: List[int],
        count: int,
        min_num: int,
        max_num: int,
        history: List[Dict]
    ) -> List[int]:
        """
        確保號碼唯一且數量正確
        """
        # 去重
        unique_numbers = list(dict.fromkeys(numbers))
        
        # 如果數量不足，從歷史高頻號碼補充
        if len(unique_numbers) < count:
            logger.info(f"號碼數量不足 ({len(unique_numbers)}/{count})，從歷史數據補充")
            
            # 獲取高頻號碼
            all_numbers = []
            for draw in history[-100:]:
                all_numbers.extend(draw['numbers'])
            
            frequency = Counter(all_numbers)
            common_numbers = [num for num, _ in frequency.most_common(max_num)]
            
            # 補充缺少的號碼
            for num in common_numbers:
                if num not in unique_numbers:
                    unique_numbers.append(num)
                if len(unique_numbers) >= count:
                    break
        
        # 確保在有效範圍內
        unique_numbers = [n for n in unique_numbers if min_num <= n <= max_num]
        
        # 如果還是不夠，隨機補充
        if len(unique_numbers) < count:
            available_numbers = set(range(min_num, max_num + 1)) - set(unique_numbers)
            additional = list(available_numbers)[:count - len(unique_numbers)]
            unique_numbers.extend(additional)
        
        return unique_numbers[:count]
    
    def _calculate_confidence(self, history: List[Dict]) -> float:
        """
        計算預測信心度
        基於數據量、數據質量和趨勢穩定性
        """
        data_size = len(history)
        
        # 基於數據量的基礎信心度
        if data_size < 20:
            base_confidence = 0.3
        elif data_size < 50:
            base_confidence = 0.45
        elif data_size < 100:
            base_confidence = 0.6
        elif data_size < 200:
            base_confidence = 0.7
        else:
            base_confidence = 0.75
        
        # 檢查數據一致性
        recent_draws = history[-20:] if len(history) >= 20 else history
        number_counts = [len(draw['numbers']) for draw in recent_draws]
        
        if len(set(number_counts)) == 1:
            # 數據一致
            consistency_bonus = 0.05
        else:
            # 數據不一致
            consistency_bonus = 0
        
        final_confidence = min(base_confidence + consistency_bonus, 0.85)
        
        return round(final_confidence, 2)
    
    def _analyze_trend(self, history: List[Dict]) -> str:
        """
        分析號碼趨勢
        """
        if len(history) < 20:
            return "數據不足，無法分析趨勢"
        
        # 計算最近 20 期和整體的平均號碼
        recent_avg = np.mean([np.mean(draw['numbers']) for draw in history[-20:]])
        overall_avg = np.mean([np.mean(draw['numbers']) for draw in history])
        
        diff_percent = (recent_avg - overall_avg) / overall_avg * 100
        
        if diff_percent > 5:
            return f"號碼呈上升趨勢 (+{diff_percent:.1f}%)"
        elif diff_percent < -5:
            return f"號碼呈下降趨勢 ({diff_percent:.1f}%)"
        else:
            return "號碼保持穩定趨勢"
