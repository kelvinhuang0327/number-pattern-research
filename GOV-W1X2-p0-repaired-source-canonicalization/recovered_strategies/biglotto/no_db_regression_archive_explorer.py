"""P379 Big Lotto no-DB regression archive explorer.

This module adds a deterministic query/explorer layer over the committed P378
regression archive bundle. It reads only committed P378 source/artifacts, writes
only P379-prefixed explorer artifacts, and does not open or write a DB, call
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

from recovered_strategies.biglotto import no_db_regression_run_archive as archive

REPO_ROOT = Path(__file__).resolve().parents[2]
TASK = "P379_biglotto_regression_archive_explorer"
GENERATED_AT = "DETERMINISTIC_PLACEHOLDER"
P378_BASELINE_COMMIT = "a863bfc25766feedb98c3d1108b8112cb5fd56a2"

SOURCE_BASELINE = {
    "required_origin_main_commit": P378_BASELINE_COMMIT,
    "source_task": archive.TASK,
    "explorer_mode": "read_only_no_db_p378_artifact_query_layer",
}

P378_SOURCE_ARTIFACTS = {
    "module": "recovered_strategies/biglotto/no_db_regression_run_archive.py",
    "index": "artifacts/P378_biglotto_regression_run_archive_index.json",
    "snapshot": "artifacts/P378_biglotto_regression_run_archive_snapshot.json",
    "comparison": "artifacts/P378_biglotto_regression_run_archive_comparison.json",
    "command_delta": "artifacts/P378_biglotto_regression_run_archive_command_delta.csv",
    "freshness_delta": "artifacts/P378_biglotto_regression_run_archive_freshness_delta.csv",
    "report": "artifacts/P378_biglotto_regression_run_archive_report.html",
    "manifest": "artifacts/P378_biglotto_regression_run_archive_manifest.csv",
    "tests": "tests/test_p378_biglotto_regression_run_archive.py",
}

P379_ARTIFACT_BASENAMES = {
    "index": "P379_biglotto_regression_archive_explorer_index.json",
    "catalog": "P379_biglotto_regression_archive_explorer_catalog.csv",
    "snapshot_summary": "P379_biglotto_regression_archive_explorer_snapshot_summary.json",
    "command_view": "P379_biglotto_regression_archive_explorer_command_view.csv",
    "freshness_view": "P379_biglotto_regression_archive_explorer_freshness_view.csv",
    "query_snapshots": "P379_biglotto_regression_archive_explorer_query_snapshots.json",
    "html": "P379_biglotto_regression_archive_explorer_report.html",
    "manifest": "P379_biglotto_regression_archive_explorer_manifest.csv",
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
    "P379 reads only committed P378 regression archive artifacts and writes only P379-prefixed explorer artifacts.",
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

CATALOG_COLUMNS = (
    "artifact_role",
    "path",
    "format",
    "sha256",
    "row_or_object_count",
    "explorer_route",
    "source_task",
    "no_db_open_write",
    "no_adapter_calls",
    "no_new_scoring",
    "no_deploy",
    "scope_statement",
)

COMMAND_VIEW_COLUMNS = (
    "command_id",
    "previous_status",
    "current_status",
    "status_delta",
    "delta_status",
    "previous_summary",
    "current_summary",
    "notes",
    "explorer_status",
    "no_db_open_write",
    "no_adapter_calls",
    "no_new_scoring",
)

FRESHNESS_VIEW_COLUMNS = (
    "artifact_path",
    "artifact_role",
    "previous_sha256",
    "current_sha256",
    "sha256_delta",
    "previous_row_or_object_count",
    "current_row_or_object_count",
    "freshness_delta_status",
    "notes",
    "explorer_status",
    "no_db_open_write",
    "no_adapter_calls",
    "no_new_scoring",
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

FORBIDDEN_AUTHORIZATION_PHRASES = archive.FORBIDDEN_AUTHORIZATION_PHRASES


@dataclass(frozen=True)
class ExplorerOutput:
    index: dict[str, object]
    catalog_rows: tuple[dict[str, str], ...]
    snapshot_summary: dict[str, object]
    command_view_rows: tuple[dict[str, str], ...]
    freshness_view_rows: tuple[dict[str, str], ...]
    query_snapshots: dict[str, object]
    html_text: str
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


def _format_from_path(path: str) -> str:
    suffix = Path(path).suffix.lower().lstrip(".")
    return suffix or "file"


def verify_required_artifacts(repo_root: Path | None = None) -> tuple[Path, ...]:
    paths = tuple(_artifact_path(relpath, repo_root) for relpath in P378_SOURCE_ARTIFACTS.values())
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise RuntimeError(f"required P378 regression archive evidence missing: {missing}")
    return paths


def source_inventory(repo_root: Path | None = None) -> tuple[dict[str, str], ...]:
    verify_required_artifacts(repo_root)
    rows: list[dict[str, str]] = []
    for role, relpath in P378_SOURCE_ARTIFACTS.items():
        path = _artifact_path(relpath, repo_root)
        rows.append(
            {
                "artifact_role": role,
                "path": relpath,
                "format": _format_from_path(relpath),
                "sha256": sha256_file(path),
                "row_or_object_count": _count_artifact(path),
            }
        )
    return tuple(rows)


def build_catalog(repo_root: Path | None = None) -> tuple[dict[str, str], ...]:
    rows = []
    for source in source_inventory(repo_root):
        role = source["artifact_role"]
        route = {
            "index": "summary",
            "snapshot": "summary",
            "comparison": "summary",
            "command_delta": "commands",
            "freshness_delta": "freshness",
            "report": "html",
            "manifest": "catalog",
            "module": "catalog",
            "tests": "catalog",
        }.get(role, "catalog")
        rows.append(
            {
                **source,
                "explorer_route": route,
                "source_task": archive.TASK,
                "no_db_open_write": "YES",
                "no_adapter_calls": "YES",
                "no_new_scoring": "YES",
                "no_deploy": "YES",
                "scope_statement": SCOPE_STATEMENT,
            }
        )
    return tuple(rows)


def build_snapshot_summary(repo_root: Path | None = None) -> dict[str, object]:
    snapshot = _read_json(P378_SOURCE_ARTIFACTS["snapshot"], repo_root)
    comparison = _read_json(P378_SOURCE_ARTIFACTS["comparison"], repo_root)
    index = _read_json(P378_SOURCE_ARTIFACTS["index"], repo_root)
    if not isinstance(snapshot, dict) or not isinstance(comparison, dict) or not isinstance(index, dict):
        raise RuntimeError("P378 index, snapshot, and comparison artifacts must be JSON objects")
    return {
        "task": TASK,
        "generated_at": GENERATED_AT,
        "source_baseline": SOURCE_BASELINE,
        "p378_task": snapshot.get("task"),
        "p378_snapshot_id": snapshot.get("snapshot_id"),
        "p378_initial_archive": comparison.get("initial_archive"),
        "p378_comparison_status": comparison.get("comparison_status"),
        "p377_overall_status": snapshot.get("p377_overall_status"),
        "p377_command_count": snapshot.get("p377_command_count"),
        "p377_pass_count": snapshot.get("p377_pass_count"),
        "p377_warn_count": snapshot.get("p377_warn_count"),
        "p377_fail_count": snapshot.get("p377_fail_count"),
        "p377_artifact_count": snapshot.get("p377_artifact_count"),
        "p378_generated_artifact_paths": index.get("generated_p378_artifact_paths", {}),
        "changed_metrics": comparison.get("changed_metrics", {}),
        "unchanged_metric_names": sorted((comparison.get("unchanged_metrics") or {}).keys()),
        "statements": STATEMENTS,
        "scope_lines": DISCLAIMER_LINES,
    }


def build_command_view(repo_root: Path | None = None) -> tuple[dict[str, str], ...]:
    rows = []
    for row in _read_csv(P378_SOURCE_ARTIFACTS["command_delta"], repo_root):
        delta_status = row.get("delta_status", "")
        rows.append(
            {
                "command_id": row.get("command_id", ""),
                "previous_status": row.get("previous_status", ""),
                "current_status": row.get("current_status", ""),
                "status_delta": row.get("status_delta", ""),
                "delta_status": delta_status,
                "previous_summary": row.get("previous_summary", ""),
                "current_summary": row.get("current_summary", ""),
                "notes": row.get("notes", ""),
                "explorer_status": "QUERYABLE" if delta_status == "PASS" else "REVIEW",
                "no_db_open_write": "YES",
                "no_adapter_calls": "YES",
                "no_new_scoring": "YES",
            }
        )
    return tuple(rows)


def build_freshness_view(repo_root: Path | None = None) -> tuple[dict[str, str], ...]:
    rows = []
    for row in _read_csv(P378_SOURCE_ARTIFACTS["freshness_delta"], repo_root):
        path = row.get("artifact_path", "")
        rows.append(
            {
                "artifact_path": path,
                "artifact_role": Path(path).stem,
                "previous_sha256": row.get("previous_sha256", ""),
                "current_sha256": row.get("current_sha256", ""),
                "sha256_delta": row.get("sha256_delta", ""),
                "previous_row_or_object_count": row.get("previous_row_or_object_count", ""),
                "current_row_or_object_count": row.get("current_row_or_object_count", ""),
                "freshness_delta_status": row.get("freshness_delta_status", ""),
                "notes": row.get("notes", ""),
                "explorer_status": "QUERYABLE" if row.get("freshness_delta_status") == "PASS" else "REVIEW",
                "no_db_open_write": "YES",
                "no_adapter_calls": "YES",
                "no_new_scoring": "YES",
            }
        )
    return tuple(rows)


def filter_commands(
    rows: Sequence[Mapping[str, str]],
    *,
    status: str | None = None,
    delta: str | None = None,
) -> tuple[dict[str, str], ...]:
    status_filter = status.upper() if status else None
    delta_filter = delta.upper() if delta else None
    selected = []
    for row in rows:
        if status_filter and row.get("delta_status", "").upper() != status_filter:
            continue
        if delta_filter and row.get("status_delta", "").upper() != delta_filter:
            continue
        selected.append(dict(row))
    return tuple(selected)


def filter_freshness(
    rows: Sequence[Mapping[str, str]],
    *,
    status: str | None = None,
    sha_delta: str | None = None,
) -> tuple[dict[str, str], ...]:
    status_filter = status.upper() if status else None
    delta_filter = sha_delta.upper() if sha_delta else None
    selected = []
    for row in rows:
        if status_filter and row.get("freshness_delta_status", "").upper() != status_filter:
            continue
        if delta_filter and row.get("sha256_delta", "").upper() != delta_filter:
            continue
        selected.append(dict(row))
    return tuple(selected)


def build_query_snapshots(
    catalog_rows: Sequence[Mapping[str, str]],
    snapshot_summary: Mapping[str, object],
    command_view_rows: Sequence[Mapping[str, str]],
    freshness_view_rows: Sequence[Mapping[str, str]],
    repo_root: Path | None = None,
) -> dict[str, object]:
    by_role = {row["artifact_role"]: dict(row) for row in catalog_rows}
    source_sha = {row["path"]: row["sha256"] for row in source_inventory(repo_root)}
    return {
        "task": TASK,
        "generated_at": GENERATED_AT,
        "scope": STATEMENTS,
        "source_sha256": source_sha,
        "counts": {
            "source_artifacts": len(catalog_rows),
            "command_rows": len(command_view_rows),
            "freshness_rows": len(freshness_view_rows),
            "pass_command_rows": len(filter_commands(command_view_rows, status="PASS")),
            "unchanged_freshness_rows": len(filter_freshness(freshness_view_rows, sha_delta="UNCHANGED")),
        },
        "query_examples": {
            "list_artifacts": tuple(dict(row) for row in catalog_rows),
            "show_artifact_index": by_role.get("index", {}),
            "summary": dict(snapshot_summary),
            "filter_commands_pass": filter_commands(command_view_rows, status="PASS"),
            "filter_freshness_unchanged": filter_freshness(freshness_view_rows, sha_delta="UNCHANGED"),
        },
        "statements": STATEMENTS,
        "scope_lines": DISCLAIMER_LINES,
    }


def build_index(
    catalog_rows: Sequence[Mapping[str, str]],
    snapshot_summary: Mapping[str, object],
    command_view_rows: Sequence[Mapping[str, str]],
    freshness_view_rows: Sequence[Mapping[str, str]],
    repo_root: Path | None = None,
) -> dict[str, object]:
    return {
        "task": TASK,
        "generated_at": GENERATED_AT,
        "source_baseline": SOURCE_BASELINE,
        "source_p378_artifact_paths": P378_SOURCE_ARTIFACTS,
        "source_p378_sha256": {row["path"]: row["sha256"] for row in source_inventory(repo_root)},
        "generated_p379_artifact_paths": {
            role: f"artifacts/{basename}" for role, basename in P379_ARTIFACT_BASENAMES.items()
        },
        "counts": {
            "catalog_rows": len(catalog_rows),
            "command_rows": len(command_view_rows),
            "freshness_rows": len(freshness_view_rows),
            "p377_command_count": snapshot_summary.get("p377_command_count"),
            "p377_artifact_count": snapshot_summary.get("p377_artifact_count"),
        },
        "routes": {
            "summary": "snapshot_summary",
            "catalog": "catalog_rows",
            "commands": "command_view_rows",
            "freshness": "freshness_view_rows",
            "query_snapshots": "query_snapshots",
            "html": "html_text",
        },
        "statements": STATEMENTS,
        "scope_lines": DISCLAIMER_LINES,
    }


def _html_table(columns: Sequence[str], rows: Iterable[Mapping[str, object]], limit: int | None = None) -> str:
    selected = list(rows)
    if limit is not None:
        selected = selected[:limit]
    head = "".join(f"<th>{html.escape(column)}</th>" for column in columns)
    body = []
    for row in selected:
        cells = "".join(f"<td>{html.escape(str(row.get(column, '')))}</td>" for column in columns)
        body.append(f"<tr>{cells}</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def build_html(
    index: Mapping[str, object],
    catalog_rows: Sequence[Mapping[str, str]],
    snapshot_summary: Mapping[str, object],
    command_view_rows: Sequence[Mapping[str, str]],
    freshness_view_rows: Sequence[Mapping[str, str]],
    query_snapshots: Mapping[str, object],
) -> str:
    disclaimer_items = "".join(f"<li>{html.escape(line)}</li>" for line in DISCLAIMER_LINES)
    css = textwrap.dedent(
        """
        body { margin: 0; font-family: Arial, sans-serif; color: #1f2933; background: #f7f8fa; }
        header { background: #21445a; color: #fff; padding: 24px 32px; }
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
          <title>P379 Big Lotto no-DB regression archive explorer</title>
          <style>{css}</style>
        </head>
        <body>
          <header>
            <h1>P379 Big Lotto no-DB regression archive explorer</h1>
            <p>P378 comparison status: <strong>{html.escape(str(snapshot_summary.get("p378_comparison_status", "")))}</strong></p>
          </header>
          <main>
            <section class="banner"><strong>Scope / disclaimer banner:</strong> {html.escape(SCOPE_STATEMENT)}</section>
            <h2>Explorer Index</h2>
            <section class="panel"><pre>{html.escape(_json_text(index))}</pre></section>
            <h2>Snapshot Summary Section</h2>
            <section class="panel"><pre>{html.escape(_json_text(snapshot_summary))}</pre></section>
            <h2>Archive Catalog Section</h2>
            {_html_table(CATALOG_COLUMNS, catalog_rows)}
            <h2>Command View Section</h2>
            {_html_table(COMMAND_VIEW_COLUMNS, command_view_rows)}
            <h2>Freshness View Section</h2>
            {_html_table(FRESHNESS_VIEW_COLUMNS, freshness_view_rows, limit=60)}
            <h2>Query Snapshot Section</h2>
            <section class="panel"><pre>{html.escape(_json_text(query_snapshots))}</pre></section>
            <h2>No-DB / No-Adapter / No-Scoring / No-Deploy Disclaimers</h2>
            <section class="panel"><ul>{disclaimer_items}</ul></section>
          </main>
        </body>
        </html>
        """
    ).lstrip()


def _artifact_contents_without_manifest(output: ExplorerOutput) -> dict[str, str]:
    return {
        "index": _json_text(output.index),
        "catalog": _csv_text(CATALOG_COLUMNS, output.catalog_rows),
        "snapshot_summary": _json_text(output.snapshot_summary),
        "command_view": _csv_text(COMMAND_VIEW_COLUMNS, output.command_view_rows),
        "freshness_view": _csv_text(FRESHNESS_VIEW_COLUMNS, output.freshness_view_rows),
        "query_snapshots": _json_text(output.query_snapshots),
        "html": output.html_text,
    }


def _artifact_contents(output: ExplorerOutput) -> dict[str, str]:
    contents = _artifact_contents_without_manifest(output)
    contents["manifest"] = _csv_text(MANIFEST_COLUMNS, output.manifest_rows)
    return contents


def _output_counts(role: str, text: str) -> tuple[str, str]:
    if role in {"catalog", "command_view", "freshness_view", "manifest"}:
        return str(len(tuple(csv.DictReader(text.splitlines())))), ""
    if role in {"index", "snapshot_summary", "query_snapshots"}:
        return "", f"json_keys={len(json.loads(text))}"
    if role == "html":
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
                "output_object_count": source["row_or_object_count"],
                "no_db_open_write": "YES",
                "no_adapter_calls": "YES",
                "no_new_scoring": "YES",
                "no_deploy": "YES",
                "details": "P379 source evidence read from committed P378 artifacts only.",
                "scope_statement": SCOPE_STATEMENT,
            }
        )
    for role, basename in P379_ARTIFACT_BASENAMES.items():
        text = output_texts_without_manifest.get(role, "")
        row_count, object_count = _output_counts(role, text)
        digest = sha256_bytes(text.encode("utf-8")) if text else ""
        if role == "manifest":
            row_count = str(len(P378_SOURCE_ARTIFACTS) + len(P379_ARTIFACT_BASENAMES) + 4)
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
                "details": "P379 generated no-DB regression archive explorer artifact.",
                "scope_statement": SCOPE_STATEMENT,
            }
        )
    for role, details in (
        ("no_db_open_write", "No DB open/write was performed by P379."),
        ("no_adapter_calls", "No adapter calls were performed by P379."),
        ("no_new_scoring", "No new scoring, scoring cohort, shape-only scoring, blocked-target scoring, or blended leaderboard was created by P379."),
        ("no_deploy", "No production registry import, deploy, or external publication was performed by P379."),
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


def validate_explorer(
    output: ExplorerOutput | None = None,
    repo_root: Path | None = None,
    include_determinism: bool = True,
) -> tuple[dict[str, str], ...]:
    current = output if output is not None else run_explorer(repo_root, include_validation=False)
    text = "\n".join(_artifact_contents(current).values()).lower()
    found = [phrase for phrase in FORBIDDEN_AUTHORIZATION_PHRASES if phrase in text]
    rows = [
        _check("required_p378_artifacts_exist", len(verify_required_artifacts(repo_root)) == len(P378_SOURCE_ARTIFACTS), len(P378_SOURCE_ARTIFACTS), len(P378_SOURCE_ARTIFACTS), "Required P378 module and artifacts are present."),
        _check("catalog_csv_schema", bool(current.catalog_rows) and tuple(current.catalog_rows[0]) == CATALOG_COLUMNS, CATALOG_COLUMNS, tuple(current.catalog_rows[0]) if current.catalog_rows else (), "Catalog rows use required columns."),
        _check("snapshot_summary_json_schema", set(current.snapshot_summary) >= {"p378_snapshot_id", "p378_comparison_status", "p377_overall_status", "p377_command_count", "p377_artifact_count"}, "required summary keys", sorted(current.snapshot_summary), "Snapshot summary includes required P378/P377 fields."),
        _check("command_view_csv_schema", bool(current.command_view_rows) and tuple(current.command_view_rows[0]) == COMMAND_VIEW_COLUMNS, COMMAND_VIEW_COLUMNS, tuple(current.command_view_rows[0]) if current.command_view_rows else (), "Command view rows use required columns."),
        _check("freshness_view_csv_schema", bool(current.freshness_view_rows) and tuple(current.freshness_view_rows[0]) == FRESHNESS_VIEW_COLUMNS, FRESHNESS_VIEW_COLUMNS, tuple(current.freshness_view_rows[0]) if current.freshness_view_rows else (), "Freshness view rows use required columns."),
        _check("query_snapshots_json_schema", set(current.query_snapshots) >= {"counts", "query_examples", "source_sha256", "scope"}, "required query snapshot keys", sorted(current.query_snapshots), "Query snapshots include examples and counts."),
        _check("html_explorer_self_contained", current.html_text.startswith("<!doctype html>") and "<script" not in current.html_text.lower() and all(section in current.html_text for section in ("Scope / disclaimer banner", "Snapshot Summary Section", "Archive Catalog Section", "Command View Section", "Freshness View Section", "Query Snapshot Section")), "self-contained HTML sections", "present", "HTML explorer includes required sections and no script tag."),
        _check("manifest_csv_schema", bool(current.manifest_rows) and tuple(current.manifest_rows[0]) == MANIFEST_COLUMNS, MANIFEST_COLUMNS, tuple(current.manifest_rows[0]) if current.manifest_rows else (), "Manifest rows use required columns."),
        _check("p378_comparison_pass", current.snapshot_summary.get("p378_comparison_status") == "PASS", "PASS", current.snapshot_summary.get("p378_comparison_status"), "P378 source comparison remains PASS."),
        _check("p377_results_pass", current.snapshot_summary.get("p377_overall_status") == "PASS", "PASS", current.snapshot_summary.get("p377_overall_status"), "P377 source regression result remains PASS through P378 archive."),
        _check("generated_outputs_include_safety_constraints", all(line.lower() in text for line in DISCLAIMER_LINES), "all scope lines", "present", "Outputs include no-DB/no-adapter/no-scoring/no-deploy constraints."),
        _check("generated_outputs_do_not_authorize_forbidden_actions", not found, "absent", ";".join(found) if found else "absent", "P379 outputs do not authorize restricted actions."),
    ]
    if include_determinism:
        first = run_explorer(repo_root, include_validation=False)
        second = run_explorer(repo_root, include_validation=False)
        rows.append(
            _check(
                "deterministic_double_run_equality",
                _artifact_contents(first) == _artifact_contents(second),
                "equal",
                "equal" if _artifact_contents(first) == _artifact_contents(second) else "different",
                "P379 generated rows and artifacts are deterministic across two runs.",
            )
        )
    return tuple(rows)


def run_explorer(repo_root: Path | None = None, include_validation: bool = True) -> ExplorerOutput:
    verify_required_artifacts(repo_root)
    catalog_rows = build_catalog(repo_root)
    snapshot_summary = build_snapshot_summary(repo_root)
    command_view_rows = build_command_view(repo_root)
    freshness_view_rows = build_freshness_view(repo_root)
    query_snapshots = build_query_snapshots(
        catalog_rows,
        snapshot_summary,
        command_view_rows,
        freshness_view_rows,
        repo_root,
    )
    index = build_index(catalog_rows, snapshot_summary, command_view_rows, freshness_view_rows, repo_root)
    html_text = build_html(index, catalog_rows, snapshot_summary, command_view_rows, freshness_view_rows, query_snapshots)
    temp = ExplorerOutput(
        index=index,
        catalog_rows=catalog_rows,
        snapshot_summary=snapshot_summary,
        command_view_rows=command_view_rows,
        freshness_view_rows=freshness_view_rows,
        query_snapshots=query_snapshots,
        html_text=html_text,
        manifest_rows=(),
        validation_rows=(),
    )
    manifest_rows = build_manifest_rows(_artifact_contents_without_manifest(temp), repo_root)
    output = ExplorerOutput(
        index=index,
        catalog_rows=catalog_rows,
        snapshot_summary=snapshot_summary,
        command_view_rows=command_view_rows,
        freshness_view_rows=freshness_view_rows,
        query_snapshots=query_snapshots,
        html_text=html_text,
        manifest_rows=manifest_rows,
        validation_rows=(),
    )
    validation_rows = validate_explorer(output, repo_root, include_determinism=False) if include_validation else ()
    return ExplorerOutput(
        index=index,
        catalog_rows=catalog_rows,
        snapshot_summary=snapshot_summary,
        command_view_rows=command_view_rows,
        freshness_view_rows=freshness_view_rows,
        query_snapshots=query_snapshots,
        html_text=html_text,
        manifest_rows=manifest_rows,
        validation_rows=validation_rows,
    )


def write_artifacts(output: ExplorerOutput, artifacts_dir: Path | None = None) -> dict[str, Path]:
    out_dir = artifacts_dir if artifacts_dir is not None else REPO_ROOT / "artifacts"
    out_dir.mkdir(parents=True, exist_ok=True)
    contents = _artifact_contents(output)
    paths: dict[str, Path] = {}
    for role, basename in P379_ARTIFACT_BASENAMES.items():
        path = out_dir / basename
        path.write_text(contents[role], encoding="utf-8")
        paths[role] = path
    return paths


def _print_csv(columns: Sequence[str], rows: Sequence[Mapping[str, str]]) -> None:
    print(_csv_text(columns, rows), end="")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="P379 Big Lotto no-DB regression archive explorer")
    parser.add_argument("--artifacts-dir", type=Path, default=None)
    parser.add_argument("--generate", action="store_true", help="Write all P379 explorer artifacts.")
    parser.add_argument("--index", action="store_true", help="Print explorer index JSON.")
    parser.add_argument("--summary", action="store_true", help="Print snapshot summary JSON.")
    parser.add_argument("--catalog", action="store_true", help="Print artifact catalog CSV.")
    parser.add_argument("--commands", action="store_true", help="Print command view CSV.")
    parser.add_argument("--command-status", default=None, help="Filter --commands by delta_status.")
    parser.add_argument("--command-delta", default=None, help="Filter --commands by status_delta.")
    parser.add_argument("--freshness", action="store_true", help="Print freshness view CSV.")
    parser.add_argument("--freshness-status", default=None, help="Filter --freshness by freshness_delta_status.")
    parser.add_argument("--sha-delta", default=None, help="Filter --freshness by sha256_delta.")
    parser.add_argument("--snapshots", action="store_true", help="Print query snapshots JSON.")
    parser.add_argument("--html", action="store_true", help="Print explorer HTML.")
    parser.add_argument("--validate", action="store_true", help="Print validation CSV.")
    args = parser.parse_args(argv)

    output = run_explorer(include_validation=True)
    if args.index:
        print(_json_text(output.index), end="")
    elif args.summary:
        print(_json_text(output.snapshot_summary), end="")
    elif args.catalog:
        _print_csv(CATALOG_COLUMNS, output.catalog_rows)
    elif args.commands:
        _print_csv(
            COMMAND_VIEW_COLUMNS,
            filter_commands(output.command_view_rows, status=args.command_status, delta=args.command_delta),
        )
    elif args.freshness:
        _print_csv(
            FRESHNESS_VIEW_COLUMNS,
            filter_freshness(output.freshness_view_rows, status=args.freshness_status, sha_delta=args.sha_delta),
        )
    elif args.snapshots:
        print(_json_text(output.query_snapshots), end="")
    elif args.html:
        print(output.html_text, end="")
    elif args.validate:
        _print_csv(VALIDATION_COLUMNS, validate_explorer(output))
    else:
        paths = write_artifacts(output, args.artifacts_dir)
        first = run_explorer(include_validation=False)
        second = run_explorer(include_validation=False)
        determinism = "PASS" if _artifact_contents(first) == _artifact_contents(second) else "FAIL"
        print(f"P379 regression archive explorer artifacts written: {len(paths)}")
        print(f"determinism double-run {determinism}")
        print(f"snapshot summary: P378={output.snapshot_summary['p378_comparison_status']} P377={output.snapshot_summary['p377_overall_status']}")
        print("No DB was opened or written; no adapters were called; no new scoring or deploy was performed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
