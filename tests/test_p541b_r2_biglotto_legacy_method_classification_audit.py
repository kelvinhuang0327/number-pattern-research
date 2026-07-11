"""Focused synthetic and deterministic tests for the P541B-R2 evidence audit."""

from __future__ import annotations

import ast
import copy
import hashlib
import inspect
import json
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


def _generator_source_tree():
    source = inspect.getsource(_module())
    return source, ast.parse(source)


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
    assert {item["state"] for item in result["evidence"].values()} == {"unknown"}


def test_unreadable_input_produces_unknown():
    mod = _module()
    result = mod.analyze_source_bytes("bad.py", b"\xff", "2" * 40)
    assert result["scan_status"] == "unreadable"
    assert {item["state"] for item in result["evidence"].values()} == {"unknown"}


def test_unsupported_input_produces_unknown():
    result = _analyze("from mystery import *\n")
    assert result["scan_status"] == "unsupported"
    assert result["safety_classification"]["risk_level"] == "unknown"


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


def test_one_hop_invoked_constructor_effect_detected(tmp_path):
    repo, commit = _synthetic_repo(
        tmp_path,
        {
            "main.py": "from helper import Worker\nWorker()\n",
            "helper.py": "import sqlite3\nclass Worker:\n    def __init__(self):\n        sqlite3.connect('x.db')\n",
        },
    )
    assert _one_hop(repo, commit, "main.py")["state"] == "detected"


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


def test_missing_blob_fails_closed():
    mod = _module()
    with pytest.raises(mod.P541BR2Error, match="corpus incomplete"):
        mod.require_frozen_entries(["missing.py"], {})


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


def test_strict_json_rejects_duplicate_and_nonfinite_values():
    mod = _module()
    with pytest.raises(mod.P541BR2Error, match="duplicate JSON key"):
        mod.strict_json_bytes(b'{"same":1,"same":2}')
    with pytest.raises(mod.P541BR2Error, match="non-finite"):
        mod.strict_json_bytes(b'{"value":NaN}')


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
    assert artifact["summary"]["total_records"] == 580
    assert len(artifact["provenance"]["source_manifest"]["ordered_entries"]) == 580
    assert set(artifact["provenance"]["historical_inputs"]) == set(mod.HISTORICAL_INPUTS)
    mod.validate_artifact(artifact)


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


def test_generator_does_not_import_target_modules():
    _source, tree = _generator_source_tree()
    allowed_roots = {
        "__future__", "ast", "hashlib", "json", "posixpath", "re",
        "subprocess", "collections", "pathlib", "typing",
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
    call_names = {
        ast.unparse(node.func)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    }
    assert {"exec", "eval", "compile", "__import__", "importlib.import_module"}.isdisjoint(
        call_names
    )
    assert "__import__(" not in source
    assert "exec(" not in source
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
