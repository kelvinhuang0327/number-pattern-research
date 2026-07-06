#!/usr/bin/env python3
"""P520G source/AST-only triage for unresolved ingest hook candidates.

This module reads committed P520F/P520E/P520D artifacts and parses source as
text/AST only. It does not import ``lottery_api.routes.ingest``, does not
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
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
INGEST_ROUTE_PATH = PROJECT_ROOT / "lottery_api" / "routes" / "ingest.py"

ARTIFACT_PREFIX = "P520G_ingest_afterinsert_hook_candidate_triage"

RESULT_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_result.json"
MEDIUM_CARDS_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_medium_cards.json"
BY_HOOK_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_by_hook.csv"
LOW_SUMMARY_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_low_summary.csv"
STATUS_BLOCK_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_status_block.md"
MANIFEST_PATH = ARTIFACTS_DIR / f"{ARTIFACT_PREFIX}_manifest.csv"

P520F_RESULT_PATH = ARTIFACTS_DIR / "P520F_ingest_afterinsert_hook_candidate_resolver_result.json"
P520F_CANDIDATES_PATH = ARTIFACTS_DIR / "P520F_ingest_afterinsert_hook_candidate_resolver_candidates.csv"
P520F_CONFIDENCE_SUMMARY_PATH = (
    ARTIFACTS_DIR / "P520F_ingest_afterinsert_hook_candidate_resolver_confidence_summary.json"
)
P520E_RESULT_PATH = ARTIFACTS_DIR / "P520E_ingest_afterinsert_hook_target_audit_result.json"
P520E_UNRESOLVED_PATH = ARTIFACTS_DIR / "P520E_ingest_afterinsert_hook_target_audit_unresolved.csv"
P520D_RESULT_PATH = ARTIFACTS_DIR / "P520D_ingest_afterinsert_hook_contract_result.json"

NOTICE_LINES: Sequence[str] = (
    "source/AST/text-only candidate triage",
    "reads committed P520F resolver artifacts",
    "focuses MEDIUM candidates with evidence cards",
    "summarizes LOW candidates only",
    "does not import lottery_api.routes.ingest",
    "does not import live hook target modules",
    "does not execute after-insert hooks",
    "does not execute draw inserts",
    "no canonical DB open/write",
    "no migration/backfill",
    "no deploy",
    "does not modify hooks",
    "does not change P520F scoring",
    "no betting/future prediction claims",
)

MEDIUM_CARD_FIELDS: Sequence[str] = (
    "unresolved_hook_name",
    "candidate_id",
    "candidate_file_path",
    "line_number",
    "ast_node_type",
    "evidence_kind",
    "matched_symbol_reference",
    "candidate_confidence",
    "supporting_source_snippet",
    "why_it_may_match",
    "why_it_remains_unconfirmed",
    "recommended_next_action",
)

BY_HOOK_FIELDS: Sequence[str] = (
    "unresolved_hook_name",
    "top_candidates",
    "medium_candidate_count",
    "low_candidate_count",
    "remaining_unresolved_count",
    "probable_upgrade",
    "probable_upgrade_reason",
    "confirmed",
    "recommendation",
)

LOW_SUMMARY_FIELDS: Sequence[str] = (
    "unresolved_hook_name",
    "low_candidate_count",
    "source_path_count",
    "evidence_kinds",
    "top_source_paths",
    "summary",
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


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(_read_text(path)) if path.exists() else {}


def _load_csv_rows(path: Path) -> List[Dict[str, str]]:
    return list(csv.DictReader(_read_text(path).splitlines())) if path.exists() else []


def _short_excerpt(text: str, limit: int = 180) -> str:
    collapsed = " ".join(text.strip().split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: limit - 3].rstrip() + "..."


def _node_source(source: str, node: ast.AST | None) -> str:
    if node is None:
        return ""
    return _short_excerpt(ast.get_source_segment(source, node) or "")


def _parse_source(label: str) -> Tuple[str, ast.AST | None, str]:
    path = PROJECT_ROOT / label
    if not path.exists():
        return "", None, "missing"
    source = _read_text(path)
    try:
        return source, ast.parse(source, filename=str(path)), ""
    except SyntaxError as exc:
        return source, None, f"{exc.__class__.__name__}: {exc.msg}"


def _matching_node(source: str, tree: ast.AST | None, line: str, ast_node_type: str) -> ast.AST | None:
    if tree is None or not line.isdigit():
        return None
    line_number = int(line)
    exact: List[ast.AST] = []
    fallback: List[ast.AST] = []
    for node in ast.walk(tree):
        if getattr(node, "lineno", None) != line_number:
            continue
        fallback.append(node)
        if type(node).__name__ == ast_node_type:
            exact.append(node)
    nodes = exact or fallback
    if not nodes:
        return None
    return sorted(nodes, key=lambda node: len(_node_source(source, node)) or 10_000)[0]


def _is_live_ingest_medium(row: Mapping[str, str]) -> bool:
    return (
        row.get("confidence") == "MEDIUM"
        and row.get("source_path") == _artifact_label(INGEST_ROUTE_PATH)
        and row.get("evidence_kind") in {"import", "call"}
    )


def _why_remains_unconfirmed(row: Mapping[str, str]) -> str:
    return (
        "P520E/P520F could not resolve the imported target source path without runtime import; "
        "P520G sees a live ingest import/call reference but no direct target implementation evidence."
    )


def _recommended_next_action(row: Mapping[str, str]) -> str:
    if _is_live_ingest_medium(row):
        return "runtime-instrumentation-required"
    return "static-followup"


def _medium_cards(candidate_rows: Sequence[Mapping[str, str]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, str]]]:
    cards: List[Dict[str, Any]] = []
    parse_notes: List[Dict[str, str]] = []
    source_cache: Dict[str, Tuple[str, ast.AST | None, str]] = {}
    for row in candidate_rows:
        if row.get("confidence") != "MEDIUM":
            continue
        label = row.get("source_path", "")
        if label not in source_cache:
            source_cache[label] = _parse_source(label)
        source, tree, parse_error = source_cache[label]
        if parse_error:
            parse_notes.append({"source_path": label, "parse_error": parse_error})
        node = _matching_node(source, tree, row.get("line", ""), row.get("ast_node_type", ""))
        snippet = _node_source(source, node) or _short_excerpt(row.get("evidence", ""))
        cards.append(
            {
                "unresolved_hook_name": row.get("hook_reference", ""),
                "candidate_id": row.get("candidate_id", ""),
                "candidate_file_path": label,
                "line_number": row.get("line", ""),
                "ast_node_type": row.get("ast_node_type", ""),
                "evidence_kind": row.get("evidence_kind", ""),
                "matched_symbol_reference": row.get("matched_name", ""),
                "candidate_confidence": row.get("confidence", ""),
                "supporting_source_snippet": snippet,
                "why_it_may_match": row.get("why_candidate_matches", ""),
                "why_it_remains_unconfirmed": _why_remains_unconfirmed(row),
                "recommended_next_action": _recommended_next_action(row),
            }
        )
    return sorted(cards, key=lambda card: (card["unresolved_hook_name"], card["candidate_id"])), parse_notes


def _source_counts(rows: Iterable[Mapping[str, str]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for row in rows:
        source_path = row.get("source_path", "")
        counts[source_path] = counts.get(source_path, 0) + 1
    return counts


def _low_summary(candidate_rows: Sequence[Mapping[str, str]]) -> List[Dict[str, Any]]:
    hooks = sorted({row.get("hook_reference", "") for row in candidate_rows if row.get("hook_reference")})
    summaries: List[Dict[str, Any]] = []
    for hook in hooks:
        rows = [
            row for row in candidate_rows if row.get("hook_reference") == hook and row.get("confidence") == "LOW"
        ]
        source_counts = _source_counts(rows)
        top_sources = sorted(source_counts.items(), key=lambda item: (-item[1], item[0]))[:8]
        evidence_kinds = sorted({row.get("evidence_kind", "") for row in rows if row.get("evidence_kind")})
        summaries.append(
            {
                "unresolved_hook_name": hook,
                "low_candidate_count": len(rows),
                "source_path_count": len(source_counts),
                "evidence_kinds": ";".join(evidence_kinds),
                "top_source_paths": ";".join(f"{path} ({count})" for path, count in top_sources),
                "summary": (
                    "LOW rows are related source/tooling references retained as context only; "
                    "they are not expanded into evidence cards and do not confirm the hook target."
                ),
            }
        )
    return summaries


def _by_hook_rows(
    candidate_rows: Sequence[Mapping[str, str]],
    cards: Sequence[Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    hooks = sorted({row.get("hook_reference", "") for row in candidate_rows if row.get("hook_reference")})
    rows: List[Dict[str, Any]] = []
    for hook in hooks:
        hook_rows = [row for row in candidate_rows if row.get("hook_reference") == hook]
        hook_cards = [card for card in cards if card.get("unresolved_hook_name") == hook]
        import_card = any(card.get("evidence_kind") == "import" for card in hook_cards)
        call_card = any(card.get("evidence_kind") == "call" for card in hook_cards)
        probable_upgrade = bool(import_card and call_card)
        top_candidates = ";".join(str(card.get("candidate_id", "")) for card in hook_cards)
        rows.append(
            {
                "unresolved_hook_name": hook,
                "top_candidates": top_candidates,
                "medium_candidate_count": sum(1 for row in hook_rows if row.get("confidence") == "MEDIUM"),
                "low_candidate_count": sum(1 for row in hook_rows if row.get("confidence") == "LOW"),
                "remaining_unresolved_count": 1,
                "probable_upgrade": "probable" if probable_upgrade else "no",
                "probable_upgrade_reason": (
                    "direct live ingest import/call pair found; target implementation remains source-unresolved"
                    if probable_upgrade
                    else "no direct paired import/call evidence in MEDIUM cards"
                ),
                "confirmed": "False",
                "recommendation": (
                    "runtime-instrumentation-required"
                    if probable_upgrade
                    else "static-followup"
                ),
            }
        )
    return rows


def _p520f_summary(candidate_rows: Sequence[Mapping[str, str]], p520f_result: Mapping[str, Any]) -> Dict[str, Any]:
    confidence_counts = {
        "HIGH": sum(1 for row in candidate_rows if row.get("confidence") == "HIGH"),
        "MEDIUM": sum(1 for row in candidate_rows if row.get("confidence") == "MEDIUM"),
        "LOW": sum(1 for row in candidate_rows if row.get("confidence") == "LOW"),
    }
    by_hook: Dict[str, int] = {}
    for row in candidate_rows:
        hook = row.get("hook_reference", "")
        by_hook[hook] = by_hook.get(hook, 0) + 1
    return {
        "result_artifact": _artifact_label(P520F_RESULT_PATH),
        "candidates_artifact": _artifact_label(P520F_CANDIDATES_PATH),
        "confidence_summary_artifact": _artifact_label(P520F_CONFIDENCE_SUMMARY_PATH),
        "result_present": P520F_RESULT_PATH.exists(),
        "candidate_count": len(candidate_rows),
        "candidate_count_by_hook": dict(sorted(by_hook.items())),
        "confidence_counts": confidence_counts,
        "final_status": p520f_result.get("final_status", ""),
    }


def _status_block(result: Mapping[str, Any]) -> str:
    lines = [
        "# P520G ingest after-insert hook candidate triage status",
        "",
        f"- Final status: `{result['final_status']}`",
        f"- P520F final status: `{result['p520f_summary'].get('final_status', '')}`",
        f"- Unresolved hook count: `{result['unresolved_hook_count']}`",
        f"- Total candidate count: `{result['candidate_count']}`",
        f"- MEDIUM evidence card count: `{result['medium_candidate_count']}`",
        f"- LOW summary count: `{result['low_candidate_count']}`",
        f"- Probable upgrade count: `{result['probable_upgrade_count']}`",
        f"- Confirmed hook count: `{result['confirmed_hook_count']}`",
        f"- PASS/WARN/FAIL counts: `{result['pass_count']}/{result['warn_count']}/{result['fail_count']}`",
        "",
        "## Scope notices",
    ]
    lines.extend(f"- {notice}" for notice in NOTICE_LINES)
    lines.extend(
        [
            "",
            "## Recommendation",
            "- MEDIUM rows are direct live ingest import/call evidence and are treated as probable, not confirmed.",
            "- LOW rows remain summarized context and do not change unresolved target status.",
            "- Runtime instrumentation is required before any target implementation can be confirmed.",
        ]
    )
    return "\n".join(lines) + "\n"


def build_triage_bundle() -> Dict[str, Any]:
    candidate_rows = _load_csv_rows(P520F_CANDIDATES_PATH)
    p520f_result = _load_json(P520F_RESULT_PATH)
    p520f_confidence = _load_json(P520F_CONFIDENCE_SUMMARY_PATH)
    p520e_result = _load_json(P520E_RESULT_PATH)
    p520d_result = _load_json(P520D_RESULT_PATH)
    unresolved_rows = _load_csv_rows(P520E_UNRESOLVED_PATH)

    cards, parse_notes = _medium_cards(candidate_rows)
    by_hook = _by_hook_rows(candidate_rows, cards)
    low_summary = _low_summary(candidate_rows)
    failures = []
    if not P520F_CANDIDATES_PATH.exists():
        failures.append(f"missing artifact: {_artifact_label(P520F_CANDIDATES_PATH)}")
    if not P520F_RESULT_PATH.exists():
        failures.append(f"missing artifact: {_artifact_label(P520F_RESULT_PATH)}")

    medium_count = sum(1 for row in candidate_rows if row.get("confidence") == "MEDIUM")
    low_count = sum(1 for row in candidate_rows if row.get("confidence") == "LOW")
    probable_count = sum(1 for row in by_hook if row.get("probable_upgrade") == "probable")
    result = {
        "artifact_prefix": ARTIFACT_PREFIX,
        "final_status": "FAIL" if failures else "WARN",
        "source_path": _artifact_label(INGEST_ROUTE_PATH),
        "p520f_summary": _p520f_summary(candidate_rows, p520f_result),
        "p520f_confidence_summary_present": P520F_CONFIDENCE_SUMMARY_PATH.exists(),
        "p520f_confidence_summary_final_status": p520f_confidence.get("final_status", ""),
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
        "unresolved_hooks": sorted({row.get("hook_reference", "") for row in candidate_rows if row.get("hook_reference")}),
        "unresolved_hook_count": len({row.get("hook_reference", "") for row in candidate_rows if row.get("hook_reference")}),
        "p520e_unresolved_row_count": len(unresolved_rows),
        "candidate_count": len(candidate_rows),
        "medium_candidate_count": medium_count,
        "medium_card_count": len(cards),
        "low_candidate_count": low_count,
        "low_summary_row_count": len(low_summary),
        "probable_upgrade_count": probable_count,
        "confirmed_hook_count": 0,
        "parse_note_count": len(parse_notes),
        "parse_notes": parse_notes,
        "component_statuses": {
            "P520F candidate artifact read": "PASS" if P520F_CANDIDATES_PATH.exists() else "FAIL",
            "P520F result artifact read": "PASS" if P520F_RESULT_PATH.exists() else "FAIL",
            "P520E artifact context read": "PASS" if P520E_RESULT_PATH.exists() else "WARN",
            "P520D artifact context read": "PASS" if P520D_RESULT_PATH.exists() else "WARN",
            "source AST evaluation": "PASS" if not parse_notes else "WARN",
            "runtime import avoided": "PASS",
            "DB side effects avoided": "PASS",
            "target confirmation conservative": "PASS",
        },
        "pass_count": 0,
        "warn_count": max(1, probable_count),
        "fail_count": len(failures),
        "warning_count": max(1, probable_count),
        "warnings": [
            "MEDIUM candidates support probable live ingest references but target implementations remain unconfirmed"
        ],
        "failure_count": len(failures),
        "failures": failures,
        "notices": list(NOTICE_LINES),
        "scope": (
            "P520G reads committed P520F/P520E/P520D artifacts and parses source as text/AST only; "
            "no app runtime import; no live target module import; no after-insert hook execution; "
            "no draw insert execution; no canonical DB open/write; no migration/backfill; no deploy; "
            "does not implement or modify hooks; does not change P520F scoring."
        ),
        "suggested_next_command": "python -m tools.ingest_afterinsert_hook_candidate_triage --status-block",
    }
    return {
        "result": result,
        "medium_cards": cards,
        "by_hook": by_hook,
        "low_summary": low_summary,
        "status_block": _status_block(result),
    }


def _manifest_rows(rendered: Mapping[Path, str]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for path in (RESULT_PATH, MEDIUM_CARDS_PATH, BY_HOOK_PATH, LOW_SUMMARY_PATH, STATUS_BLOCK_PATH):
        text = rendered[path]
        data = text.encode("utf-8")
        rows.append(
            {
                "artifact_path": _artifact_label(path),
                "artifact_kind": path.suffix.lstrip("."),
                "sha256": _sha256_bytes(data),
                "bytes": len(data),
                "notes": "generated by source/AST-only P520G triage",
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
    bundle = build_triage_bundle()
    rendered: Dict[Path, str] = {
        RESULT_PATH: _json_text(bundle["result"]),
        MEDIUM_CARDS_PATH: _json_text(bundle["medium_cards"]),
        BY_HOOK_PATH: _csv_text(bundle["by_hook"], BY_HOOK_FIELDS),
        LOW_SUMMARY_PATH: _csv_text(bundle["low_summary"], LOW_SUMMARY_FIELDS),
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
    parser.add_argument("--generate", action="store_true", help="write all P520G triage artifacts")
    parser.add_argument("--triage", action="store_true", help="print triage result JSON")
    parser.add_argument("--medium-cards", action="store_true", help="print MEDIUM candidate evidence cards JSON")
    parser.add_argument("--by-hook", action="store_true", help="print by-hook recommendation CSV")
    parser.add_argument("--low-summary", action="store_true", help="print LOW candidate summary CSV")
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

    if args.triage:
        rendered = rendered or render_artifacts()
        print(rendered[RESULT_PATH], end="")

    if args.medium_cards:
        rendered = rendered or render_artifacts()
        print(rendered[MEDIUM_CARDS_PATH], end="")

    if args.by_hook:
        rendered = rendered or render_artifacts()
        print(rendered[BY_HOOK_PATH], end="")

    if args.low_summary:
        rendered = rendered or render_artifacts()
        print(rendered[LOW_SUMMARY_PATH], end="")

    if args.status_block:
        rendered = rendered or render_artifacts()
        print(rendered[STATUS_BLOCK_PATH], end="")

    if args.validate:
        ok, mismatches = validate_artifacts(rendered)
        if ok:
            print("P520G_CANDIDATE_TRIAGE_VALIDATE_OK")
        else:
            for mismatch in mismatches:
                print(mismatch, file=sys.stderr)
            return 1

    if not any(
        (
            args.generate,
            args.triage,
            args.medium_cards,
            args.by_hook,
            args.low_summary,
            args.status_block,
            args.validate,
        )
    ):
        parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
