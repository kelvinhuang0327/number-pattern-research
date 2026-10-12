"""
P518F tests for the predraw ledger verifier no-DB smoke harness.

All fixtures are synthetic and temporary. These tests do not open or write the
canonical DB, do not run migrations/backfills, do not deploy, are not production
release approval, and make no betting or future prediction claims.
"""
from __future__ import annotations

import json
from pathlib import Path

import tools.predraw_ledger_verify as verifier
import tools.predraw_ledger_verify_smoke as smoke


def test_smoke_cases_cover_required_verifier_behaviors():
    results = smoke.run_smoke_cases()
    by_id = {case["case_id"]: case for case in results["cases"]}

    assert by_id["valid_synthetic_ledger"]["actual_exit"] == verifier.EXIT_OK
    assert by_id["tampered_chain_invalid"]["actual_exit"] == verifier.EXIT_INVALID
    assert by_id["missing_ledger_path"]["actual_exit"] == verifier.EXIT_FILE_NOT_FOUND
    assert by_id["canonical_db_basename_refusal"]["actual_exit"] == verifier.EXIT_REFUSED_PATH
    assert by_id["no_db_invariant_evidence"]["status"] == "PASS"
    assert results["overall_status"] == "PASS"


def test_smoke_transcripts_show_expected_failure_modes():
    results = smoke.run_smoke_cases()
    transcripts = {item["case_id"]: item for item in results["transcripts"]}

    assert "validation_status=VALID" in transcripts["valid_synthetic_ledger"]["stdout"]
    assert "record_hash mismatch" in transcripts["tampered_chain_invalid"]["stdout"]
    assert "does not exist" in transcripts["missing_ledger_path"]["stderr"]
    assert "REFUSED" in transcripts["canonical_db_basename_refusal"]["stderr"]
    assert "predicted_numbers" not in transcripts["valid_synthetic_ledger"]["stdout"]


def test_rendered_artifacts_are_deterministic_across_runs():
    first = smoke.render_artifacts()
    second = smoke.render_artifacts()
    assert first == second


def test_generate_and_validate_artifacts_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(smoke, "ARTIFACTS_DIR", tmp_path)
    monkeypatch.setattr(smoke, "RESULTS_PATH", tmp_path / "P518F_predraw_ledger_verify_smoke_results.json")
    monkeypatch.setattr(smoke, "CASES_PATH", tmp_path / "P518F_predraw_ledger_verify_smoke_cases.csv")
    monkeypatch.setattr(smoke, "TRANSCRIPTS_PATH", tmp_path / "P518F_predraw_ledger_verify_smoke_transcripts.json")
    monkeypatch.setattr(smoke, "REPORT_PATH", tmp_path / "P518F_predraw_ledger_verify_smoke_report.md")
    monkeypatch.setattr(smoke, "MANIFEST_PATH", tmp_path / "P518F_predraw_ledger_verify_smoke_manifest.csv")

    rendered = smoke.write_artifacts()
    ok, mismatches = smoke.validate_artifacts(rendered)

    assert ok, mismatches
    assert set(rendered) == {
        tmp_path / "P518F_predraw_ledger_verify_smoke_results.json",
        tmp_path / "P518F_predraw_ledger_verify_smoke_cases.csv",
        tmp_path / "P518F_predraw_ledger_verify_smoke_transcripts.json",
        tmp_path / "P518F_predraw_ledger_verify_smoke_report.md",
        tmp_path / "P518F_predraw_ledger_verify_smoke_manifest.csv",
    }


def test_artifacts_contain_required_safety_notices():
    rendered = smoke.render_artifacts()
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


def test_results_json_records_no_db_invariant_without_canonical_db_input():
    rendered = smoke.render_artifacts()
    results = json.loads(rendered[smoke.RESULTS_PATH])
    evidence = results["no_db_evidence"]
    canonical_db = Path(evidence["canonical_db_path"])

    assert canonical_db == smoke._PROJECT_ROOT / "data" / "lottery_v2.db"
    assert evidence["canonical_db_opened"] is False
    assert evidence["canonical_db_written"] is False
    assert evidence["migration_backfill_deploy_run"] is False
    assert evidence["canonical_db_exists_before"] == evidence["canonical_db_exists_after"]
    assert str(canonical_db) not in rendered[smoke.TRANSCRIPTS_PATH]
