"""Integration and backtest-contract tests for the committed P20C runner."""

from __future__ import annotations

import gzip
import hashlib
import json
import sqlite3
import subprocess
import sys
from itertools import combinations
from pathlib import Path

import pytest

from lottery_api.models.replay_strategy_registry import (
    get_strategy_lifecycle_status,
)
from scripts.p20c_strategy_preserving_20_ticket_backtest import (
    DETAIL_FIELDS,
    SHORT_IDENTIFIER,
    TICKET_CONSTRUCTOR_NATIVE_ONLY,
    TICKET_CONSTRUCTOR_V1,
    StrategySpec,
    build_inventory_and_failure_ledger,
    build_metrics,
    build_strategy_specs,
    execute_backtest,
    independent_detail_validation,
    open_database_readonly,
    paired_baseline_interval,
    prepare_portfolio,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
RUNNER = REPO_ROOT / "scripts/p20c_strategy_preserving_20_ticket_backtest.py"


def tickets(count):
    return [list(ticket) for ticket in list(combinations(range(1, 50), 6))[:count]]


@pytest.mark.parametrize("native_count", (1, 2, 4, 8))
def test_representative_partial_counts_become_exact_twenty(native_count):
    raw = tickets(native_count)
    result = prepare_portfolio(
        strategy_id=f"representative::{native_count}",
        draw_id="115000070",
        replicate_id=0,
        cutoff_identity="115000069",
        raw_tickets=raw,
        actual_numbers=[10, 25, 34, 36, 45, 46],
        constructor_mode=TICKET_CONSTRUCTOR_V1,
    )
    assert result["ok"] is True
    assert result["status"] == "COMPLETED_ADAPTER_20"
    assert len(result["tickets"]) == 20
    assert len(set(result["tickets"])) == 20
    assert set(tuple(sorted(ticket)) for ticket in raw).issubset(set(result["tickets"]))
    assert result["metadata"].native_retained_count == native_count
    assert result["metadata"].constructed_ticket_count == 20 - native_count
    assert result["metadata"].effective_strategy_id.endswith(f"@{SHORT_IDENTIFIER}")


def test_native_only_mode_remains_partial_and_reproducible():
    raw = tickets(4)
    first = prepare_portfolio(
        strategy_id="native-only::four",
        draw_id="115000070",
        replicate_id=0,
        cutoff_identity="115000069",
        raw_tickets=raw,
        actual_numbers=[10, 25, 34, 36, 45, 46],
        constructor_mode=TICKET_CONSTRUCTOR_NATIVE_ONLY,
    )
    second = prepare_portfolio(
        strategy_id="native-only::four",
        draw_id="115000070",
        replicate_id=0,
        cutoff_identity="115000069",
        raw_tickets=list(reversed(raw)),
        actual_numbers=[10, 25, 34, 36, 45, 46],
        constructor_mode=TICKET_CONSTRUCTOR_NATIVE_ONLY,
    )
    assert first == second
    assert first["ok"] is False
    assert first["status"] == "INSUFFICIENT_TICKETS"
    assert len(first["tickets"]) == 4


def test_target_and_future_result_mutation_cannot_change_constructor_output():
    kwargs = {
        "strategy_id": "mutation::guard",
        "draw_id": "115000070",
        "replicate_id": 0,
        "cutoff_identity": "115000069",
        "raw_tickets": tickets(2),
        "constructor_mode": TICKET_CONSTRUCTOR_V1,
    }
    original = prepare_portfolio(
        actual_numbers=[10, 25, 34, 36, 45, 46], **kwargs
    )
    mutated = prepare_portfolio(
        actual_numbers=[1, 2, 3, 4, 5, 6], **kwargs
    )
    assert original["tickets"] == mutated["tickets"]
    assert (
        original["metadata"].portfolio_sha256
        == mutated["metadata"].portfolio_sha256
    )
    assert original["metadata"].seed_digest == mutated["metadata"].seed_digest


def test_governance_status_is_not_changed_by_constructor_integration():
    before = {
        strategy_id: get_strategy_lifecycle_status(strategy_id)
        for strategy_id in (
            "biglotto_triple_strike",
            "biglotto_echo_aware_3bet",
            "markov_single_biglotto",
        )
    }
    for strategy_id in before:
        result = prepare_portfolio(
            strategy_id=f"registry::{strategy_id}",
            draw_id="115000070",
            replicate_id=0,
            cutoff_identity="115000069",
            raw_tickets=tickets(2),
            actual_numbers=[10, 25, 34, 36, 45, 46],
            constructor_mode=TICKET_CONSTRUCTOR_V1,
        )
        assert result["ok"] is True
    after = {
        strategy_id: get_strategy_lifecycle_status(strategy_id)
        for strategy_id in before
    }
    assert after == before
    assert before == {
        "biglotto_triple_strike": "ONLINE",
        "biglotto_echo_aware_3bet": "RETIRED",
        "markov_single_biglotto": "REJECTED",
    }


def test_equivalent_native_outputs_keep_distinct_strategy_identities():
    native = tickets(20)
    first = prepare_portfolio(
        strategy_id="equivalent::first",
        draw_id="115000070",
        replicate_id=0,
        cutoff_identity="115000069",
        raw_tickets=native,
        actual_numbers=[10, 25, 34, 36, 45, 46],
        constructor_mode=TICKET_CONSTRUCTOR_V1,
    )
    second = prepare_portfolio(
        strategy_id="equivalent::second",
        draw_id="115000070",
        replicate_id=0,
        cutoff_identity="115000069",
        raw_tickets=native,
        actual_numbers=[10, 25, 34, 36, 45, 46],
        constructor_mode=TICKET_CONSTRUCTOR_V1,
    )
    assert first["tickets"] == second["tickets"]
    assert first["metadata"].portfolio_sha256 == second["metadata"].portfolio_sha256
    assert first["metadata"].effective_strategy_id == "equivalent::first"
    assert second["metadata"].effective_strategy_id == "equivalent::second"


def test_failure_of_one_generator_does_not_stop_other_strategies(tmp_path):
    draws = [
        {"draw": "100", "date": "2026/01/01", "numbers": [1, 2, 3, 4, 5, 6], "special": 7},
        {"draw": "101", "date": "2026/01/02", "numbers": [7, 8, 9, 10, 11, 12], "special": 13},
    ]

    def good(history, target, replicate, seed):
        del history, target, replicate, seed
        return [[1, 2, 3, 4, 5, 6]]

    def bad(history, target, replicate, seed):
        del history, target, replicate, seed
        raise RuntimeError("deliberate generator failure")

    specs = [
        StrategySpec("good", "good", "candidate", 0, 1, "test", "adapter", True, good),
        StrategySpec("bad", "bad", "candidate", 0, 1, "test", "adapter", True, bad),
    ]
    detail = tmp_path / "detail.csv.gz"
    observations, failures, execution = execute_backtest(
        draws=draws,
        specs=specs,
        constructor_mode=TICKET_CONSTRUCTOR_V1,
        detail_path=detail,
    )
    good_rows = [row for row in observations if row["base_strategy_id"] == "good"]
    bad_rows = [row for row in observations if row["base_strategy_id"] == "bad"]
    assert len(good_rows) == 2
    assert all(row["status"] == "COMPLETED_ADAPTER_20" for row in good_rows)
    assert len(bad_rows) == 2
    assert all(row["status"] == "GENERATOR_FAILURE" for row in bad_rows)
    assert len(failures) == 2
    assert execution["detail_row_count"] == 4
    validation = independent_detail_validation(detail, observations)
    assert validation["row_count_matches"] is True
    assert validation["ticket_legality_failures"] == 0
    assert validation["hit_recomputation_mismatches"] == 0
    assert validation["native_preservation_failures"] == 0
    assert validation["constructor_metadata_mismatches"] == 0


def test_detail_stream_is_byte_reproducible(tmp_path):
    draws = [
        {
            "draw": "100",
            "date": "2026/01/01",
            "numbers": [1, 2, 3, 4, 5, 6],
            "special": 7,
        },
        {
            "draw": "101",
            "date": "2026/01/02",
            "numbers": [7, 8, 9, 10, 11, 12],
            "special": 13,
        },
    ]

    def generator(history, target, replicate, seed):
        del history, target, replicate, seed
        return [[1, 2, 3, 4, 5, 6]]

    specs = [
        StrategySpec(
            "deterministic",
            "deterministic",
            "candidate",
            1,
            1,
            "test",
            "adapter",
            True,
            generator,
        )
    ]
    paths = [tmp_path / "first.csv.gz", tmp_path / "second.csv.gz"]
    executions = [
        execute_backtest(
            draws=draws,
            specs=specs,
            constructor_mode=TICKET_CONSTRUCTOR_V1,
            detail_path=path,
        )
        for path in paths
    ]
    assert executions[0] == executions[1]
    assert paths[0].read_bytes() == paths[1].read_bytes()
    assert hashlib.sha256(paths[0].read_bytes()).hexdigest() == hashlib.sha256(
        paths[1].read_bytes()
    ).hexdigest()


def test_readonly_database_helper_never_creates_or_writes(tmp_path):
    database = tmp_path / "fixture.db"
    writable = sqlite3.connect(database)
    writable.execute("CREATE TABLE sample(value INTEGER)")
    writable.execute("INSERT INTO sample VALUES (1)")
    writable.commit()
    writable.close()
    size_before = database.stat().st_size
    connection = open_database_readonly(database)
    assert connection.execute("SELECT value FROM sample").fetchone()[0] == 1
    with pytest.raises(sqlite3.OperationalError):
        connection.execute("INSERT INTO sample VALUES (2)")
    connection.close()
    assert database.stat().st_size == size_before
    missing = tmp_path / "missing.db"
    with pytest.raises(FileNotFoundError):
        open_database_readonly(missing)
    assert not missing.exists()


def test_paired_baseline_uses_same_target_draw_clusters():
    strategy = [
        {"target_draw": "1", "m4plus": 1},
        {"target_draw": "2", "m4plus": 0},
    ]
    baseline = [
        {"target_draw": "1", "m4plus": 0},
        {"target_draw": "1", "m4plus": 0},
        {"target_draw": "2", "m4plus": 0},
        {"target_draw": "2", "m4plus": 0},
        {"target_draw": "999", "m4plus": 1},
    ]
    point, low, high = paired_baseline_interval(
        strategy,
        baseline,
        identity="pairing-test",
        bootstrap_replicates=200,
    )
    assert point == 0.5
    assert low <= point <= high


def _observation(base, effective, group, draw, m4plus, constructed):
    return {
        "base_strategy_id": base,
        "effective_strategy_id": effective,
        "ranking_group": group,
        "target_index": 100 + int(draw),
        "target_draw": draw,
        "replicate_id": 0,
        "final_ticket_count": 20,
        "m4plus": m4plus,
        "native_valid_count": 20 - constructed,
        "constructed_ticket_count": constructed,
        "native_ticket_share": (20 - constructed) / 20,
        "native_m4plus": 0,
        "construction_tier": "native_complete" if constructed == 0 else "native_ticket_derived_signal",
    }


def test_native_adapter_and_baseline_rankings_are_separate():
    def unused(history, target, replicate, seed):
        del history, target, replicate, seed
        return []

    specs = [
        StrategySpec("baseline::uniform_random_20", "baseline", "baseline", 0, 1, "test", "baseline", False, unused),
        StrategySpec("native", "native", "candidate", 0, 1, "test", "native", False, unused),
        StrategySpec("adapter", "adapter", "rejected", 0, 1, "test", "adapter", True, unused),
    ]
    observations = [
        _observation("baseline::uniform_random_20", "baseline::uniform_random_20", "baseline", "1", 0, 0),
        _observation("baseline::uniform_random_20", "baseline::uniform_random_20", "baseline", "2", 0, 0),
        _observation("native", "native", "native", "1", 1, 0),
        _observation("native", "native", "native", "2", 0, 0),
        _observation("adapter", f"adapter@{SHORT_IDENTIFIER}", "adapter", "1", 1, 19),
        _observation("adapter", f"adapter@{SHORT_IDENTIFIER}", "adapter", "2", 1, 19),
    ]
    metrics, native, adapter, baseline = build_metrics(
        observations=observations,
        specs=specs,
        bootstrap_replicates=100,
        draw_count=102,
    )
    assert len(metrics) == 2
    assert [row["effective_strategy_id"] for row in native] == ["native"]
    assert [row["effective_strategy_id"] for row in adapter] == [f"adapter@{SHORT_IDENTIFIER}"]
    assert baseline["strategy_id"] == "baseline::uniform_random_20"


def test_inventory_keeps_known_leakage_invalid_evaluator_excluded():
    specs = build_strategy_specs(10)
    summary, ledger = build_inventory_and_failure_ledger(specs)
    assert summary["formerly_partial_identities"] == 12
    assert summary["runnable_strategy_identities"] == 14
    leakage = [
        row
        for row in ledger
        if row["strategy_id"] == "history::tools/big_lotto_exhaustive_audit.py"
    ]
    assert len(leakage) == 1
    assert leakage[0]["reason_code"] == "DATA_LEAKAGE_RISK"


def test_cli_help_exposes_constructor_mode_explicitly():
    output = subprocess.check_output(
        [sys.executable, str(RUNNER), "--help"],
        cwd=REPO_ROOT,
        text=True,
    )
    assert "--ticket-constructor" in output
    assert "native-only" in output
    assert "strategy-preserving-v1" in output


def test_detail_schema_records_constructor_metadata_per_draw_and_replicate():
    required = {
        "base_strategy_id",
        "effective_strategy_id",
        "replicate_id",
        "target_draw",
        "history_cutoff_identity",
        "constructor_name",
        "constructor_version",
        "seed_material",
        "seed_digest",
        "native_input_count",
        "native_valid_count",
        "native_duplicate_count",
        "native_invalid_count",
        "native_retained_count",
        "constructed_ticket_count",
        "final_ticket_count",
        "native_ticket_share",
        "signal_source",
        "construction_tier",
        "relaxation_level",
        "warnings_json",
        "portfolio_sha256",
    }
    assert required.issubset(DETAIL_FIELDS)
