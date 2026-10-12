"""P279B frozen DAILY_539 disjoint-block diversified-baseline falsification.

This module consumes five committed JSON artifacts and performs pure,
deterministic calculations. It never opens a database, reconstructs an
outcome, generates a prediction, uses a service, or touches a registry.

The study is retrospective falsification only. Its labels cannot confirm
future prediction success, promote a strategy, or authorize deployment.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from collections import Counter
from fractions import Fraction
from itertools import combinations
from pathlib import Path
from typing import Any, Iterable, Sequence


TASK_ID = "P279B_FROZEN_DAILY539_DISJOINT_BLOCK_DIVERSIFIED_BASELINE_FALSIFICATION"
SOURCE_COMMIT = "8004c32c47cb99576ef5689f967c05306a83670c"
GENERATED_AT = "2026-06-18"
REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_JSON_PATH = (
    "outputs/research/"
    "p279b_disjoint_block_diversified_baseline_falsification_20260618.json"
)
DEFAULT_MD_PATH = (
    "outputs/research/"
    "p279b_disjoint_block_diversified_baseline_falsification_20260618.md"
)

LOTTERY_TYPE = "DAILY_539"
ENDPOINT_ID = "D539_ANY_PRIZE_AWARE_WIN"
ENDPOINT_SUCCESS_RULE = "hit_count >= 2; at most one success per draw per candidate"
DRAW_NUMBER_MAX = 39
DRAW_PICK_COUNT = 5
UNIVERSE_SIZE = math.comb(DRAW_NUMBER_MAX, DRAW_PICK_COUNT)
WINNING_TICKET_IDENTITIES = 65_621

PRIMARY_BLOCKS = (("P250", 250), ("P450", 450))
DIAGNOSTIC_BLOCK = ("D50", 50)
FAMILY_SIZE = 6
FAMILY_ALPHA = 0.05
BONFERRONI_ALPHA = FAMILY_ALPHA / FAMILY_SIZE

DECISION_RETAIN = "RETROSPECTIVE_STABILITY_NOT_FALSIFIED_RETAIN_FOR_FUTURE_ONLY"
DECISION_INCONCLUSIVE = "RETROSPECTIVE_STABILITY_INCONCLUSIVE"
DECISION_FALSIFIED = "RETROSPECTIVE_STABILITY_FALSIFIED"

CANDIDATES = (
    {"lottery_type": LOTTERY_TYPE, "strategy_id": "acb_markov_midfreq_3bet", "ticket_budget": 3},
    {"lottery_type": LOTTERY_TYPE, "strategy_id": "daily539_f4cold_3bet", "ticket_budget": 3},
    {"lottery_type": LOTTERY_TYPE, "strategy_id": "daily539_f4cold_5bet", "ticket_budget": 5},
)

EXPECTED_DISJOINT_COUNTS = {
    "acb_markov_midfreq_3bet": {"D50": 18, "P250": 102, "P450": 148},
    "daily539_f4cold_3bet": {"D50": 23, "P250": 78, "P450": 174},
    "daily539_f4cold_5bet": {"D50": 35, "P250": 135, "P450": 255},
}

SOURCE_SPECS = {
    "primary_observed_counts": {
        "path": "outputs/research/p273a_primary_window_observed_counts_20260615.json",
        "raw_sha256": "14b2ed29628111f32925909ba07e9be0b3de48a04ee4b0877e39c1dfa4e51b73",
        "canonical_payload_digest": "65a4cc59f5ab64d685890566e38493b0295e622f351e0527782f1dce2f38645f",
        "digest_excludes": (
            "canonical_payload_digest", "connection_uri", "generated_at",
            "source_db_path", "transaction_end_at", "transaction_start_at",
        ),
    },
    "distinct_ticket_identity": {
        "path": "outputs/research/p273a_distinct_ticket_identity_20260615.json",
        "raw_sha256": "b10b916c00f807ace7342250b788dbf1d62c12a0b8e2d5aa627b5a4eb25089b0",
        "canonical_payload_digest": "ad85e447dfc7db7afd70e9fdde928bb12a2ae367d6c1f23f14b7e3504701ae51",
        "digest_excludes": (
            "canonical_payload_digest", "connection_uri", "generated_at",
            "source_db_path", "transaction_end_at", "transaction_start_at",
        ),
    },
    "inferential_validation": {
        "path": "outputs/research/p273a_prize_aware_inferential_validation_20260615.json",
        "raw_sha256": "ab923a06327afcc8595f224e65bcd98fec0cfdeaf31b10aeeb86ac54ed6648fe",
        "canonical_payload_digest": "5666e67c88e5f3b1233f2d6d5a5f86746c4f7605ae98bda3f2d59ec5aa0b2fb4",
        "digest_excludes": ("canonical_payload_digest",),
    },
    "unified_success_matrix": {
        "path": "outputs/research/p275b_unified_prize_aware_success_matrix_20260616.json",
        "raw_sha256": "0a81b9e652b5d84e80ebf16e9d5c5ff625746d8c46e6cfe5d38e6cfe312cf964",
        "canonical_payload_digest": "c1b99e57024f528e39e4beeca03cb22dd3278eb1d356aafbe48d8485695102f6",
        "digest_excludes": ("canonical_payload_digest", "generated_at"),
    },
    "coverage_complementarity": {
        "path": "outputs/research/p276b_fixed_n_coverage_complementarity_20260617.json",
        "raw_sha256": "ed6ba267de53443c46ecff76914887a4595aaaa2762fa31ed46d602b7fac3264",
        "canonical_payload_digest": "438dca463edb574a3ed346ac616728d4621e669d25f010efeb9909478d68657e",
        "digest_excludes": ("canonical_payload_digest", "generated_at"),
    },
}

CANONICAL_TICKET_FAMILY = (
    (1, 2, 3, 4, 5),
    (6, 7, 8, 9, 10),
    (11, 12, 13, 14, 15),
    (16, 17, 18, 19, 20),
    (21, 22, 23, 24, 25),
)

ALTERNATIVE_TICKET_FAMILIES = {
    "SHIFTED_CONTIGUOUS": (
        (2, 3, 4, 5, 6), (7, 8, 9, 10, 11), (12, 13, 14, 15, 16),
        (17, 18, 19, 20, 21), (22, 23, 24, 25, 26),
    ),
    "INTERLEAVED_LABELS": (
        (1, 6, 11, 16, 21), (2, 7, 12, 17, 22), (3, 8, 13, 18, 23),
        (4, 9, 14, 19, 24), (5, 10, 15, 20, 25),
    ),
    "REVERSED_LABELS": (
        (39, 38, 37, 36, 35), (34, 33, 32, 31, 30),
        (29, 28, 27, 26, 25), (24, 23, 22, 21, 20),
        (19, 18, 17, 16, 15),
    ),
}

_SELF_DIGEST_EXCLUDES = frozenset({"canonical_payload_digest", "generated_at"})


class P279BError(RuntimeError):
    """Fail-closed study error."""


class SourceIntegrityError(P279BError):
    """A committed source artifact failed identity or semantic verification."""


def repository_path(relative_path: str) -> Path:
    """Resolve a repository-relative path and reject absolute/traversal paths."""
    candidate = Path(relative_path)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError(f"path must be repository-relative: {relative_path!r}")
    resolved = (REPO_ROOT / candidate).resolve()
    if REPO_ROOT.resolve() not in resolved.parents and resolved != REPO_ROOT.resolve():
        raise ValueError(f"path escapes repository: {relative_path!r}")
    return resolved


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _strip_keys(value: Any, excludes: set[str] | frozenset[str]) -> Any:
    if isinstance(value, dict):
        return {
            key: _strip_keys(item, excludes)
            for key, item in value.items()
            if key not in excludes
        }
    if isinstance(value, list):
        return [_strip_keys(item, excludes) for item in value]
    return value


def canonical_digest(value: Any, excludes: Iterable[str] = ()) -> str:
    payload = _strip_keys(copy.deepcopy(value), set(excludes))
    blob = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def load_and_verify_sources() -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    documents: dict[str, dict[str, Any]] = {}
    provenance: list[dict[str, Any]] = []
    if len(SOURCE_SPECS) != 5:
        raise SourceIntegrityError("exactly five committed source artifacts are required")
    for source_id, spec in SOURCE_SPECS.items():
        path = repository_path(spec["path"])
        raw = sha256_file(path)
        if raw != spec["raw_sha256"]:
            raise SourceIntegrityError(f"{source_id} raw SHA-256 mismatch: {raw}")
        with path.open("r", encoding="utf-8") as handle:
            document = json.load(handle)
        computed = canonical_digest(document, spec["digest_excludes"])
        embedded = document.get("canonical_payload_digest")
        if computed != embedded or computed != spec["canonical_payload_digest"]:
            raise SourceIntegrityError(
                f"{source_id} canonical digest mismatch: computed={computed}, embedded={embedded}"
            )
        documents[source_id] = document
        provenance.append({
            "source_id": source_id,
            "path": spec["path"],
            "raw_sha256": raw,
            "canonical_payload_digest": computed,
            "digest_verified": True,
        })
    return documents, provenance


def _candidate_key(candidate: dict[str, Any]) -> tuple[str, str]:
    return candidate["lottery_type"], candidate["strategy_id"]


def verify_frozen_candidate_family(documents: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    expected_keys = [_candidate_key(candidate) for candidate in CANDIDATES]
    inference = documents["inferential_validation"]
    frozen = [
        (item["lottery_type"], item["strategy_id"])
        for item in inference["summary"]["go_candidate_research_only_groups"]
    ]
    if frozen != expected_keys:
        raise SourceIntegrityError(f"frozen P273A candidate family mismatch: {frozen}")

    identity_cells = {
        (cell["lottery_type"], cell["strategy_id"]): cell
        for cell in documents["distinct_ticket_identity"]["cells"]
    }
    p275_rows = documents["unified_success_matrix"]["matrix_rows"]
    verified = []
    for candidate in CANDIDATES:
        key = _candidate_key(candidate)
        budget = candidate["ticket_budget"]
        cell = identity_cells.get(key)
        if cell is None:
            raise SourceIntegrityError(f"missing identity cell: {key}")
        identity_supports = {}
        for window in cell["windows"]:
            support = window["support_draws"]
            expected_distribution = {str(budget): support}
            if window["distinct_ticket_count_distribution"] != expected_distribution:
                raise SourceIntegrityError(
                    f"identity budget mismatch for {key} w{window['window']}"
                )
            identity_supports[str(window["window"])] = support
        rows = [
            row for row in p275_rows
            if (row["lottery_type"], row["strategy_id"]) == key
        ]
        if len(rows) != 3 or any(row["ticket_budget"] != budget for row in rows):
            raise SourceIntegrityError(f"P275B ticket budget mismatch for {key}")
        verified.append({
            **candidate,
            "identity_supports": identity_supports,
            "identity_budget_verified": True,
            "p275b_budget_verified": True,
        })
    return verified


def derive_disjoint_counts(
    documents: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    cells = {
        (cell["lottery_type"], cell["strategy_id"]): cell
        for cell in documents["primary_observed_counts"]["cells"]
    }
    result = []
    for candidate in CANDIDATES:
        key = _candidate_key(candidate)
        cell = cells.get(key)
        if cell is None:
            raise SourceIntegrityError(f"missing observed-count cell: {key}")
        windows = {int(item["window"]): item for item in cell["windows"]}
        if tuple(sorted(windows)) != (50, 300, 750):
            raise SourceIntegrityError(f"nested window mismatch for {key}")
        nested: dict[str, dict[str, int]] = {}
        for size in (50, 300, 750):
            item = windows[size]
            count = item["observed_successes"]
            support = item["support_draws"]
            if support != size or isinstance(count, bool) or not isinstance(count, int):
                raise SourceIntegrityError(f"invalid nested support/count for {key} w{size}")
            if count < 0 or count > support or item["endpoint_id"] != ENDPOINT_ID:
                raise SourceIntegrityError(f"invalid endpoint/count for {key} w{size}")
            nested[f"latest_{size}"] = {"support": support, "successes": count}
        derived = {
            "D50": nested["latest_50"]["successes"],
            "P250": nested["latest_300"]["successes"] - nested["latest_50"]["successes"],
            "P450": nested["latest_750"]["successes"] - nested["latest_300"]["successes"],
        }
        if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in derived.values()):
            raise SourceIntegrityError(f"invalid disjoint subtraction for {key}: {derived}")
        if derived != EXPECTED_DISJOINT_COUNTS[candidate["strategy_id"]]:
            raise SourceIntegrityError(
                f"P279A expected count mismatch for {key}: actual={derived}"
            )
        recombination = {
            "D50_plus_P250_equals_latest_300": (
                derived["D50"] + derived["P250"] == nested["latest_300"]["successes"]
            ),
            "D50_plus_P250_plus_P450_equals_latest_750": (
                derived["D50"] + derived["P250"] + derived["P450"]
                == nested["latest_750"]["successes"]
            ),
        }
        if not all(recombination.values()):
            raise SourceIntegrityError(f"recombination failed for {key}")
        result.append({
            **candidate,
            "endpoint_id": ENDPOINT_ID,
            "nested_counts": nested,
            "derived_disjoint_counts": derived,
            "derived_block_supports": {"D50": 50, "P250": 250, "P450": 450},
            "nonnegative_integer_subtraction": True,
            "recombination": recombination,
            "expected_p279a_counts_matched": True,
        })
    return result


def validate_disjoint_ticket_family(
    ticket_family: Sequence[Sequence[int]], ticket_budget: int,
) -> None:
    tickets = [tuple(ticket) for ticket in ticket_family[:ticket_budget]]
    if len(tickets) != ticket_budget:
        raise P279BError(f"ticket family does not supply N={ticket_budget}")
    seen: set[int] = set()
    for ticket in tickets:
        if len(ticket) != 5 or len(set(ticket)) != 5:
            raise P279BError("each ticket must contain five distinct numbers")
        if any(number < 1 or number > DRAW_NUMBER_MAX for number in ticket):
            raise P279BError("ticket number outside DAILY_539 universe")
        if seen.intersection(ticket):
            raise P279BError("ticket family is not mutually disjoint")
        seen.update(ticket)


def exhaustive_diversified_success_count(
    ticket_family: Sequence[Sequence[int]], ticket_budget: int,
) -> tuple[int, int]:
    validate_disjoint_ticket_family(ticket_family, ticket_budget)
    tickets = [set(ticket) for ticket in ticket_family[:ticket_budget]]
    outcomes = 0
    successes = 0
    for draw in combinations(range(1, DRAW_NUMBER_MAX + 1), DRAW_PICK_COUNT):
        outcomes += 1
        draw_set = set(draw)
        if any(len(draw_set.intersection(ticket)) >= 2 for ticket in tickets):
            successes += 1
    if outcomes != UNIVERSE_SIZE:
        raise P279BError(f"enumerated universe {outcomes} != {UNIVERSE_SIZE}")
    return successes, outcomes


def build_exact_diversified_baselines() -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    families = {"CANONICAL": CANONICAL_TICKET_FAMILY, **ALTERNATIVE_TICKET_FAMILIES}
    family_counts: dict[str, dict[str, int]] = {}
    baselines: dict[str, dict[str, Any]] = {}
    for family_name, tickets in families.items():
        family_counts[family_name] = {}
        for budget in (3, 5):
            numerator, denominator = exhaustive_diversified_success_count(tickets, budget)
            family_counts[family_name][f"N{budget}"] = numerator
            if family_name == "CANONICAL":
                probability = Fraction(numerator, denominator)
                baselines[str(budget)] = {
                    "ticket_budget": budget,
                    "winning_outcome_count": numerator,
                    "total_outcome_count": denominator,
                    "reduced_numerator": probability.numerator,
                    "reduced_denominator": probability.denominator,
                    "probability": float(probability),
                    "algorithm": (
                        "Exhaustively enumerate C(39,5) draws and count a success "
                        "when any of N mutually disjoint five-number tickets overlaps the draw by >=2."
                    ),
                    "canonical_ticket_family": [list(ticket) for ticket in tickets[:budget]],
                }
    canonical_counts = family_counts["CANONICAL"]
    if any(counts != canonical_counts for counts in family_counts.values()):
        raise P279BError(f"permutation/relabeling symmetry failed: {family_counts}")
    symmetry = {
        "status": "PASS",
        "alternative_family_count": len(ALTERNATIVE_TICKET_FAMILIES),
        "family_winning_outcome_counts": family_counts,
        "proof": (
            "Every valid mutually disjoint N-ticket family is related by a permutation "
            "of the 39 number labels. Uniform five-number draws and the overlap>=2 union "
            "event are invariant under that bijection, so the winning-outcome count is unchanged."
        ),
    }
    return baselines, symmetry


def build_ordinary_random_baselines(
    documents: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    groups = {
        (group["lottery_type"], group["strategy_id"]): group
        for group in documents["inferential_validation"]["inference"]["groups"]
    }
    result = {}
    for budget in (3, 5):
        numerator = math.comb(UNIVERSE_SIZE, budget) - math.comb(
            UNIVERSE_SIZE - WINNING_TICKET_IDENTITIES, budget
        )
        denominator = math.comb(UNIVERSE_SIZE, budget)
        probability = Fraction(numerator, denominator)
        source_rates = []
        for candidate in CANDIDATES:
            if candidate["ticket_budget"] != budget:
                continue
            group = groups[_candidate_key(candidate)]
            source_rates.extend(float(window["mean_baseline_rate"]) for window in group["windows"])
        reproduced = all(abs(rate - float(probability)) <= 5e-13 for rate in source_rates)
        if not reproduced:
            raise SourceIntegrityError(f"P273 ordinary-random baseline mismatch for N={budget}")
        result[str(budget)] = {
            "ticket_budget": budget,
            "formula": "1 - C(T-W,N) / C(T,N)",
            "T": UNIVERSE_SIZE,
            "W": WINNING_TICKET_IDENTITIES,
            "reduced_numerator": probability.numerator,
            "reduced_denominator": probability.denominator,
            "probability": float(probability),
            "committed_p273_values": sorted(set(source_rates)),
            "committed_p273_reproduced": True,
            "role": "SECONDARY_SENSITIVITY_ONLY",
        }
    return result


def wilson_interval(successes: int, trials: int, z: float = 1.959963984540054) -> list[float]:
    proportion = successes / trials
    denominator = 1.0 + z * z / trials
    center = (proportion + z * z / (2 * trials)) / denominator
    half = z * math.sqrt(
        proportion * (1.0 - proportion) / trials + z * z / (4 * trials * trials)
    ) / denominator
    return [max(0.0, center - half), min(1.0, center + half)]


def reconcile_p276_monte_carlo(
    documents: dict[str, dict[str, Any]], exact_baselines: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    p276 = documents["coverage_complementarity"]
    specification = p276["baseline_specification"]
    description = specification["diversified_random"]
    if "disjoint blocks" not in description or "maximizing number coverage" not in description:
        raise SourceIntegrityError("P276 diversified baseline semantics changed")
    if p276.get("scoring_version") != "prize_aware_v1":
        raise SourceIntegrityError("P276 prize-aware scoring version changed")
    scope = p276.get("scope", {})
    if scope.get("primary_lottery") != LOTTERY_TYPE or scope.get(
        "primary_fixed_ticket_budgets"
    ) != [3, 5]:
        raise SourceIntegrityError("P276 primary lottery or fixed-N budgets changed")
    single_rows = {
        row["source_cells"][0]: row
        for row in p276["portfolio_results"]
        if row.get("lottery_type") == LOTTERY_TYPE
        and row.get("kind") == "SINGLE"
        and len(row.get("source_cells", [])) == 1
    }
    expected_strategy_ids = {candidate["strategy_id"] for candidate in CANDIDATES}
    if not expected_strategy_ids.issubset(single_rows):
        raise SourceIntegrityError("P276 is missing a frozen single-candidate comparator")
    records = {}
    for budget in (3, 5):
        stored = specification["baseline_Q"][f"DAILY_539|N{budget}"]["diversified"]
        if stored["mean_pairwise_overlap"] != 0.0:
            raise SourceIntegrityError(f"P276 N={budget} diversified tickets are not disjoint")
        sample_count = int(stored["n_samples"])
        stored_probability = float(stored["prize_Q"])
        success_count = round(stored_probability * sample_count)
        if abs(success_count / sample_count - stored_probability) > 1e-15:
            raise SourceIntegrityError(f"P276 N={budget} MC count is not recoverable")
        interval = wilson_interval(success_count, sample_count)
        exact_probability = exact_baselines[str(budget)]["probability"]
        standard_error = math.sqrt(
            stored_probability * (1.0 - stored_probability) / sample_count
        )
        inside = interval[0] <= exact_probability <= interval[1]
        if not inside:
            raise SourceIntegrityError(f"P276 N={budget} MC baseline is irreconcilable")
        verified_rows = []
        for candidate in CANDIDATES:
            if candidate["ticket_budget"] != budget:
                continue
            row = single_rows[candidate["strategy_id"]]
            if row["ticket_budget"] != budget:
                raise SourceIntegrityError(
                    f"P276 budget mismatch for {candidate['strategy_id']}"
                )
            window_baselines = {
                str(window["window"]): float(
                    window["prize_aware"]["random_baselines"]["diversified"]
                    ["baseline_union_win_probability"]
                )
                for window in row["windows"]
            }
            if tuple(sorted(map(int, window_baselines))) != (50, 300, 750) or any(
                value != stored_probability for value in window_baselines.values()
            ):
                raise SourceIntegrityError(
                    f"P276 prize-aware baseline mismatch for {candidate['strategy_id']}"
                )
            verified_rows.append({
                "strategy_id": candidate["strategy_id"],
                "portfolio_id": row["portfolio_id"],
                "ticket_budget": row["ticket_budget"],
                "windows": window_baselines,
            })
        records[str(budget)] = {
            "ticket_budget": budget,
            "p276_stored_probability": stored_probability,
            "p276_sample_count": sample_count,
            "p276_implied_success_count": success_count,
            "derived_wilson_95_interval": interval,
            "monte_carlo_standard_error": standard_error,
            "exact_probability": exact_probability,
            "exact_minus_mc": exact_probability - stored_probability,
            "standardized_difference": (
                (exact_probability - stored_probability) / standard_error
            ),
            "p276_prize_aware_single_candidate_rows_verified": verified_rows,
            "exact_inside_derived_mc_interval": True,
            "status": "RECONCILED_EXACT_SUPERSEDES_MC_FOR_P279B_ONLY",
        }
    return {
        "status": "PASS",
        "same_endpoint": ENDPOINT_ID,
        "same_equal_ticket_budgets": [3, 5],
        "p276_algorithm": description,
        "note": (
            "P276 stores each Monte Carlo estimate and sample size, not an explicit interval. "
            "P279B derives the reported Wilson 95% Monte Carlo interval from those committed values."
        ),
        "by_ticket_budget": records,
    }


def binomial_probability(successes: int, trials: int, probability: float) -> float:
    return (
        math.comb(trials, successes)
        * probability ** successes
        * (1.0 - probability) ** (trials - successes)
    )


def exact_two_sided_binomial_pvalue(
    successes: int, trials: int, probability: float,
) -> float:
    """Probability-ordering two-sided exact binomial p-value.

    This is equivalent to scipy.stats.binomtest(..., alternative="two-sided")
    for this study. The tolerance only absorbs floating-point evaluation noise
    when two binomial probabilities are mathematically equal.
    """
    if isinstance(successes, bool) or not isinstance(successes, int):
        raise ValueError("successes must be an integer")
    if isinstance(trials, bool) or not isinstance(trials, int):
        raise ValueError("trials must be an integer")
    if trials < 0 or successes < 0 or successes > trials:
        raise ValueError("require 0 <= successes <= trials")
    if not 0.0 <= probability <= 1.0:
        raise ValueError("probability must be in [0,1]")
    if probability in (0.0, 1.0):
        expected = 0 if probability == 0.0 else trials
        return 1.0 if successes == expected else 0.0
    observed_probability = binomial_probability(successes, trials, probability)
    tolerance = observed_probability * 1e-12
    included = (
        binomial_probability(value, trials, probability)
        for value in range(trials + 1)
        if binomial_probability(value, trials, probability)
        <= observed_probability + tolerance
    )
    return min(1.0, math.fsum(included))


def direction(observed_rate: float, baseline_probability: float) -> str:
    if observed_rate > baseline_probability:
        return "POSITIVE"
    if observed_rate < baseline_probability:
        return "NEGATIVE"
    return "EQUAL"


def build_test_result(
    strategy_id: str, ticket_budget: int, block: str, trials: int,
    successes: int, baseline_probability: float, inferential: bool,
) -> dict[str, Any]:
    observed_rate = successes / trials
    raw_p = exact_two_sided_binomial_pvalue(successes, trials, baseline_probability)
    return {
        "lottery_type": LOTTERY_TYPE,
        "strategy_id": strategy_id,
        "ticket_budget": ticket_budget,
        "block": block,
        "n": trials,
        "k": successes,
        "observed_rate": observed_rate,
        "baseline_probability": baseline_probability,
        "absolute_excess": observed_rate - baseline_probability,
        "direction": direction(observed_rate, baseline_probability),
        "test": "EXACT_TWO_SIDED_BINOMIAL_PROBABILITY_ORDERING",
        "raw_p_value": raw_p,
        "bonferroni_adjusted_p_value": min(1.0, raw_p * FAMILY_SIZE) if inferential else None,
        "passes_bonferroni_threshold": raw_p <= BONFERRONI_ALPHA if inferential else None,
        "included_in_m6_family": inferential,
    }


def classify_candidate(primary_results: Sequence[dict[str, Any]]) -> str:
    if len(primary_results) != 2:
        raise ValueError("candidate classification requires exactly P250 and P450")
    if any(item["direction"] in {"NEGATIVE", "EQUAL"} for item in primary_results):
        return DECISION_FALSIFIED
    if all(item["passes_bonferroni_threshold"] for item in primary_results):
        return DECISION_RETAIN
    return DECISION_INCONCLUSIVE


def build_sensitivity_results(
    disjoint_counts: Sequence[dict[str, Any]],
    ordinary_baselines: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    results = []
    for candidate in disjoint_counts:
        probability = ordinary_baselines[str(candidate["ticket_budget"])]["probability"]
        counts = candidate["derived_disjoint_counts"]
        for block, trials in (DIAGNOSTIC_BLOCK, *PRIMARY_BLOCKS):
            results.append(build_test_result(
                candidate["strategy_id"], candidate["ticket_budget"], block,
                trials, counts[block], probability, inferential=False,
            ))
    return results


def build_artifact() -> dict[str, Any]:
    documents, source_provenance = load_and_verify_sources()
    candidates = verify_frozen_candidate_family(documents)
    disjoint_counts = derive_disjoint_counts(documents)
    exact_baselines, symmetry = build_exact_diversified_baselines()
    ordinary_baselines = build_ordinary_random_baselines(documents)
    reconciliation = reconcile_p276_monte_carlo(documents, exact_baselines)

    primary_results = []
    diagnostic_results = []
    candidate_decisions = []
    for candidate in disjoint_counts:
        probability = exact_baselines[str(candidate["ticket_budget"])]["probability"]
        counts = candidate["derived_disjoint_counts"]
        diagnostic_results.append(build_test_result(
            candidate["strategy_id"], candidate["ticket_budget"], "D50", 50,
            counts["D50"], probability, inferential=False,
        ))
        candidate_primary = []
        for block, trials in PRIMARY_BLOCKS:
            item = build_test_result(
                candidate["strategy_id"], candidate["ticket_budget"], block,
                trials, counts[block], probability, inferential=True,
            )
            primary_results.append(item)
            candidate_primary.append(item)
        candidate_decisions.append({
            "lottery_type": LOTTERY_TYPE,
            "strategy_id": candidate["strategy_id"],
            "ticket_budget": candidate["ticket_budget"],
            "decision": classify_candidate(candidate_primary),
            "retrospective_research_only": True,
        })

    decision_counts = Counter(item["decision"] for item in candidate_decisions)
    project_counts = {
        DECISION_RETAIN: decision_counts[DECISION_RETAIN],
        DECISION_INCONCLUSIVE: decision_counts[DECISION_INCONCLUSIVE],
        DECISION_FALSIFIED: decision_counts[DECISION_FALSIFIED],
    }
    report = {
        "task_id": TASK_ID,
        "artifact_version": "p279b_disjoint_block_diversified_baseline_falsification_v1",
        "generated_at": GENERATED_AT,
        "source_commit": SOURCE_COMMIT,
        "mode": "BOUNDED_RETROSPECTIVE_ARTIFACT_ONLY_FALSIFICATION",
        "scientific_question": (
            "Do the three frozen candidates retain positive prize-aware excess in both "
            "non-overlapping historical primary blocks versus an exact equal-budget "
            "maximally diversified random-ticket baseline?"
        ),
        "source_artifacts": source_provenance,
        "endpoint": {
            "lottery_type": LOTTERY_TYPE,
            "endpoint_id": ENDPOINT_ID,
            "success_rule": ENDPOINT_SUCCESS_RULE,
            "aggregate_counts_only": True,
        },
        "frozen_candidates": candidates,
        "disjoint_block_derivation": disjoint_counts,
        "baseline_contract": {
            "universe": "C(39,5)",
            "universe_size": UNIVERSE_SIZE,
            "primary": "EXACT_MAXIMALLY_DIVERSIFIED_MUTUALLY_DISJOINT_TICKETS",
            "secondary": "EXACT_ORDINARY_RANDOM_DISTINCT_TICKETS_SENSITIVITY_ONLY",
            "exact_diversified": exact_baselines,
            "symmetry_verification": symmetry,
            "p276_monte_carlo_reconciliation": reconciliation,
            "ordinary_random_sensitivity": ordinary_baselines,
        },
        "statistical_contract": {
            "primary_family": "3 candidates x 2 disjoint primary blocks",
            "family_size": FAMILY_SIZE,
            "family_alpha": FAMILY_ALPHA,
            "bonferroni_alpha_per_test": BONFERRONI_ALPHA,
            "test": "EXACT_TWO_SIDED_BINOMIAL_PROBABILITY_ORDERING",
            "d50_descriptive_only": True,
            "d50_included_in_family": False,
            "bh_fdr_reported": False,
        },
        "primary_test_results": primary_results,
        "diagnostic_d50_results": diagnostic_results,
        "ordinary_random_sensitivity_results": build_sensitivity_results(
            disjoint_counts, ordinary_baselines
        ),
        "candidate_decisions": candidate_decisions,
        "project_summary": {
            "candidate_count": len(candidate_decisions),
            "primary_test_count": len(primary_results),
            "diagnostic_d50_count": len(diagnostic_results),
            "decision_counts": project_counts,
            "research_verdict": "ONE_FALSIFIED_TWO_INCONCLUSIVE_ZERO_RETAINED",
            "final_research_classification": "RETROSPECTIVE_STABILITY_NOT_CONFIRMED",
        },
        "scientific_limitations": [
            "All blocks are retrospective and were derived from nested committed historical aggregates.",
            "The disjoint P250 and P450 blocks remove overlap but do not create prospective OOS evidence.",
            "The exact diversified baseline tests equal-budget number coverage, not every possible null model.",
            "D50 is descriptive only and cannot rescue, promote, or override either primary block.",
            "Candidate labels authorize future-only research at most; they do not establish betting value.",
        ],
        "safety_flags": {
            "prediction_success_claim": False,
            "strategy_promoted": False,
            "prospective_confirmation_complete": False,
            "deployment_authorized": False,
            "production_db_opened": False,
            "production_db_queried": False,
            "production_db_copied": False,
            "production_db_written": False,
            "registry_mutated": False,
            "network_used": False,
            "replay_generation_performed": False,
            "prediction_generation_performed": False,
        },
        "canonical_digest_contract": {
            "algorithm": "SHA-256 of compact, sorted-key UTF-8 JSON",
            "recursively_excluded_keys": sorted(_SELF_DIGEST_EXCLUDES),
            "excludes_wall_clock_absolute_temporary_paths_and_self_hash": True,
        },
        "final_classification": "P279B_RETROSPECTIVE_FALSIFICATION_ARTIFACT_COMPLETE",
    }
    report["canonical_payload_digest"] = canonical_digest(
        report, _SELF_DIGEST_EXCLUDES
    )
    return report


def _format_probability(value: float) -> str:
    return f"{value:.12g}"


def render_markdown(report: dict[str, Any]) -> str:
    lines: list[str] = []
    add = lines.append
    add("# P279B Frozen DAILY_539 Disjoint-Block Diversified-Baseline Falsification")
    add("")
    add("> Retrospective artifact-only falsification. This is not OOS confirmation, a prediction-success claim, strategy promotion, betting value, or deployment authorization.")
    add("")
    add(f"- Source commit: `{report['source_commit']}`")
    add(f"- Endpoint: `{ENDPOINT_ID}` ({ENDPOINT_SUCCESS_RULE})")
    add(f"- Canonical payload digest: `{report['canonical_payload_digest']}`")
    add(f"- Research verdict: `{report['project_summary']['research_verdict']}`")
    add("")
    add("## Source integrity")
    add("")
    add("| Source | Path | Raw SHA-256 | Canonical digest |")
    add("|---|---|---|---|")
    for source in report["source_artifacts"]:
        add(f"| {source['source_id']} | `{source['path']}` | `{source['raw_sha256']}` | `{source['canonical_payload_digest']}` |")
    add("")
    add("## Frozen candidates and disjoint counts")
    add("")
    add("| Candidate | N | latest 50 | latest 300 | latest 750 | D50 | P250 | P450 | Recombined |")
    add("|---|---:|---:|---:|---:|---:|---:|---:|---|")
    for candidate in report["disjoint_block_derivation"]:
        nested = candidate["nested_counts"]
        derived = candidate["derived_disjoint_counts"]
        add(
            f"| `{candidate['strategy_id']}` | {candidate['ticket_budget']} | "
            f"{nested['latest_50']['successes']} | {nested['latest_300']['successes']} | "
            f"{nested['latest_750']['successes']} | {derived['D50']} | {derived['P250']} | "
            f"{derived['P450']} | PASS |"
        )
    add("")
    add("All nested supports are exactly 50/300/750. Every subtraction is a non-negative integer and both recombination identities pass.")
    add("")
    add("## Exact diversified baseline")
    add("")
    add("| N | Winning outcomes | Total outcomes | Exact probability | P276 MC | Reconciliation |")
    add("|---:|---:|---:|---:|---:|---|")
    exact = report["baseline_contract"]["exact_diversified"]
    recon = report["baseline_contract"]["p276_monte_carlo_reconciliation"]["by_ticket_budget"]
    for budget in ("3", "5"):
        baseline = exact[budget]
        mc = recon[budget]
        add(
            f"| {budget} | {baseline['winning_outcome_count']} | {baseline['total_outcome_count']} | "
            f"{_format_probability(baseline['probability'])} | {_format_probability(mc['p276_stored_probability'])} | "
            f"`{mc['status']}` |"
        )
    add("")
    add(report["baseline_contract"]["symmetry_verification"]["proof"])
    add(" Three alternative mutually disjoint ticket families were exhaustively verified; each produced the same N=3 and N=5 numerator. Exact probabilities supersede P276 Monte Carlo uncertainty for P279B only.")
    add("")
    add("## Six primary tests")
    add("")
    add(f"Bonferroni family: m=6, alpha=0.05, per-test threshold={BONFERRONI_ALPHA:.12g}. D50 is excluded.")
    add("")
    add("| Candidate | Block | n | k | Rate | Exact q | Excess | Direction | Raw p | Adjusted p | Pass |")
    add("|---|---|---:|---:|---:|---:|---:|---|---:|---:|---|")
    for item in report["primary_test_results"]:
        add(
            f"| `{item['strategy_id']}` | {item['block']} | {item['n']} | {item['k']} | "
            f"{_format_probability(item['observed_rate'])} | {_format_probability(item['baseline_probability'])} | "
            f"{_format_probability(item['absolute_excess'])} | {item['direction']} | "
            f"{_format_probability(item['raw_p_value'])} | {_format_probability(item['bonferroni_adjusted_p_value'])} | "
            f"{str(item['passes_bonferroni_threshold']).upper()} |"
        )
    add("")
    add("## D50 descriptive results")
    add("")
    add("| Candidate | N | k/50 | Rate | Exact q | Excess | Direction | Two-sided p (descriptive) |")
    add("|---|---:|---:|---:|---:|---:|---|---:|")
    for item in report["diagnostic_d50_results"]:
        add(
            f"| `{item['strategy_id']}` | {item['ticket_budget']} | {item['k']}/50 | "
            f"{_format_probability(item['observed_rate'])} | {_format_probability(item['baseline_probability'])} | "
            f"{_format_probability(item['absolute_excess'])} | {item['direction']} | "
            f"{_format_probability(item['raw_p_value'])} |"
        )
    add("")
    add("## Ordinary-random sensitivity")
    add("")
    add("Secondary only: `q = 1 - C(T-W,N)/C(T,N)`, with T=575757 and W=65621. These reproduce committed P273 values and do not control P279B classifications.")
    add("")
    add("| N | Exact ordinary-random probability | P273 reproduced |")
    add("|---:|---:|---|")
    for budget in ("3", "5"):
        baseline = report["baseline_contract"]["ordinary_random_sensitivity"][budget]
        add(f"| {budget} | {_format_probability(baseline['probability'])} | PASS |")
    add("")
    add("| Candidate | Block | N | Rate | Ordinary q | Excess | Direction | Two-sided p (sensitivity) |")
    add("|---|---|---:|---:|---:|---:|---|---:|")
    for item in report["ordinary_random_sensitivity_results"]:
        add(
            f"| `{item['strategy_id']}` | {item['block']} | {item['ticket_budget']} | "
            f"{_format_probability(item['observed_rate'])} | {_format_probability(item['baseline_probability'])} | "
            f"{_format_probability(item['absolute_excess'])} | {item['direction']} | "
            f"{_format_probability(item['raw_p_value'])} |"
        )
    add("")
    add("## Candidate decisions")
    add("")
    add("| Candidate | N | Decision |")
    add("|---|---:|---|")
    for decision in report["candidate_decisions"]:
        add(f"| `{decision['strategy_id']}` | {decision['ticket_budget']} | `{decision['decision']}` |")
    add("")
    add("Project decision counts:")
    for label in (DECISION_RETAIN, DECISION_INCONCLUSIVE, DECISION_FALSIFIED):
        count = report["project_summary"]["decision_counts"][label]
        add(f"- `{label}`: {count}")
    add("")
    add("## Boundaries and limitations")
    add("")
    for limitation in report["scientific_limitations"]:
        add(f"- {limitation}")
    add("")
    for flag in sorted(report["safety_flags"]):
        value = report["safety_flags"][flag]
        add(f"- `{flag}={str(value).lower()}`")
    add("")
    return "\n".join(lines)


def serialize_json(report: dict[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def write_artifacts(
    report: dict[str, Any], json_path: str = DEFAULT_JSON_PATH,
    markdown_path: str = DEFAULT_MD_PATH,
) -> None:
    repository_path(json_path).write_text(serialize_json(report), encoding="utf-8")
    repository_path(markdown_path).write_text(render_markdown(report), encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="calculate and validate without writing")
    args = parser.parse_args(argv)
    report = build_artifact()
    if not args.check:
        write_artifacts(report)
    print(json.dumps({
        "task_id": TASK_ID,
        "research_verdict": report["project_summary"]["research_verdict"],
        "canonical_payload_digest": report["canonical_payload_digest"],
        "written": not args.check,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
