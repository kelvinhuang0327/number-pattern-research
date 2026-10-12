from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

import numpy as np

from wbc_backend.calibration.probability_calibrator import ProbabilityCalibrator
from wbc_backend.mlb_data.validator import MLBValidityTier

from .mlb_context_adjuster import MLBContextAdjuster
from .mlb_moneyline import (
    _tier_indices,
    build_mlb_moneyline_training_data,
)
from .mlb_moneyline_base import MLBMoneylineBaseModel
from wbc_backend.mlb_data.ingestion import load_mlb_game_data


@dataclass(frozen=True)
class BucketRow:
    bucket: str
    n: int
    predicted_mean: float
    actual_rate: float
    abs_error: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "bucket": self.bucket,
            "n": self.n,
            "predicted_mean": self.predicted_mean,
            "actual_rate": self.actual_rate,
            "abs_error": self.abs_error,
        }


def _brier(probs: np.ndarray, y: np.ndarray) -> float:
    return float(np.mean((probs - y) ** 2))


def _logloss(probs: np.ndarray, y: np.ndarray) -> float:
    eps = 1e-7
    return float(np.mean(-(y * np.log(np.clip(probs, eps, 1 - eps)) + (1 - y) * np.log(np.clip(1 - probs, eps, 1 - eps)))))


def _ece(probs: np.ndarray, y: np.ndarray, n_bins: int = 10) -> float:
    bins = np.linspace(0, 1, n_bins + 1)
    total = max(1, len(probs))
    ece = 0.0
    for i in range(n_bins):
        lo = bins[i]
        hi = bins[i + 1]
        mask = (probs >= lo) & (probs < hi if i < n_bins - 1 else probs <= hi)
        if not np.any(mask):
            continue
        pred_mean = float(np.mean(probs[mask]))
        actual_rate = float(np.mean(y[mask]))
        ece += (np.sum(mask) / total) * abs(pred_mean - actual_rate)
    return float(ece)


def _calibration_curve(probs: np.ndarray, y: np.ndarray, n_bins: int = 10) -> list[BucketRow]:
    bins = np.linspace(0, 1, n_bins + 1)
    rows: list[BucketRow] = []
    for i in range(n_bins):
        lo = bins[i]
        hi = bins[i + 1]
        mask = (probs >= lo) & (probs < hi if i < n_bins - 1 else probs <= hi)
        if not np.any(mask):
            continue
        pred_mean = float(np.mean(probs[mask]))
        actual_rate = float(np.mean(y[mask]))
        rows.append(
            BucketRow(
                bucket=f"{lo:.1f}-{hi:.1f}",
                n=int(np.sum(mask)),
                predicted_mean=round(pred_mean, 4),
                actual_rate=round(actual_rate, 4),
                abs_error=round(abs(pred_mean - actual_rate), 4),
            )
        )
    return rows


def _compute_side_metrics(
    probs: np.ndarray,
    y: np.ndarray,
    market_probs: np.ndarray,
    threshold: float,
    confidence_cutoff: float = 0.0,
    ranking_score: np.ndarray | None = None,
    top_pct: float | None = None,
) -> dict[str, Any]:
    edge = probs - market_probs
    confidence = np.abs(probs - 0.5)
    candidate_mask = (np.abs(edge) >= threshold) & (confidence >= confidence_cutoff)
    if ranking_score is not None and top_pct is not None and np.any(candidate_mask):
        candidate_idx = np.where(candidate_mask)[0]
        k = max(1, int(np.ceil(len(candidate_idx) * top_pct)))
        order = candidate_idx[np.argsort(ranking_score[candidate_idx])[::-1]]
        keep = set(order[:k].tolist())
        candidate_mask = np.array([i in keep for i in range(len(probs))], dtype=bool)
    bet_idx = np.where(candidate_mask)[0]
    if len(bet_idx) == 0:
        return {
            "n_bets": 0,
            "roi": 0.0,
            "clv": 0.0,
            "win_rate": 0.0,
            "avg_edge": 0.0,
        }

    pick_home = edge[bet_idx] > 0
    wins = np.where(pick_home, y[bet_idx] == 1, y[bet_idx] == 0)
    pnl = np.where(wins, 1.0, -1.0)
    return {
        "n_bets": int(len(bet_idx)),
        "roi": float(np.mean(pnl)),
        "clv": float(np.mean(np.abs(edge[bet_idx]))),
        "win_rate": float(np.mean(wins)),
        "avg_edge": float(np.mean(np.abs(edge[bet_idx]))),
    }


def _build_ranking_scores(probs: np.ndarray, market_probs: np.ndarray) -> dict[str, np.ndarray]:
    edge = np.abs(probs - market_probs)
    confidence = np.abs(probs - 0.5)
    return {
        "expected_value": edge,
        "confidence": confidence,
        "clv_proxy": edge * np.maximum(confidence, 1e-6),
    }


def _fold_rule_roi_std(
    folds: list[dict[str, Any]],
    probs: np.ndarray,
    y: np.ndarray,
    market_probs: np.ndarray,
    threshold: float,
    confidence_cutoff: float,
) -> float:
    rois: list[float] = []
    for fold in folds:
        s = int(fold["eval_offset_start"])
        e = int(fold["eval_offset_end"])
        if e <= s:
            continue
        metrics = _compute_side_metrics(
            probs[s:e],
            y[s:e],
            market_probs[s:e],
            threshold=threshold,
            confidence_cutoff=confidence_cutoff,
        )
        if metrics["n_bets"] > 0:
            rois.append(float(metrics["roi"]))
    return float(np.std(rois)) if rois else 0.0


def _generate_walk_forward_outputs(
    *,
    tier: MLBValidityTier,
    csv_path: str,
    n_splits: int,
    context_path: str | None,
) -> dict[str, Any]:
    X, y, df = build_mlb_moneyline_training_data(csv_path)
    all_rows = load_mlb_game_data(csv_path=csv_path, context_path=context_path)
    idx = _tier_indices(df, tier=tier, context_path=context_path)
    if len(idx) == 0:
        return {
            "tier": tier.value,
            "n_games": 0,
            "eval_games": 0,
            "raw_probs": np.array([], dtype=float),
            "platt_probs": np.array([], dtype=float),
            "isotonic_probs": np.array([], dtype=float),
            "market_probs": np.array([], dtype=float),
            "y": np.array([], dtype=int),
            "folds": [],
        }

    X_t = X[idx]
    y_t = y[idx]
    market_probs = X_t[:, 0].copy()
    rows_t = [all_rows[i] for i in idx]
    n = len(y_t)
    split_size = max(40, n // n_splits)
    raw_probs = np.full(n, np.nan, dtype=float)
    platt_probs = np.full(n, np.nan, dtype=float)
    isotonic_probs = np.full(n, np.nan, dtype=float)
    folds: list[dict[str, Any]] = []
    eval_cursor = 0
    adjuster = MLBContextAdjuster()

    for start in range(split_size, n, split_size):
        end = min(n, start + split_size)
        cal_size = max(20, start // 5)
        core_end = max(20, start - cal_size)
        # Calibration holdout is the last cal_size samples before the test fold.
        core_model = MLBMoneylineBaseModel().fit(X_t[:core_end], y_t[:core_end])
        cal_raw = np.array(
            [adjuster.adjust_home_prob(float(p), rows_t[core_end + i]) for i, p in enumerate(core_model.predict_proba(X_t[core_end:start]))],
            dtype=float,
        )
        cal_y = y_t[core_end:start]

        platt = ProbabilityCalibrator(method="platt").fit(cal_raw.tolist(), cal_y.tolist())
        isotonic_method = "isotonic" if len(cal_y) >= 50 else "platt"
        isotonic = ProbabilityCalibrator(method=isotonic_method).fit(cal_raw.tolist(), cal_y.tolist())

        final_model = MLBMoneylineBaseModel().fit(X_t[:start], y_t[:start])
        fold_raw = np.array(
            [adjuster.adjust_home_prob(float(p), rows_t[start + i]) for i, p in enumerate(final_model.predict_proba(X_t[start:end]))],
            dtype=float,
        )
        raw_probs[start:end] = fold_raw
        platt_probs[start:end] = np.asarray(platt.calibrate(fold_raw.tolist()), dtype=float)
        isotonic_probs[start:end] = np.asarray(isotonic.calibrate(fold_raw.tolist()), dtype=float)
        folds.append(
            {
                "start": int(start),
                "end": int(end),
                "train_size": int(start),
                "calibration_size": int(start - core_end),
                "platt_method": "platt",
                "isotonic_method": isotonic_method,
                "eval_offset_start": int(eval_cursor),
                "eval_offset_end": int(eval_cursor + (end - start)),
            }
        )
        eval_cursor += end - start

    eval_mask = ~np.isnan(raw_probs)
    return {
        "tier": tier.value,
        "n_games": int(n),
        "eval_games": int(np.sum(eval_mask)),
        "raw_probs": raw_probs[eval_mask],
        "platt_probs": platt_probs[eval_mask],
        "isotonic_probs": isotonic_probs[eval_mask],
        "market_probs": market_probs[eval_mask],
        "y": y_t[eval_mask],
        "folds": folds,
    }


def optimize_mlb_decision_layer(
    *,
    tier: MLBValidityTier = MLBValidityTier.STRICT_VALID,
    research_tier: MLBValidityTier = MLBValidityTier.RESEARCH_VALID,
    csv_path: str = "data/mlb_2025/mlb_odds_2025_real.csv",
    n_splits: int = 6,
    context_path: str | None = "data/mlb_context",
    report_path: str = "data/wbc_backend/reports/mlb_decision_optimization_report.json",
) -> dict[str, Any]:
    strict = _generate_walk_forward_outputs(
        tier=tier,
        csv_path=csv_path,
        n_splits=n_splits,
        context_path=context_path,
    )
    research = _generate_walk_forward_outputs(
        tier=research_tier,
        csv_path=csv_path,
        n_splits=n_splits,
        context_path=context_path,
    )

    if strict["eval_games"] == 0:
        payload = {"status": "NO_STRICT_GAMES", "tier": tier.value}
        Path(report_path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return payload

    raw_probs = strict["raw_probs"]
    platt_probs = strict["platt_probs"]
    isotonic_probs = strict["isotonic_probs"]
    market_probs = strict["market_probs"]
    y = strict["y"]

    calibration_candidates = {
        "raw": raw_probs,
        "platt": platt_probs,
        "isotonic": isotonic_probs,
    }
    calibration_metrics = {
        name: {
            "brier": round(_brier(probs, y), 4),
            "logloss": round(_logloss(probs, y), 4),
            "ece": round(_ece(probs, y), 4),
        }
        for name, probs in calibration_candidates.items()
    }
    best_calibration_name = min(calibration_metrics, key=lambda name: (calibration_metrics[name]["brier"], calibration_metrics[name]["logloss"]))
    best_probs = calibration_candidates[best_calibration_name]

    threshold_sweep = []
    for threshold in (0.01, 0.02, 0.03, 0.05):
        metrics = _compute_side_metrics(best_probs, y, market_probs, threshold=threshold)
        threshold_sweep.append(
            {
                "threshold": threshold,
                "n_bets": metrics["n_bets"],
                "roi": round(metrics["roi"], 4),
                "clv": round(metrics["clv"], 4),
                "win_rate": round(metrics["win_rate"], 4),
            }
        )

    ranking_results = []
    ranking_scores = _build_ranking_scores(best_probs, market_probs)
    for score_name, score_values in ranking_scores.items():
        for pct in (0.10, 0.20, 0.30):
            metrics = _compute_side_metrics(
                best_probs,
                y,
                market_probs,
                threshold=0.01,
                ranking_score=score_values,
                top_pct=pct,
            )
            ranking_results.append(
                {
                    "ranking": score_name,
                    "top_pct": pct,
                    "n_bets": metrics["n_bets"],
                    "roi": round(metrics["roi"], 4),
                    "clv": round(metrics["clv"], 4),
                    "win_rate": round(metrics["win_rate"], 4),
                }
            )

    rule_grid = []
    min_bets = max(30, int(0.02 * strict["eval_games"]))
    for threshold in (0.01, 0.02, 0.03, 0.05):
        for confidence_cutoff in (0.0, 0.02, 0.04, 0.06, 0.08, 0.10):
            metrics = _compute_side_metrics(
                best_probs,
                y,
                market_probs,
                threshold=threshold,
                confidence_cutoff=confidence_cutoff,
            )
            rule_grid.append(
                {
                    "threshold": threshold,
                    "confidence_cutoff": confidence_cutoff,
                    "n_bets": metrics["n_bets"],
                    "roi": round(metrics["roi"], 4),
                    "clv": round(metrics["clv"], 4),
                    "win_rate": round(metrics["win_rate"], 4),
                }
            )
    viable_rules = [row for row in rule_grid if row["n_bets"] >= min_bets] or rule_grid
    best_rule = max(viable_rules, key=lambda row: (row["roi"], row["clv"], row["n_bets"], -abs(row["confidence_cutoff"] - 0.04)))
    best_rule_metrics = _compute_side_metrics(
        best_probs,
        y,
        market_probs,
        threshold=float(best_rule["threshold"]),
        confidence_cutoff=float(best_rule["confidence_cutoff"]),
    )

    strict_baseline = {
        "n_games": strict["eval_games"],
        "brier": round(_brier(raw_probs, y), 4),
        "logloss": round(_logloss(raw_probs, y), 4),
        "clv": round(_compute_side_metrics(raw_probs, y, market_probs, threshold=0.03)["clv"], 4),
        "roi": round(_compute_side_metrics(raw_probs, y, market_probs, threshold=0.03)["roi"], 4),
    }
    strict_optimized = {
        "n_games": strict["eval_games"],
        "calibration_method": best_calibration_name,
        "brier": round(_brier(best_probs, y), 4),
        "logloss": round(_logloss(best_probs, y), 4),
        "ece": round(_ece(best_probs, y), 4),
        "roi": round(best_rule_metrics["roi"], 4),
        "clv": round(best_rule_metrics["clv"], 4),
        "n_bets": int(best_rule_metrics["n_bets"]),
        "win_rate": round(best_rule_metrics["win_rate"], 4),
        "confidence_cutoff": float(best_rule["confidence_cutoff"]),
        "threshold": float(best_rule["threshold"]),
        "fold_roi_std": round(
            _fold_rule_roi_std(
                strict["folds"],
                best_probs,
                y,
                market_probs,
                threshold=float(best_rule["threshold"]),
                confidence_cutoff=float(best_rule["confidence_cutoff"]),
            ),
            4,
        ),
    }

    research_raw = research["raw_probs"]
    research_y = research["y"]
    research_market = research["market_probs"]
    research_comparison = {
        "n_games": research["eval_games"],
        "brier": round(_brier(research_raw, research_y), 4) if research["eval_games"] else 1.0,
        "logloss": round(_logloss(research_raw, research_y), 4) if research["eval_games"] else 1.0,
        "roi": round(_compute_side_metrics(research_raw, research_y, research_market, threshold=0.03)["roi"], 4) if research["eval_games"] else 0.0,
        "clv": round(_compute_side_metrics(research_raw, research_y, research_market, threshold=0.03)["clv"], 4) if research["eval_games"] else 0.0,
        "fold_roi_std": round(
            _fold_rule_roi_std(
                research["folds"],
                research_raw,
                research_y,
                research_market,
                threshold=0.03,
                confidence_cutoff=0.0,
            ),
            4,
        )
        if research["eval_games"]
        else 0.0,
    }

    materially_improved = (
        (strict_optimized["roi"] > strict_baseline["roi"] + 0.03)
        or (strict_optimized["clv"] > strict_baseline["clv"] + 0.01)
    )
    if strict_optimized["roi"] > 0 and strict_optimized["clv"] > 0:
        diagnosis = "FIXED"
    elif strict_optimized["clv"] > 0:
        diagnosis = "STILL MODEL LIMITED"
    else:
        diagnosis = "NEED FEATURE EXPANSION"

    payload = {
        "tier": tier.value,
        "strict_eval_games": strict["eval_games"],
        "research_eval_games": research["eval_games"],
        "calibration_curve_raw": [row.as_dict() for row in _calibration_curve(raw_probs, y)],
        "calibration_curve_best": [row.as_dict() for row in _calibration_curve(best_probs, y)],
        "calibration_metrics_before_after": {
            "raw": calibration_metrics["raw"],
            "platt": calibration_metrics["platt"],
            "isotonic": calibration_metrics["isotonic"],
            "best_method": best_calibration_name,
        },
        "threshold_sweep": threshold_sweep,
        "ranking_optimization": ranking_results,
        "decision_rule_grid": rule_grid,
        "optimal_threshold": float(best_rule["threshold"]),
        "optimal_confidence_cutoff": float(best_rule["confidence_cutoff"]),
        "strict_baseline_metrics": strict_baseline,
        "strict_optimized_metrics": strict_optimized,
        "research_baseline_metrics": research_comparison,
        "folds": strict["folds"],
        "diagnosis": diagnosis,
    }
    out = Path(report_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload
