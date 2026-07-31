"""Walk-forward logistic regression baseline for P13.

Replaces P12's logit-correction base estimator with raw sklearn
LogisticRegression to break the BLOCKED_NEGATIVE_BSS pattern.

Design principles:
- Strict temporal train/predict separation (no leakage)
- StandardScaler fitted within each fold's train window only
- No row appears in both train and predict within a fold
- p_oof guaranteed in [0, 1], NaN-free
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler


# Default features from P12 best ablation variant 'no_rest'
DEFAULT_FEATURES: list[str] = [
    "indep_recent_win_rate_delta",
    "indep_starter_era_delta",
]

# Optional features (config-driven, OFF by default)
OPTIONAL_FEATURES: list[str] = [
    "indep_bullpen_proxy_delta",
    "indep_weather_score_delta",
]


class WalkForwardLogisticBaseline:
    """Walk-forward cross-validated logistic regression baseline.

    Implements expanding-window walk-forward cross-validation using
    sklearn LogisticRegression. Each fold trains on all data up to a
    temporal boundary and predicts strictly after that boundary.

    This class is the P13 replacement for the logit-correction estimator
    that caused BLOCKED_NEGATIVE_BSS across all 16 P12 ablation variants.

    Attributes:
        features: Feature column names used for training.
        n_folds: Number of walk-forward folds.
        time_column: Column used for temporal ordering.
        min_train_size: Minimum training rows required per fold.
        regularization: Inverse regularization strength C passed to
            LogisticRegression.
    """

    def __init__(
        self,
        features: list[str],
        n_folds: int = 5,
        time_column: str = "Date",
        min_train_size: int = 200,
        regularization: float = 1.0,
    ) -> None:
        """Initialize the walk-forward logistic baseline.

        Args:
            features: List of feature column names to use for training
                and prediction. Must be present in the dataframe passed
                to fit_predict_oof().
            n_folds: Number of walk-forward folds. The data timeline is
                divided into n_folds+1 equal chunks; fold i trains on
                chunks [0..i] and predicts on chunk [i+1].
            time_column: Column name for temporal ordering. Rows are
                sorted ascending by this column before splitting.
            min_train_size: Minimum number of training samples required
                for a fold to be executed. Folds with fewer training
                samples are skipped.
            regularization: Inverse regularization strength C for
                sklearn LogisticRegression. Larger values = less
                regularization.
        """
        self.features = list(features)
        self.n_folds = n_folds
        self.time_column = time_column
        self.min_train_size = min_train_size
        self.regularization = regularization
        self._fold_metadata: list[dict] = []

    def fit_predict_oof(
        self, df: pd.DataFrame, label_col: str = "home_win"
    ) -> pd.DataFrame:
        """Fit walk-forward folds and produce OOF predictions.

        Rows with NaN in any feature column or the label column are
        dropped before splitting. The temporal order is determined by
        time_column. StandardScaler is fitted exclusively on each fold's
        training window to prevent future-information leakage.

        No row will appear in both the train set and the predict set
        within the same fold.

        Args:
            df: Input dataframe containing feature columns, label column,
                and time column.
            label_col: Name of the binary outcome column (0 or 1).
                Rows where this column is NaN are dropped.

        Returns:
            DataFrame with the following columns:
                y_true: Actual label (0 or 1).
                p_oof: Predicted probability of home win (in [0, 1]).
                fold_id: 1-based fold index.
                train_window_start: Earliest date in fold's train set.
                train_window_end: Latest date in fold's train set.
                predict_window_start: Earliest date in fold's predict set.
                predict_window_end: Latest date in fold's predict set.
            Guaranteed: p_oof is NaN-free and in [0.0, 1.0].

        Raises:
            ValueError: If no folds produce predictions (data too small
                or min_train_size too large).
        """
        required_cols = self.features + [label_col, self.time_column]
        df_clean = df.dropna(subset=required_cols).copy()
        df_clean[self.time_column] = pd.to_datetime(df_clean[self.time_column])
        df_clean = df_clean.sort_values(self.time_column).reset_index(drop=True)

        n = len(df_clean)

        # Divide timeline into n_folds+1 equal-sized chunks by row index.
        # boundaries[k] = start index of chunk k.
        # Fold i (0-based): train = rows[:boundaries[i+1]],
        #                   predict = rows[boundaries[i+1]:boundaries[i+2]]
        n_chunks = self.n_folds + 1
        boundaries = [int(round(n * k / n_chunks)) for k in range(n_chunks + 1)]

        oof_rows: list[dict] = []
        self._fold_metadata = []

        for fold_idx in range(self.n_folds):
            train_end = boundaries[fold_idx + 1]
            pred_start = boundaries[fold_idx + 1]
            pred_end = boundaries[fold_idx + 2]

            # Guard: not enough training data
            if train_end < self.min_train_size:
                continue
            # Guard: empty predict window
            if pred_start >= pred_end:
                continue

            train_slice = df_clean.iloc[:train_end]
            pred_slice = df_clean.iloc[pred_start:pred_end]

            X_train = train_slice[self.features].values.astype(float)
            y_train = train_slice[label_col].values.astype(int)

            # Fit scaler on training window only
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)

            model = LogisticRegression(
                C=self.regularization,
                max_iter=1000,
                solver="lbfgs",
                random_state=42,
            )
            model.fit(X_train_scaled, y_train)

            X_pred = scaler.transform(pred_slice[self.features].values.astype(float))
            # predict_proba returns [P(class=0), P(class=1)]; take column for class=1
            proba = model.predict_proba(X_pred)
            # Find index corresponding to class label 1
            class_1_col = list(model.classes_).index(1) if 1 in model.classes_ else -1
            if class_1_col == -1:
                # Model never predicted class 1; assign 0.0 probability
                p_pred = np.zeros(len(pred_slice), dtype=float)
            else:
                p_pred = proba[:, class_1_col]

            train_window_start = df_clean[self.time_column].iloc[0]
            train_window_end = df_clean[self.time_column].iloc[train_end - 1]
            predict_window_start = df_clean[self.time_column].iloc[pred_start]
            predict_window_end = df_clean[self.time_column].iloc[pred_end - 1]

            for i in range(len(pred_slice)):
                oof_rows.append(
                    {
                        "y_true": int(pred_slice[label_col].iloc[i]),
                        "p_oof": float(p_pred[i]),
                        "fold_id": fold_idx + 1,
                        "train_window_start": train_window_start,
                        "train_window_end": train_window_end,
                        "predict_window_start": predict_window_start,
                        "predict_window_end": predict_window_end,
                    }
                )

            self._fold_metadata.append(
                {
                    "fold_id": fold_idx + 1,
                    "train_size": train_end,
                    "predict_size": pred_end - pred_start,
                    "train_window_start": str(train_window_start.date()),
                    "train_window_end": str(train_window_end.date()),
                    "predict_window_start": str(predict_window_start.date()),
                    "predict_window_end": str(predict_window_end.date()),
                }
            )

        if not oof_rows:
            raise ValueError(
                f"No folds produced OOF predictions. "
                f"Data size={n}, min_train_size={self.min_train_size}, "
                f"n_folds={self.n_folds}. "
                "Try reducing min_train_size or increasing data size."
            )

        oof_df = pd.DataFrame(oof_rows)

        # Invariant checks
        assert oof_df["p_oof"].notna().all(), "BUG: p_oof contains NaN"
        assert (oof_df["p_oof"] >= 0.0).all() and (
            oof_df["p_oof"] <= 1.0
        ).all(), "BUG: p_oof out of [0, 1]"

        return oof_df

    def fold_metadata(self) -> list[dict]:
        """Return metadata for each completed walk-forward fold.

        Must be called after fit_predict_oof(). Returns an empty list
        if fit_predict_oof() has not been called yet.

        Returns:
            List of dicts, one per completed fold, each containing:
                fold_id: 1-based fold index.
                train_size: Number of training samples in this fold.
                predict_size: Number of prediction samples in this fold.
                train_window_start: ISO date string of first training row.
                train_window_end: ISO date string of last training row.
                predict_window_start: ISO date string of first predict row.
                predict_window_end: ISO date string of last predict row.
        """
        return list(self._fold_metadata)
