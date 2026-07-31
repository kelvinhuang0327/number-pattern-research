"""
XGBoost Win Probability Model

Gradient-boosted tree model for binary classification.
Auto-trains on historical data with cross-validation.
"""
from __future__ import annotations

import logging
import pickle
from pathlib import Path

import numpy as np

from wbc_backend.config.settings import ModelConfig
from wbc_backend.domain.schemas import SubModelResult, TrainingResult
from wbc_backend.features.advanced import FEATURE_NAMES

logger = logging.getLogger(__name__)

# Lazy import to handle optional dependency
_xgb = None


def _get_xgb():
    global _xgb
    if _xgb is None:
        try:
            import xgboost as xgb
            _xgb = xgb
        except ImportError:
            logger.warning("xgboost not installed, using fallback predictions")
            return None
    return _xgb


class XGBoostModel:
    def __init__(self, config: ModelConfig | None = None):
        self.config = config or ModelConfig()
        self.model = None
        self.feature_names = FEATURE_NAMES
        self.artifact_path = Path(self.config.xgb_params.get(
            "artifact_path",
            "data/wbc_backend/artifacts/xgb_model.pkl"
        ))

    def _expected_feature_count(self) -> int:
        return len(self.feature_names)

    def _extract_model(self, payload):
        if isinstance(payload, dict) and "model" in payload:
            return payload["model"], payload.get("feature_count")
        return payload, None

    def _infer_model_feature_count(self, model) -> int | None:
        for attr in ("n_features_in_", "feature_count_"):
            value = getattr(model, attr, None)
            if isinstance(value, (int, np.integer)):
                return int(value)
        feature_names = getattr(model, "feature_names_in_", None) or getattr(model, "feature_names", None)
        if feature_names is not None:
            return len(feature_names)
        return None

    def train(self, X: np.ndarray, y: np.ndarray) -> TrainingResult:
        """Train XGBoost model with cross-validation."""
        import time
        start = time.time()

        xgb = _get_xgb()
        if xgb is None:
            return self._fallback_training_result()

        from sklearn.model_selection import cross_val_score, StratifiedKFold

        params = {k: v for k, v in self.config.xgb_params.items()
                  if k != "artifact_path"}

        self.model = xgb.XGBClassifier(**params, use_label_encoder=False)
        self.model.fit(X, y, eval_set=[(X, y)], verbose=False)

        # Cross-validation scores
        cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
        cv_scores = cross_val_score(self.model, X, y, cv=cv, scoring="accuracy").tolist()

        # Predictions for metrics
        probs = self.model.predict_proba(X)[:, 1]
        preds = (probs >= 0.5).astype(int)

        accuracy = float(np.mean(preds == y))
        logloss = float(-np.mean(y * np.log(np.clip(probs, 1e-6, 1)) +
                                  (1 - y) * np.log(np.clip(1 - probs, 1e-6, 1))))
        brier = float(np.mean((probs - y) ** 2))

        # Feature importance
        importance = {}
        if hasattr(self.model, "feature_importances_"):
            for name, imp in zip(self.feature_names[:len(self.model.feature_importances_)],
                                  self.model.feature_importances_):
                importance[name] = round(float(imp), 4)

        # Save model
        self._save()

        elapsed = time.time() - start
        logger.info("XGBoost trained: acc=%.4f, logloss=%.4f, brier=%.4f, time=%.1fs",
                     accuracy, logloss, brier, elapsed)

        return TrainingResult(
            model_name="xgboost",
            accuracy=round(accuracy, 4),
            logloss=round(logloss, 4),
            brier_score=round(brier, 4),
            feature_importance=importance,
            training_time_seconds=round(elapsed, 1),
            n_samples=len(y),
            cv_scores=[round(s, 4) for s in cv_scores],
        )

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Return P(home_win) for each sample."""
        if self.model is None:
            self._load()
        if self.model is None:
            return np.full(len(X), 0.5)  # fallback
        return self.model.predict_proba(X)[:, 1]

    def predict_single(self, feature_dict: dict[str, float]) -> SubModelResult:
        """Predict for a single matchup using feature dict."""
        features = np.array([[feature_dict.get(f, 0.0) for f in self.feature_names]])
        prob = float(self.predict_proba(features)[0])

        return SubModelResult(
            model_name="xgboost",
            home_win_prob=round(prob, 4),
            away_win_prob=round(1.0 - prob, 4),
            confidence=0.7 if self.model is not None else 0.3,
            diagnostics={"xgb_raw_prob": round(prob, 4)},
        )

    def _save(self):
        self.artifact_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.artifact_path, "wb") as f:
            pickle.dump(
                {
                    "model": self.model,
                    "feature_count": self._expected_feature_count(),
                    "feature_names": list(self.feature_names),
                },
                f,
            )

    def _load(self):
        if self.artifact_path.exists():
            try:
                with open(self.artifact_path, "rb") as f:
                    payload = pickle.load(f)
                model, saved_count = self._extract_model(payload)
                actual_count = saved_count or self._infer_model_feature_count(model)
                if actual_count is not None and actual_count != self._expected_feature_count():
                    logger.info(
                        "Ignoring stale XGBoost artifact: features=%s expected=%s",
                        actual_count,
                        self._expected_feature_count(),
                    )
                    self.model = None
                    return
                self.model = model
            except Exception as e:
                logger.warning("Failed to load XGBoost model: %s", e)

    def _fallback_training_result(self) -> TrainingResult:
        return TrainingResult(
            model_name="xgboost",
            accuracy=0.0,
            logloss=999.0,
            brier_score=999.0,
        )
