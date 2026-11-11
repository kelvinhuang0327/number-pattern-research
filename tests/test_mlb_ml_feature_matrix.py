from __future__ import annotations

from wbc_backend.prediction.mlb_ml_feature_matrix import (
    build_ml_feature_matrix,
    split_walk_forward_folds,
)


def _rows() -> list[dict]:
    rows: list[dict] = []
    for i in range(120):
        month = 3 + (i // 30)
        day = (i % 28) + 1
        rows.append(
            {
                "Date": f"2025-{month:02d}-{day:02d}",
                "Home": "AAA",
                "Away": "BBB",
                "game_id": f"2025-{month:02d}-{day:02d}_AAA_BBB",
                "home_win": "1.0" if i % 2 == 0 else "0.0",
                "Home Score": "5" if i % 2 == 0 else "3",
                "Away Score": "3" if i % 2 == 0 else "5",
                "Status": "Final",
                "Home ML": "-130",
                "Away ML": "+110",
                "raw_model_prob_before_p10": "0.53",
                "indep_recent_win_rate_delta": "0.1",
                "indep_starter_era_delta": "-0.2",
                "indep_bullpen_proxy_delta": "0.0",
                "indep_rest_days_delta": "1.0",
                "indep_wind_kmh": "12.0",
                "indep_temp_c": "21.0",
                "leakage_safe": "True",
            }
        )
    return rows


def test_feature_matrix_includes_recent_and_starter():
    matrix, meta = build_ml_feature_matrix(_rows(), feature_policy="p13_v1")
    assert matrix
    assert "indep_recent_win_rate_delta" in meta["features_used"]
    assert "indep_starter_era_delta" in meta["features_used"]


def test_feature_matrix_excludes_rest_weather_by_default():
    _, meta = build_ml_feature_matrix(_rows(), feature_policy="p13_v1")
    assert "indep_rest_days_delta" in meta["features_excluded"]
    assert "indep_wind_kmh" in meta["features_excluded"]


def test_feature_matrix_leakage_safe_true():
    _, meta = build_ml_feature_matrix(_rows(), feature_policy="p13_v1")
    assert meta["leakage_safe"] is True


def test_walk_forward_folds_strict_train_end_before_validation_start():
    matrix, _ = build_ml_feature_matrix(_rows(), feature_policy="p13_v1")
    folds = split_walk_forward_folds(matrix, min_train_size=30, initial_train_months=2)
    assert folds
    for f in folds:
        assert f["train_end"] < f["validation_start"]
        assert f["leakage_safe"] is True

