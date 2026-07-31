"""
Phase 41: Metrics SSOT for MLB Evaluation
==========================================
Single source of truth for all MLB prediction evaluation metrics.

Functions:
  Odds conversion:
    american_odds_to_implied_prob(odds) -> float
    normalize_no_vig(home_prob, away_prob) -> tuple[float, float]
    american_moneyline_pair_to_no_vig(home_ml, away_ml) -> dict

  Core metrics:
    brier_score(probs, labels) -> float
    brier_skill_score(model_brier, baseline_brier) -> float | None
    log_loss_score(probs, labels, eps=1e-15) -> float
    expected_calibration_error(probs, labels, n_bins=10) -> dict

  Reliability:
    reliability_bins(probs, labels, n_bins=10) -> list[dict]
    calibration_summary(probs, labels, n_bins=10) -> dict

  Comparison:
    compare_model_to_market(model_probs, market_probs, labels) -> dict

Hard rules:
  - No external API or LLM calls.
  - No modification to prediction values.
  - Probabilities clipped only in log_loss, not in Brier/ECE.
  - Invalid probabilities raise ValueError for Brier/ECE.
  - Pure deterministic computation.
"""
from __future__ import annotations

import math
from typing import Union

__all__ = [
    "american_odds_to_implied_prob",
    "normalize_no_vig",
    "american_moneyline_pair_to_no_vig",
    "brier_score",
    "brier_skill_score",
    "log_loss_score",
    "expected_calibration_error",
    "reliability_bins",
    "calibration_summary",
    "compare_model_to_market",
]

# ─────────────────────────────────────────────────────────────────────────────
# § 1  Odds Conversion
# ─────────────────────────────────────────────────────────────────────────────

def american_odds_to_implied_prob(
    odds: Union[str, int, float],
    *,
    safe: bool = False,
) -> float:
    """
    Convert American moneyline odds to raw (vig-inclusive) implied probability.

    Accepts strings like '+120', '-150', '120', '-150', or numeric values.

    Parameters
    ----------
    odds : str | int | float
        American odds value.
    safe : bool
        If True, returns 0.5 on parse error instead of raising ValueError.

    Returns
    -------
    float
        Implied probability in (0, 1).

    Raises
    ------
    ValueError
        If odds cannot be parsed and safe=False, or if odds == 0.

    Examples
    --------
    >>> american_odds_to_implied_prob('+100')
    0.5
    >>> american_odds_to_implied_prob('-150')
    0.6
    >>> american_odds_to_implied_prob('+120')
    0.45454545454545453
    """
    try:
        ml_str = str(odds).strip().replace(" ", "")
        if not ml_str or ml_str.lower() in ("nan", "none", "n/a", ""):
            if safe:
                return 0.5
            raise ValueError(f"Cannot parse odds: {odds!r}")

        ml = float(ml_str)
    except (ValueError, TypeError):
        if safe:
            return 0.5
        raise ValueError(f"Cannot parse American odds: {odds!r}")

    if ml == 0:
        if safe:
            return 0.5
        raise ValueError(f"American odds value 0 is invalid: {odds!r}")

    if ml > 0:
        return 100.0 / (ml + 100.0)
    else:
        return abs(ml) / (abs(ml) + 100.0)


def normalize_no_vig(
    home_prob: float,
    away_prob: float,
) -> tuple[float, float]:
    """
    Proportional (Pinnacle-style) no-vig normalization.

    Divides each implied probability by the sum of both, so that
    the resulting pair sums to exactly 1.0.

    Parameters
    ----------
    home_prob : float
        Raw implied probability for home team (vig-inclusive).
    away_prob : float
        Raw implied probability for away team (vig-inclusive).

    Returns
    -------
    tuple[float, float]
        (home_no_vig, away_no_vig) summing to 1.0.

    Raises
    ------
    ValueError
        If total <= 0.

    Examples
    --------
    >>> h, a = normalize_no_vig(0.6, 0.55)
    >>> round(h + a, 10)
    1.0
    """
    total = home_prob + away_prob
    if total <= 0:
        raise ValueError(
            f"normalize_no_vig: total probability = {total} <= 0. "
            f"home_prob={home_prob}, away_prob={away_prob}"
        )
    return home_prob / total, away_prob / total


def american_moneyline_pair_to_no_vig(
    home_ml: Union[str, int, float],
    away_ml: Union[str, int, float],
    *,
    safe: bool = False,
) -> dict:
    """
    Convert a moneyline pair (home + away) to no-vig probabilities.

    Parameters
    ----------
    home_ml : str | int | float
        Home team American odds.
    away_ml : str | int | float
        Away team American odds.
    safe : bool
        If True, individual parse failures default to 0.5 before normalization.

    Returns
    -------
    dict with keys:
        home_raw, away_raw        – raw implied probabilities
        home_no_vig, away_no_vig  – normalized (sum = 1.0)
        vig                       – overround = home_raw + away_raw - 1.0
        ok                        – True if both parsed successfully

    Examples
    --------
    >>> r = american_moneyline_pair_to_no_vig('+100', '+100')
    >>> r['home_no_vig'], r['away_no_vig']
    (0.5, 0.5)
    """
    home_raw = american_odds_to_implied_prob(home_ml, safe=safe)
    away_raw = american_odds_to_implied_prob(away_ml, safe=safe)

    total = home_raw + away_raw
    if total <= 0:
        home_nv, away_nv = 0.5, 0.5
        ok = False
    else:
        home_nv = home_raw / total
        away_nv = away_raw / total
        ok = True

    return {
        "home_raw": home_raw,
        "away_raw": away_raw,
        "home_no_vig": home_nv,
        "away_no_vig": away_nv,
        "vig": round(home_raw + away_raw - 1.0, 8),
        "ok": ok,
    }


# ─────────────────────────────────────────────────────────────────────────────
# § 2  Internal validation helpers
# ─────────────────────────────────────────────────────────────────────────────

def _validate_probs_labels(
    probs: list[float],
    labels: list[float],
    context: str = "metric",
    strict_prob_range: bool = True,
) -> None:
    """Shared validation for probability lists and binary label lists."""
    if not probs:
        raise ValueError(f"{context}: probs list is empty.")
    if not labels:
        raise ValueError(f"{context}: labels list is empty.")
    if len(probs) != len(labels):
        raise ValueError(
            f"{context}: probs length {len(probs)} != labels length {len(labels)}."
        )
    if strict_prob_range:
        for i, p in enumerate(probs):
            if not (0.0 <= p <= 1.0):
                raise ValueError(
                    f"{context}: probability at index {i} = {p} is outside [0, 1]."
                )


# ─────────────────────────────────────────────────────────────────────────────
# § 3  Core Metrics
# ─────────────────────────────────────────────────────────────────────────────

def brier_score(
    probs: list[float],
    labels: list[float],
) -> float:
    """
    Mean Brier Score = mean((prob - label)²).

    Probabilities outside [0, 1] raise ValueError (not clipped).
    Labels should be 0 or 1 but are not strictly enforced.

    Parameters
    ----------
    probs : list[float]
        Predicted probabilities for the positive class.
    labels : list[float]
        Observed binary outcomes (0 or 1).

    Returns
    -------
    float
        Brier score in [0, 1].

    Raises
    ------
    ValueError
        If any probability is outside [0, 1], or lists have different lengths.

    Examples
    --------
    >>> brier_score([0.9, 0.8], [1, 1])
    0.025
    >>> brier_score([0.5], [0])
    0.25
    """
    _validate_probs_labels(probs, labels, context="brier_score", strict_prob_range=True)
    n = len(probs)
    return sum((p - y) ** 2 for p, y in zip(probs, labels)) / n


def brier_skill_score(
    model_brier: float,
    baseline_brier: float,
) -> float | None:
    """
    Brier Skill Score = 1 - model_brier / baseline_brier.

    Returns None (not NaN, not crash) when baseline_brier = 0.

    Parameters
    ----------
    model_brier : float
        Brier score of the model.
    baseline_brier : float
        Brier score of the reference baseline (e.g., market, coin flip).

    Returns
    -------
    float | None
        BSS value; None if baseline_brier == 0.

    Examples
    --------
    >>> brier_skill_score(0.2796, 0.2451)  # doctest: +ELLIPSIS
    -0.140...
    >>> brier_skill_score(0.2, 0.2) is not None
    True
    >>> brier_skill_score(0.2, 0.0) is None
    True
    """
    if baseline_brier == 0:
        return None
    return 1.0 - model_brier / baseline_brier


def log_loss_score(
    probs: list[float],
    labels: list[float],
    eps: float = 1e-15,
) -> float:
    """
    Binary cross-entropy / log loss.

    Probabilities are clipped to [eps, 1 - eps] before log computation
    to avoid -inf. This clipping is deliberate and only applies here.

    Parameters
    ----------
    probs : list[float]
        Predicted probabilities for the positive class.
    labels : list[float]
        Observed binary outcomes (0 or 1).
    eps : float
        Clipping epsilon for numerical stability.

    Returns
    -------
    float
        Log loss (non-negative; lower = better).

    Raises
    ------
    ValueError
        If lists are empty or have different lengths.

    Examples
    --------
    >>> round(log_loss_score([1.0], [1]), 10)  # exact 1 → clipped
    0.0
    """
    _validate_probs_labels(
        probs, labels, context="log_loss_score", strict_prob_range=False
    )
    n = len(probs)
    total = 0.0
    for p, y in zip(probs, labels):
        p_clipped = max(eps, min(1.0 - eps, p))
        total += y * math.log(p_clipped) + (1.0 - y) * math.log(1.0 - p_clipped)
    return -total / n


def expected_calibration_error(
    probs: list[float],
    labels: list[float],
    n_bins: int = 10,
) -> dict:
    """
    Expected Calibration Error using equal-width bins over [0, 1].

    ECE = Σ_b (|b| / N) * |mean_confidence(b) - mean_accuracy(b)|

    Parameters
    ----------
    probs : list[float]
        Predicted probabilities for the positive class. Must be in [0, 1].
    labels : list[float]
        Observed binary outcomes (0 or 1).
    n_bins : int
        Number of equal-width bins. Default 10.

    Returns
    -------
    dict with keys:
        ece           – scalar ECE value
        n_bins        – number of bins used
        sample_size   – total number of predictions
        bins          – list of per-bin dicts (see reliability_bins)

    Raises
    ------
    ValueError
        If any probability is outside [0, 1], or lists have different lengths.

    Examples
    --------
    >>> r = expected_calibration_error([0.5, 0.5], [0, 1])
    >>> r['ece']
    0.0
    """
    _validate_probs_labels(
        probs, labels, context="expected_calibration_error", strict_prob_range=True
    )
    bins = reliability_bins(probs, labels, n_bins=n_bins)
    n = len(probs)
    ece = sum(
        (b["count"] / n) * b["gap"]
        for b in bins
        if b["count"] > 0
    )
    return {
        "ece": round(ece, 8),
        "n_bins": n_bins,
        "sample_size": n,
        "bins": bins,
    }


# ─────────────────────────────────────────────────────────────────────────────
# § 4  Reliability
# ─────────────────────────────────────────────────────────────────────────────

def reliability_bins(
    probs: list[float],
    labels: list[float],
    n_bins: int = 10,
) -> list[dict]:
    """
    Compute per-bin reliability statistics for a reliability diagram.

    Parameters
    ----------
    probs : list[float]
        Predicted probabilities in [0, 1].
    labels : list[float]
        Observed binary outcomes.
    n_bins : int
        Number of equal-width bins.

    Returns
    -------
    list[dict]
        One dict per bin with keys:
            bin_lower      – lower edge of bin
            bin_upper      – upper edge of bin
            count          – number of predictions in bin
            mean_confidence – mean predicted probability in bin
            mean_accuracy   – fraction of positives in bin
            gap             – |mean_confidence - mean_accuracy|

    Raises
    ------
    ValueError
        If probabilities are outside [0, 1].
    """
    _validate_probs_labels(
        probs, labels, context="reliability_bins", strict_prob_range=True
    )
    result = []
    for i in range(n_bins):
        lo = i / n_bins
        hi = (i + 1) / n_bins
        # Include right edge in the last bin
        bin_items = [
            (p, y) for p, y in zip(probs, labels)
            if (lo <= p < hi) or (i == n_bins - 1 and p == 1.0)
        ]
        if bin_items:
            mean_conf = sum(x[0] for x in bin_items) / len(bin_items)
            mean_acc = sum(x[1] for x in bin_items) / len(bin_items)
            gap = abs(mean_conf - mean_acc)
        else:
            mean_conf = (lo + hi) / 2.0
            mean_acc = 0.0
            gap = 0.0
        result.append(
            {
                "bin_lower": round(lo, 4),
                "bin_upper": round(hi, 4),
                "count": len(bin_items),
                "mean_confidence": round(mean_conf, 6),
                "mean_accuracy": round(mean_acc, 6),
                "gap": round(gap, 6),
            }
        )
    return result


def calibration_summary(
    probs: list[float],
    labels: list[float],
    n_bins: int = 10,
) -> dict:
    """
    Full calibration summary combining ECE, log loss, and reliability bins.

    Parameters
    ----------
    probs : list[float]
        Predicted probabilities in [0, 1].
    labels : list[float]
        Observed binary outcomes.
    n_bins : int
        Number of ECE bins.

    Returns
    -------
    dict with keys:
        brier         – Brier score
        log_loss      – binary cross-entropy
        ece           – Expected Calibration Error
        sample_size   – N
        bins          – reliability bins (list[dict])
    """
    _validate_probs_labels(
        probs, labels, context="calibration_summary", strict_prob_range=True
    )
    ece_result = expected_calibration_error(probs, labels, n_bins=n_bins)
    return {
        "brier": round(brier_score(probs, labels), 8),
        "log_loss": round(log_loss_score(probs, labels), 8),
        "ece": ece_result["ece"],
        "sample_size": len(probs),
        "bins": ece_result["bins"],
    }


# ─────────────────────────────────────────────────────────────────────────────
# § 5  Model vs Market Comparison
# ─────────────────────────────────────────────────────────────────────────────

def compare_model_to_market(
    model_probs: list[float],
    market_probs: list[float],
    labels: list[float],
) -> dict:
    """
    Head-to-head comparison of model predictions vs market (no-vig) probabilities.

    Parameters
    ----------
    model_probs : list[float]
        Model-predicted probabilities for the positive class.
    market_probs : list[float]
        Market implied no-vig probabilities for the positive class.
    labels : list[float]
        Observed binary outcomes (0 or 1).

    Returns
    -------
    dict with keys:
        sample_size
        model_brier
        market_brier
        bss                  – Brier Skill Score (model vs market); None if market_brier = 0
        model_log_loss
        market_log_loss
        model_ece            – scalar ECE for model
        market_ece           – scalar ECE for market
        reliability_bins     – reliability bins for model predictions

    Raises
    ------
    ValueError
        If any probability list has values outside [0, 1], or lengths mismatch.
    """
    if len(model_probs) != len(market_probs):
        raise ValueError(
            f"compare_model_to_market: model_probs length {len(model_probs)} "
            f"!= market_probs length {len(market_probs)}."
        )
    _validate_probs_labels(
        model_probs, labels, context="compare_model_to_market (model)", strict_prob_range=True
    )
    _validate_probs_labels(
        market_probs, labels, context="compare_model_to_market (market)", strict_prob_range=True
    )

    m_brier = brier_score(model_probs, labels)
    mkt_brier = brier_score(market_probs, labels)
    bss = brier_skill_score(m_brier, mkt_brier)

    m_ll = log_loss_score(model_probs, labels)
    mkt_ll = log_loss_score(market_probs, labels)

    m_ece_result = expected_calibration_error(model_probs, labels)
    mkt_ece_result = expected_calibration_error(market_probs, labels)

    bins = reliability_bins(model_probs, labels)

    return {
        "sample_size": len(labels),
        "model_brier": round(m_brier, 8),
        "market_brier": round(mkt_brier, 8),
        "bss": round(bss, 8) if bss is not None else None,
        "model_log_loss": round(m_ll, 8),
        "market_log_loss": round(mkt_ll, 8),
        "model_ece": m_ece_result["ece"],
        "market_ece": mkt_ece_result["ece"],
        "reliability_bins": bins,
    }
