"""
Neural Network Win Probability Model

Multi-layer perceptron built with pure NumPy/SciPy so we don't require
PyTorch/TensorFlow as a hard dependency.
"""
from __future__ import annotations

import logging
import pickle
import time
from pathlib import Path

import numpy as np
from scipy.special import expit

from wbc_backend.config.settings import ModelConfig
from wbc_backend.domain.schemas import SubModelResult, TrainingResult
from wbc_backend.features.advanced import FEATURE_NAMES

logger = logging.getLogger(__name__)


class NeuralNetModel:
    """
    Minimal MLP with:
      - Configurable hidden layers
      - Dropout (training only)
      - Adam-style optimiser (simplified)
      - Binary cross-entropy loss
    """

    def __init__(self, config: ModelConfig | None = None):
        self.config = config or ModelConfig()
        nn_p = self.config.nn_params
        self.hidden_layers: list[int] = nn_p.get("hidden_layers", [128, 64, 32])
        self.dropout: float = nn_p.get("dropout", 0.3)
        self.lr: float = nn_p.get("learning_rate", 0.001)
        self.epochs: int = nn_p.get("epochs", 100)
        self.batch_size: int = nn_p.get("batch_size", 32)
        self.feature_names = FEATURE_NAMES
        self.weights: list[np.ndarray] = []
        self.biases: list[np.ndarray] = []
        self.x_mean: np.ndarray | None = None
        self.x_std: np.ndarray | None = None
        self.artifact_path = Path("data/wbc_backend/artifacts/nn_model.pkl")
        self._fitted = False

    def _expected_feature_count(self) -> int:
        return len(self.feature_names)

    def _init_weights(self, input_dim: int):
        """He-initialisation for ReLU layers, Xavier for output."""
        dims = [input_dim] + self.hidden_layers + [1]
        self.weights = []
        self.biases = []
        rng = np.random.default_rng(42)
        for i in range(len(dims) - 1):
            fan_in = dims[i]
            fan_out = dims[i + 1]
            if i < len(dims) - 2:  # hidden → ReLU
                std = np.sqrt(2.0 / fan_in)
            else:  # output → sigmoid
                std = np.sqrt(1.0 / fan_in)
            self.weights.append(rng.normal(0, std, (fan_in, fan_out)).astype(np.float64))
            self.biases.append(np.zeros(fan_out, dtype=np.float64))

    def _forward(self, X: np.ndarray, training: bool = False) -> np.ndarray:
        h = X
        for i in range(len(self.weights) - 1):
            h = h @ self.weights[i] + self.biases[i]
            h = np.maximum(0, h)  # ReLU
            if training and self.dropout > 0:
                mask = (np.random.rand(*h.shape) > self.dropout).astype(float)
                h = h * mask / (1 - self.dropout)
        # Output layer
        logits = h @ self.weights[-1] + self.biases[-1]
        return logits.ravel()

    def train(self, X: np.ndarray, y: np.ndarray) -> TrainingResult:
        start = time.time()
        n, d = X.shape

        # Normalise
        self.x_mean = X.mean(axis=0)
        self.x_std = np.where(X.std(axis=0) < 1e-8, 1.0, X.std(axis=0))
        Xn = (X - self.x_mean) / self.x_std

        self._init_weights(d)

        # Training loop with mini-batch SGD
        rng = np.random.default_rng(42)
        best_loss = float("inf")

        for _ in range(self.epochs):
            indices = rng.permutation(n)
            epoch_loss = 0.0
            batches = 0

            for start_idx in range(0, n, self.batch_size):
                batch_idx = indices[start_idx: start_idx + self.batch_size]
                Xb = Xn[batch_idx]
                yb = y[batch_idx]

                # Forward
                logits = self._forward(Xb, training=True)
                probs = expit(logits)
                probs = np.clip(probs, 1e-7, 1 - 1e-7)

                # Loss
                loss = -np.mean(yb * np.log(probs) + (1 - yb) * np.log(1 - probs))
                epoch_loss += loss
                batches += 1

                # Backward (numerical gradient approximation for simplicity)
                grad_logits = (probs - yb) / len(yb)
                self._backward_step(Xb, grad_logits)

            avg_loss = epoch_loss / max(batches, 1)
            if avg_loss < best_loss:
                best_loss = avg_loss

        self._fitted = True

        # Metrics
        logits = self._forward(Xn, training=False)
        probs = expit(logits)
        probs = np.clip(probs, 1e-7, 1 - 1e-7)
        preds = (probs >= 0.5).astype(int)

        accuracy = float(np.mean(preds == y))
        logloss = float(-np.mean(y * np.log(probs) + (1 - y) * np.log(1 - probs)))
        brier = float(np.mean((probs - y) ** 2))

        self._save()
        elapsed = time.time() - start

        logger.info("NeuralNet trained: acc=%.4f, logloss=%.4f, brier=%.4f",
                     accuracy, logloss, brier)

        return TrainingResult(
            model_name="neural_net",
            accuracy=round(accuracy, 4),
            logloss=round(logloss, 4),
            brier_score=round(brier, 4),
            training_time_seconds=round(elapsed, 1),
            n_samples=len(y),
        )

    def _backward_step(self, X: np.ndarray, grad_output: np.ndarray):
        """Simplified gradient descent on the last layer only (for speed)."""
        # Full backprop through all layers
        h_cache = [X]
        h = X
        for i in range(len(self.weights) - 1):
            h = h @ self.weights[i] + self.biases[i]
            h = np.maximum(0, h)
            h_cache.append(h)

        # Output gradient
        dW_out = h_cache[-1].T @ grad_output.reshape(-1, 1)
        db_out = grad_output.sum()
        self.weights[-1] -= self.lr * dW_out
        self.biases[-1] -= self.lr * db_out

        # Back-propagate through hidden layers
        delta = grad_output.reshape(-1, 1) @ self.weights[-1].T
        for i in range(len(self.weights) - 2, -1, -1):
            delta = delta * (h_cache[i + 1] > 0).astype(float)  # ReLU derivative
            dW = h_cache[i].T @ delta
            db = delta.sum(axis=0)
            # L2 regularisation
            dW += 0.001 * self.weights[i]
            self.weights[i] -= self.lr * dW
            self.biases[i] -= self.lr * db
            if i > 0:
                delta = delta @ self.weights[i].T

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if not self._fitted:
            self._load()
        if not self._fitted:
            return np.full(len(X), 0.5)

        Xn = (X - self.x_mean) / self.x_std
        logits = self._forward(Xn, training=False)
        return expit(logits)

    def predict_single(self, feature_dict: dict[str, float]) -> SubModelResult:
        features = np.array([[feature_dict.get(f, 0.0) for f in self.feature_names]])
        prob = float(self.predict_proba(features)[0])

        return SubModelResult(
            model_name="neural_net",
            home_win_prob=round(prob, 4),
            away_win_prob=round(1.0 - prob, 4),
            confidence=0.65 if self._fitted else 0.3,
            diagnostics={"nn_raw_prob": round(prob, 4)},
        )

    def _save(self):
        self.artifact_path.parent.mkdir(parents=True, exist_ok=True)
        state = {
            "weights": self.weights, "biases": self.biases,
            "x_mean": self.x_mean, "x_std": self.x_std,
            "feature_count": self._expected_feature_count(),
            "feature_names": list(self.feature_names),
        }
        with open(self.artifact_path, "wb") as f:
            pickle.dump(state, f)

    def _load(self):
        if self.artifact_path.exists():
            try:
                with open(self.artifact_path, "rb") as f:
                    state = pickle.load(f)
                saved_count = state.get("feature_count")
                if saved_count is None and state.get("x_mean") is not None:
                    saved_count = int(len(state["x_mean"]))
                if saved_count is not None and saved_count != self._expected_feature_count():
                    logger.info(
                        "Ignoring stale NN artifact: features=%s expected=%s",
                        saved_count,
                        self._expected_feature_count(),
                    )
                    self.weights = []
                    self.biases = []
                    self.x_mean = None
                    self.x_std = None
                    self._fitted = False
                    return
                self.weights = state["weights"]
                self.biases = state["biases"]
                self.x_mean = state["x_mean"]
                self.x_std = state["x_std"]
                self._fitted = True
            except Exception as e:
                logger.warning("Failed to load NN model: %s", e)
