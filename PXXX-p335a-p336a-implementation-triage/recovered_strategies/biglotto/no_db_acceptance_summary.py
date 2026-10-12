"""P376 Big Lotto no-DB operator acceptance compact summary.

This module reads only merged P371/P372/P373/P374/P375 command-center and
operator-acceptance artifacts and emits a compact machine-readable and
human-readable acceptance layer. It does not open or write a DB, call adapters,
create new scoring cohorts, import production registries, deploy, provide
betting advice, or make future-performance claims.
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
TASK = "P376_biglotto_acceptance_summary"
GENERATED_AT = "DETERMINISTIC_PLACEHOLDER"
SOURCE_BASELINE = {
    "required_origin_main_merge_commit": "602fc1ead6cc86784db03612e76e9853c0c8de75",
    "p371_source_merge_baseline": "30e4120060e41e8a6f7cf529c28d9b490c01f70b",
    "p372_source_baseline": "1a971bd14a11de3e6e5967cfb543ab7069e97100",
    "p373_source_merge_baseline": "992c0c33ca9e3db1bbe81914cd1de82b21c06bde",
    "p374_merge_baseline": "e7a9a16224d3fec10500283bafef38701e1d0d21",
    "p375_merge_baseline": "602fc1ead6cc86784db03612e76e9853c0c8de75",
    "summary_mode": "read_only_no_db_compact_acceptance_layer",
}

P376_ARTIFACT_BASENAMES = {
    "badges": "P376_biglotto_acceptance_summary_badges.json",
    "status_block": "P376_biglotto_acceptance_summary_status_block.md",
    "agent_json": "P376_biglotto_acceptance_summary_agent.json",
    "release_csv": "P376_biglotto_acceptance_summary_release.csv",
    "html": "P376_biglotto_acceptance_summary.html",
    "manifest": "P376_biglotto_acceptance_summary_manifest.csv",
}

REQUIRED_SOURCE_ARTIFACTS = (
    "recovered_strategies/biglotto/no_db_operator_acceptance.py",
    "recovered_strategies/biglotto/no_db_operator_history.py",
    "recovered_strategies/biglotto/no_db_command_center_operator_console.py",
    "recovered_strategies/biglotto/no_db_command_center_route_replay.py",
    "recovered_strategies/biglotto/no_db_evidence_command_center.py",
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
    "artifacts/P375_biglotto_operator_acceptance_decision.json",
    "artifacts/P375_biglotto_operator_acceptance_checklist.csv",
    "artifacts/P375_biglotto_operator_acceptance_failure_matrix.csv",
    "artifacts/P375_biglotto_operator_acceptance_risk_notes.json",
    "artifacts/P375_biglotto_operator_acceptance_portal.html",
    "artifacts/P375_biglotto_operator_acceptance_manifest.csv",
    "tests/test_p375_biglotto_operator_acceptance.py",
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
    "This is not production release approval.",
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
    "production_release_approval": False,
}

BADGE_REQUIRED_KEYS = ("label", "status", "severity", "summary")
RELEASE_COLUMNS = ("metric", "value", "source_artifact", "status", "notes")
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
    "no_deploy",
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
class AcceptanceSummaryOutput:
    badges: dict[str, object]
    status_block: str
    agent_json: dict[str, object]
    release_rows: tuple[dict[str, str], ...]
    html_summary: str
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


def _first_row(rows: Sequence[Mapping[str, str]]) -> Mapping[str, str]:
    return rows[0] if rows else {}


def _int_text(value: object) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return 0


def verify_required_evidence(repo_root: Path | None = None) -> tuple[Path, ...]:
    paths = tuple(_artifact_path(relpath, repo_root) for relpath in REQUIRED_SOURCE_ARTIFACTS)
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise RuntimeError(f"required P371/P372/P373/P374/P375 acceptance evidence missing: {missing}")
    return paths


def source_inventory(repo_root: Path | None = None) -> tuple[dict[str, str], ...]:
    verify_required_evidence(repo_root)
    rows = []
    for relpath in REQUIRED_SOURCE_ARTIFACTS:
        rows.append(
            {
                "path": relpath,
                "kind": "source_module_or_test" if relpath.endswith(".py") else "source_artifact",
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
        "p373_status": _read_json("artifacts/P373_biglotto_command_center_operator_status.json", repo_root),
        "p373_badges": _read_json("artifacts/P373_biglotto_command_center_operator_badges.json", repo_root),
        "p373_issues": _read_csv_rows("artifacts/P373_biglotto_command_center_operator_issues.csv", repo_root),
        "p374_snapshot": _read_json("artifacts/P374_biglotto_operator_health_snapshot.json", repo_root),
        "p374_delta": _read_csv_rows("artifacts/P374_biglotto_operator_status_delta.csv", repo_root),
        "p375_decision": _read_json("artifacts/P375_biglotto_operator_acceptance_decision.json", repo_root),
        "p375_checklist": _read_csv_rows("artifacts/P375_biglotto_operator_acceptance_checklist.csv", repo_root),
        "p375_failure_matrix": _read_csv_rows("artifacts/P375_biglotto_operator_acceptance_failure_matrix.csv", repo_root),
        "p375_risk_notes": _read_json("artifacts/P375_biglotto_operator_acceptance_risk_notes.json", repo_root),
    }


def build_badges(repo_root: Path | None = None) -> dict[str, object]:
    bundle = load_source_bundle(repo_root)
    p375_decision = _as_mapping(bundle["p375_decision"])
    p373_status = _as_mapping(bundle["p373_status"])
    p374_snapshot = _as_mapping(bundle["p374_snapshot"])
    route_coverage = _first_row(bundle["p372_coverage"])  # type: ignore[arg-type]
    issue_counts = _as_mapping(p375_decision.get("issue_counts"))
    blocking_count = _int_text(p375_decision.get("blocking_issue_count", 0))
    p373_counts = _as_mapping(issue_counts.get("p373_issue_counts"))
    p374_counts = _as_mapping(issue_counts.get("p374_issue_counts"))
    accepted = p375_decision.get("accepted") is True
    acceptance_status = str(p375_decision.get("overall_acceptance", "UNKNOWN"))
    operator_health = str(
        _as_mapping(p374_snapshot.get("operator_health")).get(
            "overall_operator_health",
            p373_status.get("overall_operator_health", "UNKNOWN"),
        )
    )
    route_fail_count = _int_text(route_coverage.get("fail_count", 0))
    route_warn_count = _int_text(route_coverage.get("warn_count", 0))
    route_status = "FAIL" if route_fail_count else ("WARN" if route_warn_count else "PASS")
    badges = {
        "acceptance": {
            "label": "Acceptance",
            "status": acceptance_status,
            "severity": "low" if accepted else "high",
            "summary": f"P375 acceptance accepted={accepted}; blocking issues={blocking_count}.",
        },
        "operator_health": {
            "label": "Operator health",
            "status": operator_health,
            "severity": "low" if operator_health == "PASS" else "high",
            "summary": f"P373/P374 operator health is {operator_health}.",
        },
        "route_coverage": {
            "label": "Route coverage",
            "status": route_status,
            "severity": "low" if route_status == "PASS" else "medium",
            "summary": (
                f"{route_coverage.get('replayed_routes', '0')} of {route_coverage.get('total_routes', '0')} "
                f"routes replayed; coverage={route_coverage.get('coverage_rate', '')}; fail={route_coverage.get('fail_count', '')}."
            ),
        },
        "issue": {
            "label": "Blocking issues",
            "status": "PASS" if blocking_count == 0 else "FAIL",
            "severity": "low" if blocking_count == 0 else "high",
            "summary": (
                f"Blocking issues={blocking_count}; "
                f"P373 FAIL/WARN={p373_counts.get('FAIL', 0)}/{p373_counts.get('WARN', 0)}; "
                f"P374 FAIL/WARN={p374_counts.get('FAIL', 0)}/{p374_counts.get('WARN', 0)}."
            ),
        },
        "no_db": {
            "label": "No DB",
            "status": "PASS",
            "severity": "low",
            "summary": "No DB open/write; source artifacts are committed files only.",
        },
        "no_adapter_call": {
            "label": "No adapter calls",
            "status": "PASS",
            "severity": "low",
            "summary": "No adapter calls; summary reads merged no-DB evidence artifacts only.",
        },
        "no_new_scoring": {
            "label": "No new scoring",
            "status": "PASS",
            "severity": "low",
            "summary": "No new scoring, no new scoring cohort, no blended leaderboard.",
        },
    }
    return {
        "task": TASK,
        "generated_at": GENERATED_AT,
        "source_baseline": SOURCE_BASELINE,
        "badges": badges,
        "statements": STATEMENTS,
        "scope_lines": DISCLAIMER_LINES,
    }


def build_release_rows(badges: Mapping[str, object] | None = None, repo_root: Path | None = None) -> tuple[dict[str, str], ...]:
    bundle = load_source_bundle(repo_root)
    badge_payload = badges if badges is not None else build_badges(repo_root)
    badge_map = _as_mapping(badge_payload.get("badges"))
    p375_decision = _as_mapping(bundle["p375_decision"])
    p373_status = _as_mapping(bundle["p373_status"])
    p374_snapshot = _as_mapping(bundle["p374_snapshot"])
    route_coverage = _first_row(bundle["p372_coverage"])  # type: ignore[arg-type]
    rows = [
        {
            "metric": "acceptance_decision",
            "value": str(p375_decision.get("overall_acceptance", "")),
            "source_artifact": "artifacts/P375_biglotto_operator_acceptance_decision.json",
            "status": str(_as_mapping(badge_map.get("acceptance")).get("status", "")),
            "notes": "Compact summary of the merged P375 acceptance decision.",
        },
        {
            "metric": "accepted",
            "value": str(p375_decision.get("accepted", "")),
            "source_artifact": "artifacts/P375_biglotto_operator_acceptance_decision.json",
            "status": str(_as_mapping(badge_map.get("acceptance")).get("status", "")),
            "notes": "Historical descriptive gate state only.",
        },
        {
            "metric": "operator_health",
            "value": str(
                _as_mapping(p374_snapshot.get("operator_health")).get(
                    "overall_operator_health",
                    p373_status.get("overall_operator_health", ""),
                )
            ),
            "source_artifact": "artifacts/P374_biglotto_operator_health_snapshot.json",
            "status": str(_as_mapping(badge_map.get("operator_health")).get("status", "")),
            "notes": "P373/P374 operator-health state.",
        },
        {
            "metric": "route_coverage_rate",
            "value": str(route_coverage.get("coverage_rate", "")),
            "source_artifact": "artifacts/P372_biglotto_command_center_route_coverage.csv",
            "status": str(_as_mapping(badge_map.get("route_coverage")).get("status", "")),
            "notes": f"{route_coverage.get('replayed_routes', '')}/{route_coverage.get('total_routes', '')} routes replayed.",
        },
        {
            "metric": "blocking_issue_count",
            "value": str(p375_decision.get("blocking_issue_count", "")),
            "source_artifact": "artifacts/P375_biglotto_operator_acceptance_decision.json",
            "status": str(_as_mapping(badge_map.get("issue")).get("status", "")),
            "notes": "P375 blocking issue count.",
        },
        {
            "metric": "source_artifact_count",
            "value": str(len(REQUIRED_SOURCE_ARTIFACTS)),
            "source_artifact": "P371/P372/P373/P374/P375 merged evidence inventory",
            "status": "PASS",
            "notes": "All required source modules, tests, and artifacts are present.",
        },
        {
            "metric": "no_db_open_write",
            "value": "YES",
            "source_artifact": "P376 summary generator statement",
            "status": str(_as_mapping(badge_map.get("no_db")).get("status", "")),
            "notes": "No DB open/write.",
        },
        {
            "metric": "no_adapter_calls",
            "value": "YES",
            "source_artifact": "P376 summary generator statement",
            "status": str(_as_mapping(badge_map.get("no_adapter_call")).get("status", "")),
            "notes": "No adapter calls.",
        },
        {
            "metric": "no_new_scoring",
            "value": "YES",
            "source_artifact": "P376 summary generator statement",
            "status": str(_as_mapping(badge_map.get("no_new_scoring")).get("status", "")),
            "notes": "No new scoring cohort, shape-only scoring, blocked-target scoring, or blended leaderboard.",
        },
        {
            "metric": "not_production_release_approval",
            "value": "YES",
            "source_artifact": "P376 summary generator statement",
            "status": "PASS",
            "notes": "This compact layer is not production release approval.",
        },
    ]
    return tuple(rows)


def build_status_block(
    badges: Mapping[str, object] | None = None,
    release_rows: Sequence[Mapping[str, str]] | None = None,
    repo_root: Path | None = None,
) -> str:
    badge_payload = badges if badges is not None else build_badges(repo_root)
    rows = tuple(release_rows) if release_rows is not None else build_release_rows(badge_payload, repo_root)
    by_metric = {row["metric"]: row for row in rows}
    badge_map = _as_mapping(badge_payload.get("badges"))
    caveats = "\n".join(f"- {line}" for line in DISCLAIMER_LINES)
    return (
        "# P376 Big Lotto no-DB acceptance summary\n\n"
        f"- Acceptance decision: {by_metric['acceptance_decision']['value']} (accepted={by_metric['accepted']['value']})\n"
        f"- Source baseline: {SOURCE_BASELINE['required_origin_main_merge_commit']}\n"
        f"- Operator health: {by_metric['operator_health']['value']}\n"
        f"- Route coverage: {by_metric['route_coverage_rate']['value']}\n"
        f"- Blocking issue count: {by_metric['blocking_issue_count']['value']}\n"
        f"- Badge statuses: acceptance={_as_mapping(badge_map.get('acceptance')).get('status', '')}; "
        f"operator_health={_as_mapping(badge_map.get('operator_health')).get('status', '')}; "
        f"route_coverage={_as_mapping(badge_map.get('route_coverage')).get('status', '')}; "
        f"issue={_as_mapping(badge_map.get('issue')).get('status', '')}; "
        f"no_db={_as_mapping(badge_map.get('no_db')).get('status', '')}; "
        f"no_adapter_call={_as_mapping(badge_map.get('no_adapter_call')).get('status', '')}; "
        f"no_new_scoring={_as_mapping(badge_map.get('no_new_scoring')).get('status', '')}\n\n"
        "Safe caveats:\n"
        f"{caveats}\n"
    )


def build_agent_json(
    badges: Mapping[str, object] | None = None,
    release_rows: Sequence[Mapping[str, str]] | None = None,
    repo_root: Path | None = None,
) -> dict[str, object]:
    bundle = load_source_bundle(repo_root)
    badge_payload = badges if badges is not None else build_badges(repo_root)
    rows = tuple(release_rows) if release_rows is not None else build_release_rows(badge_payload, repo_root)
    p375_decision = _as_mapping(bundle["p375_decision"])
    return {
        "task": TASK,
        "generated_at": GENERATED_AT,
        "acceptance_summary": {
            "decision": p375_decision.get("overall_acceptance", ""),
            "accepted": p375_decision.get("accepted") is True,
            "source_baseline": SOURCE_BASELINE,
            "operator_health": next(row["value"] for row in rows if row["metric"] == "operator_health"),
            "route_coverage_rate": next(row["value"] for row in rows if row["metric"] == "route_coverage_rate"),
            "blocking_issue_count": _int_text(p375_decision.get("blocking_issue_count", 0)),
            "badges": badge_payload.get("badges", {}),
            "statements": STATEMENTS,
            "scope_lines": DISCLAIMER_LINES,
        },
        "source_artifacts": source_inventory(repo_root),
        "release_metrics": tuple(rows),
        "recommended_safe_next_action_categories": (
            "read_only_review",
            "artifact_schema_verification",
            "copy_paste_status_reporting",
            "local_no_db_validation",
        ),
        "stop_boundaries": (
            "Stop before DB open/write, migration, backfill, or generated DB rows.",
            "Stop before adapter calls or any new strategy scoring.",
            "Stop before production registry import, deploy, or external publication.",
            "Stop before strategy status changes, force operations, betting advice, or future-performance claims.",
            "Stop before treating this compact layer as production release approval.",
        ),
        "not_authorized": tuple(line for line in DISCLAIMER_LINES if line.startswith("No ") or line.startswith("This ")),
    }


def _html_table(columns: Sequence[str], rows: Iterable[Mapping[str, object]]) -> str:
    head = "".join(f"<th>{html.escape(column)}</th>" for column in columns)
    body = []
    for row in rows:
        cells = "".join(f"<td>{html.escape(str(row.get(column, '')))}</td>" for column in columns)
        body.append(f"<tr>{cells}</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def build_html_summary(
    badges: Mapping[str, object],
    status_block: str,
    agent_json: Mapping[str, object],
    release_rows: Sequence[Mapping[str, str]],
) -> str:
    badge_rows = []
    for badge_id, badge in sorted(_as_mapping(badges.get("badges")).items()):
        badge_map = _as_mapping(badge)
        badge_rows.append(
            {
                "badge": badge_id,
                "label": badge_map.get("label", ""),
                "status": badge_map.get("status", ""),
                "severity": badge_map.get("severity", ""),
                "summary": badge_map.get("summary", ""),
            }
        )
    source_rows = source_inventory()
    commands = (
        "python3 -m recovered_strategies.biglotto.no_db_acceptance_summary --generate",
        "python3 -m recovered_strategies.biglotto.no_db_acceptance_summary --badges",
        "python3 -m recovered_strategies.biglotto.no_db_acceptance_summary --status-block",
        "python3 -m recovered_strategies.biglotto.no_db_acceptance_summary --agent-json",
        "python3 -m recovered_strategies.biglotto.no_db_acceptance_summary --release-csv",
        "python3 -m recovered_strategies.biglotto.no_db_acceptance_summary --html",
        "python3 -m recovered_strategies.biglotto.no_db_acceptance_summary --validate",
    )
    command_items = "".join(f"<li><code>{html.escape(command)}</code></li>" for command in commands)
    risk_items = "".join(f"<li>{html.escape(str(item))}</li>" for item in agent_json.get("stop_boundaries", ()))
    disclaimer_items = "".join(f"<li>{html.escape(line)}</li>" for line in DISCLAIMER_LINES)
    css = textwrap.dedent(
        """
        body { margin: 0; font-family: Arial, sans-serif; color: #1f2933; background: #f7f8fa; }
        header { background: #153a5b; color: #fff; padding: 24px 32px; }
        main { max-width: 1200px; margin: 0 auto; padding: 24px; }
        .banner { background: #fff4cc; border: 1px solid #c99700; padding: 12px 16px; margin-bottom: 18px; }
        .panel { background: #fff; border: 1px solid #d9dee7; border-radius: 6px; padding: 14px; margin-bottom: 18px; }
        table { width: 100%; border-collapse: collapse; background: #fff; margin: 10px 0 24px; }
        th, td { border: 1px solid #d9dee7; padding: 8px; text-align: left; vertical-align: top; }
        th { background: #edf2f7; }
        code, pre { white-space: pre-wrap; overflow-wrap: anywhere; }
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
          <title>P376 Big Lotto no-DB acceptance summary</title>
          <style>{css}</style>
        </head>
        <body>
          <header>
            <h1>P376 Big Lotto no-DB acceptance summary</h1>
            <p>Acceptance badge: <strong>{html.escape(str(_as_mapping(_as_mapping(badges.get("badges")).get("acceptance")).get("status", "")))}</strong></p>
          </header>
          <main>
            <section class="banner"><strong>Scope banner:</strong> {html.escape(SCOPE_STATEMENT)}</section>
            <h2>Acceptance Badge</h2>
            {_html_table(("badge", "label", "status", "severity", "summary"), badge_rows)}
            <h2>Compact Release Table</h2>
            {_html_table(RELEASE_COLUMNS, release_rows)}
            <h2>Key Risk Notes</h2>
            <section class="panel"><ul>{risk_items}</ul><ul>{disclaimer_items}</ul></section>
            <h2>Status Block</h2>
            <section class="panel"><pre>{html.escape(status_block)}</pre></section>
            <h2>Source Artifact List</h2>
            {_html_table(("path", "kind", "sha256"), source_rows)}
            <h2>Local Commands</h2>
            <section class="panel"><ul>{command_items}</ul></section>
          </main>
        </body>
        </html>
        """
    ).lstrip()


def _artifact_contents_without_manifest(output: AcceptanceSummaryOutput) -> dict[str, str]:
    return {
        "badges": _json_text(output.badges),
        "status_block": output.status_block,
        "agent_json": _json_text(output.agent_json),
        "release_csv": _csv_text(RELEASE_COLUMNS, output.release_rows),
        "html": output.html_summary,
    }


def _artifact_contents(output: AcceptanceSummaryOutput) -> dict[str, str]:
    contents = _artifact_contents_without_manifest(output)
    contents["manifest"] = _csv_text(MANIFEST_COLUMNS, output.manifest_rows)
    return contents


def _output_counts(role: str, text: str) -> tuple[str, str]:
    if role in {"release_csv", "manifest"}:
        return str(len(tuple(csv.DictReader(text.splitlines())))), ""
    if role in {"badges", "agent_json", "html", "status_block"}:
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
                "no_deploy": "YES",
                "details": "P376 source evidence read from merged P371/P372/P373/P374/P375 artifacts only.",
                "scope_statement": SCOPE_STATEMENT,
            }
        )
    for role, basename in P376_ARTIFACT_BASENAMES.items():
        text = output_texts_without_manifest.get(role, "")
        row_count, object_count = _output_counts(role, text)
        digest = sha256_bytes(text.encode("utf-8")) if text else ""
        if role == "manifest":
            row_count = str(len(REQUIRED_SOURCE_ARTIFACTS) + len(P376_ARTIFACT_BASENAMES) + 4)
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
                "no_deploy": "YES",
                "details": "P376 generated no-DB compact acceptance-summary artifact.",
                "scope_statement": SCOPE_STATEMENT,
            }
        )
    for role, details in (
        ("no_db_open_write", "No DB open/write was performed by P376."),
        ("no_adapter_calls", "No adapter calls were performed by P376."),
        ("no_new_scoring", "No new scoring, scoring cohort, shape-only scoring, blocked-target scoring, or blended leaderboard was created by P376."),
        ("no_deploy", "No production registry import, deploy, or external publication was performed by P376."),
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
                "no_deploy": "YES",
                "details": details,
                "scope_statement": SCOPE_STATEMENT,
            }
        )
    return tuple(rows)


def validate_summary(
    output: AcceptanceSummaryOutput | None = None,
    repo_root: Path | None = None,
    include_determinism: bool = True,
) -> tuple[dict[str, str], ...]:
    current = output if output is not None else run_summary(repo_root, include_validation=False)
    text = "\n".join(_artifact_contents(current).values()).lower()
    found = [phrase for phrase in FORBIDDEN_AUTHORIZATION_PHRASES if phrase in text]
    badge_map = _as_mapping(current.badges.get("badges"))
    rows = [
        _check("required_p371_p372_p373_p374_p375_evidence_exists", len(verify_required_evidence(repo_root)) == len(REQUIRED_SOURCE_ARTIFACTS), len(REQUIRED_SOURCE_ARTIFACTS), len(REQUIRED_SOURCE_ARTIFACTS), "Required merged source modules, tests, and artifacts are present."),
        _check("badges_json_schema", set(badge_map) == {"acceptance", "operator_health", "route_coverage", "issue", "no_db", "no_adapter_call", "no_new_scoring"} and all(set(_as_mapping(badge).keys()) >= set(BADGE_REQUIRED_KEYS) for badge in badge_map.values()), "seven required badges", sorted(badge_map), "Badges JSON includes all required badge objects."),
        _check("status_block_contains_required_fields", all(field in current.status_block for field in ("Acceptance decision:", "Source baseline:", "Operator health:", "Route coverage:", "Blocking issue count:", "Safe caveats:", "No future prediction guarantee.", "No betting advice.")), "required fields", "present", "Status block is copy-paste friendly and includes required caveats."),
        _check("agent_json_schema", set(current.agent_json) >= {"acceptance_summary", "source_artifacts", "recommended_safe_next_action_categories", "stop_boundaries"} and len(current.agent_json.get("source_artifacts", ())) == len(REQUIRED_SOURCE_ARTIFACTS), "required agent keys", sorted(current.agent_json), "Agent JSON includes machine-readable summary, source hashes, safe next actions, and STOP boundaries."),
        _check("release_csv_schema", bool(current.release_rows) and tuple(current.release_rows[0]) == RELEASE_COLUMNS, RELEASE_COLUMNS, tuple(current.release_rows[0]) if current.release_rows else (), "Release CSV rows use required columns."),
        _check("html_summary_self_contained", current.html_summary.startswith("<!doctype html>") and "<script" not in current.html_summary.lower() and all(section in current.html_summary for section in ("Acceptance Badge", "Compact Release Table", "Key Risk Notes", "Source Artifact List", "Local Commands")), "self-contained HTML sections", "present", "HTML summary includes required sections and no script tag."),
        _check("manifest_csv_schema", bool(current.manifest_rows) and tuple(current.manifest_rows[0]) == MANIFEST_COLUMNS, MANIFEST_COLUMNS, tuple(current.manifest_rows[0]) if current.manifest_rows else (), "Manifest rows use required columns."),
        _check("manifest_records_sources_outputs_statements", sum(1 for row in current.manifest_rows if row["artifact_group"] == "source") == len(REQUIRED_SOURCE_ARTIFACTS) and sum(1 for row in current.manifest_rows if row["artifact_group"] == "output") == len(P376_ARTIFACT_BASENAMES), "all source/output rows", len(current.manifest_rows), "Manifest records source artifacts, output artifacts, counts, and safety statements."),
        _check("generated_outputs_include_safety_constraints", all(line.lower() in text for line in DISCLAIMER_LINES), "all scope lines", "present", "Outputs include no-DB/no-adapter/no-scoring/no-deploy constraints."),
        _check("generated_outputs_do_not_authorize_forbidden_actions", not found, "absent", ";".join(found) if found else "absent", "P376 outputs do not authorize restricted actions."),
    ]
    if include_determinism:
        first = run_summary(repo_root, include_validation=False)
        second = run_summary(repo_root, include_validation=False)
        rows.append(
            _check(
                "deterministic_double_run_equality",
                _artifact_contents(first) == _artifact_contents(second),
                "equal",
                "equal" if _artifact_contents(first) == _artifact_contents(second) else "different",
                "P376 generated rows and artifacts are deterministic across two runs.",
            )
        )
    return tuple(rows)


def run_summary(repo_root: Path | None = None, include_validation: bool = True) -> AcceptanceSummaryOutput:
    badges = build_badges(repo_root)
    release_rows = build_release_rows(badges, repo_root)
    status_block = build_status_block(badges, release_rows, repo_root)
    agent_json = build_agent_json(badges, release_rows, repo_root)
    html_summary = build_html_summary(badges, status_block, agent_json, release_rows)
    without_manifest = AcceptanceSummaryOutput(badges, status_block, agent_json, release_rows, html_summary, (), ())
    manifest = build_manifest_rows(_artifact_contents_without_manifest(without_manifest), repo_root)
    partial = AcceptanceSummaryOutput(badges, status_block, agent_json, release_rows, html_summary, manifest, ())
    validation = validate_summary(partial, repo_root, include_determinism=True) if include_validation else ()
    return AcceptanceSummaryOutput(badges, status_block, agent_json, release_rows, html_summary, manifest, validation)


def _assert_deterministic(first: AcceptanceSummaryOutput, second: AcceptanceSummaryOutput) -> None:
    if _artifact_contents(first) != _artifact_contents(second):
        raise RuntimeError("determinism double-run mismatch: P376 acceptance summary artifacts are not reproducible")


def write_artifacts(output: AcceptanceSummaryOutput, artifacts_dir: Path | None = None) -> dict[str, Path]:
    directory = Path(artifacts_dir) if artifacts_dir is not None else REPO_ROOT / "artifacts"
    directory.mkdir(parents=True, exist_ok=True)
    contents = _artifact_contents(output)
    paths = {key: directory / basename for key, basename in P376_ARTIFACT_BASENAMES.items()}
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
    parser.add_argument("--generate", action="store_true", help="write all P376 acceptance summary artifacts")
    parser.add_argument("--badges", action="store_true", help="emit acceptance badges JSON")
    parser.add_argument("--status-block", action="store_true", help="emit copy-paste Markdown status block")
    parser.add_argument("--agent-json", action="store_true", help="emit machine-readable agent acceptance summary JSON")
    parser.add_argument("--release-csv", action="store_true", help="emit compact release summary CSV")
    parser.add_argument("--html", action="store_true", help="emit self-contained HTML summary")
    parser.add_argument("--validate", action="store_true", help="emit P376 validation rows as CSV")
    args = parser.parse_args(argv)

    if args.badges:
        _print_json(build_badges())
    elif args.status_block:
        print(run_summary().status_block, end="")
    elif args.agent_json:
        _print_json(run_summary().agent_json)
    elif args.release_csv:
        _print_csv(RELEASE_COLUMNS, build_release_rows())
    elif args.html:
        print(run_summary().html_summary, end="")
    elif args.validate:
        _print_csv(VALIDATION_COLUMNS, validate_summary())
    else:
        first = run_summary()
        second = run_summary()
        _assert_deterministic(first, second)
        paths = write_artifacts(first, args.artifacts_dir)
        p375_decision = _as_mapping(first.agent_json["acceptance_summary"]).get("decision", "")
        print("P376 Big Lotto no-DB acceptance summary: determinism double-run PASS")
        print(f"acceptance decision: {p375_decision}")
        print(f"accepted: {_as_mapping(first.agent_json['acceptance_summary']).get('accepted', '')}")
        print(f"blocking issues: {_as_mapping(first.agent_json['acceptance_summary']).get('blocking_issue_count', '')}")
        print(f"release rows: {len(first.release_rows)}")
        print(f"validation rows: {len(first.validation_rows)}")
        print(f"validation failures: {sum(1 for row in first.validation_rows if row['status'] == 'FAIL')}")
        print("No DB was opened or written; no adapters were called; no new scoring was created; no production registry import or deploy was performed.")
        print("Historical descriptive evidence only; no betting advice; no future prediction guarantee; no strategy status changes; no blended leaderboard.")
        for key, path in sorted(paths.items()):
            print(f"{key}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
