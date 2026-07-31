#!/usr/bin/env python3
"""P293F exact conditional-null inference engine (artifact-only, stdlib-only)."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
from decimal import Decimal, ROUND_HALF_EVEN, getcontext
from pathlib import Path


EVIDENCE_ROOT = Path(
    "/Users/kelvin/LotteryResearchEvidence/"
    "P293F-big649-exact-conditional-null-20260629/attempt_1"
).resolve()
INPUT_CSV = Path(
    "/Users/kelvin/LotteryResearchEvidence/"
    "P293E-big649-independent-portfolio-audit-20260629/attempt_1/"
    "INDEPENDENT_PORTFOLIO_RESULT_TABLE.csv"
).resolve()
INPUT_SHA256 = "1a3031424c67e5adf5fc47f0fe033e411d73c8652a38d9c5a0097b42c8551825"
EXPECTED_HEADER = [
    "target_index",
    "draw_id",
    "budget",
    "subset_indices",
    "subset_names",
    "union_size",
    "redundancy",
    "pairwise_overlap",
    "union_hits",
    "ref_a_cond_expected_hits",
    "ref_b_diversified_expected_hits",
]
STRATEGY_NAMES = (
    "freq_50",
    "freq_300",
    "freq_750",
    "prior_draw",
    "exp_recency_50",
    "exp_recency_300",
    "exp_recency_750",
)
BUDGETS = (2, 3, 4)
TARGETS = tuple(range(750, 2120))
DIAGNOSTICS = (
    ("LATEST_750", 1370, 2119),
    ("LATEST_300", 1820, 2119),
    ("LATEST_50", 2070, 2119),
    ("BLOCK_1", 750, 1091),
    ("BLOCK_2", 1092, 1433),
    ("BLOCK_3", 1434, 1776),
    ("BLOCK_4", 1777, 2119),
)
EXPECTED_SEGMENT_COUNTS = {
    "LATEST_750": 750,
    "LATEST_300": 300,
    "LATEST_50": 50,
    "BLOCK_1": 342,
    "BLOCK_2": 342,
    "BLOCK_3": 343,
    "BLOCK_4": 343,
}

getcontext().prec = 80
getcontext().rounding = ROUND_HALF_EVEN
D0 = Decimal(0)
D1 = Decimal(1)
N49 = Decimal(49)
PMF_TOL = Decimal("1e-40")
CONV_TOL = Decimal("1e-30")
MOMENT_TOL = Decimal("1e-40")
ALPHA = Decimal("0.05")
COMB_49_6 = math.comb(49, 6)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def decimal_text(value: Decimal) -> str:
    return format(value, ".60E")


def require_output_path(path: Path) -> Path:
    resolved = path.resolve()
    if resolved != EVIDENCE_ROOT and EVIDENCE_ROOT not in resolved.parents:
        raise ValueError(f"output path is outside P293F evidence root: {resolved}")
    return resolved


def parse_int(row_number: int, field: str, value: str) -> int:
    if value is None or value == "" or value.strip() != value:
        raise ValueError(f"row {row_number}: malformed integer field {field!r}")
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(f"row {row_number}: non-integer {field}={value!r}") from exc
    if str(parsed) != value:
        raise ValueError(f"row {row_number}: non-canonical integer {field}={value!r}")
    return parsed


def load_rows(input_path: Path) -> tuple[dict[int, list[dict[str, object]]], dict[str, object]]:
    if input_path.resolve() != INPUT_CSV:
        raise ValueError("only the frozen P293E independent result table may be read")
    actual_hash = sha256_file(input_path)
    if actual_hash != INPUT_SHA256:
        raise ValueError(f"input SHA-256 mismatch: {actual_hash}")

    rows_by_budget: dict[int, list[dict[str, object]]] = {budget: [] for budget in BUDGETS}
    seen: set[tuple[int, int]] = set()
    draw_by_target: dict[int, int] = {}
    total_rows = 0

    with input_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != EXPECTED_HEADER:
            raise ValueError(f"unexpected CSV header: {reader.fieldnames!r}")
        for row_number, raw in enumerate(reader, start=2):
            total_rows += 1
            if None in raw or any(value is None for value in raw.values()):
                raise ValueError(f"row {row_number}: malformed column count")
            target = parse_int(row_number, "target_index", raw["target_index"])
            target_draw = parse_int(row_number, "draw_id", raw["draw_id"])
            budget = parse_int(row_number, "budget", raw["budget"])
            union_size = parse_int(row_number, "union_size", raw["union_size"])
            redundancy = parse_int(row_number, "redundancy", raw["redundancy"])
            overlap = parse_int(row_number, "pairwise_overlap", raw["pairwise_overlap"])
            union_hits = parse_int(row_number, "union_hits", raw["union_hits"])

            if target not in TARGETS:
                raise ValueError(f"row {row_number}: target_index out of range: {target}")
            if target_draw <= 0:
                raise ValueError(f"row {row_number}: invalid target draw: {target_draw}")
            if budget not in BUDGETS:
                raise ValueError(f"row {row_number}: invalid budget: {budget}")
            if not 6 <= union_size <= min(6 * budget, 49):
                raise ValueError(f"row {row_number}: invalid union size M={union_size}")
            if not 0 <= union_hits <= 6:
                raise ValueError(f"row {row_number}: invalid union_hits={union_hits}")
            if redundancy != 6 * budget - union_size:
                raise ValueError(f"row {row_number}: redundancy identity failed")
            if not 0 <= overlap <= 6 * math.comb(budget, 2):
                raise ValueError(f"row {row_number}: infeasible pairwise overlap={overlap}")

            subset_indices_raw = raw["subset_indices"].split("|")
            subset_names = raw["subset_names"].split("|")
            if len(subset_indices_raw) != budget or len(subset_names) != budget:
                raise ValueError(f"row {row_number}: subset cardinality does not equal B")
            subset_indices = tuple(
                parse_int(row_number, "subset_indices", item) for item in subset_indices_raw
            )
            if len(set(subset_indices)) != budget or tuple(sorted(subset_indices)) != subset_indices:
                raise ValueError(f"row {row_number}: subset indices are not distinct ascending")
            if any(index < 0 or index >= len(STRATEGY_NAMES) for index in subset_indices):
                raise ValueError(f"row {row_number}: subset index out of range")
            if tuple(STRATEGY_NAMES[index] for index in subset_indices) != tuple(subset_names):
                raise ValueError(f"row {row_number}: subset index/name mapping mismatch")

            key = (target, budget)
            if key in seen:
                raise ValueError(f"row {row_number}: duplicate target/budget key {key}")
            seen.add(key)
            if target in draw_by_target and draw_by_target[target] != target_draw:
                raise ValueError(f"row {row_number}: target draw differs across budgets")
            draw_by_target[target] = target_draw

            rows_by_budget[budget].append(
                {
                    "target": target,
                    "target_draw": target_draw,
                    "budget": budget,
                    "subset_indices": subset_indices,
                    "subset_names": tuple(subset_names),
                    "union_size": union_size,
                    "redundancy": redundancy,
                    "pairwise_overlap": overlap,
                    "union_hits": union_hits,
                }
            )

    expected_keys = {(target, budget) for target in TARGETS for budget in BUDGETS}
    if total_rows != 4110:
        raise ValueError(f"row count mismatch: {total_rows}")
    if seen != expected_keys:
        missing = sorted(expected_keys - seen)[:5]
        extra = sorted(seen - expected_keys)[:5]
        raise ValueError(f"target/budget coverage mismatch; missing={missing}, extra={extra}")
    if set(draw_by_target) != set(TARGETS):
        raise ValueError("target-draw coverage mismatch")
    for budget in BUDGETS:
        rows_by_budget[budget].sort(key=lambda item: int(item["target"]))
        if [int(item["target"]) for item in rows_by_budget[budget]] != list(TARGETS):
            raise ValueError(f"budget {budget}: target order/coverage mismatch")

    integrity = {
        "input_path": str(INPUT_CSV),
        "input_sha256": actual_hash,
        "row_count": total_rows,
        "target_min": min(TARGETS),
        "target_max": max(TARGETS),
        "targets_per_budget": len(TARGETS),
        "budgets": list(BUDGETS),
        "coverage_complete": True,
        "integer_constraints_valid": True,
        "subset_fields_valid": True,
        "target_draw_consistent_across_budgets": True,
    }
    return rows_by_budget, integrity


def hypergeom_pmf(union_size: int) -> tuple[Decimal, ...]:
    probabilities: list[Decimal] = []
    denominator = Decimal(COMB_49_6)
    for hits in range(7):
        if hits > union_size or 6 - hits > 49 - union_size:
            numerator = 0
        else:
            numerator = math.comb(union_size, hits) * math.comb(49 - union_size, 6 - hits)
        probabilities.append(Decimal(numerator) / denominator)
    total = sum(probabilities, D0)
    if abs(total - D1) > PMF_TOL:
        raise ArithmeticError(f"M={union_size}: PMF sum validation failed: {total}")
    return tuple(probabilities)


def analytic_variance(union_size: int) -> Decimal:
    proportion = Decimal(union_size) / N49
    return Decimal(6) * proportion * (D1 - proportion) * (Decimal(43) / Decimal(48))


def exact_primary(
    budget: int, rows: list[dict[str, object]], pmf_cache: dict[int, tuple[Decimal, ...]]
) -> tuple[dict[str, object], dict[str, object]]:
    distribution = [D1]
    observed = 0
    analytic_mean = D0
    analytic_var = D0
    max_pmf_sum_error = D0

    for row in rows:
        union_size = int(row["union_size"])
        observed += int(row["union_hits"])
        analytic_mean += Decimal(6 * union_size) / N49
        analytic_var += analytic_variance(union_size)
        pmf = pmf_cache.setdefault(union_size, hypergeom_pmf(union_size))
        max_pmf_sum_error = max(max_pmf_sum_error, abs(sum(pmf, D0) - D1))
        updated = [D0] * (len(distribution) + 6)
        for subtotal, subtotal_probability in enumerate(distribution):
            if subtotal_probability == D0:
                continue
            for hits, hit_probability in enumerate(pmf):
                if hit_probability != D0:
                    updated[subtotal + hits] += subtotal_probability * hit_probability
        distribution = updated

    distribution_sum = sum(distribution, D0)
    distribution_sum_error = abs(distribution_sum - D1)
    if distribution_sum_error > CONV_TOL:
        raise ArithmeticError(f"B={budget}: convolution sum validation failed")
    distribution_mean = sum(
        (Decimal(value) * probability for value, probability in enumerate(distribution)), D0
    )
    distribution_variance = sum(
        (
            (Decimal(value) - distribution_mean) ** 2 * probability
            for value, probability in enumerate(distribution)
        ),
        D0,
    )
    mean_error = abs(distribution_mean - analytic_mean)
    variance_error = abs(distribution_variance - analytic_var)
    if mean_error > MOMENT_TOL:
        raise ArithmeticError(f"B={budget}: mean validation failed: {mean_error}")
    if variance_error > MOMENT_TOL:
        raise ArithmeticError(f"B={budget}: variance validation failed: {variance_error}")
    upper_tail = sum(distribution[observed:], D0) if observed < len(distribution) else D0
    if not D0 <= upper_tail <= D1:
        raise ArithmeticError(f"B={budget}: tail probability outside [0,1]")

    result = {
        "budget_B": budget,
        "n_targets": len(rows),
        "observed_S": observed,
        "conditional_mean": analytic_mean,
        "excess": Decimal(observed) - analytic_mean,
        "upper_tail_p": upper_tail,
    }
    validation = {
        "budget_B": budget,
        "decimal_precision": getcontext().prec,
        "max_per_target_pmf_sum_error": max_pmf_sum_error,
        "convolution_support_min": 0,
        "convolution_support_max": len(distribution) - 1,
        "convolution_sum": distribution_sum,
        "convolution_sum_error": distribution_sum_error,
        "analytic_mean": analytic_mean,
        "distribution_mean": distribution_mean,
        "mean_abs_error": mean_error,
        "analytic_variance": analytic_var,
        "distribution_variance": distribution_variance,
        "variance_abs_error": variance_error,
        "pmf_tolerance": PMF_TOL,
        "convolution_tolerance": CONV_TOL,
        "moment_tolerance": MOMENT_TOL,
        "passed": True,
    }
    return result, validation


def apply_holm(results: list[dict[str, object]]) -> None:
    ordered = sorted(results, key=lambda item: (item["upper_tail_p"], item["budget_B"]))
    running = D0
    adjusted_by_budget: dict[int, Decimal] = {}
    family_size = len(ordered)
    for rank, item in enumerate(ordered, start=1):
        candidate = Decimal(family_size - rank + 1) * item["upper_tail_p"]
        candidate = min(candidate, D1)
        running = max(running, candidate)
        adjusted_by_budget[int(item["budget_B"])] = running
    for item in results:
        adjusted = adjusted_by_budget[int(item["budget_B"])]
        item["holm_adjusted_p"] = adjusted
        item["primary_reject"] = adjusted < ALPHA


def build_diagnostics(
    rows_by_budget: dict[int, list[dict[str, object]]]
) -> tuple[list[dict[str, object]], dict[int, int]]:
    diagnostics: list[dict[str, object]] = []
    nonnegative_blocks: dict[int, int] = {budget: 0 for budget in BUDGETS}
    for budget in BUDGETS:
        for segment, start, end in DIAGNOSTICS:
            selected = [
                row for row in rows_by_budget[budget] if start <= int(row["target"]) <= end
            ]
            if len(selected) != EXPECTED_SEGMENT_COUNTS[segment]:
                raise ValueError(f"B={budget} {segment}: diagnostic coverage mismatch")
            observed = sum(int(row["union_hits"]) for row in selected)
            mean = sum((Decimal(6 * int(row["union_size"])) / N49 for row in selected), D0)
            excess = Decimal(observed) - mean
            is_block = segment.startswith("BLOCK_")
            nonnegative = excess >= D0
            if is_block and nonnegative:
                nonnegative_blocks[budget] += 1
            diagnostics.append(
                {
                    "budget_B": budget,
                    "segment": segment,
                    "target_start": start,
                    "target_end": end,
                    "n_targets": len(selected),
                    "observed_S": observed,
                    "conditional_mean": mean,
                    "excess": excess,
                    "is_chronological_block": is_block,
                    "nonnegative_excess": nonnegative,
                }
            )
    return diagnostics, nonnegative_blocks


def csv_bytes(fieldnames: list[str], rows: list[dict[str, object]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def json_bytes(payload: object) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode("utf-8")


def write_bytes(path: Path, data: bytes) -> None:
    require_output_path(path)
    path.write_bytes(data)


def run(input_path: Path, outdir: Path, publish_root: bool) -> dict[str, str]:
    input_path = input_path.resolve()
    outdir = require_output_path(outdir)
    if outdir == EVIDENCE_ROOT:
        raise ValueError("run output directory must be a child of the P293F evidence root")
    if outdir.exists() and any(outdir.iterdir()):
        raise ValueError(f"run output directory is not empty: {outdir}")
    outdir.mkdir(parents=True, exist_ok=True)

    rows_by_budget, integrity = load_rows(input_path)
    pmf_cache: dict[int, tuple[Decimal, ...]] = {}
    primary_results: list[dict[str, object]] = []
    validations: list[dict[str, object]] = []
    for budget in BUDGETS:
        result, validation = exact_primary(budget, rows_by_budget[budget], pmf_cache)
        primary_results.append(result)
        validations.append(validation)
    apply_holm(primary_results)
    diagnostics, nonnegative_blocks = build_diagnostics(rows_by_budget)

    for result in primary_results:
        budget = int(result["budget_B"])
        result["nonnegative_blocks"] = nonnegative_blocks[budget]
        result["stability_condition"] = nonnegative_blocks[budget] >= 3
        result["retention_condition"] = bool(
            result["primary_reject"] and result["stability_condition"]
        )
    any_retention = any(bool(result["retention_condition"]) for result in primary_results)
    if any_retention:
        report_classification = "EXPLORATORY_INFERENTIAL_RETENTION_ONLY"
        final_classification = (
            "P293F_EXACT_CONDITIONAL_NULL_COMPLETE_EXPLORATORY_RETENTION_ONLY"
        )
    else:
        report_classification = "DESCRIPTIVE_ONLY_NO_INFERENTIAL_RETENTION"
        final_classification = (
            "P293F_EXACT_CONDITIONAL_NULL_COMPLETE_DESCRIPTIVE_ONLY_NO_RETENTION"
        )

    result_rows = [
        {
            "budget_B": result["budget_B"],
            "n_targets": result["n_targets"],
            "observed_S": result["observed_S"],
            "conditional_mean": decimal_text(result["conditional_mean"]),
            "excess": decimal_text(result["excess"]),
            "exact_upper_tail_p": decimal_text(result["upper_tail_p"]),
            "holm_adjusted_p": decimal_text(result["holm_adjusted_p"]),
            "primary_reject": str(result["primary_reject"]).lower(),
            "nonnegative_blocks": result["nonnegative_blocks"],
            "stability_condition": str(result["stability_condition"]).lower(),
            "retention_condition": str(result["retention_condition"]).lower(),
        }
        for result in primary_results
    ]
    diagnostic_rows = [
        {
            "budget_B": item["budget_B"],
            "segment": item["segment"],
            "target_start": item["target_start"],
            "target_end": item["target_end"],
            "n_targets": item["n_targets"],
            "observed_S": item["observed_S"],
            "conditional_mean": decimal_text(item["conditional_mean"]),
            "excess": decimal_text(item["excess"]),
            "is_chronological_block": str(item["is_chronological_block"]).lower(),
            "nonnegative_excess": str(item["nonnegative_excess"]).lower(),
        }
        for item in diagnostics
    ]
    validation_serialized = [
        {
            key: decimal_text(value) if isinstance(value, Decimal) else value
            for key, value in validation.items()
        }
        for validation in validations
    ]
    summary_core = {
        "method": "exact_PGF_convolution_of_conditional_hypergeometric_PMFs",
        "decimal_precision": getcontext().prec,
        "rounding": str(getcontext().rounding),
        "family_alpha": decimal_text(ALPHA),
        "input_integrity": integrity,
        "primary_results": result_rows,
        "numerical_validation": validation_serialized,
        "diagnostic_rows": diagnostic_rows,
        "report_classification": report_classification,
        "final_classification": final_classification,
        "post_hoc_exploratory": True,
        "promotion_authorized": False,
    }

    exact_data = csv_bytes(list(result_rows[0]), result_rows)
    diagnostic_data = csv_bytes(list(diagnostic_rows[0]), diagnostic_rows)
    core_data = json_bytes(summary_core)
    canonical_digest = sha256_bytes(exact_data + b"\0" + diagnostic_data + b"\0" + core_data)
    summary = dict(summary_core)
    summary["canonical_result_sha256"] = canonical_digest
    summary_data = json_bytes(summary)
    file_hashes = {
        "EXACT_CONDITIONAL_NULL_RESULTS.csv": sha256_bytes(exact_data),
        "BLOCK_STABILITY_DIAGNOSTICS.csv": sha256_bytes(diagnostic_data),
        "RUN_SUMMARY.json": sha256_bytes(summary_data),
    }
    run_hashes = {
        "canonical_result_sha256": canonical_digest,
        "files": file_hashes,
    }
    run_hashes_data = json_bytes(run_hashes)

    write_bytes(outdir / "EXACT_CONDITIONAL_NULL_RESULTS.csv", exact_data)
    write_bytes(outdir / "BLOCK_STABILITY_DIAGNOSTICS.csv", diagnostic_data)
    write_bytes(outdir / "RUN_SUMMARY.json", summary_data)
    write_bytes(outdir / "RUN_HASHES.json", run_hashes_data)
    if publish_root:
        write_bytes(EVIDENCE_ROOT / "EXACT_CONDITIONAL_NULL_RESULTS.csv", exact_data)
        write_bytes(EVIDENCE_ROOT / "BLOCK_STABILITY_DIAGNOSTICS.csv", diagnostic_data)
    return {
        "canonical_result_sha256": canonical_digest,
        **file_hashes,
        "RUN_HASHES.json": sha256_bytes(run_hashes_data),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--outdir", type=Path, required=True)
    parser.add_argument("--publish-root", action="store_true")
    args = parser.parse_args()
    hashes = run(args.input, args.outdir, args.publish_root)
    print(json.dumps(hashes, sort_keys=True))


if __name__ == "__main__":
    main()
