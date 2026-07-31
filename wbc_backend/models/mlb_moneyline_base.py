from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class MLBMoneylineBaseModel:
    weights: np.ndarray | None = None
    learning_rate: float = 0.05
    iterations: int = 1200
    l2: float = 1e-4

    def fit(self, X: np.ndarray, y: np.ndarray) -> "MLBMoneylineBaseModel":
        n, d = X.shape
        w = np.zeros(d, dtype=float)
        for _ in range(self.iterations):
            z = X @ w
            p = 1.0 / (1.0 + np.exp(-np.clip(z, -20, 20)))
            grad = (X.T @ (p - y)) / max(1, n) + self.l2 * w
            w -= self.learning_rate * grad
        self.weights = w
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if self.weights is None:
            raise ValueError("Base model is not trained")
        z = X @ self.weights
        return 1.0 / (1.0 + np.exp(-np.clip(z, -20, 20)))
