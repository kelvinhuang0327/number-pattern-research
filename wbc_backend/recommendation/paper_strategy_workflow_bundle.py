"""Deterministic P242-A bundle runner for result-only paper workflow artifacts.

This module orchestrates P239, P240, and P241 into one isolated local output
directory. It remains paper-only and does not contact providers, write DBs,
price outcomes, compute edge, or create recommendations.
"""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable

from wbc_backend.recommendation import paper_strategy_learning as learning
from wbc_backend.recommendation.paper_strategy_simulator import ExplorerError, ROOT
from wbc_backend.recommendation.paper_strategy_workflow import (
    DEFAULT_SOURCE_CSV,
    run_paper_strategy_workflow,
)
from wbc_backend.recommendation.paper_strategy_workflow_inspector import (
    PaperWorkflowInspectorError,
    inspect_paper_strategy_workflow,
)
from wbc_backend.recommendation.paper_strategy_workflow_review_pack import (
    ReviewPackError,
    build_paper_strategy_workflow_review_pack,
)


DEFAULT_OUTPUT_DIR = ROOT / "report" / "p242a_paper_strategy_workflow_bundle"
DEFAULT_GENERATED_AT_UTC = "2026-07-08T00:00:00Z"

BUNDLE_SUMMARY_FILENAME = "bundle_summary.json"
BUNDLE_MANIFEST_FILENAME = "bundle_manifest.json"
WORKFLOW_DIRNAME = "workflow"
INSPECTION_DIRNAME = "inspection"
REVIEW_DIRNAME = "review"

WORKFLOW_OUTPUTS = (
    "decisions.csv",
    "learning_summary.json",
    "learning_segments.csv",
    "workflow_summary.json",
    "workflow_manifest.json",
)
INSPECTION_OUTPUTS = ("inspection_summary.json", "inspection_checks.csv")
REVIEW_OUTPUTS = ("review_summary.json", "review_artifacts.csv", "review_report.md")

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
    "compounding",
    "best_strategy",
    "best_threshold",
    "recommended_bet",
    "recommendation",
    "strategy_recommendation",
)


class PaperWorkflowBundleError(RuntimeError):
    """Raised when the bundle runner cannot produce valid local artifacts."""


@dataclass(frozen=True)
class PaperWorkflowBundleResult:
    summary: dict[str, Any]
    manifest: dict[str, Any]
    artifact_paths: dict[str, str]
    artifact_sha256: dict[str, str]


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
        raise PaperWorkflowBundleError(f"CORRUPT_INPUT: invalid JSON in {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise PaperWorkflowBundleError(f"CORRUPT_INPUT: JSON root must be an object: {path}")
    return payload


def _load_csv_header(path: Path) -> list[str]:
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            return list(reader.fieldnames or ())
    except csv.Error as exc:
        raise PaperWorkflowBundleError(f"CORRUPT_INPUT: invalid CSV in {path}: {exc}") from exc


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


def _csv_field_hits(path: Path, forbidden: set[str]) -> list[str]:
    return [field for field in _load_csv_header(path) if field.casefold() in forbidden]


def _artifact_paths(output_dir: Path) -> dict[str, Path]:
    workflow_dir = output_dir / WORKFLOW_DIRNAME
    inspection_dir = output_dir / INSPECTION_DIRNAME
    review_dir = output_dir / REVIEW_DIRNAME
    paths: dict[str, Path] = {
        f"workflow/{filename}": workflow_dir / filename for filename in WORKFLOW_OUTPUTS
    }
    paths.update(
        {f"inspection/{filename}": inspection_dir / filename for filename in INSPECTION_OUTPUTS}
    )
    paths.update({f"review/{filename}": review_dir / filename for filename in REVIEW_OUTPUTS})
    paths["bundle_summary.json"] = output_dir / BUNDLE_SUMMARY_FILENAME
    paths["bundle_manifest.json"] = output_dir / BUNDLE_MANIFEST_FILENAME
    return paths


def _require_outputs(paths: dict[str, Path]) -> None:
    missing = [str(path) for path in paths.values() if not path.is_file()]
    if missing:
        raise PaperWorkflowBundleError(f"MISSING_OUTPUT: required bundle artifacts not found: {missing}")
    empty = [str(path) for path in paths.values() if path.stat().st_size == 0]
    if empty:
        raise PaperWorkflowBundleError(f"EMPTY_OUTPUT: required bundle artifacts are empty: {empty}")


def _artifact_counts() -> dict[str, int]:
    return {
        "workflow": len(WORKFLOW_OUTPUTS),
        "inspection": len(INSPECTION_OUTPUTS),
        "review": len(REVIEW_OUTPUTS),
        "bundle": 2,
        "total": len(WORKFLOW_OUTPUTS) + len(INSPECTION_OUTPUTS) + len(REVIEW_OUTPUTS) + 2,
    }


def _forbidden_output_failures(paths: dict[str, Path]) -> list[dict[str, str]]:
    forbidden = {field.casefold() for field in FORBIDDEN_FIELDS}
    failures: list[dict[str, str]] = []
    for artifact_name, path in paths.items():
        if artifact_name == "bundle_manifest.json":
            continue
        if path.suffix == ".json":
            hits = _json_key_hits(_load_json(path), forbidden)
        elif path.suffix == ".csv":
            hits = _csv_field_hits(path, forbidden)
        else:
            hits = []
        if hits:
            failures.append(
                {
                    "check_id": f"forbidden_fields.{artifact_name}",
                    "message": "bundle output contains forbidden field keys or columns",
                    "file_path": _display_path(path),
                    "observed": json.dumps(hits, sort_keys=True, separators=(",", ":")),
                }
            )
    return failures


def _status_failures(
    *,
    workflow_summary: dict[str, Any],
    inspection_summary: dict[str, Any],
    review_summary: dict[str, Any],
) -> list[dict[str, str]]:
    failures: list[dict[str, str]] = []
    if workflow_summary.get("workflow_status") != "RESULT_ONLY_PAPER_WORKFLOW":
        failures.append(
            {
                "check_id": "workflow.workflow_status",
                "message": "P239 workflow_status is not RESULT_ONLY_PAPER_WORKFLOW",
                "file_path": "",
                "observed": str(workflow_summary.get("workflow_status")),
            }
        )
    if inspection_summary.get("overall_status") != "PASS":
        failures.append(
            {
                "check_id": "inspection.overall_status",
                "message": "P240 inspection overall_status is not PASS",
                "file_path": "",
                "observed": str(inspection_summary.get("overall_status")),
            }
        )
    if review_summary.get("review_status") != "PASS":
        failures.append(
            {
                "check_id": "review.review_status",
                "message": "P241 review_status is not PASS",
                "file_path": "",
                "observed": str(review_summary.get("review_status")),
            }
        )
    if workflow_summary.get("generates_new_predictions") is not False:
        failures.append(
            {
                "check_id": "contract.generates_new_predictions",
                "message": "workflow generates_new_predictions must be false",
                "file_path": "",
                "observed": str(workflow_summary.get("generates_new_predictions")),
            }
        )
    if workflow_summary.get("roi_status") != "ROI_UNAVAILABLE":
        failures.append(
            {
                "check_id": "contract.roi_status",
                "message": "workflow roi_status must remain ROI_UNAVAILABLE",
                "file_path": "",
                "observed": str(workflow_summary.get("roi_status")),
            }
        )
    missing_labels = [
        label
        for label in REQUIRED_LIMITATION_LABELS
        if label not in set(workflow_summary.get("limitation_labels", ()))
    ]
    if missing_labels:
        failures.append(
            {
                "check_id": "contract.limitation_labels",
                "message": "workflow summary is missing required limitation labels",
                "file_path": "",
                "observed": json.dumps(missing_labels, sort_keys=True, separators=(",", ":")),
            }
        )
    return failures


def _manifest_outputs(paths: dict[str, Path], hashes: dict[str, str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for artifact_name in sorted(paths):
        row = {"name": artifact_name, "path": _display_path(paths[artifact_name])}
        if artifact_name == "bundle_manifest.json":
            row["sha256"] = None
            row["sha256_status"] = "SELF_HASH_NOT_EMBEDDED"
        else:
            row["sha256"] = hashes[artifact_name]
        rows.append(row)
    return rows


def _aggregate_failures(
    *,
    local_failures: Iterable[dict[str, str]],
    inspection_summary: dict[str, Any],
    review_summary: dict[str, Any],
) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = list(local_failures)
    failures.extend(
        {
            "check_id": f"inspection.{failure.get('check_id', '')}",
            "message": failure.get("check_name", "P240 inspection failure"),
            "file_path": failure.get("file_path", ""),
            "observed": failure.get("observed", ""),
        }
        for failure in inspection_summary.get("failures", [])
        if isinstance(failure, dict)
    )
    failures.extend(
        {
            "check_id": f"review.{failure.get('check_id', '')}",
            "message": failure.get("message", "P241 review failure"),
            "file_path": failure.get("file_path", ""),
            "observed": failure.get("observed", ""),
        }
        for failure in review_summary.get("failures", [])
        if isinstance(failure, dict)
    )
    return failures


def run_paper_strategy_workflow_bundle(
    *,
    source_csv: Path = DEFAULT_SOURCE_CSV,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    min_confidence: float = 0.5,
    thresholds: Iterable[float] = learning.DEFAULT_THRESHOLDS,
    generated_at_utc: str = DEFAULT_GENERATED_AT_UTC,
) -> PaperWorkflowBundleResult:
    source_csv = Path(source_csv)
    output_dir = Path(output_dir)
    parsed_thresholds = tuple(thresholds)
    workflow_dir = output_dir / WORKFLOW_DIRNAME
    inspection_dir = output_dir / INSPECTION_DIRNAME
    review_dir = output_dir / REVIEW_DIRNAME
    output_dir.mkdir(parents=True, exist_ok=True)
    workflow_dir.mkdir(parents=True, exist_ok=True)
    inspection_dir.mkdir(parents=True, exist_ok=True)
    review_dir.mkdir(parents=True, exist_ok=True)

    workflow_result = run_paper_strategy_workflow(
        source_csv=source_csv,
        output_dir=workflow_dir,
        min_confidence=min_confidence,
        thresholds=parsed_thresholds,
        generated_at_utc=generated_at_utc,
    )
    inspection_result = inspect_paper_strategy_workflow(
        workflow_dir=workflow_dir,
        output_dir=inspection_dir,
        generated_at_utc=generated_at_utc,
    )
    review_result = build_paper_strategy_workflow_review_pack(
        workflow_dir=workflow_dir,
        inspection_dir=inspection_dir,
        output_dir=review_dir,
        generated_at_utc=generated_at_utc,
    )

    paths = _artifact_paths(output_dir)
    child_paths = {
        name: path
        for name, path in paths.items()
        if name not in {"bundle_summary.json", "bundle_manifest.json"}
    }
    _require_outputs(child_paths)

    child_hashes = {name: _sha256(path) for name, path in child_paths.items()}
    workflow_summary = workflow_result.summary
    inspection_summary = inspection_result.summary
    review_summary = review_result.summary
    local_failures = _status_failures(
        workflow_summary=workflow_summary,
        inspection_summary=inspection_summary,
        review_summary=review_summary,
    )
    local_failures.extend(_forbidden_output_failures(child_paths))
    failures = _aggregate_failures(
        local_failures=local_failures,
        inspection_summary=inspection_summary,
        review_summary=review_summary,
    )
    warnings = list(inspection_summary.get("warnings", [])) + list(review_summary.get("warnings", []))
    bundle_status = "FAIL" if failures else "PASS"

    summary = {
        "generated_at_utc": generated_at_utc,
        "source_csv": _display_path(source_csv),
        "output_dir": _display_path(output_dir),
        "bundle_status": bundle_status,
        "workflow_status": workflow_summary.get("workflow_status"),
        "inspection_overall_status": inspection_summary.get("overall_status"),
        "review_status": review_summary.get("review_status"),
        "decisions_count": workflow_summary.get("decisions_count"),
        "learning_segments_count": workflow_summary.get("learning_segments_count"),
        "artifact_counts": _artifact_counts(),
        "artifact_sha256": {
            _display_path(path): child_hashes[name] for name, path in sorted(child_paths.items())
        },
        "roi_status": workflow_summary.get("roi_status"),
        "generates_new_predictions": False,
        "limitation_labels": list(REQUIRED_LIMITATION_LABELS),
        "failures": failures,
        "warnings": warnings,
    }
    _json_write(paths["bundle_summary.json"], summary)

    hashes = {**child_hashes, "bundle_summary.json": _sha256(paths["bundle_summary.json"])}
    manifest = {
        "generated_at_utc": generated_at_utc,
        "parameters": {
            "source_csv": _display_path(source_csv),
            "output_dir": _display_path(output_dir),
            "min_confidence": float(min_confidence),
            "thresholds": list(parsed_thresholds),
        },
        "inputs": [
            {
                "name": "source_csv",
                "path": _display_path(source_csv),
                "sha256": _sha256(source_csv),
            }
        ],
        "outputs": _manifest_outputs(paths, hashes),
        "no_side_effects": {
            "no_db_writes": True,
            "no_provider_api_calls": True,
            "no_remote_fetch": True,
            "no_pybaseball": True,
            "no_live_output": True,
            "no_real_betting": True,
            "no_sports_api_calls": True,
        },
        "orchestration": {
            "workflow_dir": _display_path(workflow_dir),
            "inspection_dir": _display_path(inspection_dir),
            "review_dir": _display_path(review_dir),
        },
        "bundle_status": bundle_status,
        "limitation_labels": list(REQUIRED_LIMITATION_LABELS),
    }
    _json_write(paths["bundle_manifest.json"], manifest)
    all_hashes = {**hashes, "bundle_manifest.json": _sha256(paths["bundle_manifest.json"])}

    return PaperWorkflowBundleResult(
        summary=summary,
        manifest=manifest,
        artifact_paths={name: _display_path(path) for name, path in sorted(paths.items())},
        artifact_sha256={_display_path(paths[name]): digest for name, digest in all_hashes.items()},
    )


def run_bundle_or_raise(
    *,
    source_csv: Path = DEFAULT_SOURCE_CSV,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    min_confidence: float = 0.5,
    thresholds: Iterable[float] = learning.DEFAULT_THRESHOLDS,
    generated_at_utc: str = DEFAULT_GENERATED_AT_UTC,
) -> PaperWorkflowBundleResult:
    try:
        return run_paper_strategy_workflow_bundle(
            source_csv=source_csv,
            output_dir=output_dir,
            min_confidence=min_confidence,
            thresholds=thresholds,
            generated_at_utc=generated_at_utc,
        )
    except (ExplorerError, PaperWorkflowInspectorError, ReviewPackError) as exc:
        raise PaperWorkflowBundleError(str(exc)) from exc
