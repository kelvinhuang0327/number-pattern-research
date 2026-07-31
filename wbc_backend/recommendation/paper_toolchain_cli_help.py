"""Deterministic local CLI `--help` smoke export for P239-P249 paper scripts.

This module runs only `<python> <script> --help` against a fixed, configured
list of committed operator scripts. It does not execute workflow, query,
diff, gate, status, dashboard, or index commands, does not contact
providers, does not fetch remote sports data, and does not write data, DB,
runtime, or log state. It captures exit code, help text hash, line count,
and basic usage flag presence so operators can confirm the paper toolchain
CLIs remain discoverable without regenerating any artifacts.
"""
from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable

from wbc_backend.recommendation.paper_strategy_learning import resolve_generated_at_utc


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_OUTPUT_DIR = ROOT / "report" / "p250a_paper_toolchain_cli_help"
DEFAULT_GENERATED_AT_UTC = None
DEFAULT_TIMEOUT_SECONDS = 10

SUMMARY_JSON_FILENAME = "cli_help_summary.json"
ENTRIES_CSV_FILENAME = "cli_help_entries.csv"
REPORT_MD_FILENAME = "cli_help_report.md"

ENTRY_CSV_FIELDNAMES = [
    "script_id",
    "step_id",
    "script_path",
    "script_present",
    "help_exit_code",
    "timed_out",
    "help_sha256",
    "help_line_count",
    "has_usage",
    "has_quiet",
    "has_output_dir",
    "status",
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


class PaperToolchainCliHelpError(RuntimeError):
    """Raised when the CLI help smoke configuration itself is invalid."""


@dataclass(frozen=True)
class ScriptSpec:
    script_id: str
    step_id: str
    script_path: Path


@dataclass(frozen=True)
class PaperToolchainCliHelpResult:
    summary: dict[str, Any]
    entry_rows: tuple[dict[str, str], ...]
    output_paths: dict[str, str]


DEFAULT_SCRIPT_SPECS = (
    ScriptSpec("run_mlb_paper_strategy_workflow", "P239", ROOT / "scripts" / "run_mlb_paper_strategy_workflow.py"),
    ScriptSpec(
        "inspect_mlb_paper_strategy_workflow",
        "P240",
        ROOT / "scripts" / "inspect_mlb_paper_strategy_workflow.py",
    ),
    ScriptSpec(
        "build_mlb_paper_strategy_workflow_review_pack",
        "P241",
        ROOT / "scripts" / "build_mlb_paper_strategy_workflow_review_pack.py",
    ),
    ScriptSpec(
        "run_mlb_paper_strategy_workflow_bundle",
        "P242",
        ROOT / "scripts" / "run_mlb_paper_strategy_workflow_bundle.py",
    ),
    ScriptSpec(
        "build_mlb_paper_artifact_catalog", "P243", ROOT / "scripts" / "build_mlb_paper_artifact_catalog.py"
    ),
    ScriptSpec(
        "query_mlb_paper_artifact_catalog", "P244", ROOT / "scripts" / "query_mlb_paper_artifact_catalog.py"
    ),
    ScriptSpec(
        "diff_mlb_paper_artifact_catalogs", "P245", ROOT / "scripts" / "diff_mlb_paper_artifact_catalogs.py"
    ),
    ScriptSpec("check_mlb_paper_artifact_diff", "P246", ROOT / "scripts" / "check_mlb_paper_artifact_diff.py"),
    ScriptSpec("build_mlb_paper_toolchain_status", "P247", ROOT / "scripts" / "build_mlb_paper_toolchain_status.py"),
    ScriptSpec(
        "build_mlb_paper_toolchain_dashboard", "P248", ROOT / "scripts" / "build_mlb_paper_toolchain_dashboard.py"
    ),
    ScriptSpec("build_mlb_paper_toolchain_index", "P249", ROOT / "scripts" / "build_mlb_paper_toolchain_index.py"),
)


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return str(path)


def _sha256_bytes(data: bytes) -> str:
    return sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _format_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return str(value)


def _stable_json_write(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _decode(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _help_env() -> dict[str, str]:
    env = dict(os.environ)
    env["COLUMNS"] = "100"
    env.pop("LINES", None)
    return env


def _run_help(
    python_executable: str, script_path: Path, timeout_seconds: int
) -> tuple[int | None, bool, str, str]:
    """Run `<python_executable> <script_path> --help` only. No other args are passed."""
    try:
        completed = subprocess.run(
            [python_executable, str(script_path), "--help"],
            cwd=str(ROOT),
            env=_help_env(),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        return None, True, _decode(exc.stdout), _decode(exc.stderr)
    except OSError as exc:
        return None, False, "", str(exc)
    return completed.returncode, False, _decode(completed.stdout), _decode(completed.stderr)


def _entry_for_spec(
    spec: ScriptSpec, *, python_executable: str, timeout_seconds: int
) -> tuple[dict[str, Any], dict[str, str], str | None, str | None]:
    """Returns (entry_dict, csv_row, warning_or_None, failure_or_None)."""
    script_present = spec.script_path.is_file()
    display_path = _display_path(spec.script_path)

    if not script_present:
        entry = {
            "script_id": spec.script_id,
            "step_id": spec.step_id,
            "script_path": display_path,
            "script_present": False,
            "help_exit_code": None,
            "timed_out": False,
            "help_sha256": "",
            "help_line_count": 0,
            "has_usage": False,
            "has_quiet": False,
            "has_output_dir": False,
            "status": "FAIL",
            "notes": f"script not found: {display_path}",
        }
        failure = f"{spec.step_id} {spec.script_id}: script not found: {display_path}"
        row = {field: entry[field] for field in ENTRY_CSV_FIELDNAMES}
        return entry, row, None, failure

    exit_code, timed_out, stdout_text, stderr_text = _run_help(
        python_executable, spec.script_path, timeout_seconds
    )

    if timed_out:
        entry = {
            "script_id": spec.script_id,
            "step_id": spec.step_id,
            "script_path": display_path,
            "script_present": True,
            "help_exit_code": None,
            "timed_out": True,
            "help_sha256": "",
            "help_line_count": 0,
            "has_usage": False,
            "has_quiet": False,
            "has_output_dir": False,
            "status": "FAIL",
            "notes": f"help call timed out after {timeout_seconds}s",
        }
        failure = f"{spec.step_id} {spec.script_id}: help call timed out after {timeout_seconds}s"
        row = {field: entry[field] for field in ENTRY_CSV_FIELDNAMES}
        return entry, row, None, failure

    if exit_code is None:
        message = stderr_text.strip() or "failed to execute python interpreter"
        entry = {
            "script_id": spec.script_id,
            "step_id": spec.step_id,
            "script_path": display_path,
            "script_present": True,
            "help_exit_code": None,
            "timed_out": False,
            "help_sha256": "",
            "help_line_count": 0,
            "has_usage": False,
            "has_quiet": False,
            "has_output_dir": False,
            "status": "FAIL",
            "notes": message,
        }
        failure = f"{spec.step_id} {spec.script_id}: {message}"
        row = {field: entry[field] for field in ENTRY_CSV_FIELDNAMES}
        return entry, row, None, failure

    help_bytes = stdout_text.encode("utf-8")
    help_sha256 = _sha256_bytes(help_bytes)
    help_line_count = len(stdout_text.splitlines())
    lowered = stdout_text.lower()
    has_usage = "usage:" in lowered
    has_quiet = "--quiet" in stdout_text
    has_output_dir = "--output-dir" in stdout_text

    if exit_code != 0:
        entry = {
            "script_id": spec.script_id,
            "step_id": spec.step_id,
            "script_path": display_path,
            "script_present": True,
            "help_exit_code": exit_code,
            "timed_out": False,
            "help_sha256": help_sha256,
            "help_line_count": help_line_count,
            "has_usage": has_usage,
            "has_quiet": has_quiet,
            "has_output_dir": has_output_dir,
            "status": "FAIL",
            "notes": f"help exit code {exit_code}",
        }
        failure = f"{spec.step_id} {spec.script_id}: help exit code {exit_code}"
        row = {field: entry[field] for field in ENTRY_CSV_FIELDNAMES}
        return entry, row, None, failure

    missing_flags = []
    if not has_usage:
        missing_flags.append("usage line")
    if not has_quiet:
        missing_flags.append("--quiet flag")
    if not has_output_dir:
        missing_flags.append("--output-dir flag")

    status = "WARN" if missing_flags else "PASS"
    notes = f"help output missing: {', '.join(missing_flags)}" if missing_flags else ""
    warning = (
        f"{spec.step_id} {spec.script_id}: help output missing {', '.join(missing_flags)}"
        if missing_flags
        else None
    )

    entry = {
        "script_id": spec.script_id,
        "step_id": spec.step_id,
        "script_path": display_path,
        "script_present": True,
        "help_exit_code": exit_code,
        "timed_out": False,
        "help_sha256": help_sha256,
        "help_line_count": help_line_count,
        "has_usage": has_usage,
        "has_quiet": has_quiet,
        "has_output_dir": has_output_dir,
        "status": status,
        "notes": notes,
    }
    row = {field: entry[field] for field in ENTRY_CSV_FIELDNAMES}
    return entry, row, warning, None


def _write_csv(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=ENTRY_CSV_FIELDNAMES, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _format_cell(row.get(field, "")) for field in ENTRY_CSV_FIELDNAMES})


def _write_markdown(path: Path, summary: dict[str, Any], entries: tuple[dict[str, Any], ...]) -> None:
    lines = [
        "# P250-A Paper Toolchain CLI Help Smoke",
        "",
        "## Summary",
        f"- Generated at UTC: {summary['generated_at_utc']}",
        f"- Smoke status: {summary['smoke_status']}",
        f"- Scripts configured: {summary['script_count']}",
        f"- Help pass: {summary['help_pass_count']}",
        f"- Help fail: {summary['help_fail_count']}",
        f"- Timeouts: {summary['timeout_count']}",
        f"- Missing scripts: {summary['missing_script_count']}",
        f"- Python executable: {summary['python_executable']}",
        f"- Timeout seconds: {summary['timeout_seconds']}",
        "",
        "## Help Smoke Results",
    ]
    for entry in entries:
        lines.append(
            "- {step_id} {script_id}: {status}; exit_code={exit_code}; timed_out={timed_out}; "
            "lines={lines}; usage={usage}; quiet={quiet}; output_dir={output_dir}".format(
                step_id=entry["step_id"],
                script_id=entry["script_id"],
                status=entry["status"],
                exit_code=entry["help_exit_code"],
                timed_out=entry["timed_out"],
                lines=entry["help_line_count"],
                usage=entry["has_usage"],
                quiet=entry["has_quiet"],
                output_dir=entry["has_output_dir"],
            )
        )

    lines.extend(["", "## Scripts"])
    for entry in entries:
        lines.append(f"- {entry['step_id']} {entry['script_id']}: `{entry['script_path']}`")

    lines.extend(["", "## Hashes"])
    for entry in entries:
        lines.append(
            f"- {entry['step_id']} {entry['script_id']}: "
            f"input_script_sha256={summary['input_script_hashes'].get(entry['script_id'], '')}; "
            f"help_output_sha256={entry['help_sha256']}"
        )

    lines.extend(["", "## Warnings / Failures"])
    if not summary["warnings"] and not summary["failures"]:
        lines.append("- None")
    for warning in summary["warnings"]:
        lines.append(f"- Warning: {warning}")
    for failure in summary["failures"]:
        lines.append(f"- Failure: {failure}")

    lines.extend(["", "## Safety Boundaries"])
    for key, value in summary["no_side_effects"].items():
        lines.append(f"- {key}: {value}")

    lines.extend(["", "## Limitations"])
    for label in summary["limitation_labels"]:
        lines.append(f"- {label}")

    lines.extend(["", "## Not Claims"])
    for claim in NOT_CLAIMS:
        lines.append(f"- {claim}")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_paper_toolchain_cli_help(
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    generated_at_utc: str | None = DEFAULT_GENERATED_AT_UTC,
    python_executable: str = sys.executable,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    script_specs: Iterable[ScriptSpec] = DEFAULT_SCRIPT_SPECS,
) -> PaperToolchainCliHelpResult:
    if timeout_seconds <= 0:
        raise PaperToolchainCliHelpError(f"timeout_seconds must be positive, got {timeout_seconds}")

    output_dir = Path(output_dir)
    generated_at_utc = resolve_generated_at_utc(generated_at_utc)
    script_specs = tuple(script_specs)

    entries: list[dict[str, Any]] = []
    rows: list[dict[str, str]] = []
    warnings: list[str] = []
    failures: list[str] = []
    help_pass_count = 0
    help_fail_count = 0
    timeout_count = 0
    missing_script_count = 0

    for spec in script_specs:
        entry, row, warning, failure = _entry_for_spec(
            spec, python_executable=python_executable, timeout_seconds=timeout_seconds
        )
        entries.append(entry)
        rows.append(row)
        if warning:
            warnings.append(warning)
        if failure:
            failures.append(failure)

        if not entry["script_present"]:
            missing_script_count += 1
        elif entry["timed_out"]:
            timeout_count += 1
        elif entry["status"] == "FAIL":
            help_fail_count += 1
        else:
            help_pass_count += 1

    input_script_hashes = {
        entry["script_id"]: _sha256_file(ROOT / entry["script_path"]) if entry["script_present"] else ""
        for entry in entries
    }
    help_output_hashes = {entry["script_id"]: entry["help_sha256"] for entry in entries}

    smoke_status = "FAIL" if failures else "PASS"

    summary: dict[str, Any] = {
        "generated_at_utc": generated_at_utc,
        "smoke_status": smoke_status,
        "script_count": len(script_specs),
        "help_pass_count": help_pass_count,
        "help_fail_count": help_fail_count,
        "timeout_count": timeout_count,
        "missing_script_count": missing_script_count,
        "input_script_hashes": dict(sorted(input_script_hashes.items())),
        "help_output_hashes": dict(sorted(help_output_hashes.items())),
        "warning_count": len(warnings),
        "failure_count": len(failures),
        "limitation_labels": list(LIMITATION_LABELS),
        "no_side_effects": {
            "executed_only_help_calls": True,
            "executed_workflow_query_diff_gate_status_dashboard_index_commands": False,
            "regenerated_predictions_or_artifacts": False,
            "mutated_p237_to_p249_source_artifacts": False,
            "contacted_providers": False,
            "fetched_remote_sports_data": False,
            "used_pybaseball": False,
            "installed_dependencies": False,
            "modified_virtualenvs": False,
            "wrote_db": False,
            "wrote_data_runtime_or_log_files": False,
            "computed_roi_pnl_ev_kelly": False,
            "created_betting_recommendations_or_rankings": False,
            "created_live_production_or_real_betting_output": False,
        },
        "warnings": sorted(warnings),
        "failures": sorted(failures),
        "python_executable": python_executable,
        "timeout_seconds": timeout_seconds,
        "configured_scripts": [
            {"script_id": entry["script_id"], "step_id": entry["step_id"], "script_path": entry["script_path"]}
            for entry in entries
        ],
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / SUMMARY_JSON_FILENAME
    entries_path = output_dir / ENTRIES_CSV_FILENAME
    report_path = output_dir / REPORT_MD_FILENAME
    _stable_json_write(summary_path, summary)
    _write_csv(entries_path, rows)
    _write_markdown(report_path, summary, tuple(entries))

    return PaperToolchainCliHelpResult(
        summary=summary,
        entry_rows=tuple(rows),
        output_paths={
            "cli_help_summary_json": _display_path(summary_path),
            "cli_help_entries_csv": _display_path(entries_path),
            "cli_help_report_md": _display_path(report_path),
        },
    )
