"""Deterministic P239-A runner for result-only paper strategy artifacts.

This module composes the P237-A simulator and P238-A learning summary.  It is
local-only and intentionally does not price decisions, compute returns, infer
edge, or create new predictions.
"""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable

from wbc_backend.recommendation import paper_strategy_learning as learning
from wbc_backend.recommendation import paper_strategy_simulator as simulator
from wbc_backend.recommendation.paper_strategy_simulator import ExplorerError, ROOT


DEFAULT_SOURCE_CSV = ROOT / "report" / "p236a_run_line_backtest_explorer_filtered_games.csv"
DEFAULT_OUTPUT_DIR = ROOT / "report" / "p239a_paper_strategy_workflow"
DEFAULT_GENERATED_AT_UTC = None

WORKFLOW_STATUS = "RESULT_ONLY_PAPER_WORKFLOW"
INTERPRETATION = "IN_SAMPLE_DESCRIPTIVE_ONLY"
ROI_STATUS = "ROI_UNAVAILABLE"
LIMITATION_LABELS = list(learning.LIMITATION_LABELS)

DECISIONS_FILENAME = "decisions.csv"
LEARNING_SUMMARY_FILENAME = "learning_summary.json"
LEARNING_SEGMENTS_FILENAME = "learning_segments.csv"
WORKFLOW_SUMMARY_FILENAME = "workflow_summary.json"
WORKFLOW_MANIFEST_FILENAME = "workflow_manifest.json"
FORBIDDEN_DECISION_OUTPUT_COLUMNS = {"pnl_units"}


@dataclass(frozen=True)
class PaperStrategyWorkflowResult:
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
    return sha256(Path(path).read_bytes()).hexdigest()


def _json_write(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _artifact_paths(output_dir: Path) -> dict[str, Path]:
    return {
        "decisions_csv": output_dir / DECISIONS_FILENAME,
        "learning_summary_json": output_dir / LEARNING_SUMMARY_FILENAME,
        "learning_segments_csv": output_dir / LEARNING_SEGMENTS_FILENAME,
        "workflow_summary_json": output_dir / WORKFLOW_SUMMARY_FILENAME,
        "workflow_manifest_json": output_dir / WORKFLOW_MANIFEST_FILENAME,
    }


def _validate_min_confidence(value: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ExplorerError("INVALID_FILTER: --min-confidence must be numeric") from exc
    if not 0.5 <= parsed <= 1.0:
        raise ExplorerError("INVALID_FILTER: --min-confidence must be between 0.5 and 1.0")
    return parsed


def _validate_thresholds(thresholds: Iterable[float]) -> tuple[float, ...]:
    parsed = tuple(sorted(dict.fromkeys(float(value) for value in thresholds)))
    if not parsed:
        raise ExplorerError("INVALID_FILTER: at least one threshold is required")
    if any(not 0.5 <= threshold <= 1.0 for threshold in parsed):
        raise ExplorerError("INVALID_FILTER: thresholds must be between 0.5 and 1.0")
    return parsed


def _for_summary(paths: dict[str, Path]) -> dict[str, str]:
    return {name: _display_path(path) for name, path in paths.items()}


def _output_manifest_entries(paths: dict[str, Path], hashes: dict[str, str]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for name in (
        "decisions_csv",
        "learning_summary_json",
        "learning_segments_csv",
        "workflow_summary_json",
        "workflow_manifest_json",
    ):
        entry = {"name": name, "path": _display_path(paths[name])}
        if name == "workflow_manifest_json":
            entry["sha256"] = None
            entry["sha256_status"] = "SELF_HASH_NOT_EMBEDDED"
        else:
            entry["sha256"] = hashes[name]
        entries.append(entry)
    return entries


def _remove_forbidden_decision_output_columns(path: Path) -> None:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = [
            name for name in (reader.fieldnames or ()) if name not in FORBIDDEN_DECISION_OUTPUT_COLUMNS
        ]
        rows = [{name: row[name] for name in fieldnames} for row in reader]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def run_paper_strategy_workflow(
    *,
    source_csv: Path = DEFAULT_SOURCE_CSV,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    min_confidence: float = 0.5,
    thresholds: Iterable[float] = learning.DEFAULT_THRESHOLDS,
    generated_at_utc: str | None = DEFAULT_GENERATED_AT_UTC,
) -> PaperStrategyWorkflowResult:
    source_csv = Path(source_csv)
    output_dir = Path(output_dir)
    generated_at_utc = learning.resolve_generated_at_utc(generated_at_utc)
    min_confidence = _validate_min_confidence(min_confidence)
    parsed_thresholds = _validate_thresholds(thresholds)
    paths = _artifact_paths(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    source_hash = _sha256(source_csv)

    simulator_dataset = simulator.load_paper_strategy_dataset(source_csv)
    simulator_payload, decisions = simulator.build_output_payload(
        simulator_dataset,
        min_confidence=min_confidence,
    )
    simulator.write_outputs(
        simulator_payload,
        decisions,
        output_dir / "_p237_summary_internal.json",
        paths["decisions_csv"],
    )
    (output_dir / "_p237_summary_internal.json").unlink()
    _remove_forbidden_decision_output_columns(paths["decisions_csv"])

    learning_dataset = learning.load_paper_decisions(paths["decisions_csv"])
    learning_payload, segments = learning.build_output_payload(
        learning_dataset,
        thresholds=parsed_thresholds,
        generated_at_utc=generated_at_utc,
    )
    learning.write_outputs(
        learning_payload,
        segments,
        paths["learning_summary_json"],
        paths["learning_segments_csv"],
    )

    artifact_paths = _for_summary(paths)
    component_hashes = {
        "decisions_csv": _sha256(paths["decisions_csv"]),
        "learning_summary_json": _sha256(paths["learning_summary_json"]),
        "learning_segments_csv": _sha256(paths["learning_segments_csv"]),
    }
    summary = {
        "source_csv": _display_path(source_csv),
        "source_sha256": source_hash,
        "output_dir": _display_path(output_dir),
        "generated_at_utc": generated_at_utc,
        "min_confidence": min_confidence,
        "thresholds": list(parsed_thresholds),
        "decisions_count": len(decisions),
        "learning_segments_count": len(segments),
        "artifact_paths": artifact_paths,
        "artifact_sha256": component_hashes,
        "roi": None,
        "roi_status": ROI_STATUS,
        "generates_new_predictions": False,
        "workflow_status": WORKFLOW_STATUS,
        "interpretation": INTERPRETATION,
        "limitation_labels": LIMITATION_LABELS,
    }
    _json_write(paths["workflow_summary_json"], summary)

    hashes_with_summary = {
        **component_hashes,
        "workflow_summary_json": _sha256(paths["workflow_summary_json"]),
    }
    manifest = {
        "generated_at_utc": generated_at_utc,
        "inputs": [
            {
                "name": "source_csv",
                "path": _display_path(source_csv),
                "sha256": source_hash,
            }
        ],
        "outputs": _output_manifest_entries(paths, hashes_with_summary),
        "parameters": {
            "source_csv": _display_path(source_csv),
            "output_dir": _display_path(output_dir),
            "min_confidence": min_confidence,
            "thresholds": list(parsed_thresholds),
        },
        "side_effects": {
            "db_writes": False,
            "provider_calls": False,
            "sports_api_calls": False,
            "live_transport": False,
            "live_output": False,
        },
        "workflow_status": WORKFLOW_STATUS,
        "interpretation": INTERPRETATION,
        "limitation_labels": LIMITATION_LABELS,
    }
    _json_write(paths["workflow_manifest_json"], manifest)

    artifact_sha256 = {
        **hashes_with_summary,
        "workflow_manifest_json": _sha256(paths["workflow_manifest_json"]),
    }
    return PaperStrategyWorkflowResult(
        summary=summary,
        manifest=manifest,
        artifact_paths=artifact_paths,
        artifact_sha256=artifact_sha256,
    )
