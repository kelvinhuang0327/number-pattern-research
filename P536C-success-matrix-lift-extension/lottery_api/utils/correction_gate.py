"""P252D — Multiple Testing Correction Gate SSOT.

Pure-Python module for Bonferroni and Benjamini-Hochberg FDR corrections.
Consolidates M6 gap from P252B. Standardises correction logic previously
scattered across P211R, P214C, P222, P227C, P219, and related research scripts.

Design constraints:
- No DB connection
- No strategy registry dependency
- No production recommendation dependency
- No numpy / scipy / statsmodels — pure stdlib only (math, typing)
- Deterministic output for identical inputs
- No claim of predictive edge
- No betting advice

Usage::

    from lottery_api.utils.correction_gate import (
        validate_p_values,
        bonferroni_correction,
        benjamini_hochberg_fdr,
        correction_summary,
        correction_gate_summary,
    )

    # Bonferroni over 7 position tests
    result = bonferroni_correction([0.03, 0.12, 0.001, 0.045, 0.22, 0.08, 0.009])
    assert result["threshold"] == pytest.approx(0.05 / 7)

    # Full gate summary (both methods)
    report = correction_gate_summary(
        p_values=[0.001, 0.008, 0.039, 0.041, 0.042, 0.06, 0.074, 0.205, 0.212, 0.216],
        alpha=0.05,
        family_label="P222_DAILY_539_10_hypotheses",
    )
    assert report["no_edge_claim"] is True
"""
from __future__ import annotations

import math
from typing import Optional, Sequence

# ---------------------------------------------------------------------------
# Module metadata
# ---------------------------------------------------------------------------

MODULE_VERSION = "1.0"
SCHEMA_VERSION = "1.0"

ALLOWED_METHODS = ("bonferroni", "bh_fdr")


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_p_values(p_values: Sequence[float]) -> dict:
    """Validate a sequence of p-values.

    Args:
        p_values: Sequence of floats expected to be in [0, 1].

    Returns:
        dict with keys:
            valid (bool): True if all checks pass.
            errors (list[str]): Error messages if invalid.
            n (int): Number of p-values (0 if invalid input type).
    """
    errors: list[str] = []

    if not hasattr(p_values, "__iter__") or isinstance(p_values, (str, bytes)):
        errors.append(f"p_values must be a list/tuple of floats, got {type(p_values).__name__!r}")
        return {"valid": False, "errors": errors, "n": 0}

    p_list = list(p_values)

    if len(p_list) == 0:
        errors.append("p_values must not be empty")
        return {"valid": False, "errors": errors, "n": 0}

    for idx, p in enumerate(p_list):
        if not isinstance(p, (int, float)):
            errors.append(f"p_values[{idx}] must be numeric, got {type(p).__name__!r}")
        elif math.isnan(p) or math.isinf(p):
            errors.append(f"p_values[{idx}] must be finite, got {p!r}")
        elif not (0.0 <= p <= 1.0):
            errors.append(f"p_values[{idx}] = {p!r} is outside [0, 1]")

    return {"valid": len(errors) == 0, "errors": errors, "n": len(p_list)}


# ---------------------------------------------------------------------------
# Bonferroni correction
# ---------------------------------------------------------------------------


def bonferroni_correction(
    p_values: Sequence[float],
    alpha: float = 0.05,
) -> dict:
    """Apply Bonferroni correction to a list of p-values.

    Adjusted p-value: p_adj[i] = min(p[i] × m, 1.0)
    Rejection decision: p_adj[i] < alpha   (strictly less than)
    Threshold for raw p-values: alpha / m

    Args:
        p_values: Sequence of raw p-values in [0, 1].
        alpha: Family-wise error rate target (default 0.05).

    Returns:
        dict with:
            method = "bonferroni"
            n_tests (int)
            threshold (float): alpha / n_tests
            alpha (float)
            raw_p_values (list[float])
            adjusted_p_values (list[float]): min(p * m, 1.0)
            rejected (list[bool]): True if adjusted_p < alpha
            survivor_count (int): number of rejected hypotheses
            correction_required (bool): always True

    Raises:
        ValueError: If p_values are invalid.
    """
    _require_valid(p_values)
    p_list = [float(p) for p in p_values]
    m = len(p_list)
    threshold = alpha / m
    adjusted = [min(p * m, 1.0) for p in p_list]
    rejected = [adj < alpha for adj in adjusted]
    return {
        "method": "bonferroni",
        "n_tests": m,
        "alpha": alpha,
        "threshold": round(threshold, 10),
        "raw_p_values": p_list,
        "adjusted_p_values": [round(adj, 10) for adj in adjusted],
        "rejected": rejected,
        "survivor_count": sum(rejected),
        "correction_required": True,
    }


# ---------------------------------------------------------------------------
# Benjamini-Hochberg FDR correction
# ---------------------------------------------------------------------------


def benjamini_hochberg_fdr(
    p_values: Sequence[float],
    alpha: float = 0.05,
) -> dict:
    """Apply Benjamini-Hochberg FDR correction to a list of p-values.

    Standard BH step-up procedure (Benjamini & Hochberg 1995):

    1. Sort p-values in ascending order: p_(1) ≤ p_(2) ≤ ... ≤ p_(m).
    2. Find the largest rank k* such that p_(k*) ≤ (k*/m) × α.
    3. Reject all H_(i) for i ≤ k*.

    BH-adjusted p-values (q-values) are computed as the step-down monotone
    sequence:
        q_(m) = p_(m)
        q_(k) = min(p_(k) × m / k, q_(k+1))

    These satisfy: rejected[i] ← q[i] < α.

    Args:
        p_values: Sequence of raw p-values in [0, 1].
        alpha: FDR target level (default 0.05).

    Returns:
        dict with:
            method = "bh_fdr"
            n_tests (int)
            alpha (float)
            raw_p_values (list[float])
            adjusted_p_values (list[float]): BH q-values, monotone
            rejected (list[bool]): True if q_value < alpha
            survivor_count (int)
            correction_required (bool): always True

    Raises:
        ValueError: If p_values are invalid.
    """
    _require_valid(p_values)
    p_list = [float(p) for p in p_values]
    m = len(p_list)

    # Sort indices by ascending p-value
    order = sorted(range(m), key=lambda i: p_list[i])

    # Compute BH q-values in step-down fashion (from largest rank to smallest)
    q = [0.0] * m
    # rank k goes from m down to 1 in sorted order
    min_q = 1.0
    for rev_k, sorted_idx in enumerate(reversed(order)):
        rank = m - rev_k  # rank in 1..m (largest first)
        raw_p = p_list[sorted_idx]
        q_candidate = min(raw_p * m / rank, 1.0)
        min_q = min(min_q, q_candidate)
        q[sorted_idx] = min_q

    rejected = [qi < alpha for qi in q]
    return {
        "method": "bh_fdr",
        "n_tests": m,
        "alpha": alpha,
        "raw_p_values": p_list,
        "adjusted_p_values": [round(qi, 10) for qi in q],
        "rejected": rejected,
        "survivor_count": sum(rejected),
        "correction_required": True,
    }


# ---------------------------------------------------------------------------
# Summary builders
# ---------------------------------------------------------------------------


def correction_summary(
    raw_p_values: Sequence[float],
    adjusted_p_values: Sequence[float],
    rejected: Sequence[bool],
    method: str,
    alpha: float,
    family_label: Optional[str] = None,
) -> dict:
    """Build a standard correction summary dict from pre-computed results.

    Args:
        raw_p_values: Original p-values.
        adjusted_p_values: Corrected p-values (Bonferroni or BH q-values).
        rejected: Rejection decision per test.
        method: "bonferroni" or "bh_fdr".
        alpha: Target error rate used.
        family_label: Optional label for the hypothesis family.

    Returns:
        dict: Standard correction summary with no_edge_claim=True.
    """
    n = len(list(raw_p_values))
    survivors = sum(rejected)
    return {
        "schema_version": SCHEMA_VERSION,
        "gate_type": "multiple_testing_correction",
        "family_label": family_label or "UNLABELED",
        "alpha": alpha,
        "method": method,
        "n_tests": n,
        "raw_p_values": list(raw_p_values),
        "adjusted_p_values": list(adjusted_p_values),
        "rejected": list(rejected),
        "survivor_count": survivors,
        "null_count": n - survivors,
        "correction_required": True,
        "no_edge_claim": True,
        "no_betting_advice": True,
        "assumptions": [
            "Tests are independent or positively correlated (BH-FDR)",
            "p-values are uniformly distributed under the null hypothesis",
            "Family size is pre-declared before data inspection",
        ],
        "limitations": [
            "Bonferroni is conservative when tests are positively correlated",
            "BH-FDR controls expected proportion of false discoveries, not family-wise error",
            "A rejection does not imply a deployable prediction edge",
            "GREEN randomness does not imply any exploitable signal",
        ],
    }


def correction_gate_summary(
    p_values: Sequence[float],
    alpha: float = 0.05,
    methods: Sequence[str] = ("bonferroni", "bh_fdr"),
    family_label: Optional[str] = None,
) -> dict:
    """Run one or more corrections and return a combined summary.

    This is the canonical entry point for correction gate output.
    Always includes no_edge_claim=True.

    Args:
        p_values: Raw p-values for the hypothesis family.
        alpha: Target error rate.
        methods: Subset of ("bonferroni", "bh_fdr") to apply.
        family_label: Optional label for audit trail.

    Returns:
        dict: Combined correction summary.

    Raises:
        ValueError: If p_values invalid or methods unknown.
    """
    validation = validate_p_values(p_values)
    if not validation["valid"]:
        raise ValueError(
            f"Invalid p-values: {'; '.join(validation['errors'])}"
        )
    for m in methods:
        if m not in ALLOWED_METHODS:
            raise ValueError(f"Unknown correction method: {m!r}. Allowed: {ALLOWED_METHODS}")

    p_list = [float(p) for p in p_values]
    n = len(p_list)
    results: dict = {
        "schema_version": SCHEMA_VERSION,
        "gate_type": "multiple_testing_correction",
        "family_label": family_label or "UNLABELED",
        "alpha": alpha,
        "methods_applied": list(methods),
        "n_tests": n,
        "raw_p_values": p_list,
        "no_edge_claim": True,
        "no_betting_advice": True,
        "correction_required": True,
        "assumptions": [
            "Tests are independent or positively correlated (BH-FDR)",
            "p-values are uniformly distributed under the null hypothesis",
            "Family size is pre-declared before data inspection",
        ],
        "limitations": [
            "Bonferroni is conservative when tests are positively correlated",
            "BH-FDR controls expected proportion of false discoveries, not family-wise error",
            "A rejection does not imply a deployable prediction edge",
            "GREEN randomness does not imply any exploitable signal",
        ],
    }

    if "bonferroni" in methods:
        bonf = bonferroni_correction(p_list, alpha)
        results["bonferroni"] = {
            "threshold": bonf["threshold"],
            "adjusted_p_values": bonf["adjusted_p_values"],
            "rejected": bonf["rejected"],
            "survivor_count": bonf["survivor_count"],
        }

    if "bh_fdr" in methods:
        bh = benjamini_hochberg_fdr(p_list, alpha)
        results["bh_fdr"] = {
            "adjusted_p_values": bh["adjusted_p_values"],
            "rejected": bh["rejected"],
            "survivor_count": bh["survivor_count"],
        }

    return results


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------


def _require_valid(p_values: Sequence[float]) -> None:
    validation = validate_p_values(p_values)
    if not validation["valid"]:
        raise ValueError(
            f"Invalid p-values: {'; '.join(validation['errors'])}"
        )
