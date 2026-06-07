"""P252C — Baseline Calculator SSOT.

Pure-Python module for computing null/random baseline statistics used in
lottery prediction research. Consolidates M4 gap from P252B.

Design constraints:
- No DB connection
- No strategy registry dependency
- No production recommendation dependency
- No numpy / scipy — pure stdlib only
- Deterministic output for identical inputs
- No claim of predictive edge
- No betting advice

Usage::

    from lottery_api.utils.baseline_calculator import (
        combination_count,
        single_ticket_probability,
        n_ticket_probability,
        expected_hits,
        baseline_hit_rate,
        validate_lottery_config,
        random_baseline_summary,
        KNOWN_LOTTERY_CONFIGS,
    )

    # Probability of ≥3 matches for one BIG_LOTTO ticket
    p = single_ticket_probability(pool_size=49, pick_count=6, match_threshold=3)

    # N-ticket baseline (1 - (1-p)^N)
    p4 = n_ticket_probability(pool_size=49, pick_count=6, n_tickets=4, match_threshold=3)

    # Summary report
    summary = random_baseline_summary(
        lottery_type="BIG_LOTTO",
        pool_size=49,
        pick_count=6,
        n_tickets=4,
        n_trials=1500,
        match_threshold=3,
    )
"""
from __future__ import annotations

import math
from typing import Optional

# ---------------------------------------------------------------------------
# Module metadata
# ---------------------------------------------------------------------------

MODULE_VERSION = "1.0"
SCHEMA_VERSION = "1.0"

# ---------------------------------------------------------------------------
# Known lottery configurations (read-only reference; not a strategy registry)
# ---------------------------------------------------------------------------

KNOWN_LOTTERY_CONFIGS: dict[str, dict] = {
    "BIG_LOTTO": {
        "pool_size": 49,
        "pick_count": 6,
        "default_match_threshold": 3,
        "description": "Taiwan Big Lotto — 6/49",
    },
    "POWER_LOTTO": {
        "pool_size": 38,
        "pick_count": 6,
        "default_match_threshold": 3,
        "description": "Taiwan Power Lotto — 6/38 (main zone)",
    },
    "DAILY_539": {
        "pool_size": 39,
        "pick_count": 5,
        "default_match_threshold": 3,
        "description": "Taiwan Daily 539 — 5/39",
    },
    "3_STAR": {
        "pool_size": 10,
        "pick_count": 3,
        "default_match_threshold": 3,
        "description": "Taiwan 3 Star — 3/10 straight-play (sorted storage blocks positional; box-play only)",
    },
    "4_STAR": {
        "pool_size": 10,
        "pick_count": 4,
        "default_match_threshold": 4,
        "description": "Taiwan 4 Star — 4/10 straight-play (sorted storage blocks positional; box-play only)",
    },
}

# ---------------------------------------------------------------------------
# Core mathematical functions — pure stdlib
# ---------------------------------------------------------------------------


def combination_count(pool_size: int, pick_count: int) -> int:
    """Return C(pool_size, pick_count) — number of ways to choose pick_count from pool_size.

    Args:
        pool_size: Total items in pool (e.g. 49 for BIG_LOTTO).
        pick_count: Items to choose (e.g. 6 for BIG_LOTTO).

    Returns:
        int: Binomial coefficient C(pool_size, pick_count).

    Raises:
        ValueError: If parameters are non-positive or pick_count > pool_size.
    """
    _validate_pool_pick(pool_size, pick_count)
    return math.comb(pool_size, pick_count)


def single_ticket_probability(
    pool_size: int,
    pick_count: int,
    match_threshold: int = 3,
) -> float:
    """Probability of matching at least match_threshold numbers with one ticket.

    Uses the hypergeometric model: drawing pick_count from pool_size without
    replacement, where the draw and ticket both consist of pick_count numbers.

    P(exactly m matches) = C(pick_count, m) × C(pool_size − pick_count, pick_count − m)
                           ─────────────────────────────────────────────────────────────
                                           C(pool_size, pick_count)

    P(≥ match_threshold matches) = Σ_{m=match_threshold}^{pick_count} P(exactly m matches)

    Args:
        pool_size: Total numbers in pool.
        pick_count: Numbers on one ticket / drawn per round.
        match_threshold: Minimum matches to count as a hit (e.g. 3 for M3+).

    Returns:
        float: Probability in [0, 1].

    Raises:
        ValueError: If parameters are invalid.
    """
    _validate_pool_pick(pool_size, pick_count)
    _validate_match_threshold(match_threshold, pick_count)

    total = math.comb(pool_size, pick_count)
    complement = pool_size - pick_count  # numbers NOT on the draw

    prob = 0.0
    for m in range(match_threshold, pick_count + 1):
        # Ways to match m of the pick_count drawn numbers
        ways_match = math.comb(pick_count, m)
        # Ways to fill remaining (pick_count - m) slots from numbers NOT drawn
        remaining = pick_count - m
        if remaining > complement:
            # Impossible combination — skip
            continue
        ways_miss = math.comb(complement, remaining)
        prob += ways_match * ways_miss / total

    return prob


def n_ticket_probability(
    pool_size: int,
    pick_count: int,
    n_tickets: int,
    match_threshold: int = 3,
) -> float:
    """Probability of at least one ticket in a set of n_tickets matching ≥ match_threshold.

    P(at least one hit | N tickets) = 1 − (1 − p_single)^N

    This is the correct N-bet baseline formula. Historical bug L14 used the
    per-ticket rate instead — this function implements the correct version.

    Args:
        pool_size: Total numbers in pool.
        pick_count: Numbers on one ticket / drawn per round.
        n_tickets: Number of independent tickets played per draw.
        match_threshold: Minimum matches to count as a hit.

    Returns:
        float: Probability in [0, 1].

    Raises:
        ValueError: If n_tickets < 1 or other parameters invalid.
    """
    if n_tickets < 1:
        raise ValueError(f"n_tickets must be ≥ 1, got {n_tickets}")
    p_single = single_ticket_probability(pool_size, pick_count, match_threshold)
    return 1.0 - (1.0 - p_single) ** n_tickets


def expected_hits(n_trials: int, probability: float) -> float:
    """Expected number of hit trials given n_trials draws and per-draw probability.

    Args:
        n_trials: Number of independent draw trials.
        probability: Per-trial hit probability in [0, 1].

    Returns:
        float: Expected hits = n_trials × probability.

    Raises:
        ValueError: If n_trials < 0 or probability outside [0, 1].
    """
    if n_trials < 0:
        raise ValueError(f"n_trials must be ≥ 0, got {n_trials}")
    if not 0.0 <= probability <= 1.0:
        raise ValueError(f"probability must be in [0, 1], got {probability}")
    return n_trials * probability


def baseline_hit_rate(n_hits: int, n_trials: int) -> float:
    """Observed hit rate = n_hits / n_trials.

    Args:
        n_hits: Number of trials that resulted in a hit.
        n_trials: Total number of trials.

    Returns:
        float: Hit rate in [0, 1].

    Raises:
        ValueError: If n_trials ≤ 0 or n_hits < 0 or n_hits > n_trials.
    """
    if n_trials <= 0:
        raise ValueError(f"n_trials must be > 0, got {n_trials}")
    if n_hits < 0:
        raise ValueError(f"n_hits must be ≥ 0, got {n_hits}")
    if n_hits > n_trials:
        raise ValueError(f"n_hits ({n_hits}) cannot exceed n_trials ({n_trials})")
    return n_hits / n_trials


# ---------------------------------------------------------------------------
# Validation helper
# ---------------------------------------------------------------------------


def validate_lottery_config(
    pool_size: int,
    pick_count: int,
    n_tickets: int = 1,
    match_threshold: int = 3,
) -> dict:
    """Validate lottery configuration parameters.

    Returns a dict with:
        valid (bool): True if all parameters are acceptable.
        errors (list[str]): List of error messages (empty if valid).
        warnings (list[str]): Non-fatal concerns.

    This function never raises — it returns structured error information.
    """
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(pool_size, int) or pool_size < 2:
        errors.append(f"pool_size must be an integer ≥ 2, got {pool_size!r}")
    if not isinstance(pick_count, int) or pick_count < 1:
        errors.append(f"pick_count must be an integer ≥ 1, got {pick_count!r}")
    if not isinstance(pool_size, int) or not isinstance(pick_count, int):
        pass  # already caught above
    elif pick_count >= pool_size:
        errors.append(
            f"pick_count ({pick_count}) must be < pool_size ({pool_size})"
        )
    if not isinstance(n_tickets, int) or n_tickets < 1:
        errors.append(f"n_tickets must be an integer ≥ 1, got {n_tickets!r}")
    if not isinstance(match_threshold, int) or match_threshold < 1:
        errors.append(f"match_threshold must be an integer ≥ 1, got {match_threshold!r}")
    if (
        isinstance(match_threshold, int)
        and isinstance(pick_count, int)
        and match_threshold > pick_count
    ):
        errors.append(
            f"match_threshold ({match_threshold}) cannot exceed pick_count ({pick_count})"
        )

    # Non-fatal warnings
    if not errors:
        if n_tickets > 20:
            warnings.append(
                f"n_tickets={n_tickets} is unusually high for baseline calculations; "
                "verify this is intentional."
            )
        if match_threshold == 1:
            warnings.append(
                "match_threshold=1 means almost any ticket hits; "
                "typical research uses ≥3."
            )

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# Summary report
# ---------------------------------------------------------------------------


def random_baseline_summary(
    pool_size: int,
    pick_count: int,
    n_tickets: int,
    n_trials: int,
    match_threshold: int = 3,
    lottery_type: Optional[str] = None,
    observed_hits: Optional[int] = None,
) -> dict:
    """Produce a structured baseline summary dict.

    This is the canonical output shape for null/random baseline results.
    It explicitly states no_edge_claim=True and includes no betting advice.

    Args:
        pool_size: Total numbers in pool.
        pick_count: Numbers per ticket / draw.
        n_tickets: Tickets played per draw (affects N-bet probability).
        n_trials: Number of draw trials (e.g. backtest length).
        match_threshold: Minimum matches for a hit.
        lottery_type: Optional label (e.g. "BIG_LOTTO").
        observed_hits: Optional int — actual hit count from backtest.

    Returns:
        dict: Structured baseline summary with schema_version and all required fields.

    Raises:
        ValueError: If configuration is invalid.
    """
    validation = validate_lottery_config(pool_size, pick_count, n_tickets, match_threshold)
    if not validation["valid"]:
        raise ValueError(
            f"Invalid lottery config: {'; '.join(validation['errors'])}"
        )

    p_single = single_ticket_probability(pool_size, pick_count, match_threshold)
    p_n = n_ticket_probability(pool_size, pick_count, n_tickets, match_threshold)
    exp_hits = expected_hits(n_trials, p_n)

    summary: dict = {
        "schema_version": SCHEMA_VERSION,
        "baseline_type": "analytical_hypergeometric",
        "lottery_type": lottery_type or "UNKNOWN",
        "pool_size": pool_size,
        "pick_count": pick_count,
        "n_tickets": n_tickets,
        "match_threshold": match_threshold,
        "trials": n_trials,
        "single_ticket_probability": round(p_single, 8),
        "n_ticket_probability": round(p_n, 8),
        "expected_hits": round(exp_hits, 4),
        "baseline_hit_rate": round(p_n, 8),
        "assumptions": [
            "Independent draws from a uniform pool without replacement",
            "Tickets are chosen independently of the draw",
            "No information about future draws is used (pure null/random baseline)",
            "N-ticket formula: 1 - (1 - p_single)^N (correct per L14 fix)",
        ],
        "limitations": [
            "Analytical baseline assumes uniform random draws; real lottery draws may deviate slightly",
            "This baseline quantifies the null hypothesis only — not predictive edge",
            "GREEN randomness audit does not imply any exploitable signal",
        ],
        "no_edge_claim": True,
        "no_betting_advice": True,
        "warnings": validation["warnings"],
    }

    if observed_hits is not None:
        obs_rate = baseline_hit_rate(observed_hits, n_trials)
        summary["observed_hits"] = observed_hits
        summary["observed_hit_rate"] = round(obs_rate, 8)
        summary["edge_vs_baseline"] = round(obs_rate - p_n, 8)

    return summary


# ---------------------------------------------------------------------------
# Internal validation helpers
# ---------------------------------------------------------------------------


def _validate_pool_pick(pool_size: int, pick_count: int) -> None:
    if not isinstance(pool_size, int) or pool_size < 2:
        raise ValueError(f"pool_size must be an integer ≥ 2, got {pool_size!r}")
    if not isinstance(pick_count, int) or pick_count < 1:
        raise ValueError(f"pick_count must be an integer ≥ 1, got {pick_count!r}")
    if pick_count >= pool_size:
        raise ValueError(
            f"pick_count ({pick_count}) must be strictly less than pool_size ({pool_size})"
        )


def _validate_match_threshold(match_threshold: int, pick_count: int) -> None:
    if not isinstance(match_threshold, int) or match_threshold < 1:
        raise ValueError(f"match_threshold must be an integer ≥ 1, got {match_threshold!r}")
    if match_threshold > pick_count:
        raise ValueError(
            f"match_threshold ({match_threshold}) cannot exceed pick_count ({pick_count})"
        )
