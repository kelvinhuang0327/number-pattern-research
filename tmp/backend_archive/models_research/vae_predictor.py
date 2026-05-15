import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

class VAE(nn.Module):
    def __init__(self, input_dim=49, latent_dim=10):
        super(VAE, self).__init__()
        self.input_dim = input_dim
        
        # Encoder
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, 32),
            nn.ReLU(),
            nn.Linear(32, 16),
            nn.ReLU()
        )
        self.fc_mu = nn.Linear(16, latent_dim)
        self.fc_logvar = nn.Linear(16, latent_dim)
        
        # Decoder
        self.decoder = nn.Sequential(
            nn.Linear(latent_dim, 16),
            nn.ReLU(),
            nn.Linear(16, 32),
            nn.ReLU(),
            nn.Linear(32, input_dim),
            nn.Sigmoid()
        )

    def encode(self, x):
        h = self.encoder(x)
        return self.fc_mu(h), self.fc_logvar(h)

    def reparameterize(self, mu, logvar):
        std = torch.exp(0.5 * logvar)
        eps = torch.randn_like(std)
        return mu + eps * std

    def decode(self, z):
        return self.decoder(z)

    def forward(self, x):
        mu, logvar = self.encode(x)
        z = self.reparameterize(mu, logvar)
        return self.decode(z), mu, logvar

class VAEPredictor:
    def __init__(self, max_number=49, latent_dim=10):
        self.max_number = max_number
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = VAE(input_dim=max_number, latent_dim=latent_dim).to(self.device)
        self.optimizer = optim.Adam(self.model.parameters(), lr=1e-3)

    def _to_one_hot_sum(self, numbers: List[int]) -> torch.Tensor:
        """將一組號碼轉換為 Multi-hot 向量"""
        vec = torch.zeros(self.max_number)
        for n in numbers:
            if 1 <= n <= self.max_number:
                vec[n-1] = 1.0
        return vec

    def train(self, history: List[Dict], epochs=50):
        self.model.train()
        data = [self._to_one_hot_sum(d['numbers']) for d in history]
        if not data: return
        
        loader = torch.utils.data.DataLoader(data, batch_size=32, shuffle=True)
        
        for epoch in range(epochs):
            total_loss = 0
            for batch in loader:
                batch = batch.to(self.device)
                self.optimizer.zero_grad()
                
                recon_x, mu, logvar = self.model(batch)
                
                # Loss = Binary Cross Entropy + KL Divergence
                BCE = nn.functional.binary_cross_entropy(recon_x, batch, reduction='sum')
                KLD = -0.5 * torch.sum(1 + logvar - mu.pow(2) - logvar.exp())
                
                loss = BCE + KLD
                loss.backward()
                self.optimizer.step()
                total_loss += loss.item()
            
            if (epoch + 1) % 10 == 0:
                logger.debug(f"VAE Epoch {epoch+1}, Loss: {total_loss/len(data):.4f}")

    def get_latent_scores(self, min_number=1) -> np.ndarray:
        """
        利用解碼器生成每個位置的「可能性」分數
        或者從潛在空間採樣生成分數
        """
        self.model.eval()
        with torch.no_grad():
            # 從標準正態分佈採樣 N 個點，取平均解碼結果
            z = torch.randn(100, self.model.fc_mu.out_features).to(self.device)
            samples = self.model.decode(z)
            mean_probs = torch.mean(samples, dim=0).cpu().numpy()
            return mean_probs

    def predict(self, history: List[Dict], lottery_rules: Dict, epochs: int = 50) -> Dict:
        """整合預測介面"""
        if epochs > 0:
            self.train(history, epochs=epochs)
        probs = self.get_latent_scores()
        
        # 轉換為排名號碼
        indices = np.argsort(probs)[::-1]
        pick_count = lottery_rules.get('pickCount', 6)
        top_numbers = [(int(i) + 1) for i in indices[:pick_count]]
        
        return {
            'numbers': top_numbers,
            'probabilities': probs.tolist(),
            'confidence': 0.6,
            'method': 'VAE_Latent_Distribution'
        }
