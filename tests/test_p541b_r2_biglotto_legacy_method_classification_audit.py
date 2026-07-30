"""Focused synthetic and deterministic tests for the P541B-R2 evidence audit."""

from __future__ import annotations

import ast
import copy
import hashlib
import inspect
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
GENERATOR_PATH = (
    REPO_ROOT / "analysis/p541b_r2_biglotto_legacy_method_classification_audit.py"
)
PROTECTED_JSON_PATH = (
    REPO_ROOT
    / "outputs/research/p541b_r2_biglotto_legacy_method_classification_audit_20260711.json"
)
PROTECTED_MARKDOWN_PATH = (
    REPO_ROOT
    / "outputs/research/p541b_r2_biglotto_legacy_method_classification_audit_20260711.md"
)
PROTECTED_JSON_BYTE_SIZE = 10490289
PROTECTED_JSON_SHA256 = "6e1c84b899dbc0b8a662f54c378d0bb2c8812b53b0377447c9c7e94b52fda61e"
PROTECTED_MARKDOWN_BYTE_SIZE = 5579
PROTECTED_MARKDOWN_SHA256 = "af92cf54340def8bb4e36c548a149561ed449f67784bb4304bfb8e93bc1c55c8"
ALLOWED_SELF_IDENTITY_JSON_POINTERS = frozenset(
    {"/generator/byte_size", "/generator/sha256"}
)
GENERATOR_BLOCK_PATTERN = re.compile(
    rb"(?m)^  \"generator\": \{\n"
    rb"    \"path\": \"(?P<path>[^\"\r\n]+)\",\n"
    rb"    \"byte_size\": (?P<byte_size>0|[1-9][0-9]*),\n"
    rb"    \"sha256\": \"(?P<sha256>[^\"\r\n]*)\"\n"
    rb"  \},$"
)
MARKDOWN_GENERATOR_SHA_PATTERN = re.compile(
    rb"^- Generator SHA-256: `(?P<sha256>[^`\r\n]*)`$"
)
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _module():
    from analysis import p541b_r2_biglotto_legacy_method_classification_audit as mod

    return mod


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical_generator_path() -> Path:
    module_path = Path(_module().__file__).resolve()
    assert module_path == GENERATOR_PATH.resolve(), "canonical generator path mismatch"
    return module_path


def _generator_identity(generator_path: Path) -> dict[str, object]:
    raw = generator_path.read_bytes()
    digest = _sha256(raw)
    assert re.fullmatch(r"[0-9a-f]{64}", digest), "generator SHA-256 is not lowercase hex"
    return {"byte_size": len(raw), "sha256": digest}


def _assert_protected_artifact_pins(
    protected_json_raw: bytes, protected_markdown_raw: bytes
) -> None:
    assert len(protected_json_raw) == PROTECTED_JSON_BYTE_SIZE, (
        "protected JSON pin byte-size drift"
    )
    assert _sha256(protected_json_raw) == PROTECTED_JSON_SHA256, (
        "protected JSON pin SHA-256 drift"
    )
    assert len(protected_markdown_raw) == PROTECTED_MARKDOWN_BYTE_SIZE, (
        "protected Markdown pin byte-size drift"
    )
    assert _sha256(protected_markdown_raw) == PROTECTED_MARKDOWN_SHA256, (
        "protected Markdown pin SHA-256 drift"
    )


def _strict_json_load(raw: bytes):
    def reject_constant(value: str):
        raise AssertionError(f"non-finite JSON constant is forbidden: {value}")

    def reject_duplicate_keys(pairs):
        result = {}
        for key, value in pairs:
            assert key not in result, f"duplicate JSON key: {key}"
            result[key] = value
        return result

    try:
        text = raw.decode("utf-8")
        return json.loads(
            text,
            object_pairs_hook=reject_duplicate_keys,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AssertionError(f"strict JSON parse failed: {exc}") from exc


def _json_pointer_child(pointer: str, token) -> str:
    escaped = str(token).replace("~", "~0").replace("/", "~1")
    return f"{pointer}/{escaped}" if pointer else f"/{escaped}"


def _json_differences(protected, regenerated, pointer: str = "") -> list[dict[str, str]]:
    differences = []
    if type(protected) is not type(regenerated):
        return [{"pointer": pointer or "/", "kind": "type"}]
    if isinstance(protected, dict):
        protected_keys = list(protected)
        regenerated_keys = list(regenerated)
        if protected_keys != regenerated_keys:
            kind = "key_order" if set(protected_keys) == set(regenerated_keys) else "key_set"
            differences.append({"pointer": pointer or "/", "kind": kind})
        for key in protected_keys:
            if key in regenerated:
                differences.extend(
                    _json_differences(
                        protected[key],
                        regenerated[key],
                        _json_pointer_child(pointer, key),
                    )
                )
        return differences
    if isinstance(protected, list):
        if len(protected) != len(regenerated):
            differences.append({"pointer": pointer or "/", "kind": "list_length"})
        for index, (left, right) in enumerate(zip(protected, regenerated)):
            differences.extend(
                _json_differences(left, right, _json_pointer_child(pointer, index))
            )
        return differences
    if protected != regenerated:
        differences.append({"pointer": pointer or "/", "kind": "value"})
    return differences


def _generator_block_match(raw: bytes):
    matches = list(GENERATOR_BLOCK_PATTERN.finditer(raw))
    assert len(matches) == 1, "generator identity block must occur exactly once"
    return matches[0]


def _replace_captured_spans(raw: bytes, replacements) -> bytes:
    result = raw
    for start, end, value in sorted(replacements, reverse=True):
        result = result[:start] + value + result[end:]
    return result


def _expected_json_with_current_identity(
    protected_json_raw: bytes, identity: dict[str, object]
) -> bytes:
    match = _generator_block_match(protected_json_raw)
    assert match.group("path").decode("utf-8") == GENERATOR_PATH.relative_to(
        REPO_ROOT
    ).as_posix()
    return _replace_captured_spans(
        protected_json_raw,
        [
            (
                match.start("byte_size"),
                match.end("byte_size"),
                str(identity["byte_size"]).encode("ascii"),
            ),
            (
                match.start("sha256"),
                match.end("sha256"),
                str(identity["sha256"]).encode("ascii"),
            ),
        ],
    )


def _assert_json_self_identity_contract(
    regenerated_json_raw: bytes,
    *,
    generator_path: Path,
    protected_json_raw: bytes,
    protected_markdown_raw: bytes,
) -> None:
    _assert_protected_artifact_pins(protected_json_raw, protected_markdown_raw)
    identity = _generator_identity(generator_path)
    protected = _strict_json_load(protected_json_raw)
    regenerated = _strict_json_load(regenerated_json_raw)
    assert type(protected) is dict, "protected JSON root must be an object"
    assert type(regenerated) is dict, "regenerated JSON root must be an object"
    generator = regenerated.get("generator")
    assert type(generator) is dict, "regenerated /generator must be an object"
    assert "byte_size" in generator, "regenerated /generator/byte_size is missing"
    assert "sha256" in generator, "regenerated /generator/sha256 is missing"
    assert type(generator["byte_size"]) is int, (
        "regenerated /generator/byte_size must be an integer"
    )
    assert type(generator["sha256"]) is str, (
        "regenerated /generator/sha256 must be a string"
    )
    assert re.fullmatch(r"[0-9a-f]{64}", generator["sha256"]), (
        "regenerated /generator/sha256 must be 64-character lowercase hex"
    )
    assert generator["byte_size"] == identity["byte_size"], (
        "regenerated /generator/byte_size does not match generator bytes"
    )
    assert generator["sha256"] == identity["sha256"], (
        "regenerated /generator/sha256 does not match generator bytes"
    )
    differences = _json_differences(protected, regenerated)
    signature = {(item["pointer"], item["kind"]) for item in differences}
    expected_signature = {
        (pointer, "value") for pointer in ALLOWED_SELF_IDENTITY_JSON_POINTERS
    }
    assert len(differences) == 2 and signature == expected_signature, (
        f"closed JSON exception mismatch: {differences}"
    )
    expected_raw = _expected_json_with_current_identity(protected_json_raw, identity)
    assert regenerated_json_raw == expected_raw, (
        "JSON bytes differ outside the two exact self-identity scalar spans"
    )


def _line_ending(line: bytes) -> bytes:
    if line.endswith(b"\r\n"):
        return b"\r\n"
    if line.endswith(b"\n"):
        return b"\n"
    if line.endswith(b"\r"):
        return b"\r"
    return b""


def _markdown_generator_sha_candidates(raw: bytes):
    lines = raw.splitlines(keepends=True)
    candidates = []
    for index, line in enumerate(lines):
        ending = _line_ending(line)
        body = line[: -len(ending)] if ending else line
        match = MARKDOWN_GENERATOR_SHA_PATTERN.fullmatch(body)
        if match:
            candidates.append(
                {
                    "index": index,
                    "line": line,
                    "ending": ending,
                    "sha256": match.group("sha256"),
                }
            )
    return lines, candidates


def _expected_markdown_with_current_identity(
    protected_markdown_raw: bytes, identity: dict[str, object]
) -> bytes:
    lines, candidates = _markdown_generator_sha_candidates(protected_markdown_raw)
    assert len(candidates) == 1, (
        "protected Markdown must contain exactly one Generator SHA-256 line"
    )
    candidate = candidates[0]
    lines[candidate["index"]] = (
        b"- Generator SHA-256: `"
        + str(identity["sha256"]).encode("ascii")
        + b"`"
        + candidate["ending"]
    )
    return b"".join(lines)


def _assert_markdown_self_identity_contract(
    regenerated_markdown_raw: bytes,
    regenerated_json_raw: bytes,
    *,
    generator_path: Path,
    protected_json_raw: bytes,
    protected_markdown_raw: bytes,
) -> None:
    _assert_protected_artifact_pins(protected_json_raw, protected_markdown_raw)
    identity = _generator_identity(generator_path)
    regenerated_json = _strict_json_load(regenerated_json_raw)
    assert type(regenerated_json) is dict, "regenerated JSON root must be an object"
    generator = regenerated_json.get("generator")
    assert type(generator) is dict, "regenerated JSON /generator must be an object"
    json_sha256 = generator.get("sha256")
    assert type(json_sha256) is str, (
        "regenerated JSON /generator/sha256 must be a string"
    )
    assert re.fullmatch(r"[0-9a-f]{64}", json_sha256), (
        "regenerated JSON /generator/sha256 must be 64-character lowercase hex"
    )
    protected_lines, protected_candidates = _markdown_generator_sha_candidates(
        protected_markdown_raw
    )
    regenerated_lines, regenerated_candidates = _markdown_generator_sha_candidates(
        regenerated_markdown_raw
    )
    assert len(protected_candidates) == 1, (
        "protected Markdown must contain exactly one Generator SHA-256 line"
    )
    assert len(regenerated_candidates) == 1, (
        "regenerated Markdown must contain exactly one Generator SHA-256 line"
    )
    assert len(regenerated_lines) == len(protected_lines), (
        "Markdown line count differs from the protected artifact"
    )
    protected_candidate = protected_candidates[0]
    regenerated_candidate = regenerated_candidates[0]
    assert regenerated_candidate["index"] == protected_candidate["index"], (
        "Generator SHA-256 line moved"
    )
    try:
        markdown_sha256 = regenerated_candidate["sha256"].decode("ascii")
    except UnicodeDecodeError as exc:
        raise AssertionError("Markdown generator SHA-256 is not ASCII") from exc
    assert re.fullmatch(r"[0-9a-f]{64}", markdown_sha256), (
        "Markdown generator SHA-256 must be 64-character lowercase hex"
    )
    assert markdown_sha256 == json_sha256, (
        "Markdown generator SHA-256 is inconsistent with regenerated JSON"
    )
    assert json_sha256 == identity["sha256"], (
        "regenerated JSON/Markdown generator SHA-256 is inconsistent with generator bytes"
    )
    assert markdown_sha256 == identity["sha256"], (
        "Markdown generator SHA-256 is inconsistent with generator bytes"
    )
    expected_line = (
        b"- Generator SHA-256: `"
        + str(identity["sha256"]).encode("ascii")
        + b"`"
        + protected_candidate["ending"]
    )
    assert regenerated_candidate["line"] == expected_line, (
        "Markdown Generator SHA-256 line is not the deterministic expected line"
    )
    for index, (protected_line, regenerated_line) in enumerate(
        zip(protected_lines, regenerated_lines)
    ):
        if index != protected_candidate["index"]:
            assert regenerated_line == protected_line, (
                f"Markdown line {index + 1} differs outside the closed exception"
            )
    expected_raw = _expected_markdown_with_current_identity(
        protected_markdown_raw, identity
    )
    assert regenerated_markdown_raw == expected_raw, (
        "Markdown bytes differ outside the one exact Generator SHA-256 line"
    )


def _canonical_json_bytes(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode(
        "utf-8"
    )


@pytest.fixture(scope="module")
def self_identity_contract_samples():
    protected_json_raw = PROTECTED_JSON_PATH.read_bytes()
    protected_markdown_raw = PROTECTED_MARKDOWN_PATH.read_bytes()
    _assert_protected_artifact_pins(protected_json_raw, protected_markdown_raw)
    generator_path = _canonical_generator_path()
    identity = _generator_identity(generator_path)
    return {
        "generator_path": generator_path,
        "identity": identity,
        "protected_json": protected_json_raw,
        "protected_markdown": protected_markdown_raw,
        "regenerated_json": _expected_json_with_current_identity(
            protected_json_raw, identity
        ),
        "regenerated_markdown": _expected_markdown_with_current_identity(
            protected_markdown_raw, identity
        ),
    }


def _analyze(source: str, path: str = "sample.py", *, resolve_transitive: bool = True):
    mod = _module()
    transitive = mod.complete_transitive_absence() if resolve_transitive else None
    return mod.analyze_source_bytes(
        path,
        source.encode("utf-8"),
        "1" * 40,
        transitive_evidence=transitive,
    )


def _state(result, key: str) -> str:
    return result["evidence"][key]["state"]


def _synthetic_repo(tmp_path: Path, files: dict[str, str]) -> tuple[Path, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "P541B Test"], cwd=repo, check=True)
    for relative, content in files.items():
        path = repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    subprocess.run(["git", "add", "--", *sorted(files)], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "fixture"], cwd=repo, check=True)
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()
    return repo, commit


def _one_hop(repo: Path, commit: str, source_path: str):
    mod = _module()
    entries = mod.git_tree_entries(repo, commit, [source_path])
    raw = mod.git_blob(repo, entries[source_path]["blob_id"])
    return mod.one_hop_transitive_evidence(source_path, raw, repo, commit)


def _frozen_analysis(source_path: str):
    mod = _module()
    entries = mod.git_tree_entries(REPO_ROOT, mod.FROZEN_SOURCE_COMMIT, [source_path])
    entry = entries[source_path]
    raw = mod.git_blob(REPO_ROOT, entry["blob_id"])
    return mod.analyze_source_bytes(
        source_path,
        raw,
        entry["blob_id"],
        transitive_evidence=mod.complete_transitive_absence(),
    )


def _frozen_one_hop_analysis(source_path: str):
    mod = _module()
    entries = mod.git_tree_entries(REPO_ROOT, mod.FROZEN_SOURCE_COMMIT, [source_path])
    entry = entries[source_path]
    raw = mod.git_blob(REPO_ROOT, entry["blob_id"])
    transitive = mod.one_hop_transitive_evidence(
        source_path,
        raw,
        REPO_ROOT,
        mod.FROZEN_SOURCE_COMMIT,
    )
    return mod.analyze_source_bytes(
        source_path,
        raw,
        entry["blob_id"],
        transitive_evidence=transitive,
    )


def _generator_source_tree():
    source = inspect.getsource(_module())
    return source, ast.parse(source)


def _static_resolved_name(node: ast.AST, aliases: dict[str, str]) -> str | None:
    if isinstance(node, ast.Name):
        return aliases.get(node.id, node.id)
    if isinstance(node, ast.Attribute):
        base = _static_resolved_name(node.value, aliases)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Call):
        called = _static_resolved_name(node.func, aliases)
        if called == "getattr" and node.args:
            base = _static_resolved_name(node.args[0], aliases)
            if (
                len(node.args) >= 2
                and isinstance(node.args[1], ast.Constant)
                and isinstance(node.args[1].value, str)
            ):
                return f"{base}.{node.args[1].value}" if base else None
            return f"{base}.<dynamic_getattr>" if base else "<dynamic_getattr>"
        return f"{called}()" if called else None
    return None


def _static_aliases(tree: ast.AST) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                aliases[alias.asname or alias.name.split(".")[0]] = alias.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                if alias.name != "*":
                    aliases[alias.asname or alias.name] = f"{node.module}.{alias.name}"
    for _ in range(6):
        changed = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                value, targets = node.value, node.targets
            elif isinstance(node, ast.AnnAssign) and node.value is not None:
                value, targets = node.value, [node.target]
            else:
                continue
            if isinstance(value, ast.Call):
                called = _static_resolved_name(value.func, aliases)
                if called != "getattr":
                    continue
            resolved = _static_resolved_name(value, aliases)
            if not resolved:
                continue
            for target in targets:
                if isinstance(target, ast.Name) and aliases.get(target.id) != resolved:
                    aliases[target.id] = resolved
                    changed = True
        if not changed:
            break
    return aliases


def _static_resolved_calls(tree: ast.AST) -> list[tuple[ast.Call, str]]:
    aliases = _static_aliases(tree)
    return [
        (node, _static_resolved_name(node.func, aliases) or "<unresolved>")
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    ]


@pytest.fixture(scope="module")
def artifact():
    return _module().build_artifact(REPO_ROOT)


def test_exact_valid_forward_main_guard():
    result = _analyze("if __name__ == '__main__':\n    print('x')\n")
    assert _state(result, "valid_main_guard") == "detected"
    finding = result["evidence"]["valid_main_guard"]["findings"][0]
    assert finding["line"] == 1 and finding["executable_statements"] is True


def test_exact_valid_reversed_main_guard():
    result = _analyze("if '__main__' == __name__:\n    pass\n")
    assert _state(result, "valid_main_guard") == "detected"


def test_main_guard_typo_rejected():
    result = _analyze("if __name__ == '_main':\n    print('x')\n")
    assert _state(result, "valid_main_guard") == "not_detected"
    assert _state(result, "malformed_main_guard") == "detected"


def test_main_guard_inequality_rejected():
    result = _analyze("if __name__ != '__main__':\n    pass\n")
    assert _state(result, "valid_main_guard") == "not_detected"


def test_main_guard_chained_comparison_rejected():
    result = _analyze("if __name__ == '__main__' == marker:\n    pass\n")
    assert _state(result, "valid_main_guard") == "not_detected"


def test_nested_main_guard_rejected():
    result = _analyze("if True:\n    if __name__ == '__main__':\n        pass\n")
    assert _state(result, "valid_main_guard") == "not_detected"


def test_function_local_main_guard_rejected():
    result = _analyze("def f():\n    if __name__ == '__main__':\n        pass\n")
    assert _state(result, "valid_main_guard") == "not_detected"


def test_boolean_combination_main_guard_rejected():
    result = _analyze("if __name__ == '__main__' and enabled:\n    pass\n")
    assert _state(result, "valid_main_guard") == "not_detected"


def test_comments_do_not_create_executable_effect_findings():
    result = _analyze(
        "# sqlite3.connect; subprocess.run; Path('x').write_text('x')\n"
        "def choose(values):\n    return values[:6]\n"
    )
    assert all(_state(result, key) == "not_detected" for key in _module().RISK_EVIDENCE_KEYS)


def test_docstrings_do_not_create_executable_effect_findings():
    result = _analyze(
        '"""sqlite3.connect; https://api.example; /Users/demo/file.db"""\n'
        "def choose(values):\n    return values[:6]\n"
    )
    assert all(_state(result, key) == "not_detected" for key in _module().RISK_EVIDENCE_KEYS)


def test_direct_sqlite_connection_detected():
    result = _analyze("import sqlite3\ndef f():\n    return sqlite3.connect('x.db')\n")
    assert _state(result, "database_access") == "detected"


def test_direct_database_manager_construction_detected():
    result = _analyze(
        "from lottery_api.database import DatabaseManager\n"
        "def f():\n    return DatabaseManager()\n"
    )
    assert _state(result, "database_access") == "detected"


def test_aliased_database_manager_construction_detected():
    result = _analyze(
        "from lottery_api.database import DatabaseManager as DM\n"
        "def f():\n    return DM()\n"
    )
    assert _state(result, "database_access") == "detected"


def test_db_manager_singleton_use_detected():
    result = _analyze(
        "from lottery_api.database import db_manager\n"
        "def f():\n    return db_manager.execute('SELECT 1')\n"
    )
    assert _state(result, "database_access") == "detected"


def test_aliased_db_manager_singleton_use_detected():
    result = _analyze(
        "from lottery_api.database import db_manager as db\n"
        "def f():\n    return db.execute('SELECT 1')\n"
    )
    assert _state(result, "database_access") == "detected"


def test_library_scope_database_use_is_callable_body():
    result = _analyze("import sqlite3\ndef load():\n    return sqlite3.connect('x.db')\n")
    finding = result["evidence"]["database_access"]["findings"][0]
    assert finding["scope"] == "callable_body"
    assert _state(result, "import_time_execution") == "not_detected"


def test_main_guard_database_demo_remains_whole_file_detected():
    result = _analyze(
        "import sqlite3\n"
        "if __name__ == '__main__':\n    sqlite3.connect('x.db')\n"
    )
    finding = result["evidence"]["database_access"]["findings"][0]
    assert finding["scope"] == "main_guard"
    assert _state(result, "database_access") == "detected"
    assert _state(result, "import_time_execution") == "not_detected"


def test_database_operation_read_and_write_are_distinguished():
    result = _analyze(
        "def f(cursor):\n"
        "    cursor.execute('SELECT * FROM draws')\n"
        "    cursor.execute('DELETE FROM draws')\n"
    )
    operations = {item["operation"] for item in result["evidence"]["database_access"]["findings"]}
    assert operations == {"read", "write"}


def test_path_write_text_detected():
    result = _analyze("from pathlib import Path\ndef f():\n    Path('x').write_text('x')\n")
    assert _state(result, "filesystem_write") == "detected"


def test_path_write_bytes_detected():
    result = _analyze("from pathlib import Path\ndef f():\n    Path('x').write_bytes(b'x')\n")
    assert _state(result, "filesystem_write") == "detected"


def test_path_open_positional_write_mode_detected():
    result = _analyze("from pathlib import Path\ndef f():\n    Path('x').open('wb')\n")
    assert _state(result, "filesystem_write") == "detected"
    assert _state(result, "filesystem_read") == "not_detected"


def test_unbound_path_open_positional_write_mode_detected():
    result = _analyze(
        "from pathlib import Path\ndef f(path):\n    Path.open(path, 'w')\n"
    )
    assert _state(result, "filesystem_write") == "detected"


def test_module_open_positional_write_mode_detected():
    result = _analyze("import gzip\ndef f():\n    gzip.open('x.gz', 'wb')\n")
    assert _state(result, "filesystem_write") == "detected"


def test_dynamic_open_keyword_expansion_fails_closed():
    result = _analyze("def f(path, options):\n    open(path, **options)\n")
    assert result["scan_status"] == "unsupported"
    assert result["safety_classification"]["risk_level"] == "unknown"


def test_model_save_detected_as_filesystem_write():
    result = _analyze("import torch\ndef f(model):\n    torch.save(model, 'model.pt')\n")
    assert _state(result, "filesystem_write") == "detected"


def test_aliased_filesystem_mutation_detected():
    result = _analyze("from pathlib import Path as P\ndef f():\n    P('x').unlink()\n")
    assert _state(result, "filesystem_write") == "detected"


def test_read_only_filesystem_access_is_separate():
    result = _analyze("from pathlib import Path\ndef f():\n    return Path('x').read_text()\n")
    assert _state(result, "filesystem_read") == "detected"
    assert _state(result, "filesystem_write") == "not_detected"


def test_requests_api_backend_detected():
    result = _analyze(
        "import requests\nAPI='http://localhost:8000/api'\ndef f():\n    requests.get(API)\n"
    )
    assert _state(result, "network_io") == "detected"
    assert _state(result, "external_service_url") == "detected"


def test_aliased_network_call_detected():
    result = _analyze("from requests import post as send\ndef f():\n    send('https://api.example')\n")
    assert _state(result, "network_io") == "detected"


def test_urllib_network_call_detected():
    result = _analyze("from urllib.request import urlopen\ndef f():\n    urlopen('https://api.example')\n")
    assert _state(result, "network_io") == "detected"


def test_subprocess_direct_call_detected():
    result = _analyze("import subprocess\ndef f():\n    subprocess.run(['true'])\n")
    assert _state(result, "process_execution") == "detected"


def test_subprocess_aliased_call_detected():
    result = _analyze("import subprocess as sp\ndef f():\n    sp.Popen(['true'])\n")
    assert _state(result, "process_execution") == "detected"


def test_os_system_detected():
    result = _analyze("import os\ndef f():\n    os.system('true')\n")
    assert _state(result, "process_execution") == "detected"


def test_hardcoded_external_inputs_are_separate_dimensions():
    result = _analyze(
        "PATH='/Users/demo/lottery.db'\nDRAW='11301001'\nURL='https://api.example/v1'\n"
    )
    assert _state(result, "hardcoded_absolute_path") == "detected"
    assert _state(result, "database_like_path") == "detected"
    assert _state(result, "hardcoded_draw_or_date") == "detected"
    assert _state(result, "external_service_url") == "detected"


def test_clean_pure_prediction_function_remains_low_risk():
    result = _analyze("def choose(values):\n    return sorted(values)[:6]\n")
    assert result["scan_status"] == "complete"
    assert result["safety_classification"]["risk_level"] == "low"
    assert result["safety_classification"]["low_risk_eligible"] is True


def test_syntax_error_produces_unknown():
    result = _analyze("this is invalid !!!\n")
    assert result["scan_status"] == "syntax_error"
    assert result["scan"]["complete"] is False
    assert result["scan"]["read_status"] == "succeeded"
    assert result["scan"]["decode_status"] == "succeeded"
    assert result["scan"]["parse_status"] == "failed"
    assert result["scan"]["error"]["code"] == "ast_parse_failed"
    assert {item["state"] for item in result["evidence"].values()} == {"unknown"}


def test_unreadable_input_produces_unknown():
    mod = _module()
    result = mod.analyze_source_bytes("bad.py", b"\xff", "2" * 40)
    assert result["scan_status"] == "unreadable"
    assert result["scan"]["read_status"] == "succeeded"
    assert result["scan"]["decode_status"] == "failed"
    assert result["scan"]["parse_status"] == "not_attempted"
    assert result["scan"]["error"]["code"] == "utf8_decode_failed"
    assert {item["state"] for item in result["evidence"].values()} == {"unknown"}


def test_unsupported_input_produces_unknown():
    result = _analyze("from mystery import *\nopen('result.txt', 'w')\n")
    assert result["scan_status"] == "unsupported"
    assert result["scan"]["complete"] is False
    assert _state(result, "filesystem_write") == "detected"
    assert all(
        item["state"] in {"detected", "unknown"}
        for item in result["evidence"].values()
    )
    assert result["safety_classification"]["risk_level"] == "unknown"
    assert result["safety_classification"]["low_risk_eligible"] is False


def test_incomplete_alias_resolution_is_truthful_unknown():
    result = _analyze("(lambda: None)()\n")
    assert result["scan_status"] == "unsupported"
    assert result["scan"]["error"]["code"] == "unsupported_static_structure"
    assert result["scan"]["complete"] is False
    assert result["safety_classification"]["low_risk_eligible"] is False


def test_detector_exception_becomes_bounded_unknown(monkeypatch):
    mod = _module()
    monkeypatch.setattr(
        mod,
        "collect_aliases",
        lambda _tree: (_ for _ in ()).throw(RuntimeError("/Users/private/secret")),
    )
    result = mod.analyze_source_bytes(
        "sample.py",
        b"print('safe')\n",
        "1" * 40,
        transitive_evidence=mod.complete_transitive_absence(),
    )
    assert result["scan_status"] == "unsupported"
    assert result["scan"]["error"] == {
        "type": "unsupported",
        "code": "detector_failed",
        "message": "detector_failed",
    }
    assert "/Users/" not in json.dumps(result)


def test_category_detector_exception_preserves_completed_detected_evidence(monkeypatch):
    mod = _module()
    original = mod.classify_call

    def injected(call, resolved):
        if resolved == "sqlite3.connect":
            raise RuntimeError("category failed")
        return original(call, resolved)

    monkeypatch.setattr(mod, "classify_call", injected)
    result = mod.analyze_source_bytes(
        "sample.py",
        b"import sqlite3\nopen('result.txt', 'w')\nsqlite3.connect('x')\n",
        "1" * 40,
        transitive_evidence=mod.complete_transitive_absence(),
    )
    assert result["scan_status"] == "unsupported"
    assert result["scan"]["error"]["code"] == "category_detector_failed"
    assert _state(result, "filesystem_write") == "detected"
    assert _state(result, "database_access") == "unknown"
    assert result["safety_classification"]["low_risk_eligible"] is False


def test_no_low_risk_result_with_unknown_safety_flag():
    result = _analyze("def choose(values):\n    return values[:6]\n", resolve_transitive=False)
    assert _state(result, "transitive_external_state") == "unknown"
    assert result["safety_classification"]["low_risk_eligible"] is False


def test_frozen_malformed_main_guard_fixture_is_fail_closed():
    result = _frozen_analysis("lottery_api/models/biglotto_2bet_final.py")
    assert _state(result, "valid_main_guard") == "not_detected"
    assert _state(result, "malformed_main_guard") == "detected"
    assert _state(result, "database_access") == "detected"
    assert result["safety_classification"]["low_risk_eligible"] is False


def test_frozen_http_backend_fixture_detects_network_activity():
    result = _frozen_analysis("lottery_api/tools/rolling_backtest_2025.py")
    assert _state(result, "network_io") == "detected"
    assert _state(result, "external_service_url") == "detected"
    assert result["safety_classification"]["low_risk_eligible"] is False


def test_frozen_torch_save_fixture_detects_filesystem_write():
    result = _frozen_analysis("ai_lab/scripts/train_critic.py")
    assert _state(result, "filesystem_write") == "detected"
    finding = result["evidence"]["filesystem_write"]["findings"][0]
    assert finding["resolved_api"] == "torch.save"
    assert result["safety_classification"]["risk_level"] == "high"


def test_frozen_sibling_tools_import_cannot_remain_low_risk():
    result = _frozen_one_hop_analysis("tools/get_more_bets.py")
    transitive = result["evidence"]["transitive_external_state"]
    assert transitive["state"] != "not_detected"
    assert any(
        finding["resolved_api"] == "sqlite3.connect"
        and finding["imported_module_path"]
        == "tools/evolving_strategy_engine/data_loader.py"
        for finding in transitive["findings"]
    )
    assert result["safety_classification"]["low_risk_eligible"] is False


@pytest.mark.parametrize(
    "source_path",
    [
        "tools/backtest_apriori.py",
        "tools/predict_sequence_transformer.py",
    ],
)
def test_frozen_unresolved_import_dispatch_cannot_remain_low_risk(source_path):
    result = _frozen_one_hop_analysis(source_path)
    assert result["evidence"]["transitive_external_state"]["state"] != "not_detected"
    assert result["safety_classification"]["low_risk_eligible"] is False


def test_frozen_quantum_nested_import_cannot_remain_low_risk():
    result = _frozen_one_hop_analysis("lottery_api/models/unified_predictor.py")
    transitive = result["evidence"]["transitive_external_state"]
    assert transitive["state"] == "unknown"
    assert "import_resolution_incomplete" in transitive["reason"]
    assert result["safety_classification"]["low_risk_eligible"] is False


def test_frozen_xgboost_import_time_constructor_cannot_remain_low_risk():
    result = _frozen_one_hop_analysis("lottery_api/models/xgboost_model.py")
    transitive = result["evidence"]["transitive_external_state"]
    assert transitive["state"] == "unknown"
    assert "import_resolution_incomplete" in transitive["reason"]
    assert result["safety_classification"]["low_risk_eligible"] is False


def test_frozen_backtest_inherited_database_effect_is_preserved():
    result = _frozen_one_hop_analysis("tools/backtest_apriori.py")
    transitive = result["evidence"]["transitive_external_state"]
    assert {
        (finding["resolved_api"], finding["imported_module_path"])
        for finding in transitive["findings"]
    } >= {
        ("database.DatabaseManager", "tools/predict_biglotto_apriori.py"),
        (
            "database.DatabaseManager().get_all_draws",
            "tools/predict_biglotto_apriori.py",
        ),
    }
    assert result["safety_classification"]["low_risk_eligible"] is False


def test_one_hop_db_coupled_import_detected(tmp_path):
    repo, commit = _synthetic_repo(
        tmp_path,
        {
            "main.py": "from helper import connect\nconnect()\n",
            "helper.py": "import sqlite3\ndef connect():\n    return sqlite3.connect('x.db')\n",
        },
    )
    result = _one_hop(repo, commit, "main.py")
    assert result["state"] == "detected"
    assert result["findings"][0]["imported_module_path"] == "helper.py"
    assert "imported_module_source" not in result["findings"][0]


def test_one_hop_clean_import_remains_clean(tmp_path):
    repo, commit = _synthetic_repo(
        tmp_path,
        {"main.py": "from helper import choose\nchoose([])\n", "helper.py": "def choose(v):\n    return v\n"},
    )
    assert _one_hop(repo, commit, "main.py")["state"] == "not_detected"


def test_one_hop_module_level_effect_detected(tmp_path):
    repo, commit = _synthetic_repo(
        tmp_path,
        {"main.py": "import helper\n", "helper.py": "import sqlite3\nsqlite3.connect('x.db')\n"},
    )
    assert _one_hop(repo, commit, "main.py")["state"] == "detected"


def test_one_hop_module_level_local_constructor_effect_detected(tmp_path):
    repo, commit = _synthetic_repo(
        tmp_path,
        {
            "main.py": "import helper\n",
            "helper.py": (
                "import requests\n"
                "class Worker:\n"
                "    def __init__(self):\n"
                "        requests.get('https://example.test')\n"
                "worker = Worker()\n"
            ),
        },
    )
    result = _one_hop(repo, commit, "main.py")
    assert result["state"] == "detected"
    assert any(
        finding["resolved_api"] == "requests.get"
        and finding["imported_module_path"] == "helper.py"
        for finding in result["findings"]
    )


def test_one_hop_invoked_constructor_effect_detected(tmp_path):
    repo, commit = _synthetic_repo(
        tmp_path,
        {
            "main.py": "from helper import Worker\nWorker()\n",
            "helper.py": "import sqlite3\nclass Worker:\n    def __init__(self):\n        sqlite3.connect('x.db')\n",
        },
    )
    assert _one_hop(repo, commit, "main.py")["state"] == "detected"


def test_one_hop_sibling_tools_import_detects_database_effect(tmp_path):
    repo, commit = _synthetic_repo(
        tmp_path,
        {
            "tools/main.py": (
                "from evolving_strategy_engine.data_loader import load_big_lotto_draws\n"
                "load_big_lotto_draws()\n"
            ),
            "tools/evolving_strategy_engine/data_loader.py": (
                "import sqlite3\n"
                "def load_big_lotto_draws():\n"
                "    return sqlite3.connect('x.db')\n"
            ),
        },
    )
    result = _one_hop(repo, commit, "tools/main.py")
    assert result["state"] == "detected"
    assert any(
        finding["resolved_api"] == "sqlite3.connect"
        and finding["imported_module_path"]
        == "tools/evolving_strategy_engine/data_loader.py"
        for finding in result["findings"]
    )


@pytest.mark.parametrize(
    "path_setup",
    [
        (
            "from pathlib import Path\n"
            "tool_root = Path(__file__).resolve().parents[1] / 'tools'\n"
            "sys.path.insert(0, str(tool_root))\n"
        ),
        (
            "import os\n"
            "repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))\n"
            "sys.path.insert(0, os.path.join(repo_root, 'tools'))\n"
        ),
    ],
)
def test_bounded_sys_path_project_import_resolves_frozen_tree(tmp_path, path_setup):
    repo, commit = _synthetic_repo(
        tmp_path,
        {
            "scripts/main.py": (
                "import sys\n"
                f"{path_setup}"
                "from hidden.data import load\n"
                "load()\n"
            ),
            "tools/hidden/data.py": (
                "import sqlite3\n"
                "def load():\n"
                "    return sqlite3.connect('x.db')\n"
            ),
        },
    )
    result = _one_hop(repo, commit, "scripts/main.py")
    assert result["state"] == "detected"
    assert any(
        finding["resolved_api"] == "sqlite3.connect"
        and finding["imported_module_path"] == "tools/hidden/data.py"
        for finding in result["findings"]
    )


def test_same_line_sys_path_update_precedes_project_import(tmp_path):
    repo, commit = _synthetic_repo(
        tmp_path,
        {
            "scripts/main.py": (
                "import sys\n"
                "from pathlib import Path\n"
                "tool_root = Path(__file__).resolve().parents[1] / 'tools'\n"
                "sys.path.insert(0, str(tool_root)); from hidden.data import load\n"
                "load()\n"
            ),
            "tools/hidden/data.py": (
                "import sqlite3\n"
                "def load():\n"
                "    return sqlite3.connect('x.db')\n"
            ),
        },
    )
    result = _one_hop(repo, commit, "scripts/main.py")
    assert result["state"] == "detected"
    assert any(
        finding["resolved_api"] == "sqlite3.connect"
        and finding["imported_module_path"] == "tools/hidden/data.py"
        for finding in result["findings"]
    )


def test_conditional_sys_path_variable_is_unknown(tmp_path):
    source = (
        "import sys\n"
        "from pathlib import Path\n"
        "repo_root = Path(__file__).resolve().parents[1]\n"
        "root = repo_root / 'danger'\n"
        "if enabled:\n"
        "    root = repo_root / 'safe'\n"
        "sys.path.insert(0, str(root))\n"
        "from hidden import run\n"
        "run()\n"
    )
    repo, commit = _synthetic_repo(
        tmp_path,
        {
            "scripts/main.py": source,
            "danger/hidden.py": (
                "import sqlite3\n"
                "def run():\n"
                "    return sqlite3.connect('x.db')\n"
            ),
            "safe/hidden.py": "def run():\n    return None\n",
        },
    )
    result = _one_hop(repo, commit, "scripts/main.py")
    assert result["state"] == "unknown"
    assert result["reason"] == "import_resolution_incomplete"
    analysis = _module().analyze_source_bytes(
        "scripts/main.py",
        source.encode("utf-8"),
        "1" * 40,
        transitive_evidence=result,
    )
    assert analysis["safety_classification"]["risk_level"] == "unknown"
    assert analysis["safety_classification"]["low_risk_eligible"] is False


def test_loop_rebound_sys_path_variable_is_unknown(tmp_path):
    source = (
        "import sys\n"
        "from pathlib import Path\n"
        "repo_root = Path(__file__).resolve().parents[1]\n"
        "root = repo_root / 'clean'\n"
        "for root in [repo_root / 'danger']:\n"
        "    pass\n"
        "sys.path.insert(0, str(root))\n"
        "from hidden import run\n"
        "run()\n"
    )
    repo, commit = _synthetic_repo(
        tmp_path,
        {
            "scripts/main.py": source,
            "clean/hidden.py": "def run():\n    return None\n",
            "danger/hidden.py": (
                "import sqlite3\n"
                "def run():\n"
                "    return sqlite3.connect('x.db')\n"
            ),
        },
    )
    result = _one_hop(repo, commit, "scripts/main.py")
    assert result["state"] == "unknown"
    assert result["reason"] == "import_resolution_incomplete"
    analysis = _module().analyze_source_bytes(
        "scripts/main.py",
        source.encode("utf-8"),
        "1" * 40,
        transitive_evidence=result,
    )
    assert analysis["safety_classification"]["low_risk_eligible"] is False


@pytest.mark.parametrize(
    "source_path",
    [
        "tools/testing/test-all-optimizations.py",
        "tools/testing/test-optimization-b.py",
        "tools/testing/test-optimization-simple.py",
    ],
)
def test_frozen_invalid_sys_path_root_cannot_remain_low_risk(source_path):
    result = _frozen_one_hop_analysis(source_path)
    assert result["evidence"]["transitive_external_state"]["state"] == "unknown"
    assert result["safety_classification"]["low_risk_eligible"] is False


def test_one_hop_function_local_import_detects_network_effect(tmp_path):
    repo, commit = _synthetic_repo(
        tmp_path,
        {
            "main.py": (
                "def run():\n"
                "    from helper import fetch\n"
                "    return fetch()\n"
                "run()\n"
            ),
            "helper.py": "import requests\ndef fetch():\n    return requests.get('https://example.test')\n",
        },
    )
    result = _one_hop(repo, commit, "main.py")
    assert result["state"] == "detected"
    assert any(finding["resolved_api"] == "requests.get" for finding in result["findings"])


def test_uninvoked_outer_project_import_is_dormant_without_promoted_effect(tmp_path):
    repo, commit = _synthetic_repo(
        tmp_path,
        {
            "main.py": "def dormant():\n    from helper import connect\n    return connect()\n",
            "helper.py": "import sqlite3\nsqlite3.connect('x.db')\n",
        },
    )
    result = _one_hop(repo, commit, "main.py")
    assert result["state"] == "not_detected"
    assert result["findings"] == []


def test_conditional_nested_project_import_is_unknown_without_promoted_effect(tmp_path):
    repo, commit = _synthetic_repo(
        tmp_path,
        {
            "main.py": "if enabled:\n    from helper import connect\n    connect()\n",
            "helper.py": "import sqlite3\nsqlite3.connect('x.db')\n",
        },
    )
    result = _one_hop(repo, commit, "main.py")
    assert result["state"] == "unknown"
    assert result["reason"] == "import_resolution_incomplete"
    assert result["findings"] == []


def test_one_hop_imported_instance_method_effect_detected(tmp_path):
    repo, commit = _synthetic_repo(
        tmp_path,
        {
            "main.py": "from helper import Worker\nworker = Worker()\nworker.fetch()\n",
            "helper.py": (
                "import requests\n"
                "class Worker:\n"
                "    def fetch(self):\n"
                "        return requests.get('https://example.test')\n"
            ),
        },
    )
    assert _one_hop(repo, commit, "main.py")["state"] == "detected"


def test_ambiguous_imported_instance_dispatch_is_unknown(tmp_path):
    repo, commit = _synthetic_repo(
        tmp_path,
        {
            "main.py": (
                "from helper import Worker\n"
                "worker = Worker()\n"
                "if enabled:\n"
                "    worker = other_factory()\n"
                "worker.fetch()\n"
            ),
            "helper.py": (
                "import requests\n"
                "class Worker:\n"
                "    def fetch(self):\n"
                "        return requests.get('https://example.test')\n"
            ),
        },
    )
    result = _one_hop(repo, commit, "main.py")
    assert result["state"] == "unknown"
    assert result["reason"] == "import_resolution_incomplete"
    assert result["findings"] == []
    analysis = _module().analyze_source_bytes(
        "main.py",
        b"from helper import Worker\nworker = Worker()\nworker.fetch()\n",
        "1" * 40,
        transitive_evidence=result,
    )
    assert analysis["safety_classification"]["risk_level"] == "unknown"
    assert analysis["safety_classification"]["low_risk_eligible"] is False


def test_ambiguous_imported_callable_alias_is_unknown(tmp_path):
    repo, commit = _synthetic_repo(
        tmp_path,
        {
            "main.py": (
                "from helper import dangerous\n"
                "target = dangerous\n"
                "if enabled:\n"
                "    target = safe\n"
                "target()\n"
            ),
            "helper.py": (
                "import sqlite3\n"
                "def dangerous():\n"
                "    return sqlite3.connect('x.db')\n"
            ),
        },
    )
    result = _one_hop(repo, commit, "main.py")
    assert result["state"] == "unknown"
    assert result["reason"] == "import_resolution_incomplete"


def test_conditional_imported_factory_dispatch_is_unknown(tmp_path):
    repo, commit = _synthetic_repo(
        tmp_path,
        {
            "main.py": (
                "from helper import Worker\n"
                "factory = Worker if enabled else Other\n"
                "factory().fetch()\n"
            ),
            "helper.py": (
                "import requests\n"
                "class Worker:\n"
                "    def fetch(self):\n"
                "        return requests.get('https://example.test')\n"
            ),
        },
    )
    result = _one_hop(repo, commit, "main.py")
    assert result["state"] == "unknown"
    assert result["reason"] == "import_resolution_incomplete"


def test_local_factory_returning_imported_class_is_unknown(tmp_path):
    repo, commit = _synthetic_repo(
        tmp_path,
        {
            "main.py": (
                "from helper import Worker\n"
                "def choose():\n"
                "    return Worker\n"
                "factory = choose()\n"
                "factory().fetch()\n"
            ),
            "helper.py": (
                "import requests\n"
                "class Worker:\n"
                "    def fetch(self):\n"
                "        return requests.get('https://example.test')\n"
            ),
        },
    )
    result = _one_hop(repo, commit, "main.py")
    assert result["state"] == "unknown"
    assert result["reason"] == "import_resolution_incomplete"


def test_loop_bound_imported_instance_dispatch_is_unknown(tmp_path):
    repo, commit = _synthetic_repo(
        tmp_path,
        {
            "main.py": (
                "from helper import Worker\n"
                "for worker in [Worker()]:\n"
                "    pass\n"
                "worker.fetch()\n"
            ),
            "helper.py": (
                "import requests\n"
                "class Worker:\n"
                "    def fetch(self):\n"
                "        return requests.get('https://example.test')\n"
            ),
        },
    )
    result = _one_hop(repo, commit, "main.py")
    assert result["state"] == "unknown"
    assert result["reason"] == "import_resolution_incomplete"


def test_one_hop_imported_instance_method_follows_same_class_helper(tmp_path):
    repo, commit = _synthetic_repo(
        tmp_path,
        {
            "main.py": "from helper import Worker\nworker = Worker()\nworker.run()\n",
            "helper.py": (
                "import requests\n"
                "class Worker:\n"
                "    def run(self):\n"
                "        return self._fetch()\n"
                "    def _fetch(self):\n"
                "        return requests.get('https://example.test')\n"
            ),
        },
    )
    result = _one_hop(repo, commit, "main.py")
    assert result["state"] == "detected"
    assert any(finding["resolved_api"] == "requests.get" for finding in result["findings"])


def test_one_hop_imported_inherited_method_effect_detected(tmp_path):
    repo, commit = _synthetic_repo(
        tmp_path,
        {
            "main.py": "from helper import Worker\nworker = Worker()\nworker.load()\n",
            "helper.py": (
                "import sqlite3\n"
                "class Base:\n"
                "    def load(self):\n"
                "        return sqlite3.connect('x.db')\n"
                "class Worker(Base):\n"
                "    pass\n"
            ),
        },
    )
    assert _one_hop(repo, commit, "main.py")["state"] == "detected"


def test_deeper_project_dependency_is_unknown_at_one_hop_boundary(tmp_path):
    repo, commit = _synthetic_repo(
        tmp_path,
        {
            "main.py": "from helper import Worker\nWorker()\n",
            "helper.py": "from deeper import DatabaseWorker\nclass Worker(DatabaseWorker):\n    pass\n",
            "deeper.py": "import sqlite3\nclass DatabaseWorker:\n    def load(self):\n        return sqlite3.connect('x.db')\n",
        },
    )
    result = _one_hop(repo, commit, "main.py")
    assert result["state"] == "unknown"
    assert result["reason"] == "import_resolution_incomplete"


@pytest.mark.parametrize(
    "helper_source",
    [
        "import deeper\n",
        "from deeper import VALUE\n",
        "from deeper import decorate\n@decorate\ndef local():\n    return 1\n",
    ],
)
def test_imported_module_load_deeper_project_import_is_unknown(
    tmp_path, helper_source
):
    repo, commit = _synthetic_repo(
        tmp_path,
        {
            "main.py": "import helper\n",
            "helper.py": helper_source,
            "deeper.py": (
                "import sqlite3\n"
                "sqlite3.connect('x.db')\n"
                "VALUE = 1\n"
                "def decorate(function):\n"
                "    return function\n"
            ),
        },
    )
    result = _one_hop(repo, commit, "main.py")
    assert result["state"] == "unknown"
    assert result["reason"] == "import_resolution_incomplete"
    assert result["findings"] == []


@pytest.mark.parametrize(
    ("main_source", "helper_source"),
    [
        (
            "from helper import run\nrun()\n",
            "def run():\n    import deeper\n    return 1\n",
        ),
        (
            "from helper import Worker\nWorker().run()\n",
            "class Worker:\n    def run(self):\n        import deeper\n        return 1\n",
        ),
    ],
)
def test_invoked_definition_deeper_project_import_is_unknown(
    tmp_path, main_source, helper_source
):
    repo, commit = _synthetic_repo(
        tmp_path,
        {
            "main.py": main_source,
            "helper.py": helper_source,
            "deeper.py": "import sqlite3\nsqlite3.connect('x.db')\n",
        },
    )
    result = _one_hop(repo, commit, "main.py")
    assert result["state"] == "unknown"
    assert result["reason"] == "import_resolution_incomplete"
    assert result["findings"] == []


def test_uninvoked_definition_deeper_project_import_remains_dormant(tmp_path):
    repo, commit = _synthetic_repo(
        tmp_path,
        {
            "main.py": "import helper\n",
            "helper.py": "def dormant():\n    import deeper\n    return 1\n",
            "deeper.py": "import sqlite3\nsqlite3.connect('x.db')\n",
        },
    )
    assert _one_hop(repo, commit, "main.py")["state"] == "not_detected"


def test_reached_outer_function_uncalled_nested_helper_import_is_dormant(tmp_path):
    repo, commit = _synthetic_repo(
        tmp_path,
        {
            "main.py": "from helper import run\nrun()\n",
            "helper.py": (
                "def run():\n"
                "    def never_called():\n"
                "        import deeper\n"
                "    return 1\n"
            ),
            "deeper.py": "VALUE = 1\n",
        },
    )
    assert _one_hop(repo, commit, "main.py")["state"] == "not_detected"


def test_reached_outer_function_uncalled_nested_method_import_is_dormant(tmp_path):
    repo, commit = _synthetic_repo(
        tmp_path,
        {
            "main.py": "from helper import run\nrun()\n",
            "helper.py": (
                "def run():\n"
                "    class Nested:\n"
                "        def never_called(self):\n"
                "            import deeper\n"
                "    return 1\n"
            ),
            "deeper.py": "VALUE = 1\n",
        },
    )
    assert _one_hop(repo, commit, "main.py")["state"] == "not_detected"


def test_reached_outer_function_invoked_nested_helper_import_is_unknown(tmp_path):
    repo, commit = _synthetic_repo(
        tmp_path,
        {
            "main.py": "from helper import run\nrun()\n",
            "helper.py": (
                "def run():\n"
                "    def called():\n"
                "        import deeper\n"
                "    called()\n"
            ),
            "deeper.py": "VALUE = 1\n",
        },
    )
    result = _one_hop(repo, commit, "main.py")
    assert result["state"] == "unknown"
    assert result["reason"] == "import_resolution_incomplete"


def test_reached_outer_function_invoked_nested_method_import_is_unknown(tmp_path):
    repo, commit = _synthetic_repo(
        tmp_path,
        {
            "main.py": "from helper import run\nrun()\n",
            "helper.py": (
                "def run():\n"
                "    class Nested:\n"
                "        def called(self):\n"
                "            import deeper\n"
                "    Nested().called()\n"
            ),
            "deeper.py": "VALUE = 1\n",
        },
    )
    result = _one_hop(repo, commit, "main.py")
    assert result["state"] == "unknown"
    assert result["reason"] == "import_resolution_incomplete"


def test_reached_outer_function_nested_class_body_import_is_unknown(tmp_path):
    repo, commit = _synthetic_repo(
        tmp_path,
        {
            "main.py": "from helper import run\nrun()\n",
            "helper.py": "def run():\n    class Nested:\n        import deeper\n",
            "deeper.py": "VALUE = 1\n",
        },
    )
    result = _one_hop(repo, commit, "main.py")
    assert result["state"] == "unknown"
    assert result["reason"] == "import_resolution_incomplete"


def test_nested_function_definition_time_dependency_is_unknown(tmp_path):
    repo, commit = _synthetic_repo(
        tmp_path,
        {
            "main.py": "from helper import run\nrun()\n",
            "helper.py": (
                "def run():\n"
                "    from deeper import decorate, default\n"
                "    @decorate\n"
                "    def nested(value=default()):\n"
                "        return value\n"
                "    return 1\n"
            ),
            "deeper.py": "def decorate(value):\n    return value\ndef default():\n    return 1\n",
        },
    )
    result = _one_hop(repo, commit, "main.py")
    assert result["state"] == "unknown"
    assert result["reason"] == "import_resolution_incomplete"


@pytest.mark.parametrize(
    "class_statement",
    [
        "@deeper.decorate\n    class Nested:\n        pass",
        "class Nested(deeper.Base):\n        pass",
        "class Nested(metaclass=deeper.Meta):\n        pass",
    ],
)
def test_nested_class_definition_time_dependency_is_unknown(tmp_path, class_statement):
    repo, commit = _synthetic_repo(
        tmp_path,
        {
            "main.py": "from helper import run\nrun()\n",
            "helper.py": (
                "def run():\n"
                "    import deeper\n"
                f"    {class_statement}\n"
                "    return 1\n"
            ),
            "deeper.py": (
                "def decorate(value):\n    return value\n"
                "class Base:\n    pass\n"
                "class Meta(type):\n    pass\n"
            ),
        },
    )
    result = _one_hop(repo, commit, "main.py")
    assert result["state"] == "unknown"
    assert result["reason"] == "import_resolution_incomplete"


@pytest.mark.parametrize("module_name", ["json", "requests"])
def test_reached_definition_nonrepository_import_does_not_taint(tmp_path, module_name):
    repo, commit = _synthetic_repo(
        tmp_path,
        {
            "main.py": "from helper import run\nrun()\n",
            "helper.py": f"def run():\n    import {module_name}\n    return 1\n",
        },
    )
    assert _one_hop(repo, commit, "main.py")["state"] == "not_detected"


@pytest.mark.parametrize(
    ("main_source", "helper_source"),
    [
        (
            "from helper import run\nrun()\n",
            "def run():\n    import deeper\n",
        ),
        (
            "from helper import Worker\nWorker().run()\n",
            "class Worker:\n    def run(self):\n        import deeper\n",
        ),
    ],
)
def test_existing_direct_reached_definition_imports_remain_unknown(
    tmp_path, main_source, helper_source
):
    repo, commit = _synthetic_repo(
        tmp_path,
        {
            "main.py": main_source,
            "helper.py": helper_source,
            "deeper.py": "VALUE = 1\n",
        },
    )
    result = _one_hop(repo, commit, "main.py")
    assert result["state"] == "unknown"
    assert result["reason"] == "import_resolution_incomplete"


def test_nested_import_unknown_preserves_reached_known_finding(tmp_path):
    repo, commit = _synthetic_repo(
        tmp_path,
        {
            "main.py": "from helper import run\nrun()\n",
            "helper.py": (
                "import sqlite3\n"
                "def run():\n"
                "    sqlite3.connect('x.db')\n"
                "    def called():\n"
                "        import deeper\n"
                "    called()\n"
            ),
            "deeper.py": "VALUE = 1\n",
        },
    )
    result = _one_hop(repo, commit, "main.py")
    assert result["state"] == "unknown"
    assert result["reason"] == "import_resolution_incomplete"
    assert any(finding["resolved_api"] == "sqlite3.connect" for finding in result["findings"])


@pytest.mark.parametrize(
    "nested_source",
    [
        (
            "    def never_called():\n"
            "        import deeper\n"
        ),
        (
            "    class Nested:\n"
            "        def never_called(self):\n"
            "            import deeper\n"
        ),
    ],
)
def test_primary_reached_outer_dormant_nested_import_is_not_detected(
    tmp_path, nested_source
):
    repo, commit = _synthetic_repo(
        tmp_path,
        {
            "main.py": f"def run():\n{nested_source}    return 1\nrun()\n",
            "deeper.py": "VALUE = 1\n",
        },
    )
    assert _one_hop(repo, commit, "main.py")["state"] == "not_detected"


@pytest.mark.parametrize(
    "run_body",
    [
        (
            "    def called():\n"
            "        import deeper\n"
            "    called()\n"
        ),
        (
            "    class Nested:\n"
            "        def called(self):\n"
            "            import deeper\n"
            "    Nested().called()\n"
        ),
    ],
)
def test_primary_reached_outer_invoked_nested_import_is_unknown(tmp_path, run_body):
    repo, commit = _synthetic_repo(
        tmp_path,
        {
            "main.py": f"def run():\n{run_body}run()\n",
            "deeper.py": "VALUE = 1\n",
        },
    )
    result = _one_hop(repo, commit, "main.py")
    assert result["state"] == "unknown"
    assert result["reason"] == "import_resolution_incomplete"


def test_nested_sibling_call_reaches_deeper_import(tmp_path):
    repo, commit = _synthetic_repo(
        tmp_path,
        {
            "main.py": "from helper import run\nrun()\n",
            "helper.py": (
                "def run():\n"
                "    def a():\n"
                "        b()\n"
                "    def b():\n"
                "        import deeper\n"
                "    a()\n"
            ),
            "deeper.py": "VALUE = 1\n",
        },
    )
    result = _one_hop(repo, commit, "main.py")
    assert result["state"] == "unknown"
    assert result["reason"] == "import_resolution_incomplete"


@pytest.mark.parametrize("import_owner", ["a", "b"])
def test_mutually_recursive_nested_helpers_are_bounded_and_unknown(
    tmp_path, import_owner
):
    import_a = "        import deeper\n" if import_owner == "a" else ""
    import_b = "        import deeper\n" if import_owner == "b" else ""
    repo, commit = _synthetic_repo(
        tmp_path,
        {
            "main.py": "from helper import run\nrun()\n",
            "helper.py": (
                "def run():\n"
                "    def a():\n"
                f"{import_a}"
                "        b()\n"
                "    def b():\n"
                f"{import_b}"
                "        a()\n"
                "    a()\n"
            ),
            "deeper.py": "VALUE = 1\n",
        },
    )
    result = _one_hop(repo, commit, "main.py")
    assert result["state"] == "unknown"
    assert result["reason"] == "import_resolution_incomplete"


def test_direct_self_recursive_nested_helper_is_bounded_and_unknown(tmp_path):
    repo, commit = _synthetic_repo(
        tmp_path,
        {
            "main.py": "from helper import run\nrun()\n",
            "helper.py": (
                "def run():\n"
                "    def recurse():\n"
                "        import deeper\n"
                "        recurse()\n"
                "    recurse()\n"
            ),
            "deeper.py": "VALUE = 1\n",
        },
    )
    assert _one_hop(repo, commit, "main.py")["state"] == "unknown"


def test_dormant_nested_sibling_import_remains_not_detected(tmp_path):
    repo, commit = _synthetic_repo(
        tmp_path,
        {
            "main.py": "from helper import run\nrun()\n",
            "helper.py": (
                "def run():\n"
                "    def called():\n"
                "        return 1\n"
                "    def dormant():\n"
                "        import deeper\n"
                "    return called()\n"
            ),
            "deeper.py": "VALUE = 1\n",
        },
    )
    assert _one_hop(repo, commit, "main.py")["state"] == "not_detected"


@pytest.mark.parametrize(
    "flow_source",
    [
        "    alias = dangerous\n    alias()\n",
        (
            "    alias = dangerous\n"
            "    if enabled:\n"
            "        alias = safe\n"
            "    alias()\n"
        ),
        (
            "    def factory():\n"
            "        return dangerous\n"
            "    callback = factory()\n"
            "    callback()\n"
        ),
        (
            "    def invoke(callback):\n"
            "        callback()\n"
            "    invoke(dangerous)\n"
        ),
    ],
)
def test_nested_callable_alias_factory_and_callback_flows_fail_closed(
    tmp_path, flow_source
):
    repo, commit = _synthetic_repo(
        tmp_path,
        {
            "main.py": "from helper import run\nrun()\n",
            "helper.py": (
                "def run():\n"
                "    def dangerous():\n"
                "        import deeper\n"
                "    def safe():\n"
                "        return 1\n"
                f"{flow_source}"
            ),
            "deeper.py": "VALUE = 1\n",
        },
    )
    result = _one_hop(repo, commit, "main.py")
    assert result["state"] == "unknown"
    assert result["reason"] == "import_resolution_incomplete"


@pytest.mark.parametrize(
    "flow_source",
    [
        "    obj = Dangerous()\n    obj.method()\n",
        (
            "    obj = Dangerous()\n"
            "    callback = obj.method\n"
            "    callback()\n"
        ),
        (
            "    obj = Dangerous()\n"
            "    if enabled:\n"
            "        obj = Safe()\n"
            "    obj.method()\n"
        ),
    ],
)
def test_nested_instance_and_bound_method_aliases_fail_closed(tmp_path, flow_source):
    repo, commit = _synthetic_repo(
        tmp_path,
        {
            "main.py": "from helper import run\nrun()\n",
            "helper.py": (
                "def run():\n"
                "    class Dangerous:\n"
                "        def method(self):\n"
                "            import deeper\n"
                "    class Safe:\n"
                "        def method(self):\n"
                "            return 1\n"
                f"{flow_source}"
            ),
            "deeper.py": "VALUE = 1\n",
        },
    )
    result = _one_hop(repo, commit, "main.py")
    assert result["state"] == "unknown"
    assert result["reason"] == "import_resolution_incomplete"


def test_partially_resolved_nested_alias_is_unknown_and_preserves_finding(tmp_path):
    repo, commit = _synthetic_repo(
        tmp_path,
        {
            "main.py": "from helper import run\nrun()\n",
            "helper.py": (
                "import sqlite3\n"
                "def run():\n"
                "    sqlite3.connect('x.db')\n"
                "    def dangerous():\n"
                "        import deeper\n"
                "    target = dangerous\n"
                "    if enabled:\n"
                "        target = unresolved\n"
                "    target()\n"
            ),
            "deeper.py": "VALUE = 1\n",
        },
    )
    result = _one_hop(repo, commit, "main.py")
    assert result["state"] == "unknown"
    assert result["reason"] == "import_resolution_incomplete"
    assert any(finding["resolved_api"] == "sqlite3.connect" for finding in result["findings"])


@pytest.mark.parametrize(
    ("main_source", "helper_source"),
    [
        (
            "def run(callback):\n    callback()\nrun(unresolved)\n",
            None,
        ),
        (
            "from helper import run\nrun()\n",
            (
                "def run():\n"
                "    callback = unresolved_factory()\n"
                "    callback()\n"
            ),
        ),
    ],
)
def test_unresolved_callback_without_project_import_is_unknown(
    tmp_path, main_source, helper_source
):
    files = {"main.py": main_source}
    if helper_source is not None:
        files["helper.py"] = helper_source
    repo, commit = _synthetic_repo(tmp_path, files)
    result = _one_hop(repo, commit, "main.py")
    assert result["state"] == "unknown"
    assert result["reason"] == "import_resolution_incomplete"


def _escaped_nested_callable_result(
    tmp_path,
    helper_source: str,
    *,
    main_source: str = "from helper import run\nrun()\n",
):
    repo, commit = _synthetic_repo(
        tmp_path,
        {
            "main.py": main_source,
            "helper.py": helper_source,
            "deeper.py": "VALUE = 1\n",
        },
    )
    return _one_hop(repo, commit, "main.py")


@pytest.mark.parametrize(
    "escape_statement",
    [
        "    register(dangerous)\n",
        "    register(callback=dangerous)\n",
        "    scheduler.submit(dangerous)\n",
        "    register((dangerous,))\n",
        "    register([dangerous])\n",
        "    register({dangerous})\n",
        "    register({'callback': dangerous})\n",
    ],
)
def test_escaped_nested_callable_argument_and_container_references_are_unknown(
    tmp_path, escape_statement
):
    result = _escaped_nested_callable_result(
        tmp_path,
        (
            "def run():\n"
            "    async def dangerous():\n"
            "        import deeper\n"
            f"{escape_statement}"
        ),
    )
    assert result["state"] == "unknown"
    assert result["reason"] == "import_resolution_incomplete"


@pytest.mark.parametrize(
    ("escape_statement", "main_source"),
    [
        ("    return dangerous\n", "from helper import run\nrun()\n"),
        ("    yield dangerous\n", "from helper import run\nnext(run())\n"),
    ],
)
def test_returned_or_yielded_nested_callable_is_unknown(
    tmp_path, escape_statement, main_source
):
    result = _escaped_nested_callable_result(
        tmp_path,
        (
            "def run():\n"
            "    def dangerous():\n"
            "        import deeper\n"
            f"{escape_statement}"
        ),
        main_source=main_source,
    )
    assert result["state"] == "unknown"
    assert result["reason"] == "import_resolution_incomplete"


def test_bound_nested_class_method_passed_externally_is_unknown(tmp_path):
    result = _escaped_nested_callable_result(
        tmp_path,
        (
            "def run():\n"
            "    class Nested:\n"
            "        def dangerous(self):\n"
            "            import deeper\n"
            "    register(Nested().dangerous)\n"
        ),
    )
    assert result["state"] == "unknown"
    assert result["reason"] == "import_resolution_incomplete"


@pytest.mark.parametrize(
    "wrapper_source",
    [
        "    register(lambda: dangerous())\n",
        (
            "    def wrapper():\n"
            "        dangerous()\n"
            "    register(wrapper)\n"
        ),
    ],
)
def test_escaping_lambda_or_local_wrapper_capture_is_unknown(
    tmp_path, wrapper_source
):
    result = _escaped_nested_callable_result(
        tmp_path,
        (
            "def run():\n"
            "    def dangerous():\n"
            "        import deeper\n"
            f"{wrapper_source}"
        ),
    )
    assert result["state"] == "unknown"
    assert result["reason"] == "import_resolution_incomplete"


@pytest.mark.parametrize(
    "storage_source",
    [
        (
            "    class Holder:\n"
            "        pass\n"
            "    holder = Holder()\n"
            "    holder.callback = dangerous\n"
            "    register(holder)\n"
        ),
        (
            "    callbacks = {}\n"
            "    callbacks['callback'] = dangerous\n"
            "    register(callbacks)\n"
        ),
    ],
)
def test_callable_stored_on_escaping_owner_is_unknown(tmp_path, storage_source):
    result = _escaped_nested_callable_result(
        tmp_path,
        (
            "def run():\n"
            "    def dangerous():\n"
            "        import deeper\n"
            f"{storage_source}"
        ),
    )
    assert result["state"] == "unknown"
    assert result["reason"] == "import_resolution_incomplete"


def test_local_callable_used_directly_as_decorator_is_unknown(tmp_path):
    result = _escaped_nested_callable_result(
        tmp_path,
        (
            "def run():\n"
            "    def dangerous(callback):\n"
            "        import deeper\n"
            "        return callback\n"
            "    @dangerous\n"
            "    def wrapped():\n"
            "        return 1\n"
        ),
    )
    assert result["state"] == "unknown"
    assert result["reason"] == "import_resolution_incomplete"


def test_local_callable_passed_to_unresolved_decorator_factory_is_unknown(tmp_path):
    result = _escaped_nested_callable_result(
        tmp_path,
        (
            "def run():\n"
            "    def dangerous():\n"
            "        import deeper\n"
            "    @decorate(dangerous)\n"
            "    def wrapped():\n"
            "        return 1\n"
        ),
    )
    assert result["state"] == "unknown"
    assert result["reason"] == "import_resolution_incomplete"


def test_escaped_known_target_with_unresolved_target_preserves_finding(tmp_path):
    result = _escaped_nested_callable_result(
        tmp_path,
        (
            "import sqlite3\n"
            "def run():\n"
            "    sqlite3.connect('x.db')\n"
            "    def dangerous():\n"
            "        import deeper\n"
            "    register(dangerous, unresolved)\n"
        ),
    )
    assert result["state"] == "unknown"
    assert result["reason"] == "import_resolution_incomplete"
    assert any(
        finding["resolved_api"] == "sqlite3.connect"
        for finding in result["findings"]
    )


def test_escaped_target_does_not_taint_unrelated_dormant_nested_callable(tmp_path):
    result = _escaped_nested_callable_result(
        tmp_path,
        (
            "def run():\n"
            "    def escaped():\n"
            "        return 1\n"
            "    def dormant():\n"
            "        import deeper\n"
            "    register(escaped)\n"
        ),
    )
    assert result["state"] == "not_detected"


@pytest.mark.parametrize(
    "local_storage",
    [
        "    callbacks = (dangerous,)\n",
        "    callbacks = [dangerous]\n",
        "    callbacks = {dangerous}\n",
        "    callbacks = {'callback': dangerous}\n",
    ],
)
def test_callable_in_provably_local_container_remains_dormant(
    tmp_path, local_storage
):
    result = _escaped_nested_callable_result(
        tmp_path,
        (
            "def run():\n"
            "    def dangerous():\n"
            "        import deeper\n"
            f"{local_storage}"
            "    return 1\n"
        ),
    )
    assert result["state"] == "not_detected"


def test_escaped_nested_same_name_remains_scope_correct(tmp_path):
    result = _escaped_nested_callable_result(
        tmp_path,
        (
            "def dangerous():\n"
            "    import deeper\n"
            "def run():\n"
            "    def dangerous():\n"
            "        return 1\n"
            "    register(dangerous)\n"
        ),
    )
    assert result["state"] == "not_detected"


def test_fully_local_consumer_does_not_escape_callable_argument(tmp_path):
    result = _escaped_nested_callable_result(
        tmp_path,
        (
            "def run():\n"
            "    def dangerous():\n"
            "        import deeper\n"
            "    def consume(callback):\n"
            "        return 1\n"
            "    consume(dangerous)\n"
        ),
    )
    assert result["state"] == "not_detected"


@pytest.mark.parametrize("reference", ["json.dumps", "requests.get"])
def test_external_callable_reference_does_not_create_repository_taint(
    tmp_path, reference
):
    module_name = reference.split(".", 1)[0]
    result = _escaped_nested_callable_result(
        tmp_path,
        (
            "def run():\n"
            f"    import {module_name}\n"
            f"    register({reference})\n"
        ),
    )
    assert result["state"] == "not_detected"


def _r6_callable_flow_result(tmp_path, flow_source: str):
    return _escaped_nested_callable_result(
        tmp_path,
        (
            "import sqlite3\n"
            "def run(callbacks=()):\n"
            "    def dangerous():\n"
            "        import deeper\n"
            "        sqlite3.connect('x.db')\n"
            "    def safe():\n"
            "        return 1\n"
            f"{flow_source}"
        ),
    )


def _assert_r6_dangerous_reached(result):
    assert result["state"] == "unknown"
    assert result["reason"] == "import_resolution_incomplete"
    assert any(
        finding["resolved_api"] == "sqlite3.connect"
        for finding in result["findings"]
    )


@pytest.mark.parametrize(
    "flow_source",
    [
        (
            "    def forward(cb):\n"
            "        register(cb)\n"
            "    forward(dangerous)\n"
        ),
        (
            "    def forward(cb):\n"
            "        register(callback=cb)\n"
            "    forward(cb=dangerous)\n"
        ),
        (
            "    def second(cb):\n"
            "        register(cb)\n"
            "    def first(cb):\n"
            "        second(cb)\n"
            "    first(dangerous)\n"
        ),
        (
            "    def third(cb):\n"
            "        register(cb)\n"
            "    def second(cb):\n"
            "        third(cb)\n"
            "    def first(cb):\n"
            "        second(cb)\n"
            "    first(dangerous)\n"
        ),
        (
            "    def forward(prefix, /, *, cb):\n"
            "        register(cb)\n"
            "    forward(1, cb=dangerous)\n"
        ),
        (
            "    def forward(cb=dangerous):\n"
            "        register(cb)\n"
            "    forward()\n"
        ),
        (
            "    def forward(cb):\n"
            "        register(cb)\n"
            "    forward(*(dangerous,))\n"
        ),
        (
            "    def forward(*, cb):\n"
            "        register(cb)\n"
            "    forward(**{'cb': dangerous})\n"
        ),
    ],
    ids=[
        "positional",
        "keyword",
        "two-level",
        "three-level",
        "positional-only-keyword-only",
        "default",
        "bounded-star-args",
        "bounded-star-kwargs",
    ],
)
def test_r6_actual_arguments_propagate_to_formals(tmp_path, flow_source):
    _assert_r6_dangerous_reached(_r6_callable_flow_result(tmp_path, flow_source))


@pytest.mark.parametrize(
    "flow_source",
    [
        (
            "    def forward(cb, *rest):\n"
            "        register(cb)\n"
            "    forward(dangerous, *callbacks)\n"
        ),
        (
            "    def forward(cb, **rest):\n"
            "        register(cb)\n"
            "    forward(dangerous, **unknown_keywords)\n"
        ),
    ],
    ids=["unbounded-star-args", "unbounded-star-kwargs"],
)
def test_r6_unbounded_expansion_fails_closed_and_preserves_known_target(
    tmp_path, flow_source
):
    _assert_r6_dangerous_reached(_r6_callable_flow_result(tmp_path, flow_source))


def test_r6_multiple_invocations_keep_distinct_callable_actuals(tmp_path):
    result = _escaped_nested_callable_result(
        tmp_path,
        (
            "import sqlite3\n"
            "def run():\n"
            "    def database_callback():\n"
            "        import deeper\n"
            "        sqlite3.connect('x.db')\n"
            "    def filesystem_callback():\n"
            "        import deeper\n"
            "        open('x.txt', 'w')\n"
            "    def forward(cb):\n"
            "        register(cb)\n"
            "    forward(database_callback)\n"
            "    forward(filesystem_callback)\n"
        ),
    )
    assert result["state"] == "unknown"
    assert {finding["resolved_api"] for finding in result["findings"]} >= {
        "sqlite3.connect",
        "open",
    }


def test_r6_known_and_unresolved_invocations_preserve_finding_and_unknown(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    def forward(cb):\n"
            "        register(cb)\n"
            "    forward(dangerous)\n"
            "    forward(unresolved)\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


@pytest.mark.parametrize(
    "flow_source",
    [
        (
            "    def escaped(cb=dangerous):\n"
            "        register(cb)\n"
            "    register(escaped)\n"
        ),
        (
            "    def decorator(cb):\n"
            "        def apply(function):\n"
            "            register(cb)\n"
            "            return function\n"
            "        return apply\n"
            "    @decorator(dangerous)\n"
            "    def wrapped():\n"
            "        return 1\n"
        ),
        (
            "    async def forward(cb):\n"
            "        register(cb)\n"
            "    forward(dangerous)\n"
        ),
        (
            "    def factory(cb):\n"
            "        def wrapper():\n"
            "            register(cb)\n"
            "        return wrapper\n"
            "    register(factory(dangerous))\n"
        ),
    ],
    ids=[
        "escaped-callable-default",
        "parameterized-decorator-factory",
        "async-callback-factory",
        "factory-returning-forwarder",
    ],
)
def test_r6_defaults_decorators_async_and_factory_wrappers_propagate(
    tmp_path, flow_source
):
    _assert_r6_dangerous_reached(_r6_callable_flow_result(tmp_path, flow_source))


@pytest.mark.parametrize(
    "escaping_expression",
    [
        "[dangerous for _ in (1,)]",
        "{dangerous for _ in (1,)}",
        "{dangerous: dangerous for _ in (1,)}",
        "(dangerous for _ in (1,))",
        "[dangerous for _ in [item for item in (1,)]]",
        "([dangerous for _ in (1,)],)",
        "[dangerous for _ in (1,) if dangerous]",
    ],
    ids=[
        "list",
        "set",
        "dict-key-value",
        "generator",
        "nested",
        "literal-container",
        "filter",
    ],
)
def test_r6_comprehensions_expose_local_callable_references(
    tmp_path, escaping_expression
):
    result = _r6_callable_flow_result(
        tmp_path, f"    register({escaping_expression})\n"
    )
    _assert_r6_dangerous_reached(result)


@pytest.mark.parametrize(
    "escape_statement",
    [
        "    register(*[dangerous])\n",
        "    register(**{'callback': dangerous})\n",
    ],
    ids=["starred-positional-literal", "dictionary-unpacked-literal"],
)
def test_r6_bounded_unpacking_exposes_local_callable(tmp_path, escape_statement):
    _assert_r6_dangerous_reached(
        _r6_callable_flow_result(tmp_path, escape_statement)
    )


def test_r6_comprehension_target_shadows_outer_callable(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import json\n"
            "    values = (json.dumps,)\n"
            "    register([dangerous for dangerous in values])\n"
        ),
    )
    assert result["state"] == "not_detected"
    assert result["findings"] == []


def test_r6_external_comprehension_values_do_not_create_repository_taint(tmp_path):
    result = _escaped_nested_callable_result(
        tmp_path,
        (
            "import json\n"
            "def run():\n"
            "    register([json.dumps for _ in range(1)])\n"
        ),
    )
    assert result["state"] == "not_detected"
    assert result["findings"] == []


def test_r6_escaped_function_with_unresolved_formal_is_incomplete(tmp_path):
    result = _escaped_nested_callable_result(
        tmp_path,
        (
            "def run():\n"
            "    def escaped(callback):\n"
            "        register(callback)\n"
            "    register(escaped)\n"
        ),
    )
    assert result["state"] == "unknown"
    assert result["reason"] == "import_resolution_incomplete"
    assert result["findings"] == []


def test_r6_escaped_function_ambiguous_local_call_preserves_known_target(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    def escaped():\n"
            "        callback = dangerous\n"
            "        if enabled:\n"
            "            callback = unresolved\n"
            "        callback()\n"
            "    register(escaped)\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_r6_escape_then_reached_invocation_keeps_distinct_binding_states(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    def worker(callback):\n"
            "        register(callback)\n"
            "    register(worker)\n"
            "    worker(dangerous)\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_r6_mixed_escape_and_mutual_recursion_is_bounded(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    def first(callback):\n"
            "        register(callback)\n"
            "        second(callback)\n"
            "    def second(callback):\n"
            "        if enabled:\n"
            "            first(callback)\n"
            "    register(first)\n"
            "    first(dangerous)\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


@pytest.mark.parametrize(
    "flow_source",
    [
        (
            "    callback = dangerous\n"
            "    callback = None\n"
            "    register(callback)\n"
        ),
        (
            "    callback = None\n"
            "    register(callback)\n"
            "    callback = dangerous\n"
        ),
        (
            "    callback = dangerous\n"
            "    callback = safe\n"
            "    register(callback)\n"
        ),
    ],
    ids=["overwritten-none", "future-assignment", "latest-unconditional"],
)
def test_r6_name_bindings_use_reaching_assignment_at_escape(
    tmp_path, flow_source
):
    result = _r6_callable_flow_result(tmp_path, flow_source)
    assert result["state"] == "not_detected"
    assert result["findings"] == []


def test_r6_conditional_name_binding_merges_possible_values(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    callback = safe\n"
            "    if enabled:\n"
            "        callback = dangerous\n"
            "    register(callback)\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


@pytest.mark.parametrize(
    "flow_source",
    [
        (
            "    class Holder:\n"
            "        pass\n"
            "    holder = Holder()\n"
            "    holder.callback = dangerous\n"
            "    holder.safe = safe\n"
            "    register(holder.safe)\n"
        ),
        (
            "    class Holder:\n"
            "        pass\n"
            "    first = Holder()\n"
            "    second = Holder()\n"
            "    first.callback = dangerous\n"
            "    second.callback = safe\n"
            "    register(second.callback)\n"
        ),
        (
            "    callbacks = {}\n"
            "    callbacks['dangerous'] = dangerous\n"
            "    callbacks['safe'] = safe\n"
            "    register(callbacks['safe'])\n"
        ),
        (
            "    callbacks = {}\n"
            "    callbacks[0] = dangerous\n"
            "    callbacks['0'] = safe\n"
            "    register(callbacks['0'])\n"
        ),
        (
            "    class Holder:\n"
            "        pass\n"
            "    holder = Holder()\n"
            "    holder.callback = dangerous\n"
            "    holder.callback = None\n"
            "    register(holder)\n"
        ),
    ],
    ids=[
        "distinct-attributes",
        "distinct-owners",
        "distinct-string-keys",
        "string-int-keys",
        "storage-overwrite",
    ],
)
def test_r6_exact_storage_paths_do_not_taint_unrelated_escape(
    tmp_path, flow_source
):
    result = _r6_callable_flow_result(tmp_path, flow_source)
    assert result["state"] == "not_detected"
    assert result["findings"] == []


def test_r6_whole_owner_escape_includes_callable_fields(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    class Holder:\n"
            "        pass\n"
            "    holder = Holder()\n"
            "    holder.callback = dangerous\n"
            "    register(holder)\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_r6_conditional_storage_assignment_merges_possible_values(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    class Holder:\n"
            "        pass\n"
            "    holder = Holder()\n"
            "    holder.callback = safe\n"
            "    if enabled:\n"
            "        holder.callback = dangerous\n"
            "    register(holder.callback)\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_r6_dynamic_subscript_fails_closed_without_exact_key_taint(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    callbacks = {}\n"
            "    callbacks[key] = dangerous\n"
            "    register(callbacks['safe'])\n"
        ),
    )
    assert result["state"] == "unknown"
    assert result["reason"] == "import_resolution_incomplete"
    assert not any(
        finding["resolved_api"] == "sqlite3.connect"
        for finding in result["findings"]
    )


def test_r6_nested_scope_storage_owners_do_not_collide(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    class Holder:\n"
            "        pass\n"
            "    holder = Holder()\n"
            "    holder.callback = dangerous\n"
            "    def inner():\n"
            "        class Holder:\n"
            "            pass\n"
            "        holder = Holder()\n"
            "        holder.callback = safe\n"
            "        register(holder.callback)\n"
            "    inner()\n"
        ),
    )
    assert result["state"] == "not_detected"
    assert result["findings"] == []


def _assert_r7_unknown_without_dangerous_finding(result):
    assert result["state"] == "unknown"
    assert result["reason"] == "import_resolution_incomplete"
    assert not any(
        finding["resolved_api"] == "sqlite3.connect"
        for finding in result["findings"]
    )


def test_r7_original_iteration_bound_dispatch_reproduction(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        "    for f in [dangerous]:\n        f()\n",
    )
    _assert_r6_dangerous_reached(result)


@pytest.mark.parametrize(
    "flow_source",
    [
        "    for f in (dangerous,):\n        f()\n",
        "    for f in {dangerous}:\n        f()\n",
        "    for f in [safe, dangerous]:\n        f()\n",
        "    for _, f in [(0, dangerous)]:\n        f()\n",
        "    for *_, f in [(0, 1, dangerous)]:\n        f()\n",
        (
            "    callbacks = [dangerous]\n"
            "    for f in callbacks:\n"
            "        f()\n"
        ),
        (
            "    pair = (0, dangerous)\n"
            "    for _, f in [pair]:\n"
            "        f()\n"
        ),
        "    for f in {dangerous: 1}:\n        f()\n",
    ],
    ids=[
        "tuple",
        "set",
        "multiple-candidates",
        "destructuring",
        "starred-destructuring",
        "bounded-alias",
        "destructured-element-alias",
        "dict-keys",
    ],
)
def test_r7_bounded_for_dispatch_reaches_local_callable(tmp_path, flow_source):
    _assert_r6_dangerous_reached(
        _r6_callable_flow_result(tmp_path, flow_source)
    )


def test_r7_empty_bounded_for_body_does_not_dispatch(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        "    for f in []:\n        f()\n",
    )
    assert result["state"] == "not_detected"
    assert result["findings"] == []


def test_r7_dynamic_for_dispatch_fails_closed(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        "    for f in unresolved_callbacks:\n        f()\n",
    )
    _assert_r7_unknown_without_dangerous_finding(result)


def test_r7_async_for_dispatch_fails_closed(tmp_path):
    result = _escaped_nested_callable_result(
        tmp_path,
        (
            "async def run():\n"
            "    async for f in unresolved_callbacks:\n"
            "        f()\n"
        ),
    )
    assert result["state"] == "unknown"
    assert result["reason"] == "import_resolution_incomplete"
    assert result["findings"] == []


def test_r7_post_loop_dispatch_uses_guaranteed_nonempty_binding(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        "    for f in [dangerous]:\n        pass\n    f()\n",
    )
    _assert_r6_dangerous_reached(result)


def test_r7_post_loop_dispatch_from_unresolved_iterable_is_incomplete(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        "    for f in unresolved_callbacks:\n        pass\n    f()\n",
    )
    _assert_r7_unknown_without_dangerous_finding(result)


def test_r7_dynamic_post_loop_binding_preserves_known_candidate(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    f = dangerous\n"
            "    for f in unresolved_callbacks:\n"
            "        pass\n"
            "    f()\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_r7_future_loop_binding_does_not_reach_earlier_call(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        "    f()\n    for f in [dangerous]:\n        pass\n",
    )
    _assert_r7_unknown_without_dangerous_finding(result)


@pytest.mark.parametrize(
    "expression",
    [
        "[f() for f in [dangerous]]",
        "{f() for f in [dangerous]}",
        "{f(): 1 for f in [dangerous]}",
        "(f() for f in [dangerous])",
        "[[f() for f in [dangerous]] for _ in [0]]",
        "[f() for _ in [0] for f in [dangerous]]",
    ],
    ids=[
        "list",
        "set",
        "dict",
        "generator",
        "nested",
        "multiple-generators",
    ],
)
def test_r7_comprehension_local_dispatch_reaches_callable(
    tmp_path, expression
):
    _assert_r6_dangerous_reached(
        _r6_callable_flow_result(tmp_path, f"    {expression}\n")
    )


def test_r7_later_comprehension_generator_shadows_earlier_binding(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        "    [f() for f in [dangerous] for f in [safe]]\n",
    )
    assert result["state"] == "not_detected"
    assert result["findings"] == []


def test_r7_comprehension_target_shadows_outer_binding_locally(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        "    f = dangerous\n    [f() for f in [safe]]\n",
    )
    assert result["state"] == "not_detected"
    assert result["findings"] == []


def test_r7_comprehension_binding_does_not_overwrite_outer_binding(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        "    f = dangerous\n    [f for f in [safe]]\n    f()\n",
    )
    _assert_r6_dangerous_reached(result)


def test_r7_empty_comprehension_does_not_dispatch(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        "    [f() for f in []]\n",
    )
    assert result["state"] == "not_detected"
    assert result["findings"] == []


def test_r7_dynamic_comprehension_dispatch_fails_closed(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        "    [f() for f in unresolved_callbacks]\n",
    )
    _assert_r7_unknown_without_dangerous_finding(result)


def test_r7_known_comprehension_target_survives_later_dynamic_generator(
    tmp_path,
):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    [f() for f in [dangerous] "
            "for _ in unresolved_callbacks]\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


@pytest.mark.parametrize(
    "flow_source",
    [
        "    import json\n    [f() for f in [json.dumps]]\n",
        "    import json\n    for f in [json.dumps]:\n        f()\n",
    ],
    ids=["comprehension", "for"],
)
def test_r7_external_iteration_values_do_not_create_repository_taint(
    tmp_path, flow_source
):
    result = _r6_callable_flow_result(tmp_path, flow_source)
    assert result["state"] == "not_detected"
    assert result["findings"] == []


def test_r7_named_expression_is_a_reaching_assignment(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        "    (f := dangerous)\n    f()\n",
    )
    _assert_r6_dangerous_reached(result)


@pytest.mark.parametrize(
    "flow_source",
    [
        "    if (f := dangerous):\n        f()\n",
        "    while (f := dangerous):\n        f()\n        break\n",
    ],
    ids=["if", "while"],
)
def test_r7_named_expression_in_condition_reaches_body(tmp_path, flow_source):
    _assert_r6_dangerous_reached(
        _r6_callable_flow_result(tmp_path, flow_source)
    )


def test_r7_conditional_named_expression_preserves_candidate_and_unknown(
    tmp_path,
):
    result = _r6_callable_flow_result(
        tmp_path,
        "    if enabled:\n        (f := dangerous)\n    f()\n",
    )
    _assert_r6_dangerous_reached(result)


def test_r7_named_expression_obeys_later_overwrite(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        "    (f := dangerous)\n    f = safe\n    f()\n",
    )
    assert result["state"] == "not_detected"
    assert result["findings"] == []


@pytest.mark.parametrize(
    "flow_source",
    [
        "    [(f := dangerous) for _ in [0]]\n    f()\n",
        "    [f() for _ in [0] if (f := dangerous)]\n",
    ],
    ids=["binding-escapes-comprehension", "filter-dispatch"],
)
def test_r7_named_expression_inside_comprehension_reaches_callable(
    tmp_path, flow_source
):
    _assert_r6_dangerous_reached(
        _r6_callable_flow_result(tmp_path, flow_source)
    )


@pytest.mark.parametrize(
    "flow_source",
    [
        "    with manager() as f:\n        f()\n",
        (
            "    with manager() as first, other_manager() as f:\n"
            "        f()\n"
        ),
        "    with manager() as (_, f):\n        f()\n",
        (
            "    try:\n"
            "        return 1\n"
            "    except SomeError as f:\n"
            "        f()\n"
        ),
    ],
    ids=["with", "multiple-with-items", "destructured-with", "except"],
)
def test_r7_context_and_exception_bound_calls_fail_closed(
    tmp_path, flow_source
):
    result = _r6_callable_flow_result(tmp_path, flow_source)
    _assert_r7_unknown_without_dangerous_finding(result)


def test_r7_async_with_bound_call_fails_closed(tmp_path):
    result = _escaped_nested_callable_result(
        tmp_path,
        (
            "async def run():\n"
            "    async with manager() as f:\n"
            "        f()\n"
        ),
    )
    assert result["state"] == "unknown"
    assert result["reason"] == "import_resolution_incomplete"
    assert result["findings"] == []


def test_r7_unused_context_binding_does_not_taint_siblings(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        "    with manager() as f:\n        safe()\n",
    )
    assert result["state"] == "not_detected"
    assert result["findings"] == []


def test_r7_dormant_context_bound_dispatch_does_not_taint_reached_sibling(
    tmp_path,
):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    def dormant():\n"
            "        with manager() as f:\n"
            "            f()\n"
            "    safe()\n"
        ),
    )
    assert result["state"] == "not_detected"
    assert result["findings"] == []


def test_r7_known_candidate_with_conditional_context_binding_is_preserved(
    tmp_path,
):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    f = dangerous\n"
            "    if enabled:\n"
            "        with manager() as f:\n"
            "            pass\n"
            "    f()\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


@pytest.mark.parametrize(
    "mutation",
    [
        "    callbacks.append(dangerous)\n",
        "    callbacks.extend([dangerous])\n",
        "    callbacks += [dangerous]\n",
    ],
    ids=["append", "extend", "iadd"],
)
def test_r8_mutation_aware_iterable_dispatch_reaches_candidate(
    tmp_path, mutation
):
    result = _r6_callable_flow_result(
        tmp_path,
        "    callbacks = []\n"
        f"{mutation}"
        "    for callback in callbacks:\n"
        "        callback()\n",
    )
    _assert_r6_dangerous_reached(result)


@pytest.mark.parametrize(
    "mutation",
    [
        "    alias.append(dangerous)\n",
        "    alias += [dangerous]\n",
    ],
    ids=["append", "iadd"],
)
def test_r8_alias_mutation_updates_original_iterable(tmp_path, mutation):
    result = _r6_callable_flow_result(
        tmp_path,
        "    callbacks = []\n"
        "    alias = callbacks\n"
        f"{mutation}"
        "    for callback in callbacks:\n"
        "        callback()\n",
    )
    _assert_r6_dangerous_reached(result)


def test_r8_dict_update_reconstructs_bounded_key_candidates(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    callbacks = {}\n"
            "    callbacks.update({dangerous: 1})\n"
            "    for callback in callbacks:\n"
            "        callback()\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_r8_unresolved_dict_update_fails_closed(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    callbacks = {safe: 1}\n"
            "    callbacks.update(unresolved_mapping)\n"
            "    for callback in callbacks:\n"
            "        callback()\n"
        ),
    )
    _assert_r7_unknown_without_dangerous_finding(result)


@pytest.mark.parametrize(
    "mutation",
    [
        "    callbacks.reorder_somehow()\n",
        "    mutate(callbacks)\n",
        "    callbacks[key] = unresolved\n",
    ],
    ids=["unknown-method", "unknown-consumer", "subscript-write"],
)
def test_r8_unknown_iterable_mutation_fails_closed(tmp_path, mutation):
    result = _r6_callable_flow_result(
        tmp_path,
        "    callbacks = [safe]\n"
        f"{mutation}"
        "    for callback in callbacks:\n"
        "        callback()\n",
    )
    _assert_r7_unknown_without_dangerous_finding(result)


def test_r8_mutation_before_loop_is_reaching(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    callbacks = []\n"
            "    callbacks += [dangerous]\n"
            "    for callback in callbacks:\n"
            "        callback()\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_r8_mutation_after_loop_does_not_flow_backward(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    callbacks = []\n"
            "    for callback in callbacks:\n"
            "        callback()\n"
            "    callbacks.append(dangerous)\n"
        ),
    )
    assert result["state"] == "not_detected"
    assert result["findings"] == []


def test_r8_unrelated_literal_iterable_is_not_globally_tainted(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    unrelated = []\n"
            "    unrelated.reorder_somehow()\n"
            "    for callback in (safe,):\n"
            "        callback()\n"
        ),
    )
    assert result["state"] == "not_detected"
    assert result["findings"] == []


def test_r8_known_candidate_survives_unresolved_append(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    callbacks = [dangerous]\n"
            "    callbacks.append(unresolved)\n"
            "    for callback in callbacks:\n"
            "        callback()\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def _r8_module_scope_result(tmp_path, helper_source: str):
    return _escaped_nested_callable_result(
        tmp_path,
        helper_source,
        main_source="import helper\n",
    )


@pytest.mark.parametrize(
    "dispatch",
    [
        "alias = dangerous\nalias()\n",
        "for callback in [dangerous]:\n    callback()\n",
    ],
    ids=["alias", "for"],
)
def test_r8_module_scope_binding_dispatch_reaches_local_definition(
    tmp_path, dispatch
):
    result = _r8_module_scope_result(
        tmp_path,
        (
            "import sqlite3\n"
            "def dangerous():\n"
            "    import deeper\n"
            "    sqlite3.connect('x.db')\n"
            f"{dispatch}"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_r8_module_conditional_binding_preserves_candidate_and_unknown(
    tmp_path,
):
    result = _r8_module_scope_result(
        tmp_path,
        (
            "import sqlite3\n"
            "def dangerous():\n"
            "    import deeper\n"
            "    sqlite3.connect('x.db')\n"
            "def safe():\n"
            "    return 1\n"
            "callback = safe\n"
            "if enabled:\n"
            "    callback = dangerous\n"
            "callback()\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_r8_future_module_binding_does_not_leak_backward(tmp_path):
    result = _r8_module_scope_result(
        tmp_path,
        (
            "import sqlite3\n"
            "def dangerous():\n"
            "    import deeper\n"
            "    sqlite3.connect('x.db')\n"
            "callback()\n"
            "callback = dangerous\n"
        ),
    )
    _assert_r7_unknown_without_dangerous_finding(result)


def test_r8_main_guard_binding_dispatch_remains_fail_closed(tmp_path):
    result = _r8_module_scope_result(
        tmp_path,
        (
            "import sqlite3\n"
            "def dangerous():\n"
            "    import deeper\n"
            "    sqlite3.connect('x.db')\n"
            "if __name__ == '__main__':\n"
            "    alias = dangerous\n"
            "    alias()\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


@pytest.mark.parametrize(
    "class_body",
    [
        "    alias = dangerous\n    alias()\n",
        "    for callback in [dangerous]:\n        callback()\n",
        "    [callback() for callback in [dangerous]]\n",
        "    (alias,) = (dangerous,)\n    alias()\n",
    ],
    ids=["alias", "for", "comprehension", "destructuring"],
)
def test_r8_eager_class_body_binding_dispatch_reaches_local_definition(
    tmp_path, class_body
):
    result = _r8_module_scope_result(
        tmp_path,
        (
            "import sqlite3\n"
            "def dangerous():\n"
            "    import deeper\n"
            "    sqlite3.connect('x.db')\n"
            "class Eager:\n"
            f"{class_body}"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_r8_dormant_class_method_body_remains_isolated(tmp_path):
    result = _r8_module_scope_result(
        tmp_path,
        (
            "import sqlite3\n"
            "class Eager:\n"
            "    def dormant(self):\n"
            "        import deeper\n"
            "        sqlite3.connect('x.db')\n"
        ),
    )
    assert result["state"] == "not_detected"
    assert result["findings"] == []


@pytest.mark.parametrize(
    "class_body",
    [
        "        alias = dangerous\n        alias()\n",
        "        for callback in [dangerous]:\n            callback()\n",
        "        [callback() for callback in [dangerous]]\n",
    ],
    ids=["alias", "for", "comprehension"],
)
def test_r8_reached_function_nested_class_body_is_eager(
    tmp_path, class_body
):
    result = _r6_callable_flow_result(
        tmp_path,
        "    class Nested:\n" f"{class_body}",
    )
    _assert_r6_dangerous_reached(result)


def test_r8_unresolved_class_binding_is_scope_local(tmp_path):
    result = _r8_module_scope_result(
        tmp_path,
        (
            "import sqlite3\n"
            "def dangerous():\n"
            "    import deeper\n"
            "    sqlite3.connect('x.db')\n"
            "def safe():\n"
            "    return 1\n"
            "class Broken:\n"
            "    callback = unresolved\n"
            "    callback()\n"
            "class Unrelated:\n"
            "    callback = safe\n"
            "    callback()\n"
        ),
    )
    _assert_r7_unknown_without_dangerous_finding(result)


@pytest.mark.parametrize(
    "flow_source",
    [
        (
            "    callbacks = []\n"
            "    callbacks.append((safe, dangerous))\n"
            "    for _, callback in callbacks:\n"
            "        callback()\n"
        ),
        (
            "    callbacks = []\n"
            "    callbacks.extend([(0, 1, dangerous)])\n"
            "    for *_, callback in callbacks:\n"
            "        callback()\n"
        ),
        (
            "    head, *callbacks = (safe, dangerous)\n"
            "    for callback in callbacks:\n"
            "        callback()\n"
        ),
    ],
    ids=["tuple", "starred-loop", "starred-assignment"],
)
def test_r8_destructuring_preserves_mutated_candidates(tmp_path, flow_source):
    result = _r6_callable_flow_result(tmp_path, flow_source)
    _assert_r6_dangerous_reached(result)


def test_r8_mutation_dispatch_cycle_terminates_with_known_finding(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    callbacks = []\n"
            "    def first():\n"
            "        second()\n"
            "    def second():\n"
            "        callbacks.append(dangerous)\n"
            "        first()\n"
            "    second()\n"
            "    for callback in callbacks:\n"
            "        callback()\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_r9_min_loop_carried_append_preserves_candidate(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    fs = []\n"
            "    for item in [1, 2]:\n"
            "        for f in fs:\n"
            "            f()\n"
            "        fs.append(dangerous)\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_r9_min_loop_carried_alias_append_preserves_candidate(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    fs = []\n"
            "    alias = fs\n"
            "    for item in [1, 2]:\n"
            "        for f in fs:\n"
            "            f()\n"
            "        alias.append(dangerous)\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_r9_min_loop_carried_mutation_before_and_after_use_preserves_candidate(
    tmp_path,
):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    fs = []\n"
            "    for item in [1, 2]:\n"
            "        fs.append(safe)\n"
            "        for f in fs:\n"
            "            f()\n"
            "        fs.append(dangerous)\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_r9_min_loop_carried_augassign_preserves_candidate(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    fs = []\n"
            "    for item in [1, 2]:\n"
            "        for f in fs:\n"
            "            f()\n"
            "        fs += [dangerous]\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_r9_min_loop_carried_nested_suite_preserves_candidate(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    fs = []\n"
            "    for item in [1, 2]:\n"
            "        if item:\n"
            "            for f in fs:\n"
            "                f()\n"
            "            fs.append(dangerous)\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_r9_min_loop_carried_branch_split_ordering_fails_closed(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    fs = []\n"
            "    for item in [1, 2]:\n"
            "        if item == 1:\n"
            "            for f in fs:\n"
            "                f()\n"
            "        else:\n"
            "            fs.append(dangerous)\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_r9_min_loop_carried_unrelated_owner_stays_sealed(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    fs = []\n"
            "    other = [safe]\n"
            "    for item in [1, 2]:\n"
            "        fs.append(dangerous)\n"
            "        for f in other:\n"
            "            f()\n"
        ),
    )
    assert result["state"] in {"not_detected", "unknown"}
    assert not any(
        finding["resolved_api"] == "sqlite3.connect"
        for finding in result["findings"]
    )


def test_r9_min_loop_carried_unrelated_alias_stays_sealed(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    fs = []\n"
            "    other = []\n"
            "    alias = other\n"
            "    for item in [1, 2]:\n"
            "        for f in fs:\n"
            "            f()\n"
            "        alias.append(dangerous)\n"
        ),
    )
    assert result["state"] in {"not_detected", "unknown"}
    assert not any(
        finding["resolved_api"] == "sqlite3.connect"
        for finding in result["findings"]
    )


@pytest.mark.parametrize(
    "consumer",
    [
        "    unknown(callbacks)\n",
        "    unknown(callback=callbacks)\n",
        (
            "    def forward(values):\n"
            "        unknown(values)\n"
            "    forward(callbacks)\n"
        ),
        "    return callbacks\n",
        "    yield callbacks\n",
        (
            "    class Holder:\n"
            "        pass\n"
            "    holder = Holder()\n"
            "    holder.callbacks = callbacks\n"
            "    unknown(holder)\n"
        ),
        (
            "    box = {}\n"
            "    box['callbacks'] = callbacks\n"
            "    unknown(box)\n"
        ),
        (
            "    box = [callbacks]\n"
            "    unknown(box)\n"
        ),
        (
            "    import json\n"
            "    json.dumps(callbacks)\n"
        ),
        (
            "    for cb in callbacks:\n"
            "        cb()\n"
        ),
        (
            "    def run_all(values):\n"
            "        for value in values:\n"
            "            value()\n"
            "    run_all(callbacks)\n"
        ),
        "    scheduler.submit(callbacks)\n",
    ],
    ids=[
        "positional-escape",
        "keyword-escape",
        "parameter-flow",
        "return",
        "yield",
        "attribute-storage",
        "subscript-storage",
        "container-storage",
        "serialization",
        "iteration-consumer",
        "local-call-transfer",
        "attribute-call-consumer",
    ],
)
def test_r9_min_modeled_mutator_consumer_preserves_candidate(tmp_path, consumer):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    callbacks = []\n"
            "    callbacks.append(dangerous)\n"
            f"{consumer}"
        ),
    )
    _assert_r6_dangerous_reached(result)


def _r8_constructor_result(tmp_path, helper_source: str):
    return _r8_module_scope_result(tmp_path, helper_source)


def _r8_sqlite_findings(result):
    return [
        finding
        for finding in result["findings"]
        if finding["resolved_api"] == "sqlite3.connect"
        and finding["imported_module_path"] == "helper.py"
    ]


def test_r8_local_default_constructor_is_complete_and_methods_stay_dormant(
    tmp_path,
):
    result = _r8_constructor_result(
        tmp_path,
        (
            "class Local:\n"
            "    def ordinary(self):\n"
            "        import deeper\n"
            "value = Local()\n"
        ),
    )
    assert result["state"] == "not_detected"
    assert result["findings"] == []


def test_r8_benign_local_init_is_reached_without_false_unknown(tmp_path):
    result = _r8_constructor_result(
        tmp_path,
        (
            "class Local:\n"
            "    def __init__(self, value=1):\n"
            "        self.value = value\n"
            "instance = Local(2)\n"
        ),
    )
    assert result["state"] == "not_detected"
    assert result["findings"] == []


def test_r8_dangerous_local_init_is_reached(tmp_path):
    result = _r8_constructor_result(
        tmp_path,
        (
            "import sqlite3\n"
            "class Local:\n"
            "    def __init__(self):\n"
            "        sqlite3.connect('init.db')\n"
            "instance = Local()\n"
        ),
    )
    assert result["state"] == "detected"
    assert len(_r8_sqlite_findings(result)) == 1


def test_r8_deeper_import_in_local_init_fails_closed(tmp_path):
    result = _r8_constructor_result(
        tmp_path,
        (
            "class Local:\n"
            "    def __init__(self):\n"
            "        import deeper\n"
            "instance = Local()\n"
        ),
    )
    assert result["state"] == "unknown"
    assert result["reason"] == "import_resolution_incomplete"


def test_r8_inherited_local_init_is_reached(tmp_path):
    result = _r8_constructor_result(
        tmp_path,
        (
            "import sqlite3\n"
            "class Base:\n"
            "    def __init__(self):\n"
            "        sqlite3.connect('base.db')\n"
            "class Child(Base):\n"
            "    pass\n"
            "instance = Child()\n"
        ),
    )
    assert result["state"] == "detected"
    assert len(_r8_sqlite_findings(result)) == 1


def test_r8_local_custom_new_is_reached(tmp_path):
    result = _r8_constructor_result(
        tmp_path,
        (
            "import sqlite3\n"
            "class Local:\n"
            "    def __new__(cls):\n"
            "        sqlite3.connect('new.db')\n"
            "        return object.__new__(cls)\n"
            "instance = Local()\n"
        ),
    )
    assert result["state"] != "not_detected"
    assert len(_r8_sqlite_findings(result)) == 1


@pytest.mark.parametrize(
    "base_source",
    [
        "class Local(MissingBase):\n    pass\n",
        "from deeper import Base\nclass Local(Base):\n    pass\n",
        (
            "from deeper import Base\n"
            "class Local(Base):\n"
            "    def __init__(self):\n"
            "        self.value = 1\n"
        ),
    ],
    ids=["unresolved", "external-project", "external-with-local-init"],
)
def test_r8_external_or_unresolved_base_fails_closed(tmp_path, base_source):
    result = _r8_constructor_result(
        tmp_path,
        f"{base_source}instance = Local()\n",
    )
    assert result["state"] == "unknown"
    assert result["reason"] == "import_resolution_incomplete"


def test_r8_bounded_local_metaclass_uses_default_type_call(tmp_path):
    result = _r8_constructor_result(
        tmp_path,
        (
            "class LocalMeta(type):\n"
            "    pass\n"
            "class Local(metaclass=LocalMeta):\n"
            "    pass\n"
            "instance = Local()\n"
        ),
    )
    assert result["state"] == "not_detected"
    assert result["findings"] == []


def test_r8_local_metaclass_call_is_reached(tmp_path):
    result = _r8_constructor_result(
        tmp_path,
        (
            "import sqlite3\n"
            "class LocalMeta(type):\n"
            "    def __call__(self, *args, **kwargs):\n"
            "        sqlite3.connect('meta.db')\n"
            "        return object()\n"
            "class Local(metaclass=LocalMeta):\n"
            "    pass\n"
            "instance = Local()\n"
        ),
    )
    assert result["state"] == "detected"
    assert len(_r8_sqlite_findings(result)) == 1


def test_r8_unresolved_metaclass_fails_closed(tmp_path):
    result = _r8_constructor_result(
        tmp_path,
        (
            "class Local(metaclass=make_meta()):\n"
            "    pass\n"
            "instance = Local()\n"
        ),
    )
    assert result["state"] == "unknown"
    assert result["reason"] == "import_resolution_incomplete"


def test_r8_unresolved_class_decorator_fails_closed(tmp_path):
    result = _r8_constructor_result(
        tmp_path,
        (
            "@decorate\n"
            "class Local:\n"
            "    pass\n"
            "instance = Local()\n"
        ),
    )
    assert result["state"] == "unknown"
    assert result["reason"] == "import_resolution_incomplete"


def test_r8_external_class_decorator_fails_closed(tmp_path):
    result = _r8_constructor_result(
        tmp_path,
        (
            "from deeper import decorate\n"
            "@decorate\n"
            "class Local:\n"
            "    pass\n"
            "instance = Local()\n"
        ),
    )
    assert result["state"] == "unknown"
    assert result["reason"] == "import_resolution_incomplete"


def test_r8_dynamic_subscript_class_target_fails_closed(tmp_path):
    result = _r8_constructor_result(
        tmp_path,
        (
            "class Local:\n"
            "    pass\n"
            "registry = {'local': Local}\n"
            "instance = registry[key]()\n"
        ),
    )
    assert result["state"] == "unknown"
    assert result["reason"] in {
        "import_resolution_incomplete",
        "imported_scan_incomplete",
    }


def test_r8_module_list_preserves_every_local_constructor(tmp_path):
    result = _r8_constructor_result(
        tmp_path,
        (
            "import sqlite3\n"
            "class First:\n"
            "    def __init__(self):\n"
            "        sqlite3.connect('first.db')\n"
            "class Second:\n"
            "    def __init__(self):\n"
            "        sqlite3.connect('second.db')\n"
            "class Third:\n"
            "    def __init__(self):\n"
            "        sqlite3.connect('third.db')\n"
            "instances = [First(), Second(), Third()]\n"
        ),
    )
    assert result["state"] == "detected"
    assert len(_r8_sqlite_findings(result)) == 3


def test_r8_diamond_mro_reaches_inherited_constructor_once(tmp_path):
    result = _r8_constructor_result(
        tmp_path,
        (
            "import sqlite3\n"
            "class Root:\n"
            "    def __init__(self):\n"
            "        sqlite3.connect('root.db')\n"
            "class Left(Root):\n"
            "    pass\n"
            "class Right(Root):\n"
            "    pass\n"
            "class Child(Left, Right):\n"
            "    pass\n"
            "instance = Child()\n"
        ),
    )
    assert result["state"] == "detected"
    assert len(_r8_sqlite_findings(result)) == 1


def test_r8_class_body_metadata_constructor_is_eager_but_methods_are_dormant(
    tmp_path,
):
    result = _r8_constructor_result(
        tmp_path,
        (
            "class Metadata:\n"
            "    def __init__(self, name):\n"
            "        self.name = name\n"
            "class Adapter:\n"
            "    meta = Metadata('bounded')\n"
            "    def ordinary(self):\n"
            "        import deeper\n"
            "instance = Adapter()\n"
        ),
    )
    assert result["state"] == "not_detected"
    assert result["findings"] == []


def test_r8_module_class_constructor_called_inside_function_is_complete(
    tmp_path,
):
    result = _escaped_nested_callable_result(
        tmp_path,
        (
            "class Bounded:\n"
            "    def __init__(self):\n"
            "        self.value = 1\n"
            "    def dormant(self):\n"
            "        import deeper\n"
            "def run():\n"
            "    Bounded()\n"
        ),
    )
    assert result["state"] == "not_detected"
    assert result["findings"] == []


def test_r8_outside_class_constructor_preserves_known_effect(tmp_path):
    result = _escaped_nested_callable_result(
        tmp_path,
        (
            "import sqlite3\n"
            "class Effectful:\n"
            "    def __init__(self):\n"
            "        sqlite3.connect('constructor.db')\n"
            "def run():\n"
            "    Effectful()\n"
        ),
    )
    assert result["state"] == "detected"
    assert len(_r8_sqlite_findings(result)) == 1


def test_r8_read_only_constructor_is_non_gating_and_preserved(tmp_path):
    source = (
        "from pathlib import Path\n"
        "class Reader:\n"
        "    def __init__(self, path):\n"
        "        self.data = Path(path).read_text()\n"
        "def run():\n"
        "    Reader('bounded.txt')\n"
    )
    transitive = _escaped_nested_callable_result(tmp_path, source)
    assert transitive["state"] == "not_detected"
    assert transitive["findings"] == []
    direct = _analyze(source)
    assert _state(direct, "filesystem_read") == "detected"
    assert _state(direct, "transitive_external_state") == "not_detected"
    assert direct["safety_classification"]["risk_level"] == "low"


def test_r8_pandas_read_csv_is_classified_as_filesystem_read():
    result = _analyze(
        "import pandas as pd\n"
        "class Reader:\n"
        "    def __init__(self, path):\n"
        "        self.data = pd.read_csv(path)\n"
    )
    finding = result["evidence"]["filesystem_read"]["findings"][0]
    assert finding["resolved_api"] == "pandas.read_csv"
    assert result["safety_classification"]["risk_level"] == "low"


def test_r8_conditional_class_constructor_fails_closed_with_candidate(
    tmp_path,
):
    result = _escaped_nested_callable_result(
        tmp_path,
        (
            "import sqlite3\n"
            "class Conditional:\n"
            "    if enabled:\n"
            "        def __init__(self):\n"
            "            sqlite3.connect('conditional.db')\n"
            "def run():\n"
            "    Conditional()\n"
        ),
    )
    assert result["state"] == "unknown"
    assert result["reason"] == "import_resolution_incomplete"
    assert len(_r8_sqlite_findings(result)) == 1


@pytest.mark.parametrize(
    "class_suite",
    [
        (
            "    try:\n"
            "        def __init__(self):\n"
            "            sqlite3.connect('try.db')\n"
            "    except Exception:\n"
            "        pass\n"
        ),
        (
            "    for option in options:\n"
            "        def __init__(self):\n"
            "            sqlite3.connect('for.db')\n"
        ),
        (
            "    with manager:\n"
            "        def __init__(self):\n"
            "            sqlite3.connect('with.db')\n"
        ),
        (
            "    while options:\n"
            "        def __init__(self):\n"
            "            sqlite3.connect('while.db')\n"
        ),
    ],
    ids=["try", "for", "with", "while"],
)
def test_r8_dynamic_class_suites_fail_closed_and_preserve_constructor(
    tmp_path, class_suite
):
    result = _escaped_nested_callable_result(
        tmp_path,
        (
            "import sqlite3\n"
            "class Dynamic:\n"
            f"{class_suite}"
            "def run():\n"
            "    Dynamic()\n"
        ),
    )
    assert result["state"] == "unknown"
    assert result["reason"] == "import_resolution_incomplete"
    assert len(_r8_sqlite_findings(result)) == 1


def test_r8_match_constructor_binding_support_is_runtime_gated():
    mod = _module()
    match_node = getattr(ast, "Match", None)
    if match_node is None:
        assert sys.version_info[:2] == (3, 9)
        assert 'hasattr(ast, "Match")' in inspect.getsource(mod)
    else:
        assert match_node in mod.CONTROL_FLOW_NODES


def test_r8_final_unresolved_constructor_rebinding_shadows_prior_method(
    tmp_path,
):
    result = _escaped_nested_callable_result(
        tmp_path,
        (
            "import sqlite3\n"
            "class Rebound:\n"
            "    def __init__(self):\n"
            "        sqlite3.connect('dormant.db')\n"
            "    __init__ = unresolved\n"
            "def run():\n"
            "    Rebound()\n"
        ),
    )
    assert result["state"] == "unknown"
    assert result["reason"] == "import_resolution_incomplete"
    assert _r8_sqlite_findings(result) == []


def test_r8_conditional_constructor_rebinding_preserves_both_paths(
    tmp_path,
):
    result = _escaped_nested_callable_result(
        tmp_path,
        (
            "import sqlite3\n"
            "class Rebound:\n"
            "    def __init__(self):\n"
            "        self.value = 1\n"
            "    def alternate(self):\n"
            "        sqlite3.connect('alternate.db')\n"
            "    if enabled:\n"
            "        __init__ = alternate\n"
            "def run():\n"
            "    Rebound()\n"
        ),
    )
    assert result["state"] == "unknown"
    assert result["reason"] == "import_resolution_incomplete"
    assert len(_r8_sqlite_findings(result)) == 1


def test_r8_conditional_constructor_preserves_inherited_fallthrough(
    tmp_path,
):
    result = _escaped_nested_callable_result(
        tmp_path,
        (
            "import sqlite3\n"
            "class Base:\n"
            "    def __init__(self):\n"
            "        sqlite3.connect('base.db')\n"
            "class Child(Base):\n"
            "    if enabled:\n"
            "        def __init__(self):\n"
            "            sqlite3.connect('child.db')\n"
            "def run():\n"
            "    Child()\n"
        ),
    )
    assert result["state"] == "unknown"
    assert result["reason"] == "import_resolution_incomplete"
    assert len(_r8_sqlite_findings(result)) == 2


def test_r8_later_direct_constructor_clears_conditional_uncertainty(
    tmp_path,
):
    result = _escaped_nested_callable_result(
        tmp_path,
        (
            "class FinalBinding:\n"
            "    if enabled:\n"
            "        __init__ = unresolved\n"
            "    def __init__(self):\n"
            "        self.value = 1\n"
            "def run():\n"
            "    FinalBinding()\n"
        ),
    )
    assert result["state"] == "not_detected"
    assert result["findings"] == []


@pytest.mark.parametrize(
    ("constructors", "expected_state", "expected_findings"),
    [
        (
            "    def __init__(self):\n"
            "        sqlite3.connect('overwritten.db')\n"
            "    def __init__(self):\n"
            "        self.value = 1\n",
            "not_detected",
            0,
        ),
        (
            "    def __init__(self):\n"
            "        self.value = 1\n"
            "    def __init__(self):\n"
            "        sqlite3.connect('effective.db')\n",
            "detected",
            1,
        ),
    ],
    ids=["final-benign", "final-effectful"],
)
def test_r8_duplicate_direct_init_uses_final_effective_binding(
    tmp_path, constructors, expected_state, expected_findings
):
    result = _escaped_nested_callable_result(
        tmp_path,
        (
            "import sqlite3\n"
            "class Duplicate:\n"
            f"{constructors}"
            "def run():\n"
            "    Duplicate()\n"
        ),
    )
    assert result["state"] == expected_state
    assert len(_r8_sqlite_findings(result)) == expected_findings


@pytest.mark.parametrize(
    "binding_source",
    [
        (
            "def initialize(self):\n"
            "    sqlite3.connect('module-local.db')\n"
            "class Assigned:\n"
            "    __init__ = initialize\n"
        ),
        (
            "class Assigned:\n"
            "    def initialize(self):\n"
            "        sqlite3.connect('class-local.db')\n"
            "    __init__ = initialize\n"
        ),
    ],
    ids=["module-local", "class-local"],
)
def test_r8_constructor_assignment_to_exact_local_callable_is_bounded(
    tmp_path, binding_source
):
    result = _escaped_nested_callable_result(
        tmp_path,
        (
            "import sqlite3\n"
            f"{binding_source}"
            "def run():\n"
            "    Assigned()\n"
        ),
    )
    assert result["state"] == "detected"
    assert len(_r8_sqlite_findings(result)) == 1


def test_r8_constructor_assignment_to_unresolved_callable_is_unknown(
    tmp_path,
):
    result = _escaped_nested_callable_result(
        tmp_path,
        (
            "class Assigned:\n"
            "    __init__ = unresolved\n"
            "def run():\n"
            "    Assigned()\n"
        ),
    )
    assert result["state"] == "unknown"
    assert result["reason"] == "import_resolution_incomplete"


def test_r8_new_phase_precedes_init_phase_in_execution_expansion():
    mod = _module()
    tree = ast.parse(
        "import sqlite3\n"
        "class Phased:\n"
        "    def __init__(self):\n"
        "        sqlite3.connect('init.db')\n"
        "    def __new__(cls):\n"
        "        sqlite3.connect('new.db')\n"
        "        return object.__new__(cls)\n"
        "def run():\n"
        "    Phased()\n"
    )
    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    classes = {
        node.name: node for node in tree.body if isinstance(node, ast.ClassDef)
    }
    nodes, _states, _calls, _incomplete = mod._definition_execution_nodes(
        functions["run"],
        mod.collect_aliases(tree),
        None,
        functions,
        classes,
    )
    phase_paths = [
        node.args[0].value
        for node in nodes
        if isinstance(node, ast.Call)
        and mod._dotted_name(node.func, mod.collect_aliases(tree))
        == "sqlite3.connect"
        and node.args
        and isinstance(node.args[0], ast.Constant)
    ]
    assert phase_paths == ["new.db", "init.db"]


def test_r8_module_class_alias_inside_reached_function_fixes_parent_map(
    tmp_path,
):
    result = _escaped_nested_callable_result(
        tmp_path,
        (
            "class Outside:\n"
            "    def __init__(self):\n"
            "        self.value = 1\n"
            "def run():\n"
            "    constructor = Outside\n"
            "    constructor()\n"
        ),
    )
    assert result["state"] == "not_detected"
    assert result["findings"] == []


@pytest.mark.parametrize(
    ("helper_source", "has_read"),
    [
        (
            "class RangeModel:\n"
            "    def __init__(self, maximum=49):\n"
            "        self.minimum = 1\n"
            "        self.maximum = maximum\n"
            "    def produce(self):\n"
            "        return list(range(self.minimum, self.maximum))\n"
            "def run():\n"
            "    model = RangeModel(38)\n"
            "    model.produce()\n",
            False,
        ),
        (
            "class CoverageModel:\n"
            "    def __init__(self, groups=6):\n"
            "        self.groups = groups\n"
            "    def describe(self):\n"
            "        return {'groups': self.groups}\n"
            "def run():\n"
            "    model = CoverageModel()\n"
            "    model.describe()\n",
            False,
        ),
        (
            "class EnsembleModel:\n"
            "    def __init__(self):\n"
            "        self.models = {}\n"
            "        print('ready')\n"
            "    def load(self):\n"
            "        return []\n"
            "    def train(self, rows):\n"
            "        self.models['rows'] = rows\n"
            "def run():\n"
            "    model = EnsembleModel()\n"
            "    rows = model.load()\n"
            "    model.train(rows)\n",
            False,
        ),
        (
            "import pandas as pd\n"
            "class TableModel:\n"
            "    def __init__(self, path):\n"
            "        self.rows = pd.read_csv(path)\n"
            "    def predict(self):\n"
            "        return len(self.rows)\n"
            "def run():\n"
            "    model = TableModel('bounded.csv')\n"
            "    model.predict()\n",
            True,
        ),
    ],
    ids=["bounded-range", "bounded-coverage", "bounded-engine", "bounded-reader"],
)
def test_r8_generic_outside_class_equivalents_remain_complete(
    tmp_path, helper_source, has_read
):
    transitive = _escaped_nested_callable_result(tmp_path, helper_source)
    assert transitive["state"] == "not_detected"
    assert transitive["findings"] == []
    direct = _analyze(helper_source)
    assert (_state(direct, "filesystem_read") == "detected") is has_read


def test_r8_function_header_annotations_follow_future_semantics():
    eager_tree = ast.parse("def run(value: marker()) -> result():\n    pass\n")
    postponed_tree = ast.parse(
        "from __future__ import annotations\n"
        "def run(value: marker()) -> result():\n"
        "    pass\n"
    )
    eager_names = {
        _module()._dotted_name(call.func, {})
        for call in _module().import_time_calls(eager_tree)
    }
    postponed_names = {
        _module()._dotted_name(call.func, {})
        for call in _module().import_time_calls(postponed_tree)
    }
    assert eager_names == {"marker", "result"}
    assert postponed_names == set()


def test_r8_three_local_adapter_shape_is_conclusively_not_detected(tmp_path):
    result = _r8_constructor_result(
        tmp_path,
        (
            "class Metadata:\n"
            "    def __init__(self, name, minimum):\n"
            "        self.name = name\n"
            "        self.minimum = minimum\n"
            "class AdapterBase:\n"
            "    def get_value(self, history):\n"
            "        return self._predict(history)\n"
            "    def _predict(self, history):\n"
            "        raise NotImplementedError\n"
            "class First(AdapterBase):\n"
            "    meta = Metadata('first', 10)\n"
            "    def _predict(self, history):\n"
            "        import deeper\n"
            "        return history\n"
            "class Second(AdapterBase):\n"
            "    meta = Metadata('second', 20)\n"
            "class Third(AdapterBase):\n"
            "    meta = Metadata('third', 30)\n"
            "adapters = [First(), Second(), Third()]\n"
            "adapter_map = {item.meta.name: item for item in adapters}\n"
        ),
    )
    assert result["state"] == "not_detected"
    assert result["findings"] == []


def test_r8_frozen_p47_local_construction_remains_complete_and_low():
    result = _frozen_one_hop_analysis(
        "lottery_api/models/p47_wave4_powerlotto_adapters.py"
    )
    assert result["scan_status"] == "complete"
    assert result["scan"]["complete"] is True
    transitive = result["evidence"]["transitive_external_state"]
    assert transitive["state"] == "not_detected"
    assert transitive["scope"] == "transitive"
    assert transitive["findings"] == []
    assert "reason" not in transitive
    assert result["safety_classification"]["risk_level"] == "low"
    assert result["safety_classification"]["low_risk_eligible"] is True


def test_r8_generator_write_scope_is_exactly_two_canonical_artifacts():
    _source, tree = _generator_source_tree()
    main = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "main"
    )
    assignments = {
        target.id: ast.unparse(node.value)
        for node in main.body
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
    }
    writes = [
        node
        for node in ast.walk(main)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {
            "mkdir", "open", "rename", "replace", "unlink",
            "write_bytes", "write_text",
        }
    ]
    assert [ast.unparse(node.func) for node in writes] == [
        "json_path.write_text",
        "markdown_path.write_text",
    ]
    assert assignments["json_path"] == "REPO_ROOT / OUTPUT_JSON"
    assert assignments["markdown_path"] == "REPO_ROOT / OUTPUT_MARKDOWN"


def test_r8_frozen_hypothesis_mutated_dispatch_is_fail_closed():
    result = _frozen_one_hop_analysis("tools/hypothesis_39lotto_test.py")
    transitive = result["evidence"]["transitive_external_state"]
    assert transitive["state"] == "unknown"
    assert transitive["reason"] == "import_resolution_incomplete"
    assert transitive["findings"] == []


def test_nested_same_name_does_not_fall_through_to_top_level(tmp_path):
    repo, commit = _synthetic_repo(
        tmp_path,
        {
            "main.py": "from helper import run\nrun()\n",
            "helper.py": (
                "def choose():\n"
                "    import deeper\n"
                "def run():\n"
                "    def choose():\n"
                "        return 1\n"
                "    return choose()\n"
            ),
            "deeper.py": "VALUE = 1\n",
        },
    )
    assert _one_hop(repo, commit, "main.py")["state"] == "not_detected"


def test_two_nested_classes_with_same_method_name_are_scope_correct(tmp_path):
    repo, commit = _synthetic_repo(
        tmp_path,
        {
            "main.py": "from helper import run\nrun()\n",
            "helper.py": (
                "def run():\n"
                "    class Dangerous:\n"
                "        def method(self):\n"
                "            import deeper\n"
                "    class Safe:\n"
                "        def method(self):\n"
                "            return 1\n"
                "    Safe().method()\n"
            ),
            "deeper.py": "VALUE = 1\n",
        },
    )
    assert _one_hop(repo, commit, "main.py")["state"] == "not_detected"


def test_uninvoked_imported_callable_effect_is_not_promoted(tmp_path):
    repo, commit = _synthetic_repo(
        tmp_path,
        {
            "main.py": "import helper\n",
            "helper.py": "import sqlite3\ndef connect():\n    return sqlite3.connect('x.db')\n",
        },
    )
    assert _one_hop(repo, commit, "main.py")["state"] == "not_detected"


def test_source_relative_resolution_cache_is_importer_specific(tmp_path):
    repo, commit = _synthetic_repo(
        tmp_path,
        {
            "a/main.py": "from helper import connect\nconnect()\n",
            "a/helper.py": "import sqlite3\ndef connect():\n    return sqlite3.connect('a.db')\n",
            "b/main.py": "from helper import choose\nchoose()\n",
            "b/helper.py": "def choose():\n    return 1\n",
        },
    )
    mod = _module()
    cache = {}
    a_entry = mod.git_tree_entries(repo, commit, ["a/main.py"])["a/main.py"]
    b_entry = mod.git_tree_entries(repo, commit, ["b/main.py"])["b/main.py"]
    a_result = mod.one_hop_transitive_evidence(
        "a/main.py",
        mod.git_blob(repo, a_entry["blob_id"]),
        repo,
        commit,
        resolution_cache=cache,
    )
    b_result = mod.one_hop_transitive_evidence(
        "b/main.py",
        mod.git_blob(repo, b_entry["blob_id"]),
        repo,
        commit,
        resolution_cache=cache,
    )
    assert a_result["state"] == "detected"
    assert b_result["state"] == "not_detected"


def test_incomplete_imported_scan_preserves_known_finding(tmp_path):
    repo, commit = _synthetic_repo(
        tmp_path,
        {
            "main.py": "import helper\n",
            "helper.py": "import sqlite3\nsqlite3.connect('x.db')\nfrom mystery import *\n",
        },
    )
    result = _one_hop(repo, commit, "main.py")
    assert result["state"] == "unknown"
    assert result["reason"] == "imported_scan_incomplete"
    assert any(
        finding["resolved_api"] == "sqlite3.connect"
        and finding["imported_module_path"] == "helper.py"
        for finding in result["findings"]
    )
    analysis = _module().analyze_source_bytes(
        "main.py",
        b"import helper\n",
        "1" * 40,
        transitive_evidence=result,
    )
    assert _state(analysis, "transitive_external_state") == "unknown"
    assert analysis["safety_classification"]["risk_level"] == "unknown"
    assert analysis["safety_classification"]["low_risk_eligible"] is False
    unsupported = _module().analyze_source_bytes(
        "main.py",
        b"from mystery import *\n",
        "1" * 40,
        transitive_evidence=result,
    )
    assert unsupported["scan_status"] == "unsupported"
    assert unsupported["evidence"]["transitive_external_state"]["state"] == "unknown"
    assert unsupported["evidence"]["transitive_external_state"]["findings"]


def test_later_transitive_failure_preserves_earlier_finding(tmp_path, monkeypatch):
    repo, commit = _synthetic_repo(
        tmp_path,
        {
            "main.py": "from first import connect\nfrom second import choose\nconnect()\nchoose()\n",
            "first.py": "import sqlite3\ndef connect():\n    return sqlite3.connect('x.db')\n",
            "second.py": "def choose():\n    return 1\n",
        },
    )
    mod = _module()
    original = mod._resolve_project_binding

    def injected(repo_root, frozen_commit, binding, cache):
        if binding["module"] == "second":
            raise RuntimeError("/Users/private/transitive failure")
        return original(repo_root, frozen_commit, binding, cache)

    monkeypatch.setattr(mod, "_resolve_project_binding", injected)
    first = _one_hop(repo, commit, "main.py")
    second = _one_hop(repo, commit, "main.py")
    assert first == second
    assert first["state"] == "unknown"
    assert first["reason"] == "transitive_detector_failed"
    assert any(finding["resolved_api"] == "sqlite3.connect" for finding in first["findings"])
    assert "/Users/" not in json.dumps(first)


def test_transitive_category_failure_preserves_earlier_finding(monkeypatch):
    mod = _module()
    tree = ast.parse(
        "import sqlite3\n"
        "import requests\n"
        "def run():\n"
        "    sqlite3.connect('x.db')\n"
        "    requests.get('https://example.test')\n"
    )
    original = mod.classify_call

    def injected(call, resolved):
        if resolved == "requests.get":
            raise RuntimeError("/Users/private/category failure")
        return original(call, resolved)

    monkeypatch.setattr(mod, "classify_call", injected)
    findings, incomplete, category_failed = mod._definition_effect_findings(
        tree,
        "helper.py",
        "main.py",
        {(None, "run")},
        [],
    )
    assert incomplete is False
    assert category_failed is True
    assert any(finding["resolved_api"] == "sqlite3.connect" for finding in findings)
    assert "/Users/" not in json.dumps(findings)


def test_one_hop_import_cycle_stops_safely(tmp_path):
    repo, commit = _synthetic_repo(
        tmp_path,
        {"a.py": "import b\n", "b.py": "import a\n"},
    )
    assert _one_hop(repo, commit, "a.py")["state"] == "not_detected"


def test_ambiguous_import_resolution_produces_unknown(tmp_path):
    repo, commit = _synthetic_repo(
        tmp_path,
        {"main.py": "import pkg\n", "pkg.py": "VALUE=1\n", "pkg/__init__.py": "VALUE=2\n"},
    )
    assert _one_hop(repo, commit, "main.py")["state"] == "unknown"


def test_evidence_reasons_are_deterministic():
    first = _analyze("from mystery import *\n")
    second = _analyze("from mystery import *\n")
    assert first == second


def test_output_finding_order_is_deterministic():
    source = "import subprocess\ndef f():\n    subprocess.run(['b'])\n    subprocess.run(['a'])\n"
    first = _analyze(source)
    second = _analyze(source)
    assert first["evidence"]["process_execution"]["findings"] == second["evidence"]["process_execution"]["findings"]


def test_duplicate_method_ids_fail_closed():
    mod = _module()
    historical, _ = mod.verified_historical_inputs(REPO_ROOT)
    forged = copy.deepcopy(historical)
    forged["method_classification_records"][1]["method_id"] = forged["method_classification_records"][0]["method_id"]
    with pytest.raises(mod.P541BR2Error, match="method IDs"):
        mod.validate_historical_payload(forged)


def test_duplicate_source_paths_fail_closed():
    mod = _module()
    historical, _ = mod.verified_historical_inputs(REPO_ROOT)
    forged = copy.deepcopy(historical)
    forged["method_classification_records"][1]["source_path"] = forged["method_classification_records"][0]["source_path"]
    with pytest.raises(mod.P541BR2Error, match="source paths"):
        mod.validate_historical_payload(forged)


def test_missing_frozen_manifest_entry_remains_terminal():
    mod = _module()
    with pytest.raises(mod.P541BR2Error, match="corpus incomplete"):
        mod.require_frozen_entries(["missing.py"], {})


def test_repository_or_git_failure_remains_terminal(monkeypatch):
    mod = _module()
    monkeypatch.setattr(
        mod,
        "git_tree_entries",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(mod.GitUnavailableError("Git unavailable")),
    )
    with pytest.raises(mod.GitUnavailableError, match="Git unavailable"):
        mod.build_artifact(REPO_ROOT)


def test_git_executable_failure_remains_terminal(monkeypatch):
    mod = _module()

    def unavailable(*_args, **_kwargs):
        raise OSError("/Users/private/git missing")

    monkeypatch.setattr(mod.subprocess, "run", unavailable)
    with pytest.raises(
        mod.GitExecutableUnavailableError, match="Git executable is unavailable"
    ):
        mod.run_git(REPO_ROOT, ["status", "--porcelain"])


def test_repository_failure_during_primary_blob_read_remains_terminal(
    artifact, monkeypatch
):
    mod = _module()
    target = artifact["provenance"]["source_manifest"]["ordered_entries"][0]["blob_id"]
    original = mod.git_blob

    def injected(repo_root, blob_id):
        if blob_id == target:
            raise mod.GitUnavailableError("Git repository is unavailable")
        return original(repo_root, blob_id)

    monkeypatch.setattr(mod, "git_blob", injected)
    with pytest.raises(mod.GitUnavailableError, match="repository is unavailable"):
        mod.build_artifact(REPO_ROOT)


def test_nonzero_repository_failure_during_imported_blob_read_is_terminal(
    tmp_path, monkeypatch
):
    repo, commit = _synthetic_repo(
        tmp_path,
        {"main.py": "import helper\n", "helper.py": "VALUE = 1\n"},
    )
    mod = _module()
    helper_entry = mod.git_tree_entries(repo, commit, ["helper.py"])["helper.py"]
    real_run = subprocess.run

    def injected(command, **kwargs):
        if command == ["git", "cat-file", "blob", helper_entry["blob_id"]]:
            return subprocess.CompletedProcess(
                command,
                128,
                stdout=b"",
                stderr=b"fatal: not a git repository",
            )
        return real_run(command, **kwargs)

    monkeypatch.setattr(mod.subprocess, "run", injected)
    with pytest.raises(mod.GitUnavailableError, match="repository is unavailable"):
        _one_hop(repo, commit, "main.py")


def test_object_store_failure_during_imported_blob_read_is_terminal(
    tmp_path, monkeypatch
):
    repo, commit = _synthetic_repo(
        tmp_path,
        {"main.py": "import helper\n", "helper.py": "VALUE = 1\n"},
    )
    mod = _module()
    helper_entry = mod.git_tree_entries(repo, commit, ["helper.py"])["helper.py"]
    real_run = subprocess.run

    def injected(command, **kwargs):
        if command == ["git", "cat-file", "blob", helper_entry["blob_id"]]:
            return subprocess.CompletedProcess(
                command, 128, stdout=b"", stderr=b"fatal: object unavailable"
            )
        if command == ["git", "cat-file", "-e", "HEAD^{commit}"]:
            return subprocess.CompletedProcess(
                command, 128, stdout=b"", stderr=b"fatal: object store unavailable"
            )
        return real_run(command, **kwargs)

    monkeypatch.setattr(mod.subprocess, "run", injected)
    with pytest.raises(mod.GitRepositoryUnavailableError, match="repository is unavailable"):
        _one_hop(repo, commit, "main.py")


def test_imported_isolated_blob_failure_preserves_findings_and_continues(
    tmp_path, monkeypatch
):
    repo, commit = _synthetic_repo(
        tmp_path,
        {
            "main.py": (
                "from first import connect\n"
                "import second\n"
                "from third import fetch\n"
                "connect()\n"
                "fetch()\n"
            ),
            "first.py": "import sqlite3\ndef connect():\n    return sqlite3.connect('x.db')\n",
            "second.py": "VALUE = 1\n",
            "third.py": "import requests\ndef fetch():\n    return requests.get('https://example.test')\n",
        },
    )
    mod = _module()
    second_entry = mod.git_tree_entries(repo, commit, ["second.py"])["second.py"]
    original = mod.git_blob

    def injected(repo_root, blob_id):
        if blob_id == second_entry["blob_id"]:
            raise mod.GitBlobReadError("isolated /Users/private/blob failure")
        return original(repo_root, blob_id)

    monkeypatch.setattr(mod, "git_blob", injected)
    result = _one_hop(repo, commit, "main.py")
    assert result["state"] == "unknown"
    assert result["reason"] == "git_blob_read_failed"
    assert {finding["resolved_api"] for finding in result["findings"]} >= {
        "sqlite3.connect",
        "requests.get",
    }
    assert "/Users/" not in json.dumps(result)


def test_provenance_mismatch_fails_closed(monkeypatch):
    mod = _module()
    monkeypatch.setattr(mod, "git_blob", lambda *_args: b"forged")
    with pytest.raises(mod.P541BR2Error, match="identity mismatch"):
        mod.verified_historical_inputs(REPO_ROOT)


def test_unknown_schema_version_fails_closed():
    mod = _module()
    with pytest.raises(mod.P541BR2Error, match="unknown schema"):
        mod.validate_consumer_contract("future-schema", mod.DETECTOR_VERSION)


def test_unknown_detector_version_fails_closed():
    mod = _module()
    with pytest.raises(mod.P541BR2Error, match="unknown detector"):
        mod.validate_consumer_contract(mod.SCHEMA_VERSION, "future-detector")


def test_canonical_runtime_mismatch_fails_before_artifact_reads(monkeypatch):
    mod = _module()
    called = False

    def forbidden_read(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("artifact read must not begin")

    monkeypatch.setattr(
        mod,
        "canonical_runtime_provenance",
        lambda: {
            "implementation": "CPython",
            "version": "3.14.4",
            "requirement": "CPython==3.9.6",
            "verification": "PASS",
        },
    )
    monkeypatch.setattr(mod, "verified_historical_inputs", forbidden_read)
    with pytest.raises(mod.P541BR2Error, match="canonical generation runtime mismatch"):
        mod.build_artifact(REPO_ROOT)
    assert called is False


def test_strict_json_rejects_duplicate_and_nonfinite_values():
    mod = _module()
    with pytest.raises(mod.P541BR2Error, match="duplicate JSON key"):
        mod.strict_json_bytes(b'{"same":1,"same":2}')
    with pytest.raises(mod.P541BR2Error, match="non-finite"):
        mod.strict_json_bytes(b'{"value":NaN}')


def test_canonical_serialization_failure_remains_terminal():
    mod = _module()
    with pytest.raises(mod.P541BR2Error, match="not finite canonical JSON"):
        mod.canonical_bytes({"not_json": object()})


def test_findings_publish_separate_resolved_api_and_syntax_fields():
    api = _analyze("import sqlite3\ndef f():\n    sqlite3.connect('x.db')\n")
    api_finding = api["evidence"]["database_access"]["findings"][0]
    assert api_finding["resolved_api"] == "sqlite3.connect"
    assert api_finding["resolved_syntax"] is None
    assert api_finding["imported_module_path"] is None
    assert "resolved_api_or_syntax" not in api_finding

    syntax = _analyze("if __name__ == '__main__':\n    pass\n")
    syntax_finding = syntax["evidence"]["valid_main_guard"]["findings"][0]
    assert syntax_finding["resolved_api"] is None
    assert syntax_finding["resolved_syntax"] == "__name__ == '__main__'"
    assert syntax_finding["imported_module_path"] is None
    assert "resolved_api_or_syntax" not in syntax_finding


def test_exact_scan_status_taxonomy_is_published_in_order(artifact):
    mod = _module()
    expected = ["complete", "syntax_error", "unreadable", "unsupported"]
    assert list(mod.SCAN_STATUS_TAXONOMY) == expected
    assert artifact["scan_status_taxonomy"] == expected
    assert artifact["detector_contract"]["scan_status_taxonomy"] == expected


def test_all_record_scan_statuses_belong_to_published_taxonomy(artifact):
    taxonomy = set(artifact["scan_status_taxonomy"])
    assert {
        record["scan_status"] for record in artifact["method_classification_records"]
    } <= taxonomy


def test_unrecognized_record_scan_status_fails_closed(artifact):
    mod = _module()
    forged = copy.deepcopy(artifact)
    forged["method_classification_records"][0]["scan_status"] = "future_status"
    with pytest.raises(mod.P541BR2Error, match="scan status mismatch"):
        mod.validate_artifact(forged)


def test_absent_record_scan_status_fails_closed(artifact):
    mod = _module()
    forged = copy.deepcopy(artifact)
    del forged["method_classification_records"][0]["scan_status"]
    with pytest.raises(mod.P541BR2Error, match="scan status mismatch"):
        mod.validate_artifact(forged)


def test_all_artifact_findings_use_exact_field_names(artifact):
    required = {"resolved_api", "resolved_syntax", "imported_module_path"}
    forbidden = {"resolved_api_or_syntax", "imported_module_source"}
    for record in artifact["method_classification_records"]:
        for evidence in record["evidence"].values():
            for finding in evidence["findings"]:
                assert required <= set(finding)
                assert forbidden.isdisjoint(finding)
                assert (finding["resolved_api"] is None) != (
                    finding["resolved_syntax"] is None
                )
                if finding["direct_or_transitive"] == "transitive":
                    assert finding["imported_module_path"]
                else:
                    assert finding["imported_module_path"] is None


def test_artifact_contract_is_complete(artifact):
    mod = _module()
    assert artifact["schema_version"] == mod.SCHEMA_VERSION
    assert artifact["detector_version"] == mod.DETECTOR_VERSION
    assert artifact["runtime_contract"] == {
        "implementation": "CPython",
        "version": "3.9.6",
        "requirement": "CPython==3.9.6",
        "verification": "PASS",
    }
    assert artifact["summary"]["total_records"] == 580
    assert len(artifact["provenance"]["source_manifest"]["ordered_entries"]) == 580
    assert artifact["provenance"]["source_manifest"]["content_read_failures"] == 0
    assert list(artifact["summary"]["scan_status_counts"]) == list(mod.SCAN_STATUS_TAXONOMY)
    assert sum(artifact["summary"]["scan_status_counts"].values()) == 580
    for counts in artifact["summary"]["evidence_status_counts"].values():
        assert set(counts) == set(mod.TRI_STATES)
        assert sum(counts.values()) == 580
    assert set(artifact["provenance"]["historical_inputs"]) == set(mod.HISTORICAL_INPUTS)
    mod.validate_artifact(artifact)


@pytest.mark.parametrize(
    ("field", "message"),
    [
        ("implementation_base_oid", "top-level provenance"),
        ("frozen_source_commit", "top-level provenance"),
    ],
)
def test_top_level_provenance_mismatch_remains_terminal(artifact, field, message):
    mod = _module()
    forged = copy.deepcopy(artifact)
    forged[field] = "0" * 40
    with pytest.raises(mod.P541BR2Error, match=message):
        mod.validate_artifact(forged)


def test_generator_provenance_mismatch_remains_terminal(artifact):
    mod = _module()
    forged = copy.deepcopy(artifact)
    forged["generator"]["sha256"] = "0" * 64
    with pytest.raises(mod.P541BR2Error, match="generator provenance"):
        mod.validate_artifact(forged)


def test_runtime_provenance_mismatch_remains_terminal(artifact):
    mod = _module()
    forged = copy.deepcopy(artifact)
    forged["runtime_contract"]["version"] = "3.14.4"
    with pytest.raises(mod.P541BR2Error, match="runtime provenance"):
        mod.validate_artifact(forged)


@pytest.mark.parametrize("location", ["detector", "provenance"])
def test_nested_runtime_contract_mismatch_remains_terminal(artifact, location):
    mod = _module()
    forged = copy.deepcopy(artifact)
    if location == "detector":
        forged["detector_contract"]["canonical_generation_runtime"] = "CPython==3.14.4"
    else:
        del forged["provenance"]["generation_runtime"]
    with pytest.raises(mod.P541BR2Error, match="runtime contract"):
        mod.validate_artifact(forged)


@pytest.mark.parametrize(
    "mutation",
    [
        "read_failed_decode_succeeded",
        "decode_failed_parse_succeeded",
        "parse_failed_complete",
    ],
)
def test_impossible_scan_phase_transition_is_rejected(artifact, mutation):
    mod = _module()
    forged = copy.deepcopy(artifact)
    record = next(
        item
        for item in forged["method_classification_records"]
        if item["scan_status"] == "unsupported"
    )
    if mutation == "read_failed_decode_succeeded":
        record["scan"]["read_status"] = "failed"
        record["source_identity"]["git_blob_read_status"] = "failed"
        record["source_identity"]["byte_size"] = None
        record["source_identity"]["sha256"] = None
    elif mutation == "decode_failed_parse_succeeded":
        record["scan"]["decode_status"] = "failed"
        record["source_identity"]["utf8_decoding_status"] = "failed"
    else:
        complete = next(
            item
            for item in forged["method_classification_records"]
            if item["scan_status"] == "complete"
        )
        complete["scan"]["parse_status"] = "failed"
    with pytest.raises(mod.P541BR2Error, match="scan phase|complete scan"):
        mod.validate_artifact(forged)


def test_semantically_impossible_low_risk_record_is_rejected(artifact):
    mod = _module()
    forged = copy.deepcopy(artifact)
    record = next(
        item
        for item in forged["method_classification_records"]
        if item["scan_status"] == "complete"
        and item["evidence"]["transitive_external_state"]["state"] == "unknown"
    )
    record["safety_classification"] = {
        "risk_level": "low",
        "low_risk_eligible": True,
        "disposition": "STATIC_LOW_RISK_ELIGIBLE",
        "reasons": [],
    }
    with pytest.raises(mod.P541BR2Error, match="safety classification|unsafe low-risk"):
        mod.validate_artifact(forged)


def test_scan_failure_reason_must_match_failed_phase(artifact):
    mod = _module()
    forged = copy.deepcopy(artifact)
    record = next(
        item
        for item in forged["method_classification_records"]
        if item["scan_status"] == "syntax_error"
    )
    record["scan"]["error"]["code"] = "git_blob_read_failed"
    record["scan"]["error"]["message"] = "git_blob_read_failed"
    record["safety_classification"]["reasons"] = ["git_blob_read_failed"]
    with pytest.raises(mod.P541BR2Error, match="failure reason mismatch"):
        mod.validate_artifact(forged)


def test_conclusive_evidence_cannot_publish_unknown_reason(artifact):
    mod = _module()
    forged = copy.deepcopy(artifact)
    record = next(
        item
        for item in forged["method_classification_records"]
        if item["safety_classification"]["risk_level"] == "low"
    )
    record["evidence"]["transitive_external_state"]["reason"] = (
        "import_resolution_incomplete"
    )
    with pytest.raises(mod.P541BR2Error, match="evidence reason/state mismatch"):
        mod.validate_artifact(forged)


@pytest.mark.parametrize(
    "reason",
    [
        "import_resolution_incomplete:ValueError(secret)",
        "import_resolution_incomplete:/Users/private/source.py",
        "ast_parse_failed:byte=1",
        "utf8_decode_failed:line=1",
        "imported_scan_incomplete; import_resolution_incomplete",
        "import_resolution_incomplete; import_resolution_incomplete",
    ],
)
def test_unknown_evidence_reason_requires_exact_bounded_grammar(artifact, reason):
    mod = _module()
    forged = copy.deepcopy(artifact)
    record = next(
        item
        for item in forged["method_classification_records"]
        if item["evidence"]["transitive_external_state"]["state"] == "unknown"
    )
    record["evidence"]["transitive_external_state"]["reason"] = reason
    with pytest.raises(mod.P541BR2Error, match="unknown evidence reason mismatch"):
        mod.validate_artifact(forged)


@pytest.mark.parametrize(
    "reason",
    [
        "ast_parse_failed:line=1",
        "utf8_decode_failed:byte=0",
        "import_resolution_incomplete",
        "import_resolution_incomplete; imported_scan_incomplete",
        "ambiguous DB-like API could not be resolved",
        "one-hop resolver not supplied",
    ],
)
def test_bounded_unknown_reason_grammar_accepts_generated_forms(reason):
    assert _module()._valid_bounded_failure_reason(reason) is True


def test_aggregate_mismatch_remains_terminal(artifact):
    mod = _module()
    forged = copy.deepcopy(artifact)
    forged["summary"]["risk_level_counts"]["unknown"] += 1
    with pytest.raises(mod.P541BR2Error, match="risk aggregate reconciliation"):
        mod.validate_artifact(forged)


def test_blob_read_failure_retains_order_continues_and_is_byte_deterministic(
    artifact, monkeypatch
):
    mod = _module()
    identities = artifact["provenance"]["source_manifest"]["ordered_entries"]
    blob_counts = {}
    for identity in identities:
        blob_counts[identity["blob_id"]] = blob_counts.get(identity["blob_id"], 0) + 1
    target_index = next(
        index
        for index in range(len(identities) - 2, 9, -1)
        if blob_counts[identities[index]["blob_id"]] == 1
    )
    target = identities[target_index]
    original = mod.git_blob

    def injected(repo_root, blob_id):
        if blob_id == target["blob_id"]:
            raise mod.GitBlobReadError("injected /Users/private/blob failure")
        return original(repo_root, blob_id)

    monkeypatch.setattr(mod, "git_blob", injected)
    first = mod.build_artifact(REPO_ROOT)
    second = mod.build_artifact(REPO_ROOT)
    assert mod.canonical_bytes(first) == mod.canonical_bytes(second)

    expected_paths = [record["source_path"] for record in artifact["method_classification_records"]]
    actual_paths = [record["source_path"] for record in first["method_classification_records"]]
    assert actual_paths == expected_paths
    failed = first["method_classification_records"][target_index]
    assert failed["source_path"] == target["source_path"]
    assert failed["source_identity"]["git_blob_read_status"] == "failed"
    assert failed["source_identity"]["byte_size"] is None
    assert failed["source_identity"]["sha256"] is None
    assert failed["scan_status"] == "unreadable"
    assert failed["scan"]["complete"] is False
    assert failed["scan"]["error"]["code"] == "git_blob_read_failed"
    assert {item["state"] for item in failed["evidence"].values()} == {"unknown"}
    assert failed["safety_classification"]["low_risk_eligible"] is False
    assert first["method_classification_records"][target_index + 1]["source_path"] == expected_paths[
        target_index + 1
    ]
    assert first["provenance"]["source_manifest"]["content_read_failures"] == 1
    assert sum(first["summary"]["scan_status_counts"].values()) == 580
    assert first["summary"]["unknown_scans"] == sum(
        record["scan"]["complete"] is False
        for record in first["method_classification_records"]
    )
    mod.validate_artifact(first)


def test_json_regeneration_equals_committed_json(artifact):
    mod = _module()
    protected_json_path = (REPO_ROOT / mod.OUTPUT_JSON).resolve()
    protected_markdown_path = (REPO_ROOT / mod.OUTPUT_MARKDOWN).resolve()
    assert protected_json_path == PROTECTED_JSON_PATH.resolve()
    assert protected_markdown_path == PROTECTED_MARKDOWN_PATH.resolve()
    _assert_json_self_identity_contract(
        _canonical_json_bytes(artifact),
        generator_path=_canonical_generator_path(),
        protected_json_raw=protected_json_path.read_bytes(),
        protected_markdown_raw=protected_markdown_path.read_bytes(),
    )


def test_markdown_regeneration_equals_committed_markdown(artifact):
    mod = _module()
    protected_json_path = (REPO_ROOT / mod.OUTPUT_JSON).resolve()
    protected_markdown_path = (REPO_ROOT / mod.OUTPUT_MARKDOWN).resolve()
    assert protected_json_path == PROTECTED_JSON_PATH.resolve()
    assert protected_markdown_path == PROTECTED_MARKDOWN_PATH.resolve()
    _assert_markdown_self_identity_contract(
        mod.render_markdown(artifact).encode("utf-8"),
        _canonical_json_bytes(artifact),
        generator_path=_canonical_generator_path(),
        protected_json_raw=protected_json_path.read_bytes(),
        protected_markdown_raw=protected_markdown_path.read_bytes(),
    )


def test_self_identity_contract_allows_exact_two_json_substitutions(
    self_identity_contract_samples,
):
    sample = self_identity_contract_samples
    _assert_json_self_identity_contract(
        sample["regenerated_json"],
        generator_path=sample["generator_path"],
        protected_json_raw=sample["protected_json"],
        protected_markdown_raw=sample["protected_markdown"],
    )


def test_self_identity_contract_allows_exact_one_markdown_substitution(
    self_identity_contract_samples,
):
    sample = self_identity_contract_samples
    _assert_markdown_self_identity_contract(
        sample["regenerated_markdown"],
        sample["regenerated_json"],
        generator_path=sample["generator_path"],
        protected_json_raw=sample["protected_json"],
        protected_markdown_raw=sample["protected_markdown"],
    )


def test_self_identity_contract_rejects_wrong_generator_byte_size(
    self_identity_contract_samples,
):
    sample = self_identity_contract_samples
    forged = _strict_json_load(sample["regenerated_json"])
    forged["generator"]["byte_size"] += 1
    with pytest.raises(AssertionError, match="byte_size"):
        _assert_json_self_identity_contract(
            _canonical_json_bytes(forged),
            generator_path=sample["generator_path"],
            protected_json_raw=sample["protected_json"],
            protected_markdown_raw=sample["protected_markdown"],
        )


def test_self_identity_contract_rejects_wrong_generator_hash(
    self_identity_contract_samples,
):
    sample = self_identity_contract_samples
    forged = _strict_json_load(sample["regenerated_json"])
    forged["generator"]["sha256"] = "0" * 64
    with pytest.raises(AssertionError, match="sha256"):
        _assert_json_self_identity_contract(
            _canonical_json_bytes(forged),
            generator_path=sample["generator_path"],
            protected_json_raw=sample["protected_json"],
            protected_markdown_raw=sample["protected_markdown"],
        )


@pytest.mark.parametrize("variant", ["uppercase", "shortened"])
def test_self_identity_contract_rejects_noncanonical_generator_hash(
    self_identity_contract_samples, variant
):
    sample = self_identity_contract_samples
    forged = _strict_json_load(sample["regenerated_json"])
    current = forged["generator"]["sha256"]
    forged["generator"]["sha256"] = (
        current.upper() if variant == "uppercase" else current[:-1]
    )
    with pytest.raises(AssertionError, match="64-character lowercase hex"):
        _assert_json_self_identity_contract(
            _canonical_json_bytes(forged),
            generator_path=sample["generator_path"],
            protected_json_raw=sample["protected_json"],
            protected_markdown_raw=sample["protected_markdown"],
        )


@pytest.mark.parametrize("field", ["byte_size", "sha256"])
def test_self_identity_contract_rejects_missing_json_identity_field(
    self_identity_contract_samples, field
):
    sample = self_identity_contract_samples
    forged = _strict_json_load(sample["regenerated_json"])
    del forged["generator"][field]
    with pytest.raises(AssertionError, match=f"generator/{field}"):
        _assert_json_self_identity_contract(
            _canonical_json_bytes(forged),
            generator_path=sample["generator_path"],
            protected_json_raw=sample["protected_json"],
            protected_markdown_raw=sample["protected_markdown"],
        )


@pytest.mark.parametrize(
    ("field", "wrong_value"),
    [("byte_size", "304503"), ("sha256", 520313)],
)
def test_self_identity_contract_rejects_wrong_json_identity_type(
    self_identity_contract_samples, field, wrong_value
):
    sample = self_identity_contract_samples
    forged = _strict_json_load(sample["regenerated_json"])
    forged["generator"][field] = wrong_value
    with pytest.raises(AssertionError, match=f"generator/{field}"):
        _assert_json_self_identity_contract(
            _canonical_json_bytes(forged),
            generator_path=sample["generator_path"],
            protected_json_raw=sample["protected_json"],
            protected_markdown_raw=sample["protected_markdown"],
        )


def test_self_identity_contract_rejects_any_third_json_pointer_difference(
    self_identity_contract_samples,
):
    sample = self_identity_contract_samples
    forged = _strict_json_load(sample["regenerated_json"])
    forged["task_id"] += "_DRIFT"
    with pytest.raises(AssertionError, match="closed JSON exception mismatch"):
        _assert_json_self_identity_contract(
            _canonical_json_bytes(forged),
            generator_path=sample["generator_path"],
            protected_json_raw=sample["protected_json"],
            protected_markdown_raw=sample["protected_markdown"],
        )


def test_self_identity_contract_rejects_json_key_order_difference(
    self_identity_contract_samples,
):
    sample = self_identity_contract_samples
    forged = _strict_json_load(sample["regenerated_json"])
    forged["generator"] = dict(reversed(list(forged["generator"].items())))
    with pytest.raises(AssertionError, match="closed JSON exception mismatch"):
        _assert_json_self_identity_contract(
            _canonical_json_bytes(forged),
            generator_path=sample["generator_path"],
            protected_json_raw=sample["protected_json"],
            protected_markdown_raw=sample["protected_markdown"],
        )


def test_self_identity_contract_rejects_json_whitespace_or_serialization_difference(
    self_identity_contract_samples,
):
    sample = self_identity_contract_samples
    marker = b'{\n  "schema_version"'
    assert sample["regenerated_json"].count(marker) == 1
    forged = sample["regenerated_json"].replace(
        marker, b'{\n   "schema_version"', 1
    )
    with pytest.raises(AssertionError, match="JSON bytes differ"):
        _assert_json_self_identity_contract(
            forged,
            generator_path=sample["generator_path"],
            protected_json_raw=sample["protected_json"],
            protected_markdown_raw=sample["protected_markdown"],
        )


def test_self_identity_contract_rejects_duplicate_json_semantic_location(
    self_identity_contract_samples,
):
    sample = self_identity_contract_samples
    sha256 = str(sample["identity"]["sha256"]).encode("ascii")
    line = b'    "sha256": "' + sha256 + b'"\n'
    assert sample["regenerated_json"].count(line) == 1
    forged = sample["regenerated_json"].replace(
        line, line[:-1] + b",\n" + line, 1
    )
    with pytest.raises(AssertionError, match="duplicate JSON key"):
        _assert_json_self_identity_contract(
            forged,
            generator_path=sample["generator_path"],
            protected_json_raw=sample["protected_json"],
            protected_markdown_raw=sample["protected_markdown"],
        )


def test_self_identity_contract_rejects_zero_markdown_sha_lines(
    self_identity_contract_samples,
):
    sample = self_identity_contract_samples
    prefix = b"- Generator SHA-256: `"
    assert sample["regenerated_markdown"].count(prefix) == 1
    forged = sample["regenerated_markdown"].replace(
        prefix, b"- Generator digest: `", 1
    )
    with pytest.raises(AssertionError, match="exactly one Generator SHA-256 line"):
        _assert_markdown_self_identity_contract(
            forged,
            sample["regenerated_json"],
            generator_path=sample["generator_path"],
            protected_json_raw=sample["protected_json"],
            protected_markdown_raw=sample["protected_markdown"],
        )


def test_self_identity_contract_rejects_duplicate_markdown_sha_lines(
    self_identity_contract_samples,
):
    sample = self_identity_contract_samples
    _lines, candidates = _markdown_generator_sha_candidates(
        sample["regenerated_markdown"]
    )
    assert len(candidates) == 1
    line = candidates[0]["line"]
    forged = sample["regenerated_markdown"].replace(line, line + line, 1)
    with pytest.raises(AssertionError, match="exactly one Generator SHA-256 line"):
        _assert_markdown_self_identity_contract(
            forged,
            sample["regenerated_json"],
            generator_path=sample["generator_path"],
            protected_json_raw=sample["protected_json"],
            protected_markdown_raw=sample["protected_markdown"],
        )


def test_self_identity_contract_rejects_wrong_markdown_hash(
    self_identity_contract_samples,
):
    sample = self_identity_contract_samples
    current = str(sample["identity"]["sha256"]).encode("ascii")
    forged = sample["regenerated_markdown"].replace(current, b"0" * 64, 1)
    with pytest.raises(AssertionError, match="inconsistent with regenerated JSON"):
        _assert_markdown_self_identity_contract(
            forged,
            sample["regenerated_json"],
            generator_path=sample["generator_path"],
            protected_json_raw=sample["protected_json"],
            protected_markdown_raw=sample["protected_markdown"],
        )


def test_self_identity_contract_rejects_markdown_hash_inconsistent_with_json(
    self_identity_contract_samples,
):
    sample = self_identity_contract_samples
    current = str(sample["identity"]["sha256"]).encode("ascii")
    forged = sample["regenerated_markdown"].replace(current, b"1" * 64, 1)
    with pytest.raises(AssertionError, match="inconsistent with regenerated JSON"):
        _assert_markdown_self_identity_contract(
            forged,
            sample["regenerated_json"],
            generator_path=sample["generator_path"],
            protected_json_raw=sample["protected_json"],
            protected_markdown_raw=sample["protected_markdown"],
        )


def test_self_identity_contract_rejects_markdown_hash_inconsistent_with_generator_bytes(
    self_identity_contract_samples,
):
    sample = self_identity_contract_samples
    wrong_identity = _generator_identity(Path(__file__).resolve())
    forged_json = _strict_json_load(sample["regenerated_json"])
    forged_json["generator"]["sha256"] = wrong_identity["sha256"]
    current = str(sample["identity"]["sha256"]).encode("ascii")
    forged_markdown = sample["regenerated_markdown"].replace(
        current, str(wrong_identity["sha256"]).encode("ascii"), 1
    )
    with pytest.raises(AssertionError, match="inconsistent with generator bytes"):
        _assert_markdown_self_identity_contract(
            forged_markdown,
            _canonical_json_bytes(forged_json),
            generator_path=sample["generator_path"],
            protected_json_raw=sample["protected_json"],
            protected_markdown_raw=sample["protected_markdown"],
        )


def test_self_identity_contract_rejects_any_second_markdown_line_difference(
    self_identity_contract_samples,
):
    sample = self_identity_contract_samples
    marker = "# P541B R2 — Fail-Closed Structured Evidence Classification".encode(
        "utf-8"
    )
    assert sample["regenerated_markdown"].count(marker) == 1
    forged = sample["regenerated_markdown"].replace(
        marker,
        "# P541B RX — Fail-Closed Structured Evidence Classification".encode("utf-8"),
        1,
    )
    with pytest.raises(AssertionError, match="differs outside the closed exception"):
        _assert_markdown_self_identity_contract(
            forged,
            sample["regenerated_json"],
            generator_path=sample["generator_path"],
            protected_json_raw=sample["protected_json"],
            protected_markdown_raw=sample["protected_markdown"],
        )


def test_self_identity_contract_rejects_protected_json_pin_drift(
    self_identity_contract_samples,
):
    sample = self_identity_contract_samples
    forged_protected = b"X" + sample["protected_json"][1:]
    with pytest.raises(AssertionError, match="protected JSON pin"):
        _assert_json_self_identity_contract(
            sample["regenerated_json"],
            generator_path=sample["generator_path"],
            protected_json_raw=forged_protected,
            protected_markdown_raw=sample["protected_markdown"],
        )


def test_self_identity_contract_rejects_protected_markdown_pin_drift(
    self_identity_contract_samples,
):
    sample = self_identity_contract_samples
    forged_protected = b"X" + sample["protected_markdown"][1:]
    with pytest.raises(AssertionError, match="protected Markdown pin"):
        _assert_markdown_self_identity_contract(
            sample["regenerated_markdown"],
            sample["regenerated_json"],
            generator_path=sample["generator_path"],
            protected_json_raw=sample["protected_json"],
            protected_markdown_raw=forged_protected,
        )


@pytest.mark.parametrize("mutation", ["generator_prefix", "identity_wildcard"])
def test_self_identity_contract_rejects_wildcard_or_prefix_style_behavior(
    self_identity_contract_samples, mutation
):
    sample = self_identity_contract_samples
    forged = _strict_json_load(sample["regenerated_json"])
    if mutation == "generator_prefix":
        forged["generator"]["path"] += ".unexpected"
    else:
        forged["generator"]["sha256_backup"] = forged["generator"]["sha256"]
    with pytest.raises(AssertionError, match="closed JSON exception mismatch"):
        _assert_json_self_identity_contract(
            _canonical_json_bytes(forged),
            generator_path=sample["generator_path"],
            protected_json_raw=sample["protected_json"],
            protected_markdown_raw=sample["protected_markdown"],
        )


def test_json_and_markdown_describe_the_same_finding_and_status_schema(artifact):
    mod = _module()
    markdown = mod.render_markdown(artifact)
    for field in ("resolved_api", "resolved_syntax", "imported_module_path"):
        assert field in artifact["detector_contract"]["finding_fields"]
        assert f"`{field}`" in markdown
    taxonomy = "`complete`, `syntax_error`, `unreadable`, `unsupported`"
    assert artifact["scan_status_taxonomy"] == list(mod.SCAN_STATUS_TAXONOMY)
    assert taxonomy in markdown


def test_historical_p541b_artifacts_remain_unchanged():
    mod = _module()
    for identity in mod.HISTORICAL_INPUTS.values():
        raw = (REPO_ROOT / identity["path"]).read_bytes()
        assert len(raw) == identity["byte_size"]
        assert hashlib.sha256(raw).hexdigest() == identity["sha256"]


def test_static_guard_resolves_aliases_without_generator_self_certification():
    tree = ast.parse(
        "import sqlite3 as s\n"
        "import subprocess as sp\n"
        "connector = s.connect\n"
        "runner = getattr(sp, 'run')\n"
        "loader = __import__\n"
        "dynamic = getattr(sp, member)\n"
        "connector('x.db')\n"
        "runner(['git', 'status'])\n"
        "loader('target')\n"
        "dynamic([])\n"
    )
    names = {name for _node, name in _static_resolved_calls(tree)}
    assert "sqlite3.connect" in names
    assert "subprocess.run" in names
    assert "__import__" in names
    assert "subprocess.<dynamic_getattr>" in names


def test_generator_opens_no_project_database():
    _source, tree = _generator_source_tree()
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert {"sqlite3", "sqlalchemy", "lottery_api.database"}.isdisjoint(imported)
    resolved_calls = _static_resolved_calls(tree)
    call_names = {name.replace("()", "") for _node, name in resolved_calls}
    forbidden_db_leaves = {"connect", "execute", "executemany", "cursor"}
    assert not {
        name
        for name in call_names
        if any(marker in name.lower() for marker in ("sqlite3", "sqlalchemy", "databasemanager"))
        or name.rsplit(".", 1)[-1].lower() in forbidden_db_leaves
    }
    assert {"open", "builtins.open"}.isdisjoint(call_names)

    db_suffix = re.compile(r"(?i)(?:^|[/\\])[^/\\\s]+\.(?:db|sqlite|sqlite3)$")
    string_literals = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]
    assert not [value for value in string_literals if db_suffix.search(value)]

    subprocess_calls = [
        (node, name)
        for node, name in resolved_calls
        if name.startswith("subprocess.")
    ]
    assert subprocess_calls
    for call, name in subprocess_calls:
        assert name == "subprocess.run"
        assert isinstance(call.args[0], ast.List)
        assert isinstance(call.args[0].elts[0], ast.Constant)
        assert call.args[0].elts[0].value == "git"
        assert not any(keyword.arg == "shell" for keyword in call.keywords)


def test_generator_does_not_import_target_modules():
    _source, tree = _generator_source_tree()
    allowed_roots = {
        "__future__", "ast", "hashlib", "json", "posixpath", "re",
        "subprocess", "sys", "collections", "pathlib", "typing",
    }
    imported_roots = {
        alias.name.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert imported_roots <= allowed_roots


def test_generator_does_not_execute_target_modules():
    source, tree = _generator_source_tree()
    resolved_calls = _static_resolved_calls(tree)
    call_names = {name.replace("()", "") for _node, name in resolved_calls}
    forbidden_calls = {
        "exec",
        "eval",
        "compile",
        "__import__",
        "importlib.import_module",
        "runpy.run_module",
        "runpy.run_path",
        "os.system",
        "os.popen",
    }
    assert forbidden_calls.isdisjoint(call_names)
    assert not {
        name
        for name in call_names
        if "<dynamic_getattr>" in name
        and name.split(".", 1)[0]
        in {"builtins", "importlib", "os", "runpy", "subprocess"}
    }
    assert "__import__(" not in source
    assert "exec(" not in source
    imported_roots = {
        alias.name.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert {"importlib", "runpy"}.isdisjoint(imported_roots)
    for node, name in resolved_calls:
        if not name.startswith("subprocess."):
            continue
        assert name == "subprocess.run"
        assert isinstance(node.args[0], ast.List)
        assert isinstance(node.args[0].elts[0], ast.Constant)
        assert node.args[0].elts[0].value == "git"
        assert not any(keyword.arg == "shell" for keyword in node.keywords)
    assert "git_tree_entries" in source and "git_blob" in source


def test_branch_diff_contains_only_authorized_paths():
    mod = _module()
    completed = subprocess.run(
        ["git", "diff", "--name-only", mod.BASE_MAIN_COMMIT],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert set(completed.stdout.splitlines()) == {
        "analysis/p541b_r2_biglotto_legacy_method_classification_audit.py",
        "tests/test_p541b_r2_biglotto_legacy_method_classification_audit.py",
        "outputs/research/p541b_r2_biglotto_legacy_method_classification_audit_20260711.json",
        "outputs/research/p541b_r2_biglotto_legacy_method_classification_audit_20260711.md",
    }


def test_corrected_counts_are_not_historical_acceptance_invariants(artifact):
    assert artifact["downstream_contract"]["historical_p541c_counts_or_shortlist_preserved"] is False
    assert artifact["downstream_contract"]["p541c_regeneration_required"] is True
    assert artifact["downstream_contract"]["pr_663_mutated"] is False
