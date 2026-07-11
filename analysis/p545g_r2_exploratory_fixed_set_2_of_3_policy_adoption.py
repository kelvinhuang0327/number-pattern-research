"""P545G R2 exploratory fixed-ticket-set 2-of-3 policy adoption.

This module reads exactly two pinned Git blobs: the committed P545C R4
registry as sole row-level evidence and the canonical P545B artifact as
expected reconciliation evidence.  It has no database, snapshot, SQLite,
network, strategy-search, combination-generation, or production interface.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
from collections import Counter
from decimal import Decimal, getcontext
from pathlib import Path
from typing import Any, Iterable, Sequence


getcontext().prec = 100
if hasattr(sys, "set_int_max_str_digits"):
    sys.set_int_max_str_digits(20_000)

TASK_ID = "P545G_R2_EXPLORATORY_FIXED_SET_2_OF_3_POLICY_ADOPTION"
SCHEMA = "p545g_r2_exploratory_fixed_set_2_of_3_policy_adoption.v1"
CLASSIFICATION = (
    "P545G_R2_ALL_THREE_RETAINED_EXPLORATORY_2_OF_3_"
    "CONFIRMATORY_NONE_NO_PREDICTIVE_OR_BETTING_CLAIM"
)
POLICY_ID = "EXPLORATORY_FIXED_SET_NULL_2_OF_3.v1"
BASE_COMMIT = "a5b1b12ddcd0c8c18ebcb9aff2e8d5ab7708fac0"
GENERATED_AT_UTC = "2026-07-11T09:11:29Z"

REGISTRY_PATH = "outputs/research/p545c_r4_strategy_draw_opportunity_registry_20260711.json"
REGISTRY_SIZE = 52_393_107
REGISTRY_SHA256 = "ea0a712fa5ba702c51271b5664fc95e5cac2feec5967ead3bd7d01cfcd7bc5d8"
REGISTRY_SCHEMA = "p545c_r4_strategy_draw_opportunity_registry.compact.v1"
REGISTRY_SEMANTIC_DIGEST = "f2c28075a3b7020629a0c6bd41504609031ff84532a672dde4f26f0485434b39"
REGISTRY_CANONICAL_DIGEST = "34bbee9b9a3cd275025db282486f8bdd3dd5c14834813061acefce220ae0ed84"

P545B_PATH = "outputs/research/p545b_full_50_300_750_per_draw_evaluation_20260711.json"
P545B_SIZE = 37_431_814
P545B_SHA256 = "08aad7a1e4185af2e8f21373a2d8e617a9cb4c876aed99246e9e219d739e21eb"
P545B_SCHEMA = "p545b_full_50_300_750_per_draw_evaluation.v1"
P545B_CANONICAL_DIGEST = "f409e0c0d28ff13a95aa29f6e17186b4e109524c66fac7835912609884d78d9f"

OUTPUT_JSON = Path("outputs/research/p545g_r2_exploratory_fixed_set_2_of_3_policy_adoption_20260711.json")
OUTPUT_MARKDOWN = Path("outputs/research/p545g_r2_exploratory_fixed_set_2_of_3_policy_adoption_20260711.md")
NEW_FILES = (
    "analysis/p545g_r2_exploratory_fixed_set_2_of_3_policy_adoption.py",
    str(OUTPUT_JSON),
    str(OUTPUT_MARKDOWN),
    "tests/test_p545g_r2_exploratory_fixed_set_2_of_3_policy_adoption.py",
)

CANDIDATES = (
    "DAILY_539:daily539_f4cold_5bet",
    "DAILY_539:daily539_f4cold_3bet",
    "DAILY_539:acb_markov_midfreq_3bet",
)
WINDOWS = ((50, "SHORT", 1), (300, "MID", 2), (750, "LONG", 4))
DRAW_DENOMINATOR = 575_757
SINGLE_TICKET_FAVORABLE = 65_621
BONFERRONI_FAMILY = 108
ALPHA_NUMERATOR = 1
ALPHA_DENOMINATOR = 20


class CalibrationError(RuntimeError):
    """Fail-closed calibration, identity, or reconciliation error."""


def canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise CalibrationError("payload is not finite canonical JSON") from exc


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _pairs_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CalibrationError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise CalibrationError(f"non-finite JSON constant: {value}")


def strict_json_bytes(raw: bytes) -> dict[str, Any]:
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_pairs_object,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CalibrationError("invalid UTF-8 JSON input") from exc
    if not isinstance(value, dict):
        raise CalibrationError("top-level JSON value must be an object")
    return value


def git_blob(repo_root: Path, path: str) -> bytes:
    completed = subprocess.run(
        ["git", "show", f"{BASE_COMMIT}:{path}"],
        cwd=repo_root,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode:
        raise CalibrationError(
            f"required committed Git blob unavailable: {path}: "
            f"{completed.stderr.decode('utf-8', errors='replace').strip()}"
        )
    return completed.stdout


def _verify_blob(
    repo_root: Path,
    *,
    path: str,
    size: int,
    sha256: str,
    schema: str,
    canonical_digest: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    raw = git_blob(repo_root, path)
    actual_sha = hashlib.sha256(raw).hexdigest()
    if len(raw) != size or actual_sha != sha256:
        raise CalibrationError(f"input identity mismatch: {path}")
    payload = strict_json_bytes(raw)
    if payload.get("schema") != schema:
        raise CalibrationError(f"input schema mismatch: {path}")
    if payload.get("canonical_payload_digest") != canonical_digest:
        raise CalibrationError(f"input canonical digest mismatch: {path}")
    return payload, {
        "path": path,
        "source_commit": BASE_COMMIT,
        "byte_size": size,
        "sha256": sha256,
        "schema": schema,
        "canonical_payload_digest": canonical_digest,
        "verification": "PASS",
        "read_method": "git show <commit>:<path>",
    }


def load_inputs(repo_root: Path) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    registry, registry_identity = _verify_blob(
        repo_root,
        path=REGISTRY_PATH,
        size=REGISTRY_SIZE,
        sha256=REGISTRY_SHA256,
        schema=REGISTRY_SCHEMA,
        canonical_digest=REGISTRY_CANONICAL_DIGEST,
    )
    semantic = registry.get("semantic_equivalence", {}).get(
        "compact_semantic_projection_digest"
    )
    if semantic != REGISTRY_SEMANTIC_DIGEST:
        raise CalibrationError("registry semantic projection mismatch")
    registry_identity["semantic_projection_digest"] = semantic
    registry_identity["role"] = "SOLE_ROW_LEVEL_EVIDENCE"

    p545b, p545b_identity = _verify_blob(
        repo_root,
        path=P545B_PATH,
        size=P545B_SIZE,
        sha256=P545B_SHA256,
        schema=P545B_SCHEMA,
        canonical_digest=P545B_CANONICAL_DIGEST,
    )
    p545b_identity["role"] = "EXPECTED_RECONCILIATION_EVIDENCE_ONLY"
    return registry, p545b, [registry_identity, p545b_identity]


def ratio_record(numerator: int, denominator: int) -> dict[str, Any]:
    if denominator <= 0:
        raise CalibrationError("ratio denominator must be positive")
    common = math.gcd(numerator, denominator)
    return {
        "numerator": str(numerator // common),
        "denominator": str(denominator // common),
        "decimal_30": format(Decimal(numerator) / Decimal(denominator), ".30f"),
    }


def canonical_ticket_set(tickets: Iterable[Sequence[int]]) -> tuple[tuple[int, ...], ...]:
    normalized = []
    for ticket in tickets:
        values = tuple(sorted(int(number) for number in ticket))
        if len(values) != 5 or len(set(values)) != 5 or values[0] < 1 or values[-1] > 39:
            raise CalibrationError(f"invalid DAILY_539 ticket: {ticket}")
        normalized.append(values)
    return tuple(sorted(set(normalized)))


def membership_signature(tickets: Sequence[Sequence[int]]) -> tuple[int, ...]:
    ticket_sets = [set(ticket) for ticket in tickets]
    counts = [0] * (1 << len(ticket_sets))
    for number in range(1, 40):
        mask = 0
        for index, ticket in enumerate(ticket_sets):
            if number in ticket:
                mask |= 1 << index
        counts[mask] += 1
    if sum(counts) != 39:
        raise CalibrationError("membership signature does not cover 39 numbers")
    return tuple(counts)


def favorable_from_signature(signature: Sequence[int], ticket_count: int) -> int:
    if len(signature) != 1 << ticket_count or sum(signature) != 39:
        raise CalibrationError("invalid geometry signature")
    states: dict[tuple[int, tuple[int, ...]], int] = {(0, (0,) * ticket_count): 1}
    for mask, category_count in enumerate(signature):
        if not category_count:
            continue
        next_states: dict[tuple[int, tuple[int, ...]], int] = {}
        for (selected, hits), count in states.items():
            for chosen in range(0, min(category_count, 5 - selected) + 1):
                updated_hits = tuple(
                    min(2, hits[index] + (chosen if mask & (1 << index) else 0))
                    for index in range(ticket_count)
                )
                key = (selected + chosen, updated_hits)
                next_states[key] = next_states.get(key, 0) + count * math.comb(
                    category_count, chosen
                )
        states = next_states
    total = sum(count for (selected, _), count in states.items() if selected == 5)
    if total != DRAW_DENOMINATOR:
        raise CalibrationError(f"category DP total mismatch: {total}")
    complement = sum(
        count
        for (selected, hits), count in states.items()
        if selected == 5 and all(hit <= 1 for hit in hits)
    )
    return DRAW_DENOMINATOR - complement


def exact_fixed_probability(tickets: Sequence[Sequence[int]]) -> tuple[int, tuple[int, ...]]:
    canonical = canonical_ticket_set(tickets)
    signature = membership_signature(canonical)
    return favorable_from_signature(signature, len(canonical)), signature


def per_number_dp_favorable(tickets: Sequence[Sequence[int]]) -> int:
    """Independent exact DP cross-check; it does not enumerate five-number outcomes."""
    canonical = canonical_ticket_set(tickets)
    ticket_sets = [set(ticket) for ticket in canonical]
    states: dict[tuple[int, tuple[int, ...]], int] = {(0, (0,) * len(canonical)): 1}
    for number in range(1, 40):
        membership = tuple(int(number in ticket) for ticket in ticket_sets)
        next_states = dict(states)
        for (selected, hits), count in states.items():
            if selected == 5:
                continue
            updated = tuple(
                min(2, hits[index] + membership[index])
                for index in range(len(canonical))
            )
            key = (selected + 1, updated)
            next_states[key] = next_states.get(key, 0) + count
        states = next_states
    return sum(
        count
        for (selected, hits), count in states.items()
        if selected == 5 and any(hit >= 2 for hit in hits)
    )


def poisson_binomial_exact(favorable_counts: Sequence[int], observed: int) -> dict[str, Any]:
    coefficients = [1]
    float_probabilities = [1.0]
    for favorable in favorable_counts:
        next_coefficients = [0] * (len(coefficients) + 1)
        for successes, count in enumerate(coefficients):
            next_coefficients[successes] += count * (DRAW_DENOMINATOR - favorable)
            next_coefficients[successes + 1] += count * favorable
        coefficients = next_coefficients

        probability = favorable / DRAW_DENOMINATOR
        next_float = [0.0] * (len(float_probabilities) + 1)
        for successes, value in enumerate(float_probabilities):
            next_float[successes] += value * (1.0 - probability)
            next_float[successes + 1] += value * probability
        float_probabilities = next_float

    denominator = pow(DRAW_DENOMINATOR, len(favorable_counts))
    upper_numerator = sum(coefficients[observed:])
    lower_numerator = sum(coefficients[: observed + 1])
    upper = Decimal(upper_numerator) / Decimal(denominator)
    lower = Decimal(lower_numerator) / Decimal(denominator)
    float_upper = sum(float_probabilities[observed:])
    float_lower = sum(float_probabilities[: observed + 1])
    tolerance = Decimal("1e-12")
    if abs(upper - Decimal(str(float_upper))) > tolerance:
        raise CalibrationError("integer and float upper-tail DP disagreement")
    if abs(lower - Decimal(str(float_lower))) > tolerance:
        raise CalibrationError("integer and float lower-tail DP disagreement")
    return {
        "method": "exact_integer_poisson_binomial_dp",
        "bernoulli_denominator": DRAW_DENOMINATOR,
        "upper_tail_numerator": str(upper_numerator),
        "lower_tail_numerator": str(lower_numerator),
        "tail_denominator": str(denominator),
        "upper_tail_decimal_30": format(upper, ".30f"),
        "lower_tail_decimal_30": format(lower, ".30f"),
        "float_crosscheck_upper": format(float_upper, ".17g"),
        "float_crosscheck_lower": format(float_lower, ".17g"),
        "float_crosscheck_tolerance": "1e-12",
        "crosscheck": "PASS",
    }


def _counter_record(values: Iterable[int]) -> dict[str, int]:
    return {str(key): value for key, value in sorted(Counter(values).items())}


def _random_distinct_probability(ticket_count: int) -> tuple[int, int]:
    total_ticket_sets = math.comb(DRAW_DENOMINATOR, ticket_count)
    losing_ticket_sets = math.comb(
        DRAW_DENOMINATOR - SINGLE_TICKET_FAVORABLE, ticket_count
    )
    return total_ticket_sets - losing_ticket_sets, total_ticket_sets


def _algorithm_crosschecks() -> dict[str, Any]:
    single = ((1, 2, 3, 4, 5),)
    duplicate_input = (single[0], single[0])
    disjoint_five = tuple(tuple(range(start, start + 5)) for start in (1, 6, 11, 16, 21))
    ordered = (
        (1, 4, 7, 10, 13),
        (2, 5, 8, 11, 14),
        (3, 6, 9, 12, 15),
    )
    renamed = tuple(tuple(((number + 6) % 39) + 1 for number in ticket) for ticket in ordered)
    single_value, _ = exact_fixed_probability(single)
    duplicate_value, _ = exact_fixed_probability(duplicate_input)
    ordered_value, _ = exact_fixed_probability(ordered)
    permuted_value, _ = exact_fixed_probability(tuple(reversed(ordered)))
    renamed_value, _ = exact_fixed_probability(renamed)
    disjoint_value, _ = exact_fixed_probability(disjoint_five)
    checks = {
        "single_ticket_identity": single_value == SINGLE_TICKET_FAVORABLE,
        "duplicate_ticket_deduplication": duplicate_value == single_value,
        "ticket_order_invariance": permuted_value == ordered_value,
        "geometry_isomorphism_invariance": renamed_value == ordered_value,
        "fully_disjoint_five_ticket_diagnostic": disjoint_value == 297_105,
        "independent_per_number_dp": all(
            exact_fixed_probability(tickets)[0] == per_number_dp_favorable(tickets)
            for tickets in (single, ordered, disjoint_five)
        ),
    }
    if not all(checks.values()):
        raise CalibrationError(f"fixed-set algorithm cross-check failed: {checks}")
    return {
        "status": "PASS",
        "checks": checks,
        "single_ticket_favorable": single_value,
        "fully_disjoint_five_ticket_favorable": disjoint_value,
        "outcome_combinations_enumerated": False,
        "strategy_combinations_generated": False,
    }


def _extract_candidate_draws(
    registry: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    descriptors = {item["cell_id"]: item for item in registry["cells"]}
    if not set(CANDIDATES) <= set(descriptors):
        raise CalibrationError("candidate descriptor missing")
    outcomes = {item["outcome_id"]: item for item in registry["official_outcomes"]}
    attempts = registry["attempts"]
    cache: dict[tuple[int, tuple[int, ...]], int] = {}
    all_records: list[dict[str, Any]] = []
    by_cell = {cell_id: [] for cell_id in CANDIDATES}
    for opportunity in registry["opportunities"]:
        cell_id = opportunity["cell_id"]
        if cell_id not in by_cell:
            continue
        if not opportunity["supported"] or not (opportunity["window_mask"] & 4):
            raise CalibrationError(f"unsupported or non-LONG candidate row: {opportunity['opportunity_id']}")
        if opportunity["missing_expected_bet_indices"] or opportunity["unexpected_bet_indices"]:
            raise CalibrationError(f"bet-index mismatch: {opportunity['opportunity_id']}")
        selected = attempts[
            opportunity["attempt_start"] : opportunity["attempt_start"]
            + opportunity["attempt_count"]
        ]
        if any(item["opportunity_id"] != opportunity["opportunity_id"] for item in selected):
            raise CalibrationError("attempt range mismatch")
        eligible = [item for item in selected if item["eligible"]]
        excluded = [item for item in selected if not item["eligible"]]
        if len(eligible) != opportunity["eligible_attempt_count"]:
            raise CalibrationError("eligible attempt count mismatch")
        identities: dict[str, tuple[int, ...]] = {}
        for attempt in eligible:
            identity = attempt["ticket_identity"]
            fingerprint = identity["fingerprint_sha256"]
            ticket = tuple(identity["canonical_ticket_content"]["main_numbers"])
            if ticket != tuple(attempt["predicted_main_numbers"]):
                raise CalibrationError("canonical ticket content mismatch")
            previous = identities.setdefault(fingerprint, ticket)
            if previous != ticket:
                raise CalibrationError("ticket fingerprint collision")
        tickets = canonical_ticket_set(identities.values())
        if len(tickets) != descriptors[cell_id]["declared_bet_count"]:
            raise CalibrationError("realized distinct-ticket count mismatch")
        signature = membership_signature(tickets)
        cache_key = (len(tickets), signature)
        favorable = cache.setdefault(
            cache_key, favorable_from_signature(signature, len(tickets))
        )
        outcome = outcomes[opportunity["outcome_id"]]
        if outcome["target_draw"] != opportunity["target_draw"]:
            raise CalibrationError("outcome target-draw mismatch")
        actual = set(outcome["main_numbers"])
        observed = any(len(actual.intersection(ticket)) >= 2 for ticket in tickets)
        registry_observed = any(item["score"]["any_prize_aware_win"] for item in eligible)
        if observed != registry_observed:
            raise CalibrationError("recomputed endpoint scoring mismatch")
        memberships = [name for _, name, bit in WINDOWS if opportunity["window_mask"] & bit]
        pairwise = [
            len(set(tickets[left]).intersection(tickets[right]))
            for left in range(len(tickets))
            for right in range(left + 1, len(tickets))
        ]
        signature_record = [[mask, count] for mask, count in enumerate(signature) if count]
        record = {
            "cell_id": cell_id,
            "opportunity_id": opportunity["opportunity_id"],
            "target_draw": opportunity["target_draw"],
            "window_memberships": memberships,
            "raw_eligible_attempt_count": len(eligible),
            "excluded_attempt_count": len(excluded),
            "realized_distinct_ticket_count": len(tickets),
            "duplicate_collapse_count": len(eligible) - len(tickets),
            "sorted_ticket_set": [list(ticket) for ticket in tickets],
            "ticket_set_digest": digest([list(ticket) for ticket in tickets]),
            "geometry_signature": signature_record,
            "geometry_signature_digest": digest(signature_record),
            "pairwise_ticket_overlaps": pairwise,
            "unique_numbers_covered": len(set().union(*(set(ticket) for ticket in tickets))),
            "fixed_null_favorable": favorable,
            "fixed_null_denominator": DRAW_DENOMINATOR,
            "fixed_null_probability_decimal_30": format(
                Decimal(favorable) / Decimal(DRAW_DENOMINATOR), ".30f"
            ),
            "official_main_numbers": outcome["main_numbers"],
            "observed_endpoint_success": observed,
        }
        all_records.append(record)
        by_cell[cell_id].append(record)
    for cell_id, records in by_cell.items():
        if len(records) != 750:
            raise CalibrationError(f"candidate LONG count mismatch: {cell_id}: {len(records)}")
        for size, name, _ in WINDOWS:
            if sum(name in item["window_memberships"] for item in records) != size:
                raise CalibrationError(f"candidate {name} count mismatch: {cell_id}")
    return all_records, by_cell


def _geometry_diagnostics(cell_id: str, records: Sequence[dict[str, Any]]) -> dict[str, Any]:
    favorable = sorted(item["fixed_null_favorable"] for item in records)
    ticket_count = records[0]["realized_distinct_ticket_count"]
    random_num, random_den = _random_distinct_probability(ticket_count)
    comparisons = Counter()
    for value in favorable:
        left = value * random_den
        right = random_num * DRAW_DENOMINATOR
        comparisons["higher" if left > right else "lower" if left < right else "equal"] += 1
    mean_num = sum(favorable)
    mean_den = len(favorable) * DRAW_DENOMINATOR
    median_num = favorable[374] + favorable[375]
    median_den = 2 * DRAW_DENOMINATOR
    mean_delta_num = mean_num * random_den - random_num * mean_den
    mean_delta_den = mean_den * random_den
    max_delta_num = favorable[-1] * random_den - random_num * DRAW_DENOMINATOR
    max_delta_den = DRAW_DENOMINATOR * random_den
    geometry_projection = [
        {
            "target_draw": item["target_draw"],
            "ticket_set_digest": item["ticket_set_digest"],
            "geometry_signature_digest": item["geometry_signature_digest"],
            "fixed_null_favorable": item["fixed_null_favorable"],
        }
        for item in records
    ]
    return {
        "cell_id": cell_id,
        "draw_count": len(records),
        "realized_distinct_ticket_count_distribution": _counter_record(
            item["realized_distinct_ticket_count"] for item in records
        ),
        "duplicate_collapse_total": sum(item["duplicate_collapse_count"] for item in records),
        "unique_ticket_set_count": len({item["ticket_set_digest"] for item in records}),
        "unique_geometry_signature_count": len(
            {item["geometry_signature_digest"] for item in records}
        ),
        "pairwise_ticket_overlap_distribution": _counter_record(
            overlap for item in records for overlap in item["pairwise_ticket_overlaps"]
        ),
        "unique_numbers_covered_distribution": _counter_record(
            item["unique_numbers_covered"] for item in records
        ),
        "random_distinct_ticket_probability": ratio_record(random_num, random_den),
        "fixed_probability_min": ratio_record(favorable[0], DRAW_DENOMINATOR),
        "fixed_probability_median": ratio_record(median_num, median_den),
        "fixed_probability_mean": ratio_record(mean_num, mean_den),
        "fixed_probability_max": ratio_record(favorable[-1], DRAW_DENOMINATOR),
        "fixed_minus_random_mean": ratio_record(mean_delta_num, mean_delta_den),
        "fixed_minus_random_max": ratio_record(max_delta_num, max_delta_den),
        "fixed_vs_random_draw_counts": {
            key: comparisons.get(key, 0) for key in ("higher", "equal", "lower")
        },
        "fixed_probability_numerator_distribution": _counter_record(favorable),
        "ticket_set_geometry_digest": digest(geometry_projection),
    }


def _window_calibrations(
    by_cell: dict[str, list[dict[str, Any]]], p545b: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    committed = {
        (item["cell_id"], item["window_size"]): item
        for item in p545b["window_evaluations"]
        if item["cell_id"] in CANDIDATES
    }
    if len(committed) != 9:
        raise CalibrationError("canonical P545B nine-window evidence missing")
    windows: list[dict[str, Any]] = []
    cell_results: list[dict[str, Any]] = []
    for cell_id in CANDIDATES:
        cell_windows = []
        for window_size, window_name, _ in WINDOWS:
            records = [
                item
                for item in by_cell[cell_id]
                if window_name in item["window_memberships"]
            ]
            evidence = committed[(cell_id, window_size)]
            opportunity_ids = [item["opportunity_id"] for item in records]
            if opportunity_ids != evidence["opportunity_ids"]:
                raise CalibrationError("P545B frozen window membership mismatch")
            observed = sum(item["observed_endpoint_success"] for item in records)
            if observed != evidence["observed_success_count"]:
                raise CalibrationError("P545B observed-success reconciliation mismatch")
            favorable = [item["fixed_null_favorable"] for item in records]
            expected_num = sum(favorable)
            expected_den = DRAW_DENOMINATOR
            variance_num = sum(value * (DRAW_DENOMINATOR - value) for value in favorable)
            variance_den = DRAW_DENOMINATOR * DRAW_DENOMINATOR
            tails = poisson_binomial_exact(favorable, observed)
            upper_num = int(tails["upper_tail_numerator"])
            lower_num = int(tails["lower_tail_numerator"])
            tail_den = int(tails["tail_denominator"])
            direction_positive = observed * expected_den > expected_num
            exploratory_pass = (
                evidence["evaluable"]
                and direction_positive
                and upper_num * ALPHA_DENOMINATOR <= tail_den * ALPHA_NUMERATOR
            )
            confirmatory_positive = (
                direction_positive
                and upper_num * BONFERRONI_FAMILY * ALPHA_DENOMINATOR
                <= tail_den * ALPHA_NUMERATOR
            )
            correction_negative = (
                observed * expected_den < expected_num
                and lower_num * BONFERRONI_FAMILY * ALPHA_DENOMINATOR
                <= tail_den * ALPHA_NUMERATOR
            )
            calibrated_bonf_num = min(tail_den, upper_num * BONFERRONI_FAMILY)
            record = {
                "cell_id": cell_id,
                "window": window_name,
                "window_size": window_size,
                "draw_count": len(records),
                "anchor_first_draw": records[-1]["target_draw"],
                "anchor_last_draw": records[0]["target_draw"],
                "draw_set_digest": evidence["draw_set_digest"],
                "realized_ticket_count_pattern": _counter_record(
                    item["realized_distinct_ticket_count"] for item in records
                ),
                "committed_random_set_expected_successes": format(
                    Decimal(str(evidence["expected_successes"])), ".12f"
                ),
                "fixed_set_expected_successes": ratio_record(expected_num, expected_den),
                "fixed_minus_committed_expected": format(
                    Decimal(expected_num) / Decimal(expected_den)
                    - Decimal(str(evidence["expected_successes"])),
                    ".12f",
                ),
                "fixed_set_variance": ratio_record(variance_num, variance_den),
                "observed_successes": observed,
                "observed_minus_fixed_expected": ratio_record(
                    observed * expected_den - expected_num, expected_den
                ),
                "absolute_excess_rate": ratio_record(
                    observed * expected_den - expected_num,
                    window_size * expected_den,
                ),
                "relative_lift": ratio_record(observed * expected_den, expected_num),
                "committed_raw_upper_p": format(
                    Decimal(str(evidence["raw_p_value_one_sided_upper"])), ".12f"
                ),
                "calibrated_poisson_binomial": tails,
                "committed_bonferroni_upper_p": format(
                    Decimal(str(evidence["bonferroni_p_value_upper"])), ".12f"
                ),
                "calibrated_bonferroni_upper": ratio_record(
                    calibrated_bonf_num, tail_den
                ),
                "bonferroni_family_size": BONFERRONI_FAMILY,
                "committed_decision": evidence["decision"]["window"],
                "fixed_probability_min": ratio_record(min(favorable), DRAW_DENOMINATOR),
                "fixed_probability_max": ratio_record(max(favorable), DRAW_DENOMINATOR),
                "direction_positive": direction_positive,
                "exploratory_policy_window_pass": exploratory_pass,
                "original_confirmatory_window_survives": confirmatory_positive,
                "correction_surviving_negative": correction_negative,
            }
            windows.append(record)
            cell_windows.append(record)
        passing = [item["window"] for item in cell_windows if item["exploratory_policy_window_pass"]]
        no_negative = not any(item["correction_surviving_negative"] for item in cell_windows)
        exploratory_cell_pass = (
            len(passing) >= 2
            and any(name in {"MID", "LONG"} for name in passing)
            and no_negative
        )
        confirmatory_cell_pass = any(
            item["original_confirmatory_window_survives"]
            and item["window"] in {"MID", "LONG"}
            for item in cell_windows
        )
        cell_results.append(
            {
                "cell_id": cell_id,
                "passing_exploratory_windows": passing,
                "passing_window_count": len(passing),
                "mid_or_long_pass_present": any(
                    name in {"MID", "LONG"} for name in passing
                ),
                "no_correction_surviving_negative_window": no_negative,
                "exploratory_policy_result": (
                    "RETAINED_EXPLORATORY_CANDIDATE"
                    if exploratory_cell_pass
                    else "NOT_RETAINED_EXPLORATORY_CANDIDATE"
                ),
                "original_bonferroni_108_result": (
                    "SURVIVES" if confirmatory_cell_pass else "DOES_NOT_SURVIVE"
                ),
            }
        )
    return windows, cell_results


def build_evaluation(repo_root: Path) -> dict[str, Any]:
    registry, p545b, identities = load_inputs(repo_root)
    crosschecks = _algorithm_crosschecks()
    candidate_draws, by_cell = _extract_candidate_draws(registry)
    for cell_id, records in by_cell.items():
        for index in (0, 374, 749):
            tickets = records[index]["sorted_ticket_set"]
            if records[index]["fixed_null_favorable"] != per_number_dp_favorable(tickets):
                raise CalibrationError(f"actual-ticket DP cross-check failed: {cell_id}:{index}")
    crosschecks["actual_candidate_ticket_sets_crosschecked"] = 9
    geometry = [_geometry_diagnostics(cell_id, by_cell[cell_id]) for cell_id in CANDIDATES]
    window_calibrations, cell_results = _window_calibrations(by_cell, p545b)
    retained = [
        item["cell_id"]
        for item in cell_results
        if item["exploratory_policy_result"] == "RETAINED_EXPLORATORY_CANDIDATE"
    ]
    confirmatory_survivors = [
        item["cell_id"]
        for item in cell_results
        if item["original_bonferroni_108_result"] == "SURVIVES"
    ]
    if retained != list(CANDIDATES) or confirmatory_survivors:
        raise CalibrationError("unexpected fixed-set policy classification")
    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "task_id": TASK_ID,
        "classification": CLASSIFICATION,
        "generated_at_utc": GENERATED_AT_UTC,
        "generated_at_policy": {
            "source": "required baseline merge committer timestamp normalized to UTC",
            "source_commit": BASE_COMMIT,
            "wall_clock_used": False,
            "deterministic": True,
        },
        "required_baseline_commit": BASE_COMMIT,
        "input_identities": identities,
        "candidate_scope": list(CANDIDATES),
        "policy": {
            "policy_id": POLICY_ID,
            "status": "OWNER_DIRECTED_EXPLORATORY_POST_HOC_POLICY",
            "pre_registered": False,
            "window_rule": (
                "evaluable AND observed_successes > fixed_expected_successes "
                "AND one_sided_raw_upper_p <= 0.05"
            ),
            "cell_rule": (
                "at least two of SHORT/MID/LONG pass AND at least one passing "
                "window is MID or LONG AND no correction-surviving negative window"
            ),
            "short_can_be_one_of_two": True,
            "short_can_be_sole_trigger": False,
            "raw_alpha": "0.05",
            "confirmatory_family_preserved_separately": BONFERRONI_FAMILY,
            "candidate_expansion_allowed": False,
            "threshold_tuning_allowed": False,
        },
        "fixed_set_null": {
            "denominator": DRAW_DENOMINATOR,
            "success_endpoint": "at least one distinct ticket has at least two main-number hits",
            "algorithm": (
                "integer combinatorial DP over number-membership categories; state tracks "
                "selected count 0..5 and per-ticket hits capped at 2; category choices use C(c_mask,k)"
            ),
            "random_distinct_ticket_average_used_for_calibrated_inference": False,
            "independent_ticket_approximation_used": False,
            "fully_disjoint_geometry_assumed": False,
            "outcome_combinations_enumerated": False,
        },
        "algorithm_crosschecks": crosschecks,
        "candidate_draws": candidate_draws,
        "geometry_diagnostics": geometry,
        "window_calibrations": window_calibrations,
        "cell_results": cell_results,
        "decision": {
            "exploratory_policy_result": "ALL_THREE_RETAINED_EXPLORATORY",
            "retained_exploratory_candidates": retained,
            "original_confirmatory_bonferroni_108_result": "NONE_SURVIVE",
            "original_confirmatory_survivors": confirmatory_survivors,
            "predictive_validation_status": "NOT_ESTABLISHED",
        },
        "p544d_gate": {
            "status": "DESIGN_ONLY_GATE_OPEN",
            "allowed_next_scope": (
                "draft a separately authorized, predefined P544D design using exactly the "
                "three retained exploratory candidates"
            ),
            "combination_generation_authorized": False,
            "combination_evaluation_authorized": False,
            "execution_requires_separate_owner_authorization": True,
            "candidate_set_locked": list(CANDIDATES),
        },
        "safety": {
            "database_or_snapshot_opened": False,
            "sqlite_imported_or_invoked": False,
            "network_used_for_calibration": False,
            "strategy_combinations_generated": False,
            "candidate_set_expanded": False,
            "thresholds_tuned": False,
            "upstream_p545b_or_p545c_modified": False,
            "predictive_validity_claim": False,
            "roi_ev_staking_purchase_or_betting_claim": False,
        },
        "limitations": [
            "Retrospective sensitivity calibration only.",
            "The exploratory 2-of-3 rule is Owner-directed and was not pre-registered.",
            "The original Bonferroni family of 108 remains the separate confirmatory result.",
            "No prospective holdout or predictive validity is established.",
            "The P544D gate is design-only; no combinations were generated or evaluated.",
        ],
    }
    payload["canonical_payload_digest"] = digest(payload)
    return payload


def render_json(payload: dict[str, Any]) -> bytes:
    return (
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# P545G R2 Exploratory Fixed-Set 2-of-3 Policy Adoption",
        "",
        "## Decision",
        "",
        "All three scoped DAILY_539 cells satisfy `EXPLORATORY_FIXED_SET_NULL_2_OF_3.v1`. "
        "This is an Owner-directed post-hoc exploratory policy, not a pre-registered confirmatory rule. "
        "Separately, none survives the original Bonferroni family of 108 under the fixed-set null.",
        "",
        "## Policy",
        "",
        "A window passes when it is evaluable, observed successes exceed fixed-set expected successes, "
        "and its one-sided raw upper-tail p-value is at most 0.05. A cell passes when at least two of "
        "SHORT/MID/LONG pass, at least one passing window is MID or LONG, and no window has "
        "correction-surviving negative evidence.",
        "",
        "## Nine-window calculation matrix",
        "",
        "| Cell | Window | Observed | Committed expected | Fixed expected | Difference | Committed raw p | Fixed raw p | Committed Bonf. p | Fixed Bonf. p | Exploratory pass | Confirmatory survives |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|:---:|:---:|",
    ]
    for item in payload["window_calibrations"]:
        strategy = item["cell_id"].split(":", 1)[1]
        fixed_expected = item["fixed_set_expected_successes"]["decimal_30"]
        raw = item["calibrated_poisson_binomial"]["upper_tail_decimal_30"]
        bonf = item["calibrated_bonferroni_upper"]["decimal_30"]
        lines.append(
            f"| `{strategy}` | {item['window']} {item['window_size']} | {item['observed_successes']} | "
            f"{item['committed_random_set_expected_successes']} | {fixed_expected} | "
            f"{item['fixed_minus_committed_expected']} | {item['committed_raw_upper_p']} | {raw} | "
            f"{item['committed_bonferroni_upper_p']} | {bonf} | "
            f"{'PASS' if item['exploratory_policy_window_pass'] else 'FAIL'} | "
            f"{'YES' if item['original_confirmatory_window_survives'] else 'NO'} |"
        )
    lines.extend(
        [
            "",
            "## Retained exploratory candidates",
            "",
        ]
    )
    for item in payload["cell_results"]:
        lines.append(
            f"- `{item['cell_id'].split(':', 1)[1]}`: {item['exploratory_policy_result']}; "
            f"passing windows = {', '.join(item['passing_exploratory_windows'])}; "
            f"original Bonferroni-108 result = {item['original_bonferroni_108_result']}."
        )
    lines.extend(
        [
            "",
            "## Exact method and evidence scope",
            "",
            f"The P545C R4 registry at `{BASE_COMMIT}` is the sole row-level input. The canonical P545B "
            "artifact is used only to reconcile the frozen memberships, observed successes, and committed "
            "comparison fields. Each fixed-set numerator is computed by integer category DP over the 39-number "
            "membership geometry. Window tails use deterministic integer Poisson-binomial DP; 100-digit Decimal "
            "rendering is independently checked against float DP within 1e-12.",
            "",
            "The JSON companion publishes all 2,250 per-draw ticket sets, geometry signatures, exact favorable "
            "numerators, nine exact tail rationals, geometry diagnostics, and input identities.",
            "",
            "## P544D gate",
            "",
            "`DESIGN_ONLY_GATE_OPEN`: a separately authorized task may draft a predefined P544D design using "
            "exactly these three retained exploratory candidates. Combination generation or evaluation is not "
            "authorized here and was not performed.",
            "",
            "## Safety and limitations",
            "",
            "No database, snapshot, SQLite, network, strategy combination, candidate expansion, or threshold tuning "
            "was used. This document makes no predictive-validity, ROI, EV, staking, purchase, deployment, or "
            "betting claim.",
            "",
            f"Canonical payload digest: `{payload['canonical_payload_digest']}`",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="write the two deterministic evidence outputs")
    args = parser.parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    payload = build_evaluation(repo_root)
    if args.write:
        (repo_root / OUTPUT_JSON).write_bytes(render_json(payload))
        (repo_root / OUTPUT_MARKDOWN).write_text(render_markdown(payload), encoding="utf-8")
    else:
        print(json.dumps(payload["decision"], sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
