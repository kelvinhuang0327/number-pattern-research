"""P362 no-DB rolling subset stability drilldown for Big Lotto adapters.

This module builds on the committed P360/P361 no-DB evidence and evaluates
whether P361 compact coverage findings are stable across trailing historical
windows. It is descriptive only: no DB access, no production registry import,
no blended leaderboard, no betting advice, and no future prediction guarantee.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from statistics import mean, pvariance
from typing import Iterable, Mapping

from recovered_strategies.biglotto import historical_adapters
from recovered_strategies.biglotto import no_db_coverage_utility as p361
from recovered_strategies.biglotto import no_db_multiwindow_validation as p360

REPO_ROOT = p360.REPO_ROOT
TASK = "P362_biglotto_subset_stability"
WINDOWS = p360.WINDOWS
FOCUS_COMPACT_SUBSET = (
    "adapt_biglotto_p0_2bet",
    "adapt_predict_biglotto_echo_mixed_3bet",
)

REQUIRED_EVIDENCE_RELPATHS = (
    "recovered_strategies/biglotto/no_db_multiwindow_validation.py",
    "recovered_strategies/biglotto/no_db_coverage_utility.py",
    "tests/test_p360_biglotto_no_db_multiwindow_validation.py",
    "tests/test_p361_biglotto_coverage_utility.py",
    "artifacts/P360_biglotto_no_db_multiwindow_validation_results.csv",
    "artifacts/P360_biglotto_no_db_multiwindow_validation_coverage.csv",
    "artifacts/P361_biglotto_coverage_utility_subset_metrics.csv",
    "artifacts/P361_biglotto_coverage_utility_marginal_contribution.csv",
    "artifacts/P361_biglotto_coverage_utility_hit_matrix.csv",
    "artifacts/P361_biglotto_coverage_utility_manifest.csv",
    "artifacts/P361_biglotto_coverage_utility_report.md",
)

WINDOW_METRICS_COLUMNS = (
    "subset_size",
    "adapter_subset",
    "total_ticket_count",
    "window_size",
    "period_count",
    "any_hit_count",
    "coverage_rate",
    "duplicate_hit_events",
    "mean_pairwise_jaccard",
    "same_total_bet_count_baseline",
    "edge_vs_same_total_bet_baseline",
    "rank_by_coverage_rate",
    "rank_by_any_hit_count",
    "within_1_hit_of_full_cohort",
    "within_3_hits_of_full_cohort",
    "fixture_sha256",
)

RANK_SUMMARY_COLUMNS = (
    "adapter_subset",
    "subset_size",
    "average_rank_by_coverage_rate",
    "rank_variance_by_coverage_rate",
    "average_rank_by_any_hit_count",
    "rank_variance_by_any_hit_count",
    "top_1_window_count",
    "top_3_window_count",
    "within_3_hits_of_full_cohort_window_count",
    "windows_evaluated",
    "fixture_sha256",
)

COMPACT_CANDIDATES_COLUMNS = (
    "row_type",
    "window_size",
    "subset_size",
    "adapter_subset",
    "total_ticket_count",
    "any_hit_count",
    "full_cohort_any_hit_count",
    "hit_gap_to_full_cohort",
    "coverage_rate",
    "duplicate_hit_events",
    "mean_pairwise_jaccard",
    "within_1_hit_of_full_cohort",
    "within_3_hits_of_full_cohort",
    "note",
    "fixture_sha256",
)

MANIFEST_COLUMNS = ("key", "value")

ARTIFACT_BASENAMES = {
    "window_metrics": "P362_biglotto_subset_stability_window_metrics.csv",
    "rank_summary": "P362_biglotto_subset_stability_rank_summary.csv",
    "compact_candidates": "P362_biglotto_subset_stability_compact_candidates.csv",
    "manifest": "P362_biglotto_subset_stability_manifest.csv",
    "report": "P362_biglotto_subset_stability_report.md",
}


@dataclass(frozen=True)
class SubsetStabilityOutput:
    fixture_sha256: str
    draw_count: int
    scoreable_period_count: int
    adapter_names: tuple[str, ...]
    window_metrics_rows: tuple[dict[str, str], ...]
    rank_summary_rows: tuple[dict[str, str], ...]
    compact_candidate_rows: tuple[dict[str, str], ...]
    manifest_rows: tuple[dict[str, str], ...]


def verify_required_evidence(repo_root: Path | None = None) -> tuple[Path, ...]:
    root = Path(repo_root) if repo_root is not None else REPO_ROOT
    missing = [relpath for relpath in REQUIRED_EVIDENCE_RELPATHS if not (root / relpath).is_file()]
    if missing:
        raise p360.FixtureValidationError(f"required P360/P361 evidence missing: {missing}")
    return tuple(root / relpath for relpath in REQUIRED_EVIDENCE_RELPATHS)


def resolve_scoring_adapters(
    requested: Iterable[str] = p360.ALLOWLISTED_ADAPTERS,
) -> tuple[p360.AdapterSpec, ...]:
    requested = tuple(requested)
    if requested != p360.ALLOWLISTED_ADAPTERS:
        raise p360.AdapterSelectionError(
            "P362 scoring cohort must be the exact P361 5-adapter parity allowlist"
        )
    return p360.resolve_scoring_adapters(requested)


def enumerate_adapter_subsets(adapter_names: Iterable[str]) -> tuple[tuple[str, ...], ...]:
    names = tuple(adapter_names)
    subsets: list[tuple[str, ...]] = []
    for subset_size in range(1, len(names) + 1):
        subsets.extend(combinations(names, subset_size))
    return tuple(subsets)


def _union_hit_set(names: Iterable[str], hit_sets: Mapping[str, set[int]]) -> set[int]:
    union: set[int] = set()
    for name in names:
        union |= hit_sets[name]
    return union


def _mean_pairwise_jaccard(names: tuple[str, ...], hit_sets: Mapping[str, set[int]]) -> str:
    values = []
    for left, right in combinations(names, 2):
        union = hit_sets[left] | hit_sets[right]
        values.append((len(hit_sets[left] & hit_sets[right]) / len(union)) if union else 0.0)
    return f"{mean(values):.8f}" if values else ""


def _window_hit_sets(
    hit_sets: Mapping[str, set[int]], adapter_names: Iterable[str], tail_periods: set[int]
) -> dict[str, set[int]]:
    return {name: hit_sets[name] & tail_periods for name in adapter_names}


def _ticket_counts(specs: Iterable[p360.AdapterSpec]) -> dict[str, int]:
    return {spec.name: spec.bet_count for spec in specs}


def _rank_rows(rows: Iterable[dict[str, str]], rank_column: str) -> dict[str, int]:
    ordered = sorted(
        rows,
        key=lambda row: (
            -int(row["any_hit_count"]),
            int(row["duplicate_hit_events"]),
            int(row["total_ticket_count"]),
            row["adapter_subset"],
        ),
    )
    return {row["adapter_subset"]: rank for rank, row in enumerate(ordered, start=1)}


def compute_window_metrics_rows(
    periods: Iterable[int],
    hit_sets: Mapping[str, set[int]],
    specs: Iterable[p360.AdapterSpec],
    fixture_sha256: str,
    windows: Iterable[int] = WINDOWS,
) -> tuple[dict[str, str], ...]:
    periods = tuple(periods)
    specs = tuple(specs)
    adapter_names = tuple(spec.name for spec in specs)
    bet_counts = _ticket_counts(specs)
    subsets = enumerate_adapter_subsets(adapter_names)
    rows: list[dict[str, str]] = []
    for window in windows:
        if window > len(periods):
            raise p360.FixtureValidationError(
                f"window {window} exceeds scoreable periods {len(periods)}"
            )
        tail_periods = set(periods[-window:])
        window_sets = _window_hit_sets(hit_sets, adapter_names, tail_periods)
        full_hits = _union_hit_set(adapter_names, window_sets)
        unranked_rows: list[dict[str, str]] = []
        for subset in subsets:
            union = _union_hit_set(subset, window_sets)
            hit_counts_by_period = [
                sum(1 for name in subset if period in window_sets[name]) for period in periods[-window:]
            ]
            duplicate_events = sum(max(0, count - 1) for count in hit_counts_by_period)
            total_ticket_count = sum(bet_counts[name] for name in subset)
            coverage_rate = len(union) / window
            baseline = p360.compute_baseline(total_ticket_count)
            gap_to_full = len(full_hits) - len(union)
            unranked_rows.append(
                {
                    "subset_size": str(len(subset)),
                    "adapter_subset": ";".join(subset),
                    "total_ticket_count": str(total_ticket_count),
                    "window_size": str(window),
                    "period_count": str(window),
                    "any_hit_count": str(len(union)),
                    "coverage_rate": f"{coverage_rate:.8f}",
                    "duplicate_hit_events": str(duplicate_events),
                    "mean_pairwise_jaccard": _mean_pairwise_jaccard(subset, window_sets),
                    "same_total_bet_count_baseline": f"{baseline:.8f}",
                    "edge_vs_same_total_bet_baseline": f"{coverage_rate - baseline:.8f}",
                    "rank_by_coverage_rate": "",
                    "rank_by_any_hit_count": "",
                    "within_1_hit_of_full_cohort": "true" if gap_to_full <= 1 else "false",
                    "within_3_hits_of_full_cohort": "true" if gap_to_full <= 3 else "false",
                    "fixture_sha256": fixture_sha256,
                }
            )
        coverage_ranks = _rank_rows(unranked_rows, "rank_by_coverage_rate")
        hit_count_ranks = _rank_rows(unranked_rows, "rank_by_any_hit_count")
        for row in unranked_rows:
            ranked = dict(row)
            ranked["rank_by_coverage_rate"] = str(coverage_ranks[row["adapter_subset"]])
            ranked["rank_by_any_hit_count"] = str(hit_count_ranks[row["adapter_subset"]])
            rows.append(ranked)
    return tuple(rows)


def compute_rank_summary_rows(
    window_metrics_rows: Iterable[dict[str, str]], fixture_sha256: str
) -> tuple[dict[str, str], ...]:
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in window_metrics_rows:
        grouped.setdefault(row["adapter_subset"], []).append(row)
    summary_rows = []
    for adapter_subset in sorted(grouped):
        rows = sorted(grouped[adapter_subset], key=lambda row: int(row["window_size"]))
        coverage_ranks = [int(row["rank_by_coverage_rate"]) for row in rows]
        hit_count_ranks = [int(row["rank_by_any_hit_count"]) for row in rows]
        summary_rows.append(
            {
                "adapter_subset": adapter_subset,
                "subset_size": rows[0]["subset_size"],
                "average_rank_by_coverage_rate": f"{mean(coverage_ranks):.4f}",
                "rank_variance_by_coverage_rate": f"{pvariance(coverage_ranks):.4f}",
                "average_rank_by_any_hit_count": f"{mean(hit_count_ranks):.4f}",
                "rank_variance_by_any_hit_count": f"{pvariance(hit_count_ranks):.4f}",
                "top_1_window_count": str(sum(1 for rank in coverage_ranks if rank == 1)),
                "top_3_window_count": str(sum(1 for rank in coverage_ranks if rank <= 3)),
                "within_3_hits_of_full_cohort_window_count": str(
                    sum(1 for row in rows if row["within_3_hits_of_full_cohort"] == "true")
                ),
                "windows_evaluated": str(len(rows)),
                "fixture_sha256": fixture_sha256,
            }
        )
    return tuple(
        sorted(
            summary_rows,
            key=lambda row: (
                float(row["average_rank_by_coverage_rate"]),
                float(row["rank_variance_by_coverage_rate"]),
                int(row["subset_size"]),
                row["adapter_subset"],
            ),
        )
    )


def _candidate_row(
    row_type: str,
    row: Mapping[str, str],
    full_any_hit_count: int,
    note: str,
) -> dict[str, str]:
    any_hit_count = int(row["any_hit_count"])
    gap = full_any_hit_count - any_hit_count
    return {
        "row_type": row_type,
        "window_size": row["window_size"],
        "subset_size": row["subset_size"],
        "adapter_subset": row["adapter_subset"],
        "total_ticket_count": row["total_ticket_count"],
        "any_hit_count": row["any_hit_count"],
        "full_cohort_any_hit_count": str(full_any_hit_count),
        "hit_gap_to_full_cohort": str(gap),
        "coverage_rate": row["coverage_rate"],
        "duplicate_hit_events": row["duplicate_hit_events"],
        "mean_pairwise_jaccard": row["mean_pairwise_jaccard"],
        "within_1_hit_of_full_cohort": "true" if gap <= 1 else "false",
        "within_3_hits_of_full_cohort": "true" if gap <= 3 else "false",
        "note": note,
        "fixture_sha256": row["fixture_sha256"],
    }


def compute_compact_candidate_rows(
    window_metrics_rows: Iterable[dict[str, str]], adapter_names: Iterable[str]
) -> tuple[dict[str, str], ...]:
    adapter_names = tuple(adapter_names)
    full_subset = ";".join(adapter_names)
    focus_subset = ";".join(FOCUS_COMPACT_SUBSET)
    grouped: dict[int, list[dict[str, str]]] = {}
    for row in window_metrics_rows:
        grouped.setdefault(int(row["window_size"]), []).append(row)
    candidate_rows: list[dict[str, str]] = []
    for window in sorted(grouped):
        rows = grouped[window]
        full_row = next(row for row in rows if row["adapter_subset"] == full_subset)
        full_any_hit_count = int(full_row["any_hit_count"])
        for subset_size in range(1, len(adapter_names) + 1):
            same_size = [row for row in rows if int(row["subset_size"]) == subset_size]
            best = sorted(
                same_size,
                key=lambda row: (
                    -int(row["any_hit_count"]),
                    int(row["duplicate_hit_events"]),
                    int(row["total_ticket_count"]),
                    row["adapter_subset"],
                ),
            )[0]
            candidate_rows.append(
                _candidate_row(
                    "best_subset_for_size",
                    best,
                    full_any_hit_count,
                    f"Best historical coverage among subsets of size {subset_size}.",
                )
            )
        for tolerance in (1, 3):
            eligible = [
                row for row in rows if full_any_hit_count - int(row["any_hit_count"]) <= tolerance
            ]
            smallest = sorted(
                eligible,
                key=lambda row: (
                    int(row["subset_size"]),
                    -int(row["any_hit_count"]),
                    int(row["duplicate_hit_events"]),
                    int(row["total_ticket_count"]),
                    row["adapter_subset"],
                ),
            )[0]
            candidate_rows.append(
                _candidate_row(
                    f"smallest_within_{tolerance}_hit_of_full_cohort",
                    smallest,
                    full_any_hit_count,
                    f"Smallest subset within {tolerance} any-hit period(s) of the full cohort.",
                )
            )
        focus = next(row for row in rows if row["adapter_subset"] == focus_subset)
        focus_gap = full_any_hit_count - int(focus["any_hit_count"])
        candidate_rows.append(
            _candidate_row(
                "p361_compact_pair_check",
                focus,
                full_any_hit_count,
                "P361 compact pair remains within 3 hits of full cohort."
                if focus_gap <= 3
                else "P361 compact pair is not within 3 hits of full cohort in this window.",
            )
        )
    return tuple(candidate_rows)


def build_manifest_rows(output_fields: Mapping[str, object]) -> tuple[dict[str, str], ...]:
    return tuple({"key": key, "value": str(value)} for key, value in output_fields.items())


def run_subset_stability(fixture_path: Path | None = None) -> SubsetStabilityOutput:
    if fixture_path is None:
        verify_required_evidence()
    draws, sha256 = p360.load_big_lotto_draws(fixture_path)
    if fixture_path is None and sha256 != p360.EXPECTED_FIXTURE_SHA256:
        raise p360.FixtureValidationError(
            f"fixture SHA256 mismatch: expected {p360.EXPECTED_FIXTURE_SHA256}, got {sha256}"
        )
    specs = resolve_scoring_adapters()
    adapter_names = tuple(spec.name for spec in specs)
    records = p360.run_walk_forward(draws, {spec.name: spec.fn for spec in specs})
    periods, hit_sets = p361.build_hit_sets(records, adapter_names)
    window_rows = compute_window_metrics_rows(periods, hit_sets, specs, sha256)
    rank_rows = compute_rank_summary_rows(window_rows, sha256)
    compact_rows = compute_compact_candidate_rows(window_rows, adapter_names)
    focus_rows = [row for row in compact_rows if row["row_type"] == "p361_compact_pair_check"]
    manifest_rows = build_manifest_rows(
        {
            "task": TASK,
            "source_tasks": "P360_biglotto_no_db_multiwindow_validation;P361_biglotto_coverage_utility",
            "fixture_relpath": p360.FIXTURE_RELPATH,
            "fixture_sha256": sha256,
            "big_lotto_row_count": len(draws),
            "lookback_draws": p360.LOOKBACK,
            "scoreable_period_count": len(periods),
            "first_scoreable_period": periods[0],
            "last_scoreable_period": periods[-1],
            "windows": ";".join(str(w) for w in WINDOWS),
            "adapter_count": len(adapter_names),
            "adapters": ";".join(adapter_names),
            "subset_count_per_window": len(enumerate_adapter_subsets(adapter_names)),
            "window_metric_rows": len(window_rows),
            "rank_summary_rows": len(rank_rows),
            "compact_candidate_rows": len(compact_rows),
            "focus_compact_subset": ";".join(FOCUS_COMPACT_SUBSET),
            "focus_compact_subset_within_3_hits_all_windows": str(
                all(row["within_3_hits_of_full_cohort"] == "true" for row in focus_rows)
            ).upper(),
            "baseline_formula": p360.BASELINE_FORMULA.replace("bet_count", "total_ticket_count"),
            "baseline_single_ticket_p": p360.BASELINE_SINGLE_TICKET_P,
            "baseline_note": "same-total-bet-count independent-ticket approximation, not proof of edge",
            "hit_definition": f"any ticket matching >={p360.HIT_THRESHOLD_MAINS} main numbers",
            "tier": p360.TIER,
            "required_parity_status": p360.REQUIRED_PARITY_STATUS,
            "db_opened": "NO",
            "db_written": "NO",
            "production_registry_imported": "NO",
            "strategy_status_changed": "NO",
            "blended_leaderboard": "NO",
            "future_prediction_claim": "NO",
            "betting_advice": "NO",
        }
    )
    return SubsetStabilityOutput(
        fixture_sha256=sha256,
        draw_count=len(draws),
        scoreable_period_count=len(periods),
        adapter_names=adapter_names,
        window_metrics_rows=window_rows,
        rank_summary_rows=rank_rows,
        compact_candidate_rows=compact_rows,
        manifest_rows=manifest_rows,
    )


def _markdown_table(columns: Iterable[str], rows: Iterable[Mapping[str, str]]) -> str:
    columns = list(columns)
    lines = ["| " + " | ".join(columns) + " |", "|" + "|".join(" --- " for _ in columns) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(str(row[column]) for column in columns) + " |")
    return "\n".join(lines)


def render_report(output: SubsetStabilityOutput) -> str:
    excluded_shape_only = sorted(
        name
        for name, meta in historical_adapters.ADAPTER_METADATA.items()
        if meta.get("parity_status") != p360.REQUIRED_PARITY_STATUS
    )
    best_by_size = [
        row for row in output.compact_candidate_rows if row["row_type"] == "best_subset_for_size"
    ]
    smallest_rows = [
        row
        for row in output.compact_candidate_rows
        if row["row_type"].startswith("smallest_within_")
    ]
    focus_rows = [
        row for row in output.compact_candidate_rows if row["row_type"] == "p361_compact_pair_check"
    ]
    top_rank_rows = output.rank_summary_rows[:10]
    parts = [
        "# P362 Big Lotto no-DB Rolling Subset Stability Drilldown",
        "",
        "## Scope statements",
        "",
        "- This is historical descriptive subset stability only.",
        "- No future prediction guarantee. Past coverage stability does not predict future draws.",
        "- No betting advice. Nothing here recommends placing any bet.",
        "- No DB was opened or written. The data source remains the committed JSONL fixture and P360/P361 no-DB evidence.",
        "- No production registry import, no deploy, no migration/backfill, and no strategy status change.",
        "- No blended leaderboard: P356/P358/P360/P361 results are not merged into any cross-task ranking.",
        "- Shape/safety-only adapters and blocked targets were excluded from scoring: "
        + ", ".join(f"`{name}`" for name in excluded_shape_only)
        + ".",
        "",
        "## Method",
        "",
        f"- Source modules: `recovered_strategies/biglotto/no_db_multiwindow_validation.py` and `recovered_strategies/biglotto/no_db_coverage_utility.py`.",
        f"- Fixture: `{p360.FIXTURE_RELPATH}`",
        f"- Fixture SHA256: `{output.fixture_sha256}`",
        f"- BIG_LOTTO rows: {output.draw_count}; scoreable periods: {output.scoreable_period_count}.",
        f"- Adapter cohort: {', '.join(f'`{name}`' for name in output.adapter_names)}.",
        f"- Windows: {', '.join(str(window) for window in WINDOWS)} trailing periods.",
        f"- Subsets: all {2 ** len(output.adapter_names) - 1} non-empty subsets of the parity-only adapter cohort.",
        f"- Baseline: `{p360.BASELINE_FORMULA.replace('bet_count', 'total_ticket_count')}`; same-total-bet-count independent-ticket approximation, not proof of edge.",
        "",
        "## Best subset by size and window",
        "",
        _markdown_table(
            (
                "window_size",
                "subset_size",
                "adapter_subset",
                "any_hit_count",
                "full_cohort_any_hit_count",
                "hit_gap_to_full_cohort",
                "coverage_rate",
                "duplicate_hit_events",
                "mean_pairwise_jaccard",
            ),
            best_by_size,
        ),
        "",
        "## Compact candidate thresholds",
        "",
        _markdown_table(
            (
                "row_type",
                "window_size",
                "subset_size",
                "adapter_subset",
                "any_hit_count",
                "full_cohort_any_hit_count",
                "hit_gap_to_full_cohort",
            ),
            smallest_rows,
        ),
        "",
        "## P361 compact pair check",
        "",
        _markdown_table(
            (
                "window_size",
                "adapter_subset",
                "any_hit_count",
                "full_cohort_any_hit_count",
                "hit_gap_to_full_cohort",
                "within_3_hits_of_full_cohort",
                "note",
            ),
            focus_rows,
        ),
        "",
        "## Rank stability summary",
        "",
        _markdown_table(
            (
                "adapter_subset",
                "subset_size",
                "average_rank_by_coverage_rate",
                "rank_variance_by_coverage_rate",
                "top_1_window_count",
                "top_3_window_count",
                "within_3_hits_of_full_cohort_window_count",
            ),
            top_rank_rows,
        ),
        "",
        "## Artifact inventory",
        "",
        "- `artifacts/P362_biglotto_subset_stability_window_metrics.csv`",
        "- `artifacts/P362_biglotto_subset_stability_rank_summary.csv`",
        "- `artifacts/P362_biglotto_subset_stability_compact_candidates.csv`",
        "- `artifacts/P362_biglotto_subset_stability_manifest.csv`",
        "- `artifacts/P362_biglotto_subset_stability_report.md`",
        "",
    ]
    return "\n".join(parts)


def _write_csv(path: Path, columns: Iterable[str], rows: Iterable[Mapping[str, str]]) -> None:
    columns = list(columns)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_artifacts(
    output: SubsetStabilityOutput, artifacts_dir: Path | None = None
) -> dict[str, Path]:
    directory = Path(artifacts_dir) if artifacts_dir is not None else REPO_ROOT / "artifacts"
    directory.mkdir(parents=True, exist_ok=True)
    paths = {key: directory / name for key, name in ARTIFACT_BASENAMES.items()}
    _write_csv(paths["window_metrics"], WINDOW_METRICS_COLUMNS, output.window_metrics_rows)
    _write_csv(paths["rank_summary"], RANK_SUMMARY_COLUMNS, output.rank_summary_rows)
    _write_csv(
        paths["compact_candidates"],
        COMPACT_CANDIDATES_COLUMNS,
        output.compact_candidate_rows,
    )
    _write_csv(paths["manifest"], MANIFEST_COLUMNS, output.manifest_rows)
    with open(paths["report"], "w", encoding="utf-8") as handle:
        handle.write(render_report(output))
    return paths


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=None, help="override fixture path (tests only)")
    parser.add_argument("--artifacts-dir", type=Path, default=None, help="override artifacts directory")
    args = parser.parse_args(argv)
    first = run_subset_stability(args.fixture)
    second = run_subset_stability(args.fixture)
    if (
        first.window_metrics_rows != second.window_metrics_rows
        or first.rank_summary_rows != second.rank_summary_rows
        or first.compact_candidate_rows != second.compact_candidate_rows
        or first.manifest_rows != second.manifest_rows
    ):
        raise RuntimeError("determinism double-run mismatch: P362 artifacts are not reproducible")
    paths = write_artifacts(first, args.artifacts_dir)
    print("P362 no-DB subset stability: determinism double-run PASS")
    print(f"fixture sha256: {first.fixture_sha256}")
    print(f"scoreable periods: {first.scoreable_period_count}")
    for key, path in sorted(paths.items()):
        print(f"artifact[{key}]: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
