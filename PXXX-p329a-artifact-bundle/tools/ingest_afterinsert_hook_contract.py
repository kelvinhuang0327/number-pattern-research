#!/usr/bin/env python3
"""P520D source-only contract evaluator for ingest after-insert live hooks.

This module parses source files as text/AST only. It does not import
``lottery_api.routes.ingest``, execute after-insert hooks, open or write a
database, run migrations/backfills, deploy, or implement replacement
scheduler/tracker behavior.
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

ARTIFACT_PREFIX = "P520D_ingest_afterinsert_hook_contract"

RESULT_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_result.json"
CONTRACT_MATRIX_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_matrix.csv"
TARGET_RESOLUTION_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_target_resolution.csv"
DEAD_HOOKS_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_dead_hooks.csv"
STATUS_BLOCK_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_status_block.md"
MANIFEST_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_manifest.csv"

P520C_RESULT_PATH = ARTIFACTS_DIR / "P520C_ingest_afterinsert_hook_healthcheck_result.json"
P520C_HOOK_INVENTORY_PATH = ARTIFACTS_DIR / "P520C_ingest_afterinsert_hook_healthcheck_hook_inventory.csv"
P520C_DEAD_HOOKS_PATH = ARTIFACTS_DIR / "P520C_ingest_afterinsert_hook_healthcheck_dead_hooks.csv"

REMOVED_DEAD_HOOKS: Sequence[str] = (
    "_schedule_after_insert",
    "snapshot_scheduler",
    "prediction_tracker",
)

REMOVED_MISSING_TARGET_HOOKS: Sequence[str] = (
    "refresh_hedge_fund_outputs",
    "weight_adjuster",
    "learning_integrator",
)

NOTICE_LINES: Sequence[str] = (
    "source/AST-only contract evaluation",
    "does not import lottery_api.routes.ingest",
    "does not execute after-insert hooks",
    "does not execute draw inserts",
    "historical missing-target hooks are removed from active and disabled surface",
    "no canonical DB open/write",
    "no migration/backfill",
    "no deploy",
    "does not implement replacement scheduler/tracker",
    "no betting/future prediction claims",
)

CONTRACT_FIELDS: Sequence[str] = (
    "hook_reference",
    "expected_live",
    "refresh_after_insert_present",
    "reference_found",
    "source_line",
    "ast_node_type",
    "reference_evidence",
    "call_like_in_refresh_after_insert",
    "call_line",
    "call_evidence",
    "imported_or_assigned_symbol",
    "symbol_evidence",
    "static_target_resolution",
    "status",
    "notes",
)

TARGET_RESOLUTION_FIELDS: Sequence[str] = (
    "hook_reference",
    "import_module",
    "imported_symbol",
    "local_symbol",
    "target_attribute",
    "target_path",
    "target_path_exists",
    "target_symbol_found",
    "target_symbol_line",
    "target_attribute_found",
    "target_attribute_line",
    "static_target_resolution",
    "notes",
)

DEAD_HOOK_FIELDS: Sequence[str] = (
    "symbol",
    "absent_from_source_text",
    "absent_from_ast_names",
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
            names.update(alias.asname for alias in node.names if alias.asname)
    return names


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _call_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


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


def _find_assignment(function_node: ast.AST | None, symbol: str) -> ast.AST | None:
    if function_node is None:
        return None
    for node in ast.walk(function_node):
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets: Iterable[ast.AST]
            if isinstance(node, ast.Assign):
                targets = node.targets
            else:
                targets = (node.target,)
            for target in targets:
                if isinstance(target, ast.Name) and target.id == symbol:
                    return node
    return None


def _imported_local_name(import_node: ast.ImportFrom | None, symbol: str) -> str:
    if import_node is None:
        return ""
    for alias in import_node.names:
        if alias.name == symbol:
            return alias.asname or alias.name
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


def _top_level_symbol(tree: ast.AST, symbol: str) -> ast.AST | None:
    for node in getattr(tree, "body", []):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == symbol:
            return node
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == symbol:
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


def _target_resolution_row(spec: HookSpec) -> Dict[str, Any]:
    target_path = _resolve_module_path(spec.import_module)
    if target_path is None:
        return {
            "hook_reference": spec.hook_reference,
            "import_module": spec.import_module,
            "imported_symbol": spec.imported_symbol,
            "local_symbol": spec.local_symbol,
            "target_attribute": spec.target_attribute,
            "target_path": "",
            "target_path_exists": False,
            "target_symbol_found": False,
            "target_symbol_line": "",
            "target_attribute_found": False,
            "target_attribute_line": "",
            "static_target_resolution": "WARN",
            "notes": "import target module path not found by source-only resolution; runtime import not attempted",
        }

    source = _read_text(target_path)
    tree = ast.parse(source, filename=str(target_path))
    symbol_node = _top_level_symbol(tree, spec.imported_symbol)
    attr_node = None
    if spec.target_attribute and symbol_node is not None:
        class_name = _assigned_call_class(symbol_node)
        if class_name:
            attr_node = _class_method(tree, class_name, spec.target_attribute)
    symbol_found = symbol_node is not None
    attr_found = bool(attr_node) if spec.target_attribute else True
    status = "PASS" if symbol_found and attr_found else "WARN"
    notes = "target module and symbol resolved by source/AST"
    if spec.target_attribute:
        notes = (
            "target module, imported instance symbol, and called class method resolved by source/AST"
            if status == "PASS"
            else "target module found but imported symbol or called attribute was not fully resolved by source/AST"
        )
    elif status != "PASS":
        notes = "target module found but imported symbol was not resolved by source/AST"

    return {
        "hook_reference": spec.hook_reference,
        "import_module": spec.import_module,
        "imported_symbol": spec.imported_symbol,
        "local_symbol": spec.local_symbol,
        "target_attribute": spec.target_attribute,
        "target_path": _artifact_label(target_path),
        "target_path_exists": True,
        "target_symbol_found": symbol_found,
        "target_symbol_line": _line(symbol_node),
        "target_attribute_found": attr_found,
        "target_attribute_line": _line(attr_node) if spec.target_attribute else "",
        "static_target_resolution": status,
        "notes": notes,
    }


def _contract_row(
    spec: HookSpec,
    source: str,
    refresh_function: ast.AST | None,
    target_row: Mapping[str, Any],
) -> Dict[str, Any]:
    import_node = _find_import_from(refresh_function, spec.import_module, spec.imported_symbol)
    assignment_node = _find_assignment(refresh_function, spec.local_symbol)
    call_node = _find_call(refresh_function, spec.call_name)
    reference_node = import_node or call_node or assignment_node
    local_name = _imported_local_name(import_node, spec.imported_symbol)
    imported_or_assigned = bool(import_node or assignment_node)
    reference_found = reference_node is not None
    status = "FAIL"
    notes = "expected live hook reference missing"
    if reference_found and call_node is not None:
        status = str(target_row["static_target_resolution"])
        notes = str(target_row["notes"])
    elif reference_found:
        status = "WARN"
        notes = "reference found but call-like use was not found in _refresh_after_insert"

    symbol_bits: List[str] = []
    if import_node is not None:
        symbol_bits.append(_node_source(source, import_node))
    if assignment_node is not None:
        symbol_bits.append(_node_source(source, assignment_node))

    return {
        "hook_reference": spec.hook_reference,
        "expected_live": True,
        "refresh_after_insert_present": refresh_function is not None,
        "reference_found": reference_found,
        "source_line": _line(reference_node),
        "ast_node_type": type(reference_node).__name__ if reference_node is not None else "",
        "reference_evidence": _node_source(source, reference_node),
        "call_like_in_refresh_after_insert": call_node is not None,
        "call_line": _line(call_node),
        "call_evidence": _node_source(source, call_node),
        "imported_or_assigned_symbol": local_name or spec.local_symbol if imported_or_assigned else "",
        "symbol_evidence": " | ".join(symbol_bits),
        "static_target_resolution": target_row["static_target_resolution"],
        "status": status,
        "notes": notes,
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


def _load_csv_rows(path: Path) -> List[Dict[str, str]]:
    return list(csv.DictReader(_read_text(path).splitlines()))


def _load_p520c_summary() -> Dict[str, Any]:
    result = json.loads(_read_text(P520C_RESULT_PATH)) if P520C_RESULT_PATH.exists() else {}
    hook_rows = _load_csv_rows(P520C_HOOK_INVENTORY_PATH) if P520C_HOOK_INVENTORY_PATH.exists() else []
    dead_rows = _load_csv_rows(P520C_DEAD_HOOKS_PATH) if P520C_DEAD_HOOKS_PATH.exists() else []
    return {
        "result_artifact": _artifact_label(P520C_RESULT_PATH),
        "result_present": P520C_RESULT_PATH.exists(),
        "final_status": result.get("final_status", ""),
        "expected_live_hooks": result.get("expected_live_hooks", []),
        "detected_live_hook_count": result.get("detected_live_hook_count", ""),
        "removed_dead_hooks": result.get("removed_dead_hooks", []),
        "hook_inventory_artifact": _artifact_label(P520C_HOOK_INVENTORY_PATH),
        "hook_inventory_rows": len(hook_rows),
        "dead_hooks_artifact": _artifact_label(P520C_DEAD_HOOKS_PATH),
        "dead_hook_rows": len(dead_rows),
    }


def analyze_contract(path: Path = INGEST_ROUTE_PATH) -> Dict[str, Any]:
    source = _read_text(path)
    tree = ast.parse(source, filename=str(path))
    functions = _function_defs(tree)
    refresh_function = functions.get("_refresh_after_insert")
    refresh_source = _node_source(source, refresh_function)

    target_rows = [_target_resolution_row(spec) for spec in EXPECTED_HOOKS]
    target_by_hook = {row["hook_reference"]: row for row in target_rows}
    contract_rows = [
        _contract_row(spec, source, refresh_function, target_by_hook[spec.hook_reference])
        for spec in EXPECTED_HOOKS
    ]
    dead_rows = _dead_hook_rows(source, tree)
    removed_missing_residue = [
        hook_name for hook_name in REMOVED_MISSING_TARGET_HOOKS if hook_name in source
    ]
    warnings = [
        f"{row['hook_reference']}: {row['notes']}"
        for row in contract_rows
        if row["status"] == "WARN"
    ]
    failures = [
        f"{row['hook_reference']}: {row['notes']}"
        for row in contract_rows
        if row["status"] == "FAIL"
    ]
    failures.extend(f"removed dead hook reference found: {row['symbol']}" for row in dead_rows if row["status"] != "PASS")
    failures.extend(
        f"removed missing-target hook residue found: {hook_name}"
        for hook_name in removed_missing_residue
    )
    if refresh_function is None:
        failures.append("_refresh_after_insert missing")

    final_status = "FAIL" if failures else "WARN" if warnings else "PASS"
    return {
        "source_path": _artifact_label(path),
        "source_sha256": _sha256_bytes(source.encode("utf-8")),
        "source_bytes": len(source.encode("utf-8")),
        "refresh_after_insert_present": refresh_function is not None,
        "refresh_after_insert_line": _line(refresh_function),
        "refresh_after_insert_source_sha256": _sha256_bytes(refresh_source.encode("utf-8")) if refresh_source else "",
        "refresh_after_insert_call_site_lines": _call_sites(tree, "_refresh_after_insert"),
        "expected_live_hooks": [spec.hook_reference for spec in EXPECTED_HOOKS],
        "contract_matrix": contract_rows,
        "target_resolution": target_rows,
        "removed_missing_target_hooks": list(REMOVED_MISSING_TARGET_HOOKS),
        "removed_missing_target_hook_count": len(REMOVED_MISSING_TARGET_HOOKS) - len(removed_missing_residue),
        "missing_target_residue_status": "PASS" if not removed_missing_residue else "FAIL",
        "missing_target_residue": removed_missing_residue,
        "dead_hooks": dead_rows,
        "detected_live_hook_count": sum(1 for row in contract_rows if row["reference_found"]),
        "call_like_live_hook_count": sum(1 for row in contract_rows if row["call_like_in_refresh_after_insert"]),
        "target_resolution_pass_count": sum(1 for row in target_rows if row["static_target_resolution"] == "PASS"),
        "target_resolution_warn_count": sum(1 for row in target_rows if row["static_target_resolution"] == "WARN"),
        "dead_hook_absence_status": "PASS" if all(row["status"] == "PASS" for row in dead_rows) else "FAIL",
        "warning_count": len(warnings),
        "warnings": warnings,
        "failure_count": len(failures),
        "failures": failures,
        "final_status": final_status,
        "p520c_summary": _load_p520c_summary(),
    }


def build_contract_bundle() -> Dict[str, Any]:
    analysis = analyze_contract()
    component_statuses = {
        "_refresh_after_insert present": "PASS" if analysis["refresh_after_insert_present"] else "FAIL",
        "expected live hooks referenced": "PASS"
        if analysis["detected_live_hook_count"] == len(EXPECTED_HOOKS)
        else "FAIL",
        "expected live hooks call-like": "PASS"
        if analysis["call_like_live_hook_count"] == len(EXPECTED_HOOKS)
        else "WARN",
        "static target resolution": "WARN" if analysis["target_resolution_warn_count"] else "PASS",
        "missing-target hook residue absent": analysis["missing_target_residue_status"],
        "removed dead hooks absent": analysis["dead_hook_absence_status"],
        "source AST evaluation": "PASS",
        "runtime import avoided": "PASS",
        "DB side effects avoided": "PASS",
    }
    result = {
        "artifact_prefix": ARTIFACT_PREFIX,
        "final_status": analysis["final_status"],
        "source_path": analysis["source_path"],
        "source_sha256": analysis["source_sha256"],
        "refresh_after_insert_present": analysis["refresh_after_insert_present"],
        "refresh_after_insert_line": analysis["refresh_after_insert_line"],
        "refresh_after_insert_call_site_lines": analysis["refresh_after_insert_call_site_lines"],
        "expected_live_hooks": analysis["expected_live_hooks"],
        "detected_live_hook_count": analysis["detected_live_hook_count"],
        "call_like_live_hook_count": analysis["call_like_live_hook_count"],
        "target_resolution_pass_count": analysis["target_resolution_pass_count"],
        "target_resolution_warn_count": analysis["target_resolution_warn_count"],
        "removed_missing_target_hooks": analysis["removed_missing_target_hooks"],
        "removed_missing_target_hook_count": analysis["removed_missing_target_hook_count"],
        "missing_target_residue_status": analysis["missing_target_residue_status"],
        "missing_target_residue": analysis["missing_target_residue"],
        "removed_dead_hooks": list(REMOVED_DEAD_HOOKS),
        "dead_hook_absence_status": analysis["dead_hook_absence_status"],
        "warning_count": analysis["warning_count"],
        "warnings": analysis["warnings"],
        "failure_count": analysis["failure_count"],
        "failures": analysis["failures"],
        "component_statuses": component_statuses,
        "p520c_summary": analysis["p520c_summary"],
        "suggested_next_command": "python -m tools.ingest_afterinsert_hook_contract --status-block",
        "scope": (
            "P520D parses lottery_api/routes/ingest.py and statically resolvable targets as text/AST only; "
            "no app runtime import; no after-insert hook execution; no draw insert execution; no canonical DB "
            "open/write; no migration/backfill; no deploy; does not implement replacement scheduler/tracker; "
            "no betting/future prediction claims."
        ),
        "notices": list(NOTICE_LINES),
    }
    return {
        "result": result,
        "contract_matrix": analysis["contract_matrix"],
        "target_resolution": analysis["target_resolution"],
        "dead_hooks": analysis["dead_hooks"],
        "status_block": _status_block_md(result),
    }


def _status_block_md(result: Mapping[str, Any]) -> str:
    lines = [
        "## P520D Ingest After-Insert Hook Contract",
        "",
        f"- Final status: `{result['final_status']}`",
        f"- Source path: `{result['source_path']}`",
        f"- `_refresh_after_insert` present: `{result['refresh_after_insert_present']}`",
        f"- `_refresh_after_insert` line: `{result['refresh_after_insert_line']}`",
        f"- `_refresh_after_insert` call sites: `{result['refresh_after_insert_call_site_lines']}`",
        f"- Expected live hooks: `{result['expected_live_hooks']}`",
        f"- Detected live hook references: `{result['detected_live_hook_count']}`",
        f"- Call-like live hooks: `{result['call_like_live_hook_count']}`",
        f"- Static target resolution PASS count: `{result['target_resolution_pass_count']}`",
        f"- Static target resolution WARN count: `{result['target_resolution_warn_count']}`",
        f"- Removed missing-target hooks: `{result['removed_missing_target_hooks']}`",
        f"- Missing-target residue status: `{result['missing_target_residue_status']}`",
        f"- Dead hook absence status: `{result['dead_hook_absence_status']}`",
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
    for path in (RESULT_PATH, CONTRACT_MATRIX_PATH, TARGET_RESOLUTION_PATH, DEAD_HOOKS_PATH, STATUS_BLOCK_PATH):
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
    bundle = build_contract_bundle()
    rendered: Dict[Path, str] = {
        RESULT_PATH: _json_text(bundle["result"]),
        CONTRACT_MATRIX_PATH: _csv_text(bundle["contract_matrix"], CONTRACT_FIELDS),
        TARGET_RESOLUTION_PATH: _csv_text(bundle["target_resolution"], TARGET_RESOLUTION_FIELDS),
        DEAD_HOOKS_PATH: _csv_text(bundle["dead_hooks"], DEAD_HOOK_FIELDS),
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
    if result.get("dead_hook_absence_status") != "PASS":
        mismatches.append("dead hook absence failed")
    return not mismatches, mismatches


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="P520D source/AST-only contract evaluator for ingest after-insert live hooks."
    )
    parser.add_argument("--generate", action="store_true", help="write all deterministic P520D contract artifacts")
    parser.add_argument("--contract", action="store_true", help="print live hook contract matrix CSV")
    parser.add_argument("--target-resolution", action="store_true", help="print static target resolution CSV")
    parser.add_argument("--dead-hook-check", action="store_true", help="print removed dead hook absence CSV")
    parser.add_argument("--status-block", action="store_true", help="print copy-paste contract status block Markdown")
    parser.add_argument("--validate", action="store_true", help="validate generated P520D artifacts by byte equality")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    rendered = render_artifacts()

    if args.generate:
        write_artifacts(rendered)
        for path in rendered:
            print(f"[p520d-contract] wrote {_artifact_label(path)}")

    if args.contract:
        print(rendered[CONTRACT_MATRIX_PATH], end="")

    if args.target_resolution:
        print(rendered[TARGET_RESOLUTION_PATH], end="")

    if args.dead_hook_check:
        print(rendered[DEAD_HOOKS_PATH], end="")

    if args.status_block:
        print(rendered[STATUS_BLOCK_PATH], end="")

    if args.validate:
        ok, mismatches = validate_artifacts(rendered)
        if ok:
            print("[p520d-contract] validation_status=PASS")
        else:
            print("[p520d-contract] validation_status=FAIL", file=sys.stderr)
            for mismatch in mismatches:
                print(f"[p520d-contract] {mismatch}", file=sys.stderr)
            return 1

    if not any(
        (
            args.generate,
            args.contract,
            args.target_resolution,
            args.dead_hook_check,
            args.status_block,
            args.validate,
        )
    ):
        parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
