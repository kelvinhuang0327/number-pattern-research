"""Deterministic result-only diff for P243 paper artifact catalogs.

This module reads existing P243 catalog snapshots and writes local diff
artifacts. It does not regenerate source artifacts, contact providers, write
data, or compute betting performance.
"""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable

from wbc_backend.recommendation.paper_artifact_catalog import (
    CSV_FIELDNAMES as CATALOG_CSV_FIELDNAMES,
    REQUIRED_LIMITATION_LABELS,
)
from wbc_backend.recommendation.paper_strategy_learning import resolve_generated_at_utc


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_BASELINE_CATALOG_JSON = (
    ROOT / "report" / "p243a_paper_artifact_catalog" / "artifact_catalog.json"
)
DEFAULT_BASELINE_CATALOG_CSV = (
    ROOT / "report" / "p243a_paper_artifact_catalog" / "artifact_catalog.csv"
)
DEFAULT_CURRENT_CATALOG_JSON = DEFAULT_BASELINE_CATALOG_JSON
DEFAULT_CURRENT_CATALOG_CSV = DEFAULT_BASELINE_CATALOG_CSV
DEFAULT_OUTPUT_DIR = ROOT / "report" / "p245a_paper_artifact_catalog_diff"
DEFAULT_GENERATED_AT_UTC = None

DIFF_SUMMARY_FILENAME = "diff_summary.json"
DIFF_ENTRIES_FILENAME = "diff_entries.csv"
DIFF_REPORT_FILENAME = "diff_report.md"

DIFF_CSV_FIELDNAMES = [
    "change_type",
    "artifact_group",
    "relative_path",
    "baseline_sha256",
    "current_sha256",
    "baseline_status",
    "current_status",
    "baseline_detected_role",
    "current_detected_role",
    "baseline_file_type",
    "current_file_type",
    "field_changes",
    "notes",
]

COMPARE_FIELDS = (
    ("sha256", "hash-changed"),
    ("status", "status-changed"),
    ("detected_role", "role-changed"),
    ("file_type", "type-changed"),
    ("notes", "notes-changed"),
)


class PaperArtifactCatalogDiffError(RuntimeError):
    """Raised when catalog diff/export cannot complete."""


@dataclass(frozen=True)
class PaperArtifactCatalogDiffResult:
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


def _stable_items(items: Any) -> list[Any]:
    if not isinstance(items, list):
        return []
    return sorted(items, key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")))


def _load_catalog_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise PaperArtifactCatalogDiffError(f"MISSING_INPUT: catalog JSON not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PaperArtifactCatalogDiffError(
            f"CORRUPT_INPUT: invalid catalog JSON in {path}: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise PaperArtifactCatalogDiffError(
            f"CORRUPT_INPUT: catalog JSON must be an object: {path}"
        )
    missing = sorted({"source_files", "limitation_labels", "failures", "warnings"} - set(payload))
    if missing:
        raise PaperArtifactCatalogDiffError(
            f"CORRUPT_INPUT: catalog JSON missing required keys {missing}: {path}"
        )
    if not isinstance(payload["source_files"], list):
        raise PaperArtifactCatalogDiffError(
            f"CORRUPT_INPUT: catalog JSON source_files must be a list: {path}"
        )
    return payload


def _load_catalog_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise PaperArtifactCatalogDiffError(f"MISSING_INPUT: catalog CSV not found: {path}")
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fieldnames = list(reader.fieldnames or ())
            missing = [field for field in CATALOG_CSV_FIELDNAMES if field not in fieldnames]
            if missing:
                raise PaperArtifactCatalogDiffError(
                    f"CORRUPT_INPUT: catalog CSV missing required columns {missing}: {path}"
                )
            rows = [
                {field: _format_cell(row.get(field, "")) for field in CATALOG_CSV_FIELDNAMES}
                for row in reader
            ]
    except csv.Error as exc:
        raise PaperArtifactCatalogDiffError(
            f"CORRUPT_INPUT: invalid catalog CSV in {path}: {exc}"
        ) from exc
    return rows


def _rows_by_relative_path(
    rows: Iterable[dict[str, str]],
    *,
    label: str,
) -> dict[str, dict[str, str]]:
    by_path: dict[str, dict[str, str]] = {}
    duplicates: list[str] = []
    for row in rows:
        relative_path = row.get("relative_path", "")
        if not relative_path:
            raise PaperArtifactCatalogDiffError(
                f"CORRUPT_INPUT: {label} catalog CSV row missing relative_path"
            )
        if relative_path in by_path:
            duplicates.append(relative_path)
        by_path[relative_path] = row
    if duplicates:
        raise PaperArtifactCatalogDiffError(
            f"CORRUPT_INPUT: {label} catalog CSV duplicate relative_path values "
            f"{sorted(set(duplicates))}"
        )
    return by_path


def _field_changes(baseline: dict[str, str], current: dict[str, str]) -> list[str]:
    changes = [
        change
        for field, change in COMPARE_FIELDS
        if baseline.get(field, "") != current.get(field, "")
    ]
    if baseline.get("artifact_group", "") != current.get("artifact_group", ""):
        changes.append("artifact-group-changed")
    return changes


def _notes_for_change(
    *,
    baseline: dict[str, str] | None,
    current: dict[str, str] | None,
    changes: list[str],
) -> str:
    if baseline is None:
        return "artifact added in current catalog"
    if current is None:
        return "artifact removed from current catalog"
    if not changes:
        return "unchanged"
    return "changed fields: " + ", ".join(changes)


def _diff_row(
    relative_path: str,
    baseline: dict[str, str] | None,
    current: dict[str, str] | None,
) -> dict[str, str]:
    if baseline is None and current is None:
        raise PaperArtifactCatalogDiffError(
            "INTERNAL_ERROR: diff row has no baseline or current row"
        )
    if baseline is None:
        changes = ["added"]
        change_type = "added"
    elif current is None:
        changes = ["removed"]
        change_type = "removed"
    else:
        changes = _field_changes(baseline, current)
        change_type = ";".join(changes) if changes else "unchanged"

    source = current or baseline or {}
    baseline_row = baseline or {}
    current_row = current or {}
    return {
        "change_type": change_type,
        "artifact_group": source.get("artifact_group", ""),
        "relative_path": relative_path,
        "baseline_sha256": baseline_row.get("sha256", ""),
        "current_sha256": current_row.get("sha256", ""),
        "baseline_status": baseline_row.get("status", ""),
        "current_status": current_row.get("status", ""),
        "baseline_detected_role": baseline_row.get("detected_role", ""),
        "current_detected_role": current_row.get("detected_role", ""),
        "baseline_file_type": baseline_row.get("file_type", ""),
        "current_file_type": current_row.get("file_type", ""),
        "field_changes": ",".join(changes),
        "notes": _notes_for_change(baseline=baseline, current=current, changes=changes),
    }


def _build_diff_rows(
    baseline_rows: Iterable[dict[str, str]],
    current_rows: Iterable[dict[str, str]],
) -> tuple[list[dict[str, str]], dict[str, int]]:
    baseline_by_path = _rows_by_relative_path(baseline_rows, label="baseline")
    current_by_path = _rows_by_relative_path(current_rows, label="current")
    all_paths = sorted(set(baseline_by_path) | set(current_by_path))
    rows = [
        _diff_row(path, baseline_by_path.get(path), current_by_path.get(path))
        for path in all_paths
    ]
    counts = {
        "baseline_entry_count": len(baseline_by_path),
        "current_entry_count": len(current_by_path),
        "added_count": sum(1 for row in rows if row["change_type"] == "added"),
        "removed_count": sum(1 for row in rows if row["change_type"] == "removed"),
        "unchanged_count": sum(1 for row in rows if row["change_type"] == "unchanged"),
        "changed_count": sum(
            1 for row in rows if row["change_type"] not in {"added", "removed", "unchanged"}
        ),
        "hash_changed_count": sum(
            1 for row in rows if "hash-changed" in row["field_changes"].split(",")
        ),
        "status_changed_count": sum(
            1 for row in rows if "status-changed" in row["field_changes"].split(",")
        ),
        "role_changed_count": sum(
            1 for row in rows if "role-changed" in row["field_changes"].split(",")
        ),
        "file_type_changed_count": sum(
            1 for row in rows if "type-changed" in row["field_changes"].split(",")
        ),
        "notes_changed_count": sum(
            1 for row in rows if "notes-changed" in row["field_changes"].split(",")
        ),
    }
    return rows, counts


def _limitation_labels(*catalog_payloads: dict[str, Any]) -> list[str]:
    labels: list[str] = []
    for payload in catalog_payloads:
        for label in payload.get("limitation_labels", []):
            text = str(label)
            if text and text not in labels:
                labels.append(text)
    for label in REQUIRED_LIMITATION_LABELS:
        if label not in labels:
            labels.append(label)
    return labels


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: Iterable[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=DIFF_CSV_FIELDNAMES, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {field: _format_cell(row.get(field, "")) for field in DIFF_CSV_FIELDNAMES}
            )


def _write_markdown(path: Path, summary: dict[str, Any], rows: Iterable[dict[str, str]]) -> None:
    changed_rows = [row for row in rows if row["change_type"] != "unchanged"]
    warnings = summary["warnings"]
    failures = summary["failures"]
    lines = [
        "# P245-A Paper Artifact Catalog Diff",
        "",
        "## Summary",
        f"- Generated at UTC: {summary['generated_at_utc']}",
        f"- Diff status: {summary['diff_status']}",
        f"- Baseline entries: {summary['baseline_entry_count']}",
        f"- Current entries: {summary['current_entry_count']}",
        f"- Changed artifacts: {summary['changed_count']}",
        f"- Added artifacts: {summary['added_count']}",
        f"- Removed artifacts: {summary['removed_count']}",
        "",
        "## Inputs",
        f"- Baseline catalog JSON: {summary['baseline_catalog_json']}",
        f"- Baseline catalog CSV: {summary['baseline_catalog_csv']}",
        f"- Current catalog JSON: {summary['current_catalog_json']}",
        f"- Current catalog CSV: {summary['current_catalog_csv']}",
    ]
    for key, value in summary["input_hashes"].items():
        lines.append(f"- {key}: {value}")

    lines.extend(
        [
            "",
            "## Diff Counts",
            f"- added_count: {summary['added_count']}",
            f"- removed_count: {summary['removed_count']}",
            f"- unchanged_count: {summary['unchanged_count']}",
            f"- changed_count: {summary['changed_count']}",
            f"- hash_changed_count: {summary['hash_changed_count']}",
            f"- status_changed_count: {summary['status_changed_count']}",
            f"- role_changed_count: {summary['role_changed_count']}",
            f"- file_type_changed_count: {summary['file_type_changed_count']}",
            f"- notes_changed_count: {summary['notes_changed_count']}",
            f"- warning_count: {summary['warning_count']}",
            f"- failure_count: {summary['failure_count']}",
            "",
            "## Changed Artifacts",
        ]
    )
    if changed_rows:
        for row in changed_rows:
            lines.append(
                "- {change_type}: {relative_path} ({field_changes})".format(
                    change_type=row["change_type"],
                    relative_path=row["relative_path"],
                    field_changes=row["field_changes"] or "none",
                )
            )
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
    for item in warnings:
        lines.append(f"- Warning: {item.get('message', '')}")
    for item in failures:
        lines.append(f"- Failure: {item.get('message', '')}")

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


def diff_paper_artifact_catalogs(
    *,
    baseline_catalog_json: Path = DEFAULT_BASELINE_CATALOG_JSON,
    baseline_catalog_csv: Path = DEFAULT_BASELINE_CATALOG_CSV,
    current_catalog_json: Path = DEFAULT_CURRENT_CATALOG_JSON,
    current_catalog_csv: Path = DEFAULT_CURRENT_CATALOG_CSV,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    fail_on_changes: bool = False,
    include_unchanged: bool = False,
    generated_at_utc: str | None = DEFAULT_GENERATED_AT_UTC,
) -> PaperArtifactCatalogDiffResult:
    baseline_catalog_json = Path(baseline_catalog_json)
    baseline_catalog_csv = Path(baseline_catalog_csv)
    current_catalog_json = Path(current_catalog_json)
    current_catalog_csv = Path(current_catalog_csv)
    output_dir = Path(output_dir)
    generated_at_utc = resolve_generated_at_utc(generated_at_utc)

    baseline_payload = _load_catalog_json(baseline_catalog_json)
    current_payload = _load_catalog_json(current_catalog_json)
    baseline_rows = _load_catalog_csv(baseline_catalog_csv)
    current_rows = _load_catalog_csv(current_catalog_csv)
    all_rows, counts = _build_diff_rows(baseline_rows, current_rows)
    output_rows = list(
        all_rows
        if include_unchanged
        else [row for row in all_rows if row["change_type"] != "unchanged"]
    )

    has_changes = (
        counts["added_count"] > 0 or counts["removed_count"] > 0 or counts["changed_count"] > 0
    )
    warnings: list[dict[str, str]] = []
    failures: list[dict[str, str]] = []
    if has_changes and fail_on_changes:
        failures.append(
            {
                "check_id": "diff.changes_absent",
                "message": "catalog changes detected and --fail-on-changes was set",
                "observed": str(
                    counts["added_count"] + counts["removed_count"] + counts["changed_count"]
                ),
            }
        )
    elif has_changes:
        warnings.append(
            {
                "check_id": "diff.changes_absent",
                "message": "catalog changes detected",
                "observed": str(
                    counts["added_count"] + counts["removed_count"] + counts["changed_count"]
                ),
            }
        )
    diff_status = "FAIL" if failures else "WARN" if warnings else "PASS"

    summary = {
        "generated_at_utc": generated_at_utc,
        "baseline_catalog_json": _display_path(baseline_catalog_json),
        "baseline_catalog_csv": _display_path(baseline_catalog_csv),
        "current_catalog_json": _display_path(current_catalog_json),
        "current_catalog_csv": _display_path(current_catalog_csv),
        "input_hashes": {
            "baseline_catalog_json_sha256": _sha256(baseline_catalog_json),
            "baseline_catalog_csv_sha256": _sha256(baseline_catalog_csv),
            "current_catalog_json_sha256": _sha256(current_catalog_json),
            "current_catalog_csv_sha256": _sha256(current_catalog_csv),
        },
        "diff_status": diff_status,
        **counts,
        "warning_count": len(warnings),
        "failure_count": len(failures),
        "limitation_labels": _limitation_labels(baseline_payload, current_payload),
        "failures": _stable_items(failures),
        "warnings": _stable_items(warnings),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / DIFF_SUMMARY_FILENAME
    entries_path = output_dir / DIFF_ENTRIES_FILENAME
    report_path = output_dir / DIFF_REPORT_FILENAME
    _write_json(summary_path, summary)
    _write_csv(entries_path, output_rows)
    _write_markdown(report_path, summary, output_rows)

    return PaperArtifactCatalogDiffResult(
        summary=summary,
        rows=tuple(output_rows),
        output_paths={
            "diff_summary_json": _display_path(summary_path),
            "diff_entries_csv": _display_path(entries_path),
            "diff_report_md": _display_path(report_path),
        },
    )
