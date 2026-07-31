"""
Alpha Feature Lab — Automated Feature Discovery for MLB Walk-Forward Backtest
==============================================================================

Generates pairwise interaction candidates from base features, ranks them via
out-of-fold permutation importance inside each walk-forward window, and prunes
features that fail a statistical significance gate.

Integration:
    from wbc_backend.intelligence.auto_feature_lab import AlphaFeatureLab
    lab = AlphaFeatureLab(base_features=FEATURE_COLUMNS)
    df  = lab.generate_candidates(df)                    # expand columns
    sel = lab.rank_and_select(X_train, y_train, X_val, y_val)  # OOF ranking
    # sel.survivors  → list of feature names to keep
"""
from __future__ import annotations

import itertools
import logging
from dataclasses import dataclass
from collections.abc import Sequence

import numpy as np
import pandas as pd
from scipy.special import expit

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Interaction operators
# ---------------------------------------------------------------------------
def _safe_ratio(a: np.ndarray, b: np.ndarray, eps: float = 0.1) -> np.ndarray:
    """a / (|b| + eps), avoids division by zero and extreme values."""
    return a / (np.abs(b) + eps)


_OPS = {
    "mul": lambda a, b: a * b,
    "ratio": _safe_ratio,
    "add": lambda a, b: a + b,
    "sub": lambda a, b: a - b,
}


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class FeatureImportance:
    name: str
    importance_mean: float
    importance_std: float
    is_base: bool


@dataclass
class SelectionResult:
    all_ranked: list[FeatureImportance]
    survivors: list[str]
    pruned: list[str]
    threshold_used: float


# ---------------------------------------------------------------------------
# Core lab
# ---------------------------------------------------------------------------
class AlphaFeatureLab:
    """
    Walk-forward-safe feature discovery engine.

    Parameters
    ----------
    base_features : list[str]
        The pregame feature column names (from FEATURE_COLUMNS).
    operators : list[str]
        Interaction operators to apply. Default: ["mul", "ratio"].
    max_candidates : int
        Hard cap on generated interaction candidates to avoid combinatorial
        explosion. Pairs are sorted by base-feature variance product (desc)
        and the top ``max_candidates`` are kept.
    """

    def __init__(
        self,
        base_features: Sequence[str],
        operators: Sequence[str] = ("mul", "ratio"),
        max_candidates: int = 60,
    ):
        self.base_features = list(base_features)
        self.operators = [op for op in operators if op in _OPS]
        self.max_candidates = max_candidates
        self._candidate_names: list[str] = []

    # ------------------------------------------------------------------
    # 1. Generate candidate interaction columns
    # ------------------------------------------------------------------
    def generate_candidates(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Create pairwise interaction features for every pair of *present*
        base features, up to ``max_candidates`` columns.

        Columns are named ``alpha_{op}_{feat_a}__{feat_b}``.
        Missing base features are silently skipped.
        """
        present = [f for f in self.base_features if f in df.columns]
        if len(present) < 2:
            logger.warning("[ALPHA LAB] <2 base features present; skipping generation")
            return df

        pairs = list(itertools.combinations(present, 2))

        # Rank pairs by variance product so we keep the most informative
        var = {}
        for f in present:
            v = df[f].var()
            var[f] = v if np.isfinite(v) and v > 0 else 1e-12

        pairs.sort(key=lambda ab: var[ab[0]] * var[ab[1]], reverse=True)

        out = df.copy()
        generated: list[str] = []

        for a, b in pairs:
            if len(generated) >= self.max_candidates:
                break
            for op_name in self.operators:
                if len(generated) >= self.max_candidates:
                    break
                col = f"alpha_{op_name}_{a}__{b}"
                vals = _OPS[op_name](df[a].to_numpy(dtype=float),
                                     df[b].to_numpy(dtype=float))
                vals = np.nan_to_num(vals, nan=0.0, posinf=0.0, neginf=0.0)
                out[col] = vals
                generated.append(col)

        self._candidate_names = generated
        logger.info(
            "[ALPHA LAB] Generated %d interaction candidates from %d base features",
            len(generated), len(present),
        )
        return out

    @property
    def candidate_names(self) -> list[str]:
        return list(self._candidate_names)

    # ------------------------------------------------------------------
    # 2. Rank via out-of-fold permutation importance
    # ------------------------------------------------------------------
    def rank_and_select(
        self,
        X_train: pd.DataFrame,
        y_train: np.ndarray,
        X_val: pd.DataFrame,
        y_val: np.ndarray,
        threshold: float = 0.0005,
        n_repeats: int = 5,
    ) -> SelectionResult:
        """
        Train a lightweight logistic model on ``X_train``, measure feature
        importance via permutation on ``X_val`` (out-of-fold), and keep only
        features whose mean importance exceeds ``threshold``.

        Uses a simple logistic regression (same spec as the walk-forward
        pipeline) so there's no heavy dependency.
        """
        features = list(X_train.columns)
        if len(features) == 0 or len(y_train) < 30:
            return SelectionResult([], features, [], threshold)

        # ---- fast logistic fit (L2-regularised, mirrors modeling.py) ----
        x_tr = X_train[features].to_numpy(dtype=float)
        x_tr = np.nan_to_num(x_tr, nan=0.0, posinf=0.0, neginf=0.0)
        x_mean = x_tr.mean(axis=0)
        x_std = np.where(x_tr.std(axis=0) < 1e-8, 1.0, x_tr.std(axis=0))
        z_tr = (x_tr - x_mean) / x_std
        z_tr = np.hstack([np.ones((len(z_tr), 1)), z_tr])

        from scipy.optimize import minimize as _minimize

        def _loss(w: np.ndarray) -> float:
            p = expit(z_tr @ w)
            p = np.clip(p, 1e-6, 1 - 1e-6)
            yt = np.asarray(y_train, dtype=float)
            ll = -(yt * np.log(p) + (1 - yt) * np.log(1 - p)).mean()
            return ll + 0.01 * np.sum(w[1:] ** 2)

        res = _minimize(_loss, np.zeros(z_tr.shape[1]), method="L-BFGS-B")
        w = res.x

        # ---- baseline log-loss on validation ----
        x_val = X_val[features].to_numpy(dtype=float)
        x_val = np.nan_to_num(x_val, nan=0.0, posinf=0.0, neginf=0.0)
        z_val = (x_val - x_mean) / x_std
        z_val = np.hstack([np.ones((len(z_val), 1)), z_val])
        y_v = np.asarray(y_val, dtype=float)

        def _logloss(z: np.ndarray) -> float:
            p = np.clip(expit(z @ w), 1e-6, 1 - 1e-6)
            return float(-(y_v * np.log(p) + (1 - y_v) * np.log(1 - p)).mean())

        baseline = _logloss(z_val)

        # ---- permutation importance (out-of-fold) ----
        rng = np.random.RandomState(42)
        importances: list[FeatureImportance] = []

        for j, fname in enumerate(features):
            deltas = []
            col_idx = j + 1  # +1 because column 0 is intercept
            for _ in range(n_repeats):
                z_perm = z_val.copy()
                rng.shuffle(z_perm[:, col_idx])
                perm_loss = _logloss(z_perm)
                deltas.append(perm_loss - baseline)  # positive = feature matters

            imp_mean = float(np.mean(deltas))
            imp_std = float(np.std(deltas))
            importances.append(FeatureImportance(
                name=fname,
                importance_mean=imp_mean,
                importance_std=imp_std,
                is_base=fname in self.base_features,
            ))

        importances.sort(key=lambda fi: fi.importance_mean, reverse=True)

        survivors = [fi.name for fi in importances if fi.importance_mean >= threshold]
        pruned = [fi.name for fi in importances if fi.importance_mean < threshold]

        # Always keep base features even if marginally below threshold
        for fi in importances:
            if fi.is_base and fi.name not in survivors:
                survivors.append(fi.name)
                if fi.name in pruned:
                    pruned.remove(fi.name)

        logger.info(
            "[ALPHA LAB] OOF ranking done: %d survivors, %d pruned (threshold=%.4f, baseline_ll=%.4f)",
            len(survivors), len(pruned), threshold, baseline,
        )
        return SelectionResult(
            all_ranked=importances,
            survivors=survivors,
            pruned=pruned,
            threshold_used=threshold,
        )

    # ------------------------------------------------------------------
    # 3. Feature stability across walk-forward windows
    # ------------------------------------------------------------------
    def compute_stability(
        self,
        window_results: list[SelectionResult],
    ) -> dict[str, float]:
        """
        Given a list of ``SelectionResult`` from consecutive walk-forward
        windows, return per-feature *survival rate* (fraction of windows
        in which the feature survived).  Features with rate < 0.5 are
        essentially noise.
        """
        if not window_results:
            return {}

        feature_counts: dict[str, int] = {}
        n_windows = len(window_results)

        for sr in window_results:
            for name in sr.survivors:
                feature_counts[name] = feature_counts.get(name, 0) + 1

        return {
            name: count / n_windows
            for name, count in sorted(feature_counts.items(),
                                       key=lambda kv: kv[1], reverse=True)
        }
