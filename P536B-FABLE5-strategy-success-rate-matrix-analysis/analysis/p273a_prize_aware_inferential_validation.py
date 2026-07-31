"""P273A — Prize-Aware Inferential Validation (primary windows 50/300/750).

Primary research question
-------------------------
Do any already-frozen strategies show a statistically credible prize-aware
advantage over the governed random baseline, on the draw-level any-bet
prize-aware success endpoint, under the OWNER-APPROVED primary decision policy
of three nested windows 50 (SHORT) / 300 (MID) / 750 (LONG) distinct target
draws?

What this module IS
-------------------
* A self-contained, import-safe, deterministic statistical engine that:
  - encodes the frozen prize-aware endpoints EXACTLY as traced from committed
    P271A evidence (no redefinition from memory);
  - computes the EXACT analytic random baseline per lottery from official
    lottery rules, modelling the BIG_LOTTO special number and POWER_LOTTO
    second zone JOINTLY with the main-number hit count (independence is only
    assumed where it is structurally proven — see notes);
  - consumes the IMMUTABLE committed observed-counts artifact for the primary
    windows (50/300/750) and the IMMUTABLE distinct-ticket identity artifact —
    it NEVER opens the production database;
  - uses the exact without-replacement null for N distinct ticket identities:
    q_N = 1 - C(T-W,N)/C(T,N);
  - runs the full per-cell inference (exact one-sided binomial upper tail when
    the per-draw null probability is constant, exact deterministic
    Poisson-binomial upper tail when it varies by bet count, Wilson + exact
    Clopper-Pearson confidence intervals, Bonferroni family correction over the
    fixed family m = 108, Benjamini-Hochberg FDR as descriptive-only);
  - applies the OWNER-PRE-REGISTERED 10-point STABILITY rule at the
    strategy x lottery group level across the three nested windows.

Pre-registration / hard ordering
--------------------------------
The minimum-support rule (>= 30 support draws AND >= 5 expected successes) and
the full STABILITY rule are frozen as module constants BEFORE any outcome is
read, and are mirrored in the focused tests and in the emitted JSON/Markdown
methodology. No window may be removed and no threshold/family may be changed
after outcomes are observed. SHORT-50 is a recent-direction guardrail and can
NEVER independently trigger a correction-surviving edge or a GO candidate.

What this module is NOT / hard constraints
------------------------------------------
* It NEVER opens, queries, copies, or writes the production SQLite database
  ``lottery_api/data/lottery_v2.db``. It contains zero DB / network /
  subprocess / registry interface (no ``sqlite3``, ``urllib``, ``requests``,
  ``subprocess``, ``socket`` imports; no registry import). Verified by a static
  scan test. It reads only the three committed research artifacts named above
  and immutable source files whose SHA-256 values are recorded in the report.
* It performs NO strategy reselection, NO feature mining, NO prospective
  activation, NO production apply, NO controlled apply / migration / deploy.
* It does NOT modify either observed-counts artifact, the export module, the
  export tests, the scorer, or any package / CI configuration.

Scientific framing
-------------------
Retrospective research only. A descriptive observed rate is NOT evidence of a
predictive edge. NULL and INSUFFICIENT_SUPPORT are valid, successful results.
Nothing here authorizes production apply, prospective activation, strategy
reselection, or P273B. GO_CANDIDATE_RESEARCH_ONLY (if it ever arises) is a
research label only and is NOT deployment authorization. The 1500-draw and
all-history horizons are REFERENCE-ONLY and may never drive a primary decision.

Traceable source provenance (SHA-256, recorded at task time)
------------------------------------------------------------
* Primary obs : outputs/research/p273a_primary_window_observed_counts_20260615.json
                canonical_payload_digest
                65a4cc59f5ab64d685890566e38493b0295e622f351e0527782f1dce2f38645f
* Reference   : outputs/research/p273a_prizeaware_observed_counts_20260614.json
  (100/500/1500, reference-only)
                canonical_payload_digest
                859c3889f2c698a27d16caf4195bbd0fd032cad80d8c44e990958658624b3103
* Endpoints   : outputs/research/p271a_prize_aware_endpoint_scoring_spec_20260611.md
                sha256 6c598b38b19bae1d1c2097a1c2d9d946351ea31a2e87b6b1d34b576d7bf5eb04
                outputs/research/p271a_prize_aware_endpoint_scoring_spec_20260611.json
                sha256 73517f8be239a5638489b1b6291e2bb6a382b59be82d353e63916472939329ab
* Strategy    : outputs/research/p267c_m3plus_strategy_revalidation_20260610.json
  cell set      sha256 3769596df51f6eaab5ef98cdf799ba9915f0c0349810f0899a7516004639a241
* Scorer      : lottery_api/prize_aware_scorer.py (P271C, scoring_version prize_aware_v1)

This task did not open any production DB; SHA-256 values are recorded for
provenance only.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
from collections import Counter
from typing import Dict, List, Optional, Sequence, Tuple

# --------------------------------------------------------------------------- #
# Frozen task identity / pre-registration constants                           #
# --------------------------------------------------------------------------- #

TASK_ID = "P273A_EXACT_DISTINCT_TICKET_PRIZE_AWARE_INFERENCE"
GENERATED_DATE = "2026-06-15"  # fixed (not a live clock) -> deterministic regen
BRANCH = "task/p273a-prize-aware-inferential-validation"
BASE_ORIGIN_MAIN = "63452e7d589739b5ec3eb58035e7b8aff9014639"
IDENTITY_EXPORT_COMMIT = "be6365da947922807c1e302a296400661287beab"
IDENTITY_MERGE_COMMIT = "63452e7d589739b5ec3eb58035e7b8aff9014639"
MODE = "exact_distinct_ticket_prize_aware_inferential_validation"
ARTIFACT_VERSION = "p273a_exact_distinct_ticket_inference_v2"
POLICY_VERSION = "primary_window_policy_v1_50_300_750"

LOTTERIES: Tuple[str, ...] = ("DAILY_539", "BIG_LOTTO", "POWER_LOTTO")

# Owner-approved primary decision windows (frozen). The labels are part of the
# pre-registration: SHORT is a guardrail; MID and LONG carry promotion power.
PRIMARY_WINDOWS: Tuple[int, ...] = (50, 300, 750)
PRIMARY_WINDOW_LABELS: Dict[int, str] = {50: "SHORT", 300: "MID", 750: "LONG"}
WINDOW_ORDER: Tuple[str, ...] = ("SHORT", "MID", "LONG")

# Reference-only horizons: excluded from every primary decision. Recorded so the
# containment is explicit and testable.
REFERENCE_ONLY_WINDOWS: Tuple[int, ...] = (100, 500, 1500)
REFERENCE_ONLY_DESCRIPTIONS: Tuple[str, ...] = (
    "1500 draws",
    "all-history frequency or distribution",
    "any longer-horizon aggregate not in 50 / 300 / 750",
    "the previous 100/500/1500 observed-counts artifact",
)
REFERENCE_ONLY_PROHIBITED_USES: Tuple[str, ...] = (
    "strategy_promotion",
    "strategy_elimination",
    "stability_pass_or_fail",
    "go_recommendation",
    "production_deployment_screening",
)
# Windows that must NEVER appear as a primary decision input.
FORBIDDEN_PRIMARY_WINDOWS = frozenset({100, 500, 1500})

ANALYSIS_UNIT = "distinct_target_draw"
OUTCOME = "draw-level any-bet prize-aware success"
FAMILY_ALPHA = 0.05
BH_FDR_Q = 0.10

# --------------------------------------------------------------------------- #
# Source provenance (recorded; never opened for write)                        #
# --------------------------------------------------------------------------- #

PRIMARY_OBSERVED_COUNTS_PATH = "outputs/research/p273a_primary_window_observed_counts_20260615.json"
PRIMARY_OBSERVED_COUNTS_DIGEST = "65a4cc59f5ab64d685890566e38493b0295e622f351e0527782f1dce2f38645f"
PRIMARY_OBSERVED_COUNTS_RAW_SHA = "14b2ed29628111f32925909ba07e9be0b3de48a04ee4b0877e39c1dfa4e51b73"
IDENTITY_ARTIFACT_PATH = "outputs/research/p273a_distinct_ticket_identity_20260615.json"
IDENTITY_ARTIFACT_DIGEST = "ad85e447dfc7db7afd70e9fdde928bb12a2ae367d6c1f23f14b7e3504701ae51"
IDENTITY_ARTIFACT_RAW_SHA = "b10b916c00f807ace7342250b788dbf1d62c12a0b8e2d5aa627b5a4eb25089b0"
REFERENCE_OBSERVED_COUNTS_PATH = "outputs/research/p273a_prizeaware_observed_counts_20260614.json"
REFERENCE_OBSERVED_COUNTS_DIGEST = "859c3889f2c698a27d16caf4195bbd0fd032cad80d8c44e990958658624b3103"
REFERENCE_OBSERVED_COUNTS_RAW_SHA = "ee5cc98a4c0b673e1172d4478e72bced50167e7f206acf25fe170eee0ece7bd9"

ENDPOINT_SOURCE_MD = "outputs/research/p271a_prize_aware_endpoint_scoring_spec_20260611.md"
ENDPOINT_SOURCE_MD_SHA = "6c598b38b19bae1d1c2097a1c2d9d946351ea31a2e87b6b1d34b576d7bf5eb04"
ENDPOINT_SOURCE_JSON = "outputs/research/p271a_prize_aware_endpoint_scoring_spec_20260611.json"
ENDPOINT_SOURCE_JSON_SHA = "73517f8be239a5638489b1b6291e2bb6a382b59be82d353e63916472939329ab"
STRATEGY_CELL_SOURCE = "outputs/research/p267c_m3plus_strategy_revalidation_20260610.json"
STRATEGY_CELL_SOURCE_SHA = "3769596df51f6eaab5ef98cdf799ba9915f0c0349810f0899a7516004639a241"
SCORER_SOURCE = "lottery_api/prize_aware_scorer.py"
ADAPTER_SOURCE = "lottery_api/prize_aware_replay_adapter.py"
IDENTITY_EXPORT_SOURCE = "analysis/p273a_distinct_ticket_identity_export.py"
PRIMARY_EXPORT_SOURCE = "analysis/p273a_primary_window_observed_counts_export.py"
INFERENCE_SOURCE = "analysis/p273a_prize_aware_inferential_validation.py"
PRODUCTION_DB_PATH = "lottery_api/data/lottery_v2.db"  # named only to assert it is NEVER opened

# Volatile keys excluded from the canonical-payload digest of the observed-counts
# artifact (must mirror the export module so the digest reproduces exactly).
_OBS_VOLATILE_KEYS = frozenset({
    "generated_at", "transaction_start_at", "transaction_end_at",
    "canonical_payload_digest", "source_db_path", "connection_uri",
})

# --------------------------------------------------------------------------- #
# Pre-registered gates (frozen BEFORE any outcome is read)                     #
# --------------------------------------------------------------------------- #

MIN_SUPPORT_DRAWS = 30          # below this -> PRIZE_AWARE_INSUFFICIENT_SUPPORT
MIN_EXPECTED_SUCCESSES = 5.0    # support * baseline below this -> insufficient

# Fixed Bonferroni family: 36 frozen strategy x lottery cells x 3 primary windows.
EXPECTED_FROZEN_CELL_COUNT = 36
CORRECTION_FAMILY_M = EXPECTED_FROZEN_CELL_COUNT * len(PRIMARY_WINDOWS)  # 108

# Owner pre-registered STABILITY rule, evaluated at the strategy x lottery group
# level across the three nested primary windows. Frozen as data so the focused
# tests, the JSON methodology, and the Markdown methodology all reference one
# canonical definition.
STABILITY_RULE: Dict[str, object] = {
    "evaluation_level": "strategy_x_lottery group across SHORT(50)/MID(300)/LONG(750)",
    "family_m_fixed": CORRECTION_FAMILY_M,
    "criteria": [
        "1. All three primary windows pass the minimum-support rule and are evaluable.",
        "2. MID-300 absolute excess is strictly greater than 0.",
        "3. LONG-750 absolute excess is strictly greater than 0.",
        "4. SHORT-50 absolute excess is greater than or equal to 0.",
        "5. At least one of MID-300 or LONG-750 has Bonferroni-corrected "
        "p-value <= 0.05 using the fixed family m=108.",
        "6. SHORT-50 alone can never trigger correction-surviving edge or "
        "GO-candidate classification.",
        "7. Any primary window that is significantly negative, "
        "insufficient-support, or unevaluable causes STABILITY_FAIL.",
        "8. No window may be removed and no threshold/family may be changed "
        "after outcomes are observed.",
        "9. The three nested windows represent cross-timescale directional "
        "consistency, not independent replications.",
        "10. Passing stability creates at most a research GO candidate; it does "
        "not authorize production apply.",
    ],
}

# --------------------------------------------------------------------------- #
# Official lottery rules (game geometry only; no prize amounts)               #
# --------------------------------------------------------------------------- #

GAME_RULES: Dict[str, Dict[str, object]] = {
    "DAILY_539": {
        "main_pool": 39, "main_pick": 6 - 1, "main_drawn": 5,  # pick 5 of 1..39
        "has_special": False, "special_kind": None,
    },
    "BIG_LOTTO": {
        "main_pool": 49, "main_pick": 6, "main_drawn": 6,      # pick 6 of 1..49
        "has_special": True, "special_kind": "from_remaining",  # special from the other 43
        "special_remaining": 43,
    },
    "POWER_LOTTO": {
        "main_pool": 38, "main_pick": 6, "main_drawn": 6,      # first zone: pick 6 of 1..38
        "has_special": True, "special_kind": "independent_zone",
        "second_zone_size": 8,                                  # second zone: 1 of 1..8
    },
}

# Frozen prize-aware endpoints, traced verbatim from P271A (see module docstring).
ENDPOINTS: Dict[str, Dict[str, str]] = {
    "DAILY_539": {
        "name": "D539_ANY_PRIZE_AWARE_WIN",
        "condition": "hit_count >= 2",
        "covers": "肆獎(2)+參獎(3)+貳獎(4)+頭獎(5); identical to D539_M2_PLUS",
        "special_role": "none (no special number / no second zone)",
    },
    "BIG_LOTTO": {
        "name": "BIG_ANY_PRIZE_AWARE_WIN",
        "condition": "hit_count >= 3 OR (hit_count == 2 AND special_hit == 1)",
        "covers": "all 8 tiers incl. 普獎 (M2 + special)",
        "special_role": "special_hit = actual_special IN predicted_numbers (always computable)",
    },
    "POWER_LOTTO": {
        "name": "POWER_ANY_PRIZE_AWARE_WIN",
        "condition": "hit_count >= 3 OR (hit_count >= 1 AND special_hit == 1)",
        "covers": "all 10 tiers incl. 捌獎 (M2+second) and 普獎 (M1+second)",
        "special_role": "special_hit = predicted_second_zone == actual_second_zone",
    },
}

# Frozen strategy x lottery cells — the committed P267C replay-backed universe
# (36 cells). Cross-checked against the primary observed-counts artifact.
FROZEN_STRATEGY_CELLS: Dict[str, Tuple[str, ...]] = {
    "BIG_LOTTO": (
        "bet2_fourier_expansion_biglotto", "biglotto_deviation_2bet",
        "biglotto_echo_aware_3bet", "biglotto_triple_strike",
        "biglotto_ts3_markov_4bet_w30", "cold_complement_biglotto",
        "coldpool15_biglotto", "fourier30_markov30_biglotto",
        "markov_2bet_biglotto", "markov_single_biglotto", "ts3_regime_3bet",
    ),
    "DAILY_539": (
        "539_3bet_orthogonal", "acb_1bet", "acb_markov_midfreq",
        "acb_markov_midfreq_3bet", "acb_single_539", "daily539_f4cold",
        "daily539_f4cold_3bet", "daily539_f4cold_5bet", "daily539_markov_cold",
        "markov_1bet_539", "midfreq_acb_2bet", "midfreq_fourier_2bet",
        "p0b_539_3bet_f_cold_fmid", "p0c_539_3bet_f_cold_x2", "zone_gap_3bet_539",
    ),
    "POWER_LOTTO": (
        "cold_complement_2bet", "fourier30_markov30_2bet", "fourier_rhythm_3bet",
        "midfreq_fourier_2bet", "midfreq_fourier_mk_3bet",
        "power_fourier_rhythm_2bet", "power_orthogonal_5bet",
        "power_precision_3bet", "pp3_freqort_4bet", "zonal_entropy_2bet",
    ),
}


# --------------------------------------------------------------------------- #
# Combinatorial helpers                                                       #
# --------------------------------------------------------------------------- #

def hypergeometric_pmf(pool: int, drawn: int, pick: int, k: int) -> float:
    """P(exactly k of the `pick` chosen numbers are among the `drawn` winners).

    Sampling `pick` numbers without replacement from `pool`, with `drawn`
    winning numbers. Exact rational evaluated as a float via math.comb.
    """
    if k < 0 or k > pick or k > drawn:
        return 0.0
    if pick - k > pool - drawn:
        return 0.0
    return (math.comb(drawn, k) * math.comb(pool - drawn, pick - k)) / math.comb(pool, pick)


def main_hit_distribution(lottery: str) -> List[float]:
    """Full P(hit_count = k) distribution for k = 0..main_pick (main numbers only)."""
    r = GAME_RULES[lottery]
    pool, drawn, pick = int(r["main_pool"]), int(r["main_drawn"]), int(r["main_pick"])
    return [hypergeometric_pmf(pool, drawn, pick, k) for k in range(pick + 1)]


# --------------------------------------------------------------------------- #
# Exact analytic random baselines (per ticket), with JOINT special modelling  #
# --------------------------------------------------------------------------- #

def daily539_ticket_baseline() -> Dict[str, float]:
    """D539 prize-aware = hit_count >= 2. No special number."""
    total = math.comb(39, 5)
    winning = sum(
        math.comb(5, k) * math.comb(34, 5 - k)
        for k in range(2, 6)
    )
    pmf = main_hit_distribution("DAILY_539")
    p = winning / total
    return {
        "total_ticket_identities": total,
        "winning_ticket_identities": winning,
        "ticket_baseline": p,
        "p_hit2": pmf[2], "p_hit3": pmf[3], "p_hit4": pmf[4], "p_hit5": pmf[5],
        "independence_assumed": False,
        "joint_note": "no special/second zone; pure main-number hypergeometric",
    }


def big_lotto_ticket_baseline() -> Dict[str, float]:
    """BIG prize-aware = hit>=3 OR (hit==2 AND special_hit).

    special_hit = actual_special IN predicted_numbers. The special ball is
    drawn uniformly from the 43 NON-main balls, so given hit_count == h the
    ticket holds (6 - h) of those 43 balls => P(special_hit | hit==h) = (6-h)/43.
    The special is therefore NOT independent of the main hit count; we model the
    conditional exactly (no independence assumption).
    """
    total = math.comb(49, 6)
    main_three_plus = sum(
        math.comb(6, k) * math.comb(43, 6 - k)
        for k in range(3, 7)
    )
    hit_two_plus_special = math.comb(6, 2) * math.comb(42, 3)
    winning = main_three_plus + hit_two_plus_special
    pmf = main_hit_distribution("BIG_LOTTO")
    p_hit3_plus = sum(pmf[3:])
    remaining = int(GAME_RULES["BIG_LOTTO"]["special_remaining"])  # 43
    p_special_given_hit2 = (6 - 2) / remaining  # 4/43
    p_hit2_and_special = pmf[2] * p_special_given_hit2
    p = winning / total
    return {
        "total_ticket_identities": total,
        "winning_ticket_identities": winning,
        "winning_main_three_plus_identities": main_three_plus,
        "winning_hit_two_plus_special_identities": hit_two_plus_special,
        "ticket_baseline": p,
        "p_hit3_plus": p_hit3_plus,
        "p_hit2": pmf[2],
        "p_special_given_hit2": p_special_given_hit2,
        "p_hit2_and_special": p_hit2_and_special,
        "independence_assumed": False,
        "joint_note": "special drawn from remaining 43; P(special|hit=h)=(6-h)/43 (conditional, exact)",
    }


def power_lotto_ticket_baseline() -> Dict[str, float]:
    """POWER prize-aware = hit>=3 OR (hit>=1 AND second_hit).

    The second zone is a SEPARATE draw (1 of 1..8) from an independent pool;
    second_hit = predicted_second == actual_second has probability 1/8 and is
    structurally independent of the first-zone hit count (different balls,
    different draw). Independence is therefore PROVEN here, not assumed for
    convenience. The disjoint decomposition:
        win = (hit>=3) OR (1<=hit<=2 AND second_hit)
            = P(hit>=3) + (P(hit==1)+P(hit==2)) * (1/8)
    """
    total = math.comb(38, 6) * 8
    main_three_plus = 8 * sum(
        math.comb(6, k) * math.comb(32, 6 - k)
        for k in range(3, 7)
    )
    low_hits_plus_second = (
        math.comb(6, 1) * math.comb(32, 5)
        + math.comb(6, 2) * math.comb(32, 4)
    )
    winning = main_three_plus + low_hits_plus_second
    pmf = main_hit_distribution("POWER_LOTTO")
    p_hit3_plus = sum(pmf[3:])
    zone = int(GAME_RULES["POWER_LOTTO"]["second_zone_size"])  # 8
    p_second = 1.0 / zone
    p_low_and_second = (pmf[1] + pmf[2]) * p_second
    p = winning / total
    return {
        "total_ticket_identities": total,
        "winning_ticket_identities": winning,
        "winning_main_three_plus_identities": main_three_plus,
        "winning_low_hits_plus_second_identities": low_hits_plus_second,
        "ticket_baseline": p,
        "p_hit3_plus": p_hit3_plus,
        "p_hit1": pmf[1], "p_hit2": pmf[2],
        "p_second": p_second,
        "p_low_and_second": p_low_and_second,
        "independence_assumed": True,
        "joint_note": "second zone is a separate independent draw; P(second)=1/8 proven-independent of first-zone hits",
    }


def analytic_ticket_baseline(lottery: str) -> Dict[str, float]:
    return {
        "DAILY_539": daily539_ticket_baseline,
        "BIG_LOTTO": big_lotto_ticket_baseline,
        "POWER_LOTTO": power_lotto_ticket_baseline,
    }[lottery]()


def ticket_universe(lottery: str) -> Tuple[int, int]:
    baseline = analytic_ticket_baseline(lottery)
    return (
        int(baseline["total_ticket_identities"]),
        int(baseline["winning_ticket_identities"]),
    )


def exact_distinct_draw_baseline(total: int, winning: int, n_tickets: int) -> float:
    """Exact P(at least one win) for distinct tickets sampled without replacement."""
    if not 0 < winning < total:
        raise ValueError("require 0 < winning < total")
    if not 1 <= n_tickets <= total:
        raise ValueError("n_tickets must be in [1, total]")
    if n_tickets == 1:
        return winning / total
    if n_tickets > total - winning:
        return 1.0
    log_no_win = math.fsum(
        math.log1p(-winning / (total - i))
        for i in range(n_tickets)
    )
    return -math.expm1(log_no_win)


def independent_draw_baseline(ticket_p: float, n_tickets: int) -> float:
    """Rejected independent-with-replacement approximation, diagnostic only."""
    if n_tickets < 1:
        raise ValueError("n_tickets must be >= 1")
    if n_tickets == 1:
        return ticket_p
    return 1.0 - (1.0 - ticket_p) ** n_tickets


def null_probability_diagnostic(lottery: str, n_tickets: int) -> Dict[str, float]:
    total, winning = ticket_universe(lottery)
    ticket_p = winning / total
    exact = exact_distinct_draw_baseline(total, winning, n_tickets)
    independent = independent_draw_baseline(ticket_p, n_tickets)
    absolute = exact - independent
    return {
        "distinct_ticket_count": n_tickets,
        "q_distinct": exact,
        "q_independent_rejected": independent,
        "absolute_difference": absolute,
        "relative_difference": absolute / independent if independent else 0.0,
    }


def per_draw_probabilities(
    lottery: str,
    distinct_ticket_counts: Sequence[int],
    *,
    exact: bool = True,
) -> List[float]:
    """Build the per-draw null vector from traceable distinct-ticket counts."""
    total, winning = ticket_universe(lottery)
    ticket_p = winning / total
    if exact:
        return [
            exact_distinct_draw_baseline(total, winning, int(n))
            for n in distinct_ticket_counts
        ]
    return [
        independent_draw_baseline(ticket_p, int(n))
        for n in distinct_ticket_counts
    ]


# --------------------------------------------------------------------------- #
# Inference engine (exact binomial + exact Poisson-binomial, CIs, corrections)#
# --------------------------------------------------------------------------- #

def _log_binom_pmf(i: int, n: int, p: float) -> float:
    if p <= 0.0:
        return 0.0 if i == 0 else float("-inf")
    if p >= 1.0:
        return 0.0 if i == n else float("-inf")
    return (
        math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1)
        + i * math.log(p) + (n - i) * math.log1p(-p)
    )


def binomial_upper_pvalue(k: int, n: int, p: float) -> float:
    """Exact one-sided upper-tail p-value: P(X >= k), X ~ Binomial(n, p)."""
    if n < 0 or k > n:
        return 0.0
    if k <= 0:
        return 1.0
    total = 0.0
    for i in range(k, n + 1):
        lp = _log_binom_pmf(i, n, p)
        if lp != float("-inf"):
            total += math.exp(lp)
    return min(1.0, total)


def binomial_cdf_leq(k: int, n: int, p: float) -> float:
    """P(X <= k) = 1 - P(X >= k+1)."""
    if k >= n:
        return 1.0
    if k < 0:
        return 0.0
    return 1.0 - binomial_upper_pvalue(k + 1, n, p)


def poisson_binomial_pmf(probs: Sequence[float]) -> List[float]:
    """Exact Poisson-binomial PMF over heterogeneous Bernoulli probs.

    Returns ``dist`` with ``dist[j] = P(S = j)`` for j = 0..len(probs), by exact
    DP convolution. Deterministic and bounded (O(n^2))."""
    dist = [1.0]
    for p in probs:
        nxt = [0.0] * (len(dist) + 1)
        for j, dj in enumerate(dist):
            if dj == 0.0:
                continue
            nxt[j] += dj * (1.0 - p)
            nxt[j + 1] += dj * p
        dist = nxt
    return dist


def poisson_binomial_upper_pvalue(k: int, probs: Sequence[float]) -> float:
    """Exact one-sided upper tail P(S >= k) for a Poisson-binomial S."""
    n = len(probs)
    if k <= 0:
        return 1.0
    if k > n:
        return 0.0
    dist = poisson_binomial_pmf(probs)
    return min(1.0, math.fsum(dist[k:]))


def poisson_binomial_cdf_leq(k: int, probs: Sequence[float]) -> float:
    """Exact lower tail P(S <= k) for a Poisson-binomial S."""
    n = len(probs)
    if k < 0:
        return 0.0
    if k >= n:
        return 1.0
    dist = poisson_binomial_pmf(probs)
    return min(1.0, math.fsum(dist[:k + 1]))


def _probs_are_constant(probs: Sequence[float]) -> bool:
    if not probs:
        return True
    p0 = probs[0]
    return all(abs(p - p0) <= 1e-15 for p in probs)


def upper_tail_pvalue(observed_k: int, probs: Sequence[float]) -> Tuple[float, str]:
    """One-sided upper-tail p-value with exact method selection.

    Constant per-draw null prob -> exact binomial; heterogeneous -> exact
    Poisson-binomial. Returns (p_value, method)."""
    if not probs:
        return 1.0, "degenerate_empty"
    if _probs_are_constant(probs):
        return binomial_upper_pvalue(observed_k, len(probs), probs[0]), "exact_binomial_upper"
    return poisson_binomial_upper_pvalue(observed_k, probs), "exact_poisson_binomial_upper"


def lower_tail_pvalue(observed_k: int, probs: Sequence[float]) -> Tuple[float, str]:
    """One-sided lower-tail p-value P(S <= observed) with exact method selection."""
    if not probs:
        return 1.0, "degenerate_empty"
    if _probs_are_constant(probs):
        return binomial_cdf_leq(observed_k, len(probs), probs[0]), "exact_binomial_lower"
    return poisson_binomial_cdf_leq(observed_k, probs), "exact_poisson_binomial_lower"


def wilson_interval(k: int, n: int, conf: float = 0.95) -> Tuple[float, float]:
    """Two-sided Wilson score interval (closed form, dependency-free)."""
    if n == 0:
        return (0.0, 1.0)
    z = _z_for_conf(conf)
    phat = k / n
    z2 = z * z
    denom = 1.0 + z2 / n
    center = (phat + z2 / (2 * n)) / denom
    half = (z * math.sqrt(phat * (1 - phat) / n + z2 / (4 * n * n))) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def clopper_pearson_interval(k: int, n: int, conf: float = 0.95) -> Tuple[float, float]:
    """Exact two-sided Clopper-Pearson interval via bisection on the binomial CDF."""
    if n == 0:
        return (0.0, 1.0)
    alpha = 1.0 - conf
    lower = 0.0 if k == 0 else _bisect(lambda p: binomial_upper_pvalue(k, n, p) - alpha / 2.0, 0.0, 1.0)
    upper = 1.0 if k == n else _bisect(lambda p: binomial_cdf_leq(k, n, p) - alpha / 2.0, 0.0, 1.0)
    return (lower, upper)


def _z_for_conf(conf: float) -> float:
    table = {0.90: 1.6448536269514722, 0.95: 1.959963984540054, 0.99: 2.5758293035489004}
    if conf in table:
        return table[conf]
    return _norm_ppf(1.0 - (1.0 - conf) / 2.0)


def _norm_ppf(q: float) -> float:
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    plow, phigh = 0.02425, 1 - 0.02425
    if q < plow:
        r = math.sqrt(-2 * math.log(q))
        return (((((c[0] * r + c[1]) * r + c[2]) * r + c[3]) * r + c[4]) * r + c[5]) / \
               ((((d[0] * r + d[1]) * r + d[2]) * r + d[3]) * r + 1)
    if q > phigh:
        r = math.sqrt(-2 * math.log(1 - q))
        return -(((((c[0] * r + c[1]) * r + c[2]) * r + c[3]) * r + c[4]) * r + c[5]) / \
               ((((d[0] * r + d[1]) * r + d[2]) * r + d[3]) * r + 1)
    r = q - 0.5
    s = r * r
    return (((((a[0] * s + a[1]) * s + a[2]) * s + a[3]) * s + a[4]) * s + a[5]) * r / \
           (((((b[0] * s + b[1]) * s + b[2]) * s + b[3]) * s + b[4]) * s + 1)


def _bisect(f, lo: float, hi: float, tol: float = 1e-10, iters: int = 200) -> float:
    flo, fhi = f(lo), f(hi)
    if flo == 0.0:
        return lo
    if fhi == 0.0:
        return hi
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        fm = f(mid)
        if abs(fm) < tol or (hi - lo) < tol:
            return mid
        if (fm > 0) == (flo > 0):
            lo, flo = mid, fm
        else:
            hi, fhi = mid, fm
    return 0.5 * (lo + hi)


def bonferroni_pvalue(raw_p: float, family_m: int = CORRECTION_FAMILY_M) -> float:
    """Bonferroni-corrected p-value: min(1, p * m). Family m is fixed (108)."""
    return min(1.0, raw_p * family_m)


def benjamini_hochberg(pvalues: Sequence[float], q: float = BH_FDR_Q) -> List[bool]:
    """BH-FDR rejection flags (DESCRIPTIVE ONLY in this task — cannot promote)."""
    m = len(pvalues)
    if m == 0:
        return []
    order = sorted(range(m), key=lambda i: pvalues[i])
    flags = [False] * m
    max_rank = -1
    for rank, idx in enumerate(order, start=1):
        if pvalues[idx] <= (rank / m) * q:
            max_rank = rank
    for rank, idx in enumerate(order, start=1):
        if rank <= max_rank:
            flags[idx] = True
    return flags


# --------------------------------------------------------------------------- #
# Observed-counts artifact loader (committed artifact ONLY; never the DB)      #
# --------------------------------------------------------------------------- #

class ObservedCountsError(RuntimeError):
    """Raised when the observed-counts artifact fails an integrity/scope gate."""


class IdentityArtifactError(ObservedCountsError):
    """Raised when distinct-ticket identity evidence is incomplete or misaligned."""


def _strip_obs_volatile(obj):
    if isinstance(obj, dict):
        return {k: _strip_obs_volatile(v) for k, v in obj.items() if k not in _OBS_VOLATILE_KEYS}
    if isinstance(obj, list):
        return [_strip_obs_volatile(x) for x in obj]
    return obj


def compute_observed_payload_digest(artifact: Dict[str, object]) -> str:
    """Reproduce the export's canonical payload digest from a loaded artifact."""
    payload = _strip_obs_volatile(copy.deepcopy(artifact))
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_source_artifact(
    path: str,
    expected_digest: Optional[str],
    expected_raw_sha: Optional[str],
) -> Dict[str, object]:
    with open(path, "r", encoding="utf-8") as fh:
        artifact = json.load(fh)
    raw_sha = sha256_file(path)
    canonical = compute_observed_payload_digest(artifact)
    embedded = artifact.get("canonical_payload_digest")
    if embedded != canonical:
        raise ObservedCountsError(
            f"{path}: embedded digest {embedded} != recomputed {canonical}"
        )
    if expected_digest is not None and canonical != expected_digest:
        raise ObservedCountsError(
            f"{path}: canonical digest {canonical} != expected {expected_digest}"
        )
    if expected_raw_sha is not None and raw_sha != expected_raw_sha:
        raise ObservedCountsError(
            f"{path}: raw SHA-256 {raw_sha} != expected {expected_raw_sha}"
        )
    return {
        "path": path,
        "raw_sha256": raw_sha,
        "canonical_payload_digest": canonical,
        "artifact": artifact,
    }


def load_primary_observed_counts(path: str = PRIMARY_OBSERVED_COUNTS_PATH,
                                 expected_digest: Optional[str] = PRIMARY_OBSERVED_COUNTS_DIGEST,
                                 ) -> Dict[str, object]:
    """Read and validate the IMMUTABLE primary observed-counts artifact.

    Hard gates (raise ObservedCountsError on failure):
      * canonical payload digest reproduces and (when pinned) equals the
        expected digest;
      * exactly 36 frozen strategy x lottery cells (15/11/10);
      * every cell carries exactly the primary windows 50/300/750 and no
        forbidden window (100/500/1500) appears as a primary record;
      * each window record carries the required observed fields.

    Reads only the committed artifact file — never the production DB.
    """
    with open(path, "r", encoding="utf-8") as fh:
        artifact = json.load(fh)

    recomputed = compute_observed_payload_digest(artifact)
    embedded = artifact.get("canonical_payload_digest")
    if embedded is not None and recomputed != embedded:
        raise ObservedCountsError(
            f"observed-counts canonical digest mismatch: recomputed {recomputed} "
            f"!= embedded {embedded}")
    if expected_digest is not None and recomputed != expected_digest:
        raise ObservedCountsError(
            f"observed-counts canonical digest {recomputed} != expected {expected_digest}")

    cells = artifact.get("cells")
    if not isinstance(cells, list) or len(cells) != EXPECTED_FROZEN_CELL_COUNT:
        raise ObservedCountsError(
            f"expected {EXPECTED_FROZEN_CELL_COUNT} cells, found "
            f"{len(cells) if isinstance(cells, list) else 'n/a'}")

    by_lottery: Dict[str, set] = {lot: set() for lot in LOTTERIES}
    for cell in cells:
        lot = cell.get("lottery_type")
        sid = cell.get("strategy_id")
        if lot not in by_lottery:
            raise ObservedCountsError(f"unexpected lottery_type {lot!r}")
        by_lottery[lot].add(sid)
        windows = cell.get("windows")
        if not isinstance(windows, list):
            raise ObservedCountsError(f"cell {lot}/{sid} has no windows list")
        seen = []
        for w in windows:
            wv = w.get("window")
            if wv in FORBIDDEN_PRIMARY_WINDOWS:
                raise ObservedCountsError(
                    f"forbidden primary window {wv} present in cell {lot}/{sid}")
            seen.append(wv)
            for field in ("support_draws", "observed_successes",
                          "bet_count_distribution", "window_label"):
                if field not in w:
                    raise ObservedCountsError(
                        f"cell {lot}/{sid} window {wv} missing field {field}")
        if tuple(seen) != PRIMARY_WINDOWS:
            raise ObservedCountsError(
                f"cell {lot}/{sid} windows {tuple(seen)} != primary {PRIMARY_WINDOWS}")

    for lot, expected in FROZEN_STRATEGY_CELLS.items():
        if by_lottery[lot] != set(expected):
            raise ObservedCountsError(
                f"{lot} strategy set mismatch vs frozen P267C universe")

    return artifact


def _canonical_ticket_serialization(content: Dict[str, object]) -> str:
    return json.dumps(
        content, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def _identity_window_index(cell: Dict[str, object]) -> Dict[int, Dict[str, object]]:
    windows = cell.get("windows")
    if not isinstance(windows, list):
        raise IdentityArtifactError("identity cell has no windows list")
    result = {int(window["window"]): window for window in windows}
    if tuple(result) != PRIMARY_WINDOWS:
        raise IdentityArtifactError(
            f"identity windows {tuple(result)} != {PRIMARY_WINDOWS}"
        )
    return result


def load_identity_artifact(
    path: str = IDENTITY_ARTIFACT_PATH,
    expected_digest: Optional[str] = IDENTITY_ARTIFACT_DIGEST,
    expected_raw_sha: Optional[str] = IDENTITY_ARTIFACT_RAW_SHA,
    expected_aggregate_distributions: Optional[
        Dict[int, Dict[int, int]]
    ] = None,
) -> Dict[str, object]:
    verified = verify_source_artifact(path, expected_digest, expected_raw_sha)
    artifact = verified["artifact"]
    cells = artifact.get("cells")
    if not isinstance(cells, list) or len(cells) != EXPECTED_FROZEN_CELL_COUNT:
        raise IdentityArtifactError("identity artifact must contain 36 cells")

    expected_cells = {
        (lottery, strategy)
        for lottery, strategies in FROZEN_STRATEGY_CELLS.items()
        for strategy in strategies
    }
    actual_cells = {
        (cell.get("lottery_type"), cell.get("strategy_id"))
        for cell in cells
    }
    if actual_cells != expected_cells:
        raise IdentityArtifactError("identity cell set differs from frozen family")

    windows_checked = 0
    aggregate_dist = {window: Counter() for window in PRIMARY_WINDOWS}
    for cell in cells:
        lottery = str(cell["lottery_type"])
        strategy = str(cell["strategy_id"])
        window_index = _identity_window_index(cell)
        supported_draws = cell.get("supported_draws")
        if not isinstance(supported_draws, list):
            raise IdentityArtifactError(
                f"{lottery}/{strategy}: supported_draws missing"
            )
        for draw in supported_draws:
            groups = draw.get("canonical_ticket_groups")
            if not isinstance(groups, list) or not groups:
                raise IdentityArtifactError(
                    f"{lottery}/{strategy}/{draw.get('target_draw')}: "
                    "canonical ticket groups missing"
                )
            eligible = int(draw["eligible_bet_index_count"])
            distinct = int(draw["distinct_ticket_count"])
            if distinct != len(groups):
                raise IdentityArtifactError("distinct count/group count mismatch")
            if eligible != sum(int(group["group_multiplicity"]) for group in groups):
                raise IdentityArtifactError("eligible count/group multiplicity mismatch")
            if int(draw["duplicate_ticket_count"]) != eligible - distinct:
                raise IdentityArtifactError("duplicate ticket arithmetic mismatch")
            for group in groups:
                serialization = _canonical_ticket_serialization(
                    group["canonical_ticket_content"]
                )
                fingerprint = hashlib.sha256(
                    serialization.encode("utf-8")
                ).hexdigest()
                if fingerprint != group["fingerprint_sha256"]:
                    raise IdentityArtifactError("canonical fingerprint mismatch")
                if int(group["group_multiplicity"]) != len(
                    group["bet_index_values"]
                ):
                    raise IdentityArtifactError("ticket group multiplicity mismatch")

        for window in PRIMARY_WINDOWS:
            rec = window_index[window]
            if rec.get("artifact_alignment", {}).get("status") != "PASS":
                raise IdentityArtifactError(
                    f"{lottery}/{strategy}/w{window}: alignment not PASS"
                )
            if int(rec["duplicate_content_draw_count"]) != 0:
                raise IdentityArtifactError("duplicate-content draw found")
            if int(rec["total_duplicate_ticket_content_count"]) != 0:
                raise IdentityArtifactError("duplicate ticket content found")
            for value, count in rec["distinct_ticket_count_distribution"].items():
                aggregate_dist[window][int(value)] += int(count)
            windows_checked += 1

    summary = artifact.get("summary") or {}
    if int(summary.get("same_bet_index_content_conflict_count", -1)) != 0:
        raise IdentityArtifactError("same-bet-index content conflict found")
    if int(summary.get("duplicate_content_draw_count_long_window_records", -1)) != 0:
        raise IdentityArtifactError("cross-index duplicate-content draw found")
    if int(summary.get("total_duplicate_ticket_content_count_long_window_records", -1)) != 0:
        raise IdentityArtifactError("cross-index duplicate ticket found")
    if summary.get("duplicate_content_groups") != []:
        raise IdentityArtifactError("duplicate-content groups are not empty")
    if windows_checked != CORRECTION_FAMILY_M:
        raise IdentityArtifactError("identity alignment did not cover 108 windows")

    expected_dist = expected_aggregate_distributions
    if expected_dist is None and path == IDENTITY_ARTIFACT_PATH:
        expected_dist = {
            50: {1: 1349, 3: 150, 4: 50, 5: 50},
            300: {1: 8099, 3: 900, 4: 300, 5: 300},
            750: {1: 20249, 3: 2250, 4: 750, 5: 750},
        }
    actual_dist = {
        window: dict(sorted(counter.items()))
        for window, counter in aggregate_dist.items()
    }
    if expected_dist is not None and actual_dist != expected_dist:
        raise IdentityArtifactError(
            f"identity aggregate distributions {actual_dist} != {expected_dist}"
        )
    return artifact


def identity_draws_for_window(
    identity_cell: Dict[str, object],
    observed_window: Dict[str, object],
) -> List[Dict[str, object]]:
    window = int(observed_window["window"])
    identity_window = _identity_window_index(identity_cell)[window]
    lottery = str(observed_window["lottery_type"])
    strategy = str(observed_window["strategy_id"])

    alignment_fields = (
        "support_draws",
        "distinct_draws_in_window",
        "latest_target_draw",
        "earliest_target_draw",
        "excluded_rows",
        "excluded_missing_special_rows",
        "exclusion_by_reason",
    )
    for field in alignment_fields:
        if identity_window[field] != observed_window[field]:
            raise IdentityArtifactError(
                f"{lottery}/{strategy}/w{window}: {field} mismatch"
            )
    if (
        identity_window["eligible_bet_index_count_distribution"]
        != observed_window["bet_count_distribution"]
    ):
        raise IdentityArtifactError(
            f"{lottery}/{strategy}/w{window}: eligible-index distribution mismatch"
        )

    earliest = int(identity_window["earliest_target_draw"])
    latest = int(identity_window["latest_target_draw"])
    selected = [
        draw
        for draw in identity_cell["supported_draws"]
        if earliest <= int(draw["target_draw"]) <= latest
    ]
    support = int(observed_window["support_draws"])
    if len(selected) != support:
        raise IdentityArtifactError(
            f"{lottery}/{strategy}/w{window}: selected {len(selected)} "
            f"identity draws != support {support}"
        )
    distribution = {
        str(value): count
        for value, count in sorted(
            Counter(int(draw["distinct_ticket_count"]) for draw in selected).items()
        )
    }
    if distribution != identity_window["distinct_ticket_count_distribution"]:
        raise IdentityArtifactError(
            f"{lottery}/{strategy}/w{window}: distinct-ticket distribution mismatch"
        )
    return selected


# --------------------------------------------------------------------------- #
# Per-window evaluation                                                        #
# --------------------------------------------------------------------------- #

def _round(x: float, nd: int = 12) -> float:
    return round(x, nd)


def evaluate_window(
    lottery: str,
    strategy: str,
    window_record: Dict[str, object],
    identity_draws: Sequence[Dict[str, object]],
) -> Dict[str, object]:
    """Full per-window inference record (decision finalized later with stability)."""
    window = int(window_record["window"])
    label = str(window_record["window_label"])
    support = int(window_record["support_draws"])
    observed = int(window_record["observed_successes"])
    bet_dist = dict(window_record.get("bet_count_distribution") or {})

    distinct_counts = [int(draw["distinct_ticket_count"]) for draw in identity_draws]
    probs = per_draw_probabilities(lottery, distinct_counts, exact=True)
    independent_probs = per_draw_probabilities(
        lottery, distinct_counts, exact=False
    )
    if len(probs) != support:
        raise ObservedCountsError(
            f"{lottery}/{strategy} w{window}: identity-draw total {len(probs)} "
            f"!= support_draws {support}")
    expected = math.fsum(probs)
    expected_independent = math.fsum(independent_probs)
    null_constant = _probs_are_constant(probs)
    distinct_distribution = {
        str(value): count
        for value, count in sorted(Counter(distinct_counts).items())
    }
    total_tickets, winning_tickets = ticket_universe(lottery)

    rec: Dict[str, object] = {
        "lottery_type": lottery,
        "strategy_id": strategy,
        "window": window,
        "window_label": label,
        "support_draws": support,
        "observed_successes": observed,
        "bet_count_distribution": {str(k): int(v) for k, v in bet_dist.items()},
        "eligible_bet_index_count_definition": (
            "distinct scoreable bet_index values from the immutable primary artifact"
        ),
        "distinct_ticket_count_definition": (
            "unique canonical ticket contents from the immutable identity artifact"
        ),
        "distinct_ticket_count_distribution": distinct_distribution,
        "per_draw_distinct_ticket_trace": [
            {
                "target_draw": str(draw["target_draw"]),
                "distinct_ticket_count": int(draw["distinct_ticket_count"]),
            }
            for draw in identity_draws
        ],
        "null_probability_constant": null_constant,
        "ticket_universe_total": total_tickets,
        "ticket_universe_winning": winning_tickets,
        "expected_successes": _round(expected),
        "rejected_independent_expected_successes": _round(expected_independent),
        "null_probability_diagnostics": [
            {
                key: (_round(value) if isinstance(value, float) else value)
                for key, value in null_probability_diagnostic(
                    lottery, distinct_count
                ).items()
            }
            for distinct_count in sorted(set(distinct_counts))
        ],
        "exact_distinct_ticket_null_used": True,
        "independent_approximation_rejected_for_final_inference": True,
        "rejected_independent_approximation": {
            "evaluable": (
                support >= MIN_SUPPORT_DRAWS
                and expected_independent >= MIN_EXPECTED_SUCCESSES
            ),
            "mean_baseline_rate": (
                _round(expected_independent / support) if support else None
            ),
            "expected_successes": _round(expected_independent),
            "window_decision": None,
        },
    }

    evaluable = support >= MIN_SUPPORT_DRAWS and expected >= MIN_EXPECTED_SUCCESSES
    if not evaluable:
        rec.update({
            "evaluable": False,
            "support_status": "INSUFFICIENT_SUPPORT",
            "statistical_status": "NOT_EVALUATED",
            "significant_positive": False,
            "significant_negative": False,
            "window_decision": "PRIZE_AWARE_INSUFFICIENT_SUPPORT",
            "insufficient_reason": (
                f"support_draws {support} < {MIN_SUPPORT_DRAWS}"
                if support < MIN_SUPPORT_DRAWS
                else f"expected_successes {expected:.4f} < {MIN_EXPECTED_SUCCESSES}"
            ),
        })
        return rec

    mean_baseline_rate = expected / support
    mean_independent_rate = expected_independent / support
    obs_rate = observed / support
    excess = obs_rate - mean_baseline_rate
    independent_excess = obs_rate - mean_independent_rate
    raw_p, up_method = upper_tail_pvalue(observed, probs)
    raw_p_lower, lo_method = lower_tail_pvalue(observed, probs)
    provisional_raw_p, provisional_up_method = upper_tail_pvalue(
        observed, independent_probs
    )
    provisional_raw_p_lower, provisional_lo_method = lower_tail_pvalue(
        observed, independent_probs
    )
    bonf_p = bonferroni_pvalue(raw_p)
    bonf_p_lower = bonferroni_pvalue(raw_p_lower)
    provisional_bonf_p = bonferroni_pvalue(provisional_raw_p)
    provisional_bonf_p_lower = bonferroni_pvalue(provisional_raw_p_lower)
    wilson = wilson_interval(observed, support)
    cp = clopper_pearson_interval(observed, support)

    significant_positive = excess > 0 and bonf_p <= FAMILY_ALPHA
    significant_negative = excess < 0 and bonf_p_lower <= FAMILY_ALPHA
    if significant_positive:
        statistical_status = "SIGNIFICANT_POSITIVE_CORRECTED"
    elif significant_negative:
        statistical_status = "SIGNIFICANT_NEGATIVE_CORRECTED"
    elif excess > 0:
        statistical_status = "POSITIVE_NOT_CORRECTED"
    elif excess < 0:
        statistical_status = "NEGATIVE_NOT_CORRECTED"
    else:
        statistical_status = "FLAT"

    rec.update({
        "evaluable": True,
        "support_status": "SUFFICIENT",
        "observed_rate": _round(obs_rate),
        "mean_baseline_rate": _round(mean_baseline_rate),
        "ticket_baseline": _round(winning_tickets / total_tickets),
        "absolute_excess": _round(excess),
        "absolute_excess_pp": _round(excess * 100.0, 8),
        "relative_lift": _round(obs_rate / mean_baseline_rate, 8) if mean_baseline_rate > 0 else None,
        "wilson_ci_95": [_round(wilson[0]), _round(wilson[1])],
        "clopper_pearson_ci_95": [_round(cp[0]), _round(cp[1])],
        "raw_p_value_one_sided_upper": _round(raw_p),
        "bonferroni_p_value": _round(bonf_p),
        "raw_p_value_one_sided_lower": _round(raw_p_lower),
        "bonferroni_p_value_lower": _round(bonf_p_lower),
        "p_value_method_upper": up_method,
        "p_value_method_lower": lo_method,
        "significant_positive": significant_positive,
        "significant_negative": significant_negative,
        "statistical_status": statistical_status,
        # decision finalized in evaluate_group once stability is known:
        "window_decision": None,
        "rejected_independent_approximation": {
            "evaluable": (
                support >= MIN_SUPPORT_DRAWS
                and expected_independent >= MIN_EXPECTED_SUCCESSES
            ),
            "mean_baseline_rate": _round(mean_independent_rate),
            "expected_successes": _round(expected_independent),
            "absolute_excess": _round(independent_excess),
            "absolute_excess_pp": _round(independent_excess * 100.0, 8),
            "raw_p_value_one_sided_upper": _round(provisional_raw_p),
            "bonferroni_p_value": _round(provisional_bonf_p),
            "raw_p_value_one_sided_lower": _round(provisional_raw_p_lower),
            "bonferroni_p_value_lower": _round(provisional_bonf_p_lower),
            "p_value_method_upper": provisional_up_method,
            "p_value_method_lower": provisional_lo_method,
            "significant_positive": (
                independent_excess > 0
                and provisional_bonf_p <= FAMILY_ALPHA
            ),
            "significant_negative": (
                independent_excess < 0
                and provisional_bonf_p_lower <= FAMILY_ALPHA
            ),
            "window_decision": None,
        },
    })
    return rec


# --------------------------------------------------------------------------- #
# Stability rule + group / project decisions                                  #
# --------------------------------------------------------------------------- #

def evaluate_stability(windows: Dict[str, Dict[str, object]]) -> Dict[str, object]:
    """Owner pre-registered 10-point STABILITY rule at the strategy x lottery
    group level. Returns the per-criterion booleans and the PASS/FAIL status."""
    short, mid, long = windows["SHORT"], windows["MID"], windows["LONG"]
    all_evaluable = bool(short["evaluable"] and mid["evaluable"] and long["evaluable"])

    c1 = all_evaluable
    # criteria 2-5,7 require evaluable windows to read excess/significance.
    c2 = bool(all_evaluable and mid["absolute_excess"] > 0)
    c3 = bool(all_evaluable and long["absolute_excess"] > 0)
    c4 = bool(all_evaluable and short["absolute_excess"] >= 0)
    c5 = bool(all_evaluable and (mid["significant_positive"] or long["significant_positive"]))
    c6 = True  # structural: SHORT is never consulted for c5 / promotion
    any_sig_neg = bool(
        short.get("significant_negative") or mid.get("significant_negative")
        or long.get("significant_negative"))
    c7 = bool(all_evaluable and not any_sig_neg)
    c8 = True  # frozen thresholds/family; no post-outcome change
    c9 = True  # nested windows = cross-timescale consistency, not replication
    c10 = True  # passing => research GO candidate only; never production apply

    operational_pass = c1 and c2 and c3 and c4 and c5 and c7
    criteria = {
        "c1_all_three_evaluable": c1,
        "c2_mid_excess_strictly_positive": c2,
        "c3_long_excess_strictly_positive": c3,
        "c4_short_excess_nonnegative": c4,
        "c5_mid_or_long_bonferroni_sig": c5,
        "c6_short_cannot_trigger_promotion": c6,
        "c7_no_negative_or_insufficient_window": c7,
        "c8_no_post_outcome_family_or_threshold_change": c8,
        "c9_nested_not_independent_replications": c9,
        "c10_passing_is_research_go_candidate_only": c10,
    }
    fail_reasons = [name for name, ok in criteria.items()
                    if not ok and name in (
                        "c1_all_three_evaluable",
                        "c2_mid_excess_strictly_positive",
                        "c3_long_excess_strictly_positive",
                        "c4_short_excess_nonnegative",
                        "c5_mid_or_long_bonferroni_sig",
                        "c7_no_negative_or_insufficient_window")]
    return {
        "status": "STABILITY_PASS" if operational_pass else "STABILITY_FAIL",
        "criteria": criteria,
        "fail_reasons": fail_reasons,
    }


def finalize_window_decision(label: str, window: Dict[str, object],
                             stability: Dict[str, object]) -> str:
    """Per-window decision class. SHORT can never be EDGE (guardrail only)."""
    if not window["evaluable"]:
        return "PRIZE_AWARE_INSUFFICIENT_SUPPORT"
    if float(window["absolute_excess"]) <= 0.0:
        return "PRIZE_AWARE_NULL"
    if float(window["raw_p_value_one_sided_upper"]) > FAMILY_ALPHA:
        return "PRIZE_AWARE_NULL"
    if (label in ("MID", "LONG")
            and window["significant_positive"]
            and stability["status"] == "STABILITY_PASS"):
        return "PRIZE_AWARE_EDGE_CORRECTION_SURVIVING"
    return "PRIZE_AWARE_DESCRIPTIVE_ONLY"


def overall_group_decision(windows: Dict[str, Dict[str, object]],
                           stability: Dict[str, object]) -> str:
    if any(not w["evaluable"] for w in windows.values()):
        return "INSUFFICIENT_SUPPORT"
    has_edge = (stability["status"] == "STABILITY_PASS" and any(
        windows[l]["window_decision"] == "PRIZE_AWARE_EDGE_CORRECTION_SURVIVING"
        for l in ("MID", "LONG")))
    if has_edge:
        return "GO_CANDIDATE_RESEARCH_ONLY"
    if any(float(w["absolute_excess"]) > 0.0 for w in windows.values()):
        return "DESCRIPTIVE_ONLY"
    return "NULL"


def _provisional_windows(
    exact_windows: Dict[str, Dict[str, object]],
) -> Dict[str, Dict[str, object]]:
    provisional: Dict[str, Dict[str, object]] = {}
    for label, exact in exact_windows.items():
        diag = exact["rejected_independent_approximation"]
        rec = copy.deepcopy(exact)
        rec["evaluable"] = bool(diag["evaluable"])
        if rec["evaluable"]:
            rec["expected_successes"] = diag["expected_successes"]
            rec["mean_baseline_rate"] = diag["mean_baseline_rate"]
            rec["absolute_excess"] = diag["absolute_excess"]
            rec["absolute_excess_pp"] = diag["absolute_excess_pp"]
            rec["raw_p_value_one_sided_upper"] = diag[
                "raw_p_value_one_sided_upper"
            ]
            rec["bonferroni_p_value"] = diag["bonferroni_p_value"]
            rec["raw_p_value_one_sided_lower"] = diag[
                "raw_p_value_one_sided_lower"
            ]
            rec["bonferroni_p_value_lower"] = diag[
                "bonferroni_p_value_lower"
            ]
            rec["significant_positive"] = diag["significant_positive"]
            rec["significant_negative"] = diag["significant_negative"]
        else:
            rec["significant_positive"] = False
            rec["significant_negative"] = False
        provisional[label] = rec
    stability = evaluate_stability(provisional)
    for label, rec in provisional.items():
        rec["window_decision"] = finalize_window_decision(label, rec, stability)
    return provisional


def evaluate_group(
    lottery: str,
    strategy: str,
    cell_record: Dict[str, object],
    identity_cell: Dict[str, object],
) -> Dict[str, object]:
    """Evaluate one strategy x lottery group across its three primary windows."""
    by_label: Dict[str, Dict[str, object]] = {}
    for w in cell_record["windows"]:
        identity_draws = identity_draws_for_window(identity_cell, w)
        rec = evaluate_window(lottery, strategy, w, identity_draws)
        by_label[rec["window_label"]] = rec
    if set(by_label) != set(WINDOW_ORDER):
        raise ObservedCountsError(
            f"{lottery}/{strategy} labels {set(by_label)} != {set(WINDOW_ORDER)}")

    stability = evaluate_stability(by_label)
    for label, rec in by_label.items():
        rec["window_decision"] = finalize_window_decision(label, rec, stability)
    overall = overall_group_decision(by_label, stability)

    provisional_by_label = _provisional_windows(by_label)
    provisional_stability = evaluate_stability(provisional_by_label)
    provisional_overall = overall_group_decision(
        provisional_by_label, provisional_stability
    )
    for label, rec in by_label.items():
        provisional = provisional_by_label[label]
        rec["rejected_independent_approximation"]["window_decision"] = (
            provisional["window_decision"]
        )
    return {
        "lottery_type": lottery,
        "strategy_id": strategy,
        "windows": [by_label[l] for l in WINDOW_ORDER],
        "stability": stability,
        "overall_group_decision": overall,
        "rejected_provisional_independent_null": {
            "stability": provisional_stability,
            "overall_group_decision": provisional_overall,
        },
    }


def overall_project_classification(groups: Sequence[Dict[str, object]]) -> str:
    decisions = [g["overall_group_decision"] for g in groups]
    if any(d == "GO_CANDIDATE_RESEARCH_ONLY" for d in decisions):
        return "PRIZE_AWARE_EDGE_CORRECTION_SURVIVING"
    if any(d == "DESCRIPTIVE_ONLY" for d in decisions):
        return "PRIZE_AWARE_DESCRIPTIVE_ONLY"
    if any(d == "NULL" for d in decisions):
        return "PRIZE_AWARE_NULL"
    return "PRIZE_AWARE_INSUFFICIENT_SUPPORT"


# --------------------------------------------------------------------------- #
# Report assembly                                                             #
# --------------------------------------------------------------------------- #

DISCLAIMERS: Tuple[str, ...] = (
    "Retrospective research only.",
    "Primary observed counts come from the immutable 50/300/750 observed-counts artifact.",
    "Ticket multiplicities come only from the immutable distinct-ticket identity artifact.",
    "The exact distinct-ticket without-replacement null is used for final inference.",
    "The independent-with-replacement approximation is rejected for final inference.",
    "1500-draw and all-history horizons are REFERENCE-ONLY and never drive a primary decision.",
    "The production DB was not opened, queried, or written.",
    "A descriptive observed rate is NOT a predictive edge.",
    "Bonferroni family is fixed at m=108 (36 cells x 3 primary windows); no post-outcome shrinkage.",
    "BH-FDR is descriptive only and cannot promote an edge.",
    "The three nested windows are cross-timescale consistency checks, not independent replications.",
    "SHORT-50 is a recent-direction guardrail and can never independently trigger an EDGE or a GO candidate.",
    "NULL and INSUFFICIENT_SUPPORT are valid, successful outcomes.",
    "No strategy reselection was performed.",
    "No prospective activation is authorized.",
    "No production apply is authorized; GO_CANDIDATE_RESEARCH_ONLY is not deployment authorization.",
    "P273B (replay feature mining) is NOT started.",
)


def compute_report_digest(report: Dict[str, object]) -> str:
    payload = copy.deepcopy(report)
    payload.pop("canonical_payload_digest", None)
    blob = json.dumps(
        payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _source_hashes() -> Dict[str, Dict[str, str]]:
    paths = {
        "primary_observed_counts": PRIMARY_OBSERVED_COUNTS_PATH,
        "identity_artifact": IDENTITY_ARTIFACT_PATH,
        "reference_observed_counts": REFERENCE_OBSERVED_COUNTS_PATH,
        "endpoint_json": ENDPOINT_SOURCE_JSON,
        "endpoint_markdown": ENDPOINT_SOURCE_MD,
        "strategy_cells": STRATEGY_CELL_SOURCE,
        "scorer": SCORER_SOURCE,
        "adapter": ADAPTER_SOURCE,
        "identity_exporter": IDENTITY_EXPORT_SOURCE,
        "primary_exporter": PRIMARY_EXPORT_SOURCE,
        "inference_source": INFERENCE_SOURCE,
    }
    return {
        name: {"path": path, "sha256": sha256_file(path)}
        for name, path in paths.items()
    }


def build_report(primary_path: str = PRIMARY_OBSERVED_COUNTS_PATH,
                 expected_digest: Optional[str] = PRIMARY_OBSERVED_COUNTS_DIGEST,
                 identity_path: str = IDENTITY_ARTIFACT_PATH,
                 identity_expected_digest: Optional[str] = IDENTITY_ARTIFACT_DIGEST,
                 identity_expected_raw_sha: Optional[str] = IDENTITY_ARTIFACT_RAW_SHA,
                 identity_expected_aggregate_distributions: Optional[
                     Dict[int, Dict[int, int]]
                 ] = None,
                 reference_path: str = REFERENCE_OBSERVED_COUNTS_PATH,
                 reference_expected_digest: Optional[str] = REFERENCE_OBSERVED_COUNTS_DIGEST,
                 reference_expected_raw_sha: Optional[str] = REFERENCE_OBSERVED_COUNTS_RAW_SHA,
                 ) -> Dict[str, object]:
    primary_verified = verify_source_artifact(
        primary_path,
        expected_digest,
        PRIMARY_OBSERVED_COUNTS_RAW_SHA if primary_path == PRIMARY_OBSERVED_COUNTS_PATH else None,
    )
    artifact = load_primary_observed_counts(primary_path, expected_digest)
    primary_digest = compute_observed_payload_digest(artifact)
    identity = load_identity_artifact(
        identity_path,
        identity_expected_digest,
        identity_expected_raw_sha,
        identity_expected_aggregate_distributions,
    )
    identity_digest = compute_observed_payload_digest(identity)
    reference_verified = verify_source_artifact(
        reference_path,
        reference_expected_digest,
        reference_expected_raw_sha,
    )

    baselines = {}
    for lottery in LOTTERIES:
        b = analytic_ticket_baseline(lottery)
        baselines[lottery] = {k: (_round(v) if isinstance(v, float) else v) for k, v in b.items()}

    # Per-cell, per-window inference across the full frozen family.
    cells_by_key = {(c["lottery_type"], c["strategy_id"]): c for c in artifact["cells"]}
    identity_by_key = {
        (c["lottery_type"], c["strategy_id"]): c for c in identity["cells"]
    }
    groups: List[Dict[str, object]] = []
    for lottery in LOTTERIES:
        for strategy in FROZEN_STRATEGY_CELLS[lottery]:
            cell = cells_by_key[(lottery, strategy)]
            identity_cell = identity_by_key[(lottery, strategy)]
            groups.append(evaluate_group(lottery, strategy, cell, identity_cell))

    # Descriptive-only BH-FDR over the evaluable primary cells (cannot promote).
    eval_index: List[Tuple[int, int]] = []
    raw_ps: List[float] = []
    for gi, g in enumerate(groups):
        for wi, w in enumerate(g["windows"]):
            if w["evaluable"]:
                eval_index.append((gi, wi))
                raw_ps.append(float(w["raw_p_value_one_sided_upper"]))
    bh_flags = benjamini_hochberg(raw_ps)
    for (gi, wi), flag in zip(eval_index, bh_flags):
        groups[gi]["windows"][wi]["bh_fdr_descriptive_reject"] = bool(flag)
    for g in groups:
        for w in g["windows"]:
            w.setdefault("bh_fdr_descriptive_reject", None)

    overall_project = overall_project_classification(groups)

    # Counts for the executive summary.
    window_decision_counts: Dict[str, int] = {}
    group_decision_counts: Dict[str, int] = {}
    stability_counts = {"STABILITY_PASS": 0, "STABILITY_FAIL": 0}
    n_eval_windows = 0
    for g in groups:
        group_decision_counts[g["overall_group_decision"]] = \
            group_decision_counts.get(g["overall_group_decision"], 0) + 1
        stability_counts[g["stability"]["status"]] += 1
        for w in g["windows"]:
            window_decision_counts[w["window_decision"]] = \
                window_decision_counts.get(w["window_decision"], 0) + 1
            if w["evaluable"]:
                n_eval_windows += 1

    family_cells = sum(len(v) for v in FROZEN_STRATEGY_CELLS.values())
    used_counts_by_lottery = {
        lottery: sorted({
            int(draw["distinct_ticket_count"])
            for cell in identity["cells"]
            if cell["lottery_type"] == lottery
            for draw in cell["supported_draws"]
        })
        for lottery in LOTTERIES
    }
    null_diagnostics = {
        lottery: [
            {
                key: (_round(value) if isinstance(value, float) else value)
                for key, value in null_probability_diagnostic(lottery, count).items()
            }
            for count in used_counts_by_lottery[lottery]
        ]
        for lottery in LOTTERIES
    }

    provisional_candidates = []
    for group in groups:
        provisional = group["rejected_provisional_independent_null"]
        if provisional["overall_group_decision"] != "GO_CANDIDATE_RESEARCH_ONLY":
            continue
        windows = []
        for window in group["windows"]:
            old = window["rejected_independent_approximation"]
            windows.append({
                "window": window["window"],
                "window_label": window["window_label"],
                "support_draws": window["support_draws"],
                "observed_successes": window["observed_successes"],
                "distinct_ticket_count_distribution": window[
                    "distinct_ticket_count_distribution"
                ],
                "rejected_independent_baseline_rate": old.get(
                    "mean_baseline_rate"
                ),
                "exact_distinct_baseline_rate": window.get("mean_baseline_rate"),
                "rejected_independent_expected_successes": old.get(
                    "expected_successes"
                ),
                "exact_distinct_expected_successes": window.get(
                    "expected_successes"
                ),
                "rejected_independent_raw_p_value": old.get(
                    "raw_p_value_one_sided_upper"
                ),
                "exact_distinct_raw_p_value": window.get(
                    "raw_p_value_one_sided_upper"
                ),
                "rejected_independent_bonferroni_p_value": old.get(
                    "bonferroni_p_value"
                ),
                "exact_distinct_bonferroni_p_value": window.get(
                    "bonferroni_p_value"
                ),
                "rejected_independent_window_decision": old.get(
                    "window_decision"
                ),
                "exact_distinct_window_decision": window["window_decision"],
            })
        provisional_candidates.append({
            "lottery_type": group["lottery_type"],
            "strategy_id": group["strategy_id"],
            "rejected_independent_stability": provisional["stability"]["status"],
            "exact_distinct_stability": group["stability"]["status"],
            "rejected_independent_group_decision": provisional[
                "overall_group_decision"
            ],
            "exact_distinct_group_decision": group["overall_group_decision"],
            "classification_transition": (
                f"{provisional['overall_group_decision']} -> "
                f"{group['overall_group_decision']}"
            ),
            "windows": windows,
        })

    report: Dict[str, object] = {
        "task_id": TASK_ID,
        "generated_date": GENERATED_DATE,
        "artifact_version": ARTIFACT_VERSION,
        "policy_version": POLICY_VERSION,
        "branch": BRANCH,
        "base_origin_main": BASE_ORIGIN_MAIN,
        "mode": MODE,
        "primary_question": (
            "Do any already-frozen strategies show a statistically credible "
            "prize-aware advantage over the governed random baseline (draw-level "
            "any-bet prize-aware success) under the owner-approved primary "
            "decision windows 50 (SHORT) / 300 (MID) / 750 (LONG)?"
        ),
        "retrospective_research_only": True,
        "window_policy": {
            "owner_approved": True,
            "policy_version": POLICY_VERSION,
            "primary_windows": list(PRIMARY_WINDOWS),
            "primary_window_labels": {str(k): v for k, v in PRIMARY_WINDOW_LABELS.items()},
            "reference_only_windows": list(REFERENCE_ONLY_WINDOWS),
            "reference_only_descriptions": list(REFERENCE_ONLY_DESCRIPTIONS),
            "reference_only_prohibited_uses": list(REFERENCE_ONLY_PROHIBITED_USES),
            "forbidden_primary_windows": sorted(FORBIDDEN_PRIMARY_WINDOWS),
        },
        "frozen_setup": {
            "lotteries": list(LOTTERIES),
            "analysis_unit": ANALYSIS_UNIT,
            "outcome": OUTCOME,
            "no_outcome_based_reselection": True,
            "identity_export_commit": IDENTITY_EXPORT_COMMIT,
            "identity_merge_commit": IDENTITY_MERGE_COMMIT,
            "strategy_set_source": {
                "path": STRATEGY_CELL_SOURCE, "sha256": STRATEGY_CELL_SOURCE_SHA,
                "cell_count": family_cells,
            },
            "frozen_strategy_cells": {k: list(v) for k, v in FROZEN_STRATEGY_CELLS.items()},
            "endpoint_source": {
                "md_path": ENDPOINT_SOURCE_MD, "md_sha256": ENDPOINT_SOURCE_MD_SHA,
                "json_path": ENDPOINT_SOURCE_JSON, "json_sha256": ENDPOINT_SOURCE_JSON_SHA,
            },
            "endpoints": ENDPOINTS,
            "scorer_source": SCORER_SOURCE,
        },
        "input_contract": {
            "primary_observed_counts_path": primary_path,
            "primary_observed_counts_raw_sha256": primary_verified["raw_sha256"],
            "primary_observed_counts_digest": primary_digest,
            "primary_observed_counts_digest_expected": expected_digest,
            "identity_artifact_path": identity_path,
            "identity_artifact_raw_sha256": sha256_file(identity_path),
            "identity_artifact_digest": identity_digest,
            "identity_artifact_digest_expected": identity_expected_digest,
            "reference_only_artifact_path": reference_path,
            "reference_only_artifact_raw_sha256": reference_verified["raw_sha256"],
            "reference_only_artifact_digest": reference_verified[
                "canonical_payload_digest"
            ],
            "production_db_path": PRODUCTION_DB_PATH,
            "production_db_opened": False,
            "observed_counts_regenerated": False,
            "identity_export_regenerated": False,
            "source_files": _source_hashes(),
        },
        "correction_family": {
            "definition": "all pre-registered (strategy x lottery x primary window) hypotheses",
            "strategy_lottery_cells": family_cells,
            "primary_windows": len(PRIMARY_WINDOWS),
            "family_m": CORRECTION_FAMILY_M,
            "family_alpha": FAMILY_ALPHA,
            "bonferroni_alpha_per_test": _round(FAMILY_ALPHA / CORRECTION_FAMILY_M),
            "bh_fdr_q_descriptive_only": BH_FDR_Q,
            "no_post_outcome_family_shrinkage": True,
        },
        "minimum_support_rule": {
            "min_support_draws": MIN_SUPPORT_DRAWS,
            "min_expected_successes": MIN_EXPECTED_SUCCESSES,
            "evaluable_requires": "support_draws >= 30 AND expected_successes >= 5.0",
        },
        "stability_rule": STABILITY_RULE,
        "baseline_contract": {
            "final_null": (
                "q_N = 1 - C(T-W,N)/C(T,N), using each draw's actual "
                "distinct_ticket_count from the immutable identity artifact"
            ),
            "rejected_final_null": (
                "q_independent = 1 - (1-W/T)^N; retained only as a rejected "
                "provisional diagnostic"
            ),
            "method_per_lottery": {
                "DAILY_539": "T=C(39,5); W=sum[k=2..5] C(5,k)C(34,5-k)",
                "BIG_LOTTO": "T=C(49,6); W=sum[k=3..6] C(6,k)C(43,6-k)+C(6,2)C(42,3)",
                "POWER_LOTTO": "T=C(38,6)x8; W=8sum[k=3..6]C(6,k)C(32,6-k)+C(6,1)C(32,5)+C(6,2)C(32,4)",
            },
            "identity_authority": IDENTITY_ARTIFACT_PATH,
            "actual_distinct_ticket_counts_used": used_counts_by_lottery,
            "independence_only_where_proven": True,
        },
        "analytic_random_baselines": baselines,
        "exact_null_probability_diagnostics": null_diagnostics,
        "statistical_methods": {
            "primary_test": "one-sided upper-tail (observed >= governed random baseline)",
            "constant_per_draw_null_probability": "exact binomial upper tail",
            "variable_per_draw_null_probability": "exact deterministic Poisson-binomial upper tail",
            "confidence_intervals": "Wilson score + exact Clopper-Pearson (95%)",
            "multiple_testing": "Bonferroni p = min(1, raw_p x 108)",
            "fdr": "Benjamini-Hochberg q=0.10 (descriptive only; cannot promote)",
            "negative_window_test": "one-sided lower-tail, Bonferroni-corrected (veto)",
            "monte_carlo_used": False,
        },
        "inference": {
            "family_size": CORRECTION_FAMILY_M,
            "n_groups": len(groups),
            "n_evaluable_windows": n_eval_windows,
            "n_windows": len(groups) * len(PRIMARY_WINDOWS),
            "groups": groups,
        },
        "summary": {
            "window_decision_counts": window_decision_counts,
            "group_decision_counts": group_decision_counts,
            "stability_counts": stability_counts,
            "go_candidate_research_only_groups": [
                {"lottery_type": g["lottery_type"], "strategy_id": g["strategy_id"]}
                for g in groups if g["overall_group_decision"] == "GO_CANDIDATE_RESEARCH_ONLY"
            ],
            "correction_surviving_edge_found": any(
                w["window_decision"] == "PRIZE_AWARE_EDGE_CORRECTION_SURVIVING"
                for g in groups for w in g["windows"]),
            "preliminary_independent_null_candidates": len(
                provisional_candidates
            ),
        },
        "preliminary_result_reconciliation": {
            "status": "PROVISIONAL_INDEPENDENT_NULL_REJECTED",
            "independent_approximation_is_final_result": False,
            "candidates": provisional_candidates,
        },
        "overall_project_classification": overall_project,
        "prediction_success_claim": False,
        "prediction_success_basis": (
            "Retrospective descriptive/inferential validation only; the overall "
            "project classification reflects the prize-aware evidence tier, not a "
            "predictive-edge or deployment claim."
        ),
        "governance": {
            "production_db_path": PRODUCTION_DB_PATH,
            "production_db_opened": False,
            "production_db_queried": False,
            "production_db_written": False,
            "observed_counts_artifacts_modified": False,
            "identity_artifact_modified": False,
            "export_module_or_tests_modified": False,
            "scorer_or_adapter_modified": False,
            "package_or_ci_config_changed": False,
            "registry_mutated": False,
            "production_apply": False,
            "controlled_apply_or_migration_or_deploy": False,
            "service_or_process_control": False,
            "strategy_reselection": False,
            "prospective_activation": False,
            "feature_mining_started": False,
            "p273b_started": False,
            "production_apply_readiness": "NOT_READY_FOR_APPLY",
        },
        "validation_plan": {
            "focused_tests": "tests/test_p273a_prize_aware_inferential_validation.py",
            "full_repo_suite": "NOT RUN",
            "deterministic_regeneration": "byte-identical on re-run (fixed date; immutable inputs)",
        },
        "disclaimers": list(DISCLAIMERS),
        "modified_files": [
            "analysis/p273a_prize_aware_inferential_validation.py",
            "tests/test_p273a_prize_aware_inferential_validation.py",
            "outputs/research/p273a_prize_aware_inferential_validation_20260615.json",
            "outputs/research/p273a_prize_aware_inferential_validation_20260615.md",
            "00-Plan/roadmap/active_task.md",
            "00-Plan/roadmap/agent_bootstrap/CURRENT_STATE.md",
        ],
    }
    if overall_project == "PRIZE_AWARE_EDGE_CORRECTION_SURVIVING":
        report["final_classification"] = (
            "P273A_DISTINCT_TICKET_INFERENCE_COMPLETE_EDGE_SURVIVES_RESEARCH_ONLY"
        )
    elif overall_project == "PRIZE_AWARE_INSUFFICIENT_SUPPORT":
        report["final_classification"] = (
            "P273A_DISTINCT_TICKET_INFERENCE_COMPLETE_INSUFFICIENT_SUPPORT"
        )
    else:
        report["final_classification"] = (
            "P273A_DISTINCT_TICKET_INFERENCE_COMPLETE_EDGE_DOES_NOT_SURVIVE"
        )
    report["canonical_payload_digest"] = compute_report_digest(report)
    return report


# --------------------------------------------------------------------------- #
# Markdown rendering (deterministic; derived from the report dict)            #
# --------------------------------------------------------------------------- #

def render_markdown(report: Dict[str, object]) -> str:
    wp = report["window_policy"]
    cf = report["correction_family"]
    bl = report["analytic_random_baselines"]
    summ = report["summary"]
    lines: List[str] = []
    A = lines.append
    A("# P273A Exact Distinct-Ticket Prize-Aware Inference")
    A("")
    A(f"**Task:** `{report['task_id']}`")
    A(f"**Generated:** {report['generated_date']}")
    A(f"**Policy:** `{report['policy_version']}`")
    A(f"**Branch:** `{report['branch']}` (base `{report['base_origin_main']}`)")
    A(f"**Overall project classification:** `{report['overall_project_classification']}`")
    A(f"**Final classification:** `{report['final_classification']}`")
    A(f"**Canonical payload digest:** `{report['canonical_payload_digest']}`")
    A("")
    A("> Retrospective research only. A descriptive observed rate is NOT a predictive "
      "edge. NULL and INSUFFICIENT_SUPPORT are valid, successful outcomes. 1500/all-history "
      "are reference-only and never drive a primary decision. SHORT-50 is a guardrail and "
      "can never independently trigger an EDGE or a GO candidate. No production apply, no "
      "prospective activation, no strategy reselection, no P273B. The production DB was "
      "never opened, queried, or written. Final inference uses the exact distinct-ticket "
      "without-replacement null; the independent approximation is rejected.")
    A("")
    A("## 1. Primary question")
    A("")
    A(str(report["primary_question"]))
    A("")
    A("## 2. Window policy (owner-approved)")
    A("")
    A(f"- **Primary decision windows:** "
      + ", ".join(f"{w} ({PRIMARY_WINDOW_LABELS[w]})" for w in PRIMARY_WINDOWS))
    A(f"- **Reference-only (excluded from every primary decision):** "
      + "; ".join(wp["reference_only_descriptions"]))
    A(f"- **Reference-only prohibited uses:** " + ", ".join(wp["reference_only_prohibited_uses"]))
    A(f"- **Forbidden primary windows:** {wp['forbidden_primary_windows']}")
    A("")
    A("## 3. Frozen setup (no outcome-based reselection)")
    A("")
    A(f"- **Lotteries:** {', '.join(LOTTERIES)}")
    A(f"- **Unit:** {report['frozen_setup']['analysis_unit']}; **Outcome:** {report['frozen_setup']['outcome']}")
    A(f"- **Strategy universe:** {cf['strategy_lottery_cells']} cells "
      f"(`{STRATEGY_CELL_SOURCE}`, sha256 `{STRATEGY_CELL_SOURCE_SHA[:16]}…`)")
    A(f"- **Primary observed counts:** `{report['input_contract']['primary_observed_counts_path']}` "
      f"(digest `{report['input_contract']['primary_observed_counts_digest'][:16]}…`)")
    A(f"- **Distinct-ticket identities:** `{report['input_contract']['identity_artifact_path']}` "
      f"(digest `{report['input_contract']['identity_artifact_digest'][:16]}…`)")
    A("")
    A("| Lottery | Endpoint | Condition |")
    A("|---|---|---|")
    for lottery in LOTTERIES:
        e = ENDPOINTS[lottery]
        A(f"| {lottery} | `{e['name']}` | `{e['condition']}` |")
    A("")
    A("## 4. Correction family and gates")
    A("")
    A(f"- Family = (strategy x lottery) x primary window = {cf['strategy_lottery_cells']} x "
      f"{cf['primary_windows']} = **{cf['family_m']}** hypotheses (fixed; no post-outcome shrinkage)")
    A(f"- Family alpha = {cf['family_alpha']}; Bonferroni per-test alpha = {cf['bonferroni_alpha_per_test']}; "
      f"BH-FDR q = {cf['bh_fdr_q_descriptive_only']} (descriptive only)")
    A(f"- Minimum-support rule: support_draws >= {MIN_SUPPORT_DRAWS} AND expected_successes >= {MIN_EXPECTED_SUCCESSES}")
    A("")
    A("**Stability rule (owner pre-registered, frozen before outcomes):**")
    A("")
    for crit in STABILITY_RULE["criteria"]:
        A(f"- {crit}")
    A("")
    A("## 5. Exact distinct-ticket null")
    A("")
    A("Final per-draw null: `q_N = 1 - C(T-W,N) / C(T,N)`. Actual `N` comes "
      "from each supported draw in the immutable identity artifact.")
    A("")
    A("| Lottery | T total identities | W winning identities | W/T |")
    A("|---|---:|---:|---:|")
    for lottery in LOTTERIES:
        A(f"| {lottery} | {bl[lottery]['total_ticket_identities']} | "
          f"{bl[lottery]['winning_ticket_identities']} | "
          f"{bl[lottery]['ticket_baseline']:.12f} |")
    A("")
    A("Exact versus rejected independent approximation for every used N:")
    A("")
    A("| Lottery | N | q_distinct | q_independent (rejected) | Abs diff | Rel diff |")
    A("|---|---:|---:|---:|---:|---:|")
    for lottery in LOTTERIES:
        for diagnostic in report["exact_null_probability_diagnostics"][lottery]:
            A(f"| {lottery} | {diagnostic['distinct_ticket_count']} | "
              f"{diagnostic['q_distinct']:.12f} | "
              f"{diagnostic['q_independent_rejected']:.12f} | "
              f"{diagnostic['absolute_difference']:.12g} | "
              f"{diagnostic['relative_difference']:.12g} |")
    A("")
    A("## 6. Result summary")
    A("")
    A(f"- **Overall project classification:** `{report['overall_project_classification']}`")
    A(f"- **Evaluable primary windows:** {report['inference']['n_evaluable_windows']} / "
      f"{report['inference']['n_windows']}")
    A(f"- **Correction-surviving edge found:** {summ['correction_surviving_edge_found']}")
    A(f"- **Stability:** PASS={summ['stability_counts']['STABILITY_PASS']}, "
      f"FAIL={summ['stability_counts']['STABILITY_FAIL']}")
    A("")
    A("Per-window decision counts:")
    A("")
    A("| Decision | Count |")
    A("|---|---|")
    for k in sorted(summ["window_decision_counts"]):
        A(f"| `{k}` | {summ['window_decision_counts'][k]} |")
    A("")
    A("Overall group decision counts:")
    A("")
    A("| Group decision | Count |")
    A("|---|---|")
    for k in sorted(summ["group_decision_counts"]):
        A(f"| `{k}` | {summ['group_decision_counts'][k]} |")
    A("")
    go = summ["go_candidate_research_only_groups"]
    A(f"GO_CANDIDATE_RESEARCH_ONLY groups: **{len(go)}**"
      + ("" if not go else " — " + ", ".join(f"{g['lottery_type']}/{g['strategy_id']}" for g in go)))
    A("")
    A("## 7. Rejected provisional-result reconciliation")
    A("")
    reconciliation = report["preliminary_result_reconciliation"]
    A(f"- Status: `{reconciliation['status']}`")
    A(f"- Provisionally promoted groups audited: **{len(reconciliation['candidates'])}**")
    A("")
    A("| Lottery | Strategy | Rejected stability | Exact stability | Transition |")
    A("|---|---|---|---|---|")
    for candidate in reconciliation["candidates"]:
        A(f"| {candidate['lottery_type']} | {candidate['strategy_id']} | "
          f"{candidate['rejected_independent_stability']} | "
          f"{candidate['exact_distinct_stability']} | "
          f"`{candidate['classification_transition']}` |")
    A("")
    for candidate in reconciliation["candidates"]:
        A(f"### {candidate['lottery_type']} / {candidate['strategy_id']}")
        A("")
        A("| Window | Support | Observed | Distinct N dist | Old base | Exact base | "
          "Old exp | Exact exp | Old raw p | Exact raw p | Old Bonf p | "
          "Exact Bonf p | Old decision | Exact decision |")
        A("|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|")
        for window in candidate["windows"]:
            A(f"| {window['window']} | {window['support_draws']} | "
              f"{window['observed_successes']} | "
              f"`{json.dumps(window['distinct_ticket_count_distribution'], sort_keys=True)}` | "
              f"{window['rejected_independent_baseline_rate']:.12f} | "
              f"{window['exact_distinct_baseline_rate']:.12f} | "
              f"{window['rejected_independent_expected_successes']:.8f} | "
              f"{window['exact_distinct_expected_successes']:.8f} | "
              f"{window['rejected_independent_raw_p_value']:.8g} | "
              f"{window['exact_distinct_raw_p_value']:.8g} | "
              f"{window['rejected_independent_bonferroni_p_value']:.8g} | "
              f"{window['exact_distinct_bonferroni_p_value']:.8g} | "
              f"`{window['rejected_independent_window_decision']}` | "
              f"`{window['exact_distinct_window_decision']}` |")
        A("")
    A("## 8. Per-cell primary-window inference (all 108 windows)")
    A("")
    A("Columns: support / observed / distinct-ticket distribution / obs-rate / "
      "exact baseline-rate / excess(pp) / raw-p(upper) / Bonferroni-p / "
      "stat-status / decision. SHORT rows are guardrail-only.")
    A("")
    A("| Lottery | Strategy | Win | Lbl | Supp | Obs | Distinct N | ObsRate | "
      "Exact Base | Excess(pp) | RawP | BonfP | Status | Decision | Stability |")
    A("|---|---|---|---|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|")
    for g in report["inference"]["groups"]:
        stab = g["stability"]["status"]
        for w in g["windows"]:
            if w["evaluable"]:
                A(f"| {g['lottery_type']} | {g['strategy_id']} | {w['window']} | {w['window_label']} | "
                  f"{w['support_draws']} | {w['observed_successes']} | "
                  f"`{json.dumps(w['distinct_ticket_count_distribution'], sort_keys=True)}` | "
                  f"{w['observed_rate']:.4f} | "
                  f"{w['mean_baseline_rate']:.4f} | {w['absolute_excess_pp']:+.4f} | "
                  f"{w['raw_p_value_one_sided_upper']:.4g} | {w['bonferroni_p_value']:.4g} | "
                  f"{w['statistical_status']} | `{w['window_decision']}` | {stab} |")
            else:
                A(f"| {g['lottery_type']} | {g['strategy_id']} | {w['window']} | {w['window_label']} | "
                  f"{w['support_draws']} | {w['observed_successes']} | "
                  f"`{json.dumps(w['distinct_ticket_count_distribution'], sort_keys=True)}` | "
                  f"— | — | — | — | — | "
                  f"{w['support_status']} | `{w['window_decision']}` | {stab} |")
    A("")
    A("## 9. Disclaimers")
    A("")
    for d in report["disclaimers"]:
        A(f"- {d}")
    A("")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Artifact writers / entry point                                              #
# --------------------------------------------------------------------------- #

JSON_ARTIFACT = "outputs/research/p273a_prize_aware_inferential_validation_20260615.json"
MD_ARTIFACT = "outputs/research/p273a_prize_aware_inferential_validation_20260615.md"


def write_artifacts(json_path: str = JSON_ARTIFACT, md_path: str = MD_ARTIFACT,
                    primary_path: str = PRIMARY_OBSERVED_COUNTS_PATH,
                    expected_digest: Optional[str] = PRIMARY_OBSERVED_COUNTS_DIGEST) -> Dict[str, object]:
    report = build_report(primary_path, expected_digest)
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write(render_markdown(report))
    return report


if __name__ == "__main__":
    rep = write_artifacts()
    print("P273A primary-window inference artifacts regenerated:", JSON_ARTIFACT, MD_ARTIFACT)
    print("overall_project_classification:", rep["overall_project_classification"])
    print("final_classification:", rep["final_classification"])
