"""
wbc_backend/recommendation/p16_recommendation_row_builder.py

P16 Recommendation Row Builder — CEO-revised scope.

Constructs the canonical recommendation row including risk profile fields.

Row contract:
  - recommendation_id / game_id / date / side
  - p_model / p_market / edge / odds_decimal
  - paper_stake_fraction / strategy_policy
  - gate_decision / gate_reason
  - source_model / source_bss_oof / odds_join_status
  - paper_only / production_ready
  - created_from = "P16_RECOMMENDATION_GATE_REEVALUATION_RISK_HARDENED"
  - strategy_risk_profile_roi_ci_low_95
  - strategy_risk_profile_roi_ci_high_95
  - strategy_risk_profile_max_drawdown
  - strategy_risk_profile_sharpe
  - strategy_risk_profile_n_bets
  - selected_edge_threshold

Stake rules:
  - Gate fail → stake = 0
  - Gate pass → paper stake per capped_kelly capped at min(kelly, 0.02)
    and respects strategy_risk_profile

PAPER_ONLY: Paper simulation only. No production bets.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass

from wbc_backend.recommendation.p16_recommendation_gate import (
    GateResult,
    compute_paper_stake,
)
from wbc_backend.recommendation.p16_recommendation_input_adapter import P16InputRow
from wbc_backend.simulation.strategy_risk_metrics import StrategyRiskProfile

CREATED_FROM = "P16_RECOMMENDATION_GATE_REEVALUATION_RISK_HARDENED"
STRATEGY_POLICY = "capped_kelly"


# ── Row contract ──────────────────────────────────────────────────────────────

@dataclass
class P16RecommendationRow:
    recommendation_id: str
    game_id: str
    date: str
    side: str
    p_model: float | None
    p_market: float | None
    edge: float | None
    odds_decimal: float | None
    paper_stake_fraction: float
    strategy_policy: str
    gate_decision: str
    gate_reason: str
    source_model: str
    source_bss_oof: float
    odds_join_status: str
    paper_only: bool
    production_ready: bool
    created_from: str
    strategy_risk_profile_roi_ci_low_95: float
    strategy_risk_profile_roi_ci_high_95: float
    strategy_risk_profile_max_drawdown: float
    strategy_risk_profile_sharpe: float
    strategy_risk_profile_n_bets: int
    selected_edge_threshold: float

    def to_dict(self) -> dict:
        return asdict(self)


# ── Deterministic ID ──────────────────────────────────────────────────────────

def _make_recommendation_id(
    game_id: str,
    date: str,
    gate_decision: str,
    selected_edge_threshold: float,
) -> str:
    """
    Deterministic recommendation ID based on key fields.
    Uses SHA-256 truncated to 12 hex chars.
    """
    key = f"{game_id}|{date}|{gate_decision}|{selected_edge_threshold:.6f}"
    return "P16-" + hashlib.sha256(key.encode()).hexdigest()[:12].upper()


def _determine_side(row: P16InputRow) -> str:
    """
    Determine the side the model recommends based on edge direction.
    Positive edge → home team favoured by model.
    Negative edge → away team favoured by model.
    """
    if row.edge is None:
        return "UNKNOWN"
    return "HOME" if row.edge >= 0.0 else "AWAY"


# ── Builder ───────────────────────────────────────────────────────────────────

def build_recommendation_row(
    row: P16InputRow,
    gate: GateResult,
    risk_profile: StrategyRiskProfile,
    selected_edge_threshold: float,
    max_stake_cap: float = 0.02,
) -> P16RecommendationRow:
    """
    Build a P16 recommendation row.

    Parameters
    ----------
    row : P16InputRow
        Adapted P15 input row.
    gate : GateResult
        Gate decision for this row.
    risk_profile : StrategyRiskProfile
        Strategy risk profile from sweep.
    selected_edge_threshold : float
        Threshold selected by sweep.
    max_stake_cap : float
        Maximum paper stake cap. Default 0.02.

    Returns
    -------
    P16RecommendationRow
    """
    stake = compute_paper_stake(row, gate, risk_profile, max_stake_cap=max_stake_cap)
    side = _determine_side(row)
    rec_id = _make_recommendation_id(
        row.game_id, row.date, gate.decision, selected_edge_threshold
    )

    return P16RecommendationRow(
        recommendation_id=rec_id,
        game_id=row.game_id,
        date=row.date,
        side=side,
        p_model=row.p_model,
        p_market=row.p_market,
        edge=row.edge,
        odds_decimal=row.odds_decimal,
        paper_stake_fraction=stake,
        strategy_policy=STRATEGY_POLICY,
        gate_decision=gate.decision,
        gate_reason=gate.reason_code,
        source_model=row.source_model,
        source_bss_oof=row.source_bss_oof,
        odds_join_status=row.odds_join_status,
        paper_only=row.paper_only,
        production_ready=row.production_ready,
        created_from=CREATED_FROM,
        strategy_risk_profile_roi_ci_low_95=risk_profile.roi_ci_low_95,
        strategy_risk_profile_roi_ci_high_95=risk_profile.roi_ci_high_95,
        strategy_risk_profile_max_drawdown=risk_profile.max_drawdown_pct,
        strategy_risk_profile_sharpe=risk_profile.sharpe_ratio,
        strategy_risk_profile_n_bets=risk_profile.n_bets,
        selected_edge_threshold=selected_edge_threshold,
    )


def build_all_rows(
    input_rows: list[P16InputRow],
    gate_results: list[GateResult],
    risk_profile: StrategyRiskProfile,
    selected_edge_threshold: float,
    max_stake_cap: float = 0.02,
) -> list[P16RecommendationRow]:
    """
    Build all recommendation rows from parallel input_rows + gate_results lists.
    """
    assert len(input_rows) == len(gate_results), (
        f"input_rows ({len(input_rows)}) and gate_results ({len(gate_results)}) "
        "must have the same length"
    )
    return [
        build_recommendation_row(r, g, risk_profile, selected_edge_threshold, max_stake_cap)
        for r, g in zip(input_rows, gate_results)
    ]


# ── P16.6 extensions (P18 policy gate re-run) ─────────────────────────────────

CREATED_FROM_P16_6 = "P16_6_RECOMMENDATION_GATE_RERUN_WITH_P18_POLICY"
STRATEGY_POLICY_P16_6 = "capped_kelly_p18"


@dataclass
class P16_6RecommendationRow:
    """Extended recommendation row with P18 policy metadata (P16.6 re-run)."""

    # ── Core row fields ────────────────────────────────────────────────────────
    recommendation_id: str
    game_id: str
    date: str
    side: str
    p_model: float | None
    p_market: float | None
    edge: float | None
    odds_decimal: float | None
    paper_stake_fraction: float
    strategy_policy: str
    gate_decision: str
    gate_reason: str
    source_model: str
    source_bss_oof: float
    odds_join_status: str
    paper_only: bool
    production_ready: bool
    created_from: str
    selected_edge_threshold: float

    # ── P18 policy fields ──────────────────────────────────────────────────────
    p18_policy_id: str
    p18_edge_threshold: float
    p18_max_stake_cap: float
    p18_kelly_fraction: float
    p18_odds_decimal_max: float
    p18_policy_max_drawdown_pct: float
    p18_policy_sharpe_ratio: float
    p18_policy_n_bets: int
    p18_policy_roi_ci_low_95: float
    p18_policy_roi_ci_high_95: float

    def to_dict(self) -> dict:
        return {
            "recommendation_id": self.recommendation_id,
            "game_id": self.game_id,
            "date": self.date,
            "side": self.side,
            "p_model": self.p_model,
            "p_market": self.p_market,
            "edge": self.edge,
            "odds_decimal": self.odds_decimal,
            "paper_stake_fraction": self.paper_stake_fraction,
            "strategy_policy": self.strategy_policy,
            "gate_decision": self.gate_decision,
            "gate_reason": self.gate_reason,
            "source_model": self.source_model,
            "source_bss_oof": self.source_bss_oof,
            "odds_join_status": self.odds_join_status,
            "paper_only": self.paper_only,
            "production_ready": self.production_ready,
            "created_from": self.created_from,
            "selected_edge_threshold": self.selected_edge_threshold,
            "p18_policy_id": self.p18_policy_id,
            "p18_edge_threshold": self.p18_edge_threshold,
            "p18_max_stake_cap": self.p18_max_stake_cap,
            "p18_kelly_fraction": self.p18_kelly_fraction,
            "p18_odds_decimal_max": self.p18_odds_decimal_max,
            "p18_policy_max_drawdown_pct": self.p18_policy_max_drawdown_pct,
            "p18_policy_sharpe_ratio": self.p18_policy_sharpe_ratio,
            "p18_policy_n_bets": self.p18_policy_n_bets,
            "p18_policy_roi_ci_low_95": self.p18_policy_roi_ci_low_95,
            "p18_policy_roi_ci_high_95": self.p18_policy_roi_ci_high_95,
        }


def build_recommendation_row_p16_6(
    row: P16InputRow,
    gate: GateResult,
    p18_policy: "P18SelectedPolicy",
    stake: float,
) -> P16_6RecommendationRow:
    """Build a single P16.6 recommendation row."""
    edge = row.edge
    side = "HOME" if (edge is not None and edge >= 0) else "AWAY"

    rec_id = _make_recommendation_id(
        row.game_id, row.date, gate.decision, p18_policy.edge_threshold
    )

    return P16_6RecommendationRow(
        recommendation_id=rec_id,
        game_id=row.game_id,
        date=row.date,
        side=side,
        p_model=row.p_model,
        p_market=row.p_market,
        edge=row.edge,
        odds_decimal=row.odds_decimal,
        paper_stake_fraction=stake,
        strategy_policy=STRATEGY_POLICY_P16_6,
        gate_decision=gate.decision,
        gate_reason=gate.reason_code,
        source_model=row.source_model,
        source_bss_oof=row.source_bss_oof,
        odds_join_status=row.odds_join_status,
        paper_only=row.paper_only,
        production_ready=row.production_ready,
        created_from=CREATED_FROM_P16_6,
        selected_edge_threshold=p18_policy.edge_threshold,
        p18_policy_id=p18_policy.selected_policy_id,
        p18_edge_threshold=p18_policy.edge_threshold,
        p18_max_stake_cap=p18_policy.max_stake_cap,
        p18_kelly_fraction=p18_policy.kelly_fraction,
        p18_odds_decimal_max=p18_policy.odds_decimal_max,
        p18_policy_max_drawdown_pct=p18_policy.max_drawdown_pct,
        p18_policy_sharpe_ratio=p18_policy.sharpe_ratio,
        p18_policy_n_bets=p18_policy.n_bets,
        p18_policy_roi_ci_low_95=p18_policy.roi_ci_low_95,
        p18_policy_roi_ci_high_95=p18_policy.roi_ci_high_95,
    )


def build_all_rows_p16_6(
    input_rows: list[P16InputRow],
    gate_results: list[GateResult],
    stakes: list[float],
    p18_policy: "P18SelectedPolicy",
) -> list[P16_6RecommendationRow]:
    """
    Build all P16.6 recommendation rows from parallel input_rows + gate_results + stakes.
    """
    assert len(input_rows) == len(gate_results) == len(stakes), (
        "input_rows, gate_results, and stakes must have the same length"
    )
    return [
        build_recommendation_row_p16_6(r, g, p18_policy, s)
        for r, g, s in zip(input_rows, gate_results, stakes)
    ]


from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from wbc_backend.recommendation.p16_p18_policy_loader import P18SelectedPolicy
