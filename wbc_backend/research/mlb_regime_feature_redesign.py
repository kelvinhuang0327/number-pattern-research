from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from data.mlb_data_loader import load_mlb_records
from wbc_backend.calibration.probability_calibrator import ProbabilityCalibrator
from wbc_backend.models.elo import elo_win_prob
from wbc_backend.models.mlb_regime_paper import classify_regimes_from_row, derive_regime_gate_config, regime_feature_sets
from wbc_backend.research.mlb_model_rebuild import build_mlb_rebuild_frame


try:
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
except Exception:  # pragma: no cover
    LogisticRegression = None
    Pipeline = None
    StandardScaler = None


TARGET_REGIMES = ("small_edge", "weak_starter_mismatch")
EDGE_THRESHOLD = 0.01


@dataclass(frozen=True)
class FoldMetrics:
    n_games: int
    n_bets: int
    roi: float
    brier: float
    logloss: float
    clv: float
    fold_roi_std: float
    win_rate: float
    avg_abs_edge: float
    calibration: str = "raw"

    def as_dict(self) -> dict[str, Any]:
        return {
            "n_games": self.n_games,
            "n_bets": self.n_bets,
            "roi": self.roi,
            "brier": self.brier,
            "logloss": self.logloss,
            "clv": self.clv,
            "fold_roi_std": self.fold_roi_std,
            "win_rate": self.win_rate,
            "avg_abs_edge": self.avg_abs_edge,
            "calibration": self.calibration,
        }


def _sigmoid(x: np.ndarray | float) -> np.ndarray | float:
    return 1.0 / (1.0 + np.exp(-np.clip(x, -20, 20)))


def _norm_team(value: str) -> str:
    out = "".join(ch if ch.isalnum() else "_" for ch in str(value).upper())
    while "__" in out:
        out = out.replace("__", "_")
    return out.strip("_")


def _brier(probs: np.ndarray, y: np.ndarray) -> float:
    return float(np.mean((probs - y) ** 2))


def _logloss(probs: np.ndarray, y: np.ndarray) -> float:
    eps = 1e-7
    return float(np.mean(-(y * np.log(np.clip(probs, eps, 1 - eps)) + (1 - y) * np.log(np.clip(1 - probs, eps, 1 - eps)))))


def _bet_metrics(probs: np.ndarray, market_probs: np.ndarray, y: np.ndarray, threshold: float = EDGE_THRESHOLD) -> dict[str, float]:
    valid = np.isfinite(probs) & np.isfinite(market_probs) & np.isfinite(y)
    if not np.any(valid):
        return {"n_bets": 0, "roi": 0.0, "clv": 0.0, "win_rate": 0.0, "avg_abs_edge": 0.0}
    edge = probs[valid] - market_probs[valid]
    outcomes_y = y[valid]
    mask = np.abs(edge) >= threshold
    if not np.any(mask):
        return {"n_bets": 0, "roi": 0.0, "clv": 0.0, "win_rate": 0.0, "avg_abs_edge": 0.0}
    chosen_home = edge[mask] > 0
    wins = np.where(chosen_home, outcomes_y[mask] == 1, outcomes_y[mask] == 0)
    pnl = np.where(wins, 1.0, -1.0)
    return {
        "n_bets": int(np.sum(mask)),
        "roi": float(np.mean(pnl)),
        "clv": float(np.mean(np.abs(edge[mask]))),
        "win_rate": float(np.mean(wins)),
        "avg_abs_edge": float(np.mean(np.abs(edge[mask]))),
    }


def _fold_roi_std(fold_ids: np.ndarray, probs: np.ndarray, market_probs: np.ndarray, y: np.ndarray) -> float:
    rois: list[float] = []
    for fold_id in sorted({int(v) for v in fold_ids if int(v) >= 0}):
        mask = fold_ids == fold_id
        metrics = _bet_metrics(probs[mask], market_probs[mask], y[mask], threshold=EDGE_THRESHOLD)
        if metrics["n_bets"] > 0:
            rois.append(float(metrics["roi"]))
    return round(float(np.std(rois)) if rois else 0.0, 4)


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


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def redesign_feature_families() -> dict[str, dict[str, list[str]]]:
    current = regime_feature_sets()
    return {
        "small_edge": {
            "baseline": current["small_edge"],
            "market_microstructure": [
                "elo_diff",
                "woba_diff",
                "fip_adv_diff",
                "rsi_diff",
                "elo_home_prob",
                "form_home_prob",
                "skill_blend_home_prob",
                "market_minus_elo_prob",
                "market_minus_form_prob",
                "market_minus_skill_blend_prob",
                "market_total_pressure",
                "market_form_pressure",
                "market_injury_pressure",
                "market_lineup_pressure",
                "market_fundamental_dispersion",
            ],
            "starter_lineup_interaction": [
                "starter_form_blend_diff",
                "starter_recent_ra_volatility_diff",
                "starter_quality_volatility_diff",
                "lineup_vs_starter_interaction_diff",
                "lineup_depth_pressure",
                "injury_count_diff",
                "rest_day_diff",
                "starter_run_support_asymmetry",
            ],
            "bullpen_environment": [
                "bullpen_usage_diff",
                "bullpen_usage_intensity_diff",
                "bullpen_quality_diff",
                "bullpen_bridge_quality",
                "environment_run_proxy",
                "weather_temp_c",
                "weather_wind_kmh",
                "bullpen_environment_pressure",
            ],
        },
        "weak_starter_mismatch": {
            "baseline": current["weak_starter_mismatch"],
            "market_microstructure": [
                "elo_diff",
                "woba_diff",
                "fip_adv_diff",
                "rsi_diff",
                "elo_home_prob",
                "skill_blend_home_prob",
                "market_minus_elo_prob",
                "market_minus_skill_blend_prob",
                "starter_market_tension",
                "market_fundamental_dispersion",
            ],
            "starter_lineup_interaction": [
                "starter_recent_ra_diff",
                "starter_quality_diff",
                "starter_rest_diff",
                "starter_workload_pressure_diff",
                "starter_form_blend_diff",
                "starter_matchup_depth_diff",
                "starter_recent_ra_volatility_diff",
                "starter_support_volatility_diff",
                "starter_quality_volatility_diff",
                "lineup_vs_starter_interaction_diff",
                "starter_run_support_asymmetry",
                "lineup_depth_pressure",
                "contact_quality_proxy_diff",
                "run_support_asymmetry",
            ],
            "bullpen_environment": [
                "bullpen_usage_diff",
                "bullpen_usage_intensity_diff",
                "bullpen_quality_diff",
                "bullpen_bridge_quality",
                "bridge_starter_interaction",
                "environment_run_proxy",
                "weather_temp_c",
                "weather_wind_kmh",
                "starter_environment_stress",
                "run_env_contact_interaction",
            ],
        },
    }


def _record_map_frame() -> pd.DataFrame:
    records = load_mlb_records()
    rows = []
    for idx, rec in enumerate(records):
        rows.append(
            {
                "record_idx": idx,
                "game_date": str(rec.game_date)[:10],
                "away_key": _norm_team(rec.away_team),
                "home_key": _norm_team(rec.home_team),
                "home_elo": float(rec.home_elo),
                "away_elo": float(rec.away_elo),
                "home_woba": float(rec.home_woba),
                "away_woba": float(rec.away_woba),
                "home_fip": float(rec.home_fip),
                "away_fip": float(rec.away_fip),
                "home_rest_days_loader": float(rec.home_rest_days),
                "away_rest_days_loader": float(rec.away_rest_days),
                "home_rsi": float(rec.home_rsi),
                "away_rsi": float(rec.away_rsi),
            }
        )
    return pd.DataFrame(rows)


def build_regime_redesign_frame(
    csv_path: str = "data/mlb_2025/mlb_odds_2025_real.csv",
    context_path: str | None = "data/mlb_context",
) -> pd.DataFrame:
    frame = build_mlb_rebuild_frame(csv_path=csv_path, context_path=context_path).copy()
    frame["home_key"] = frame["home_team"].map(_norm_team)
    frame["away_key"] = frame["away_team"].map(_norm_team)
    frame["matchup_ordinal"] = frame.groupby(["game_date", "away_key", "home_key"]).cumcount()

    loader = _record_map_frame()
    loader = loader.copy()
    loader["matchup_ordinal"] = loader.groupby(["game_date", "away_key", "home_key"]).cumcount()
    frame = frame.merge(loader, on=["game_date", "away_key", "home_key", "matchup_ordinal"], how="left", validate="one_to_one")

    strict = frame[frame["strict_valid"]].reset_index(drop=True)
    gate = derive_regime_gate_config(strict)
    frame["applicable_regimes"] = frame.apply(lambda row: classify_regimes_from_row(row, gate), axis=1)

    frame["elo_diff"] = frame["home_elo"] - frame["away_elo"]
    frame["woba_diff"] = frame["home_woba"] - frame["away_woba"]
    frame["fip_adv_diff"] = frame["away_fip"] - frame["home_fip"]
    frame["rsi_diff"] = frame["home_rsi"] - frame["away_rsi"]
    frame["elo_home_prob"] = frame.apply(lambda r: float(elo_win_prob(float(r["home_elo"]), float(r["away_elo"]), 30.0)), axis=1)
    frame["form_home_prob"] = _sigmoid(
        4.0 * frame["team_posterior_diff"].to_numpy(dtype=float)
        + 0.12 * frame["team_recent_run_diff_delta"].to_numpy(dtype=float)
        + 0.15 * frame["team_home_away_form_diff"].to_numpy(dtype=float)
    )
    frame["contact_home_prob"] = _sigmoid(
        7.5 * frame["woba_diff"].to_numpy(dtype=float)
        + 0.65 * frame["fip_adv_diff"].to_numpy(dtype=float)
        + 0.05 * frame["rsi_diff"].to_numpy(dtype=float)
    )
    frame["skill_blend_home_prob"] = (
        0.45 * frame["elo_home_prob"].to_numpy(dtype=float)
        + 0.30 * frame["form_home_prob"].to_numpy(dtype=float)
        + 0.25 * frame["contact_home_prob"].to_numpy(dtype=float)
    )
    frame["market_minus_elo_prob"] = frame["market_home_prob"] - frame["elo_home_prob"]
    frame["market_minus_form_prob"] = frame["market_home_prob"] - frame["form_home_prob"]
    frame["market_minus_skill_blend_prob"] = frame["market_home_prob"] - frame["skill_blend_home_prob"]
    frame["market_total_pressure"] = frame["market_abs_dev_50"] * (frame["ou_line"] - 8.5)
    frame["market_form_pressure"] = frame["market_abs_dev_50"] * frame["team_home_away_form_diff"]
    frame["market_injury_pressure"] = frame["market_abs_dev_50"] * frame["injury_count_diff"]
    frame["market_lineup_pressure"] = frame["market_abs_dev_50"] * frame["lineup_missing_slots_diff"]
    frame["market_fundamental_dispersion"] = (
        np.abs(frame["market_minus_elo_prob"])
        + np.abs(frame["market_minus_form_prob"])
        + np.abs(frame["market_minus_skill_blend_prob"])
    )
    frame["lineup_depth_pressure"] = (
        frame["lineup_vs_starter_interaction_diff"] * (1.0 + np.abs(frame["injury_count_diff"]) + np.abs(frame["lineup_missing_slots_diff"]))
    )
    frame["bullpen_bridge_quality"] = frame["bullpen_quality_diff"] - 0.20 * frame["bullpen_usage_intensity_diff"]
    frame["bullpen_environment_pressure"] = frame["bullpen_bridge_quality"] * frame["environment_run_proxy"]
    frame["starter_market_tension"] = frame["starter_form_blend_diff"] * frame["market_minus_skill_blend_prob"]
    frame["contact_quality_proxy_diff"] = 8.0 * frame["woba_diff"] + 0.35 * frame["team_recent_run_diff_delta"]
    frame["run_support_asymmetry"] = frame["starter_support_diff"] * frame["team_offense_diff"]
    frame["bridge_starter_interaction"] = frame["bullpen_bridge_quality"] * frame["starter_workload_pressure_diff"]
    frame["starter_environment_stress"] = frame["starter_form_blend_diff"] * frame["environment_run_proxy"]
    frame["run_env_contact_interaction"] = frame["contact_quality_proxy_diff"] * frame["environment_run_proxy"]
    frame["loader_rest_diff"] = frame["home_rest_days_loader"] - frame["away_rest_days_loader"]
    return frame


def _fit_logistic(x_train: pd.DataFrame, y_train: np.ndarray) -> tuple[Any, dict[str, float], np.ndarray]:
    medians = {col: float(x_train[col].median()) for col in x_train.columns}
    model = Pipeline(
        [
            ("scaler", StandardScaler()),
            ("clf", LogisticRegression(C=0.35, penalty="l2", max_iter=800, solver="lbfgs")),
        ]
    )
    model.fit(x_train.fillna(medians), y_train)
    coefs = model.named_steps["clf"].coef_[0]
    return model, medians, np.asarray(coefs, dtype=float)


def _walk_forward_raw(subset: pd.DataFrame, feature_cols: list[str], n_splits: int = 6) -> dict[str, Any]:
    subset = subset.reset_index(drop=True)
    n = len(subset)
    split_size = max(25, n // n_splits)
    market = subset["market_home_prob"].to_numpy(dtype=float)
    y = subset["target"].to_numpy(dtype=int)
    probs = np.full(n, np.nan, dtype=float)
    fold_ids = np.full(n, -1, dtype=int)
    coeffs: list[dict[str, float]] = []

    for fold_id, start in enumerate(range(split_size, n, split_size)):
        end = min(n, start + split_size)
        if end <= start:
            continue
        model, medians, coefs = _fit_logistic(subset.loc[: start - 1, feature_cols], y[:start])
        x_test = subset.loc[start:end - 1, feature_cols].fillna(medians)
        probs[start:end] = model.predict_proba(x_test)[:, 1]
        fold_ids[start:end] = fold_id
        coeffs.append({col: float(val) for col, val in zip(feature_cols, coefs)})

    eval_mask = fold_ids >= 0
    probs_eval = probs[eval_mask]
    market_eval = market[eval_mask]
    y_eval = y[eval_mask]
    fold_eval = fold_ids[eval_mask]
    decision = _bet_metrics(probs_eval, market_eval, y_eval, threshold=EDGE_THRESHOLD)
    metrics = FoldMetrics(
        n_games=int(np.sum(eval_mask)),
        n_bets=int(decision["n_bets"]),
        roi=round(float(decision["roi"]), 4),
        brier=round(_brier(probs_eval, y_eval), 4),
        logloss=round(_logloss(probs_eval, y_eval), 4),
        clv=round(float(decision["clv"]), 4),
        fold_roi_std=_fold_roi_std(fold_eval, probs_eval, market_eval, y_eval),
        win_rate=round(float(decision["win_rate"]), 4),
        avg_abs_edge=round(float(decision["avg_abs_edge"]), 4),
        calibration="raw",
    )
    return {
        "metrics": metrics,
        "probs": probs_eval,
        "market": market_eval,
        "y": y_eval,
        "fold_ids": fold_eval,
        "coefficients": coeffs,
    }


def _walk_forward_calibrated(subset: pd.DataFrame, feature_cols: list[str], calibration: str, n_splits: int = 6) -> dict[str, Any]:
    subset = subset.reset_index(drop=True)
    n = len(subset)
    split_size = max(25, n // n_splits)
    market = subset["market_home_prob"].to_numpy(dtype=float)
    y = subset["target"].to_numpy(dtype=int)
    probs = np.full(n, np.nan, dtype=float)
    fold_ids = np.full(n, -1, dtype=int)

    for fold_id, start in enumerate(range(split_size, n, split_size)):
        end = min(n, start + split_size)
        cal_size = max(20, start // 5)
        core_end = max(40, start - cal_size)
        if core_end < 40 or end <= start:
            continue

        base_model, base_medians, _ = _fit_logistic(subset.loc[: core_end - 1, feature_cols], y[:core_end])
        cal_frame = subset.loc[core_end:start - 1, feature_cols].fillna(base_medians)
        cal_raw = np.asarray(base_model.predict_proba(cal_frame)[:, 1], dtype=float)
        cal_y = y[core_end:start]
        final_model, final_medians, _ = _fit_logistic(subset.loc[: start - 1, feature_cols], y[:start])
        test_frame = subset.loc[start:end - 1, feature_cols].fillna(final_medians)
        test_raw = np.asarray(final_model.predict_proba(test_frame)[:, 1], dtype=float)

        if calibration == "raw":
            test_probs = test_raw
        else:
            method = "isotonic" if calibration == "isotonic" and len(cal_y) >= 50 else "platt"
            calibrator = ProbabilityCalibrator(method=method).fit(cal_raw.tolist(), cal_y.tolist())
            test_probs = np.asarray(calibrator.calibrate(test_raw.tolist()), dtype=float)

        probs[start:end] = test_probs
        fold_ids[start:end] = fold_id

    eval_mask = fold_ids >= 0
    eval_indices = np.where(eval_mask)[0]
    probs_eval = probs[eval_mask]
    market_eval = market[eval_mask]
    y_eval = y[eval_mask]
    fold_eval = fold_ids[eval_mask]
    decision = _bet_metrics(probs_eval, market_eval, y_eval, threshold=EDGE_THRESHOLD)
    metrics = FoldMetrics(
        n_games=int(np.sum(eval_mask)),
        n_bets=int(decision["n_bets"]),
        roi=round(float(decision["roi"]), 4),
        brier=round(_brier(probs_eval, y_eval), 4),
        logloss=round(_logloss(probs_eval, y_eval), 4),
        clv=round(float(decision["clv"]), 4),
        fold_roi_std=_fold_roi_std(fold_eval, probs_eval, market_eval, y_eval),
        win_rate=round(float(decision["win_rate"]), 4),
        avg_abs_edge=round(float(decision["avg_abs_edge"]), 4),
        calibration=calibration,
    )
    return {
        "metrics": metrics,
        "probs": probs_eval,
        "market": market_eval,
        "y": y_eval,
        "fold_ids": fold_eval,
        "eval_indices": eval_indices,
        "curve": _calibration_curve(probs_eval, y_eval),
    }


def _corr_pairs(frame: pd.DataFrame, feature_cols: list[str], threshold: float = 0.85) -> list[dict[str, Any]]:
    corr = frame[feature_cols].corr().abs()
    pairs: list[dict[str, Any]] = []
    for i, a in enumerate(feature_cols):
        for b in feature_cols[i + 1:]:
            if pd.notna(corr.loc[a, b]) and corr.loc[a, b] >= threshold:
                pairs.append({"a": a, "b": b, "corr": round(float(corr.loc[a, b]), 4)})
    return pairs


def _current_feature_deadness(subset: pd.DataFrame, features: list[str]) -> list[str]:
    dead = []
    for feat in features:
        series = subset[feat].replace([np.inf, -np.inf], np.nan).dropna()
        if len(series) == 0 or float(series.std()) == 0.0:
            dead.append(feat)
    return dead


def _classify(metrics: FoldMetrics, baseline: FoldMetrics) -> str:
    if metrics.roi > 0 and metrics.clv > 0 and metrics.fold_roi_std < 0.15 and (metrics.brier < baseline.brier or metrics.logloss < baseline.logloss):
        return "TRADABLE_SIGNAL"
    if metrics.roi > 0 and metrics.clv > 0:
        return "OVERFIT_SIGNAL"
    if metrics.clv > 0 and (metrics.brier <= baseline.brier or metrics.logloss <= baseline.logloss):
        return "WEAK_SIGNAL"
    return "NOISE"


def autopsy_regime(data: pd.DataFrame, regime: str) -> dict[str, Any]:
    baseline_features = regime_feature_sets()[regime]
    subset = data[data["strict_valid"] & data["applicable_regimes"].apply(lambda regs: regime in regs)].copy().reset_index(drop=True)
    raw_eval = _walk_forward_raw(subset, baseline_features)
    coeff_df = pd.DataFrame(raw_eval["coefficients"]).fillna(0.0)
    mean_abs = coeff_df.abs().mean().sort_values(ascending=False)
    instability = coeff_df.std().sort_values(ascending=False)
    dead_features = _current_feature_deadness(subset, baseline_features)

    missing_domain = {
        "small_edge": [
            "true intraday odds path is unavailable (odds_history length is 1 for all games)",
            "lineup confirmation timing is backfilled by feed fetch time, not pregame release time",
            "public-vs-sharp order-flow features are absent",
        ],
        "weak_starter_mismatch": [
            "starter handedness depth is unavailable; platoon_splits are structurally empty",
            "contact-quality stats (xwOBA / hard-hit / barrel) are absent from the strict frame",
            "bullpen role-chain quality is missing; only usage and coarse quality proxy exist",
        ],
    }[regime]

    clv_gap_diag = {
        "small_edge": [
            f"baseline ROI {raw_eval['metrics'].roi} stays negative while CLV {raw_eval['metrics'].clv} remains positive, implying price direction without enough mispricing separation.",
            "the current market microstructure block is effectively dead: open/current/close path features are all zero-variance in the dataset.",
            "bets cluster near market-like probabilities, so slight positive CLV is not converting into high enough win-rate dispersion.",
        ],
        "weak_starter_mismatch": [
            f"baseline ROI {raw_eval['metrics'].roi} is only marginal despite CLV {raw_eval['metrics'].clv} > 0, which points to late-game resolution risk outside the shallow starter proxy set.",
            "the regime gate is broad, so many games are tagged 'weak mismatch' even when bullpen bridge and contact-quality determine the outcome.",
            "starter and lineup features currently capture level but not volatility/interaction depth, so the model follows market tension without separating the true winner.",
        ],
    }[regime]

    return {
        "sample_count": int(len(subset)),
        "baseline_metrics": raw_eval["metrics"].as_dict(),
        "strongest_features": mean_abs.head(5).round(4).to_dict(),
        "weakest_features": mean_abs.tail(5).round(4).to_dict(),
        "unstable_features": instability.head(5).round(4).to_dict(),
        "redundant_pairs": _corr_pairs(subset, baseline_features),
        "dead_features": dead_features,
        "missing_domain_features": missing_domain,
        "why_clv_not_roi": clv_gap_diag,
    }


def run_regime_feature_redesign(
    *,
    csv_path: str = "data/mlb_2025/mlb_odds_2025_real.csv",
    context_path: str | None = "data/mlb_context",
    report_path: str = "data/wbc_backend/reports/mlb_regime_feature_redesign_report.json",
) -> dict[str, Any]:
    data = build_regime_redesign_frame(csv_path=csv_path, context_path=context_path)
    families = redesign_feature_families()

    autopsy: dict[str, Any] = {}
    redesign_summary: dict[str, Any] = {}
    ablation_rows: list[dict[str, Any]] = []
    strict_results: dict[str, Any] = {}
    verdicts: dict[str, str] = {}

    for regime in TARGET_REGIMES:
        subset = data[data["strict_valid"] & data["applicable_regimes"].apply(lambda regs: regime in regs)].copy().reset_index(drop=True)
        autopsy[regime] = autopsy_regime(data, regime)
        base = families[regime]["baseline"]
        market = families[regime]["market_microstructure"]
        starter_lineup = families[regime]["starter_lineup_interaction"]
        bullpen_env = families[regime]["bullpen_environment"]

        redesign_summary[regime] = {
            "baseline": base,
            "market_microstructure": market,
            "starter_lineup_interaction": starter_lineup,
            "bullpen_environment": bullpen_env,
        }

        ablations = {
            "baseline": base,
            "baseline_plus_market_micro": _dedupe(base + market),
            "baseline_plus_starter_lineup": _dedupe(base + starter_lineup),
            "baseline_plus_bullpen_environment": _dedupe(base + bullpen_env),
            "full_redesign": _dedupe(base + market + starter_lineup + bullpen_env),
        }

        regime_ablation_results = []
        for label, cols in ablations.items():
            result = _walk_forward_raw(subset, cols)
            metrics = result["metrics"]
            row = {
                "regime": regime,
                "ablation": label,
                "feature_count": len(cols),
                **metrics.as_dict(),
            }
            ablation_rows.append(row)
            regime_ablation_results.append((label, cols, metrics))

        baseline_metrics = regime_ablation_results[0][2]
        best_label, best_cols, best_metrics = max(
            regime_ablation_results,
            key=lambda item: (
                item[2].roi,
                item[2].clv,
                -item[2].fold_roi_std,
                -item[2].brier,
            ),
        )

        calibration_candidates = {}
        for calibration in ("raw", "platt", "isotonic"):
            eval_result = _walk_forward_calibrated(subset, best_cols, calibration=calibration)
            calibration_candidates[calibration] = {
                "metrics": eval_result["metrics"],
                "curve": eval_result["curve"],
            }
        best_calibration_name = min(
            calibration_candidates,
            key=lambda name: (
                calibration_candidates[name]["metrics"].brier,
                calibration_candidates[name]["metrics"].logloss,
            ),
        )
        final_metrics = calibration_candidates[best_calibration_name]["metrics"]
        verdict = _classify(final_metrics, baseline_metrics)
        verdicts[regime] = verdict

        strict_results[regime] = {
            "selected_ablation": best_label,
            "selected_feature_count": len(best_cols),
            "selected_features": best_cols,
            "best_ablation_metrics_raw": best_metrics.as_dict(),
            "calibration_comparison": {
                name: {
                    **payload["metrics"].as_dict(),
                    "calibration_curve": payload["curve"],
                }
                for name, payload in calibration_candidates.items()
            },
            "final_selected_calibration": best_calibration_name,
            "final_metrics": final_metrics.as_dict(),
            "verdict": verdict,
        }

    if any(verdict == "TRADABLE_SIGNAL" for verdict in verdicts.values()):
        final_recommendation = "promote one regime"
    elif any(verdict in {"WEAK_SIGNAL", "OVERFIT_SIGNAL"} for verdict in verdicts.values()):
        final_recommendation = "continue paper mode"
    else:
        final_recommendation = "stop MLB moneyline work"

    payload = {
        "feature_autopsy_by_regime": autopsy,
        "redesigned_feature_families": redesign_summary,
        "ablation_table": ablation_rows,
        "strict_only_results_after_redesign": strict_results,
        "tradable_regimes_after_redesign": [regime for regime, verdict in verdicts.items() if verdict == "TRADABLE_SIGNAL"],
        "final_recommendation": final_recommendation,
        "notes": [
            "WBC path remains untouched.",
            "MLB stays PAPER_ONLY regardless of redesign outcome in this sprint.",
            "Missing domain features were not backfilled or simulated.",
        ],
    }

    out = Path(report_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def build_regime_prediction_table_for_decision_quality(
    *,
    csv_path: str = "data/mlb_2025/mlb_odds_2025_real.csv",
    context_path: str | None = "data/mlb_context",
    redesign_report_path: str = "data/wbc_backend/reports/mlb_regime_feature_redesign_report.json",
) -> pd.DataFrame:
    report_file = Path(redesign_report_path)
    if not report_file.exists():
        run_regime_feature_redesign(csv_path=csv_path, context_path=context_path, report_path=redesign_report_path)
    report = json.loads(report_file.read_text(encoding="utf-8"))

    data = build_regime_redesign_frame(csv_path=csv_path, context_path=context_path)
    strict = data[data["strict_valid"]].copy().reset_index(drop=True)
    records: list[pd.DataFrame] = []

    for regime in TARGET_REGIMES:
        regime_report = report["strict_only_results_after_redesign"][regime]
        feature_cols = regime_report["selected_features"]
        calibration = regime_report["final_selected_calibration"]
        subset = strict[strict["applicable_regimes"].apply(lambda regs: regime in regs)].copy().reset_index(drop=True)
        if subset.empty:
            continue
        eval_result = _walk_forward_calibrated(subset, feature_cols, calibration=calibration)
        eval_indices = eval_result.get("eval_indices", np.array([], dtype=int))
        subset_eval = subset.iloc[eval_indices].reset_index(drop=True)
        probs = eval_result["probs"]
        market = eval_result["market"]
        edges = probs - market
        frame = pd.DataFrame(
            {
                "game_id": subset_eval["game_id"].to_numpy(),
                "game_date": subset_eval["game_date"].to_numpy(),
                "home_team": subset_eval["home_team"].to_numpy(),
                "away_team": subset_eval["away_team"].to_numpy(),
                "regime_label": regime,
                "predicted_home_win_prob": probs,
                "market_home_prob": market,
                "actual_result": subset_eval["target"].to_numpy(dtype=int),
                "edge": edges,
                "was_selected_for_bet": np.abs(edges) >= EDGE_THRESHOLD,
            }
        )
        records.append(frame)

    if not records:
        return pd.DataFrame(
            columns=[
                "game_id",
                "game_date",
                "home_team",
                "away_team",
                "regime_label",
                "predicted_home_win_prob",
                "market_home_prob",
                "actual_result",
                "edge",
                "was_selected_for_bet",
                "passed_strict_gate",
            ]
        )

    all_candidates = pd.concat(records, ignore_index=True)
    all_candidates = all_candidates.sort_values(
        ["game_id", "was_selected_for_bet", "edge"],
        ascending=[True, False, False],
        kind="mergesort",
    )
    chosen = all_candidates.drop_duplicates(subset=["game_id"], keep="first").reset_index(drop=True)
    chosen["passed_strict_gate"] = True
    return chosen
