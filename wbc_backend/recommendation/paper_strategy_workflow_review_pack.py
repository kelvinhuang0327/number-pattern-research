"""Deterministic review pack for P239/P240 paper workflow artifacts.

This module reads existing local artifacts only. It does not regenerate
decisions, run inspectors, call providers, compute edge, or price outcomes.
"""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_WORKFLOW_DIR = ROOT / "report" / "p239a_paper_strategy_workflow"
DEFAULT_INSPECTION_DIR = ROOT / "report" / "p240a_paper_strategy_workflow_inspector"
DEFAULT_OUTPUT_DIR = ROOT / "report" / "p241a_paper_strategy_workflow_review_pack"
DEFAULT_GENERATED_AT_UTC = "2026-07-08T00:00:00Z"

WORKFLOW_SUMMARY_FILENAME = "workflow_summary.json"
WORKFLOW_MANIFEST_FILENAME = "workflow_manifest.json"
DECISIONS_FILENAME = "decisions.csv"
LEARNING_SUMMARY_FILENAME = "learning_summary.json"
LEARNING_SEGMENTS_FILENAME = "learning_segments.csv"
INSPECTION_SUMMARY_FILENAME = "inspection_summary.json"
INSPECTION_CHECKS_FILENAME = "inspection_checks.csv"

REVIEW_SUMMARY_FILENAME = "review_summary.json"
REVIEW_ARTIFACTS_FILENAME = "review_artifacts.csv"
REVIEW_REPORT_FILENAME = "review_report.md"

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
    "pnl",
    "profit",
    "bankroll",
    "best_strategy",
    "best_threshold",
    "recommended_bet",
    "recommendation",
    "strategy_recommendation",
)

REQUIRED_INSPECTION_STATUS_FIELDS = (
    "manifest_hash_check_status",
    "forbidden_field_check_status",
    "limitation_label_check_status",
    "count_check_status",
)

ARTIFACT_FIELDNAMES = [
    "artifact_type",
    "artifact_path",
    "sha256",
    "source",
    "status",
    "notes",
]

SOURCE_SPECS = (
    ("p239_workflow_summary", WORKFLOW_SUMMARY_FILENAME, "workflow"),
    ("p239_workflow_manifest", WORKFLOW_MANIFEST_FILENAME, "workflow"),
    ("p239_decisions", DECISIONS_FILENAME, "workflow"),
    ("p239_learning_summary", LEARNING_SUMMARY_FILENAME, "workflow"),
    ("p239_learning_segments", LEARNING_SEGMENTS_FILENAME, "workflow"),
    ("p240_inspection_summary", INSPECTION_SUMMARY_FILENAME, "inspection"),
    ("p240_inspection_checks", INSPECTION_CHECKS_FILENAME, "inspection"),
)


class ReviewPackError(RuntimeError):
    """Raised when review-pack inputs are missing, empty, or unreadable."""


@dataclass(frozen=True)
class ReviewPackResult:
    summary: dict[str, Any]
    artifacts: tuple[dict[str, str], ...]
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


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ReviewPackError(f"CORRUPT_INPUT: invalid JSON in {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ReviewPackError(f"CORRUPT_INPUT: JSON root must be an object: {path}")
    return payload


def _load_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fieldnames = list(reader.fieldnames or ())
            rows = list(reader)
    except csv.Error as exc:
        raise ReviewPackError(f"CORRUPT_INPUT: invalid CSV in {path}: {exc}") from exc
    if not fieldnames:
        raise ReviewPackError(f"EMPTY_INPUT: CSV has no header: {path}")
    return fieldnames, rows


def _source_paths(workflow_dir: Path, inspection_dir: Path) -> dict[str, Path]:
    return {
        artifact_type: (workflow_dir if source == "workflow" else inspection_dir) / filename
        for artifact_type, filename, source in SOURCE_SPECS
    }


def _require_inputs(workflow_dir: Path, inspection_dir: Path) -> dict[str, Path]:
    if not workflow_dir.is_dir():
        raise ReviewPackError(f"MISSING_INPUT: workflow dir not found: {workflow_dir}")
    if not inspection_dir.is_dir():
        raise ReviewPackError(f"MISSING_INPUT: inspection dir not found: {inspection_dir}")
    paths = _source_paths(workflow_dir, inspection_dir)
    missing = [str(path) for path in paths.values() if not path.is_file()]
    if missing:
        raise ReviewPackError(f"MISSING_INPUT: required review-pack files not found: {missing}")
    empty = [str(path) for path in paths.values() if path.stat().st_size == 0]
    if empty:
        raise ReviewPackError(f"EMPTY_INPUT: required review-pack files are empty: {empty}")
    return paths


def _json_key_hits(value: Any, forbidden: set[str], prefix: str = "$") -> list[str]:
    hits: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_prefix = f"{prefix}.{key}"
            if str(key).casefold() in forbidden:
                hits.append(child_prefix)
            hits.extend(_json_key_hits(child, forbidden, child_prefix))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            hits.extend(_json_key_hits(child, forbidden, f"{prefix}[{index}]"))
    return hits


def _csv_field_hits(fieldnames: Iterable[str], forbidden: set[str]) -> list[str]:
    return [field for field in fieldnames if field.casefold() in forbidden]


def _labels(payload: dict[str, Any]) -> set[str]:
    raw = payload.get("limitation_labels")
    if not isinstance(raw, list):
        return set()
    return {str(item) for item in raw}


def _append_failure(
    failures: list[dict[str, str]],
    *,
    check_id: str,
    message: str,
    file_path: Path | None = None,
    observed: Any = None,
) -> None:
    failures.append(
        {
            "check_id": check_id,
            "message": message,
            "file_path": _display_path(file_path) if file_path is not None else "",
            "observed": _format_cell(observed),
        }
    )


def _format_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return str(value)


def _artifact_source(artifact_type: str) -> str:
    for spec_artifact_type, _filename, source in SOURCE_SPECS:
        if spec_artifact_type == artifact_type:
            return "P239 workflow" if source == "workflow" else "P240 inspection"
    return ""


def _build_artifact_rows(
    *,
    paths: dict[str, Path],
    hashes: dict[str, str],
    forbidden_hits: dict[str, list[str]],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for artifact_type, _filename, _source in SOURCE_SPECS:
        hits = forbidden_hits.get(artifact_type, [])
        rows.append(
            {
                "artifact_type": artifact_type,
                "artifact_path": _display_path(paths[artifact_type]),
                "sha256": hashes[artifact_type],
                "source": _artifact_source(artifact_type),
                "status": "FAIL" if hits else "PASS",
                "notes": "forbidden fields: " + "; ".join(hits) if hits else "sha256 recorded",
            }
        )
    return rows


def _write_artifact_csv(path: Path, rows: Iterable[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=ARTIFACT_FIELDNAMES, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _audit_forbidden_fields(
    *,
    json_payloads: dict[str, dict[str, Any]],
    csv_payloads: dict[str, tuple[list[str], list[dict[str, str]]]],
) -> dict[str, list[str]]:
    forbidden = {field.casefold() for field in FORBIDDEN_FIELDS}
    hits: dict[str, list[str]] = {}
    for artifact_type, payload in json_payloads.items():
        artifact_hits = _json_key_hits(payload, forbidden)
        if artifact_hits:
            hits[artifact_type] = artifact_hits
    for artifact_type, (fieldnames, _rows) in csv_payloads.items():
        artifact_hits = _csv_field_hits(fieldnames, forbidden)
        if artifact_hits:
            hits[artifact_type] = artifact_hits
    return hits


def _report_markdown(summary: dict[str, Any], artifacts: Iterable[dict[str, str]]) -> str:
    artifact_rows = list(artifacts)
    lines = [
        "# P241-A Paper Strategy Workflow Review Pack",
        "",
        "## Summary",
        f"- Generated at UTC: {summary['generated_at_utc']}",
        f"- Review status: {summary['review_status']}",
        f"- Workflow status: {summary['workflow_status']}",
        f"- Inspection overall status: {summary['inspection_overall_status']}",
        f"- Decisions count: {summary['decisions_count']}",
        f"- Learning segments count: {summary['learning_segments_count']}",
        "",
        "## Source Artifacts",
        "| Artifact | Source | SHA-256 | Status |",
        "|---|---|---|---|",
    ]
    for row in artifact_rows:
        lines.append(
            f"| {row['artifact_path']} | {row['source']} | {row['sha256']} | {row['status']} |"
        )
    lines.extend(
        [
            "",
            "## Verification Status",
            f"- Manifest hash check: {summary['manifest_hash_check_status']}",
            f"- Forbidden field check: {summary['forbidden_field_check_status']}",
            f"- Limitation label check: {summary['limitation_label_check_status']}",
            f"- ROI status: {summary['roi_status']}",
            f"- Generates new predictions: {str(summary['generates_new_predictions']).lower()}",
            "",
            "## Safety Boundaries",
            "- Existing P239/P240 artifacts are read only.",
            "- No DB writes, provider calls, sports API calls, live transport, or live output.",
            "- No prediction regeneration, paper P/L, pricing, stake sizing, bankroll, or compounding computation.",
            "",
            "## Limitations",
        ]
    )
    for label in summary["limitation_labels"]:
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
            "",
        ]
    )
    return "\n".join(lines)


def build_paper_strategy_workflow_review_pack(
    *,
    workflow_dir: Path = DEFAULT_WORKFLOW_DIR,
    inspection_dir: Path = DEFAULT_INSPECTION_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    generated_at_utc: str = DEFAULT_GENERATED_AT_UTC,
) -> ReviewPackResult:
    workflow_dir = Path(workflow_dir)
    inspection_dir = Path(inspection_dir)
    output_dir = Path(output_dir)
    paths = _require_inputs(workflow_dir, inspection_dir)

    json_payloads = {
        "p239_workflow_summary": _load_json(paths["p239_workflow_summary"]),
        "p239_workflow_manifest": _load_json(paths["p239_workflow_manifest"]),
        "p239_learning_summary": _load_json(paths["p239_learning_summary"]),
        "p240_inspection_summary": _load_json(paths["p240_inspection_summary"]),
    }
    csv_payloads = {
        "p239_decisions": _load_csv(paths["p239_decisions"]),
        "p239_learning_segments": _load_csv(paths["p239_learning_segments"]),
        "p240_inspection_checks": _load_csv(paths["p240_inspection_checks"]),
    }
    hashes = {artifact_type: _sha256(path) for artifact_type, path in paths.items()}
    forbidden_hits = _audit_forbidden_fields(json_payloads=json_payloads, csv_payloads=csv_payloads)

    workflow_summary = json_payloads["p239_workflow_summary"]
    learning_summary = json_payloads["p239_learning_summary"]
    inspection_summary = json_payloads["p240_inspection_summary"]
    inspection_check_rows = csv_payloads["p240_inspection_checks"][1]
    decisions_count = len(csv_payloads["p239_decisions"][1])
    learning_segments_count = len(csv_payloads["p239_learning_segments"][1])

    failures: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    if workflow_summary.get("decisions_count") != decisions_count:
        _append_failure(
            failures,
            check_id="counts.decisions",
            message="workflow_summary decisions_count does not match decisions.csv row count",
            file_path=paths["p239_workflow_summary"],
            observed={"summary": workflow_summary.get("decisions_count"), "csv": decisions_count},
        )
    if workflow_summary.get("learning_segments_count") != learning_segments_count:
        _append_failure(
            failures,
            check_id="counts.learning_segments.workflow_summary",
            message="workflow_summary learning_segments_count does not match learning_segments.csv",
            file_path=paths["p239_workflow_summary"],
            observed={
                "summary": workflow_summary.get("learning_segments_count"),
                "csv": learning_segments_count,
            },
        )
    if learning_summary.get("segments_count") != learning_segments_count:
        _append_failure(
            failures,
            check_id="counts.learning_segments.learning_summary",
            message="learning_summary segments_count does not match learning_segments.csv",
            file_path=paths["p239_learning_summary"],
            observed={"summary": learning_summary.get("segments_count"), "csv": learning_segments_count},
        )

    inspection_overall_status = str(inspection_summary.get("overall_status", ""))
    if inspection_overall_status != "PASS":
        _append_failure(
            failures,
            check_id="inspection.overall_status",
            message="P240 inspection overall_status is not PASS",
            file_path=paths["p240_inspection_summary"],
            observed=inspection_overall_status,
        )
    for field in REQUIRED_INSPECTION_STATUS_FIELDS:
        if inspection_summary.get(field) != "PASS":
            _append_failure(
                failures,
                check_id=f"inspection.{field}",
                message=f"P240 inspection {field} is not PASS",
                file_path=paths["p240_inspection_summary"],
                observed=inspection_summary.get(field),
            )
    failed_inspection_rows = [row for row in inspection_check_rows if row.get("status") == "FAIL"]
    if failed_inspection_rows:
        _append_failure(
            failures,
            check_id="inspection.check_rows",
            message="P240 inspection_checks.csv contains failed checks",
            file_path=paths["p240_inspection_checks"],
            observed=[row.get("check_id", "") for row in failed_inspection_rows],
        )

    manifest_hash_status = "PASS" if inspection_summary.get("manifest_hash_check_status") == "PASS" else "FAIL"
    label_sets = {
        "p239_workflow_summary": _labels(workflow_summary),
        "p239_workflow_manifest": _labels(json_payloads["p239_workflow_manifest"]),
        "p239_learning_summary": _labels(learning_summary),
    }
    limitation_labels = list(REQUIRED_LIMITATION_LABELS)
    missing_by_artifact = {
        artifact_type: [label for label in REQUIRED_LIMITATION_LABELS if label not in labels]
        for artifact_type, labels in label_sets.items()
    }
    missing_labels = {
        artifact_type: missing for artifact_type, missing in missing_by_artifact.items() if missing
    }
    limitation_label_status = (
        "PASS"
        if not missing_labels and inspection_summary.get("limitation_label_check_status") == "PASS"
        else "FAIL"
    )
    if missing_labels:
        _append_failure(
            failures,
            check_id="contract.limitation_labels",
            message="required limitation labels are missing",
            file_path=paths["p239_workflow_summary"],
            observed={"missing": missing_labels},
        )

    forbidden_field_status = (
        "PASS"
        if not forbidden_hits and inspection_summary.get("forbidden_field_check_status") == "PASS"
        else "FAIL"
    )
    for artifact_type, hits in forbidden_hits.items():
        _append_failure(
            failures,
            check_id=f"forbidden_fields.{artifact_type}",
            message="source artifact contains forbidden field keys or columns",
            file_path=paths[artifact_type],
            observed=hits,
        )

    roi_values = {
        "workflow_summary": workflow_summary.get("roi_status"),
        "learning_summary": learning_summary.get("roi_status"),
        "inspection_summary": inspection_summary.get("roi_status"),
    }
    roi_status = "ROI_UNAVAILABLE" if set(roi_values.values()) == {"ROI_UNAVAILABLE"} else "FAIL"
    if roi_status != "ROI_UNAVAILABLE":
        _append_failure(
            failures,
            check_id="contract.roi_status",
            message="ROI status must remain ROI_UNAVAILABLE",
            file_path=paths["p239_workflow_summary"],
            observed=roi_values,
        )

    generates_values = {
        "workflow_summary": workflow_summary.get("generates_new_predictions"),
        "learning_summary": learning_summary.get("generates_new_predictions"),
        "inspection_summary": inspection_summary.get("generates_new_predictions"),
    }
    source_generates_new_predictions_ok = all(value is False for value in generates_values.values())
    if not source_generates_new_predictions_ok:
        _append_failure(
            failures,
            check_id="contract.generates_new_predictions",
            message="generates_new_predictions must be false in source summaries",
            file_path=paths["p239_workflow_summary"],
            observed=generates_values,
        )

    workflow_status = str(workflow_summary.get("workflow_status", ""))
    if workflow_status != "RESULT_ONLY_PAPER_WORKFLOW":
        _append_failure(
            failures,
            check_id="contract.workflow_status",
            message="workflow_status must remain RESULT_ONLY_PAPER_WORKFLOW",
            file_path=paths["p239_workflow_summary"],
            observed=workflow_status,
        )

    artifacts = _build_artifact_rows(paths=paths, hashes=hashes, forbidden_hits=forbidden_hits)
    review_status = "FAIL" if failures else "PASS"
    source_files = [
        {
            "artifact_type": artifact_type,
            "path": _display_path(paths[artifact_type]),
            "sha256": hashes[artifact_type],
        }
        for artifact_type, _filename, _source in SOURCE_SPECS
    ]
    summary = {
        "generated_at_utc": generated_at_utc,
        "workflow_dir": _display_path(workflow_dir),
        "inspection_dir": _display_path(inspection_dir),
        "source_files": source_files,
        "decisions_count": decisions_count,
        "learning_segments_count": learning_segments_count,
        "inspection_overall_status": inspection_overall_status,
        "manifest_hash_check_status": manifest_hash_status,
        "forbidden_field_check_status": forbidden_field_status,
        "limitation_label_check_status": limitation_label_status,
        "roi_status": roi_status,
        "generates_new_predictions": False,
        "workflow_status": workflow_status,
        "review_status": review_status,
        "failures": failures,
        "warnings": warnings,
        "limitation_labels": list(REQUIRED_LIMITATION_LABELS),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / REVIEW_SUMMARY_FILENAME
    artifacts_path = output_dir / REVIEW_ARTIFACTS_FILENAME
    report_path = output_dir / REVIEW_REPORT_FILENAME
    _json_write(summary_path, summary)
    _write_artifact_csv(artifacts_path, artifacts)
    report_path.write_text(_report_markdown(summary, artifacts), encoding="utf-8")

    return ReviewPackResult(
        summary=summary,
        artifacts=tuple(artifacts),
        output_paths={
            "review_summary_json": _display_path(summary_path),
            "review_artifacts_csv": _display_path(artifacts_path),
            "review_report_md": _display_path(report_path),
        },
    )
