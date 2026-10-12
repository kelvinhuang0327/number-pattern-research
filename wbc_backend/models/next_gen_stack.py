"""
Next-Gen Model Stack — Meta Learner & Online Learning
======================================================
Institutional-grade model ensemble upgrade:
  1. Meta Learner — learns optimal model combination from data
  2. Bayesian Ensemble — full posterior weight distribution
  3. Dynamic Weight Learning — time-varying optimal blend
  4. Online Learning Model — incremental SGD for real-time adaptation

Replaces the hand-tuned stacking model with data-driven approaches.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field


# ─── Data Structures ─────────────────────────────────────────────────────────

@dataclass
class MetaPrediction:
    """Output from the meta-learner."""
    home_win_prob: float
    away_win_prob: float
    confidence: float
    model_weights: dict[str, float]
    strategy: str
    diagnostics: dict[str, float] = field(default_factory=dict)


@dataclass
class OnlineState:
    """Persistent state for online learning model."""
    weights: list[float] = field(default_factory=list)
    bias: float = 0.0
    learning_rate: float = 0.01
    n_updates: int = 0
    running_loss: float = 0.693  # initial log-loss


# ─── 1. Meta Learner (Stacking with Logistic + Feature Engineering) ─────────

class MetaLearner:
    """
    Second-level learner that takes sub-model predictions + context
    features and outputs calibrated probabilities.

    Uses logistic regression with L2 regularisation, trained via
    closed-form iteratively reweighted least squares (IRLS) or
    simple gradient descent.
    """

    def __init__(self, model_names: list[str], context_features: int = 5):
        self.model_names = model_names
        self.n_models = len(model_names)
        self.n_context = context_features
        self.n_features = self.n_models + self.n_context + self.n_models  # models + context + model² terms
        # Initialise weights: uniform for models, zero for context/interaction
        self.weights = [1.0 / self.n_models] * self.n_models
        self.weights += [0.0] * self.n_context
        self.weights += [0.0] * self.n_models  # quadratic model terms
        self.bias = 0.0
        self.reg_lambda = 0.01
        self.fitted = False

    def _build_features(
        self,
        sub_preds: dict[str, float],
        context: dict[str, float],
    ) -> list[float]:
        """
        Build meta-feature vector:
          [model_1_pred, ..., model_n_pred,
           ctx_1, ..., ctx_k,
           model_1²,  ..., model_n²]
        """
        features = []

        # Model predictions (home win prob)
        for name in self.model_names:
            features.append(sub_preds.get(name, 0.5))

        # Context (normalised)
        ctx_keys = ["elo_diff", "rsi_diff", "is_neutral", "round_importance", "steam_move"]
        for key in ctx_keys[:self.n_context]:
            features.append(context.get(key, 0.0))

        # Quadratic terms (capture non-linear model interactions)
        for name in self.model_names:
            p = sub_preds.get(name, 0.5)
            features.append(p * p)

        return features

    def fit(
        self,
        sub_predictions: list[dict[str, float]],
        contexts: list[dict[str, float]],
        targets: list[int],
        learning_rate: float = 0.01,
        epochs: int = 100,
    ):
        """
        Train the meta-learner via mini-batch gradient descent.
        """
        n = len(targets)
        if n < 10:
            return

        X = [self._build_features(sp, ctx) for sp, ctx in zip(sub_predictions, contexts)]
        nf = len(X[0])

        # Ensure weights match feature count
        if len(self.weights) != nf:
            self.weights = [0.1] * nf
            self.bias = 0.0

        for epoch in range(epochs):
            # Shuffle
            indices = list(range(n))
            random.shuffle(indices)

            total_loss = 0.0
            for idx in indices:
                x = X[idx]
                y = targets[idx]

                # Forward
                logit = self.bias + sum(w * xi for w, xi in zip(self.weights, x))
                pred = _sigmoid(logit)

                # Log-loss
                p = max(min(pred, 0.999), 0.001)
                loss = -(y * math.log(p) + (1 - y) * math.log(1 - p))
                total_loss += loss

                # Gradient
                error = pred - y
                for j in range(nf):
                    grad = error * x[j] + self.reg_lambda * self.weights[j]
                    self.weights[j] -= learning_rate * grad
                self.bias -= learning_rate * error

            avg_loss = total_loss / n
            # Early stopping
            if epoch > 20 and avg_loss < 0.60:
                break

        self.fitted = True

    def predict(
        self,
        sub_preds: dict[str, float],
        context: dict[str, float],
    ) -> MetaPrediction:
        """
        Generate calibrated prediction from sub-model outputs.
        """
        features = self._build_features(sub_preds, context)

        if self.fitted and len(self.weights) == len(features):
            logit = self.bias + sum(w * xi for w, xi in zip(self.weights, features))
            home_wp = _sigmoid(logit)
        else:
            # Fallback: simple weighted average
            total = 0.0
            for name in self.model_names:
                total += sub_preds.get(name, 0.5)
            home_wp = total / max(len(self.model_names), 1)

        # Confidence from model agreement
        preds = [sub_preds.get(n, 0.5) for n in self.model_names]
        std = _std(preds)
        confidence = max(0.0, 1.0 - std * 4)  # low std → high confidence

        # Extract effective model weights
        model_weights = {}
        for i, name in enumerate(self.model_names):
            if i < len(self.weights):
                model_weights[name] = abs(self.weights[i])

        # Normalise weights
        total_w = sum(model_weights.values()) or 1
        model_weights = {k: v / total_w for k, v in model_weights.items()}

        return MetaPrediction(
            home_win_prob=round(home_wp, 4),
            away_win_prob=round(1.0 - home_wp, 4),
            confidence=round(confidence, 4),
            model_weights=model_weights,
            strategy="META_LEARNER",
            diagnostics={
                "logit": round(logit if self.fitted else 0.0, 4),
                "n_features": len(features),
                "model_std": round(std, 4),
            },
        )


# ─── 2. Bayesian Ensemble (Full Posterior) ───────────────────────────────────

class BayesianEnsemble:
    """
    Maintains a posterior distribution over model weights using
    Dirichlet updates.

    Prior: Dirichlet(α₁, ..., αₙ)  — uniform
    Update: αᵢ += reward_i after each game
    Posterior: E[wᵢ] = αᵢ / Σα
    """

    def __init__(self, model_names: list[str], prior_strength: float = 10.0):
        self.model_names = model_names
        # Uniform Dirichlet prior: all αᵢ = prior_strength / n
        self.alphas = {
            name: prior_strength / len(model_names) for name in model_names
        }
        self.n_updates = 0

    def update(
        self,
        model_predictions: dict[str, float],
        actual: int,
    ):
        """
        Update posterior after observing a game result.

        Reward = 1 - (pred - actual)² (Brier-like reward).
        Better predictions → higher alpha → higher posterior weight.
        """
        for name, pred in model_predictions.items():
            if name not in self.alphas:
                continue
            brier = (pred - actual) ** 2
            reward = max(0.01, 1.0 - brier)
            self.alphas[name] += reward

        self.n_updates += 1

    def get_weights(self) -> dict[str, float]:
        """Current posterior mean weights (E[Dirichlet])."""
        total = sum(self.alphas.values())
        return {k: v / total for k, v in self.alphas.items()}

    def predict(
        self,
        sub_preds: dict[str, float],
    ) -> MetaPrediction:
        """Posterior-weighted ensemble prediction."""
        weights = self.get_weights()
        home_wp = sum(
            weights.get(name, 0) * sub_preds.get(name, 0.5)
            for name in self.model_names
        )
        home_wp = max(0.01, min(0.99, home_wp))

        # Confidence from Dirichlet concentration
        total_alpha = sum(self.alphas.values())
        concentration = total_alpha / len(self.model_names)
        confidence = min(1.0, concentration / 50.0)

        return MetaPrediction(
            home_win_prob=round(home_wp, 4),
            away_win_prob=round(1.0 - home_wp, 4),
            confidence=round(confidence, 4),
            model_weights=weights,
            strategy="BAYESIAN_ENSEMBLE",
            diagnostics={
                "total_alpha": round(total_alpha, 2),
                "n_updates": self.n_updates,
            },
        )


# ─── 3. Dynamic Weight Learner (Exponentially Weighted) ─────────────────────

class DynamicWeightLearner:
    """
    Time-varying model weights using exponentially weighted moving
    average (EWMA) of model accuracy.

    Recent performance matters more than historical performance,
    enabling rapid adaptation to regime changes.
    """

    def __init__(
        self,
        model_names: list[str],
        decay: float = 0.95,
        min_weight: float = 0.03,
    ):
        self.model_names = model_names
        self.decay = decay
        self.min_weight = min_weight
        self.ewma_accuracy: dict[str, float] = {name: 0.5 for name in model_names}
        self.n_updates = 0

    def update(
        self,
        model_predictions: dict[str, float],
        actual: int,
    ):
        """Update EWMA accuracy after observing result."""
        for name, pred in model_predictions.items():
            if name not in self.ewma_accuracy:
                continue
            # Accuracy: 1 - |pred - actual|
            acc = 1.0 - abs(pred - actual)
            self.ewma_accuracy[name] = (
                self.decay * self.ewma_accuracy[name] +
                (1 - self.decay) * acc
            )
        self.n_updates += 1

    def get_weights(self) -> dict[str, float]:
        """Convert EWMA accuracy to normalised weights."""
        # Softmax-like transformation
        scores = {}
        for name in self.model_names:
            acc = self.ewma_accuracy.get(name, 0.5)
            scores[name] = max(self.min_weight, math.exp(acc * 3))

        total = sum(scores.values())
        return {k: v / total for k, v in scores.items()}

    def predict(self, sub_preds: dict[str, float]) -> MetaPrediction:
        """Dynamic-weight prediction."""
        weights = self.get_weights()
        home_wp = sum(
            weights.get(name, 0) * sub_preds.get(name, 0.5)
            for name in self.model_names
        )
        home_wp = max(0.01, min(0.99, home_wp))

        preds_list = [sub_preds.get(n, 0.5) for n in self.model_names]
        confidence = max(0.0, 1.0 - _std(preds_list) * 4)

        return MetaPrediction(
            home_win_prob=round(home_wp, 4),
            away_win_prob=round(1.0 - home_wp, 4),
            confidence=round(confidence, 4),
            model_weights=weights,
            strategy="DYNAMIC_EWMA",
            diagnostics={
                "decay": self.decay,
                "n_updates": self.n_updates,
            },
        )


# ─── 4. Online Learning Model (Incremental SGD) ─────────────────────────────

class OnlineLearningModel:
    """
    Online logistic regression with:
      - Incremental SGD (no full retraining needed)
      - Adaptive learning rate (1/sqrt(t))
      - L2 regularisation
      - Prediction caching for speed

    Learns directly from (features, outcome) pairs as they arrive.
    """

    def __init__(
        self,
        n_features: int,
        initial_lr: float = 0.05,
        reg_lambda: float = 0.001,
    ):
        self.n_features = n_features
        self.weights = [0.0] * n_features
        self.bias = 0.0
        self.initial_lr = initial_lr
        self.reg_lambda = reg_lambda
        self.n_updates = 0
        self.running_loss = 0.693

    @property
    def learning_rate(self) -> float:
        """Adaptive learning rate: lr_0 / sqrt(1 + t)."""
        return self.initial_lr / math.sqrt(1 + self.n_updates)

    def predict_proba(self, features: list[float]) -> float:
        """Predict P(home_win) from feature vector."""
        if len(features) != self.n_features:
            return 0.5

        logit = self.bias + sum(
            w * x for w, x in zip(self.weights, features)
        )
        return _sigmoid(logit)

    def update(self, features: list[float], actual: int):
        """
        Single-step SGD update.

        Parameters
        ----------
        features : feature vector
        actual : 1 if home won, 0 otherwise
        """
        if len(features) != self.n_features:
            return

        pred = self.predict_proba(features)
        error = pred - actual
        lr = self.learning_rate

        for j in range(self.n_features):
            grad = error * features[j] + self.reg_lambda * self.weights[j]
            self.weights[j] -= lr * grad

        self.bias -= lr * error
        self.n_updates += 1

        # Running loss (for monitoring)
        p = max(min(pred, 0.999), 0.001)
        loss = -(actual * math.log(p) + (1 - actual) * math.log(1 - p))
        self.running_loss = 0.95 * self.running_loss + 0.05 * loss

    def get_state(self) -> OnlineState:
        return OnlineState(
            weights=self.weights[:],
            bias=self.bias,
            learning_rate=self.learning_rate,
            n_updates=self.n_updates,
            running_loss=self.running_loss,
        )

    def load_state(self, state: OnlineState):
        self.weights = state.weights[:]
        self.bias = state.bias
        self.n_updates = state.n_updates
        self.running_loss = state.running_loss


# ─── 5. Ensemble of Ensembles (Super-Ensemble) ──────────────────────────────

class SuperEnsemble:
    """
    Top-level ensemble that selects or blends the best meta-strategy
    based on recent performance.

    Strategies:
      - meta_learner: trained logistic stacking
      - bayesian: Dirichlet posterior
      - dynamic: EWMA weights
      - consensus: simple average

    The super-ensemble uses a simple multi-armed bandit (UCB1)
    to allocate weight to each meta-strategy.
    """

    def __init__(self, model_names: list[str]):
        self.model_names = model_names
        self.meta = MetaLearner(model_names)
        self.bayesian = BayesianEnsemble(model_names)
        self.dynamic = DynamicWeightLearner(model_names)

        # UCB1 tracking
        self.strategy_names = ["meta", "bayesian", "dynamic", "consensus"]
        self.rewards: dict[str, list[float]] = {s: [] for s in self.strategy_names}
        self.n_plays: dict[str, int] = {s: 0 for s in self.strategy_names}

    def predict(
        self,
        sub_preds: dict[str, float],
        context: dict[str, float] | None = None,
    ) -> MetaPrediction:
        """
        Generate prediction using UCB1-selected strategy.
        """
        context = context or {}

        # Get predictions from all strategies
        meta_pred = self.meta.predict(sub_preds, context)
        bayes_pred = self.bayesian.predict(sub_preds)
        dyn_pred = self.dynamic.predict(sub_preds)

        # Consensus
        all_preds = list(sub_preds.values())
        consensus_hp = sum(all_preds) / max(len(all_preds), 1)

        strategy_outputs = {
            "meta": meta_pred.home_win_prob,
            "bayesian": bayes_pred.home_win_prob,
            "dynamic": dyn_pred.home_win_prob,
            "consensus": consensus_hp,
        }

        # UCB1 selection (or blend if insufficient data)
        total_plays = sum(self.n_plays.values())

        if total_plays < len(self.strategy_names) * 5:
            # Not enough data — blend equally
            home_wp = sum(strategy_outputs.values()) / len(strategy_outputs)
            strategy = "SUPER_BLEND"
            weights = {k: 1.0 / len(strategy_outputs) for k in strategy_outputs}
        else:
            # UCB1 selection
            ucb_scores = {}
            for s_name in self.strategy_names:
                n = max(self.n_plays[s_name], 1)
                avg_reward = sum(self.rewards[s_name][-50:]) / max(len(self.rewards[s_name][-50:]), 1)
                ucb = avg_reward + math.sqrt(2 * math.log(total_plays) / n)
                ucb_scores[s_name] = ucb

            # Softmax-weighted blend (not pure argmax ─ reduces variance)
            max_ucb = max(ucb_scores.values())
            exp_scores = {k: math.exp((v - max_ucb) * 5) for k, v in ucb_scores.items()}
            total_exp = sum(exp_scores.values())
            weights = {k: v / total_exp for k, v in exp_scores.items()}

            home_wp = sum(
                weights[k] * strategy_outputs[k] for k in self.strategy_names
            )
            strategy = "SUPER_UCB1"

        home_wp = max(0.01, min(0.99, home_wp))

        return MetaPrediction(
            home_win_prob=round(home_wp, 4),
            away_win_prob=round(1.0 - home_wp, 4),
            confidence=round(meta_pred.confidence, 4),
            model_weights=weights,
            strategy=strategy,
            diagnostics={
                "meta_hp": meta_pred.home_win_prob,
                "bayes_hp": bayes_pred.home_win_prob,
                "dynamic_hp": dyn_pred.home_win_prob,
                "consensus_hp": round(consensus_hp, 4),
            },
        )

    def update(self, model_predictions: dict[str, float], actual: int):
        """Update all sub-strategies after observing result."""
        self.bayesian.update(model_predictions, actual)
        self.dynamic.update(model_predictions, actual)

        # Compute rewards for UCB1
        for s_name in self.strategy_names:
            if s_name == "meta":
                pred = self.meta.predict(model_predictions, {}).home_win_prob
            elif s_name == "bayesian":
                pred = self.bayesian.predict(model_predictions).home_win_prob
            elif s_name == "dynamic":
                pred = self.dynamic.predict(model_predictions).home_win_prob
            else:
                pred = sum(model_predictions.values()) / max(len(model_predictions), 1)

            # Reward = 1 - Brier
            reward = 1.0 - (pred - actual) ** 2
            self.rewards[s_name].append(reward)
            self.n_plays[s_name] += 1


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _sigmoid(x: float) -> float:
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    ez = math.exp(x)
    return ez / (1.0 + ez)


def _std(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    var = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    return math.sqrt(max(var, 0))
