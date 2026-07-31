import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import json
import os
import sys
from typing import List

# Add parent dir to path to import models
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from ai_models.transformer_v1 import LotteryTransformer

class LotteryDataset(Dataset):
    """
    Dataset for lottery sequences.
    Converts list of draws into (context, target) pairs.
    """
    def __init__(self, data_path: str, seq_len: int = 10):
        with open(data_path, 'r') as f:
            self.draws = json.load(f)
        self.seq_len = seq_len
        
    def __len__(self):
        return len(self.draws) - self.seq_len
        
    def __getitem__(self, idx):
        # Input: seq_len draws
        # Target: The FIRST number of the next draw (simplified for prototype)
        # Note: A real implementation would predict the set or use multi-label loss
        context = torch.tensor(self.draws[idx:idx+self.seq_len], dtype=torch.long)
        target_draw = self.draws[idx+self.seq_len]
        # For now, let's predict the presence of numbers (multi-label)
        target = torch.zeros(50)
        for num in target_draw:
            if num < 50:
                target[num] = 1.0
        return context, target

def train():
    # 1. Configuration
    data_file = os.path.join(os.path.dirname(__file__), '../data/temporal_50k.json')
    if not os.path.exists(data_file):
        print(f"Error: Data file {data_file} not found. Run synthetic_gen.py first.")
        return

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")

    # 2. Data Loading
    dataset = LotteryDataset(data_file)
    dataloader = DataLoader(dataset, batch_size=64, shuffle=True)

    # 3. Model Initialization
    model = LotteryTransformer().to(device)
    criterion = nn.BCEWithLogitsLoss() # Good for multi-label (presence of numbers)
    optimizer = optim.Adam(model.parameters(), lr=0.001)

    # 4. Training Loop (Short run for prototype)
    epochs = 3
    print(f"Starting training on {len(dataset)} sequences for {epochs} epochs...")
    
    model.train()
    for epoch in range(epochs):
        total_loss = 0
        for i, (context, target) in enumerate(dataloader):
            context, target = context.to(device), target.to(device)
            
            optimizer.zero_grad()
            logits = model(context)
            loss = criterion(logits, target)
            loss.backward()
            optimizer.step()
            
            total_loss += loss.item()
            
            if i % 100 == 0:
                print(f"Epoch {epoch+1}/{epochs} | Step {i} | Loss: {loss.item():.4f}")
                
        print(f"Epoch {epoch+1} Complete. Average Loss: {total_loss / len(dataloader):.4f}")

    # 5. Save Model
    save_path = os.path.join(os.path.dirname(__file__), '../models/pretrained_v1.pth')
    torch.save(model.state_dict(), save_path)
    print(f"Model saved to {save_path}")

if __name__ == "__main__":
    train()
