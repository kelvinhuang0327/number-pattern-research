"""
Walk-Forward Validation Framework (§ P1).

Simulates realistic temporal prediction workflow:
  - Train on games BEFORE the test window
  - Predict the test window
  - Slide forward, repeat

This avoids look-ahead bias (§ 核心規範 01) by ensuring the model
only sees data available at prediction time.

Usage:
    from examples.run_walkforward_backtest import run_walkforward
    run_walkforward()  # runs anchored expanding window by default
"""
from __future__ import annotations

import math
from typing import Callable, Dict, List, Tuple


def expanding_window_split(
    matches: List[Dict],
    min_train: int = 10,
    test_size: int = 5,
) -> List[Tuple[List[Dict], List[Dict]]]:
    """
    Anchored Expanding Window: train grows, test slides.

    Each fold:
      train = matches[0 : min_train + fold * test_size]
      test  = matches[train_end : train_end + test_size]

    Returns list of (train, test) tuples.
    """
    sorted_matches = sorted(matches, key=lambda m: m["date"])
    n = len(sorted_matches)
    folds = []
    train_end = min_train

    while train_end + test_size <= n:
        train = sorted_matches[:train_end]
        test = sorted_matches[train_end : train_end + test_size]
        folds.append((train, test))
        train_end += test_size

    # Remaining matches
    if train_end < n:
        train = sorted_matches[:train_end]
        test = sorted_matches[train_end:]
        if test:
            folds.append((train, test))

    return folds


def rolling_window_split(
    matches: List[Dict],
    train_size: int = 20,
    test_size: int = 5,
) -> List[Tuple[List[Dict], List[Dict]]]:
    """
    Rolling Window: fixed-size train window slides with test window.
    """
    sorted_matches = sorted(matches, key=lambda m: m["date"])
    n = len(sorted_matches)
    folds = []
    start = 0

    while start + train_size + test_size <= n:
        train = sorted_matches[start : start + train_size]
        test = sorted_matches[start + train_size : start + train_size + test_size]
        folds.append((train, test))
        start += test_size

    return folds


def walkforward_backtest(
    matches: List[Dict],
    predict_fn: Callable[[List[Dict], List[Dict]], List[Dict]],
    split_mode: str = "expanding",
    min_train: int = 10,
    train_size: int = 20,
    test_size: int = 5,
    verbose: bool = True,
) -> Dict:
    """
    Run walk-forward validation.

    Parameters
    ----------
    matches : list of match dicts (must contain 'date', 'actual_away_score', 'actual_home_score')
    predict_fn : callable(train_matches, test_matches) -> list of prediction dicts
        Each prediction dict: {"match_id", "predicted_winner", "confidence", ...}
    split_mode : "expanding" or "rolling"
    verbose : print per-fold stats

    Returns
    -------
    dict with overall and per-fold metrics
    """
    if split_mode == "expanding":
        folds = expanding_window_split(matches, min_train, test_size)
    else:
        folds = rolling_window_split(matches, train_size, test_size)

    fold_results = []
    total_correct = 0
    total_games = 0
    total_brier = 0.0
    total_log_loss = 0.0

    for i, (train, test) in enumerate(folds):
        predictions = predict_fn(train, test)

        fold_correct = 0
        fold_brier = 0.0
        fold_log_loss = 0.0

        for pred, actual in zip(predictions, test):
            actual_away = actual["actual_away_score"]
            actual_home = actual["actual_home_score"]
            actual_home_win = 1.0 if actual_home > actual_away else 0.0

            # Extract prediction probability for home win
            home_wp = pred.get("home_wp", 0.5)
            predicted_home_win = home_wp > 0.5

            if predicted_home_win == bool(actual_home_win):
                fold_correct += 1

            # Brier score
            fold_brier += (home_wp - actual_home_win) ** 2

            # Log loss (bounded)
            eps = 1e-6
            p = max(eps, min(1 - eps, home_wp))
            fold_log_loss += -(
                actual_home_win * math.log(p) +
                (1 - actual_home_win) * math.log(1 - p)
            )

        n_test = len(test)
        fold_win_rate = fold_correct / n_test if n_test else 0
        fold_avg_brier = fold_brier / n_test if n_test else 0
        fold_avg_ll = fold_log_loss / n_test if n_test else 0

        fold_results.append({
            "fold": i + 1,
            "train_size": len(train),
            "test_size": n_test,
            "train_dates": f"{train[0]['date']}..{train[-1]['date']}",
            "test_dates": f"{test[0]['date']}..{test[-1]['date']}",
            "win_rate": round(fold_win_rate, 4),
            "avg_brier": round(fold_avg_brier, 6),
            "avg_log_loss": round(fold_avg_ll, 6),
        })

        total_correct += fold_correct
        total_games += n_test
        total_brier += fold_brier
        total_log_loss += fold_log_loss

        if verbose:
            print(
                f"  Fold {i+1}: train={len(train)}, test={n_test} | "
                f"WR={fold_win_rate:.1%} Brier={fold_avg_brier:.4f} "
                f"LL={fold_avg_ll:.4f} [{test[0]['date']}..{test[-1]['date']}]"
            )

    overall_win_rate = total_correct / total_games if total_games else 0
    overall_brier = total_brier / total_games if total_games else 0
    overall_log_loss = total_log_loss / total_games if total_games else 0

    summary = {
        "split_mode": split_mode,
        "n_folds": len(folds),
        "total_games": total_games,
        "overall_win_rate": round(overall_win_rate, 4),
        "overall_brier": round(overall_brier, 6),
        "overall_log_loss": round(overall_log_loss, 6),
        "folds": fold_results,
    }

    if verbose:
        print(f"\n=== Walk-Forward Summary ({split_mode}) ===")
        print(f"  Folds: {len(folds)}  |  Games: {total_games}")
        print(f"  Win Rate: {overall_win_rate:.1%}")
        print(f"  Avg Brier: {overall_brier:.4f}")
        print(f"  Avg Log Loss: {overall_log_loss:.4f}")

    return summary
