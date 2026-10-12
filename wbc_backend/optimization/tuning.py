from __future__ import annotations

from dataclasses import asdict

import numpy as np

from wbc_backend.optimization.dataset import build_pregame_features, load_odds_results
from wbc_backend.optimization.modeling import FEATURE_COLUMNS
from wbc_backend.optimization.walkforward import run_walkforward_backtest

try:
    import optuna
except Exception:  # pragma: no cover
    optuna = None

try:
    from sklearn.model_selection import TimeSeriesSplit
except Exception:  # pragma: no cover
    TimeSeriesSplit = None

try:
    from xgboost import XGBClassifier
except Exception:  # pragma: no cover
    XGBClassifier = None


def _timeseries_logloss(path: str, params: dict) -> float:
    if TimeSeriesSplit is None or XGBClassifier is None:
        # fallback to walk-forward logloss if optional deps unavailable
        summary, _ = run_walkforward_backtest(
            path=path,
            min_train_games=240,
            retrain_every=params["retrain_every"],
            ev_threshold=params["ev_threshold"],
            lookback=params["lookback"],
            min_confidence=params["min_confidence"],
            markets=("ML",),
            calibration_method=params["calibration_method"],
        )
        return float(summary.logloss)

    raw = load_odds_results(path)
    df = build_pregame_features(raw, lookback=params["lookback"])
    x = np.nan_to_num(df[FEATURE_COLUMNS].to_numpy(dtype=float), nan=0.0, posinf=0.0, neginf=0.0)
    y = df["home_win"].to_numpy(dtype=int)

    tss = TimeSeriesSplit(n_splits=5)
    losses = []

    for tr_idx, va_idx in tss.split(x):
        x_tr, x_va = x[tr_idx], x[va_idx]
        y_tr, y_va = y[tr_idx], y[va_idx]

        model = XGBClassifier(
            learning_rate=params["learning_rate"],
            max_depth=params["max_depth"],
            subsample=params["subsample"],
            gamma=params["gamma"],
            n_estimators=300,
            objective="binary:logistic",
            eval_metric="logloss",
            random_state=42,
        )
        model.fit(x_tr, y_tr)
        p = np.clip(model.predict_proba(x_va)[:, 1], 1e-6, 1 - 1e-6)
        ll = float(-np.mean(y_va * np.log(p) + (1 - y_va) * np.log(1 - p)))
        losses.append(ll)

    return float(np.mean(losses))


def optimize_with_optuna(path: str, n_trials: int = 30) -> dict:
    if optuna is None:
        raise RuntimeError("optuna is not installed. Please install optuna to run hyperparameter search.")

    def objective(trial):
        params = {
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.25, log=True),
            "max_depth": trial.suggest_int("max_depth", 2, 8),
            "subsample": trial.suggest_float("subsample", 0.55, 1.0),
            "gamma": trial.suggest_float("gamma", 0.0, 5.0),
            "lookback": trial.suggest_int("lookback", 8, 24),
            "retrain_every": trial.suggest_int("retrain_every", 20, 80, step=10),
            "ev_threshold": trial.suggest_float("ev_threshold", 0.015, 0.06),
            "min_confidence": trial.suggest_float("min_confidence", 0.0, 0.1),
            "calibration_method": trial.suggest_categorical("calibration_method", ["platt", "isotonic"]),
        }

        logloss = _timeseries_logloss(path, params)
        summary, artifacts = run_walkforward_backtest(
            path=path,
            min_train_games=240,
            retrain_every=params["retrain_every"],
            ev_threshold=params["ev_threshold"],
            lookback=params["lookback"],
            min_confidence=params["min_confidence"],
            markets=("ML",),
            calibration_method=params["calibration_method"],
        )

        trial.set_user_attr("summary", asdict(summary))
        trial.set_user_attr("artifacts", artifacts)
        return logloss, float(summary.ml_roi)

    study = optuna.create_study(
        directions=["minimize", "maximize"],
        sampler=optuna.samplers.TPESampler(seed=42),
    )
    study.optimize(objective, n_trials=n_trials)

    pareto = []
    for t in study.best_trials:
        pareto.append(
            {
                "trial": t.number,
                "values": {"logloss": t.values[0], "roi": t.values[1]},
                "params": t.params,
                "summary": t.user_attrs.get("summary", {}),
                "artifacts": t.user_attrs.get("artifacts", {}),
            }
        )

    return {"pareto_front": pareto, "best_trials_count": len(pareto)}


def compare_calibration_methods(path: str) -> dict:
    base_params = {
        "retrain_every": 40,
        "ev_threshold": 0.03,
        "lookback": 12,
        "min_confidence": 0.0,
    }

    out = {}
    for method in ("platt", "isotonic"):
        summary, artifacts = run_walkforward_backtest(
            path=path,
            min_train_games=240,
            retrain_every=base_params["retrain_every"],
            ev_threshold=base_params["ev_threshold"],
            lookback=base_params["lookback"],
            min_confidence=base_params["min_confidence"],
            markets=("ML",),
            calibration_method=method,
        )
        out[method] = {
            "summary": asdict(summary),
            "odds_band_stats": artifacts.get("odds_band_stats", {}),
        }
    return out
