"""
Tests for P22.5 P15 readiness planner.
Validates per-date P15 readiness and build plan construction.
"""
import pytest

from wbc_backend.recommendation.p22_5_source_artifact_contract import (
    HISTORICAL_MARKET_ODDS,
    HISTORICAL_OOF_PREDICTIONS,
    HISTORICAL_P15_JOINED_INPUT,
    MAPPING_RISK_HIGH,
    MAPPING_RISK_LOW,
    MAPPING_RISK_MEDIUM,
    SOURCE_CANDIDATE_PARTIAL,
    SOURCE_CANDIDATE_USABLE,
    P225HistoricalSourceCandidate,
)
from wbc_backend.recommendation.p22_5_p15_readiness_planner import (
    build_source_artifact_build_plan,
    evaluate_p15_readiness_for_date,
    validate_build_plan,
    generate_safe_next_commands,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_candidate(
    source_type=HISTORICAL_MARKET_ODDS,
    has_game_id=False,
    has_y_true=True,
    has_odds=True,
    has_p_model_or_p_oof=False,
    mapping_risk=MAPPING_RISK_MEDIUM,
    candidate_status=SOURCE_CANDIDATE_USABLE,
    source_date="2025-04-15",
    source_path="/data/mlb_odds.csv",
) -> P225HistoricalSourceCandidate:
    return P225HistoricalSourceCandidate(
        source_path=source_path,
        source_type=source_type,
        source_date=source_date,
        coverage_pct=0.9,
        row_count=2430,
        has_game_id=has_game_id,
        has_y_true=has_y_true,
        has_odds=has_odds,
        has_p_model_or_p_oof=has_p_model_or_p_oof,
        mapping_risk=mapping_risk,
        candidate_status=candidate_status,
        paper_only=True,
        production_ready=False,
    )


def _make_joined_candidate(source_path="/outputs/joined_oof.csv") -> P225HistoricalSourceCandidate:
    return _make_candidate(
        source_type=HISTORICAL_P15_JOINED_INPUT,
        has_game_id=True,
        has_y_true=True,
        has_odds=True,
        has_p_model_or_p_oof=True,
        mapping_risk=MAPPING_RISK_LOW,
        candidate_status=SOURCE_CANDIDATE_USABLE,
        source_path=source_path,
    )


def _make_oof_candidate(source_path="/outputs/oof_predictions.csv") -> P225HistoricalSourceCandidate:
    return _make_candidate(
        source_type=HISTORICAL_OOF_PREDICTIONS,
        has_game_id=False,
        has_y_true=True,
        has_odds=False,
        has_p_model_or_p_oof=True,
        mapping_risk=MAPPING_RISK_HIGH,
        candidate_status=SOURCE_CANDIDATE_USABLE,
        source_path=source_path,
    )


def _make_odds_candidate(source_path="/data/mlb_odds.csv") -> P225HistoricalSourceCandidate:
    return _make_candidate(
        source_type=HISTORICAL_MARKET_ODDS,
        has_game_id=False,
        has_y_true=True,
        has_odds=True,
        has_p_model_or_p_oof=False,
        mapping_risk=MAPPING_RISK_MEDIUM,
        candidate_status=SOURCE_CANDIDATE_USABLE,
        source_path=source_path,
    )


# ---------------------------------------------------------------------------
# evaluate_p15_readiness_for_date
# ---------------------------------------------------------------------------


def test_p15_ready_when_joined_input_available():
    """A fully-joined P15 input candidate makes any date P15-ready."""
    joined = _make_joined_candidate()
    result = evaluate_p15_readiness_for_date("2026-05-05", [joined])
    assert result.is_p15_ready is True
    assert result.has_predictions is True
    assert result.has_odds is True
    assert result.has_outcomes is True
    assert result.has_identity is True
    assert result.blocked_reason == ""
    assert result.paper_only is True
    assert result.production_ready is False


def test_p15_ready_when_oof_plus_odds_available():
    """OOF predictions + market odds + outcomes = P15-ready."""
    oof = _make_oof_candidate()
    odds = _make_odds_candidate()
    # OOF has high risk, odds has medium — combined should cover all fields
    result = evaluate_p15_readiness_for_date("2026-05-03", [oof, odds])
    # has_predictions from oof, has_odds from odds, has_outcomes from both
    assert result.has_predictions is True
    assert result.has_odds is True
    assert result.has_outcomes is True


def test_p15_not_ready_when_missing_predictions():
    odds = _make_odds_candidate()  # only has odds + outcomes, no predictions
    result = evaluate_p15_readiness_for_date("2026-05-01", [odds])
    assert result.has_predictions is False
    assert result.is_p15_ready is False
    assert "MISSING_MODEL_PREDICTIONS" in result.blocked_reason


def test_p15_not_ready_when_missing_market_odds():
    oof = _make_oof_candidate()  # only has predictions + outcomes, no odds
    result = evaluate_p15_readiness_for_date("2026-05-01", [oof])
    assert result.has_odds is False
    assert result.is_p15_ready is False
    assert "MISSING_MARKET_ODDS" in result.blocked_reason


def test_p15_not_ready_when_no_candidates():
    result = evaluate_p15_readiness_for_date("2026-05-01", [])
    assert result.is_p15_ready is False
    assert "NO_SOURCE_CANDIDATES" in result.blocked_reason


def test_p15_not_ready_when_all_candidates_high_risk():
    """All HIGH risk with no game_id should block P15 readiness."""
    c_high = _make_candidate(
        has_game_id=False,
        has_y_true=True,
        has_odds=True,
        has_p_model_or_p_oof=True,
        mapping_risk=MAPPING_RISK_HIGH,
        candidate_status=SOURCE_CANDIDATE_USABLE,
    )
    result = evaluate_p15_readiness_for_date("2026-05-04", [c_high])
    assert result.is_p15_ready is False
    assert "UNSAFE" in result.blocked_reason or "MISSING_IDENTITY" in result.blocked_reason


def test_p15_ready_result_is_frozen():
    joined = _make_joined_candidate()
    result = evaluate_p15_readiness_for_date("2026-05-05", [joined])
    with pytest.raises((AttributeError, TypeError)):
        result.is_p15_ready = False  # type: ignore


def test_p15_ready_result_enforces_paper_only():
    joined = _make_joined_candidate()
    result = evaluate_p15_readiness_for_date("2026-05-05", [joined])
    assert result.paper_only is True
    assert result.production_ready is False


# ---------------------------------------------------------------------------
# build_source_artifact_build_plan
# ---------------------------------------------------------------------------


def test_build_plan_classifies_ready_dates():
    joined = _make_joined_candidate()
    dates = [
        evaluate_p15_readiness_for_date(f"2026-05-{i:02d}", [joined])
        for i in range(1, 13)
    ]
    plan = build_source_artifact_build_plan(dates, [joined])
    assert len(plan.dates_ready_to_build_p15_inputs) == 12
    assert len(plan.dates_missing_all_sources) == 0
    assert plan.paper_only is True
    assert plan.production_ready is False


def test_build_plan_classifies_partial_dates():
    odds_only = _make_odds_candidate()  # no predictions
    dates = [evaluate_p15_readiness_for_date("2026-05-05", [odds_only])]
    plan = build_source_artifact_build_plan(dates, [odds_only])
    # Not ready (missing predictions), not unsafe (has odds + outcomes)
    assert len(plan.dates_ready_to_build_p15_inputs) == 0


def test_build_plan_mixed_dates():
    joined = _make_joined_candidate()
    odds_only = _make_odds_candidate()

    dates = [
        evaluate_p15_readiness_for_date("2026-05-01", [joined]),  # ready
        evaluate_p15_readiness_for_date("2026-05-02", [odds_only]),  # partial
        evaluate_p15_readiness_for_date("2026-05-03", []),  # missing all
    ]
    plan = build_source_artifact_build_plan(dates, [joined, odds_only])
    assert "2026-05-01" in plan.dates_ready_to_build_p15_inputs
    assert "2026-05-03" in plan.dates_missing_all_sources
    assert plan.date_start == "2026-05-01"
    assert plan.date_end == "2026-05-03"


def test_build_plan_empty_dates():
    plan = build_source_artifact_build_plan([], [])
    assert plan.date_start == ""
    assert plan.date_end == ""


def test_build_plan_generates_recommended_commands():
    joined = _make_joined_candidate()
    dates = [evaluate_p15_readiness_for_date("2026-05-05", [joined])]
    plan = build_source_artifact_build_plan(dates, [joined])
    assert len(plan.recommended_safe_commands) > 0


# ---------------------------------------------------------------------------
# validate_build_plan
# ---------------------------------------------------------------------------


def test_validate_plan_accepts_valid_plan():
    joined = _make_joined_candidate()
    dates = [evaluate_p15_readiness_for_date("2026-05-05", [joined])]
    plan = build_source_artifact_build_plan(dates, [joined])
    valid, err = validate_build_plan(plan)
    assert valid is True
    assert err == ""


def test_validate_plan_accepts_empty_plan():
    plan = build_source_artifact_build_plan([], [])
    valid, err = validate_build_plan(plan)
    assert valid is True


# ---------------------------------------------------------------------------
# generate_safe_next_commands
# ---------------------------------------------------------------------------


def test_generate_commands_when_no_ready_dates():
    plan = build_source_artifact_build_plan([], [])
    cmds = generate_safe_next_commands(plan, "2026-05-01", "2026-05-12")
    assert any("NO DATES READY" in c for c in cmds)


def test_generate_commands_when_dates_ready():
    joined = _make_joined_candidate()
    dates = [evaluate_p15_readiness_for_date(f"2026-05-{i:02d}", [joined]) for i in range(1, 6)]
    plan = build_source_artifact_build_plan(dates, [joined])
    cmds = generate_safe_next_commands(plan, "2026-05-01", "2026-05-05")
    assert any("5" in c or "ready" in c.lower() for c in cmds)
