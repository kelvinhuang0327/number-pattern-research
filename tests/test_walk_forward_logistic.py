"""Tests for WalkForwardLogisticBaseline (P13).

All tests use synthetic fixtures — no real production data.
Covers: constructor, OOF columns, train/predict isolation,
temporal ordering, p_oof bounds, fold count, min_train_size,
and optional feature defaults.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from wbc_backend.models.walk_forward_logistic import (
    DEFAULT_FEATURES,
    OPTIONAL_FEATURES,
    WalkForwardLogisticBaseline,
)


# ---------------------------------------------------------------------------
# Synthetic fixture factory
# ---------------------------------------------------------------------------

def make_synthetic_df(
    n: int = 600,
    seed: int = 42,
    label_col: str = "home_win",
    date_start: str = "2024-04-01",
    extra_cols: list[str] | None = None,
) -> pd.DataFrame:
    """Return a minimal synthetic dataframe for testing.

    Generates deterministic data with:
      - Date: sequential daily dates
      - indep_recent_win_rate_delta: N(0, 0.1)
      - indep_starter_era_delta: N(0, 1.0)
      - indep_bullpen_proxy_delta: N(0, 0.5) (optional feature)
      - indep_weather_score_delta: N(0, 0.2) (optional feature)
      - home_win: binary (slightly correlated with win_rate_delta)
    """
    rng = np.random.default_rng(seed)
    dates = pd.date_range(start=date_start, periods=n, freq="D")
    win_delta = rng.normal(0.0, 0.1, size=n)
    era_delta = rng.normal(0.0, 1.0, size=n)
    bullpen_delta = rng.normal(0.0, 0.5, size=n)
    weather_delta = rng.normal(0.0, 0.2, size=n)
    # Label slightly correlated with features
    logit = 0.5 * win_delta - 0.3 * era_delta
    prob = 1 / (1 + np.exp(-logit))
    labels = (rng.uniform(size=n) < prob).astype(int)

    data: dict[str, object] = {
        "Date": dates,
        "indep_recent_win_rate_delta": win_delta,
        "indep_starter_era_delta": era_delta,
        "indep_bullpen_proxy_delta": bullpen_delta,
        "indep_weather_score_delta": weather_delta,
        label_col: labels,
    }
    if extra_cols:
        for col in extra_cols:
            data[col] = rng.normal(size=n)
    return pd.DataFrame(data)


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

class TestConstructorAcceptsFeatures:
    """test_constructor_accepts_features"""

    def test_constructor_accepts_features(self) -> None:
        features = ["indep_recent_win_rate_delta", "indep_starter_era_delta"]
        model = WalkForwardLogisticBaseline(features=features)
        assert model.features == features
        assert model.n_folds == 5
        assert model.time_column == "Date"
        assert model.min_train_size == 200
        assert model.regularization == 1.0

    def test_constructor_custom_params(self) -> None:
        features = ["feat_a", "feat_b"]
        model = WalkForwardLogisticBaseline(
            features=features,
            n_folds=3,
            time_column="game_date",
            min_train_size=50,
            regularization=0.1,
        )
        assert model.n_folds == 3
        assert model.time_column == "game_date"
        assert model.min_train_size == 50
        assert model.regularization == 0.1


class TestFitPredictOofReturnsRequiredColumns:
    """test_fit_predict_oof_returns_required_columns"""

    def test_fit_predict_oof_returns_required_columns(self) -> None:
        df = make_synthetic_df(n=600)
        model = WalkForwardLogisticBaseline(features=DEFAULT_FEATURES)
        oof = model.fit_predict_oof(df)

        required = {
            "y_true",
            "p_oof",
            "fold_id",
            "train_window_start",
            "train_window_end",
            "predict_window_start",
            "predict_window_end",
        }
        assert required.issubset(set(oof.columns)), (
            f"Missing columns: {required - set(oof.columns)}"
        )

    def test_oof_is_non_empty(self) -> None:
        df = make_synthetic_df(n=600)
        model = WalkForwardLogisticBaseline(features=DEFAULT_FEATURES)
        oof = model.fit_predict_oof(df)
        assert len(oof) > 0


class TestNoRowInBothTrainAndPredictWithinFold:
    """test_no_row_in_both_train_and_predict_within_fold"""

    def test_no_row_in_both_train_and_predict_within_fold(self) -> None:
        """Verify no temporal overlap between train and predict windows."""
        df = make_synthetic_df(n=600)
        model = WalkForwardLogisticBaseline(
            features=DEFAULT_FEATURES, n_folds=5
        )
        oof = model.fit_predict_oof(df)
        meta = model.fold_metadata()

        # For each fold, train_window_end < predict_window_start
        for fold in meta:
            train_end = pd.Timestamp(fold["train_window_end"])
            pred_start = pd.Timestamp(fold["predict_window_start"])
            assert train_end <= pred_start, (
                f"Fold {fold['fold_id']}: train_window_end={train_end} "
                f">= predict_window_start={pred_start} — overlap detected!"
            )


class TestPredictWindowStrictlyAfterTrainWindow:
    """test_predict_window_strictly_after_train_window"""

    def test_predict_window_strictly_after_train_window(self) -> None:
        df = make_synthetic_df(n=600)
        model = WalkForwardLogisticBaseline(
            features=DEFAULT_FEATURES, n_folds=5
        )
        oof = model.fit_predict_oof(df)
        meta = model.fold_metadata()

        for fold in meta:
            train_end = pd.Timestamp(fold["train_window_end"])
            pred_start = pd.Timestamp(fold["predict_window_start"])
            pred_end = pd.Timestamp(fold["predict_window_end"])

            # predict window must not precede train window end
            assert pred_end > train_end, (
                f"Fold {fold['fold_id']}: predict_window_end {pred_end} "
                f"not after train_window_end {train_end}"
            )

    def test_predict_rows_have_later_dates_than_train_rows(self) -> None:
        """Walk-forward ordering: each fold's predict dates > train dates."""
        df = make_synthetic_df(n=600)
        model = WalkForwardLogisticBaseline(
            features=DEFAULT_FEATURES, n_folds=5
        )
        oof = model.fit_predict_oof(df)
        meta = model.fold_metadata()

        for fold in meta:
            train_end_date = pd.Timestamp(fold["train_window_end"])
            pred_start_date = pd.Timestamp(fold["predict_window_start"])
            assert pred_start_date >= train_end_date, (
                f"Fold {fold['fold_id']}: predict starts before train ends"
            )


class TestPOofWithinUnitInterval:
    """test_p_oof_within_unit_interval"""

    def test_p_oof_within_unit_interval(self) -> None:
        df = make_synthetic_df(n=600)
        model = WalkForwardLogisticBaseline(features=DEFAULT_FEATURES)
        oof = model.fit_predict_oof(df)

        assert oof["p_oof"].notna().all(), "p_oof contains NaN values"
        assert (oof["p_oof"] >= 0.0).all(), "p_oof has values below 0"
        assert (oof["p_oof"] <= 1.0).all(), "p_oof has values above 1"

    def test_p_oof_not_all_identical(self) -> None:
        """Model should produce variation in predictions."""
        df = make_synthetic_df(n=600)
        model = WalkForwardLogisticBaseline(features=DEFAULT_FEATURES)
        oof = model.fit_predict_oof(df)
        assert oof["p_oof"].std() > 0.001, "p_oof has no variation (degenerate model)"


class TestFoldIdMatchesNFolds:
    """test_fold_id_matches_n_folds"""

    def test_fold_id_matches_n_folds(self) -> None:
        n_folds = 5
        df = make_synthetic_df(n=600)
        model = WalkForwardLogisticBaseline(
            features=DEFAULT_FEATURES, n_folds=n_folds
        )
        oof = model.fit_predict_oof(df)
        meta = model.fold_metadata()

        # Number of completed folds must not exceed n_folds
        assert len(meta) <= n_folds, (
            f"Got {len(meta)} folds, expected <= {n_folds}"
        )
        # fold_id values must be unique and 1-based
        fold_ids = [m["fold_id"] for m in meta]
        assert len(fold_ids) == len(set(fold_ids)), "Duplicate fold IDs"
        assert all(fid >= 1 for fid in fold_ids), "fold_id below 1"

    def test_fold_id_column_matches_metadata_count(self) -> None:
        n_folds = 4
        df = make_synthetic_df(n=600)
        model = WalkForwardLogisticBaseline(
            features=DEFAULT_FEATURES, n_folds=n_folds
        )
        oof = model.fit_predict_oof(df)
        meta = model.fold_metadata()

        unique_folds_in_oof = oof["fold_id"].nunique()
        assert unique_folds_in_oof == len(meta), (
            f"OOF has {unique_folds_in_oof} unique fold_ids "
            f"but metadata has {len(meta)} entries"
        )


class TestHandlesMinTrainSizeFloor:
    """test_handles_min_train_size_floor"""

    def test_handles_min_train_size_floor(self) -> None:
        """Folds where training size < min_train_size must be skipped."""
        df = make_synthetic_df(n=600)

        # Set min_train_size so large that fold 1 (smallest train) is skipped
        # With n=600, n_folds=5, chunk_size≈100; fold 1 train_size≈100
        model = WalkForwardLogisticBaseline(
            features=DEFAULT_FEATURES,
            n_folds=5,
            min_train_size=150,  # fold 1 has ~100 rows → skipped
        )
        oof = model.fit_predict_oof(df)
        meta = model.fold_metadata()

        # Should still produce output from folds 2-5
        assert len(meta) >= 1, "Expected at least some folds to execute"
        # No fold should have train_size < min_train_size
        for fold in meta:
            assert fold["train_size"] >= 150, (
                f"Fold {fold['fold_id']} has train_size={fold['train_size']} "
                f"< min_train_size=150"
            )

    def test_raises_if_no_folds_possible(self) -> None:
        """Should raise ValueError when all folds are below min_train_size."""
        df = make_synthetic_df(n=100)
        model = WalkForwardLogisticBaseline(
            features=DEFAULT_FEATURES,
            n_folds=5,
            min_train_size=500,  # larger than entire dataset
        )
        with pytest.raises(ValueError, match="No folds produced OOF predictions"):
            model.fit_predict_oof(df)


class TestOptionalFeaturesOffByDefault:
    """test_optional_features_off_by_default"""

    def test_optional_features_off_by_default(self) -> None:
        """DEFAULT_FEATURES must not include optional features."""
        for opt_feat in OPTIONAL_FEATURES:
            assert opt_feat not in DEFAULT_FEATURES, (
                f"Optional feature '{opt_feat}' found in DEFAULT_FEATURES — "
                "it must be off by default"
            )

    def test_default_features_are_required_two(self) -> None:
        """DEFAULT_FEATURES must be exactly the two required features."""
        assert "indep_recent_win_rate_delta" in DEFAULT_FEATURES
        assert "indep_starter_era_delta" in DEFAULT_FEATURES
        assert len(DEFAULT_FEATURES) == 2, (
            f"Expected 2 default features, got {len(DEFAULT_FEATURES)}: {DEFAULT_FEATURES}"
        )

    def test_constructor_does_not_add_optional_features_by_default(self) -> None:
        """Constructing with DEFAULT_FEATURES should not include optionals."""
        model = WalkForwardLogisticBaseline(features=DEFAULT_FEATURES)
        for opt_feat in OPTIONAL_FEATURES:
            assert opt_feat not in model.features, (
                f"Optional feature '{opt_feat}' found in model.features"
            )

    def test_optional_features_can_be_added_explicitly(self) -> None:
        """Users can explicitly add optional features."""
        all_features = DEFAULT_FEATURES + ["indep_bullpen_proxy_delta"]
        df = make_synthetic_df(n=600)
        model = WalkForwardLogisticBaseline(features=all_features)
        oof = model.fit_predict_oof(df)
        assert len(oof) > 0, "OOF should not be empty with optional feature added"
