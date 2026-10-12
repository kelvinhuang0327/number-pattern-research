"""
Phase 5 — Meta Learning Loop
================================
Autonomous self-improvement engine that:

  1. Tracks per-model and per-strategy performance over time
  2. Retrains ensemble weights every N games
  3. Auto-adjusts feature importance
  4. Disables models/strategies with negative trailing ROI
  5. Detects regime shifts triggering accelerated retraining

Key rules:
  - Retrain every 100 games (or on regime shift detection)
  - Auto-disable any model if 300-game ROI < 0
  - Never retrain on fewer than 30 samples
  - Log all retrains for audit trail
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ─── Configuration ──────────────────────────────────────────────────────────

META_CONFIG = {
    "retrain_interval": 100,               # games between retrains
    "min_retrain_samples": 30,             # minimum samples for retrain
    "auto_disable_window": 300,            # games window for disable check
    "auto_disable_roi_threshold": 0.0,     # disable if ROI < this
    "regime_shift_retrain_accel": 0.5,     # retrain at 50% interval if shift
    "max_disabled_models": 3,              # keep at least some models active
    "performance_ewma_alpha": 0.05,        # exponential smoothing factor
    "weight_learning_rate": 0.01,          # how fast to adjust weights
    "min_model_weight": 0.05,             # floor for any model weight
    "max_model_weight": 0.40,             # ceiling for any model weight
}


# ─── Data Structures ────────────────────────────────────────────────────────

class ModelStatus(Enum):
    ACTIVE = "ACTIVE"
    PROBATION = "PROBATION"       # degraded performance, reduced weight
    DISABLED = "DISABLED"          # auto-disabled due to negative ROI


@dataclass
class ModelPerformanceEntry:
    """Single prediction record for tracking."""
    game_id: str = ""
    timestamp: float = 0.0
    model_name: str = ""
    predicted_prob: float = 0.5
    actual_outcome: int = 0  # 1 = correct side, 0 = wrong
    brier_contribution: float = 0.25
    log_loss_contribution: float = 0.693
    roi_contribution: float = 0.0
    odds_at_bet: float = 2.0


@dataclass
class ModelTracker:
    """Performance tracking for a single model/strategy."""
    name: str = ""
    status: ModelStatus = ModelStatus.ACTIVE
    current_weight: float = 0.2

    # Running stats
    total_predictions: int = 0
    trailing_brier: float = 0.25
    trailing_log_loss: float = 0.693
    trailing_roi: float = 0.0
    trailing_hit_rate: float = 0.50

    # EWMA smoothed
    ewma_brier: float = 0.25
    ewma_roi: float = 0.0
    ewma_hit_rate: float = 0.50

    # History (circular buffer approach — keep last N)
    recent_outcomes: list[int] = field(default_factory=list)
    recent_roi: list[float] = field(default_factory=list)

    # Metadata
    last_retrain_at: int = 0
    disabled_at: int | None = None
    disabled_reason: str = ""


@dataclass
class RetrainEvent:
    """Log of a retrain action."""
    event_id: int = 0
    timestamp: float = 0.0
    game_count: int = 0
    trigger: str = "SCHEDULED"         # SCHEDULED / REGIME_SHIFT / MANUAL
    models_retrained: list[str] = field(default_factory=list)
    weight_changes: dict[str, tuple[float, float]] = field(default_factory=dict)
    models_disabled: list[str] = field(default_factory=list)
    models_reactivated: list[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class MetaState:
    """Full state of the meta-learning system."""
    total_games: int = 0
    models: dict[str, ModelTracker] = field(default_factory=dict)
    retrain_history: list[RetrainEvent] = field(default_factory=list)
    next_retrain_at: int = 100
    regime_shift_detected: bool = False
    global_hit_rate: float = 0.50
    global_roi: float = 0.0


# ─── Core Meta-Learning Functions ──────────────────────────────────────────

def initialize_meta_state(model_names: list[str]) -> MetaState:
    """Initialize meta state with equal weights."""
    n = len(model_names)
    weight = 1.0 / n if n > 0 else 0.2

    models = {}
    for name in model_names:
        models[name] = ModelTracker(
            name=name,
            current_weight=weight,
        )

    return MetaState(
        models=models,
        next_retrain_at=META_CONFIG["retrain_interval"],
    )


def record_prediction(
    state: MetaState,
    model_name: str,
    entry: ModelPerformanceEntry,
) -> None:
    """Record a single prediction outcome for a model."""
    if model_name not in state.models:
        state.models[model_name] = ModelTracker(name=model_name)

    tracker = state.models[model_name]
    tracker.total_predictions += 1

    # Update circular buffers
    window = META_CONFIG["auto_disable_window"]
    tracker.recent_outcomes.append(entry.actual_outcome)
    tracker.recent_roi.append(entry.roi_contribution)
    if len(tracker.recent_outcomes) > window:
        tracker.recent_outcomes = tracker.recent_outcomes[-window:]
    if len(tracker.recent_roi) > window:
        tracker.recent_roi = tracker.recent_roi[-window:]

    # Update EWMA
    alpha = META_CONFIG["performance_ewma_alpha"]
    tracker.ewma_brier = (1 - alpha) * tracker.ewma_brier + alpha * entry.brier_contribution
    tracker.ewma_roi = (1 - alpha) * tracker.ewma_roi + alpha * entry.roi_contribution
    tracker.ewma_hit_rate = (1 - alpha) * tracker.ewma_hit_rate + alpha * entry.actual_outcome

    # Update trailing stats
    if tracker.recent_outcomes:
        tracker.trailing_hit_rate = sum(tracker.recent_outcomes) / len(tracker.recent_outcomes)
    if tracker.recent_roi:
        tracker.trailing_roi = sum(tracker.recent_roi) / len(tracker.recent_roi)


def record_game(state: MetaState) -> None:
    """Increment global game counter."""
    state.total_games += 1


def should_retrain(state: MetaState) -> tuple[bool, str]:
    """Check if a retrain is triggered."""
    if state.total_games >= state.next_retrain_at:
        return True, "SCHEDULED"

    if state.regime_shift_detected:
        accel = META_CONFIG["regime_shift_retrain_accel"]
        accel_at = int(
            state.retrain_history[-1].game_count
            + META_CONFIG["retrain_interval"] * accel
        ) if state.retrain_history else state.total_games
        if state.total_games >= accel_at:
            return True, "REGIME_SHIFT"

    return False, ""


def execute_retrain(state: MetaState, trigger: str = "SCHEDULED") -> RetrainEvent:  # noqa: C901
    """
    Execute a meta-learning retrain:
      1. Evaluate each model's trailing performance
      2. Adjust weights (reward good, penalise bad)
      3. Disable models with persistent negative ROI
      4. Log the event
    """
    event = RetrainEvent(
        event_id=len(state.retrain_history) + 1,
        timestamp=time.time(),
        game_count=state.total_games,
        trigger=trigger,
    )

    min_samples = META_CONFIG["min_retrain_samples"]
    lr = META_CONFIG["weight_learning_rate"]
    min_w = META_CONFIG["min_model_weight"]
    max_w = META_CONFIG["max_model_weight"]
    disable_window = META_CONFIG["auto_disable_window"]
    disable_threshold = META_CONFIG["auto_disable_roi_threshold"]

    active_models = [
        m for m in state.models.values()
        if m.status != ModelStatus.DISABLED
    ]

    # --- Step 1: Check for auto-disable ---
    disabled_count = sum(1 for m in state.models.values() if m.status == ModelStatus.DISABLED)
    max_disable = META_CONFIG["max_disabled_models"]

    for tracker in active_models:
        if len(tracker.recent_roi) >= disable_window:
            trailing_roi = sum(tracker.recent_roi[-disable_window:]) / disable_window
            if trailing_roi < disable_threshold and disabled_count < max_disable:
                tracker.status = ModelStatus.DISABLED
                tracker.disabled_at = state.total_games
                tracker.disabled_reason = (
                    f"ROI {trailing_roi:.4f} < {disable_threshold} "
                    f"over last {disable_window} games"
                )
                event.models_disabled.append(tracker.name)
                disabled_count += 1

    # --- Step 2: Try to reactivate disabled models ---
    for tracker in state.models.values():
        if tracker.status == ModelStatus.DISABLED and tracker.disabled_at:
            games_since = state.total_games - tracker.disabled_at
            if games_since > disable_window:
                # Give it another chance
                tracker.status = ModelStatus.PROBATION
                tracker.current_weight = min_w
                tracker.disabled_at = None
                event.models_reactivated.append(tracker.name)

    # --- Step 3: Adjust weights based on performance ---
    active_models = [
        m for m in state.models.values()
        if m.status in (ModelStatus.ACTIVE, ModelStatus.PROBATION)
    ]

    if len(active_models) < 2:
        event.notes = "Too few active models for weight adjustment"
        state.next_retrain_at = state.total_games + META_CONFIG["retrain_interval"]
        state.retrain_history.append(event)
        return event

    # Performance ranking
    ranked = sorted(active_models, key=lambda m: m.ewma_roi, reverse=True)

    for i, tracker in enumerate(ranked):
        if tracker.total_predictions < min_samples:
            continue

        old_weight = tracker.current_weight
        rank_score = 1.0 - (i / len(ranked))  # 1.0 for best, 0.0 for worst

        # Gradient update towards performance-weighted target
        target = rank_score / len(ranked) * 2  # normalise
        delta = lr * (target - old_weight)
        new_weight = old_weight + delta

        # Clamp
        new_weight = max(min_w, min(max_w, new_weight))

        # Probation models get capped lower
        if tracker.status == ModelStatus.PROBATION:
            new_weight = min(new_weight, 2 * min_w)

        tracker.current_weight = round(new_weight, 4)
        event.weight_changes[tracker.name] = (old_weight, new_weight)
        event.models_retrained.append(tracker.name)

    # Normalise weights to sum to 1
    total_w = sum(m.current_weight for m in active_models)
    if total_w > 0:
        for m in active_models:
            m.current_weight = round(m.current_weight / total_w, 4)

    # Update last retrain marker
    for m in active_models:
        m.last_retrain_at = state.total_games

    # Schedule next retrain
    state.next_retrain_at = state.total_games + META_CONFIG["retrain_interval"]
    state.regime_shift_detected = False

    event.notes = (
        f"Retrained {len(event.models_retrained)} models, "
        f"disabled {len(event.models_disabled)}, "
        f"reactivated {len(event.models_reactivated)}"
    )

    state.retrain_history.append(event)
    return event


def get_model_weights(state: MetaState) -> dict[str, float]:
    """Get current model weights (only active models)."""
    return {
        name: tracker.current_weight
        for name, tracker in state.models.items()
        if tracker.status in (ModelStatus.ACTIVE, ModelStatus.PROBATION)
    }


def detect_regime_shift(
    state: MetaState,
    recent_regimes: list[str],
    window: int = 10,
) -> bool:
    """
    Detect if the market regime has shifted significantly.
    If >60% of recent games have a different regime than the
    trailing average, flag a shift.
    """
    if len(recent_regimes) < window:
        return False

    recent = recent_regimes[-window:]
    prior = recent_regimes[-(window * 2):-window] if len(recent_regimes) >= window * 2 else []

    if not prior:
        return False

    # Most common regime in each window
    from collections import Counter
    recent_mode = Counter(recent).most_common(1)[0][0]
    prior_mode = Counter(prior).most_common(1)[0][0]

    if recent_mode != prior_mode:
        # How dominant is the new regime?
        dominance = Counter(recent)[recent_mode] / len(recent)
        if dominance > 0.60:
            state.regime_shift_detected = True
            return True

    return False


def get_meta_summary(state: MetaState) -> dict[str, Any]:
    """Get a summary of the meta-learning state for reporting."""
    active = [m for m in state.models.values() if m.status == ModelStatus.ACTIVE]
    probation = [m for m in state.models.values() if m.status == ModelStatus.PROBATION]
    disabled = [m for m in state.models.values() if m.status == ModelStatus.DISABLED]

    return {
        "total_games": state.total_games,
        "next_retrain_at": state.next_retrain_at,
        "games_until_retrain": state.next_retrain_at - state.total_games,
        "regime_shift_detected": state.regime_shift_detected,
        "active_models": len(active),
        "probation_models": len(probation),
        "disabled_models": len(disabled),
        "model_weights": get_model_weights(state),
        "total_retrains": len(state.retrain_history),
        "best_model": max(active, key=lambda m: m.ewma_roi).name if active else "N/A",
        "worst_model": min(active, key=lambda m: m.ewma_roi).name if active else "N/A",
    }
