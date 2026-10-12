from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import numpy as np
import pandas as pd

from wbc_backend.mlb_data.ingestion import load_mlb_game_data
from wbc_backend.mlb_data.ids import make_mlb_game_id
from wbc_backend.mlb_data.validator import MLBValidityTier, validate_mlb_game_data

from .mlb_context_adjuster import MLBContextAdjuster
from .mlb_moneyline_base import MLBMoneylineBaseModel


def american_to_implied_prob(odds: float) -> float:
    if odds is None or (isinstance(odds, float) and np.isnan(odds)):
        return np.nan
    if isinstance(odds, str):
        token = odds.strip()
        if token in {"", "-", "NA", "N/A", "null", "None"}:
            return np.nan
        odds = token
    odds = float(odds)
    if odds < 0:
        return abs(odds) / (abs(odds) + 100.0)
    return 100.0 / (odds + 100.0)


def _build_base_features(df: pd.DataFrame) -> np.ndarray:
    home_mkt = df["Home ML"].apply(american_to_implied_prob).to_numpy(dtype=float)
    away_mkt = df["Away ML"].apply(american_to_implied_prob).to_numpy(dtype=float)
    ou = pd.to_numeric(df["O/U"], errors="coerce").to_numpy(dtype=float)
    starter_home_known = (~df["Home Starter"].isna()).astype(float).to_numpy()
    starter_away_known = (~df["Away Starter"].isna()).astype(float).to_numpy()
    home_bias = np.full_like(home_mkt, 1.0)
    X = np.column_stack(
        [
            np.nan_to_num(home_mkt, nan=0.5),
            np.nan_to_num(away_mkt, nan=0.5),
            np.nan_to_num(home_mkt - away_mkt, nan=0.0),
            np.nan_to_num(ou, nan=8.5),
            starter_home_known,
            starter_away_known,
            home_bias,
        ]
    )
    return X


def _build_labels(df: pd.DataFrame) -> np.ndarray:
    return (pd.to_numeric(df["Home Score"], errors="coerce") > pd.to_numeric(df["Away Score"], errors="coerce")).astype(int).to_numpy()


def build_mlb_moneyline_training_data(csv_path: str = "data/mlb_2025/mlb_odds_2025_real.csv") -> tuple[np.ndarray, np.ndarray, pd.DataFrame]:
    df = pd.read_csv(csv_path)
    for col in ("Date", "Home", "Away", "Home ML", "Away ML", "O/U", "Home Score", "Away Score"):
        if col not in df.columns:
            raise ValueError(f"Missing required MLB column: {col}")
    return _build_base_features(df), _build_labels(df), df


@dataclass
class MLBMoneylineModel:
    base_model: MLBMoneylineBaseModel
    context_adjuster: MLBContextAdjuster

    def predict_home_win_prob_from_record(self, record) -> float:
        home_ml = float(getattr(record, "market_home_prob", 0.5))
        away_ml = max(1e-6, 1.0 - home_ml)
        ou_line = float(getattr(record, "ou_line", 8.5))
        home_starter = float(1.0 if getattr(record, "home_starter", None) else 0.0)
        away_starter = float(1.0 if getattr(record, "away_starter", None) else 0.0)
        X = np.array([[home_ml, away_ml, home_ml - away_ml, ou_line, home_starter, away_starter, 1.0]], dtype=float)
        return float(self.base_model.predict_proba(X)[0])


def _tier_indices(df: pd.DataFrame, tier: MLBValidityTier, context_path: str | None = None) -> np.ndarray:
    rows = load_mlb_game_data(csv_path="data/mlb_2025/mlb_odds_2025_real.csv", context_path=context_path or "data/mlb_context")
    validation = validate_mlb_game_data(rows)
    tier_ids = {gid for gid, status in validation.status_by_game.items() if status == tier}
    idx = []
    for i, row in df.iterrows():
        game_id = make_mlb_game_id(
            str(row.get("Date", "")),
            str(row.get("Start Time (EDT)", "")),
            str(row.get("Away", "")),
            str(row.get("Home", "")),
        )
        if game_id in tier_ids:
            idx.append(i)
    return np.asarray(idx, dtype=int)


def _compute_metrics(probs: np.ndarray, y: np.ndarray, market_probs: np.ndarray) -> dict:
    eps = 1e-7
    brier = float(np.mean((probs - y) ** 2))
    logloss = float(np.mean(-(y * np.log(np.clip(probs, eps, 1 - eps)) + (1 - y) * np.log(np.clip(1 - probs, eps, 1 - eps)))))
    edge = probs - market_probs
    bets = np.abs(edge) >= 0.03
    pnl = np.where((edge > 0) & (y == 1), 1.0, np.where((edge <= 0) & (y == 0), 1.0, -1.0))
    roi = float(pnl[bets].mean()) if bets.any() else 0.0
    clv = float(np.mean(edge[bets])) if bets.any() else 0.0
    return {
        "n_bets": int(bets.sum()),
        "roi": roi,
        "brier": brier,
        "logloss": logloss,
        "clv": clv,
    }


def walk_forward_backtest_mlb_moneyline(
    csv_path: str = "data/mlb_2025/mlb_odds_2025_real.csv",
    n_splits: int = 5,
    tier: MLBValidityTier = MLBValidityTier.RESEARCH_VALID,
    context_path: str | None = None,
) -> dict:
    X, y, df = build_mlb_moneyline_training_data(csv_path)
    all_rows = load_mlb_game_data(csv_path=csv_path, context_path=context_path)
    market_probs = X[:, 0].copy()
    idx = _tier_indices(df, tier=tier, context_path=context_path)
    if len(idx) == 0:
        return {
            "tier": tier.value,
            "n_games": 0,
            "n_bets": 0,
            "roi": 0.0,
            "brier": 1.0,
            "logloss": 1.0,
            "clv": 0.0,
            "fold_roi_std": 0.0,
            "pass_thresholds": False,
            "reason": "no_games_in_tier",
        }
    X_t = X[idx]
    y_t = y[idx]
    mkt_t = market_probs[idx]
    rows_t = [all_rows[i] for i in idx]
    n = len(y_t)
    split_size = max(20, n // n_splits)
    probs = np.zeros(n, dtype=float)
    fold_rois = []

    for start in range(split_size, n, split_size):
        end = min(n, start + split_size)
        base = MLBMoneylineBaseModel().fit(X_t[:start], y_t[:start])
        adjuster = MLBContextAdjuster()
        raw = base.predict_proba(X_t[start:end])
        adj = np.array(
            [adjuster.adjust_home_prob(float(raw[i]), rows_t[start + i]) for i in range(len(raw))],
            dtype=float,
        )
        probs[start:end] = adj
        fold_metrics = _compute_metrics(adj, y_t[start:end], mkt_t[start:end])
        fold_rois.append(fold_metrics["roi"])
    probs[:split_size] = mkt_t[:split_size]

    metrics = _compute_metrics(probs, y_t, mkt_t)
    fold_roi_std = float(np.std(fold_rois)) if fold_rois else 0.0
    pass_thresholds = bool(
        (metrics["roi"] > 0)
        and (metrics["brier"] < 0.240)
        and (metrics["logloss"] < 0.670)
        and (metrics["clv"] > 0)
        and (fold_roi_std < 0.30)
    )
    return {
        "tier": tier.value,
        "n_games": int(n),
        "n_bets": int(metrics["n_bets"]),
        "roi": float(metrics["roi"]),
        "brier": float(metrics["brier"]),
        "logloss": float(metrics["logloss"]),
        "clv": float(metrics["clv"]),
        "fold_roi_std": fold_roi_std,
        "pass_thresholds": pass_thresholds,
    }


@lru_cache(maxsize=1)
def default_mlb_moneyline_model() -> MLBMoneylineModel:
    X, y, _ = build_mlb_moneyline_training_data()
    base = MLBMoneylineBaseModel().fit(X, y)
    return MLBMoneylineModel(base_model=base, context_adjuster=MLBContextAdjuster())
