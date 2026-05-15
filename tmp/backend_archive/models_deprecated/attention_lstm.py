#!/usr/bin/env python3
"""
Attention LSTM 預測模型
========================
基於 lotto-ai 概念，適配威力彩 (38主號 + 8特別號)
架構:
- Input: 滑動窗口 (過去 N 期的 One-Hot 編碼)
- Bidirectional LSTM + Attention 機制
- Output: 號碼機率分佈

參考: https://github.com/kyr0/lotto-ai
"""
import numpy as np
import os
import json

# 延遲導入 TensorFlow 以加速載入
_tf = None
_keras = None

def _load_tf():
    global _tf, _keras
    if _tf is None:
        os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
        os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'
        os.environ['OMP_NUM_THREADS'] = '1'
        import tensorflow as tf
        # 🔧 防止 Mac 上的 Threading 衝突 (libc++abi mutex lock failed)
        try:
            tf.config.threading.set_intra_op_parallelism_threads(1)
            tf.config.threading.set_inter_op_parallelism_threads(1)
        except:
            pass
        _tf = tf
        _keras = tf.keras
    return _tf, _keras


class AttentionLayer:
    """自定義 Attention 層"""

    @staticmethod
    def build(lstm_output, units=1):
        """
        實作注意力機制

        Args:
            lstm_output: LSTM 輸出 [batch, timesteps, features]
            units: attention dense units

        Returns:
            context_vector: 加權後的上下文向量
        """
        tf, keras = _load_tf()

        # Attention weights
        attention_dense = keras.layers.Dense(units, activation='tanh')
        attention_weights = attention_dense(lstm_output)  # [batch, timesteps, 1]

        # Softmax over timesteps
        attention_weights = keras.layers.Softmax(axis=1)(attention_weights)

        # Weighted sum (context vector)
        context_vector = keras.layers.Dot(axes=[1, 1])([attention_weights, lstm_output])

        return context_vector


class AttentionLSTMPredictor:
    """
    Attention LSTM 預測器

    特點:
    - 使用 One-Hot 編碼
    - 滑動窗口輸入
    - Bidirectional LSTM 雙向學習
    - Attention 機制學習重要的歷史期
    - L2 正則化 + Dropout 防止過擬合
    """

    def __init__(self, num_balls=38, window_size=5, lstm_units=64,
                 dropout_rate=0.3, l2_reg=0.001):
        """
        初始化

        Args:
            num_balls: 號碼範圍 (威力彩主號 1-38)
            window_size: 滑動窗口大小 (用幾期預測)
            lstm_units: LSTM 單元數
            dropout_rate: Dropout 比率
            l2_reg: L2 正則化係數
        """
        self.num_balls = num_balls
        self.window_size = window_size
        self.lstm_units = lstm_units
        self.dropout_rate = dropout_rate
        self.l2_reg = l2_reg
        self.model = None
        self.is_trained = False

    def _one_hot_encode(self, numbers, num_classes=None):
        """
        One-Hot 編碼

        Args:
            numbers: 號碼列表 [n1, n2, n3, ...]
            num_classes: 類別數

        Returns:
            one_hot: [num_classes] 的 0/1 向量
        """
        if num_classes is None:
            num_classes = self.num_balls

        one_hot = np.zeros(num_classes)
        for n in numbers:
            if 1 <= n <= num_classes:
                one_hot[n - 1] = 1
        return one_hot

    def _prepare_data(self, history):
        """
        準備訓練數據

        Args:
            history: 歷史開獎記錄 [{'numbers': [...], 'special': int}, ...]

        Returns:
            X: [samples, window_size, num_balls]
            y: [samples, num_balls]
        """
        if len(history) < self.window_size + 1:
            return None, None

        # One-Hot 編碼所有期
        encoded = []
        for draw in history:
            nums = [n for n in draw['numbers'] if n <= self.num_balls]
            encoded.append(self._one_hot_encode(nums))

        encoded = np.array(encoded)

        # 建立滑動窗口
        X, y = [], []
        for i in range(len(encoded) - self.window_size):
            X.append(encoded[i:i + self.window_size])
            y.append(encoded[i + self.window_size])

        return np.array(X), np.array(y)

    def _build_model(self):
        """建立 Attention LSTM 模型"""
        tf, keras = _load_tf()

        # Input shape: [window_size, num_balls]
        inputs = keras.layers.Input(shape=(self.window_size, self.num_balls))

        # Bidirectional LSTM with return_sequences for attention
        x = keras.layers.Bidirectional(
            keras.layers.LSTM(
                self.lstm_units,
                return_sequences=True,
                kernel_initializer='glorot_normal',
                recurrent_initializer='glorot_normal',
                kernel_regularizer=keras.regularizers.l2(self.l2_reg)
            )
        )(inputs)

        # Dropout
        x = keras.layers.Dropout(self.dropout_rate)(x)

        # Attention mechanism
        context = AttentionLayer.build(x)

        # Flatten
        x = keras.layers.Flatten()(context)

        # Output: 每個號碼的機率
        outputs = keras.layers.Dense(
            self.num_balls,
            activation='sigmoid',
            kernel_initializer='glorot_normal',
            kernel_regularizer=keras.regularizers.l2(self.l2_reg)
        )(x)

        model = keras.Model(inputs, outputs)

        model.compile(
            optimizer=keras.optimizers.Adam(learning_rate=0.001),
            loss='binary_crossentropy',
            metrics=['accuracy']
        )

        return model

    def train(self, history, epochs=50, batch_size=16, validation_split=0.2, verbose=0):
        """
        訓練模型

        Args:
            history: 歷史開獎記錄
            epochs: 訓練輪數
            batch_size: 批次大小
            validation_split: 驗證集比例
            verbose: 是否顯示訓練過程

        Returns:
            history: 訓練歷史
        """
        tf, keras = _load_tf()

        X, y = self._prepare_data(history)
        if X is None:
            return None

        self.model = self._build_model()

        # Early stopping
        early_stop = keras.callbacks.EarlyStopping(
            monitor='val_loss',
            patience=10,
            restore_best_weights=True
        )

        train_history = self.model.fit(
            X, y,
            epochs=epochs,
            batch_size=batch_size,
            validation_split=validation_split,
            callbacks=[early_stop],
            verbose=verbose
        )

        self.is_trained = True
        return train_history

    def predict_proba(self, history):
        """
        預測下一期各號碼的機率

        Args:
            history: 最近 window_size 期的歷史記錄

        Returns:
            proba: [num_balls] 的機率向量
        """
        if not self.is_trained or self.model is None:
            return None

        # 準備輸入
        recent = history[-self.window_size:]
        encoded = []
        for draw in recent:
            nums = [n for n in draw['numbers'] if n <= self.num_balls]
            encoded.append(self._one_hot_encode(nums))

        X = np.array([encoded])  # [1, window_size, num_balls]

        proba = self.model.predict(X, verbose=0)[0]
        return proba

    def predict(self, history, n_numbers=6, temperature=1.0):
        """
        預測下一期號碼

        Args:
            history: 歷史記錄
            n_numbers: 要預測幾個號碼
            temperature: 採樣溫度 (低=確定, 高=隨機)

        Returns:
            numbers: 預測的號碼列表
        """
        proba = self.predict_proba(history)
        if proba is None:
            return []

        if temperature != 1.0:
            # Temperature scaling
            proba = np.log(proba + 1e-10) / temperature
            proba = np.exp(proba) / np.sum(np.exp(proba))

        # 選擇 top-n 號碼
        indices = np.argsort(proba)[::-1][:n_numbers]
        numbers = sorted([i + 1 for i in indices])

        return numbers

    def predict_with_sampling(self, history, n_numbers=6, temperature=0.8, n_samples=10):
        """
        使用 Temperature 採樣預測多組號碼

        Args:
            history: 歷史記錄
            n_numbers: 每組幾個號碼
            temperature: 採樣溫度
            n_samples: 生成幾組

        Returns:
            samples: 多組預測號碼
        """
        proba = self.predict_proba(history)
        if proba is None:
            return []

        # Temperature scaling
        scaled = np.log(proba + 1e-10) / temperature
        scaled = np.exp(scaled) / np.sum(np.exp(scaled))

        samples = []
        for _ in range(n_samples):
            # 不重複採樣
            chosen = np.random.choice(
                self.num_balls,
                size=n_numbers,
                replace=False,
                p=scaled
            )
            samples.append(sorted([c + 1 for c in chosen]))

        return samples


def attention_lstm_predict(history, rules=None, n_numbers=6, **kwargs):
    """
    Attention LSTM 預測函數 (供回測框架使用)

    Args:
        history: 歷史開獎記錄
        rules: 彩種規則 (未使用)
        n_numbers: 預測號碼數

    Returns:
        dict: {'numbers': [...], 'method': 'attention_lstm'}
    """
    # 訓練窗口
    train_window = kwargs.get('train_window', 200)
    window_size = kwargs.get('window_size', 5)

    # 使用最近的數據訓練
    train_data = history[-train_window:] if len(history) > train_window else history

    if len(train_data) < window_size + 10:
        # 數據不足，返回頻率法
        from collections import Counter
        freq = Counter()
        for d in train_data:
            for n in d['numbers']:
                freq[n] += 1
        return {
            'numbers': [n for n, _ in freq.most_common(n_numbers)],
            'method': 'attention_lstm_fallback'
        }

    # 訓練模型
    predictor = AttentionLSTMPredictor(
        num_balls=38,
        window_size=window_size,
        lstm_units=64,
        dropout_rate=0.3
    )

    predictor.train(train_data, epochs=30, verbose=0)

    # 預測
    numbers = predictor.predict(train_data, n_numbers=n_numbers)

    return {
        'numbers': numbers,
        'method': 'attention_lstm'
    }


# ============ 快速測試 ============
if __name__ == '__main__':
    print("=" * 60)
    print("Attention LSTM 模型測試")
    print("=" * 60)

    # 載入測試數據
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

    from lottery_api.database import DatabaseManager

    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path=db_path)
    res = db.get_draws('POWER_LOTTO', page_size=300)
    history = res['draws']
    if history and history[0]['draw'] > history[-1]['draw']:
        history = history[::-1]

    print(f"載入 {len(history)} 期歷史數據")

    # 訓練模型
    predictor = AttentionLSTMPredictor(
        num_balls=38,
        window_size=5,
        lstm_units=64
    )

    print("\n訓練中...")
    train_data = history[:-10]  # 保留最後 10 期驗證
    predictor.train(train_data, epochs=30, verbose=1)

    # 預測
    print("\n預測結果:")
    for i in range(5):
        test_history = history[:-10+i] if i > 0 else history[:-10]
        actual = history[-10+i]['numbers'] if i < 10 else None

        pred = predictor.predict(test_history, n_numbers=6)

        if actual:
            match = len(set(pred) & set(actual))
            print(f"預測: {pred} | 實際: {sorted(actual)} | 命中: {match}/6")
