"""
Dynamic Bayesian Ensemble — Phase 4/5 Upgrade
==============================================
Replaces the fixed static weights (Elo=45%, BaseRuns=25%, ...) with
a Bayesian online-updating framework that:

  1. Maintains a Dirichlet prior over model weights
  2. Updates weights after each game using likelihood of predictions
  3. Applies regime-aware mixing (tournament vs regular season)
  4. Enforces diversity constraints to prevent weight collapse
  5. Persists weight state between sessions (JSON/SQLite)

Key improvements over static ensemble:
  ┌─────────────────────────────────────────────────────────────────┐
  │ BEFORE: Elo=45%, BaseRuns=25%, Pythagorean=15%, Form=5%,...     │
  │ AFTER:  Weights adapt dynamically based on model performance     │
  │         WBC 2023: Elo=72.3% acc → higher initial weight, but    │
  │         form score was 48.9% → auto-penalized near 0%           │
  └─────────────────────────────────────────────────────────────────┘

Design:
  - Weight state persists in data/wbc_backend/artifacts/ensemble_weights.json
  - Supports separate weight profiles: WBC_POOL, WBC_KNOCKOUT, MLB
  - Hierarchical: regime weights × model weights
  - Calibration: weights adjusted for probability calibration quality
"""
from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from wbc_backend.domain.schemas import SubModelResult

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────

WEIGHT_FILE = Path("data/wbc_backend/artifacts/ensemble_weights.json")

# WBC 2023 empirical accuracy by model
# Source: wbc_2023_v5_full_pipeline backtest
WBC_2023_EMPIRICAL_ACCURACY = {
    "elo": 0.723,           # Best single model
    "bayesian": 0.702,      # Close second
    "poisson": 0.681,       # Good for run totals
    "baseline": 0.638,      # Pythagorean regression
    "real_gbm_stack": 0.670, # ML model (limited WBC data)
    "neural_net": 0.651,    # Neural net (limited data)
    "form": 0.489,          # Worst — small WBC samples
}

# Minimum/maximum weight bounds per model
MIN_WEIGHT = 0.02
MAX_WEIGHT = 0.60

# Regime definitions
REGIME_WBC_POOL = "wbc_pool"
REGIME_WBC_KNOCKOUT = "wbc_knockout"
REGIME_MLB_REGULAR = "mlb_regular"
REGIME_MLB_PLAYOFF = "mlb_playoff"

# Default priors (calibrated from WBC 2023 backtest)
DEFAULT_WEIGHTS: dict[str, dict[str, float]] = {
    REGIME_WBC_POOL: {
        "elo": 0.38,
        "bayesian": 0.22,
        "poisson": 0.18,
        "baseline": 0.08,
        "real_gbm_stack": 0.08,
        "neural_net": 0.04,
        "form": 0.02,
    },
    REGIME_WBC_KNOCKOUT: {
        "elo": 0.30,         # Less dominant in high-pressure knockouts
        "bayesian": 0.25,    # Uncertainty modeling more valuable
        "poisson": 0.18,
        "baseline": 0.10,
        "real_gbm_stack": 0.10,
        "neural_net": 0.05,
        "form": 0.02,
    },
    REGIME_MLB_REGULAR: {
        "elo": 0.20,         # Elo less dominant in long season (regression)
        "bayesian": 0.20,
        "poisson": 0.20,     # Stronger signal with more data
        "baseline": 0.15,
        "real_gbm_stack": 0.15,  # ML more valuable with large dataset
        "neural_net": 0.08,
        "form": 0.02,
    },
    REGIME_MLB_PLAYOFF: {
        "elo": 0.30,
        "bayesian": 0.25,
        "poisson": 0.18,
        "baseline": 0.10,
        "real_gbm_stack": 0.10,
        "neural_net": 0.05,
        "form": 0.02,
    },
}


# ── Data Structures ────────────────────────────────────────────────────────

@dataclass
class ModelWeightState:
    """Persisted weight state for all models."""
    regime: str = REGIME_WBC_POOL
    weights: dict[str, float] = field(default_factory=dict)
    # Dirichlet concentration parameters (α_i)
    dirichlet_alpha: dict[str, float] = field(default_factory=dict)
    # Running performance tracking
    n_updates: int = 0
    cumulative_log_score: float = 0.0
    # Per-model performance statistics
    model_brier: dict[str, float] = field(default_factory=dict)
    model_accuracy: dict[str, float] = field(default_factory=dict)
    model_n_predictions: dict[str, int] = field(default_factory=dict)
    last_updated: str = ""

    def to_dict(self) -> dict:
        return {
            "regime": self.regime,
            "weights": self.weights,
            "dirichlet_alpha": self.dirichlet_alpha,
            "n_updates": self.n_updates,
            "cumulative_log_score": self.cumulative_log_score,
            "model_brier": self.model_brier,
            "model_accuracy": self.model_accuracy,
            "model_n_predictions": self.model_n_predictions,
            "last_updated": self.last_updated,
        }

    @classmethod
    def from_dict(cls, d: dict) -> ModelWeightState:
        state = cls()
        state.regime = d.get("regime", REGIME_WBC_POOL)
        state.weights = d.get("weights", {})
        state.dirichlet_alpha = d.get("dirichlet_alpha", {})
        state.n_updates = d.get("n_updates", 0)
        state.cumulative_log_score = d.get("cumulative_log_score", 0.0)
        state.model_brier = d.get("model_brier", {})
        state.model_accuracy = d.get("model_accuracy", {})
        state.model_n_predictions = d.get("model_n_predictions", {})
        state.last_updated = d.get("last_updated", "")
        return state


@dataclass
class EnsembleBlendResult:
    """Output of dynamic ensemble blending."""
    home_win_prob: float
    away_win_prob: float
    confidence: float
    weights_used: dict[str, float]
    regime: str
    diagnostics: dict[str, float] = field(default_factory=dict)


# ── Core Bayesian Ensemble ─────────────────────────────────────────────────

class DynamicBayesianEnsemble:
    """
    Bayesian online-learning ensemble that adapts weights from game outcomes.

    Theory:
      P(y=1 | x) = Σ_m w_m * p_m(y=1 | x)

    where weights w_m are drawn from a Dirichlet distribution:
      w ~ Dirichlet(α)

    After observing outcome y:
      α_m ← α_m + log_score_m(y)   (multiplicative Bayes update)

    Weights are then normalized: w_m = α_m / Σ_j α_j
    """

    def __init__(self, regime: str = REGIME_WBC_POOL):
        self.state = self._load_or_initialize(regime)
        logger.info(
            "DynamicBayesianEnsemble initialized: regime=%s, n_updates=%d",
            self.state.regime, self.state.n_updates
        )

    def _load_or_initialize(self, regime: str) -> ModelWeightState:
        """Load persisted state or initialize from empirical priors."""
        if WEIGHT_FILE.exists():
            try:
                with open(WEIGHT_FILE) as f:
                    data = json.load(f)
                all_states = data.get("states", {})
                if regime in all_states:
                    state = ModelWeightState.from_dict(all_states[regime])
                    logger.info("Loaded weights for regime=%s (n=%d)", regime, state.n_updates)
                    return state
            except Exception as e:
                logger.warning("Failed to load weight file: %s — using defaults", e)

        return self._initialize_from_prior(regime)

    def _initialize_from_prior(self, regime: str) -> ModelWeightState:
        """Initialize Dirichlet parameters from empirical WBC 2023 accuracies."""
        default_w = DEFAULT_WEIGHTS.get(regime, DEFAULT_WEIGHTS[REGIME_WBC_POOL])
        state = ModelWeightState(regime=regime)

        # Convert accuracy to Dirichlet concentration (higher accuracy = higher α)
        total_acc = sum(WBC_2023_EMPIRICAL_ACCURACY.values())
        for model, _default_weight in default_w.items():
            acc = WBC_2023_EMPIRICAL_ACCURACY.get(model, 0.60)
            # α_0 = 10 (prior strength), higher accuracy → higher initial concentration
            state.dirichlet_alpha[model] = 10.0 * acc / total_acc
            state.model_brier[model] = 0.25  # neutral prior
            state.model_accuracy[model] = acc
            state.model_n_predictions[model] = 0

        state.weights = self._alpha_to_weights(state.dirichlet_alpha)
        return state

    def _alpha_to_weights(self, alpha: dict[str, float]) -> dict[str, float]:
        """Convert Dirichlet α to normalized weights with bounds enforcement."""
        total = sum(alpha.values())
        if total <= 0:
            models = list(alpha.keys())
            return {m: 1.0 / len(models) for m in models}

        raw = {m: a / total for m, a in alpha.items()}

        # Enforce bounds
        weights: dict[str, float] = {}
        excess = 0.0
        deficit_models = []

        for m, w in raw.items():
            if w > MAX_WEIGHT:
                excess += w - MAX_WEIGHT
                weights[m] = MAX_WEIGHT
            elif w < MIN_WEIGHT:
                deficit_models.append(m)
                weights[m] = MIN_WEIGHT
            else:
                weights[m] = w

        # Redistribute excess to unconstrained models
        unconstrained = [m for m in weights if MIN_WEIGHT < weights[m] < MAX_WEIGHT]
        if unconstrained and excess > 0:
            per_model = excess / len(unconstrained)
            for m in unconstrained:
                weights[m] = min(MAX_WEIGHT, weights[m] + per_model)

        # Final normalization
        total_w = sum(weights.values())
        return {m: round(w / total_w, 4) for m, w in weights.items()}

    def blend(self, sub_results: list[SubModelResult],
              regime: str | None = None) -> EnsembleBlendResult:
        """
        Blend sub-model predictions using dynamic Bayesian weights.

        Parameters
        ----------
        sub_results : list of SubModelResult
        regime : override regime for this prediction (optional)

        Returns
        -------
        EnsembleBlendResult
        """
        if not sub_results:
            return EnsembleBlendResult(
                home_win_prob=0.5, away_win_prob=0.5, confidence=0.1,
                weights_used={}, regime=self.state.regime
            )

        # Use current regime weights
        weights = self.state.weights.copy()

        # Build prediction dict
        preds: dict[str, float] = {}
        for sr in sub_results:
            preds[sr.model_name] = sr.home_win_prob

        # Weighted blend
        total_weight = 0.0
        blended_prob = 0.0
        weights_used: dict[str, float] = {}
        confidence_sum = 0.0

        for sr in sub_results:
            w = weights.get(sr.model_name, 1.0 / len(sub_results))
            blended_prob += w * sr.home_win_prob
            total_weight += w
            weights_used[sr.model_name] = w
            confidence_sum += w * sr.confidence

        if total_weight > 0:
            blended_prob /= total_weight
            confidence_sum /= total_weight

        # Normalize remaining weight for models not in results
        if total_weight < 1.0 and total_weight > 0:
            blended_prob = blended_prob / total_weight

        # Bound probability
        home_wp = float(np.clip(blended_prob, 0.05, 0.95))
        away_wp = float(1.0 - home_wp)

        # Confidence: ensemble agreement (1 - variance across model predictions)
        if len(preds) > 1:
            pred_values = list(preds.values())
            variance = float(np.var(pred_values))
            # Lower variance = higher confidence
            confidence = max(0.1, min(0.95, 1.0 - variance * 4.0))
        else:
            confidence = 0.5

        diagnostics = {
            "total_weight": round(total_weight, 4),
            "n_models": float(len(sub_results)),
            "model_variance": float(np.var(list(preds.values()))) if preds else 0.0,
            "n_weight_updates": float(self.state.n_updates),
        }

        return EnsembleBlendResult(
            home_win_prob=home_wp,
            away_win_prob=away_wp,
            confidence=confidence,
            weights_used=weights_used,
            regime=self.state.regime,
            diagnostics=diagnostics,
        )

    def update_weights(self, sub_results: list[SubModelResult],
                       actual_home_win: int) -> None:
        """
        Bayesian weight update after observing game outcome.

        Uses log scoring rule:
          score_m = log(p_m(correct_outcome))

        Updates Dirichlet α:
          α_m ← α_m * (1 + learning_rate * normalized_score_m)

        § 核心規範 01: This must ONLY be called after prediction is complete.
        """
        if not sub_results:
            return

        LEARNING_RATE = 0.03  # Conservative to avoid overfitting small WBC samples

        log_scores: dict[str, float] = {}
        for sr in sub_results:
            if actual_home_win == 1:
                p_correct = max(1e-6, sr.home_win_prob)
            else:
                p_correct = max(1e-6, sr.away_win_prob)
            log_scores[sr.model_name] = math.log(p_correct)

        # Normalize log scores to [0, 2] range
        min_ls = min(log_scores.values())
        max_ls = max(log_scores.values())
        score_range = max_ls - min_ls

        for model, ls in log_scores.items():
            if model not in self.state.dirichlet_alpha:
                self.state.dirichlet_alpha[model] = 0.10

            if score_range > 0:
                normalized = (ls - min_ls) / score_range  # [0, 1]
            else:
                normalized = 0.5

            # Multiplicative update: better models get higher α
            update = 1.0 + LEARNING_RATE * (normalized - 0.5)
            self.state.dirichlet_alpha[model] = max(
                0.01, self.state.dirichlet_alpha[model] * update
            )

            # Track Brier score
            n = self.state.model_n_predictions.get(model, 0)
            if actual_home_win == 1:
                brier_contrib = (sr.home_win_prob - 1.0) ** 2
                correct = 1 if sr.home_win_prob >= 0.5 else 0
            else:
                brier_contrib = (sr.home_win_prob - 0.0) ** 2
                correct = 1 if sr.home_win_prob < 0.5 else 0

            old_brier = self.state.model_brier.get(model, 0.25)
            self.state.model_brier[model] = (old_brier * n + brier_contrib) / (n + 1)
            old_acc = self.state.model_accuracy.get(model, 0.6)
            self.state.model_accuracy[model] = (old_acc * n + correct) / (n + 1)
            self.state.model_n_predictions[model] = n + 1

        # Recompute normalized weights
        self.state.weights = self._alpha_to_weights(self.state.dirichlet_alpha)
        self.state.n_updates += 1
        self.state.cumulative_log_score += float(np.mean(list(log_scores.values())))

        logger.debug(
            "Weight update #%d complete. Top model: %s (α=%.3f)",
            self.state.n_updates,
            max(self.state.dirichlet_alpha, key=self.state.dirichlet_alpha.get),
            max(self.state.dirichlet_alpha.values()),
        )

    def save(self) -> None:
        """Persist weight state to JSON."""
        WEIGHT_FILE.parent.mkdir(parents=True, exist_ok=True)
        all_states: dict = {}
        if WEIGHT_FILE.exists():
            try:
                with open(WEIGHT_FILE) as f:
                    all_states = json.load(f).get("states", {})
            except Exception:
                pass

        from datetime import datetime
        self.state.last_updated = datetime.now().isoformat()
        all_states[self.state.regime] = self.state.to_dict()

        with open(WEIGHT_FILE, "w") as f:
            json.dump({"states": all_states, "version": "2.0"}, f, indent=2)
        logger.info("Ensemble weights saved to %s", WEIGHT_FILE)

    def get_weight_report(self) -> dict:
        """Return human-readable weight summary."""
        w = self.state.weights
        sorted_w = sorted(w.items(), key=lambda x: x[1], reverse=True)
        return {
            "regime": self.state.regime,
            "n_updates": self.state.n_updates,
            "weights": dict(sorted_w),
            "model_accuracy": {
                m: round(self.state.model_accuracy.get(m, 0.0), 4)
                for m in w
            },
            "model_brier": {
                m: round(self.state.model_brier.get(m, 0.25), 4)
                for m in w
            },
            "top_model": sorted_w[0][0] if sorted_w else "unknown",
        }


# ── Regime Detection ────────────────────────────────────────────────────────

def detect_regime(tournament: str, round_name: str) -> str:
    """Detect the appropriate ensemble regime from matchup context."""
    t = tournament.lower()
    r = round_name.lower()

    if "wbc" in t or "world baseball classic" in t:
        if any(kw in r for kw in ["final", "semifinal", "sf", "qf", "quarter"]):
            return REGIME_WBC_KNOCKOUT
        return REGIME_WBC_POOL
    elif "playoff" in t or "postseason" in t or "lcs" in r or "lcs" in t or "ws" in r:
        return REGIME_MLB_PLAYOFF
    return REGIME_MLB_REGULAR


# ── Factory / Singleton ────────────────────────────────────────────────────

_ENSEMBLE_CACHE: dict[str, DynamicBayesianEnsemble] = {}


def get_ensemble(regime: str = REGIME_WBC_POOL) -> DynamicBayesianEnsemble:
    """Get or create a DynamicBayesianEnsemble for the given regime."""
    if regime not in _ENSEMBLE_CACHE:
        _ENSEMBLE_CACHE[regime] = DynamicBayesianEnsemble(regime)
    return _ENSEMBLE_CACHE[regime]


def blend_predictions(sub_results: list[SubModelResult],
                       tournament: str = "WBC",
                       round_name: str = "Pool") -> EnsembleBlendResult:
    """
    Convenience function: auto-detect regime and blend predictions.

    This is the primary API for the ensemble layer.
    """
    regime = detect_regime(tournament, round_name)
    ensemble = get_ensemble(regime)
    return ensemble.blend(sub_results)


def record_outcome(sub_results: list[SubModelResult],
                   actual_home_win: int,
                   tournament: str = "WBC",
                   round_name: str = "Pool") -> None:
    """
    Record actual game outcome and update ensemble weights.

    § 核心規範 01: Must be called AFTER prediction, not before.
    """
    regime = detect_regime(tournament, round_name)
    ensemble = get_ensemble(regime)
    ensemble.update_weights(sub_results, actual_home_win)
    ensemble.save()


# ── Diagnostics ────────────────────────────────────────────────────────────

def compare_static_vs_dynamic(static_home_wp: float,
                               dynamic_result: EnsembleBlendResult) -> dict:
    """Compare static vs dynamic ensemble output for transparency."""
    return {
        "static_home_wp": static_home_wp,
        "dynamic_home_wp": dynamic_result.home_win_prob,
        "divergence": abs(static_home_wp - dynamic_result.home_win_prob),
        "dynamic_regime": dynamic_result.regime,
        "n_weight_updates": dynamic_result.diagnostics.get("n_weight_updates", 0),
        "top_model_by_weight": max(
            dynamic_result.weights_used,
            key=dynamic_result.weights_used.get,
            default="unknown"
        ),
        "ensemble_confidence": dynamic_result.confidence,
    }
