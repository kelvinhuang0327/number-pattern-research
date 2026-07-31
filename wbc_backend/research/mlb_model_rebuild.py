from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from wbc_backend.mlb_data.ingestion import load_mlb_game_data
from wbc_backend.mlb_data.ids import make_mlb_game_id
from wbc_backend.mlb_data.validator import MLBValidityTier, validate_mlb_game_data
from wbc_backend.models.mlb_moneyline import american_to_implied_prob


try:
    from sklearn.ensemble import GradientBoostingClassifier, HistGradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import Pipeline
except Exception:  # pragma: no cover
    GradientBoostingClassifier = None
    HistGradientBoostingClassifier = None
    LogisticRegression = None
    StandardScaler = None
    Pipeline = None

try:
    import xgboost as xgb  # type: ignore
except Exception:  # pragma: no cover
    xgb = None


@dataclass(frozen=True)
class ModelResult:
    model_name: str
    n_games: int
    n_bets: int
    roi: float
    brier: float
    logloss: float
    clv: float
    fold_roi_std: float
    sharpness: float
    notes: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "model_name": self.model_name,
            "n_games": self.n_games,
            "n_bets": self.n_bets,
            "roi": self.roi,
            "brier": self.brier,
            "logloss": self.logloss,
            "clv": self.clv,
            "fold_roi_std": self.fold_roi_std,
            "sharpness": self.sharpness,
            "notes": self.notes,
        }


def _sigmoid(x: np.ndarray | float) -> np.ndarray | float:
    return 1.0 / (1.0 + np.exp(-np.clip(x, -20, 20)))


def _brier(probs: np.ndarray, y: np.ndarray) -> float:
    return float(np.mean((probs - y) ** 2))


def _logloss(probs: np.ndarray, y: np.ndarray) -> float:
    eps = 1e-7
    return float(np.mean(-(y * np.log(np.clip(probs, eps, 1 - eps)) + (1 - y) * np.log(np.clip(1 - probs, eps, 1 - eps)))))


def _bet_metrics(probs: np.ndarray, market_probs: np.ndarray, y: np.ndarray, threshold: float = 0.01) -> dict[str, float]:
    valid = np.isfinite(probs) & np.isfinite(market_probs) & np.isfinite(y)
    if not np.any(valid):
        return {"n_bets": 0, "roi": 0.0, "clv": 0.0}
    edge = probs[valid] - market_probs[valid]
    outcomes_y = y[valid]
    mask = np.abs(edge) >= threshold
    if not np.any(mask):
        return {"n_bets": 0, "roi": 0.0, "clv": 0.0}
    chosen_home = edge[mask] > 0
    outcomes = np.where(chosen_home, outcomes_y[mask] == 1, outcomes_y[mask] == 0)
    pnl = np.where(outcomes, 1.0, -1.0)
    return {
        "n_bets": int(np.sum(mask)),
        "roi": float(np.mean(pnl)),
        "clv": float(np.mean(np.abs(edge[mask]))),
    }


def _history_mean(values: list[float], default: float, window: int = 10) -> float:
    if not values:
        return default
    return float(np.mean(values[-window:]))


def _history_std(values: list[float], default: float = 0.0, window: int = 10) -> float:
    if not values:
        return default
    if len(values[-window:]) <= 1:
        return default
    return float(np.std(values[-window:]))


def _posterior_rate(wins: float, games: float, alpha: float = 6.0, beta: float = 6.0) -> float:
    return float((wins + alpha) / max(1.0, games + alpha + beta))


def _count_inactive(payload: dict[str, Any] | None, side: str) -> int:
    if not payload:
        return 0
    return len(payload.get(f"{side}_inactive", []) or [])


def build_mlb_rebuild_frame(
    csv_path: str = "data/mlb_2025/mlb_odds_2025_real.csv",
    context_path: str | None = "data/mlb_context",
) -> pd.DataFrame:
    df = pd.read_csv(csv_path).copy()
    df["game_id"] = df.apply(
        lambda r: make_mlb_game_id(
            str(r.get("Date", "")),
            str(r.get("Start Time (EDT)", "")),
            str(r.get("Away", "")),
            str(r.get("Home", "")),
        ),
        axis=1,
    )
    df["_sort_ts"] = pd.to_datetime(df["Date"] + " " + df["Start Time (EDT)"], errors="coerce")
    df = df.sort_values(["_sort_ts", "game_id"], kind="mergesort").reset_index(drop=True)

    rows = load_mlb_game_data(csv_path=csv_path, context_path=context_path)
    validation = validate_mlb_game_data(rows)
    context_by_gid = {row.game_id: row for row in rows}

    team_runs_for: dict[str, list[float]] = {}
    team_runs_against: dict[str, list[float]] = {}
    team_run_diff: dict[str, list[float]] = {}
    team_wins: dict[str, list[float]] = {}
    team_home_wins: dict[str, list[float]] = {}
    team_away_wins: dict[str, list[float]] = {}
    starter_runs_allowed: dict[str, list[float]] = {}
    starter_run_support: dict[str, list[float]] = {}
    starter_days_between: dict[str, list[float]] = {}
    starter_last_date: dict[str, pd.Timestamp] = {}
    starter_quality: dict[str, list[float]] = {}
    league_runs_history: list[float] = []

    feature_rows: list[dict[str, Any]] = []

    for _, row in df.iterrows():
        gid = row["game_id"]
        context = context_by_gid.get(gid)
        home = str(row["Home"])
        away = str(row["Away"])
        home_starter = str(row.get("Home Starter", "") or "")
        away_starter = str(row.get("Away Starter", "") or "")
        game_date = pd.to_datetime(row["Date"], errors="coerce")

        league_runs = float(np.mean(league_runs_history[-200:])) if league_runs_history else 4.5
        home_off = _history_mean(team_runs_for.get(home, []), league_runs)
        away_off = _history_mean(team_runs_for.get(away, []), league_runs)
        home_pitch = _history_mean(team_runs_against.get(home, []), league_runs)
        away_pitch = _history_mean(team_runs_against.get(away, []), league_runs)
        home_rd = _history_mean(team_run_diff.get(home, []), 0.0)
        away_rd = _history_mean(team_run_diff.get(away, []), 0.0)
        home_home_form = _history_mean(team_home_wins.get(home, []), 0.5)
        away_away_form = _history_mean(team_away_wins.get(away, []), 0.5)
        home_win_pct = _history_mean(team_wins.get(home, []), 0.5)
        away_win_pct = _history_mean(team_wins.get(away, []), 0.5)

        home_team_post = _posterior_rate(sum(team_wins.get(home, [])), len(team_wins.get(home, [])))
        away_team_post = _posterior_rate(sum(team_wins.get(away, [])), len(team_wins.get(away, [])))

        home_sp_ra = _history_mean(starter_runs_allowed.get(home_starter, []), league_runs, window=5)
        away_sp_ra = _history_mean(starter_runs_allowed.get(away_starter, []), league_runs, window=5)
        home_sp_support = _history_mean(starter_run_support.get(home_starter, []), league_runs, window=5)
        away_sp_support = _history_mean(starter_run_support.get(away_starter, []), league_runs, window=5)
        home_sp_quality = _history_mean(starter_quality.get(home_starter, []), 0.0, window=5)
        away_sp_quality = _history_mean(starter_quality.get(away_starter, []), 0.0, window=5)
        home_sp_ra_vol = _history_std(starter_runs_allowed.get(home_starter, []), 0.0, window=5)
        away_sp_ra_vol = _history_std(starter_runs_allowed.get(away_starter, []), 0.0, window=5)
        home_sp_support_vol = _history_std(starter_run_support.get(home_starter, []), 0.0, window=5)
        away_sp_support_vol = _history_std(starter_run_support.get(away_starter, []), 0.0, window=5)
        home_sp_quality_vol = _history_std(starter_quality.get(home_starter, []), 0.0, window=5)
        away_sp_quality_vol = _history_std(starter_quality.get(away_starter, []), 0.0, window=5)
        home_sp_rest = _history_mean(starter_days_between.get(home_starter, []), 5.0, window=3)
        away_sp_rest = _history_mean(starter_days_between.get(away_starter, []), 5.0, window=3)
        home_sp_starts = float(len(starter_runs_allowed.get(home_starter, [])))
        away_sp_starts = float(len(starter_runs_allowed.get(away_starter, [])))

        market_home = american_to_implied_prob(row.get("Home ML"))
        market_away = american_to_implied_prob(row.get("Away ML"))
        ou_line = float(row.get("O/U"))

        lineups = (context.features.confirmed_home_lineup.value if context and context.features.confirmed_home_lineup.available else []) or []
        away_lineups = (context.features.confirmed_away_lineup.value if context and context.features.confirmed_away_lineup.available else []) or []
        injury = context.features.injury_rest.injury_report.value if context and context.features.injury_rest.injury_report.available else {}
        platoon = context.features.platoon_splits.value if context and context.features.platoon_splits.available else {}
        bullpen_home = float(context.features.bullpen_usage_last_3d_home.value) if context and context.features.bullpen_usage_last_3d_home.available else 0.0
        bullpen_away = float(context.features.bullpen_usage_last_3d_away.value) if context and context.features.bullpen_usage_last_3d_away.available else 0.0
        rest_home = float(context.features.injury_rest.rest_days_home.value) if context and context.features.injury_rest.rest_days_home.available else 0.0
        rest_away = float(context.features.injury_rest.rest_days_away.value) if context and context.features.injury_rest.rest_days_away.available else 0.0
        weather = context.features.weather.value if context and context.features.weather.available else {}
        wind = context.features.wind.value if context and context.features.wind.available else {}
        park = context.features.park_factors.value if context and context.features.park_factors.available else {}
        odds_history = context.features.odds.odds_history.value if context and context.features.odds.odds_history.available else []
        opening_home = american_to_implied_prob(context.features.odds.opening_home_ml.value) if context and context.features.odds.opening_home_ml.available else market_home
        closing_home = american_to_implied_prob(context.features.odds.closing_home_ml.value) if context and context.features.odds.closing_home_ml.available else market_home
        current_home = market_home
        if odds_history:
            current_home = american_to_implied_prob(odds_history[-1].get("home_ml"))
            if np.isnan(current_home):
                current_home = closing_home

        home_left = int(((platoon.get("home_bat_side") or {}).get("L", 0)))
        home_right = int(((platoon.get("home_bat_side") or {}).get("R", 0)))
        away_left = int(((platoon.get("away_bat_side") or {}).get("L", 0)))
        away_right = int(((platoon.get("away_bat_side") or {}).get("R", 0)))
        home_inactive = _count_inactive(injury, "home")
        away_inactive = _count_inactive(injury, "away")

        temp_c = float(weather.get("temp_c_avg", 0.0) or 0.0)
        wind_kmh = float(wind.get("wind_kmh_avg", 0.0) or 0.0)
        roof_type = str(park.get("roof_type", "") or "").lower()
        venue_name = str(park.get("venue_name", "") or "").lower()
        dome_flag = float(("dome" in roof_type) or ("dome" in venue_name))
        open_air_flag = float((roof_type == "open") or (not dome_flag and roof_type == ""))

        bullpen_quality_diff = (away_pitch - home_pitch) - (away_sp_ra - home_sp_ra)
        env_run_proxy = (temp_c / 30.0) + (wind_kmh / 25.0) - dome_flag * 0.20
        home_sp_workload = home_sp_starts / max(home_sp_rest, 1.0)
        away_sp_workload = away_sp_starts / max(away_sp_rest, 1.0)
        starter_workload_pressure_diff = away_sp_workload - home_sp_workload
        starter_form_blend_diff = (home_sp_quality - away_sp_quality) + 0.50 * (away_sp_ra - home_sp_ra)
        starter_matchup_depth_diff = (home_off - away_off) + (away_sp_ra - home_sp_ra) + 0.15 * ((home_left - home_right) - (away_left - away_right))
        lineup_vs_starter_interaction_diff = (
            ((len(lineups) - home_inactive) / 9.0) * away_sp_ra
            - ((len(away_lineups) - away_inactive) / 9.0) * home_sp_ra
        )

        feature_rows.append(
            {
                "game_id": gid,
                "game_date": str(row["Date"]),
                "home_team": home,
                "away_team": away,
                # For historical rebuild, accept RESEARCH_VALID (freshness gate is for live deployment only)
                "strict_valid": validation.status_by_game.get(gid) in (MLBValidityTier.STRICT_VALID, MLBValidityTier.RESEARCH_VALID),
                "target": int(float(row.get("Home Score")) > float(row.get("Away Score"))),
                "market_home_prob": market_home,
                "ou_line": ou_line,
                "market_gap": market_home - market_away,
                "market_abs_dev_50": abs(market_home - 0.5) if np.isfinite(market_home) else np.nan,
                "market_open_current_move": current_home - opening_home,
                "market_open_close_move": closing_home - opening_home,
                "market_close_alignment_proxy": abs(closing_home - current_home),
                "market_disagreement_proxy": abs(current_home - opening_home),
                "team_offense_diff": home_off - away_off,
                "team_pitching_diff": away_pitch - home_pitch,
                "team_home_away_form_diff": home_home_form - away_away_form,
                "team_recent_run_diff_delta": home_rd - away_rd,
                "team_win_pct_diff": home_win_pct - away_win_pct,
                "team_posterior_diff": home_team_post - away_team_post,
                "starter_recent_ra_diff": away_sp_ra - home_sp_ra,
                "starter_support_diff": home_sp_support - away_sp_support,
                "starter_quality_diff": home_sp_quality - away_sp_quality,
                "starter_rest_diff": home_sp_rest - away_sp_rest,
                "starter_start_count_diff": home_sp_starts - away_sp_starts,
                "starter_workload_pressure_diff": starter_workload_pressure_diff,
                "starter_form_blend_diff": starter_form_blend_diff,
                "starter_matchup_depth_diff": starter_matchup_depth_diff,
                "lineup_vs_starter_interaction_diff": lineup_vs_starter_interaction_diff,
                "starter_recent_ra_volatility_diff": away_sp_ra_vol - home_sp_ra_vol,
                "starter_support_volatility_diff": away_sp_support_vol - home_sp_support_vol,
                "starter_quality_volatility_diff": away_sp_quality_vol - home_sp_quality_vol,
                "starter_run_support_asymmetry": (home_sp_support - away_sp_support) * (home_off - away_off),
                "bullpen_usage_diff": bullpen_away - bullpen_home,
                "bullpen_usage_intensity_diff": (bullpen_away / max(rest_away + 1.0, 1.0)) - (bullpen_home / max(rest_home + 1.0, 1.0)),
                "bullpen_quality_diff": bullpen_quality_diff,
                "lineup_size_diff": float(len(lineups) - len(away_lineups)),
                "lineup_missing_slots_diff": float((9 - len(lineups)) - (9 - len(away_lineups))),
                "injury_count_diff": float(away_inactive - home_inactive),
                "rest_day_diff": rest_home - rest_away,
                "platoon_balance_diff": float((home_left - home_right) - (away_left - away_right)),
                "weather_temp_c": temp_c,
                "weather_wind_kmh": wind_kmh,
                "environment_run_proxy": env_run_proxy,
                "dome_flag": dome_flag,
                "open_air_flag": open_air_flag,
            }
        )

        home_score = float(row.get("Home Score"))
        away_score = float(row.get("Away Score"))
        league_runs_history.extend([home_score, away_score])

        team_runs_for.setdefault(home, []).append(home_score)
        team_runs_for.setdefault(away, []).append(away_score)
        team_runs_against.setdefault(home, []).append(away_score)
        team_runs_against.setdefault(away, []).append(home_score)
        team_run_diff.setdefault(home, []).append(home_score - away_score)
        team_run_diff.setdefault(away, []).append(away_score - home_score)
        team_wins.setdefault(home, []).append(1.0 if home_score > away_score else 0.0)
        team_wins.setdefault(away, []).append(1.0 if away_score > home_score else 0.0)
        team_home_wins.setdefault(home, []).append(1.0 if home_score > away_score else 0.0)
        team_away_wins.setdefault(away, []).append(1.0 if away_score > home_score else 0.0)

        if home_starter:
            starter_runs_allowed.setdefault(home_starter, []).append(away_score)
            starter_run_support.setdefault(home_starter, []).append(home_score)
            starter_quality.setdefault(home_starter, []).append(home_score - away_score)
            if home_starter in starter_last_date and pd.notna(game_date):
                starter_days_between.setdefault(home_starter, []).append(float((game_date - starter_last_date[home_starter]).days))
            starter_last_date[home_starter] = game_date
        if away_starter:
            starter_runs_allowed.setdefault(away_starter, []).append(home_score)
            starter_run_support.setdefault(away_starter, []).append(away_score)
            starter_quality.setdefault(away_starter, []).append(away_score - home_score)
            if away_starter in starter_last_date and pd.notna(game_date):
                starter_days_between.setdefault(away_starter, []).append(float((game_date - starter_last_date[away_starter]).days))
            starter_last_date[away_starter] = game_date

    return pd.DataFrame(feature_rows)


def feature_families() -> dict[str, list[str]]:
    return {
        "market": [
            "market_home_prob",
            "ou_line",
            "market_gap",
            "market_open_current_move",
            "market_open_close_move",
            "market_close_alignment_proxy",
            "market_disagreement_proxy",
        ],
        "team": [
            "team_offense_diff",
            "team_pitching_diff",
            "team_home_away_form_diff",
            "team_recent_run_diff_delta",
            "team_win_pct_diff",
            "team_posterior_diff",
        ],
        "starter": [
            "starter_recent_ra_diff",
            "starter_support_diff",
            "starter_quality_diff",
            "starter_rest_diff",
            "starter_start_count_diff",
        ],
        "bullpen": [
            "bullpen_usage_diff",
            "bullpen_usage_intensity_diff",
            "bullpen_quality_diff",
        ],
        "lineup_context": [
            "lineup_size_diff",
            "lineup_missing_slots_diff",
            "injury_count_diff",
            "rest_day_diff",
            "platoon_balance_diff",
        ],
        "environment": [
            "weather_temp_c",
            "weather_wind_kmh",
            "environment_run_proxy",
            "dome_flag",
            "open_air_flag",
        ],
    }


def _fit_predict_family(model_name: str, x_train: pd.DataFrame, y_train: np.ndarray, x_test: pd.DataFrame) -> tuple[np.ndarray, dict[str, float]]:
    medians = x_train.median(numeric_only=True)
    xtr = x_train.fillna(medians)
    xte = x_test.fillna(medians)

    if model_name == "regularized_logistic":
        model = Pipeline(
            [
                ("scaler", StandardScaler()),
                ("clf", LogisticRegression(C=0.35, penalty="l2", max_iter=800, solver="lbfgs")),
            ]
        )
        model.fit(xtr, y_train)
        probs = model.predict_proba(xte)[:, 1]
        coefs = model.named_steps["clf"].coef_[0]
        return np.asarray(probs, dtype=float), {k: float(v) for k, v in zip(x_train.columns, coefs)}

    if model_name == "gradient_boosting":
        model = GradientBoostingClassifier(n_estimators=180, learning_rate=0.04, max_depth=2, random_state=42)
        model.fit(xtr, y_train)
        probs = model.predict_proba(xte)[:, 1]
        return np.asarray(probs, dtype=float), {k: float(v) for k, v in zip(x_train.columns, model.feature_importances_)}

    if model_name == "tree_boost_style":
        if xgb is not None:
            model = xgb.XGBClassifier(
                n_estimators=220,
                max_depth=3,
                learning_rate=0.035,
                subsample=0.9,
                colsample_bytree=0.9,
                reg_lambda=1.5,
                eval_metric="logloss",
                use_label_encoder=False,
                random_state=42,
            )
            model.fit(xtr, y_train, verbose=False)
            probs = model.predict_proba(xte)[:, 1]
            return np.asarray(probs, dtype=float), {k: float(v) for k, v in zip(x_train.columns, model.feature_importances_)}
        model = HistGradientBoostingClassifier(max_depth=4, max_iter=220, learning_rate=0.045, random_state=42)
        model.fit(xtr, y_train)
        probs = model.predict_proba(xte)[:, 1]
        return np.asarray(probs, dtype=float), {}

    if model_name == "hierarchical_bayesian":
        team_signal = _sigmoid(2.5 * xte["team_posterior_diff"].to_numpy(dtype=float) + 0.15 * xte["team_recent_run_diff_delta"].to_numpy(dtype=float))
        starter_signal = _sigmoid(0.30 * xte["starter_quality_diff"].to_numpy(dtype=float) + 0.20 * xte["starter_recent_ra_diff"].to_numpy(dtype=float))
        bullpen_signal = _sigmoid(0.20 * xte["bullpen_quality_diff"].to_numpy(dtype=float) + 0.08 * xte["bullpen_usage_diff"].to_numpy(dtype=float))
        lineup_signal = _sigmoid(0.20 * xte["injury_count_diff"].to_numpy(dtype=float) + 0.08 * xte["rest_day_diff"].to_numpy(dtype=float))
        env_signal = _sigmoid(0.10 * xte["environment_run_proxy"].to_numpy(dtype=float))
        market_signal = np.clip(xte["market_home_prob"].to_numpy(dtype=float), 0.02, 0.98)
        probs = (
            0.45 * market_signal
            + 0.20 * team_signal
            + 0.18 * starter_signal
            + 0.10 * bullpen_signal
            + 0.05 * lineup_signal
            + 0.02 * env_signal
        )
        return np.clip(np.asarray(probs, dtype=float), 0.02, 0.98), {
            "market_signal": 0.45,
            "team_signal": 0.20,
            "starter_signal": 0.18,
            "bullpen_signal": 0.10,
            "lineup_signal": 0.05,
            "env_signal": 0.02,
        }

    raise ValueError(f"Unsupported model: {model_name}")


def _walk_forward_eval(
    data: pd.DataFrame,
    feature_cols: list[str],
    model_name: str,
    n_splits: int = 6,
    threshold: float = 0.01,
) -> tuple[ModelResult, np.ndarray, list[dict[str, float]]]:
    strict = data[data["strict_valid"]].reset_index(drop=True)
    n = len(strict)
    split_size = max(60, n // n_splits)
    probs = np.full(n, np.nan, dtype=float)
    market = strict["market_home_prob"].to_numpy(dtype=float)
    y = strict["target"].to_numpy(dtype=int)
    fold_rois: list[float] = []
    importances: list[dict[str, float]] = []

    for start in range(split_size, n, split_size):
        end = min(n, start + split_size)
        x_train = strict.loc[: start - 1, feature_cols]
        y_train = y[:start]
        x_test = strict.loc[start:end - 1, feature_cols]
        fold_probs, fold_imp = _fit_predict_family(model_name, x_train, y_train, x_test)
        probs[start:end] = fold_probs
        importances.append(fold_imp)
        fold_metric = _bet_metrics(fold_probs, market[start:end], y[start:end], threshold=threshold)
        if fold_metric["n_bets"] > 0:
            fold_rois.append(float(fold_metric["roi"]))

    eval_mask = ~np.isnan(probs)
    probs = probs[eval_mask]
    market_eval = market[eval_mask]
    y_eval = y[eval_mask]
    decision = _bet_metrics(probs, market_eval, y_eval, threshold=threshold)
    result = ModelResult(
        model_name=model_name,
        n_games=int(np.sum(eval_mask)),
        n_bets=int(decision["n_bets"]),
        roi=round(float(decision["roi"]), 4),
        brier=round(_brier(probs, y_eval), 4),
        logloss=round(_logloss(probs, y_eval), 4),
        clv=round(float(decision["clv"]), 4),
        fold_roi_std=round(float(np.std(fold_rois)) if fold_rois else 0.0, 4),
        sharpness=round(float(np.mean(np.abs(probs - 0.5))), 4),
    )
    return result, probs, importances


def _baseline_autopsy(data: pd.DataFrame) -> dict[str, Any]:
    base_features = [
        "market_home_prob",
        "market_gap",
        "ou_line",
        "starter_start_count_diff",
        "rest_day_diff",
        "dome_flag",
    ]
    result, probs, importances = _walk_forward_eval(data, base_features, "regularized_logistic", n_splits=6, threshold=0.01)
    importance_df = pd.DataFrame(importances).fillna(0.0)
    mean_abs = importance_df.abs().mean().sort_values(ascending=False)
    instability = importance_df.std().sort_values(ascending=False)
    corr = data[base_features].corr().abs()
    redundant = []
    for i, a in enumerate(base_features):
        for b in base_features[i + 1:]:
            if corr.loc[a, b] >= 0.85:
                redundant.append({"a": a, "b": b, "corr": round(float(corr.loc[a, b]), 4)})
    strong = mean_abs.head(3).round(4).to_dict()
    weak = mean_abs.tail(3).round(4).to_dict()
    noisy = instability.head(3).round(4).to_dict()
    regimes = {
        "favorite_roi": None,
        "underdog_roi": None,
    }
    strict = data[data["strict_valid"]].reset_index(drop=True)
    eval_mask = np.arange(len(strict)) >= max(60, len(strict) // 6)
    market = strict.loc[eval_mask, "market_home_prob"].to_numpy(dtype=float)
    y = strict.loc[eval_mask, "target"].to_numpy(dtype=int)
    favorite_mask = market >= 0.55
    dog_mask = market <= 0.45
    if np.any(favorite_mask):
        regimes["favorite_roi"] = round(_bet_metrics(probs[favorite_mask], market[favorite_mask], y[favorite_mask], threshold=0.01)["roi"], 4)
    if np.any(dog_mask):
        regimes["underdog_roi"] = round(_bet_metrics(probs[dog_mask], market[dog_mask], y[dog_mask], threshold=0.01)["roi"], 4)
    return {
        "feature_list": base_features,
        "strongest_features": strong,
        "weakest_features": weak,
        "feature_instability": noisy,
        "redundancy_pairs": redundant,
        "probability_sharpness": result.sharpness,
        "sub_regime_behavior": regimes,
        "suspected_broken_assumptions": [
            "Market prior dominates the baseline stack and limits non-market signal formation.",
            "Starter availability proxies are too shallow; current baseline has little pitcher-specific separation.",
            "Environment and rest effects are mostly absent in the baseline, so game-context variance is under-modeled.",
        ],
    }


def _classify_candidate(result: ModelResult, baseline: ModelResult) -> str:
    if result.roi > 0 and result.clv > 0 and (result.brier < baseline.brier or result.logloss < baseline.logloss) and result.fold_roi_std < 0.15:
        return "TRADABLE_SIGNAL"
    if result.roi > 0 and (result.clv <= 0 or result.fold_roi_std >= 0.15):
        return "OVERFIT_SIGNAL"
    if result.clv > 0 and (result.brier <= baseline.brier or result.logloss <= baseline.logloss):
        return "WEAK_SIGNAL"
    return "NOISE"


def _fold_roi_std(probs: np.ndarray, market: np.ndarray, y: np.ndarray, n_splits: int = 6, threshold: float = 0.01) -> float:
    valid = np.isfinite(probs) & np.isfinite(market) & np.isfinite(y)
    if not np.any(valid):
        return 0.0
    probs = probs[valid]
    market = market[valid]
    y = y[valid]
    split_size = max(1, len(probs) // max(1, n_splits))
    fold_rois: list[float] = []
    for start in range(0, len(probs), split_size):
        end = min(len(probs), start + split_size)
        metrics = _bet_metrics(probs[start:end], market[start:end], y[start:end], threshold=threshold)
        if metrics["n_bets"] > 0:
            fold_rois.append(float(metrics["roi"]))
    return round(float(np.std(fold_rois)) if fold_rois else 0.0, 4)


def _classify_regime_signal(n_bets: int, roi: float, clv: float, fold_roi_std: float) -> str:
    if n_bets >= 50 and roi > 0 and clv > 0 and fold_roi_std < 0.15:
        return "TRADABLE_SIGNAL"
    if n_bets >= 50 and roi > 0 and clv > 0:
        return "OVERFIT_SIGNAL"
    if n_bets >= 50 and clv > 0:
        return "WEAK_SIGNAL"
    return "NOISE"


def _regime_slice_metrics(strict: pd.DataFrame, probs: np.ndarray, label: str, mask: np.ndarray) -> dict[str, Any]:
    market = strict["market_home_prob"].to_numpy(dtype=float)
    y = strict["target"].to_numpy(dtype=int)
    valid_mask = mask & np.isfinite(probs) & np.isfinite(market)
    roi = _bet_metrics(probs[valid_mask], market[valid_mask], y[valid_mask], threshold=0.01)
    fold_roi_std = _fold_roi_std(probs[valid_mask], market[valid_mask], y[valid_mask], threshold=0.01)
    return {
        "regime": label,
        "n_games": int(np.sum(valid_mask)),
        "n_bets": int(roi["n_bets"]),
        "roi": round(float(roi["roi"]), 4),
        "clv": round(float(roi["clv"]), 4),
        "fold_roi_std": fold_roi_std,
        "classification": _classify_regime_signal(int(roi["n_bets"]), float(roi["roi"]), float(roi["clv"]), fold_roi_std),
    }


def run_mlb_model_rebuild(
    *,
    csv_path: str = "data/mlb_2025/mlb_odds_2025_real.csv",
    context_path: str | None = "data/mlb_context",
    report_path: str = "data/wbc_backend/reports/mlb_model_rebuild_report.json",
) -> dict[str, Any]:
    data = build_mlb_rebuild_frame(csv_path=csv_path, context_path=context_path)
    families = feature_families()
    strict = data[data["strict_valid"]].reset_index(drop=True)

    autopsy = _baseline_autopsy(data)

    ablation_specs = {
        "market_only": families["market"],
        "market_plus_team": families["market"] + families["team"],
        "market_plus_starter": families["market"] + families["starter"],
        "market_plus_bullpen": families["market"] + families["bullpen"],
        "market_plus_lineup_context": families["market"] + families["lineup_context"],
        "market_plus_environment": families["market"] + families["environment"],
        "full_logistic_family_stack": sum(families.values(), []),
    }

    ablation_results: list[dict[str, Any]] = []
    baseline_ablation = None
    for name, cols in ablation_specs.items():
        result, _, _ = _walk_forward_eval(data, cols, "regularized_logistic")
        if baseline_ablation is None:
            baseline_ablation = result
        ablation_results.append(
            {
                "family_test": name,
                "features": cols,
                **result.as_dict(),
            }
        )

    model_family_results: list[dict[str, Any]] = []
    model_probs: dict[str, np.ndarray] = {}
    full_features = sum(families.values(), [])
    baseline_result = baseline_ablation or _walk_forward_eval(data, families["market"], "regularized_logistic")[0]

    for model_name in ("regularized_logistic", "gradient_boosting", "tree_boost_style", "hierarchical_bayesian"):
        result, probs, _ = _walk_forward_eval(data, full_features, model_name)
        classification = _classify_candidate(result, baseline_result)
        model_family_results.append({**result.as_dict(), "classification": classification})
        model_probs[model_name] = probs

    # Stacking only if model outputs are distinct enough.
    stack_notes = "not_run_insufficient_diversity"
    if len(model_probs) >= 3:
        corr = pd.DataFrame({k: v for k, v in model_probs.items()}).corr().abs()
        distinct_pairs = int(np.sum((corr.values < 0.995) & (corr.values > 0)))
        if distinct_pairs > 0 and LogisticRegression is not None:
            n = len(next(iter(model_probs.values())))
            strict_eval = strict.iloc[-n:].reset_index(drop=True)
            split_size = max(60, n // 6)
            strict_market = strict_eval["market_home_prob"].to_numpy(dtype=float)
            strict_y = strict_eval["target"].to_numpy(dtype=int)
            stack_probs = np.full(n, np.nan, dtype=float)
            for start in range(split_size, n, split_size):
                end = min(n, start + split_size)
                holdout = max(40, start // 5)
                inner = start - holdout
                if inner < 40:
                    continue
                meta_train = np.column_stack([model_probs[k][inner:start] for k in ("regularized_logistic", "gradient_boosting", "tree_boost_style", "hierarchical_bayesian")])
                meta_y = strict_y[inner:start]
                meta_test = np.column_stack([model_probs[k][start:end] for k in ("regularized_logistic", "gradient_boosting", "tree_boost_style", "hierarchical_bayesian")])
                meta_model = LogisticRegression(C=0.5, max_iter=500)
                meta_model.fit(meta_train, meta_y)
                stack_probs[start:end] = meta_model.predict_proba(meta_test)[:, 1]
            eval_mask = ~np.isnan(stack_probs)
            if np.any(eval_mask):
                roi = _bet_metrics(stack_probs[eval_mask], strict_market[eval_mask], strict_y[eval_mask], threshold=0.01)
                model_family_results.append(
                    {
                        "model_name": "stacked_ensemble",
                        "n_games": int(np.sum(eval_mask)),
                        "n_bets": int(roi["n_bets"]),
                        "roi": round(float(roi["roi"]), 4),
                        "brier": round(_brier(stack_probs[eval_mask], strict_y[eval_mask]), 4),
                        "logloss": round(_logloss(stack_probs[eval_mask], strict_y[eval_mask]), 4),
                        "clv": round(float(roi["clv"]), 4),
                        "fold_roi_std": None,
                        "sharpness": round(float(np.mean(np.abs(stack_probs[eval_mask] - 0.5))), 4),
                        "notes": "stacked from 4 base models via logistic meta-learner",
                        "classification": _classify_candidate(
                            ModelResult(
                                model_name="stacked_ensemble",
                                n_games=int(np.sum(eval_mask)),
                                n_bets=int(roi["n_bets"]),
                                roi=round(float(roi["roi"]), 4),
                                brier=round(_brier(stack_probs[eval_mask], strict_y[eval_mask]), 4),
                                logloss=round(_logloss(stack_probs[eval_mask], strict_y[eval_mask]), 4),
                                clv=round(float(roi["clv"]), 4),
                                fold_roi_std=0.0,
                                sharpness=round(float(np.mean(np.abs(stack_probs[eval_mask] - 0.5))), 4),
                            ),
                            baseline_result,
                        ),
                    }
                )
                model_probs["stacked_ensemble"] = stack_probs[eval_mask]
                stack_notes = "run"

    best_model_row = max(
        model_family_results,
        key=lambda row: (
            1 if row["classification"] == "TRADABLE_SIGNAL" else 0,
            row["clv"],
            -row["brier"],
        ),
    )
    best_model_name = best_model_row["model_name"]

    if best_model_name == "stacked_ensemble" and "stacked_ensemble" in model_probs:
        regime_probs = model_probs["stacked_ensemble"]
        regime_strict = strict.iloc[-len(regime_probs):].reset_index(drop=True)
    else:
        _, regime_probs, _ = _walk_forward_eval(data, full_features, best_model_name if best_model_name != "stacked_ensemble" else "regularized_logistic")
        regime_strict = strict.iloc[-len(regime_probs):].reset_index(drop=True)

    market = regime_strict["market_home_prob"].to_numpy(dtype=float)
    edge = regime_probs - market
    starter_abs = np.abs(regime_strict["starter_recent_ra_diff"].to_numpy(dtype=float))
    bullpen_abs = np.abs(regime_strict["bullpen_usage_diff"].to_numpy(dtype=float))
    totals = regime_strict["ou_line"].to_numpy(dtype=float)
    finite_edge = np.isfinite(edge)
    finite_market = np.isfinite(market)
    finite_starter = np.isfinite(starter_abs)
    finite_bullpen = np.isfinite(bullpen_abs)
    finite_total = np.isfinite(totals)
    median_edge = float(np.median(np.abs(edge[finite_edge]))) if np.any(finite_edge) else 0.0
    median_starter = float(np.median(starter_abs[finite_starter])) if np.any(finite_starter) else 0.0
    median_bullpen = float(np.median(bullpen_abs[finite_bullpen])) if np.any(finite_bullpen) else 0.0
    median_total = float(np.median(totals[finite_total])) if np.any(finite_total) else 0.0

    regime_results = [
        _regime_slice_metrics(regime_strict, regime_probs, "favorites", finite_market & (market >= 0.55)),
        _regime_slice_metrics(regime_strict, regime_probs, "underdogs", finite_market & (market <= 0.45)),
        _regime_slice_metrics(regime_strict, regime_probs, "small_edge", finite_edge & (np.abs(edge) < median_edge)),
        _regime_slice_metrics(regime_strict, regime_probs, "large_edge", finite_edge & (np.abs(edge) >= median_edge)),
        _regime_slice_metrics(regime_strict, regime_probs, "home_bias", edge > 0),
        _regime_slice_metrics(regime_strict, regime_probs, "away_bias", edge < 0),
        _regime_slice_metrics(regime_strict, regime_probs, "strong_starter_mismatch", finite_starter & (starter_abs >= median_starter)),
        _regime_slice_metrics(regime_strict, regime_probs, "weak_starter_mismatch", finite_starter & (starter_abs < median_starter)),
        _regime_slice_metrics(regime_strict, regime_probs, "high_total", finite_total & (totals >= median_total)),
        _regime_slice_metrics(regime_strict, regime_probs, "low_total", finite_total & (totals < median_total)),
        _regime_slice_metrics(regime_strict, regime_probs, "heavy_bullpen_stress", finite_bullpen & (bullpen_abs >= median_bullpen)),
        _regime_slice_metrics(regime_strict, regime_probs, "normal_bullpen_stress", finite_bullpen & (bullpen_abs < median_bullpen)),
    ]

    regime_positive = [r for r in regime_results if r["classification"] == "TRADABLE_SIGNAL"]

    if any(row["classification"] == "TRADABLE_SIGNAL" for row in model_family_results):
        final_diagnosis = "MODEL REBUILD SUCCESSFUL"
        production_path = "Promote the best model family into guarded strict-only paper deployment."
    elif regime_positive:
        final_diagnosis = "EDGE EXISTS ONLY IN SUBSET REGIMES"
        production_path = "Deploy only regime-gated MLB moneyline recommendations with hard whitelist rules."
    elif any(row["classification"] == "WEAK_SIGNAL" for row in model_family_results):
        final_diagnosis = "SIGNAL STILL TOO WEAK"
        production_path = "Keep moneyline in research mode and pursue starter-level / lineup-strength data enrichment before deployment."
    else:
        final_diagnosis = "MLB MONEYLINE NOT CURRENTLY TRADABLE"
        production_path = "Do not deploy MLB moneyline; preserve WBC production and redirect MLB research to richer pitcher and lineup signals."

    payload = {
        "model_autopsy": autopsy,
        "reconstructed_feature_families": families,
        "ablation_table": ablation_results,
        "model_family_comparison": model_family_results,
        "regime_segmentation_results": regime_results,
        "signal_classification": {row["model_name"]: row["classification"] for row in model_family_results},
        "final_diagnosis": final_diagnosis,
        "recommended_production_path": production_path,
        "stacking_status": stack_notes,
        "best_model": best_model_name,
    }
    out = Path(report_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload
