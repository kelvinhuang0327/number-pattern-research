"""Tests for P257A — Best N-Bet Strategy Overview: Historical Replay Data + UI Contract.

Read-only artifact validation tests.
No DB write, no replay generation, no registry mutation, no strategy promotion, no betting advice.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO_ROOT    = Path(__file__).resolve().parent.parent
ARTIFACT_JSON = REPO_ROOT / "outputs" / "research" / "p257a_best_nbet_strategy_overview_historical_replay_20260608.json"
ARTIFACT_MD   = REPO_ROOT / "outputs" / "research" / "p257a_best_nbet_strategy_overview_historical_replay_20260608.md"

VALID_FINAL_DECISIONS = {
    "BEST_NBET_STRATEGY_OVERVIEW_DATA_READY_FOR_UI_DESIGN",
    "DATA_INSUFFICIENT_FOR_UI_IMPLEMENTATION",
    "HOLD_NEEDS_SCHEMA_CLARIFICATION",
}

FORBIDDEN_JACKPOT_PHRASES = [
    "大獎",
    "中大獎",
    "jackpot",
]


@pytest.fixture(scope="module")
def artifact() -> dict:
    assert ARTIFACT_JSON.exists(), f"Artifact missing: {ARTIFACT_JSON}"
    with ARTIFACT_JSON.open() as f:
        return json.load(f)


@pytest.fixture(scope="module")
def md_text() -> str:
    assert ARTIFACT_MD.exists(), f"Markdown missing: {ARTIFACT_MD}"
    return ARTIFACT_MD.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. Basic structure
# ---------------------------------------------------------------------------

def test_json_parses(artifact):
    assert isinstance(artifact, dict)


def test_task_id(artifact):
    assert artifact["task_id"] == "P257A"


def test_classification_exists(artifact):
    assert "classification" in artifact
    assert artifact["classification"]


def test_final_decision_valid(artifact):
    assert artifact["final_decision"] in VALID_FINAL_DECISIONS


# ---------------------------------------------------------------------------
# 2. Required top-level sections
# ---------------------------------------------------------------------------

def test_portfolio_metrics_exists(artifact):
    assert "portfolio_metrics_by_lottery_strategy_and_bet_count" in artifact
    assert isinstance(artifact["portfolio_metrics_by_lottery_strategy_and_bet_count"], list)
    assert len(artifact["portfolio_metrics_by_lottery_strategy_and_bet_count"]) > 0


def test_best_strategy_by_lottery_and_bet_count_exists(artifact):
    assert "best_strategy_by_lottery_and_bet_count" in artifact
    best = artifact["best_strategy_by_lottery_and_bet_count"]
    assert isinstance(best, dict)
    assert len(best) > 0


def test_high_hit_events_by_lottery_exists(artifact):
    assert "high_hit_events_by_lottery" in artifact
    assert isinstance(artifact["high_hit_events_by_lottery"], list)


def test_high_hit_events_by_lottery_and_bet_count_exists(artifact):
    assert "high_hit_events_by_lottery_and_bet_count" in artifact
    assert isinstance(artifact["high_hit_events_by_lottery_and_bet_count"], list)


def test_page_contract_exists(artifact):
    assert "page_contract" in artifact
    pc = artifact["page_contract"]
    assert "warning_copy" in pc
    assert "best_nbet_strategy_table_columns" in pc
    assert "high_hit_event_table_columns" in pc
    assert "empty_states" in pc


def test_ranking_rules_exist(artifact):
    rules = artifact.get("ranking_rules", [])
    assert len(rules) >= 7, "Ranking rules must include all 7 tie-breakers"
    rules_text = " ".join(rules).lower()
    # Verify all required tie-breakers are present
    assert "success_rate" in rules_text or "portfolio_success_rate" in rules_text
    assert "avg_best" in rules_text or "best_hit" in rules_text
    assert "avg_total" in rules_text or "total_hit" in rules_text
    assert "max_single" in rules_text or "single_bet" in rules_text
    assert "portfolio_total" in rules_text or "max_portfolio" in rules_text
    assert "distinct_draw" in rules_text or "draw_count" in rules_text
    assert "lexical" in rules_text or "strategy_id" in rules_text


# ---------------------------------------------------------------------------
# 3. Correct N-bet portfolio semantics (NOT bet_index ranking)
# ---------------------------------------------------------------------------

def test_primary_output_is_not_best_by_bet_index(artifact):
    """The primary ranking key must not be bet_index-centric."""
    # The key format must be 'lottery|N' not 'lottery|bet_index=N'
    for key in artifact["best_strategy_by_lottery_and_bet_count"]:
        assert "bet_index" not in key, (
            f"Key {key!r} suggests bet_index ranking, not N-bet portfolio ranking"
        )


def test_n2_metrics_are_portfolio_grouped(artifact):
    """For bet_count=2, portfolio_success_count must be based on distinct draws, not rows."""
    n2_metrics = [
        m for m in artifact["portfolio_metrics_by_lottery_strategy_and_bet_count"]
        if m["bet_count"] == 2
    ]
    assert len(n2_metrics) > 0, "No bet_count=2 metrics found"
    for m in n2_metrics:
        # portfolio_success_count <= distinct_draw_count (it's a fraction of draws, not rows)
        assert m["portfolio_success_count"] <= m["distinct_draw_count"], (
            f"portfolio_success_count ({m['portfolio_success_count']}) > "
            f"distinct_draw_count ({m['distinct_draw_count']}) — "
            f"suggests counting replay rows, not draws"
        )
        # For N=2, replay_row_count should be approximately 2× distinct_draw_count
        ratio = m["replay_row_count"] / max(m["distinct_draw_count"], 1)
        assert 1.0 < ratio <= 2.5, (
            f"bet_count=2 row/draw ratio={ratio:.2f} unexpected for {m['strategy_id']}; "
            f"rows={m['replay_row_count']}, draws={m['distinct_draw_count']}"
        )


def test_portfolio_success_rate_in_0_1(artifact):
    for m in artifact["portfolio_metrics_by_lottery_strategy_and_bet_count"]:
        sr = m["portfolio_success_rate"]
        assert 0.0 <= sr <= 1.0, f"portfolio_success_rate={sr} out of [0,1] for {m['strategy_id']}"


def test_portfolio_success_rate_computed_from_draws(artifact):
    """Rate = success_count / distinct_draw_count (not relay row count)."""
    for m in artifact["portfolio_metrics_by_lottery_strategy_and_bet_count"]:
        dc = m["distinct_draw_count"]
        sc = m["portfolio_success_count"]
        rate = m["portfolio_success_rate"]
        if dc > 0:
            expected = round(sc / dc, 4)
            assert abs(rate - expected) < 0.001, (
                f"success_rate mismatch: rate={rate}, sc/dc={expected} for {m['strategy_id']}"
            )


# ---------------------------------------------------------------------------
# 4. Baseline / governance flags
# ---------------------------------------------------------------------------

def test_baseline_replays(artifact):
    cab = artifact["current_accepted_baseline"]
    assert cab["strategy_prediction_replays"] == 94924


def test_baseline_big_lotto(artifact):
    cab = artifact["current_accepted_baseline"]
    assert cab["BIG_LOTTO_raw"] == 22239
    assert cab["BIG_LOTTO_canonical"] == 2114


@pytest.mark.parametrize("flag", [
    "no_db_write_confirmed",
    "no_replay_generation_confirmed",
    "no_registry_mutation_confirmed",
    "no_strategy_promotion_confirmed",
    "no_recommendation_logic_change_confirmed",
    "no_betting_advice_confirmed",
])
def test_governance_flags_all_true(artifact, flag):
    assert artifact.get(flag) is True, f"Flag {flag!r} must be True"


# ---------------------------------------------------------------------------
# 5. Warning copy includes required disclaimers
# ---------------------------------------------------------------------------

def test_warning_copy_historical_only(artifact):
    wc = artifact["page_contract"]["warning_copy"]
    all_warnings = " ".join(wc.get("zh", []) + wc.get("en", []))
    # Must include these concepts
    assert any(w in all_warnings for w in ("historical", "歷史", "回測")), \
        "Warning copy must mention historical/回測 nature"
    assert any(w in all_warnings for w in ("no betting", "不提供投注", "not betting advice")), \
        "Warning copy must disclaim betting advice"
    assert any(w in all_warnings for w in ("no future", "不代表未來", "future win")), \
        "Warning copy must disclaim future win guarantee"


def test_warning_copy_no_deployable_edge(artifact):
    wc = artifact["page_contract"]["warning_copy"]
    all_text = " ".join(wc.get("zh", []) + wc.get("en", []))
    assert "deployable" in all_text or "可部署" in all_text, \
        "Warning copy must mention no deployable edge"


# ---------------------------------------------------------------------------
# 6. No jackpot / prize-tier claims without evidence
# ---------------------------------------------------------------------------

def test_no_jackpot_language_in_artifact(artifact):
    """Forbidden jackpot phrases must not appear as promotional claims.
    They are allowed only in explicit disclaimer/negation contexts."""
    artifact_str = json.dumps(artifact, ensure_ascii=False)
    # Check line-by-line so we can verify each occurrence is in a disclaimer context
    for phrase in FORBIDDEN_JACKPOT_PHRASES:
        if phrase in artifact_str:
            # Find every JSON string segment containing the phrase and verify it's a disclaimer
            for chunk in artifact_str.split(phrase):
                pass  # presence alone is not an error; check context below
            # Extract surrounding context for each occurrence
            idx = 0
            while True:
                pos = artifact_str.find(phrase, idx)
                if pos == -1:
                    break
                context = artifact_str[max(0, pos - 60): pos + 60].lower()
                # Allowed only if in a negation/disclaimer context
                assert any(neg in context for neg in (
                    "不標示", "未提供", "not ", "no ", "prize_tier_note", "只顯示命中數"
                )), (
                    f"Phrase {phrase!r} found in non-disclaimer context near: "
                    f"{artifact_str[max(0,pos-40):pos+40]!r}"
                )
                idx = pos + 1


def test_no_jackpot_language_in_markdown(md_text):
    for phrase in FORBIDDEN_JACKPOT_PHRASES:
        # Allow "jackpot" only in the prize_tier_note field as a disclaimer
        occurrences = [line for line in md_text.splitlines() if phrase in line]
        for line in occurrences:
            # Must be in a disclaimer context, not a promotional claim
            assert any(neg in line.lower() for neg in ("no prize", "not ", "prize_tier_note", "未提供")), (
                f"Phrase {phrase!r} found outside disclaimer context: {line!r}"
            )


# ---------------------------------------------------------------------------
# 7. High-hit events use correct terminology
# ---------------------------------------------------------------------------

def test_high_hit_events_use_correct_terminology(artifact):
    for event in artifact["high_hit_events_by_lottery"]:
        assert event.get("event_type") == "historical_high_hit_event", (
            f"event_type should be 'historical_high_hit_event', got {event.get('event_type')!r}"
        )
        assert "prize_tier_note" in event


def test_high_hit_events_by_bet_count_have_required_fields(artifact):
    required = {"lottery_type", "bet_count", "strategy_id", "target_draw",
                "portfolio_total_hit_count", "event_type"}
    for event in artifact["high_hit_events_by_lottery_and_bet_count"]:
        missing = required - set(event.keys())
        assert not missing, f"High-hit event missing fields: {missing}"


# ---------------------------------------------------------------------------
# 8. Page contract structure
# ---------------------------------------------------------------------------

def test_page_contract_has_all_tabs(artifact):
    pc = artifact["page_contract"]
    tabs = pc["tab_model"]["tabs"]
    for lottery in ("BIG_LOTTO", "DAILY_539", "POWER_LOTTO", "3_STAR", "4_STAR"):
        assert lottery in tabs


def test_page_contract_empty_states_defined(artifact):
    pc = artifact["page_contract"]
    es = pc["empty_states"]
    assert "no_replay_lottery" in es
    assert "no_data_for_bet_count" in es
    assert "missing_predicted_numbers" in es
    assert "no_prize_tier" in es


def test_page_contract_best_nbet_table_columns(artifact):
    cols = {c["key"] for c in artifact["page_contract"]["best_nbet_strategy_table_columns"]}
    required_cols = {
        "bet_count_label", "strategy_id", "portfolio_success_rate",
        "avg_best_hit_count_per_draw", "max_single_bet_hit_count",
        "evidence_label",
    }
    missing = required_cols - cols
    assert not missing, f"Missing table columns: {missing}"
