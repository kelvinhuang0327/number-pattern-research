"""
Self-Improvement Module — § 九 自動優化機制

Provides:
  self_improve()  — automatic feature selection, model elimination, weight rebalancing

Methods:
  1. Auto feature selection (drop low-importance features)
  2. Model elimination (remove underperforming models)
  3. Weight redistribution (rebalance stacking weights)
"""
from __future__ import annotations

import logging
import json
from pathlib import Path


from wbc_backend.config.settings import AppConfig, SelfImproveConfig
from wbc_backend.domain.schemas import TrainingResult
from wbc_backend.optimization.continuous_learning import ContinuousLearningSystem

logger = logging.getLogger(__name__)

IMPROVEMENT_LOG_PATH = Path("data/wbc_backend/artifacts/improvement_log.json")


def _load_improvement_history() -> list[dict]:
    if IMPROVEMENT_LOG_PATH.exists():
        try:
            return json.loads(IMPROVEMENT_LOG_PATH.read_text())
        except Exception:
            return []
    return []


def _save_improvement_history(history: list[dict]):
    IMPROVEMENT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    IMPROVEMENT_LOG_PATH.write_text(json.dumps(history, indent=2))


def auto_feature_selection(
    training_results: list[TrainingResult],
    config: SelfImproveConfig,
) -> dict[str, bool]:
    """
    Identify features to keep/drop based on aggregate importance.

    Returns dict {feature_name: keep (True/False)}
    """
    # Aggregate feature importance across all models
    agg_importance: dict[str, float] = {}
    count: dict[str, int] = {}

    for result in training_results:
        for feat, imp in result.feature_importance.items():
            agg_importance[feat] = agg_importance.get(feat, 0) + imp
            count[feat] = count.get(feat, 0) + 1

    # Average importance
    for feat in agg_importance:
        agg_importance[feat] /= count[feat]

    # Identify features to drop
    threshold = config.feature_importance_threshold
    sorted_feats = sorted(agg_importance.items(), key=lambda x: x[1])

    feature_status = {}
    dropped = 0
    for feat, imp in sorted_feats:
        if imp < threshold and dropped < config.max_features_to_drop:
            feature_status[feat] = False  # drop
            dropped += 1
            logger.info("FEATURE DROP: %s (importance=%.4f < threshold=%.4f)",
                        feat, imp, threshold)
        else:
            feature_status[feat] = True  # keep

    logger.info("Feature selection: %d kept, %d dropped out of %d",
                sum(1 for v in feature_status.values() if v),
                sum(1 for v in feature_status.values() if not v),
                len(feature_status))

    return feature_status


def model_elimination(
    training_results: list[TrainingResult],
    brier_threshold: float = 0.30,
) -> dict[str, str]:
    """
    Identify models to eliminate or flag.

    Returns {model_name: "keep" | "warn" | "eliminate"}
    """
    status = {}

    for result in training_results:
        if result.model_name == "stacking":
            status[result.model_name] = "keep"
            continue

        if result.brier_score >= 999:
            status[result.model_name] = "eliminate"
            logger.warning("MODEL ELIMINATE: %s (not trained)", result.model_name)
        elif result.brier_score > brier_threshold:
            status[result.model_name] = "warn"
            logger.warning("MODEL WARN: %s (brier=%.4f > %.2f)",
                           result.model_name, result.brier_score, brier_threshold)
        else:
            status[result.model_name] = "keep"

    return status


def weight_redistribution(
    training_results: list[TrainingResult],
    model_status: dict[str, str],
) -> dict[str, float]:
    """
    Redistribute stacking weights based on model performance.

    Better-performing models get higher weights; eliminated models get 0.
    """
    eligible = [r for r in training_results
                if model_status.get(r.model_name) != "eliminate"
                and r.model_name != "stacking"
                and r.brier_score < 999]

    if not eligible:
        # All models eliminated or failed — use equal weights for base models
        return {"elo": 0.25, "poisson": 0.25, "bayesian": 0.25, "baseline": 0.25}

    # Inverse Brier score weighting
    inv_brier = {}
    for r in eligible:
        inv_brier[r.model_name] = 1.0 / max(r.brier_score, 0.01)

    total = sum(inv_brier.values())
    weights = {name: round(v / total, 4) for name, v in inv_brier.items()}

    # Add statistical models with default weights if not in ML results
    for base in ["elo", "poisson", "bayesian", "baseline"]:
        if base not in weights:
            weights[base] = round(0.15 / max(1, len(weights)), 4)

    # Renormalise
    total = sum(weights.values())
    weights = {k: round(v / total, 4) for k, v in weights.items()}

    logger.info("Weight redistribution: %s", weights)
    return weights


def self_improve(
    training_results: list[TrainingResult] | None = None,
    config: AppConfig | None = None,
) -> dict:
    """
    Run the full self-improvement pipeline:
      1. Auto feature selection
      2. Model elimination
      3. Weight redistribution
      4. Log improvements

    Returns summary dict.
    """
    config = config or AppConfig()
    si_config = config.self_improve

    logger.info("=" * 60)
    logger.info("🧬 SELF-IMPROVEMENT CYCLE")
    logger.info("=" * 60)

    # If no training results provided, run training
    if training_results is None:
        from wbc_backend.models.trainer import auto_train_models
        training_results = auto_train_models(config)

    # ── 1. Feature selection ─────────────────────────────
    feature_status = auto_feature_selection(training_results, si_config)

    # ── 2. Model elimination ─────────────────────────────
    model_status = model_elimination(
        training_results,
        config.model.model_eliminate_brier_threshold,
    )

    # ── 3. Weight redistribution ─────────────────────────
    new_weights = weight_redistribution(training_results, model_status)

    # ── 4. Log improvement cycle ─────────────────────────
    import datetime
    history = _load_improvement_history()
    cycle_log = {
        "timestamp": datetime.datetime.now().isoformat(),
        "features_kept": sum(1 for v in feature_status.values() if v),
        "features_dropped": sum(1 for v in feature_status.values() if not v),
        "model_status": model_status,
        "new_weights": new_weights,
        "training_metrics": {
            r.model_name: {
                "accuracy": r.accuracy,
                "logloss": r.logloss,
                "brier_score": r.brier_score,
            }
            for r in training_results
        },
    }
    history.append(cycle_log)
    _save_improvement_history(history)

    summary = {
        "feature_status": feature_status,
        "model_status": model_status,
        "new_weights": new_weights,
        "cycle_number": len(history),
    }

    # Attach continuous learning system health snapshot (Phase 8 runtime integration).
    try:
        cl = ContinuousLearningSystem()
        summary["continuous_learning"] = cl.get_system_report()
    except Exception as exc:
        logger.warning("Continuous learning snapshot unavailable: %s", exc)

    logger.info("Self-improvement cycle #%d complete.", len(history))
    logger.info("  Features: %d kept, %d dropped",
                cycle_log["features_kept"], cycle_log["features_dropped"])
    logger.info("  Models: %s", model_status)
    logger.info("  Weights: %s", new_weights)
    logger.info("=" * 60)

    return summary
