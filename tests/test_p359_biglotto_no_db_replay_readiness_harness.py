import builtins
import csv
import importlib
import sqlite3
from pathlib import Path

import pytest

from recovered_strategies.biglotto import no_db_replay_readiness_harness as harness


REQUIRED_COLUMNS = set(harness.REQUIRED_COLUMNS)


def assert_biglotto_outputs(outputs, expected_count):
    assert isinstance(outputs, list)
    assert len(outputs) == 1
    assert len(outputs[0]) == expected_count
    for bet in outputs[0]:
        assert bet == sorted(bet)
        assert len(bet) == 6
        assert len(set(bet)) == 6
        assert all(1 <= number <= 49 for number in bet)


def test_harness_import_and_run_do_not_call_sqlite_connect(monkeypatch):
    def blocked_connect(*args, **kwargs):
        raise AssertionError("sqlite3.connect must not be called by P359 harness")

    monkeypatch.setattr(sqlite3, "connect", blocked_connect)
    result = harness.run_harness()
    assert result["no_db_open_write_status"] == "NO_DB_OPENED_OR_WRITTEN"
    assert all(row.db_opened is False for row in result["rows"])


def test_harness_does_not_import_production_registry(monkeypatch):
    original_import = builtins.__import__
    blocked_prefixes = (
        "lottery_api.models.replay_strategy_registry",
        "lottery_api.strategy",
        "lottery_api.services.strategy",
    )

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name.startswith(blocked_prefixes):
            raise AssertionError(f"production registry import blocked: {name}")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    module = importlib.reload(harness)
    result = module.run_harness()
    assert result["production_registry_status"] == "NOT_IMPORTED_OR_CONNECTED"
    assert all(row.production_registry_imported is False for row in result["rows"])


def test_harness_output_is_deterministic():
    first = [row.as_csv_row() for row in harness.build_readiness_rows()]
    second = [row.as_csv_row() for row in harness.build_readiness_rows()]
    assert first == second


def test_every_row_has_expected_tier_and_required_columns():
    rows = harness.build_readiness_rows()
    assert {row.tier for row in rows} == {
        "p356_baseline",
        "p358_parity_acceptable",
        "p358_shape_safety_only",
        "blocked_excluded",
    }
    for row in rows:
        csv_row = row.as_csv_row()
        assert row.tier
        assert REQUIRED_COLUMNS.issubset(csv_row)


def test_p356_baseline_rows_are_prior_evidence_only():
    rows = [row for row in harness.build_readiness_rows() if row.tier == "p356_baseline"]
    assert {row.strategy_id for row in rows} == {strategy_id for strategy_id, _ in harness.P356_BASELINE}
    assert all(row.execution_status == "PRIOR_REPLAY_EVIDENCE_ONLY" for row in rows)
    assert all(row.readiness_status == "PRIOR_BASELINE_ONLY" for row in rows)
    assert all(row.parity_status == "PRIOR_P356_REPLAY_EVIDENCE" for row in rows)
    assert all(row.adapter_function == "NOT_EXECUTED_BY_DESIGN" for row in rows)


def test_parity_acceptable_adapters_execute_under_no_db_fixture():
    rows = [row for row in harness.build_readiness_rows() if row.tier == "p358_parity_acceptable"]
    assert {row.adapter_function for row in rows} == set(harness.P358_PARITY_ACCEPTABLE)
    assert all(row.execution_status == "EXECUTED_NO_DB" for row in rows)
    assert all(row.readiness_status == "READY_FOR_NO_DB_HARNESS" for row in rows)
    assert all(row.parity_status == "PARITY_ACCEPTABLE_FOR_NO_DB_HARNESS" for row in rows)
    assert all(row.all_outputs_valid for row in rows)
    assert all(row.deterministic for row in rows)


@pytest.mark.parametrize(
    ("adapter_function", "expected_count"),
    [
        ("adapt_biglotto_p0_2bet", 2),
        ("adapt_predict_biglotto_echo_2bet", 2),
        ("adapt_predict_biglotto_echo_phase2_2bet", 2),
        ("adapt_predict_biglotto_echo_phase2_3bet", 3),
        ("adapt_predict_biglotto_echo_mixed_3bet", 3),
        ("adapt_biglotto_zonal_pruning", 4),
        ("adapt_biglotto_5bet_orthogonal", 5),
        ("adapt_predict_biglotto_regime_3bet", 3),
        ("adapt_biglotto_10bet_combined", 10),
    ],
)
def test_executed_adapters_have_valid_biglotto_main_number_shape(adapter_function, expected_count):
    row = next(row for row in harness.build_readiness_rows() if row.adapter_function == adapter_function)
    assert_biglotto_outputs(__import__("json").loads(row.outputs_json), expected_count)


def test_shape_safety_only_adapters_are_flagged_not_parity_evidence():
    rows = [row for row in harness.build_readiness_rows() if row.tier == "p358_shape_safety_only"]
    assert {row.adapter_function for row in rows} == set(harness.P358_SHAPE_SAFETY_ONLY)
    assert all(row.execution_status == "EXECUTED_NO_DB" for row in rows)
    assert all(row.readiness_status == "READY_SHAPE_SAFETY_ONLY" for row in rows)
    assert all(row.parity_status == "SHAPE_SAFETY_ONLY" for row in rows)
    assert all("not parity replay evidence" in row.notes for row in rows)


def test_blocked_strategies_are_present_as_excluded_rows():
    rows = [row for row in harness.build_readiness_rows() if row.tier == "blocked_excluded"]
    assert {row.strategy_id for row in rows} == {strategy_id for strategy_id, _, _ in harness.BLOCKED_EXCLUDED}
    assert all(row.execution_status == "EXCLUDED_BLOCKED" for row in rows)
    assert all(row.parity_status == "BLOCKED_NOT_COMPARABLE" for row in rows)


def test_bet2_fourier_expansion_biglotto_excluded_due_id_reuse():
    row = next(row for row in harness.build_readiness_rows() if row.strategy_id == "bet2_fourier_expansion_biglotto")
    assert row.tier == "blocked_excluded"
    assert row.readiness_status == "BLOCKED_ID_REUSE"
    assert "ID reuse" in row.blocked_reason


def test_no_single_blended_leaderboard_artifact_is_produced():
    assert not list(Path("artifacts").glob("P359*leaderboard*"))
    report = harness.render_report(harness.run_harness())
    assert "no blended leaderboard" in report
    assert "tiers must not be ranked together" in report


def test_manifest_and_results_csv_parse_with_required_columns(tmp_path):
    result = harness.run_harness()
    manifest_path = harness.write_manifest_csv(result, tmp_path / "manifest.csv")
    results_path = harness.write_results_csv(result, tmp_path / "results.csv")
    report_path = harness.write_report(result, tmp_path / "report.md")

    for path in (manifest_path, results_path):
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            assert REQUIRED_COLUMNS.issubset(reader.fieldnames or [])
            rows = list(reader)
        assert rows
        assert {row["tier"] for row in rows} == {
            "p356_baseline",
            "p358_parity_acceptable",
            "p358_shape_safety_only",
            "blocked_excluded",
        }

    report = report_path.read_text(encoding="utf-8")
    assert "Shape/safety-only results are flagged" in report
    assert "No DB open/write" in report
    assert "This is not betting evidence" in report
    assert "{row.adapter_function}" not in report
    assert "adapt_biglotto_p0_2bet" in report
