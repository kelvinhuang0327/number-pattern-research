"""P374 Big Lotto no-DB operator history and snapshot comparison.

This module reads only merged P371/P372/P373 command-center artifacts and
generates a deterministic operator-health snapshot, initial status delta,
issue trends, snapshot comparison, and self-contained history HTML. It does
not open or write a DB, call adapters, create new scoring cohorts, import
production registries, deploy, provide betting advice, or make future-
performance claims.
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
TASK = "P374_biglotto_operator_history"
GENERATED_AT = "DETERMINISTIC_PLACEHOLDER"
SOURCE_BASELINE = {
    "required_origin_main_merge_commit": "992c0c33ca9e3db1bbe81914cd1de82b21c06bde",
    "p371_source_merge_baseline": "30e4120060e41e8a6f7cf529c28d9b490c01f70b",
    "p372_source_baseline": "1a971bd14a11de3e6e5967cfb543ab7069e97100",
    "p373_source_merge_baseline": "992c0c33ca9e3db1bbe81914cd1de82b21c06bde",
    "history_mode": "initial_snapshot_baseline_equals_current",
}

P374_ARTIFACT_BASENAMES = {
    "health_snapshot": "P374_biglotto_operator_health_snapshot.json",
    "status_delta": "P374_biglotto_operator_status_delta.csv",
    "issue_trends": "P374_biglotto_operator_issue_trends.csv",
    "snapshot_comparison": "P374_biglotto_operator_snapshot_comparison.json",
    "history_html": "P374_biglotto_operator_history.html",
    "manifest": "P374_biglotto_operator_manifest.csv",
}

REQUIRED_SOURCE_ARTIFACTS = (
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
    "tests/test_p371_biglotto_evidence_command_center.py",
    "tests/test_p372_biglotto_command_center_route_replay.py",
    "tests/test_p373_biglotto_command_center_operator_console.py",
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
    "Snapshot comparison is baseline-current descriptive evidence only.",
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
}

STATUS_DELTA_COLUMNS = ("metric_name", "baseline_value", "current_value", "delta", "status", "notes")
ISSUE_TRENDS_COLUMNS = ("issue_type", "current_count", "baseline_count", "trend", "severity", "notes")
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
class OperatorHistoryOutput:
    health_snapshot: dict[str, object]
    status_delta_rows: tuple[dict[str, str], ...]
    issue_trend_rows: tuple[dict[str, str], ...]
    snapshot_comparison: dict[str, object]
    history_html: str
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


def verify_required_evidence(repo_root: Path | None = None) -> tuple[Path, ...]:
    paths = tuple(_artifact_path(relpath, repo_root) for relpath in REQUIRED_SOURCE_ARTIFACTS)
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise RuntimeError(f"required P371/P372/P373 command center evidence missing: {missing}")
    return paths


def source_inventory(repo_root: Path | None = None) -> tuple[dict[str, str], ...]:
    verify_required_evidence(repo_root)
    rows: list[dict[str, str]] = []
    for relpath in REQUIRED_SOURCE_ARTIFACTS:
        rows.append(
            {
                "path": relpath,
                "sha256": sha256_file(_artifact_path(relpath, repo_root)),
                "kind": "source_module" if relpath.endswith(".py") else "source_artifact",
            }
        )
    return tuple(rows)


def load_source_bundle(repo_root: Path | None = None) -> dict[str, object]:
    verify_required_evidence(repo_root)
    return {
        "p371_status": _read_json("artifacts/P371_biglotto_command_center_status.json", repo_root),
        "p372_coverage": _read_csv_rows("artifacts/P372_biglotto_command_center_route_coverage.csv", repo_root),
        "p372_health": _read_csv_rows("artifacts/P372_biglotto_command_center_route_health.csv", repo_root),
        "p373_status": _read_json("artifacts/P373_biglotto_command_center_operator_status.json", repo_root),
        "p373_badges": _read_json("artifacts/P373_biglotto_command_center_operator_badges.json", repo_root),
        "p373_issues": _read_csv_rows("artifacts/P373_biglotto_command_center_operator_issues.csv", repo_root),
        "p373_actions": _read_json("artifacts/P373_biglotto_command_center_operator_actions.json", repo_root),
        "p373_manifest": _read_csv_rows("artifacts/P373_biglotto_command_center_operator_manifest.csv", repo_root),
    }


def _as_mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _as_sequence(value: object) -> Sequence[object]:
    return value if isinstance(value, Sequence) and not isinstance(value, (str, bytes)) else ()


def _numeric(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _metric(name: str, value: object, notes: str) -> dict[str, object]:
    return {"metric_name": name, "value": value, "notes": notes}


def _metric_map(snapshot: Mapping[str, object]) -> dict[str, object]:
    return {str(row["metric_name"]): row["value"] for row in _as_sequence(snapshot.get("metric_summary")) if isinstance(row, Mapping)}


def _stable_snapshot_id(snapshot_without_id: Mapping[str, object]) -> str:
    return sha256_bytes(_json_text(snapshot_without_id).encode("utf-8"))[:16]


def build_health_snapshot(repo_root: Path | None = None) -> dict[str, object]:
    bundle = load_source_bundle(repo_root)
    p371_status = _as_mapping(bundle["p371_status"])
    p373_status = _as_mapping(bundle["p373_status"])
    p373_badges = _as_mapping(bundle["p373_badges"])
    p373_actions = _as_mapping(bundle["p373_actions"])
    route_coverage = _as_mapping(p373_status.get("route_coverage_summary"))
    p372_status = _as_mapping(p373_status.get("p372_route_replay_status"))
    p371_summary = _as_mapping(p373_status.get("p371_command_center_status"))
    badges = tuple(dict(badge) for badge in _as_sequence(p373_badges.get("badges")) if isinstance(badge, Mapping))
    issues = tuple(dict(row) for row in bundle["p373_issues"])  # type: ignore[arg-type]
    action_cards = tuple(dict(card) for card in _as_sequence(p373_actions.get("action_cards")) if isinstance(card, Mapping))
    issue_counts = _as_mapping(p373_status.get("issue_counts"))
    inventory = source_inventory(repo_root)
    badge_summary = {
        "badge_count": len(badges),
        "pass_count": sum(1 for badge in badges if badge.get("status") == "PASS"),
        "warn_count": sum(1 for badge in badges if badge.get("status") == "WARN"),
        "fail_count": sum(1 for badge in badges if badge.get("status") == "FAIL"),
        "badges": badges,
    }
    metric_summary = (
        _metric("overall_operator_health", p373_status.get("overall_operator_health", ""), "P373 compact operator health."),
        _metric("route_coverage_rate", route_coverage.get("coverage_rate", ""), "P372 replay coverage rate surfaced through P373."),
        _metric("route_health_pass_count", p372_status.get("route_health_pass_count", 0), "P372 route health PASS count."),
        _metric("route_health_warn_count", p372_status.get("route_health_warn_count", 0), "P372 route health WARN count."),
        _metric("route_health_fail_count", p372_status.get("route_health_fail_count", 0), "P372 route health FAIL count."),
        _metric("p371_smoke_pass_count", p371_summary.get("smoke_pass_count", 0), "P371 smoke PASS count."),
        _metric("p371_smoke_fail_count", p371_summary.get("smoke_fail_count", 0), "P371 smoke FAIL count."),
        _metric("issue_info_count", issue_counts.get("INFO", 0), "P373 operator INFO issue count."),
        _metric("issue_warn_count", issue_counts.get("WARN", 0), "P373 operator WARN issue count."),
        _metric("issue_fail_count", issue_counts.get("FAIL", 0), "P373 operator FAIL issue count."),
        _metric("badge_pass_count", badge_summary["pass_count"], "P373 PASS badge count."),
        _metric("badge_warn_count", badge_summary["warn_count"], "P373 WARN badge count."),
        _metric("badge_fail_count", badge_summary["fail_count"], "P373 FAIL badge count."),
        _metric("action_count", len(action_cards), "P373 template-only action card count."),
        _metric("required_source_artifact_count", len(inventory), "P374 source inventory row count."),
    )
    snapshot_without_id: dict[str, object] = {
        "task": TASK,
        "generated_at": GENERATED_AT,
        "source_baseline": SOURCE_BASELINE,
        "history_mode": "initial_snapshot",
        "operator_health": {
            "overall_operator_health": p373_status.get("overall_operator_health", ""),
            "p371_command_center_ready": p371_status.get("command_center_ready") is True,
            "p373_required_source_file_count": p373_status.get("required_source_file_count", 0),
            "p373_required_source_files_present": p373_status.get("required_source_files_present", 0),
        },
        "route_coverage": route_coverage,
        "issue_counts": dict(issue_counts),
        "badge_summary": badge_summary,
        "action_count": len(action_cards),
        "metric_summary": metric_summary,
        "source_artifact_sha256": {row["path"]: row["sha256"] for row in inventory},
        "statements": STATEMENTS,
        "scope_lines": DISCLAIMER_LINES,
        "notes": (
            "Initial P374 snapshot: deterministic baseline equals current. "
            "It compares committed command-center artifacts only and does not create a new scoring cohort."
        ),
    }
    snapshot = dict(snapshot_without_id)
    snapshot["snapshot_id"] = _stable_snapshot_id(snapshot_without_id)
    return snapshot


def build_status_delta(snapshot: Mapping[str, object]) -> tuple[dict[str, str], ...]:
    rows: list[dict[str, str]] = []
    for metric in _as_sequence(snapshot.get("metric_summary")):
        if not isinstance(metric, Mapping):
            continue
        value = metric.get("value", "")
        value_text = str(value)
        rows.append(
            {
                "metric_name": str(metric.get("metric_name", "")),
                "baseline_value": value_text,
                "current_value": value_text,
                "delta": "0" if _numeric(value) is not None else "unchanged",
                "status": "PASS",
                "notes": f"Initial snapshot baseline=current. {metric.get('notes', '')}",
            }
        )
    return tuple(rows)


def build_issue_trends(repo_root: Path | None = None) -> tuple[dict[str, str], ...]:
    issues = _read_csv_rows("artifacts/P373_biglotto_command_center_operator_issues.csv", repo_root)
    grouped: dict[tuple[str, str], int] = {}
    for row in issues:
        key = (row.get("issue_type", ""), row.get("severity", ""))
        grouped[key] = grouped.get(key, 0) + 1
    if not grouped:
        grouped[("no_operator_issues_file_rows", "INFO")] = 0
    rows = []
    for issue_type, severity in sorted(grouped):
        count = grouped[(issue_type, severity)]
        rows.append(
            {
                "issue_type": issue_type,
                "current_count": str(count),
                "baseline_count": str(count),
                "trend": "initial_snapshot",
                "severity": severity,
                "notes": "Initial P374 trend row; deterministic baseline equals current.",
            }
        )
    return tuple(rows)


def build_snapshot_comparison(
    snapshot: Mapping[str, object],
    delta_rows: Sequence[Mapping[str, str]],
    issue_rows: Sequence[Mapping[str, str]],
) -> dict[str, object]:
    snapshot_id = str(snapshot.get("snapshot_id", ""))
    unchanged_metrics = tuple(row["metric_name"] for row in delta_rows if row.get("delta") in {"0", "unchanged"})
    return {
        "task": TASK,
        "generated_at": GENERATED_AT,
        "source_baseline": SOURCE_BASELINE,
        "baseline_snapshot_id": snapshot_id,
        "current_snapshot_id": snapshot_id,
        "comparison_status": "INITIAL_SNAPSHOT_NO_CHANGES",
        "changed_metrics": (),
        "unchanged_metrics": unchanged_metrics,
        "issue_trend_count": len(issue_rows),
        "initial_snapshot": True,
        "statements": STATEMENTS,
        "scope_lines": DISCLAIMER_LINES,
        "notes": "First P374 history artifact: baseline and current are intentionally identical.",
    }


def _html_table(columns: Sequence[str], rows: Iterable[Mapping[str, object]]) -> str:
    head = "".join(f"<th>{html.escape(column)}</th>" for column in columns)
    body = []
    for row in rows:
        cells = "".join(f"<td>{html.escape(str(row.get(column, '')))}</td>" for column in columns)
        body.append(f"<tr>{cells}</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def build_history_html(
    snapshot: Mapping[str, object],
    delta_rows: Sequence[Mapping[str, str]],
    issue_rows: Sequence[Mapping[str, str]],
    comparison: Mapping[str, object],
    repo_root: Path | None = None,
) -> str:
    badge_rows = tuple(
        {
            "badge_id": badge.get("badge_id", ""),
            "label": badge.get("label", ""),
            "status": badge.get("status", ""),
            "summary": badge.get("summary", ""),
        }
        for badge in _as_sequence(_as_mapping(snapshot.get("badge_summary")).get("badges"))
        if isinstance(badge, Mapping)
    )
    inventory_rows = source_inventory(repo_root)
    commands = (
        "python3 -m recovered_strategies.biglotto.no_db_operator_history --generate",
        "python3 -m recovered_strategies.biglotto.no_db_operator_history --snapshot",
        "python3 -m recovered_strategies.biglotto.no_db_operator_history --delta",
        "python3 -m recovered_strategies.biglotto.no_db_operator_history --trends",
        "python3 -m recovered_strategies.biglotto.no_db_operator_history --compare",
        "python3 -m recovered_strategies.biglotto.no_db_operator_history --html",
        "python3 -m recovered_strategies.biglotto.no_db_operator_history --validate",
    )
    command_items = "".join(f"<li><code>{html.escape(command)}</code></li>" for command in commands)
    coverage = _as_mapping(snapshot.get("route_coverage"))
    health = _as_mapping(snapshot.get("operator_health"))
    issue_counts = _as_mapping(snapshot.get("issue_counts"))
    css = textwrap.dedent(
        """
        body { margin: 0; font-family: Arial, sans-serif; color: #172033; background: #f7f8fa; }
        header { background: #102a43; color: #fff; padding: 24px 32px; }
        main { max-width: 1180px; margin: 0 auto; padding: 24px; }
        .banner { background: #fff3cd; border: 1px solid #d6a400; padding: 12px 16px; margin-bottom: 20px; }
        .panel { background: #fff; border: 1px solid #d9dee7; border-radius: 6px; padding: 14px; margin-bottom: 18px; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }
        .metric { background: #fff; border: 1px solid #d9dee7; border-radius: 6px; padding: 14px; }
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
          <title>P374 Big Lotto no-DB operator history</title>
          <style>{css}</style>
        </head>
        <body>
          <header>
            <h1>P374 Big Lotto no-DB operator history</h1>
            <p>Snapshot: <strong>{html.escape(str(snapshot.get("snapshot_id", "")))}</strong></p>
          </header>
          <main>
            <section class="banner"><strong>Scope banner:</strong> {html.escape(SCOPE_STATEMENT)}</section>
            <h2>Health snapshot summary</h2>
            <div class="grid">
              <section class="metric">Overall health<strong>{html.escape(str(health.get("overall_operator_health", "")))}</strong></section>
              <section class="metric">Coverage rate<strong>{html.escape(str(coverage.get("coverage_rate", "")))}</strong></section>
              <section class="metric">Issue counts<strong>{html.escape(str(dict(issue_counts)))}</strong></section>
              <section class="metric">Action count<strong>{html.escape(str(snapshot.get("action_count", "")))}</strong></section>
            </div>
            <h2>Status delta table</h2>
            {_html_table(STATUS_DELTA_COLUMNS, delta_rows)}
            <h2>Issue trends table</h2>
            {_html_table(ISSUE_TRENDS_COLUMNS, issue_rows)}
            <h2>Badge summary</h2>
            {_html_table(("badge_id", "label", "status", "summary"), badge_rows)}
            <h2>Snapshot comparison</h2>
            <section class="panel">
              <p>Comparison status: <strong>{html.escape(str(comparison.get("comparison_status", "")))}</strong></p>
              <p>Initial snapshot: <strong>{html.escape(str(comparison.get("initial_snapshot", "")))}</strong></p>
              <p>Changed metrics: <strong>{html.escape(str(len(_as_sequence(comparison.get("changed_metrics")))))}</strong></p>
              <p>Unchanged metrics: <strong>{html.escape(str(len(_as_sequence(comparison.get("unchanged_metrics")))))}</strong></p>
            </section>
            <h2>Source artifact inventory</h2>
            {_html_table(("path", "kind", "sha256"), inventory_rows)}
            <h2>Local commands</h2>
            <section class="panel"><ul>{command_items}</ul></section>
          </main>
        </body>
        </html>
        """
    ).lstrip()


def _artifact_contents_without_manifest(output: OperatorHistoryOutput) -> dict[str, str]:
    return {
        "health_snapshot": _json_text(output.health_snapshot),
        "status_delta": _csv_text(STATUS_DELTA_COLUMNS, output.status_delta_rows),
        "issue_trends": _csv_text(ISSUE_TRENDS_COLUMNS, output.issue_trend_rows),
        "snapshot_comparison": _json_text(output.snapshot_comparison),
        "history_html": output.history_html,
    }


def _artifact_contents(output: OperatorHistoryOutput) -> dict[str, str]:
    contents = _artifact_contents_without_manifest(output)
    contents["manifest"] = _csv_text(MANIFEST_COLUMNS, output.manifest_rows)
    return contents


def _output_counts(role: str, text: str) -> tuple[str, str]:
    if role in {"status_delta", "issue_trends", "manifest"}:
        return str(len(tuple(csv.DictReader(text.splitlines())))), ""
    if role in {"health_snapshot", "snapshot_comparison", "history_html"}:
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
                "details": "P374 source evidence read from merged P371/P372/P373 command-center artifacts only.",
                "scope_statement": SCOPE_STATEMENT,
            }
        )
    for role, basename in P374_ARTIFACT_BASENAMES.items():
        text = output_texts_without_manifest.get(role, "")
        row_count, object_count = _output_counts(role, text)
        digest = sha256_bytes(text.encode("utf-8")) if text else ""
        if role == "manifest":
            row_count = str(len(REQUIRED_SOURCE_ARTIFACTS) + len(P374_ARTIFACT_BASENAMES) + 4)
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
                "details": "P374 generated no-DB operator-history artifact.",
                "scope_statement": SCOPE_STATEMENT,
            }
        )
    for role, details in (
        ("no_db_open_write", "No DB open/write was performed by P374."),
        ("no_adapter_calls", "No adapter calls were performed by P374."),
        ("no_new_scoring", "No new scoring, scoring cohort, shape-only scoring, blocked-target scoring, or blended leaderboard was created by P374."),
        ("no_deploy", "No production registry import, strategy status change, deploy, force operation, betting advice, or future-performance claim was performed by P374."),
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


def validate_operator_history(
    output: OperatorHistoryOutput | None = None,
    repo_root: Path | None = None,
    include_determinism: bool = True,
) -> tuple[dict[str, str], ...]:
    current = output if output is not None else run_operator_history(repo_root, include_validation=False)
    text = "\n".join(_artifact_contents(current).values()).lower()
    found = [phrase for phrase in FORBIDDEN_AUTHORIZATION_PHRASES if phrase in text]
    metric_names = set(_metric_map(current.health_snapshot))
    rows = [
        _check("required_p371_p372_p373_evidence_exists", len(verify_required_evidence(repo_root)) == len(REQUIRED_SOURCE_ARTIFACTS), len(REQUIRED_SOURCE_ARTIFACTS), len(REQUIRED_SOURCE_ARTIFACTS), "Required P371/P372/P373 modules, artifacts, and tests are present."),
        _check("health_snapshot_json_schema", set(current.health_snapshot) >= {"source_baseline", "operator_health", "route_coverage", "issue_counts", "badge_summary", "action_count", "source_artifact_sha256", "statements", "snapshot_id"}, "required snapshot keys", sorted(current.health_snapshot), "Health snapshot includes required operator-history fields."),
        _check("health_snapshot_metric_summary", {"overall_operator_health", "route_coverage_rate", "action_count"}.issubset(metric_names), "core metrics present", sorted(metric_names), "Snapshot exposes deterministic comparable metric rows."),
        _check("status_delta_csv_schema", bool(current.status_delta_rows) and tuple(current.status_delta_rows[0]) == STATUS_DELTA_COLUMNS, STATUS_DELTA_COLUMNS, tuple(current.status_delta_rows[0]) if current.status_delta_rows else (), "Status delta CSV uses required columns."),
        _check("status_delta_initial_snapshot", {row["status"] for row in current.status_delta_rows} == {"PASS"} and all("Initial snapshot baseline=current" in row["notes"] for row in current.status_delta_rows), "baseline=current PASS rows", len(current.status_delta_rows), "Initial snapshot delta rows clearly label baseline=current."),
        _check("issue_trends_csv_schema", bool(current.issue_trend_rows) and tuple(current.issue_trend_rows[0]) == ISSUE_TRENDS_COLUMNS, ISSUE_TRENDS_COLUMNS, tuple(current.issue_trend_rows[0]) if current.issue_trend_rows else (), "Issue trends CSV uses required columns."),
        _check("snapshot_comparison_json_schema", set(current.snapshot_comparison) >= {"baseline_snapshot_id", "current_snapshot_id", "comparison_status", "changed_metrics", "unchanged_metrics", "initial_snapshot"}, "required comparison keys", sorted(current.snapshot_comparison), "Snapshot comparison JSON includes required fields."),
        _check("snapshot_comparison_initial", current.snapshot_comparison["initial_snapshot"] is True and current.snapshot_comparison["baseline_snapshot_id"] == current.snapshot_comparison["current_snapshot_id"], "initial snapshot same id", current.snapshot_comparison.get("comparison_status"), "First P374 comparison is deterministic baseline=current."),
        _check("history_html_self_contained", current.history_html.startswith("<!doctype html>") and "<script" not in current.history_html.lower() and "Source artifact inventory" in current.history_html, "self-contained html", "present", "History HTML includes summary, deltas, trends, badges, inventory, and commands."),
        _check("manifest_csv_schema", bool(current.manifest_rows) and tuple(current.manifest_rows[0]) == MANIFEST_COLUMNS, MANIFEST_COLUMNS, tuple(current.manifest_rows[0]) if current.manifest_rows else (), "Manifest rows use required columns."),
        _check("manifest_records_sources_outputs_statements", sum(1 for row in current.manifest_rows if row["artifact_group"] == "source") == len(REQUIRED_SOURCE_ARTIFACTS) and sum(1 for row in current.manifest_rows if row["artifact_group"] == "output") == len(P374_ARTIFACT_BASENAMES), "all source/output rows", len(current.manifest_rows), "Manifest records source artifacts, output artifacts, and safety statements."),
        _check("generated_outputs_include_safety_constraints", all(line.lower() in text for line in DISCLAIMER_LINES), "all scope lines", "present", "Outputs include no-DB/no-adapter/no-scoring/no-deploy constraints."),
        _check("generated_outputs_do_not_authorize_forbidden_actions", not found, "absent", ";".join(found) if found else "absent", "P374 outputs do not authorize DB writes, adapter execution, scoring, deploy, force operations, status changes, betting advice, or future prediction claims."),
    ]
    if include_determinism:
        first = run_operator_history(repo_root, include_validation=False)
        second = run_operator_history(repo_root, include_validation=False)
        rows.append(
            _check(
                "deterministic_double_run_equality",
                _artifact_contents(first) == _artifact_contents(second),
                "equal",
                "equal" if _artifact_contents(first) == _artifact_contents(second) else "different",
                "P374 generated rows and artifacts are deterministic across two runs.",
            )
        )
    return tuple(rows)


def run_operator_history(repo_root: Path | None = None, include_validation: bool = True) -> OperatorHistoryOutput:
    snapshot = build_health_snapshot(repo_root)
    delta_rows = build_status_delta(snapshot)
    issue_rows = build_issue_trends(repo_root)
    comparison = build_snapshot_comparison(snapshot, delta_rows, issue_rows)
    history_html = build_history_html(snapshot, delta_rows, issue_rows, comparison, repo_root)
    with_html = OperatorHistoryOutput(snapshot, delta_rows, issue_rows, comparison, history_html, (), ())
    manifest = build_manifest_rows(_artifact_contents_without_manifest(with_html), repo_root)
    partial = OperatorHistoryOutput(snapshot, delta_rows, issue_rows, comparison, history_html, manifest, ())
    validation = validate_operator_history(partial, repo_root, include_determinism=True) if include_validation else ()
    return OperatorHistoryOutput(snapshot, delta_rows, issue_rows, comparison, history_html, manifest, validation)


def _assert_deterministic(first: OperatorHistoryOutput, second: OperatorHistoryOutput) -> None:
    if _artifact_contents(first) != _artifact_contents(second):
        raise RuntimeError("determinism double-run mismatch: P374 operator history artifacts are not reproducible")


def write_artifacts(output: OperatorHistoryOutput, artifacts_dir: Path | None = None) -> dict[str, Path]:
    directory = Path(artifacts_dir) if artifacts_dir is not None else REPO_ROOT / "artifacts"
    directory.mkdir(parents=True, exist_ok=True)
    contents = _artifact_contents(output)
    paths = {key: directory / basename for key, basename in P374_ARTIFACT_BASENAMES.items()}
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
    parser.add_argument("--generate", action="store_true", help="write all P374 operator history artifacts")
    parser.add_argument("--snapshot", action="store_true", help="emit operator health snapshot JSON")
    parser.add_argument("--delta", action="store_true", help="emit initial status delta CSV")
    parser.add_argument("--trends", action="store_true", help="emit issue trends CSV")
    parser.add_argument("--compare", action="store_true", help="emit snapshot comparison JSON")
    parser.add_argument("--html", action="store_true", help="emit self-contained history HTML")
    parser.add_argument("--validate", action="store_true", help="emit P374 validation rows as CSV")
    args = parser.parse_args(argv)

    if args.snapshot:
        _print_json(build_health_snapshot())
    elif args.delta:
        _print_csv(STATUS_DELTA_COLUMNS, build_status_delta(build_health_snapshot()))
    elif args.trends:
        _print_csv(ISSUE_TRENDS_COLUMNS, build_issue_trends())
    elif args.compare:
        snapshot = build_health_snapshot()
        delta_rows = build_status_delta(snapshot)
        trend_rows = build_issue_trends()
        _print_json(build_snapshot_comparison(snapshot, delta_rows, trend_rows))
    elif args.html:
        output = run_operator_history()
        print(output.history_html, end="")
    elif args.validate:
        _print_csv(VALIDATION_COLUMNS, validate_operator_history())
    else:
        first = run_operator_history()
        second = run_operator_history()
        _assert_deterministic(first, second)
        paths = write_artifacts(first, args.artifacts_dir)
        print("P374 Big Lotto no-DB operator history: determinism double-run PASS")
        print(f"snapshot id: {first.health_snapshot['snapshot_id']}")
        print(f"overall operator health: {first.health_snapshot['operator_health']['overall_operator_health']}")  # type: ignore[index]
        print(f"status delta rows: {len(first.status_delta_rows)}")
        print(f"issue trend rows: {len(first.issue_trend_rows)}")
        print(f"validation rows: {len(first.validation_rows)}")
        print(f"validation failures: {sum(1 for row in first.validation_rows if row['status'] == 'FAIL')}")
        print("No DB was opened or written; no adapters were called; no new scoring was created; no production registry import or deploy was performed.")
        print("Historical descriptive evidence only; no betting advice; no future prediction guarantee; no blended leaderboard.")
        for key, path in sorted(paths.items()):
            print(f"{key}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
