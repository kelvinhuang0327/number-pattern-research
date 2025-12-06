"""
Transformer 时序预测模型 (PatchTST 架构)

基于最新研究的 Transformer 架构，专门优化用于时间序列预测
参考论文: "A Time Series is Worth 64 Words: Long-term Forecasting with Transformers"

特点:
1. Patch-based 输入处理（降低计算复杂度）
2. Multi-head Self-Attention（捕获长期依赖）
3. 通道独立处理（每个号码位置独立建模）
4. 轻量级设计（适合实时预测）
"""

import numpy as np
import logging
from typing import List, Dict, Tuple, Optional
from collections import Counter, defaultdict
import warnings
warnings.filterwarnings('ignore')

logger = logging.getLogger(__name__)

# 尝试导入 PyTorch
HAS_TORCH = False
try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    from torch.utils.data import Dataset, DataLoader
    HAS_TORCH = True
    logger.info("✓ PyTorch 可用，使用完整 Transformer 实现")
except ImportError:
    logger.warning("⚠️ PyTorch 不可用，将使用轻量级实现")


# 定义 PatchTST 类（仅在 PyTorch 可用时）
if HAS_TORCH:
    class PatchTSTModel(nn.Module):
        """
        PatchTST: Patch-based Time Series Transformer

        核心思想：
        1. 将时间序列切分成多个 patches（类似 ViT 对图像的处理）
        2. 对每个 patch 应用线性投影
        3. 使用 Transformer Encoder 处理
        4. 独立预测每个通道（号码位置）
        """

        def __init__(
            self,
            num_channels: int = 6,      # 通道数（6个号码位置）
            seq_len: int = 50,          # 输入序列长度
            pred_len: int = 1,          # 预测长度
            patch_len: int = 8,         # Patch 长度
            stride: int = 4,            # Patch 步长
            d_model: int = 64,          # 模型维度
            n_heads: int = 4,           # 注意力头数
            n_layers: int = 2,          # Transformer 层数
            d_ff: int = 128,            # FFN 维度
            dropout: float = 0.1,
            num_classes: int = 49       # 分类数（号码范围）
        ):
            super().__init__()

            self.num_channels = num_channels
            self.seq_len = seq_len
            self.pred_len = pred_len
            self.patch_len = patch_len
            self.stride = stride
            self.num_classes = num_classes

            # 计算 patch 数量
            self.num_patches = (seq_len - patch_len) // stride + 1

            # Patch Embedding: 将每个 patch 投影到 d_model 维度
            self.patch_embedding = nn.Linear(patch_len, d_model)

            # Positional Encoding
            self.positional_encoding = nn.Parameter(
                torch.randn(1, self.num_patches, d_model)
            )

            # Transformer Encoder
            encoder_layer = nn.TransformerEncoderLayer(
                d_model=d_model,
                nhead=n_heads,
                dim_feedforward=d_ff,
                dropout=dropout,
                batch_first=True
            )
            self.transformer_encoder = nn.TransformerEncoder(
                encoder_layer,
                num_layers=n_layers
            )

            # 输出层：为每个通道独立预测
            self.output_layers = nn.ModuleList([
                nn.Sequential(
                    nn.Linear(d_model * self.num_patches, d_ff),
                    nn.ReLU(),
                    nn.Dropout(dropout),
                    nn.Linear(d_ff, num_classes)
                ) for _ in range(num_channels)
            ])

            # Dropout
            self.dropout = nn.Dropout(dropout)

        def create_patches(self, x: torch.Tensor) -> torch.Tensor:
            """
            将时间序列切分成 patches

            Args:
                x: [batch, channels, seq_len]

            Returns:
                patches: [batch, channels, num_patches, patch_len]
            """
            batch_size, channels, seq_len = x.shape
            patches = []

            for i in range(self.num_patches):
                start = i * self.stride
                end = start + self.patch_len
                patch = x[:, :, start:end]  # [batch, channels, patch_len]
                patches.append(patch)

            patches = torch.stack(patches, dim=2)  # [batch, channels, num_patches, patch_len]
            return patches

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            """
            前向传播

            Args:
                x: [batch, channels, seq_len] - 历史序列

            Returns:
                logits: [batch, channels, num_classes] - 每个通道的分类 logits
            """
            batch_size = x.shape[0]

            # 1. 创建 patches: [batch, channels, num_patches, patch_len]
            patches = self.create_patches(x)

            # 2. 对每个通道独立处理
            channel_outputs = []

            for ch in range(self.num_channels):
                # 获取当前通道的 patches: [batch, num_patches, patch_len]
                ch_patches = patches[:, ch, :, :]

                # 3. Patch Embedding: [batch, num_patches, d_model]
                embedded = self.patch_embedding(ch_patches)
                embedded = embedded + self.positional_encoding
                embedded = self.dropout(embedded)

                # 4. Transformer Encoder: [batch, num_patches, d_model]
                encoded = self.transformer_encoder(embedded)

                # 5. 展平并输出: [batch, d_model * num_patches] -> [batch, num_classes]
                flattened = encoded.reshape(batch_size, -1)
                logits = self.output_layers[ch](flattened)

                channel_outputs.append(logits)

            # [batch, channels, num_classes]
            output = torch.stack(channel_outputs, dim=1)
            return output


class TransformerPredictor:
    """
    基于 Transformer 的彩票预测器

    根据环境自动选择：
    1. 完整 PyTorch 实现（如果可用）
    2. 轻量级统计实现（回退方案）
    """

    def __init__(
        self,
        seq_len: int = 50,
        num_channels: int = 6,
        device: str = 'cpu'
    ):
        self.seq_len = seq_len
        self.num_channels = num_channels
        self.device = device
        self.model = None
        self.is_trained = False

        if HAS_TORCH:
            self.use_torch = True
            logger.info("TransformerPredictor 初始化 (PyTorch 完整实现)")
        else:
            self.use_torch = False
            logger.info("TransformerPredictor 初始化 (轻量级实现)")

    def prepare_sequences(
        self,
        history: List[Dict],
        lottery_rules: Dict
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        准备训练序列

        Returns:
            X: [num_samples, channels, seq_len] - 输入序列
            y: [num_samples, channels] - 目标值
        """
        max_num = lottery_rules.get('maxNumber', 49)
        pick_count = lottery_rules.get('pickCount', 6)

        # 反转历史（从旧到新）
        history_sorted = list(reversed(history))

        X_list = []
        y_list = []

        # 滑动窗口创建序列
        for i in range(len(history_sorted) - self.seq_len):
            # 输入序列: seq_len 期
            seq_data = history_sorted[i:i + self.seq_len]
            # 目标: 下一期
            target_data = history_sorted[i + self.seq_len]

            # 归一化号码到 [0, 1]
            seq_matrix = []
            for draw in seq_data:
                numbers = sorted(draw['numbers'])[:pick_count]
                # 补齐到 pick_count 个号码
                while len(numbers) < pick_count:
                    numbers.append(max_num // 2)
                # 归一化
                normalized = [n / max_num for n in numbers]
                seq_matrix.append(normalized)

            # 转置: [seq_len, channels] -> [channels, seq_len]
            seq_matrix = np.array(seq_matrix).T

            # 目标
            target_numbers = sorted(target_data['numbers'])[:pick_count]
            while len(target_numbers) < pick_count:
                target_numbers.append(max_num // 2)

            X_list.append(seq_matrix)
            y_list.append(target_numbers)

        X = np.array(X_list)  # [num_samples, channels, seq_len]
        y = np.array(y_list)  # [num_samples, channels]

        return X, y

    def train(
        self,
        history: List[Dict],
        lottery_rules: Dict,
        epochs: int = 20,
        batch_size: int = 16,
        learning_rate: float = 0.001
    ):
        """训练模型"""

        if not self.use_torch:
            logger.info("轻量级模式不需要训练，使用统计方法")
            self.is_trained = True
            return

        logger.info(f"开始训练 Transformer 模型 (epochs={epochs}, batch_size={batch_size})")

        # 准备数据
        X, y = self.prepare_sequences(history, lottery_rules)

        if len(X) < 10:
            logger.warning(f"训练数据不足 ({len(X)} 样本)，跳过训练")
            return

        logger.info(f"训练数据: {X.shape}, 目标: {y.shape}")

        # 创建模型
        max_num = lottery_rules.get('maxNumber', 49)
        self.model = PatchTSTModel(
            num_channels=self.num_channels,
            seq_len=self.seq_len,
            num_classes=max_num,
            d_model=64,
            n_heads=4,
            n_layers=2
        ).to(self.device)

        # 转换为 Tensor
        X_tensor = torch.FloatTensor(X).to(self.device)
        y_tensor = torch.LongTensor(y - 1).to(self.device)  # 转换为 0-indexed

        # 创建 DataLoader
        dataset = torch.utils.data.TensorDataset(X_tensor, y_tensor)
        dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

        # 优化器和损失函数
        optimizer = torch.optim.Adam(self.model.parameters(), lr=learning_rate)
        criterion = nn.CrossEntropyLoss()

        # 训练循环
        self.model.train()
        for epoch in range(epochs):
            total_loss = 0
            num_batches = 0

            for batch_X, batch_y in dataloader:
                optimizer.zero_grad()

                # 前向传播: [batch, channels, num_classes]
                logits = self.model(batch_X)

                # 计算每个通道的损失
                loss = 0
                for ch in range(self.num_channels):
                    ch_logits = logits[:, ch, :]  # [batch, num_classes]
                    ch_targets = batch_y[:, ch]   # [batch]
                    loss += criterion(ch_logits, ch_targets)

                loss = loss / self.num_channels

                # 反向传播
                loss.backward()
                optimizer.step()

                total_loss += loss.item()
                num_batches += 1

            avg_loss = total_loss / num_batches
            if (epoch + 1) % 5 == 0:
                logger.info(f"Epoch {epoch+1}/{epochs}, Loss: {avg_loss:.4f}")

        self.is_trained = True
        logger.info("✓ Transformer 模型训练完成")

    async def predict(
        self,
        history: List[Dict],
        lottery_rules: Dict
    ) -> Dict:
        """预测下一期号码"""

        logger.info("开始 Transformer 预测...")

        pick_count = lottery_rules.get('pickCount', 6)
        min_num = lottery_rules.get('minNumber', 1)
        max_num = lottery_rules.get('maxNumber', 49)

        # 如果使用 Torch 且模型未训练，先训练
        if self.use_torch and not self.is_trained:
            self.train(history, lottery_rules, epochs=15, batch_size=8)

        if self.use_torch and self.is_trained and self.model is not None:
            # PyTorch 预测
            predicted_numbers = self._predict_torch(history, lottery_rules)
        else:
            # 轻量级统计预测
            predicted_numbers = self._predict_lightweight(history, lottery_rules)

        # 预测特别号
        from .unified_predictor import predict_special_number
        special = predict_special_number(history, lottery_rules, predicted_numbers)

        confidence = 0.75 if self.use_torch else 0.65

        logger.info(f"✓ Transformer 预测完成: {predicted_numbers} (特别号: {special})")

        return {
            'numbers': predicted_numbers,
            'special': special,
            'confidence': confidence,
            'method': 'Transformer (PatchTST)' if self.use_torch else 'Transformer (轻量级)'
        }

    def _predict_torch(
        self,
        history: List[Dict],
        lottery_rules: Dict
    ) -> List[int]:
        """使用 PyTorch 模型预测"""

        min_num = lottery_rules.get('minNumber', 1)
        max_num = lottery_rules.get('maxNumber', 49)
        pick_count = lottery_rules.get('pickCount', 6)

        # 准备最近的序列
        recent_history = history[:self.seq_len]
        if len(recent_history) < self.seq_len:
            # 数据不足，回退到统计方法
            return self._predict_lightweight(history, lottery_rules)

        # 反转并归一化
        history_sorted = list(reversed(recent_history))
        seq_matrix = []

        for draw in history_sorted:
            numbers = sorted(draw['numbers'])[:pick_count]
            while len(numbers) < pick_count:
                numbers.append(max_num // 2)
            normalized = [n / max_num for n in numbers]
            seq_matrix.append(normalized)

        # [channels, seq_len]
        seq_matrix = np.array(seq_matrix).T

        # 转换为 Tensor: [1, channels, seq_len]
        X = torch.FloatTensor(seq_matrix).unsqueeze(0).to(self.device)

        # 预测
        self.model.eval()
        with torch.no_grad():
            logits = self.model(X)  # [1, channels, num_classes]

            # 为每个通道选择概率最高的号码
            probs = F.softmax(logits[0], dim=-1)  # [channels, num_classes]

            predicted_numbers = []
            used_numbers = set()

            # 第一轮：为每个通道选择最高概率且未使用的号码
            for ch in range(pick_count):
                ch_probs = probs[ch].cpu().numpy()
                # 排序获取 top-k
                sorted_indices = np.argsort(ch_probs)[::-1]

                # 选择第一个未使用的号码
                for idx in sorted_indices:
                    num = idx + 1  # 转回 1-indexed
                    if num not in used_numbers and min_num <= num <= max_num:
                        predicted_numbers.append(num)
                        used_numbers.add(num)
                        break

        # 确保有足够号码
        if len(predicted_numbers) < pick_count:
            # 使用频率补充
            freq_numbers = self._get_frequency_backup(history, lottery_rules, used_numbers)
            predicted_numbers.extend(freq_numbers[:pick_count - len(predicted_numbers)])

        return sorted(predicted_numbers[:pick_count])

    def _predict_lightweight(
        self,
        history: List[Dict],
        lottery_rules: Dict
    ) -> List[int]:
        """
        轻量级预测（不需要 PyTorch）

        使用改进的统计方法模拟 Transformer 的注意力机制：
        1. 近期加权频率（模拟时序注意力）
        2. 位置感知统计（模拟通道独立）
        3. 周期性分析（捕获长期模式）
        """

        pick_count = lottery_rules.get('pickCount', 6)
        min_num = lottery_rules.get('minNumber', 1)
        max_num = lottery_rules.get('maxNumber', 49)

        # 1. 近期加权频率（时间注意力）
        weighted_freq = defaultdict(float)
        for i, draw in enumerate(history[:30]):
            weight = np.exp(-0.05 * i)  # 指数衰减权重
            for num in draw['numbers']:
                weighted_freq[num] += weight

        # 2. 位置感知统计（每个位置的号码分布）
        position_prefs = [defaultdict(int) for _ in range(pick_count)]
        for draw in history[:50]:
            sorted_nums = sorted(draw['numbers'])
            for pos, num in enumerate(sorted_nums[:pick_count]):
                position_prefs[pos][num] += 1

        # 3. 周期性分析（查找重复模式）
        cycle_bonus = defaultdict(float)
        for period in [3, 5, 7]:  # 检查不同周期
            if len(history) >= period * 2:
                recent = set(history[0]['numbers'])
                past = set(history[period]['numbers'])
                overlap = recent & past
                for num in overlap:
                    cycle_bonus[num] += 0.5

        # 综合评分
        number_scores = {}
        for num in range(min_num, max_num + 1):
            score = 0

            # 加权频率得分 (40%)
            score += weighted_freq.get(num, 0) * 0.4

            # 位置偏好得分 (40%)
            pos_score = sum(position_prefs[pos].get(num, 0) for pos in range(pick_count))
            score += pos_score * 0.4

            # 周期性加成 (20%)
            score += cycle_bonus.get(num, 0) * 0.2

            number_scores[num] = score

        # 选择得分最高的号码
        sorted_numbers = sorted(number_scores.items(), key=lambda x: x[1], reverse=True)
        predicted = [num for num, score in sorted_numbers[:pick_count]]

        return sorted(predicted)

    def _get_frequency_backup(
        self,
        history: List[Dict],
        lottery_rules: Dict,
        exclude: set
    ) -> List[int]:
        """获取频率最高的号码作为备用"""

        pick_count = lottery_rules.get('pickCount', 6)
        freq = Counter()

        for draw in history[:30]:
            for num in draw['numbers']:
                if num not in exclude:
                    freq[num] += 1

        return [num for num, _ in freq.most_common(pick_count)]


# 工厂函数
def create_transformer_predictor(
    seq_len: int = 50,
    num_channels: int = 6,
    device: str = 'cpu'
) -> TransformerPredictor:
    """创建 Transformer 预测器"""
    return TransformerPredictor(seq_len, num_channels, device)
