"""
Alpha Discovery Engine
=======================
Automated feature importance analysis and hidden market edge detection.

  1. Feature Importance Ranking — permutation importance + SHAP-like scores
  2. Hidden Market Bias Detection — systematic bookmaker inefficiencies
  3. Non-Linear Edge Discovery — interaction effects & polynomial features
  4. Alpha Signal Generation — actionable trading signals

This module continuously scans for new predictive features and market
inefficiencies, acting as a quantitative research assistant.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any


# ─── Data Structures ─────────────────────────────────────────────────────────

@dataclass
class AlphaSignal:
    """A discovered predictive edge (alpha)."""
    name: str
    category: str          # "FEATURE" | "MARKET_BIAS" | "INTERACTION" | "TIMING"
    strength: float        # 0-1 (normalised signal strength)
    direction: str         # "LONG_HOME" | "LONG_AWAY" | "OVER" | "UNDER"
    description: str
    sharpe_estimate: float  # estimated Sharpe ratio from this signal alone
    sample_size: int
    confidence: float      # 0-1
    actionable: bool       # whether it can be directly traded


@dataclass
class FeatureImportance:
    """Feature importance analysis result."""
    feature_name: str
    permutation_importance: float   # drop in accuracy when feature is shuffled
    correlation_with_target: float  # Pearson correlation
    redundancy_score: float         # max correlation with another feature
    noise_score: float              # estimated noise contribution
    recommendation: str             # "KEEP" | "REMOVE" | "INVESTIGATE"


@dataclass
class MarketInefficiency:
    """A discovered market pricing inefficiency."""
    market: str
    book: str
    pattern: str           # description of the pattern
    avg_edge: float        # average edge exploitable
    frequency: float       # how often this occurs (0-1)
    sample_size: int
    expected_roi: float
    is_persistent: bool    # has it persisted over time?
    description: str


@dataclass
class AlphaReport:
    """Complete alpha discovery report."""
    feature_importances: list[FeatureImportance] = field(default_factory=list)
    market_inefficiencies: list[MarketInefficiency] = field(default_factory=list)
    alpha_signals: list[AlphaSignal] = field(default_factory=list)
    features_to_add: list[str] = field(default_factory=list)
    features_to_remove: list[str] = field(default_factory=list)
    total_alpha_count: int = 0
    best_signal: AlphaSignal | None = None
    summary: str = ""


# ─── Constants ────────────────────────────────────────────────────────────────

NOISE_THRESHOLD = 0.005          # features below this importance → noise
REDUNDANCY_THRESHOLD = 0.85      # correlation > 0.85 → redundant pair
MIN_SIGNAL_STRENGTH = 0.02       # minimum alpha strength to report
MIN_SAMPLE_SIZE = 30             # minimum games to trust a signal


# ─── 1. Feature Importance Analysis ─────────────────────────────────────────

def analyze_feature_importance(
    feature_matrix: list[dict[str, float]],
    targets: list[int],
    feature_names: list[str] | None = None,
) -> list[FeatureImportance]:
    """
    Compute permutation-based feature importance without external ML libraries.

    For each feature:
      1. Compute baseline accuracy (logistic proxy)
      2. Shuffle that feature and re-evaluate
      3. Importance = accuracy_drop / baseline_accuracy
    """
    if not feature_matrix or not targets:
        return []

    if feature_names is None:
        feature_names = list(feature_matrix[0].keys()) if feature_matrix else []

    # Build matrix
    X = [[row.get(f, 0.0) for f in feature_names] for row in feature_matrix]

    # Baseline accuracy: simple logistic regression proxy
    baseline_acc = _logistic_accuracy(X, targets)

    results = []
    correlations = _feature_correlations(X, feature_names)

    for i, fname in enumerate(feature_names):
        # Shuffle feature i
        X_shuffled = [row[:] for row in X]
        col_vals = [r[i] for r in X_shuffled]
        random.shuffle(col_vals)
        for j, row in enumerate(X_shuffled):
            row[i] = col_vals[j]

        shuffled_acc = _logistic_accuracy(X_shuffled, targets)
        perm_imp = max(0, baseline_acc - shuffled_acc)

        # Correlation with target
        feat_vals = [r[i] for r in X]
        corr = _pearson(feat_vals, [float(t) for t in targets])

        # Redundancy: max correlation with other features
        max_corr = 0.0
        for other_name, corr_val in correlations.get(fname, {}).items():
            if other_name != fname:
                max_corr = max(max_corr, abs(corr_val))

        # Noise assessment
        noise = 1.0 - min(1.0, perm_imp / max(NOISE_THRESHOLD, 0.001))

        # Recommendation
        if perm_imp < NOISE_THRESHOLD and abs(corr) < 0.05:
            rec = "REMOVE"
        elif max_corr > REDUNDANCY_THRESHOLD:
            rec = "INVESTIGATE"
        else:
            rec = "KEEP"

        results.append(FeatureImportance(
            feature_name=fname,
            permutation_importance=round(perm_imp, 5),
            correlation_with_target=round(corr, 4),
            redundancy_score=round(max_corr, 4),
            noise_score=round(noise, 4),
            recommendation=rec,
        ))

    return sorted(results, key=lambda x: -x.permutation_importance)


# ─── 2. Market Inefficiency Detection ───────────────────────────────────────

def detect_market_inefficiencies(  # noqa: C901
    backtest_results: list[dict[str, Any]],
) -> list[MarketInefficiency]:
    """
    Scan backtest results for systematic market inefficiencies.

    Looks for patterns where certain conditions consistently produce
    positive expected value bets.
    """
    inefficiencies: list[MarketInefficiency] = []

    # Pattern 1: Odds band inefficiency
    bands = {
        "1.50-1.80": {"wins": 0, "bets": 0, "pnl": 0.0},
        "1.81-2.10": {"wins": 0, "bets": 0, "pnl": 0.0},
        "2.11-2.60": {"wins": 0, "bets": 0, "pnl": 0.0},
        "2.61-3.50": {"wins": 0, "bets": 0, "pnl": 0.0},
        "3.51+":     {"wins": 0, "bets": 0, "pnl": 0.0},
    }

    for res in backtest_results:
        odds = res.get("odds", 2.0)
        won = res.get("won", False)
        stake = res.get("stake", 1.0)
        pnl = stake * (odds - 1) if won else -stake

        band = _classify_odds_band(odds)
        bands[band]["bets"] += 1
        bands[band]["pnl"] += pnl
        if won:
            bands[band]["wins"] += 1

    for band_name, stats in bands.items():
        if stats["bets"] < MIN_SAMPLE_SIZE:
            continue
        roi = stats["pnl"] / max(stats["bets"], 1)
        win_rate = stats["wins"] / stats["bets"]
        if roi > 0.01:  # >1% ROI
            inefficiencies.append(MarketInefficiency(
                market="ML",
                book="aggregate",
                pattern=f"Positive ROI in odds band {band_name}",
                avg_edge=roi,
                frequency=stats["bets"] / max(len(backtest_results), 1),
                sample_size=stats["bets"],
                expected_roi=roi,
                is_persistent=stats["bets"] >= 100,
                description=f"Odds {band_name}: {stats['bets']} bets, "
                            f"WR {win_rate:.1%}, ROI {roi:.1%}",
            ))

    # Pattern 2: Day-of-week effect
    dow_stats: dict[str, dict[str, Any]] = {}
    for res in backtest_results:
        dow = res.get("day_of_week", "unknown")
        if dow not in dow_stats:
            dow_stats[dow] = {"wins": 0, "bets": 0, "pnl": 0.0}
        dow_stats[dow]["bets"] += 1
        if res.get("won", False):
            dow_stats[dow]["wins"] += 1
        stake = res.get("stake", 1.0)
        dow_stats[dow]["pnl"] += stake * (res.get("odds", 2.0) - 1) if res.get("won") else -stake

    for dow, stats in dow_stats.items():
        if stats["bets"] < MIN_SAMPLE_SIZE // 2:
            continue
        roi = stats["pnl"] / max(stats["bets"], 1)
        if abs(roi) > 0.02:
            inefficiencies.append(MarketInefficiency(
                market="ML",
                book="aggregate",
                pattern=f"Day-of-week effect: {dow}",
                avg_edge=roi,
                frequency=stats["bets"] / max(len(backtest_results), 1),
                sample_size=stats["bets"],
                expected_roi=roi,
                is_persistent=False,
                description=f"{dow}: ROI {roi:.1%} ({stats['bets']} bets)",
            ))

    # Pattern 3: Home/away asymmetry
    side_stats = {"home": {"wins": 0, "bets": 0, "pnl": 0.0},
                  "away": {"wins": 0, "bets": 0, "pnl": 0.0}}
    for res in backtest_results:
        side = res.get("bet_side", "home")
        if side not in side_stats:
            continue
        side_stats[side]["bets"] += 1
        if res.get("won", False):
            side_stats[side]["wins"] += 1
        stake = res.get("stake", 1.0)
        side_stats[side]["pnl"] += stake * (res.get("odds", 2.0) - 1) if res.get("won") else -stake

    for side, stats in side_stats.items():
        if stats["bets"] < MIN_SAMPLE_SIZE:
            continue
        roi = stats["pnl"] / max(stats["bets"], 1)
        if abs(roi) > 0.01:
            inefficiencies.append(MarketInefficiency(
                market="ML",
                book="aggregate",
                pattern=f"Side bias: {side} bets",
                avg_edge=roi,
                frequency=stats["bets"] / max(len(backtest_results), 1),
                sample_size=stats["bets"],
                expected_roi=roi,
                is_persistent=stats["bets"] >= 200,
                description=f"{side}: ROI {roi:.1%} ({stats['bets']} bets, "
                            f"WR {stats['wins']/stats['bets']:.1%})",
            ))

    return sorted(inefficiencies, key=lambda x: -abs(x.avg_edge))


# ─── 3. Non-Linear Edge Discovery ───────────────────────────────────────────

def discover_interaction_effects(
    feature_matrix: list[dict[str, float]],
    targets: list[int],
    top_k: int = 5,
) -> list[AlphaSignal]:
    """
    Search for interaction effects (feature pairs) that have predictive power
    beyond individual features.

    Tests: f_i × f_j as new features and evaluates information gain.
    """
    if not feature_matrix or not targets:
        return []

    feature_names = list(feature_matrix[0].keys())
    n = len(feature_names)
    interactions: list[tuple[str, str, float]] = []

    for i in range(min(n, 15)):  # limit search space
        for j in range(i + 1, min(n, 15)):
            fi = feature_names[i]
            fj = feature_names[j]

            # Create interaction feature
            interaction = [
                feature_matrix[k].get(fi, 0) * feature_matrix[k].get(fj, 0)
                for k in range(len(feature_matrix))
            ]

            # Correlation with target
            corr = abs(_pearson(interaction, [float(t) for t in targets]))

            # Also check individual correlations
            corr_i = abs(_pearson(
                [row.get(fi, 0) for row in feature_matrix],
                [float(t) for t in targets]
            ))
            corr_j = abs(_pearson(
                [row.get(fj, 0) for row in feature_matrix],
                [float(t) for t in targets]
            ))

            # Information gain: interaction should be more predictive than individuals
            gain = corr - max(corr_i, corr_j)
            if gain > 0.01:
                interactions.append((fi, fj, gain))

    interactions.sort(key=lambda x: -x[2])

    signals = []
    for fi, fj, gain in interactions[:top_k]:
        signals.append(AlphaSignal(
            name=f"{fi}×{fj}",
            category="INTERACTION",
            strength=min(1.0, gain * 10),
            direction="LONG_HOME",  # direction depends on sign
            description=f"Interaction {fi}×{fj}: info gain +{gain:.4f} "
                        f"over individual features",
            sharpe_estimate=gain * 5,  # rough estimate
            sample_size=len(targets),
            confidence=min(0.9, len(targets) / 200),
            actionable=gain > 0.03,
        ))

    return signals


# ─── 4. Alpha Signal Aggregation ────────────────────────────────────────────

def generate_alpha_signals(
    feature_importances: list[FeatureImportance],
    market_inefficiencies: list[MarketInefficiency],
    interaction_signals: list[AlphaSignal],
) -> list[AlphaSignal]:
    """
    Aggregate all discovered alpha sources into actionable signals.
    """
    signals: list[AlphaSignal] = list(interaction_signals)

    # Feature-based signals
    for fi in feature_importances:
        if fi.permutation_importance > 0.01 and fi.recommendation == "KEEP":
            signals.append(AlphaSignal(
                name=f"feature:{fi.feature_name}",
                category="FEATURE",
                strength=min(1.0, fi.permutation_importance * 20),
                direction="LONG_HOME" if fi.correlation_with_target > 0 else "LONG_AWAY",
                description=f"{fi.feature_name}: perm_imp={fi.permutation_importance:.4f}, "
                            f"corr={fi.correlation_with_target:.3f}",
                sharpe_estimate=fi.permutation_importance * 10,
                sample_size=0,  # unknown
                confidence=0.7 if fi.noise_score < 0.5 else 0.4,
                actionable=True,
            ))

    # Market inefficiency signals
    for mi in market_inefficiencies:
        if mi.expected_roi > 0.01 and mi.sample_size >= MIN_SAMPLE_SIZE:
            signals.append(AlphaSignal(
                name=f"market:{mi.pattern}",
                category="MARKET_BIAS",
                strength=min(1.0, mi.avg_edge * 10),
                direction="LONG_HOME",  # simplified
                description=mi.description,
                sharpe_estimate=mi.expected_roi * 5,
                sample_size=mi.sample_size,
                confidence=0.6 if mi.is_persistent else 0.3,
                actionable=mi.is_persistent,
            ))

    return sorted(signals, key=lambda s: (-s.confidence * s.strength))


# ─── 5. Full Alpha Discovery Pipeline ───────────────────────────────────────

def run_alpha_discovery(
    feature_matrix: list[dict[str, float]],
    targets: list[int],
    backtest_results: list[dict[str, Any]] | None = None,
) -> AlphaReport:
    """
    Run the complete alpha discovery pipeline.

    Parameters
    ----------
    feature_matrix : list of feature dictionaries (one per game)
    targets : binary outcomes (1=home_win, 0=away_win)
    backtest_results : optional backtest output for market inefficiency analysis

    Returns
    -------
    AlphaReport with all discoveries
    """
    # 1. Feature importance
    importances = analyze_feature_importance(feature_matrix, targets)

    # 2. Market inefficiencies
    inefficiencies = detect_market_inefficiencies(backtest_results or [])

    # 3. Interaction effects
    interactions = discover_interaction_effects(feature_matrix, targets)

    # 4. Aggregate signals
    all_signals = generate_alpha_signals(importances, inefficiencies, interactions)

    # 5. Feature recommendations
    to_remove = [fi.feature_name for fi in importances if fi.recommendation == "REMOVE"]
    to_add = [s.name.replace("×", "_x_") for s in interactions if s.actionable]

    # 6. Summary
    actionable = [s for s in all_signals if s.actionable]
    best = all_signals[0] if all_signals else None

    parts = [
        f"Features: {len(importances)} analyzed, {len(to_remove)} to remove, {len(to_add)} to add",
        f"Market inefficiencies: {len(inefficiencies)}",
        f"Actionable signals: {len(actionable)}",
    ]
    if best:
        parts.append(f"Best: {best.name} (str={best.strength:.2f}, conf={best.confidence:.2f})")

    return AlphaReport(
        feature_importances=importances,
        market_inefficiencies=inefficiencies,
        alpha_signals=all_signals,
        features_to_add=to_add,
        features_to_remove=to_remove,
        total_alpha_count=len(all_signals),
        best_signal=best,
        summary=" | ".join(parts),
    )


# ─── Internal Helpers ────────────────────────────────────────────────────────

def _logistic_accuracy(X: list[list[float]], y: list[int]) -> float:
    """
    Quick logistic regression accuracy estimate (no scipy dependency).
    Uses a simple dot-product with uniform weights + bias.
    """
    if not X or not y:
        return 0.5

    n_features = len(X[0])
    # Simple: predict based on mean of positive features
    correct = 0
    for i, row in enumerate(X):
        score = sum(row) / max(n_features, 1)
        pred = 1 if score > 0 else 0
        if pred == y[i]:
            correct += 1

    return correct / max(len(y), 1)


def _pearson(x: list[float], y: list[float]) -> float:
    """Pearson correlation coefficient."""
    n = min(len(x), len(y))
    if n < 3:
        return 0.0

    mx = sum(x[:n]) / n
    my = sum(y[:n]) / n

    cov = sum((x[i] - mx) * (y[i] - my) for i in range(n))
    sx = math.sqrt(max(sum((x[i] - mx) ** 2 for i in range(n)), 1e-12))
    sy = math.sqrt(max(sum((y[i] - my) ** 2 for i in range(n)), 1e-12))

    return cov / (sx * sy)


def _feature_correlations(
    X: list[list[float]],
    names: list[str],
) -> dict[str, dict[str, float]]:
    """Compute pairwise feature correlations."""
    corrs: dict[str, dict[str, float]] = {n: {} for n in names}

    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            vals_i = [row[i] for row in X]
            vals_j = [row[j] for row in X]
            c = _pearson(vals_i, vals_j)
            corrs[names[i]][names[j]] = c
            corrs[names[j]][names[i]] = c

    return corrs


def _classify_odds_band(odds: float) -> str:
    """Classify decimal odds into band."""
    if odds <= 1.80:
        return "1.50-1.80"
    elif odds <= 2.10:
        return "1.81-2.10"
    elif odds <= 2.60:
        return "2.11-2.60"
    elif odds <= 3.50:
        return "2.61-3.50"
    else:
        return "3.51+"
