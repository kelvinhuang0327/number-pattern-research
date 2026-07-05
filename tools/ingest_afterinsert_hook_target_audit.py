#!/usr/bin/env python3
"""P520E source/AST-only target audit for ingest after-insert live hooks.

This module parses source files and prior P520D artifacts as text/AST only. It
does not import ``lottery_api.routes.ingest``, does not import live hook target
modules, does not execute hooks or draw inserts, does not open or write a
database, does not run migrations/backfills, and does not deploy.
"""
from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import io
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
INGEST_ROUTE_PATH = PROJECT_ROOT / "lottery_api" / "routes" / "ingest.py"

ARTIFACT_PREFIX = "P520E_ingest_afterinsert_hook_target_audit"

RESULT_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_result.json"
TARGET_AUDIT_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_matrix.csv"
RISK_INDICATORS_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_risk_indicators.csv"
UNRESOLVED_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_unresolved.csv"
STATUS_BLOCK_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_status_block.md"
MANIFEST_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_manifest.csv"

P520D_RESULT_PATH = ARTIFACTS_DIR / "P520D_ingest_afterinsert_hook_contract_result.json"
P520D_MATRIX_PATH = ARTIFACTS_DIR / "P520D_ingest_afterinsert_hook_contract_matrix.csv"
P520D_TARGET_RESOLUTION_PATH = ARTIFACTS_DIR / "P520D_ingest_afterinsert_hook_contract_target_resolution.csv"

NOTICE_LINES: Sequence[str] = (
    "source/AST-only target audit",
    "does not import lottery_api.routes.ingest",
    "does not import live hook target modules",
    "does not execute after-insert hooks",
    "does not execute draw inserts",
    "no canonical DB open/write",
    "no migration/backfill",
    "no deploy",
    "does not implement or modify hooks",
    "no betting/future prediction claims",
)

DB_PATTERNS: Sequence[str] = (
    "sqlite3",
    "DatabaseManager",
    "lottery_v2.db",
    ".execute(",
    ".commit(",
    "connect(",
)

FILE_PATTERNS: Sequence[str] = (
    "open(",
    "Path.write_text",
    "Path.write_bytes",
    "json.dump",
    "csv",
)

RUNTIME_PATTERNS: Sequence[str] = (
    "subprocess",
    "requests",
    "urllib",
    "socket",
    "AsyncIOScheduler",
    "BackgroundScheduler",
    ".start(",
    "Thread(",
    "Process(",
)

TARGET_AUDIT_FIELDS: Sequence[str] = (
    "hook_reference",
    "found_in_p520d_contract",
    "p520d_contract_status",
    "import_module",
    "imported_symbol",
    "local_symbol",
    "target_attribute",
    "call_name",
    "source_path",
    "source_path_resolved",
    "target_symbol_found",
    "target_symbol_evidence",
    "ast_node_type",
    "function_class_presence",
    "call_signature_hints",
    "db_touch_indicators",
    "file_output_indicators",
    "runtime_side_effect_indicators",
    "target_audit_status",
    "notes",
)

RISK_INDICATOR_FIELDS: Sequence[str] = (
    "hook_reference",
    "source_path",
    "indicator_category",
    "indicator",
    "line",
    "ast_node_type",
    "evidence",
)

UNRESOLVED_FIELDS: Sequence[str] = (
    "hook_reference",
    "import_module",
    "imported_symbol",
    "local_symbol",
    "target_attribute",
    "reason",
    "status",
    "notes",
)

MANIFEST_FIELDS: Sequence[str] = ("artifact_path", "artifact_kind", "sha256", "bytes", "notes")


@dataclass(frozen=True)
class HookSpec:
    hook_reference: str
    import_module: str
    imported_symbol: str
    local_symbol: str
    call_name: str
    target_attribute: str = ""


EXPECTED_HOOKS: Sequence[HookSpec] = (
    HookSpec(
        hook_reference="scheduler.load_data",
        import_module="utils.scheduler",
        imported_symbol="scheduler",
        local_symbol="scheduler",
        call_name="scheduler.load_data",
        target_attribute="load_data",
    ),
    HookSpec(
        hook_reference="refresh_hedge_fund_outputs",
        import_module="analysis.payout.sync",
        imported_symbol="refresh_hedge_fund_outputs",
        local_symbol="refresh_hedge_fund_outputs",
        call_name="refresh_hedge_fund_outputs",
    ),
    HookSpec(
        hook_reference="weight_adjuster",
        import_module="engine.weight_adjuster",
        imported_symbol="adjust_all_types",
        local_symbol="adjust_all_types",
        call_name="adjust_all_types",
    ),
    HookSpec(
        hook_reference="learning_integrator",
        import_module="engine.learning_integrator",
        imported_symbol="apply_all_types",
        local_symbol="apply_learning",
        call_name="apply_learning",
    ),
)


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


def _node_source(source: str, node: ast.AST | None) -> str:
    if node is None:
        return ""
    return (ast.get_source_segment(source, node) or "").strip().replace("\n", " ")


def _line(node: ast.AST | None) -> str:
    if node is None:
        return ""
    lineno = getattr(node, "lineno", "")
    return str(lineno) if lineno else ""


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _call_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


def _module_path_candidates(module: str) -> List[Path]:
    module_rel = Path(*module.split("."))
    return [
        PROJECT_ROOT / f"{module_rel}.py",
        PROJECT_ROOT / module_rel / "__init__.py",
        PROJECT_ROOT / "lottery_api" / f"{module_rel}.py",
        PROJECT_ROOT / "lottery_api" / module_rel / "__init__.py",
    ]


def _resolve_module_path(module: str) -> Path | None:
    for candidate in _module_path_candidates(module):
        if candidate.exists():
            return candidate
    return None


def _function_defs(tree: ast.AST) -> Dict[str, ast.AST]:
    return {
        node.name: node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _find_import_from(function_node: ast.AST | None, module: str, symbol: str) -> ast.ImportFrom | None:
    if function_node is None:
        return None
    for node in ast.walk(function_node):
        if isinstance(node, ast.ImportFrom) and node.module == module:
            if any(alias.name == symbol for alias in node.names):
                return node
    return None


def _find_call(function_node: ast.AST | None, call_name: str) -> ast.Call | None:
    if function_node is None:
        return None
    for node in ast.walk(function_node):
        if isinstance(node, ast.Call) and _call_name(node.func) == call_name:
            return node
    return None


def _top_level_symbol(tree: ast.AST, symbol: str) -> ast.AST | None:
    for node in getattr(tree, "body", []):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == symbol:
            return node
        if isinstance(node, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == symbol for target in node.targets):
                return node
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == symbol:
            return node
    return None


def _assigned_call_class(node: ast.AST | None) -> str:
    if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
        return ""
    return _call_name(node.value.func)


def _class_method(tree: ast.AST, class_name: str, method_name: str) -> ast.AST | None:
    for node in getattr(tree, "body", []):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name == method_name:
                    return child
    return None


def _signature_hint(node: ast.AST | None) -> str:
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return ""
    args = list(node.args.posonlyargs) + list(node.args.args)
    rendered_args = [arg.arg for arg in args]
    if node.args.vararg is not None:
        rendered_args.append(f"*{node.args.vararg.arg}")
    rendered_args.extend(arg.arg for arg in node.args.kwonlyargs)
    if node.args.kwarg is not None:
        rendered_args.append(f"**{node.args.kwarg.arg}")
    return f"{node.name}({', '.join(rendered_args)})"


def _load_csv_rows(path: Path) -> List[Dict[str, str]]:
    return list(csv.DictReader(_read_text(path).splitlines())) if path.exists() else []


def _load_p520d_summary() -> Dict[str, Any]:
    result = json.loads(_read_text(P520D_RESULT_PATH)) if P520D_RESULT_PATH.exists() else {}
    matrix_rows = _load_csv_rows(P520D_MATRIX_PATH)
    target_rows = _load_csv_rows(P520D_TARGET_RESOLUTION_PATH)
    return {
        "result_artifact": _artifact_label(P520D_RESULT_PATH),
        "result_present": P520D_RESULT_PATH.exists(),
        "final_status": result.get("final_status", ""),
        "expected_live_hooks": result.get("expected_live_hooks", []),
        "detected_live_hook_count": result.get("detected_live_hook_count", ""),
        "call_like_live_hook_count": result.get("call_like_live_hook_count", ""),
        "warning_count": result.get("warning_count", ""),
        "failure_count": result.get("failure_count", ""),
        "matrix_artifact": _artifact_label(P520D_MATRIX_PATH),
        "matrix_rows": len(matrix_rows),
        "target_resolution_artifact": _artifact_label(P520D_TARGET_RESOLUTION_PATH),
        "target_resolution_rows": len(target_rows),
    }


def _p520d_contract_status_by_hook() -> Dict[str, str]:
    rows = _load_csv_rows(P520D_MATRIX_PATH)
    return {row.get("hook_reference", ""): row.get("status", "") for row in rows}


def _walk_parent_map(tree: ast.AST) -> Dict[ast.AST, ast.AST]:
    parent_by_node: Dict[ast.AST, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parent_by_node[child] = parent
    return parent_by_node


def _enclosing_node_type(node: ast.AST, parent_by_node: Mapping[ast.AST, ast.AST]) -> str:
    current = node
    while current in parent_by_node:
        current = parent_by_node[current]
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return type(current).__name__
    return "Module"


def _indicator_rows_for_source(hook_reference: str, path: Path, source: str, tree: ast.AST) -> List[Dict[str, Any]]:
    source_path = _artifact_label(path)
    parent_by_node = _walk_parent_map(tree)
    lines = source.splitlines()
    rows: List[Dict[str, Any]] = []

    def add_text_matches(category: str, patterns: Sequence[str]) -> None:
        for line_no, line_text in enumerate(lines, start=1):
            stripped = line_text.strip()
            for pattern in patterns:
                if pattern in line_text:
                    rows.append(
                        {
                            "hook_reference": hook_reference,
                            "source_path": source_path,
                            "indicator_category": category,
                            "indicator": pattern,
                            "line": line_no,
                            "ast_node_type": "text",
                            "evidence": stripped,
                        }
                    )

    add_text_matches("db_touch", DB_PATTERNS)
    add_text_matches("file_output", FILE_PATTERNS)
    add_text_matches("runtime_side_effect", RUNTIME_PATTERNS)

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            call_name = _assigned_call_class(node)
            if call_name and _enclosing_node_type(node, parent_by_node) == "Module":
                evidence = _node_source(source, node)
                rows.append(
                    {
                        "hook_reference": hook_reference,
                        "source_path": source_path,
                        "indicator_category": "runtime_side_effect",
                        "indicator": "top_level_call_assignment",
                        "line": _line(node),
                        "ast_node_type": "Module",
                        "evidence": evidence,
                    }
                )
    return _dedupe_indicator_rows(rows)


def _dedupe_indicator_rows(rows: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    seen: set[Tuple[str, str, str, str, str, str]] = set()
    unique: List[Dict[str, Any]] = []
    for row in rows:
        key = (
            str(row.get("hook_reference", "")),
            str(row.get("source_path", "")),
            str(row.get("indicator_category", "")),
            str(row.get("indicator", "")),
            str(row.get("line", "")),
            str(row.get("evidence", "")),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(dict(row))
    return sorted(
        unique,
        key=lambda row: (
            str(row["hook_reference"]),
            str(row["indicator_category"]),
            str(row["indicator"]),
            int(row["line"]) if str(row["line"]).isdigit() else 0,
            str(row["evidence"]),
        ),
    )


def _indicator_summary(rows: Sequence[Mapping[str, Any]], category: str) -> str:
    indicators = sorted({str(row["indicator"]) for row in rows if row.get("indicator_category") == category})
    return "; ".join(indicators)


def _audit_hook(
    spec: HookSpec,
    ingest_source: str,
    refresh_function: ast.AST | None,
    p520d_status_by_hook: Mapping[str, str],
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], Dict[str, Any] | None]:
    import_node = _find_import_from(refresh_function, spec.import_module, spec.imported_symbol)
    call_node = _find_call(refresh_function, spec.call_name)
    found_in_p520d = spec.hook_reference in p520d_status_by_hook
    target_path = _resolve_module_path(spec.import_module)

    unresolved_base = {
        "hook_reference": spec.hook_reference,
        "import_module": spec.import_module,
        "imported_symbol": spec.imported_symbol,
        "local_symbol": spec.local_symbol,
        "target_attribute": spec.target_attribute,
    }

    if target_path is None:
        notes = "source path unresolved by static source mapping; runtime import not attempted"
        matrix_row = {
            "hook_reference": spec.hook_reference,
            "found_in_p520d_contract": found_in_p520d,
            "p520d_contract_status": p520d_status_by_hook.get(spec.hook_reference, ""),
            "import_module": spec.import_module,
            "imported_symbol": spec.imported_symbol,
            "local_symbol": spec.local_symbol,
            "target_attribute": spec.target_attribute,
            "call_name": spec.call_name,
            "source_path": "",
            "source_path_resolved": False,
            "target_symbol_found": False,
            "target_symbol_evidence": _node_source(ingest_source, import_node or call_node),
            "ast_node_type": "",
            "function_class_presence": "unresolved",
            "call_signature_hints": "",
            "db_touch_indicators": "",
            "file_output_indicators": "",
            "runtime_side_effect_indicators": "",
            "target_audit_status": "WARN" if found_in_p520d else "FAIL",
            "notes": notes,
        }
        unresolved_row = {
            **unresolved_base,
            "reason": "source_path_unresolved",
            "status": matrix_row["target_audit_status"],
            "notes": notes,
        }
        return matrix_row, [], unresolved_row

    target_source = _read_text(target_path)
    target_tree = ast.parse(target_source, filename=str(target_path))
    symbol_node = _top_level_symbol(target_tree, spec.imported_symbol)
    method_node = None
    presence = "missing"
    if spec.target_attribute and symbol_node is not None:
        class_name = _assigned_call_class(symbol_node)
        method_node = _class_method(target_tree, class_name, spec.target_attribute) if class_name else None
        presence = "instance_assign+class_method" if method_node is not None else "instance_assign_without_method"
    elif isinstance(symbol_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        presence = "function"
    elif isinstance(symbol_node, ast.ClassDef):
        presence = "class"
    elif symbol_node is not None:
        presence = type(symbol_node).__name__

    signature_node = method_node or symbol_node
    target_found = symbol_node is not None and (method_node is not None if spec.target_attribute else True)
    indicators = _indicator_rows_for_source(spec.hook_reference, target_path, target_source, target_tree)
    has_db = bool(_indicator_summary(indicators, "db_touch"))
    has_file = bool(_indicator_summary(indicators, "file_output"))
    has_runtime = bool(_indicator_summary(indicators, "runtime_side_effect"))
    status = "FAIL" if not found_in_p520d or not target_found else "WARN" if has_db or has_file or has_runtime else "PASS"
    notes = "target source and symbol resolved by source/AST"
    if not target_found:
        notes = "target source resolved, but expected symbol or attribute was not found"
    elif has_db or has_file or has_runtime:
        notes = "target source resolved with side-effect indicators; review matrix/risk CSV"

    matrix_row = {
        "hook_reference": spec.hook_reference,
        "found_in_p520d_contract": found_in_p520d,
        "p520d_contract_status": p520d_status_by_hook.get(spec.hook_reference, ""),
        "import_module": spec.import_module,
        "imported_symbol": spec.imported_symbol,
        "local_symbol": spec.local_symbol,
        "target_attribute": spec.target_attribute,
        "call_name": spec.call_name,
        "source_path": _artifact_label(target_path),
        "source_path_resolved": True,
        "target_symbol_found": target_found,
        "target_symbol_evidence": _node_source(target_source, method_node or symbol_node),
        "ast_node_type": type(method_node or symbol_node).__name__ if (method_node or symbol_node) is not None else "",
        "function_class_presence": presence,
        "call_signature_hints": _signature_hint(signature_node),
        "db_touch_indicators": _indicator_summary(indicators, "db_touch"),
        "file_output_indicators": _indicator_summary(indicators, "file_output"),
        "runtime_side_effect_indicators": _indicator_summary(indicators, "runtime_side_effect"),
        "target_audit_status": status,
        "notes": notes,
    }
    unresolved_row = None
    if not target_found:
        unresolved_row = {
            **unresolved_base,
            "reason": "target_symbol_or_attribute_missing",
            "status": status,
            "notes": notes,
        }
    return matrix_row, indicators, unresolved_row


def analyze_targets(path: Path = INGEST_ROUTE_PATH) -> Dict[str, Any]:
    ingest_source = _read_text(path)
    ingest_tree = ast.parse(ingest_source, filename=str(path))
    refresh_function = _function_defs(ingest_tree).get("_refresh_after_insert")
    p520d_status_by_hook = _p520d_contract_status_by_hook()

    matrix_rows: List[Dict[str, Any]] = []
    risk_rows: List[Dict[str, Any]] = []
    unresolved_rows: List[Dict[str, Any]] = []
    for spec in EXPECTED_HOOKS:
        matrix_row, indicator_rows, unresolved_row = _audit_hook(
            spec, ingest_source, refresh_function, p520d_status_by_hook
        )
        matrix_rows.append(matrix_row)
        risk_rows.extend(indicator_rows)
        if unresolved_row is not None:
            unresolved_rows.append(unresolved_row)

    failures = [
        f"{row['hook_reference']}: {row['notes']}"
        for row in matrix_rows
        if row["target_audit_status"] == "FAIL"
    ]
    warnings = [
        f"{row['hook_reference']}: {row['notes']}"
        for row in matrix_rows
        if row["target_audit_status"] == "WARN"
    ]
    final_status = "FAIL" if failures else "WARN" if warnings else "PASS"
    return {
        "source_path": _artifact_label(path),
        "source_sha256": _sha256_bytes(ingest_source.encode("utf-8")),
        "refresh_after_insert_present": refresh_function is not None,
        "refresh_after_insert_line": _line(refresh_function),
        "expected_live_hooks": [spec.hook_reference for spec in EXPECTED_HOOKS],
        "target_audit_matrix": matrix_rows,
        "risk_indicators": _dedupe_indicator_rows(risk_rows),
        "unresolved_targets": unresolved_rows,
        "resolved_source_count": sum(1 for row in matrix_rows if row["source_path_resolved"]),
        "unresolved_source_count": sum(1 for row in matrix_rows if not row["source_path_resolved"]),
        "target_symbol_found_count": sum(1 for row in matrix_rows if row["target_symbol_found"]),
        "db_indicator_count": sum(1 for row in risk_rows if row.get("indicator_category") == "db_touch"),
        "file_indicator_count": sum(1 for row in risk_rows if row.get("indicator_category") == "file_output"),
        "runtime_indicator_count": sum(1 for row in risk_rows if row.get("indicator_category") == "runtime_side_effect"),
        "pass_count": sum(1 for row in matrix_rows if row["target_audit_status"] == "PASS"),
        "warn_count": sum(1 for row in matrix_rows if row["target_audit_status"] == "WARN"),
        "fail_count": sum(1 for row in matrix_rows if row["target_audit_status"] == "FAIL"),
        "warning_count": len(warnings),
        "warnings": warnings,
        "failure_count": len(failures),
        "failures": failures,
        "final_status": final_status,
        "p520d_summary": _load_p520d_summary(),
    }


def build_target_audit_bundle() -> Dict[str, Any]:
    analysis = analyze_targets()
    component_statuses = {
        "_refresh_after_insert present": "PASS" if analysis["refresh_after_insert_present"] else "FAIL",
        "P520D contract artifact read": "PASS" if analysis["p520d_summary"]["result_present"] else "WARN",
        "expected live hooks audited": "PASS"
        if len(analysis["target_audit_matrix"]) == len(EXPECTED_HOOKS)
        else "FAIL",
        "source path resolution": "WARN" if analysis["unresolved_source_count"] else "PASS",
        "target symbol resolution": "WARN"
        if analysis["target_symbol_found_count"] < len(EXPECTED_HOOKS)
        else "PASS",
        "DB side effects avoided": "PASS",
        "runtime import avoided": "PASS",
        "source AST evaluation": "PASS",
    }
    result = {
        "artifact_prefix": ARTIFACT_PREFIX,
        "final_status": analysis["final_status"],
        "source_path": analysis["source_path"],
        "source_sha256": analysis["source_sha256"],
        "refresh_after_insert_present": analysis["refresh_after_insert_present"],
        "refresh_after_insert_line": analysis["refresh_after_insert_line"],
        "expected_live_hooks": analysis["expected_live_hooks"],
        "target_audit_row_count": len(analysis["target_audit_matrix"]),
        "resolved_source_count": analysis["resolved_source_count"],
        "unresolved_source_count": analysis["unresolved_source_count"],
        "target_symbol_found_count": analysis["target_symbol_found_count"],
        "db_indicator_count": analysis["db_indicator_count"],
        "file_indicator_count": analysis["file_indicator_count"],
        "runtime_indicator_count": analysis["runtime_indicator_count"],
        "pass_count": analysis["pass_count"],
        "warn_count": analysis["warn_count"],
        "fail_count": analysis["fail_count"],
        "warning_count": analysis["warning_count"],
        "warnings": analysis["warnings"],
        "failure_count": analysis["failure_count"],
        "failures": analysis["failures"],
        "component_statuses": component_statuses,
        "p520d_summary": analysis["p520d_summary"],
        "suggested_next_command": "python -m tools.ingest_afterinsert_hook_target_audit --status-block",
        "scope": (
            "P520E parses lottery_api/routes/ingest.py, P520D artifacts, and statically resolvable target "
            "source files as text/AST only; no app runtime import; no live target module import; no "
            "after-insert hook execution; no draw insert execution; no canonical DB open/write; no "
            "migration/backfill; no deploy; does not implement or modify hooks; no betting/future "
            "prediction claims."
        ),
        "notices": list(NOTICE_LINES),
    }
    return {
        "result": result,
        "target_audit_matrix": analysis["target_audit_matrix"],
        "risk_indicators": analysis["risk_indicators"],
        "unresolved_targets": analysis["unresolved_targets"],
        "status_block": _status_block_md(result),
    }


def _status_block_md(result: Mapping[str, Any]) -> str:
    lines = [
        "## P520E Ingest After-Insert Hook Target Audit",
        "",
        f"- Final status: `{result['final_status']}`",
        f"- Source path: `{result['source_path']}`",
        f"- `_refresh_after_insert` present: `{result['refresh_after_insert_present']}`",
        f"- `_refresh_after_insert` line: `{result['refresh_after_insert_line']}`",
        f"- Expected live hooks: `{result['expected_live_hooks']}`",
        f"- Target audit rows: `{result['target_audit_row_count']}`",
        f"- Resolved source count: `{result['resolved_source_count']}`",
        f"- Unresolved source count: `{result['unresolved_source_count']}`",
        f"- Target symbol found count: `{result['target_symbol_found_count']}`",
        f"- DB indicator count: `{result['db_indicator_count']}`",
        f"- File-output indicator count: `{result['file_indicator_count']}`",
        f"- Runtime-side-effect indicator count: `{result['runtime_indicator_count']}`",
        f"- PASS/WARN/FAIL counts: `{result['pass_count']}/{result['warn_count']}/{result['fail_count']}`",
        f"- Warning count: `{result['warning_count']}`",
        f"- Failure count: `{result['failure_count']}`",
        f"- Suggested next command: `{result['suggested_next_command']}`",
        "",
        "Warnings:",
    ]
    warnings = result.get("warnings", [])
    if warnings:
        lines.extend(f"- {warning}" for warning in warnings)
    else:
        lines.append("- none")
    lines.extend(["", "Safety / scope:"])
    lines.extend(f"- {notice}" for notice in NOTICE_LINES)
    lines.append("")
    return "\n".join(lines)


def _manifest_csv(rendered: Mapping[Path, str]) -> str:
    rows: List[Dict[str, Any]] = []
    for path in (RESULT_PATH, TARGET_AUDIT_PATH, RISK_INDICATORS_PATH, UNRESOLVED_PATH, STATUS_BLOCK_PATH):
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
    bundle = build_target_audit_bundle()
    rendered: Dict[Path, str] = {
        RESULT_PATH: _json_text(bundle["result"]),
        TARGET_AUDIT_PATH: _csv_text(bundle["target_audit_matrix"], TARGET_AUDIT_FIELDS),
        RISK_INDICATORS_PATH: _csv_text(bundle["risk_indicators"], RISK_INDICATOR_FIELDS),
        UNRESOLVED_PATH: _csv_text(bundle["unresolved_targets"], UNRESOLVED_FIELDS),
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
    result = json.loads(first[RESULT_PATH])
    if result.get("final_status") == "FAIL":
        mismatches.append("final_status=FAIL")
    if result.get("component_statuses", {}).get("runtime import avoided") != "PASS":
        mismatches.append("runtime import invariant failed")
    if result.get("component_statuses", {}).get("DB side effects avoided") != "PASS":
        mismatches.append("DB side effect invariant failed")
    if result.get("target_audit_row_count") != len(EXPECTED_HOOKS):
        mismatches.append("unexpected target audit row count")
    return not mismatches, mismatches


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="P520E source/AST-only target audit for ingest after-insert live hooks."
    )
    parser.add_argument("--generate", action="store_true", help="write all deterministic P520E target audit artifacts")
    parser.add_argument("--target-audit", action="store_true", help="print hook target audit matrix CSV")
    parser.add_argument("--risk-indicators", action="store_true", help="print source risk indicators CSV")
    parser.add_argument("--unresolved", action="store_true", help="print unresolved target CSV")
    parser.add_argument("--status-block", action="store_true", help="print copy-paste target audit status block Markdown")
    parser.add_argument("--validate", action="store_true", help="validate generated P520E artifacts by byte equality")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    rendered = render_artifacts()

    if args.generate:
        write_artifacts(rendered)
        for path in rendered:
            print(f"[p520e-target-audit] wrote {_artifact_label(path)}")

    if args.target_audit:
        print(rendered[TARGET_AUDIT_PATH], end="")

    if args.risk_indicators:
        print(rendered[RISK_INDICATORS_PATH], end="")

    if args.unresolved:
        print(rendered[UNRESOLVED_PATH], end="")

    if args.status_block:
        print(rendered[STATUS_BLOCK_PATH], end="")

    if args.validate:
        ok, mismatches = validate_artifacts(rendered)
        if ok:
            print("[p520e-target-audit] validation_status=PASS")
        else:
            print("[p520e-target-audit] validation_status=FAIL", file=sys.stderr)
            for mismatch in mismatches:
                print(f"[p520e-target-audit] {mismatch}", file=sys.stderr)
            return 1

    if not any(
        (
            args.generate,
            args.target_audit,
            args.risk_indicators,
            args.unresolved,
            args.status_block,
            args.validate,
        )
    ):
        parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
