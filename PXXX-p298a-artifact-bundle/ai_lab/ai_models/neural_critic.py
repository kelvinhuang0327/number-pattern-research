import torch
import torch.nn as nn
import torch.nn.functional as F

class NeuralCritic(nn.Module):
    """
    Neural Critic: Evaluates the 'Naturalness' of a specific combination.
    Input: Multi-hot vector (1, 50) representing numbers 1-49.
    Output: Fraud/Natural probability score.
    """
    def __init__(self):
        super(NeuralCritic, self).__init__()
        self.fc1 = nn.Linear(50, 64)
        self.fc2 = nn.Linear(64, 32)
        self.fc3 = nn.Linear(32, 1)
        self.dropout = nn.Dropout(0.2)
        
    def forward(self, x):
        # x is (batch, 50) multi-hot
        x = F.relu(self.fc1(x))
        x = self.dropout(x)
        x = F.relu(self.fc2(x))
        x = torch.sigmoid(self.fc3(x))
        return x

def get_critic_summary():
    model = NeuralCritic()
    return {
        "model_type": "Neural-Critic-V1",
        "description": "Natural Distribution Filter",
        "parameters": sum(p.numel() for p in model.parameters())
    }
