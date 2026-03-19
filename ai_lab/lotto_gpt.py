
import torch
import torch.nn as nn
from torch.nn import functional as F
import numpy as np
import logging

class LottoGPTLite(nn.Module):
    """
    LottoGPT-Lite: 專為彩票序列預測設計的小型 Transformer
    架構參考 minGPT，但參數量極小化以避免過擬合 (彩票數據極少)
    """
    def __init__(self, vocab_size=50, d_model=64, n_head=4, n_layer=2, block_size=10):
        super().__init__()
        self.block_size = block_size
        
        # Embedding: 號碼嵌入 + 位置嵌入
        self.token_embedding = nn.Embedding(vocab_size, d_model)
        self.position_embedding = nn.Parameter(torch.zeros(1, block_size, d_model))
        
        # Transformer Blocks
        self.blocks = nn.Sequential(*[
            nn.TransformerEncoderLayer(
                d_model=d_model, 
                nhead=n_head, 
                dim_feedforward=d_model*4, 
                dropout=0.1,
                batch_first=True
            ) for _ in range(n_layer)
        ])
        
        # Final LayerNorm & Head
        self.ln_f = nn.LayerNorm(d_model)
        self.head = nn.Linear(d_model, vocab_size, bias=False)
        
        self.apply(self._init_weights)

    def _init_weights(self, module):
        if isinstance(module, (nn.Linear, nn.Embedding)):
            module.weight.data.normal_(mean=0.0, std=0.02)
            if isinstance(module, nn.Linear) and module.bias is not None:
                module.bias.data.zero_()
        elif isinstance(module, nn.LayerNorm):
            module.bias.data.zero_()
            module.weight.data.fill_(1.0)

    def forward(self, idx, targets=None):
        b, t = idx.size()
        
        # Embeddings
        token_embeddings = self.token_embedding(idx) # (b, t, d_model)
        position_embeddings = self.position_embedding[:, :t, :] # (1, t, d_model)
        x = token_embeddings + position_embeddings
        
        # Transformer Layers
        x = self.blocks(x) # (b, t, d_model)
        x = self.ln_f(x)
        
        # Logits
        logits = self.head(x) # (b, t, vocab_size)

        loss = None
        if targets is not None:
            # Flatten for loss calculation
            logits = logits.view(-1, logits.size(-1))
            targets = targets.view(-1)
            loss = F.cross_entropy(logits, targets)

        return logits, loss

    def generate(self, idx, max_new_tokens):
        # 簡單的生成循環
        for _ in range(max_new_tokens):
            idx_cond = idx[:, -self.block_size:]
            logits, _ = self(idx_cond)
            logits = logits[:, -1, :] # 取最後一個時間步
            probs = F.softmax(logits, dim=-1)
            idx_next = torch.multinomial(probs, num_samples=1)
            idx = torch.cat((idx, idx_next), dim=1)
        return idx
