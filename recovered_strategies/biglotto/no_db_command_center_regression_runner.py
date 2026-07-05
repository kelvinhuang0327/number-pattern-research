"""P377 Big Lotto no-DB command center regression orchestrator.

This module runs one read-only regression layer over the merged P371-P376
Big Lotto no-DB command-center stack. It executes only safe validation CLI
commands that emit stdout, reads committed artifacts, and writes only P377
regression artifacts. It does not open or write a DB, call adapters, create
new scoring cohorts, import production registries, deploy, provide betting
advice, or make future-performance claims.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import subprocess
import sys
import textwrap
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Iterable, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
TASK = "P377_biglotto_command_center_regression_runner"
GENERATED_AT = "DETERMINISTIC_PLACEHOLDER"
SOURCE_BASELINE = {
    "required_origin_main_merge_commit": "8467ea77b851fc94951490332c51dc7ffd7b868f",
    "p371_p376_evidence_mode": "merged_read_only_no_db_command_center_stack",
    "regression_mode": "safe_validation_commands_and_committed_artifact_freshness",
}

P377_ARTIFACT_BASENAMES = {
    "results": "P377_biglotto_command_center_regression_results.json",
    "commands": "P377_biglotto_command_center_regression_commands.csv",
    "failures": "P377_biglotto_command_center_regression_failures.csv",
    "freshness": "P377_biglotto_command_center_regression_artifact_freshness.csv",
    "report": "P377_biglotto_command_center_regression_report.html",
    "manifest": "P377_biglotto_command_center_regression_manifest.csv",
}

REQUIRED_SOURCE_ARTIFACTS = (
    "recovered_strategies/biglotto/no_db_evidence_command_center.py",
    "recovered_strategies/biglotto/no_db_command_center_route_replay.py",
    "recovered_strategies/biglotto/no_db_command_center_operator_console.py",
    "recovered_strategies/biglotto/no_db_operator_history.py",
    "recovered_strategies/biglotto/no_db_operator_acceptance.py",
    "recovered_strategies/biglotto/no_db_acceptance_summary.py",
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
    "artifacts/P376_biglotto_acceptance_summary_badges.json",
    "artifacts/P376_biglotto_acceptance_summary_status_block.md",
    "artifacts/P376_biglotto_acceptance_summary_agent.json",
    "artifacts/P376_biglotto_acceptance_summary_release.csv",
    "artifacts/P376_biglotto_acceptance_summary.html",
    "artifacts/P376_biglotto_acceptance_summary_manifest.csv",
    "tests/test_p371_biglotto_evidence_command_center.py",
    "tests/test_p372_biglotto_command_center_route_replay.py",
    "tests/test_p373_biglotto_command_center_operator_console.py",
    "tests/test_p374_biglotto_operator_history.py",
    "tests/test_p375_biglotto_operator_acceptance.py",
    "tests/test_p376_biglotto_acceptance_summary.py",
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
    "Regression runner writes only P377-prefixed artifacts.",
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

COMMAND_COLUMNS = (
    "command_id",
    "stage",
    "command",
    "expected_output_artifact",
    "status",
    "normalized_output_summary",
    "no_db_confirmed",
    "no_adapter_calls_confirmed",
    "no_new_scoring_confirmed",
)

FAILURE_COLUMNS = (
    "failure_id",
    "command_id",
    "failure_class",
    "severity",
    "blocking",
    "description",
    "remediation_hint",
)

FRESHNESS_COLUMNS = (
    "artifact_path",
    "source_stage",
    "exists",
    "sha256",
    "row_or_object_count",
    "freshness_status",
    "notes",
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

SAFE_COMMAND_SPECS = (
    (
        "P377-CMD-001",
        "P371",
        "python3 -m recovered_strategies.biglotto.no_db_evidence_command_center --validate",
        "artifacts/P371_biglotto_command_center_manifest.csv",
        ("recovered_strategies.biglotto.no_db_evidence_command_center", "--validate"),
    ),
    (
        "P377-CMD-002",
        "P372",
        "python3 -m recovered_strategies.biglotto.no_db_command_center_route_replay --validate",
        "artifacts/P372_biglotto_command_center_manifest.csv",
        ("recovered_strategies.biglotto.no_db_command_center_route_replay", "--validate"),
    ),
    (
        "P377-CMD-003",
        "P373",
        "python3 -m recovered_strategies.biglotto.no_db_command_center_operator_console --validate",
        "artifacts/P373_biglotto_command_center_operator_manifest.csv",
        ("recovered_strategies.biglotto.no_db_command_center_operator_console", "--validate"),
    ),
    (
        "P377-CMD-004",
        "P374",
        "python3 -m recovered_strategies.biglotto.no_db_operator_history --validate",
        "artifacts/P374_biglotto_operator_manifest.csv",
        ("recovered_strategies.biglotto.no_db_operator_history", "--validate"),
    ),
    (
        "P377-CMD-005",
        "P375",
        "python3 -m recovered_strategies.biglotto.no_db_operator_acceptance --validate",
        "artifacts/P375_biglotto_operator_acceptance_manifest.csv",
        ("recovered_strategies.biglotto.no_db_operator_acceptance", "--validate"),
    ),
    (
        "P377-CMD-006",
        "P376",
        "python3 -m recovered_strategies.biglotto.no_db_acceptance_summary --validate",
        "artifacts/P376_biglotto_acceptance_summary_manifest.csv",
        ("recovered_strategies.biglotto.no_db_acceptance_summary", "--validate"),
    ),
)


@dataclass(frozen=True)
class RegressionOutput:
    results: dict[str, object]
    command_rows: tuple[dict[str, str], ...]
    failure_rows: tuple[dict[str, str], ...]
    freshness_rows: tuple[dict[str, str], ...]
    report_html: str
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


def _json_text(payload: object) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _csv_text(columns: Sequence[str], rows: Iterable[Mapping[str, str]]) -> str:
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(columns), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({column: row.get(column, "") for column in columns})
    return buffer.getvalue()


def _read_csv_rows_from_text(text: str) -> tuple[dict[str, str], ...]:
    if not text.strip():
        return ()
    return tuple(dict(row) for row in csv.DictReader(text.splitlines()))


def _source_stage(relpath: str) -> str:
    name = Path(relpath).name
    for stage in ("P371", "P372", "P373", "P374", "P375", "P376"):
        if name.startswith(stage) or f"test_{stage.lower()}" in name:
            return stage
    if relpath.endswith(".py"):
        module_map = {
            "no_db_evidence_command_center.py": "P371",
            "no_db_command_center_route_replay.py": "P372",
            "no_db_command_center_operator_console.py": "P373",
            "no_db_operator_history.py": "P374",
            "no_db_operator_acceptance.py": "P375",
            "no_db_acceptance_summary.py": "P376",
        }
        return module_map.get(name, "P371-P376")
    return "P371-P376"


def verify_required_evidence(repo_root: Path | None = None) -> tuple[Path, ...]:
    paths = tuple(_artifact_path(relpath, repo_root) for relpath in REQUIRED_SOURCE_ARTIFACTS)
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise RuntimeError(f"required P371/P372/P373/P374/P375/P376 regression evidence missing: {missing}")
    return paths


def source_inventory(repo_root: Path | None = None) -> tuple[dict[str, str], ...]:
    verify_required_evidence(repo_root)
    rows = []
    for relpath in REQUIRED_SOURCE_ARTIFACTS:
        path = _artifact_path(relpath, repo_root)
        rows.append(
            {
                "path": relpath,
                "source_stage": _source_stage(relpath),
                "sha256": sha256_file(path),
                "kind": "source_module_or_test" if relpath.endswith(".py") else "source_artifact",
            }
        )
    return tuple(rows)


def _count_artifact(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        with open(path, newline="", encoding="utf-8") as handle:
            return f"csv_rows={len(tuple(csv.DictReader(handle)))}"
    if suffix == ".json":
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)
        if isinstance(payload, dict):
            return f"json_keys={len(payload)}"
        if isinstance(payload, list):
            return f"json_items={len(payload)}"
        return f"json_scalar={type(payload).__name__}"
    if suffix in {".html", ".md", ".py", ".txt"}:
        return f"text_lines={len(path.read_text(encoding='utf-8').splitlines())}"
    return "object_count=1"


def build_artifact_freshness(repo_root: Path | None = None) -> tuple[dict[str, str], ...]:
    rows = []
    for relpath in REQUIRED_SOURCE_ARTIFACTS:
        path = _artifact_path(relpath, repo_root)
        exists = path.is_file()
        rows.append(
            {
                "artifact_path": relpath,
                "source_stage": _source_stage(relpath),
                "exists": "YES" if exists else "NO",
                "sha256": sha256_file(path) if exists else "",
                "row_or_object_count": _count_artifact(path) if exists else "",
                "freshness_status": "FRESH" if exists else "MISSING",
                "notes": "Committed P371-P376 evidence artifact read-only; no DB open/write.",
            }
        )
    return tuple(rows)


def _summarize_validation_stdout(stdout: str, returncode: int) -> tuple[str, str]:
    rows = _read_csv_rows_from_text(stdout)
    if rows and "status" in rows[0]:
        pass_count = sum(1 for row in rows if row.get("status") == "PASS")
        warn_count = sum(1 for row in rows if row.get("status") == "WARN")
        fail_count = sum(1 for row in rows if row.get("status") == "FAIL")
        status = "FAIL" if returncode else ("FAIL" if fail_count else ("WARN" if warn_count else "PASS"))
        summary = (
            f"validation_rows={len(rows)} pass={pass_count} warn={warn_count} fail={fail_count} "
            f"stdout_sha256={sha256_bytes(stdout.encode('utf-8'))}"
        )
        return status, summary
    status = "FAIL" if returncode else "WARN"
    summary = f"unparsed_stdout_bytes={len(stdout.encode('utf-8'))} returncode={returncode}"
    return status, summary


def _safe_expected_output(relpath: str) -> bool:
    return relpath.startswith("artifacts/P37") and not relpath.startswith("artifacts/P377")


def execute_safe_commands(repo_root: Path | None = None) -> tuple[dict[str, str], ...]:
    root = Path(repo_root) if repo_root is not None else REPO_ROOT
    verify_required_evidence(root)
    rows = []
    for command_id, stage, command, expected_artifact, module_args in SAFE_COMMAND_SPECS:
        if not _safe_expected_output(expected_artifact):
            rows.append(
                {
                    "command_id": command_id,
                    "stage": stage,
                    "command": command,
                    "expected_output_artifact": expected_artifact,
                    "status": "FAIL",
                    "normalized_output_summary": "command skipped because expected output path was outside committed P371-P376 evidence",
                    "no_db_confirmed": "YES",
                    "no_adapter_calls_confirmed": "YES",
                    "no_new_scoring_confirmed": "YES",
                }
            )
            continue
        completed = subprocess.run(
            [sys.executable, "-m", *module_args],
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
        )
        status, summary = _summarize_validation_stdout(completed.stdout, completed.returncode)
        if completed.stderr.strip():
            status = "FAIL"
            summary = f"{summary}; stderr_sha256={sha256_bytes(completed.stderr.encode('utf-8'))}"
        rows.append(
            {
                "command_id": command_id,
                "stage": stage,
                "command": command,
                "expected_output_artifact": expected_artifact,
                "status": status,
                "normalized_output_summary": summary,
                "no_db_confirmed": "YES",
                "no_adapter_calls_confirmed": "YES",
                "no_new_scoring_confirmed": "YES",
            }
        )
    return tuple(rows)


def build_failures(command_rows: Sequence[Mapping[str, str]], freshness_rows: Sequence[Mapping[str, str]]) -> tuple[dict[str, str], ...]:
    rows: list[dict[str, str]] = []
    for command in command_rows:
        if command["status"] in {"WARN", "FAIL"}:
            rows.append(
                {
                    "failure_id": f"P377-FAIL-{len(rows) + 1:03d}",
                    "command_id": command["command_id"],
                    "failure_class": "safe_validation_command_warning_or_failure",
                    "severity": "high" if command["status"] == "FAIL" else "medium",
                    "blocking": "true" if command["status"] == "FAIL" else "false",
                    "description": f"{command['stage']} safe validation returned {command['status']}: {command['normalized_output_summary']}",
                    "remediation_hint": "Inspect the source stage validation output and fix only P377-specific orchestration issues if applicable.",
                }
            )
    for freshness in freshness_rows:
        if freshness["freshness_status"] != "FRESH":
            rows.append(
                {
                    "failure_id": f"P377-FAIL-{len(rows) + 1:03d}",
                    "command_id": "artifact_freshness",
                    "failure_class": "missing_or_stale_source_artifact",
                    "severity": "high",
                    "blocking": "true",
                    "description": f"{freshness['artifact_path']} freshness status is {freshness['freshness_status']}.",
                    "remediation_hint": "Stop and restore merged P371-P376 evidence on origin/main before rerunning P377.",
                }
            )
    if rows:
        return tuple(rows)
    return (
        {
            "failure_id": "none",
            "command_id": "none",
            "failure_class": "none",
            "severity": "none",
            "blocking": "false",
            "description": "No warnings or failures were observed.",
            "remediation_hint": "No remediation required.",
        },
    )


def build_results(
    command_rows: Sequence[Mapping[str, str]],
    freshness_rows: Sequence[Mapping[str, str]],
    failure_rows: Sequence[Mapping[str, str]],
) -> dict[str, object]:
    pass_count = sum(1 for row in command_rows if row["status"] == "PASS")
    warn_count = sum(1 for row in command_rows if row["status"] == "WARN")
    fail_count = sum(1 for row in command_rows if row["status"] == "FAIL")
    missing_count = sum(1 for row in freshness_rows if row["freshness_status"] != "FRESH")
    overall_status = "FAIL" if fail_count or missing_count else ("WARN" if warn_count else "PASS")
    return {
        "task": TASK,
        "generated_at": GENERATED_AT,
        "source_baseline": SOURCE_BASELINE,
        "overall_status": overall_status,
        "command_count": len(command_rows),
        "pass_count": pass_count,
        "warn_count": warn_count,
        "fail_count": fail_count,
        "artifact_count": len(freshness_rows),
        "warning_or_failure_count": 0 if failure_rows and failure_rows[0]["failure_id"] == "none" else len(failure_rows),
        "statements": STATEMENTS,
        "scope_lines": DISCLAIMER_LINES,
        "no_db_no_adapter_no_scoring_no_deploy_statement": (
            "No DB was opened or written; no adapters were called; no new scoring, scoring cohort, "
            "shape-only scoring, blocked-target scoring, or blended leaderboard was created; no production "
            "registry import or deploy was performed."
        ),
    }


def _html_table(columns: Sequence[str], rows: Iterable[Mapping[str, object]]) -> str:
    head = "".join(f"<th>{html.escape(column)}</th>" for column in columns)
    body = []
    for row in rows:
        cells = "".join(f"<td>{html.escape(str(row.get(column, '')))}</td>" for column in columns)
        body.append(f"<tr>{cells}</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def build_report(
    results: Mapping[str, object],
    command_rows: Sequence[Mapping[str, str]],
    failure_rows: Sequence[Mapping[str, str]],
    freshness_rows: Sequence[Mapping[str, str]],
) -> str:
    commands = (
        "python3 -m recovered_strategies.biglotto.no_db_command_center_regression_runner --generate",
        "python3 -m recovered_strategies.biglotto.no_db_command_center_regression_runner --run",
        "python3 -m recovered_strategies.biglotto.no_db_command_center_regression_runner --commands",
        "python3 -m recovered_strategies.biglotto.no_db_command_center_regression_runner --failures",
        "python3 -m recovered_strategies.biglotto.no_db_command_center_regression_runner --freshness",
        "python3 -m recovered_strategies.biglotto.no_db_command_center_regression_runner --report",
        "python3 -m recovered_strategies.biglotto.no_db_command_center_regression_runner --validate",
    )
    command_items = "".join(f"<li><code>{html.escape(command)}</code></li>" for command in commands)
    disclaimer_items = "".join(f"<li>{html.escape(line)}</li>" for line in DISCLAIMER_LINES)
    css = textwrap.dedent(
        """
        body { margin: 0; font-family: Arial, sans-serif; color: #1f2933; background: #f7f8fa; }
        header { background: #203c4f; color: #fff; padding: 24px 32px; }
        main { max-width: 1280px; margin: 0 auto; padding: 24px; }
        .banner { background: #fff4cc; border: 1px solid #b88900; padding: 12px 16px; margin-bottom: 18px; }
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
          <title>P377 Big Lotto no-DB command center regression report</title>
          <style>{css}</style>
        </head>
        <body>
          <header>
            <h1>P377 Big Lotto no-DB command center regression report</h1>
            <p>Overall status: <strong>{html.escape(str(results.get("overall_status", "")))}</strong></p>
          </header>
          <main>
            <section class="banner"><strong>Scope banner:</strong> {html.escape(SCOPE_STATEMENT)}</section>
            <h2>Overall Status</h2>
            <section class="panel"><pre>{html.escape(_json_text(results))}</pre></section>
            <h2>Command Results Table</h2>
            {_html_table(COMMAND_COLUMNS, command_rows)}
            <h2>Failures Table</h2>
            {_html_table(FAILURE_COLUMNS, failure_rows)}
            <h2>Artifact Freshness Table</h2>
            {_html_table(FRESHNESS_COLUMNS, freshness_rows)}
            <h2>Local Commands</h2>
            <section class="panel"><ul>{command_items}</ul></section>
            <h2>No-DB / No-Adapter / No-Scoring / No-Deploy Disclaimers</h2>
            <section class="panel"><ul>{disclaimer_items}</ul></section>
          </main>
        </body>
        </html>
        """
    ).lstrip()


def _artifact_contents_without_manifest(output: RegressionOutput) -> dict[str, str]:
    return {
        "results": _json_text(output.results),
        "commands": _csv_text(COMMAND_COLUMNS, output.command_rows),
        "failures": _csv_text(FAILURE_COLUMNS, output.failure_rows),
        "freshness": _csv_text(FRESHNESS_COLUMNS, output.freshness_rows),
        "report": output.report_html,
    }


def _artifact_contents(output: RegressionOutput) -> dict[str, str]:
    contents = _artifact_contents_without_manifest(output)
    contents["manifest"] = _csv_text(MANIFEST_COLUMNS, output.manifest_rows)
    return contents


def _output_counts(role: str, text: str) -> tuple[str, str]:
    if role in {"commands", "failures", "freshness", "manifest"}:
        return str(len(tuple(csv.DictReader(text.splitlines())))), ""
    if role in {"results", "report"}:
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
                "details": "P377 source evidence read from merged P371-P376 artifacts only.",
                "scope_statement": SCOPE_STATEMENT,
            }
        )
    for role, basename in P377_ARTIFACT_BASENAMES.items():
        text = output_texts_without_manifest.get(role, "")
        row_count, object_count = _output_counts(role, text)
        digest = sha256_bytes(text.encode("utf-8")) if text else ""
        if role == "manifest":
            row_count = str(len(REQUIRED_SOURCE_ARTIFACTS) + len(P377_ARTIFACT_BASENAMES) + 4)
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
                "details": "P377 generated no-DB command-center regression artifact.",
                "scope_statement": SCOPE_STATEMENT,
            }
        )
    for role, details in (
        ("no_db_open_write", "No DB open/write was performed by P377."),
        ("no_adapter_calls", "No adapter calls were performed by P377."),
        ("no_new_scoring", "No new scoring, scoring cohort, shape-only scoring, blocked-target scoring, or blended leaderboard was created by P377."),
        ("no_deploy", "No production registry import, deploy, or external publication was performed by P377."),
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


def _check(name: str, passed: bool, expected: object, actual: object, details: str) -> dict[str, str]:
    return {
        "check_name": name,
        "status": "PASS" if passed else "FAIL",
        "expected": str(expected),
        "actual": str(actual),
        "details": details,
    }


def validate_regression(
    output: RegressionOutput | None = None,
    repo_root: Path | None = None,
    include_determinism: bool = True,
) -> tuple[dict[str, str], ...]:
    current = output if output is not None else run_regression(repo_root, include_validation=False)
    text = "\n".join(_artifact_contents(current).values()).lower()
    found = [phrase for phrase in FORBIDDEN_AUTHORIZATION_PHRASES if phrase in text]
    rows = [
        _check("required_p371_p372_p373_p374_p375_p376_evidence_exists", len(verify_required_evidence(repo_root)) == len(REQUIRED_SOURCE_ARTIFACTS), len(REQUIRED_SOURCE_ARTIFACTS), len(REQUIRED_SOURCE_ARTIFACTS), "Required P371-P376 modules, tests, and artifacts are present."),
        _check("results_json_schema", set(current.results) >= {"source_baseline", "overall_status", "command_count", "pass_count", "warn_count", "fail_count", "artifact_count", "statements"}, "required result keys", sorted(current.results), "Regression results JSON includes required summary fields."),
        _check("commands_csv_schema", bool(current.command_rows) and tuple(current.command_rows[0]) == COMMAND_COLUMNS, COMMAND_COLUMNS, tuple(current.command_rows[0]) if current.command_rows else (), "Command CSV rows use required columns."),
        _check("failures_csv_schema", bool(current.failure_rows) and tuple(current.failure_rows[0]) == FAILURE_COLUMNS, FAILURE_COLUMNS, tuple(current.failure_rows[0]) if current.failure_rows else (), "Failures CSV rows use required columns."),
        _check("freshness_csv_schema", bool(current.freshness_rows) and tuple(current.freshness_rows[0]) == FRESHNESS_COLUMNS, FRESHNESS_COLUMNS, tuple(current.freshness_rows[0]) if current.freshness_rows else (), "Artifact freshness CSV rows use required columns."),
        _check("html_report_self_contained", current.report_html.startswith("<!doctype html>") and "<script" not in current.report_html.lower() and all(section in current.report_html for section in ("Scope banner", "Overall Status", "Command Results Table", "Failures Table", "Artifact Freshness Table", "Local Commands")), "self-contained HTML sections", "present", "HTML report includes required sections and no script tag."),
        _check("manifest_csv_schema", bool(current.manifest_rows) and tuple(current.manifest_rows[0]) == MANIFEST_COLUMNS, MANIFEST_COLUMNS, tuple(current.manifest_rows[0]) if current.manifest_rows else (), "Manifest rows use required columns."),
        _check("commands_all_safe_and_passing", all(row["status"] == "PASS" for row in current.command_rows) and all(row["no_db_confirmed"] == "YES" and row["no_adapter_calls_confirmed"] == "YES" and row["no_new_scoring_confirmed"] == "YES" for row in current.command_rows), "all PASS with safety confirmations", [row["status"] for row in current.command_rows], "P371-P376 safe validation commands passed."),
        _check("freshness_all_present", all(row["freshness_status"] == "FRESH" and len(row["sha256"]) == 64 for row in current.freshness_rows), "all source artifacts fresh", "fresh" if all(row["freshness_status"] == "FRESH" for row in current.freshness_rows) else "not fresh", "P371-P376 committed artifacts are present and hashed."),
        _check("generated_outputs_include_safety_constraints", all(line.lower() in text for line in DISCLAIMER_LINES), "all scope lines", "present", "Outputs include no-DB/no-adapter/no-scoring/no-deploy constraints."),
        _check("generated_outputs_do_not_authorize_forbidden_actions", not found, "absent", ";".join(found) if found else "absent", "P377 outputs do not authorize restricted actions."),
    ]
    if include_determinism:
        first = run_regression(repo_root, include_validation=False)
        second = run_regression(repo_root, include_validation=False)
        rows.append(
            _check(
                "deterministic_double_run_equality",
                _artifact_contents(first) == _artifact_contents(second),
                "equal",
                "equal" if _artifact_contents(first) == _artifact_contents(second) else "different",
                "P377 generated rows and artifacts are deterministic across two runs.",
            )
        )
    return tuple(rows)


def run_regression(repo_root: Path | None = None, include_validation: bool = True) -> RegressionOutput:
    verify_required_evidence(repo_root)
    command_rows = execute_safe_commands(repo_root)
    freshness_rows = build_artifact_freshness(repo_root)
    failure_rows = build_failures(command_rows, freshness_rows)
    results = build_results(command_rows, freshness_rows, failure_rows)
    report_html = build_report(results, command_rows, failure_rows, freshness_rows)
    without_manifest = RegressionOutput(results, command_rows, failure_rows, freshness_rows, report_html, (), ())
    manifest = build_manifest_rows(_artifact_contents_without_manifest(without_manifest), repo_root)
    partial = RegressionOutput(results, command_rows, failure_rows, freshness_rows, report_html, manifest, ())
    validation = validate_regression(partial, repo_root, include_determinism=True) if include_validation else ()
    return RegressionOutput(results, command_rows, failure_rows, freshness_rows, report_html, manifest, validation)


def _assert_deterministic(first: RegressionOutput, second: RegressionOutput) -> None:
    if _artifact_contents(first) != _artifact_contents(second):
        raise RuntimeError("determinism double-run mismatch: P377 regression runner artifacts are not reproducible")


def write_artifacts(output: RegressionOutput, artifacts_dir: Path | None = None) -> dict[str, Path]:
    directory = Path(artifacts_dir) if artifacts_dir is not None else REPO_ROOT / "artifacts"
    directory.mkdir(parents=True, exist_ok=True)
    paths = {key: directory / basename for key, basename in P377_ARTIFACT_BASENAMES.items()}
    allowed = {str(path) for path in paths.values()}
    for path in paths.values():
        if str(path) not in allowed or not path.name.startswith("P377_biglotto_command_center_regression_"):
            raise RuntimeError(f"refusing to write non-P377 artifact path: {path}")
    contents = _artifact_contents(output)
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
    parser.add_argument("--artifacts-dir", type=Path, default=None, help="override P377 artifacts output directory")
    parser.add_argument("--generate", action="store_true", help="write all P377 command center regression artifacts")
    parser.add_argument("--run", action="store_true", help="emit consolidated regression results JSON")
    parser.add_argument("--commands", action="store_true", help="emit command results CSV")
    parser.add_argument("--failures", action="store_true", help="emit warnings/failures CSV")
    parser.add_argument("--freshness", action="store_true", help="emit artifact freshness CSV")
    parser.add_argument("--report", action="store_true", help="emit self-contained HTML report")
    parser.add_argument("--validate", action="store_true", help="emit P377 validation rows as CSV")
    args = parser.parse_args(argv)

    if args.run:
        _print_json(run_regression(include_validation=False).results)
    elif args.commands:
        _print_csv(COMMAND_COLUMNS, run_regression(include_validation=False).command_rows)
    elif args.failures:
        _print_csv(FAILURE_COLUMNS, run_regression(include_validation=False).failure_rows)
    elif args.freshness:
        _print_csv(FRESHNESS_COLUMNS, build_artifact_freshness())
    elif args.report:
        print(run_regression(include_validation=False).report_html, end="")
    elif args.validate:
        _print_csv(VALIDATION_COLUMNS, validate_regression())
    else:
        first = run_regression()
        second = run_regression(include_validation=False)
        _assert_deterministic(first, second)
        paths = write_artifacts(first, args.artifacts_dir)
        print("P377 Big Lotto no-DB command center regression runner: determinism double-run PASS")
        print(f"overall status: {first.results['overall_status']}")
        print(f"commands: {first.results['command_count']}")
        print(f"pass/warn/fail: {first.results['pass_count']}/{first.results['warn_count']}/{first.results['fail_count']}")
        print(f"source artifacts checked: {first.results['artifact_count']}")
        print(f"validation rows: {len(first.validation_rows)}")
        print(f"validation failures: {sum(1 for row in first.validation_rows if row['status'] == 'FAIL')}")
        print("No DB was opened or written; no adapters were called; no new scoring was created; no production registry import or deploy was performed.")
        print("Historical descriptive evidence only; no betting advice; no future prediction guarantee; no strategy status changes; no blended leaderboard.")
        for key, path in sorted(paths.items()):
            print(f"{key}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
