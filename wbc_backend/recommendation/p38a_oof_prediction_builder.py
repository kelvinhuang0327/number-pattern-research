"""
P38A OOF Prediction Builder.

Walk-forward out-of-fold predictions using logistic regression.
Time-ordered folds, no shuffling, fixed random_state=42.

PAPER_ONLY=True
production_ready=False
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss

logger = logging.getLogger(__name__)

PAPER_ONLY: bool = True
PRODUCTION_READY: bool = False

MODEL_VERSION = "p38a_walk_forward_logistic_v1"
RANDOM_STATE = 42

# Minimum training samples before a fold can produce predictions
MIN_TRAIN_SAMPLES = 10


@dataclass(frozen=True)
class OOFMetrics:
    brier: float
    log_loss_val: float
    brier_skill_score: float  # vs base-rate (always-predict-mean) baseline
    base_rate: float
    n_predictions: int
    coverage_pct: float  # pct of input rows with a valid p_oof


@dataclass(frozen=True)
class OOFResult:
    predictions_df: pd.DataFrame  # game_id, fold_id, p_oof, model_version, source_prediction_ref, generated_without_y_true
    metrics: OOFMetrics
    output_hash: str  # SHA-256 of p_oof column sorted by game_id
    fold_count: int


def _feature_matrix(feature_df: pd.DataFrame) -> tuple[np.ndarray, list[str]]:
    """Extract sorted feature names and numpy matrix from pregame_features dicts."""
    feature_keys = sorted(
        set(k for features in feature_df["pregame_features"] for k in features)
    )
    X = np.array(
        [
            [row.get(k, 0.0) for k in feature_keys]
            for row in feature_df["pregame_features"]
        ],
        dtype=np.float64,
    )
    return X, feature_keys


def _source_prediction_ref(game_id: str, feature_row: dict[str, float]) -> str:
    """Stable hash of (game_id, sorted feature values) for audit trail."""
    payload = game_id + "|" + ",".join(f"{k}={v:.10f}" for k, v in sorted(feature_row.items()))
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def build_oof_predictions(
    feature_df: pd.DataFrame,
    y_true: pd.Series,
    n_folds: int = 10,
) -> OOFResult:
    """
    Time-ordered walk-forward OOF predictions.

    Args:
        feature_df: Output of p38a_retrosheet_feature_adapter (must include
                    game_date for ordering and pregame_features dict column).
        y_true: Binary outcome series (1 = home win), index-aligned with feature_df.
        n_folds: Number of temporal folds. Each fold trains on all prior data
                 and predicts on the next chunk.

    Returns:
        OOFResult with predictions and metrics.
    """
    if len(feature_df) != len(y_true):
        raise ValueError("feature_df and y_true must have the same length")

    # Sort chronologically
    sorted_idx = feature_df["game_date"].argsort() if hasattr(feature_df["game_date"].iloc[0], "__lt__") else feature_df["game_date"].argsort()
    df = feature_df.iloc[sorted_idx.values if hasattr(sorted_idx, "values") else sorted_idx].reset_index(drop=True)
    y = y_true.iloc[sorted_idx.values if hasattr(sorted_idx, "values") else sorted_idx].reset_index(drop=True)

    X, feature_keys = _feature_matrix(df)
    n = len(df)

    # Walk-forward split: fold k trains on [0, split_k) and predicts [split_k, split_{k+1})
    fold_size = n // n_folds
    fold_starts = [fold_size * i for i in range(1, n_folds + 1)]  # first fold trains on fold_size rows
    fold_starts[-1] = n  # ensure last fold covers remainder

    records: list[dict] = []
    fold_id = 0

    train_end = fold_size  # first train window
    for fold_idx in range(n_folds):
        pred_start = fold_size * (fold_idx + 1)
        if fold_idx < n_folds - 1:
            pred_end = fold_size * (fold_idx + 2)
        else:
            pred_end = n

        if pred_start >= n:
            break
        if train_end < MIN_TRAIN_SAMPLES:
            train_end = pred_end
            continue

        X_train = X[:train_end]
        y_train = y.iloc[:train_end].values

        # Skip fold if only one class in training labels
        if len(np.unique(y_train)) < 2:
            train_end = pred_end
            continue

        model = LogisticRegression(
            C=1.0,
            max_iter=1000,
            random_state=RANDOM_STATE,
            solver="lbfgs",
        )
        model.fit(X_train, y_train)

        X_pred = X[pred_start:pred_end]
        probs = model.predict_proba(X_pred)
        home_win_class_idx = list(model.classes_).index(1)
        p_oof_vals = probs[:, home_win_class_idx]

        for local_i, global_i in enumerate(range(pred_start, pred_end)):
            row = df.iloc[global_i]
            feat_row = row["pregame_features"]
            records.append(
                {
                    "game_id": str(row["game_id"]),
                    "fold_id": fold_id,
                    "p_oof": float(p_oof_vals[local_i]),
                    "model_version": MODEL_VERSION,
                    "source_prediction_ref": _source_prediction_ref(str(row["game_id"]), feat_row),
                    "generated_without_y_true": True,
                }
            )

        fold_id += 1
        train_end = pred_end

    predictions_df = pd.DataFrame(records)

    # Metrics
    n_total = len(df)
    n_predicted = len(predictions_df)
    coverage_pct = n_predicted / n_total * 100.0 if n_total > 0 else 0.0

    if n_predicted > 0:
        # Align y_true to predictions via game_id
        pred_game_ids = set(predictions_df["game_id"])
        mask = df["game_id"].astype(str).isin(pred_game_ids)
        y_aligned = y[mask.values].values
        p_aligned = predictions_df.set_index("game_id").loc[df[mask]["game_id"].astype(str), "p_oof"].values

        base_rate = float(np.mean(y_aligned))
        brier = float(brier_score_loss(y_aligned, p_aligned))
        ll = float(log_loss(y_aligned, p_aligned))

        # BSS = 1 - brier / brier_reference (reference = always predict base_rate)
        brier_ref = float(brier_score_loss(y_aligned, np.full_like(p_aligned, base_rate)))
        bss = 1.0 - brier / brier_ref if brier_ref > 0 else 0.0
    else:
        base_rate = 0.5
        brier = float("nan")
        ll = float("nan")
        bss = float("nan")

    metrics = OOFMetrics(
        brier=brier,
        log_loss_val=ll,
        brier_skill_score=bss,
        base_rate=base_rate,
        n_predictions=n_predicted,
        coverage_pct=coverage_pct,
    )

    # Deterministic hash of p_oof sorted by game_id
    if len(predictions_df) > 0:
        sorted_p = predictions_df.sort_values("game_id")["p_oof"]
        hash_payload = ",".join(f"{v:.10f}" for v in sorted_p).encode("utf-8")
        output_hash = hashlib.sha256(hash_payload).hexdigest()
    else:
        output_hash = hashlib.sha256(b"empty").hexdigest()

    logger.info(
        "P38A OOF build complete: %d/%d rows (%.1f%%), Brier=%.4f, BSS=%.4f",
        n_predicted,
        n_total,
        coverage_pct,
        brier if not isinstance(brier, float) or not (brier != brier) else -1,
        bss if not isinstance(bss, float) or not (bss != bss) else -1,
    )

    return OOFResult(
        predictions_df=predictions_df,
        metrics=metrics,
        output_hash=output_hash,
        fold_count=fold_id,
    )
