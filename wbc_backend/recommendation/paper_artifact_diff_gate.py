"""Deterministic pass/fail gate for P245 paper artifact diff outputs.

This module reads existing P245 diff artifacts and writes local gate artifacts.
It does not regenerate catalogs or diffs, contact providers, write data, or
compute betting performance.
"""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable

from wbc_backend.recommendation.paper_artifact_catalog import REQUIRED_LIMITATION_LABELS
from wbc_backend.recommendation.paper_artifact_catalog_diff import DIFF_CSV_FIELDNAMES
from wbc_backend.recommendation.paper_strategy_learning import resolve_generated_at_utc


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_DIFF_SUMMARY = ROOT / "report" / "p245a_paper_artifact_catalog_diff" / "diff_summary.json"
DEFAULT_DIFF_ENTRIES = ROOT / "report" / "p245a_paper_artifact_catalog_diff" / "diff_entries.csv"
DEFAULT_OUTPUT_DIR = ROOT / "report" / "p246a_paper_artifact_diff_gate"
DEFAULT_GENERATED_AT_UTC = None

GATE_SUMMARY_FILENAME = "gate_summary.json"
GATE_CHECKS_FILENAME = "gate_checks.csv"
GATE_REPORT_FILENAME = "gate_report.md"

GATE_CHECK_FIELDNAMES = [
    "check_id",
    "check_name",
    "severity",
    "expected",
    "observed",
    "result",
    "notes",
]

COUNT_KEYS = (
    "added_count",
    "removed_count",
    "changed_count",
    "warning_count",
    "failure_count",
    "status_changed_count",
    "role_changed_count",
    "file_type_changed_count",
    "notes_changed_count",
)

FORBIDDEN_NOT_CLAIMS = (
    "No ROI, paper P/L, EV, Kelly, bankroll, or compounding is computed.",
    "No best_strategy, best_threshold, recommended_bet, or strategy ranking is output.",
    "No betting edge, future prediction, true-PIT validation, "
    "or multi-season validation is claimed.",
    "No live, production, or real betting output is created.",
)


class PaperArtifactDiffGateError(RuntimeError):
    """Raised when diff gate evaluation cannot complete."""


@dataclass(frozen=True)
class PaperArtifactDiffGatePolicy:
    max_added: int = 0
    max_removed: int = 0
    max_changed: int = 0
    max_warning: int = 0
    allow_status_changes: bool = False
    allow_role_changes: bool = False
    allow_file_type_changes: bool = False
    allow_notes_changes: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "max_added": self.max_added,
            "max_removed": self.max_removed,
            "max_changed": self.max_changed,
            "max_warning": self.max_warning,
            "allow_status_changes": self.allow_status_changes,
            "allow_role_changes": self.allow_role_changes,
            "allow_file_type_changes": self.allow_file_type_changes,
            "allow_notes_changes": self.allow_notes_changes,
        }


@dataclass(frozen=True)
class PaperArtifactDiffGateResult:
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


def _format_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return str(value)


def _stable_items(items: Any) -> list[Any]:
    if not isinstance(items, list):
        return []
    return sorted(items, key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")))


def _load_diff_summary(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise PaperArtifactDiffGateError(f"MISSING_INPUT: diff summary not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PaperArtifactDiffGateError(
            f"CORRUPT_INPUT: invalid diff summary JSON in {path}: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise PaperArtifactDiffGateError(
            f"CORRUPT_INPUT: diff summary JSON must be an object: {path}"
        )
    missing = sorted(set(COUNT_KEYS) - set(payload))
    if missing:
        raise PaperArtifactDiffGateError(
            f"CORRUPT_INPUT: diff summary missing required keys {missing}: {path}"
        )
    for key in COUNT_KEYS:
        if not isinstance(payload.get(key), int):
            raise PaperArtifactDiffGateError(
                f"CORRUPT_INPUT: diff summary key {key} must be an integer: {path}"
            )
    if not isinstance(payload.get("warnings", []), list):
        raise PaperArtifactDiffGateError(
            f"CORRUPT_INPUT: diff summary warnings must be a list: {path}"
        )
    if not isinstance(payload.get("failures", []), list):
        raise PaperArtifactDiffGateError(
            f"CORRUPT_INPUT: diff summary failures must be a list: {path}"
        )
    return payload


def _load_diff_entries(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise PaperArtifactDiffGateError(f"MISSING_INPUT: diff entries CSV not found: {path}")
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fieldnames = list(reader.fieldnames or ())
            missing = [field for field in DIFF_CSV_FIELDNAMES if field not in fieldnames]
            if missing:
                raise PaperArtifactDiffGateError(
                    f"CORRUPT_INPUT: diff entries CSV missing required columns {missing}: {path}"
                )
            return [
                {field: _format_cell(row.get(field, "")) for field in DIFF_CSV_FIELDNAMES}
                for row in reader
            ]
    except csv.Error as exc:
        raise PaperArtifactDiffGateError(
            f"CORRUPT_INPUT: invalid diff entries CSV in {path}: {exc}"
        ) from exc


def _entry_counts(rows: Iterable[dict[str, str]]) -> dict[str, int]:
    rows = list(rows)
    field_change_sets = [set(row.get("field_changes", "").split(",")) for row in rows]
    return {
        "entry_row_count": len(rows),
        "entry_added_count": sum(1 for row in rows if row.get("change_type") == "added"),
        "entry_removed_count": sum(1 for row in rows if row.get("change_type") == "removed"),
        "entry_changed_count": sum(
            1
            for row in rows
            if row.get("change_type") not in {"added", "removed", "unchanged"}
        ),
        "entry_status_changed_count": sum(
            1 for changes in field_change_sets if "status-changed" in changes
        ),
        "entry_role_changed_count": sum(
            1 for changes in field_change_sets if "role-changed" in changes
        ),
        "entry_file_type_changed_count": sum(
            1 for changes in field_change_sets if "type-changed" in changes
        ),
        "entry_notes_changed_count": sum(
            1 for changes in field_change_sets if "notes-changed" in changes
        ),
    }


def _observed_counts(summary: dict[str, Any], rows: list[dict[str, str]]) -> dict[str, int]:
    counts = {key: int(summary[key]) for key in COUNT_KEYS}
    counts.update(_entry_counts(rows))
    return counts


def _check(
    *,
    check_id: str,
    check_name: str,
    expected: str,
    observed: Any,
    passed: bool,
    notes: str = "",
    severity: str = "FAIL",
) -> dict[str, str]:
    return {
        "check_id": check_id,
        "check_name": check_name,
        "severity": severity,
        "expected": expected,
        "observed": _format_cell(observed),
        "result": "PASS" if passed else "FAIL",
        "notes": notes,
    }


def _build_checks(
    *,
    policy: PaperArtifactDiffGatePolicy,
    observed: dict[str, int],
) -> list[dict[str, str]]:
    checks = [
        _check(
            check_id="threshold.added_count",
            check_name="Added artifacts within policy",
            expected=f"<= {policy.max_added}",
            observed=observed["added_count"],
            passed=observed["added_count"] <= policy.max_added,
        ),
        _check(
            check_id="threshold.removed_count",
            check_name="Removed artifacts within policy",
            expected=f"<= {policy.max_removed}",
            observed=observed["removed_count"],
            passed=observed["removed_count"] <= policy.max_removed,
        ),
        _check(
            check_id="threshold.changed_count",
            check_name="Changed artifacts within policy",
            expected=f"<= {policy.max_changed}",
            observed=observed["changed_count"],
            passed=observed["changed_count"] <= policy.max_changed,
        ),
        _check(
            check_id="threshold.warning_count",
            check_name="Input diff warnings within policy",
            expected=f"<= {policy.max_warning}",
            observed=observed["warning_count"],
            passed=observed["warning_count"] <= policy.max_warning,
        ),
        _check(
            check_id="input.failure_count",
            check_name="Input diff has no failures",
            expected="0",
            observed=observed["failure_count"],
            passed=observed["failure_count"] == 0,
        ),
        _check(
            check_id="change.status_allowed",
            check_name="Status changes allowed by policy",
            expected="allowed" if policy.allow_status_changes else "0",
            observed=observed["status_changed_count"],
            passed=policy.allow_status_changes or observed["status_changed_count"] == 0,
        ),
        _check(
            check_id="change.role_allowed",
            check_name="Role changes allowed by policy",
            expected="allowed" if policy.allow_role_changes else "0",
            observed=observed["role_changed_count"],
            passed=policy.allow_role_changes or observed["role_changed_count"] == 0,
        ),
        _check(
            check_id="change.file_type_allowed",
            check_name="File type changes allowed by policy",
            expected="allowed" if policy.allow_file_type_changes else "0",
            observed=observed["file_type_changed_count"],
            passed=policy.allow_file_type_changes or observed["file_type_changed_count"] == 0,
        ),
        _check(
            check_id="change.notes_allowed",
            check_name="Notes changes allowed by policy",
            expected="allowed" if policy.allow_notes_changes else "0",
            observed=observed["notes_changed_count"],
            passed=policy.allow_notes_changes or observed["notes_changed_count"] == 0,
        ),
    ]
    return checks


def _warnings_from_input(
    summary: dict[str, Any],
    policy: PaperArtifactDiffGatePolicy,
) -> list[dict[str, str]]:
    source_warning_count = int(summary["warning_count"])
    if source_warning_count == 0 or source_warning_count > policy.max_warning:
        return []
    source_warnings = _stable_items(summary.get("warnings", []))
    if source_warnings:
        return [
            {
                "check_id": str(item.get("check_id", "input.warning")),
                "message": str(item.get("message", "input diff warning observed")),
                "observed": str(item.get("observed", source_warning_count)),
            }
            for item in source_warnings
        ]
    return [
        {
            "check_id": "input.warning_count",
            "message": "input diff warning count is within configured policy",
            "observed": str(source_warning_count),
        }
    ]


def _failures_from_checks(checks: Iterable[dict[str, str]]) -> list[dict[str, str]]:
    failures = []
    for check in checks:
        if check["result"] == "FAIL":
            failures.append(
                {
                    "check_id": check["check_id"],
                    "message": check["check_name"],
                    "expected": check["expected"],
                    "observed": check["observed"],
                }
            )
    return failures


def _limitation_labels(summary: dict[str, Any]) -> list[str]:
    labels: list[str] = []
    for label in summary.get("limitation_labels", []):
        text = str(label)
        if text and text not in labels:
            labels.append(text)
    for label in REQUIRED_LIMITATION_LABELS:
        if label not in labels:
            labels.append(label)
    return labels


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: Iterable[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=GATE_CHECK_FIELDNAMES, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {field: _format_cell(row.get(field, "")) for field in GATE_CHECK_FIELDNAMES}
            )


def _write_markdown(path: Path, summary: dict[str, Any], checks: Iterable[dict[str, str]]) -> None:
    checks = list(checks)
    lines = [
        "# P246-A Paper Artifact Diff Gate",
        "",
        "## Summary",
        f"- Generated at UTC: {summary['generated_at_utc']}",
        f"- Gate status: {summary['gate_status']}",
        f"- Passed checks: {summary['check_counts']['passed']}",
        f"- Failed checks: {summary['check_counts']['failed']}",
        f"- Warnings: {summary['warning_count']}",
        f"- Failures: {summary['failure_count']}",
        "",
        "## Inputs",
        f"- Diff summary: {summary['diff_summary_path']}",
        f"- Diff entries: {summary['diff_entries_path']}",
    ]
    for key, value in summary["input_hashes"].items():
        lines.append(f"- {key}: {value}")

    lines.extend(["", "## Policy"])
    for key, value in summary["policy"].items():
        lines.append(f"- {key}: {value}")

    lines.extend(["", "## Gate Checks"])
    for check in checks:
        lines.append(
            "- {result} {check_id}: expected {expected}; observed {observed}".format(
                result=check["result"],
                check_id=check["check_id"],
                expected=check["expected"],
                observed=check["observed"],
            )
        )

    lines.extend(
        [
            "",
            "## Warnings / Failures",
            f"- Warnings: {summary['warning_count']}",
            f"- Failures: {summary['failure_count']}",
        ]
    )
    for item in summary["warnings"]:
        lines.append(f"- Warning: {item.get('message', '')}")
    for item in summary["failures"]:
        lines.append(f"- Failure: {item.get('message', '')}")

    lines.extend(["", "## Safety Boundaries"])
    for label in REQUIRED_LIMITATION_LABELS:
        lines.append(f"- {label}")

    lines.extend(["", "## Not Claims"])
    for claim in FORBIDDEN_NOT_CLAIMS:
        lines.append(f"- {claim}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def gate_paper_artifact_diff(
    *,
    diff_summary_path: Path = DEFAULT_DIFF_SUMMARY,
    diff_entries_path: Path = DEFAULT_DIFF_ENTRIES,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    policy: PaperArtifactDiffGatePolicy | None = None,
    generated_at_utc: str | None = DEFAULT_GENERATED_AT_UTC,
) -> PaperArtifactDiffGateResult:
    diff_summary_path = Path(diff_summary_path)
    diff_entries_path = Path(diff_entries_path)
    output_dir = Path(output_dir)
    policy = policy or PaperArtifactDiffGatePolicy()
    generated_at_utc = resolve_generated_at_utc(generated_at_utc)

    diff_summary = _load_diff_summary(diff_summary_path)
    diff_entries = _load_diff_entries(diff_entries_path)
    observed = _observed_counts(diff_summary, diff_entries)
    checks = _build_checks(policy=policy, observed=observed)
    passed_checks = [check["check_id"] for check in checks if check["result"] == "PASS"]
    failed_checks = [check["check_id"] for check in checks if check["result"] == "FAIL"]
    warnings = _warnings_from_input(diff_summary, policy)
    failures = _failures_from_checks(checks)
    gate_status = "FAIL" if failures else "PASS"

    summary = {
        "generated_at_utc": generated_at_utc,
        "diff_summary_path": _display_path(diff_summary_path),
        "diff_entries_path": _display_path(diff_entries_path),
        "input_hashes": {
            "diff_summary_sha256": _sha256(diff_summary_path),
            "diff_entries_sha256": _sha256(diff_entries_path),
        },
        "gate_status": gate_status,
        "policy": policy.as_dict(),
        "observed_counts": observed,
        "check_counts": {
            "total": len(checks),
            "passed": len(passed_checks),
            "failed": len(failed_checks),
        },
        "passed_checks": passed_checks,
        "failed_checks": failed_checks,
        "warning_count": len(warnings),
        "failure_count": len(failures),
        "limitation_labels": _limitation_labels(diff_summary),
        "failures": _stable_items(failures),
        "warnings": _stable_items(warnings),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / GATE_SUMMARY_FILENAME
    checks_path = output_dir / GATE_CHECKS_FILENAME
    report_path = output_dir / GATE_REPORT_FILENAME
    _write_json(summary_path, summary)
    _write_csv(checks_path, checks)
    _write_markdown(report_path, summary, checks)

    return PaperArtifactDiffGateResult(
        summary=summary,
        checks=tuple(checks),
        output_paths={
            "gate_summary_json": _display_path(summary_path),
            "gate_checks_csv": _display_path(checks_path),
            "gate_report_md": _display_path(report_path),
        },
    )
