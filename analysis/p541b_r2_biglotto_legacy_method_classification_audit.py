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
import re
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]

TASK_ID = "P541B_R2_BIG_LOTTO_LEGACY_METHOD_CLASSIFICATION_AUDIT"
SCHEMA_VERSION = "p541b_r2_biglotto_legacy_method_classification_audit.v2"
DETECTOR_VERSION = "p541b_r2_static_effect_detector.v1"
BASE_MAIN_COMMIT = "c50137583243d4f9f4915a3e1d9babee50b5bbd7"
FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
GENERATED_AT_UTC = "2026-07-11T12:43:50Z"

HISTORICAL_JSON_PATH = (
    "outputs/research/p541b_biglotto_legacy_method_classification_audit_20260709.json"
)
HISTORICAL_MARKDOWN_PATH = (
    "outputs/research/p541b_biglotto_legacy_method_classification_audit_20260709.md"
)
HISTORICAL_INPUTS = {
    "json": {
        "path": HISTORICAL_JSON_PATH,
        "blob_id": "12f1595c96e3f9deddc7a7d2d9549c03144635f0",
        "byte_size": 1_120_976,
        "sha256": "4828e67b06fe43e8db661c4a96fdaf37e25cef500759f7825ad96eeea1971f35",
    },
    "markdown": {
        "path": HISTORICAL_MARKDOWN_PATH,
        "blob_id": "3b28e39bfe747c5f196b9aec6610284709466cf8",
        "byte_size": 14_737,
        "sha256": "a39131ba7d4536e39a07f36314870ba210e280d6d4c71e3046f82994733ed0a9",
    },
}

OUTPUT_JSON = Path(
    "outputs/research/p541b_r2_biglotto_legacy_method_classification_audit_20260711.json"
)
OUTPUT_MARKDOWN = Path(
    "outputs/research/p541b_r2_biglotto_legacy_method_classification_audit_20260711.md"
)

TRI_STATES = frozenset({"detected", "not_detected", "unknown"})
EFFECT_KEYS = (
    "database_access",
    "filesystem_write",
    "network_io",
    "subprocess_execution",
    "other_external_effect",
)
RISK_EVIDENCE_KEYS = EFFECT_KEYS + (
    "import_time_execution",
    "hardcoded_absolute_path",
    "hardcoded_draw_or_date",
)
ALL_EVIDENCE_KEYS = RISK_EVIDENCE_KEYS + (
    "valid_main_guard",
    "malformed_main_guard",
)

HARD_CODED_PATH_RE = re.compile(r"[\"'](?:/Users/|/home/|[A-Za-z]:\\\\)")
HARD_CODED_DRAW_RE = re.compile(r"\b11\d{7}\b")

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
    relative = Path(path)
    if (
        not isinstance(path, str)
        or not path
        or relative.is_absolute()
        or ".." in relative.parts
        or "\x00" in path
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
        if name == "json":
            payload = strict_json_bytes(raw)
    if payload is None:
        raise P541BR2Error("historical JSON was not loaded")
    records = payload.get("method_classification_records")
    if (
        payload.get("schema_version") != "1.0"
        or payload.get("task_id") != "P541B_BIG_LOTTO_LEGACY_METHOD_CLASSIFICATION_AUDIT"
        or not isinstance(records, list)
        or len(records) != 580
    ):
        raise P541BR2Error("historical P541B schema or record count mismatch")
    paths = [record.get("source_path") for record in records if isinstance(record, dict)]
    if len(paths) != 580 or any(not isinstance(path, str) for path in paths) or len(set(paths)) != 580:
        raise P541BR2Error("historical P541B source paths are incomplete or non-unique")
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


def _call_finding(call: ast.Call, resolved: str, scope: str) -> dict[str, Any]:
    return {
        "line": getattr(call, "lineno", None),
        "resolved_call": resolved,
        "scope": scope,
    }


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
    if leaf in FILESYSTEM_LEAF_CALLS:
        categories.add("filesystem_write")
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
        categories.add("subprocess_execution")

    if leaf in OTHER_EXTERNAL_CALLS or normalized in {
        "sys.exit", "os._exit", "importlib.import_module",
    }:
        categories.add("other_external_effect")
    if leaf in {"__import__", "eval", "exec", "compile"} or normalized == "importlib.import_module":
        unsupported.append(f"dynamic code/import at line {getattr(call, 'lineno', '?')}")
    return categories, unsupported


def _evidence(
    status: str,
    *,
    locations: Iterable[dict[str, Any]] = (),
    reason: str | None = None,
) -> dict[str, Any]:
    if status not in TRI_STATES:
        raise P541BR2Error(f"invalid evidence status: {status}")
    result: dict[str, Any] = {
        "status": status,
        "locations": list(locations)[:50],
        "detector_version": DETECTOR_VERSION,
    }
    if reason:
        result["reason"] = reason
    return result


def unknown_analysis(
    source_path: str,
    raw: bytes,
    blob_id: str,
    reason: str,
) -> dict[str, Any]:
    return {
        "source_identity": {
            "source_path": source_path,
            "source_commit": FROZEN_SOURCE_COMMIT,
            "blob_id": blob_id,
            "byte_size": len(raw),
            "sha256": sha256_bytes(raw),
        },
        "scan": {"status": "unknown", "complete": False, "reason": reason},
        "evidence": {
            key: _evidence("unknown", reason=reason) for key in ALL_EVIDENCE_KEYS
        },
        "safety_classification": {
            "risk_level": "unknown",
            "low_risk_eligible": False,
            "disposition": "BLOCKED_UNKNOWN",
            "reasons": [reason],
        },
    }


def analyze_source_bytes(source_path: str, raw: bytes, blob_id: str) -> dict[str, Any]:
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        return unknown_analysis(source_path, raw, blob_id, f"UTF-8 decode failure: {exc}")
    try:
        tree = ast.parse(content, filename=source_path)
    except SyntaxError as exc:
        return unknown_analysis(
            source_path,
            raw,
            blob_id,
            f"AST parse failure: {exc.msg} (line {exc.lineno})",
        )

    aliases = collect_aliases(tree)
    runtime_call_ids = {id(call) for call in import_time_calls(tree)}
    findings: dict[str, list[dict[str, Any]]] = {key: [] for key in EFFECT_KEYS}
    unsupported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and any(alias.name == "*" for alias in node.names):
            unsupported.append(f"star import at line {getattr(node, 'lineno', '?')}")
        if not isinstance(node, ast.Call):
            continue
        resolved = _dotted_name(node.func, aliases) or "<unresolved>"
        categories, call_unsupported = classify_call(node, resolved)
        unsupported.extend(call_unsupported)
        scope = "import_time" if id(node) in runtime_call_ids else "deferred"
        for category in categories:
            findings[category].append(_call_finding(node, resolved, scope))

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
    runtime_locations = [
        _call_finding(call, _dotted_name(call.func, aliases) or "<unresolved>", "import_time")
        for call in import_time_calls(tree)
    ]
    hardcoded_paths = [
        {"line": content.count("\n", 0, match.start()) + 1, "match": match.group(0)[:120]}
        for match in HARD_CODED_PATH_RE.finditer(content)
    ]
    hardcoded_draws = [
        {"line": content.count("\n", 0, match.start()) + 1, "match": match.group(0)}
        for match in HARD_CODED_DRAW_RE.finditer(content)
    ]

    if unsupported:
        reason = "; ".join(sorted(set(unsupported)))
        result = unknown_analysis(source_path, raw, blob_id, f"unsupported static structure: {reason}")
        # Preserve partial findings for diagnosis without presenting them as complete.
        for key, locations in findings.items():
            result["evidence"][key]["locations"] = locations[:50]
        return result

    evidence = {
        key: _evidence("detected" if locations else "not_detected", locations=locations)
        for key, locations in findings.items()
    }
    evidence["import_time_execution"] = _evidence(
        "detected" if runtime_locations else "not_detected",
        locations=runtime_locations,
    )
    evidence["hardcoded_absolute_path"] = _evidence(
        "detected" if hardcoded_paths else "not_detected",
        locations=hardcoded_paths,
    )
    evidence["hardcoded_draw_or_date"] = _evidence(
        "detected" if hardcoded_draws else "not_detected",
        locations=hardcoded_draws,
    )
    evidence["valid_main_guard"] = _evidence(
        "detected" if valid_guards else "not_detected",
        locations=[{"line": node.lineno} for node in valid_guards],
    )
    evidence["malformed_main_guard"] = _evidence(
        "detected" if malformed_guards else "not_detected",
        locations=[{"line": node.lineno} for node in malformed_guards],
    )

    detected_effects = [key for key in EFFECT_KEYS if evidence[key]["status"] == "detected"]
    detected_static_risks = [
        key
        for key in ("import_time_execution", "hardcoded_absolute_path", "hardcoded_draw_or_date")
        if evidence[key]["status"] == "detected"
    ]
    all_relevant_not_detected = all(
        evidence[key]["status"] == "not_detected" for key in RISK_EVIDENCE_KEYS
    )
    if detected_effects:
        risk_level = "high"
        disposition = "BLOCKED_EXTERNAL_EFFECT"
        reasons = detected_effects
    elif detected_static_risks:
        risk_level = "medium"
        disposition = "BLOCKED_STATIC_RISK"
        reasons = detected_static_risks
    elif all_relevant_not_detected:
        risk_level = "low"
        disposition = "STATIC_LOW_RISK_ELIGIBLE"
        reasons = []
    else:  # Defensive: complete scans must resolve every relevant category.
        raise P541BR2Error(f"incomplete tri-state resolution for {source_path}")

    return {
        "source_identity": {
            "source_path": source_path,
            "source_commit": FROZEN_SOURCE_COMMIT,
            "blob_id": blob_id,
            "byte_size": len(raw),
            "sha256": sha256_bytes(raw),
        },
        "scan": {
            "status": "complete",
            "complete": True,
            "encoding": "UTF-8",
            "parser": "python ast.parse",
        },
        "evidence": evidence,
        "safety_classification": {
            "risk_level": risk_level,
            "low_risk_eligible": all_relevant_not_detected,
            "disposition": disposition,
            "reasons": reasons,
        },
    }


def _historical_context(record: dict[str, Any]) -> dict[str, Any]:
    excluded = {"evidence", "source_path", "method_id"}
    return {key: value for key, value in record.items() if key not in excluded}


def validate_artifact(artifact: dict[str, Any]) -> None:
    if artifact.get("schema_version") != SCHEMA_VERSION or artifact.get("task_id") != TASK_ID:
        raise P541BR2Error("artifact identity mismatch")
    records = artifact.get("method_classification_records")
    if not isinstance(records, list) or len(records) != 580:
        raise P541BR2Error("artifact must contain exactly 580 records")
    paths = [record.get("source_path") for record in records]
    if len(set(paths)) != 580:
        raise P541BR2Error("artifact source paths are not unique")
    for record in records:
        evidence = record.get("evidence")
        if not isinstance(evidence, dict) or set(evidence) != set(ALL_EVIDENCE_KEYS):
            raise P541BR2Error(f"evidence schema mismatch: {record.get('source_path')}")
        statuses = {item.get("status") for item in evidence.values()}
        if not statuses <= TRI_STATES:
            raise P541BR2Error(f"invalid evidence state: {record.get('source_path')}")
        scan_complete = record.get("scan", {}).get("complete") is True
        low_risk = record.get("safety_classification", {}).get("low_risk_eligible") is True
        if low_risk and (
            not scan_complete
            or any(evidence[key]["status"] != "not_detected" for key in RISK_EVIDENCE_KEYS)
        ):
            raise P541BR2Error(f"unsafe low-risk classification: {record.get('source_path')}")
    manifest = artifact.get("provenance", {}).get("source_manifest", {})
    identities = [record["source_identity"] for record in records]
    digest = sha256_bytes(canonical_bytes(identities))
    if (
        manifest.get("record_count") != 580
        or manifest.get("canonical_sha256") != digest
        or manifest.get("verification") != "PASS"
    ):
        raise P541BR2Error("source manifest invariant mismatch")
    canonical_bytes(artifact)


def build_artifact(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    historical, historical_provenance = verified_historical_inputs(repo_root)
    historical_records = historical["method_classification_records"]
    paths = [record["source_path"] for record in historical_records]
    entries = git_tree_entries(repo_root, FROZEN_SOURCE_COMMIT, paths)
    if len(entries) != 580:
        missing = sorted(set(paths) - set(entries))
        raise P541BR2Error(f"frozen source corpus incomplete: {missing[:5]}")

    records: list[dict[str, Any]] = []
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
        analysis = analyze_source_bytes(source_path, raw, entry["blob_id"])
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
        key: dict(sorted(Counter(record["evidence"][key]["status"] for record in records).items()))
        for key in ALL_EVIDENCE_KEYS
    }
    identities = [record["source_identity"] for record in records]
    artifact = {
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "generated_at_utc": GENERATED_AT_UTC,
        "base_main_commit": BASE_MAIN_COMMIT,
        "frozen_source_commit": FROZEN_SOURCE_COMMIT,
        "supersedes": {
            "task_id": historical["task_id"],
            "schema_version": historical["schema_version"],
            "artifacts": [HISTORICAL_JSON_PATH, HISTORICAL_MARKDOWN_PATH],
            "overwrite_policy": "HISTORICAL_ARTIFACTS_PRESERVED",
        },
        "detector_contract": {
            "detector_version": DETECTOR_VERSION,
            "evidence_states": sorted(TRI_STATES),
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
        },
        "summary": {
            "total_records": len(records),
            "complete_scans": sum(record["scan"]["complete"] is True for record in records),
            "unknown_scans": sum(record["scan"]["complete"] is False for record in records),
            "risk_level_counts": dict(sorted(risk_counts.items())),
            "disposition_counts": dict(sorted(disposition_counts.items())),
            "evidence_status_counts": evidence_counts,
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
                "verification": "PASS",
            },
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
        "# P541B-R2 — BIG_LOTTO Legacy Method Evidence Remediation",
        "",
        f"> generated_at_utc: `{artifact['generated_at_utc']}`",
        "",
        "## Decision",
        "",
        "The historical Boolean safety evidence is superseded by a fail-closed, "
        "tri-state static evidence contract. Historical P541B artifacts remain unchanged.",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Frozen source records | {summary['total_records']} |",
        f"| Complete scans | {summary['complete_scans']} |",
        f"| Unknown scans | {summary['unknown_scans']} |",
    ]
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
        "## Detector Contract",
        "",
        "- Evidence states are exactly `detected`, `not_detected`, and `unknown`.",
        "- Decode failure, AST failure, star imports, dynamic code/imports, and dynamic file modes fail closed.",
        "- Main-guard recognition accepts only an exact top-level `__name__ == '__main__'` comparison (either operand order).",
        "- A valid main guard mitigates import-time execution only; effects inside guarded or deferred code remain detected.",
        "- DB, filesystem-write, network, subprocess, and other external-effect detection resolves supported aliases.",
        "- Low-risk eligibility requires a complete scan and every relevant evidence category explicitly `not_detected`.",
        "",
        "## Frozen Provenance",
        "",
        f"- Base main: `{artifact['base_main_commit']}`",
        f"- Frozen source commit: `{artifact['frozen_source_commit']}`",
        f"- Historical JSON blob: `{artifact['provenance']['historical_inputs']['json']['blob_id']}` — verification **PASS**",
        f"- Historical Markdown blob: `{artifact['provenance']['historical_inputs']['markdown']['blob_id']}` — verification **PASS**",
        f"- Frozen manifest: 580 Git blobs, canonical SHA-256 `{artifact['provenance']['source_manifest']['canonical_sha256']}` — verification **PASS**",
        "- Source discovery from the current working tree is prohibited.",
        "",
        "## Downstream Requirement",
        "",
        "PR #663 was not changed. A separately authorized replacement P541C task must consume this tri-state evidence, regenerate all derived counts and shortlist membership, and must never coerce `unknown` to `false`.",
        "",
        "## Limitations",
        "",
    ])
    lines.extend(f"- {item}" for item in artifact["limitations"])
    lines.extend(["", f"**Disclaimer:** {artifact['disclaimer']}", ""])
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
