from __future__ import annotations

from wbc_backend.prediction.mlb_ml_feature_matrix import build_ml_feature_matrix
from wbc_backend.prediction.mlb_walk_forward_model import (
    run_walk_forward_ml_candidate,
    train_logistic_regression_candidate,
)


def _rows(n: int = 240) -> list[dict]:
    rows: list[dict] = []
    for i in range(n):
        month = 3 + (i // 60)
        day = (i % 28) + 1
        target = 1.0 if (i % 5) in {0, 1, 2} else 0.0
        rows.append(
            {
                "Date": f"2025-{month:02d}-{day:02d}",
                "Home": "AAA",
                "Away": "BBB",
                "game_id": f"gid_{i}",
                "home_win": str(target),
                "Home Score": "5" if target >= 0.5 else "3",
                "Away Score": "3" if target >= 0.5 else "5",
                "Status": "Final",
                "Home ML": "-130",
                "Away ML": "+110",
                "raw_model_prob_before_p10": "0.52",
                "indep_recent_win_rate_delta": "0.2" if target >= 0.5 else "-0.2",
                "indep_starter_era_delta": "-0.3" if target >= 0.5 else "0.3",
                "indep_bullpen_proxy_delta": "0.0",
                "leakage_safe": "True",
            }
        )
    return rows


def test_train_logistic_regression_candidate_trains():
    matrix, meta = build_ml_feature_matrix(_rows(80), feature_policy="p13_v1")
    bundle = train_logistic_regression_candidate(
        matrix[:60], feature_columns=meta["features_used"]
    )
    assert bundle["training_status"] == "TRAINED"
    assert bundle["model_type"] == "logistic_regression"


def test_run_walk_forward_ml_candidate_outputs_probabilities():
    matrix, meta = build_ml_feature_matrix(_rows(), feature_policy="p13_v1")
    preds, run_meta = run_walk_forward_ml_candidate(
        matrix,
        feature_columns=meta["features_used"],
        min_train_size=60,
        initial_train_months=2,
    )
    assert preds
    assert run_meta["prediction_count"] > 0
    for p in preds[:20]:
        assert 0.0 <= float(p["model_prob_home"]) <= 1.0
        assert p["probability_source"] == "walk_forward_ml_candidate"
        assert p["leakage_safe"] is True

