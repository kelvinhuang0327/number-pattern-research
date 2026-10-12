"""P272B — Prospective OOS Detectability & Apply Go/No-Go Power Brief.

Statistical research / artifact task. This module quantifies, for a *future*
(prospective) out-of-sample stream, how many draws would be required to detect a
historically-observed M3+ excess at the pre-registered family alpha and power
targets, and converts those draw counts into calendar horizons.

CRITICAL TRUTHFULNESS NOTES
---------------------------
* This is a *power feasibility* (required-sample-size) computation. It does NOT
  establish, claim, or imply that any predictive edge exists. Power feasibility
  is not evidence of an edge. Every effect scenario used here is a committed
  *historical observed excess* that did NOT survive multiplicity correction in
  P267C (0/36 cells passed Bonferroni or BH-FDR).
* Nothing here authorizes production apply, controlled apply, prospective
  activation, P271M, or P271N. No prediction-success claim is made.

IMPLEMENTATION CONSTRAINTS (enforced by tests + static scan)
------------------------------------------------------------
* Pure, deterministic, import-safe. No import-time side effects / artifact writes.
* No sqlite3, no SQLAlchemy/create_engine, no DB connection, no SQL.
* No requests / network access. No subprocess / process control. No registry.
* Exact one-sided binomial method (log-gamma PMF + tail summation), NOT a
  normal/Poisson approximation. A normal approximation is computed separately and
  labelled as an approximate cross-check only.
* All decisive constants come from the locked contract / evidence manifest below;
  they are defined once here and imported (not duplicated) by the test module.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

# ---------------------------------------------------------------------------
# Static identifiers (deterministic — no live clock, no subprocess/git call).
# ---------------------------------------------------------------------------
TASK_ID = "P272B_PROSPECTIVE_OOS_DETECTABILITY_POWER"
ARTIFACT_DATE = "2026-06-14"  # task date; fixed constant to keep regen deterministic
BRANCH = "task/p272b-prospective-oos-detectability-power"
BASE_MAIN = "8b62b358aef3e9fce8962054c166e80c1944d00c"
SUCCESS_CLASSIFICATION = "P272B_PROSPECTIVE_OOS_DETECTABILITY_POWER_COMPLETE"
PROJECT_CLASSIFICATION = "P271L_PREFLIGHT_COMPLETE_NOT_READY_FOR_APPLY"

LOTTERIES = ("DAILY_539", "BIG_LOTTO", "POWER_LOTTO")

# Permitted decision classifications (Phase 2 contract).
ALLOWED_DECISIONS = (
    "PROSPECTIVE_APPLY_POWER_GO",
    "PROSPECTIVE_APPLY_POWER_NO_GO",
    "POWER_QUANTIFIED_THRESHOLD_NOT_GOVERNED",
    "NOT_DETECTABLE_WITHIN_SEARCH_BOUND",
    "P272B_BLOCKED_UNTRACEABLE_POWER_INPUT",
)

# ---------------------------------------------------------------------------
# LOCKED PRE-REGISTERED CONTRACT (Phase 2).
# ---------------------------------------------------------------------------
CONTRACT = {
    "lotteries": list(LOTTERIES),
    "primary_endpoint": "P265A-compatible draw-level M3+ any-bet (hit_count>=3; special_hit excluded; denominator=distinct target_draw)",
    "primary_bet_count": 1,
    "power_targets": [0.80, 0.90],
    "family_alpha": 0.05,
    "primary_correction": "Bonferroni",
    "primary_correction_m": 3,
    "bh_fdr": "descriptive_only",
    "deterministic_seed": 42,  # no stochastic component is used; recorded per governance
    "effect_scenarios": "committed_evidence_only",
    "calendar_reporting_horizons_years": [1, 3, 5, 10],
    "test_sidedness": "one_sided_upper",  # Phase 3 mandates exact ONE-SIDED binomial
    "no_invented_deployable_threshold": True,
    "no_retrospective_strategy_reselection": True,
}

# Per-test alpha after Bonferroni correction over m=3 lotteries (one-sided).
ALPHA_CORRECTED = CONTRACT["family_alpha"] / CONTRACT["primary_correction_m"]  # 0.016666...
ALPHA_UNCORRECTED = CONTRACT["family_alpha"]  # 0.05

# Bounded N search ceiling (Phase 3: explicit maximum). Far above any plausible N*.
DEFAULT_MAX_N = 100_000

# ---------------------------------------------------------------------------
# LOTTERY POOL / PICK (decisive input).
# DAILY_539 5/39, BIG_LOTTO 6/49, POWER_LOTTO first-zone 6/38 (+ 1/8 second zone,
# excluded from the M3+ first-zone endpoint). p0_committed = the exact 1-bet M3+
# hypergeometric baseline as committed in P267C one_bet_baseline_sanity; this
# module recomputes p0 from (pool, pick) and asserts equality to the committed
# value (see verify_p0_against_committed()).
# ---------------------------------------------------------------------------
LOTTERY_SPECS = {
    "DAILY_539": {"pool": 39, "pick": 5, "p0_committed": 0.010041},
    "BIG_LOTTO": {"pool": 49, "pick": 6, "p0_committed": 0.018638},
    "POWER_LOTTO": {"pool": 38, "pick": 6, "p0_committed": 0.038698, "second_zone": 8},
}

# Committed historical observed-excess scenarios (effect sizes, in percentage
# points). Source: P267C best uncorrected per-lottery observed excess, surfaced as
# `p267c_best_uncorrected_excess_pp` in P270B mde_summary and as the per-cell
# Excess(pp) column in the P267C results table. These are upper-plausible
# scenarios; NONE survived multiplicity correction.
EFFECT_SCENARIO_PP = {
    "DAILY_539": 1.32,    # daily539_f4cold_5bet, +1.32pp, p=0.0308 (uncorrected)
    "BIG_LOTTO": 1.23,    # biglotto_ts3_markov_4bet_w30, +1.23pp, p=0.0786
    "POWER_LOTTO": 1.48,  # midfreq_fourier_mk_3bet, +1.48pp, p=0.0634
}

# Draw cadence (decisive input) reproducibly derived from committed draw dates in
# outputs/research/p268d1_draw_order_full_history_artifact_backfill_20260610.jsonl
# (field: draw_date). Method: modal weekday set over the most recent complete
# calendar year (2025) of that committed source. draws/year = dpw * 365.25/7.
CADENCE = {
    "DAILY_539": {"draws_per_week": 6, "weekdays": "Mon-Sat"},
    "BIG_LOTTO": {"draws_per_week": 2, "weekdays": "Tue,Fri"},
    "POWER_LOTTO": {"draws_per_week": 2, "weekdays": "Mon,Thu"},
}
DAYS_PER_YEAR = 365.25
DAYS_PER_WEEK = 7.0

# ---------------------------------------------------------------------------
# EVIDENCE MANIFEST (Phase 1). Decisive inputs only. SHA-256 of each committed
# source recorded for provenance; the dated research artifacts in
# outputs/research/ are immutable and re-hashed by the test suite.
# ---------------------------------------------------------------------------
P267C_JSON = "outputs/research/p267c_m3plus_strategy_revalidation_20260610.json"
P267C_MD = "outputs/research/p267c_m3plus_strategy_revalidation_20260610.md"
P270B_JSON = "outputs/research/p270b_outcome_blind_portfolio_geometry_power_audit_20260611.json"
P265A_MD = "outputs/research/p265a_d3_m3_real_replay_success_rate_20260610.md"
P268D1_JSONL = "outputs/research/p268d1_draw_order_full_history_artifact_backfill_20260610.jsonl"
LOTTERY_CLAUDE_MD = "lottery_api/CLAUDE.md"

# Hashes verified at authoring time (Phase 1). Test re-hashes the immutable
# dated outputs/research artifacts; lottery_api/CLAUDE.md is corroborating only.
EVIDENCE_SOURCE_SHA256 = {
    P267C_JSON: "3769596df51f6eaab5ef98cdf799ba9915f0c0349810f0899a7516004639a241",
    P267C_MD: "a223a81099ebb12bc1d3df4f8db32f37977bb8a354fe007e5c0988c25349860f",
    P270B_JSON: "37808a0166d22113598eaf0458e190c92187708424e690109fd432c7168c53d9",
    P265A_MD: "6c9d8af89381ddfc495f3dec62a2bad0ccc8c27fd9b81f708418279b5b60d41f",
    P268D1_JSONL: "f4accb6f527694e739689242c929e87e4b031a364becb4fadb4aaea50ef2e3f8",
    LOTTERY_CLAUDE_MD: "7124d1d519c464d472115cf934b98d9b7cf6e9f650520c1e7f2dd9578eb550d5",
}
# Immutable dated artifacts the test suite re-hashes for traceability.
DECISIVE_HASH_VERIFY_SOURCES = (P267C_JSON, P267C_MD, P270B_JSON, P265A_MD, P268D1_JSONL)

# Governed acceptable-horizon search (Phase 1 / Phase 2). An exhaustive bounded
# search of 00-Plan/, docs/, and outputs/research/ found NO committed governed
# acceptable detection horizon or deployable threshold for prospective M3+
# detectability. (Loose narrative phrases like "3-5 years of data" in old
# executive summaries are not a governed go/no-go threshold.)
GOVERNED_HORIZON_YEARS = None
GOVERNED_HORIZON_SEARCH_RESULT = "NO_GOVERNED_ACCEPTABLE_HORIZON_OR_THRESHOLD_FOUND"

# Actual focused/regression test results (filled as constants after execution so
# artifact regeneration stays byte-deterministic). See Phase 4.
TEST_EXECUTION = {
    "focused_command": "./venv/bin/python -m pytest tests/test_p272b_prospective_oos_detectability_power.py -q",
    "focused_result": "61 passed",
    "regression_p267c": "19 passed",
    "regression_p270b": "12 passed",
    "regression_p271l_preflight": "50 passed",
    "regression_p271l_readonly_schema": "72 passed",
    "full_repository_suite": "NOT_RUN",
    "git_diff_check": "PASS",
    "static_forbidden_interface_scan": "PASS",
    "json_parse_validation": "PASS",
    "deterministic_regeneration": "PASS",
    "markdown_json_consistency": "PASS",
}


# ===========================================================================
# Exact binomial engine (pure functions).
# ===========================================================================
def _validate_prob(p: float, name: str) -> None:
    if not isinstance(p, (int, float)) or isinstance(p, bool):
        raise ValueError(f"{name} must be a real number, got {type(p).__name__}")
    if not (0.0 <= p <= 1.0):
        raise ValueError(f"{name} must be in [0, 1], got {p}")


def _validate_open_prob(p: float, name: str) -> None:
    _validate_prob(p, name)
    if not (0.0 < p < 1.0):
        raise ValueError(f"{name} must be strictly in (0, 1), got {p}")


def _validate_n(n: int, name: str = "n") -> None:
    if isinstance(n, bool) or not isinstance(n, int):
        raise ValueError(f"{name} must be an integer, got {type(n).__name__}")
    if n < 1:
        raise ValueError(f"{name} must be a positive integer, got {n}")


def log_binom_pmf(n: int, k: int, p: float) -> float:
    """log P(X = k) for X ~ Binomial(n, p). Returns -inf for impossible (k, p)."""
    if k < 0 or k > n:
        return float("-inf")
    if p <= 0.0:
        return 0.0 if k == 0 else float("-inf")
    if p >= 1.0:
        return 0.0 if k == n else float("-inf")
    return (
        math.lgamma(n + 1)
        - math.lgamma(k + 1)
        - math.lgamma(n - k + 1)
        + k * math.log(p)
        + (n - k) * math.log1p(-p)
    )


def binom_sf_ge(n: int, k: int, p: float) -> float:
    """Exact upper tail P(X >= k) for X ~ Binomial(n, p).

    Computed with the exact binomial distribution (NOT a normal/Poisson
    approximation). The summation is anchored at the distribution mode — where
    the PMF is largest and always representable — and weights are accumulated
    outward relative to the mode, then normalised. This is numerically stable
    for all (n, k, p): a naive recurrence anchored at k underflows when k lies
    far in a tail (the anchor PMF rounds to 0.0 and the recurrence stays 0).
    """
    _validate_n(n)
    _validate_prob(p, "p")
    if k <= 0:
        return 1.0
    if k > n:
        return 0.0
    if p <= 0.0:
        return 0.0  # k >= 1 impossible when p == 0
    if p >= 1.0:
        return 1.0  # X == n >= k (k <= n)

    mode = min(max(int((n + 1) * p), 0), n)  # index of the maximum PMF term
    up_ratio = p / (1.0 - p)
    down_ratio = (1.0 - p) / p

    total = 1.0                      # mode weight (pmf(mode)/pmf(mode) == 1)
    tail = 1.0 if mode >= k else 0.0  # mode contributes to the upper tail iff mode >= k

    # Walk up from the mode.
    w = 1.0
    i = mode
    while i < n:
        w *= ((n - i) / (i + 1)) * up_ratio
        i += 1
        total += w
        if i >= k:
            tail += w
        if w < 1e-300:
            break

    # Walk down from the mode.
    w = 1.0
    i = mode
    while i > 0:
        w *= (i / (n - i + 1)) * down_ratio
        i -= 1
        total += w
        if i >= k:
            tail += w
        if w < 1e-300:
            break

    result = tail / total  # normalise by the (numerically complete) mass sum
    if result < 0.0:
        return 0.0
    return result if result < 1.0 else 1.0


def binom_cdf_le(n: int, k: int, p: float) -> float:
    """Exact lower CDF P(X <= k) = 1 - P(X >= k+1)."""
    if k < 0:
        return 0.0
    if k >= n:
        return 1.0
    return 1.0 - binom_sf_ge(n, k + 1, p)


def one_sided_rejection_threshold(n: int, p0: float, alpha: float) -> dict:
    """Smallest k* such that the one-sided rejection region {X >= k*} has exact
    size P(X >= k* | p0) <= alpha.

    Returns {"k_star", "actual_size"}. k_star == n + 1 means the region is empty
    (size 0) — i.e. no rejection achievable at non-trivial k for this (n, alpha).
    """
    _validate_n(n)
    _validate_open_prob(p0, "p0")
    if not (0.0 < alpha < 1.0):
        raise ValueError(f"alpha must be in (0, 1), got {alpha}")

    # P(X >= k | p0) is non-increasing in k, so binary-search the smallest k whose
    # upper tail is <= alpha. binom_sf_ge is log-gamma based and numerically robust
    # at large n (a direct k=0 PMF recurrence underflows: (1-p0)**n -> 0.0).
    # Bracket: k=0 gives sf=1 > alpha (alpha<1); k=n+1 gives the empty region (size 0).
    lo, hi = 1, n + 1
    while lo < hi:
        mid = (lo + hi) // 2
        if binom_sf_ge(n, mid, p0) <= alpha:
            hi = mid
        else:
            lo = mid + 1
    k_star = lo
    actual_size = binom_sf_ge(n, k_star, p0) if k_star <= n else 0.0
    return {"k_star": k_star, "actual_size": actual_size}


def binomial_power(n: int, p0: float, p1: float, alpha: float) -> dict:
    """Exact power of the level-<=alpha one-sided upper binomial test at p = p1.

    Returns {"power", "k_star", "actual_size"}.
    """
    _validate_n(n)
    _validate_open_prob(p0, "p0")
    _validate_prob(p1, "p1")
    thr = one_sided_rejection_threshold(n, p0, alpha)
    k_star = thr["k_star"]
    if k_star > n:
        power = 0.0  # empty rejection region
    else:
        power = binom_sf_ge(n, k_star, p1)
    return {"power": power, "k_star": k_star, "actual_size": thr["actual_size"]}


def normal_approx_min_n(p0: float, p1: float, alpha: float, power_target: float) -> int:
    """Approximate (NOT exact) minimum N via the normal two-point formula.

    Labelled approximate; used only as a cross-check against the exact search.
    """
    _validate_open_prob(p0, "p0")
    _validate_open_prob(p1, "p1")
    if p1 <= p0:
        return -1
    z_alpha = _z_from_upper_tail(alpha)
    z_beta = _z_from_upper_tail(1.0 - power_target)
    num = z_alpha * math.sqrt(p0 * (1.0 - p0)) + z_beta * math.sqrt(p1 * (1.0 - p1))
    n = (num * num) / ((p1 - p0) ** 2)
    return int(math.ceil(n))


def min_n_for_power(
    p0: float,
    p1: float,
    alpha: float,
    power_target: float,
    max_n: int = DEFAULT_MAX_N,
) -> dict:
    """Smallest integer N in [1, max_n] whose exact one-sided binomial power at p1
    is >= power_target.

    Returns a dict with found/n_star/power/k_star/actual_size. If p1 <= p0 (a
    non-positive effect) or no N within the bound reaches the target,
    found=False and result_label="NOT_DETECTABLE_WITHIN_SEARCH_BOUND".
    """
    _validate_open_prob(p0, "p0")
    _validate_prob(p1, "p1")
    if not (0.0 < alpha < 1.0):
        raise ValueError(f"alpha must be in (0, 1), got {alpha}")
    if not (0.0 < power_target < 1.0):
        raise ValueError(f"power_target must be in (0, 1), got {power_target}")
    _validate_n(max_n, "max_n")

    not_detectable = {
        "found": False,
        "n_star": None,
        "power_at_n_star": None,
        "k_star": None,
        "actual_size": None,
        "max_n": max_n,
        "result_label": "NOT_DETECTABLE_WITHIN_SEARCH_BOUND",
    }
    # A non-positive effect can never become an upper-tail detectable advantage:
    # power equals the test size (<= alpha < power_target) for all N.
    if p1 <= p0:
        return not_detectable

    # Fast bound pre-check: if even max_n cannot reach the target, exhausted.
    if binomial_power(max_n, p0, p1, alpha)["power"] < power_target:
        return not_detectable

    # Scan upward for the smallest qualifying N. Real N* are small (hundreds to a
    # few thousand); the scan stops at the first hit.
    for n in range(1, max_n + 1):
        res = binomial_power(n, p0, p1, alpha)
        if res["power"] >= power_target:
            return {
                "found": True,
                "n_star": n,
                "power_at_n_star": res["power"],
                "k_star": res["k_star"],
                "actual_size": res["actual_size"],
                "max_n": max_n,
                "result_label": "DETECTABLE",
            }
    return not_detectable


# Hardcoded standard-normal upper-tail quantiles (avoids a scipy dependency),
# matching the convention in analysis/p270b_*. Only the values needed here.
_Z_UPPER_TAIL = {
    0.05: 1.6448536269514722,        # one-sided uncorrected alpha
    0.016666666666666666: 2.1280449591106686,  # one-sided Bonferroni alpha (0.05/3)
    0.2: 0.8416212335729143,         # 1 - 0.80 power
    0.1: 1.2815515594457882,         # 1 - 0.90 power
}


def _z_from_upper_tail(q: float) -> float:
    """Standard-normal quantile z with P(Z > z) = q, for the discrete q values
    used by this brief. Raises if an unlisted q is requested (keeps the approx
    cross-check honest and dependency-free)."""
    for key, val in _Z_UPPER_TAIL.items():
        if abs(key - q) < 1e-12:
            return val
    raise ValueError(f"no hardcoded normal quantile for upper-tail q={q}")


# ===========================================================================
# Combinatorics / baseline derivation.
# ===========================================================================
def exact_one_bet_m3plus_p0(pool: int, pick: int) -> float:
    """Exact 1-bet M3+ null probability: P(>=3 main matches) when a single ticket
    of `pick` numbers is compared to `pick` drawn numbers from a `pool`.

    Closed-form hypergeometric: sum_{k=3..pick} C(pick,k) C(pool-pick, pick-k) / C(pool, pick).
    """
    if pick < 0 or pool < pick:
        raise ValueError(f"invalid (pool={pool}, pick={pick})")
    denom = math.comb(pool, pick)
    num = 0
    for k in range(3, pick + 1):
        num += math.comb(pick, k) * math.comb(pool - pick, pick - k)
    return num / denom


def verify_p0_against_committed(tol: float = 5e-7) -> dict:
    """Recompute p0 from (pool, pick) and check it matches the committed P267C
    value within tol. Returns per-lottery {computed, committed, abs_diff, match}."""
    out = {}
    for lt in LOTTERIES:
        spec = LOTTERY_SPECS[lt]
        computed = exact_one_bet_m3plus_p0(spec["pool"], spec["pick"])
        committed = spec["p0_committed"]
        diff = abs(computed - committed)
        out[lt] = {
            "computed": computed,
            "committed": committed,
            "abs_diff": diff,
            "match": diff <= tol,
        }
    return out


# ===========================================================================
# Calendar-horizon conversion.
# ===========================================================================
def draws_per_year(lottery: str) -> float:
    dpw = CADENCE[lottery]["draws_per_week"]
    return dpw * DAYS_PER_YEAR / DAYS_PER_WEEK


def draws_to_years(n_draws: int, lottery: str) -> float:
    return n_draws / draws_per_year(lottery)


def years_to_draws(years: float, lottery: str) -> float:
    return years * draws_per_year(lottery)


# ===========================================================================
# Decision classification (Phase 2).
# ===========================================================================
def classify_decision(
    primary_cells_found: list,
    governed_horizon_years,
    inputs_traceable: bool,
    cadence_traceable: bool,
) -> str:
    """Map traceability + detectability + governance to a permitted classification.

    GO / NO_GO are only permitted when a committed governed horizon exists.
    """
    if not inputs_traceable or not cadence_traceable:
        return "P272B_BLOCKED_UNTRACEABLE_POWER_INPUT"
    if not all(primary_cells_found):
        return "NOT_DETECTABLE_WITHIN_SEARCH_BOUND"
    if governed_horizon_years is None:
        return "POWER_QUANTIFIED_THRESHOLD_NOT_GOVERNED"
    # A governed horizon exists -> compare (not reachable in this brief).
    # GO if every primary cell is detectable within the governed horizon.
    return "PROSPECTIVE_APPLY_POWER_GO"  # pragma: no cover - no governed horizon committed


# ===========================================================================
# Report assembly (pure: returns a dict; no I/O).
# ===========================================================================
def _round(x, nd):
    return None if x is None else round(x, nd)


def build_report(max_n: int = DEFAULT_MAX_N) -> dict:
    p0_check = verify_p0_against_committed()
    inputs_traceable = all(v["match"] for v in p0_check.values())
    cadence_traceable = all(lt in CADENCE for lt in LOTTERIES)

    lottery_inputs = {}
    power_results = {}
    calendar_horizons = {}
    primary_cells_found = []

    for lt in LOTTERIES:
        spec = LOTTERY_SPECS[lt]
        p0 = exact_one_bet_m3plus_p0(spec["pool"], spec["pick"])
        delta = EFFECT_SCENARIO_PP[lt] / 100.0
        p1 = p0 + delta
        lottery_inputs[lt] = {
            "pool_size": spec["pool"],
            "pick_count": spec["pick"],
            "second_zone_size": spec.get("second_zone"),
            "p0_exact": _round(p0, 8),
            "p0_committed_p267c": spec["p0_committed"],
            "p0_match_committed": p0_check[lt]["match"],
            "effect_scenario_pp": EFFECT_SCENARIO_PP[lt],
            "p1": _round(p1, 8),
            "endpoint": CONTRACT["primary_endpoint"],
            "bet_count": CONTRACT["primary_bet_count"],
        }

        dpy = draws_per_year(lt)
        power_results[lt] = {"draws_per_year": _round(dpy, 4)}
        calendar_horizons[lt] = {}

        for alpha_label, alpha in (
            ("alpha_corrected_bonferroni_m3", ALPHA_CORRECTED),
            ("alpha_uncorrected", ALPHA_UNCORRECTED),
        ):
            power_results[lt][alpha_label] = {"alpha": _round(alpha, 8)}
            for tgt in CONTRACT["power_targets"]:
                res = min_n_for_power(p0, p1, alpha, tgt, max_n=max_n)
                approx_n = normal_approx_min_n(p0, p1, alpha, tgt)
                key = f"power_{int(round(tgt * 100))}"
                n_star = res["n_star"]
                years = draws_to_years(n_star, lt) if n_star else None
                cell = {
                    "target_power": tgt,
                    "found": res["found"],
                    "result_label": res["result_label"],
                    "n_star_draws": n_star,
                    "k_star": res["k_star"],
                    "actual_test_size": _round(res["actual_size"], 8),
                    "power_at_n_star": _round(res["power_at_n_star"], 6),
                    "normal_approx_n_crosscheck": approx_n,
                    "calendar_years_required": _round(years, 3),
                    "max_n_search_bound": res["max_n"],
                }
                power_results[lt][alpha_label][key] = cell

                # Calendar-horizon detectability (per corrected-alpha primary view).
                if alpha_label == "alpha_corrected_bonferroni_m3":
                    horizon_flags = {}
                    for h in CONTRACT["calendar_reporting_horizons_years"]:
                        draws_in_h = years_to_draws(h, lt)
                        horizon_flags[str(h)] = bool(n_star is not None and n_star <= draws_in_h)
                    calendar_horizons[lt][key] = {
                        "n_star_draws": n_star,
                        "calendar_years_required": _round(years, 3),
                        "detectable_within_horizon_years": horizon_flags,
                    }
                    # Primary cell = corrected alpha, 80% power.
                    if abs(tgt - 0.80) < 1e-9:
                        primary_cells_found.append(res["found"])

    decision = classify_decision(
        primary_cells_found, GOVERNED_HORIZON_YEARS, inputs_traceable, cadence_traceable
    )

    evidence_manifest = _build_evidence_manifest(lottery_inputs)

    limitations = [
        "POWER FEASIBILITY IS NOT EVIDENCE OF A PREDICTIVE EDGE. This brief only "
        "answers 'how many future draws to detect an effect of magnitude delta'; it "
        "makes no claim that such an effect exists.",
        "Effect scenarios are the committed P267C best uncorrected per-lottery "
        "observed excesses (DAILY_539 +1.32pp / BIG_LOTTO +1.23pp / POWER_LOTTO "
        "+1.48pp). NONE survived Bonferroni or BH-FDR in P267C (0/36 cells); they "
        "are upper-plausible scenario magnitudes, not established edges.",
        "Bet-count nuance: p0 is the exact 1-bet M3+ hypergeometric baseline and the "
        "locked contract fixes primary_bet_count=1, but the committed observed "
        "excesses were measured at the draw-level any-bet endpoint on multi-bet "
        "cells (5/3/4 bets). The excess is applied here as a candidate prospective "
        "1-bet effect magnitude; a true prospective 1-bet stream may exhibit a "
        "different effect size.",
        "The test is exact one-sided upper binomial (detecting excess). P267C/P270B "
        "used two-sided framing; a one-sided test needs no more N than two-sided at "
        "the same per-test alpha, so these N* are not inflated by sidedness.",
        "Draw cadence is derived from the modal weekday set over calendar year 2025 "
        "in the committed P268D1 draw_date field (DAILY_539 6/wk, BIG_LOTTO 2/wk, "
        "POWER_LOTTO 2/wk). Sporadic BIG_LOTTO add-on draws and rare DAILY_539 "
        "Sunday make-ups are excluded from the regular accrual rate; empirical "
        "full-history rates (5.80 / 2.11 / 2.00 per week) and CY2025 counts "
        "(316 / 118 / 104) bound the sensitivity.",
        "No committed governed acceptable detection horizon or deployable threshold "
        "exists; therefore neither GO nor NO_GO is selectable and the decision is "
        "POWER_QUANTIFIED_THRESHOLD_NOT_GOVERNED.",
        "Prospective detection further assumes a stable data-generating process over "
        "the multi-year accrual window and i.i.d. draw-level outcomes; regime drift "
        "or non-stationarity would invalidate the simple binomial model.",
    ]

    report = {
        "task_id": TASK_ID,
        "artifact_date": ARTIFACT_DATE,
        "branch": BRANCH,
        "base_main": BASE_MAIN,
        "mode": "prospective_oos_detectability_power_brief",
        "task_class": "statistical_research_and_artifact",
        # Governance / no-claim flags.
        "production_apply_authorized": False,
        "controlled_apply_started": False,
        "P271M_started": False,
        "P271N_started": False,
        "prediction_success_claim": False,
        "db_opened": False,
        "db_write": False,
        "registry_write": False,
        "network_access": False,
        "subprocess_used": False,
        "migration_or_deployment_or_activation": False,
        "historical_strategy_reselection": False,
        "project_classification": PROJECT_CLASSIFICATION,
        "production_apply_state": "NOT_READY_FOR_APPLY",
        "pre_registered_contract": CONTRACT,
        "alpha_corrected_bonferroni_m3": _round(ALPHA_CORRECTED, 8),
        "alpha_uncorrected": _round(ALPHA_UNCORRECTED, 8),
        "statistical_method": {
            "test": "exact one-sided (upper) binomial test of observed M3+ rate vs p0",
            "exactness": "EXACT_BINOMIAL",
            "exact_method_detail": "log-gamma PMF + forward-recurrence tail summation; not a normal/Poisson approximation",
            "rejection_rule": "reject H0 when X >= k*, where k* is the smallest k with P(X>=k|p0) <= alpha",
            "power_definition": "P(X >= k* | p1)",
            "normal_approx": "reported per cell as normal_approx_n_crosscheck (APPROXIMATE cross-check only)",
            "deterministic": True,
            "seed": CONTRACT["deterministic_seed"],
            "stochastic_component": False,
        },
        "p0_verification": {
            lt: {
                "computed": _round(p0_check[lt]["computed"], 8),
                "committed": p0_check[lt]["committed"],
                "abs_diff": _round(p0_check[lt]["abs_diff"], 10),
                "match": p0_check[lt]["match"],
            }
            for lt in LOTTERIES
        },
        "inputs_traceable": inputs_traceable,
        "cadence_traceable": cadence_traceable,
        "evidence_manifest": evidence_manifest,
        "lottery_inputs": lottery_inputs,
        "cadence": {
            lt: {
                "draws_per_week": CADENCE[lt]["draws_per_week"],
                "weekdays": CADENCE[lt]["weekdays"],
                "draws_per_year": _round(draws_per_year(lt), 4),
                "source_path": P268D1_JSONL,
                "source_sha256": EVIDENCE_SOURCE_SHA256[P268D1_JSONL],
                "derivation": "modal weekday set over calendar year 2025 of committed draw_date field; draws/year = draws_per_week * 365.25/7",
                "status": "CONFIRMED",
            }
            for lt in LOTTERIES
        },
        "power_results": power_results,
        "calendar_horizons": calendar_horizons,
        "governed_horizon": {
            "years": GOVERNED_HORIZON_YEARS,
            "search_result": GOVERNED_HORIZON_SEARCH_RESULT,
            "searched_paths": ["00-Plan/", "docs/", "outputs/research/"],
        },
        "decision_classification": decision,
        "allowed_decision_classifications": list(ALLOWED_DECISIONS),
        "success_classification": SUCCESS_CLASSIFICATION,
        "test_execution": TEST_EXECUTION,
        "limitations": limitations,
    }
    return report


def _build_evidence_manifest(lottery_inputs: dict) -> list:
    """Decisive-input evidence manifest (Phase 1): source/sha/field/value/method/status."""
    m = []
    m.append({
        "input": "lottery_pool_and_pick",
        "source_path": LOTTERY_CLAUDE_MD,
        "source_sha256": EVIDENCE_SOURCE_SHA256[LOTTERY_CLAUDE_MD],
        "field": "header line '大樂透 (1-49選6) | 威力彩 (1-38選6)' + DAILY_539 5/39 convention",
        "value": "DAILY_539=5/39, BIG_LOTTO=6/49, POWER_LOTTO=6/38 first zone (+1/8 second zone)",
        "derivation": "documented pool/pick; cross-checked by recomputing p0 (hypergeometric) == committed P267C value",
        "status": "CONFIRMED",
    })
    m.append({
        "input": "p265a_m3plus_endpoint_definition",
        "source_path": P265A_MD,
        "source_sha256": EVIDENCE_SOURCE_SHA256[P265A_MD],
        "field": "draw_success_rule / success_metric",
        "value": "draw-level any-bet hit_count>=3; special_hit excluded; denominator=distinct target_draw",
        "derivation": "quoted verbatim from committed P265A artifact (corroborated by P267C success_metric)",
        "status": "CONFIRMED",
    })
    for lt in LOTTERIES:
        m.append({
            "input": f"p0_one_bet_null_{lt}",
            "source_path": P267C_JSON,
            "source_sha256": EVIDENCE_SOURCE_SHA256[P267C_JSON],
            "field": f"one_bet_baseline_sanity.{lt}.exact",
            "value": LOTTERY_SPECS[lt]["p0_committed"],
            "derivation": "exact hypergeometric P(>=3) recomputed here from (pool,pick) and matched to committed value within 5e-7",
            "status": "CONFIRMED",
        })
    for lt in LOTTERIES:
        m.append({
            "input": f"effect_scenario_observed_excess_{lt}",
            "source_path": P270B_JSON,
            "source_sha256": EVIDENCE_SOURCE_SHA256[P270B_JSON],
            "field": f"mde_summary.{lt}.p267c_best_uncorrected_excess_pp",
            "value": EFFECT_SCENARIO_PP[lt],
            "derivation": "P267C best uncorrected per-lottery observed excess (committed in P270B and P267C results table); NOT correction-surviving",
            "status": "CONFIRMED",
        })
    m.append({
        "input": "p270b_mde_power_findings",
        "source_path": P270B_JSON,
        "source_sha256": EVIDENCE_SOURCE_SHA256[P270B_JSON],
        "field": "mde_summary.{lottery}.{n,alpha,power,z_alpha_2,z_beta,mde_increment_pp_*}",
        "value": "n=1000, alpha=0.0167, power=0.80, z_alpha_2=2.3934, z_beta=0.8416 (two-proportion portfolio MDE)",
        "derivation": "prior committed power finding; complementary two-proportion MDE, distinct from this one-sample binomial N*",
        "status": "CONFIRMED",
    })
    m.append({
        "input": "draw_cadence",
        "source_path": P268D1_JSONL,
        "source_sha256": EVIDENCE_SOURCE_SHA256[P268D1_JSONL],
        "field": "draw_date (per record, all 5 games, 2007..2026)",
        "value": "DAILY_539 6/wk (Mon-Sat), BIG_LOTTO 2/wk (Tue,Fri), POWER_LOTTO 2/wk (Mon,Thu)",
        "derivation": "reproducibly derived: modal weekday set over CY2025 of committed draw_date; no production DB access",
        "status": "CONFIRMED",
    })
    m.append({
        "input": "governed_acceptable_horizon",
        "source_path": "00-Plan/, docs/, outputs/research/ (bounded search)",
        "source_sha256": None,
        "field": "n/a",
        "value": GOVERNED_HORIZON_SEARCH_RESULT,
        "derivation": "bounded rg search found no committed governed acceptable horizon or deployable threshold",
        "status": "CONFIRMED_ABSENT",
    })
    m.append({
        "input": "family_alpha_and_correction",
        "source_path": "locked_contract (this artifact) + P270B alpha=0.0167 cross-check",
        "source_sha256": None,
        "field": "family_alpha / Bonferroni m",
        "value": "family alpha=0.05; Bonferroni m=3 -> per-test 0.016667 (P270B used rounded 0.0167)",
        "derivation": "pre-registered contract; corroborated by committed P270B alpha",
        "status": "CONFIRMED",
    })
    return m


# ===========================================================================
# Markdown rendering (pure; values pulled from the report so MD == JSON).
# ===========================================================================
def render_markdown(report: dict) -> str:
    L = []
    L.append("# P272B — Prospective OOS Detectability & Apply Go/No-Go Power Brief")
    L.append("")
    L.append(f"- **Task ID:** `{report['task_id']}`")
    L.append(f"- **Artifact date:** {report['artifact_date']}")
    L.append(f"- **Branch:** `{report['branch']}` (base main `{report['base_main']}`)")
    L.append(f"- **Decision classification:** `{report['decision_classification']}`")
    L.append(f"- **Project classification:** `{report['project_classification']}`")
    L.append(f"- **Production apply:** `{report['production_apply_state']}`")
    L.append("")
    L.append("> **Power feasibility is NOT evidence of a predictive edge.** This brief "
             "quantifies the future-draw sample size required to detect a historically "
             "observed M3+ excess at the pre-registered alpha/power; it makes no claim "
             "that such an edge exists. Every effect scenario failed multiplicity "
             "correction in P267C (0/36).")
    L.append("")

    L.append("## Pre-registered contract")
    c = report["pre_registered_contract"]
    L.append(f"- Lotteries: {', '.join(c['lotteries'])}")
    L.append(f"- Primary endpoint: {c['primary_endpoint']}")
    L.append(f"- Primary bet count: {c['primary_bet_count']}")
    L.append(f"- Test: exact one-sided (upper) binomial — `{report['statistical_method']['exactness']}` "
             f"({report['statistical_method']['exact_method_detail']})")
    L.append(f"- Power targets: {c['power_targets']}")
    L.append(f"- Family alpha: {c['family_alpha']}; correction: {c['primary_correction']} m={c['primary_correction_m']} "
             f"-> per-test corrected alpha = {report['alpha_corrected_bonferroni_m3']}; uncorrected = {report['alpha_uncorrected']}")
    L.append(f"- BH-FDR: {c['bh_fdr']}; seed: {c['deterministic_seed']} (no stochastic component)")
    L.append(f"- Calendar horizons (years): {c['calendar_reporting_horizons_years']}")
    L.append("")

    L.append("## Decisive inputs (per lottery)")
    L.append("")
    L.append("| Lottery | pool/pick | p0 (exact 1-bet M3+) | committed P267C | match | effect δ (pp) | p1 | draws/week | draws/year |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for lt in report["pre_registered_contract"]["lotteries"]:
        li = report["lottery_inputs"][lt]
        cad = report["cadence"][lt]
        L.append(
            f"| {lt} | {li['pool_size']}/{li['pick_count']} | {li['p0_exact']} | "
            f"{li['p0_committed_p267c']} | {li['p0_match_committed']} | {li['effect_scenario_pp']} | "
            f"{li['p1']} | {cad['draws_per_week']} | {cad['draws_per_year']} |"
        )
    L.append("")

    L.append("## Minimum prospective sample size N* (exact one-sided binomial)")
    L.append("")
    L.append("Corrected alpha = Bonferroni m=3 (per-test); N* = smallest future-draw count whose exact power >= target.")
    L.append("")
    L.append("| Lottery | alpha | power target | N* (draws) | k* | actual size | power@N* | normal-approx N | calendar years |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for lt in report["pre_registered_contract"]["lotteries"]:
        for alpha_label in ("alpha_corrected_bonferroni_m3", "alpha_uncorrected"):
            blk = report["power_results"][lt][alpha_label]
            alpha = blk["alpha"]
            for tgt in report["pre_registered_contract"]["power_targets"]:
                key = f"power_{int(round(tgt * 100))}"
                cell = blk[key]
                L.append(
                    f"| {lt} | {alpha} | {cell['target_power']} | {cell['n_star_draws']} | "
                    f"{cell['k_star']} | {cell['actual_test_size']} | {cell['power_at_n_star']} | "
                    f"{cell['normal_approx_n_crosscheck']} | {cell['calendar_years_required']} |"
                )
    L.append("")

    L.append("## Calendar-horizon detectability (corrected alpha)")
    L.append("")
    L.append("| Lottery | power target | N* (draws) | years required | within 1y | within 3y | within 5y | within 10y |")
    L.append("|---|---|---|---|---|---|---|---|")
    for lt in report["pre_registered_contract"]["lotteries"]:
        for tgt in report["pre_registered_contract"]["power_targets"]:
            key = f"power_{int(round(tgt * 100))}"
            ch = report["calendar_horizons"][lt][key]
            f = ch["detectable_within_horizon_years"]
            L.append(
                f"| {lt} | {tgt} | {ch['n_star_draws']} | {ch['calendar_years_required']} | "
                f"{f['1']} | {f['3']} | {f['5']} | {f['10']} |"
            )
    L.append("")

    L.append("## Governed-horizon search")
    gh = report["governed_horizon"]
    L.append(f"- Result: `{gh['search_result']}`")
    L.append(f"- Searched: {', '.join(gh['searched_paths'])}")
    L.append(f"- Governed horizon (years): {gh['years']}")
    L.append("")
    L.append(f"Because no committed governed acceptable horizon or deployable threshold exists, "
             f"neither GO nor NO_GO is selectable. **Decision: `{report['decision_classification']}`.**")
    L.append("")

    L.append("## Evidence manifest (decisive inputs)")
    L.append("")
    L.append("| Input | Source | SHA-256 | Field | Value | Status |")
    L.append("|---|---|---|---|---|---|")
    for e in report["evidence_manifest"]:
        sha = e["source_sha256"] or "—"
        sha_disp = (sha[:16] + "…") if e["source_sha256"] else "—"
        val = str(e["value"]).replace("|", "\\|")
        field = str(e["field"]).replace("|", "\\|")
        L.append(f"| {e['input']} | `{e['source_path']}` | `{sha_disp}` | {field} | {val} | {e['status']} |")
    L.append("")

    L.append("## Statistical & calendar limitations")
    for lim in report["limitations"]:
        L.append(f"- {lim}")
    L.append("")

    L.append("## Tests actually run")
    te = report["test_execution"]
    L.append(f"- Focused: `{te['focused_command']}` → **{te['focused_result']}**")
    L.append(f"- Regression P267C: **{te['regression_p267c']}**")
    L.append(f"- Regression P270B: **{te['regression_p270b']}**")
    L.append(f"- Regression P271L (preflight): **{te['regression_p271l_preflight']}**")
    L.append(f"- Regression P271L (readonly schema): **{te['regression_p271l_readonly_schema']}**")
    L.append(f"- Full repository suite: **{te['full_repository_suite']}**")
    L.append(f"- git diff --check: **{te['git_diff_check']}**; static forbidden-interface scan: **{te['static_forbidden_interface_scan']}**")
    L.append(f"- JSON parse: **{te['json_parse_validation']}**; deterministic regeneration: **{te['deterministic_regeneration']}**; "
             f"MD/JSON consistency: **{te['markdown_json_consistency']}**")
    L.append("")

    L.append("## Governance assertions")
    L.append(f"- production_apply_authorized = {report['production_apply_authorized']}")
    L.append(f"- controlled_apply_started = {report['controlled_apply_started']}")
    L.append(f"- P271M_started = {report['P271M_started']}")
    L.append(f"- P271N_started = {report['P271N_started']}")
    L.append(f"- prediction_success_claim = {report['prediction_success_claim']}")
    L.append(f"- db_opened = {report['db_opened']}; db_write = {report['db_write']}; registry_write = {report['registry_write']}")
    L.append("")
    L.append(f"_Success classification: `{report['success_classification']}`._")
    L.append("")
    return "\n".join(L)


# ===========================================================================
# Artifact writers (only invoked from __main__ — no import-time writes).
# ===========================================================================
def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def write_artifacts(out_dir: Path | None = None) -> tuple:
    report = build_report()
    md = render_markdown(report)
    root = out_dir if out_dir is not None else (_repo_root() / "outputs" / "research")
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / f"p272b_prospective_oos_detectability_power_{ARTIFACT_DATE.replace('-', '')}.json"
    md_path = root / f"p272b_prospective_oos_detectability_power_{ARTIFACT_DATE.replace('-', '')}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(md, encoding="utf-8")
    return json_path, md_path


def main() -> None:
    json_path, md_path = write_artifacts()
    print(f"wrote {json_path}")
    print(f"wrote {md_path}")
    rep = build_report()
    print(f"decision_classification = {rep['decision_classification']}")
    for lt in LOTTERIES:
        cell = rep["power_results"][lt]["alpha_corrected_bonferroni_m3"]["power_80"]
        print(f"  {lt}: N*(80%,corrected) = {cell['n_star_draws']} draws "
              f"({cell['calendar_years_required']} yr)")


if __name__ == "__main__":
    main()
