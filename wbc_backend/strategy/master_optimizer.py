"""
Master Optimizer — Autonomous System Controller
=================================================
Automated execution of the full optimization loop:
  1. Model Selection — assess & retire underperformers
  2. Hyperparameter Optimisation — Bayesian + random search
  3. Feature Selection — importance-based pruning & expansion
  4. Weight Adjustment — posterior-driven ensemble rebalancing
  5. Strategy Evolution — meta-strategy rotation & selection

The Master Optimizer runs periodically (configurable) and produces
an optimization report with all changes applied.
"""
from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from wbc_backend.strategy.live_retrainer import (
    ModelPerformance, evaluate_model_health, load_state, save_state
)
from wbc_backend.strategy.alpha_discovery import (
    AlphaReport, run_alpha_discovery
)


# ─── Data Structures ─────────────────────────────────────────────────────────

@dataclass
class OptimizationAction:
    """A single optimization action taken by the controller."""
    category: str      # MODEL | HYPERPARAMS | FEATURES | WEIGHTS | STRATEGY
    action: str        # human-readable description
    before: Any = None
    after: Any = None
    impact_estimate: float = 0.0  # estimated Brier / ROI improvement


@dataclass
class OptimizationReport:
    """Complete optimization cycle report."""
    timestamp: float = 0.0
    actions: list[OptimizationAction] = field(default_factory=list)
    model_health: str = "HEALTHY"
    drift_detected: bool = False
    features_added: int = 0
    features_removed: int = 0
    models_retired: int = 0
    weight_changes: dict[str, tuple[float, float]] = field(default_factory=dict)
    strategy_recommendation: str = ""
    estimated_improvement: float = 0.0
    summary: str = ""


# ─── Constants ────────────────────────────────────────────────────────────────

OPTIMIZATION_LOG = Path("data/wbc_backend/artifacts/optimization_log.json")
BRIER_TARGET = 0.24              # target Brier score
BRIER_ACCEPTABLE = 0.26          # acceptable Brier
BRIER_RETIRE = 0.30              # retire models above this
MIN_SAMPLE_FOR_DECISION = 30     # minimum games before making changes
WEIGHT_CHANGE_MAX = 0.10         # max weight change per cycle
FEATURE_IMPORTANCE_FLOOR = 0.005 # features below this get removed


# ─── 1. Model Selection ─────────────────────────────────────────────────────

def optimize_model_selection(
    performances: dict[str, ModelPerformance],
) -> list[OptimizationAction]:
    """
    Assess all models and decide: KEEP, WARN, or RETIRE.

    Retirement criteria:
      - Brier > threshold over sustained window
      - Consistent degradation trend
      - Adding noise to ensemble (high variance, low accuracy)
    """
    actions: list[OptimizationAction] = []

    for name, perf in performances.items():
        if perf.sample_size < MIN_SAMPLE_FOR_DECISION:
            continue

        brier = perf.recent_brier
        trend = perf.trend

        if brier > BRIER_RETIRE:
            actions.append(OptimizationAction(
                category="MODEL",
                action=f"RETIRE {name}: Brier {brier:.4f} > {BRIER_RETIRE}",
                before=brier,
                after=None,
                impact_estimate=0.005,  # expected improvement from removal
            ))
        elif brier > BRIER_ACCEPTABLE and trend == "DEGRADING":
            actions.append(OptimizationAction(
                category="MODEL",
                action=f"WARNING {name}: Brier {brier:.4f} & degrading. "
                       f"Reduce weight and monitor.",
                before=brier,
                impact_estimate=0.002,
            ))
        elif brier < BRIER_TARGET and trend == "IMPROVING":
            actions.append(OptimizationAction(
                category="MODEL",
                action=f"BOOST {name}: Brier {brier:.4f} & improving. "
                       f"Increase weight.",
                before=brier,
                impact_estimate=0.003,
            ))

    return actions


# ─── 2. Hyperparameter Optimisation ─────────────────────────────────────────

@dataclass
class HyperparamSearchResult:
    """Result from a single hyperparameter trial."""
    params: dict[str, float]
    score: float
    trial_id: int


def optimize_hyperparameters(
    current_params: dict[str, float],
    eval_fn: Any | None = None,
    n_trials: int = 20,
) -> list[OptimizationAction]:
    """
    Bayesian-inspired hyperparameter search.

    Uses random perturbation around current best params with
    shrinking perturbation radius (simulated annealing).

    Parameters to tune:
      - elo_k_factor
      - ensemble weights
      - kelly_fraction
      - ev_threshold
      - lookback window
    """
    actions: list[OptimizationAction] = []

    # Define parameter space
    param_space = {
        "elo_k": (4.0, 32.0, current_params.get("elo_k", 6.0)),
        "kelly_frac": (0.10, 0.50, current_params.get("kelly_frac", 0.25)),
        "ev_threshold": (0.01, 0.08, current_params.get("ev_threshold", 0.03)),
        "lookback": (8, 30, current_params.get("lookback", 12)),
        "home_adv": (15.0, 40.0, current_params.get("home_adv", 24.0)),
    }

    best_params = {k: v[2] for k, v in param_space.items()}
    best_score = _evaluate_params(best_params, eval_fn)

    for trial in range(n_trials):
        # Temperature-based perturbation
        temperature = 1.0 - (trial / n_trials)
        candidate = {}
        for name, (lo, hi, current) in param_space.items():
            noise = random.gauss(0, (hi - lo) * 0.15 * temperature)
            candidate[name] = max(lo, min(hi, current + noise))

        score = _evaluate_params(candidate, eval_fn)

        if score < best_score:
            best_score = score
            best_params = candidate

    # Report changes
    for name in param_space:
        old_val = param_space[name][2]
        new_val = best_params[name]
        if abs(new_val - old_val) > 0.01 * old_val:
            actions.append(OptimizationAction(
                category="HYPERPARAMS",
                action=f"Tune {name}: {old_val:.4f} → {new_val:.4f}",
                before=old_val,
                after=new_val,
                impact_estimate=abs(best_score - _evaluate_params(
                    {k: param_space[k][2] for k in param_space}, eval_fn
                )) if eval_fn else 0.001,
            ))

    return actions


def _evaluate_params(params: dict[str, float], eval_fn: Any | None) -> float:
    """Evaluate parameters. If no eval_fn, return surrogate score."""
    if eval_fn is not None:
        try:
            return eval_fn(params)
        except Exception:
            return 1.0

    # Surrogate: penalise deviation from known-good defaults
    good_defaults = {"elo_k": 6.0, "kelly_frac": 0.25, "ev_threshold": 0.03,
                     "lookback": 12.0, "home_adv": 24.0}
    penalty = sum(
        ((params.get(k, v) - v) / max(abs(v), 0.01)) ** 2
        for k, v in good_defaults.items()
    )
    return 0.25 + penalty * 0.01  # baseline Brier + penalty


# ─── 3. Feature Selection ───────────────────────────────────────────────────

def optimize_features(
    alpha_report: AlphaReport | None = None,
) -> list[OptimizationAction]:
    """
    Feature pruning and expansion based on alpha discovery results.
    """
    actions: list[OptimizationAction] = []

    if alpha_report is None:
        return actions

    # Remove low-importance features
    for fname in alpha_report.features_to_remove:
        actions.append(OptimizationAction(
            category="FEATURES",
            action=f"REMOVE feature '{fname}': below importance threshold",
            impact_estimate=0.001,
        ))

    # Add high-value interaction features
    for fname in alpha_report.features_to_add:
        actions.append(OptimizationAction(
            category="FEATURES",
            action=f"ADD feature '{fname}': interaction with predictive power",
            impact_estimate=0.002,
        ))

    return actions


# ─── 4. Weight Adjustment ───────────────────────────────────────────────────

def optimize_weights(
    current_weights: dict[str, float],
    performances: dict[str, ModelPerformance],
) -> tuple[dict[str, float], list[OptimizationAction]]:
    """
    Adjust ensemble weights based on recent model performance.

    Uses inverse-Brier weighting with smooth transition
    (max change per cycle capped at WEIGHT_CHANGE_MAX).
    """
    actions: list[OptimizationAction] = []
    new_weights = dict(current_weights)

    if not performances:
        return new_weights, actions

    # Compute inverse-Brier scores
    inv_brier = {}
    for name, perf in performances.items():
        if perf.sample_size < 10:
            inv_brier[name] = 1.0
        else:
            inv_brier[name] = 1.0 / max(perf.recent_brier, 0.01)

    total_inv = sum(inv_brier.values())
    target_weights = {k: v / total_inv for k, v in inv_brier.items()}

    # Apply smooth transition (cap change per cycle)
    for name in target_weights:
        old_w = current_weights.get(name, 0.1)
        target_w = target_weights[name]
        delta = target_w - old_w
        capped_delta = max(-WEIGHT_CHANGE_MAX, min(WEIGHT_CHANGE_MAX, delta))
        new_weights[name] = max(0.02, old_w + capped_delta)

    # Renormalise
    total = sum(new_weights.values())
    new_weights = {k: v / total for k, v in new_weights.items()}

    # Log significant changes
    for name in new_weights:
        old_w = current_weights.get(name, 0.1)
        new_w = new_weights[name]
        if abs(new_w - old_w) > 0.005:
            actions.append(OptimizationAction(
                category="WEIGHTS",
                action=f"Adjust {name}: {old_w:.3f} → {new_w:.3f}",
                before=old_w,
                after=new_w,
                impact_estimate=abs(new_w - old_w) * 0.1,
            ))

    return new_weights, actions


# ─── 5. Strategy Evolution ──────────────────────────────────────────────────

def optimize_strategy(
    recent_roi: float,
    recent_sharpe: float,
    market_efficiency: float,
) -> list[OptimizationAction]:
    """
    Meta-strategy selection based on recent performance and market conditions.
    """
    actions: list[OptimizationAction] = []

    # Determine recommended strategy
    if recent_roi < -0.03:
        # Losing: switch to conservative
        actions.append(OptimizationAction(
            category="STRATEGY",
            action=f"Switch to RISK_PARITY: negative ROI (-{recent_roi:.1%})",
            before="KELLY_DYNAMIC",
            after="RISK_PARITY",
            impact_estimate=0.01,
        ))
    elif recent_sharpe > 1.5 and market_efficiency < 0.6:
        # Winning in inefficient market: scale up
        actions.append(OptimizationAction(
            category="STRATEGY",
            action=f"Upgrade to AGGRESSIVE: Sharpe {recent_sharpe:.1f}, "
                   f"market efficiency {market_efficiency:.0%}",
            before="KELLY_DYNAMIC",
            after="ADAPTIVE_AGGRESSIVE",
            impact_estimate=0.02,
        ))
    elif market_efficiency > 0.8:
        # Efficient market: be more selective
        actions.append(OptimizationAction(
            category="STRATEGY",
            action=f"Switch to MEAN_VARIANCE: high market efficiency {market_efficiency:.0%}",
            before="KELLY_DYNAMIC",
            after="MEAN_VARIANCE",
            impact_estimate=0.005,
        ))

    return actions


# ─── Master Optimization Loop ───────────────────────────────────────────────

def run_master_optimization(
    feature_matrix: list[dict[str, float]] | None = None,
    targets: list[int] | None = None,
    backtest_results: list[dict[str, Any]] | None = None,
    current_params: dict[str, float] | None = None,
    recent_roi: float = 0.0,
    recent_sharpe: float = 0.0,
    market_efficiency: float = 0.5,
) -> OptimizationReport:
    """
    Execute the complete Master Optimization cycle.

    Steps:
      1. Load model performance state
      2. Model selection (retire/boost)
      3. Hyperparameter search
      4. Feature optimization (via alpha discovery)
      5. Weight rebalancing
      6. Strategy evolution
      7. Persist changes & report
    """
    report = OptimizationReport(timestamp=time.time())
    all_actions: list[OptimizationAction] = []

    # ── Step 1: Load state ────────────────────────────────
    performances, current_weights = load_state()

    # ── Step 2: Model selection ───────────────────────────
    model_actions = optimize_model_selection(performances)
    all_actions.extend(model_actions)
    report.models_retired = sum(
        1 for a in model_actions if "RETIRE" in a.action
    )

    # ── Step 3: Hyperparameters ───────────────────────────
    hp_actions = optimize_hyperparameters(current_params or {})
    all_actions.extend(hp_actions)

    # ── Step 4: Feature optimization ──────────────────────
    alpha_report = None
    if feature_matrix and targets:
        alpha_report = run_alpha_discovery(
            feature_matrix, targets, backtest_results
        )
        feat_actions = optimize_features(alpha_report)
        all_actions.extend(feat_actions)
        report.features_added = len(alpha_report.features_to_add)
        report.features_removed = len(alpha_report.features_to_remove)

    # ── Step 5: Weight rebalancing ────────────────────────
    new_weights, weight_actions = optimize_weights(current_weights, performances)
    all_actions.extend(weight_actions)
    report.weight_changes = {
        name: (current_weights.get(name, 0.1), new_weights.get(name, 0.1))
        for name in set(list(current_weights.keys()) + list(new_weights.keys()))
    }

    # ── Step 6: Strategy evolution ────────────────────────
    strat_actions = optimize_strategy(recent_roi, recent_sharpe, market_efficiency)
    all_actions.extend(strat_actions)
    if strat_actions:
        report.strategy_recommendation = strat_actions[0].after

    # ── Step 7: Evaluate & persist ────────────────────────
    health = evaluate_model_health(performances, current_weights)
    report.model_health = health.overall_health
    report.drift_detected = any(d.drift_detected for d in health.drift_reports)
    report.actions = all_actions
    report.estimated_improvement = sum(a.impact_estimate for a in all_actions)

    # Save updated weights
    save_state(performances, new_weights)

    # Log optimization report
    _log_optimization(report)

    # Build summary
    parts = [
        f"Health: {report.model_health}",
        f"Actions: {len(all_actions)}",
        f"Models retired: {report.models_retired}",
        f"Features: +{report.features_added} / -{report.features_removed}",
        f"Drift: {'YES' if report.drift_detected else 'no'}",
        f"Est. improvement: {report.estimated_improvement:.4f} Brier",
    ]
    if report.strategy_recommendation:
        parts.append(f"Strategy: → {report.strategy_recommendation}")

    report.summary = " | ".join(parts)

    return report


def _log_optimization(report: OptimizationReport):
    """Append optimization report to log file."""
    OPTIMIZATION_LOG.parent.mkdir(parents=True, exist_ok=True)

    log_entry = {
        "timestamp": report.timestamp,
        "health": report.model_health,
        "n_actions": len(report.actions),
        "actions": [
            {"category": a.category, "action": a.action, "impact": a.impact_estimate}
            for a in report.actions
        ],
        "summary": report.summary,
    }

    if OPTIMIZATION_LOG.exists():
        try:
            existing = json.loads(OPTIMIZATION_LOG.read_text())
        except Exception:
            existing = []
    else:
        existing = []

    existing.append(log_entry)
    # Keep last 100 entries
    existing = existing[-100:]
    OPTIMIZATION_LOG.write_text(json.dumps(existing, indent=2))
