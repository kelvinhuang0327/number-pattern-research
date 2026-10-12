"""P363 no-DB consolidated evidence pack for Big Lotto parity adapters.

This module reads the merged P360/P361/P362 no-DB artifacts and consolidates
them into machine-readable cards, consistency checks, a source-artifact
manifest, and a human-readable report. It does not score strategies, open the
DB, import production registries, deploy, or make future-performance claims.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

from recovered_strategies.biglotto import no_db_multiwindow_validation as p360

REPO_ROOT = p360.REPO_ROOT
TASK = "P363_biglotto_evidence_pack"

EXPECTED_ADAPTERS = p360.ALLOWLISTED_ADAPTERS
EXPECTED_WINDOWS = p360.WINDOWS
EXPECTED_SUBSET_COUNT = 31
EXPECTED_HIT_MATRIX_PERIOD_COUNT = 1619

SOURCE_ARTIFACTS = (
    ("p360_results", "P360", "artifacts/P360_biglotto_no_db_multiwindow_validation_results.csv"),
    ("p360_manifest", "P360", "artifacts/P360_biglotto_no_db_multiwindow_validation_manifest.csv"),
    ("p360_coverage", "P360", "artifacts/P360_biglotto_no_db_multiwindow_validation_coverage.csv"),
    ("p360_report", "P360", "artifacts/P360_biglotto_no_db_multiwindow_validation_report.md"),
    ("p361_subset_metrics", "P361", "artifacts/P361_biglotto_coverage_utility_subset_metrics.csv"),
    ("p361_marginal_contribution", "P361", "artifacts/P361_biglotto_coverage_utility_marginal_contribution.csv"),
    ("p361_hit_matrix", "P361", "artifacts/P361_biglotto_coverage_utility_hit_matrix.csv"),
    ("p361_manifest", "P361", "artifacts/P361_biglotto_coverage_utility_manifest.csv"),
    ("p361_report", "P361", "artifacts/P361_biglotto_coverage_utility_report.md"),
    ("p362_window_metrics", "P362", "artifacts/P362_biglotto_subset_stability_window_metrics.csv"),
    ("p362_rank_summary", "P362", "artifacts/P362_biglotto_subset_stability_rank_summary.csv"),
    ("p362_compact_candidates", "P362", "artifacts/P362_biglotto_subset_stability_compact_candidates.csv"),
    ("p362_manifest", "P362", "artifacts/P362_biglotto_subset_stability_manifest.csv"),
    ("p362_report", "P362", "artifacts/P362_biglotto_subset_stability_report.md"),
)

SUMMARY_COLUMNS = ("section", "key", "value")

SOURCE_MANIFEST_COLUMNS = (
    "artifact_role",
    "source_task",
    "path",
    "file_type",
    "data_row_count",
    "line_count",
    "sha256",
    "manifest_expected_key",
    "manifest_expected_value",
    "row_count_matches_manifest",
)

ADAPTER_CARD_COLUMNS = (
    "adapter_function",
    "strategy_id",
    "bet_count",
    "p360_windows_present",
    "p360_hit_rate_w30",
    "p360_edge_w30",
    "p360_hit_rate_w150",
    "p360_edge_w150",
    "p360_hit_rate_w750",
    "p360_edge_w750",
    "p360_hit_rate_w1500",
    "p360_edge_w1500",
    "p361_total_hit_count",
    "p361_unique_hit_count",
    "p361_candidate_marginal_share_full_context",
    "p361_redundancy_note",
    "p362_singleton_average_rank_by_coverage_rate",
    "p362_singleton_top_3_window_count",
    "p362_singleton_within_3_hits_window_count",
    "p362_stability_note",
    "caveat",
)

SUBSET_CARD_COLUMNS = (
    "adapter_subset",
    "subset_size",
    "subset_is_full_cohort",
    "p361_rank_within_subset_size",
    "p361_best_subset_for_size",
    "p361_period_count",
    "p361_any_hit_count",
    "p361_coverage_rate",
    "p361_duplicate_hit_events",
    "p361_mean_pairwise_jaccard",
    "p362_windows_evaluated",
    "p362_average_rank_by_coverage_rate",
    "p362_rank_variance_by_coverage_rate",
    "p362_top_1_window_count",
    "p362_top_3_window_count",
    "p362_within_3_hits_window_count",
    "compact_candidate_row_types",
    "compact_candidate_windows",
    "p362_stability_note",
    "caveat",
)

CONSISTENCY_CHECK_COLUMNS = ("check_name", "status", "expected", "actual", "details")

ARTIFACT_BASENAMES = {
    "summary": "P363_biglotto_evidence_pack_summary.csv",
    "adapter_cards": "P363_biglotto_evidence_pack_adapter_cards.csv",
    "subset_cards": "P363_biglotto_evidence_pack_subset_cards.csv",
    "consistency_checks": "P363_biglotto_evidence_pack_consistency_checks.csv",
    "manifest": "P363_biglotto_evidence_pack_manifest.csv",
    "report": "P363_biglotto_evidence_pack_report.md",
}


@dataclass(frozen=True)
class EvidencePackOutput:
    summary_rows: tuple[dict[str, str], ...]
    source_manifest_rows: tuple[dict[str, str], ...]
    adapter_card_rows: tuple[dict[str, str], ...]
    subset_card_rows: tuple[dict[str, str], ...]
    consistency_check_rows: tuple[dict[str, str], ...]


class EvidencePackError(RuntimeError):
    """P363 source evidence is missing, malformed, or inconsistent."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv_rows(path: Path) -> tuple[dict[str, str], ...]:
    with open(path, newline="", encoding="utf-8") as handle:
        return tuple(dict(row) for row in csv.DictReader(handle))


def read_key_value_manifest(path: Path) -> dict[str, str]:
    return {row["key"]: row["value"] for row in read_csv_rows(path)}


def verify_required_artifacts(repo_root: Path | None = None) -> tuple[Path, ...]:
    root = Path(repo_root) if repo_root is not None else REPO_ROOT
    paths = tuple(root / relpath for _role, _task, relpath in SOURCE_ARTIFACTS)
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise EvidencePackError(f"required P360/P361/P362 artifacts missing: {missing}")
    return paths


def _line_count(path: Path) -> int:
    with open(path, "r", encoding="utf-8") as handle:
        return sum(1 for _line in handle)


def _manifest_expectations(
    p360_manifest: Mapping[str, str],
    p361_manifest: Mapping[str, str],
    p362_manifest: Mapping[str, str],
) -> dict[str, tuple[str, str]]:
    adapter_count = int(p360_manifest["adapter_count"])
    window_count = len(p360_manifest["windows"].split(";"))
    p360_coverage_count = (adapter_count * (adapter_count - 1) // 2) + adapter_count + window_count + 1
    return {
        "p360_results": ("adapter_count*window_count", str(adapter_count * window_count)),
        "p360_coverage": ("pairwise+unique+cohort_windows", str(p360_coverage_count)),
        "p361_subset_metrics": ("subset_metric_rows", p361_manifest["subset_metric_rows"]),
        "p361_marginal_contribution": (
            "marginal_contribution_rows",
            p361_manifest["marginal_contribution_rows"],
        ),
        "p361_hit_matrix": ("hit_matrix_rows", p361_manifest["hit_matrix_rows"]),
        "p362_window_metrics": ("window_metric_rows", p362_manifest["window_metric_rows"]),
        "p362_rank_summary": ("rank_summary_rows", p362_manifest["rank_summary_rows"]),
        "p362_compact_candidates": (
            "compact_candidate_rows",
            p362_manifest["compact_candidate_rows"],
        ),
    }


def build_source_manifest_rows(
    repo_root: Path | None = None,
) -> tuple[dict[str, str], ...]:
    root = Path(repo_root) if repo_root is not None else REPO_ROOT
    verify_required_artifacts(root)
    p360_manifest = read_key_value_manifest(root / "artifacts/P360_biglotto_no_db_multiwindow_validation_manifest.csv")
    p361_manifest = read_key_value_manifest(root / "artifacts/P361_biglotto_coverage_utility_manifest.csv")
    p362_manifest = read_key_value_manifest(root / "artifacts/P362_biglotto_subset_stability_manifest.csv")
    expectations = _manifest_expectations(p360_manifest, p361_manifest, p362_manifest)
    rows = []
    for role, source_task, relpath in SOURCE_ARTIFACTS:
        path = root / relpath
        file_type = path.suffix.lstrip(".")
        data_row_count = ""
        if file_type == "csv":
            data_row_count = str(len(read_csv_rows(path)))
        line_count = str(_line_count(path))
        expected_key, expected_value = expectations.get(role, ("", ""))
        matches = ""
        if expected_value:
            matches = "true" if data_row_count == expected_value else "false"
        rows.append(
            {
                "artifact_role": role,
                "source_task": source_task,
                "path": relpath,
                "file_type": file_type,
                "data_row_count": data_row_count,
                "line_count": line_count,
                "sha256": sha256_file(path),
                "manifest_expected_key": expected_key,
                "manifest_expected_value": expected_value,
                "row_count_matches_manifest": matches,
            }
        )
    return tuple(rows)


def _adapter_set_from_p360_results(rows: Iterable[Mapping[str, str]]) -> tuple[str, ...]:
    return tuple(sorted({row["adapter_function"] for row in rows}))


def _adapter_set_from_p361(rows: Iterable[Mapping[str, str]]) -> tuple[str, ...]:
    names: set[str] = set()
    for row in rows:
        names.update(name for name in row["adapter_subset"].split(";") if name)
    return tuple(sorted(names))


def _adapter_set_from_hit_matrix(rows: Iterable[Mapping[str, str]]) -> tuple[str, ...]:
    first = next(iter(rows), None)
    if not first:
        return tuple()
    excluded = {"period", "cohort_hit_count", "cohort_any_hit", "fixture_sha256"}
    return tuple(sorted(column for column in first if column not in excluded))


def _adapter_set_from_p362(rows: Iterable[Mapping[str, str]]) -> tuple[str, ...]:
    names: set[str] = set()
    for row in rows:
        names.update(name for name in row["adapter_subset"].split(";") if name)
    return tuple(sorted(names))


def _check(name: str, passed: bool, expected: object, actual: object, details: str = "") -> dict[str, str]:
    return {
        "check_name": name,
        "status": "PASS" if passed else "FAIL",
        "expected": str(expected),
        "actual": str(actual),
        "details": details,
    }


def build_consistency_check_rows(
    p360_results: tuple[dict[str, str], ...],
    p360_coverage: tuple[dict[str, str], ...],
    p360_manifest: Mapping[str, str],
    p361_subset_metrics: tuple[dict[str, str], ...],
    p361_marginal: tuple[dict[str, str], ...],
    p361_hit_matrix: tuple[dict[str, str], ...],
    p361_manifest: Mapping[str, str],
    p362_window_metrics: tuple[dict[str, str], ...],
    p362_rank_summary: tuple[dict[str, str], ...],
    p362_compact_candidates: tuple[dict[str, str], ...],
    p362_manifest: Mapping[str, str],
    source_manifest_rows: tuple[dict[str, str], ...],
) -> tuple[dict[str, str], ...]:
    expected_adapters = tuple(sorted(EXPECTED_ADAPTERS))
    p360_adapters = _adapter_set_from_p360_results(p360_results)
    p361_adapters = _adapter_set_from_p361(p361_subset_metrics)
    hit_matrix_adapters = _adapter_set_from_hit_matrix(p361_hit_matrix)
    p362_adapters = _adapter_set_from_p362(p362_window_metrics)
    p360_windows = tuple(sorted({int(row["window_size"]) for row in p360_results}))
    p362_windows = tuple(sorted({int(row["window_size"]) for row in p362_window_metrics}))
    p361_subsets = {row["adapter_subset"] for row in p361_subset_metrics}
    p362_subsets = {row["adapter_subset"] for row in p362_window_metrics}
    compact_refs = {row["adapter_subset"] for row in p362_compact_candidates}
    row_count_matches = [
        row for row in source_manifest_rows if row["row_count_matches_manifest"] in {"true", "false"}
    ]
    rows = [
        _check(
            "exact_5_parity_adapter_names_consistent",
            p360_adapters == p361_adapters == hit_matrix_adapters == p362_adapters == expected_adapters,
            ";".join(expected_adapters),
            (
                f"P360={';'.join(p360_adapters)} | P361={';'.join(p361_adapters)} | "
                f"hit_matrix={';'.join(hit_matrix_adapters)} | P362={';'.join(p362_adapters)}"
            ),
            "Adapter names are read from committed P360/P361/P362 artifacts.",
        ),
        _check(
            "expected_windows_present",
            p360_windows == EXPECTED_WINDOWS and p362_windows == EXPECTED_WINDOWS,
            ";".join(str(window) for window in EXPECTED_WINDOWS),
            f"P360={';'.join(str(w) for w in p360_windows)} | P362={';'.join(str(w) for w in p362_windows)}",
            "P363 does not add or remove evaluation windows.",
        ),
        _check(
            "p361_subset_count",
            len(p361_subset_metrics) == EXPECTED_SUBSET_COUNT,
            EXPECTED_SUBSET_COUNT,
            len(p361_subset_metrics),
            "Every non-empty subset of five adapters should appear exactly once.",
        ),
        _check(
            "p361_hit_matrix_period_count",
            len(p361_hit_matrix) == EXPECTED_HIT_MATRIX_PERIOD_COUNT,
            EXPECTED_HIT_MATRIX_PERIOD_COUNT,
            len(p361_hit_matrix),
            "Period-level historical hit matrix remains the P360 scoreable range.",
        ),
        _check(
            "p362_compact_candidates_reference_valid_subsets",
            compact_refs <= p362_subsets and compact_refs <= p361_subsets,
            "all compact candidate subsets present in P361 and P362 subset artifacts",
            ";".join(sorted(compact_refs - (p362_subsets & p361_subsets))) or "all valid",
            "Compact candidate cards are descriptive labels over existing subsets.",
        ),
        _check(
            "source_artifact_row_counts_match_manifests",
            all(row["row_count_matches_manifest"] == "true" for row in row_count_matches),
            "all manifest-backed source row counts match",
            ";".join(
                f"{row['artifact_role']}={row['data_row_count']}/{row['manifest_expected_value']}"
                for row in row_count_matches
            ),
            "Manifest-backed checks are applied where P360/P361/P362 publish expected row counts.",
        ),
        _check(
            "p360_manifest_adapter_and_window_counts",
            p360_manifest.get("adapter_count") == "5" and p360_manifest.get("windows") == "30;150;750;1500",
            "adapter_count=5; windows=30;150;750;1500",
            f"adapter_count={p360_manifest.get('adapter_count')}; windows={p360_manifest.get('windows')}",
            "Confirms P360 manifest agrees with the card dimensions.",
        ),
        _check(
            "p361_manifest_subset_and_matrix_counts",
            p361_manifest.get("subset_metric_rows") == "31"
            and p361_manifest.get("hit_matrix_rows") == "1619",
            "subset_metric_rows=31; hit_matrix_rows=1619",
            (
                f"subset_metric_rows={p361_manifest.get('subset_metric_rows')}; "
                f"hit_matrix_rows={p361_manifest.get('hit_matrix_rows')}"
            ),
            "Confirms P361 manifest remains aligned with committed artifact rows.",
        ),
        _check(
            "p362_manifest_subset_stability_counts",
            p362_manifest.get("subset_count_per_window") == "31"
            and p362_manifest.get("rank_summary_rows") == "31"
            and p362_manifest.get("compact_candidate_rows") == "32",
            "subset_count_per_window=31; rank_summary_rows=31; compact_candidate_rows=32",
            (
                f"subset_count_per_window={p362_manifest.get('subset_count_per_window')}; "
                f"rank_summary_rows={p362_manifest.get('rank_summary_rows')}; "
                f"compact_candidate_rows={p362_manifest.get('compact_candidate_rows')}"
            ),
            "Confirms P362 subset/card dimensions are unchanged.",
        ),
    ]
    if len(p360_coverage) != 20:
        rows.append(_check("p360_coverage_row_count", False, 20, len(p360_coverage)))
    if len(p361_marginal) != 80:
        rows.append(_check("p361_marginal_row_count", False, 80, len(p361_marginal)))
    if len(p362_rank_summary) != 31:
        rows.append(_check("p362_rank_summary_row_count", False, 31, len(p362_rank_summary)))
    return tuple(rows)


def _p360_rows_by_adapter_window(
    p360_results: Iterable[Mapping[str, str]],
) -> dict[tuple[str, str], Mapping[str, str]]:
    return {(row["adapter_function"], row["window_size"]): row for row in p360_results}


def _max_pairwise_jaccard_note(adapter: str, p360_coverage: Iterable[Mapping[str, str]]) -> str:
    values = []
    for row in p360_coverage:
        if row["row_type"] != "pairwise":
            continue
        if adapter not in {row["adapter_a"], row["adapter_b"]}:
            continue
        other = row["adapter_b"] if row["adapter_a"] == adapter else row["adapter_a"]
        values.append((float(row["jaccard"]), other))
    if not values:
        return "No pairwise redundancy row available."
    max_jaccard, other = max(values, key=lambda item: (item[0], item[1]))
    if max_jaccard >= 0.80:
        return f"High overlap screen: max Jaccard {max_jaccard:.8f} versus {other}."
    return f"No near-duplicate screen hit; max pairwise Jaccard {max_jaccard:.8f} versus {other}."


def build_adapter_card_rows(
    p360_results: tuple[dict[str, str], ...],
    p360_coverage: tuple[dict[str, str], ...],
    p361_marginal: tuple[dict[str, str], ...],
    p362_rank_summary: tuple[dict[str, str], ...],
) -> tuple[dict[str, str], ...]:
    p360_by_window = _p360_rows_by_adapter_window(p360_results)
    p361_full_context = {
        row["candidate_adapter"]: row
        for row in p361_marginal
        if row["context_size"] == str(len(EXPECTED_ADAPTERS) - 1)
    }
    p362_singletons = {row["adapter_subset"]: row for row in p362_rank_summary if row["subset_size"] == "1"}
    rows = []
    for adapter in EXPECTED_ADAPTERS:
        first_window = p360_by_window[(adapter, str(EXPECTED_WINDOWS[0]))]
        full_context = p361_full_context[adapter]
        singleton = p362_singletons[adapter]
        row = {
            "adapter_function": adapter,
            "strategy_id": first_window["strategy_id"],
            "bet_count": first_window["bet_count"],
            "p360_windows_present": ";".join(
                window for window in (str(value) for value in EXPECTED_WINDOWS)
                if (adapter, window) in p360_by_window
            ),
            "p361_total_hit_count": full_context["candidate_total_hit_count"],
            "p361_unique_hit_count": full_context["marginal_unique_hit_count"],
            "p361_candidate_marginal_share_full_context": full_context["candidate_marginal_share"],
            "p361_redundancy_note": _max_pairwise_jaccard_note(adapter, p360_coverage),
            "p362_singleton_average_rank_by_coverage_rate": singleton["average_rank_by_coverage_rate"],
            "p362_singleton_top_3_window_count": singleton["top_3_window_count"],
            "p362_singleton_within_3_hits_window_count": singleton[
                "within_3_hits_of_full_cohort_window_count"
            ],
            "p362_stability_note": (
                f"Singleton evaluated across {singleton['windows_evaluated']} windows; "
                f"top-3 in {singleton['top_3_window_count']} window(s)."
            ),
            "caveat": "Historical descriptive evidence only; no betting advice or future prediction guarantee.",
        }
        for window in EXPECTED_WINDOWS:
            result = p360_by_window[(adapter, str(window))]
            row[f"p360_hit_rate_w{window}"] = result["hit_rate"]
            row[f"p360_edge_w{window}"] = result["edge_vs_same_bet_count_baseline"]
        rows.append(row)
    return tuple(rows)


def build_subset_card_rows(
    p361_subset_metrics: tuple[dict[str, str], ...],
    p362_rank_summary: tuple[dict[str, str], ...],
    p362_compact_candidates: tuple[dict[str, str], ...],
) -> tuple[dict[str, str], ...]:
    rank_by_subset = {row["adapter_subset"]: row for row in p362_rank_summary}
    compact_by_subset: dict[str, list[dict[str, str]]] = {}
    for row in p362_compact_candidates:
        compact_by_subset.setdefault(row["adapter_subset"], []).append(row)
    full_subset = ";".join(EXPECTED_ADAPTERS)
    rows = []
    for subset_row in sorted(
        p361_subset_metrics,
        key=lambda row: (int(row["subset_size"]), int(row["rank_within_subset_size"]), row["adapter_subset"]),
    ):
        subset = subset_row["adapter_subset"]
        rank_row = rank_by_subset[subset]
        compact_rows = sorted(
            compact_by_subset.get(subset, []),
            key=lambda row: (int(row["window_size"]), row["row_type"]),
        )
        rows.append(
            {
                "adapter_subset": subset,
                "subset_size": subset_row["subset_size"],
                "subset_is_full_cohort": "true" if subset == full_subset else "false",
                "p361_rank_within_subset_size": subset_row["rank_within_subset_size"],
                "p361_best_subset_for_size": subset_row["best_subset_for_size"],
                "p361_period_count": subset_row["period_count"],
                "p361_any_hit_count": subset_row["any_hit_count"],
                "p361_coverage_rate": subset_row["coverage_rate"],
                "p361_duplicate_hit_events": subset_row["duplicate_hit_events"],
                "p361_mean_pairwise_jaccard": subset_row["mean_pairwise_jaccard"],
                "p362_windows_evaluated": rank_row["windows_evaluated"],
                "p362_average_rank_by_coverage_rate": rank_row["average_rank_by_coverage_rate"],
                "p362_rank_variance_by_coverage_rate": rank_row["rank_variance_by_coverage_rate"],
                "p362_top_1_window_count": rank_row["top_1_window_count"],
                "p362_top_3_window_count": rank_row["top_3_window_count"],
                "p362_within_3_hits_window_count": rank_row[
                    "within_3_hits_of_full_cohort_window_count"
                ],
                "compact_candidate_row_types": ";".join(row["row_type"] for row in compact_rows),
                "compact_candidate_windows": ";".join(row["window_size"] for row in compact_rows),
                "p362_stability_note": (
                    f"Ranked across {rank_row['windows_evaluated']} windows; "
                    f"within 3 hits of full cohort in "
                    f"{rank_row['within_3_hits_of_full_cohort_window_count']} window(s)."
                ),
                "caveat": "Subset card summarizes historical coverage only; no new scoring or recommendation.",
            }
        )
    return tuple(rows)


def build_summary_rows(
    adapter_rows: tuple[dict[str, str], ...],
    subset_rows: tuple[dict[str, str], ...],
    consistency_rows: tuple[dict[str, str], ...],
    source_manifest_rows: tuple[dict[str, str], ...],
    p361_manifest: Mapping[str, str],
    p362_manifest: Mapping[str, str],
) -> tuple[dict[str, str], ...]:
    pass_count = sum(1 for row in consistency_rows if row["status"] == "PASS")
    fail_count = sum(1 for row in consistency_rows if row["status"] == "FAIL")
    full_subset = next(row for row in subset_rows if row["subset_is_full_cohort"] == "true")
    compact_focus = p362_manifest.get("focus_compact_subset", "")
    rows = (
        {"section": "scope", "key": "task", "value": TASK},
        {"section": "scope", "key": "source_tasks", "value": "P360;P361;P362"},
        {"section": "scope", "key": "historical_descriptive_evidence_only", "value": "YES"},
        {"section": "scope", "key": "db_opened", "value": "NO"},
        {"section": "scope", "key": "db_written", "value": "NO"},
        {"section": "scope", "key": "production_registry_imported", "value": "NO"},
        {"section": "scope", "key": "deploy", "value": "NO"},
        {"section": "scope", "key": "new_strategy_scoring", "value": "NO"},
        {"section": "scope", "key": "blended_leaderboard", "value": "NO"},
        {"section": "scope", "key": "betting_advice", "value": "NO"},
        {"section": "scope", "key": "future_prediction_claim", "value": "NO"},
        {"section": "dimensions", "key": "adapter_card_rows", "value": str(len(adapter_rows))},
        {"section": "dimensions", "key": "subset_card_rows", "value": str(len(subset_rows))},
        {"section": "dimensions", "key": "source_artifact_rows", "value": str(len(source_manifest_rows))},
        {"section": "dimensions", "key": "p361_scoreable_period_count", "value": p361_manifest["scoreable_period_count"]},
        {"section": "dimensions", "key": "p361_subset_count", "value": p361_manifest["subset_metric_rows"]},
        {"section": "dimensions", "key": "p361_hit_matrix_period_count", "value": p361_manifest["hit_matrix_rows"]},
        {"section": "dimensions", "key": "p362_windows", "value": p362_manifest["windows"]},
        {"section": "evidence", "key": "full_cohort_any_hit_count", "value": full_subset["p361_any_hit_count"]},
        {"section": "evidence", "key": "full_cohort_coverage_rate", "value": full_subset["p361_coverage_rate"]},
        {"section": "evidence", "key": "focus_compact_subset", "value": compact_focus},
        {
            "section": "evidence",
            "key": "focus_compact_subset_within_3_hits_all_windows",
            "value": p362_manifest.get("focus_compact_subset_within_3_hits_all_windows", ""),
        },
        {"section": "checks", "key": "pass_count", "value": str(pass_count)},
        {"section": "checks", "key": "fail_count", "value": str(fail_count)},
    )
    return rows


def run_evidence_pack(repo_root: Path | None = None) -> EvidencePackOutput:
    root = Path(repo_root) if repo_root is not None else REPO_ROOT
    verify_required_artifacts(root)
    p360_results = read_csv_rows(root / "artifacts/P360_biglotto_no_db_multiwindow_validation_results.csv")
    p360_coverage = read_csv_rows(root / "artifacts/P360_biglotto_no_db_multiwindow_validation_coverage.csv")
    p360_manifest = read_key_value_manifest(root / "artifacts/P360_biglotto_no_db_multiwindow_validation_manifest.csv")
    p361_subset_metrics = read_csv_rows(root / "artifacts/P361_biglotto_coverage_utility_subset_metrics.csv")
    p361_marginal = read_csv_rows(root / "artifacts/P361_biglotto_coverage_utility_marginal_contribution.csv")
    p361_hit_matrix = read_csv_rows(root / "artifacts/P361_biglotto_coverage_utility_hit_matrix.csv")
    p361_manifest = read_key_value_manifest(root / "artifacts/P361_biglotto_coverage_utility_manifest.csv")
    p362_window_metrics = read_csv_rows(root / "artifacts/P362_biglotto_subset_stability_window_metrics.csv")
    p362_rank_summary = read_csv_rows(root / "artifacts/P362_biglotto_subset_stability_rank_summary.csv")
    p362_compact_candidates = read_csv_rows(root / "artifacts/P362_biglotto_subset_stability_compact_candidates.csv")
    p362_manifest = read_key_value_manifest(root / "artifacts/P362_biglotto_subset_stability_manifest.csv")
    source_manifest_rows = build_source_manifest_rows(root)
    consistency_rows = build_consistency_check_rows(
        p360_results,
        p360_coverage,
        p360_manifest,
        p361_subset_metrics,
        p361_marginal,
        p361_hit_matrix,
        p361_manifest,
        p362_window_metrics,
        p362_rank_summary,
        p362_compact_candidates,
        p362_manifest,
        source_manifest_rows,
    )
    adapter_rows = build_adapter_card_rows(
        p360_results,
        p360_coverage,
        p361_marginal,
        p362_rank_summary,
    )
    subset_rows = build_subset_card_rows(
        p361_subset_metrics,
        p362_rank_summary,
        p362_compact_candidates,
    )
    summary_rows = build_summary_rows(
        adapter_rows,
        subset_rows,
        consistency_rows,
        source_manifest_rows,
        p361_manifest,
        p362_manifest,
    )
    return EvidencePackOutput(
        summary_rows=summary_rows,
        source_manifest_rows=source_manifest_rows,
        adapter_card_rows=adapter_rows,
        subset_card_rows=subset_rows,
        consistency_check_rows=consistency_rows,
    )


def _markdown_table(columns: Iterable[str], rows: Iterable[Mapping[str, str]]) -> str:
    columns = list(columns)
    lines = ["| " + " | ".join(columns) + " |", "|" + "|".join(" --- " for _ in columns) + "|"]
    for row in rows:
        values = [str(row[column]).replace("|", "\\|") for column in columns]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def render_report(output: EvidencePackOutput) -> str:
    summary = {(row["section"], row["key"]): row["value"] for row in output.summary_rows}
    compact_rows = [
        row for row in output.subset_card_rows if row["compact_candidate_row_types"]
    ][:10]
    parts = [
        "# P363 Big Lotto no-DB Consolidated Evidence Pack",
        "",
        "## Scope statements",
        "",
        "- This is historical descriptive evidence only.",
        "- No future prediction guarantee. Past hit rates, coverage, and stability do not predict future draws.",
        "- No betting advice. Nothing here recommends placing any bet.",
        "- No DB was opened or written. P363 reads only committed P360/P361/P362 artifacts.",
        "- No production registry import, no deploy, no migration/backfill, and no strategy status change.",
        "- No blended leaderboard: P363 creates cards and checks, not a cross-task ranking.",
        "- Shape-only and blocked targets remain excluded; P363 keeps the same five parity adapters from P360/P361/P362.",
        "",
        "## Consolidated dimensions",
        "",
        f"- Adapter cards: {summary[('dimensions', 'adapter_card_rows')]}",
        f"- Subset cards: {summary[('dimensions', 'subset_card_rows')]}",
        f"- Source artifacts fingerprinted: {summary[('dimensions', 'source_artifact_rows')]}",
        f"- P361 scoreable periods: {summary[('dimensions', 'p361_scoreable_period_count')]}",
        f"- P362 windows: {summary[('dimensions', 'p362_windows')]}",
        "",
        "## Consistency checks",
        "",
        _markdown_table(CONSISTENCY_CHECK_COLUMNS, output.consistency_check_rows),
        "",
        "## Adapter cards",
        "",
        _markdown_table(
            (
                "adapter_function",
                "bet_count",
                "p360_windows_present",
                "p361_total_hit_count",
                "p361_unique_hit_count",
                "p362_singleton_average_rank_by_coverage_rate",
                "p362_singleton_top_3_window_count",
            ),
            output.adapter_card_rows,
        ),
        "",
        "## Compact candidate subset summary",
        "",
    ]
    if compact_rows:
        parts.append(
            _markdown_table(
                (
                    "adapter_subset",
                    "subset_size",
                    "p361_any_hit_count",
                    "p362_top_3_window_count",
                    "compact_candidate_row_types",
                    "compact_candidate_windows",
                ),
                compact_rows,
            )
        )
    else:
        parts.append("No compact candidate labels were present in P362.")
    parts.extend(
        [
            "",
            "## Source artifact manifest",
            "",
            _markdown_table(
                (
                    "artifact_role",
                    "path",
                    "data_row_count",
                    "line_count",
                    "sha256",
                    "row_count_matches_manifest",
                ),
                output.source_manifest_rows,
            ),
            "",
            "## Exclusions",
            "",
            "- Shape-only scoring remains excluded.",
            "- Blocked target scoring remains excluded.",
            "- P363 does not call adapters, re-score strategies, or create a new scoring cohort.",
            "- P363 does not publish betting advice or future-performance claims.",
            "",
        ]
    )
    return "\n".join(parts)


def _write_csv(path: Path, columns: Iterable[str], rows: Iterable[Mapping[str, str]]) -> None:
    columns = list(columns)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_artifacts(output: EvidencePackOutput, artifacts_dir: Path | None = None) -> dict[str, Path]:
    directory = Path(artifacts_dir) if artifacts_dir is not None else REPO_ROOT / "artifacts"
    directory.mkdir(parents=True, exist_ok=True)
    paths = {key: directory / name for key, name in ARTIFACT_BASENAMES.items()}
    _write_csv(paths["summary"], SUMMARY_COLUMNS, output.summary_rows)
    _write_csv(paths["adapter_cards"], ADAPTER_CARD_COLUMNS, output.adapter_card_rows)
    _write_csv(paths["subset_cards"], SUBSET_CARD_COLUMNS, output.subset_card_rows)
    _write_csv(paths["consistency_checks"], CONSISTENCY_CHECK_COLUMNS, output.consistency_check_rows)
    _write_csv(paths["manifest"], SOURCE_MANIFEST_COLUMNS, output.source_manifest_rows)
    with open(paths["report"], "w", encoding="utf-8") as handle:
        handle.write(render_report(output))
    return paths


def _assert_deterministic(first: EvidencePackOutput, second: EvidencePackOutput) -> None:
    if (
        first.summary_rows != second.summary_rows
        or first.source_manifest_rows != second.source_manifest_rows
        or first.adapter_card_rows != second.adapter_card_rows
        or first.subset_card_rows != second.subset_card_rows
        or first.consistency_check_rows != second.consistency_check_rows
        or render_report(first) != render_report(second)
    ):
        raise RuntimeError("determinism double-run mismatch: P363 evidence pack is not reproducible")


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts-dir", type=Path, default=None, help="override artifacts directory")
    args = parser.parse_args(argv)
    first = run_evidence_pack()
    second = run_evidence_pack()
    _assert_deterministic(first, second)
    failed = [row for row in first.consistency_check_rows if row["status"] != "PASS"]
    if failed:
        raise EvidencePackError(f"P363 consistency checks failed: {failed}")
    paths = write_artifacts(first, args.artifacts_dir)
    print("P363 no-DB evidence pack: determinism double-run PASS")
    print(f"adapter cards: {len(first.adapter_card_rows)}")
    print(f"subset cards: {len(first.subset_card_rows)}")
    print(f"consistency checks: {len(first.consistency_check_rows)} PASS")
    for key, path in sorted(paths.items()):
        print(f"artifact[{key}]: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
