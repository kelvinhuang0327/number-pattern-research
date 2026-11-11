"""
tests/test_p17_paper_ledger_contract.py

Unit tests for P17 paper ledger frozen dataclass contracts.
"""
import pytest
from wbc_backend.recommendation.p17_paper_ledger_contract import (
    ALL_SETTLEMENT_STATUSES,
    CREATED_FROM,
    P16_6_ELIGIBLE_DECISION,
    P17_BLOCKED_CONTRACT_VIOLATION,
    P17_BLOCKED_NO_ACTIVE_RECOMMENDATIONS,
    P17_BLOCKED_SETTLEMENT_JOIN_INCOMPLETE,
    P17_FAIL_INPUT_MISSING,
    P17_FAIL_NON_DETERMINISTIC,
    P17_PAPER_LEDGER_READY,
    SETTLED_LOSS,
    SETTLED_PUSH,
    SETTLED_WIN,
    SOURCE_PHASE,
    UNSETTLED_INVALID_ODDS,
    UNSETTLED_INVALID_STAKE,
    UNSETTLED_MISSING_OUTCOME,
    UNSETTLED_NOT_RECOMMENDED,
    P17LedgerGateResult,
    PaperLedgerEntry,
    PaperLedgerSummary,
    SettlementJoinResult,
    ValidationResult,
)


class TestSettlementStatusConstants:
    def test_all_statuses_populated(self):
        assert len(ALL_SETTLEMENT_STATUSES) == 7

    def test_settled_statuses_in_set(self):
        assert SETTLED_WIN in ALL_SETTLEMENT_STATUSES
        assert SETTLED_LOSS in ALL_SETTLEMENT_STATUSES
        assert SETTLED_PUSH in ALL_SETTLEMENT_STATUSES

    def test_unsettled_statuses_in_set(self):
        assert UNSETTLED_MISSING_OUTCOME in ALL_SETTLEMENT_STATUSES
        assert UNSETTLED_INVALID_ODDS in ALL_SETTLEMENT_STATUSES
        assert UNSETTLED_INVALID_STAKE in ALL_SETTLEMENT_STATUSES
        assert UNSETTLED_NOT_RECOMMENDED in ALL_SETTLEMENT_STATUSES

    def test_gate_constants_defined(self):
        assert P17_PAPER_LEDGER_READY.startswith("P17_")
        assert P17_BLOCKED_NO_ACTIVE_RECOMMENDATIONS.startswith("P17_")
        assert P17_BLOCKED_SETTLEMENT_JOIN_INCOMPLETE.startswith("P17_")
        assert P17_BLOCKED_CONTRACT_VIOLATION.startswith("P17_")
        assert P17_FAIL_INPUT_MISSING.startswith("P17_")
        assert P17_FAIL_NON_DETERMINISTIC.startswith("P17_")

    def test_source_phase_and_created_from(self):
        assert SOURCE_PHASE == "P16_6"
        assert "P17" in CREATED_FROM


class TestPaperLedgerEntryFrozen:
    def _make_entry(self, **overrides) -> PaperLedgerEntry:
        defaults = dict(
            ledger_id="L17-TEST000001",
            recommendation_id="R-001",
            game_id="2025-05-08_MIN_BAL",
            date="2025-05-08",
            side="HOME",
            p_model=0.60,
            p_market=0.55,
            edge=0.05,
            odds_decimal=1.80,
            paper_stake_fraction=0.0025,
            paper_stake_units=0.25,
            policy_id="e0p0500_s0p0025_k0p10_o2p50",
            strategy_policy="capped_kelly_p18",
            gate_decision=P16_6_ELIGIBLE_DECISION,
            gate_reason="eligible",
            paper_only=True,
            production_ready=False,
            source_phase=SOURCE_PHASE,
            created_from=CREATED_FROM,
            y_true=1.0,
            settlement_status=SETTLED_WIN,
            settlement_reason="y_true=1.0, side=HOME, odds=1.8000",
            pnl_units=0.20,
            roi=0.80,
            is_win=True,
            is_loss=False,
            is_push=False,
            risk_profile_max_drawdown=1.847,
            risk_profile_sharpe=0.1016,
            risk_profile_n_bets=324,
        )
        defaults.update(overrides)
        return PaperLedgerEntry(**defaults)

    def test_entry_is_frozen(self):
        entry = self._make_entry()
        with pytest.raises(Exception):  # FrozenInstanceError
            entry.paper_only = False  # type: ignore[misc]

    def test_entry_paper_only_true(self):
        entry = self._make_entry()
        assert entry.paper_only is True

    def test_entry_production_ready_false(self):
        entry = self._make_entry()
        assert entry.production_ready is False

    def test_entry_source_phase(self):
        entry = self._make_entry()
        assert entry.source_phase == "P16_6"

    def test_entry_created_from(self):
        entry = self._make_entry()
        assert "P17" in entry.created_from


class TestPaperLedgerSummaryFrozen:
    def _make_summary(self, **overrides) -> PaperLedgerSummary:
        defaults = dict(
            p17_gate=P17_PAPER_LEDGER_READY,
            source_p16_6_gate="P16_6_PAPER_RECOMMENDATION_GATE_READY",
            n_recommendation_rows=1577,
            n_active_paper_entries=324,
            n_settled_win=170,
            n_settled_loss=154,
            n_settled_push=0,
            n_unsettled=0,
            total_stake_units=81.0,
            total_pnl_units=5.0,
            roi_units=0.0617,
            hit_rate=0.5247,
            avg_edge=0.08,
            avg_odds_decimal=2.0,
            max_drawdown_pct=1.847,
            sharpe_ratio=0.1016,
            settlement_join_coverage=1.0,
            duplicate_game_id_count=0,
            unmatched_recommendation_count=0,
            paper_only=True,
            production_ready=False,
        )
        defaults.update(overrides)
        return PaperLedgerSummary(**defaults)

    def test_summary_frozen(self):
        summary = self._make_summary()
        with pytest.raises(Exception):
            summary.production_ready = True  # type: ignore[misc]

    def test_summary_safety_invariants(self):
        summary = self._make_summary()
        assert summary.paper_only is True
        assert summary.production_ready is False


class TestSettlementJoinResult:
    def test_basic(self):
        r = SettlementJoinResult(
            n_recommendations=100,
            n_joined=95,
            n_unmatched=5,
            n_duplicate_game_ids=2,
            join_coverage=0.95,
            join_method="game_id",
            join_quality="HIGH",
            risk_notes=["some note"],
        )
        assert r.join_coverage == 0.95
        assert r.join_quality == "HIGH"
        assert len(r.risk_notes) == 1

    def test_frozen(self):
        r = SettlementJoinResult(
            n_recommendations=10,
            n_joined=0,
            n_unmatched=10,
            n_duplicate_game_ids=0,
            join_coverage=0.0,
            join_method="none",
            join_quality="NONE",
        )
        with pytest.raises(Exception):
            r.join_quality = "HIGH"  # type: ignore[misc]


class TestP17LedgerGateResult:
    def test_basic(self):
        g = P17LedgerGateResult(
            gate_decision=P17_PAPER_LEDGER_READY,
            paper_only=True,
            production_ready=False,
            n_active_entries=324,
            n_settled=324,
            n_unsettled=0,
            settlement_join_quality="HIGH",
            error_message=None,
        )
        assert g.paper_only is True
        assert g.production_ready is False


class TestValidationResult:
    def test_valid(self):
        v = ValidationResult(valid=True, error_code=None, error_message=None)
        assert v.valid is True

    def test_invalid(self):
        v = ValidationResult(
            valid=False,
            error_code=P17_BLOCKED_CONTRACT_VIOLATION,
            error_message="production_ready=True found",
        )
        assert v.valid is False
        assert v.error_code == P17_BLOCKED_CONTRACT_VIOLATION
