from __future__ import annotations

import json
from pathlib import Path

import pytest

from lottery_api.models.strategy_preserving_20_ticket import ConstructorSuccess
from scripts import p20c_strategy_preserving_20_ticket_backtest as p20c
from scripts import p20s_all_strategies_bulk_recovery as p20s


def synthetic_draws(count: int = 620) -> list[dict]:
    draws = []
    for index in range(count):
        start = (index * 7) % 49
        numbers = sorted({((start + offset * 8) % 49) + 1 for offset in range(6)})
        if len(numbers) != 6:
            raise AssertionError("synthetic fixture did not produce six unique numbers")
        draws.append(
            {
                "id": index + 1,
                "draw": str(96000001 + index),
                "date": f"2007/{1 + (index // 28) % 12:02d}/{1 + index % 28:02d}",
                "numbers": numbers,
                "special": next(number for number in range(1, 50) if number not in numbers),
            }
        )
    return draws


def test_governed_denominator_is_unique_and_baseline_is_separate():
    inventory = p20s.build_master_inventory()
    ids = [row["strategy_id"] for row in inventory]

    assert len(inventory) == p20s.EXPECTED_IDENTITY_COUNT == 39
    assert len(ids) == len(set(ids))
    assert "baseline::uniform_random_20" not in ids
    assert all(row["game"] == "BIG_LOTTO" for row in inventory)
    assert all(row["terminal_disposition"] in p20s.TERMINAL_DISPOSITIONS for row in inventory)


def test_evidence_records_do_not_inflate_strategy_denominator():
    inventory = p20s.build_master_inventory()
    ledger = p20s.build_resolution_ledger()

    assert len(ledger) == p20s.EXPECTED_EVIDENCE_RECORDS == 607
    assert len(inventory) == 39
    assert any(row["source_identity"] == "tools/advanced_methods_benchmark.py" for row in ledger)
    assert not any(row["strategy_id"] == "history::tools/advanced_methods_benchmark.py" for row in inventory)
    assert sum(row["evidence_kind"] == "historical_source_surface" for row in ledger) == 580
    assert sum(row["evidence_kind"] == "governance_record" for row in ledger) == 27


def test_aliases_equivalents_and_id_reuse_are_explicit():
    inventory = {row["strategy_id"]: row for row in p20s.build_master_inventory()}
    counts = p20s.inventory_counts(list(inventory.values()))

    assert counts["aliases"] == 2
    assert counts["equivalent_implementations"] == 3
    assert inventory["ts3_acb_4bet_biglotto"]["alias_of"] == "biglotto_ts3_acb_4bet"
    assert inventory["core_satellite_biglotto"]["equivalence_group"] == "core_satellite_family"
    assert "bet2_fourier_expansion_biglotto@p42_p280_frozen_code" in inventory
    assert "bet2_fourier_expansion_biglotto@rejected_json_historical" in inventory
    assert (
        inventory["bet2_fourier_expansion_biglotto@p42_p280_frozen_code"]["independent_algorithm_id"]
        != inventory["bet2_fourier_expansion_biglotto@rejected_json_historical"]["independent_algorithm_id"]
    )


def test_execution_specs_cover_exactly_the_rankable_identities():
    specs = p20s.build_strategy_specs(10)
    real = [spec for spec in specs if spec.ranking_group != "baseline"]
    baseline = [spec for spec in specs if spec.ranking_group == "baseline"]

    assert len(baseline) == 1
    assert baseline[0].strategy_id == "baseline::uniform_random_20"
    assert len(real) == 18
    assert len({p20s.SPEC_TO_IDENTITY[spec.strategy_id] for spec in real}) == 18
    assert [spec.strategy_id for spec in real] == sorted(spec.strategy_id for spec in real)


@pytest.mark.parametrize(
    "strategy_id,expected_native",
    [
        ("biglotto_p0_2bet", 2),
        ("predict_biglotto_echo_2bet", 2),
        ("predict_biglotto_echo_phase2", 3),
        ("predict_biglotto_mixed_3bet", 3),
    ],
)
def test_recovered_adapters_preserve_native_output_and_construct_20(strategy_id, expected_native):
    draws = synthetic_draws()
    spec = next(spec for spec in p20s.build_strategy_specs(10) if spec.strategy_id == strategy_id)
    target_index = max(spec.min_history, 100)
    history = draws[:target_index]
    target = draws[target_index]
    seed = p20c.stable_seed("p20s-test", strategy_id, target["draw"])

    first = spec.generator(history, target, 0, seed)
    second = spec.generator(history, {**target, "numbers": [1, 2, 3, 4, 5, 6]}, 0, seed)
    assert first == second
    assert len(first) == expected_native
    assert p20s._legal_native(first)

    portfolio = p20c.prepare_portfolio(
        strategy_id=strategy_id,
        draw_id=target["draw"],
        replicate_id=0,
        cutoff_identity=history[-1]["draw"],
        raw_tickets=first,
        actual_numbers=target["numbers"],
        constructor_mode=p20c.TICKET_CONSTRUCTOR_V1,
    )
    assert portfolio["ok"]
    assert len(portfolio["tickets"]) == 20
    assert len(set(portfolio["tickets"])) == 20
    assert set(map(tuple, first)).issubset(set(portfolio["tickets"]))
    assert isinstance(portfolio["metadata"], object)
    assert portfolio["metadata"].constructor_name == p20c.CONSTRUCTOR_NAME
    assert portfolio["metadata"].constructor_version == p20c.CONSTRUCTOR_VERSION


def test_full_executable_preflight_enforces_target_and_future_invariance():
    rows = p20s.preflight_executable_specs(synthetic_draws(), p20s.build_strategy_specs(10))

    assert len(rows) == 18
    assert all(row["preflight_status"] == "PASS" for row in rows)
    assert all(row["target_mutation_invariant"] for row in rows)
    assert all(row["future_mutation_invariant"] for row in rows)
    assert all(row["native_output_valid"] for row in rows)
    assert all(row["final_ticket_count"] == 20 for row in rows)


def test_full_preflight_has_one_terminal_row_per_identity():
    inventory = p20s.build_master_inventory()
    executable = p20s.preflight_executable_specs(synthetic_draws(), p20s.build_strategy_specs(10))
    rows = p20s.full_preflight(inventory, executable)

    assert len(rows) == 39
    assert len({row["strategy_id"] for row in rows}) == 39
    assert sum(row["preflight_status"] == "PASS" for row in rows) == 18
    assert sum(row["preflight_status"] == "PARTIAL_EVIDENCE_ONLY" for row in rows) == 4
    assert sum(row["preflight_status"] == "TERMINAL_RESOLUTION" for row in rows) == 17


def test_checkpoint_header_rejects_every_incompatible_boundary():
    expected = p20s.checkpoint_header(
        head="head-a",
        dataset_sha256="data-a",
        runner_sha256="runner-a",
        strategy_id="strategy-a",
    )
    assert p20s.checkpoint_compatible(dict(expected), expected)

    for key in (
        "source_head",
        "dataset_sha256",
        "constructor_version",
        "runner_version",
        "runner_sha256",
        "strategy_id",
    ):
        mutated = dict(expected)
        mutated[key] = "different"
        assert not p20s.checkpoint_compatible(mutated, expected)


def test_one_strategy_failure_does_not_stop_checkpoint_batch(tmp_path: Path):
    draws = synthetic_draws(8)

    def bad(history, target, replicate, seed):
        del history, target, replicate, seed
        raise RuntimeError("isolated failure")

    def good(history, target, replicate, seed):
        del history, target, replicate, seed
        return [[1, 2, 3, 4, 5, 6]]

    specs = [
        p20c.StrategySpec("bad", "bad", "candidate", 1, 1, "fixture", "adapter", True, bad),
        p20c.StrategySpec("good", "good", "candidate", 1, 1, "fixture", "adapter", True, good),
    ]
    original = dict(p20s.SPEC_TO_IDENTITY)
    p20s.SPEC_TO_IDENTITY.update({"bad": "bad", "good": "good"})
    try:
        observations, failures, execution = p20s.execute_with_checkpoints(
            draws=draws,
            specs=specs,
            checkpoint_dir=tmp_path / "checkpoints",
            head="head",
            dataset_sha256="dataset",
            runner_sha256="runner",
            timeout_seconds=10,
            resume=False,
        )
    finally:
        p20s.SPEC_TO_IDENTITY.clear()
        p20s.SPEC_TO_IDENTITY.update(original)

    assert failures
    assert any(row["base_strategy_id"] == "bad" for row in observations)
    good_rows = [row for row in observations if row["base_strategy_id"] == "good"]
    assert good_rows
    assert all(row["final_ticket_count"] == 20 for row in good_rows)
    assert len(execution["strategy_runs"]) == 2


def test_finalization_keeps_aliases_out_of_complete_counts():
    inventory = p20s.build_master_inventory()
    synthetic_metrics = []
    for spec_id, identity_id in p20s.SPEC_TO_IDENTITY.items():
        synthetic_metrics.append(
            {
                "strategy_id": identity_id,
                "completion_rate": 1.0,
                "ranking_group": "native" if spec_id in {
                    "history::lottery_api/models/core_satellite.py",
                    "history::lottery_api/models/zone_split.py",
                } else "adapter",
                "native_ticket_count": 20 if "history::" in spec_id else 3,
            }
        )
    final = p20s.finalize_inventory(inventory, synthetic_metrics)
    counts = p20s.inventory_counts(final)

    assert counts["total_complete"] == 18
    assert counts["native_20_ticket"] == 2
    assert counts["adapter_20_ticket"] == 16
    assert counts["aliases"] == 2
    assert counts["equivalent_implementations"] == 3


def test_verification_evidence_fails_closed_on_missing_fields(tmp_path: Path):
    path = tmp_path / "verification.json"
    path.write_text(json.dumps({"status": "PASS"}), encoding="utf-8")
    with pytest.raises(ValueError, match="missing fields"):
        p20s.load_verification_evidence(path)


def test_compact_csv_writer_uses_git_safe_lf_line_endings(tmp_path: Path):
    path = tmp_path / "evidence.csv"
    p20s.write_csv(path, [{"a": "one", "b": "two"}], ("a", "b"))
    payload = path.read_bytes()
    assert b"\r" not in payload
    assert payload == b"a,b\none,two\n"


def test_constructor_result_type_remains_reviewed_success_contract():
    request = p20c.ConstructorRequest(
        strategy_id="fixture",
        draw_id="100",
        replicate_id=0,
        raw_tickets=[[1, 2, 3, 4, 5, 6]],
        historical_cutoff_identity="99",
        user_seed=p20c.USER_SEED_NAMESPACE,
    )
    result = p20c.construct_strategy_preserving_20_ticket(request)
    assert isinstance(result, ConstructorSuccess)
    assert len(result.tickets) == 20
