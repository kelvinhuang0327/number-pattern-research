from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

import pytest

from recovered_strategies.daily539.no_db_replay_harness import (
    EXCLUDED_SHAPE_ONLY_STRATEGY_IDS,
    INCLUDED_STRATEGY_IDS,
    build_deterministic_daily539_fixture,
    run_controlled_no_db_replay,
)


def test_p357e_harness_scope_is_exact_parity_acceptable_slice() -> None:
    assert INCLUDED_STRATEGY_IDS == (
        "p0b_539_3bet_f_cold_fmid",
        "p0c_539_3bet_f_cold_x2",
    )
    assert EXCLUDED_SHAPE_ONLY_STRATEGY_IDS == ("539_3bet_orthogonal",)


def test_p357e_harness_produces_deterministic_valid_prediction_rows() -> None:
    first = run_controlled_no_db_replay()
    second = run_controlled_no_db_replay()

    assert first == second
    assert first["fixture_size"] == 520
    assert first["replay_window"] == 500
    assert first["total_periods"] == 21
    assert first["prediction_row_count"] == 42
    assert first["included_adapters"] == list(INCLUDED_STRATEGY_IDS)
    assert first["excluded_shape_only_adapters"] == list(
        EXCLUDED_SHAPE_ONLY_STRATEGY_IDS
    )
    assert first["all_outputs_valid"] is True
    assert first["no_db_write_open_status"] == "NO_DB_OPENED_OR_WRITTEN"
    assert first["production_registry_status"] == "NOT_CONNECTED"
    assert first["strategy_status_change_status"] == "NOT_CHANGED"
    assert first["full_replay_status"] == "NOT_RUN"
    assert first["next_readiness"] == "READY_FOR_CONTROLLED_REPLAY_EXPANSION"

    for row in first["rows"]:
        assert row["strategy_id"] in INCLUDED_STRATEGY_IDS
        assert row["strategy_id"] not in EXCLUDED_SHAPE_ONLY_STRATEGY_IDS
        assert row["game"] == "DAILY_539"
        assert row["fixture_size"] == 520
        assert row["replay_window"] == 500
        assert row["total_periods"] == 21
        assert row["prediction_rows"] == 3
        assert row["output_valid"] is True
        assert "in-memory fixture only" in row["no_db_access_proof"]


def test_p357e_harness_rejects_less_than_500_draw_fixture() -> None:
    with pytest.raises(ValueError, match="at least 500 draws"):
        build_deterministic_daily539_fixture(499)

    fixture = build_deterministic_daily539_fixture(500)
    result = run_controlled_no_db_replay(fixture)
    assert result["total_periods"] == 1
    assert result["prediction_row_count"] == 2


def test_p357e_harness_does_not_open_sqlite(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_connect(*args: object, **kwargs: object) -> None:
        raise AssertionError(f"sqlite3.connect must not be called: {args} {kwargs}")

    monkeypatch.setattr(sqlite3, "connect", fail_connect)
    result = run_controlled_no_db_replay()

    assert result["no_db_write_open_status"] == "NO_DB_OPENED_OR_WRITTEN"
    assert result["all_outputs_valid"] is True


def test_p357e_artifacts_exist_and_match_harness_contract() -> None:
    report_path = Path("artifacts/P357E_daily539_no_db_replay_harness_report.md")
    results_path = Path("artifacts/P357E_daily539_no_db_replay_harness_results.csv")

    assert report_path.exists()
    assert results_path.exists()

    report = report_path.read_text(encoding="utf-8")
    assert "P357E_COMPLETE_NO_DB_REPLAY_HARNESS" in report
    assert "READY_FOR_CONTROLLED_REPLAY_EXPANSION" in report
    assert "NO_DB_OPENED_OR_WRITTEN" in report
    assert "539_3bet_orthogonal" in report
    assert "shape/safety-only" in report

    rows = list(csv.DictReader(results_path.open(newline="", encoding="utf-8")))
    assert len(rows) == 42
    assert {row["strategy_id"] for row in rows} == set(INCLUDED_STRATEGY_IDS)
    assert {row["output_valid"] for row in rows} == {"True"}
    assert {row["total_periods"] for row in rows} == {"21"}
    assert {row["replay_window"] for row in rows} == {"500"}
