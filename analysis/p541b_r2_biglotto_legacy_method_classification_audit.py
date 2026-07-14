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
import sys
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]

TASK_ID = "P541B_R2_BIG_LOTTO_LEGACY_METHOD_CLASSIFICATION_AUDIT"
SCHEMA_VERSION = "p541b-r2-evidence-v1"
DETECTOR_VERSION = "p541b-r2-detector-v10"
CANONICAL_RUNTIME_IMPLEMENTATION = "CPython"
CANONICAL_RUNTIME_VERSION = "3.9.6"
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
    "save",
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
TABULAR_FILESYSTEM_READ_CALLS = {
    "pandas.read_csv",
    "pandas.read_excel",
    "pandas.read_feather",
    "pandas.read_parquet",
    "pandas.read_pickle",
    "pandas.read_table",
    "polars.read_csv",
    "polars.read_excel",
    "polars.read_parquet",
}
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

CONTROL_FLOW_NODES: tuple[type[ast.AST], ...] = (
    ast.For,
    ast.AsyncFor,
    ast.If,
    ast.Try,
    ast.While,
    ast.With,
    ast.AsyncWith,
)
if hasattr(ast, "Match"):
    CONTROL_FLOW_NODES += (getattr(ast, "Match"),)

DISCLAIMER = (
    "Historical static safety-evidence remediation only. This artifact does not "
    "establish prediction quality, replay readiness, betting edge, ROI, or "
    "production safety."
)


class P541BR2Error(RuntimeError):
    """Raised when pinned provenance or the fail-closed contract is violated."""


class GitUnavailableError(P541BR2Error):
    """Raised when Git or its repository is unavailable; this remains terminal."""


class GitExecutableUnavailableError(GitUnavailableError):
    """Raised when the Git executable cannot be launched."""


class GitRepositoryUnavailableError(GitUnavailableError):
    """Raised when repository metadata or its object store is unavailable."""


class GitBlobReadError(P541BR2Error):
    """Raised for an individual Git blob-read failure in an available repository."""


def canonical_runtime_provenance() -> dict[str, Any]:
    implementation = (
        "CPython" if sys.implementation.name == "cpython" else sys.implementation.name
    )
    return {
        "implementation": implementation,
        "version": ".".join(str(part) for part in sys.version_info[:3]),
        "requirement": (
            f"{CANONICAL_RUNTIME_IMPLEMENTATION}=={CANONICAL_RUNTIME_VERSION}"
        ),
        "verification": "PASS",
    }


def require_canonical_runtime() -> dict[str, Any]:
    provenance = canonical_runtime_provenance()
    if (
        provenance["implementation"] != CANONICAL_RUNTIME_IMPLEMENTATION
        or provenance["version"] != CANONICAL_RUNTIME_VERSION
    ):
        raise P541BR2Error(
            "canonical generation runtime mismatch: "
            f"required {CANONICAL_RUNTIME_IMPLEMENTATION} "
            f"{CANONICAL_RUNTIME_VERSION}"
        )
    return provenance


FAILURE_REASON_CODES = frozenset(
    {
        "ast_parse_failed",
        "category_detector_failed",
        "detector_failed",
        "git_blob_read_failed",
        "import_resolution_incomplete",
        "imported_blob_invalid",
        "imported_scan_incomplete",
        "transitive_detector_failed",
        "unsupported_static_structure",
        "utf8_decode_failed",
    }
)

TRANSITIVE_FAILURE_REASON_CODES = frozenset(
    {
        "category_detector_failed",
        "detector_failed",
        "git_blob_read_failed",
        "import_resolution_incomplete",
        "imported_blob_invalid",
        "imported_scan_incomplete",
        "transitive_detector_failed",
    }
)

APPROVED_UNKNOWN_REASON_LITERALS = frozenset(
    {
        "ambiguous DB-like API could not be resolved",
        "one-hop resolver not supplied",
    }
)


def _failure_reason(code: str, *, line: int | None = None, byte: int | None = None) -> str:
    """Return a bounded deterministic reason containing no exception or host-path text."""
    if code not in FAILURE_REASON_CODES:
        raise P541BR2Error(f"unknown failure reason code: {code}")
    fields = [code]
    if line is not None:
        fields.append(f"line={max(0, int(line))}")
    if byte is not None:
        fields.append(f"byte={max(0, int(byte))}")
    return ":".join(fields)


def _valid_bounded_failure_reason(reason: Any) -> bool:
    """Accept only reasons emitted by the bounded deterministic reason contract."""
    if not isinstance(reason, str) or not reason or len(reason) > 256:
        return False
    if HARD_CODED_PATH_RE.search(reason):
        return False
    if reason in APPROVED_UNKNOWN_REASON_LITERALS:
        return True
    parts = reason.split("; ")
    if len(parts) > 1:
        return (
            parts == sorted(set(parts))
            and all(part in TRANSITIVE_FAILURE_REASON_CODES for part in parts)
        )
    if reason in FAILURE_REASON_CODES - {"utf8_decode_failed"}:
        return True
    return bool(
        re.fullmatch(r"ast_parse_failed:line=(?:0|[1-9][0-9]*)", reason)
        or re.fullmatch(r"utf8_decode_failed:byte=(?:0|[1-9][0-9]*)", reason)
    )


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


def _git_repository_available(repo_root: Path) -> bool:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=repo_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except OSError:
        return False
    return completed.returncode == 0


def _git_object_store_available(repo_root: Path) -> bool:
    try:
        completed = subprocess.run(
            ["git", "cat-file", "-e", "HEAD^{commit}"],
            cwd=repo_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except OSError:
        return False
    return completed.returncode == 0


def run_git(repo_root: Path, arguments: Sequence[str], *, stdin: bytes | None = None) -> bytes:
    try:
        completed = subprocess.run(
            ["git", *arguments],
            cwd=repo_root,
            input=stdin,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except OSError as exc:
        raise GitExecutableUnavailableError("Git executable is unavailable") from exc
    if completed.returncode:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        repository_failure_markers = (
            "not a git repository",
            "cannot change to",
            "cannot chdir",
            "detected dubious ownership",
            "must be run in a work tree",
            "permission denied",
            "unable to read current working directory",
        )
        if (
            any(marker in detail.lower() for marker in repository_failure_markers)
            or not _git_repository_available(repo_root)
            or not _git_object_store_available(repo_root)
        ):
            raise GitRepositoryUnavailableError("Git repository is unavailable")
        raise P541BR2Error(f"git {' '.join(arguments[:2])} failed")
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
    try:
        return run_git(repo_root, ["cat-file", "blob", blob_id])
    except GitUnavailableError:
        raise
    except P541BR2Error as exc:
        raise GitBlobReadError("Git blob is unavailable") from exc


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


def _function_header_expressions(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    *,
    annotations_eager: bool,
) -> list[ast.AST]:
    """Return expressions evaluated when one function definition executes."""
    expressions: list[ast.AST] = [
        *node.decorator_list,
        *node.args.defaults,
        *(item for item in node.args.kw_defaults if item is not None),
    ]
    if not annotations_eager:
        return expressions
    arguments = [
        *getattr(node.args, "posonlyargs", ()),
        *node.args.args,
        *node.args.kwonlyargs,
    ]
    if node.args.vararg is not None:
        arguments.append(node.args.vararg)
    if node.args.kwarg is not None:
        arguments.append(node.args.kwarg)
    expressions.extend(
        argument.annotation
        for argument in arguments
        if argument.annotation is not None
    )
    if node.returns is not None:
        expressions.append(node.returns)
    return expressions


def _module_annotations_are_eager(tree: ast.Module) -> bool:
    return not any(
        isinstance(statement, ast.ImportFrom)
        and statement.module == "__future__"
        and any(alias.name == "annotations" for alias in statement.names)
        for statement in tree.body
    )


class _RuntimeCallVisitor(ast.NodeVisitor):
    """Collect calls evaluated while a module is imported.

    Function/lambda bodies are deferred, while decorators and default values
    are evaluated at definition time. Class bodies execute at import time.
    """

    def __init__(self, *, annotations_eager: bool = True) -> None:
        self.calls: list[ast.Call] = []
        self.annotations_eager = annotations_eager

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        self.calls.append(node)
        self.generic_visit(node)

    def _visit_function_header(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        for item in _function_header_expressions(
            node, annotations_eager=self.annotations_eager
        ):
            self.visit(item)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
        self._visit_function_header(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: N802
        self._visit_function_header(node)

    def visit_Lambda(self, node: ast.Lambda) -> None:  # noqa: N802
        for item in [*node.args.defaults, *node.args.kw_defaults]:
            if item is not None:
                self.visit(item)


def import_time_calls(tree: ast.Module) -> list[ast.Call]:
    visitor = _RuntimeCallVisitor(
        annotations_eager=_module_annotations_are_eager(tree)
    )
    for statement in tree.body:
        if isinstance(statement, ast.If) and is_valid_main_guard_test(statement.test):
            for alternate in statement.orelse:
                visitor.visit(alternate)
            continue
        visitor.visit(statement)
    return visitor.calls


def guarded_calls(tree: ast.Module) -> list[ast.Call]:
    visitor = _RuntimeCallVisitor(
        annotations_eager=_module_annotations_are_eager(tree)
    )
    for statement in tree.body:
        if isinstance(statement, ast.If) and is_valid_main_guard_test(statement.test):
            for guarded_statement in statement.body:
                visitor.visit(guarded_statement)
    return visitor.calls


def _call_mode(call: ast.Call, resolved: str) -> str | None:
    # A ``**kwargs`` expansion can supply or override the mode in ways that
    # static inspection cannot resolve, so it must fail closed.
    if any(keyword.arg is None for keyword in call.keywords):
        return None

    normalized = resolved.lower()
    module_open_apis = {
        "open",
        "builtins.open",
        "bz2.open",
        "codecs.open",
        "gzip.open",
        "io.open",
        "lzma.open",
        "tarfile.open",
    }
    if normalized in module_open_apis or normalized == "pathlib.path.open":
        positional_mode_index = 1
    else:
        # Bound ``Path.open`` and other instance ``.open`` methods accept mode
        # as their first positional argument.
        positional_mode_index = 0
    value: ast.AST | None = (
        call.args[positional_mode_index]
        if len(call.args) > positional_mode_index
        else None
    )
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
        mode = _call_mode(call, resolved)
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
    if normalized in TABULAR_FILESYSTEM_READ_CALLS:
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
        ),
    }
    if reason:
        result["reason"] = reason
    return result


def unknown_analysis(
    source_path: str,
    raw: bytes | None,
    blob_id: str,
    reason: str,
    scan_status: str,
    *,
    reason_code: str,
    preserved_evidence: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if scan_status not in SCAN_STATUSES or scan_status == "complete":
        raise P541BR2Error(f"invalid incomplete scan status: {scan_status}")
    if (
        reason_code not in FAILURE_REASON_CODES
        or not _valid_bounded_failure_reason(reason)
        or "; " in reason
        or reason.split(":", 1)[0] != reason_code
    ):
        raise P541BR2Error(f"invalid bounded failure reason: {reason_code}")
    evidence = {
        key: _evidence("unknown", scope="unknown", reason=reason)
        for key in ALL_EVIDENCE_KEYS
    }
    for key, item in (preserved_evidence or {}).items():
        if key in evidence and item.get("state") == "detected":
            evidence[key] = _evidence(
                "detected",
                scope=str(item.get("scope", "whole_file")),
                findings=item.get("findings", ()),
            )
        elif key in evidence and item.get("state") == "unknown" and item.get("findings"):
            evidence[key] = _evidence(
                "unknown",
                scope=str(item.get("scope", "whole_file")),
                findings=item["findings"],
                reason=str(item.get("reason") or reason),
            )
    read_status = "succeeded" if raw is not None else "failed"
    if raw is None:
        decode_status, parse_status = "not_attempted", "not_attempted"
    elif scan_status == "unreadable":
        decode_status, parse_status = "failed", "not_attempted"
    elif scan_status == "syntax_error":
        decode_status, parse_status = "succeeded", "failed"
    else:
        decode_status, parse_status = "succeeded", "succeeded"
    return {
        "schema_version": SCHEMA_VERSION,
        "detector_version": DETECTOR_VERSION,
        "source_identity": {
            "source_path": source_path,
            "source_commit": FROZEN_SOURCE_COMMIT,
            "blob_id": blob_id,
            "byte_size": len(raw) if raw is not None else None,
            "sha256": sha256_bytes(raw) if raw is not None else None,
            "git_blob_read_status": read_status,
            "utf8_decoding_status": decode_status,
        },
        "scan_status": scan_status,
        "scan": {
            "status": scan_status,
            "complete": False,
            "read_status": read_status,
            "decode_status": decode_status,
            "parse_status": parse_status,
            "error": {"type": scan_status, "code": reason_code, "message": reason},
        },
        "evidence": evidence,
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
        reason = _failure_reason("utf8_decode_failed", byte=exc.start)
        return unknown_analysis(
            source_path,
            raw,
            blob_id,
            reason,
            "unreadable",
            reason_code="utf8_decode_failed",
        )
    try:
        tree = ast.parse(content, filename=source_path)
    except SyntaxError as exc:
        reason = _failure_reason("ast_parse_failed", line=exc.lineno)
        return unknown_analysis(
            source_path,
            raw,
            blob_id,
            reason,
            "syntax_error",
            reason_code="ast_parse_failed",
        )

    try:
        aliases = collect_aliases(tree)
        runtime_call_ids = {id(call) for call in import_time_calls(tree)}
        guarded_call_ids = {id(call) for call in guarded_calls(tree)}
    except P541BR2Error:
        raise
    except Exception:
        reason = _failure_reason("detector_failed")
        return unknown_analysis(
            source_path,
            raw,
            blob_id,
            reason,
            "unsupported",
            reason_code="detector_failed",
        )
    findings: dict[str, list[dict[str, Any]]] = {
        key: [] for key in (*EFFECT_KEYS, "filesystem_read")
    }
    unsupported: list[str] = []
    category_detector_failed = False
    ambiguous_database: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and any(alias.name == "*" for alias in node.names):
            unsupported.append(f"star import at line {getattr(node, 'lineno', '?')}")
        if not isinstance(node, ast.Call):
            continue
        resolved = _dotted_name(node.func, aliases) or "<unresolved>"
        if resolved == "<unresolved>":
            unsupported.append(f"unresolved call target at line {getattr(node, 'lineno', 0)}")
        try:
            categories, call_unsupported = classify_call(node, resolved)
        except P541BR2Error:
            raise
        except Exception:
            category_detector_failed = True
            continue
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
        try:
            text_findings = _literal_findings(tree, pattern, source_path, key)
        except P541BR2Error:
            raise
        except Exception:
            category_detector_failed = True
            evidence[key] = _evidence(
                "unknown",
                scope="whole_file",
                reason=_failure_reason("category_detector_failed"),
            )
        else:
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

    if unsupported or category_detector_failed:
        reason_code = (
            "category_detector_failed"
            if category_detector_failed
            else "unsupported_static_structure"
        )
        reason = _failure_reason(reason_code)
        return unknown_analysis(
            source_path,
            raw,
            blob_id,
            reason,
            "unsupported",
            reason_code=reason_code,
            preserved_evidence=evidence,
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
            "git_blob_read_status": "succeeded",
            "utf8_decoding_status": "succeeded",
        },
        "scan_status": "complete",
        "scan": {
            "status": "complete",
            "complete": True,
            "read_status": "succeeded",
            "decode_status": "succeeded",
            "parse_status": "succeeded",
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


def _normalized_static_repo_path(value: PurePosixPath) -> str | None:
    normalized = PurePosixPath(posixpath.normpath(value.as_posix()))
    if normalized.is_absolute() or ".." in normalized.parts:
        return None
    return "" if normalized.as_posix() == "." else normalized.as_posix()


def _static_repo_path_value(
    node: ast.AST,
    source_path: str,
    aliases: dict[str, str],
    variables: dict[str, PurePosixPath],
) -> PurePosixPath | None:
    if isinstance(node, ast.Name):
        if node.id == "__file__":
            return PurePosixPath(source_path)
        return variables.get(node.id)
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        value = PurePosixPath(node.value)
        return value if _normalized_static_repo_path(value) is not None else None
    if isinstance(node, ast.Attribute) and node.attr == "parent":
        base = _static_repo_path_value(node.value, source_path, aliases, variables)
        return base.parent if base is not None else None
    if (
        isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Attribute)
        and node.value.attr == "parents"
    ):
        base = _static_repo_path_value(
            node.value.value, source_path, aliases, variables
        )
        index = node.slice
        if (
            base is not None
            and isinstance(index, ast.Constant)
            and isinstance(index.value, int)
            and 0 <= index.value < len(base.parts)
        ):
            for _ in range(index.value + 1):
                base = base.parent
            return base
        return None
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        left = _static_repo_path_value(node.left, source_path, aliases, variables)
        right = _static_repo_path_value(node.right, source_path, aliases, variables)
        if left is not None and right is not None and not right.is_absolute():
            return left / right
        return None
    if not isinstance(node, ast.Call):
        return None
    resolved = (_dotted_name(node.func, aliases) or "").replace("()", "")
    if resolved in {"str", "os.fspath"} and len(node.args) == 1:
        return _static_repo_path_value(node.args[0], source_path, aliases, variables)
    if resolved in {"Path", "pathlib.Path"} and len(node.args) <= 1:
        argument = node.args[0] if node.args else ast.Constant(value=".")
        return _static_repo_path_value(argument, source_path, aliases, variables)
    if resolved in {
        "os.path.abspath",
        "os.path.normpath",
        "os.path.realpath",
    } and len(node.args) == 1:
        return _static_repo_path_value(node.args[0], source_path, aliases, variables)
    if resolved == "os.path.dirname" and len(node.args) == 1:
        value = _static_repo_path_value(node.args[0], source_path, aliases, variables)
        return value.parent if value is not None else None
    if resolved == "os.path.join" and node.args:
        value = _static_repo_path_value(node.args[0], source_path, aliases, variables)
        if value is None:
            return None
        for argument in node.args[1:]:
            component = _static_repo_path_value(
                argument, source_path, aliases, variables
            )
            if component is None or component.is_absolute():
                return None
            value /= component
        return value
    if isinstance(node.func, ast.Attribute) and node.func.attr in {
        "absolute",
        "resolve",
    }:
        return _static_repo_path_value(
            node.func.value, source_path, aliases, variables
        )
    return None


def _static_path_variables(
    tree: ast.Module, source_path: str, aliases: dict[str, str]
) -> dict[str, PurePosixPath]:
    parents = _ast_parent_map(tree)
    definitions: dict[str, list[tuple[ast.AST, ast.AST | None]]] = {}
    binding_counts: Counter[str] = Counter(
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del))
    )
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            binding_counts.update(
                alias.asname or alias.name.split(".", 1)[0]
                for alias in node.names
            )
        elif isinstance(node, ast.ImportFrom):
            binding_counts.update(
                alias.asname or alias.name
                for alias in node.names
                if alias.name != "*"
            )
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            binding_counts[node.name] += 1
        elif isinstance(node, ast.arg):
            binding_counts[node.arg] += 1
        elif isinstance(node, ast.ExceptHandler) and isinstance(node.name, str):
            binding_counts[node.name] += 1
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            binding_counts.update(node.names)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            value, targets = node.value, node.targets
        elif isinstance(node, ast.AnnAssign):
            value, targets = node.value, [node.target]
        elif isinstance(node, ast.AugAssign):
            value, targets = None, [node.target]
        elif isinstance(node, ast.NamedExpr):
            value, targets = None, [node.target]
        else:
            continue
        for target in targets:
            target_names = [target.id] if isinstance(target, ast.Name) else []
            for name in target_names:
                definitions.setdefault(name, []).append((node, value))

    eligible: dict[str, ast.AST] = {}
    for name, items in definitions.items():
        if len(items) != 1:
            continue
        node, value = items[0]
        if (
            value is not None
            and binding_counts[name] == 1
            and parents.get(id(node)) is tree
            and not any(isinstance(item, ast.IfExp) for item in ast.walk(value))
        ):
            eligible[name] = value

    variables: dict[str, PurePosixPath] = {}
    for _ in range(8):
        changed = False
        for name, value in eligible.items():
            resolved = _static_repo_path_value(
                value, source_path, aliases, variables
            )
            if resolved is None or _normalized_static_repo_path(resolved) is None:
                continue
            if variables.get(name) != resolved:
                variables[name] = resolved
                changed = True
        if not changed:
            break
    return variables


def _node_position(node: ast.AST) -> tuple[int, int]:
    return (getattr(node, "lineno", 0), getattr(node, "col_offset", 0))


def _bounded_sys_path_updates(
    tree: ast.Module, source_path: str
) -> tuple[
    tuple[tuple[tuple[int, int], str], ...],
    tuple[tuple[int, int], ...],
]:
    aliases = collect_aliases(tree)
    variables = _static_path_variables(tree, source_path, aliases)
    parents = _ast_parent_map(tree)
    reached, unknown, known, module_incomplete = (
        _invoked_local_definition_reachability(tree)
    )
    execution_states, execution_incomplete = _definition_execution_reachability(
        tree, reached, unknown
    )
    execution_incomplete = execution_incomplete or module_incomplete
    roots: set[tuple[tuple[int, int], str]] = set()
    incomplete_positions: set[tuple[int, int]] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        resolved = (_dotted_name(node.func, aliases) or "").replace("()", "")
        if resolved not in {
            "sys.path.append",
            "sys.path.extend",
            "sys.path.insert",
        }:
            continue
        context = _import_lexical_context(node, parents)
        lexical_state = _lexical_reachability(
            context,
            reached,
            unknown,
            known,
            execution_states=execution_states,
            execution_incomplete=execution_incomplete,
        )
        if lexical_state == "unreachable":
            continue
        if lexical_state != "reached" or context["definition_target"] is not None:
            incomplete_positions.add(_node_position(node))
            continue
        arguments: list[ast.AST] = []
        if resolved == "sys.path.insert" and len(node.args) >= 2:
            arguments = [node.args[1]]
        elif resolved == "sys.path.append" and node.args:
            arguments = [node.args[0]]
        elif resolved == "sys.path.extend" and node.args:
            if isinstance(node.args[0], (ast.List, ast.Tuple)):
                arguments = list(node.args[0].elts)
        if not arguments:
            incomplete_positions.add(_node_position(node))
            continue
        for argument in arguments:
            value = _static_repo_path_value(
                argument, source_path, aliases, variables
            )
            normalized = (
                _normalized_static_repo_path(value) if value is not None else None
            )
            if normalized is not None:
                roots.add((_node_position(node), normalized))
            else:
                incomplete_positions.add(_node_position(node))
    return tuple(sorted(roots)), tuple(sorted(incomplete_positions))


def _ast_parent_map(tree: ast.AST) -> dict[int, ast.AST]:
    return {
        id(child): parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }


def _import_lexical_context(
    statement: ast.AST,
    parents: dict[int, ast.AST],
) -> dict[str, Any]:
    function_owner: ast.FunctionDef | ast.AsyncFunctionDef | None = None
    function_depth = 0
    class_owner: ast.ClassDef | None = None
    conditional = False
    current: ast.AST | None = statement
    while current is not None and id(current) in parents:
        current = parents[id(current)]
        if isinstance(current, CONTROL_FLOW_NODES):
            conditional = True
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
            function_depth += 1
            if function_owner is None:
                function_owner = current
                continue
        if class_owner is None and isinstance(current, ast.ClassDef):
            class_owner = current
    definition_target = (
        (class_owner.name if class_owner is not None else None, function_owner.name)
        if function_owner is not None
        else None
    )
    return {
        "lexical_scope": (
            "method"
            if function_owner is not None and class_owner is not None
            else "function"
            if function_owner is not None
            else "class_body"
            if class_owner is not None
            else "module"
        ),
        "definition_target": definition_target,
        "conditional_context": conditional,
        "nested_definition": function_depth > 1,
        "line": getattr(statement, "lineno", 0),
        "column": getattr(statement, "col_offset", 0),
    }


def _lexical_reachability(
    context: dict[str, Any],
    reached_definitions: set[tuple[str | None, str]],
    unknown_definitions: set[tuple[str | None, str]],
    known_definitions: set[tuple[str | None, str]],
    *,
    execution_states: dict[tuple[int, int], str] | None = None,
    execution_incomplete: bool = False,
) -> str:
    definition_target = context.get("definition_target")
    if definition_target is None:
        return "unknown" if context["conditional_context"] else "reached"
    if execution_states is not None:
        position = (int(context.get("line", 0)), int(context.get("column", 0)))
        execution_state = execution_states.get(position)
        if execution_state is not None:
            return (
                "unknown"
                if context.get("nested_definition")
                or execution_state == "unknown"
                or context["conditional_context"]
                else "reached"
            )
        if context.get("nested_definition"):
            return "unknown" if execution_incomplete else "unreachable"
    if definition_target in reached_definitions:
        return "unknown" if context["conditional_context"] else "reached"
    if definition_target in unknown_definitions:
        return "unknown"
    if definition_target in known_definitions:
        return "unreachable"
    return "unknown"


def _import_bindings(tree: ast.Module, source_path: str) -> list[dict[str, Any]]:
    bindings: list[dict[str, Any]] = []
    root_updates, incomplete_updates = _bounded_sys_path_updates(tree, source_path)
    parents = _ast_parent_map(tree)
    statements = sorted(
        (
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
        ),
        key=lambda node: (
            getattr(node, "lineno", -1),
            getattr(node, "col_offset", -1),
            ast.dump(node, include_attributes=False),
        ),
    )
    for statement in statements:
        lexical_context = _import_lexical_context(statement, parents)
        statement_position = _node_position(statement)
        search_roots = tuple(
            sorted(
                {
                    root
                    for update_position, root in root_updates
                    if update_position < statement_position
                }
            )
        )
        sys_path_resolution_incomplete = any(
            update_position < statement_position
            for update_position in incomplete_updates
        )
        if isinstance(statement, ast.Import):
            for alias in statement.names:
                bindings.append(
                    {
                        "source_path": source_path,
                        "search_roots": search_roots,
                        "sys_path_resolution_incomplete": sys_path_resolution_incomplete,
                        "module": alias.name,
                        "symbol": None,
                        "local_name": alias.asname or alias.name.split(".")[0],
                        "line": statement.lineno,
                        "column": statement.col_offset,
                        "relative": False,
                        **lexical_context,
                    }
                )
        elif isinstance(statement, ast.ImportFrom):
            module = _absolute_import_module(source_path, statement.module, statement.level)
            for alias in statement.names:
                bindings.append(
                    {
                        "source_path": source_path,
                        "search_roots": search_roots,
                        "sys_path_resolution_incomplete": sys_path_resolution_incomplete,
                        "module": module,
                        "symbol": alias.name,
                        "local_name": alias.asname or alias.name,
                        "line": statement.lineno,
                        "column": statement.col_offset,
                        "relative": statement.level > 0,
                        **lexical_context,
                    }
                )
    return sorted(
        bindings,
        key=lambda item: (
            item["line"],
            item["column"],
            item["module"] or "",
            item["symbol"] or "",
            item["local_name"],
        ),
    )


def _module_candidates(module: str, symbol: str | None) -> list[str]:
    base = module.replace(".", "/")
    candidates = [f"{base}.py", f"{base}/__init__.py"]
    if symbol and symbol != "*":
        candidates.extend([f"{base}/{symbol}.py", f"{base}/{symbol}/__init__.py"])
    return list(dict.fromkeys(candidates))


def _binding_module_candidates(binding: dict[str, Any]) -> list[str]:
    module = binding["module"]
    if not module:
        return []
    candidates = _module_candidates(module, binding["symbol"])
    if not binding["relative"]:
        base_candidates = _module_candidates(module, binding["symbol"])
        for root in binding.get("search_roots", ()):
            candidates.extend(
                f"{root}/{candidate}" if root else candidate
                for candidate in base_candidates
            )
        parent_parts = PurePosixPath(binding["source_path"]).parent.parts
        for length in range(len(parent_parts), 0, -1):
            prefix = "/".join(parent_parts[:length])
            candidates.extend(f"{prefix}/{candidate}" for candidate in base_candidates)
    return list(dict.fromkeys(candidates))


def _resolve_project_binding(
    repo_root: Path,
    commit: str,
    binding: dict[str, Any],
    cache: dict[tuple[Any, ...], tuple[str, str | None]],
) -> tuple[str, str | None]:
    key = (
        binding["source_path"],
        binding["module"],
        binding["symbol"],
        binding["relative"],
        tuple(binding.get("search_roots", ())),
        bool(binding.get("sys_path_resolution_incomplete")),
        commit,
    )
    if key in cache:
        return cache[key]
    module = binding["module"]
    if not module:
        result = ("unknown", "relative import has no resolvable module")
        cache[key] = result
        return result
    candidates = _binding_module_candidates(binding)
    search_roots = [root for root in binding.get("search_roots", ()) if root]
    entries = git_tree_entries(
        repo_root, commit, list(dict.fromkeys([*candidates, *search_roots]))
    )
    resolved = [path for path in candidates if path in entries]
    invalid_search_roots = [
        root
        for root in search_roots
        if root not in entries
        or entries[root]["type"] != "tree"
        or entries[root]["mode"] != "040000"
    ]
    if binding.get("sys_path_resolution_incomplete"):
        result = ("unknown", "repository-relative sys.path resolution is incomplete")
    elif len(resolved) > 1:
        result = ("unknown", f"ambiguous project import resolves to {resolved}")
    elif len(resolved) == 1:
        result = (resolved[0], None)
    elif binding["relative"]:
        result = ("unknown", f"relative project import not found: {module}")
    elif invalid_search_roots:
        result = ("unknown", "repository-relative sys.path root is absent")
    else:
        # Absent absolute modules are external dependencies, not project imports.
        result = ("external", None)
    cache[key] = result
    return result


def _node_references_binding(
    node: ast.AST,
    binding: dict[str, Any],
    aliases: dict[str, str],
) -> bool:
    local_name = binding["local_name"]
    module = binding["module"] or ""
    symbol = binding["symbol"]
    canonical = f"{module}.{symbol}" if symbol and symbol != "*" else module
    raw = (_dotted_name(node, {}) or "").replace("()", "")
    resolved = (_dotted_name(node, aliases) or "").replace("()", "")
    return (
        raw == local_name
        or raw.startswith(f"{local_name}.")
        or resolved == canonical
        or (canonical and resolved.startswith(f"{canonical}."))
    )


def _promote_imported_module_load_findings(
    imported: dict[str, Any],
    source_path: str,
    imported_path: str,
    import_line: int,
) -> tuple[list[dict[str, Any]], bool]:
    promoted: list[dict[str, Any]] = []
    incomplete = False
    for family in EFFECT_KEYS:
        evidence = imported["evidence"][family]
        if evidence["state"] == "unknown":
            incomplete = True
        for direct in evidence["findings"]:
            if direct["scope"] != "module_load":
                continue
            promoted.append(
                {
                    **direct,
                    "rule_id": f"transitive.{family}.module_load",
                    "scope": "transitive",
                    "direct_or_transitive": "transitive",
                    "source_path": source_path,
                    "imported_module_path": imported_path,
                    "import_line": import_line,
                }
            )
    return promoted, incomplete


def _call_targets_for_binding(
    call_name: str,
    binding: dict[str, Any],
    function_names: set[str],
    class_names: set[str],
) -> tuple[set[tuple[str | None, str]], bool]:
    targets: set[tuple[str | None, str]] = set()
    incomplete = False
    unresolved_match = False
    symbol = binding["symbol"]
    module = binding["module"] or ""
    prefixes = [binding["local_name"]]
    canonical = f"{module}.{symbol}" if symbol and symbol != "*" else module
    if canonical:
        prefixes.append(canonical)
    if not symbol and module:
        prefixes.append(module)
    for prefix in sorted(set(prefixes), key=len, reverse=True):
        if call_name == prefix:
            definition_name = symbol if symbol and symbol != "*" else prefix.rsplit(".", 1)[-1]
            if definition_name in function_names:
                targets.add((None, definition_name))
            elif definition_name in class_names:
                targets.add((definition_name, "__init__"))
            else:
                unresolved_match = True
            continue
        if not call_name.startswith(f"{prefix}.") and not call_name.startswith(
            f"{prefix}()."
        ):
            continue
        suffix = call_name[len(prefix):].lstrip(".")
        if suffix.startswith("()."):
            suffix = suffix[3:]
            if symbol in class_names:
                targets.add((symbol, suffix.split(".", 1)[0]))
            else:
                unresolved_match = True
            continue
        if "()." in suffix:
            class_name, method_name = suffix.split("().", 1)
            class_name = class_name.rsplit(".", 1)[-1]
            if class_name in class_names:
                targets.add((class_name, method_name.split(".", 1)[0]))
            else:
                unresolved_match = True
            continue
        first, _, remainder = suffix.partition(".")
        if first in function_names:
            targets.add((None, first))
            incomplete = incomplete or bool(remainder)
        elif first in class_names:
            targets.add((first, remainder.split(".", 1)[0] if remainder else "__init__"))
        else:
            unresolved_match = True
    return targets, incomplete or (unresolved_match and not targets)


def _has_ambiguous_binding_dispatch(
    importing_tree: ast.Module,
    binding: dict[str, Any],
    imported_tree: ast.Module,
) -> bool:
    function_names = {
        node.name
        for node in imported_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    class_names = {
        node.name for node in imported_tree.body if isinstance(node, ast.ClassDef)
    }
    aliases = collect_aliases(importing_tree)
    parents = _ast_parent_map(importing_tree)
    assignments: dict[str, list[dict[str, Any]]] = {}
    for node in ast.walk(importing_tree):
        if isinstance(node, ast.Assign):
            value, targets = node.value, node.targets
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            value, targets = node.value, [node.target]
        else:
            continue
        for target in targets:
            if isinstance(target, ast.Name):
                assignments.setdefault(target.id, []).append(
                    {
                        "value": value,
                        "conditional": (
                            _control_flow_between(node, None, parents)
                            or any(
                                isinstance(item, ast.IfExp)
                                for item in ast.walk(value)
                            )
                        ),
                        "signature": ast.dump(value, include_attributes=False),
                    }
                )

    binding_names = {binding["local_name"]}
    for node in ast.walk(importing_tree):
        if _node_references_binding(node, binding, aliases) and isinstance(
            node, ast.Name
        ):
            binding_names.add(node.id)

    tainted = set(binding_names)
    changed = True
    while changed:
        changed = False
        for target, values in assignments.items():
            if target in tainted:
                continue
            if any(
                any(
                    isinstance(item, ast.Name) and item.id in tainted
                    for item in ast.walk(value["value"])
                )
                or any(
                    _node_references_binding(item, binding, aliases)
                    for item in ast.walk(value["value"])
                )
                for value in values
            ):
                tainted.add(target)
                changed = True

    def references_tainted(node: ast.AST | None) -> bool:
        if node is None:
            return False
        return any(
            (isinstance(child, ast.Name) and child.id in tainted)
            or _node_references_binding(child, binding, aliases)
            for child in ast.walk(node)
        )

    for node in ast.walk(importing_tree):
        if isinstance(node, (ast.Return, ast.Yield, ast.YieldFrom)):
            if references_tainted(node.value):
                if isinstance(node, ast.Return) and isinstance(node.value, ast.Call):
                    returned_targets: set[tuple[str | None, str]] = set()
                    returned_incomplete = False
                    for call_name in {
                        _dotted_name(node.value.func, {}) or "",
                        _dotted_name(node.value.func, aliases) or "",
                    }:
                        found, unresolved = _call_targets_for_binding(
                            call_name, binding, function_names, class_names
                        )
                        returned_targets.update(found)
                        returned_incomplete = returned_incomplete or unresolved
                    if (
                        returned_targets
                        and not returned_incomplete
                        and all(
                            class_name is None
                            for class_name, _definition_name in returned_targets
                        )
                    ):
                        continue
                return True
        elif isinstance(node, ast.Lambda) and references_tainted(node.body):
            return True
        elif isinstance(node, ast.Call):
            if any(references_tainted(argument) for argument in node.args) or any(
                references_tainted(keyword.value) for keyword in node.keywords
            ):
                return True
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            value = getattr(node, "value", None)
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if references_tainted(value) and any(
                not isinstance(target, ast.Name) for target in targets
            ):
                return True
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            target_names = [
                child
                for child in ast.walk(node.target)
                if isinstance(child, ast.Name)
            ]
            if any(child.id in tainted for child in target_names) or (
                target_names and references_tainted(node.iter)
            ):
                return True
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            if any(
                item.optional_vars is not None
                and (
                    references_tainted(item.context_expr)
                    or any(
                        isinstance(child, ast.Name) and child.id in tainted
                        for child in ast.walk(item.optional_vars)
                    )
                )
                for item in node.items
            ):
                return True
        elif isinstance(node, ast.comprehension):
            if references_tainted(node.iter) and any(
                isinstance(child, ast.Name) for child in ast.walk(node.target)
            ):
                return True
        elif isinstance(node, ast.NamedExpr):
            if references_tainted(node.value):
                return True
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name in tainted and node.lineno != binding["line"]:
                return True
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                local_name = alias.asname or (
                    alias.name.split(".", 1)[0]
                    if isinstance(node, ast.Import)
                    else alias.name
                )
                if local_name in tainted and node.lineno != binding["line"]:
                    return True

    called_names = {
        item.id
        for call in ast.walk(importing_tree)
        if isinstance(call, ast.Call)
        for item in ast.walk(call.func)
        if isinstance(item, ast.Name)
    }
    for target in sorted(tainted & called_names):
        values = assignments.get(target, [])
        if not values:
            continue
        derived: list[bool] = []
        direct: list[bool] = []
        for item in values:
            value = item["value"]
            value_names = {
                child.id
                for child in ast.walk(value)
                if isinstance(child, ast.Name)
            }
            references = bool(value_names & tainted) or any(
                _node_references_binding(child, binding, aliases)
                for child in ast.walk(value)
            )
            derived.append(references)
            direct_value = value.func if isinstance(value, ast.Call) else value
            direct.append(
                isinstance(direct_value, (ast.Name, ast.Attribute))
                and (
                    any(
                        isinstance(child, ast.Name) and child.id in tainted
                        for child in ast.walk(direct_value)
                    )
                    or _node_references_binding(direct_value, binding, aliases)
                )
            )
        if (
            len(values) > 1
            or any(item["conditional"] for item in values)
            or any(not item for item in derived)
            or any(not item for item in direct)
        ):
            return True
    return False


def _invoked_definition_targets(
    importing_tree: ast.Module,
    binding: dict[str, Any],
    imported_tree: ast.Module,
) -> tuple[set[tuple[str | None, str]], bool]:
    functions = {
        node.name
        for node in imported_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    classes = {
        node.name: node for node in imported_tree.body if isinstance(node, ast.ClassDef)
    }
    aliases = collect_aliases(importing_tree)
    targets: set[tuple[str | None, str]] = set()
    incomplete = _has_ambiguous_binding_dispatch(
        importing_tree, binding, imported_tree
    )
    for node in ast.walk(importing_tree):
        if not isinstance(node, ast.Call):
            continue
        call_targets: set[tuple[str | None, str]] = set()
        references_binding = any(
            _node_references_binding(child, binding, aliases)
            for child in ast.walk(node.func)
        )
        for call_name in {
            _dotted_name(node.func, {}) or "",
            _dotted_name(node.func, aliases) or "",
        }:
            found, unresolved = _call_targets_for_binding(
                call_name, binding, functions, set(classes)
            )
            call_targets.update(found)
            incomplete = incomplete or unresolved
        targets.update(call_targets)
        if references_binding and not call_targets:
            incomplete = True

    imported_class_names = set(classes)
    local_subclasses: dict[str, tuple[str, set[str]]] = {}
    for local_class in (
        node for node in importing_tree.body if isinstance(node, ast.ClassDef)
    ):
        for base in local_class.bases:
            for base_name in {
                _dotted_name(base, {}) or "",
                _dotted_name(base, aliases) or "",
            }:
                found, _unresolved = _call_targets_for_binding(
                    base_name, binding, set(), imported_class_names
                )
                incomplete = incomplete or _unresolved
                imported_bases = {name for name, method in found if method == "__init__"}
                if imported_bases:
                    methods = {
                        item.name
                        for item in local_class.body
                        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                    }
                    local_subclasses[local_class.name] = (
                        sorted(imported_bases)[0],
                        methods,
                    )
                    if len(imported_bases) > 1 or len(local_class.bases) > 1:
                        incomplete = True
    for node in ast.walk(importing_tree):
        if not isinstance(node, ast.Call):
            continue
        names = {
            _dotted_name(node.func, {}) or "",
            _dotted_name(node.func, aliases) or "",
        }
        for local_name, (imported_base, local_methods) in local_subclasses.items():
            for call_name in names:
                if call_name == local_name and "__init__" not in local_methods:
                    targets.add((imported_base, "__init__"))
                prefix = f"{local_name}()."
                if call_name.startswith(prefix):
                    method_name = call_name[len(prefix):].split(".", 1)[0]
                    if method_name not in local_methods:
                        targets.add((imported_base, method_name))
                if call_name.startswith("super()."):
                    method_name = call_name[len("super()."):].split(".", 1)[0]
                    targets.add((imported_base, method_name))
    return targets, incomplete


def _project_dependency_bindings(
    imported_tree: ast.Module,
    imported_path: str,
    source_path: str,
    repo_root: Path,
    commit: str,
    resolution_cache: dict[tuple[Any, ...], tuple[str, str | None]],
) -> list[dict[str, Any]]:
    dependencies: list[dict[str, Any]] = []
    for binding in _import_bindings(imported_tree, imported_path):
        resolved_path, _issue = _resolve_project_binding(
            repo_root, commit, binding, resolution_cache
        )
        if resolved_path == "unknown":
            dependencies.append(binding)
            continue
        if resolved_path not in {"external", source_path, imported_path}:
            dependencies.append(binding)
    return dependencies


def _resolve_imported_method(
    classes: dict[str, ast.ClassDef],
    class_name: str,
    method_name: str,
    seen: frozenset[str] = frozenset(),
) -> tuple[ast.FunctionDef | ast.AsyncFunctionDef | None, str | None, bool]:
    if class_name in seen or class_name not in classes:
        return None, None, True
    class_node = classes[class_name]
    for item in class_node.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == method_name:
            return item, class_name, False
    local_bases: list[str] = []
    external_base = False
    for base in class_node.bases:
        base_name = (_dotted_name(base, {}) or "").replace("()", "")
        if base_name in classes:
            local_bases.append(base_name)
        elif base_name not in {"", "object"}:
            external_base = True
    for base_name in local_bases:
        found, owner, incomplete = _resolve_imported_method(
            classes, base_name, method_name, seen | {class_name}
        )
        if found is not None or not incomplete:
            return found, owner, incomplete or external_base
        external_base = external_base or incomplete
    if method_name == "__init__" and not local_bases and not external_base:
        return None, class_name, False
    return None, None, True


def _nearest_function_owner(
    node: ast.AST, parents: dict[int, ast.AST]
) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    current = node
    while id(current) in parents:
        current = parents[id(current)]
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return current
    return None


def _control_flow_between(
    node: ast.AST,
    stop: ast.AST | None,
    parents: dict[int, ast.AST],
) -> bool:
    current = node
    while id(current) in parents:
        current = parents[id(current)]
        if current is stop:
            return False
        if isinstance(current, CONTROL_FLOW_NODES):
            return True
    return False


def _local_call_targets(
    call: ast.Call,
    aliases: dict[str, str],
    function_names: set[str],
    class_names: set[str],
    owner: str | None,
) -> set[tuple[str | None, str]]:
    targets: set[tuple[str | None, str]] = set()
    names = {
        _dotted_name(call.func, {}) or "",
        _dotted_name(call.func, aliases) or "",
    }
    for name in names:
        if name in function_names:
            targets.add((None, name))
        if name in class_names:
            targets.add((name, "__init__"))
        self_method = re.fullmatch(r"(?:self|cls)\.([A-Za-z_]\w*)", name)
        if owner and self_method:
            targets.add((owner, self_method.group(1)))
        constructor_method = re.fullmatch(
            r"([A-Za-z_]\w*)\(\)\.([A-Za-z_]\w*)", name
        )
        if constructor_method and constructor_method.group(1) in class_names:
            targets.add(
                (constructor_method.group(1), constructor_method.group(2))
            )
        class_method = re.fullmatch(r"([A-Za-z_]\w*)\.([A-Za-z_]\w*)", name)
        if class_method and class_method.group(1) in class_names:
            targets.add((class_method.group(1), class_method.group(2)))
    return targets


def _invoked_local_definition_reachability(
    tree: ast.Module,
) -> tuple[
    set[tuple[str | None, str]],
    set[tuple[str | None, str]],
    set[tuple[str | None, str]],
    bool,
]:
    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    classes = {
        node.name: node for node in tree.body if isinstance(node, ast.ClassDef)
    }
    known = {(None, name) for name in functions} | {
        (class_name, item.name)
        for class_name, class_node in classes.items()
        for item in class_node.body
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    wrapper = ast.FunctionDef(
        name="__p541b_module_scope__",
        args=ast.arguments(
            posonlyargs=[],
            args=[],
            vararg=None,
            kwonlyargs=[],
            kw_defaults=[],
            kwarg=None,
            defaults=[],
        ),
        body=list(tree.body),
        decorator_list=[],
        returns=None,
        type_comment=None,
    )
    wrapper.lineno = 0
    wrapper.col_offset = 0
    wrapper.end_lineno = 0
    wrapper.end_col_offset = 0
    definition_states: dict[int, str] = {}
    _nodes, _node_states, _call_states, incomplete = (
        _definition_execution_nodes(
            wrapper,
            collect_aliases(tree),
            None,
            functions,
            classes,
            definition_states=definition_states,
        )
    )
    target_nodes: dict[tuple[str | None, str], ast.AST] = {
        (None, name): node for name, node in functions.items()
    }
    target_nodes.update({
        (class_name, item.name): item
        for class_name, class_node in classes.items()
        for item in class_node.body
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
    })
    reached = {
        target
        for target, node in target_nodes.items()
        if definition_states.get(id(node)) == "reached"
    }
    unknown = {
        target
        for target, node in target_nodes.items()
        if definition_states.get(id(node)) == "unknown"
    }
    return reached, unknown, known, incomplete


def _eager_execution_nodes(
    definition: ast.FunctionDef | ast.AsyncFunctionDef,
    *,
    annotations_eager: bool,
) -> list[ast.AST]:
    """Nodes that unconditionally execute whenever ``definition`` runs.

    Mirrors ``ast.walk`` breadth-first order exactly when there is nothing to
    bound. A nested ``FunctionDef``/``AsyncFunctionDef``/``Lambda`` body is
    dormant code — defining it does not run it — so traversal does not
    descend into it here; only its decorator/default expressions, which
    evaluate eagerly at definition time, are included. A nested ``ClassDef``
    does execute its own body immediately (defining a class runs it once),
    so its decorators/bases/keywords/body are included, recursively applying
    the same dormant-body rule to any methods nested inside it.
    """
    nodes: list[ast.AST] = []
    todo: list[ast.AST] = [definition]
    while todo:
        node = todo.pop(0)
        nodes.append(node)
        if node is definition:
            # The definition's own header was evaluated when its enclosing
            # scope created it.  Invoking the function executes only its body.
            todo.extend(node.body)
            continue
        if node is not definition and isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            todo.extend(
                _function_header_expressions(
                    node, annotations_eager=annotations_eager
                )
            )
            continue
        if isinstance(node, ast.Lambda):
            todo.extend(
                default
                for default in (*node.args.defaults, *node.args.kw_defaults)
                if default is not None
            )
            continue
        if node is not definition and isinstance(node, ast.ClassDef):
            todo.extend(node.decorator_list)
            todo.extend(node.bases)
            todo.extend(kw.value for kw in node.keywords)
            todo.extend(node.body)
            continue
        todo.extend(ast.iter_child_nodes(node))
    return nodes


def _definition_execution_nodes(
    definition: ast.FunctionDef | ast.AsyncFunctionDef,
    aliases: dict[str, str],
    owner_class: ast.ClassDef | None,
    module_functions: dict[
        str, ast.FunctionDef | ast.AsyncFunctionDef
    ] | None = None,
    module_classes: dict[str, ast.ClassDef] | None = None,
    project_binding_names: set[str] | None = None,
    definition_states: dict[int, str] | None = None,
) -> tuple[list[ast.AST], dict[int, str], dict[int, str], bool]:
    """Expand nested callables with lexical scope and explicit resolution state."""
    module_functions = module_functions or {}
    module_classes = module_classes or {}
    definition_states = (
        definition_states if definition_states is not None else {}
    )
    if project_binding_names is None:
        # Callers without repository-resolution context remain conservative.
        project_binding_names = set(aliases)
    parents = _ast_parent_map(definition)
    nodes: list[ast.AST] = []
    added: set[int] = set()
    node_states: dict[int, str] = {}
    call_resolutions: dict[int, str] = {}
    resolution_incomplete = False
    queue: list[tuple[Any, ...]] = []
    queued_definitions: set[tuple[Any, ...]] = set()
    visited_definitions: set[tuple[Any, ...]] = set()

    # Bindings are scoped by the exact lexical definition identity.  Each
    # formal retains a deterministic set of possible values plus independent
    # completeness, so separate invocation sites can be merged soundly.
    invocation_bindings: dict[
        int, dict[str, tuple[list[tuple[str, ast.AST, ast.ClassDef | None]], str]]
    ] = {}
    binding_in_progress: set[tuple[int, int]] = set()

    # Assignment records retain their source node and conditionality.  Name
    # and storage resolution can therefore select only reaching bindings at a
    # particular use, rather than unioning the entire flow-insensitive history.
    scope_definitions: dict[
        int, dict[str, list[tuple[ast.AST, bool, ast.AST]]]
    ] = {}
    scope_assignments: dict[
        int, dict[str, list[tuple[ast.AST, bool, ast.AST]]]
    ] = {}
    scope_stored_values: dict[
        int,
        dict[
            str,
            dict[
                tuple[tuple[str, str], ...],
                list[tuple[ast.AST, bool, ast.AST]],
            ],
        ],
    ] = {}
    scope_bound_names: dict[int, set[str]] = {}
    scope_special_bindings: dict[
        int, dict[str, list[dict[str, Any]]]
    ] = {}
    scope_iterable_events: dict[int, list[dict[str, Any]]] = {}

    def lexical_owner(node: ast.AST) -> ast.AST | None:
        current = node
        while id(current) in parents:
            current = parents[id(current)]
            if isinstance(
                current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
            ):
                return current
        return None

    def subscript_component(node: ast.AST) -> tuple[str, str]:
        value = node.value if isinstance(node, ast.Index) else node
        if isinstance(value, ast.Constant):
            if isinstance(value.value, str):
                return ("key:str", value.value)
            if isinstance(value.value, bool):
                return ("key:bool", str(value.value))
            if isinstance(value.value, int):
                return ("key:int", str(value.value))
        return ("dynamic", ast.dump(value, include_attributes=False))

    def storage_reference(
        target: ast.AST,
    ) -> tuple[str, tuple[tuple[str, str], ...]] | None:
        if isinstance(target, ast.Name):
            return target.id, ()
        if isinstance(target, ast.Attribute):
            base = storage_reference(target.value)
            if base is None:
                return None
            return base[0], (*base[1], ("attr", target.attr))
        if isinstance(target, ast.Subscript):
            base = storage_reference(target.value)
            if base is None:
                return None
            return base[0], (*base[1], subscript_component(target.slice))
        return None

    def bound_target_names(target: ast.AST) -> set[str]:
        if isinstance(target, ast.Name):
            return {target.id}
        if isinstance(target, (ast.Tuple, ast.List)):
            names: set[str] = set()
            for item in target.elts:
                names.update(bound_target_names(item))
            return names
        if isinstance(target, ast.Starred):
            return bound_target_names(target.value)
        return set()

    def is_ancestor(ancestor: ast.AST, node: ast.AST) -> bool:
        current = node
        while id(current) in parents:
            current = parents[id(current)]
            if current is ancestor:
                return True
        return False

    def occurs_before(event: ast.AST, use: ast.AST) -> bool:
        if isinstance(event, ast.NamedExpr):
            event_comprehension = nearest_comprehension(event)
            use_comprehension = nearest_comprehension(use)
            if (
                event_comprehension is not None
                and event_comprehension is use_comprehension
            ):
                event_phase = comprehension_phase(
                    event, event_comprehension
                )
                use_phase = comprehension_phase(use, use_comprehension)
                if event_phase != use_phase:
                    return event_phase < use_phase
        return _node_position(event) < _node_position(use) and not is_ancestor(
            event, use
        )

    def contains_node(root: ast.AST, node: ast.AST) -> bool:
        return root is node or is_ancestor(root, node)

    def nearest_comprehension(
        node: ast.AST,
    ) -> ast.ListComp | ast.SetComp | ast.DictComp | ast.GeneratorExp | None:
        current = node
        while id(current) in parents:
            current = parents[id(current)]
            if isinstance(
                current,
                (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp),
            ):
                return current
            if isinstance(
                current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)
            ):
                return None
        return None

    def comprehension_phase(
        node: ast.AST,
        comprehension: (
            ast.ListComp | ast.SetComp | ast.DictComp | ast.GeneratorExp
        ),
    ) -> tuple[int, int, int, int]:
        for index, generator in enumerate(comprehension.generators):
            if contains_node(generator.iter, node):
                return (index, 0, *_node_position(node))
            if contains_node(generator.target, node):
                return (index, 1, *_node_position(node))
            for condition_index, condition in enumerate(generator.ifs):
                if contains_node(condition, node):
                    return (
                        index,
                        2 + condition_index,
                        *_node_position(node),
                    )
        return (
            len(comprehension.generators),
            0,
            *_node_position(node),
        )

    def control_regions(node: ast.AST) -> dict[int, tuple[str, int]]:
        """Return the conditional suites that must run before ``node``."""
        regions: dict[int, tuple[str, int]] = {}
        current = node
        while id(current) in parents:
            parent = parents[id(current)]
            if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
                break
            if isinstance(parent, CONTROL_FLOW_NODES):
                region = ("body", 0)
                for field, value in ast.iter_fields(parent):
                    if isinstance(value, list) and any(
                        item is current for item in value
                    ):
                        branch_index = 0
                        if field in {"handlers", "cases"}:
                            branch_index = next(
                                index
                                for index, item in enumerate(value)
                                if item is current
                            )
                        region = (field, branch_index)
                        break
                    if value is current:
                        region = (field, 0)
                        break
                regions[id(parent)] = region
            current = parent
        return regions

    def conditional_at_use(event: ast.AST, use: ast.AST) -> bool:
        if isinstance(event, ast.NamedExpr):
            event_comprehension = nearest_comprehension(event)
            if event_comprehension is not None:
                if nearest_comprehension(use) is event_comprehension:
                    return False
                return True
        use_regions = control_regions(use)
        return any(
            use_regions.get(control_id) != region
            for control_id, region in control_regions(event).items()
        )

    def reaching_records(
        records: list[tuple[Any, ...]], use: ast.AST
    ) -> tuple[list[tuple[Any, ...]], bool]:
        active: list[tuple[Any, ...]] = []
        incomplete = False
        for record in sorted(
            (item for item in records if occurs_before(item[2], use)),
            key=lambda item: (
                *_node_position(item[2]),
                ast.dump(item[2], include_attributes=False),
            ),
        ):
            effective_conditional = bool(record[1]) and conditional_at_use(
                record[2], use
            )
            effective_record = (
                record[0],
                effective_conditional,
                *record[2:],
            )
            if effective_conditional:
                active.append(effective_record)
                incomplete = True
            else:
                active = [effective_record]
                incomplete = False
        return active, incomplete

    indexed_nodes: set[int] = set()
    indexed_roots: set[int] = set()

    def add_special_binding(
        scope: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
        name: str,
        *,
        kind: str,
        source: ast.AST | None,
        target: ast.AST | None,
        event: ast.AST,
        owner: ast.AST,
        item_index: int | None = None,
    ) -> None:
        scope_bound_names.setdefault(id(scope), set()).add(name)
        scope_special_bindings.setdefault(id(scope), {}).setdefault(
            name, []
        ).append({
            "kind": kind,
            "source": source,
            "target": target,
            "event": event,
            "owner": owner,
            "item_index": item_index,
        })

    def index_scope_root(root: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        if id(root) in indexed_roots:
            return
        indexed_roots.add(id(root))
        parents.update(_ast_parent_map(root))
        for candidate in ast.walk(root):
            if id(candidate) in indexed_nodes:
                continue
            indexed_nodes.add(id(candidate))
            if candidate is root:
                continue
            candidate_scope = lexical_owner(candidate)
            if isinstance(
                candidate_scope,
                (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
            ):
                if isinstance(candidate, (ast.For, ast.AsyncFor)):
                    for name in sorted(bound_target_names(candidate.target)):
                        add_special_binding(
                            candidate_scope,
                            name,
                            kind=(
                                "async_for"
                                if isinstance(candidate, ast.AsyncFor)
                                else "for"
                            ),
                            source=candidate.iter,
                            target=candidate.target,
                            event=candidate.target,
                            owner=candidate,
                        )
                elif isinstance(candidate, (ast.With, ast.AsyncWith)):
                    for item_index, item in enumerate(candidate.items):
                        if item.optional_vars is not None:
                            for name in sorted(
                                bound_target_names(item.optional_vars)
                            ):
                                add_special_binding(
                                    candidate_scope,
                                    name,
                                    kind=(
                                        "async_with"
                                        if isinstance(candidate, ast.AsyncWith)
                                        else "with"
                                    ),
                                    source=item.context_expr,
                                    target=item.optional_vars,
                                    event=item.optional_vars,
                                    owner=candidate,
                                    item_index=item_index,
                                )
                elif isinstance(candidate, ast.ExceptHandler) and candidate.name:
                    add_special_binding(
                        candidate_scope,
                        candidate.name,
                        kind="except",
                        source=None,
                        target=None,
                        event=candidate,
                        owner=candidate,
                    )
            if isinstance(
                candidate, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
            ):
                scope = lexical_owner(candidate)
                if scope is not None:
                    scope_definitions.setdefault(id(scope), {}).setdefault(
                        candidate.name, []
                    ).append((
                        candidate,
                        _control_flow_between(candidate, scope, parents),
                        candidate,
                    ))
            if isinstance(candidate, ast.Assign):
                value, targets = candidate.value, candidate.targets
            elif (
                isinstance(candidate, ast.AnnAssign)
                and candidate.value is not None
            ):
                value, targets = candidate.value, [candidate.target]
            elif isinstance(candidate, ast.NamedExpr):
                current: ast.AST = candidate
                inside_lambda = False
                while id(current) in parents:
                    current = parents[id(current)]
                    if current is candidate_scope:
                        break
                    if isinstance(current, ast.Lambda):
                        inside_lambda = True
                        break
                if inside_lambda:
                    continue
                value, targets = candidate.value, [candidate.target]
            elif isinstance(candidate, ast.AugAssign):
                scope = lexical_owner(candidate)
                if isinstance(
                    scope,
                    (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
                ):
                    scope_iterable_events.setdefault(id(scope), []).append({
                        "kind": "augassign",
                        "event": candidate,
                        "target": candidate.target,
                        "value": candidate.value,
                        "conditional": _control_flow_between(
                            candidate, scope, parents
                        ),
                    })
                continue
            else:
                if isinstance(candidate, ast.Call):
                    scope = lexical_owner(candidate)
                    current: ast.AST = candidate
                    inside_lambda = False
                    while id(current) in parents:
                        current = parents[id(current)]
                        if current is scope:
                            break
                        if isinstance(current, ast.Lambda):
                            inside_lambda = True
                            break
                    if isinstance(
                        scope,
                        (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
                    ) and not inside_lambda:
                        scope_iterable_events.setdefault(id(scope), []).append({
                            "kind": "call",
                            "event": candidate,
                            "call": candidate,
                            "conditional": _control_flow_between(
                                candidate, scope, parents
                            ),
                        })
                continue
            scope = lexical_owner(candidate)
            if not isinstance(
                scope,
                (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
            ):
                continue
            conditional = _control_flow_between(candidate, scope, parents)
            if isinstance(candidate, ast.NamedExpr):
                conditional = conditional or nearest_comprehension(
                    candidate
                ) is not None
            for target in targets:
                target_bound_names = bound_target_names(target)
                if target_bound_names:
                    scope_bound_names.setdefault(id(scope), set()).update(
                        target_bound_names
                    )
                if isinstance(target, ast.Name):
                    scope_assignments.setdefault(id(scope), {}).setdefault(
                        target.id, []
                    ).append((value, conditional, candidate))
                    scope_iterable_events.setdefault(id(scope), []).append({
                        "kind": "bind",
                        "event": candidate,
                        "target": target,
                        "value": value,
                        "conditional": conditional,
                        "value_identity": id(value),
                    })
                    continue
                if isinstance(target, (ast.Tuple, ast.List, ast.Starred)):
                    for name in sorted(target_bound_names):
                        add_special_binding(
                            scope,
                            name,
                            kind="destructure",
                            source=value,
                            target=target,
                            event=candidate,
                            owner=candidate,
                        )
                    continue
                storage = storage_reference(target)
                if storage is not None and storage[1]:
                    owner_name, path = storage
                    scope_stored_values.setdefault(id(scope), {}).setdefault(
                        owner_name, {}
                    ).setdefault(path, []).append((
                        value, conditional, candidate
                    ))
                    scope_iterable_events.setdefault(id(scope), []).append({
                        "kind": "storage_write",
                        "event": candidate,
                        "target": target,
                        "value": value,
                        "conditional": conditional,
                    })
        for definitions in scope_definitions.values():
            for values in definitions.values():
                values.sort(
                    key=lambda item: (
                        getattr(item[0], "lineno", 0),
                        getattr(item[0], "col_offset", 0),
                        getattr(item[0], "name", ""),
                    )
                )

    index_scope_root(definition)

    def parameter_names(
        function: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
    ) -> set[str]:
        if isinstance(function, ast.ClassDef):
            return set()
        result = {
            argument.arg
            for argument in (
                *getattr(function.args, "posonlyargs", ()),
                *function.args.args,
                *function.args.kwonlyargs,
            )
        }
        if function.args.vararg is not None:
            result.add(function.args.vararg.arg)
        if function.args.kwarg is not None:
            result.add(function.args.kwarg.arg)
        return result

    def function_scope_chain(
        function: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
        result = [function]
        current: ast.AST = function
        while id(current) in parents:
            current = parents[id(current)]
            if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
                result.append(current)
        return result

    def resolution_scope_chain(
        current_definition: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
        use: ast.AST,
    ) -> list[ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef]:
        """Return lexical bindings visible at ``use`` without method leakage."""
        result: list[
            ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef
        ] = []
        current = use
        while id(current) in parents:
            current = parents[id(current)]
            if isinstance(
                current,
                (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
            ):
                result.append(current)
                if current is current_definition:
                    break
                if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    # A function body never closes over an enclosing class
                    # namespace.  Its enclosing function scopes are appended
                    # below from the exact definition chain instead.
                    break
        if isinstance(current_definition, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for scope in function_scope_chain(current_definition):
                if scope not in result:
                    result.append(scope)
        elif current_definition not in result:
            result.append(current_definition)
        return result

    def definition_class_owner(node: ast.AST) -> ast.ClassDef | None:
        scope = lexical_owner(node)
        return scope if isinstance(scope, ast.ClassDef) else None

    def deduplicate_values(
        values: list[tuple[str, ast.AST, ast.ClassDef | None]],
    ) -> list[tuple[str, ast.AST, ast.ClassDef | None]]:
        deduplicated: dict[
            tuple[str, int, int], tuple[str, ast.AST, ast.ClassDef | None]
        ] = {}
        for kind, target, target_owner in values:
            deduplicated.setdefault(
                (kind, id(target), id(target_owner) if target_owner else 0),
                (kind, target, target_owner),
            )
        return sorted(
            deduplicated.values(),
            key=lambda item: (
                getattr(item[1], "lineno", 0),
                getattr(item[1], "col_offset", 0),
                item[0],
                getattr(item[1], "name", ""),
            ),
        )

    def merge_status(left: str, right: str) -> str:
        if "incomplete" in {left, right}:
            return "incomplete"
        if left == right:
            return left
        if "complete" in {left, right}:
            return "incomplete"
        return "not_local"

    safe_global_names = frozenset({
        "abs", "all", "any", "ascii", "bin", "bool", "bytes", "callable",
        "chr", "dict", "dir", "divmod", "enumerate", "filter", "float",
        "format", "frozenset", "getattr", "hasattr", "hash", "hex", "id",
        "int", "isinstance", "issubclass", "iter", "len", "list", "map",
        "max", "min", "next", "object", "oct", "open", "ord", "pow",
        "print", "range", "repr", "reversed", "round", "set", "slice",
        "sorted", "str", "sum", "super", "tuple", "type", "vars", "zip",
    })

    def value_signature(
        value: tuple[str, ast.AST, ast.ClassDef | None],
    ) -> tuple[Any, ...]:
        kind, target, target_owner = value
        return (
            kind,
            type(target).__name__,
            getattr(target, "lineno", 0),
            getattr(target, "col_offset", 0),
            getattr(target, "end_lineno", 0),
            getattr(target, "end_col_offset", 0),
            getattr(target, "name", ""),
            type(target_owner).__name__ if target_owner is not None else "",
            getattr(target_owner, "lineno", 0) if target_owner is not None else 0,
            getattr(target_owner, "col_offset", 0)
            if target_owner is not None
            else 0,
            getattr(target_owner, "name", "")
            if target_owner is not None
            else "",
        )

    def binding_signature(
        function: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> tuple[Any, ...]:
        signature: list[tuple[Any, ...]] = []
        for scope in sorted(
            function_scope_chain(function),
            key=lambda item: (
                getattr(item, "lineno", 0),
                getattr(item, "col_offset", 0),
                item.name,
            ),
        ):
            for name, (values, status) in sorted(
                invocation_bindings.get(id(scope), {}).items()
            ):
                signature.append((
                    getattr(scope, "lineno", 0),
                    getattr(scope, "col_offset", 0),
                    scope.name,
                    name,
                    status,
                    tuple(value_signature(value) for value in values),
                ))
        return tuple(signature)

    comprehension_types = (
        ast.ListComp,
        ast.SetComp,
        ast.DictComp,
        ast.GeneratorExp,
    )

    def raw_deduplicate(values: list[ast.AST]) -> list[ast.AST]:
        deduplicated: dict[int, ast.AST] = {}
        for value in values:
            deduplicated.setdefault(id(value), value)
        return list(deduplicated.values())

    def comprehension_ancestors(
        use: ast.AST,
    ) -> list[ast.ListComp | ast.SetComp | ast.DictComp | ast.GeneratorExp]:
        result: list[
            ast.ListComp | ast.SetComp | ast.DictComp | ast.GeneratorExp
        ] = []
        current = use
        while id(current) in parents:
            current = parents[id(current)]
            if isinstance(current, comprehension_types):
                result.append(current)
            if isinstance(
                current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)
            ):
                break
        return result

    def visible_generator_count(
        comprehension: (
            ast.ListComp | ast.SetComp | ast.DictComp | ast.GeneratorExp
        ),
        use: ast.AST,
    ) -> int:
        for index, generator in enumerate(comprehension.generators):
            if contains_node(generator.iter, use) or contains_node(
                generator.target, use
            ):
                return index
            if any(
                contains_node(condition, use) for condition in generator.ifs
            ):
                return index + 1
        return len(comprehension.generators)

    def visible_comprehension_binding(
        name: str, use: ast.AST
    ) -> dict[str, Any] | None:
        for comprehension in comprehension_ancestors(use):
            visible = visible_generator_count(comprehension, use)
            for index in range(visible - 1, -1, -1):
                generator = comprehension.generators[index]
                if name in bound_target_names(generator.target):
                    return {
                        "kind": "comprehension",
                        "source": generator.iter,
                        "target": generator.target,
                        "event": generator.target,
                        "owner": comprehension,
                        "generator_index": index,
                    }
        return None

    def target_contains_name(target: ast.AST, name: str) -> bool:
        return name in bound_target_names(target)

    def destructured_sources(
        target: ast.AST,
        element: ast.AST,
        name: str,
        current_definition: ast.FunctionDef | ast.AsyncFunctionDef,
        use: ast.AST,
        seen: frozenset[tuple[str, int]],
    ) -> tuple[list[ast.AST], str]:
        if isinstance(target, ast.Name):
            return ([element], "complete") if target.id == name else ([], "complete")
        if isinstance(target, ast.Starred):
            return destructured_sources(
                target.value,
                element,
                name,
                current_definition,
                use,
                seen,
            )
        if not isinstance(target, (ast.Tuple, ast.List)):
            return (
                ([], "incomplete")
                if target_contains_name(target, name)
                else ([], "complete")
            )
        if not target_contains_name(target, name):
            return [], "complete"
        if isinstance(element, ast.Name):
            key = (f"destructure-alias:{element.id}", id(element))
            if key in seen:
                return [], "incomplete"
            aliases_to_elements, alias_status, local = raw_name_sources(
                element.id,
                current_definition,
                element,
                seen | {key},
            )
            if local:
                values: list[ast.AST] = []
                status = alias_status
                for alias_value in aliases_to_elements:
                    nested_values, nested_status = destructured_sources(
                        target,
                        alias_value,
                        name,
                        current_definition,
                        use,
                        seen | {key},
                    )
                    values.extend(nested_values)
                    status = merge_status(status, nested_status)
                return raw_deduplicate(values), status
        if not isinstance(element, (ast.Tuple, ast.List)):
            return [], "incomplete"

        target_items = list(target.elts)
        element_items = list(element.elts)
        starred_indexes = [
            index
            for index, item in enumerate(target_items)
            if isinstance(item, ast.Starred)
        ]
        if len(starred_indexes) > 1:
            return [], "incomplete"
        pairs: list[tuple[ast.AST, ast.AST]] = []
        if not starred_indexes:
            if len(target_items) != len(element_items):
                return [], "incomplete"
            pairs.extend(zip(target_items, element_items))
        else:
            starred_index = starred_indexes[0]
            trailing = len(target_items) - starred_index - 1
            if len(element_items) < starred_index + trailing:
                return [], "incomplete"
            pairs.extend(zip(
                target_items[:starred_index],
                element_items[:starred_index],
            ))
            starred_values = element_items[
                starred_index:len(element_items) - trailing if trailing else None
            ]
            starred_value = ast.copy_location(
                ast.List(elts=starred_values, ctx=ast.Load()), element
            )
            pairs.append((target_items[starred_index], starred_value))
            if trailing:
                pairs.extend(zip(
                    target_items[-trailing:], element_items[-trailing:]
                ))

        values: list[ast.AST] = []
        status = "complete"
        for nested_target, nested_element in pairs:
            if not target_contains_name(nested_target, name):
                continue
            nested_values, nested_status = destructured_sources(
                nested_target,
                nested_element,
                name,
                current_definition,
                use,
                seen,
            )
            values.extend(nested_values)
            status = merge_status(status, nested_status)
        return raw_deduplicate(values), status

    def raw_name_sources(
        name: str,
        current_definition: (
            ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef
        ),
        use: ast.AST,
        seen: frozenset[tuple[str, int]],
    ) -> tuple[list[ast.AST], str, bool]:
        comprehension_binding = visible_comprehension_binding(name, use)
        if comprehension_binding is not None:
            key = (f"raw-comprehension:{name}", id(comprehension_binding["event"]))
            if key in seen:
                return [], "incomplete", True
            sources, status, _order = iteration_target_sources(
                comprehension_binding["source"],
                comprehension_binding["target"],
                name,
                current_definition,
                use,
                seen | {key},
            )
            return sources, status, True

        for scope in resolution_scope_chain(current_definition, use):
            assignments = scope_assignments.get(id(scope), {}).get(name, [])
            definitions = scope_definitions.get(id(scope), {}).get(name, [])
            destructuring = [
                record
                for record in scope_special_bindings.get(id(scope), {}).get(
                    name, []
                )
                if record["kind"] == "destructure"
                and occurs_before(record["event"], use)
            ]
            is_parameter = name in parameter_names(scope)
            is_bound = name in scope_bound_names.get(id(scope), set())
            if (
                not assignments
                and not definitions
                and not destructuring
                and not is_parameter
                and not is_bound
            ):
                continue
            key = (f"raw-name:{name}", id(scope))
            if key in seen:
                return [], "incomplete", True
            values: list[ast.AST] = []
            status = "not_local"
            if is_parameter:
                binding = invocation_bindings.get(id(scope), {}).get(name)
                if binding is None:
                    status = "incomplete"
                else:
                    values.extend(item[1] for item in binding[0])
                    status = binding[1]
            events, conditional = reaching_records(assignments, use)
            if events and not events[0][1]:
                values = []
                status = "complete"
            for source, is_conditional, _event in events:
                if is_conditional:
                    values.append(source)
                    status = "incomplete"
                else:
                    values = [source]
                    status = "complete"
            if conditional:
                status = "incomplete"
            for record in destructuring:
                extracted, extracted_status = destructured_sources(
                    record["target"],
                    record["source"],
                    name,
                    current_definition,
                    use,
                    seen | {key},
                )
                if record.get("conditional") and conditional_at_use(
                    record["event"], use
                ):
                    values.extend(extracted)
                    status = "incomplete"
                else:
                    values = list(extracted)
                    status = extracted_status
            if not events and not destructuring and not is_parameter:
                return [], "incomplete", True
            if not values and status == "not_local":
                status = "incomplete"
            return raw_deduplicate(values), status, True
        return [], "not_local", False

    def root_reference_name(node: ast.AST) -> str | None:
        current = node
        while isinstance(current, (ast.Attribute, ast.Subscript)):
            current = current.value
        return current.id if isinstance(current, ast.Name) else None

    def mutable_name_iterable_elements(
        name: str,
        current_definition: (
            ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef
        ),
        use: ast.AST,
        seen: frozenset[tuple[str, int]],
    ) -> tuple[list[ast.AST], str, str] | None:
        """Reconstruct a name-bound iterable through reaching alias mutations."""
        binding_scope: (
            ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef | None
        ) = None
        for scope in resolution_scope_chain(current_definition, use):
            if name in scope_assignments.get(id(scope), {}):
                binding_scope = scope
                break
        if binding_scope is None:
            return None
        events = scope_iterable_events.get(id(binding_scope), [])
        if not events:
            return None
        guard = (f"mutable-name:{name}", id(binding_scope))
        if guard in seen:
            return [], "incomplete", "unknown"
        next_seen = seen | {guard}

        Token = tuple[str, int, int]
        bindings: dict[str, set[Token]] = {}
        token_sources: dict[Token, ast.AST] = {}
        token_incomplete: dict[Token, bool] = {}
        token_mutations: dict[Token, list[dict[str, Any]]] = {}
        binding_uncertain: set[str] = set()

        def current_tokens(reference: ast.AST) -> set[Token]:
            root_name = root_reference_name(reference)
            return set(bindings.get(root_name or "", set()))

        def mark_tokens_unknown(tokens: set[Token], event: ast.AST) -> None:
            for token in tokens:
                token_mutations.setdefault(token, []).append({
                    "kind": "unknown",
                    "event": event,
                    "conditional": True,
                })

        read_only_methods = frozenset({
            "__contains__", "copy", "count", "get", "index", "isdisjoint",
            "issubset", "issuperset", "items", "keys", "values",
        })
        safe_consumers = frozenset({
            "all", "any", "enumerate", "frozenset", "iter", "len", "list",
            "max", "min", "print", "reversed", "set", "sorted", "sum",
            "tuple", "zip",
        })

        ordered_events = sorted(
            (
                event
                for event in events
                if occurs_before(event["event"], use)
            ),
            key=lambda item: (
                *_node_position(item["event"]),
                {"bind": 0, "augassign": 1}.get(item["kind"], 2),
                ast.dump(item["event"], include_attributes=False),
            ),
        )
        for record in ordered_events:
            event = record["event"]
            conditional = bool(record.get("conditional")) and (
                conditional_at_use(event, use)
            )
            kind = record["kind"]
            if kind == "bind":
                target = record["target"]
                if not isinstance(target, ast.Name):
                    continue
                value = record["value"]
                if isinstance(value, ast.Name) and value.id in bindings:
                    new_tokens = set(bindings[value.id])
                else:
                    token = (
                        "value",
                        int(record["value_identity"]),
                        id(event),
                    )
                    token_sources.setdefault(token, value)
                    token_incomplete.setdefault(
                        token,
                        isinstance(value, ast.Name),
                    )
                    new_tokens = {token}
                if conditional:
                    bindings.setdefault(target.id, set()).update(new_tokens)
                    binding_uncertain.add(target.id)
                    for token in new_tokens:
                        token_incomplete[token] = True
                else:
                    bindings[target.id] = new_tokens
                    binding_uncertain.discard(target.id)
                continue

            if kind == "augassign":
                target = record["target"]
                tokens = current_tokens(target)
                if not tokens:
                    continue
                mutation_kind = (
                    "extend"
                    if isinstance(target, ast.Name)
                    and isinstance(event.op, ast.Add)
                    else "unknown"
                )
                for token in tokens:
                    token_mutations.setdefault(token, []).append({
                        "kind": mutation_kind,
                        "event": event,
                        "value": record["value"],
                        "conditional": conditional,
                    })
                    if conditional or mutation_kind == "unknown":
                        token_incomplete[token] = True
                continue

            if kind == "storage_write":
                mark_tokens_unknown(current_tokens(record["target"]), event)
                continue

            assert kind == "call"
            call = record["call"]
            handled_method = False
            if isinstance(call.func, ast.Attribute):
                tokens = current_tokens(call.func.value)
                if tokens:
                    handled_method = True
                    method = call.func.attr
                    mutation: dict[str, Any]
                    if method == "append" and len(call.args) == 1 and not call.keywords:
                        mutation = {
                            "kind": "append",
                            "value": call.args[0],
                        }
                    elif method == "extend" and len(call.args) == 1 and not call.keywords:
                        mutation = {
                            "kind": "extend",
                            "value": call.args[0],
                        }
                    elif method == "update" and len(call.args) <= 1:
                        update_values: list[ast.AST] = list(call.args)
                        if call.keywords:
                            if any(item.arg is None for item in call.keywords):
                                update_values = []
                            else:
                                update_values.append(
                                    ast.copy_location(
                                        ast.Dict(
                                            keys=[
                                                ast.Constant(value=item.arg)
                                                for item in call.keywords
                                            ],
                                            values=[item.value for item in call.keywords],
                                        ),
                                        call,
                                    )
                                )
                        mutation = {
                            "kind": (
                                "dict_update"
                                if update_values or not call.args and not call.keywords
                                else "unknown"
                            ),
                            "values": update_values,
                        }
                    elif method in read_only_methods:
                        mutation = {"kind": "none"}
                    elif method in {"add", "insert"} and call.args:
                        mutation = {
                            "kind": "append",
                            "value": call.args[-1],
                            "force_incomplete": True,
                        }
                    else:
                        mutation = {"kind": "unknown"}
                    if mutation["kind"] != "none":
                        for token in tokens:
                            token_mutations.setdefault(token, []).append({
                                **mutation,
                                "event": event,
                                "conditional": conditional,
                            })
                            if (
                                conditional
                                or mutation["kind"] == "unknown"
                                or mutation.get("force_incomplete")
                            ):
                                token_incomplete[token] = True
            if handled_method:
                continue

            resolved_call = (_dotted_name(call.func, aliases) or "").replace(
                "()", ""
            )
            if resolved_call in safe_consumers:
                continue
            referenced_names = {
                item.id
                for value in [
                    *call.args,
                    *(keyword.value for keyword in call.keywords),
                ]
                for item in ast.walk(value)
                if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Load)
            }
            for referenced_name in referenced_names:
                mark_tokens_unknown(
                    set(bindings.get(referenced_name, set())), event
                )

        final_tokens = set(bindings.get(name, set()))
        if not final_tokens:
            return [], "incomplete", "unknown"
        elements: list[ast.AST] = []
        status = "incomplete" if (
            len(final_tokens) > 1 or name in binding_uncertain
        ) else "complete"
        orders: set[str] = set()
        for token in sorted(final_tokens):
            source = token_sources.get(token)
            if source is None:
                status = "incomplete"
                orders.add("unknown")
                continue
            base, base_status, order = bounded_iterable_elements(
                source,
                current_definition,
                source,
                next_seen,
            )
            token_elements = list(base)
            token_status = base_status
            if token_incomplete.get(token):
                token_status = "incomplete"
            for mutation in token_mutations.get(token, []):
                mutation_kind = mutation["kind"]
                if mutation_kind == "append":
                    token_elements.append(mutation["value"])
                    if mutation.get("conditional") or mutation.get(
                        "force_incomplete"
                    ):
                        token_status = "incomplete"
                        order = "unknown"
                elif mutation_kind in {"extend", "dict_update"}:
                    values = (
                        [mutation["value"]]
                        if mutation_kind == "extend"
                        else mutation.get("values", [])
                    )
                    if not values and mutation_kind == "dict_update":
                        continue
                    for extension in values:
                        expanded, expanded_status, expanded_order = (
                            bounded_iterable_elements(
                                extension,
                                current_definition,
                                mutation["event"],
                                next_seen,
                            )
                        )
                        token_elements.extend(expanded)
                        token_status = merge_status(
                            token_status, expanded_status
                        )
                        if expanded_order != "ordered":
                            order = "unknown"
                    if mutation.get("conditional"):
                        token_status = "incomplete"
                else:
                    token_status = "incomplete"
                    order = "unknown"
            elements.extend(token_elements)
            status = merge_status(status, token_status)
            orders.add(order)
        order = orders.pop() if len(orders) == 1 else "unknown"
        return raw_deduplicate(elements), status, order

    def bounded_iterable_elements(
        value: ast.AST,
        current_definition: (
            ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef
        ),
        use: ast.AST,
        seen: frozenset[tuple[str, int]] = frozenset(),
    ) -> tuple[list[ast.AST], str, str]:
        key = ("bounded-iterable", id(value))
        if key in seen:
            return [], "incomplete", "unknown"
        next_seen = seen | {key}

        if isinstance(value, (ast.List, ast.Tuple, ast.Set)):
            elements: list[ast.AST] = []
            status = "complete"
            order = "unordered" if isinstance(value, ast.Set) else "ordered"
            for element in value.elts:
                if not isinstance(element, ast.Starred):
                    elements.append(element)
                    continue
                expanded, expanded_status, expanded_order = (
                    bounded_iterable_elements(
                        element.value,
                        current_definition,
                        element.value,
                        next_seen,
                    )
                )
                elements.extend(expanded)
                status = merge_status(status, expanded_status)
                if expanded_order != "ordered":
                    order = "unordered"
            return raw_deduplicate(elements), status, order

        if isinstance(value, ast.Dict):
            elements = []
            status = "complete"
            for key_node, item in zip(value.keys, value.values):
                if key_node is not None:
                    elements.append(key_node)
                    continue
                expanded, expanded_status, _expanded_order = (
                    bounded_iterable_elements(
                        item, current_definition, item, next_seen
                    )
                )
                elements.extend(expanded)
                status = merge_status(status, expanded_status)
            return raw_deduplicate(elements), status, "ordered"

        if isinstance(value, ast.Name):
            reconstructed = mutable_name_iterable_elements(
                value.id,
                current_definition,
                use,
                next_seen,
            )
            if reconstructed is not None:
                return reconstructed
            sources, source_status, local = raw_name_sources(
                value.id, current_definition, use, next_seen
            )
            if not local:
                return [], "incomplete", "unknown"
            elements: list[ast.AST] = []
            status = source_status
            orders: set[str] = set()
            for source in sources:
                expanded, expanded_status, expanded_order = (
                    bounded_iterable_elements(
                        source, current_definition, source, next_seen
                    )
                )
                elements.extend(expanded)
                status = merge_status(status, expanded_status)
                orders.add(expanded_order)
            order = orders.pop() if len(orders) == 1 else "unknown"
            if not sources:
                status = "incomplete"
            return raw_deduplicate(elements), status, order

        if isinstance(value, ast.IfExp):
            left, left_status, left_order = bounded_iterable_elements(
                value.body, current_definition, value.body, next_seen
            )
            right, right_status, right_order = bounded_iterable_elements(
                value.orelse, current_definition, value.orelse, next_seen
            )
            order = left_order if left_order == right_order else "unknown"
            return (
                raw_deduplicate([*left, *right]),
                "incomplete"
                if "incomplete" in {left_status, right_status}
                else "incomplete",
                order,
            )
        return [], "incomplete", "unknown"

    def modeled_iterable_mutation_call(
        call: ast.Call,
        current_definition: (
            ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef
        ),
    ) -> str | None:
        if not isinstance(call.func, ast.Attribute):
            return None
        if call.func.attr not in {
            "add", "append", "clear", "extend", "insert", "pop", "remove",
            "reverse", "setdefault", "sort", "update",
        }:
            return None
        if not isinstance(call.func.value, ast.Name):
            return None
        binding_scope = next(
            (
                scope
                for scope in resolution_scope_chain(current_definition, call)
                if call.func.value.id
                in scope_assignments.get(id(scope), {})
            ),
            None,
        )
        if binding_scope is None:
            return None
        reconstructed = mutable_name_iterable_elements(
            call.func.value.id,
            current_definition,
            call,
            frozenset(),
        )
        if reconstructed is None or reconstructed[2] == "unknown":
            return None
        active_scope = resolution_scope_chain(current_definition, call)[0]
        return "modeled" if binding_scope is active_scope else "incomplete"

    def iteration_target_sources(
        source: ast.AST,
        target: ast.AST,
        name: str,
        current_definition: ast.FunctionDef | ast.AsyncFunctionDef,
        use: ast.AST,
        seen: frozenset[tuple[str, int]] = frozenset(),
        *,
        post_loop: bool = False,
        preserve_all_ordered: bool = False,
    ) -> tuple[list[ast.AST], str, str]:
        elements, status, order = bounded_iterable_elements(
            source, current_definition, use, seen
        )
        selected = elements
        if (
            post_loop
            and elements
            and order == "ordered"
            and status == "complete"
            and not preserve_all_ordered
        ):
            selected = [elements[-1]]
        values: list[ast.AST] = []
        for element in selected:
            extracted, extracted_status = destructured_sources(
                target,
                element,
                name,
                current_definition,
                use,
                seen,
            )
            values.extend(extracted)
            status = merge_status(status, extracted_status)
        return raw_deduplicate(values), status, order

    def node_in_suite(nodes: list[ast.stmt], use: ast.AST) -> bool:
        return any(contains_node(node, use) for node in nodes)

    def loop_has_owned_break(owner: ast.For | ast.AsyncFor) -> bool:
        for candidate in ast.walk(owner):
            if not isinstance(candidate, ast.Break):
                continue
            current: ast.AST = candidate
            while id(current) in parents:
                current = parents[id(current)]
                if isinstance(current, (ast.For, ast.AsyncFor, ast.While)):
                    if current is owner:
                        return True
                    break
        return False

    def special_binding_event(
        record: dict[str, Any],
        name: str,
        scope: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
        use: ast.AST,
        seen: frozenset[tuple[str, int]],
    ) -> dict[str, Any] | None:
        kind = record["kind"]
        owner = record["owner"]
        event = record["event"]
        owner_conditional = _control_flow_between(owner, scope, parents)

        if kind == "destructure":
            if not occurs_before(event, use):
                return None
            sources, status = destructured_sources(
                record["target"],
                record["source"],
                name,
                scope,
                use,
                seen,
            )
            conditional = owner_conditional and conditional_at_use(event, use)
            return {
                "event": event,
                "conditional": conditional,
                "sources": sources,
                "status": (
                    "incomplete" if conditional else status
                ),
            }

        if kind in {"for", "async_for"}:
            assert isinstance(owner, (ast.For, ast.AsyncFor))
            if contains_node(owner.iter, use) or contains_node(
                owner.target, use
            ):
                return None
            in_body = node_in_suite(owner.body, use)
            in_orelse = node_in_suite(owner.orelse, use)
            if not in_body and not in_orelse and not occurs_before(event, use):
                return None
            if kind == "async_for":
                return {
                    "event": event,
                    "conditional": not in_body,
                    "sources": [],
                    "status": "incomplete",
                }
            preserve_all = post_loop = not in_body
            preserve_all = preserve_all and loop_has_owned_break(owner)
            sources, status, _order = iteration_target_sources(
                record["source"],
                record["target"],
                name,
                scope,
                use,
                seen,
                post_loop=post_loop,
                preserve_all_ordered=preserve_all,
            )
            if status == "complete" and not sources:
                return None
            conditional = False
            if post_loop and status == "incomplete":
                conditional = True
            if owner_conditional and conditional_at_use(event, use):
                conditional = True
            return {
                "event": event,
                "conditional": conditional,
                "sources": sources,
                "status": status,
            }

        if kind in {"with", "async_with"}:
            assert isinstance(owner, (ast.With, ast.AsyncWith))
            record_index = int(record["item_index"])
            visible_in_owner = node_in_suite(owner.body, use)
            for item_index, item in enumerate(owner.items):
                if contains_node(item.context_expr, use):
                    visible_in_owner = record_index < item_index
                    break
                if item.optional_vars is not None and contains_node(
                    item.optional_vars, use
                ):
                    visible_in_owner = record_index < item_index
                    break
            if contains_node(owner, use) and not visible_in_owner:
                return None
            if not contains_node(owner, use) and not occurs_before(event, use):
                return None
            conditional = not visible_in_owner
            if owner_conditional and conditional_at_use(event, use):
                conditional = True
            return {
                "event": event,
                "conditional": conditional,
                "sources": [],
                "status": "incomplete",
            }

        assert kind == "except" and isinstance(owner, ast.ExceptHandler)
        if owner.type is not None and contains_node(owner.type, use):
            return None
        in_body = node_in_suite(owner.body, use)
        if not in_body and not occurs_before(event, use):
            return None
        return {
            "event": event,
            "conditional": not in_body,
            "sources": [],
            "status": "incomplete",
        }

    def resolve_source_values(
        sources: list[ast.AST],
        source_status: str,
        current_definition: (
            ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef
        ),
        current_owner: ast.ClassDef | None,
        seen: frozenset[tuple[str, int]],
    ) -> tuple[list[tuple[str, ast.AST, ast.ClassDef | None]], str]:
        values: list[tuple[str, ast.AST, ast.ClassDef | None]] = []
        status = source_status
        for source in sources:
            resolved, resolved_status = resolve_value(
                source,
                current_definition,
                current_owner,
                seen,
            )
            if resolved_status == "not_local":
                if isinstance(source, ast.Name):
                    resolved_status = "incomplete"
                else:
                    resolved = [("opaque", source, None)]
                    resolved_status = "complete"
            values.extend(resolved)
            status = merge_status(status, resolved_status)
        return deduplicate_values(values), status

    def call_is_proven_iteration_unreachable(
        call: ast.Call,
        current_definition: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> bool:
        current: ast.AST = call
        while id(current) in parents:
            current = parents[id(current)]
            if current is current_definition:
                break
            if isinstance(current, ast.For) and node_in_suite(
                current.body, call
            ):
                elements, status, _order = bounded_iterable_elements(
                    current.iter, current_definition, current.iter
                )
                if status == "complete" and not elements:
                    return True
            if isinstance(current, comprehension_types):
                required = visible_generator_count(current, call)
                for generator in current.generators[:required]:
                    elements, status, _order = bounded_iterable_elements(
                        generator.iter,
                        current_definition,
                        generator.iter,
                    )
                    if status == "complete" and not elements:
                        return True
        return False

    def storage_scope(
        root_name: str,
        current_definition: (
            ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef
        ),
        use: ast.AST,
    ) -> ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef | None:
        for scope in resolution_scope_chain(current_definition, use):
            if (
                root_name in scope_definitions.get(id(scope), {})
                or root_name in scope_assignments.get(id(scope), {})
                or root_name in scope_stored_values.get(id(scope), {})
                or root_name in parameter_names(scope)
            ):
                return scope
        return None

    def storage_records(
        reference: tuple[str, tuple[tuple[str, str], ...]],
        current_definition: (
            ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef
        ),
        use: ast.AST,
        *,
        whole_owner: bool = False,
    ) -> tuple[
        list[tuple[ast.AST, bool, ast.AST]],
        bool,
        ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef | None,
    ]:
        root_name, requested_path = reference
        scope = storage_scope(root_name, current_definition, use)
        if scope is None:
            return [], False, None
        paths = scope_stored_values.get(id(scope), {}).get(root_name, {})
        selected: list[tuple[ast.AST, bool, ast.AST]] = []
        incomplete = False
        request_dynamic = any(item[0] == "dynamic" for item in requested_path)
        for path, records in sorted(paths.items()):
            path_dynamic = any(item[0] == "dynamic" for item in path)
            include = whole_owner or request_dynamic or path == requested_path
            if include:
                active, conditional = reaching_records(records, use)
                selected.extend(active)
                incomplete = incomplete or (
                    (conditional or path_dynamic) and not whole_owner
                )
            elif path_dynamic:
                # A dynamic write could overlap an exact lookup.  Preserve
                # incompleteness without attributing its callable to every
                # unrelated exact key.
                active, _conditional = reaching_records(records, use)
                incomplete = incomplete or bool(active)
        return selected, incomplete, scope

    def resolve_storage_values(
        reference: tuple[str, tuple[tuple[str, str], ...]],
        current_definition: (
            ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef
        ),
        current_owner: ast.ClassDef | None,
        use: ast.AST,
        seen: frozenset[tuple[str, int]],
        *,
        whole_owner: bool = False,
    ) -> tuple[
        list[tuple[str, ast.AST, ast.ClassDef | None]], str, bool
    ]:
        records, incomplete, scope = storage_records(
            reference,
            current_definition,
            use,
            whole_owner=whole_owner,
        )
        if scope is None:
            return [], "not_local", False
        values: list[tuple[str, ast.AST, ast.ClassDef | None]] = []
        status = "incomplete" if incomplete else "complete"
        key = (f"storage:{reference[0]}:{reference[1]}", id(scope))
        if key in seen:
            return [], "incomplete", True
        for stored, _conditional, _event in records:
            resolved, stored_status = resolve_value(
                stored,
                current_definition,
                current_owner,
                seen | {key},
            )
            if stored_status == "not_local":
                if isinstance(stored, ast.Name):
                    stored_status = "incomplete"
                else:
                    resolved = [("opaque", stored, None)]
                    stored_status = "complete"
            values.extend(resolved)
            status = merge_status(status, stored_status)
        return deduplicate_values(values), status, True

    def resolve_returns(
        target: ast.FunctionDef | ast.AsyncFunctionDef,
        target_owner: ast.ClassDef | None,
        seen: frozenset[tuple[str, int]],
    ) -> tuple[list[tuple[str, ast.AST, ast.ClassDef | None]], str]:
        key = ("return", id(target))
        if key in seen:
            return [], "incomplete"
        returns = [
            node
            for node in ast.walk(target)
            if isinstance(node, ast.Return)
            and _nearest_function_owner(node, parents) is target
        ]
        if not returns:
            return [], "incomplete"
        values: list[tuple[str, ast.AST, ast.ClassDef | None]] = []
        status = "complete"
        for returned in returns:
            resolved, returned_status = resolve_value(
                returned.value,
                target,
                target_owner,
                seen | {key},
            )
            values.extend(resolved)
            status = merge_status(status, returned_status)
            if _control_flow_between(returned, target, parents):
                status = "incomplete"
        if len(returns) > 1:
            status = "incomplete"
        return deduplicate_values(values), status

    def resolve_name(
        name: str,
        current_definition: (
            ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef
        ),
        current_owner: ast.ClassDef | None,
        use: ast.AST,
        seen: frozenset[tuple[str, int]],
    ) -> tuple[list[tuple[str, ast.AST, ast.ClassDef | None]], str]:
        comprehension_binding = visible_comprehension_binding(name, use)
        if comprehension_binding is not None:
            key = (
                f"comprehension:{name}",
                id(comprehension_binding["event"]),
            )
            if key in seen:
                return [], "incomplete"
            sources, source_status, _order = iteration_target_sources(
                comprehension_binding["source"],
                comprehension_binding["target"],
                name,
                current_definition,
                use,
                seen | {key},
            )
            return resolve_source_values(
                sources,
                source_status,
                current_definition,
                current_owner,
                seen | {key},
            )

        for scope in resolution_scope_chain(current_definition, use):
            definitions = scope_definitions.get(id(scope), {}).get(name, [])
            assignments = scope_assignments.get(id(scope), {}).get(name, [])
            special_bindings = scope_special_bindings.get(id(scope), {}).get(
                name, []
            )
            is_parameter = name in parameter_names(scope)
            if (
                not definitions
                and not assignments
                and not special_bindings
                and not is_parameter
            ):
                continue
            key = (name, id(scope))
            if key in seen:
                return [], "incomplete"

            events: list[dict[str, Any]] = []
            for target, conditional, event in [*definitions, *assignments]:
                if not occurs_before(event, use):
                    continue
                events.append({
                    "event": event,
                    "conditional": bool(conditional)
                    and conditional_at_use(event, use),
                    "sources": [target],
                    "status": "complete",
                    "definition": isinstance(
                        target,
                        (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
                    ),
                })
            for record in special_bindings:
                resolved_event = special_binding_event(
                    record, name, scope, use, seen | {key}
                )
                if resolved_event is not None:
                    resolved_event["definition"] = False
                    events.append(resolved_event)
            events.sort(
                key=lambda item: (
                    *_node_position(item["event"]),
                    ast.dump(item["event"], include_attributes=False),
                )
            )

            values: list[tuple[str, ast.AST, ast.ClassDef | None]] = []
            status = "not_local"
            if is_parameter:
                binding = invocation_bindings.get(id(scope), {}).get(name)
                if binding is None:
                    status = "incomplete"
                else:
                    values.extend(binding[0])
                    status = binding[1]
            for event in events:
                event_sources = event["sources"]
                if event["definition"]:
                    target = event_sources[0]
                    resolved = [(
                        "class"
                        if isinstance(target, ast.ClassDef)
                        else "callable",
                        target,
                        None
                        if isinstance(target, ast.ClassDef)
                        else definition_class_owner(target),
                    )]
                    event_status = "complete"
                else:
                    resolved, event_status = resolve_source_values(
                        event_sources,
                        event["status"],
                        current_definition,
                        current_owner,
                        seen | {key},
                    )
                if event["conditional"]:
                    values.extend(resolved)
                    status = merge_status(status, event_status)
                    status = "incomplete"
                else:
                    values = list(resolved)
                    status = event_status
            if not events and not is_parameter:
                # The name is lexically local but no binding reaches this use.
                return [], "incomplete"
            if not values and status == "not_local":
                status = "incomplete"
            return deduplicate_values(values), status
        if name in module_functions:
            return [("callable", module_functions[name], None)], "complete"
        if name in module_classes:
            return [("class", module_classes[name], None)], "complete"
        if name in aliases or name in safe_global_names:
            return [("opaque", use, None)], "complete"
        return [], "not_local"

    def resolve_value(
        value: ast.AST | None,
        current_definition: (
            ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef
        ),
        current_owner: ast.ClassDef | None,
        seen: frozenset[tuple[str, int]] = frozenset(),
    ) -> tuple[list[tuple[str, ast.AST, ast.ClassDef | None]], str]:
        if value is None:
            return [], "incomplete"
        if isinstance(value, ast.Name):
            return resolve_name(
                value.id, current_definition, current_owner, value, seen
            )
        if isinstance(value, ast.NamedExpr):
            return resolve_value(
                value.value,
                current_definition,
                current_owner,
                seen,
            )
        if isinstance(value, (ast.Attribute, ast.Subscript)):
            storage = storage_reference(value)
            if storage is not None and storage[1]:
                stored, stored_status, storage_known = resolve_storage_values(
                    storage,
                    current_definition,
                    current_owner,
                    value,
                    seen,
                )
                if stored:
                    return stored, stored_status
                if storage_known and stored_status == "incomplete":
                    return [], "incomplete"
                if storage_known and isinstance(value, ast.Subscript):
                    return [("opaque_attribute", value, None)], "complete"
        if isinstance(value, ast.Attribute):
            if (
                isinstance(value.value, ast.Name)
                and value.value.id in {"self", "cls"}
                and current_owner is not None
            ):
                method, method_owner, method_incomplete = _resolve_imported_method(
                    {current_owner.name: current_owner},
                    current_owner.name,
                    value.attr,
                )
                if method is None:
                    return [("opaque_attribute", value, None)], "complete"
                return [(
                    "callable",
                    method,
                    current_owner if method_owner else current_owner,
                )], "incomplete" if method_incomplete else "complete"
            base_values, base_status = resolve_value(
                value.value, current_definition, current_owner, seen
            )
            if base_values and all(
                kind in {"opaque", "opaque_attribute"}
                for kind, _target, _target_owner in base_values
            ):
                return [("opaque_attribute", value, None)], "complete"
            methods: list[tuple[str, ast.AST, ast.ClassDef | None]] = []
            status = base_status
            for kind, target, _target_owner in base_values:
                if kind in {"opaque", "opaque_attribute"}:
                    methods.append(("opaque_attribute", value, None))
                    continue
                if kind not in {"class", "instance"} or not isinstance(
                    target, ast.ClassDef
                ):
                    status = "incomplete"
                    continue
                method, method_owner, method_incomplete = _resolve_imported_method(
                    {target.name: target}, target.name, value.attr
                )
                if method is None:
                    methods.append(("opaque_attribute", value, None))
                    continue
                methods.append(("callable", method, target))
                if method_incomplete or method_owner is None:
                    status = "incomplete"
            if methods:
                return deduplicate_values(methods), status
            if base_status == "not_local":
                return [("opaque_attribute", value, None)], "complete"
            return [], "incomplete"
        if isinstance(value, ast.Subscript):
            base_values, base_status = resolve_value(
                value.value, current_definition, current_owner, seen
            )
            if base_values and all(
                kind in {"opaque", "opaque_attribute"}
                for kind, _target, _target_owner in base_values
            ):
                return [("opaque_attribute", value, None)], "complete"
            if base_status == "not_local":
                return [("opaque_attribute", value, None)], "complete"
            return [], "incomplete"
        if isinstance(value, ast.Call):
            called_values, called_status = resolve_value(
                value.func, current_definition, current_owner, seen
            )
            results: list[tuple[str, ast.AST, ast.ClassDef | None]] = []
            status = called_status
            for kind, target, target_owner in called_values:
                if kind == "class" and isinstance(target, ast.ClassDef):
                    constructors, constructor_status = (
                        resolve_local_class_construction(
                            value,
                            target,
                            current_definition,
                            current_owner,
                        )
                    )
                    # The executable-call pass enqueues these exact targets;
                    # value resolution still performs argument binding so an
                    # instance carried through aliases retains constructor
                    # parameter provenance.
                    _ = constructors
                    status = merge_status(status, constructor_status)
                    results.append(("instance", target, None))
                elif kind == "callable" and isinstance(
                    target, (ast.FunctionDef, ast.AsyncFunctionDef)
                ):
                    status = merge_status(
                        status,
                        bind_invocation(
                            value,
                            target,
                            target_owner,
                            current_definition,
                            current_owner,
                        ),
                    )
                    returned, returned_status = resolve_returns(
                        target, target_owner, seen
                    )
                    results.extend(returned)
                    status = merge_status(status, returned_status)
                elif kind in {"opaque", "opaque_attribute"}:
                    results.append(("opaque", value, None))
                else:
                    status = "incomplete"
            if results:
                return deduplicate_values(results), status
            if called_status == "not_local":
                return [("opaque", value, None)], "complete"
            return [], "incomplete"
        if isinstance(value, ast.Lambda):
            return [], "incomplete"
        if isinstance(
            value,
            (
                ast.Constant,
                ast.List,
                ast.ListComp,
                ast.Set,
                ast.SetComp,
                ast.Dict,
                ast.DictComp,
                ast.Tuple,
                ast.GeneratorExp,
            ),
        ):
            return [("opaque", value, None)], "complete"
        return [], "not_local"

    def merge_invocation_binding(
        target: ast.FunctionDef | ast.AsyncFunctionDef,
        name: str,
        values: list[tuple[str, ast.AST, ast.ClassDef | None]],
        status: str,
    ) -> None:
        bindings = invocation_bindings.setdefault(id(target), {})
        previous = bindings.get(name)
        if previous is None:
            bindings[name] = (deduplicate_values(values), status)
            return
        merged_values = deduplicate_values([*previous[0], *values])
        merged_status = (
            "incomplete"
            if "incomplete" in {previous[1], status}
            else "complete"
        )
        bindings[name] = (merged_values, merged_status)

    def bounded_positional_values(value: ast.AST) -> list[ast.AST] | None:
        if not isinstance(value, (ast.List, ast.Tuple)):
            return None
        result: list[ast.AST] = []
        for item in value.elts:
            if isinstance(item, ast.Starred):
                expanded = bounded_positional_values(item.value)
                if expanded is None:
                    return None
                result.extend(expanded)
            else:
                result.append(item)
        return result

    def bounded_keyword_values(
        value: ast.AST,
    ) -> list[tuple[str, ast.AST]] | None:
        if not isinstance(value, ast.Dict):
            return None
        result: list[tuple[str, ast.AST]] = []
        for key, item in zip(value.keys, value.values):
            if key is None:
                expanded = bounded_keyword_values(item)
                if expanded is None:
                    return None
                result.extend(expanded)
            elif (
                isinstance(key, ast.Constant)
                and isinstance(key.value, str)
            ):
                result.append((key.value, item))
            else:
                return None
        return result

    def lexical_parent_function(
        target: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
        current: ast.AST = target
        while id(current) in parents:
            current = parents[id(current)]
            if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return current
        return None

    def bind_invocation(
        call: ast.Call,
        target: ast.FunctionDef | ast.AsyncFunctionDef,
        target_owner: ast.ClassDef | None,
        current_definition: (
            ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef
        ),
        current_owner: ast.ClassDef | None,
    ) -> str:
        index_scope_root(target)
        guard = (id(call), id(target))
        if guard in binding_in_progress:
            return "incomplete"
        binding_in_progress.add(guard)
        try:
            posonly = list(getattr(target.args, "posonlyargs", ()))
            positional = [*posonly, *target.args.args]
            kwonly = list(target.args.kwonlyargs)
            vararg = target.args.vararg
            kwarg = target.args.kwarg
            defaults: dict[str, ast.AST] = {}
            if target.args.defaults:
                for argument, default in zip(
                    positional[-len(target.args.defaults):],
                    target.args.defaults,
                ):
                    defaults[argument.arg] = default
            for argument, default in zip(kwonly, target.args.kw_defaults):
                if default is not None:
                    defaults[argument.arg] = default

            sources: dict[
                str,
                list[
                    tuple[
                        ast.AST,
                        ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
                        ast.ClassDef | None,
                    ]
                ],
            ] = {argument.arg: [] for argument in (*positional, *kwonly)}
            if vararg is not None:
                sources[vararg.arg] = []
            if kwarg is not None:
                sources[kwarg.arg] = []
            incomplete_names: set[str] = set()
            mapping_incomplete = False

            implicit = bool(target_owner is not None and positional)
            available_positional = positional[1:] if implicit else positional
            if implicit:
                merge_invocation_binding(target, positional[0].arg, [], "complete")

            positional_values: list[ast.AST] = []
            unbounded_positional: list[ast.AST] = []
            for argument in call.args:
                if isinstance(argument, ast.Starred):
                    expanded = bounded_positional_values(argument.value)
                    if expanded is None:
                        unbounded_positional.append(argument.value)
                    else:
                        positional_values.extend(expanded)
                else:
                    positional_values.append(argument)

            for index, argument in enumerate(positional_values):
                if index < len(available_positional):
                    sources[available_positional[index].arg].append((
                        argument, current_definition, current_owner
                    ))
                elif vararg is not None:
                    sources[vararg.arg].append((
                        argument, current_definition, current_owner
                    ))
                else:
                    mapping_incomplete = True
                    incomplete_names.update(item.arg for item in available_positional)

            keyword_items: list[tuple[str, ast.AST]] = []
            unbounded_keywords: list[ast.AST] = []
            for keyword in call.keywords:
                if keyword.arg is None:
                    expanded = bounded_keyword_values(keyword.value)
                    if expanded is None:
                        unbounded_keywords.append(keyword.value)
                    else:
                        keyword_items.extend(expanded)
                else:
                    keyword_items.append((keyword.arg, keyword.value))

            positional_names = {argument.arg for argument in positional}
            posonly_names = {argument.arg for argument in posonly}
            kwonly_names = {argument.arg for argument in kwonly}
            for name, argument in keyword_items:
                if name in posonly_names:
                    mapping_incomplete = True
                    incomplete_names.add(name)
                elif name in positional_names or name in kwonly_names:
                    if sources[name]:
                        mapping_incomplete = True
                        incomplete_names.add(name)
                    sources[name].append((
                        argument, current_definition, current_owner
                    ))
                elif kwarg is not None:
                    sources[kwarg.arg].append((
                        argument, current_definition, current_owner
                    ))
                else:
                    mapping_incomplete = True

            if unbounded_positional:
                mapping_incomplete = True
                affected = [argument.arg for argument in available_positional]
                if vararg is not None:
                    affected.append(vararg.arg)
                incomplete_names.update(affected)
                for argument in unbounded_positional:
                    destination_names = (
                        [vararg.arg]
                        if vararg is not None
                        else [item.arg for item in available_positional]
                    )
                    for name in destination_names:
                        sources[name].append((
                            argument, current_definition, current_owner
                        ))
            if unbounded_keywords:
                mapping_incomplete = True
                affected = [
                    argument.arg
                    for argument in (*target.args.args, *kwonly)
                ]
                if kwarg is not None:
                    affected.append(kwarg.arg)
                incomplete_names.update(affected)
                for argument in unbounded_keywords:
                    destination_names = (
                        [kwarg.arg]
                        if kwarg is not None
                        else affected
                    )
                    for name in destination_names:
                        sources[name].append((
                            argument, current_definition, current_owner
                        ))

            default_scope = lexical_parent_function(target) or target
            default_owner = definition_class_owner(default_scope)
            for argument in (*available_positional, *kwonly):
                if not sources[argument.arg]:
                    default = defaults.get(argument.arg)
                    if default is None:
                        incomplete_names.add(argument.arg)
                        mapping_incomplete = True
                    else:
                        sources[argument.arg].append((
                            default, default_scope, default_owner
                        ))

            for name in sorted(sources):
                values: list[tuple[str, ast.AST, ast.ClassDef | None]] = []
                status = "incomplete" if name in incomplete_names else "complete"
                for argument, argument_scope, argument_owner in sources[name]:
                    resolved, argument_status = resolve_value(
                        argument, argument_scope, argument_owner
                    )
                    if argument_status == "not_local":
                        if isinstance(argument, ast.Name):
                            argument_status = "incomplete"
                        else:
                            resolved = [("opaque", argument, None)]
                            argument_status = "complete"
                    values.extend(resolved)
                    status = merge_status(status, argument_status)
                merge_invocation_binding(
                    target, name, deduplicate_values(values), status
                )
            return "incomplete" if mapping_incomplete else "complete"
        finally:
            binding_in_progress.discard(guard)

    def resolve_local_class_construction(
        call: ast.Call,
        target: ast.ClassDef,
        current_definition: (
            ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef
        ),
        current_owner: ast.ClassDef | None,
    ) -> tuple[
        list[tuple[ast.FunctionDef | ast.AsyncFunctionDef, ast.ClassDef]],
        str,
    ]:
        """Resolve the bounded eager behavior of one exact local class call.

        Python class construction is not equivalent to invoking every method
        on the class.  A call reaches only the effective metaclass ``__call__``
        (when locally overridden) and the first ``__new__``/``__init__`` found
        in the class MRO.  This resolver therefore builds a bounded local C3
        MRO, rejects any external or dynamic construction input, and preserves
        only those constructor definitions as reached targets.
        """

        def evaluation_scope(
            class_node: ast.ClassDef,
        ) -> ast.FunctionDef | ast.AsyncFunctionDef:
            current: ast.AST = class_node
            while id(current) in parents:
                current = parents[id(current)]
                if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    return current
            return definition

        def evaluation_owner(class_node: ast.ClassDef) -> ast.ClassDef | None:
            current: ast.AST = class_node
            while id(current) in parents:
                current = parents[id(current)]
                if isinstance(current, ast.ClassDef):
                    return current
                if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    return None
            return None

        # Constructor lookup needs the class's complete lexical tree.  The
        # caller may be a different function (for example, module-level class
        # ``C`` constructed inside ``main``), so the caller-rooted ``parents``
        # map cannot decide whether a method binding is direct or conditional.
        # Build an effective class-dictionary environment in source order for
        # each class participating in construction instead.
        class_binding_cache: dict[int, dict[str, dict[str, Any]]] = {}

        def empty_class_binding() -> dict[str, Any]:
            return {
                "targets": [],
                "unknown": False,
                "absent": True,
                "incomplete": False,
            }

        def copy_class_binding(binding: dict[str, Any]) -> dict[str, Any]:
            return {
                "targets": list(binding["targets"]),
                "unknown": bool(binding["unknown"]),
                "absent": bool(binding["absent"]),
                "incomplete": bool(binding["incomplete"]),
            }

        def copy_class_environment(
            environment: dict[str, dict[str, Any]],
        ) -> dict[str, dict[str, Any]]:
            return {
                name: copy_class_binding(binding)
                for name, binding in environment.items()
            }

        def ordered_constructor_targets(
            targets: Iterable[ast.FunctionDef | ast.AsyncFunctionDef],
        ) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
            unique = {id(target): target for target in targets}
            return sorted(
                unique.values(),
                key=lambda item: (
                    getattr(item, "lineno", 0),
                    getattr(item, "col_offset", 0),
                    item.name,
                ),
            )

        def function_class_binding(
            function: ast.FunctionDef | ast.AsyncFunctionDef,
        ) -> dict[str, Any]:
            uncertain = bool(function.decorator_list) or isinstance(
                function, ast.AsyncFunctionDef
            )
            return {
                # A decorator can be the identity, so retain the raw function
                # as a possible target while failing closed on its result.
                "targets": [function],
                "unknown": uncertain,
                "absent": False,
                "incomplete": uncertain,
            }

        def merge_class_bindings(
            bindings: Iterable[dict[str, Any]],
            *,
            force_incomplete: bool,
        ) -> dict[str, Any]:
            values = list(bindings)
            if not values:
                return empty_class_binding()
            targets = ordered_constructor_targets(
                target
                for binding in values
                for target in binding["targets"]
            )
            return {
                "targets": targets,
                "unknown": any(binding["unknown"] for binding in values),
                "absent": any(binding["absent"] for binding in values),
                "incomplete": (
                    force_incomplete
                    or len(targets) > 1
                    or any(binding["incomplete"] for binding in values)
                ),
            }

        def class_binding_environment(
            class_node: ast.ClassDef,
        ) -> dict[str, dict[str, Any]]:
            cached = class_binding_cache.get(id(class_node))
            if cached is not None:
                return copy_class_environment(cached)

            class_parents = _ast_parent_map(class_node)

            def class_scoped(node: ast.AST) -> bool:
                current = node
                while id(current) in class_parents:
                    current = class_parents[id(current)]
                    if current is class_node:
                        return True
                    if isinstance(
                        current,
                        (
                            ast.FunctionDef,
                            ast.AsyncFunctionDef,
                            ast.Lambda,
                            ast.ClassDef,
                        ),
                    ):
                        return False
                return False

            def value_binding(
                value: ast.AST,
                environment: dict[str, dict[str, Any]],
            ) -> dict[str, Any]:
                if isinstance(value, ast.Name):
                    local = environment.get(value.id)
                    if local is not None:
                        result = copy_class_binding(local)
                        # Assignment itself definitely creates the target
                        # name, but a possibly absent source is unresolved.
                        result["unknown"] = (
                            result["unknown"] or result["absent"]
                        )
                        result["incomplete"] = (
                            result["incomplete"] or result["absent"]
                        )
                        result["absent"] = False
                        return result
                    module_function = module_functions.get(value.id)
                    if module_function is not None:
                        return function_class_binding(module_function)
                    resolved, resolved_status = resolve_value(
                        value,
                        evaluation_scope(class_node),
                        evaluation_owner(class_node),
                    )
                    callable_values = [
                        target
                        for kind, target, _target_owner in resolved
                        if kind == "callable"
                        and isinstance(
                            target,
                            (ast.FunctionDef, ast.AsyncFunctionDef),
                        )
                    ]
                    only_callables = bool(resolved) and len(
                        callable_values
                    ) == len(resolved)
                    if resolved_status == "complete" and only_callables:
                        bindings = [
                            function_class_binding(target)
                            for target in callable_values
                        ]
                        merged = merge_class_bindings(
                            bindings, force_incomplete=len(bindings) != 1
                        )
                        merged["absent"] = False
                        return merged
                    return {
                        "targets": ordered_constructor_targets(
                            callable_values
                        ),
                        "unknown": True,
                        "absent": False,
                        "incomplete": True,
                    }
                if isinstance(value, ast.IfExp):
                    alternatives = [
                        value_binding(value.body, environment),
                        value_binding(value.orelse, environment),
                    ]
                    merged = merge_class_bindings(
                        alternatives, force_incomplete=True
                    )
                    merged["unknown"] = (
                        merged["unknown"] or merged["absent"]
                    )
                    merged["absent"] = False
                    return merged
                # Descriptors, factories, lambdas, attributes, subscripts,
                # and arbitrary expressions need semantics beyond an exact
                # local function identity.  They shadow the MRO but remain
                # unresolved.
                return {
                    "targets": [],
                    "unknown": True,
                    "absent": False,
                    "incomplete": True,
                }

            def bind_target(
                environment: dict[str, dict[str, Any]],
                target: ast.AST,
                binding: dict[str, Any],
            ) -> set[str]:
                if isinstance(target, ast.Name):
                    environment[target.id] = copy_class_binding(binding)
                    return {target.id}
                names = bound_target_names(target)
                for name in names:
                    environment[name] = {
                        "targets": [],
                        "unknown": True,
                        "absent": False,
                        "incomplete": True,
                    }
                return names

            def delete_target(
                environment: dict[str, dict[str, Any]], target: ast.AST
            ) -> set[str]:
                names = bound_target_names(target)
                for name in names:
                    environment[name] = empty_class_binding()
                return names

            def unknown_target(
                environment: dict[str, dict[str, Any]], target: ast.AST
            ) -> set[str]:
                names = bound_target_names(target)
                for name in names:
                    previous = environment.get(name, empty_class_binding())
                    environment[name] = {
                        "targets": list(previous["targets"]),
                        "unknown": True,
                        "absent": False,
                        "incomplete": True,
                    }
                return names

            def merge_environments(
                base: dict[str, dict[str, Any]],
                branches: list[dict[str, dict[str, Any]]],
                touched: set[str],
            ) -> dict[str, dict[str, Any]]:
                result = copy_class_environment(base)
                for name in touched:
                    result[name] = merge_class_bindings(
                        [
                            branch.get(name, empty_class_binding())
                            for branch in branches
                        ],
                        force_incomplete=True,
                    )
                return result

            def preserve_nested_function_candidates(
                statement: ast.AST,
                environment: dict[str, dict[str, Any]],
                touched: set[str],
            ) -> None:
                candidates = sorted(
                    (
                        item
                        for item in ast.walk(statement)
                        if isinstance(
                            item,
                            (ast.FunctionDef, ast.AsyncFunctionDef),
                        )
                        and class_scoped(item)
                    ),
                    key=lambda item: (
                        getattr(item, "lineno", 0),
                        getattr(item, "col_offset", 0),
                        item.name,
                    ),
                )
                for candidate in candidates:
                    previous = environment.get(
                        candidate.name, empty_class_binding()
                    )
                    previous["targets"] = ordered_constructor_targets([
                        *previous["targets"],
                        candidate,
                    ])
                    previous["incomplete"] = True
                    environment[candidate.name] = previous
                    touched.add(candidate.name)

            def named_expression_bindings(
                statement: ast.AST,
            ) -> list[ast.NamedExpr]:
                found: list[ast.NamedExpr] = []
                todo = list(ast.iter_child_nodes(statement))
                while todo:
                    item = todo.pop(0)
                    if isinstance(
                        item,
                        (
                            ast.FunctionDef,
                            ast.AsyncFunctionDef,
                            ast.Lambda,
                            ast.ClassDef,
                        ),
                    ):
                        continue
                    if isinstance(item, ast.NamedExpr) and class_scoped(item):
                        found.append(item)
                    todo.extend(ast.iter_child_nodes(item))
                return sorted(found, key=_node_position)

            def process_statements(
                statements: list[ast.stmt],
                environment: dict[str, dict[str, Any]],
            ) -> tuple[dict[str, dict[str, Any]], set[str]]:
                result = copy_class_environment(environment)
                all_touched: set[str] = set()
                for statement in statements:
                    before = copy_class_environment(result)
                    touched: set[str] = set()
                    if isinstance(
                        statement,
                        (ast.FunctionDef, ast.AsyncFunctionDef),
                    ):
                        result[statement.name] = function_class_binding(
                            statement
                        )
                        touched.add(statement.name)
                    elif isinstance(statement, ast.ClassDef):
                        result[statement.name] = {
                            "targets": [],
                            "unknown": True,
                            "absent": False,
                            "incomplete": True,
                        }
                        touched.add(statement.name)
                    elif isinstance(statement, ast.Assign):
                        binding = value_binding(statement.value, result)
                        for target in statement.targets:
                            touched.update(
                                bind_target(result, target, binding)
                            )
                    elif isinstance(statement, ast.AnnAssign):
                        if statement.value is not None:
                            touched.update(bind_target(
                                result,
                                statement.target,
                                value_binding(statement.value, result),
                            ))
                    elif isinstance(statement, ast.AugAssign):
                        touched.update(unknown_target(result, statement.target))
                    elif isinstance(statement, (ast.Import, ast.ImportFrom)):
                        for alias in statement.names:
                            name = alias.asname or alias.name.split(".", 1)[0]
                            result[name] = {
                                "targets": [],
                                "unknown": True,
                                "absent": False,
                                "incomplete": True,
                            }
                            touched.add(name)
                    elif isinstance(statement, ast.Delete):
                        for target in statement.targets:
                            touched.update(delete_target(result, target))
                    elif isinstance(statement, ast.If):
                        if isinstance(statement.test, ast.Constant) and isinstance(
                            statement.test.value, bool
                        ):
                            selected = (
                                statement.body
                                if statement.test.value
                                else statement.orelse
                            )
                            result, touched = process_statements(
                                selected, result
                            )
                        else:
                            body, body_touched = process_statements(
                                statement.body, result
                            )
                            alternate, alternate_touched = process_statements(
                                statement.orelse, result
                            )
                            touched = body_touched | alternate_touched
                            result = merge_environments(
                                before, [body, alternate], touched
                            )
                            preserve_nested_function_candidates(
                                statement, result, touched
                            )
                    elif isinstance(statement, (ast.For, ast.AsyncFor)):
                        iteration = copy_class_environment(result)
                        target_touched = unknown_target(
                            iteration, statement.target
                        )
                        body, body_touched = process_statements(
                            statement.body, iteration
                        )
                        body_else, body_else_touched = process_statements(
                            statement.orelse, body
                        )
                        zero_else, zero_else_touched = process_statements(
                            statement.orelse, result
                        )
                        touched = (
                            target_touched
                            | body_touched
                            | body_else_touched
                            | zero_else_touched
                        )
                        result = merge_environments(
                            before, [body, body_else, zero_else], touched
                        )
                        preserve_nested_function_candidates(
                            statement, result, touched
                        )
                    elif isinstance(statement, ast.While):
                        body, body_touched = process_statements(
                            statement.body, result
                        )
                        body_else, body_else_touched = process_statements(
                            statement.orelse, body
                        )
                        zero_else, zero_else_touched = process_statements(
                            statement.orelse, result
                        )
                        touched = (
                            body_touched
                            | body_else_touched
                            | zero_else_touched
                        )
                        result = merge_environments(
                            before, [body, body_else, zero_else], touched
                        )
                        preserve_nested_function_candidates(
                            statement, result, touched
                        )
                    elif isinstance(statement, (ast.With, ast.AsyncWith)):
                        entered = copy_class_environment(result)
                        for item in statement.items:
                            if item.optional_vars is not None:
                                touched.update(
                                    unknown_target(entered, item.optional_vars)
                                )
                        body, body_touched = process_statements(
                            statement.body, entered
                        )
                        touched.update(body_touched)
                        # ``__exit__`` may suppress a failure before a later
                        # body binding, so retain the pre-With possibility.
                        result = merge_environments(
                            before, [before, body], touched
                        )
                        preserve_nested_function_candidates(
                            statement, result, touched
                        )
                    elif isinstance(statement, ast.Try):
                        body, body_touched = process_statements(
                            statement.body, result
                        )
                        body_else, body_else_touched = process_statements(
                            statement.orelse, body
                        )
                        branches = [before, body, body_else]
                        touched = body_touched | body_else_touched
                        for handler in statement.handlers:
                            handled = copy_class_environment(before)
                            handler_touched: set[str] = set()
                            if handler.name:
                                target = ast.copy_location(
                                    ast.Name(id=handler.name, ctx=ast.Store()),
                                    handler,
                                )
                                handler_touched.update(
                                    unknown_target(handled, target)
                                )
                            handled, nested_touched = process_statements(
                                handler.body, handled
                            )
                            handler_touched.update(nested_touched)
                            if handler.name:
                                target = ast.copy_location(
                                    ast.Name(id=handler.name, ctx=ast.Del()),
                                    handler,
                                )
                                handler_touched.update(
                                    delete_target(handled, target)
                                )
                            touched.update(handler_touched)
                            branches.append(handled)
                        result = merge_environments(before, branches, touched)
                        if statement.finalbody:
                            result, final_touched = process_statements(
                                statement.finalbody, result
                            )
                            touched.update(final_touched)
                        preserve_nested_function_candidates(
                            statement, result, touched
                        )
                        for name in touched:
                            result[name]["incomplete"] = True
                    elif hasattr(ast, "Match") and isinstance(
                        statement, getattr(ast, "Match")
                    ):
                        branches = [before]
                        for case in statement.cases:
                            branch = copy_class_environment(before)
                            capture_names: set[str] = set()
                            for pattern in ast.walk(case.pattern):
                                if type(pattern).__name__.startswith("Match"):
                                    name = getattr(pattern, "name", None)
                                    rest = getattr(pattern, "rest", None)
                                    if isinstance(name, str):
                                        capture_names.add(name)
                                    if isinstance(rest, str):
                                        capture_names.add(rest)
                            for name in capture_names:
                                target = ast.copy_location(
                                    ast.Name(id=name, ctx=ast.Store()),
                                    case.pattern,
                                )
                                touched.update(unknown_target(branch, target))
                            branch, case_touched = process_statements(
                                case.body, branch
                            )
                            touched.update(case_touched)
                            branches.append(branch)
                        result = merge_environments(before, branches, touched)
                        preserve_nested_function_candidates(
                            statement, result, touched
                        )
                    elif isinstance(statement, (ast.Global, ast.Nonlocal)):
                        for name in statement.names:
                            result[name] = {
                                "targets": [],
                                "unknown": True,
                                "absent": True,
                                "incomplete": True,
                            }
                            touched.add(name)

                    # Assignment expressions and other expression-contained
                    # bindings are conditional with respect to short-circuit
                    # evaluation unless modeled as a direct statement above.
                    for named in named_expression_bindings(statement):
                        if not isinstance(named.target, ast.Name):
                            continue
                        name = named.target.id
                        alternative = value_binding(named.value, result)
                        result[name] = merge_class_bindings(
                            [
                                before.get(name, empty_class_binding()),
                                alternative,
                            ],
                            force_incomplete=True,
                        )
                        touched.add(name)
                    all_touched.update(touched)
                return result, all_touched

            environment, _touched = process_statements(
                class_node.body, {}
            )
            class_binding_cache[id(class_node)] = copy_class_environment(
                environment
            )
            return environment

        def direct_magic_definitions(
            class_node: ast.ClassDef, name: str
        ) -> tuple[
            list[ast.FunctionDef | ast.AsyncFunctionDef], bool, bool
        ]:
            binding = class_binding_environment(class_node).get(
                name, empty_class_binding()
            )
            incomplete = bool(
                binding["unknown"]
                or binding["incomplete"]
                or len(binding["targets"]) > 1
            )
            return (
                list(binding["targets"]),
                incomplete,
                bool(binding["absent"]),
            )

        mro_cache: dict[
            tuple[int, bool], tuple[list[ast.ClassDef], str]
        ] = {}

        def local_bases(
            class_node: ast.ClassDef,
            *,
            allow_type: bool,
        ) -> tuple[list[ast.ClassDef], str]:
            bases: list[ast.ClassDef] = []
            status = "complete"
            scope = evaluation_scope(class_node)
            owner = evaluation_owner(class_node)
            for base in class_node.bases:
                if isinstance(base, ast.Name) and base.id == "object":
                    continue
                if allow_type and isinstance(base, ast.Name) and base.id == "type":
                    continue
                if isinstance(base, ast.Name):
                    # Bases are captured when the ClassDef executes.  Resolve
                    # against the enclosing scope at that event, before the
                    # new class namespace exists and before any later rebinding.
                    values, base_status = resolve_name(
                        base.id, scope, owner, class_node, frozenset()
                    )
                else:
                    # Attribute/subscript/factory bases can change class
                    # identity dynamically and are deliberately fail closed.
                    values, base_status = [], "incomplete"
                local = sorted(
                    {
                        value
                        for kind, value, _value_owner in values
                        if kind == "class" and isinstance(value, ast.ClassDef)
                    },
                    key=lambda item: (
                        getattr(item, "lineno", 0),
                        getattr(item, "col_offset", 0),
                        item.name,
                    ),
                )
                if (
                    base_status != "complete"
                    or len(local) != 1
                    or any(kind != "class" for kind, _value, _owner in values)
                ):
                    status = "incomplete"
                if len(local) == 1:
                    bases.append(local[0])
            if len({id(base) for base in bases}) != len(bases):
                status = "incomplete"
            return bases, status

        def local_c3_mro(
            class_node: ast.ClassDef,
            *,
            allow_type: bool = False,
            stack: frozenset[int] = frozenset(),
        ) -> tuple[list[ast.ClassDef], str]:
            cache_key = (id(class_node), allow_type)
            if cache_key in mro_cache and id(class_node) not in stack:
                cached_mro, cached_status = mro_cache[cache_key]
                return list(cached_mro), cached_status
            if id(class_node) in stack:
                return [class_node], "incomplete"

            bases, status = local_bases(class_node, allow_type=allow_type)
            if class_node.decorator_list:
                status = "incomplete"
            if any(keyword.arg != "metaclass" for keyword in class_node.keywords):
                status = "incomplete"

            sequences: list[list[ast.ClassDef]] = []
            for base in bases:
                base_mro, base_status = local_c3_mro(
                    base,
                    allow_type=allow_type,
                    stack=stack | {id(class_node)},
                )
                sequences.append(list(base_mro))
                status = merge_status(status, base_status)
            sequences.append(list(bases))
            result = [class_node]
            while any(sequences):
                sequences = [sequence for sequence in sequences if sequence]
                candidate = next(
                    (
                        sequence[0]
                        for sequence in sequences
                        if all(
                            sequence[0] not in other[1:]
                            for other in sequences
                        )
                    ),
                    None,
                )
                if candidate is None:
                    status = "incomplete"
                    for sequence in sequences:
                        for item in sequence:
                            if item not in result:
                                result.append(item)
                    break
                result.append(candidate)
                for sequence in sequences:
                    if sequence and sequence[0] is candidate:
                        sequence.pop(0)
            mro_cache[cache_key] = (list(result), status)
            return result, status

        def explicit_metaclass(
            class_node: ast.ClassDef,
        ) -> tuple[ast.ClassDef | None, str, bool]:
            keywords = [
                keyword
                for keyword in class_node.keywords
                if keyword.arg == "metaclass"
            ]
            if not keywords:
                return None, "complete", False
            if len(keywords) != 1:
                return None, "incomplete", True
            value = keywords[0].value
            if isinstance(value, ast.Name) and value.id == "type":
                return None, "complete", True
            if isinstance(value, ast.Name):
                values, status = resolve_name(
                    value.id,
                    evaluation_scope(class_node),
                    evaluation_owner(class_node),
                    class_node,
                    frozenset(),
                )
            else:
                values, status = [], "incomplete"
            local = sorted(
                {
                    item
                    for kind, item, _item_owner in values
                    if kind == "class" and isinstance(item, ast.ClassDef)
                },
                key=lambda item: (
                    getattr(item, "lineno", 0),
                    getattr(item, "col_offset", 0),
                    item.name,
                ),
            )
            if (
                status != "complete"
                or len(local) != 1
                or any(kind != "class" for kind, _item, _owner in values)
            ):
                return local[0] if len(local) == 1 else None, "incomplete", True
            return local[0], "complete", True

        class_mro, status = local_c3_mro(target)
        metaclasses: list[ast.ClassDef] = []
        explicit_default_metaclass = False
        for class_node in class_mro:
            metaclass, metaclass_status, was_explicit = explicit_metaclass(class_node)
            status = merge_status(status, metaclass_status)
            if was_explicit and metaclass is None and metaclass_status == "complete":
                explicit_default_metaclass = True
            if metaclass is not None:
                metaclasses.append(metaclass)
        unique_metaclasses = list(dict.fromkeys(metaclasses))
        if len(unique_metaclasses) > 1 or (
            explicit_default_metaclass and unique_metaclasses
        ):
            status = "incomplete"

        targets: list[
            tuple[ast.FunctionDef | ast.AsyncFunctionDef, ast.ClassDef]
        ] = []

        def preserve_first_magic(
            mro: list[ast.ClassDef],
            name: str,
            dispatch_owner: ast.ClassDef,
        ) -> None:
            nonlocal status
            for class_node in mro:
                (
                    definitions,
                    definitions_incomplete,
                    may_be_absent,
                ) = direct_magic_definitions(class_node, name)
                if definitions_incomplete:
                    status = "incomplete"
                if definitions:
                    for constructor in definitions:
                        targets.append((constructor, dispatch_owner))
                        status = merge_status(
                            status,
                            bind_invocation(
                                call,
                                constructor,
                                dispatch_owner,
                                current_definition,
                                current_owner,
                            ),
                        )
                if not may_be_absent:
                    return

        if unique_metaclasses:
            metaclass_mro, metaclass_mro_status = local_c3_mro(
                unique_metaclasses[0], allow_type=True
            )
            status = merge_status(status, metaclass_mro_status)
            preserve_first_magic(
                metaclass_mro, "__call__", unique_metaclasses[0]
            )

        preserve_first_magic(class_mro, "__new__", target)
        preserve_first_magic(class_mro, "__init__", target)
        return list(dict.fromkeys(targets)), (
            "complete" if status == "complete" else "incomplete"
        )

    def resolve_call(
        call: ast.Call,
        current_definition: (
            ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef
        ),
        current_owner: ast.ClassDef | None,
        *,
        escape_provenance: bool = False,
    ) -> tuple[
        list[tuple[ast.FunctionDef | ast.AsyncFunctionDef, ast.ClassDef | None]],
        str,
    ]:
        values, status = resolve_value(
            call.func, current_definition, current_owner
        )
        targets: list[
            tuple[ast.FunctionDef | ast.AsyncFunctionDef, ast.ClassDef | None]
        ] = []
        saw_opaque = False
        saw_bound_opaque = False

        def proven_nonproject_opaque(target: ast.AST) -> bool:
            root = target
            while isinstance(root, (ast.Attribute, ast.Subscript)):
                root = root.value
            if not isinstance(root, ast.Name):
                return False
            if root.id in project_binding_names:
                return False
            if root.id not in aliases and root.id not in safe_global_names:
                return False
            resolved = _dotted_name(target, aliases)
            if not resolved:
                return False
            try:
                categories, unsupported = classify_call(call, resolved)
            except Exception:
                return False
            return not categories and not unsupported

        for kind, target, target_owner in values:
            if kind == "callable" and isinstance(
                target, (ast.FunctionDef, ast.AsyncFunctionDef)
            ):
                targets.append((target, target_owner))
                status = merge_status(
                    status,
                    bind_invocation(
                        call,
                        target,
                        target_owner,
                        current_definition,
                        current_owner,
                    ),
                )
            elif kind == "class" and isinstance(target, ast.ClassDef):
                constructors, constructor_status = (
                    resolve_local_class_construction(
                        call,
                        target,
                        current_definition,
                        current_owner,
                    )
                )
                targets.extend(constructors)
                status = merge_status(status, constructor_status)
            elif kind == "instance":
                status = "incomplete"
            elif kind in {"opaque", "opaque_attribute"}:
                saw_opaque = True
                saw_bound_opaque = saw_bound_opaque or (
                    target is not call.func
                    and not proven_nonproject_opaque(target)
                )
                if targets:
                    status = "incomplete"
        if status == "not_local":
            return [], "not_local"
        if isinstance(call.func, ast.Attribute) and not targets:
            return [], "not_local"
        if not targets and saw_opaque:
            return [], (
                "incomplete"
                if saw_bound_opaque and not escape_provenance
                else "not_local"
            )
        return list(dict.fromkeys(targets)), (
            "complete" if status == "complete" else "incomplete"
        )

    def callable_targets(
        values: list[tuple[str, ast.AST, ast.ClassDef | None]],
    ) -> list[
        tuple[ast.FunctionDef | ast.AsyncFunctionDef, ast.ClassDef | None]
    ]:
        targets = {
            (target, target_owner)
            for kind, target, target_owner in values
            if kind == "callable"
            and isinstance(target, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        return sorted(
            targets,
            key=lambda item: (
                getattr(item[0], "lineno", 0),
                getattr(item[0], "col_offset", 0),
                item[0].name,
                item[1].name if item[1] else "",
            ),
        )

    def escaped_callable_targets(
        value: ast.AST | None,
        current_definition: (
            ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef
        ),
        current_owner: ast.ClassDef | None,
        seen: frozenset[tuple[str, int]] = frozenset(),
        shadowed: frozenset[str] = frozenset(),
    ) -> tuple[
        list[tuple[ast.FunctionDef | ast.AsyncFunctionDef, ast.ClassDef | None]],
        str,
    ]:
        """Resolve local callables and completeness in an escaping value."""
        if value is None:
            return [], "complete"
        shadow_key = ",".join(sorted(shadowed))
        key = (f"escape:{shadow_key}", id(value))
        if key in seen:
            return [], "complete"
        next_seen = seen | {key}
        targets: list[
            tuple[ast.FunctionDef | ast.AsyncFunctionDef, ast.ClassDef | None]
        ] = []
        status = "complete"

        def collect(item: ast.AST | None, names: frozenset[str] = shadowed) -> None:
            nonlocal status
            nested_targets, nested_status = escaped_callable_targets(
                item,
                current_definition,
                current_owner,
                next_seen,
                names,
            )
            targets.extend(nested_targets)
            if nested_status == "incomplete":
                status = "incomplete"

        def target_names(target: ast.AST) -> set[str]:
            if isinstance(target, ast.Name):
                return {target.id}
            if isinstance(target, (ast.Tuple, ast.List)):
                names: set[str] = set()
                for item in target.elts:
                    names.update(target_names(item))
                return names
            if isinstance(target, ast.Starred):
                return target_names(target.value)
            return set()

        if isinstance(value, (ast.List, ast.Set, ast.Tuple)):
            for item in value.elts:
                collect(item)
            return callable_targets_from_targets(targets), status
        if isinstance(value, ast.Dict):
            for item in (*value.keys, *value.values):
                collect(item)
            return callable_targets_from_targets(targets), status
        if isinstance(
            value, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
        ):
            comprehension_shadowed = shadowed
            for generator in value.generators:
                collect(generator.iter, comprehension_shadowed)
                comprehension_shadowed = frozenset({
                    *comprehension_shadowed,
                    *target_names(generator.target),
                })
                for condition in generator.ifs:
                    collect(condition, comprehension_shadowed)
            if isinstance(value, ast.DictComp):
                collect(value.key, comprehension_shadowed)
                collect(value.value, comprehension_shadowed)
            else:
                collect(value.elt, comprehension_shadowed)
            return callable_targets_from_targets(targets), status
        if isinstance(value, ast.Starred):
            return escaped_callable_targets(
                value.value,
                current_definition,
                current_owner,
                next_seen,
                shadowed,
            )
        if isinstance(value, ast.IfExp):
            for item in (value.body, value.orelse):
                collect(item)
            return callable_targets_from_targets(targets), status
        if isinstance(value, ast.NamedExpr):
            return escaped_callable_targets(
                value.value,
                current_definition,
                current_owner,
                next_seen,
                shadowed,
            )
        if isinstance(value, ast.Lambda):
            lambda_shadowed = frozenset({
                *shadowed,
                *(argument.arg for argument in (
                    *getattr(value.args, "posonlyargs", ()),
                    *value.args.args,
                    *value.args.kwonlyargs,
                )),
                *(
                    (value.args.vararg.arg,)
                    if value.args.vararg is not None
                    else ()
                ),
                *(
                    (value.args.kwarg.arg,)
                    if value.args.kwarg is not None
                    else ()
                ),
            })
            for default in (*value.args.defaults, *value.args.kw_defaults):
                collect(default, shadowed)
            references = sorted(
                (
                    item for item in ast.walk(value.body)
                    if isinstance(item, (ast.Name, ast.Attribute))
                    and isinstance(getattr(item, "ctx", ast.Load()), ast.Load)
                    and not (
                        isinstance(item, ast.Name)
                        and item.id in lambda_shadowed
                    )
                ),
                key=lambda item: (
                    getattr(item, "lineno", 0),
                    getattr(item, "col_offset", 0),
                    ast.dump(item, include_attributes=False),
                ),
            )
            for reference in references:
                collect(reference, lambda_shadowed)
            return callable_targets_from_targets(targets), status

        if isinstance(value, ast.Name) and value.id in shadowed:
            return [], "complete"

        resolved, resolved_status = resolve_value(
            value, current_definition, current_owner
        )
        targets.extend(callable_targets(resolved))
        if resolved_status == "incomplete" and (
            not resolved
            or any(kind == "callable" for kind, _target, _owner in resolved)
        ):
            status = "incomplete"
        elif resolved_status == "not_local":
            locally_bound = isinstance(value, ast.Name) and any(
                value.id in scope_bound_names.get(id(scope), set())
                for scope in resolution_scope_chain(
                    current_definition, value
                )
            )
            if (
                isinstance(value, ast.Name)
                and value.id not in aliases
                and value.id not in safe_global_names
                and not locally_bound
            ):
                status = "incomplete"

        if isinstance(value, ast.Name):
            scope = storage_scope(value.id, current_definition, value)
            if scope is not None:
                binding_key = (f"escape-binding:{value.id}", id(scope))
                if binding_key not in next_seen:
                    assignments = scope_assignments.get(id(scope), {}).get(
                        value.id, []
                    )
                    active, conditional = reaching_records(assignments, value)
                    binding_seen = next_seen | {binding_key}
                    for assigned, _conditional, _event in active:
                        nested_targets, nested_status = escaped_callable_targets(
                            assigned,
                            scope,
                            definition_class_owner(scope),
                            binding_seen,
                            shadowed,
                        )
                        targets.extend(nested_targets)
                        if nested_status == "incomplete":
                            status = "incomplete"
                    stored, stored_incomplete, _stored_scope = storage_records(
                        (value.id, ()),
                        current_definition,
                        value,
                        whole_owner=True,
                    )
                    if stored_incomplete:
                        status = "incomplete"
                    for assigned, _conditional, _event in stored:
                        nested_targets, nested_status = escaped_callable_targets(
                            assigned,
                            scope,
                            definition_class_owner(scope),
                            binding_seen,
                            shadowed,
                        )
                        targets.extend(nested_targets)
                        if nested_status == "incomplete":
                            status = "incomplete"
        elif isinstance(value, (ast.Attribute, ast.Subscript)):
            reference = storage_reference(value)
            if reference is not None:
                stored, stored_incomplete, scope = storage_records(
                    reference, current_definition, value
                )
                if stored_incomplete:
                    status = "incomplete"
                if scope is not None:
                    binding_seen = next_seen | {
                        (f"escape-storage:{reference}", id(scope))
                    }
                    for assigned, _conditional, _event in stored:
                        nested_targets, nested_status = escaped_callable_targets(
                            assigned,
                            scope,
                            definition_class_owner(scope),
                            binding_seen,
                            shadowed,
                        )
                        targets.extend(nested_targets)
                        if nested_status == "incomplete":
                            status = "incomplete"
        return callable_targets_from_targets(targets), status

    def callable_targets_from_targets(
        targets: list[
            tuple[ast.FunctionDef | ast.AsyncFunctionDef, ast.ClassDef | None]
        ],
    ) -> list[
        tuple[ast.FunctionDef | ast.AsyncFunctionDef, ast.ClassDef | None]
    ]:
        return sorted(
            set(targets),
            key=lambda item: (
                getattr(item[0], "lineno", 0),
                getattr(item[0], "col_offset", 0),
                item[0].name,
                item[1].name if item[1] else "",
            ),
        )

    def enqueue_definition(
        target: ast.FunctionDef | ast.AsyncFunctionDef,
        target_owner: ast.ClassDef | None,
        state: str,
        *,
        escaped: bool = False,
        escape_provenance: bool = False,
    ) -> None:
        index_scope_root(target)
        if escaped:
            escape_provenance = True
            positional = [
                *getattr(target.args, "posonlyargs", ()),
                *target.args.args,
            ]
            defaults: dict[str, ast.AST] = {}
            if target.args.defaults:
                for argument, default in zip(
                    positional[-len(target.args.defaults):],
                    target.args.defaults,
                ):
                    defaults[argument.arg] = default
            for argument, default in zip(
                target.args.kwonlyargs, target.args.kw_defaults
            ):
                if default is not None:
                    defaults[argument.arg] = default
            default_scope = lexical_parent_function(target) or target
            default_owner = definition_class_owner(default_scope)
            for name in sorted(parameter_names(target)):
                values: list[tuple[str, ast.AST, ast.ClassDef | None]] = []
                default = defaults.get(name)
                if default is not None:
                    values, _default_status = resolve_value(
                        default, default_scope, default_owner
                    )
                merge_invocation_binding(target, name, values, "incomplete")
        signature = binding_signature(target)
        target_id = id(target)
        if state == "unknown" and (
            target_id, "reached", signature, escape_provenance
        ) in visited_definitions:
            return
        key = (target_id, state, signature, escape_provenance)
        if key in queued_definitions:
            return
        queued_definitions.add(key)
        queue.append((
            target,
            target_owner,
            state,
            signature,
            escape_provenance,
        ))

    def add_nodes(candidates: list[ast.AST], state: str) -> None:
        for candidate in candidates:
            if id(candidate) not in added:
                added.add(id(candidate))
                nodes.append(candidate)
            previous = node_states.get(id(candidate))
            if previous != "reached":
                node_states[id(candidate)] = (
                    "reached" if state == "reached" else previous or "unknown"
                )

    def enclosing_class(
        node: ast.AST,
        stop: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> ast.ClassDef | None:
        current = node
        while id(current) in parents:
            current = parents[id(current)]
            if isinstance(current, ast.ClassDef):
                return current
            if current is stop:
                return None
        return None

    def unresolved_escape_sink(
        call: ast.Call,
        current_definition: (
            ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef
        ),
    ) -> bool:
        current: ast.AST = call.func
        while isinstance(current, (ast.Attribute, ast.Subscript)):
            current = current.value
        while isinstance(current, ast.Call):
            current = current.func
            while isinstance(current, (ast.Attribute, ast.Subscript)):
                current = current.value
        if not isinstance(current, ast.Name):
            return False
        name = current.id
        if (
            name in aliases
            or name in safe_global_names
            or name in module_functions
            or name in module_classes
        ):
            return False
        if name.isupper():
            return False
        for scope in resolution_scope_chain(current_definition, call):
            if (
                name in scope_definitions.get(id(scope), {})
                or name in scope_assignments.get(id(scope), {})
                or name in parameter_names(scope)
                or name in scope_bound_names.get(id(scope), set())
            ):
                return False
        return True

    enqueue_definition(definition, owner_class, "reached")

    while queue:
        (
            current_definition,
            current_owner,
            current_state,
            queued_signature,
            current_escape_provenance,
        ) = queue.pop(0)
        current_id = id(current_definition)
        queued_definitions.discard((
            current_id,
            current_state,
            queued_signature,
            current_escape_provenance,
        ))
        current_signature = binding_signature(current_definition)
        if current_state == "unknown" and (
            current_id,
            "reached",
            current_signature,
            current_escape_provenance,
        ) in visited_definitions:
            continue
        visit_key = (
            current_id,
            current_state,
            current_signature,
            current_escape_provenance,
        )
        if visit_key in visited_definitions:
            continue
        visited_definitions.add(visit_key)
        previous_definition_state = definition_states.get(current_id)
        if previous_definition_state != "reached":
            definition_states[current_id] = (
                "reached"
                if current_state == "reached"
                else previous_definition_state or "unknown"
            )
        eager_nodes = _eager_execution_nodes(
            current_definition,
            annotations_eager=(
                aliases.get("annotations") != "__future__.annotations"
            ),
        )
        add_nodes(eager_nodes, current_state)

        for node in eager_nodes:
            if isinstance(node, (ast.Return, ast.Yield, ast.YieldFrom)):
                escaped_targets, escape_status = escaped_callable_targets(
                    node.value, current_definition, current_owner
                )
                if escape_status == "incomplete" and current_escape_provenance:
                    resolution_incomplete = True
                for target, target_owner in escaped_targets:
                    enqueue_definition(
                        target, target_owner, "unknown", escaped=True
                    )
            if node is not current_definition and isinstance(
                node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
            ):
                decorator_owner = (
                    enclosing_class(node, current_definition) or current_owner
                )
                for decorator in node.decorator_list:
                    escaped_targets, escape_status = escaped_callable_targets(
                        decorator, current_definition, decorator_owner
                    )
                    if escape_status == "incomplete":
                        resolution_incomplete = True
                    for target, target_owner in escaped_targets:
                        enqueue_definition(
                            target, target_owner, "unknown", escaped=True
                        )
            if not isinstance(node, ast.Call):
                continue
            if call_is_proven_iteration_unreachable(
                node, current_definition
            ):
                call_resolutions[id(node)] = "complete"
                continue
            mutation_call_state = modeled_iterable_mutation_call(
                node, current_definition
            )
            if mutation_call_state == "modeled":
                # The mutation model consumes this local container operation;
                # its callable values are reached only through a later
                # iterable dispatch, not by storing them in the container.
                call_resolutions[id(node)] = "complete"
                continue
            if mutation_call_state == "incomplete":
                # A reached nested scope may mutate an iterable owned by an
                # outer scope.  Preserve any concrete callable argument via
                # the ordinary escape walk, but do not claim exact mutation
                # reconstruction across the call boundary.
                call_resolutions[id(node)] = "incomplete"
                resolution_incomplete = True
            call_owner = enclosing_class(node, current_definition)
            targets, resolution = resolve_call(
                node,
                current_definition,
                call_owner or current_owner,
                escape_provenance=current_escape_provenance,
            )
            previous_resolution = call_resolutions.get(id(node))
            if "incomplete" in {previous_resolution, resolution}:
                call_resolutions[id(node)] = "incomplete"
            elif "complete" in {previous_resolution, resolution}:
                call_resolutions[id(node)] = "complete"
            else:
                call_resolutions[id(node)] = resolution
            if resolution == "incomplete":
                resolution_incomplete = True
            if resolution != "complete":
                escaped_values = [*node.args, *(kw.value for kw in node.keywords)]
                for escaped_value in escaped_values:
                    escaped_targets, escape_status = escaped_callable_targets(
                        escaped_value,
                        current_definition,
                        call_owner or current_owner,
                    )
                    if escape_status == "incomplete" and unresolved_escape_sink(
                        node, current_definition
                    ):
                        resolution_incomplete = True
                    for target, target_owner in escaped_targets:
                        enqueue_definition(
                            target, target_owner, "unknown", escaped=True
                        )
            child_state = (
                "unknown"
                if current_state == "unknown"
                or _control_flow_between(node, current_definition, parents)
                or resolution == "incomplete"
                else "reached"
            )
            for target, target_owner in targets:
                enqueue_definition(
                    target,
                    target_owner,
                    child_state,
                    escape_provenance=current_escape_provenance,
                )

    return nodes, node_states, call_resolutions, resolution_incomplete


def _definition_execution_reachability(
    tree: ast.Module,
    reached_definitions: set[tuple[str | None, str]],
    unknown_definitions: set[tuple[str | None, str]],
) -> tuple[dict[tuple[int, int], str], bool]:
    """Map imports to reached/unknown execution through bounded local calls."""
    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    classes = {
        node.name: node for node in tree.body if isinstance(node, ast.ClassDef)
    }
    aliases = collect_aliases(tree)
    states: dict[tuple[int, int], str] = {}
    incomplete = False
    target_key = lambda item: (item[0] or "", item[1])
    targets = [
        (target, "reached")
        for target in sorted(reached_definitions, key=target_key)
    ] + [
        (target, "unknown")
        for target in sorted(unknown_definitions, key=target_key)
    ]
    for (class_name, definition_name), initial_state in targets:
        owner = class_name
        method_incomplete = False
        if class_name is None:
            definition = functions.get(definition_name)
        else:
            definition, owner, method_incomplete = _resolve_imported_method(
                classes, class_name, definition_name
            )
            incomplete = incomplete or method_incomplete
        if definition is None:
            incomplete = incomplete or class_name is None or method_incomplete
            continue
        nodes, node_states, _call_resolutions, local_incomplete = (
            _definition_execution_nodes(
                definition,
                aliases,
                classes.get(owner) if owner is not None else None,
                functions,
                classes,
            )
        )
        incomplete = incomplete or local_incomplete
        for node in nodes:
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            node_state = node_states.get(id(node), "unknown")
            state = (
                "unknown"
                if initial_state == "unknown" or node_state == "unknown"
                else "reached"
            )
            position = _node_position(node)
            if states.get(position) != "reached":
                states[position] = state
    return states, incomplete


def _definition_effect_findings(
    imported_tree: ast.Module,
    imported_path: str,
    importing_path: str,
    definition_targets: set[tuple[str | None, str]],
    project_dependencies: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], bool, bool]:
    functions = {
        node.name: node
        for node in imported_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    classes = {
        node.name: node for node in imported_tree.body if isinstance(node, ast.ClassDef)
    }
    aliases = collect_aliases(imported_tree)
    queue = sorted(definition_targets, key=lambda item: (item[0] or "", item[1]))
    visited: set[tuple[str | None, str]] = set()
    findings: list[dict[str, Any]] = []
    incomplete = False
    category_detector_failed = False
    dependency_positions = {
        (binding["line"], binding["column"])
        for binding in project_dependencies
    }
    while queue:
        class_name, definition_name = queue.pop(0)
        target = (class_name, definition_name)
        if target in visited:
            continue
        visited.add(target)
        owner = class_name
        if class_name is None:
            definition = functions.get(definition_name)
            if definition is None:
                incomplete = True
                continue
        else:
            definition, owner, method_incomplete = _resolve_imported_method(
                classes, class_name, definition_name
            )
            incomplete = incomplete or method_incomplete
            if definition is None:
                continue
        (
            effect_nodes,
            _node_states,
            local_call_resolutions,
            local_resolution_incomplete,
        ) = _definition_execution_nodes(
            definition,
            aliases,
            classes.get(owner) if owner is not None else None,
            functions,
            classes,
            {binding["local_name"] for binding in project_dependencies},
        )
        incomplete = incomplete or local_resolution_incomplete
        if any(
            isinstance(node, (ast.Import, ast.ImportFrom))
            and _node_position(node) in dependency_positions
            for node in effect_nodes
        ):
            # Import execution itself loads the deeper repository module.  The
            # one-hop detector must therefore fail closed even when no symbol
            # from that module is subsequently called by the reached definition.
            incomplete = True
        for node in effect_nodes:
            if not isinstance(node, ast.Call):
                continue
            resolved = _dotted_name(node.func, aliases) or "<unresolved>"
            try:
                categories, _unsupported = classify_call(node, resolved)
            except P541BR2Error:
                raise
            except Exception:
                category_detector_failed = True
                continue
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
                        operation=(
                            _db_operation(node, resolved)
                            if category == "database_access"
                            else None
                        ),
                    )
                )
            if any(
                _node_references_binding(node.func, binding, aliases)
                for binding in project_dependencies
            ):
                incomplete = True
            local_resolution = local_call_resolutions.get(id(node), "not_local")
            if local_resolution == "incomplete":
                incomplete = True
                continue
            if local_resolution == "complete":
                continue
            raw = (_dotted_name(node.func, {}) or "").replace("()", "")
            resolved_clean = resolved.replace("()", "")
            if raw in functions:
                queue.append((None, raw))
            elif resolved_clean in functions:
                queue.append((None, resolved_clean))
            if raw in classes:
                queue.append((raw, "__init__"))
            self_method = re.fullmatch(r"(?:self|cls)\.([A-Za-z_]\w*)", raw)
            if owner and self_method:
                queue.append((owner, self_method.group(1)))
            if owner and raw.startswith("super()."):
                method_name = raw[len("super()."):].split(".", 1)[0]
                local_bases = [
                    (_dotted_name(base, {}) or "").replace("()", "")
                    for base in classes[owner].bases
                ]
                matching_bases = [base for base in local_bases if base in classes]
                if matching_bases:
                    queue.append((matching_bases[0], method_name))
                else:
                    incomplete = True
            for candidate in {raw, resolved_clean}:
                match = re.fullmatch(r"([A-Za-z_]\w*)\.([A-Za-z_]\w*)", candidate)
                if match and match.group(1) in classes:
                    queue.append((match.group(1), match.group(2)))
    return findings, incomplete, category_detector_failed


def one_hop_transitive_evidence(
    source_path: str,
    raw: bytes,
    repo_root: Path,
    commit: str,
    *,
    resolution_cache: dict[tuple[Any, ...], tuple[str, str | None]] | None = None,
    blob_cache: dict[str, bytes] | None = None,
    analysis_cache: dict[tuple[str, str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    try:
        content = raw.decode("utf-8")
        tree = ast.parse(content, filename=source_path)
    except (UnicodeDecodeError, SyntaxError) as exc:
        return _evidence(
            "unknown",
            scope="transitive",
            reason=_failure_reason("imported_scan_incomplete"),
        )
    resolution_cache = resolution_cache if resolution_cache is not None else {}
    blob_cache = blob_cache if blob_cache is not None else {}
    analysis_cache = analysis_cache if analysis_cache is not None else {}
    findings: list[dict[str, Any]] = []
    unknown_reasons: list[str] = []
    (
        reached_definitions,
        unknown_definitions,
        known_definitions,
        module_dispatch_incomplete,
    ) = (
        _invoked_local_definition_reachability(tree)
    )
    primary_execution_states, primary_execution_incomplete = (
        _definition_execution_reachability(
            tree, reached_definitions, unknown_definitions
        )
    )
    primary_execution_incomplete = (
        primary_execution_incomplete or module_dispatch_incomplete
    )
    if primary_execution_incomplete:
        unknown_reasons.append(_failure_reason("import_resolution_incomplete"))
    for binding in _import_bindings(tree, source_path):
        try:
            lexical_state = _lexical_reachability(
                binding,
                reached_definitions,
                unknown_definitions,
                known_definitions,
                execution_states=primary_execution_states,
                execution_incomplete=primary_execution_incomplete,
            )
            resolved_path, _issue = _resolve_project_binding(
                repo_root, commit, binding, resolution_cache
            )
            if resolved_path == "external":
                continue
            if resolved_path == "unknown":
                unknown_reasons.append(_failure_reason("import_resolution_incomplete"))
                continue
            if lexical_state == "unknown":
                unknown_reasons.append(_failure_reason("import_resolution_incomplete"))
                continue
            if lexical_state == "unreachable":
                continue
            if resolved_path == source_path:  # One-hop cycle stops without recursion.
                continue
            entries = git_tree_entries(repo_root, commit, [resolved_path])
            entry = entries.get(resolved_path)
            if (
                not entry
                or entry["type"] != "blob"
                or entry["mode"] not in {"100644", "100755"}
            ):
                unknown_reasons.append(_failure_reason("imported_blob_invalid"))
                continue
            imported_raw = blob_cache.get(entry["blob_id"])
            if imported_raw is None:
                try:
                    imported_raw = git_blob(repo_root, entry["blob_id"])
                except GitUnavailableError:
                    raise
                except GitBlobReadError:
                    unknown_reasons.append(_failure_reason("git_blob_read_failed"))
                    continue
                blob_cache[entry["blob_id"]] = imported_raw
            analysis_key = (resolved_path, entry["blob_id"])
            imported = analysis_cache.get(analysis_key)
            if imported is None:
                try:
                    imported = analyze_source_bytes(
                        resolved_path,
                        imported_raw,
                        entry["blob_id"],
                        transitive_evidence=complete_transitive_absence(),
                    )
                except P541BR2Error:
                    raise
                except Exception:
                    unknown_reasons.append(_failure_reason("detector_failed"))
                    continue
                analysis_cache[analysis_key] = imported
            promoted, imported_evidence_incomplete = (
                _promote_imported_module_load_findings(
                    imported,
                    source_path,
                    resolved_path,
                    binding["line"],
                )
            )
            findings.extend(promoted)
            if imported["scan_status"] != "complete":
                unknown_reasons.append(_failure_reason("imported_scan_incomplete"))
                continue
            if imported_evidence_incomplete:
                unknown_reasons.append(_failure_reason("imported_scan_incomplete"))
            try:
                imported_tree = ast.parse(
                    imported_raw.decode("utf-8"), filename=resolved_path
                )
            except (UnicodeDecodeError, SyntaxError) as exc:
                unknown_reasons.append(_failure_reason("imported_scan_incomplete"))
            else:
                definition_targets, target_incomplete = _invoked_definition_targets(
                    tree, binding, imported_tree
                )
                (
                    module_reached,
                    module_unknown,
                    _module_known,
                    module_dispatch_incomplete,
                ) = (
                    _invoked_local_definition_reachability(imported_tree)
                )
                definition_targets.update(module_reached)
                definition_targets.update(module_unknown)
                target_incomplete = (
                    target_incomplete
                    or bool(module_unknown)
                    or module_dispatch_incomplete
                )
                if target_incomplete:
                    unknown_reasons.append(_failure_reason("import_resolution_incomplete"))
                dependencies = _project_dependency_bindings(
                    imported_tree,
                    resolved_path,
                    source_path,
                    repo_root,
                    commit,
                    resolution_cache,
                )
                if any(
                    binding.get("definition_target") is None
                    for binding in dependencies
                ):
                    # Module and class-body imports execute while the imported
                    # module loads.  A deeper repository import crosses the
                    # one-hop boundary regardless of whether its binding is used.
                    unknown_reasons.append(
                        _failure_reason("import_resolution_incomplete")
                    )
                if definition_targets:
                    (
                        definition_findings,
                        definition_incomplete,
                        definition_category_failed,
                    ) = (
                        _definition_effect_findings(
                            imported_tree,
                            resolved_path,
                            source_path,
                            definition_targets,
                            dependencies,
                        )
                    )
                    findings.extend(definition_findings)
                    if definition_incomplete:
                        unknown_reasons.append(
                            _failure_reason("import_resolution_incomplete")
                        )
                    if definition_category_failed:
                        unknown_reasons.append(
                            _failure_reason("category_detector_failed")
                        )
        except GitUnavailableError:
            raise
        except P541BR2Error:
            raise
        except Exception:
            unknown_reasons.append(_failure_reason("transitive_detector_failed"))
    deduplicated: dict[bytes, dict[str, Any]] = {}
    for finding in findings:
        try:
            key = canonical_bytes(finding)
        except P541BR2Error:
            unknown_reasons.append(_failure_reason("transitive_detector_failed"))
            continue
        deduplicated.setdefault(key, finding)
    findings = list(deduplicated.values())
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
    expected_runtime = {
        "implementation": CANONICAL_RUNTIME_IMPLEMENTATION,
        "version": CANONICAL_RUNTIME_VERSION,
        "requirement": (
            f"{CANONICAL_RUNTIME_IMPLEMENTATION}=={CANONICAL_RUNTIME_VERSION}"
        ),
        "verification": "PASS",
    }
    if artifact.get("runtime_contract") != expected_runtime:
        raise P541BR2Error("canonical runtime provenance mismatch")
    if (
        artifact.get("detector_contract", {}).get("canonical_generation_runtime")
        != expected_runtime["requirement"]
        or artifact.get("provenance", {}).get("generation_runtime")
        != expected_runtime
    ):
        raise P541BR2Error("canonical runtime contract mismatch")
    if (
        artifact.get("implementation_base_oid") != BASE_MAIN_COMMIT
        or artifact.get("frozen_source_commit") != FROZEN_SOURCE_COMMIT
    ):
        raise P541BR2Error("artifact top-level provenance mismatch")
    generator_raw = Path(__file__).read_bytes()
    generator = artifact.get("generator", {})
    if (
        generator.get("path") != GENERATOR_PATH
        or generator.get("byte_size") != len(generator_raw)
        or generator.get("sha256") != sha256_bytes(generator_raw)
    ):
        raise P541BR2Error("generator provenance mismatch")
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
        identity = record.get("source_identity", {})
        if (
            identity.get("source_path") != record.get("source_path")
            or identity.get("source_commit") != FROZEN_SOURCE_COMMIT
            or identity.get("git_blob_read_status") not in {"succeeded", "failed"}
            or identity.get("utf8_decoding_status")
            not in {"succeeded", "failed", "not_attempted"}
        ):
            raise P541BR2Error(f"source identity status mismatch: {record.get('source_path')}")
        scan = record.get("scan", {})
        if (
            scan.get("status") != record.get("scan_status")
            or scan.get("read_status") not in {"succeeded", "failed"}
            or scan.get("decode_status") not in {"succeeded", "failed", "not_attempted"}
            or scan.get("parse_status") not in {"succeeded", "failed", "not_attempted"}
        ):
            raise P541BR2Error(f"scan phase status mismatch: {record.get('source_path')}")
        phase_tuple = (
            scan["read_status"],
            scan["decode_status"],
            scan["parse_status"],
        )
        allowed_phase_tuples = {
            "complete": {("succeeded", "succeeded", "succeeded")},
            "syntax_error": {("succeeded", "succeeded", "failed")},
            "unreadable": {
                ("failed", "not_attempted", "not_attempted"),
                ("succeeded", "failed", "not_attempted"),
            },
            "unsupported": {("succeeded", "succeeded", "succeeded")},
        }
        if (
            phase_tuple not in allowed_phase_tuples[record["scan_status"]]
            or identity["git_blob_read_status"] != scan["read_status"]
            or identity["utf8_decoding_status"] != scan["decode_status"]
        ):
            raise P541BR2Error(
                f"impossible scan phase transition: {record.get('source_path')}"
            )
        if scan["read_status"] == "failed":
            if identity.get("byte_size") is not None or identity.get("sha256") is not None:
                raise P541BR2Error(
                    f"failed read published content identity: {record.get('source_path')}"
                )
        elif (
            not isinstance(identity.get("byte_size"), int)
            or identity["byte_size"] < 0
            or not isinstance(identity.get("sha256"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", identity["sha256"])
        ):
            raise P541BR2Error(
                f"successful read missing content identity: {record.get('source_path')}"
            )
        if record["scan_status"] == "complete":
            if (
                scan.get("complete") is not True
                or scan.get("error") is not None
                or {scan["read_status"], scan["decode_status"], scan["parse_status"]}
                != {"succeeded"}
            ):
                raise P541BR2Error(f"complete scan status mismatch: {record.get('source_path')}")
        else:
            error = scan.get("error", {})
            reason_code = error.get("code")
            reason = error.get("message")
            if (
                scan.get("complete") is not False
                or error.get("type") != record["scan_status"]
                or reason_code not in FAILURE_REASON_CODES
                or not _valid_bounded_failure_reason(reason)
                or "; " in reason
                or reason.split(":", 1)[0] != reason_code
            ):
                raise P541BR2Error(f"incomplete scan status mismatch: {record.get('source_path')}")
            expected_reason_codes = {
                "syntax_error": {"ast_parse_failed"},
                "unsupported": {
                    "category_detector_failed",
                    "detector_failed",
                    "transitive_detector_failed",
                    "unsupported_static_structure",
                },
                "unreadable": {
                    "git_blob_read_failed"
                    if scan["read_status"] == "failed"
                    else "utf8_decode_failed"
                },
            }
            if reason_code not in expected_reason_codes[record["scan_status"]]:
                raise P541BR2Error(
                    f"scan failure reason mismatch: {record.get('source_path')}"
                )
            expected_incomplete_safety = {
                "risk_level": "unknown",
                "low_risk_eligible": False,
                "disposition": "BLOCKED_UNKNOWN",
                "reasons": [reason],
            }
            if record.get("safety_classification") != expected_incomplete_safety:
                raise P541BR2Error(f"incomplete scan safety mismatch: {record.get('source_path')}")
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
            if (
                (item["state"] == "detected" and not item["findings"])
                or (item["state"] == "not_detected" and item["findings"])
            ):
                raise P541BR2Error(
                    f"evidence state/finding mismatch: {record.get('source_path')}"
                )
            if item["state"] != "unknown" and "reason" in item:
                raise P541BR2Error(
                    f"evidence reason/state mismatch: {record.get('source_path')}"
                )
            if item["state"] == "unknown":
                item_reason = item.get("reason")
                if not _valid_bounded_failure_reason(item_reason):
                    raise P541BR2Error(
                        f"unknown evidence reason mismatch: {record.get('source_path')}"
                    )
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
        safety = record.get("safety_classification", {})
        low_risk = safety.get("low_risk_eligible") is True
        if scan_complete and safety != classify_safety("complete", evidence):
            raise P541BR2Error(
                f"safety classification mismatch: {record.get('source_path')}"
            )
        if low_risk and (
            not scan_complete
            or any(evidence[key]["state"] != "not_detected" for key in RISK_EVIDENCE_KEYS)
        ):
            raise P541BR2Error(f"unsafe low-risk classification: {record.get('source_path')}")
        if not scan_complete and any(
            item["state"] == "not_detected" for item in evidence.values()
        ):
            raise P541BR2Error(f"incomplete scan published false absence: {record.get('source_path')}")
    manifest = artifact.get("provenance", {}).get("source_manifest", {})
    identities = [record["source_identity"] for record in records]
    digest = sha256_bytes(canonical_bytes(identities))
    if (
        manifest.get("record_count") != 580
        or manifest.get("canonical_sha256") != digest
        or manifest.get("verification") != "PASS"
        or manifest.get("ordered_entries") != identities
        or manifest.get("content_read_failures")
        != sum(identity["git_blob_read_status"] == "failed" for identity in identities)
    ):
        raise P541BR2Error("source manifest invariant mismatch")
    summary = artifact.get("summary", {})
    scan_counts = summary.get("scan_status_counts", {})
    if (
        summary.get("total_records") != 580
        or list(scan_counts) != list(SCAN_STATUS_TAXONOMY)
        or sum(scan_counts.values()) != 580
        or summary.get("complete_scans") != scan_counts["complete"]
        or summary.get("unknown_scans") != 580 - scan_counts["complete"]
    ):
        raise P541BR2Error("scan aggregate reconciliation mismatch")
    for key in ALL_EVIDENCE_KEYS:
        expected = Counter(record["evidence"][key]["state"] for record in records)
        published = summary.get("evidence_status_counts", {}).get(key, {})
        if (
            set(published) != set(TRI_STATES)
            or sum(published.values()) != 580
            or any(published[state] != expected.get(state, 0) for state in TRI_STATES)
        ):
            raise P541BR2Error(f"evidence aggregate reconciliation mismatch: {key}")
    expected_risks = Counter(
        record["safety_classification"]["risk_level"] for record in records
    )
    expected_dispositions = Counter(
        record["safety_classification"]["disposition"] for record in records
    )
    if summary.get("risk_level_counts") != dict(sorted(expected_risks.items())):
        raise P541BR2Error("risk aggregate reconciliation mismatch")
    if summary.get("disposition_counts") != dict(sorted(expected_dispositions.items())):
        raise P541BR2Error("disposition aggregate reconciliation mismatch")
    expected_direct_findings = sum(
        finding["direct_or_transitive"] == "direct"
        for record in records
        for item in record["evidence"].values()
        for finding in item["findings"]
    )
    expected_transitive_findings = sum(
        len(record["evidence"]["transitive_external_state"]["findings"])
        for record in records
    )
    if (
        summary.get("direct_finding_count") != expected_direct_findings
        or summary.get("transitive_finding_count") != expected_transitive_findings
    ):
        raise P541BR2Error("finding aggregate reconciliation mismatch")
    canonical_bytes(artifact)


def build_artifact(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    runtime_contract = require_canonical_runtime()
    historical, historical_provenance = verified_historical_inputs(repo_root)
    historical_records = historical["method_classification_records"]
    paths = [record["source_path"] for record in historical_records]
    entries = git_tree_entries(repo_root, FROZEN_SOURCE_COMMIT, paths)
    require_frozen_entries(paths, entries)

    records: list[dict[str, Any]] = []
    blob_cache: dict[str, bytes] = {}
    analysis_cache: dict[tuple[str, str], dict[str, Any]] = {}
    resolution_cache: dict[tuple[Any, ...], tuple[str, str | None]] = {}
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
        try:
            raw = git_blob(repo_root, entry["blob_id"])
        except GitUnavailableError:
            raise
        except GitBlobReadError:
            reason = _failure_reason("git_blob_read_failed")
            analysis = unknown_analysis(
                source_path,
                None,
                entry["blob_id"],
                reason,
                "unreadable",
                reason_code="git_blob_read_failed",
            )
            records.append(
                {
                    "method_id": historical_record["method_id"],
                    "source_path": source_path,
                    **analysis,
                    "historical_p541b_classification": _historical_context(historical_record),
                }
            )
            continue
        blob_cache[entry["blob_id"]] = raw
        transitive_failed = False
        try:
            transitive = one_hop_transitive_evidence(
                source_path,
                raw,
                repo_root,
                FROZEN_SOURCE_COMMIT,
                resolution_cache=resolution_cache,
                blob_cache=blob_cache,
                analysis_cache=analysis_cache,
            )
        except P541BR2Error:
            raise
        except Exception:
            transitive_failed = True
            transitive = _evidence(
                "unknown",
                scope="transitive",
                reason=_failure_reason("transitive_detector_failed"),
            )
        try:
            analysis = analyze_source_bytes(
                source_path,
                raw,
                entry["blob_id"],
                transitive_evidence=transitive,
            )
        except P541BR2Error:
            raise
        except Exception:
            reason = _failure_reason("detector_failed")
            analysis = unknown_analysis(
                source_path,
                raw,
                entry["blob_id"],
                reason,
                "unsupported",
                reason_code="detector_failed",
            )
        if transitive_failed and analysis["scan"]["complete"] is True:
            reason = _failure_reason("transitive_detector_failed")
            analysis = unknown_analysis(
                source_path,
                raw,
                entry["blob_id"],
                reason,
                "unsupported",
                reason_code="transitive_detector_failed",
                preserved_evidence=analysis["evidence"],
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
    evidence_counts = {}
    for key in ALL_EVIDENCE_KEYS:
        counts = Counter(record["evidence"][key]["state"] for record in records)
        evidence_counts[key] = {state: counts.get(state, 0) for state in sorted(TRI_STATES)}
    observed_scan_statuses = Counter(record["scan_status"] for record in records)
    scan_status_counts = {
        status: observed_scan_statuses.get(status, 0) for status in SCAN_STATUS_TAXONOMY
    }
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
        "runtime_contract": runtime_contract,
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
            "canonical_generation_runtime": runtime_contract["requirement"],
            "evidence_states": sorted(TRI_STATES),
            "scan_status_taxonomy": list(SCAN_STATUS_TAXONOMY),
            "failure_reason_codes": sorted(FAILURE_REASON_CODES),
            "failure_reason_policy": (
                "bounded deterministic codes only; exception text and private host paths are excluded"
            ),
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
                "Git blob-read failure",
                "UTF-8 decode failure",
                "AST parse failure",
                "detector exception",
                "category-detector exception",
                "incomplete alias resolution",
                "invoked deeper repository-local dependency beyond one-hop boundary",
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
            "one_hop_policy": (
                "module-load effects and effects reachable through invoked imported functions, "
                "classes, instance methods, same-module inheritance, and same-module helper calls "
                "are promoted; unresolved direct imports or invoked deeper repository dependencies "
                "are unknown; no source is imported, executed, or recursively scanned beyond one hop"
            ),
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
            "generation_runtime": runtime_contract,
            "historical_inputs": historical_provenance,
            "source_manifest": {
                "record_count": 580,
                "entry_fields": [
                    "source_path", "source_commit", "blob_id", "byte_size", "sha256",
                    "git_blob_read_status", "utf8_decoding_status",
                ],
                "entries_embedded_at": "method_classification_records[*].source_identity",
                "canonicalization": "UTF-8 compact sorted-key JSON in historical record order",
                "canonical_sha256": sha256_bytes(canonical_bytes(identities)),
                "ordered_entries": identities,
                "verification": "PASS",
                "content_read_failures": sum(
                    identity["git_blob_read_status"] == "failed" for identity in identities
                ),
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
            "Canonical artifact generation is pinned to CPython 3.9.6; other runtimes fail closed before source reads.",
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
        f"- Canonical generation runtime: `{artifact['runtime_contract']['requirement']}` — verification **{artifact['runtime_contract']['verification']}**.",
        "- Every evidence family publishes `state`, `scope`, `detector_id`, and deterministic `findings`.",
        "- Every finding publishes separate `resolved_api` and `resolved_syntax` fields plus `imported_module_path`; exactly one resolved field is populated.",
        "- States are exactly `detected`, `not_detected`, and `unknown`.",
        "- Scan-status taxonomy (ordered): `complete`, `syntax_error`, `unreadable`, `unsupported`.",
        "- Each record publishes truthful Git-read, UTF-8 decode, AST parse, and scan-completion statuses.",
        "- Recoverable per-file blob-read, decode, parse, detector, category-detector, unsupported-structure, and ambiguous one-hop failures retain the original manifest record as `unknown` and continue in original order.",
        "- Completed `detected` evidence is preserved when another detector category fails; an incomplete scan can never be low risk.",
        "- Failure reasons use bounded deterministic codes and exclude exception text and private host paths.",
        "- Repository/Git unavailability, baseline or frozen-manifest failure, duplicates, top-level invariants, and serialization failures remain terminal.",
        "- Only an exact top-level `__name__ == '__main__'` comparison is a valid guard; it mitigates import-time reachability only.",
        "",
        "## Detector Families",
        "",
        "- Direct and aliased database access, including DatabaseManager/db_manager and supported SQLAlchemy APIs.",
        "- Filesystem reads separated from filesystem writes, deletes, moves, and mutations.",
        "- Requests/urllib/http.client/httpx/aiohttp/socket network I/O and external URLs.",
        "- Direct and aliased subprocess/process-spawning APIs.",
        "- Hardcoded absolute, DB-like, draw/date, and external-service inputs.",
        "- Bounded one-hop project imports promote module-load effects and effects reachable through invoked functions, classes, instance methods, same-module inheritance, and helper calls; cycles stop and unresolved direct imports or invoked deeper project dependencies route to `unknown`.",
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
        f"- Recovered source blob-read failures: **{artifact['provenance']['source_manifest']['content_read_failures']}**",
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
