"""
tests/test_p17_paper_ledger_writer.py

Unit tests for P17 paper ledger writer — build, settle, summarize, validate.
"""
import math
import pytest
import pandas as pd

from wbc_backend.recommendation.p17_paper_ledger_contract import (
    P16_6_ELIGIBLE_DECISION,
    P17_BLOCKED_CONTRACT_VIOLATION,
    P17_BLOCKED_NO_ACTIVE_RECOMMENDATIONS,
    P17_PAPER_LEDGER_READY,
    SETTLED_LOSS,
    SETTLED_WIN,
    UNSETTLED_INVALID_ODDS,
    UNSETTLED_INVALID_STAKE,
    UNSETTLED_MISSING_OUTCOME,
    UNSETTLED_NOT_RECOMMENDED,
)
from wbc_backend.recommendation.p17_paper_ledger_writer import (
    build_paper_ledger,
    settle_ledger_entries,
    summarize_paper_ledger,
    validate_paper_ledger_contract,
)


# ── Fixtures ───────────────────────────────────────────────────────────────────

ELIGIBLE_GATE = P16_6_ELIGIBLE_DECISION
BLOCKED_GATE = "P16_6_BLOCKED_EDGE_BELOW_P18_THRESHOLD"

BASE_ROW = dict(
    recommendation_id="R-001",
    game_id="2025-05-08_MIN_BAL",
    date="2025-05-08",
    side="HOME",
    p_model=0.60,
    p_market=0.55,
    edge=0.0535,
    odds_decimal=1.80,
    paper_stake_fraction=0.0025,
    strategy_policy="capped_kelly_p18",
    gate_decision=ELIGIBLE_GATE,
    gate_reason="eligible",
    source_model="test_model",
    source_bss_oof=0.05,
    odds_join_status="JOINED",
    paper_only=True,
    production_ready=False,
    created_from="P16_6_RECOMMENDATION_GATE_RERUN_WITH_P18_POLICY",
    selected_edge_threshold=0.05,
    p18_policy_id="e0p0500_s0p0025_k0p10_o2p50",
    p18_edge_threshold=0.05,
    p18_max_stake_cap=0.0025,
    p18_kelly_fraction=0.10,
    p18_odds_decimal_max=2.5,
    p18_policy_max_drawdown_pct=1.847,
    p18_policy_sharpe_ratio=0.1016,
    p18_policy_n_bets=324,
    p18_policy_roi_ci_low_95=-0.99,
    p18_policy_roi_ci_high_95=20.78,
)


def make_rec_df(**row_overrides) -> pd.DataFrame:
    row = {**BASE_ROW, **row_overrides}
    return pd.DataFrame([row])


def make_multi_rec_df(rows: list[dict]) -> pd.DataFrame:
    """Build a recommendation DataFrame from a list of row dicts (merged with BASE_ROW)."""
    merged = []
    for r in rows:
        merged.append({**BASE_ROW, **r})
    return pd.DataFrame(merged)


# ── Tests for build_paper_ledger ──────────────────────────────────────────────

class TestBuildPaperLedger:
    def test_eligible_row_becomes_active_entry(self):
        df = make_rec_df()
        ledger = build_paper_ledger(df, bankroll_units=100.0)
        assert len(ledger) == 1
        assert ledger.iloc[0]["gate_decision"] == ELIGIBLE_GATE

    def test_eligible_row_stake_units_correct(self):
        df = make_rec_df(paper_stake_fraction=0.0025)
        ledger = build_paper_ledger(df, bankroll_units=100.0)
        row = ledger.iloc[0]
        assert abs(row["paper_stake_units"] - 0.25) < 1e-9

    def test_blocked_row_stake_units_zero(self):
        df = make_rec_df(gate_decision=BLOCKED_GATE)
        ledger = build_paper_ledger(df, bankroll_units=100.0)
        row = ledger.iloc[0]
        assert row["paper_stake_units"] == 0.0

    def test_blocked_row_settlement_status_not_recommended(self):
        df = make_rec_df(gate_decision=BLOCKED_GATE)
        ledger = build_paper_ledger(df, bankroll_units=100.0)
        row = ledger.iloc[0]
        assert row["settlement_status"] == UNSETTLED_NOT_RECOMMENDED

    def test_paper_only_true(self):
        df = make_rec_df()
        ledger = build_paper_ledger(df)
        assert all(ledger["paper_only"].astype(bool))

    def test_production_ready_false(self):
        df = make_rec_df()
        ledger = build_paper_ledger(df)
        assert not any(ledger["production_ready"].astype(bool))

    def test_ledger_id_deterministic(self):
        df = make_rec_df()
        ledger1 = build_paper_ledger(df)
        ledger2 = build_paper_ledger(df)
        assert ledger1.iloc[0]["ledger_id"] == ledger2.iloc[0]["ledger_id"]

    def test_multiple_rows_preserved(self):
        rows = [
            {"recommendation_id": f"R-{i:03d}", "game_id": f"2025-01-0{i}_A_B"}
            for i in range(5)
        ]
        df = make_multi_rec_df(rows)
        ledger = build_paper_ledger(df)
        assert len(ledger) == 5

    def test_missing_required_column_raises(self):
        df = make_rec_df()
        df = df.drop(columns=["gate_decision"])
        with pytest.raises(ValueError):
            build_paper_ledger(df)


# ── Tests for settle_ledger_entries ──────────────────────────────────────────

class TestSettleLedgerEntries:
    def _build_and_settle(self, **overrides):
        df = make_rec_df(**overrides)
        ledger = build_paper_ledger(df, bankroll_units=100.0)
        return settle_ledger_entries(ledger)

    def test_y_true_1_home_side_settled_win(self):
        settled = self._build_and_settle(y_true=1.0, side="HOME", odds_decimal=2.0)
        row = settled.iloc[0]
        assert row["settlement_status"] == SETTLED_WIN
        assert bool(row["is_win"]) is True
        assert row["pnl_units"] > 0

    def test_y_true_1_home_side_pnl_correct(self):
        # stake_units = 100 * 0.0025 = 0.25; odds=2.0; pnl = 0.25 * (2.0 - 1) = 0.25
        settled = self._build_and_settle(y_true=1.0, side="HOME", odds_decimal=2.0,
                                          paper_stake_fraction=0.0025)
        row = settled.iloc[0]
        assert abs(row["pnl_units"] - 0.25) < 1e-9

    def test_y_true_0_home_side_settled_loss(self):
        settled = self._build_and_settle(y_true=0.0, side="HOME", odds_decimal=2.0)
        row = settled.iloc[0]
        assert row["settlement_status"] == SETTLED_LOSS
        assert bool(row["is_loss"]) is True
        assert row["pnl_units"] < 0

    def test_y_true_0_home_side_pnl_minus_stake(self):
        # stake = 0.25; pnl = -0.25
        settled = self._build_and_settle(y_true=0.0, side="HOME", odds_decimal=2.0,
                                          paper_stake_fraction=0.0025)
        row = settled.iloc[0]
        assert abs(row["pnl_units"] - (-0.25)) < 1e-9

    def test_y_true_0_away_side_settled_win(self):
        # AWAY bet: home lost (y_true=0) → AWAY wins
        settled = self._build_and_settle(y_true=0.0, side="AWAY", odds_decimal=2.0)
        row = settled.iloc[0]
        assert row["settlement_status"] == SETTLED_WIN

    def test_y_true_1_away_side_settled_loss(self):
        # AWAY bet: home won (y_true=1) → AWAY loses
        settled = self._build_and_settle(y_true=1.0, side="AWAY", odds_decimal=2.0)
        row = settled.iloc[0]
        assert row["settlement_status"] == SETTLED_LOSS

    def test_missing_y_true_unsettled(self):
        settled = self._build_and_settle()  # no y_true → defaults to None
        row = settled.iloc[0]
        assert row["settlement_status"] == UNSETTLED_MISSING_OUTCOME
        assert row["pnl_units"] == 0.0

    def test_invalid_odds_unsettled(self):
        df = make_rec_df(y_true=1.0, odds_decimal=0.5)  # <= 1.0 → invalid
        ledger = build_paper_ledger(df, bankroll_units=100.0)
        # Override odds_decimal in ledger directly
        ledger_copy = ledger.copy()
        ledger_copy.loc[0, "odds_decimal"] = 0.5
        settled = settle_ledger_entries(ledger_copy)
        row = settled.iloc[0]
        assert row["settlement_status"] == UNSETTLED_INVALID_ODDS
        assert row["pnl_units"] == 0.0

    def test_invalid_stake_unsettled(self):
        df = make_rec_df(y_true=1.0)
        ledger = build_paper_ledger(df, bankroll_units=100.0)
        ledger_copy = ledger.copy()
        ledger_copy.loc[0, "paper_stake_units"] = -1.0  # negative → invalid
        settled = settle_ledger_entries(ledger_copy)
        row = settled.iloc[0]
        assert row["settlement_status"] == UNSETTLED_INVALID_STAKE
        assert row["pnl_units"] == 0.0

    def test_blocked_rows_remain_not_recommended(self):
        rows = [
            {"gate_decision": ELIGIBLE_GATE, "y_true": 1.0, "recommendation_id": "R-001"},
            {"gate_decision": BLOCKED_GATE, "y_true": 1.0, "recommendation_id": "R-002"},
        ]
        df = make_multi_rec_df(rows)
        ledger = build_paper_ledger(df, bankroll_units=100.0)
        settled = settle_ledger_entries(ledger)
        blocked_row = settled[settled["gate_decision"] == BLOCKED_GATE].iloc[0]
        assert blocked_row["settlement_status"] == UNSETTLED_NOT_RECOMMENDED
        assert blocked_row["pnl_units"] == 0.0

    def test_roi_computed_correctly(self):
        # stake=0.25, pnl=0.25, roi=1.0
        settled = self._build_and_settle(y_true=1.0, side="HOME", odds_decimal=2.0,
                                          paper_stake_fraction=0.0025)
        row = settled.iloc[0]
        assert abs(row["roi"] - 1.0) < 1e-9


# ── Tests for summarize_paper_ledger ─────────────────────────────────────────

class TestSummarizePaperLedger:
    def _make_settled_df(self, y_true_vals: list, gate_vals: list | None = None) -> pd.DataFrame:
        if gate_vals is None:
            gate_vals = [ELIGIBLE_GATE] * len(y_true_vals)
        rows = [
            {"gate_decision": g, "y_true": y, "recommendation_id": f"R-{i:03d}",
             "odds_decimal": 2.0}
            for i, (y, g) in enumerate(zip(y_true_vals, gate_vals))
        ]
        df = make_multi_rec_df(rows)
        ledger = build_paper_ledger(df, bankroll_units=100.0)
        return settle_ledger_entries(ledger)

    def test_gate_ready_when_some_settled(self):
        settled = self._make_settled_df([1.0, 0.0, 1.0])
        summary = summarize_paper_ledger(settled)
        assert summary.p17_gate == P17_PAPER_LEDGER_READY

    def test_gate_blocked_no_active_when_all_blocked(self):
        settled = self._make_settled_df(
            [1.0, 0.0],
            gate_vals=[BLOCKED_GATE, BLOCKED_GATE],
        )
        summary = summarize_paper_ledger(settled)
        assert summary.p17_gate == P17_BLOCKED_NO_ACTIVE_RECOMMENDATIONS

    def test_n_settled_win_loss_correct(self):
        settled = self._make_settled_df([1.0, 0.0, 1.0])
        summary = summarize_paper_ledger(settled)
        assert summary.n_settled_win == 2
        assert summary.n_settled_loss == 1

    def test_paper_only_true(self):
        settled = self._make_settled_df([1.0])
        summary = summarize_paper_ledger(settled)
        assert summary.paper_only is True

    def test_production_ready_false(self):
        settled = self._make_settled_df([1.0])
        summary = summarize_paper_ledger(settled)
        assert summary.production_ready is False


# ── Tests for validate_paper_ledger_contract ──────────────────────────────────

class TestValidatePaperLedgerContract:
    def _make_valid_settled() -> pd.DataFrame:
        df = make_rec_df(y_true=1.0)
        ledger = build_paper_ledger(df)
        return settle_ledger_entries(ledger)

    def test_valid_ledger_passes(self):
        df = make_rec_df(y_true=1.0)
        ledger = build_paper_ledger(df)
        settled = settle_ledger_entries(ledger)
        result = validate_paper_ledger_contract(settled)
        assert result.valid is True

    def test_production_ready_true_blocks(self):
        df = make_rec_df(y_true=1.0)
        ledger = build_paper_ledger(df)
        settled = settle_ledger_entries(ledger)
        settled = settled.copy()
        settled["production_ready"] = True
        result = validate_paper_ledger_contract(settled)
        assert result.valid is False
        assert result.error_code == P17_BLOCKED_CONTRACT_VIOLATION

    def test_paper_only_false_blocks(self):
        df = make_rec_df(y_true=1.0)
        ledger = build_paper_ledger(df)
        settled = settle_ledger_entries(ledger)
        settled = settled.copy()
        settled["paper_only"] = False
        result = validate_paper_ledger_contract(settled)
        assert result.valid is False
        assert result.error_code == P17_BLOCKED_CONTRACT_VIOLATION

    def test_blocked_row_non_zero_stake_blocks(self):
        df = make_rec_df(gate_decision=BLOCKED_GATE)
        ledger = build_paper_ledger(df)
        settled = settle_ledger_entries(ledger)
        settled = settled.copy()
        # Manually corrupt stake for blocked row
        settled.loc[settled["gate_decision"] == BLOCKED_GATE, "paper_stake_units"] = 1.0
        result = validate_paper_ledger_contract(settled)
        assert result.valid is False
        assert result.error_code == P17_BLOCKED_CONTRACT_VIOLATION

    def test_unsettled_pnl_non_zero_blocks(self):
        df = make_rec_df()  # no y_true → UNSETTLED_MISSING_OUTCOME
        ledger = build_paper_ledger(df)
        settled = settle_ledger_entries(ledger)
        settled = settled.copy()
        settled.loc[0, "pnl_units"] = 5.0  # corrupt
        result = validate_paper_ledger_contract(settled)
        assert result.valid is False
        assert result.error_code == P17_BLOCKED_CONTRACT_VIOLATION
