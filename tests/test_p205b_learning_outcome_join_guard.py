from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orchestrator.mlb_paper_evaluator import evaluate_paper_recommendations
from wbc_backend.recommendation.learning_outcome_join import (
    AMBIGUOUS_OUTCOME_JOIN,
    LEGACY_CONTRACT,
    MALFORMED_CONTRACT,
    MISSING_CONTRACT,
    MISSING_GAME_ID,
    MISSING_PREDICTION_AS_OF_UTC,
    NOT_LEARNING_ELIGIBLE,
    OUTCOME_NOT_FOUND,
    RESULT_TIMESTAMP_MISSING,
    STALE_OR_INVALID_AS_OF,
    evaluate_learning_outcome_join,
)
from wbc_backend.recommendation.provenance_contract import build_provenance_contract


def _contract(**overrides):
    base = dict(
        prediction_input_mode="game_specific",
        prediction_source="unit_test_model",
        prediction_source_id="824441",
        model_version="unit-test-v1",
        feature_fingerprint="feature-fp",
        prediction_as_of_utc="2026-05-11T10:00:00+00:00",
        game_specific=True,
        selected_side_method="argmax_model_probability",
        odds_source="observed_market",
        odds_is_market_observed=True,
        edge_is_real_evidence=True,
        learning_eligible=True,
        learning_block_reason="",
    )
    base.update(overrides)
    return build_provenance_contract(**base)


def _rec(game_pk: str = "824441", *, source_trace=None) -> dict:
    row = {
        "game_id": f"2026-05-11-LAA-CLE-{game_pk}",
        "model_prob_home": 0.55,
        "model_prob_away": 0.45,
        "tsl_market": "moneyline",
        "tsl_side": "home",
        "tsl_decimal_odds": 1.90,
        "stake_units_paper": 0.0,
        "gate_status": "PASS",
        "paper_only": True,
    }
    if source_trace is not None:
        row["source_trace"] = source_trace
    return row


def _outcome(game_pk: str = "824441", *, result_timestamp="2026-05-12T04:00:00+00:00") -> dict:
    row = {
        "game_id": f"mlb_2026_{game_pk}",
        "outcome_available": True,
        "actual_winner": "home",
    }
    if result_timestamp is not None:
        row["result_timestamp_utc"] = result_timestamp
    return row


def _reason(rec: dict, outcomes: list[dict]) -> str | None:
    return evaluate_learning_outcome_join(rec, outcomes).block_reason


def test_valid_contract_stable_identity_and_fresh_asof_passes():
    decision = evaluate_learning_outcome_join(_rec(source_trace=_contract()), [_outcome()])
    assert decision.learning_eligible is True
    assert decision.block_reason is None
    assert decision.recommendation_game_identity == "824441"
    assert decision.outcome_game_identity == "824441"


def test_missing_source_trace_blocks_as_missing_contract():
    assert _reason(_rec(), [_outcome()]) == MISSING_CONTRACT


def test_legacy_contract_blocks_even_when_learning_true():
    assert _reason(_rec(source_trace={"learning_eligible": True}), [_outcome()]) == LEGACY_CONTRACT


def test_malformed_contract_blocks_string_booleans():
    malformed = _contract()
    malformed["learning_eligible"] = "true"
    assert _reason(_rec(source_trace=malformed), [_outcome()]) == MALFORMED_CONTRACT


def test_not_learning_eligible_blocks_false_contract():
    blocked = _contract(
        learning_eligible=False,
        edge_is_real_evidence=False,
        learning_block_reason="paper_only",
    )
    assert _reason(_rec(source_trace=blocked), [_outcome()]) == NOT_LEARNING_ELIGIBLE


def test_missing_game_id_blocks_before_outcome_lookup():
    rec = _rec(source_trace=_contract())
    rec["game_id"] = "2026-05-11-LAA-CLE"
    assert _reason(rec, [_outcome()]) == MISSING_GAME_ID


def test_outcome_not_found_blocks_learning():
    assert _reason(_rec(source_trace=_contract()), [_outcome("824442")]) == OUTCOME_NOT_FOUND


def test_ambiguous_outcome_join_blocks_learning():
    assert _reason(_rec(source_trace=_contract()), [_outcome(), _outcome()]) == AMBIGUOUS_OUTCOME_JOIN


def test_missing_prediction_as_of_blocks_learning():
    malformed = _contract()
    malformed["prediction_as_of_utc"] = ""
    assert _reason(_rec(source_trace=malformed), [_outcome()]) == MISSING_PREDICTION_AS_OF_UTC


def test_result_timestamp_missing_blocks_learning():
    assert _reason(_rec(source_trace=_contract()), [_outcome(result_timestamp=None)]) == RESULT_TIMESTAMP_MISSING


def test_stale_or_invalid_as_of_blocks_learning():
    stale = _contract(prediction_as_of_utc="2026-05-12T04:00:00+00:00")
    assert _reason(_rec(source_trace=stale), [_outcome()]) == STALE_OR_INVALID_AS_OF


def test_evaluator_uses_guard_for_learning_acceptance_without_changing_scoring():
    recs = [
        _rec("824441", source_trace=_contract()),
        _rec("824442", source_trace=_contract(prediction_as_of_utc="2026-05-13T00:00:00+00:00")),
    ]
    outcomes = [_outcome("824441"), _outcome("824442")]

    metrics = evaluate_paper_recommendations(recs, outcomes)

    assert metrics.matched_outcome_count == 2
    assert metrics.hit_rate == 1.0
    assert metrics.learning_eligible_count == 1
    assert metrics.learning_ineligible_count == 1
    assert metrics.learning_eligibility_segmentation["block_reasons"][STALE_OR_INVALID_AS_OF] == 1


def test_unversioned_timestamp_rows_are_still_legacy_contracts():
    rec = _rec(source_trace={"learning_eligible": True, "prediction_as_of_utc": ""})
    assert _reason(rec, [_outcome()]) == LEGACY_CONTRACT
