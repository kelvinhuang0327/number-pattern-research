#!/usr/bin/env python3
"""
P518I compact no-DB status layer for predraw ledger verifier acceptance.

This module reads committed P518H acceptance artifacts only. It does not execute
the verifier, smoke, edge, or acceptance CLIs; does not open or write the
canonical DB; does not run migrations/backfills; does not deploy; is not
production release approval; and makes no betting or future prediction claims.
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

SOURCE_PREFIX = "P518H_predraw_ledger_verify_acceptance"
ARTIFACT_PREFIX = "P518I_predraw_ledger_verify_status"

P518H_DECISION_PATH = ARTIFACTS_DIR / f"{SOURCE_PREFIX}_decision.json"
P518H_CASE_SUMMARY_PATH = ARTIFACTS_DIR / f"{SOURCE_PREFIX}_case_summary.csv"
P518H_FAILURE_MATRIX_PATH = ARTIFACTS_DIR / f"{SOURCE_PREFIX}_failure_matrix.csv"
P518H_DB_INVARIANT_PATH = ARTIFACTS_DIR / f"{SOURCE_PREFIX}_db_invariant.json"
P518H_REPORT_PATH = ARTIFACTS_DIR / f"{SOURCE_PREFIX}_report.md"
P518H_MANIFEST_PATH = ARTIFACTS_DIR / f"{SOURCE_PREFIX}_manifest.csv"

STATUS_SUMMARY_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_summary.json"
BADGES_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_badges.json"
STATUS_BLOCK_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_block.md"
QUERY_SUMMARY_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_query_summary.json"
REPORT_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_report.md"
MANIFEST_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_manifest.csv"

SOURCE_ARTIFACTS = (
    P518H_DECISION_PATH,
    P518H_CASE_SUMMARY_PATH,
    P518H_FAILURE_MATRIX_PATH,
    P518H_DB_INVARIANT_PATH,
    P518H_REPORT_PATH,
    P518H_MANIFEST_PATH,
)

NOTICE_LINES = (
    "no canonical DB open/write",
    "no migration/backfill",
    "no deploy",
    "synthetic fixture evidence only",
    "not production release approval",
    "no betting/future prediction claims",
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


def _load_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _source_inventory() -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for path in SOURCE_ARTIFACTS:
        if path.exists():
            data = path.read_bytes()
            rows.append(
                {
                    "path": _artifact_label(path),
                    "exists": True,
                    "sha256": _sha256_bytes(data),
                    "bytes": len(data),
                }
            )
        else:
            rows.append({"path": _artifact_label(path), "exists": False, "sha256": "", "bytes": 0})
    return rows


def _source_manifest_checks(manifest_rows: Sequence[Mapping[str, str]]) -> List[Dict[str, Any]]:
    checks: List[Dict[str, Any]] = []
    for row in manifest_rows:
        relpath = row.get("artifact_path", "")
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
    return checks


def _count_cases(case_rows: Sequence[Mapping[str, str]], source: str) -> Dict[str, Any]:
    rows = [row for row in case_rows if row.get("source") == source]
    return {
        "source": source,
        "total": len(rows),
        "passed": sum(1 for row in rows if row.get("status") == "PASS"),
        "failed": sum(1 for row in rows if row.get("status") != "PASS"),
        "status": "PASS" if rows and all(row.get("status") == "PASS" for row in rows) else "FAIL",
    }


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


def _status_label(status: str) -> str:
    if status == "PASS":
        return "passing"
    if status == "WARN":
        return "warning"
    return "failing"


def build_status_bundle() -> Dict[str, Any]:
    missing_sources = [_artifact_label(path) for path in SOURCE_ARTIFACTS if not path.exists()]
    if missing_sources:
        decision: Dict[str, Any] = {}
        case_rows: List[Dict[str, str]] = []
        failure_rows: List[Dict[str, str]] = []
        db_invariant: Dict[str, Any] = {}
        manifest_rows: List[Dict[str, str]] = []
        report_text = ""
    else:
        decision = _load_json(P518H_DECISION_PATH)
        case_rows = _load_csv(P518H_CASE_SUMMARY_PATH)
        failure_rows = _load_csv(P518H_FAILURE_MATRIX_PATH)
        db_invariant = _load_json(P518H_DB_INVARIANT_PATH)
        manifest_rows = _load_csv(P518H_MANIFEST_PATH)
        report_text = _read_text(P518H_REPORT_PATH)

    smoke_cases = _count_cases(case_rows, "P518F_smoke")
    edge_cases = _count_cases(case_rows, "P518G_edge_matrix")
    failed_case_rows = [row for row in case_rows if row.get("status") != "PASS"]
    blocking_failures = [row for row in failure_rows if row.get("severity") == "blocking" and row.get("status") != "PASS"]
    manifest_checks = _source_manifest_checks(manifest_rows) if manifest_rows else []
    manifest_failures = [check for check in manifest_checks if check.get("status") != "PASS"]
    source_inventory = _source_inventory()
    missing_artifacts = list(decision.get("case_summary", {}).get("missing_artifacts", [])) if decision else []

    acceptance_status = str(decision.get("final_status", "FAIL"))
    db_invariant_status = str(db_invariant.get("status", "FAIL"))
    canonical_refusal_status = str(
        decision.get("canonical_db_refusal_evidence", {}).get("status", "FAIL")
    )
    p518h_report_notice_status = "PASS" if _required_notices_present(decision, db_invariant, report_text) else "FAIL"
    warning_items: List[str] = []
    if not manifest_rows and not missing_sources:
        warning_items.append("P518H manifest had no rows")

    hard_failures = [
        bool(missing_sources),
        acceptance_status != "PASS",
        smoke_cases["status"] != "PASS",
        edge_cases["status"] != "PASS",
        db_invariant_status != "PASS",
        canonical_refusal_status != "PASS",
        bool(failed_case_rows),
        bool(blocking_failures),
        bool(missing_artifacts),
        bool(manifest_failures),
        p518h_report_notice_status != "PASS",
    ]
    final_compact_status = "FAIL" if any(hard_failures) else "WARN" if warning_items else "PASS"

    failed_or_missing_count = len(failed_case_rows) + len(missing_sources) + len(missing_artifacts)
    status_summary = {
        "artifact_prefix": ARTIFACT_PREFIX,
        "source_acceptance_artifact_prefix": SOURCE_PREFIX,
        "source_artifacts": source_inventory,
        "acceptance_decision": {
            "final_status": acceptance_status,
            "case_summary": decision.get("case_summary", {}),
        },
        "smoke_cases": smoke_cases,
        "edge_cases": edge_cases,
        "db_invariant": {
            "status": db_invariant_status,
            "checks": db_invariant.get("checks", []),
        },
        "canonical_db_refusal": {
            "status": canonical_refusal_status,
            "evidence": decision.get("canonical_db_refusal_evidence", {}),
        },
        "canonical_db_refusal_status": canonical_refusal_status,
        "canonical_db_open_write_status": "PASS" if db_invariant_status == "PASS" else "FAIL",
        "failed_missing_case_count": failed_or_missing_count,
        "failed_cases": failed_case_rows,
        "missing_required_source_artifacts": missing_sources,
        "missing_case_artifacts": missing_artifacts,
        "warning_count": len(warning_items),
        "warnings": warning_items,
        "source_manifest_status": "PASS" if not manifest_failures and manifest_checks else "FAIL",
        "source_manifest_checks": manifest_checks,
        "required_notice_status": p518h_report_notice_status,
        "final_compact_status": final_compact_status,
        "notices": list(NOTICE_LINES),
        "scope": (
            "P518I reads committed P518H acceptance artifacts only; no verifier, smoke, edge, "
            "or acceptance CLI execution; no canonical DB open/write; no migration/backfill; "
            "no deploy; synthetic fixture evidence only; not production release approval; "
            "no betting/future prediction claims."
        ),
    }
    badges = _badges(status_summary)
    query_summary = _query_summary(status_summary)
    return {
        "status_summary": status_summary,
        "badges": badges,
        "status_block": _status_block_md(status_summary, badges),
        "query_summary": query_summary,
        "status_report": _report_md(status_summary, badges),
    }


def _badge(name: str, status: str, message: str) -> Dict[str, str]:
    return {"label": name, "status": status, "badge": _status_label(status), "message": message}


def _badges(summary: Mapping[str, Any]) -> Dict[str, Any]:
    smoke = summary["smoke_cases"]
    edge = summary["edge_cases"]
    return {
        "artifact_prefix": ARTIFACT_PREFIX,
        "badges": {
            "verifier_health": _badge(
                "verifier_health",
                summary["final_compact_status"],
                "P518H acceptance {status}; failed/missing={count}; warnings={warnings}".format(
                    status=summary["acceptance_decision"]["final_status"],
                    count=summary["failed_missing_case_count"],
                    warnings=summary["warning_count"],
                ),
            ),
            "db_invariant": _badge(
                "db_invariant",
                summary["db_invariant"]["status"],
                "no canonical DB open/write; no migration/backfill; no deploy",
            ),
            "smoke_cases": _badge(
                "smoke_cases",
                smoke["status"],
                f"{smoke['passed']}/{smoke['total']} P518F smoke cases passed",
            ),
            "edge_cases": _badge(
                "edge_cases",
                edge["status"],
                f"{edge['passed']}/{edge['total']} P518G edge cases passed",
            ),
            "canonical_db_refusal": _badge(
                "canonical_db_refusal",
                summary["canonical_db_refusal"]["status"],
                "canonical DB basename refusal evidence from P518H",
            ),
            "no_deploy": _badge(
                "no_deploy",
                "PASS" if summary["required_notice_status"] == "PASS" else "FAIL",
                "no deploy / migration / backfill; not production release approval",
            ),
        },
        "notices": list(NOTICE_LINES),
    }


def _query_summary(summary: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "artifact_prefix": ARTIFACT_PREFIX,
        "final_compact_status": summary["final_compact_status"],
        "acceptance_final_status": summary["acceptance_decision"]["final_status"],
        "smoke_total": summary["smoke_cases"]["total"],
        "smoke_passed": summary["smoke_cases"]["passed"],
        "edge_total": summary["edge_cases"]["total"],
        "edge_passed": summary["edge_cases"]["passed"],
        "db_invariant_status": summary["db_invariant"]["status"],
        "canonical_db_refusal_status": summary["canonical_db_refusal"]["status"],
        "canonical_db_open_write_status": summary["canonical_db_open_write_status"],
        "failed_missing_case_count": summary["failed_missing_case_count"],
        "warning_count": summary["warning_count"],
        "source": "committed P518H acceptance artifacts only",
        "no_canonical_db_open_write": True,
        "no_migration_backfill": True,
        "no_deploy": True,
        "synthetic_fixture_evidence_only": True,
        "not_production_release_approval": True,
        "no_betting_future_prediction_claims": True,
        "notices": list(NOTICE_LINES),
    }


def _status_block_md(summary: Mapping[str, Any], badges: Mapping[str, Any]) -> str:
    badge_rows = badges["badges"]
    lines = [
        "## P518I Predraw Ledger Verifier Status",
        "",
        f"- Final compact status: `{summary['final_compact_status']}`",
        f"- P518H acceptance decision: `{summary['acceptance_decision']['final_status']}`",
        "- Cases: P518F smoke `{passed}/{total}`; P518G edge `{edge_passed}/{edge_total}`".format(
            passed=summary["smoke_cases"]["passed"],
            total=summary["smoke_cases"]["total"],
            edge_passed=summary["edge_cases"]["passed"],
            edge_total=summary["edge_cases"]["total"],
        ),
        f"- DB invariant: `{summary['db_invariant']['status']}`",
        f"- Canonical DB refusal: `{summary['canonical_db_refusal']['status']}`",
        f"- Failed/missing case count: `{summary['failed_missing_case_count']}`",
        f"- Warning count: `{summary['warning_count']}`",
        "",
        "Badges:",
    ]
    for key in (
        "verifier_health",
        "db_invariant",
        "smoke_cases",
        "edge_cases",
        "canonical_db_refusal",
        "no_deploy",
    ):
        badge = badge_rows[key]
        lines.append(f"- `{key}`: `{badge['status']}` - {badge['message']}")
    lines.extend(["", "Safety / scope:"])
    lines.extend(f"- {notice}" for notice in NOTICE_LINES)
    lines.append("- P518I reads committed P518H acceptance artifacts only.")
    lines.append("- P518I is not production release approval.")
    lines.append("")
    return "\n".join(lines)


def _report_md(summary: Mapping[str, Any], badges: Mapping[str, Any]) -> str:
    lines = [
        "# P518I Predraw Ledger Verifier Status Report",
        "",
        "## Scope",
        "",
        "This compact status layer reads committed P518H acceptance artifacts only.",
        "It performs no canonical DB open/write, no migration/backfill, and no deploy.",
        "It uses synthetic fixture evidence only, is not production release approval, and makes no betting/future prediction claims.",
        "",
        "## Compact Status",
        "",
        f"- Final compact status: `{summary['final_compact_status']}`",
        f"- P518H acceptance decision: `{summary['acceptance_decision']['final_status']}`",
        f"- Failed/missing case count: `{summary['failed_missing_case_count']}`",
        f"- Warning count: `{summary['warning_count']}`",
        "",
        "## Case Totals",
        "",
        "| Source | Passed | Total | Status |",
        "| --- | ---: | ---: | --- |",
        "| P518F smoke | {passed} | {total} | {status} |".format(**summary["smoke_cases"]),
        "| P518G edge matrix | {passed} | {total} | {status} |".format(**summary["edge_cases"]),
        "",
        "## Badges",
        "",
        "| Badge | Status | Message |",
        "| --- | --- | --- |",
    ]
    for key, badge in badges["badges"].items():
        lines.append(f"| {key} | {badge['status']} | {badge['message']} |")
    lines.extend(
        [
            "",
            "## Source Artifact Integrity",
            "",
            f"- Source manifest status: `{summary['source_manifest_status']}`",
            f"- Required notice status: `{summary['required_notice_status']}`",
            "",
            "## Safety Notices",
            "",
        ]
    )
    lines.extend(f"- {notice}" for notice in NOTICE_LINES)
    lines.append("")
    return "\n".join(lines)


def _manifest_csv(rendered: Mapping[Path, str]) -> str:
    rows: List[Dict[str, Any]] = []
    for path in (STATUS_SUMMARY_PATH, BADGES_PATH, STATUS_BLOCK_PATH, QUERY_SUMMARY_PATH, REPORT_PATH):
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
    bundle = build_status_bundle()
    rendered: Dict[Path, str] = {
        STATUS_SUMMARY_PATH: _json_text(bundle["status_summary"]),
        BADGES_PATH: _json_text(bundle["badges"]),
        STATUS_BLOCK_PATH: bundle["status_block"],
        QUERY_SUMMARY_PATH: _json_text(bundle["query_summary"]),
        REPORT_PATH: bundle["status_report"],
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
    summary = json.loads(first[STATUS_SUMMARY_PATH])
    if summary.get("final_compact_status") == "FAIL":
        mismatches.append("final_compact_status=FAIL")
    if summary.get("required_notice_status") != "PASS":
        mismatches.append("required notices missing")
    return not mismatches, mismatches


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="P518I compact no-DB status layer for committed P518H predraw ledger verifier artifacts."
    )
    parser.add_argument("--generate", action="store_true", help="write all deterministic P518I status artifacts")
    parser.add_argument("--status", action="store_true", help="print status summary JSON")
    parser.add_argument("--badges", action="store_true", help="print badges JSON")
    parser.add_argument("--status-block", action="store_true", help="print copy-paste status block Markdown")
    parser.add_argument("--query-summary", action="store_true", help="print compact query summary JSON")
    parser.add_argument("--validate", action="store_true", help="validate committed P518I artifacts by byte equality")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    rendered = render_artifacts()

    if args.generate:
        write_artifacts(rendered)
        for path in rendered:
            print(f"[p518i-status] wrote {_artifact_label(path)}")

    if args.status:
        print(rendered[STATUS_SUMMARY_PATH], end="")

    if args.badges:
        print(rendered[BADGES_PATH], end="")

    if args.status_block:
        print(rendered[STATUS_BLOCK_PATH], end="")

    if args.query_summary:
        print(rendered[QUERY_SUMMARY_PATH], end="")

    if args.validate:
        ok, mismatches = validate_artifacts(rendered)
        if ok:
            print("[p518i-status] validation_status=PASS")
        else:
            print("[p518i-status] validation_status=FAIL", file=sys.stderr)
            for mismatch in mismatches:
                print(f"[p518i-status] {mismatch}", file=sys.stderr)
            return 1

    if not any((args.generate, args.status, args.badges, args.status_block, args.query_summary, args.validate)):
        parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
