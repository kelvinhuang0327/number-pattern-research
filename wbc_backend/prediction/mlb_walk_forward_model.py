"""
wbc_backend/prediction/mlb_walk_forward_model.py

P13: Walk-forward ML model candidate (logistic regression baseline).
"""
from __future__ import annotations

from statistics import mean
from typing import Any

from wbc_backend.prediction.mlb_ml_feature_matrix import split_walk_forward_folds


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def train_logistic_regression_candidate(
    train_rows: list[dict],
    *,
    feature_columns: list[str],
    target_col: str = "y_home_win",
) -> dict:
    """
    Fit logistic regression with train-fold-only standardization.
    """
    if not train_rows:
        return {"training_status": "NO_TRAIN_ROWS", "model_type": "logistic_regression"}
    if not feature_columns:
        return {"training_status": "NO_FEATURE_COLUMNS", "model_type": "logistic_regression"}

    try:
        import numpy as np
        from sklearn.linear_model import LogisticRegression
    except Exception as exc:
        return {
            "training_status": "SKLEARN_UNAVAILABLE",
            "model_type": "logistic_regression",
            "error": str(exc),
        }

    X = np.array([[ _as_float(r.get(c)) for c in feature_columns ] for r in train_rows], dtype=float)
    y = np.array([1 if _as_float(r.get(target_col), 0.0) >= 0.5 else 0 for r in train_rows], dtype=int)

    means = X.mean(axis=0)
    stds = X.std(axis=0)
    stds = np.where(stds < 1e-8, 1.0, stds)
    Xz = (X - means) / stds

    model = LogisticRegression(max_iter=1000, solver="lbfgs")
    model.fit(Xz, y)

    coef = model.coef_[0].tolist()
    intercept = float(model.intercept_[0])
    coef_summary = {
        "min_coef": min(coef) if coef else 0.0,
        "max_coef": max(coef) if coef else 0.0,
        "mean_abs_coef": mean(abs(c) for c in coef) if coef else 0.0,
    }
    return {
        "training_status": "TRAINED",
        "model_type": "logistic_regression",
        "feature_columns": feature_columns,
        "coefficients": coef,
        "intercept": intercept,
        "scaler_means": means.tolist(),
        "scaler_stds": stds.tolist(),
        "train_size": len(train_rows),
        "coefficient_summary": coef_summary,
        "_model_obj": model,
    }


def predict_model_candidate(
    model_bundle: dict,
    validation_rows: list[dict],
) -> list[float]:
    """
    Predict home-win probabilities from trained bundle.
    """
    if model_bundle.get("training_status") != "TRAINED":
        return []
    feature_columns = list(model_bundle.get("feature_columns") or [])
    if not feature_columns or not validation_rows:
        return []

    try:
        import numpy as np
    except Exception:
        return []

    model = model_bundle.get("_model_obj")
    if model is None:
        return []
    means = np.array(model_bundle.get("scaler_means"), dtype=float)
    stds = np.array(model_bundle.get("scaler_stds"), dtype=float)
    X = np.array([[ _as_float(r.get(c)) for c in feature_columns ] for r in validation_rows], dtype=float)
    Xz = (X - means) / stds
    probs = model.predict_proba(Xz)[:, 1]
    return [max(1e-6, min(1 - 1e-6, float(p))) for p in probs]


def run_walk_forward_ml_candidate(
    matrix_rows: list[dict],
    *,
    feature_columns: list[str],
    model_type: str = "logistic_regression",
    min_train_size: int = 300,
    initial_train_months: int = 2,
) -> tuple[list[dict], dict]:
    """
    Train/predict fold-by-fold and emit prediction rows + metadata.
    """
    if model_type != "logistic_regression":
        return [], {
            "fold_count": 0,
            "prediction_count": 0,
            "skipped_count": len(matrix_rows),
            "features_used": feature_columns,
            "model_type": model_type,
            "leakage_safe": True,
            "coefficient_summary": {},
            "training_failures": [f"unsupported model_type={model_type}"],
        }

    folds = split_walk_forward_folds(
        matrix_rows,
        min_train_size=min_train_size,
        initial_train_months=initial_train_months,
    )
    predictions: list[dict] = []
    training_failures: list[str] = []
    coefficient_summaries: list[dict] = []

    for fold in folds:
        train_rows = [matrix_rows[i] for i in fold["train_indices"]]
        val_rows = [matrix_rows[i] for i in fold["validation_indices"]]
        bundle = train_logistic_regression_candidate(
            train_rows,
            feature_columns=feature_columns,
            target_col="y_home_win",
        )
        if bundle.get("training_status") != "TRAINED":
            training_failures.append(
                f"{fold['fold_id']}:{bundle.get('training_status')}:{bundle.get('error','')}"
            )
            continue
        coefficient_summaries.append(bundle.get("coefficient_summary", {}))
        probs = predict_model_candidate(bundle, val_rows)
        for row, p in zip(val_rows, probs):
            predictions.append(
                {
                    "game_id": row.get("game_id"),
                    "date": row.get("date"),
                    "Date": row.get("Date"),
                    "home_team": row.get("home_team"),
                    "away_team": row.get("away_team"),
                    "Home": row.get("Home"),
                    "Away": row.get("Away"),
                    "home_win": row.get("y_home_win"),
                    "Home Score": row.get("Home Score"),
                    "Away Score": row.get("Away Score"),
                    "Status": row.get("Status", "Final"),
                    "Home ML": row.get("Home ML"),
                    "Away ML": row.get("Away ML"),
                    "model_prob_home": round(p, 6),
                    "model_prob_away": round(1.0 - p, 6),
                    "raw_model_prob_home": row.get("raw_model_prob_home"),
                    "probability_source": "walk_forward_ml_candidate",
                    "model_version": "p13_walk_forward_logistic_v1",
                    "ml_model_type": "logistic_regression",
                    "ml_feature_policy": row.get("ml_feature_policy", "p13_v1"),
                    "ml_features_used": ",".join(feature_columns),
                    "fold_id": fold["fold_id"],
                    "fold_train_start": fold["train_start"],
                    "fold_train_end": fold["train_end"],
                    "fold_validation_start": fold["validation_start"],
                    "fold_validation_end": fold["validation_end"],
                    "leakage_safe": True,
                    "source_trace": {
                        "probability_source": "walk_forward_ml_candidate",
                        "ml_model_type": "logistic_regression",
                        "ml_feature_policy": row.get("ml_feature_policy", "p13_v1"),
                        "ml_features_used": feature_columns,
                        "fold_id": fold["fold_id"],
                        "train_size": fold["train_size"],
                        "validation_size": fold["validation_size"],
                        "leakage_safe": True,
                    },
                }
            )

    meta = {
        "fold_count": len(folds),
        "prediction_count": len(predictions),
        "skipped_count": max(0, len(matrix_rows) - len(predictions)),
        "features_used": feature_columns,
        "model_type": model_type,
        "leakage_safe": True,
        "coefficient_summary": {
            "folds_trained": len(coefficient_summaries),
            "mean_abs_coef": (
                round(mean(s.get("mean_abs_coef", 0.0) for s in coefficient_summaries), 6)
                if coefficient_summaries
                else 0.0
            ),
        },
        "training_failures": training_failures,
    }
    return predictions, meta

