"""Unit tests for the paper recommendation quality evaluator."""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from orchestrator.mlb_paper_evaluator import (
    _row_learning_eligibility,
    calculate_binomial_p_value,
    evaluate_paper_recommendations,
    execute_evaluation,
    load_outcome_records,
    load_paper_recommendations,
)


@pytest.fixture
def mock_recommendation_data() -> list[dict]:
    return [
        {
            "game_id": "2026-05-11-LAA-CLE-824441",
            "model_prob_home": 0.60,
            "model_prob_away": 0.40,
            "tsl_market": "moneyline",
            "tsl_side": "home",
            "tsl_decimal_odds": 2.0,
            "stake_units_paper": 2.5,
            "gate_status": "PASS",
            "paper_only": True,
        },
        {
            "game_id": "2026-05-11-NYY-BOS-824442",
            "model_prob_home": 0.45,
            "model_prob_away": 0.55,
            "tsl_market": "moneyline",
            "tsl_side": "away",
            "tsl_decimal_odds": 1.80,
            "stake_units_paper": 0.0,
            "gate_status": "BLOCKED_SIMULATION_GATE",
            "paper_only": True,
        },
        {
            "game_id": "2026-05-11-CHC-MIL-824443",
            "model_prob_home": 0.70,
            "model_prob_away": 0.30,
            "tsl_market": "moneyline",
            "tsl_side": "home",
            "tsl_decimal_odds": 1.50,
            "stake_units_paper": 5.0,
            "gate_status": "PASS",
            "paper_only": True,
        },
    ]


@pytest.fixture
def mock_outcome_data() -> list[dict]:
    return [
        {
            "game_id": "mlb_2026_824441",
            "outcome_available": True,
            "actual_winner": "home",
        },
        {
            "game_id": "mlb_2026_824442",
            "outcome_available": True,
            "actual_winner": "home",  # Lost: recommendation was away
        },
        {
            "game_id": "mlb_2026_824443",
            "outcome_available": True,
            "actual_winner": "home",  # Won: recommendation was home
        },
    ]


def test_binomial_p_value_calculation():
    """Verify binomial p-value logic works as mathematically expected."""
    # 5 hits out of 10 under p=0.5 -> CDF for getting >= 5 should be safe and correct
    pval_5_10 = calculate_binomial_p_value(5, 10)
    assert 0.0 < pval_5_10 <= 1.0

    # 10 hits out of 10 under p=0.5 -> highly significant, p-value should be low
    pval_10_10 = calculate_binomial_p_value(10, 10)
    assert pval_10_10 == (0.5 ** 10)

    # 0 hits -> p-value must be 1.0 (at least 0 hits is certain)
    assert calculate_binomial_p_value(0, 5) == 1.0


def test_evaluation_metric_computations(mock_recommendation_data, mock_outcome_data):
    """Verify evaluation logic matches mock inputs exactly."""
    metrics = evaluate_paper_recommendations(mock_recommendation_data, mock_outcome_data)

    assert metrics.evaluated_count == 3
    assert metrics.matched_outcome_count == 3
    assert metrics.missing_outcome_count == 0
    assert metrics.coverage_rate == 1.0

    # Hits: 824441 (CLE home win -> CLE rec home won), 824443 (MIL home win -> CHC rec home won)
    # Total correct: 2/3
    assert metrics.hit_rate == round(2 / 3, 4)

    # Brier calculation:
    # 824441: (0.60 - 1.0)^2 = 0.16
    # 824442: (0.45 - 1.0)^2 = 0.3025 (model_prob_home is 0.45, actual winner is home -> actual=1.0)
    # 824443: (0.70 - 1.0)^2 = 0.09
    # Mean: (0.16 + 0.3025 + 0.09) / 3 = 0.5525 / 3 = 0.184167
    assert metrics.brier_score is not None
    assert abs(metrics.brier_score - 0.184167) < 1e-4

    # Simulated paper-only PnL:
    # 824441: PASS, won: 2.5 * (2.0 - 1.0) = +2.5 units
    # 824442: BLOCKED, lost: -0.0 units
    # 824443: PASS, won: 5.0 * (1.5 - 1.0) = +2.5 units
    # Total actual PnL: 2.5 + 2.5 = 5.0 units
    assert metrics.actual_paper_pnl == 5.0
    assert metrics.actual_paper_stake == 7.5
    assert metrics.actual_paper_roi == round(5.0 / 7.5, 4)

    # Shadow PnL (assume 1.0 units flat for all):
    # 824441: +1.0
    # 824442: -1.0
    # 824443: +0.5
    # Total shadow PnL: +0.5 units
    assert metrics.shadow_unit_pnl == 0.5
    assert metrics.shadow_unit_stake == 3.0
    assert metrics.shadow_unit_roi == round(0.5 / 3.0, 4)


def test_missing_outcome_handling(mock_recommendation_data, mock_outcome_data):
    """Verify evaluation handles missing or incomplete outcomes cleanly."""
    incomplete_outcomes = [
        # 824441 is missing
        {
            "game_id": "mlb_2026_824442",
            "outcome_available": False,  # Not available
            "actual_winner": "home",
        },
        {
            "game_id": "mlb_2026_824443",
            "outcome_available": True,
            "actual_winner": None,  # Winner missing
        },
    ]

    metrics = evaluate_paper_recommendations(mock_recommendation_data, incomplete_outcomes)

    assert metrics.evaluated_count == 3
    assert metrics.matched_outcome_count == 0
    assert metrics.missing_outcome_count == 3
    assert metrics.coverage_rate == 0.0
    assert metrics.hit_rate == 0.0


def test_segmentation_logic(mock_recommendation_data, mock_outcome_data):
    """Verify segmentation by gate status and confidence bands."""
    metrics = evaluate_paper_recommendations(mock_recommendation_data, mock_outcome_data)

    assert "PASS" in metrics.gate_segmentation
    assert "BLOCKED_SIMULATION_GATE" in metrics.gate_segmentation

    pass_seg = metrics.gate_segmentation["PASS"]
    assert pass_seg["count"] == 2
    assert pass_seg["correct_count"] == 2  # Both home bets won

    blocked_seg = metrics.gate_segmentation["BLOCKED_SIMULATION_GATE"]
    assert blocked_seg["count"] == 1
    assert blocked_seg["correct_count"] == 0

    assert "low (0.50-0.55)" in metrics.confidence_segmentation
    assert "mid (0.55-0.65)" in metrics.confidence_segmentation
    assert "high (0.65-1.00)" in metrics.confidence_segmentation


def test_evaluator_file_loading_and_execute(tmp_path, mock_recommendation_data, mock_outcome_data):
    """Verify directories can be traversed, files parsed, and JSON summary generated."""
    # Write recommendation file
    rec_dir = tmp_path / "recommendations" / "PAPER" / "2026-05-11"
    rec_dir.mkdir(parents=True)
    rec_file = rec_dir / "rec_game_1.jsonl"
    with open(rec_file, "w", encoding="utf-8") as f:
        for r in mock_recommendation_data:
            f.write(json.dumps(r) + "\n")

    # Write outcome file
    outcome_file = tmp_path / "outcome_attached.jsonl"
    with open(outcome_file, "w", encoding="utf-8") as f:
        for o in mock_outcome_data:
            f.write(json.dumps(o) + "\n")

    summary_file = tmp_path / "summary.json"

    # Test load functions directly
    recs = load_paper_recommendations(tmp_path / "recommendations")
    assert len(recs) == 3

    outcomes = load_outcome_records(outcome_file)
    assert len(outcomes) == 3

    # Test execution
    res = execute_evaluation(
        paper_dir=tmp_path / "recommendations",
        outcome_path=outcome_file,
        summary_output_path=summary_file,
    )

    assert res["evaluator_version"] == "p180_evaluator_v2"
    assert res["metrics"]["evaluated_count"] == 3
    assert res["metrics"]["matched_outcome_count"] == 3

    # Verify summary file exists and can be parsed back
    assert summary_file.exists()
    with open(summary_file, encoding="utf-8") as f:
        loaded_res = json.load(f)
    assert loaded_res["metrics"]["evaluated_count"] == 3


# ── P201: evaluator-side learning_eligible enforcement ────────────────────────


def _p201_rec(game_pk: str, side: str, *, source_trace=None, strategy_id=None) -> dict:
    r = {
        "game_id": f"2026-05-11-LAA-CLE-{game_pk}",
        "model_prob_home": 0.55,
        "model_prob_away": 0.45,
        "tsl_market": "moneyline",
        "tsl_side": side,
        "tsl_decimal_odds": 1.90,
        "stake_units_paper": 1.0,
        "gate_status": "PASS",
        "paper_only": True,
    }
    if source_trace is not None:
        r["source_trace"] = source_trace
    if strategy_id is not None:
        r["strategy_id"] = strategy_id
    return r


def _p201_outcome(game_pk: str, winner: str) -> dict:
    return {
        "game_id": f"mlb_2026_{game_pk}",
        "outcome_available": True,
        "actual_winner": winner,
    }


class TestP201RowLearningEligibilityHelper:
    """_row_learning_eligibility is conservative: eligible only on explicit True."""

    def test_explicit_true_is_eligible(self):
        ok, reason = _row_learning_eligibility(
            {"source_trace": {"learning_eligible": True}}
        )
        assert ok is True
        assert reason is None

    def test_explicit_false_is_ineligible_with_reason(self):
        ok, reason = _row_learning_eligibility(
            {"source_trace": {"learning_eligible": False, "learning_block_reason": "neutral"}}
        )
        assert ok is False
        assert reason == "neutral"

    def test_false_without_reason_gets_default_reason(self):
        ok, reason = _row_learning_eligibility(
            {"source_trace": {"learning_eligible": False}}
        )
        assert ok is False
        assert reason == "learning_eligible=false"

    def test_missing_source_trace_is_ineligible(self):
        ok, reason = _row_learning_eligibility({})
        assert ok is False
        assert reason == "missing_source_trace_provenance"

    def test_malformed_source_trace_is_ineligible(self):
        ok, reason = _row_learning_eligibility({"source_trace": "not-a-dict"})
        assert ok is False
        assert reason == "missing_source_trace_provenance"

    def test_flag_absent_is_ineligible(self):
        ok, reason = _row_learning_eligibility(
            {"source_trace": {"prediction_input_mode": "neutral_fixed_prior"}}
        )
        assert ok is False
        assert reason == "learning_eligible_not_declared"


class TestP201EvaluatorLearningCounts:
    """Evaluator counts eligible/ineligible rows separately (D1, D3)."""

    def test_ineligible_row_is_scored_but_counted_ineligible(self):
        rec = _p201_rec("930001", "home", source_trace={"learning_eligible": False})
        m = evaluate_paper_recommendations([rec], [_p201_outcome("930001", "home")])
        # Still scored for auditability
        assert m.matched_outcome_count == 1
        assert m.hit_rate == 1.0
        # But counted as learning-ineligible
        assert m.learning_eligible_count == 0
        assert m.learning_ineligible_count == 1

    def test_eligible_and_ineligible_counted_separately(self):
        recs = [
            _p201_rec("930010", "home", source_trace={"learning_eligible": True}),
            _p201_rec("930011", "home", source_trace={"learning_eligible": False}),
            _p201_rec("930012", "home"),  # no source_trace → ineligible
        ]
        outcomes = [_p201_outcome(f"93001{i}", "home") for i in range(3)]
        m = evaluate_paper_recommendations(recs, outcomes)
        assert m.learning_eligible_count == 1
        assert m.learning_ineligible_count == 2

    def test_block_reasons_surfaced_in_segmentation(self):
        """learning_block_reason is preserved/surfaced in segmentation (D2)."""
        recs = [
            _p201_rec(
                "930020", "home",
                source_trace={"learning_eligible": False, "learning_block_reason": "neutral_fixed_prior"},
            ),
            _p201_rec("930021", "home"),  # missing source_trace
        ]
        outcomes = [_p201_outcome("930020", "home"), _p201_outcome("930021", "home")]
        m = evaluate_paper_recommendations(recs, outcomes)
        seg = m.learning_eligibility_segmentation
        assert seg["eligible_count"] == 0
        assert seg["ineligible_count"] == 2
        assert seg["block_reasons"]["neutral_fixed_prior"] == 1
        assert seg["block_reasons"]["missing_source_trace_provenance"] == 1

    def test_legacy_rows_missing_source_trace_do_not_crash(self):
        """Historical rows without provenance evaluate and classify conservatively (D5)."""
        recs = [_p201_rec("930030", "home"), _p201_rec("930031", "away")]
        outcomes = [_p201_outcome("930030", "home"), _p201_outcome("930031", "away")]
        m = evaluate_paper_recommendations(recs, outcomes)
        assert m.matched_outcome_count == 2
        assert m.learning_eligible_count == 0
        assert m.learning_ineligible_count == 2

    def test_eligible_rows_remain_eligible(self):
        """Explicit non-fallback eligible rows remain eligible (D6)."""
        recs = [
            _p201_rec("930040", "home", source_trace={"learning_eligible": True}, strategy_id="game_specific_v1"),
        ]
        m = evaluate_paper_recommendations(recs, [_p201_outcome("930040", "home")])
        assert m.learning_eligible_count == 1
        assert m.learning_ineligible_count == 0

    def test_learning_counts_are_json_serializable_and_deterministic(self):
        recs = [_p201_rec("930050", "home", source_trace={"learning_eligible": False})]
        outcomes = [_p201_outcome("930050", "home")]
        m1 = evaluate_paper_recommendations(recs, outcomes)
        m2 = evaluate_paper_recommendations(recs, outcomes)
        assert m1.learning_eligibility_segmentation == m2.learning_eligibility_segmentation
        json.dumps(m1.learning_eligibility_segmentation)  # must not raise
