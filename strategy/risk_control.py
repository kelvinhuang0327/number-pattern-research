"""
Risk Control AI.

Enforces automatic stop-loss and circuit-breaker rules.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List
from config import settings as cfg
from strategy.kelly_criterion import BankrollState
from strategy.sharp_detector import MarketSignal


@dataclass
class RiskStatus:
    allow_betting: bool = True
    reasons: List[str] = field(default_factory=list)
    risk_level: str = "GREEN"   # GREEN / YELLOW / RED


def evaluate(
    state: BankrollState,
    market_signals: List[MarketSignal],
    recent_errors: List[float] | None = None,
) -> RiskStatus:
    """
    Evaluate whether betting should continue.
    """
    status = RiskStatus()
    reasons = []

    # ── 1. Daily loss stop ───────────────────────────────
    if state.current > 0:
        daily_loss_pct = -state.daily_pnl / state.initial
        if daily_loss_pct >= cfg.DAILY_LOSS_STOP_PCT:
            reasons.append(
                f"Daily loss {daily_loss_pct:.1%} ≥ {cfg.DAILY_LOSS_STOP_PCT:.0%} limit"
            )
            status.risk_level = "RED"

    # ── 2. Model prediction errors ───────────────────────
    if recent_errors:
        consecutive_bad = 0
        for err in reversed(recent_errors):
            if err > cfg.MODEL_ERROR_THRESHOLD:
                consecutive_bad += 1
            else:
                break
        if consecutive_bad >= cfg.MODEL_ERROR_CONSECUTIVE:
            reasons.append(
                f"Model error > {cfg.MODEL_ERROR_THRESHOLD:.0%} for "
                f"{consecutive_bad} consecutive games"
            )
            status.risk_level = "RED"

    # ── 3. Market anomalies ──────────────────────────────
    anomaly_count = sum(
        1 for s in market_signals
        if s.signal in ("TRAP_LINE", "INSIDER_MOVEMENT")
    )
    if anomaly_count >= cfg.MARKET_ANOMALY_LIMIT:
        reasons.append(
            f"Market anomalies ({anomaly_count}) ≥ limit ({cfg.MARKET_ANOMALY_LIMIT})"
        )
        status.risk_level = "RED"
    elif anomaly_count > 0:
        if status.risk_level != "RED":
            status.risk_level = "YELLOW"

    # ── 4. Drawdown check (V3 Adaptive) ──────────────────
    if state.drawdown_pct >= cfg.DRAWDOWN_MAX * 0.5:
        reasons.append(
            f"Drawdown {state.drawdown_pct:.1%} ≥ 50% of Limit ({cfg.DRAWDOWN_MAX:.0%}) "
            f"→ Adaptive Kelly aggressive decay active."
        )
        if status.risk_level == "GREEN":
            status.risk_level = "YELLOW"

    # ── Final decision ───────────────────────────────────
    if status.risk_level == "RED":
        status.allow_betting = False
    status.reasons = reasons if reasons else ["All systems nominal"]

    return status
