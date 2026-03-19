#!/usr/bin/env python3
"""
M1 PoC: Regime Detector
=======================
Detect latent performance regimes from recent hit series.
Primary model: 2-state Gaussian HMM (if hmmlearn available)
Fallback: 2-cluster KMeans on rolling features
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from typing import Dict, List

import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "lottery_api"))

from database import DatabaseManager  # noqa: E402
from engine.rolling_strategy_monitor import BASELINES, METRIC_KEY  # noqa: E402
from engine.strategy_coordinator import coordinator_predict  # noqa: E402


def _metric_hit(bets: List[List[int]], actual: List[int], metric: str) -> int:
    s = set(actual)
    m = max(len(set(b) & s) for b in bets) if bets else 0
    return 1 if (m >= 2 if metric == "is_m2plus" else m >= 3) else 0


def _build_hit_series(history: List[dict], lottery: str, n_bets: int, min_train: int, train_window: int) -> List[int]:
    metric = METRIC_KEY[lottery]
    hits = []
    for i in range(min_train, len(history)):
        train = history[max(0, i - train_window):i]
        actual = history[i]["numbers"]
        try:
            bets, _ = coordinator_predict(lottery, train, n_bets=n_bets, mode="hybrid")
            h = _metric_hit(bets, actual, metric)
        except Exception:
            h = 0
        hits.append(h)
    return hits


def _rolling_features(hits: List[int], baseline: float, w: int = 30) -> np.ndarray:
    X = []
    for i in range(w, len(hits)):
        x = np.array(hits[i - w:i], dtype=float)
        rate = x.mean()
        edge = rate - baseline
        vol = x.std()
        accel = x[-10:].mean() - x[:10].mean()
        X.append([rate, edge, vol, accel])
    return np.asarray(X, dtype=float)


def _fit_regime(X: np.ndarray) -> Dict:
    if len(X) < 30:
        return {"method": "none", "regimes": [], "current_regime": -1, "transition": []}
    try:
        from hmmlearn.hmm import GaussianHMM  # type: ignore

        model = GaussianHMM(n_components=2, covariance_type="diag", n_iter=200, random_state=42)
        model.fit(X)
        z = model.predict(X)
        trans = model.transmat_.tolist()
        means = model.means_.tolist()
        return {
            "method": "hmmlearn.GaussianHMM",
            "regimes": z.tolist(),
            "current_regime": int(z[-1]),
            "transition": trans,
            "means": means,
        }
    except Exception:
        from sklearn.cluster import KMeans  # type: ignore

        km = KMeans(n_clusters=2, random_state=42, n_init=20)
        z = km.fit_predict(X)
        centers = km.cluster_centers_.tolist()
        return {
            "method": "fallback.KMeans",
            "regimes": z.tolist(),
            "current_regime": int(z[-1]),
            "transition": [],
            "means": centers,
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lottery", choices=["BIG_LOTTO", "POWER_LOTTO", "DAILY_539"], default="BIG_LOTTO")
    parser.add_argument("--bets", type=int, default=2)
    parser.add_argument("--min-train", type=int, default=300)
    parser.add_argument("--train-window", type=int, default=500)
    parser.add_argument("--db-path", default=os.path.join(PROJECT_ROOT, "lottery_api", "data", "lottery_v2.db"))
    parser.add_argument("--out-json", default=os.path.join(PROJECT_ROOT, "research", "m1_regime_detector_poc.json"))
    args = parser.parse_args()

    db = DatabaseManager(db_path=args.db_path)
    history = sorted(db.get_all_draws(args.lottery), key=lambda x: (x["date"], x["draw"]))
    baseline = BASELINES[args.lottery][args.bets]

    hits = _build_hit_series(history, args.lottery, args.bets, args.min_train, args.train_window)
    X = _rolling_features(hits, baseline=baseline, w=30)
    regime = _fit_regime(X)

    out = {
        "generated_at": datetime.now().isoformat(),
        "lottery_type": args.lottery,
        "num_bets": args.bets,
        "baseline": baseline,
        "n_hits": len(hits),
        "n_features": int(len(X)),
        "regime_result": regime,
    }
    os.makedirs(os.path.dirname(args.out_json), exist_ok=True)
    with open(args.out_json, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"method={regime['method']} current_regime={regime['current_regime']} n_features={len(X)}")
    print(f"saved: {args.out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
