from __future__ import annotations

from dataclasses import dataclass, field
from collections.abc import Callable, Sequence

import numpy as np


def walk_forward_windows(
    n_samples: int,
    train_size: int,
    test_size: int,
    step_size: int,
) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    windows: list[tuple[tuple[int, int], tuple[int, int]]] = []
    start = 0
    while start + train_size + test_size <= n_samples:
        train = (start, start + train_size)
        test = (start + train_size, start + train_size + test_size)
        windows.append((train, test))
        start += step_size
    return windows


def cross_year_validation_splits(
    years: Sequence[int],
    min_train_years: int = 2,
) -> list[tuple[list[int], list[int]]]:
    uniq = sorted(set(years))
    if len(uniq) <= min_train_years:
        return []
    splits: list[tuple[list[int], list[int]]] = []
    for idx in range(min_train_years, len(uniq)):
        train = uniq[:idx]
        test = [uniq[idx]]
        splits.append((train, test))
    return splits


def monte_carlo_season_simulation(
    daily_returns: Sequence[float],
    horizon_days: int = 120,
    n_paths: int = 3000,
    seed: int = 42,
) -> dict[str, float]:
    rets = np.asarray(daily_returns, dtype=float)
    if rets.size == 0:
        raise ValueError("daily_returns cannot be empty")

    rng = np.random.default_rng(seed)
    ending = np.empty(n_paths, dtype=float)
    mdd = np.empty(n_paths, dtype=float)
    for i in range(n_paths):
        path = rng.choice(rets, size=horizon_days, replace=True)
        equity = np.cumprod(1.0 + path)
        peak = np.maximum.accumulate(equity)
        drawdown = (peak - equity) / np.maximum(peak, 1e-9)
        ending[i] = float(equity[-1])
        mdd[i] = float(np.max(drawdown))

    return {
        "median_ending_bankroll": float(np.median(ending)),
        "p05_ending_bankroll": float(np.quantile(ending, 0.05)),
        "p95_ending_bankroll": float(np.quantile(ending, 0.95)),
        "mean_max_drawdown": float(np.mean(mdd)),
    }


def hyperparameter_search_protocol(
    search_space: dict[str, tuple[float, float]],
    n_trials: int,
    seed: int = 42,
) -> list[dict[str, float]]:
    rng = np.random.default_rng(seed)
    trials: list[dict[str, float]] = []
    for _ in range(max(1, n_trials)):
        params = {}
        for k, (lo, hi) in search_space.items():
            if hi < lo:
                raise ValueError(f"invalid bounds for {k}: {lo}, {hi}")
            params[k] = float(rng.uniform(lo, hi))
        trials.append(params)
    return trials


def feature_ablation_testing(
    feature_names: Sequence[str],
    scorer: Callable[[Sequence[str]], float],
) -> dict[str, float]:
    baseline = scorer(feature_names)
    impacts: dict[str, float] = {"baseline": float(baseline)}
    for feat in feature_names:
        reduced = [f for f in feature_names if f != feat]
        score = scorer(reduced)
        impacts[feat] = float(baseline - score)
    return impacts


def edge_decay_analysis(edge_curve: Sequence[tuple[float, float]]) -> dict[str, float]:
    if not edge_curve:
        return {"half_life": 0.0, "initial_edge": 0.0, "terminal_edge": 0.0}
    ordered = sorted(edge_curve, key=lambda x: x[0])
    t = np.asarray([p[0] for p in ordered], dtype=float)
    e = np.asarray([p[1] for p in ordered], dtype=float)
    initial = float(e[0])
    target = initial * 0.5
    half_life = float(t[-1])
    for ti, ei in zip(t, e):
        if ei <= target:
            half_life = float(ti)
            break
    return {"half_life": half_life, "initial_edge": initial, "terminal_edge": float(e[-1])}


@dataclass
class CLVTracker:
    records: list[tuple[float, float, float]] = field(default_factory=list)

    def add(self, open_odds: float, close_odds: float, stake: float = 1.0) -> None:
        self.records.append((float(open_odds), float(close_odds), float(stake)))

    def summary(self) -> dict[str, float]:
        if not self.records:
            return {"mean_clv": 0.0, "positive_rate": 0.0, "count": 0.0}
        clvs = np.asarray(
            [((o / c) - 1.0) for o, c, _ in self.records if o > 0 and c > 0],
            dtype=float,
        )
        if clvs.size == 0:
            return {"mean_clv": 0.0, "positive_rate": 0.0, "count": 0.0}
        return {
            "mean_clv": float(np.mean(clvs)),
            "positive_rate": float(np.mean(clvs > 0)),
            "count": float(clvs.size),
        }


def calibration_monitoring(
    probabilities: Sequence[float],
    outcomes: Sequence[int],
    bins: int = 10,
) -> dict[str, float]:
    p = np.clip(np.asarray(probabilities, dtype=float), 1e-6, 1 - 1e-6)
    y = np.asarray(outcomes, dtype=float)
    if p.size != y.size:
        raise ValueError("probabilities and outcomes size mismatch")
    n = p.size
    if n == 0:
        raise ValueError("empty calibration input")

    brier = float(np.mean((p - y) ** 2))
    logloss = float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))

    edges = np.linspace(0, 1, bins + 1)
    ece = 0.0
    mce = 0.0
    for i in range(bins):
        lo, hi = edges[i], edges[i + 1]
        mask = (p >= lo) & (p < hi if i < bins - 1 else p <= hi)
        if not np.any(mask):
            continue
        acc = float(np.mean(y[mask]))
        conf = float(np.mean(p[mask]))
        gap = abs(acc - conf)
        ece += (np.sum(mask) / n) * gap
        mce = max(mce, gap)
    return {"brier": brier, "logloss": logloss, "ece": float(ece), "mce": float(mce)}


def population_stability_index(
    reference: Sequence[float],
    current: Sequence[float],
    bins: int = 10,
) -> float:
    ref = np.asarray(reference, dtype=float)
    cur = np.asarray(current, dtype=float)
    if ref.size == 0 or cur.size == 0:
        raise ValueError("reference and current must be non-empty")

    edges = np.quantile(ref, q=np.linspace(0, 1, bins + 1))
    edges[0] = -np.inf
    edges[-1] = np.inf

    ref_hist, _ = np.histogram(ref, bins=edges)
    cur_hist, _ = np.histogram(cur, bins=edges)
    ref_pct = np.clip(ref_hist / max(1, ref_hist.sum()), 1e-6, 1.0)
    cur_pct = np.clip(cur_hist / max(1, cur_hist.sum()), 1e-6, 1.0)
    psi = np.sum((cur_pct - ref_pct) * np.log(cur_pct / ref_pct))
    return float(psi)


def _ks_statistic(reference: np.ndarray, current: np.ndarray) -> float:
    values = np.sort(np.unique(np.concatenate([reference, current])))
    if values.size == 0:
        return 0.0
    ref_sorted = np.sort(reference)
    cur_sorted = np.sort(current)
    ref_cdf = np.searchsorted(ref_sorted, values, side="right") / max(1, ref_sorted.size)
    cur_cdf = np.searchsorted(cur_sorted, values, side="right") / max(1, cur_sorted.size)
    return float(np.max(np.abs(ref_cdf - cur_cdf)))


def drift_detection(
    reference: Sequence[float],
    current: Sequence[float],
    psi_threshold: float = 0.20,
    ks_threshold: float = 0.10,
) -> dict[str, float]:
    ref = np.asarray(reference, dtype=float)
    cur = np.asarray(current, dtype=float)
    psi = population_stability_index(ref, cur)
    ks = _ks_statistic(ref, cur)
    drift_flag = 1.0 if (psi >= psi_threshold or ks >= ks_threshold) else 0.0
    return {"psi": psi, "ks": ks, "drift_flag": drift_flag}
