#!/usr/bin/env python3
"""
ARIMA 預測模型
========================
基於 statsmodels 的 ARIMA 實作，針對開獎號碼數值進行時間序列預測。
參考 GitHub 專案: michaelkupfer97/Lotto-prediction (p=5, d=1, q=0)
"""
import numpy as np
import pandas as pd
import logging
from typing import List, Dict, Optional
from statsmodels.tsa.arima.model import ARIMA

logger = logging.getLogger(__name__)

class ARIMALotteryPredictor:
    """
    ARIMA 樂透預測器
    """

    def __init__(self, p=1, d=0, q=0):
        """
        初始化 ARIMA 參數
        """
        self.order = (p, d, q)

    def predict(self, history: List[Dict], rules: Dict) -> Dict:
        """
        執行 ARIMA 預測
        
        Args:
            history: 歷史數據 [{'numbers': [1,2,3,4,5,6], 'special': 7}, ...]
            rules: 彩票規則 {'pickCount': 6, 'maxNumber': 38, ...}
            
        Returns:
            {'numbers': [...], 'confidence': float, 'method': 'arima'}
        """
        if not history or len(history) < 10:
            return {'numbers': [], 'confidence': 0.0, 'method': 'arima_error'}

        pick_count = rules.get('pickCount', 6)
        max_num = rules.get('maxNumber', 38)
        min_num = rules.get('minNumber', 1)

        # 1. 準備數據框架
        # 假設 history 是按時間順序排列 (Old -> New)
        # 提取主號並按位置排列
        main_numbers = [draw['numbers'] for draw in history]
        df = pd.DataFrame(main_numbers)
        
        # 如果列數不對，補齊或裁切
        if df.shape[1] < pick_count:
            logger.warning(f"ARIMA: Data columns ({df.shape[1]}) < pickCount ({pick_count})")
            # 這裡簡單處理，只預測已有的列
        
        arima_results = []
        
        # 2. 為每個位置建立 ARIMA 模型
        for col in range(min(df.shape[1], pick_count)):
            series = df.iloc[:, col].astype(float)
            try:
                # 建立並擬合模型
                model = ARIMA(series, order=self.order)
                model_fit = model.fit()
                
                # 預測下一個值
                forecast = model_fit.forecast(steps=1)
                val = int(round(forecast.iloc[0]))
                
                # 限制範圍
                val = max(min_num, min(max_num, val))
                arima_results.append(val)
            except Exception as e:
                logger.error(f"ARIMA error at position {col}: {e}")
                #  fallback: 使用該位置的均值或最後一個值
                arima_results.append(int(round(series.iloc[-1])))

        # 3. 處理重複號碼 (因為各位置是獨立預測的)
        final_numbers = []
        for n in arima_results:
            if n not in final_numbers:
                final_numbers.append(n)
            else:
                # 如果重複，尋找最近的可用號碼
                next_val = n
                while next_val in final_numbers or next_val > max_num:
                    next_val += 1
                    if next_val > max_num:
                        next_val = min_num
                final_numbers.append(next_val)
        
        # 4. 預測特別號 (如果有)
        special_val = None
        if rules.get('hasSpecialNumber', False):
            specials = [draw.get('special') for draw in history if draw.get('special') is not None]
            if specials:
                try:
                    s_series = pd.Series(specials).astype(float)
                    s_model = ARIMA(s_series, order=self.order)
                    s_model_fit = s_model.fit()
                    s_forecast = s_model_fit.forecast(steps=1)
                    special_val = int(round(s_forecast.iloc[0]))
                    
                    s_max = rules.get('specialMaxNumber', max_num)
                    s_min = rules.get('specialMinNumber', min_num)
                    special_val = max(s_min, min(s_max, special_val))
                except:
                    special_val = specials[-1]

        result = {
            'numbers': sorted(final_numbers[:pick_count]),
            'confidence': 0.6,  # ARIMA 在樂透中信心度通常給予中等
            'method': f'ARIMA ({self.order[0]},{self.order[1]},{self.order[2]})'
        }
        
        if special_val is not None:
            result['special'] = special_val
            
        return result

def arima_predict(history, rules, **kwargs):
    """供集成系統調用的包裝函數"""
    p = kwargs.get('p', 1)
    d = kwargs.get('d', 0)
    q = kwargs.get('q', 0)
    predictor = ARIMALotteryPredictor(p=p, d=d, q=q)
    return predictor.predict(history, rules)

if __name__ == "__main__":
    # 簡單測試
    test_history = [
        {'numbers': [1, 5, 10, 15, 20, 25], 'special': 1},
        {'numbers': [2, 6, 11, 16, 21, 26], 'special': 2},
        {'numbers': [3, 7, 12, 17, 22, 27], 'special': 3},
        {'numbers': [4, 8, 13, 18, 23, 28], 'special': 4},
        {'numbers': [5, 9, 14, 19, 24, 29], 'special': 5},
        {'numbers': [6, 10, 15, 20, 25, 30], 'special': 6},
        {'numbers': [7, 11, 16, 21, 26, 31], 'special': 7},
        {'numbers': [8, 12, 17, 22, 27, 32], 'special': 8},
        {'numbers': [9, 13, 18, 23, 28, 33], 'special': 1},
        {'numbers': [10, 14, 19, 24, 29, 34], 'special': 2},
        {'numbers': [11, 15, 20, 25, 30, 35], 'special': 3},
        {'numbers': [12, 16, 21, 26, 31, 36], 'special': 4},
    ]
    test_rules = {'pickCount': 6, 'maxNumber': 38, 'minNumber': 1, 'hasSpecialNumber': True, 'specialMaxNumber': 8}
    
    res = arima_predict(test_history, test_rules)
    print(f"ARIMA Prediction: {res}")
