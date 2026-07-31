"""P373 Big Lotto no-DB command center operator console.

This module reads only merged P371/P372 command-center artifacts and emits a
compact operator health dashboard. It does not open or write a DB, call
adapters, create new scoring cohorts, import production registries, deploy,
provide betting advice, or make future-performance claims.
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
TASK = "P373_biglotto_command_center_operator_console"
GENERATED_AT = "DETERMINISTIC_PLACEHOLDER"
SOURCE_BASELINE = {
    "required_origin_main_merge_commit": "269e50da43b0173809a44bc6010668ba92e488ca",
    "p371_source_merge_baseline": "30e4120060e41e8a6f7cf529c28d9b490c01f70b",
    "p372_source_baseline": "1a971bd14a11de3e6e5967cfb543ab7069e97100",
}

P373_ARTIFACT_BASENAMES = {
    "operator_status": "P373_biglotto_command_center_operator_status.json",
    "operator_badges": "P373_biglotto_command_center_operator_badges.json",
    "operator_issues": "P373_biglotto_command_center_operator_issues.csv",
    "operator_actions": "P373_biglotto_command_center_operator_actions.json",
    "operator_console": "P373_biglotto_command_center_operator_console.html",
    "operator_manifest": "P373_biglotto_command_center_operator_manifest.csv",
}

REQUIRED_SOURCE_ARTIFACTS = (
    "recovered_strategies/biglotto/no_db_evidence_command_center.py",
    "recovered_strategies/biglotto/no_db_command_center_route_replay.py",
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
    "tests/test_p371_biglotto_evidence_command_center.py",
    "tests/test_p372_biglotto_command_center_route_replay.py",
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
    "Operator action cards are templates, not standing authorization.",
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
    "operator_action_cards_templates_not_standing_authorization": True,
}

ISSUE_COLUMNS = (
    "issue_id",
    "source",
    "severity",
    "route_id",
    "issue_type",
    "description",
    "suggested_next_check",
    "status",
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
class OperatorConsoleOutput:
    status: dict[str, object]
    badges: dict[str, object]
    issue_rows: tuple[dict[str, str], ...]
    actions: dict[str, object]
    console_html: str
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


def _read_text(relpath: str, repo_root: Path | None = None) -> str:
    return _artifact_path(relpath, repo_root).read_text(encoding="utf-8")


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


def verify_required_evidence(repo_root: Path | None = None) -> tuple[Path, ...]:
    paths = tuple(_artifact_path(relpath, repo_root) for relpath in REQUIRED_SOURCE_ARTIFACTS)
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise RuntimeError(f"required P371/P372 command center evidence missing: {missing}")
    return paths


def load_source_bundle(repo_root: Path | None = None) -> dict[str, object]:
    verify_required_evidence(repo_root)
    return {
        "p371_index": _read_json("artifacts/P371_biglotto_command_center_index.json", repo_root),
        "p371_routes": _read_csv_rows("artifacts/P371_biglotto_command_center_routes.csv", repo_root),
        "p371_status": _read_json("artifacts/P371_biglotto_command_center_status.json", repo_root),
        "p371_smoke": _read_csv_rows("artifacts/P371_biglotto_command_center_smoke_results.csv", repo_root),
        "p371_task_cards": _read_json("artifacts/P371_biglotto_command_center_task_cards.json", repo_root),
        "p371_manifest": _read_csv_rows("artifacts/P371_biglotto_command_center_manifest.csv", repo_root),
        "p371_launchpad_text": _read_text("artifacts/P371_biglotto_command_center_launchpad.html", repo_root),
        "p371_quickstart_text": _read_text("artifacts/P371_biglotto_command_center_quickstart.md", repo_root),
        "p372_transcripts": _read_json("artifacts/P372_biglotto_command_center_route_transcripts.json", repo_root),
        "p372_route_health": _read_csv_rows("artifacts/P372_biglotto_command_center_route_health.csv", repo_root),
        "p372_route_coverage": _read_csv_rows("artifacts/P372_biglotto_command_center_route_coverage.csv", repo_root),
        "p372_failure_taxonomy": _read_csv_rows("artifacts/P372_biglotto_command_center_failure_taxonomy.csv", repo_root),
        "p372_smoke_bundle": _read_json("artifacts/P372_biglotto_command_center_smoke_bundle.json", repo_root),
        "p372_manifest": _read_csv_rows("artifacts/P372_biglotto_command_center_manifest.csv", repo_root),
    }


def _p371_status_summary(bundle: Mapping[str, object]) -> dict[str, object]:
    status = bundle["p371_status"]  # type: ignore[assignment]
    smoke_rows = bundle["p371_smoke"]  # type: ignore[assignment]
    route_rows = bundle["p371_routes"]  # type: ignore[assignment]
    status_map = status if isinstance(status, dict) else {}
    return {
        "task": status_map.get("task", "P371_biglotto_command_center"),
        "command_center_ready": status_map.get("command_center_ready") is True,
        "route_count": int(status_map.get("route_count", 0)),
        "route_catalog_rows": len(route_rows),  # type: ignore[arg-type]
        "smoke_pass_count": sum(1 for row in smoke_rows if row.get("status") == "PASS"),  # type: ignore[union-attr]
        "smoke_fail_count": sum(1 for row in smoke_rows if row.get("status") != "PASS"),  # type: ignore[union-attr]
        "p367_validation_fail_count": _int_from_nested(status_map, "p367_validation", "fail_count"),
        "p368_drift_fail_count": _int_from_nested(status_map, "p368_compatibility", "drift_fail_count"),
        "p369_validation_fail_count": _int_from_nested(status_map, "p369_validation", "fail_count"),
        "p370_recipe_fail_count": _int_from_nested(status_map, "p370_consumer", "recipe_fail_count"),
        "p370_prompt_safety_fail_count": _int_from_nested(status_map, "p370_consumer", "prompt_safety_fail_count"),
        "db_registry_deploy_status": status_map.get("db_registry_deploy_status", {}),
    }


def _int_from_nested(payload: Mapping[str, object], key: str, nested_key: str) -> int:
    nested = payload.get(key)
    if isinstance(nested, Mapping):
        return int(nested.get(nested_key, 0))
    return 0


def _p372_status_summary(bundle: Mapping[str, object]) -> dict[str, object]:
    smoke_bundle = bundle["p372_smoke_bundle"]  # type: ignore[assignment]
    route_health = bundle["p372_route_health"]  # type: ignore[assignment]
    coverage = bundle["p372_route_coverage"]  # type: ignore[assignment]
    smoke_map = smoke_bundle if isinstance(smoke_bundle, dict) else {}
    health_summary = smoke_map.get("route_health_summary", {})
    transcripts_summary = smoke_map.get("transcripts_summary", {})
    health_map = health_summary if isinstance(health_summary, Mapping) else {}
    transcripts_map = transcripts_summary if isinstance(transcripts_summary, Mapping) else {}
    return {
        "task": smoke_map.get("task", "P372_biglotto_command_center_route_replay"),
        "source_route_count": int(smoke_map.get("source_route_count", 0)),
        "route_health_row_count": len(route_health),  # type: ignore[arg-type]
        "route_health_pass_count": int(health_map.get("pass_count", 0)),
        "route_health_warn_count": int(health_map.get("warn_count", 0)),
        "route_health_fail_count": int(health_map.get("fail_count", 0)),
        "transcript_pass_count": int(transcripts_map.get("pass_count", 0)),
        "transcript_fail_count": int(transcripts_map.get("fail_count", 0)),
        "route_coverage": tuple(dict(row) for row in coverage),  # type: ignore[arg-type]
        "failure_taxonomy_class_count": len(bundle["p372_failure_taxonomy"]),  # type: ignore[arg-type]
    }


def _issue(
    issue_id: str,
    source: str,
    severity: str,
    route_id: str,
    issue_type: str,
    description: str,
    suggested_next_check: str,
    status: str,
) -> dict[str, str]:
    return {
        "issue_id": issue_id,
        "source": source,
        "severity": severity,
        "route_id": route_id,
        "issue_type": issue_type,
        "description": description,
        "suggested_next_check": suggested_next_check,
        "status": status,
    }


def build_issue_rows(bundle: Mapping[str, object]) -> tuple[dict[str, str], ...]:
    p371 = _p371_status_summary(bundle)
    p372 = _p372_status_summary(bundle)
    rows: list[dict[str, str]] = []

    if p371["command_center_ready"] is not True:
        rows.append(
            _issue(
                "P373-ISSUE-001",
                "P371 status",
                "FAIL",
                "",
                "command_center_not_ready",
                "P371 command_center_ready is not true.",
                "Run python3 -m recovered_strategies.biglotto.no_db_evidence_command_center --status and inspect missing_source_files.",
                "OPEN",
            )
        )
    if int(p371["smoke_fail_count"]) > 0:
        rows.append(
            _issue(
                "P373-ISSUE-002",
                "P371 smoke",
                "FAIL",
                "",
                "smoke_failure",
                f"P371 smoke has {p371['smoke_fail_count']} non-PASS rows.",
                "Run python3 -m recovered_strategies.biglotto.no_db_evidence_command_center --smoke and inspect failing smoke rows.",
                "OPEN",
            )
        )
    if int(p371["p370_prompt_safety_fail_count"]) > 0:
        rows.append(
            _issue(
                "P373-ISSUE-003",
                "P371 prompt safety",
                "FAIL",
                "",
                "prompt_template_safety_failure",
                f"P370 prompt safety has {p371['p370_prompt_safety_fail_count']} non-PASS rows.",
                "Inspect artifacts/P370_biglotto_agent_pack_consumer_prompt_safety_audit.csv.",
                "OPEN",
            )
        )

    for index, row in enumerate(bundle["p372_route_health"], start=1):  # type: ignore[index]
        if row.get("replay_status") != "PASS" or row.get("safety_status") != "PASS":
            rows.append(
                _issue(
                    f"P373-ROUTE-{index:03d}",
                    "P372 route_health",
                    "FAIL",
                    row.get("route_id", ""),
                    "route_replay_health_failure",
                    f"Route {row.get('route_id', '')} replay_status={row.get('replay_status', '')} safety_status={row.get('safety_status', '')}.",
                    "Run python3 -m recovered_strategies.biglotto.no_db_command_center_route_replay --health and inspect this route.",
                    "OPEN",
                )
            )

    coverage_rows = bundle["p372_route_coverage"]  # type: ignore[assignment]
    coverage = coverage_rows[0] if coverage_rows else {}
    if coverage.get("coverage_rate") != "1.0000":
        rows.append(
            _issue(
                "P373-ISSUE-004",
                "P372 coverage",
                "WARN",
                "",
                "route_coverage_incomplete",
                f"P372 route coverage rate is {coverage.get('coverage_rate', '')}.",
                "Run python3 -m recovered_strategies.biglotto.no_db_command_center_route_replay --coverage and inspect skipped routes.",
                "OPEN",
            )
        )

    if not rows:
        rows.append(
            _issue(
                "P373-INFO-001",
                "P373 operator console",
                "INFO",
                "",
                "no_operator_blocking_issues",
                "No FAIL or WARN operator-console issues were detected in merged P371/P372 artifacts.",
                "Continue with read-only artifact inspection or rerun focused regression tests if source artifacts change.",
                "INFO",
            )
        )
    return tuple(rows)


def _issue_counts(issue_rows: Sequence[Mapping[str, str]]) -> dict[str, int]:
    return {
        "INFO": sum(1 for row in issue_rows if row["severity"] == "INFO"),
        "WARN": sum(1 for row in issue_rows if row["severity"] == "WARN"),
        "FAIL": sum(1 for row in issue_rows if row["severity"] == "FAIL"),
    }


def _overall_health(issue_rows: Sequence[Mapping[str, str]]) -> str:
    counts = _issue_counts(issue_rows)
    if counts["FAIL"]:
        return "FAIL"
    if counts["WARN"]:
        return "WARN"
    return "PASS"


def _severity(status: str) -> str:
    return {"PASS": "low", "WARN": "medium", "FAIL": "high"}.get(status, "low")


def _badge(badge_id: str, label: str, status: str, summary: str) -> dict[str, str]:
    return {
        "badge_id": badge_id,
        "label": label,
        "status": status,
        "summary": summary,
        "severity": _severity(status),
    }


def build_badges(status: Mapping[str, object]) -> dict[str, object]:
    p371 = status["p371_command_center_status"]  # type: ignore[assignment]
    p372 = status["p372_route_replay_status"]  # type: ignore[assignment]
    coverage = status["route_coverage_summary"]  # type: ignore[assignment]
    prompt_failures = int(p371["p370_prompt_safety_fail_count"])  # type: ignore[index]
    artifact_status = "PASS" if status["required_source_file_count"] == status["required_source_files_present"] else "FAIL"
    smoke_status = "PASS" if int(p371["smoke_fail_count"]) == 0 else "FAIL"  # type: ignore[index]
    replay_status = "PASS" if int(p372["route_health_fail_count"]) == 0 else "FAIL"  # type: ignore[index]
    prompt_status = "PASS" if prompt_failures == 0 else "FAIL"
    badges = (
        _badge("overall_health", "Overall", str(status["overall_operator_health"]), f"Operator health is {status['overall_operator_health']}."),
        _badge("route_replay_health", "Route replay", replay_status, f"{p372['route_health_pass_count']} pass, {p372['route_health_fail_count']} fail."),
        _badge("smoke_health", "Smoke", smoke_status, f"{p371['smoke_pass_count']} P371 smoke rows pass; {p371['smoke_fail_count']} fail."),
        _badge("artifact_health", "Artifacts", artifact_status, f"{status['required_source_files_present']} of {status['required_source_file_count']} source artifacts present."),
        _badge("prompt_template_safety", "Prompt safety", prompt_status, f"{prompt_failures} prompt-safety failures; action cards are templates only."),
    )
    return {
        "task": TASK,
        "generated_at": GENERATED_AT,
        "source_baseline": SOURCE_BASELINE,
        "coverage_rate": coverage.get("coverage_rate", ""),
        "badges": badges,
        "statements": STATEMENTS,
        "scope_lines": DISCLAIMER_LINES,
    }


def build_status(repo_root: Path | None = None) -> dict[str, object]:
    bundle = load_source_bundle(repo_root)
    issues = build_issue_rows(bundle)
    coverage_rows = bundle["p372_route_coverage"]  # type: ignore[assignment]
    coverage = dict(coverage_rows[0]) if coverage_rows else {}
    p371_summary = _p371_status_summary(bundle)
    p372_summary = _p372_status_summary(bundle)
    required_paths = verify_required_evidence(repo_root)
    return {
        "task": TASK,
        "generated_at": GENERATED_AT,
        "source_baseline": SOURCE_BASELINE,
        "source_artifacts": REQUIRED_SOURCE_ARTIFACTS,
        "required_source_file_count": len(REQUIRED_SOURCE_ARTIFACTS),
        "required_source_files_present": len(required_paths),
        "p371_command_center_status": p371_summary,
        "p372_route_replay_status": p372_summary,
        "route_coverage_summary": coverage,
        "issue_counts": _issue_counts(issues),
        "overall_operator_health": _overall_health(issues),
        "statements": STATEMENTS,
        "scope_lines": DISCLAIMER_LINES,
    }


def _action_card(card_id: str, title: str, command: str, objective: str) -> dict[str, object]:
    return {
        "card_id": card_id,
        "title": title,
        "objective": objective,
        "local_command": command,
        "template_not_standing_authorization": True,
        "no_db_open_write": True,
        "no_adapter_calls": True,
        "no_new_scoring": True,
        "no_production_registry_import": True,
        "no_deploy": True,
        "scope_statement": SCOPE_STATEMENT,
        "operator_note": (
            "This action card is a template only, not standing authorization. "
            "Stop before any DB open/write, adapter call, new scoring, production registry import, deploy, betting advice, or future-performance claim."
        ),
    }


def build_actions() -> dict[str, object]:
    cards = (
        _action_card(
            "run_command_center_status",
            "Run command center status",
            "python3 -m recovered_strategies.biglotto.no_db_evidence_command_center --status",
            "Inspect the committed P371 no-DB command center readiness summary.",
        ),
        _action_card(
            "run_route_replay_validate",
            "Run route replay validate",
            "python3 -m recovered_strategies.biglotto.no_db_command_center_route_replay --validate",
            "Validate P372 route replay artifacts without opening DB files or calling adapters.",
        ),
        _action_card(
            "inspect_failing_routes",
            "Inspect failing routes",
            "python3 -m recovered_strategies.biglotto.no_db_command_center_route_replay --health",
            "Review route health rows and focus only on WARN/FAIL rows if present.",
        ),
        _action_card(
            "inspect_artifact_inventory",
            "Inspect artifact inventory",
            "python3 -m recovered_strategies.biglotto.no_db_evidence_command_center --list-artifacts",
            "Review P371 source/output artifact inventory and SHA256 values.",
        ),
        _action_card(
            "rerun_regression_tests",
            "Rerun regression tests",
            "python3 -m pytest tests/test_p371_biglotto_evidence_command_center.py tests/test_p372_biglotto_command_center_route_replay.py tests/test_p373_biglotto_command_center_operator_console.py",
            "Rerun focused no-DB command center regression coverage.",
        ),
    )
    return {
        "task": TASK,
        "generated_at": GENERATED_AT,
        "source_baseline": SOURCE_BASELINE,
        "action_cards": cards,
        "statements": STATEMENTS,
        "scope_lines": DISCLAIMER_LINES,
    }


def _source_inventory(repo_root: Path | None = None) -> tuple[dict[str, str], ...]:
    rows: list[dict[str, str]] = []
    for relpath in REQUIRED_SOURCE_ARTIFACTS:
        path = _artifact_path(relpath, repo_root)
        rows.append(
            {
                "path": relpath,
                "sha256": sha256_file(path),
                "kind": "source_module" if relpath.endswith(".py") else "source_artifact",
            }
        )
    return tuple(rows)


def _html_table(columns: Sequence[str], rows: Iterable[Mapping[str, object]]) -> str:
    head = "".join(f"<th>{html.escape(column)}</th>" for column in columns)
    body = []
    for row in rows:
        cells = "".join(f"<td>{html.escape(str(row.get(column, '')))}</td>" for column in columns)
        body.append(f"<tr>{cells}</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def build_console_html(
    status: Mapping[str, object],
    badges: Mapping[str, object],
    issue_rows: Sequence[Mapping[str, str]],
    actions: Mapping[str, object],
    repo_root: Path | None = None,
) -> str:
    badge_cards = []
    for badge in badges["badges"]:  # type: ignore[index]
        badge_cards.append(
            '<section class="badge">'
            f"<div class=\"badge-label\">{html.escape(str(badge['label']))}</div>"
            f"<div class=\"badge-status {html.escape(str(badge['status']).lower())}\">{html.escape(str(badge['status']))}</div>"
            f"<p>{html.escape(str(badge['summary']))}</p>"
            f"<small>Severity: {html.escape(str(badge['severity']))}</small>"
            "</section>"
        )
    coverage = status["route_coverage_summary"]  # type: ignore[assignment]
    inventory_rows = _source_inventory(repo_root)
    action_cards = []
    for card in actions["action_cards"]:  # type: ignore[index]
        action_cards.append(
            '<section class="action">'
            f"<h3>{html.escape(str(card['title']))}</h3>"
            f"<p>{html.escape(str(card['objective']))}</p>"
            f"<pre>{html.escape(str(card['local_command']))}</pre>"
            f"<small>{html.escape(str(card['operator_note']))}</small>"
            "</section>"
        )
    commands = (
        "python3 -m recovered_strategies.biglotto.no_db_command_center_operator_console --status",
        "python3 -m recovered_strategies.biglotto.no_db_command_center_operator_console --badges",
        "python3 -m recovered_strategies.biglotto.no_db_command_center_operator_console --issues",
        "python3 -m recovered_strategies.biglotto.no_db_command_center_operator_console --actions",
        "python3 -m recovered_strategies.biglotto.no_db_command_center_operator_console --validate",
    )
    command_items = "".join(f"<li><code>{html.escape(command)}</code></li>" for command in commands)
    disclaimer = " ".join(DISCLAIMER_LINES)
    css = textwrap.dedent(
        """
        body { margin: 0; font-family: Arial, sans-serif; color: #1f2933; background: #f6f7f9; }
        header { background: #14213d; color: #fff; padding: 24px 32px; }
        main { max-width: 1180px; margin: 0 auto; padding: 24px; }
        .banner { background: #fff4d6; border: 1px solid #d6a400; padding: 12px 16px; margin: 0 0 20px; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 12px; }
        .badge, .action, .panel { background: #fff; border: 1px solid #d9dee7; border-radius: 6px; padding: 14px; }
        .badge-label { font-size: 12px; text-transform: uppercase; color: #51606f; }
        .badge-status { font-size: 24px; font-weight: 700; margin: 4px 0; }
        .pass { color: #146c43; } .warn { color: #9a6700; } .fail { color: #b42318; }
        table { width: 100%; border-collapse: collapse; background: #fff; margin: 10px 0 24px; }
        th, td { border: 1px solid #d9dee7; padding: 8px; text-align: left; vertical-align: top; }
        th { background: #eef2f7; }
        pre, code { white-space: pre-wrap; overflow-wrap: anywhere; }
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
          <title>P373 Big Lotto no-DB command center operator console</title>
          <style>{css}</style>
        </head>
        <body>
          <header>
            <h1>P373 Big Lotto no-DB command center operator console</h1>
            <p>Overall operator health: <strong>{html.escape(str(status["overall_operator_health"]))}</strong></p>
          </header>
          <main>
            <section class="banner"><strong>Scope:</strong> {html.escape(disclaimer)}</section>
            <h2>Health badges</h2>
            <div class="grid">{''.join(badge_cards)}</div>
            <h2>Route coverage summary</h2>
            {_html_table(("total_routes", "replayed_routes", "skipped_routes", "pass_count", "warn_count", "fail_count", "coverage_rate"), (coverage,))}
            <h2>Issue table</h2>
            {_html_table(ISSUE_COLUMNS, issue_rows)}
            <h2>Action cards</h2>
            <div class="grid">{''.join(action_cards)}</div>
            <h2>Source artifact inventory</h2>
            {_html_table(("path", "kind", "sha256"), inventory_rows)}
            <h2>Local commands</h2>
            <section class="panel"><ul>{command_items}</ul></section>
          </main>
        </body>
        </html>
        """
    ).lstrip()


def _artifact_contents_without_manifest(output: OperatorConsoleOutput) -> dict[str, str]:
    return {
        "operator_status": _json_text(output.status),
        "operator_badges": _json_text(output.badges),
        "operator_issues": _csv_text(ISSUE_COLUMNS, output.issue_rows),
        "operator_actions": _json_text(output.actions),
        "operator_console": output.console_html,
    }


def _artifact_contents(output: OperatorConsoleOutput) -> dict[str, str]:
    contents = _artifact_contents_without_manifest(output)
    contents["operator_manifest"] = _csv_text(MANIFEST_COLUMNS, output.manifest_rows)
    return contents


def _output_counts(role: str, text: str) -> tuple[str, str]:
    if role in {"operator_issues", "operator_manifest"}:
        return str(len(tuple(csv.DictReader(text.splitlines())))), ""
    if role in {"operator_status", "operator_badges", "operator_actions"}:
        return "", "1"
    if role == "operator_console":
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
                "details": "P373 source evidence read from merged P371/P372 command-center artifacts only.",
                "scope_statement": SCOPE_STATEMENT,
            }
        )
    for role, basename in P373_ARTIFACT_BASENAMES.items():
        text = output_texts_without_manifest.get(role, "")
        row_count, object_count = _output_counts(role, text)
        digest = sha256_bytes(text.encode("utf-8")) if text else ""
        if role == "operator_manifest":
            row_count = str(len(REQUIRED_SOURCE_ARTIFACTS) + len(P373_ARTIFACT_BASENAMES) + 3)
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
                "details": "P373 generated no-DB operator-console artifact.",
                "scope_statement": SCOPE_STATEMENT,
            }
        )
    for role, details in (
        ("no_db_open_write", "No DB open/write was performed by P373."),
        ("no_adapter_calls", "No adapter calls were performed by P373."),
        ("no_new_scoring", "No new scoring, scoring cohort, shape-only scoring, blocked-target scoring, or blended leaderboard was created by P373."),
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


def validate_operator_console(
    output: OperatorConsoleOutput | None = None,
    repo_root: Path | None = None,
    include_determinism: bool = True,
) -> tuple[dict[str, str], ...]:
    current = output if output is not None else run_operator_console(repo_root, include_validation=False)
    text = "\n".join(_artifact_contents(current).values()).lower()
    found = [phrase for phrase in FORBIDDEN_AUTHORIZATION_PHRASES if phrase in text]
    badge_ids = {badge["badge_id"] for badge in current.badges["badges"]}  # type: ignore[index]
    rows = [
        _check("required_p371_p372_evidence_exists", len(verify_required_evidence(repo_root)) == len(REQUIRED_SOURCE_ARTIFACTS), len(REQUIRED_SOURCE_ARTIFACTS), len(REQUIRED_SOURCE_ARTIFACTS), "Required P371/P372 modules, artifacts, and tests are present."),
        _check("operator_status_json_schema", set(current.status) >= {"source_baseline", "p371_command_center_status", "p372_route_replay_status", "route_coverage_summary", "issue_counts", "overall_operator_health", "statements"}, "required status keys", sorted(current.status), "Status JSON includes required operator-health fields."),
        _check("operator_health_pass_warn_fail", current.status["overall_operator_health"] in {"PASS", "WARN", "FAIL"}, "PASS/WARN/FAIL", current.status["overall_operator_health"], "Overall health uses the required compact enum."),
        _check("badges_json_schema", badge_ids == {"overall_health", "route_replay_health", "smoke_health", "artifact_health", "prompt_template_safety"}, "five required badge ids", sorted(badge_ids), "Badges JSON includes required deterministic badge objects."),
        _check("issues_csv_schema", bool(current.issue_rows) and tuple(current.issue_rows[0]) == ISSUE_COLUMNS, ISSUE_COLUMNS, tuple(current.issue_rows[0]) if current.issue_rows else (), "Issues CSV uses required columns."),
        _check("actions_json_schema", len(current.actions["action_cards"]) == 5 and all(card["template_not_standing_authorization"] is True for card in current.actions["action_cards"]), "5 template-only action cards", len(current.actions["action_cards"]), "Action cards are template-only and cover required operator actions."),
        _check("console_html_self_contained", current.console_html.startswith("<!doctype html>") and "<script" not in current.console_html.lower() and "Source artifact inventory" in current.console_html, "self-contained html", "present", "Console HTML includes badges, coverage, issues, actions, inventory, and commands."),
        _check("manifest_csv_schema", bool(current.manifest_rows) and tuple(current.manifest_rows[0]) == MANIFEST_COLUMNS, MANIFEST_COLUMNS, tuple(current.manifest_rows[0]) if current.manifest_rows else (), "Manifest rows use required columns."),
        _check("manifest_source_artifacts_recorded", sum(1 for row in current.manifest_rows if row["artifact_group"] == "source") == len(REQUIRED_SOURCE_ARTIFACTS), len(REQUIRED_SOURCE_ARTIFACTS), sum(1 for row in current.manifest_rows if row["artifact_group"] == "source"), "Manifest records all source artifacts with SHA256 values."),
        _check("generated_outputs_do_not_authorize_forbidden_actions", not found, "absent", ";".join(found) if found else "absent", "P373 outputs do not authorize DB writes, adapter execution, scoring, deploy, force operations, status changes, betting advice, or future prediction claims."),
        _check("generated_outputs_include_safety_constraints", all(line.lower() in text for line in DISCLAIMER_LINES), "all scope lines", "present", "Outputs include no-DB/no-adapter/no-scoring/no-deploy constraints."),
    ]
    if include_determinism:
        first = run_operator_console(repo_root, include_validation=False)
        second = run_operator_console(repo_root, include_validation=False)
        rows.append(
            _check(
                "deterministic_double_run_equality",
                _artifact_contents(first) == _artifact_contents(second),
                "equal",
                "equal" if _artifact_contents(first) == _artifact_contents(second) else "different",
                "P373 generated rows and artifacts are deterministic across two runs.",
            )
        )
    return tuple(rows)


def run_operator_console(repo_root: Path | None = None, include_validation: bool = True) -> OperatorConsoleOutput:
    status = build_status(repo_root)
    badges = build_badges(status)
    issues = build_issue_rows(load_source_bundle(repo_root))
    actions = build_actions()
    console = build_console_html(status, badges, issues, actions, repo_root)
    with_console = OperatorConsoleOutput(status, badges, issues, actions, console, (), ())
    manifest = build_manifest_rows(_artifact_contents_without_manifest(with_console), repo_root)
    partial = OperatorConsoleOutput(status, badges, issues, actions, console, manifest, ())
    validation = validate_operator_console(partial, repo_root, include_determinism=True) if include_validation else ()
    return OperatorConsoleOutput(status, badges, issues, actions, console, manifest, validation)


def _assert_deterministic(first: OperatorConsoleOutput, second: OperatorConsoleOutput) -> None:
    if _artifact_contents(first) != _artifact_contents(second):
        raise RuntimeError("determinism double-run mismatch: P373 operator console artifacts are not reproducible")


def write_artifacts(output: OperatorConsoleOutput, artifacts_dir: Path | None = None) -> dict[str, Path]:
    directory = Path(artifacts_dir) if artifacts_dir is not None else REPO_ROOT / "artifacts"
    directory.mkdir(parents=True, exist_ok=True)
    contents = _artifact_contents(output)
    paths = {key: directory / basename for key, basename in P373_ARTIFACT_BASENAMES.items()}
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
    parser.add_argument("--generate", action="store_true", help="write all P373 operator console artifacts")
    parser.add_argument("--status", action="store_true", help="emit operator status JSON")
    parser.add_argument("--badges", action="store_true", help="emit compact health badges JSON")
    parser.add_argument("--issues", action="store_true", help="emit operator issues CSV")
    parser.add_argument("--actions", action="store_true", help="emit template-only safe action cards JSON")
    parser.add_argument("--console", action="store_true", help="emit self-contained operator console HTML")
    parser.add_argument("--validate", action="store_true", help="emit P373 validation rows as CSV")
    args = parser.parse_args(argv)

    if args.status:
        _print_json(build_status())
    elif args.badges:
        _print_json(build_badges(build_status()))
    elif args.issues:
        _print_csv(ISSUE_COLUMNS, build_issue_rows(load_source_bundle()))
    elif args.actions:
        _print_json(build_actions())
    elif args.console:
        output = run_operator_console()
        print(output.console_html, end="")
    elif args.validate:
        _print_csv(VALIDATION_COLUMNS, validate_operator_console())
    else:
        first = run_operator_console()
        second = run_operator_console()
        _assert_deterministic(first, second)
        paths = write_artifacts(first, args.artifacts_dir)
        print("P373 Big Lotto no-DB command center operator console: determinism double-run PASS")
        print(f"overall operator health: {first.status['overall_operator_health']}")
        print(f"validation rows: {len(first.validation_rows)}")
        print(f"validation failures: {sum(1 for row in first.validation_rows if row['status'] == 'FAIL')}")
        print("No DB was opened or written; no adapters were called; no new scoring was created; no production registry import or deploy was performed.")
        print("Operator action cards are templates, not standing authorization.")
        print("Historical descriptive evidence only; no betting advice; no future prediction guarantee.")
        for key, path in sorted(paths.items()):
            print(f"{key}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
