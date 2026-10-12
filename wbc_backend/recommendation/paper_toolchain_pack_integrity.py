"""Deterministic local integrity verifier for the P252 operator pack manifest.

This module only reads the committed P252 operator pack summary and files
manifest, then writes P253 integrity outputs. It does not execute any
workflow, query, diff, gate, status, dashboard, index, help-smoke,
quickstart, or operator-pack script.
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

DEFAULT_OPERATOR_PACK_SUMMARY_JSON = (
    ROOT / "report" / "p252a_paper_toolchain_operator_pack" / "operator_pack_summary.json"
)
DEFAULT_OPERATOR_PACK_FILES_CSV = (
    ROOT / "report" / "p252a_paper_toolchain_operator_pack" / "operator_pack_files.csv"
)
DEFAULT_OUTPUT_DIR = ROOT / "report" / "p253a_paper_toolchain_pack_integrity"
DEFAULT_GENERATED_AT_UTC = None

SUMMARY_JSON_FILENAME = "integrity_summary.json"
CHECKS_CSV_FILENAME = "integrity_checks.csv"
REPORT_MD_FILENAME = "integrity_report.md"

PACK_FILE_REQUIRED_FIELDS = (
    "file_id",
    "category",
    "relative_path",
    "target_exists",
    "sha256",
)

CHECK_CSV_FIELDNAMES = [
    "check_id",
    "file_id",
    "category",
    "relative_path",
    "path_safe",
    "target_exists",
    "expected_sha256",
    "actual_sha256",
    "hash_matches",
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

STATUS_FIELDS = (
    "operator_pack_status",
    "dashboard_status",
    "index_status",
    "cli_help_smoke_status",
    "quickstart_status",
)


class PaperToolchainPackIntegrityError(RuntimeError):
    """Raised when P252 integrity inputs are missing or structurally corrupt."""


@dataclass(frozen=True)
class PaperToolchainPackIntegrityResult:
    summary: dict[str, Any]
    check_rows: tuple[dict[str, Any], ...]
    output_paths: dict[str, str]


def _display_path(path: Path, repo_root: Path = ROOT) -> str:
    try:
        return str(path.resolve().relative_to(repo_root.resolve()))
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


def _read_json(path: Path, label: str, repo_root: Path) -> dict[str, Any]:
    if not path.is_file():
        raise PaperToolchainPackIntegrityError(f"{label} not found: {_display_path(path, repo_root)}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PaperToolchainPackIntegrityError(
            f"{label} is not valid JSON: {_display_path(path, repo_root)} ({exc})"
        ) from exc
    if not isinstance(payload, dict):
        raise PaperToolchainPackIntegrityError(
            f"{label} must decode to a JSON object: {_display_path(path, repo_root)}"
        )
    return payload


def _read_csv_rows(path: Path, label: str, repo_root: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise PaperToolchainPackIntegrityError(f"{label} not found: {_display_path(path, repo_root)}")
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            missing = [field for field in PACK_FILE_REQUIRED_FIELDS if field not in (reader.fieldnames or [])]
            if missing:
                joined = ", ".join(missing)
                raise PaperToolchainPackIntegrityError(f"{label} missing required column(s): {joined}")
            return list(reader)
    except csv.Error as exc:
        raise PaperToolchainPackIntegrityError(
            f"{label} is not valid CSV: {_display_path(path, repo_root)} ({exc})"
        ) from exc


def _valid_sha256(value: str) -> bool:
    return len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def _is_manifest_true(value: str) -> bool:
    return value.strip().lower() == "true"


def _safe_target(relative_path: str, repo_root: Path) -> tuple[bool, Path | None, str]:
    raw = relative_path.strip()
    if not raw:
        return False, None, "relative_path is empty"
    if raw.startswith("/"):
        return False, None, "relative_path starts with /"
    if ".." in raw:
        return False, None, "relative_path contains .."
    if "http://" in raw or "https://" in raw:
        return False, None, "relative_path contains an external URL"

    root = repo_root.resolve()
    target = (root / raw).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        return False, None, "resolved target escapes repo root"
    return True, target, ""


def _write_csv(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CHECK_CSV_FIELDNAMES, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _format_cell(row.get(field, "")) for field in CHECK_CSV_FIELDNAMES})


def _write_markdown(
    path: Path,
    summary: dict[str, Any],
    rows: tuple[dict[str, Any], ...],
) -> None:
    lines = [
        "# P253-A Paper Toolchain Pack Integrity",
        "",
        "## Summary",
        f"- Generated at UTC: {summary['generated_at_utc']}",
        f"- Integrity status: {summary['integrity_status']}",
        f"- Referenced pack files: {summary['file_count']}",
        f"- Checked files: {summary['checked_file_count']}",
        f"- Hash matches: {summary['hash_match_count']}",
        f"- Hash mismatches: {summary['hash_mismatch_count']}",
        f"- Missing files: {summary['missing_file_count']}",
        f"- Unsafe paths: {summary['unsafe_path_count']}",
        f"- Warnings: {summary['warning_count']}",
        f"- Failures: {summary['failure_count']}",
        "",
        "## Integrity Checks",
    ]
    for row in rows:
        lines.append(
            f"- {row['check_id']} {row['status']}: `{row['relative_path']}` "
            f"(safe={row['path_safe']}, exists={row['target_exists']})"
        )

    lines.extend(["", "## Hash Matches"])
    for row in rows:
        if row["hash_matches"]:
            lines.append(f"- {row['file_id']}: {row['actual_sha256']}")
    if not any(row["hash_matches"] for row in rows):
        lines.append("- None")

    lines.extend(["", "## Missing / Unsafe / Mismatch Findings"])
    findings = [row for row in rows if row["status"] != "PASS"]
    if findings:
        for row in findings:
            lines.append(f"- {row['file_id']}: {row['notes']}")
    else:
        lines.append("- None")

    lines.extend(["", "## Status Snapshot"])
    lines.append(f"- operator_pack_status: {summary['operator_pack_status']}")
    lines.append(f"- dashboard_status: {summary['dashboard_status']}")
    lines.append(f"- index_status: {summary['index_status']}")
    lines.append(f"- cli_help_smoke_status: {summary['cli_help_smoke_status']}")
    lines.append(f"- quickstart_status: {summary['quickstart_status']}")

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


def build_paper_toolchain_pack_integrity(
    *,
    operator_pack_summary_json: Path = DEFAULT_OPERATOR_PACK_SUMMARY_JSON,
    operator_pack_files_csv: Path = DEFAULT_OPERATOR_PACK_FILES_CSV,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    generated_at_utc: str | None = DEFAULT_GENERATED_AT_UTC,
    repo_root: Path = ROOT,
) -> PaperToolchainPackIntegrityResult:
    repo_root = Path(repo_root)
    operator_pack_summary_json = Path(operator_pack_summary_json)
    operator_pack_files_csv = Path(operator_pack_files_csv)
    output_dir = Path(output_dir)
    generated_at_utc = resolve_generated_at_utc(generated_at_utc)

    operator_summary = _read_json(operator_pack_summary_json, "operator pack summary JSON", repo_root)
    pack_rows = _read_csv_rows(operator_pack_files_csv, "operator pack files CSV", repo_root)

    warnings: list[str] = []
    failures: list[str] = []

    status_values: dict[str, Any] = {}
    for field in STATUS_FIELDS:
        status = operator_summary.get(field)
        status_values[field] = status
        if status != "PASS":
            failures.append(f"P252 {field} is {status!r}, expected PASS")

    summary_file_count = operator_summary.get("file_count")
    if summary_file_count != len(pack_rows):
        failures.append(
            f"P252 file_count is {summary_file_count!r}, expected operator_pack_files.csv row count {len(pack_rows)}"
        )

    check_rows: list[dict[str, Any]] = []
    checked_file_count = 0
    hash_match_count = 0
    hash_mismatch_count = 0
    missing_file_count = 0
    unsafe_path_count = 0

    for index, pack_row in enumerate(pack_rows, start=1):
        check_id = f"P253A-{index:04d}"
        file_id = pack_row.get("file_id", "").strip()
        category = pack_row.get("category", "").strip()
        relative_path = pack_row.get("relative_path", "").strip()
        expected_sha256 = pack_row.get("sha256", "").strip()
        notes: list[str] = []

        path_safe, target, safety_note = _safe_target(relative_path, repo_root)
        if not path_safe:
            unsafe_path_count += 1
            notes.append(safety_note)
            failures.append(f"{check_id} unsafe path for {file_id or '(missing file_id)'}: {safety_note}")

        expected_hash_valid = _valid_sha256(expected_sha256)
        if not expected_hash_valid:
            notes.append("expected_sha256 is not a lowercase 64-character hex digest")
            failures.append(f"{check_id} invalid expected SHA-256 for {file_id or relative_path}")

        manifest_target_exists = _is_manifest_true(pack_row.get("target_exists", ""))
        if not manifest_target_exists:
            notes.append("P252 manifest target_exists is not True")
            failures.append(f"{check_id} P252 target_exists is not True for {file_id or relative_path}")

        target_exists = bool(path_safe and target is not None and target.is_file())
        actual_sha256 = ""
        hash_matches = False
        if not target_exists:
            missing_file_count += 1
            if path_safe:
                notes.append("target file is missing")
                failures.append(f"{check_id} missing target file: {relative_path}")
        elif expected_hash_valid:
            checked_file_count += 1
            actual_sha256 = _sha256_file(target)
            hash_matches = actual_sha256 == expected_sha256
            if hash_matches:
                hash_match_count += 1
            else:
                hash_mismatch_count += 1
                notes.append("actual SHA-256 does not match P252 manifest SHA-256")
                failures.append(f"{check_id} hash mismatch for {relative_path}")

        status = "PASS" if not notes and target_exists and hash_matches else "FAIL"
        check_rows.append(
            {
                "check_id": check_id,
                "file_id": file_id,
                "category": category,
                "relative_path": relative_path,
                "path_safe": path_safe,
                "target_exists": target_exists,
                "expected_sha256": expected_sha256,
                "actual_sha256": actual_sha256,
                "hash_matches": hash_matches,
                "status": status,
                "notes": "; ".join(notes),
            }
        )

    integrity_status = "FAIL" if failures else ("WARN" if warnings else "PASS")

    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / SUMMARY_JSON_FILENAME
    checks_path = output_dir / CHECKS_CSV_FILENAME
    report_path = output_dir / REPORT_MD_FILENAME

    output_files = {
        "integrity_summary_json": _display_path(summary_path, repo_root),
        "integrity_checks_csv": _display_path(checks_path, repo_root),
        "integrity_report_md": _display_path(report_path, repo_root),
    }

    input_paths = {
        "operator_pack_summary_json": _display_path(operator_pack_summary_json, repo_root),
        "operator_pack_files_csv": _display_path(operator_pack_files_csv, repo_root),
    }
    input_hashes = {
        "operator_pack_summary_json": _sha256_file(operator_pack_summary_json),
        "operator_pack_files_csv": _sha256_file(operator_pack_files_csv),
    }

    summary: dict[str, Any] = {
        "generated_at_utc": generated_at_utc,
        "integrity_status": integrity_status,
        "input_paths": dict(sorted(input_paths.items())),
        "input_hashes": dict(sorted(input_hashes.items())),
        "operator_pack_status": status_values["operator_pack_status"],
        "dashboard_status": status_values["dashboard_status"],
        "index_status": status_values["index_status"],
        "cli_help_smoke_status": status_values["cli_help_smoke_status"],
        "quickstart_status": status_values["quickstart_status"],
        "file_count": len(pack_rows),
        "checked_file_count": checked_file_count,
        "hash_match_count": hash_match_count,
        "hash_mismatch_count": hash_mismatch_count,
        "missing_file_count": missing_file_count,
        "unsafe_path_count": unsafe_path_count,
        "warning_count": len(warnings),
        "failure_count": len(failures),
        "output_files": output_files,
        "limitation_labels": list(LIMITATION_LABELS),
        "no_side_effects": {
            "read_existing_p252_artifacts_only": True,
            "executed_p239_to_p252_scripts": False,
            "executed_workflow_query_diff_gate_status_dashboard_index_help_smoke_quickstart_operator_pack_commands": False,
            "executed_operator_scripts": False,
            "regenerated_predictions_or_artifacts": False,
            "mutated_p237_to_p252_source_artifacts": False,
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
    _write_csv(checks_path, check_rows)
    _write_markdown(report_path, summary, tuple(check_rows))

    return PaperToolchainPackIntegrityResult(
        summary=summary,
        check_rows=tuple(check_rows),
        output_paths=output_files,
    )
