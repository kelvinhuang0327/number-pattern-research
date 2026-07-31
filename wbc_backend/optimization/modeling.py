from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit

try:
    from sklearn.isotonic import IsotonicRegression
except Exception:  # pragma: no cover
    IsotonicRegression = None


FEATURE_COLUMNS = [
    "elo_diff",
    "wr_diff",
    "rd_diff",
    "rf_diff",
    "ra_diff",
    "wr_5_diff",
    "wr_10_diff",
    "rf_5_diff",
    "rf_10_diff",
    "rf_var_5_diff",
    "rf_var_10_diff",
    "platoon_woba_diff",
    "starter_kbb_trend_diff",
    "starter_kbb_level_diff",
    "park_hr_factor",
    "park_run_factor",
    "bullpen_stress_diff",
]


@dataclass
class WinModel:
    coef: np.ndarray
    feature_names: list[str]


@dataclass
class PlattCalibrator:
    a: float
    b: float


@dataclass
class IsotonicCalibrator:
    model: Any


def _matrix(df: pd.DataFrame, feature_names: list[str]) -> np.ndarray:
    out = df[feature_names].to_numpy(dtype=float)
    return np.nan_to_num(out, nan=0.0, posinf=0.0, neginf=0.0)


def fit_logistic_model(train_df: pd.DataFrame, feature_names: list[str] | None = None) -> WinModel:
    feature_names = feature_names or FEATURE_COLUMNS
    x = _matrix(train_df, feature_names)
    y = train_df["home_win"].to_numpy(dtype=float)

    x_mean = x.mean(axis=0)
    x_std = np.where(x.std(axis=0) < 1e-8, 1.0, x.std(axis=0))
    z = (x - x_mean) / x_std
    z = np.hstack([np.ones((len(z), 1)), z])

    def loss(w: np.ndarray) -> float:
        p = expit(z @ w)
        p = np.clip(p, 1e-6, 1 - 1e-6)
        ll = -(y * np.log(p) + (1 - y) * np.log(1 - p)).mean()
        reg = 0.01 * np.sum(w[1:] ** 2)
        return ll + reg

    init = np.zeros(z.shape[1], dtype=float)
    res = minimize(loss, init, method="L-BFGS-B")
    coef = res.x.copy()
    merged = np.concatenate([coef, x_mean, x_std])
    return WinModel(coef=merged, feature_names=feature_names)


def predict_home_win_prob(model: WinModel, df: pd.DataFrame) -> np.ndarray:
    raw = _matrix(df, model.feature_names)
    p = raw.shape[1]
    w = model.coef[: p + 1]
    x_mean = model.coef[p + 1 : p + 1 + p]
    x_std = model.coef[p + 1 + p : p + 1 + 2 * p]
    z = (raw - x_mean) / x_std
    z = np.hstack([np.ones((len(z), 1)), z])
    return expit(z @ w)


def fit_platt(raw_prob: np.ndarray, y: np.ndarray) -> PlattCalibrator:
    raw_prob = np.clip(raw_prob, 1e-6, 1 - 1e-6)
    logits = np.log(raw_prob / (1 - raw_prob))

    def loss(ab: np.ndarray) -> float:
        a, b = ab
        p = expit(a * logits + b)
        p = np.clip(p, 1e-6, 1 - 1e-6)
        return -(y * np.log(p) + (1 - y) * np.log(1 - p)).mean()

    res = minimize(loss, np.array([1.0, 0.0]), method="L-BFGS-B")
    return PlattCalibrator(a=float(res.x[0]), b=float(res.x[1]))


def apply_platt(cal: PlattCalibrator, prob: np.ndarray) -> np.ndarray:
    prob = np.clip(prob, 1e-6, 1 - 1e-6)
    logits = np.log(prob / (1 - prob))
    return expit(cal.a * logits + cal.b)


def fit_isotonic(raw_prob: np.ndarray, y: np.ndarray) -> IsotonicCalibrator | None:
    if IsotonicRegression is None:
        return None
    model = IsotonicRegression(out_of_bounds="clip")
    model.fit(raw_prob, y)
    return IsotonicCalibrator(model=model)


def apply_isotonic(cal: IsotonicCalibrator | None, prob: np.ndarray) -> np.ndarray:
    if cal is None:
        return prob
    return np.clip(np.asarray(cal.model.predict(prob), dtype=float), 1e-6, 1 - 1e-6)


def poisson_prob_matrix(lambda_home: np.ndarray, lambda_away: np.ndarray, max_runs: int = 15) -> np.ndarray:
    from scipy.stats import poisson

    r = np.arange(max_runs + 1)
    ph = poisson.pmf(r[None, :], lambda_home[:, None])
    pa = poisson.pmf(r[None, :], lambda_away[:, None])
    return ph[:, :, None] * pa[:, None, :]
