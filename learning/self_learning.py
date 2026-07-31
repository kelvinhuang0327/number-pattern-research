"""
Self-Learning / Bayesian Updating Module.

After each completed game, this module:
  1. Calculates prediction error for every sub-model
  2. Updates ensemble weights using Bayesian posterior updating
  3. Adjusts pitcher / batter parameters
  4. Persists state to disk (JSON)
"""
from __future__ import annotations
import json
import math
import os
from typing import Dict, List, Optional

STATE_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "learning_state.json")


_EMA_ALPHA = 0.15  # EMA smoothing factor for Brier scores
_MODEL_NAMES = ("elo", "bayesian", "poisson", "gbm", "monte_carlo")


def _load_state() -> Dict:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {
        "model_weights": {
            "elo": 0.20,
            "bayesian": 0.25,
            "poisson": 0.20,
            "gbm": 0.15,
            "monte_carlo": 0.20,
        },
        "ema_brier": {m: 0.25 for m in _MODEL_NAMES},  # initial EMA Brier
        "game_log": [],
        "cumulative_error": {
            "elo": [], "bayesian": [], "poisson": [],
            "gbm": [], "monte_carlo": [],
        },
    }


def _save_state(state: Dict):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def log_result(
    game_id: str,
    actual_winner: str,       # team code
    actual_away_score: int,
    actual_home_score: int,
    predictions: Dict[str, Dict],
    # predictions = {model_name: {"away_wp": float, "predicted_score": "X-Y"}}
):
    """
    Record a completed game and update learning state.
    """
    state = _load_state()

    actual_away_won = actual_away_score > actual_home_score

    # ── Per-model error ──────────────────────────────────
    errors: Dict[str, float] = {}
    for model, pred in predictions.items():
        predicted_away_wp = pred.get("away_wp", 0.5)
        outcome = 1.0 if actual_away_won else 0.0
        # Brier-style error
        error = (predicted_away_wp - outcome) ** 2
        errors[model] = error
        state["cumulative_error"].setdefault(model, []).append(round(error, 6))

    # ── Bayesian weight update ───────────────────────────
    # Likelihood ∝ exp(-error / 2σ²)
    sigma = 0.3  # smoothing parameter
    log_likelihoods = {}
    for model, err in errors.items():
        log_likelihoods[model] = -err / (2 * sigma ** 2)

    # Current log-prior
    weights = state["model_weights"]
    log_posteriors = {}
    for model in weights:
        log_prior = math.log(max(weights[model], 1e-6))
        log_posteriors[model] = log_prior + log_likelihoods.get(model, 0)

    # Normalize
    max_lp = max(log_posteriors.values())
    exp_posteriors = {m: math.exp(lp - max_lp) for m, lp in log_posteriors.items()}
    total = sum(exp_posteriors.values())
    new_weights = {m: round(v / total, 6) for m, v in exp_posteriors.items()}

    # ── EMA Brier update ─────────────────────────────────
    ema = state.get("ema_brier", {m: 0.25 for m in _MODEL_NAMES})
    for model, err in errors.items():
        prev = ema.get(model, 0.25)
        ema[model] = round(_EMA_ALPHA * err + (1 - _EMA_ALPHA) * prev, 8)
    state["ema_brier"] = ema

    # ── EMA-derived weights (inverse Brier) ──────────────
    inv_brier = {m: 1.0 / max(b, 0.01) for m, b in ema.items()}
    inv_total = sum(inv_brier.values())
    ema_weights = {m: round(v / inv_total, 6) for m, v in inv_brier.items()}

    # Blend Bayesian posterior & EMA weights (50/50)
    blended = {}
    for m in new_weights:
        blended[m] = round(0.5 * new_weights[m] + 0.5 * ema_weights.get(m, new_weights[m]), 6)
    # Renormalize
    b_total = sum(blended.values())
    new_weights = {m: round(v / b_total, 6) for m, v in blended.items()}

    state["model_weights"] = new_weights

    # ── Game log ─────────────────────────────────────────
    state["game_log"].append({
        "game_id": game_id,
        "actual_winner": actual_winner,
        "actual_score": f"{actual_away_score}-{actual_home_score}",
        "errors": {m: round(e, 6) for m, e in errors.items()},
        "updated_weights": new_weights,
    })

    _save_state(state)
    return new_weights, errors


def get_recent_errors(n: int = 5) -> List[float]:
    """Return the average ensemble error for the last n games."""
    state = _load_state()
    games = state.get("game_log", [])[-n:]
    result = []
    for g in games:
        errs = g.get("errors", {})
        if errs:
            result.append(sum(errs.values()) / len(errs))
    return result


def get_current_weights() -> Dict[str, float]:
    state = _load_state()
    return state["model_weights"]


def get_ema_brier() -> Dict[str, float]:
    """Return per-model EMA Brier scores."""
    state = _load_state()
    return state.get("ema_brier", {m: 0.25 for m in _MODEL_NAMES})
