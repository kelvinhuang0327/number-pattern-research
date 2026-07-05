"""
P518H tests for the predraw ledger verifier no-DB acceptance bundle.

The acceptance bundle reads committed P518F/P518G artifacts only. These tests do
not open or write the canonical DB, do not run migrations/backfills, do not
deploy, are not production release approval, and make no betting or future
prediction claims.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import tools.predraw_ledger_verify_acceptance as acceptance


def test_acceptance_decision_passes_from_committed_p518f_p518g_artifacts():
    bundle = acceptance.build_acceptance()
    decision = bundle["decision"]

    assert decision["source_evidence"]["P518F_smoke_status"] == "PASS"
    assert decision["source_evidence"]["P518G_edge_matrix_status"] == "PASS"
    assert decision["canonical_db_refusal_evidence"]["status"] == "PASS"
    assert decision["final_status"] == "PASS"
    assert decision["case_summary"]["failed_cases"] == []
    assert decision["case_summary"]["missing_artifacts"] == []


def test_case_summary_includes_smoke_and_edge_cases():
    rendered = acceptance.render_artifacts()
    rows = list(csv.DictReader(rendered[acceptance.CASE_SUMMARY_PATH].splitlines()))
    by_case = {(row["source"], row["case_id"]): row for row in rows}

    assert by_case[("P518F_smoke", "valid_synthetic_ledger")]["status"] == "PASS"
    assert by_case[("P518F_smoke", "canonical_db_basename_refusal")]["actual_exit"] == "3"
    assert by_case[("P518G_edge_matrix", "malformed_jsonl_row")]["status"] == "PASS"
    assert by_case[("P518G_edge_matrix", "prev_hash_mismatch_chain_invalid")]["status"] == "PASS"


def test_failure_matrix_and_db_invariant_record_no_db_guards():
    rendered = acceptance.render_artifacts()
    failure_rows = list(csv.DictReader(rendered[acceptance.FAILURE_MATRIX_PATH].splitlines()))
    db_invariant = json.loads(rendered[acceptance.DB_INVARIANT_PATH])

    assert {row["check_id"] for row in failure_rows} >= {
        "canonical_db_refusal",
        "db_invariant_P518F_smoke",
        "db_invariant_P518G_edge_matrix",
        "db_invariant_P518H_acceptance",
    }
    assert db_invariant["status"] == "PASS"
    for check in db_invariant["checks"]:
        assert check["canonical_db_opened"] is False
        assert check["canonical_db_written"] is False
        assert check["migration_backfill_deploy_run"] is False


def test_artifacts_are_deterministic_across_runs():
    first = acceptance.render_artifacts()
    second = acceptance.render_artifacts()
    assert first == second


def test_generate_and_validate_artifacts_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(acceptance, "ARTIFACTS_DIR", tmp_path)
    monkeypatch.setattr(acceptance, "DECISION_PATH", tmp_path / "P518H_predraw_ledger_verify_acceptance_decision.json")
    monkeypatch.setattr(
        acceptance,
        "CASE_SUMMARY_PATH",
        tmp_path / "P518H_predraw_ledger_verify_acceptance_case_summary.csv",
    )
    monkeypatch.setattr(
        acceptance,
        "FAILURE_MATRIX_PATH",
        tmp_path / "P518H_predraw_ledger_verify_acceptance_failure_matrix.csv",
    )
    monkeypatch.setattr(
        acceptance,
        "DB_INVARIANT_PATH",
        tmp_path / "P518H_predraw_ledger_verify_acceptance_db_invariant.json",
    )
    monkeypatch.setattr(acceptance, "REPORT_PATH", tmp_path / "P518H_predraw_ledger_verify_acceptance_report.md")
    monkeypatch.setattr(acceptance, "MANIFEST_PATH", tmp_path / "P518H_predraw_ledger_verify_acceptance_manifest.csv")

    rendered = acceptance.write_artifacts()
    ok, mismatches = acceptance.validate_artifacts(rendered)

    assert ok, mismatches
    assert set(rendered) == {
        tmp_path / "P518H_predraw_ledger_verify_acceptance_decision.json",
        tmp_path / "P518H_predraw_ledger_verify_acceptance_case_summary.csv",
        tmp_path / "P518H_predraw_ledger_verify_acceptance_failure_matrix.csv",
        tmp_path / "P518H_predraw_ledger_verify_acceptance_db_invariant.json",
        tmp_path / "P518H_predraw_ledger_verify_acceptance_report.md",
        tmp_path / "P518H_predraw_ledger_verify_acceptance_manifest.csv",
    }


def test_artifacts_contain_required_safety_notices():
    rendered = acceptance.render_artifacts()
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


def test_cli_parser_exposes_required_p518h_flags():
    help_text = acceptance.build_parser().format_help()

    for flag in (
        "--generate",
        "--decision",
        "--case-summary",
        "--failure-matrix",
        "--db-invariant",
        "--report",
        "--validate",
        "--help",
    ):
        assert flag in help_text


def test_acceptance_module_does_not_import_verifier_or_smoke_harness():
    source = Path(acceptance.__file__).read_text(encoding="utf-8")

    assert "import tools.predraw_ledger_verify" not in source
    assert "import tools.predraw_ledger_verify_smoke" not in source
    assert "from tools import predraw_ledger_verify_smoke" not in source
