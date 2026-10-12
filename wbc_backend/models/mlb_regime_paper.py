from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from wbc_backend.mlb_data.governance import mlb_governance_flags
from wbc_backend.calibration.probability_calibrator import ProbabilityCalibrator
from wbc_backend.research.mlb_model_rebuild import build_mlb_rebuild_frame

from .mlb_moneyline import american_to_implied_prob


try:
    from sklearn.ensemble import GradientBoostingClassifier, HistGradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
except Exception:  # pragma: no cover
    GradientBoostingClassifier = None
    HistGradientBoostingClassifier = None
    LogisticRegression = None
    Pipeline = None
    StandardScaler = None


REGIME_WHITELIST = (
    "favorites",
    "small_edge",
    "weak_starter_mismatch",
    "heavy_bullpen_stress",
)

PAPER_EDGE_THRESHOLD = 0.01

REGIME_PRIORITY = (
    "weak_starter_mismatch",
    "favorites",
    "small_edge",
    "heavy_bullpen_stress",
)


def _brier(probs: np.ndarray, y: np.ndarray) -> float:
    return float(np.mean((probs - y) ** 2))


def _logloss(probs: np.ndarray, y: np.ndarray) -> float:
    eps = 1e-7
    return float(np.mean(-(y * np.log(np.clip(probs, eps, 1 - eps)) + (1 - y) * np.log(np.clip(1 - probs, eps, 1 - eps)))))


def _bet_metrics(probs: np.ndarray, market_probs: np.ndarray, y: np.ndarray, threshold: float = PAPER_EDGE_THRESHOLD) -> dict[str, float]:
    valid = np.isfinite(probs) & np.isfinite(market_probs) & np.isfinite(y)
    if not np.any(valid):
        return {"n_bets": 0, "roi": 0.0, "clv": 0.0}
    edge = probs[valid] - market_probs[valid]
    outcomes_y = y[valid]
    mask = np.abs(edge) >= threshold
    if not np.any(mask):
        return {"n_bets": 0, "roi": 0.0, "clv": 0.0}
    chosen_home = edge[mask] > 0
    wins = np.where(chosen_home, outcomes_y[mask] == 1, outcomes_y[mask] == 0)
    pnl = np.where(wins, 1.0, -1.0)
    return {
        "n_bets": int(np.sum(mask)),
        "roi": float(np.mean(pnl)),
        "clv": float(np.mean(np.abs(edge[mask]))),
    }


def _calibration_curve(probs: np.ndarray, y: np.ndarray, n_bins: int = 10) -> list[dict[str, Any]]:
    bins = np.linspace(0, 1, n_bins + 1)
    rows: list[dict[str, Any]] = []
    for i in range(n_bins):
        lo = bins[i]
        hi = bins[i + 1]
        mask = (probs >= lo) & (probs < hi if i < n_bins - 1 else probs <= hi)
        if not np.any(mask):
            continue
        pred_mean = float(np.mean(probs[mask]))
        actual_rate = float(np.mean(y[mask]))
        rows.append(
            {
                "bucket": f"{lo:.1f}-{hi:.1f}",
                "n": int(np.sum(mask)),
                "predicted_mean": round(pred_mean, 4),
                "actual_rate": round(actual_rate, 4),
                "abs_error": round(abs(pred_mean - actual_rate), 4),
            }
        )
    return rows


def _fold_roi_std(fold_ids: np.ndarray, probs: np.ndarray, market_probs: np.ndarray, y: np.ndarray) -> float:
    rois: list[float] = []
    for fold_id in sorted({int(v) for v in fold_ids if int(v) >= 0}):
        mask = fold_ids == fold_id
        metrics = _bet_metrics(probs[mask], market_probs[mask], y[mask], threshold=PAPER_EDGE_THRESHOLD)
        if metrics["n_bets"] > 0:
            rois.append(float(metrics["roi"]))
    return round(float(np.std(rois)) if rois else 0.0, 4)


def _safe_float(value: Any) -> float:
    try:
        if value is None:
            return np.nan
        return float(value)
    except Exception:
        return np.nan


def _feature_lookup(record: Any, key: str, default: float = np.nan) -> float:
    direct = getattr(record, key, None)
    if direct is not None:
        return _safe_float(direct)

    for container_name in ("mlb_features", "features", "team_features", "starter_features", "context_features"):
        container = getattr(record, container_name, None)
        if isinstance(container, dict) and key in container:
            return _safe_float(container.get(key))
    return default


def _dict_lookup(payload: dict[str, Any] | None, *keys: str) -> Any:
    if not isinstance(payload, dict):
        return None
    for key in keys:
        if key in payload:
            return payload.get(key)
    return None


def regime_feature_sets() -> dict[str, list[str]]:
    return {
        "favorites": [
            "market_home_prob",
            "market_abs_dev_50",
            "ou_line",
            "market_open_current_move",
            "market_open_close_move",
            "team_offense_diff",
            "team_pitching_diff",
            "bullpen_quality_diff",
            "rest_day_diff",
            "environment_run_proxy",
        ],
        "small_edge": [
            "market_abs_dev_50",
            "market_open_current_move",
            "market_open_close_move",
            "market_close_alignment_proxy",
            "market_disagreement_proxy",
            "team_offense_diff",
            "team_pitching_diff",
            "team_home_away_form_diff",
            "team_recent_run_diff_delta",
            "bullpen_quality_diff",
            "lineup_size_diff",
            "injury_count_diff",
            "rest_day_diff",
            "environment_run_proxy",
        ],
        "weak_starter_mismatch": [
            "market_home_prob",
            "market_abs_dev_50",
            "starter_recent_ra_diff",
            "starter_quality_diff",
            "starter_rest_diff",
            "starter_start_count_diff",
            "starter_workload_pressure_diff",
            "starter_form_blend_diff",
            "starter_matchup_depth_diff",
            "lineup_vs_starter_interaction_diff",
            "team_offense_diff",
            "bullpen_quality_diff",
            "injury_count_diff",
            "rest_day_diff",
        ],
        "heavy_bullpen_stress": [
            "market_home_prob",
            "market_abs_dev_50",
            "bullpen_usage_diff",
            "bullpen_usage_intensity_diff",
            "bullpen_quality_diff",
            "team_pitching_diff",
            "starter_quality_diff",
            "rest_day_diff",
            "weather_wind_kmh",
            "environment_run_proxy",
        ],
    }


@dataclass(frozen=True)
class RegimeGateConfig:
    favorite_cutoff: float
    small_edge_band: float
    weak_starter_cutoff: float
    heavy_bullpen_cutoff: float

    def as_dict(self) -> dict[str, float]:
        return {
            "favorite_cutoff": round(self.favorite_cutoff, 4),
            "small_edge_band": round(self.small_edge_band, 4),
            "weak_starter_cutoff": round(self.weak_starter_cutoff, 4),
            "heavy_bullpen_cutoff": round(self.heavy_bullpen_cutoff, 4),
        }


@dataclass(frozen=True)
class RegimeModelMetrics:
    regime: str
    model_family: str
    calibration: str
    n_games: int
    n_bets: int
    roi: float
    brier: float
    logloss: float
    clv: float
    fold_roi_std: float
    sample_count: int
    tradable: bool
    calibration_curve: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "regime": self.regime,
            "model_family": self.model_family,
            "calibration": self.calibration,
            "n_games": self.n_games,
            "n_bets": self.n_bets,
            "roi": self.roi,
            "brier": self.brier,
            "logloss": self.logloss,
            "clv": self.clv,
            "fold_roi_std": self.fold_roi_std,
            "sample_count": self.sample_count,
            "tradable": self.tradable,
            "calibration_curve": self.calibration_curve,
        }


@dataclass
class TrainedRegimeModel:
    regime: str
    model_family: str
    calibration: str
    feature_cols: list[str]
    medians: dict[str, float]
    estimator: Any
    calibrator: ProbabilityCalibrator | None
    historical_roi: float
    historical_clv: float
    historical_fold_std: float


@dataclass(frozen=True)
class PaperInference:
    execution_mode: str
    paper_side: str
    paper_regime: str
    paper_prob: float
    edge_vs_market: float
    applicable_regimes: list[str]
    paper_reason: str
    candidates: list[dict[str, Any]] = field(default_factory=list)


def derive_regime_gate_config(strict: pd.DataFrame) -> RegimeGateConfig:
    market_abs = np.abs(strict["market_home_prob"].to_numpy(dtype=float) - 0.5)
    starter_abs = np.abs(strict["starter_recent_ra_diff"].to_numpy(dtype=float))
    bullpen_abs = np.abs(strict["bullpen_usage_diff"].to_numpy(dtype=float))
    return RegimeGateConfig(
        favorite_cutoff=0.55,
        small_edge_band=float(np.nanmedian(market_abs)),
        weak_starter_cutoff=float(np.nanmedian(starter_abs)),
        heavy_bullpen_cutoff=float(np.nanmedian(bullpen_abs)),
    )


def classify_regimes_from_row(row: pd.Series | dict[str, Any], gate: RegimeGateConfig) -> list[str]:
    market = _safe_float(row["market_home_prob"] if isinstance(row, pd.Series) else row.get("market_home_prob"))
    starter = abs(_safe_float(row["starter_recent_ra_diff"] if isinstance(row, pd.Series) else row.get("starter_recent_ra_diff")))
    bullpen = abs(_safe_float(row["bullpen_usage_diff"] if isinstance(row, pd.Series) else row.get("bullpen_usage_diff")))
    regimes: list[str] = []
    if np.isfinite(market) and market >= gate.favorite_cutoff:
        regimes.append("favorites")
    if np.isfinite(market) and abs(market - 0.5) <= gate.small_edge_band:
        regimes.append("small_edge")
    if np.isfinite(starter) and starter < gate.weak_starter_cutoff:
        regimes.append("weak_starter_mismatch")
    if np.isfinite(bullpen) and bullpen >= gate.heavy_bullpen_cutoff:
        regimes.append("heavy_bullpen_stress")
    return [r for r in REGIME_WHITELIST if r in regimes]


def _build_estimator(model_family: str) -> Any:
    if model_family == "regularized_logistic":
        return Pipeline(
            [
                ("scaler", StandardScaler()),
                ("clf", LogisticRegression(C=0.35, penalty="l2", max_iter=800, solver="lbfgs")),
            ]
        )
    if model_family == "gradient_boosting":
        return GradientBoostingClassifier(n_estimators=180, learning_rate=0.04, max_depth=2, random_state=42)
    if model_family == "tree_boost_style":
        return HistGradientBoostingClassifier(max_depth=4, max_iter=220, learning_rate=0.045, random_state=42)
    raise ValueError(f"unsupported model family: {model_family}")


def _model_candidates(regime: str) -> tuple[str, ...]:
    if regime == "weak_starter_mismatch":
        return ("regularized_logistic", "tree_boost_style", "gradient_boosting")
    return ("regularized_logistic", "gradient_boosting", "tree_boost_style")


def _predict_proba(estimator: Any, x: pd.DataFrame) -> np.ndarray:
    probs = estimator.predict_proba(x)[:, 1]
    return np.asarray(probs, dtype=float)


def _fit_estimator(model_family: str, x_train: pd.DataFrame, y_train: np.ndarray) -> tuple[Any, dict[str, float]]:
    medians = {col: float(x_train[col].median()) for col in x_train.columns}
    estimator = _build_estimator(model_family)
    estimator.fit(x_train.fillna(medians), y_train)
    return estimator, medians


def _eval_calibration_set(probs: np.ndarray, y: np.ndarray) -> tuple[dict[str, Any], str]:
    candidates = {
        "raw": probs,
        "platt": np.asarray(ProbabilityCalibrator(method="platt").fit(probs.tolist(), y.tolist()).calibrate(probs.tolist()), dtype=float),
        "isotonic": np.asarray(ProbabilityCalibrator(method="isotonic" if len(y) >= 50 else "platt").fit(probs.tolist(), y.tolist()).calibrate(probs.tolist()), dtype=float),
    }
    metrics = {
        name: {
            "brier": _brier(arr, y),
            "logloss": _logloss(arr, y),
        }
        for name, arr in candidates.items()
    }
    best_name = min(metrics, key=lambda name: (metrics[name]["brier"], metrics[name]["logloss"]))
    return metrics, best_name


def _walk_forward_regime_eval(
    data: pd.DataFrame,
    regime: str,
    feature_cols: list[str],
    model_family: str,
    n_splits: int = 6,
) -> dict[str, Any]:
    subset = data[data["applicable_regimes"].apply(lambda regs: regime in regs)].copy().reset_index(drop=True)
    subset = subset[np.isfinite(subset["market_home_prob"])].reset_index(drop=True)
    n = len(subset)
    if n < 120:
        empty = RegimeModelMetrics(
            regime=regime,
            model_family=model_family,
            calibration="raw",
            n_games=0,
            n_bets=0,
            roi=0.0,
            brier=1.0,
            logloss=1.0,
            clv=0.0,
            fold_roi_std=0.0,
            sample_count=n,
            tradable=False,
            calibration_curve=[],
        )
        return {"metrics": empty, "predictions": pd.DataFrame(), "candidates": {}}

    split_size = max(25, n // n_splits)
    market = subset["market_home_prob"].to_numpy(dtype=float)
    y = subset["target"].to_numpy(dtype=int)
    raw_probs = np.full(n, np.nan, dtype=float)
    platt_probs = np.full(n, np.nan, dtype=float)
    isotonic_probs = np.full(n, np.nan, dtype=float)
    fold_ids = np.full(n, -1, dtype=int)

    for fold_id, start in enumerate(range(split_size, n, split_size)):
        end = min(n, start + split_size)
        cal_size = max(20, start // 5)
        core_end = max(40, start - cal_size)
        if core_end < 40 or end <= start:
            continue
        fit_frame = subset.loc[: core_end - 1, feature_cols]
        fit_y = y[:core_end]
        cal_frame = subset.loc[core_end:start - 1, feature_cols]
        cal_y = y[core_end:start]
        test_frame = subset.loc[start:end - 1, feature_cols]

        core_model, core_medians = _fit_estimator(model_family, fit_frame, fit_y)
        cal_raw = _predict_proba(core_model, cal_frame.fillna(core_medians))

        platt = ProbabilityCalibrator(method="platt").fit(cal_raw.tolist(), cal_y.tolist())
        isotonic_method = "isotonic" if len(cal_y) >= 50 else "platt"
        isotonic = ProbabilityCalibrator(method=isotonic_method).fit(cal_raw.tolist(), cal_y.tolist())

        final_model, final_medians = _fit_estimator(model_family, subset.loc[: start - 1, feature_cols], y[:start])
        test_raw = _predict_proba(final_model, test_frame.fillna(final_medians))
        raw_probs[start:end] = test_raw
        platt_probs[start:end] = np.asarray(platt.calibrate(test_raw.tolist()), dtype=float)
        isotonic_probs[start:end] = np.asarray(isotonic.calibrate(test_raw.tolist()), dtype=float)
        fold_ids[start:end] = fold_id

    eval_mask = fold_ids >= 0
    subset_eval = subset.loc[eval_mask].reset_index(drop=True)
    market_eval = market[eval_mask]
    y_eval = y[eval_mask]
    fold_eval = fold_ids[eval_mask]
    calibration_candidates = {
        "raw": raw_probs[eval_mask],
        "platt": platt_probs[eval_mask],
        "isotonic": isotonic_probs[eval_mask],
    }
    calibration_scores = {
        name: {
            "brier": round(_brier(arr, y_eval), 4),
            "logloss": round(_logloss(arr, y_eval), 4),
        }
        for name, arr in calibration_candidates.items()
    }
    best_calibration = min(calibration_scores, key=lambda name: (calibration_scores[name]["brier"], calibration_scores[name]["logloss"]))
    best_probs = calibration_candidates[best_calibration]
    decision = _bet_metrics(best_probs, market_eval, y_eval, threshold=PAPER_EDGE_THRESHOLD)
    fold_std = _fold_roi_std(fold_eval, best_probs, market_eval, y_eval)
    raw_baseline = calibration_scores["raw"]
    tradable = bool(
        decision["n_bets"] >= 50
        and decision["roi"] > 0
        and decision["clv"] > 0
        and fold_std < 0.15
        and (
            calibration_scores[best_calibration]["brier"] <= raw_baseline["brier"]
            or calibration_scores[best_calibration]["logloss"] <= raw_baseline["logloss"]
        )
    )
    metrics = RegimeModelMetrics(
        regime=regime,
        model_family=model_family,
        calibration=best_calibration,
        n_games=int(len(subset_eval)),
        n_bets=int(decision["n_bets"]),
        roi=round(float(decision["roi"]), 4),
        brier=round(float(calibration_scores[best_calibration]["brier"]), 4),
        logloss=round(float(calibration_scores[best_calibration]["logloss"]), 4),
        clv=round(float(decision["clv"]), 4),
        fold_roi_std=fold_std,
        sample_count=int(n),
        tradable=tradable,
        calibration_curve=_calibration_curve(best_probs, y_eval),
    )
    preds = subset_eval.loc[:, ["game_id", "game_date", "home_team", "away_team", "target", "market_home_prob"]].copy()
    preds["regime"] = regime
    preds["model_family"] = model_family
    preds["calibration"] = best_calibration
    preds["pred_home_prob"] = best_probs
    preds["edge"] = best_probs - preds["market_home_prob"].to_numpy(dtype=float)
    preds["paper_side"] = np.where(preds["edge"] > PAPER_EDGE_THRESHOLD, "home", np.where(preds["edge"] < -PAPER_EDGE_THRESHOLD, "away", "skip"))
    preds["fold_id"] = fold_eval
    return {
        "metrics": metrics,
        "predictions": preds,
        "candidates": calibration_scores,
    }


def _select_best_regime_model(results: list[dict[str, Any]]) -> dict[str, Any]:
    return max(
        results,
        key=lambda item: (
            1 if item["metrics"].tradable else 0,
            item["metrics"].roi,
            item["metrics"].clv,
            -item["metrics"].fold_roi_std,
            -item["metrics"].brier,
        ),
    )


def _fit_live_model(subset: pd.DataFrame, feature_cols: list[str], model_family: str, calibration: str) -> tuple[Any, dict[str, float], ProbabilityCalibrator | None]:
    n = len(subset)
    cal_size = max(20, n // 5)
    core_end = max(40, n - cal_size)
    fit_frame = subset.loc[: core_end - 1, feature_cols]
    fit_y = subset.loc[: core_end - 1, "target"].to_numpy(dtype=int)
    cal_frame = subset.loc[core_end:, feature_cols]
    cal_y = subset.loc[core_end:, "target"].to_numpy(dtype=int)

    core_model, core_medians = _fit_estimator(model_family, fit_frame, fit_y)
    cal_raw = _predict_proba(core_model, cal_frame.fillna(core_medians))
    calibrator = None
    if calibration != "raw":
        method = "isotonic" if calibration == "isotonic" and len(cal_y) >= 50 else "platt"
        calibrator = ProbabilityCalibrator(method=method).fit(cal_raw.tolist(), cal_y.tolist())

    full_model, full_medians = _fit_estimator(model_family, subset.loc[:, feature_cols], subset["target"].to_numpy(dtype=int))
    return full_model, full_medians, calibrator


def _make_record_feature_frame(record: Any) -> pd.DataFrame:
    odds = getattr(record, "odds", {}) or {}
    pitchers = getattr(record, "pitchers", {}) or {}
    lineups = getattr(record, "lineups", {}) or {}
    bullpen = getattr(record, "bullpen_usage", {}) or {}
    injury = getattr(record, "injury_report", {}) or {}
    weather = getattr(record, "weather", {}) or {}

    market_home_prob = _feature_lookup(record, "market_home_prob")
    if not np.isfinite(market_home_prob):
        market_home_prob = _safe_float(_dict_lookup(odds, "market_home_prob"))

    opening_home_prob = _feature_lookup(record, "opening_home_prob")
    if not np.isfinite(opening_home_prob):
        opening_home_prob = american_to_implied_prob(_dict_lookup(odds, "opening_home_ml", "open_home_ml"))
    current_home_prob = _feature_lookup(record, "current_home_prob")
    if not np.isfinite(current_home_prob):
        current_home_prob = american_to_implied_prob(_dict_lookup(odds, "current_home_ml"))
    if not np.isfinite(current_home_prob):
        current_home_prob = market_home_prob
    closing_home_prob = _feature_lookup(record, "closing_home_prob")
    if not np.isfinite(closing_home_prob):
        closing_home_prob = american_to_implied_prob(_dict_lookup(odds, "closing_home_ml", "home_ml"))
    if not np.isfinite(closing_home_prob):
        closing_home_prob = market_home_prob

    home_lineup = _dict_lookup(lineups, "confirmed_home_lineup", "home_lineup", "home")
    away_lineup = _dict_lookup(lineups, "confirmed_away_lineup", "away_lineup", "away")
    home_lineup = home_lineup if isinstance(home_lineup, list) else []
    away_lineup = away_lineup if isinstance(away_lineup, list) else []

    home_inactive = _dict_lookup(injury, "home_inactive") or []
    away_inactive = _dict_lookup(injury, "away_inactive") or []
    home_inactive = home_inactive if isinstance(home_inactive, list) else []
    away_inactive = away_inactive if isinstance(away_inactive, list) else []

    home_left = _safe_float(_dict_lookup(lineups, "home_left_count", "home_left"))
    home_right = _safe_float(_dict_lookup(lineups, "home_right_count", "home_right"))
    away_left = _safe_float(_dict_lookup(lineups, "away_left_count", "away_left"))
    away_right = _safe_float(_dict_lookup(lineups, "away_right_count", "away_right"))
    if not np.isfinite(home_left):
        home_left = float(sum(1 for p in home_lineup if isinstance(p, dict) and str(p.get("bat_side", "")).upper().startswith("L")))
    if not np.isfinite(home_right):
        home_right = float(sum(1 for p in home_lineup if isinstance(p, dict) and str(p.get("bat_side", "")).upper().startswith("R")))
    if not np.isfinite(away_left):
        away_left = float(sum(1 for p in away_lineup if isinstance(p, dict) and str(p.get("bat_side", "")).upper().startswith("L")))
    if not np.isfinite(away_right):
        away_right = float(sum(1 for p in away_lineup if isinstance(p, dict) and str(p.get("bat_side", "")).upper().startswith("R")))

    home_rest = _feature_lookup(record, "home_rest_days")
    away_rest = _feature_lookup(record, "away_rest_days")
    if not np.isfinite(home_rest):
        home_rest = _safe_float(_dict_lookup(injury, "rest_days_home", "home_rest_days"))
    if not np.isfinite(away_rest):
        away_rest = _safe_float(_dict_lookup(injury, "rest_days_away", "away_rest_days"))

    home_woba = _feature_lookup(record, "home_woba")
    away_woba = _feature_lookup(record, "away_woba")
    home_fip = _feature_lookup(record, "home_fip")
    away_fip = _feature_lookup(record, "away_fip")

    starter_home_ra = _feature_lookup(record, "home_starter_recent_ra")
    starter_away_ra = _feature_lookup(record, "away_starter_recent_ra")
    if not np.isfinite(starter_home_ra):
        starter_home_ra = _safe_float(_dict_lookup(pitchers, "home_recent_ra", "home_starter_recent_ra"))
    if not np.isfinite(starter_away_ra):
        starter_away_ra = _safe_float(_dict_lookup(pitchers, "away_recent_ra", "away_starter_recent_ra"))
    starter_home_quality = _feature_lookup(record, "home_starter_quality")
    starter_away_quality = _feature_lookup(record, "away_starter_quality")
    if not np.isfinite(starter_home_quality):
        starter_home_quality = _safe_float(_dict_lookup(pitchers, "home_quality", "home_starter_quality"))
    if not np.isfinite(starter_away_quality):
        starter_away_quality = _safe_float(_dict_lookup(pitchers, "away_quality", "away_starter_quality"))
    starter_home_rest = _feature_lookup(record, "home_starter_rest")
    starter_away_rest = _feature_lookup(record, "away_starter_rest")
    if not np.isfinite(starter_home_rest):
        starter_home_rest = _safe_float(_dict_lookup(pitchers, "home_rest", "home_starter_rest"))
    if not np.isfinite(starter_away_rest):
        starter_away_rest = _safe_float(_dict_lookup(pitchers, "away_rest", "away_starter_rest"))
    starter_home_count = _feature_lookup(record, "home_starter_start_count")
    starter_away_count = _feature_lookup(record, "away_starter_start_count")
    if not np.isfinite(starter_home_count):
        starter_home_count = _safe_float(_dict_lookup(pitchers, "home_start_count", "home_starter_start_count"))
    if not np.isfinite(starter_away_count):
        starter_away_count = _safe_float(_dict_lookup(pitchers, "away_start_count", "away_starter_start_count"))

    bullpen_home = _feature_lookup(record, "bullpen_usage_last_3d_home")
    bullpen_away = _feature_lookup(record, "bullpen_usage_last_3d_away")
    if not np.isfinite(bullpen_home):
        bullpen_home = _safe_float(_dict_lookup(bullpen, "home_last_3d", "bullpen_usage_last_3d_home"))
    if not np.isfinite(bullpen_away):
        bullpen_away = _safe_float(_dict_lookup(bullpen, "away_last_3d", "bullpen_usage_last_3d_away"))

    temp_c = _feature_lookup(record, "weather_temp_c")
    wind_kmh = _feature_lookup(record, "weather_wind_kmh")
    if not np.isfinite(temp_c):
        temp_c = _safe_float(_dict_lookup(weather, "temp_c_avg", "temp_c"))
    if not np.isfinite(wind_kmh):
        wind_kmh = _safe_float(_dict_lookup(weather, "wind_kmh_avg", "wind_kmh"))
    roof_type = str(_dict_lookup(weather, "roof_type") or "").lower()
    venue_name = str(_dict_lookup(weather, "venue_name") or "").lower()
    dome_flag = float(("dome" in roof_type) or ("dome" in venue_name))
    open_air_flag = float((roof_type == "open") or (not dome_flag and roof_type == ""))

    team_offense_diff = _feature_lookup(record, "team_offense_diff")
    if not np.isfinite(team_offense_diff) and np.isfinite(home_woba) and np.isfinite(away_woba):
        team_offense_diff = (home_woba - away_woba) * 10.0
    team_pitching_diff = _feature_lookup(record, "team_pitching_diff")
    if not np.isfinite(team_pitching_diff) and np.isfinite(home_fip) and np.isfinite(away_fip):
        team_pitching_diff = away_fip - home_fip

    market_abs_dev_50 = abs(market_home_prob - 0.5) if np.isfinite(market_home_prob) else np.nan
    market_open_current_move = current_home_prob - opening_home_prob if np.isfinite(current_home_prob) and np.isfinite(opening_home_prob) else np.nan
    market_open_close_move = closing_home_prob - opening_home_prob if np.isfinite(closing_home_prob) and np.isfinite(opening_home_prob) else np.nan
    market_close_alignment_proxy = abs(closing_home_prob - current_home_prob) if np.isfinite(closing_home_prob) and np.isfinite(current_home_prob) else np.nan
    market_disagreement_proxy = abs(current_home_prob - opening_home_prob) if np.isfinite(current_home_prob) and np.isfinite(opening_home_prob) else np.nan
    starter_recent_ra_diff = starter_away_ra - starter_home_ra if np.isfinite(starter_home_ra) and np.isfinite(starter_away_ra) else np.nan
    starter_quality_diff = starter_home_quality - starter_away_quality if np.isfinite(starter_home_quality) and np.isfinite(starter_away_quality) else np.nan
    starter_rest_diff = starter_home_rest - starter_away_rest if np.isfinite(starter_home_rest) and np.isfinite(starter_away_rest) else np.nan
    starter_start_count_diff = starter_home_count - starter_away_count if np.isfinite(starter_home_count) and np.isfinite(starter_away_count) else np.nan
    starter_workload_pressure_diff = (
        (starter_away_count / max(starter_away_rest, 1.0)) - (starter_home_count / max(starter_home_rest, 1.0))
        if np.isfinite(starter_home_count) and np.isfinite(starter_away_count) and np.isfinite(starter_home_rest) and np.isfinite(starter_away_rest)
        else np.nan
    )
    starter_form_blend_diff = starter_quality_diff + 0.50 * starter_recent_ra_diff if np.isfinite(starter_quality_diff) and np.isfinite(starter_recent_ra_diff) else np.nan
    platoon_balance_diff = (home_left - home_right) - (away_left - away_right)
    starter_matchup_depth_diff = team_offense_diff + starter_recent_ra_diff + 0.15 * platoon_balance_diff if np.isfinite(team_offense_diff) and np.isfinite(starter_recent_ra_diff) else np.nan
    lineup_vs_starter_interaction_diff = (
        ((len(home_lineup) - len(home_inactive)) / 9.0) * starter_away_ra
        - ((len(away_lineup) - len(away_inactive)) / 9.0) * starter_home_ra
        if np.isfinite(starter_home_ra) and np.isfinite(starter_away_ra)
        else np.nan
    )
    bullpen_quality_diff = _feature_lookup(record, "bullpen_quality_diff")
    if not np.isfinite(bullpen_quality_diff) and np.isfinite(team_pitching_diff) and np.isfinite(starter_recent_ra_diff):
        bullpen_quality_diff = team_pitching_diff - starter_recent_ra_diff
    bullpen_usage_diff = bullpen_away - bullpen_home if np.isfinite(bullpen_home) and np.isfinite(bullpen_away) else np.nan
    bullpen_usage_intensity_diff = (
        (bullpen_away / max(away_rest + 1.0, 1.0)) - (bullpen_home / max(home_rest + 1.0, 1.0))
        if np.isfinite(bullpen_home) and np.isfinite(bullpen_away) and np.isfinite(home_rest) and np.isfinite(away_rest)
        else np.nan
    )
    environment_run_proxy = (temp_c / 30.0) + (wind_kmh / 25.0) - dome_flag * 0.20 if np.isfinite(temp_c) and np.isfinite(wind_kmh) else np.nan

    row = {
        "market_home_prob": market_home_prob,
        "market_abs_dev_50": market_abs_dev_50,
        "ou_line": _feature_lookup(record, "ou_line"),
        "market_open_current_move": market_open_current_move,
        "market_open_close_move": market_open_close_move,
        "market_close_alignment_proxy": market_close_alignment_proxy,
        "market_disagreement_proxy": market_disagreement_proxy,
        "team_offense_diff": team_offense_diff,
        "team_pitching_diff": team_pitching_diff,
        "team_home_away_form_diff": _feature_lookup(record, "team_home_away_form_diff"),
        "team_recent_run_diff_delta": _feature_lookup(record, "team_recent_run_diff_delta"),
        "bullpen_quality_diff": bullpen_quality_diff,
        "lineup_size_diff": float(len(home_lineup) - len(away_lineup)),
        "injury_count_diff": float(len(away_inactive) - len(home_inactive)),
        "rest_day_diff": home_rest - away_rest if np.isfinite(home_rest) and np.isfinite(away_rest) else np.nan,
        "environment_run_proxy": environment_run_proxy,
        "starter_recent_ra_diff": starter_recent_ra_diff,
        "starter_quality_diff": starter_quality_diff,
        "starter_rest_diff": starter_rest_diff,
        "starter_start_count_diff": starter_start_count_diff,
        "starter_workload_pressure_diff": starter_workload_pressure_diff,
        "starter_form_blend_diff": starter_form_blend_diff,
        "starter_matchup_depth_diff": starter_matchup_depth_diff,
        "lineup_vs_starter_interaction_diff": lineup_vs_starter_interaction_diff,
        "bullpen_usage_diff": bullpen_usage_diff,
        "bullpen_usage_intensity_diff": bullpen_usage_intensity_diff,
        "weather_wind_kmh": wind_kmh,
    }
    return pd.DataFrame([row])


def _record_is_strict_valid(record: Any) -> bool:
    tier = getattr(record, "mlb_validity_tier", None) or getattr(record, "validity_tier", None)
    if isinstance(tier, str) and tier.upper() == "STRICT_VALID":
        return True
    return bool(getattr(record, "strict_valid", False))


class MLBRegimePaperSystem:
    def __init__(self, gate_config: RegimeGateConfig, trained_models: dict[str, TrainedRegimeModel], report: dict[str, Any]):
        self.gate_config = gate_config
        self.trained_models = trained_models
        self.report = report

    def predict_record(self, record: Any) -> PaperInference:
        if not _record_is_strict_valid(record):
            return PaperInference(
                execution_mode="PAPER_ONLY",
                paper_side="skip",
                paper_regime="",
                paper_prob=float(getattr(record, "market_home_prob", 0.5) or 0.5),
                edge_vs_market=0.0,
                applicable_regimes=[],
                paper_reason="strict_validation_failed_or_missing",
                candidates=[],
            )

        row = _make_record_feature_frame(record)
        applicable = classify_regimes_from_row(row.iloc[0], self.gate_config)
        if not applicable:
            return PaperInference(
                execution_mode="PAPER_ONLY",
                paper_side="skip",
                paper_regime="",
                paper_prob=float(np.clip(row.iloc[0]["market_home_prob"], 0.01, 0.99)) if np.isfinite(row.iloc[0]["market_home_prob"]) else 0.5,
                edge_vs_market=0.0,
                applicable_regimes=[],
                paper_reason="regime_not_whitelisted",
                candidates=[],
            )

        candidates: list[dict[str, Any]] = []
        market_home_prob = float(row.iloc[0]["market_home_prob"]) if np.isfinite(row.iloc[0]["market_home_prob"]) else 0.5
        for regime in applicable:
            trained = self.trained_models.get(regime)
            if trained is None:
                continue
            feature_slice = row.loc[:, trained.feature_cols]
            if not np.isfinite(feature_slice.to_numpy(dtype=float)).all():
                continue
            raw = _predict_proba(trained.estimator, feature_slice.fillna(trained.medians))[0]
            prob = float(raw)
            if trained.calibrator is not None:
                prob = float(trained.calibrator.calibrate([prob])[0])
            edge = prob - market_home_prob
            candidates.append(
                {
                    "regime": regime,
                    "paper_prob": round(prob, 4),
                    "edge_vs_market": round(edge, 4),
                    "paper_side": "home" if edge > PAPER_EDGE_THRESHOLD else ("away" if edge < -PAPER_EDGE_THRESHOLD else "skip"),
                    "historical_roi": round(trained.historical_roi, 4),
                    "historical_clv": round(trained.historical_clv, 4),
                    "historical_fold_std": round(trained.historical_fold_std, 4),
                }
            )

        if not candidates:
            return PaperInference(
                execution_mode="PAPER_ONLY",
                paper_side="skip",
                paper_regime="",
                paper_prob=market_home_prob,
                edge_vs_market=0.0,
                applicable_regimes=applicable,
                paper_reason="missing_live_features_for_regime_models",
                candidates=[],
            )

        chosen = max(
            candidates,
            key=lambda item: (
                1 if item["paper_side"] != "skip" else 0,
                abs(item["edge_vs_market"]),
                item["historical_roi"],
                -item["historical_fold_std"],
                -REGIME_PRIORITY.index(item["regime"]) if item["regime"] in REGIME_PRIORITY else -99,
            ),
        )
        reason = "paper_pick_available" if chosen["paper_side"] != "skip" else "all_regime_edges_below_threshold"
        return PaperInference(
            execution_mode="PAPER_ONLY",
            paper_side=str(chosen["paper_side"]),
            paper_regime=str(chosen["regime"]),
            paper_prob=float(chosen["paper_prob"]),
            edge_vs_market=float(chosen["edge_vs_market"]),
            applicable_regimes=applicable,
            paper_reason=reason,
            candidates=candidates,
        )


def run_mlb_regime_paper_mode(
    *,
    csv_path: str = "data/mlb_2025/mlb_odds_2025_real.csv",
    context_path: str | None = "data/mlb_context",
    report_path: str = "data/wbc_backend/reports/mlb_regime_paper_report.json",
) -> dict[str, Any]:
    data = build_mlb_rebuild_frame(csv_path=csv_path, context_path=context_path)
    strict = data[data["strict_valid"]].reset_index(drop=True)
    gate = derive_regime_gate_config(strict)
    data = data.copy()
    data["applicable_regimes"] = data.apply(lambda row: classify_regimes_from_row(row, gate), axis=1)
    strict = data[data["strict_valid"]].reset_index(drop=True)

    feature_sets = regime_feature_sets()
    regime_results: list[dict[str, Any]] = []
    selected_models: dict[str, dict[str, Any]] = {}
    trained_models: dict[str, TrainedRegimeModel] = {}

    for regime in REGIME_WHITELIST:
        candidates: list[dict[str, Any]] = []
        for model_family in _model_candidates(regime):
            candidate = _walk_forward_regime_eval(data[data["strict_valid"]].reset_index(drop=True), regime, feature_sets[regime], model_family)
            candidates.append(candidate)
        best = _select_best_regime_model(candidates)
        best_metrics = best["metrics"]
        regime_results.append(
            {
                "regime": regime,
                "selected_model": best_metrics.as_dict(),
                "candidate_models": [cand["metrics"].as_dict() for cand in candidates],
            }
        )
        selected_models[regime] = best
        subset = strict[strict["applicable_regimes"].apply(lambda regs: regime in regs)].reset_index(drop=True)
        if best_metrics.tradable and len(subset) >= 120:
            estimator, medians, calibrator = _fit_live_model(subset, feature_sets[regime], best_metrics.model_family, best_metrics.calibration)
            trained_models[regime] = TrainedRegimeModel(
                regime=regime,
                model_family=best_metrics.model_family,
                calibration=best_metrics.calibration,
                feature_cols=feature_sets[regime],
                medians=medians,
                estimator=estimator,
                calibrator=calibrator,
                historical_roi=best_metrics.roi,
                historical_clv=best_metrics.clv,
                historical_fold_std=best_metrics.fold_roi_std,
            )

    ledger_rows: list[dict[str, Any]] = []
    game_candidates: dict[str, list[dict[str, Any]]] = {}
    eval_game_meta: dict[str, dict[str, Any]] = {}
    for regime, best in selected_models.items():
        metrics: RegimeModelMetrics = best["metrics"]
        preds = best["predictions"]
        for _, row in preds.iterrows():
            gid = str(row["game_id"])
            eval_game_meta[gid] = {
                "game_id": gid,
                "game_date": str(row["game_date"]),
                "home_team": str(row["home_team"]),
                "away_team": str(row["away_team"]),
                "target": int(row["target"]),
                "market_home_prob": float(row["market_home_prob"]),
            }
            game_candidates.setdefault(gid, []).append(
                {
                    "regime": regime,
                    "paper_prob": float(row["pred_home_prob"]),
                    "edge": float(row["edge"]),
                    "paper_side": str(row["paper_side"]),
                    "fold_id": int(row["fold_id"]),
                    "tradable": bool(metrics.tradable),
                    "fold_roi_std": float(metrics.fold_roi_std),
                    "historical_roi": float(metrics.roi),
                }
            )

    for gid, meta in eval_game_meta.items():
        candidates = [c for c in game_candidates.get(gid, []) if c["tradable"]]
        if candidates:
            chosen = max(
                candidates,
                key=lambda item: (
                    1 if item["paper_side"] != "skip" else 0,
                    abs(item["edge"]),
                    item["historical_roi"],
                    -item["fold_roi_std"],
                ),
            )
            paper_side = str(chosen["paper_side"])
            regime = str(chosen["regime"])
            paper_prob = float(chosen["paper_prob"])
            edge = float(chosen["edge"])
            fold_id = int(chosen["fold_id"])
        else:
            paper_side = "skip"
            regime = ""
            paper_prob = float(meta["market_home_prob"])
            edge = 0.0
            fold_id = -1
        target = int(meta["target"])
        pnl = 0.0
        if paper_side == "home":
            pnl = 1.0 if target == 1 else -1.0
        elif paper_side == "away":
            pnl = 1.0 if target == 0 else -1.0
        ledger_rows.append(
            {
                **meta,
                "regime": regime,
                "paper_side": paper_side,
                "paper_prob": round(paper_prob, 4),
                "edge_vs_market": round(edge, 4),
                "execution_mode": "PAPER_ONLY",
                "pick_or_skip": "PICK" if paper_side in {"home", "away"} else "SKIP",
                "pnl": round(pnl, 4),
                "fold_id": fold_id,
            }
        )

    ledger = pd.DataFrame(ledger_rows)
    pick_mask = ledger["pick_or_skip"] == "PICK"
    paper_roi = float(ledger.loc[pick_mask, "pnl"].mean()) if pick_mask.any() else 0.0
    paper_clv = float(np.mean(np.abs(ledger.loc[pick_mask, "edge_vs_market"]))) if pick_mask.any() else 0.0
    overall_fold_std = _fold_roi_std(
        ledger["fold_id"].to_numpy(dtype=int),
        ledger["paper_prob"].to_numpy(dtype=float),
        ledger["market_home_prob"].to_numpy(dtype=float),
        ledger["target"].to_numpy(dtype=int),
    ) if len(ledger) else 0.0

    regime_tracking = []
    tradable_regimes = []
    for row in regime_results:
        selected = row["selected_model"]
        regime = row["regime"]
        regime_ledger = ledger[ledger["regime"] == regime].copy()
        pick_count = int((regime_ledger["pick_or_skip"] == "PICK").sum())
        skip_count = int(regime_ledger["pick_or_skip"].eq("SKIP").sum())
        if skip_count == 0:
            skip_count = int(selected["n_games"]) - pick_count
        if bool(selected["tradable"]):
            tradable_regimes.append(regime)
        regime_tracking.append(
            {
                "regime": regime,
                "selected_model_family": selected["model_family"],
                "selected_calibration": selected["calibration"],
                "sample_count": int(selected["sample_count"]),
                "n_games": int(selected["n_games"]),
                "pick_count": pick_count,
                "skip_count": max(0, skip_count),
                "paper_roi": round(float(regime_ledger.loc[regime_ledger["pick_or_skip"] == "PICK", "pnl"].mean()) if not regime_ledger.empty and (regime_ledger["pick_or_skip"] == "PICK").any() else 0.0, 4),
                "clv": round(float(np.mean(np.abs(regime_ledger.loc[regime_ledger["pick_or_skip"] == "PICK", "edge_vs_market"]))) if not regime_ledger.empty and (regime_ledger["pick_or_skip"] == "PICK").any() else 0.0, 4),
                "fold_stability": float(selected["fold_roi_std"]),
                "tradable": bool(selected["tradable"]),
            }
        )

    flags = mlb_governance_flags()
    payload = {
        "governance_flags": flags,
        "guarded_paper_mode": {
            "full_market_production_betting": "DISABLED",
            "execution_mode": flags["execution_mode"],
            "whitelist": list(REGIME_WHITELIST),
            "pipeline": [
                "strict_validation",
                "regime_classification",
                "regime_specific_model_or_skip",
                "paper_only_output",
            ],
        },
        "regime_gate_design": {
            "thresholds": gate.as_dict(),
            "classification_rules": {
                "favorites": "market_home_prob >= favorite_cutoff",
                "small_edge": "abs(market_home_prob - 0.5) <= small_edge_band",
                "weak_starter_mismatch": "abs(starter_recent_ra_diff) < weak_starter_cutoff",
                "heavy_bullpen_stress": "abs(bullpen_usage_diff) >= heavy_bullpen_cutoff",
            },
            "front_of_pipeline": True,
        },
        "regime_specific_model_results": regime_results,
        "paper_mode_reporting": {
            "overall": {
                "paper_roi": round(paper_roi, 4),
                "paper_clv": round(paper_clv, 4),
                "fold_stability": round(overall_fold_std, 4),
                "pick_count": int(pick_mask.sum()),
                "skip_count": int((~pick_mask).sum()),
                "sample_count": int(len(ledger)),
            },
            "by_regime": regime_tracking,
            "decision_samples": ledger.head(25).to_dict(orient="records"),
        },
        "report_sections": {
            "paper_modeling_metrics": {
                "overall": {
                    "paper_roi": round(paper_roi, 4),
                    "pick_count": int(pick_mask.sum()),
                    "skip_count": int((~pick_mask).sum()),
                    "sample_count": int(len(ledger)),
                },
                "by_regime": regime_tracking,
            },
            "sandbox_clv_diagnostics": {
                "paper_clv_proxy": round(paper_clv, 4),
                "scope": "strict_only_regime_paper",
                "note": "CLV proxy uses edge_vs_market within paper sandbox; not full-universe 2025 CLV timeline.",
            },
            "decision_quality_scale_status": {
                "status": "UNAVAILABLE",
                "reason": "2025_full_universe_clv_timeline_not_available",
            },
        },
        "tradable_regimes": tradable_regimes,
        "paper_to_live_ready_regimes": [],
        "notes": [
            "MLB remains execution-blocked; all outputs are paper-only.",
            "MLB live recommendation is disabled until 2025 historical odds timeline reaches governance coverage threshold.",
            "small_edge is a front-gate proxy based on market-centering, not the old post-model edge bucket.",
        ],
    }

    out = Path(report_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


@lru_cache(maxsize=1)
def default_mlb_regime_paper_system() -> MLBRegimePaperSystem:
    report = run_mlb_regime_paper_mode()
    strict = build_mlb_rebuild_frame(context_path="data/mlb_context")
    strict = strict[strict["strict_valid"]].reset_index(drop=True)
    gate = derive_regime_gate_config(strict)
    strict["applicable_regimes"] = strict.apply(lambda row: classify_regimes_from_row(row, gate), axis=1)

    trained_models: dict[str, TrainedRegimeModel] = {}
    feature_sets = regime_feature_sets()
    for row in report["regime_specific_model_results"]:
        selected = row["selected_model"]
        regime = row["regime"]
        if not selected["tradable"]:
            continue
        subset = strict[strict["applicable_regimes"].apply(lambda regs: regime in regs)].reset_index(drop=True)
        estimator, medians, calibrator = _fit_live_model(
            subset,
            feature_sets[regime],
            str(selected["model_family"]),
            str(selected["calibration"]),
        )
        trained_models[regime] = TrainedRegimeModel(
            regime=regime,
            model_family=str(selected["model_family"]),
            calibration=str(selected["calibration"]),
            feature_cols=feature_sets[regime],
            medians=medians,
            estimator=estimator,
            calibrator=calibrator,
            historical_roi=float(selected["roi"]),
            historical_clv=float(selected["clv"]),
            historical_fold_std=float(selected["fold_roi_std"]),
        )
    return MLBRegimePaperSystem(gate_config=gate, trained_models=trained_models, report=report)
