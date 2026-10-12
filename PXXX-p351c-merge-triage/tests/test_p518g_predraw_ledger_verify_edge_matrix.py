"""
P518G tests for the predraw ledger verifier no-DB edge matrix.

All fixtures are synthetic and temporary. These tests do not open or write the
canonical DB, do not run migrations/backfills, do not deploy, are not production
release approval, and make no betting or future prediction claims.
"""
from __future__ import annotations

import json
from pathlib import Path

import tools.predraw_ledger_verify as verifier
import tools.predraw_ledger_verify_smoke as smoke


def test_edge_matrix_covers_required_verifier_behaviors():
    results = smoke.run_edge_matrix_cases()
    by_id = {case["case_id"]: case for case in results["cases"]}

    assert by_id["malformed_jsonl_row"]["actual_exit"] == verifier.EXIT_INVALID
    assert by_id["empty_ledger_file"]["actual_exit"] == verifier.EXIT_OK
    assert by_id["missing_required_field"]["actual_exit"] == verifier.EXIT_INVALID
    assert by_id["duplicate_draw_record_supported"]["actual_exit"] == verifier.EXIT_OK
    assert by_id["wrong_game_identifier_supported"]["actual_exit"] == verifier.EXIT_OK
    assert by_id["prev_hash_mismatch_chain_invalid"]["actual_exit"] == verifier.EXIT_INVALID
    assert by_id["no_db_invariant_evidence"]["status"] == "PASS"
    assert results["overall_status"] == "PASS"


def test_edge_transcripts_show_distinct_failure_modes_and_supported_behaviors():
    results = smoke.run_edge_matrix_cases()
    transcripts = {item["case_id"]: item for item in results["transcripts"]}

    assert "unparseable/truncated" in transcripts["malformed_jsonl_row"]["stdout"]
    assert "record_count=0" in transcripts["empty_ledger_file"]["stdout"]
    assert "strategy_id" in transcripts["missing_required_field"]["stdout"]
    assert "validation_status=VALID" in transcripts["duplicate_draw_record_supported"]["stdout"]
    assert "lottery_type=MYSTERY_LOTTO" in transcripts["wrong_game_identifier_supported"]["stdout"]
    assert "prev_record_hash mismatch" in transcripts["prev_hash_mismatch_chain_invalid"]["stdout"]
    assert "predicted_numbers" not in transcripts["duplicate_draw_record_supported"]["stdout"]


def test_edge_coverage_records_all_requested_edge_categories():
    results = smoke.run_edge_matrix_cases()
    requirements = {row["requirement"] for row in results["coverage"]}

    assert {
        "malformed JSONL row",
        "empty ledger file",
        "missing required field",
        "duplicate draw record if supported by verifier behavior",
        "wrong game identifier if supported by verifier behavior",
        "inconsistent hash chain beyond existing tampered case",
        "DB side-effect invariant",
    } == requirements
    assert all(row["covered"] is True for row in results["coverage"])
    assert all(row["verifier_semantic_change_required"] is False for row in results["coverage"])


def test_edge_artifacts_are_deterministic_across_runs():
    first = smoke.render_edge_artifacts()
    second = smoke.render_edge_artifacts()
    assert first == second


def test_generate_and_validate_edge_artifacts_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(smoke, "ARTIFACTS_DIR", tmp_path)
    monkeypatch.setattr(smoke, "EDGE_RESULTS_PATH", tmp_path / "P518G_predraw_ledger_verify_edge_matrix_results.json")
    monkeypatch.setattr(smoke, "EDGE_CASES_PATH", tmp_path / "P518G_predraw_ledger_verify_edge_matrix_cases.csv")
    monkeypatch.setattr(
        smoke,
        "EDGE_TRANSCRIPTS_PATH",
        tmp_path / "P518G_predraw_ledger_verify_edge_matrix_transcripts.json",
    )
    monkeypatch.setattr(smoke, "EDGE_COVERAGE_PATH", tmp_path / "P518G_predraw_ledger_verify_edge_matrix_coverage.csv")
    monkeypatch.setattr(smoke, "EDGE_REPORT_PATH", tmp_path / "P518G_predraw_ledger_verify_edge_matrix_report.md")
    monkeypatch.setattr(smoke, "EDGE_MANIFEST_PATH", tmp_path / "P518G_predraw_ledger_verify_edge_matrix_manifest.csv")

    rendered = smoke.write_edge_artifacts()
    ok, mismatches = smoke.validate_edge_artifacts(rendered)

    assert ok, mismatches
    assert set(rendered) == {
        tmp_path / "P518G_predraw_ledger_verify_edge_matrix_results.json",
        tmp_path / "P518G_predraw_ledger_verify_edge_matrix_cases.csv",
        tmp_path / "P518G_predraw_ledger_verify_edge_matrix_transcripts.json",
        tmp_path / "P518G_predraw_ledger_verify_edge_matrix_coverage.csv",
        tmp_path / "P518G_predraw_ledger_verify_edge_matrix_report.md",
        tmp_path / "P518G_predraw_ledger_verify_edge_matrix_manifest.csv",
    }


def test_edge_artifacts_contain_required_safety_notices_and_no_db_invariant():
    rendered = smoke.render_edge_artifacts()
    required = (
        "no canonical DB open/write",
        "no migration/backfill",
        "no deploy",
        "synthetic fixtures only",
        "not production release approval",
        "no betting/future prediction claims",
    )
    combined = "\n".join(rendered.values())
    for notice in required:
        assert notice in combined

    results = json.loads(rendered[smoke.EDGE_RESULTS_PATH])
    evidence = results["no_db_evidence"]
    canonical_db = Path(evidence["canonical_db_path"])

    assert canonical_db == smoke._PROJECT_ROOT / "data" / "lottery_v2.db"
    assert evidence["canonical_db_opened"] is False
    assert evidence["canonical_db_written"] is False
    assert evidence["migration_backfill_deploy_run"] is False
    assert evidence["canonical_db_exists_before"] == evidence["canonical_db_exists_after"]
    assert str(canonical_db) not in rendered[smoke.EDGE_TRANSCRIPTS_PATH]


def test_cli_parser_exposes_p518g_edge_flags():
    help_text = smoke.build_parser().format_help()

    for flag in (
        "--generate",
        "--edge-cases",
        "--edge-transcripts",
        "--edge-coverage",
        "--edge-report",
        "--validate",
    ):
        assert flag in help_text
