"""Focused tests for P541B-R2 fail-closed static evidence remediation."""

from __future__ import annotations

import ast
import inspect
import json
import os
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _module():
    from analysis import p541b_r2_biglotto_legacy_method_classification_audit as mod

    return mod


@pytest.fixture(scope="module")
def artifact():
    return _module().build_artifact(REPO_ROOT)


def _analyze(source: str, path: str = "sample.py"):
    return _module().analyze_source_bytes(path, source.encode("utf-8"), "1" * 40)


def test_generator_has_no_database_or_legacy_execution_interface():
    mod = _module()
    source = inspect.getsource(mod)
    tree = ast.parse(source)
    imported_roots = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in (node.names if isinstance(node, ast.Import) else [ast.alias(node.module or "")])
    }
    assert not imported_roots & {
        "sqlite3", "sqlalchemy", "requests", "httpx", "aiohttp", "importlib",
    }
    assert "exec(" not in source
    assert "__import__(" not in source
    assert "FROZEN_SOURCE_COMMIT" in source
    assert "git ls-tree + git cat-file blob" in source


def test_exact_main_guard_accepts_only_canonical_forms():
    mod = _module()
    canonical = ast.parse("if __name__ == '__main__':\n    pass\n").body[0]
    reversed_form = ast.parse("if '__main__' == __name__:\n    pass\n").body[0]
    malformed = ast.parse("if __name__ == '_main':\n    pass\n").body[0]
    chained = ast.parse("if __name__ == '__main__' == marker:\n    pass\n").body[0]
    assert mod.is_valid_main_guard_test(canonical.test)
    assert mod.is_valid_main_guard_test(reversed_form.test)
    assert not mod.is_valid_main_guard_test(malformed.test)
    assert not mod.is_valid_main_guard_test(chained.test)


def test_malformed_main_guard_is_explicit_and_does_not_suppress_import_time():
    result = _analyze(
        "def main():\n"
        "    return 1\n"
        "if __name__ == '_main':\n"
        "    main()\n"
    )
    assert result["scan"]["complete"] is True
    assert result["evidence"]["valid_main_guard"]["status"] == "not_detected"
    assert result["evidence"]["malformed_main_guard"]["status"] == "detected"
    assert result["evidence"]["import_time_execution"]["status"] == "detected"
    assert result["safety_classification"]["low_risk_eligible"] is False


def test_ast_parse_failure_sets_every_evidence_category_unknown():
    result = _analyze("this is not valid python !!!\n")
    assert result["scan"] == {
        "status": "unknown",
        "complete": False,
        "reason": "AST parse failure: invalid syntax (line 1)",
    }
    assert {
        evidence["status"] for evidence in result["evidence"].values()
    } == {"unknown"}
    assert result["safety_classification"] == {
        "risk_level": "unknown",
        "low_risk_eligible": False,
        "disposition": "BLOCKED_UNKNOWN",
        "reasons": ["AST parse failure: invalid syntax (line 1)"],
    }


def test_non_utf8_and_unsupported_structures_fail_closed():
    mod = _module()
    decoded = mod.analyze_source_bytes("bad.py", b"\xff", "2" * 40)
    assert decoded["scan"]["status"] == "unknown"
    starred = _analyze("from mystery import *\n")
    assert starred["scan"]["status"] == "unknown"
    dynamic = _analyze("import importlib\nplugin = importlib.import_module(name)\n")
    assert dynamic["scan"]["status"] == "unknown"


def test_alias_aware_database_filesystem_network_and_subprocess_detection():
    result = _analyze(
        "import sqlite3 as sql\n"
        "from pathlib import Path as P\n"
        "from requests import get as fetch\n"
        "import subprocess as sp\n"
        "from lottery_api.database import DatabaseManager as DM\n"
        "manager = DM()\n"
        "def work():\n"
        "    sql.connect('x')\n"
        "    manager.execute('select 1')\n"
        "    P('x').write_text('x')\n"
        "    fetch('https://example.invalid')\n"
        "    sp.run(['true'])\n"
    )
    evidence = result["evidence"]
    assert evidence["database_access"]["status"] == "detected"
    assert evidence["filesystem_write"]["status"] == "detected"
    assert evidence["network_io"]["status"] == "detected"
    assert evidence["subprocess_execution"]["status"] == "detected"
    assert result["safety_classification"]["risk_level"] == "high"


def test_sqlalchemy_and_db_manager_aliases_are_detected():
    result = _analyze(
        "from sqlalchemy import create_engine as engine\n"
        "from lottery_api.database import db_manager as singleton\n"
        "def work():\n"
        "    engine('sqlite://')\n"
        "    singleton.execute('select 1')\n"
    )
    locations = result["evidence"]["database_access"]["locations"]
    assert result["evidence"]["database_access"]["status"] == "detected"
    assert any("sqlalchemy.create_engine" in item["resolved_call"] for item in locations)
    assert any("db_manager.execute" in item["resolved_call"] for item in locations)


def test_path_write_and_dynamic_open_mode_are_fail_closed():
    path_write = _analyze("from pathlib import Path\nPath('x').write_bytes(b'x')\n")
    assert path_write["evidence"]["filesystem_write"]["status"] == "detected"
    dynamic_mode = _analyze("mode = choose_mode()\nopen('x', mode)\n")
    assert dynamic_mode["scan"]["status"] == "unknown"
    assert dynamic_mode["safety_classification"]["disposition"] == "BLOCKED_UNKNOWN"


def test_valid_main_guard_only_suppresses_import_time_execution():
    result = _analyze(
        "import requests as rq\n"
        "def main():\n"
        "    rq.get('https://example.invalid')\n"
        "if __name__ == '__main__':\n"
        "    main()\n"
    )
    assert result["evidence"]["valid_main_guard"]["status"] == "detected"
    assert result["evidence"]["import_time_execution"]["status"] == "not_detected"
    assert result["evidence"]["network_io"]["status"] == "detected"
    assert result["safety_classification"]["risk_level"] == "high"


def test_low_risk_requires_complete_scan_and_every_risk_category_not_detected():
    result = _analyze(
        "def choose_numbers(values):\n"
        "    return sorted(values)[:6]\n"
        "if __name__ == '__main__':\n"
        "    choose_numbers([])\n"
    )
    mod = _module()
    assert result["scan"]["complete"] is True
    assert all(
        result["evidence"][key]["status"] == "not_detected"
        for key in mod.RISK_EVIDENCE_KEYS
    )
    assert result["safety_classification"] == {
        "risk_level": "low",
        "low_risk_eligible": True,
        "disposition": "STATIC_LOW_RISK_ELIGIBLE",
        "reasons": [],
    }


def test_pinned_historical_inputs_and_frozen_corpus_are_exact():
    mod = _module()
    historical, provenance = mod.verified_historical_inputs(REPO_ROOT)
    assert len(historical["method_classification_records"]) == 580
    assert {item["verification"] for item in provenance.values()} == {"PASS"}
    paths = [item["source_path"] for item in historical["method_classification_records"]]
    assert len(paths) == len(set(paths)) == 580
    entries = mod.git_tree_entries(REPO_ROOT, mod.FROZEN_SOURCE_COMMIT, paths)
    assert len(entries) == 580
    assert {item["type"] for item in entries.values()} == {"blob"}


def test_artifact_has_complete_tri_state_contract(artifact):
    mod = _module()
    assert artifact["schema_version"] == mod.SCHEMA_VERSION
    assert artifact["summary"]["total_records"] == 580
    assert (
        artifact["summary"]["complete_scans"]
        + artifact["summary"]["unknown_scans"]
        == 580
    )
    assert artifact["summary"]["unknown_scans"] >= 1
    assert artifact["provenance"]["source_manifest"]["verification"] == "PASS"
    for record in artifact["method_classification_records"]:
        assert set(record["evidence"]) == set(mod.ALL_EVIDENCE_KEYS)
        assert {
            item["status"] for item in record["evidence"].values()
        } <= mod.TRI_STATES


def test_historical_boolean_evidence_is_not_republished_as_current(artifact):
    serialized = json.dumps(artifact, ensure_ascii=False)
    assert "module_level_db_call=False" not in serialized
    assert "uses_db_anywhere=False" not in serialized
    assert "has_main_guard=False" not in serialized
    assert all(
        "evidence" not in record["historical_p541b_classification"]
        for record in artifact["method_classification_records"]
    )


def test_historical_artifacts_are_superseded_not_overwritten(artifact):
    mod = _module()
    assert artifact["supersedes"]["overwrite_policy"] == "HISTORICAL_ARTIFACTS_PRESERVED"
    assert mod.OUTPUT_JSON.name.startswith("p541b_r2_")
    assert mod.OUTPUT_MARKDOWN.name.startswith("p541b_r2_")
    assert str(mod.OUTPUT_JSON) not in artifact["supersedes"]["artifacts"]
    assert str(mod.OUTPUT_MARKDOWN) not in artifact["supersedes"]["artifacts"]


def test_p541c_regeneration_is_explicit_and_pr663_is_not_mutated(artifact):
    contract = artifact["downstream_contract"]
    assert contract["p541c_regeneration_required"] is True
    assert contract["historical_p541c_counts_or_shortlist_preserved"] is False
    assert contract["pr_663_mutated"] is False
    assert "must not coerce unknown to false" in contract["consumer_requirement"]


def test_committed_outputs_match_deterministic_regeneration(artifact):
    mod = _module()
    expected_json = (
        json.dumps(artifact, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    ).encode("utf-8")
    expected_markdown = mod.render_markdown(artifact).encode("utf-8")
    assert (REPO_ROOT / mod.OUTPUT_JSON).read_bytes() == expected_json
    assert (REPO_ROOT / mod.OUTPUT_MARKDOWN).read_bytes() == expected_markdown


def test_only_authorized_paths_are_new_or_modified():
    completed = os.popen(
        f"git -C {REPO_ROOT} diff --name-only { _module().BASE_MAIN_COMMIT }"
    ).read().splitlines()
    assert set(completed) <= {
        "analysis/p541b_r2_biglotto_legacy_method_classification_audit.py",
        "tests/test_p541b_r2_biglotto_legacy_method_classification_audit.py",
        "outputs/research/p541b_r2_biglotto_legacy_method_classification_audit_20260711.json",
        "outputs/research/p541b_r2_biglotto_legacy_method_classification_audit_20260711.md",
    }
