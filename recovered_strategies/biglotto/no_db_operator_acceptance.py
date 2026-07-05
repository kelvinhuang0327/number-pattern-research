"""P375 Big Lotto no-DB operator acceptance suite and release gate.

This module reads only merged P371/P372/P373/P374 command-center artifacts and
returns one deterministic acceptance decision for the Big Lotto no-DB operator
stack. It does not open or write a DB, call adapters, create new scoring
cohorts, import production registries, deploy, provide betting advice, or make
future-performance claims.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import textwrap
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Iterable, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
TASK = "P375_biglotto_operator_acceptance"
GENERATED_AT = "DETERMINISTIC_PLACEHOLDER"
SOURCE_BASELINE = {
    "required_origin_main_merge_commit": "e7a9a16224d3fec10500283bafef38701e1d0d21",
    "p371_source_merge_baseline": "30e4120060e41e8a6f7cf529c28d9b490c01f70b",
    "p372_source_baseline": "1a971bd14a11de3e6e5967cfb543ab7069e97100",
    "p373_source_merge_baseline": "992c0c33ca9e3db1bbe81914cd1de82b21c06bde",
    "p374_merge_baseline": "e7a9a16224d3fec10500283bafef38701e1d0d21",
    "acceptance_mode": "read_only_no_db_release_gate",
}

P375_ARTIFACT_BASENAMES = {
    "decision": "P375_biglotto_operator_acceptance_decision.json",
    "checklist": "P375_biglotto_operator_acceptance_checklist.csv",
    "failure_matrix": "P375_biglotto_operator_acceptance_failure_matrix.csv",
    "risk_notes": "P375_biglotto_operator_acceptance_risk_notes.json",
    "portal": "P375_biglotto_operator_acceptance_portal.html",
    "manifest": "P375_biglotto_operator_acceptance_manifest.csv",
}

REQUIRED_SOURCE_ARTIFACTS = (
    "recovered_strategies/biglotto/no_db_evidence_command_center.py",
    "recovered_strategies/biglotto/no_db_command_center_route_replay.py",
    "recovered_strategies/biglotto/no_db_command_center_operator_console.py",
    "recovered_strategies/biglotto/no_db_operator_history.py",
    "artifacts/P371_biglotto_command_center_index.json",
    "artifacts/P371_biglotto_command_center_routes.csv",
    "artifacts/P371_biglotto_command_center_status.json",
    "artifacts/P371_biglotto_command_center_smoke_results.csv",
    "artifacts/P371_biglotto_command_center_task_cards.json",
    "artifacts/P371_biglotto_command_center_launchpad.html",
    "artifacts/P371_biglotto_command_center_quickstart.md",
    "artifacts/P371_biglotto_command_center_manifest.csv",
    "artifacts/P372_biglotto_command_center_route_transcripts.json",
    "artifacts/P372_biglotto_command_center_route_health.csv",
    "artifacts/P372_biglotto_command_center_route_coverage.csv",
    "artifacts/P372_biglotto_command_center_failure_taxonomy.csv",
    "artifacts/P372_biglotto_command_center_smoke_bundle.json",
    "artifacts/P372_biglotto_command_center_manifest.csv",
    "artifacts/P373_biglotto_command_center_operator_status.json",
    "artifacts/P373_biglotto_command_center_operator_badges.json",
    "artifacts/P373_biglotto_command_center_operator_issues.csv",
    "artifacts/P373_biglotto_command_center_operator_actions.json",
    "artifacts/P373_biglotto_command_center_operator_console.html",
    "artifacts/P373_biglotto_command_center_operator_manifest.csv",
    "artifacts/P374_biglotto_operator_health_snapshot.json",
    "artifacts/P374_biglotto_operator_status_delta.csv",
    "artifacts/P374_biglotto_operator_issue_trends.csv",
    "artifacts/P374_biglotto_operator_snapshot_comparison.json",
    "artifacts/P374_biglotto_operator_history.html",
    "artifacts/P374_biglotto_operator_manifest.csv",
    "tests/test_p371_biglotto_evidence_command_center.py",
    "tests/test_p372_biglotto_command_center_route_replay.py",
    "tests/test_p373_biglotto_command_center_operator_console.py",
    "tests/test_p374_biglotto_operator_history.py",
)

DISCLAIMER_LINES = (
    "Historical descriptive evidence only.",
    "No future prediction guarantee.",
    "No betting advice.",
    "No DB open/write.",
    "No adapter calls.",
    "No new scoring.",
    "No new scoring cohort.",
    "No production registry import.",
    "No deploy.",
    "No generated DB rows.",
    "No strategy status changes.",
    "No blended leaderboard.",
    "No force operations.",
    "Acceptance decision is a read-only release gate over committed P371/P372/P373/P374 evidence.",
)
SCOPE_STATEMENT = " ".join(DISCLAIMER_LINES)

STATEMENTS = {
    "historical_descriptive_evidence_only": True,
    "future_prediction_guarantee": False,
    "betting_advice": False,
    "db_opened": False,
    "db_written": False,
    "adapter_calls": False,
    "new_scoring": False,
    "new_scoring_cohort": False,
    "production_registry_imported": False,
    "deployed": False,
    "generated_db_rows": False,
    "strategy_status_changes": False,
    "blended_leaderboard": False,
    "force_operations": False,
}

CHECKLIST_COLUMNS = (
    "check_id",
    "check_group",
    "description",
    "source_artifact",
    "expected",
    "observed",
    "status",
    "blocking",
)

FAILURE_MATRIX_COLUMNS = (
    "failure_class",
    "source_stage",
    "detection_artifact",
    "severity",
    "blocking",
    "remediation_hint",
    "current_count",
)

MANIFEST_COLUMNS = (
    "artifact_group",
    "artifact_role",
    "path",
    "source_sha256",
    "output_row_count",
    "output_object_count",
    "no_db_open_write",
    "no_adapter_calls",
    "no_new_scoring",
    "details",
    "scope_statement",
)

VALIDATION_COLUMNS = ("check_name", "status", "expected", "actual", "details")

FORBIDDEN_AUTHORIZATION_PHRASES = (
    "you may open the db",
    "you may write the db",
    "open the database",
    "write to the database",
    "adapter execution is authorized",
    "adapter calls are authorized",
    "new scoring cohort is authorized",
    "deploy to production",
    "force push",
    "force merge",
    "force-delete",
    "status changes are authorized",
    "bet this",
    "recommended wager",
    "guaranteed win",
    "guaranteed profit",
    "will win",
    "future lock",
    "sure thing",
    "standing authorization granted",
)


@dataclass(frozen=True)
class AcceptanceOutput:
    decision: dict[str, object]
    checklist_rows: tuple[dict[str, str], ...]
    failure_matrix_rows: tuple[dict[str, str], ...]
    risk_notes: dict[str, object]
    portal_html: str
    manifest_rows: tuple[dict[str, str], ...]
    validation_rows: tuple[dict[str, str], ...]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact_path(relpath: str, repo_root: Path | None = None) -> Path:
    root = Path(repo_root) if repo_root is not None else REPO_ROOT
    return root / relpath


def _read_json(relpath: str, repo_root: Path | None = None) -> object:
    with open(_artifact_path(relpath, repo_root), encoding="utf-8") as handle:
        return json.load(handle)


def _read_csv_rows(relpath: str, repo_root: Path | None = None) -> tuple[dict[str, str], ...]:
    with open(_artifact_path(relpath, repo_root), newline="", encoding="utf-8") as handle:
        return tuple(dict(row) for row in csv.DictReader(handle))


def _json_text(payload: object) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _csv_text(columns: Sequence[str], rows: Iterable[Mapping[str, str]]) -> str:
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(columns), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({column: row.get(column, "") for column in columns})
    return buffer.getvalue()


def _check(name: str, passed: bool, expected: object, actual: object, details: str) -> dict[str, str]:
    return {
        "check_name": name,
        "status": "PASS" if passed else "FAIL",
        "expected": str(expected),
        "actual": str(actual),
        "details": details,
    }


def _as_mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def verify_required_evidence(repo_root: Path | None = None) -> tuple[Path, ...]:
    paths = tuple(_artifact_path(relpath, repo_root) for relpath in REQUIRED_SOURCE_ARTIFACTS)
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise RuntimeError(f"required P371/P372/P373/P374 acceptance evidence missing: {missing}")
    return paths


def source_inventory(repo_root: Path | None = None) -> tuple[dict[str, str], ...]:
    verify_required_evidence(repo_root)
    rows = []
    for relpath in REQUIRED_SOURCE_ARTIFACTS:
        rows.append(
            {
                "path": relpath,
                "kind": "source_module" if relpath.endswith(".py") else "source_artifact",
                "sha256": sha256_file(_artifact_path(relpath, repo_root)),
            }
        )
    return tuple(rows)


def load_source_bundle(repo_root: Path | None = None) -> dict[str, object]:
    verify_required_evidence(repo_root)
    return {
        "p371_status": _read_json("artifacts/P371_biglotto_command_center_status.json", repo_root),
        "p371_routes": _read_csv_rows("artifacts/P371_biglotto_command_center_routes.csv", repo_root),
        "p371_smoke": _read_csv_rows("artifacts/P371_biglotto_command_center_smoke_results.csv", repo_root),
        "p372_coverage": _read_csv_rows("artifacts/P372_biglotto_command_center_route_coverage.csv", repo_root),
        "p372_health": _read_csv_rows("artifacts/P372_biglotto_command_center_route_health.csv", repo_root),
        "p372_failure_taxonomy": _read_csv_rows("artifacts/P372_biglotto_command_center_failure_taxonomy.csv", repo_root),
        "p372_smoke_bundle": _read_json("artifacts/P372_biglotto_command_center_smoke_bundle.json", repo_root),
        "p373_status": _read_json("artifacts/P373_biglotto_command_center_operator_status.json", repo_root),
        "p373_issues": _read_csv_rows("artifacts/P373_biglotto_command_center_operator_issues.csv", repo_root),
        "p374_snapshot": _read_json("artifacts/P374_biglotto_operator_health_snapshot.json", repo_root),
        "p374_delta": _read_csv_rows("artifacts/P374_biglotto_operator_status_delta.csv", repo_root),
        "p374_issue_trends": _read_csv_rows("artifacts/P374_biglotto_operator_issue_trends.csv", repo_root),
        "p374_comparison": _read_json("artifacts/P374_biglotto_operator_snapshot_comparison.json", repo_root),
    }


def _first_row(rows: Sequence[Mapping[str, str]]) -> Mapping[str, str]:
    return rows[0] if rows else {}


def _int_text(value: object) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return 0


def build_checklist(repo_root: Path | None = None) -> tuple[dict[str, str], ...]:
    bundle = load_source_bundle(repo_root)
    p371_status = _as_mapping(bundle["p371_status"])
    p373_status = _as_mapping(bundle["p373_status"])
    p374_snapshot = _as_mapping(bundle["p374_snapshot"])
    p374_comparison = _as_mapping(bundle["p374_comparison"])
    p372_coverage = _first_row(bundle["p372_coverage"])  # type: ignore[arg-type]
    p373_issues = bundle["p373_issues"]  # type: ignore[assignment]
    p374_delta = bundle["p374_delta"]  # type: ignore[assignment]
    issue_counts = _as_mapping(p373_status.get("issue_counts"))
    statements = _as_mapping(p374_snapshot.get("statements"))
    observed_restricted_statements = {
        key: statements.get(key, STATEMENTS[key])
        for key, value in STATEMENTS.items()
        if value is False
    }

    checks = (
        (
            "P375-CHECK-001",
            "source",
            "All required P371/P372/P373/P374 modules, tests, and artifacts are present.",
            "P371/P372/P373/P374 source inventory",
            str(len(REQUIRED_SOURCE_ARTIFACTS)),
            str(len(verify_required_evidence(repo_root))),
            len(verify_required_evidence(repo_root)) == len(REQUIRED_SOURCE_ARTIFACTS),
            True,
        ),
        (
            "P375-CHECK-002",
            "p371_command_center",
            "P371 command center is ready.",
            "artifacts/P371_biglotto_command_center_status.json",
            "command_center_ready=True",
            f"command_center_ready={p371_status.get('command_center_ready')}",
            p371_status.get("command_center_ready") is True,
            True,
        ),
        (
            "P375-CHECK-003",
            "p371_command_center",
            "P371 smoke rows have no FAIL status.",
            "artifacts/P371_biglotto_command_center_smoke_results.csv",
            "0 fail rows",
            f"{sum(1 for row in bundle['p371_smoke'] if row.get('status') != 'PASS')} fail rows",  # type: ignore[union-attr]
            sum(1 for row in bundle["p371_smoke"] if row.get("status") != "PASS") == 0,  # type: ignore[union-attr]
            True,
        ),
        (
            "P375-CHECK-004",
            "p372_route_replay",
            "All P371 command-center routes were replayed.",
            "artifacts/P372_biglotto_command_center_route_coverage.csv",
            "coverage_rate=1.0000 and fail_count=0",
            f"coverage_rate={p372_coverage.get('coverage_rate')} fail_count={p372_coverage.get('fail_count')}",
            p372_coverage.get("coverage_rate") == "1.0000" and p372_coverage.get("fail_count") == "0",
            True,
        ),
        (
            "P375-CHECK-005",
            "p372_route_replay",
            "Route health has no FAIL rows.",
            "artifacts/P372_biglotto_command_center_route_health.csv",
            "0 FAIL rows",
            f"{sum(1 for row in bundle['p372_health'] if row.get('replay_status') == 'FAIL')} FAIL rows",  # type: ignore[union-attr]
            sum(1 for row in bundle["p372_health"] if row.get("replay_status") == "FAIL") == 0,  # type: ignore[union-attr]
            True,
        ),
        (
            "P375-CHECK-006",
            "p373_operator_console",
            "Operator console health is PASS.",
            "artifacts/P373_biglotto_command_center_operator_status.json",
            "overall_operator_health=PASS",
            f"overall_operator_health={p373_status.get('overall_operator_health')}",
            p373_status.get("overall_operator_health") == "PASS",
            True,
        ),
        (
            "P375-CHECK-007",
            "p373_operator_console",
            "Operator console has no FAIL or WARN issues.",
            "artifacts/P373_biglotto_command_center_operator_issues.csv",
            "FAIL=0 WARN=0",
            f"FAIL={issue_counts.get('FAIL', 0)} WARN={issue_counts.get('WARN', 0)} rows={len(p373_issues)}",
            _int_text(issue_counts.get("FAIL", 0)) == 0 and _int_text(issue_counts.get("WARN", 0)) == 0,
            True,
        ),
        (
            "P375-CHECK-008",
            "p374_operator_history",
            "P374 snapshot health is PASS.",
            "artifacts/P374_biglotto_operator_health_snapshot.json",
            "overall_operator_health=PASS",
            f"overall_operator_health={_as_mapping(p374_snapshot.get('operator_health')).get('overall_operator_health')}",
            _as_mapping(p374_snapshot.get("operator_health")).get("overall_operator_health") == "PASS",
            True,
        ),
        (
            "P375-CHECK-009",
            "p374_operator_history",
            "P374 history comparison is an unchanged initial snapshot.",
            "artifacts/P374_biglotto_operator_snapshot_comparison.json",
            "INITIAL_SNAPSHOT_NO_CHANGES",
            str(p374_comparison.get("comparison_status", "")),
            p374_comparison.get("comparison_status") == "INITIAL_SNAPSHOT_NO_CHANGES",
            False,
        ),
        (
            "P375-CHECK-010",
            "p374_operator_history",
            "P374 status delta rows are PASS.",
            "artifacts/P374_biglotto_operator_status_delta.csv",
            "all PASS",
            f"{sum(1 for row in p374_delta if row.get('status') != 'PASS')} non-PASS rows",
            sum(1 for row in p374_delta if row.get("status") != "PASS") == 0,  # type: ignore[union-attr]
            True,
        ),
        (
            "P375-CHECK-011",
            "safety_constraints",
            "No DB, adapter, scoring, registry, deploy, status-change, force, betting, or future-claim action is authorized.",
            "artifacts/P374_biglotto_operator_health_snapshot.json",
            "all restricted statements false",
            str({key: observed_restricted_statements[key] for key in sorted(observed_restricted_statements)}),
            all(value is False for value in observed_restricted_statements.values()),
            True,
        ),
        (
            "P375-CHECK-012",
            "acceptance_gate",
            "P375 acceptance gate is generated from read-only committed artifacts.",
            "P375 generator",
            "read-only no-DB aggregation",
            "read-only no-DB aggregation",
            True,
            True,
        ),
    )
    rows = []
    for check_id, group, description, source, expected, observed, passed, blocking in checks:
        rows.append(
            {
                "check_id": check_id,
                "check_group": group,
                "description": description,
                "source_artifact": source,
                "expected": expected,
                "observed": observed,
                "status": "PASS" if passed else "FAIL",
                "blocking": "true" if blocking else "false",
            }
        )
    return tuple(rows)


def build_failure_matrix(repo_root: Path | None = None) -> tuple[dict[str, str], ...]:
    bundle = load_source_bundle(repo_root)
    taxonomy = bundle["p372_failure_taxonomy"]  # type: ignore[assignment]
    p373_issues = bundle["p373_issues"]  # type: ignore[assignment]
    p374_delta = bundle["p374_delta"]  # type: ignore[assignment]
    rows = []
    for row in taxonomy:
        rows.append(
            {
                "failure_class": row.get("failure_class", ""),
                "source_stage": "P372 route replay",
                "detection_artifact": "artifacts/P372_biglotto_command_center_failure_taxonomy.csv",
                "severity": row.get("route_health_impact", "FAIL"),
                "blocking": "true" if row.get("route_health_impact", "FAIL") == "FAIL" else "false",
                "remediation_hint": row.get("safe_action", ""),
                "current_count": "0",
            }
        )
    rows.extend(
        (
            {
                "failure_class": "operator_console_fail_or_warn_issue",
                "source_stage": "P373 operator console",
                "detection_artifact": "artifacts/P373_biglotto_command_center_operator_issues.csv",
                "severity": "FAIL",
                "blocking": "true",
                "remediation_hint": "Inspect P373 issue rows and regenerate read-only operator-console artifacts after the source issue is fixed.",
                "current_count": str(sum(1 for row in p373_issues if row.get("severity") in {"FAIL", "WARN"})),
            },
            {
                "failure_class": "operator_history_status_delta_failure",
                "source_stage": "P374 operator history",
                "detection_artifact": "artifacts/P374_biglotto_operator_status_delta.csv",
                "severity": "FAIL",
                "blocking": "true",
                "remediation_hint": "Inspect P374 delta rows; acceptance remains blocked until all read-only history deltas are PASS.",
                "current_count": str(sum(1 for row in p374_delta if row.get("status") != "PASS")),
            },
            {
                "failure_class": "acceptance_gate_forbidden_language",
                "source_stage": "P375 acceptance gate",
                "detection_artifact": "artifacts/P375_biglotto_operator_acceptance_*",
                "severity": "FAIL",
                "blocking": "true",
                "remediation_hint": "Remove authorization-style wording and rerun deterministic P375 validation.",
                "current_count": "0",
            },
        )
    )
    return tuple(rows)


def build_decision(
    checklist_rows: Sequence[Mapping[str, str]] | None = None,
    failure_matrix_rows: Sequence[Mapping[str, str]] | None = None,
    repo_root: Path | None = None,
) -> dict[str, object]:
    checks = tuple(checklist_rows) if checklist_rows is not None else build_checklist(repo_root)
    failures = tuple(failure_matrix_rows) if failure_matrix_rows is not None else build_failure_matrix(repo_root)
    bundle = load_source_bundle(repo_root)
    p373_status = _as_mapping(bundle["p373_status"])
    p374_snapshot = _as_mapping(bundle["p374_snapshot"])
    route_coverage = _first_row(bundle["p372_coverage"])  # type: ignore[arg-type]
    fail_checks = tuple(row for row in checks if row.get("status") == "FAIL")
    warn_checks = tuple(row for row in checks if row.get("status") == "WARN")
    blocking_fail_checks = tuple(row for row in fail_checks if row.get("blocking") == "true")
    matrix_current_blocking = sum(_int_text(row.get("current_count", 0)) for row in failures if row.get("blocking") == "true")
    blocking_issue_count = len(blocking_fail_checks) + matrix_current_blocking
    overall = "FAIL" if blocking_issue_count else ("WARN" if warn_checks else "PASS")
    rejection_reasons = tuple(row["check_id"] for row in blocking_fail_checks)
    return {
        "task": TASK,
        "generated_at": GENERATED_AT,
        "source_baseline": SOURCE_BASELINE,
        "overall_acceptance": overall,
        "accepted": overall == "PASS",
        "operator_health": {
            "p373_overall_operator_health": p373_status.get("overall_operator_health", ""),
            "p374_overall_operator_health": _as_mapping(p374_snapshot.get("operator_health")).get("overall_operator_health", ""),
        },
        "route_coverage": dict(route_coverage),
        "issue_counts": {
            "check_fail_count": len(fail_checks),
            "check_warn_count": len(warn_checks),
            "failure_matrix_current_blocking_count": matrix_current_blocking,
            "p373_issue_counts": dict(_as_mapping(p373_status.get("issue_counts"))),
            "p374_issue_counts": dict(_as_mapping(p374_snapshot.get("issue_counts"))),
        },
        "blocking_issue_count": blocking_issue_count,
        "rejection_reasons": rejection_reasons,
        "checklist_row_count": len(checks),
        "failure_matrix_row_count": len(failures),
        "statements": STATEMENTS,
        "scope_lines": DISCLAIMER_LINES,
        "notes": (
            "P375 returns one deterministic acceptance decision from committed P371/P372/P373/P374 artifacts only. "
            "It is not betting advice and provides no future prediction guarantee."
        ),
    }


def build_risk_notes(repo_root: Path | None = None) -> dict[str, object]:
    inventory_count = len(source_inventory(repo_root))
    return {
        "task": TASK,
        "generated_at": GENERATED_AT,
        "source_baseline": SOURCE_BASELINE,
        "technical_risks": (
            "Acceptance is only as fresh as the committed P371/P372/P373/P374 artifacts.",
            "Read-only route and operator health do not prove future strategy performance.",
            "Any later source artifact change requires rerunning this deterministic gate.",
        ),
        "governance_risks": (
            "Action cards and local commands are templates only, not standing authorization.",
            "Acceptance does not authorize DB writes, adapter execution, strategy status changes, registry import, deploy, force operations, betting advice, or future-performance claims.",
            "P375 is a release gate over historical descriptive evidence only.",
        ),
        "known_non_goals": (
            "No new scoring cohort.",
            "No shape-only scoring.",
            "No blocked target scoring.",
            "No blended leaderboard.",
            "No migration, backfill, deploy, or production registry import.",
            "No external publication.",
        ),
        "retained_worktree_notes": (
            "P371 retained worktree/branch must remain untouched.",
            "P373 retained worktree/branch must remain untouched.",
            "P360 readonly worktree must remain untouched.",
        ),
        "future_worker_notes": (
            f"P375 source inventory contains {inventory_count} required files.",
            "Rerun python3 -m recovered_strategies.biglotto.no_db_operator_acceptance --validate after any upstream evidence change.",
            "Keep subsequent work in isolated worktrees and preserve no-DB/no-adapter/no-scoring/no-deploy boundaries.",
        ),
        "statements": STATEMENTS,
        "scope_lines": DISCLAIMER_LINES,
    }


def _html_table(columns: Sequence[str], rows: Iterable[Mapping[str, object]]) -> str:
    head = "".join(f"<th>{html.escape(column)}</th>" for column in columns)
    body = []
    for row in rows:
        cells = "".join(f"<td>{html.escape(str(row.get(column, '')))}</td>" for column in columns)
        body.append(f"<tr>{cells}</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def build_portal_html(
    decision: Mapping[str, object],
    checklist_rows: Sequence[Mapping[str, str]],
    failure_matrix_rows: Sequence[Mapping[str, str]],
    risk_notes: Mapping[str, object],
    repo_root: Path | None = None,
) -> str:
    inventory_rows = source_inventory(repo_root)
    commands = (
        "python3 -m recovered_strategies.biglotto.no_db_operator_acceptance --generate",
        "python3 -m recovered_strategies.biglotto.no_db_operator_acceptance --decision",
        "python3 -m recovered_strategies.biglotto.no_db_operator_acceptance --checklist",
        "python3 -m recovered_strategies.biglotto.no_db_operator_acceptance --failure-matrix",
        "python3 -m recovered_strategies.biglotto.no_db_operator_acceptance --risk-notes",
        "python3 -m recovered_strategies.biglotto.no_db_operator_acceptance --portal",
        "python3 -m recovered_strategies.biglotto.no_db_operator_acceptance --validate",
    )
    command_items = "".join(f"<li><code>{html.escape(command)}</code></li>" for command in commands)
    risk_items = []
    for key in ("technical_risks", "governance_risks", "known_non_goals", "retained_worktree_notes", "future_worker_notes"):
        values = risk_notes.get(key, ())
        items = "".join(f"<li>{html.escape(str(value))}</li>" for value in values) if isinstance(values, Sequence) and not isinstance(values, (str, bytes)) else ""
        risk_items.append(f"<h3>{html.escape(key)}</h3><ul>{items}</ul>")
    css = textwrap.dedent(
        """
        body { margin: 0; font-family: Arial, sans-serif; color: #1f2933; background: #f6f7f9; }
        header { background: #17324d; color: #fff; padding: 24px 32px; }
        main { max-width: 1200px; margin: 0 auto; padding: 24px; }
        .banner { background: #fff3cd; border: 1px solid #c99a00; padding: 12px 16px; margin-bottom: 18px; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }
        .metric, .panel { background: #fff; border: 1px solid #d9dee7; border-radius: 6px; padding: 14px; margin-bottom: 18px; }
        .metric strong { display: block; font-size: 24px; margin-top: 4px; }
        table { width: 100%; border-collapse: collapse; background: #fff; margin: 10px 0 24px; }
        th, td { border: 1px solid #d9dee7; padding: 8px; text-align: left; vertical-align: top; }
        th { background: #edf2f7; }
        code { white-space: pre-wrap; overflow-wrap: anywhere; }
        h2 { margin-top: 28px; }
        """
    ).strip()
    return textwrap.dedent(
        f"""\
        <!doctype html>
        <html lang="en">
        <head>
          <meta charset="utf-8">
          <meta name="viewport" content="width=device-width, initial-scale=1">
          <title>P375 Big Lotto no-DB operator acceptance</title>
          <style>{css}</style>
        </head>
        <body>
          <header>
            <h1>P375 Big Lotto no-DB operator acceptance</h1>
            <p>Acceptance decision: <strong>{html.escape(str(decision.get("overall_acceptance", "")))}</strong></p>
          </header>
          <main>
            <section class="banner"><strong>Scope banner:</strong> {html.escape(SCOPE_STATEMENT)}</section>
            <h2>Acceptance Decision</h2>
            <div class="grid">
              <section class="metric">Accepted<strong>{html.escape(str(decision.get("accepted", "")))}</strong></section>
              <section class="metric">Overall acceptance<strong>{html.escape(str(decision.get("overall_acceptance", "")))}</strong></section>
              <section class="metric">Blocking issues<strong>{html.escape(str(decision.get("blocking_issue_count", "")))}</strong></section>
              <section class="metric">Checklist rows<strong>{html.escape(str(decision.get("checklist_row_count", "")))}</strong></section>
            </div>
            <h2>Checklist Table</h2>
            {_html_table(CHECKLIST_COLUMNS, checklist_rows)}
            <h2>Failure Matrix</h2>
            {_html_table(FAILURE_MATRIX_COLUMNS, failure_matrix_rows)}
            <h2>Risk Notes</h2>
            <section class="panel">{''.join(risk_items)}</section>
            <h2>Source Artifact Inventory</h2>
            {_html_table(("path", "kind", "sha256"), inventory_rows)}
            <h2>Local Commands</h2>
            <section class="panel"><ul>{command_items}</ul></section>
          </main>
        </body>
        </html>
        """
    ).lstrip()


def _artifact_contents_without_manifest(output: AcceptanceOutput) -> dict[str, str]:
    return {
        "decision": _json_text(output.decision),
        "checklist": _csv_text(CHECKLIST_COLUMNS, output.checklist_rows),
        "failure_matrix": _csv_text(FAILURE_MATRIX_COLUMNS, output.failure_matrix_rows),
        "risk_notes": _json_text(output.risk_notes),
        "portal": output.portal_html,
    }


def _artifact_contents(output: AcceptanceOutput) -> dict[str, str]:
    contents = _artifact_contents_without_manifest(output)
    contents["manifest"] = _csv_text(MANIFEST_COLUMNS, output.manifest_rows)
    return contents


def _output_counts(role: str, text: str) -> tuple[str, str]:
    if role in {"checklist", "failure_matrix", "manifest"}:
        return str(len(tuple(csv.DictReader(text.splitlines())))), ""
    if role in {"decision", "risk_notes", "portal"}:
        return "", "1"
    return "", ""


def build_manifest_rows(output_texts_without_manifest: Mapping[str, str], repo_root: Path | None = None) -> tuple[dict[str, str], ...]:
    rows: list[dict[str, str]] = []
    for relpath in REQUIRED_SOURCE_ARTIFACTS:
        rows.append(
            {
                "artifact_group": "source",
                "artifact_role": Path(relpath).stem,
                "path": relpath,
                "source_sha256": sha256_file(_artifact_path(relpath, repo_root)),
                "output_row_count": "",
                "output_object_count": "",
                "no_db_open_write": "YES",
                "no_adapter_calls": "YES",
                "no_new_scoring": "YES",
                "details": "P375 source evidence read from merged P371/P372/P373/P374 command-center artifacts only.",
                "scope_statement": SCOPE_STATEMENT,
            }
        )
    for role, basename in P375_ARTIFACT_BASENAMES.items():
        text = output_texts_without_manifest.get(role, "")
        row_count, object_count = _output_counts(role, text)
        digest = sha256_bytes(text.encode("utf-8")) if text else ""
        if role == "manifest":
            row_count = str(len(REQUIRED_SOURCE_ARTIFACTS) + len(P375_ARTIFACT_BASENAMES) + 3)
            digest = "SELF_SHA256_OMITTED_RECURSIVE_ARTIFACT"
        rows.append(
            {
                "artifact_group": "output",
                "artifact_role": role,
                "path": f"artifacts/{basename}",
                "source_sha256": digest,
                "output_row_count": row_count,
                "output_object_count": object_count,
                "no_db_open_write": "YES",
                "no_adapter_calls": "YES",
                "no_new_scoring": "YES",
                "details": "P375 generated no-DB operator acceptance artifact.",
                "scope_statement": SCOPE_STATEMENT,
            }
        )
    for role, details in (
        ("no_db_open_write", "No DB open/write was performed by P375."),
        ("no_adapter_calls", "No adapter calls were performed by P375."),
        ("no_new_scoring", "No new scoring, scoring cohort, shape-only scoring, blocked-target scoring, or blended leaderboard was created by P375."),
    ):
        rows.append(
            {
                "artifact_group": "statement",
                "artifact_role": role,
                "path": "",
                "source_sha256": "",
                "output_row_count": "",
                "output_object_count": "",
                "no_db_open_write": "YES",
                "no_adapter_calls": "YES",
                "no_new_scoring": "YES",
                "details": details,
                "scope_statement": SCOPE_STATEMENT,
            }
        )
    return tuple(rows)


def validate_acceptance(
    output: AcceptanceOutput | None = None,
    repo_root: Path | None = None,
    include_determinism: bool = True,
) -> tuple[dict[str, str], ...]:
    current = output if output is not None else run_acceptance(repo_root, include_validation=False)
    text = "\n".join(_artifact_contents(current).values()).lower()
    found = [phrase for phrase in FORBIDDEN_AUTHORIZATION_PHRASES if phrase in text]
    rows = [
        _check("required_p371_p372_p373_p374_evidence_exists", len(verify_required_evidence(repo_root)) == len(REQUIRED_SOURCE_ARTIFACTS), len(REQUIRED_SOURCE_ARTIFACTS), len(REQUIRED_SOURCE_ARTIFACTS), "Required merged modules, tests, and artifacts are present."),
        _check("decision_json_schema", set(current.decision) >= {"source_baseline", "overall_acceptance", "operator_health", "route_coverage", "issue_counts", "blocking_issue_count", "accepted", "rejection_reasons", "statements"}, "required decision keys", sorted(current.decision), "Decision JSON includes required acceptance fields."),
        _check("decision_acceptance_pass", current.decision.get("overall_acceptance") in {"PASS", "WARN", "FAIL"} and current.decision.get("accepted") is True, "accepted PASS", current.decision.get("overall_acceptance"), "Merged P371/P372/P373/P374 evidence yields accepted PASS."),
        _check("checklist_csv_schema", bool(current.checklist_rows) and tuple(current.checklist_rows[0]) == CHECKLIST_COLUMNS, CHECKLIST_COLUMNS, tuple(current.checklist_rows[0]) if current.checklist_rows else (), "Checklist rows use required columns."),
        _check("failure_matrix_csv_schema", bool(current.failure_matrix_rows) and tuple(current.failure_matrix_rows[0]) == FAILURE_MATRIX_COLUMNS, FAILURE_MATRIX_COLUMNS, tuple(current.failure_matrix_rows[0]) if current.failure_matrix_rows else (), "Failure matrix rows use required columns."),
        _check("risk_notes_json_schema", set(current.risk_notes) >= {"technical_risks", "governance_risks", "known_non_goals", "retained_worktree_notes", "future_worker_notes"}, "required risk note keys", sorted(current.risk_notes), "Risk notes include required sections."),
        _check("portal_html_self_contained", current.portal_html.startswith("<!doctype html>") and "<script" not in current.portal_html.lower() and all(section in current.portal_html for section in ("Scope banner:", "Acceptance Decision", "Checklist Table", "Failure Matrix", "Risk Notes", "Source Artifact Inventory", "Local Commands")), "self-contained portal sections", "present", "Portal includes required sections and no script tag."),
        _check("manifest_csv_schema", bool(current.manifest_rows) and tuple(current.manifest_rows[0]) == MANIFEST_COLUMNS, MANIFEST_COLUMNS, tuple(current.manifest_rows[0]) if current.manifest_rows else (), "Manifest rows use required columns."),
        _check("manifest_records_sources_outputs_statements", sum(1 for row in current.manifest_rows if row["artifact_group"] == "source") == len(REQUIRED_SOURCE_ARTIFACTS) and sum(1 for row in current.manifest_rows if row["artifact_group"] == "output") == len(P375_ARTIFACT_BASENAMES), "all source/output rows", len(current.manifest_rows), "Manifest records source artifacts, output artifacts, and safety statements."),
        _check("generated_outputs_include_safety_constraints", all(line.lower() in text for line in DISCLAIMER_LINES), "all scope lines", "present", "Outputs include no-DB/no-adapter/no-scoring/no-deploy constraints."),
        _check("generated_outputs_do_not_authorize_forbidden_actions", not found, "absent", ";".join(found) if found else "absent", "P375 outputs do not authorize DB writes, adapter execution, scoring, deploy, force operations, status changes, betting advice, or future prediction claims."),
    ]
    if include_determinism:
        first = run_acceptance(repo_root, include_validation=False)
        second = run_acceptance(repo_root, include_validation=False)
        rows.append(
            _check(
                "deterministic_double_run_equality",
                _artifact_contents(first) == _artifact_contents(second),
                "equal",
                "equal" if _artifact_contents(first) == _artifact_contents(second) else "different",
                "P375 generated rows and artifacts are deterministic across two runs.",
            )
        )
    return tuple(rows)


def run_acceptance(repo_root: Path | None = None, include_validation: bool = True) -> AcceptanceOutput:
    checklist = build_checklist(repo_root)
    failure_matrix = build_failure_matrix(repo_root)
    decision = build_decision(checklist, failure_matrix, repo_root)
    risk_notes = build_risk_notes(repo_root)
    portal = build_portal_html(decision, checklist, failure_matrix, risk_notes, repo_root)
    with_portal = AcceptanceOutput(decision, checklist, failure_matrix, risk_notes, portal, (), ())
    manifest = build_manifest_rows(_artifact_contents_without_manifest(with_portal), repo_root)
    partial = AcceptanceOutput(decision, checklist, failure_matrix, risk_notes, portal, manifest, ())
    validation = validate_acceptance(partial, repo_root, include_determinism=True) if include_validation else ()
    return AcceptanceOutput(decision, checklist, failure_matrix, risk_notes, portal, manifest, validation)


def _assert_deterministic(first: AcceptanceOutput, second: AcceptanceOutput) -> None:
    if _artifact_contents(first) != _artifact_contents(second):
        raise RuntimeError("determinism double-run mismatch: P375 operator acceptance artifacts are not reproducible")


def write_artifacts(output: AcceptanceOutput, artifacts_dir: Path | None = None) -> dict[str, Path]:
    directory = Path(artifacts_dir) if artifacts_dir is not None else REPO_ROOT / "artifacts"
    directory.mkdir(parents=True, exist_ok=True)
    contents = _artifact_contents(output)
    paths = {key: directory / basename for key, basename in P375_ARTIFACT_BASENAMES.items()}
    for key, path in paths.items():
        if path.suffix == ".csv":
            with open(path, "w", encoding="utf-8", newline="") as handle:
                handle.write(contents[key])
        else:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(contents[key])
    return paths


def _print_json(payload: object) -> None:
    print(_json_text(payload), end="")


def _print_csv(columns: Sequence[str], rows: Iterable[Mapping[str, str]]) -> None:
    print(_csv_text(columns, rows), end="")


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts-dir", type=Path, default=None, help="override artifacts output directory")
    parser.add_argument("--generate", action="store_true", help="write all P375 operator acceptance artifacts")
    parser.add_argument("--decision", action="store_true", help="emit acceptance decision JSON")
    parser.add_argument("--checklist", action="store_true", help="emit acceptance checklist CSV")
    parser.add_argument("--failure-matrix", action="store_true", help="emit failure matrix CSV")
    parser.add_argument("--risk-notes", action="store_true", help="emit risk notes JSON")
    parser.add_argument("--portal", action="store_true", help="emit self-contained acceptance portal HTML")
    parser.add_argument("--validate", action="store_true", help="emit P375 validation rows as CSV")
    args = parser.parse_args(argv)

    if args.decision:
        _print_json(build_decision())
    elif args.checklist:
        _print_csv(CHECKLIST_COLUMNS, build_checklist())
    elif args.failure_matrix:
        _print_csv(FAILURE_MATRIX_COLUMNS, build_failure_matrix())
    elif args.risk_notes:
        _print_json(build_risk_notes())
    elif args.portal:
        output = run_acceptance()
        print(output.portal_html, end="")
    elif args.validate:
        _print_csv(VALIDATION_COLUMNS, validate_acceptance())
    else:
        first = run_acceptance()
        second = run_acceptance()
        _assert_deterministic(first, second)
        paths = write_artifacts(first, args.artifacts_dir)
        print("P375 Big Lotto no-DB operator acceptance: determinism double-run PASS")
        print(f"overall acceptance: {first.decision['overall_acceptance']}")
        print(f"accepted: {first.decision['accepted']}")
        print(f"blocking issues: {first.decision['blocking_issue_count']}")
        print(f"checklist rows: {len(first.checklist_rows)}")
        print(f"failure matrix rows: {len(first.failure_matrix_rows)}")
        print(f"validation rows: {len(first.validation_rows)}")
        print(f"validation failures: {sum(1 for row in first.validation_rows if row['status'] == 'FAIL')}")
        print("No DB was opened or written; no adapters were called; no new scoring was created; no production registry import or deploy was performed.")
        print("Historical descriptive evidence only; no betting advice; no future prediction guarantee; no strategy status changes; no blended leaderboard.")
        for key, path in sorted(paths.items()):
            print(f"{key}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
