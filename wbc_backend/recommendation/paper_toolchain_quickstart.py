"""Deterministic local operator quickstart export for the P239-P250 paper toolchain.

This module only reads existing committed P249 launch index and P250 CLI
help smoke artifacts. It does not execute any P237-P250 operator script,
even with `--help`, does not contact providers, does not fetch remote
sports data, and does not write data, DB, runtime, or log state. It
renders safe local viewing references and safe `--help` command text
(derived from already-recorded P250 results, never re-executed here) so
operators can navigate the committed paper toolchain without running any
workflow, query, diff, gate, status, dashboard, or index command.
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

DEFAULT_INDEX_SUMMARY_JSON = ROOT / "report" / "p249a_paper_toolchain_index" / "index_summary.json"
DEFAULT_INDEX_LINKS_CSV = ROOT / "report" / "p249a_paper_toolchain_index" / "index_links.csv"
DEFAULT_CLI_HELP_SUMMARY_JSON = ROOT / "report" / "p250a_paper_toolchain_cli_help" / "cli_help_summary.json"
DEFAULT_CLI_HELP_ENTRIES_CSV = ROOT / "report" / "p250a_paper_toolchain_cli_help" / "cli_help_entries.csv"
DEFAULT_OUTPUT_DIR = ROOT / "report" / "p251a_paper_toolchain_quickstart"
DEFAULT_GENERATED_AT_UTC = None

SUMMARY_JSON_FILENAME = "quickstart_summary.json"
COMMANDS_CSV_FILENAME = "quickstart_commands.csv"
REPORT_MD_FILENAME = "quickstart.md"

COMMAND_CSV_FIELDNAMES = [
    "command_id",
    "category",
    "title",
    "command_text",
    "references_path",
    "safety_level",
    "executes_workflow",
    "writes_outputs",
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

WHAT_NOT_TO_RUN = (
    "Do not run any P237-P250 script without --help; workflow, query, diff, gate, status, "
    "dashboard, and index commands regenerate artifacts and are out of scope here.",
    "Do not pass --output-dir or any other write flag when exploring scripts locally.",
    "Do not contact odds/market providers, MLB Stats API, or any external network source.",
    "Do not use pybaseball or any live/paid data fetch.",
    "Do not compute ROI, P&L, EV, Kelly, bankroll, or compounding from these artifacts.",
    "Do not treat any status, link, or help availability as a betting recommendation or "
    "predictive signal.",
)

FORBIDDEN_COMMAND_TOKENS = (
    "output-dir",
    "provider",
    "API",
    "DB",
    "pybaseball",
    "fetch",
    "ROI",
    "EV",
    "Kelly",
    "real betting",
    "production",
    "live",
    "recommended_bet",
)

REQUIRED_INDEX_SUMMARY_FIELDS = (
    "index_status",
    "dashboard_status",
    "toolchain_status",
    "latest_gate_status",
    "output_files",
)
REQUIRED_CLI_HELP_SUMMARY_FIELDS = ("smoke_status", "python_executable")


class PaperToolchainQuickstartError(RuntimeError):
    """Raised when quickstart inputs are missing, corrupt, or a generated command is unsafe."""


@dataclass(frozen=True)
class PaperToolchainQuickstartResult:
    summary: dict[str, Any]
    command_rows: tuple[dict[str, Any], ...]
    output_paths: dict[str, str]


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return str(path)


def _sha256_file(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


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


def _bool_from_csv(value: Any) -> bool:
    return str(value).strip().lower() == "true"


def _read_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise PaperToolchainQuickstartError(f"{label} not found: {_display_path(path)}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PaperToolchainQuickstartError(f"{label} is not valid JSON: {_display_path(path)} ({exc})") from exc
    if not isinstance(payload, dict):
        raise PaperToolchainQuickstartError(f"{label} must decode to a JSON object: {_display_path(path)}")
    return payload


def _read_csv_rows(path: Path, label: str) -> list[dict[str, str]]:
    if not path.is_file():
        raise PaperToolchainQuickstartError(f"{label} not found: {_display_path(path)}")
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))
    except csv.Error as exc:
        raise PaperToolchainQuickstartError(f"{label} is not valid CSV: {_display_path(path)} ({exc})") from exc


def _load_index(index_summary_path: Path, index_links_path: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    summary = _read_json(index_summary_path, "index summary JSON")
    for field in REQUIRED_INDEX_SUMMARY_FIELDS:
        if field not in summary:
            raise PaperToolchainQuickstartError(f"index summary JSON missing required field: {field}")
    links = _read_csv_rows(index_links_path, "index links CSV")
    return summary, links


def _load_cli_help(
    cli_help_summary_path: Path, cli_help_entries_path: Path
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    summary = _read_json(cli_help_summary_path, "CLI help summary JSON")
    for field in REQUIRED_CLI_HELP_SUMMARY_FIELDS:
        if field not in summary:
            raise PaperToolchainQuickstartError(f"CLI help summary JSON missing required field: {field}")
    entries = _read_csv_rows(cli_help_entries_path, "CLI help entries CSV")
    return summary, entries


def _resolve_relative(base_csv_path: Path, relative_path: str) -> Path:
    return (base_csv_path.parent / relative_path).resolve()


def _check_forbidden_tokens(text: str) -> list[str]:
    return [token for token in FORBIDDEN_COMMAND_TOKENS if token in text]


def _validate_command_row(row: dict[str, Any]) -> None:
    if row["executes_workflow"] is not False:
        raise PaperToolchainQuickstartError(f"unsafe command flagged executes_workflow: {row['command_id']}")
    if row["writes_outputs"] is not False:
        raise PaperToolchainQuickstartError(f"unsafe command flagged writes_outputs: {row['command_id']}")
    text = row["command_text"]
    hits = _check_forbidden_tokens(text)
    if hits:
        raise PaperToolchainQuickstartError(
            f"unsafe command contains forbidden token(s) {hits}: {row['command_id']}"
        )
    if row["category"] == "help":
        if not text.rstrip().endswith("--help"):
            raise PaperToolchainQuickstartError(f"help command missing trailing --help flag: {row['command_id']}")
    else:
        if not text.startswith("view: "):
            raise PaperToolchainQuickstartError(
                f"viewing command missing safe 'view:' prefix: {row['command_id']}"
            )


def _viewing_row(
    *, command_id: str, category: str, title: str, references_path: str, target_present: bool, notes: str = ""
) -> dict[str, Any]:
    row = {
        "command_id": command_id,
        "category": category,
        "title": title,
        "command_text": f"view: {references_path}",
        "references_path": references_path,
        "safety_level": "view_only",
        "executes_workflow": False,
        "writes_outputs": False,
        "notes": notes if notes else ("" if target_present else "missing target"),
    }
    _validate_command_row(row)
    return row


def _help_row(
    *,
    command_id: str,
    title: str,
    python_executable: str,
    script_path: str,
    script_present: bool,
    notes: str = "",
) -> dict[str, Any]:
    row = {
        "command_id": command_id,
        "category": "help",
        "title": title,
        "command_text": f"{python_executable} {script_path} --help",
        "references_path": script_path,
        "safety_level": "help_only",
        "executes_workflow": False,
        "writes_outputs": False,
        "notes": notes if notes else ("" if script_present else "script not present in P250 smoke"),
    }
    _validate_command_row(row)
    return row


def _write_csv(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COMMAND_CSV_FIELDNAMES, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _format_cell(row.get(field, "")) for field in COMMAND_CSV_FIELDNAMES})


def _write_markdown(path: Path, summary: dict[str, Any], rows: tuple[dict[str, Any], ...]) -> None:
    lines = [
        "# P251-A Paper Toolchain Operator Quickstart",
        "",
        "## Summary",
        f"- Generated at UTC: {summary['generated_at_utc']}",
        f"- Quickstart status: {summary['quickstart_status']}",
        f"- Local viewing links: {summary['local_link_count']}",
        f"- Safe help commands: {summary['help_command_count']}",
        f"- Total commands: {summary['command_count']}",
        f"- Warnings: {summary['warning_count']}",
        f"- Failures: {summary['failure_count']}",
        "",
        "## Start Here",
    ]
    start_here_rows = [row for row in rows if row["category"] == "start_here"]
    other_view_rows = [row for row in rows if row["category"] not in ("start_here", "help")]
    help_rows = [row for row in rows if row["category"] == "help"]

    for row in start_here_rows:
        lines.append(f"- {row['title']}: `{row['references_path']}`")

    lines.extend(["", "## Safe Viewing Links"])
    for row in other_view_rows:
        note = f" ({row['notes']})" if row["notes"] else ""
        lines.append(f"- [{row['category']}] {row['title']}: `{row['references_path']}`{note}")

    lines.extend(["", "## Safe Help Commands"])
    for row in help_rows:
        note = f" ({row['notes']})" if row["notes"] else ""
        lines.append(f"- {row['title']}: `{row['command_text']}`{note}")

    lines.extend(["", "## What Not To Run"])
    for item in WHAT_NOT_TO_RUN:
        lines.append(f"- {item}")

    lines.extend(["", "## Current Status Snapshot"])
    lines.append(f"- P249 index_status: {summary['index_status']}")
    lines.append(f"- P248 dashboard_status: {summary['dashboard_status']}")
    lines.append(f"- P247 toolchain_status: {summary['toolchain_status']}")
    lines.append(f"- P246 latest_gate_status: {summary['latest_gate_status']}")
    lines.append(f"- P250 cli_help_smoke_status: {summary['cli_help_smoke_status']}")

    lines.extend(["", "## Safety Boundaries"])
    for key, value in summary["no_side_effects"].items():
        lines.append(f"- {key}: {value}")

    lines.extend(["", "## Limitations"])
    for label in summary["limitation_labels"]:
        lines.append(f"- {label}")

    lines.extend(["", "## Not Claims"])
    for claim in NOT_CLAIMS:
        lines.append(f"- {claim}")

    if summary["warnings"] or summary["failures"]:
        lines.extend(["", "## Warnings / Failures"])
        for warning in summary["warnings"]:
            lines.append(f"- Warning: {warning}")
        for failure in summary["failures"]:
            lines.append(f"- Failure: {failure}")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_paper_toolchain_quickstart(
    *,
    index_summary_json: Path = DEFAULT_INDEX_SUMMARY_JSON,
    index_links_csv: Path = DEFAULT_INDEX_LINKS_CSV,
    cli_help_summary_json: Path = DEFAULT_CLI_HELP_SUMMARY_JSON,
    cli_help_entries_csv: Path = DEFAULT_CLI_HELP_ENTRIES_CSV,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    generated_at_utc: str | None = DEFAULT_GENERATED_AT_UTC,
) -> PaperToolchainQuickstartResult:
    index_summary_json = Path(index_summary_json)
    index_links_csv = Path(index_links_csv)
    cli_help_summary_json = Path(cli_help_summary_json)
    cli_help_entries_csv = Path(cli_help_entries_csv)
    output_dir = Path(output_dir)
    generated_at_utc = resolve_generated_at_utc(generated_at_utc)

    index_summary, index_links = _load_index(index_summary_json, index_links_csv)
    cli_help_summary, cli_help_entries = _load_cli_help(cli_help_summary_json, cli_help_entries_csv)

    warnings: list[str] = []
    failures: list[str] = []

    index_status = index_summary.get("index_status")
    dashboard_status = index_summary.get("dashboard_status")
    toolchain_status = index_summary.get("toolchain_status")
    latest_gate_status = index_summary.get("latest_gate_status")
    cli_help_smoke_status = cli_help_summary.get("smoke_status")
    python_executable = cli_help_summary.get("python_executable", "")

    for label, status in (
        ("P249 index_status", index_status),
        ("P248 dashboard_status", dashboard_status),
        ("P247 toolchain_status", toolchain_status),
        ("P246 latest_gate_status", latest_gate_status),
        ("P250 cli_help_smoke_status", cli_help_smoke_status),
    ):
        if status != "PASS":
            failures.append(f"{label} is {status!r}, expected PASS")

    rows: list[dict[str, Any]] = []

    index_output_files = index_summary.get("output_files", {})
    index_html_relative = index_output_files.get("index_html")
    if index_html_relative:
        index_html_path = (ROOT / index_html_relative).resolve()
        target_present = index_html_path.is_file()
        if not target_present:
            failures.append(f"missing configured local link: start_here_index ({index_html_relative})")
        rows.append(
            _viewing_row(
                command_id="start_here_index",
                category="start_here",
                title="P249 paper toolchain launch index",
                references_path=str(index_html_relative),
                target_present=target_present,
            )
        )

    for link_row in index_links:
        if link_row.get("category") == "scripts":
            continue
        link_id = link_row.get("link_id", "")
        relative_path = link_row.get("relative_path", "")
        resolved = _resolve_relative(index_links_csv, relative_path)
        references_path = _display_path(resolved)
        csv_target_exists = _bool_from_csv(link_row.get("target_exists", ""))
        target_present = csv_target_exists and resolved.is_file()
        if not target_present:
            failures.append(f"missing configured local link: {link_id} ({references_path})")
        rows.append(
            _viewing_row(
                command_id=f"view_{link_id}",
                category=link_row.get("category", "viewing"),
                title=link_row.get("title", link_id),
                references_path=references_path,
                target_present=target_present,
            )
        )

    cli_help_output_dir = cli_help_summary_json.parent
    for suffix, title, filename in (
        ("summary", "P250 CLI help summary JSON", cli_help_summary_json.name),
        ("entries", "P250 CLI help entries CSV", cli_help_entries_csv.name),
        ("report", "P250 CLI help report Markdown", "cli_help_report.md"),
    ):
        candidate = cli_help_output_dir / filename
        target_present = candidate.is_file()
        references_path = _display_path(candidate)
        if not target_present:
            failures.append(f"missing configured local link: p250_cli_help_{suffix} ({references_path})")
        rows.append(
            _viewing_row(
                command_id=f"view_p250_cli_help_{suffix}",
                category="help_smoke",
                title=title,
                references_path=references_path,
                target_present=target_present,
            )
        )

    for entry in cli_help_entries:
        script_id = entry.get("script_id", "")
        step_id = entry.get("step_id", "")
        script_path = entry.get("script_path", "")
        script_present = _bool_from_csv(entry.get("script_present", ""))
        if not script_present:
            failures.append(f"missing configured help entry: {script_id} ({script_path})")
        rows.append(
            _help_row(
                command_id=f"help_{script_id}",
                title=f"{step_id} {script_id} --help",
                python_executable=python_executable,
                script_path=script_path,
                script_present=script_present,
            )
        )

    local_link_count = sum(1 for row in rows if row["safety_level"] == "view_only")
    help_command_count = sum(1 for row in rows if row["safety_level"] == "help_only")
    command_count = len(rows)

    quickstart_status = "FAIL" if failures else ("WARN" if warnings else "PASS")

    input_paths = {
        "index_summary_json": _display_path(index_summary_json),
        "index_links_csv": _display_path(index_links_csv),
        "cli_help_summary_json": _display_path(cli_help_summary_json),
        "cli_help_entries_csv": _display_path(cli_help_entries_csv),
    }
    input_hashes = {
        "index_summary_json": _sha256_file(index_summary_json),
        "index_links_csv": _sha256_file(index_links_csv),
        "cli_help_summary_json": _sha256_file(cli_help_summary_json),
        "cli_help_entries_csv": _sha256_file(cli_help_entries_csv),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / SUMMARY_JSON_FILENAME
    commands_path = output_dir / COMMANDS_CSV_FILENAME
    report_path = output_dir / REPORT_MD_FILENAME

    output_files = {
        "quickstart_summary_json": _display_path(summary_path),
        "quickstart_commands_csv": _display_path(commands_path),
        "quickstart_report_md": _display_path(report_path),
    }

    summary: dict[str, Any] = {
        "generated_at_utc": generated_at_utc,
        "quickstart_status": quickstart_status,
        "input_paths": dict(sorted(input_paths.items())),
        "input_hashes": dict(sorted(input_hashes.items())),
        "index_status": index_status,
        "dashboard_status": dashboard_status,
        "toolchain_status": toolchain_status,
        "latest_gate_status": latest_gate_status,
        "cli_help_smoke_status": cli_help_smoke_status,
        "python_executable": python_executable,
        "local_link_count": local_link_count,
        "help_command_count": help_command_count,
        "command_count": command_count,
        "warning_count": len(warnings),
        "failure_count": len(failures),
        "output_files": output_files,
        "limitation_labels": list(LIMITATION_LABELS),
        "no_side_effects": {
            "read_existing_p249_and_p250_artifacts_only": True,
            "executed_p239_to_p250_scripts": False,
            "executed_help_calls": False,
            "executed_workflow_query_diff_gate_status_dashboard_index_commands": False,
            "regenerated_predictions_or_artifacts": False,
            "mutated_p237_to_p250_source_artifacts": False,
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
    }

    _stable_json_write(summary_path, summary)
    _write_csv(commands_path, rows)
    _write_markdown(report_path, summary, tuple(rows))

    return PaperToolchainQuickstartResult(
        summary=summary,
        command_rows=tuple(rows),
        output_paths=output_files,
    )
