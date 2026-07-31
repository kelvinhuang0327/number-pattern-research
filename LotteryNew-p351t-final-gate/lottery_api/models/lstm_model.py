"""
LSTM / 序列預測模型

支援兩種深度學習框架：
1. PyTorch（推薦 - macOS 上更穩定）
2. 回退到 NumPy 統計方法（如果深度學習框架都不可用）
"""

import numpy as np
import logging
from typing import List, Dict, Optional
from collections import Counter
import os

from .unified_predictor import log_data_range, get_data_range_info

logger = logging.getLogger(__name__)

# ===== 嘗試導入 PyTorch =====
HAS_PYTORCH = False
try:
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, TensorDataset
    HAS_PYTORCH = True
    logger.info(f"✅ PyTorch {torch.__version__} 可用")
except ImportError:
    logger.warning("PyTorch 未安裝")

# ===== 回退方案：sklearn =====
HAS_SKLEARN = False
try:
    from sklearn.ensemble import GradientBoostingClassifier
    HAS_SKLEARN = True
except ImportError:
    pass


# ===== PyTorch LSTM 模型定義 =====
if HAS_PYTORCH:
    class LotteryLSTM(nn.Module):
        """PyTorch LSTM 模型用於彩票號碼預測"""
        
        def __init__(self, input_dim: int, hidden_dim: int = 128, num_layers: int = 2, dropout: float = 0.3):
            super().__init__()
            self.hidden_dim = hidden_dim
            self.num_layers = num_layers
            
            self.lstm = nn.LSTM(
                input_size=input_dim,
                hidden_size=hidden_dim,
                num_layers=num_layers,
                batch_first=True,
                dropout=dropout if num_layers > 1 else 0
            )
            
            self.fc = nn.Sequential(
                nn.Linear(hidden_dim, 64),
                nn.ReLU(),
                nn.Dropout(dropout),
                nn.Linear(64, input_dim),
                nn.Sigmoid()  # 多標籤分類
            )
        
        def forward(self, x):
            # x shape: (batch, seq_len, input_dim)
            lstm_out, _ = self.lstm(x)
            # 取最後一個時間步的輸出
            last_output = lstm_out[:, -1, :]
            output = self.fc(last_output)
            return output


class LSTMPredictor:
    """
    序列預測模型
    
    優先使用 PyTorch LSTM，如果不可用則使用統計回退模式。
    """
    
    def __init__(self, model_path: Optional[str] = None):
        self.model = None
        self.model_path = model_path or "data/lstm_model.pt"
        self.use_pytorch = HAS_PYTORCH
        self.device = "cpu"  # 預設使用 CPU
        
        if HAS_PYTORCH:
            # 檢查 MPS (Apple Silicon) 可用性
            if torch.backends.mps.is_available():
                self.device = "mps"
                logger.info("🍎 使用 Apple Silicon MPS 加速")
            logger.info("LSTMPredictor 初始化完成 (PyTorch backend)")
        elif HAS_SKLEARN:
            logger.info("LSTMPredictor 初始化完成 (回退模式)")
        else:
            logger.warning("LSTMPredictor: 無深度學習框架可用")

    async def predict(self, history: List[Dict], lottery_rules: Dict) -> Dict:
        """預測下一期號碼"""
        log_data_range('LSTM/序列預測', history)

        try:
            logger.info(f"開始序列預測，歷史數據量: {len(history)}")

            if self.use_pytorch:
                return await self._predict_pytorch(history, lottery_rules)
            else:
                return await self._predict_fallback(history, lottery_rules)
                
        except Exception as e:
            logger.error(f"序列預測失敗: {str(e)}", exc_info=True)
            raise

    async def _predict_pytorch(self, history: List[Dict], lottery_rules: Dict) -> Dict:
        """使用 PyTorch LSTM 進行預測"""
        pick_count = lottery_rules.get('pickCount', 6)
        min_num = lottery_rules.get('minNumber', 1)
        max_num = lottery_rules.get('maxNumber', 49)
        total_numbers = max_num - min_num + 1
        
        window_size = 30  # 使用30期作為序列長度
        if len(history) < window_size + 10:
            raise ValueError(f"數據不足，LSTM 至少需要 {window_size + 10} 期數據")
        
        # 只使用最近 500 期（避免過久數據干擾）
        train_history = history[:500] if len(history) > 500 else history
        
        logger.info("🧠 PyTorch LSTM 開始訓練...")
        
        # 準備數據
        X, y = self._prepare_pytorch_data(train_history, window_size, min_num, max_num)
        
        # 轉換為 PyTorch 張量
        X_tensor = torch.FloatTensor(X).to(self.device)
        y_tensor = torch.FloatTensor(y).to(self.device)
        
        dataset = TensorDataset(X_tensor, y_tensor)
        dataloader = DataLoader(dataset, batch_size=32, shuffle=True)
        
        # 建立模型
        model = LotteryLSTM(input_dim=total_numbers).to(self.device)
        criterion = nn.BCELoss()
        optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
        
        # 訓練
        epochs = 30
        model.train()
        for epoch in range(epochs):
            total_loss = 0
            for batch_X, batch_y in dataloader:
                optimizer.zero_grad()
                outputs = model(batch_X)
                loss = criterion(outputs, batch_y)
                loss.backward()
                optimizer.step()
                total_loss += loss.item()
            
            if (epoch + 1) % 10 == 0:
                logger.info(f"   Epoch {epoch+1}/{epochs}, Loss: {total_loss/len(dataloader):.4f}")
        
        logger.info("✅ PyTorch LSTM 訓練完成")
        
        # 預測
        model.eval()
        with torch.no_grad():
            last_sequence = self._prepare_last_sequence_pytorch(train_history, window_size, min_num, max_num)
            last_sequence_tensor = torch.FloatTensor(last_sequence).to(self.device)
            prediction_probs = model(last_sequence_tensor).cpu().numpy()[0]
        
        # 選擇機率最高的號碼
        number_probs = {min_num + i: float(prob) for i, prob in enumerate(prediction_probs)}
        sorted_numbers = sorted(number_probs.items(), key=lambda x: x[1], reverse=True)
        predicted_numbers = sorted([num for num, _ in sorted_numbers[:pick_count]])
        
        confidence = float(np.mean([prob for _, prob in sorted_numbers[:pick_count]]))
        
        # 預測特別號碼

        result = {
            "numbers": predicted_numbers,
            "confidence": min(0.85, confidence),
            "method": "PyTorch LSTM 深度學習",
            "probabilities": [float(prob) for _, prob in sorted_numbers[:pick_count]],
            "trend": "LSTM 深度學習趨勢預測",
            "modelInfo": {
                "framework": f"PyTorch {torch.__version__}",
                "architecture": "LSTM(128) -> FC(64) -> Sigmoid",
                "device": self.device,
                "window_size": window_size,
                "epochs": epochs
            },
            "dataRange": get_data_range_info(history)
        }


        return result

    def _prepare_pytorch_data(self, history, window_size, min_num, max_num):
        """準備 PyTorch 訓練數據"""
        total_numbers = max_num - min_num + 1
        
        # 將每期轉換為多熱編碼
        draws_vectorized = []
        for draw in history:
            vec = np.zeros(total_numbers)
            for num in draw['numbers']:
                if min_num <= num <= max_num:
                    vec[num - min_num] = 1
            draws_vectorized.append(vec)
        
        draws_vectorized = np.array(draws_vectorized)
        
        X, y = [], []
        for i in range(len(draws_vectorized) - window_size):
            X.append(draws_vectorized[i:i+window_size])
            y.append(draws_vectorized[i+window_size])
        
        return np.array(X), np.array(y)

    def _prepare_last_sequence_pytorch(self, history, window_size, min_num, max_num):
        """準備預測用的最後序列"""
        total_numbers = max_num - min_num + 1
        last_draws = history[:window_size]  # 最近的 window_size 期
        
        sequence = []
        for draw in reversed(last_draws):  # 反轉因為 history 是最新在前
            vec = np.zeros(total_numbers)
            for num in draw['numbers']:
                if min_num <= num <= max_num:
                    vec[num - min_num] = 1
            sequence.append(vec)
        
        return np.array([sequence])

    async def _predict_fallback(self, history: List[Dict], lottery_rules: Dict) -> Dict:
        """回退預測方法：使用序列特徵 + 統計學習"""
        pick_count = lottery_rules.get('pickCount', 6)
        min_num = lottery_rules.get('minNumber', 1)
        max_num = lottery_rules.get('maxNumber', 49)
        total_numbers = max_num - min_num + 1
        
        window_size = 30
        if len(history) < window_size + 10:
            raise ValueError(f"數據不足，至少需要 {window_size + 10} 期數據")
        
        logger.info("🧮 使用序列特徵回退模式...")
        
        number_scores = {num: 0.0 for num in range(min_num, max_num + 1)}
        
        # 多窗口頻率分析
        windows = [10, 20, 50, 100]
        for w in windows:
            weight = 1.0 / (windows.index(w) + 1)
            recent = history[:min(w, len(history))]
            all_nums = [n for draw in recent for n in draw['numbers']]
            freq = Counter(all_nums)
            max_freq = max(freq.values()) if freq else 1
            for num in range(min_num, max_num + 1):
                number_scores[num] += (freq.get(num, 0) / max_freq) * weight
        
        # 遺漏值分析
        missing_days = {num: 0 for num in range(min_num, max_num + 1)}
        for draw in history:
            for num in range(min_num, max_num + 1):
                if num in draw['numbers']:
                    break
                missing_days[num] += 1
        
        max_missing = max(missing_days.values()) if missing_days else 1
        for num in range(min_num, max_num + 1):
            miss_score = missing_days[num] / max_missing
            if miss_score > 0.5:
                number_scores[num] += miss_score * 0.3
        
        # 趨勢分析
        decay = 0.95
        for i, draw in enumerate(history[:50]):
            weight = decay ** i
            for num in draw['numbers']:
                number_scores[num] += weight * 0.2
        
        # 添加隨機性
        for num in number_scores:
            number_scores[num] += np.random.uniform(0, 0.05)
        
        sorted_numbers = sorted(number_scores.items(), key=lambda x: x[1], reverse=True)
        predicted_numbers = sorted([num for num, _ in sorted_numbers[:pick_count]])
        
        top_scores = [score for _, score in sorted_numbers[:pick_count]]
        confidence = np.mean(top_scores) / max(top_scores) if top_scores else 0.5
        confidence = min(0.85, max(0.3, confidence))
        

        result = {
            "numbers": predicted_numbers,
            "confidence": float(confidence),
            "method": "序列特徵預測 (Fallback)",
            "probabilities": [float(score) for _, score in sorted_numbers[:pick_count]],
            "trend": "基於多窗口頻率、遺漏值和趨勢的序列分析",
            "modelInfo": {
                "framework": "NumPy + Statistics",
                "architecture": "Multi-window Feature Engineering",
                "window_sizes": windows
            },
            "dataRange": get_data_range_info(history)
        }


        logger.info(f"✅ 序列預測完成: {predicted_numbers}")
        return result

    def save_model(self, path: Optional[str] = None):
        """保存 PyTorch 模型"""
        if not HAS_PYTORCH or self.model is None:
            logger.warning("沒有可保存的模型")
            return False
        
        save_path = path or self.model_path
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        torch.save(self.model.state_dict(), save_path)
        logger.info(f"✅ 模型已保存至 {save_path}")
        return True

    def load_model(self, path: Optional[str] = None, input_dim: int = 49):
        """載入 PyTorch 模型"""
        if not HAS_PYTORCH:
            logger.warning("PyTorch 不可用，無法載入模型")
            return False
        
        load_path = path or self.model_path
        if not os.path.exists(load_path):
            logger.warning(f"模型文件不存在: {load_path}")
            return False
        
        self.model = LotteryLSTM(input_dim=input_dim).to(self.device)
        self.model.load_state_dict(torch.load(load_path, map_location=self.device))
        self.model.eval()
        logger.info(f"✅ 模型已從 {load_path} 載入")
        return True
