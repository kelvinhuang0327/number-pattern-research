"""
策略2: 時間序列深度學習 (LSTM + Attention)
用於大樂透號碼預測的深度學習模型

特點:
1. Bidirectional LSTM 捕捉雙向時間依賴
2. Multi-Head Self-Attention 關注重要歷史模式
3. 多任務學習: 同時預測號碼概率和統計特徵
4. 特徵增強: 加入奇偶、區間、總和等統計特徵
"""

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
from typing import List, Dict, Tuple, Optional
from collections import Counter
import logging
import os
import pickle

logger = logging.getLogger(__name__)


class LotteryDataset(Dataset):
    """彩票數據集"""

    def __init__(self, draws: List[Dict], seq_length: int = 30, num_range: int = 49):
        """
        Args:
            draws: 歷史開獎數據 (新→舊排序)
            seq_length: 序列長度 (使用多少期歷史)
            num_range: 號碼範圍 (1-49)
        """
        self.draws = draws
        self.seq_length = seq_length
        self.num_range = num_range
        self.samples = self._prepare_samples()

    def _number_to_multihot(self, numbers: List[int]) -> np.ndarray:
        """將號碼轉換為 multi-hot 編碼"""
        vec = np.zeros(self.num_range, dtype=np.float32)
        for n in numbers:
            if 1 <= n <= self.num_range:
                vec[n-1] = 1.0
        return vec

    def _extract_features(self, numbers: List[int]) -> np.ndarray:
        """提取統計特徵"""
        features = []

        # 1. 奇數比例
        odd_ratio = sum(1 for n in numbers if n % 2 == 1) / len(numbers)
        features.append(odd_ratio)

        # 2. 總和（歸一化）
        total = sum(numbers)
        normalized_sum = (total - 21) / (279 - 21)  # 大樂透總和範圍: 21-279
        features.append(normalized_sum)

        # 3. 區間分布 (低/中/高)
        low = sum(1 for n in numbers if n <= 16) / len(numbers)
        mid = sum(1 for n in numbers if 17 <= n <= 33) / len(numbers)
        high = sum(1 for n in numbers if n >= 34) / len(numbers)
        features.extend([low, mid, high])

        # 4. 連號數量
        sorted_nums = sorted(numbers)
        consecutive = sum(1 for i in range(len(sorted_nums)-1)
                        if sorted_nums[i+1] - sorted_nums[i] == 1)
        features.append(consecutive / (len(numbers) - 1))

        # 5. 號碼跨度
        span = max(numbers) - min(numbers)
        features.append(span / (self.num_range - 1))

        # 6. 平均間隔
        avg_gap = np.mean([sorted_nums[i+1] - sorted_nums[i]
                         for i in range(len(sorted_nums)-1)])
        features.append(avg_gap / self.num_range)

        return np.array(features, dtype=np.float32)

    def _prepare_samples(self) -> List[Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]]:
        """準備訓練樣本"""
        samples = []

        for i in range(len(self.draws) - self.seq_length - 1):
            # 目標: 第 i 期的號碼
            target_draw = self.draws[i]
            target_numbers = target_draw.get('numbers', [])

            if len(target_numbers) != 6:
                continue

            # 輸入序列: 第 i+1 到 i+seq_length 期
            seq_multihot = []
            seq_features = []

            valid_seq = True
            for j in range(i + 1, i + 1 + self.seq_length):
                if j >= len(self.draws):
                    valid_seq = False
                    break

                hist_numbers = self.draws[j].get('numbers', [])
                if len(hist_numbers) != 6:
                    valid_seq = False
                    break

                seq_multihot.append(self._number_to_multihot(hist_numbers))
                seq_features.append(self._extract_features(hist_numbers))

            if not valid_seq:
                continue

            # 轉換為 numpy arrays
            X_multihot = np.array(seq_multihot)  # [seq_length, num_range]
            X_features = np.array(seq_features)  # [seq_length, num_features]
            y_multihot = self._number_to_multihot(target_numbers)  # [num_range]
            y_features = self._extract_features(target_numbers)  # [num_features]

            samples.append((X_multihot, X_features, y_multihot, y_features))

        return samples

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        X_multihot, X_features, y_multihot, y_features = self.samples[idx]
        return (
            torch.FloatTensor(X_multihot),
            torch.FloatTensor(X_features),
            torch.FloatTensor(y_multihot),
            torch.FloatTensor(y_features)
        )


class MultiHeadAttention(nn.Module):
    """多頭自注意力機制"""

    def __init__(self, d_model: int, num_heads: int = 4, dropout: float = 0.1):
        super().__init__()
        assert d_model % num_heads == 0

        self.d_model = d_model
        self.num_heads = num_heads
        self.d_k = d_model // num_heads

        self.W_q = nn.Linear(d_model, d_model)
        self.W_k = nn.Linear(d_model, d_model)
        self.W_v = nn.Linear(d_model, d_model)
        self.W_o = nn.Linear(d_model, d_model)

        self.dropout = nn.Dropout(dropout)
        self.layer_norm = nn.LayerNorm(d_model)

    def forward(self, x: torch.Tensor, mask: torch.Tensor = None) -> torch.Tensor:
        """
        Args:
            x: [batch, seq_len, d_model]
            mask: optional attention mask
        Returns:
            [batch, seq_len, d_model]
        """
        batch_size, seq_len, _ = x.shape
        residual = x

        # 線性變換
        Q = self.W_q(x).view(batch_size, seq_len, self.num_heads, self.d_k).transpose(1, 2)
        K = self.W_k(x).view(batch_size, seq_len, self.num_heads, self.d_k).transpose(1, 2)
        V = self.W_v(x).view(batch_size, seq_len, self.num_heads, self.d_k).transpose(1, 2)

        # 計算注意力分數
        scores = torch.matmul(Q, K.transpose(-2, -1)) / np.sqrt(self.d_k)

        if mask is not None:
            scores = scores.masked_fill(mask == 0, -1e9)

        attn_weights = F.softmax(scores, dim=-1)
        attn_weights = self.dropout(attn_weights)

        # 加權求和
        context = torch.matmul(attn_weights, V)
        context = context.transpose(1, 2).contiguous().view(batch_size, seq_len, self.d_model)

        # 輸出投影 + 殘差連接 + LayerNorm
        output = self.W_o(context)
        output = self.dropout(output)
        output = self.layer_norm(output + residual)

        return output


class LotteryLSTMAttention(nn.Module):
    """
    LSTM + Attention 彩票預測模型

    架構:
    1. 輸入嵌入層 (Multi-hot + 統計特徵)
    2. Bidirectional LSTM
    3. Multi-Head Self-Attention
    4. 全連接輸出層 (號碼概率 + 統計特徵)
    """

    def __init__(
        self,
        num_range: int = 49,
        num_features: int = 8,
        hidden_size: int = 128,
        num_layers: int = 2,
        num_heads: int = 4,
        dropout: float = 0.3
    ):
        super().__init__()

        self.num_range = num_range
        self.num_features = num_features
        self.hidden_size = hidden_size

        # 輸入嵌入
        self.input_proj = nn.Linear(num_range + num_features, hidden_size)
        self.input_norm = nn.LayerNorm(hidden_size)
        self.input_dropout = nn.Dropout(dropout)

        # Bidirectional LSTM
        self.lstm = nn.LSTM(
            input_size=hidden_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            bidirectional=True,
            dropout=dropout if num_layers > 1 else 0
        )

        # Self-Attention
        self.attention = MultiHeadAttention(
            d_model=hidden_size * 2,  # bidirectional
            num_heads=num_heads,
            dropout=dropout
        )

        # 輸出層
        self.fc1 = nn.Linear(hidden_size * 2, hidden_size)
        self.fc2 = nn.Linear(hidden_size, hidden_size // 2)

        # 多任務輸出
        self.number_head = nn.Linear(hidden_size // 2, num_range)  # 號碼概率
        self.feature_head = nn.Linear(hidden_size // 2, num_features)  # 統計特徵

        self.dropout = nn.Dropout(dropout)
        self.relu = nn.ReLU()

    def forward(
        self,
        x_multihot: torch.Tensor,
        x_features: torch.Tensor
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Args:
            x_multihot: [batch, seq_len, num_range]
            x_features: [batch, seq_len, num_features]
        Returns:
            number_probs: [batch, num_range] - 每個號碼的出現概率
            feature_pred: [batch, num_features] - 預測的統計特徵
        """
        # 合併輸入
        x = torch.cat([x_multihot, x_features], dim=-1)  # [batch, seq_len, num_range + num_features]

        # 輸入嵌入
        x = self.input_proj(x)
        x = self.input_norm(x)
        x = self.relu(x)
        x = self.input_dropout(x)

        # LSTM
        lstm_out, _ = self.lstm(x)  # [batch, seq_len, hidden_size * 2]

        # Self-Attention
        attn_out = self.attention(lstm_out)  # [batch, seq_len, hidden_size * 2]

        # 取最後一個時間步 + 平均池化
        last_hidden = attn_out[:, -1, :]  # [batch, hidden_size * 2]
        avg_hidden = attn_out.mean(dim=1)  # [batch, hidden_size * 2]
        combined = last_hidden + avg_hidden  # 結合兩種表示

        # 全連接層
        h = self.relu(self.fc1(combined))
        h = self.dropout(h)
        h = self.relu(self.fc2(h))
        h = self.dropout(h)

        # 多任務輸出
        number_logits = self.number_head(h)
        number_probs = torch.sigmoid(number_logits)  # [batch, num_range]

        feature_pred = self.feature_head(h)  # [batch, num_features]

        return number_probs, feature_pred


class LSTMAttentionPredictor:
    """LSTM + Attention 預測器封裝類"""

    def __init__(
        self,
        num_range: int = 49,
        seq_length: int = 30,
        hidden_size: int = 128,
        num_layers: int = 2,
        device: str = None
    ):
        self.num_range = num_range
        self.seq_length = seq_length
        self.num_features = 8  # 統計特徵數量

        # 自動選擇設備
        if device is None:
            self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        else:
            self.device = torch.device(device)

        # 初始化模型
        self.model = LotteryLSTMAttention(
            num_range=num_range,
            num_features=self.num_features,
            hidden_size=hidden_size,
            num_layers=num_layers
        ).to(self.device)

        self.is_trained = False
        self.training_history = []

    def _number_to_multihot(self, numbers: List[int]) -> np.ndarray:
        """將號碼轉換為 multi-hot 編碼"""
        vec = np.zeros(self.num_range, dtype=np.float32)
        for n in numbers:
            if 1 <= n <= self.num_range:
                vec[n-1] = 1.0
        return vec

    def _extract_features(self, numbers: List[int]) -> np.ndarray:
        """提取統計特徵"""
        features = []

        odd_ratio = sum(1 for n in numbers if n % 2 == 1) / len(numbers)
        features.append(odd_ratio)

        total = sum(numbers)
        normalized_sum = (total - 21) / (279 - 21)
        features.append(normalized_sum)

        low = sum(1 for n in numbers if n <= 16) / len(numbers)
        mid = sum(1 for n in numbers if 17 <= n <= 33) / len(numbers)
        high = sum(1 for n in numbers if n >= 34) / len(numbers)
        features.extend([low, mid, high])

        sorted_nums = sorted(numbers)
        consecutive = sum(1 for i in range(len(sorted_nums)-1)
                        if sorted_nums[i+1] - sorted_nums[i] == 1)
        features.append(consecutive / (len(numbers) - 1))

        span = max(numbers) - min(numbers)
        features.append(span / (self.num_range - 1))

        avg_gap = np.mean([sorted_nums[i+1] - sorted_nums[i]
                         for i in range(len(sorted_nums)-1)])
        features.append(avg_gap / self.num_range)

        return np.array(features, dtype=np.float32)

    def train(
        self,
        draws: List[Dict],
        epochs: int = 100,
        batch_size: int = 32,
        learning_rate: float = 0.001,
        validation_split: float = 0.2,
        early_stopping_patience: int = 15,
        verbose: bool = True
    ) -> Dict:
        """
        訓練模型

        Args:
            draws: 歷史開獎數據
            epochs: 訓練輪數
            batch_size: 批次大小
            learning_rate: 學習率
            validation_split: 驗證集比例
            early_stopping_patience: 早停耐心值
            verbose: 是否顯示訓練進度

        Returns:
            訓練歷史記錄
        """
        # 準備數據集
        dataset = LotteryDataset(draws, self.seq_length, self.num_range)

        if len(dataset) < 50:
            raise ValueError(f"數據不足: 只有 {len(dataset)} 個樣本，至少需要 50 個")

        # 分割訓練集和驗證集
        val_size = int(len(dataset) * validation_split)
        train_size = len(dataset) - val_size

        train_dataset, val_dataset = torch.utils.data.random_split(
            dataset, [train_size, val_size]
        )

        train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
        val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)

        # 優化器和損失函數
        optimizer = torch.optim.AdamW(self.model.parameters(), lr=learning_rate, weight_decay=0.01)
        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=5, factor=0.5)

        # 加權 BCE Loss (處理類別不平衡)
        pos_weight = torch.ones(self.num_range) * 7  # 每期只有6個號碼中獎
        number_criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight.to(self.device))
        feature_criterion = nn.MSELoss()

        # 訓練循環
        best_val_loss = float('inf')
        patience_counter = 0
        history = {'train_loss': [], 'val_loss': [], 'val_accuracy': []}

        if verbose:
            print(f"開始訓練 LSTM+Attention 模型...")
            print(f"訓練樣本: {train_size}, 驗證樣本: {val_size}")
            print(f"設備: {self.device}")

        for epoch in range(epochs):
            # 訓練階段
            self.model.train()
            train_loss = 0.0

            for X_mh, X_f, y_mh, y_f in train_loader:
                X_mh = X_mh.to(self.device)
                X_f = X_f.to(self.device)
                y_mh = y_mh.to(self.device)
                y_f = y_f.to(self.device)

                optimizer.zero_grad()

                number_probs, feature_pred = self.model(X_mh, X_f)

                # 計算損失 (多任務)
                loss_number = number_criterion(
                    torch.log(number_probs + 1e-8) - torch.log(1 - number_probs + 1e-8),
                    y_mh
                )
                loss_feature = feature_criterion(feature_pred, y_f)
                loss = loss_number + 0.3 * loss_feature

                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
                optimizer.step()

                train_loss += loss.item()

            train_loss /= len(train_loader)

            # 驗證階段
            self.model.eval()
            val_loss = 0.0
            correct_predictions = 0
            total_predictions = 0

            with torch.no_grad():
                for X_mh, X_f, y_mh, y_f in val_loader:
                    X_mh = X_mh.to(self.device)
                    X_f = X_f.to(self.device)
                    y_mh = y_mh.to(self.device)
                    y_f = y_f.to(self.device)

                    number_probs, feature_pred = self.model(X_mh, X_f)

                    loss_number = number_criterion(
                        torch.log(number_probs + 1e-8) - torch.log(1 - number_probs + 1e-8),
                        y_mh
                    )
                    loss_feature = feature_criterion(feature_pred, y_f)
                    loss = loss_number + 0.3 * loss_feature

                    val_loss += loss.item()

                    # 計算準確率 (預測的 Top-6 與實際的交集)
                    _, top6_indices = torch.topk(number_probs, 6, dim=1)
                    for i in range(y_mh.shape[0]):
                        predicted_set = set((top6_indices[i] + 1).cpu().numpy())
                        actual_set = set(torch.where(y_mh[i] == 1)[0].cpu().numpy() + 1)
                        correct_predictions += len(predicted_set & actual_set)
                        total_predictions += 6

            val_loss /= len(val_loader)
            val_accuracy = correct_predictions / total_predictions

            history['train_loss'].append(train_loss)
            history['val_loss'].append(val_loss)
            history['val_accuracy'].append(val_accuracy)

            scheduler.step(val_loss)

            if verbose and (epoch + 1) % 10 == 0:
                print(f"Epoch {epoch+1}/{epochs} - "
                      f"Train Loss: {train_loss:.4f}, "
                      f"Val Loss: {val_loss:.4f}, "
                      f"Val Acc: {val_accuracy:.4f}")

            # 早停檢查
            if val_loss < best_val_loss:
                best_val_loss = val_loss
                patience_counter = 0
                # 保存最佳模型
                self.best_state = {k: v.cpu().clone() for k, v in self.model.state_dict().items()}
            else:
                patience_counter += 1
                if patience_counter >= early_stopping_patience:
                    if verbose:
                        print(f"早停於 Epoch {epoch+1}")
                    break

        # 恢復最佳模型
        if hasattr(self, 'best_state'):
            self.model.load_state_dict({k: v.to(self.device) for k, v in self.best_state.items()})

        self.is_trained = True
        self.training_history = history

        if verbose:
            print(f"訓練完成! 最佳驗證損失: {best_val_loss:.4f}")
            print(f"最終驗證準確率: {history['val_accuracy'][-1]:.4f}")

        return history

    def predict(self, history: List[Dict], rules: Dict, top_k: int = 6) -> Dict:
        """
        預測下一期號碼

        Args:
            history: 歷史開獎數據 (需要至少 seq_length 期)
            rules: 彩票規則
            top_k: 選擇前幾個號碼

        Returns:
            預測結果
        """
        if not self.is_trained:
            raise RuntimeError("模型尚未訓練，請先調用 train() 方法")

        if len(history) < self.seq_length:
            raise ValueError(f"歷史數據不足: 需要至少 {self.seq_length} 期")

        self.model.eval()

        # 準備輸入
        seq_multihot = []
        seq_features = []

        for i in range(self.seq_length):
            numbers = history[i].get('numbers', [])
            if len(numbers) != 6:
                # 如果某期數據異常，使用前一期的數據
                if i > 0 and seq_multihot:
                    seq_multihot.append(seq_multihot[-1])
                    seq_features.append(seq_features[-1])
                continue

            seq_multihot.append(self._number_to_multihot(numbers))
            seq_features.append(self._extract_features(numbers))

        X_multihot = torch.FloatTensor(np.array(seq_multihot)).unsqueeze(0).to(self.device)
        X_features = torch.FloatTensor(np.array(seq_features)).unsqueeze(0).to(self.device)

        with torch.no_grad():
            number_probs, feature_pred = self.model(X_multihot, X_features)

        # 獲取概率最高的 top_k 個號碼
        probs = number_probs[0].cpu().numpy()
        top_indices = np.argsort(probs)[::-1][:top_k]
        predicted_numbers = [int(i + 1) for i in top_indices]

        # 計算置信度
        confidence = float(np.mean([probs[i] for i in top_indices]))

        # 預測的統計特徵
        pred_features = feature_pred[0].cpu().numpy()

        return {
            'numbers': sorted(predicted_numbers),
            'confidence': confidence,
            'method': 'lstm_attention_predict',
            'probabilities': {i+1: float(probs[i]) for i in range(len(probs))},
            'predicted_features': {
                'odd_ratio': float(pred_features[0]),
                'sum_normalized': float(pred_features[1]),
                'zone_low': float(pred_features[2]),
                'zone_mid': float(pred_features[3]),
                'zone_high': float(pred_features[4]),
                'consecutive_ratio': float(pred_features[5]),
                'span_normalized': float(pred_features[6]),
                'avg_gap_normalized': float(pred_features[7]),
            }
        }

    def save(self, filepath: str):
        """保存模型"""
        torch.save({
            'model_state_dict': self.model.state_dict(),
            'num_range': self.num_range,
            'seq_length': self.seq_length,
            'is_trained': self.is_trained,
            'training_history': self.training_history
        }, filepath)
        logger.info(f"模型已保存至: {filepath}")

    def load(self, filepath: str):
        """載入模型"""
        checkpoint = torch.load(filepath, map_location=self.device)
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.num_range = checkpoint['num_range']
        self.seq_length = checkpoint['seq_length']
        self.is_trained = checkpoint['is_trained']
        self.training_history = checkpoint.get('training_history', [])
        logger.info(f"模型已從 {filepath} 載入")


# 全局預測器實例
_lstm_predictor = None

def get_lstm_predictor(force_new: bool = False) -> LSTMAttentionPredictor:
    """獲取 LSTM 預測器實例"""
    global _lstm_predictor
    if _lstm_predictor is None or force_new:
        _lstm_predictor = LSTMAttentionPredictor()
    return _lstm_predictor


def lstm_attention_predict(history: List[Dict], rules: Dict) -> Dict:
    """
    LSTM + Attention 預測函數（統一接口）

    Args:
        history: 歷史開獎數據
        rules: 彩票規則

    Returns:
        預測結果
    """
    predictor = get_lstm_predictor()

    # 如果模型未訓練，先訓練
    if not predictor.is_trained:
        logger.info("LSTM模型首次使用，開始訓練...")
        predictor.train(history, epochs=50, verbose=False)

    return predictor.predict(history, rules)
