"""P520H tests for source/AST-only ingest hook import-chain resolution.

The resolver reads committed artifacts and parses source only. These tests do
not import lottery_api.routes.ingest, do not import live hook target modules,
do not execute hooks or draw inserts, do not open or write a database, do not
run migrations/backfills, and do not deploy.
"""
from __future__ import annotations

import ast
import csv
import json
from pathlib import Path

import tools.ingest_afterinsert_hook_import_chain_resolver as resolver


EXPECTED_HOOKS = set()


def test_import_chain_resolver_reads_p520g_probable_refs_conservatively():
    result = resolver.build_import_chain_bundle()["result"]

    assert result["final_status"] == "PASS"
    assert result["probable_reference_count"] == 0
    assert result["confirmed_hook_count"] == 0
    assert result["probable_hook_count"] == 0
    assert result["unresolved_hook_count"] == 0
    assert result["target_source_unresolved_count"] == 0
    assert set(result["probable_hooks"]) == EXPECTED_HOOKS
    assert result["component_statuses"]["runtime import avoided"] == "PASS"
    assert result["component_statuses"]["DB side effects avoided"] == "PASS"
    assert result["component_statuses"]["target confirmation conservative"] == "PASS"


def test_import_chain_matrix_maps_ingest_imports_and_calls_without_confirming_targets():
    rendered = resolver.render_artifacts()
    rows = list(csv.DictReader(rendered[resolver.MATRIX_PATH].splitlines()))
    by_hook = {row["hook_name"]: row for row in rows}

    assert set(by_hook) == EXPECTED_HOOKS


def test_target_definition_evidence_records_unresolved_static_paths():
    rendered = resolver.render_artifacts()
    rows = list(csv.DictReader(rendered[resolver.TARGET_DEFINITIONS_PATH].splitlines()))

    assert rows == []


def test_unresolved_summary_marks_probable_references_for_runtime_instrumentation():
    rendered = resolver.render_artifacts()
    rows = list(csv.DictReader(rendered[resolver.UNRESOLVED_PATH].splitlines()))

    assert rows == []


def test_status_block_is_copy_paste_friendly_and_scoped():
    block = resolver.build_import_chain_bundle()["status_block"]

    assert "Final status: `PASS`" in block
    assert "Confirmed hook count: `0`" in block
    assert "Probable hook count: `0`" in block
    assert "Target source unresolved count: `0`" in block
    for notice in resolver.NOTICE_LINES:
        assert notice in block


def test_rendered_artifacts_are_deterministic_across_runs():
    first = resolver.render_artifacts()
    second = resolver.render_artifacts()
    assert first == second


def test_generate_and_validate_artifacts_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(resolver, "ARTIFACTS_DIR", tmp_path)
    monkeypatch.setattr(resolver, "RESULT_PATH", tmp_path / "P520H_ingest_afterinsert_hook_import_chain_resolver_result.json")
    monkeypatch.setattr(resolver, "MATRIX_PATH", tmp_path / "P520H_ingest_afterinsert_hook_import_chain_resolver_matrix.csv")
    monkeypatch.setattr(
        resolver,
        "TARGET_DEFINITIONS_PATH",
        tmp_path / "P520H_ingest_afterinsert_hook_import_chain_resolver_target_definitions.csv",
    )
    monkeypatch.setattr(resolver, "UNRESOLVED_PATH", tmp_path / "P520H_ingest_afterinsert_hook_import_chain_resolver_unresolved.csv")
    monkeypatch.setattr(
        resolver,
        "STATUS_BLOCK_PATH",
        tmp_path / "P520H_ingest_afterinsert_hook_import_chain_resolver_status_block.md",
    )
    monkeypatch.setattr(resolver, "MANIFEST_PATH", tmp_path / "P520H_ingest_afterinsert_hook_import_chain_resolver_manifest.csv")

    rendered = resolver.write_artifacts()
    ok, mismatches = resolver.validate_artifacts(rendered)

    assert ok, mismatches
    assert set(rendered) == {
        tmp_path / "P520H_ingest_afterinsert_hook_import_chain_resolver_result.json",
        tmp_path / "P520H_ingest_afterinsert_hook_import_chain_resolver_matrix.csv",
        tmp_path / "P520H_ingest_afterinsert_hook_import_chain_resolver_target_definitions.csv",
        tmp_path / "P520H_ingest_afterinsert_hook_import_chain_resolver_unresolved.csv",
        tmp_path / "P520H_ingest_afterinsert_hook_import_chain_resolver_status_block.md",
        tmp_path / "P520H_ingest_afterinsert_hook_import_chain_resolver_manifest.csv",
    }


def test_cli_parser_exposes_required_p520h_flags():
    help_text = resolver.build_parser().format_help()

    for flag in (
        "--generate",
        "--import-chain",
        "--target-definitions",
        "--unresolved",
        "--status-block",
        "--validate",
        "--help",
    ):
        assert flag in help_text


def test_static_module_mapping_checks_repo_root_and_lottery_api_prefixes():
    labels = [resolver._artifact_label(path) for path in resolver.module_path_candidates("engine.weight_adjuster")]

    assert "engine/weight_adjuster.py" in labels
    assert "engine/weight_adjuster/__init__.py" in labels
    assert "lottery_api/engine/weight_adjuster.py" in labels
    assert "lottery_api/engine/weight_adjuster/__init__.py" in labels
    assert resolver.resolve_module_path("engine.weight_adjuster") is None


def test_resolver_module_does_not_import_ingest_route_or_live_targets():
    source = Path(resolver.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)

    assert "lottery_api.routes.ingest" not in imported_modules
    assert "lottery_api.routes" not in imported_modules
    assert "analysis.payout.sync" not in imported_modules
    assert "engine.weight_adjuster" not in imported_modules
    assert "engine.learning_integrator" not in imported_modules
    assert "sqlite3" not in imported_modules
    assert "insert_draw" not in source


def test_generated_json_and_manifest_are_parseable():
    rendered = resolver.render_artifacts()
    result = json.loads(rendered[resolver.RESULT_PATH])
    matrix_rows = list(csv.DictReader(rendered[resolver.MATRIX_PATH].splitlines()))
    definition_rows = list(csv.DictReader(rendered[resolver.TARGET_DEFINITIONS_PATH].splitlines()))
    manifest_rows = list(csv.DictReader(rendered[resolver.MANIFEST_PATH].splitlines()))

    assert result["final_status"] == "PASS"
    assert result["failure_count"] == 0
    assert len(matrix_rows) == 0
    assert len(definition_rows) == 0
    assert len(manifest_rows) == 6
    assert manifest_rows[-1]["sha256"] == ""
