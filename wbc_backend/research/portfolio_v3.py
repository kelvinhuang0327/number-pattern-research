from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Iterable

import numpy as np


@dataclass(frozen=True)
class PortfolioOptimizationResult:
    weights: list[float]
    expected_return: float
    cvar_95: float
    gross_exposure: float
    stress_cvar: dict[str, float]


def _ensure_2d(arr: np.ndarray) -> np.ndarray:
    if arr.ndim == 1:
        return arr.reshape(-1, 1)
    return arr


def _psd_covariance(cov: np.ndarray, eps: float = 1e-8) -> np.ndarray:
    cov = (cov + cov.T) * 0.5
    eigvals, eigvecs = np.linalg.eigh(cov)
    eigvals = np.clip(eigvals, eps, None)
    return eigvecs @ np.diag(eigvals) @ eigvecs.T


def compute_portfolio_covariance(scenario_returns: Iterable[Iterable[float]]) -> np.ndarray:
    matrix = _ensure_2d(np.asarray(list(scenario_returns), dtype=float))
    if matrix.shape[0] < 2:
        return np.eye(matrix.shape[1], dtype=float) * 1e-6
    cov = np.cov(matrix.T)
    return _psd_covariance(np.asarray(cov, dtype=float))


def correlation_adjusted_kelly(
    expected_edges: Iterable[float],
    covariance: np.ndarray,
    leverage_cap: float = 0.20,
) -> np.ndarray:
    """
    Solve constrained Kelly proxy:
      w* ~ inv(Sigma) * mu
      then clip negatives and scale to leverage cap.
    """
    mu = np.asarray(list(expected_edges), dtype=float)
    if mu.size == 0:
        return np.array([], dtype=float)
    sigma = _psd_covariance(np.asarray(covariance, dtype=float))
    inv = np.linalg.pinv(sigma)
    raw = inv @ mu
    raw = np.where(raw > 0.0, raw, 0.0)
    gross = np.sum(np.abs(raw))
    if gross <= 1e-12:
        return np.zeros_like(raw)
    scaled = raw * (min(leverage_cap, gross) / gross)
    return scaled


def portfolio_cvar(losses: np.ndarray, alpha: float = 0.95) -> float:
    if losses.size == 0:
        return 0.0
    sorted_losses = np.sort(losses)
    idx = int(np.floor(alpha * (len(sorted_losses) - 1)))
    var_alpha = sorted_losses[idx]
    tail = sorted_losses[idx:]
    return float(np.mean(tail)) if tail.size else float(var_alpha)


def _evaluate_candidate(
    weights: np.ndarray,
    expected_edges: np.ndarray,
    scenario_returns: np.ndarray,
    alpha: float = 0.95,
) -> tuple[float, float]:
    exp_ret = float(np.dot(weights, expected_edges))
    scenario_pnl = scenario_returns @ weights
    losses = -scenario_pnl
    cvar = portfolio_cvar(losses, alpha=alpha)
    return exp_ret, cvar


def optimize_cvar_allocation(
    expected_edges: Iterable[float],
    scenario_returns: Iterable[Iterable[float]],
    max_gross_exposure: float = 0.20,
    lambda_cvar: float = 1.0,
) -> PortfolioOptimizationResult:
    edge_vec = np.asarray(list(expected_edges), dtype=float)
    scenarios = _ensure_2d(np.asarray(list(scenario_returns), dtype=float))
    if scenarios.shape[1] != edge_vec.shape[0]:
        raise ValueError("scenario_returns columns must equal expected_edges length")

    cov = compute_portfolio_covariance(scenarios)
    base = correlation_adjusted_kelly(edge_vec, cov, leverage_cap=max_gross_exposure)

    best_w = np.zeros_like(base)
    best_score = -1e18
    best_er = 0.0
    best_cvar = 0.0

    # Scale search controls risk appetite without nonlinear solver dependency.
    for scale in np.linspace(0.0, 1.0, 31):
        w = base * scale
        exp_ret, cvar = _evaluate_candidate(w, edge_vec, scenarios)
        score = exp_ret - lambda_cvar * cvar
        if score > best_score:
            best_score = score
            best_w = w
            best_er = exp_ret
            best_cvar = cvar

    stress = stress_scenario_simulation(best_w, scenarios)
    return PortfolioOptimizationResult(
        weights=[float(x) for x in best_w],
        expected_return=float(best_er),
        cvar_95=float(best_cvar),
        gross_exposure=float(np.sum(np.abs(best_w))),
        stress_cvar=stress,
    )


def drawdown_adaptive_sizing(drawdown_pct: float) -> float:
    if drawdown_pct >= 0.20:
        return 0.0
    if drawdown_pct >= 0.15:
        return 0.25
    if drawdown_pct >= 0.10:
        return 0.50
    if drawdown_pct >= 0.05:
        return 0.75
    return 1.0


def stress_scenario_simulation(
    weights: Iterable[float],
    scenario_returns: Iterable[Iterable[float]],
    shock_grid: tuple[float, ...] = (-0.01, -0.03, -0.05),
) -> dict[str, float]:
    w = np.asarray(list(weights), dtype=float)
    scenarios = _ensure_2d(np.asarray(list(scenario_returns), dtype=float))
    base_losses = -(scenarios @ w)
    stats: dict[str, float] = {"base_cvar_95": portfolio_cvar(base_losses, 0.95)}

    for shock in shock_grid:
        shocked = scenarios + shock
        shocked_losses = -(shocked @ w)
        key = f"shock_{int(abs(shock) * 1000)}bp_cvar95"
        stats[key] = portfolio_cvar(shocked_losses, 0.95)
    return stats


def bankroll_survival_probability(
    weights: Iterable[float],
    scenario_returns: Iterable[Iterable[float]],
    horizon_days: int = 120,
    ruin_threshold: float = 0.60,
    n_paths: int = 2000,
    seed: int = 42,
) -> float:
    rng = np.random.default_rng(seed)
    w = np.asarray(list(weights), dtype=float)
    scenarios = _ensure_2d(np.asarray(list(scenario_returns), dtype=float))
    pnl_dist = scenarios @ w
    if pnl_dist.size == 0:
        return 0.0

    survivors = 0
    for _ in range(n_paths):
        bankroll = 1.0
        alive = True
        for _ in range(horizon_days):
            r = float(rng.choice(pnl_dist))
            bankroll *= (1.0 + r)
            if bankroll <= ruin_threshold:
                alive = False
                break
        if alive:
            survivors += 1
    return survivors / n_paths
