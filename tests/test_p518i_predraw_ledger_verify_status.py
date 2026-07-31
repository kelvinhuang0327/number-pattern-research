"""
P518I tests for the compact predraw ledger verifier no-DB status layer.

The status layer reads committed P518H artifacts only. These tests do not open
or write the canonical DB, do not run migrations/backfills, do not deploy, are
not production release approval, and make no betting or future prediction claims.
"""
from __future__ import annotations

import json
from pathlib import Path

import tools.predraw_ledger_verify_status as status


def test_status_summary_compacts_p518h_acceptance_health():
    bundle = status.build_status_bundle()
    summary = bundle["status_summary"]

    assert summary["acceptance_decision"]["final_status"] == "PASS"
    assert summary["smoke_cases"]["total"] == 5
    assert summary["smoke_cases"]["passed"] == 5
    assert summary["edge_cases"]["total"] == 7
    assert summary["edge_cases"]["passed"] == 7
    assert summary["db_invariant"]["status"] == "PASS"
    assert summary["canonical_db_refusal_status"] == "PASS"
    assert summary["failed_missing_case_count"] == 0
    assert summary["warning_count"] == 0
    assert summary["final_compact_status"] == "PASS"


def test_badges_include_required_health_dimensions():
    badges = status.build_status_bundle()["badges"]["badges"]

    assert set(badges) == {
        "verifier_health",
        "db_invariant",
        "smoke_cases",
        "edge_cases",
        "canonical_db_refusal",
        "no_deploy",
    }
    assert all(badge["status"] == "PASS" for badge in badges.values())


def test_status_block_is_copy_paste_friendly_and_scoped():
    block = status.build_status_bundle()["status_block"]

    assert "Final compact status: `PASS`" in block
    assert "`verifier_health`: `PASS`" in block
    assert "P518I reads committed P518H acceptance artifacts only." in block
    for notice in status.NOTICE_LINES:
        assert notice in block


def test_query_summary_exposes_machine_readable_no_db_flags():
    query = status.build_status_bundle()["query_summary"]

    assert query["final_compact_status"] == "PASS"
    assert query["no_canonical_db_open_write"] is True
    assert query["no_migration_backfill"] is True
    assert query["no_deploy"] is True
    assert query["synthetic_fixture_evidence_only"] is True
    assert query["not_production_release_approval"] is True
    assert query["no_betting_future_prediction_claims"] is True


def test_rendered_artifacts_are_deterministic_across_runs():
    first = status.render_artifacts()
    second = status.render_artifacts()
    assert first == second


def test_generate_and_validate_artifacts_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(status, "ARTIFACTS_DIR", tmp_path)
    monkeypatch.setattr(status, "STATUS_SUMMARY_PATH", tmp_path / "P518I_predraw_ledger_verify_status_summary.json")
    monkeypatch.setattr(status, "BADGES_PATH", tmp_path / "P518I_predraw_ledger_verify_status_badges.json")
    monkeypatch.setattr(status, "STATUS_BLOCK_PATH", tmp_path / "P518I_predraw_ledger_verify_status_block.md")
    monkeypatch.setattr(
        status,
        "QUERY_SUMMARY_PATH",
        tmp_path / "P518I_predraw_ledger_verify_status_query_summary.json",
    )
    monkeypatch.setattr(status, "REPORT_PATH", tmp_path / "P518I_predraw_ledger_verify_status_report.md")
    monkeypatch.setattr(status, "MANIFEST_PATH", tmp_path / "P518I_predraw_ledger_verify_status_manifest.csv")

    rendered = status.write_artifacts()
    ok, mismatches = status.validate_artifacts(rendered)

    assert ok, mismatches
    assert set(rendered) == {
        tmp_path / "P518I_predraw_ledger_verify_status_summary.json",
        tmp_path / "P518I_predraw_ledger_verify_status_badges.json",
        tmp_path / "P518I_predraw_ledger_verify_status_block.md",
        tmp_path / "P518I_predraw_ledger_verify_status_query_summary.json",
        tmp_path / "P518I_predraw_ledger_verify_status_report.md",
        tmp_path / "P518I_predraw_ledger_verify_status_manifest.csv",
    }


def test_artifacts_contain_required_safety_notices():
    rendered = status.render_artifacts()
    combined = "\n".join(rendered.values())

    for notice in status.NOTICE_LINES:
        assert notice in combined


def test_cli_parser_exposes_required_p518i_flags():
    help_text = status.build_parser().format_help()

    for flag in (
        "--generate",
        "--status",
        "--badges",
        "--status-block",
        "--query-summary",
        "--validate",
        "--help",
    ):
        assert flag in help_text


def test_status_module_does_not_import_or_execute_verifier_harnesses():
    source = Path(status.__file__).read_text(encoding="utf-8")

    assert "import tools.predraw_ledger_verify" not in source
    assert "import tools.predraw_ledger_verify_smoke" not in source
    assert "import tools.predraw_ledger_verify_acceptance" not in source
    assert "from tools import predraw_ledger_verify" not in source
    assert "from tools import predraw_ledger_verify_smoke" not in source
    assert "from tools import predraw_ledger_verify_acceptance" not in source


def test_generated_status_json_is_parseable():
    rendered = status.render_artifacts()

    summary = json.loads(rendered[status.STATUS_SUMMARY_PATH])
    badges = json.loads(rendered[status.BADGES_PATH])
    query = json.loads(rendered[status.QUERY_SUMMARY_PATH])

    assert summary["final_compact_status"] == "PASS"
    assert badges["badges"]["verifier_health"]["status"] == "PASS"
    assert query["acceptance_final_status"] == "PASS"
