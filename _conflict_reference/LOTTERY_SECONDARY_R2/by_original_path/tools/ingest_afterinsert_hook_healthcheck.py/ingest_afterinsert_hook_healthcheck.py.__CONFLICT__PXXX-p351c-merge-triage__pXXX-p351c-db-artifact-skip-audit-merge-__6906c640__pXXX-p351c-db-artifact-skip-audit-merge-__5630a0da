#!/usr/bin/env python3
"""P520C source-only healthcheck for ingest after-insert hook wiring.

This module parses ``lottery_api/routes/ingest.py`` as text/AST only. It does
not import the app route module, does not execute draw inserts, does not open or
write a database, does not run migrations/backfills, and does not deploy.
"""
from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import io
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
INGEST_ROUTE_PATH = PROJECT_ROOT / "lottery_api" / "routes" / "ingest.py"

ARTIFACT_PREFIX = "P520C_ingest_afterinsert_hook_healthcheck"

HEALTH_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_result.json"
HOOK_INVENTORY_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_hook_inventory.csv"
DEAD_HOOKS_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_dead_hooks.csv"
COMPLETION_SUMMARY_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_completion_summary.json"
STATUS_BLOCK_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_status_block.md"
MANIFEST_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_manifest.csv"

EXPECTED_LIVE_HOOKS: Sequence[str] = (
    "scheduler.load_data",
    "refresh_hedge_fund_outputs",
    "weight_adjuster",
    "learning_integrator",
)

REMOVED_DEAD_HOOKS: Sequence[str] = (
    "_schedule_after_insert",
    "snapshot_scheduler",
    "prediction_tracker",
)

NOTICE_LINES = (
    "source/AST-only healthcheck",
    "does not import lottery_api.routes.ingest",
    "does not execute draw inserts",
    "no canonical DB open/write",
    "no migration/backfill",
    "no deploy",
    "does not implement replacement scheduler/tracker",
    "no betting/future prediction claims",
)

HOOK_INVENTORY_FIELDS = (
    "hook_name",
    "expected",
    "present",
    "status",
    "line",
    "evidence_type",
    "evidence",
    "notes",
)

DEAD_HOOK_FIELDS = (
    "symbol",
    "absent_from_source_text",
    "absent_from_ast_names",
    "status",
    "notes",
)

MANIFEST_FIELDS = ("artifact_path", "artifact_kind", "sha256", "bytes", "notes")


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _json_text(data: Mapping[str, Any]) -> str:
    return json.dumps(data, indent=2, sort_keys=True) + "\n"


def _csv_text(rows: Sequence[Mapping[str, Any]], fieldnames: Sequence[str]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fieldnames})
    return buffer.getvalue()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _artifact_label(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return path.name


def _node_source(source: str, node: ast.AST) -> str:
    return ast.get_source_segment(source, node) or ""


def _function_defs(tree: ast.AST) -> Dict[str, ast.AST]:
    return {
        node.name: node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _referenced_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
            names.update(alias.name for alias in node.names)
    return names


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _call_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


def _line(node: ast.AST | None) -> str:
    if node is None:
        return ""
    lineno = getattr(node, "lineno", "")
    return str(lineno) if lineno else ""


def _find_import_from(function_node: ast.AST, module: str) -> ast.ImportFrom | None:
    for node in ast.walk(function_node):
        if isinstance(node, ast.ImportFrom) and node.module == module:
            return node
    return None


def _find_name(function_node: ast.AST, name: str) -> ast.AST | None:
    for node in ast.walk(function_node):
        if isinstance(node, ast.Name) and node.id == name:
            return node
    return None


def _find_call(function_node: ast.AST, call_name: str) -> ast.Call | None:
    for node in ast.walk(function_node):
        if isinstance(node, ast.Call) and _call_name(node.func) == call_name:
            return node
    return None


def _detect_live_hook(function_node: ast.AST | None, source: str, hook_name: str) -> Dict[str, Any]:
    if function_node is None:
        return {
            "hook_name": hook_name,
            "expected": True,
            "present": False,
            "status": "WARN",
            "line": "",
            "evidence_type": "missing_function",
            "evidence": "",
            "notes": "_refresh_after_insert is missing",
        }

    evidence_node: ast.AST | None = None
    evidence_type = ""
    evidence = ""
    notes = "expected live hook reference present"

    if hook_name == "scheduler.load_data":
        evidence_node = _find_call(function_node, "scheduler.load_data")
        evidence_type = "call"
    elif hook_name == "refresh_hedge_fund_outputs":
        evidence_node = _find_call(function_node, "refresh_hedge_fund_outputs") or _find_name(
            function_node, "refresh_hedge_fund_outputs"
        )
        evidence_type = "call_or_name"
    elif hook_name == "weight_adjuster":
        evidence_node = _find_import_from(function_node, "engine.weight_adjuster")
        evidence_type = "import_from"
    elif hook_name == "learning_integrator":
        evidence_node = _find_import_from(function_node, "engine.learning_integrator")
        evidence_type = "import_from"

    if evidence_node is not None:
        evidence = _node_source(source, evidence_node).strip().replace("\n", " ")
        return {
            "hook_name": hook_name,
            "expected": True,
            "present": True,
            "status": "PASS",
            "line": _line(evidence_node),
            "evidence_type": evidence_type,
            "evidence": evidence,
            "notes": notes,
        }

    return {
        "hook_name": hook_name,
        "expected": True,
        "present": False,
        "status": "WARN",
        "line": "",
        "evidence_type": evidence_type or "unknown",
        "evidence": "",
        "notes": "expected live hook reference missing or renamed",
    }


def _call_sites(tree: ast.AST, function_name: str) -> List[int]:
    lines: List[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == function_name:
            lineno = getattr(node, "lineno", None)
            if lineno is not None:
                lines.append(lineno)
    return sorted(lines)


def _dead_hook_rows(source: str, tree: ast.AST) -> List[Dict[str, Any]]:
    names = _referenced_names(tree)
    rows: List[Dict[str, Any]] = []
    for symbol in REMOVED_DEAD_HOOKS:
        absent_from_source = symbol not in source
        absent_from_ast = symbol not in names
        rows.append(
            {
                "symbol": symbol,
                "absent_from_source_text": absent_from_source,
                "absent_from_ast_names": absent_from_ast,
                "status": "PASS" if absent_from_source and absent_from_ast else "FAIL",
                "notes": "removed dead hook remains absent" if absent_from_source and absent_from_ast else "removed dead hook reference found",
            }
        )
    return rows


def analyze_ingest_source(path: Path = INGEST_ROUTE_PATH) -> Dict[str, Any]:
    source = _read_text(path)
    tree = ast.parse(source, filename=str(path))
    functions = _function_defs(tree)
    refresh_function = functions.get("_refresh_after_insert")
    refresh_present = refresh_function is not None
    refresh_line = getattr(refresh_function, "lineno", "") if refresh_function is not None else ""
    function_source = _node_source(source, refresh_function) if refresh_function is not None else ""

    hook_rows = [_detect_live_hook(refresh_function, source, hook) for hook in EXPECTED_LIVE_HOOKS]
    dead_rows = _dead_hook_rows(source, tree)
    missing_or_renamed = [row["hook_name"] for row in hook_rows if row["status"] != "PASS"]
    warnings = [f"expected live hook missing or renamed: {hook}" for hook in missing_or_renamed]
    failures: List[str] = []
    if not refresh_present:
        failures.append("_refresh_after_insert missing")
    failures.extend(f"removed dead hook reference found: {row['symbol']}" for row in dead_rows if row["status"] != "PASS")

    final_status = "FAIL" if failures else "WARN" if warnings else "PASS"
    call_site_lines = _call_sites(tree, "_refresh_after_insert")

    return {
        "source_path": _artifact_label(path),
        "source_sha256": _sha256_bytes(source.encode("utf-8")),
        "source_bytes": len(source.encode("utf-8")),
        "refresh_after_insert_present": refresh_present,
        "refresh_after_insert_line": refresh_line,
        "refresh_after_insert_call_site_lines": call_site_lines,
        "refresh_after_insert_source_sha256": _sha256_bytes(function_source.encode("utf-8")) if function_source else "",
        "expected_live_hooks": list(EXPECTED_LIVE_HOOKS),
        "detected_live_hook_count": sum(1 for row in hook_rows if row["present"]),
        "missing_or_renamed_live_hooks": missing_or_renamed,
        "removed_dead_hooks": list(REMOVED_DEAD_HOOKS),
        "dead_hook_absence_status": "PASS" if all(row["status"] == "PASS" for row in dead_rows) else "FAIL",
        "final_status": final_status,
        "warnings": warnings,
        "failures": failures,
        "hook_inventory": hook_rows,
        "dead_hooks": dead_rows,
        "notices": list(NOTICE_LINES),
    }


def build_healthcheck_bundle() -> Dict[str, Any]:
    analysis = analyze_ingest_source()
    component_statuses = {
        "_refresh_after_insert present": "PASS" if analysis["refresh_after_insert_present"] else "FAIL",
        "expected live hooks visible": "PASS" if not analysis["missing_or_renamed_live_hooks"] else "WARN",
        "removed dead hooks absent": analysis["dead_hook_absence_status"],
        "source AST evaluation": "PASS",
        "runtime import avoided": "PASS",
        "DB side effects avoided": "PASS",
    }
    health = {
        "artifact_prefix": ARTIFACT_PREFIX,
        "final_status": analysis["final_status"],
        "source_path": analysis["source_path"],
        "source_sha256": analysis["source_sha256"],
        "refresh_after_insert_present": analysis["refresh_after_insert_present"],
        "refresh_after_insert_line": analysis["refresh_after_insert_line"],
        "refresh_after_insert_call_site_lines": analysis["refresh_after_insert_call_site_lines"],
        "expected_live_hooks": analysis["expected_live_hooks"],
        "detected_live_hook_count": analysis["detected_live_hook_count"],
        "missing_or_renamed_live_hooks": analysis["missing_or_renamed_live_hooks"],
        "removed_dead_hooks": analysis["removed_dead_hooks"],
        "dead_hook_absence_status": analysis["dead_hook_absence_status"],
        "warning_count": len(analysis["warnings"]),
        "warnings": analysis["warnings"],
        "failure_count": len(analysis["failures"]),
        "failures": analysis["failures"],
        "component_statuses": component_statuses,
        "suggested_next_command": "python -m tools.ingest_afterinsert_hook_healthcheck --status-block",
        "scope": (
            "P520C parses lottery_api/routes/ingest.py as text/AST only; no app runtime import; "
            "no draw insert execution; no canonical DB open/write; no migration/backfill; no deploy; "
            "does not implement replacement scheduler/tracker; no betting/future prediction claims."
        ),
        "notices": list(NOTICE_LINES),
    }
    completion_summary = {
        "artifact_prefix": ARTIFACT_PREFIX,
        "completion_status": analysis["final_status"],
        "source_ast_only": True,
        "imports_lottery_api_routes_ingest": False,
        "executes_draw_insert": False,
        "opens_or_writes_db": False,
        "runs_migration_backfill_or_deploy": False,
        "implements_replacement_scheduler_or_tracker": False,
        "live_hook_references_visible": analysis["detected_live_hook_count"] == len(EXPECTED_LIVE_HOOKS),
        "removed_dead_hooks_absent": analysis["dead_hook_absence_status"] == "PASS",
        "expected_artifact_count": 6,
        "notices": list(NOTICE_LINES),
    }
    return {
        "health": health,
        "hook_inventory": analysis["hook_inventory"],
        "dead_hooks": analysis["dead_hooks"],
        "completion_summary": completion_summary,
        "status_block": _status_block_md(health),
    }


def _status_block_md(health: Mapping[str, Any]) -> str:
    lines = [
        "## P520C Ingest After-Insert Hook Healthcheck",
        "",
        f"- Final status: `{health['final_status']}`",
        f"- Source path: `{health['source_path']}`",
        f"- `_refresh_after_insert` present: `{health['refresh_after_insert_present']}`",
        f"- `_refresh_after_insert` line: `{health['refresh_after_insert_line']}`",
        f"- `_refresh_after_insert` call sites: `{health['refresh_after_insert_call_site_lines']}`",
        f"- Detected live hook count: `{health['detected_live_hook_count']}`",
        f"- Missing or renamed live hooks: `{health['missing_or_renamed_live_hooks']}`",
        f"- Dead hook absence status: `{health['dead_hook_absence_status']}`",
        f"- Warning count: `{health['warning_count']}`",
        f"- Failure count: `{health['failure_count']}`",
        f"- Suggested next command: `{health['suggested_next_command']}`",
        "",
        "Safety / scope:",
    ]
    lines.extend(f"- {notice}" for notice in NOTICE_LINES)
    lines.append("")
    return "\n".join(lines)


def _manifest_csv(rendered: Mapping[Path, str]) -> str:
    rows: List[Dict[str, Any]] = []
    for path in (HEALTH_PATH, HOOK_INVENTORY_PATH, DEAD_HOOKS_PATH, COMPLETION_SUMMARY_PATH, STATUS_BLOCK_PATH):
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
        HOOK_INVENTORY_PATH: _csv_text(bundle["hook_inventory"], HOOK_INVENTORY_FIELDS),
        DEAD_HOOKS_PATH: _csv_text(bundle["dead_hooks"], DEAD_HOOK_FIELDS),
        COMPLETION_SUMMARY_PATH: _json_text(bundle["completion_summary"]),
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
    if health.get("final_status") == "FAIL":
        mismatches.append("final_status=FAIL")
    if health.get("component_statuses", {}).get("runtime import avoided") != "PASS":
        mismatches.append("runtime import invariant failed")
    if health.get("component_statuses", {}).get("DB side effects avoided") != "PASS":
        mismatches.append("DB side effect invariant failed")
    return not mismatches, mismatches


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="P520C source/AST-only healthcheck for ingest after-insert hook wiring."
    )
    parser.add_argument("--generate", action="store_true", help="write all deterministic P520C healthcheck artifacts")
    parser.add_argument("--health", action="store_true", help="print healthcheck result JSON")
    parser.add_argument("--hook-inventory", action="store_true", help="print detected live hook inventory CSV")
    parser.add_argument("--dead-hook-check", action="store_true", help="print removed dead hook absence CSV")
    parser.add_argument("--completion-summary", action="store_true", help="print completion summary JSON")
    parser.add_argument("--status-block", action="store_true", help="print copy-paste health status block Markdown")
    parser.add_argument("--validate", action="store_true", help="validate committed P520C artifacts by byte equality")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    rendered = render_artifacts()

    if args.generate:
        write_artifacts(rendered)
        for path in rendered:
            print(f"[p520c-healthcheck] wrote {_artifact_label(path)}")

    if args.health:
        print(rendered[HEALTH_PATH], end="")

    if args.hook_inventory:
        print(rendered[HOOK_INVENTORY_PATH], end="")

    if args.dead_hook_check:
        print(rendered[DEAD_HOOKS_PATH], end="")

    if args.completion_summary:
        print(rendered[COMPLETION_SUMMARY_PATH], end="")

    if args.status_block:
        print(rendered[STATUS_BLOCK_PATH], end="")

    if args.validate:
        ok, mismatches = validate_artifacts(rendered)
        if ok:
            print("[p520c-healthcheck] validation_status=PASS")
        else:
            print("[p520c-healthcheck] validation_status=FAIL", file=sys.stderr)
            for mismatch in mismatches:
                print(f"[p520c-healthcheck] {mismatch}", file=sys.stderr)
            return 1

    if not any(
        (
            args.generate,
            args.health,
            args.hook_inventory,
            args.dead_hook_check,
            args.completion_summary,
            args.status_block,
            args.validate,
        )
    ):
        parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
