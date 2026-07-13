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
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _module():
    from analysis import p541b_r2_biglotto_legacy_method_classification_audit as mod

    return mod


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
    expected = json.dumps(artifact, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    assert (REPO_ROOT / mod.OUTPUT_JSON).read_text(encoding="utf-8") == expected


def test_markdown_regeneration_equals_committed_markdown(artifact):
    mod = _module()
    assert (REPO_ROOT / mod.OUTPUT_MARKDOWN).read_text(encoding="utf-8") == mod.render_markdown(artifact)


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
