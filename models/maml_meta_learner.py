"""
Meta-Learning (MAML-inspired) for WBC Cold Start (§ P3).

Problem: WBC has only 5-7 games per team per edition. Traditional ML
models need 50+ samples to converge. This module uses a MAML-style
approach to learn good initialization weights from multiple "tasks"
(= previous WBC editions, Premier12, international friendlies).

Key idea: Instead of training from scratch each WBC, we learn
"meta-parameters" that can be fine-tuned with just 2-3 games.

Architecture:
    Meta-train on {WBC 2009, 2013, 2017, 2023, Premier12} tasks:
      For each task (edition):
        1. Take initial θ_meta
        2. Fine-tune θ' = θ_meta - α * ∇L_task(θ_meta) using K games
        3. Evaluate on remaining games
        4. Update θ_meta to minimize evaluation loss across all tasks

    At inference (WBC 2026):
        1. Start with θ_meta
        2. After each game, do 1-step gradient update
        3. Predictions improve rapidly (target: stable after ~5 games)

Implementation:
    Since our models aren't all differentiable neural nets, we apply
    MAML principles to the ensemble weight vector and feature scaling
    parameters, which CAN be gradient-updated.
"""
from __future__ import annotations

import json
import math
import os
from typing import Dict, List, Optional, Tuple


class MAMLWeightLearner:
    """
    MAML-inspired meta-learner for ensemble weights.

    Meta-parameters: initial ensemble weights + per-feature scaling factors.
    Inner loop: 1-step SGD on Brier loss using K support games.
    Outer loop: optimize meta-params to minimize query set loss.
    """

    def __init__(
        self,
        model_names: Optional[List[str]] = None,
        inner_lr: float = 0.05,
        meta_lr: float = 0.01,
        n_inner_steps: int = 1,
    ):
        if model_names is None:
            model_names = ["elo", "bayesian", "poisson", "gbm", "monte_carlo"]
        self.model_names = model_names
        self.inner_lr = inner_lr
        self.meta_lr = meta_lr
        self.n_inner_steps = n_inner_steps
        self.n_models = len(model_names)

        # Meta-parameters: initial weights (will be learned)
        self.meta_weights = {m: 1.0 / self.n_models for m in model_names}

        # State file
        self._state_file = os.path.join(
            os.path.dirname(__file__), "..", "data", "maml_state.json"
        )
        self._load_state()

    # ── Core MAML Algorithm ──────────────────────────────

    def meta_train(
        self,
        tasks: List[List[Dict]],
        support_size: int = 3,
        n_epochs: int = 50,
    ) -> Dict[str, float]:
        """
        Meta-train on multiple tasks (WBC editions).

        Each task is a list of game dicts with:
          {"model_probs": {model: prob}, "actual_home_win": 0 or 1}

        Support set = first `support_size` games (fine-tune)
        Query set = remaining games (evaluate)
        """
        for epoch in range(n_epochs):
            meta_gradients = {m: 0.0 for m in self.model_names}

            for task in tasks:
                if len(task) <= support_size:
                    continue

                support = task[:support_size]
                query = task[support_size:]

                # Inner loop: adapt weights using support set
                adapted = dict(self.meta_weights)
                for _ in range(self.n_inner_steps):
                    grad = self._compute_gradient(adapted, support)
                    adapted = {
                        m: adapted[m] - self.inner_lr * grad[m]
                        for m in self.model_names
                    }
                    adapted = self._normalize(adapted)

                # Outer loop: compute loss on query set with adapted weights
                query_grad = self._compute_gradient(adapted, query)
                for m in self.model_names:
                    meta_gradients[m] += query_grad[m]

            # Meta-update
            n_tasks = max(1, len(tasks))
            self.meta_weights = {
                m: self.meta_weights[m] - self.meta_lr * meta_gradients[m] / n_tasks
                for m in self.model_names
            }
            self.meta_weights = self._normalize(self.meta_weights)

        self._save_state()
        return dict(self.meta_weights)

    def adapt(
        self,
        recent_games: List[Dict],
        n_steps: Optional[int] = None,
    ) -> Dict[str, float]:
        """
        Adapt meta-weights to current tournament using K observed games.

        Call this after each game in WBC 2026 to refine predictions.
        Returns adapted weight vector.
        """
        if not recent_games:
            return dict(self.meta_weights)

        steps = n_steps or self.n_inner_steps
        adapted = dict(self.meta_weights)

        for _ in range(steps):
            grad = self._compute_gradient(adapted, recent_games)
            adapted = {
                m: adapted[m] - self.inner_lr * grad[m]
                for m in self.model_names
            }
            adapted = self._normalize(adapted)

        return adapted

    def predict_ensemble(
        self,
        model_probs: Dict[str, float],
        adapted_weights: Optional[Dict[str, float]] = None,
    ) -> float:
        """
        Compute weighted ensemble probability using (adapted) meta-weights.
        """
        weights = adapted_weights or self.meta_weights
        total_w = sum(weights.get(m, 0) for m in model_probs)
        if total_w <= 0:
            return 0.5

        p = sum(
            model_probs[m] * weights.get(m, 0)
            for m in model_probs
            if m in weights
        ) / total_w
        return max(0.01, min(0.99, p))

    # ── Gradient Computation ─────────────────────────────

    def _compute_gradient(
        self,
        weights: Dict[str, float],
        games: List[Dict],
    ) -> Dict[str, float]:
        """
        Compute gradient of Brier loss w.r.t. ensemble weights.

        ∂L/∂w_m = (2/N) * Σ (p_ensemble - y) * (p_m - p_ensemble) / W
        """
        grad = {m: 0.0 for m in self.model_names}
        n = len(games)
        if n == 0:
            return grad

        total_w = sum(max(0, weights[m]) for m in self.model_names)
        if total_w <= 0:
            return grad

        for game in games:
            model_probs = game.get("model_probs", {})
            y = float(game.get("actual_home_win", 0))

            # Ensemble prediction
            p_ens = sum(
                model_probs.get(m, 0.5) * max(0, weights.get(m, 0))
                for m in self.model_names
            ) / total_w

            residual = p_ens - y

            for m in self.model_names:
                p_m = model_probs.get(m, 0.5)
                grad[m] += 2.0 * residual * (p_m - p_ens) / total_w

        # Average
        return {m: g / n for m, g in grad.items()}

    # ── Utility ──────────────────────────────────────────

    @staticmethod
    def _normalize(weights: Dict[str, float]) -> Dict[str, float]:
        """Ensure weights are non-negative and sum to 1."""
        clamped = {m: max(0.01, w) for m, w in weights.items()}
        total = sum(clamped.values())
        return {m: w / total for m, w in clamped.items()}

    def _save_state(self) -> None:
        os.makedirs(os.path.dirname(self._state_file), exist_ok=True)
        with open(self._state_file, "w") as f:
            json.dump({
                "meta_weights": self.meta_weights,
                "inner_lr": self.inner_lr,
                "meta_lr": self.meta_lr,
            }, f, indent=2)

    def _load_state(self) -> None:
        if os.path.exists(self._state_file):
            with open(self._state_file, "r") as f:
                state = json.load(f)
            self.meta_weights = state.get("meta_weights", self.meta_weights)

    def get_cold_start_weights(self) -> Dict[str, float]:
        """Return the meta-learned initial weights for a new tournament."""
        return dict(self.meta_weights)
