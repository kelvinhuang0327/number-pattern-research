"""P520C tests for the ingest after-insert hook healthcheck.

The healthcheck parses lottery_api/routes/ingest.py as source/AST only. These
tests do not import the app route module, do not execute draw inserts, do not
open or write a database, do not run migrations/backfills, and do not deploy.
"""
from __future__ import annotations

import ast
import csv
import json
from pathlib import Path

import tools.ingest_afterinsert_hook_healthcheck as healthcheck


def test_healthcheck_reports_pass_for_current_ingest_hook_surface():
    result = healthcheck.build_healthcheck_bundle()["health"]

    assert result["final_status"] == "PASS"
    assert result["refresh_after_insert_present"] is True
    assert result["detected_live_hook_count"] == len(healthcheck.EXPECTED_LIVE_HOOKS)
    assert result["missing_or_renamed_live_hooks"] == []
    assert result["dead_hook_absence_status"] == "PASS"
    assert result["warning_count"] == 0
    assert result["failure_count"] == 0
    assert result["component_statuses"]["runtime import avoided"] == "PASS"
    assert result["component_statuses"]["DB side effects avoided"] == "PASS"


def test_hook_inventory_lists_expected_live_hook_references():
    rendered = healthcheck.render_artifacts()
    rows = list(csv.DictReader(rendered[healthcheck.HOOK_INVENTORY_PATH].splitlines()))
    by_hook = {row["hook_name"]: row for row in rows}

    assert set(by_hook) == set(healthcheck.EXPECTED_LIVE_HOOKS)
    for hook_name in healthcheck.EXPECTED_LIVE_HOOKS:
        assert by_hook[hook_name]["expected"] == "True"
        assert by_hook[hook_name]["present"] == "True"
        assert by_hook[hook_name]["status"] == "PASS"
        assert by_hook[hook_name]["line"]
        assert by_hook[hook_name]["evidence"]


def test_dead_hook_check_pins_removed_symbols_absent():
    rendered = healthcheck.render_artifacts()
    rows = list(csv.DictReader(rendered[healthcheck.DEAD_HOOKS_PATH].splitlines()))
    by_symbol = {row["symbol"]: row for row in rows}

    assert set(by_symbol) == set(healthcheck.REMOVED_DEAD_HOOKS)
    for symbol in healthcheck.REMOVED_DEAD_HOOKS:
        assert by_symbol[symbol]["absent_from_source_text"] == "True"
        assert by_symbol[symbol]["absent_from_ast_names"] == "True"
        assert by_symbol[symbol]["status"] == "PASS"


def test_completion_summary_records_no_db_no_runtime_import_scope():
    rendered = healthcheck.render_artifacts()
    summary = json.loads(rendered[healthcheck.COMPLETION_SUMMARY_PATH])

    assert summary["completion_status"] == "PASS"
    assert summary["source_ast_only"] is True
    assert summary["imports_lottery_api_routes_ingest"] is False
    assert summary["executes_draw_insert"] is False
    assert summary["opens_or_writes_db"] is False
    assert summary["runs_migration_backfill_or_deploy"] is False
    assert summary["implements_replacement_scheduler_or_tracker"] is False
    assert summary["live_hook_references_visible"] is True
    assert summary["removed_dead_hooks_absent"] is True


def test_status_block_is_copy_paste_friendly_and_scoped():
    block = healthcheck.build_healthcheck_bundle()["status_block"]

    assert "Final status: `PASS`" in block
    assert "`_refresh_after_insert` present: `True`" in block
    assert "Dead hook absence status: `PASS`" in block
    for notice in healthcheck.NOTICE_LINES:
        assert notice in block


def test_rendered_artifacts_are_deterministic_across_runs():
    first = healthcheck.render_artifacts()
    second = healthcheck.render_artifacts()
    assert first == second


def test_generate_and_validate_artifacts_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(healthcheck, "ARTIFACTS_DIR", tmp_path)
    monkeypatch.setattr(healthcheck, "HEALTH_PATH", tmp_path / "P520C_ingest_afterinsert_hook_healthcheck_result.json")
    monkeypatch.setattr(
        healthcheck,
        "HOOK_INVENTORY_PATH",
        tmp_path / "P520C_ingest_afterinsert_hook_healthcheck_hook_inventory.csv",
    )
    monkeypatch.setattr(
        healthcheck,
        "DEAD_HOOKS_PATH",
        tmp_path / "P520C_ingest_afterinsert_hook_healthcheck_dead_hooks.csv",
    )
    monkeypatch.setattr(
        healthcheck,
        "COMPLETION_SUMMARY_PATH",
        tmp_path / "P520C_ingest_afterinsert_hook_healthcheck_completion_summary.json",
    )
    monkeypatch.setattr(
        healthcheck,
        "STATUS_BLOCK_PATH",
        tmp_path / "P520C_ingest_afterinsert_hook_healthcheck_status_block.md",
    )
    monkeypatch.setattr(
        healthcheck,
        "MANIFEST_PATH",
        tmp_path / "P520C_ingest_afterinsert_hook_healthcheck_manifest.csv",
    )

    rendered = healthcheck.write_artifacts()
    ok, mismatches = healthcheck.validate_artifacts(rendered)

    assert ok, mismatches
    assert set(rendered) == {
        tmp_path / "P520C_ingest_afterinsert_hook_healthcheck_result.json",
        tmp_path / "P520C_ingest_afterinsert_hook_healthcheck_hook_inventory.csv",
        tmp_path / "P520C_ingest_afterinsert_hook_healthcheck_dead_hooks.csv",
        tmp_path / "P520C_ingest_afterinsert_hook_healthcheck_completion_summary.json",
        tmp_path / "P520C_ingest_afterinsert_hook_healthcheck_status_block.md",
        tmp_path / "P520C_ingest_afterinsert_hook_healthcheck_manifest.csv",
    }


def test_cli_parser_exposes_required_p520c_flags():
    help_text = healthcheck.build_parser().format_help()

    for flag in (
        "--generate",
        "--health",
        "--hook-inventory",
        "--dead-hook-check",
        "--completion-summary",
        "--status-block",
        "--validate",
        "--help",
    ):
        assert flag in help_text


def test_healthcheck_module_does_not_import_ingest_route_or_db_runtime():
    source = Path(healthcheck.__file__).read_text(encoding="utf-8")
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
    rendered = healthcheck.render_artifacts()
    result = json.loads(rendered[healthcheck.HEALTH_PATH])
    summary = json.loads(rendered[healthcheck.COMPLETION_SUMMARY_PATH])
    manifest_rows = list(csv.DictReader(rendered[healthcheck.MANIFEST_PATH].splitlines()))

    assert result["final_status"] == "PASS"
    assert summary["completion_status"] == "PASS"
    assert len(manifest_rows) == 6
    assert manifest_rows[-1]["sha256"] == ""
