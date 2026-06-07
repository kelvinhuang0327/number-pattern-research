"""P252E — Permutation Test SSOT.

Pure-Python module for empirical p-value calculation from a Monte-Carlo
null distribution. Consolidates M5 gap from P252B. Standardises permutation-
test logic previously scattered across P219, Special3, P51, P3, and related
research scripts.

Design constraints:
- No DB connection
- No strategy registry dependency
- No production recommendation dependency
- No numpy / scipy — pure stdlib only (random, math, statistics, typing)
- Deterministic output when a seed is supplied
- No claim of predictive edge
- No betting advice

Key design decision — plus-one correction:
    The empirical p-value uses the formula (1 + count_extreme) / (B + 1)
    (Phipson & Smyth 2010). This avoids p=0 when the observed statistic is
    more extreme than every null sample, and is the formula used in p219
    (reference implementation). The L96 bug in older scripts arose from
    shuffling hit-count labels, which preserves the mean; this module does
    NOT generate null distributions — it receives a pre-generated one.

Usage::

    from lottery_api.utils.permutation_test import (
        empirical_p_value,
        permutation_summary,
        compare_observed_to_null,
        deterministic_shuffle,
        validate_permutation_inputs,
    )

    null = [0.012, 0.018, 0.025, 0.009, 0.021, ...]  # B null samples
    p = empirical_p_value(observed=0.030, null_distribution=null, alternative="greater")
    # p = (1 + count(null >= 0.030 - ε)) / (B + 1)

    summary = permutation_summary(
        observed_statistic=0.030,
        null_distribution=null,
        alternative="greater",
        seed=42,
        family_label="DAILY_539_midfreq",
    )
    assert summary["no_edge_claim"] is True
"""
from __future__ import annotations

import math
import random
import statistics
from typing import Optional, Sequence

# ---------------------------------------------------------------------------
# Module metadata
# ---------------------------------------------------------------------------

MODULE_VERSION = "1.0"
SCHEMA_VERSION = "1.0"

ALLOWED_ALTERNATIVES = ("greater", "less", "two-sided")
EPSILON = 1e-12  # tolerance for floating-point comparisons at boundary


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_permutation_inputs(
    observed_statistic: float,
    null_distribution: Sequence[float],
    alternative: str = "greater",
) -> dict:
    """Validate inputs for empirical p-value calculation.

    Args:
        observed_statistic: The test statistic from the real data.
        null_distribution: Sequence of statistics from null/random trials.
        alternative: One of "greater", "less", "two-sided".

    Returns:
        dict with keys:
            valid (bool): True if all checks pass.
            errors (list[str]): Error messages.
            n_null (int): Length of null_distribution (0 if input invalid).
    """
    errors: list[str] = []

    if not isinstance(observed_statistic, (int, float)):
        errors.append(
            f"observed_statistic must be numeric, got {type(observed_statistic).__name__!r}"
        )
    elif math.isnan(observed_statistic) or math.isinf(observed_statistic):
        errors.append(f"observed_statistic must be finite, got {observed_statistic!r}")

    if not hasattr(null_distribution, "__iter__") or isinstance(null_distribution, (str, bytes)):
        errors.append(
            f"null_distribution must be a list/sequence, got {type(null_distribution).__name__!r}"
        )
        return {"valid": False, "errors": errors, "n_null": 0}

    null_list = list(null_distribution)
    if len(null_list) == 0:
        errors.append("null_distribution must not be empty")
    else:
        for idx, v in enumerate(null_list):
            if not isinstance(v, (int, float)):
                errors.append(
                    f"null_distribution[{idx}] must be numeric, got {type(v).__name__!r}"
                )
            elif math.isnan(v) or math.isinf(v):
                errors.append(f"null_distribution[{idx}] is non-finite: {v!r}")

    if alternative not in ALLOWED_ALTERNATIVES:
        errors.append(
            f"alternative must be one of {ALLOWED_ALTERNATIVES}, got {alternative!r}"
        )

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "n_null": len(null_list) if not errors or (len(errors) == 1 and "empty" not in errors[0]) else 0,
    }


# ---------------------------------------------------------------------------
# Core empirical p-value
# ---------------------------------------------------------------------------


def empirical_p_value(
    observed_statistic: float,
    null_distribution: Sequence[float],
    alternative: str = "greater",
    plus_one: bool = True,
) -> float:
    """Compute empirical p-value from a Monte-Carlo null distribution.

    Uses the formula  (1 + count_extreme) / (B + 1)  when plus_one=True
    (Phipson & Smyth 2010), or  count_extreme / B  when plus_one=False.
    The plus-one form prevents p=0 and gives a conservative, valid p-value.

    This is the standard formula from p219 (reference implementation).

    Args:
        observed_statistic: The test statistic computed from real data.
        null_distribution: Sequence of B test statistics under the null.
        alternative: "greater" (default), "less", or "two-sided".
            - "greater": p = proportion of null >= observed (upper-tail)
            - "less": p = proportion of null <= observed (lower-tail)
            - "two-sided": p = 2 × min(upper, lower), capped at 1.0
        plus_one: If True (default), apply the +1 Phipson-Smyth correction.
            Set False only for comparison with uncorrected implementations.

    Returns:
        float: Empirical p-value in (0, 1] when plus_one=True, or [0, 1].

    Raises:
        ValueError: If inputs are invalid.
    """
    _require_valid(observed_statistic, null_distribution, alternative)
    null_list = [float(v) for v in null_distribution]
    b = len(null_list)
    obs = float(observed_statistic)

    if alternative == "greater":
        count = sum(1 for s in null_list if s >= obs - EPSILON)
        if plus_one:
            return (1 + count) / (b + 1)
        return count / b

    if alternative == "less":
        count = sum(1 for s in null_list if s <= obs + EPSILON)
        if plus_one:
            return (1 + count) / (b + 1)
        return count / b

    # two-sided
    c_greater = sum(1 for s in null_list if s >= obs - EPSILON)
    c_less    = sum(1 for s in null_list if s <= obs + EPSILON)
    if plus_one:
        return min(1.0, 2.0 * (1 + min(c_greater, c_less)) / (b + 1))
    return min(1.0, 2.0 * min(c_greater, c_less) / b)


# ---------------------------------------------------------------------------
# Null distribution summary
# ---------------------------------------------------------------------------


def compare_observed_to_null(
    observed_statistic: float,
    null_distribution: Sequence[float],
) -> dict:
    """Compute summary statistics of a null distribution vs the observed.

    Args:
        observed_statistic: Test statistic from real data.
        null_distribution: Sequence of null statistics.

    Returns:
        dict with null_count, null_min, null_max, null_mean, null_std,
        null_median, observed_statistic, obs_percentile (0–100),
        obs_above_null_mean (bool), obs_above_null_median (bool).

    Raises:
        ValueError: If inputs are invalid.
    """
    _require_valid(observed_statistic, null_distribution, "greater")
    null_list = [float(v) for v in null_distribution]
    obs = float(observed_statistic)
    b = len(null_list)

    null_min  = min(null_list)
    null_max  = max(null_list)
    null_mean = sum(null_list) / b
    null_med  = statistics.median(null_list)
    null_std  = statistics.pstdev(null_list) if b > 1 else 0.0
    percentile = sum(1 for s in null_list if s <= obs) / b * 100.0

    return {
        "observed_statistic": obs,
        "null_count": b,
        "null_min": null_min,
        "null_max": null_max,
        "null_mean": null_mean,
        "null_std": null_std,
        "null_median": null_med,
        "obs_percentile": round(percentile, 2),
        "obs_above_null_mean": obs > null_mean,
        "obs_above_null_median": obs > null_med,
    }


# ---------------------------------------------------------------------------
# Permutation summary — canonical output
# ---------------------------------------------------------------------------


def permutation_summary(
    observed_statistic: float,
    null_distribution: Sequence[float],
    alternative: str = "greater",
    plus_one: bool = True,
    seed: Optional[int] = None,
    family_label: Optional[str] = None,
) -> dict:
    """Produce a structured permutation test summary dict.

    This is the canonical SSOT output for permutation test results.
    Always includes no_edge_claim=True and no_betting_advice=True.

    Args:
        observed_statistic: Test statistic from real data.
        null_distribution: Sequence of B null statistics (pre-generated).
        alternative: "greater", "less", or "two-sided".
        plus_one: Apply plus-one Phipson-Smyth correction (default True).
        seed: Optional RNG seed used when generating null_distribution
              (for audit trail only — not used internally here).
        family_label: Optional label for the hypothesis / family.

    Returns:
        dict: Structured summary with schema_version and all required fields.

    Raises:
        ValueError: If inputs are invalid.
    """
    _require_valid(observed_statistic, null_distribution, alternative)
    null_list = [float(v) for v in null_distribution]
    obs = float(observed_statistic)
    b = len(null_list)

    p_val = empirical_p_value(obs, null_list, alternative, plus_one)
    null_stats = compare_observed_to_null(obs, null_list)

    return {
        "schema_version": SCHEMA_VERSION,
        "test_type": "permutation_test",
        "family_label": family_label or "UNLABELED",
        "alternative": alternative,
        "observed_statistic": obs,
        "null_count": b,
        "null_min": null_stats["null_min"],
        "null_max": null_stats["null_max"],
        "null_mean": null_stats["null_mean"],
        "null_std": null_stats["null_std"],
        "null_median": null_stats["null_median"],
        "obs_percentile": null_stats["obs_percentile"],
        "empirical_p_value": p_val,
        "plus_one_correction": plus_one,
        "seed": seed,
        "no_edge_claim": True,
        "no_betting_advice": True,
        "assumptions": [
            "Null distribution is generated by a valid null-generation process "
            "(e.g., random permutation of labels, Binomial(1, baseline_i) MC draws, "
            "or random shuffling of draw sequences)",
            "Null samples are exchangeable under H0",
            "The plus-one correction prevents p=0 and gives a conservative valid p-value",
            "A pre-declared hypothesis and family size are required before inspecting data",
        ],
        "limitations": [
            "L96 warning: shuffling binary hit-labels preserves their mean, causing "
            "the null distribution to overlap the observed — use Binomial MC null instead",
            "Empirical p is discrete; minimum achievable p is 1/(B+1) with plus-one correction",
            "A significant empirical p does not imply a deployable prediction edge",
            "GREEN randomness does not imply any exploitable signal",
        ],
    }


# ---------------------------------------------------------------------------
# Deterministic shuffle helper
# ---------------------------------------------------------------------------


def deterministic_shuffle(values: Sequence, seed: int) -> list:
    """Return a deterministically shuffled copy of values using the given seed.

    Args:
        values: Sequence to shuffle (not modified in place).
        seed: Integer RNG seed for reproducibility.

    Returns:
        list: Shuffled copy.

    Raises:
        ValueError: If values is empty or seed is not an integer.
    """
    if not isinstance(seed, int):
        raise ValueError(f"seed must be an integer, got {type(seed).__name__!r}")
    lst = list(values)
    if len(lst) == 0:
        raise ValueError("values must not be empty")
    rng = random.Random(seed)
    rng.shuffle(lst)
    return lst


# ---------------------------------------------------------------------------
# Internal validation helper
# ---------------------------------------------------------------------------


def _require_valid(
    observed_statistic: float,
    null_distribution: Sequence[float],
    alternative: str,
) -> None:
    result = validate_permutation_inputs(observed_statistic, null_distribution, alternative)
    if not result["valid"]:
        raise ValueError(
            f"Invalid permutation test inputs: {'; '.join(result['errors'])}"
        )
