"""Deterministic result-only query/export for the P243 paper artifact catalog.

This module reads existing P243 catalog artifacts and writes filtered query
outputs. It does not regenerate source artifacts, contact providers, write data,
or compute betting performance.
"""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable

from wbc_backend.recommendation.paper_artifact_catalog import (
    CSV_FIELDNAMES,
    REQUIRED_LIMITATION_LABELS,
)
from wbc_backend.recommendation.paper_strategy_learning import resolve_generated_at_utc


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_CATALOG_JSON = ROOT / "report" / "p243a_paper_artifact_catalog" / "artifact_catalog.json"
DEFAULT_CATALOG_CSV = ROOT / "report" / "p243a_paper_artifact_catalog" / "artifact_catalog.csv"
DEFAULT_OUTPUT_DIR = ROOT / "report" / "p244a_paper_artifact_catalog_query"
DEFAULT_GENERATED_AT_UTC = None

QUERY_SUMMARY_FILENAME = "query_summary.json"
QUERY_RESULTS_FILENAME = "query_results.csv"
QUERY_REPORT_FILENAME = "query_report.md"


class PaperArtifactCatalogQueryError(RuntimeError):
    """Raised when catalog query/export cannot complete."""


@dataclass(frozen=True)
class PaperArtifactCatalogQueryFilters:
    artifact_groups: tuple[str, ...] = ()
    file_types: tuple[str, ...] = ()
    detected_roles: tuple[str, ...] = ()
    statuses: tuple[str, ...] = ()
    include_warnings: bool = False
    only_warnings: bool = False
    only_failures: bool = False


@dataclass(frozen=True)
class PaperArtifactCatalogQueryResult:
    summary: dict[str, Any]
    rows: tuple[dict[str, str], ...]
    output_paths: dict[str, str]


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return str(path)


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _format_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return str(value)


def _dedupe_sorted(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({str(value) for value in values if str(value)}))


def _load_catalog_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise PaperArtifactCatalogQueryError(f"MISSING_INPUT: catalog JSON not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PaperArtifactCatalogQueryError(
            f"CORRUPT_INPUT: invalid catalog JSON in {path}: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise PaperArtifactCatalogQueryError(f"CORRUPT_INPUT: catalog JSON must be an object: {path}")
    required = {"source_files", "limitation_labels", "failures", "warnings"}
    missing = sorted(required - set(payload))
    if missing:
        raise PaperArtifactCatalogQueryError(
            f"CORRUPT_INPUT: catalog JSON missing required keys {missing}: {path}"
        )
    if not isinstance(payload["source_files"], list):
        raise PaperArtifactCatalogQueryError(
            f"CORRUPT_INPUT: catalog JSON source_files must be a list: {path}"
        )
    return payload


def _load_catalog_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise PaperArtifactCatalogQueryError(f"MISSING_INPUT: catalog CSV not found: {path}")
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fieldnames = list(reader.fieldnames or ())
            missing = [field for field in CSV_FIELDNAMES if field not in fieldnames]
            if missing:
                raise PaperArtifactCatalogQueryError(
                    f"CORRUPT_INPUT: catalog CSV missing required columns {missing}: {path}"
                )
            return [
                {field: _format_cell(row.get(field, "")) for field in CSV_FIELDNAMES}
                for row in reader
            ]
    except csv.Error as exc:
        raise PaperArtifactCatalogQueryError(
            f"CORRUPT_INPUT: invalid catalog CSV in {path}: {exc}"
        ) from exc


def _filters_payload(filters: PaperArtifactCatalogQueryFilters) -> dict[str, Any]:
    return {
        "artifact_group": list(filters.artifact_groups),
        "file_type": list(filters.file_types),
        "detected_role": list(filters.detected_roles),
        "status": list(filters.statuses),
        "include_warnings": filters.include_warnings,
        "only_warnings": filters.only_warnings,
        "only_failures": filters.only_failures,
    }


def _file_paths(items: Iterable[Any]) -> set[str]:
    paths: set[str] = set()
    for item in items:
        if isinstance(item, dict):
            path = str(item.get("file_path", ""))
            if path:
                paths.add(path)
    return paths


def _row_matches_values(row: dict[str, str], field: str, allowed: tuple[str, ...]) -> bool:
    return not allowed or row.get(field, "") in allowed


def _row_has_warning(row: dict[str, str], warning_paths: set[str]) -> bool:
    return row.get("status") == "WARN" or row.get("relative_path") in warning_paths


def _row_has_failure(row: dict[str, str], failure_paths: set[str]) -> bool:
    return row.get("status") == "FAIL" or row.get("relative_path") in failure_paths


def _filter_rows(
    rows: Iterable[dict[str, str]],
    *,
    filters: PaperArtifactCatalogQueryFilters,
    warning_paths: set[str],
    failure_paths: set[str],
) -> list[dict[str, str]]:
    matched: list[dict[str, str]] = []
    for row in rows:
        if not _row_matches_values(row, "artifact_group", filters.artifact_groups):
            continue
        if not _row_matches_values(row, "file_type", filters.file_types):
            continue
        if not _row_matches_values(row, "detected_role", filters.detected_roles):
            continue
        if filters.only_warnings and not _row_has_warning(row, warning_paths):
            continue
        if filters.only_failures and not _row_has_failure(row, failure_paths):
            continue
        if filters.statuses and row.get("status", "") not in filters.statuses:
            if not (filters.include_warnings and _row_has_warning(row, warning_paths)):
                continue
        matched.append(row)
    return sorted(
        matched,
        key=lambda row: (
            row.get("artifact_group", ""),
            row.get("relative_path", ""),
            row.get("file_type", ""),
        ),
    )


def _status_counts(rows: Iterable[dict[str, str]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        status = row.get("status", "")
        counts[status] = counts.get(status, 0) + 1
    return {key: counts[key] for key in sorted(counts)}


def _stable_items(items: Any) -> list[Any]:
    if not isinstance(items, list):
        return []
    return sorted(
        items,
        key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")),
    )


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: Iterable[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDNAMES, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _format_cell(row.get(field, "")) for field in CSV_FIELDNAMES})


def _write_markdown(path: Path, summary: dict[str, Any]) -> None:
    filters = summary["filters"]
    groups = summary["matched_groups"]
    warnings = summary["warnings"]
    failures = summary["failures"]
    lines = [
        "# P244-A Paper Artifact Catalog Query",
        "",
        "## Summary",
        f"- Generated at UTC: {summary['generated_at_utc']}",
        f"- Query status: {summary['query_status']}",
        f"- Total catalog entries: {summary['total_catalog_entries']}",
        f"- Matched entries: {summary['matched_entries']}",
        f"- Warning count: {summary['warning_count']}",
        f"- Failure count: {summary['failure_count']}",
        f"- Catalog JSON SHA-256: {summary['catalog_json_sha256']}",
        f"- Catalog CSV SHA-256: {summary['catalog_csv_sha256']}",
        "",
        "## Filters",
    ]
    for key in (
        "artifact_group",
        "file_type",
        "detected_role",
        "status",
        "include_warnings",
        "only_warnings",
        "only_failures",
    ):
        value = filters[key]
        if isinstance(value, list):
            rendered = ", ".join(value) if value else "none"
        elif isinstance(value, bool):
            rendered = str(value).lower()
        else:
            rendered = _format_cell(value) or "none"
        lines.append(f"- {key}: {rendered}")
    lines.extend(["", "## Matched Artifact Groups"])
    if groups:
        for group in groups:
            lines.append(f"- {group}")
    else:
        lines.append("- None.")
    lines.extend(
        [
            "",
            "## Warnings / Failures",
            f"- Warnings: {len(warnings)}",
            f"- Failures: {len(failures)}",
        ]
    )
    if warnings:
        for item in warnings:
            lines.append(
                "- Warning: {file_path} - {message}".format(
                    file_path=item.get("file_path", ""),
                    message=item.get("message", ""),
                )
            )
    if failures:
        for item in failures:
            lines.append(
                "- Failure: {file_path} - {message}".format(
                    file_path=item.get("file_path", ""),
                    message=item.get("message", ""),
                )
            )
    lines.extend(["", "## Safety Boundaries"])
    for label in REQUIRED_LIMITATION_LABELS:
        lines.append(f"- {label}")
    lines.extend(
        [
            "",
            "## Not Claims",
            "- Not betting edge.",
            "- Not future prediction.",
            "- Not true-PIT validation.",
            "- Not multi-season validation.",
            "- Not live, production, or real betting output.",
            "- No ROI, paper P/L, EV, Kelly, bankroll, or strategy recommendation is computed.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def query_paper_artifact_catalog(
    *,
    catalog_json: Path = DEFAULT_CATALOG_JSON,
    catalog_csv: Path = DEFAULT_CATALOG_CSV,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    filters: PaperArtifactCatalogQueryFilters | None = None,
    generated_at_utc: str | None = DEFAULT_GENERATED_AT_UTC,
) -> PaperArtifactCatalogQueryResult:
    catalog_json = Path(catalog_json)
    catalog_csv = Path(catalog_csv)
    output_dir = Path(output_dir)
    filters = filters or PaperArtifactCatalogQueryFilters()
    generated_at_utc = resolve_generated_at_utc(generated_at_utc)

    catalog_payload = _load_catalog_json(catalog_json)
    rows = _load_catalog_csv(catalog_csv)
    warnings = _stable_items(catalog_payload.get("warnings", []))
    failures = _stable_items(catalog_payload.get("failures", []))
    warning_paths = _file_paths(warnings)
    failure_paths = _file_paths(failures)
    matched_rows = _filter_rows(
        rows,
        filters=filters,
        warning_paths=warning_paths,
        failure_paths=failure_paths,
    )
    limitation_labels = list(catalog_payload.get("limitation_labels", []))
    for label in REQUIRED_LIMITATION_LABELS:
        if label not in limitation_labels:
            limitation_labels.append(label)

    query_status = "FAIL" if failures else "PASS"
    summary = {
        "generated_at_utc": generated_at_utc,
        "catalog_json": _display_path(catalog_json),
        "catalog_csv": _display_path(catalog_csv),
        "catalog_json_sha256": _sha256(catalog_json),
        "catalog_csv_sha256": _sha256(catalog_csv),
        "filters": _filters_payload(filters),
        "query_status": query_status,
        "total_catalog_entries": len(rows),
        "matched_entries": len(matched_rows),
        "matched_groups": sorted({row["artifact_group"] for row in matched_rows}),
        "matched_status_counts": _status_counts(matched_rows),
        "warning_count": len(warnings),
        "failure_count": len(failures),
        "limitation_labels": limitation_labels,
        "failures": failures,
        "warnings": warnings,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / QUERY_SUMMARY_FILENAME
    results_path = output_dir / QUERY_RESULTS_FILENAME
    report_path = output_dir / QUERY_REPORT_FILENAME

    _write_json(summary_path, summary)
    _write_csv(results_path, matched_rows)
    _write_markdown(report_path, summary)

    return PaperArtifactCatalogQueryResult(
        summary=summary,
        rows=tuple(matched_rows),
        output_paths={
            "query_summary_json": _display_path(summary_path),
            "query_results_csv": _display_path(results_path),
            "query_report_md": _display_path(report_path),
        },
    )
