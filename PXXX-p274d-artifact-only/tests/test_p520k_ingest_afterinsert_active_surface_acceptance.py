"""P520K source-only acceptance for active after-insert hook surface.

These tests parse source and committed artifacts only. They do not import
lottery_api.routes.ingest, do not import live hook target modules, do not
execute hooks or draw inserts, do not open or write a database, do not run
migrations/backfills, and do not deploy.
"""
from __future__ import annotations

import ast
import csv
import json
from pathlib import Path

import tools.ingest_afterinsert_active_surface_acceptance as acceptance


EXPECTED_DISABLED_HOOKS = {
    "refresh_hedge_fund_outputs",
    "weight_adjuster",
    "learning_integrator",
}


def test_acceptance_result_keeps_scheduler_active_and_missing_hooks_out_of_completion_surface():
    bundle = acceptance.build_active_surface_acceptance_bundle()
    result = bundle["result"]
    summary = bundle["completion_summary"]

    assert result["acceptance_status"] == "PASS"
    assert result["final_status"] == "WARN"
    assert result["scheduler_load_data_active"] is True
    assert result["scheduler_load_data_outside_missing_hook_guard"] is True
    assert result["active_completion_surface"] == ["scheduler.load_data"]
    assert result["active_completion_surface_count"] == 1
    assert set(result["disabled_missing_target_surface"]) == EXPECTED_DISABLED_HOOKS
    assert result["missing_target_hooks_counted_as_active_completion_surface"] == []
    assert summary["missing_target_hooks_no_longer_active_completion_surface"] is True
    assert summary["scheduler_refresh_retained"] is True


def test_active_surface_csv_contains_only_scheduler_completion_surface():
    rendered = acceptance.render_artifacts()
    rows = list(csv.DictReader(rendered[acceptance.ACTIVE_SURFACE_PATH].splitlines()))

    assert len(rows) == 1
    row = rows[0]
    assert row["surface_name"] == "scheduler.load_data"
    assert row["status"] == "ACTIVE"
    assert row["active"] == "True"
    assert row["guarded_by_missing_hook_flag"] == "False"
    assert row["completion_surface_counted"] == "True"
    assert row["import_module"] == "utils.scheduler"
    assert row["imported_symbol"] == "scheduler"
    assert row["call_line"].isdigit()


def test_disabled_surface_csv_maps_p520j_and_p520i_missing_targets_to_false_guard():
    rendered = acceptance.render_artifacts()
    rows = list(csv.DictReader(rendered[acceptance.DISABLED_SURFACE_PATH].splitlines()))
    by_hook = {row["hook_name"]: row for row in rows}

    assert set(by_hook) == EXPECTED_DISABLED_HOOKS
    for hook_name, row in by_hook.items():
        assert row["status"] == "DISABLED", hook_name
        assert row["active"] == "False", hook_name
        assert row["guard_symbol"] == acceptance.DISABLED_FLAG, hook_name
        assert row["guard_value"] == "False", hook_name
        assert row["guard_line"].isdigit(), hook_name
        assert row["import_line"].isdigit(), hook_name
        assert row["call_line"].isdigit(), hook_name
        assert row["p520i_terminal_status"] == "UNRESOLVED", hook_name
        assert row["p520i_unresolved_reason"] == "source file missing", hook_name
        assert row["completion_surface_counted"] == "False", hook_name


def test_ingest_source_guard_scheduler_and_removed_symbols_are_static_only():
    source = acceptance.INGEST_ROUTE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(acceptance.INGEST_ROUTE_PATH))
    guard_assign, guard_value = acceptance._guard_assignment(tree)
    refresh_function = acceptance._refresh_function(tree)
    guard = acceptance._guard_node(refresh_function)
    parents = acceptance._parent_map(tree)
    scheduler_call = acceptance._find_call(refresh_function, "scheduler.load_data")

    assert guard_assign is not None
    assert guard_value is False
    assert guard is not None
    assert scheduler_call is not None
    assert guard not in acceptance._ancestors(scheduler_call, parents)
    for symbol in acceptance.REMOVED_DEAD_SYMBOLS:
        assert symbol not in source


def test_generated_artifacts_are_parseable_and_manifest_is_complete():
    rendered = acceptance.render_artifacts()
    result = json.loads(rendered[acceptance.RESULT_PATH])
    summary = json.loads(rendered[acceptance.COMPLETION_SUMMARY_PATH])
    active_rows = list(csv.DictReader(rendered[acceptance.ACTIVE_SURFACE_PATH].splitlines()))
    disabled_rows = list(csv.DictReader(rendered[acceptance.DISABLED_SURFACE_PATH].splitlines()))
    manifest_rows = list(csv.DictReader(rendered[acceptance.MANIFEST_PATH].splitlines()))

    assert result["artifact_prefix"] == acceptance.ARTIFACT_PREFIX
    assert result["acceptance_status"] == "PASS"
    assert summary["active_completion_surface"] == ["scheduler.load_data"]
    assert len(active_rows) == 1
    assert len(disabled_rows) == 3
    assert len(manifest_rows) == 6
    assert manifest_rows[-1]["sha256"] == ""


def test_rendered_artifacts_are_deterministic_across_runs():
    first = acceptance.render_artifacts()
    second = acceptance.render_artifacts()

    assert first == second


def test_generate_and_validate_artifacts_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(acceptance, "ARTIFACTS_DIR", tmp_path)
    monkeypatch.setattr(acceptance, "RESULT_PATH", tmp_path / "P520K_ingest_afterinsert_active_surface_acceptance_result.json")
    monkeypatch.setattr(acceptance, "ACTIVE_SURFACE_PATH", tmp_path / "P520K_ingest_afterinsert_active_surface_acceptance_active_surface.csv")
    monkeypatch.setattr(acceptance, "DISABLED_SURFACE_PATH", tmp_path / "P520K_ingest_afterinsert_active_surface_acceptance_disabled_surface.csv")
    monkeypatch.setattr(
        acceptance,
        "COMPLETION_SUMMARY_PATH",
        tmp_path / "P520K_ingest_afterinsert_active_surface_acceptance_completion_summary.json",
    )
    monkeypatch.setattr(acceptance, "STATUS_BLOCK_PATH", tmp_path / "P520K_ingest_afterinsert_active_surface_acceptance_status_block.md")
    monkeypatch.setattr(acceptance, "MANIFEST_PATH", tmp_path / "P520K_ingest_afterinsert_active_surface_acceptance_manifest.csv")

    rendered = acceptance.write_artifacts()
    ok, mismatches = acceptance.validate_artifacts(rendered)

    assert ok, mismatches
    assert set(rendered) == {
        tmp_path / "P520K_ingest_afterinsert_active_surface_acceptance_result.json",
        tmp_path / "P520K_ingest_afterinsert_active_surface_acceptance_active_surface.csv",
        tmp_path / "P520K_ingest_afterinsert_active_surface_acceptance_disabled_surface.csv",
        tmp_path / "P520K_ingest_afterinsert_active_surface_acceptance_completion_summary.json",
        tmp_path / "P520K_ingest_afterinsert_active_surface_acceptance_status_block.md",
        tmp_path / "P520K_ingest_afterinsert_active_surface_acceptance_manifest.csv",
    }


def test_cli_parser_exposes_required_p520k_flags():
    help_text = acceptance.build_parser().format_help()

    for flag in (
        "--generate",
        "--acceptance",
        "--active-surface",
        "--disabled-surface",
        "--completion-summary",
        "--status-block",
        "--validate",
        "--help",
    ):
        assert flag in help_text


def test_acceptance_module_does_not_import_runtime_or_db_modules():
    source = Path(acceptance.__file__).read_text(encoding="utf-8")
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
    assert "utils.scheduler" not in imported_modules
    assert "sqlite3" not in imported_modules
    assert "insert_draw" not in source
