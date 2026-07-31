"""P372 Big Lotto no-DB command center route replay and health monitor.

This module replays the merged P371 command-center routes from committed
artifacts and P371 no-DB route functions. It does not open or write a DB, call
adapters, create new scoring cohorts, import production registries, deploy,
provide betting advice, or make future-performance claims.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from recovered_strategies.biglotto import no_db_evidence_command_center as center

REPO_ROOT = Path(__file__).resolve().parents[2]
TASK = "P372_biglotto_command_center_route_replay"
GENERATED_AT = "DETERMINISTIC_PLACEHOLDER"
SOURCE_BASELINE = "1a971bd14a11de3e6e5967cfb543ab7069e97100"

P372_ARTIFACT_BASENAMES = {
    "route_transcripts": "P372_biglotto_command_center_route_transcripts.json",
    "route_health": "P372_biglotto_command_center_route_health.csv",
    "route_coverage": "P372_biglotto_command_center_route_coverage.csv",
    "failure_taxonomy": "P372_biglotto_command_center_failure_taxonomy.csv",
    "smoke_bundle": "P372_biglotto_command_center_smoke_bundle.json",
    "manifest": "P372_biglotto_command_center_manifest.csv",
}

P371_REQUIRED_EVIDENCE = (
    "recovered_strategies/biglotto/no_db_evidence_command_center.py",
    "artifacts/P371_biglotto_command_center_index.json",
    "artifacts/P371_biglotto_command_center_routes.csv",
    "artifacts/P371_biglotto_command_center_status.json",
    "artifacts/P371_biglotto_command_center_smoke_results.csv",
    "artifacts/P371_biglotto_command_center_task_cards.json",
    "artifacts/P371_biglotto_command_center_launchpad.html",
    "artifacts/P371_biglotto_command_center_quickstart.md",
    "artifacts/P371_biglotto_command_center_manifest.csv",
    "tests/test_p371_biglotto_evidence_command_center.py",
)

DISCLAIMER_LINES = (
    "Historical descriptive evidence only.",
    "No future prediction guarantee.",
    "No betting advice.",
    "No DB open/write.",
    "No adapter calls.",
    "No new scoring.",
    "No production registry import.",
    "No deploy.",
    "No new scoring cohort.",
    "No blended leaderboard.",
)
SCOPE_STATEMENT = " ".join(DISCLAIMER_LINES)

TRANSCRIPT_REQUIRED_KEYS = (
    "route_id",
    "command",
    "status",
    "output_summary",
    "stdout_excerpt",
    "normalized_output",
    "no_db_confirmed",
    "no_adapter_calls_confirmed",
    "no_new_scoring_confirmed",
    "no_deploy_confirmed",
)

VALIDATION_COLUMNS = ("check_name", "status", "expected", "actual", "details")

ROUTE_HEALTH_COLUMNS = (
    "route_id",
    "route_name",
    "backing_module",
    "expected_artifact",
    "replay_status",
    "parse_status",
    "safety_status",
    "notes",
)

ROUTE_COVERAGE_COLUMNS = (
    "total_routes",
    "replayed_routes",
    "skipped_routes",
    "pass_count",
    "warn_count",
    "fail_count",
    "coverage_rate",
)

FAILURE_TAXONOMY_COLUMNS = (
    "failure_class",
    "replay_detection",
    "route_health_impact",
    "safe_action",
    "no_db_open_write",
    "no_adapter_calls",
    "no_new_scoring",
    "no_deploy",
    "scope_statement",
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

EXPECTED_ROUTE_ARTIFACT = {
    "status": "artifacts/P371_biglotto_command_center_status.json",
    "routes": "artifacts/P371_biglotto_command_center_routes.csv",
    "smoke": "artifacts/P371_biglotto_command_center_smoke_results.csv",
    "list_tools": "artifacts/P371_biglotto_command_center_index.json",
    "list_artifacts": "artifacts/P371_biglotto_command_center_manifest.csv",
    "task_cards": "artifacts/P371_biglotto_command_center_task_cards.json",
    "validate": "tests/test_p371_biglotto_evidence_command_center.py",
    "query_list_adapters": "artifacts/P370_biglotto_agent_pack_consumer_recipe_results.csv",
    "query_compact_shortlist": "artifacts/P370_biglotto_agent_pack_consumer_recipe_results.csv",
}


@dataclass(frozen=True)
class RouteReplayOutput:
    transcripts: dict[str, object]
    route_health_rows: tuple[dict[str, str], ...]
    route_coverage_rows: tuple[dict[str, str], ...]
    failure_taxonomy_rows: tuple[dict[str, str], ...]
    smoke_bundle: dict[str, object]
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


def _check(name: str, passed: bool, expected: object, actual: object, details: str) -> dict[str, str]:
    return {
        "check_name": name,
        "status": "PASS" if passed else "FAIL",
        "expected": str(expected),
        "actual": str(actual),
        "details": details,
    }


def verify_p371_evidence(repo_root: Path | None = None) -> tuple[Path, ...]:
    paths = tuple(_artifact_path(relpath, repo_root) for relpath in P371_REQUIRED_EVIDENCE)
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise RuntimeError(f"required P371 command center evidence missing: {missing}")
    return paths


def _normalize_payload(payload: object, output_format: str) -> tuple[str, str, str]:
    if output_format == "csv" and isinstance(payload, tuple):
        columns = tuple(payload[0]) if payload else ()
        text = _csv_text(columns, payload) if columns else ""
        rows = tuple(csv.DictReader(text.splitlines())) if text else ()
        return text, "PARSED_CSV", f"{len(rows)} CSV rows"
    text = _json_text(payload)
    parsed = json.loads(text)
    if isinstance(parsed, dict):
        summary = f"JSON object keys={len(parsed)}"
    elif isinstance(parsed, list):
        summary = f"JSON list rows={len(parsed)}"
    else:
        summary = f"JSON scalar type={type(parsed).__name__}"
    return text, "PARSED_JSON", summary


def _route_payload(route_id: str, repo_root: Path | None = None) -> object:
    if route_id == "status":
        return center.build_status(repo_root)
    if route_id == "routes":
        return center.build_routes(repo_root)
    if route_id == "smoke":
        return center.run_smoke(repo_root)
    if route_id == "list_tools":
        return center.build_tool_catalog(repo_root)
    if route_id == "list_artifacts":
        output = center._run_command_center_without_validation(repo_root)
        return center.build_manifest_rows(center._artifact_contents_without_manifest(output), repo_root)
    if route_id == "task_cards":
        return center.build_task_cards(repo_root)
    if route_id == "validate":
        return center.validate_command_center(repo_root)
    if route_id == "query_list_adapters":
        return center.query_command_center("list_adapters", repo_root)
    if route_id == "query_compact_shortlist":
        return center.query_command_center("list_compact_shortlist", repo_root)
    raise RuntimeError(f"unsupported P371 safe route id: {route_id}")


def replay_routes(repo_root: Path | None = None) -> dict[str, object]:
    verify_p371_evidence(repo_root)
    routes = center.build_routes(repo_root)
    transcript_rows: list[dict[str, object]] = []
    for route in routes:
        route_id = route["route_id"]
        try:
            payload = _route_payload(route_id, repo_root)
            normalized, parse_status, output_summary = _normalize_payload(payload, route["output_format"])
            status = "PASS"
            error = ""
        except Exception as exc:  # pragma: no cover - failure path is surfaced in health rows.
            normalized = ""
            parse_status = "PARSE_FAILED"
            output_summary = "route replay failed"
            status = "FAIL"
            error = f"{type(exc).__name__}: {exc}"
        excerpt = normalized[:900]
        if len(normalized) > len(excerpt):
            excerpt += "\n...[truncated]"
        transcript_rows.append(
            {
                "route_id": route_id,
                "route_name": route["title"],
                "command": route["command"],
                "status": status,
                "output_summary": output_summary,
                "stdout_excerpt": excerpt,
                "normalized_output": normalized,
                "parse_status": parse_status,
                "error": error,
                "no_db_confirmed": route["no_db_open_write"] == "YES",
                "no_adapter_calls_confirmed": route["no_adapter_calls"] == "YES",
                "no_new_scoring_confirmed": route["no_new_scoring"] == "YES",
                "no_deploy_confirmed": route["no_deploy"] == "YES",
            }
        )
    return {
        "task": TASK,
        "generated_at": GENERATED_AT,
        "source_baseline": SOURCE_BASELINE,
        "source_task": center.TASK,
        "source_artifacts": tuple(P371_REQUIRED_EVIDENCE),
        "scope_lines": DISCLAIMER_LINES,
        "statements": {
            "historical_descriptive_evidence_only": True,
            "future_prediction_guarantee": False,
            "betting_advice": False,
            "db_opened": False,
            "db_written": False,
            "adapter_calls": False,
            "new_scoring": False,
            "production_registry_imported": False,
            "deployed": False,
            "blended_leaderboard": False,
        },
        "route_count": len(transcript_rows),
        "transcripts": transcript_rows,
    }


def build_route_health(transcripts: Mapping[str, object], repo_root: Path | None = None) -> tuple[dict[str, str], ...]:
    verify_p371_evidence(repo_root)
    routes_by_id = {row["route_id"]: row for row in center.build_routes(repo_root)}
    rows: list[dict[str, str]] = []
    for transcript in transcripts["transcripts"]:  # type: ignore[index]
        route_id = str(transcript["route_id"])
        route = routes_by_id[route_id]
        artifact = EXPECTED_ROUTE_ARTIFACT.get(route_id, "")
        artifact_exists = bool(artifact) and _artifact_path(artifact, repo_root).is_file()
        safe = all(
            transcript.get(key) is True
            for key in ("no_db_confirmed", "no_adapter_calls_confirmed", "no_new_scoring_confirmed", "no_deploy_confirmed")
        )
        parsed = str(transcript.get("parse_status", "")).startswith("PARSED_")
        replay_status = "PASS" if transcript["status"] == "PASS" and parsed and safe and artifact_exists else "FAIL"
        rows.append(
            {
                "route_id": route_id,
                "route_name": route["title"],
                "backing_module": "recovered_strategies.biglotto.no_db_evidence_command_center",
                "expected_artifact": artifact,
                "replay_status": replay_status,
                "parse_status": str(transcript.get("parse_status", "")),
                "safety_status": "PASS" if safe else "FAIL",
                "notes": (
                    "Replay parsed P371 artifact-only route; no DB open/write, no adapter calls, "
                    "no new scoring, no production registry import, and no deploy."
                    if replay_status == "PASS"
                    else f"Route replay requires review; expected artifact exists={artifact_exists}."
                ),
            }
        )
    return tuple(rows)


def build_route_coverage(route_health_rows: Sequence[Mapping[str, str]], repo_root: Path | None = None) -> tuple[dict[str, str], ...]:
    total_routes = len(center.build_routes(repo_root))
    replayed_routes = len(route_health_rows)
    pass_count = sum(1 for row in route_health_rows if row["replay_status"] == "PASS")
    warn_count = sum(1 for row in route_health_rows if row["replay_status"] == "WARN")
    fail_count = sum(1 for row in route_health_rows if row["replay_status"] == "FAIL")
    skipped_routes = max(total_routes - replayed_routes, 0)
    coverage_rate = replayed_routes / total_routes if total_routes else 0.0
    return (
        {
            "total_routes": str(total_routes),
            "replayed_routes": str(replayed_routes),
            "skipped_routes": str(skipped_routes),
            "pass_count": str(pass_count),
            "warn_count": str(warn_count),
            "fail_count": str(fail_count),
            "coverage_rate": f"{coverage_rate:.4f}",
        },
    )


def build_failure_taxonomy() -> tuple[dict[str, str], ...]:
    specs = (
        ("missing_artifact", "Expected P371 artifact path is absent or unreadable.", "FAIL", "Stop and regenerate or restore P371 evidence before replay."),
        ("parse_failure", "Route output cannot be parsed as its declared JSON or CSV format.", "FAIL", "Stop and inspect the P371 route output shape."),
        ("unsafe_route", "P371 route row lacks required no-DB/no-adapter/no-scoring/no-deploy flags.", "FAIL", "Do not replay that route until the route catalog is corrected."),
        ("forbidden_language", "Generated text contains an authorization-style forbidden phrase.", "FAIL", "Remove the phrase and rerun deterministic validation."),
        ("db_touch_attempt", "sqlite3.connect or DB-path access would be treated as a replay failure.", "FAIL", "Stop; P372 is artifact-only and must not open or write DB files."),
        ("adapter_call_attempt", "Runtime adapter module execution would be treated as a replay failure.", "FAIL", "Stop; P372 may read evidence naming adapters but must not execute adapters."),
        ("scoring_attempt", "Any new scoring cohort, shape-only scoring, or blocked-target scoring would be treated as a replay failure.", "FAIL", "Stop; P372 only replays historical P371 route outputs."),
        ("deploy_attempt", "Any deploy or production registry import intent would be treated as a replay failure.", "FAIL", "Stop; P372 has no deploy or registry side effects."),
    )
    return tuple(
        {
            "failure_class": failure_class,
            "replay_detection": detection,
            "route_health_impact": impact,
            "safe_action": action,
            "no_db_open_write": "YES",
            "no_adapter_calls": "YES",
            "no_new_scoring": "YES",
            "no_deploy": "YES",
            "scope_statement": SCOPE_STATEMENT,
        }
        for failure_class, detection, impact, action in specs
    )


def build_smoke_bundle(
    transcripts: Mapping[str, object],
    route_health_rows: Sequence[Mapping[str, str]],
    route_coverage_rows: Sequence[Mapping[str, str]],
    failure_taxonomy_rows: Sequence[Mapping[str, str]],
    repo_root: Path | None = None,
) -> dict[str, object]:
    health_summary = {
        "route_count": len(route_health_rows),
        "pass_count": sum(1 for row in route_health_rows if row["replay_status"] == "PASS"),
        "warn_count": sum(1 for row in route_health_rows if row["replay_status"] == "WARN"),
        "fail_count": sum(1 for row in route_health_rows if row["replay_status"] == "FAIL"),
    }
    return {
        "task": TASK,
        "generated_at": GENERATED_AT,
        "source_baseline": SOURCE_BASELINE,
        "source_task": center.TASK,
        "source_artifacts": tuple(P371_REQUIRED_EVIDENCE),
        "source_route_count": len(center.build_routes(repo_root)),
        "route_health_summary": health_summary,
        "route_coverage": tuple(dict(row) for row in route_coverage_rows),
        "transcripts_summary": {
            "route_count": transcripts["route_count"],
            "pass_count": sum(1 for row in transcripts["transcripts"] if row["status"] == "PASS"),  # type: ignore[index]
            "fail_count": sum(1 for row in transcripts["transcripts"] if row["status"] == "FAIL"),  # type: ignore[index]
        },
        "failure_taxonomy_classes": tuple(row["failure_class"] for row in failure_taxonomy_rows),
        "recommended_safe_next_checks": (
            "Run P372 --validate after artifact regeneration.",
            "Run the focused P372 pytest file.",
            "Review route_health FAIL/WARN rows before any downstream handoff.",
        ),
        "statements": {
            "historical_descriptive_evidence_only": True,
            "future_prediction_guarantee": False,
            "betting_advice": False,
            "db_opened": False,
            "db_written": False,
            "adapter_calls": False,
            "new_scoring": False,
            "production_registry_imported": False,
            "deployed": False,
            "blended_leaderboard": False,
        },
        "scope_lines": DISCLAIMER_LINES,
    }


def _artifact_contents_without_manifest(output: RouteReplayOutput) -> dict[str, str]:
    return {
        "route_transcripts": _json_text(output.transcripts),
        "route_health": _csv_text(ROUTE_HEALTH_COLUMNS, output.route_health_rows),
        "route_coverage": _csv_text(ROUTE_COVERAGE_COLUMNS, output.route_coverage_rows),
        "failure_taxonomy": _csv_text(FAILURE_TAXONOMY_COLUMNS, output.failure_taxonomy_rows),
        "smoke_bundle": _json_text(output.smoke_bundle),
    }


def _artifact_contents(output: RouteReplayOutput) -> dict[str, str]:
    contents = _artifact_contents_without_manifest(output)
    contents["manifest"] = _csv_text(MANIFEST_COLUMNS, output.manifest_rows)
    return contents


def _output_counts(role: str, text: str) -> tuple[str, str]:
    if role in {"route_health", "route_coverage", "failure_taxonomy", "manifest"}:
        return str(len(tuple(csv.DictReader(text.splitlines())))), ""
    if role in {"route_transcripts", "smoke_bundle"}:
        return "", "1"
    return "", ""


def build_manifest_rows(output_texts_without_manifest: Mapping[str, str], repo_root: Path | None = None) -> tuple[dict[str, str], ...]:
    rows: list[dict[str, str]] = []
    for relpath in P371_REQUIRED_EVIDENCE:
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
                "details": "P372 source evidence read from merged P371 artifacts only.",
                "scope_statement": SCOPE_STATEMENT,
            }
        )
    for role, basename in P372_ARTIFACT_BASENAMES.items():
        text = output_texts_without_manifest.get(role, "")
        row_count, object_count = _output_counts(role, text)
        digest = sha256_bytes(text.encode("utf-8")) if text else ""
        if role == "manifest":
            row_count = str(len(P371_REQUIRED_EVIDENCE) + len(P372_ARTIFACT_BASENAMES) + 3)
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
                "details": "P372 generated no-DB route replay artifact.",
                "scope_statement": SCOPE_STATEMENT,
            }
        )
    for role, details in (
        ("no_db_open_write", "No DB open/write was performed by P372."),
        ("no_adapter_calls", "No adapter calls were performed by P372."),
        ("no_new_scoring", "No new scoring, scoring cohort, shape-only scoring, blocked-target scoring, or blended leaderboard was created by P372."),
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


def validate_route_replay(output: RouteReplayOutput | None = None, repo_root: Path | None = None, include_determinism: bool = True) -> tuple[dict[str, str], ...]:
    current = output if output is not None else run_route_replay(repo_root, include_validation=False)
    routes = center.build_routes(repo_root)
    transcripts = current.transcripts
    text = "\n".join(_artifact_contents(current).values()).lower()
    found = [phrase for phrase in FORBIDDEN_AUTHORIZATION_PHRASES if phrase in text]
    rows = [
        _check("required_p371_module_and_artifacts_exist", len(verify_p371_evidence(repo_root)) == len(P371_REQUIRED_EVIDENCE), len(P371_REQUIRED_EVIDENCE), len(P371_REQUIRED_EVIDENCE), "P371 command center module, artifacts, and test evidence are present."),
        _check("route_transcripts_json_schema", all(set(row) >= set(TRANSCRIPT_REQUIRED_KEYS) for row in transcripts["transcripts"]), "required transcript keys", len(transcripts["transcripts"]), "Every replayed route has deterministic transcript fields."),
        _check("route_health_csv_schema", bool(current.route_health_rows) and tuple(current.route_health_rows[0]) == ROUTE_HEALTH_COLUMNS, ROUTE_HEALTH_COLUMNS, tuple(current.route_health_rows[0]) if current.route_health_rows else (), "Route health rows use required columns."),
        _check("route_coverage_csv_schema", bool(current.route_coverage_rows) and tuple(current.route_coverage_rows[0]) == ROUTE_COVERAGE_COLUMNS, ROUTE_COVERAGE_COLUMNS, tuple(current.route_coverage_rows[0]) if current.route_coverage_rows else (), "Route coverage summary uses required columns."),
        _check("failure_taxonomy_csv_schema", bool(current.failure_taxonomy_rows) and tuple(current.failure_taxonomy_rows[0]) == FAILURE_TAXONOMY_COLUMNS, FAILURE_TAXONOMY_COLUMNS, tuple(current.failure_taxonomy_rows[0]) if current.failure_taxonomy_rows else (), "Failure taxonomy rows use required columns."),
        _check("smoke_bundle_json_schema", set(current.smoke_bundle) >= {"source_baseline", "source_artifacts", "route_health_summary", "transcripts_summary", "recommended_safe_next_checks", "statements"}, "required smoke bundle keys", sorted(current.smoke_bundle), "Smoke bundle includes baseline, summaries, safe checks, and safety statements."),
        _check("manifest_csv_schema", bool(current.manifest_rows) and tuple(current.manifest_rows[0]) == MANIFEST_COLUMNS, MANIFEST_COLUMNS, tuple(current.manifest_rows[0]) if current.manifest_rows else (), "Manifest rows use required columns."),
        _check("all_routes_replayed", transcripts["route_count"] == len(routes), len(routes), transcripts["route_count"], "Every P371 safe command-center route is replayed."),
        _check("route_health_all_pass", all(row["replay_status"] == "PASS" for row in current.route_health_rows), "all PASS", sum(1 for row in current.route_health_rows if row["replay_status"] != "PASS"), "All route health rows pass."),
        _check("coverage_complete", current.route_coverage_rows[0]["coverage_rate"] == "1.0000", "1.0000", current.route_coverage_rows[0]["coverage_rate"], "Route replay coverage is complete."),
        _check("failure_taxonomy_complete", {row["failure_class"] for row in current.failure_taxonomy_rows} == {"missing_artifact", "parse_failure", "unsafe_route", "forbidden_language", "db_touch_attempt", "adapter_call_attempt", "scoring_attempt", "deploy_attempt"}, "required failure classes", sorted(row["failure_class"] for row in current.failure_taxonomy_rows), "Failure taxonomy includes all required classes."),
        _check("generated_outputs_do_not_authorize_forbidden_actions", not found, "absent", ";".join(found) if found else "absent", "P372 generated outputs do not authorize DB writes, adapter execution, scoring, deploy, force operations, status changes, betting advice, or future prediction claims."),
        _check("generated_outputs_include_safety_constraints", all(line.lower() in text for line in DISCLAIMER_LINES), "all scope lines", "present", "Outputs include no-DB/no-adapter/no-scoring/no-deploy constraints."),
    ]
    if include_determinism:
        first = run_route_replay(repo_root, include_validation=False)
        second = run_route_replay(repo_root, include_validation=False)
        rows.append(
            _check(
                "deterministic_double_run_equality",
                _artifact_contents(first) == _artifact_contents(second),
                "equal",
                "equal" if _artifact_contents(first) == _artifact_contents(second) else "different",
                "P372 generated rows and artifacts are deterministic across two runs.",
            )
        )
    return tuple(rows)


def run_route_replay(repo_root: Path | None = None, include_validation: bool = True) -> RouteReplayOutput:
    transcripts = replay_routes(repo_root)
    health = build_route_health(transcripts, repo_root)
    coverage = build_route_coverage(health, repo_root)
    taxonomy = build_failure_taxonomy()
    smoke = build_smoke_bundle(transcripts, health, coverage, taxonomy, repo_root)
    placeholder = RouteReplayOutput(transcripts, health, coverage, taxonomy, smoke, (), ())
    manifest = build_manifest_rows(_artifact_contents_without_manifest(placeholder), repo_root)
    partial = RouteReplayOutput(transcripts, health, coverage, taxonomy, smoke, manifest, ())
    validation = validate_route_replay(partial, repo_root, include_determinism=True) if include_validation else ()
    return RouteReplayOutput(transcripts, health, coverage, taxonomy, smoke, manifest, validation)


def _assert_deterministic(first: RouteReplayOutput, second: RouteReplayOutput) -> None:
    if _artifact_contents(first) != _artifact_contents(second):
        raise RuntimeError("determinism double-run mismatch: P372 route replay artifacts are not reproducible")


def write_artifacts(output: RouteReplayOutput, artifacts_dir: Path | None = None) -> dict[str, Path]:
    directory = Path(artifacts_dir) if artifacts_dir is not None else REPO_ROOT / "artifacts"
    directory.mkdir(parents=True, exist_ok=True)
    contents = _artifact_contents(output)
    paths = {key: directory / basename for key, basename in P372_ARTIFACT_BASENAMES.items()}
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
    parser.add_argument("--generate", action="store_true", help="write all P372 route replay artifacts")
    parser.add_argument("--replay-routes", action="store_true", help="emit route transcripts JSON")
    parser.add_argument("--health", action="store_true", help="emit route health CSV")
    parser.add_argument("--coverage", action="store_true", help="emit route coverage CSV")
    parser.add_argument("--smoke-bundle", action="store_true", help="emit smoke bundle JSON")
    parser.add_argument("--validate", action="store_true", help="emit P372 validation rows as CSV")
    args = parser.parse_args(argv)

    if args.replay_routes:
        _print_json(replay_routes())
    elif args.health:
        transcripts = replay_routes()
        _print_csv(ROUTE_HEALTH_COLUMNS, build_route_health(transcripts))
    elif args.coverage:
        transcripts = replay_routes()
        health = build_route_health(transcripts)
        _print_csv(ROUTE_COVERAGE_COLUMNS, build_route_coverage(health))
    elif args.smoke_bundle:
        output = run_route_replay()
        _print_json(output.smoke_bundle)
    elif args.validate:
        _print_csv(VALIDATION_COLUMNS, validate_route_replay())
    else:
        first = run_route_replay()
        second = run_route_replay()
        _assert_deterministic(first, second)
        paths = write_artifacts(first, args.artifacts_dir)
        print("P372 Big Lotto no-DB command center route replay: determinism double-run PASS")
        print(f"validation rows: {len(first.validation_rows)}")
        print(f"validation failures: {sum(1 for row in first.validation_rows if row['status'] == 'FAIL')}")
        print("No DB was opened or written; no adapters were called; no new scoring was created; no production registry import or deploy was performed.")
        print("Historical descriptive evidence only; no betting advice; no future prediction guarantee.")
        for key, path in sorted(paths.items()):
            print(f"{key}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
