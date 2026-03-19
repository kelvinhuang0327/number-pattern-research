#!/usr/bin/env python3
"""
Per-Ball LSTM 預測模型
========================
借鑑 predict_Lottery_ticket 開源專案的技術:
1. Per-Ball Position Encoding: 為每個球位建立獨立 LSTM 分支
2. Number Embedding: 用 Embedding 替代 One-Hot
3. Greedy Dedup Sampling: 確保預測號碼不重複
4. ReduceLROnPlateau: 動態調整學習率
5. Clipnorm: 防止梯度爆炸

支援: 大樂透 (49選6) 和 威力彩 (38選6)
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
        try:
            tf.config.threading.set_intra_op_parallelism_threads(1)
            tf.config.threading.set_inter_op_parallelism_threads(1)
        except:
            pass
        _tf = tf
        _keras = tf.keras
    return _tf, _keras


class PerBallLSTMPredictor:
    """
    Per-Ball LSTM 預測器
    
    特點:
    - Number Embedding: 將號碼映射到向量空間
    - Per-Ball LSTM: 為每個球位建立獨立 LSTM 分支
    - Greedy Dedup: 預測時確保號碼不重複
    - 動態學習率調整
    """
    
    def __init__(self, num_balls=49, n_picks=6, window_size=5, 
                 embedding_dim=64, lstm_units=128, dropout_rate=0.3,
                 learning_rate=8e-4):
        """
        初始化
        
        Args:
            num_balls: 號碼範圍 (大樂透 1-49, 威力彩 1-38)
            n_picks: 每期選幾個號碼
            window_size: 滑動窗口大小
            embedding_dim: Embedding 維度
            lstm_units: LSTM 單元數
            dropout_rate: Dropout 比率
            learning_rate: 初始學習率
        """
        self.num_balls = num_balls
        self.n_picks = n_picks
        self.window_size = window_size
        self.embedding_dim = embedding_dim
        self.lstm_units = lstm_units
        self.dropout_rate = dropout_rate
        self.learning_rate = learning_rate
        self.model = None
        self.is_trained = False
        self._proba_cache = {} # Cache for (history_key, n_picks)
    
    def _prepare_data(self, history):
        """
        準備訓練數據 (0-based encoding)
        
        Args:
            history: 歷史開獎記錄 [{'numbers': [...], ...}, ...]
        
        Returns:
            X: [samples, window_size, n_picks] - 號碼序列 (0-based)
            y: [samples, n_picks, num_balls] - 每個球位的目標
        """
        if len(history) < self.window_size + 1:
            return None, None
        
        # 提取號碼並轉為 0-based
        all_draws = []
        for draw in history:
            nums = sorted([n for n in draw['numbers'] if 1 <= n <= self.num_balls])
            if len(nums) >= self.n_picks:
                nums = nums[:self.n_picks]
            else:
                # 補齊不足的
                while len(nums) < self.n_picks:
                    nums.append(nums[-1] if nums else 1)
            # 0-based encoding
            all_draws.append([n - 1 for n in nums])
        
        all_draws = np.array(all_draws, dtype=np.int32)
        
        # 建立滑動窗口
        X, y = [], []
        for i in range(len(all_draws) - self.window_size):
            X.append(all_draws[i:i + self.window_size])  # [window, n_picks]
            # 目標: 每個球位的 one-hot
            target = np.zeros((self.n_picks, self.num_balls), dtype=np.float32)
            for pos, num_idx in enumerate(all_draws[i + self.window_size]):
                target[pos, num_idx] = 1.0
            y.append(target)
        
        return np.array(X, dtype=np.int32), np.array(y, dtype=np.float32)
    
    def _build_model(self):
        """建立 Per-Ball LSTM 模型"""
        tf, keras = _load_tf()
        
        # Input: [window_size, n_picks]
        inputs = keras.layers.Input(shape=(self.window_size, self.n_picks), dtype='int32')
        
        # Number Embedding: 將號碼映射到向量空間
        # num_balls + 1 for 0-based indexing safety
        embedding = keras.layers.Embedding(
            input_dim=self.num_balls + 1,
            output_dim=self.embedding_dim,
            embeddings_initializer='he_normal',
            name='number_embedding'
        )
        
        # embedded: [batch, window, n_picks, embed_dim]
        embedded = embedding(inputs)
        
        # 將球位與時間維度交換，便於對每個球做 LSTM
        # permute to: [batch, n_picks, window, embed_dim]
        per_ball_sequence = keras.layers.Permute((2, 1, 3))(embedded)
        
        # TimeDistributed LSTM: 對每個球位獨立 LSTM
        per_ball_lstm = keras.layers.TimeDistributed(
            keras.layers.LSTM(self.lstm_units, return_sequences=False),
            name='per_ball_lstm'
        )
        
        # per_ball_encoded: [batch, n_picks, lstm_units]
        per_ball_encoded = per_ball_lstm(per_ball_sequence)
        
        # 全局 LSTM: 學習球位之間的關係
        global_lstm = keras.layers.LSTM(
            self.lstm_units // 2,
            return_sequences=True,
            dropout=self.dropout_rate,
            name='global_lstm'
        )
        
        # global_encoded: [batch, n_picks, lstm_units//2]
        global_encoded = global_lstm(per_ball_encoded)
        
        # Dropout
        x = keras.layers.Dropout(self.dropout_rate)(global_encoded)
        
        # 輸出層: 每個球位預測類別
        # logits: [batch, n_picks, num_balls]
        logits = keras.layers.Dense(self.num_balls, name='logits')(x)
        
        # Softmax: 每個球位的機率分佈
        outputs = keras.layers.Activation('softmax', name='output_proba')(logits)
        
        model = keras.Model(inputs=inputs, outputs=outputs, name='PerBallLSTM')
        
        # 使用 Clipnorm 防止梯度爆炸
        optimizer = keras.optimizers.Adam(
            learning_rate=self.learning_rate,
            clipnorm=1.0
        )
        
        model.compile(
            optimizer=optimizer,
            loss='categorical_crossentropy',
            metrics=['accuracy']
        )
        
        return model
    
    def train(self, history, epochs=60, batch_size=32, validation_split=0.15, verbose=0):
        """
        訓練模型
        
        Args:
            history: 歷史開獎記錄
            epochs: 訓練輪數
            batch_size: 批次大小
            validation_split: 驗證集比例
            verbose: 是否顯示訓練過程
        
        Returns:
            train_history: 訓練歷史
        """
        tf, keras = _load_tf()
        
        X, y = self._prepare_data(history)
        if X is None:
            return None
        
        self.model = self._build_model()
        
        callbacks = [
            # EarlyStopping
            keras.callbacks.EarlyStopping(
                monitor='val_loss',
                patience=8,
                restore_best_weights=True,
                verbose=verbose
            ),
            # ReduceLROnPlateau: 動態調整學習率
            keras.callbacks.ReduceLROnPlateau(
                monitor='val_loss',
                factor=0.5,
                patience=4,
                min_lr=1e-6,
                verbose=verbose
            )
        ]
        
        train_history = self.model.fit(
            X, y,
            epochs=epochs,
            batch_size=batch_size,
            validation_split=validation_split,
            callbacks=callbacks,
            verbose=verbose
        )
        
        self.is_trained = True
        return train_history

    def save_model(self, path):
        """保存模型"""
        if self.model:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            self.model.save(path)
            # 保存元數據
            meta_path = path + ".json"
            meta = {
                'num_balls': self.num_balls,
                'n_picks': self.n_picks,
                'window_size': self.window_size,
                'embedding_dim': self.embedding_dim,
                'lstm_units': self.lstm_units
            }
            with open(meta_path, 'w') as f:
                json.dump(meta, f)

    @classmethod
    def load_model(cls, path):
        """加載模型"""
        _, keras = _load_tf()
        meta_path = path + ".json"
        with open(meta_path, 'r') as f:
            meta = json.load(f)
        
        predictor = cls(**meta)
        predictor.model = keras.models.load_model(path)
        predictor.is_trained = True
        return predictor
    
    def predict_proba(self, history):
        """
        預測下一期各位置的號碼機率
        
        Returns:
            proba: [n_picks, num_balls] 每個球位的機率分佈
        """
        if not self.is_trained or self.model is None:
            return None
        
        # 準備最近 window_size 期的輸入
        recent = history[-self.window_size:]
        
        encoded = []
        for draw in recent:
            nums = sorted([n for n in draw['numbers'] if 1 <= n <= self.num_balls])
            if len(nums) >= self.n_picks:
                nums = nums[:self.n_picks]
            else:
                while len(nums) < self.n_picks:
                    nums.append(nums[-1] if nums else 1)
            encoded.append([n - 1 for n in nums])  # 0-based
        
        # 建立快取鍵
        history_key = str([d['draw'] for d in history[-self.window_size:]])
        if history_key in self._proba_cache:
            return self._proba_cache[history_key]

        X = np.array([encoded], dtype=np.int32)  # [1, window, n_picks]
        
        proba = self.model.predict(X, verbose=0)[0]  # [n_picks, num_balls]
        self._proba_cache[history_key] = proba
        return proba
    
    def predict(self, history, n_numbers=6):
        """
        預測下一期號碼 (使用 Greedy Dedup Sampling)
        
        Args:
            history: 歷史記錄
            n_numbers: 要預測幾個號碼
        
        Returns:
            numbers: 預測的號碼列表 (1-based)
        """
        proba = self.predict_proba(history)
        if proba is None:
            return []
        
        return self._greedy_dedup_sample(proba, n_numbers)
    
    def _greedy_dedup_sample(self, proba_matrix, n_picks):
        """
        Greedy Dedup Sampling: 確保預測號碼不重複
        
        Args:
            proba_matrix: [n_picks, num_balls] 機率矩陣
            n_picks: 要選幾個號碼
        
        Returns:
            numbers: 不重複的號碼列表 (1-based)
        """
        chosen = set()
        result = []
        
        for i in range(min(n_picks, proba_matrix.shape[0])):
            probs = proba_matrix[i].copy()
            
            # 將已選過的號碼概率置為 -inf
            for idx in chosen:
                if idx < len(probs):
                    probs[idx] = -np.inf
            
            # 選最高概率的號碼
            pick = int(np.argmax(probs))
            chosen.add(pick)
            result.append(pick + 1)  # 轉回 1-based
        
        return sorted(result)
    
    def predict_with_temperature(self, history, n_numbers=6, temperature=0.8, n_samples=10):
        """
        使用 Temperature Sampling 預測多組號碼
        
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
        
        samples = []
        for _ in range(n_samples):
            # Temperature scaling for each position
            sample = []
            chosen = set()
            
            for i in range(min(n_numbers, proba.shape[0])):
                probs = proba[i].copy()
                
                # Mask already chosen
                for idx in chosen:
                    probs[idx] = 0
                
                # Temperature scaling
                if temperature != 1.0:
                    log_probs = np.log(probs + 1e-10) / temperature
                    scaled = np.exp(log_probs)
                    scaled = scaled / (np.sum(scaled) + 1e-10)
                else:
                    scaled = probs / (np.sum(probs) + 1e-10)
                
                # Sample
                pick = np.random.choice(len(scaled), p=scaled)
                chosen.add(pick)
                sample.append(pick + 1)
            
            samples.append(sorted(sample))
        
        return samples


def perball_lstm_predict(history, rules=None, n_numbers=6, **kwargs):
    """
    Per-Ball LSTM 預測函數 (供回測框架使用)
    
    Args:
        history: 歷史開獎記錄
        rules: 彩種規則
        n_numbers: 預測號碼數
    
    Returns:
        dict: {'numbers': [...], 'method': 'perball_lstm'}
    """
    # 參數
    train_window = kwargs.get('train_window', 200)
    window_size = kwargs.get('window_size', 5)
    num_balls = kwargs.get('num_balls', 49)  # 預設大樂透
    
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
            'method': 'perball_lstm_fallback'
        }
    
    # 訓練模型
    predictor = PerBallLSTMPredictor(
        num_balls=num_balls,
        n_picks=n_numbers,
        window_size=window_size,
        embedding_dim=64,
        lstm_units=128,
        dropout_rate=0.3
    )
    
    predictor.train(train_data, epochs=40, verbose=0)
    
    # 預測
    numbers = predictor.predict(train_data, n_numbers=n_numbers)
    
    return {
        'numbers': numbers,
        'method': 'perball_lstm'
    }


# ============ 配置常量 ============
LOTTERY_CONFIGS = {
    'big_lotto': {
        'num_balls': 49,
        'n_picks': 6,
        'name': '大樂透',
        'embedding_dim': 64,
        'hidden_units': (128, 64),
        'dropout': 0.3,
        'window_size': 5
    },
    'power_lotto': {
        'num_balls': 38,
        'n_picks': 6,
        'name': '威力彩',
        'embedding_dim': 48,
        'hidden_units': (96, 48),
        'dropout': 0.3,
        'window_size': 5
    }
}


# ============ 快速測試 ============
if __name__ == '__main__':
    print("=" * 60)
    print("Per-Ball LSTM 模型測試")
    print("=" * 60)
    
    # 載入測試數據
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    
    from lottery_api.database import DatabaseManager
    
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path=db_path)
    
    # 測試大樂透
    res = db.get_draws('BIG_LOTTO', page_size=300)
    history = res['draws']
    if history and history[0]['draw'] > history[-1]['draw']:
        history = history[::-1]
    
    print(f"載入大樂透 {len(history)} 期歷史數據")
    
    # 訓練模型
    predictor = PerBallLSTMPredictor(
        num_balls=49,
        n_picks=6,
        window_size=5,
        embedding_dim=64,
        lstm_units=128
    )
    
    print("\n訓練中...")
    train_data = history[:-10]  # 保留最後 10 期驗證
    predictor.train(train_data, epochs=30, verbose=1)
    
    # 預測並驗證
    print("\n預測結果:")
    total_match = 0
    for i in range(10):
        test_history = history[:-10+i] if i > 0 else history[:-10]
        actual = history[-10+i]['numbers'] if i < 10 else None
        
        pred = predictor.predict(test_history, n_numbers=6)
        
        if actual:
            match = len(set(pred) & set(actual))
            total_match += match
            print(f"預測: {pred} | 實際: {sorted(actual)} | 命中: {match}/6")
    
    print(f"\n平均命中: {total_match/10:.2f}/6")
