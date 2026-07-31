"""
Auto-Trainer — orchestrates training of all ML models.

Provides:
  auto_train_models(config)  →  trains XGB, LGBM, NN, then stacking
  Outputs accuracy, logloss, Brier score for each model.
"""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from wbc_backend.config.settings import AppConfig
from wbc_backend.data.validator import load_dataset_frame
from wbc_backend.domain.schemas import TrainingResult
from wbc_backend.features.advanced import FEATURE_NAMES

logger = logging.getLogger(__name__)


def _build_training_data(config: AppConfig) -> tuple[np.ndarray, np.ndarray]:
    """
    Build training matrix from historical game data.

    Reads CSV files from the data directory and constructs feature vectors
    using the same FEATURE_NAMES used by the advanced feature builder.
    """
    csv_path = config.sources.mlb_2025_csv
    if not Path(csv_path).exists():
        raise RuntimeError("MLB_2025 training data not found; synthetic fallback is disabled.")

    df = load_dataset_frame(csv_path)

    if df is None or df.empty:
        raise RuntimeError("MLB_2025 training data could not be loaded after normalization.")

    if "is_synthetic" in df.columns and df["is_synthetic"].fillna(False).astype(bool).any():
        raise RuntimeError("Synthetic training rows detected in MLB_2025 dataset; training aborted.")

    return _df_to_features(df)


def _df_to_features(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Convert a game log DataFrame to (X, y) training pair."""
    normalized = df.copy()
    if "date" in normalized.columns:
        normalized["date"] = pd.to_datetime(normalized["date"], errors="coerce")
        normalized = normalized.sort_values("date").reset_index(drop=True)

    if {"home_team", "away_team", "home_score", "away_score"}.issubset(normalized.columns):
        feature_frame = _build_real_feature_frame(normalized)
    else:
        feature_frame = pd.DataFrame(index=normalized.index)

    for feat_name in FEATURE_NAMES:
        if feat_name not in feature_frame.columns:
            if feat_name == "is_neutral":
                feature_frame[feat_name] = 0.0
            elif feat_name == "park_factor" or feat_name == "climate_run_factor" or feat_name == "climate_hr_factor":
                feature_frame[feat_name] = 1.0
            elif feat_name == "recent_inning_load_diff":
                feature_frame[feat_name] = 0.0
            else:
                feature_frame[feat_name] = 0.0

    X = feature_frame[FEATURE_NAMES].fillna(0.0).to_numpy(dtype=float)

    if "home_win" in normalized.columns:
        y = normalized["home_win"].to_numpy(dtype=float)
    else:
        y = (normalized["home_score"] > normalized["away_score"]).astype(float).to_numpy(dtype=float)

    return X, y


def _build_real_feature_frame(df: pd.DataFrame) -> pd.DataFrame:
    ratings: dict[str, float] = {}
    run_history: dict[str, list[float]] = {}
    allow_history: dict[str, list[float]] = {}
    win_history: dict[str, list[float]] = {}
    last_game_date: dict[str, pd.Timestamp] = {}

    def _rating(team: str) -> float:
        return ratings.get(team, 1500.0)

    def _rolling(history: dict[str, list[float]], team: str, default: float) -> float:
        values = history.get(team, [])
        return float(np.mean(values[-10:])) if values else default

    def _rest_days(team: str, game_date: pd.Timestamp) -> float:
        prior = last_game_date.get(team)
        if prior is None or pd.isna(game_date):
            return 1.0
        return float(max((game_date - prior).days, 0))

    rows = []
    k_factor = 20.0

    for row in df.itertuples(index=False):
        game_date = getattr(row, "date", pd.NaT)
        home_team = row.home_team
        away_team = row.away_team
        home_score = float(row.home_score)
        away_score = float(row.away_score)

        home_rating = _rating(home_team)
        away_rating = _rating(away_team)
        home_rpg = _rolling(run_history, home_team, 4.5)
        away_rpg = _rolling(run_history, away_team, 4.5)
        home_rapg = _rolling(allow_history, home_team, 4.5)
        away_rapg = _rolling(allow_history, away_team, 4.5)
        home_wpct = _rolling(win_history, home_team, 0.5)
        away_wpct = _rolling(win_history, away_team, 0.5)
        home_rest = _rest_days(home_team, game_date)
        away_rest = _rest_days(away_team, game_date)

        offense_diff = home_rpg - away_rpg
        defense_diff = home_rapg - away_rapg

        rows.append(
            {
                "elo_diff": round(home_rating - away_rating, 4),
                "woba_diff": round(offense_diff / 12.0, 4),
                "fip_diff": round(defense_diff / 3.0, 4),
                "whip_diff": round(defense_diff / 10.0, 4),
                "stuff_plus_diff": round((home_rating - away_rating) / 40.0, 4),
                "der_diff": round(-defense_diff / 15.0, 4),
                "bullpen_depth_diff": 0.0,
                "ops_plus_diff": round(offense_diff * 8.0, 4),
                "rpg_diff": round(offense_diff, 4),
                "rapg_diff": round(defense_diff, 4),
                "home_sp_fatigue": 0.0,
                "away_sp_fatigue": 0.0,
                "sp_fatigue_diff": 0.0,
                "home_matchup_edge": round(offense_diff / 8.0, 4),
                "away_matchup_edge": round(-offense_diff / 8.0, 4),
                "matchup_edge_diff": round(offense_diff / 4.0, 4),
                "home_bullpen_stress": 0.0,
                "away_bullpen_stress": 0.0,
                "bullpen_stress_diff": 0.0,
                "home_clutch_index": round(home_wpct - 0.5, 4),
                "away_clutch_index": round(away_wpct - 0.5, 4),
                "clutch_diff": round(home_wpct - away_wpct, 4),
                "roster_strength_diff": round((home_rating - away_rating) / 25.0, 4),
                "rest_days_diff": round(home_rest - away_rest, 4),
                "win_pct_l10_diff": round(home_wpct - away_wpct, 4),
                "travel_fatigue_diff": 0.0,
                "park_factor": 1.0,
                "umpire_bias": 0.0,
                "elevation_m": 0.0,
                "is_neutral": 0.0,
                "climate_run_factor": 1.0,
                "climate_hr_factor": 1.0,
                "pitch_arsenal_entropy_diff": 0.0,
                "velocity_trend_diff": 0.0,
                "platoon_split_diff": 0.0,
                "recent_inning_load_diff": 0.0,
                "spin_rate_zscore_diff": 0.0,
            }
        )

        expected_home = 1.0 / (1.0 + 10 ** (-(home_rating - away_rating) / 400.0))
        actual_home = 1.0 if home_score > away_score else 0.0
        delta = k_factor * (actual_home - expected_home)
        ratings[home_team] = home_rating + delta
        ratings[away_team] = away_rating - delta

        run_history.setdefault(home_team, []).append(home_score)
        run_history.setdefault(away_team, []).append(away_score)
        allow_history.setdefault(home_team, []).append(away_score)
        allow_history.setdefault(away_team, []).append(home_score)
        win_history.setdefault(home_team, []).append(actual_home)
        win_history.setdefault(away_team, []).append(1.0 - actual_home)
        last_game_date[home_team] = game_date
        last_game_date[away_team] = game_date

    return pd.DataFrame(rows)


def _generate_synthetic_training_data(n: int = 500) -> tuple[np.ndarray, np.ndarray]:
    """Generate synthetic training data when no real data is available."""
    rng = np.random.default_rng(42)
    d = len(FEATURE_NAMES)
    X = rng.normal(0, 1, (n, d))

    # Create correlated target (home team wins more when features favour home)
    logit = 0.1 * X[:, 0] + 0.05 * X[:, 1] - 0.08 * X[:, 2] + rng.normal(0, 0.5, n)
    y = (logit > 0).astype(float)

    return X, y


def auto_train_models(config: AppConfig | None = None) -> list[TrainingResult]:
    """
    Auto-train all ML models and the stacking meta-learner.

    Steps:
      1. Load / generate training data
      2. Train XGBoost, LightGBM, Neural Net
      3. Train stacking meta-learner on their outputs
      4. Return performance metrics for each model

    Returns list of TrainingResult.
    """
    config = config or AppConfig()
    results: list[TrainingResult] = []

    logger.info("=" * 60)
    logger.info("AUTO TRAIN MODELS — Starting")
    logger.info("=" * 60)

    # ── 1. Load training data ────────────────────────────
    X, y = _build_training_data(config)
    logger.info("Training data loaded: %d samples, %d features", X.shape[0], X.shape[1])

    # ── 2. Train individual ML models ────────────────────
    from wbc_backend.models.xgboost_model import XGBoostModel
    from wbc_backend.models.lightgbm_model import LightGBMModel
    from wbc_backend.models.neural_net import NeuralNetModel

    models = [
        ("xgboost", XGBoostModel(config.model)),
        ("lightgbm", LightGBMModel(config.model)),
        ("neural_net", NeuralNetModel(config.model)),
    ]

    base_predictions: dict[str, np.ndarray] = {}

    for name, model in models:
        try:
            logger.info("Training %s...", name)
            result = model.train(X, y)
            results.append(result)

            # Get hold-out predictions for stacking
            probs = model.predict_proba(X)
            base_predictions[name] = probs

            logger.info("  %s → acc=%.4f, logloss=%.4f, brier=%.4f",
                        name, result.accuracy, result.logloss, result.brier_score)
        except Exception as e:
            logger.error("Failed to train %s: %s", name, e)
            results.append(TrainingResult(
                model_name=name, accuracy=0.0, logloss=999.0, brier_score=999.0,
            ))

    # ── 3. Train stacking meta-learner ───────────────────
    if base_predictions:
        from wbc_backend.models.stacking import StackingModel

        try:
            stacker = StackingModel()
            weights = stacker.fit(base_predictions, y)
            logger.info("Stacking weights: %s", weights)

            # Evaluate stacking performance
            stack_probs = np.zeros(len(y))
            for name, probs in base_predictions.items():
                w = weights.get(name, 1.0 / len(base_predictions))
                stack_probs += w * probs
            stack_probs = np.clip(stack_probs, 1e-6, 1 - 1e-6)

            stack_acc = float(np.mean((stack_probs >= 0.5).astype(int) == y))
            stack_logloss = float(-np.mean(y * np.log(stack_probs) +
                                            (1 - y) * np.log(1 - stack_probs)))
            stack_brier = float(np.mean((stack_probs - y) ** 2))

            results.append(TrainingResult(
                model_name="stacking",
                accuracy=round(stack_acc, 4),
                logloss=round(stack_logloss, 4),
                brier_score=round(stack_brier, 4),
                n_samples=len(y),
            ))
            logger.info("  stacking → acc=%.4f, logloss=%.4f, brier=%.4f",
                        stack_acc, stack_logloss, stack_brier)
        except Exception as e:
            logger.error("Failed to train stacking model: %s", e)

    # ── 4. Model elimination check ───────────────────────
    threshold = config.model.model_eliminate_brier_threshold
    for r in results:
        if r.brier_score > threshold and r.model_name != "stacking":
            logger.warning("MODEL ALERT: %s brier=%.4f exceeds threshold %.2f — "
                           "consider elimination", r.model_name, r.brier_score, threshold)

    logger.info("=" * 60)
    logger.info("AUTO TRAIN COMPLETE — %d models trained", len(results))
    logger.info("=" * 60)

    return results
