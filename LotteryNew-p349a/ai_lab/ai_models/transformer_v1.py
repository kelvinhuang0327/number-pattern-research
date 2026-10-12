import torch
import torch.nn as nn
import math
from typing import List, Dict

class LotteryTransformer(nn.Module):
    """
    LotteryTransformer: A decoder-only transformer for lottery number prediction.
    Input: Sequence of draws (each draw is a sorted list of numbers).
    Output: Probability distribution for each possible number [1-49].
    """
    
    def __init__(self, vocab_size=50, d_model=128, nhead=8, num_layers=4, dim_feedforward=512):
        super(LotteryTransformer, self).__init__()
        self.d_model = d_model
        
        # Embedding for 1-49 numbers (0 is padding)
        self.embedding = nn.Embedding(vocab_size, d_model)
        
        # Positional Encoding to retain sequence order
        self.pos_encoder = nn.Parameter(torch.zeros(1, 1000, d_model)) # Max sequence length 1000
        
        # Transformer Layers
        encoder_layers = nn.TransformerEncoderLayer(d_model=d_model, nhead=nhead, dim_feedforward=dim_feedforward, batch_first=True)
        self.transformer_encoder = nn.TransformerEncoder(encoder_layers, num_layers=num_layers)
        
        # Output Head: Map latent space to number probabilities
        self.output_layer = nn.Linear(d_model, vocab_size)
        
    def forward(self, x):
        """
        x: (batch_size, seq_len, pick_count) - sequence of draws
        """
        # Flatten and embed: (batch_size, seq_len, pick_count) -> (batch_size, seq_len, pick_count, d_model)
        # We simplify by averaging the embeddings of the numbers within a single draw
        batch_size, seq_len, pick_count = x.size()
        
        # x is long tensor: [batch, seq, pick]
        embeds = self.embedding(x) # (batch, seq, pick, d_model)
        
        # Average number embeddings to get 'draw embedding'
        draw_embeds = embeds.mean(dim=2) # (batch, seq, d_model)
        
        # Add Positional Encoding
        draw_embeds = draw_embeds + self.pos_encoder[:, :seq_len, :]
        
        # Transformer Pass
        out = self.transformer_encoder(draw_embeds) # (batch, seq, d_model)
        
        # Pool/Take last output: (batch, d_model)
        last_out = out[:, -1, :]
        
        # Predict: (batch, vocab_size)
        logits = self.output_layer(last_out)
        return logits

def get_model_summary():
    model = LotteryTransformer()
    total_params = sum(p.numel() for p in model.parameters())
    return {
        "model_type": "LotteryTransformer-V1",
        "parameters": total_params,
        "d_model": 128,
        "nhead": 8
    }

if __name__ == "__main__":
    # Test Scaffolding
    try:
        summary = get_model_summary()
        print(f"Model Initialized: {summary}")
        # Dummy forward pass
        dummy_input = torch.randint(1, 50, (1, 10, 6)) # 1 batch, 10 draws, 6 numbers each
        model = LotteryTransformer()
        output = model(dummy_input)
        print(f"Output Head Shape: {output.shape} (Matches vocab_size)")
    except Exception as e:
        print(f"Scaffolding Test Failed: {e}")
