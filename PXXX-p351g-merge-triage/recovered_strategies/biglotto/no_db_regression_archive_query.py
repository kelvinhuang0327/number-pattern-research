"""P380 Big Lotto no-DB regression archive query API / recipe runner.

This module builds deterministic query recipes over committed P377/P378/P379
regression archive evidence. It reads only source files and generated
artifacts, writes only P380-prefixed artifacts, and does not open or write a
DB, call adapters, create new scoring cohorts, import production registries,
deploy, provide betting advice, or make future-performance claims.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import textwrap
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Iterable, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
TASK = "P380_biglotto_regression_archive_query"
GENERATED_AT = "DETERMINISTIC_PLACEHOLDER"
P379_BASELINE_COMMIT = "e09c8cb6de9d95ff1e381104425bbbcc5c79b781"

P379_EXTERNAL_WORKTREE = Path("/Users/kelvin/Kelvin-WorkSpace/LotteryNew-p379")
PROTECTED_HISTORICAL_WORKTREES = (
    Path("/Users/kelvin/Kelvin-WorkSpace/LotteryNew.worktrees/P360-fable5-biglotto-success-direction-readonly"),
    Path("/Users/kelvin/Kelvin-WorkSpace/LotteryNew.worktrees/P371-biglotto-command-center"),
    Path("/Users/kelvin/Kelvin-WorkSpace/LotteryNew.worktrees/P373-biglotto-command-center-operator-console"),
)

SOURCE_BASELINE = {
    "required_origin_main_merge_commit": P379_BASELINE_COMMIT,
    "source_tasks": (
        "P377_biglotto_command_center_regression_runner",
        "P378_biglotto_regression_run_archive",
        "P379_biglotto_regression_archive_explorer",
    ),
    "query_mode": "read_only_no_db_regression_archive_recipe_runner",
}

P377_SOURCE_ARTIFACTS = {
    "p377_module": "recovered_strategies/biglotto/no_db_command_center_regression_runner.py",
    "p377_results": "artifacts/P377_biglotto_command_center_regression_results.json",
    "p377_commands": "artifacts/P377_biglotto_command_center_regression_commands.csv",
    "p377_failures": "artifacts/P377_biglotto_command_center_regression_failures.csv",
    "p377_freshness": "artifacts/P377_biglotto_command_center_regression_artifact_freshness.csv",
    "p377_report": "artifacts/P377_biglotto_command_center_regression_report.html",
    "p377_manifest": "artifacts/P377_biglotto_command_center_regression_manifest.csv",
}

P378_SOURCE_ARTIFACTS = {
    "p378_module": "recovered_strategies/biglotto/no_db_regression_run_archive.py",
    "p378_index": "artifacts/P378_biglotto_regression_run_archive_index.json",
    "p378_snapshot": "artifacts/P378_biglotto_regression_run_archive_snapshot.json",
    "p378_comparison": "artifacts/P378_biglotto_regression_run_archive_comparison.json",
    "p378_command_delta": "artifacts/P378_biglotto_regression_run_archive_command_delta.csv",
    "p378_freshness_delta": "artifacts/P378_biglotto_regression_run_archive_freshness_delta.csv",
    "p378_report": "artifacts/P378_biglotto_regression_run_archive_report.html",
    "p378_manifest": "artifacts/P378_biglotto_regression_run_archive_manifest.csv",
}

P379_SOURCE_ARTIFACTS = {
    "p379_module": "recovered_strategies/biglotto/no_db_regression_archive_explorer.py",
    "p379_index": "artifacts/P379_biglotto_regression_archive_explorer_index.json",
    "p379_catalog": "artifacts/P379_biglotto_regression_archive_explorer_catalog.csv",
    "p379_snapshot_summary": "artifacts/P379_biglotto_regression_archive_explorer_snapshot_summary.json",
    "p379_command_view": "artifacts/P379_biglotto_regression_archive_explorer_command_view.csv",
    "p379_freshness_view": "artifacts/P379_biglotto_regression_archive_explorer_freshness_view.csv",
    "p379_query_snapshots": "artifacts/P379_biglotto_regression_archive_explorer_query_snapshots.json",
    "p379_report": "artifacts/P379_biglotto_regression_archive_explorer_report.html",
    "p379_manifest": "artifacts/P379_biglotto_regression_archive_explorer_manifest.csv",
}

SOURCE_ARTIFACTS = {
    **P377_SOURCE_ARTIFACTS,
    **P378_SOURCE_ARTIFACTS,
    **P379_SOURCE_ARTIFACTS,
}

P380_ARTIFACT_BASENAMES = {
    "index": "P380_biglotto_regression_archive_query_index.json",
    "recipes": "P380_biglotto_regression_archive_query_recipes.json",
    "command_results": "P380_biglotto_regression_archive_query_command_results.csv",
    "artifact_results": "P380_biglotto_regression_archive_query_artifact_results.csv",
    "delta_results": "P380_biglotto_regression_archive_query_delta_results.csv",
    "transcripts": "P380_biglotto_regression_archive_query_transcripts.json",
    "guide": "P380_biglotto_regression_archive_query_guide.md",
    "manifest": "P380_biglotto_regression_archive_query_manifest.csv",
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
    "No production registry import or production release approval.",
    "Not production release approval.",
    "P380 reads only merged P377/P378/P379 regression archive artifacts and writes only P380-prefixed query artifacts.",
)
SCOPE_STATEMENT = " ".join(DISCLAIMER_LINES)
NO_DB_NO_ADAPTER_NO_SCORING_NO_DEPLOY_STATEMENT = (
    "No DB was opened or written; no adapters were called; no new scoring, scoring cohort, "
    "shape-only scoring, blocked-target scoring, or blended leaderboard was created; no "
    "production registry import, deploy, or external publication was performed."
)

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

COMMAND_RESULT_COLUMNS = (
    "query_id",
    "command_id",
    "stage",
    "status",
    "command",
    "normalized_summary",
    "related_delta",
    "notes",
)

ARTIFACT_RESULT_COLUMNS = (
    "query_id",
    "artifact_path",
    "source_stage",
    "exists",
    "sha256",
    "row_or_object_count",
    "freshness_status",
    "related_delta",
    "notes",
)

DELTA_RESULT_COLUMNS = (
    "query_id",
    "delta_id",
    "delta_type",
    "source_artifact",
    "status",
    "severity",
    "previous_value",
    "current_value",
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

RECIPE_IDS = (
    "all_commands",
    "non_pass_commands",
    "all_artifacts",
    "stale_or_missing_artifacts",
    "all_deltas",
    "warn_or_fail_deltas",
    "handoff_digest",
)


@dataclass(frozen=True)
class QueryOutput:
    index: dict[str, object]
    recipes: dict[str, object]
    command_rows: tuple[dict[str, str], ...]
    artifact_rows: tuple[dict[str, str], ...]
    delta_rows: tuple[dict[str, str], ...]
    transcripts: dict[str, object]
    guide_markdown: str
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
    paths = tuple(_artifact_path(relpath, repo_root) for relpath in SOURCE_ARTIFACTS.values())
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise RuntimeError(f"required P377/P378/P379 regression archive evidence missing: {missing}")
    return paths


def source_inventory(repo_root: Path | None = None) -> tuple[dict[str, str], ...]:
    verify_required_evidence(repo_root)
    rows: list[dict[str, str]] = []
    for role, relpath in SOURCE_ARTIFACTS.items():
        path = _artifact_path(relpath, repo_root)
        rows.append(
            {
                "artifact_role": role,
                "path": relpath,
                "source_stage": role.split("_", 1)[0].upper(),
                "format": path.suffix.lower().lstrip(".") or "file",
                "sha256": sha256_file(path),
                "row_or_object_count": _count_artifact(path),
            }
        )
    return tuple(rows)


def inspect_path_warnings() -> dict[str, object]:
    protected = {
        str(path): "PRESENT" if path.exists() else "ABSENT"
        for path in PROTECTED_HISTORICAL_WORKTREES
    }
    protected_warning = (
        "P380_WARN_PROTECTED_WORKTREES_ABSENT"
        if any(status == "ABSENT" for status in protected.values())
        else "P380_PROTECTED_WORKTREES_PRESENT"
    )
    return {
        "p379_previous_worktree": {
            "path": str(P379_EXTERNAL_WORKTREE),
            "status": "PRESENT" if P379_EXTERNAL_WORKTREE.exists() else "ABSENT",
            "policy": "read-only presence check only; do not use or clean",
        },
        "protected_historical_worktrees": protected,
        "protected_historical_warning": protected_warning,
    }


def _command_delta_lookup(repo_root: Path | None = None) -> dict[str, dict[str, str]]:
    return {
        row.get("command_id", ""): row
        for row in _read_csv(P378_SOURCE_ARTIFACTS["p378_command_delta"], repo_root)
    }


def build_command_rows(repo_root: Path | None = None) -> tuple[dict[str, str], ...]:
    delta_by_command = _command_delta_lookup(repo_root)
    rows: list[dict[str, str]] = []
    source_rows = _read_csv(P377_SOURCE_ARTIFACTS["p377_commands"], repo_root)
    for source in source_rows:
        command_id = source.get("command_id", "")
        delta = delta_by_command.get(command_id, {})
        status = source.get("status", "")
        rows.append(
            {
                "query_id": "all_commands",
                "command_id": command_id,
                "stage": source.get("stage", ""),
                "status": status,
                "command": source.get("command", ""),
                "normalized_summary": source.get("normalized_output_summary", ""),
                "related_delta": delta.get("delta_status", ""),
                "notes": delta.get("notes", "P377 command evidence read-only; command was not executed by P380."),
            }
        )
    non_pass_rows = [row for row in rows if row["status"].upper() != "PASS" or row["related_delta"].upper() != "PASS"]
    if non_pass_rows:
        rows.extend({**row, "query_id": "non_pass_commands"} for row in non_pass_rows)
    else:
        rows.append(
            {
                "query_id": "non_pass_commands",
                "command_id": "none",
                "stage": "none",
                "status": "NONE",
                "command": "",
                "normalized_summary": "No non-PASS command rows were present in committed P377/P378/P379 archive evidence.",
                "related_delta": "none",
                "notes": "Sentinel row; P380 did not execute commands.",
            }
        )
    return tuple(rows)


def _freshness_delta_lookup(repo_root: Path | None = None) -> dict[str, dict[str, str]]:
    return {
        row.get("artifact_path", ""): row
        for row in _read_csv(P378_SOURCE_ARTIFACTS["p378_freshness_delta"], repo_root)
    }


def build_artifact_rows(repo_root: Path | None = None) -> tuple[dict[str, str], ...]:
    freshness_delta = _freshness_delta_lookup(repo_root)
    rows: list[dict[str, str]] = []
    source_rows = source_inventory(repo_root)
    p377_freshness = {
        row.get("artifact_path", ""): row
        for row in _read_csv(P377_SOURCE_ARTIFACTS["p377_freshness"], repo_root)
    }
    for source in source_rows:
        relpath = source["path"]
        source_stage = source["source_stage"]
        p377_row = p377_freshness.get(relpath, {})
        delta = freshness_delta.get(relpath, {})
        freshness_status = (
            delta.get("freshness_delta_status")
            or p377_row.get("freshness_status")
            or "ARCHIVED_SOURCE"
        )
        related_delta = delta.get("sha256_delta", "SOURCE_INVENTORY")
        rows.append(
            {
                "query_id": "all_artifacts",
                "artifact_path": relpath,
                "source_stage": source_stage,
                "exists": "YES",
                "sha256": source["sha256"],
                "row_or_object_count": source["row_or_object_count"],
                "freshness_status": freshness_status,
                "related_delta": related_delta,
                "notes": "Committed P377/P378/P379 evidence artifact read-only; no DB open/write.",
            }
        )
    stale_rows = [
        row for row in rows
        if row["exists"] != "YES"
        or row["freshness_status"].upper() not in {"PASS", "FRESH", "ARCHIVED_SOURCE"}
        or row["related_delta"].upper() in {"CHANGED", "MISSING", "STALE"}
    ]
    if stale_rows:
        rows.extend({**row, "query_id": "stale_or_missing_artifacts"} for row in stale_rows)
    else:
        rows.append(
            {
                "query_id": "stale_or_missing_artifacts",
                "artifact_path": "none",
                "source_stage": "none",
                "exists": "YES",
                "sha256": "",
                "row_or_object_count": "0",
                "freshness_status": "NONE",
                "related_delta": "none",
                "notes": "Sentinel row; no stale or missing committed source artifacts were observed.",
            }
        )
    return tuple(rows)


def build_delta_rows(repo_root: Path | None = None) -> tuple[dict[str, str], ...]:
    rows: list[dict[str, str]] = []
    for row in _read_csv(P378_SOURCE_ARTIFACTS["p378_command_delta"], repo_root):
        status = row.get("delta_status", "")
        severity = "INFO" if status == "PASS" else "WARN"
        rows.append(
            {
                "query_id": "all_deltas",
                "delta_id": row.get("command_id", ""),
                "delta_type": "command_status",
                "source_artifact": P378_SOURCE_ARTIFACTS["p378_command_delta"],
                "status": status,
                "severity": severity,
                "previous_value": row.get("previous_status", ""),
                "current_value": row.get("current_status", ""),
                "notes": row.get("notes", ""),
            }
        )
    for row in _read_csv(P378_SOURCE_ARTIFACTS["p378_freshness_delta"], repo_root):
        status = row.get("freshness_delta_status", "")
        severity = "INFO" if status == "PASS" else "WARN"
        rows.append(
            {
                "query_id": "all_deltas",
                "delta_id": row.get("artifact_path", ""),
                "delta_type": "artifact_freshness",
                "source_artifact": P378_SOURCE_ARTIFACTS["p378_freshness_delta"],
                "status": status,
                "severity": severity,
                "previous_value": row.get("previous_sha256", ""),
                "current_value": row.get("current_sha256", ""),
                "notes": row.get("notes", ""),
            }
        )
    warn_or_fail = [
        row for row in rows
        if row["severity"] in {"WARN", "FAIL"} or row["status"].upper() not in {"PASS", "NONE"}
    ]
    if warn_or_fail:
        rows.extend({**row, "query_id": "warn_or_fail_deltas"} for row in warn_or_fail)
    else:
        rows.append(
            {
                "query_id": "warn_or_fail_deltas",
                "delta_id": "none",
                "delta_type": "none",
                "source_artifact": "none",
                "status": "NONE",
                "severity": "INFO",
                "previous_value": "",
                "current_value": "",
                "notes": "Sentinel row; no WARN/FAIL deltas were present in committed archive evidence.",
            }
        )
    return tuple(rows)


def _recipe(
    recipe_id: str,
    description: str,
    source_artifacts: Sequence[str],
    output_artifact: str,
) -> dict[str, object]:
    return {
        "recipe_id": recipe_id,
        "description": description,
        "source_artifacts": tuple(source_artifacts),
        "output_artifact": output_artifact,
        "safety_notes": (
            "Historical descriptive evidence only.",
            "No DB open/write.",
            "No adapter calls.",
            "No new scoring.",
            "No deploy.",
            "No betting advice or future prediction guarantee.",
        ),
    }


def build_recipes() -> dict[str, object]:
    recipes = (
        _recipe(
            "all_commands",
            "List every archived P377 command row with P378/P379 status context.",
            (P377_SOURCE_ARTIFACTS["p377_commands"], P378_SOURCE_ARTIFACTS["p378_command_delta"], P379_SOURCE_ARTIFACTS["p379_command_view"]),
            f"artifacts/{P380_ARTIFACT_BASENAMES['command_results']}",
        ),
        _recipe(
            "non_pass_commands",
            "List command rows whose command or related delta status is not PASS.",
            (P377_SOURCE_ARTIFACTS["p377_commands"], P378_SOURCE_ARTIFACTS["p378_command_delta"], P379_SOURCE_ARTIFACTS["p379_command_view"]),
            f"artifacts/{P380_ARTIFACT_BASENAMES['command_results']}",
        ),
        _recipe(
            "all_artifacts",
            "List all committed P377/P378/P379 source artifacts indexed by P380.",
            tuple(SOURCE_ARTIFACTS.values()),
            f"artifacts/{P380_ARTIFACT_BASENAMES['artifact_results']}",
        ),
        _recipe(
            "stale_or_missing_artifacts",
            "List source artifacts marked stale, missing, changed, or non-PASS where present.",
            (P377_SOURCE_ARTIFACTS["p377_freshness"], P378_SOURCE_ARTIFACTS["p378_freshness_delta"], P379_SOURCE_ARTIFACTS["p379_freshness_view"]),
            f"artifacts/{P380_ARTIFACT_BASENAMES['artifact_results']}",
        ),
        _recipe(
            "all_deltas",
            "List every archived command and artifact freshness delta from P378 evidence.",
            (P378_SOURCE_ARTIFACTS["p378_command_delta"], P378_SOURCE_ARTIFACTS["p378_freshness_delta"]),
            f"artifacts/{P380_ARTIFACT_BASENAMES['delta_results']}",
        ),
        _recipe(
            "warn_or_fail_deltas",
            "List archived delta rows that require WARN/FAIL review.",
            (P378_SOURCE_ARTIFACTS["p378_command_delta"], P378_SOURCE_ARTIFACTS["p378_freshness_delta"]),
            f"artifacts/{P380_ARTIFACT_BASENAMES['delta_results']}",
        ),
        _recipe(
            "handoff_digest",
            "Return compact P377/P378/P379/P380 counts and safety statements for future Workers.",
            tuple(SOURCE_ARTIFACTS.values()),
            f"artifacts/{P380_ARTIFACT_BASENAMES['transcripts']}",
        ),
    )
    return {
        "task": TASK,
        "generated_at": GENERATED_AT,
        "recipes": recipes,
        "recipe_ids": RECIPE_IDS,
        "statements": STATEMENTS,
        "scope_lines": DISCLAIMER_LINES,
    }


def _filter_by_query(rows: Sequence[Mapping[str, str]], query_id: str) -> tuple[dict[str, str], ...]:
    return tuple(dict(row) for row in rows if row.get("query_id") == query_id)


def _handoff_digest(
    command_rows: Sequence[Mapping[str, str]],
    artifact_rows: Sequence[Mapping[str, str]],
    delta_rows: Sequence[Mapping[str, str]],
    path_warnings: Mapping[str, object],
) -> dict[str, object]:
    return {
        "query_id": "handoff_digest",
        "task": TASK,
        "generated_at": GENERATED_AT,
        "source_baseline": SOURCE_BASELINE,
        "counts": {
            "all_commands": len(_filter_by_query(command_rows, "all_commands")),
            "non_pass_commands": len(_filter_by_query(command_rows, "non_pass_commands")),
            "all_artifacts": len(_filter_by_query(artifact_rows, "all_artifacts")),
            "stale_or_missing_artifacts": len(_filter_by_query(artifact_rows, "stale_or_missing_artifacts")),
            "all_deltas": len(_filter_by_query(delta_rows, "all_deltas")),
            "warn_or_fail_deltas": len(_filter_by_query(delta_rows, "warn_or_fail_deltas")),
        },
        "path_warnings": path_warnings,
        "statements": STATEMENTS,
        "no_db_no_adapter_no_scoring_no_deploy_statement": NO_DB_NO_ADAPTER_NO_SCORING_NO_DEPLOY_STATEMENT,
        "scope_lines": DISCLAIMER_LINES,
    }


def build_index(
    recipes: Mapping[str, object],
    command_rows: Sequence[Mapping[str, str]],
    artifact_rows: Sequence[Mapping[str, str]],
    delta_rows: Sequence[Mapping[str, str]],
    path_warnings: Mapping[str, object],
    repo_root: Path | None = None,
) -> dict[str, object]:
    inventory = source_inventory(repo_root)
    return {
        "task": TASK,
        "generated_at": GENERATED_AT,
        "source_baseline": SOURCE_BASELINE,
        "source_p377_artifact_paths": P377_SOURCE_ARTIFACTS,
        "source_p378_artifact_paths": P378_SOURCE_ARTIFACTS,
        "source_p379_artifact_paths": P379_SOURCE_ARTIFACTS,
        "source_sha256": {row["path"]: row["sha256"] for row in inventory},
        "available_recipes": recipes["recipe_ids"],
        "generated_p380_artifact_paths": {
            role: f"artifacts/{basename}" for role, basename in P380_ARTIFACT_BASENAMES.items()
        },
        "path_warnings": path_warnings,
        "counts": {
            "source_artifacts": len(inventory),
            "all_commands": len(_filter_by_query(command_rows, "all_commands")),
            "all_artifacts": len(_filter_by_query(artifact_rows, "all_artifacts")),
            "all_deltas": len(_filter_by_query(delta_rows, "all_deltas")),
            "recipes": len(RECIPE_IDS),
        },
        "statements": STATEMENTS,
        "no_db_no_adapter_no_scoring_no_deploy_statement": NO_DB_NO_ADAPTER_NO_SCORING_NO_DEPLOY_STATEMENT,
        "scope_lines": DISCLAIMER_LINES,
    }


def _show_command_payload(command_rows: Sequence[Mapping[str, str]], command_id: str) -> dict[str, object]:
    for row in command_rows:
        if row.get("query_id") == "all_commands" and row.get("command_id") == command_id:
            return {"found": True, "command": dict(row), "scope_lines": DISCLAIMER_LINES}
    return {"found": False, "command_id": command_id, "scope_lines": DISCLAIMER_LINES}


def _show_artifact_payload(artifact_rows: Sequence[Mapping[str, str]], artifact_id_or_path: str) -> dict[str, object]:
    query = artifact_id_or_path
    for row in artifact_rows:
        if row.get("query_id") != "all_artifacts":
            continue
        path = row.get("artifact_path", "")
        role = next((key for key, value in SOURCE_ARTIFACTS.items() if value == path), "")
        if query in {path, Path(path).name, role}:
            return {"found": True, "artifact": dict(row), "artifact_role": role, "scope_lines": DISCLAIMER_LINES}
    return {"found": False, "artifact_id_or_path": artifact_id_or_path, "scope_lines": DISCLAIMER_LINES}


def build_transcripts(
    command_rows: Sequence[Mapping[str, str]],
    artifact_rows: Sequence[Mapping[str, str]],
    delta_rows: Sequence[Mapping[str, str]],
    path_warnings: Mapping[str, object],
) -> dict[str, object]:
    first_command = next(row["command_id"] for row in command_rows if row["query_id"] == "all_commands")
    first_artifact = next(row["artifact_path"] for row in artifact_rows if row["query_id"] == "all_artifacts")
    return {
        "task": TASK,
        "generated_at": GENERATED_AT,
        "recipe_transcripts": {
            "all_commands": {
                "command": "python3 -m recovered_strategies.biglotto.no_db_regression_archive_query --query all_commands",
                "rows": len(_filter_by_query(command_rows, "all_commands")),
                "output_artifact": f"artifacts/{P380_ARTIFACT_BASENAMES['command_results']}",
            },
            "non_pass_commands": {
                "command": "python3 -m recovered_strategies.biglotto.no_db_regression_archive_query --query non_pass_commands",
                "rows": len(_filter_by_query(command_rows, "non_pass_commands")),
                "output_artifact": f"artifacts/{P380_ARTIFACT_BASENAMES['command_results']}",
            },
            "all_artifacts": {
                "command": "python3 -m recovered_strategies.biglotto.no_db_regression_archive_query --query all_artifacts",
                "rows": len(_filter_by_query(artifact_rows, "all_artifacts")),
                "output_artifact": f"artifacts/{P380_ARTIFACT_BASENAMES['artifact_results']}",
            },
            "stale_or_missing_artifacts": {
                "command": "python3 -m recovered_strategies.biglotto.no_db_regression_archive_query --query stale_or_missing_artifacts",
                "rows": len(_filter_by_query(artifact_rows, "stale_or_missing_artifacts")),
                "output_artifact": f"artifacts/{P380_ARTIFACT_BASENAMES['artifact_results']}",
            },
            "all_deltas": {
                "command": "python3 -m recovered_strategies.biglotto.no_db_regression_archive_query --query all_deltas",
                "rows": len(_filter_by_query(delta_rows, "all_deltas")),
                "output_artifact": f"artifacts/{P380_ARTIFACT_BASENAMES['delta_results']}",
            },
            "warn_or_fail_deltas": {
                "command": "python3 -m recovered_strategies.biglotto.no_db_regression_archive_query --query warn_or_fail_deltas",
                "rows": len(_filter_by_query(delta_rows, "warn_or_fail_deltas")),
                "output_artifact": f"artifacts/{P380_ARTIFACT_BASENAMES['delta_results']}",
            },
            "handoff_digest": {
                "command": "python3 -m recovered_strategies.biglotto.no_db_regression_archive_query --query handoff_digest",
                "payload": _handoff_digest(command_rows, artifact_rows, delta_rows, path_warnings),
            },
        },
        "show_command_example": {
            "command": f"python3 -m recovered_strategies.biglotto.no_db_regression_archive_query --show-command {first_command}",
            "payload": _show_command_payload(command_rows, first_command),
        },
        "show_artifact_example": {
            "command": f"python3 -m recovered_strategies.biglotto.no_db_regression_archive_query --show-artifact {first_artifact}",
            "payload": _show_artifact_payload(artifact_rows, first_artifact),
        },
        "path_warnings": path_warnings,
        "statements": STATEMENTS,
        "scope_lines": DISCLAIMER_LINES,
    }


def build_guide_markdown() -> str:
    return textwrap.dedent(
        f"""\
        # P380 Big Lotto no-DB regression archive query

        ## Scope

        Historical descriptive evidence only. No future prediction guarantee. No betting advice.
        No DB open/write. No adapter calls. No new scoring. No new scoring cohort.
        No production registry import. No deploy. No blended leaderboard. Not production release approval.

        ## List commands

        ```bash
        python3 -m recovered_strategies.biglotto.no_db_regression_archive_query --list-commands
        ```

        ## List artifacts

        ```bash
        python3 -m recovered_strategies.biglotto.no_db_regression_archive_query --list-artifacts
        ```

        ## List deltas

        ```bash
        python3 -m recovered_strategies.biglotto.no_db_regression_archive_query --list-deltas
        ```

        ## Query by recipe

        ```bash
        python3 -m recovered_strategies.biglotto.no_db_regression_archive_query --query all_commands
        python3 -m recovered_strategies.biglotto.no_db_regression_archive_query --query non_pass_commands
        python3 -m recovered_strategies.biglotto.no_db_regression_archive_query --query all_artifacts
        python3 -m recovered_strategies.biglotto.no_db_regression_archive_query --query stale_or_missing_artifacts
        python3 -m recovered_strategies.biglotto.no_db_regression_archive_query --query all_deltas
        python3 -m recovered_strategies.biglotto.no_db_regression_archive_query --query warn_or_fail_deltas
        python3 -m recovered_strategies.biglotto.no_db_regression_archive_query --query handoff_digest
        ```

        ## Inspect one command

        ```bash
        python3 -m recovered_strategies.biglotto.no_db_regression_archive_query --show-command P377-CMD-001
        ```

        ## Inspect one artifact

        ```bash
        python3 -m recovered_strategies.biglotto.no_db_regression_archive_query --show-artifact artifacts/P379_biglotto_regression_archive_explorer_index.json
        ```

        ## Safe caveats

        {NO_DB_NO_ADAPTER_NO_SCORING_NO_DEPLOY_STATEMENT}
        P380 does not execute P371-P379 CLI commands. It queries committed archive evidence only.
        P380 does not authorize DB writes, adapter execution, strategy status changes, deploys, force operations,
        betting advice, future prediction claims, or production release approval.

        ## Generated artifacts

        {chr(10).join(f"- artifacts/{basename}" for basename in P380_ARTIFACT_BASENAMES.values())}
        """
    )


def _artifact_contents_without_manifest(output: QueryOutput) -> dict[str, str]:
    return {
        "index": _json_text(output.index),
        "recipes": _json_text(output.recipes),
        "command_results": _csv_text(COMMAND_RESULT_COLUMNS, output.command_rows),
        "artifact_results": _csv_text(ARTIFACT_RESULT_COLUMNS, output.artifact_rows),
        "delta_results": _csv_text(DELTA_RESULT_COLUMNS, output.delta_rows),
        "transcripts": _json_text(output.transcripts),
        "guide": output.guide_markdown,
    }


def _artifact_contents(output: QueryOutput) -> dict[str, str]:
    contents = _artifact_contents_without_manifest(output)
    contents["manifest"] = _csv_text(MANIFEST_COLUMNS, output.manifest_rows)
    return contents


def _output_counts(role: str, text: str) -> tuple[str, str]:
    if role in {"command_results", "artifact_results", "delta_results", "manifest"}:
        return str(len(tuple(csv.DictReader(text.splitlines())))), ""
    if role in {"index", "recipes", "transcripts"}:
        return "", f"json_keys={len(json.loads(text))}"
    if role == "guide":
        return "", f"text_lines={len(text.splitlines())}"
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
                "details": "P380 source evidence read from committed P377/P378/P379 artifacts only.",
                "scope_statement": SCOPE_STATEMENT,
            }
        )
    for role, basename in P380_ARTIFACT_BASENAMES.items():
        text = output_texts_without_manifest.get(role, "")
        row_count, object_count = _output_counts(role, text)
        digest = sha256_bytes(text.encode("utf-8")) if text else ""
        if role == "manifest":
            row_count = str(len(SOURCE_ARTIFACTS) + len(P380_ARTIFACT_BASENAMES) + 4)
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
                "details": "P380 generated no-DB regression archive query artifact.",
                "scope_statement": SCOPE_STATEMENT,
            }
        )
    for role, details in (
        ("no_db_open_write", "No DB open/write was performed by P380."),
        ("no_adapter_calls", "No adapter calls were performed by P380."),
        ("no_new_scoring", "No new scoring, scoring cohort, shape-only scoring, blocked-target scoring, or blended leaderboard was created by P380."),
        ("no_deploy", "No production registry import, deploy, or external publication was performed by P380."),
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


def validate_query(
    output: QueryOutput | None = None,
    repo_root: Path | None = None,
    include_determinism: bool = True,
) -> tuple[dict[str, str], ...]:
    current = output if output is not None else run_query(repo_root, include_validation=False)
    text = "\n".join(_artifact_contents(current).values()).lower()
    found = [phrase for phrase in FORBIDDEN_AUTHORIZATION_PHRASES if phrase in text]
    rows = [
        _check("required_p377_p378_p379_evidence_exists", len(verify_required_evidence(repo_root)) == len(SOURCE_ARTIFACTS), len(SOURCE_ARTIFACTS), len(SOURCE_ARTIFACTS), "Required P377/P378/P379 modules and artifacts are present."),
        _check("index_json_schema", set(current.index) >= {"source_baseline", "source_sha256", "available_recipes", "generated_p380_artifact_paths", "path_warnings", "statements"}, "required index keys", sorted(current.index), "Index includes required P380 keys."),
        _check("recipes_json_schema", set(current.recipes) >= {"recipes", "recipe_ids", "statements"}, "required recipe keys", sorted(current.recipes), "Recipes JSON includes required keys."),
        _check("command_results_csv_schema", bool(current.command_rows) and tuple(current.command_rows[0]) == COMMAND_RESULT_COLUMNS, COMMAND_RESULT_COLUMNS, tuple(current.command_rows[0]) if current.command_rows else (), "Command result rows use required columns."),
        _check("artifact_results_csv_schema", bool(current.artifact_rows) and tuple(current.artifact_rows[0]) == ARTIFACT_RESULT_COLUMNS, ARTIFACT_RESULT_COLUMNS, tuple(current.artifact_rows[0]) if current.artifact_rows else (), "Artifact result rows use required columns."),
        _check("delta_results_csv_schema", bool(current.delta_rows) and tuple(current.delta_rows[0]) == DELTA_RESULT_COLUMNS, DELTA_RESULT_COLUMNS, tuple(current.delta_rows[0]) if current.delta_rows else (), "Delta result rows use required columns."),
        _check("transcripts_json_schema", set(current.transcripts) >= {"recipe_transcripts", "show_command_example", "show_artifact_example", "path_warnings"}, "required transcript keys", sorted(current.transcripts), "Transcripts include recipe and show examples."),
        _check("guide_contains_required_sections_and_disclaimers", all(section in current.guide_markdown for section in ("## List commands", "## List artifacts", "## List deltas", "## Query by recipe", "## Inspect one command", "## Inspect one artifact", "## Safe caveats")) and all(line in current.guide_markdown for line in ("No future prediction guarantee.", "No betting advice.", "No DB open/write.", "No adapter calls.", "No deploy.")), "sections and disclaimers present", "present", "Guide is copy-paste friendly and includes required caveats."),
        _check("manifest_csv_schema", bool(current.manifest_rows) and tuple(current.manifest_rows[0]) == MANIFEST_COLUMNS, MANIFEST_COLUMNS, tuple(current.manifest_rows[0]) if current.manifest_rows else (), "Manifest rows use required columns."),
        _check("generated_outputs_include_safety_constraints", all(line.lower() in text for line in DISCLAIMER_LINES), "all scope lines", "present", "Outputs include no-DB/no-adapter/no-scoring/no-deploy constraints."),
        _check("generated_outputs_do_not_authorize_forbidden_actions", not found, "absent", ";".join(found) if found else "absent", "P380 outputs do not authorize restricted actions."),
    ]
    if include_determinism:
        first = run_query(repo_root, include_validation=False)
        second = run_query(repo_root, include_validation=False)
        rows.append(
            _check(
                "deterministic_double_run_equality",
                _artifact_contents(first) == _artifact_contents(second),
                "equal",
                "equal" if _artifact_contents(first) == _artifact_contents(second) else "different",
                "P380 generated rows and artifacts are deterministic across two runs.",
            )
        )
    return tuple(rows)


def run_query(repo_root: Path | None = None, include_validation: bool = True) -> QueryOutput:
    verify_required_evidence(repo_root)
    path_warnings = inspect_path_warnings()
    recipes = build_recipes()
    command_rows = build_command_rows(repo_root)
    artifact_rows = build_artifact_rows(repo_root)
    delta_rows = build_delta_rows(repo_root)
    index = build_index(recipes, command_rows, artifact_rows, delta_rows, path_warnings, repo_root)
    transcripts = build_transcripts(command_rows, artifact_rows, delta_rows, path_warnings)
    guide_markdown = build_guide_markdown()
    temp = QueryOutput(
        index=index,
        recipes=recipes,
        command_rows=command_rows,
        artifact_rows=artifact_rows,
        delta_rows=delta_rows,
        transcripts=transcripts,
        guide_markdown=guide_markdown,
        manifest_rows=(),
        validation_rows=(),
    )
    manifest_rows = build_manifest_rows(_artifact_contents_without_manifest(temp), repo_root)
    output = QueryOutput(
        index=index,
        recipes=recipes,
        command_rows=command_rows,
        artifact_rows=artifact_rows,
        delta_rows=delta_rows,
        transcripts=transcripts,
        guide_markdown=guide_markdown,
        manifest_rows=manifest_rows,
        validation_rows=(),
    )
    validation_rows = validate_query(output, repo_root, include_determinism=False) if include_validation else ()
    return QueryOutput(
        index=index,
        recipes=recipes,
        command_rows=command_rows,
        artifact_rows=artifact_rows,
        delta_rows=delta_rows,
        transcripts=transcripts,
        guide_markdown=guide_markdown,
        manifest_rows=manifest_rows,
        validation_rows=validation_rows,
    )


def write_artifacts(output: QueryOutput, artifacts_dir: Path | None = None) -> dict[str, Path]:
    out_dir = artifacts_dir if artifacts_dir is not None else REPO_ROOT / "artifacts"
    out_dir.mkdir(parents=True, exist_ok=True)
    contents = _artifact_contents(output)
    paths: dict[str, Path] = {}
    for role, basename in P380_ARTIFACT_BASENAMES.items():
        path = out_dir / basename
        path.write_text(contents[role], encoding="utf-8")
        paths[role] = path
    return paths


def _print_csv(columns: Sequence[str], rows: Sequence[Mapping[str, str]]) -> None:
    print(_csv_text(columns, rows), end="")


def _print_query(output: QueryOutput, recipe_id: str) -> int:
    if recipe_id not in RECIPE_IDS:
        raise SystemExit(f"unknown recipe_id: {recipe_id}")
    if recipe_id in {"all_commands", "non_pass_commands"}:
        _print_csv(COMMAND_RESULT_COLUMNS, _filter_by_query(output.command_rows, recipe_id))
    elif recipe_id in {"all_artifacts", "stale_or_missing_artifacts"}:
        _print_csv(ARTIFACT_RESULT_COLUMNS, _filter_by_query(output.artifact_rows, recipe_id))
    elif recipe_id in {"all_deltas", "warn_or_fail_deltas"}:
        _print_csv(DELTA_RESULT_COLUMNS, _filter_by_query(output.delta_rows, recipe_id))
    else:
        print(_json_text(_handoff_digest(output.command_rows, output.artifact_rows, output.delta_rows, output.index["path_warnings"])), end="")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="P380 Big Lotto no-DB regression archive query API / recipe runner")
    parser.add_argument("--artifacts-dir", type=Path, default=None)
    parser.add_argument("--generate", action="store_true", help="Write all P380 query artifacts.")
    parser.add_argument("--recipes", action="store_true", help="Print recipe JSON.")
    parser.add_argument("--list-commands", action="store_true", help="Print archived command results CSV.")
    parser.add_argument("--list-artifacts", action="store_true", help="Print archived artifact results CSV.")
    parser.add_argument("--list-deltas", action="store_true", help="Print archived delta results CSV.")
    parser.add_argument("--query", choices=RECIPE_IDS, default=None, help="Run one deterministic recipe.")
    parser.add_argument("--show-command", default=None, help="Print one command row as JSON by command_id.")
    parser.add_argument("--show-artifact", default=None, help="Print one artifact row as JSON by role, basename, or path.")
    parser.add_argument("--validate", action="store_true", help="Print validation CSV.")
    args = parser.parse_args(argv)

    output = run_query(include_validation=True)
    if args.generate:
        paths = write_artifacts(output, args.artifacts_dir)
        first = run_query(include_validation=False)
        second = run_query(include_validation=False)
        determinism = "PASS" if _artifact_contents(first) == _artifact_contents(second) else "FAIL"
        print(f"P380 regression archive query artifacts written: {len(paths)}")
        print(f"determinism double-run {determinism}")
        print(f"recipes={len(RECIPE_IDS)} commands={output.index['counts']['all_commands']} artifacts={output.index['counts']['all_artifacts']} deltas={output.index['counts']['all_deltas']}")
        print(NO_DB_NO_ADAPTER_NO_SCORING_NO_DEPLOY_STATEMENT)
    elif args.recipes:
        print(_json_text(output.recipes), end="")
    elif args.list_commands:
        _print_csv(COMMAND_RESULT_COLUMNS, _filter_by_query(output.command_rows, "all_commands"))
    elif args.list_artifacts:
        _print_csv(ARTIFACT_RESULT_COLUMNS, _filter_by_query(output.artifact_rows, "all_artifacts"))
    elif args.list_deltas:
        _print_csv(DELTA_RESULT_COLUMNS, _filter_by_query(output.delta_rows, "all_deltas"))
    elif args.query:
        return _print_query(output, args.query)
    elif args.show_command:
        print(_json_text(_show_command_payload(output.command_rows, args.show_command)), end="")
    elif args.show_artifact:
        print(_json_text(_show_artifact_payload(output.artifact_rows, args.show_artifact)), end="")
    elif args.validate:
        _print_csv(VALIDATION_COLUMNS, validate_query(output))
    else:
        parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
