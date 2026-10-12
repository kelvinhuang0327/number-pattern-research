from __future__ import annotations

import csv
import json
from fractions import Fraction
from pathlib import Path

import pytest

from scripts import p20c_strategy_preserving_20_ticket_backtest as p20c
from scripts import p20u_multi_ticket_count_m4plus_analysis as p20u


def legal_twenty() -> list[list[int]]:
    return [
        sorted({((index + offset * 7) % 49) + 1 for offset in range(6)})
        for index in range(20)
    ]


def synthetic_draws(count: int = 102) -> list[dict[str, object]]:
    return [
        {
            "draw": str(96000001 + index),
            "date": f"2007/01/{(index % 28) + 1:02d}",
            "numbers": [1, 2, 3, 4, 5, 6],
            "special": 7,
            "id": index + 1,
        }
        for index in range(count)
    ]


def fake_entry(call_counter: list[int] | None = None) -> p20u.ExecutionIdentity:
    tickets = legal_twenty()

    def generator(history, target, replicate, seed):
        del history, target, replicate, seed
        if call_counter is not None:
            call_counter[0] += 1
        return tickets

    spec = p20c.StrategySpec(
        strategy_id="fake_strategy",
        strategy_name="Fake Strategy",
        governance_status="candidate",
        min_history=0,
        replicates=1,
        execution_mode="test",
        ranking_group="native",
        formerly_partial=False,
        generator=generator,
    )
    governance = {
        "strategy_id": "fake_strategy",
        "strategy_name": "Fake Strategy",
        "governance_status": "UNKNOWN",
        "independent_algorithm_id": "fake_strategy",
        "alias_of": "",
        "equivalence_group": "",
        "terminal_disposition": "COMPLETE_NATIVE_20",
    }
    return p20u.ExecutionIdentity(
        "fake_strategy", spec, governance, {"effective_strategy_id": "fake_strategy"}
    )


def test_authorized_ticket_counts_are_exact() -> None:
    assert p20u.validate_ticket_counts([10, 15, 20]) == (10, 15, 20)


@pytest.mark.parametrize("counts", ([10, 10, 20], [10, 15, 15]))
def test_duplicate_ticket_counts_are_rejected(counts) -> None:
    with pytest.raises(ValueError, match="duplicate"):
        p20u.validate_ticket_counts(counts)


@pytest.mark.parametrize("counts", ([0, 15, 20], [-10, 15, 20], [True, 15, 20]))
def test_nonpositive_or_boolean_ticket_counts_are_rejected(counts) -> None:
    with pytest.raises(ValueError, match="positive integers"):
        p20u.validate_ticket_counts(counts)


def test_ticket_count_over_twenty_is_rejected() -> None:
    with pytest.raises(ValueError, match="exceeds"):
        p20u.validate_ticket_counts([10, 15, 21])


def test_incomplete_ticket_count_set_is_rejected() -> None:
    with pytest.raises(ValueError, match="exactly"):
        p20u.validate_ticket_counts([10, 20])


def test_prefixes_are_nested_without_reordering() -> None:
    tickets = legal_twenty()
    prefixes = p20u.ordered_prefixes(tickets)
    assert prefixes[10] == tuple(tuple(row) for row in tickets[:10])
    assert prefixes[15][:10] == prefixes[10]
    assert prefixes[20][:15] == prefixes[15]


def test_duplicate_portfolio_ticket_is_rejected() -> None:
    tickets = legal_twenty()
    tickets[-1] = tickets[0]
    with pytest.raises(ValueError, match="unique"):
        p20u.ordered_prefixes(tickets)


@pytest.mark.parametrize(
    "field,value",
    (
        ("strategy_id", "other"),
        ("effective_strategy_id", "other@sp20_v1"),
        ("ticket_count", 15),
        ("target_draw", "96000104"),
        ("replicate_id", 1),
        ("source_head", "def456"),
        ("constructor_version", "other/v2"),
    ),
)
def test_count_hash_binds_every_identity_field(field, value) -> None:
    arguments = {
        "strategy_id": "strategy",
        "effective_strategy_id": "strategy@sp20_v1",
        "ticket_count": 10,
        "target_draw": "96000103",
        "replicate_id": 0,
        "source_head": "abc123",
        "constructor_version": "constructor/v1",
        "tickets": legal_twenty(),
    }
    original = p20u.ticket_count_portfolio_sha256(**arguments)
    arguments[field] = value
    changed = p20u.ticket_count_portfolio_sha256(**arguments)
    assert changed != original


def test_count_hash_is_reproducible() -> None:
    arguments = {
        "strategy_id": "strategy",
        "effective_strategy_id": "strategy@sp20_v1",
        "ticket_count": 15,
        "target_draw": "96000103",
        "replicate_id": 0,
        "source_head": "abc123",
        "constructor_version": "constructor/v1",
        "tickets": legal_twenty(),
    }
    assert p20u.ticket_count_portfolio_sha256(
        **arguments
    ) == p20u.ticket_count_portfolio_sha256(**arguments)


def test_m4plus_uses_four_main_numbers_not_special() -> None:
    tickets = legal_twenty()
    tickets[0] = [1, 2, 3, 7, 8, 9]
    score = p20u.score_nested_portfolio(tickets, [1, 2, 3, 4, 5, 6])
    assert score["max_main_hits_10"] == 3
    assert score["m4plus_10"] == 0


def test_multiple_qualifying_tickets_count_once_per_portfolio() -> None:
    tickets = legal_twenty()
    tickets[0] = [1, 2, 3, 4, 20, 21]
    tickets[1] = [1, 2, 3, 4, 22, 23]
    score = p20u.score_nested_portfolio(tickets, [1, 2, 3, 4, 5, 6])
    assert score["m4plus_10"] == 1


def test_nested_m4plus_and_marginal_indicators() -> None:
    tickets = legal_twenty()
    for index in range(20):
        tickets[index] = [10, 11, 12, 13, 14, 15]
        tickets[index][-1] = 15 + index
    tickets[12] = [1, 2, 3, 4, 40, 41]
    tickets[18] = [1, 2, 3, 4, 42, 43]
    score = p20u.score_nested_portfolio(tickets, [1, 2, 3, 4, 5, 6])
    assert (score["m4plus_10"], score["m4plus_15"], score["m4plus_20"]) == (
        0,
        1,
        1,
    )
    assert score["incremental_10_to_15"] == 1
    assert score["incremental_15_to_20"] == 0
    assert score["incremental_10_to_20"] == 1


def test_paired_draw_differences_use_draw_means() -> None:
    strategy = [
        {"target_draw": "1", "m4plus": 1},
        {"target_draw": "1", "m4plus": 0},
        {"target_draw": "2", "m4plus": 0},
    ]
    baseline = [
        {"target_draw": "1", "m4plus": 0},
        {"target_draw": "1", "m4plus": 0},
        {"target_draw": "2", "m4plus": 1},
    ]
    assert p20u.paired_draw_differences(strategy, baseline) == [
        Fraction(1, 2),
        Fraction(-1, 1),
    ]


@pytest.mark.parametrize(
    "differences,expected",
    (
        ([Fraction(0)], 1.0),
        ([Fraction(1)], 0.5),
        ([Fraction(1), Fraction(1)], 0.25),
        ([Fraction(-1)], 1.0),
    ),
)
def test_exact_sign_flip_p_values(differences, expected) -> None:
    assert p20u.exact_one_sided_sign_flip_p_value(differences) == expected


def test_bh_adjustment_is_monotone_in_rank() -> None:
    assert p20u.adjust_bh([0.01, 0.04, 0.03]) == pytest.approx([0.03, 0.04, 0.04])


def test_confirmatory_family_is_frozen_at_ninety() -> None:
    metrics = []
    for index in range(30):
        for count in p20u.TICKET_COUNTS:
            metrics.append(
                {
                    "strategy_id": f"s{index:02d}",
                    "independent_algorithm_id": f"a{index:02d}",
                    "ticket_count": count,
                    "paired_p_value": 0.01,
                    "_paired_ci_low": 0.001,
                }
            )
    p20u.apply_multiplicity(metrics)
    assert len(metrics) == 90
    assert all(
        row["multiplicity_adjusted_p_value"] == pytest.approx(0.9) for row in metrics
    )


def test_aliases_cannot_expand_confirmatory_family() -> None:
    metrics = []
    for index in range(30):
        for count in p20u.TICKET_COUNTS:
            metrics.append(
                {
                    "strategy_id": f"s{index:02d}",
                    "independent_algorithm_id": "a00"
                    if index == 1
                    else f"a{index:02d}",
                    "ticket_count": count,
                    "paired_p_value": 0.5,
                    "_paired_ci_low": -0.01,
                }
            )
    with pytest.raises(p20u.ContractError, match="family drift"):
        p20u.apply_multiplicity(metrics)


def test_checkpoint_key_contains_complete_contract() -> None:
    entry = fake_entry()
    key = p20u.checkpoint_compatibility_key(
        source_head="abc",
        dataset_digest="dataset",
        database_digest="database",
        runner_source_sha256="runner",
        entry=entry,
        common_window_draws=2,
    )
    assert key["source_head"] == "abc"
    assert key["dataset_digest"] == "dataset"
    assert key["database_digest"] == "database"
    assert key["constructor_version"] == p20u.CONSTRUCTOR_IDENTIFIER
    assert key["runner_version"] == p20u.RUNNER_VERSION
    assert key["strategy_identity"] == "fake_strategy"
    assert key["effective_strategy_identity"] == "fake_strategy"
    assert key["ticket_counts"] == [10, 15, 20]
    assert key["random_replicates"] == 10
    assert key["portfolio_ordering_contract"] == p20u.PORTFOLIO_ORDERING_CONTRACT
    assert key["metric_contract_version"] == p20u.METRIC_CONTRACT_VERSION


def test_checkpoint_rejects_any_changed_key() -> None:
    expected = {"source_head": "abc", "ticket_counts": [10, 15, 20]}
    assert p20u.checkpoint_compatible(dict(expected), expected)
    assert not p20u.checkpoint_compatible(
        {"source_head": "def", "ticket_counts": [10, 15, 20]}, expected
    )
    assert not p20u.checkpoint_compatible(
        {"source_head": "abc", "ticket_counts": [10, 20]}, expected
    )


def test_fresh_and_resumed_checkpoint_are_byte_identical(tmp_path: Path) -> None:
    entry = fake_entry()
    draws = synthetic_draws()
    arguments = {
        "entry": entry,
        "draws": draws,
        "checkpoint_dir": tmp_path,
        "source_head": "abc123",
        "dataset_digest": "dataset",
        "database_digest": "database",
        "runner_source_sha256": "runner",
        "timeout_seconds": 30,
    }
    fresh = p20u.execute_identity(**arguments, resume=False)
    resumed = p20u.execute_identity(**arguments, resume=True)
    assert fresh["checkpoint_reused"] is False
    assert resumed["checkpoint_reused"] is True
    assert p20u.stable_run_records([fresh]) == p20u.stable_run_records([resumed])
    assert (
        Path(fresh["detail_path"]).read_bytes()
        == Path(resumed["detail_path"]).read_bytes()
    )


def test_portfolio_is_generated_once_per_draw_not_once_per_count(
    tmp_path: Path,
) -> None:
    calls = [0]
    entry = fake_entry(calls)
    p20u.execute_identity(
        entry=entry,
        draws=synthetic_draws(),
        checkpoint_dir=tmp_path,
        source_head="abc123",
        dataset_digest="dataset",
        database_digest="database",
        runner_source_sha256="runner",
        timeout_seconds=30,
        resume=False,
    )
    assert calls[0] == 2


def test_target_outcome_mutation_cannot_change_portfolio() -> None:
    entry = fake_entry()
    draws = synthetic_draws()
    history = draws[:100]
    target = dict(draws[100])
    seed = p20c.stable_seed(
        p20u.SEED_NAMESPACE, entry.spec.strategy_id, target["draw"], 0
    )
    first = p20u._construct_portfolio(entry, history, target, 0, seed)
    target["numbers"] = [44, 45, 46, 47, 48, 49]
    target["special"] = 1
    second = p20u._construct_portfolio(entry, history, target, 0, seed)
    assert first["tickets"] == second["tickets"]


def test_detail_independent_recomputation_passes(tmp_path: Path) -> None:
    entry = fake_entry()
    run = p20u.execute_identity(
        entry=entry,
        draws=synthetic_draws(),
        checkpoint_dir=tmp_path,
        source_head="abc123",
        dataset_digest="dataset",
        database_digest="database",
        runner_source_sha256="runner",
        timeout_seconds=30,
        resume=False,
    )
    result = p20u.validate_detail_file(run, entry, "abc123")
    assert result["all_pass"] is True
    assert result["detail_rows"] == 2


def test_normalized_full20_digest_is_stable(tmp_path: Path) -> None:
    entry = fake_entry()
    run = p20u.execute_identity(
        entry=entry,
        draws=synthetic_draws(),
        checkpoint_dir=tmp_path,
        source_head="abc123",
        dataset_digest="dataset",
        database_digest="database",
        runner_source_sha256="runner",
        timeout_seconds=30,
        resume=False,
    )
    first = p20u.normalized_full20_digest(Path(run["detail_path"]))
    second = p20u.normalized_full20_digest(Path(run["detail_path"]))
    assert first == second


def test_zero_increment_efficiency_has_explicit_status() -> None:
    metrics = [
        {
            "strategy_id": "s",
            "ticket_count": 10,
            "m4plus_rate": 0.01,
        }
    ]
    marginals = [
        {
            "strategy_id": "s",
            "from_ticket_count": 10,
            "to_ticket_count": 15,
            "incremental_m4plus_rate": 0.0,
        }
    ]
    rows = p20u.ticket_efficiency_rows(metrics, marginals)
    marginal = next(row for row in rows if row["metric_scope"] == "marginal")
    assert marginal["status"] == "NO_INCREMENTAL_SUCCESSES"
    assert marginal["extra_tickets_per_additional_m4plus_success"] == "NOT_APPLICABLE"


def test_ranking_matches_p20t_governed_identity_tie_break() -> None:
    rows = [
        {
            "strategy_id": "z",
            "effective_strategy_id": "a",
            "ticket_count": 20,
            "m4plus_rate": 0.01,
            "m4plus_hits": 2,
        },
        {
            "strategy_id": "a",
            "effective_strategy_id": "z",
            "ticket_count": 20,
            "m4plus_rate": 0.01,
            "m4plus_hits": 2,
        },
    ]
    ranked = p20u.ranked_metric_rows(rows, 20)
    assert [row["strategy_id"] for row in ranked] == ["a", "z"]


def test_random_parity_uses_unrounded_interval_bounds() -> None:
    current = {
        "complete_portfolios": 20250,
        "m4plus_hits": 412,
        "m4plus_rate": 0.02034567901234568,
        "m4plus_confidence_interval_95": "[0.018469135802,0.022320987654]",
        "_ci_low": 0.018469135802469235,
        "_ci_high": 0.022320987654321143,
    }
    upstream = {
        "evaluated_portfolios": 20250,
        "m4plus_draw_hits": 412,
        "m4plus_draw_rate": 0.02034567901234568,
        "m4plus_ci95_low": 0.018469135802469235,
        "m4plus_ci95_high": 0.022320987654321143,
    }
    assert p20u.random_metric_matches_upstream(current, upstream)


def test_ranked_20_ticket_slice_reproduces_p20t_ranking() -> None:
    metrics = p20u.read_csv(p20u.P20T_DIR / "final_39_completed_strategy_metrics.csv")
    upstream = sorted(
        p20u.read_csv(p20u.P20T_DIR / "final_39_m4plus_all_valid_ranking.csv"),
        key=lambda row: int(row["rank"]),
    )
    assert [row["strategy_id"] for row in p20u.ranked_metric_rows(metrics, 20)] == [
        row["strategy_id"] for row in upstream
    ]


def test_frozen_universe_is_exactly_30_plus_9() -> None:
    universe = p20u.load_frozen_universe()
    assert len(universe["completed_ids"]) == 30
    assert len(set(universe["completed_ids"])) == 30
    assert len(universe["excluded_ids"]) == 9
    assert not set(universe["completed_ids"]) & set(universe["excluded_ids"])


def test_execution_specs_equal_frozen_completed_set() -> None:
    universe = p20u.load_frozen_universe()
    entries = p20u.build_execution_identities(universe)
    strategy_ids = {
        entry.strategy_id for entry in entries if entry.spec.ranking_group != "baseline"
    }
    assert strategy_ids == set(universe["completed_ids"])
    assert len(entries) == 31


def test_random_baseline_is_outside_governed_universe() -> None:
    universe = p20u.load_frozen_universe()
    assert "baseline::uniform_random_20" not in universe["completed_ids"]
    assert "baseline::uniform_random_20" not in universe["excluded_ids"]


def test_native_metric_series_excludes_constructor_fallback_rows() -> None:
    entry = fake_entry()
    native_row = {
        "target_draw": "1",
        "replicate_id": 0,
        "effective_strategy_id": "fake_strategy",
        "m4plus": 1,
    }
    fallback_row = {
        "target_draw": "2",
        "replicate_id": 0,
        "effective_strategy_id": f"fake_strategy@{p20c.SHORT_IDENTIFIER}",
        "m4plus": 0,
    }
    series = {
        "counts": {
            count: [dict(native_row), dict(fallback_row)]
            for count in p20u.TICKET_COUNTS
        },
        "marginals": {
            transition: [dict(native_row), dict(fallback_row)]
            for transition in p20u.MARGINAL_TRANSITIONS
        },
        "effective_ids": {
            "fake_strategy",
            f"fake_strategy@{p20c.SHORT_IDENTIFIER}",
        },
    }
    filtered = p20u.metric_eligible_series(entry, series)
    assert all(len(rows) == 1 for rows in filtered["counts"].values())
    assert all(len(rows) == 1 for rows in filtered["marginals"].values())
    assert all(
        row["effective_strategy_id"] == "fake_strategy"
        for rows in filtered["counts"].values()
        for row in rows
    )


def test_all_completed_strategies_are_independent_representatives() -> None:
    universe = p20u.load_frozen_universe()
    algorithms = {row["independent_algorithm_id"] for row in universe["completed"]}
    assert len(algorithms) == 30


def test_pre_run_manifest_freezes_exact_ids_before_execution() -> None:
    universe = p20u.load_frozen_universe()
    manifest = p20u.pre_run_manifest(
        source_head="code",
        origin_main="main",
        p20t_manifest_sha256="manifest",
        p20t_tree_digest="tree",
        dataset_sha256="dataset",
        database_sha256="database",
        completed_ids=universe["completed_ids"],
        excluded_ids=universe["excluded_ids"],
    )
    assert manifest["status"] == "PREPARED_BEFORE_HISTORICAL_EXECUTION"
    assert manifest["completed_strategy_ids"] == universe["completed_ids"]
    assert manifest["completed_strategy_count"] == 30
    assert manifest["excluded_strategy_count"] == 9
    assert manifest["confirmatory_family_size"] == 90


def test_verification_summary_rejects_failures() -> None:
    with pytest.raises(ValueError, match="failures"):
        p20u.parse_verification_summary(
            json.dumps(
                {
                    "passed": 1,
                    "failed": 1,
                    "skipped": 0,
                    "deselected": 0,
                    "commands": ["pytest"],
                }
            )
        )


def test_quality_contract_accepts_known_clean_shape() -> None:
    quality = {
        "canonical_main_rows": 2125,
        "common_window_rows": 2025,
        "duplicate_draw_ids": 0,
        "duplicate_dates": 0,
        "invalid_json_rows": 0,
        "wrong_main_number_count_rows": 0,
        "out_of_range_rows": 0,
        "duplicate_main_number_rows": 0,
        "invalid_or_overlapping_special_rows": 0,
        "negative_financial_rows": 0,
        "outside_selected_window_rows": 0,
        "date_format_counts": {"YYYY/MM/DD": 2125},
    }
    assert p20u.quality_pass(quality)


def test_required_outputs_include_every_authorized_artifact() -> None:
    assert len(p20u.REQUIRED_OUTPUTS) == 21
    assert "run_manifest.json" in p20u.REQUIRED_OUTPUTS
    assert "strategy_ticket_count_metrics.csv" in p20u.REQUIRED_OUTPUTS
    assert "marginal_gain_10_to_15.csv" in p20u.REQUIRED_OUTPUTS
    assert "marginal_gain_15_to_20.csv" in p20u.REQUIRED_OUTPUTS
    assert "marginal_gain_10_to_20.csv" in p20u.REQUIRED_OUTPUTS
    assert "validation_results.json" in p20u.REQUIRED_OUTPUTS
    assert "final_report.md" in p20u.REQUIRED_OUTPUTS


def test_p20t_predecessor_manifest_hash_is_frozen() -> None:
    assert p20u.sha256_file(p20u.P20T_MANIFEST) == (
        "12abef07b6223de3661aae6def9e40bbe56a2771a26824649e1aa255e273d46c"
    )


def test_detail_csv_has_no_ticket_count_specific_regeneration_columns(
    tmp_path: Path,
) -> None:
    entry = fake_entry()
    run = p20u.execute_identity(
        entry=entry,
        draws=synthetic_draws(),
        checkpoint_dir=tmp_path,
        source_head="abc123",
        dataset_digest="dataset",
        database_digest="database",
        runner_source_sha256="runner",
        timeout_seconds=30,
        resume=False,
    )
    with p20u.gzip.open(
        run["detail_path"], "rt", encoding="utf-8", newline=""
    ) as handle:
        header = next(csv.reader(handle))
    assert "ordered_tickets_20_json" in header
    assert "ordered_tickets_10_json" not in header
    assert "ordered_tickets_15_json" not in header
