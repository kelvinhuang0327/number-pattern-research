#!/usr/bin/env python3
"""
P518J no-DB healthcheck runner for the predraw ledger verifier evidence stack.

This module reads committed P518I/P518H/P518F/P518G artifacts only. It does not
execute the verifier, smoke, edge, acceptance, or status CLIs; does not open or
write the canonical DB; does not run migrations/backfills; does not deploy; is
not production release approval; and makes no betting or future prediction
claims.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
SOURCE_ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"

ARTIFACT_PREFIX = "P518J_predraw_ledger_verify_healthcheck"

HEALTH_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_result.json"
ARTIFACT_INVENTORY_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_artifact_inventory.csv"
COMMAND_MATRIX_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_command_matrix.csv"
DB_INVARIANT_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_db_invariant.json"
STATUS_BLOCK_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_status_block.md"
MANIFEST_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_manifest.csv"

NOTICE_LINES = (
    "no canonical DB open/write",
    "no migration/backfill",
    "no deploy",
    "synthetic fixture evidence only",
    "not production release approval",
    "no betting/future prediction claims",
)

INVENTORY_FIELDS = (
    "phase",
    "artifact_path",
    "artifact_kind",
    "required_for_health",
    "exists",
    "sha256",
    "bytes",
    "notes",
)
COMMAND_FIELDS = (
    "command_id",
    "command",
    "evidence_layer",
    "reads_artifacts_only",
    "generates_artifacts",
    "executes_verifier_or_harness",
    "opens_canonical_db",
    "notes",
)
MANIFEST_FIELDS = ("artifact_path", "artifact_kind", "sha256", "bytes", "notes")

EXPECTED_SOURCE_ARTIFACTS: Sequence[Tuple[str, str, str, bool]] = (
    ("P518I", "P518I_predraw_ledger_verify_status_summary.json", "json", True),
    ("P518I", "P518I_predraw_ledger_verify_status_badges.json", "json", True),
    ("P518I", "P518I_predraw_ledger_verify_status_block.md", "md", True),
    ("P518I", "P518I_predraw_ledger_verify_status_query_summary.json", "json", True),
    ("P518I", "P518I_predraw_ledger_verify_status_report.md", "md", True),
    ("P518I", "P518I_predraw_ledger_verify_status_manifest.csv", "csv", True),
    ("P518H", "P518H_predraw_ledger_verify_acceptance_decision.json", "json", True),
    ("P518H", "P518H_predraw_ledger_verify_acceptance_case_summary.csv", "csv", True),
    ("P518H", "P518H_predraw_ledger_verify_acceptance_failure_matrix.csv", "csv", True),
    ("P518H", "P518H_predraw_ledger_verify_acceptance_db_invariant.json", "json", True),
    ("P518H", "P518H_predraw_ledger_verify_acceptance_report.md", "md", True),
    ("P518H", "P518H_predraw_ledger_verify_acceptance_manifest.csv", "csv", True),
    ("P518F", "P518F_predraw_ledger_verify_smoke_results.json", "json", True),
    ("P518F", "P518F_predraw_ledger_verify_smoke_cases.csv", "csv", True),
    ("P518F", "P518F_predraw_ledger_verify_smoke_transcripts.json", "json", True),
    ("P518F", "P518F_predraw_ledger_verify_smoke_report.md", "md", True),
    ("P518F", "P518F_predraw_ledger_verify_smoke_manifest.csv", "csv", True),
    ("P518G", "P518G_predraw_ledger_verify_edge_matrix_results.json", "json", True),
    ("P518G", "P518G_predraw_ledger_verify_edge_matrix_cases.csv", "csv", True),
    ("P518G", "P518G_predraw_ledger_verify_edge_matrix_coverage.csv", "csv", True),
    ("P518G", "P518G_predraw_ledger_verify_edge_matrix_transcripts.json", "json", True),
    ("P518G", "P518G_predraw_ledger_verify_edge_matrix_report.md", "md", True),
    ("P518G", "P518G_predraw_ledger_verify_edge_matrix_manifest.csv", "csv", True),
)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _artifact_label(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return path.name


def _artifact_path(filename: str) -> Path:
    return SOURCE_ARTIFACTS_DIR / filename


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(_read_text(path))


def _load_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _json_text(data: Mapping[str, Any]) -> str:
    return json.dumps(data, indent=2, sort_keys=True) + "\n"


def _csv_text(rows: Sequence[Mapping[str, Any]], fieldnames: Sequence[str]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fieldnames})
    return buffer.getvalue()


def _required_notices_present(*values: Any) -> bool:
    combined = "\n".join(str(value) for value in values)
    required = (
        "no canonical DB open/write",
        "no migration/backfill",
        "no deploy",
        "not production release approval",
        "no betting/future prediction claims",
    )
    return all(notice in combined for notice in required) and (
        "synthetic fixture evidence only" in combined or "synthetic fixtures only" in combined
    )


def _status_or_fail(value: Any) -> str:
    status = str(value or "FAIL")
    return status if status in {"PASS", "WARN", "FAIL"} else "FAIL"


def build_artifact_inventory() -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for phase, filename, kind, required in EXPECTED_SOURCE_ARTIFACTS:
        path = _artifact_path(filename)
        if path.exists():
            data = path.read_bytes()
            rows.append(
                {
                    "phase": phase,
                    "artifact_path": _artifact_label(path),
                    "artifact_kind": kind,
                    "required_for_health": required,
                    "exists": True,
                    "sha256": _sha256_bytes(data),
                    "bytes": len(data),
                    "notes": "; ".join(NOTICE_LINES),
                }
            )
        else:
            rows.append(
                {
                    "phase": phase,
                    "artifact_path": _artifact_label(path),
                    "artifact_kind": kind,
                    "required_for_health": required,
                    "exists": False,
                    "sha256": "",
                    "bytes": 0,
                    "notes": "missing artifact; " + "; ".join(NOTICE_LINES),
                }
            )
    return rows


def _manifest_checks(manifest_filename: str) -> List[Dict[str, Any]]:
    checks: List[Dict[str, Any]] = []
    for row in _load_csv(_artifact_path(manifest_filename)):
        relpath = row.get("artifact_path", "")
        expected_sha = row.get("sha256", "")
        expected_bytes = row.get("bytes", "")
        if not expected_sha:
            checks.append(
                {
                    "manifest_path": f"artifacts/{manifest_filename}",
                    "artifact_path": relpath,
                    "status": "PASS",
                    "notes": "manifest self-hash intentionally omitted",
                }
            )
            continue
        path = PROJECT_ROOT / relpath
        if not path.exists():
            checks.append(
                {
                    "manifest_path": f"artifacts/{manifest_filename}",
                    "artifact_path": relpath,
                    "status": "FAIL",
                    "notes": "missing artifact",
                }
            )
            continue
        data = path.read_bytes()
        actual_sha = _sha256_bytes(data)
        actual_bytes = str(len(data))
        status = "PASS" if actual_sha == expected_sha and actual_bytes == expected_bytes else "FAIL"
        checks.append(
            {
                "manifest_path": f"artifacts/{manifest_filename}",
                "artifact_path": relpath,
                "status": status,
                "notes": f"sha256={actual_sha}; bytes={actual_bytes}",
            }
        )
    return checks


def _all_manifest_checks() -> List[Dict[str, Any]]:
    return [
        *_manifest_checks("P518I_predraw_ledger_verify_status_manifest.csv"),
        *_manifest_checks("P518H_predraw_ledger_verify_acceptance_manifest.csv"),
        *_manifest_checks("P518F_predraw_ledger_verify_smoke_manifest.csv"),
        *_manifest_checks("P518G_predraw_ledger_verify_edge_matrix_manifest.csv"),
    ]


def _count_case_failures(rows: Iterable[Mapping[str, str]]) -> int:
    return sum(1 for row in rows if row.get("status") != "PASS")


def build_db_invariant_snapshot() -> Dict[str, Any]:
    p518i_summary = _load_json(_artifact_path("P518I_predraw_ledger_verify_status_summary.json"))
    p518h_db = _load_json(_artifact_path("P518H_predraw_ledger_verify_acceptance_db_invariant.json"))
    p518f_results = _load_json(_artifact_path("P518F_predraw_ledger_verify_smoke_results.json"))
    p518g_results = _load_json(_artifact_path("P518G_predraw_ledger_verify_edge_matrix_results.json"))

    p518i_db_status = _status_or_fail(p518i_summary.get("db_invariant", {}).get("status"))
    p518h_db_status = _status_or_fail(p518h_db.get("status"))
    p518f_no_db = p518f_results.get("no_db_evidence", {})
    p518g_no_db = p518g_results.get("no_db_evidence", {})
    p518f_status = "PASS" if _no_db_evidence_passes(p518f_no_db) else "FAIL"
    p518g_status = "PASS" if _no_db_evidence_passes(p518g_no_db) else "FAIL"
    status = "PASS" if all(item == "PASS" for item in (p518i_db_status, p518h_db_status, p518f_status, p518g_status)) else "FAIL"

    return {
        "artifact_prefix": ARTIFACT_PREFIX,
        "status": status,
        "p518j_runner_invariant": {
            "canonical_db_path": "data/lottery_v2.db",
            "canonical_db_opened": False,
            "canonical_db_written": False,
            "canonical_db_hash_computed_by_runner": False,
            "migration_backfill_deploy_run": False,
            "fixture_scope": "committed P518I/P518H/P518F/P518G artifacts only",
            "status": "PASS",
        },
        "source_invariants": {
            "P518I_db_invariant_status": p518i_db_status,
            "P518H_db_invariant_status": p518h_db_status,
            "P518F_no_db_evidence_status": p518f_status,
            "P518G_no_db_evidence_status": p518g_status,
            "P518H_checks": p518h_db.get("checks", []),
            "P518F_no_db_evidence": p518f_no_db,
            "P518G_no_db_evidence": p518g_no_db,
        },
        "notices": list(NOTICE_LINES),
    }


def _no_db_evidence_passes(evidence: Mapping[str, Any]) -> bool:
    return bool(evidence) and (
        evidence.get("canonical_db_opened") is False
        and evidence.get("canonical_db_written") is False
        and evidence.get("migration_backfill_deploy_run") is False
        and evidence.get("canonical_db_exists_before") == evidence.get("canonical_db_exists_after")
    )


def build_command_matrix() -> List[Dict[str, Any]]:
    notice_notes = "; ".join(NOTICE_LINES)
    return [
        {
            "command_id": "p518j_health",
            "command": "python3 -m tools.predraw_ledger_verify_healthcheck --health",
            "evidence_layer": "P518J",
            "reads_artifacts_only": True,
            "generates_artifacts": False,
            "executes_verifier_or_harness": False,
            "opens_canonical_db": False,
            "notes": "primary Worker handoff health command; " + notice_notes,
        },
        {
            "command_id": "p518j_generate",
            "command": "python3 -m tools.predraw_ledger_verify_healthcheck --generate",
            "evidence_layer": "P518J",
            "reads_artifacts_only": True,
            "generates_artifacts": True,
            "executes_verifier_or_harness": False,
            "opens_canonical_db": False,
            "notes": "generates P518J artifacts from committed evidence only; " + notice_notes,
        },
        {
            "command_id": "p518j_validate",
            "command": "python3 -m tools.predraw_ledger_verify_healthcheck --validate",
            "evidence_layer": "P518J",
            "reads_artifacts_only": True,
            "generates_artifacts": False,
            "executes_verifier_or_harness": False,
            "opens_canonical_db": False,
            "notes": "validates committed P518J artifacts by byte equality; " + notice_notes,
        },
        {
            "command_id": "p518i_status",
            "command": "python3 -m tools.predraw_ledger_verify_status --status",
            "evidence_layer": "P518I",
            "reads_artifacts_only": True,
            "generates_artifacts": False,
            "executes_verifier_or_harness": False,
            "opens_canonical_db": False,
            "notes": "reads committed P518H acceptance artifacts only; " + notice_notes,
        },
        {
            "command_id": "p518i_generate",
            "command": "python3 -m tools.predraw_ledger_verify_status --generate",
            "evidence_layer": "P518I",
            "reads_artifacts_only": True,
            "generates_artifacts": True,
            "executes_verifier_or_harness": False,
            "opens_canonical_db": False,
            "notes": "regenerates P518I status artifacts from committed P518H artifacts; " + notice_notes,
        },
        {
            "command_id": "p518h_decision",
            "command": "python3 -m tools.predraw_ledger_verify_acceptance --decision",
            "evidence_layer": "P518H",
            "reads_artifacts_only": True,
            "generates_artifacts": False,
            "executes_verifier_or_harness": False,
            "opens_canonical_db": False,
            "notes": "reads committed P518F/P518G artifacts only; " + notice_notes,
        },
        {
            "command_id": "p518h_generate",
            "command": "python3 -m tools.predraw_ledger_verify_acceptance --generate",
            "evidence_layer": "P518H",
            "reads_artifacts_only": True,
            "generates_artifacts": True,
            "executes_verifier_or_harness": False,
            "opens_canonical_db": False,
            "notes": "regenerates P518H acceptance artifacts from committed P518F/P518G artifacts; " + notice_notes,
        },
        {
            "command_id": "p518f_smoke_reference",
            "command": "python3 -m tools.predraw_ledger_verify_smoke --validate",
            "evidence_layer": "P518F",
            "reads_artifacts_only": False,
            "generates_artifacts": False,
            "executes_verifier_or_harness": True,
            "opens_canonical_db": False,
            "notes": "reference validation uses temporary synthetic fixtures and verifier harness; P518J does not execute it; "
            + notice_notes,
        },
        {
            "command_id": "p518g_edge_reference",
            "command": "python3 -m tools.predraw_ledger_verify_smoke --validate",
            "evidence_layer": "P518G",
            "reads_artifacts_only": False,
            "generates_artifacts": False,
            "executes_verifier_or_harness": True,
            "opens_canonical_db": False,
            "notes": "same module validates P518G edge matrix with temporary synthetic fixtures; P518J does not execute it; "
            + notice_notes,
        },
    ]


def build_healthcheck_bundle() -> Dict[str, Any]:
    inventory = build_artifact_inventory()
    manifest_checks = _all_manifest_checks()

    p518i_summary = _load_json(_artifact_path("P518I_predraw_ledger_verify_status_summary.json"))
    p518i_query = _load_json(_artifact_path("P518I_predraw_ledger_verify_status_query_summary.json"))
    p518h_decision = _load_json(_artifact_path("P518H_predraw_ledger_verify_acceptance_decision.json"))
    p518h_db = _load_json(_artifact_path("P518H_predraw_ledger_verify_acceptance_db_invariant.json"))
    p518f_results = _load_json(_artifact_path("P518F_predraw_ledger_verify_smoke_results.json"))
    p518g_results = _load_json(_artifact_path("P518G_predraw_ledger_verify_edge_matrix_results.json"))
    p518h_case_rows = _load_csv(_artifact_path("P518H_predraw_ledger_verify_acceptance_case_summary.csv"))
    source_texts = [
        _read_text(_artifact_path(filename))
        for _, filename, _, _ in EXPECTED_SOURCE_ARTIFACTS
        if _artifact_path(filename).exists()
    ]

    p518i_status = _status_or_fail(p518i_summary.get("final_compact_status") or p518i_query.get("final_compact_status"))
    p518h_status = _status_or_fail(p518h_decision.get("final_status"))
    p518f_status = _status_or_fail(p518f_results.get("overall_status"))
    p518g_status = _status_or_fail(p518g_results.get("overall_status"))
    db_invariant = build_db_invariant_snapshot()
    db_status = _status_or_fail(db_invariant.get("status") or p518h_db.get("status"))
    canonical_refusal_status = _status_or_fail(
        p518i_summary.get("canonical_db_refusal_status")
        or p518h_decision.get("canonical_db_refusal_evidence", {}).get("status")
    )
    missing_artifacts = [row["artifact_path"] for row in inventory if not row["exists"]]
    manifest_failures = [check for check in manifest_checks if check.get("status") != "PASS"]
    case_failure_count = _count_case_failures(p518h_case_rows)
    required_notice_status = "PASS" if _required_notices_present(*source_texts) else "FAIL"

    component_statuses = {
        "P518I compact status": p518i_status,
        "P518H acceptance decision": p518h_status,
        "P518F smoke status": p518f_status,
        "P518G edge matrix status": p518g_status,
        "DB invariant status": db_status,
        "canonical DB refusal status": canonical_refusal_status,
        "source manifest status": "PASS" if not manifest_failures and manifest_checks else "FAIL",
        "required notice status": required_notice_status,
    }
    warning_items: List[str] = []
    if not manifest_checks and not missing_artifacts:
        warning_items.append("source manifests had no rows")
    failed_count = sum(1 for status in component_statuses.values() if status == "FAIL")
    failed_count += len(missing_artifacts) + len(manifest_failures) + case_failure_count
    warning_count = sum(1 for status in component_statuses.values() if status == "WARN") + len(warning_items)
    final_health = "FAIL" if failed_count else "WARN" if warning_count else "PASS"
    suggested_next_command = (
        "python3 -m tools.predraw_ledger_verify_healthcheck --status-block"
        if final_health == "PASS"
        else "python3 -m tools.predraw_ledger_verify_healthcheck --artifact-inventory"
    )

    health_result = {
        "artifact_prefix": ARTIFACT_PREFIX,
        "final_verifier_health": final_health,
        "p518i_compact_status": p518i_status,
        "p518h_acceptance_decision": p518h_status,
        "p518f_smoke_status": p518f_status,
        "p518g_edge_matrix_status": p518g_status,
        "db_invariant_status": db_status,
        "canonical_db_refusal_status": canonical_refusal_status,
        "missing_artifact_count": len(missing_artifacts),
        "missing_artifacts": missing_artifacts,
        "failed_count": failed_count,
        "warning_count": warning_count,
        "warnings": warning_items,
        "source_manifest_failures": manifest_failures,
        "source_case_failure_count": case_failure_count,
        "suggested_next_command": suggested_next_command,
        "component_statuses": component_statuses,
        "source_artifact_count": len(inventory),
        "source_manifest_check_count": len(manifest_checks),
        "db_side_effect_scope": db_invariant["p518j_runner_invariant"],
        "scope": (
            "P518J reads committed P518I/P518H/P518F/P518G artifacts only; no verifier, smoke, "
            "edge, acceptance, or status CLI execution; no canonical DB open/write; no "
            "migration/backfill; no deploy; synthetic fixture evidence only; not production "
            "release approval; no betting/future prediction claims."
        ),
        "notices": list(NOTICE_LINES),
    }

    return {
        "health": health_result,
        "artifact_inventory": inventory,
        "command_matrix": build_command_matrix(),
        "db_invariant": db_invariant,
        "status_block": _status_block_md(health_result),
        "manifest_checks": manifest_checks,
    }


def _status_block_md(health: Mapping[str, Any]) -> str:
    lines = [
        "## P518J Predraw Ledger Verifier Healthcheck",
        "",
        f"- Final verifier health: `{health['final_verifier_health']}`",
        f"- P518I compact status: `{health['p518i_compact_status']}`",
        f"- P518H acceptance decision: `{health['p518h_acceptance_decision']}`",
        f"- P518F smoke status: `{health['p518f_smoke_status']}`",
        f"- P518G edge matrix status: `{health['p518g_edge_matrix_status']}`",
        f"- DB invariant status: `{health['db_invariant_status']}`",
        f"- Canonical DB refusal status: `{health['canonical_db_refusal_status']}`",
        f"- Missing artifact count: `{health['missing_artifact_count']}`",
        f"- Failed count: `{health['failed_count']}`",
        f"- Warning count: `{health['warning_count']}`",
        f"- Suggested next command: `{health['suggested_next_command']}`",
        "",
        "Safety / scope:",
    ]
    lines.extend(f"- {notice}" for notice in NOTICE_LINES)
    lines.append("- P518J reads committed P518I/P518H/P518F/P518G artifacts only.")
    lines.append("- P518J is not production release approval.")
    lines.append("")
    return "\n".join(lines)


def _manifest_csv(rendered: Mapping[Path, str]) -> str:
    rows: List[Dict[str, Any]] = []
    for path in (HEALTH_PATH, ARTIFACT_INVENTORY_PATH, COMMAND_MATRIX_PATH, DB_INVARIANT_PATH, STATUS_BLOCK_PATH):
        data = rendered[path].encode("utf-8")
        rows.append(
            {
                "artifact_path": _artifact_label(path),
                "artifact_kind": path.suffix.lstrip("."),
                "sha256": _sha256_bytes(data),
                "bytes": len(data),
                "notes": "; ".join(NOTICE_LINES),
            }
        )
    rows.append(
        {
            "artifact_path": _artifact_label(MANIFEST_PATH),
            "artifact_kind": "csv",
            "sha256": "",
            "bytes": "",
            "notes": "manifest self-hash intentionally omitted; " + "; ".join(NOTICE_LINES),
        }
    )
    return _csv_text(rows, MANIFEST_FIELDS)


def render_artifacts() -> Dict[Path, str]:
    bundle = build_healthcheck_bundle()
    rendered: Dict[Path, str] = {
        HEALTH_PATH: _json_text(bundle["health"]),
        ARTIFACT_INVENTORY_PATH: _csv_text(bundle["artifact_inventory"], INVENTORY_FIELDS),
        COMMAND_MATRIX_PATH: _csv_text(bundle["command_matrix"], COMMAND_FIELDS),
        DB_INVARIANT_PATH: _json_text(bundle["db_invariant"]),
        STATUS_BLOCK_PATH: bundle["status_block"],
    }
    rendered[MANIFEST_PATH] = _manifest_csv(rendered)
    return rendered


def write_artifacts(rendered: Mapping[Path, str] | None = None) -> Dict[Path, str]:
    rendered = dict(rendered or render_artifacts())
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    for path, body in rendered.items():
        path.write_text(body, encoding="utf-8")
    return rendered


def validate_artifacts(rendered: Mapping[Path, str] | None = None) -> Tuple[bool, List[str]]:
    first = dict(rendered or render_artifacts())
    second = render_artifacts()
    mismatches: List[str] = []
    if first != second:
        mismatches.append("deterministic double-run mismatch")
    for path, expected in first.items():
        if not path.exists():
            mismatches.append(f"missing: {_artifact_label(path)}")
            continue
        actual = _read_text(path)
        if actual != expected:
            mismatches.append(f"content mismatch: {_artifact_label(path)}")
    health = json.loads(first[HEALTH_PATH])
    if health.get("final_verifier_health") == "FAIL":
        mismatches.append("final_verifier_health=FAIL")
    if health.get("db_side_effect_scope", {}).get("canonical_db_hash_computed_by_runner") is not False:
        mismatches.append("P518J runner unexpectedly computed canonical DB hash")
    if not _required_notices_present(*first.values()):
        mismatches.append("required safety notices missing from P518J artifacts")
    return not mismatches, mismatches


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="P518J no-DB healthcheck runner for committed predraw ledger verifier artifacts."
    )
    parser.add_argument("--generate", action="store_true", help="write all deterministic P518J healthcheck artifacts")
    parser.add_argument("--health", action="store_true", help="print healthcheck result JSON")
    parser.add_argument("--artifact-inventory", action="store_true", help="print source artifact inventory CSV")
    parser.add_argument("--command-matrix", action="store_true", help="print Worker handoff command matrix CSV")
    parser.add_argument("--db-invariant", action="store_true", help="print DB invariant snapshot JSON")
    parser.add_argument("--status-block", action="store_true", help="print copy-paste health status block Markdown")
    parser.add_argument("--validate", action="store_true", help="validate committed P518J artifacts by byte equality")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    rendered = render_artifacts()

    if args.generate:
        write_artifacts(rendered)
        for path in rendered:
            print(f"[p518j-healthcheck] wrote {_artifact_label(path)}")

    if args.health:
        print(rendered[HEALTH_PATH], end="")

    if args.artifact_inventory:
        print(rendered[ARTIFACT_INVENTORY_PATH], end="")

    if args.command_matrix:
        print(rendered[COMMAND_MATRIX_PATH], end="")

    if args.db_invariant:
        print(rendered[DB_INVARIANT_PATH], end="")

    if args.status_block:
        print(rendered[STATUS_BLOCK_PATH], end="")

    if args.validate:
        ok, mismatches = validate_artifacts(rendered)
        if ok:
            print("[p518j-healthcheck] validation_status=PASS")
        else:
            print("[p518j-healthcheck] validation_status=FAIL", file=sys.stderr)
            for mismatch in mismatches:
                print(f"[p518j-healthcheck] {mismatch}", file=sys.stderr)
            return 1

    if not any(
        (
            args.generate,
            args.health,
            args.artifact_inventory,
            args.command_matrix,
            args.db_invariant,
            args.status_block,
            args.validate,
        )
    ):
        parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
