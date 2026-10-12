#!/usr/bin/env python3
"""P520F source/AST-only candidate resolver for unresolved ingest hooks.

This module reads prior P520E artifacts and scans repository Python source as
text/AST only. It does not import ``lottery_api.routes.ingest``, does not
import live hook target modules, does not execute after-insert hooks or draw
inserts, does not open or write a database, and does not run migrations,
backfills, or deploys.
"""
from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import io
import json
import re
import sys
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
INGEST_ROUTE_PATH = PROJECT_ROOT / "lottery_api" / "routes" / "ingest.py"

ARTIFACT_PREFIX = "P520F_ingest_afterinsert_hook_candidate_resolver"

RESULT_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_result.json"
CANDIDATES_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_candidates.csv"
REFERENCES_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_references.csv"
CONFIDENCE_SUMMARY_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_confidence_summary.json"
STATUS_BLOCK_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_status_block.md"
MANIFEST_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_manifest.csv"

P520E_RESULT_PATH = ARTIFACTS_DIR / "P520E_ingest_afterinsert_hook_target_audit_result.json"
P520E_MATRIX_PATH = ARTIFACTS_DIR / "P520E_ingest_afterinsert_hook_target_audit_matrix.csv"
P520E_UNRESOLVED_PATH = ARTIFACTS_DIR / "P520E_ingest_afterinsert_hook_target_audit_unresolved.csv"

NOTICE_LINES: Sequence[str] = (
    "source/AST-only candidate resolver",
    "reads P520E unresolved artifacts",
    "repo-wide Python source scan only",
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

EXCLUDED_DIRS: Sequence[str] = (
    ".git",
    ".hg",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "htmlcov",
    "node_modules",
)

CANDIDATE_FIELDS: Sequence[str] = (
    "hook_reference",
    "candidate_id",
    "source_path",
    "line",
    "ast_node_type",
    "evidence_kind",
    "matched_name",
    "confidence",
    "target_confirmed",
    "why_candidate_matches",
    "evidence",
)

REFERENCE_FIELDS: Sequence[str] = (
    "hook_reference",
    "source_path",
    "line",
    "ast_node_type",
    "reference_kind",
    "matched_name",
    "confidence",
    "evidence",
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
    p520e_reason: str = ""


@dataclass(frozen=True)
class ParsedSource:
    path: Path
    label: str
    source: str
    tree: ast.AST | None
    parse_error: str = ""


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


def _normalized(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _name_parts(value: str) -> List[str]:
    return [part for part in re.split(r"[^A-Za-z0-9]+", value) if len(part) >= 4]


def _load_csv_rows(path: Path) -> List[Dict[str, str]]:
    return list(csv.DictReader(_read_text(path).splitlines())) if path.exists() else []


def _load_p520e_result() -> Dict[str, Any]:
    return json.loads(_read_text(P520E_RESULT_PATH)) if P520E_RESULT_PATH.exists() else {}


def _load_unresolved_specs() -> List[HookSpec]:
    unresolved_rows = _load_csv_rows(P520E_UNRESOLVED_PATH)
    matrix_by_hook = {row.get("hook_reference", ""): row for row in _load_csv_rows(P520E_MATRIX_PATH)}
    specs: List[HookSpec] = []
    for row in unresolved_rows:
        hook = row.get("hook_reference", "")
        matrix = matrix_by_hook.get(hook, {})
        specs.append(
            HookSpec(
                hook_reference=hook,
                import_module=row.get("import_module", ""),
                imported_symbol=row.get("imported_symbol", ""),
                local_symbol=row.get("local_symbol", ""),
                call_name=matrix.get("call_name", "") or row.get("local_symbol", ""),
                target_attribute=row.get("target_attribute", ""),
                p520e_reason=row.get("reason", ""),
            )
        )
    return sorted(specs, key=lambda spec: spec.hook_reference)


def _iter_python_paths(root: Path = PROJECT_ROOT) -> List[Path]:
    paths: List[Path] = []
    for path in root.rglob("*.py"):
        rel_parts = path.relative_to(root).parts
        if any(part in EXCLUDED_DIRS for part in rel_parts):
            continue
        paths.append(path)
    return sorted(paths, key=lambda path: _artifact_label(path))


def _parse_sources(paths: Sequence[Path]) -> List[ParsedSource]:
    parsed: List[ParsedSource] = []
    for path in paths:
        label = _artifact_label(path)
        source = _read_text(path)
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                tree = ast.parse(source, filename=str(path))
            parsed.append(ParsedSource(path=path, label=label, source=source, tree=tree))
        except SyntaxError as exc:
            parsed.append(
                ParsedSource(
                    path=path,
                    label=label,
                    source=source,
                    tree=None,
                    parse_error=f"{exc.__class__.__name__}: {exc.msg}",
                )
            )
    return parsed


def _module_path_candidates(module: str) -> List[str]:
    module_path = "/".join(part for part in module.split(".") if part)
    return [
        f"{module_path}.py",
        f"{module_path}/__init__.py",
        f"lottery_api/{module_path}.py",
        f"lottery_api/{module_path}/__init__.py",
    ]


def _expected_module_path_exists(spec: HookSpec) -> bool:
    return any((PROJECT_ROOT / candidate).exists() for candidate in _module_path_candidates(spec.import_module))


def _exact_names(spec: HookSpec) -> set[str]:
    names = {
        spec.hook_reference,
        spec.imported_symbol,
        spec.local_symbol,
        spec.call_name,
    }
    names.update(part for part in spec.hook_reference.split(".") if part)
    return {name for name in names if name}


def _related_needles(spec: HookSpec) -> set[str]:
    needles = {_normalized(spec.hook_reference), _normalized(spec.imported_symbol)}
    if spec.import_module:
        needles.add(_normalized(spec.import_module.split(".")[-1]))
    for part in _name_parts(spec.hook_reference):
        needles.add(_normalized(part))
    return {needle for needle in needles if needle and len(needle) >= 4}


def _is_tooling_path(label: str) -> bool:
    return label.startswith("tests/") or label.startswith("tools/")


def _is_live_ingest_path(label: str) -> bool:
    return label == _artifact_label(INGEST_ROUTE_PATH)


def _confidence_for_reference(label: str, kind: str, direct: bool, related: bool) -> str:
    if _is_tooling_path(label):
        return "LOW"
    if direct and _is_live_ingest_path(label) and kind in {"import", "call"}:
        return "MEDIUM"
    if direct and kind in {"function_def", "class_def", "assignment"}:
        return "MEDIUM"
    if direct:
        return "LOW" if _is_tooling_path(label) else "MEDIUM"
    if related and not _is_tooling_path(label):
        return "LOW"
    return "LOW"


def _candidate_reason(
    spec: HookSpec,
    label: str,
    kind: str,
    matched_name: str,
    confidence: str,
    target_confirmed: bool,
) -> str:
    if target_confirmed:
        return "expected import module source exists and imported symbol definition is direct"
    if _is_live_ingest_path(label) and kind == "import":
        return "live ingest hook imports this unresolved target, but target source remains unresolved"
    if _is_live_ingest_path(label) and kind == "call":
        return "live ingest hook calls this unresolved local symbol, but target source remains unresolved"
    if kind in {"function_def", "class_def"} and confidence == "MEDIUM":
        return "direct source definition name matches unresolved hook symbol outside tooling"
    if kind in {"function_def", "class_def"}:
        return "related source definition name matches unresolved hook naming tokens"
    if _is_tooling_path(label):
        return "tooling or test reference corroborates prior audit evidence only"
    return f"source {kind} references {matched_name!r} for unresolved hook {spec.hook_reference!r}"


def _add_reference(
    rows: List[Dict[str, Any]],
    spec: HookSpec,
    parsed: ParsedSource,
    node: ast.AST,
    kind: str,
    matched_name: str,
    confidence: str,
) -> None:
    rows.append(
        {
            "hook_reference": spec.hook_reference,
            "source_path": parsed.label,
            "line": _line(node),
            "ast_node_type": type(node).__name__,
            "reference_kind": kind,
            "matched_name": matched_name,
            "confidence": confidence,
            "evidence": _node_source(parsed.source, node),
        }
    )


def _scan_source_for_spec(spec: HookSpec, parsed: ParsedSource) -> List[Dict[str, Any]]:
    if parsed.tree is None:
        return []

    rows: List[Dict[str, Any]] = []
    exact_names = _exact_names(spec)
    related_needles = _related_needles(spec)

    for node in ast.walk(parsed.tree):
        if isinstance(node, ast.ImportFrom):
            names = {alias.name for alias in node.names}
            names.update(alias.asname for alias in node.names if alias.asname)
            direct = node.module == spec.import_module or bool(names & exact_names)
            if direct:
                matched = spec.import_module if node.module == spec.import_module else sorted(names & exact_names)[0]
                confidence = _confidence_for_reference(parsed.label, "import", True, False)
                _add_reference(rows, spec, parsed, node, "import", matched, confidence)
        elif isinstance(node, ast.Import):
            imported = {alias.name for alias in node.names}
            imported.update(alias.asname for alias in node.names if alias.asname)
            if spec.import_module in imported or bool(imported & exact_names):
                matched = spec.import_module if spec.import_module in imported else sorted(imported & exact_names)[0]
                confidence = _confidence_for_reference(parsed.label, "import", True, False)
                _add_reference(rows, spec, parsed, node, "import", matched, confidence)
        elif isinstance(node, ast.Call):
            name = _call_name(node.func)
            if name in exact_names:
                confidence = _confidence_for_reference(parsed.label, "call", True, False)
                _add_reference(rows, spec, parsed, node, "call", name, confidence)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            normalized = _normalized(node.name)
            direct = node.name in exact_names
            related = not direct and any(needle in normalized for needle in related_needles)
            if direct or related:
                kind = "class_def" if isinstance(node, ast.ClassDef) else "function_def"
                confidence = _confidence_for_reference(parsed.label, kind, direct, related)
                _add_reference(rows, spec, parsed, node, kind, node.name, confidence)
        elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets: Iterable[ast.AST]
            if isinstance(node, ast.Assign):
                targets = node.targets
            else:
                targets = (node.target,)
            matched_targets = [target.id for target in targets if isinstance(target, ast.Name) and target.id in exact_names]
            if matched_targets:
                confidence = _confidence_for_reference(parsed.label, "assignment", True, False)
                _add_reference(rows, spec, parsed, node, "assignment", sorted(matched_targets)[0], confidence)
        elif isinstance(node, ast.Name) and node.id in exact_names:
            confidence = _confidence_for_reference(parsed.label, "name", True, False)
            _add_reference(rows, spec, parsed, node, "name", node.id, confidence)
        elif isinstance(node, ast.Attribute) and node.attr in exact_names:
            confidence = _confidence_for_reference(parsed.label, "attribute", True, False)
            _add_reference(rows, spec, parsed, node, "attribute", node.attr, confidence)
    return rows


def _dedupe_rows(rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> List[Dict[str, Any]]:
    seen: set[Tuple[str, ...]] = set()
    unique: List[Dict[str, Any]] = []
    for row in rows:
        key = tuple(str(row.get(field, "")) for field in fields)
        if key in seen:
            continue
        seen.add(key)
        unique.append(dict(row))
    return sorted(
        unique,
        key=lambda row: (
            str(row.get("hook_reference", "")),
            str(row.get("source_path", "")),
            int(row.get("line", 0)) if str(row.get("line", "")).isdigit() else 0,
            str(row.get("reference_kind", row.get("evidence_kind", ""))),
            str(row.get("matched_name", "")),
            str(row.get("evidence", "")),
        ),
    )


def _candidate_rows(specs: Sequence[HookSpec], reference_rows: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    spec_by_hook = {spec.hook_reference: spec for spec in specs}
    candidates: List[Dict[str, Any]] = []
    selected_kinds = {"import", "call", "function_def", "class_def", "assignment"}
    by_hook_counter: Dict[str, int] = {spec.hook_reference: 0 for spec in specs}

    for ref in reference_rows:
        if ref.get("reference_kind") not in selected_kinds:
            continue
        hook = str(ref.get("hook_reference", ""))
        spec = spec_by_hook[hook]
        confidence = str(ref.get("confidence", "LOW"))
        target_confirmed = False
        if confidence == "HIGH" and _expected_module_path_exists(spec):
            target_confirmed = True
        by_hook_counter[hook] += 1
        kind = str(ref.get("reference_kind", ""))
        matched = str(ref.get("matched_name", ""))
        candidates.append(
            {
                "hook_reference": hook,
                "candidate_id": f"{hook}#{by_hook_counter[hook]:03d}",
                "source_path": ref.get("source_path", ""),
                "line": ref.get("line", ""),
                "ast_node_type": ref.get("ast_node_type", ""),
                "evidence_kind": kind,
                "matched_name": matched,
                "confidence": confidence,
                "target_confirmed": target_confirmed,
                "why_candidate_matches": _candidate_reason(spec, str(ref.get("source_path", "")), kind, matched, confidence, target_confirmed),
                "evidence": ref.get("evidence", ""),
            }
        )
    return _dedupe_rows(candidates, CANDIDATE_FIELDS)


def _confidence_summary(
    specs: Sequence[HookSpec],
    candidate_rows: Sequence[Mapping[str, Any]],
    reference_rows: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    by_hook: Dict[str, Dict[str, Any]] = {}
    for spec in specs:
        hook_candidates = [row for row in candidate_rows if row.get("hook_reference") == spec.hook_reference]
        hook_refs = [row for row in reference_rows if row.get("hook_reference") == spec.hook_reference]
        counts = {
            "HIGH": sum(1 for row in hook_candidates if row.get("confidence") == "HIGH"),
            "MEDIUM": sum(1 for row in hook_candidates if row.get("confidence") == "MEDIUM"),
            "LOW": sum(1 for row in hook_candidates if row.get("confidence") == "LOW"),
        }
        best = "NONE"
        for confidence in ("HIGH", "MEDIUM", "LOW"):
            if counts[confidence]:
                best = confidence
                break
        by_hook[spec.hook_reference] = {
            "candidate_count": len(hook_candidates),
            "reference_count": len(hook_refs),
            "confidence_counts": counts,
            "best_confidence": best,
            "target_confirmed": any(str(row.get("target_confirmed")) == "True" for row in hook_candidates),
            "status": "WARN",
            "notes": "candidate evidence only; no target confirmed unless HIGH direct source evidence exists",
        }
    total_counts = {
        "HIGH": sum(item["confidence_counts"]["HIGH"] for item in by_hook.values()),
        "MEDIUM": sum(item["confidence_counts"]["MEDIUM"] for item in by_hook.values()),
        "LOW": sum(item["confidence_counts"]["LOW"] for item in by_hook.values()),
    }
    return {
        "artifact_prefix": ARTIFACT_PREFIX,
        "final_status": "WARN",
        "unresolved_hook_count": len(specs),
        "candidate_count": len(candidate_rows),
        "reference_count": len(reference_rows),
        "confidence_counts": total_counts,
        "candidate_count_by_hook": {hook: data["candidate_count"] for hook, data in by_hook.items()},
        "reference_count_by_hook": {hook: data["reference_count"] for hook, data in by_hook.items()},
        "best_confidence_by_hook": {hook: data["best_confidence"] for hook, data in by_hook.items()},
        "target_confirmed_by_hook": {hook: data["target_confirmed"] for hook, data in by_hook.items()},
        "no_high_confidence_hooks": [
            hook for hook, data in by_hook.items() if data["confidence_counts"]["HIGH"] == 0
        ],
        "by_hook": by_hook,
    }


def analyze_candidates() -> Dict[str, Any]:
    specs = _load_unresolved_specs()
    python_paths = _iter_python_paths()
    parsed_sources = _parse_sources(python_paths)
    references: List[Dict[str, Any]] = []
    for spec in specs:
        for parsed in parsed_sources:
            references.extend(_scan_source_for_spec(spec, parsed))
    reference_rows = _dedupe_rows(references, REFERENCE_FIELDS)
    candidate_rows = _candidate_rows(specs, reference_rows)
    confidence_summary = _confidence_summary(specs, candidate_rows, reference_rows)
    parse_errors = [
        {"source_path": parsed.label, "parse_error": parsed.parse_error}
        for parsed in parsed_sources
        if parsed.parse_error
    ]
    p520e_result = _load_p520e_result()
    warnings = [
        f"{spec.hook_reference}: static candidates only; target remains unconfirmed without direct HIGH evidence"
        for spec in specs
        if spec.hook_reference in confidence_summary["no_high_confidence_hooks"]
    ]
    return {
        "specs": specs,
        "candidate_rows": candidate_rows,
        "reference_rows": reference_rows,
        "confidence_summary": confidence_summary,
        "parse_errors": parse_errors,
        "p520e_result": p520e_result,
        "source_files_scanned_count": len(python_paths),
        "source_files_parsed_count": sum(1 for parsed in parsed_sources if parsed.tree is not None),
        "parse_error_count": len(parse_errors),
        "warnings": warnings,
    }


def _status_block(result: Mapping[str, Any], confidence_summary: Mapping[str, Any]) -> str:
    lines = [
        "# P520F ingest after-insert hook candidate resolver status",
        "",
        f"- Final status: `{result['final_status']}`",
        f"- P520E final status: `{result['p520e_summary'].get('final_status', '')}`",
        f"- Unresolved hook count: `{result['unresolved_hook_count']}`",
        f"- Candidate count: `{result['candidate_count']}`",
        f"- Reference count: `{result['reference_count']}`",
        f"- Source files scanned: `{result['source_files_scanned_count']}`",
        f"- Parse error count: `{result['parse_error_count']}`",
        f"- Confidence counts: `{confidence_summary['confidence_counts']}`",
        f"- Candidate count by hook: `{confidence_summary['candidate_count_by_hook']}`",
        f"- Target confirmed by hook: `{confidence_summary['target_confirmed_by_hook']}`",
        f"- PASS/WARN/FAIL counts: `{result['pass_count']}/{result['warn_count']}/{result['fail_count']}`",
        "",
        "## Scope notices",
    ]
    lines.extend(f"- {notice}" for notice in NOTICE_LINES)
    lines.append("")
    lines.append("## Warnings")
    lines.extend(f"- {warning}" for warning in result["warnings"])
    return "\n".join(lines) + "\n"


def build_candidate_resolver_bundle() -> Dict[str, Any]:
    analysis = analyze_candidates()
    specs: Sequence[HookSpec] = analysis["specs"]
    confidence_summary = analysis["confidence_summary"]
    failures: List[str] = []
    warning_count = max(1, len(analysis["warnings"])) if specs else 0
    p520e_result = analysis["p520e_result"]
    result = {
        "artifact_prefix": ARTIFACT_PREFIX,
        "final_status": "FAIL" if failures else "WARN",
        "source_path": _artifact_label(INGEST_ROUTE_PATH),
        "p520e_summary": {
            "result_artifact": _artifact_label(P520E_RESULT_PATH),
            "result_present": P520E_RESULT_PATH.exists(),
            "final_status": p520e_result.get("final_status", ""),
            "unresolved_source_count": p520e_result.get("unresolved_source_count", ""),
            "target_symbol_found_count": p520e_result.get("target_symbol_found_count", ""),
            "db_indicator_count": p520e_result.get("db_indicator_count", ""),
            "file_indicator_count": p520e_result.get("file_indicator_count", ""),
            "runtime_indicator_count": p520e_result.get("runtime_indicator_count", ""),
        },
        "unresolved_hooks": [spec.hook_reference for spec in specs],
        "unresolved_hook_count": len(specs),
        "source_files_scanned_count": analysis["source_files_scanned_count"],
        "source_files_parsed_count": analysis["source_files_parsed_count"],
        "parse_error_count": analysis["parse_error_count"],
        "parse_errors": analysis["parse_errors"],
        "candidate_count": len(analysis["candidate_rows"]),
        "reference_count": len(analysis["reference_rows"]),
        "candidate_count_by_hook": confidence_summary["candidate_count_by_hook"],
        "reference_count_by_hook": confidence_summary["reference_count_by_hook"],
        "confidence_counts": confidence_summary["confidence_counts"],
        "best_confidence_by_hook": confidence_summary["best_confidence_by_hook"],
        "target_confirmed_by_hook": confidence_summary["target_confirmed_by_hook"],
        "component_statuses": {
            "P520E unresolved artifact read": "PASS" if P520E_UNRESOLVED_PATH.exists() else "FAIL",
            "P520E result artifact read": "PASS" if P520E_RESULT_PATH.exists() else "WARN",
            "repo Python source scan": "PASS",
            "source AST evaluation": "PASS" if analysis["parse_error_count"] == 0 else "WARN",
            "runtime import avoided": "PASS",
            "DB side effects avoided": "PASS",
            "target confirmation conservative": "PASS",
        },
        "pass_count": 0,
        "warn_count": warning_count,
        "fail_count": len(failures),
        "warning_count": warning_count,
        "warnings": analysis["warnings"] or ["no unresolved hooks found in P520E artifacts"],
        "failure_count": len(failures),
        "failures": failures,
        "notices": list(NOTICE_LINES),
        "scope": (
            "P520F reads P520E artifacts and parses repository Python source as text/AST only; "
            "no app runtime import; no live target module import; no after-insert hook execution; "
            "no draw insert execution; no canonical DB open/write; no migration/backfill; no deploy; "
            "does not implement or modify hooks; no betting/future prediction claims."
        ),
        "suggested_next_command": "python -m tools.ingest_afterinsert_hook_candidate_resolver --status-block",
    }
    return {
        "result": result,
        "candidates": analysis["candidate_rows"],
        "references": analysis["reference_rows"],
        "confidence_summary": confidence_summary,
        "status_block": _status_block(result, confidence_summary),
    }


def _manifest_rows(rendered: Mapping[Path, str]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for path in (RESULT_PATH, CANDIDATES_PATH, REFERENCES_PATH, CONFIDENCE_SUMMARY_PATH, STATUS_BLOCK_PATH):
        text = rendered[path]
        data = text.encode("utf-8")
        rows.append(
            {
                "artifact_path": _artifact_label(path),
                "artifact_kind": path.suffix.lstrip("."),
                "sha256": _sha256_bytes(data),
                "bytes": len(data),
                "notes": "generated by source/AST-only P520F resolver",
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
    bundle = build_candidate_resolver_bundle()
    rendered: Dict[Path, str] = {
        RESULT_PATH: _json_text(bundle["result"]),
        CANDIDATES_PATH: _csv_text(bundle["candidates"], CANDIDATE_FIELDS),
        REFERENCES_PATH: _csv_text(bundle["references"], REFERENCE_FIELDS),
        CONFIDENCE_SUMMARY_PATH: _json_text(bundle["confidence_summary"]),
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
    parser.add_argument("--generate", action="store_true", help="write all P520F candidate resolver artifacts")
    parser.add_argument("--candidates", action="store_true", help="print unresolved hook candidate matrix CSV")
    parser.add_argument("--references", action="store_true", help="print source reference inventory CSV")
    parser.add_argument("--confidence-summary", action="store_true", help="print confidence summary JSON")
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

    if args.candidates:
        rendered = rendered or render_artifacts()
        print(rendered[CANDIDATES_PATH], end="")

    if args.references:
        rendered = rendered or render_artifacts()
        print(rendered[REFERENCES_PATH], end="")

    if args.confidence_summary:
        rendered = rendered or render_artifacts()
        print(rendered[CONFIDENCE_SUMMARY_PATH], end="")

    if args.status_block:
        rendered = rendered or render_artifacts()
        print(rendered[STATUS_BLOCK_PATH], end="")

    if args.validate:
        ok, mismatches = validate_artifacts(rendered)
        if ok:
            print("P520F_CANDIDATE_RESOLVER_VALIDATE_OK")
        else:
            for mismatch in mismatches:
                print(mismatch, file=sys.stderr)
            return 1

    if not any((args.generate, args.candidates, args.references, args.confidence_summary, args.status_block, args.validate)):
        parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
