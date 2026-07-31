"""P520E tests for the ingest after-insert live hook target audit.

The auditor parses source and prior artifacts only. These tests do not import
lottery_api.routes.ingest, do not import live hook target modules, do not
execute hooks or draw inserts, do not open or write a database, do not run
migrations/backfills, and do not deploy.
"""
from __future__ import annotations

import ast
import csv
import json
from pathlib import Path

import tools.ingest_afterinsert_hook_target_audit as audit


def test_target_audit_reports_current_live_hook_targets_without_failures():
    result = audit.build_target_audit_bundle()["result"]

    assert result["final_status"] == "WARN"
    assert result["refresh_after_insert_present"] is True
    assert result["target_audit_row_count"] == len(audit.EXPECTED_HOOKS)
    assert result["resolved_source_count"] == 1
    assert result["unresolved_source_count"] == 3
    assert result["target_symbol_found_count"] == 1
    assert result["db_indicator_count"] == 0
    assert result["file_indicator_count"] > 0
    assert result["runtime_indicator_count"] > 0
    assert result["pass_count"] == 0
    assert result["warn_count"] == len(audit.EXPECTED_HOOKS)
    assert result["fail_count"] == 0
    assert result["component_statuses"]["runtime import avoided"] == "PASS"
    assert result["component_statuses"]["DB side effects avoided"] == "PASS"


def test_target_audit_matrix_contains_expected_target_evidence():
    rendered = audit.render_artifacts()
    rows = list(csv.DictReader(rendered[audit.TARGET_AUDIT_PATH].splitlines()))
    by_hook = {row["hook_reference"]: row for row in rows}

    assert set(by_hook) == {spec.hook_reference for spec in audit.EXPECTED_HOOKS}

    scheduler = by_hook["scheduler.load_data"]
    assert scheduler["found_in_p520d_contract"] == "True"
    assert scheduler["p520d_contract_status"] == "PASS"
    assert scheduler["source_path"] == "lottery_api/utils/scheduler.py"
    assert scheduler["source_path_resolved"] == "True"
    assert scheduler["target_symbol_found"] == "True"
    assert scheduler["ast_node_type"] == "FunctionDef"
    assert scheduler["function_class_presence"] == "instance_assign+class_method"
    assert scheduler["call_signature_hints"] == "load_data(self)"
    assert "open(" in scheduler["file_output_indicators"]
    assert "AsyncIOScheduler" in scheduler["runtime_side_effect_indicators"]
    assert scheduler["target_audit_status"] == "WARN"

    for hook in ("refresh_hedge_fund_outputs", "weight_adjuster", "learning_integrator"):
        row = by_hook[hook]
        assert row["found_in_p520d_contract"] == "True"
        assert row["source_path_resolved"] == "False"
        assert row["target_symbol_found"] == "False"
        assert row["function_class_presence"] == "unresolved"
        assert row["target_audit_status"] == "WARN"
        assert "runtime import not attempted" in row["notes"]


def test_risk_indicator_csv_is_source_only_and_specific_to_resolved_target():
    rendered = audit.render_artifacts()
    rows = list(csv.DictReader(rendered[audit.RISK_INDICATORS_PATH].splitlines()))

    assert rows
    assert {row["hook_reference"] for row in rows} == {"scheduler.load_data"}
    assert {row["source_path"] for row in rows} == {"lottery_api/utils/scheduler.py"}
    assert any(row["indicator_category"] == "file_output" and row["indicator"] == "json.dump" for row in rows)
    assert any(
        row["indicator_category"] == "runtime_side_effect"
        and row["indicator"] == "top_level_call_assignment"
        and "scheduler = AutoLearningScheduler()" in row["evidence"]
        for row in rows
    )
    assert not any(row["indicator_category"] == "db_touch" for row in rows)


def test_unresolved_csv_lists_targets_that_require_runtime_import_to_resolve():
    rendered = audit.render_artifacts()
    rows = list(csv.DictReader(rendered[audit.UNRESOLVED_PATH].splitlines()))
    by_hook = {row["hook_reference"]: row for row in rows}

    assert set(by_hook) == {"refresh_hedge_fund_outputs", "weight_adjuster", "learning_integrator"}
    assert by_hook["refresh_hedge_fund_outputs"]["import_module"] == "analysis.payout.sync"
    assert by_hook["weight_adjuster"]["import_module"] == "engine.weight_adjuster"
    assert by_hook["learning_integrator"]["import_module"] == "engine.learning_integrator"
    for row in rows:
        assert row["reason"] == "source_path_unresolved"
        assert row["status"] == "WARN"
        assert "runtime import not attempted" in row["notes"]


def test_result_reads_p520d_artifact_summary_as_prior_evidence():
    result = audit.build_target_audit_bundle()["result"]
    summary = result["p520d_summary"]

    assert summary["result_present"] is True
    assert summary["final_status"] == "WARN"
    assert summary["expected_live_hooks"] == [spec.hook_reference for spec in audit.EXPECTED_HOOKS]
    assert summary["matrix_rows"] == len(audit.EXPECTED_HOOKS)
    assert summary["target_resolution_rows"] == len(audit.EXPECTED_HOOKS)


def test_status_block_is_copy_paste_friendly_and_scoped():
    block = audit.build_target_audit_bundle()["status_block"]

    assert "Final status: `WARN`" in block
    assert "Unresolved source count: `3`" in block
    assert "DB indicator count: `0`" in block
    assert "PASS/WARN/FAIL counts: `0/4/0`" in block
    for notice in audit.NOTICE_LINES:
        assert notice in block


def test_rendered_artifacts_are_deterministic_across_runs():
    first = audit.render_artifacts()
    second = audit.render_artifacts()
    assert first == second


def test_generate_and_validate_artifacts_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "ARTIFACTS_DIR", tmp_path)
    monkeypatch.setattr(audit, "RESULT_PATH", tmp_path / "P520E_ingest_afterinsert_hook_target_audit_result.json")
    monkeypatch.setattr(audit, "TARGET_AUDIT_PATH", tmp_path / "P520E_ingest_afterinsert_hook_target_audit_matrix.csv")
    monkeypatch.setattr(
        audit,
        "RISK_INDICATORS_PATH",
        tmp_path / "P520E_ingest_afterinsert_hook_target_audit_risk_indicators.csv",
    )
    monkeypatch.setattr(audit, "UNRESOLVED_PATH", tmp_path / "P520E_ingest_afterinsert_hook_target_audit_unresolved.csv")
    monkeypatch.setattr(
        audit,
        "STATUS_BLOCK_PATH",
        tmp_path / "P520E_ingest_afterinsert_hook_target_audit_status_block.md",
    )
    monkeypatch.setattr(audit, "MANIFEST_PATH", tmp_path / "P520E_ingest_afterinsert_hook_target_audit_manifest.csv")

    rendered = audit.write_artifacts()
    ok, mismatches = audit.validate_artifacts(rendered)

    assert ok, mismatches
    assert set(rendered) == {
        tmp_path / "P520E_ingest_afterinsert_hook_target_audit_result.json",
        tmp_path / "P520E_ingest_afterinsert_hook_target_audit_matrix.csv",
        tmp_path / "P520E_ingest_afterinsert_hook_target_audit_risk_indicators.csv",
        tmp_path / "P520E_ingest_afterinsert_hook_target_audit_unresolved.csv",
        tmp_path / "P520E_ingest_afterinsert_hook_target_audit_status_block.md",
        tmp_path / "P520E_ingest_afterinsert_hook_target_audit_manifest.csv",
    }


def test_cli_parser_exposes_required_p520e_flags():
    help_text = audit.build_parser().format_help()

    for flag in (
        "--generate",
        "--target-audit",
        "--risk-indicators",
        "--unresolved",
        "--status-block",
        "--validate",
        "--help",
    ):
        assert flag in help_text


def test_target_audit_module_does_not_import_ingest_route_or_live_targets():
    source = Path(audit.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)

    assert "lottery_api.routes.ingest" not in imported_modules
    assert "lottery_api.routes" not in imported_modules
    assert "utils.scheduler" not in imported_modules
    assert "analysis.payout.sync" not in imported_modules
    assert "engine.weight_adjuster" not in imported_modules
    assert "engine.learning_integrator" not in imported_modules
    assert "sqlite3" not in imported_modules
    assert "insert_draw" not in source


def test_generated_json_and_manifest_are_parseable():
    rendered = audit.render_artifacts()
    result = json.loads(rendered[audit.RESULT_PATH])
    manifest_rows = list(csv.DictReader(rendered[audit.MANIFEST_PATH].splitlines()))

    assert result["final_status"] == "WARN"
    assert result["failure_count"] == 0
    assert len(manifest_rows) == 6
    assert manifest_rows[-1]["sha256"] == ""
