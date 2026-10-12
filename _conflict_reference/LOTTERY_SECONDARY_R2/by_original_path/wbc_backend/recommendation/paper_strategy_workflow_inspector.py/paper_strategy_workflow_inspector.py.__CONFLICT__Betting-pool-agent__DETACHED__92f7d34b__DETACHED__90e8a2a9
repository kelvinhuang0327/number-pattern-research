"""Read-only inspector for P239-A result-only paper workflow artifacts.

The inspector audits existing workflow outputs only. It does not regenerate
decisions, call providers, price rows, compute returns, or rank strategies.
"""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable

from wbc_backend.recommendation.paper_strategy_learning import resolve_generated_at_utc


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_WORKFLOW_DIR = ROOT / "report" / "p239a_paper_strategy_workflow"
DEFAULT_OUTPUT_DIR = ROOT / "report" / "p240a_paper_strategy_workflow_inspector"
DEFAULT_GENERATED_AT_UTC = None

WORKFLOW_SUMMARY_FILENAME = "workflow_summary.json"
WORKFLOW_MANIFEST_FILENAME = "workflow_manifest.json"
DECISIONS_FILENAME = "decisions.csv"
LEARNING_SUMMARY_FILENAME = "learning_summary.json"
LEARNING_SEGMENTS_FILENAME = "learning_segments.csv"

REQUIRED_FILES = (
    WORKFLOW_SUMMARY_FILENAME,
    WORKFLOW_MANIFEST_FILENAME,
    DECISIONS_FILENAME,
    LEARNING_SUMMARY_FILENAME,
    LEARNING_SEGMENTS_FILENAME,
)

MANIFEST_OUTPUTS = (
    ("decisions_csv", DECISIONS_FILENAME),
    ("learning_summary_json", LEARNING_SUMMARY_FILENAME),
    ("learning_segments_csv", LEARNING_SEGMENTS_FILENAME),
    ("workflow_summary_json", WORKFLOW_SUMMARY_FILENAME),
    ("workflow_manifest_json", WORKFLOW_MANIFEST_FILENAME),
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
)

EXPECTED_LIMITATION_LABELS = (
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

SIDE_EFFECT_FIELDS = (
    "db_writes",
    "provider_calls",
    "sports_api_calls",
    "live_transport",
    "live_output",
)

CHECK_FIELDNAMES = [
    "check_id",
    "check_category",
    "check_name",
    "status",
    "file_path",
    "expected",
    "observed",
    "notes",
]

INSPECTION_SUMMARY_FILENAME = "inspection_summary.json"
INSPECTION_CHECKS_FILENAME = "inspection_checks.csv"


class PaperWorkflowInspectorError(RuntimeError):
    """Raised when inspector inputs are missing, empty, or unreadable."""


@dataclass(frozen=True)
class PaperWorkflowInspectionResult:
    summary: dict[str, Any]
    checks: tuple[dict[str, str], ...]
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
        raise PaperWorkflowInspectorError(f"CORRUPT_INPUT: invalid JSON in {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise PaperWorkflowInspectorError(f"CORRUPT_INPUT: JSON root must be an object: {path}")
    return payload


def _load_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fieldnames = list(reader.fieldnames or ())
            rows = list(reader)
    except csv.Error as exc:
        raise PaperWorkflowInspectorError(f"CORRUPT_INPUT: invalid CSV in {path}: {exc}") from exc
    if not fieldnames:
        raise PaperWorkflowInspectorError(f"EMPTY_INPUT: CSV has no header: {path}")
    return fieldnames, rows


def _require_inputs(workflow_dir: Path) -> dict[str, Path]:
    if not workflow_dir.is_dir():
        raise PaperWorkflowInspectorError(f"MISSING_INPUT: workflow dir not found: {workflow_dir}")
    paths = {filename: workflow_dir / filename for filename in REQUIRED_FILES}
    missing = [str(path) for path in paths.values() if not path.is_file()]
    if missing:
        raise PaperWorkflowInspectorError(f"MISSING_INPUT: required workflow files not found: {missing}")
    empty = [str(path) for path in paths.values() if path.stat().st_size == 0]
    if empty:
        raise PaperWorkflowInspectorError(f"EMPTY_INPUT: required workflow files are empty: {empty}")
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


def _add_check(
    checks: list[dict[str, str]],
    *,
    check_id: str,
    check_category: str,
    check_name: str,
    status: str,
    file_path: Path | str,
    expected: Any,
    observed: Any,
    notes: str = "",
) -> None:
    checks.append(
        {
            "check_id": check_id,
            "check_category": check_category,
            "check_name": check_name,
            "status": status,
            "file_path": _display_path(Path(file_path)) if isinstance(file_path, Path) else file_path,
            "expected": _format_cell(expected),
            "observed": _format_cell(observed),
            "notes": notes,
        }
    )


def _format_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return str(value)


def _manifest_output_map(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    outputs = manifest.get("outputs")
    if not isinstance(outputs, list):
        return {}
    mapped: dict[str, dict[str, Any]] = {}
    for item in outputs:
        if isinstance(item, dict) and "name" in item:
            mapped[str(item["name"])] = item
    return mapped


def _path_text_matches(path_text: Any, expected_path: Path) -> bool:
    if not isinstance(path_text, str) or not path_text:
        return False
    candidate = Path(path_text)
    if candidate.is_absolute():
        return candidate.resolve() == expected_path.resolve()
    return (ROOT / candidate).resolve() == expected_path.resolve() or candidate.name == expected_path.name


def _audit_manifest_hashes(
    checks: list[dict[str, str]],
    *,
    paths: dict[str, Path],
    manifest: dict[str, Any],
    file_sha256: dict[str, str],
) -> str:
    status = "PASS"
    outputs = _manifest_output_map(manifest)
    if not outputs:
        _add_check(
            checks,
            check_id="manifest.outputs.present",
            check_category="manifest_hash",
            check_name="workflow manifest has output entries",
            status="FAIL",
            file_path=paths[WORKFLOW_MANIFEST_FILENAME],
            expected="non-empty outputs list",
            observed=manifest.get("outputs"),
        )
        return "FAIL"

    for name, filename in MANIFEST_OUTPUTS:
        check_prefix = f"manifest.{name}"
        entry = outputs.get(name)
        if entry is None:
            status = "FAIL"
            _add_check(
                checks,
                check_id=f"{check_prefix}.present",
                check_category="manifest_hash",
                check_name=f"{name} manifest entry is present",
                status="FAIL",
                file_path=paths[WORKFLOW_MANIFEST_FILENAME],
                expected=name,
                observed="missing",
            )
            continue

        expected_path = paths[filename]
        path_ok = _path_text_matches(entry.get("path"), expected_path)
        if not path_ok:
            status = "FAIL"
        _add_check(
            checks,
            check_id=f"{check_prefix}.path",
            check_category="manifest_hash",
            check_name=f"{name} manifest path points to inspected file",
            status="PASS" if path_ok else "FAIL",
            file_path=paths[WORKFLOW_MANIFEST_FILENAME],
            expected=_display_path(expected_path),
            observed=entry.get("path"),
        )

        if name == "workflow_manifest_json":
            self_ok = entry.get("sha256") is None and entry.get("sha256_status") == "SELF_HASH_NOT_EMBEDDED"
            if not self_ok:
                status = "FAIL"
            _add_check(
                checks,
                check_id=f"{check_prefix}.self_hash_marker",
                check_category="manifest_hash",
                check_name="workflow manifest self-hash is explicitly not embedded",
                status="PASS" if self_ok else "FAIL",
                file_path=paths[WORKFLOW_MANIFEST_FILENAME],
                expected={"sha256": None, "sha256_status": "SELF_HASH_NOT_EMBEDDED"},
                observed={"sha256": entry.get("sha256"), "sha256_status": entry.get("sha256_status")},
                notes="actual manifest file hash is reported in inspected_file_sha256",
            )
            continue

        actual_hash = file_sha256[filename]
        hash_ok = entry.get("sha256") == actual_hash
        if not hash_ok:
            status = "FAIL"
        _add_check(
            checks,
            check_id=f"{check_prefix}.sha256",
            check_category="manifest_hash",
            check_name=f"{name} manifest SHA-256 matches inspected file",
            status="PASS" if hash_ok else "FAIL",
            file_path=expected_path,
            expected=entry.get("sha256"),
            observed=actual_hash,
        )
    return status


def _audit_forbidden_fields(
    checks: list[dict[str, str]],
    *,
    paths: dict[str, Path],
    json_payloads: dict[str, dict[str, Any]],
    csv_payloads: dict[str, tuple[list[str], list[dict[str, str]]]],
) -> str:
    status = "PASS"
    forbidden = {field.casefold() for field in FORBIDDEN_FIELDS}
    for filename in (WORKFLOW_SUMMARY_FILENAME, WORKFLOW_MANIFEST_FILENAME, LEARNING_SUMMARY_FILENAME):
        hits = _json_key_hits(json_payloads[filename], forbidden)
        if hits:
            status = "FAIL"
        _add_check(
            checks,
            check_id=f"forbidden_fields.{filename}",
            check_category="forbidden_fields",
            check_name=f"{filename} has no forbidden field keys",
            status="PASS" if not hits else "FAIL",
            file_path=paths[filename],
            expected="no forbidden keys",
            observed=hits,
        )
    for filename in (DECISIONS_FILENAME, LEARNING_SEGMENTS_FILENAME):
        fieldnames, _rows = csv_payloads[filename]
        hits = _csv_field_hits(fieldnames, forbidden)
        if hits:
            status = "FAIL"
        _add_check(
            checks,
            check_id=f"forbidden_fields.{filename}",
            check_category="forbidden_fields",
            check_name=f"{filename} has no forbidden columns",
            status="PASS" if not hits else "FAIL",
            file_path=paths[filename],
            expected="no forbidden columns",
            observed=hits,
        )
    return status


def _all_false(payload: dict[str, Any], fields: Iterable[str]) -> bool:
    return all(payload.get(field) is False for field in fields)


def _audit_labels_and_contracts(
    checks: list[dict[str, str]],
    *,
    paths: dict[str, Path],
    workflow_summary: dict[str, Any],
    manifest: dict[str, Any],
    learning_summary: dict[str, Any],
    decisions_rows: list[dict[str, str]],
    learning_segment_rows: list[dict[str, str]],
) -> str:
    status = "PASS"

    def add_contract(check_id: str, name: str, ok: bool, file_path: Path, expected: Any, observed: Any) -> None:
        nonlocal status
        if not ok:
            status = "FAIL"
        _add_check(
            checks,
            check_id=check_id,
            check_category="labels_contracts",
            check_name=name,
            status="PASS" if ok else "FAIL",
            file_path=file_path,
            expected=expected,
            observed=observed,
        )

    summary_result_only = str(workflow_summary.get("workflow_status", "")).startswith("RESULT_ONLY")
    manifest_result_only = str(manifest.get("workflow_status", "")).startswith("RESULT_ONLY")
    settlement_values = sorted({row.get("settlement_status", "") for row in decisions_rows})
    settlements_result_only = bool(settlement_values) and all("RESULT_ONLY" in item for item in settlement_values)
    add_contract(
        "contract.result_only",
        "result-only contract is present",
        summary_result_only and manifest_result_only and settlements_result_only,
        paths[WORKFLOW_SUMMARY_FILENAME],
        "RESULT_ONLY workflow status and decision settlements",
        {
            "workflow_summary": workflow_summary.get("workflow_status"),
            "manifest": manifest.get("workflow_status"),
            "decision_settlement_statuses": settlement_values,
        },
    )

    side_effects = manifest.get("side_effects") if isinstance(manifest.get("side_effects"), dict) else {}
    add_contract(
        "contract.local_only",
        "local-only contract has no DB, provider, sports API, live transport, or live output side effects",
        _all_false(side_effects, SIDE_EFFECT_FIELDS),
        paths[WORKFLOW_MANIFEST_FILENAME],
        {field: False for field in SIDE_EFFECT_FIELDS},
        {field: side_effects.get(field) for field in SIDE_EFFECT_FIELDS},
    )

    for filename, payload in (
        (WORKFLOW_SUMMARY_FILENAME, workflow_summary),
        (WORKFLOW_MANIFEST_FILENAME, manifest),
        (LEARNING_SUMMARY_FILENAME, learning_summary),
    ):
        labels = _labels(payload)
        missing = [label for label in EXPECTED_LIMITATION_LABELS if label not in labels]
        add_contract(
            f"contract.limitation_labels.{filename}",
            f"{filename} has required limitation labels",
            not missing,
            paths[filename],
            list(EXPECTED_LIMITATION_LABELS),
            {"present": sorted(labels), "missing": missing},
        )

    interpretations = {
        "workflow_summary": workflow_summary.get("interpretation"),
        "workflow_manifest": manifest.get("interpretation"),
        "learning_summary": learning_summary.get("interpretation"),
    }
    diagnostic_labels = {"not betting edge", "not future prediction", "not production"}
    label_union = _labels(workflow_summary) | _labels(manifest) | _labels(learning_summary)
    diagnostic_ok = all(value == "IN_SAMPLE_DESCRIPTIVE_ONLY" for value in interpretations.values()) and (
        diagnostic_labels <= label_union
    )
    add_contract(
        "contract.diagnostic_only",
        "diagnostic-only contract is present",
        diagnostic_ok,
        paths[WORKFLOW_SUMMARY_FILENAME],
        {
            "interpretation": "IN_SAMPLE_DESCRIPTIVE_ONLY",
            "labels": sorted(diagnostic_labels),
        },
        {"interpretations": interpretations, "labels": sorted(label_union)},
    )

    roi_segments_ok = all(
        row.get("roi", "") in {"", None} and row.get("roi_status") == "ROI_UNAVAILABLE"
        for row in learning_segment_rows
    )
    add_contract(
        "contract.roi_unavailable",
        "ROI is unavailable or null/empty",
        workflow_summary.get("roi") is None
        and workflow_summary.get("roi_status") == "ROI_UNAVAILABLE"
        and learning_summary.get("roi") is None
        and learning_summary.get("roi_status") == "ROI_UNAVAILABLE"
        and roi_segments_ok,
        paths[LEARNING_SUMMARY_FILENAME],
        "ROI null/empty with ROI_UNAVAILABLE status",
        {
            "workflow_summary": {
                "roi": workflow_summary.get("roi"),
                "roi_status": workflow_summary.get("roi_status"),
            },
            "learning_summary": {
                "roi": learning_summary.get("roi"),
                "roi_status": learning_summary.get("roi_status"),
            },
            "learning_segments_all_roi_unavailable": roi_segments_ok,
        },
    )

    add_contract(
        "contract.generates_new_predictions_false",
        "generates_new_predictions is false",
        workflow_summary.get("generates_new_predictions") is False
        and learning_summary.get("generates_new_predictions") is False,
        paths[WORKFLOW_SUMMARY_FILENAME],
        False,
        {
            "workflow_summary": workflow_summary.get("generates_new_predictions"),
            "learning_summary": learning_summary.get("generates_new_predictions"),
        },
    )

    return status


def _audit_counts(
    checks: list[dict[str, str]],
    *,
    paths: dict[str, Path],
    workflow_summary: dict[str, Any],
    learning_summary: dict[str, Any],
    decisions_count: int,
    learning_segments_count: int,
) -> str:
    status = "PASS"
    count_checks = (
        (
            "counts.decisions.workflow_summary",
            WORKFLOW_SUMMARY_FILENAME,
            "workflow_summary decisions_count matches decisions.csv row count",
            workflow_summary.get("decisions_count"),
            decisions_count,
        ),
        (
            "counts.learning_segments.workflow_summary",
            WORKFLOW_SUMMARY_FILENAME,
            "workflow_summary learning_segments_count matches learning_segments.csv row count",
            workflow_summary.get("learning_segments_count"),
            learning_segments_count,
        ),
        (
            "counts.learning_segments.learning_summary",
            LEARNING_SUMMARY_FILENAME,
            "learning_summary segments_count matches learning_segments.csv row count",
            learning_summary.get("segments_count"),
            learning_segments_count,
        ),
    )
    for check_id, filename, name, expected, observed in count_checks:
        ok = expected == observed
        if not ok:
            status = "FAIL"
        _add_check(
            checks,
            check_id=check_id,
            check_category="counts",
            check_name=name,
            status="PASS" if ok else "FAIL",
            file_path=paths[filename],
            expected=expected,
            observed=observed,
        )
    return status


def inspect_paper_strategy_workflow(
    *,
    workflow_dir: Path = DEFAULT_WORKFLOW_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    generated_at_utc: str | None = DEFAULT_GENERATED_AT_UTC,
) -> PaperWorkflowInspectionResult:
    workflow_dir = Path(workflow_dir)
    output_dir = Path(output_dir)
    generated_at_utc = resolve_generated_at_utc(generated_at_utc)
    paths = _require_inputs(workflow_dir)

    json_payloads = {
        WORKFLOW_SUMMARY_FILENAME: _load_json(paths[WORKFLOW_SUMMARY_FILENAME]),
        WORKFLOW_MANIFEST_FILENAME: _load_json(paths[WORKFLOW_MANIFEST_FILENAME]),
        LEARNING_SUMMARY_FILENAME: _load_json(paths[LEARNING_SUMMARY_FILENAME]),
    }
    csv_payloads = {
        DECISIONS_FILENAME: _load_csv(paths[DECISIONS_FILENAME]),
        LEARNING_SEGMENTS_FILENAME: _load_csv(paths[LEARNING_SEGMENTS_FILENAME]),
    }

    file_sha256 = {filename: _sha256(paths[filename]) for filename in REQUIRED_FILES}
    checks: list[dict[str, str]] = []

    manifest_hash_status = _audit_manifest_hashes(
        checks,
        paths=paths,
        manifest=json_payloads[WORKFLOW_MANIFEST_FILENAME],
        file_sha256=file_sha256,
    )
    forbidden_status = _audit_forbidden_fields(
        checks,
        paths=paths,
        json_payloads=json_payloads,
        csv_payloads=csv_payloads,
    )
    limitation_status = _audit_labels_and_contracts(
        checks,
        paths=paths,
        workflow_summary=json_payloads[WORKFLOW_SUMMARY_FILENAME],
        manifest=json_payloads[WORKFLOW_MANIFEST_FILENAME],
        learning_summary=json_payloads[LEARNING_SUMMARY_FILENAME],
        decisions_rows=csv_payloads[DECISIONS_FILENAME][1],
        learning_segment_rows=csv_payloads[LEARNING_SEGMENTS_FILENAME][1],
    )
    counts_status = _audit_counts(
        checks,
        paths=paths,
        workflow_summary=json_payloads[WORKFLOW_SUMMARY_FILENAME],
        learning_summary=json_payloads[LEARNING_SUMMARY_FILENAME],
        decisions_count=len(csv_payloads[DECISIONS_FILENAME][1]),
        learning_segments_count=len(csv_payloads[LEARNING_SEGMENTS_FILENAME][1]),
    )

    failed_checks = [check for check in checks if check["status"] == "FAIL"]
    warning_checks = [check for check in checks if check["status"] == "WARN"]
    overall_status = "FAIL" if failed_checks else "PASS"

    workflow_summary = json_payloads[WORKFLOW_SUMMARY_FILENAME]
    summary = {
        "workflow_dir": _display_path(workflow_dir),
        "generated_at_utc": generated_at_utc,
        "inspected_files": [_display_path(paths[filename]) for filename in REQUIRED_FILES],
        "inspected_file_sha256": {
            _display_path(paths[filename]): file_sha256[filename] for filename in REQUIRED_FILES
        },
        "manifest_hash_check_status": manifest_hash_status,
        "forbidden_field_check_status": forbidden_status,
        "limitation_label_check_status": limitation_status,
        "count_check_status": counts_status,
        "decisions_count": len(csv_payloads[DECISIONS_FILENAME][1]),
        "learning_segments_count": len(csv_payloads[LEARNING_SEGMENTS_FILENAME][1]),
        "workflow_status": workflow_summary.get("workflow_status"),
        "roi_status": workflow_summary.get("roi_status"),
        "generates_new_predictions": workflow_summary.get("generates_new_predictions"),
        "overall_status": overall_status,
        "failures": [
            {
                "check_id": check["check_id"],
                "check_name": check["check_name"],
                "file_path": check["file_path"],
                "observed": check["observed"],
            }
            for check in failed_checks
        ],
        "warnings": [
            {
                "check_id": check["check_id"],
                "check_name": check["check_name"],
                "file_path": check["file_path"],
                "observed": check["observed"],
            }
            for check in warning_checks
        ],
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / INSPECTION_SUMMARY_FILENAME
    checks_path = output_dir / INSPECTION_CHECKS_FILENAME
    _json_write(summary_path, summary)
    with checks_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CHECK_FIELDNAMES, lineterminator="\n")
        writer.writeheader()
        writer.writerows(checks)

    return PaperWorkflowInspectionResult(
        summary=summary,
        checks=tuple(checks),
        output_paths={
            "inspection_summary_json": _display_path(summary_path),
            "inspection_checks_csv": _display_path(checks_path),
        },
    )
