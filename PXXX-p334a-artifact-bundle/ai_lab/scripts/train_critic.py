import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import json
import os
import random
import numpy as np
import sys

# Add path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
from ai_lab.ai_models.neural_critic import NeuralCritic

class CriticDataset(Dataset):
    def __init__(self, real_data_path: str, synth_count: int = 5000):
        with open(real_data_path, 'r') as f:
            real_draws = json.load(f)
        
        self.samples = []
        self.labels = []
        
        # 1. Positive Samples (Actual History)
        for draw_nums in real_draws:
            vec = self._to_multi_hot(draw_nums)
            self.samples.append(vec)
            self.labels.append(1.0)
            
        # 2. Negative Samples (Unrealistic Sets)
        # Type A: Extreme Clusters
        for _ in range(synth_count // 2):
            zone = random.randint(0, 2)
            if zone == 0: nums = random.sample(range(1, 17), 6)
            elif zone == 1: nums = random.sample(range(17, 33), 6)
            else: nums = random.sample(range(33, 50), 6)
            self.samples.append(self._to_multi_hot(nums))
            self.labels.append(0.0)
            
        # Type B: Pure Random (Often contains natural patterns, weighted lower in logic but here as baseline)
        for _ in range(synth_count // 4):
            nums = random.sample(range(1, 50), 6)
            self.samples.append(self._to_multi_hot(nums))
            self.labels.append(0.0)

        # Type C: Extreme Sequences
        for i in range(1, 44, 5):
            nums = list(range(i, i+6))
            self.samples.append(self._to_multi_hot(nums))
            self.labels.append(0.0)

    def _to_multi_hot(self, nums):
        vec = np.zeros(50, dtype=np.float32)
        for n in nums:
            if 0 < n < 50: vec[n] = 1.0
        return vec

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        return torch.tensor(self.samples[idx]), torch.tensor([self.labels[idx]])

def train_critic():
    data_file = os.path.join(os.path.dirname(__file__), '../data/real_biglotto.json')
    device = torch.device("cpu")
    
    dataset = CriticDataset(data_file)
    loader = DataLoader(dataset, batch_size=32, shuffle=True)
    
    model = NeuralCritic().to(device)
    optimizer = optim.Adam(model.parameters(), lr=0.001)
    criterion = nn.BCELoss()
    
    epochs = 20
    print(f"Training Neural Critic to filter 'Unnatural' bets...")
    
    for epoch in range(epochs):
        model.train()
        total_loss = 0
        for x, y in loader:
            optimizer.zero_grad()
            pred = model(x)
            loss = criterion(pred, y)
            loss.backward()
            optimizer.step()
            total_loss += loss.item()
            
        if (epoch + 1) % 5 == 0:
            print(f"Epoch {epoch+1} | Loss: {total_loss / len(loader):.4f}")
            
    save_path = os.path.join(os.path.dirname(__file__), '../ai_models/neural_critic.pth')
    torch.save(model.state_dict(), save_path)
    print(f"Neural Critic saved to {save_path}")

if __name__ == "__main__":
    train_critic()
