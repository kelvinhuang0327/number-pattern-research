import torch
import torch.nn as nn
import math
from typing import List, Dict

class HybridLotteryTransformer(nn.Module):
    """
    HybridLotteryTransformer: Combines sequence embeddings with statistical feature vectors.
    Input: 
      - x: (batch_size, seq_len, pick_count) - sequence of draws
      - s: (batch_size, seq_len, stat_dim) - statistical features per draw
    """
    
    def __init__(self, vocab_size=50, d_model=128, stat_dim=9, nhead=8, num_layers=4, dim_feedforward=512):
        super(HybridLotteryTransformer, self).__init__()
        self.d_model = d_model
        
        # 1. Number Embedding
        self.embedding = nn.Embedding(vocab_size, d_model)
        
        # 2. Statistical Feature Projector (Now 9 features)
        self.stat_projector = nn.Linear(stat_dim, d_model // 4)
        
        # 3. Combined Context Projector
        self.combined_projector = nn.Linear(d_model + (d_model // 4), d_model)
        
        # 4. LayerNorm for stability (Phase 10)
        self.norm = nn.LayerNorm(d_model)
        
        # 5. Dropout for regularization
        self.dropout = nn.Dropout(0.2)
        
        # Positional Encoding
        self.pos_encoder = nn.Parameter(torch.zeros(1, 1000, d_model))
        
        # Transformer Layers
        encoder_layers = nn.TransformerEncoderLayer(
            d_model=d_model, nhead=nhead, dim_feedforward=dim_feedforward, 
            dropout=0.2, batch_first=True
        )
        self.transformer_encoder = nn.TransformerEncoder(encoder_layers, num_layers=num_layers)
        
        # Output Head
        self.output_layer = nn.Linear(d_model, vocab_size)
        
    def forward(self, x, s):
        """
        x: (batch, seq, pick)
        s: (batch, seq, stat_dim)
        """
        batch_size, seq_len, pick_count = x.size()
        
        # Embed numbers and average
        embeds = self.embedding(x) # (batch, seq, pick, d_model)
        draw_embeds = embeds.mean(dim=2) # (batch, seq, d_model)
        
        # Project statistical features
        stat_embeds = torch.relu(self.stat_projector(s)) # (batch, seq, d_model // 4)
        
        # Concatenate and re-project to d_model
        combined = torch.cat([draw_embeds, stat_embeds], dim=2) # (batch, seq, d_model * 1.25)
        combined = self.combined_projector(combined) # (batch, seq, d_model)
        
        # Phase 10: Stability Norm
        combined = self.norm(combined)
        
        # Add Positional Encoding
        combined = combined + self.pos_encoder[:, :seq_len, :]
        
        # Transformer Pass
        out = self.transformer_encoder(combined) # (batch, seq, d_model)
        
        # Predict based on last draw state
        last_out = out[:, -1, :]
        logits = self.output_layer(last_out)
        return logits

def get_hybrid_summary():
    model = HybridLotteryTransformer()
    total_params = sum(p.numel() for p in model.parameters())
    return {
        "model_type": "HybridTransformer-V3",
        "parameters": total_params,
        "input_features": "Numbers + Stats(9)"
    }

if __name__ == "__main__":
    summary = get_hybrid_summary()
    print(f"Hybrid Model Initialized: {summary}")
    # Dummy pass
    x = torch.randint(1, 50, (1, 10, 6))
    s = torch.randn(1, 10, 9)
    model = HybridLotteryTransformer()
    output = model(x, s)
    print(f"Output Shape: {output.shape}")
