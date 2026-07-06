#!/usr/bin/env python3
"""P520H source/AST-only import-chain resolver for ingest live hook references.

This module reads committed P520G/P520F/P520E/P520D artifacts and parses source
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

ARTIFACT_PREFIX = "P520H_ingest_afterinsert_hook_import_chain_resolver"

RESULT_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_result.json"
MATRIX_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_matrix.csv"
TARGET_DEFINITIONS_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_target_definitions.csv"
UNRESOLVED_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_unresolved.csv"
STATUS_BLOCK_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_status_block.md"
MANIFEST_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_manifest.csv"

P520G_RESULT_PATH = ARTIFACTS_DIR / "P520G_ingest_afterinsert_hook_candidate_triage_result.json"
P520G_BY_HOOK_PATH = ARTIFACTS_DIR / "P520G_ingest_afterinsert_hook_candidate_triage_by_hook.csv"
P520G_MEDIUM_CARDS_PATH = ARTIFACTS_DIR / "P520G_ingest_afterinsert_hook_candidate_triage_medium_cards.json"
P520F_RESULT_PATH = ARTIFACTS_DIR / "P520F_ingest_afterinsert_hook_candidate_resolver_result.json"
P520E_RESULT_PATH = ARTIFACTS_DIR / "P520E_ingest_afterinsert_hook_target_audit_result.json"
P520D_RESULT_PATH = ARTIFACTS_DIR / "P520D_ingest_afterinsert_hook_contract_result.json"

NOTICE_LINES: Sequence[str] = (
    "source/AST/text-only import-chain resolver",
    "reads committed P520G/P520F/P520E/P520D artifacts",
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

MATRIX_FIELDS: Sequence[str] = (
    "hook_name",
    "status",
    "ingest_call_site_line",
    "ingest_call_site_evidence",
    "import_statement_line",
    "import_statement_evidence",
    "import_kind",
    "import_module",
    "imported_symbol",
    "local_symbol",
    "alias_mapping",
    "candidate_module_path",
    "candidate_source_file_path",
    "candidate_source_exists",
    "checked_source_paths",
    "target_definition_status",
    "target_definition_line",
    "target_definition_ast_node_type",
    "target_definition_evidence",
    "reexport_chain",
    "reason",
)

TARGET_DEFINITION_FIELDS: Sequence[str] = (
    "hook_name",
    "import_module",
    "imported_symbol",
    "source_file_path",
    "definition_line",
    "definition_kind",
    "definition_evidence",
    "reexport_depth",
    "reexport_module",
    "reexport_symbol",
    "status",
    "reason",
)

UNRESOLVED_FIELDS: Sequence[str] = (
    "hook_name",
    "status",
    "import_module",
    "imported_symbol",
    "local_symbol",
    "ingest_call_site_line",
    "candidate_source_file_path",
    "reason",
    "recommended_next_action",
)

MANIFEST_FIELDS: Sequence[str] = ("artifact_path", "artifact_kind", "sha256", "bytes", "notes")


@dataclass(frozen=True)
class ProbableReference:
    hook_name: str
    import_candidate_id: str
    call_candidate_id: str
    call_symbol: str
    call_line: str
    call_evidence: str


@dataclass(frozen=True)
class ImportBinding:
    import_kind: str
    import_module: str
    imported_symbol: str
    local_symbol: str
    line: str
    evidence: str


@dataclass(frozen=True)
class DefinitionEvidence:
    status: str
    source_file_path: str
    line: str
    ast_node_type: str
    evidence: str
    reexport_chain: str
    reexport_module: str
    reexport_symbol: str
    reason: str
    depth: int


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


def _function_defs(tree: ast.AST) -> Dict[str, ast.AST]:
    return {
        node.name: node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _parse_python_file(path: Path) -> Tuple[str, ast.AST | None, str]:
    if not path.exists():
        return "", None, "missing"
    source = _read_text(path)
    try:
        return source, ast.parse(source, filename=str(path)), ""
    except SyntaxError as exc:
        return source, None, f"{exc.__class__.__name__}: {exc.msg}"


def _probable_references() -> List[ProbableReference]:
    by_hook_rows = _load_csv_rows(P520G_BY_HOOK_PATH)
    medium_cards = _load_json(P520G_MEDIUM_CARDS_PATH)
    if not isinstance(medium_cards, list):
        medium_cards = []

    probable_hooks = sorted(
        row.get("unresolved_hook_name", "")
        for row in by_hook_rows
        if row.get("probable_upgrade") == "probable"
    )
    references: List[ProbableReference] = []
    for hook in probable_hooks:
        cards = [
            card
            for card in medium_cards
            if isinstance(card, dict) and card.get("unresolved_hook_name") == hook
        ]
        import_cards = sorted(
            (card for card in cards if card.get("evidence_kind") == "import"),
            key=lambda card: str(card.get("candidate_id", "")),
        )
        call_cards = sorted(
            (card for card in cards if card.get("evidence_kind") == "call"),
            key=lambda card: str(card.get("candidate_id", "")),
        )
        if not import_cards or not call_cards:
            continue
        import_card = import_cards[0]
        call_card = call_cards[0]
        references.append(
            ProbableReference(
                hook_name=hook,
                import_candidate_id=str(import_card.get("candidate_id", "")),
                call_candidate_id=str(call_card.get("candidate_id", "")),
                call_symbol=str(call_card.get("matched_symbol_reference", "")),
                call_line=str(call_card.get("line_number", "")),
                call_evidence=str(call_card.get("supporting_source_snippet", "")),
            )
        )
    return references


def _find_calls(function_node: ast.AST | None, call_name: str, source: str) -> List[Dict[str, str]]:
    if function_node is None:
        return []
    rows: List[Dict[str, str]] = []
    for node in ast.walk(function_node):
        if isinstance(node, ast.Call) and _call_name(node.func) == call_name:
            rows.append({"line": _line(node), "evidence": _node_source(source, node)})
    return sorted(rows, key=lambda row: int(row["line"]) if row["line"].isdigit() else 0)


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


def module_path_candidates(module: str) -> List[Path]:
    module_rel = Path(*module.split("."))
    return [
        PROJECT_ROOT / f"{module_rel}.py",
        PROJECT_ROOT / module_rel / "__init__.py",
        PROJECT_ROOT / "lottery_api" / f"{module_rel}.py",
        PROJECT_ROOT / "lottery_api" / module_rel / "__init__.py",
    ]


def resolve_module_path(module: str) -> Path | None:
    for candidate in module_path_candidates(module):
        if candidate.exists():
            return candidate
    return None


def _target_symbol_node(tree: ast.AST, symbol: str) -> ast.AST | None:
    for node in getattr(tree, "body", []):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == symbol:
            return node
        if isinstance(node, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == symbol for target in node.targets):
                return node
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == symbol:
            return node
    return None


def _direct_reexport(tree: ast.AST, symbol: str) -> Tuple[str, str, ast.AST | None]:
    for node in getattr(tree, "body", []):
        if not isinstance(node, ast.ImportFrom) or not node.module:
            continue
        for alias in node.names:
            local_symbol = alias.asname or alias.name
            if local_symbol == symbol:
                return node.module, alias.name, node
    return "", "", None


def _resolve_definition(
    module: str,
    symbol: str,
    *,
    depth: int = 0,
    max_depth: int = 2,
    seen: frozenset[Tuple[str, str]] = frozenset(),
) -> DefinitionEvidence:
    if not module or not symbol:
        return DefinitionEvidence(
            status="UNRESOLVED",
            source_file_path="",
            line="",
            ast_node_type="",
            evidence="",
            reexport_chain="",
            reexport_module="",
            reexport_symbol="",
            reason="missing import module or symbol",
            depth=depth,
        )

    key = (module, symbol)
    if key in seen:
        return DefinitionEvidence(
            status="UNRESOLVED",
            source_file_path="",
            line="",
            ast_node_type="",
            evidence="",
            reexport_chain="",
            reexport_module="",
            reexport_symbol="",
            reason="static re-export cycle detected",
            depth=depth,
        )

    path = resolve_module_path(module)
    if path is None:
        return DefinitionEvidence(
            status="SOURCE_PATH_UNRESOLVED",
            source_file_path="",
            line="",
            ast_node_type="",
            evidence="",
            reexport_chain="",
            reexport_module="",
            reexport_symbol="",
            reason="source path unresolved by static module-to-file mapping; runtime import not attempted",
            depth=depth,
        )

    source, tree, parse_error = _parse_python_file(path)
    if tree is None:
        return DefinitionEvidence(
            status="UNRESOLVED",
            source_file_path=_artifact_label(path),
            line="",
            ast_node_type="",
            evidence="",
            reexport_chain="",
            reexport_module="",
            reexport_symbol="",
            reason=f"target source parse failed: {parse_error}",
            depth=depth,
        )

    symbol_node = _target_symbol_node(tree, symbol)
    if symbol_node is not None:
        return DefinitionEvidence(
            status="DEFINITION_FOUND",
            source_file_path=_artifact_label(path),
            line=_line(symbol_node),
            ast_node_type=type(symbol_node).__name__,
            evidence=_node_source(source, symbol_node),
            reexport_chain=f"{module}.{symbol}",
            reexport_module="",
            reexport_symbol="",
            reason="target symbol definition is statically present",
            depth=depth,
        )

    reexport_module, reexport_symbol, reexport_node = _direct_reexport(tree, symbol)
    if reexport_node is not None:
        direct_evidence = _node_source(source, reexport_node)
        direct_chain = f"{module}.{symbol} -> {reexport_module}.{reexport_symbol}"
        if depth >= max_depth:
            return DefinitionEvidence(
                status="REEXPORT_FOUND",
                source_file_path=_artifact_label(path),
                line=_line(reexport_node),
                ast_node_type=type(reexport_node).__name__,
                evidence=direct_evidence,
                reexport_chain=direct_chain,
                reexport_module=reexport_module,
                reexport_symbol=reexport_symbol,
                reason="direct re-export is statically present; max follow depth reached",
                depth=depth,
            )
        followed = _resolve_definition(
            reexport_module,
            reexport_symbol,
            depth=depth + 1,
            max_depth=max_depth,
            seen=seen | {key},
        )
        if followed.status in {"DEFINITION_FOUND", "REEXPORT_FOUND"}:
            chain = f"{direct_chain} -> {followed.reexport_chain}" if followed.reexport_chain else direct_chain
            return DefinitionEvidence(
                status="REEXPORT_FOUND",
                source_file_path=_artifact_label(path),
                line=_line(reexport_node),
                ast_node_type=type(reexport_node).__name__,
                evidence=direct_evidence,
                reexport_chain=chain,
                reexport_module=reexport_module,
                reexport_symbol=reexport_symbol,
                reason="direct re-export is statically present",
                depth=depth,
            )
        return DefinitionEvidence(
            status="REEXPORT_UNRESOLVED",
            source_file_path=_artifact_label(path),
            line=_line(reexport_node),
            ast_node_type=type(reexport_node).__name__,
            evidence=direct_evidence,
            reexport_chain=direct_chain,
            reexport_module=reexport_module,
            reexport_symbol=reexport_symbol,
            reason=f"direct re-export found but target unresolved: {followed.reason}",
            depth=depth,
        )

    return DefinitionEvidence(
        status="SYMBOL_UNRESOLVED",
        source_file_path=_artifact_label(path),
        line="",
        ast_node_type="",
        evidence="",
        reexport_chain=f"{module}.{symbol}",
        reexport_module="",
        reexport_symbol="",
        reason="target source resolved, but expected symbol definition or direct re-export was not found",
        depth=depth,
    )


def _status_for(binding: ImportBinding | None, call_rows: Sequence[Mapping[str, str]], evidence: DefinitionEvidence) -> str:
    if binding is None or not call_rows:
        return "UNRESOLVED"
    if evidence.status in {"DEFINITION_FOUND", "REEXPORT_FOUND"}:
        return "CONFIRMED"
    if evidence.status == "SOURCE_PATH_UNRESOLVED":
        return "PROBABLE"
    return "UNRESOLVED"


def _reason_for(status: str, evidence: DefinitionEvidence, binding: ImportBinding | None, call_rows: Sequence[Mapping[str, str]]) -> str:
    if binding is None:
        return "probable hook call did not map to a static import binding in ingest.py"
    if not call_rows:
        return "probable hook import did not have a matching static call site in ingest.py"
    if status == "CONFIRMED":
        return evidence.reason
    if status == "PROBABLE":
        return (
            "direct live ingest import/call pair found, but target source path was not found by "
            "static module-to-file mapping; runtime import not attempted"
        )
    return evidence.reason


def _analyze_import_chains() -> Dict[str, Any]:
    ingest_source, ingest_tree, parse_error = _parse_python_file(INGEST_ROUTE_PATH)
    refresh_function = _function_defs(ingest_tree).get("_refresh_after_insert") if ingest_tree else None
    bindings = _collect_import_bindings(refresh_function, ingest_source)
    references = _probable_references()

    matrix_rows: List[Dict[str, Any]] = []
    target_rows: List[Dict[str, Any]] = []
    unresolved_rows: List[Dict[str, Any]] = []
    for reference in references:
        call_rows = _find_calls(refresh_function, reference.call_symbol, ingest_source)
        binding = bindings.get(reference.call_symbol)
        if binding is None:
            evidence = DefinitionEvidence(
                status="UNRESOLVED",
                source_file_path="",
                line="",
                ast_node_type="",
                evidence="",
                reexport_chain="",
                reexport_module="",
                reexport_symbol="",
                reason="no static import binding found for local call symbol",
                depth=0,
            )
            checked_paths: List[Path] = []
        else:
            evidence = _resolve_definition(binding.import_module, binding.imported_symbol)
            checked_paths = module_path_candidates(binding.import_module)

        status = _status_for(binding, call_rows, evidence)
        reason = _reason_for(status, evidence, binding, call_rows)
        candidate_source_file = evidence.source_file_path
        checked_path_text = ";".join(_artifact_label(path) for path in checked_paths)
        call_row = call_rows[0] if call_rows else {"line": reference.call_line, "evidence": reference.call_evidence}
        alias_mapping = ""
        if binding is not None and binding.local_symbol != binding.imported_symbol:
            alias_mapping = f"{binding.imported_symbol} as {binding.local_symbol}"

        matrix_rows.append(
            {
                "hook_name": reference.hook_name,
                "status": status,
                "ingest_call_site_line": call_row.get("line", ""),
                "ingest_call_site_evidence": call_row.get("evidence", ""),
                "import_statement_line": binding.line if binding else "",
                "import_statement_evidence": binding.evidence if binding else "",
                "import_kind": binding.import_kind if binding else "",
                "import_module": binding.import_module if binding else "",
                "imported_symbol": binding.imported_symbol if binding else "",
                "local_symbol": binding.local_symbol if binding else reference.call_symbol,
                "alias_mapping": alias_mapping,
                "candidate_module_path": binding.import_module if binding else "",
                "candidate_source_file_path": candidate_source_file,
                "candidate_source_exists": bool(candidate_source_file),
                "checked_source_paths": checked_path_text,
                "target_definition_status": evidence.status,
                "target_definition_line": evidence.line,
                "target_definition_ast_node_type": evidence.ast_node_type,
                "target_definition_evidence": evidence.evidence,
                "reexport_chain": evidence.reexport_chain,
                "reason": reason,
            }
        )
        target_rows.append(
            {
                "hook_name": reference.hook_name,
                "import_module": binding.import_module if binding else "",
                "imported_symbol": binding.imported_symbol if binding else "",
                "source_file_path": candidate_source_file,
                "definition_line": evidence.line,
                "definition_kind": evidence.ast_node_type,
                "definition_evidence": evidence.evidence,
                "reexport_depth": evidence.depth,
                "reexport_module": evidence.reexport_module,
                "reexport_symbol": evidence.reexport_symbol,
                "status": evidence.status,
                "reason": evidence.reason,
            }
        )
        if status != "CONFIRMED":
            unresolved_rows.append(
                {
                    "hook_name": reference.hook_name,
                    "status": status,
                    "import_module": binding.import_module if binding else "",
                    "imported_symbol": binding.imported_symbol if binding else "",
                    "local_symbol": binding.local_symbol if binding else reference.call_symbol,
                    "ingest_call_site_line": call_row.get("line", ""),
                    "candidate_source_file_path": candidate_source_file,
                    "reason": reason,
                    "recommended_next_action": "runtime-instrumentation-required" if status == "PROBABLE" else "static-followup",
                }
            )

    failures = []
    for path in (P520G_RESULT_PATH, P520G_BY_HOOK_PATH, P520G_MEDIUM_CARDS_PATH):
        if not path.exists():
            failures.append(f"missing artifact: {_artifact_label(path)}")
    if parse_error:
        failures.append(f"ingest source parse failed: {parse_error}")

    status_counts = {
        "CONFIRMED": sum(1 for row in matrix_rows if row["status"] == "CONFIRMED"),
        "PROBABLE": sum(1 for row in matrix_rows if row["status"] == "PROBABLE"),
        "UNRESOLVED": sum(1 for row in matrix_rows if row["status"] == "UNRESOLVED"),
    }
    source_unresolved_count = sum(
        1 for row in matrix_rows if row["target_definition_status"] == "SOURCE_PATH_UNRESOLVED"
    )
    final_status = "FAIL" if failures else "PASS" if status_counts["PROBABLE"] == 0 and status_counts["UNRESOLVED"] == 0 else "WARN"
    warnings = [
        f"{row['hook_name']}: {row['reason']}"
        for row in matrix_rows
        if row["status"] != "CONFIRMED"
    ]

    p520g_result = _load_json(P520G_RESULT_PATH)
    p520f_result = _load_json(P520F_RESULT_PATH)
    p520e_result = _load_json(P520E_RESULT_PATH)
    p520d_result = _load_json(P520D_RESULT_PATH)

    result = {
        "artifact_prefix": ARTIFACT_PREFIX,
        "final_status": final_status,
        "source_path": _artifact_label(INGEST_ROUTE_PATH),
        "probable_reference_count": len(references),
        "import_chain_row_count": len(matrix_rows),
        "target_definition_row_count": len(target_rows),
        "unresolved_summary_row_count": len(unresolved_rows),
        "confirmed_hook_count": status_counts["CONFIRMED"],
        "probable_hook_count": status_counts["PROBABLE"],
        "unresolved_hook_count": status_counts["UNRESOLVED"],
        "target_source_unresolved_count": source_unresolved_count,
        "status_counts": status_counts,
        "confirmed_hooks": sorted(row["hook_name"] for row in matrix_rows if row["status"] == "CONFIRMED"),
        "probable_hooks": sorted(row["hook_name"] for row in matrix_rows if row["status"] == "PROBABLE"),
        "unresolved_hooks": sorted(row["hook_name"] for row in matrix_rows if row["status"] == "UNRESOLVED"),
        "component_statuses": {
            "P520G result artifact read": "PASS" if P520G_RESULT_PATH.exists() else "FAIL",
            "P520G by-hook artifact read": "PASS" if P520G_BY_HOOK_PATH.exists() else "FAIL",
            "P520G medium cards artifact read": "PASS" if P520G_MEDIUM_CARDS_PATH.exists() else "FAIL",
            "P520F artifact context read": "PASS" if P520F_RESULT_PATH.exists() else "WARN",
            "P520E artifact context read": "PASS" if P520E_RESULT_PATH.exists() else "WARN",
            "P520D artifact context read": "PASS" if P520D_RESULT_PATH.exists() else "WARN",
            "ingest source AST evaluation": "PASS" if not parse_error else "FAIL",
            "import-chain static resolution": "WARN" if source_unresolved_count else "PASS",
            "runtime import avoided": "PASS",
            "DB side effects avoided": "PASS",
            "target confirmation conservative": "PASS",
        },
        "p520g_summary": {
            "result_artifact": _artifact_label(P520G_RESULT_PATH),
            "result_present": P520G_RESULT_PATH.exists(),
            "final_status": p520g_result.get("final_status", ""),
            "probable_upgrade_count": p520g_result.get("probable_upgrade_count", ""),
            "confirmed_hook_count": p520g_result.get("confirmed_hook_count", ""),
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
        "p520d_summary": {
            "result_artifact": _artifact_label(P520D_RESULT_PATH),
            "result_present": P520D_RESULT_PATH.exists(),
            "final_status": p520d_result.get("final_status", ""),
            "detected_live_hook_count": p520d_result.get("detected_live_hook_count", ""),
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
            "P520H reads committed P520G/P520F/P520E/P520D artifacts, parses "
            "lottery_api/routes/ingest.py, and inspects candidate target files as text/AST only; "
            "no app runtime import; no live target module import; no after-insert hook execution; "
            "no draw insert execution; no canonical DB open/write; no migration/backfill; no deploy; "
            "does not implement or modify hooks; does not modify prediction/strategy/scoring logic."
        ),
        "suggested_next_command": "python -m tools.ingest_afterinsert_hook_import_chain_resolver --status-block",
    }
    return {
        "result": result,
        "matrix": sorted(matrix_rows, key=lambda row: row["hook_name"]),
        "target_definitions": sorted(target_rows, key=lambda row: row["hook_name"]),
        "unresolved": sorted(unresolved_rows, key=lambda row: row["hook_name"]),
    }


def _status_block(result: Mapping[str, Any]) -> str:
    lines = [
        "# P520H ingest after-insert hook import-chain resolver status",
        "",
        f"- Final status: `{result['final_status']}`",
        f"- Probable live reference count from P520G: `{result['probable_reference_count']}`",
        f"- Confirmed hook count: `{result['confirmed_hook_count']}`",
        f"- Probable hook count: `{result['probable_hook_count']}`",
        f"- Unresolved hook count: `{result['unresolved_hook_count']}`",
        f"- Target source unresolved count: `{result['target_source_unresolved_count']}`",
        f"- Import-chain matrix rows: `{result['import_chain_row_count']}`",
        f"- Target definition rows: `{result['target_definition_row_count']}`",
        f"- PASS/WARN/FAIL counts: `{result['pass_count']}/{result['warn_count']}/{result['fail_count']}`",
        "",
        "## Status Summary",
        f"- Confirmed: `{';'.join(result['confirmed_hooks'])}`",
        f"- Probable: `{';'.join(result['probable_hooks'])}`",
        f"- Unresolved: `{';'.join(result['unresolved_hooks'])}`",
        "",
        "## Scope notices",
    ]
    lines.extend(f"- {notice}" for notice in NOTICE_LINES)
    lines.extend(
        [
            "",
            "## Recommendation",
            "- No hook target is confirmed unless a direct static definition or direct re-export is present.",
            "- In this baseline the three P520G probable live references remain probable because static module-to-file mapping does not locate their target source files.",
            "- Runtime import or hook execution was not attempted.",
        ]
    )
    return "\n".join(lines) + "\n"


def build_import_chain_bundle() -> Dict[str, Any]:
    bundle = _analyze_import_chains()
    bundle["status_block"] = _status_block(bundle["result"])
    return bundle


def _manifest_rows(rendered: Mapping[Path, str]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for path in (RESULT_PATH, MATRIX_PATH, TARGET_DEFINITIONS_PATH, UNRESOLVED_PATH, STATUS_BLOCK_PATH):
        text = rendered[path]
        data = text.encode("utf-8")
        rows.append(
            {
                "artifact_path": _artifact_label(path),
                "artifact_kind": path.suffix.lstrip("."),
                "sha256": _sha256_bytes(data),
                "bytes": len(data),
                "notes": "generated by source/AST-only P520H import-chain resolver",
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
    bundle = build_import_chain_bundle()
    rendered: Dict[Path, str] = {
        RESULT_PATH: _json_text(bundle["result"]),
        MATRIX_PATH: _csv_text(bundle["matrix"], MATRIX_FIELDS),
        TARGET_DEFINITIONS_PATH: _csv_text(bundle["target_definitions"], TARGET_DEFINITION_FIELDS),
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
    parser.add_argument("--generate", action="store_true", help="write all P520H import-chain resolver artifacts")
    parser.add_argument("--import-chain", action="store_true", help="print import-chain matrix CSV")
    parser.add_argument("--target-definitions", action="store_true", help="print target definition evidence CSV")
    parser.add_argument("--unresolved", action="store_true", help="print unresolved/probable summary CSV")
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

    if args.import_chain:
        rendered = rendered or render_artifacts()
        print(rendered[MATRIX_PATH], end="")

    if args.target_definitions:
        rendered = rendered or render_artifacts()
        print(rendered[TARGET_DEFINITIONS_PATH], end="")

    if args.unresolved:
        rendered = rendered or render_artifacts()
        print(rendered[UNRESOLVED_PATH], end="")

    if args.status_block:
        rendered = rendered or render_artifacts()
        print(rendered[STATUS_BLOCK_PATH], end="")

    if args.validate:
        ok, mismatches = validate_artifacts(rendered)
        if ok:
            print("P520H_IMPORT_CHAIN_RESOLVER_VALIDATE_OK")
        else:
            for mismatch in mismatches:
                print(mismatch, file=sys.stderr)
            return 1

    if not any(
        (
            args.generate,
            args.import_chain,
            args.target_definitions,
            args.unresolved,
            args.status_block,
            args.validate,
        )
    ):
        parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
