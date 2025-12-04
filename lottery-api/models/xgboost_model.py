import xgboost as xgb
import pandas as pd
import numpy as np
from typing import List, Dict, Tuple
import logging
from sklearn.multioutput import MultiOutputClassifier
from sklearn.preprocessing import MultiLabelBinarizer

logger = logging.getLogger(__name__)

class XGBoostPredictor:
    """
    使用 XGBoost 進行彩票號碼預測
    採用多標籤分類 (Multi-label Classification) 方法
    """
    
    def __init__(self):
        logger.info("XGBoostPredictor 初始化完成")
        
    async def predict(self, history: List[Dict], lottery_rules: Dict) -> Dict:
        """
        預測下一期彩票號碼
        """
        try:
            logger.info(f"開始 XGBoost 預測，歷史數據量: {len(history)}")
            
            # 1. 參數設定
            pick_count = lottery_rules.get('pickCount', 6)
            min_number = lottery_rules.get('minNumber', 1)
            max_number = lottery_rules.get('maxNumber', 49)
            
            # 2. 數據準備
            # 為了效能，只取最近 1000 期進行訓練
            train_history = history[-1000:] if len(history) > 1000 else history
            
            X, y, mlb = self._prepare_data(train_history, pick_count, min_number, max_number)
            
            if len(X) < 10:
                raise ValueError("訓練數據不足")
                
            # 3. 訓練模型
            # 使用 MultiOutputClassifier 配合 XGBClassifier
            # 這會為每個號碼訓練一個二元分類器
            clf = MultiOutputClassifier(xgb.XGBClassifier(
                n_estimators=50,      # 樹的數量 (降低以提升速度)
                max_depth=3,          # 樹的深度
                learning_rate=0.1,
                objective='binary:logistic',
                eval_metric='logloss',
                n_jobs=-1             # 使用所有 CPU 核心
            ))
            
            clf.fit(X, y)
            
            # 4. 預測下一期
            # 建構最後一期的特徵
            last_features = self._extract_features(train_history, len(train_history), pick_count)
            last_features = last_features.reshape(1, -1)
            
            # 預測機率
            # predict_proba 返回一個 list，每個元素是該標籤的 (n_samples, 2) 機率陣列
            probas_list = clf.predict_proba(last_features)
            
            # 整合所有號碼的機率
            number_probs = {}
            for i, prob_arr in enumerate(probas_list):
                # prob_arr[0][1] 是 "出現" (class 1) 的機率
                # mlb.classes_[i] 是對應的號碼
                number = mlb.classes_[i]
                probability = prob_arr[0][1]
                number_probs[number] = probability
            
            # 5. 選擇機率最高的號碼
            sorted_numbers = sorted(number_probs.items(), key=lambda x: x[1], reverse=True)
            top_numbers = [num for num, prob in sorted_numbers[:pick_count]]
            top_numbers.sort()
            
            # 6. 計算信心度 (取前 N 個號碼的平均機率)
            confidence = np.mean([prob for num, prob in sorted_numbers[:pick_count]])
            
            # 7. 生成趨勢描述
            trend = "XGBoost 模型偵測到高機率模式"
            
            logger.info(f"XGBoost 預測完成: {top_numbers}, 信心度: {confidence:.2%}")
            
            return {
                "numbers": top_numbers,
                "confidence": float(confidence),
                "method": "XGBoost 梯度提升決策樹",
                "probabilities": [float(prob) for num, prob in sorted_numbers[:pick_count]],
                "trend": trend,
                "seasonality": None,
                "modelInfo": {
                    "trainingSize": len(train_history),
                    "version": "1.0",
                    "algorithm": "XGBoost Multi-label"
                },
                "notes": "基於歷史開獎模式的機器學習預測，分析號碼間的關聯性"
            }
            
        except Exception as e:
            logger.error(f"XGBoost 預測失敗: {str(e)}", exc_info=True)
            raise

    def _prepare_data(self, history: List[Dict], pick_count: int, min_num: int, max_num: int):
        """
        準備訓練數據
        X: 過去 N 期的特徵
        y: 當期開出的號碼 (Multi-hot encoding)
        """
        X = []
        y_raw = []
        
        # 使用過去 5 期作為特徵視窗
        window_size = 5
        
        for i in range(window_size, len(history)):
            # 特徵: 過去 window_size 期的號碼
            features = self._extract_features(history, i, pick_count, window_size)
            X.append(features)
            
            # 目標: 當期號碼
            y_raw.append(history[i]['numbers'])
            
        # 轉換 y 為 Multi-hot 格式
        # 確保所有可能的號碼都在 classes 中
        all_possible_numbers = list(range(min_num, max_num + 1))
        mlb = MultiLabelBinarizer(classes=all_possible_numbers)
        y = mlb.fit_transform(y_raw)
        
        return np.array(X), y, mlb

    def _extract_features(self, history: List[Dict], current_index: int, pick_count: int, window_size: int = 5):
        """
        提取高級特徵
        包含：
        1. 每個號碼的遺漏值 (Gap)
        2. 每個號碼的近期頻率 (近 10, 30 期)
        3. 每個號碼的平均遺漏值
        4. 前 N 期的和值、奇偶比等統計特徵
        """
        features = []
        
        # 1. 基礎參數
        # 假設號碼範圍 1-49 (應從規則獲取，這裡暫時 hardcode 或從 history 推斷)
        all_numbers_flat = [n for d in history for n in d['numbers']]
        max_num = max(all_numbers_flat) if all_numbers_flat else 49
        min_num = 1
        
        # 2. 計算遺漏值 (Gap)
        # 對每個號碼，計算距離上次出現隔了多少期
        gaps = {num: 0 for num in range(min_num, max_num + 1)}
        # 從 current_index - 1 往回找
        for num in range(min_num, max_num + 1):
            gap = 0
            found = False
            for i in range(current_index - 1, -1, -1):
                if num in history[i]['numbers']:
                    found = True
                    break
                gap += 1
            gaps[num] = gap if found else 100 # 未出現過給個大值
            
        # 3. 計算頻率 (近 10 期, 近 30 期)
        freq_10 = {num: 0 for num in range(min_num, max_num + 1)}
        freq_30 = {num: 0 for num in range(min_num, max_num + 1)}
        
        start_10 = max(0, current_index - 10)
        start_30 = max(0, current_index - 30)
        
        for i in range(start_10, current_index):
            for num in history[i]['numbers']:
                if num in freq_10: freq_10[num] += 1
                
        for i in range(start_30, current_index):
            for num in history[i]['numbers']:
                if num in freq_30: freq_30[num] += 1
        
        # 4. 組合特徵向量
        # 順序: [Gap_1, Gap_2..., Freq10_1, Freq10_2..., Freq30_1, Freq30_2...]
        for num in range(min_num, max_num + 1):
            features.append(gaps[num])
            features.append(freq_10[num])
            features.append(freq_30[num])
            
        # 5. 加入前 5 期的統計特徵 (和值, 奇偶數)
        start_idx = max(0, current_index - 5)
        past_draws = history[start_idx:current_index]
        
        for draw in past_draws:
            nums = draw['numbers']
            features.append(sum(nums)) # 和值
            features.append(sum(1 for n in nums if n % 2 == 1)) # 奇數個數
            
        # 補齊特徵長度 (如果歷史不足 5 期)
        expected_draw_features = 5 * 2
        current_draw_features = len(past_draws) * 2
        if current_draw_features < expected_draw_features:
            features.extend([0] * (expected_draw_features - current_draw_features))
            
        return np.array(features)
