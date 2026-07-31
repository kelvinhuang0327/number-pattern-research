#!/usr/bin/env python3
"""P520I source/AST/text-only static binding resolver for ingest hook references.

This module reads committed P520H/P520G/P520F/P520E artifacts and parses source
as text/AST only. It does not import ``lottery_api.routes.ingest``, does not
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
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
INGEST_ROUTE_PATH = PROJECT_ROOT / "lottery_api" / "routes" / "ingest.py"

ARTIFACT_PREFIX = "P520I_ingest_afterinsert_hook_static_binding_resolver"

RESULT_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_result.json"
BINDING_CHAIN_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_binding_chain.csv"
INSPECTED_FILES_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_inspected_files.csv"
UNRESOLVED_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_unresolved.csv"
STATUS_BLOCK_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_status_block.md"
MANIFEST_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_manifest.csv"

P520H_RESULT_PATH = ARTIFACTS_DIR / "P520H_ingest_afterinsert_hook_import_chain_resolver_result.json"
P520H_UNRESOLVED_PATH = ARTIFACTS_DIR / "P520H_ingest_afterinsert_hook_import_chain_resolver_unresolved.csv"
P520H_MATRIX_PATH = ARTIFACTS_DIR / "P520H_ingest_afterinsert_hook_import_chain_resolver_matrix.csv"
P520G_RESULT_PATH = ARTIFACTS_DIR / "P520G_ingest_afterinsert_hook_candidate_triage_result.json"
P520F_RESULT_PATH = ARTIFACTS_DIR / "P520F_ingest_afterinsert_hook_candidate_resolver_result.json"
P520E_RESULT_PATH = ARTIFACTS_DIR / "P520E_ingest_afterinsert_hook_target_audit_result.json"

MAX_FOLLOW_DEPTH = 5

NOTICE_LINES: Sequence[str] = (
    "source/AST/text-only static binding resolver",
    "reads committed P520H/P520G/P520F/P520E artifacts",
    "parses lottery_api/routes/ingest.py without importing it",
    "does not import live hook target modules",
    "does not execute after-insert hooks",
    "does not execute draw inserts",
    "no canonical DB open/write",
    "no migration/backfill",
    "no deploy",
    "does not implement or modify hooks",
    "does not modify prediction/strategy/scoring logic",
    "no betting/future prediction claims",
)

BINDING_CHAIN_FIELDS: Sequence[str] = (
    "hook_name",
    "original_p520h_status",
    "terminal_symbol_status",
    "ingest_call_site_line",
    "ingest_call_site_evidence",
    "import_statement_line",
    "import_statement_evidence",
    "import_kind",
    "import_module",
    "imported_symbol",
    "local_symbol",
    "alias_mapping",
    "binding_chain_steps",
    "source_files_inspected",
    "terminal_module",
    "terminal_symbol",
    "terminal_source_file_path",
    "terminal_definition_line",
    "terminal_definition_kind",
    "direct_definition_evidence",
    "unresolved_reason",
)

INSPECTED_FILES_FIELDS: Sequence[str] = (
    "hook_name",
    "depth",
    "module",
    "symbol",
    "candidate_path",
    "exists",
    "parsed",
    "inspection_kind",
    "evidence",
    "reason",
)

UNRESOLVED_FIELDS: Sequence[str] = (
    "hook_name",
    "original_p520h_status",
    "terminal_symbol_status",
    "import_module",
    "imported_symbol",
    "local_symbol",
    "ingest_call_site_line",
    "terminal_source_file_path",
    "reason",
    "reason_category",
    "recommended_next_action",
)

MANIFEST_FIELDS: Sequence[str] = ("artifact_path", "artifact_kind", "sha256", "bytes", "notes")


@dataclass(frozen=True)
class P520HReference:
    hook_name: str
    original_status: str
    import_module: str
    imported_symbol: str
    local_symbol: str
    call_line: str
    p520h_reason: str


@dataclass(frozen=True)
class ImportBinding:
    import_kind: str
    import_module: str
    imported_symbol: str
    local_symbol: str
    line: str
    evidence: str


@dataclass(frozen=True)
class CallEvidence:
    line: str
    evidence: str


@dataclass(frozen=True)
class BindingResolution:
    terminal_status: str
    terminal_module: str
    terminal_symbol: str
    terminal_source_file_path: str
    terminal_definition_line: str
    terminal_definition_kind: str
    direct_definition_evidence: str
    chain_steps: Tuple[str, ...]
    inspected_rows: Tuple[Dict[str, Any], ...]
    unresolved_reason: str
    reason_category: str


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


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _call_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


def _parse_python_file(path: Path) -> Tuple[str, ast.AST | None, str]:
    if not path.exists():
        return "", None, "source file missing"
    source = _read_text(path)
    try:
        return source, ast.parse(source, filename=str(path)), ""
    except SyntaxError as exc:
        return source, None, f"{exc.__class__.__name__}: {exc.msg}"


def _function_defs(tree: ast.AST) -> Dict[str, ast.AST]:
    return {
        node.name: node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _literal_str_sequence(node: ast.AST) -> Tuple[str, ...]:
    if not isinstance(node, (ast.List, ast.Tuple)):
        return ()
    values: List[str] = []
    for element in node.elts:
        if not isinstance(element, ast.Constant) or not isinstance(element.value, str):
            return ()
        values.append(element.value)
    return tuple(values)


def _p520h_references() -> List[P520HReference]:
    unresolved_rows = _load_csv_rows(P520H_UNRESOLVED_PATH)
    matrix_rows = _load_csv_rows(P520H_MATRIX_PATH)
    matrix_by_hook = {row.get("hook_name", ""): row for row in matrix_rows}

    references: List[P520HReference] = []
    for row in sorted(unresolved_rows, key=lambda item: item.get("hook_name", "")):
        hook_name = row.get("hook_name", "")
        matrix = matrix_by_hook.get(hook_name, {})
        references.append(
            P520HReference(
                hook_name=hook_name,
                original_status=row.get("status", ""),
                import_module=row.get("import_module", "") or matrix.get("import_module", ""),
                imported_symbol=row.get("imported_symbol", "") or matrix.get("imported_symbol", ""),
                local_symbol=row.get("local_symbol", "") or matrix.get("local_symbol", ""),
                call_line=row.get("ingest_call_site_line", "") or matrix.get("ingest_call_site_line", ""),
                p520h_reason=row.get("reason", ""),
            )
        )
    return references


def _find_calls(function_node: ast.AST | None, call_name: str, source: str) -> List[CallEvidence]:
    if function_node is None:
        return []
    calls: List[CallEvidence] = []
    for node in ast.walk(function_node):
        if isinstance(node, ast.Call) and _call_name(node.func) == call_name:
            calls.append(CallEvidence(line=_line(node), evidence=_node_source(source, node)))
    return sorted(calls, key=lambda call: int(call.line) if call.line.isdigit() else 0)


def _collect_import_bindings(function_node: ast.AST | None, source: str) -> Dict[str, ImportBinding]:
    bindings: Dict[str, ImportBinding] = {}
    if function_node is None:
        return bindings
    for node in ast.walk(function_node):
        if isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                if alias.name == "*":
                    continue
                local_symbol = alias.asname or alias.name
                bindings[local_symbol] = ImportBinding(
                    import_kind="ImportFrom",
                    import_module=node.module,
                    imported_symbol=alias.name,
                    local_symbol=local_symbol,
                    line=_line(node),
                    evidence=_node_source(source, node),
                )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                local_symbol = alias.asname or alias.name.split(".")[0]
                bindings[local_symbol] = ImportBinding(
                    import_kind="Import",
                    import_module=alias.name,
                    imported_symbol="",
                    local_symbol=local_symbol,
                    line=_line(node),
                    evidence=_node_source(source, node),
                )
    return bindings


def source_roots() -> List[Path]:
    return [PROJECT_ROOT, PROJECT_ROOT / "lottery_api"]


def module_path_candidates(module: str) -> List[Path]:
    module_rel = Path(*module.split("."))
    candidates: List[Path] = []
    for root in source_roots():
        candidates.extend((root / f"{module_rel}.py", root / module_rel / "__init__.py"))
    return candidates


def _module_to_package_init_candidates(module: str) -> List[Path]:
    parts = module.split(".")
    if len(parts) <= 1:
        return []
    package_rel = Path(*parts[:-1]) / "__init__.py"
    return [root / package_rel for root in source_roots()]


def _resolve_relative_module(current_module: str, imported_module: str | None, level: int) -> str:
    if level <= 0:
        return imported_module or ""
    parts = current_module.split(".")
    if len(parts) >= level:
        base = parts[: len(parts) - level]
    else:
        base = []
    if imported_module:
        base.extend(imported_module.split("."))
    return ".".join(part for part in base if part)


def _top_level_definitions(tree: ast.AST, symbol: str) -> List[ast.AST]:
    matches: List[ast.AST] = []
    for node in getattr(tree, "body", []):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == symbol:
            matches.append(node)
        elif isinstance(node, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == symbol for target in node.targets):
                matches.append(node)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == symbol:
            matches.append(node)
    return matches


def _literal_all(tree: ast.AST) -> Tuple[str, ...]:
    for node in getattr(tree, "body", []):
        if isinstance(node, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets):
                return _literal_str_sequence(node.value)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == "__all__":
            return _literal_str_sequence(node.value)
    return ()


def _name_aliases(tree: ast.AST, source: str) -> Dict[str, Tuple[str, ast.AST]]:
    aliases: Dict[str, Tuple[str, ast.AST]] = {}
    for node in getattr(tree, "body", []):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Name):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    aliases[target.id] = (node.value.id, node)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and isinstance(node.value, ast.Name):
            aliases[node.target.id] = (node.value.id, node)
    return aliases


def _reexports(tree: ast.AST, source: str, current_module: str, symbol: str) -> List[Tuple[str, str, ast.AST, str]]:
    rows: List[Tuple[str, str, ast.AST, str]] = []
    exported = _literal_all(tree)
    for node in getattr(tree, "body", []):
        if isinstance(node, ast.ImportFrom):
            module = _resolve_relative_module(current_module, node.module, node.level)
            if not module:
                continue
            for alias in node.names:
                if alias.name == "*":
                    continue
                local_symbol = alias.asname or alias.name
                if local_symbol == symbol and (not exported or symbol in exported):
                    evidence = _node_source(source, node)
                    rows.append((module, alias.name, node, evidence))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                local_symbol = alias.asname or alias.name.split(".")[0]
                if local_symbol == symbol and (not exported or symbol in exported):
                    evidence = _node_source(source, node)
                    rows.append((alias.name, "", node, evidence))
    return rows


def _inspect_row(
    *,
    hook_name: str,
    depth: int,
    module: str,
    symbol: str,
    candidate_path: Path,
    exists: bool,
    parsed: bool,
    inspection_kind: str,
    evidence: str = "",
    reason: str = "",
) -> Dict[str, Any]:
    return {
        "hook_name": hook_name,
        "depth": depth,
        "module": module,
        "symbol": symbol,
        "candidate_path": _artifact_label(candidate_path),
        "exists": str(bool(exists)),
        "parsed": str(bool(parsed)),
        "inspection_kind": inspection_kind,
        "evidence": evidence,
        "reason": reason,
    }


def _missing_resolution(
    *,
    hook_name: str,
    module: str,
    symbol: str,
    inspected_rows: List[Dict[str, Any]],
    chain_steps: List[str],
) -> BindingResolution:
    return BindingResolution(
        terminal_status="UNRESOLVED",
        terminal_module=module,
        terminal_symbol=symbol,
        terminal_source_file_path="",
        terminal_definition_line="",
        terminal_definition_kind="",
        direct_definition_evidence="",
        chain_steps=tuple(chain_steps),
        inspected_rows=tuple(inspected_rows),
        unresolved_reason="source file missing",
        reason_category="source file missing",
    )


def _resolve_symbol(
    *,
    hook_name: str,
    module: str,
    symbol: str,
    depth: int = 0,
    seen: frozenset[Tuple[str, str]] = frozenset(),
) -> BindingResolution:
    chain_steps = [f"{module}.{symbol}" if symbol else module]
    inspected_rows: List[Dict[str, Any]] = []
    key = (module, symbol)

    if not module or not symbol:
        return BindingResolution(
            terminal_status="UNRESOLVED",
            terminal_module=module,
            terminal_symbol=symbol,
            terminal_source_file_path="",
            terminal_definition_line="",
            terminal_definition_kind="",
            direct_definition_evidence="",
            chain_steps=tuple(chain_steps),
            inspected_rows=tuple(inspected_rows),
            unresolved_reason="runtime binding required",
            reason_category="runtime binding required",
        )

    if key in seen:
        return BindingResolution(
            terminal_status="UNRESOLVED",
            terminal_module=module,
            terminal_symbol=symbol,
            terminal_source_file_path="",
            terminal_definition_line="",
            terminal_definition_kind="",
            direct_definition_evidence="",
            chain_steps=tuple(chain_steps),
            inspected_rows=tuple(inspected_rows),
            unresolved_reason="ambiguous candidates",
            reason_category="ambiguous candidates",
        )

    if depth > MAX_FOLLOW_DEPTH:
        return BindingResolution(
            terminal_status="UNRESOLVED",
            terminal_module=module,
            terminal_symbol=symbol,
            terminal_source_file_path="",
            terminal_definition_line="",
            terminal_definition_kind="",
            direct_definition_evidence="",
            chain_steps=tuple(chain_steps),
            inspected_rows=tuple(inspected_rows),
            unresolved_reason="dynamic import required",
            reason_category="dynamic import required",
        )

    existing_paths: List[Path] = []
    for candidate in module_path_candidates(module):
        exists = candidate.exists()
        inspected_rows.append(
            _inspect_row(
                hook_name=hook_name,
                depth=depth,
                module=module,
                symbol=symbol,
                candidate_path=candidate,
                exists=exists,
                parsed=False,
                inspection_kind="module-path-candidate",
                reason="" if exists else "source file missing",
            )
        )
        if exists:
            existing_paths.append(candidate)

    if not existing_paths:
        for candidate in _module_to_package_init_candidates(module):
            exists = candidate.exists()
            inspected_rows.append(
                _inspect_row(
                    hook_name=hook_name,
                    depth=depth,
                    module=module,
                    symbol=symbol,
                    candidate_path=candidate,
                    exists=exists,
                    parsed=False,
                    inspection_kind="package-init-reexport-candidate",
                    reason="" if exists else "source file missing",
                )
            )
            if exists:
                existing_paths.append(candidate)

    if not existing_paths:
        return _missing_resolution(
            hook_name=hook_name,
            module=module,
            symbol=symbol,
            inspected_rows=inspected_rows,
            chain_steps=chain_steps,
        )

    if len(existing_paths) > 1:
        return BindingResolution(
            terminal_status="UNRESOLVED",
            terminal_module=module,
            terminal_symbol=symbol,
            terminal_source_file_path=";".join(_artifact_label(path) for path in existing_paths),
            terminal_definition_line="",
            terminal_definition_kind="",
            direct_definition_evidence="",
            chain_steps=tuple(chain_steps),
            inspected_rows=tuple(inspected_rows),
            unresolved_reason="ambiguous candidates",
            reason_category="ambiguous candidates",
        )

    source_path = existing_paths[0]
    source, tree, parse_error = _parse_python_file(source_path)
    inspected_rows.append(
        _inspect_row(
            hook_name=hook_name,
            depth=depth,
            module=module,
            symbol=symbol,
            candidate_path=source_path,
            exists=True,
            parsed=tree is not None,
            inspection_kind="source-ast-parse",
            reason=parse_error,
        )
    )
    if tree is None:
        return BindingResolution(
            terminal_status="UNRESOLVED",
            terminal_module=module,
            terminal_symbol=symbol,
            terminal_source_file_path=_artifact_label(source_path),
            terminal_definition_line="",
            terminal_definition_kind="",
            direct_definition_evidence="",
            chain_steps=tuple(chain_steps),
            inspected_rows=tuple(inspected_rows),
            unresolved_reason="source file missing" if parse_error == "source file missing" else "dynamic import required",
            reason_category="source file missing" if parse_error == "source file missing" else "dynamic import required",
        )

    definitions = _top_level_definitions(tree, symbol)
    if len(definitions) == 1:
        node = definitions[0]
        return BindingResolution(
            terminal_status="CONFIRMED",
            terminal_module=module,
            terminal_symbol=symbol,
            terminal_source_file_path=_artifact_label(source_path),
            terminal_definition_line=_line(node),
            terminal_definition_kind=type(node).__name__,
            direct_definition_evidence=_node_source(source, node),
            chain_steps=tuple(chain_steps),
            inspected_rows=tuple(inspected_rows),
            unresolved_reason="",
            reason_category="",
        )
    if len(definitions) > 1:
        return BindingResolution(
            terminal_status="UNRESOLVED",
            terminal_module=module,
            terminal_symbol=symbol,
            terminal_source_file_path=_artifact_label(source_path),
            terminal_definition_line="",
            terminal_definition_kind="",
            direct_definition_evidence="",
            chain_steps=tuple(chain_steps),
            inspected_rows=tuple(inspected_rows),
            unresolved_reason="ambiguous candidates",
            reason_category="ambiguous candidates",
        )

    aliases = _name_aliases(tree, source)
    if symbol in aliases:
        next_symbol, node = aliases[symbol]
        followed = _resolve_symbol(
            hook_name=hook_name,
            module=module,
            symbol=next_symbol,
            depth=depth + 1,
            seen=seen | {key},
        )
        step = f"{module}.{symbol} = {next_symbol}"
        return BindingResolution(
            terminal_status=followed.terminal_status,
            terminal_module=followed.terminal_module,
            terminal_symbol=followed.terminal_symbol,
            terminal_source_file_path=followed.terminal_source_file_path or _artifact_label(source_path),
            terminal_definition_line=followed.terminal_definition_line or _line(node),
            terminal_definition_kind=followed.terminal_definition_kind or type(node).__name__,
            direct_definition_evidence=followed.direct_definition_evidence or _node_source(source, node),
            chain_steps=tuple(chain_steps + [step] + list(followed.chain_steps)),
            inspected_rows=tuple(inspected_rows + list(followed.inspected_rows)),
            unresolved_reason=followed.unresolved_reason,
            reason_category=followed.reason_category,
        )

    reexports = _reexports(tree, source, module, symbol)
    if len(reexports) == 1:
        next_module, next_symbol, node, evidence = reexports[0]
        if not next_symbol:
            return BindingResolution(
                terminal_status="PROBABLE",
                terminal_module=next_module,
                terminal_symbol=next_symbol,
                terminal_source_file_path=_artifact_label(source_path),
                terminal_definition_line=_line(node),
                terminal_definition_kind=type(node).__name__,
                direct_definition_evidence=evidence,
                chain_steps=tuple(chain_steps + [f"{module}.{symbol} -> {next_module}"]),
                inspected_rows=tuple(inspected_rows),
                unresolved_reason="runtime binding required",
                reason_category="runtime binding required",
            )
        followed = _resolve_symbol(
            hook_name=hook_name,
            module=next_module,
            symbol=next_symbol,
            depth=depth + 1,
            seen=seen | {key},
        )
        step = f"{module}.{symbol} -> {next_module}.{next_symbol}"
        return BindingResolution(
            terminal_status=followed.terminal_status,
            terminal_module=followed.terminal_module,
            terminal_symbol=followed.terminal_symbol,
            terminal_source_file_path=followed.terminal_source_file_path or _artifact_label(source_path),
            terminal_definition_line=followed.terminal_definition_line or _line(node),
            terminal_definition_kind=followed.terminal_definition_kind or type(node).__name__,
            direct_definition_evidence=followed.direct_definition_evidence or evidence,
            chain_steps=tuple(chain_steps + [step] + list(followed.chain_steps)),
            inspected_rows=tuple(inspected_rows + list(followed.inspected_rows)),
            unresolved_reason=followed.unresolved_reason,
            reason_category=followed.reason_category,
        )
    if len(reexports) > 1:
        return BindingResolution(
            terminal_status="UNRESOLVED",
            terminal_module=module,
            terminal_symbol=symbol,
            terminal_source_file_path=_artifact_label(source_path),
            terminal_definition_line="",
            terminal_definition_kind="",
            direct_definition_evidence="",
            chain_steps=tuple(chain_steps),
            inspected_rows=tuple(inspected_rows),
            unresolved_reason="ambiguous candidates",
            reason_category="ambiguous candidates",
        )

    return BindingResolution(
        terminal_status="UNRESOLVED",
        terminal_module=module,
        terminal_symbol=symbol,
        terminal_source_file_path=_artifact_label(source_path),
        terminal_definition_line="",
        terminal_definition_kind="",
        direct_definition_evidence="",
        chain_steps=tuple(chain_steps),
        inspected_rows=tuple(inspected_rows),
        unresolved_reason="symbol not found",
        reason_category="symbol not found",
    )


def _binding_for_reference(reference: P520HReference, bindings: Mapping[str, ImportBinding]) -> ImportBinding | None:
    binding = bindings.get(reference.local_symbol)
    if binding is not None:
        return binding
    for candidate in bindings.values():
        if (
            candidate.import_module == reference.import_module
            and candidate.imported_symbol == reference.imported_symbol
            and candidate.local_symbol == reference.local_symbol
        ):
            return candidate
    return None


def _build_bundle() -> Dict[str, Any]:
    ingest_source, ingest_tree, parse_error = _parse_python_file(INGEST_ROUTE_PATH)
    refresh_function = _function_defs(ingest_tree).get("_refresh_after_insert") if ingest_tree else None
    bindings = _collect_import_bindings(refresh_function, ingest_source)
    references = _p520h_references()

    binding_rows: List[Dict[str, Any]] = []
    inspected_rows: List[Dict[str, Any]] = []
    unresolved_rows: List[Dict[str, Any]] = []

    for reference in references:
        binding = _binding_for_reference(reference, bindings)
        local_symbol = binding.local_symbol if binding else reference.local_symbol
        calls = _find_calls(refresh_function, local_symbol, ingest_source)
        call = calls[0] if calls else CallEvidence(line=reference.call_line, evidence="")
        if binding is None:
            resolution = BindingResolution(
                terminal_status="UNRESOLVED",
                terminal_module=reference.import_module,
                terminal_symbol=reference.imported_symbol,
                terminal_source_file_path="",
                terminal_definition_line="",
                terminal_definition_kind="",
                direct_definition_evidence="",
                chain_steps=(f"ingest local symbol {reference.local_symbol} has no static import binding",),
                inspected_rows=(),
                unresolved_reason="runtime binding required",
                reason_category="runtime binding required",
            )
        else:
            resolution = _resolve_symbol(
                hook_name=reference.hook_name,
                module=binding.import_module,
                symbol=binding.imported_symbol,
            )

        inspected_rows.extend(resolution.inspected_rows)
        source_files_inspected = ";".join(
            row["candidate_path"]
            for row in resolution.inspected_rows
            if row.get("exists") == "True" and row.get("inspection_kind") in {"source-ast-parse", "package-init-reexport-candidate"}
        )
        if not source_files_inspected:
            source_files_inspected = ";".join(
                row["candidate_path"] for row in resolution.inspected_rows if row.get("inspection_kind") == "module-path-candidate"
            )
        alias_mapping = ""
        if binding is not None and binding.imported_symbol and binding.local_symbol != binding.imported_symbol:
            alias_mapping = f"{binding.imported_symbol} as {binding.local_symbol}"

        binding_rows.append(
            {
                "hook_name": reference.hook_name,
                "original_p520h_status": reference.original_status,
                "terminal_symbol_status": resolution.terminal_status,
                "ingest_call_site_line": call.line,
                "ingest_call_site_evidence": call.evidence,
                "import_statement_line": binding.line if binding else "",
                "import_statement_evidence": binding.evidence if binding else "",
                "import_kind": binding.import_kind if binding else "",
                "import_module": binding.import_module if binding else reference.import_module,
                "imported_symbol": binding.imported_symbol if binding else reference.imported_symbol,
                "local_symbol": local_symbol,
                "alias_mapping": alias_mapping,
                "binding_chain_steps": " | ".join(resolution.chain_steps),
                "source_files_inspected": source_files_inspected,
                "terminal_module": resolution.terminal_module,
                "terminal_symbol": resolution.terminal_symbol,
                "terminal_source_file_path": resolution.terminal_source_file_path,
                "terminal_definition_line": resolution.terminal_definition_line,
                "terminal_definition_kind": resolution.terminal_definition_kind,
                "direct_definition_evidence": resolution.direct_definition_evidence,
                "unresolved_reason": resolution.unresolved_reason,
            }
        )
        if resolution.terminal_status != "CONFIRMED":
            unresolved_rows.append(
                {
                    "hook_name": reference.hook_name,
                    "original_p520h_status": reference.original_status,
                    "terminal_symbol_status": resolution.terminal_status,
                    "import_module": binding.import_module if binding else reference.import_module,
                    "imported_symbol": binding.imported_symbol if binding else reference.imported_symbol,
                    "local_symbol": local_symbol,
                    "ingest_call_site_line": call.line,
                    "terminal_source_file_path": resolution.terminal_source_file_path,
                    "reason": resolution.unresolved_reason,
                    "reason_category": resolution.reason_category,
                    "recommended_next_action": "source-path-followup-required",
                }
            )

    status_counts = {
        "CONFIRMED": sum(1 for row in binding_rows if row["terminal_symbol_status"] == "CONFIRMED"),
        "PROBABLE": sum(1 for row in binding_rows if row["terminal_symbol_status"] == "PROBABLE"),
        "UNRESOLVED": sum(1 for row in binding_rows if row["terminal_symbol_status"] == "UNRESOLVED"),
    }
    missing_artifacts = [
        path
        for path in (P520H_RESULT_PATH, P520H_UNRESOLVED_PATH, P520H_MATRIX_PATH, P520G_RESULT_PATH, P520F_RESULT_PATH, P520E_RESULT_PATH)
        if not path.exists()
    ]
    failures = [f"missing artifact: {_artifact_label(path)}" for path in missing_artifacts]
    if parse_error:
        failures.append(f"ingest source parse failed: {parse_error}")
    warnings = [
        f"{row['hook_name']}: {row['unresolved_reason']}"
        for row in binding_rows
        if row["terminal_symbol_status"] != "CONFIRMED"
    ]

    final_status = "FAIL" if failures else "PASS" if not warnings else "WARN"
    p520h_result = _load_json(P520H_RESULT_PATH)
    p520g_result = _load_json(P520G_RESULT_PATH)
    p520f_result = _load_json(P520F_RESULT_PATH)
    p520e_result = _load_json(P520E_RESULT_PATH)

    result = {
        "artifact_prefix": ARTIFACT_PREFIX,
        "final_status": final_status,
        "source_path": _artifact_label(INGEST_ROUTE_PATH),
        "max_follow_depth": MAX_FOLLOW_DEPTH,
        "focused_reference_count": len(references),
        "binding_chain_row_count": len(binding_rows),
        "inspected_file_row_count": len(inspected_rows),
        "unresolved_summary_row_count": len(unresolved_rows),
        "confirmed_hook_count": status_counts["CONFIRMED"],
        "probable_hook_count": status_counts["PROBABLE"],
        "unresolved_hook_count": status_counts["UNRESOLVED"],
        "status_counts": status_counts,
        "confirmed_hooks": sorted(row["hook_name"] for row in binding_rows if row["terminal_symbol_status"] == "CONFIRMED"),
        "probable_hooks": sorted(row["hook_name"] for row in binding_rows if row["terminal_symbol_status"] == "PROBABLE"),
        "unresolved_hooks": sorted(row["hook_name"] for row in binding_rows if row["terminal_symbol_status"] == "UNRESOLVED"),
        "unresolved_reasons": sorted({row["reason_category"] for row in unresolved_rows if row["reason_category"]}),
        "component_statuses": {
            "P520H result artifact read": "PASS" if P520H_RESULT_PATH.exists() else "FAIL",
            "P520H unresolved artifact read": "PASS" if P520H_UNRESOLVED_PATH.exists() else "FAIL",
            "P520H matrix artifact read": "PASS" if P520H_MATRIX_PATH.exists() else "FAIL",
            "P520G artifact context read": "PASS" if P520G_RESULT_PATH.exists() else "WARN",
            "P520F artifact context read": "PASS" if P520F_RESULT_PATH.exists() else "WARN",
            "P520E artifact context read": "PASS" if P520E_RESULT_PATH.exists() else "WARN",
            "ingest source AST evaluation": "PASS" if not parse_error else "FAIL",
            "static binding resolution": "WARN" if warnings else "PASS",
            "runtime import avoided": "PASS",
            "DB side effects avoided": "PASS",
            "target confirmation conservative": "PASS",
        },
        "p520h_summary": {
            "result_artifact": _artifact_label(P520H_RESULT_PATH),
            "result_present": P520H_RESULT_PATH.exists(),
            "final_status": p520h_result.get("final_status", ""),
            "probable_hook_count": p520h_result.get("probable_hook_count", ""),
            "target_source_unresolved_count": p520h_result.get("target_source_unresolved_count", ""),
        },
        "p520g_summary": {
            "result_artifact": _artifact_label(P520G_RESULT_PATH),
            "result_present": P520G_RESULT_PATH.exists(),
            "final_status": p520g_result.get("final_status", ""),
            "probable_upgrade_count": p520g_result.get("probable_upgrade_count", ""),
        },
        "p520f_summary": {
            "result_artifact": _artifact_label(P520F_RESULT_PATH),
            "result_present": P520F_RESULT_PATH.exists(),
            "final_status": p520f_result.get("final_status", ""),
            "candidate_count": p520f_result.get("candidate_count", ""),
        },
        "p520e_summary": {
            "result_artifact": _artifact_label(P520E_RESULT_PATH),
            "result_present": P520E_RESULT_PATH.exists(),
            "final_status": p520e_result.get("final_status", ""),
            "unresolved_source_count": p520e_result.get("unresolved_source_count", ""),
        },
        "pass_count": 0,
        "warn_count": len(warnings),
        "fail_count": len(failures),
        "warning_count": len(warnings),
        "warnings": warnings,
        "failure_count": len(failures),
        "failures": failures,
        "notices": list(NOTICE_LINES),
        "scope": (
            "P520I reads committed P520H/P520G/P520F/P520E artifacts, parses "
            "lottery_api/routes/ingest.py, follows direct import/alias/from-import/module-assignment/"
            "__init__.py re-export/static __all__ chains up to depth 5 as source/AST/text only; "
            "no app runtime import; no live target module import; no after-insert hook execution; "
            "no draw insert execution; no canonical DB open/write; no migration/backfill; no deploy."
        ),
        "suggested_next_command": "python -m tools.ingest_afterinsert_hook_static_binding_resolver --status-block",
    }
    return {
        "result": result,
        "binding_chain": sorted(binding_rows, key=lambda row: row["hook_name"]),
        "inspected_files": sorted(
            inspected_rows,
            key=lambda row: (
                row["hook_name"],
                int(row["depth"]) if str(row["depth"]).isdigit() else 0,
                row["candidate_path"],
                row["inspection_kind"],
            ),
        ),
        "unresolved": sorted(unresolved_rows, key=lambda row: row["hook_name"]),
    }


def _status_block(result: Mapping[str, Any]) -> str:
    lines = [
        "# P520I ingest after-insert hook static binding resolver status",
        "",
        f"- Final status: `{result['final_status']}`",
        f"- Focused P520H unresolved probable reference count: `{result['focused_reference_count']}`",
        f"- Confirmed hook count: `{result['confirmed_hook_count']}`",
        f"- Probable hook count: `{result['probable_hook_count']}`",
        f"- Unresolved hook count: `{result['unresolved_hook_count']}`",
        f"- Binding chain rows: `{result['binding_chain_row_count']}`",
        f"- Inspected file rows: `{result['inspected_file_row_count']}`",
        f"- Unresolved summary rows: `{result['unresolved_summary_row_count']}`",
        f"- PASS/WARN/FAIL counts: `{result['pass_count']}/{result['warn_count']}/{result['fail_count']}`",
        "",
        "## Status Summary",
        f"- Confirmed: `{';'.join(result['confirmed_hooks'])}`",
        f"- Probable: `{';'.join(result['probable_hooks'])}`",
        f"- Unresolved: `{';'.join(result['unresolved_hooks'])}`",
        f"- Unresolved reasons: `{';'.join(result['unresolved_reasons'])}`",
        "",
        "## Scope notices",
    ]
    lines.extend(f"- {notice}" for notice in NOTICE_LINES)
    lines.extend(
        [
            "",
            "## Recommendation",
            "- No hook target is confirmed unless direct, unambiguous static source evidence exists.",
            "- The P520H probable references remain terminally unresolved when target source files are missing from static module path candidates.",
            "- Runtime import, hook execution, draw insertion, DB access, migration, backfill, and deploy were not attempted.",
        ]
    )
    return "\n".join(lines) + "\n"


def build_static_binding_bundle() -> Dict[str, Any]:
    bundle = _build_bundle()
    bundle["status_block"] = _status_block(bundle["result"])
    return bundle


def _manifest_rows(rendered: Mapping[Path, str]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for path in (RESULT_PATH, BINDING_CHAIN_PATH, INSPECTED_FILES_PATH, UNRESOLVED_PATH, STATUS_BLOCK_PATH):
        text = rendered[path]
        data = text.encode("utf-8")
        rows.append(
            {
                "artifact_path": _artifact_label(path),
                "artifact_kind": path.suffix.lstrip("."),
                "sha256": _sha256_bytes(data),
                "bytes": len(data),
                "notes": "generated by source/AST-only P520I static binding resolver",
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
    bundle = build_static_binding_bundle()
    rendered: Dict[Path, str] = {
        RESULT_PATH: _json_text(bundle["result"]),
        BINDING_CHAIN_PATH: _csv_text(bundle["binding_chain"], BINDING_CHAIN_FIELDS),
        INSPECTED_FILES_PATH: _csv_text(bundle["inspected_files"], INSPECTED_FILES_FIELDS),
        UNRESOLVED_PATH: _csv_text(bundle["unresolved"], UNRESOLVED_FIELDS),
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
    if rendered != render_artifacts():
        mismatches.append("deterministic double-run render mismatch")
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
    parser.add_argument("--generate", action="store_true", help="write all P520I static binding resolver artifacts")
    parser.add_argument("--binding-chain", action="store_true", help="print binding chain matrix CSV")
    parser.add_argument("--inspected-files", action="store_true", help="print inspected files CSV")
    parser.add_argument("--unresolved", action="store_true", help="print unresolved reasons CSV")
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

    if args.binding_chain:
        rendered = rendered or render_artifacts()
        print(rendered[BINDING_CHAIN_PATH], end="")

    if args.inspected_files:
        rendered = rendered or render_artifacts()
        print(rendered[INSPECTED_FILES_PATH], end="")

    if args.unresolved:
        rendered = rendered or render_artifacts()
        print(rendered[UNRESOLVED_PATH], end="")

    if args.status_block:
        rendered = rendered or render_artifacts()
        print(rendered[STATUS_BLOCK_PATH], end="")

    if args.validate:
        ok, mismatches = validate_artifacts(rendered)
        if ok:
            print("P520I_STATIC_BINDING_RESOLVER_VALIDATE_OK")
        else:
            for mismatch in mismatches:
                print(mismatch, file=sys.stderr)
            return 1

    if not any((args.generate, args.binding_chain, args.inspected_files, args.unresolved, args.status_block, args.validate)):
        parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
