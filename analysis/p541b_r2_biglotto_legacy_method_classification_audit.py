"""P541B-R2: fail-closed evidence remediation for the frozen BIG_LOTTO corpus.

The historical P541B artifact supplies the exact 580 source paths and the
non-safety classification context.  Every source is read as a Git blob from
``FROZEN_SOURCE_COMMIT``.  No source module is imported or executed, no
working-tree discovery is performed, and no database is opened.
"""

from __future__ import annotations

import ast
import hashlib
import json
import posixpath
import re
import subprocess
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]

TASK_ID = "P541B_R2_BIG_LOTTO_LEGACY_METHOD_CLASSIFICATION_AUDIT"
SCHEMA_VERSION = "p541b-r2-evidence-v1"
DETECTOR_VERSION = "p541b-r2-detector-v2"
BASE_MAIN_COMMIT = "c50137583243d4f9f4915a3e1d9babee50b5bbd7"
FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
GENERATED_AT_UTC = "2026-07-11T12:43:50Z"
GENERATOR_PATH = "analysis/p541b_r2_biglotto_legacy_method_classification_audit.py"

HISTORICAL_JSON_PATH = (
    "outputs/research/p541b_biglotto_legacy_method_classification_audit_20260709.json"
)
HISTORICAL_MARKDOWN_PATH = (
    "outputs/research/p541b_biglotto_legacy_method_classification_audit_20260709.md"
)
HISTORICAL_INPUTS = {
    "p541b_json": {
        "path": HISTORICAL_JSON_PATH,
        "blob_id": "12f1595c96e3f9deddc7a7d2d9549c03144635f0",
        "byte_size": 1_120_976,
        "sha256": "4828e67b06fe43e8db661c4a96fdaf37e25cef500759f7825ad96eeea1971f35",
    },
    "p541b_markdown": {
        "path": HISTORICAL_MARKDOWN_PATH,
        "blob_id": "3b28e39bfe747c5f196b9aec6610284709466cf8",
        "byte_size": 14_737,
        "sha256": "a39131ba7d4536e39a07f36314870ba210e280d6d4c71e3046f82994733ed0a9",
    },
    "p541a_json": {
        "path": "outputs/research/p541a_biglotto_strategy_inventory_replay_coverage_audit_20260709.json",
        "blob_id": "7557f364160dc09c91a19c07b370cb4b231c0194",
        "byte_size": 52_406,
        "sha256": "52a90c714b495dde43db25f5d29aa6c4f3f2442e9225cd347b6ff4cde2cb3a47",
    },
    "p541a_markdown": {
        "path": "outputs/research/p541a_biglotto_strategy_inventory_replay_coverage_audit_20260709.md",
        "blob_id": "7c2574dd80e8fbef147da0d4477a0c8eda56afe0",
        "byte_size": 5_224,
        "sha256": "d05e2e78e0378ffcb81d8e8e416aeed714d834f9ae82b43f84af4fbcda2cd34e",
    },
}

OUTPUT_JSON = Path(
    "outputs/research/p541b_r2_biglotto_legacy_method_classification_audit_20260711.json"
)
OUTPUT_MARKDOWN = Path(
    "outputs/research/p541b_r2_biglotto_legacy_method_classification_audit_20260711.md"
)

TRI_STATES = frozenset({"detected", "not_detected", "unknown"})
SCAN_STATUS_TAXONOMY = (
    "complete",
    "syntax_error",
    "unreadable",
    "unsupported",
)
SCAN_STATUSES = frozenset(SCAN_STATUS_TAXONOMY)
EFFECT_KEYS = (
    "database_access",
    "filesystem_write",
    "network_io",
    "process_execution",
    "other_external_effect",
)
RISK_EVIDENCE_KEYS = EFFECT_KEYS + (
    "transitive_external_state",
    "import_time_execution",
    "hardcoded_absolute_path",
    "hardcoded_draw_or_date",
    "database_like_path",
    "external_service_url",
)
ALL_EVIDENCE_KEYS = RISK_EVIDENCE_KEYS + (
    "filesystem_read",
    "valid_main_guard",
    "malformed_main_guard",
)

HARD_CODED_PATH_RE = re.compile(r"(?:/Users/|/home/|[A-Za-z]:\\\\)")
HARD_CODED_DRAW_RE = re.compile(r"\b1[01]\d{6,7}\b")
DATABASE_LIKE_PATH_RE = re.compile(r"[^\s]*\.(?:db|sqlite|sqlite3)\b", re.IGNORECASE)
EXTERNAL_URL_RE = re.compile(r"https?://(?:localhost|127\.0\.0\.1|[A-Za-z0-9.-]+)(?::\d+)?[^\s\"']*")

DATABASE_MARKERS = (
    "sqlite3",
    "sqlalchemy",
    "databasemanager",
    "db_manager",
    "psycopg",
    "pymysql",
    "mysql.connector",
    "create_engine",
    "sessionmaker",
)
DATABASE_LEAF_CALLS = {
    "execute",
    "executemany",
    "cursor",
    "commit",
    "rollback",
    "raw_connection",
}
FILESYSTEM_LEAF_CALLS = {
    "write_text",
    "write_bytes",
    "touch",
    "unlink",
    "rmdir",
    "mkdir",
    "rename",
    "replace",
    "chmod",
    "to_csv",
    "to_json",
    "to_excel",
    "dump",
    "dumps_to_file",
}
NETWORK_MODULE_MARKERS = (
    "requests",
    "urllib.request",
    "http.client",
    "httpx",
    "aiohttp",
    "socket",
    "ftplib",
    "smtplib",
)
NETWORK_LEAF_CALLS = {
    "urlopen",
    "urlretrieve",
    "create_connection",
    "sendmail",
}
SUBPROCESS_LEAF_CALLS = {
    "popen",
    "run",
    "call",
    "check_call",
    "check_output",
    "spawnl",
    "spawnle",
    "spawnlp",
    "spawnlpe",
    "spawnv",
    "spawnve",
    "spawnvp",
    "spawnvpe",
    "system",
}

READ_LEAF_CALLS = {"read", "read_text", "read_bytes", "load", "loads", "fetchone", "fetchall"}
DATABASE_READ_WORDS = {"select", "pragma", "explain", "show", "describe"}
DATABASE_WRITE_WORDS = {"insert", "update", "delete", "replace", "create", "alter", "drop", "vacuum"}
OTHER_EXTERNAL_CALLS = {
    "eval",
    "exec",
    "compile",
    "__import__",
    "input",
    "breakpoint",
}

DISCLAIMER = (
    "Historical static safety-evidence remediation only. This artifact does not "
    "establish prediction quality, replay readiness, betting edge, ROI, or "
    "production safety."
)


class P541BR2Error(RuntimeError):
    """Raised when pinned provenance or the fail-closed contract is violated."""


def canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise P541BR2Error("value is not finite canonical JSON") from exc


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _strict_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise P541BR2Error(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def strict_json_bytes(raw: bytes) -> dict[str, Any]:
    def reject_constant(value: str) -> None:
        raise P541BR2Error(f"non-finite JSON constant: {value}")

    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_strict_pairs,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise P541BR2Error("historical input is not strict UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise P541BR2Error("historical input must be a JSON object")
    return value


def _safe_repo_path(path: str) -> None:
    relative = PurePosixPath(path)
    if (
        not isinstance(path, str)
        or not path
        or relative.is_absolute()
        or ".." in relative.parts
        or "\x00" in path
        or "\\" in path
    ):
        raise P541BR2Error(f"unsafe repository path: {path!r}")


def run_git(repo_root: Path, arguments: Sequence[str], *, stdin: bytes | None = None) -> bytes:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=repo_root,
        input=stdin,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise P541BR2Error(f"git {' '.join(arguments[:2])} failed: {detail}")
    return completed.stdout


def git_tree_entries(
    repo_root: Path, commit: str, paths: Sequence[str]
) -> dict[str, dict[str, str]]:
    if not paths:
        return {}
    for path in paths:
        _safe_repo_path(path)
    raw = run_git(repo_root, ["ls-tree", "-z", commit, "--", *paths])
    result: dict[str, dict[str, str]] = {}
    for record in raw.split(b"\x00"):
        if not record:
            continue
        metadata, encoded_path = record.split(b"\t", 1)
        mode, object_type, oid = metadata.decode("ascii").split(" ")
        path = encoded_path.decode("utf-8")
        result[path] = {"mode": mode, "type": object_type, "blob_id": oid}
    return result


def git_blob(repo_root: Path, blob_id: str) -> bytes:
    if not re.fullmatch(r"[0-9a-f]{40}", blob_id):
        raise P541BR2Error(f"invalid Git blob id: {blob_id!r}")
    return run_git(repo_root, ["cat-file", "blob", blob_id])


def validate_historical_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    records = payload.get("method_classification_records")
    if (
        payload.get("schema_version") != "1.0"
        or payload.get("task_id") != "P541B_BIG_LOTTO_LEGACY_METHOD_CLASSIFICATION_AUDIT"
        or not isinstance(records, list)
        or len(records) != 580
    ):
        raise P541BR2Error("historical P541B schema or record count mismatch")
    method_ids = [record.get("method_id") for record in records if isinstance(record, dict)]
    paths = [record.get("source_path") for record in records if isinstance(record, dict)]
    if (
        len(method_ids) != 580
        or any(not isinstance(method_id, str) or not method_id for method_id in method_ids)
        or len(set(method_ids)) != 580
    ):
        raise P541BR2Error("historical P541B method IDs are incomplete or non-unique")
    if (
        len(paths) != 580
        or any(not isinstance(path, str) for path in paths)
        or len(set(paths)) != 580
    ):
        raise P541BR2Error("historical P541B source paths are incomplete or non-unique")
    for path in paths:
        _safe_repo_path(path)
        if PurePosixPath(path).suffix != ".py":
            raise P541BR2Error(f"historical source path is not a non-DB Python path: {path}")
    return records


def verified_historical_inputs(
    repo_root: Path = REPO_ROOT,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    paths = [identity["path"] for identity in HISTORICAL_INPUTS.values()]
    entries = git_tree_entries(repo_root, FROZEN_SOURCE_COMMIT, paths)
    provenance: dict[str, dict[str, Any]] = {}
    payload: dict[str, Any] | None = None
    for name, expected in HISTORICAL_INPUTS.items():
        path = expected["path"]
        entry = entries.get(path)
        if not entry or entry["type"] != "blob" or entry["mode"] not in {"100644", "100755"}:
            raise P541BR2Error(f"historical input is not a regular Git blob: {path}")
        raw = git_blob(repo_root, entry["blob_id"])
        if (
            entry["blob_id"] != expected["blob_id"]
            or len(raw) != expected["byte_size"]
            or sha256_bytes(raw) != expected["sha256"]
        ):
            raise P541BR2Error(f"historical input identity mismatch: {path}")
        provenance[name] = {
            **expected,
            "source_commit": FROZEN_SOURCE_COMMIT,
            "verification": "PASS",
            "read_method": "git ls-tree + git cat-file blob",
        }
        if name == "p541b_json":
            payload = strict_json_bytes(raw)
    if payload is None:
        raise P541BR2Error("historical JSON was not loaded")
    validate_historical_payload(payload)
    return payload, provenance


def _dotted_name(node: ast.AST, aliases: dict[str, str], seen: frozenset[str] = frozenset()) -> str | None:
    if isinstance(node, ast.Name):
        if node.id in seen:
            return node.id
        replacement = aliases.get(node.id)
        if replacement and replacement != node.id:
            return replacement
        return node.id
    if isinstance(node, ast.Attribute):
        base = _dotted_name(node.value, aliases, seen)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Call):
        base = _dotted_name(node.func, aliases, seen)
        return f"{base}()" if base else None
    return None


def collect_aliases(tree: ast.AST) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                aliases[alias.asname or alias.name.split(".")[0]] = alias.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                if alias.name != "*":
                    aliases[alias.asname or alias.name] = f"{node.module}.{alias.name}"

    # Propagate straightforward aliases and constructed manager/session objects.
    for _ in range(4):
        changed = False
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            value = getattr(node, "value", None)
            if value is None:
                continue
            targets: list[ast.AST]
            if isinstance(node, ast.Assign):
                targets = list(node.targets)
            else:
                targets = [node.target]
            resolved = _dotted_name(value, aliases)
            if not resolved:
                continue
            for target in targets:
                if isinstance(target, ast.Name) and aliases.get(target.id) != resolved:
                    aliases[target.id] = resolved
                    changed = True
        if not changed:
            break
    return aliases


def is_valid_main_guard_test(test: ast.AST) -> bool:
    if not (
        isinstance(test, ast.Compare)
        and len(test.ops) == 1
        and isinstance(test.ops[0], ast.Eq)
        and len(test.comparators) == 1
    ):
        return False
    left, right = test.left, test.comparators[0]

    def is_name(node: ast.AST) -> bool:
        return isinstance(node, ast.Name) and node.id == "__name__"

    def is_main(node: ast.AST) -> bool:
        return isinstance(node, ast.Constant) and node.value == "__main__"

    return (is_name(left) and is_main(right)) or (is_main(left) and is_name(right))


def _mentions_name_guard(test: ast.AST) -> bool:
    return any(isinstance(node, ast.Name) and node.id == "__name__" for node in ast.walk(test))


class _RuntimeCallVisitor(ast.NodeVisitor):
    """Collect calls evaluated while a module is imported.

    Function/lambda bodies are deferred, while decorators and default values
    are evaluated at definition time. Class bodies execute at import time.
    """

    def __init__(self) -> None:
        self.calls: list[ast.Call] = []

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        self.calls.append(node)
        self.generic_visit(node)

    def _visit_function_header(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        for item in [*node.decorator_list, *node.args.defaults, *node.args.kw_defaults]:
            if item is not None:
                self.visit(item)
        if node.returns:
            self.visit(node.returns)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
        self._visit_function_header(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: N802
        self._visit_function_header(node)

    def visit_Lambda(self, node: ast.Lambda) -> None:  # noqa: N802
        for item in [*node.args.defaults, *node.args.kw_defaults]:
            if item is not None:
                self.visit(item)


def import_time_calls(tree: ast.Module) -> list[ast.Call]:
    visitor = _RuntimeCallVisitor()
    for statement in tree.body:
        if isinstance(statement, ast.If) and is_valid_main_guard_test(statement.test):
            for alternate in statement.orelse:
                visitor.visit(alternate)
            continue
        visitor.visit(statement)
    return visitor.calls


def guarded_calls(tree: ast.Module) -> list[ast.Call]:
    visitor = _RuntimeCallVisitor()
    for statement in tree.body:
        if isinstance(statement, ast.If) and is_valid_main_guard_test(statement.test):
            for guarded_statement in statement.body:
                visitor.visit(guarded_statement)
    return visitor.calls


def _call_mode(call: ast.Call) -> str | None:
    value: ast.AST | None = call.args[1] if len(call.args) >= 2 else None
    for keyword in call.keywords:
        if keyword.arg == "mode":
            value = keyword.value
    if value is None:
        return "r"
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        return value.value
    return None


def _call_finding(
    call: ast.Call,
    resolved: str,
    scope: str,
    source_path: str,
    family: str,
    *,
    classification: str = "direct",
    imported_module_path: str | None = None,
    operation: str | None = None,
) -> dict[str, Any]:
    finding: dict[str, Any] = {
        "line": getattr(call, "lineno", None),
        "column": getattr(call, "col_offset", None),
        "rule_id": f"{classification}.{family}",
        "resolved_api": resolved,
        "resolved_syntax": None,
        "scope": scope,
        "direct_or_transitive": classification,
        "source_path": source_path,
        "imported_module_path": imported_module_path,
    }
    if operation is not None:
        finding["operation"] = operation
    return finding


def _db_operation(call: ast.Call, resolved: str) -> str:
    leaf = resolved.lower().replace("()", "").rsplit(".", 1)[-1]
    if leaf in {"fetchone", "fetchall", "select", "query", "read_sql"}:
        return "read"
    if leaf in {"commit", "rollback", "insert", "update", "delete", "write"}:
        return "write"
    if call.args and isinstance(call.args[0], ast.Constant) and isinstance(call.args[0].value, str):
        first_word = call.args[0].value.strip().split(None, 1)[0].lower() if call.args[0].value.strip() else ""
        if first_word in DATABASE_READ_WORDS:
            return "read"
        if first_word in DATABASE_WRITE_WORDS:
            return "write"
    return "unknown"


def classify_call(
    call: ast.Call, resolved: str
) -> tuple[set[str], list[str]]:
    normalized = resolved.lower().replace("()", "")
    leaf = normalized.rsplit(".", 1)[-1]
    categories: set[str] = set()
    unsupported: list[str] = []

    if any(marker in normalized for marker in DATABASE_MARKERS) or leaf in DATABASE_LEAF_CALLS:
        categories.add("database_access")

    is_open = leaf == "open"
    if is_open:
        mode = _call_mode(call)
        if mode is None:
            unsupported.append(f"dynamic file mode at line {getattr(call, 'lineno', '?')}")
        elif any(character in mode for character in "wax+"):
            categories.add("filesystem_write")
        else:
            categories.add("filesystem_read")
    if leaf in FILESYSTEM_LEAF_CALLS:
        categories.add("filesystem_write")
    if leaf in READ_LEAF_CALLS and (
        "path" in normalized or normalized.startswith("json.") or normalized.startswith("pickle.")
    ):
        categories.add("filesystem_read")
    if normalized.startswith("os.") and leaf in {
        "remove", "unlink", "rename", "replace", "mkdir", "makedirs", "rmdir",
    }:
        categories.add("filesystem_write")
    if normalized.startswith("shutil.") and leaf in {
        "copy", "copy2", "copyfile", "copytree", "move", "rmtree",
    }:
        categories.add("filesystem_write")

    network_method = leaf in {"get", "post", "put", "delete", "patch", "head", "request"}
    if (
        any(marker in normalized for marker in NETWORK_MODULE_MARKERS)
        and (network_method or leaf in NETWORK_LEAF_CALLS or "clientsession" in normalized)
    ) or leaf in NETWORK_LEAF_CALLS:
        categories.add("network_io")

    if normalized.startswith("subprocess.") or (
        normalized.startswith("os.") and leaf in SUBPROCESS_LEAF_CALLS
    ):
        categories.add("process_execution")

    if leaf in OTHER_EXTERNAL_CALLS or normalized in {
        "sys.exit", "os._exit", "importlib.import_module",
    }:
        categories.add("other_external_effect")
    if leaf in {"__import__", "eval", "exec", "compile"} or normalized == "importlib.import_module":
        unsupported.append(f"dynamic code/import at line {getattr(call, 'lineno', '?')}")
    return categories, unsupported


def _evidence(
    state: str,
    *,
    scope: str,
    findings: Iterable[dict[str, Any]] = (),
    reason: str | None = None,
) -> dict[str, Any]:
    if state not in TRI_STATES:
        raise P541BR2Error(f"invalid evidence state: {state}")
    result: dict[str, Any] = {
        "state": state,
        "scope": scope,
        "detector_id": DETECTOR_VERSION,
        "findings": sorted(
            list(findings),
            key=lambda item: (
                item.get("source_path", ""),
                item.get("line") if item.get("line") is not None else -1,
                item.get("column") if item.get("column") is not None else -1,
                item.get("rule_id", ""),
                item.get("resolved_api") or "",
                item.get("resolved_syntax") or "",
                item.get("imported_module_path") or "",
            ),
        )[:100],
    }
    if reason:
        result["reason"] = reason
    return result


def unknown_analysis(
    source_path: str,
    raw: bytes,
    blob_id: str,
    reason: str,
    scan_status: str,
) -> dict[str, Any]:
    if scan_status not in SCAN_STATUSES or scan_status == "complete":
        raise P541BR2Error(f"invalid incomplete scan status: {scan_status}")
    return {
        "schema_version": SCHEMA_VERSION,
        "detector_version": DETECTOR_VERSION,
        "source_identity": {
            "source_path": source_path,
            "source_commit": FROZEN_SOURCE_COMMIT,
            "blob_id": blob_id,
            "byte_size": len(raw),
            "sha256": sha256_bytes(raw),
            "utf8_decoding_status": "failed" if scan_status == "unreadable" else "succeeded",
        },
        "scan_status": scan_status,
        "scan": {
            "status": scan_status,
            "complete": False,
            "error": {"type": scan_status, "message": reason},
        },
        "evidence": {
            key: _evidence("unknown", scope="unknown", reason=reason)
            for key in ALL_EVIDENCE_KEYS
        },
        "safety_classification": {
            "risk_level": "unknown",
            "low_risk_eligible": False,
            "disposition": "BLOCKED_UNKNOWN",
            "reasons": [reason],
        },
    }


def _literal_findings(
    tree: ast.Module, pattern: re.Pattern[str], source_path: str, family: str
) -> list[dict[str, Any]]:
    docstring_ids: set[int] = set()
    for owner in [tree, *[node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]]:
        body = getattr(owner, "body", [])
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            docstring_ids.add(id(body[0].value))
    findings: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if (
            not isinstance(node, ast.Constant)
            or not isinstance(node.value, str)
            or id(node) in docstring_ids
        ):
            continue
        for match in pattern.finditer(node.value):
            findings.append(
                {
                    "line": getattr(node, "lineno", None),
                    "column": getattr(node, "col_offset", 0) + match.start(),
                    "rule_id": f"direct.{family}",
                    "resolved_api": None,
                    "resolved_syntax": match.group(0)[:160],
                    "scope": "whole_file",
                    "direct_or_transitive": "direct",
                    "source_path": source_path,
                    "imported_module_path": None,
                }
            )
    return findings


def classify_safety(scan_status: str, evidence: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if scan_status != "complete":
        reason = f"scan_status={scan_status}"
        return {
            "risk_level": "unknown",
            "low_risk_eligible": False,
            "disposition": "NEEDS_CTO_REVIEW_UNKNOWN",
            "reasons": [reason],
        }
    unknown = sorted(key for key in RISK_EVIDENCE_KEYS if evidence[key]["state"] == "unknown")
    if unknown:
        return {
            "risk_level": "unknown",
            "low_risk_eligible": False,
            "disposition": "NEEDS_CTO_REVIEW_UNKNOWN",
            "reasons": [f"unknown:{key}" for key in unknown],
        }
    detected_effects = sorted(
        key
        for key in (*EFFECT_KEYS, "transitive_external_state")
        if evidence[key]["state"] == "detected"
    )
    if detected_effects:
        return {
            "risk_level": "high",
            "low_risk_eligible": False,
            "disposition": "BLOCKED_EXTERNAL_EFFECT",
            "reasons": [f"detected:{key}" for key in detected_effects],
        }
    detected_static = sorted(
        key
        for key in (
            "import_time_execution",
            "hardcoded_absolute_path",
            "hardcoded_draw_or_date",
            "database_like_path",
            "external_service_url",
        )
        if evidence[key]["state"] == "detected"
    )
    if detected_static:
        return {
            "risk_level": "medium",
            "low_risk_eligible": False,
            "disposition": "BLOCKED_STATIC_RISK",
            "reasons": [f"detected:{key}" for key in detected_static],
        }
    if all(evidence[key]["state"] == "not_detected" for key in RISK_EVIDENCE_KEYS):
        return {
            "risk_level": "low",
            "low_risk_eligible": True,
            "disposition": "STATIC_LOW_RISK_ELIGIBLE",
            "reasons": [],
        }
    raise P541BR2Error("complete scan did not resolve every safety-relevant evidence family")


def analyze_source_bytes(
    source_path: str,
    raw: bytes,
    blob_id: str,
    *,
    transitive_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        return unknown_analysis(
            source_path, raw, blob_id, f"UTF-8 decode failure at byte {exc.start}", "unreadable"
        )
    try:
        tree = ast.parse(content, filename=source_path)
    except SyntaxError as exc:
        return unknown_analysis(
            source_path,
            raw,
            blob_id,
            f"AST parse failure: {exc.msg} (line {exc.lineno})",
            "syntax_error",
        )

    aliases = collect_aliases(tree)
    runtime_call_ids = {id(call) for call in import_time_calls(tree)}
    guarded_call_ids = {id(call) for call in guarded_calls(tree)}
    findings: dict[str, list[dict[str, Any]]] = {
        key: [] for key in (*EFFECT_KEYS, "filesystem_read")
    }
    unsupported: list[str] = []
    ambiguous_database: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and any(alias.name == "*" for alias in node.names):
            unsupported.append(f"star import at line {getattr(node, 'lineno', '?')}")
        if not isinstance(node, ast.Call):
            continue
        resolved = _dotted_name(node.func, aliases) or "<unresolved>"
        categories, call_unsupported = classify_call(node, resolved)
        unsupported.extend(call_unsupported)
        if id(node) in runtime_call_ids:
            scope = "module_load"
        elif id(node) in guarded_call_ids:
            scope = "main_guard"
        else:
            scope = "callable_body"
        for category in categories:
            operation = _db_operation(node, resolved) if category == "database_access" else None
            findings[category].append(
                _call_finding(
                    node,
                    resolved,
                    scope,
                    source_path,
                    category,
                    operation=operation,
                )
            )
        lowered = resolved.lower().replace("()", "")
        db_tokens = set(re.split(r"[^a-z0-9_]+", lowered))
        if not categories & {"database_access"} and db_tokens & {
            "db", "database", "sql", "session", "engine", "connection",
        }:
            ambiguous_database.append(
                _call_finding(
                    node,
                    resolved,
                    scope,
                    source_path,
                    "database_access",
                    operation="unknown",
                )
            )

    if unsupported:
        reason = f"unsupported static structure: {'; '.join(sorted(set(unsupported)))}"
        result = unknown_analysis(source_path, raw, blob_id, reason, "unsupported")
        for key, partial in findings.items():
            result["evidence"][key]["findings"] = _evidence(
                "unknown", scope="unknown", findings=partial, reason=reason
            )["findings"]
        return result

    valid_guards = [
        node for node in tree.body
        if isinstance(node, ast.If) and is_valid_main_guard_test(node.test)
    ]
    malformed_guards = [
        node for node in tree.body
        if isinstance(node, ast.If)
        and _mentions_name_guard(node.test)
        and not is_valid_main_guard_test(node.test)
    ]
    valid_guard_findings = [
        {
            "line": node.lineno,
            "column": node.col_offset,
            "rule_id": "direct.valid_main_guard",
            "resolved_api": None,
            "resolved_syntax": "__name__ == '__main__'",
            "scope": "main_guard",
            "direct_or_transitive": "direct",
            "source_path": source_path,
            "imported_module_path": None,
            "executable_statements": any(
                not isinstance(statement, ast.Pass)
                and not (
                    isinstance(statement, ast.Expr)
                    and isinstance(statement.value, ast.Constant)
                    and isinstance(statement.value.value, str)
                )
                for statement in node.body
            ),
        }
        for node in valid_guards
    ]
    malformed_findings = [
        {
            "line": node.lineno,
            "column": node.col_offset,
            "rule_id": "direct.malformed_main_guard",
            "resolved_api": None,
            "resolved_syntax": ast.dump(node.test, include_attributes=False),
            "scope": "module_load",
            "direct_or_transitive": "direct",
            "source_path": source_path,
            "imported_module_path": None,
        }
        for node in malformed_guards
    ]
    module_effect_findings = sorted(
        [
            finding
            for key in EFFECT_KEYS
            for finding in findings[key]
            if finding["scope"] == "module_load"
        ],
        key=lambda item: (item["line"], item["column"], item["rule_id"]),
    )

    evidence: dict[str, dict[str, Any]] = {}
    for key in (*EFFECT_KEYS, "filesystem_read"):
        if key == "database_access" and ambiguous_database and not findings[key]:
            evidence[key] = _evidence(
                "unknown",
                scope="whole_file",
                findings=ambiguous_database,
                reason="ambiguous DB-like API could not be resolved",
            )
        else:
            evidence[key] = _evidence(
                "detected" if findings[key] else "not_detected",
                scope="whole_file",
                findings=findings[key],
            )
    evidence["transitive_external_state"] = transitive_evidence or _evidence(
        "unknown",
        scope="transitive",
        reason="one-hop resolver not supplied",
    )
    evidence["import_time_execution"] = _evidence(
        "detected" if module_effect_findings else "not_detected",
        scope="module_load",
        findings=module_effect_findings,
    )
    for key, pattern in (
        ("hardcoded_absolute_path", HARD_CODED_PATH_RE),
        ("hardcoded_draw_or_date", HARD_CODED_DRAW_RE),
        ("database_like_path", DATABASE_LIKE_PATH_RE),
        ("external_service_url", EXTERNAL_URL_RE),
    ):
        text_findings = _literal_findings(tree, pattern, source_path, key)
        evidence[key] = _evidence(
            "detected" if text_findings else "not_detected",
            scope="whole_file",
            findings=text_findings,
        )
    evidence["valid_main_guard"] = _evidence(
        "detected" if valid_guard_findings else "not_detected",
        scope="main_guard",
        findings=valid_guard_findings,
    )
    evidence["malformed_main_guard"] = _evidence(
        "detected" if malformed_findings else "not_detected",
        scope="module_load",
        findings=malformed_findings,
    )

    result = {
        "schema_version": SCHEMA_VERSION,
        "detector_version": DETECTOR_VERSION,
        "source_identity": {
            "source_path": source_path,
            "source_commit": FROZEN_SOURCE_COMMIT,
            "blob_id": blob_id,
            "byte_size": len(raw),
            "sha256": sha256_bytes(raw),
            "utf8_decoding_status": "succeeded",
        },
        "scan_status": "complete",
        "scan": {
            "status": "complete",
            "complete": True,
            "encoding": "UTF-8",
            "parser": "python ast.parse",
            "error": None,
        },
        "evidence": evidence,
    }
    result["safety_classification"] = classify_safety("complete", evidence)
    return result


def complete_transitive_absence() -> dict[str, Any]:
    return _evidence("not_detected", scope="transitive")


def _absolute_import_module(source_path: str, module: str | None, level: int) -> str | None:
    if level == 0:
        return module
    package_parts = list(PurePosixPath(source_path).parent.parts)
    remove = level - 1
    if remove > len(package_parts):
        return None
    base = package_parts[: len(package_parts) - remove]
    if module:
        base.extend(module.split("."))
    return ".".join(part for part in base if part)


def _import_bindings(tree: ast.Module, source_path: str) -> list[dict[str, Any]]:
    bindings: list[dict[str, Any]] = []
    for statement in tree.body:
        if isinstance(statement, ast.Import):
            for alias in statement.names:
                bindings.append(
                    {
                        "module": alias.name,
                        "symbol": None,
                        "local_name": alias.asname or alias.name.split(".")[0],
                        "line": statement.lineno,
                        "column": statement.col_offset,
                        "relative": False,
                    }
                )
        elif isinstance(statement, ast.ImportFrom):
            module = _absolute_import_module(source_path, statement.module, statement.level)
            for alias in statement.names:
                bindings.append(
                    {
                        "module": module,
                        "symbol": alias.name,
                        "local_name": alias.asname or alias.name,
                        "line": statement.lineno,
                        "column": statement.col_offset,
                        "relative": statement.level > 0,
                    }
                )
    return bindings


def _module_candidates(module: str, symbol: str | None) -> list[str]:
    base = module.replace(".", "/")
    candidates = [f"{base}.py", f"{base}/__init__.py"]
    if symbol and symbol != "*":
        candidates.extend([f"{base}/{symbol}.py", f"{base}/{symbol}/__init__.py"])
    return list(dict.fromkeys(candidates))


def _resolve_project_binding(
    repo_root: Path,
    commit: str,
    binding: dict[str, Any],
    cache: dict[tuple[str | None, str | None], tuple[str, str | None]],
) -> tuple[str, str | None]:
    key = (binding["module"], binding["symbol"])
    if key in cache:
        return cache[key]
    module = binding["module"]
    if not module:
        result = ("unknown", "relative import has no resolvable module")
        cache[key] = result
        return result
    candidates = _module_candidates(module, binding["symbol"])
    entries = git_tree_entries(repo_root, commit, candidates)
    resolved = [path for path in candidates if path in entries]
    if len(resolved) > 1:
        result = ("unknown", f"ambiguous project import resolves to {resolved}")
    elif len(resolved) == 1:
        result = (resolved[0], None)
    elif binding["relative"]:
        result = ("unknown", f"relative project import not found: {module}")
    else:
        # Absent absolute modules are external dependencies, not project imports.
        result = ("external", None)
    cache[key] = result
    return result


def _invoked_definition_names(tree: ast.Module, binding: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    local = binding["local_name"]
    symbol = binding["symbol"]
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        raw_name = _dotted_name(node.func, {}) or ""
        parts = raw_name.replace("()", "").split(".")
        if not parts or parts[0] != local:
            continue
        if symbol and len(parts) == 1:
            names.add(symbol)
        elif len(parts) >= 2:
            names.add(parts[-1])
    return names


def _definition_effect_findings(
    imported_tree: ast.Module,
    imported_path: str,
    importing_path: str,
    definition_names: set[str],
) -> list[dict[str, Any]]:
    aliases = collect_aliases(imported_tree)
    target_nodes: list[ast.AST] = []
    for node in imported_tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in definition_names:
            target_nodes.extend(node.body)
        elif isinstance(node, ast.ClassDef) and node.name in definition_names:
            target_nodes.extend(
                child
                for item in node.body
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == "__init__"
                for child in item.body
            )
    findings: list[dict[str, Any]] = []
    for target in target_nodes:
        for node in ast.walk(target):
            if not isinstance(node, ast.Call):
                continue
            resolved = _dotted_name(node.func, aliases) or "<unresolved>"
            categories, _ = classify_call(node, resolved)
            for category in sorted(categories & set(EFFECT_KEYS)):
                findings.append(
                    _call_finding(
                        node,
                        resolved,
                        "transitive",
                        importing_path,
                        category,
                        classification="transitive",
                        imported_module_path=imported_path,
                        operation=_db_operation(node, resolved) if category == "database_access" else None,
                    )
                )
    return findings


def one_hop_transitive_evidence(
    source_path: str,
    raw: bytes,
    repo_root: Path,
    commit: str,
    *,
    resolution_cache: dict[tuple[str | None, str | None], tuple[str, str | None]] | None = None,
    blob_cache: dict[str, bytes] | None = None,
) -> dict[str, Any]:
    try:
        content = raw.decode("utf-8")
        tree = ast.parse(content, filename=source_path)
    except (UnicodeDecodeError, SyntaxError) as exc:
        return _evidence(
            "unknown",
            scope="transitive",
            reason=f"importing source unavailable for one-hop analysis: {type(exc).__name__}",
        )
    resolution_cache = resolution_cache if resolution_cache is not None else {}
    blob_cache = blob_cache if blob_cache is not None else {}
    findings: list[dict[str, Any]] = []
    unknown_reasons: list[str] = []
    for binding in _import_bindings(tree, source_path):
        resolved_path, issue = _resolve_project_binding(
            repo_root, commit, binding, resolution_cache
        )
        if resolved_path == "external":
            continue
        if resolved_path == "unknown":
            unknown_reasons.append(issue or "ambiguous import resolution")
            continue
        if resolved_path == source_path:  # One-hop cycle stops without recursion.
            continue
        entries = git_tree_entries(repo_root, commit, [resolved_path])
        entry = entries.get(resolved_path)
        if not entry or entry["type"] != "blob" or entry["mode"] not in {"100644", "100755"}:
            unknown_reasons.append(f"imported project module is not a regular blob: {resolved_path}")
            continue
        imported_raw = blob_cache.get(entry["blob_id"])
        if imported_raw is None:
            imported_raw = git_blob(repo_root, entry["blob_id"])
            blob_cache[entry["blob_id"]] = imported_raw
        imported = analyze_source_bytes(
            resolved_path,
            imported_raw,
            entry["blob_id"],
            transitive_evidence=complete_transitive_absence(),
        )
        if imported["scan_status"] != "complete":
            unknown_reasons.append(
                f"imported module {resolved_path} scan_status={imported['scan_status']}"
            )
            continue
        for family in EFFECT_KEYS:
            for direct in imported["evidence"][family]["findings"]:
                if direct["scope"] != "module_load":
                    continue
                findings.append(
                    {
                        **direct,
                        "rule_id": f"transitive.{family}.module_load",
                        "scope": "transitive",
                        "direct_or_transitive": "transitive",
                        "source_path": source_path,
                        "imported_module_path": resolved_path,
                        "import_line": binding["line"],
                    }
                )
        definition_names = _invoked_definition_names(tree, binding)
        if definition_names:
            try:
                imported_tree = ast.parse(imported_raw.decode("utf-8"), filename=resolved_path)
            except (UnicodeDecodeError, SyntaxError) as exc:
                unknown_reasons.append(
                    f"invoked imported definition unavailable in {resolved_path}: {type(exc).__name__}"
                )
            else:
                findings.extend(
                    _definition_effect_findings(
                        imported_tree,
                        resolved_path,
                        source_path,
                        definition_names,
                    )
                )
    if unknown_reasons:
        return _evidence(
            "unknown",
            scope="transitive",
            findings=findings,
            reason="; ".join(sorted(set(unknown_reasons))),
        )
    return _evidence(
        "detected" if findings else "not_detected",
        scope="transitive",
        findings=findings,
    )


def _historical_context(record: dict[str, Any]) -> dict[str, Any]:
    excluded = {"evidence", "source_path", "method_id"}
    return {key: value for key, value in record.items() if key not in excluded}


def require_frozen_entries(
    paths: Sequence[str], entries: dict[str, dict[str, str]]
) -> None:
    missing = [path for path in paths if path not in entries]
    if missing or len(entries) != len(paths):
        raise P541BR2Error(f"frozen source corpus incomplete: {missing[:5]}")


def validate_consumer_contract(schema_version: str, detector_version: str) -> None:
    if schema_version != SCHEMA_VERSION:
        raise P541BR2Error(f"unknown schema version: {schema_version}")
    if detector_version != DETECTOR_VERSION:
        raise P541BR2Error(f"unknown detector version: {detector_version}")


def validate_artifact(artifact: dict[str, Any]) -> None:
    validate_consumer_contract(
        str(artifact.get("schema_version")), str(artifact.get("detector_version"))
    )
    if artifact.get("scan_status_taxonomy") != list(SCAN_STATUS_TAXONOMY):
        raise P541BR2Error("scan status taxonomy mismatch")
    if artifact.get("task_id") != TASK_ID:
        raise P541BR2Error("artifact identity mismatch")
    records = artifact.get("method_classification_records")
    if not isinstance(records, list) or len(records) != 580:
        raise P541BR2Error("artifact must contain exactly 580 records")
    paths = [record.get("source_path") for record in records]
    method_ids = [record.get("method_id") for record in records]
    if len(set(paths)) != 580 or len(set(method_ids)) != 580:
        raise P541BR2Error("artifact method IDs or source paths are not unique")
    for record in records:
        validate_consumer_contract(
            str(record.get("schema_version")), str(record.get("detector_version"))
        )
        if record.get("scan_status") not in SCAN_STATUSES:
            raise P541BR2Error(f"scan status mismatch: {record.get('source_path')}")
        evidence = record.get("evidence")
        if not isinstance(evidence, dict) or set(evidence) != set(ALL_EVIDENCE_KEYS):
            raise P541BR2Error(f"evidence schema mismatch: {record.get('source_path')}")
        states = {item.get("state") for item in evidence.values()}
        if not states <= TRI_STATES:
            raise P541BR2Error(f"invalid evidence state: {record.get('source_path')}")
        for item in evidence.values():
            if not {"state", "scope", "detector_id", "findings"} <= set(item):
                raise P541BR2Error(f"incomplete structured evidence: {record.get('source_path')}")
            if item["detector_id"] != DETECTOR_VERSION or not isinstance(item["findings"], list):
                raise P541BR2Error(f"detector evidence identity mismatch: {record.get('source_path')}")
            for finding in item["findings"]:
                required = {
                    "line", "column", "rule_id", "resolved_api", "resolved_syntax",
                    "scope", "direct_or_transitive", "source_path", "imported_module_path",
                }
                if (
                    not required <= set(finding)
                    or "resolved_api_or_syntax" in finding
                    or "imported_module_source" in finding
                ):
                    raise P541BR2Error(f"finding contract mismatch: {record.get('source_path')}")
                resolved_api = finding["resolved_api"]
                resolved_syntax = finding["resolved_syntax"]
                if (
                    (resolved_api is None) == (resolved_syntax is None)
                    or (resolved_api is not None and not isinstance(resolved_api, str))
                    or (resolved_syntax is not None and not isinstance(resolved_syntax, str))
                ):
                    raise P541BR2Error(f"finding resolution mismatch: {record.get('source_path')}")
                classification = finding["direct_or_transitive"]
                imported_module_path = finding["imported_module_path"]
                if classification == "direct" and imported_module_path is not None:
                    raise P541BR2Error(f"direct finding import mismatch: {record.get('source_path')}")
                if classification == "transitive":
                    if not isinstance(imported_module_path, str) or not imported_module_path:
                        raise P541BR2Error(f"transitive finding import mismatch: {record.get('source_path')}")
                    _safe_repo_path(imported_module_path)
                elif classification != "direct":
                    raise P541BR2Error(f"finding classification mismatch: {record.get('source_path')}")
        scan_complete = record.get("scan", {}).get("complete") is True
        low_risk = record.get("safety_classification", {}).get("low_risk_eligible") is True
        if low_risk and (
            not scan_complete
            or any(evidence[key]["state"] != "not_detected" for key in RISK_EVIDENCE_KEYS)
        ):
            raise P541BR2Error(f"unsafe low-risk classification: {record.get('source_path')}")
    manifest = artifact.get("provenance", {}).get("source_manifest", {})
    identities = [record["source_identity"] for record in records]
    digest = sha256_bytes(canonical_bytes(identities))
    if (
        manifest.get("record_count") != 580
        or manifest.get("canonical_sha256") != digest
        or manifest.get("verification") != "PASS"
        or manifest.get("ordered_entries") != identities
    ):
        raise P541BR2Error("source manifest invariant mismatch")
    canonical_bytes(artifact)


def build_artifact(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    historical, historical_provenance = verified_historical_inputs(repo_root)
    historical_records = historical["method_classification_records"]
    paths = [record["source_path"] for record in historical_records]
    entries = git_tree_entries(repo_root, FROZEN_SOURCE_COMMIT, paths)
    require_frozen_entries(paths, entries)

    records: list[dict[str, Any]] = []
    raw_by_path: dict[str, bytes] = {}
    blob_cache: dict[str, bytes] = {}
    resolution_cache: dict[tuple[str | None, str | None], tuple[str, str | None]] = {}
    for historical_record in historical_records:
        source_path = historical_record["source_path"]
        _safe_repo_path(source_path)
        entry = entries[source_path]
        if (
            Path(source_path).suffix != ".py"
            or entry["type"] != "blob"
            or entry["mode"] not in {"100644", "100755"}
        ):
            raise P541BR2Error(f"frozen source is not a regular Python blob: {source_path}")
        raw = git_blob(repo_root, entry["blob_id"])
        raw_by_path[source_path] = raw
        blob_cache[entry["blob_id"]] = raw
        transitive = one_hop_transitive_evidence(
            source_path,
            raw,
            repo_root,
            FROZEN_SOURCE_COMMIT,
            resolution_cache=resolution_cache,
            blob_cache=blob_cache,
        )
        analysis = analyze_source_bytes(
            source_path,
            raw,
            entry["blob_id"],
            transitive_evidence=transitive,
        )
        records.append(
            {
                "method_id": historical_record["method_id"],
                "source_path": source_path,
                **analysis,
                "historical_p541b_classification": _historical_context(historical_record),
            }
        )

    risk_counts = Counter(
        record["safety_classification"]["risk_level"] for record in records
    )
    disposition_counts = Counter(
        record["safety_classification"]["disposition"] for record in records
    )
    evidence_counts = {
        key: dict(sorted(Counter(record["evidence"][key]["state"] for record in records).items()))
        for key in ALL_EVIDENCE_KEYS
    }
    scan_status_counts = dict(sorted(Counter(record["scan_status"] for record in records).items()))
    direct_finding_count = sum(
        1
        for record in records
        for item in record["evidence"].values()
        for finding in item["findings"]
        if finding["direct_or_transitive"] == "direct"
    )
    transitive_finding_count = sum(
        len(record["evidence"]["transitive_external_state"]["findings"])
        for record in records
    )
    identities = [record["source_identity"] for record in records]
    generator_raw = (repo_root / GENERATOR_PATH).read_bytes()
    artifact = {
        "schema_version": SCHEMA_VERSION,
        "detector_version": DETECTOR_VERSION,
        "scan_status_taxonomy": list(SCAN_STATUS_TAXONOMY),
        "task_id": TASK_ID,
        "generated_at_utc": GENERATED_AT_UTC,
        "implementation_base_oid": BASE_MAIN_COMMIT,
        "frozen_source_commit": FROZEN_SOURCE_COMMIT,
        "generator": {
            "path": GENERATOR_PATH,
            "byte_size": len(generator_raw),
            "sha256": sha256_bytes(generator_raw),
        },
        "supersedes": {
            "task_id": historical["task_id"],
            "schema_version": historical["schema_version"],
            "artifacts": [HISTORICAL_JSON_PATH, HISTORICAL_MARKDOWN_PATH],
            "overwrite_policy": "HISTORICAL_ARTIFACTS_PRESERVED",
            "semantics": "R2 supersedes historical Boolean evidence semantics without deleting historical artifacts",
        },
        "detector_contract": {
            "detector_version": DETECTOR_VERSION,
            "evidence_states": sorted(TRI_STATES),
            "scan_status_taxonomy": list(SCAN_STATUS_TAXONOMY),
            "finding_fields": [
                "line",
                "column",
                "rule_id",
                "resolved_api",
                "resolved_syntax",
                "scope",
                "direct_or_transitive",
                "source_path",
                "imported_module_path",
            ],
            "fail_closed_conditions": [
                "UTF-8 decode failure",
                "AST parse failure",
                "star import",
                "dynamic code or import",
                "dynamic file mode",
            ],
            "valid_main_guard": "exact top-level __name__ == '__main__' comparison, either operand order",
            "main_guard_scope": "mitigates import-time execution only; never suppresses anywhere-effect evidence",
            "alias_awareness": [
                "import aliases",
                "from-import aliases",
                "simple name/attribute aliases",
                "constructed manager/session/path aliases",
            ],
            "low_risk_rule": (
                "scan.complete=true and every risk evidence category is explicitly not_detected"
            ),
            "source_access": "pinned Git blobs only; no working-tree discovery/import/execution",
            "one_hop_policy": "direct repository-local imports only; no recursion beyond one hop",
        },
        "summary": {
            "total_records": len(records),
            "complete_scans": sum(record["scan"]["complete"] is True for record in records),
            "unknown_scans": sum(record["scan"]["complete"] is False for record in records),
            "scan_status_counts": scan_status_counts,
            "risk_level_counts": dict(sorted(risk_counts.items())),
            "disposition_counts": dict(sorted(disposition_counts.items())),
            "evidence_status_counts": evidence_counts,
            "direct_finding_count": direct_finding_count,
            "transitive_finding_count": transitive_finding_count,
        },
        "provenance": {
            "historical_inputs": historical_provenance,
            "source_manifest": {
                "record_count": 580,
                "entry_fields": [
                    "source_path", "source_commit", "blob_id", "byte_size", "sha256",
                ],
                "entries_embedded_at": "method_classification_records[*].source_identity",
                "canonicalization": "UTF-8 compact sorted-key JSON in historical record order",
                "canonical_sha256": sha256_bytes(canonical_bytes(identities)),
                "ordered_entries": identities,
                "verification": "PASS",
            },
            "no_database_access": True,
            "no_database_hashing": True,
            "no_target_module_import_or_execution": True,
        },
        "method_classification_records": records,
        "downstream_contract": {
            "p541c_regeneration_required": True,
            "historical_p541c_counts_or_shortlist_preserved": False,
            "pr_663_mutated": False,
            "consumer_requirement": (
                "A replacement P541C consumer must require complete tri-state evidence and "
                "must not coerce unknown to false."
            ),
        },
        "limitations": [
            "Static detection is conservative and does not prove runtime safety.",
            "Unknown blocks low-risk eligibility and requires targeted review or detector support.",
            "Historical identity/method-family classifications are retained as context, not re-proven.",
            "No database, source import, source execution, replay, or predictive evaluation was performed.",
        ],
        "disclaimer": DISCLAIMER,
    }
    validate_artifact(artifact)
    return artifact


def render_markdown(artifact: dict[str, Any]) -> str:
    summary = artifact["summary"]
    evidence_counts = summary["evidence_status_counts"]
    lines = [
        "# P541B R2 — Fail-Closed Structured Evidence Classification",
        "",
        f"> generated_at_utc: `{artifact['generated_at_utc']}`",
        "",
        "## Scope and Frozen Corpus",
        "",
        f"- Implementation base: `{artifact['implementation_base_oid']}`",
        f"- Frozen source commit: `{artifact['frozen_source_commit']}`",
        "- Ordered corpus: exactly **580** unique historical method IDs and source paths.",
        "- Source bytes were read only with Git plumbing from the frozen commit.",
        "- No source module was imported or executed; no database was opened or hashed.",
        "",
        "## Evidence Schema and Fail-Closed Rules",
        "",
        f"- Schema: `{artifact['schema_version']}`",
        f"- Detector: `{artifact['detector_version']}`",
        "- Every evidence family publishes `state`, `scope`, `detector_id`, and deterministic `findings`.",
        "- Every finding publishes separate `resolved_api` and `resolved_syntax` fields plus `imported_module_path`; exactly one resolved field is populated.",
        "- States are exactly `detected`, `not_detected`, and `unknown`.",
        "- Scan-status taxonomy (ordered): `complete`, `syntax_error`, `unreadable`, `unsupported`.",
        "- Read/decode, AST parse, unsupported-structure, provenance, and ambiguous one-hop failures fail closed.",
        "- Only an exact top-level `__name__ == '__main__'` comparison is a valid guard; it mitigates import-time reachability only.",
        "",
        "## Detector Families",
        "",
        "- Direct and aliased database access, including DatabaseManager/db_manager and supported SQLAlchemy APIs.",
        "- Filesystem reads separated from filesystem writes, deletes, moves, and mutations.",
        "- Requests/urllib/http.client/httpx/aiohttp/socket network I/O and external URLs.",
        "- Direct and aliased subprocess/process-spawning APIs.",
        "- Hardcoded absolute, DB-like, draw/date, and external-service inputs.",
        "- Bounded one-hop project imports with cycle stops and ambiguity routed to `unknown`.",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Frozen source records | {summary['total_records']} |",
        f"| Complete scans | {summary['complete_scans']} |",
        f"| Unknown scans | {summary['unknown_scans']} |",
        f"| Direct findings | {summary['direct_finding_count']} |",
        f"| Transitive findings | {summary['transitive_finding_count']} |",
    ]
    for status, count in summary["scan_status_counts"].items():
        lines.append(f"| Scan `{status}` | {count} |")
    for risk, count in summary["risk_level_counts"].items():
        lines.append(f"| Risk `{risk}` | {count} |")
    lines.extend([
        "",
        "## Tri-State Evidence",
        "",
        "| Evidence | detected | not_detected | unknown |",
        "|---|---:|---:|---:|",
    ])
    for key in ALL_EVIDENCE_KEYS:
        counts = evidence_counts[key]
        lines.append(
            f"| `{key}` | {counts.get('detected', 0)} | "
            f"{counts.get('not_detected', 0)} | {counts.get('unknown', 0)} |"
        )
    lines.extend([
        "",
        "## Superseded Historical Artifacts",
        "",
        f"- `{HISTORICAL_JSON_PATH}`",
        f"- `{HISTORICAL_MARKDOWN_PATH}`",
        "- R2 supersedes their Boolean evidence semantics without overwriting or deleting them.",
        "",
        "## Frozen Provenance",
        "",
        f"- Generator SHA-256: `{artifact['generator']['sha256']}`",
        f"- Historical P541B JSON blob: `{artifact['provenance']['historical_inputs']['p541b_json']['blob_id']}` — verification **PASS**",
        f"- Historical P541B Markdown blob: `{artifact['provenance']['historical_inputs']['p541b_markdown']['blob_id']}` — verification **PASS**",
        f"- Historical P541A JSON blob: `{artifact['provenance']['historical_inputs']['p541a_json']['blob_id']}` — verification **PASS**",
        f"- Historical P541A Markdown blob: `{artifact['provenance']['historical_inputs']['p541a_markdown']['blob_id']}` — verification **PASS**",
        f"- Frozen manifest: 580 Git blobs, canonical SHA-256 `{artifact['provenance']['source_manifest']['canonical_sha256']}` — verification **PASS**",
        "- Source discovery from the current working tree is prohibited.",
        "",
        "## Downstream Requirement",
        "",
        "PR #663 remains **HOLD_DO_NOT_MERGE** and was not changed. A separately authorized replacement P541C task must consume this schema, regenerate all derived counts and shortlist membership, and must never coerce `unknown` to `false`.",
        "",
        "## Limitations",
        "",
    ])
    lines.extend(f"- {item}" for item in artifact["limitations"])
    lines.extend([
        "",
        "**Disclaimer:** This is static classification, not source execution, replay, production, predictive, ROI, or betting validation.",
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    artifact = build_artifact(REPO_ROOT)
    json_path = REPO_ROOT / OUTPUT_JSON
    markdown_path = REPO_ROOT / OUTPUT_MARKDOWN
    json_path.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(render_markdown(artifact), encoding="utf-8")


if __name__ == "__main__":
    main()
