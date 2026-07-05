"""P378 Big Lotto no-DB regression run archive/comparison.

This module archives the merged P377 no-DB regression runner output as a
deterministic snapshot and comparison bundle. It reads only committed P377
source/artifacts, writes only P378-prefixed archive artifacts, and does not
open or write a DB, call adapters, create new scoring cohorts, import
production registries, deploy, provide betting advice, or make
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
TASK = "P378_biglotto_regression_run_archive"
GENERATED_AT = "DETERMINISTIC_PLACEHOLDER"
P377_BASELINE_COMMIT = "0fd6dfb95fcb8389519aee6359e91696119da649"
SNAPSHOT_ID = f"P378-P377-{P377_BASELINE_COMMIT[:12]}"

SOURCE_BASELINE = {
    "required_origin_main_merge_commit": P377_BASELINE_COMMIT,
    "source_task": "P377_biglotto_command_center_regression_runner",
    "archive_mode": "read_only_no_db_p377_artifact_snapshot_and_comparison",
}

P377_SOURCE_ARTIFACTS = {
    "module": "recovered_strategies/biglotto/no_db_command_center_regression_runner.py",
    "results": "artifacts/P377_biglotto_command_center_regression_results.json",
    "commands": "artifacts/P377_biglotto_command_center_regression_commands.csv",
    "failures": "artifacts/P377_biglotto_command_center_regression_failures.csv",
    "freshness": "artifacts/P377_biglotto_command_center_regression_artifact_freshness.csv",
    "report": "artifacts/P377_biglotto_command_center_regression_report.html",
    "manifest": "artifacts/P377_biglotto_command_center_regression_manifest.csv",
}

P378_ARTIFACT_BASENAMES = {
    "index": "P378_biglotto_regression_run_archive_index.json",
    "snapshot": "P378_biglotto_regression_run_archive_snapshot.json",
    "comparison": "P378_biglotto_regression_run_archive_comparison.json",
    "command_delta": "P378_biglotto_regression_run_archive_command_delta.csv",
    "freshness_delta": "P378_biglotto_regression_run_archive_freshness_delta.csv",
    "report": "P378_biglotto_regression_run_archive_report.html",
    "manifest": "P378_biglotto_regression_run_archive_manifest.csv",
}

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
    "Not production release approval.",
    "P378 reads only merged P377 regression artifacts and writes only P378-prefixed archive artifacts.",
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

COMMAND_DELTA_COLUMNS = (
    "command_id",
    "previous_status",
    "current_status",
    "status_delta",
    "previous_summary",
    "current_summary",
    "delta_status",
    "notes",
)

FRESHNESS_DELTA_COLUMNS = (
    "artifact_path",
    "previous_sha256",
    "current_sha256",
    "sha256_delta",
    "previous_row_or_object_count",
    "current_row_or_object_count",
    "freshness_delta_status",
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

NO_DB_NO_ADAPTER_NO_SCORING_NO_DEPLOY_STATEMENT = (
    "No DB was opened or written; no adapters were called; no new scoring, scoring cohort, "
    "shape-only scoring, blocked-target scoring, or blended leaderboard was created; no production "
    "registry import or deploy was performed."
)


@dataclass(frozen=True)
class ArchiveOutput:
    index: dict[str, object]
    snapshot: dict[str, object]
    comparison: dict[str, object]
    command_delta_rows: tuple[dict[str, str], ...]
    freshness_delta_rows: tuple[dict[str, str], ...]
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


def _read_json(relpath: str, repo_root: Path | None = None) -> object:
    with open(_artifact_path(relpath, repo_root), encoding="utf-8") as handle:
        return json.load(handle)


def _read_csv(relpath: str, repo_root: Path | None = None) -> tuple[dict[str, str], ...]:
    with open(_artifact_path(relpath, repo_root), newline="", encoding="utf-8") as handle:
        return tuple(dict(row) for row in csv.DictReader(handle))


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


def verify_required_evidence(repo_root: Path | None = None) -> tuple[Path, ...]:
    paths = tuple(_artifact_path(relpath, repo_root) for relpath in P377_SOURCE_ARTIFACTS.values())
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise RuntimeError(f"required P377 regression evidence missing: {missing}")
    return paths


def source_inventory(repo_root: Path | None = None) -> tuple[dict[str, str], ...]:
    verify_required_evidence(repo_root)
    rows: list[dict[str, str]] = []
    for role, relpath in P377_SOURCE_ARTIFACTS.items():
        path = _artifact_path(relpath, repo_root)
        rows.append(
            {
                "artifact_role": role,
                "path": relpath,
                "sha256": sha256_file(path),
                "row_or_object_count": _count_artifact(path),
            }
        )
    return tuple(rows)


def _p377_results(repo_root: Path | None = None) -> Mapping[str, object]:
    payload = _read_json(P377_SOURCE_ARTIFACTS["results"], repo_root)
    if not isinstance(payload, dict):
        raise RuntimeError("P377 results artifact must contain a JSON object")
    return payload


def build_snapshot(repo_root: Path | None = None) -> dict[str, object]:
    verify_required_evidence(repo_root)
    results = _p377_results(repo_root)
    command_rows = _read_csv(P377_SOURCE_ARTIFACTS["commands"], repo_root)
    freshness_rows = _read_csv(P377_SOURCE_ARTIFACTS["freshness"], repo_root)
    return {
        "task": TASK,
        "generated_at": GENERATED_AT,
        "snapshot_id": SNAPSHOT_ID,
        "source_baseline": SOURCE_BASELINE,
        "p377_overall_status": results.get("overall_status", ""),
        "p377_command_count": int(results.get("command_count", len(command_rows))),
        "p377_pass_count": int(results.get("pass_count", 0)),
        "p377_warn_count": int(results.get("warn_count", 0)),
        "p377_fail_count": int(results.get("fail_count", 0)),
        "p377_artifact_count": int(results.get("artifact_count", len(freshness_rows))),
        "p377_artifact_sha256_inventory": source_inventory(repo_root),
        "statements": STATEMENTS,
        "scope_lines": DISCLAIMER_LINES,
        "no_db_no_adapter_no_scoring_no_deploy_statement": NO_DB_NO_ADAPTER_NO_SCORING_NO_DEPLOY_STATEMENT,
    }


def _metric_subset(snapshot: Mapping[str, object]) -> dict[str, object]:
    keys = (
        "p377_overall_status",
        "p377_command_count",
        "p377_pass_count",
        "p377_warn_count",
        "p377_fail_count",
        "p377_artifact_count",
    )
    return {key: snapshot.get(key) for key in keys}


def build_comparison(snapshot: Mapping[str, object]) -> dict[str, object]:
    previous = _metric_subset(snapshot)
    current = _metric_subset(snapshot)
    changed_metrics = {
        key: {"previous": previous[key], "current": current[key]}
        for key in sorted(current)
        if previous[key] != current[key]
    }
    unchanged_metrics = {
        key: {"previous": previous[key], "current": current[key]}
        for key in sorted(current)
        if previous[key] == current[key]
    }
    return {
        "task": TASK,
        "generated_at": GENERATED_AT,
        "baseline_snapshot_id": snapshot["snapshot_id"],
        "current_snapshot_id": snapshot["snapshot_id"],
        "comparison_status": "PASS" if not changed_metrics and snapshot.get("p377_overall_status") == "PASS" else "WARN",
        "initial_archive": True,
        "changed_metrics": changed_metrics,
        "unchanged_metrics": unchanged_metrics,
        "notes": (
            "Initial P378 archive: no previous committed P378 archive snapshot exists. "
            "The first comparison intentionally uses baseline=current so future P378 archives can compare "
            "against this deterministic snapshot."
        ),
        "statements": STATEMENTS,
        "scope_lines": DISCLAIMER_LINES,
    }


def build_command_delta(repo_root: Path | None = None) -> tuple[dict[str, str], ...]:
    rows = []
    for command in _read_csv(P377_SOURCE_ARTIFACTS["commands"], repo_root):
        current_status = command.get("status", "")
        current_summary = command.get("normalized_output_summary", "")
        rows.append(
            {
                "command_id": command.get("command_id", ""),
                "previous_status": current_status,
                "current_status": current_status,
                "status_delta": "UNCHANGED",
                "previous_summary": current_summary,
                "current_summary": current_summary,
                "delta_status": "PASS",
                "notes": "Initial P378 archive baseline=current; P377 command row read-only, not re-executed.",
            }
        )
    return tuple(rows)


def build_freshness_delta(repo_root: Path | None = None) -> tuple[dict[str, str], ...]:
    rows = []
    for artifact in _read_csv(P377_SOURCE_ARTIFACTS["freshness"], repo_root):
        sha = artifact.get("sha256", "")
        count = artifact.get("row_or_object_count", "")
        rows.append(
            {
                "artifact_path": artifact.get("artifact_path", ""),
                "previous_sha256": sha,
                "current_sha256": sha,
                "sha256_delta": "UNCHANGED",
                "previous_row_or_object_count": count,
                "current_row_or_object_count": count,
                "freshness_delta_status": "PASS",
                "notes": "Initial P378 archive baseline=current; P377 freshness artifact read-only.",
            }
        )
    return tuple(rows)


def build_index(
    snapshot: Mapping[str, object],
    comparison: Mapping[str, object],
    repo_root: Path | None = None,
) -> dict[str, object]:
    return {
        "task": TASK,
        "generated_at": GENERATED_AT,
        "source_baseline": SOURCE_BASELINE,
        "source_p377_artifact_paths": P377_SOURCE_ARTIFACTS,
        "source_p377_sha256": {row["path"]: row["sha256"] for row in source_inventory(repo_root)},
        "generated_p378_artifact_paths": {
            role: f"artifacts/{basename}" for role, basename in P378_ARTIFACT_BASENAMES.items()
        },
        "current_run_snapshot_id": snapshot["snapshot_id"],
        "initial_archive": bool(comparison["initial_archive"]),
        "statements": STATEMENTS,
        "scope_lines": DISCLAIMER_LINES,
        "no_db_no_adapter_no_scoring_no_deploy_statement": NO_DB_NO_ADAPTER_NO_SCORING_NO_DEPLOY_STATEMENT,
    }


def _html_table(columns: Sequence[str], rows: Iterable[Mapping[str, object]]) -> str:
    head = "".join(f"<th>{html.escape(column)}</th>" for column in columns)
    body = []
    for row in rows:
        cells = "".join(f"<td>{html.escape(str(row.get(column, '')))}</td>" for column in columns)
        body.append(f"<tr>{cells}</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def build_report(
    index: Mapping[str, object],
    snapshot: Mapping[str, object],
    comparison: Mapping[str, object],
    command_delta_rows: Sequence[Mapping[str, str]],
    freshness_delta_rows: Sequence[Mapping[str, str]],
    repo_root: Path | None = None,
) -> str:
    local_commands = (
        "python3 -m recovered_strategies.biglotto.no_db_regression_run_archive --generate",
        "python3 -m recovered_strategies.biglotto.no_db_regression_run_archive --index",
        "python3 -m recovered_strategies.biglotto.no_db_regression_run_archive --snapshot",
        "python3 -m recovered_strategies.biglotto.no_db_regression_run_archive --compare",
        "python3 -m recovered_strategies.biglotto.no_db_regression_run_archive --command-delta",
        "python3 -m recovered_strategies.biglotto.no_db_regression_run_archive --freshness-delta",
        "python3 -m recovered_strategies.biglotto.no_db_regression_run_archive --report",
        "python3 -m recovered_strategies.biglotto.no_db_regression_run_archive --validate",
    )
    command_items = "".join(f"<li><code>{html.escape(command)}</code></li>" for command in local_commands)
    disclaimer_items = "".join(f"<li>{html.escape(line)}</li>" for line in DISCLAIMER_LINES)
    source_rows = source_inventory(repo_root)
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
          <title>P378 Big Lotto no-DB regression run archive report</title>
          <style>{css}</style>
        </head>
        <body>
          <header>
            <h1>P378 Big Lotto no-DB regression run archive report</h1>
            <p>Comparison status: <strong>{html.escape(str(comparison.get("comparison_status", "")))}</strong></p>
          </header>
          <main>
            <section class="banner"><strong>Scope banner:</strong> {html.escape(SCOPE_STATEMENT)}</section>
            <h2>Current Snapshot Summary</h2>
            <section class="panel"><pre>{html.escape(_json_text(snapshot))}</pre></section>
            <h2>Comparison Summary</h2>
            <section class="panel"><pre>{html.escape(_json_text(comparison))}</pre></section>
            <h2>Command Delta Table</h2>
            {_html_table(COMMAND_DELTA_COLUMNS, command_delta_rows)}
            <h2>Freshness Delta Table</h2>
            {_html_table(FRESHNESS_DELTA_COLUMNS, freshness_delta_rows)}
            <h2>Source P377 Artifact Inventory</h2>
            {_html_table(("artifact_role", "path", "sha256", "row_or_object_count"), source_rows)}
            <h2>Archive Index</h2>
            <section class="panel"><pre>{html.escape(_json_text(index))}</pre></section>
            <h2>Local Commands</h2>
            <section class="panel"><ul>{command_items}</ul></section>
            <h2>No-DB / No-Adapter / No-Scoring / No-Deploy Disclaimers</h2>
            <section class="panel"><ul>{disclaimer_items}</ul></section>
          </main>
        </body>
        </html>
        """
    ).lstrip()


def _artifact_contents_without_manifest(output: ArchiveOutput) -> dict[str, str]:
    return {
        "index": _json_text(output.index),
        "snapshot": _json_text(output.snapshot),
        "comparison": _json_text(output.comparison),
        "command_delta": _csv_text(COMMAND_DELTA_COLUMNS, output.command_delta_rows),
        "freshness_delta": _csv_text(FRESHNESS_DELTA_COLUMNS, output.freshness_delta_rows),
        "report": output.report_html,
    }


def _artifact_contents(output: ArchiveOutput) -> dict[str, str]:
    contents = _artifact_contents_without_manifest(output)
    contents["manifest"] = _csv_text(MANIFEST_COLUMNS, output.manifest_rows)
    return contents


def _output_counts(role: str, text: str) -> tuple[str, str]:
    if role in {"command_delta", "freshness_delta", "manifest"}:
        return str(len(tuple(csv.DictReader(text.splitlines())))), ""
    if role in {"index", "snapshot", "comparison"}:
        return "", f"json_keys={len(json.loads(text))}"
    if role == "report":
        return "", "1"
    return "", ""


def build_manifest_rows(output_texts_without_manifest: Mapping[str, str], repo_root: Path | None = None) -> tuple[dict[str, str], ...]:
    rows: list[dict[str, str]] = []
    for source in source_inventory(repo_root):
        rows.append(
            {
                "artifact_group": "source",
                "artifact_role": source["artifact_role"],
                "path": source["path"],
                "source_sha256": source["sha256"],
                "output_row_count": "",
                "output_object_count": "",
                "no_db_open_write": "YES",
                "no_adapter_calls": "YES",
                "no_new_scoring": "YES",
                "no_deploy": "YES",
                "details": "P378 source evidence read from merged P377 artifacts only.",
                "scope_statement": SCOPE_STATEMENT,
            }
        )
    for role, basename in P378_ARTIFACT_BASENAMES.items():
        text = output_texts_without_manifest.get(role, "")
        row_count, object_count = _output_counts(role, text)
        digest = sha256_bytes(text.encode("utf-8")) if text else ""
        if role == "manifest":
            row_count = str(len(P377_SOURCE_ARTIFACTS) + len(P378_ARTIFACT_BASENAMES) + 4)
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
                "details": "P378 generated no-DB regression run archive artifact.",
                "scope_statement": SCOPE_STATEMENT,
            }
        )
    for role, details in (
        ("no_db_open_write", "No DB open/write was performed by P378."),
        ("no_adapter_calls", "No adapter calls were performed by P378."),
        ("no_new_scoring", "No new scoring, scoring cohort, shape-only scoring, blocked-target scoring, or blended leaderboard was created by P378."),
        ("no_deploy", "No production registry import, deploy, or external publication was performed by P378."),
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


def validate_archive(
    output: ArchiveOutput | None = None,
    repo_root: Path | None = None,
    include_determinism: bool = True,
) -> tuple[dict[str, str], ...]:
    current = output if output is not None else run_archive(repo_root, include_validation=False)
    text = "\n".join(_artifact_contents(current).values()).lower()
    found = [phrase for phrase in FORBIDDEN_AUTHORIZATION_PHRASES if phrase in text]
    rows = [
        _check("required_p377_evidence_exists", len(verify_required_evidence(repo_root)) == len(P377_SOURCE_ARTIFACTS), len(P377_SOURCE_ARTIFACTS), len(P377_SOURCE_ARTIFACTS), "Required P377 module and artifacts are present."),
        _check("archive_index_json_schema", set(current.index) >= {"source_baseline", "source_p377_artifact_paths", "source_p377_sha256", "generated_p378_artifact_paths", "current_run_snapshot_id", "initial_archive"}, "required index keys", sorted(current.index), "Archive index includes required fields."),
        _check("run_snapshot_json_schema", set(current.snapshot) >= {"snapshot_id", "source_baseline", "p377_overall_status", "p377_command_count", "p377_pass_count", "p377_warn_count", "p377_fail_count", "p377_artifact_count", "p377_artifact_sha256_inventory"}, "required snapshot keys", sorted(current.snapshot), "Run snapshot includes required P377 metrics and inventory."),
        _check("comparison_json_schema", set(current.comparison) >= {"baseline_snapshot_id", "current_snapshot_id", "comparison_status", "initial_archive", "changed_metrics", "unchanged_metrics", "notes"}, "required comparison keys", sorted(current.comparison), "Comparison JSON includes required fields."),
        _check("command_delta_csv_schema", bool(current.command_delta_rows) and tuple(current.command_delta_rows[0]) == COMMAND_DELTA_COLUMNS, COMMAND_DELTA_COLUMNS, tuple(current.command_delta_rows[0]) if current.command_delta_rows else (), "Command delta rows use required columns."),
        _check("freshness_delta_csv_schema", bool(current.freshness_delta_rows) and tuple(current.freshness_delta_rows[0]) == FRESHNESS_DELTA_COLUMNS, FRESHNESS_DELTA_COLUMNS, tuple(current.freshness_delta_rows[0]) if current.freshness_delta_rows else (), "Freshness delta rows use required columns."),
        _check("html_report_self_contained", current.report_html.startswith("<!doctype html>") and "<script" not in current.report_html.lower() and all(section in current.report_html for section in ("Scope banner", "Current Snapshot Summary", "Comparison Summary", "Command Delta Table", "Freshness Delta Table", "Source P377 Artifact Inventory", "Local Commands")), "self-contained HTML sections", "present", "HTML report includes required sections and no script tag."),
        _check("manifest_csv_schema", bool(current.manifest_rows) and tuple(current.manifest_rows[0]) == MANIFEST_COLUMNS, MANIFEST_COLUMNS, tuple(current.manifest_rows[0]) if current.manifest_rows else (), "Manifest rows use required columns."),
        _check("p377_results_pass", current.snapshot.get("p377_overall_status") == "PASS", "PASS", current.snapshot.get("p377_overall_status"), "P377 source regression result remains PASS."),
        _check("deltas_initial_archive_unchanged", current.comparison.get("initial_archive") is True and not current.comparison.get("changed_metrics") and all(row["delta_status"] == "PASS" for row in current.command_delta_rows) and all(row["freshness_delta_status"] == "PASS" for row in current.freshness_delta_rows), "initial unchanged PASS deltas", "PASS", "Initial archive compares baseline=current."),
        _check("generated_outputs_include_safety_constraints", all(line.lower() in text for line in DISCLAIMER_LINES), "all scope lines", "present", "Outputs include no-DB/no-adapter/no-scoring/no-deploy constraints."),
        _check("generated_outputs_do_not_authorize_forbidden_actions", not found, "absent", ";".join(found) if found else "absent", "P378 outputs do not authorize restricted actions."),
    ]
    if include_determinism:
        first = run_archive(repo_root, include_validation=False)
        second = run_archive(repo_root, include_validation=False)
        rows.append(
            _check(
                "deterministic_double_run_equality",
                _artifact_contents(first) == _artifact_contents(second),
                "equal",
                "equal" if _artifact_contents(first) == _artifact_contents(second) else "different",
                "P378 generated rows and artifacts are deterministic across two runs.",
            )
        )
    return tuple(rows)


def run_archive(repo_root: Path | None = None, include_validation: bool = True) -> ArchiveOutput:
    verify_required_evidence(repo_root)
    snapshot = build_snapshot(repo_root)
    comparison = build_comparison(snapshot)
    command_delta = build_command_delta(repo_root)
    freshness_delta = build_freshness_delta(repo_root)
    index = build_index(snapshot, comparison, repo_root)
    report_html = build_report(index, snapshot, comparison, command_delta, freshness_delta, repo_root)
    without_manifest = ArchiveOutput(index, snapshot, comparison, command_delta, freshness_delta, report_html, (), ())
    manifest = build_manifest_rows(_artifact_contents_without_manifest(without_manifest), repo_root)
    partial = ArchiveOutput(index, snapshot, comparison, command_delta, freshness_delta, report_html, manifest, ())
    validation = validate_archive(partial, repo_root, include_determinism=True) if include_validation else ()
    return ArchiveOutput(index, snapshot, comparison, command_delta, freshness_delta, report_html, manifest, validation)


def _assert_deterministic(first: ArchiveOutput, second: ArchiveOutput) -> None:
    if _artifact_contents(first) != _artifact_contents(second):
        raise RuntimeError("determinism double-run mismatch: P378 archive artifacts are not reproducible")


def write_artifacts(output: ArchiveOutput, artifacts_dir: Path | None = None) -> dict[str, Path]:
    directory = Path(artifacts_dir) if artifacts_dir is not None else REPO_ROOT / "artifacts"
    directory.mkdir(parents=True, exist_ok=True)
    paths = {key: directory / basename for key, basename in P378_ARTIFACT_BASENAMES.items()}
    for path in paths.values():
        if not path.name.startswith("P378_biglotto_regression_run_archive_"):
            raise RuntimeError(f"refusing to write non-P378 artifact path: {path}")
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
    parser.add_argument("--artifacts-dir", type=Path, default=None, help="override P378 artifacts output directory")
    parser.add_argument("--generate", action="store_true", help="write all P378 regression run archive artifacts")
    parser.add_argument("--index", action="store_true", help="emit archive index JSON")
    parser.add_argument("--snapshot", action="store_true", help="emit current run snapshot JSON")
    parser.add_argument("--compare", action="store_true", help="emit previous/current comparison JSON")
    parser.add_argument("--command-delta", action="store_true", help="emit command delta CSV")
    parser.add_argument("--freshness-delta", action="store_true", help="emit freshness delta CSV")
    parser.add_argument("--report", action="store_true", help="emit self-contained HTML archive report")
    parser.add_argument("--validate", action="store_true", help="emit P378 validation rows as CSV")
    args = parser.parse_args(argv)

    if args.index:
        _print_json(run_archive(include_validation=False).index)
    elif args.snapshot:
        _print_json(run_archive(include_validation=False).snapshot)
    elif args.compare:
        _print_json(run_archive(include_validation=False).comparison)
    elif args.command_delta:
        _print_csv(COMMAND_DELTA_COLUMNS, build_command_delta())
    elif args.freshness_delta:
        _print_csv(FRESHNESS_DELTA_COLUMNS, build_freshness_delta())
    elif args.report:
        print(run_archive(include_validation=False).report_html, end="")
    elif args.validate:
        _print_csv(VALIDATION_COLUMNS, validate_archive())
    else:
        first = run_archive()
        second = run_archive(include_validation=False)
        _assert_deterministic(first, second)
        paths = write_artifacts(first, args.artifacts_dir)
        print("P378 Big Lotto no-DB regression run archive: determinism double-run PASS")
        print(f"snapshot id: {first.snapshot['snapshot_id']}")
        print(f"comparison status: {first.comparison['comparison_status']}")
        print(f"initial archive: {first.comparison['initial_archive']}")
        print(f"p377 overall status: {first.snapshot['p377_overall_status']}")
        print(f"p377 commands pass/warn/fail: {first.snapshot['p377_pass_count']}/{first.snapshot['p377_warn_count']}/{first.snapshot['p377_fail_count']}")
        print(f"source P377 artifacts checked: {len(P377_SOURCE_ARTIFACTS)}")
        print(f"validation rows: {len(first.validation_rows)}")
        print(f"validation failures: {sum(1 for row in first.validation_rows if row['status'] == 'FAIL')}")
        print("No DB was opened or written; no adapters were called; no new scoring was created; no production registry import or deploy was performed.")
        print("Historical descriptive evidence only; no betting advice; no future prediction guarantee; no strategy status changes; no blended leaderboard.")
        for key, path in sorted(paths.items()):
            print(f"{key}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
