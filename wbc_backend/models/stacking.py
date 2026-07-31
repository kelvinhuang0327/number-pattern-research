"""
Stacking Meta-Learner — § 二 Stacking 融合模型

Learns optimal weights for combining sub-model predictions
using logistic regression on cross-validated holdout predictions.

optimize_model_weights() runs the full stacking pipeline.
"""
from __future__ import annotations

import logging
import pickle
from pathlib import Path

import numpy as np
from scipy.optimize import minimize
from scipy.special import expit

from wbc_backend.domain.schemas import SubModelResult
from wbc_backend.intelligence.regime_classifier import RegimeClassifier

logger = logging.getLogger(__name__)


class StackingModel:
    """
    Second-level meta-learner that combines base model predictions.

    Uses L-BFGS-B optimised logistic regression with L2 regularisation
    to learn the optimal blending weights.
    """

    def __init__(self):
        self.weights: np.ndarray | None = None
        self.bias: float = 0.0
        self.model_names: list[str] = []
        self.artifact_path = Path("data/wbc_backend/artifacts/stacking_model.pkl")

    def fit(
        self,
        base_predictions: dict[str, np.ndarray],
        y: np.ndarray,
    ) -> dict[str, float]:
        """
        Learn stacking weights from base model predictions.

        Parameters
        ----------
        base_predictions : dict
            {model_name: array of P(home_win) for each sample}
        y : ndarray
            Ground truth (1=home_win, 0=away_win)

        Returns
        -------
        dict : Learned weights per model
        """
        self.model_names = sorted(base_predictions.keys())
        X = np.column_stack([base_predictions[name] for name in self.model_names])
        n, k = X.shape

        # Normalise inputs (logit transform)
        X_logit = np.log(np.clip(X, 1e-6, 1 - 1e-6) / (1 - np.clip(X, 1e-6, 1 - 1e-6)))

        def loss(params):
            w = params[:k]
            b = params[k]
            logits = X_logit @ w + b
            p = expit(logits)
            p = np.clip(p, 1e-7, 1 - 1e-7)
            bce = -np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))
            reg = 0.01 * np.sum(w ** 2)
            return bce + reg

        init = np.zeros(k + 1)
        init[:k] = 1.0 / k  # Equal initial weights
        result = minimize(loss, init, method="L-BFGS-B")

        self.weights = result.x[:k]
        self.bias = float(result.x[k])

        # Normalise weights to sum to 1 (for interpretability)
        weight_dict = {}
        abs_sum = np.abs(self.weights).sum()
        for name, w in zip(self.model_names, self.weights):
            weight_dict[name] = round(float(w / abs_sum if abs_sum > 0 else 1.0 / k), 4)

        self._save()
        logger.info("Stacking weights learned: %s", weight_dict)
        return weight_dict

    def predict(self, sub_results: list[SubModelResult]) -> tuple[float, float, float]:
        """
        Blend sub-model predictions using learned weights.

        Returns (home_win_prob, away_win_prob, confidence).
        """
        if self.weights is None:
            self._load()

        pred_dict = {r.model_name: r.home_win_prob for r in sub_results}

        if self.weights is None:
            # Fallback: equal weighting
            return self._fallback_predict(sub_results)

        overlap = [name for name in self.model_names if name in pred_dict]
        if len(overlap) < max(2, len(self.model_names)):
            logger.warning(
                "Stacking artifact expects %s but live sub-models only provide %s; using fallback blend",
                self.model_names,
                sorted(pred_dict.keys()),
            )
            return self._fallback_predict(sub_results)

        # Build prediction vector
        X = np.array([pred_dict.get(name, 0.5) for name in self.model_names])
        X_logit = np.log(np.clip(X, 1e-6, 1 - 1e-6) / (1 - np.clip(X, 1e-6, 1 - 1e-6)))

        logit = float(X_logit @ self.weights + self.bias)
        home_wp = float(expit(logit))

        # ── P1.1: Institutional Calibration (Platt-style) ──
        # Protect against overconfidence in small sample WBC datasets
        calibration_alpha = 0.94
        home_wp = calibration_alpha * home_wp + (1 - calibration_alpha) * 0.5

        home_wp = max(0.02, min(0.98, home_wp))

        # ── P1.8: Regime-Aware Adjustments ─────────────────
        regime = RegimeClassifier.classify(sub_results[0].diagnostics.get("round_name", "Pool"))
        var_mult = RegimeClassifier.get_variance_multiplier(regime)

        # Confidence from agreement among models
        model_probs = [pred_dict.get(name, 0.5) for name in self.model_names]
        std = float(np.std(model_probs)) if model_probs else 0.2
        confidence = max(0.15, min(1.0, (1.0 - std * 3.5) * var_mult))

        return home_wp, 1.0 - home_wp, confidence

    @staticmethod
    def _fallback_predict(sub_results: list[SubModelResult]) -> tuple[float, float, float]:
        probs = [r.home_win_prob for r in sub_results]
        if not probs:
            return 0.5, 0.5, 0.5
        weighted = [
            max(0.05, min(1.0, float(getattr(r, "confidence", 0.5)))) for r in sub_results
        ]
        total_weight = sum(weighted)
        avg = (
            sum(prob * weight for prob, weight in zip(probs, weighted)) / total_weight
            if total_weight > 0
            else sum(probs) / len(probs)
        )
        avg = max(0.05, min(0.95, avg))
        std = float(np.std(probs)) if probs else 0.2
        confidence = max(0.15, min(1.0, (1.0 - std * 3.5)))
        return avg, 1.0 - avg, confidence

    def update_online(
        self,
        sub_results: list[SubModelResult],
        actual_home_win: int,
        learning_rate: float = 0.012,
    ) -> dict[str, float]:
        """
        P0.3 Upgrade: Online SGD Meta-learner.
        Performs a single SGD step based on the prediction error of the current match.
        """
        if self.weights is None:
            self._load()
        if self.weights is None:
            return {}

        # 1. Get current prediction (before update)
        pred_dict = {r.model_name: r.home_win_prob for r in sub_results}
        X = np.array([pred_dict.get(name, 0.5) for name in self.model_names])
        X_logit = np.log(np.clip(X, 1e-6, 1 - 1e-6) / (1 - np.clip(X, 1e-6, 1 - 1e-6)))

        logit = float(X_logit @ self.weights + self.bias)
        p = expit(logit)

        # 2. Compute Gradient (BCE over sigmoid)
        error = p - actual_home_win
        grad_w = X_logit * error
        grad_b = error

        # 3. Update Weights (with L2 regularization)
        self.weights -= learning_rate * (grad_w + 0.005 * self.weights)
        self.bias -= learning_rate * grad_b

        self._save()

        updated_weights = {
            name: round(float(w), 4)
            for name, w in zip(self.model_names, self.weights)
        }
        logger.info("[ONLINE] Weights updated for %s models | error=%.3f", len(self.weights), error)
        return updated_weights

    def _save(self):
        self.artifact_path.parent.mkdir(parents=True, exist_ok=True)
        state = {
            "weights": self.weights,
            "bias": self.bias,
            "model_names": self.model_names,
        }
        with open(self.artifact_path, "wb") as f:
            pickle.dump(state, f)

    def _load(self):
        if self.artifact_path.exists():
            try:
                with open(self.artifact_path, "rb") as f:
                    state = pickle.load(f)
                self.weights = state["weights"]
                self.bias = state["bias"]
                self.model_names = state["model_names"]
            except Exception as e:
                logger.warning("Failed to load stacking model: %s", e)


    def record_performance(self, sub_results: list[SubModelResult], actual_home_win: int):
        """
        Record the accuracy (Brier score) of each sub-model.
        """
        history_path = Path("data/wbc_backend/artifacts/model_performance.pkl")
        history = {}
        if history_path.exists():
            with open(history_path, "rb") as f:
                history = pickle.load(f)

        for res in sub_results:
            model_name = res.model_name
            if model_name not in history:
                history[model_name] = []

            error_sq = (res.home_win_prob - actual_home_win) ** 2
            history[model_name].append(error_sq)
            # Keep only last 50 matches for moving average
            history[model_name] = history[model_name][-50:]

        with open(history_path, "wb") as f:
            pickle.dump(history, f)

    def run_tournament_rebalance(self):
        """
        P2.7 Upgrade: Model Tournament Engine.
        Penalize models with high recent Brier scores.
        """
        if self.weights is None:
            return

        history_path = Path("data/wbc_backend/artifacts/model_performance.pkl")
        if not history_path.exists():
            return

        with open(history_path, "rb") as f:
            history = pickle.load(f)

        for i, name in enumerate(self.model_names):
            if name in history and len(history[name]) >= 10:
                avg_brier = np.mean(history[name])
                # Penalty threshold: if Brier > 0.25, reduce its weight in meta-layer
                if avg_brier > 0.25:
                    penalty = (avg_brier - 0.25) * 2.0
                    self.weights[i] *= max(0.2, 1.0 - penalty)
                    logger.info("[TOURNAMENT] Penalizing model %s (Brier=%.4f)", name, avg_brier)

        self._save()
