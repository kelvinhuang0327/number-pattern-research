from __future__ import annotations

import json
from collections import Counter

import pytest

from recovered_strategies.biglotto import p20t_recovery_adapters as recovered
from scripts import p20c_strategy_preserving_20_ticket_backtest as p20c
from scripts import p20s_all_strategies_bulk_recovery as p20s
from scripts import p20t_remaining_16_strategy_recovery as p20t


def synthetic_draws(count: int = 620) -> list[dict]:
    draws = []
    for index in range(count):
        values: list[int] = []
        step = index % 11 + 1
        cursor = index * 7 % 49
        while len(values) < 6:
            number = (cursor + step * len(values) + index // 7) % 49 + 1
            if number not in values:
                values.append(number)
            else:
                cursor += 1
        draws.append(
            {
                "draw": f"{index + 1:08d}",
                "date": f"2024/{index % 12 + 1:02d}/{index % 28 + 1:02d}",
                "numbers": sorted(values),
                "special": index * 13 % 49 + 1,
            }
        )
    return draws


def test_target_set_is_exact_stable_and_reconciles_p20s():
    targets = p20t.load_target_inventory()
    assert tuple(row["strategy_id"] for row in targets) == p20t.TARGET_IDS
    assert len(targets) == len(set(p20t.TARGET_IDS)) == 16
    assert Counter(row["terminal_disposition"] for row in targets) == {
        "MISSING_IMPLEMENTATION": 12,
        "PARTIAL_BACKTEST": 4,
    }
    assert set(p20t.RECOVERIES) | set(p20t.TERMINAL_DECISIONS) == set(p20t.TARGET_IDS)
    assert set(p20t.RECOVERIES).isdisjoint(p20t.TERMINAL_DECISIONS)
    assert not any("random" in strategy_id for strategy_id in p20t.TARGET_IDS)
    ledger = p20t.read_csv(p20t.P20S_DIR / "strategy_resolution_ledger.csv")
    non_backlog = {
        row["strategy_id"]
        for row in ledger
        if row["terminal_disposition"] not in p20t.TARGET_DISPOSITIONS
    }
    assert set(p20t.TARGET_IDS).isdisjoint(non_backlog)


def test_three_prior_partials_are_exact_recoveries_and_zonal_is_terminal():
    assert {
        "biglotto_10bet_combined",
        "biglotto_5bet_orthogonal",
        "predict_biglotto_regime",
    } <= set(p20t.RECOVERIES)
    assert p20t.TERMINAL_DECISIONS["biglotto_zonal_pruning"]["final"] == (
        "OTHER_EVIDENCED_TERMINAL_EXCLUSION"
    )


def test_constructor_reproducibility_uses_the_p20c_mismatch_contract():
    assert p20t.constructor_reproducibility_pass(
        {"sample_count": 12, "mismatch_count": 0, "mismatched_strategy_ids": []}
    )


@pytest.mark.parametrize("value", [20, "20"])
def test_ticket_count_parameter_accepts_positive_integer_20(value):
    assert p20t.validate_target_ticket_count(value) == 20


@pytest.mark.parametrize("value", [True, False, 0, -1, 1.5, "15.0", "abc", None])
def test_ticket_count_parameter_rejects_non_positive_or_non_integer_values(value):
    with pytest.raises(ValueError, match="positive integer"):
        p20t.validate_target_ticket_count(value)


def test_p20t_historical_executor_refuses_10_and_15_ticket_runs():
    for ticket_count in p20t.NOT_RUN_TICKET_COUNTS:
        with pytest.raises(ValueError, match="only at 20 tickets"):
            p20t.build_strategy_specs(target_ticket_count=ticket_count)


def test_nested_prefix_interface_is_order_preserving_and_count_aware():
    history = synthetic_draws(500)
    raw = p20t.RECOVERIES["acb_hot_fourier_3bet_biglotto"]["function"](history)
    result = p20c.prepare_portfolio(
        strategy_id="acb_hot_fourier_3bet_biglotto",
        draw_id="fixture-target",
        replicate_id=0,
        cutoff_identity=history[-1]["draw"],
        raw_tickets=raw,
        actual_numbers=[1, 2, 3, 4, 5, 6],
        constructor_mode=p20c.TICKET_CONSTRUCTOR_V1,
    )
    ordered = result["tickets"]
    prefix_10 = p20t.ordered_portfolio_prefix(ordered, 10)
    prefix_15 = p20t.ordered_portfolio_prefix(ordered, 15)
    prefix_20 = p20t.ordered_portfolio_prefix(ordered, 20)
    assert prefix_10 == prefix_15[:10]
    assert prefix_15 == prefix_20[:15]
    assert prefix_20 == tuple(ordered)
    fixture = p20t.nested_prefix_fixture(ordered)
    assert fixture["pass"] is True
    assert fixture["historical_status"] == {
        "10": "NOT_RUN",
        "15": "NOT_RUN",
        "20": "RUN",
    }
    assert len(set(fixture["portfolio_hashes"].values())) == 3


def test_checkpoint_compatibility_binding_changes_with_ticket_count(tmp_path):
    base = {
        "source_head": "a" * 40,
        "dataset_sha256": "b" * 64,
        "runner_sha256": "c" * 64,
    }
    key_20 = p20t.checkpoint_compatibility_key(**base, target_ticket_count=20)
    key_15 = p20t.checkpoint_compatibility_key(**base, target_ticket_count=15)
    assert key_20["ticket_count"] == 20
    assert key_15["ticket_count"] == 15
    assert p20t.checkpoint_runner_sha256(key_20) != p20t.checkpoint_runner_sha256(
        key_15
    )

    metadata = tmp_path / "checkpoint.json"
    metadata.write_text(
        json.dumps({"runner_sha256": p20t.checkpoint_runner_sha256(key_20)}),
        encoding="utf-8",
    )
    assert (
        p20t.annotate_checkpoint_metadata(
            tmp_path,
            compatibility_key=key_20,
            bound_runner_sha256=p20t.checkpoint_runner_sha256(key_20),
        )
        == 1
    )
    annotated = json.loads(metadata.read_text(encoding="utf-8"))
    assert annotated["ticket_count"] == 20
    assert annotated["p20t_checkpoint_compatibility_key"] == key_20


def test_immutable_execution_record_omits_checkpoint_transport_state():
    execution = {
        "strategy_runs": [
            {
                "strategy_id": "example",
                "checkpoint_reused": True,
                "runtime_seconds": 1.25,
            }
        ],
        "detail_files": [],
    }
    stable = p20t.stable_execution_record(execution)
    assert "checkpoint_reused" not in stable["strategy_runs"][0]
    assert stable["strategy_runs"][0]["runtime_seconds"] == 1.25
    assert execution["strategy_runs"][0]["checkpoint_reused"] is True
    assert not p20t.constructor_reproducibility_pass(
        {
            "sample_count": 12,
            "mismatch_count": 1,
            "mismatched_strategy_ids": ["example"],
        }
    )


@pytest.mark.parametrize(
    ("strategy_id", "native_count"),
    [
        (strategy_id, definition["native"])
        for strategy_id, definition in p20t.RECOVERIES.items()
    ],
)
def test_recovered_generators_emit_legal_native_tickets_and_construct_20(
    strategy_id: str, native_count: int
):
    history = synthetic_draws(500)
    raw = p20t.RECOVERIES[strategy_id]["function"](history)
    assert len(raw) == native_count
    assert len({tuple(ticket) for ticket in raw}) == native_count
    assert all(
        len(ticket) == len(set(ticket)) == 6
        and all(type(number) is int and 1 <= number <= 49 for number in ticket)
        for ticket in raw
    )
    result = p20c.prepare_portfolio(
        strategy_id=strategy_id,
        draw_id="fixture-target",
        replicate_id=0,
        cutoff_identity=history[-1]["draw"],
        raw_tickets=raw,
        actual_numbers=[1, 2, 3, 4, 5, 6],
        constructor_mode=p20c.TICKET_CONSTRUCTOR_V1,
    )
    assert result["ok"] is True
    assert len(result["tickets"]) == len(set(result["tickets"])) == 20


def test_current_source_wrappers_have_direct_parity():
    from tools.backtest_apriori import BacktestApriori
    from tools.backtest_big_lotto_orthogonal_5bet import (
        generate_big_lotto_orthogonal_5bet,
    )
    from tools.backtest_biglotto_5bet_ts3markov import (
        generate_ts3_markov_freq_5bet,
    )
    from tools.backtest_biglotto_hot_stop_rebound import generate_hot_stop_bet
    from tools.backtest_cluster_pivot_biglotto import cluster_pivot_4bet
    from tools.backtest_gap_dynamic_1500 import triple_strike_gap_dynamic
    from tools.backtest_markov_repeat_exception import generate_ts3_markov4

    history = synthetic_draws(500)
    assert recovered.adapt_apriori_3bet(
        history
    ) == BacktestApriori().predict_for_backtest(history, num_bets=3, window=150)
    assert recovered.adapt_biglotto_5bet_orthogonal(
        history
    ) == generate_big_lotto_orthogonal_5bet(history)
    assert recovered.adapt_cluster_pivot_4bet(history) == cluster_pivot_4bet(history)
    assert recovered.adapt_gap_dynamic_threshold(history) == triple_strike_gap_dynamic(
        history, gap_threshold=12, gap_weight=1.0
    )
    assert recovered.adapt_hot_stop_rebound(history) == [
        generate_hot_stop_bet(history, freq_threshold=15, gap_threshold=12)
    ]
    assert recovered.adapt_markov_repeat_exception(history) == generate_ts3_markov4(
        history, markov_window=30, repeat_boost_factor=0.1
    )
    assert recovered.adapt_ts3_markov_freq_5bet(
        history
    ) == generate_ts3_markov_freq_5bet(history, markov_window=30)


def test_zonal_adapter_has_source_parity_without_database_initialization():
    from tools.strategy_leaderboard import StrategyLeaderboard

    history = synthetic_draws(500)
    leaderboard = StrategyLeaderboard.__new__(StrategyLeaderboard)
    leaderboard.max_num = 49
    base_bets = leaderboard.strat_cluster_pivot(history, n_bets=12, window=150)
    coverage = Counter(
        len({(number - 1) // 7 for number in draw["numbers"]})
        for draw in history[-200:]
    )
    typical = {count for count, _ in coverage.most_common(2)}
    expected = []
    for bet in base_bets:
        if len({(number - 1) // 7 for number in bet}) in typical:
            expected.append(bet)
            if len(expected) == 4:
                break
    assert recovered.adapt_biglotto_zonal_pruning(history) == (
        expected or base_bets[:4]
    )
    with pytest.raises(ValueError, match="expected 4 bets, got 3"):
        recovered.adapt_biglotto_zonal_pruning(synthetic_draws(104))


def test_historical_adapter_fixtures_are_frozen_to_recovered_outputs():
    history = synthetic_draws(500)
    assert recovered.adapt_acb_hot_fourier_3bet(history) == [
        [6, 18, 30, 39, 48, 49],
        [2, 5, 13, 23, 32, 43],
        [5, 10, 14, 24, 36, 43],
    ]
    assert recovered.adapt_neighbor_injection(history) == [
        [5, 10, 14, 24, 36, 44],
        [6, 7, 18, 30, 39, 49],
        [4, 15, 21, 23, 32, 46],
    ]
    assert recovered.adapt_ts3_acb_4bet(history)[-1] == [6, 18, 28, 31, 39, 49]
    assert recovered.adapt_biglotto_10bet_combined(history) == [
        [5, 10, 14, 24, 36, 44],
        [6, 7, 18, 30, 39, 49],
        [4, 15, 21, 23, 32, 46],
        [3, 8, 9, 12, 13, 34],
        [2, 22, 31, 33, 42, 43],
        [4, 7, 9, 14, 36, 43],
        [6, 17, 18, 19, 40, 49],
        [2, 3, 5, 13, 23, 32],
        [11, 16, 26, 28, 30, 31],
        [1, 15, 24, 27, 37, 45],
    ]
    assert recovered.adapt_predict_biglotto_regime_3bet(history)[0] == [
        5,
        10,
        14,
        24,
        36,
        44,
    ]


def test_regime_adapter_fixtures_cover_historical_neutral_high_and_low_paths():
    base = synthetic_draws(500)
    high = base[:-5] + [
        {**draw, "numbers": [39, 41, 43, 45, 47, 49]} for draw in base[-5:]
    ]
    low = base[:-5] + [{**draw, "numbers": [1, 2, 3, 4, 5, 6]} for draw in base[-5:]]
    assert recovered.adapt_predict_biglotto_regime_3bet(base) == [
        [5, 10, 14, 24, 36, 44],
        [6, 7, 18, 30, 39, 49],
        [4, 15, 21, 23, 32, 46],
    ]
    assert recovered.adapt_predict_biglotto_regime_3bet(high) == [
        [5, 14, 20, 24, 32, 36],
        [15, 16, 17, 18, 19, 25],
        [4, 12, 41, 43, 45, 47],
    ]
    assert recovered.adapt_predict_biglotto_regime_3bet(low) == [
        [32, 34, 36, 43, 44, 45],
        [26, 28, 29, 30, 35, 37],
        [1, 2, 3, 4, 5, 6],
    ]


def test_orthogonal_5bet_is_not_silently_reclassified_as_ts3_markov_equivalent():
    history = synthetic_draws(500)
    assert recovered.adapt_biglotto_5bet_orthogonal(
        history
    ) != recovered.adapt_ts3_markov_freq_5bet(history)


def test_all_recovered_specs_pass_target_and_future_invariance():
    draws = synthetic_draws()
    original_mapping = dict(p20s.SPEC_TO_IDENTITY)
    try:
        p20s.SPEC_TO_IDENTITY.update(
            {strategy_id: strategy_id for strategy_id in p20t.RECOVERIES}
        )
        specs = p20t.build_strategy_specs(random_replicates=2)
        rows = p20s.preflight_executable_specs(draws, specs)
    finally:
        p20s.SPEC_TO_IDENTITY.clear()
        p20s.SPEC_TO_IDENTITY.update(original_mapping)
    assert len(rows) == len(p20t.RECOVERIES)
    assert all(row["preflight_status"] == "PASS" for row in rows)
    assert all(row["target_mutation_invariant"] is True for row in rows)
    assert all(row["future_mutation_invariant"] is True for row in rows)
    assert all(row["final_ticket_count"] == 20 for row in rows)


def test_terminal_exclusions_are_conclusive_and_do_not_invent_logic():
    assert set(p20t.TERMINAL_DECISIONS) == {
        "bet2_fourier_expansion_biglotto@rejected_json_historical",
        "biglotto_zonal_pruning",
        "hot_gap_return_biglotto",
        "multiwindow_fourier_biglotto",
    }
    assert all(
        decision["final"]
        in {
            "INSUFFICIENT_ALGORITHM_SPECIFICATION",
            "MISSING_IMPLEMENTATION_CONFIRMED",
            "OTHER_EVIDENCED_TERMINAL_EXCLUSION",
        }
        and decision["evidence"]
        for decision in p20t.TERMINAL_DECISIONS.values()
    )


def test_output_contract_is_complete_and_has_no_raw_detail_artifact():
    assert len(p20t.REQUIRED_OUTPUTS) == 17
    assert "final_39_resolution_ledger.csv" in p20t.REQUIRED_OUTPUTS
    assert "ticket_count_capability.csv" in p20t.REQUIRED_OUTPUTS
    assert "nested_portfolio_capability.csv" in p20t.REQUIRED_OUTPUTS
    assert "run_manifest.json" in p20t.REQUIRED_OUTPUTS
    assert not any("detail" in name for name in p20t.REQUIRED_OUTPUTS)


def test_metric_and_capability_schemas_are_ticket_count_aware():
    assert {
        "ticket_count",
        "common_window_draws",
        "random_m4plus_rate_same_ticket_count",
        "random_baseline_ticket_count",
        "nested_prefix_supported",
        "nested_prefix_failure_reason",
    } <= set(p20t.METRIC_FIELDS)
    assert set(p20t.TICKET_COUNT_CAPABILITY_FIELDS) == {
        "strategy_id",
        "ticket_count_10_supported_by_interface",
        "ticket_count_15_supported_by_interface",
        "ticket_count_20_supported",
        "nested_prefix_supported",
        "nested_prefix_failure_reason",
        "current_authoritative_ticket_count",
        "historical_10_status",
        "historical_15_status",
        "historical_20_status",
    }
    assert {"external_state_dependency", "historical_cutoff_support"} <= set(
        p20t.SEARCH_FIELDS
    )
    assert {
        "ticket_count",
        "prior_failure_classification",
        "reproduced_cause",
        "repair_classification",
        "nested_prefix_supported",
    } <= set(p20t.PARTIAL_FIELDS)


def test_all_39_identities_receive_explicit_ticket_capability():
    final_inventory = p20t.read_csv(
        p20t.DEFAULT_OUTPUT_DIR / "final_39_resolution_ledger.csv"
    )
    integrated_metrics = p20t.read_csv(
        p20t.DEFAULT_OUTPUT_DIR / "final_39_completed_strategy_metrics.csv"
    )
    ticket_rows = p20t.build_ticket_count_capability_rows(
        final_inventory, integrated_metrics
    )
    nested_rows = p20t.build_nested_portfolio_capability_rows(
        final_inventory, integrated_metrics
    )
    assert len(ticket_rows) == len(nested_rows) == 39
    assert {row["strategy_id"] for row in ticket_rows} == set(p20t.TARGET_IDS) | {
        row["strategy_id"]
        for row in final_inventory
        if row["strategy_id"] not in p20t.TARGET_IDS
    }
    assert all(row["historical_10_status"] == "NOT_RUN" for row in ticket_rows)
    assert all(row["historical_15_status"] == "NOT_RUN" for row in ticket_rows)
    assert sum(bool(row["nested_prefix_supported"]) for row in nested_rows) == 30
