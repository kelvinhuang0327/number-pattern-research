from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from wbc_backend.optimization.dataset import build_pregame_features, load_odds_results
from wbc_backend.optimization.modeling import (
    FEATURE_COLUMNS,
    apply_isotonic,
    apply_platt,
    fit_isotonic,
    fit_logistic_model,
    fit_platt,
    poisson_prob_matrix,
    predict_home_win_prob,
)


ODDS_BANDS = [(1.50, 1.80), (1.81, 2.10), (2.11, 2.60), (2.61, 3.50)]


@dataclass
class BacktestSummary:
    games: int
    ml_bets: int
    ml_roi: float
    ml_hit_rate: float
    rl_bets: int
    rl_roi: float
    ou_bets: int
    ou_roi: float
    brier: float
    logloss: float
    ece: float = 0.0   # Expected Calibration Error（deployment gate P1-A 硬閘，目標 < 0.12）


def _ev(prob: float, dec: float) -> float:
    return prob * (dec - 1.0) - (1.0 - prob)


def _compute_ece(y_prob: np.ndarray, y_true: np.ndarray, n_bins: int = 10) -> float:
    """Expected Calibration Error（等距分箱，面積加權平均絕對誤差）。"""
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    n = len(y_prob)
    if n == 0:
        return 0.0
    ece = 0.0
    for i in range(n_bins):
        lo, hi = bins[i], bins[i + 1]
        mask = (y_prob >= lo) & (y_prob < hi)
        cnt = int(mask.sum())
        if cnt == 0:
            continue
        ece += (cnt / n) * abs(float(y_prob[mask].mean()) - float(y_true[mask].mean()))
    return round(float(ece), 6)


def _band_key(odds: float) -> str:
    for lo, hi in ODDS_BANDS:
        if lo <= odds <= hi:
            return f"{lo:.2f}-{hi:.2f}"
    return "other"


def run_walkforward_backtest(  # noqa: C901
    path: str,
    min_train_games: int = 240,
    retrain_every: int = 40,
    ev_threshold: float = 0.02,
    lookback: int = 15,
    min_confidence: float = 0.0,
    markets: tuple[str, ...] = ("ML", "RL", "OU"),
    calibration_method: str = "platt",
    alpha_lab: bool = False,
    alpha_max_candidates: int = 40,
    alpha_threshold: float = 0.0005,
) -> tuple[BacktestSummary, dict]:
    raw = load_odds_results(path)
    df = build_pregame_features(raw, lookback=lookback)

    # --- Alpha Feature Lab (opt-in) ---
    lab = None
    active_features: list[str] | None = None
    alpha_stability: list = []
    if alpha_lab:
        from wbc_backend.intelligence.auto_feature_lab import AlphaFeatureLab
        lab = AlphaFeatureLab(
            base_features=FEATURE_COLUMNS,
            operators=("mul", "ratio"),
            max_candidates=alpha_max_candidates,
        )
        df = lab.generate_candidates(df)

    y_true = []
    y_prob = []

    ml_profit = 0.0
    rl_profit = 0.0
    ou_profit = 0.0
    ml_bets = 0
    rl_bets = 0
    ou_bets = 0
    ml_hits = 0

    ml_band_profit = {}
    ml_band_bets = {}

    win_model = None
    platt_calibrator = None
    iso_calibrator = None

    for i in range(min_train_games, len(df)):
        if win_model is None or (i - min_train_games) % retrain_every == 0:
            train = df.iloc[:i].copy()

            # --- Alpha Lab: OOF feature selection at each retrain ---
            if lab is not None:
                val_end = i
                val_start = max(0, i - retrain_every)
                if val_start > 0:
                    X_tr = train.iloc[:val_start]
                    X_vl = train.iloc[val_start:val_end]
                    y_tr = X_tr["home_win"].to_numpy(dtype=float)
                    y_vl = X_vl["home_win"].to_numpy(dtype=float)
                    candidate_cols = FEATURE_COLUMNS + lab.candidate_names
                    present = [c for c in candidate_cols if c in train.columns]
                    sel = lab.rank_and_select(
                        X_tr[present], y_tr,
                        X_vl[present], y_vl,
                        threshold=alpha_threshold,
                    )
                    active_features = sel.survivors
                    alpha_stability.append(sel)
                else:
                    active_features = FEATURE_COLUMNS

            fn = active_features if (lab is not None and active_features) else None
            win_model = fit_logistic_model(train, feature_names=fn)
            raw_train_prob = predict_home_win_prob(win_model, train)
            y_train = train["home_win"].to_numpy(dtype=float)
            platt_calibrator = fit_platt(raw_train_prob, y_train)
            iso_calibrator = fit_isotonic(raw_train_prob, y_train)

        row = df.iloc[[i]].copy()
        p_home_raw = predict_home_win_prob(win_model, row)

        if calibration_method == "isotonic" and iso_calibrator is not None:
            p_home = float(apply_isotonic(iso_calibrator, p_home_raw)[0])
        else:
            p_home = float(apply_platt(platt_calibrator, p_home_raw)[0])

        p_away = 1.0 - p_home

        y_true.append(int(row.iloc[0]["home_win"]))
        y_prob.append(p_home)

        lh = float(row.iloc[0]["exp_home_runs_base"]) * (0.92 + 0.16 * p_home)
        la = float(row.iloc[0]["exp_away_runs_base"]) * (0.92 + 0.16 * p_away)

        matrix = poisson_prob_matrix(np.array([lh]), np.array([la]), max_runs=15)[0]

        if "ML" in markets:
            home_dec = float(row.iloc[0]["home_ml_dec"])
            away_dec = float(row.iloc[0]["away_ml_dec"])
            ev_home = _ev(p_home, home_dec)
            ev_away = _ev(p_away, away_dec)
            confidence = abs(p_home - 0.5)
            home_win = int(row.iloc[0]["home_win"])
            if max(ev_home, ev_away) >= ev_threshold and confidence >= min_confidence:
                if ev_home >= ev_away:
                    won = home_win == 1
                    profit = (home_dec - 1.0) if won else -1.0
                    ml_profit += profit
                    ml_hits += int(won)
                    band = _band_key(home_dec)
                else:
                    won = home_win == 0
                    profit = (away_dec - 1.0) if won else -1.0
                    ml_profit += profit
                    ml_hits += int(won)
                    band = _band_key(away_dec)
                ml_bets += 1
                ml_band_profit[band] = ml_band_profit.get(band, 0.0) + profit
                ml_band_bets[band] = ml_band_bets.get(band, 0) + 1

        if "RL" in markets:
            spread = float(row.iloc[0]["home_spread"])
            home_cover_prob = 0.0
            for h in range(matrix.shape[0]):
                for a in range(matrix.shape[1]):
                    if h + spread > a:
                        home_cover_prob += matrix[h, a]
            away_cover_prob = 1.0 - home_cover_prob
            home_rl_dec = float(row.iloc[0]["rl_home_dec"])
            away_rl_dec = float(row.iloc[0]["rl_away_dec"])
            ev_h_rl = _ev(home_cover_prob, home_rl_dec)
            ev_a_rl = _ev(away_cover_prob, away_rl_dec)
            home_cover = int(row.iloc[0]["home_cover"])
            if max(ev_h_rl, ev_a_rl) >= ev_threshold:
                if ev_h_rl >= ev_a_rl:
                    won = home_cover == 1
                    rl_profit += (home_rl_dec - 1.0) if won else -1.0
                else:
                    won = home_cover == 0
                    rl_profit += (away_rl_dec - 1.0) if won else -1.0
                rl_bets += 1

        if "OU" in markets:
            line_total = float(row.iloc[0]["line_total"])
            p_over = 0.0
            for h in range(matrix.shape[0]):
                for a in range(matrix.shape[1]):
                    if (h + a) > line_total:
                        p_over += matrix[h, a]
            p_under = 1.0 - p_over
            over_dec = float(row.iloc[0]["over_dec"])
            under_dec = float(row.iloc[0]["under_dec"])
            ev_over = _ev(p_over, over_dec)
            ev_under = _ev(p_under, under_dec)
            over_hit = int(row.iloc[0]["over_hit"])
            if max(ev_over, ev_under) >= ev_threshold:
                if ev_over >= ev_under:
                    won = over_hit == 1
                    ou_profit += (over_dec - 1.0) if won else -1.0
                else:
                    won = over_hit == 0
                    ou_profit += (under_dec - 1.0) if won else -1.0
                ou_bets += 1

    y_true_arr = np.array(y_true, dtype=float)
    y_prob_arr = np.clip(np.array(y_prob, dtype=float), 1e-6, 1 - 1e-6)
    brier = float(np.mean((y_prob_arr - y_true_arr) ** 2))
    logloss = float(-np.mean(y_true_arr * np.log(y_prob_arr) + (1 - y_true_arr) * np.log(1 - y_prob_arr)))
    ece = _compute_ece(y_prob_arr, y_true_arr)

    summary = BacktestSummary(
        games=len(y_true),
        ml_bets=ml_bets,
        ml_roi=(ml_profit / ml_bets) if ml_bets else 0.0,
        ml_hit_rate=(ml_hits / ml_bets) if ml_bets else 0.0,
        rl_bets=rl_bets,
        rl_roi=(rl_profit / rl_bets) if rl_bets else 0.0,
        ou_bets=ou_bets,
        ou_roi=(ou_profit / ou_bets) if ou_bets else 0.0,
        brier=brier,
        logloss=logloss,
        ece=ece,
    )

    odds_band_roi = {
        band: (ml_band_profit[band] / ml_band_bets[band])
        for band in ml_band_bets
        if ml_band_bets[band] > 0
    }
    high_conf_bands = [band for band, roi in odds_band_roi.items() if roi > 0 and ml_band_bets.get(band, 0) >= 80]

    artifacts = {
        "calibration": {"a": platt_calibrator.a, "b": platt_calibrator.b},
        "params": {
            "min_train_games": min_train_games,
            "retrain_every": retrain_every,
            "ev_threshold": ev_threshold,
            "lookback": lookback,
            "min_confidence": min_confidence,
            "markets": list(markets),
            "calibration_method": calibration_method,
            "alpha_lab": alpha_lab,
        },
        "odds_band_stats": {
            "roi": odds_band_roi,
            "bets": ml_band_bets,
            "high_confidence_bands": high_conf_bands,
        },
    }

    # Alpha Lab stability report
    if lab is not None and alpha_stability:
        stability = lab.compute_stability(alpha_stability)
        artifacts["alpha_lab"] = {
            "candidates_generated": len(lab.candidate_names),
            "final_features": active_features or FEATURE_COLUMNS,
            "feature_stability": {
                k: round(v, 3) for k, v in stability.items()
            },
            "windows_evaluated": len(alpha_stability),
        }

    return summary, artifacts
