"""Deterministic local catalog for P237-P242 paper-only artifacts.

The catalog reads existing report artifacts, records file metadata, and writes
catalog files. It does not regenerate workflows, contact providers, write data,
or compute betting performance.
"""
from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable

from wbc_backend.recommendation.paper_strategy_learning import resolve_generated_at_utc


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_OUTPUT_DIR = ROOT / "report" / "p243a_paper_artifact_catalog"
DEFAULT_GENERATED_AT_UTC = None

CATALOG_JSON_FILENAME = "artifact_catalog.json"
CATALOG_CSV_FILENAME = "artifact_catalog.csv"
CATALOG_MD_FILENAME = "artifact_catalog.md"

SOURCE_ROOT_SPECS = (
    ("p237_simulator_summary", ROOT / "report" / "p237a_paper_strategy_simulator_summary.json"),
    ("p237_decisions", ROOT / "report" / "p237a_paper_strategy_decisions.csv"),
    ("p238_learning_summary", ROOT / "report" / "p238a_paper_strategy_learning_summary.json"),
    ("p238_learning_segments", ROOT / "report" / "p238a_paper_strategy_learning_segments.csv"),
    ("p239_workflow", ROOT / "report" / "p239a_paper_strategy_workflow"),
    ("p240_inspector", ROOT / "report" / "p240a_paper_strategy_workflow_inspector"),
    ("p241_review_pack", ROOT / "report" / "p241a_paper_strategy_workflow_review_pack"),
    ("p242_bundle", ROOT / "report" / "p242a_paper_strategy_workflow_bundle"),
)
DEFAULT_SOURCE_ROOTS = tuple(path for _group, path in SOURCE_ROOT_SPECS)

OPTIONAL_MARKDOWN_REPORTS = (
    ROOT / "report" / "p241a_paper_strategy_workflow_review_pack" / "review_report.md",
    ROOT / "report" / "p242a_paper_strategy_workflow_bundle" / "review" / "review_report.md",
)

REQUIRED_LIMITATION_LABELS = (
    "2025-only",
    "historical paper-only",
    "odds provenance unverified",
    "not true-PIT",
    "not betting edge",
    "not future prediction",
    "not live",
    "not production",
    "not real betting",
    "not multi-season validation",
)

FORBIDDEN_FIELDS = (
    "pnl_units",
    "ev",
    "kelly",
    "bankroll",
    "best_strategy",
    "best_threshold",
    "recommended_bet",
)

CSV_FIELDNAMES = [
    "artifact_group",
    "relative_path",
    "file_type",
    "size_bytes",
    "sha256",
    "detected_role",
    "status",
    "notes",
]


class PaperArtifactCatalogError(RuntimeError):
    """Raised when catalog generation cannot complete."""


@dataclass(frozen=True)
class PaperArtifactCatalogResult:
    catalog: dict[str, Any]
    csv_rows: tuple[dict[str, str], ...]
    output_paths: dict[str, str]


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return str(path)


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _json_write(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _format_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return str(value)


def _artifact_group_for_path(path: Path, source_specs: tuple[tuple[str, Path], ...]) -> str:
    resolved = path.resolve()
    best_match: tuple[int, str] | None = None
    for group, root in source_specs:
        root_resolved = root.resolve()
        if resolved == root_resolved or root_resolved in resolved.parents:
            depth = len(root_resolved.parts)
            if best_match is None or depth > best_match[0]:
                best_match = (depth, group)
    return best_match[1] if best_match else "unknown"


def _source_specs(source_roots: Iterable[Path]) -> tuple[tuple[str, Path], ...]:
    default_by_path = {path.resolve(): group for group, path in SOURCE_ROOT_SPECS}
    specs: list[tuple[str, Path]] = []
    for index, root in enumerate(source_roots):
        path = Path(root)
        group = default_by_path.get(path.resolve(), path.name or f"source_{index + 1}")
        specs.append((group, path))
    return tuple(specs)


def _source_root_rows(source_specs: tuple[tuple[str, Path], ...]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for group, path in source_specs:
        rows.append(
            {
                "artifact_group": group,
                "path": _display_path(path),
                "exists": path.exists(),
                "root_type": (
                    "directory" if path.is_dir() else "file" if path.is_file() else "missing"
                ),
            }
        )
    return rows


def _collect_source_files(
    source_specs: tuple[tuple[str, Path], ...],
) -> tuple[list[Path], list[dict[str, str]]]:
    files: list[Path] = []
    failures: list[dict[str, str]] = []
    for group, root in source_specs:
        if not root.exists():
            failures.append(
                {
                    "check_id": f"source_root.{group}.present",
                    "message": "required source artifact root is missing",
                    "file_path": _display_path(root),
                    "observed": "missing",
                }
            )
            continue
        if root.is_file():
            files.append(root)
            continue
        if root.is_dir():
            files.extend(path for path in root.rglob("*") if path.is_file())
            continue
        failures.append(
            {
                "check_id": f"source_root.{group}.type",
                "message": "required source artifact root is neither file nor directory",
                "file_path": _display_path(root),
                "observed": "unsupported",
            }
        )
    return sorted(files, key=lambda path: _display_path(path)), failures


def _file_type(path: Path) -> str:
    return path.suffix.lower().lstrip(".") or "none"


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PaperArtifactCatalogError(f"CORRUPT_INPUT: invalid JSON in {path}: {exc}") from exc


def _csv_header_and_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            return list(reader.fieldnames or ()), list(reader)
    except csv.Error as exc:
        raise PaperArtifactCatalogError(f"CORRUPT_INPUT: invalid CSV in {path}: {exc}") from exc


def _json_forbidden_hits(
    value: Any, forbidden: set[str], prefix: str = "$"
) -> tuple[list[str], list[str]]:
    failures: list[str] = []
    warnings: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_prefix = f"{prefix}.{key}"
            key_text = str(key).casefold()
            if key_text in forbidden:
                if child in (None, "", [], {}):
                    warnings.append(child_prefix)
                else:
                    failures.append(child_prefix)
            child_failures, child_warnings = _json_forbidden_hits(child, forbidden, child_prefix)
            failures.extend(child_failures)
            warnings.extend(child_warnings)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            child_failures, child_warnings = _json_forbidden_hits(
                child, forbidden, f"{prefix}[{index}]"
            )
            failures.extend(child_failures)
            warnings.extend(child_warnings)
    return failures, warnings


def _csv_forbidden_hits(
    fieldnames: Iterable[str],
    rows: Iterable[dict[str, str]],
    forbidden: set[str],
) -> tuple[list[str], list[str]]:
    forbidden_columns = [field for field in fieldnames if field.casefold() in forbidden]
    failures: list[str] = []
    warnings: list[str] = []
    materialized_rows = list(rows)
    for field in forbidden_columns:
        has_value = any(str(row.get(field, "")).strip() for row in materialized_rows)
        if has_value:
            failures.append(field)
        else:
            warnings.append(field)
    return failures, warnings


_MD_KEY_RE = re.compile(r"^\s*(?:[-*]\s*)?`?([A-Za-z_][A-Za-z0-9_]*)`?\s*:")


def _markdown_forbidden_hits(text: str, forbidden: set[str]) -> tuple[list[str], list[str]]:
    failures: list[str] = []
    warnings: list[str] = []
    ignored_section = False
    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("#"):
            heading = stripped.lstrip("#").strip().casefold()
            ignored_section = heading in {
                "not claims",
                "limitations",
                "safety boundaries",
                "safety scan",
                "forbidden-field explanations",
            }
            continue
        if ignored_section:
            continue
        if stripped.startswith("|") and stripped.endswith("|"):
            cells = [cell.strip(" `").casefold() for cell in stripped.strip("|").split("|")]
            for cell in cells:
                if cell in forbidden:
                    failures.append(f"line {line_number}: {cell}")
        match = _MD_KEY_RE.match(line)
        if match and match.group(1).casefold() in forbidden:
            failures.append(f"line {line_number}: {match.group(1)}")
    return failures, warnings


def _scan_forbidden_fields(
    files: Iterable[Path],
) -> tuple[dict[str, dict[str, list[str]]], list[dict[str, str]], list[dict[str, str]]]:
    forbidden = {field.casefold() for field in FORBIDDEN_FIELDS}
    per_file: dict[str, dict[str, list[str]]] = {}
    failures: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    for path in files:
        suffix = path.suffix.casefold()
        if suffix == ".json":
            file_failures, file_warnings = _json_forbidden_hits(_load_json(path), forbidden)
        elif suffix == ".csv":
            fieldnames, rows = _csv_header_and_rows(path)
            file_failures, file_warnings = _csv_forbidden_hits(fieldnames, rows, forbidden)
        elif suffix == ".md":
            file_failures, file_warnings = _markdown_forbidden_hits(
                path.read_text(encoding="utf-8"), forbidden
            )
        else:
            file_failures, file_warnings = [], []
        relative_path = _display_path(path)
        if file_failures or file_warnings:
            per_file[relative_path] = {
                "failures": sorted(file_failures),
                "warnings": sorted(file_warnings),
            }
        if file_failures:
            failures.append(
                {
                    "check_id": f"forbidden_fields.{relative_path}",
                    "message": "source artifact contains forbidden populated field data",
                    "file_path": relative_path,
                    "observed": json.dumps(sorted(file_failures), separators=(",", ":")),
                }
            )
        if file_warnings:
            warnings.append(
                {
                    "check_id": f"forbidden_fields.{relative_path}.empty",
                    "message": "source artifact has forbidden field names with empty values",
                    "file_path": relative_path,
                    "observed": json.dumps(sorted(file_warnings), separators=(",", ":")),
                }
            )
    return per_file, failures, warnings


def _json_status_values(value: Any, prefix: str = "$") -> list[dict[str, str]]:
    statuses: list[dict[str, str]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_prefix = f"{prefix}.{key}"
            key_text = str(key)
            if "status" in key_text.casefold() and not isinstance(child, (dict, list)):
                statuses.append({"status_field": child_prefix, "status_value": str(child)})
            statuses.extend(_json_status_values(child, child_prefix))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            statuses.extend(_json_status_values(child, f"{prefix}[{index}]"))
    return statuses


def _detect_statuses(files: Iterable[Path]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in files:
        relative_path = _display_path(path)
        if path.suffix.casefold() == ".json":
            for item in _json_status_values(_load_json(path)):
                rows.append({"relative_path": relative_path, **item})
        elif path.suffix.casefold() == ".csv":
            fieldnames, csv_rows = _csv_header_and_rows(path)
            for field in fieldnames:
                if "status" not in field.casefold():
                    continue
                values = sorted({row.get(field, "") for row in csv_rows if row.get(field, "")})
                rows.append(
                    {
                        "relative_path": relative_path,
                        "status_field": field,
                        "status_value": ";".join(values[:10]),
                    }
                )
    return sorted(rows, key=lambda row: (row["relative_path"], row["status_field"]))


def _detect_role(path: Path, status_paths: set[str]) -> str:
    name = path.name.casefold()
    relative_path = _display_path(path)
    if "manifest" in name:
        return "manifest"
    if relative_path in status_paths or "status" in name or "summary" in name:
        return "status"
    if path.suffix.casefold() == ".md":
        return "markdown_report"
    return "source_artifact"


def _optional_markdown_warnings() -> list[dict[str, str]]:
    warnings: list[dict[str, str]] = []
    for path in OPTIONAL_MARKDOWN_REPORTS:
        if not path.exists():
            warnings.append(
                {
                    "check_id": f"optional_markdown.{_display_path(path)}",
                    "message": "optional markdown report is missing",
                    "file_path": _display_path(path),
                    "observed": "missing",
                }
            )
    return warnings


def _build_source_file_rows(
    *,
    files: Iterable[Path],
    source_specs: tuple[tuple[str, Path], ...],
    forbidden_hits: dict[str, dict[str, list[str]]],
    status_paths: set[str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in files:
        relative_path = _display_path(path)
        hits = forbidden_hits.get(relative_path, {"failures": [], "warnings": []})
        status = "FAIL" if hits["failures"] else "WARN" if hits["warnings"] else "PASS"
        notes = "sha256 recorded"
        if hits["failures"]:
            notes = "forbidden populated fields: " + "; ".join(hits["failures"])
        elif hits["warnings"]:
            notes = "empty forbidden fields: " + "; ".join(hits["warnings"])
        rows.append(
            {
                "artifact_group": _artifact_group_for_path(path, source_specs),
                "relative_path": relative_path,
                "file_type": _file_type(path),
                "size_bytes": path.stat().st_size,
                "sha256": _sha256(path),
                "detected_role": _detect_role(path, status_paths),
                "status": status,
                "notes": notes,
            }
        )
    return rows


def _write_csv(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDNAMES, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _format_cell(row.get(field, "")) for field in CSV_FIELDNAMES})


def _group_summaries(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        group = row["artifact_group"]
        item = grouped.setdefault(
            group,
            {
                "artifact_group": group,
                "file_count": 0,
                "total_bytes": 0,
                "status": "PASS",
            },
        )
        item["file_count"] += 1
        item["total_bytes"] += int(row["size_bytes"])
        if row["status"] == "FAIL":
            item["status"] = "FAIL"
        elif row["status"] == "WARN" and item["status"] == "PASS":
            item["status"] = "WARN"
    return [grouped[key] for key in sorted(grouped)]


def _write_markdown(
    path: Path,
    *,
    catalog: dict[str, Any],
    group_summaries: list[dict[str, Any]],
) -> None:
    manifests = catalog["detected_manifests"]
    failures = catalog["failures"]
    warnings = catalog["warnings"]
    lines = [
        "# P243-A Paper Artifact Catalog",
        "",
        "## Summary",
        f"- Generated at UTC: {catalog['generated_at_utc']}",
        f"- Catalog status: {catalog['catalog_status']}",
        f"- Source file count: {catalog['source_file_count']}",
        f"- Source total bytes: {catalog['source_total_bytes']}",
        f"- Forbidden field scan: {catalog['forbidden_field_scan_status']}",
        f"- Mutation guard: {catalog['mutation_guard_status']}",
        "",
        "## Artifact Groups",
        "| Artifact Group | Files | Total Bytes | Status |",
        "|---|---:|---:|---|",
    ]
    for group in group_summaries:
        lines.append(
            "| {artifact_group} | {file_count} | {total_bytes} | {status} |".format(**group)
        )
    lines.extend(
        [
            "",
            "## Detected Manifests",
        ]
    )
    if manifests:
        for item in manifests:
            lines.append(f"- {item['relative_path']} ({item['sha256']})")
    else:
        lines.append("- None detected.")
    lines.extend(
        [
            "",
            "## Safety Scan",
            f"- Forbidden field scan status: {catalog['forbidden_field_scan_status']}",
            f"- Mutation guard status: {catalog['mutation_guard_status']}",
            f"- Failures: {len(failures)}",
            f"- Warnings: {len(warnings)}",
            "",
            "## Limitations",
        ]
    )
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
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_paper_artifact_catalog(
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    generated_at_utc: str | None = DEFAULT_GENERATED_AT_UTC,
    source_roots: Iterable[Path] = DEFAULT_SOURCE_ROOTS,
) -> PaperArtifactCatalogResult:
    output_dir = Path(output_dir)
    generated_at_utc = resolve_generated_at_utc(generated_at_utc)
    source_specs = _source_specs(tuple(Path(path) for path in source_roots))
    output_dir.mkdir(parents=True, exist_ok=True)
    catalog_json_path = output_dir / CATALOG_JSON_FILENAME
    catalog_csv_path = output_dir / CATALOG_CSV_FILENAME
    catalog_md_path = output_dir / CATALOG_MD_FILENAME

    files, root_failures = _collect_source_files(source_specs)
    before_hashes = {_display_path(path): _sha256(path) for path in files}

    forbidden_hits, forbidden_failures, forbidden_warnings = _scan_forbidden_fields(files)
    detected_statuses = _detect_statuses(files)
    status_paths = {item["relative_path"] for item in detected_statuses}
    source_file_rows = _build_source_file_rows(
        files=files,
        source_specs=source_specs,
        forbidden_hits=forbidden_hits,
        status_paths=status_paths,
    )
    group_summaries = _group_summaries(source_file_rows)
    optional_warnings = _optional_markdown_warnings()
    warnings = forbidden_warnings + optional_warnings
    failures = root_failures + forbidden_failures

    detected_manifests = [
        {
            "relative_path": row["relative_path"],
            "artifact_group": row["artifact_group"],
            "sha256": row["sha256"],
            "size_bytes": row["size_bytes"],
        }
        for row in source_file_rows
        if row["detected_role"] == "manifest"
    ]

    after_hashes = {_display_path(path): _sha256(path) for path in files}
    mutation_guard_status = "PASS" if before_hashes == after_hashes else "FAIL"
    if mutation_guard_status == "FAIL":
        failures.append(
            {
                "check_id": "mutation_guard.source_hashes",
                "message": "source artifact hashes changed during catalog generation",
                "file_path": "",
                "observed": "source hash mismatch",
            }
        )

    forbidden_field_scan_status = "FAIL" if forbidden_failures else "PASS"
    catalog_status = "FAIL" if failures else "PASS"
    source_total_bytes = sum(int(row["size_bytes"]) for row in source_file_rows)
    catalog = {
        "generated_at_utc": generated_at_utc,
        "catalog_status": catalog_status,
        "source_roots": _source_root_rows(source_specs),
        "source_file_count": len(source_file_rows),
        "source_total_bytes": source_total_bytes,
        "source_files": source_file_rows,
        "detected_manifests": sorted(
            detected_manifests, key=lambda item: item["relative_path"]
        ),
        "detected_statuses": detected_statuses,
        "forbidden_field_scan_status": forbidden_field_scan_status,
        "mutation_guard_status": mutation_guard_status,
        "limitation_labels": list(REQUIRED_LIMITATION_LABELS),
        "failures": failures,
        "warnings": warnings,
    }

    _json_write(catalog_json_path, catalog)
    _write_csv(catalog_csv_path, source_file_rows)
    _write_markdown(catalog_md_path, catalog=catalog, group_summaries=group_summaries)

    return PaperArtifactCatalogResult(
        catalog=catalog,
        csv_rows=tuple(
            {field: _format_cell(row.get(field, "")) for field in CSV_FIELDNAMES}
            for row in source_file_rows
        ),
        output_paths={
            "artifact_catalog_json": _display_path(catalog_json_path),
            "artifact_catalog_csv": _display_path(catalog_csv_path),
            "artifact_catalog_md": _display_path(catalog_md_path),
        },
    )
