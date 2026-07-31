"""Deterministic local status export for P237-P246 paper-only artifacts.

This module reads committed source and report files, records metadata, and
writes a compact status pack. It does not execute workflow/query/diff/gate
scripts, contact providers, write data/DB/runtime state, or compute betting
performance.
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

DEFAULT_OUTPUT_DIR = ROOT / "report" / "p247a_paper_toolchain_status"
DEFAULT_GENERATED_AT_UTC = None

STATUS_JSON_FILENAME = "toolchain_status.json"
STEPS_CSV_FILENAME = "toolchain_steps.csv"
REPORT_MD_FILENAME = "toolchain_report.md"

STEP_CSV_FIELDNAMES = [
    "step_id",
    "step_name",
    "script_path",
    "script_present",
    "artifact_root_or_file",
    "artifact_present",
    "file_count",
    "total_bytes",
    "status",
    "sha256_or_digest",
    "notes",
]

LIMITATION_LABELS = (
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

NOT_CLAIMS = (
    "No ROI, paper P/L, EV, Kelly, bankroll, or compounding is computed.",
    "No best_strategy, best_threshold, recommended_bet, or strategy ranking is output.",
    "No betting edge, future prediction, true-PIT validation, or multi-season validation is claimed.",
    "No live, production, or real betting output is created.",
)


@dataclass(frozen=True)
class ToolchainStepSpec:
    step_id: str
    step_name: str
    script_candidates: tuple[Path, ...]
    module_path: Path | None
    artifact_roots: tuple[Path, ...]
    script_optional: bool = False


@dataclass(frozen=True)
class ArtifactSummary:
    path: str
    present: bool
    path_type: str
    file_count: int
    total_bytes: int
    sha256_or_digest: str


@dataclass(frozen=True)
class PaperToolchainStatusResult:
    status: dict[str, Any]
    step_rows: tuple[dict[str, str], ...]
    output_paths: dict[str, str]


STEP_SPECS = (
    ToolchainStepSpec(
        step_id="P237",
        step_name="paper strategy simulator",
        script_candidates=(ROOT / "scripts" / "run_mlb_paper_strategy_simulator.py",),
        module_path=ROOT / "wbc_backend" / "recommendation" / "paper_strategy_simulator.py",
        artifact_roots=(
            ROOT / "report" / "p237a_paper_strategy_simulator_summary.json",
            ROOT / "report" / "p237a_paper_strategy_decisions.csv",
        ),
        script_optional=True,
    ),
    ToolchainStepSpec(
        step_id="P238",
        step_name="paper strategy learning",
        script_candidates=(ROOT / "scripts" / "run_mlb_paper_strategy_learning.py",),
        module_path=ROOT / "wbc_backend" / "recommendation" / "paper_strategy_learning.py",
        artifact_roots=(
            ROOT / "report" / "p238a_paper_strategy_learning_summary.json",
            ROOT / "report" / "p238a_paper_strategy_learning_segments.csv",
        ),
        script_optional=True,
    ),
    ToolchainStepSpec(
        step_id="P239",
        step_name="paper strategy workflow",
        script_candidates=(ROOT / "scripts" / "run_mlb_paper_strategy_workflow.py",),
        module_path=ROOT / "wbc_backend" / "recommendation" / "paper_strategy_workflow.py",
        artifact_roots=(ROOT / "report" / "p239a_paper_strategy_workflow",),
    ),
    ToolchainStepSpec(
        step_id="P240",
        step_name="paper strategy workflow inspector",
        script_candidates=(ROOT / "scripts" / "inspect_mlb_paper_strategy_workflow.py",),
        module_path=ROOT / "wbc_backend" / "recommendation" / "paper_strategy_workflow_inspector.py",
        artifact_roots=(ROOT / "report" / "p240a_paper_strategy_workflow_inspector",),
    ),
    ToolchainStepSpec(
        step_id="P241",
        step_name="paper strategy workflow review pack",
        script_candidates=(ROOT / "scripts" / "build_mlb_paper_strategy_workflow_review_pack.py",),
        module_path=ROOT
        / "wbc_backend"
        / "recommendation"
        / "paper_strategy_workflow_review_pack.py",
        artifact_roots=(ROOT / "report" / "p241a_paper_strategy_workflow_review_pack",),
    ),
    ToolchainStepSpec(
        step_id="P242",
        step_name="paper strategy workflow bundle",
        script_candidates=(ROOT / "scripts" / "run_mlb_paper_strategy_workflow_bundle.py",),
        module_path=ROOT / "wbc_backend" / "recommendation" / "paper_strategy_workflow_bundle.py",
        artifact_roots=(ROOT / "report" / "p242a_paper_strategy_workflow_bundle",),
    ),
    ToolchainStepSpec(
        step_id="P243",
        step_name="paper artifact catalog",
        script_candidates=(ROOT / "scripts" / "build_mlb_paper_artifact_catalog.py",),
        module_path=ROOT / "wbc_backend" / "recommendation" / "paper_artifact_catalog.py",
        artifact_roots=(ROOT / "report" / "p243a_paper_artifact_catalog",),
    ),
    ToolchainStepSpec(
        step_id="P244",
        step_name="paper artifact catalog query",
        script_candidates=(ROOT / "scripts" / "query_mlb_paper_artifact_catalog.py",),
        module_path=ROOT / "wbc_backend" / "recommendation" / "paper_artifact_catalog_query.py",
        artifact_roots=(ROOT / "report" / "p244a_paper_artifact_catalog_query",),
    ),
    ToolchainStepSpec(
        step_id="P245",
        step_name="paper artifact catalog diff",
        script_candidates=(ROOT / "scripts" / "diff_mlb_paper_artifact_catalogs.py",),
        module_path=ROOT / "wbc_backend" / "recommendation" / "paper_artifact_catalog_diff.py",
        artifact_roots=(ROOT / "report" / "p245a_paper_artifact_catalog_diff",),
    ),
    ToolchainStepSpec(
        step_id="P246",
        step_name="paper artifact diff gate",
        script_candidates=(ROOT / "scripts" / "check_mlb_paper_artifact_diff.py",),
        module_path=ROOT / "wbc_backend" / "recommendation" / "paper_artifact_diff_gate.py",
        artifact_roots=(ROOT / "report" / "p246a_paper_artifact_diff_gate",),
    ),
)


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


def _stable_json_write(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _files_for_root(path: Path) -> tuple[Path, ...]:
    if path.is_file():
        return (path,)
    if path.is_dir():
        return tuple(sorted((child for child in path.rglob("*") if child.is_file()), key=_display_path))
    return ()


def _digest_for_files(files: Iterable[Path]) -> str:
    digest = sha256()
    for path in files:
        relative = _display_path(path)
        file_hash = _sha256(path)
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(path.stat().st_size).encode("ascii"))
        digest.update(b"\0")
        digest.update(file_hash.encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _summarize_artifact_root(path: Path) -> ArtifactSummary:
    files = _files_for_root(path)
    present = path.exists()
    path_type = "directory" if path.is_dir() else "file" if path.is_file() else "missing"
    total_bytes = sum(file_path.stat().st_size for file_path in files)
    digest = _sha256(path) if path.is_file() else _digest_for_files(files) if files else ""
    return ArtifactSummary(
        path=_display_path(path),
        present=present,
        path_type=path_type,
        file_count=len(files),
        total_bytes=total_bytes,
        sha256_or_digest=digest,
    )


def _selected_script(spec: ToolchainStepSpec) -> Path:
    for candidate in spec.script_candidates:
        if candidate.is_file():
            return candidate
    return spec.script_candidates[0]


def _load_latest_gate(gate_summary_path: Path) -> tuple[str, dict[str, Any], list[str]]:
    if not gate_summary_path.is_file():
        return "MISSING", {}, ["latest P246 gate summary is missing"]
    try:
        payload = json.loads(gate_summary_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return "CORRUPT", {}, [f"latest P246 gate summary is invalid JSON: {exc}"]
    if not isinstance(payload, dict):
        return "CORRUPT", {}, ["latest P246 gate summary JSON is not an object"]
    latest_status = str(payload.get("gate_status", "UNKNOWN"))
    counts = {
        "check_counts": payload.get("check_counts", {}),
        "observed_counts": payload.get("observed_counts", {}),
        "warning_count": payload.get("warning_count", 0),
        "failure_count": payload.get("failure_count", 0),
    }
    return latest_status, counts, []


def _step_summary(spec: ToolchainStepSpec) -> tuple[dict[str, Any], dict[str, str], list[str], list[str]]:
    warnings: list[str] = []
    failures: list[str] = []
    script_path = _selected_script(spec)
    script_present = script_path.is_file()
    module_present = spec.module_path.is_file() if spec.module_path else False
    artifact_summaries = [_summarize_artifact_root(path) for path in spec.artifact_roots]
    missing_artifacts = [item for item in artifact_summaries if not item.present]

    if not script_present:
        message = f"{spec.step_id} script not found: {_display_path(script_path)}"
        if spec.script_optional:
            warnings.append(message)
        else:
            warnings.append(message)
    if spec.module_path and not module_present:
        warnings.append(f"{spec.step_id} module not found: {_display_path(spec.module_path)}")
    for artifact in missing_artifacts:
        failures.append(f"{spec.step_id} required artifact root missing: {artifact.path}")

    status = "FAIL" if missing_artifacts else "WARN" if warnings else "PASS"
    file_count = sum(item.file_count for item in artifact_summaries)
    total_bytes = sum(item.total_bytes for item in artifact_summaries)
    digest = _digest_for_files(
        file_path
        for artifact_root in spec.artifact_roots
        for file_path in _files_for_root(artifact_root)
    )
    artifact_paths = [item.path for item in artifact_summaries]
    notes = []
    if warnings:
        notes.append("; ".join(warnings))
    if failures:
        notes.append("; ".join(failures))

    summary = {
        "step_id": spec.step_id,
        "step_name": spec.step_name,
        "script_path": _display_path(script_path),
        "script_present": script_present,
        "script_optional": spec.script_optional,
        "module_path": _display_path(spec.module_path) if spec.module_path else "",
        "module_present": module_present,
        "artifact_roots": [item.__dict__ for item in artifact_summaries],
        "artifact_present": not missing_artifacts,
        "file_count": file_count,
        "total_bytes": total_bytes,
        "status": status,
        "sha256_or_digest": digest,
        "notes": " ".join(notes),
    }
    row = {
        "step_id": spec.step_id,
        "step_name": spec.step_name,
        "script_path": _display_path(script_path),
        "script_present": script_present,
        "artifact_root_or_file": "; ".join(artifact_paths),
        "artifact_present": not missing_artifacts,
        "file_count": file_count,
        "total_bytes": total_bytes,
        "status": status,
        "sha256_or_digest": digest,
        "notes": summary["notes"],
    }
    return summary, row, warnings, failures


def _source_hashes(step_summaries: Iterable[dict[str, Any]]) -> dict[str, Any]:
    scripts: dict[str, str] = {}
    modules: dict[str, str] = {}
    artifact_roots: dict[str, dict[str, Any]] = {}
    for step in step_summaries:
        script = ROOT / step["script_path"]
        if script.is_file():
            scripts[step["script_path"]] = _sha256(script)
        module_path = step.get("module_path")
        if module_path:
            module = ROOT / str(module_path)
            if module.is_file():
                modules[str(module_path)] = _sha256(module)
        for artifact in step["artifact_roots"]:
            artifact_roots[artifact["path"]] = {
                "present": artifact["present"],
                "file_count": artifact["file_count"],
                "total_bytes": artifact["total_bytes"],
                "sha256_or_digest": artifact["sha256_or_digest"],
            }
    return {
        "scripts": dict(sorted(scripts.items())),
        "modules": dict(sorted(modules.items())),
        "artifact_roots": dict(sorted(artifact_roots.items())),
    }


def _write_csv(path: Path, rows: Iterable[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=STEP_CSV_FIELDNAMES, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _format_cell(row.get(field, "")) for field in STEP_CSV_FIELDNAMES})


def _write_markdown(path: Path, status: dict[str, Any]) -> None:
    lines = [
        "# P247-A Paper Toolchain Status",
        "",
        "## Summary",
        f"- Generated at UTC: {status['generated_at_utc']}",
        f"- Toolchain status: {status['toolchain_status']}",
        f"- Steps: {status['step_count']}",
        f"- Artifact roots present: {status['present_artifact_root_count']} / {status['artifact_root_count']}",
        f"- Scripts present: {status['present_script_count']} / {status['script_count']}",
        "",
        "## Toolchain Steps",
    ]
    for step in status["step_summaries"]:
        lines.append(
            "- {step_id} {step_name}: {status}; files={file_count}; bytes={total_bytes}; digest={digest}".format(
                step_id=step["step_id"],
                step_name=step["step_name"],
                status=step["status"],
                file_count=step["file_count"],
                total_bytes=step["total_bytes"],
                digest=step["sha256_or_digest"],
            )
        )

    lines.extend(
        [
            "",
            "## Latest Gate",
            f"- Latest P246 gate status: {status['latest_gate_status']}",
            f"- Latest P246 gate counts: {_format_cell(status['latest_gate_counts'])}",
            "",
            "## Missing / Warning Items",
        ]
    )
    if not status["warnings"] and not status["failures"]:
        lines.append("- None")
    for warning in status["warnings"]:
        lines.append(f"- Warning: {warning}")
    for failure in status["failures"]:
        lines.append(f"- Failure: {failure}")

    lines.extend(["", "## Safety Boundaries"])
    for key, value in status["no_side_effects"].items():
        lines.append(f"- {key}: {value}")

    lines.extend(["", "## Limitations"])
    for label in status["limitation_labels"]:
        lines.append(f"- {label}")

    lines.extend(["", "## Not Claims"])
    for claim in NOT_CLAIMS:
        lines.append(f"- {claim}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_paper_toolchain_status(
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    generated_at_utc: str | None = DEFAULT_GENERATED_AT_UTC,
    step_specs: Iterable[ToolchainStepSpec] = STEP_SPECS,
) -> PaperToolchainStatusResult:
    output_dir = Path(output_dir)
    generated_at_utc = resolve_generated_at_utc(generated_at_utc)
    step_specs = tuple(step_specs)
    step_summaries: list[dict[str, Any]] = []
    step_rows: list[dict[str, str]] = []
    warnings: list[str] = []
    failures: list[str] = []

    for spec in step_specs:
        summary, row, step_warnings, step_failures = _step_summary(spec)
        step_summaries.append(summary)
        step_rows.append(row)
        warnings.extend(step_warnings)
        failures.extend(step_failures)

    latest_gate_status, latest_gate_counts, gate_issues = _load_latest_gate(
        ROOT / "report" / "p246a_paper_artifact_diff_gate" / "gate_summary.json"
    )
    failures.extend(gate_issues)
    if latest_gate_status == "FAIL":
        failures.append("latest P246 gate status is FAIL")
    elif latest_gate_status not in {"PASS", "WARN"}:
        warnings.append(f"latest P246 gate status is {latest_gate_status}")

    artifact_root_count = sum(len(spec.artifact_roots) for spec in step_specs)
    present_artifact_root_count = sum(
        1 for step in step_summaries for artifact in step["artifact_roots"] if artifact["present"]
    )
    script_count = len(step_summaries)
    present_script_count = sum(1 for step in step_summaries if step["script_present"])
    toolchain_status = "FAIL" if failures else "WARN" if warnings else "PASS"

    status = {
        "generated_at_utc": generated_at_utc,
        "toolchain_status": toolchain_status,
        "step_count": len(step_summaries),
        "artifact_root_count": artifact_root_count,
        "present_artifact_root_count": present_artifact_root_count,
        "missing_artifact_root_count": artifact_root_count - present_artifact_root_count,
        "script_count": script_count,
        "present_script_count": present_script_count,
        "latest_gate_status": latest_gate_status,
        "latest_gate_counts": latest_gate_counts,
        "source_hashes": _source_hashes(step_summaries),
        "step_summaries": step_summaries,
        "warnings": sorted(warnings),
        "failures": sorted(failures),
        "limitation_labels": list(LIMITATION_LABELS),
        "no_side_effects": {
            "read_existing_artifacts_only": True,
            "executed_existing_workflows": False,
            "regenerated_catalogs_diffs_or_gates": False,
            "contacted_providers": False,
            "fetched_remote_sports_data": False,
            "used_pybaseball": False,
            "wrote_db": False,
            "wrote_data_runtime_logs_or_outputs": False,
            "mutated_p237_to_p246_artifacts": False,
            "computed_roi_pnl_ev_kelly": False,
            "created_betting_recommendations": False,
            "created_live_production_or_real_betting_output": False,
        },
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    status_path = output_dir / STATUS_JSON_FILENAME
    steps_path = output_dir / STEPS_CSV_FILENAME
    report_path = output_dir / REPORT_MD_FILENAME
    _stable_json_write(status_path, status)
    _write_csv(steps_path, step_rows)
    _write_markdown(report_path, status)

    return PaperToolchainStatusResult(
        status=status,
        step_rows=tuple(step_rows),
        output_paths={
            "toolchain_status_json": _display_path(status_path),
            "toolchain_steps_csv": _display_path(steps_path),
            "toolchain_report_md": _display_path(report_path),
        },
    )
