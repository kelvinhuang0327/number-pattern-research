"""P361 no-DB coverage utility drilldown for parity-tier Big Lotto adapters.

This module builds only on the P360 no-DB walk-forward harness and its
committed JSONL fixture. It computes descriptive historical coverage,
redundancy, subset, and marginal contribution artifacts for the same five
PARITY_ACCEPTABLE adapters. It does not open the DB, import production
registries, promote strategy status, or make future-performance claims.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Iterable, Mapping

from recovered_strategies.biglotto import historical_adapters
from recovered_strategies.biglotto import no_db_multiwindow_validation as p360

REPO_ROOT = p360.REPO_ROOT
TASK = "P361_biglotto_coverage_utility"

SUBSET_METRICS_COLUMNS = (
    "subset_size",
    "rank_within_subset_size",
    "best_subset_for_size",
    "adapter_subset",
    "period_count",
    "any_hit_count",
    "coverage_rate",
    "total_adapter_hit_events",
    "duplicate_hit_events",
    "multi_adapter_hit_period_count",
    "single_adapter_hit_period_count",
    "mean_pairwise_jaccard",
    "max_pairwise_jaccard",
    "fixture_sha256",
)

MARGINAL_CONTRIBUTION_COLUMNS = (
    "context_size",
    "context_adapters",
    "candidate_adapter",
    "prior_any_hit_count",
    "candidate_total_hit_count",
    "candidate_overlap_count",
    "marginal_unique_hit_count",
    "with_candidate_any_hit_count",
    "marginal_coverage_rate_delta",
    "candidate_marginal_share",
    "fixture_sha256",
)

HIT_MATRIX_BASE_COLUMNS = ("period",)
HIT_MATRIX_TRAILING_COLUMNS = ("cohort_hit_count", "cohort_any_hit", "fixture_sha256")

MANIFEST_COLUMNS = ("key", "value")

ARTIFACT_BASENAMES = {
    "subset_metrics": "P361_biglotto_coverage_utility_subset_metrics.csv",
    "marginal_contribution": "P361_biglotto_coverage_utility_marginal_contribution.csv",
    "hit_matrix": "P361_biglotto_coverage_utility_hit_matrix.csv",
    "manifest": "P361_biglotto_coverage_utility_manifest.csv",
    "report": "P361_biglotto_coverage_utility_report.md",
}


@dataclass(frozen=True)
class CoverageUtilityOutput:
    fixture_sha256: str
    draw_count: int
    scoreable_period_count: int
    adapter_names: tuple[str, ...]
    subset_metrics_rows: tuple[dict[str, str], ...]
    marginal_contribution_rows: tuple[dict[str, str], ...]
    hit_matrix_rows: tuple[dict[str, str], ...]
    manifest_rows: tuple[dict[str, str], ...]


def _records_by_adapter(records: Iterable[tuple[int, str, int, bool]]) -> dict[str, list[tuple[int, bool]]]:
    grouped: dict[str, list[tuple[int, bool]]] = {}
    for period, name, _bet_count, hit in records:
        grouped.setdefault(name, []).append((period, bool(hit)))
    for name in grouped:
        grouped[name].sort(key=lambda item: item[0])
    return grouped


def build_hit_sets(
    records: Iterable[tuple[int, str, int, bool]], adapter_names: Iterable[str]
) -> tuple[list[int], dict[str, set[int]]]:
    grouped = _records_by_adapter(records)
    names = tuple(adapter_names)
    missing = [name for name in names if name not in grouped]
    if missing:
        raise p360.AdapterSelectionError(f"missing walk-forward records: {missing}")
    periods = [period for period, _hit in grouped[names[0]]]
    if periods != sorted(periods) or len(set(periods)) != len(periods):
        raise p360.FixtureValidationError("scoreable periods are not unique and ordered")
    for name in names[1:]:
        other_periods = [period for period, _hit in grouped[name]]
        if other_periods != periods:
            raise p360.FixtureValidationError(f"adapter period grid mismatch: {name}")
    hit_sets = {
        name: {period for period, hit in grouped[name] if hit}
        for name in names
    }
    return periods, hit_sets


def _union_hit_set(names: Iterable[str], hit_sets: Mapping[str, set[int]]) -> set[int]:
    union: set[int] = set()
    for name in names:
        union |= hit_sets[name]
    return union


def _pairwise_jaccards(names: tuple[str, ...], hit_sets: Mapping[str, set[int]]) -> list[float]:
    values = []
    for left, right in combinations(names, 2):
        union = hit_sets[left] | hit_sets[right]
        values.append((len(hit_sets[left] & hit_sets[right]) / len(union)) if union else 0.0)
    return values


def compute_subset_metrics_rows(
    periods: Iterable[int],
    hit_sets: Mapping[str, set[int]],
    adapter_names: Iterable[str],
    fixture_sha256: str,
) -> tuple[dict[str, str], ...]:
    periods = tuple(periods)
    names = tuple(adapter_names)
    period_count = len(periods)
    rows_by_size: dict[int, list[dict[str, str]]] = {}
    for subset_size in range(1, len(names) + 1):
        rows_by_size[subset_size] = []
        for subset in combinations(names, subset_size):
            union = _union_hit_set(subset, hit_sets)
            hit_counts_by_period = [
                sum(1 for name in subset if period in hit_sets[name])
                for period in periods
            ]
            total_events = sum(hit_counts_by_period)
            duplicate_events = sum(max(0, count - 1) for count in hit_counts_by_period)
            multi_hit_periods = sum(1 for count in hit_counts_by_period if count >= 2)
            single_hit_periods = sum(1 for count in hit_counts_by_period if count == 1)
            jaccards = _pairwise_jaccards(subset, hit_sets)
            rows_by_size[subset_size].append(
                {
                    "subset_size": str(subset_size),
                    "rank_within_subset_size": "",
                    "best_subset_for_size": "",
                    "adapter_subset": ";".join(subset),
                    "period_count": str(period_count),
                    "any_hit_count": str(len(union)),
                    "coverage_rate": f"{len(union) / period_count:.8f}",
                    "total_adapter_hit_events": str(total_events),
                    "duplicate_hit_events": str(duplicate_events),
                    "multi_adapter_hit_period_count": str(multi_hit_periods),
                    "single_adapter_hit_period_count": str(single_hit_periods),
                    "mean_pairwise_jaccard": f"{(sum(jaccards) / len(jaccards)):.8f}" if jaccards else "",
                    "max_pairwise_jaccard": f"{max(jaccards):.8f}" if jaccards else "",
                    "fixture_sha256": fixture_sha256,
                }
            )
    ranked_rows = []
    for subset_size in sorted(rows_by_size):
        ordered = sorted(
            rows_by_size[subset_size],
            key=lambda row: (
                -int(row["any_hit_count"]),
                int(row["duplicate_hit_events"]),
                row["adapter_subset"],
            ),
        )
        best_hit_count = int(ordered[0]["any_hit_count"])
        for rank, row in enumerate(ordered, start=1):
            ranked = dict(row)
            ranked["rank_within_subset_size"] = str(rank)
            ranked["best_subset_for_size"] = (
                "true" if int(row["any_hit_count"]) == best_hit_count else "false"
            )
            ranked_rows.append(ranked)
    return tuple(ranked_rows)


def compute_marginal_contribution_rows(
    periods: Iterable[int],
    hit_sets: Mapping[str, set[int]],
    adapter_names: Iterable[str],
    fixture_sha256: str,
) -> tuple[dict[str, str], ...]:
    periods = tuple(periods)
    names = tuple(adapter_names)
    period_count = len(periods)
    rows = []
    for candidate in names:
        context_pool = tuple(name for name in names if name != candidate)
        for context_size in range(0, len(context_pool) + 1):
            for context in combinations(context_pool, context_size):
                prior_hits = _union_hit_set(context, hit_sets)
                candidate_hits = hit_sets[candidate]
                marginal_hits = candidate_hits - prior_hits
                with_candidate = prior_hits | candidate_hits
                marginal_share = (
                    len(marginal_hits) / len(candidate_hits) if candidate_hits else 0.0
                )
                rows.append(
                    {
                        "context_size": str(context_size),
                        "context_adapters": ";".join(context),
                        "candidate_adapter": candidate,
                        "prior_any_hit_count": str(len(prior_hits)),
                        "candidate_total_hit_count": str(len(candidate_hits)),
                        "candidate_overlap_count": str(len(candidate_hits & prior_hits)),
                        "marginal_unique_hit_count": str(len(marginal_hits)),
                        "with_candidate_any_hit_count": str(len(with_candidate)),
                        "marginal_coverage_rate_delta": f"{len(marginal_hits) / period_count:.8f}",
                        "candidate_marginal_share": f"{marginal_share:.8f}",
                        "fixture_sha256": fixture_sha256,
                    }
                )
    return tuple(
        sorted(
            rows,
            key=lambda row: (
                int(row["context_size"]),
                row["candidate_adapter"],
                row["context_adapters"],
            ),
        )
    )


def compute_hit_matrix_rows(
    periods: Iterable[int],
    hit_sets: Mapping[str, set[int]],
    adapter_names: Iterable[str],
    fixture_sha256: str,
) -> tuple[dict[str, str], ...]:
    names = tuple(adapter_names)
    rows = []
    for period in periods:
        hit_count = sum(1 for name in names if period in hit_sets[name])
        row = {"period": str(period)}
        for name in names:
            row[name] = "1" if period in hit_sets[name] else "0"
        row["cohort_hit_count"] = str(hit_count)
        row["cohort_any_hit"] = "1" if hit_count else "0"
        row["fixture_sha256"] = fixture_sha256
        rows.append(row)
    return tuple(rows)


def build_manifest_rows(output_fields: Mapping[str, object]) -> tuple[dict[str, str], ...]:
    return tuple({"key": key, "value": str(value)} for key, value in output_fields.items())


def run_coverage_utility(fixture_path: Path | None = None) -> CoverageUtilityOutput:
    draws, sha256 = p360.load_big_lotto_draws(fixture_path)
    if fixture_path is None and sha256 != p360.EXPECTED_FIXTURE_SHA256:
        raise p360.FixtureValidationError(
            f"fixture SHA256 mismatch: expected {p360.EXPECTED_FIXTURE_SHA256}, got {sha256}"
        )
    specs = p360.resolve_scoring_adapters()
    adapter_names = tuple(spec.name for spec in specs)
    records = p360.run_walk_forward(draws, {spec.name: spec.fn for spec in specs})
    periods, hit_sets = build_hit_sets(records, adapter_names)
    subset_rows = compute_subset_metrics_rows(periods, hit_sets, adapter_names, sha256)
    marginal_rows = compute_marginal_contribution_rows(periods, hit_sets, adapter_names, sha256)
    matrix_rows = compute_hit_matrix_rows(periods, hit_sets, adapter_names, sha256)
    manifest_rows = build_manifest_rows(
        {
            "task": TASK,
            "source_task": "P360_biglotto_no_db_multiwindow_validation",
            "fixture_relpath": p360.FIXTURE_RELPATH,
            "fixture_sha256": sha256,
            "big_lotto_row_count": len(draws),
            "lookback_draws": p360.LOOKBACK,
            "scoreable_period_count": len(periods),
            "first_scoreable_period": periods[0],
            "last_scoreable_period": periods[-1],
            "adapter_count": len(adapter_names),
            "adapters": ";".join(adapter_names),
            "subset_metric_rows": len(subset_rows),
            "marginal_contribution_rows": len(marginal_rows),
            "hit_matrix_rows": len(matrix_rows),
            "hit_definition": f"any ticket matching >={p360.HIT_THRESHOLD_MAINS} main numbers",
            "tier": p360.TIER,
            "required_parity_status": p360.REQUIRED_PARITY_STATUS,
            "db_opened": "NO",
            "production_registry_imported": "NO",
            "strategy_status_changed": "NO",
            "future_prediction_claim": "NO",
            "betting_advice": "NO",
        }
    )
    return CoverageUtilityOutput(
        fixture_sha256=sha256,
        draw_count=len(draws),
        scoreable_period_count=len(periods),
        adapter_names=adapter_names,
        subset_metrics_rows=subset_rows,
        marginal_contribution_rows=marginal_rows,
        hit_matrix_rows=matrix_rows,
        manifest_rows=manifest_rows,
    )


def _markdown_table(columns: Iterable[str], rows: Iterable[Mapping[str, str]]) -> str:
    columns = list(columns)
    lines = ["| " + " | ".join(columns) + " |", "|" + "|".join(" --- " for _ in columns) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(str(row[column]) for column in columns) + " |")
    return "\n".join(lines)


def _full_context_rows(output: CoverageUtilityOutput) -> list[dict[str, str]]:
    full_context_size = len(output.adapter_names) - 1
    return [
        row for row in output.marginal_contribution_rows
        if row["context_size"] == str(full_context_size)
    ]


def _near_duplicate_rows(output: CoverageUtilityOutput, threshold: float = 0.80) -> list[dict[str, str]]:
    hit_sets = {
        name: {int(row["period"]) for row in output.hit_matrix_rows if row[name] == "1"}
        for name in output.adapter_names
    }
    rows = []
    for left, right in combinations(output.adapter_names, 2):
        both = hit_sets[left] & hit_sets[right]
        union = hit_sets[left] | hit_sets[right]
        jaccard = (len(both) / len(union)) if union else 0.0
        if jaccard >= threshold:
            rows.append(
                {
                    "adapter_a": left,
                    "adapter_b": right,
                    "both_hit_count": str(len(both)),
                    "union_hit_count": str(len(union)),
                    "jaccard": f"{jaccard:.8f}",
                }
            )
    return rows


def render_report(output: CoverageUtilityOutput) -> str:
    excluded_shape_only = sorted(
        name
        for name, meta in historical_adapters.ADAPTER_METADATA.items()
        if meta.get("parity_status") != p360.REQUIRED_PARITY_STATUS
    )
    best_subsets = [
        row for row in output.subset_metrics_rows
        if row["rank_within_subset_size"] == "1"
    ]
    near_duplicate_pairs = _near_duplicate_rows(output)
    parts = []
    parts.append("# P361 Big Lotto no-DB Coverage Utility Drilldown")
    parts.append("")
    parts.append("## Scope statements")
    parts.append("")
    parts.append("- This is historical descriptive coverage utility only.")
    parts.append("- No future prediction guarantee. Past coverage does not predict future draws.")
    parts.append("- No betting advice. Nothing here recommends placing any bet.")
    parts.append("- No DB was opened or written. The only data source is the committed JSONL fixture.")
    parts.append("- No production registry import, no deploy, no migration/backfill, and no strategy status change.")
    parts.append("- Shape/safety-only adapters and blocked targets were excluded from scoring: "
                 + ", ".join(f"`{name}`" for name in excluded_shape_only) + ".")
    parts.append("")
    parts.append("## Method")
    parts.append("")
    parts.append(f"- Source module: `recovered_strategies/biglotto/no_db_multiwindow_validation.py`")
    parts.append(f"- Fixture: `{p360.FIXTURE_RELPATH}`")
    parts.append(f"- Fixture SHA256: `{output.fixture_sha256}`")
    parts.append(f"- BIG_LOTTO rows: {output.draw_count}; scoreable periods: {output.scoreable_period_count}.")
    parts.append(f"- Adapter cohort: {', '.join(f'`{name}`' for name in output.adapter_names)}.")
    parts.append(f"- Hit definition: any ticket matching >= {p360.HIT_THRESHOLD_MAINS} main numbers.")
    parts.append("- Subset utility: every non-empty adapter subset is ranked by any-adapter historical hit coverage.")
    parts.append("- Marginal utility: every adapter is evaluated against every possible context subset of the other adapters.")
    parts.append("")
    parts.append("## Best subset by size")
    parts.append("")
    parts.append(
        _markdown_table(
            (
                "subset_size",
                "adapter_subset",
                "any_hit_count",
                "coverage_rate",
                "duplicate_hit_events",
                "mean_pairwise_jaccard",
            ),
            best_subsets,
        )
    )
    parts.append("")
    parts.append("## Full-cohort marginal contribution")
    parts.append("")
    parts.append(
        _markdown_table(
            (
                "candidate_adapter",
                "candidate_total_hit_count",
                "candidate_overlap_count",
                "marginal_unique_hit_count",
                "candidate_marginal_share",
            ),
            _full_context_rows(output),
        )
    )
    parts.append("")
    parts.append("## Near-duplicate pair screen")
    parts.append("")
    if near_duplicate_pairs:
        parts.append(
            _markdown_table(
                ("adapter_a", "adapter_b", "both_hit_count", "union_hit_count", "jaccard"),
                near_duplicate_pairs,
            )
        )
    else:
        parts.append("No pair had Jaccard >= 0.80.")
    parts.append("")
    parts.append("## Artifact inventory")
    parts.append("")
    parts.append("- `artifacts/P361_biglotto_coverage_utility_subset_metrics.csv`")
    parts.append("- `artifacts/P361_biglotto_coverage_utility_marginal_contribution.csv`")
    parts.append("- `artifacts/P361_biglotto_coverage_utility_hit_matrix.csv`")
    parts.append("- `artifacts/P361_biglotto_coverage_utility_manifest.csv`")
    parts.append("- `artifacts/P361_biglotto_coverage_utility_report.md`")
    parts.append("")
    return "\n".join(parts)


def _write_csv(path: Path, columns: Iterable[str], rows: Iterable[Mapping[str, str]]) -> None:
    columns = list(columns)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_artifacts(output: CoverageUtilityOutput, artifacts_dir: Path | None = None) -> dict[str, Path]:
    directory = Path(artifacts_dir) if artifacts_dir is not None else REPO_ROOT / "artifacts"
    directory.mkdir(parents=True, exist_ok=True)
    paths = {key: directory / name for key, name in ARTIFACT_BASENAMES.items()}
    _write_csv(paths["subset_metrics"], SUBSET_METRICS_COLUMNS, output.subset_metrics_rows)
    _write_csv(
        paths["marginal_contribution"],
        MARGINAL_CONTRIBUTION_COLUMNS,
        output.marginal_contribution_rows,
    )
    matrix_columns = HIT_MATRIX_BASE_COLUMNS + output.adapter_names + HIT_MATRIX_TRAILING_COLUMNS
    _write_csv(paths["hit_matrix"], matrix_columns, output.hit_matrix_rows)
    _write_csv(paths["manifest"], MANIFEST_COLUMNS, output.manifest_rows)
    with open(paths["report"], "w", encoding="utf-8") as handle:
        handle.write(render_report(output))
    return paths


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=None, help="override fixture path (tests only)")
    parser.add_argument("--artifacts-dir", type=Path, default=None, help="override artifacts directory")
    args = parser.parse_args(argv)
    first = run_coverage_utility(args.fixture)
    second = run_coverage_utility(args.fixture)
    if (
        first.subset_metrics_rows != second.subset_metrics_rows
        or first.marginal_contribution_rows != second.marginal_contribution_rows
        or first.hit_matrix_rows != second.hit_matrix_rows
        or first.manifest_rows != second.manifest_rows
    ):
        raise RuntimeError("determinism double-run mismatch: P361 artifacts are not reproducible")
    paths = write_artifacts(first, args.artifacts_dir)
    print("P361 no-DB coverage utility: determinism double-run PASS")
    print(f"fixture sha256: {first.fixture_sha256}")
    print(f"scoreable periods: {first.scoreable_period_count}")
    for key, path in sorted(paths.items()):
        print(f"artifact[{key}]: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
