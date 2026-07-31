#!/usr/bin/env python3
"""
P518H no-DB acceptance bundle for predraw ledger verifier evidence.

This module reads committed P518F/P518G smoke and edge artifacts only. It does
not execute the verifier, does not open or write the canonical DB, does not run
migrations or backfills, does not deploy, is not production release approval,
and makes no betting advice or future prediction claims.
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

ARTIFACT_PREFIX = "P518H_predraw_ledger_verify_acceptance"
DECISION_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_decision.json"
CASE_SUMMARY_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_case_summary.csv"
FAILURE_MATRIX_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_failure_matrix.csv"
DB_INVARIANT_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_db_invariant.json"
REPORT_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_report.md"
MANIFEST_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_manifest.csv"

SOURCE_ARTIFACTS = (
    "artifacts/P518F_predraw_ledger_verify_smoke_results.json",
    "artifacts/P518F_predraw_ledger_verify_smoke_cases.csv",
    "artifacts/P518F_predraw_ledger_verify_smoke_transcripts.json",
    "artifacts/P518F_predraw_ledger_verify_smoke_report.md",
    "artifacts/P518F_predraw_ledger_verify_smoke_manifest.csv",
    "artifacts/P518G_predraw_ledger_verify_edge_matrix_results.json",
    "artifacts/P518G_predraw_ledger_verify_edge_matrix_cases.csv",
    "artifacts/P518G_predraw_ledger_verify_edge_matrix_coverage.csv",
    "artifacts/P518G_predraw_ledger_verify_edge_matrix_transcripts.json",
    "artifacts/P518G_predraw_ledger_verify_edge_matrix_report.md",
    "artifacts/P518G_predraw_ledger_verify_edge_matrix_manifest.csv",
)

SMOKE_RESULTS_PATH = PROJECT_ROOT / "artifacts/P518F_predraw_ledger_verify_smoke_results.json"
SMOKE_TRANSCRIPTS_PATH = PROJECT_ROOT / "artifacts/P518F_predraw_ledger_verify_smoke_transcripts.json"
SMOKE_MANIFEST_PATH = PROJECT_ROOT / "artifacts/P518F_predraw_ledger_verify_smoke_manifest.csv"
EDGE_RESULTS_PATH = PROJECT_ROOT / "artifacts/P518G_predraw_ledger_verify_edge_matrix_results.json"
EDGE_MANIFEST_PATH = PROJECT_ROOT / "artifacts/P518G_predraw_ledger_verify_edge_matrix_manifest.csv"

NOTICE_LINES = (
    "no canonical DB open/write",
    "no migration/backfill",
    "no deploy",
    "synthetic fixtures only",
    "not production release approval",
    "no betting/future prediction claims",
)

CASE_FIELDS = (
    "source",
    "case_id",
    "requirement",
    "description",
    "ledger_input",
    "expected_exit",
    "actual_exit",
    "expected_signal",
    "signal_present",
    "status",
    "notes",
    "invariant_notes",
)

FAILURE_FIELDS = (
    "check_id",
    "source",
    "case_id",
    "status",
    "severity",
    "notes",
)

MANIFEST_FIELDS = ("artifact_path", "artifact_kind", "sha256", "bytes", "notes")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _artifact_label(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return path.name


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(_read_text(path))


def _json_text(data: Mapping[str, Any]) -> str:
    return json.dumps(data, indent=2, sort_keys=True) + "\n"


def _csv_text(rows: Sequence[Mapping[str, Any]], fieldnames: Sequence[str]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fieldnames})
    return buffer.getvalue()


def _source_inventory() -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for relpath in SOURCE_ARTIFACTS:
        path = PROJECT_ROOT / relpath
        if path.exists():
            data = path.read_bytes()
            rows.append(
                {
                    "path": relpath,
                    "exists": True,
                    "sha256": _sha256_bytes(data),
                    "bytes": len(data),
                }
            )
        else:
            rows.append({"path": relpath, "exists": False, "sha256": "", "bytes": 0})
    return rows


def _manifest_integrity(manifest_path: Path) -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []
    if not manifest_path.exists():
        return {"manifest_path": _artifact_label(manifest_path), "status": "FAIL", "checks": checks}

    with manifest_path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            relpath = row["artifact_path"]
            expected_sha = row.get("sha256", "")
            expected_bytes = row.get("bytes", "")
            if not expected_sha:
                checks.append(
                    {
                        "artifact_path": relpath,
                        "status": "PASS",
                        "notes": "manifest self-hash intentionally omitted",
                    }
                )
                continue
            path = PROJECT_ROOT / relpath
            if not path.exists():
                checks.append({"artifact_path": relpath, "status": "FAIL", "notes": "missing artifact"})
                continue
            data = path.read_bytes()
            actual_sha = _sha256_bytes(data)
            actual_bytes = str(len(data))
            status = "PASS" if actual_sha == expected_sha and actual_bytes == expected_bytes else "FAIL"
            checks.append(
                {
                    "artifact_path": relpath,
                    "status": status,
                    "notes": f"sha256={actual_sha}; bytes={actual_bytes}",
                }
            )
    return {
        "manifest_path": _artifact_label(manifest_path),
        "status": "PASS" if all(check["status"] == "PASS" for check in checks) else "FAIL",
        "checks": checks,
    }


def _normalize_case(source: str, case: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "source": source,
        "case_id": case.get("case_id", ""),
        "requirement": case.get("requirement", source),
        "description": case.get("description", ""),
        "ledger_input": case.get("ledger_input", ""),
        "expected_exit": case.get("expected_exit", ""),
        "actual_exit": case.get("actual_exit", ""),
        "expected_signal": case.get("expected_signal", ""),
        "signal_present": case.get("signal_present", ""),
        "status": case.get("status", ""),
        "notes": case.get("semantic_notes", ""),
        "invariant_notes": case.get("invariant_notes", "; ".join(NOTICE_LINES)),
    }


def _case_summary(smoke: Mapping[str, Any], edge: Mapping[str, Any]) -> List[Dict[str, Any]]:
    rows = [_normalize_case("P518F_smoke", case) for case in smoke.get("cases", [])]
    rows.extend(_normalize_case("P518G_edge_matrix", case) for case in edge.get("cases", []))
    return rows


def _no_db_check(source: str, evidence: Mapping[str, Any]) -> Dict[str, Any]:
    exists_stable = evidence.get("canonical_db_exists_before") == evidence.get("canonical_db_exists_after")
    ok = (
        exists_stable
        and evidence.get("canonical_db_opened") is False
        and evidence.get("canonical_db_written") is False
        and evidence.get("migration_backfill_deploy_run") is False
    )
    return {
        "source": source,
        "status": "PASS" if ok else "FAIL",
        "canonical_db_path": evidence.get("canonical_db_path", ""),
        "canonical_db_exists_before": evidence.get("canonical_db_exists_before"),
        "canonical_db_exists_after": evidence.get("canonical_db_exists_after"),
        "canonical_db_opened": evidence.get("canonical_db_opened"),
        "canonical_db_written": evidence.get("canonical_db_written"),
        "migration_backfill_deploy_run": evidence.get("migration_backfill_deploy_run"),
        "fixture_scope": evidence.get("fixture_scope", ""),
    }


def _canonical_refusal(smoke: Mapping[str, Any]) -> Dict[str, Any]:
    cases = {case.get("case_id"): case for case in smoke.get("cases", [])}
    refusal_case = cases.get("canonical_db_basename_refusal", {})
    transcript_status = "FAIL"
    transcript_signal = ""
    if SMOKE_TRANSCRIPTS_PATH.exists():
        transcripts = _load_json(SMOKE_TRANSCRIPTS_PATH).get("transcripts", [])
        for transcript in transcripts:
            if transcript.get("case_id") == "canonical_db_basename_refusal":
                combined = str(transcript.get("stdout", "")) + str(transcript.get("stderr", ""))
                transcript_signal = "REFUSED" if "REFUSED" in combined else ""
                transcript_status = "PASS" if transcript_signal else "FAIL"
                break
    case_status = "PASS" if refusal_case.get("status") == "PASS" and refusal_case.get("actual_exit") == 3 else "FAIL"
    return {
        "case_id": "canonical_db_basename_refusal",
        "case_status": case_status,
        "transcript_status": transcript_status,
        "expected_exit": refusal_case.get("expected_exit", ""),
        "actual_exit": refusal_case.get("actual_exit", ""),
        "signal": transcript_signal,
        "status": "PASS" if case_status == "PASS" and transcript_status == "PASS" else "FAIL",
    }


def _status_from_inputs(
    smoke: Mapping[str, Any],
    edge: Mapping[str, Any],
    case_rows: Sequence[Mapping[str, Any]],
    db_checks: Sequence[Mapping[str, Any]],
    manifest_checks: Sequence[Mapping[str, Any]],
    source_inventory: Sequence[Mapping[str, Any]],
    canonical_refusal: Mapping[str, Any],
) -> str:
    hard_failures: List[bool] = [
        smoke.get("overall_status") != "PASS",
        edge.get("overall_status") != "PASS",
        any(row.get("status") != "PASS" for row in case_rows),
        any(row.get("status") != "PASS" for row in db_checks),
        any(row.get("status") != "PASS" for row in manifest_checks),
        any(not row.get("exists") for row in source_inventory),
        canonical_refusal.get("status") != "PASS",
    ]
    return "FAIL" if any(hard_failures) else "PASS"


def build_acceptance() -> Dict[str, Any]:
    smoke = _load_json(SMOKE_RESULTS_PATH)
    edge = _load_json(EDGE_RESULTS_PATH)
    case_rows = _case_summary(smoke, edge)
    db_checks = (
        _no_db_check("P518F_smoke", smoke.get("no_db_evidence", {})),
        _no_db_check("P518G_edge_matrix", edge.get("no_db_evidence", {})),
        {
            "source": "P518H_acceptance",
            "status": "PASS",
            "canonical_db_path": "data/lottery_v2.db",
            "canonical_db_exists_before": "not inspected by P518H",
            "canonical_db_exists_after": "not inspected by P518H",
            "canonical_db_opened": False,
            "canonical_db_written": False,
            "migration_backfill_deploy_run": False,
            "fixture_scope": "committed P518F/P518G artifacts only",
        },
    )
    manifest_checks = (
        _manifest_integrity(SMOKE_MANIFEST_PATH),
        _manifest_integrity(EDGE_MANIFEST_PATH),
    )
    source_inventory = _source_inventory()
    canonical_refusal = _canonical_refusal(smoke)
    failed_cases = [row for row in case_rows if row.get("status") != "PASS"]
    missing_artifacts = [row["path"] for row in source_inventory if not row.get("exists")]
    final_status = _status_from_inputs(
        smoke,
        edge,
        case_rows,
        db_checks,
        manifest_checks,
        source_inventory,
        canonical_refusal,
    )
    decision = {
        "artifact_prefix": ARTIFACT_PREFIX,
        "source_evidence": {
            "P518F_smoke_status": smoke.get("overall_status"),
            "P518G_edge_matrix_status": edge.get("overall_status"),
            "source_artifacts": source_inventory,
            "source_manifest_integrity": list(manifest_checks),
        },
        "case_summary": {
            "total_cases": len(case_rows),
            "passed_cases": sum(1 for row in case_rows if row.get("status") == "PASS"),
            "failed_cases": failed_cases,
            "missing_artifacts": missing_artifacts,
        },
        "db_hash_invariant_evidence": list(db_checks),
        "canonical_db_refusal_evidence": canonical_refusal,
        "final_status": final_status,
        "notices": list(NOTICE_LINES),
        "scope": (
            "P518H reads committed P518F/P518G artifacts only; no verifier execution, "
            "no canonical DB open/write, no migration/backfill, no deploy, synthetic fixtures only, "
            "not production release approval, no betting/future prediction claims."
        ),
    }
    return {
        "decision": decision,
        "case_rows": case_rows,
        "failure_rows": _failure_matrix(decision, case_rows),
        "db_invariant": _db_invariant(decision),
    }


def _failure_matrix(decision: Mapping[str, Any], case_rows: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = [
        {
            "check_id": "p518f_smoke_overall",
            "source": "P518F_smoke",
            "case_id": "",
            "status": decision["source_evidence"]["P518F_smoke_status"],
            "severity": "blocking",
            "notes": "P518F committed smoke overall status",
        },
        {
            "check_id": "p518g_edge_overall",
            "source": "P518G_edge_matrix",
            "case_id": "",
            "status": decision["source_evidence"]["P518G_edge_matrix_status"],
            "severity": "blocking",
            "notes": "P518G committed edge matrix overall status",
        },
        {
            "check_id": "canonical_db_refusal",
            "source": "P518F_smoke",
            "case_id": "canonical_db_basename_refusal",
            "status": decision["canonical_db_refusal_evidence"]["status"],
            "severity": "blocking",
            "notes": "canonical DB basename refusal evidence includes expected exit and REFUSED transcript signal",
        },
    ]
    rows.extend(
        {
            "check_id": f"case_{row['source']}_{row['case_id']}",
            "source": row["source"],
            "case_id": row["case_id"],
            "status": row["status"],
            "severity": "blocking" if row["status"] != "PASS" else "none",
            "notes": row["description"],
        }
        for row in case_rows
    )
    rows.extend(
        {
            "check_id": f"db_invariant_{row['source']}",
            "source": row["source"],
            "case_id": "no_db_invariant_evidence",
            "status": row["status"],
            "severity": "blocking" if row["status"] != "PASS" else "none",
            "notes": "no canonical DB open/write; no migration/backfill; no deploy",
        }
        for row in decision["db_hash_invariant_evidence"]
    )
    rows.extend(
        {
            "check_id": f"source_manifest_{check['manifest_path']}",
            "source": check["manifest_path"],
            "case_id": "",
            "status": check["status"],
            "severity": "blocking" if check["status"] != "PASS" else "none",
            "notes": "committed source manifest sha256/byte checks",
        }
        for check in decision["source_evidence"]["source_manifest_integrity"]
    )
    return rows


def _db_invariant(decision: Mapping[str, Any]) -> Dict[str, Any]:
    checks = decision["db_hash_invariant_evidence"]
    return {
        "artifact_prefix": ARTIFACT_PREFIX,
        "status": "PASS" if all(row.get("status") == "PASS" for row in checks) else "FAIL",
        "checks": checks,
        "notices": list(NOTICE_LINES),
        "p518h_db_access": {
            "canonical_db_opened": False,
            "canonical_db_written": False,
            "migration_backfill_deploy_run": False,
            "input_scope": "committed P518F/P518G artifacts only",
        },
    }


def _report_md(decision: Mapping[str, Any], case_rows: Sequence[Mapping[str, Any]]) -> str:
    lines = [
        "# P518H Predraw Ledger Verify Acceptance Report",
        "",
        "## Scope",
        "",
        "This acceptance bundle reads committed P518F/P518G smoke and edge artifacts only.",
        "It performs no canonical DB open/write, no migration/backfill, and no deploy.",
        "It uses synthetic fixtures only, is not production release approval, and makes no betting/future prediction claims.",
        "",
        "## Acceptance Decision",
        "",
        f"- P518F smoke status: `{decision['source_evidence']['P518F_smoke_status']}`",
        f"- P518G edge matrix status: `{decision['source_evidence']['P518G_edge_matrix_status']}`",
        f"- Canonical DB refusal evidence: `{decision['canonical_db_refusal_evidence']['status']}`",
        f"- DB invariant evidence: `{_db_invariant(decision)['status']}`",
        f"- Final status: `{decision['final_status']}`",
        "",
        "## Case Summary",
        "",
        "| Source | Case | Expected | Actual | Status |",
        "| --- | --- | ---: | ---: | --- |",
    ]
    for row in case_rows:
        lines.append(
            f"| {row['source']} | {row['case_id']} | {row['expected_exit']} | {row['actual_exit']} | {row['status']} |"
        )
    lines.extend(["", "## Missing Or Failed Cases", ""])
    failed_cases = decision["case_summary"]["failed_cases"]
    missing_artifacts = decision["case_summary"]["missing_artifacts"]
    if not failed_cases and not missing_artifacts:
        lines.append("- None")
    for case in failed_cases:
        lines.append(f"- Failed case: `{case['source']}/{case['case_id']}` status `{case['status']}`")
    for artifact in missing_artifacts:
        lines.append(f"- Missing artifact: `{artifact}`")
    lines.extend(["", "## DB Invariant Summary", ""])
    for row in decision["db_hash_invariant_evidence"]:
        lines.append(
            "- {source}: `{status}`; opened=`{opened}`; written=`{written}`; migration/backfill/deploy=`{deploy}`".format(
                source=row["source"],
                status=row["status"],
                opened=row["canonical_db_opened"],
                written=row["canonical_db_written"],
                deploy=row["migration_backfill_deploy_run"],
            )
        )
    lines.extend(["", "## Safety Notices", ""])
    lines.extend(f"- {notice}" for notice in NOTICE_LINES)
    lines.append("")
    return "\n".join(lines)


def _manifest_csv(rendered: Mapping[Path, str]) -> str:
    rows: List[Dict[str, Any]] = []
    for path in (DECISION_PATH, CASE_SUMMARY_PATH, FAILURE_MATRIX_PATH, DB_INVARIANT_PATH, REPORT_PATH):
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
    bundle = build_acceptance()
    decision = bundle["decision"]
    rendered: Dict[Path, str] = {
        DECISION_PATH: _json_text(decision),
        CASE_SUMMARY_PATH: _csv_text(bundle["case_rows"], CASE_FIELDS),
        FAILURE_MATRIX_PATH: _csv_text(bundle["failure_rows"], FAILURE_FIELDS),
        DB_INVARIANT_PATH: _json_text(bundle["db_invariant"]),
        REPORT_PATH: _report_md(decision, bundle["case_rows"]),
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
    decision = json.loads(first[DECISION_PATH])
    if decision.get("final_status") != "PASS":
        mismatches.append(f"acceptance final_status={decision.get('final_status')}")
    return not mismatches, mismatches


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "P518H no-DB acceptance bundle for committed P518F/P518G predraw ledger verifier artifacts."
        )
    )
    parser.add_argument("--generate", action="store_true", help="write all deterministic P518H acceptance artifacts")
    parser.add_argument("--decision", action="store_true", help="print the acceptance decision JSON")
    parser.add_argument("--case-summary", action="store_true", help="print the case summary CSV")
    parser.add_argument("--failure-matrix", action="store_true", help="print the failure matrix CSV")
    parser.add_argument("--db-invariant", action="store_true", help="print the DB invariant summary JSON")
    parser.add_argument("--report", action="store_true", help="print the acceptance report Markdown")
    parser.add_argument("--validate", action="store_true", help="validate committed P518H artifacts by byte equality")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    rendered = render_artifacts()

    if args.generate:
        write_artifacts(rendered)
        for path in rendered:
            print(f"[p518h-acceptance] wrote {_artifact_label(path)}")

    if args.decision:
        print(rendered[DECISION_PATH], end="")

    if args.case_summary:
        print(rendered[CASE_SUMMARY_PATH], end="")

    if args.failure_matrix:
        print(rendered[FAILURE_MATRIX_PATH], end="")

    if args.db_invariant:
        print(rendered[DB_INVARIANT_PATH], end="")

    if args.report:
        print(rendered[REPORT_PATH], end="")

    if args.validate:
        ok, mismatches = validate_artifacts(rendered)
        if ok:
            print("[p518h-acceptance] validation_status=PASS")
        else:
            print("[p518h-acceptance] validation_status=FAIL", file=sys.stderr)
            for mismatch in mismatches:
                print(f"[p518h-acceptance] {mismatch}", file=sys.stderr)
            return 1

    if not any(
        (
            args.generate,
            args.decision,
            args.case_summary,
            args.failure_matrix,
            args.db_invariant,
            args.report,
            args.validate,
        )
    ):
        parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
