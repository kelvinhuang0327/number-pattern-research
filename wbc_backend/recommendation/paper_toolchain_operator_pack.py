"""Deterministic local operator pack manifest export for the P248-P251 paper toolchain.

This module only reads existing committed P248 dashboard, P249 launch
index, P250 CLI help smoke, and P251 quickstart artifacts. It does not
execute any P237-P251 operator script, does not contact providers, does
not fetch remote sports data, and does not write data, DB, runtime, or
log state. It renders a manifest of safe local viewing files plus
pass-through references to P249's existing local links and P251's
existing safe `--help`/viewing commands (never re-executed here) so
reviewers can verify the current offline paper-only operator surfaces.
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

DEFAULT_DASHBOARD_SUMMARY_JSON = ROOT / "report" / "p248a_paper_toolchain_dashboard" / "dashboard_summary.json"
DEFAULT_INDEX_SUMMARY_JSON = ROOT / "report" / "p249a_paper_toolchain_index" / "index_summary.json"
DEFAULT_INDEX_LINKS_CSV = ROOT / "report" / "p249a_paper_toolchain_index" / "index_links.csv"
DEFAULT_CLI_HELP_SUMMARY_JSON = ROOT / "report" / "p250a_paper_toolchain_cli_help" / "cli_help_summary.json"
DEFAULT_QUICKSTART_SUMMARY_JSON = ROOT / "report" / "p251a_paper_toolchain_quickstart" / "quickstart_summary.json"
DEFAULT_QUICKSTART_COMMANDS_CSV = ROOT / "report" / "p251a_paper_toolchain_quickstart" / "quickstart_commands.csv"
DEFAULT_QUICKSTART_MD = ROOT / "report" / "p251a_paper_toolchain_quickstart" / "quickstart.md"
DEFAULT_OUTPUT_DIR = ROOT / "report" / "p252a_paper_toolchain_operator_pack"
DEFAULT_GENERATED_AT_UTC = None

SUMMARY_JSON_FILENAME = "operator_pack_summary.json"
FILES_CSV_FILENAME = "operator_pack_files.csv"
REPORT_MD_FILENAME = "operator_pack.md"

FILE_CSV_FIELDNAMES = [
    "file_id",
    "category",
    "title",
    "relative_path",
    "target_exists",
    "sha256",
    "source_artifact",
    "safe_to_view",
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

FORBIDDEN_REFERENCE_TOKENS = (
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

REQUIRED_DASHBOARD_SUMMARY_FIELDS = ("dashboard_status", "output_files")
REQUIRED_INDEX_SUMMARY_FIELDS = ("index_status", "output_files")
REQUIRED_CLI_HELP_SUMMARY_FIELDS = ("smoke_status",)
REQUIRED_QUICKSTART_SUMMARY_FIELDS = ("quickstart_status",)


class PaperToolchainOperatorPackError(RuntimeError):
    """Raised when operator pack inputs are missing, corrupt, or a reference is unsafe."""


@dataclass(frozen=True)
class PaperToolchainOperatorPackResult:
    summary: dict[str, Any]
    file_rows: tuple[dict[str, Any], ...]
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
        raise PaperToolchainOperatorPackError(f"{label} not found: {_display_path(path)}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PaperToolchainOperatorPackError(
            f"{label} is not valid JSON: {_display_path(path)} ({exc})"
        ) from exc
    if not isinstance(payload, dict):
        raise PaperToolchainOperatorPackError(f"{label} must decode to a JSON object: {_display_path(path)}")
    return payload


def _read_csv_rows(path: Path, label: str) -> list[dict[str, str]]:
    if not path.is_file():
        raise PaperToolchainOperatorPackError(f"{label} not found: {_display_path(path)}")
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))
    except csv.Error as exc:
        raise PaperToolchainOperatorPackError(f"{label} is not valid CSV: {_display_path(path)} ({exc})") from exc


def _read_text(path: Path, label: str) -> str:
    if not path.is_file():
        raise PaperToolchainOperatorPackError(f"{label} not found: {_display_path(path)}")
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise PaperToolchainOperatorPackError(f"{label} is not valid UTF-8 text: {_display_path(path)} ({exc})") from exc


def _check_forbidden_tokens(text: str) -> list[str]:
    return [token for token in FORBIDDEN_REFERENCE_TOKENS if token in text]


def _file_row(
    *,
    file_id: str,
    category: str,
    title: str,
    path: Path,
    source_artifact: str,
    notes: str = "",
) -> dict[str, Any]:
    target_exists = path.is_file()
    row = {
        "file_id": file_id,
        "category": category,
        "title": title,
        "relative_path": _display_path(path),
        "target_exists": target_exists,
        "sha256": _sha256_file(path) if target_exists else "",
        "source_artifact": source_artifact,
        "safe_to_view": True,
        "notes": notes if notes else ("" if target_exists else "missing target"),
    }
    return row


def _write_csv(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FILE_CSV_FIELDNAMES, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _format_cell(row.get(field, "")) for field in FILE_CSV_FIELDNAMES})


def _write_markdown(
    path: Path,
    summary: dict[str, Any],
    rows: tuple[dict[str, Any], ...],
    index_links: list[dict[str, str]],
    index_links_csv_path: Path,
    quickstart_rows: list[dict[str, str]],
) -> None:
    lines = [
        "# P252-A Paper Toolchain Operator Pack",
        "",
        "## Summary",
        f"- Generated at UTC: {summary['generated_at_utc']}",
        f"- Operator pack status: {summary['operator_pack_status']}",
        f"- Pack file count: {summary['file_count']}",
        f"- P249 local link count (pass-through): {summary['local_link_count']}",
        f"- P251 command count (pass-through): {summary['command_count']}",
        f"- Warnings: {summary['warning_count']}",
        f"- Failures: {summary['failure_count']}",
        "",
        "## Pack Contents",
    ]
    for row in rows:
        note = f" ({row['notes']})" if row["notes"] else ""
        lines.append(f"- [{row['category']}] {row['title']}: `{row['relative_path']}`{note}")

    lines.extend(["", "## Status Snapshot"])
    lines.append(f"- P248 dashboard_status: {summary['dashboard_status']}")
    lines.append(f"- P249 index_status: {summary['index_status']}")
    lines.append(f"- P250 cli_help_smoke_status: {summary['cli_help_smoke_status']}")
    lines.append(f"- P251 quickstart_status: {summary['quickstart_status']}")

    lines.extend(["", "## Safe Viewing Files", "", "P249 local links (pass-through, not re-executed):"])
    for link in index_links:
        if link.get("category") == "scripts":
            continue
        relative_path = link.get("relative_path", "")
        resolved = (index_links_csv_path.parent / relative_path).resolve()
        lines.append(f"- [{link.get('category', 'viewing')}] {link.get('title', '')}: `view: {_display_path(resolved)}`")

    lines.extend(["", "## Safe Help / Quickstart References", "", "P251 commands (pass-through, not re-executed):"])
    for command in quickstart_rows:
        note = f" ({command['notes']})" if command.get("notes") else ""
        lines.append(f"- [{command.get('category', '')}] {command.get('title', '')}: `{command.get('command_text', '')}`{note}")

    lines.extend(["", "## Hashes"])
    for row in rows:
        lines.append(f"- {row['file_id']}: {row['sha256'] or '(missing)'}")

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


def build_paper_toolchain_operator_pack(
    *,
    dashboard_summary_json: Path = DEFAULT_DASHBOARD_SUMMARY_JSON,
    index_summary_json: Path = DEFAULT_INDEX_SUMMARY_JSON,
    index_links_csv: Path = DEFAULT_INDEX_LINKS_CSV,
    cli_help_summary_json: Path = DEFAULT_CLI_HELP_SUMMARY_JSON,
    quickstart_summary_json: Path = DEFAULT_QUICKSTART_SUMMARY_JSON,
    quickstart_commands_csv: Path = DEFAULT_QUICKSTART_COMMANDS_CSV,
    quickstart_md: Path = DEFAULT_QUICKSTART_MD,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    generated_at_utc: str | None = DEFAULT_GENERATED_AT_UTC,
) -> PaperToolchainOperatorPackResult:
    dashboard_summary_json = Path(dashboard_summary_json)
    index_summary_json = Path(index_summary_json)
    index_links_csv = Path(index_links_csv)
    cli_help_summary_json = Path(cli_help_summary_json)
    quickstart_summary_json = Path(quickstart_summary_json)
    quickstart_commands_csv = Path(quickstart_commands_csv)
    quickstart_md = Path(quickstart_md)
    output_dir = Path(output_dir)
    generated_at_utc = resolve_generated_at_utc(generated_at_utc)

    dashboard_summary = _read_json(dashboard_summary_json, "dashboard summary JSON")
    for field in REQUIRED_DASHBOARD_SUMMARY_FIELDS:
        if field not in dashboard_summary:
            raise PaperToolchainOperatorPackError(f"dashboard summary JSON missing required field: {field}")

    index_summary = _read_json(index_summary_json, "index summary JSON")
    for field in REQUIRED_INDEX_SUMMARY_FIELDS:
        if field not in index_summary:
            raise PaperToolchainOperatorPackError(f"index summary JSON missing required field: {field}")
    index_links = _read_csv_rows(index_links_csv, "index links CSV")

    cli_help_summary = _read_json(cli_help_summary_json, "CLI help summary JSON")
    for field in REQUIRED_CLI_HELP_SUMMARY_FIELDS:
        if field not in cli_help_summary:
            raise PaperToolchainOperatorPackError(f"CLI help summary JSON missing required field: {field}")

    quickstart_summary = _read_json(quickstart_summary_json, "quickstart summary JSON")
    for field in REQUIRED_QUICKSTART_SUMMARY_FIELDS:
        if field not in quickstart_summary:
            raise PaperToolchainOperatorPackError(f"quickstart summary JSON missing required field: {field}")
    quickstart_rows = _read_csv_rows(quickstart_commands_csv, "quickstart commands CSV")
    _read_text(quickstart_md, "quickstart Markdown")

    warnings: list[str] = []
    failures: list[str] = []

    dashboard_status = dashboard_summary.get("dashboard_status")
    index_status = index_summary.get("index_status")
    cli_help_smoke_status = cli_help_summary.get("smoke_status")
    quickstart_status = quickstart_summary.get("quickstart_status")

    for label, status in (
        ("P248 dashboard_status", dashboard_status),
        ("P249 index_status", index_status),
        ("P250 cli_help_smoke_status", cli_help_smoke_status),
        ("P251 quickstart_status", quickstart_status),
    ):
        if status != "PASS":
            failures.append(f"{label} is {status!r}, expected PASS")

    for command in quickstart_rows:
        text = command.get("command_text", "")
        hits = _check_forbidden_tokens(text)
        if hits:
            raise PaperToolchainOperatorPackError(
                f"unsafe pass-through quickstart command contains forbidden token(s) {hits}: "
                f"{command.get('command_id', '')}"
            )

    dashboard_output_files = dashboard_summary.get("output_files", {})
    index_output_files = index_summary.get("output_files", {})
    cli_help_dir = cli_help_summary_json.parent

    file_specs = [
        (
            "dashboard_html",
            "dashboard",
            "P248 dashboard HTML",
            ROOT / dashboard_output_files.get("dashboard_html", "does_not_exist"),
            "P248-dashboard",
        ),
        ("dashboard_summary_json", "dashboard", "P248 dashboard summary JSON", dashboard_summary_json, "P248-dashboard"),
        (
            "dashboard_sections_csv",
            "dashboard",
            "P248 dashboard sections CSV",
            ROOT / dashboard_output_files.get("dashboard_sections_csv", "does_not_exist"),
            "P248-dashboard",
        ),
        (
            "index_html",
            "index",
            "P249 launch index HTML",
            ROOT / index_output_files.get("index_html", "does_not_exist"),
            "P249-index",
        ),
        ("index_summary_json", "index", "P249 index summary JSON", index_summary_json, "P249-index"),
        ("index_links_csv", "index", "P249 index links CSV", index_links_csv, "P249-index"),
        ("cli_help_summary_json", "cli_help", "P250 CLI help summary JSON", cli_help_summary_json, "P250-cli_help"),
        (
            "cli_help_entries_csv",
            "cli_help",
            "P250 CLI help entries CSV",
            cli_help_dir / "cli_help_entries.csv",
            "P250-cli_help",
        ),
        (
            "cli_help_report_md",
            "cli_help",
            "P250 CLI help report Markdown",
            cli_help_dir / "cli_help_report.md",
            "P250-cli_help",
        ),
        (
            "quickstart_summary_json",
            "quickstart",
            "P251 quickstart summary JSON",
            quickstart_summary_json,
            "P251-quickstart",
        ),
        (
            "quickstart_commands_csv",
            "quickstart",
            "P251 quickstart commands CSV",
            quickstart_commands_csv,
            "P251-quickstart",
        ),
        ("quickstart_md", "quickstart", "P251 quickstart Markdown", quickstart_md, "P251-quickstart"),
    ]

    rows: list[dict[str, Any]] = []
    for file_id, category, title, path, source_artifact in file_specs:
        row = _file_row(file_id=file_id, category=category, title=title, path=path, source_artifact=source_artifact)
        if not row["target_exists"]:
            failures.append(f"missing configured pack file: {file_id} ({row['relative_path']})")
        rows.append(row)

    file_count = len(rows)
    local_link_count = len(index_links)
    command_count = len(quickstart_rows)

    operator_pack_status = "FAIL" if failures else ("WARN" if warnings else "PASS")

    input_paths = {
        "dashboard_summary_json": _display_path(dashboard_summary_json),
        "index_summary_json": _display_path(index_summary_json),
        "index_links_csv": _display_path(index_links_csv),
        "cli_help_summary_json": _display_path(cli_help_summary_json),
        "quickstart_summary_json": _display_path(quickstart_summary_json),
        "quickstart_commands_csv": _display_path(quickstart_commands_csv),
        "quickstart_md": _display_path(quickstart_md),
    }
    input_hashes = {
        "dashboard_summary_json": _sha256_file(dashboard_summary_json),
        "index_summary_json": _sha256_file(index_summary_json),
        "index_links_csv": _sha256_file(index_links_csv),
        "cli_help_summary_json": _sha256_file(cli_help_summary_json),
        "quickstart_summary_json": _sha256_file(quickstart_summary_json),
        "quickstart_commands_csv": _sha256_file(quickstart_commands_csv),
        "quickstart_md": _sha256_file(quickstart_md),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / SUMMARY_JSON_FILENAME
    files_path = output_dir / FILES_CSV_FILENAME
    report_path = output_dir / REPORT_MD_FILENAME

    output_files = {
        "operator_pack_summary_json": _display_path(summary_path),
        "operator_pack_files_csv": _display_path(files_path),
        "operator_pack_report_md": _display_path(report_path),
    }

    summary: dict[str, Any] = {
        "generated_at_utc": generated_at_utc,
        "operator_pack_status": operator_pack_status,
        "input_paths": dict(sorted(input_paths.items())),
        "input_hashes": dict(sorted(input_hashes.items())),
        "dashboard_status": dashboard_status,
        "index_status": index_status,
        "cli_help_smoke_status": cli_help_smoke_status,
        "quickstart_status": quickstart_status,
        "file_count": file_count,
        "local_link_count": local_link_count,
        "command_count": command_count,
        "warning_count": len(warnings),
        "failure_count": len(failures),
        "output_files": output_files,
        "limitation_labels": list(LIMITATION_LABELS),
        "no_side_effects": {
            "read_existing_p248_p249_p250_p251_artifacts_only": True,
            "executed_p239_to_p251_scripts": False,
            "executed_workflow_query_diff_gate_status_dashboard_index_help_smoke_quickstart_commands": False,
            "regenerated_predictions_or_artifacts": False,
            "mutated_p237_to_p251_source_artifacts": False,
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
    _write_csv(files_path, rows)
    _write_markdown(report_path, summary, tuple(rows), index_links, index_links_csv, quickstart_rows)

    return PaperToolchainOperatorPackResult(
        summary=summary,
        file_rows=tuple(rows),
        output_paths=output_files,
    )
