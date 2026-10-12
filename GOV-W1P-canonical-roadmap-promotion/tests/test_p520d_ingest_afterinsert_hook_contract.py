"""P520D tests for the ingest after-insert live hook contract evaluator.

The evaluator parses source files only. These tests do not import
lottery_api.routes.ingest, do not execute hooks or draw inserts, do not open or
write a database, do not run migrations/backfills, and do not deploy.
"""
from __future__ import annotations

import ast
import csv
import json
from pathlib import Path

import tools.ingest_afterinsert_hook_contract as contract


def test_contract_reports_current_live_hook_surface_without_failures():
    result = contract.build_contract_bundle()["result"]

    assert result["final_status"] == "PASS"
    assert result["refresh_after_insert_present"] is True
    assert result["detected_live_hook_count"] == len(contract.EXPECTED_HOOKS)
    assert result["call_like_live_hook_count"] == len(contract.EXPECTED_HOOKS)
    assert result["target_resolution_pass_count"] == 1
    assert result["target_resolution_warn_count"] == 0
    assert result["removed_missing_target_hooks"] == list(contract.REMOVED_MISSING_TARGET_HOOKS)
    assert result["removed_missing_target_hook_count"] == len(contract.REMOVED_MISSING_TARGET_HOOKS)
    assert result["missing_target_residue_status"] == "PASS"
    assert result["missing_target_residue"] == []
    assert result["dead_hook_absence_status"] == "PASS"
    assert result["warning_count"] == 0
    assert result["failure_count"] == 0
    assert result["component_statuses"]["runtime import avoided"] == "PASS"
    assert result["component_statuses"]["DB side effects avoided"] == "PASS"


def test_contract_matrix_lists_expected_live_hooks_with_call_like_evidence():
    rendered = contract.render_artifacts()
    rows = list(csv.DictReader(rendered[contract.CONTRACT_MATRIX_PATH].splitlines()))
    by_hook = {row["hook_reference"]: row for row in rows}

    assert set(by_hook) == {spec.hook_reference for spec in contract.EXPECTED_HOOKS}
    for spec in contract.EXPECTED_HOOKS:
        row = by_hook[spec.hook_reference]
        assert row["expected_live"] == "True"
        assert row["refresh_after_insert_present"] == "True"
        assert row["reference_found"] == "True"
        assert row["source_line"]
        assert row["reference_evidence"]
        assert row["call_like_in_refresh_after_insert"] == "True"
        assert row["call_line"]
        assert row["call_evidence"]
        assert row["imported_or_assigned_symbol"]
        assert row["status"] in {"PASS", "WARN"}


def test_target_resolution_distinguishes_static_pass_from_unresolved_warnings():
    rendered = contract.render_artifacts()
    rows = list(csv.DictReader(rendered[contract.TARGET_RESOLUTION_PATH].splitlines()))
    by_hook = {row["hook_reference"]: row for row in rows}

    scheduler = by_hook["scheduler.load_data"]
    assert scheduler["static_target_resolution"] == "PASS"
    assert scheduler["target_path"] == "lottery_api/utils/scheduler.py"
    assert scheduler["target_symbol_found"] == "True"
    assert scheduler["target_attribute_found"] == "True"
    assert scheduler["target_attribute_line"]

    assert set(by_hook) == {"scheduler.load_data"}


def test_dead_hook_check_pins_removed_symbols_absent():
    rendered = contract.render_artifacts()
    rows = list(csv.DictReader(rendered[contract.DEAD_HOOKS_PATH].splitlines()))
    by_symbol = {row["symbol"]: row for row in rows}

    assert set(by_symbol) == set(contract.REMOVED_DEAD_HOOKS)
    for symbol in contract.REMOVED_DEAD_HOOKS:
        assert by_symbol[symbol]["absent_from_source_text"] == "True"
        assert by_symbol[symbol]["absent_from_ast_names"] == "True"
        assert by_symbol[symbol]["status"] == "PASS"


def test_result_reads_p520c_artifact_summary_as_prior_evidence():
    result = contract.build_contract_bundle()["result"]
    summary = result["p520c_summary"]

    assert summary["result_present"] is True
    assert summary["final_status"] == "PASS"
    assert summary["expected_live_hooks"] == [spec.hook_reference for spec in contract.EXPECTED_HOOKS]
    assert summary["hook_inventory_rows"] == len(contract.EXPECTED_HOOKS) + len(contract.REMOVED_MISSING_TARGET_HOOKS)
    assert summary["dead_hook_rows"] == len(contract.REMOVED_DEAD_HOOKS)


def test_status_block_is_copy_paste_friendly_and_scoped():
    block = contract.build_contract_bundle()["status_block"]

    assert "Final status: `PASS`" in block
    assert "Static target resolution WARN count: `0`" in block
    assert "Missing-target residue status: `PASS`" in block
    assert "Dead hook absence status: `PASS`" in block
    for notice in contract.NOTICE_LINES:
        assert notice in block


def test_rendered_artifacts_are_deterministic_across_runs():
    first = contract.render_artifacts()
    second = contract.render_artifacts()
    assert first == second


def test_generate_and_validate_artifacts_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(contract, "ARTIFACTS_DIR", tmp_path)
    monkeypatch.setattr(contract, "RESULT_PATH", tmp_path / "P520D_ingest_afterinsert_hook_contract_result.json")
    monkeypatch.setattr(contract, "CONTRACT_MATRIX_PATH", tmp_path / "P520D_ingest_afterinsert_hook_contract_matrix.csv")
    monkeypatch.setattr(
        contract,
        "TARGET_RESOLUTION_PATH",
        tmp_path / "P520D_ingest_afterinsert_hook_contract_target_resolution.csv",
    )
    monkeypatch.setattr(contract, "DEAD_HOOKS_PATH", tmp_path / "P520D_ingest_afterinsert_hook_contract_dead_hooks.csv")
    monkeypatch.setattr(
        contract,
        "STATUS_BLOCK_PATH",
        tmp_path / "P520D_ingest_afterinsert_hook_contract_status_block.md",
    )
    monkeypatch.setattr(contract, "MANIFEST_PATH", tmp_path / "P520D_ingest_afterinsert_hook_contract_manifest.csv")

    rendered = contract.write_artifacts()
    ok, mismatches = contract.validate_artifacts(rendered)

    assert ok, mismatches
    assert set(rendered) == {
        tmp_path / "P520D_ingest_afterinsert_hook_contract_result.json",
        tmp_path / "P520D_ingest_afterinsert_hook_contract_matrix.csv",
        tmp_path / "P520D_ingest_afterinsert_hook_contract_target_resolution.csv",
        tmp_path / "P520D_ingest_afterinsert_hook_contract_dead_hooks.csv",
        tmp_path / "P520D_ingest_afterinsert_hook_contract_status_block.md",
        tmp_path / "P520D_ingest_afterinsert_hook_contract_manifest.csv",
    }


def test_cli_parser_exposes_required_p520d_flags():
    help_text = contract.build_parser().format_help()

    for flag in (
        "--generate",
        "--contract",
        "--target-resolution",
        "--dead-hook-check",
        "--status-block",
        "--validate",
        "--help",
    ):
        assert flag in help_text


def test_contract_module_does_not_import_ingest_route_or_db_runtime():
    source = Path(contract.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)

    assert "lottery_api.routes.ingest" not in imported_modules
    assert "lottery_api.routes" not in imported_modules
    assert "sqlite3" not in imported_modules
    assert "insert_draw" not in source


def test_generated_json_and_manifest_are_parseable():
    rendered = contract.render_artifacts()
    result = json.loads(rendered[contract.RESULT_PATH])
    manifest_rows = list(csv.DictReader(rendered[contract.MANIFEST_PATH].splitlines()))

    assert result["final_status"] == "PASS"
    assert result["failure_count"] == 0
    assert len(manifest_rows) == 6
    assert manifest_rows[-1]["sha256"] == ""
