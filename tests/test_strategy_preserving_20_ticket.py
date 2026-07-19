"""Contract and parity tests for strategy_preserving_20_ticket/v1."""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from itertools import combinations
from pathlib import Path

import pytest

from lottery_api.models.strategy_preserving_20_ticket import (
    CANDIDATE_POOL_SIZE,
    CONSTRUCTOR_IDENTIFIER,
    CONSTRUCTOR_NAME,
    CONSTRUCTOR_VERSION,
    MAX_CANDIDATE_ATTEMPTS,
    MAX_OVERLAP_PENALTY,
    NUMBER_CONCENTRATION_PENALTY,
    SHORT_IDENTIFIER,
    SIGNAL_SCORE_WEIGHT,
    V1_PARITY_PORTFOLIO_SHA256,
    ConstructionTier,
    ConstructorFailure,
    ConstructorFailureReason,
    ConstructorRequest,
    ConstructorSuccess,
    construct_strategy_preserving_20_ticket,
    objective_constants,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "lottery_api/models/strategy_preserving_20_ticket.py"


def make_request(raw_tickets, **overrides):
    values = {
        "strategy_id": "fixture::tier_c",
        "draw_id": "115000070",
        "replicate_id": 0,
        "raw_tickets": raw_tickets,
        "historical_cutoff_identity": "115000069",
        "user_seed": "unit-test",
    }
    values.update(overrides)
    return ConstructorRequest(**values)


def native_tickets(count):
    return [list(ticket) for ticket in list(combinations(range(1, 50), 6))[:count]]


def assert_legal_portfolio(result):
    assert isinstance(result, ConstructorSuccess)
    assert len(result.tickets) == 20
    assert len(set(result.tickets)) == 20
    for ticket in result.tickets:
        assert tuple(sorted(ticket)) == ticket
        assert len(ticket) == 6
        assert len(set(ticket)) == 6
        assert all(type(number) is int and 1 <= number <= 49 for number in ticket)


def parity_request():
    return ConstructorRequest(
        strategy_id="fixture::ranked_signal",
        draw_id="115000070",
        replicate_id=3,
        raw_tickets=[
            [1, 7, 13, 19, 25, 31],
            [2, 8, 14, 20, 26, 32],
        ],
        historical_cutoff_identity="115000069",
        user_seed="p20c-parity-v1",
        number_scores={
            1: 9.5,
            2: 9.0,
            7: 8.5,
            8: 8.0,
            13: 7.5,
            14: 7.0,
            19: 6.5,
            20: 6.0,
            25: 5.5,
            26: 5.0,
            31: 4.5,
            32: 4.0,
        },
        ranked_numbers=[1, 2, 7, 8, 13, 14, 19, 20, 25, 26, 31, 32],
    )


def test_zero_valid_inputs_returns_typed_tier_d_failure():
    result = construct_strategy_preserving_20_ticket(make_request([]))
    assert isinstance(result, ConstructorFailure)
    assert result.reason is ConstructorFailureReason.NO_VALID_STRATEGY_SIGNAL
    assert result.ok is False


@pytest.mark.parametrize(
    "ticket",
    (
        [0, 2, 3, 4, 5, 6],
        [1, 2, 3, 4, 5, 50],
        [1, 1, 2, 3, 4, 5],
        [1, 2, 3, 4, 5],
        [1, 2, 3, 4, 5, True],
    ),
)
def test_invalid_native_ticket_shapes_are_rejected(ticket):
    result = construct_strategy_preserving_20_ticket(make_request([ticket]))
    assert isinstance(result, ConstructorFailure)
    assert result.reason is ConstructorFailureReason.INVALID_NATIVE_OUTPUT
    assert result.native_invalid_count == 1


def test_duplicate_tickets_are_deduplicated_and_native_is_preserved():
    native = [[6, 1, 5, 2, 4, 3], [1, 2, 3, 4, 5, 6]]
    result = construct_strategy_preserving_20_ticket(make_request(native))
    assert_legal_portfolio(result)
    assert result.metadata.native_input_count == 2
    assert result.metadata.native_valid_count == 1
    assert result.metadata.native_duplicate_count == 1
    assert result.metadata.native_retained_count == 1
    assert result.metadata.constructed_ticket_count == 19
    assert (1, 2, 3, 4, 5, 6) in result.tickets


def test_exactly_twenty_native_tickets_are_tier_a_and_not_reordered_by_input():
    native = native_tickets(20)
    forward = construct_strategy_preserving_20_ticket(make_request(native))
    reverse = construct_strategy_preserving_20_ticket(make_request(list(reversed(native))))
    assert_legal_portfolio(forward)
    assert forward.tickets == reverse.tickets
    assert forward.tickets == tuple(sorted(tuple(ticket) for ticket in native))
    assert forward.metadata.construction_tier == ConstructionTier.NATIVE_COMPLETE.value
    assert forward.metadata.constructed_ticket_count == 0
    assert forward.metadata.effective_strategy_id == "fixture::tier_c"


def test_same_input_is_deterministic():
    request = make_request(native_tickets(4))
    first = construct_strategy_preserving_20_ticket(request)
    second = construct_strategy_preserving_20_ticket(request)
    assert first == second


def test_replicate_ids_have_independent_deterministic_seed_namespaces():
    first = construct_strategy_preserving_20_ticket(
        make_request(native_tickets(4), replicate_id=1)
    )
    repeat = construct_strategy_preserving_20_ticket(
        make_request(native_tickets(4), replicate_id=1)
    )
    second = construct_strategy_preserving_20_ticket(
        make_request(native_tickets(4), replicate_id=2)
    )
    assert first == repeat
    assert isinstance(first, ConstructorSuccess)
    assert isinstance(second, ConstructorSuccess)
    assert first.metadata.seed_digest != second.metadata.seed_digest
    assert first.metadata.portfolio_sha256 != second.metadata.portfolio_sha256


def test_raw_ticket_input_order_does_not_change_output():
    raw = native_tickets(8)
    first = construct_strategy_preserving_20_ticket(make_request(raw))
    second = construct_strategy_preserving_20_ticket(make_request(raw[3:] + raw[:3]))
    assert first == second


def test_number_score_dictionary_order_does_not_change_output():
    scores = {1: 8.0, 2: 7.0, 3: 6.0, 4: 5.0, 5: 4.0, 6: 3.0}
    reversed_scores = dict(reversed(list(scores.items())))
    first = construct_strategy_preserving_20_ticket(
        make_request([], number_scores=scores)
    )
    second = construct_strategy_preserving_20_ticket(
        make_request([], number_scores=reversed_scores)
    )
    assert first == second
    assert_legal_portfolio(first)


def test_parity_fixture_pins_portfolio_and_metadata():
    result = construct_strategy_preserving_20_ticket(parity_request())
    assert_legal_portfolio(result)
    assert result.metadata.portfolio_sha256 == V1_PARITY_PORTFOLIO_SHA256
    assert V1_PARITY_PORTFOLIO_SHA256 == (
        "8f756025c8818987101b2b61f7c296d0341d7fea52ffa95f7272ca121c9b30d6"
    )
    assert result.metadata.constructor_name == CONSTRUCTOR_NAME
    assert result.metadata.constructor_version == CONSTRUCTOR_VERSION
    assert result.metadata.construction_tier == "strategy_ranked_signal"
    assert result.metadata.signal_source == "strategy_number_scores_and_ranked_numbers"
    assert result.metadata.native_retained_count == 2
    assert result.metadata.constructed_ticket_count == 18
    assert result.metadata.native_ticket_share == 0.1
    assert result.metadata.seed_digest == (
        "f525648c05ca53a9858847303992c7a25132f6f306061547df53a14c06d0b406"
    )


def test_v1_version_and_objective_constants_are_explicitly_pinned():
    assert CONSTRUCTOR_IDENTIFIER == "strategy_preserving_20_ticket/v1"
    assert SHORT_IDENTIFIER == "sp20_v1"
    assert CANDIDATE_POOL_SIZE == 80
    assert MAX_CANDIDATE_ATTEMPTS == 4096
    assert SIGNAL_SCORE_WEIGHT == 100.0
    assert MAX_OVERLAP_PENALTY == 12.0
    assert NUMBER_CONCENTRATION_PENALTY == 2.0
    assert objective_constants()["parity_portfolio_sha256"] == V1_PARITY_PORTFOLIO_SHA256


def test_source_does_not_call_python_hash():
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "hash"
    ]
    assert calls == []


def test_request_contract_has_no_target_result_or_generic_context_field():
    fields = set(ConstructorRequest.__dataclass_fields__)
    assert "target_numbers" not in fields
    assert "winning_numbers" not in fields
    assert "actual_numbers" not in fields
    assert "context" not in fields
    assert "historical_cutoff_identity" in fields


def test_tier_b_can_construct_from_scores_without_native_tickets():
    result = construct_strategy_preserving_20_ticket(
        make_request([], number_scores={1: 4.0, 2: 3.0, 3: 2.0, 4: 1.0})
    )
    assert_legal_portfolio(result)
    assert result.metadata.native_retained_count == 0
    assert result.metadata.constructed_ticket_count == 20
    assert result.metadata.construction_tier == "strategy_ranked_signal"
    assert all(len(set(ticket) & {1, 2, 3, 4}) >= 4 for ticket in result.tickets)


def test_tier_c_uses_membership_not_position_and_meets_signal_minimum():
    first = construct_strategy_preserving_20_ticket(
        make_request([[1, 2, 3, 4, 5, 6]])
    )
    second = construct_strategy_preserving_20_ticket(
        make_request([[6, 5, 4, 3, 2, 1]])
    )
    assert first == second
    assert_legal_portfolio(first)
    assert first.metadata.construction_tier == "native_ticket_derived_signal"
    signal = {1, 2, 3, 4, 5, 6}
    assert all(len(set(ticket) & signal) >= 3 for ticket in first.tickets[1:])


def test_invalid_or_equal_cutoff_fails_closed():
    equal = construct_strategy_preserving_20_ticket(
        make_request(native_tickets(1), historical_cutoff_identity="115000070")
    )
    future = construct_strategy_preserving_20_ticket(
        make_request(native_tickets(1), historical_cutoff_identity="115000071")
    )
    assert equal.reason is ConstructorFailureReason.INVALID_CUTOFF
    assert future.reason is ConstructorFailureReason.INVALID_CUTOFF


def test_pre_cutoff_strategy_input_can_change_output():
    first = construct_strategy_preserving_20_ticket(make_request([[1, 2, 3, 4, 5, 6]]))
    second = construct_strategy_preserving_20_ticket(make_request([[7, 8, 9, 10, 11, 12]]))
    assert isinstance(first, ConstructorSuccess)
    assert isinstance(second, ConstructorSuccess)
    assert first.metadata.portfolio_sha256 != second.metadata.portfolio_sha256


def test_more_than_twenty_native_tickets_are_selected_deterministically():
    native = native_tickets(25)
    result = construct_strategy_preserving_20_ticket(make_request(native))
    repeat = construct_strategy_preserving_20_ticket(make_request(list(reversed(native))))
    assert_legal_portfolio(result)
    assert result == repeat
    assert result.metadata.native_valid_count == 25
    assert result.metadata.native_retained_count == 20
    assert result.metadata.constructed_ticket_count == 0
    assert set(result.tickets).issubset({tuple(ticket) for ticket in native})


def test_non_twenty_target_is_explicit_typed_failure():
    result = construct_strategy_preserving_20_ticket(
        make_request(native_tickets(1), target_ticket_count=19)
    )
    assert result.reason is ConstructorFailureReason.UNSUPPORTED_TARGET_TICKET_COUNT


def test_fresh_python_process_reproduces_parity_hash():
    script = r'''
import json
from lottery_api.models.strategy_preserving_20_ticket import ConstructorRequest, construct_strategy_preserving_20_ticket
r = construct_strategy_preserving_20_ticket(ConstructorRequest(
    strategy_id="fixture::ranked_signal", draw_id="115000070", replicate_id=3,
    raw_tickets=[[1,7,13,19,25,31],[2,8,14,20,26,32]],
    historical_cutoff_identity="115000069", user_seed="p20c-parity-v1",
    number_scores={1:9.5,2:9.0,7:8.5,8:8.0,13:7.5,14:7.0,19:6.5,20:6.0,25:5.5,26:5.0,31:4.5,32:4.0},
    ranked_numbers=[1,2,7,8,13,14,19,20,25,26,31,32],
))
print(json.dumps({"sha": r.metadata.portfolio_sha256, "seed": r.metadata.seed_digest}, sort_keys=True))
'''
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    first = subprocess.check_output(
        [sys.executable, "-c", script], cwd=REPO_ROOT, env=environment, text=True
    ).strip()
    second = subprocess.check_output(
        [sys.executable, "-c", script], cwd=REPO_ROOT, env=environment, text=True
    ).strip()
    assert first == second
    assert json.loads(first)["sha"] == V1_PARITY_PORTFOLIO_SHA256
