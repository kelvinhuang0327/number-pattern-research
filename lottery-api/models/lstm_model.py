import numpy as np
import logging
from typing import List, Dict
import os

# 嘗試導入 TensorFlow，如果失敗則標記不可用
# 臨時禁用TensorFlow以解決互斥鎖阻塞問題
HAS_TF = False
# try:
#     import tensorflow as tf
#     from tensorflow.keras.models import Sequential
#     from tensorflow.keras.layers import LSTM, Dense, Dropout, BatchNormalization
#     from tensorflow.keras.optimizers import Adam
#     HAS_TF = True
# except ImportError:
#     HAS_TF = False

logger = logging.getLogger(__name__)

class LSTMPredictor:
    """
    使用 LSTM (Long Short-Term Memory) 深度學習模型進行預測
    適合捕捉時間序列數據中的長期依賴關係
    """
    
    def __init__(self):
        self.model = None
        if not HAS_TF:
            logger.warning("TensorFlow 未安裝，LSTM 模型將無法使用。請執行: pip install tensorflow")
        else:
            logger.info("LSTMPredictor 初始化完成 (TensorFlow backend)")
            # 抑制 TF 日誌
            os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

    async def predict(self, history: List[Dict], lottery_rules: Dict) -> Dict:
        """
        預測下一期號碼
        """
        if not HAS_TF:
            raise ImportError("請安裝 tensorflow 以使用 LSTM 模型 (pip install tensorflow)")

        try:
            logger.info(f"開始 LSTM 預測，歷史數據量: {len(history)}")
            
            pick_count = lottery_rules.get('pickCount', 6)
            min_number = lottery_rules.get('minNumber', 1)
            max_number = lottery_rules.get('maxNumber', 49)
            total_numbers = max_number - min_number + 1
            
            # 1. 數據預處理
            # 使用過去 60 期作為時間窗口 (Time Steps)
            window_size = 60
            if len(history) < window_size + 10:
                raise ValueError(f"數據不足，LSTM 至少需要 {window_size + 10} 期數據")
            
            # 只取最近 1000 期訓練，避免過久遠數據干擾
            train_history = history[-1000:] if len(history) > 1000 else history
            
            X, y = self._prepare_data(train_history, window_size, min_number, max_number)
            
            # 2. 構建模型
            model = self._build_model(input_shape=(X.shape[1], X.shape[2]), output_dim=total_numbers)
            
            # 3. 訓練模型
            # epochs=50, batch_size=32
            model.fit(X, y, epochs=30, batch_size=32, verbose=0, validation_split=0.1)
            
            # 4. 預測下一期
            last_sequence = self._prepare_last_sequence(train_history, window_size, min_number, max_number)
            prediction_probs = model.predict(last_sequence, verbose=0)[0]
            
            # 5. 選擇機率最高的號碼
            # prediction_probs 是一個長度為 total_numbers 的陣列，表示每個號碼出現的機率
            number_probs = {}
            for i, prob in enumerate(prediction_probs):
                num = min_number + i
                number_probs[num] = float(prob)
                
            sorted_numbers = sorted(number_probs.items(), key=lambda x: x[1], reverse=True)
            predicted_numbers = sorted([num for num, _ in sorted_numbers[:pick_count]])
            
            confidence = np.mean([prob for _, prob in sorted_numbers[:pick_count]])
            
            return {
                "numbers": predicted_numbers,
                "confidence": float(confidence),
                "method": "LSTM 深度神經網絡",
                "probabilities": [float(prob) for _, prob in sorted_numbers[:pick_count]],
                "trend": "LSTM 深度學習趨勢預測",
                "modelInfo": {
                    "framework": "TensorFlow/Keras",
                    "architecture": "LSTM -> Dropout -> Dense",
                    "window_size": window_size
                }
            }

        except Exception as e:
            logger.error(f"LSTM 預測失敗: {str(e)}", exc_info=True)
            raise

    def _prepare_data(self, history, window_size, min_num, max_num):
        """
        準備 LSTM 訓練數據
        輸入: (Samples, Window_Size, Features)
        輸出: (Samples, Total_Numbers) - Multi-hot encoding
        """
        total_numbers = max_num - min_num + 1
        X = []
        y = []
        
        # 將每一期轉換為 Multi-hot 向量
        draws_vectorized = []
        for draw in history:
            vec = np.zeros(total_numbers)
            for num in draw['numbers']:
                if min_num <= num <= max_num:
                    vec[num - min_num] = 1
            draws_vectorized.append(vec)
            
        draws_vectorized = np.array(draws_vectorized)
        
        for i in range(window_size, len(draws_vectorized)):
            X.append(draws_vectorized[i-window_size:i])
            y.append(draws_vectorized[i])
            
        return np.array(X), np.array(y)

    def _prepare_last_sequence(self, history, window_size, min_num, max_num):
        """準備最後一期的輸入序列"""
        total_numbers = max_num - min_num + 1
        last_draws = history[-window_size:]
        
        sequence = []
        for draw in last_draws:
            vec = np.zeros(total_numbers)
            for num in draw['numbers']:
                if min_num <= num <= max_num:
                    vec[num - min_num] = 1
            sequence.append(vec)
            
        return np.array([sequence])

    def _build_model(self, input_shape, output_dim):
        """構建 LSTM 模型"""
        model = Sequential([
            LSTM(128, return_sequences=True, input_shape=input_shape),
            Dropout(0.3),
            BatchNormalization(),
            LSTM(64, return_sequences=False),
            Dropout(0.3),
            BatchNormalization(),
            Dense(64, activation='relu'),
            Dense(output_dim, activation='sigmoid') # 使用 sigmoid 因為是多標籤分類 (每個號碼獨立機率)
        ])
        
        model.compile(
            optimizer=Adam(learning_rate=0.001),
            loss='binary_crossentropy', # 多標籤分類使用 binary_crossentropy
            metrics=['accuracy']
        )
        return model
