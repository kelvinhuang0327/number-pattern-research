"""P520G tests for unresolved ingest hook candidate triage.

The triage tool reads committed artifacts and parses source only. These tests
do not import lottery_api.routes.ingest, do not import live hook target modules,
do not execute hooks or draw inserts, do not open or write a database, do not
run migrations/backfills, and do not deploy.
"""
from __future__ import annotations

import ast
import csv
import json
from pathlib import Path

import tools.ingest_afterinsert_hook_candidate_triage as triage


EXPECTED_HOOKS = {
    "refresh_hedge_fund_outputs",
    "weight_adjuster",
    "learning_integrator",
}


def test_triage_reads_p520f_candidates_and_keeps_conservative_status():
    result = triage.build_triage_bundle()["result"]

    assert result["final_status"] == "WARN"
    assert set(result["unresolved_hooks"]) == EXPECTED_HOOKS
    assert result["candidate_count"] == 145
    assert result["medium_candidate_count"] == 6
    assert result["low_candidate_count"] == 139
    assert result["confirmed_hook_count"] == 0
    assert result["probable_upgrade_count"] == 3
    assert result["component_statuses"]["runtime import avoided"] == "PASS"
    assert result["component_statuses"]["DB side effects avoided"] == "PASS"
    assert result["component_statuses"]["target confirmation conservative"] == "PASS"
    assert result["p520f_summary"]["confidence_counts"] == {"HIGH": 0, "MEDIUM": 6, "LOW": 139}


def test_medium_cards_cover_only_p520f_medium_candidates_with_required_fields():
    rendered = triage.render_artifacts()
    cards = json.loads(rendered[triage.MEDIUM_CARDS_PATH])

    assert len(cards) == 6
    assert {card["unresolved_hook_name"] for card in cards} == EXPECTED_HOOKS
    assert {card["candidate_confidence"] for card in cards} == {"MEDIUM"}
    assert {card["candidate_file_path"] for card in cards} == {"lottery_api/routes/ingest.py"}
    for card in cards:
        assert set(triage.MEDIUM_CARD_FIELDS).issubset(card)
        assert card["line_number"].isdigit()
        assert card["ast_node_type"] in {"ImportFrom", "Call"}
        assert card["matched_symbol_reference"]
        assert card["supporting_source_snippet"]
        assert len(card["supporting_source_snippet"]) <= 180
        assert "remains source-unresolved" not in card["why_it_may_match"]
        assert "target implementation evidence" in card["why_it_remains_unconfirmed"]
        assert card["recommended_next_action"] == "runtime-instrumentation-required"


def test_by_hook_recommendation_marks_probable_but_not_confirmed():
    rendered = triage.render_artifacts()
    rows = list(csv.DictReader(rendered[triage.BY_HOOK_PATH].splitlines()))
    by_hook = {row["unresolved_hook_name"]: row for row in rows}

    assert set(by_hook) == EXPECTED_HOOKS
    for hook, row in by_hook.items():
        assert row["medium_candidate_count"] == "2", hook
        assert row["remaining_unresolved_count"] == "1"
        assert row["probable_upgrade"] == "probable"
        assert row["confirmed"] == "False"
        assert row["recommendation"] == "runtime-instrumentation-required"
        assert "target implementation remains source-unresolved" in row["probable_upgrade_reason"]


def test_low_summary_is_by_hook_context_not_expanded_cards():
    rendered = triage.render_artifacts()
    rows = list(csv.DictReader(rendered[triage.LOW_SUMMARY_PATH].splitlines()))
    by_hook = {row["unresolved_hook_name"]: row for row in rows}

    assert set(by_hook) == EXPECTED_HOOKS
    assert by_hook["learning_integrator"]["low_candidate_count"] == "17"
    assert by_hook["refresh_hedge_fund_outputs"]["low_candidate_count"] == "57"
    assert by_hook["weight_adjuster"]["low_candidate_count"] == "65"
    for row in rows:
        assert int(row["source_path_count"]) > 0
        assert row["evidence_kinds"]
        assert "do not confirm the hook target" in row["summary"]


def test_status_block_is_copy_paste_friendly_and_scoped():
    block = triage.build_triage_bundle()["status_block"]

    assert "Final status: `WARN`" in block
    assert "MEDIUM evidence card count: `6`" in block
    assert "LOW summary count: `139`" in block
    assert "Confirmed hook count: `0`" in block
    for notice in triage.NOTICE_LINES:
        assert notice in block


def test_rendered_artifacts_are_deterministic_across_runs():
    first = triage.render_artifacts()
    second = triage.render_artifacts()
    assert first == second


def test_generate_and_validate_artifacts_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(triage, "ARTIFACTS_DIR", tmp_path)
    monkeypatch.setattr(triage, "RESULT_PATH", tmp_path / "P520G_ingest_afterinsert_hook_candidate_triage_result.json")
    monkeypatch.setattr(
        triage,
        "MEDIUM_CARDS_PATH",
        tmp_path / "P520G_ingest_afterinsert_hook_candidate_triage_medium_cards.json",
    )
    monkeypatch.setattr(triage, "BY_HOOK_PATH", tmp_path / "P520G_ingest_afterinsert_hook_candidate_triage_by_hook.csv")
    monkeypatch.setattr(
        triage,
        "LOW_SUMMARY_PATH",
        tmp_path / "P520G_ingest_afterinsert_hook_candidate_triage_low_summary.csv",
    )
    monkeypatch.setattr(
        triage,
        "STATUS_BLOCK_PATH",
        tmp_path / "P520G_ingest_afterinsert_hook_candidate_triage_status_block.md",
    )
    monkeypatch.setattr(triage, "MANIFEST_PATH", tmp_path / "P520G_ingest_afterinsert_hook_candidate_triage_manifest.csv")

    rendered = triage.write_artifacts()
    ok, mismatches = triage.validate_artifacts(rendered)

    assert ok, mismatches
    assert set(rendered) == {
        tmp_path / "P520G_ingest_afterinsert_hook_candidate_triage_result.json",
        tmp_path / "P520G_ingest_afterinsert_hook_candidate_triage_medium_cards.json",
        tmp_path / "P520G_ingest_afterinsert_hook_candidate_triage_by_hook.csv",
        tmp_path / "P520G_ingest_afterinsert_hook_candidate_triage_low_summary.csv",
        tmp_path / "P520G_ingest_afterinsert_hook_candidate_triage_status_block.md",
        tmp_path / "P520G_ingest_afterinsert_hook_candidate_triage_manifest.csv",
    }


def test_cli_parser_exposes_required_p520g_flags():
    help_text = triage.build_parser().format_help()

    for flag in (
        "--generate",
        "--triage",
        "--medium-cards",
        "--by-hook",
        "--low-summary",
        "--status-block",
        "--validate",
        "--help",
    ):
        assert flag in help_text


def test_triage_module_does_not_import_ingest_route_or_live_targets():
    source = Path(triage.__file__).read_text(encoding="utf-8")
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
    rendered = triage.render_artifacts()
    result = json.loads(rendered[triage.RESULT_PATH])
    cards = json.loads(rendered[triage.MEDIUM_CARDS_PATH])
    manifest_rows = list(csv.DictReader(rendered[triage.MANIFEST_PATH].splitlines()))

    assert result["final_status"] == "WARN"
    assert result["failure_count"] == 0
    assert len(cards) == 6
    assert len(manifest_rows) == 6
    assert manifest_rows[-1]["sha256"] == ""
