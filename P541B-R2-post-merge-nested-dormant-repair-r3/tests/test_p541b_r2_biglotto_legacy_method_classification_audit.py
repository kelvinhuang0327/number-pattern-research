"""Focused synthetic and deterministic tests for the P541B-R2 evidence audit."""

from __future__ import annotations

import ast
import copy
import hashlib
import inspect
import itertools
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


def test_artifact_r9_detector_v11_preserves_evidence_schema(artifact):
    mod = _module()
    assert mod.DETECTOR_VERSION == "p541b-r2-detector-v11"
    assert artifact["schema_version"] == "p541b-r2-evidence-v1"
    assert artifact["detector_version"] == mod.DETECTOR_VERSION
    for record in artifact["method_classification_records"]:
        assert set(record["evidence"]) == set(mod.ALL_EVIDENCE_KEYS)
        for evidence in record["evidence"].values():
            assert set(evidence) <= {
                "state", "scope", "detector_id", "findings", "reason"
            }
            assert evidence["detector_id"] == mod.DETECTOR_VERSION


def test_artifact_r9_exact_r8_record_semantics_are_preserved(artifact):
    mod = _module()
    projection = []
    for record in artifact["method_classification_records"]:
        item = copy.deepcopy(record)
        item.pop("detector_version")
        for evidence in item["evidence"].values():
            evidence.pop("detector_id")
        projection.append(item)
    assert len(projection) == 580
    assert hashlib.sha256(mod.canonical_bytes(projection)).hexdigest() == (
        "f61f79d6cace713143c3a828a36d529b459f76142fdfa5c4d42552c52285612a"
    )
    assert artifact["summary"]["direct_finding_count"] == 3548
    assert artifact["summary"]["transitive_finding_count"] == 11484
    assert artifact["summary"]["risk_level_counts"] == {
        "high": 71,
        "low": 24,
        "medium": 4,
        "unknown": 481,
    }


def test_artifact_r9_exact_low_24_membership_and_gating_are_preserved(artifact):
    expected = {
        "tools/advanced_prediction_engine.py",
        "tools/analyze_theoretical_vs_actual.py",
        "tools/baseline_validator.py",
        "tools/big_lotto_exhaustive_audit.py",
        "tools/quick_ml_predict.py",
        "analysis/p246h_advanced_learning_scheduler_trace.py",
        "analysis/p246i_big_lotto_population_assertion_cleanup.py",
        "ai_lab/automl_biglotto/__init__.py",
        "ai_lab/automl_biglotto/config.py",
        "recovered_strategies/biglotto/__init__.py",
        "recovered_strategies/biglotto/historical_adapters.py",
        "lottery_api/models/advanced_strategies.py",
        "lottery_api/models/autogluon_model.py",
        "lottery_api/models/bayesian_ensemble.py",
        "lottery_api/models/big_lotto_optimizer.py",
        "lottery_api/models/core_satellite.py",
        "lottery_api/models/lottery_graph.py",
        "lottery_api/models/negative_selector.py",
        "lottery_api/models/optimized_ensemble.py",
        "lottery_api/models/p47_wave4_powerlotto_adapters.py",
        "lottery_api/models/power_lotto_second_zone.py",
        "lottery_api/models/regime_detector.py",
        "lottery_api/models/social_wisdom_predictor.py",
        "lottery_api/models/zone_split.py",
    }
    low_records = [
        record
        for record in artifact["method_classification_records"]
        if record["safety_classification"]["risk_level"] == "low"
    ]
    assert {record["source_path"] for record in low_records} == expected
    assert len(low_records) == 24
    for record in low_records:
        assert record["scan"]["complete"] is True
        assert record["safety_classification"]["low_risk_eligible"] is True
        assert record["safety_classification"]["disposition"] == (
            "STATIC_LOW_RISK_ELIGIBLE"
        )
        assert all(
            evidence["state"] != "unknown"
            for evidence in record["evidence"].values()
        )
    assert {
        "lottery_api/models/advanced_strategies.py",
        "lottery_api/models/power_lotto_second_zone.py",
    } <= {record["source_path"] for record in low_records}


def test_artifact_r9_ai_config_optimizer_retains_exact_r8_reason(artifact):
    record = next(
        item
        for item in artifact["method_classification_records"]
        if item["source_path"] == "tools/ai_config_optimizer.py"
    )
    evidence = record["evidence"]["transitive_external_state"]
    assert evidence["state"] == "unknown"
    assert evidence["findings"] == []
    assert evidence["reason"] == "imported_scan_incomplete"
    assert record["safety_classification"] == {
        "risk_level": "unknown",
        "low_risk_eligible": False,
        "disposition": "NEEDS_CTO_REVIEW_UNKNOWN",
        "reasons": ["unknown:transitive_external_state"],
    }


def test_artifact_r9_independent_r8_record_and_summary_projection(artifact):
    r8_commit = "1ffdec601d0b3908d9f6374d9934a6d8f883c81f"
    r8_path = (
        "outputs/research/"
        "p541b_r2_biglotto_legacy_method_classification_audit_20260711.json"
    )
    r8_sha256 = (
        "6e1c84b899dbc0b8a662f54c378d0bb2c8812b53b0377447c9c7e94b52fda61e"
    )
    normalized_sha256 = (
        "f61f79d6cace713143c3a828a36d529b459f76142fdfa5c4d42552c52285612a"
    )

    top_level_fields = {
        "schema_version",
        "detector_version",
        "scan_status_taxonomy",
        "task_id",
        "implementation_base_oid",
        "frozen_source_commit",
        "generated_at_utc",
        "generator",
        "runtime_contract",
        "provenance",
        "method_classification_records",
        "summary",
        "detector_contract",
        "supersedes",
        "downstream_contract",
        "limitations",
        "disclaimer",
    }
    record_fields = {
        "method_id",
        "source_path",
        "schema_version",
        "detector_version",
        "source_identity",
        "scan_status",
        "scan",
        "evidence",
        "safety_classification",
        "historical_p541b_classification",
    }
    evidence_keys = (
        "database_access",
        "filesystem_write",
        "network_io",
        "process_execution",
        "other_external_effect",
        "transitive_external_state",
        "import_time_execution",
        "hardcoded_absolute_path",
        "hardcoded_draw_or_date",
        "database_like_path",
        "external_service_url",
        "filesystem_read",
        "valid_main_guard",
        "malformed_main_guard",
    )
    risk_evidence_keys = (
        "database_access",
        "filesystem_write",
        "network_io",
        "process_execution",
        "other_external_effect",
        "transitive_external_state",
        "import_time_execution",
        "hardcoded_absolute_path",
        "hardcoded_draw_or_date",
        "database_like_path",
        "external_service_url",
    )
    summary_fields = {
        "total_records",
        "complete_scans",
        "unknown_scans",
        "scan_status_counts",
        "risk_level_counts",
        "disposition_counts",
        "evidence_status_counts",
        "direct_finding_count",
        "transitive_finding_count",
    }
    scan_statuses = (
        "complete",
        "syntax_error",
        "unreadable",
        "unsupported",
    )
    evidence_states = ("detected", "not_detected", "unknown")
    risk_levels = ("high", "low", "medium", "unknown")
    dispositions = (
        "BLOCKED_EXTERNAL_EFFECT",
        "BLOCKED_STATIC_RISK",
        "BLOCKED_UNKNOWN",
        "NEEDS_CTO_REVIEW_UNKNOWN",
        "STATIC_LOW_RISK_ELIGIBLE",
    )
    low_paths = {
        "tools/advanced_prediction_engine.py",
        "tools/analyze_theoretical_vs_actual.py",
        "tools/baseline_validator.py",
        "tools/big_lotto_exhaustive_audit.py",
        "tools/quick_ml_predict.py",
        "analysis/p246h_advanced_learning_scheduler_trace.py",
        "analysis/p246i_big_lotto_population_assertion_cleanup.py",
        "ai_lab/automl_biglotto/__init__.py",
        "ai_lab/automl_biglotto/config.py",
        "recovered_strategies/biglotto/__init__.py",
        "recovered_strategies/biglotto/historical_adapters.py",
        "lottery_api/models/advanced_strategies.py",
        "lottery_api/models/autogluon_model.py",
        "lottery_api/models/bayesian_ensemble.py",
        "lottery_api/models/big_lotto_optimizer.py",
        "lottery_api/models/core_satellite.py",
        "lottery_api/models/lottery_graph.py",
        "lottery_api/models/negative_selector.py",
        "lottery_api/models/optimized_ensemble.py",
        "lottery_api/models/p47_wave4_powerlotto_adapters.py",
        "lottery_api/models/power_lotto_second_zone.py",
        "lottery_api/models/regime_detector.py",
        "lottery_api/models/social_wisdom_predictor.py",
        "lottery_api/models/zone_split.py",
    }

    def strict_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    def reject_nonfinite(token):
        raise ValueError(f"non-finite JSON constant: {token}")

    def canonical_bytes(value):
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")

    completed = subprocess.run(
        ["git", "cat-file", "blob", f"{r8_commit}:{r8_path}"],
        cwd=REPO_ROOT,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    r8_raw = completed.stdout
    assert len(r8_raw) == 10_490_289
    assert hashlib.sha256(r8_raw).hexdigest() == r8_sha256

    r8 = json.loads(
        r8_raw.decode("utf-8", errors="strict"),
        object_pairs_hook=strict_object,
        parse_constant=reject_nonfinite,
    )

    assert set(r8) == top_level_fields
    assert set(artifact) == top_level_fields
    assert r8["schema_version"] == "p541b-r2-evidence-v1"
    assert artifact["schema_version"] == "p541b-r2-evidence-v1"
    assert r8["detector_version"] == "p541b-r2-detector-v10"
    assert artifact["detector_version"] == "p541b-r2-detector-v11"
    assert r8["scan_status_taxonomy"] == list(scan_statuses)
    assert artifact["scan_status_taxonomy"] == list(scan_statuses)

    def normalized_records(payload):
        records = copy.deepcopy(payload["method_classification_records"])
        assert len(records) == 580
        for record in records:
            assert set(record) == record_fields
            assert record["detector_version"] == payload["detector_version"]
            assert set(record["evidence"]) == set(evidence_keys)
            record.pop("detector_version")
            for key in evidence_keys:
                item = record["evidence"][key]
                expected_fields = {
                    "state",
                    "scope",
                    "detector_id",
                    "findings",
                }
                if item["state"] == "unknown":
                    expected_fields.add("reason")
                assert set(item) == expected_fields
                assert item["detector_id"] == payload["detector_version"]
                item.pop("detector_id")
        return records

    r8_records = normalized_records(r8)
    r9_records = normalized_records(artifact)

    # Indexing avoids truncation and gives Python 3.9-compatible ordered proof.
    for index in range(580):
        assert r9_records[index] == r8_records[index], (
            f"normalized record drift at index {index}: "
            f"{r8_records[index]['source_path']}"
        )

    assert hashlib.sha256(canonical_bytes(r8_records)).hexdigest() == (
        normalized_sha256
    )
    assert hashlib.sha256(canonical_bytes(r9_records)).hexdigest() == (
        normalized_sha256
    )

    def exact_counts(values, allowed):
        counts = {value: 0 for value in allowed}
        for value in values:
            assert value in counts
            counts[value] += 1
        return counts

    def recalculate_summary(payload):
        records = payload["method_classification_records"]
        assert set(payload["summary"]) == summary_fields
        for record in records:
            for evidence in record["evidence"].values():
                for finding in evidence["findings"]:
                    assert finding["direct_or_transitive"] in {
                        "direct",
                        "transitive",
                    }
        return {
            "total_records": len(records),
            "complete_scans": sum(
                record["scan"]["complete"] is True for record in records
            ),
            "unknown_scans": sum(
                record["scan"]["complete"] is False for record in records
            ),
            "scan_status_counts": exact_counts(
                (record["scan_status"] for record in records),
                scan_statuses,
            ),
            "risk_level_counts": exact_counts(
                (
                    record["safety_classification"]["risk_level"]
                    for record in records
                ),
                risk_levels,
            ),
            "disposition_counts": exact_counts(
                (
                    record["safety_classification"]["disposition"]
                    for record in records
                ),
                dispositions,
            ),
            "evidence_status_counts": {
                key: exact_counts(
                    (record["evidence"][key]["state"] for record in records),
                    evidence_states,
                )
                for key in evidence_keys
            },
            "direct_finding_count": sum(
                finding["direct_or_transitive"] == "direct"
                for record in records
                for evidence in record["evidence"].values()
                for finding in evidence["findings"]
            ),
            "transitive_finding_count": sum(
                len(
                    record["evidence"]["transitive_external_state"][
                        "findings"
                    ]
                )
                for record in records
            ),
        }

    r8_summary = recalculate_summary(r8)
    r9_summary = recalculate_summary(artifact)
    assert r8_summary == r8["summary"]
    assert r9_summary == artifact["summary"]
    assert r9_summary == r8_summary
    assert r9_summary["total_records"] == 580
    assert r9_summary["direct_finding_count"] == 3548
    assert r9_summary["transitive_finding_count"] == 11484
    assert r9_summary["risk_level_counts"] == {
        "high": 71,
        "low": 24,
        "medium": 4,
        "unknown": 481,
    }

    current_low = [
        record
        for record in artifact["method_classification_records"]
        if record["safety_classification"]["risk_level"] == "low"
    ]
    assert len(current_low) == 24
    assert {record["source_path"] for record in current_low} == low_paths
    for record in current_low:
        assert record["scan"]["complete"] is True
        assert record["safety_classification"] == {
            "risk_level": "low",
            "low_risk_eligible": True,
            "disposition": "STATIC_LOW_RISK_ELIGIBLE",
            "reasons": [],
        }
        assert all(
            record["evidence"][key]["state"] == "not_detected"
            for key in risk_evidence_keys
        )

    ai_records = [
        record
        for record in artifact["method_classification_records"]
        if record["source_path"] == "tools/ai_config_optimizer.py"
    ]
    assert len(ai_records) == 1
    ai_record = ai_records[0]
    ai_evidence = ai_record["evidence"]["transitive_external_state"]
    assert ai_evidence["state"] == "unknown"
    assert ai_evidence["findings"] == []
    assert ai_evidence["reason"] == "imported_scan_incomplete"
    assert ai_record["safety_classification"] == {
        "risk_level": "unknown",
        "low_risk_eligible": False,
        "disposition": "NEEDS_CTO_REVIEW_UNKNOWN",
        "reasons": ["unknown:transitive_external_state"],
    }


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
        "def choose_enabled():\n"
        "    return False\n"
        "enabled = choose_enabled()\n"
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
    assert [
        (finding["resolved_api"], finding["imported_module_path"])
        for finding in result["findings"]
    ] == [("sqlite3.connect", "danger/hidden.py")]
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
    assert [
        (finding["resolved_api"], finding["imported_module_path"])
        for finding in result["findings"]
    ] == [("sqlite3.connect", "danger/hidden.py")]
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


def test_conditional_nested_project_import_preserves_promoted_effect(tmp_path):
    repo, commit = _synthetic_repo(
        tmp_path,
        {
            "main.py": (
                "def choose_enabled():\n"
                "    return True\n"
                "enabled = choose_enabled()\n"
                "if enabled:\n"
                "    from helper import connect\n"
                "    connect()\n"
            ),
            "helper.py": "import sqlite3\nsqlite3.connect('x.db')\n",
        },
    )
    result = _one_hop(repo, commit, "main.py")
    assert result["state"] == "unknown"
    assert result["reason"] == "import_resolution_incomplete"
    assert any(
        finding["resolved_api"] == "sqlite3.connect"
        for finding in result["findings"]
    )


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
                "def choose_enabled():\n"
                "    return False\n"
                "enabled = choose_enabled()\n"
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
    assert any(
        finding["resolved_api"] == "requests.get"
        for finding in result["findings"]
    )
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
                "def choose_enabled():\n"
                "    return False\n"
                "enabled = choose_enabled()\n"
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
    assert any(
        finding["resolved_api"] == "sqlite3.connect"
        for finding in result["findings"]
    )


def test_conditional_imported_factory_dispatch_is_unknown(tmp_path):
    repo, commit = _synthetic_repo(
        tmp_path,
        {
            "main.py": (
                "from helper import Worker\n"
                "def choose_enabled():\n"
                "    return True\n"
                "enabled = choose_enabled()\n"
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
    assert any(
        finding["resolved_api"] == "requests.get"
        for finding in result["findings"]
    )


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
    assert any(
        finding["resolved_api"] == "requests.get"
        for finding in result["findings"]
    )


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
    assert any(
        finding["resolved_api"] == "requests.get"
        for finding in result["findings"]
    )


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
    reasons = frozenset(result["reason"].split("; "))
    assert reasons in (
        frozenset({"import_resolution_incomplete"}),
        frozenset({
            "import_resolution_incomplete",
            "imported_scan_incomplete",
        }),
    )
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
            "    coroutine = forward(dangerous)\n"
            "    try:\n"
            "        coroutine.send(None)\n"
            "    except StopIteration:\n"
            "        pass\n"
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


def test_r6_dynamic_subscript_storage_preserves_concrete_candidate(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    def choose_key():\n"
            "        return 'other'\n"
            "    callbacks = {'safe': safe}\n"
            "    key = choose_key()\n"
            "    callbacks[key] = dangerous\n"
            "    register(callbacks['safe'])\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


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
            "import sqlite3\n"
            "def dangerous():\n"
            "    import deeper\n"
            "    sqlite3.connect('x.db')\n"
            "class AsyncCallbacks:\n"
            "    def __aiter__(self):\n"
            "        return self\n"
            "    async def __anext__(self):\n"
            "        return dangerous\n"
            "async def run():\n"
            "    async for f in AsyncCallbacks():\n"
            "        f()\n"
            "        break\n"
            "coroutine = run()\n"
            "try:\n"
            "    coroutine.send(None)\n"
            "except StopIteration:\n"
            "    pass\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


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
            "import sqlite3\n"
            "def dangerous():\n"
            "    import deeper\n"
            "    sqlite3.connect('x.db')\n"
            "class Manager:\n"
            "    async def __aenter__(self):\n"
            "        return dangerous\n"
            "    async def __aexit__(self, exc_type, exc, traceback):\n"
            "        return False\n"
            "async def run():\n"
            "    async with Manager() as f:\n"
            "        f()\n"
            "coroutine = run()\n"
            "try:\n"
            "    coroutine.send(None)\n"
            "except StopIteration:\n"
            "    pass\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


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
        (
            "    def choose_key():\n"
            "        return 0\n"
            "    callbacks[choose_key()] = safe\n"
        ),
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


@pytest.mark.parametrize(
    "flow_source",
    [
        (
            "    callbacks = []\n"
            "    while True:\n"
            "        for callback in callbacks:\n"
            "            callback()\n"
            "        callbacks.append(dangerous)\n"
        ),
        (
            "    callbacks = []\n"
            "    for _ in range(2):\n"
            "        for callback in callbacks:\n"
            "            callback()\n"
            "        callbacks.append(dangerous)\n"
        ),
        (
            "    callbacks = []\n"
            "    for _ in range(2):\n"
            "        for callback in callbacks:\n"
            "            callback()\n"
            "        callbacks += [dangerous]\n"
        ),
        (
            "    callbacks = []\n"
            "    for _ in range(2):\n"
            "        for callback in callbacks:\n"
            "            callback()\n"
            "        callbacks.extend([dangerous])\n"
        ),
        (
            "    callbacks = []\n"
            "    alias = callbacks\n"
            "    for _ in range(2):\n"
            "        for callback in callbacks:\n"
            "            callback()\n"
            "        alias.append(dangerous)\n"
        ),
        (
            "    callbacks = []\n"
            "    for _ in range(2):\n"
            "        for callback in callbacks:\n"
            "            callback()\n"
            "        if enabled:\n"
            "            callbacks.append(dangerous)\n"
        ),
    ],
    ids=[
        "while-append",
        "for-range-append",
        "for-range-iadd",
        "for-range-extend",
        "for-range-alias-append",
        "conditional-append",
    ],
)
def test_r9_loop_carried_mutation_reaches_next_iteration(
    tmp_path, flow_source
):
    _assert_r6_dangerous_reached(
        _r6_callable_flow_result(tmp_path, flow_source)
    )


def test_r9_nested_loop_mutation_preserves_candidate_and_fails_closed(
    tmp_path,
):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    callbacks = []\n"
            "    for _ in range(2):\n"
            "        for __ in range(2):\n"
            "            for callback in callbacks:\n"
            "                callback()\n"
            "            callbacks.append(dangerous)\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


@pytest.mark.parametrize(
    "rebind",
    [
        "        callbacks = [dangerous]\n",
        "        if enabled:\n            callbacks = [dangerous]\n",
    ],
    ids=["direct", "conditional"],
)
def test_r9_loop_rebinding_applies_on_back_edge(tmp_path, rebind):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    callbacks = [safe]\n"
            "    for _ in range(2):\n"
            "        for callback in callbacks:\n"
            "            callback()\n"
            f"{rebind}"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_r9_rebound_alias_does_not_mutate_original_loop_container(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    callbacks = []\n"
            "    alias = callbacks\n"
            "    alias = []\n"
            "    for _ in range(2):\n"
            "        for callback in callbacks:\n"
            "            callback()\n"
            "        alias.append(dangerous)\n"
        ),
    )
    assert result["state"] == "not_detected"
    assert result["findings"] == []


@pytest.mark.parametrize(
    "mutation",
    [
        "    callbacks = []\n    callbacks.insert(0, dangerous)\n",
        "    callbacks = set()\n    callbacks.add(dangerous)\n",
        "    callbacks = set()\n    callbacks.update([dangerous])\n",
        "    callbacks = [safe]\n    callbacks[0] = dangerous\n",
    ],
    ids=["list-insert", "set-add", "set-update", "exact-subscript"],
)
def test_r9_supported_container_mutations_preserve_candidate(
    tmp_path, mutation
):
    result = _r6_callable_flow_result(
        tmp_path,
        mutation
        + "    for callback in callbacks:\n"
        + "        callback()\n",
    )
    _assert_r6_dangerous_reached(result)


@pytest.mark.parametrize(
    "flow_source",
    [
        (
            "    def choose_index():\n"
            "        return 0\n"
            "    callbacks = [safe]\n"
            "    index = choose_index()\n"
            "    callbacks[index] = dangerous\n"
            "    for callback in callbacks:\n"
            "        callback()\n"
        ),
        (
            "    callbacks = [dangerous]\n"
            "    callbacks.reorder_somehow()\n"
            "    for callback in callbacks:\n"
            "        callback()\n"
        ),
        (
            "    callbacks = [dangerous]\n"
            "    mutate(callbacks)\n"
            "    for callback in callbacks:\n"
            "        callback()\n"
        ),
    ],
    ids=["dynamic-subscript", "unknown-method", "unknown-consumer"],
)
def test_r9_unbounded_container_mutation_preserves_known_candidate(
    tmp_path, flow_source
):
    _assert_r6_dangerous_reached(
        _r6_callable_flow_result(tmp_path, flow_source)
    )


@pytest.mark.parametrize(
    "flow_source",
    [
        (
            "    callbacks = []\n"
            "    callbacks.append(dangerous)\n"
            "    return callbacks\n"
        ),
        (
            "    callbacks = []\n"
            "    callbacks.append(dangerous)\n"
            "    yield callbacks\n"
        ),
        (
            "    callbacks = []\n"
            "    callbacks.append(dangerous)\n"
            "    yield from callbacks\n"
        ),
    ],
    ids=["return", "yield", "yield-from"],
)
def test_r9_returned_or_yielded_mutated_container_reaches_callable(
    tmp_path, flow_source
):
    _assert_r6_dangerous_reached(
        _r6_callable_flow_result(tmp_path, flow_source)
    )


@pytest.mark.parametrize(
    "flow_source",
    [
        (
            "    callbacks = []\n"
            "    callbacks.append(dangerous)\n"
            "    register(callbacks)\n"
        ),
        (
            "    callbacks = []\n"
            "    callbacks.append(dangerous)\n"
            "    register(callbacks=callbacks)\n"
        ),
        (
            "    import json\n"
            "    callbacks = []\n"
            "    callbacks.append(dangerous)\n"
            "    json.dumps(callbacks)\n"
        ),
        (
            "    import json\n"
            "    callbacks = []\n"
            "    callbacks.append(dangerous)\n"
            "    json.dumps(obj=callbacks)\n"
        ),
        (
            "    import json\n"
            "    def handoff(value):\n"
            "        json.dumps(value)\n"
            "    callbacks = []\n"
            "    callbacks.append(dangerous)\n"
            "    handoff(callbacks)\n"
        ),
        (
            "    callbacks = []\n"
            "    callbacks.append(dangerous)\n"
            "    @unresolved_factory(callbacks)\n"
            "    def wrapped():\n"
            "        return 1\n"
        ),
    ],
    ids=[
        "unresolved-positional",
        "unresolved-keyword",
        "json-positional",
        "json-keyword",
        "local-formal-to-external",
        "decorator-factory",
    ],
)
def test_r9_mutated_container_argument_escape_reaches_callable(
    tmp_path, flow_source
):
    _assert_r6_dangerous_reached(
        _r6_callable_flow_result(tmp_path, flow_source)
    )


@pytest.mark.parametrize(
    "flow_source",
    [
        (
            "    class Holder:\n"
            "        pass\n"
            "    callbacks = []\n"
            "    callbacks.append(dangerous)\n"
            "    holder = Holder()\n"
            "    holder.callbacks = callbacks\n"
        ),
        (
            "    callbacks = []\n"
            "    callbacks.append(dangerous)\n"
            "    holder = {}\n"
            "    holder['callbacks'] = callbacks\n"
        ),
        (
            "    import json\n"
            "    callbacks = []\n"
            "    callbacks.append(dangerous)\n"
            "    holder = {}\n"
            "    holder['callbacks'] = callbacks\n"
            "    json.dumps(holder)\n"
        ),
        (
            "    import json\n"
            "    callbacks = []\n"
            "    callbacks.append(dangerous)\n"
            "    json.dumps([callbacks])\n"
        ),
        (
            "    import json\n"
            "    callbacks = []\n"
            "    callbacks.append(dangerous)\n"
            "    json.dumps((callbacks,))\n"
        ),
        (
            "    callbacks = []\n"
            "    callbacks.append(dangerous)\n"
            "    nested = {tuple(callbacks)}\n"
            "    def publish(groups):\n"
            "        for group in groups:\n"
            "            for callback in group:\n"
            "                callback()\n"
            "    publish(nested)\n"
        ),
        (
            "    import json\n"
            "    callbacks = []\n"
            "    callbacks.append(dangerous)\n"
            "    json.dumps({'callbacks': callbacks})\n"
        ),
        (
            "    import json\n"
            "    callbacks = []\n"
            "    callbacks.append(dangerous)\n"
            "    json.dumps(callbacks if enabled else [])\n"
        ),
        (
            "    import json\n"
            "    callbacks = []\n"
            "    callbacks.append(dangerous)\n"
            "    json.dumps((published := callbacks))\n"
        ),
    ],
    ids=[
        "attribute-owner",
        "subscript-owner",
        "whole-owner",
        "nested-list",
        "nested-tuple",
        "nested-set",
        "nested-dict",
        "if-expression",
        "named-expression",
    ],
)
def test_r9_mutated_container_storage_or_nested_escape_reaches_callable(
    tmp_path, flow_source
):
    _assert_r6_dangerous_reached(
        _r6_callable_flow_result(tmp_path, flow_source)
    )


def test_r9_mutated_local_container_without_consumer_stays_dormant(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    callbacks = []\n"
            "    callbacks.append(dangerous)\n"
            "    return 1\n"
        ),
    )
    assert result["state"] == "not_detected"
    assert result["findings"] == []


def test_r9_straight_line_mutation_after_use_does_not_flow_backward(tmp_path):
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


@pytest.mark.parametrize(
    "flow_source",
    [
        (
            "    import json\n"
            "    callbacks = []\n"
            "    callbacks.append(1)\n"
            "    json.dumps(callbacks)\n"
        ),
        (
            "    import json\n"
            "    callbacks = []\n"
            "    callbacks.append(json.dumps)\n"
            "    register(callbacks)\n"
        ),
        "    import json\n    json.dumps([])\n",
    ],
    ids=["non-callable", "external-callable", "mutation-free-empty"],
)
def test_r9_non_repository_container_values_do_not_create_taint(
    tmp_path, flow_source
):
    result = _r6_callable_flow_result(tmp_path, flow_source)
    assert result["state"] == "not_detected"
    assert result["findings"] == []


def test_r9_alias_rebinding_separates_container_tokens(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    callbacks = []\n"
            "    alias = callbacks\n"
            "    alias = []\n"
            "    alias.append(dangerous)\n"
            "    for callback in callbacks:\n"
            "        callback()\n"
        ),
    )
    assert result["state"] == "not_detected"
    assert result["findings"] == []


def test_r9_nested_scope_container_tokens_do_not_collide(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    callbacks = []\n"
            "    def dormant():\n"
            "        callbacks = []\n"
            "        callbacks.append(dangerous)\n"
            "        return callbacks\n"
            "    return 1\n"
        ),
    )
    assert result["state"] == "not_detected"
    assert result["findings"] == []


def test_r9_local_container_consumer_without_escape_stays_dormant(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    def ignore(value):\n"
            "        return 1\n"
            "    callbacks = []\n"
            "    callbacks.append(dangerous)\n"
            "    ignore(callbacks)\n"
        ),
    )
    assert result["state"] == "not_detected"
    assert result["findings"] == []


def test_r9_conditional_aliasing_merges_container_tokens(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    first = []\n"
            "    second = []\n"
            "    alias = first\n"
            "    if enabled:\n"
            "        alias = second\n"
            "    alias.append(dangerous)\n"
            "    for callback in first:\n"
            "        callback()\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_r9_known_candidate_beneath_unknown_container_state_is_preserved(
    tmp_path,
):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import json\n"
            "    callbacks = [dangerous]\n"
            "    callbacks.append(unresolved)\n"
            "    json.dumps(callbacks)\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_r9_incomplete_then_complete_opaque_assignment_merge_stays_incomplete(
    tmp_path,
):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import json\n"
            "    item = unresolved\n"
            "    if enabled:\n"
            "        item = 1 + 2\n"
            "    callbacks = []\n"
            "    callbacks.append(item)\n"
            "    json.dumps(callbacks)\n"
        ),
    )
    assert result["state"] == "unknown"
    assert result["reason"] == "import_resolution_incomplete"
    assert result["findings"] == []


def test_r9_known_candidate_survives_incomplete_assignment_merge(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import json\n"
            "    item = unresolved\n"
            "    if enabled:\n"
            "        item = dangerous\n"
            "    callbacks = []\n"
            "    callbacks.append(item)\n"
            "    json.dumps(callbacks)\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


@pytest.mark.parametrize(
    "assignment",
    [
        "    item = (1 + 2) if enabled else unresolved\n",
        "    item = unresolved if enabled else (1 + 2)\n",
    ],
    ids=["opaque-first", "unresolved-first"],
)
def test_r9_conditional_opaque_and_unresolved_merge_is_order_independent(
    tmp_path, assignment
):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import json\n"
            f"{assignment}"
            "    callbacks = []\n"
            "    callbacks.append(item)\n"
            "    json.dumps(callbacks)\n"
        ),
    )
    assert result["state"] == "unknown"
    assert result["reason"] == "import_resolution_incomplete"
    assert result["findings"] == []


def test_r9_conditional_opaque_binding_with_unbound_fallthrough_fails_closed(
    tmp_path,
):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import json\n"
            "    if enabled:\n"
            "        item = 1 + 2\n"
            "    callbacks = []\n"
            "    callbacks.append(item)\n"
            "    json.dumps(callbacks)\n"
        ),
    )
    assert result["state"] == "unknown"
    assert result["reason"] == "import_resolution_incomplete"
    assert result["findings"] == []


@pytest.mark.parametrize(
    "element_source",
    [
        "    callbacks.append(unresolved)\n",
        (
            "    if enabled:\n"
            "        item = 1\n"
            "    else:\n"
            "        item = unresolved\n"
            "    callbacks.append(item)\n"
        ),
    ],
    ids=["bare-unresolved", "conditional-opaque-unresolved"],
)
def test_r9_unresolved_only_mutated_container_escape_fails_closed(
    tmp_path, element_source
):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import json\n"
            "    callbacks = []\n"
            f"{element_source}"
            "    json.dumps(callbacks)\n"
        ),
    )
    assert result["state"] == "unknown"
    assert result["reason"] == "import_resolution_incomplete"
    assert result["findings"] == []


def test_r9_opaque_numeric_expression_does_not_create_false_unknown(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import json\n"
            "    callbacks = []\n"
            "    callbacks.append((1 + 2) * 3.0)\n"
            "    json.dumps(callbacks)\n"
        ),
    )
    assert result["state"] == "not_detected"
    assert result["findings"] == []


def test_r9_numpy_like_numeric_array_result_does_not_create_false_unknown(
    tmp_path,
):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import json\n"
            "    import numpy as np\n"
            "    prediction = np.asarray([0.1, 0.2, 0.3])\n"
            "    callbacks = []\n"
            "    callbacks.append(prediction)\n"
            "    json.dumps(callbacks)\n"
        ),
    )
    assert result["state"] == "not_detected"
    assert result["findings"] == []


def test_r9_opaque_prediction_vector_with_unresolved_branch_fails_closed(
    tmp_path,
):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import json\n"
            "    import numpy as np\n"
            "    prediction = (\n"
            "        np.asarray([0.1, 0.2]) if enabled else unresolved\n"
            "    )\n"
            "    callbacks = []\n"
            "    callbacks.append(prediction)\n"
            "    json.dumps(callbacks)\n"
        ),
    )
    assert result["state"] == "unknown"
    assert result["reason"] == "import_resolution_incomplete"
    assert result["findings"] == []


@pytest.mark.parametrize(
    "element_source",
    [
        "    callbacks.append(unresolved_factory())\n",
        (
            "    item = unresolved_factory()\n"
            "    callbacks.append(item)\n"
        ),
    ],
    ids=["direct", "stored-name"],
)
def test_r9_unresolved_factory_result_escape_fails_closed(
    tmp_path, element_source
):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import json\n"
            "    callbacks = []\n"
            f"{element_source}"
            "    json.dumps(callbacks)\n"
        ),
    )
    assert result["state"] == "unknown"
    assert result["reason"] == "import_resolution_incomplete"
    assert result["findings"] == []


def test_r9_unbound_factory_method_result_escape_fails_closed(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import json\n"
            "    callbacks = []\n"
            "    callbacks.append(factory.make())\n"
            "    json.dumps(callbacks)\n"
        ),
    )
    assert result["state"] == "unknown"
    assert result["reason"] == "import_resolution_incomplete"
    assert result["findings"] == []


def test_r9_repeated_equivalent_invocation_merge_is_idempotent(tmp_path):
    single_root = tmp_path / "single"
    repeated_root = tmp_path / "repeated"
    single_root.mkdir()
    repeated_root.mkdir()
    common = (
        "    import json\n"
        "    def publish(value):\n"
        "        json.dumps(value)\n"
        "    callbacks = []\n"
        "    callbacks.append(dangerous)\n"
        "    callbacks.append(unresolved)\n"
    )
    single = _r6_callable_flow_result(
        single_root,
        common + "    publish(callbacks)\n",
    )
    repeated = _r6_callable_flow_result(
        repeated_root,
        common + "    publish(callbacks)\n" * 3,
    )
    _assert_r6_dangerous_reached(single)
    assert repeated == single


def test_r9_conditional_exact_index_overwrite_preserves_previous_candidate(
    tmp_path,
):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    callbacks = [dangerous]\n"
            "    if enabled:\n"
            "        callbacks[0] = safe\n"
            "    for callback in callbacks:\n"
            "        callback()\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_r9_loop_back_edge_exact_index_overwrite_preserves_previous_candidate(
    tmp_path,
):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    callbacks = [dangerous]\n"
            "    for _ in range(2):\n"
            "        for callback in callbacks:\n"
            "            callback()\n"
            "        callbacks[0] = safe\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_r9_conditional_alias_exact_index_write_preserves_original_candidate(
    tmp_path,
):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    first = [dangerous]\n"
            "    second = [safe]\n"
            "    alias = first\n"
            "    if enabled:\n"
            "        alias = second\n"
            "    alias[0] = safe\n"
            "    for callback in first:\n"
            "        callback()\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_r9_raw_mutated_container_unknown_taint_crosses_local_formal(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import json\n"
            "    def publish(value):\n"
            "        json.dumps(value)\n"
            "    callbacks = []\n"
            "    callbacks.append(unresolved)\n"
            "    publish(callbacks)\n"
        ),
    )
    assert result["state"] == "unknown"
    assert result["reason"] == "import_resolution_incomplete"
    assert result["findings"] == []


def test_r9_prior_exact_call_raw_source_survives_later_function_escape(
    tmp_path,
):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import json\n"
            "    def publish(value):\n"
            "        json.dumps(value)\n"
            "    callbacks = []\n"
            "    callbacks.append(dangerous)\n"
            "    publish(callbacks)\n"
            "    register(publish)\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


@pytest.mark.parametrize(
    "caller_value",
    ["[]", "[safe]"],
    ids=["empty-caller", "safe-caller"],
)
def test_r9_conditional_formal_rebind_to_candidate_survives_iterable_dispatch(
    tmp_path, caller_value
):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    def dispatch(value):\n"
            "        if enabled:\n"
            "            value = [dangerous]\n"
            "        for callback in value:\n"
            "            callback()\n"
            f"    dispatch({caller_value})\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_r9_conditional_formal_rebinding_preserves_raw_container_candidate(
    tmp_path,
):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import json\n"
            "    def publish(value):\n"
            "        if enabled:\n"
            "            value = []\n"
            "        json.dumps(value)\n"
            "    callbacks = []\n"
            "    callbacks.append(dangerous)\n"
            "    publish(callbacks)\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_r9_mutation_unknown_state_is_monotone(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import json\n"
            "    callbacks = []\n"
            "    callbacks *= unresolved\n"
            "    callbacks /= 1\n"
            "    json.dumps(callbacks)\n"
        ),
    )
    assert result["state"] == "unknown"
    assert result["reason"] == "import_resolution_incomplete"
    assert result["findings"] == []


def test_r9_mutation_escape_cycle_is_bounded_and_preserves_candidate(
    tmp_path,
):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    callbacks = []\n"
            "    callbacks.append(callbacks)\n"
            "    callbacks.append(dangerous)\n"
            "    register(callbacks)\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def _assert_r9_proven_non_callable(result):
    assert result["state"] == "not_detected"
    assert result["findings"] == []
    assert "reason" not in result


def _r9_semantic_result(result):
    return result["state"], result.get("reason"), result["findings"]


def test_r9_try_except_numeric_scalars_are_proven_non_callable(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import json\n"
            "    try:\n"
            "        item = (1 + 2) * 3.0\n"
            "    except ArithmeticError:\n"
            "        item = float(4) / 2\n"
            "    values = []\n"
            "    values.append(item)\n"
            "    json.dumps(values)\n"
        ),
    )
    _assert_r9_proven_non_callable(result)


def test_r9_numeric_property_and_numeric_function_fallback_are_safe(
    tmp_path,
):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import json\n"
            "    def numeric_result():\n"
            "        return 0.25\n"
            "    def numeric_fallback():\n"
            "        return float(1) / 2\n"
            "    try:\n"
            "        item = numeric_result().real\n"
            "    except AttributeError:\n"
            "        item = numeric_fallback()\n"
            "    values = []\n"
            "    values.append(item)\n"
            "    json.dumps(values)\n"
        ),
    )
    _assert_r9_proven_non_callable(result)


def test_r9_numpy_scalar_and_python_float_merge_without_numpy_runtime(
    tmp_path,
):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import json\n"
            "    import numpy as np\n"
            "    try:\n"
            "        item = np.float64(0.25)\n"
            "    except (AttributeError, TypeError):\n"
            "        item = float(0.5)\n"
            "    values = []\n"
            "    values.append(item)\n"
            "    json.dumps(values)\n"
        ),
    )
    _assert_r9_proven_non_callable(result)


def test_r9_numeric_array_results_on_both_try_paths_are_safe(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import json\n"
            "    import numpy as np\n"
            "    try:\n"
            "        vector = np.asarray([0.1, 0.2, 0.3])\n"
            "    except AttributeError:\n"
            "        vector = np.array([1.0, 2.0, 3.0])\n"
            "    values = []\n"
            "    values.append(vector)\n"
            "    json.dumps(values)\n"
        ),
    )
    _assert_r9_proven_non_callable(result)


def test_r9_try_else_applies_after_safe_try_path_and_merges_safe_handler(
    tmp_path,
):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import json\n"
            "    try:\n"
            "        item = float(1)\n"
            "    except (TypeError, ValueError):\n"
            "        item = 2.0\n"
            "    else:\n"
            "        item = item + 3.0\n"
            "    values = []\n"
            "    values.append(item)\n"
            "    json.dumps(values)\n"
        ),
    )
    _assert_r9_proven_non_callable(result)


def test_r9_try_else_unresolved_normal_path_remains_fail_closed(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import json\n"
            "    try:\n"
            "        item = 1.0\n"
            "    except ArithmeticError:\n"
            "        item = 2.0\n"
            "    else:\n"
            "        item = unresolved\n"
            "    values = []\n"
            "    values.append(item)\n"
            "    json.dumps(values)\n"
        ),
    )
    _assert_r7_unknown_without_dangerous_finding(result)


def test_r9_try_handler_preserves_prior_numeric_binding(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import json\n"
            "    item = 0.25\n"
            "    try:\n"
            "        item = 0.5\n"
            "    except ArithmeticError:\n"
            "        pass\n"
            "    values = []\n"
            "    values.append(item)\n"
            "    json.dumps(values)\n"
        ),
    )
    _assert_r9_proven_non_callable(result)


def test_r9_finally_non_callable_overwrite_kills_prior_uncertainty(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import json\n"
            "    item = unresolved\n"
            "    try:\n"
            "        item = dangerous\n"
            "    except ArithmeticError:\n"
            "        item = unresolved\n"
            "    finally:\n"
            "        item = 1.0\n"
            "    values = []\n"
            "    values.append(item)\n"
            "    json.dumps(values)\n"
        ),
    )
    _assert_r9_proven_non_callable(result)


@pytest.mark.parametrize(
    "non_continuing_handler",
    [
        "        return 0.0\n",
        "        raise\n",
    ],
    ids=["return", "raise"],
)
def test_r9_non_continuing_paths_do_not_taint_continuation(
    tmp_path, non_continuing_handler
):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import json\n"
            "    try:\n"
            "        if enabled:\n"
            "            raise ArithmeticError()\n"
            "        item = 1.0\n"
            "    except ArithmeticError:\n"
            f"{non_continuing_handler}"
            "    values = []\n"
            "    values.append(item)\n"
            "    json.dumps(values)\n"
        ),
    )
    _assert_r9_proven_non_callable(result)


def test_r9_numeric_tuple_in_mutated_container_is_safe(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import json\n"
            "    values = []\n"
            "    values.append((1, (2 + 3) * 4.0, float(5)))\n"
            "    json.dumps(values)\n"
        ),
    )
    _assert_r9_proven_non_callable(result)


def test_r9_tuple_with_known_local_callable_preserves_candidate(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import json\n"
            "    values = []\n"
            "    values.append((1, dangerous))\n"
            "    json.dumps(values)\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_r9_tuple_with_unresolved_element_remains_unknown(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import json\n"
            "    values = []\n"
            "    values.append((1, unresolved))\n"
            "    json.dumps(values)\n"
        ),
    )
    _assert_r7_unknown_without_dangerous_finding(result)


def test_r9_numeric_vector_and_unresolved_branch_remain_unknown(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import json\n"
            "    import numpy as np\n"
            "    if enabled:\n"
            "        vector = np.asarray([0.1, 0.2])\n"
            "    else:\n"
            "        vector = unresolved\n"
            "    values = []\n"
            "    values.append(vector)\n"
            "    json.dumps(values)\n"
        ),
    )
    _assert_r7_unknown_without_dangerous_finding(result)


@pytest.mark.parametrize("control_kind", ["try", "if"], ids=["try", "if"])
def test_r9_reversing_non_callable_branch_order_is_invariant(
    tmp_path, control_kind
):
    left_root = tmp_path / "left"
    right_root = tmp_path / "right"
    left_root.mkdir()
    right_root.mkdir()
    if control_kind == "try":
        left_assignment = (
            "    try:\n"
            "        item = np.asarray([0.1, 0.2])\n"
            "    except AttributeError:\n"
            "        item = float(0.5)\n"
        )
        right_assignment = (
            "    try:\n"
            "        item = float(0.5)\n"
            "    except AttributeError:\n"
            "        item = np.asarray([0.1, 0.2])\n"
        )
    else:
        left_assignment = (
            "    if enabled:\n"
            "        item = np.asarray([0.1, 0.2])\n"
            "    else:\n"
            "        item = float(0.5)\n"
        )
        right_assignment = (
            "    if enabled:\n"
            "        item = float(0.5)\n"
            "    else:\n"
            "        item = np.asarray([0.1, 0.2])\n"
        )
    suffix = (
        "    values = []\n"
        "    values.append(item)\n"
        "    json.dumps(values)\n"
    )
    prefix = "    import json\n    import numpy as np\n"
    left = _r6_callable_flow_result(
        left_root, prefix + left_assignment + suffix
    )
    right = _r6_callable_flow_result(
        right_root, prefix + right_assignment + suffix
    )
    _assert_r9_proven_non_callable(left)
    assert _r9_semantic_result(right) == _r9_semantic_result(left)


@pytest.mark.parametrize(
    ("left", "right", "expected"),
    [
        (
            "EXACT_NON_CALLABLE",
            "PROVEN_NON_CALLABLE_OPAQUE",
            "PROVEN_NON_CALLABLE_OPAQUE",
        ),
        (
            "PROVEN_NON_CALLABLE_OPAQUE",
            "MAY_CONTAIN_CALLABLE",
            "MAY_CONTAIN_CALLABLE",
        ),
        (
            "KNOWN_CALLABLE_CONTENT",
            "UNRESOLVED",
            "MAY_CONTAIN_CALLABLE",
        ),
        ("UNRESOLVED", "EXACT_NON_CALLABLE", "UNRESOLVED"),
        (
            "KNOWN_CALLABLE_CONTENT",
            "EXACT_NON_CALLABLE",
            "KNOWN_CALLABLE_CONTENT",
        ),
    ],
)
def test_r9_value_kind_join_is_commutative_and_monotone(
    left, right, expected
):
    join = _module()._join_value_kinds
    assert join(left, right) == expected
    assert join(right, left) == expected


@pytest.mark.parametrize(
    "kind",
    [
        "KNOWN_CALLABLE_CONTENT",
        "MAY_CONTAIN_CALLABLE",
        "PROVEN_NON_CALLABLE_OPAQUE",
        "EXACT_NON_CALLABLE",
        "UNRESOLVED",
    ],
)
def test_r9_value_kind_join_is_idempotent(kind):
    mod = _module()
    assert mod._join_value_kinds(kind, kind) == kind
    assert mod._join_many_value_kinds([kind, kind, kind], empty=kind) == kind


def test_r9_value_kind_join_is_associative_and_permutation_invariant():
    mod = _module()
    kinds = (
        "KNOWN_CALLABLE_CONTENT",
        "MAY_CONTAIN_CALLABLE",
        "PROVEN_NON_CALLABLE_OPAQUE",
        "EXACT_NON_CALLABLE",
        "UNRESOLVED",
    )
    assert set(kinds) == set(mod.VALUE_KINDS)
    join = mod._join_value_kinds
    join_many = mod._join_many_value_kinds
    for left, middle, right in itertools.product(kinds, repeat=3):
        expected = join(join(left, middle), right)
        assert join(left, join(middle, right)) == expected
        for ordering in set(itertools.permutations((left, middle, right))):
            assert join_many(ordering) == expected


def test_r9_repeated_safe_value_kind_merge_is_idempotent(tmp_path):
    single_root = tmp_path / "single"
    repeated_root = tmp_path / "repeated"
    single_root.mkdir()
    repeated_root.mkdir()
    common = (
        "    import json\n"
        "    def publish(value):\n"
        "        json.dumps(value)\n"
        "    try:\n"
        "        item = (1 + 2) * 3.0\n"
        "    except ArithmeticError:\n"
        "        item = float(4)\n"
        "    values = []\n"
        "    values.append(item)\n"
    )
    single = _r6_callable_flow_result(
        single_root, common + "    publish(values)\n"
    )
    repeated = _r6_callable_flow_result(
        repeated_root, common + "    publish(values)\n" * 3
    )
    _assert_r9_proven_non_callable(single)
    assert _r9_semantic_result(repeated) == _r9_semantic_result(single)


def test_r9_unresolved_only_value_remains_fail_closed(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import json\n"
            "    values = []\n"
            "    values.append(unresolved)\n"
            "    json.dumps(values)\n"
        ),
    )
    _assert_r7_unknown_without_dangerous_finding(result)


def test_r9_known_local_scalar_factory_result_is_safe(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import json\n"
            "    def scalar_factory():\n"
            "        return (2 + 3) / 4\n"
            "    values = []\n"
            "    values.append(scalar_factory())\n"
            "    json.dumps(values)\n"
        ),
    )
    _assert_r9_proven_non_callable(result)


def test_r9_unresolved_factory_result_remains_fail_closed(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import json\n"
            "    values = []\n"
            "    values.append(unresolved_factory())\n"
            "    json.dumps(values)\n"
        ),
    )
    _assert_r7_unknown_without_dangerous_finding(result)


def test_r9_known_numeric_receiver_attribute_is_safe(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import json\n"
            "    item = (1.5).real\n"
            "    values = []\n"
            "    values.append(item)\n"
            "    json.dumps(values)\n"
        ),
    )
    _assert_r9_proven_non_callable(result)


@pytest.mark.parametrize(
    "numeric_alias",
    ["array_backend", "numeric_runtime"],
)
def test_r9_renamed_numpy_alias_retains_numeric_value_kinds(
    tmp_path, numeric_alias
):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import json\n"
            f"    import numpy as {numeric_alias}\n"
            f"    sample = {numeric_alias}.asarray([0.1, 0.2, 0.3])\n"
            f"    score = {numeric_alias}.float64(0.25)\n"
            "    measurements = []\n"
            "    measurements.append((sample, score))\n"
            "    json.dumps(measurements)\n"
        ),
    )
    _assert_r9_proven_non_callable(result)


def test_r9_aliased_scipy_numeric_property_and_fallback_are_safe(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import json\n"
            "    from scipy import stats as probability_api\n"
            "    try:\n"
            "        score = probability_api.binomtest(2, 4).pvalue\n"
            "    except AttributeError:\n"
            "        score = probability_api.binom_test(2, 4)\n"
            "    measurements = []\n"
            "    measurements.append(score)\n"
            "    json.dumps(measurements)\n"
        ),
    )
    _assert_r9_proven_non_callable(result)


def test_r9_unknown_attribute_receiver_remains_fail_closed(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import json\n"
            "    item = receiver.numeric_value\n"
            "    values = []\n"
            "    values.append(item)\n"
            "    json.dumps(values)\n"
        ),
    )
    _assert_r7_unknown_without_dangerous_finding(result)


def test_r9_sort_with_key_is_reorder_only_for_numeric_data(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import json\n"
            "    values = [3, 1, 2]\n"
            "    values.sort(key=lambda value: value)\n"
            "    json.dumps(values)\n"
        ),
    )
    _assert_r9_proven_non_callable(result)


def test_r9_sort_with_key_preserves_existing_callable_candidate(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    callbacks = [dangerous, safe]\n"
            "    callbacks.sort(key=lambda callback: callback.__name__)\n"
            "    for callback in callbacks:\n"
            "        callback()\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_r9_loop_built_numeric_data_crosses_local_formal_safely(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import json\n"
            "    def publish(value):\n"
            "        json.dumps(value)\n"
            "    values = []\n"
            "    for number in range(4):\n"
            "        values.append((number, float(number)))\n"
            "    publish(values)\n"
        ),
    )
    _assert_r9_proven_non_callable(result)


def test_r9_loop_data_provenance_keeps_unresolved_element_fail_closed(
    tmp_path,
):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import json\n"
            "    values = []\n"
            "    for item in [1, unresolved]:\n"
            "        values.append(item)\n"
            "    json.dumps(values)\n"
        ),
    )
    _assert_r7_unknown_without_dangerous_finding(result)


def test_r9_assignment_before_caught_raise_reaches_later_escape(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import json\n"
            "    item = 0\n"
            "    try:\n"
            "        item = dangerous\n"
            "        raise ArithmeticError()\n"
            "    except ArithmeticError:\n"
            "        pass\n"
            "    values = []\n"
            "    values.append(item)\n"
            "    json.dumps(values)\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_r9_caught_raise_handler_overwrite_kills_prior_candidate(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import json\n"
            "    try:\n"
            "        item = dangerous\n"
            "        raise ArithmeticError()\n"
            "    except ArithmeticError:\n"
            "        item = 1\n"
            "    values = []\n"
            "    values.append(item)\n"
            "    json.dumps(values)\n"
        ),
    )
    _assert_r9_proven_non_callable(result)


def test_r9_sort_key_callback_execution_is_not_skipped(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    def projection(value):\n"
            "        dangerous()\n"
            "        return value\n"
            "    values = [3, 1, 2]\n"
            "    values.sort(key=projection)\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


@pytest.mark.parametrize("shadow_kind", ["parameter", "assignment"])
def test_r9_import_alias_shadowing_does_not_inherit_numeric_contract(
    tmp_path, shadow_kind
):
    if shadow_kind == "parameter":
        flow = (
            "    import json\n"
            "    import numpy as numerical\n"
            "    def publish(numerical):\n"
            "        values = []\n"
            "        values.append(numerical.asarray([1.0]))\n"
            "        json.dumps(values)\n"
            "    publish(unresolved_backend)\n"
        )
    else:
        flow = (
            "    import json\n"
            "    import numpy as numerical\n"
            "    numerical = unresolved_backend\n"
            "    values = []\n"
            "    values.append(numerical.asarray([1.0]))\n"
            "    json.dumps(values)\n"
        )
    result = _r6_callable_flow_result(tmp_path, flow)
    _assert_r7_unknown_without_dangerous_finding(result)


@pytest.mark.parametrize("method_name", ["append", "fetchall", "json"])
def test_r9_custom_receiver_method_result_is_not_treated_as_builtin(
    tmp_path, method_name
):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import json\n"
            "    class Receiver:\n"
            f"        def {method_name}(self):\n"
            "            return dangerous\n"
            "    receiver = Receiver()\n"
            f"    item = receiver.{method_name}()\n"
            "    values = []\n"
            "    values.append(item)\n"
            "    json.dumps(values)\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_r9_json_object_hook_return_is_not_proven_plain_data(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import json\n"
            "    def hook(value):\n"
            "        return dangerous\n"
            "    decoded = json.loads('{}', object_hook=hook)\n"
            "    values = []\n"
            "    values.append(decoded)\n"
            "    json.dumps(values)\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_r9_random_choice_propagates_callable_content(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import json\n"
            "    import random\n"
            "    selected = random.choice([dangerous])\n"
            "    values = []\n"
            "    values.append(selected)\n"
            "    json.dumps(values)\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


@pytest.mark.parametrize(
    ("method_source", "expression"),
    [
        ("        def __eq__(self, other):\n            return dangerous\n", "Payload() == 1"),
        ("        def __add__(self, other):\n            return dangerous\n", "Payload() + 1"),
        ("        def __getitem__(self, key):\n            return dangerous\n", "Payload()[0]"),
    ],
    ids=["comparison", "binary-operator", "subscript"],
)
def test_r9_overloaded_projection_result_remains_fail_closed(
    tmp_path, method_source, expression
):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import json\n"
            "    class Payload:\n"
            f"{method_source}"
            f"    item = {expression}\n"
            "    values = []\n"
            "    values.append(item)\n"
            "    json.dumps(values)\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


@pytest.mark.parametrize(
    ("expression", "expected_candidate"),
    [
        ("numeric.array([dangerous], dtype='O')", True),
        ("numeric.vectorize(dangerous)", True),
        ("numeric.load('payload.npy', allow_pickle=True)", False),
    ],
    ids=["object-dtype", "vectorize", "pickle-load"],
)
def test_r9_numpy_object_capable_results_remain_fail_closed(
    tmp_path, expression, expected_candidate
):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import json\n"
            "    import numpy as numeric\n"
            f"    item = {expression}\n"
            "    values = []\n"
            "    values.append(item)\n"
            "    json.dumps(values)\n"
        ),
    )
    if expected_candidate:
        _assert_r6_dangerous_reached(result)
    else:
        _assert_r7_unknown_without_dangerous_finding(result)


def test_r9_dict_unpack_with_unresolved_contents_remains_fail_closed(
    tmp_path,
):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import json\n"
            "    data = {'safe': 1, **unresolved_mapping}\n"
            "    values = []\n"
            "    values.extend(data.values())\n"
            "    json.dumps(values)\n"
        ),
    )
    _assert_r7_unknown_without_dangerous_finding(result)


def test_r9_later_dict_write_is_visible_to_values_projection(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import json\n"
            "    data = {'safe': 1}\n"
            "    data['callback'] = dangerous\n"
            "    values = []\n"
            "    values.extend(data.values())\n"
            "    json.dumps(values)\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_r9_json_actual_to_formal_alias_stays_proven_data(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import json\n"
            "    def publish(raw):\n"
            "        values = raw\n"
            "        values.append(1)\n"
            "        json.dumps(values)\n"
            "    publish(json.loads('[]'))\n"
        ),
    )
    _assert_r9_proven_non_callable(result)


def test_r9_nested_try_if_exhaustive_safe_bindings_merge_safely(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import json\n"
            "    try:\n"
            "        if enabled:\n"
            "            item = 1\n"
            "        else:\n"
            "            item = 2\n"
            "    except Exception:\n"
            "        item = 3\n"
            "    values = []\n"
            "    values.append(item)\n"
            "    json.dumps(values)\n"
        ),
    )
    _assert_r9_proven_non_callable(result)


def test_r9_terminating_mutation_path_does_not_taint_later_sink(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import json\n"
            "    values = []\n"
            "    if enabled:\n"
            "        values.append(unresolved)\n"
            "        return\n"
            "    json.dumps(values)\n"
        ),
    )
    _assert_r9_proven_non_callable(result)


def _r9_fanin_has_finding(result, resolved_api: str) -> bool:
    return any(
        finding["resolved_api"] == resolved_api
        for finding in result["findings"]
    )


def _r9_fanin_assert_no_dangerous(result):
    assert result["state"] == "not_detected"
    assert result["findings"] == []
    assert "reason" not in result


@pytest.mark.parametrize(
    "outer_control",
    [
        (
            "    if enabled:\n"
            "        try:\n"
            "            pass\n"
            "        finally:\n"
            "            item = 1\n"
        ),
        (
            "    for _ in callbacks:\n"
            "        try:\n"
            "            pass\n"
            "        finally:\n"
            "            item = 1\n"
        ),
    ],
    ids=["conditional-finally", "loop-contained-finally"],
)
def test_fanin_finally_overwrite_requires_outer_dominance(
    tmp_path, outer_control
):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import json\n"
            "    item = dangerous\n"
            f"{outer_control}"
            "    json.dumps([item])\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_fanin_assignment_caught_raise_reaches_finally_sink(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    try:\n"
            "        item = dangerous\n"
            "        raise ArithmeticError()\n"
            "    except ArithmeticError:\n"
            "        pass\n"
            "    finally:\n"
            "        register(item)\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


@pytest.mark.parametrize(
    "try_source",
    [
        (
            "    try:\n"
            "        raise ValueError()\n"
            "    except ValueError:\n"
            "        item = 1\n"
        ),
        (
            "    try:\n"
            "        pass\n"
            "    except ValueError:\n"
            "        item = 2\n"
            "    else:\n"
            "        item = 1\n"
        ),
    ],
    ids=["handler", "else"],
)
def test_fanin_try_path_binding_reaches_finally_use(
    tmp_path, try_source
):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import json\n"
            f"{try_source}"
            "    finally:\n"
            "        json.dumps([item])\n"
        ),
    )
    _assert_r9_proven_non_callable(result)


@pytest.mark.parametrize(
    "flow_source",
    [
        (
            "    def transfer():\n"
            "        try:\n"
            "            return 1\n"
            "        finally:\n"
            "            register(dangerous)\n"
            "    transfer()\n"
        ),
        (
            "    try:\n"
            "        try:\n"
            "            raise ArithmeticError()\n"
            "        finally:\n"
            "            register(dangerous)\n"
            "    except ArithmeticError:\n"
            "        pass\n"
        ),
        (
            "    for _ in [0]:\n"
            "        try:\n"
            "            break\n"
            "        finally:\n"
            "            register(dangerous)\n"
        ),
        (
            "    for _ in [0]:\n"
            "        try:\n"
            "            continue\n"
            "        finally:\n"
            "            register(dangerous)\n"
        ),
    ],
    ids=["return", "raise", "break", "continue"],
)
def test_fanin_every_transfer_executes_finally(tmp_path, flow_source):
    _assert_r6_dangerous_reached(
        _r6_callable_flow_result(tmp_path, flow_source)
    )


def test_fanin_finally_return_replaces_prior_return(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    def choose():\n"
            "        try:\n"
            "            return dangerous\n"
            "        finally:\n"
            "            return safe\n"
            "    callback = choose()\n"
            "    callback()\n"
        ),
    )
    assert result["state"] == "not_detected"
    _r9_fanin_assert_no_dangerous(result)


def test_fanin_exception_evaluating_return_reaches_handler(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    def choose():\n"
            "        try:\n"
            "            return unresolved_factory()\n"
            "        except Exception:\n"
            "            return dangerous\n"
            "    callback = choose()\n"
            "    callback()\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


@pytest.mark.parametrize(
    "flow_source",
    [
        (
            "    try:\n"
            "        raise unresolved_factory()\n"
            "    except TypeError:\n"
            "        register(dangerous)\n"
        ),
        (
            "    try:\n"
            "        raise ValueError() from unresolved_factory()\n"
            "    except TypeError:\n"
            "        register(dangerous)\n"
        ),
        (
            "    try:\n"
            "        holder[unresolved_index()] = safe\n"
            "    except Exception:\n"
            "        register(dangerous)\n"
        ),
        (
            "    try:\n"
            "        unresolved_holder.callback = safe\n"
            "    except Exception:\n"
            "        register(dangerous)\n"
        ),
        (
            "    if enabled:\n"
            "        item = safe\n"
            "    try:\n"
            "        result = item\n"
            "    except UnboundLocalError:\n"
            "        register(dangerous)\n"
        ),
    ],
    ids=[
        "raise-operand", "raise-cause", "subscript-store",
        "attribute-store", "conditionally-unbound-name",
    ],
)
def test_fanin_expression_exceptions_feed_handlers(
    tmp_path, flow_source
):
    _assert_r6_dangerous_reached(
        _r6_callable_flow_result(tmp_path, flow_source)
    )


def test_fanin_local_exception_inheritance_reaches_base_handler(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    class MyError(ValueError):\n"
            "        pass\n"
            "    try:\n"
            "        raise MyError()\n"
            "    except ValueError:\n"
            "        register(dangerous)\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_fanin_sys_exit_requires_scoped_import_identity(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    def dormant():\n"
            "        import sys\n"
            "    try:\n"
            "        sys.exit(0)\n"
            "    except NameError:\n"
            "        register(dangerous)\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_fanin_nested_class_namespace_does_not_shadow_method_global(
    tmp_path,
):
    result = _escaped_nested_callable_result(
        tmp_path,
        (
            "import requests as api\n"
            "def run():\n"
            "    class C:\n"
            "        import numpy as api\n"
            "        def method(self):\n"
            "            api.get('https://example.invalid')\n"
            "    C().method()\n"
        ),
    )
    assert _r9_fanin_has_finding(result, "requests.get")


def test_fanin_method_does_not_invent_alias_from_class_namespace(tmp_path):
    result = _escaped_nested_callable_result(
        tmp_path,
        (
            "def run():\n"
            "    class C:\n"
            "        import requests as api\n"
            "        def method(self):\n"
            "            api.get('https://example.invalid')\n"
            "    C().method()\n"
        ),
    )
    assert not _r9_fanin_has_finding(result, "requests.get")


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            "import requests as api\n"
            "class C:\n"
            "    import numpy as api\n"
            "    def method(self):\n"
            "        api.get('body')\n",
            "requests.get",
        ),
        (
            "import numpy as api\n"
            "class C:\n"
            "    import requests as api\n"
            "    def method(self, value=api.get('default')):\n"
            "        pass\n",
            "requests.get",
        ),
        (
            "class C:\n"
            "    import requests as api\n"
            "    values = [api.get('element') for _ in [1]]\n",
            None,
        ),
        (
            "class C:\n"
            "    import requests as api\n"
            "    values = [item for item in api.get('outer-iterable')]\n",
            "requests.get",
        ),
        (
            "class C:\n"
            "    def method(self, value=api.get('before-import')):\n"
            "        pass\n"
            "    import requests as api\n",
            None,
        ),
        (
            "import requests as api\n"
            "class C:\n"
            "    def method(self, value=api.get('global-before-import')):\n"
            "        pass\n"
            "    import numpy as api\n",
            "requests.get",
        ),
    ],
    ids=[
        "method-body-skips-class",
        "method-default-uses-class",
        "class-comprehension-skips-class",
        "class-comprehension-outer-iterable-uses-class",
        "method-default-rejects-later-class-import",
        "method-default-uses-prior-global-before-class-import",
    ],
)
def test_fanin_scoped_alias_respects_definition_expression_boundary(
    source, expected
):
    mod = _module()
    tree = ast.parse(source)
    resolver = mod._ScopedAliasResolver(tree)
    call = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
    )
    assert resolver.dotted_name_at(call.func, call) == expected


@pytest.mark.parametrize(
    ("class_events", "expected"),
    [
        (
            "    import numpy as api\n"
            "    del api\n",
            "requests.get",
        ),
        (
            "    if enabled:\n"
            "        import requests as api\n",
            "requests.get",
        ),
        (
            "    if enabled:\n"
            "        import numpy as api\n",
            None,
        ),
        (
            "    import numpy as api\n"
            "    if enabled:\n"
            "        del api\n",
            None,
        ),
    ],
    ids=[
        "delete-restores-global",
        "same-conditional-identity",
        "different-conditional-identity",
        "conditional-delete-is-ambiguous",
    ],
)
def test_fanin_class_alias_lookup_joins_namespace_fallback(
    class_events, expected
):
    mod = _module()
    tree = ast.parse(
        "import requests as api\n"
        "class Created:\n"
        f"{class_events}"
        "    value = api.get('x')\n"
    )
    resolver = mod._ScopedAliasResolver(tree)
    call = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
    )
    assert resolver.dotted_name_at(call.func, call) == expected


@pytest.mark.parametrize(
    ("class_body", "expected"),
    [
        (
            "    if enabled:\n"
            "        import numpy as api\n"
            "    else:\n"
            "        value = api.get('x')\n",
            "requests.get",
        ),
        (
            "    import numpy as api\n"
            "    if enabled:\n"
            "        del api\n"
            "    else:\n"
            "        value = api.get('x')\n",
            "numpy.get",
        ),
    ],
    ids=["sibling-import", "sibling-delete"],
)
def test_fanin_class_alias_ignores_mutually_exclusive_binding(
    class_body, expected
):
    mod = _module()
    tree = ast.parse(
        "import requests as api\n"
        "class Created:\n"
        f"{class_body}"
    )
    resolver = mod._ScopedAliasResolver(tree)
    call = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
    )
    assert resolver.dotted_name_at(call.func, call) == expected


@pytest.mark.parametrize(
    ("invocation_source", "expected"),
    [
        (
            "    try:\n"
            "        nested()\n"
            "    except NameError:\n"
            "        pass\n"
            "    import sqlite3\n",
            False,
        ),
        (
            "    import sqlite3\n"
            "    nested()\n",
            True,
        ),
        (
            "    try:\n"
            "        nested()\n"
            "    except NameError:\n"
            "        pass\n"
            "    import sqlite3\n"
            "    nested()\n",
            True,
        ),
        (
            "    alias = nested\n"
            "    try:\n"
            "        alias()\n"
            "    except NameError:\n"
            "        pass\n"
            "    import sqlite3\n",
            False,
        ),
        (
            "    try:\n"
            "        nested()\n"
            "    except NameError:\n"
            "        pass\n"
            "    import sqlite3\n"
            "    if False:\n"
            "        nested()\n",
            False,
        ),
        (
            "    callbacks = [nested]\n"
            "    try:\n"
            "        callbacks[0]()\n"
            "    except NameError:\n"
            "        pass\n"
            "    import sqlite3\n",
            False,
        ),
        (
            "    class Holder:\n"
            "        pass\n"
            "    holder = Holder()\n"
            "    holder.callback = nested\n"
            "    try:\n"
            "        holder.callback()\n"
            "    except NameError:\n"
            "        pass\n"
            "    import sqlite3\n",
            False,
        ),
    ],
    ids=[
        "before-import",
        "after-import",
        "caught-before-and-after",
        "aliased-before-import",
        "dead-after-import",
        "container-before-import",
        "attribute-before-import",
    ],
)
def test_fanin_deferred_alias_uses_invocation_time_environment(
    tmp_path, invocation_source, expected
):
    result = _escaped_nested_callable_result(
        tmp_path,
        (
            "def run():\n"
            "    def nested():\n"
            "        sqlite3.connect('x.db')\n"
            f"{invocation_source}"
        ),
    )
    if expected:
        assert result["state"] == "detected"
        assert [
            finding["resolved_api"] for finding in result["findings"]
        ] == ["sqlite3.connect"]
        assert "reason" not in result
    else:
        _r9_fanin_assert_no_dangerous(result)


@pytest.mark.parametrize(
    "helper_source",
    [
        (
            "import sqlite3\n"
            "def run():\n"
            "    global sqlite3\n"
            "    def nested():\n"
            "        sqlite3.connect('x.db')\n"
            "    nested()\n"
            "    import sqlite3\n"
        ),
        (
            "import sqlite3\n"
            "def run():\n"
            "    def nested():\n"
            "        global sqlite3\n"
            "        sqlite3.connect('x.db')\n"
            "    nested()\n"
            "    import sqlite3\n"
        ),
    ],
    ids=["parent-global", "target-global"],
)
def test_fanin_deferred_unbound_proof_respects_namespace_directives(
    tmp_path, helper_source
):
    result = _escaped_nested_callable_result(tmp_path, helper_source)
    assert result["state"] == "unknown"
    assert result["reason"] == "import_resolution_incomplete"
    assert _r9_fanin_has_finding(result, "sqlite3.connect")


def test_fanin_deferred_callable_escape_invalidates_early_unbound_proof(
    tmp_path,
):
    result = _escaped_nested_callable_result(
        tmp_path,
        (
            "def run():\n"
            "    def nested():\n"
            "        sqlite3.connect('x.db')\n"
            "    try:\n"
            "        nested()\n"
            "    except NameError:\n"
            "        pass\n"
            "    import sqlite3\n"
            "    return nested\n"
        ),
        main_source=(
            "from helper import run\n"
            "callback = run()\n"
            "callback()\n"
        ),
    )
    assert result["state"] == "unknown"
    assert result["reason"] == "import_resolution_incomplete"
    assert _r9_fanin_has_finding(result, "sqlite3.connect")


def test_fanin_aliased_nonlocal_import_can_bind_deferred_cell(tmp_path):
    result = _escaped_nested_callable_result(
        tmp_path,
        (
            "def run():\n"
            "    def bind():\n"
            "        nonlocal sqlite3\n"
            "        import sqlite3\n"
            "    alias = bind\n"
            "    alias()\n"
            "    def nested():\n"
            "        sqlite3.connect('x.db')\n"
            "    nested()\n"
            "    import sqlite3\n"
        ),
    )
    assert _r9_fanin_has_finding(result, "sqlite3.connect")


@pytest.mark.parametrize(
    ("container_source", "index"),
    [
        (
            (
                "    callbacks = [nested]\n"
                "    alias = callbacks\n"
                "    alias[0] = requests.get\n"
            ),
            0,
        ),
        (
            (
                "    nested = requests.get\n"
                "    callbacks = [nested]\n"
            ),
            0,
        ),
        (
            (
                "    sources = [nested, requests.get]\n"
                "    callbacks = [*sources, nested]\n"
            ),
            1,
        ),
    ],
    ids=["carrier-alias-mutation", "selected-name-rebind", "starred-index"],
)
def test_fanin_container_callable_proof_rejects_runtime_identity_changes(
    tmp_path, container_source, index
):
    result = _escaped_nested_callable_result(
        tmp_path,
        (
            "import requests\n"
            "def run():\n"
            "    def nested():\n"
            "        return 1\n"
            "    prefix = 'https'\n"
            f"{container_source}"
            f"    callbacks[{index}](\n"
            "        prefix + '://example.invalid'\n"
            "    )\n"
        ),
    )
    assert _r9_fanin_has_finding(result, "requests.get")


def test_fanin_reflective_container_write_preserves_exact_api(tmp_path):
    result = _escaped_nested_callable_result(
        tmp_path,
        (
            "import requests\n"
            "def nested():\n"
            "    return 1\n"
            "callbacks = [nested]\n"
            "globals()['callbacks'][0] = requests.get\n"
            "prefix = 'https'\n"
            "callbacks[0](prefix + '://example.invalid')\n"
            "def run():\n"
            "    return 1\n"
        ),
    )
    assert _r9_fanin_has_finding(result, "requests.get")


@pytest.mark.parametrize(
    "setup_and_mutation",
    [
        (
            "sources = [random.Random]\n"
            "callbacks = sources\n"
            "sources[0] = subprocess.run\n"
        ),
        (
            "callbacks = [random.Random]\n"
            "globals()['callbacks'] = [subprocess.run]\n"
        ),
        (
            "callbacks = [random.Random]\n"
            "globals().update(callbacks=[subprocess.run])\n"
        ),
        (
            "callbacks = [random.Random]\n"
            "sys.modules[__name__].callbacks[0] = subprocess.run\n"
        ),
        (
            "callbacks = [random.Random]\n"
            "setattr(\n"
            "    sys.modules[__name__], 'callbacks', [subprocess.run]\n"
            ")\n"
        ),
        (
            "callbacks = [random.Random]\n"
            "sys.modules[__name__].__dict__.update(\n"
            "    callbacks=[subprocess.run]\n"
            ")\n"
        ),
        (
            "callbacks = [random.Random]\n"
            "sys.modules[__name__].callbacks.__setitem__(\n"
            "    0, subprocess.run\n"
            ")\n"
        ),
        (
            "callbacks = [random.Random]\n"
            "sys.modules[__name__].__dict__.__setitem__(\n"
            "    'callbacks', [subprocess.run]\n"
            ")\n"
        ),
    ],
    ids=[
        "reverse-alias",
        "globals-rebind",
        "globals-update",
        "sys-modules-alias",
        "setattr-module",
        "module-dict-update",
        "module-item-call",
        "module-dict-setitem",
    ],
)
def test_fanin_runtime_container_alias_mutation_preserves_process_api(
    tmp_path, setup_and_mutation
):
    result = _escaped_nested_callable_result(
        tmp_path,
        (
            "import random\n"
            "import subprocess\n"
            "import sys\n"
            f"{setup_and_mutation}"
            "callbacks[0](['echo'])\n"
            "def run():\n"
            "    return 1\n"
        ),
    )
    assert _r9_fanin_has_finding(result, "subprocess.run")


def test_fanin_latest_reflective_carrier_replacement_controls_identity(
    tmp_path,
):
    result = _escaped_nested_callable_result(
        tmp_path,
        (
            "import random\n"
            "import subprocess\n"
            "import sys\n"
            "callbacks = [random.Random]\n"
            "globals()['callbacks'] = [subprocess.run]\n"
            "setattr(\n"
            "    sys.modules[__name__], 'callbacks', [random.Random]\n"
            ")\n"
            "callbacks[0](['echo'])\n"
            "def run():\n"
            "    return 1\n"
        ),
    )
    assert not _r9_fanin_has_finding(result, "subprocess.run")


@pytest.mark.parametrize(
    "overwrite",
    ["    api = {}\n", "    del api\n"],
    ids=["assignment", "delete"],
)
def test_fanin_dominating_alias_overwrite_kills_historical_import(
    tmp_path, overwrite
):
    result = _escaped_nested_callable_result(
        tmp_path,
        (
            "def run():\n"
            "    import requests as api\n"
            f"{overwrite}"
            "    def nested():\n"
            "        api.get('local')\n"
            "    try:\n"
            "        nested()\n"
            "    except NameError:\n"
            "        pass\n"
        ),
    )
    assert not _r9_fanin_has_finding(result, "requests.get")


@pytest.mark.parametrize(
    ("helper_source", "main_source", "expected"),
    [
        (
            (
                "def run():\n"
                "    import requests as api\n"
                "    def nested():\n"
                "        api.get('https://example.invalid')\n"
                "    return nested\n"
                "    api = {}\n"
            ),
            "from helper import run\ncallback = run()\ncallback()\n",
            True,
        ),
        (
            (
                "def run():\n"
                "    def nested():\n"
                "        api.get('https://example.invalid')\n"
                "    return nested\n"
                "    import requests as api\n"
            ),
            "from helper import run\ncallback = run()\ncallback()\n",
            False,
        ),
        (
            (
                "def run(enabled):\n"
                "    import requests as api\n"
                "    def nested():\n"
                "        api.get('https://example.invalid')\n"
                "    if enabled:\n"
                "        return nested\n"
                "    api = {}\n"
                "    return nested\n"
            ),
            (
                "from helper import run\n"
                "callback = run(bool(__name__))\n"
                "callback()\n"
            ),
            True,
        ),
    ],
    ids=[
        "unreachable-overwrite",
        "unreachable-import",
        "conditional-early-return",
    ],
)
def test_fanin_deferred_import_state_respects_terminating_paths(
    tmp_path, helper_source, main_source, expected
):
    result = _escaped_nested_callable_result(
        tmp_path, helper_source, main_source=main_source
    )
    assert _r9_fanin_has_finding(result, "requests.get") is expected


@pytest.mark.parametrize(
    "overwrite_source",
    [
        (
            "    if enabled:\n"
            "        api = {}\n"
            "    else:\n"
            "        api = []\n"
        ),
        (
            "    try:\n"
            "        pass\n"
            "    finally:\n"
            "        api = {}\n"
        ),
    ],
    ids=["exhaustive-branches", "finally"],
)
def test_fanin_deferred_import_state_joins_dominating_overwrites(
    tmp_path, overwrite_source
):
    result = _escaped_nested_callable_result(
        tmp_path,
        (
            "def run():\n"
            "    import requests as api\n"
            f"{overwrite_source}"
            "    def nested():\n"
            "        api.get('local')\n"
            "    return nested\n"
        ),
        main_source=(
            "from helper import run\n"
            "callback = run()\n"
            "callback()\n"
        ),
    )
    assert not _r9_fanin_has_finding(result, "requests.get")


@pytest.mark.parametrize(
    "member_write",
    ["    requests.get = safe\n", "    del requests.get\n"],
    ids=["assignment", "delete"],
)
def test_fanin_external_deferred_callback_respects_member_write(
    tmp_path, member_write
):
    result = _escaped_nested_callable_result(
        tmp_path,
        (
            "import requests\n"
            "def run():\n"
            "    def safe(value):\n"
            "        return value\n"
            "    def nested():\n"
            "        requests.get('https://example.invalid')\n"
            f"{member_write}"
            "    return nested\n"
        ),
        main_source=(
            "from helper import run\n"
            "callback = run()\n"
            "callback()\n"
        ),
    )
    assert not _r9_fanin_has_finding(result, "requests.get")


@pytest.mark.parametrize(
    "handler_body",
    ["        nested()\n", "        return nested\n"],
    ids=["immediate-call", "escaped-callback"],
)
def test_fanin_failed_import_handler_has_no_imported_api_candidate(
    tmp_path, handler_body
):
    result = _escaped_nested_callable_result(
        tmp_path,
        (
            "def run():\n"
            "    try:\n"
            "        import requests as api\n"
            "    except ImportError:\n"
            "        def nested():\n"
            "            api.get('https://example.invalid')\n"
            f"{handler_body}"
        ),
        main_source="from helper import run\nrun()\n",
    )
    assert not _r9_fanin_has_finding(result, "requests.get")


def test_fanin_conditional_import_preserves_concrete_api_candidate(tmp_path):
    result = _escaped_nested_callable_result(
        tmp_path,
        (
            "def run():\n"
            "    if enabled:\n"
            "        import requests as api\n"
            "    api.get('https://example.invalid')\n"
        ),
    )
    assert _r9_fanin_has_finding(result, "requests.get")


def test_fanin_failed_import_does_not_bind_alias_in_its_handler(tmp_path):
    result = _escaped_nested_callable_result(
        tmp_path,
        (
            "def run():\n"
            "    try:\n"
            "        import requests as api\n"
            "    except ImportError:\n"
            "        api.get('https://example.invalid')\n"
        ),
    )
    assert not _r9_fanin_has_finding(result, "requests.get")


@pytest.mark.parametrize(
    "assignment_source",
    [
        (
            "    if enabled:\n"
            "        api = requests\n"
            "        api.get('https://example.invalid')\n"
        ),
        (
            "    if enabled:\n"
            "        api = requests\n"
            "    else:\n"
            "        api = requests\n"
            "    api.get('https://example.invalid')\n"
        ),
    ],
    ids=["same-branch", "exhaustive-branches"],
)
def test_fanin_conditional_assignment_preserves_alias_candidate(
    tmp_path, assignment_source
):
    result = _escaped_nested_callable_result(
        tmp_path,
        "import requests\ndef run():\n" + assignment_source,
    )
    assert _r9_fanin_has_finding(result, "requests.get")


@pytest.mark.parametrize(
    "prefix",
    [
        "    api = object()\n    import requests as api\n",
        "    import numpy as api\n    import requests as api\n",
        (
            "    import numpy as api\n"
            "    del api\n"
            "    import requests as api\n"
        ),
    ],
    ids=["assignment", "prior-import", "delete"],
)
def test_fanin_last_dominating_import_controls_alias(tmp_path, prefix):
    result = _escaped_nested_callable_result(
        tmp_path,
        (
            "def run():\n"
            f"{prefix}"
            "    api.get('https://example.invalid')\n"
        ),
    )
    assert _r9_fanin_has_finding(result, "requests.get")


@pytest.mark.parametrize(
    "write_source",
    [
        "    requests.get('https://example.invalid')\n    requests.get = safe\n",
        (
            "    if False:\n"
            "        requests.get = safe\n"
            "    requests.get('https://example.invalid')\n"
        ),
    ],
    ids=["later-write", "dead-write"],
)
def test_fanin_member_write_only_invalidates_reaching_calls(
    tmp_path, write_source
):
    result = _escaped_nested_callable_result(
        tmp_path,
        "import requests\ndef run():\n" + write_source,
    )
    assert _r9_fanin_has_finding(result, "requests.get")


@pytest.mark.parametrize(
    ("helper_source", "expected"),
    [
        (
            "import requests\n"
            "def fake(value):\n"
            "    return value\n"
            "def run():\n"
            "    requests.get('https://example.invalid')\n"
            "requests.get = fake\n"
            "run()\n",
            False,
        ),
        (
            "import requests\n"
            "def fake(value):\n"
            "    return value\n"
            "def run():\n"
            "    requests.get('https://example.invalid')\n"
            "run()\n"
            "requests.get = fake\n",
            True,
        ),
        (
            "import requests\n"
            "def run():\n"
            "    def fake(value):\n"
            "        return value\n"
            "    def nested():\n"
            "        requests.get('https://example.invalid')\n"
            "    requests.get = fake\n"
            "    nested()\n",
            False,
        ),
    ],
    ids=["module-before-call", "module-after-call", "outer-before-call"],
)
def test_fanin_deferred_member_write_uses_invocation_order(
    tmp_path, helper_source, expected
):
    result = _escaped_nested_callable_result(tmp_path, helper_source)
    assert _r9_fanin_has_finding(result, "requests.get") is expected


@pytest.mark.parametrize(
    ("helper_source", "expected"),
    [
        (
            "def publish():\n"
            "    global api\n"
            "    import requests\n"
            "    api = requests\n"
            "def run():\n"
            "    publish()\n"
            "    api.get('https://example.invalid')\n",
            True,
        ),
        (
            "import requests\n"
            "class Backend:\n"
            "    def get(self, value):\n"
            "        return value\n"
            "def replace():\n"
            "    global requests\n"
            "    requests = Backend()\n"
            "def run():\n"
            "    replace()\n"
            "    requests.get('https://example.invalid')\n",
            False,
        ),
        (
            "import requests\n"
            "def clear():\n"
            "    global requests\n"
            "    del requests\n"
            "def run():\n"
            "    clear()\n"
            "    try:\n"
            "        requests.get('https://example.invalid')\n"
            "    except NameError:\n"
            "        pass\n",
            False,
        ),
    ],
    ids=["bind", "rebind", "delete"],
)
def test_fanin_invoked_global_effect_reaches_later_consumer(
    tmp_path, helper_source, expected
):
    result = _escaped_nested_callable_result(tmp_path, helper_source)
    assert _r9_fanin_has_finding(result, "requests.get") is expected


@pytest.mark.parametrize(
    ("nested_effect", "consumer", "expected"),
    [
        (
            "        api = requests\n",
            "    api.get('https://example.invalid')\n",
            True,
        ),
        (
            "        del api\n",
            (
                "    try:\n"
                "        api.get('https://example.invalid')\n"
                "    except NameError:\n"
                "        pass\n"
            ),
            False,
        ),
    ],
    ids=["bind", "delete"],
)
def test_fanin_invoked_nonlocal_effect_reaches_later_consumer(
    tmp_path, nested_effect, consumer, expected
):
    initial = "None" if expected else "requests"
    result = _escaped_nested_callable_result(
        tmp_path,
        (
            "def run():\n"
            "    import requests\n"
            f"    api = {initial}\n"
            "    def change():\n"
            "        nonlocal api\n"
            f"{nested_effect}"
            "    change()\n"
            f"{consumer}"
        ),
    )
    assert _r9_fanin_has_finding(result, "requests.get") is expected


@pytest.mark.parametrize(
    "member_effect",
    [
        "        requests.get = safe_get\n",
        "        del requests.get\n",
    ],
    ids=["mutation", "delete"],
)
def test_fanin_conditional_invoked_member_effect_invalidates_api_identity(
    tmp_path, member_effect
):
    result = _escaped_nested_callable_result(
        tmp_path,
        (
            "import requests\n"
            "def safe_get(value):\n"
            "    return value\n"
            "def change(flag):\n"
            "    if flag:\n"
            f"{member_effect}"
            "def run(flag):\n"
            "    change(flag)\n"
            "    try:\n"
            "        requests.get('https://example.invalid')\n"
            "    except AttributeError:\n"
            "        pass\n"
        ),
        main_source="from helper import run\nrun(bool(__name__))\n",
    )
    assert not _r9_fanin_has_finding(result, "requests.get")


def test_fanin_handler_type_evaluation_exception_reaches_outer_handler(
    tmp_path,
):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    try:\n"
            "        try:\n"
            "            raise ValueError()\n"
            "        except MissingHandler:\n"
            "            pass\n"
            "    except NameError:\n"
            "        dangerous()\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_fanin_handler_search_stops_before_later_type_expression(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    try:\n"
            "        try:\n"
            "            raise KeyError()\n"
            "        except KeyError:\n"
            "            pass\n"
            "        except MissingHandler:\n"
            "            pass\n"
            "    except NameError:\n"
            "        dangerous()\n"
        ),
    )
    _r9_fanin_assert_no_dangerous(result)


def test_fanin_failing_handler_type_stops_later_sibling(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    try:\n"
            "        raise KeyError()\n"
            "    except MissingHandler:\n"
            "        pass\n"
            "    except KeyError:\n"
            "        dangerous()\n"
        ),
    )
    _r9_fanin_assert_no_dangerous(result)


def test_fanin_invalid_handler_tuple_raises_type_error(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    try:\n"
            "        try:\n"
            "            raise KeyError()\n"
            "        except (ValueError, 1):\n"
            "            pass\n"
            "    except TypeError:\n"
            "        dangerous()\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_fanin_deleted_handler_alias_raises_name_error(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    Alias = ValueError\n"
            "    del Alias\n"
            "    try:\n"
            "        try:\n"
            "            raise ValueError()\n"
            "        except Alias:\n"
            "            pass\n"
            "    except UnboundLocalError:\n"
            "        dangerous()\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_fanin_nested_handler_tuple_raises_type_error(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    try:\n"
            "        try:\n"
            "            raise KeyError()\n"
            "        except (ValueError, (TypeError,)):\n"
            "            pass\n"
            "    except TypeError:\n"
            "        dangerous()\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


@pytest.mark.parametrize(
    ("alias_source", "handler_name"),
    [
        ("    Alias = ValueError\n", "Alias"),
        ("    Handlers = (ValueError, TypeError)\n", "Handlers"),
    ],
    ids=["class-alias", "tuple-alias"],
)
def test_fanin_local_handler_aliases_match_exact_exception(
    tmp_path, alias_source, handler_name
):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            f"{alias_source}"
            "    try:\n"
            "        raise ValueError()\n"
            f"    except {handler_name}:\n"
            "        dangerous()\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_fanin_nonmatching_named_handler_type_binds_for_later_sibling(
    tmp_path,
):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    try:\n"
            "        raise KeyError()\n"
            "    except (flag := ValueError):\n"
            "        pass\n"
            "    except KeyError:\n"
            "        try:\n"
            "            item = flag\n"
            "        except UnboundLocalError:\n"
            "            dangerous()\n"
        ),
    )
    _r9_fanin_assert_no_dangerous(result)


def test_fanin_failing_tuple_prefix_skips_later_handler_type_call(tmp_path):
    result = _escaped_nested_callable_result(
        tmp_path,
        (
            "import requests\n"
            "def run():\n"
            "    try:\n"
            "        raise KeyError()\n"
            "    except (MissingHandler, requests.get('x')):\n"
            "        pass\n"
        ),
    )
    assert not _r9_fanin_has_finding(result, "requests.get")


@pytest.mark.parametrize(
    "delete_source",
    [
        "    del value\n",
        "    if enabled:\n        del value\n",
        (
            "    try:\n"
            "        pass\n"
            "    finally:\n"
            "        del value\n"
        ),
    ],
    ids=["unconditional", "conditional", "finally"],
)
def test_fanin_deleted_local_load_reaches_unbound_handler(
    tmp_path, delete_source
):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    value = 1\n"
            f"{delete_source}"
            "    try:\n"
            "        return value\n"
            "    except UnboundLocalError:\n"
            "        dangerous()\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


@pytest.mark.parametrize(
    "restore_source",
    [
        "    value = 2\n",
        (
            "    if enabled:\n"
            "        value = 2\n"
            "    else:\n"
            "        value = 3\n"
        ),
        (
            "    try:\n"
            "        pass\n"
            "    finally:\n"
            "        value = 2\n"
        ),
    ],
    ids=["straight-line", "exhaustive-branches", "finally"],
)
def test_fanin_rebinding_deleted_local_avoids_unbound_handler(
    tmp_path, restore_source
):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    value = 1\n"
            "    del value\n"
            f"{restore_source}"
            "    try:\n"
            "        return value\n"
            "    except UnboundLocalError:\n"
            "        dangerous()\n"
        ),
    )
    _r9_fanin_assert_no_dangerous(result)


@pytest.mark.parametrize(
    "binding_source",
    [
        (
            "    import math\n"
            "    try:\n"
            "        item = math\n"
            "    except UnboundLocalError:\n"
            "        dangerous()\n"
        ),
        (
            "    for value in [1]:\n"
            "        try:\n"
            "            item = value\n"
            "        except UnboundLocalError:\n"
            "            dangerous()\n"
        ),
        (
            "    try:\n"
            "        raise ValueError()\n"
            "    except ValueError as error:\n"
            "        try:\n"
            "            item = error\n"
            "        except UnboundLocalError:\n"
            "            dangerous()\n"
        ),
        (
            "    if True:\n"
            "        value = 1\n"
            "    try:\n"
            "        item = value\n"
            "    except UnboundLocalError:\n"
            "        dangerous()\n"
        ),
        (
            "    value = 1\n"
            "    if False:\n"
            "        del value\n"
            "    while False:\n"
            "        del value\n"
            "    try:\n"
            "        item = value\n"
            "    except UnboundLocalError:\n"
            "        dangerous()\n"
        ),
    ],
    ids=["import", "for-target", "except-target", "if-true", "dead-delete"],
)
def test_fanin_successful_binding_events_avoid_invented_unbound_paths(
    tmp_path, binding_source
):
    result = _r6_callable_flow_result(tmp_path, binding_source)
    _r9_fanin_assert_no_dangerous(result)


@pytest.mark.parametrize(
    "flow_source",
    [
        (
            "    if 1:\n"
            "        value = 1\n"
            "    try:\n"
            "        item = value\n"
            "    except UnboundLocalError:\n"
            "        dangerous()\n"
        ),
        (
            "    value = 1\n"
            "    if 0:\n"
            "        del value\n"
            "    while 0:\n"
            "        del value\n"
            "    try:\n"
            "        item = value\n"
            "    except UnboundLocalError:\n"
            "        dangerous()\n"
        ),
    ],
    ids=["truthy-if", "falsy-if-and-while"],
)
def test_fanin_non_boolean_literal_truth_prunes_dead_paths(
    tmp_path, flow_source
):
    result = _r6_callable_flow_result(tmp_path, flow_source)
    _r9_fanin_assert_no_dangerous(result)


def test_fanin_multi_import_preserves_earlier_successful_binding(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    try:\n"
            "        import sys as item, definitely_missing_module\n"
            "    except ImportError:\n"
            "        try:\n"
            "            value = item\n"
            "        except UnboundLocalError:\n"
            "            dangerous()\n"
        ),
    )
    _r9_fanin_assert_no_dangerous(result)


def test_fanin_multi_import_failure_before_binding_reaches_handler(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    try:\n"
            "        import definitely_missing_module, sys as item\n"
            "    except ImportError:\n"
            "        try:\n"
            "            value = item\n"
            "        except UnboundLocalError:\n"
            "            dangerous()\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_fanin_short_circuit_named_expression_remains_conditional(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    callbacks and (value := 1)\n"
            "    try:\n"
            "        item = value\n"
            "    except UnboundLocalError:\n"
            "        dangerous()\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_fanin_delete_after_loop_target_binding_reaches_handler(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    for value in [1]:\n"
            "        del value\n"
            "        try:\n"
            "            item = value\n"
            "        except UnboundLocalError:\n"
            "            dangerous()\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_fanin_except_target_is_cleared_after_handler(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    try:\n"
            "        raise ValueError()\n"
            "    except ValueError as error:\n"
            "        pass\n"
            "    try:\n"
            "        item = error\n"
            "    except UnboundLocalError:\n"
            "        dangerous()\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_fanin_rebound_except_target_is_still_cleared_after_handler(
    tmp_path,
):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    try:\n"
            "        raise ValueError()\n"
            "    except ValueError as error:\n"
            "        error = safe\n"
            "    try:\n"
            "        item = error\n"
            "    except UnboundLocalError:\n"
            "        dangerous()\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_fanin_parameter_shadowed_by_except_target_is_cleared(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    try:\n"
            "        raise ValueError()\n"
            "    except ValueError as callbacks:\n"
            "        pass\n"
            "    try:\n"
            "        item = callbacks\n"
            "    except UnboundLocalError:\n"
            "        dangerous()\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_fanin_deleting_unbound_local_feeds_handler(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    value = 1\n"
            "    del value\n"
            "    try:\n"
            "        del value\n"
            "    except UnboundLocalError:\n"
            "        dangerous()\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_fanin_repeated_target_in_one_delete_feeds_handler(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    value = 1\n"
            "    try:\n"
            "        del value, value\n"
            "    except UnboundLocalError:\n"
            "        dangerous()\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


@pytest.mark.parametrize(
    "delete_statement",
    ["del (value, value)", "del [value, value]"],
    ids=["tuple", "list"],
)
def test_fanin_nested_delete_targets_preserve_left_to_right_failure(
    tmp_path, delete_statement
):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    value = 1\n"
            "    try:\n"
            f"        {delete_statement}\n"
            "    except UnboundLocalError:\n"
            "        dangerous()\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_fanin_definitely_failing_delete_does_not_reach_try_else(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    value = 1\n"
            "    try:\n"
            "        del value, value\n"
            "    except UnboundLocalError:\n"
            "        pass\n"
            "    else:\n"
            "        dangerous()\n"
        ),
    )
    _r9_fanin_assert_no_dangerous(result)


@pytest.mark.parametrize(
    "setup",
    [
        "",
        "    value = safe\n    del value\n",
    ],
    ids=["never-bound", "previously-deleted"],
)
def test_fanin_definitely_unbound_first_delete_does_not_reach_try_else(
    tmp_path, setup
):
    name = "missing" if not setup else "value"
    result = _r6_callable_flow_result(
        tmp_path,
        (
            f"{setup}"
            "    try:\n"
            f"        del {name}\n"
            "    except UnboundLocalError:\n"
            "        pass\n"
            "    else:\n"
            "        dangerous()\n"
        ),
    )
    _r9_fanin_assert_no_dangerous(result)


@pytest.mark.parametrize(
    "delete_source",
    [
        (
            "    try:\n"
            "        class Created:\n"
            "            del missing\n"
        ),
        (
            "    global missing\n"
            "    try:\n"
            "        del missing\n"
        ),
    ],
    ids=["class-namespace", "global-namespace"],
)
def test_fanin_namespace_delete_name_error_does_not_match_unbound_local(
    tmp_path, delete_source
):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            f"{delete_source}"
            "    except UnboundLocalError:\n"
            "        dangerous()\n"
        ),
    )
    _r9_fanin_assert_no_dangerous(result)


@pytest.mark.parametrize(
    "operation",
    [
        "        copy = value\n",
        "        del value\n",
    ],
    ids=["load", "delete"],
)
def test_fanin_proven_module_global_binding_avoids_name_error_handler(
    tmp_path, operation
):
    result = _escaped_nested_callable_result(
        tmp_path,
        (
            "value = 1\n"
            "import sqlite3\n"
            "def run():\n"
            "    global value\n"
            "    def dangerous():\n"
            "        import deeper\n"
            "        sqlite3.connect('x.db')\n"
            "    try:\n"
            f"{operation}"
            "    except NameError:\n"
            "        dangerous()\n"
        ),
    )
    _r9_fanin_assert_no_dangerous(result)


@pytest.mark.parametrize(
    ("invocation_source", "expected"),
    [
        ("    value = 1\n    nested()\n", False),
        ("    nested()\n    value = 1\n", True),
    ],
    ids=["bound-before-call", "unbound-before-call"],
)
def test_fanin_nonlocal_delete_uses_invocation_time_binding_state(
    tmp_path, invocation_source, expected
):
    result = _escaped_nested_callable_result(
        tmp_path,
        (
            "import sqlite3\n"
            "def run():\n"
            "    def dangerous():\n"
            "        import deeper\n"
            "        sqlite3.connect('x.db')\n"
            "    def nested():\n"
            "        nonlocal value\n"
            "        try:\n"
            "            del value\n"
            "        except NameError:\n"
            "            dangerous()\n"
            f"{invocation_source}"
        ),
    )
    assert _r9_fanin_has_finding(result, "sqlite3.connect") is expected


def test_fanin_prior_delete_target_state_reaches_later_target_exception(
    tmp_path,
):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    value = 1\n"
            "    try:\n"
            "        del value, missing\n"
            "    except UnboundLocalError:\n"
            "        try:\n"
            "            item = value\n"
            "        except UnboundLocalError:\n"
            "            dangerous()\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_fanin_deleting_bound_local_does_not_seed_handler(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    value = 1\n"
            "    try:\n"
            "        del value\n"
            "    except UnboundLocalError:\n"
            "        dangerous()\n"
        ),
    )
    _r9_fanin_assert_no_dangerous(result)


@pytest.mark.parametrize(
    "definition_source",
    [
        "        def created(value=missing):\n            pass\n",
        "        @missing\n        def created():\n            pass\n",
        "        class Created(MissingBase):\n            pass\n",
        "        class Created:\n            item = missing\n",
    ],
    ids=["default", "decorator", "class-base", "class-body"],
)
def test_fanin_definition_time_exceptions_feed_handlers(
    tmp_path, definition_source
):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    try:\n"
            f"{definition_source}"
            "    except NameError:\n"
            "        dangerous()\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_fanin_nonraising_definition_header_skips_handler(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    try:\n"
            "        def created(value=1):\n"
            "            return value\n"
            "    except NameError:\n"
            "        dangerous()\n"
        ),
    )
    _r9_fanin_assert_no_dangerous(result)


def test_fanin_lambda_default_exception_feeds_handler(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    try:\n"
            "        callback = lambda value=missing: value\n"
            "    except NameError:\n"
            "        dangerous()\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_fanin_class_body_annotation_exception_feeds_handler(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    try:\n"
            "        class Created:\n"
            "            item: missing\n"
            "    except NameError:\n"
            "        dangerous()\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_fanin_future_annotations_do_not_feed_name_error_handler(tmp_path):
    result = _escaped_nested_callable_result(
        tmp_path,
        (
            "from __future__ import annotations\n"
            "import sqlite3\n"
            "def run():\n"
            "    def dangerous():\n"
            "        import deeper\n"
            "        sqlite3.connect('x.db')\n"
            "    try:\n"
            "        def created(value: missing) -> missing_result:\n"
            "            return value\n"
            "    except NameError:\n"
            "        dangerous()\n"
        ),
    )
    _r9_fanin_assert_no_dangerous(result)


def test_fanin_local_decorator_function_is_executed(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    def decorate(target):\n"
            "        dangerous()\n"
            "        return target\n"
            "    @decorate\n"
            "    def created():\n"
            "        pass\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


@pytest.mark.parametrize(
    "class_body",
    [
        (
            "        try:\n"
            "            def __init__(self):\n"
            "                dangerous()\n"
            "        finally:\n"
            "            del __init__\n"
        ),
        (
            "        try:\n"
            "            def __init__(self):\n"
            "                dangerous()\n"
            "            del __init__\n"
            "        except Exception:\n"
            "            pass\n"
        ),
        (
            "        try:\n"
            "            def __init__(self):\n"
            "                dangerous()\n"
            "            marker = 1\n"
            "            del __init__\n"
            "        except Exception:\n"
            "            pass\n"
        ),
    ],
    ids=["finally-delete", "body-delete", "safe-statement-before-delete"],
)
def test_fanin_deleted_class_constructor_is_not_invoked(
    tmp_path, class_body
):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    class Created:\n"
            f"{class_body}"
            "    Created()\n"
        ),
    )
    _r9_fanin_assert_no_dangerous(result)


def test_fanin_failed_earlier_delete_keeps_class_constructor(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    class Created:\n"
            "        try:\n"
            "            def __init__(self):\n"
            "                dangerous()\n"
            "            del missing, __init__\n"
            "        except NameError:\n"
            "            pass\n"
            "    Created()\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_fanin_try_else_skips_unreachable_handler(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import json\n"
            "    try:\n"
            "        item = 1\n"
            "    except Exception:\n"
            "        item = dangerous\n"
            "    else:\n"
            "        item = 2\n"
            "    json.dumps([item])\n"
        ),
    )
    _assert_r9_proven_non_callable(result)


def test_fanin_multiple_handlers_use_exception_matching(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import json\n"
            "    try:\n"
            "        raise KeyError()\n"
            "    except ValueError:\n"
            "        item = dangerous\n"
            "    except KeyError:\n"
            "        item = 1\n"
            "    json.dumps([item])\n"
        ),
    )
    _assert_r9_proven_non_callable(result)


def test_fanin_condition_evaluation_exception_reaches_handler(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    try:\n"
            "        if unresolved_predicate():\n"
            "            item = safe\n"
            "        else:\n"
            "            item = safe\n"
            "    except Exception:\n"
            "        item = dangerous\n"
            "    register(item)\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_fanin_prior_assignment_survives_return_expression_exception(
    tmp_path,
):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    def choose():\n"
            "        item = safe\n"
            "        try:\n"
            "            item = dangerous\n"
            "            return unresolved_factory()\n"
            "        except Exception:\n"
            "            register(item)\n"
            "    choose()\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


@pytest.mark.parametrize(
    "protected",
    ["int('bad')", "assert False"],
    ids=["fallible-builtin", "assert"],
)
def test_fanin_proven_fallible_statement_reaches_handler(
    tmp_path, protected
):
    statement = (
        f"            {protected}\n"
        if not protected.startswith("assert")
        else f"            {protected}\n"
    )
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    try:\n"
            f"{statement}"
            "    except (ValueError, AssertionError):\n"
            "        register(dangerous)\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_fanin_unknown_exception_can_reach_later_typed_handler(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    try:\n"
            "        unresolved_factory()\n"
            "    except ValueError:\n"
            "        pass\n"
            "    except TypeError:\n"
            "        register(dangerous)\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_fanin_exception_subclass_matches_builtin_base_handler(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    try:\n"
            "        raise KeyError('missing')\n"
            "    except LookupError:\n"
            "        register(dangerous)\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_fanin_uncaught_exception_makes_later_sink_unreachable(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    item = dangerous\n"
            "    try:\n"
            "        raise KeyError('missing')\n"
            "    except ValueError:\n"
            "        item = safe\n"
            "    register(item)\n"
        ),
    )
    _r9_fanin_assert_no_dangerous(result)


@pytest.mark.parametrize(
    ("prefix", "terminator"),
    [
        ("    import sys\n", "sys.exit(0)"),
        ("", "exit()"),
        ("", "quit()"),
    ],
    ids=["sys-exit", "exit", "quit"],
)
def test_fanin_exit_paths_do_not_pollute_continuation(
    tmp_path, prefix, terminator
):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import json\n"
            f"{prefix}"
            "    def choose_enabled():\n"
            "        return False\n"
            "    enabled = choose_enabled()\n"
            "    item = 1\n"
            "    if enabled:\n"
            "        item = dangerous\n"
            f"        {terminator}\n"
            "    json.dumps([item])\n"
        ),
    )
    if terminator == "sys.exit(0)":
        assert result["state"] == "detected"
        assert [
            finding["resolved_api"] for finding in result["findings"]
        ] == ["sys.exit"]
        assert "reason" not in result
    else:
        _r9_fanin_assert_no_dangerous(result)


def test_fanin_shadowed_exit_is_not_nonreturning(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import json\n"
            "    def exit():\n"
            "        return None\n"
            "    item = dangerous\n"
            "    exit()\n"
            "    json.dumps([item])\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_fanin_scalar_binding_fixed_point_reaches_next_iteration(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    callback = safe\n"
            "    for _ in range(2):\n"
            "        callback()\n"
            "        callback = dangerous\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_fanin_three_hop_alias_fixed_point_is_order_independent(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    callbacks = []\n"
            "    root = callbacks\n"
            "    second = root\n"
            "    for _ in range(4):\n"
            "        for callback in callbacks:\n"
            "            callback()\n"
            "        third = second\n"
            "        second = root\n"
            "        third.append(dangerous)\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_fanin_mutation_after_continue_is_unreachable(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import json\n"
            "    callbacks = []\n"
            "    for _ in range(2):\n"
            "        continue\n"
            "        callbacks.append(dangerous)\n"
            "    json.dumps(callbacks)\n"
        ),
    )
    _assert_r9_proven_non_callable(result)


def test_fanin_mutation_before_break_reaches_post_loop_use(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    callbacks = []\n"
            "    for _ in range(2):\n"
            "        callbacks.append(dangerous)\n"
            "        break\n"
            "    for callback in callbacks:\n"
            "        callback()\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_fanin_nested_loop_alias_propagation_converges(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    callbacks = []\n"
            "    alias = callbacks\n"
            "    for _ in range(2):\n"
            "        for __ in range(2):\n"
            "            for callback in callbacks:\n"
            "                callback()\n"
            "            nested = alias\n"
            "            nested.append(dangerous)\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_fanin_unresolved_only_loop_cycle_is_bounded(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    callbacks = unresolved_callbacks\n"
            "    for _ in range(4):\n"
            "        alias = callbacks\n"
            "        callbacks = alias\n"
            "    for callback in callbacks:\n"
            "        callback()\n"
        ),
    )
    _assert_r7_unknown_without_dangerous_finding(result)


def test_fanin_loop_fixed_point_has_explicit_bounded_cap():
    mod = _module()
    assert isinstance(mod.LOOP_FIXED_POINT_CAP, int)
    assert 4 <= mod.LOOP_FIXED_POINT_CAP <= 128


def test_fanin_loop_chain_beyond_minimum_cap_preserves_candidate(tmp_path):
    aliases = [f"alias_{index}" for index in range(41)]
    initialization = "".join(f"    {name} = []\n" for name in aliases)
    propagation = "".join(
        f"        {left} = {right}\n"
        for left, right in zip(aliases, [*aliases[1:], "root"])
    )
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    root = []\n"
            f"{initialization}"
            "    for _ in range(50):\n"
            f"        for callback in {aliases[0]}:\n"
            "            callback()\n"
            f"{propagation}"
            "        root.append(dangerous)\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_fanin_post_loop_alias_chain_fixed_point_reaches_real_consumer(
    tmp_path,
):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    root = [dangerous]\n"
            "    first = []\n"
            "    second = []\n"
            "    third = []\n"
            "    for _ in range(3):\n"
            "        third = second\n"
            "        second = first\n"
            "        first = root\n"
            "    for callback in third:\n"
            "        callback()\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


@pytest.mark.parametrize(
    ("setup", "loop_body", "consumer"),
    [
        (
            "    callbacks = {}\n",
            "        callbacks.update({'target': dangerous})\n",
            (
                "    for callback in callbacks.values():\n"
                "        callback()\n"
            ),
        ),
        (
            "    callbacks = {}\n",
            "        callbacks.setdefault('target', dangerous)\n",
            (
                "    for callback in callbacks.values():\n"
                "        callback()\n"
            ),
        ),
        (
            "    callbacks = {}\n",
            "        callbacks['target'] = dangerous\n",
            (
                "    for callback in callbacks.values():\n"
                "        callback()\n"
            ),
        ),
        (
            (
                "    def choose_key():\n"
                "        return 'target'\n"
                "    callbacks = {}\n"
            ),
            "        callbacks[choose_key()] = dangerous\n",
            (
                "    for callback in callbacks.values():\n"
                "        callback()\n"
            ),
        ),
        (
            "    callbacks = []\n",
            "        callbacks += [dangerous]\n",
            "    for callback in callbacks:\n        callback()\n",
        ),
    ],
    ids=["dict-update", "setdefault", "exact-write", "dynamic-write", "iadd"],
)
def test_fanin_loop_carried_mutations_reach_post_loop_consumer(
    tmp_path, setup, loop_body, consumer
):
    result = _r6_callable_flow_result(
        tmp_path,
        setup + "    for _ in range(2):\n" + loop_body + consumer,
    )
    _assert_r6_dangerous_reached(result)


@pytest.mark.parametrize(
    "flow_source",
    [
        (
            "    callbacks = []\n"
            "    for _ in range(1):\n"
            "        callbacks.append(dangerous)\n"
            "    else:\n"
            "        for callback in callbacks:\n"
            "            callback()\n"
        ),
        (
            "    callbacks = []\n"
            "    for _ in range(2):\n"
            "        if False:\n"
            "            break\n"
            "        for callback in callbacks:\n"
            "            callback()\n"
            "        callbacks.append(dangerous)\n"
        ),
    ],
    ids=["loop-else", "dead-break-back-edge"],
)
def test_fanin_loop_else_and_dead_break_preserve_candidate(
    tmp_path, flow_source
):
    _assert_r6_dangerous_reached(
        _r6_callable_flow_result(tmp_path, flow_source)
    )


@pytest.mark.parametrize(
    "terminator",
    ["return None", "raise RuntimeError('stop')"],
    ids=["return", "raise"],
)
def test_fanin_terminating_branch_does_not_pollute_normal_continuation(
    tmp_path, terminator
):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import json\n"
            "    def choose_enabled():\n"
            "        return False\n"
            "    enabled = choose_enabled()\n"
            "    values = []\n"
            "    for _ in range(2):\n"
            "        if enabled:\n"
            "            values.append(dangerous)\n"
            f"            {terminator}\n"
            "        values.append(1)\n"
            "    json.dumps(values)\n"
        ),
    )
    _r9_fanin_assert_no_dangerous(result)


@pytest.mark.parametrize(
    "expression",
    [
        "[dangerous][0]",
        "dangerous or safe",
        "[dangerous] + []",
        "dangerous if enabled else unresolved",
    ],
    ids=["subscript", "boolop", "binop", "unknown-branch"],
)
def test_fanin_expression_projection_preserves_candidate(
    tmp_path, expression
):
    result = _r6_callable_flow_result(
        tmp_path, f"    register({expression})\n"
    )
    _assert_r6_dangerous_reached(result)


def test_fanin_unary_projection_preserves_candidate(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    class Projection:\n"
            "        def __pos__(self):\n"
            "            return dangerous\n"
            "    register(+Projection())\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_fanin_subscript_read_uses_reconstructed_mutation_state(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    items = [safe]\n"
            "    items[0] = dangerous\n"
            "    register(items[0])\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_fanin_lambda_escape_executes_body(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path, "    register(lambda: dangerous())\n"
    )
    _assert_r6_dangerous_reached(result)


@pytest.mark.parametrize(
    "escape_source",
    [
        (
            "    def make_callback():\n"
            "        return lambda: dangerous()\n"
            "    callback = make_callback()\n"
            "    callback()\n"
        ),
        (
            "    def consume(callback):\n"
            "        callback()\n"
            "    def choose_name():\n"
            "        return 'consume'\n"
            "    locals()[choose_name()](lambda: dangerous())\n"
        ),
        (
            "    class Holder:\n"
            "        pass\n"
            "    def choose_name():\n"
            "        return 'callback'\n"
            "    holder = Holder()\n"
            "    holder.callback = lambda: dangerous()\n"
            "    getattr(holder, choose_name())()\n"
        ),
        (
            "    def choose_key():\n"
            "        return 'callback'\n"
            "    holder = {'callback': lambda: dangerous()}\n"
            "    holder[choose_key()]()\n"
        ),
        (
            "    def consume(groups):\n"
            "        for group in groups.values():\n"
            "            for callback in group:\n"
            "                callback()\n"
            "    def choose_name():\n"
            "        return 'consume'\n"
            "    groups = {'group': [lambda: dangerous()]}\n"
            "    locals()[choose_name()](groups)\n"
        ),
    ],
    ids=["returned", "unresolved-consumer", "attribute", "subscript", "nested"],
)
def test_fanin_escaped_lambda_runtime_consumers_execute_body(
    tmp_path, escape_source
):
    _assert_r6_dangerous_reached(
        _r6_callable_flow_result(tmp_path, escape_source)
    )


def test_fanin_escaped_lambda_executes_project_import_call(tmp_path):
    repo, commit = _synthetic_repo(
        tmp_path,
        {
            "main.py": (
                "from helper import imported_dangerous\n"
                "class Holder:\n"
                "    pass\n"
                "def choose_name():\n"
                "    return 'callback'\n"
                "holder = Holder()\n"
                "holder.callback = lambda: imported_dangerous()\n"
                "getattr(holder, choose_name())()\n"
            ),
            "helper.py": (
                "import sqlite3\n"
                "def imported_dangerous():\n"
                "    sqlite3.connect('x.db')\n"
            ),
        },
    )
    result = _one_hop(repo, commit, "main.py")
    assert result["state"] == "unknown"
    assert result["reason"] == "import_resolution_incomplete"
    assert any(
        finding["resolved_api"] == "sqlite3.connect"
        and finding["imported_module_path"] == "helper.py"
        for finding in result["findings"]
    )


@pytest.mark.parametrize(
    ("support_source", "expression"),
    [
        (
            "    class Payload:\n"
            "        def __bool__(self):\n"
            "            dangerous()\n"
            "            return False\n",
            "bool(Payload())",
        ),
        (
            "    class Payload:\n"
            "        def __getitem__(self, key):\n"
            "            dangerous()\n"
            "            return 1\n",
            "Payload()[0]",
        ),
        (
            "    class Payload:\n"
            "        def __iter__(self):\n"
            "            dangerous()\n"
            "            return iter(())\n",
            "tuple(Payload())",
        ),
        (
            "    class Payload:\n"
            "        def __enter__(self):\n"
            "            dangerous()\n"
            "            return self\n"
            "        def __exit__(self, exc_type, exc, traceback):\n"
            "            return False\n"
            "    def use_context(value):\n"
            "        with value:\n"
            "            return 1\n",
            "use_context(Payload())",
        ),
    ],
    ids=["truth", "subscript", "iterator", "context-manager"],
)
def test_fanin_escaped_lambda_body_executes_implicit_protocol(
    tmp_path, support_source, expression
):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            support_source
            + "    def choose_key():\n"
            + "        return 'callback'\n"
            + "    callbacks = {}\n"
            + f"    callbacks['callback'] = lambda: {expression}\n"
            + "    callbacks[choose_key()]()\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_fanin_unescaped_dormant_lambda_body_remains_precise(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        "    callback = lambda: dangerous()\n"
        "    safe()\n",
    )
    _r9_fanin_assert_no_dangerous(result)


@pytest.mark.parametrize(
    "storage",
    [
        (
            "    class Holder:\n"
            "        pass\n"
            "    holder = Holder()\n"
            "    holder.callback = dangerous\n"
        ),
        (
            "    holder = {}\n"
            "    holder['callback'] = dangerous\n"
        ),
    ],
    ids=["attribute", "subscript"],
)
def test_fanin_direct_callable_storage_is_an_escape(tmp_path, storage):
    _assert_r6_dangerous_reached(_r6_callable_flow_result(tmp_path, storage))


@pytest.mark.parametrize(
    ("copy_expression", "expected_dangerous"),
    [("items", True), ("items.copy()", False), ("list(items)", False)],
    ids=["alias", "method-copy", "constructor-copy"],
)
def test_fanin_list_copy_and_alias_have_distinct_outer_identity(
    tmp_path, copy_expression, expected_dangerous
):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    items = []\n"
            f"    copied = {copy_expression}\n"
            "    copied.append(dangerous)\n"
            "    for callback in items:\n"
            "        callback()\n"
        ),
    )
    if expected_dangerous:
        _assert_r6_dangerous_reached(result)
    else:
        _r9_fanin_assert_no_dangerous(result)


def test_fanin_mutation_after_publication_propagates(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    items = []\n"
            "    register(items)\n"
            "    items.append(dangerous)\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


@pytest.mark.parametrize(
    "publication_source",
    [
        (
            "    class Holder:\n"
            "        pass\n"
            "    def mutate(values):\n"
            "        values.append(dangerous)\n"
            "    holder = Holder()\n"
            "    items = []\n"
            "    holder.items = items\n"
            "    mutate(items)\n"
            "    for callback in holder.items:\n"
            "        callback()\n"
        ),
        (
            "    class Holder:\n"
            "        pass\n"
            "    holder = Holder()\n"
            "    parent = []\n"
            "    holder.parent = parent\n"
            "    child = []\n"
            "    parent.append(child)\n"
            "    child.append(dangerous)\n"
            "    for group in holder.parent:\n"
            "        for callback in group:\n"
            "            callback()\n"
        ),
        (
            "    class Holder:\n"
            "        pass\n"
            "    holder = Holder()\n"
            "    mapping = {}\n"
            "    holder.values = mapping.values()\n"
            "    child = []\n"
            "    mapping.update(later=child)\n"
            "    child.append(dangerous)\n"
            "    for group in holder.values:\n"
            "        for callback in group:\n"
            "            callback()\n"
        ),
    ],
    ids=["callee-mutation", "late-child", "live-values-view"],
)
def test_fanin_published_identity_observes_later_mutation(
    tmp_path, publication_source
):
    _assert_r6_dangerous_reached(
        _r6_callable_flow_result(tmp_path, publication_source)
    )


def test_fanin_exact_string_key_dict_overwrite_is_strong(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    callbacks = {'callback': dangerous}\n"
            "    callbacks['callback'] = safe\n"
            "    for callback in callbacks.values():\n"
            "        callback()\n"
        ),
    )
    _r9_fanin_assert_no_dangerous(result)


def test_fanin_unconditional_exact_subscript_overwrite_is_strong(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    items = [dangerous]\n"
            "    items[0] = safe\n"
            "    for callback in items:\n"
            "        callback()\n"
        ),
    )
    _r9_fanin_assert_no_dangerous(result)


@pytest.mark.parametrize(
    "write",
    [
        (
            "    def choose_enabled():\n"
            "        return False\n"
            "    enabled = choose_enabled()\n"
            "    if enabled:\n"
            "        items[0] = safe\n"
        ),
        (
            "    def choose_index():\n"
            "        return 1\n"
            "    index = choose_index()\n"
            "    items[index] = safe\n"
        ),
    ],
    ids=["conditional", "dynamic-index"],
)
def test_fanin_weak_subscript_overwrite_preserves_candidate(
    tmp_path, write
):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    items = [dangerous, safe]\n"
            + write
            + "    for callback in items:\n"
            + "        callback()\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


@pytest.mark.parametrize(
    "alias_source",
    [
        "    alias = inner\n",
        "    (alias,) = outer\n",
    ],
    ids=["nested-name", "destructured"],
)
def test_fanin_nested_alias_mutation_reaches_published_owner(
    tmp_path, alias_source
):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    inner = []\n"
            "    outer = [inner]\n"
            f"{alias_source}"
            "    register(outer)\n"
            "    alias.append(dangerous)\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_fanin_exact_dict_child_alias_keeps_published_identity(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    items = []\n"
            "    mapping = {'items': items}\n"
            "    alias = mapping['items']\n"
            "    register(mapping)\n"
            "    alias.append(dangerous)\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_fanin_shallow_copy_keeps_shared_child_identity(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    inner = []\n"
            "    original = [inner]\n"
            "    copied = original.copy()\n"
            "    register(copied)\n"
            "    alias = original[0]\n"
            "    alias.append(dangerous)\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_fanin_mapping_view_keeps_live_child_identity(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    inner = []\n"
            "    values = {'item': inner}\n"
            "    view = values.values()\n"
            "    register(view)\n"
            "    inner.append(dangerous)\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_fanin_prepublication_append_creates_persistent_child_edge(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    inner = []\n"
            "    outer = []\n"
            "    outer.append(inner)\n"
            "    register(outer)\n"
            "    inner.append(dangerous)\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_fanin_strong_child_overwrite_removes_stale_identity(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    inner = []\n"
            "    outer = [inner]\n"
            "    outer[0] = []\n"
            "    register(outer)\n"
            "    inner.append(dangerous)\n"
        ),
    )
    _r9_fanin_assert_no_dangerous(result)


@pytest.mark.parametrize(
    "setup",
    [
        (
            "    def publish(value):\n"
            "        register(value)\n"
            "    items = []\n"
            "    publish(items)\n"
            "    items.append(dangerous)\n"
        ),
        (
            "    class Holder:\n"
            "        pass\n"
            "    holder = Holder()\n"
            "    def publish(value):\n"
            "        holder.value = value\n"
            "    inner = []\n"
            "    outer = [inner]\n"
            "    publish(outer)\n"
            "    inner.append(dangerous)\n"
        ),
    ],
    ids=["direct", "nested-child"],
)
def test_fanin_publication_through_local_formal_persists_in_caller(
    tmp_path, setup
):
    _assert_r6_dangerous_reached(_r6_callable_flow_result(tmp_path, setup))


def test_fanin_shadowed_safe_builtin_can_publish_container(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    list = external_register\n"
            "    items = []\n"
            "    list(items)\n"
            "    items.append(dangerous)\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_fanin_owner_rebinding_separates_tokens(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    owner = []\n"
            "    alias = owner\n"
            "    alias = []\n"
            "    alias.append(dangerous)\n"
            "    for value in owner:\n"
            "        value()\n"
        ),
    )
    _r9_fanin_assert_no_dangerous(result)


def test_fanin_mutated_actual_destructures_in_callee(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    def publish(wrapper):\n"
            "        (value,) = wrapper\n"
            "        for callback in value:\n"
            "            callback()\n"
            "    items = []\n"
            "    items.append(dangerous)\n"
            "    publish((items,))\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


@pytest.mark.parametrize(
    "invocation",
    ["publish(items)", "publish(value=items)"],
    ids=["positional", "keyword"],
)
def test_fanin_formal_alias_preserves_actual_mutation_identity(
    tmp_path, invocation
):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    def publish(value):\n"
            "        alias = value\n"
            "        alias.append(dangerous)\n"
            "        register(value)\n"
            "    items = []\n"
            f"    {invocation}\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_fanin_formal_rebinding_separates_actual_token(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    def mutate(value):\n"
            "        value = []\n"
            "        value.append(dangerous)\n"
            "    items = []\n"
            "    mutate(items)\n"
            "    for callback in items:\n"
            "        callback()\n"
        ),
    )
    _r9_fanin_assert_no_dangerous(result)


@pytest.mark.parametrize(
    "mutation_source",
    [
        "        value += [dangerous]\n        value = []\n",
        (
            "        if enabled:\n"
            "            value = []\n"
            "        value.append(dangerous)\n"
        ),
        (
            "        factory = lambda: (yield None)\n"
            "        value += [dangerous]\n"
        ),
        (
            "        if enabled:\n"
            "            del value\n"
            "        value += [dangerous]\n"
        ),
        (
            "        for _ in []:\n"
            "            value = []\n"
            "        value += [dangerous]\n"
        ),
        (
            "        for _ in callbacks:\n"
            "            value = []\n"
            "        value += [dangerous]\n"
        ),
        (
            "        for _ in [1]:\n"
            "            if enabled:\n"
            "                value = []\n"
            "        value += [dangerous]\n"
        ),
        (
            "        for value in []:\n"
            "            pass\n"
            "        value += [dangerous]\n"
        ),
        (
            "        for value in callbacks:\n"
            "            pass\n"
            "        value += [dangerous]\n"
        ),
        (
            "        if enabled:\n"
            "            (value,) = ([],)\n"
            "        value += [dangerous]\n"
        ),
        (
            "        if enabled:\n"
            "            def value():\n"
            "                return 1\n"
            "        value += [dangerous]\n"
        ),
        (
            "        if enabled:\n"
            "            import json as value\n"
            "        value += [dangerous]\n"
        ),
    ],
    ids=[
        "augassign-before-rebind",
        "conditional-rebind-before-append",
        "dormant-generator-lambda",
        "conditional-delete",
        "empty-loop-rebind",
        "unknown-loop-rebind",
        "conditional-nonempty-loop-rebind",
        "empty-loop-target",
        "unknown-loop-target",
        "conditional-destructure",
        "conditional-function",
        "conditional-import",
    ],
)
def test_fanin_local_formal_mutation_survives_possible_rebinding(
    tmp_path, mutation_source
):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    def mutate(value):\n"
            f"{mutation_source}"
            "    items = []\n"
            "    mutate(items)\n"
            "    for callback in items:\n"
            "        callback()\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


@pytest.mark.parametrize(
    "mutation_source",
    [
        "        value = []\n        value += [dangerous]\n",
        (
            "        if enabled:\n"
            "            value = []\n"
            "        else:\n"
            "            value = []\n"
            "        value.append(dangerous)\n"
        ),
    ],
    ids=["rebind-before-augassign", "exhaustive-rebind-before-append"],
)
def test_fanin_local_formal_mutation_excludes_rebound_actual(
    tmp_path, mutation_source
):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    def mutate(value):\n"
            f"{mutation_source}"
            "    items = []\n"
            "    mutate(items)\n"
            "    for callback in items:\n"
            "        callback()\n"
        ),
    )
    assert not _r9_fanin_has_finding(result, "sqlite3.connect")


def test_fanin_custom_iadd_does_not_mutate_builtin_list_actual(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    class Weird(list):\n"
            "        def __iadd__(self, other):\n"
            "            return []\n"
            "    def mutate(value):\n"
            "        value += [dangerous]\n"
            "    items = Weird()\n"
            "    mutate(items)\n"
            "    for callback in items:\n"
            "        callback()\n"
        ),
    )
    assert not _r9_fanin_has_finding(result, "sqlite3.connect")


@pytest.mark.parametrize(
    "replacement_source",
    [
        "        del value\n",
        "        def value():\n            return 1\n",
        "        import json as value\n",
        "        (value,) = ([],)\n",
        "        for value in [[]]:\n            pass\n",
        "        for _ in [1]:\n            value = []\n",
        "        for _ in [1]:\n            value = [safe]\n",
        "        for _ in [1]:\n            value = list()\n",
        "        for _ in [1]:\n            value: list = []\n",
        "        for _ in [1]:\n            value = {}\n",
        "        for _ in range(1):\n            value = []\n",
    ],
    ids=[
        "delete",
        "function",
        "import",
        "destructure",
        "for-target",
        "nonempty-loop-rebind",
        "nonempty-loop-safe-list",
        "nonempty-loop-list-call",
        "nonempty-loop-annotation",
        "nonempty-loop-dict",
        "nonempty-range-rebind",
    ],
)
def test_fanin_special_formal_replacement_blocks_mutation_transfer(
    tmp_path, replacement_source
):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    def mutate(value):\n"
            f"{replacement_source}"
            "        value += [dangerous]\n"
            "    items = []\n"
            "    mutate(items)\n"
            "    for callback in items:\n"
            "        callback()\n"
        ),
    )
    assert not _r9_fanin_has_finding(result, "sqlite3.connect")


@pytest.mark.parametrize(
    "flow_source",
    [
        (
            "    def mutate(value):\n"
            "        yield None\n"
            "        value += [dangerous]\n"
            "    items = []\n"
            "    mutate(items)\n"
            "    for callback in items:\n"
            "        callback()\n"
        ),
        (
            "    def mutate(value):\n"
            "        value += [dangerous]\n"
            "    items = []\n"
            "    other = []\n"
            "    mutate(other)\n"
            "    for callback in items:\n"
            "        callback()\n"
        ),
    ],
    ids=["generator-not-advanced", "different-actual"],
)
def test_fanin_local_formal_mutation_transfer_respects_invocation_identity(
    tmp_path, flow_source
):
    result = _r6_callable_flow_result(tmp_path, flow_source)
    assert not _r9_fanin_has_finding(result, "sqlite3.connect")


def test_fanin_unreachable_storage_does_not_publish_formal(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    class Holder:\n"
            "        pass\n"
            "    holder = Holder()\n"
            "    def dormant(value):\n"
            "        return\n"
            "        holder.value = value\n"
            "    items = []\n"
            "    items.append(dangerous)\n"
            "    dormant(items)\n"
        ),
    )
    _r9_fanin_assert_no_dangerous(result)


def test_fanin_nested_wrapper_preserves_raw_actual_context(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    def publish(value):\n"
            "        for callback in value:\n"
            "            callback()\n"
            "    def wrapper(value):\n"
            "        publish(value)\n"
            "    items = []\n"
            "    items.append(dangerous)\n"
            "    wrapper(items)\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_fanin_conditional_actual_preserves_all_source_tokens(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    def publish(value):\n"
            "        for callback in value:\n"
            "            callback()\n"
            "    first = [dangerous]\n"
            "    second = []\n"
            "    publish(first if enabled else second)\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_fanin_keyword_actual_preserves_mutation_identity(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    def mutate(*, values):\n"
            "        values.append(dangerous)\n"
            "    items = []\n"
            "    mutate(values=items)\n"
            "    register(items)\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


@pytest.mark.parametrize(
    ("protocol", "method_source"),
    [
        ("len(Payload())", "        def __len__(self):\n            dangerous()\n            return 0\n"),
        ("float(Payload())", "        def __float__(self):\n            dangerous()\n            return 0.0\n"),
        ("bool(Payload())", "        def __bool__(self):\n            dangerous()\n            return False\n"),
        ("Payload() < 1", "        def __lt__(self, other):\n            dangerous()\n            return False\n"),
        ("sum(Payload())", "        def __iter__(self):\n            dangerous()\n            return iter([])\n"),
    ],
    ids=["len", "float", "bool", "comparison", "sum"],
)
def test_fanin_implicit_protocols_execute_local_methods(
    tmp_path, protocol, method_source
):
    result = _r6_callable_flow_result(
        tmp_path,
        "    class Payload:\n" + method_source + f"    {protocol}\n",
    )
    _assert_r6_dangerous_reached(result)


@pytest.mark.parametrize(
    ("expression", "method_name", "return_value"),
    [
        ("int(Payload())", "__int__", "1"),
        ("int(Payload())", "__index__", "1"),
        ("abs(Payload())", "__abs__", "1"),
        ("hash(Payload())", "__hash__", "1"),
        ("round(Payload())", "__round__", "1"),
        ("str(Payload())", "__str__", "'value'"),
    ],
    ids=["int", "index-fallback", "abs", "hash", "round", "str"],
)
def test_fanin_scalar_protocol_family_executes_local_methods(
    tmp_path, expression, method_name, return_value
):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    class Payload:\n"
            f"        def {method_name}(self):\n"
            "            dangerous()\n"
            f"            return {return_value}\n"
            f"    {expression}\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


@pytest.mark.parametrize(
    ("expression", "method_name"),
    [
        ("+Payload()", "__pos__"),
        ("-Payload()", "__neg__"),
        ("~Payload()", "__invert__"),
        ("not Payload()", "__bool__"),
    ],
    ids=["positive", "negative", "invert", "not"],
)
def test_fanin_unary_operator_protocols_execute_local_methods(
    tmp_path, expression, method_name
):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    class Payload:\n"
            f"        def {method_name}(self):\n"
            "            dangerous()\n"
            "            return False\n"
            f"    {expression}\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


@pytest.mark.parametrize(
    ("expression", "method_source"),
    [
        (
            "sum(Values())",
            (
                "        pass\n"
                "    class Iterator:\n"
                "        def __iter__(self):\n"
                "            return self\n"
                "        def __next__(self):\n"
                "            dangerous()\n"
                "            raise StopIteration\n"
                "    class Values:\n"
                "        def __iter__(self):\n"
                "            return Iterator()\n"
            ),
        ),
        (
            "value += 1",
            (
                "        def __iadd__(self, other):\n"
                "            dangerous()\n"
                "            return self\n"
            ),
        ),
        (
            "value @ 1",
            (
                "        def __matmul__(self, other):\n"
                "            dangerous()\n"
                "            return self\n"
            ),
        ),
        (
            "value | 1",
            (
                "        def __or__(self, other):\n"
                "            dangerous()\n"
                "            return self\n"
            ),
        ),
    ],
    ids=["iterator-next", "in-place-add", "matrix", "bitwise"],
)
def test_fanin_extended_operator_protocols_execute_local_methods(
    tmp_path, expression, method_source
):
    if expression.startswith("sum"):
        flow = "    class Placeholder:\n" + method_source + f"    {expression}\n"
    else:
        flow = (
            "    class Payload:\n"
            + method_source
            + "    value = Payload()\n"
            + f"    {expression}\n"
        )
    _assert_r6_dangerous_reached(_r6_callable_flow_result(tmp_path, flow))


@pytest.mark.parametrize(
    ("expression", "preferred", "fallback"),
    [
        ("bool(Payload())", "__bool__", "__len__"),
        ("int(Payload())", "__int__", "__index__"),
    ],
    ids=["bool", "int"],
)
def test_fanin_protocol_fallback_stops_after_preferred_method(
    tmp_path, expression, preferred, fallback
):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    class Payload:\n"
            f"        def {preferred}(self):\n"
            f"            return {('False' if preferred == '__bool__' else '1')}\n"
            f"        def {fallback}(self):\n"
            "            dangerous()\n"
            "            return 1\n"
            f"    {expression}\n"
        ),
    )
    _r9_fanin_assert_no_dangerous(result)


@pytest.mark.parametrize("protocol", ["__len__", "__call__"])
def test_fanin_inherited_protocol_method_is_reached(tmp_path, protocol):
    invocation = "len(Child())" if protocol == "__len__" else "Child()()"
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    class Base:\n"
            f"        def {protocol}(self):\n"
            "            dangerous()\n"
            "            return 0\n"
            "    class Child(Base):\n"
            "        pass\n"
            f"    {invocation}\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


@pytest.mark.parametrize(
    "setup",
    [
        (
            "    class Callback:\n"
            "        def __call__(self):\n"
            "            dangerous()\n"
            "    Callback()()\n"
        ),
        (
            "    class Callback:\n"
            "        def __call__(self):\n"
            "            dangerous()\n"
            "    callback = Callback()\n"
            "    callback()\n"
        ),
    ],
    ids=["callable-class-result", "callable-instance"],
)
def test_fanin_callable_objects_execute_dunder_call(tmp_path, setup):
    _assert_r6_dangerous_reached(_r6_callable_flow_result(tmp_path, setup))


@pytest.mark.parametrize(
    "flow_source",
    [
        (
            "    import json\n"
            "    class Reader:\n"
            "        def read(self):\n"
            "            dangerous()\n"
            "            return '[]'\n"
            "    json.load(Reader())\n"
        ),
        (
            "    from pathlib import Path\n"
            "    class Source:\n"
            "        def __fspath__(self):\n"
            "            dangerous()\n"
            "            return 'input.txt'\n"
            "    Path(Source())\n"
        ),
        (
            "    import pandas as pd\n"
            "    class Source:\n"
            "        def __fspath__(self):\n"
            "            dangerous()\n"
            "            return 'input.csv'\n"
            "    pd.read_csv(Source())\n"
        ),
        (
            "    import pandas as pd\n"
            "    class Connection:\n"
            "        def cursor(self):\n"
            "            dangerous()\n"
            "            return self\n"
            "    pd.read_sql('select 1', Connection())\n"
        ),
        (
            "    import numpy as np\n"
            "    class Payload:\n"
            "        def __array__(self):\n"
            "            dangerous()\n"
            "            return []\n"
            "    np.asarray(Payload())\n"
        ),
        (
            "    import numpy as np\n"
            "    class Shape:\n"
            "        def __index__(self):\n"
            "            dangerous()\n"
            "            return 1\n"
            "    np.zeros(Shape())\n"
        ),
        (
            "    from scipy import stats\n"
            "    class Payload:\n"
            "        def __array__(self):\n"
            "            dangerous()\n"
            "            return []\n"
            "    stats.ttest_1samp(Payload(), 0)\n"
        ),
    ],
    ids=[
        "json-read",
        "path-fspath",
        "pandas-fspath",
        "pandas-cursor",
        "numpy-array",
        "numpy-index",
        "scipy-array",
    ],
)
def test_fanin_library_calls_execute_local_operand_protocols(
    tmp_path, flow_source
):
    _assert_r6_dangerous_reached(
        _r6_callable_flow_result(tmp_path, flow_source)
    )


@pytest.mark.parametrize(
    "reduction",
    ["np.sum(values)", "values.sum()"],
    ids=["module", "bound"],
)
def test_fanin_numpy_object_reduction_executes_operator_protocol(
    tmp_path, reduction
):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import numpy as np\n"
            "    class Element:\n"
            "        def __add__(self, other):\n"
            "            dangerous()\n"
            "            return self\n"
            "        def __radd__(self, other):\n"
            "            dangerous()\n"
            "            return self\n"
            "    values = np.array([Element(), Element()], dtype=object)\n"
            f"    {reduction}\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_fanin_safe_builtin_primitives_remain_precise(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import json\n"
            "    values = [\n"
            "        len([1, 2]), bool(1), int('2'), float(3),\n"
            "        abs(-4), hash('x'), round(1.5), str(5), sum([1, 2]),\n"
            "    ]\n"
            "    json.dumps(values)\n"
        ),
    )
    _assert_r9_proven_non_callable(result)


@pytest.mark.parametrize(
    "iterable_source",
    [
        (
            "    class Values:\n"
            "        def __iter__(self):\n"
            "            dangerous()\n"
            "            return iter([1])\n"
            "    sorted(Values())\n"
        ),
        (
            "    class Iterator:\n"
            "        def __iter__(self):\n"
            "            return self\n"
            "        def __next__(self):\n"
            "            dangerous()\n"
            "            raise StopIteration\n"
            "    sorted(Iterator())\n"
        ),
        (
            "    class Sequence:\n"
            "        def __getitem__(self, index):\n"
            "            dangerous()\n"
            "            raise IndexError\n"
            "    sorted(Sequence())\n"
        ),
    ],
    ids=["iter", "next", "getitem"],
)
def test_fanin_sorted_executes_source_iteration_protocols(
    tmp_path, iterable_source
):
    _assert_r6_dangerous_reached(
        _r6_callable_flow_result(tmp_path, iterable_source)
    )


@pytest.mark.parametrize(
    "sort_source",
    [
        "    values = [1]\n    values.sort(key=lambda value: dangerous())\n",
        (
            "    class Key:\n"
            "        def __call__(self, value):\n"
            "            dangerous()\n"
            "            return value\n"
            "    values = [1]\n"
            "    values.sort(key=Key())\n"
        ),
        (
            "    class Flag:\n"
            "        def __bool__(self):\n"
            "            dangerous()\n"
            "            return False\n"
            "    values = [1]\n"
            "    values.sort(reverse=Flag())\n"
        ),
        (
            "    class Element:\n"
            "        def __lt__(self, other):\n"
            "            dangerous()\n"
            "            return False\n"
            "    sorted([Element(), Element()])\n"
        ),
    ],
    ids=["lambda-key", "callable-instance-key", "reverse-bool", "element-lt"],
)
def test_fanin_sort_executes_callbacks_and_protocols(
    tmp_path, sort_source
):
    _assert_r6_dangerous_reached(
        _r6_callable_flow_result(tmp_path, sort_source)
    )


def test_fanin_sort_executes_callable_class_constructor(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    class Key:\n"
            "        def __init__(self, value):\n"
            "            dangerous()\n"
            "    values = [1]\n"
            "    values.sort(key=Key)\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_fanin_unresolved_sort_key_preserves_content_candidate(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    callbacks = [dangerous]\n"
            "    callbacks.sort(key=unresolved_key)\n"
            "    for callback in callbacks:\n"
            "        callback()\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_fanin_safe_numeric_sorted_is_precise(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import json\n"
            "    values = sorted([3, 1, 2], reverse=False)\n"
            "    json.dumps(values)\n"
        ),
    )
    _assert_r9_proven_non_callable(result)


def test_fanin_unresolved_sort_key_executes_concrete_alternative(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    key = dangerous if enabled else unresolved_key\n"
            "    sorted([1], key=key)\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


@pytest.mark.parametrize(
    "call",
    [
        "sorted([1], dangerous)",
        "sorted([1], bogus=dangerous)",
    ],
    ids=["extra-positional", "unsupported-keyword"],
)
def test_fanin_malformed_sort_signature_fails_closed_with_candidate(
    tmp_path, call
):
    _assert_r6_dangerous_reached(
        _r6_callable_flow_result(tmp_path, f"    {call}\n")
    )


@pytest.mark.parametrize(
    "sort_source",
    [
        "    sorted([], key=dangerous)\n",
        (
            "    class Element:\n"
            "        def __lt__(self, other):\n"
            "            dangerous()\n"
            "            return False\n"
            "    sorted([Element()])\n"
        ),
    ],
    ids=["empty-key", "singleton-comparison"],
)
def test_fanin_sort_avoids_callbacks_when_cardinality_forbids_them(
    tmp_path, sort_source
):
    _r9_fanin_assert_no_dangerous(
        _r6_callable_flow_result(tmp_path, sort_source)
    )


def _r9_fanin_api_flow_result(tmp_path, flow_source: str):
    return _escaped_nested_callable_result(
        tmp_path,
        (
            "import json\n"
            "import requests\n"
            "import sqlite3\n"
            "def run():\n"
            "    def dangerous():\n"
            "        requests.get('https://example.invalid')\n"
            f"{flow_source}"
        ),
    )


def test_fanin_trusted_sqlite_fetch_uses_default_row_contract(tmp_path):
    result = _r9_fanin_api_flow_result(
        tmp_path,
        (
            "    connection = sqlite3.connect(':memory:')\n"
            "    cursor = connection.cursor()\n"
            "    row = cursor.fetchone()\n"
            "    json.dumps([row])\n"
        ),
    )
    assert not _r9_fanin_has_finding(result, "requests.get")


def test_fanin_custom_sqlite_row_factory_fails_closed_with_candidate(
    tmp_path,
):
    result = _r9_fanin_api_flow_result(
        tmp_path,
        (
            "    def row_factory(cursor, row):\n"
            "        return dangerous\n"
            "    connection = sqlite3.connect(':memory:')\n"
            "    connection.row_factory = row_factory\n"
            "    row = connection.execute('select 1').fetchone()\n"
            "    register(row)\n"
        ),
    )
    assert _r9_fanin_has_finding(result, "requests.get")


@pytest.mark.parametrize("reader", ["reader", "DictReader"])
def test_fanin_trusted_csv_reader_contract_is_data_only(tmp_path, reader):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import csv\n"
            "    import json\n"
            f"    rows = csv.{reader}(['a,b'])\n"
            "    json.dumps(list(rows))\n"
        ),
    )
    _assert_r9_proven_non_callable(result)


@pytest.mark.parametrize(
    "rows_source",
    [
        (
            "        def __iter__(self):\n"
            "            dangerous()\n"
            "            return iter([])\n"
        ),
        (
            "        def __iter__(self):\n"
            "            return self\n"
            "        def __next__(self):\n"
            "            dangerous()\n"
            "            raise StopIteration\n"
        ),
        (
            "        def __getitem__(self, index):\n"
            "            dangerous()\n"
            "            raise IndexError\n"
        ),
    ],
    ids=["iter", "next", "sequence-getitem"],
)
def test_fanin_custom_csv_iterable_executes_protocol(
    tmp_path, rows_source
):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import csv\n"
            "    class Rows:\n"
            f"{rows_source}"
            "    list(csv.reader(Rows()))\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_fanin_customized_dict_reader_preserves_output_candidate(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import csv\n"
            "    rows = csv.DictReader(\n"
            "        ['a'],\n"
            "        fieldnames=['first', 'missing'],\n"
            "        restval=dangerous,\n"
            "    )\n"
            "    register(list(rows))\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_fanin_dict_reader_executes_custom_fieldnames_protocol(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import csv\n"
            "    class Fieldnames:\n"
            "        def __iter__(self):\n"
            "            dangerous()\n"
            "            return iter([])\n"
            "    list(csv.DictReader(['1'], Fieldnames()))\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_fanin_shadowed_csv_alias_does_not_invent_iteration(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import csv\n"
            "    class LocalCSV:\n"
            "        def reader(self, rows):\n"
            "            return []\n"
            "    class Rows:\n"
            "        def __iter__(self):\n"
            "            dangerous()\n"
            "            return iter([])\n"
            "    def publish(csv):\n"
            "        list(csv.reader(Rows()))\n"
            "    publish(LocalCSV())\n"
        ),
    )
    _r9_fanin_assert_no_dangerous(result)


def test_fanin_requests_response_json_requires_proven_response(tmp_path):
    result = _r9_fanin_api_flow_result(
        tmp_path,
        (
            "    response = requests.get('https://example.invalid/data')\n"
            "    decoded = response.json()\n"
            "    json.dumps([decoded])\n"
        ),
    )
    # The request itself is expected; decoding must not invent execution of
    # the dormant local callback.
    assert sum(
        finding["resolved_api"] == "requests.get"
        for finding in result["findings"]
    ) == 1


def test_fanin_requests_response_hook_preserves_concrete_candidate(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import requests\n"
            "    response = requests.get(\n"
            "        'https://example.invalid/data',\n"
            "        hooks={'response': dangerous},\n"
            "    )\n"
            "    register(response.json())\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


@pytest.mark.parametrize("callback_name", ["auth", "hooks"])
def test_fanin_requests_executes_callable_instance_callback(
    tmp_path, callback_name
):
    callback = (
        "Auth()"
        if callback_name == "auth"
        else "{'response': [Auth()]}"
    )
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import requests\n"
            "    class Auth:\n"
            "        def __call__(self, *args, **kwargs):\n"
            "            dangerous()\n"
            "            return args[0] if args else None\n"
            "    requests.get(\n"
            "        'https://example.invalid',\n"
            f"        {callback_name}={callback},\n"
            "    )\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_fanin_requests_json_custom_hook_executes_candidate(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import requests\n"
            "    response = requests.Response()\n"
            "    response._content = b'{\"value\": 1}'\n"
            "    def hook(value):\n"
            "        dangerous()\n"
            "        return value\n"
            "    response.json(object_hook=hook)\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_fanin_custom_json_receiver_preserves_concrete_candidate(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    class CustomResponse:\n"
            "        def json(self):\n"
            "            return dangerous\n"
            "    register(CustomResponse().json())\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_fanin_unknown_execute_preserves_concrete_argument(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        "    receiver.execute(dangerous)\n",
    )
    _assert_r6_dangerous_reached(result)


@pytest.mark.parametrize("api", ["pandas", "numpy", "requests"])
def test_fanin_shadowed_api_alias_does_not_retain_trust(
    tmp_path, api
):
    alias = {"pandas": "pd", "numpy": "np", "requests": "requests"}[api]
    result = _r6_callable_flow_result(
        tmp_path,
        (
            f"    import {api} as {alias}\n"
            "    class Backend:\n"
            "        def produce(self, *args, **kwargs):\n"
            "            return dangerous\n"
            f"    {alias} = Backend()\n"
            f"    item = {alias}.produce()\n"
            "    register(item)\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_fanin_module_level_api_alias_rebinding_invalidates_trust(tmp_path):
    helper_source = (
        "import numpy as np\n"
        "import sqlite3\n"
        "class Backend:\n"
        "    def asarray(self, values, **kwargs):\n"
        "        return values[0]\n"
        "providers = [Backend()]\n"
        "np = providers[0]\n"
        "def run():\n"
        "    def dangerous():\n"
        "        import deeper\n"
        "        sqlite3.connect('x.db')\n"
        "    item = np.asarray([dangerous], dtype=float)\n"
        "    register(item)\n"
    )
    assert "np" not in _module().collect_aliases(ast.parse(helper_source))
    result = _escaped_nested_callable_result(tmp_path, helper_source)
    assert result["state"] == "unknown"
    assert set(result["reason"].split("; ")) == {
        "import_resolution_incomplete",
        "imported_scan_incomplete",
    }
    assert _r9_fanin_has_finding(result, "sqlite3.connect")


def test_fanin_rebound_requests_alias_does_not_invent_api_identity(tmp_path):
    result = _escaped_nested_callable_result(
        tmp_path,
        (
            "import requests\n"
            "import sqlite3\n"
            "providers = [object()]\n"
            "requests = providers[0]\n"
            "def run():\n"
            "    def dangerous():\n"
            "        import deeper\n"
            "        sqlite3.connect('x.db')\n"
            "    requests.get(\n"
            "        'https://example.invalid',\n"
            "        hooks={'response': dangerous},\n"
            "    )\n"
        ),
    )
    assert result["state"] == "unknown"
    assert set(result["reason"].split("; ")) == {
        "import_resolution_incomplete",
        "imported_scan_incomplete",
    }
    assert not _r9_fanin_has_finding(result, "requests.get")
    assert _r9_fanin_has_finding(result, "sqlite3.connect")


def test_fanin_dormant_local_alias_does_not_pollute_module_import(tmp_path):
    result = _escaped_nested_callable_result(
        tmp_path,
        (
            "import requests\n"
            "def dormant():\n"
            "    requests = other\n"
            "def run():\n"
            "    requests.get('https://example.invalid')\n"
        ),
    )
    assert _r9_fanin_has_finding(result, "requests.get")


def test_fanin_dormant_sibling_import_does_not_create_alias(tmp_path):
    result = _escaped_nested_callable_result(
        tmp_path,
        (
            "def dormant():\n"
            "    import requests as client\n"
            "def run():\n"
            "    client.get('https://example.invalid')\n"
        ),
    )
    assert not _r9_fanin_has_finding(result, "requests.get")


def test_fanin_dormant_import_cannot_overwrite_module_alias(tmp_path):
    result = _escaped_nested_callable_result(
        tmp_path,
        (
            "import requests\n"
            "def dormant():\n"
            "    import numpy as requests\n"
            "def run():\n"
            "    requests.get('https://example.invalid')\n"
        ),
    )
    assert _r9_fanin_has_finding(result, "requests.get")


@pytest.mark.parametrize(
    "binding",
    [
        "def run(requests):\n",
        (
            "class Backend:\n"
            "    def get(self, value):\n"
            "        return value\n"
            "def run():\n"
            "    requests = Backend()\n"
        ),
        (
            "class Backend:\n"
            "    def get(self, value):\n"
            "        return value\n"
            "client = requests\n"
            "client = Backend()\n"
            "def run():\n"
        ),
    ],
    ids=["parameter", "local-rebind", "derived-rebind"],
)
def test_fanin_shadowed_api_root_does_not_invent_effect(tmp_path, binding):
    prefix = "import requests\n"
    receiver = "client" if "client =" in binding else "requests"
    result = _escaped_nested_callable_result(
        tmp_path,
        prefix + binding
        + f"    {receiver}.get('https://example.invalid')\n",
        main_source=(
            "from helper import run\n"
            "run(object())\n"
            if binding == "def run(requests):\n"
            else "from helper import run\nrun()\n"
        ),
    )
    assert not _r9_fanin_has_finding(result, "requests.get")


def test_fanin_comprehension_walrus_invalidates_module_alias(tmp_path):
    result = _escaped_nested_callable_result(
        tmp_path,
        (
            "import requests\n"
            "class Backend:\n"
            "    def get(self, value):\n"
            "        return value\n"
            "[(requests := Backend()) for _ in [0]]\n"
            "def run():\n"
            "    requests.get('https://example.invalid')\n"
        ),
    )
    assert not _r9_fanin_has_finding(result, "requests.get")


def test_fanin_member_rebind_invalidates_exact_api_identity(tmp_path):
    result = _escaped_nested_callable_result(
        tmp_path,
        (
            "import requests\n"
            "def fake_get(value):\n"
            "    return value\n"
            "requests.get = fake_get\n"
            "def run():\n"
            "    requests.get('https://example.invalid')\n"
        ),
    )
    assert not _r9_fanin_has_finding(result, "requests.get")


def test_fanin_sibling_local_aliases_are_scope_order_independent(tmp_path):
    result = _escaped_nested_callable_result(
        tmp_path,
        (
            "def dormant():\n"
            "    import numpy as api\n"
            "    api.get('not-a-network-api')\n"
            "def run():\n"
            "    import requests as api\n"
            "    api.get('https://example.invalid')\n"
        ),
    )
    assert sum(
        finding["resolved_api"] == "requests.get"
        for finding in result["findings"]
    ) == 1


@pytest.mark.parametrize(
    "protocol_source",
    [
        (
            "    class Sequence:\n"
            "        def __getitem__(self, index):\n"
            "            dangerous()\n"
            "            raise IndexError\n"
            "    sum(Sequence())\n"
        ),
        (
            "    class Iterator:\n"
            "        def __iter__(self):\n"
            "            return self\n"
            "        def __next__(self):\n"
            "            dangerous()\n"
            "            raise StopIteration\n"
            "    sum(Iterator())\n"
        ),
        (
            "    class Start:\n"
            "        def __add__(self, value):\n"
            "            dangerous()\n"
            "            return self\n"
            "    sum([1], Start())\n"
        ),
    ],
    ids=["sequence-getitem", "iterator-next", "custom-start"],
)
def test_fanin_sum_executes_all_implicit_protocols(
    tmp_path, protocol_source
):
    _assert_r6_dangerous_reached(
        _r6_callable_flow_result(tmp_path, protocol_source)
    )


@pytest.mark.parametrize("constructor", ["list", "tuple", "set", "dict"])
def test_fanin_shadowed_carrier_constructor_does_not_publish_contents(
    tmp_path, constructor
):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            f"    def {constructor}(value):\n"
            "        return []\n"
            f"    register({constructor}([dangerous]))\n"
        ),
    )
    _r9_fanin_assert_no_dangerous(result)


@pytest.mark.parametrize(
    "escape_source",
    [
        (
            "    class Callback:\n"
            "        def __call__(self):\n"
            "            dangerous()\n"
            "    register(Callback())\n"
        ),
        (
            "    class Callback:\n"
            "        def __call__(self):\n"
            "            dangerous()\n"
            "    class Holder:\n"
            "        pass\n"
            "    holder = Holder()\n"
            "    holder.callback = Callback()\n"
        ),
        (
            "    class Callback:\n"
            "        def __init__(self):\n"
            "            dangerous()\n"
            "    register(Callback)\n"
        ),
    ],
    ids=["instance", "stored-instance", "class-constructor"],
)
def test_fanin_escaped_callable_objects_preserve_execution(
    tmp_path, escape_source
):
    _assert_r6_dangerous_reached(
        _r6_callable_flow_result(tmp_path, escape_source)
    )


@pytest.mark.parametrize(
    "hook_source",
    [
        (
            "    callbacks = [Auth()]\n"
            "    hooks = {'response': callbacks}\n"
        ),
        (
            "    callbacks = []\n"
            "    hooks = {'response': callbacks}\n"
            "    callbacks.append(Auth())\n"
        ),
        (
            "    callback = lambda response: dangerous()\n"
            "    hooks = {'response': [callback]}\n"
        ),
    ],
    ids=["aliased", "mutated", "named-lambda"],
)
def test_fanin_requests_hook_carriers_preserve_callbacks(
    tmp_path, hook_source
):
    class_source = (
        "    import requests\n"
        "    class Auth:\n"
        "        def __call__(self, response):\n"
        "            dangerous()\n"
        "            return response\n"
    )
    result = _r6_callable_flow_result(
        tmp_path,
        class_source + hook_source
        + "    requests.get('https://example.invalid', hooks=hooks)\n",
    )
    _assert_r6_dangerous_reached(result)


@pytest.mark.parametrize(
    "callback_argument",
    ["object_hook=[dangerous]", "parse_int={'callback': dangerous}"],
)
def test_fanin_json_single_callback_slot_does_not_flatten_malformed_carrier(
    tmp_path, callback_argument
):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import json\n"
            f"    json.loads('1', {callback_argument})\n"
        ),
    )
    _r9_fanin_assert_no_dangerous(result)


def test_fanin_requests_basic_auth_uses_string_protocol_not_call(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import requests\n"
            "    class Credential:\n"
            "        def __call__(self, request):\n"
            "            open('unexpected-call.txt', 'w')\n"
            "            return request\n"
            "        def __str__(self):\n"
            "            dangerous()\n"
            "            return 'user'\n"
            "    requests.get(\n"
            "        'https://example.invalid',\n"
            "        auth=(Credential(), 'password'),\n"
            "    )\n"
        ),
    )
    _assert_r6_dangerous_reached(result)
    assert not _r9_fanin_has_finding(result, "open")


@pytest.mark.parametrize(
    "auth_assignment",
    [
        "    auth = (Credential(), 'password')\n",
        (
            "    auth = ((Credential(), 'password') if enabled "
            "else ('user', 'password'))\n"
        ),
    ],
    ids=["named", "conditional"],
)
def test_fanin_named_basic_auth_tuple_uses_string_protocol(
    tmp_path, auth_assignment
):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import requests\n"
            "    class Credential:\n"
            "        def __str__(self):\n"
            "            dangerous()\n"
            "            return 'user'\n"
            f"{auth_assignment}"
            "    requests.get('https://example.invalid', auth=auth)\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


@pytest.mark.parametrize(
    "key_expression",
    ["callbacks['key']", "callbacks.get('key')", "{'key': dangerous}['key']"],
    ids=["named-subscript", "named-get", "literal-subscript"],
)
def test_fanin_exact_mapping_callback_lookup_preserves_candidate(
    tmp_path, key_expression
):
    assignment = (
        "    callbacks = {'key': dangerous}\n"
        if key_expression.startswith("callbacks")
        else ""
    )
    result = _r6_callable_flow_result(
        tmp_path,
        assignment
        + f"    sorted([1], key={key_expression})\n",
    )
    _assert_r6_dangerous_reached(result)


@pytest.mark.parametrize(
    "lookup_source",
    [
        "    register({'cb': dangerous}['cb'])\n",
        (
            "    mapping = {'cb': dangerous}\n"
            "    register(mapping['cb'])\n"
        ),
    ],
    ids=["literal", "named"],
)
def test_fanin_exact_dict_subscript_escape_preserves_candidate(
    tmp_path, lookup_source
):
    _assert_r6_dangerous_reached(
        _r6_callable_flow_result(tmp_path, lookup_source)
    )


def test_fanin_trusted_sqlite_fetchall_uses_default_row_contract(tmp_path):
    result = _r9_fanin_api_flow_result(
        tmp_path,
        (
            "    connection = sqlite3.connect('x.db')\n"
            "    rows = connection.execute('SELECT 1').fetchall()\n"
            "    json.dumps(rows)\n"
        ),
    )
    assert not _r9_fanin_has_finding(result, "requests.get")


@pytest.mark.parametrize(
    "sqlite_source",
    [
        (
            "    class Factory:\n"
            "        def __call__(self, cursor, row):\n"
            "            dangerous()\n"
            "            return row\n"
            "    connection = sqlite3.connect('x.db')\n"
            "    connection.row_factory = Factory()\n"
            "    connection.execute('SELECT 1').fetchall()\n"
        ),
        (
            "    class Factory:\n"
            "        def __call__(self, *args, **kwargs):\n"
            "            dangerous()\n"
            "            return sqlite3.Connection(*args, **kwargs)\n"
            "    sqlite3.connect('x.db', factory=Factory())\n"
        ),
        (
            "    class Converter:\n"
            "        def __call__(self, value):\n"
            "            dangerous()\n"
            "            return value\n"
            "    sqlite3.register_converter('X', Converter())\n"
        ),
    ],
    ids=["row-factory", "connection-factory", "converter"],
)
def test_fanin_sqlite_callable_instances_preserve_callbacks(
    tmp_path, sqlite_source
):
    _assert_r6_dangerous_reached(
        _r6_callable_flow_result(tmp_path, sqlite_source)
    )


def test_fanin_pandas_numeric_series_path_is_precise(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import json\n"
            "    import pandas as pd\n"
            "    data = pd.Series([1.0, 2.0])\n"
            "    json.dumps([data])\n"
        ),
    )
    _assert_r9_proven_non_callable(result)


def test_fanin_pandas_numeric_dataframe_path_is_precise(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import json\n"
            "    import pandas as pd\n"
            "    data = pd.DataFrame({'score': [1.0, 2.0]})\n"
            "    json.dumps([data])\n"
        ),
    )
    _assert_r9_proven_non_callable(result)


def test_fanin_pandas_read_sql_default_sqlite_source_is_precise(tmp_path):
    result = _r9_fanin_api_flow_result(
        tmp_path,
        (
            "    import pandas as pd\n"
            "    connection = sqlite3.connect('input.db')\n"
            "    frame = pd.read_sql('select 1', connection)\n"
            "    json.dumps([frame])\n"
        ),
    )
    assert not _r9_fanin_has_finding(result, "requests.get")


@pytest.mark.parametrize(
    ("cursor_method", "read_options"),
    [
        (
            "        def execute(self, query):\n"
            "            dangerous()\n"
            "            return self\n"
            "        def fetchall(self):\n"
            "            return []\n",
            "",
        ),
        (
            "        def execute(self, query):\n"
            "            return self\n"
            "        def fetchall(self):\n"
            "            return [(dangerous,)]\n",
            "",
        ),
        (
            "        def execute(self, query):\n"
            "            return self\n"
            "        def fetchmany(self, size):\n"
            "            return [(dangerous,)]\n",
            ", chunksize=1",
        ),
    ],
    ids=["execute", "fetchall", "fetchmany"],
)
def test_fanin_pandas_read_sql_executes_custom_cursor_pipeline(
    tmp_path, cursor_method, read_options
):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import pandas as pd\n"
            "    class Cursor:\n"
            f"{cursor_method}"
            "        def close(self):\n"
            "            return None\n"
            "    class Connection:\n"
            "        def cursor(self):\n"
            "            return Cursor()\n"
            "    frame = pd.read_sql(\n"
            "        'select 1', Connection()"
            f"{read_options}\n"
            "    )\n"
            "    register(frame)\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


@pytest.mark.parametrize(
    "read_call",
    [
        (
            "pd.read_sql("
            "'select 1', Connection(), None, True, None, None, None, 1)"
        ),
        (
            "pd.read_sql_query("
            "'select 1', Connection(), None, True, None, None, 1)"
        ),
        (
            "pd.read_sql_table("
            "'table', Connection(), None, None, True, None, None, 1)"
        ),
    ],
    ids=["read-sql", "read-sql-query", "read-sql-table"],
)
def test_fanin_pandas_positional_chunksize_uses_fetchmany(
    tmp_path, read_call
):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import pandas as pd\n"
            "    class Cursor:\n"
            "        def execute(self, query):\n"
            "            return self\n"
            "        def fetchmany(self, size):\n"
            "            return [(dangerous,)]\n"
            "        def close(self):\n"
            "            return None\n"
            "    class Connection:\n"
            "        def cursor(self):\n"
            "            return Cursor()\n"
            f"    frame = {read_call}\n"
            "    register(frame)\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_fanin_pandas_invalid_duplicate_connection_skips_cursor(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import pandas as pd\n"
            "    class Connection:\n"
            "        def cursor(self):\n"
            "            dangerous()\n"
            "            return self\n"
            "    pd.read_sql(\n"
            "        'select 1', Connection(), con=Connection()\n"
            "    )\n"
        ),
    )
    _assert_r7_unknown_without_dangerous_finding(result)
    assert result["findings"] == []


@pytest.mark.parametrize(
    "api_source",
    [
        (
            "    import pandas as pd\n"
            "    source = [dangerous] if enabled else unresolved_source\n"
            "    pd.read_csv(source)\n"
        ),
        (
            "    from pathlib import Path\n"
            "    source = [dangerous] if enabled else unresolved_source\n"
            "    Path(source)\n"
        ),
        (
            "    import csv\n"
            "    source = [dangerous] if enabled else unresolved_source\n"
            "    list(csv.reader(source))\n"
        ),
        (
            "    import numpy as np\n"
            "    source = [dangerous] if enabled else unresolved_source\n"
            "    np.asarray(source, dtype=float)\n"
        ),
        (
            "    from scipy import stats\n"
            "    source = [dangerous] if enabled else unresolved_source\n"
            "    stats.ttest_1samp(source, 0)\n"
        ),
        (
            "    import random\n"
            "    class Bound:\n"
            "        def __index__(self):\n"
            "            dangerous()\n"
            "            return 1\n"
            "    if enabled:\n"
            "        random.randrange(Bound())\n"
            "    else:\n"
            "        random.randrange(unresolved_bound)\n"
        ),
    ],
    ids=["pandas", "path", "csv", "numpy", "scipy", "random"],
)
def test_fanin_unknown_api_operand_preserves_concrete_alternative(
    tmp_path, api_source
):
    _assert_r6_dangerous_reached(
        _r6_callable_flow_result(tmp_path, api_source)
    )


@pytest.mark.parametrize(
    "api_call",
    [
        "json.loads('[]', object_hook=option)",
        "pd.read_csv('input.csv', engine=option)",
        "np.zeros(1, bogus=option)",
        "random.random(option)",
    ],
    ids=["json", "pandas", "numpy", "random"],
)
def test_fanin_unresolved_api_option_preserves_concrete_alternative(
    tmp_path, api_call
):
    imports = (
        "    import json\n"
        "    import numpy as np\n"
        "    import pandas as pd\n"
        "    import random\n"
    )
    result = _r6_callable_flow_result(
        tmp_path,
        imports
        + "    option = dangerous if enabled else unresolved_option\n"
        + f"    {api_call}\n",
    )
    _assert_r6_dangerous_reached(result)


def test_fanin_numpy_numeric_dtype_is_precise(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import json\n"
            "    import numpy as np\n"
            "    data = np.array([1.0, 2.0], dtype=float)\n"
            "    json.dumps([data])\n"
        ),
    )
    _assert_r9_proven_non_callable(result)


def test_fanin_numpy_object_dtype_preserves_concrete_candidate(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import numpy as np\n"
            "    data = np.array([dangerous], dtype=object)\n"
            "    register(data)\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_fanin_scipy_unresolved_operand_preserves_candidate(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    from scipy import stats\n"
            "    value = stats.ttest_1samp([dangerous], unresolved_mean)\n"
            "    register(value)\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


def test_fanin_random_validates_index_protocol(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import random\n"
            "    class Bound:\n"
            "        def __index__(self):\n"
            "            dangerous()\n"
            "            return 1\n"
            "    random.randrange(Bound())\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


@pytest.mark.parametrize(
    "random_source",
    [
        (
            "    class Values:\n"
            "        def __len__(self):\n"
            "            dangerous()\n"
            "            return 1\n"
            "        def __getitem__(self, index):\n"
            "            return 1\n"
            "    random.choice(Values())\n"
        ),
        (
            "    class Values:\n"
            "        def __len__(self):\n"
            "            return 1\n"
            "        def __getitem__(self, index):\n"
            "            dangerous()\n"
            "            return 1\n"
            "    random.choice(Values())\n"
        ),
        (
            "    from collections.abc import Sequence\n"
            "    class Values(Sequence):\n"
            "        def __len__(self):\n"
            "            dangerous()\n"
            "            return 1\n"
            "        def __getitem__(self, index):\n"
            "            if index == 0:\n"
            "                return 1\n"
            "            raise IndexError\n"
            "    random.sample(Values(), 1)\n"
        ),
        (
            "    class Values(list):\n"
            "        def __iter__(self):\n"
            "            dangerous()\n"
            "            return super().__iter__()\n"
            "    random.sample(Values([1]), 1)\n"
        ),
    ],
    ids=["choice-len", "choice-getitem", "sample-len", "sample-iter"],
)
def test_fanin_random_sequence_protocols_are_executed(
    tmp_path, random_source
):
    result = _r6_callable_flow_result(
        tmp_path, "    import random\n" + random_source
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
            "import sqlite3\n"
            "class Local:\n"
            "    def __init__(self):\n"
            "        sqlite3.connect('dynamic.db')\n"
            "registry = {'local': Local}\n"
            "def choose_key():\n"
            "    return 'local'\n"
            "key = choose_key()\n"
            "instance = registry[key]()\n"
        ),
    )
    assert result["state"] == "unknown"
    assert set(result["reason"].split("; ")) == {
        "import_resolution_incomplete",
        "imported_scan_incomplete",
    }
    assert len(_r8_sqlite_findings(result)) == 1


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


# ── R9 receiver provenance projection proofs ────────────────────────────────


def _r9_filesystem_read_apis(source: str) -> list[str]:
    result = _analyze(source)
    return [
        finding["resolved_api"]
        for finding in result["evidence"]["filesystem_read"]["findings"]
    ]


def test_r9_unique_helper_call_receiver_origin_is_preserved_through_alias():
    assert _r9_filesystem_read_apis(
        "def make_path():\n"
        "    return object()\n"
        "def run():\n"
        "    receiver = make_path()\n"
        "    alias = receiver\n"
        "    alias.read_text()\n"
    ) == ["make_path().read_text"]


def test_r9_nested_receiver_call_chain_preserves_root_call_origin():
    mod = _module()
    tree = ast.parse(
        "def make_connection():\n"
        "    return object()\n"
        "def run():\n"
        "    connection = make_connection()\n"
        "    cursor = connection.cursor()\n"
        "    cursor.read_text()\n"
    )
    call = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "read_text"
    )
    resolver = mod._ScopedAliasResolver(tree)
    assert mod._effect_call_name(
        call, resolver, resolver.module_aliases()
    ) == ("make_connection().cursor().read_text", False)


def test_r9_branch_local_receiver_chain_preserves_dominating_origin():
    mod = _module()
    tree = ast.parse(
        "def run(items):\n"
        "    for item in items:\n"
        "        if item:\n"
        "            connection = make_connection()\n"
        "            cursor = connection.cursor()\n"
        "            cursor.read_text()\n"
    )
    call = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "read_text"
    )
    resolver = mod._ScopedAliasResolver(tree)
    assert mod._effect_call_name(
        call, resolver, resolver.module_aliases()
    ) == ("make_connection().cursor().read_text", False)


def test_r9_frozen_projection_recovers_only_missing_effect_classification():
    result = _analyze(
        "from lottery_api.database import DatabaseManager\n"
        "def load():\n"
        "    manager = DatabaseManager()\n"
        "    result = manager.get_draws()\n"
        "    return result\n"
        "def report(items):\n"
        "    for label, result in items:\n"
        "        result.get('draws')\n"
    )
    assert [
        finding["resolved_api"]
        for finding in result["evidence"]["database_access"]["findings"]
    ] == [
        "lottery_api.database.DatabaseManager",
        "lottery_api.database.DatabaseManager().get_draws",
        "lottery_api.database.DatabaseManager().get_draws().get",
    ]


def test_r9_direct_receiver_expression_preserves_its_call_origin():
    assert _r9_filesystem_read_apis(
        "def make_path():\n"
        "    return object()\n"
        "make_path().read_text()\n"
    ) == ["make_path().read_text"]


def test_r9_strong_receiver_rebinding_uses_latest_call_origin():
    assert _r9_filesystem_read_apis(
        "def run():\n"
        "    receiver = first_path()\n"
        "    receiver = second_path()\n"
        "    receiver.read_text()\n"
    ) == ["second_path().read_text"]


def test_r9_conditional_receiver_alternatives_fail_closed():
    assert _r9_filesystem_read_apis(
        "def run(flag):\n"
        "    if flag:\n"
        "        receiver_path = left_path()\n"
        "    else:\n"
        "        receiver_path = right_path()\n"
        "    receiver_path.read_text()\n"
    ) == ["receiver_path.read_text"]


def test_r9_unresolved_and_parameter_receivers_keep_source_spelling():
    assert _r9_filesystem_read_apis(
        "def from_parameter(receiver_path):\n"
        "    receiver_path.read_text()\n"
        "def unresolved():\n"
        "    missing_path.read_text()\n"
    ) == ["receiver_path.read_text", "missing_path.read_text"]


def test_r9_same_receiver_name_isolated_by_lexical_owner():
    assert _r9_filesystem_read_apis(
        "def left():\n"
        "    receiver = left_path()\n"
        "    receiver.read_text()\n"
        "def right():\n"
        "    receiver = right_path()\n"
        "    receiver.read_text()\n"
    ) == ["left_path().read_text", "right_path().read_text"]


def test_r9_receiver_origin_is_independent_of_binding_storage_order():
    mod = _module()
    tree = ast.parse(
        "def run():\n"
        "    receiver = first_source()\n"
        "    receiver = second_source()\n"
        "    receiver.read_text()\n"
    )
    call = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "read_text"
    )
    resolver = mod._ScopedAliasResolver(tree)
    aliases = resolver.module_aliases()
    forward = mod._effect_call_name(call, resolver, aliases)
    for scope_bindings in resolver.bindings.values():
        for records in scope_bindings.values():
            records.reverse()
    resolver._aliases_cache.clear()
    resolver._runtime_aliases_cache.clear()
    resolver._dotted_cache.clear()
    resolver._receiver_call_origin_cache.clear()
    reversed_storage = mod._effect_call_name(
        call, resolver, resolver.module_aliases()
    )
    assert forward == reversed_storage == ("second_source().read_text", False)


def test_r9_receiver_projection_preserves_exact_finding_order():
    assert _r9_filesystem_read_apis(
        "def run():\n"
        "    first = alpha_path()\n"
        "    first.read_text()\n"
        "    direct_path().read_text()\n"
        "    last = omega_path()\n"
        "    last.read_text()\n"
    ) == [
        "alpha_path().read_text",
        "direct_path().read_text",
        "omega_path().read_text",
    ]


# ── R9 cache transparency and isolation proofs ───────────────────────────────


def _r9_summary_execution_probe(
    source: str,
    *,
    use_structural_summary: bool,
    use_demand_driven_dataflow: bool | None = None,
    use_stable_dataflow_raise_cache: bool | None = None,
    use_full_corpus_query_collapse: bool | None = None,
    reverse_dataflow_predecessors: bool = False,
) -> dict[str, object]:
    mod = _module()
    tree = ast.parse(source)
    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    classes = {
        node.name: node for node in tree.body if isinstance(node, ast.ClassDef)
    }
    definition = functions["run"]
    metrics: dict[str, object] = {}
    nodes, states, resolutions, incomplete = mod._definition_execution_nodes(
        definition,
        mod.collect_aliases(tree),
        None,
        functions,
        classes,
        trusted_aliases=mod._ScopedAliasResolver(tree).module_aliases(),
        module_bound_names=mod._module_bound_names_before(tree, definition),
        use_structural_summary=use_structural_summary,
        use_demand_driven_dataflow=use_demand_driven_dataflow,
        use_stable_dataflow_raise_cache=(
            use_stable_dataflow_raise_cache
        ),
        use_full_corpus_query_collapse=(
            use_full_corpus_query_collapse
        ),
        reverse_dataflow_predecessors=reverse_dataflow_predecessors,
        debug_metrics=metrics,
    )
    node_by_id = {id(node): node for node in ast.walk(tree)}

    def normalized_node(node: ast.AST) -> tuple[str, str]:
        return type(node).__name__, ast.dump(node, include_attributes=True)

    return {
        "ordered_nodes": tuple(normalized_node(node) for node in nodes),
        "states": tuple(sorted(
            (normalized_node(node_by_id[node_id]), state)
            for node_id, state in states.items()
        )),
        "resolutions": tuple(sorted(
            (normalized_node(node_by_id[node_id]), state)
            for node_id, state in resolutions.items()
        )),
        "call_names": tuple(sorted({
            (mod._dotted_name(node.func, mod.collect_aliases(tree)) or "")
            .replace("()", "")
            for node in nodes
            if isinstance(node, ast.Call)
        })),
        "incomplete": incomplete,
        "metrics": metrics,
    }


def test_r9_structural_summary_exposes_immutable_complete_definition_facts():
    mod = _module()
    tree = ast.parse(
        "def run(flag, callback):\n"
        "    values = [callback]\n"
        "    try:\n"
        "        if flag:\n"
        "            values.append(callback)\n"
        "    except Exception:\n"
        "        del values\n"
        "    for item in values:\n"
        "        item()\n"
    )
    definition = tree.body[0]
    summary = mod._definition_structural_summary(definition)

    assert summary.definition_identity == id(definition)
    for field in (
        "statements", "expressions", "control_flow_edges",
        "exception_operations", "lexical_bindings", "lexical_deletes",
        "callable_sites", "protocol_sites", "mutation_sites",
        "dependency_name_sets",
    ):
        assert isinstance(getattr(summary, field), tuple)
        assert getattr(summary, field)
    with pytest.raises((AttributeError, TypeError)):
        summary.statements = ()


def test_r9_recursive_and_summary_paths_have_exact_execution_projection():
    source = (
        "def run(flag):\n"
        "    class Left:\n"
        "        def __add__(self, other):\n"
        "            return NotImplemented\n"
        "    class Right:\n"
        "        def __radd__(self, other):\n"
        "            open('reflected.txt')\n"
        "            return 1\n"
        "    callbacks = []\n"
        "    def repository_candidate():\n"
        "        import deeper\n"
        "    callbacks.append(repository_candidate)\n"
        "    if flag:\n"
        "        callbacks.extend([repository_candidate])\n"
        "    Left() + Right()\n"
        "    for callback in callbacks:\n"
        "        callback()\n"
    )
    recursive = _r9_summary_execution_probe(
        source,
        use_structural_summary=False,
        use_demand_driven_dataflow=False,
    )
    summarized = _r9_summary_execution_probe(
        source,
        use_structural_summary=True,
        use_demand_driven_dataflow=False,
    )
    for field in (
        "ordered_nodes", "states", "resolutions", "call_names", "incomplete"
    ):
        assert summarized[field] == recursive[field]
    assert {"open", "callback"} <= set(summarized["call_names"])
    metrics = summarized["metrics"]
    assert metrics["structural_summary_count"] <= 6
    assert metrics["summary_control_transfer_hits"] > 0
    assert metrics["maximum_delta_generations_per_cache_entry"] <= 1


def test_r9_summary_and_recursive_one_hop_preserve_candidates_and_reason(
    tmp_path, monkeypatch
):
    repo, commit = _synthetic_repo(
        tmp_path,
        {
            "main.py": "from helper import run\nrun(flag)\n",
            "helper.py": (
                "import sqlite3\n"
                "def run(flag):\n"
                "    def candidate():\n"
                "        sqlite3.connect('candidate.db')\n"
                "        import deeper\n"
                "    callbacks = [candidate]\n"
                "    if flag:\n"
                "        callbacks.append(candidate)\n"
                "    register(callbacks)\n"
            ),
            "deeper.py": "VALUE = 1\n",
        },
    )
    mod = _module()
    monkeypatch.setattr(mod, "_USE_DEFINITION_STRUCTURAL_SUMMARIES", False)
    recursive = _one_hop(repo, commit, "main.py")
    monkeypatch.setattr(mod, "_USE_DEFINITION_STRUCTURAL_SUMMARIES", True)
    summarized = _one_hop(repo, commit, "main.py")

    assert summarized == recursive
    assert summarized["state"] == "unknown"
    assert summarized["reason"] == "import_resolution_incomplete"
    assert any(
        finding["resolved_api"] == "sqlite3.connect"
        for finding in summarized["findings"]
    )


def test_r9_dependency_delta_is_owner_name_scoped_and_monotone():
    mod = _module()
    first_owner = object()
    second_owner = object()
    delta = mod._DefinitionRuntimeDelta()
    first = frozenset({(id(first_owner), "callback")})
    second = frozenset({(id(second_owner), "callback")})
    unrelated = frozenset({(id(first_owner), "other")})
    baseline = {
        "first": delta.signature(first),
        "second": delta.signature(second),
        "unrelated": delta.signature(unrelated),
    }

    delta.record_invocation_value(id(first_owner), "callback", ("first",))
    assert delta.signature(first) != baseline["first"]
    assert delta.signature(second) == baseline["second"]
    assert delta.signature(unrelated) == baseline["unrelated"]

    second_before = delta.signature(second, include_publication=True)
    delta.record_publication(
        id(first_owner), "callback", ("object", 1, "list")
    )
    assert delta.signature(first, include_publication=True)
    assert delta.signature(second, include_publication=True) == second_before
    assert delta.invocation_values[(id(first_owner), "callback")] == ("first",)
    assert len(delta.publication_facts) == 1


def test_r9_dependency_cache_releases_superseded_generations():
    mod = _module()
    cache = mod._DependencyScopedCache()
    assert cache.resolve("definition", (("name", 0),), lambda: "cold") == "cold"
    assert cache.resolve("definition", (("name", 0),), lambda: "bad") == "cold"
    assert cache.resolve("definition", (("name", 1),), lambda: "warm") == "warm"
    assert len(cache) == 1
    assert cache.maximum_generations_per_entry == 1
    assert cache.hits == 1
    assert cache.misses == 2


def test_r9_summary_cold_warm_reversed_order_and_nonlocal_loop_equality():
    def source(first: str, second: str) -> str:
        return (
            "def run(flag):\n"
            "    state = []\n"
            "    def alpha():\n"
            "        nonlocal state\n"
            "        state.append(open)\n"
            "    def beta():\n"
            "        nonlocal state\n"
            "        state.append(print)\n"
            f"    callbacks = [{first}, {second}]\n"
            "    while flag:\n"
            "        for callback in callbacks:\n"
            "            callback()\n"
            "        break\n"
            "    register(state)\n"
        )

    forward = _r9_summary_execution_probe(
        source("alpha", "beta"), use_structural_summary=True
    )
    warm = _r9_summary_execution_probe(
        source("alpha", "beta"), use_structural_summary=True
    )
    reverse = _r9_summary_execution_probe(
        source("beta", "alpha"), use_structural_summary=True
    )
    recursive = _r9_summary_execution_probe(
        source("alpha", "beta"), use_structural_summary=False
    )
    assert forward["ordered_nodes"] == warm["ordered_nodes"]
    assert forward["states"] == warm["states"] == recursive["states"]
    assert forward["resolutions"] == warm["resolutions"] == recursive[
        "resolutions"
    ]
    assert forward["call_names"] == warm["call_names"]
    assert set(forward["call_names"]) == set(reverse["call_names"])
    assert forward["incomplete"] is True
    assert reverse["incomplete"] is True


_R9_INTERNAL_EXECUTION_CACHES = (
    "reachable_entry_cache",
    "iterable_reachability_cache",
    "value_kind_cache",
)

_R9_EPOCH_EXECUTION_CACHES = (
    "name_raise_cache",
    "expression_raise_cache",
    "control_suite_states_at_use_cache",
    "statement_exit_cache",
    "suite_exit_cache",
    "reaching_records_cache",
    "conditional_records_leave_unbound_cache",
    "binding_state_records_at_use_cache",
    "value_kind_cache",
)

_R9_OBSERVED_EXECUTION_CACHES = tuple(dict.fromkeys((
    *_R9_INTERNAL_EXECUTION_CACHES,
    *_R9_EPOCH_EXECUTION_CACHES,
)))


def _r9_cache_probe_line(
    source_lines: list[str], first_line: int, marker: str, statement: str
) -> int:
    marker_index = next(
        index for index, line in enumerate(source_lines) if marker in line
    )
    statement_index = next(
        index
        for index in range(marker_index, len(source_lines))
        if source_lines[index].strip() == statement
    )
    return first_line + statement_index


def _r9_definition_cache_probe(
    source: str,
    *,
    disabled_cache: str | None = None,
    disabled_caches: tuple[str, ...] = (),
) -> dict[str, object]:
    """Exercise the retained recursive reference-oracle cache boundaries."""
    mod = _module()
    tree = ast.parse(source)
    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    classes = {
        node.name: node for node in tree.body if isinstance(node, ast.ClassDef)
    }
    definition = functions["run"]
    aliases = mod.collect_aliases(tree)
    source_lines, first_line = inspect.getsourcelines(
        mod._definition_execution_nodes
    )
    hit_lines = {
        _r9_cache_probe_line(
            source_lines,
            first_line,
            "reachable_entry_cache: dict[",
            "return cached",
        ): "reachable_entry_cache",
        _r9_cache_probe_line(
            source_lines,
            first_line,
            "iterable_reachability_cache: dict[",
            "return iterable_reachability_cache[cache_key]",
        ): "iterable_reachability_cache",
        _r9_cache_probe_line(
            source_lines,
            first_line,
            "value_kind_cache: dict[",
            "return cached_result",
        ): "value_kind_cache",
    }
    value_kind_query_line = _r9_cache_probe_line(
        source_lines,
        first_line,
        "def infer_value_kind(",
        "cache_key = (",
    )
    hits = {name: 0 for name in _R9_INTERNAL_EXECUTION_CACHES}
    maximum_sizes = {name: 0 for name in _R9_OBSERVED_EXECUTION_CACHES}
    maximum_epoch_generations = {
        name: 0 for name in _R9_EPOCH_EXECUTION_CACHES
    }
    reachable_events: set[tuple[int | None, int | None, str]] = set()
    iterable_sites: set[
        tuple[
            tuple[int | None, int | None, str],
            tuple[int | None, int | None, str],
        ]
    ] = set()
    publication_counts: set[int] = set()
    value_seen_contexts: dict[int, set[frozenset[tuple[str, int]]]] = {}
    generator_filename = mod._definition_execution_nodes.__code__.co_filename
    disabled = set(disabled_caches)
    if disabled_cache is not None:
        disabled.add(disabled_cache)
    root_definition_walk_calls = 0

    def node_site(node: ast.AST) -> tuple[int | None, int | None, str]:
        return (
            getattr(node, "lineno", None),
            getattr(node, "col_offset", None),
            type(node).__name__,
        )

    def trace(frame, event, _arg):
        if event != "line" or frame.f_code.co_filename != generator_filename:
            return trace
        for cache_name in _R9_OBSERVED_EXECUTION_CACHES:
            cache = frame.f_locals.get(cache_name)
            if not isinstance(cache, dict):
                continue
            maximum_sizes[cache_name] = max(
                maximum_sizes[cache_name], len(cache)
            )
            if cache_name in _R9_EPOCH_EXECUTION_CACHES:
                epoch_index = 3 if cache_name == "value_kind_cache" else -1
                generations = {
                    key[epoch_index]
                    for key in tuple(cache)
                    if isinstance(key, tuple) and len(key) > abs(epoch_index)
                }
                maximum_epoch_generations[cache_name] = max(
                    maximum_epoch_generations[cache_name], len(generations)
                )
            if cache_name == "reachable_entry_cache":
                reachable_events.update(
                    node_site(key[0]) for key in tuple(cache)
                )
            elif cache_name == "iterable_reachability_cache":
                iterable_sites.update(
                    (node_site(key[0]), node_site(key[1]))
                    for key in tuple(cache)
                )
            else:
                publication_counts.update(
                    key[4]
                    for key in tuple(cache)
                    if len(key) > 4 and isinstance(key[4], int)
                )
            if cache_name in disabled:
                cache.clear()
        cache_name = hit_lines.get(frame.f_lineno)
        if cache_name is not None:
            hits[cache_name] += 1
        if frame.f_lineno == value_kind_query_line:
            value = frame.f_locals.get("value")
            seen = frame.f_locals.get("seen")
            if isinstance(value, ast.AST) and isinstance(seen, frozenset):
                value_seen_contexts.setdefault(id(value), set()).add(seen)
        return trace

    previous_trace = sys.gettrace()
    original_walk = mod.ast.walk

    def counted_walk(node):
        nonlocal root_definition_walk_calls
        if node is definition:
            root_definition_walk_calls += 1
        return original_walk(node)

    mod.ast.walk = counted_walk
    sys.settrace(trace)
    try:
        nodes, node_states, call_resolutions, incomplete = (
            mod._definition_execution_nodes(
                definition,
                aliases,
                None,
                functions,
                classes,
                trusted_aliases=mod._ScopedAliasResolver(tree).module_aliases(),
                module_bound_names=mod._module_bound_names_before(
                    tree, definition
                ),
                use_demand_driven_dataflow=False,
                use_full_corpus_query_collapse=False,
            )
        )
    finally:
        sys.settrace(previous_trace)
        mod.ast.walk = original_walk

    node_by_id = {id(node): node for node in ast.walk(tree)}

    def normalized_node(node: ast.AST) -> tuple[str, str]:
        return type(node).__name__, ast.dump(node, include_attributes=True)

    assert set(node_states) <= set(node_by_id)
    assert set(call_resolutions) <= set(node_by_id)
    normalized = {
        "nodes": tuple(normalized_node(node) for node in nodes),
        "node_states": tuple(
            sorted(
                (normalized_node(node_by_id[node_id]), state)
                for node_id, state in node_states.items()
            )
        ),
        "call_resolutions": tuple(
            sorted(
                (normalized_node(node_by_id[node_id]), state)
                for node_id, state in call_resolutions.items()
            )
        ),
        "incomplete": incomplete,
    }
    call_names = {
        (mod._dotted_name(node.func, aliases) or "").replace("()", "")
        for node in nodes
        if isinstance(node, ast.Call)
    }
    return {
        "normalized": normalized,
        "hits": hits,
        "maximum_sizes": maximum_sizes,
        "maximum_epoch_generations": maximum_epoch_generations,
        "root_definition_walk_calls": root_definition_walk_calls,
        "reachable_events": reachable_events,
        "iterable_sites": iterable_sites,
        "publication_counts": publication_counts,
        "maximum_seen_contexts": max(
            (len(contexts) for contexts in value_seen_contexts.values()),
            default=0,
        ),
        "call_names": call_names,
    }


def _r9_assert_cache_hits_equal_misses(
    source: str, cache_names: tuple[str, ...] = _R9_INTERNAL_EXECUTION_CACHES
) -> dict[str, object]:
    warm = _r9_definition_cache_probe(source)
    for cache_name in cache_names:
        assert warm["hits"][cache_name] > 0
        cold = _r9_definition_cache_probe(
            source, disabled_cache=cache_name
        )
        assert cold["hits"][cache_name] == 0
        assert cold["normalized"] == warm["normalized"]
    return warm


def test_r9_internal_cache_hits_equal_forced_cold_misses():
    warm = _r9_assert_cache_hits_equal_misses(
        "import json\n"
        "def run(flag):\n"
        "    callbacks = []\n"
        "    def dangerous():\n"
        "        open('danger')\n"
        "    callbacks.append(dangerous)\n"
        "    if flag:\n"
        "        callbacks.extend([dangerous])\n"
        "    for callback in callbacks:\n"
        "        json.dumps(callback)\n"
        "    json.dumps(callbacks)\n"
    )
    assert all(
        warm["maximum_sizes"][name] > 0
        for name in _R9_INTERNAL_EXECUTION_CACHES
    )
    assert "open" in warm["call_names"]


def test_r9_cache_requery_after_invocation_source_and_site_growth():
    warm = _r9_assert_cache_hits_equal_misses(
        "import json\n"
        "def run(flag):\n"
        "    callbacks = []\n"
        "    def first():\n"
        "        open('first')\n"
        "    def second():\n"
        "        import sqlite3\n"
        "        sqlite3.connect('second.db')\n"
        "    callbacks.append(first)\n"
        "    json.dumps(callbacks)\n"
        "    callbacks.append(second)\n"
        "    json.dumps(callbacks)\n"
    )
    assert {"open", "sqlite3.connect"} <= warm["call_names"]
    assert len(warm["reachable_events"]) >= 6
    assert len(warm["iterable_sites"]) >= 8


def test_r9_internal_cache_results_ignore_reversed_execution_order():
    def source(first: str, second: str) -> str:
        return (
            "import json\n"
            "def run(flag):\n"
            "    callbacks = []\n"
            "    def alpha():\n"
            "        open('alpha')\n"
            "    def beta():\n"
            "        import sqlite3\n"
            "        sqlite3.connect('beta.db')\n"
            f"    callbacks.append({first})\n"
            f"    callbacks.append({second})\n"
            "    for callback in callbacks:\n"
            "        json.dumps(callback)\n"
        )

    forward = _r9_assert_cache_hits_equal_misses(source("alpha", "beta"))
    reverse = _r9_assert_cache_hits_equal_misses(source("beta", "alpha"))
    assert forward["call_names"] == reverse["call_names"]
    assert {"open", "sqlite3.connect"} <= forward["call_names"]


def test_r9_value_kind_cache_separates_publication_count_changes():
    warm = _r9_assert_cache_hits_equal_misses(
        "import json\n"
        "def run(flag):\n"
        "    callbacks = []\n"
        "    def dangerous():\n"
        "        open('danger')\n"
        "    json.dumps(callbacks)\n"
        "    callbacks.append(dangerous)\n"
        "    json.dumps(callbacks)\n",
        ("value_kind_cache",),
    )
    assert {0, 1} <= warm["publication_counts"]
    assert "open" in warm["call_names"]


def test_r9_value_kind_cache_separates_cycle_contexts():
    warm = _r9_assert_cache_hits_equal_misses(
        "import json\n"
        "def run(flag):\n"
        "    left = [right]\n"
        "    right = [left]\n"
        "    json.dumps(left)\n"
        "    json.dumps(right)\n"
        "    json.dumps([left, right])\n",
        ("value_kind_cache",),
    )
    assert warm["maximum_seen_contexts"] > 1


def _r9_shared_transitive_caches() -> dict[str, dict]:
    return {
        "resolution_cache": {},
        "blob_cache": {},
        "analysis_cache": {},
        "module_reachability_cache": {},
        "definition_execution_cache": {},
    }


def test_r9_shared_caches_isolate_identical_bytes_by_helper_and_owner(
    tmp_path, monkeypatch
):
    helper_source = (
        "import sqlite3\n"
        "class Dangerous:\n"
        "    def run(self):\n"
        "        sqlite3.connect('danger.db')\n"
        "class Safe:\n"
        "    def run(self):\n"
        "        return 1\n"
    )
    repo, commit = _synthetic_repo(
        tmp_path,
        {
            "a/main.py": (
                "from helper import Dangerous\nDangerous().run()\n"
            ),
            "a/helper.py": helper_source,
            "b/main.py": "from helper import Safe\nSafe().run()\n",
            "b/helper.py": helper_source,
        },
    )
    mod = _module()
    entries = mod.git_tree_entries(
        repo, commit, ["a/main.py", "a/helper.py", "b/main.py", "b/helper.py"]
    )

    def invoke(source_path: str, caches: dict[str, dict]):
        return mod.one_hop_transitive_evidence(
            source_path,
            mod.git_blob(repo, entries[source_path]["blob_id"]),
            repo,
            commit,
            **caches,
        )

    cold = {
        path: invoke(path, _r9_shared_transitive_caches())
        for path in ("a/main.py", "b/main.py")
    }
    assert any(
        finding["resolved_api"] == "sqlite3.connect"
        for finding in cold["a/main.py"]["findings"]
    )
    assert not cold["b/main.py"]["findings"]

    original = mod._definition_execution_nodes
    executed_definitions: list[str] = []

    def counted(*args, **kwargs):
        executed_definitions.append(args[0].name)
        return original(*args, **kwargs)

    monkeypatch.setattr(mod, "_definition_execution_nodes", counted)
    for order in (
        ("a/main.py", "b/main.py"),
        ("b/main.py", "a/main.py"),
    ):
        caches = _r9_shared_transitive_caches()
        for path in order:
            executed_definitions.clear()
            first = invoke(path, caches)
            assert first == cold[path]
            assert "run" in executed_definitions
            sizes = {name: len(cache) for name, cache in caches.items()}
            executed_definitions.clear()
            second = invoke(path, caches)
            assert second == first
            assert "run" not in executed_definitions
            assert {name: len(cache) for name, cache in caches.items()} == sizes
        module_keys = set(caches["module_reachability_cache"])
        assert any(key[0] == "a/helper.py" for key in module_keys)
        assert any(key[0] == "b/helper.py" for key in module_keys)
        owners = {
            key[2] for key in caches["definition_execution_cache"]
        }
        assert {"Dangerous", "Safe"} <= owners


def test_r9_internal_caches_isolate_incompatible_lexical_scopes():
    warm = _r9_assert_cache_hits_equal_misses(
        "import json\n"
        "def run(flag):\n"
        "    def outer():\n"
        "        callbacks = []\n"
        "        def callback():\n"
        "            open('danger')\n"
        "        callbacks.append(callback)\n"
        "        for item in callbacks:\n"
        "            json.dumps(item)\n"
        "    def other():\n"
        "        callbacks = []\n"
        "        def callback():\n"
        "            import sqlite3\n"
        "            sqlite3.connect('must-not-leak.db')\n"
        "        callbacks.append(callback)\n"
        "        len(callbacks)\n"
        "    outer()\n"
        "    other()\n"
    )
    assert "open" in warm["call_names"]
    assert "sqlite3.connect" not in warm["call_names"]


def test_r9_epoch_eviction_and_operator_registry_are_semantics_neutral():
    source = (
        "def run(flag):\n"
        "    class Base:\n"
        "        def __add__(self, other):\n"
        "            return NotImplemented\n"
        "    class Child(Base):\n"
        "        def __radd__(self, other):\n"
        "            open('danger')\n"
        "            return 1\n"
        "    def relay(value):\n"
        "        return value + Child()\n"
        "    first = Base()\n"
        "    second = Child()\n"
        "    relay(first)\n"
        "    relay(second)\n"
        "    if flag:\n"
        "        relay(first)\n"
    )
    warm = _r9_definition_cache_probe(source)
    repeated = _r9_definition_cache_probe(source)
    cold = _r9_definition_cache_probe(
        source, disabled_caches=_R9_EPOCH_EXECUTION_CACHES
    )

    assert warm["normalized"] == repeated["normalized"] == cold["normalized"]
    assert warm["call_names"] == repeated["call_names"] == cold["call_names"]
    assert "open" in warm["call_names"]
    assert all(
        generations <= 1
        for generations in warm["maximum_epoch_generations"].values()
    )
    assert sum(warm["maximum_sizes"].values()) < 10_000
    assert warm["root_definition_walk_calls"] <= 64
    assert repeated["root_definition_walk_calls"] == warm[
        "root_definition_walk_calls"
    ]


# ── R9 demand-driven CFG/SCC dataflow proofs ────────────────────────────────


def _r9_dataflow_fixture(source: str):
    mod = _module()
    tree = ast.parse(source)
    definition = next(
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    )
    graph = mod._definition_dataflow_graph(definition)
    by_line = {
        node.lineno: node
        for node in ast.walk(definition)
        if isinstance(node, ast.stmt)
        and node is not definition
    }
    return mod, definition, graph, by_line


def _r9_dataflow_query(
    mod,
    definition,
    *,
    entry,
    target,
    events,
    dependency_signature=(),
    slice_complete=True,
):
    return mod._DemandDrivenDataflowQuery(
        definition_identity=id(definition),
        query_kind="binding-state-at-use",
        owner_identity=id(definition),
        dependency_signature=tuple(dependency_signature),
        entry_identities=(id(entry),),
        target_identity=id(target),
        event_values=tuple((id(node), value) for node, value in events),
        initial_states=frozenset({False}),
        slice_complete=slice_complete,
    )


def test_r9_demand_dataflow_exact_ordered_nodes_states_and_sccs():
    mod, definition, graph, by_line = _r9_dataflow_fixture(
        "def run(flag, items):\n"
        "    state = False\n"
        "    if flag:\n"
        "        state = True\n"
        "    for item in items:\n"
        "        consume(state)\n"
    )
    engine = mod._DemandDrivenDataflowEngine(graph)
    query = _r9_dataflow_query(
        mod,
        definition,
        entry=by_line[2],
        target=by_line[6],
        events=((by_line[4], True),),
    )

    result = engine.resolve(query)

    line_by_identity = {
        id(block.node): block.node.lineno for block in graph.blocks
    }
    assert result.complete is True
    assert result.reason is None
    assert result.states == frozenset({False, True})
    assert tuple(
        line_by_identity[node_id]
        for node_id in result.ordered_node_identities
    ) == (2, 3, 4, 5, 6)
    assert any(
        {line_by_identity[node_id] for node_id in component}
        == {5, 6}
        for component in graph.scc_node_identities
    )


def test_r9_demand_dataflow_recursive_reference_exact_execution_equality():
    source = (
        "def run(flag, items):\n"
        "    callbacks = []\n"
        "    def dangerous():\n"
        "        import sqlite3\n"
        "        sqlite3.connect('danger.db')\n"
        "    if flag:\n"
        "        callbacks.append(dangerous)\n"
        "    for item in items:\n"
        "        callbacks.extend([dangerous])\n"
        "    for callback in callbacks:\n"
        "        callback()\n"
    )
    reference = _r9_summary_execution_probe(
        source,
        use_structural_summary=True,
        use_demand_driven_dataflow=False,
    )
    demand = _r9_summary_execution_probe(
        source,
        use_structural_summary=True,
        use_demand_driven_dataflow=True,
    )
    for field in (
        "ordered_nodes", "states", "resolutions", "call_names", "incomplete"
    ):
        assert demand[field] == reference[field]
    assert {"callback", "sqlite3.connect"} <= set(demand["call_names"])
    assert demand["metrics"]["dataflow_query_count"] > 0
    assert demand["metrics"]["dataflow_cfg_node_visits"] > 0
    assert (
        demand["metrics"]["mutable_iterable_query_cache_hits"]
        + demand["metrics"]["value_resolution_query_cache_hits"]
    ) > 0
    assert demand["metrics"]["mutable_iterable_query_cache_entries"] <= 2_048
    assert (
        demand["metrics"]["mutable_iterable_query_computations"]
        + demand["metrics"]["value_resolution_query_computations"]
    ) < (
        demand["metrics"]["mutable_iterable_query_count"]
        + demand["metrics"]["value_resolution_query_count"]
    )
    assert demand["metrics"][
        "mutable_iterable_query_maximum_generations"
    ] <= 1


def test_r9_demand_dataflow_one_hop_preserves_candidates_and_reasons(
    tmp_path, monkeypatch
):
    repo, commit = _synthetic_repo(
        tmp_path,
        {
            "main.py": "from helper import run\nrun(flag)\n",
            "helper.py": (
                "import sqlite3\n"
                "def run(flag):\n"
                "    callbacks = []\n"
                "    def candidate():\n"
                "        sqlite3.connect('candidate.db')\n"
                "        import deeper\n"
                "    if flag:\n"
                "        callbacks.append(candidate)\n"
                "    for callback in callbacks:\n"
                "        callback()\n"
            ),
            "deeper.py": "VALUE = 1\n",
        },
    )
    mod = _module()
    monkeypatch.setattr(mod, "_USE_DEMAND_DRIVEN_DATAFLOW", False)
    reference = _one_hop(repo, commit, "main.py")
    monkeypatch.setattr(mod, "_USE_DEMAND_DRIVEN_DATAFLOW", True)
    demand = _one_hop(repo, commit, "main.py")

    assert demand == reference
    assert demand["state"] == "unknown"
    assert demand["reason"] == "import_resolution_incomplete"
    assert any(
        finding["resolved_api"] == "sqlite3.connect"
        for finding in demand["findings"]
    )


def test_r9_demand_dataflow_preserves_legacy_transitive_local_effect_candidates(
    tmp_path,
):
    repo, commit = _synthetic_repo(
        tmp_path,
        {
            "main.py": "from helper import launch\nlaunch()\n",
            "helper.py": (
                "import sqlite3\n"
                "class Manager:\n"
                "    def _get_connection(self):\n"
                "        return sqlite3.connect('candidate.db')\n"
                "    def run(self):\n"
                "        conn = self._get_connection()\n"
                "        cursor = conn.cursor()\n"
                "        cursor.execute('select 1')\n"
                "def launch():\n"
                "    Manager().run()\n"
            ),
        },
    )

    result = _one_hop(repo, commit, "main.py")

    resolved_apis = {
        finding["resolved_api"] for finding in result["findings"]
    }
    assert {
        "sqlite3.connect",
        "self._get_connection().cursor",
        "self._get_connection().cursor().execute",
    } <= resolved_apis


def test_r9_demand_dataflow_cold_warm_and_reversed_order_equality():
    mod, definition, graph, by_line = _r9_dataflow_fixture(
        "def run(left, right):\n"
        "    state = False\n"
        "    if left:\n"
        "        state = True\n"
        "    if right:\n"
        "        state = False\n"
        "    consume(state)\n"
    )
    query = _r9_dataflow_query(
        mod,
        definition,
        entry=by_line[2],
        target=by_line[7],
        events=((by_line[4], True), (by_line[6], False)),
    )
    engine = mod._DemandDrivenDataflowEngine(graph)
    cold = engine.resolve(query)
    warm = engine.resolve(query)
    reversed_result = mod._DemandDrivenDataflowEngine(graph).resolve(
        query, reverse_predecessors=True
    )

    assert cold.states == warm.states == reversed_result.states
    assert cold.ordered_node_identities == warm.ordered_node_identities
    assert cold.ordered_node_identities == reversed_result.ordered_node_identities
    assert cold.cache_hit is False
    assert warm.cache_hit is True
    assert reversed_result.cache_hit is False


def test_r9_demand_dataflow_loop_scc_converges():
    mod, definition, graph, by_line = _r9_dataflow_fixture(
        "def run(items):\n"
        "    state = False\n"
        "    for item in items:\n"
        "        consume(state)\n"
        "        state = True\n"
    )
    query = _r9_dataflow_query(
        mod,
        definition,
        entry=by_line[2],
        target=by_line[4],
        events=((by_line[5], True),),
    )
    engine = mod._DemandDrivenDataflowEngine(graph)
    result = engine.resolve(query)

    assert result.states == frozenset({False, True})
    assert result.complete is True
    assert result.node_visits <= len(graph.blocks) * 4
    assert engine.maximum_node_visits <= len(graph.blocks) * 4


def test_r9_demand_dataflow_dependency_and_publication_invalidation_is_scoped():
    mod, definition, graph, by_line = _r9_dataflow_fixture(
        "def run():\n"
        "    state = False\n"
        "    state = True\n"
        "    consume(state)\n"
    )

    def query(signature):
        return _r9_dataflow_query(
            mod,
            definition,
            entry=by_line[2],
            target=by_line[4],
            events=((by_line[3], True),),
            dependency_signature=signature,
        )

    engine = mod._DemandDrivenDataflowEngine(graph)
    binding_v0 = (("binding", id(definition), "state", 0),)
    binding_v1 = (("binding", id(definition), "state", 1),)
    publication_v1 = (
        *binding_v1,
        ("publication", id(definition), "state", 1),
    )
    cold = engine.resolve(query(binding_v0))
    warm_after_unrelated_change = engine.resolve(query(binding_v0))
    binding_changed = engine.resolve(query(binding_v1))
    publication_changed = engine.resolve(query(publication_v1))

    assert cold.cache_hit is False
    assert warm_after_unrelated_change.cache_hit is True
    assert binding_changed.cache_hit is False
    assert publication_changed.cache_hit is False
    assert {
        cold.states,
        warm_after_unrelated_change.states,
        binding_changed.states,
        publication_changed.states,
    } == {frozenset({True})}
    assert engine.cache_entries == 1
    assert engine.maximum_generations_per_entry == 1


def test_r9_demand_dataflow_incomplete_slice_fails_closed():
    mod, definition, graph, by_line = _r9_dataflow_fixture(
        "def run():\n"
        "    state = False\n"
        "    state = True\n"
        "    consume(state)\n"
    )
    query = _r9_dataflow_query(
        mod,
        definition,
        entry=by_line[2],
        target=by_line[4],
        events=((by_line[3], True),),
        slice_complete=False,
    )
    result = mod._DemandDrivenDataflowEngine(graph).resolve(query)

    assert result.complete is False
    assert result.reason == "incomplete_dependency_slice"
    assert result.states == frozenset({False, True})
    assert result.node_visits == 0


def test_r9_demand_dataflow_cyclic_mutable_protocol_query_fails_closed():
    source = (
        "def run(history, models, min_num, max_num):\n"
        "    all_numbers = []\n"
        "    for nums in history:\n"
        "        all_numbers.extend(nums)\n"
        "    feature = {}\n"
        "    for num in range(min_num, max_num + 1):\n"
        "        recent = []\n"
        "        for nums in history:\n"
        "            recent.extend(nums)\n"
        "        feature[num] = recent.count(num)\n"
        "    probabilities = {}\n"
        "    for num in range(min_num, max_num + 1):\n"
        "        model_info = models[num]\n"
        "        submodels = model_info['models']\n"
        "        values = []\n"
        "        for name, model in submodels:\n"
        "            if hasattr(model, 'predict_proba'):\n"
        "                prob = model.predict_proba(feature)[0][1]\n"
        "            else:\n"
        "                prob = model.predict(feature)[0]\n"
        "            values.append(prob)\n"
        "        probabilities[num] = sum(values)\n"
        "    return probabilities\n"
    )

    first = _r9_summary_execution_probe(
        source,
        use_structural_summary=True,
        use_demand_driven_dataflow=True,
    )
    repeated = _r9_summary_execution_probe(
        source,
        use_structural_summary=True,
        use_demand_driven_dataflow=True,
    )

    for field in (
        "ordered_nodes", "states", "resolutions", "call_names", "incomplete"
    ):
        assert repeated[field] == first[field]
    assert first["incomplete"] is True
    assert {"model.predict", "model.predict_proba"} <= set(
        first["call_names"]
    )
    assert first["metrics"]["mutable_iterable_query_cache_entries"] <= 2_048


def test_r9_demand_dataflow_unrelated_dispatch_does_not_taint_one_hop(
    tmp_path,
):
    repo, commit = _synthetic_repo(
        tmp_path,
        {
            "main.py": (
                "import json\n"
                "def run(models):\n"
                "    values = []\n"
                "    for name, model in models:\n"
                "        values.append(model.predict({}))\n"
                "    return json.dumps(values)\n"
                "if __name__ == '__main__':\n"
                "    run(unresolved)\n"
            ),
        },
    )

    result = _one_hop(repo, commit, "main.py")

    assert result["state"] == "not_detected"
    assert result["findings"] == []


def test_r9_demand_dataflow_unsupported_import_definition_stays_fail_closed(
    tmp_path,
):
    repo, commit = _synthetic_repo(
        tmp_path,
        {
            "main.py": (
                "from helper import Worker\n"
                "def launch():\n"
                "    Worker()\n"
                "if __name__ == '__main__':\n"
                "    launch()\n"
            ),
            "helper.py": (
                "import sqlite3\n"
                "sqlite3.connect('module.db')\n"
                "class Worker:\n"
                "    def __init__(self):\n"
                "        sqlite3.connect('definition.db')\n"
                "from mystery import *\n"
            ),
        },
    )

    result = _one_hop(repo, commit, "main.py")

    assert result["state"] == "unknown"
    assert result["reason"] == "imported_scan_incomplete"
    sqlite_findings = [
        finding
        for finding in result["findings"]
        if finding["resolved_api"] == "sqlite3.connect"
    ]
    assert [(finding["line"], finding["column"]) for finding in sqlite_findings] == [
        (2, 0)
    ]


def test_r9_demand_dataflow_bounds_cache_visits_and_is_deterministic():
    source = "def run(flag):\n" + "".join(
        f"    value_{index} = {index}\n" for index in range(24)
    ) + "    consume(value_23)\n"
    mod, definition, graph, by_line = _r9_dataflow_fixture(source)
    query = _r9_dataflow_query(
        mod,
        definition,
        entry=by_line[2],
        target=by_line[26],
        events=((by_line[13], True),),
    )
    engine = mod._DemandDrivenDataflowEngine(graph, maximum_cache_entries=8)
    first = engine.resolve(query)
    repeated = [engine.resolve(query) for _ in range(12)]

    assert all(result.states == first.states for result in repeated)
    assert all(
        result.ordered_node_identities == first.ordered_node_identities
        for result in repeated
    )
    assert first.node_visits <= len(graph.blocks) * 2
    assert engine.cache_entries == 1
    assert engine.cache_entries <= engine.maximum_cache_entries
    assert engine.cache_hits == 12
    assert engine.cache_misses == 1


def test_r9_publication_prefilter_is_bounded_and_reference_equivalent():
    source = (
        "def run(holder):\n"
        "    values = []\n"
        "    def candidate():\n"
        "        import deeper\n"
        "    if holder:\n"
        "        holder.slot = values\n"
        + "".join(
            f"    noise_{index} = {index}\n" for index in range(96)
        )
        + "    values.append(candidate)\n"
        "    for callback in values:\n"
        "        callback()\n"
    )
    mod = _module()
    tree = ast.parse(source)
    definition = tree.body[0]
    resolver = mod._ScopedAliasResolver(definition)
    candidates = mod._mutation_publication_candidate_nodes(
        definition, resolver._owner_scope
    )
    assert len(tuple(ast.walk(definition))) > 300
    assert len(candidates) == 3
    assert all(
        isinstance(
            candidate,
            (
                ast.Return, ast.Yield, ast.YieldFrom,
                ast.Assign, ast.AnnAssign, ast.Call,
            ),
        )
        for candidate in candidates
    )
    reference = _r9_summary_execution_probe(
        source,
        use_structural_summary=True,
        use_demand_driven_dataflow=False,
    )
    demand = _r9_summary_execution_probe(
        source,
        use_structural_summary=True,
        use_demand_driven_dataflow=True,
    )
    repeated = _r9_summary_execution_probe(
        source,
        use_structural_summary=True,
        use_demand_driven_dataflow=True,
    )

    for field in (
        "ordered_nodes", "states", "resolutions", "call_names", "incomplete"
    ):
        assert demand[field] == repeated[field] == reference[field]
    metrics = demand["metrics"]
    assert metrics["mutation_publication_reachability_queries"] <= 8
    assert metrics["dataflow_query_count"] < 512
    assert metrics["dataflow_cache_entries"] < 512
    assert repeated["metrics"] == metrics


def test_r9_stable_dependency_cache_replays_only_unchanged_generations():
    mod = _module()
    cache = mod._DependencyScopedCache(maximum_variants=4)
    generation = [0]
    evaluations = []

    def signature():
        return (generation[0],)

    def unstable():
        evaluations.append("unstable")
        generation[0] += 1
        return "transition"

    assert cache.resolve_stable_variant(
        "query", signature, ("context",), unstable
    ) == "transition"
    assert len(cache) == 0
    assert cache.unstable_results == 1

    def stable():
        evaluations.append(f"stable-{generation[0]}")
        return f"generation-{generation[0]}"

    assert cache.resolve_stable_variant(
        "query", signature, ("context",), stable
    ) == "generation-1"
    assert cache.resolve_stable_variant(
        "query", signature, ("context",), stable
    ) == "generation-1"
    generation[0] += 1
    assert cache.resolve_stable_variant(
        "query", signature, ("context",), stable
    ) == "generation-2"

    assert evaluations == ["unstable", "stable-1", "stable-2"]
    assert cache.hits == 1
    assert cache.misses == 3
    assert len(cache) == 1
    assert cache.maximum_generations_per_entry == 1
    assert cache.maximum_variants_per_entry == 1


def test_r9_observed_requirement_cache_ignores_unrelated_guard_changes():
    mod = _module()
    cache = mod._DependencyScopedCache(maximum_variants=4)
    generation = [0]
    guards = set()
    evaluations = []

    def signature():
        return (generation[0],)

    def present(key):
        return key in guards

    def evaluate():
        evaluations.append("used" in guards)
        requirements = frozenset({("used", "used" in guards)})
        return requirements, evaluations[-1]

    assert cache.resolve_stable_requirements(
        "query", signature, present, evaluate
    ) == (frozenset({("used", False)}), False)
    guards.add("unrelated")
    assert cache.resolve_stable_requirements(
        "query", signature, present, evaluate
    ) == (frozenset({("used", False)}), False)
    guards.add("used")
    assert cache.resolve_stable_requirements(
        "query", signature, present, evaluate
    ) == (frozenset({("used", True)}), True)
    guards.remove("unrelated")
    assert cache.resolve_stable_requirements(
        "query", signature, present, evaluate
    ) == (frozenset({("used", True)}), True)

    assert evaluations == [False, True]
    assert cache.hits == 2
    assert cache.misses == 2
    assert len(cache) == 1
    assert cache.maximum_generations_per_entry == 1
    assert cache.maximum_variants_per_entry == 2


def test_r9_stable_raise_cache_reference_cold_warm_reversed_and_bounds():
    source = (
        "def run(flag, items, holder):\n"
        "    callbacks = []\n"
        "    def candidate():\n"
        "        import deeper\n"
        "    try:\n"
        "        for item in items:\n"
        "            if flag:\n"
        "                callbacks.append(candidate)\n"
        "            holder.slot = callbacks\n"
        "            consume(callbacks)\n"
        "    except (ValueError, TypeError):\n"
        "        callbacks.extend([candidate])\n"
        "    finally:\n"
        "        for callback in callbacks:\n"
        "            callback()\n"
    )
    reference = _r9_summary_execution_probe(
        source,
        use_structural_summary=True,
        use_demand_driven_dataflow=True,
        use_stable_dataflow_raise_cache=False,
    )
    cold = _r9_summary_execution_probe(
        source,
        use_structural_summary=True,
        use_demand_driven_dataflow=True,
        use_stable_dataflow_raise_cache=True,
    )
    warm = _r9_summary_execution_probe(
        source,
        use_structural_summary=True,
        use_demand_driven_dataflow=True,
        use_stable_dataflow_raise_cache=True,
    )
    reversed_result = _r9_summary_execution_probe(
        source,
        use_structural_summary=True,
        use_demand_driven_dataflow=True,
        use_stable_dataflow_raise_cache=True,
        reverse_dataflow_predecessors=True,
    )

    for field in (
        "ordered_nodes", "states", "resolutions", "call_names", "incomplete"
    ):
        assert cold[field] == warm[field] == reversed_result[field]
        assert cold[field] == reference[field]
    assert cold["incomplete"] is True
    assert {"callback", "callbacks.append", "consume"} <= set(
        cold["call_names"]
    )
    assert cold["metrics"] == warm["metrics"]

    metrics = cold["metrics"]
    assert metrics["dataflow_raise_type_evaluations"] > 0
    assert metrics["dataflow_raise_type_cache_hits"] > 0
    assert metrics["dataflow_raise_type_cache_entries"] <= 4_096
    assert metrics["dataflow_raise_type_maximum_generations"] <= 1
    assert metrics["dataflow_raise_type_maximum_variants"] <= 512
    assert metrics["dataflow_query_count"] < 5_000
    assert metrics["dataflow_cfg_node_visits"] < 100_000


def test_r9_stable_raise_cache_preserves_exact_candidates_order_and_reason(
    tmp_path, monkeypatch
):
    repo, commit = _synthetic_repo(
        tmp_path,
        {
            "main.py": "from helper import run\nrun(flag, items)\n",
            "helper.py": (
                "import sqlite3\n"
                "def run(flag, items):\n"
                "    callbacks = []\n"
                "    def first():\n"
                "        sqlite3.connect('first.db')\n"
                "    def second():\n"
                "        sqlite3.connect('second.db')\n"
                "        import deeper\n"
                "    try:\n"
                "        if flag:\n"
                "            callbacks.append(first)\n"
                "        for item in items:\n"
                "            callbacks.append(second)\n"
                "    except Exception:\n"
                "        callbacks.extend([first, second])\n"
                "    for callback in callbacks:\n"
                "        callback()\n"
            ),
            "deeper.py": "VALUE = 1\n",
        },
    )
    mod = _module()
    monkeypatch.setattr(mod, "_USE_STABLE_DATAFLOW_RAISE_CACHE", False)
    reference = _one_hop(repo, commit, "main.py")
    monkeypatch.setattr(mod, "_USE_STABLE_DATAFLOW_RAISE_CACHE", True)
    optimized = _one_hop(repo, commit, "main.py")
    repeated = _one_hop(repo, commit, "main.py")

    assert optimized == repeated == reference
    assert optimized["state"] == "unknown"
    assert optimized["reason"] == "import_resolution_incomplete"
    assert [
        (finding["line"], finding["resolved_api"])
        for finding in optimized["findings"]
    ] == [
        (5, "sqlite3.connect"),
        (7, "sqlite3.connect"),
    ]


# ---------------------------------------------------------------------------
# R9 shared protocol-dispatch semantics
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("flow_source", "expected_dangerous"),
    [
        (
            "    class Left:\n"
            "        def __add__(self, other):\n"
            "            return 1\n"
            "    class Right:\n"
            "        def __radd__(self, other):\n"
            "            dangerous()\n"
            "            return 2\n"
            "    Left() + Right()\n",
            False,
        ),
        (
            "    class Left:\n"
            "        def __add__(self, other):\n"
            "            return NotImplemented\n"
            "    class Right:\n"
            "        def __radd__(self, other):\n"
            "            dangerous()\n"
            "            return 2\n"
            "    Left() + Right()\n",
            True,
        ),
        (
            "    class Value:\n"
            "        def __add__(self, other):\n"
            "            return NotImplemented\n"
            "        def __radd__(self, other):\n"
            "            dangerous()\n"
            "            return 2\n"
            "    try:\n"
            "        Value() + Value()\n"
            "    except TypeError:\n"
            "        pass\n",
            False,
        ),
        (
            "    class Left:\n"
            "        def __add__(self, other):\n"
            "            dangerous()\n"
            "            return 1\n"
            "    class Right(Left):\n"
            "        def __radd__(self, other):\n"
            "            return 2\n"
            "    Left() + Right()\n",
            False,
        ),
    ],
    ids=[
        "preferred-stops-reflected",
        "notimplemented-enables-reflected",
        "same-type-skips-reflected",
        "strict-subclass-reflected-priority",
    ],
)
def test_fanin_operator_dispatch_orders_preferred_and_reflected(
    tmp_path, flow_source, expected_dangerous
):
    result = _r6_callable_flow_result(tmp_path, flow_source)
    if expected_dangerous:
        _assert_r6_dangerous_reached(result)
    else:
        _r9_fanin_assert_no_dangerous(result)


@pytest.mark.parametrize(
    ("flow_source", "expected_dangerous"),
    [
        (
            "    class Left:\n"
            "        def __iadd__(self, other):\n"
            "            return self\n"
            "        def __add__(self, other):\n"
            "            dangerous()\n"
            "            return self\n"
            "    class Right:\n"
            "        def __radd__(self, other):\n"
            "            dangerous()\n"
            "            return 2\n"
            "    value = Left()\n"
            "    value += Right()\n",
            False,
        ),
        (
            "    class Left:\n"
            "        def __iadd__(self, other):\n"
            "            return NotImplemented\n"
            "        def __add__(self, other):\n"
            "            dangerous()\n"
            "            return self\n"
            "    value = Left()\n"
            "    value += 1\n",
            True,
        ),
        (
            "    class Left:\n"
            "        def __iadd__(self, other):\n"
            "            return NotImplemented\n"
            "        def __add__(self, other):\n"
            "            return NotImplemented\n"
            "    class Right:\n"
            "        def __radd__(self, other):\n"
            "            dangerous()\n"
            "            return 2\n"
            "    value = Left()\n"
            "    value += Right()\n",
            True,
        ),
    ],
    ids=["iadd-stops", "iadd-to-add", "iadd-to-add-to-radd"],
)
def test_fanin_augassign_notimplemented_fallback_chain(
    tmp_path, flow_source, expected_dangerous
):
    result = _r6_callable_flow_result(tmp_path, flow_source)
    if expected_dangerous:
        _assert_r6_dangerous_reached(result)
    else:
        _r9_fanin_assert_no_dangerous(result)


@pytest.mark.parametrize("operation", ["binary", "augassign"])
@pytest.mark.parametrize("raises", [False, True], ids=["safe", "raises"])
def test_fanin_operator_exception_transfer_is_precise(
    tmp_path, operation, raises
):
    method = "__add__" if operation == "binary" else "__iadd__"
    action = "raise KeyError" if raises else (
        "return 1" if operation == "binary" else "return self"
    )
    statement = "Left() + 1" if operation == "binary" else "value += 1"
    setup = "    value = Left()\n" if operation == "augassign" else ""
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    class Left:\n"
            f"        def {method}(self, other):\n"
            f"            {action}\n"
            f"{setup}"
            "    try:\n"
            f"        {statement}\n"
            "    except KeyError:\n"
            "        dangerous()\n"
        ),
    )
    if raises:
        _assert_r6_dangerous_reached(result)
    else:
        _r9_fanin_assert_no_dangerous(result)


@pytest.mark.parametrize(
    ("asynchronous", "exception_name", "expected_dangerous"),
    [
        (False, "StopIteration", False),
        (False, "KeyError", True),
        (True, "StopAsyncIteration", False),
        (True, "KeyError", True),
    ],
    ids=["sync-stop", "sync-error", "async-stop", "async-error"],
)
def test_fanin_separate_iterator_exception_transfer_consumes_stop_signal(
    tmp_path, asynchronous, exception_name, expected_dangerous
):
    if asynchronous:
        flow_source = (
            "    import asyncio\n"
            "    class Iterator:\n"
            "        async def __anext__(self):\n"
            f"            raise {exception_name}\n"
            "    class Iterable:\n"
            "        def __aiter__(self):\n"
            "            return Iterator()\n"
            "    async def consume():\n"
            "        try:\n"
            "            async for item in Iterable():\n"
            "                pass\n"
            "        except KeyError:\n"
            "            dangerous()\n"
            "    asyncio.run(consume())\n"
        )
    else:
        flow_source = (
            "    class Iterator:\n"
            "        def __next__(self):\n"
            f"            raise {exception_name}\n"
            "    class Iterable:\n"
            "        def __iter__(self):\n"
            "            return Iterator()\n"
            "    try:\n"
            "        for item in Iterable():\n"
            "            pass\n"
            "    except KeyError:\n"
            "        dangerous()\n"
        )
    result = _r6_callable_flow_result(tmp_path, flow_source)
    if expected_dangerous:
        _assert_r6_dangerous_reached(result)
    else:
        _r9_fanin_assert_no_dangerous(result)


def test_fanin_separate_async_iterator_projects_consumed_callback(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import asyncio\n"
            "    class Iterator:\n"
            "        async def __anext__(self):\n"
            "            return dangerous\n"
            "    class Iterable:\n"
            "        def __aiter__(self):\n"
            "            return Iterator()\n"
            "    async def consume():\n"
            "        async for callback in Iterable():\n"
            "            callback()\n"
            "    asyncio.run(consume())\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


@pytest.mark.parametrize(
    "projection_source",
    [
        "    item = not dangerous\n",
        "    item = dangerous is safe\n",
        (
            "    class Container:\n"
            "        def __contains__(self, item):\n"
            "            return False\n"
            "    item = dangerous in Container()\n"
        ),
        (
            "    class Container:\n"
            "        def __contains__(self, item):\n"
            "            return dangerous\n"
            "    item = 1 in Container()\n"
        ),
    ],
    ids=["not", "identity", "membership-operand", "membership-result"],
)
def test_fanin_boolean_projection_does_not_publish_callable(
    tmp_path, projection_source
):
    result = _r6_callable_flow_result(
        tmp_path, projection_source + "    register(item)\n"
    )
    _r9_fanin_assert_no_dangerous(result)


def test_fanin_builtin_iter_does_not_execute_next(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    class Iterator:\n"
            "        def __next__(self):\n"
            "            dangerous()\n"
            "            raise StopIteration\n"
            "    class Iterable:\n"
            "        def __iter__(self):\n"
            "            return Iterator()\n"
            "    iter(Iterable())\n"
        ),
    )
    _r9_fanin_assert_no_dangerous(result)


def test_fanin_sort_uses_lt_dispatch_not_unrelated_order_methods(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    class Value:\n"
            "        def __lt__(self, other):\n"
            "            return True\n"
            "        def __le__(self, other):\n"
            "            dangerous()\n"
            "            return True\n"
            "    sorted([Value(), Value()])\n"
        ),
    )
    _r9_fanin_assert_no_dangerous(result)


def test_fanin_notimplemented_fallback_projects_concrete_value(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    class Left:\n"
            "        def __add__(self, other):\n"
            "            return NotImplemented\n"
            "    class Right:\n"
            "        def __radd__(self, other):\n"
            "            return 2\n"
            "    item = Left() + Right()\n"
            "    register(item)\n"
        ),
    )
    _r9_fanin_assert_no_dangerous(result)


# R9 Group 7: exact API/receiver provenance and supported signatures.


def test_fanin_json_supported_decoder_signature_is_precise(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import json\n"
            "    decoded = json.loads('[]', strict=False)\n"
            "    register(decoded)\n"
        ),
    )
    _assert_r9_proven_non_callable(result)


@pytest.mark.parametrize(
    "call_source",
    [
        "json.loads('[]', default=dangerous)",
        "json.dumps({}, object_hook=dangerous)",
    ],
    ids=["decoder-rejects-encoder-option", "encoder-rejects-decoder-option"],
)
def test_fanin_json_unsupported_signature_does_not_execute_callback(
    tmp_path, call_source
):
    result = _r6_callable_flow_result(
        tmp_path, f"    import json\n    {call_source}\n"
    )
    _assert_r7_unknown_without_dangerous_finding(result)
    assert result["findings"] == []


@pytest.mark.parametrize(
    "json_source",
    [
        (
            "    class Encoder(json.JSONEncoder):\n"
            "        def default(self, value):\n"
            "            dangerous()\n"
            "            return None\n"
            "    json.dumps(object(), cls=Encoder)\n"
        ),
        (
            "    class Decoder(json.JSONDecoder):\n"
            "        def decode(self, value):\n"
            "            dangerous()\n"
            "            return {}\n"
            "    json.loads('{}', cls=Decoder)\n"
        ),
        (
            "    class Writer:\n"
            "        def write(self, value):\n"
            "            dangerous()\n"
            "    json.dump({}, Writer())\n"
        ),
    ],
    ids=["encoder-default", "decoder-decode", "writer-write"],
)
def test_fanin_json_custom_protocols_are_executed(tmp_path, json_source):
    result = _r6_callable_flow_result(
        tmp_path, "    import json\n" + json_source
    )
    _assert_r6_dangerous_reached(result)


def test_fanin_sqlite_receiver_customization_is_isolated(tmp_path):
    result = _r9_fanin_api_flow_result(
        tmp_path,
        (
            "    custom = sqlite3.connect(':memory:')\n"
            "    custom.text_factory = bytes\n"
            "    plain = sqlite3.connect(':memory:')\n"
            "    row = plain.execute('select 1').fetchone()\n"
            "    json.dumps([row])\n"
        ),
    )
    assert not _r9_fanin_has_finding(result, "requests.get")


@pytest.mark.parametrize(
    "array_function_body",
    [
        "            dangerous()\n            return 0\n",
        "            return dangerous\n",
    ],
    ids=["execution", "return-projection"],
)
def test_fanin_numpy_array_function_execution_and_projection(
    tmp_path, array_function_body
):
    suffix = (
        "    np.sum(Payload())\n"
        if "dangerous()" in array_function_body
        else "    register(np.sum(Payload()))\n"
    )
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import numpy as np\n"
            "    class Payload:\n"
            "        def __array_function__(self, func, types, args, kwargs):\n"
            f"{array_function_body}"
            f"{suffix}"
        ),
    )
    _assert_r6_dangerous_reached(result)


@pytest.mark.parametrize(
    "counts_source",
    [
        (
            "    class Counts:\n"
            "        def __iter__(self):\n"
            "            dangerous()\n"
            "            return iter([1])\n"
            "    random.sample(['x'], 1, counts=Counts())\n"
        ),
        (
            "    class Count:\n"
            "        def __index__(self):\n"
            "            return 1\n"
            "        def __radd__(self, other):\n"
            "            dangerous()\n"
            "            return 2\n"
            "    random.sample(['a', 'b'], 1, counts=[1, Count()])\n"
        ),
    ],
    ids=["counts-iter", "count-radd"],
)
def test_fanin_random_sample_counts_protocols_are_executed(
    tmp_path, counts_source
):
    result = _r6_callable_flow_result(
        tmp_path, "    import random\n" + counts_source
    )
    _assert_r6_dangerous_reached(result)


@pytest.mark.parametrize(
    "requests_source",
    [
        (
            "    class Body:\n"
            "        def __iter__(self):\n"
            "            dangerous()\n"
            "            return iter([])\n"
            "    requests.post('https://example.invalid', data=Body())\n"
        ),
        (
            "    class Body:\n"
            "        def __iter__(self):\n"
            "            dangerous()\n"
            "            return iter([])\n"
            "    session = requests.Session()\n"
            "    session.post('https://example.invalid', data=Body())\n"
        ),
        (
            "    class Upload:\n"
            "        def read(self):\n"
            "            dangerous()\n"
            "            return b'payload'\n"
            "    requests.post(\n"
            "        'https://example.invalid', files={'file': Upload()}\n"
            "    )\n"
        ),
        (
            "    class Upload:\n"
            "        def read(self):\n"
            "            dangerous()\n"
            "            return b'payload'\n"
            "    session = requests.Session()\n"
            "    session.post(\n"
            "        'https://example.invalid', files={'file': Upload()}\n"
            "    )\n"
        ),
    ],
    ids=["module-body", "session-body", "module-files", "session-files"],
)
def test_fanin_requests_body_and_file_protocols_are_executed(
    tmp_path, requests_source
):
    result = _r6_callable_flow_result(
        tmp_path, "    import requests\n" + requests_source
    )
    _assert_r6_dangerous_reached(result)


def test_fanin_requests_session_subclass_send_is_executed(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import requests\n"
            "    class LocalSession(requests.Session):\n"
            "        def send(self, request, **kwargs):\n"
            "            dangerous()\n"
            "            return requests.Response()\n"
            "    LocalSession().get('https://example.invalid')\n"
        ),
    )
    _assert_r6_dangerous_reached(result)


@pytest.mark.parametrize(
    "csv_source",
    [
        (
            "    class Sink:\n"
            "        def write(self, value):\n"
            "            dangerous()\n"
            "    writer = csv.writer(Sink())\n"
            "    writer.writerow([1])\n"
        ),
        (
            "    class Sink:\n"
            "        def write(self, value):\n"
            "            return None\n"
            "    class Row:\n"
            "        def __iter__(self):\n"
            "            dangerous()\n"
            "            return iter([1])\n"
            "    csv.writer(Sink()).writerow(Row())\n"
        ),
        (
            "    class Sink:\n"
            "        def write(self, value):\n"
            "            return None\n"
            "    class Field:\n"
            "        def __str__(self):\n"
            "            dangerous()\n"
            "            return 'value'\n"
            "    csv.writer(Sink()).writerow([Field()])\n"
        ),
        (
            "    class Dialect(csv.excel):\n"
            "        def __getattribute__(self, name):\n"
            "            dangerous()\n"
            "            return super().__getattribute__(name)\n"
            "    list(csv.reader(['value'], dialect=Dialect()))\n"
        ),
    ],
    ids=["named-writer-sink", "row-iter", "field-str", "dialect-access"],
)
def test_fanin_csv_writer_and_dialect_protocols_are_executed(
    tmp_path, csv_source
):
    result = _r6_callable_flow_result(
        tmp_path, "    import csv\n" + csv_source
    )
    _assert_r6_dangerous_reached(result)


@pytest.mark.parametrize(
    "numpy_source",
    [
        (
            "    class Payload:\n"
            "        def __array_function__(self, func, types, args, kwargs):\n"
            "            return dangerous\n"
            "    register(np.sum(a=Payload()))\n"
        ),
        (
            "    class Payload:\n"
            "        def __array_ufunc__(self, func, method, *args, **kwargs):\n"
            "            return dangerous\n"
            "    register(np.add(Payload(), 1))\n"
        ),
        (
            "    class Element:\n"
            "        def __add__(self, other):\n"
            "            dangerous()\n"
            "            return 1\n"
            "    values = np.array([Element()], dtype=object)\n"
            "    np.add(values, values)\n"
        ),
    ],
    ids=["keyword-array-function", "ufunc-result", "object-element-add"],
)
def test_fanin_numpy_override_and_object_ufunc_paths(
    tmp_path, numpy_source
):
    result = _r6_callable_flow_result(
        tmp_path, "    import numpy as np\n" + numpy_source
    )
    _assert_r6_dangerous_reached(result)


@pytest.mark.parametrize(
    "numpy_source",
    [
        (
            "    class Payload:\n"
            "        def __array__(self):\n"
            "            dangerous()\n"
            "            return np.array([1])\n"
            "        def __array_ufunc__(self, *args, **kwargs):\n"
            "            dangerous()\n"
            "            return 0\n"
            "        def __array_function__(self, func, types, args, kwargs):\n"
            "            return 0\n"
            "    np.sum(Payload())\n"
        ),
        (
            "    class Payload:\n"
            "        def __array_function__(self, *args, **kwargs):\n"
            "            dangerous()\n"
            "            return 0\n"
            "        def __array_ufunc__(self, *args, **kwargs):\n"
            "            return 0\n"
            "    np.add(Payload(), 1)\n"
        ),
    ],
    ids=["array-function-only", "array-ufunc-only"],
)
def test_fanin_numpy_dispatch_does_not_execute_unrelated_protocols(
    tmp_path, numpy_source
):
    result = _r6_callable_flow_result(
        tmp_path, "    import numpy as np\n" + numpy_source
    )
    _r9_fanin_assert_no_dangerous(result)


@pytest.mark.parametrize(
    "requests_source",
    [
        (
            "    class Field:\n"
            "        def __str__(self):\n"
            "            dangerous()\n"
            "            return 'value'\n"
            "    requests.post(\n"
            "        'https://example.invalid', data={'field': Field()}\n"
            "    )\n"
        ),
        (
            "    class Upload:\n"
            "        def read(self):\n"
            "            dangerous()\n"
            "            return b'payload'\n"
            "    requests.post(\n"
            "        'https://example.invalid',\n"
            "        files={'field': ('payload.txt', Upload())},\n"
            "    )\n"
        ),
        (
            "    class LocalSession(requests.Session):\n"
            "        def request(self, *args, **kwargs):\n"
            "            dangerous()\n"
            "            return requests.Response()\n"
            "    LocalSession().get('https://example.invalid')\n"
        ),
        (
            "    class LocalResponse:\n"
            "        def json(self):\n"
            "            return dangerous\n"
            "    def hook(response, *args, **kwargs):\n"
            "        return LocalResponse()\n"
            "    session = requests.Session()\n"
            "    session.hooks = {'response': [hook]}\n"
            "    response = session.get('https://example.invalid')\n"
            "    register(response.json())\n"
        ),
    ],
    ids=["form-value", "nested-file", "request-override", "session-hook-json"],
)
def test_fanin_requests_structured_and_session_provenance(
    tmp_path, requests_source
):
    result = _r6_callable_flow_result(
        tmp_path, "    import requests\n" + requests_source
    )
    _assert_r6_dangerous_reached(result)


@pytest.mark.parametrize(
    "json_source",
    [
        (
            "    import json\n"
            "    class Decoder(json.JSONDecoder):\n"
            "        def decode(self, value):\n"
            "            return dangerous\n"
            "    register(json.loads('{}', cls=Decoder))\n"
        ),
        (
            "    import json\n"
            "    import requests\n"
            "    class Decoder(json.JSONDecoder):\n"
            "        def decode(self, value):\n"
            "            return dangerous\n"
            "    response = requests.Response()\n"
            "    response._content = b'{}'\n"
            "    register(response.json(cls=Decoder))\n"
        ),
    ],
    ids=["json-loads", "requests-response-json"],
)
def test_fanin_json_decoder_class_result_is_projected(
    tmp_path, json_source
):
    _assert_r6_dangerous_reached(
        _r6_callable_flow_result(tmp_path, json_source)
    )


@pytest.mark.parametrize(
    "json_source",
    [
        (
            "    class Reader:\n"
            "        def read(self):\n"
            "            dangerous()\n"
            "            return '{}'\n"
            "    json.load(fp=Reader())\n"
        ),
        (
            "    class Writer:\n"
            "        def write(self, value):\n"
            "            dangerous()\n"
            "    json.dump(obj={}, fp=Writer())\n"
        ),
    ],
    ids=["keyword-reader", "keyword-writer"],
)
def test_fanin_json_keyword_source_and_sink_protocols(
    tmp_path, json_source
):
    result = _r6_callable_flow_result(
        tmp_path, "    import json\n" + json_source
    )
    _assert_r6_dangerous_reached(result)


@pytest.mark.parametrize(
    "csv_source",
    [
        (
            "    class Sink:\n"
            "        def write(self, value):\n"
            "            return None\n"
            "    class Field:\n"
            "        def __str__(self):\n"
            "            dangerous()\n"
            "            return 'value'\n"
            "    csv.DictWriter(Sink(), ['field']).writerow(\n"
            "        {'field': Field()}\n"
            "    )\n"
        ),
        (
            "    class Sink:\n"
            "        def write(self, value):\n"
            "            return None\n"
            "    class Fields:\n"
            "        def __iter__(self):\n"
            "            dangerous()\n"
            "            return iter(['field'])\n"
            "    csv.DictWriter(Sink(), Fields()).writerow(\n"
            "        {'field': 'value'}\n"
            "    )\n"
        ),
    ],
    ids=["mapping-value", "fieldnames-iteration"],
)
def test_fanin_csv_dict_writer_protocols_are_executed(
    tmp_path, csv_source
):
    result = _r6_callable_flow_result(
        tmp_path, "    import csv\n" + csv_source
    )
    _assert_r6_dangerous_reached(result)


def test_fanin_csv_reader_construction_does_not_advance_input(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    import csv\n"
            "    class Lines:\n"
            "        def __iter__(self):\n"
            "            return self\n"
            "        def __next__(self):\n"
            "            dangerous()\n"
            "            raise StopIteration\n"
            "    csv.reader(Lines())\n"
        ),
    )
    _r9_fanin_assert_no_dangerous(result)


@pytest.mark.parametrize(
    "random_source",
    [
        (
            "    class Count(int):\n"
            "        def __add__(self, other):\n"
            "            dangerous()\n"
            "            return int(self) + int(other)\n"
            "    random.sample(\n"
            "        ['a', 'b'], 1, counts=[Count(1), Count(1)]\n"
            "    )\n"
        ),
        (
            "    class Weight(float):\n"
            "        def __add__(self, other):\n"
            "            dangerous()\n"
            "            return float(self) + float(other)\n"
            "    random.choices(\n"
            "        ['a', 'b'], weights=[Weight(1), Weight(1)], k=1\n"
            "    )\n"
        ),
    ],
    ids=["sample-count", "choices-weight"],
)
def test_fanin_random_accumulation_executes_left_add(
    tmp_path, random_source
):
    result = _r6_callable_flow_result(
        tmp_path, "    import random\n" + random_source
    )
    _assert_r6_dangerous_reached(result)


def test_fanin_custom_json_receiver_does_not_invent_hook_execution(tmp_path):
    result = _r6_callable_flow_result(
        tmp_path,
        (
            "    class LocalResponse:\n"
            "        def json(self, object_hook=None):\n"
            "            return {}\n"
            "    LocalResponse().json(object_hook=dangerous)\n"
        ),
    )
    _r9_fanin_assert_no_dangerous(result)


# ── R9 full-corpus semantic-query collapse proofs ──────────────────────────


def test_r9_full_corpus_query_collapse_coalesces_equivalent_queries():
    mod = _module()
    cache = mod._DependencyScopedCache(maximum_variants=4)
    generation = [0]
    guards: set[str] = set()
    computations: list[bool] = []

    def signature():
        return (("binding", 1, "value", generation[0]),)

    def evaluate():
        observed = "relevant" in guards
        computations.append(observed)
        return frozenset({("relevant", observed)}), observed

    first = cache.resolve_stable_requirements(
        "semantic-query", signature, guards.__contains__, evaluate
    )
    guards.add("unrelated")
    repeated = cache.resolve_stable_requirements(
        "semantic-query", signature, guards.__contains__, evaluate
    )

    assert first == repeated == (frozenset({("relevant", False)}), False)
    assert computations == [False]
    assert cache.hits == 1
    assert cache.misses == 1


def test_r9_full_corpus_deferred_query_store_is_exact_and_stable():
    mod = _module()
    cache = mod._DependencyScopedCache(maximum_variants=4)
    guards: set[str] = set()
    dependency = (("binding", 1, "value", 0),)
    requirements = frozenset({("relevant", False)})

    found, _requirements, _value = cache.lookup_stable_requirements(
        "blocked-edges", dependency, guards.__contains__
    )
    assert found is False
    cache.store_stable_requirements(
        "blocked-edges",
        dependency,
        dependency,
        requirements,
        ((1, 2),),
        stable=True,
        cacheable=True,
    )

    guards.add("unrelated")
    assert cache.lookup_stable_requirements(
        "blocked-edges", dependency, guards.__contains__
    ) == (True, requirements, ((1, 2),))

    guards.add("relevant")
    found, _requirements, _value = cache.lookup_stable_requirements(
        "blocked-edges", dependency, guards.__contains__
    )
    assert found is False
    cache.store_stable_requirements(
        "unstable",
        dependency,
        (("binding", 1, "value", 1),),
        frozenset(),
        ((2, 3),),
        stable=True,
        cacheable=True,
    )
    assert len(cache) == 1
    assert cache.unstable_results == 1


def test_r9_full_corpus_structural_facts_share_only_exact_blob_owner():
    mod = _module()
    first_tree = ast.parse("def run(value):\n    return value\n")
    second_tree = ast.parse("def run(value):\n    return value\n")
    first = first_tree.body[0]
    second = second_tree.body[0]
    scope = mod._FullCorpusQueryCollapseScope(
        maximum_structural_entries=4
    )

    first_cold = scope.structural_summary_for(
        ("a.py", "blob-a"), first
    )
    first_warm = scope.structural_summary_for(
        ("a.py", "blob-a"), first
    )
    different_owner = scope.structural_summary_for(
        ("a.py", "blob-a"), second
    )
    different_module = scope.structural_summary_for(
        ("b.py", "blob-a"), first
    )

    assert first_cold is first_warm
    assert different_owner is not first_cold
    assert different_module is not first_cold
    assert scope.structural_summary_hits == 1
    assert scope.structural_summary_misses == 3
    assert scope.structural_entry_count == 3


def test_r9_full_corpus_query_collapse_dependency_invalidation_is_scoped():
    mod = _module()
    delta = mod._DefinitionRuntimeDelta()
    cache = mod._DependencyScopedCache(maximum_variants=4)
    owner = object()
    dependencies = frozenset({(id(owner), "dependent")})
    computations: list[tuple[tuple[str, int, str, int], ...]] = []

    def signature():
        return delta.signature(dependencies, include_publication=True)

    def evaluate():
        computations.append(signature())
        return frozenset(), len(computations)

    assert cache.resolve_stable_requirements(
        "query", signature, lambda _key: False, evaluate
    )[1] == 1
    delta.record_invocation_value(id(owner), "unrelated", ("noise",))
    assert cache.resolve_stable_requirements(
        "query", signature, lambda _key: False, evaluate
    )[1] == 1
    delta.record_invocation_value(id(owner), "dependent", ("changed",))
    assert cache.resolve_stable_requirements(
        "query", signature, lambda _key: False, evaluate
    )[1] == 2
    delta.record_publication(id(owner), "dependent", ("object", 1, "list"))
    assert cache.resolve_stable_requirements(
        "query", signature, lambda _key: False, evaluate
    )[1] == 3

    assert len(computations) == 3
    assert cache.maximum_generations_per_entry == 1


def test_r9_full_corpus_query_collapse_separates_real_cycle_contexts():
    mod = _module()
    cache = mod._DependencyScopedCache(maximum_variants=4)
    guards: set[str] = set()
    evaluations: list[bool] = []

    def evaluate():
        present = "cycle" in guards
        evaluations.append(present)
        return frozenset({("cycle", present)}), present

    absent = cache.resolve_stable_requirements(
        "query", lambda: (), guards.__contains__, evaluate
    )
    guards.add("unrelated")
    equivalent = cache.resolve_stable_requirements(
        "query", lambda: (), guards.__contains__, evaluate
    )
    guards.add("cycle")
    cyclic = cache.resolve_stable_requirements(
        "query", lambda: (), guards.__contains__, evaluate
    )

    assert absent == equivalent == (frozenset({("cycle", False)}), False)
    assert cyclic == (frozenset({("cycle", True)}), True)
    assert evaluations == [False, True]
    assert cache.maximum_variants_per_entry == 2


def test_r9_full_corpus_query_collapse_rejects_unstable_and_incomplete():
    mod = _module()
    cache = mod._DependencyScopedCache(maximum_variants=4)
    stability = [0]
    unstable_calls = [0]

    def unstable():
        unstable_calls[0] += 1
        stability[0] += 1
        return frozenset(), ("unstable", True)

    for _ in range(2):
        cache.resolve_stable_requirements(
            "unstable",
            lambda: (),
            lambda _key: False,
            unstable,
            stability_signature_factory=lambda: stability[0],
            cacheable=lambda value: value[1],
        )
    assert unstable_calls[0] == 2

    incomplete_calls = [0]

    def incomplete():
        incomplete_calls[0] += 1
        return frozenset(), ("fail-closed", False)

    for _ in range(2):
        cache.resolve_stable_requirements(
            "incomplete",
            lambda: (),
            lambda _key: False,
            incomplete,
            stability_signature_factory=lambda: stability[0],
            cacheable=lambda value: value[1],
        )
    assert incomplete_calls[0] == 2
    assert cache.unstable_results == 4
    assert len(cache) == 0


def test_r9_full_corpus_query_collapse_cold_warm_reversed_exact():
    source = (
        "def run(flag, items, holder):\n"
        "    callbacks = []\n"
        "    def candidate():\n"
        "        open('candidate.txt')\n"
        "    try:\n"
        "        for item in items:\n"
        "            if flag:\n"
        "                callbacks.append(candidate)\n"
        "            holder.slot = callbacks\n"
        "            consume(callbacks)\n"
        "    except (ValueError, TypeError):\n"
        "        callbacks.extend([candidate])\n"
        "    finally:\n"
        "        for callback in callbacks:\n"
        "            callback()\n"
    )
    reference = _r9_summary_execution_probe(
        source,
        use_structural_summary=True,
        use_full_corpus_query_collapse=False,
    )
    cold = _r9_summary_execution_probe(
        source,
        use_structural_summary=True,
        use_full_corpus_query_collapse=True,
    )
    warm = _r9_summary_execution_probe(
        source,
        use_structural_summary=True,
        use_full_corpus_query_collapse=True,
    )
    reversed_result = _r9_summary_execution_probe(
        source,
        use_structural_summary=True,
        use_full_corpus_query_collapse=True,
        reverse_dataflow_predecessors=True,
    )

    for field in (
        "ordered_nodes", "states", "resolutions", "call_names", "incomplete"
    ):
        assert cold[field] == warm[field] == reversed_result[field]
        assert cold[field] == reference[field]
    metrics = cold["metrics"]
    assert metrics["full_corpus_query_cache_hits"] > 0
    assert metrics["full_corpus_query_computations"] < metrics[
        "full_corpus_query_count"
    ]
    assert metrics["full_corpus_query_cache_entries"] <= 4096
    assert metrics["full_corpus_query_maximum_generations"] <= 1


def test_r9_full_corpus_query_collapse_preserves_exception_findings_order(
    tmp_path, monkeypatch
):
    repo, commit = _synthetic_repo(
        tmp_path,
        {
            "main.py": "from helper import run\nrun(flag, items)\n",
            "helper.py": (
                "import sqlite3\n"
                "def run(flag, items):\n"
                "    callbacks = []\n"
                "    def first():\n"
                "        sqlite3.connect('first.db')\n"
                "    def second():\n"
                "        sqlite3.connect('second.db')\n"
                "        import deeper\n"
                "    try:\n"
                "        if flag:\n"
                "            callbacks.append(first)\n"
                "        for item in items:\n"
                "            callbacks.append(second)\n"
                "    except Exception:\n"
                "        callbacks.extend([first, second])\n"
                "    for callback in callbacks:\n"
                "        callback()\n"
            ),
            "deeper.py": "VALUE = 1\n",
        },
    )
    mod = _module()
    monkeypatch.setattr(mod, "_USE_FULL_CORPUS_QUERY_COLLAPSE", False)
    reference = _one_hop(repo, commit, "main.py")
    monkeypatch.setattr(mod, "_USE_FULL_CORPUS_QUERY_COLLAPSE", True)
    optimized = _one_hop(repo, commit, "main.py")
    repeated = _one_hop(repo, commit, "main.py")

    assert optimized == repeated == reference
    assert optimized["state"] == "unknown"
    assert optimized["reason"] == "import_resolution_incomplete"
    assert [
        (finding["line"], finding["resolved_api"])
        for finding in optimized["findings"]
    ] == [
        (5, "sqlite3.connect"),
        (7, "sqlite3.connect"),
    ]


def test_r9_full_corpus_sys_path_absence_skips_dispatch_query(monkeypatch):
    mod = _module()
    tree = ast.parse(
        "import os\n"
        "def dormant():\n"
        "    return os.path.join('a', 'b')\n"
    )

    def unexpected_dispatch(*_args, **_kwargs):
        raise AssertionError("dispatch analysis is unnecessary without sys.path updates")

    monkeypatch.setattr(
        mod,
        "_invoked_local_definition_reachability",
        unexpected_dispatch,
    )
    assert mod._bounded_sys_path_updates(tree, "tools/sample.py") == ((), ())


def test_r9_full_corpus_mutable_iterable_uses_alias_dependency_slice():
    unrelated = "".join(
        f"    unrelated_{index} = []\n"
        f"    unrelated_{index}.append({index})\n"
        for index in range(24)
    )
    source = (
        "def run(flag):\n"
        "    callbacks = []\n"
        "    def candidate():\n"
        "        open('candidate.txt')\n"
        + unrelated
        + "    alias = callbacks\n"
        "    if flag:\n"
        "        alias.append(candidate)\n"
        "    for callback in callbacks:\n"
        "        callback()\n"
    )
    reference = _r9_summary_execution_probe(
        source,
        use_structural_summary=True,
        use_full_corpus_query_collapse=False,
    )
    optimized = _r9_summary_execution_probe(
        source,
        use_structural_summary=True,
        use_full_corpus_query_collapse=True,
    )

    for field in (
        "ordered_nodes", "states", "resolutions", "call_names", "incomplete"
    ):
        assert optimized[field] == reference[field]
    metrics = optimized["metrics"]
    assert metrics["mutable_iterable_relevant_event_candidates"] < metrics[
        "mutable_iterable_event_candidates"
    ]


def test_r9_full_corpus_raise_observer_deep_chain_is_iterative():
    mod = _module()
    root = mod._RaiseGuardRequirementObserver(frozenset())
    observer = root
    for _index in range(1_500):
        observer = mod._RaiseGuardRequirementObserver(
            frozenset(), observer
        )
    requirement = ("expression", (17, 23))

    observer.observe(requirement, False)

    assert observer.requirements[requirement] is False
    assert root.requirements[requirement] is False


def test_r9_full_corpus_definition_recursion_budget_is_scoped():
    mod = _module()
    source = "def run(obj):\n    return obj" + ".child" * 160 + "\n"
    tree = ast.parse(source)
    definition = tree.body[0]
    initial_limit = sys.getrecursionlimit()

    nodes, _states, _resolutions, _incomplete = mod._definition_execution_nodes(
        definition,
        mod.collect_aliases(tree),
        None,
        {"run": definition},
        {},
        trusted_aliases=mod._ScopedAliasResolver(tree).module_aliases(),
        use_full_corpus_query_collapse=True,
    )

    assert nodes
    assert sys.getrecursionlimit() == initial_limit


def test_r9_full_corpus_structural_scope_is_bounded_and_deterministic():
    mod = _module()
    scope = mod._FullCorpusQueryCollapseScope(
        maximum_structural_entries=2
    )
    definitions = [
        ast.parse(f"def run_{index}():\n    return {index}\n").body[0]
        for index in range(3)
    ]
    first_dumps = []
    for index, definition in enumerate(definitions):
        summary = scope.structural_summary_for(
            (f"module_{index}.py", f"blob-{index}"), definition
        )
        first_dumps.append(
            tuple(ast.dump(node) for node in summary.statements)
        )

    assert scope.structural_entry_count == 2
    assert scope.maximum_structural_entries == 2
    repeated = scope.structural_summary_for(
        ("module_2.py", "blob-2"), definitions[2]
    )
    assert tuple(ast.dump(node) for node in repeated.statements) == first_dumps[2]
    assert scope.maximum_generations_per_structural_entry == 1


def test_r9_full_corpus_execution_query_contexts_share_and_isolate():
    mod = _module()
    scope = mod._FullCorpusQueryCollapseScope(
        maximum_structural_entries=2
    )

    first = scope.execution_query_caches_for(("blob", "owner-a"))
    repeated = scope.execution_query_caches_for(("blob", "owner-a"))
    isolated = scope.execution_query_caches_for(("blob", "owner-b"))

    assert first is repeated
    assert isolated is not first
    assert scope.execution_query_context_hits == 1
    assert scope.execution_query_context_misses == 2
    assert scope.execution_query_context_count == 2

    scope.execution_query_caches_for(("blob", "owner-c"))
    assert scope.execution_query_context_count == 2


def test_r9_module_eager_dispatch_proof_skips_only_dormant_definitions(
    monkeypatch,
):
    mod = _module()
    tree = ast.parse(
        "import logging\n"
        "logger = logging.getLogger(__name__)\n"
        "class Worker:\n"
        "    def run(self):\n"
        "        return dangerous()\n"
        "def helper():\n"
        "    return Worker().run()\n"
    )

    assert mod._module_eager_local_dispatch_is_absent(tree) is True
    reference = mod._invoked_local_definition_reachability(
        tree, use_eager_dispatch_proof=False
    )
    assert reference == (
        set(), set(), {(None, "helper"), ("Worker", "run")}, False
    )
    monkeypatch.setattr(
        mod,
        "_definition_execution_nodes",
        lambda *_args, **_kwargs: pytest.fail(
            "dormant definitions must not enter execution analysis"
        ),
    )
    reached, unknown, known, incomplete = (
        mod._invoked_local_definition_reachability(tree)
    )

    assert reached == set()
    assert unknown == set()
    assert known == {(None, "helper"), ("Worker", "run")}
    assert incomplete is False


@pytest.mark.parametrize(
    "source",
    [
        "def local():\n    return 1\nlocal()\n",
        "def local():\n    return 1\nalias = local\nalias()\n",
        "def local():\n    return 1\nregister(lambda: local())\n",
        "@decorate\ndef local():\n    return 1\n",
        "class Worker:\n    def run():\n        return 1\n    run()\n",
        "def local():\n    return 1\nglobals()['local']()\n",
    ],
)
def test_r9_module_eager_dispatch_proof_rejects_ambiguous_execution(source):
    mod = _module()
    assert mod._module_eager_local_dispatch_is_absent(
        ast.parse(source)
    ) is False


def test_r9_function_return_query_fixed_point_is_bounded_and_exact():
    source = (
        "def run(flag):\n"
        "    def first():\n"
        "        return second()\n"
        "    def second():\n"
        "        if flag:\n"
        "            return first()\n"
        "        return []\n"
        "    callbacks = first()\n"
        "    repeated = first()\n"
        "    for callback in callbacks + repeated:\n"
        "        callback()\n"
    )
    reference = _r9_summary_execution_probe(
        source,
        use_structural_summary=True,
        use_full_corpus_query_collapse=False,
    )
    optimized = _r9_summary_execution_probe(
        source,
        use_structural_summary=True,
        use_full_corpus_query_collapse=True,
    )

    for field in (
        "ordered_nodes", "states", "resolutions", "call_names", "incomplete"
    ):
        assert optimized[field] == reference[field]
    metrics = optimized["metrics"]
    assert metrics["function_return_query_computations"] == metrics[
        "function_return_query_cache_misses"
    ]
    assert metrics["function_return_query_cache_entries"] <= 2_048
    assert metrics["function_return_query_maximum_generations"] <= 1
    assert metrics["return_resolution_query_computations"] == metrics[
        "return_resolution_query_cache_misses"
    ]
    assert metrics["return_resolution_query_cache_entries"] <= 2_048
    assert metrics["return_resolution_query_maximum_generations"] <= 1
    assert metrics["value_resolution_query_computations"] == metrics[
        "value_resolution_query_cache_misses"
    ]
    assert metrics["value_resolution_query_cache_entries"] <= 4_096


def test_r9_transitive_completeness_incomplete_guarded_import_is_unknown(
    tmp_path,
):
    repo, commit = _synthetic_repo(
        tmp_path,
        {
            "main.py": (
                "import sys\n"
                "def launch():\n"
                "    sys.path.insert(0, choose_plugin_root())\n"
                "    from helper import run\n"
                "    return run()\n"
                "if __name__ == '__main__':\n"
                "    launch()\n"
            ),
            "plugins/helper.py": "def run():\n    return 1\n",
        },
    )

    result = _one_hop(repo, commit, "main.py")

    assert result["state"] == "unknown"
    assert result["reason"] == "import_resolution_incomplete"
    assert result["findings"] == []


def test_r9_transitive_completeness_unsupported_guarded_import_is_unknown(
    tmp_path,
):
    repo, commit = _synthetic_repo(
        tmp_path,
        {
            "main.py": (
                "def launch():\n"
                "    from helper import run\n"
                "    return run()\n"
                "if __name__ == '__main__':\n"
                "    launch()\n"
            ),
            "helper.py": (
                "from unavailable_package import *\n"
                "def run():\n"
                "    return 1\n"
            ),
        },
    )

    result = _one_hop(repo, commit, "main.py")

    assert result["state"] == "unknown"
    assert result["reason"] in {
        "import_resolution_incomplete",
        "imported_scan_incomplete; import_resolution_incomplete",
    }
    assert result["findings"] == []


def test_r9_transitive_completeness_unresolved_guarded_target_is_unknown(
    tmp_path,
):
    repo, commit = _synthetic_repo(
        tmp_path,
        {
            "main.py": (
                "def launch(name):\n"
                "    from helper import run\n"
                "    callbacks = {'run': run}\n"
                "    return callbacks[name]()\n"
                "if __name__ == '__main__':\n"
                "    launch(select_name())\n"
            ),
            "helper.py": "def run():\n    return 1\n",
        },
    )

    result = _one_hop(repo, commit, "main.py")

    assert result["state"] == "unknown"
    assert result["reason"] == "import_resolution_incomplete"
    assert result["findings"] == []


def test_r9_transitive_completeness_empty_complete_import_is_not_detected(
    tmp_path,
):
    repo, commit = _synthetic_repo(
        tmp_path,
        {
            "main.py": "from helper import run\nrun()\n",
            "helper.py": "def run():\n    return 1\n",
        },
    )

    result = _one_hop(repo, commit, "main.py")

    assert result == _module().complete_transitive_absence()


def test_r9_transitive_completeness_dormant_nested_import_is_not_detected(
    tmp_path,
):
    repo, commit = _synthetic_repo(
        tmp_path,
        {
            "main.py": (
                "def launch():\n"
                "    def dormant():\n"
                "        from dangerous import run\n"
                "        return run()\n"
                "    return 1\n"
                "launch()\n"
            ),
            "dangerous.py": (
                "import sqlite3\n"
                "def run():\n"
                "    return sqlite3.connect('danger.db')\n"
            ),
        },
    )

    result = _one_hop(repo, commit, "main.py")

    assert result == _module().complete_transitive_absence()


def test_r9_transitive_completeness_concrete_imported_finding_is_preserved(
    tmp_path,
):
    repo, commit = _synthetic_repo(
        tmp_path,
        {
            "main.py": "from helper import run\nrun()\n",
            "helper.py": (
                "import sqlite3\n"
                "def run():\n"
                "    return sqlite3.connect('known.db')\n"
            ),
        },
    )

    result = _one_hop(repo, commit, "main.py")

    assert result["state"] == "detected"
    assert [
        (finding["resolved_api"], finding["imported_module_path"])
        for finding in result["findings"]
    ] == [("sqlite3.connect", "helper.py")]


def test_r9_transitive_completeness_partial_resolution_keeps_known_finding(
    tmp_path,
):
    repo, commit = _synthetic_repo(
        tmp_path,
        {
            "main.py": (
                "from helper import run\n"
                "callback = run\n"
                "if choose_branch():\n"
                "    callback = unresolved\n"
                "callback()\n"
            ),
            "helper.py": (
                "import sqlite3\n"
                "def run():\n"
                "    return sqlite3.connect('known.db')\n"
            ),
        },
    )

    result = _one_hop(repo, commit, "main.py")

    assert result["state"] == "unknown"
    assert result["reason"] == "import_resolution_incomplete"
    assert any(
        finding["resolved_api"] == "sqlite3.connect"
        and finding["imported_module_path"] == "helper.py"
        for finding in result["findings"]
    )


def test_r9_transitive_completeness_unknown_reason_survives_composition():
    mod = _module()
    transitive = mod._evidence(
        "unknown",
        scope="transitive",
        reason="import_resolution_incomplete",
    )

    result = mod.analyze_source_bytes(
        "synthetic.py",
        b"VALUE = 1\n",
        "1" * 40,
        transitive_evidence=transitive,
    )

    assert result["evidence"]["transitive_external_state"]["state"] == "unknown"
    assert result["evidence"]["transitive_external_state"]["reason"] == (
        "import_resolution_incomplete"
    )


def test_r9_transitive_completeness_unknown_drives_existing_safety_policy():
    mod = _module()
    transitive = mod._evidence(
        "unknown",
        scope="transitive",
        reason="import_resolution_incomplete",
    )

    result = mod.analyze_source_bytes(
        "synthetic.py",
        b"open('known.txt', 'w')\n",
        "1" * 40,
        transitive_evidence=transitive,
    )

    assert result["safety_classification"] == {
        "risk_level": "unknown",
        "low_risk_eligible": False,
        "disposition": "NEEDS_CTO_REVIEW_UNKNOWN",
        "reasons": ["unknown:transitive_external_state"],
    }


def test_r9_transitive_completeness_separate_lexical_owners_stay_isolated(
    tmp_path,
):
    repo, commit = _synthetic_repo(
        tmp_path,
        {
            "main.py": "from helper import Safe, Dangerous\nSafe().run()\n",
            "helper.py": (
                "import sqlite3\n"
                "class Safe:\n"
                "    def run(self):\n"
                "        return 1\n"
                "class Dangerous:\n"
                "    def run(self):\n"
                "        return sqlite3.connect('must-not-leak.db')\n"
            ),
        },
    )

    result = _one_hop(repo, commit, "main.py")

    assert result == _module().complete_transitive_absence()


def test_r9_transitive_completeness_cold_warm_and_reversed_are_equal(
    tmp_path,
):
    repo, commit = _synthetic_repo(
        tmp_path,
        {
            "safe.py": "from helper import safe\nsafe()\n",
            "danger.py": "from helper import dangerous\ndangerous()\n",
            "helper.py": (
                "import sqlite3\n"
                "def safe():\n"
                "    return 1\n"
                "def dangerous():\n"
                "    return sqlite3.connect('known.db')\n"
            ),
        },
    )
    mod = _module()
    paths = ("safe.py", "danger.py")
    entries = mod.git_tree_entries(repo, commit, paths)

    def run(order, *, shared):
        caches = _r9_shared_transitive_caches() if shared else None
        scope = mod._FullCorpusQueryCollapseScope() if shared else None
        results = {}
        for path in order:
            kwargs = dict(caches or {})
            if scope is not None:
                kwargs["query_collapse_scope"] = scope
            results[path] = mod.one_hop_transitive_evidence(
                path,
                mod.git_blob(repo, entries[path]["blob_id"]),
                repo,
                commit,
                **kwargs,
            )
        return results

    cold = run(paths, shared=False)
    warm = run(paths, shared=True)
    reversed_results = run(tuple(reversed(paths)), shared=True)

    assert warm == cold
    assert reversed_results == cold


def test_r9_transitive_completeness_demand_and_reference_paths_are_equal(
    tmp_path, monkeypatch,
):
    repo, commit = _synthetic_repo(
        tmp_path,
        {
            "main.py": "from helper import run\nrun()\n",
            "helper.py": (
                "import sqlite3\n"
                "def run():\n"
                "    def local():\n"
                "        return sqlite3.connect('known.db')\n"
                "    return local()\n"
            ),
        },
    )
    mod = _module()

    monkeypatch.setattr(mod, "_USE_DEMAND_DRIVEN_DATAFLOW", False)
    reference = _one_hop(repo, commit, "main.py")
    monkeypatch.setattr(mod, "_USE_DEMAND_DRIVEN_DATAFLOW", True)
    demand = _one_hop(repo, commit, "main.py")

    assert reference["state"] == "detected"
    assert demand == reference
