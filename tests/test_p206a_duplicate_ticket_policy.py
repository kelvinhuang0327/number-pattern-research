from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wbc_backend.recommendation.duplicate_ticket_policy import (
    KEEP_OVERLAP_DIFFERENT_STRATEGY,
    SUPPRESS_EXACT_DUPLICATE,
    UNGROUPABLE_MISSING_IDENTITY,
    UNGROUPABLE_MISSING_MARKET,
    UNGROUPABLE_MISSING_SELECTED_SIDE,
    analyze_duplicate_tickets,
)
from wbc_backend.recommendation.provenance_contract import (
    PROVENANCE_CONTRACT_VERSION,
    build_provenance_contract,
)


def _contract(**overrides):
    base = dict(
        prediction_input_mode="historical_replay",
        prediction_source="unit-test-replay",
        prediction_source_id="824441",
        model_version="unit-test-v1",
        feature_fingerprint="feature-fp",
        prediction_as_of_utc="2026-05-11T10:00:00+00:00",
        game_specific=True,
        selected_side_method="argmax_model_probability",
        odds_source="historical_no_vig",
        odds_is_market_observed=False,
        edge_is_real_evidence=False,
        learning_eligible=False,
        learning_block_reason="historical_replay_descriptive_only",
    )
    base.update(overrides)
    return build_provenance_contract(**base)


def _row(**overrides):
    row = {
        "game_id": "2026-05-11-LAA-CLE-824441",
        "tsl_side": "home",
        "tsl_market": "moneyline",
        "strategy_id": "strategy-a",
        "source_trace": _contract(),
    }
    row.update(overrides)
    return row


def test_exact_duplicate_same_identity_side_market_and_strategy_is_suppressed():
    result = analyze_duplicate_tickets([_row(), _row()])

    assert result["total_input_rows"] == 2
    assert result["total_groups"] == 1
    assert result["kept_rows"] == 1
    assert result["suppressed_rows"] == 1
    assert result["decisions"][1]["suppress_reason"] == SUPPRESS_EXACT_DUPLICATE
    assert result["decisions"][0]["provenance_contract_version"] == PROVENANCE_CONTRACT_VERSION
    assert result["decisions"][0]["learning_guard_status"] == "not_learning_eligible"


def test_overlapping_different_strategy_is_grouped_but_not_suppressed():
    result = analyze_duplicate_tickets([_row(strategy_id="strategy-a"), _row(strategy_id="strategy-b")])

    assert result["total_groups"] == 1
    assert result["kept_rows"] == 2
    assert result["suppressed_rows"] == 0
    assert {decision["keep_reason"] for decision in result["decisions"]} == {
        KEEP_OVERLAP_DIFFERENT_STRATEGY
    }


def test_missing_identity_side_or_market_fail_closed_as_ungroupable():
    result = analyze_duplicate_tickets(
        [
            _row(game_id="2026-05-11-LAA-CLE"),
            _row(tsl_side=""),
            _row(tsl_market=""),
        ]
    )

    assert result["kept_rows"] == 3
    assert result["suppressed_rows"] == 0
    assert result["ungroupable_counts"] == {
        UNGROUPABLE_MISSING_IDENTITY: 1,
        UNGROUPABLE_MISSING_SELECTED_SIDE: 1,
        UNGROUPABLE_MISSING_MARKET: 1,
    }
    assert [decision["keep_reason"] for decision in result["decisions"]] == [
        UNGROUPABLE_MISSING_IDENTITY,
        UNGROUPABLE_MISSING_SELECTED_SIDE,
        UNGROUPABLE_MISSING_MARKET,
    ]


def test_team_date_text_is_not_fuzzy_matched_as_stable_identity():
    result = analyze_duplicate_tickets(
        [
            _row(game_id="2026-05-11-Los Angeles Angels-Cleveland Guardians"),
            _row(game_id="2026-05-11-LAA-CLE"),
        ]
    )

    assert result["total_groups"] == 0
    assert result["suppressed_rows"] == 0
    assert result["ungroupable_counts"][UNGROUPABLE_MISSING_IDENTITY] == 2
