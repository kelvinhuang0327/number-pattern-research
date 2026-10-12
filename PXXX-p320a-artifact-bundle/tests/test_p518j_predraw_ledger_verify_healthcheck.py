"""
P518J tests for the predraw ledger verifier no-DB healthcheck runner.

The healthcheck runner reads committed P518I/P518H/P518F/P518G artifacts only.
These tests do not open or write the canonical DB, do not run
migrations/backfills, do not deploy, are not production release approval, and
make no betting or future prediction claims.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import tools.predraw_ledger_verify_healthcheck as healthcheck


def test_healthcheck_result_compacts_mainline_evidence_stack():
    result = healthcheck.build_healthcheck_bundle()["health"]

    assert result["final_verifier_health"] == "PASS"
    assert result["p518i_compact_status"] == "PASS"
    assert result["p518h_acceptance_decision"] == "PASS"
    assert result["p518f_smoke_status"] == "PASS"
    assert result["p518g_edge_matrix_status"] == "PASS"
    assert result["db_invariant_status"] == "PASS"
    assert result["canonical_db_refusal_status"] == "PASS"
    assert result["missing_artifact_count"] == 0
    assert result["failed_count"] == 0
    assert result["warning_count"] == 0
    assert result["suggested_next_command"] == "python3 -m tools.predraw_ledger_verify_healthcheck --status-block"


def test_artifact_inventory_lists_p518i_p518h_p518f_p518g_artifacts():
    rendered = healthcheck.render_artifacts()
    rows = list(csv.DictReader(rendered[healthcheck.ARTIFACT_INVENTORY_PATH].splitlines()))
    by_path = {row["artifact_path"]: row for row in rows}

    assert len(rows) == len(healthcheck.EXPECTED_SOURCE_ARTIFACTS)
    assert by_path["artifacts/P518I_predraw_ledger_verify_status_summary.json"]["exists"] == "True"
    assert by_path["artifacts/P518H_predraw_ledger_verify_acceptance_decision.json"]["exists"] == "True"
    assert by_path["artifacts/P518F_predraw_ledger_verify_smoke_results.json"]["exists"] == "True"
    assert by_path["artifacts/P518G_predraw_ledger_verify_edge_matrix_results.json"]["exists"] == "True"
    assert all(row["sha256"] for row in rows)
    assert all(row["required_for_health"] == "True" for row in rows)


def test_command_matrix_marks_artifact_only_and_generating_commands():
    rendered = healthcheck.render_artifacts()
    rows = list(csv.DictReader(rendered[healthcheck.COMMAND_MATRIX_PATH].splitlines()))
    by_id = {row["command_id"]: row for row in rows}

    assert by_id["p518j_health"]["reads_artifacts_only"] == "True"
    assert by_id["p518j_health"]["generates_artifacts"] == "False"
    assert by_id["p518j_generate"]["generates_artifacts"] == "True"
    assert by_id["p518i_status"]["reads_artifacts_only"] == "True"
    assert by_id["p518h_decision"]["reads_artifacts_only"] == "True"
    assert by_id["p518f_smoke_reference"]["executes_verifier_or_harness"] == "True"
    assert by_id["p518g_edge_reference"]["executes_verifier_or_harness"] == "True"
    assert all(row["opens_canonical_db"] == "False" for row in rows)


def test_db_invariant_snapshot_records_no_runner_db_access():
    snapshot = healthcheck.build_db_invariant_snapshot()

    assert snapshot["status"] == "PASS"
    assert snapshot["p518j_runner_invariant"]["canonical_db_opened"] is False
    assert snapshot["p518j_runner_invariant"]["canonical_db_written"] is False
    assert snapshot["p518j_runner_invariant"]["canonical_db_hash_computed_by_runner"] is False
    assert snapshot["p518j_runner_invariant"]["migration_backfill_deploy_run"] is False
    assert snapshot["source_invariants"]["P518I_db_invariant_status"] == "PASS"
    assert snapshot["source_invariants"]["P518H_db_invariant_status"] == "PASS"
    assert snapshot["source_invariants"]["P518F_no_db_evidence_status"] == "PASS"
    assert snapshot["source_invariants"]["P518G_no_db_evidence_status"] == "PASS"


def test_status_block_is_copy_paste_friendly_and_scoped():
    block = healthcheck.build_healthcheck_bundle()["status_block"]

    assert "Final verifier health: `PASS`" in block
    assert "P518I compact status: `PASS`" in block
    assert "P518J reads committed P518I/P518H/P518F/P518G artifacts only." in block
    for notice in healthcheck.NOTICE_LINES:
        assert notice in block


def test_rendered_artifacts_are_deterministic_across_runs():
    first = healthcheck.render_artifacts()
    second = healthcheck.render_artifacts()
    assert first == second


def test_generate_and_validate_artifacts_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(healthcheck, "ARTIFACTS_DIR", tmp_path)
    monkeypatch.setattr(healthcheck, "HEALTH_PATH", tmp_path / "P518J_predraw_ledger_verify_healthcheck_result.json")
    monkeypatch.setattr(
        healthcheck,
        "ARTIFACT_INVENTORY_PATH",
        tmp_path / "P518J_predraw_ledger_verify_healthcheck_artifact_inventory.csv",
    )
    monkeypatch.setattr(
        healthcheck,
        "COMMAND_MATRIX_PATH",
        tmp_path / "P518J_predraw_ledger_verify_healthcheck_command_matrix.csv",
    )
    monkeypatch.setattr(
        healthcheck,
        "DB_INVARIANT_PATH",
        tmp_path / "P518J_predraw_ledger_verify_healthcheck_db_invariant.json",
    )
    monkeypatch.setattr(
        healthcheck,
        "STATUS_BLOCK_PATH",
        tmp_path / "P518J_predraw_ledger_verify_healthcheck_status_block.md",
    )
    monkeypatch.setattr(
        healthcheck,
        "MANIFEST_PATH",
        tmp_path / "P518J_predraw_ledger_verify_healthcheck_manifest.csv",
    )

    rendered = healthcheck.write_artifacts()
    ok, mismatches = healthcheck.validate_artifacts(rendered)

    assert ok, mismatches
    assert set(rendered) == {
        tmp_path / "P518J_predraw_ledger_verify_healthcheck_result.json",
        tmp_path / "P518J_predraw_ledger_verify_healthcheck_artifact_inventory.csv",
        tmp_path / "P518J_predraw_ledger_verify_healthcheck_command_matrix.csv",
        tmp_path / "P518J_predraw_ledger_verify_healthcheck_db_invariant.json",
        tmp_path / "P518J_predraw_ledger_verify_healthcheck_status_block.md",
        tmp_path / "P518J_predraw_ledger_verify_healthcheck_manifest.csv",
    }


def test_artifacts_contain_required_safety_notices():
    rendered = healthcheck.render_artifacts()
    combined = "\n".join(rendered.values())

    for notice in healthcheck.NOTICE_LINES:
        assert notice in combined


def test_cli_parser_exposes_required_p518j_flags():
    help_text = healthcheck.build_parser().format_help()

    for flag in (
        "--generate",
        "--health",
        "--artifact-inventory",
        "--command-matrix",
        "--db-invariant",
        "--status-block",
        "--validate",
        "--help",
    ):
        assert flag in help_text


def test_healthcheck_module_does_not_import_or_execute_verifier_harnesses():
    source = Path(healthcheck.__file__).read_text(encoding="utf-8")

    forbidden = (
        "import tools.predraw_ledger_verify",
        "import tools.predraw_ledger_verify_smoke",
        "import tools.predraw_ledger_verify_acceptance",
        "import tools.predraw_ledger_verify_status",
        "from tools import predraw_ledger_verify",
        "from tools import predraw_ledger_verify_smoke",
        "from tools import predraw_ledger_verify_acceptance",
        "from tools import predraw_ledger_verify_status",
    )
    for needle in forbidden:
        assert needle not in source


def test_generated_health_json_is_parseable():
    rendered = healthcheck.render_artifacts()
    result = json.loads(rendered[healthcheck.HEALTH_PATH])
    db_invariant = json.loads(rendered[healthcheck.DB_INVARIANT_PATH])

    assert result["final_verifier_health"] == "PASS"
    assert result["missing_artifact_count"] == 0
    assert db_invariant["status"] == "PASS"
