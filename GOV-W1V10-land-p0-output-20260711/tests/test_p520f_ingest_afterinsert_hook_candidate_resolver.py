"""P520F tests for the unresolved ingest hook static candidate resolver.

The resolver reads artifacts and parses Python source only. These tests do not
import lottery_api.routes.ingest, do not import live hook target modules, do not
execute hooks or draw inserts, do not open or write a database, do not run
migrations/backfills, and do not deploy.
"""
from __future__ import annotations

import ast
import csv
import json
from pathlib import Path

import tools.ingest_afterinsert_hook_candidate_resolver as resolver


EXPECTED_UNRESOLVED = set()


def test_candidate_resolver_reads_p520e_unresolved_hooks_without_failures():
    result = resolver.build_candidate_resolver_bundle()["result"]

    assert result["final_status"] == "WARN"
    assert set(result["unresolved_hooks"]) == EXPECTED_UNRESOLVED
    assert result["unresolved_hook_count"] == 0
    assert result["candidate_count"] == 0
    assert result["reference_count"] == 0
    assert result["failure_count"] == 0
    assert result["component_statuses"]["runtime import avoided"] == "PASS"
    assert result["component_statuses"]["DB side effects avoided"] == "PASS"
    assert result["component_statuses"]["target confirmation conservative"] == "PASS"
    assert result["p520e_summary"]["final_status"] == "WARN"


def test_candidates_are_empty_after_missing_hooks_are_removed():
    rendered = resolver.render_artifacts()
    rows = list(csv.DictReader(rendered[resolver.CANDIDATES_PATH].splitlines()))

    assert rows == []


def test_removed_weight_adjuster_no_longer_has_candidate_rows():
    rendered = resolver.render_artifacts()
    rows = list(csv.DictReader(rendered[resolver.CANDIDATES_PATH].splitlines()))
    weight_rows = [row for row in rows if row["hook_reference"] == "weight_adjuster"]

    assert weight_rows == []


def test_reference_inventory_is_empty_after_missing_hooks_are_removed():
    rendered = resolver.render_artifacts()
    rows = list(csv.DictReader(rendered[resolver.REFERENCES_PATH].splitlines()))

    assert rows == []


def test_confidence_summary_is_warn_and_conservative():
    rendered = resolver.render_artifacts()
    summary = json.loads(rendered[resolver.CONFIDENCE_SUMMARY_PATH])

    assert summary["final_status"] == "WARN"
    assert set(summary["candidate_count_by_hook"]) == EXPECTED_UNRESOLVED
    assert set(summary["target_confirmed_by_hook"]) == EXPECTED_UNRESOLVED
    assert not any(summary["target_confirmed_by_hook"].values())
    assert set(summary["no_high_confidence_hooks"]) == EXPECTED_UNRESOLVED
    assert summary["confidence_counts"] == {"HIGH": 0, "MEDIUM": 0, "LOW": 0}


def test_status_block_is_copy_paste_friendly_and_scoped():
    block = resolver.build_candidate_resolver_bundle()["status_block"]

    assert "Final status: `WARN`" in block
    assert "Unresolved hook count: `0`" in block
    assert "no unresolved hooks found in P520E artifacts" in block
    for notice in resolver.NOTICE_LINES:
        assert notice in block


def test_rendered_artifacts_are_deterministic_across_runs():
    first = resolver.render_artifacts()
    second = resolver.render_artifacts()
    assert first == second


def test_generate_and_validate_artifacts_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(resolver, "ARTIFACTS_DIR", tmp_path)
    monkeypatch.setattr(resolver, "RESULT_PATH", tmp_path / "P520F_ingest_afterinsert_hook_candidate_resolver_result.json")
    monkeypatch.setattr(resolver, "CANDIDATES_PATH", tmp_path / "P520F_ingest_afterinsert_hook_candidate_resolver_candidates.csv")
    monkeypatch.setattr(resolver, "REFERENCES_PATH", tmp_path / "P520F_ingest_afterinsert_hook_candidate_resolver_references.csv")
    monkeypatch.setattr(
        resolver,
        "CONFIDENCE_SUMMARY_PATH",
        tmp_path / "P520F_ingest_afterinsert_hook_candidate_resolver_confidence_summary.json",
    )
    monkeypatch.setattr(
        resolver,
        "STATUS_BLOCK_PATH",
        tmp_path / "P520F_ingest_afterinsert_hook_candidate_resolver_status_block.md",
    )
    monkeypatch.setattr(resolver, "MANIFEST_PATH", tmp_path / "P520F_ingest_afterinsert_hook_candidate_resolver_manifest.csv")

    rendered = resolver.write_artifacts()
    ok, mismatches = resolver.validate_artifacts(rendered)

    assert ok, mismatches
    assert set(rendered) == {
        tmp_path / "P520F_ingest_afterinsert_hook_candidate_resolver_result.json",
        tmp_path / "P520F_ingest_afterinsert_hook_candidate_resolver_candidates.csv",
        tmp_path / "P520F_ingest_afterinsert_hook_candidate_resolver_references.csv",
        tmp_path / "P520F_ingest_afterinsert_hook_candidate_resolver_confidence_summary.json",
        tmp_path / "P520F_ingest_afterinsert_hook_candidate_resolver_status_block.md",
        tmp_path / "P520F_ingest_afterinsert_hook_candidate_resolver_manifest.csv",
    }


def test_cli_parser_exposes_required_p520f_flags():
    help_text = resolver.build_parser().format_help()

    for flag in (
        "--generate",
        "--candidates",
        "--references",
        "--confidence-summary",
        "--status-block",
        "--validate",
        "--help",
    ):
        assert flag in help_text


def test_candidate_resolver_module_does_not_import_ingest_route_or_live_targets():
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
    summary = json.loads(rendered[resolver.CONFIDENCE_SUMMARY_PATH])
    manifest_rows = list(csv.DictReader(rendered[resolver.MANIFEST_PATH].splitlines()))

    assert result["final_status"] == "WARN"
    assert result["failure_count"] == 0
    assert summary["final_status"] == "WARN"
    assert len(manifest_rows) == 6
    assert manifest_rows[-1]["sha256"] == ""
