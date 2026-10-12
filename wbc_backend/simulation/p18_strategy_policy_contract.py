"""
wbc_backend/simulation/p18_strategy_policy_contract.py

P18 — Strategy policy recommendation contract types.

Defines the canonical output types for the P18 strategy policy risk repair:
  - StrategyPolicyCandidate  (alias for PolicyCandidate from grid)
  - StrategyPolicyGridReport (audit envelope)
  - StrategyPolicyRecommendation (final output contract)

Gate decisions:
  P18_STRATEGY_POLICY_RISK_REPAIRED         — selected policy satisfies all criteria
  P18_BLOCKED_NO_RISK_ACCEPTABLE_POLICY     — no candidate passed
  P18_FAIL_INPUT_MISSING                    — required input files absent
  P18_FAIL_CONTRACT_VIOLATION               — output contract check failed
  P18_FAIL_NON_DETERMINISTIC                — two runs disagree

PAPER_ONLY=true | PRODUCTION_READY=false always.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from wbc_backend.simulation.p18_strategy_policy_grid import (
    GridSearchReport,
    PolicyCandidate,
)

# Re-export alias
StrategyPolicyCandidate = PolicyCandidate


# ── Gate decision constants ────────────────────────────────────────────────────

GATE_REPAIRED = "P18_STRATEGY_POLICY_RISK_REPAIRED"
GATE_BLOCKED = "P18_BLOCKED_NO_RISK_ACCEPTABLE_POLICY"
GATE_INPUT_MISSING = "P18_FAIL_INPUT_MISSING"
GATE_CONTRACT_VIOLATION = "P18_FAIL_CONTRACT_VIOLATION"
GATE_NON_DETERMINISTIC = "P18_FAIL_NON_DETERMINISTIC"


# ── Report container ───────────────────────────────────────────────────────────

@dataclass(frozen=True)
class StrategyPolicyGridReport:
    """Audit-ready envelope for the full grid search output."""

    grid_report: GridSearchReport
    p16_prior_gate: str
    p16_prior_max_drawdown: float
    p16_prior_sharpe: float
    p16_prior_n_bets: int
    paper_only: bool = True
    production_ready: bool = False
    created_from: str = "P18_STRATEGY_POLICY_RISK_REPAIR"

    def __post_init__(self) -> None:
        if self.paper_only is not True:
            raise ValueError("paper_only must be True")
        if self.production_ready is not False:
            raise ValueError("production_ready must be False")


# ── Final recommendation ───────────────────────────────────────────────────────

@dataclass(frozen=True)
class StrategyPolicyRecommendation:
    """
    Final output contract for the P18 strategy policy risk repair.

    All fields required; paper_only=True, production_ready=False enforced.
    """

    selected_policy_id: Optional[str]
    edge_threshold: Optional[float]
    max_stake_cap: Optional[float]
    kelly_fraction: Optional[float]
    odds_decimal_max: Optional[float]
    n_bets: Optional[int]
    roi_mean: Optional[float]
    roi_ci_low_95: Optional[float]
    roi_ci_high_95: Optional[float]
    max_drawdown_pct: Optional[float]
    sharpe_ratio: Optional[float]
    hit_rate: Optional[float]
    selection_reason: str
    gate_decision: str
    paper_only: bool = True
    production_ready: bool = False

    def __post_init__(self) -> None:
        valid_gates = {
            GATE_REPAIRED,
            GATE_BLOCKED,
            GATE_INPUT_MISSING,
            GATE_CONTRACT_VIOLATION,
            GATE_NON_DETERMINISTIC,
        }
        if self.gate_decision not in valid_gates:
            raise ValueError(f"Unknown gate_decision: {self.gate_decision}")
        if self.paper_only is not True:
            raise ValueError("paper_only must be True")
        if self.production_ready is not False:
            raise ValueError("production_ready must be False")

    def as_dict(self) -> dict:
        return {
            "selected_policy_id": self.selected_policy_id,
            "edge_threshold": self.edge_threshold,
            "max_stake_cap": self.max_stake_cap,
            "kelly_fraction": self.kelly_fraction,
            "odds_decimal_max": self.odds_decimal_max,
            "n_bets": self.n_bets,
            "roi_mean": self.roi_mean,
            "roi_ci_low_95": self.roi_ci_low_95,
            "roi_ci_high_95": self.roi_ci_high_95,
            "max_drawdown_pct": self.max_drawdown_pct,
            "sharpe_ratio": self.sharpe_ratio,
            "hit_rate": self.hit_rate,
            "selection_reason": self.selection_reason,
            "gate_decision": self.gate_decision,
            "paper_only": self.paper_only,
            "production_ready": self.production_ready,
        }


# ── Factory ────────────────────────────────────────────────────────────────────

def build_recommendation(
    grid_report: GridSearchReport,
) -> StrategyPolicyRecommendation:
    """
    Build the final StrategyPolicyRecommendation from a completed grid report.
    """
    best = grid_report.best_candidate

    if best is not None:
        return StrategyPolicyRecommendation(
            selected_policy_id=best.policy_id,
            edge_threshold=best.edge_threshold,
            max_stake_cap=best.max_stake_cap,
            kelly_fraction=best.kelly_fraction,
            odds_decimal_max=best.odds_decimal_max,
            n_bets=best.n_bets,
            roi_mean=best.roi_mean,
            roi_ci_low_95=best.roi_ci_low_95,
            roi_ci_high_95=best.roi_ci_high_95,
            max_drawdown_pct=best.max_drawdown_pct,
            sharpe_ratio=best.sharpe_ratio,
            hit_rate=best.hit_rate,
            selection_reason=grid_report.selection_reason,
            gate_decision=grid_report.gate_decision,
            paper_only=True,
            production_ready=False,
        )
    else:
        return StrategyPolicyRecommendation(
            selected_policy_id=None,
            edge_threshold=None,
            max_stake_cap=None,
            kelly_fraction=None,
            odds_decimal_max=None,
            n_bets=None,
            roi_mean=None,
            roi_ci_low_95=None,
            roi_ci_high_95=None,
            max_drawdown_pct=None,
            sharpe_ratio=None,
            hit_rate=None,
            selection_reason=grid_report.selection_reason,
            gate_decision=grid_report.gate_decision,
            paper_only=True,
            production_ready=False,
        )
