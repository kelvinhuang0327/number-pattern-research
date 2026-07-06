"""P520I tests for source/AST-only ingest hook static binding resolution.

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

import tools.ingest_afterinsert_hook_static_binding_resolver as resolver


EXPECTED_HOOKS = set()


def test_static_binding_resolver_reads_exact_p520h_unresolved_probable_refs():
    result = resolver.build_static_binding_bundle()["result"]

    assert result["final_status"] == "PASS"
    assert result["focused_reference_count"] == 0
    assert result["confirmed_hook_count"] == 0
    assert result["probable_hook_count"] == 0
    assert result["unresolved_hook_count"] == 0
    assert set(result["unresolved_hooks"]) == EXPECTED_HOOKS
    assert result["unresolved_reasons"] == []
    assert result["component_statuses"]["runtime import avoided"] == "PASS"
    assert result["component_statuses"]["DB side effects avoided"] == "PASS"
    assert result["component_statuses"]["target confirmation conservative"] == "PASS"


def test_binding_chain_matrix_maps_import_aliases_without_confirming_missing_sources():
    rendered = resolver.render_artifacts()
    rows = list(csv.DictReader(rendered[resolver.BINDING_CHAIN_PATH].splitlines()))
    by_hook = {row["hook_name"]: row for row in rows}

    assert set(by_hook) == EXPECTED_HOOKS


def test_inspected_files_records_static_path_mapping_candidates():
    rendered = resolver.render_artifacts()
    rows = list(csv.DictReader(rendered[resolver.INSPECTED_FILES_PATH].splitlines()))
    by_hook = {}
    for row in rows:
        by_hook.setdefault(row["hook_name"], []).append(row)

    assert set(by_hook) == EXPECTED_HOOKS


def test_unresolved_reasons_are_source_file_missing_and_static_followup():
    rendered = resolver.render_artifacts()
    rows = list(csv.DictReader(rendered[resolver.UNRESOLVED_PATH].splitlines()))

    assert rows == []


def test_status_block_is_copy_paste_friendly_and_scoped():
    block = resolver.build_static_binding_bundle()["status_block"]

    assert "Final status: `PASS`" in block
    assert "Confirmed hook count: `0`" in block
    assert "Probable hook count: `0`" in block
    assert "Unresolved hook count: `0`" in block
    assert "Unresolved reasons: ``" in block
    for notice in resolver.NOTICE_LINES:
        assert notice in block


def test_rendered_artifacts_are_deterministic_across_runs():
    first = resolver.render_artifacts()
    second = resolver.render_artifacts()
    assert first == second


def test_generate_and_validate_artifacts_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(resolver, "ARTIFACTS_DIR", tmp_path)
    monkeypatch.setattr(resolver, "RESULT_PATH", tmp_path / "P520I_ingest_afterinsert_hook_static_binding_resolver_result.json")
    monkeypatch.setattr(
        resolver,
        "BINDING_CHAIN_PATH",
        tmp_path / "P520I_ingest_afterinsert_hook_static_binding_resolver_binding_chain.csv",
    )
    monkeypatch.setattr(
        resolver,
        "INSPECTED_FILES_PATH",
        tmp_path / "P520I_ingest_afterinsert_hook_static_binding_resolver_inspected_files.csv",
    )
    monkeypatch.setattr(resolver, "UNRESOLVED_PATH", tmp_path / "P520I_ingest_afterinsert_hook_static_binding_resolver_unresolved.csv")
    monkeypatch.setattr(
        resolver,
        "STATUS_BLOCK_PATH",
        tmp_path / "P520I_ingest_afterinsert_hook_static_binding_resolver_status_block.md",
    )
    monkeypatch.setattr(resolver, "MANIFEST_PATH", tmp_path / "P520I_ingest_afterinsert_hook_static_binding_resolver_manifest.csv")

    rendered = resolver.write_artifacts()
    ok, mismatches = resolver.validate_artifacts(rendered)

    assert ok, mismatches
    assert set(rendered) == {
        tmp_path / "P520I_ingest_afterinsert_hook_static_binding_resolver_result.json",
        tmp_path / "P520I_ingest_afterinsert_hook_static_binding_resolver_binding_chain.csv",
        tmp_path / "P520I_ingest_afterinsert_hook_static_binding_resolver_inspected_files.csv",
        tmp_path / "P520I_ingest_afterinsert_hook_static_binding_resolver_unresolved.csv",
        tmp_path / "P520I_ingest_afterinsert_hook_static_binding_resolver_status_block.md",
        tmp_path / "P520I_ingest_afterinsert_hook_static_binding_resolver_manifest.csv",
    }


def test_cli_parser_exposes_required_p520i_flags():
    help_text = resolver.build_parser().format_help()

    for flag in (
        "--generate",
        "--binding-chain",
        "--inspected-files",
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
    binding_rows = list(csv.DictReader(rendered[resolver.BINDING_CHAIN_PATH].splitlines()))
    inspected_rows = list(csv.DictReader(rendered[resolver.INSPECTED_FILES_PATH].splitlines()))
    unresolved_rows = list(csv.DictReader(rendered[resolver.UNRESOLVED_PATH].splitlines()))
    manifest_rows = list(csv.DictReader(rendered[resolver.MANIFEST_PATH].splitlines()))

    assert result["final_status"] == "PASS"
    assert result["failure_count"] == 0
    assert len(binding_rows) == 0
    assert len(inspected_rows) == 0
    assert len(unresolved_rows) == 0
    assert len(manifest_rows) == 6
    assert manifest_rows[-1]["sha256"] == ""
