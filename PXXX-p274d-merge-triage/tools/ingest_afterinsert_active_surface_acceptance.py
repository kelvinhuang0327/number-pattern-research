#!/usr/bin/env python3
"""P520K source/AST/text-only active after-insert surface acceptance.

This module parses ``lottery_api/routes/ingest.py`` and committed P520J/P520I
artifacts only. It does not import ``lottery_api.routes.ingest``, does not
import live hook target modules, does not execute hooks or draw inserts, does
not open or write a database, does not run migrations/backfills, and does not
deploy.
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
from typing import Any, Dict, List, Mapping, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
INGEST_ROUTE_PATH = PROJECT_ROOT / "lottery_api" / "routes" / "ingest.py"

ARTIFACT_PREFIX = "P520K_ingest_afterinsert_active_surface_acceptance"

RESULT_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_result.json"
ACTIVE_SURFACE_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_active_surface.csv"
DISABLED_SURFACE_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_disabled_surface.csv"
COMPLETION_SUMMARY_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_completion_summary.json"
STATUS_BLOCK_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_status_block.md"
MANIFEST_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_manifest.csv"

P520I_BINDING_PATH = ARTIFACTS_DIR / "P520I_ingest_afterinsert_hook_static_binding_resolver_binding_chain.csv"
P520J_RESULT_PATH = ARTIFACTS_DIR / "P520J_disable_missing_afterinsert_hooks_result.json"
P520J_DISABLED_MATRIX_PATH = ARTIFACTS_DIR / "P520J_disable_missing_afterinsert_hooks_disabled_matrix.csv"
P520J_RETAINED_HOOKS_PATH = ARTIFACTS_DIR / "P520J_disable_missing_afterinsert_hooks_retained_hooks.csv"
P520J_WARNING_EVIDENCE_PATH = ARTIFACTS_DIR / "P520J_disable_missing_afterinsert_hooks_warning_only_evidence.json"

DISABLED_FLAG = "_MISSING_AFTERINSERT_HOOKS_ENABLED"
REMOVED_DEAD_SYMBOLS: Sequence[str] = (
    "_schedule_after_insert",
    "snapshot_scheduler",
    "prediction_tracker",
)
NOTICE_LINES: Sequence[str] = (
    "source/AST/text-only active surface acceptance",
    "reads committed P520J/P520I artifacts",
    "parses lottery_api/routes/ingest.py without importing it",
    "does not import live hook target modules",
    "does not execute after-insert hooks",
    "does not execute draw inserts",
    "no canonical DB open/write",
    "no migration/backfill",
    "no deploy",
    "does not modify hook implementation files",
    "does not modify lottery_api/routes/ingest.py",
    "no betting/future prediction claims",
)

ACTIVE_SURFACE_FIELDS: Sequence[str] = (
    "surface_name",
    "status",
    "active",
    "guard_symbol",
    "guard_value",
    "import_module",
    "imported_symbol",
    "local_symbol",
    "import_line",
    "call_line",
    "call_evidence",
    "guarded_by_missing_hook_flag",
    "completion_surface_counted",
    "reason",
)
DISABLED_SURFACE_FIELDS: Sequence[str] = (
    "hook_name",
    "status",
    "active",
    "guard_symbol",
    "guard_value",
    "guard_line",
    "import_module",
    "imported_symbol",
    "local_symbol",
    "import_line",
    "call_line",
    "warning_line",
    "p520i_terminal_status",
    "p520i_unresolved_reason",
    "completion_surface_counted",
    "reason",
)
MANIFEST_FIELDS: Sequence[str] = ("artifact_path", "artifact_kind", "sha256", "bytes", "notes")


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _json_text(data: Any) -> str:
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


def _load_json(path: Path) -> Any:
    return json.loads(_read_text(path)) if path.exists() else {}


def _load_csv_rows(path: Path) -> List[Dict[str, str]]:
    return list(csv.DictReader(_read_text(path).splitlines())) if path.exists() else []


def _short_excerpt(text: str, limit: int = 220) -> str:
    collapsed = " ".join(text.strip().split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: limit - 3].rstrip() + "..."


def _node_source(source: str, node: ast.AST | None) -> str:
    if node is None:
        return ""
    return _short_excerpt(ast.get_source_segment(source, node) or "")


def _line(node: ast.AST | None) -> str:
    if node is None:
        return ""
    lineno = getattr(node, "lineno", "")
    return str(lineno) if lineno else ""


def _parse_ingest() -> Tuple[str, ast.Module | None, str]:
    if not INGEST_ROUTE_PATH.exists():
        return "", None, "source file missing"
    source = _read_text(INGEST_ROUTE_PATH)
    try:
        return source, ast.parse(source, filename=str(INGEST_ROUTE_PATH)), ""
    except SyntaxError as exc:
        return source, None, f"{exc.__class__.__name__}: {exc.msg}"


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _call_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return ""


def _refresh_function(tree: ast.AST | None) -> ast.FunctionDef | None:
    if tree is None:
        return None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_refresh_after_insert":
            return node
    return None


def _parent_map(tree: ast.AST | None) -> Dict[ast.AST, ast.AST]:
    if tree is None:
        return {}
    return {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}


def _ancestors(node: ast.AST, parents: Mapping[ast.AST, ast.AST]) -> List[ast.AST]:
    chain: List[ast.AST] = []
    while node in parents:
        node = parents[node]
        chain.append(node)
    return chain


def _guard_assignment(tree: ast.AST | None) -> Tuple[ast.Assign | None, bool | None]:
    if tree is None:
        return None, None
    for node in getattr(tree, "body", []):
        if not isinstance(node, ast.Assign):
            continue
        if any(isinstance(target, ast.Name) and target.id == DISABLED_FLAG for target in node.targets):
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, bool):
                return node, node.value.value
            return node, None
    return None, None


def _guard_node(refresh_function: ast.AST | None) -> ast.If | None:
    if refresh_function is None:
        return None
    for node in ast.walk(refresh_function):
        if isinstance(node, ast.If) and isinstance(node.test, ast.Name) and node.test.id == DISABLED_FLAG:
            return node
    return None


def _collect_imports(function_node: ast.AST | None, source: str) -> Dict[str, Dict[str, str]]:
    imports: Dict[str, Dict[str, str]] = {}
    if function_node is None:
        return imports
    for node in ast.walk(function_node):
        if isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                local_symbol = alias.asname or alias.name
                imports[local_symbol] = {
                    "import_module": node.module,
                    "imported_symbol": alias.name,
                    "local_symbol": local_symbol,
                    "import_line": _line(node),
                    "import_evidence": _node_source(source, node),
                }
        elif isinstance(node, ast.Import):
            for alias in node.names:
                local_symbol = alias.asname or alias.name.split(".")[0]
                imports[local_symbol] = {
                    "import_module": alias.name,
                    "imported_symbol": "",
                    "local_symbol": local_symbol,
                    "import_line": _line(node),
                    "import_evidence": _node_source(source, node),
                }
    return imports


def _find_call(function_node: ast.AST | None, call_name: str) -> ast.Call | None:
    if function_node is None:
        return None
    calls = [
        node
        for node in ast.walk(function_node)
        if isinstance(node, ast.Call) and _call_name(node.func) == call_name
    ]
    calls.sort(key=lambda node: getattr(node, "lineno", 0))
    return calls[0] if calls else None


def _missing_hook_order(p520j_result: Mapping[str, Any], disabled_rows: Sequence[Mapping[str, str]]) -> List[str]:
    result_order = [str(item) for item in p520j_result.get("disabled_missing_hooks", [])]
    row_names = [row.get("hook_name", "") for row in disabled_rows if row.get("hook_name")]
    ordered = [name for name in result_order if name in row_names]
    ordered.extend(name for name in row_names if name not in ordered)
    return ordered


def _line_int(value: str) -> int:
    return int(value) if str(value).isdigit() else 0


def _build_bundle() -> Dict[str, Any]:
    source, tree, parse_error = _parse_ingest()
    refresh_function = _refresh_function(tree)
    parents = _parent_map(tree)
    guard_assign, guard_value = _guard_assignment(tree)
    guard = _guard_node(refresh_function)
    imports = _collect_imports(refresh_function, source)

    p520j_result = _load_json(P520J_RESULT_PATH)
    p520j_warning_evidence = _load_json(P520J_WARNING_EVIDENCE_PATH)
    p520j_disabled_rows = _load_csv_rows(P520J_DISABLED_MATRIX_PATH)
    p520j_retained_rows = _load_csv_rows(P520J_RETAINED_HOOKS_PATH)
    p520i_rows = _load_csv_rows(P520I_BINDING_PATH)
    p520i_by_hook = {row.get("hook_name", ""): row for row in p520i_rows}
    disabled_by_hook = {row.get("hook_name", ""): row for row in p520j_disabled_rows}

    scheduler_call = _find_call(refresh_function, "scheduler.load_data")
    scheduler_guarded = bool(scheduler_call is not None and guard is not None and guard in _ancestors(scheduler_call, parents))
    scheduler_import = imports.get("scheduler", {})
    scheduler_active = scheduler_call is not None and not scheduler_guarded

    active_rows = [
        {
            "surface_name": "scheduler.load_data",
            "status": "ACTIVE" if scheduler_active else "MISSING_OR_GUARDED",
            "active": str(bool(scheduler_active)),
            "guard_symbol": "",
            "guard_value": "",
            "import_module": scheduler_import.get("import_module", "utils.scheduler"),
            "imported_symbol": scheduler_import.get("imported_symbol", "scheduler"),
            "local_symbol": scheduler_import.get("local_symbol", "scheduler"),
            "import_line": scheduler_import.get("import_line", ""),
            "call_line": _line(scheduler_call),
            "call_evidence": _node_source(source, scheduler_call),
            "guarded_by_missing_hook_flag": str(bool(scheduler_guarded)),
            "completion_surface_counted": str(bool(scheduler_active)),
            "reason": "scheduler refresh retained outside disabled missing-hook guard" if scheduler_active else "scheduler refresh is missing or gated",
        }
    ]

    disabled_rows: List[Dict[str, Any]] = []
    active_missing_hooks: List[str] = []
    disabled_hook_order = _missing_hook_order(p520j_result, p520j_disabled_rows)
    for hook_name in disabled_hook_order:
        p520j_row = disabled_by_hook.get(hook_name, {})
        p520i_row = p520i_by_hook.get(hook_name, {})
        local_symbol = p520j_row.get("local_symbol") or p520i_row.get("local_symbol", "")
        import_module = p520j_row.get("import_module") or p520i_row.get("import_module", "")
        imported_symbol = p520j_row.get("imported_symbol") or p520i_row.get("imported_symbol", "")
        call_name = local_symbol
        call = _find_call(refresh_function, call_name) if call_name else None
        import_binding = imports.get(local_symbol, {})
        guarded_call = bool(call is not None and guard is not None and guard in _ancestors(call, parents))
        guarded_import = bool(
            import_binding.get("import_line")
            and guard is not None
            and any(
                isinstance(node, (ast.Import, ast.ImportFrom))
                and _line(node) == import_binding.get("import_line")
                and guard in _ancestors(node, parents)
                for node in ast.walk(refresh_function or ast.Module(body=[], type_ignores=[]))
            )
        )
        safely_disabled = guard_value is False and guarded_call and guarded_import
        active = not safely_disabled
        if active:
            active_missing_hooks.append(hook_name)
        disabled_rows.append(
            {
                "hook_name": hook_name,
                "status": "DISABLED" if safely_disabled else "ACTIVE_OR_UNRESOLVED",
                "active": str(bool(active)),
                "guard_symbol": DISABLED_FLAG if guard is not None else "",
                "guard_value": str(guard_value) if guard_value is not None else "",
                "guard_line": _line(guard_assign),
                "import_module": import_module,
                "imported_symbol": imported_symbol,
                "local_symbol": local_symbol,
                "import_line": import_binding.get("import_line", p520j_row.get("import_line", "")),
                "call_line": _line(call) or p520j_row.get("call_line", ""),
                "warning_line": p520j_row.get("warning_line", ""),
                "p520i_terminal_status": p520i_row.get("terminal_symbol_status", ""),
                "p520i_unresolved_reason": p520i_row.get("unresolved_reason", ""),
                "completion_surface_counted": str(False if safely_disabled else True),
                "reason": "missing-target hook remains in source but is gated by false missing-hook flag"
                if safely_disabled
                else "missing-target hook is not safely gated by false missing-hook flag",
            }
        )

    removed_dead_symbols_present = sorted(symbol for symbol in REMOVED_DEAD_SYMBOLS if symbol in source)
    missing_artifacts = [
        path
        for path in (
            P520J_RESULT_PATH,
            P520J_DISABLED_MATRIX_PATH,
            P520J_RETAINED_HOOKS_PATH,
            P520J_WARNING_EVIDENCE_PATH,
            P520I_BINDING_PATH,
        )
        if not path.exists()
    ]

    failures: List[str] = []
    if missing_artifacts:
        failures.extend(f"missing artifact: {_artifact_label(path)}" for path in missing_artifacts)
    if parse_error:
        failures.append(f"ingest source parse failed: {parse_error}")
    if refresh_function is None:
        failures.append("_refresh_after_insert missing")
    if guard_assign is None or guard_value is not False:
        failures.append(f"{DISABLED_FLAG} is missing or not constant False")
    if guard is None:
        failures.append("disabled missing-hook guard not found")
    if not scheduler_active:
        failures.append("scheduler.load_data is missing or gated by missing-hook flag")
    if active_missing_hooks:
        failures.append("missing-target hooks active: " + ";".join(sorted(active_missing_hooks)))
    if removed_dead_symbols_present:
        failures.append("removed dead hook symbols present: " + ";".join(removed_dead_symbols_present))

    disabled_hook_count = sum(1 for row in disabled_rows if row["status"] == "DISABLED")
    active_completion_surface = [
        row["surface_name"] for row in active_rows if row["completion_surface_counted"] == "True"
    ]
    disabled_completion_surface = [
        row["hook_name"] for row in disabled_rows if row["completion_surface_counted"] == "False"
    ]
    warnings = []
    if disabled_rows and not failures:
        warnings.append("disabled missing-target hook blocks remain in source but are gated false")

    final_status = "FAIL" if failures else "WARN" if warnings else "PASS"
    acceptance_status = "PASS" if not failures and scheduler_active and not active_missing_hooks else "FAIL"
    component_statuses = {
        "P520J result artifact read": "PASS" if P520J_RESULT_PATH.exists() else "FAIL",
        "P520J disabled matrix artifact read": "PASS" if P520J_DISABLED_MATRIX_PATH.exists() else "FAIL",
        "P520J retained hooks artifact read": "PASS" if P520J_RETAINED_HOOKS_PATH.exists() else "FAIL",
        "P520J warning evidence artifact read": "PASS" if P520J_WARNING_EVIDENCE_PATH.exists() else "FAIL",
        "P520I binding artifact read": "PASS" if P520I_BINDING_PATH.exists() else "FAIL",
        "ingest source AST evaluation": "PASS" if not parse_error else "FAIL",
        "disabled missing-target hook guard": "PASS" if guard_value is False else "FAIL",
        "scheduler.load_data active": "PASS" if scheduler_active else "FAIL",
        "missing-target hooks not active": "PASS" if not active_missing_hooks else "FAIL",
        "removed dead hook symbols absent": "PASS" if not removed_dead_symbols_present else "FAIL",
        "runtime import avoided": "PASS",
        "DB side effects avoided": "PASS",
    }
    pass_count = sum(1 for status in component_statuses.values() if status == "PASS")

    result = {
        "artifact_prefix": ARTIFACT_PREFIX,
        "final_status": final_status,
        "acceptance_status": acceptance_status,
        "source_path": _artifact_label(INGEST_ROUTE_PATH),
        "active_completion_surface_count": len(active_completion_surface),
        "active_completion_surface": active_completion_surface,
        "disabled_missing_target_surface_count": disabled_hook_count,
        "disabled_missing_target_surface": disabled_completion_surface,
        "missing_target_hooks_counted_as_active_completion_surface": sorted(active_missing_hooks),
        "scheduler_load_data_active": scheduler_active,
        "scheduler_load_data_line": _line(scheduler_call),
        "scheduler_load_data_outside_missing_hook_guard": scheduler_active,
        "disabled_guard": {
            "symbol": DISABLED_FLAG,
            "line": _line(guard_assign),
            "value": guard_value,
        },
        "removed_dead_hook_symbols_absent": sorted(REMOVED_DEAD_SYMBOLS),
        "removed_dead_hook_symbols_present": removed_dead_symbols_present,
        "p520j_summary": {
            "result_artifact": _artifact_label(P520J_RESULT_PATH),
            "final_status": p520j_result.get("final_status", ""),
            "disabled_missing_hook_count": p520j_result.get("disabled_missing_hook_count", ""),
            "retained_hook_count": p520j_result.get("retained_hook_count", ""),
            "warning_only_hooks": sorted((p520j_warning_evidence.get("hooks") or {}).keys()),
            "retained_hooks": [row.get("hook_name", "") for row in p520j_retained_rows],
        },
        "p520i_summary": {
            "binding_artifact": _artifact_label(P520I_BINDING_PATH),
            "unresolved_hooks": sorted(row.get("hook_name", "") for row in p520i_rows if row.get("terminal_symbol_status") == "UNRESOLVED"),
            "unresolved_reasons": sorted({row.get("unresolved_reason", "") for row in p520i_rows if row.get("unresolved_reason")}),
        },
        "component_statuses": component_statuses,
        "pass_count": pass_count,
        "warn_count": len(warnings),
        "fail_count": len(failures),
        "warning_count": len(warnings),
        "warnings": warnings,
        "failure_count": len(failures),
        "failures": failures,
        "notices": list(NOTICE_LINES),
        "scope": (
            "P520K parses lottery_api/routes/ingest.py and committed P520J/P520I artifacts only. "
            "scheduler.load_data is counted as retained active completion surface when outside "
            "the false missing-hook guard. Missing-target hooks are excluded from active completion "
            "surface when their import and call are inside _MISSING_AFTERINSERT_HOOKS_ENABLED = False."
        ),
        "suggested_next_command": "python -m tools.ingest_afterinsert_active_surface_acceptance --status-block",
    }

    completion_summary = {
        "artifact_prefix": ARTIFACT_PREFIX,
        "final_status": final_status,
        "acceptance_status": acceptance_status,
        "active_completion_surface_count": len(active_completion_surface),
        "active_completion_surface": active_completion_surface,
        "disabled_missing_target_surface_count": disabled_hook_count,
        "disabled_missing_target_surface": disabled_completion_surface,
        "missing_target_hooks_counted_as_active_completion_surface": sorted(active_missing_hooks),
        "scheduler_refresh_retained": scheduler_active,
        "missing_target_hooks_no_longer_active_completion_surface": not active_missing_hooks,
        "removed_dead_hook_symbols_present": removed_dead_symbols_present,
    }

    return {
        "result": result,
        "active_surface": active_rows,
        "disabled_surface": sorted(disabled_rows, key=lambda row: _line_int(str(row["call_line"]))),
        "completion_summary": completion_summary,
    }


def _status_block(result: Mapping[str, Any]) -> str:
    lines = [
        "# P520K ingest after-insert active surface acceptance status",
        "",
        f"- Final status: `{result['final_status']}`",
        f"- Acceptance status: `{result['acceptance_status']}`",
        f"- Active completion surface count: `{result['active_completion_surface_count']}`",
        f"- Disabled missing-target surface count: `{result['disabled_missing_target_surface_count']}`",
        f"- Missing-target hooks counted as active completion surface: `{';'.join(result['missing_target_hooks_counted_as_active_completion_surface'])}`",
        f"- scheduler.load_data active: `{result['scheduler_load_data_active']}`",
        f"- scheduler.load_data line: `{result['scheduler_load_data_line']}`",
        f"- PASS/WARN/FAIL counts: `{result['pass_count']}/{result['warn_count']}/{result['fail_count']}`",
        "",
        "## Active Surface",
    ]
    lines.extend(f"- `{name}`" for name in result["active_completion_surface"])
    lines.extend(["", "## Disabled Missing-Target Surface"])
    lines.extend(f"- `{name}`" for name in result["disabled_missing_target_surface"])
    lines.extend(["", "## Scope notices"])
    lines.extend(f"- {notice}" for notice in NOTICE_LINES)
    lines.extend(
        [
            "",
            "## Recommendation",
            "- Treat scheduler.load_data as the retained active after-insert completion surface.",
            "- Treat the missing-target hooks as disabled warning-only source blocks, not active completion surface.",
            "- Runtime import, hook execution, draw insertion, DB access, migration, backfill, and deploy were not attempted.",
        ]
    )
    return "\n".join(lines) + "\n"


def build_active_surface_acceptance_bundle() -> Dict[str, Any]:
    bundle = _build_bundle()
    bundle["status_block"] = _status_block(bundle["result"])
    return bundle


def _manifest_rows(rendered: Mapping[Path, str]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for path in (RESULT_PATH, ACTIVE_SURFACE_PATH, DISABLED_SURFACE_PATH, COMPLETION_SUMMARY_PATH, STATUS_BLOCK_PATH):
        text = rendered[path]
        data = text.encode("utf-8")
        rows.append(
            {
                "artifact_path": _artifact_label(path),
                "artifact_kind": path.suffix.lstrip("."),
                "sha256": _sha256_bytes(data),
                "bytes": len(data),
                "notes": "generated by source/AST/text-only P520K active surface acceptance",
            }
        )
    rows.append(
        {
            "artifact_path": _artifact_label(MANIFEST_PATH),
            "artifact_kind": "csv",
            "sha256": "",
            "bytes": "",
            "notes": "self row omits digest to avoid recursion",
        }
    )
    return rows


def render_artifacts() -> Dict[Path, str]:
    bundle = build_active_surface_acceptance_bundle()
    rendered: Dict[Path, str] = {
        RESULT_PATH: _json_text(bundle["result"]),
        ACTIVE_SURFACE_PATH: _csv_text(bundle["active_surface"], ACTIVE_SURFACE_FIELDS),
        DISABLED_SURFACE_PATH: _csv_text(bundle["disabled_surface"], DISABLED_SURFACE_FIELDS),
        COMPLETION_SUMMARY_PATH: _json_text(bundle["completion_summary"]),
        STATUS_BLOCK_PATH: bundle["status_block"],
    }
    rendered[MANIFEST_PATH] = _csv_text(_manifest_rows(rendered), MANIFEST_FIELDS)
    return rendered


def write_artifacts() -> Dict[Path, str]:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    rendered = render_artifacts()
    for path, text in rendered.items():
        path.write_text(text, encoding="utf-8")
    return rendered


def validate_artifacts(expected: Mapping[Path, str] | None = None) -> Tuple[bool, List[str]]:
    rendered = dict(expected or render_artifacts())
    mismatches: List[str] = []
    second_render = render_artifacts()
    if rendered != second_render:
        mismatches.append("deterministic double-run render mismatch")
    result = json.loads(second_render[RESULT_PATH])
    if result.get("acceptance_status") != "PASS":
        mismatches.append(f"acceptance status is {result.get('acceptance_status')}")
    if result.get("fail_count") != 0:
        mismatches.append("acceptance result has failures")
    for path, expected_text in rendered.items():
        if not path.exists():
            mismatches.append(f"missing artifact: {_artifact_label(path)}")
            continue
        actual_text = path.read_text(encoding="utf-8")
        if actual_text != expected_text:
            mismatches.append(f"artifact mismatch: {_artifact_label(path)}")
    return not mismatches, mismatches


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--generate", action="store_true", help="write all P520K active surface acceptance artifacts")
    parser.add_argument("--acceptance", action="store_true", help="print acceptance result JSON")
    parser.add_argument("--active-surface", action="store_true", help="print active hook surface CSV")
    parser.add_argument("--disabled-surface", action="store_true", help="print disabled missing-target surface CSV")
    parser.add_argument("--completion-summary", action="store_true", help="print completion surface summary JSON")
    parser.add_argument("--status-block", action="store_true", help="print status block Markdown")
    parser.add_argument("--validate", action="store_true", help="validate generated artifacts and deterministic rendering")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    rendered: Dict[Path, str] | None = None
    if args.generate:
        rendered = write_artifacts()
        print(f"generated {len(rendered)} artifacts with prefix {ARTIFACT_PREFIX}")

    if args.acceptance:
        rendered = rendered or render_artifacts()
        print(rendered[RESULT_PATH], end="")

    if args.active_surface:
        rendered = rendered or render_artifacts()
        print(rendered[ACTIVE_SURFACE_PATH], end="")

    if args.disabled_surface:
        rendered = rendered or render_artifacts()
        print(rendered[DISABLED_SURFACE_PATH], end="")

    if args.completion_summary:
        rendered = rendered or render_artifacts()
        print(rendered[COMPLETION_SUMMARY_PATH], end="")

    if args.status_block:
        rendered = rendered or render_artifacts()
        print(rendered[STATUS_BLOCK_PATH], end="")

    if args.validate:
        ok, mismatches = validate_artifacts(rendered)
        if ok:
            print("P520K_ACTIVE_AFTERINSERT_SURFACE_ACCEPTANCE_VALIDATE_OK")
        else:
            for mismatch in mismatches:
                print(mismatch, file=sys.stderr)
            return 1

    if not any(
        (
            args.generate,
            args.acceptance,
            args.active_surface,
            args.disabled_surface,
            args.completion_summary,
            args.status_block,
            args.validate,
        )
    ):
        parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
